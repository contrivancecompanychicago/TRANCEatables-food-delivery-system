"""One-way, idempotent SQLite to Grist synchronization for Stage 2.1.

Grist is an audit/dashboard mirror. This module never reads Grist data back into
SQLite and never emits robot or order commands.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class GristSyncError(RuntimeError):
    """Raised when configuration, SQLite, or Grist prevents synchronization."""


@dataclass(frozen=True)
class TableMapping:
    sqlite_query: str
    grist_table: str
    key_column: str
    transforms: dict[str, Callable[[Any], Any]] | None = None


@dataclass(frozen=True)
class SyncResult:
    table: str
    source_rows: int
    created: int
    updated: int
    unchanged: int
    dry_run: bool


def _epoch(value: Any) -> Any:
    if value in (None, ""):
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _boolean(value: Any) -> bool:
    return bool(value)


TABLE_MAPPINGS: tuple[TableMapping, ...] = (
    TableMapping(
        """SELECT order_id AS OrderId, restaurant_id AS RestaurantId,
        status AS Status, created_at AS CreatedAt, updated_at AS UpdatedAt,
        1 AS SimulationOnly FROM orders ORDER BY order_id""",
        "Orders", "OrderId",
        {"CreatedAt": _epoch, "UpdatedAt": _epoch, "SimulationOnly": _boolean},
    ),
    TableMapping(
        """SELECT 'ORDER-EVENT-' || event_id AS EventId, order_id AS OrderId,
        from_status AS PreviousStatus, to_status AS NewStatus,
        CASE WHEN from_status IS NULL THEN 'order_created'
             ELSE 'order_transition' END AS EventType,
        reason AS Message, occurred_at AS OccurredAt
        FROM order_events ORDER BY event_id""",
        "OrderEvents", "EventId", {"OccurredAt": _epoch},
    ),
    TableMapping(
        """SELECT meal_plan_id AS MealPlanId, order_id AS OrderId,
        nutrients_json AS Nutrients,
        json_extract(exact_quantities_json, '$[0]') AS Food1Exact,
        json_extract(exact_quantities_json, '$[1]') AS Food2Exact,
        json_extract(exact_quantities_json, '$[2]') AS Food3Exact,
        json_extract(quantities_json, '$[0]') AS Food1Quantity,
        json_extract(quantities_json, '$[1]') AS Food2Quantity,
        json_extract(quantities_json, '$[2]') AS Food3Quantity,
        calculated_targets_json AS CalculatedTargets,
        residuals_json AS Residuals, target_unit AS TargetUnit,
        quantity_unit AS QuantityUnit, status AS Status,
        food1_item_id AS Food1ItemId, food2_item_id AS Food2ItemId,
        food3_item_id AS Food3ItemId, created_at AS CreatedAt,
        updated_at AS UpdatedAt, simulation_only AS SimulationOnly
        FROM simulated_meal_plans ORDER BY meal_plan_id""",
        "SimulatedMealPlans", "MealPlanId",
        {"CreatedAt": _epoch, "UpdatedAt": _epoch,
         "SimulationOnly": _boolean},
    ),
    TableMapping(
        """SELECT 'MEAL-PLAN-EVENT-' || event_id AS EventId,
        meal_plan_id AS MealPlanId, event_type AS EventType,
        actor AS Actor, message AS Message, occurred_at AS OccurredAt
        FROM meal_plan_events ORDER BY event_id""",
        "MealPlanEvents", "EventId", {"OccurredAt": _epoch},
    ),
    TableMapping(
        """SELECT robot_id AS RobotId, name AS RobotName, status AS Status,
        battery_percent AS BatteryPercent, current_zone AS CurrentZone,
        payload_capacity_kg AS PayloadCapacityKg, operational AS Operational,
        1 AS SimulationOnly, updated_at AS UpdatedAt
        FROM simulated_robots ORDER BY robot_id""",
        "Robots", "RobotId",
        {"Operational": _boolean, "SimulationOnly": _boolean, "UpdatedAt": _epoch},
    ),
    TableMapping(
        """SELECT mission_id AS MissionId, order_id AS OrderId, robot_id AS RobotId,
        status AS Status, pickup_zone AS PickupZone, dropoff_zone AS DropoffZone,
        payload_kg AS PayloadKg, 1 AS RequiresApproval, created_at AS CreatedAt,
        updated_at AS UpdatedAt, 1 AS SimulationOnly
        FROM robot_missions ORDER BY mission_id""",
        "RobotMissions", "MissionId",
        {"RequiresApproval": _boolean, "CreatedAt": _epoch,
         "UpdatedAt": _epoch, "SimulationOnly": _boolean},
    ),
    TableMapping(
        """SELECT 'MISSION-EVENT-' || e.event_id AS EventId,
        e.mission_id AS MissionId, m.robot_id AS RobotId,
        e.from_status AS PreviousStatus, e.to_status AS NewStatus,
        'mission_transition' AS EventType, e.message AS Message,
        e.occurred_at AS OccurredAt
        FROM mission_events e JOIN robot_missions m USING (mission_id)
        ORDER BY e.event_id""",
        "MissionEvents", "EventId", {"OccurredAt": _epoch},
    ),
    TableMapping(
        """SELECT 'APPROVAL-' || approval_id AS ApprovalId,
        mission_id AS MissionId, decision AS Decision,
        operator_reference AS OperatorReference, note AS Notes,
        decided_at AS DecidedAt FROM operator_approvals ORDER BY approval_id""",
        "OperatorApprovals", "ApprovalId", {"DecidedAt": _epoch},
    ),
    TableMapping(
        """SELECT 'TELEMETRY-' || telemetry_id AS TelemetryId,
        robot_id AS RobotId, mission_id AS MissionId,
        battery_percent AS BatteryPercent, current_zone AS CurrentZone,
        position_x AS PositionX, position_y AS PositionY, speed_mps AS SpeedMps,
        observed_at AS ObservedAt FROM robot_telemetry ORDER BY telemetry_id""",
        "RobotTelemetry", "TelemetryId", {"ObservedAt": _epoch},
    ),
    TableMapping(
        """SELECT 'SAFETY-' || safety_event_id AS SafetyEventId,
        robot_id AS RobotId, mission_id AS MissionId, severity AS Severity,
        event_type AS EventType, message AS Message, resolved AS Resolved,
        occurred_at AS OccurredAt FROM robot_safety_events ORDER BY safety_event_id""",
        "SafetyEvents", "SafetyEventId",
        {"Resolved": _boolean, "OccurredAt": _epoch},
    ),
)


class GristClient:
    """Small dependency-free client for the Grist records API."""

    def __init__(self, base_url: str, doc_id: str, api_key: str, *, timeout: int = 30) -> None:
        if not base_url.startswith("https://"):
            raise GristSyncError("GRIST_BASE_URL must use https")
        if not doc_id or not api_key:
            raise GristSyncError("GRIST_DOC_ID and GRIST_API_KEY are required")
        self.base_url = base_url.rstrip("/")
        self.doc_id = doc_id
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            f"{self.base_url}/api/docs/{quote(self.doc_id, safe='')}{path}",
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read()
        except HTTPError as error:
            detail = error.read().decode(errors="replace")[:500]
            raise GristSyncError(f"Grist HTTP {error.code}: {detail}") from error
        except URLError as error:
            raise GristSyncError(f"Grist connection failed: {error.reason}") from error
        return json.loads(body) if body else {}

    def columns(self, table: str) -> set[str]:
        result = self._request("GET", f"/tables/{quote(table, safe='')}/columns")
        return {column["id"] for column in result.get("columns", [])}

    def records(self, table: str) -> list[dict[str, Any]]:
        result = self._request("GET", f"/tables/{quote(table, safe='')}/records")
        return list(result.get("records", []))

    def add(self, table: str, fields: list[dict[str, Any]]) -> None:
        if fields:
            self._request("POST", f"/tables/{quote(table, safe='')}/records",
                          {"records": [{"fields": row} for row in fields]})

    def update(self, table: str, records: list[dict[str, Any]]) -> None:
        if records:
            self._request("PATCH", f"/tables/{quote(table, safe='')}/records",
                          {"records": records})


def _source_rows(connection: sqlite3.Connection, mapping: TableMapping) -> list[dict[str, Any]]:
    try:
        rows = [dict(row) for row in connection.execute(mapping.sqlite_query).fetchall()]
    except sqlite3.Error as error:
        raise GristSyncError(f"SQLite query failed for {mapping.grist_table}: {error}") from error
    for row in rows:
        for column, transform in (mapping.transforms or {}).items():
            row[column] = transform(row.get(column))
    return rows


def sync_table(connection: sqlite3.Connection, client: GristClient, mapping: TableMapping,
               *, apply: bool = False) -> SyncResult:
    source = _source_rows(connection, mapping)
    remote = client.records(mapping.grist_table)
    indexed = {record.get("fields", {}).get(mapping.key_column): record for record in remote}
    creates: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    unchanged = 0
    for row in source:
        key = row[mapping.key_column]
        current = indexed.get(key)
        if current is None:
            creates.append(row)
        elif all(current.get("fields", {}).get(column) == value for column, value in row.items()):
            unchanged += 1
        else:
            updates.append({"id": current["id"], "fields": row})
    if apply:
        client.add(mapping.grist_table, creates)
        client.update(mapping.grist_table, updates)
    return SyncResult(mapping.grist_table, len(source), len(creates), len(updates), unchanged, not apply)


def _validate_schemas(connection: sqlite3.Connection, client: GristClient) -> None:
    """Validate every destination before any writes can begin."""
    errors: list[str] = []
    for mapping in TABLE_MAPPINGS:
        source = _source_rows(connection, mapping)
        required = set(source[0]) if source else {mapping.key_column}
        missing = sorted(required - client.columns(mapping.grist_table))
        if missing:
            errors.append(f"{mapping.grist_table}: missing {', '.join(missing)}")
    if errors:
        raise GristSyncError("Grist schema preflight failed; no writes attempted: " + "; ".join(errors))


def sync_database(database_path: str | Path, client: GristClient, *, apply: bool = False) -> tuple[SyncResult, ...]:
    path = Path(database_path)
    if not path.is_file():
        raise GristSyncError(f"SQLite database not found: {path}")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        _validate_schemas(connection, client)
        return tuple(sync_table(connection, client, mapping, apply=apply) for mapping in TABLE_MAPPINGS)
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror TRANCEatables SQLite data to Grist")
    parser.add_argument("--database", default=os.getenv("TRANCEATABLES_DB_PATH", "tranceatables.sqlite3"))
    parser.add_argument("--apply", action="store_true", help="write changes; default is dry-run")
    args = parser.parse_args()
    client = GristClient(os.environ["GRIST_BASE_URL"], os.environ["GRIST_DOC_ID"], os.environ["GRIST_API_KEY"])
    for result in sync_database(args.database, client, apply=args.apply):
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"{mode} {result.table}: source={result.source_rows} create={result.created} update={result.updated} unchanged={result.unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
