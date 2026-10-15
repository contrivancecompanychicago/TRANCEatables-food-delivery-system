# Stage 2.12.2 — Exact nutrient-evidence gating

Stage 2.12.2 records what is known—and what is still missing—about absolute
nutrient amounts for the exact branded products selected by the simulation.

## Persistence

- `nutrient_evidence_records` stores product identity, nutrient, serving basis,
  source reference, optional absolute value, status, and provenance.
- `nutrient_evidence_reviews` stores one immutable human decision per record.
- `nutrient_evidence_events` provides an append-only audit trail.

An `evidence_required` record must have null value and unit fields. A
`not_declared_on_label` record also has no value: absence is unknown, not zero.
Evidence marked `pending_review` or `validated` must contain a nonnegative value
in `mg`. Approval is permitted only for a `validated` record.

## Evidence policy

Acceptable evidence identifies the exact product and retains an exact label,
manufacturer, or verified retailer reference. A serving quantity, serving unit,
and optional gram weight are stored separately from the nutrient amount.

The implementation rejects:

- `%DV` presented as an absolute milligram value;
- `model_unit` converted into a physical unit;
- a similar product substituted for an unmatched UPC;
- missing Magnesium interpreted as zero; and
- approval of unresolved evidence.

## Safety boundary

This stage is an evidence and audit subsystem. It does not provide dietary or
medical advice, assign meal-plan products, advance an order, create a robot
mission, or dispatch physical hardware. Grist mirroring is intentionally
deferred until dedicated destination tables are created and verified.
