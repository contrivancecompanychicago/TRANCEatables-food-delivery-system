"""Stage 2.10 read-only product-mapping readiness evaluation.

The evaluator resolves approved effective serving records but never writes to
SQLite, assigns products, advances orders, creates missions, or dispatches
hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3


class MappingReadinessError(RuntimeError):
    """Raised when the readiness report cannot be produced safely."""


@dataclass(frozen=True)
class EffectiveServingRecord:
    food_slot: int
    candidate_id: str
    revision_id: str | None
    source_item_id: str
    item_name: str
    serving_quantity: float
    serving_unit_label: str
    serving_weight_grams: float
    metric_quantity: float | None
    metric_unit: str | None
    approval_source: str
    simulation_only: bool = True


@dataclass(frozen=True)
class ProductMappingReadinessReport:
    meal_plan_id: str
    plan_status: str
    nutrients: tuple[str, ...]
    target_unit: str
    quantity_unit: str
    food_item_ids: tuple[str | None, ...]
    effective_records: tuple[EffectiveServingRecord, ...]
    serving_records_ready: bool
    product_mapping_ready: bool
    blockers: tuple[str, ...]
    simulation_only: bool = True


def _readonly_connection(database_path: str | Path) -> sqlite3.Connection:
    path = Path(database_path).resolve()
    if not path.is_file():
        raise MappingReadinessError(f"SQLite database not found: {path}")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def evaluate_product_mapping_readiness(
    database_path: str | Path,
    meal_plan_id: str,
) -> ProductMappingReadinessReport:
    """Return a deterministic report without modifying any persisted state."""
    if not meal_plan_id.strip():
        raise ValueError("meal_plan_id cannot be blank")

    with _readonly_connection(database_path) as connection:
        plan = connection.execute(
            """SELECT * FROM simulated_meal_plans
            WHERE meal_plan_id = ?""",
            (meal_plan_id,),
        ).fetchone()
        if plan is None:
            raise MappingReadinessError(
                f"meal plan not found: {meal_plan_id}"
            )

        candidates = connection.execute(
            """SELECT c.*, r.decision AS candidate_decision
            FROM food_serving_candidates c
            LEFT JOIN serving_candidate_reviews r
                ON r.candidate_id = c.candidate_id
            WHERE c.meal_plan_id = ?
            ORDER BY c.food_slot, c.candidate_id""",
            (meal_plan_id,),
        ).fetchall()

        effective_by_slot: dict[int, list[EffectiveServingRecord]] = {
            1: [],
            2: [],
            3: [],
        }

        for candidate in candidates:
            decision = candidate["candidate_decision"]
            if (
                decision == "approved"
                and candidate["review_status"] == "structurally_valid"
                and candidate["serving_weight_grams"] is not None
            ):
                effective_by_slot[candidate["food_slot"]].append(
                    EffectiveServingRecord(
                        food_slot=candidate["food_slot"],
                        candidate_id=candidate["candidate_id"],
                        revision_id=None,
                        source_item_id=candidate["source_item_id"],
                        item_name=candidate["item_name"],
                        serving_quantity=candidate["serving_quantity"],
                        serving_unit_label=candidate["serving_unit_label"],
                        serving_weight_grams=candidate["serving_weight_grams"],
                        metric_quantity=candidate["metric_quantity"],
                        metric_unit=candidate["metric_unit"],
                        approval_source="candidate_review",
                    )
                )
            elif decision == "correction_required":
                revisions = connection.execute(
                    """SELECT revision.*, review.decision
                    FROM serving_candidate_revisions revision
                    JOIN serving_revision_reviews review
                        ON review.revision_id = revision.revision_id
                    WHERE revision.original_candidate_id = ?
                      AND review.decision = 'approved'
                    ORDER BY revision.revision_id""",
                    (candidate["candidate_id"],),
                ).fetchall()
                for revision in revisions:
                    effective_by_slot[candidate["food_slot"]].append(
                        EffectiveServingRecord(
                            food_slot=candidate["food_slot"],
                            candidate_id=candidate["candidate_id"],
                            revision_id=revision["revision_id"],
                            source_item_id=revision["source_item_id"],
                            item_name=candidate["item_name"],
                            serving_quantity=revision["serving_quantity"],
                            serving_unit_label=revision["serving_unit_label"],
                            serving_weight_grams=revision[
                                "serving_weight_grams"
                            ],
                            metric_quantity=revision["metric_quantity"],
                            metric_unit=revision["metric_unit"],
                            approval_source="revision_review",
                        )
                    )

        blockers: list[str] = []
        effective_records: list[EffectiveServingRecord] = []
        for slot in (1, 2, 3):
            records = effective_by_slot[slot]
            if not records:
                blockers.append(f"food_slot_{slot}_has_no_approved_record")
            elif len(records) > 1:
                blockers.append(
                    f"food_slot_{slot}_has_multiple_approved_records"
                )
            else:
                effective_records.append(records[0])

        serving_records_ready = len(effective_records) == 3 and not any(
            blocker.startswith("food_slot_") for blocker in blockers
        )

        food_item_ids = (
            plan["food1_item_id"],
            plan["food2_item_id"],
            plan["food3_item_id"],
        )
        nutrients = tuple(json.loads(plan["nutrients_json"]))

        if not bool(plan["simulation_only"]):
            blockers.append("meal_plan_is_not_simulation_only")
        if plan["status"] != "solved_unmapped":
            blockers.append("meal_plan_status_is_not_solved_unmapped")
        if any(food_item_ids):
            blockers.append("meal_plan_already_has_product_assignments")
        if plan["target_unit"] == "model_unit":
            blockers.append("target_unit_is_unmapped_model_unit")
        if plan["quantity_unit"] == "model_unit":
            blockers.append("quantity_unit_is_unmapped_model_unit")
        if any(value.casefold() == "magnesium" for value in nutrients):
            blockers.append("magnesium_product_mapping_is_unvalidated")

        # Stage 2.10 has no validated nutrient-to-product mapping artifact.
        blockers.append("nutrient_product_mapping_not_validated")

        return ProductMappingReadinessReport(
            meal_plan_id=meal_plan_id,
            plan_status=plan["status"],
            nutrients=nutrients,
            target_unit=plan["target_unit"],
            quantity_unit=plan["quantity_unit"],
            food_item_ids=food_item_ids,
            effective_records=tuple(effective_records),
            serving_records_ready=serving_records_ready,
            product_mapping_ready=False,
            blockers=tuple(dict.fromkeys(blockers)),
            simulation_only=True,
        )
