# Stage 2.3: restaurant-linked simulated orders

Stage 2.3 stores the stable restaurant identifier and simulated pickup zone on
an order while preserving the Stage 2.2 read-only Sheety boundary.

## Data flow

```text
Sheety Restaurants (GET only)
        -> validate active restaurant
        -> create draft order in SQLite
        -> mirror RestaurantId to Grist
```

Sheety remains reference data. SQLite remains authoritative. Grist remains an
audit mirror. This stage does not create a robot mission or dispatch anything.

## Migration

Opening an existing database with `SQLiteOrderRepository` adds these nullable
columns when they are absent:

- `orders.restaurant_id`
- `orders.pickup_zone`

Existing orders are preserved and receive `NULL` for both values. New linked
orders must provide both values together.

## Google Colab: create SIM-ORDER-0002

Pull and reinstall the current repository first:

```python
%cd /content/TRANCEatables-food-delivery-system
!git pull
!pip install -e ".[dev]"
!pytest -q
```

Then run this cell. It reads the restaurant through authenticated Sheety and
creates a draft SQLite order. It is safe to rerun because it reuses an existing
order rather than inserting a duplicate.

```python
from google.colab import userdata
import os

from tranceatables import (
    DeliveryRequest,
    OrderNotFoundError,
    OrderService,
    SQLiteOrderRepository,
)
from tranceatables.sheety_reference import SheetyReferenceClient

os.environ["SHEETY_BASE_URL"] = (
    "https://api.sheety.co/2038ea59d35e3cf806679a2706330dc9/"
    "makeDeepHumanMealsServicesStage22CleanedReview"
)
os.environ["SHEETY_BEARER_TOKEN"] = userdata.get("SHEETY_BEARER_TOKEN")

database_path = os.environ.get(
    "TRANCEATABLES_DB_PATH",
    "/content/tranceatables-demo.sqlite3",
)

restaurant = (
    SheetyReferenceClient.from_environment()
    .get_active_restaurant("SIM-RESTAURANT-001")
)

service = OrderService(SQLiteOrderRepository(database_path))

try:
    order = service.get_order("SIM-ORDER-0002")
    action = "EXISTING"
except OrderNotFoundError:
    order = service.create_order(
        DeliveryRequest(
            order_id="SIM-ORDER-0002",
            distance_km=2.0,
            payload_kg=2.0,
            restaurant_id=restaurant.restaurant_id,
            pickup_zone=restaurant.pickup_zone,
        ),
        actor="colab-simulation",
    )
    action = "CREATED"

print(action, order.order_id)
print("Status:", order.status.value)
print("Restaurant:", order.request.restaurant_id)
print("Pickup zone:", order.request.pickup_zone)
print("Robot mission created:", False)
print("Physical dispatch:", False)
```

Expected output:

```text
CREATED SIM-ORDER-0002
Status: draft
Restaurant: SIM-RESTAURANT-001
Pickup zone: SIM_RESTAURANT_KITCHEN_001
Robot mission created: False
Physical dispatch: False
```

## Grist sync

The existing Stage 2.1 sync now includes `RestaurantId` in the Orders mapping.
The current Grist Orders table already contains this column. The authoritative
pickup zone stays in SQLite; a future mission copies it deliberately when a
human-approved simulation mission is planned.

Run a dry-run before applying:

```bash
python -m tranceatables.grist_sync --database "$TRANCEATABLES_DB_PATH"
python -m tranceatables.grist_sync --database "$TRANCEATABLES_DB_PATH" --apply
```

## Safety boundary

- Only an active, uniquely identified restaurant is accepted.
- Sheety's numeric `id` is not stored as the business identifier.
- No customer name, address, health information, or payment data is required.
- No robot mission is created or dispatched by this workflow.
