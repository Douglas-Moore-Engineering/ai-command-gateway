# Results and evidence - v0.4

**The approved private Azure foundation is deployed in `rg-ai-command-gateway-dev`, East US 2**, using the connected `douglas@dmesystems.global` subscription ending f609. The subscription deployment `aicg-foundation` and nested `aicg-bootstrap` succeeded. All **21/21 read-only control-plane checks passed**. The job remains unprovisioned; no image, supplied dataset or model request was sent to Azure.

Recorded on 2026-10-15 in the client timezone. The [Azure readiness record](../governance/azure-readiness-v0.4.json) preserves approval, target, deployment outputs, image identity, source/report hashes and verification limits. Original v0.2-v0.4 local records and static infrastructure snapshots remain unchanged.

| Check | Observed result | Meaning and limit |
| --- | --- | --- |
| Approved Azure apply | **Succeeded** | Fresh Provider preview: 39 creates, zero modify/delete/unsupported; existing Network Watcher excluded; no job |
| Deployed configuration | **21/21 passed** | Private storage/registry/environment/Monitor controls, exact three direct scoped identity roles, three approved endpoints, six DNS zones with VNet links, no jobs; no data-plane test |
| Infrastructure and scripts | **Bicep compile passed; Checkov 19/0/4; 40/40 contract checks** | Four scoped dispositions remain; contract tests use simulated Azure responses |
| Final image with supplied datasets | **16/16 passed; 81.363 seconds; peak 0.94 GiB** | Actual Linux image under 1 CPU/2 GiB, no swap, network disabled, read-only root, UID 10001; filesystem Blob simulation |
| Final image scan | **0 critical; 44 high mappings across 8 distinct advisories** | 164 mappings across 71 advisory IDs overall; no available fixes reported by the captured database; promotion unresolved |
| Application regression baseline | **452 tests + 44 subtests passed** | Application, test, contract and policy hashes still match the preserved v0.4 run; infrastructure changes do not imply new domain acceptance |

The foundation includes Premium ACR, Standard_ZRS storage, managed identity, an internal Consumption Container Apps environment, VNet/private endpoints/DNS and private Monitor/Log Analytics. The [deployment review](azure-deployment-review.md) records the exact approved action. The [cost estimate](azure-cost-estimate.md) remains approximately **$97.49/month standing core cost**, plus usage and the still-unpriced private publisher/operator path. This is an estimate, not a measured bill.

The final local image has the available compression-library fix and removes the unused pip installer after building. [Image security](image-security.md) preserves all findings and scope; [runtime checks](azure-runtime-checks.md) reproduce the constrained dataset run. A successful package scan process does not mean its security gate passed.

Recheck deployed configuration without changing Azure resources:

```powershell
./scripts/verify_azure_foundation.ps1 -SubscriptionId b31e9bd1-6179-4504-819b-f212ed36f609 -ResourceGroup rg-ai-command-gateway-dev
```

Before enabling the workload, establish private publisher/operator access, disposition image findings, bind the reviewed image to the published registry digest and obtain the separately scoped publication/upload/execution authorization. Actual private DNS, image pull, identity data permissions, denied input writes, completion artifacts, diagnostics and failure behavior remain untested. Engineering semantics, independent cases, authenticated operational authority and production release remain open.

## Historical initial v0.4 local snapshot

The following preserves the local-only state before the separately approved Azure foundation deployment. Current deployment and image evidence are recorded above.

The first Azure implementation is complete locally: a manual Container Apps Job, managed-identity Blob runner, private-service Bicep, pinned container and staged deployment scripts. The optional OpenAI advice adapter is also implemented. **No Azure resources were deployed, datasets uploaded to Azure, or live model calls made.**

Verified on 2026-10-15. The [v0.4 verification record](../governance/local-verification-v0.4.json) combines source hashes, actual command outcomes, local dataset-job evidence, container inspection and infrastructure checks. The v0.2 and v0.3 records remain unchanged.

