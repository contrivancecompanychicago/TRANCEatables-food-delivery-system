"""Stage 2.7–2.8 persistence for simulation-only serving candidates.

Candidates are review records only. They never assign a grocery item to a meal
plan, advance an order, create a robot mission, or dispatch hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Callable

from .meal_plan import SQLiteMealPlanRepository


class DuplicateServingCandidateError(ValueError):
    pass


class ServingCandidateNotFoundError(LookupError):
    pass


class ServingCandidateEligibilityError(ValueError):
    pass


class DuplicateServingCandidateReviewError(ValueError):
    pass


VALID_REVIEW_DECISIONS = ("approved", "correction_required", "rejected")


@dataclass(frozen=True)
class ServingCandidateInput:
    candidate_id: str
    meal_plan_id: str
    food_slot: int
    source: str
    source_item_id: str
    source_upc: str | None
    brand_name: str
    item_name: str
    serving_quantity: float
    serving_unit_label: str
    serving_weight_grams: float | None
    metric_quantity: float | None
    metric_unit: str | None
    ontology_source: str = "tranceatables_internal"


@dataclass(frozen=True)
class FoodServingCandidate:
    candidate_id: str
    meal_plan_id: str
    food_slot: int
    source: str
    source_item_id: str
    source_upc: str | None
    brand_name: str
    item_name: str
    serving_quantity: float
    serving_unit_label: str
    serving_weight_grams: float | None
    metric_quantity: float | None
    metric_unit: str | None
    ontology_source: str
    review_status: str
    created_at: str
    updated_at: str
    simulation_only: bool = True


@dataclass(frozen=True)
class ServingCandidateEvent:
    event_id: int
    candidate_id: str
    event_type: str
    actor: str
    message: str
    occurred_at: str


@dataclass(frozen=True)
class ServingCandidateReview:
    review_id: str
    candidate_id: str
    decision: str
    reviewer: str
    notes: str
    decided_at: str
    simulation_only: bool = True


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SQLiteServingCandidateRepository:
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
            meal_plans_exist = connection.execute(
                """SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'simulated_meal_plans'"""
            ).fetchone()
            if meal_plans_exist is None:
                raise ServingCandidateEligibilityError(
                    "simulated_meal_plans must exist before candidate persistence"
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS food_serving_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    meal_plan_id TEXT NOT NULL
                        REFERENCES simulated_meal_plans(meal_plan_id),
                    food_slot INTEGER NOT NULL CHECK(food_slot BETWEEN 1 AND 3),
                    source TEXT NOT NULL,
                    source_item_id TEXT NOT NULL,
                    source_upc TEXT,
                    brand_name TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    serving_quantity REAL NOT NULL CHECK(serving_quantity > 0),
                    serving_unit_label TEXT NOT NULL,
                    serving_weight_grams REAL
                        CHECK(serving_weight_grams IS NULL
                              OR serving_weight_grams > 0),
                    metric_quantity REAL
                        CHECK(metric_quantity IS NULL OR metric_quantity > 0),
                    metric_unit TEXT,
                    ontology_source TEXT NOT NULL,
                    review_status TEXT NOT NULL
                        CHECK(review_status IN (
                            'structurally_valid',
                            'mass_missing',
                            'rejected'
                        )),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1),
                    UNIQUE(meal_plan_id, food_slot, source_item_id)
                );
                CREATE TABLE IF NOT EXISTS food_serving_candidate_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id TEXT NOT NULL
                        REFERENCES food_serving_candidates(candidate_id),
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    message TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS serving_candidate_reviews (
                    review_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL UNIQUE
                        REFERENCES food_serving_candidates(candidate_id),
                    decision TEXT NOT NULL CHECK(decision IN (
                        'approved',
                        'correction_required',
                        'rejected'
                    )),
                    reviewer TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1)
                );
                """
            )

    def create(
        self,
        candidate: FoodServingCandidate,
        *,
        actor: str,
        message: str,
    ) -> FoodServingCandidate:
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO food_serving_candidates (
                        candidate_id, meal_plan_id, food_slot, source,
                        source_item_id, source_upc, brand_name, item_name,
                        serving_quantity, serving_unit_label,
                        serving_weight_grams, metric_quantity, metric_unit,
                        ontology_source, review_status, created_at, updated_at,
                        simulation_only
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              ?, ?)""",
                    (
                        candidate.candidate_id,
                        candidate.meal_plan_id,
                        candidate.food_slot,
                        candidate.source,
                        candidate.source_item_id,
                        candidate.source_upc,
                        candidate.brand_name,
                        candidate.item_name,
                        candidate.serving_quantity,
                        candidate.serving_unit_label,
                        candidate.serving_weight_grams,
                        candidate.metric_quantity,
                        candidate.metric_unit,
                        candidate.ontology_source,
                        candidate.review_status,
                        candidate.created_at,
                        candidate.updated_at,
                        int(candidate.simulation_only),
                    ),
                )
                connection.execute(
                    """INSERT INTO food_serving_candidate_events
                    (candidate_id, event_type, actor, message, occurred_at)
                    VALUES (?, 'candidate_created', ?, ?, ?)""",
                    (
                        candidate.candidate_id,
                        actor,
                        message,
                        candidate.created_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateServingCandidateError(
                f"candidate already exists or conflicts: {candidate.candidate_id}"
            ) from error
        return candidate

    def get(self, candidate_id: str) -> FoodServingCandidate:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM food_serving_candidates
                WHERE candidate_id = ?""",
                (candidate_id,),
            ).fetchone()
        if row is None:
            raise ServingCandidateNotFoundError(candidate_id)
        return self._row_to_candidate(row)

    def list_for_plan(self, meal_plan_id: str) -> tuple[FoodServingCandidate, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM food_serving_candidates
                WHERE meal_plan_id = ?
                ORDER BY food_slot, candidate_id""",
                (meal_plan_id,),
            ).fetchall()
        return tuple(self._row_to_candidate(row) for row in rows)

    def events(self, candidate_id: str) -> tuple[ServingCandidateEvent, ...]:
        self.get(candidate_id)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM food_serving_candidate_events
                WHERE candidate_id = ? ORDER BY event_id""",
                (candidate_id,),
            ).fetchall()
        return tuple(
            ServingCandidateEvent(
                event_id=row["event_id"],
                candidate_id=row["candidate_id"],
                event_type=row["event_type"],
                actor=row["actor"],
                message=row["message"],
                occurred_at=row["occurred_at"],
            )
            for row in rows
        )

    def record_review(
        self,
        review: ServingCandidateReview,
    ) -> ServingCandidateReview:
        self.get(review.candidate_id)
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO serving_candidate_reviews (
                        review_id, candidate_id, decision, reviewer, notes,
                        decided_at, simulation_only
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        review.review_id,
                        review.candidate_id,
                        review.decision,
                        review.reviewer,
                        review.notes,
                        review.decided_at,
                        int(review.simulation_only),
                    ),
                )
                connection.execute(
                    """INSERT INTO food_serving_candidate_events
                    (candidate_id, event_type, actor, message, occurred_at)
                    VALUES (?, 'candidate_reviewed', ?, ?, ?)""",
                    (
                        review.candidate_id,
                        review.reviewer,
                        f"{review.decision}: {review.notes}",
                        review.decided_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateServingCandidateReviewError(
                f"candidate already reviewed or review ID conflicts: "
                f"{review.candidate_id}"
            ) from error
        return review

    def get_review(self, candidate_id: str) -> ServingCandidateReview | None:
        self.get(candidate_id)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM serving_candidate_reviews
                WHERE candidate_id = ?""",
                (candidate_id,),
            ).fetchone()
        if row is None:
            return None
        return ServingCandidateReview(
            review_id=row["review_id"],
            candidate_id=row["candidate_id"],
            decision=row["decision"],
            reviewer=row["reviewer"],
            notes=row["notes"],
            decided_at=row["decided_at"],
            simulation_only=bool(row["simulation_only"]),
        )

    @staticmethod
    def _row_to_candidate(row: sqlite3.Row) -> FoodServingCandidate:
        return FoodServingCandidate(
            candidate_id=row["candidate_id"],
            meal_plan_id=row["meal_plan_id"],
            food_slot=row["food_slot"],
            source=row["source"],
            source_item_id=row["source_item_id"],
            source_upc=row["source_upc"],
            brand_name=row["brand_name"],
            item_name=row["item_name"],
            serving_quantity=row["serving_quantity"],
            serving_unit_label=row["serving_unit_label"],
            serving_weight_grams=row["serving_weight_grams"],
            metric_quantity=row["metric_quantity"],
            metric_unit=row["metric_unit"],
            ontology_source=row["ontology_source"],
            review_status=row["review_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            simulation_only=bool(row["simulation_only"]),
        )


class ServingCandidateService:
    def __init__(
        self,
        meal_plan_repository: SQLiteMealPlanRepository,
        candidate_repository: SQLiteServingCandidateRepository,
        *,
        clock: Clock = _utc_now,
    ) -> None:
        self.meal_plan_repository = meal_plan_repository
        self.candidate_repository = candidate_repository
        self.clock = clock

    def _timestamp(self) -> str:
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc).isoformat()

    def create_candidate(
        self,
        candidate_input: ServingCandidateInput,
        *,
        actor: str,
    ) -> FoodServingCandidate:
        self._validate_input(candidate_input, actor)
        plan = self.meal_plan_repository.get(candidate_input.meal_plan_id)
        if not plan.simulation_only or plan.status != "solved_unmapped":
            raise ServingCandidateEligibilityError(
                "candidates require a simulation-only solved_unmapped meal plan"
            )
        if any(plan.food_item_ids):
            raise ServingCandidateEligibilityError(
                "candidates cannot be added after product assignment"
            )

        timestamp = self._timestamp()
        status = (
            "structurally_valid"
            if candidate_input.serving_weight_grams is not None
            else "mass_missing"
        )
        candidate = FoodServingCandidate(
            **candidate_input.__dict__,
            review_status=status,
            created_at=timestamp,
            updated_at=timestamp,
        )
        return self.candidate_repository.create(
            candidate,
            actor=actor,
            message=(
                "serving candidate recorded for human review; "
                "meal-plan mapping remains unchanged"
            ),
        )

    def review_candidate(
        self,
        *,
        review_id: str,
        candidate_id: str,
        decision: str,
        reviewer: str,
        notes: str,
    ) -> ServingCandidateReview:
        values = (review_id, candidate_id, reviewer, notes)
        if any(not value.strip() for value in values):
            raise ValueError(
                "review ID, candidate ID, reviewer, and notes cannot be blank"
            )
        if decision not in VALID_REVIEW_DECISIONS:
            raise ValueError(
                f"decision must be one of {VALID_REVIEW_DECISIONS}"
            )

        candidate = self.candidate_repository.get(candidate_id)
        if decision == "approved" and candidate.review_status != "structurally_valid":
            raise ServingCandidateEligibilityError(
                "only structurally_valid candidates may be approved"
            )

        review = ServingCandidateReview(
            review_id=review_id,
            candidate_id=candidate_id,
            decision=decision,
            reviewer=reviewer,
            notes=notes,
            decided_at=self._timestamp(),
        )
        return self.candidate_repository.record_review(review)

    @staticmethod
    def _validate_input(
        candidate_input: ServingCandidateInput,
        actor: str,
    ) -> None:
        text_values = (
            candidate_input.candidate_id,
            candidate_input.meal_plan_id,
            candidate_input.source,
            candidate_input.source_item_id,
            candidate_input.brand_name,
            candidate_input.item_name,
            candidate_input.serving_unit_label,
            candidate_input.ontology_source,
            actor,
        )
        if any(not value.strip() for value in text_values):
            raise ValueError("candidate identifiers, labels, and actor cannot be blank")
        if candidate_input.food_slot not in (1, 2, 3):
            raise ValueError("food_slot must be 1, 2, or 3")
        if candidate_input.serving_quantity <= 0:
            raise ValueError("serving_quantity must be positive")
        if (
            candidate_input.serving_weight_grams is not None
            and candidate_input.serving_weight_grams <= 0
        ):
            raise ValueError("serving_weight_grams must be positive when present")
        metric_pair = (
            candidate_input.metric_quantity is not None,
            candidate_input.metric_unit is not None
            and bool(candidate_input.metric_unit.strip()),
        )
        if metric_pair[0] != metric_pair[1]:
            raise ValueError(
                "metric_quantity and metric_unit must be supplied together"
            )
        if (
            candidate_input.metric_quantity is not None
            and candidate_input.metric_quantity <= 0
        ):
            raise ValueError("metric_quantity must be positive when present")
