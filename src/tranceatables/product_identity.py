"""Stage 2.11 immutable source-product identity verification.

Identity evidence and corrections are audit records only. They do not mutate the
original serving candidate or assign a product to a meal plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Callable


class ProductIdentityError(ValueError):
    pass


@dataclass(frozen=True)
class ProductIdentityVerification:
    verification_id: str
    candidate_id: str
    source_system: str
    local_item_id: str
    verified_item_id: str | None
    local_upc: str | None
    verified_upc: str | None
    brand_matches: bool
    item_name_matches: bool
    status: str
    evidence_json: str
    created_at: str
    simulation_only: bool = True


@dataclass(frozen=True)
class ProductIdentityReview:
    review_id: str
    verification_id: str
    decision: str
    reviewer: str
    notes: str
    decided_at: str
    simulation_only: bool = True


@dataclass(frozen=True)
class ProductIdentityCorrection:
    correction_id: str
    verification_id: str
    corrected_item_id: str
    provenance: str
    created_by: str
    created_at: str
    simulation_only: bool = True


@dataclass(frozen=True)
class ProductIdentityCorrectionReview:
    review_id: str
    correction_id: str
    decision: str
    reviewer: str
    notes: str
    decided_at: str
    simulation_only: bool = True


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SQLiteProductIdentityRepository:
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
            candidate_table = connection.execute(
                """SELECT 1 FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'food_serving_candidates'"""
            ).fetchone()
            if candidate_table is None:
                raise ProductIdentityError(
                    "food_serving_candidates must exist before identity verification"
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS product_identity_verifications (
                    verification_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL UNIQUE
                        REFERENCES food_serving_candidates(candidate_id),
                    source_system TEXT NOT NULL,
                    local_item_id TEXT NOT NULL,
                    verified_item_id TEXT,
                    local_upc TEXT,
                    verified_upc TEXT,
                    brand_matches INTEGER NOT NULL,
                    item_name_matches INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN (
                        'identity_verified',
                        'source_item_id_mismatch',
                        'identity_conflict',
                        'source_record_not_found'
                    )),
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1)
                );
                CREATE TABLE IF NOT EXISTS product_identity_reviews (
                    review_id TEXT PRIMARY KEY,
                    verification_id TEXT NOT NULL UNIQUE
                        REFERENCES product_identity_verifications(verification_id),
                    decision TEXT NOT NULL CHECK(decision IN (
                        'approved',
                        'identity_correction_required',
                        'rejected'
                    )),
                    reviewer TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1)
                );
                CREATE TABLE IF NOT EXISTS product_identity_corrections (
                    correction_id TEXT PRIMARY KEY,
                    verification_id TEXT NOT NULL UNIQUE
                        REFERENCES product_identity_verifications(verification_id),
                    corrected_item_id TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1)
                );
                CREATE TABLE IF NOT EXISTS product_identity_correction_reviews (
                    review_id TEXT PRIMARY KEY,
                    correction_id TEXT NOT NULL UNIQUE
                        REFERENCES product_identity_corrections(correction_id),
                    decision TEXT NOT NULL CHECK(decision IN (
                        'approved', 'rejected'
                    )),
                    reviewer TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    simulation_only INTEGER NOT NULL CHECK(simulation_only = 1)
                );
                """
            )

    def candidate(self, candidate_id: str) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM food_serving_candidates
                WHERE candidate_id = ?""",
                (candidate_id,),
            ).fetchone()
        if row is None:
            raise ProductIdentityError(f"candidate not found: {candidate_id}")
        return row

    def create_verification(
        self, verification: ProductIdentityVerification
    ) -> ProductIdentityVerification:
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO product_identity_verifications VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        verification.verification_id,
                        verification.candidate_id,
                        verification.source_system,
                        verification.local_item_id,
                        verification.verified_item_id,
                        verification.local_upc,
                        verification.verified_upc,
                        int(verification.brand_matches),
                        int(verification.item_name_matches),
                        verification.status,
                        verification.evidence_json,
                        verification.created_at,
                        int(verification.simulation_only),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ProductIdentityError(
                "identity verification already exists or conflicts"
            ) from error
        return verification

    def get_verification(self, verification_id: str) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM product_identity_verifications
                WHERE verification_id = ?""",
                (verification_id,),
            ).fetchone()
        if row is None:
            raise ProductIdentityError(
                f"verification not found: {verification_id}"
            )
        return row

    def create_review(
        self, review: ProductIdentityReview
    ) -> ProductIdentityReview:
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO product_identity_reviews VALUES
                    (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        review.review_id,
                        review.verification_id,
                        review.decision,
                        review.reviewer,
                        review.notes,
                        review.decided_at,
                        int(review.simulation_only),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ProductIdentityError(
                "identity verification already reviewed or review conflicts"
            ) from error
        return review

    def get_review(self, verification_id: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                """SELECT * FROM product_identity_reviews
                WHERE verification_id = ?""",
                (verification_id,),
            ).fetchone()

    def create_correction(
        self, correction: ProductIdentityCorrection
    ) -> ProductIdentityCorrection:
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO product_identity_corrections VALUES
                    (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        correction.correction_id,
                        correction.verification_id,
                        correction.corrected_item_id,
                        correction.provenance,
                        correction.created_by,
                        correction.created_at,
                        int(correction.simulation_only),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ProductIdentityError(
                "identity correction already exists or conflicts"
            ) from error
        return correction

    def get_correction(self, correction_id: str) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM product_identity_corrections
                WHERE correction_id = ?""",
                (correction_id,),
            ).fetchone()
        if row is None:
            raise ProductIdentityError(
                f"correction not found: {correction_id}"
            )
        return row

    def create_correction_review(
        self, review: ProductIdentityCorrectionReview
    ) -> ProductIdentityCorrectionReview:
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO product_identity_correction_reviews VALUES
                    (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        review.review_id,
                        review.correction_id,
                        review.decision,
                        review.reviewer,
                        review.notes,
                        review.decided_at,
                        int(review.simulation_only),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ProductIdentityError(
                "identity correction already reviewed or review conflicts"
            ) from error
        return review


class ProductIdentityService:
    def __init__(
        self,
        repository: SQLiteProductIdentityRepository,
        *,
        clock: Clock = _utc_now,
    ) -> None:
        self.repository = repository
        self.clock = clock

    def _timestamp(self) -> str:
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc).isoformat()

    def verify(
        self,
        *,
        verification_id: str,
        candidate_id: str,
        source_system: str,
        verified_item_id: str | None,
        verified_upc: str | None,
        verified_brand_name: str | None,
        verified_item_name: str | None,
        evidence: dict[str, object],
    ) -> ProductIdentityVerification:
        if any(
            not value.strip()
            for value in (verification_id, candidate_id, source_system)
        ):
            raise ValueError("verification identifiers cannot be blank")

        candidate = self.repository.candidate(candidate_id)
        local_upc = candidate["source_upc"]
        brand_matches = (
            verified_brand_name is not None
            and candidate["brand_name"].casefold()
            == verified_brand_name.casefold()
        )
        item_name_matches = (
            verified_item_name is not None
            and candidate["item_name"].casefold()
            == verified_item_name.casefold()
        )

        if verified_item_id is None:
            status = "source_record_not_found"
        elif (
            candidate["source_item_id"] == verified_item_id
            and str(local_upc) == str(verified_upc)
            and brand_matches
            and item_name_matches
        ):
            status = "identity_verified"
        elif (
            str(local_upc) == str(verified_upc)
            and brand_matches
            and item_name_matches
        ):
            status = "source_item_id_mismatch"
        else:
            status = "identity_conflict"

        verification = ProductIdentityVerification(
            verification_id=verification_id,
            candidate_id=candidate_id,
            source_system=source_system,
            local_item_id=candidate["source_item_id"],
            verified_item_id=verified_item_id,
            local_upc=local_upc,
            verified_upc=verified_upc,
            brand_matches=brand_matches,
            item_name_matches=item_name_matches,
            status=status,
            evidence_json=json.dumps(evidence, sort_keys=True),
            created_at=self._timestamp(),
        )
        return self.repository.create_verification(verification)

    def review(
        self,
        *,
        review_id: str,
        verification_id: str,
        decision: str,
        reviewer: str,
        notes: str,
    ) -> ProductIdentityReview:
        if decision not in (
            "approved",
            "identity_correction_required",
            "rejected",
        ):
            raise ValueError("invalid identity review decision")
        verification = self.repository.get_verification(verification_id)
        if (
            decision == "approved"
            and verification["status"] != "identity_verified"
        ):
            raise ProductIdentityError(
                "only identity_verified evidence may be approved directly"
            )
        if (
            decision == "identity_correction_required"
            and verification["status"] != "source_item_id_mismatch"
        ):
            raise ProductIdentityError(
                "correction requires source_item_id_mismatch evidence"
            )
        review = ProductIdentityReview(
            review_id=review_id,
            verification_id=verification_id,
            decision=decision,
            reviewer=reviewer,
            notes=notes,
            decided_at=self._timestamp(),
        )
        return self.repository.create_review(review)

    def correct(
        self,
        *,
        correction_id: str,
        verification_id: str,
        corrected_item_id: str,
        provenance: str,
        created_by: str,
    ) -> ProductIdentityCorrection:
        if any(
            not value.strip()
            for value in (
                correction_id,
                verification_id,
                corrected_item_id,
                provenance,
                created_by,
            )
        ):
            raise ValueError("correction fields cannot be blank")
        verification = self.repository.get_verification(verification_id)
        review = self.repository.get_review(verification_id)
        if verification["status"] != "source_item_id_mismatch":
            raise ProductIdentityError("only an item-ID mismatch may be corrected")
        if (
            review is None
            or review["decision"] != "identity_correction_required"
        ):
            raise ProductIdentityError(
                "identity_correction_required review is required"
            )
        if corrected_item_id != verification["verified_item_id"]:
            raise ProductIdentityError(
                "corrected item ID must match verified source evidence"
            )
        correction = ProductIdentityCorrection(
            correction_id=correction_id,
            verification_id=verification_id,
            corrected_item_id=corrected_item_id,
            provenance=provenance,
            created_by=created_by,
            created_at=self._timestamp(),
        )
        return self.repository.create_correction(correction)

    def review_correction(
        self,
        *,
        review_id: str,
        correction_id: str,
        decision: str,
        reviewer: str,
        notes: str,
    ) -> ProductIdentityCorrectionReview:
        if decision not in ("approved", "rejected"):
            raise ValueError("correction decision must be approved or rejected")
        self.repository.get_correction(correction_id)
        review = ProductIdentityCorrectionReview(
            review_id=review_id,
            correction_id=correction_id,
            decision=decision,
            reviewer=reviewer,
            notes=notes,
            decided_at=self._timestamp(),
        )
        return self.repository.create_correction_review(review)
