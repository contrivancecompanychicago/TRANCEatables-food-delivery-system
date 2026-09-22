"""Pure farm-to-fork traceability rules for simulated deliveries."""

from dataclasses import dataclass, replace
from enum import Enum


class FarmToForkStatus(str, Enum):
    PLANNED = "planned"
    HARVESTED = "harvested"
    FARM_PACKED = "farm_packed"
    PICKED_UP = "picked_up"
    KITCHEN_RECEIVED = "kitchen_received"
    MEAL_PREPARED = "meal_prepared"
    MEAL_PACKAGED = "meal_packaged"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


_SEQUENCE = (
    FarmToForkStatus.PLANNED,
    FarmToForkStatus.HARVESTED,
    FarmToForkStatus.FARM_PACKED,
    FarmToForkStatus.PICKED_UP,
    FarmToForkStatus.KITCHEN_RECEIVED,
    FarmToForkStatus.MEAL_PREPARED,
    FarmToForkStatus.MEAL_PACKAGED,
    FarmToForkStatus.OUT_FOR_DELIVERY,
    FarmToForkStatus.DELIVERED,
)

ALLOWED_FARM_TO_FORK_TRANSITIONS: dict[FarmToForkStatus, frozenset[FarmToForkStatus]] = {
    status: frozenset(
        ({_SEQUENCE[index + 1]} if index + 1 < len(_SEQUENCE) else set())
        | ({FarmToForkStatus.CANCELLED} if status != FarmToForkStatus.DELIVERED else set())
    )
    for index, status in enumerate(_SEQUENCE)
}
ALLOWED_FARM_TO_FORK_TRANSITIONS[FarmToForkStatus.CANCELLED] = frozenset()


class InvalidFarmToForkTransition(ValueError):
    """Raised when a traceability transition is not permitted."""


@dataclass(frozen=True)
class FarmToForkRecord:
    trace_id: str
    farm_code: str
    product_code: str
    order_id: str | None
    status: FarmToForkStatus
    version: int
    created_at: str
    updated_at: str


def transition_farm_to_fork(
    record: FarmToForkRecord,
    target: FarmToForkStatus,
    *,
    occurred_at: str,
) -> FarmToForkRecord:
    if target not in ALLOWED_FARM_TO_FORK_TRANSITIONS[record.status]:
        raise InvalidFarmToForkTransition(
            f"cannot transition trace from {record.status.value} to {target.value}"
        )
    return replace(
        record,
        status=target,
        version=record.version + 1,
        updated_at=occurred_at,
    )