| Check | Observed result | Meaning and limit |
| --- | --- | --- |
| Python regression | **452 tests and 44 subtests passed** | Gateway, source/catalog/advice, guarded provider failures and Azure runner behavior; external services are simulated |
| Complete local verification | **11/11 stages passed** | Five supplied sources, 154-fact catalog, 12/12 advice cases, 5/5 synthetic demo checks, preview and 20/20 qualification escalations |
| Real dataset job through local Blob simulation | **16/16 checks passed** | Five original input hashes verified; seven published artifact hashes checked; completion last; no raw files or local paths published; no Azure SDK/network calls |
| Deployment script contracts | **14/14 checks passed** | Real Bicep compiler plus fake Azure CLI; explicit apply/modify gates and negative what-if results; no live ARM request |
| Linux container | Build and isolated smoke passed | UID 10001, networking disabled, read-only root filesystem, two synthetic artifacts; SDK imports pass; raw datasets, secrets and workspace outputs excluded |
| Bicep | **Compile exit 0; no warnings** | Main template and six modules; actual Azure target, policy, availability and connectivity remain unchecked |
| Checkov 3.3.29 | **19 passed, 0 failed, 4 skipped** | Four [scoped dispositions](../infra/security-exceptions.md); no image scan, severity-based assurance or production acceptance claim |
| Architecture views | All four Mermaid sources match the index | New model/Azure SVG and PNG previews inspected; exports remain transparent |

The local Blob simulation ran the actual dataset-analysis runner against the supplied files. It passed all 12 engineer-authored advice cases and durably escalated all 20 historical replay rows under `policy_unqualified`. The manifest's `azure_blob` storage label identifies the exercised runtime branch; that run used local files exclusively. These cases establish implementation behavior, not independently reviewed domain correctness.

The optional provider adapter sends only a bounded question and selected observations when explicitly enabled. Local checks accept the complete exact claim set or return a labeled fallback/rejection. Its verified dry run makes no network request. Live provider compatibility, model quality and account data handling remain unevaluated.

Reproduce the local application and real-dataset job checks:

```powershell
.venv/Scripts/python.exe scripts/verify_local.py --input-dir "C:/Users/moore/Downloads"
.venv/Scripts/python.exe scripts/verify_azure_local.py --input-dir "C:/Users/moore/Downloads"
./scripts/test_azure_scripts.ps1
```

