# Operating instructions

This v0.4 application runs on demand and exits; there is no network listener or equipment connection. Default CLI commands stay offline. Explicit `advise --provider openai` can make one outbound request when local evidence and a credential are available. The approved private Azure foundation is deployed with the job disabled; image publication, uploads and job execution are outside that approval. Use the [local setup](../README.md#run-locally), [Azure implementation procedure](../docs/azure-implementation.md) and [current deployment record](../docs/azure-deployment-review.md).

## Start, stop and inspect

1. Verify the five source paths and compare SHA256 against the [source inventory](../data/lineage/source-inventory.json). Keep raw files immutable and outside Git.
2. Run `profile` to generate source observations, `demo` for synthetic branches, or `replay` for historical qualification gating. Ctrl+C stops a local process. Interrupted SQLite transactions roll back; a partially written replay observations file must be regenerated and is not acceptance evidence.
3. Run `audit --db outputs/demo/audit.sqlite3` to export JSON to stdout. Inspect `decision`, `reasons`, `outcome`, `event_id`, `policy_hash`, and `mock_only` before interpreting a result.
4. Run `.venv/Scripts/python.exe -m pytest -q` and `.venv/Scripts/python.exe scripts/check_repository.py` after changes. Original discovery hash must continue to match.

## Failure handling

- Missing, malformed, expired or unqualified policy: escalate; inspect the reason and resolve policy provenance. Never replace a missing real limit with an observed data minimum/maximum.
- Missing/invalid units, action, asset or mode: refuse. Reconcile the source contract before resubmission.
- Stale/future state: refresh actual observation evidence; do not relabel an old observation as current. The synthetic demo refreshes only its artificial fixture.
- Audit unavailable, locked or corrupt: refuse new approval/mock execution. Preserve the failed database for investigation, restore writable local storage and retry with fresh evidence. Do not reinterpret a missing audit event as success.
- Expired, changed or consumed approval: obtain a new approval for current request/policy/state. A proposal ID already mock-executed remains refused across process restarts.
- Profile partial/error: inspect per-file and per-member statuses; a report is not data qualification. Repair input or record the limitation rather than omitting the source silently.
- Qualification partial/error or identity mismatch: preserve the report and compare the input against the pinned inventory. Completion refers to the declared numeric/timestamp inspection scope; engineering qualification remains unresolved.
- Advice catalog unavailable or inconsistent: `advise` returns `catalog_unverified` and exit code 1. Regenerate `profile` then `catalog` from the known inputs; do not hand-edit checksums to suppress the failure. Keep catalog, snapshot and manifest together.
- Unsupported or operational advice query: exit code 2 with empty claims and an abstention reason. This is a valid refusal, not a successful equipment recommendation. An observation response uses exit code 0 and carries exact citations. `eval-advice` uses exit code 0 only when every declared regression case passes.
- Provider unavailable, timed out, unconfigured or refused: inspect `model.status` and `model.reason_code`. A labeled fallback retains exact local observations and exits 3; do not count it as a successful model response. There are no automatic retries. Correct configuration or deliberately retry after reviewing the cause and possible usage cost.
- Invalid model response, changed statement, missing selected claim or invented ID: the local validator rejects it and returns offline observations. Preserve the result metadata for investigation. Do not weaken citation checks to make a response pass.
- Catalog changed or became unverifiable during provider use: `model.status` is `rejected`, claims are cleared and the command exits 1. Rebuild or restore the verified bundle and rerun against the intended evidence version.

## Optional provider operation

Use `advise --provider openai --dry-run` to inspect the exact request without reading `OPENAI_API_KEY` or contacting OpenAI. The preview contains the question, selected observation IDs/statements and catalog identity/hash, plus fixed instructions/schema. It can expose filenames and column names in the observation text. Local paths and raw files are excluded. Inspect any private information included in the question before a live call.

The live command requires `OPENAI_API_KEY` in the process environment; `.env` is not loaded automatically. Use the normal secret-management method for the workstation. The key is used for transport authentication and is excluded from the request preview and response metadata. Default socket timeout is 30 seconds (configurable 1-60); maximum output is 2048 tokens (configurable 256-4096). The timeout is not a total-runtime guarantee. The fixed endpoint, empty tool list and `store=false` are application settings; provider retention remains subject to its data controls. See the [complete provider procedure](../docs/demo.md#optional-openai-advice).

For local recovery, omit `--provider openai` to use deterministic advice. The gateway, approvals and mock execution remain independent of provider availability. Local model metadata is not added to the gateway audit ledger; save the returned JSON separately when retaining evaluation evidence. A live call can consume tokens even when the local validator rejects its result. The checked-in verification does not establish provider uptime, latency, retention compliance or model accuracy.

Actor labels and input state come from the local caller. This process does not authenticate a person, attest telemetry, enforce multiuser policy permissions, or protect evidence from someone who can edit the database. Keep files within appropriate OS permissions; production authority requires a separate design and review.

## Azure job operation and failures

The [Azure guide](../docs/azure-implementation.md) is the concrete bootstrap, private-image publication and job procedure. [ADR-004](../architecture/adr/ADR-004-azure-batch-foundation.md) explains its scope; [Bicep](../infra/main.bicep) defines the deployment. The approved target is `rg-ai-command-gateway-dev`, East US 2, subscription ending `f609`. Foundation deployment succeeded with `jobProvisioned=false`. Do not repeat the new-group bootstrap against a group that now exists; inspect deployment operations and review the group-scoped what-if for any repair. Run `.venv/Scripts/python.exe -m ai_command_gateway.azure_job --local-output outputs/azure-local-demo` for the synthetic local path without Azure credentials.

Cloud execution uses managed identity and private Blob/ACR access. Start with synthetic `demo`; `dataset-analysis` requires explicit configuration and all five pinned inputs already uploaded through a reviewed private-network path. One worker runs per execution, but separate starts can overlap. Each uses a distinct output prefix; there is no global approval ledger. Restrict job-start/template-override permission to trusted deployment operators, independently of application review labels.

- Image pull or startup failure: inspect the execution status, reviewed image digest, `AcrPull` assignment and private registry DNS/connectivity. No application completion manifest means no completed workload evidence.
- Input download or hash/size mismatch: the job fails before analysis. Preserve its fixed error code and inspect exact filenames, input identity, Blob reader scope and network access. Do not replace the inventory digest merely to accept changed inputs.
- Analysis or artifact upload failure: inspect the job's status and final completion record. A partial output prefix or uploaded report alone is not success. Completion is published last; failure to publish it makes the job fail.
- Deployment what-if failure, deletion or indeterminate change: the helper stops before apply. Existing-resource changes require separate review and explicit `-AllowModify`. The script never silently rolls back a partial deployment.

The deployed foundation passed 21/21 control-plane checks through 20 read-only ARM requests. Azure data-plane identity, private DNS resolution, image pull, log access and end-to-end output behavior still require live validation. Control-plane settings alone do not prove private connectivity. Four [Checkov exceptions](../infra/security-exceptions.md) remain documented; static checks do not establish production security. The [image findings](../docs/image-security.md) keep image promotion unresolved. The [bounded container check](../docs/azure-runtime-checks.md) verifies local execution only. The default job makes no hosted-model calls and does not use `OPENAI_API_KEY`.

## Backup, restore and rollback

Use Python's SQLite backup API for a consistent backup; copying only the main file while WAL writes are active can omit decisions. Example from the repository root:

```powershell
.venv/Scripts/python.exe -c "import sqlite3; src=sqlite3.connect('outputs/demo/audit.sqlite3'); dst=sqlite3.connect('outputs/demo/audit-backup.sqlite3'); src.backup(dst); dst.close(); src.close()"
```

Stop local commands before replacing a database. Restore into a new path and inspect events before reuse. Restoring an older database loses later consumed approvals; never claim replay protection across such a rollback. Keep restored evidence read-only for review and start a distinct demo run with fresh proposal IDs. Production recovery and reconciliation remain unqualified.

Code/policy rollback uses a reviewed prior version and a separate output directory. A policy content change invalidates existing bindings. Preserve the source inventory and audit evidence of the changed run. Generated outputs and `.venv` can be removed manually after review; do not remove or modify the original supplied data as cleanup.

For a future Azure image rollback, review and redeploy the Job stage with a previously reviewed immutable digest, then check a separate execution. Preserve existing output prefixes and deployment operations. Blob lifecycle and soft-delete settings do not substitute for a tested recovery procedure. No Azure restore, rollback or production recovery capability has been demonstrated by the local implementation.
