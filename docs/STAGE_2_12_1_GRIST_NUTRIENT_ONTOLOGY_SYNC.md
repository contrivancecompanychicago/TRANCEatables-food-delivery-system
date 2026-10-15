# Stage 2.12.1: Grist nutrient-ontology mirror

Stage 2.12.1 mirrors the Stage 2.12 SQLite nutrient ontology into Grist for human-readable audit and dashboard use. SQLite remains authoritative.

## Destination tables

| Grist table | Stable key | SQLite source |
| --- | --- | --- |
| `MeasurementUnitDefinitions` | `UnitCode` | `measurement_unit_definitions` |
| `NutrientDefinitions` | `NutrientId` | `nutrient_definitions` |
| `NutrientMeasurementMappings` | `MappingId` | `nutrient_measurement_mappings` |
| `NutrientMappingReviews` | `ReviewId` | `nutrient_mapping_reviews` |
| `NutrientOntologyEvents` | `EventId` | `nutrient_ontology_events` |

Datetime values are converted to Grist epoch timestamps and simulation flags are converted to booleans. Null normalized values remain null.

## Dry-run-first workflow

Set credentials outside the repository:

```bash
export GRIST_BASE_URL="https://your-team.getgrist.com"
export GRIST_DOC_ID="your-document-id"
export GRIST_API_KEY="your-secret-api-key"
```

Preview changes without writing:

```bash
python -m tranceatables.grist_sync --database tranceatables.sqlite3
```

Apply only after reviewing the dry run:

```bash
python -m tranceatables.grist_sync --database tranceatables.sqlite3 --apply
```

A second dry run should report every synchronized ontology row as unchanged.

## Validated demonstration state

The Colab workflow validated this expected audit snapshot:

- 6 measurement-unit definitions
- 3 nutrient definitions
- 9 source-measurement mappings
- 9 human mapping reviews
- 27 ontology events

The six Daily Value observations remain `unconvertible`, and the three missing Magnesium observations remain `source_missing`. All nine reviews remain `correction_required`.

## Safety boundary

This synchronization:

- never reads Grist values back into SQLite;
- never converts Daily Value percentages into milligrams;
- never assigns meal-plan products;
- never advances an order;
- never creates or approves a robot mission;
- never emits a physical robot command.

Grist is an audit mirror only. Exact product-label or other validated absolute nutrient evidence must be recorded through a future correction workflow.
