# AI governance plan — current screen, 2026-10-16

## Cited explanation change — 2026-10-16

User-authorized local work adds opt-in cited model prose, plain-text output and saved answers. [ADR-005](../architecture/adr/ADR-005-cited-explanations.md) records the change and bounded checks; [verification](cited-explanation-verification-2026-10-16.json) records actual evidence. Exact evidence, offline defaults, mock-only authority and Azure retirement remain intact. This increment has no live-provider or domain-quality result and no new release/gate approval. Lifecycle/control-coverage JSON projections are absent; no executable checker PASS is claimed. Manual review checks the existing scope, trace, unchanged authority boundary, fallback and regression evidence. Future production exposure remains blocked by the existing unresolved conditions; next permitted work is offline review or a separately scoped live-provider evaluation. Douglas Moore remains the maintainer; independent domain reviewer is unassigned.

Status: provisional screen, not an approved governance baseline. Real owner/preparer: Douglas Moore. Fictional engagement roles provide no real approval authority. The current repository supports offline source observations, synthetic policy validation and mock execution. The optional provider adapter exists but no live inference is evidenced. Azure is retired; maintenance does not reconnect it.

## Current exposure and evidence

The bounded private Azure pilot completed demo and dataset executions, nine job-identity checks, an expected configuration failure and operator cleanup checks. The [pilot record](azure-pilot-v0.4.json) preserves exact scope and historical bindings. Separate [retirement evidence](azure-retirement-v0.4.json) records removal of active cloud resources while retaining the subscription. These events supersede the historical implementation-only status below; neither is production release authorization.

Advice has no policy-edit, approval or execution authority. Local actor labels are simulated identities. Synthetic policy limits are not validated physical limits; dataset observations remain context only. No equipment adapter or live command path is present. Loss of advice must preserve manual/non-AI operations; equipment-specific safe responses still require domain engineering.

Impact tier remains provisional and unassigned pending asset-specific consequence assessment. AIG-G0 through AIG-G7 have no recorded PASS decision. Atomic governance requirements, applicable obligations, corpus/supplier rights, independent assessment, residual-risk acceptance and review cadence remain unresolved. [Open conditions](../customer/open-items.csv), [release gates](release_gates.md) and [handoff](../customer/HANDOFF.md) remain authoritative. No safety certification, domain acceptance, business benefit or completed governance gate follows from software tests.

## Maintenance and future change

[Current local verification](repository-maintenance-2026-10-16.json) and [offline CI](../.github/workflows/offline-verification.yml) check software and repository consistency only. Self-review is not independent assurance. Historical records remain unchanged; current evidence uses separate source hashes and environment details. Remote CI outcomes and merge controls must be verified separately. A future cloud connection, live provider evaluation, authenticated deployment or equipment influence requires its own scope, exposure and authorization assessment.

## Historical screen and implementation progression

# Historical AI governance screen — v0.2

Status: discovery screen carried forward, not an approved governance baseline. Scope: offline advisory reference concept, mock output only. Real owner/preparer: Douglas Moore. Fictional controls/security/platform/operations roles have no real sign-off authority.

Impact tier remains provisional and unassigned pending asset-specific consequence assessment. The current repository has no operational exposure. Future equipment influence can introduce physical harm, automation bias, policy tampering, stale-state decisions and authority bypass. No residual-risk reduction is claimed without implemented/tested controls.

AIG-G0 through AIG-G7: no PASS decision or production authorization. Classification, obligations/control applicability, atomic governance requirements, independence, supplier/corpus rights and review cadence require scoped assessment before design baseline. No safety certification is claimed. REQ-01–06 now trace local synthetic policy, approval and audit tests. Those tests do not establish production identity, physical limits, independent assessment or completed governance gates.

No live actuation, LLM execution credential or policy-edit authority is permitted by the current scope. Loss of AI advice must preserve existing manual/non-AI operations. Equipment-specific safe responses require domain engineering. [Open conditions](../customer/open-items.csv) and [handoff](../customer/HANDOFF.md) remain authoritative.

The implemented scope is a single-host offline CLI with user-supplied state and actor labels, unqualified historical context and synthetic policy fixtures. [Implementation threats](../docs/implementation-baseline.md) and [results](../docs/results.md) record tested controls and residual gaps. No LLM provider or approved retrieval corpus is connected.

## v0.3 local continuation

Source timestamp/numeric quality analysis and exact observation retrieval now extend the offline foundation. The catalog retains unresolved qualification, source identities and explicit context-only status. [ADR-002](../architecture/adr/ADR-002-cited-observations.md) records the implemented design and proposed hosted runtime. No provider is connected and no governance or acceptance gate is passed by this increment. [Results](../docs/results.md) distinguish regression evidence from domain measurement.

## v0.4 model and Azure implementation

The optional OpenAI adapter and Azure batch artifacts are implemented under the user's continuation requests. Model claims remain exact context-only observations; no tools, approval authority or operating recommendations are delegated. The initial Azure job performs offline demo or dataset analysis with managed identity, not hosted inference. [ADR-003](../architecture/adr/ADR-003-guarded-model-advice.md), [ADR-004](../architecture/adr/ADR-004-azure-batch-foundation.md), and [results](../docs/results.md) separate local controls from unverified live behavior. No Azure or governance gate is passed by generating code.
