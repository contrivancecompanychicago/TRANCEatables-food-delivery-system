"""API-neutral orchestration for Stage 2 robot mission simulations."""

from datetime import datetime, timezone
from typing import Callable

from .robot_mission import MissionStatus, RobotMission, RobotStatus, SimulatedRobot
from .robot_mission_repository import (
    MissionEvent,
    SafetyEvent,
    SQLiteRobotMissionRepository,
    TelemetryRecord,
)


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RobotMissionService:
    def __init__(
        self, repository: SQLiteRobotMissionRepository, *, clock: Clock = _utc_now
    ) -> None:
        self.repository = repository
        self.clock = clock

    def _timestamp(self) -> str:
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc).isoformat()

    def register_robot(
        self,
        *,
        robot_id: str,
        name: str,
        battery_percent: float,
        current_zone: str,
        payload_capacity_kg: float,
        operational: bool = True,
    ) -> SimulatedRobot:
        timestamp = self._timestamp()
        robot = SimulatedRobot(
            robot_id=robot_id,
            name=name,
            status=RobotStatus.AVAILABLE,
            battery_percent=battery_percent,
            current_zone=current_zone,
            payload_capacity_kg=payload_capacity_kg,
            operational=operational,
            version=0,
            created_at=timestamp,
            updated_at=timestamp,
        )
        return self.repository.register_robot(robot)

    def create_mission(
        self,
        *,
        mission_id: str,
        order_id: str,
        robot_id: str,
        pickup_zone: str,
        dropoff_zone: str,
        payload_kg: float,
        actor: str = "system",
    ) -> RobotMission:
        timestamp = self._timestamp()
        mission = RobotMission(
            mission_id=mission_id,
            order_id=order_id,
            robot_id=robot_id,
            status=MissionStatus.PLANNED,
            pickup_zone=pickup_zone,
            dropoff_zone=dropoff_zone,
            payload_kg=payload_kg,
            version=0,
            created_at=timestamp,
            updated_at=timestamp,
        )
        return self.repository.create_mission(mission, actor=actor)

    def transition(
        self,
        mission_id: str,
        target: MissionStatus,
        *,
        actor: str,
        message: str | None = None,
        expected_version: int | None = None,
    ) -> RobotMission:
        if not actor.strip():
            raise ValueError("actor cannot be blank")
        if target is MissionStatus.DISPATCHED:
            return self.repository.dispatch(
                mission_id,
                actor=actor,
                occurred_at=self._timestamp(),
                expected_version=expected_version,
            )
        mission = self.repository.transition(
            mission_id,
            target,
            actor=actor,
            message=message,
            occurred_at=self._timestamp(),
            expected_version=expected_version,
        )
        robot_status = {
            MissionStatus.NAVIGATING_TO_PICKUP: RobotStatus.NAVIGATING,
            MissionStatus.LOADING: RobotStatus.LOADING,
            MissionStatus.NAVIGATING_TO_DROPOFF: RobotStatus.NAVIGATING,
            MissionStatus.AWAITING_HANDOFF: RobotStatus.AWAITING_HANDOFF,
            MissionStatus.COMPLETED: RobotStatus.AVAILABLE,
            MissionStatus.CANCELLED: RobotStatus.AVAILABLE,
            MissionStatus.EMERGENCY_STOPPED: RobotStatus.EMERGENCY_STOPPED,
        }.get(target)
        if robot_status is not None:
            robot = self.repository.get_robot(mission.robot_id)
            self.repository.set_robot_state(
                robot.robot_id,
                status=robot_status,
                battery_percent=robot.battery_percent,
                current_zone=robot.current_zone,
                occurred_at=mission.updated_at,
            )
        return mission

    def record_approval(
        self,
        mission_id: str,
        *,
        operator_reference: str,
        decision: str,
        note: str | None = None,
    ) -> None:
        if not operator_reference.strip():
            raise ValueError("operator_reference cannot be blank")
        self.repository.record_approval(
            mission_id,
            operator_reference=operator_reference,
            decision=decision,
            note=note,
            decided_at=self._timestamp(),
        )

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
    ) -> TelemetryRecord:
        record = self.repository.record_telemetry(
            robot_id=robot_id,
            mission_id=mission_id,
            battery_percent=battery_percent,
            current_zone=current_zone,
            position_x=position_x,
            position_y=position_y,
            speed_mps=speed_mps,
            observed_at=self._timestamp(),
        )
        robot = self.repository.get_robot(robot_id)
        self.repository.set_robot_state(
            robot_id,
            status=robot.status,
            battery_percent=battery_percent,
            current_zone=current_zone,
            occurred_at=record.observed_at,
        )
        return record

    def record_safety_event(
        self,
        *,
        robot_id: str,
        mission_id: str | None,
        severity: str,
        event_type: str,
        message: str,
    ) -> SafetyEvent:
        return self.repository.record_safety_event(
            robot_id=robot_id,
            mission_id=mission_id,
            severity=severity,
            event_type=event_type,
            message=message,
            occurred_at=self._timestamp(),
        )

    def get_robot(self, robot_id: str) -> SimulatedRobot:
        return self.repository.get_robot(robot_id)

    def get_mission(self, mission_id: str) -> RobotMission:
        return self.repository.get_mission(mission_id)

    def get_history(self, mission_id: str) -> tuple[MissionEvent, ...]:
        return self.repository.events(mission_id)

    def get_telemetry(self, mission_id: str) -> tuple[TelemetryRecord, ...]:
        return self.repository.telemetry(mission_id)
