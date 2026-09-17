# TRANCEatables Food Delivery System

Stage 0 establishes a testable foundation for a Chicago-focused food-service and autonomous-delivery research prototype.

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

## Vendor updates with CULAP Data Farm

Vendors can use the [CULAP Data Farm agent](https://culapsedatafarm-agent-lab.erichilarysmithsr.chatgpt.site) to draft repository-aware implementation plans, identify tests, and document operational changes.

The agent should be used as a planning and review aid only. Do not provide it with secrets, payment data, customer addresses, health information, or credentials. All changes require human review and testing before deployment.

See [`docs/VENDOR_CULAP_DATA_FARM.md`](docs/VENDOR_CULAP_DATA_FARM.md) for the complete workflow, a reusable prompt, data-minimization rules, and vendor approval checklist.

## Roadmap

Stage 1 will add an order state machine and persistence. Later stages may add mapping, dispatch, robot adapters, food-temperature telemetry, human oversight, and simulation. See `docs/STAGE_0.md` for the current scope and exit criteria.

## License

Apache-2.0. See `LICENSE`.
