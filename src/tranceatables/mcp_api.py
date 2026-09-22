"""Testable, transport-neutral operations exposed by the Stage 1.5 MCP server."""

from __future__ import annotations

from pathlib import Path
import re
from datetime import datetime, timezone
from typing import Any

from .feasibility import evaluate_delivery
from .farm_to_fork import (
    ALLOWED_FARM_TO_FORK_TRANSITIONS,
    FarmToForkRecord,
    FarmToForkStatus,
)
from .farm_to_fork_repository import FarmToForkEvent, SQLiteFarmToForkRepository
from .models import DeliveryRequest, FoodHandling, RobotState
from .order_state import ALLOWED_TRANSITIONS, Order, OrderStatus
from .repository import OrderEvent, SQLiteOrderRepository
from .service import OrderService


SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _safe_identifier(value: str, field: str) -> str:
    if not SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(
            f"{field} must be 1-64 characters using only letters, numbers, '.', '_' or '-'"
        )
    return value


def _order_dict(order: Order) -> dict[str, Any]:
    request = order.request
    return {
        "order_id": order.order_id,
        "status": order.status.value,
        "version": order.version,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "request": {
            "distance_km": request.distance_km,
            "payload_kg": request.payload_kg,
            "handling": request.handling.value,
            "packaging_verified": request.packaging_verified,
            "customer_handoff_required": request.customer_handoff_required,
        },
        "allowed_next_statuses": sorted(
            status.value for status in ALLOWED_TRANSITIONS[order.status]
        ),
        "simulation_only": True,
    }


def _event_dict(event: OrderEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "order_id": event.order_id,
        "from_status": event.from_status.value if event.from_status else None,
        "to_status": event.to_status.value,
        "actor": event.actor,
        "reason": event.reason,
        "occurred_at": event.occurred_at,
        "version": event.version,
    }


def _trace_dict(record: FarmToForkRecord) -> dict[str, Any]:
    return {
        "trace_id": record.trace_id,
        "farm_code": record.farm_code,
        "product_code": record.product_code,
        "order_id": record.order_id,
        "status": record.status.value,
        "version": record.version,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "allowed_next_statuses": sorted(
            status.value for status in ALLOWED_FARM_TO_FORK_TRANSITIONS[record.status]
        ),
        "simulation_only": True,
    }


def _trace_event_dict(event: FarmToForkEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "trace_id": event.trace_id,
        "from_status": event.from_status.value if event.from_status else None,
        "to_status": event.to_status.value,
        "actor": event.actor,
        "location_code": event.location_code,
        "temperature_c": event.temperature_c,
        "note": event.note,
        "occurred_at": event.occurred_at,
        "version": event.version,
    }


