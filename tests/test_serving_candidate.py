from datetime import datetime, timezone

import pytest

from tranceatables import DeliveryRequest, OrderService, SQLiteOrderRepository
from tranceatables.meal_plan import MealPlanService, SQLiteMealPlanRepository
from tranceatables.nutrient_solver import solve_meal_references
from tranceatables.serving_candidate import (
    DuplicateServingCandidateError,
    DuplicateServingCandidateReviewError,
    ServingCandidateEligibilityError,
    ServingCandidateInput,
    ServingCandidateService,
    SQLiteServingCandidateRepository,
)


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
    return datetime(2026, 10, 10, 20, 0, tzinfo=timezone.utc)


def setup_service(tmp_path):
    database = tmp_path / "serving-candidates.sqlite3"
    orders = SQLiteOrderRepository(database)
    order_service = OrderService(orders)
    order_service.create_order(
        DeliveryRequest(
            "SIM-ORDER-0002",
            2.0,
            2.0,
            restaurant_id="SIM-RESTAURANT-001",
            pickup_zone="SIM_RESTAURANT_KITCHEN_001",
        )
    )
    plans = SQLiteMealPlanRepository(database)
    MealPlanService(orders, plans, clock=fixed_clock).create_from_solution(
        "SIM-MEAL-PLAN-0001",
        "SIM-ORDER-0002",
        solve_meal_references(REFERENCES),
        actor="colab-simulation",
    )
    candidates = SQLiteServingCandidateRepository(database)
    service = ServingCandidateService(plans, candidates, clock=fixed_clock)
    return service, candidates, plans, orders


def orange_juice(**changes):
    values = {
        "candidate_id": "SERVING-CANDIDATE-0001",
        "meal_plan_id": "SIM-MEAL-PLAN-0001",
        "food_slot": 1,
        "source": "sheety",
        "source_item_id": "51c3d56997c3e6d8d3b53524",
        "source_upc": "41268111268",
        "brand_name": "Hannaford",
        "item_name": "Orange Juice",
        "serving_quantity": 8.0,
        "serving_unit_label": "fl oz",
        "serving_weight_grams": 226.0,
        "metric_quantity": 226.0,
        "metric_unit": "g",
    }
    values.update(changes)
    return ServingCandidateInput(**values)


def test_persists_structurally_valid_candidate_and_event(tmp_path):
    service, repository, _, _ = setup_service(tmp_path)

    created = service.create_candidate(
        orange_juice(),
        actor="colab-human-review",
    )
    reopened = SQLiteServingCandidateRepository(
        repository.database_path
    ).get(created.candidate_id)

    assert reopened.review_status == "structurally_valid"
    assert reopened.serving_quantity == 8.0
    assert reopened.serving_unit_label == "fl oz"
    assert reopened.serving_weight_grams == 226.0
    assert reopened.simulation_only is True

    events = repository.events(created.candidate_id)
    assert len(events) == 1
    assert events[0].event_type == "candidate_created"
    assert events[0].actor == "colab-human-review"


def test_persists_mass_missing_candidate_for_review(tmp_path):
    service, repository, _, _ = setup_service(tmp_path)

    created = service.create_candidate(
        orange_juice(
            candidate_id="SERVING-CANDIDATE-0002",
            food_slot=2,
            source_item_id="54f01bf33e1cba632126a72e",
            source_upc="74336863950",
            brand_name="Hunter Farms",
            item_name="Milk, 2% Reduced Fat",
            serving_quantity=1.74,
            serving_unit_label="cups",
            serving_weight_grams=None,
            metric_quantity=414.0,
            metric_unit="ml",
        ),
        actor="colab-human-review",
    )

    assert created.review_status == "mass_missing"
    assert repository.get(created.candidate_id).serving_weight_grams is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"food_slot": 4}, "food_slot"),
        ({"serving_quantity": 0}, "serving_quantity"),
        ({"serving_weight_grams": -1}, "serving_weight_grams"),
        ({"metric_unit": None}, "supplied together"),
        ({"metric_quantity": None}, "supplied together"),
    ],
)
def test_rejects_invalid_candidate_input(tmp_path, changes, message):
    service, _, _, _ = setup_service(tmp_path)

    with pytest.raises(ValueError, match=message):
        service.create_candidate(
            orange_juice(**changes),
            actor="colab-human-review",
        )


