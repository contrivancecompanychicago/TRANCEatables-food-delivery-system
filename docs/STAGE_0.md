# Stage 0 — Foundation and Feasibility

## Purpose

Stage 0 creates the shared vocabulary and smallest executable rule set for TRANCEatables Food Services and a future autonomous delivery workflow. It is simulation-only and intentionally conservative.

## Initial service hypothesis

A food-service operator can accept an order, package it for the required handling class, screen a simulated robot for payload/range/battery constraints, and produce an auditable feasibility decision before dispatch.

## Actors

- Customer: requests an order and receives it through an agreed handoff.
- Food-service operator: prepares, labels, packages, and releases an order.
- Dispatcher: selects a suitable delivery resource and supervises exceptions.
- Simulated robot: exposes operational state, capacity, range, and battery.
- Human safety operator: can prevent or stop dispatch and handle incidents.

## Stage 0 workflow

1. Create a delivery request.
2. Assign a food-handling class: ambient, chilled, or hot.
3. Confirm packaging when temperature control is needed.
4. Read a simulated robot state.
5. Evaluate payload, round-trip range plus reserve, battery floor, and operational state.
6. Return a decision with machine-readable reason codes.
7. Do not dispatch; record what must be built and validated in later stages.

## Non-goals

- Physical robot control, navigation, obstacle avoidance, or remote operation
- Claims that a meal treats, prevents, or cures disease
- Clinical decision support or individualized nutrition prescriptions
- Compliance certification for food service, privacy, accessibility, traffic, or robotics
- Live payments, ordering, customer location storage, or production telemetry

## Safety gates for later stages

Before any public-road or sidewalk pilot: identify the operating design domain; verify applicable Chicago, Illinois, and federal requirements; perform food-safety and accessibility reviews; add secure identity and audit logging; validate fail-safe behavior; establish trained human oversight; and obtain appropriate insurance and institutional approvals.

## Stage 0 exit criteria

- [x] Repository purpose and boundaries documented
- [x] Source registry created
- [x] Core request and robot-state models implemented
- [x] Deterministic feasibility rules implemented
- [x] Acceptance tests cover approval and multi-reason rejection
- [ ] Stakeholders approve Stage 1 requirements

## Proposed Stage 1

Add an order lifecycle (`draft -> accepted -> prepared -> packaged -> ready -> assigned -> cancelled`) with SQLite persistence, audit events, validation, and API-neutral service functions. Dispatch and physical control remain out of scope.
