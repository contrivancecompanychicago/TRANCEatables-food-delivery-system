from datetime import datetime, timezone

import pytest

from tranceatables import DeliveryRequest, OrderService, SQLiteOrderRepository
from tranceatables.meal_plan import MealPlanService, SQLiteMealPlanRepository
from tranceatables.nutrient_solver import solve_meal_references
from tranceatables.serving_candidate import (
    ServingCandidateEligibilityError,
    ServingCandidateInput,
    ServingCandidateService,
    SQLiteServingCandidateRepository,
)
from tranceatables.serving_revision import (
    DuplicateServingRevisionError,
    ServingRevisionService,
    SQLiteServingRevisionRepository,
)


REFERENCES = [
    {"nutrient": "Vitamin C", "food1Amount": 10, "food2Amount": 20,
     "food3Amount": 20, "targetAmount": 100},
    {"nutrient": "Calcium", "food1Amount": 50, "food2Amount": 40,
     "food3Amount": 10, "targetAmount": 300},
    {"nutrient": "Magnesium", "food1Amount": 30, "food2Amount": 10,
     "food3Amount": 40, "targetAmount": 200},
]


def clock():
    return datetime(2026, 10, 10, 22, 0, tzinfo=timezone.utc)


def setup(tmp_path):
    database = tmp_path / "revision.sqlite3"
    orders = SQLiteOrderRepository(database)
    OrderService(orders).create_order(
        DeliveryRequest(
            "SIM-ORDER-0002", 2.0, 2.0,
            restaurant_id="SIM-RESTAURANT-001",
            pickup_zone="SIM_RESTAURANT_KITCHEN_001",
        )
    )
    plans = SQLiteMealPlanRepository(database)
    MealPlanService(orders, plans, clock=clock).create_from_solution(
        "SIM-MEAL-PLAN-0001", "SIM-ORDER-0002",
        solve_meal_references(REFERENCES),
    )
    candidates = SQLiteServingCandidateRepository(database)
    candidate_service = ServingCandidateService(plans, candidates, clock=clock)
    candidate_service.create_candidate(
        ServingCandidateInput(
            candidate_id="SERVING-CANDIDATE-0002",
            meal_plan_id="SIM-MEAL-PLAN-0001",
            food_slot=2,
            source="sheety",
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
    candidate_service.review_candidate(
        review_id="SERVING-REVIEW-0002",
        candidate_id="SERVING-CANDIDATE-0002",
        decision="correction_required",
        reviewer="colab-human-operator",
        notes="Verified gram weight required.",
    )
    revisions = SQLiteServingRevisionRepository(database)
    service = ServingRevisionService(candidates, revisions, clock=clock)
    return service, revisions, candidates, plans, orders


def test_creates_and_approves_immutable_revision(tmp_path):
    service, revisions, candidates, plans, orders = setup(tmp_path)

    revision = service.create_revision(
        revision_id="SERVING-REVISION-0001",
        original_candidate_id="SERVING-CANDIDATE-0002",
        serving_weight_grams=426.0,
        provenance="Sheety row 49 verified 2026-10-10",
        created_by="colab-human-operator",
    )
    review = service.review_revision(
        review_id="SERVING-REVISION-REVIEW-0001",
        revision_id=revision.revision_id,
        decision="approved",
        reviewer="colab-human-operator",
        notes="Corrected gram weight and provenance reviewed.",
    )

    assert revision.serving_weight_grams == 426.0
    assert revision.metric_quantity == 414.0
    assert review.decision == "approved"
    assert revisions.get_review(revision.revision_id) == review
    assert candidates.get("SERVING-CANDIDATE-0002").serving_weight_grams is None
    assert candidates.get_review("SERVING-CANDIDATE-0002").decision == (
        "correction_required"
    )
    assert plans.get("SIM-MEAL-PLAN-0001").food_item_ids == (None, None, None)
    assert plans.get("SIM-MEAL-PLAN-0001").status == "solved_unmapped"
    assert orders.get("SIM-ORDER-0002").status.value == "draft"

    event_types = [
        event.event_type
        for event in candidates.events("SERVING-CANDIDATE-0002")
    ]
    assert event_types[-2:] == [
        "candidate_revision_created",
        "candidate_revision_reviewed",
    ]


def test_requires_correction_review_and_positive_weight(tmp_path):
    service, _, candidates, _, _ = setup(tmp_path)

    with pytest.raises(ValueError, match="positive"):
        service.create_revision(
            revision_id="SERVING-REVISION-0001",
            original_candidate_id="SERVING-CANDIDATE-0002",
            serving_weight_grams=0,
            provenance="Sheety",
            created_by="operator",
        )

    with candidates._connect() as connection:
        connection.execute(
            "DELETE FROM serving_candidate_reviews WHERE candidate_id = ?",
            ("SERVING-CANDIDATE-0002",),
        )
    with pytest.raises(ServingCandidateEligibilityError, match="correction_required"):
        service.create_revision(
            revision_id="SERVING-REVISION-0001",
            original_candidate_id="SERVING-CANDIDATE-0002",
            serving_weight_grams=426,
            provenance="Sheety",
            created_by="operator",
        )


def test_rejects_second_revision_for_same_original(tmp_path):
    service, _, _, _, _ = setup(tmp_path)
    values = {
        "original_candidate_id": "SERVING-CANDIDATE-0002",
        "serving_weight_grams": 426.0,
        "provenance": "Sheety row 49",
        "created_by": "operator",
    }
    service.create_revision(revision_id="SERVING-REVISION-0001", **values)

    with pytest.raises(DuplicateServingRevisionError):
        service.create_revision(revision_id="SERVING-REVISION-0002", **values)
