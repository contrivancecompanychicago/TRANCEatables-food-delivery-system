# Stage 2.11.1: Grist identity-audit mirror

Stage 2.11.1 mirrors the immutable Stage 2.11 product-identity audit trail from authoritative SQLite storage into Grist. It does not perform product assignment or change operational state.

## Mirrored tables

| SQLite source | Grist destination | Stable key |
| --- | --- | --- |
| `product_identity_verifications` | `ProductIdentityVerifications` | `VerificationId` |
| `product_identity_reviews` | `ProductIdentityReviews` | `ReviewId` |
| `product_identity_corrections` | `ProductIdentityCorrections` | `CorrectionId` |
| `product_identity_correction_reviews` | `ProductIdentityCorrectionReviews` | `ReviewId` |

Boolean values and ISO 8601 timestamps are converted to Grist-compatible values. Evidence JSON remains text so the full source comparison is preserved.

## Safety and authority boundary

- SQLite remains authoritative.
- The default command is a read-only dry run.
- Grist writes occur only when `--apply` is supplied.
- Every configured destination schema is checked before any write starts.
- Synchronization uses stable-key idempotent creates and updates.
- The sync cannot overwrite serving candidates, assign products to a meal plan, advance an order, create a robot mission, or dispatch a physical robot.

## Colab dry run

Configure `GRIST_BASE_URL`, `GRIST_DOC_ID`, and `GRIST_API_KEY`, then run:

```bash
python -m tranceatables.grist_sync \
  --database /content/tranceatables-demo.sqlite3
```

For the validated Stage 2.11 dataset, the first dry run should report three identity verifications, three verification reviews, one correction, and one correction review as pending creates.

Review the dry-run output before using `--apply`. After a successful apply, a second dry run should show those eight records as unchanged.
