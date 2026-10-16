# Changelog

## 0.4.0 - 2026-10-15

Added an optional OpenAI Responses adapter for `advise`, targeting GPT-6.1 Sol. Default advice remains offline. The adapter supports request preview without credentials, sends only selected observations and the question, and validates exact claim coverage before assembling local citations. Provider failures and invalid outputs return labeled offline fallback. Added simulated-provider regression coverage and documented data exposure, retention and operating limits. No live provider inference or model-quality acceptance was performed; execution remains mock-only.

Extended the same increment through the first Azure implementation: a pinned non-root container, manual job runner with managed-identity Blob access, private-service Bicep, staged review/apply scripts and local deployment-contract checks. Synthetic demo is the default; dataset analysis requires explicit mode selection and the five pinned inputs. Added ADR-004, deployment/runbook guidance and scoped Checkov dispositions.

The user subsequently approved foundation deployment to `rg-ai-command-gateway-dev` in East US 2; deployment succeeded with the job disabled and all 21 read-only control-plane checks passed. Added a new-group subscription wrapper, deterministic role-assignment names, CIDR validation and 40 script checks. The live preview reported 39 creates and no other changes. The final local container passed all 16 dataset checks under 1 CPU / 2 GiB. Patched available image findings and removed the runtime installer; remaining scan findings keep image promotion open. Added [deployment review](docs/azure-deployment-review.md), [cost estimate](docs/azure-cost-estimate.md), [runtime evidence](docs/azure-runtime-checks.md) and [image findings](docs/image-security.md). Image publication, uploads, job execution, live data-plane validation and production acceptance remain pending.

## 0.3.0 - 2026-10-15

Added inventory-bound S1 timestamp/numeric qualification, stable aggregate evidence hashes, a controlled profile-derived catalog with regeneration checks, deterministic cited observation retrieval and abstention, and frozen local advice regressions. New CLI commands: `qualify`, `catalog`, `advise`, `eval-advice`. Source semantics and catalog trust boundaries are documented. Physical units, clock alignment, reviewed domain rules, model API integration and independent acceptance remain unresolved; execution remains mock-only.

## 0.2.0 - 2026-10-15

First authorized offline implementation: profiles for the five supplied datasets, deterministic synthetic policies, SQLite audit/approval transactions, mock execution and replay prevention, real-data qualification-gate replay, CLI and regression tests. Added source observations, contracts, architecture/ADR and standards tailoring. Physical limits, LLM advice, formal acceptance and deployment remain pending.

## 0.1.0 — 2026-10-15

Initial discovery repository: preserved DISC-001, transcribed its text/tables, retained candidate IDs, added trace and unmeasured KPI records, scope/governance boundaries and local repository validation. No application release.
