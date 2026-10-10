# Stage 2.7 — Serving-candidate review persistence

Stage 2.7 records normalized grocery serving candidates in authoritative SQLite so a human can review them later. It preserves serving quantity, unit label, optional gram weight, metric quantity/unit, provenance, and an append-only audit event.

This stage is **review persistence only**. It does not validate nutrition claims, convert percent Daily Value into solver units, assign a grocery item to a meal plan, advance an order, create a robot mission, or dispatch hardware.

## Why this stage exists

The Stage 2.4 solver still uses abstract `model_unit` values. The Sheety grocery reference data uses serving descriptions and selected nutrients expressed as label values such as percent Daily Value. Magnesium is absent from the current reference rows. Those values are not automatically interchangeable.

Stage 2.7 therefore creates a review queue instead of making an unsafe mapping.

## SQLite tables

Opening `SQLiteServingCandidateRepository` creates:

- `food_serving_candidates` — one normalized candidate record per meal plan, food slot, and source item
- `food_serving_candidate_events` — append-only creation audit records

A candidate must reference an existing simulation-only meal plan whose status is `solved_unmapped`. The plan must not already have assigned food item IDs.

Review statuses:

- `structurally_valid` — serving quantity, unit, and gram weight are present
- `mass_missing` — a useful volume or count record exists, but gram weight is absent
- `rejected` — reserved for a later human-review transition; Stage 2.7 does not set it automatically

## Google Colab setup

After cloning or updating the repository:

```python
%cd /content/TRANCEatables-food-delivery-system
!git pull --ff-only
!python -m pip install -e '.[dev]'
!python -m pytest -q
```

Select the recovered authoritative database:

```python
import os

os.environ["TRANCEATABLES_DB_PATH"] = (
    "/content/tranceatables-demo.sqlite3"
)
```

Create the repository and service:

```python
import os
from tranceatables import (
    ServingCandidateInput,
    ServingCandidateService,
    SQLiteMealPlanRepository,
    SQLiteServingCandidateRepository,
)

database = os.environ["TRANCEATABLES_DB_PATH"]
meal_plans = SQLiteMealPlanRepository(database)
candidates = SQLiteServingCandidateRepository(database)
service = ServingCandidateService(meal_plans, candidates)
```

## Record the reviewed examples

Orange Juice has a complete mass record:

```python
orange_juice = service.create_candidate(
    ServingCandidateInput(
        candidate_id="SERVING-CANDIDATE-0001",
        meal_plan_id="SIM-MEAL-PLAN-0001",
        food_slot=1,
        source="sheety",
        source_item_id="51c3d56997c3e6d8d3b53524",
        source_upc="41268111268",
        brand_name="Hannaford",
        item_name="Orange Juice",
        serving_quantity=8,
        serving_unit_label="fl oz",
        serving_weight_grams=226,
        metric_quantity=226,
        metric_unit="g",
    ),
    actor="colab-human-review",
)
print(orange_juice.review_status)
```

The milk row is retained for review even though its gram weight is missing:

```python
milk = service.create_candidate(
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
        metric_quantity=414,
        metric_unit="ml",
    ),
    actor="colab-human-review",
)
print(milk.review_status)
```

Stewed Tomatoes has a complete mass record:

```python
tomatoes = service.create_candidate(
    ServingCandidateInput(
        candidate_id="SERVING-CANDIDATE-0003",
        meal_plan_id="SIM-MEAL-PLAN-0001",
        food_slot=3,
        source="sheety",
        source_item_id="51c3e9f397c3e6de73cb9a63",
        source_upc="70253267345",
        brand_name="Our Family",
        item_name="Tomatoes, Stewed Italian",
        serving_quantity=0.5,
        serving_unit_label="cup",
        serving_weight_grams=117,
        metric_quantity=117,
        metric_unit="g",
    ),
    actor="colab-human-review",
)
print(tomatoes.review_status)
```

Do not rerun these creation calls with new candidate IDs for the same meal plan, food slot, and source item. The database uniqueness rule intentionally rejects that duplicate mapping.

## Verify the safety boundary

```python
plan = meal_plans.get("SIM-MEAL-PLAN-0001")
saved = candidates.list_for_plan(plan.meal_plan_id)

print("Candidate count:", len(saved))
for candidate in saved:
    print(
        candidate.food_slot,
        candidate.item_name,
        candidate.review_status,
    )

print("Meal-plan status:", plan.status)
print("Assigned product IDs:", plan.food_item_ids)
print("Robot mission created:", False)
print("Physical dispatch:", False)
```

Expected meal-plan state remains:

```text
Meal-plan status: solved_unmapped
Assigned product IDs: (None, None, None)
Robot mission created: False
Physical dispatch: False
```

## Recovery and persistence

Back up the SQLite file after verification. Use SQLite's backup API rather than copying an open database. If Google Drive reports `OSError: [Errno 5] Input/output error`, stop and download the local backup through the Colab Files pane; do not treat an inaccessible Drive path as authoritative.

## Deferred work

A later stage may add:

- explicit human accept/reject decisions;
- a documented nutrient ontology and unit conversions;
- Edamam Food Database enrichment when the correct API product is authorized;
- product assignment to a meal plan after nutrition and serving validation;
- optional Grist tables for the serving-candidate review queue.

None of those deferred features should bypass human review or the simulation-only boundary.
