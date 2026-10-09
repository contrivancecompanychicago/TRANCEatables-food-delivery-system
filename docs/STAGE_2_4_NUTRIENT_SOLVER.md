# Stage 2.4: abstract nutrient constraint solver

Stage 2.4 solves the three supplied MealReferences as an abstract linear
system. It does not assign grocery products, prescribe food, or advance an
order.

## Model

```text
10 Food1 + 20 Food2 + 20 Food3 = 100  (Vitamin C)
50 Food1 + 40 Food2 + 10 Food3 = 300  (Calcium)
30 Food1 + 10 Food2 + 40 Food3 = 200  (Magnesium)
```

The exact solution is:

| Slot | Exact | Decimal |
| --- | ---: | ---: |
| Food1 | 50/11 | 4.5454545 |
| Food2 | 50/33 | 1.5151515 |
| Food3 | 40/33 | 1.2121212 |

All residuals are exactly zero.

## Interpretation boundary

The source workbook does not define physical units for the coefficients,
targets, or food quantities. GroceryItems reports Vitamin C and Calcium as
percent Daily Value, while Magnesium is absent. Consequently:

- target and quantity units are labeled `model_unit`;
- status is `solved_unmapped`;
- Food1, Food2, and Food3 remain abstract slots;
- orange juice, milk, and other products are not assigned to these slots;
- results are not servings, grams, clinical targets, or dietary advice.

## Google Colab

```python
from tranceatables.nutrient_solver import solve_meal_references
from tranceatables.sheety_reference import SheetyReferenceClient

references = (
    SheetyReferenceClient.from_environment()
    .get_meal_references()
)

solution = solve_meal_references(references)

print("Nutrients:", solution.nutrients)
print("Exact quantities:", solution.exact_food_quantities)
print("Decimal quantities:", solution.food_quantities)
print("Calculated targets:", solution.calculated_targets)
print("Residuals:", solution.target_residuals)
print("Target unit:", solution.target_unit)
print("Quantity unit:", solution.food_quantity_unit)
print("Status:", solution.validation_status)
print("Order advanced:", False)
print("Robot mission created:", False)
```

Expected status:

```text
Exact quantities: ('50/11', '50/33', '40/33')
Calculated targets: (100.0, 300.0, 200.0)
Residuals: (0.0, 0.0, 0.0)
Target unit: model_unit
Quantity unit: model_unit
Status: solved_unmapped
Order advanced: False
Robot mission created: False
```

## Validation

The solver uses exact rational arithmetic and:

- requires exactly three reference rows and three food slots;
- requires unique, nonblank reference IDs and nutrient labels;
- rejects missing, nonnumeric, or negative coefficients and targets;
- rejects singular systems without a unique solution;
- rejects negative solutions;
- verifies exact zero residuals.

It uses only Python's standard library. NumPy is not required by repository
code.

## Next data requirement

Product mapping remains blocked until a curated source supplies compatible
units for all three nutrients, including Magnesium, together with serving-size
definitions. Any future mapping must preserve source provenance and distinguish
label Daily Value percentages from nutrient masses.
