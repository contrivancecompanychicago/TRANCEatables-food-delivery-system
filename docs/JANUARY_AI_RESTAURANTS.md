# January AI restaurant API integration

## Placement decision

The supplied endpoint is:

```text
https://partners.january.ai/v1.2/restaurants
```

Restaurant reference data fits in two places:

1. **Order workflow:** restaurant discovery before a simulated order enters `draft`.
2. **Farm-to-fork workflow:** restaurant or kitchen selection after `kitchen_received` and before `meal_prepared`.

It does not belong in `planned`, `harvested`, or `farm_packed`, because those stages describe farm production, harvest evidence, and packing verification. It also does not belong in autonomous robot dispatch.

## Conservative implementation

The endpoint could not be publicly inspected during implementation, so its authentication method and response schema remain unverified. The adapter therefore:

- uses only the exact HTTPS endpoint supplied by the project owner
- performs `GET` only
- is disabled by default
- requires the official authorization header name and complete value to be configured explicitly
- returns valid JSON without renaming or guessing provider fields
- never logs or returns the configured authorization value
- does not create an order or automatically change a lifecycle state
- does not contact a restaurant, submit a purchase, or dispatch a robot

## MCP interface

Resource:

```text
tranceatables://integrations/january-ai/restaurants
```

This reports placement, enabled/configured status, and the safety boundary. It never reveals credentials.

Tool:

```text
fetch_january_ai_restaurants
```

This makes the read-only request only after explicit opt-in.

## Configuration

Obtain the exact authentication requirements from official January AI partner documentation. Do not guess whether it expects `Authorization`, `X-API-Key`, a bearer token, or another format.

When those requirements are known, configure:

```bash
export TRANCEATABLES_ENABLE_JANUARY_AI=true
export JANUARY_AI_AUTH_HEADER='<official header name>'
export JANUARY_AI_AUTH_VALUE='<complete official header value>'
export JANUARY_AI_TIMEOUT_SECONDS=15
```

For Google Colab, use Colab Secrets rather than placing a credential directly in a notebook cell:

```python
from google.colab import userdata
import os

os.environ["TRANCEATABLES_ENABLE_JANUARY_AI"] = "true"
os.environ["JANUARY_AI_AUTH_HEADER"] = userdata.get("JANUARY_AI_AUTH_HEADER")
os.environ["JANUARY_AI_AUTH_VALUE"] = userdata.get("JANUARY_AI_AUTH_VALUE")
```

Create the API facade only after setting the environment:

```python
from tranceatables.mcp_api import SimulationMCPAPI

api = SimulationMCPAPI("/content/tranceatables-demo.sqlite3")
status = api.january_ai_status()
restaurants = api.fetch_january_ai_restaurants()
```

Do not print environment variables or commit credentials to GitHub.

## Future normalization work

Once an authorized sample response or official OpenAPI/schema document is available, a later update can add a provider-specific normalized restaurant model. That update should preserve the raw provider identifier, distinguish restaurant data from menu/item data, document pagination, and add contract tests from a redacted fixture.
