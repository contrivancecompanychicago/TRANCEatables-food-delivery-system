# Vendor updates with the CULAP Data Farm agent

This guide explains how a vendor can use the [CULAP Data Farm agent](https://culapsedatafarm-agent-lab.erichilarysmithsr.chatgpt.site) to propose, prepare, and safely document updates to this repository.

The agent is a planning and review aid. It is not a deployment system, payment processor, food-safety certification authority, robot controller, or substitute for human approval.

## Vendor update workflow

1. Prepare a small change request
   - Describe the vendor capability or operational change.
   - Identify the affected package behavior, documentation, or test coverage.
   - State assumptions, constraints, and acceptance criteria.
   - Do not include passwords, API keys, customer addresses, payment data, health information, or other secrets.

2. Ask the CULAP Data Farm agent for a repository-aware plan
   Provide the agent with:
   - Repository: `contrivancecompanychicago/TRANCEatables-food-delivery-system`
   - The proposed vendor change.
   - Relevant file paths, such as `src/tranceatables/models.py`, `src/tranceatables/feasibility.py`, `tests/`, or `docs/`.
   - Whether the request is documentation-only, a package change, or a future integration proposal.

   Ask it to return:
   - a concise implementation plan;
   - files that should change;
   - test cases and acceptance criteria;
   - risks and unresolved vendor or regulatory questions;
   - a clear distinction between implemented behavior and future work.

3. Review the plan as the vendor
   Confirm that the plan does not:
   - claim that Stage 0 certifies food safety or legal compliance;
   - infer medical suitability from delivery feasibility;
   - dispatch or control a physical robot;
   - store unnecessary personal or location data;
   - introduce credentials or proprietary source material.

4. Implement in a branch or pull request
   Keep each vendor change focused. Update code, tests, and documentation together. Use a descriptive commit or pull-request title, for example:

   `Vendor: document insulated packaging verification workflow`

5. Run local checks before requesting review

   ```bash
   python -m pip install -e '.[dev]'
   python -m pytest
   python -m tranceatables.demo
