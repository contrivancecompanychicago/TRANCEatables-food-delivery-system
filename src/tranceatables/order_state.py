"""Pure order lifecycle rules for Stage 1."""

from dataclasses import dataclass, replace
from enum import Enum

from .models import DeliveryRequest


class OrderStatus(str, Enum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    PREPARED = "prepared"
    PACKAGED = "packaged"
    READY = "ready"
    ASSIGNED = "assigned"
    CANCELLED = "cancelled"


ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.DRAFT: frozenset({OrderStatus.ACCEPTED, OrderStatus.CANCELLED}),
    OrderStatus.ACCEPTED: frozenset({OrderStatus.PREPARED, OrderStatus.CANCELLED}),
    OrderStatus.PREPARED: frozenset({OrderStatus.PACKAGED, OrderStatus.CANCELLED}),
    OrderStatus.PACKAGED: frozenset({OrderStatus.READY, OrderStatus.CANCELLED}),
    OrderStatus.READY: frozenset({OrderStatus.ASSIGNED, OrderStatus.CANCELLED}),
    OrderStatus.ASSIGNED: frozenset({OrderStatus.CANCELLED}),
    OrderStatus.CANCELLED: frozenset(),
}


class InvalidTransition(ValueError):
    """Raised when an order lifecycle transition is not permitted."""


@dataclass(frozen=True)
class Order:
    request: DeliveryRequest
    status: OrderStatus
    version: int
    created_at: str
    updated_at: str

    @property
    def order_id(self) -> str:
        return self.request.order_id


def can_transition(current: OrderStatus, target: OrderStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def transition_order(order: Order, target: OrderStatus, *, occurred_at: str) -> Order:
    if not can_transition(order.status, target):
        raise InvalidTransition(f"cannot transition order from {order.status.value} to {target.value}")
    return replace(order, status=target, version=order.version + 1, updated_at=occurred_at)
