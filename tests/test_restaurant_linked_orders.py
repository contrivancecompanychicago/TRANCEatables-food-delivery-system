import json
import sqlite3

import pytest

from tranceatables import (
    DeliveryRequest,
    OrderService,
    OrderStatus,
    SQLiteOrderRepository,
)
from tranceatables.sheety_reference import (
    SheetyReferenceClient,
    SheetyReferenceError,
)


BASE_URL = "https://api.sheety.co/project/name"


def restaurant_transport(records):
    def transport(request, timeout):
        return 200, json.dumps({"restaurants": records}).encode()

    return transport


def test_resolves_active_restaurant_and_persists_order_link(tmp_path):
    client = SheetyReferenceClient(
        BASE_URL,
        "secret",
        transport=restaurant_transport(
            [
                {
                    "restaurantId": "SIM-RESTAURANT-001",
                    "restaurantName": "TRANCEatables Simulation Kitchen",
                    "pickupZone": "SIM_RESTAURANT_KITCHEN_001",
                    "active": True,
                    "source": "internal_simulation",
                    "id": 2,
                }
            ]
        ),
    )
    restaurant = client.get_active_restaurant("SIM-RESTAURANT-001")

    service = OrderService(SQLiteOrderRepository(tmp_path / "orders.sqlite3"))
    created = service.create_order(
        DeliveryRequest(
            order_id="SIM-ORDER-0002",
            distance_km=2.0,
            payload_kg=2.0,
            restaurant_id=restaurant.restaurant_id,
            pickup_zone=restaurant.pickup_zone,
        ),
        actor="colab-simulation",
    )

    reopened = OrderService(
        SQLiteOrderRepository(tmp_path / "orders.sqlite3")
    ).get_order(created.order_id)
    assert reopened.status is OrderStatus.DRAFT
    assert reopened.request.restaurant_id == "SIM-RESTAURANT-001"
    assert reopened.request.pickup_zone == "SIM_RESTAURANT_KITCHEN_001"
    assert restaurant.sheety_row_id == 2


def test_rejects_partial_restaurant_link(tmp_path):
    service = OrderService(SQLiteOrderRepository(tmp_path / "orders.sqlite3"))
    with pytest.raises(ValueError, match="supplied together"):
        service.create_order(
            DeliveryRequest(
                "SIM-ORDER-BAD",
                1.0,
                1.0,
                restaurant_id="SIM-RESTAURANT-001",
            )
        )


def test_rejects_inactive_restaurant():
    client = SheetyReferenceClient(
        BASE_URL,
        "secret",
        transport=restaurant_transport(
            [
                {
                    "restaurantId": "SIM-RESTAURANT-001",
                    "restaurantName": "TRANCEatables Simulation Kitchen",
                    "pickupZone": "SIM_RESTAURANT_KITCHEN_001",
                    "active": False,
                    "source": "internal_simulation",
                    "id": 2,
                }
            ]
        ),
    )
    with pytest.raises(SheetyReferenceError, match="not active"):
        client.get_active_restaurant("SIM-RESTAURANT-001")


def test_migrates_legacy_orders_without_losing_rows(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            distance_km REAL NOT NULL,
            payload_kg REAL NOT NULL,
            handling TEXT NOT NULL,
            packaging_verified INTEGER NOT NULL,
            customer_handoff_required INTEGER NOT NULL,
            status TEXT NOT NULL,
            version INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT INTO orders VALUES
            ('SIM-ORDER-0001', 1.0, 1.0, 'ambient', 0, 1,
             'draft', 0, '2026-10-08T00:00:00+00:00',
             '2026-10-08T00:00:00+00:00')"""
        )

    repository = SQLiteOrderRepository(database)
    migrated = repository.get("SIM-ORDER-0001")

    assert migrated.request.restaurant_id is None
    assert migrated.request.pickup_zone is None
    with sqlite3.connect(database) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(orders)")
        }
        count = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    assert {"restaurant_id", "pickup_zone"} <= columns
    assert count == 1
