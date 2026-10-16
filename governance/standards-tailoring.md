# Standards applicability and engineering management baseline

Artifact: SAR-SEMP-001 v0.1, 2026-10-15. Prepared by DME delivery lead for the local offline increment. Status: preliminary applicability/tailoring record with unresolved assurance conditions. Receiving roles: DME technical implementer and user scope reviewer. This is a consolidated equivalent for the applicability, SEMP, viewpoint and assurance records; no formal conformity or independent assessment is claimed.

The original sections preserve the local increment's design basis. Later Azure authorization and evidence are recorded in the v0.4 follow-ons below; they do not rewrite the discovery or imply formal standards acceptance.

## Authority and lifecycle tailoring

The current user request authorizes starting local implementation. [DISC-001 v0.1](../customer/DISC-001-v0.1.md), REQ-01–06, AC-01–06 and OPEN-01–08 retain their evidence status. Fictional customer roles and budgets are scenario inputs, not actual signatories or commitments. [BASE-001](../docs/implementation-baseline.md) defines the current scope, owners, risks and technical boundaries.

Apply an incremental lifecycle: local foundation and data qualification; reviewed offline rules/cases; independent validation; then separately governed shadow/advisory exposure if authorized. Customer phases 3–7 receive bounded scope and assurance inputs for this increment, phase 8 implements it, and phase 9 reviews changes continuously. Commercial contracting, real site adaptation, ORR, CAR, production support and retirement execution remain pending rather than implicitly completed. There is no paid-service or production obligation in this local increment.

The local foundation may proceed while customer policy, equipment limits and hosting inputs remain unresolved because it supplies no real equipment command path. Those gaps block the dependent domain validation, cloud and site decisions. This tailoring does not waive production safeguards.

## Applicability register and source status

The installed `systems-engineering-standards-assurance` reference supplies the candidate families below. No contractual standard edition or normative clause has been adopted for this project; editions and official publisher metadata must be verified before adoption. This record maps engineering concerns to controls and does not assert a standard's detailed requirements or current publication status.

| Candidate guidance | Applicability / owner | Current control and evidence | Edition/adoption and review trigger |
|---|---|---|---|
| ISO/IEC/IEEE 15288 and 12207 | Project system/software lifecycle; DME lead | Increment boundaries, requirements, code, tests and release evidence | Pending; before technical baseline freeze |
| ISO/IEC/IEEE 42010 | Architecture concerns/views; DME architecture owner | BASE-001, ADR-001 and system/authority view | Pending; before architecture approval |
| ISO/IEC/IEEE 29148 | Requirements clarity/trace; DME with future controls owner | Existing stable REQ/AC IDs; unresolved semantic and acceptance inputs explicit | Pending; before requirements freeze |
| ISO/IEC/IEEE 15289 | Information control; DME lead | Versioned repository, source manifest and evidence indices | Pending; before contractual information baseline |
| ISO/IEC/IEEE 24748 family | Lifecycle tailoring/management plan; DME lead | This consolidated plan and explicit phase boundaries | Pending; before engineering governance baseline |
| IEEE 1012 | V&V rigor/independence; future release reviewer | Negative/fault tests now; independent domain review still required | Pending; before offline validation claim |
| ISO/IEC 25010 | Software quality coverage; DME lead | Quality concerns below; no service SLO measured | Pending; before NFR approval |
| ISO/IEC 23894 | AI risk guidance; DME with controls/security owners | BASE-001 threat/assumption table; deferred AI layer | Pending; revisit before retrieval/model integration |
| ISO/IEC 42001 / 42005 | Organization/impact overlays; owner unassigned | No organization-wide assessment or applicable contract established | Deferred applicability decision before customer deployment |
| INCOSE handbook | Optional engineering guidance; DME lead | Stakeholder/requirement/architecture/V&V trace | Edition adoption pending; no certification claim |
| Industrial safety/security and regulatory overlays | Future site/customer owners | No site, jurisdiction or equipment classification established | Deferred until site context; do not infer applicability from research data |

