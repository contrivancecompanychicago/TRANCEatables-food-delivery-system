import json
import sqlite3

from tranceatables.mapping_readiness import (
    evaluate_product_mapping_readiness,
)


def build_database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE simulated_meal_plans (
                meal_plan_id TEXT PRIMARY KEY,
                order_id TEXT,
                nutrients_json TEXT,
                exact_quantities_json TEXT,
                quantities_json TEXT,
                calculated_targets_json TEXT,
                residuals_json TEXT,
                target_unit TEXT,
                quantity_unit TEXT,
                status TEXT,
                food1_item_id TEXT,
                food2_item_id TEXT,
                food3_item_id TEXT,
                created_at TEXT,
                updated_at TEXT,
                simulation_only INTEGER
            );
            CREATE TABLE food_serving_candidates (
                candidate_id TEXT PRIMARY KEY,
                meal_plan_id TEXT,
                food_slot INTEGER,
                source TEXT,
                source_item_id TEXT,
                source_upc TEXT,
                brand_name TEXT,
                item_name TEXT,
                serving_quantity REAL,
                serving_unit_label TEXT,
                serving_weight_grams REAL,
                metric_quantity REAL,
                metric_unit TEXT,
                ontology_source TEXT,
                review_status TEXT,
                created_at TEXT,
                updated_at TEXT,
                simulation_only INTEGER
            );
            CREATE TABLE serving_candidate_reviews (
                review_id TEXT PRIMARY KEY,
                candidate_id TEXT,
                decision TEXT,
                reviewer TEXT,
                notes TEXT,
                decided_at TEXT,
                simulation_only INTEGER
            );
            CREATE TABLE serving_candidate_revisions (
                revision_id TEXT PRIMARY KEY,
                original_candidate_id TEXT,
                source_item_id TEXT,
                serving_quantity REAL,
                serving_unit_label TEXT,
                serving_weight_grams REAL,
                metric_quantity REAL,
                metric_unit TEXT,
                provenance TEXT,
                created_by TEXT,
                created_at TEXT,
                simulation_only INTEGER
            );
            CREATE TABLE serving_revision_reviews (
                review_id TEXT PRIMARY KEY,
                revision_id TEXT,
                decision TEXT,
                reviewer TEXT,
                notes TEXT,
                decided_at TEXT,
                simulation_only INTEGER
            );
            """
        )
        connection.execute(
            """INSERT INTO simulated_meal_plans VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "MP-1",
                "O-1",
                json.dumps(["Vitamin C", "Calcium", "Magnesium"]),
                "[]",
                "[]",
                "[]",
                "[]",
                "model_unit",
                "model_unit",
                "solved_unmapped",
                None,
                None,
                None,
                "2026-10-12T12:00:00+00:00",
                "2026-10-12T12:00:00+00:00",
                1,
            ),
        )

        candidates = [
            (
                "C-1", "MP-1", 1, "sheety", "ITEM-1", "111",
                "Brand", "Orange Juice", 8.0, "fl oz", 226.0,
                226.0, "g", "internal", "structurally_valid",
                "t", "t", 1,
            ),
            (
                "C-2", "MP-1", 2, "sheety", "ITEM-2", "222",
                "Brand", "Milk", 1.74, "cups", None,
                414.0, "ml", "internal", "mass_missing",
                "t", "t", 1,
            ),
            (
                "C-3", "MP-1", 3, "sheety", "ITEM-3", "333",
                "Brand", "Tomatoes", 0.5, "cup", 117.0,
                117.0, "g", "internal", "structurally_valid",
                "t", "t", 1,
            ),
        ]
        connection.executemany(
            """INSERT INTO food_serving_candidates VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            candidates,
        )
        connection.executemany(
            """INSERT INTO serving_candidate_reviews VALUES
            (?, ?, ?, ?, ?, ?, ?)""",
            [
                ("CR-1", "C-1", "approved", "operator", "ok", "t", 1),
                (
                    "CR-2", "C-2", "correction_required",
                    "operator", "mass", "t", 1,
                ),
                ("CR-3", "C-3", "approved", "operator", "ok", "t", 1),
            ],
        )
        connection.execute(
            """INSERT INTO serving_candidate_revisions VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "R-1", "C-2", "ITEM-2", 1.74, "cups", 426.0,
                414.0, "ml", "corrected_sheety_row", "operator", "t", 1,
            ),
        )
        connection.execute(
            """INSERT INTO serving_revision_reviews VALUES
            (?, ?, ?, ?, ?, ?, ?)""",
            ("RR-1", "R-1", "approved", "operator", "ok", "t", 1),
        )


def test_resolves_originals_and_approved_revision_without_mapping(tmp_path):
    database = tmp_path / "test.sqlite3"
    build_database(database)

    report = evaluate_product_mapping_readiness(database, "MP-1")

    assert report.serving_records_ready is True
    assert report.product_mapping_ready is False
    assert [record.food_slot for record in report.effective_records] == [1, 2, 3]
    assert report.effective_records[0].revision_id is None
    assert report.effective_records[1].revision_id == "R-1"
    assert report.effective_records[1].serving_weight_grams == 426.0
    assert report.effective_records[1].approval_source == "revision_review"
    assert report.food_item_ids == (None, None, None)
    assert "target_unit_is_unmapped_model_unit" in report.blockers
    assert "magnesium_product_mapping_is_unvalidated" in report.blockers
    assert "nutrient_product_mapping_not_validated" in report.blockers


def test_missing_revision_approval_blocks_serving_readiness(tmp_path):
    database = tmp_path / "test.sqlite3"
    build_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM serving_revision_reviews")

    report = evaluate_product_mapping_readiness(database, "MP-1")

    assert report.serving_records_ready is False
    assert report.product_mapping_ready is False
    assert "food_slot_2_has_no_approved_record" in report.blockers


def test_evaluation_is_read_only(tmp_path):
    database = tmp_path / "test.sqlite3"
    build_database(database)
    with sqlite3.connect(database) as connection:
        before = connection.total_changes
        counts_before = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "simulated_meal_plans",
                "food_serving_candidates",
                "serving_candidate_reviews",
                "serving_candidate_revisions",
                "serving_revision_reviews",
            )
        )

    evaluate_product_mapping_readiness(database, "MP-1")

    with sqlite3.connect(database) as connection:
        counts_after = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "simulated_meal_plans",
                "food_serving_candidates",
                "serving_candidate_reviews",
                "serving_candidate_revisions",
                "serving_revision_reviews",
            )
        )
    assert before == 0
    assert counts_after == counts_before
