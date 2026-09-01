"""Dependency-free Stage 0 domain models."""

from dataclasses import dataclass
from enum import Enum


class FoodHandling(str, Enum):
    AMBIENT = "ambient"
    CHILLED = "chilled"
    HOT = "hot"


@dataclass(frozen=True)
class DeliveryRequest:
    order_id: str
    distance_km: float
    payload_kg: float
    handling: FoodHandling = FoodHandling.AMBIENT
    packaging_verified: bool = False
    customer_handoff_required: bool = True


@dataclass(frozen=True)
class RobotState:
    robot_id: str
    battery_percent: float
    available_range_km: float
    payload_capacity_kg: float
    operational: bool = True

    def __post_init__(self) -> None:
        if not 0 <= self.battery_percent <= 100:
            raise ValueError("battery_percent must be between 0 and 100")
        if self.available_range_km < 0 or self.payload_capacity_kg < 0:
            raise ValueError("range and capacity cannot be negative")