Public publisher summaries, when later inspected, support publication metadata only. Clause-level claims require the actual normative text and an identified assessment basis. Organizational competence, quality management, retention and supplier approval remain organizational/customer responsibilities; repository contents alone cannot satisfy them.

## Engineering management and review plan

| Activity | Controlled artifact / decision | Responsibility and exit evidence |
|---|---|---|
| Scope/configuration | BASE-001; historical DISC-001; code and config versions | DME proposes; user decides scope; preserve history and input digests |
| Requirements and interfaces | Existing requirements/acceptance/traceability registers; data contracts | DME maintains IDs; controls owner must review units, limits and expected outcomes |
| Architecture | ADR-001 and architecture index | DME records tradeoffs; add ADR when trust, authority or deployment changes |
| Integration | Profiler and gateway tests with clearly labeled fixtures | DME records exact source/config versions; no automatic dataset merge |
| Verification | Deterministic unit/integration/negative tests and audit failure checks | DME records actual results; tests remain implementation evidence |
| Validation | Reviewed domain cases and usability/recommendation protocols | Independent domain reviewer unassigned; G2 acceptance remains pending |
| Release/transition | Release gates, evidence manifest and runbooks | Separate engineering, governance and customer decisions; no operational release now |
| Operation/recovery | Local error reporting and ledger backup/export procedure | DME documents; service availability and restore targets need tested evidence |
| Change/revalidation | Change history, affected requirements, new test evidence | Reopen affected baseline for policy/model/mapping/dependency/exposure changes |
| Cost | COST-001 v0.1, the single lifecycle model | DME prepares quantities/scenarios; budget authority unassigned; no spending inferred |
| Exit | Preserve evidence; export local ledger; revoke future access where applicable | DME proposes scope; user directs deletion/retention; no silent destruction |

Review COST-001 at architecture/hosting decisions, operational readiness, material changes and exit. Missing rates and workload prevent an affordability claim, while this local implementation remains authorized. Estimate effort, third-party usage, review, support and retirement separately; do not count fictional budget as a cost estimate.

## Requirements quality and V&V coverage

REQ-01 needs action-specific units, mode/state semantics and authoritative constraints before an equipment validity claim. REQ-02 needs an actual deployment permission boundary before isolation can be claimed against an untrusted actor. REQ-03 can be exercised with simulated identities; production authorization remains unresolved. REQ-04 needs explicit versions, source and outcome linkage; retaining a database alone is insufficient. REQ-05 awaits approved guidance and independently reviewed recommendations. REQ-06 needs both local fault cases and actual operational timing/recovery obligations. Existing IDs are preserved; none is silently redefined as accepted.

Current rigor is appropriate to a no-actuation reference implementation: reproducible parser/rule tests, negative and fault cases, replay checks, source inspection, and peer review of the code/evidence. Implementer-authored fixtures are not independent ground truth. Controls-domain review, realistic attack evaluation, human-factors testing and representative performance/recovery evidence are required before stronger claims. Physical criticality must be reassessed before any actuation design.

Quality coverage: functional suitability and security are exercised by rule/authority tests; reliability by failure/restart tests; performance by future measured workload; compatibility by versioned file/JSON interfaces; interaction by CLI error messages and future operator study; maintainability by separated modules, fixtures and reproducible setup; adaptability by explicit contracts; safety by mock-only scope and unresolved physical validation. These are project concerns, not claims of exhaustive standards coverage.

## Viewpoint and correspondence rules

The [system/data/authority view](../docs/architecture/README.md) serves the implementer, data reviewer and future controls/security reviewer. Its Mermaid model distinguishes input sources, data qualification, deterministic decisions, simulated human authority and evidence. Every executable arrow must correspond to code; a future/proposed relationship must be labeled. Profiles may inform a mapping review but cannot authorize commands. Source and rendered preview must agree. No plant actuation or cloud component may appear as implemented without code and authorization evidence.

