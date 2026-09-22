# CULAPSE Data Farm mapping to farm-to-fork stages

## Source reviewed

**Kaggriculture Agent Lab - CULAPSEDataFarm Site Documentation**, prepared September 17, 2026, nine pages.

The document describes a simulation dashboard, Farmer Production Problem diagnostics, an autonomous WHEAT lifecycle, a 720-turn season, harvest routing, inventory, sale, reinvestment, and Backend Version 0 validation.

## Fit decision

| Farm-to-fork stage | Fit | Reason |
|---|---|---|
| `planned` | Strong | Farm-state observation, P/M/L/C measures, revised `S = P x Mf x C` stability model, FPP diagnostics, and prioritized action policy support planning. |
| `harvested` | Strong | The source contains a HARVEST lifecycle action, potential and collected yield, FPP-05 harvest bottleneck evidence, inventory transfer, and event telemetry. |
| `farm_packed` | Not supported | Shed inventory is not evidence of food-grade packing, sanitation, sealed lots, labels, packing temperature, or package integrity. |

The source therefore supports research-simulation checkpoints at `planned` and `harvested`. It must not be cited as proof that a lot reached `farm_packed`.

## Implemented MCP capability

Resource:

- `tranceatables://knowledge/culapse-data-farm/stage-fit`

Tools:

- `evaluate_culapse_planning_checkpoint`
- `evaluate_culapse_harvest_checkpoint`

The planning tool implements the document's revised operational model:

```text
S = P x Mf x C
```

with experimental classifications:

- `stable`: `S >= 0.80`
- `watch`: `0.60 <= S < 0.80`
- `unstable`: `0.40 <= S < 0.60`
- `production_crisis`: `S < 0.40`

The harvest tool computes collected fraction and routing loss. Positive routing loss produces the simulation diagnostic `FPP-05`; zero loss produces `FPP-00`.

## Document example

The source's validated harvest example reports 12 potential WHEAT units and 9 collected units:

```text
routing loss = 12 - 9 = 3 units
completion fraction = 9 / 12 = 0.75
diagnostic = FPP-05
```

## What is needed for `farm_packed`

Before CULAPSE can support the packing stage, a later module should record:

1. lot identifier and package identifier
2. packaging material or container type
3. sanitation checkpoint
4. packing timestamp and opaque facility code
5. observed packing temperature when applicable
6. seal or package-integrity result
7. label and traceability verification

These remain simulation records unless a separately validated operational and regulatory program is established.
