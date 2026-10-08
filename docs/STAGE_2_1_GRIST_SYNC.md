# Stage 2.1 — SQLite-to-Grist synchronization

Stage 2.1 mirrors simulation records from the authoritative SQLite database into Grist. It is one-way and idempotent: SQLite is never changed from Grist, and repeated runs update records by stable IDs instead of duplicating them.

## Safety boundary

- Grist is a dashboard and audit mirror only.
- The adapter cannot change order or mission state.
- The adapter cannot dispatch or control a robot.
- Telemetry remains simulated data, not physical GPS or sensor data.
- Use opaque simulation identifiers; do not synchronize names, addresses, health data, or payment data.

## Configuration

In Colab, store the API key in **Secrets** as `GRIST_API_KEY`. Do not paste it into a notebook cell or commit it to GitHub.

```python
from google.colab import userdata
import os

os.environ["GRIST_API_KEY"] = userdata.get("GRIST_API_KEY")
os.environ["GRIST_BASE_URL"] = "https://math4youbyusgroupil.getgrist.com"
os.environ["GRIST_DOC_ID"] = "kFcsHd7v8Bfwk8AFbqpeU7"
os.environ["TRANCEATABLES_DB_PATH"] = "/content/tranceatables.sqlite3"
```

The configured Grist document must already contain these tables and stable key columns:

| Table | Stable key |
|---|---|
| Orders | OrderId |
| OrderEvents | EventId |
| Robots | RobotId |
| RobotMissions | MissionId |
| MissionEvents | EventId |
| OperatorApprovals | ApprovalId |
| RobotTelemetry | TelemetryId |
| SafetyEvents | SafetyEventId |

## Run a dry-run first

```bash
python -m tranceatables.grist_sync --database "$TRANCEATABLES_DB_PATH"
```

Dry-run reads SQLite and Grist, then prints planned create/update counts. It performs no Grist writes.

## Apply the synchronization

After reviewing the dry-run:

```bash
python -m tranceatables.grist_sync --database "$TRANCEATABLES_DB_PATH" --apply
```

Run the dry-run again. A stable result should report all source rows as `unchanged` with zero creates and updates.

## Data-flow rule

```text
Stage 1/2 services -> SQLite (authoritative) -> Stage 2.1 sync -> Grist (read-only mirror)
```

Physical robot integration belongs in a later supervised hardware stage with onboard safety controls, authenticated command transport, and a dedicated robot middleware adapter.
