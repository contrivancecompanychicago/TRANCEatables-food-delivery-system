import sqlite3

import pytest

from tranceatables.nutrient_ontology import (
    MeasurementUnitDefinition,
    NutrientDefinition,
    NutrientMappingReview,
    NutrientMeasurementMapping,
    NutrientOntologyError,
    SQLiteNutrientOntologyRepository,
)


NOW = "2026-10-15T12:00:00+00:00"


def repository(tmp_path):
    database = tmp_path / "ontology.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE simulated_meal_plans (
                meal_plan_id TEXT PRIMARY KEY
            );
            INSERT INTO simulated_meal_plans VALUES ('MP-1');
            """
        )
    return SQLiteNutrientOntologyRepository(database)


def unit(code, dimension="mass", status="canonical"):
    return MeasurementUnitDefinition(
        code, code, dimension, code, status, "internal", NOW
    )


def nutrient(unit_code="mg"):
    return NutrientDefinition(
        "NUT-VITAMIN-C", "Vitamin C", "absolute_mass",
        unit_code, "internal", NOW,
    )


def mapping(**changes):
    values = {
        "mapping_id": "MAP-1",
        "meal_plan_id": "MP-1",
        "food_slot": 1,
        "nutrient_id": "NUT-VITAMIN-C",
        "source_item_id": "ITEM-1",
        "source_field": "nfVitaminCDv",
        "source_value": 20.0,
        "source_unit_code": "percent_dv",
        "normalized_value": None,
        "normalized_unit_code": None,
        "status": "unconvertible",
        "provenance": "sheety",
        "created_at": NOW,
    }
    values.update(changes)
    return NutrientMeasurementMapping(**values)


def seed_definitions(repo):
    repo.define_unit(unit("mg"), actor="test")
    repo.define_unit(
        unit("percent_dv", "relative", "context_required"), actor="test"
    )
    repo.define_unit(
        unit("model_unit", "abstract", "not_convertible"), actor="test"
    )
    repo.define_nutrient(nutrient(), actor="test")


def test_creates_five_ontology_tables(tmp_path):
    repo = repository(tmp_path)
    with sqlite3.connect(repo.database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {
        "nutrient_definitions",
        "measurement_unit_definitions",
        "nutrient_measurement_mappings",
        "nutrient_mapping_reviews",
        "nutrient_ontology_events",
    } <= tables


def test_records_definitions_mapping_and_append_only_events(tmp_path):
    repo = repository(tmp_path)
    seed_definitions(repo)
    repo.create_mapping(mapping(), actor="test")

    assert len(repo.rows("measurement_unit_definitions")) == 3
    assert len(repo.rows("nutrient_definitions")) == 1
    stored = repo.rows("nutrient_measurement_mappings")[0]
    assert stored["status"] == "unconvertible"
    assert stored["normalized_value"] is None
    assert len(repo.rows("nutrient_ontology_events")) == 5


def test_missing_magnesium_is_explicit_and_cannot_be_approved(tmp_path):
    repo = repository(tmp_path)
    seed_definitions(repo)
    repo.create_mapping(
        mapping(
            mapping_id="MAP-MAGNESIUM",
            source_field="magnesium",
            source_value=None,
            source_unit_code="mg",
            status="source_missing",
        ),
        actor="test",
    )

    with pytest.raises(NutrientOntologyError, match="validated"):
        repo.review_mapping(
            NutrientMappingReview(
                "REVIEW-1", "MAP-MAGNESIUM", "approved", "reviewer",
                "missing source", NOW,
            )
        )


def test_daily_value_is_not_silently_converted_to_milligrams(tmp_path):
    repo = repository(tmp_path)
    seed_definitions(repo)

    with pytest.raises(NutrientOntologyError, match="cross-unit"):
        repo.create_mapping(
            mapping(
                normalized_value=18.0,
                normalized_unit_code="mg",
                status="validated",
            ),
            actor="test",
        )


def test_model_unit_cannot_be_converted_to_physical_unit(tmp_path):
    repo = repository(tmp_path)
    seed_definitions(repo)

    with pytest.raises(NutrientOntologyError, match="model_unit"):
        repo.create_mapping(
            mapping(
                source_unit_code="model_unit",
                normalized_value=20.0,
                normalized_unit_code="mg",
                status="pending_review",
            ),
            actor="test",
        )


def test_validated_same_unit_mapping_can_receive_one_review(tmp_path):
    repo = repository(tmp_path)
    seed_definitions(repo)
    repo.create_mapping(
        mapping(
            source_unit_code="mg",
            normalized_value=20.0,
            normalized_unit_code="mg",
            status="validated",
        ),
        actor="test",
    )
    review = NutrientMappingReview(
        "REVIEW-1", "MAP-1", "approved", "reviewer", "verified", NOW
    )
    repo.review_mapping(review)
    assert repo.rows("nutrient_mapping_reviews")[0]["decision"] == "approved"

    with pytest.raises(NutrientOntologyError, match="already reviewed"):
        repo.review_mapping(review)
