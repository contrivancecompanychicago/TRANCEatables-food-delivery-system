"""CULAPSE Data Farm evidence adapter for simulation-only checkpoints."""

from __future__ import annotations

from typing import Any


SOURCE = {
    "source_id": "culapse-kaggriculture-agent-lab-2026-09-17",
    "title": "Kaggriculture Agent Lab - CULAPSEDataFarm Site Documentation",
    "source_date": "2026-09-17",
    "scope": "simulated WHEAT production, harvest, inventory, sale, and reinvestment",
    "stage_fit": {
        "planned": {
            "fit": "strong",
            "supports": [
                "farm-state observation",
                "production, maintenance, labor, and capital diagnostics",
                "stability classification",
                "state-driven action planning",
            ],
        },
        "harvested": {
            "fit": "strong",
            "supports": [
                "harvest lifecycle action",
                "potential-versus-collected yield",
                "FPP-05 harvest bottleneck detection",
                "inventory and event telemetry",
            ],
        },
        "farm_packed": {
            "fit": "not_supported",
            "missing": [
                "food-grade packaging verification",
                "sealed lot and label record",
                "sanitation checkpoint",
                "packing temperature observation",
                "packaging integrity checkpoint",
            ],
        },
    },
    "boundary": "Research simulation evidence only; not a food-safety or regulatory certification.",
}


def _fraction(value: float, name: str) -> float:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return value


def evaluate_planning_checkpoint(
    production_reliability: float,
    maintenance_feasibility: float,
    capital_sufficiency: float,
) -> dict[str, Any]:
    """Apply the PDF's revised P x Mf x C simulation model."""
    p = _fraction(production_reliability, "production_reliability")
    mf = _fraction(maintenance_feasibility, "maintenance_feasibility")
    c = _fraction(capital_sufficiency, "capital_sufficiency")
    stability = p * mf * c
    if stability >= 0.80:
        classification = "stable"
    elif stability >= 0.60:
        classification = "watch"
    elif stability >= 0.40:
        classification = "unstable"
    else:
        classification = "production_crisis"
    return {
        "stage": "planned",
        "stability": round(stability, 6),
        "classification": classification,
        "model": "S = P x Mf x C",
        "source_id": SOURCE["source_id"],
        "simulation_only": True,
    }


def evaluate_harvest_checkpoint(
    potential_yield_units: float,
    collected_yield_units: float,
) -> dict[str, Any]:
    """Calculate harvest completion and the PDF's FPP-05 signal."""
    if potential_yield_units < 0 or collected_yield_units < 0:
        raise ValueError("yield values cannot be negative")
    if collected_yield_units > potential_yield_units:
        raise ValueError("collected yield cannot exceed potential yield")
    loss = potential_yield_units - collected_yield_units
    completion = (
        collected_yield_units / potential_yield_units
        if potential_yield_units
        else 0.0
    )
    return {
        "stage": "harvested",
        "potential_yield_units": potential_yield_units,
        "collected_yield_units": collected_yield_units,
        "routing_loss_units": loss,
        "completion_fraction": round(completion, 6),
        "diagnostic": "FPP-05" if loss > 0 else "FPP-00",
        "source_id": SOURCE["source_id"],
        "simulation_only": True,
    }
