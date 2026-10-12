# Stage 2.9.1 — Grist serving-review audit mirror

## Purpose

This stage mirrors the Stage 2.7–2.9 serving-review audit trail from authoritative SQLite into Grist. Grist remains a dashboard and reporting copy.

## Table mappings

| SQLite table | Grist table | Stable key |
| --- | --- | --- |
| `food_serving_candidates` | `ServingCandidates` | `CandidateId` |
| `serving_candidate_reviews` | `ServingCandidateReviews` | `ReviewId` |
| `serving_candidate_revisions` | `ServingCandidateRevisions` | `RevisionId` |
| `serving_revision_reviews` | `ServingRevisionReviews` | `ReviewId` |

Datetime values are converted to Grist epoch values and integer simulation flags are converted to booleans. Nullable source UPC, gram weight, and metric fields remain nullable.

## Safety and authority

- SQLite is authoritative.
- Synchronization is one-way from SQLite to Grist.
- The default command is a dry run.
- Writes require the explicit `--apply` option.
- Every destination schema is validated before any write begins.
- Stable-key upserts make repeated runs idempotent.
- The sync does not assign products, map abstract nutrient units, advance orders, create missions, or dispatch robots.

## Colab workflow

After loading `GRIST_BASE_URL`, `GRIST_DOC_ID`, and `GRIST_API_KEY` securely:

```bash
python -m tranceatables.grist_sync --database /content/tranceatables-demo.sqlite3
python -m tranceatables.grist_sync --database /content/tranceatables-demo.sqlite3 --apply
python -m tranceatables.grist_sync --database /content/tranceatables-demo.sqlite3
```

For the validated demonstration dataset, the first dry run should plan 3 candidate creates, 3 candidate-review creates, 1 revision create, and 1 revision-review create. After apply, the final dry run should report all eight as unchanged.

Never print, commit, or place the Grist API key in notebook source.
