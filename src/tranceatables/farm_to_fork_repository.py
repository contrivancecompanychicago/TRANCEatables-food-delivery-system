"""SQLite persistence for simulated farm-to-fork traceability."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from .farm_to_fork import (
    FarmToForkRecord,
    FarmToForkStatus,
    transition_farm_to_fork,
)
from .repository import ConcurrentUpdateError, DuplicateOrderError, OrderNotFoundError


@dataclass(frozen=True)
class FarmToForkEvent:
    event_id: int
    trace_id: str
    from_status: FarmToForkStatus | None
    to_status: FarmToForkStatus
    actor: str
    location_code: str | None
    temperature_c: float | None
    note: str | None
    occurred_at: str
    version: int


class SQLiteFarmToForkRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS farm_to_fork_records (
                    trace_id TEXT PRIMARY KEY,
                    farm_code TEXT NOT NULL,
                    product_code TEXT NOT NULL,
                    order_id TEXT,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS farm_to_fork_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL REFERENCES farm_to_fork_records(trace_id),
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    location_code TEXT,
                    temperature_c REAL,
                    note TEXT,
                    occurred_at TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    UNIQUE(trace_id, version)
                );
                """
            )

    def create(self, record: FarmToForkRecord, *, actor: str) -> FarmToForkRecord:
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO farm_to_fork_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record.trace_id,
                        record.farm_code,
                        record.product_code,
                        record.order_id,
                        record.status.value,
                        record.version,
                        record.created_at,
                        record.updated_at,
                    ),
                )
                connection.execute(
                    """INSERT INTO farm_to_fork_events
                    (trace_id, from_status, to_status, actor, location_code,
                     temperature_c, note, occurred_at, version)
                    VALUES (?, NULL, ?, ?, ?, NULL, ?, ?, ?)""",
                    (
                        record.trace_id,
                        record.status.value,
                        actor,
                        record.farm_code,
                        "trace_created",
                        record.created_at,
                        record.version,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateOrderError(f"trace already exists: {record.trace_id}") from error
        return record

    def get(self, trace_id: str) -> FarmToForkRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM farm_to_fork_records WHERE trace_id = ?", (trace_id,)
            ).fetchone()
        if row is None:
            raise OrderNotFoundError(f"farm-to-fork trace not found: {trace_id}")
        return self._row_to_record(row)

    def transition(
        self,
        trace_id: str,
        target: FarmToForkStatus,
        *,
        actor: str,
        location_code: str | None,
        temperature_c: float | None,
        note: str | None,
        occurred_at: str,
        expected_version: int | None,
    ) -> FarmToForkRecord:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM farm_to_fork_records WHERE trace_id = ?", (trace_id,)
            ).fetchone()
            if row is None:
                raise OrderNotFoundError(f"farm-to-fork trace not found: {trace_id}")
            current = self._row_to_record(row)
            if expected_version is not None and current.version != expected_version:
                raise ConcurrentUpdateError(
                    f"expected version {expected_version}, found {current.version}"
                )
            updated = transition_farm_to_fork(current, target, occurred_at=occurred_at)
            result = connection.execute(
                """UPDATE farm_to_fork_records SET status = ?, version = ?, updated_at = ?
                WHERE trace_id = ? AND version = ?""",
                (updated.status.value, updated.version, updated.updated_at, trace_id, current.version),
            )
            if result.rowcount != 1:
                raise ConcurrentUpdateError(f"trace changed during update: {trace_id}")
            connection.execute(
                """INSERT INTO farm_to_fork_events
                (trace_id, from_status, to_status, actor, location_code,
                 temperature_c, note, occurred_at, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trace_id,
                    current.status.value,
                    updated.status.value,
                    actor,
                    location_code,
                    temperature_c,
                    note,
                    occurred_at,
                    updated.version,
                ),
            )
        return updated

    def events(self, trace_id: str) -> tuple[FarmToForkEvent, ...]:
        self.get(trace_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM farm_to_fork_events WHERE trace_id = ? ORDER BY version",
                (trace_id,),
            ).fetchall()
        return tuple(
            FarmToForkEvent(
                event_id=row["event_id"],
                trace_id=row["trace_id"],
                from_status=FarmToForkStatus(row["from_status"]) if row["from_status"] else None,
                to_status=FarmToForkStatus(row["to_status"]),
                actor=row["actor"],
                location_code=row["location_code"],
                temperature_c=row["temperature_c"],
                note=row["note"],
                occurred_at=row["occurred_at"],
                version=row["version"],
            )
            for row in rows
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> FarmToForkRecord:
        return FarmToForkRecord(
            trace_id=row["trace_id"],
            farm_code=row["farm_code"],
            product_code=row["product_code"],
            order_id=row["order_id"],
            status=FarmToForkStatus(row["status"]),
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
