import sqlite3

from tranceatables.grist_sync import TABLE_MAPPINGS, _source_rows


def test_meal_plan_mapping_matches_confirmed_grist_schema():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE simulated_meal_plans (
        meal_plan_id TEXT, order_id TEXT, nutrients_json TEXT,
        exact_quantities_json TEXT, quantities_json TEXT,
        calculated_targets_json TEXT, residuals_json TEXT,
        target_unit TEXT, quantity_unit TEXT, status TEXT,
        food1_item_id TEXT, food2_item_id TEXT, food3_item_id TEXT,
        created_at TEXT, updated_at TEXT, simulation_only INTEGER
        )"""
    )
    connection.execute(
        """INSERT INTO simulated_meal_plans VALUES (
        'SIM-MEAL-PLAN-0001', 'SIM-ORDER-0002',
        '["Vitamin C", "Calcium", "Magnesium"]',
        '["50/11", "50/33", "40/33"]',
        '[4.545454545454546, 1.5151515151515151, 1.2121212121212122]',
        '[100.0, 300.0, 200.0]', '[0.0, 0.0, 0.0]',
        'model_unit', 'model_unit', 'solved_unmapped',
        NULL, NULL, NULL,
        '2026-10-09T19:00:00+00:00',
        '2026-10-09T19:00:00+00:00', 1
        )"""
    )
    mapping = next(
        item for item in TABLE_MAPPINGS
        if item.grist_table == "SimulatedMealPlans"
    )

    row = _source_rows(connection, mapping)[0]

    assert set(row) == {
        "MealPlanId", "OrderId", "Nutrients",
        "Food1Exact", "Food2Exact", "Food3Exact",
        "Food1Quantity", "Food2Quantity", "Food3Quantity",
        "CalculatedTargets", "Residuals", "TargetUnit",
        "QuantityUnit", "Status", "Food1ItemId", "Food2ItemId",
        "Food3ItemId", "CreatedAt", "UpdatedAt", "SimulationOnly",
    }
    assert row["Food1Exact"] == "50/11"
    assert row["Food1Quantity"] == 4.545454545454546
    assert row["Food1ItemId"] is None
    assert row["SimulationOnly"] is True


def test_meal_plan_event_mapping_matches_confirmed_grist_schema():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE meal_plan_events (
        event_id INTEGER, meal_plan_id TEXT, event_type TEXT,
        actor TEXT, message TEXT, occurred_at TEXT
        )"""
    )
    connection.execute(
        """INSERT INTO meal_plan_events VALUES (
        1, 'SIM-MEAL-PLAN-0001', 'meal_plan_created',
        'colab-simulation', 'abstract model solution persisted',
        '2026-10-09T19:00:00+00:00'
        )"""
    )
    mapping = next(
        item for item in TABLE_MAPPINGS
        if item.grist_table == "MealPlanEvents"
    )

    row = _source_rows(connection, mapping)[0]

    assert set(row) == {
        "EventId", "MealPlanId", "EventType",
        "Actor", "Message", "OccurredAt",
    }
    assert row["EventId"] == "MEAL-PLAN-EVENT-1"
    assert row["EventType"] == "meal_plan_created"