Generated logs and reports stay in ignored `outputs/`; versioned governance records are reviewed snapshots. [Infrastructure validation](../infra/validation.md) records exact compiler/scanner commands and exceptions. [Azure implementation](azure-implementation.md) describes the container, staged deployment and runtime checks; [ARCH-004](architecture/README.md#azure-batch-foundation) shows the Azure design.

A deployed pilot next needs the intended subscription, existing resource group, region and private build/upload path, followed by cost/data review, a scanned image digest and target-specific what-if. Live checks must establish image pull, private DNS, managed-identity permissions, artifact completion, logs and failure behavior. The initial job has one worker per execution; separate manual starts can overlap. Container resource sizing remains provisional. Engineering semantics, authenticated operational authority, AC-01-06 and production release remain open.

## Historical v0.3 snapshot

The following records the previous increment. Statements below about an absent provider or cloud integration describe that historical state; current implementation and validation limits are recorded above.

Verified locally on 2026-10-15 with CPython 3.10.11 on Windows. The [v0.3 verification record](../governance/local-verification-v0.3.json) binds the checks to code, contracts, casebook, fixtures, inventory and dependency versions. It preserves the separate [v0.2 record](../governance/local-verification-v0.2.json). Generated profiles, catalog bundles, reports and logs remain under ignored `outputs/`.

| Check | Observed result | Meaning and limit |
| --- | --- | --- |
| Automated regression | 215 tests and 44 subtests passed | Includes malformed/tampered catalog, timestamp nanoseconds, citation/authority bindings, CLI and existing gateway failures |
| Supplied file inspection | 5/5 source profiles complete and 5/5 identities matched | Full S1 numeric/timestamp analysis; S2/S3 retain their declared archive inspection scope |
| Source quality analysis | 28 identity-bound evidence facts | Stored order, repeats and cadence; engineering qualification remains unresolved |
| Observation catalog | 154 facts from five pinned files | Controlled aggregate observations; bundle consistency checks do not authenticate a source |
| Advice regression | 12/12 cases passed: 8 observation cases and 4 abstentions | Exact expected facts/citations; engineer-authored cases used during development, not independent acceptance |
| Synthetic CLI demo | 5/5 checks passed | Existing allow/block/escalate, mock approval and replay refusal behavior preserved |
| Historical replay | 20/20 rows durably escalated with `policy_unqualified` | First-N process records exercise qualification gating; no physical validity labels |
| Repository and diagrams | Consistency passed; both Mermaid sources match index; new SVG/PNG visually inspected | Design and document checks; no production assurance |

The complete run produced all ten expected command outcomes, including exit code 2 for an intentional operational-request abstention. A final full regression rerun covers the evaluator's last validation change. All recorded source hashes were checked again before the versioned snapshot was written.

Process timestamps have median positive spacing of 1.011444222 seconds and a maximum gap of 66.970768608 seconds. Packet records contain 2,966,555 repeated timestamp rows. Log server timestamps decrease once; device timestamps decrease 407 times. These observations do not justify clock alignment, dropped-sample claims or equipment rules. See [source semantics](source-semantics.md).

Reproduce the complete run:

```powershell
.venv/Scripts/python.exe scripts/verify_local.py --input-dir "C:/Users/moore/Downloads"
```

Omit `--input-dir` to run regression, repository consistency and the synthetic demo. The supplied-input mode additionally profiles, qualifies, builds the catalog, queries observations, checks abstention, evaluates the casebook and replays historical records. A failed prerequisite prevents a downstream stage from reusing stale output. The runner writes a new `outputs/verification/summary.json`; it does not overwrite versioned governance records.

Try the current local advisor:

```powershell
.venv/Scripts/python.exe -m ai_command_gateway advise --question "What are the minimum and maximum in_batt_state_of_charge in process_dataset.parquet?" --source S1
```

The response reports observed values 36 and 121 with unresolved physical units and exact citations. It has no command proposal or execution authority. [Catalog design](evidence-design.md) describes the trusted local artifact boundary. [ADR-002](../architecture/adr/ADR-002-cited-observations.md) records the proposed OpenAI Responses API / GPT-6.1 Sol evaluation; no provider is connected and no model inference was used.

AC-01-06 and domain KPI protocols remain unevaluated. Next work requires reviewed engineering meanings, authoritative limits and independent expected cases; source quality checks do not supply these decisions. Local actor labels remain unauthenticated. No physical safety, production latency, availability, avoided loss or customer acceptance claim is made.

## Historical v0.2 snapshot

The following is the prior increment's result and remaining-work record, retained as history. Its statements about absent retrieval describe v0.2; v0.3 behavior is recorded above.


Verified locally on 2026-10-15 using CPython 3.10.11 on Windows. The [machine-readable verification record](../governance/local-verification-v0.2.json) includes commands, dependency versions, source-code/configuration hashes and observed results. Raw logs and generated data remain in ignored `outputs/verification/` and `outputs/profiles/`.

| Check | Observed result | Meaning and limit |
| --- | --- | --- |
| Automated regression | 51 tests and 44 subtests passed | Parser, rule boundaries, approvals, audit faults, restart/concurrency replay, CLI failures and data inspection; synthetic fixtures |
| Synthetic CLI demo | 5/5 checks passed | In-range allow, out-of-range block, missing-evidence escalation, approved mock receipt and replay refusal |
| Supplied source profiling | 5/5 configured file inspections complete | Full Parquet scans and bounded archive metadata/hash scope; source qualification remains unresolved |
| Historical S1 replay | 20/20 rows durably escalated with `policy_unqualified` | First 20 stored process records exercise the qualification gate; no domain accuracy or validity labels |
| Repository consistency | Passed | Local links, stable 6 requirements/6 criteria/8 open items and original discovery hash preserved |
| Diagram review | SVG/PNG rendered and visually inspected; transparent export verified | Design representation and source/index consistency, not runtime assurance |

The Parquet files contain 10,002,790 packets, 13,912 process records and 6,459 logs. Archive metadata covers the independent PV and microgrid collections. See [data observations](data-observations.md) and [file identity inventory](../data/lineage/source-inventory.json). All three S1 files match the publisher's recorded checksums; physical interpretation still requires source review.

Reproduce the recorded software and supplied-input checks from the repository root:

```powershell
.venv/Scripts/python.exe scripts/verify_local.py --input-dir "C:/Users/moore/Downloads"
```

Omit `--input-dir` to run only regression, repository consistency and the synthetic demo. The runner writes a fresh `outputs/verification/summary.json`; the versioned evidence record is a reviewed snapshot rather than automatically rewritten history. A repeated replay/demo adds local audit events with fresh demo proposal identities.

No formal AC-01-06 acceptance result is claimed. The seven [measurement planning records](appendix-a-kpi-dictionary.md) remain unevaluated against their frozen domain protocols. This increment establishes limited implementation evidence; it does not establish physical safety, authenticated human authority, model correctness, operator savings, measured latency SLOs, site recovery, production availability or customer acceptance. No LLM provider, approved corpus, cloud service or equipment adapter has been integrated.

Remaining work: qualify units, clocks, signs, source-to-asset mappings and licenses; obtain authoritative action/state limits and independently reviewed cases; then integrate approved-source advice and evaluate grounding/abstention. The local actor-label and file-permission assumptions must be replaced before an operational authority claim.
