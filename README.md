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
- `src/tranceatables/models.py` — typed delivery request and robot state
- `src/tranceatables/feasibility.py` — deterministic go/no-go evaluator
- `tests/` — baseline acceptance tests

## Roadmap

Stage 1 will add an order state machine and persistence. Later stages may add mapping, dispatch, robot adapters, food-temperature telemetry, human oversight, and simulation. See `docs/STAGE_0.md` for the boundary between the research prototype and safety-critical deployment.

## License

Apache-2.0. See `LICENSE`.
