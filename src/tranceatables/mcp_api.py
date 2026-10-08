"""Testable, transport-neutral operations exposed by the Stage 1.5 MCP server."""

from __future__ import annotations

from pathlib import Path
import re
from datetime import datetime, timezone
from typing import Any

from .feasibility import evaluate_delivery
from .culapse_adapter import (
    SOURCE as CULAPSE_SOURCE,
    evaluate_harvest_checkpoint,
    evaluate_planning_checkpoint,
)
from .farm_to_fork import (
    ALLOWED_FARM_TO_FORK_TRANSITIONS,
    FarmToForkRecord,
    FarmToForkStatus,
)
from .farm_to_fork_repository import FarmToForkEvent, SQLiteFarmToForkRepository
from .models import DeliveryRequest, FoodHandling, RobotState
from .january_ai import JanuaryAIRestaurantClient, JanuaryAISettings
from .order_state import ALLOWED_TRANSITIONS, Order, OrderStatus
from .repository import OrderEvent, SQLiteOrderRepository
from .service import OrderService
from .robot_mission import (
    ALLOWED_MISSION_TRANSITIONS,
    MissionStatus,
    RobotMission,
    SimulatedRobot,
)
from .robot_mission_repository import (
    MissionEvent,
    SafetyEvent,
    SQLiteRobotMissionRepository,
    TelemetryRecord,
)
from .robot_mission_service import RobotMissionService


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


def _robot_dict(robot: SimulatedRobot) -> dict[str, Any]:
    return {
        "robot_id": robot.robot_id,
        "name": robot.name,
        "status": robot.status.value,
        "battery_percent": robot.battery_percent,
        "current_zone": robot.current_zone,
        "payload_capacity_kg": robot.payload_capacity_kg,
        "operational": robot.operational,
        "version": robot.version,
        "created_at": robot.created_at,
        "updated_at": robot.updated_at,
        "simulation_only": True,
    }


def _mission_dict(mission: RobotMission) -> dict[str, Any]:
    return {
        "mission_id": mission.mission_id,
        "order_id": mission.order_id,
        "robot_id": mission.robot_id,
        "status": mission.status.value,
        "pickup_zone": mission.pickup_zone,
        "dropoff_zone": mission.dropoff_zone,
        "payload_kg": mission.payload_kg,
        "version": mission.version,
        "created_at": mission.created_at,
        "updated_at": mission.updated_at,
        "allowed_next_statuses": sorted(
            status.value for status in ALLOWED_MISSION_TRANSITIONS[mission.status]
        ),
        "simulation_only": True,
        "physical_command_sent": False,
    }


def _mission_event_dict(event: MissionEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "mission_id": event.mission_id,
        "from_status": event.from_status.value if event.from_status else None,
        "to_status": event.to_status.value,
        "actor": event.actor,
        "message": event.message,
        "occurred_at": event.occurred_at,
        "version": event.version,
    }


def _telemetry_dict(record: TelemetryRecord) -> dict[str, Any]:
    return {
        "telemetry_id": record.telemetry_id,
        "robot_id": record.robot_id,
        "mission_id": record.mission_id,
        "battery_percent": record.battery_percent,
        "current_zone": record.current_zone,
        "position_x": record.position_x,
        "position_y": record.position_y,
        "speed_mps": record.speed_mps,
        "observed_at": record.observed_at,
        "simulation_only": True,
    }


def _safety_event_dict(event: SafetyEvent) -> dict[str, Any]:
    return {
        "safety_event_id": event.safety_event_id,
        "robot_id": event.robot_id,
        "mission_id": event.mission_id,
        "severity": event.severity,
        "event_type": event.event_type,
        "message": event.message,
        "resolved": event.resolved,
        "occurred_at": event.occurred_at,
        "simulation_only": True,
    }


