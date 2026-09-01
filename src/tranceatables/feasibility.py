"""Conservative, deterministic Stage 0 delivery screening."""

from dataclasses import dataclass

from .models import DeliveryRequest, FoodHandling, RobotState


@dataclass(frozen=True)
class FeasibilityDecision:
    feasible: bool
    reasons: tuple[str, ...]


def evaluate_delivery(
    request: DeliveryRequest,
    robot: RobotState,
    *,
    reserve_fraction: float = 0.20,
) -> FeasibilityDecision:
    """Return a Stage 0 go/no-go decision without dispatching a robot.

    Range is evaluated as a round trip plus a configurable reserve. Perishable
    food requires verified packaging. Real deployments need validated routing,
    local authorization, telemetry, hazard detection, and human oversight.
    """
    if not 0 <= reserve_fraction < 1:
        raise ValueError("reserve_fraction must be in [0, 1)")
    if request.distance_km < 0 or request.payload_kg < 0:
        raise ValueError("distance and payload cannot be negative")

    reasons: list[str] = []
    required_range = request.distance_km * 2 * (1 + reserve_fraction)

    if not robot.operational:
        reasons.append("robot_not_operational")
    if request.payload_kg > robot.payload_capacity_kg:
        reasons.append("payload_exceeds_capacity")
    if required_range > robot.available_range_km:
        reasons.append("insufficient_round_trip_range")
    if robot.battery_percent < 25:
        reasons.append("battery_below_stage_0_floor")
    if request.handling in {FoodHandling.CHILLED, FoodHandling.HOT} and not request.packaging_verified:
        reasons.append("temperature_control_packaging_unverified")

    return FeasibilityDecision(feasible=not reasons, reasons=tuple(reasons))
