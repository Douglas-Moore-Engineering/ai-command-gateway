# Changelog

## 2026-10-16 — Cited explanations

- Added opt-in provider explanations with local citations, bounded validation and explicit semantic-review limits.
- Added plain-text answers, saved output and reproducible offline/simulated examples.
- Preserved exact-evidence mode, offline defaults, mock-only execution and historical cloud evidence.

## Azure retirement - 2026-10-16 (verified)

The user requested retaining the established Azure subscription ending `f609` and deleting its other resources. Final read-only ARM verification at **05:13:03 UTC** confirmed the subscription remains `Enabled`, with zero active resources, zero resource groups, zero project-principal role assignments and zero management locks; both existing subscription Owner assignments were preserved. The three inventoried groups were deleted: project foundation, Container Apps managed resources and Network Watcher, including the cloud image, five uploaded inputs, manual job and cloud results. This supersedes the earlier retain-foundation decision after operator cleanup. The [retirement record](governance/azure-retirement-v0.4.json) preserves the verification and provider-recovery limits.

Original local datasets, downloaded evidence, the source repository and GitHub source remain retained. The completed pilot and historical governance snapshots are preserved. The previous standing-cost estimate is historical; deletion does not imply zero final charges, and billed cost remains unmeasured.

## 0.4.0 - 2026-10-15

### Historical Azure pilot continuation - 2026-10-16 UTC, before retirement

Published the exact reviewed Wolfi/Python 3.13 image to private ACR at `sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad`, without rebuilding. The recorded unfiltered Trivy scan has zero findings in its scanner/database scope. Created the separately approved temporary private operator path, uploaded all five inventory-bound originals using create-only writes and verified their full Blob readback hashes. The retained job uses `dataset-analysis`; demo remains the source/image fallback and was tested through an execution-only override.

Added the isolated `job-only.bicep` wrapper after a foundation-template preview exposed unwanted peering changes; the corrected Provider preview showed one create and 33 ignores. Azure records successful demo and dataset-analysis executions, and private console logs bind them to distinct runner UUIDs. Added bounded transfer/log and downloaded-artifact verification helpers, a job-identity probe, explicit execution-start controls and scoped cleanup tooling. Downloaded artifact checks passed for both runs. The identity probe passed all nine checks, including exact denied input-write permission and output write/read; a deliberate invalid configuration produced ARM Failed and the safe expected error. The temporary operator group and all eleven foundation additions were removed. All 31 post-cleanup configuration checks passed; explicit child and temporary-role absence was verified. Final closure evidence is in [the pilot record](governance/azure-pilot-v0.4.json).

The local suite records 590 passed tests plus 44 subtests and one skip; subsequent focused suites pass 46 transfer/log tests, 61 execution-start checks and 28 pilot-verifier tests, and deployment-script contracts pass 46 checks. The strengthened start helper postdates the actual execution starts. Whole-infrastructure Checkov records 39 passed, zero failed, four scoped skips and one parser error; focused job scans have no applicable checks. The [private-access plan](docs/azure-private-access-plan.md) preserves those limits. Git history identifies the published revision; no remote CI result is claimed. No live model, production acceptance or independently reviewed domain qualification is claimed.

### Historical foundation and application milestone

Added an optional OpenAI Responses adapter for `advise`, targeting GPT-6.1 Sol. Default advice remains offline. The adapter supports request preview without credentials, sends only selected observations and the question, and validates exact claim coverage before assembling local citations. Provider failures and invalid outputs return labeled offline fallback. Added simulated-provider regression coverage and documented data exposure, retention and operating limits. No live provider inference or model-quality acceptance was performed; execution remains mock-only.

Extended the same increment through the first Azure implementation: a pinned non-root container, manual job runner with managed-identity Blob access, private-service Bicep, staged review/apply scripts and local deployment-contract checks. Synthetic demo is the default; dataset analysis requires explicit mode selection and the five pinned inputs. Added ADR-004, deployment/runbook guidance and scoped Checkov dispositions.

The user subsequently approved foundation deployment to `rg-ai-command-gateway-dev` in East US 2; deployment succeeded with the job disabled and all 21 read-only control-plane checks passed. Added a new-group subscription wrapper, deterministic role-assignment names, CIDR validation and 40 script checks. The live preview reported 39 creates and no other changes. The then-current local container passed all 16 dataset checks under 1 CPU / 2 GiB. Patched available image findings and removed the runtime installer; remaining scan findings kept image promotion open at that milestone. Added [deployment review](docs/azure-deployment-review.md), [cost estimate](docs/azure-cost-estimate.md), [runtime evidence](docs/azure-runtime-checks.md) and [image findings](docs/image-security.md). Image publication, uploads, job execution and live data-plane validation were pending at that historical point; the continuation above supersedes that state. Production acceptance remains open.

## 0.3.0 - 2026-10-15

Added inventory-bound S1 timestamp/numeric qualification, stable aggregate evidence hashes, a controlled profile-derived catalog with regeneration checks, deterministic cited observation retrieval and abstention, and frozen local advice regressions. New CLI commands: `qualify`, `catalog`, `advise`, `eval-advice`. Source semantics and catalog trust boundaries are documented. Physical units, clock alignment, reviewed domain rules, model API integration and independent acceptance remain unresolved; execution remains mock-only.

## 0.2.0 - 2026-10-15

First authorized offline implementation: profiles for the five supplied datasets, deterministic synthetic policies, SQLite audit/approval transactions, mock execution and replay prevention, real-data qualification-gate replay, CLI and regression tests. Added source observations, contracts, architecture/ADR and standards tailoring. Physical limits, LLM advice, formal acceptance and deployment remain pending.

## 0.1.0 — 2026-10-15

Initial discovery repository: preserved DISC-001, transcribed its text/tables, retained candidate IDs, added trace and unmeasured KPI records, scope/governance boundaries and local repository validation. No application release.
