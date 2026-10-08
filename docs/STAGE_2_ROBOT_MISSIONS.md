# Stage 2: simulation-only robot mission management

## Purpose

Stage 2 converts the validated Grist/Google Colab exercise into tested repository code. It manages simulated robots, approvals, missions, generated telemetry, and safety observations without connecting to a physical robot, navigation stack, delivery provider, customer, or payment system.

## Architecture

- `robot_mission.py` is the authority for robot and mission states.
- `robot_mission_repository.py` stores SQLite snapshots and append-only mission events.
- `robot_mission_service.py` provides API-neutral orchestration.
- `mcp_api.py` validates data-minimized MCP inputs and returns JSON-safe results.
- `mcp_server.py` exposes deliberately limited simulation resources and tools.
- Grist remains an optional human-readable dashboard and audit mirror. It is not a motor-control channel.
- Google Colab remains a development environment. It is not a persistent robot controller.

## Mission lifecycle

```text
planned -> awaiting_approval -> approved -> dispatched
        -> navigating_to_pickup -> loading
        -> navigating_to_dropoff -> awaiting_handoff -> completed
```

Validated exception branches include `cancelled`, `paused`, `blocked`, and `emergency_stopped`. The exception states are terminal in this first Stage 2 implementation; recovery workflows belong in a later stage.

## Eligibility and approval rules

A mission may be created only when:

- the referenced simulated order exists and is `ready`;
- the simulated robot exists, is `available`, and is operational;
- robot battery is at least 50 percent;
- mission payload does not exceed robot capacity; and
- all identifiers are opaque simulation identifiers.

A mission cannot transition to `approved` until an explicit operator approval is stored. A mission cannot transition to `dispatched` until it is approved. Simulated dispatch is a single SQLite transaction that:

1. changes the mission from `approved` to `dispatched`;
2. changes the robot from `available` to `assigned`;
3. changes the Stage 1 order from `ready` to `assigned`;
4. appends mission and order audit events; and
5. records the first stationary telemetry observation.

No physical command is produced.

## Persistence

Stage 2 adds these SQLite tables:

- `simulated_robots`
- `robot_missions`
- `mission_events`
- `operator_approvals`
- `robot_telemetry`
- `robot_safety_events`

Telemetry values are generated simulation observations. They are not GPS, physical sensor measurements, food-safety certifications, or proof of delivery.

## MCP capabilities

Resources:

- `tranceatables://robots/{robot_id}`
- `tranceatables://robot-missions/{mission_id}`
- `tranceatables://robot-missions/{mission_id}/history`
- `tranceatables://robot-missions/{mission_id}/telemetry`

Tools:

- `register_simulated_robot`
- `create_simulated_robot_mission`
- `record_simulated_mission_approval`
- `transition_simulated_robot_mission`
- `record_simulated_robot_telemetry`
- `record_simulated_robot_safety_event`

## Safety boundary

Stage 2 cannot:

- issue velocity, steering, motor, brake, route, or actuator commands;
- start or stop a physical robot;
- claim that generated telemetry came from hardware;
- call DoorDash or another delivery provider;
- contact a customer or restaurant;
- accept payment;
- certify food handling or delivery completion; or
- turn Grist, Colab, or MCP into a real-time safety controller.

A future physical prototype must add an onboard independent emergency stop, obstacle detection, speed limits, geofencing, authenticated command transport, human supervision, and a robotics control layer such as ROS 2/Nav2. Those capabilities are explicitly outside Stage 2.

## Grist mapping

The validated Grist workflow maps to repository concepts as follows:

| Grist table | Repository table |
|---|---|
| `Robots` | `simulated_robots` |
| `RobotMissions` | `robot_missions` |
| `MissionEvents` | `mission_events` |
| `OperatorApprovals` | `operator_approvals` |
| `RobotTelemetry` | `robot_telemetry` |
| `SafetyEvents` | `robot_safety_events` |

Grist synchronization is not automatic in Stage 2. A later adapter may mirror repository records to Grist through its REST API or webhooks, with SQLite remaining the simulation authority.

## Acceptance criteria

- [x] Invalid mission transitions do not alter mission history.
- [x] A ready order and eligible simulated robot are required.
- [x] Human approval is required before approval and dispatch.
- [x] Simulated dispatch assigns the mission, order, and robot together.
- [x] Mission events are append-only and versioned.
- [x] Generated telemetry and safety events persist separately.
- [x] Completion releases the simulated robot.
- [x] MCP outputs retain `simulation_only: true`.
- [x] No physical robot or third-party delivery control exists.
