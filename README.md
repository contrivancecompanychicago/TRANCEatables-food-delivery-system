# TRANCEatables Food Delivery System

Stage 1.5 adds a local, simulation-only Model Context Protocol (MCP) server to the auditable Stage 1 order lifecycle.

## Stage 0 goal

Answer one question before route optimization or robot integration begins:

> Is a proposed food delivery request operationally feasible under basic food-safety, payload, range, and service constraints?

This repository is an early research and software prototype. It does **not** provide medical advice, replace clinical care, certify food safety, or control a physical robot.

## Quick start

```bash
python -m pip install -e '.[dev]'
python -m pytest
python -m tranceatables.demo
```

## DoorDash Drive API integration

`create_delivery.py` demonstrates how to create a DoorDash Drive delivery from Python using the `requests` package. The script sends an outbound REST request directly to the DoorDash Drive API; a webhook is not required to create the delivery.

Install the dependency and provide the API token through an environment variable:

```bash
pip3 install requests
export DOORDASH_TOKEN="your-token-here"
python create_delivery.py
```

The script uses `DOORDASH_TOKEN` rather than storing credentials in source code. Do not commit API tokens, customer information, or other secrets to the repository.

```python name=create_delivery.py
import os
import requests

DOORDASH_TOKEN = os.environ["DOORDASH_TOKEN"]

endpoint = "https://openapi.doordash.com/drive/v2/deliveries/"

headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {DOORDASH_TOKEN}",
    "Content-Type": "application/json",
}

request_body = {
    "external_delivery_id": "D-12345",
    "pickup_address": "901 Market Street 6th Floor San Francisco, CA 94103",
    "pickup_business_name": "Wells Fargo SF Downtown",
    "pickup_phone_number": "+16505555555",
    "pickup_instructions": "Enter gate code 1234 on the callbox.",
    "dropoff_address": "901 Market Street 6th Floor San Francisco, CA 94103",
    "dropoff_business_name": "Wells Fargo SF Downtown",
    "dropoff_phone_number": "+16505555555",
    "dropoff_instructions": "Enter gate code 1234 on the callbox.",
    "order_value": 1999,
}

try:
    response = requests.post(
        endpoint,
        headers=headers,
        json=request_body,
        timeout=30,
    )

    print(f"HTTP status: {response.status_code}")
    print(response.text)

    response.raise_for_status()

except requests.RequestException as error:
    print(f"DoorDash request failed: {error}")
    raise
```

The example targets the DoorDash API and may create a real delivery or incur charges depending on the configured account and environment. Confirm the current DoorDash authentication, sandbox, and billing requirements before running it with production credentials. For delivery-status callbacks, a separate publicly reachable webhook endpoint is required; GitHub Actions is suitable for manually triggered jobs, but it is not a persistent webhook server.

## Stage 0 contents

- `docs/STAGE_0.md` — charter, actors, workflow, assumptions, and exit criteria
- `docs/KNOWLEDGE_BASE.md` — source registry and evidence-handling rules
- `docs/VENDOR_CULAP_DATA_FARM.md` — vendor update workflow using the CULAP Data Farm agent
- `src/tranceatables/models.py` — typed delivery request and robot state
- `src/tranceatables/feasibility.py` — deterministic go/no-go evaluator
- `tests/` — baseline acceptance tests
- `create_delivery.py` — DoorDash Drive delivery creation example

## Stage 1 contents

- `src/tranceatables/order_state.py` — validated order lifecycle rules
- `src/tranceatables/repository.py` — SQLite snapshots and append-only audit events
- `src/tranceatables/service.py` — API-neutral create, retrieve, transition, and history operations
- `tests/test_order_state.py` — lifecycle, persistence, audit, duplicate, and concurrency tests
- `docs/STAGE_1.md` — Stage 1 design, safety boundary, and acceptance criteria

The Stage 1 lifecycle is:

```text
draft -> accepted -> prepared -> packaged -> ready -> assigned
```

Every active state can be cancelled. Invalid transitions are rejected without modifying the persisted order or its audit history.

## Stage 1.5 MCP server

The MCP server lets an MCP-capable AI host inspect and exercise the existing TRANCEatables rules through a deliberately limited simulation interface. It exposes delivery feasibility, simulated order creation, state transitions, snapshots, and audit history. It cannot place a real order, take payment, contact a customer, call a delivery provider, or control a physical robot.

Start with the novice-friendly walkthrough in [`docs/STAGE_1_5_MCP.md`](docs/STAGE_1_5_MCP.md).

```bash
python -m pip install -e '.[mcp,dev]'
python -m pytest -q
TRANCEATABLES_DB_PATH=demo.sqlite3 mcp dev src/tranceatables/mcp_server.py
```

Use opaque test identifiers only. Do not enter names, addresses, health information, payment data, credentials, or secrets.

## Farm-to-fork simulation

The MCP server now includes an auditable food-lot chain:

```text
planned -> harvested -> farm_packed -> picked_up -> kitchen_received
        -> meal_prepared -> meal_packaged -> out_for_delivery -> delivered
```

Each active stage can be cancelled. Stages cannot be skipped. Optional location codes, observed temperatures, and short notes are stored as append-only events; recorded temperatures are observations and do not certify food safety.

See [`docs/FARM_TO_FORK.md`](docs/FARM_TO_FORK.md) for the workflow, MCP resources and tools, example inputs, and safety boundary.

### CULAPSE Data Farm checkpoints

The Kaggriculture Agent Lab documentation maps strongly to the `planned` and `harvested` stages. The MCP adapter exposes the revised `S = P x Mf x C` planning model and potential-versus-collected harvest analysis with FPP-05 routing-loss detection.

It does **not** validate `farm_packed`: shed inventory is not evidence of food-grade packing, sanitation, sealed lots, labeling, temperature control, or package integrity. See [`docs/CULAPSE_STAGE_MAPPING.md`](docs/CULAPSE_STAGE_MAPPING.md).

## Vendor updates with CULAP Data Farm

Vendors can use the [CULAP Data Farm agent](https://culapsedatafarm-agent-lab.erichilarysmithsr.chatgpt.site) to draft repository-aware implementation plans, identify tests, and document operational changes.

The agent should be used as a planning and review aid only. Do not provide it with secrets, payment data, customer addresses, health information, or credentials. All changes require human review and testing before deployment.

See [`docs/VENDOR_CULAP_DATA_FARM.md`](docs/VENDOR_CULAP_DATA_FARM.md) for the complete workflow, a reusable prompt, data-minimization rules, and vendor approval checklist.

## Roadmap

Stage 1 order state and persistence, the Stage 1.5 simulation-only MCP server, and simulation-only farm-to-fork traceability are implemented. Later stages may add mapping, dispatch, robot adapters, food-temperature telemetry, and human oversight. See `docs/STAGE_1.md` for the current scope and exit criteria.

## License

Apache-2.0. See `LICENSE`.
