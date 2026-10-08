"""Stage 2 simulation-only MCP adapter.

Run locally with:
    python -m tranceatables.mcp_server
"""

from __future__ import annotations

import os

from mcp.server import MCPServer

from .mcp_api import SimulationMCPAPI


api = SimulationMCPAPI(os.getenv("TRANCEATABLES_DB_PATH", "tranceatables-simulation.sqlite3"))
mcp = MCPServer("TRANCEatables Simulation")


@mcp.resource("tranceatables://about")
def about() -> dict:
    """Explain the server's simulation scope and data-safety boundary."""
    return api.about()


@mcp.resource("tranceatables://knowledge/culapse-data-farm/stage-fit")
def culapse_stage_fit_resource() -> dict:
    """Read how CULAPSE evidence maps to farm-to-fork stages and its limits."""
    return api.culapse_stage_fit()


@mcp.resource("tranceatables://integrations/january-ai/restaurants")
def january_ai_restaurant_integration_resource() -> dict:
    """Read placement, configuration status, and safety boundaries for January AI."""
    return api.january_ai_status()


@mcp.resource("tranceatables://orders/{order_id}")
def order_resource(order_id: str) -> dict:
    """Read the current snapshot of one simulated order."""
    return api.get_order(order_id)


@mcp.resource("tranceatables://orders/{order_id}/history")
def order_history_resource(order_id: str) -> dict:
    """Read the append-only event history of one simulated order."""
    return api.get_history(order_id)


@mcp.resource("tranceatables://farm-to-fork/{trace_id}")
def farm_to_fork_resource(trace_id: str) -> dict:
    """Read one simulated farm-to-fork trace."""
    return api.get_farm_to_fork_trace(trace_id)


@mcp.resource("tranceatables://farm-to-fork/{trace_id}/history")
def farm_to_fork_history_resource(trace_id: str) -> dict:
    """Read the append-only events for one farm-to-fork trace."""
    return api.get_farm_to_fork_history(trace_id)


@mcp.tool()
def evaluate_simulated_delivery(
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
) -> dict:
    """Evaluate a hypothetical delivery without creating an order or dispatching a robot."""
    return api.evaluate(
        order_id=order_id,
        distance_km=distance_km,
        payload_kg=payload_kg,
        handling=handling,
        packaging_verified=packaging_verified,
        robot_id=robot_id,
        battery_percent=battery_percent,
        available_range_km=available_range_km,
        payload_capacity_kg=payload_capacity_kg,
        operational=operational,
        reserve_fraction=reserve_fraction,
    )


@mcp.tool()
def evaluate_culapse_planning_checkpoint(
    production_reliability: float,
    maintenance_feasibility: float,
    capital_sufficiency: float,
) -> dict:
    """Calculate the CULAPSE planning stability classification for simulation."""
    return api.evaluate_culapse_planning(
        production_reliability=production_reliability,
        maintenance_feasibility=maintenance_feasibility,
        capital_sufficiency=capital_sufficiency,
    )


@mcp.tool()
def evaluate_culapse_harvest_checkpoint(
    potential_yield_units: float,
    collected_yield_units: float,
) -> dict:
    """Calculate harvest completion and FPP-05 routing-loss evidence."""
    return api.evaluate_culapse_harvest(
        potential_yield_units=potential_yield_units,
        collected_yield_units=collected_yield_units,
    )


@mcp.tool()
def fetch_january_ai_restaurants() -> dict:
    """Fetch read-only restaurant reference data when the opt-in adapter is configured."""
    return api.fetch_january_ai_restaurants()


@mcp.tool()
def create_simulated_order(
    order_id: str,
    distance_km: float,
    payload_kg: float,
    handling: str = "ambient",
    packaging_verified: bool = False,
    customer_handoff_required: bool = True,
    actor: str = "mcp-simulator",
) -> dict:
    """Create a local simulated order in draft state; use opaque test identifiers only."""
    return api.create_order(
        order_id=order_id,
        distance_km=distance_km,
        payload_kg=payload_kg,
        handling=handling,
        packaging_verified=packaging_verified,
        customer_handoff_required=customer_handoff_required,
        actor=actor,
    )


@mcp.tool()
def get_simulated_order(order_id: str) -> dict:
    """Read one simulated order and its allowed next states."""
    return api.get_order(order_id)


@mcp.tool()
def get_simulated_order_history(order_id: str) -> dict:
    """Read the append-only audit history for one simulated order."""
    return api.get_history(order_id)


@mcp.tool()
def transition_simulated_order(
    order_id: str,
    target_status: str,
    actor: str = "mcp-simulator",
    reason: str | None = None,
    expected_version: int | None = None,
) -> dict:
    """Advance or cancel a simulated order using the Stage 1 state machine."""
    return api.transition_order(
        order_id=order_id,
        target_status=target_status,
        actor=actor,
        reason=reason,
        expected_version=expected_version,
    )