class SimulationMCPAPI:
    """Simulation facade over the Stage 0 evaluator and Stage 1 order service."""

    def __init__(self, database_path: str | Path) -> None:
        self.service = OrderService(SQLiteOrderRepository(database_path))
        self.farm_to_fork = SQLiteFarmToForkRepository(database_path)
        self.robot_missions = RobotMissionService(
            SQLiteRobotMissionRepository(database_path)
        )
        self.january_ai = JanuaryAIRestaurantClient(JanuaryAISettings.from_environment())

    @staticmethod
    def about() -> dict[str, Any]:
        return {
            "name": "TRANCEatables Stage 2 MCP",
            "mode": "simulation-only",
            "can_do": [
                "evaluate a hypothetical delivery",
                "create a simulated order",
                "read simulated order state and history",
                "advance or cancel a simulated order using Stage 1 rules",
                "trace a simulated food lot from farm planning through delivery",
                "manage approved simulation-only robot missions and telemetry",
            ],
            "cannot_do": [
                "control or dispatch a physical robot",
                "navigate a physical robot",
                "contact a customer, restaurant, or delivery provider",
                "accept payment or place a real order",
                "provide medical advice or certify food safety",
            ],
            "data_rule": "Use opaque test identifiers only; do not enter names, addresses, health data, payment data, credentials, or secrets.",
        }

    @staticmethod
    def culapse_stage_fit() -> dict[str, Any]:
        return CULAPSE_SOURCE

    def january_ai_status(self) -> dict[str, Any]:
        return self.january_ai.status()

    def fetch_january_ai_restaurants(self) -> dict[str, Any]:
        return self.january_ai.list_restaurants()

    @staticmethod
    def evaluate_culapse_planning(
        *,
        production_reliability: float,
        maintenance_feasibility: float,
        capital_sufficiency: float,
    ) -> dict[str, Any]:
        return evaluate_planning_checkpoint(
            production_reliability,
            maintenance_feasibility,
            capital_sufficiency,
        )

    @staticmethod
    def evaluate_culapse_harvest(
        *, potential_yield_units: float, collected_yield_units: float
    ) -> dict[str, Any]:
        return evaluate_harvest_checkpoint(
            potential_yield_units, collected_yield_units
        )

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


    def register_simulated_robot(
        self,
        *,
        robot_id: str,
        name: str,
        battery_percent: float,
        current_zone: str,
        payload_capacity_kg: float,
        operational: bool = True,
    ) -> dict[str, Any]:
        robot = self.robot_missions.register_robot(
            robot_id=_safe_identifier(robot_id, "robot_id"),
            name=_safe_identifier(name, "name"),
            battery_percent=battery_percent,
            current_zone=_safe_identifier(current_zone, "current_zone"),
            payload_capacity_kg=payload_capacity_kg,
            operational=operational,
        )
        return _robot_dict(robot)

    def get_simulated_robot(self, robot_id: str) -> dict[str, Any]:
        return _robot_dict(
            self.robot_missions.get_robot(_safe_identifier(robot_id, "robot_id"))
        )

    def create_robot_mission(
        self,
        *,
        mission_id: str,
        order_id: str,
        robot_id: str,
        pickup_zone: str,
        dropoff_zone: str,
        payload_kg: float,
        actor: str = "mcp-simulator",
    ) -> dict[str, Any]:
        mission = self.robot_missions.create_mission(
            mission_id=_safe_identifier(mission_id, "mission_id"),
            order_id=_safe_identifier(order_id, "order_id"),
            robot_id=_safe_identifier(robot_id, "robot_id"),
            pickup_zone=_safe_identifier(pickup_zone, "pickup_zone"),
            dropoff_zone=_safe_identifier(dropoff_zone, "dropoff_zone"),
            payload_kg=payload_kg,
            actor=_safe_identifier(actor, "actor"),
        )
        return _mission_dict(mission)

    def get_robot_mission(self, mission_id: str) -> dict[str, Any]:
        return _mission_dict(
            self.robot_missions.get_mission(
                _safe_identifier(mission_id, "mission_id")
            )
        )

    def get_robot_mission_history(self, mission_id: str) -> dict[str, Any]:
        safe_id = _safe_identifier(mission_id, "mission_id")
        return {
            "mission_id": safe_id,
            "events": [
                _mission_event_dict(event)
                for event in self.robot_missions.get_history(safe_id)
            ],
            "simulation_only": True,
        }

    def get_robot_mission_telemetry(self, mission_id: str) -> dict[str, Any]:
        safe_id = _safe_identifier(mission_id, "mission_id")
        return {
            "mission_id": safe_id,
            "telemetry": [
                _telemetry_dict(record)
                for record in self.robot_missions.get_telemetry(safe_id)
            ],
            "simulation_only": True,
        }

    def record_robot_mission_approval(
        self,
        *,
        mission_id: str,
        operator_reference: str,
        decision: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        if note is not None and len(note) > 200:
            raise ValueError("note cannot exceed 200 characters")
        safe_id = _safe_identifier(mission_id, "mission_id")
        self.robot_missions.record_approval(
            safe_id,
            operator_reference=_safe_identifier(
                operator_reference, "operator_reference"
            ),
            decision=decision,
            note=note,
        )
        return {
            "mission_id": safe_id,
            "decision": decision,
            "recorded": True,
            "simulation_only": True,
        }

    def transition_robot_mission(
        self,
        *,
        mission_id: str,
        target_status: str,
        actor: str = "mcp-simulator",
        message: str | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        if message is not None and len(message) > 200:
            raise ValueError("message cannot exceed 200 characters")
        mission = self.robot_missions.transition(
            _safe_identifier(mission_id, "mission_id"),
            MissionStatus(target_status),
            actor=_safe_identifier(actor, "actor"),
            message=message,
            expected_version=expected_version,
        )
        result = _mission_dict(mission)
        result["physical_command_sent"] = False
        return result

    def record_robot_telemetry(
        self,
        *,
        robot_id: str,
        mission_id: str | None,
        battery_percent: float,
        current_zone: str,
        position_x: float,
        position_y: float,
        speed_mps: float,
    ) -> dict[str, Any]:
        record = self.robot_missions.record_telemetry(
            robot_id=_safe_identifier(robot_id, "robot_id"),
            mission_id=(
                _safe_identifier(mission_id, "mission_id") if mission_id else None
            ),
            battery_percent=battery_percent,
            current_zone=_safe_identifier(current_zone, "current_zone"),
            position_x=position_x,
            position_y=position_y,
            speed_mps=speed_mps,
        )
        return _telemetry_dict(record)

    def record_robot_safety_event(
        self,
        *,
        robot_id: str,
        mission_id: str | None,
        severity: str,
        event_type: str,
        message: str,
    ) -> dict[str, Any]:
        if len(message) > 200:
            raise ValueError("message cannot exceed 200 characters")
        event = self.robot_missions.record_safety_event(
            robot_id=_safe_identifier(robot_id, "robot_id"),
            mission_id=(
                _safe_identifier(mission_id, "mission_id") if mission_id else None
            ),
            severity=_safe_identifier(severity, "severity"),
            event_type=_safe_identifier(event_type, "event_type"),
            message=message,
        )
        return _safety_event_dict(event)
