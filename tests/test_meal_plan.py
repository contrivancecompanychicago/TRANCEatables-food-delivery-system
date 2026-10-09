from dataclasses import replace
from datetime import datetime, timezone

import pytest

from tranceatables import DeliveryRequest, OrderService, SQLiteOrderRepository
from tranceatables.meal_plan import (
    DuplicateMealPlanError,
    MealPlanEligibilityError,
    MealPlanService,
    SQLiteMealPlanRepository,
)
from tranceatables.nutrient_solver import solve_meal_references


REFERENCES = [
    {
        "mealReferenceId": "MEAL-NUTRIENT-001",
        "nutrient": "Vitamin C",
        "food1Amount": 10,
        "food2Amount": 20,
        "food3Amount": 20,
        "targetAmount": 100,
    },
    {
        "mealReferenceId": "MEAL-NUTRIENT-002",
        "nutrient": "Calcium",
        "food1Amount": 50,
        "food2Amount": 40,
        "food3Amount": 10,
        "targetAmount": 300,
    },
    {
        "mealReferenceId": "MEAL-NUTRIENT-003",
        "nutrient": "Magnesium",
        "food1Amount": 30,
        "food2Amount": 10,
        "food3Amount": 40,
        "targetAmount": 200,
    },
]


def fixed_clock():
    return datetime(2026, 10, 9, 19, 0, tzinfo=timezone.utc)


def setup_service(tmp_path):
    database = tmp_path / "meal-plans.sqlite3"
    orders = SQLiteOrderRepository(database)
    OrderService(orders).create_order(
        DeliveryRequest(
            "SIM-ORDER-0002",
            2.0,
            2.0,
            restaurant_id="SIM-RESTAURANT-001",
            pickup_zone="SIM_RESTAURANT_KITCHEN_001",
        )
    )
    plans = SQLiteMealPlanRepository(database)
    return MealPlanService(orders, plans, clock=fixed_clock), plans


def test_persists_solution_and_append_only_event(tmp_path):
    service, repository = setup_service(tmp_path)
    solution = solve_meal_references(REFERENCES)

    created = service.create_from_solution(
        "SIM-MEAL-PLAN-0001",
        "SIM-ORDER-0002",
        solution,
        actor="colab-simulation",
    )
    reopened = SQLiteMealPlanRepository(
        repository.database_path
    ).get(created.meal_plan_id)

    assert reopened.order_id == "SIM-ORDER-0002"
    assert reopened.exact_food_quantities == ("50/11", "50/33", "40/33")
    assert reopened.target_residuals == (0.0, 0.0, 0.0)
    assert reopened.status == "solved_unmapped"
    assert reopened.food_item_ids == (None, None, None)
    assert reopened.simulation_only is True

    events = repository.events(created.meal_plan_id)
    assert len(events) == 1
    assert events[0].event_type == "meal_plan_created"
    assert events[0].actor == "colab-simulation"


def test_rejects_duplicate_plan_or_second_plan_for_order(tmp_path):
    service, _ = setup_service(tmp_path)
    solution = solve_meal_references(REFERENCES)
    service.create_from_solution("SIM-MEAL-PLAN-0001", "SIM-ORDER-0002", solution)

    with pytest.raises(DuplicateMealPlanError):
        service.create_from_solution(
            "SIM-MEAL-PLAN-0002", "SIM-ORDER-0002", solution
        )


def test_rejects_nonzero_residuals(tmp_path):
    service, _ = setup_service(tmp_path)
    solution = replace(
        solve_meal_references(REFERENCES),
        target_residuals=(1.0, 0.0, 0.0),
    )
    with pytest.raises(MealPlanEligibilityError, match="zero"):
        service.create_from_solution(
            "SIM-MEAL-PLAN-0001", "SIM-ORDER-0002", solution
        )


def test_requires_existing_orders_table(tmp_path):
    with pytest.raises(MealPlanEligibilityError, match="orders table"):
        SQLiteMealPlanRepository(tmp_path / "empty.sqlite3")
