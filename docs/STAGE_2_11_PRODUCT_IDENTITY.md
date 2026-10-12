# Stage 2.11 — Source-product identity verification

## Purpose

Preserve external source evidence and human decisions without overwriting reviewed serving candidates.

## Persistence

- `product_identity_verifications` stores the local identity, observed source identity, comparison results, status, and evidence.
- `product_identity_reviews` stores one human decision for each verification.
- `product_identity_corrections` stores a corrected item ID separately from the original candidate.
- `product_identity_correction_reviews` stores one human decision for each correction.

## Status rules

- `identity_verified`: item ID, UPC, brand, and item name match.
- `source_item_id_mismatch`: UPC, brand, and item name match, but item ID differs.
- `identity_conflict`: source evidence conflicts beyond the item ID.
- `source_record_not_found`: no source record was found.

Only `identity_verified` evidence may be approved directly. An item-ID mismatch must receive `identity_correction_required` before a correction can be created. The corrected ID must equal the ID captured in the source evidence, and the correction receives a separate approval or rejection.

## Validated demonstration

- Orange Juice: identity verified.
- Milk: identity verified.
- Tomatoes: local ID `51c3e9f397c3e6d8d3b4a63`; verified Sheety ID `51c3e9f397c3e6de73cb9a63`; UPC, brand, item name, and serving evidence match.

## Safety boundary

The original serving candidate remains unchanged. Stage 2.11 cannot populate meal-plan product IDs, advance an order, create a mission, dispatch a robot, or write to Sheety or Grist.
