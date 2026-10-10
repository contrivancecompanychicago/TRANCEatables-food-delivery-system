"""Stage 2.9 immutable corrections for simulation-only serving candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Callable

from .serving_candidate import (
    ServingCandidateEligibilityError,
    SQLiteServingCandidateRepository,
    VALID_REVIEW_DECISIONS,
)


class DuplicateServingRevisionError(ValueError):
    pass


class ServingRevisionNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class ServingCandidateRevision:
    revision_id: str
    original_candidate_id: str
    source_item_id: str
    serving_quantity: float
    serving_unit_label: str
    serving_weight_grams: float
    metric_quantity: float | None
    metric_unit: str | None
    provenance: str
    created_by: str
    created_at: str
    simulation_only: bool = True


@dataclass(frozen=True)
class ServingRevisionReview:
    review_id: str
    revision_id: str
    decision: str
    reviewer: str
    notes: str
    decided_at: str
    simulation_only: bool = True


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SQLiteServingRevisionRepository:
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
            candidates_exist = connection.execute(
                """SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'food_serving_candidates'"""
            ).fetchone()
            if candidates_exist is None:
                raise ServingCandidateEligibilityError(
                    "food_serving_candidates must exist before revision persistence"
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS serving_candidate_revisions (
                    revision_id TEXT PRIMARY KEY,
                    original_candidate_id TEXT NOT NULL UNIQUE
                        REFERENCES food_serving_candidates(candidate_id),
                    source_item_id TEXT NOT NULL,
                    serving_quantity REAL NOT NULL CHECK(serving_quantity > 0),
                    serving_unit_label TEXT NOT NULL,
                    serving_weight_grams REAL NOT NULL
                        CHECK(serving_weight_grams > 0),
                    metric_quantity REAL
                        CHECK(metric_quantity IS NULL OR metric_quantity > 0),
                    metric_unit TEXT,
                    provenance TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1)
                );
                CREATE TABLE IF NOT EXISTS serving_revision_reviews (
                    review_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL UNIQUE
                        REFERENCES serving_candidate_revisions(revision_id),
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

    def create(self, revision: ServingCandidateRevision) -> ServingCandidateRevision:
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO serving_candidate_revisions VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        revision.revision_id,
                        revision.original_candidate_id,
                        revision.source_item_id,
                        revision.serving_quantity,
                        revision.serving_unit_label,
                        revision.serving_weight_grams,
                        revision.metric_quantity,
                        revision.metric_unit,
                        revision.provenance,
                        revision.created_by,
                        revision.created_at,
                        int(revision.simulation_only),
                    ),
                )
                connection.execute(
                    """INSERT INTO food_serving_candidate_events
                    (candidate_id, event_type, actor, message, occurred_at)
                    VALUES (?, 'candidate_revision_created', ?, ?, ?)""",
                    (
                        revision.original_candidate_id,
                        revision.created_by,
                        f"revision {revision.revision_id} created; "
                        "original candidate preserved",
                        revision.created_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateServingRevisionError(
                f"revision already exists or original was revised: "
                f"{revision.original_candidate_id}"
            ) from error
        return revision

    def get(self, revision_id: str) -> ServingCandidateRevision:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM serving_candidate_revisions
                WHERE revision_id = ?""",
                (revision_id,),
            ).fetchone()
        if row is None:
            raise ServingRevisionNotFoundError(revision_id)
        return ServingCandidateRevision(
            revision_id=row["revision_id"],
            original_candidate_id=row["original_candidate_id"],
            source_item_id=row["source_item_id"],
            serving_quantity=row["serving_quantity"],
            serving_unit_label=row["serving_unit_label"],
            serving_weight_grams=row["serving_weight_grams"],
            metric_quantity=row["metric_quantity"],
            metric_unit=row["metric_unit"],
            provenance=row["provenance"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            simulation_only=bool(row["simulation_only"]),
        )

    def record_review(self, review: ServingRevisionReview) -> ServingRevisionReview:
        self.get(review.revision_id)
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO serving_revision_reviews VALUES
                    (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        review.review_id,
                        review.revision_id,
                        review.decision,
                        review.reviewer,
                        review.notes,
                        review.decided_at,
                        int(review.simulation_only),
                    ),
                )
                original_id = connection.execute(
                    """SELECT original_candidate_id
                    FROM serving_candidate_revisions WHERE revision_id = ?""",
                    (review.revision_id,),
                ).fetchone()["original_candidate_id"]
                connection.execute(
                    """INSERT INTO food_serving_candidate_events
                    (candidate_id, event_type, actor, message, occurred_at)
                    VALUES (?, 'candidate_revision_reviewed', ?, ?, ?)""",
                    (
                        original_id,
                        review.reviewer,
                        f"{review.revision_id} {review.decision}: {review.notes}",
                        review.decided_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateServingRevisionError(
                f"revision already reviewed or review ID conflicts: "
                f"{review.revision_id}"
            ) from error
        return review

    def get_review(self, revision_id: str) -> ServingRevisionReview | None:
        self.get(revision_id)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM serving_revision_reviews
                WHERE revision_id = ?""",
                (revision_id,),
            ).fetchone()
        if row is None:
            return None
        return ServingRevisionReview(
            review_id=row["review_id"],
            revision_id=row["revision_id"],
            decision=row["decision"],
            reviewer=row["reviewer"],
            notes=row["notes"],
            decided_at=row["decided_at"],
            simulation_only=bool(row["simulation_only"]),
        )


class ServingRevisionService:
    def __init__(
        self,
        candidate_repository: SQLiteServingCandidateRepository,
        revision_repository: SQLiteServingRevisionRepository,
        *,
        clock: Clock = _utc_now,
    ) -> None:
        self.candidate_repository = candidate_repository
        self.revision_repository = revision_repository
        self.clock = clock

    def _timestamp(self) -> str:
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc).isoformat()

    def create_revision(
        self,
        *,
        revision_id: str,
        original_candidate_id: str,
        serving_weight_grams: float,
        provenance: str,
        created_by: str,
    ) -> ServingCandidateRevision:
        values = (revision_id, original_candidate_id, provenance, created_by)
        if any(not value.strip() for value in values):
            raise ValueError("revision identifiers and provenance cannot be blank")
        if serving_weight_grams <= 0:
            raise ValueError("serving_weight_grams must be positive")

        candidate = self.candidate_repository.get(original_candidate_id)
        original_review = self.candidate_repository.get_review(
            original_candidate_id
        )
        if candidate.review_status != "mass_missing":
            raise ServingCandidateEligibilityError(
                "only mass_missing candidates may be revised in Stage 2.9"
            )
        if original_review is None or original_review.decision != "correction_required":
            raise ServingCandidateEligibilityError(
                "original candidate must have a correction_required review"
            )

        revision = ServingCandidateRevision(
            revision_id=revision_id,
            original_candidate_id=original_candidate_id,
            source_item_id=candidate.source_item_id,
            serving_quantity=candidate.serving_quantity,
            serving_unit_label=candidate.serving_unit_label,
            serving_weight_grams=serving_weight_grams,
            metric_quantity=candidate.metric_quantity,
            metric_unit=candidate.metric_unit,
            provenance=provenance,
            created_by=created_by,
            created_at=self._timestamp(),
        )
        return self.revision_repository.create(revision)

    def review_revision(
        self,
        *,
        review_id: str,
        revision_id: str,
        decision: str,
        reviewer: str,
        notes: str,
    ) -> ServingRevisionReview:
        values = (review_id, revision_id, reviewer, notes)
        if any(not value.strip() for value in values):
            raise ValueError("review identifiers, reviewer, and notes cannot be blank")
        if decision not in VALID_REVIEW_DECISIONS:
            raise ValueError(f"decision must be one of {VALID_REVIEW_DECISIONS}")
        self.revision_repository.get(revision_id)
        review = ServingRevisionReview(
            review_id=review_id,
            revision_id=revision_id,
            decision=decision,
            reviewer=reviewer,
            notes=notes,
            decided_at=self._timestamp(),
        )
        return self.revision_repository.record_review(review)
