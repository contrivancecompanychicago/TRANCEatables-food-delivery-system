# Stage 2.9 — Immutable serving-candidate correction

Stage 2.9 preserves the original `mass_missing` candidate and creates a separately reviewed correction record. A revision is eligible only when the original candidate has a `correction_required` human decision.

For the validated Milk correction:

- original candidate: `SERVING-CANDIDATE-0002`
- revision: `SERVING-REVISION-0001`
- Sheety row: `49`
- UPC: `74336863950`
- volume: `414 ml`
- verified mass: `426 g`

The original candidate remains unchanged. Approval of the revision does not assign a product, map nutrient units, advance an order, create a mission, or dispatch a robot.

## Colab

Update the repository, install version 0.12.0, run tests, and restart the runtime.

```python
from pathlib import Path
from tranceatables import (
    ServingRevisionService,
    SQLiteServingCandidateRepository,
    SQLiteServingRevisionRepository,
)

database = Path("/content/tranceatables-demo.sqlite3")
candidates = SQLiteServingCandidateRepository(database)
revisions = SQLiteServingRevisionRepository(database)
service = ServingRevisionService(candidates, revisions)
```

Create the immutable correction:

```python
revision = service.create_revision(
    revision_id="SERVING-REVISION-0001",
    original_candidate_id="SERVING-CANDIDATE-0002",
    serving_weight_grams=426.0,
    provenance=(
        "Sheety groceryItems row 49 read-back verified "
        "2026-10-10; UPC 74336863950"
    ),
    created_by="colab-human-operator",
)
```

Review the correction separately:

```python
review = service.review_revision(
    review_id="SERVING-REVISION-REVIEW-0001",
    revision_id="SERVING-REVISION-0001",
    decision="approved",
    reviewer="colab-human-operator",
    notes="Corrected gram weight and provenance reviewed.",
)
```

Verify:

```python
original = candidates.get("SERVING-CANDIDATE-0002")
revision = revisions.get("SERVING-REVISION-0001")
review = revisions.get_review(revision.revision_id)

print("Original mass:", original.serving_weight_grams)
print("Revision mass:", revision.serving_weight_grams)
print("Provenance:", revision.provenance)
print("Decision:", review.decision)
print("Meal plan mapped:", False)
print("Order advanced:", False)
print("Robot mission created:", False)
print("Physical dispatch:", False)
```

Expected: original mass remains `None`, revision mass is `426.0`, and the revision decision is `approved`.
