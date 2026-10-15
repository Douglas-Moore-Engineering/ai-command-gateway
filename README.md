# AI Command Gateway

LLM-assisted industrial command validation for an offline solar-and-battery reference demonstration.

## Operational problem

Energy operators need consistent, auditable checks before AI recommendations become control instructions. This fictional portfolio project explores independent command validation; financial losses and avoided incidents have not been established.

## Users and supported action

Operators request advice and submit proposals. Controls engineers own operating rules; security reviewers assess authority boundaries. The planned deterministic gateway returns **allow, block or escalate**. An allow decision ends at a mock interface. The LLM must have no equipment credentials, execution permission or policy-editing authority.

## Current capability

Discovery v0.1 is preserved in [Word](customer/DISC-001-v0.1.docx) and [browsable Markdown](customer/DISC-001-v0.1.md). Six candidate requirements, six acceptance criteria and eight open items are indexed and traced. The repository checker validates documentation links, IDs and source integrity. The gateway and LLM application are not implemented.

## Measurements

| Measure | Result / denominator | Context | Record |
| --- | --- | --- | --- |
| Forbidden accepts | not measured / no evaluated cases | Proposed offline critical suite | [MEAS-001](governance/measurements/MEAS-001.md) |
| Valid-command false blocks | not measured / no evaluated cases | Threshold unresolved | [MEAS-002](governance/measurements/MEAS-002.md) |
| Authority bypass | not measured / no attempts | Planned access and replay tests | [MEAS-003](governance/measurements/MEAS-003.md) |
| Audit completeness | not measured / no decision records | Planned field/link checks | [MEAS-004](governance/measurements/MEAS-004.md) |
| Operator review time / correctness | not measured / no operator cases | Matched manual comparator required | [MEAS-005](governance/measurements/MEAS-005.md) |
| Grounding / abstention | not measured / no reviewed recommendations | Independent domain review required | [MEAS-006](governance/measurements/MEAS-006.md) |
| Timing / recovery | not measured / no runs | Hardware, load and boundaries unresolved | [MEAS-007](governance/measurements/MEAS-007.md) |

Savings, incident reduction and operational availability are not measured. [Results](docs/results.md) explains the current evidence boundary.

## Qualification gaps

Source files, redistribution rights, units, authoritative rules, expected decisions, thresholds, costs and reviewer assignments remain open. All criteria are proposed. No engineering, governance or customer acceptance gate has passed. Cloud provisioning and live equipment access remain outside scope. See [status](PROJECT_STATUS.md) and [open items](customer/open-items.csv).

## Inspect and validate

Requires Python 3.11+ and Git. No third-party package or credential is required for repository validation:

```sh
python scripts/check_repository.py
```

Open `ai-command-gateway.code-workspace` in VS Code or follow the [code walkthrough](docs/code-walkthrough.md). The [demo page](docs/demo.md) records prerequisites for the future application demo; no runnable command-validation demo exists yet.

## Engineering records

- [Documentation index](docs/README.md) and [architecture index](docs/architecture/README.md)
- [Requirements](requirements/requirements.csv), [acceptance](requirements/acceptance.csv) and [traceability](requirements/traceability.csv)
- [Lifecycle checklist](governance/LIFECYCLE_CHECKLIST.md), [AI governance](governance/AI_GOVERNANCE_PLAN.md) and [release boundaries](governance/release_gates.md)
- [Source data](data/README.md), [cost planning](customer/COST-001.md), [handoff](customer/HANDOFF.md) and [operating instructions](runbooks/README.md)

Maintainer: Douglas Moore / Douglas Moore Engineering. Fictional scenario records are not customer histories. Third-party datasets are not bundled; rights require qualification. No open-source license is granted by this repository.