class SimulationMCPAPI:
    """Simulation facade over the Stage 0 evaluator and Stage 1 order service."""

    def __init__(self, database_path: str | Path) -> None:
        self.service = OrderService(SQLiteOrderRepository(database_path))
        self.farm_to_fork = SQLiteFarmToForkRepository(database_path)

    @staticmethod
    def about() -> dict[str, Any]:
        return {
            "name": "TRANCEatables Stage 1.5 MCP",
            "mode": "simulation-only",
            "can_do": [
                "evaluate a hypothetical delivery",
                "create a simulated order",
                "read simulated order state and history",
                "advance or cancel a simulated order using Stage 1 rules",
                "trace a simulated food lot from farm planning through delivery",
            ],
            "cannot_do": [
                "control or dispatch a physical robot",
                "contact a customer, restaurant, or delivery provider",
                "accept payment or place a real order",
                "provide medical advice or certify food safety",
            ],
            "data_rule": "Use opaque test identifiers only; do not enter names, addresses, health data, payment data, credentials, or secrets.",
        }

    @staticmethod
    def evaluate(
        *,
        order_id: str,
        distance_km: float,
        payload_kg: float,
        handling: str,
        packaging_verified: bool,
        robot_id: str,
        battery_percent: float,
        available_range_km: float,
        payload_capacity_kg: float,
        operational: bool = True,
        reserve_fraction: float = 0.20,
    ) -> dict[str, Any]:
        request = DeliveryRequest(
            order_id=_safe_identifier(order_id, "order_id"),
            distance_km=distance_km,
            payload_kg=payload_kg,
            handling=FoodHandling(handling),
            packaging_verified=packaging_verified,
        )
        robot = RobotState(
            robot_id=_safe_identifier(robot_id, "robot_id"),
            battery_percent=battery_percent,
            available_range_km=available_range_km,
            payload_capacity_kg=payload_capacity_kg,
            operational=operational,
        )
        decision = evaluate_delivery(request, robot, reserve_fraction=reserve_fraction)
        return {
            "feasible": decision.feasible,
            "reasons": list(decision.reasons),
            "order_id": request.order_id,
            "robot_id": robot.robot_id,
            "simulation_only": True,
            "dispatched": False,
        }

    def create_order(
        self,
        *,
        order_id: str,
        distance_km: float,
        payload_kg: float,
        handling: str = "ambient",
        packaging_verified: bool = False,
        customer_handoff_required: bool = True,
        actor: str = "mcp-simulator",
    ) -> dict[str, Any]:
        request = DeliveryRequest(
            order_id=_safe_identifier(order_id, "order_id"),
            distance_km=distance_km,
            payload_kg=payload_kg,
            handling=FoodHandling(handling),
            packaging_verified=packaging_verified,
            customer_handoff_required=customer_handoff_required,
        )
        order = self.service.create_order(
            request, actor=_safe_identifier(actor, "actor")
        )
        return _order_dict(order)

    def get_order(self, order_id: str) -> dict[str, Any]:
        return _order_dict(self.service.get_order(_safe_identifier(order_id, "order_id")))

    def get_history(self, order_id: str) -> dict[str, Any]:
        safe_order_id = _safe_identifier(order_id, "order_id")
        return {
            "order_id": safe_order_id,
            "events": [_event_dict(event) for event in self.service.get_history(safe_order_id)],
            "simulation_only": True,
        }

    def transition_order(
        self,
        *,
        order_id: str,
        target_status: str,
        actor: str = "mcp-simulator",
        reason: str | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        if reason is not None and len(reason) > 200:
            raise ValueError("reason cannot exceed 200 characters")
        order = self.service.transition(
            _safe_identifier(order_id, "order_id"),
            OrderStatus(target_status),
            actor=_safe_identifier(actor, "actor"),
            reason=reason,
            expected_version=expected_version,
        )
        return _order_dict(order)

    def create_farm_to_fork_trace(
        self,
        *,
        trace_id: str,
        farm_code: str,
        product_code: str,
        order_id: str | None = None,
        actor: str = "mcp-simulator",
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        record = FarmToForkRecord(
            trace_id=_safe_identifier(trace_id, "trace_id"),
            farm_code=_safe_identifier(farm_code, "farm_code"),
            product_code=_safe_identifier(product_code, "product_code"),
            order_id=_safe_identifier(order_id, "order_id") if order_id else None,
            status=FarmToForkStatus.PLANNED,
            version=0,
            created_at=timestamp,
            updated_at=timestamp,
        )
        return _trace_dict(
            self.farm_to_fork.create(record, actor=_safe_identifier(actor, "actor"))
        )

    def get_farm_to_fork_trace(self, trace_id: str) -> dict[str, Any]:
        return _trace_dict(
            self.farm_to_fork.get(_safe_identifier(trace_id, "trace_id"))
        )

    def get_farm_to_fork_history(self, trace_id: str) -> dict[str, Any]:
        safe_trace_id = _safe_identifier(trace_id, "trace_id")
        return {
            "trace_id": safe_trace_id,
            "events": [
                _trace_event_dict(event)
                for event in self.farm_to_fork.events(safe_trace_id)
            ],
            "simulation_only": True,
        }

    def transition_farm_to_fork_trace(
        self,
        *,
        trace_id: str,
        target_status: str,
        actor: str = "mcp-simulator",
        location_code: str | None = None,
        temperature_c: float | None = None,
        note: str | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        if note is not None and len(note) > 200:
            raise ValueError("note cannot exceed 200 characters")
        if temperature_c is not None and not -50 <= temperature_c <= 150:
            raise ValueError("temperature_c must be between -50 and 150")
        record = self.farm_to_fork.transition(
            _safe_identifier(trace_id, "trace_id"),
            FarmToForkStatus(target_status),
            actor=_safe_identifier(actor, "actor"),
            location_code=(
                _safe_identifier(location_code, "location_code") if location_code else None
            ),
            temperature_c=temperature_c,
            note=note,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            expected_version=expected_version,
        )
        return _trace_dict(record)
