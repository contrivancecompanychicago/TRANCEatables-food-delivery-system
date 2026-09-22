import pytest

from tranceatables.culapse_adapter import (
    SOURCE,
    evaluate_harvest_checkpoint,
    evaluate_planning_checkpoint,
)


def test_stage_mapping_accepts_planning_and_harvest_not_packing() -> None:
    assert SOURCE["stage_fit"]["planned"]["fit"] == "strong"
    assert SOURCE["stage_fit"]["harvested"]["fit"] == "strong"
    assert SOURCE["stage_fit"]["farm_packed"]["fit"] == "not_supported"
    assert "food-grade packaging verification" in SOURCE["stage_fit"]["farm_packed"]["missing"]


def test_planning_checkpoint_uses_revised_model() -> None:
    result = evaluate_planning_checkpoint(0.9, 0.95, 0.98)
    assert result["stability"] == 0.8379
    assert result["classification"] == "stable"
    assert result["stage"] == "planned"


def test_planning_checkpoint_validates_fractions() -> None:
    with pytest.raises(ValueError):
        evaluate_planning_checkpoint(1.1, 0.9, 0.9)


def test_harvest_checkpoint_reproduces_document_example() -> None:
    result = evaluate_harvest_checkpoint(12, 9)
    assert result["routing_loss_units"] == 3
    assert result["completion_fraction"] == 0.75
    assert result["diagnostic"] == "FPP-05"


def test_harvest_checkpoint_rejects_impossible_yield() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        evaluate_harvest_checkpoint(9, 12)
