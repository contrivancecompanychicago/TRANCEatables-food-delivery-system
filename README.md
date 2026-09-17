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

## Stage 0 contents

- `docs/STAGE_0.md` — charter, actors, workflow, assumptions, and exit criteria
- `docs/KNOWLEDGE_BASE.md` — source registry and evidence-handling rules
- `docs/VENDOR_CULAP_DATA_FARM.md` — vendor update workflow using the CULAP Data Farm agent
- `src/tranceatables/models.py` — typed delivery request and robot state
- `src/tranceatables/feasibility.py` — deterministic go/no-go evaluator
- `tests/` — baseline acceptance tests

## Vendor updates with CULAP Data Farm

Vendors can use the [CULAP Data Farm agent](https://culapsedatafarm-agent-lab.erichilarysmithsr.chatgpt.site) to draft repository-aware implementation plans, identify tests, and document operational assumptions.

The agent should be used as a planning and review aid only. Do not provide it with secrets, payment data, customer addresses, health information, or credentials. All changes require human review and should preserve the Stage 0 simulation-only boundary.

See [`docs/VENDOR_CULAP_DATA_FARM.md`](docs/VENDOR_CULAP_DATA_FARM.md) for the complete workflow, a reusable prompt, data-minimization rules, and vendor approval checklist.

## Roadmap

Stage 1 will add an order state machine and persistence. Later stages may add mapping, dispatch, robot adapters, food-temperature telemetry, human oversight, and simulation. See `docs/STAGE_0.md` for the current boundaries.

## License

Apache-2.0. See `LICENSE`.
