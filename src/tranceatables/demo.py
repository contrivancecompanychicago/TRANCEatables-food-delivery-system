"""Command-line demonstration for the non-physical Stage 0 core."""

from .feasibility import evaluate_delivery
from .models import DeliveryRequest, FoodHandling, RobotState


def main() -> None:
    """Evaluate one safe-to-screen example and print the decision."""
    request = DeliveryRequest(
        order_id="TRANCE-STAGE0-001",
        distance_km=1.5,
        payload_kg=2.0,
        handling=FoodHandling.HOT,
        packaging_verified=True,
    )
    robot = RobotState(
        robot_id="SIM-ROBOT-001",
        battery_percent=80,
        available_range_km=10,
        payload_capacity_kg=8,
    )
    print(evaluate_delivery(request, robot))


if __name__ == "__main__":
    main()
