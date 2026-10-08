"""SQLite snapshots and append-only audit data for Stage 2 simulations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from .order_state import OrderStatus
from .repository import ConcurrentUpdateError
from .robot_mission import (
    MissionStatus,
    RobotMission,
    RobotStatus,
    SimulatedRobot,
    transition_mission,
)


class DuplicateRobotError(ValueError):
    pass


class DuplicateMissionError(ValueError):
    pass


class RobotNotFoundError(LookupError):
    pass


class MissionNotFoundError(LookupError):
    pass


class MissionEligibilityError(ValueError):
    pass


@dataclass(frozen=True)
class MissionEvent:
    event_id: int
    mission_id: str
    from_status: MissionStatus | None
    to_status: MissionStatus
    actor: str
    message: str | None
    occurred_at: str
    version: int


@dataclass(frozen=True)
class TelemetryRecord:
    telemetry_id: int
    robot_id: str
    mission_id: str | None
    battery_percent: float
    current_zone: str
    position_x: float
    position_y: float
    speed_mps: float
    observed_at: str


@dataclass(frozen=True)
class SafetyEvent:
    safety_event_id: int
    robot_id: str
    mission_id: str | None
    severity: str
    event_type: str
    message: str
    resolved: bool
    occurred_at: str


class SQLiteRobotMissionRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS simulated_robots (
                    robot_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    battery_percent REAL NOT NULL CHECK(battery_percent BETWEEN 0 AND 100),
                    current_zone TEXT NOT NULL,
                    payload_capacity_kg REAL NOT NULL CHECK(payload_capacity_kg > 0),
                    operational INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS robot_missions (
                    mission_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    robot_id TEXT NOT NULL REFERENCES simulated_robots(robot_id),
                    status TEXT NOT NULL,
                    pickup_zone TEXT NOT NULL,
                    dropoff_zone TEXT NOT NULL,
                    payload_kg REAL NOT NULL CHECK(payload_kg > 0),
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mission_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT NOT NULL REFERENCES robot_missions(mission_id),
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    message TEXT,
                    occurred_at TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    UNIQUE(mission_id, version)
                );
                CREATE TABLE IF NOT EXISTS operator_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT NOT NULL REFERENCES robot_missions(mission_id),
                    operator_reference TEXT NOT NULL,
                    decision TEXT NOT NULL CHECK(decision IN ('approved', 'rejected')),
                    note TEXT,
                    decided_at TEXT NOT NULL,
                    UNIQUE(mission_id)
                );
                CREATE TABLE IF NOT EXISTS robot_telemetry (
                    telemetry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    robot_id TEXT NOT NULL REFERENCES simulated_robots(robot_id),
                    mission_id TEXT REFERENCES robot_missions(mission_id),
                    battery_percent REAL NOT NULL CHECK(battery_percent BETWEEN 0 AND 100),
                    current_zone TEXT NOT NULL,
                    position_x REAL NOT NULL,
                    position_y REAL NOT NULL,
                    speed_mps REAL NOT NULL CHECK(speed_mps >= 0),
                    observed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS robot_safety_events (
                    safety_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    robot_id TEXT NOT NULL REFERENCES simulated_robots(robot_id),
                    mission_id TEXT REFERENCES robot_missions(mission_id),
                    severity TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    resolved INTEGER NOT NULL DEFAULT 0,
                    occurred_at TEXT NOT NULL
                );
                """
            )

    def register_robot(self, robot: SimulatedRobot) -> SimulatedRobot:
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO simulated_robots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        robot.robot_id,
                        robot.name,
                        robot.status.value,
                        robot.battery_percent,
                        robot.current_zone,
                        robot.payload_capacity_kg,
                        int(robot.operational),
                        robot.version,
                        robot.created_at,
                        robot.updated_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateRobotError(f"robot already exists: {robot.robot_id}") from error
        return robot

    def get_robot(self, robot_id: str) -> SimulatedRobot:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM simulated_robots WHERE robot_id = ?", (robot_id,)
            ).fetchone()
        if row is None:
            raise RobotNotFoundError(robot_id)
        return self._row_to_robot(row)

    def create_mission(self, mission: RobotMission, *, actor: str) -> RobotMission:
        try:
            with self._connect() as connection:
                order = connection.execute(
                    "SELECT status, payload_kg FROM orders WHERE order_id = ?",
                    (mission.order_id,),
                ).fetchone()
                robot = connection.execute(
                    "SELECT * FROM simulated_robots WHERE robot_id = ?",
                    (mission.robot_id,),
                ).fetchone()
                if order is None:
                    raise MissionEligibilityError(f"order not found: {mission.order_id}")
                if order["status"] != OrderStatus.READY.value:
                    raise MissionEligibilityError("order must be ready")
                if robot is None:
                    raise RobotNotFoundError(mission.robot_id)
                if robot["status"] != RobotStatus.AVAILABLE.value:
                    raise MissionEligibilityError("robot must be available")
                if not bool(robot["operational"]):
                    raise MissionEligibilityError("robot must be operational")
                if robot["battery_percent"] < 50:
                    raise MissionEligibilityError("robot battery must be at least 50 percent")
                if mission.payload_kg > robot["payload_capacity_kg"]:
                    raise MissionEligibilityError("payload exceeds robot capacity")
                connection.execute(
                    """INSERT INTO robot_missions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        mission.mission_id,
                        mission.order_id,
                        mission.robot_id,
                        mission.status.value,
                        mission.pickup_zone,
                        mission.dropoff_zone,
                        mission.payload_kg,
                        mission.version,
                        mission.created_at,
                        mission.updated_at,
                    ),
                )
                connection.execute(
                    """INSERT INTO mission_events
                    (mission_id, from_status, to_status, actor, message, occurred_at, version)
                    VALUES (?, NULL, ?, ?, ?, ?, ?)""",
                    (
                        mission.mission_id,
                        mission.status.value,
                        actor,
                        "mission_created",
                        mission.created_at,
                        mission.version,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateMissionError(
                f"mission already exists: {mission.mission_id}"
            ) from error
        return mission

    def get_mission(self, mission_id: str) -> RobotMission:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM robot_missions WHERE mission_id = ?", (mission_id,)
            ).fetchone()
        if row is None:
            raise MissionNotFoundError(mission_id)
        return self._row_to_mission(row)

    def transition(
        self,
        mission_id: str,
        target: MissionStatus,
        *,
        actor: str,
        message: str | None,
        occurred_at: str,
        expected_version: int | None = None,
    ) -> RobotMission:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM robot_missions WHERE mission_id = ?", (mission_id,)
            ).fetchone()
            if row is None:
                raise MissionNotFoundError(mission_id)
            current = self._row_to_mission(row)
            if expected_version is not None and current.version != expected_version:
                raise ConcurrentUpdateError(
                    f"expected version {expected_version}, found {current.version}"
                )
            if target is MissionStatus.APPROVED:
                approval = connection.execute(
                    "SELECT decision FROM operator_approvals WHERE mission_id = ?",
                    (mission_id,),
                ).fetchone()
                if approval is None or approval["decision"] != "approved":
                    raise MissionEligibilityError("human approval is required")
            updated = transition_mission(current, target, occurred_at=occurred_at)
            result = connection.execute(
                """UPDATE robot_missions SET status = ?, version = ?, updated_at = ?
                WHERE mission_id = ? AND version = ?""",
                (
                    updated.status.value,
                    updated.version,
                    updated.updated_at,
                    mission_id,
                    current.version,
                ),
            )
            if result.rowcount != 1:
                raise ConcurrentUpdateError(f"mission changed during update: {mission_id}")
            connection.execute(
                """INSERT INTO mission_events
                (mission_id, from_status, to_status, actor, message, occurred_at, version)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    mission_id,
                    current.status.value,
                    updated.status.value,
                    actor,
                    message,
                    occurred_at,
                    updated.version,
                ),
            )
        return updated

    def record_approval(
        self,
        mission_id: str,
        *,
        operator_reference: str,
        decision: str,
        note: str | None,
        decided_at: str,
    ) -> None:
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        mission = self.get_mission(mission_id)
        if mission.status is not MissionStatus.AWAITING_APPROVAL:
            raise MissionEligibilityError("mission must be awaiting approval")
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO operator_approvals
                (mission_id, operator_reference, decision, note, decided_at)
                VALUES (?, ?, ?, ?, ?)""",
                (mission_id, operator_reference, decision, note, decided_at),
            )

    def dispatch(
        self,
        mission_id: str,
        *,
        actor: str,
        occurred_at: str,
        expected_version: int | None = None,
    ) -> RobotMission:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            mission_row = connection.execute(
                "SELECT * FROM robot_missions WHERE mission_id = ?", (mission_id,)
            ).fetchone()
            if mission_row is None:
                raise MissionNotFoundError(mission_id)
            current = self._row_to_mission(mission_row)
            if expected_version is not None and current.version != expected_version:
                raise ConcurrentUpdateError(
                    f"expected version {expected_version}, found {current.version}"
                )
            updated = transition_mission(
                current, MissionStatus.DISPATCHED, occurred_at=occurred_at
            )
            approval = connection.execute(
                "SELECT decision FROM operator_approvals WHERE mission_id = ?",
                (mission_id,),
            ).fetchone()
            if approval is None or approval["decision"] != "approved":
                raise MissionEligibilityError("human approval is required")
            robot = connection.execute(
                "SELECT * FROM simulated_robots WHERE robot_id = ?",
                (current.robot_id,),
            ).fetchone()
            order = connection.execute(
                "SELECT status, version FROM orders WHERE order_id = ?",
                (current.order_id,),
            ).fetchone()
            if robot is None:
                raise RobotNotFoundError(current.robot_id)
            if order is None or order["status"] != OrderStatus.READY.value:
                raise MissionEligibilityError("order must be ready")
            if robot["status"] != RobotStatus.AVAILABLE.value:
                raise MissionEligibilityError("robot must be available")
            if not bool(robot["operational"]) or robot["battery_percent"] < 50:
                raise MissionEligibilityError("robot is not eligible for dispatch")
            connection.execute(
                """UPDATE robot_missions SET status = ?, version = ?, updated_at = ?
                WHERE mission_id = ?""",
                (updated.status.value, updated.version, occurred_at, mission_id),
            )
            connection.execute(
                """UPDATE simulated_robots SET status = ?, version = version + 1,
                updated_at = ? WHERE robot_id = ?""",
                (RobotStatus.ASSIGNED.value, occurred_at, current.robot_id),
            )
            order_version = order["version"] + 1
            connection.execute(
                """UPDATE orders SET status = ?, version = ?, updated_at = ?
                WHERE order_id = ?""",
                (OrderStatus.ASSIGNED.value, order_version, occurred_at, current.order_id),
            )
            connection.execute(
                """INSERT INTO order_events
                (order_id, from_status, to_status, actor, reason, occurred_at, version)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    current.order_id,
                    OrderStatus.READY.value,
                    OrderStatus.ASSIGNED.value,
                    actor,
                    "simulated_robot_assigned",
                    occurred_at,
                    order_version,
                ),
            )
            connection.execute(
                """INSERT INTO mission_events
                (mission_id, from_status, to_status, actor, message, occurred_at, version)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    mission_id,
                    current.status.value,
                    updated.status.value,
                    actor,
                    "simulation dispatch; no physical command sent",
                    occurred_at,
                    updated.version,
                ),
            )
            connection.execute(
                """INSERT INTO robot_telemetry
                (robot_id, mission_id, battery_percent, current_zone,
                 position_x, position_y, speed_mps, observed_at)
                VALUES (?, ?, ?, ?, 0, 0, 0, ?)""",
                (
                    current.robot_id,
                    mission_id,
                    robot["battery_percent"],
                    robot["current_zone"],
                    occurred_at,
                ),
            )
        return updated

    def set_robot_state(
        self,
        robot_id: str,
        *,
        status: RobotStatus,
        battery_percent: float,
        current_zone: str,
        occurred_at: str,
    ) -> SimulatedRobot:
        if not 0 <= battery_percent <= 100:
            raise ValueError("battery_percent must be between 0 and 100")
        with self._connect() as connection:
            result = connection.execute(
                """UPDATE simulated_robots SET status = ?, battery_percent = ?,
                current_zone = ?, version = version + 1, updated_at = ?
                WHERE robot_id = ?""",
                (status.value, battery_percent, current_zone, occurred_at, robot_id),
            )
            if result.rowcount != 1:
                raise RobotNotFoundError(robot_id)
        return self.get_robot(robot_id)

    def record_telemetry(
        self,
        *,
        robot_id: str,
        mission_id: str | None,
        battery_percent: float,
        current_zone: str,
        position_x: float,
        position_y: float,
        speed_mps: float,
        observed_at: str,
    ) -> TelemetryRecord:
        if not 0 <= battery_percent <= 100:
            raise ValueError("battery_percent must be between 0 and 100")
        if speed_mps < 0:
            raise ValueError("speed_mps cannot be negative")
        self.get_robot(robot_id)
        if mission_id is not None:
            mission = self.get_mission(mission_id)
            if mission.robot_id != robot_id:
                raise ValueError("mission is assigned to a different robot")
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO robot_telemetry
                (robot_id, mission_id, battery_percent, current_zone,
                 position_x, position_y, speed_mps, observed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    robot_id,
                    mission_id,
                    battery_percent,
                    current_zone,
                    position_x,
                    position_y,
                    speed_mps,
                    observed_at,
                ),
            )
            telemetry_id = cursor.lastrowid
        return TelemetryRecord(
            telemetry_id,
            robot_id,
            mission_id,
            battery_percent,
            current_zone,
            position_x,
            position_y,
            speed_mps,
            observed_at,
        )

    def record_safety_event(
        self,
        *,
        robot_id: str,
        mission_id: str | None,
        severity: str,
        event_type: str,
        message: str,
        occurred_at: str,
    ) -> SafetyEvent:
        self.get_robot(robot_id)
        if mission_id is not None:
            mission = self.get_mission(mission_id)
            if mission.robot_id != robot_id:
                raise ValueError("mission is assigned to a different robot")
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO robot_safety_events
                (robot_id, mission_id, severity, event_type, message, resolved, occurred_at)
                VALUES (?, ?, ?, ?, ?, 0, ?)""",
                (robot_id, mission_id, severity, event_type, message, occurred_at),
            )
            event_id = cursor.lastrowid
        return SafetyEvent(
            event_id,
            robot_id,
            mission_id,
            severity,
            event_type,
            message,
            False,
            occurred_at,
        )

    def events(self, mission_id: str) -> tuple[MissionEvent, ...]:
        self.get_mission(mission_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM mission_events WHERE mission_id = ? ORDER BY version",
                (mission_id,),
            ).fetchall()
        return tuple(
            MissionEvent(
                row["event_id"],
                row["mission_id"],
                MissionStatus(row["from_status"]) if row["from_status"] else None,
                MissionStatus(row["to_status"]),
                row["actor"],
                row["message"],
                row["occurred_at"],
                row["version"],
            )
            for row in rows
        )

    def telemetry(self, mission_id: str) -> tuple[TelemetryRecord, ...]:
        self.get_mission(mission_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM robot_telemetry WHERE mission_id = ? ORDER BY telemetry_id",
                (mission_id,),
            ).fetchall()
        return tuple(TelemetryRecord(**dict(row)) for row in rows)

    @staticmethod
    def _row_to_robot(row: sqlite3.Row) -> SimulatedRobot:
        return SimulatedRobot(
            row["robot_id"],
            row["name"],
            RobotStatus(row["status"]),
            row["battery_percent"],
            row["current_zone"],
            row["payload_capacity_kg"],
            bool(row["operational"]),
            row["version"],
            row["created_at"],
            row["updated_at"],
        )

    @staticmethod
    def _row_to_mission(row: sqlite3.Row) -> RobotMission:
        return RobotMission(
            row["mission_id"],
            row["order_id"],
            row["robot_id"],
            MissionStatus(row["status"]),
            row["pickup_zone"],
            row["dropoff_zone"],
            row["payload_kg"],
            row["version"],
            row["created_at"],
            row["updated_at"],
        )
