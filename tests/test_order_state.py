from datetime import datetime, timedelta, timezone

import pytest

from tranceatables import (
    ConcurrentUpdateError,
    DeliveryRequest,
    DuplicateOrderError,
    InvalidTransition,
    OrderService,
    OrderStatus,
    SQLiteOrderRepository,
)


class TestClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def make_service(tmp_path):
    return OrderService(SQLiteOrderRepository(tmp_path / "orders.sqlite3"), clock=TestClock())


def test_full_stage_1_lifecycle_and_audit_history(tmp_path) -> None:
    service = make_service(tmp_path)
    created = service.create_order(DeliveryRequest("TRN-001", 2.0, 3.0), actor="operator")
    assert created.status is OrderStatus.DRAFT
    assert created.version == 0

    order = created
    for status in (
        OrderStatus.ACCEPTED,
        OrderStatus.PREPARED,
        OrderStatus.PACKAGED,
        OrderStatus.READY,
        OrderStatus.ASSIGNED,
    ):
        order = service.transition(
            order.order_id,
            status,
            actor="operator",
            expected_version=order.version,
        )

    assert order.status is OrderStatus.ASSIGNED
    assert order.version == 5
    history = service.get_history(order.order_id)
    assert [event.to_status for event in history] == [
        OrderStatus.DRAFT,
        OrderStatus.ACCEPTED,
        OrderStatus.PREPARED,
        OrderStatus.PACKAGED,
        OrderStatus.READY,
        OrderStatus.ASSIGNED,
    ]


def test_invalid_transition_does_not_mutate_persisted_order(tmp_path) -> None:
    service = make_service(tmp_path)
    service.create_order(DeliveryRequest("TRN-002", 1.0, 1.0))
    with pytest.raises(InvalidTransition):
        service.transition("TRN-002", OrderStatus.READY, actor="operator")
    assert service.get_order("TRN-002").status is OrderStatus.DRAFT
    assert len(service.get_history("TRN-002")) == 1


def test_order_survives_repository_reopen(tmp_path) -> None:
    path = tmp_path / "orders.sqlite3"
    first = OrderService(SQLiteOrderRepository(path), clock=TestClock())
    first.create_order(DeliveryRequest("TRN-003", 1.5, 2.5))
    second = OrderService(SQLiteOrderRepository(path), clock=TestClock())
    assert second.get_order("TRN-003").request.payload_kg == 2.5


def test_duplicate_order_and_stale_version_are_rejected(tmp_path) -> None:
    service = make_service(tmp_path)
    service.create_order(DeliveryRequest("TRN-004", 1.0, 1.0))
    with pytest.raises(DuplicateOrderError):
        service.create_order(DeliveryRequest("TRN-004", 1.0, 1.0))
    service.transition("TRN-004", OrderStatus.ACCEPTED, actor="operator", expected_version=0)
    with pytest.raises(ConcurrentUpdateError):
        service.transition("TRN-004", OrderStatus.PREPARED, actor="operator", expected_version=0)
