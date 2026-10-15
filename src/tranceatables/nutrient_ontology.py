"""Stage 2.12 deterministic nutrient measurement ontology.

The ontology records definitions, source measurements, and human review. It
does not infer conversions, assign products, advance orders, or control robots.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


class NutrientOntologyError(ValueError):
    pass


@dataclass(frozen=True)
class NutrientDefinition:
    nutrient_id: str
    canonical_name: str
    measurement_basis: str
    canonical_unit_code: str
    provenance: str
    created_at: str
    simulation_only: bool = True


@dataclass(frozen=True)
class MeasurementUnitDefinition:
    unit_code: str
    display_name: str
    dimension: str
    symbol: str
    conversion_status: str
    provenance: str
    created_at: str
    simulation_only: bool = True


@dataclass(frozen=True)
class NutrientMeasurementMapping:
    mapping_id: str
    meal_plan_id: str
    food_slot: int
    nutrient_id: str
    source_item_id: str
    source_field: str
    source_value: float | None
    source_unit_code: str
    normalized_value: float | None
    normalized_unit_code: str | None
    status: str
    provenance: str
    created_at: str
    simulation_only: bool = True


@dataclass(frozen=True)
class NutrientMappingReview:
    review_id: str
    mapping_id: str
    decision: str
    reviewer: str
    notes: str
    decided_at: str
    simulation_only: bool = True


VALID_BASES = {"absolute_mass", "daily_value_percent", "abstract_model"}
VALID_CONVERSION_STATUSES = {"canonical", "exact", "context_required", "not_convertible"}
VALID_MAPPING_STATUSES = {"pending_review", "source_missing", "unconvertible", "validated"}
VALID_REVIEW_DECISIONS = {"approved", "correction_required", "rejected"}


class SQLiteNutrientOntologyRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            plan_table = connection.execute(
                """SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'simulated_meal_plans'"""
            ).fetchone()
            if plan_table is None:
                raise NutrientOntologyError(
                    "simulated_meal_plans must exist before ontology persistence"
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS measurement_unit_definitions (
                    unit_code TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    conversion_status TEXT NOT NULL CHECK(conversion_status IN (
                        'canonical', 'exact', 'context_required', 'not_convertible'
                    )),
                    provenance TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1)
                );
                CREATE TABLE IF NOT EXISTS nutrient_definitions (
                    nutrient_id TEXT PRIMARY KEY,
                    canonical_name TEXT NOT NULL UNIQUE,
                    measurement_basis TEXT NOT NULL CHECK(measurement_basis IN (
                        'absolute_mass', 'daily_value_percent', 'abstract_model'
                    )),
                    canonical_unit_code TEXT NOT NULL
                        REFERENCES measurement_unit_definitions(unit_code),
                    provenance TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1)
                );
                CREATE TABLE IF NOT EXISTS nutrient_measurement_mappings (
                    mapping_id TEXT PRIMARY KEY,
                    meal_plan_id TEXT NOT NULL
                        REFERENCES simulated_meal_plans(meal_plan_id),
                    food_slot INTEGER NOT NULL CHECK(food_slot BETWEEN 1 AND 3),
                    nutrient_id TEXT NOT NULL
                        REFERENCES nutrient_definitions(nutrient_id),
                    source_item_id TEXT NOT NULL,
                    source_field TEXT NOT NULL,
                    source_value REAL CHECK(source_value IS NULL OR source_value >= 0),
                    source_unit_code TEXT NOT NULL
                        REFERENCES measurement_unit_definitions(unit_code),
                    normalized_value REAL CHECK(
                        normalized_value IS NULL OR normalized_value >= 0
                    ),
                    normalized_unit_code TEXT
                        REFERENCES measurement_unit_definitions(unit_code),
                    status TEXT NOT NULL CHECK(status IN (
                        'pending_review', 'source_missing',
                        'unconvertible', 'validated'
                    )),
                    provenance TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1),
                    UNIQUE(meal_plan_id, food_slot, nutrient_id)
                );
                CREATE TABLE IF NOT EXISTS nutrient_mapping_reviews (
                    review_id TEXT PRIMARY KEY,
                    mapping_id TEXT NOT NULL UNIQUE
                        REFERENCES nutrient_measurement_mappings(mapping_id),
                    decision TEXT NOT NULL CHECK(decision IN (
                        'approved', 'correction_required', 'rejected'
                    )),
                    reviewer TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1)
                );
                CREATE TABLE IF NOT EXISTS nutrient_ontology_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    message TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                """
            )

    def define_unit(self, unit: MeasurementUnitDefinition, *, actor: str) -> None:
        if unit.conversion_status not in VALID_CONVERSION_STATUSES:
            raise NutrientOntologyError("invalid unit conversion status")
        self._insert_with_event(
            """INSERT INTO measurement_unit_definitions VALUES
            (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                unit.unit_code, unit.display_name, unit.dimension, unit.symbol,
                unit.conversion_status, unit.provenance, unit.created_at,
                int(unit.simulation_only),
            ),
            "measurement_unit", unit.unit_code, "unit_defined", actor,
            f"unit {unit.unit_code} defined", unit.created_at,
        )

    def define_nutrient(self, nutrient: NutrientDefinition, *, actor: str) -> None:
        if nutrient.measurement_basis not in VALID_BASES:
            raise NutrientOntologyError("invalid nutrient measurement basis")
        self._insert_with_event(
            """INSERT INTO nutrient_definitions VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                nutrient.nutrient_id, nutrient.canonical_name,
                nutrient.measurement_basis, nutrient.canonical_unit_code,
                nutrient.provenance, nutrient.created_at,
                int(nutrient.simulation_only),
            ),
            "nutrient", nutrient.nutrient_id, "nutrient_defined", actor,
            f"nutrient {nutrient.canonical_name} defined", nutrient.created_at,
        )

    def create_mapping(self, mapping: NutrientMeasurementMapping, *, actor: str) -> None:
        self._validate_mapping(mapping)
        self._insert_with_event(
            """INSERT INTO nutrient_measurement_mappings VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mapping.mapping_id, mapping.meal_plan_id, mapping.food_slot,
                mapping.nutrient_id, mapping.source_item_id,
                mapping.source_field, mapping.source_value,
                mapping.source_unit_code, mapping.normalized_value,
                mapping.normalized_unit_code, mapping.status,
                mapping.provenance, mapping.created_at,
                int(mapping.simulation_only),
            ),
            "nutrient_mapping", mapping.mapping_id, "mapping_created", actor,
            f"mapping recorded with status {mapping.status}", mapping.created_at,
        )

    def review_mapping(self, review: NutrientMappingReview) -> None:
        if review.decision not in VALID_REVIEW_DECISIONS:
            raise NutrientOntologyError("invalid mapping review decision")
        with self._connect() as connection:
            mapping = connection.execute(
                "SELECT status FROM nutrient_measurement_mappings WHERE mapping_id = ?",
                (review.mapping_id,),
            ).fetchone()
            if mapping is None:
                raise NutrientOntologyError("nutrient mapping not found")
            if review.decision == "approved" and mapping["status"] != "validated":
                raise NutrientOntologyError(
                    "only a validated nutrient mapping can be approved"
                )
            try:
                connection.execute(
                    """INSERT INTO nutrient_mapping_reviews VALUES
                    (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        review.review_id, review.mapping_id, review.decision,
                        review.reviewer, review.notes, review.decided_at,
                        int(review.simulation_only),
                    ),
                )
                connection.execute(
                    """INSERT INTO nutrient_ontology_events
                    (entity_type, entity_id, event_type, actor, message, occurred_at)
                    VALUES ('nutrient_mapping', ?, 'mapping_reviewed', ?, ?, ?)""",
                    (
                        review.mapping_id, review.reviewer,
                        f"mapping {review.decision}: {review.notes}",
                        review.decided_at,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise NutrientOntologyError("mapping already reviewed") from error

    def _validate_mapping(self, mapping: NutrientMeasurementMapping) -> None:
        if mapping.status not in VALID_MAPPING_STATUSES:
            raise NutrientOntologyError("invalid nutrient mapping status")
        if mapping.source_value is None and mapping.status != "source_missing":
            raise NutrientOntologyError(
                "a missing source value must use source_missing status"
            )
        if mapping.status == "validated":
            if mapping.normalized_value is None or not mapping.normalized_unit_code:
                raise NutrientOntologyError(
                    "validated mappings require a normalized value and unit"
                )
            if mapping.source_unit_code != mapping.normalized_unit_code:
                raise NutrientOntologyError(
                    "cross-unit normalization requires a separately validated rule"
                )
        if mapping.status == "source_missing" and (
            mapping.normalized_value is not None
            or mapping.normalized_unit_code is not None
        ):
            raise NutrientOntologyError(
                "a source-missing mapping cannot contain a normalized value"
            )
        if mapping.source_unit_code == "model_unit" and (
            mapping.normalized_unit_code not in (None, "model_unit")
        ):
            raise NutrientOntologyError(
                "model_unit cannot be converted to a physical unit without a rule"
            )

    def _insert_with_event(
        self, sql: str, values: tuple[object, ...], entity_type: str,
        entity_id: str, event_type: str, actor: str, message: str,
        occurred_at: str,
    ) -> None:
        try:
            with self._connect() as connection:
                connection.execute(sql, values)
                connection.execute(
                    """INSERT INTO nutrient_ontology_events
                    (entity_type, entity_id, event_type, actor, message, occurred_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (entity_type, entity_id, event_type, actor, message, occurred_at),
                )
        except sqlite3.IntegrityError as error:
            raise NutrientOntologyError(
                f"ontology record already exists or conflicts: {entity_id}"
            ) from error

    def rows(self, table: str) -> list[sqlite3.Row]:
        allowed = {
            "measurement_unit_definitions", "nutrient_definitions",
            "nutrient_measurement_mappings", "nutrient_mapping_reviews",
            "nutrient_ontology_events",
        }
        if table not in allowed:
            raise NutrientOntologyError("unsupported ontology table")
        with self._connect() as connection:
            return connection.execute(f'SELECT * FROM "{table}"').fetchall()
