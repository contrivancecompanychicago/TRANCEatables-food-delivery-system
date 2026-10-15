"""Stage 2.12.2 exact nutrient-evidence persistence.

Evidence gaps may be recorded without inventing nutrient values. Accepted
evidence must identify an exact product, use an absolute milligram value, and
receive a separate human review. This module never assigns meal-plan products,
advances orders, or controls robots.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


class NutrientEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class NutrientEvidenceRecord:
    evidence_id: str
    meal_plan_id: str
    food_slot: int
    nutrient_id: str
    source_item_id: str
    evidence_source: str
    evidence_reference: str
    reported_value: float | None
    reported_unit_code: str | None
    serving_basis_quantity: float | None
    serving_basis_unit: str
    serving_weight_grams: float | None
    status: str
    provenance: str
    created_at: str
    simulation_only: bool = True


@dataclass(frozen=True)
class NutrientEvidenceReview:
    review_id: str
    evidence_id: str
    decision: str
    reviewer: str
    notes: str
    decided_at: str
    simulation_only: bool = True


VALID_EVIDENCE_STATUSES = {
    "evidence_required", "pending_review", "not_declared_on_label", "validated"
}
VALID_EVIDENCE_DECISIONS = {"approved", "correction_required", "rejected"}


class SQLiteNutrientEvidenceRepository:
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
            present = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            required = {
                "simulated_meal_plans", "nutrient_definitions",
                "measurement_unit_definitions",
            }
            if required - present:
                raise NutrientEvidenceError(
                    "meal-plan and nutrient-ontology tables must exist before "
                    "nutrient-evidence persistence"
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS nutrient_evidence_records (
                    evidence_id TEXT PRIMARY KEY,
                    meal_plan_id TEXT NOT NULL
                        REFERENCES simulated_meal_plans(meal_plan_id),
                    food_slot INTEGER NOT NULL CHECK(food_slot BETWEEN 1 AND 3),
                    nutrient_id TEXT NOT NULL
                        REFERENCES nutrient_definitions(nutrient_id),
                    source_item_id TEXT NOT NULL,
                    evidence_source TEXT NOT NULL,
                    evidence_reference TEXT NOT NULL,
                    reported_value REAL CHECK(
                        reported_value IS NULL OR reported_value >= 0
                    ),
                    reported_unit_code TEXT
                        REFERENCES measurement_unit_definitions(unit_code),
                    serving_basis_quantity REAL CHECK(
                        serving_basis_quantity IS NULL OR serving_basis_quantity > 0
                    ),
                    serving_basis_unit TEXT NOT NULL,
                    serving_weight_grams REAL CHECK(
                        serving_weight_grams IS NULL OR serving_weight_grams > 0
                    ),
                    status TEXT NOT NULL CHECK(status IN (
                        'evidence_required', 'pending_review',
                        'not_declared_on_label', 'validated'
                    )),
                    provenance TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1),
                    UNIQUE(
                        meal_plan_id, food_slot, nutrient_id,
                        evidence_source, evidence_reference
                    )
                );
                CREATE TABLE IF NOT EXISTS nutrient_evidence_reviews (
                    review_id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL UNIQUE
                        REFERENCES nutrient_evidence_records(evidence_id),
                    decision TEXT NOT NULL CHECK(decision IN (
                        'approved', 'correction_required', 'rejected'
                    )),
                    reviewer TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1)
                );
                CREATE TABLE IF NOT EXISTS nutrient_evidence_events (
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

    def create(self, record: NutrientEvidenceRecord, *, actor: str) -> None:
        self._validate(record)
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO nutrient_evidence_records VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.evidence_id, record.meal_plan_id, record.food_slot,
                        record.nutrient_id, record.source_item_id,
                        record.evidence_source, record.evidence_reference,
                        record.reported_value, record.reported_unit_code,
                        record.serving_basis_quantity, record.serving_basis_unit,
                        record.serving_weight_grams, record.status,
                        record.provenance, record.created_at,
                        int(record.simulation_only),
                    ),
                )
                connection.execute(
                    """INSERT INTO nutrient_evidence_events
                    (entity_type, entity_id, event_type, actor, message, occurred_at)
                    VALUES ('nutrient_evidence', ?, 'evidence_recorded', ?, ?, ?)""",
                    (
                        record.evidence_id, actor,
                        f"nutrient evidence recorded with status {record.status}",
                        record.created_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise NutrientEvidenceError(
                "nutrient evidence already exists or conflicts"
            ) from error

    def review(self, review: NutrientEvidenceReview) -> None:
        if review.decision not in VALID_EVIDENCE_DECISIONS:
            raise NutrientEvidenceError("invalid nutrient-evidence decision")
        with self._connect() as connection:
            record = connection.execute(
                "SELECT status FROM nutrient_evidence_records WHERE evidence_id = ?",
                (review.evidence_id,),
            ).fetchone()
            if record is None:
                raise NutrientEvidenceError("nutrient evidence not found")
            if review.decision == "approved" and record["status"] != "validated":
                raise NutrientEvidenceError(
                    "only validated exact nutrient evidence can be approved"
                )
            try:
                connection.execute(
                    """INSERT INTO nutrient_evidence_reviews VALUES
                    (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        review.review_id, review.evidence_id, review.decision,
                        review.reviewer, review.notes, review.decided_at,
                        int(review.simulation_only),
                    ),
                )
                connection.execute(
                    """INSERT INTO nutrient_evidence_events
                    (entity_type, entity_id, event_type, actor, message, occurred_at)
                    VALUES ('nutrient_evidence', ?, 'evidence_reviewed', ?, ?, ?)""",
                    (
                        review.evidence_id, review.reviewer,
                        f"nutrient evidence {review.decision}: {review.notes}",
                        review.decided_at,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise NutrientEvidenceError("nutrient evidence already reviewed") from error

    def _validate(self, record: NutrientEvidenceRecord) -> None:
        if record.status not in VALID_EVIDENCE_STATUSES:
            raise NutrientEvidenceError("invalid nutrient-evidence status")
        if not 1 <= record.food_slot <= 3:
            raise NutrientEvidenceError("food_slot must be between 1 and 3")
        if record.status == "evidence_required":
            if record.reported_value is not None or record.reported_unit_code is not None:
                raise NutrientEvidenceError(
                    "an evidence gap cannot contain a reported nutrient value"
                )
        elif record.status == "not_declared_on_label":
            if record.reported_value is not None:
                raise NutrientEvidenceError(
                    "not_declared_on_label is unknown, not a zero value"
                )
        else:
            if record.reported_value is None or not record.reported_unit_code:
                raise NutrientEvidenceError(
                    "reported evidence requires a value and unit"
                )
            if record.reported_unit_code != "mg":
                raise NutrientEvidenceError(
                    "Stage 2.12.2 accepts only absolute milligram evidence"
                )

    def rows(self, table: str) -> list[sqlite3.Row]:
        allowed = {
            "nutrient_evidence_records", "nutrient_evidence_reviews",
            "nutrient_evidence_events",
        }
        if table not in allowed:
            raise NutrientEvidenceError("unsupported nutrient-evidence table")
        with self._connect() as connection:
            return connection.execute(f'SELECT * FROM "{table}"').fetchall()
