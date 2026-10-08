from pathlib import Path

import pytest

from tranceatables.mcp_api import SimulationMCPAPI
from tranceatables.order_state import InvalidTransition


def api(tmp_path: Path) -> SimulationMCPAPI:
    return SimulationMCPAPI(tmp_path / "simulation.sqlite3")


def test_about_declares_simulation_boundary() -> None:
    result = SimulationMCPAPI.about()
    assert result["mode"] == "simulation-only"
    assert "control or dispatch a physical robot" in result["cannot_do"]


def test_evaluate_never_dispatches() -> None:
    result = SimulationMCPAPI.evaluate(
        order_id="SIM-100",
        distance_km=1.0,
        payload_kg=1.0,
        handling="ambient",
        packaging_verified=False,
        robot_id="BOT-1",
        battery_percent=80,
        available_range_km=10,
        payload_capacity_kg=5,
    )
    assert result["feasible"] is True
    assert result["simulation_only"] is True
    assert result["dispatched"] is False


def test_create_transition_and_history(tmp_path: Path) -> None:
    simulation = api(tmp_path)
    created = simulation.create_order(
        order_id="SIM-101", distance_km=2.0, payload_kg=1.5
    )
    assert created["status"] == "draft"
    assert created["allowed_next_statuses"] == ["accepted", "cancelled"]

    accepted = simulation.transition_order(
        order_id="SIM-101", target_status="accepted", expected_version=0
    )
    assert accepted["status"] == "accepted"
    assert accepted["version"] == 1
    assert len(simulation.get_history("SIM-101")["events"]) == 2


def test_invalid_transition_is_rejected(tmp_path: Path) -> None:
    simulation = api(tmp_path)
    simulation.create_order(order_id="SIM-102", distance_km=2, payload_kg=1)
    with pytest.raises(InvalidTransition):
        simulation.transition_order(order_id="SIM-102", target_status="ready")


@pytest.mark.parametrize("unsafe", ["", "contains space", "name@example.com", "x" * 65])
def test_identifiers_are_data_minimized(tmp_path: Path, unsafe: str) -> None:
    with pytest.raises(ValueError):
        api(tmp_path).create_order(order_id=unsafe, distance_km=1, payload_kg=1)


def test_stage_2_mission_requires_approval_and_never_sends_physical_command(
    tmp_path: Path,
) -> None:
    simulation = api(tmp_path)
    simulation.create_order(order_id="SIM-200", distance_km=2, payload_kg=2)
    for target in ("accepted", "prepared", "packaged", "ready"):
        simulation.transition_order(order_id="SIM-200", target_status=target)

    robot = simulation.register_simulated_robot(
        robot_id="SIM-ROBOT-1",
        name="TRANCE-BOT-1",
        battery_percent=100,
        current_zone="SIM-CHARGING",
        payload_capacity_kg=10,
    )
    assert robot["status"] == "available"

    mission = simulation.create_robot_mission(
        mission_id="SIM-MISSION-1",
        order_id="SIM-200",
        robot_id="SIM-ROBOT-1",
        pickup_zone="SIM-KITCHEN-1",
        dropoff_zone="SIM-HANDOFF-1",
        payload_kg=2,
    )
    mission = simulation.transition_robot_mission(
        mission_id=mission["mission_id"],
        target_status="awaiting_approval",
    )
    with pytest.raises(ValueError, match="human approval"):
        simulation.transition_robot_mission(
            mission_id=mission["mission_id"],
            target_status="approved",
        )

    simulation.record_robot_mission_approval(
        mission_id=mission["mission_id"],
        operator_reference="SIM-OPERATOR-1",
        decision="approved",
    )
    mission = simulation.transition_robot_mission(
        mission_id=mission["mission_id"],
        target_status="approved",
    )
    mission = simulation.transition_robot_mission(
        mission_id=mission["mission_id"],
        target_status="dispatched",
    )
    assert mission["status"] == "dispatched"
    assert mission["physical_command_sent"] is False
    assert simulation.get_order("SIM-200")["status"] == "assigned"
    assert simulation.get_simulated_robot("SIM-ROBOT-1")["status"] == "assigned"
    assert len(
        simulation.get_robot_mission_telemetry("SIM-MISSION-1")["telemetry"]
    ) == 1
