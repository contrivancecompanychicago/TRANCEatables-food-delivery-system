import pytest

from tranceatables.nutrient_solver import (
    NutrientSolverError,
    solve_meal_references,
)


REFERENCES = [
    {
        "mealReferenceId": "MEAL-NUTRIENT-001",
        "nutrient": "Vitamin C",
        "food1Amount": 10,
        "food2Amount": 20,
        "food3Amount": 20,
        "targetAmount": 100,
    },
    {
        "mealReferenceId": "MEAL-NUTRIENT-002",
        "nutrient": "Calcium",
        "food1Amount": 50,
        "food2Amount": 40,
        "food3Amount": 10,
        "targetAmount": 300,
    },
    {
        "mealReferenceId": "MEAL-NUTRIENT-003",
        "nutrient": "Magnesium",
        "food1Amount": 30,
        "food2Amount": 10,
        "food3Amount": 40,
        "targetAmount": 200,
    },
]


def test_solves_validated_abstract_system_exactly():
    solution = solve_meal_references(REFERENCES)

    assert solution.exact_food_quantities == ("50/11", "50/33", "40/33")
    assert solution.food_quantities == pytest.approx(
        (4.5454545455, 1.5151515152, 1.2121212121)
    )
    assert solution.calculated_targets == pytest.approx((100, 300, 200))
    assert solution.target_residuals == (0.0, 0.0, 0.0)
    assert solution.target_unit == "model_unit"
    assert solution.food_quantity_unit == "model_unit"
    assert solution.validation_status == "solved_unmapped"


def test_rejects_wrong_number_of_references():
    with pytest.raises(NutrientSolverError, match="exactly three"):
        solve_meal_references(REFERENCES[:2])


def test_rejects_singular_matrix():
    singular = [dict(row) for row in REFERENCES]
    singular[2].update(
        food1Amount=20,
        food2Amount=40,
        food3Amount=40,
    )
    with pytest.raises(NutrientSolverError, match="singular"):
        solve_meal_references(singular)


def test_rejects_negative_source_values():
    invalid = [dict(row) for row in REFERENCES]
    invalid[0]["food1Amount"] = -1
    with pytest.raises(NutrientSolverError, match="cannot be negative"):
        solve_meal_references(invalid)


def test_rejects_duplicate_reference_ids():
    invalid = [dict(row) for row in REFERENCES]
    invalid[1]["mealReferenceId"] = "MEAL-NUTRIENT-001"
    with pytest.raises(NutrientSolverError, match="unique"):
        solve_meal_references(invalid)
