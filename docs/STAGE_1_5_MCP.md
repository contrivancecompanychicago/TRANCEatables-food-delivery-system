# Stage 1.5: simulation-only TRANCEatables MCP server

## MCP in plain language

Model Context Protocol (MCP) is a standard way for an AI application to discover and use capabilities supplied by another program. In this project:

1. **Host** — the AI application in which a person asks for help.
2. **MCP client** — the host's connector that speaks the MCP protocol.
3. **TRANCEatables MCP server** — this repository's local Python process.
4. **Resources** — information the host can read, such as an order snapshot.
5. **Tools** — named operations the model can request, such as evaluating a hypothetical delivery.

The model does not receive arbitrary database access. It sees only the resources and tools intentionally registered by `mcp_server.py`.

## What Stage 1.5 exposes

| MCP capability | Kind | Effect |
|---|---|---|
| `tranceatables://about` | resource | Reads scope and safety rules |
| `tranceatables://orders/{order_id}` | resource | Reads a simulated order snapshot |
| `tranceatables://orders/{order_id}/history` | resource | Reads its audit events |
| `evaluate_simulated_delivery` | tool | Runs the Stage 0 feasibility rules without saving or dispatching |
| `create_simulated_order` | tool | Saves a local draft order |
| `get_simulated_order` | tool | Reads an order and allowed next states |
| `get_simulated_order_history` | tool | Reads audit history |
| `transition_simulated_order` | tool | Applies one Stage 1 transition |

No prompt templates are exposed in Stage 1.5. They are not necessary for the first testable server.

## Safety boundary

This server cannot call delivery providers, control a robot, collect payment, contact anyone, or certify food safety. It accepts opaque test identifiers such as `SIM-100`; do not enter names, addresses, health information, payment data, API keys, or other secrets.

The default transport is local standard input/output (stdio). The server writes simulations to a local SQLite file selected with `TRANCEATABLES_DB_PATH`.

## Run it step by step

Prerequisites: Python 3.10 or newer.

1. Clone the repository and enter its directory.
2. Create and activate a virtual environment.
3. Install the project with the MCP extra:

   ```bash
   python -m pip install -e '.[mcp,dev]'
   ```

4. Run the automated tests:

   ```bash
   python -m pytest -q
   ```

5. Start the official MCP Inspector for a visual development session:

   ```bash
   TRANCEATABLES_DB_PATH=demo.sqlite3 mcp dev src/tranceatables/mcp_server.py
   ```

6. In the Inspector, first read `tranceatables://about`.
7. Call `evaluate_simulated_delivery` with test values. Confirm that the result says `simulation_only: true` and `dispatched: false`.
8. Call `create_simulated_order` with order ID `SIM-100`.
9. Read `tranceatables://orders/SIM-100` and note that the status is `draft`.
10. Call `transition_simulated_order` with target `accepted` and `expected_version` 0.
11. Read `tranceatables://orders/SIM-100/history`; it should show creation and transition events.

To run the stdio server without the Inspector:

```bash
TRANCEATABLES_DB_PATH=demo.sqlite3 python -m tranceatables.mcp_server
```

An MCP-capable host can use that command as its local server command. Exact configuration screens differ by host, but the command, module, working directory, and environment variable are the same.

## Code map

- `mcp_api.py` converts plain MCP inputs into existing domain objects and converts results into JSON-friendly dictionaries.
- `mcp_server.py` registers resources and tools with the MCP SDK.
- `service.py` coordinates Stage 1 operations.
- `repository.py` persists snapshots and append-only audit events.
- `order_state.py` remains the authority for permitted transitions.

This separation is intentional: replacing MCP or adding another API does not rewrite the order rules.
