from datetime import datetime, timezone
import sqlite3

import pytest

from tranceatables.product_identity import (
    ProductIdentityError,
    ProductIdentityService,
    SQLiteProductIdentityRepository,
)


NOW = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)


def setup_database(path):
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE food_serving_candidates (
                candidate_id TEXT PRIMARY KEY,
                source_item_id TEXT NOT NULL,
                source_upc TEXT,
                brand_name TEXT NOT NULL,
                item_name TEXT NOT NULL
            )"""
        )
        connection.executemany(
            "INSERT INTO food_serving_candidates VALUES (?, ?, ?, ?, ?)",
            [
                ("C-1", "ITEM-1", "111", "Brand A", "Orange Juice"),
                ("C-2", "WRONG", "222", "Brand B", "Tomatoes"),
            ],
        )


def service(path):
    setup_database(path)
    repository = SQLiteProductIdentityRepository(path)
    return ProductIdentityService(repository, clock=lambda: NOW), repository


def test_verified_identity_can_be_approved(tmp_path):
    api, repository = service(tmp_path / "db.sqlite3")
    verification = api.verify(
        verification_id="V-1",
        candidate_id="C-1",
        source_system="sheety",
        verified_item_id="ITEM-1",
        verified_upc="111",
        verified_brand_name="Brand A",
        verified_item_name="Orange Juice",
        evidence={"sheety_row_id": 1},
    )
    assert verification.status == "identity_verified"

    review = api.review(
        review_id="RV-1",
        verification_id="V-1",
        decision="approved",
        reviewer="operator",
        notes="identity matches",
    )
    assert review.decision == "approved"
    assert repository.candidate("C-1")["source_item_id"] == "ITEM-1"


def test_mismatch_requires_separate_correction_and_review(tmp_path):
    api, repository = service(tmp_path / "db.sqlite3")
    verification = api.verify(
        verification_id="V-2",
        candidate_id="C-2",
        source_system="sheety",
        verified_item_id="ITEM-2",
        verified_upc="222",
        verified_brand_name="Brand B",
        verified_item_name="Tomatoes",
        evidence={"sheety_row_id": 2},
    )
    assert verification.status == "source_item_id_mismatch"

    api.review(
        review_id="RV-2",
        verification_id="V-2",
        decision="identity_correction_required",
        reviewer="operator",
        notes="UPC and labels match",
    )
    correction = api.correct(
        correction_id="IC-1",
        verification_id="V-2",
        corrected_item_id="ITEM-2",
        provenance="sheety row 2",
        created_by="operator",
    )
    correction_review = api.review_correction(
        review_id="ICR-1",
        correction_id="IC-1",
        decision="approved",
        reviewer="operator",
        notes="verified against source",
    )

    assert correction.corrected_item_id == "ITEM-2"
    assert correction_review.decision == "approved"
    assert repository.candidate("C-2")["source_item_id"] == "WRONG"


def test_mismatch_cannot_be_directly_approved(tmp_path):
    api, _ = service(tmp_path / "db.sqlite3")
    api.verify(
        verification_id="V-2",
        candidate_id="C-2",
        source_system="sheety",
        verified_item_id="ITEM-2",
        verified_upc="222",
        verified_brand_name="Brand B",
        verified_item_name="Tomatoes",
        evidence={},
    )
    with pytest.raises(ProductIdentityError, match="identity_verified"):
        api.review(
            review_id="RV-2",
            verification_id="V-2",
            decision="approved",
            reviewer="operator",
            notes="incorrect direct approval",
        )


def test_correction_must_match_verified_source_id(tmp_path):
    api, _ = service(tmp_path / "db.sqlite3")
    api.verify(
        verification_id="V-2",
        candidate_id="C-2",
        source_system="sheety",
        verified_item_id="ITEM-2",
        verified_upc="222",
        verified_brand_name="Brand B",
        verified_item_name="Tomatoes",
        evidence={},
    )
    api.review(
        review_id="RV-2",
        verification_id="V-2",
        decision="identity_correction_required",
        reviewer="operator",
        notes="correction required",
    )
    with pytest.raises(ProductIdentityError, match="verified source"):
        api.correct(
            correction_id="IC-1",
            verification_id="V-2",
            corrected_item_id="ANOTHER-ID",
            provenance="unverified",
            created_by="operator",
        )


def test_identity_workflow_does_not_create_assignment_or_robot_tables(tmp_path):
    path = tmp_path / "db.sqlite3"
    api, _ = service(path)
    api.verify(
        verification_id="V-1",
        candidate_id="C-1",
        source_system="sheety",
        verified_item_id="ITEM-1",
        verified_upc="111",
        verified_brand_name="Brand A",
        verified_item_name="Orange Juice",
        evidence={},
    )
    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert "robot_missions" not in tables
    assert "product_assignments" not in tables
