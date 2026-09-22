"""TRANCEatables Stage 1 domain core."""

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

__all__ = [
    "ConcurrentUpdateError",
    "DeliveryRequest",
    "DuplicateOrderError",
    "FeasibilityDecision",
    "FoodHandling",
    "InvalidTransition",
    "Order",
    "OrderEvent",
    "OrderNotFoundError",
    "OrderService",
    "OrderStatus",
    "RobotState",
    "SQLiteOrderRepository",
    "can_transition",
    "evaluate_delivery",
]
