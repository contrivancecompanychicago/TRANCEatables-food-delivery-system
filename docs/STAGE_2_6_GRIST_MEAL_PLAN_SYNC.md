# Stage 2.6: Grist meal-plan audit mirror

Stage 2.6 extends the existing one-way SQLite-to-Grist synchronization with the
Stage 2.5 simulated meal plan and its append-only event.

## Destination tables

### SimulatedMealPlans

Stable key: `MealPlanId`

The mapping includes the linked order, nutrient names, exact and decimal food
slot quantities, calculated targets, residuals, units, status, nullable product
IDs, timestamps, and the simulation-only flag.

### MealPlanEvents

Stable key: `EventId`, generated as
`MEAL-PLAN-EVENT-<SQLite event_id>`.

## Authority and safety

- SQLite remains authoritative.
- Grist is a dashboard and audit mirror.
- Dry-run remains the default.
- Writes require the explicit `--apply` flag.
- Schema preflight checks every mapped destination before any write.
- No reverse Grist-to-SQLite synchronization exists.
- No order transition, grocery assignment, mission creation, or robot dispatch
  can be triggered by this sync.

## Google Colab

Pull and install version 0.9.0:

```python
%cd /content/TRANCEatables-food-delivery-system
!git pull
!pip install -e ".[dev]"
!pytest -q
```

Restore `GRIST_BASE_URL`, `GRIST_DOC_ID`, `GRIST_API_KEY`, and
`TRANCEATABLES_DB_PATH`, then run the dry-run:

```python
!python -m tranceatables.grist_sync \
    --database "$TRANCEATABLES_DB_PATH"
```

For a database containing one plan and one plan event, the new mappings should
initially report:

```text
DRY-RUN SimulatedMealPlans: source=1 create=1 update=0 unchanged=0
DRY-RUN MealPlanEvents: source=1 create=1 update=0 unchanged=0
```

Review every table summary before applying:

```python
!python -m tranceatables.grist_sync \
    --database "$TRANCEATABLES_DB_PATH" \
    --apply
```

Then run one final dry-run. The new mappings should report:

```text
DRY-RUN SimulatedMealPlans: source=1 create=0 update=0 unchanged=1
DRY-RUN MealPlanEvents: source=1 create=0 update=0 unchanged=1
```

All pre-existing tables should also report zero creates and zero updates.
