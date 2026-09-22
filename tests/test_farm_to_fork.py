from pathlib import Path

import pytest

from tranceatables.farm_to_fork import InvalidFarmToForkTransition
from tranceatables.mcp_api import SimulationMCPAPI
from tranceatables.repository import ConcurrentUpdateError


def api(tmp_path: Path) -> SimulationMCPAPI:
    return SimulationMCPAPI(tmp_path / "farm-to-fork.sqlite3")


def test_create_trace_starts_planned(tmp_path: Path) -> None:
    result = api(tmp_path).create_farm_to_fork_trace(
        trace_id="TRACE-1",
        farm_code="FARM-CHI-1",
        product_code="KALE-LOT-1",
        order_id="SIM-200",
    )
    assert result["status"] == "planned"
    assert result["allowed_next_statuses"] == ["cancelled", "harvested"]
    assert result["simulation_only"] is True


def test_trace_progress_and_audit_metadata(tmp_path: Path) -> None:
    simulation = api(tmp_path)
    simulation.create_farm_to_fork_trace(
        trace_id="TRACE-2", farm_code="FARM-1", product_code="SPINACH-1"
    )
    result = simulation.transition_farm_to_fork_trace(
        trace_id="TRACE-2",
        target_status="harvested",
        location_code="FIELD-A",
        temperature_c=18.5,
        note="simulation harvest",
        expected_version=0,
    )
    assert result["status"] == "harvested"
    history = simulation.get_farm_to_fork_history("TRACE-2")
    assert len(history["events"]) == 2
    assert history["events"][1]["temperature_c"] == 18.5
    assert history["events"][1]["location_code"] == "FIELD-A"


def test_trace_rejects_skipped_stage(tmp_path: Path) -> None:
    simulation = api(tmp_path)
    simulation.create_farm_to_fork_trace(
        trace_id="TRACE-3", farm_code="FARM-1", product_code="KALE-1"
    )
    with pytest.raises(InvalidFarmToForkTransition):
        simulation.transition_farm_to_fork_trace(
            trace_id="TRACE-3", target_status="kitchen_received"
        )


def test_trace_optimistic_concurrency(tmp_path: Path) -> None:
    simulation = api(tmp_path)
    simulation.create_farm_to_fork_trace(
        trace_id="TRACE-4", farm_code="FARM-1", product_code="KALE-2"
    )
    simulation.transition_farm_to_fork_trace(
        trace_id="TRACE-4", target_status="harvested", expected_version=0
    )
    with pytest.raises(ConcurrentUpdateError):
        simulation.transition_farm_to_fork_trace(
            trace_id="TRACE-4", target_status="farm_packed", expected_version=0
        )


def test_trace_temperature_guard(tmp_path: Path) -> None:
    simulation = api(tmp_path)
    simulation.create_farm_to_fork_trace(
        trace_id="TRACE-5", farm_code="FARM-1", product_code="KALE-3"
    )
    with pytest.raises(ValueError, match="temperature_c"):
        simulation.transition_farm_to_fork_trace(
            trace_id="TRACE-5", target_status="harvested", temperature_c=151
        )
