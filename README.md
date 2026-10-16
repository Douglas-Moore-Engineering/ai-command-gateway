# AI Command Gateway

An offline-first reference system for inspecting industrial datasets, retrieving cited source observations, and independently checking proposed solar/battery commands before a **mock-only** execution interface. An optional OpenAI adapter exercises a model round trip within a locally checked evidence contract.

**Current state: Azure retirement verified; the subscription is kept.** At **2026-10-16 05:13:03 UTC**, separate read-only ARM checks confirmed that the established subscription ending `f609` remains `Enabled`, with zero active resources, zero resource groups, zero project-principal role assignments and zero management locks. Both existing subscription Owner assignments were preserved. The foundation, Container Apps managed resources and Network Watcher group were deleted, including the cloud image, uploaded dataset copies, job and cloud results. Original local datasets, downloaded evidence and source/GitHub copies remain retained. The [retirement record](governance/azure-retirement-v0.4.json) preserves the verification and provider-recovery limits. The successful v0.4 pilot remains historical evidence, with no domain or production acceptance claim.


## What problem does this solve?

Operators need consistent, auditable checks before AI recommendations become control instructions. This fictional portfolio project separates source observations, proposals, deterministic policy decisions, human review, and mock outcomes. Financial savings, incident reduction and operator benefit have not been measured.

The gateway returns **allow, block, or escalate**. An allow means eligibility under an explicitly synthetic software-test policy. The provided datasets do not establish engineering limits. The default unqualified policy escalates. There is no equipment adapter or live command path. Optional inference has no policy, approval or execution access. Local actor labels simulate workflow; authenticated identities and protected policy administration remain future work.

## Who uses it, and what can they do?

Engineers inspect source quality and retrieve cited observations. Reviewers inspect deterministic decisions, approval bindings and audit history. Operators can exercise a synthetic proposal through the mock workflow. No role can actuate equipment through this application. Local actor labels do not authenticate a person.

## What works today?

| Capability | Local implementation | Evidence boundary |
| --- | --- | --- |
| Source qualification | Inventory-bound hashes, complete S1 timestamp order/duplicates/cadence and numeric quality, archive identity checks | Clock alignment, units, scaling, rights and operational mappings remain unresolved |
| Cited observation advice | Controlled aggregate catalog, deterministic retrieval, exact statements and file/field citations, abstention | Observations only; catalog consistency is not source authenticity |
| Advice evaluation | Frozen local casebook checks retrieval, citation bindings and abstention | Engineer-authored regression cases; no independent domain or LLM-quality acceptance |
| Deterministic validation | Explicit actions, units, asset/mode/state limits, freshness and approved source references | Synthetic limits only; no physical safety inference |
| Approval and mock execution | Request/policy binding, expiry, revalidation, persistent replay rejection | Local actor labels; single-host SQLite transactions |
| Audit | Proposal, sources, model/policy versions, state time, actor, decision and mock outcome | Local durable records; not a tamper-proof evidence service |
| Historical replay | Recorded S1 battery targets reach the unqualified-policy gate | No ground-truth accuracy measurement or invented unit conversion |
| Readable answers | Plain-text observations, optional cited model explanations and saved output | [Examples](docs/answer-examples.md); bounded contract checks, semantic accuracy unqualified |
| Optional model integration | Explicit OpenAI Responses call, request preview, exact-claim validation and offline fallback | Simulated-response tests only; no live integration, model-quality or operational acceptance claim |
| Historical Azure batch pilot | Exact image and five inputs transferred; demo/dataset executions, nine identity checks, expected failure and artifact checks passed before retirement | Cloud resource retirement verified; local evidence remains; no domain or production acceptance |

## What has been measured, and in what context?

| Result | Context and evidence | Limit |
| --- | --- | --- |
| Cited explanation integration | [Current verification](governance/cited-explanation-verification-2026-10-16.json) | Simulated provider; model quality and domain acceptance unmeasured |
| Current maintenance verification | [Dated verification record](governance/repository-maintenance-2026-10-16.json) | Local software and fixtures; remote CI is tracked separately |
| Historical local suite: 590 passed, 44 subtests, one skip | [Pilot record](governance/azure-pilot-v0.4.json) | Earlier Windows environment; not a new run |
| Historical Azure demo and dataset executions; nine identity checks | [Pilot record](governance/azure-pilot-v0.4.json), [results](docs/results.md) | Bounded sandbox evidence; no production acceptance |
| Azure resource retirement verified, subscription retained | [Retirement record](governance/azure-retirement-v0.4.json) | Recorded ARM checks; no fresh cloud query or zero-bill claim |
| Domain and business benefits unmeasured | [Results and measurement links](docs/results.md), [acceptance criteria](requirements/acceptance.csv) | No savings, safety, model-quality or customer-acceptance claim |

