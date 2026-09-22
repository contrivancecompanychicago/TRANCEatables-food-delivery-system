"""API-neutral orchestration for Stage 1 orders."""

from datetime import datetime, timezone
from typing import Callable

from .models import DeliveryRequest
from .order_state import Order, OrderStatus
from .repository import OrderEvent, SQLiteOrderRepository


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrderService:
    def __init__(self, repository: SQLiteOrderRepository, *, clock: Clock = _utc_now) -> None:
        self.repository = repository
        self.clock = clock

    def _timestamp(self) -> str:
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc).isoformat()

    def create_order(self, request: DeliveryRequest, *, actor: str = "system") -> Order:
        if not request.order_id.strip():
            raise ValueError("order_id cannot be blank")
        if request.distance_km < 0 or request.payload_kg < 0:
            raise ValueError("distance and payload cannot be negative")
        timestamp = self._timestamp()
        order = Order(request, OrderStatus.DRAFT, 0, timestamp, timestamp)
        return self.repository.create(order, actor=actor)

    def transition(
        self,
        order_id: str,
        target: OrderStatus,
        *,
        actor: str,
        reason: str | None = None,
        expected_version: int | None = None,
    ) -> Order:
        if not actor.strip():
            raise ValueError("actor cannot be blank")
        return self.repository.transition(
            order_id,
            target,
            actor=actor,
            reason=reason,
            occurred_at=self._timestamp(),
            expected_version=expected_version,
        )

    def get_order(self, order_id: str) -> Order:
        return self.repository.get(order_id)

    def get_history(self, order_id: str) -> tuple[OrderEvent, ...]:
        return self.repository.events(order_id)
