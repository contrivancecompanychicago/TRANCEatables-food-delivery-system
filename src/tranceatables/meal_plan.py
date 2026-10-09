"""Stage 2.5 persistence for simulation-only abstract meal plans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Callable

from .nutrient_solver import MealConstraintSolution
from .order_state import OrderStatus
from .repository import SQLiteOrderRepository


class DuplicateMealPlanError(ValueError):
    pass


class MealPlanNotFoundError(LookupError):
    pass


class MealPlanEligibilityError(ValueError):
    pass


@dataclass(frozen=True)
class SimulatedMealPlan:
    meal_plan_id: str
    order_id: str
    nutrients: tuple[str, str, str]
    exact_food_quantities: tuple[str, str, str]
    food_quantities: tuple[float, float, float]
    calculated_targets: tuple[float, float, float]
    target_residuals: tuple[float, float, float]
    target_unit: str
    food_quantity_unit: str
    status: str
    food_item_ids: tuple[str | None, str | None, str | None]
    created_at: str
    updated_at: str
    simulation_only: bool = True


@dataclass(frozen=True)
class MealPlanEvent:
    event_id: int
    meal_plan_id: str
    event_type: str
    actor: str
    message: str
    occurred_at: str


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SQLiteMealPlanRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            orders_exists = connection.execute(
                """SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'orders'"""
            ).fetchone()
            if orders_exists is None:
                raise MealPlanEligibilityError(
                    "orders table must exist before meal-plan persistence"
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS simulated_meal_plans (
                    meal_plan_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL UNIQUE REFERENCES orders(order_id),
                    nutrients_json TEXT NOT NULL,
                    exact_quantities_json TEXT NOT NULL,
                    quantities_json TEXT NOT NULL,
                    calculated_targets_json TEXT NOT NULL,
                    residuals_json TEXT NOT NULL,
                    target_unit TEXT NOT NULL,
                    quantity_unit TEXT NOT NULL,
                    status TEXT NOT NULL,
                    food1_item_id TEXT,
                    food2_item_id TEXT,
                    food3_item_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1)
                );
                CREATE TABLE IF NOT EXISTS meal_plan_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meal_plan_id TEXT NOT NULL
                        REFERENCES simulated_meal_plans(meal_plan_id),
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    message TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                """
            )

    def create(
        self,
        plan: SimulatedMealPlan,
        *,
        actor: str,
        message: str,
    ) -> SimulatedMealPlan:
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO simulated_meal_plans VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        plan.meal_plan_id,
                        plan.order_id,
                        json.dumps(plan.nutrients),
                        json.dumps(plan.exact_food_quantities),
                        json.dumps(plan.food_quantities),
                        json.dumps(plan.calculated_targets),
                        json.dumps(plan.target_residuals),
                        plan.target_unit,
                        plan.food_quantity_unit,
                        plan.status,
                        plan.food_item_ids[0],
                        plan.food_item_ids[1],
                        plan.food_item_ids[2],
                        plan.created_at,
                        plan.updated_at,
                        int(plan.simulation_only),
                    ),
                )
                connection.execute(
                    """INSERT INTO meal_plan_events
                    (meal_plan_id, event_type, actor, message, occurred_at)
                    VALUES (?, 'meal_plan_created', ?, ?, ?)""",
                    (
                        plan.meal_plan_id,
                        actor,
                        message,
                        plan.created_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateMealPlanError(
                f"meal plan or order link already exists: {plan.meal_plan_id}"
            ) from error
        return plan

    def get(self, meal_plan_id: str) -> SimulatedMealPlan:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM simulated_meal_plans WHERE meal_plan_id = ?",
                (meal_plan_id,),
            ).fetchone()
        if row is None:
            raise MealPlanNotFoundError(meal_plan_id)
        return self._row_to_plan(row)

    def events(self, meal_plan_id: str) -> tuple[MealPlanEvent, ...]:
        self.get(meal_plan_id)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM meal_plan_events
                WHERE meal_plan_id = ? ORDER BY event_id""",
                (meal_plan_id,),
            ).fetchall()
        return tuple(
            MealPlanEvent(
                event_id=row["event_id"],
                meal_plan_id=row["meal_plan_id"],
                event_type=row["event_type"],
                actor=row["actor"],
                message=row["message"],
                occurred_at=row["occurred_at"],
            )
            for row in rows
        )

    @staticmethod
    def _row_to_plan(row: sqlite3.Row) -> SimulatedMealPlan:
        return SimulatedMealPlan(
            meal_plan_id=row["meal_plan_id"],
            order_id=row["order_id"],
            nutrients=tuple(json.loads(row["nutrients_json"])),
            exact_food_quantities=tuple(
                json.loads(row["exact_quantities_json"])
            ),
            food_quantities=tuple(json.loads(row["quantities_json"])),
            calculated_targets=tuple(
                json.loads(row["calculated_targets_json"])
            ),
            target_residuals=tuple(json.loads(row["residuals_json"])),
            target_unit=row["target_unit"],
            food_quantity_unit=row["quantity_unit"],
            status=row["status"],
            food_item_ids=(
                row["food1_item_id"],
                row["food2_item_id"],
                row["food3_item_id"],
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            simulation_only=bool(row["simulation_only"]),
        )


class MealPlanService:
    def __init__(
        self,
        order_repository: SQLiteOrderRepository,
        meal_plan_repository: SQLiteMealPlanRepository,
        *,
        clock: Clock = _utc_now,
    ) -> None:
        self.order_repository = order_repository
        self.meal_plan_repository = meal_plan_repository
        self.clock = clock

    def _timestamp(self) -> str:
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc).isoformat()

    def create_from_solution(
        self,
        meal_plan_id: str,
        order_id: str,
        solution: MealConstraintSolution,
        *,
        actor: str = "system",
    ) -> SimulatedMealPlan:
        if not meal_plan_id.strip() or not actor.strip():
            raise ValueError("meal_plan_id and actor cannot be blank")
        order = self.order_repository.get(order_id)
        if order.status is not OrderStatus.DRAFT:
            raise MealPlanEligibilityError(
                "abstract meal plans can only link to draft orders"
            )
        if solution.validation_status != "solved_unmapped":
            raise MealPlanEligibilityError(
                "only solved_unmapped solutions may be persisted"
            )
        if any(solution.target_residuals):
            raise MealPlanEligibilityError("solution residuals must be zero")

        timestamp = self._timestamp()
        plan = SimulatedMealPlan(
            meal_plan_id=meal_plan_id,
            order_id=order_id,
            nutrients=solution.nutrients,
            exact_food_quantities=solution.exact_food_quantities,
            food_quantities=solution.food_quantities,
            calculated_targets=solution.calculated_targets,
            target_residuals=solution.target_residuals,
            target_unit=solution.target_unit,
            food_quantity_unit=solution.food_quantity_unit,
            status=solution.validation_status,
            food_item_ids=(None, None, None),
            created_at=timestamp,
            updated_at=timestamp,
        )
        return self.meal_plan_repository.create(
            plan,
            actor=actor,
            message=(
                "abstract model solution persisted; grocery products remain unmapped"
            ),
        )
