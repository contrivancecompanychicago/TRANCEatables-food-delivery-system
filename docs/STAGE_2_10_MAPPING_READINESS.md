# Stage 2.10 — Controlled product-mapping readiness

## Goal

Resolve the effective, human-approved serving record for each of the three meal-plan food slots and produce an explicit readiness report. This stage evaluates readiness only; it does not assign products.

## Resolution rules

1. A `structurally_valid` candidate with an `approved` candidate review is effective.
2. A `mass_missing` candidate must retain its `correction_required` review.
3. That candidate becomes effective only through a separate revision with an `approved` revision review.
4. Each food slot must resolve to exactly one effective record.
5. Missing or ambiguous effective records are blockers.

For the validated dataset:

| Food slot | Effective record |
| --- | --- |
| 1 | Approved Orange Juice candidate |
| 2 | Approved Milk revision with 426 g |
| 3 | Approved Tomatoes candidate |

## Mapping blockers

Even when all serving records resolve, product assignment remains blocked while:

- target units remain `model_unit`;
- food quantity units remain `model_unit`;
- Magnesium-to-product compatibility is unvalidated; or
- no approved nutrient-to-product mapping artifact exists.

## Read-only boundary

The evaluator connects to SQLite with `mode=ro`. It cannot:

- update the meal plan;
- populate `food1_item_id`, `food2_item_id`, or `food3_item_id`;
- change the linked order;
- create or approve a robot mission;
- write to Grist or Sheety; or
- send a physical command.

## Python usage

```python
from tranceatables import evaluate_product_mapping_readiness

report = evaluate_product_mapping_readiness(
    "/content/tranceatables-demo.sqlite3",
    "SIM-MEAL-PLAN-0001",
)
print(report.serving_records_ready)
print(report.product_mapping_ready)
print(report.blockers)
```

Expected validated state:

- `serving_records_ready = True`
- `product_mapping_ready = False`
- meal-plan status remains `solved_unmapped`
- product IDs remain null
- order remains `draft`
