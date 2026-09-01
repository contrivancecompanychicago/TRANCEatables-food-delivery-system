import pytest

from tranceatables import DeliveryRequest, FoodHandling, RobotState, evaluate_delivery


def test_feasible_delivery() -> None:
    request = DeliveryRequest("order-1", 1.0, 2.0, packaging_verified=True)
    robot = RobotState("robot-1", 80, 5.0, 5.0)
    decision = evaluate_delivery(request, robot)
    assert decision.feasible
    assert decision.reasons == ()


def test_rejects_multiple_constraints() -> None:
    request = DeliveryRequest("order-2", 3.0, 8.0, FoodHandling.HOT, False)
    robot = RobotState("robot-2", 20, 4.0, 5.0)
    decision = evaluate_delivery(request, robot)
    assert not decision.feasible
    assert set(decision.reasons) == {
        "payload_exceeds_capacity",
        "insufficient_round_trip_range",
        "battery_below_stage_0_floor",
        "temperature_control_packaging_unverified",
    }


def test_invalid_battery_is_rejected() -> None:
    with pytest.raises(ValueError):
        RobotState("robot-3", 101, 5.0, 5.0)