The historical standing-core estimate was about $97.49/month plus usage while the foundation existed. [Cost assumptions](docs/azure-cost-estimate.md) remain historical; actual billed charges are unmeasured. The reviewed Wolfi/Python 3.13 image had zero findings in its [recorded scan scope](docs/image-security.md).

## What is missing?

OPEN-01–08 remain unresolved. Clock relationships, units, source rights, equipment semantics and reviewed physical limits need domain assessment. Authenticated users, protected policy administration, independent review and operational readiness remain future work. Synthetic tests do not close the proposed AC-01–06 criteria or governance gates. [Project status](PROJECT_STATUS.md), [open items](customer/open-items.csv) and [release boundaries](governance/release_gates.md) define the remaining work.

Azure remains retired. Any future deployment needs a separate target and scope review. No live inference was performed for the release or this maintenance verification.

## How do I run the demo?

Create an environment and install pinned dependencies. Installation needs network access; the default demo and tests run without cloud credentials.

```bash
python -m venv .venv
# Linux/macOS; on Windows use .venv/Scripts/python.exe below
.venv/bin/python -m pip install -r requirements-dev.lock -r requirements-azure.lock
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv/bin/python -m ai_command_gateway demo
.venv/bin/python scripts/verify_offline_ci.py
```

The Azure SDK dependencies support mocked boundary tests; installing them does not connect Azure. The verification runner uses the committed aggregate fixture, runs the full suite and checks retrieval, abstention, mock behavior and an OpenAI dry-run. It does not inspect the original datasets. Historical development used Windows CPython 3.10.11; current verification environments are identified in the dated record and CI workflow. Container dependencies remain separately locked.

For source profiling, qualification, catalog queries and replay, use the [demo guide](docs/demo.md). For readable offline examples, run `python scripts/show_answer_examples.py` or open [the recorded answers](docs/answer-examples.md). With a configured provider and catalog, `advise --provider openai --explain --question "How many rows are in process_dataset.parquet?" --output outputs/answers/answer.txt` displays and saves cited prose. No live model evaluation is claimed; explanation accuracy needs review.

The [optional provider instructions](docs/demo.md#optional-openai-advice) explain the explicit live-call boundary. Default advice is offline; the application does not load `.env` automatically. Previewing uses `--provider openai --dry-run` and neither reads credentials nor calls a model.

## Where are the engineering details?

The Python CLI composes independent source inspection, cited observation retrieval, deterministic proposal validation and persistent mock approvals. Advice cannot create commands or grant execution authority. SQLite keeps mock execution and approval consumption in one transaction. The original discovery remains immutable.

- [System and data/authority diagram](docs/architecture/README.md)
- [Implementation baseline, threat model and operating assumptions](docs/implementation-baseline.md)
- [ADR-001: offline foundation](architecture/adr/ADR-001-offline-foundation.md)
- [ADR-003: guarded model advice](architecture/adr/ADR-003-guarded-model-advice.md)
- [ADR-004: Azure batch foundation](architecture/adr/ADR-004-azure-batch-foundation.md), [Azure implementation guide](docs/azure-implementation.md)
- [Evidence catalog and trust boundary](docs/evidence-design.md), [source semantics and timestamp findings](docs/source-semantics.md)
- [Standards tailoring and review obligations](governance/standards-tailoring.md)

| Path | Purpose |
| --- | --- |
| `src/ai_command_gateway/` | Source analysis, evidence catalog/advisor, evaluation, deterministic core, replay and CLI |
| `tests/`, `config/policies/`, `data/contracts/`, `data/samples/` | Regression checks, explicit policy and contracts, synthetic fixtures |
| `customer/`, `requirements/`, `governance/` | Preserved discovery, stable traces, risks and gates |
| `docs/`, `architecture/`, `runbooks/` | Design decisions, evidence and operating instructions |
| `infra/`, `Dockerfile`, `scripts/azure_*.ps1`, `scripts/deploy_azure.ps1` | Private Azure batch foundation, container packaging and deliberate deployment workflow |
| `outputs/` | Ignored profiles, qualification, catalog/evaluation, replay records and audit databases |

- [Documentation contents](docs/README.md), [code walkthrough](docs/code-walkthrough.md), [operating instructions](runbooks/README.md)
- [Requirements](requirements/requirements.csv), [acceptance](requirements/acceptance.csv), [traceability](requirements/traceability.csv)
- [Data qualification](data/README.md), [lifecycle](governance/LIFECYCLE_CHECKLIST.md), [AI governance](governance/AI_GOVERNANCE_PLAN.md)
- [Discovery](customer/DISC-001-v0.1.md), [open items](customer/open-items.csv), [cost planning](customer/COST-001.md), [handoff](customer/HANDOFF.md)

Maintainer: Douglas Moore / Douglas Moore Engineering. Raw datasets, local outputs and environments are excluded from Git. Dataset descriptions and archive text are untrusted evidence, never executable instructions. No open-source license is granted by this repository, and no third-party redistribution is included.
