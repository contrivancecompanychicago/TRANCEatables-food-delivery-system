# Simulation-only farm-to-fork delivery

This update adds an auditable food-lot trace to the TRANCEatables MCP server. It models the handoffs between farm, transportation, kitchen, meal preparation, and final delivery without contacting a real vendor or controlling a robot.

## Lifecycle

```text
planned
  -> harvested
  -> farm_packed
  -> picked_up
  -> kitchen_received
  -> meal_prepared
  -> meal_packaged
  -> out_for_delivery
  -> delivered
```

Every active stage can transition to `cancelled`. Stages cannot be skipped, and delivered or cancelled traces are terminal.

## Trace record

Each trace stores:

- an opaque `trace_id`
- an opaque `farm_code`
- an opaque `product_code`
- an optional simulated `order_id`
- current status and version
- creation and update timestamps

Each transition appends an event containing the actor, optional location code, optional observed temperature, optional note, timestamp, and version. A temperature is an observation only; the system does not certify food safety.

## MCP interface

Resources:

- `tranceatables://farm-to-fork/{trace_id}`
- `tranceatables://farm-to-fork/{trace_id}/history`

Tools:

- `create_simulated_farm_to_fork_trace`
- `get_simulated_farm_to_fork_trace`
- `get_simulated_farm_to_fork_history`
- `transition_simulated_farm_to_fork_trace`

## Example

Create a trace:

```json
{
  "trace_id": "TRACE-100",
  "farm_code": "FARM-CHI-1",
  "product_code": "KALE-LOT-2026-01",
  "order_id": "SIM-100"
}
```

Record harvest:

```json
{
  "trace_id": "TRACE-100",
  "target_status": "harvested",
  "location_code": "FIELD-A",
  "temperature_c": 18.5,
  "note": "simulation harvest",
  "expected_version": 0
}
```

Continue one stage at a time until `delivered`, reading the history after each handoff.

## Data and safety boundary

Use test identifiers only. Do not enter names, street addresses, health information, payment data, credentials, or secrets. This feature does not dispatch vehicles, direct food handling, contact customers, place orders, or certify regulatory compliance.
