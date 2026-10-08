from datetime import datetime, timedelta, timezone

import pytest

from tranceatables.models import DeliveryRequest
from tranceatables.order_state import OrderStatus
from tranceatables.repository import SQLiteOrderRepository
from tranceatables.robot_mission import InvalidMissionTransition, MissionStatus, RobotStatus
from tranceatables.robot_mission_repository import (
    MissionEligibilityError,
    SQLiteRobotMissionRepository,
)
from tranceatables.robot_mission_service import RobotMissionService
from tranceatables.service import OrderService


class ManualClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def setup_services(tmp_path):
    path = tmp_path / "stage2.sqlite3"
    clock = ManualClock()
    orders = OrderService(SQLiteOrderRepository(path), clock=clock)
    missions = RobotMissionService(SQLiteRobotMissionRepository(path), clock=clock)
    order = orders.create_order(DeliveryRequest("SIM-ORDER-1", 2.0, 2.0))
    for status in (
        OrderStatus.ACCEPTED,
        OrderStatus.PREPARED,
        OrderStatus.PACKAGED,
        OrderStatus.READY,
    ):
        order = orders.transition(order.order_id, status, actor="SIM-OPERATOR")
    missions.register_robot(
        robot_id="SIM-ROBOT-1",
        name="TRANCE-BOT-1",
        battery_percent=100,
        current_zone="SIM-CHARGING",
        payload_capacity_kg=10,
    )
    return orders, missions


def test_full_approved_simulation_cycle(tmp_path) -> None:
    orders, service = setup_services(tmp_path)
    mission = service.create_mission(
        mission_id="SIM-MISSION-1",
        order_id="SIM-ORDER-1",
        robot_id="SIM-ROBOT-1",
        pickup_zone="SIM-KITCHEN-1",
        dropoff_zone="SIM-HANDOFF-1",
        payload_kg=2,
        actor="SIM-OPERATOR",
    )
    assert mission.status is MissionStatus.PLANNED
    mission = service.transition(
        mission.mission_id,
        MissionStatus.AWAITING_APPROVAL,
        actor="SIM-OPERATOR",
    )
    service.record_approval(
        mission.mission_id,
        operator_reference="SIM-OPERATOR-1",
        decision="approved",
    )
    mission = service.transition(
        mission.mission_id,
        MissionStatus.APPROVED,
        actor="SIM-OPERATOR",
    )
    mission = service.transition(
        mission.mission_id,
        MissionStatus.DISPATCHED,
        actor="SIM-OPERATOR",
    )
    assert mission.status is MissionStatus.DISPATCHED
    assert orders.get_order("SIM-ORDER-1").status is OrderStatus.ASSIGNED
    assert service.get_robot("SIM-ROBOT-1").status is RobotStatus.ASSIGNED
    assert len(service.get_telemetry(mission.mission_id)) == 1

    for status in (
        MissionStatus.NAVIGATING_TO_PICKUP,
        MissionStatus.LOADING,
        MissionStatus.NAVIGATING_TO_DROPOFF,
        MissionStatus.AWAITING_HANDOFF,
        MissionStatus.COMPLETED,
    ):
        mission = service.transition(
            mission.mission_id, status, actor="SIM-OPERATOR"
        )
    assert service.get_robot("SIM-ROBOT-1").status is RobotStatus.AVAILABLE
    assert len(service.get_history(mission.mission_id)) == 9


def test_approval_is_required(tmp_path) -> None:
    _, service = setup_services(tmp_path)
    mission = service.create_mission(
        mission_id="SIM-MISSION-2",
        order_id="SIM-ORDER-1",
        robot_id="SIM-ROBOT-1",
        pickup_zone="SIM-KITCHEN-1",
        dropoff_zone="SIM-HANDOFF-1",
        payload_kg=2,
    )
    service.transition(
        mission.mission_id,
        MissionStatus.AWAITING_APPROVAL,
        actor="SIM-OPERATOR",
    )
    with pytest.raises(MissionEligibilityError, match="human approval"):
        service.transition(
            mission.mission_id,
            MissionStatus.APPROVED,
            actor="SIM-OPERATOR",
        )


def test_invalid_skip_does_not_mutate_mission(tmp_path) -> None:
    _, service = setup_services(tmp_path)
    mission = service.create_mission(
        mission_id="SIM-MISSION-3",
        order_id="SIM-ORDER-1",
        robot_id="SIM-ROBOT-1",
        pickup_zone="SIM-KITCHEN-1",
        dropoff_zone="SIM-HANDOFF-1",
        payload_kg=2,
    )
    with pytest.raises(InvalidMissionTransition):
        service.transition(
            mission.mission_id,
            MissionStatus.DISPATCHED,
            actor="SIM-OPERATOR",
        )
    assert service.get_mission(mission.mission_id).status is MissionStatus.PLANNED
    assert len(service.get_history(mission.mission_id)) == 1


def test_telemetry_and_safety_observations_are_persisted(tmp_path) -> None:
    _, service = setup_services(tmp_path)
    mission = service.create_mission(
        mission_id="SIM-MISSION-4",
        order_id="SIM-ORDER-1",
        robot_id="SIM-ROBOT-1",
        pickup_zone="SIM-KITCHEN-1",
        dropoff_zone="SIM-HANDOFF-1",
        payload_kg=2,
    )
    telemetry = service.record_telemetry(
        robot_id="SIM-ROBOT-1",
        mission_id=mission.mission_id,
        battery_percent=98,
        current_zone="SIM-ROUTE",
        position_x=1,
        position_y=0,
        speed_mps=0.5,
    )
    event = service.record_safety_event(
        robot_id="SIM-ROBOT-1",
        mission_id=mission.mission_id,
        severity="warning",
        event_type="simulated_obstacle",
        message="simulation only",
    )
    assert telemetry.battery_percent == 98
    assert event.resolved is False


def test_over_capacity_mission_is_rejected(tmp_path) -> None:
    _, service = setup_services(tmp_path)
    with pytest.raises(MissionEligibilityError, match="capacity"):
        service.create_mission(
            mission_id="SIM-MISSION-5",
            order_id="SIM-ORDER-1",
            robot_id="SIM-ROBOT-1",
            pickup_zone="SIM-KITCHEN-1",
            dropoff_zone="SIM-HANDOFF-1",
            payload_kg=11,
        )
