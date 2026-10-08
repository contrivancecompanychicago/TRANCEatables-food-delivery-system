"""Pure Stage 2 simulation-only robot and mission domain rules."""

from dataclasses import dataclass, replace
from enum import Enum


class RobotStatus(str, Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    NAVIGATING = "navigating"
    LOADING = "loading"
    AWAITING_HANDOFF = "awaiting_handoff"
    EMERGENCY_STOPPED = "emergency_stopped"
    OUT_OF_SERVICE = "out_of_service"


class MissionStatus(str, Enum):
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    DISPATCHED = "dispatched"
    NAVIGATING_TO_PICKUP = "navigating_to_pickup"
    LOADING = "loading"
    NAVIGATING_TO_DROPOFF = "navigating_to_dropoff"
    AWAITING_HANDOFF = "awaiting_handoff"
    COMPLETED = "completed"
    PAUSED = "paused"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    EMERGENCY_STOPPED = "emergency_stopped"


ALLOWED_MISSION_TRANSITIONS: dict[MissionStatus, frozenset[MissionStatus]] = {
    MissionStatus.PLANNED: frozenset(
        {MissionStatus.AWAITING_APPROVAL, MissionStatus.CANCELLED}
    ),
    MissionStatus.AWAITING_APPROVAL: frozenset(
        {MissionStatus.APPROVED, MissionStatus.CANCELLED}
    ),
    MissionStatus.APPROVED: frozenset(
        {MissionStatus.DISPATCHED, MissionStatus.CANCELLED}
    ),
    MissionStatus.DISPATCHED: frozenset(
        {
            MissionStatus.NAVIGATING_TO_PICKUP,
            MissionStatus.CANCELLED,
            MissionStatus.EMERGENCY_STOPPED,
        }
    ),
    MissionStatus.NAVIGATING_TO_PICKUP: frozenset(
        {
            MissionStatus.LOADING,
            MissionStatus.PAUSED,
            MissionStatus.BLOCKED,
            MissionStatus.CANCELLED,
            MissionStatus.EMERGENCY_STOPPED,
        }
    ),
    MissionStatus.LOADING: frozenset(
        {
            MissionStatus.NAVIGATING_TO_DROPOFF,
            MissionStatus.CANCELLED,
            MissionStatus.EMERGENCY_STOPPED,
        }
    ),
    MissionStatus.NAVIGATING_TO_DROPOFF: frozenset(
        {
            MissionStatus.AWAITING_HANDOFF,
            MissionStatus.PAUSED,
            MissionStatus.BLOCKED,
            MissionStatus.CANCELLED,
            MissionStatus.EMERGENCY_STOPPED,
        }
    ),
    MissionStatus.AWAITING_HANDOFF: frozenset(
        {
            MissionStatus.COMPLETED,
            MissionStatus.CANCELLED,
            MissionStatus.EMERGENCY_STOPPED,
        }
    ),
    MissionStatus.COMPLETED: frozenset(),
    MissionStatus.PAUSED: frozenset(),
    MissionStatus.BLOCKED: frozenset(),
    MissionStatus.CANCELLED: frozenset(),
    MissionStatus.EMERGENCY_STOPPED: frozenset(),
}


class InvalidMissionTransition(ValueError):
    """Raised when a simulated mission transition is not permitted."""


@dataclass(frozen=True)
class SimulatedRobot:
    robot_id: str
    name: str
    status: RobotStatus
    battery_percent: float
    current_zone: str
    payload_capacity_kg: float
    operational: bool
    version: int
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if not 0 <= self.battery_percent <= 100:
            raise ValueError("battery_percent must be between 0 and 100")
        if self.payload_capacity_kg <= 0:
            raise ValueError("payload_capacity_kg must be greater than zero")


@dataclass(frozen=True)
class RobotMission:
    mission_id: str
    order_id: str
    robot_id: str
    status: MissionStatus
    pickup_zone: str
    dropoff_zone: str
    payload_kg: float
    version: int
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if self.payload_kg <= 0:
            raise ValueError("payload_kg must be greater than zero")


def can_transition_mission(current: MissionStatus, target: MissionStatus) -> bool:
    return target in ALLOWED_MISSION_TRANSITIONS[current]


def transition_mission(
    mission: RobotMission, target: MissionStatus, *, occurred_at: str
) -> RobotMission:
    if not can_transition_mission(mission.status, target):
        raise InvalidMissionTransition(
            f"cannot transition mission from {mission.status.value} to {target.value}"
        )
    return replace(
        mission,
        status=target,
        version=mission.version + 1,
        updated_at=occurred_at,
    )
