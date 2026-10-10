# Stage 2.8 — Human serving-candidate review

Stage 2.8 records one immutable human decision for each Stage 2.7 serving candidate.

Decisions are:

- `approved` — allowed only when the candidate is `structurally_valid`
- `correction_required` — records missing or questionable information for later correction
- `rejected` — excludes the candidate from later mapping work

A decision is stored in `serving_candidate_reviews` and also appends a `candidate_reviewed` event. The original candidate record is preserved.

## Safety boundary

Approval means only that a human reviewed the candidate's serving structure. It does not:

- validate clinical suitability or nutrition claims;
- convert percent Daily Value into the solver's `model_unit`;
- assign a grocery product to a meal plan;
- advance an order;
- create a robot mission; or
- dispatch physical hardware.

A `mass_missing` candidate cannot be approved. It may be marked `correction_required` or `rejected`.

## Colab setup

After pulling and installing version 0.11.0:

```python
from pathlib import Path

from tranceatables import (
    ServingCandidateService,
    SQLiteMealPlanRepository,
    SQLiteServingCandidateRepository,
)

database = Path("/content/tranceatables-demo.sqlite3")
meal_plans = SQLiteMealPlanRepository(database)
candidates = SQLiteServingCandidateRepository(database)
service = ServingCandidateService(meal_plans, candidates)
```

## Review the three validated candidates

Approve Orange Juice:

```python
orange_review = service.review_candidate(
    review_id="SERVING-REVIEW-0001",
    candidate_id="SERVING-CANDIDATE-0001",
    decision="approved",
    reviewer="colab-human-operator",
    notes="Serving quantity, unit label, and gram weight reviewed.",
)
```

Require correction for Milk because the gram weight is absent:

```python
milk_review = service.review_candidate(
    review_id="SERVING-REVIEW-0002",
    candidate_id="SERVING-CANDIDATE-0002",
    decision="correction_required",
    reviewer="colab-human-operator",
    notes="Verified serving weight in grams is required before approval.",
)
```

Approve Stewed Tomatoes:

```python
tomato_review = service.review_candidate(
    review_id="SERVING-REVIEW-0003",
    candidate_id="SERVING-CANDIDATE-0003",
    decision="approved",
    reviewer="colab-human-operator",
    notes="Serving quantity, unit label, and gram weight reviewed.",
)
```

Do not rerun a decision cell after it succeeds. Reviews are intentionally immutable, and a second decision for the same candidate is rejected.

## Verify

```python
for candidate in candidates.list_for_plan("SIM-MEAL-PLAN-0001"):
    review = candidates.get_review(candidate.candidate_id)
    print(
        candidate.candidate_id,
        candidate.review_status,
        review.decision if review else "pending",
    )

plan = meal_plans.get("SIM-MEAL-PLAN-0001")
print("Meal-plan status:", plan.status)
print("Assigned product IDs:", plan.food_item_ids)
print("Order advanced:", False)
print("Robot mission created:", False)
print("Physical dispatch:", False)
```

Expected decisions are `approved`, `correction_required`, and `approved`. The meal plan must remain `solved_unmapped` with all product IDs null.
