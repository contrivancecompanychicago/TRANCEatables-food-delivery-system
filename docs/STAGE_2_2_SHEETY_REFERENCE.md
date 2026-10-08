# Stage 2.2: read-only Sheety reference adapter

Stage 2.2 connects the cleaned **make DEEP Human Meals Services** workbook
to TRANCEatables through Sheety. It treats Sheety as curated reference data,
not as an operational database.

## Data flow

```text
Google Sheet -> Sheety (GET only) -> validation -> TRANCEatables services
                                                |
                                                +-> SQLite remains authoritative
                                                +-> Grist remains an audit mirror
```

The adapter reads three collections:

| Sheety endpoint | Purpose |
| --- | --- |
| `restaurants` | Restaurant and simulated pickup references |
| `groceryItems` | Curated grocery and nutrition reference rows |
| `mealReferences` | Experimental meal-constraint reference rows |

The `review` worksheet is excluded because it is documentation rather than
application data.

## Security boundary

- Bearer authentication is required.
- The adapter only constructs HTTP `GET` requests.
- It provides no POST, PUT, PATCH, or DELETE methods.
- Tokens are loaded from environment variables and must never be committed.
- Sheety cannot create an order, approve a mission, dispatch a robot, or update
  the authoritative SQLite database.
- Reference nutrition fields are source data, not medical advice or verified
  clinical recommendations.

Keep Sheety write methods disabled in its dashboard.

## Configuration

```bash
export SHEETY_BASE_URL="https://api.sheety.co/PROJECT_ID/PROJECT_NAME"
export SHEETY_BEARER_TOKEN="your-secret"
```

The base URL must use HTTPS and the `api.sheety.co` host. Do not add an
endpoint name to the base URL.

## Python usage

```python
from tranceatables.sheety_reference import SheetyReferenceClient

client = SheetyReferenceClient.from_environment()
snapshot = client.snapshot()

print("restaurants:", len(snapshot.restaurants))
print("grocery items:", len(snapshot.grocery_items))
print("meal references:", len(snapshot.meal_references))
```

## Google Colab usage

Store `SHEETY_BEARER_TOKEN` in Colab Secrets. Do not print it.

```python
from google.colab import userdata
import os

os.environ["SHEETY_BASE_URL"] = (
    "https://api.sheety.co/2038ea59d35e3cf806679a2706330dc9/"
    "makeDeepHumanMealsServicesStage22CleanedReview"
)
os.environ["SHEETY_BEARER_TOKEN"] = userdata.get("SHEETY_BEARER_TOKEN")

from tranceatables.sheety_reference import SheetyReferenceClient

snapshot = SheetyReferenceClient.from_environment().snapshot()
print("restaurants:", len(snapshot.restaurants))
print("groceryItems:", len(snapshot.grocery_items))
print("mealReferences:", len(snapshot.meal_references))
```

Validated initial counts were 0 restaurants, 94 grocery items, and 3 meal
references. Counts may change when the source sheet is deliberately updated.

## Current data limitation

The first three meal-reference rows have coefficient fields such as
`food1Amount`, but they do not yet identify the corresponding grocery items.
Before meal selection is implemented, add stable fields such as
`food1ItemId`, `food2ItemId`, and `food3ItemId`. Until then,
`mealReferences` must be treated as experimental constraint data only.
