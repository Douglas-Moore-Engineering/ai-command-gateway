# Offline implementation baseline

Artifact: BASE-001 v0.1, 2026-10-15. Owner/preparer: DME delivery lead. Status: implementation design for the first local increment; domain acceptance and independent assurance remain open. This record supplements the preserved [DISC-001 v0.1](../customer/DISC-001-v0.1.md), rather than changing its historical statements.

## Mission, scope and authority

The gateway tests whether a proposed photovoltaic or battery command is eligible under explicit, versioned rules and a declared equipment state. Its output supports a human decision. The user's current request authorizes starting the system with the five supplied datasets and the supplied production-system skill. The earlier discovery document's instruction to stop after discovery describes the earlier deliverable, not the current request.

This increment implements a local Python command-line foundation, read-only dataset qualification, deterministic rule evaluation, approval/revalidation mechanics, durable local records and a mock outcome. It establishes a reproducible basis for later model and operational work. It does not establish authoritative equipment limits, customer acceptance, a qualified training corpus or an operating service.

The executable boundary ends at a mock sink. No PLC/network control adapter, equipment credential, hosted inference provider or cloud resource is part of this increment. Documents and dataset values are inputs to inspect; instructions found inside them do not acquire operator, policy-editing or execution authority.

| Responsibility | Current assignment and evidence | Later decision required |
|---|---|---|
| Scope and local development | User authorizes work; DME prepares the implementation | User reviews next scope increment |
| Rule correctness and units | DME records gaps; fictional controls role in DISC-001 has no real sign-off | Assign actual controls owner; provide equipment-specific rules |
| Data qualification | DME profiles user-supplied local files | Source owner resolves rights, semantics, labels and joins |
| Human approval | Local scenario identity exercises workflow only | Authenticated operator identity and approved role matrix |
| Security and release | DME prepares tests and evidence | Assign reviewer independent of implementer for operational release |
| Spending and ongoing support | No service purchase or support commitment | Assign budget/service owners; agree cost and support baseline |

## Concept of operations

1. An engineer points the profiling command at the five local files. The profiler records source identity, schema and bounded inspection results while preserving the originals.
2. The engineer inspects the profiles and source documentation. Missing units, asset identity, clock basis or authoritative limits remain unresolved; observed ranges do not become allowed operating ranges.
3. A local caller submits a structured command and explicit state with versioned policy. A deterministic evaluator reports `allow`, `block` or `escalate` with reasons. Historical replay of S1 process targets uses explicit `UNQUALIFIED` units and unqualified policy, so it escalates; synthetic fixtures separately exercise eligible/blocked branches. An eligibility result grants no control authority.
4. The simulated reviewer approves a specific eligible proposal. Before a mock outcome is recorded, the gateway checks the command, policy, approval validity and current state again. Changed, expired or insufficient context prevents the outcome.
5. Decisions and mock outcomes remain distinguishable in the local ledger. Errors surface to the caller; an audit failure cannot be represented as successful authorization.

The LLM/retrieval layer is deferred until an approved guidance corpus and evaluation cases exist. Rule reasons and source metadata are not model inference. No model accuracy or operator time savings can be claimed from this foundation.

## Boundaries and information contracts

The local process, file permissions and SQLite store form one workstation trust boundary. Passing a role name on the command line is a simulation, not authentication. A user who can alter code, policy or the database can defeat local workflow controls; the implementation cannot establish separation of duties against that user.

| Contract | Required meaning | Failure treatment |
|---|---|---|
| Raw source | Original file, byte size and digest; archive member identity where applicable | Report unavailable/unsupported/corrupt sources without inventing content |
| Dataset profile | Schema, actual inspection scope, row-count basis, source provenance and observed quality limitations | Keep bounded samples separate from whole-dataset facts |
| Replay/state | Asset, timestamp, explicitly qualified units and mode; mapping/version and source reference | Unknown semantics or stale/invalid state cannot support a new allow |
| Command | Stable proposal identity, action, asset, value/unit, model/version provenance and source references | Unsupported actions, malformed values and mismatches are rejected |
| Policy | Version/identity, action and asset restrictions, limits, freshness and qualification status | Missing, invalid, expired or unqualified policy cannot permit a command |
| Approval | Complete request including state, policy content hash, reviewer label, validity interval and one-use state | Any request/state change needs new approval; missing, mismatched, expired or replayed approval prevents mock execution |
| Decision/outcome | Proposal, policy, state time, rule/reason, actor and distinct evaluation/outcome status | Durable-write failure is visible and prevents reporting a completed transaction |

The machine-readable contracts and implementation are authoritative for field names; this table defines their architectural meaning. Source observations, derived state, policy decisions, human disposition and mock outcomes must retain separate provenance. See [data documentation](../data/README.md) and [measured source observations](data-observations.md) for the inspected schemas and dataset-specific qualification limits.

All five provided inputs are in profiling scope: `logs_dataset.parquet`, `packets_dataset.parquet`, `process_dataset.parquet`, `doi-10.34810-data2936.zip` and `n76t439f65-1.zip`. The archives are separate research collections, not automatically additional runs of the S7 testbed. Shared column names or timestamps are insufficient join keys. Attack and fault labels do not establish safe-command labels. Raw files remain outside version control; checked-in examples and tests must carry their source or synthetic status.

## Threats, assumptions and assurance limits

