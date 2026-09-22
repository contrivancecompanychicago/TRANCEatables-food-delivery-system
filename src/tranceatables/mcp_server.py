"""Stage 1.5 simulation-only MCP adapter.

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


@mcp.resource("tranceatables://orders/{order_id}")
def order_resource(order_id: str) -> dict:
    """Read the current snapshot of one simulated order."""
    return api.get_order(order_id)


@mcp.resource("tranceatables://orders/{order_id}/history")
def order_history_resource(order_id: str) -> dict:
    """Read the append-only event history of one simulated order."""
    return api.get_history(order_id)


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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
