"""TRANCEatables simulation domain core."""

from .feasibility import FeasibilityDecision, evaluate_delivery
from .models import DeliveryRequest, FoodHandling, RobotState
from .order_state import InvalidTransition, Order, OrderStatus, can_transition
from .repository import (
    ConcurrentUpdateError,
    DuplicateOrderError,
    OrderEvent,
    OrderNotFoundError,
    SQLiteOrderRepository,
)
from .service import OrderService
from .robot_mission import (
    ALLOWED_MISSION_TRANSITIONS,
    InvalidMissionTransition,
    MissionStatus,
    RobotMission,
    RobotStatus,
    SimulatedRobot,
    can_transition_mission,
)
from .robot_mission_repository import (
    DuplicateMissionError,
    DuplicateRobotError,
    MissionEligibilityError,
    MissionEvent,
    MissionNotFoundError,
    RobotNotFoundError,
    SafetyEvent,
    SQLiteRobotMissionRepository,
    TelemetryRecord,
)
from .robot_mission_service import RobotMissionService
from .sheety_reference import (
    RestaurantReference,
    SheetyReferenceClient,
    SheetyReferenceError,
    SheetyReferenceSnapshot,
)

__all__ = [
    "ALLOWED_MISSION_TRANSITIONS",
    "ConcurrentUpdateError",
    "DeliveryRequest",
    "DuplicateMissionError",
    "DuplicateOrderError",
    "DuplicateRobotError",
    "FeasibilityDecision",
    "FoodHandling",
    "InvalidMissionTransition",
    "InvalidTransition",
    "MissionEligibilityError",
    "MissionEvent",
    "MissionNotFoundError",
    "MissionStatus",
    "Order",
    "OrderEvent",
    "OrderNotFoundError",
    "OrderService",
    "OrderStatus",
    "RobotMission",
    "RobotMissionService",
    "RobotNotFoundError",
    "RobotState",
    "RobotStatus",
    "RestaurantReference",
    "SafetyEvent",
    "SheetyReferenceClient",
    "SheetyReferenceError",
    "SheetyReferenceSnapshot",
    "SimulatedRobot",
    "SQLiteRobotMissionRepository",
    "TelemetryRecord",
    "SQLiteOrderRepository",
    "can_transition",
    "can_transition_mission",
    "evaluate_delivery",
]