@mcp.tool()
def create_simulated_farm_to_fork_trace(
    trace_id: str,
    farm_code: str,
    product_code: str,
    order_id: str | None = None,
    actor: str = "mcp-simulator",
) -> dict:
    """Create a simulated food-lot trace starting in planned state."""
    return api.create_farm_to_fork_trace(
        trace_id=trace_id,
        farm_code=farm_code,
        product_code=product_code,
        order_id=order_id,
        actor=actor,
    )


@mcp.tool()
def get_simulated_farm_to_fork_trace(trace_id: str) -> dict:
    """Read a simulated trace and its permitted next states."""
    return api.get_farm_to_fork_trace(trace_id)


@mcp.tool()
def get_simulated_farm_to_fork_history(trace_id: str) -> dict:
    """Read the append-only event history for a simulated trace."""
    return api.get_farm_to_fork_history(trace_id)


@mcp.tool()
def transition_simulated_farm_to_fork_trace(
    trace_id: str,
    target_status: str,
    actor: str = "mcp-simulator",
    location_code: str | None = None,
    temperature_c: float | None = None,
    note: str | None = None,
    expected_version: int | None = None,
) -> dict:
    """Advance or cancel a simulated farm-to-fork trace."""
    return api.transition_farm_to_fork_trace(
        trace_id=trace_id,
        target_status=target_status,
        actor=actor,
        location_code=location_code,
        temperature_c=temperature_c,
        note=note,
        expected_version=expected_version,
    )



@mcp.resource("tranceatables://robots/{robot_id}")
def simulated_robot_resource(robot_id: str) -> dict:
    """Read one simulated robot snapshot."""
    return api.get_simulated_robot(robot_id)


@mcp.resource("tranceatables://robot-missions/{mission_id}")
def robot_mission_resource(mission_id: str) -> dict:
    """Read one simulation-only robot mission."""
    return api.get_robot_mission(mission_id)


@mcp.resource("tranceatables://robot-missions/{mission_id}/history")
def robot_mission_history_resource(mission_id: str) -> dict:
    """Read append-only mission transition history."""
    return api.get_robot_mission_history(mission_id)


@mcp.resource("tranceatables://robot-missions/{mission_id}/telemetry")
def robot_mission_telemetry_resource(mission_id: str) -> dict:
    """Read generated simulation telemetry; values are not physical sensor data."""
    return api.get_robot_mission_telemetry(mission_id)


@mcp.tool()
def register_simulated_robot(
    robot_id: str,
    name: str,
    battery_percent: float,
    current_zone: str,
    payload_capacity_kg: float,
    operational: bool = True,
) -> dict:
    """Register a local simulated robot; this does not connect to hardware."""
    return api.register_simulated_robot(
        robot_id=robot_id,
        name=name,
        battery_percent=battery_percent,
        current_zone=current_zone,
        payload_capacity_kg=payload_capacity_kg,
        operational=operational,
    )


@mcp.tool()
def create_simulated_robot_mission(
    mission_id: str,
    order_id: str,
    robot_id: str,
    pickup_zone: str,
    dropoff_zone: str,
    payload_kg: float,
    actor: str = "mcp-simulator",
) -> dict:
    """Plan a mission for a ready simulated order and eligible simulated robot."""
    return api.create_robot_mission(
        mission_id=mission_id,
        order_id=order_id,
        robot_id=robot_id,
        pickup_zone=pickup_zone,
        dropoff_zone=dropoff_zone,
        payload_kg=payload_kg,
        actor=actor,
    )


@mcp.tool()
def record_simulated_mission_approval(
    mission_id: str,
    operator_reference: str,
    decision: str,
    note: str | None = None,
) -> dict:
    """Record an explicit human simulation approval or rejection."""
    return api.record_robot_mission_approval(
        mission_id=mission_id,
        operator_reference=operator_reference,
        decision=decision,
        note=note,
    )


@mcp.tool()
def transition_simulated_robot_mission(
    mission_id: str,
    target_status: str,
    actor: str = "mcp-simulator",
    message: str | None = None,
    expected_version: int | None = None,
) -> dict:
    """Apply one validated simulation transition; no physical command is sent."""
    return api.transition_robot_mission(
        mission_id=mission_id,
        target_status=target_status,
        actor=actor,
        message=message,
        expected_version=expected_version,
    )


@mcp.tool()
def record_simulated_robot_telemetry(
    robot_id: str,
    mission_id: str | None,
    battery_percent: float,
    current_zone: str,
    position_x: float,
    position_y: float,
    speed_mps: float,
) -> dict:
    """Store generated simulation telemetry, never physical sensor telemetry."""
    return api.record_robot_telemetry(
        robot_id=robot_id,
        mission_id=mission_id,
        battery_percent=battery_percent,
        current_zone=current_zone,
        position_x=position_x,
        position_y=position_y,
        speed_mps=speed_mps,
    )


@mcp.tool()
def record_simulated_robot_safety_event(
    robot_id: str,
    mission_id: str | None,
    severity: str,
    event_type: str,
    message: str,
) -> dict:
    """Record a simulation safety observation; this cannot actuate an emergency stop."""
    return api.record_robot_safety_event(
        robot_id=robot_id,
        mission_id=mission_id,
        severity=severity,
        event_type=event_type,
        message=message,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
