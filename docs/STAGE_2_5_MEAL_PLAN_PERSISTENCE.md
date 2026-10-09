# Stage 2.5: simulated meal-plan persistence

Stage 2.5 stores the validated Stage 2.4 abstract solution in SQLite and links it
to one draft simulated order.

## New SQLite tables

- `simulated_meal_plans` — one simulation-only plan per order
- `meal_plan_events` — append-only creation audit

The stored plan preserves:

- exact fractions and decimal quantities;
- nutrients, calculated targets, and zero residuals;
- `model_unit` for targets and quantities;
- `solved_unmapped` status;
- three nullable grocery item IDs.

## Safety and interpretation boundary

- Only a draft order may receive an abstract plan.
- Only a `solved_unmapped` solution with zero residuals is accepted.
- Grocery product IDs remain null.
- The plan is not a prescription, serving recommendation, or clinical target.
- Creating a plan does not transition the order.
- No robot mission or physical dispatch is created.
- Grist synchronization is intentionally deferred until dedicated destination
  tables are created and schema-checked.

## Google Colab

After pulling version 0.8.0 and restoring the Sheety environment variables:

```python
import os

from tranceatables import (
    SQLiteOrderRepository,
    solve_meal_references,
)
from tranceatables.meal_plan import (
    MealPlanNotFoundError,
    MealPlanService,
    SQLiteMealPlanRepository,
)
from tranceatables.sheety_reference import SheetyReferenceClient

database_path = os.environ.get(
    "TRANCEATABLES_DB_PATH",
    "/content/tranceatables-demo.sqlite3",
)

solution = solve_meal_references(
    SheetyReferenceClient.from_environment().get_meal_references()
)

orders = SQLiteOrderRepository(database_path)
plans = SQLiteMealPlanRepository(database_path)
service = MealPlanService(orders, plans)

try:
    plan = plans.get("SIM-MEAL-PLAN-0001")
    action = "EXISTING"
except MealPlanNotFoundError:
    plan = service.create_from_solution(
        "SIM-MEAL-PLAN-0001",
        "SIM-ORDER-0002",
        solution,
        actor="colab-simulation",
    )
    action = "CREATED"

order = orders.get("SIM-ORDER-0002")

print(action, plan.meal_plan_id)
print("Order:", plan.order_id)
print("Order status:", order.status.value)
print("Exact quantities:", plan.exact_food_quantities)
print("Residuals:", plan.target_residuals)
print("Units:", plan.target_unit, plan.food_quantity_unit)
print("Status:", plan.status)
print("Product IDs:", plan.food_item_ids)
print("Simulation only:", plan.simulation_only)
print("Robot mission created:", False)
print("Physical dispatch:", False)
```

Expected first-run output:

```text
CREATED SIM-MEAL-PLAN-0001
Order: SIM-ORDER-0002
Order status: draft
Exact quantities: ('50/11', '50/33', '40/33')
Residuals: (0.0, 0.0, 0.0)
Units: model_unit model_unit
Status: solved_unmapped
Product IDs: (None, None, None)
Simulation only: True
Robot mission created: False
Physical dispatch: False
```

A rerun reports `EXISTING` and does not create a duplicate event.
