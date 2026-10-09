"""Simulation-only abstract nutrient constraint solver for Stage 2.4.

The source coefficients and targets have no verified physical units. Results are
therefore labeled model_unit and must not be interpreted as servings, grams,
clinical targets, or dietary recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping, Sequence


class NutrientSolverError(ValueError):
    """Raised when reference rows cannot form a valid abstract system."""


@dataclass(frozen=True)
class MealConstraintSolution:
    nutrients: tuple[str, str, str]
    exact_food_quantities: tuple[str, str, str]
    food_quantities: tuple[float, float, float]
    calculated_targets: tuple[float, float, float]
    target_residuals: tuple[float, float, float]
    target_unit: str = "model_unit"
    food_quantity_unit: str = "model_unit"
    validation_status: str = "solved_unmapped"


def _fraction(value: Any, field: str) -> Fraction:
    if value is None or isinstance(value, bool):
        raise NutrientSolverError(f"{field} must be numeric")
    try:
        result = Fraction(str(value).strip())
    except (ValueError, ZeroDivisionError) as error:
        raise NutrientSolverError(f"{field} must be numeric") from error
    if result < 0:
        raise NutrientSolverError(f"{field} cannot be negative")
    return result


def _solve(matrix: list[list[Fraction]], targets: list[Fraction]) -> list[Fraction]:
    size = len(matrix)
    augmented = [row[:] + [target] for row, target in zip(matrix, targets)]

    for column in range(size):
        pivot = next(
            (row for row in range(column, size) if augmented[row][column] != 0),
            None,
        )
        if pivot is None:
            raise NutrientSolverError(
                "nutrient matrix is singular and has no unique solution"
            )
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]

        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    current - factor * pivot_value
                    for current, pivot_value in zip(
                        augmented[row], augmented[column]
                    )
                ]

    return [augmented[row][-1] for row in range(size)]


def _exact_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else (
        f"{value.numerator}/{value.denominator}"
    )


def solve_meal_references(
    records: Sequence[Mapping[str, Any]],
) -> MealConstraintSolution:
    """Solve three abstract food slots against three nutrient reference rows."""

    if len(records) != 3:
        raise NutrientSolverError(
            f"exactly three meal references are required; found {len(records)}"
        )

    identifiers: set[str] = set()
    nutrients: list[str] = []
    matrix: list[list[Fraction]] = []
    targets: list[Fraction] = []

    for index, record in enumerate(records, start=1):
        identifier = str(record.get("mealReferenceId", "")).strip()
        nutrient = str(record.get("nutrient", "")).strip()
        if not identifier or identifier in identifiers:
            raise NutrientSolverError(
                "mealReferenceId values must be nonblank and unique"
            )
        if not nutrient:
            raise NutrientSolverError(f"row {index} nutrient cannot be blank")
        identifiers.add(identifier)
        nutrients.append(nutrient)
        matrix.append(
            [
                _fraction(record.get("food1Amount"), f"{identifier}.food1Amount"),
                _fraction(record.get("food2Amount"), f"{identifier}.food2Amount"),
                _fraction(record.get("food3Amount"), f"{identifier}.food3Amount"),
            ]
        )
        targets.append(
            _fraction(record.get("targetAmount"), f"{identifier}.targetAmount")
        )

    quantities = _solve(matrix, targets)
    if any(quantity < 0 for quantity in quantities):
        raise NutrientSolverError(
            "solution contains a negative abstract food quantity"
        )

    calculated = [
        sum(coefficient * quantity for coefficient, quantity in zip(row, quantities))
        for row in matrix
    ]
    residuals = [
        calculated_value - target
        for calculated_value, target in zip(calculated, targets)
    ]
    if any(residual != 0 for residual in residuals):
        raise NutrientSolverError("exact solution failed residual validation")

    return MealConstraintSolution(
        nutrients=tuple(nutrients),  # type: ignore[arg-type]
        exact_food_quantities=tuple(  # type: ignore[arg-type]
            _exact_text(quantity) for quantity in quantities
        ),
        food_quantities=tuple(float(quantity) for quantity in quantities),  # type: ignore[arg-type]
        calculated_targets=tuple(float(value) for value in calculated),  # type: ignore[arg-type]
        target_residuals=tuple(float(value) for value in residuals),  # type: ignore[arg-type]
    )
