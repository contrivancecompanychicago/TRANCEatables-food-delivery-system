# Stage 1 - Order Lifecycle and Persistence

## Purpose

Stage 1 turns the Stage 0 feasibility prototype into an auditable order workflow. It remains simulation-only and does not dispatch or control a physical robot.

## Lifecycle

`draft -> accepted -> prepared -> packaged -> ready -> assigned`

Every non-cancelled state may transition to `cancelled`. Cancelled orders are terminal. Skipping stages, reversing an order, or repeating the current state is rejected.

## Persistence

`SQLiteOrderRepository` stores operational order data in SQLite using two tables:

- `orders`: the current order snapshot and integer version.
- `order_events`: append-only creation and transition history.

The repository uses a transaction for each transition. Optional `expected_version` checks protect callers from silently overwriting a newer update.

## Service boundary

`OrderService` is API-neutral. A future web API, dashboard, CLI, or MCP server can call the same methods:

- `create_order`
- `get_order`
- `transition`
- `get_history`

## Privacy and safety

Stage 1 stores opaque order IDs and operational attributes only. Do not store names, medical conditions, Medicaid identifiers, payment credentials, phone numbers, or private addresses in this database.

## Acceptance criteria

- [x] Valid transitions follow the declared sequence.
- [x] Invalid transitions do not modify the order or audit history.
- [x] Orders survive repository reinitialization.
- [x] Every successful transition appends one audit event.
- [x] Duplicate IDs and stale versions are rejected.
- [x] Stage 0 feasibility tests continue to pass.

## Next stage

Stage 1.5 may expose read-only resources and simulation-only order tools through a TRANCEatables MCP server. Physical robot control remains out of scope.