## Return assessment

This package makes the bounded local increment reviewable. It supplies scope, architecture, a tailored engineering plan, threats and an assurance gap register through the referenced artifacts. It does not complete formal standards assessment, domain acceptance or G2 validation. DME returns actual implementation/test/profile evidence through [the handoff](../customer/HANDOFF.md); the user may review the next engineering increment. Before cloud/site exposure, close the assigned [entry conditions](cloud_entry_criteria.csv), verify/adopt the relevant standards baseline and obtain the applicable release decisions.

## v0.4 change review

User authorization now includes Azure implementation artifacts. The referenced-workload plan uses the existing CLI, source contracts and synthetic policy boundary. Private data endpoints, managed identity, scoped Blob roles, digest-addressed job images and local validation are proposed controls with code evidence. They do not replace live RBAC/DNS/image-pull tests or independent domain review. Model transport and fallback tests address the new provider failure boundary; hosted quality, cost, availability and data rights remain open. [Azure implementation](../docs/azure-implementation.md) records remaining entry conditions.

## v0.4 foundation authorization follow-on

The user explicitly approved foundation provisioning in the Douglas DME Systems subscription ending `f609`, new group `rg-ai-command-gateway-dev`, East US 2. Foundation deployment succeeded with the job disabled; [deployment review](../docs/azure-deployment-review.md) records scope and actual outcome. [COST-001](../customer/COST-001.md) records approval of the reviewed standing costs, usage and partial-deployment risk. Source semantics do not prevent this bounded, no-actuation foundation from being provisioned; they still block dependent domain and operational claims.

The actual 39-create preview, successful deployment, 21/21 read-only control-plane checks, current static/script checks and [bounded local container evidence](../docs/azure-runtime-checks.md) extend implementation evidence. They do not establish effective data-plane access, private DNS resolution, an accepted image, runtime availability or customer acceptance. [Image findings](../docs/image-security.md), private access, dataset-transfer review and subsequent job authorization remain visible conditions. No formal G0/G1, G2, standards-conformity or production-release claim is made.

## v0.4 private pilot change review - 2026-10-16 UTC

The later user approval covers the temporary operator, reviewed image publication, five original uploads, cloud tests and scoped cleanup. This extends the historical foundation-only authorization above. Actual evidence now establishes private DNS, image pull, scoped managed-identity reads/output writes and denied input creation; successful demo/dataset completion with hash-bound output verification; and one deliberate configuration failure. The reviewed image has zero findings in the captured scan database. The whole-infra static scan still has four scoped exceptions and one operator-links parser error; zero applicable job checks are not a security pass.

Stable requirements, acceptance IDs and historical evidence are preserved. REQ-02 gains specific Azure permission evidence, while user authentication and approval-role separation remain unresolved. REQ-04 gains linked ARM/log/run/artifact records. REQ-06 gains one actual cloud configuration-failure observation, without a service availability, restore, dependency-failure or timing acceptance claim. Implementer-authored cases and agent peer review do not constitute independent domain validation.

The receiving engineering role may review the bounded pilot and continue source/policy qualification. Temporary-access retirement and retained-resource checks belong to this approved increment; broader service transition and production release remain separate. The existing candidate standards register and edition-adoption gaps remain unchanged. No normative clause, standards conformity, formal G0/G1/G2 approval or customer acceptance is inferred from the deployment. [Results](../docs/results.md) and [handoff](../customer/HANDOFF.md) carry the current evidence and limitations.

The approved temporary access retirement is now complete: The temporary operator group and all eleven foundation additions were removed. All 31 post-cleanup configuration checks passed; explicit child and temporary-role absence was verified. This closes the scoped pilot transition/retirement evidence only; the retained system remains a mock-only reference implementation.