def test_rejects_duplicate_candidate_mapping(tmp_path):
    service, _, _, _ = setup_service(tmp_path)
    service.create_candidate(orange_juice(), actor="colab-human-review")

    with pytest.raises(DuplicateServingCandidateError):
        service.create_candidate(
            orange_juice(candidate_id="SERVING-CANDIDATE-0099"),
            actor="colab-human-review",
        )


def test_candidate_review_does_not_map_plan_or_advance_order(tmp_path):
    service, _, plans, orders = setup_service(tmp_path)

    service.create_candidate(orange_juice(), actor="colab-human-review")

    assert plans.get("SIM-MEAL-PLAN-0001").food_item_ids == (None, None, None)
    assert plans.get("SIM-MEAL-PLAN-0001").status == "solved_unmapped"
    assert orders.get("SIM-ORDER-0002").status.value == "draft"


def test_requires_existing_meal_plan_table(tmp_path):
    SQLiteOrderRepository(tmp_path / "orders-only.sqlite3")

    with pytest.raises(
        ServingCandidateEligibilityError,
        match="simulated_meal_plans",
    ):
        SQLiteServingCandidateRepository(tmp_path / "orders-only.sqlite3")


def test_approves_structurally_valid_candidate_with_audit_event(tmp_path):
    service, repository, plans, orders = setup_service(tmp_path)
    service.create_candidate(orange_juice(), actor="colab-human-review")

    review = service.review_candidate(
        review_id="SERVING-REVIEW-0001",
        candidate_id="SERVING-CANDIDATE-0001",
        decision="approved",
        reviewer="human-operator",
        notes="Serving description and gram weight checked.",
    )

    assert review.decision == "approved"
    assert review.simulation_only is True
    assert repository.get_review(review.candidate_id) == review
    assert [event.event_type for event in repository.events(review.candidate_id)] == [
        "candidate_created",
        "candidate_reviewed",
    ]
    assert plans.get("SIM-MEAL-PLAN-0001").food_item_ids == (None, None, None)
    assert plans.get("SIM-MEAL-PLAN-0001").status == "solved_unmapped"
    assert orders.get("SIM-ORDER-0002").status.value == "draft"


def test_mass_missing_candidate_requires_correction_not_approval(tmp_path):
    service, repository, _, _ = setup_service(tmp_path)
    milk = orange_juice(
        candidate_id="SERVING-CANDIDATE-0002",
        food_slot=2,
        source_item_id="54f01bf33e1cba632126a72e",
        source_upc="74336863950",
        brand_name="Hunter Farms",
        item_name="Milk, 2% Reduced Fat",
        serving_quantity=1.74,
        serving_unit_label="cups",
        serving_weight_grams=None,
        metric_quantity=414.0,
        metric_unit="ml",
    )
    service.create_candidate(milk, actor="colab-human-review")

    with pytest.raises(ServingCandidateEligibilityError, match="structurally_valid"):
        service.review_candidate(
            review_id="SERVING-REVIEW-0002",
            candidate_id=milk.candidate_id,
            decision="approved",
            reviewer="human-operator",
            notes="Approval attempted without a gram weight.",
        )

    review = service.review_candidate(
        review_id="SERVING-REVIEW-0002",
        candidate_id=milk.candidate_id,
        decision="correction_required",
        reviewer="human-operator",
        notes="Verified gram weight is required.",
    )
    assert review.decision == "correction_required"
    assert repository.get_review(milk.candidate_id) == review


def test_rejects_duplicate_review_and_invalid_decision(tmp_path):
    service, _, _, _ = setup_service(tmp_path)
    service.create_candidate(orange_juice(), actor="colab-human-review")
    values = {
        "review_id": "SERVING-REVIEW-0001",
        "candidate_id": "SERVING-CANDIDATE-0001",
        "decision": "approved",
        "reviewer": "human-operator",
        "notes": "Reviewed.",
    }
    service.review_candidate(**values)

    with pytest.raises(DuplicateServingCandidateReviewError):
        service.review_candidate(**values)

    with pytest.raises(ValueError, match="decision"):
        service.review_candidate(
            **{
                **values,
                "review_id": "SERVING-REVIEW-0002",
                "decision": "maybe",
            }
        )
