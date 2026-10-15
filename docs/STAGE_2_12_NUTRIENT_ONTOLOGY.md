# Stage 2.12: Nutrient measurement ontology

Stage 2.12 creates a deterministic, simulation-only vocabulary for nutrient measurements. It preserves the Stage 2.4 solver's abstract `model_unit` output while preparing independently sourced food measurements for human review.

## Persistence

| Table | Purpose |
| --- | --- |
| `measurement_unit_definitions` | Defines unit identity, dimension, and conversion status |
| `nutrient_definitions` | Defines nutrients, measurement basis, and canonical unit |
| `nutrient_measurement_mappings` | Records one source observation per meal-plan slot and nutrient |
| `nutrient_mapping_reviews` | Records one immutable human decision per mapping |
| `nutrient_ontology_events` | Append-only audit history |

## Measurement boundaries

The ontology distinguishes:

- `absolute_mass`, such as milligrams;
- `daily_value_percent`, a relative label value requiring reference context; and
- `abstract_model`, the dimensionless values used by the original solver.

`model_unit` is not a physical unit. `%DV` is not automatically equivalent to milligrams. A cross-unit normalization is rejected until a separate validated conversion rule exists. A missing source measurement is represented explicitly with `source_missing`; it is never imputed.

## Review rules

- Only a mapping with status `validated` can be approved.
- A validated mapping must contain a normalized value and unit.
- In this first ontology layer, validated mappings must retain the same source and normalized unit.
- Definitions, mappings, reviews, and events are append-only in normal service use.
- Duplicate slot-and-nutrient mappings for a meal plan are rejected.

## Safety boundary

Stage 2.12 does not modify the existing meal plan, replace `model_unit`, assign product IDs, provide dietary advice, advance an order, create a robot mission, write to Grist, or dispatch a physical robot.
