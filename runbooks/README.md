# Operating instructions

This v0.4 application runs on demand and exits; there is no network listener or equipment connection. Default CLI commands stay offline. Explicit `advise --provider openai` can make one outbound request when local evidence and a credential are available. The separately approved private Azure pilot has published the reviewed image, uploaded all five inputs and completed its demo, dataset, identity and expected-failure checks. Temporary operator cleanup and retained-configuration checks are complete. Use the [local setup](../README.md#run-locally), [Azure implementation procedure](../docs/azure-implementation.md) and [current results](../docs/results.md). No hosted-model inference or production acceptance was performed for this pilot.

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

The [Azure guide](../docs/azure-implementation.md) is the concrete private-publication and job procedure. [ADR-004](../architecture/adr/ADR-004-azure-batch-foundation.md) records the foundation decision; [main.bicep](../infra/main.bicep) defines that foundation and [job-only.bicep](../infra/job-only.bicep) isolates job deployment from existing network resources. The approved target is `rg-ai-command-gateway-dev`, East US 2, subscription ending `f609`. The retained job is provisioned with reviewed digest `sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad`. Do not repeat the new-group bootstrap against a group that now exists; review the correct stage's what-if for any change. Run `.venv/Scripts/python.exe -m ai_command_gateway.azure_job --local-output outputs/azure-local-demo` for the synthetic local path without Azure credentials.

Cloud execution uses managed identity and private Blob/ACR access. The retained configuration is `dataset-analysis`; all five pinned inputs were uploaded and fully read back through the approved private path. The synthetic demo was an execution-only override; the image/source fallback remains `demo`. Use the fixed-target [start helper](../scripts/start_azure_pilot_test.ps1) for reviewed pilot modes: it prepares read-only by default and requires `-Run` for one explicit start request. Never automatically retry an ambiguous start. One worker runs per execution, but separate starts can overlap. Each uses a distinct output prefix; there is no global approval ledger. Restrict job-start/template-override permission to trusted deployment operators, independently of application review labels.

- Image pull or startup failure: inspect the execution status, reviewed image digest, `AcrPull` assignment and private registry DNS/connectivity. No application completion manifest means no completed workload evidence.
- Input download or hash/size mismatch: the job fails before analysis. Preserve its fixed error code and inspect exact filenames, input identity, Blob reader scope and network access. Do not replace the inventory digest merely to accept changed inputs.
- Analysis or artifact upload failure: inspect the job's status and final completion record. A partial output prefix or uploaded report alone is not success. Completion is published last; failure to publish it makes the job fail.
- Deployment what-if failure, deletion or indeterminate change: the helper stops before apply. Existing-job changes require review and explicit `-AllowModify`; Job stage refuses changes outside the manual job even with that switch. The script never silently rolls back a partial deployment.

Current live evidence covers private DNS, exact image pull, five input readbacks, successful demo/dataset executions with downloaded-artifact checks, nine identity-probe checks including exact denied input creation, and an expected `configuration_invalid` failure. The identity report was verified from Blob; no probe console rows were captured. The current Wolfi/Python 3.13 [image scan](../docs/image-security.md) has zero known findings within its recorded scanner/database scope. Whole-infrastructure Checkov reports 39 passed, zero failed, four scoped skips and one operator-links parser error; focused job scans have no applicable checks. [The operator plan](../docs/azure-private-access-plan.md) records those limits. Control-plane, data-plane, artifact and local-container checks remain separate evidence; none establishes production security or domain correctness.

After the approved temporary group and all 11 enumerated foundation children are confirmed removed, verify the retained configuration with the [pilot verifier](../scripts/verify_azure_pilot.ps1), omitting `-OperatorPresent`:

```powershell
./scripts/verify_azure_pilot.ps1 -SubscriptionId b31e9bd1-6179-4504-819b-f212ed36f609 -ResourceGroup rg-ai-command-gateway-dev -ExpectedImageDigest sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad -ExpectedJobMode dataset-analysis
```

This read-only ARM command checks the retained job and foundation plus absence of the temporary operator; it does not reconnect to private Blob/ACR/Monitor or repeat cloud executions. While the operator is present, use `-OperatorPresent` only when that state is intended. The temporary operator group and all eleven foundation additions were removed. All 31 post-cleanup configuration checks passed; explicit child and temporary-role absence was verified. The [cleanup helper](../scripts/remove_azure_operator.ps1) defaults to read-only checking and confines its explicitly requested `-Delete` action to the approved temporary group and validated child targets. Preserve cloud evidence locally before removing the access path; retaining private services does not leave a workstation data-plane connection after the operator is removed.

### Historical foundation-only verification

The initial foundation deployment had `jobProvisioned=false` and passed 21/21 checks through 20 ARM GET requests. That original approval excluded image/data publication and execution; the later explicit pilot approval extended the scope. The original [foundation verifier](../scripts/verify_azure_foundation.ps1) expects no job and is not the current pilot check. Its result remains historical evidence in the [deployment review](../docs/azure-deployment-review.md). The deployed job has no hosted-model call and does not use `OPENAI_API_KEY`.

## Backup, restore and rollback

Use Python's SQLite backup API for a consistent backup; copying only the main file while WAL writes are active can omit decisions. Example from the repository root:

```powershell
.venv/Scripts/python.exe -c "import sqlite3; src=sqlite3.connect('outputs/demo/audit.sqlite3'); dst=sqlite3.connect('outputs/demo/audit-backup.sqlite3'); src.backup(dst); dst.close(); src.close()"
```

Stop local commands before replacing a database. Restore into a new path and inspect events before reuse. Restoring an older database loses later consumed approvals; never claim replay protection across such a rollback. Keep restored evidence read-only for review and start a distinct demo run with fresh proposal IDs. Production recovery and reconciliation remain unqualified.

Code/policy rollback uses a reviewed prior version and a separate output directory. A policy content change invalidates existing bindings. Preserve the source inventory and audit evidence of the changed run. Generated outputs and `.venv` can be removed manually after review; do not remove or modify the original supplied data as cleanup.

For a future Azure image rollback, review and redeploy the Job stage with a previously reviewed immutable digest, then check a separate execution. Preserve existing output prefixes and deployment operations. Blob lifecycle and soft-delete settings do not substitute for a tested recovery procedure. No Azure restore, rollback or production recovery capability has been demonstrated by the local implementation.
