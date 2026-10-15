from dataclasses import replace
import sqlite3

import pytest

from tranceatables import (
    DeliveryRequest,
    MeasurementUnitDefinition,
    NutrientDefinition,
    NutrientEvidenceError,
    NutrientEvidenceRecord,
    NutrientEvidenceReview,
    OrderService,
    SQLiteMealPlanRepository,
    SQLiteNutrientEvidenceRepository,
    SQLiteNutrientOntologyRepository,
    SQLiteOrderRepository,
)


NOW = "2026-10-15T19:00:00+00:00"


def repository(tmp_path):
    database = tmp_path / "evidence.sqlite3"
    orders = SQLiteOrderRepository(database)
    OrderService(orders).create_order(DeliveryRequest("O-1", 1.0, 1.0))
    SQLiteMealPlanRepository(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO simulated_meal_plans VALUES
            ('MP-1', 'O-1', '[]', '[]', '[]', '[]', '[]', 'model_unit',
             'model_unit', 'solved_unmapped', NULL, NULL, NULL, ?, ?, 1)""",
            (NOW, NOW),
        )
    ontology = SQLiteNutrientOntologyRepository(database)
    ontology.define_unit(
        MeasurementUnitDefinition(
            "mg", "milligram", "mass", "mg", "canonical", "test", NOW
        ),
        actor="test",
    )
    ontology.define_unit(
        MeasurementUnitDefinition(
            "percent_dv", "Daily Value percentage", "relative", "%DV",
            "context_required", "test", NOW,
        ),
        actor="test",
    )
    ontology.define_nutrient(
        NutrientDefinition(
            "N-C", "Vitamin C", "absolute_mass", "mg", "test", NOW
        ),
        actor="test",
    )
    return SQLiteNutrientEvidenceRepository(database)


def gap() -> NutrientEvidenceRecord:
    return NutrientEvidenceRecord(
        "E-1", "MP-1", 1, "N-C", "ITEM-1", "pending_label",
        "exact label required", None, None, 8.0, "fl oz", 226.0,
        "evidence_required", "no value inferred", NOW,
    )


def test_records_gap_without_fabricating_value(tmp_path):
    repo = repository(tmp_path)
    repo.create(gap(), actor="system")
    record = repo.rows("nutrient_evidence_records")[0]
    assert record["reported_value"] is None
    assert record["reported_unit_code"] is None
    assert record["status"] == "evidence_required"
    assert len(repo.rows("nutrient_evidence_events")) == 1


def test_gap_rejects_value_and_percent_dv_is_rejected(tmp_path):
    repo = repository(tmp_path)
    with pytest.raises(NutrientEvidenceError, match="gap"):
        repo.create(
            replace(gap(), reported_value=110.0, reported_unit_code="mg"),
            actor="test",
        )
    with pytest.raises(NutrientEvidenceError, match="milligram"):
        repo.create(
            replace(
                gap(), status="pending_review", reported_value=110.0,
                reported_unit_code="percent_dv",
            ),
            actor="test",
        )


def test_missing_label_declaration_is_not_zero(tmp_path):
    repo = repository(tmp_path)
    with pytest.raises(NutrientEvidenceError, match="unknown"):
        repo.create(
            replace(
                gap(), status="not_declared_on_label", reported_value=0.0,
                reported_unit_code="mg",
            ),
            actor="test",
        )


def test_unresolved_evidence_cannot_be_approved(tmp_path):
    repo = repository(tmp_path)
    repo.create(gap(), actor="system")
    review = NutrientEvidenceReview(
        "ER-1", "E-1", "approved", "operator", "reviewed", NOW
    )
    with pytest.raises(NutrientEvidenceError, match="validated"):
        repo.review(review)


def test_validated_mg_evidence_can_be_approved(tmp_path):
    repo = repository(tmp_path)
    record = replace(
        gap(), status="validated", reported_value=20.0,
        reported_unit_code="mg", evidence_source="exact_product_label",
        evidence_reference="label-photo-sha256:test",
    )
    repo.create(record, actor="operator")
    repo.review(
        NutrientEvidenceReview(
            "ER-1", "E-1", "approved", "operator", "exact label", NOW
        )
    )
    assert repo.rows("nutrient_evidence_reviews")[0]["decision"] == "approved"
    assert len(repo.rows("nutrient_evidence_events")) == 2