| ID | Scenario and consequence | Treatment in this increment | Open owner/closure |
|---|---|---|---|
| T-001 | Malformed or adversarial proposal bypasses checks | Structured validation; explicit actions; deterministic rules; negative tests | DME: extend parser/boundary cases before reference freeze |
| T-002 | Dataset/document text is treated as operating instruction | Keep content outside policy/authority path; no dataset-driven execution | Controls owner: approve corpus and source trust before retrieval |
| T-003 | Missing units, bad clocks or wrong asset produces unsafe apparent eligibility | Explicit state and policy contracts; fail closed on missing context | Data/controls owners: qualified mappings and freshness requirements |
| T-004 | Approval is reused or applies to changed inputs | Bind approval to proposal/policy; check expiry/use; revalidate state | Security owner: real identity and independent enforcement before exposure |
| T-005 | Database failure or concurrent attempts produce unrecorded/duplicate mock outcomes | Durable local transaction boundary and replay/failure tests | DME: inspect exact transaction behavior and recovery evidence |
| T-006 | Workstation user edits code, policy, clock or ledger | Explicit trusted-host assumption; do not claim tamper resistance | Platform/security owners: protected policy supply chain, time and evidence store |
| T-007 | Large or corrupt research files exhaust memory/disk | Bounded inspection; archive member inventory; avoid broad extraction | DME: declare sample/scan scope and observed resource use |
| T-008 | Synthetic tests are reported as equipment safety evidence | Label fixtures and finite test coverage; retain unevaluated domain criteria | Controls/release owners: independent expected cases and site validation |

Assumptions: one trusted local operator/developer; no operational network access; input files are supplied for local inspection; no confirmed data redistribution permission; source units, signs and time alignment require evidence. Each assumption is rechecked if source, user population or execution boundary changes.

## Timing, capacity and cost

DISC-001 proposes gateway p95 at 100 ms and explanation p95 at 10 seconds as fictional demonstration targets. These are neither plant deadlines nor achieved SLOs. State freshness, timeout behavior, availability, peak concurrency, RPO and RTO need actual operating context before service qualification. The proposed one-business-day restoration objective and daily backups are also planning assumptions.

Measure input bytes, row counts, scan duration and memory before choosing larger infrastructure. For future sizing retain formulas: daily event bytes = events/second × mean bytes/event × 86,400; retained bytes = daily bytes × retention days × replication/overhead factor; audit bytes = decisions/day × mean audit-record bytes × retention days. Burst factor, event rate, concurrency and all retention periods remain unapproved. File size and sample counts do not demonstrate production throughput.

[COST-001 v0.1](../customer/COST-001.md) remains the single lifecycle cost record. This increment uses local compute and creates no recurring cloud commitment. Local engineering time, storage and dependency costs have not been priced or measured; they are not asserted to be zero. The fictional USD 30,000 ceiling is not a spending authorization. Update the same cost model with measured workload and low/base/high scenarios before a hosted-service decision.

## Verification, release and recovery

The implementation checks are distinct from acceptance: parser boundaries, invalid numbers, denied actions, unavailable/unqualified policy, stale state, wrong asset/unit, unauthorized or expired approval, replay, changed context and storage failure require deterministic tests. Data inspection must demonstrate all five named inputs were attempted and accurately state full-file versus sample scope. The test report must state the actual command, result and execution environment.

AC-01 through AC-06 remain the discovery acceptance candidates. Passing synthetic rule/authority tests provides limited implementation evidence for REQ-01 through REQ-04 and REQ-06; it does not pass AC-01's domain case suite, AC-04's human study, AC-05's recommendation assessment or AC-06's performance/recovery obligations. Independent controls review and representative cases are required before G2 offline validation can pass.

Release manifest: retain code revision, dependency versions, configuration/schema versions, source/profile digests and exact test evidence. See [release gates](../governance/release_gates.md) and [standards tailoring](../governance/standards-tailoring.md). This increment supports work toward G1 reproducibility; no later gate follows automatically.

Rollback is local: stop the CLI, preserve a copy/export of the current ledger and evidence, restore a compatible known code/configuration revision, and replay only into a new demonstration ledger. Do not silently reuse stale approvals or overwrite historical outcomes. Database schema changes need an explicit migration/backup plan. Recovery claims require a tested restore procedure. Operational response and handoff instructions are maintained in [runbooks](../runbooks/README.md).

## Review triggers

Revisit [ADR-001](../architecture/adr/ADR-001-offline-foundation.md), threat controls, contracts, test coverage and COST-001 whenever adding an LLM/provider, live source, command action, policy, mapping, actor, network service or database migration. Cloud and site entry remain conditional on the [entry criteria](../governance/cloud_entry_criteria.csv). The next useful increment is qualified source mapping plus independently reviewed rules/cases, followed by a grounded recommendation layer with abstention evidence.

## v0.4 continuation and trust boundary update

The sections above preserve the first-increment design basis. The user subsequently authorized continued construction through Azure implementation. [ADR-003](../architecture/adr/ADR-003-guarded-model-advice.md) adds an optional fixed-endpoint provider path with exact-claim validation, bounded requests and local fallback. [ADR-004](../architecture/adr/ADR-004-azure-batch-foundation.md) adds a manual Azure job, private storage/registry connectivity, managed identity and controlled artifact export. No equipment path exists. Source semantics and acceptance remain unresolved.

Additional threat cases: model-authored unsupported prose is rejected; changed catalogs invalidate waiting responses; credential/error content is not logged; Azure input blob paths and identities are pinned; output upload success is required before a run is reported complete. Azure job-start privileges can use the job identity through execution overrides and must remain limited to trusted data operators. Container isolation, RBAC effectiveness, private DNS, image pulls and recovery still require live deployment evidence.
