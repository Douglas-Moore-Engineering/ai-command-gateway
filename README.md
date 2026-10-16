# AI Command Gateway

An offline-first reference system for inspecting industrial datasets, retrieving cited source observations, and independently checking proposed solar/battery commands before a **mock-only** execution interface. An optional OpenAI adapter exercises a model round trip within a locally checked evidence contract.

**Current state: Azure retirement verified; the subscription is kept.** At **2026-10-16 05:13:03 UTC**, separate read-only ARM checks confirmed that the established subscription ending `f609` remains `Enabled`, with zero active resources, zero resource groups, zero project-principal role assignments and zero management locks. Both existing subscription Owner assignments were preserved. The foundation, Container Apps managed resources and Network Watcher group were deleted, including the cloud image, uploaded dataset copies, job and cloud results. Original local datasets, downloaded evidence and source/GitHub copies remain retained. The [retirement record](governance/azure-retirement-v0.4.json) preserves the verification and provider-recovery limits. The successful v0.4 pilot remains historical evidence, with no domain or production acceptance claim.

## Contents

- [Mission and authority](#mission-and-authority)
- [Run locally](#run-locally)
- [Optional model adapter](#optional-model-adapter)
- [Azure batch implementation](#azure-batch-implementation)
- [Implemented behavior](#implemented-behavior)
- [Architecture and diagrams](#architecture-and-diagrams)
- [Evidence and next increment](#evidence-and-next-increment)
- [Repository and engineering records](#repository-and-engineering-records)

## Mission and authority

Operators need consistent, auditable checks before AI recommendations become control instructions. This fictional portfolio project separates source observations, proposals, deterministic policy decisions, human review, and mock outcomes. Financial savings, incident reduction and operator benefit have not been measured.

The gateway returns **allow, block, or escalate**. An allow means eligibility under an explicitly synthetic software-test policy. The provided datasets do not establish engineering limits. The default unqualified policy escalates. There is no equipment adapter or live command path. Optional inference has no policy, approval or execution access. Local actor labels simulate workflow; authenticated identities and protected policy administration remain future work.

## Run locally

The existing Windows development environment uses CPython 3.10.11 and its pinned dependencies; these commands reproduce that historical local environment. The reviewed pilot Linux image uses vendor-maintained Python 3.13 and the separate [container locks](containers/python-linux-amd64.lock).

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.lock
.venv/Scripts/python.exe -m pip install --no-build-isolation --no-deps -e .
.venv/Scripts/python.exe -m ai_command_gateway demo
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check_repository.py
```

The prepared workspace already has an installed `.venv`. `uv` can also install the pinned dependencies; set `--cache-dir .cache/uv` to keep its cache inside the workspace. Dependency installation needs network access; the default application runs locally without network access or credentials.

Profile and qualify the five supplied files, then build and query the local evidence catalog:

```powershell
.venv/Scripts/python.exe -m ai_command_gateway profile --input-dir "C:/Users/moore/Downloads" --output-dir outputs/profiles
.venv/Scripts/python.exe -m ai_command_gateway qualify --input-dir "C:/Users/moore/Downloads"
.venv/Scripts/python.exe -m ai_command_gateway catalog
.venv/Scripts/python.exe -m ai_command_gateway advise --question "How many rows are in packets_dataset.parquet?" --source S1
.venv/Scripts/python.exe -m ai_command_gateway eval-advice
.venv/Scripts/python.exe -m ai_command_gateway replay --input-dir "C:/Users/moore/Downloads" --limit 20
.venv/Scripts/python.exe -m ai_command_gateway audit --db outputs/demo/audit.sqlite3
```

`qualify` checks source identities and writes timestamp/numeric observations to `outputs/qualification/source-qualification.json`. `catalog` builds a verified bundle from the aggregate profile under `outputs/advice/`; `advise` returns exact cited observations or abstains. `eval-advice` writes local retrieval regression evidence under `outputs/advice-evaluation/`. Raw files stay at the supplied paths. Full usage, outputs and exit codes are in the [demo guide](docs/demo.md).

## Optional model adapter

Preview the request without a credential or network call:

```powershell
.venv/Scripts/python.exe -m ai_command_gateway advise --provider openai --dry-run --question "How many rows are in packets_dataset.parquet?" --source S1
```

The initial target is OpenAI Responses API with `gpt-6.1-sol`, which supports structured outputs. This is a runtime to evaluate, with no measured quality advantage claimed. [Official model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)

Explicit `--provider openai` without `--dry-run` reads `OPENAI_API_KEY` from the process environment and, when evidence is available, sends the question, selected observation IDs/statements and catalog identity/hash to OpenAI. The application does not load `.env` automatically. The preview shows the request body; the adapter does not add raw dataset files or local file paths. Review the [provider instructions](docs/demo.md#optional-openai-advice) before making a live call.

The model must return the complete selected claim set unchanged or refuse. Local validation permits any order, rejects changed statements, missing facts and invented IDs, and reconstructs claims/citations locally in the validated order. Failures receive explicit fallback metadata. This increment verifies integration mechanics; it adds no question coverage or engineering explanation, and ordering quality has not been measured. Default `advise` remains fully offline. No live inference was performed for this release evidence.

## Azure batch implementation

The [Azure implementation guide](docs/azure-implementation.md) preserves the completed manual-job pilot and its implementation. The cloud deployment has been retired, including ACR, Blob inputs/results, the job and supporting services. Local execution remains available. The instructions below describe the implementation and historical pilot. Any future cloud redeployment requires a separate target and scope review.

Exercise its local demo path without Azure credentials:

```powershell
.venv/Scripts/python.exe -m ai_command_gateway.azure_job --local-output outputs/azure-local-demo
```

The [foundation template](infra/main.bicep), isolated [job-only wrapper](infra/job-only.bicep), [Dockerfile](Dockerfile) and [deployment helpers](scripts/deploy_azure.ps1) implement staged deployment. The reviewed image was transferred through a temporary private operator VM and published without rebuilding, at digest `sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad`. The job-only preview showed one create and 33 ignores. Job-stage preflight refuses foundation changes even with `-AllowModify`. [ADR-004](architecture/adr/ADR-004-azure-batch-foundation.md) records the platform decision; [private-access evidence](docs/azure-private-access-plan.md) records the operator path and static-check coverage limits. Production release gates remain closed.

Historically, foundation deployment succeeded and **21/21 read-only control-plane checks passed**, including the then-absent job. The [foundation review](docs/azure-deployment-review.md) preserves that earlier scope. Historical operator receipts confirm private DNS for Blob, ACR and Monitor, exact image publication, five-file upload/readback and private execution-log access; separate ARM records confirm the two successful job executions.

The historical [regional estimate](docs/azure-cost-estimate.md) was about **$97.49/month** in standing core charges plus usage while the foundation existed. Final ARM verification confirmed removal of those resources; the estimate is historical and does not describe a current deployment. Actual billed charges remain unmeasured and billing can arrive after deletion, so no zero-charge claim is made. The reviewed Wolfi/Python 3.13 image passed all 16 [bounded local dataset checks](docs/azure-runtime-checks.md); its unfiltered [Trivy scan](docs/image-security.md) reported zero findings within the recorded scanner/database scope.

## Implemented behavior

| Capability | Local implementation | Evidence boundary |
| --- | --- | --- |
| Source qualification | Inventory-bound hashes, complete S1 timestamp order/duplicates/cadence and numeric quality, archive identity checks | Clock alignment, units, scaling, rights and operational mappings remain unresolved |
| Cited observation advice | Controlled aggregate catalog, deterministic retrieval, exact statements and file/field citations, abstention | Observations only; catalog consistency is not source authenticity |
| Advice evaluation | Frozen local casebook checks retrieval, citation bindings and abstention | Engineer-authored regression cases; no independent domain or LLM-quality acceptance |
| Deterministic validation | Explicit actions, units, asset/mode/state limits, freshness and approved source references | Synthetic limits only; no physical safety inference |
| Approval and mock execution | Request/policy binding, expiry, revalidation, persistent replay rejection | Local actor labels; single-host SQLite transactions |
| Audit | Proposal, sources, model/policy versions, state time, actor, decision and mock outcome | Local durable records; not a tamper-proof evidence service |
| Historical replay | Recorded S1 battery targets reach the unqualified-policy gate | No ground-truth accuracy measurement or invented unit conversion |
| Optional model integration | Explicit OpenAI Responses call, request preview, exact-claim validation and offline fallback | Simulated-response tests only; no live integration, model-quality or operational acceptance claim |
| Historical Azure batch pilot | Exact image and five inputs transferred; demo/dataset executions, nine identity checks, expected failure and artifact checks passed before retirement | Cloud resource retirement verified; local evidence remains; no domain or production acceptance |

## Architecture and diagrams

The Python CLI composes independent source inspection, cited observation retrieval, deterministic proposal validation and persistent mock approvals. Advice cannot create commands or grant execution authority. SQLite keeps mock execution and approval consumption in one transaction. The original discovery remains immutable.

- [System and data/authority diagram](docs/architecture/README.md)
- [Implementation baseline, threat model and operating assumptions](docs/implementation-baseline.md)
- [ADR-001: offline foundation](architecture/adr/ADR-001-offline-foundation.md)
- [ADR-003: guarded model advice](architecture/adr/ADR-003-guarded-model-advice.md)
- [ADR-004: Azure batch foundation](architecture/adr/ADR-004-azure-batch-foundation.md), [Azure implementation guide](docs/azure-implementation.md)
- [Evidence catalog and trust boundary](docs/evidence-design.md), [source semantics and timestamp findings](docs/source-semantics.md)
- [Standards tailoring and review obligations](governance/standards-tailoring.md)

## Evidence and next increment

The v0.2 verification history records 51 tests and 44 subtests, the five-check demo and 20-row qualification replay. The v0.3 increment adds full S1 timestamp analysis, catalog integrity checks and observation/abstention evaluation. The v0.4 increment adds provider request/failure verification and Azure container/IaC/job implementation. See [results](docs/results.md) for recorded verification outcomes and [project status](PROJECT_STATUS.md) for remaining work. Local and simulated-cloud checks are separate from live Azure validation and the proposed AC-01-06 acceptance criteria; customer acceptance and production measurements remain pending.

The current local suite records **590 passed tests plus 44 subtests and one skipped test**; the subsequent focused transfer/log-helper suite passes 46 tests. These are local checks, distinct from the live Azure receipts. Historical pilot evidence is preserved unchanged in [the pilot record](governance/azure-pilot-v0.4.json). Azure retirement was verified separately; it does not invalidate those recorded results. Subsequent local engineering work can resolve clock relationships, units and equipment semantics, obtain reviewed policy/cases and evaluate provider behavior against approved knowledge. OPEN-01-08 retain their original unresolved conditions. Cloud and production entry remain governed by [release boundaries](governance/release_gates.md).

## Repository and engineering records

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
