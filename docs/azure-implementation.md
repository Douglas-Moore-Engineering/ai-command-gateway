# Azure batch implementation

The private Azure pilot is deployed in `rg-ai-command-gateway-dev`, East US 2, subscription ending `f609`. The separately approved temporary operator path published the reviewed image and uploaded all five original inputs with complete Blob readback hash verification. ARM records show successful demo and dataset-analysis executions, with private console logs and downloaded artifacts. Downloaded artifacts passed their verifier checks, the job-identity probe passed all nine checks, and deliberate configuration failure was observed. The temporary operator group and all eleven foundation additions were removed. All 31 post-cleanup configuration checks passed; explicit child and temporary-role absence was verified. Final consolidated evidence is in [the pilot record](../governance/azure-pilot-v0.4.json); [results](results.md) records current verification boundaries.

The retained manual Container Apps Job is configured for `dataset-analysis`. The demo was an execution-only override; the source/image fallback remains `demo`. The job has no web endpoint, hosted-model call or equipment connection. It processes finite inputs, uploads declared artifacts and exits. Concurrent manual starts can overlap; separate UUID prefixes do not create a shared approval ledger.

## Current resources and image

The [foundation template](../infra/main.bicep) defines private networking/DNS, Premium ACR, Blob Storage, a user-assigned managed identity, Container Apps environment and Log Analytics with private Monitor access. [ADR-004](../architecture/adr/ADR-004-azure-batch-foundation.md) records the platform decision. The job identity has input-container read access, output-container write access and image-pull permission; storage keys and model credentials are not used.

The [isolated job wrapper](../infra/job-only.bicep) references existing foundation resources and invokes only the job module. Its live Provider preview showed **1 Create, 33 Ignore, 0 Modify and 0 Delete**. The previous Job-stage preview through the entire foundation template exposed unintended peering changes and was not applied. Job-stage preflight now refuses Create or Modify changes outside the manual job even with `-AllowModify`; Bootstrap retains the original template.

The published registry reference is:

```text
craicgsn5edmznrgh7s.azurecr.io/ai-command-gateway@sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad
```

The [Dockerfile](../Dockerfile) uses a digest-pinned Wolfi base, vendor-maintained Python 3.13, [exact OS package versions](../containers/wolfi-packages.lock) and [hashed Linux amd64 wheels](../containers/python-linux-amd64.lock). It runs as UID/GID 10001. The deny-by-default [.dockerignore](../.dockerignore) excludes raw data, credentials, tests, Git history and local outputs. The reviewed OCI layout was transferred and published without rebuilding or creating a mutable tag; the registry returned the exact reviewed platform manifest digest.

The unfiltered [Trivy scan](image-security.md) reports zero findings across the recorded 34 OS and 34 Python packages. This means no known findings within that scanner/database scope, not vulnerability freedom. The exact image passed 480 tests plus 44 subtests and all 16 [bounded local dataset checks](azure-runtime-checks.md) at one CPU and 2 GiB. The existing Windows CPython 3.10 environment is historical local evidence, separate from the deployed Python 3.13 runtime.

## Recorded live executions

All times below are UTC on 2026-10-16; the user session began on 2026-10-15 local time.

| Mode | Azure execution | ARM interval / status | Runner UUID |
| --- | --- | --- | --- |
| Demo override | `job-aicg-sn5edmznrgh7s-lefuw26` | 03:20:04-03:20:43 / Succeeded | `5b5cf03b-1c1d-48a5-b8bd-60df78c922a1` |
| Retained dataset mode | `job-aicg-sn5edmznrgh7s-uzke2ju` | 03:23:10-03:24:04 / Succeeded | `2fe6e591-4be0-4553-9630-4c2feb27e3a6` |

The private `ContainerAppConsoleLogs` query binds each execution to its runner UUID and completed output prefix. The initial fuzzy-union log query returned an invalid/partial result and was rejected; the helper now accepts an explicit choice of the two known console tables and continues to reject partial/error responses. The original failure record is preserved. ARM completion, console statements, downloaded byte/hash checks and application-result checks are distinct evidence. A start-helper `summary.json` records start acceptance only and is not retroactively rewritten as completion proof.

Private receipts remain under ignored `outputs/azure-pilot-transfer/registry-publication.json` and `input-upload.json`. Execution records are under `outputs/azure-pilot-execution/df13a729-1d62-4523-a0cc-3432b143e562/` for demo and `48f62606-50c8-4aee-8026-7fadcc1a193f/` for dataset analysis. These include ARM observations, bounded private logs and download receipts. Both `artifact-verification.json` records report `all_checks_passed: true` for downloaded contents and declared results. These are separate from ARM completion and private-log bindings; local files alone do not prove cloud provenance, upload ordering, database semantics or domain acceptance.

## Reviewed deployment and operator workflow

The explicit project target and digest are:

```powershell
$subscriptionId = 'b31e9bd1-6179-4504-819b-f212ed36f609'
$resourceGroup = 'rg-ai-command-gateway-dev'
$location = 'eastus2'
$imageDigest = 'sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad'
```

The foundation and job already exist. The following commands describe deliberate reviewed changes, not a request to repeat deployment. Compile/review Job stage using only its wrapper, with the retained workload mode explicit:

```powershell
./scripts/azure_preflight.ps1 -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup -Location $location -Stage Job -ImageDigest $imageDigest -JobMode dataset-analysis -Online
./scripts/deploy_azure.ps1 -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup -Location $location -Stage Job -ImageDigest $imageDigest -JobMode dataset-analysis -Online -Deploy
```

Without `-Online`, preflight compiles locally. Apply requires `-Online -Deploy` and a successful repeated what-if. Existing-job modifications also require reviewed `-AllowModify`; deletion, unknown/unsupported results and any foundation changes are refused. The scripts require explicit subscription/group/region and do not log in, upload inputs, push images or start executions. The [new-group wrapper](../infra/subscription-readme.md) was used for initial foundation creation and must not be rerun against the existing group.

The separately approved [private operator path](azure-private-access-plan.md) uses a temporary Ubuntu VM, Bastion tunnel and scoped user-assigned identity. SCP carries only the reviewed image archive, verified tools and five exact originals. The [transfer helper](../scripts/azure_operator_transfer.py) checks the fixed private hosts, verifies all local input hashes before upload, uses create-only Blob writes and verifies full readback. Existing inputs must match before being skipped; arbitrary endpoints, filenames and overwrite/delete operations are not accepted. No public data staging or VM internet package installation is used.

The helper publishes the verified OCI layout with pinned Crane 0.22.1 and an ephemeral authentication directory. IMDS tokens and registry refresh tokens are not printed. Rebuilding would produce a new artifact requiring separate scan and identity review; the existing review does not cover a future build.

The [execution helper](../scripts/start_azure_pilot_test.ps1) defaults to read-only preparation and sends at most one start request with `-Run`. It validates the fixed live job and reviewed digest, records the execution template, and uses execution-only overrides for demo, probe and deliberate configuration failure. It never changes the retained job. Do not automatically retry an ambiguous start; coordinate operators because pre-start concurrency checks are not atomic.

Treat `Microsoft.App/jobs/start/action` as privileged authority: Azure permits execution-template overrides that can use the job identity. It is separate from an application command approver role. [Microsoft job permissions](https://learn.microsoft.com/en-us/azure/container-apps/jobs#permissions).

## Inputs, outputs and verification

All five original supplied files were uploaded under their exact inventory names in private `inputs`, using the separately approved transfer scope. The runner verifies their identities before analysis. Dataset mode performs profiling, qualification, catalog construction, advice regression and unqualified-policy replay. It uploads seven declared aggregate artifacts plus completion; raw source rows, source prose, replay observations and the replay database are excluded. Demo uploads its report and synthetic audit backup. No artifact establishes equipment policy or production safety.

| Runtime input | Meaning |
| --- | --- |
| `AI_GATEWAY_JOB_MODE` | Retained Azure job: `dataset-analysis`; source/image fallback: `demo` |
| `AZURE_STORAGE_ACCOUNT_URL` | Fixed project's private Blob endpoint |
| `AZURE_CLIENT_ID` | Job user-assigned identity, distinct from the temporary operator |
| `AZURE_INPUT_CONTAINER` / `AZURE_OUTPUT_CONTAINER` | `inputs` / `outputs` |
| `AI_GATEWAY_WORKSPACE` | Writable temporary workspace, `/tmp/ai-command-gateway` |

The transfer helper downloads one exact run into a new directory, with bounded manifest/artifact sizes and full hash checks. The [output verifier](../scripts/verify_azure_outputs.py) additionally checks mode, UUID, complete artifact allowlist, source identities and expected demo/evaluation/replay results without executing SQLite or pickle content:

```powershell
.venv/Scripts/python.exe scripts/verify_azure_outputs.py --run-dir <downloaded-run-directory> --expected-mode dataset-analysis --expected-run-id 2fe6e591-4be0-4553-9630-4c2feb27e3a6
```

That verifier checks downloaded files only. Pair it with separate ARM execution state, execution-bound private logs and transfer receipts before asserting cloud-run verification. Private log access uses the explicitly confirmed `ContainerAppConsoleLogs` table, a fixed execution filter, 24-hour window, 2,000-row cap and 16-MiB response bound. The job-identity probe passed all nine checks: private Blob/registry DNS, metadata plus a one-byte read for all five inputs, exact HTTP 403 `AuthorizationPermissionMismatch` on input creation, and output create/read persistence. No unexpected input blob was created. Execution `job-aicg-sn5edmznrgh7s-vo1uj55` succeeded at 03:29:46-03:30:20 UTC. Its persisted report and constant were read back with verified hashes; the report SHA-256 is `fd17421a8efa6fc4a2e445af2ca0f14584b69a28dbb3cd4f0b3023acb4dadca0`, retained under `outputs/azure-pilot-execution/3384f84c-8290-4e33-a04c-b7ededdd07e9/report-readback.json`. No probe console rows were captured, so the report, execution template and time supply the evidence.

The deliberately invalid configuration execution `job-aicg-sn5edmznrgh7s-76kvm8l` is ARM `Failed`; private logs contain exactly the safe application error `configuration_invalid`. Its evidence is under `outputs/azure-pilot-execution/877c2585-9f05-42cc-a99d-95a9af9df52f/`. This is the expected failure-path result, not a successful application workload.

The [pilot configuration verifier](../scripts/verify_azure_pilot.ps1) checks live ARM settings and distinguishes whether temporary operator resources should exist. It makes no data-plane calls. The [cleanup helper](../scripts/remove_azure_operator.ps1) defaults to read-only checking and restricts approved deletion to the temporary operator group plus 11 enumerated foundation children after checking their targets. The temporary operator group and all eleven foundation additions were removed. All 31 post-cleanup configuration checks passed; explicit child and temporary-role absence was verified. Core standing cost remains about $97.49/month plus usage; temporary access adds the separately approved charges until removed. See [cost estimate](azure-cost-estimate.md) and [operator plan](azure-private-access-plan.md).

## Assurance limits and historical foundation evidence

The current local suite records 590 passed tests plus 44 subtests and one skip; subsequent focused suites passed 46 transfer/log tests, 61 execution-start checks and 28 pilot-verifier tests. The strengthened start-helper version postdates the actual starts, whose own helper hashes remain in the execution receipts. All 46 deployment-script contracts passed using a real local Bicep compiler and simulated Azure CLI. The full infrastructure Checkov scan reports **39 passed, zero failed, four scoped skips and one parser error** in `operator-foundation-links.bicep`; focused job scans have zero applicable checks. [The operator plan](azure-private-access-plan.md) identifies the parser limitation and raw evidence. Bicep/Provider validation and observed controls are separate from static-check coverage.

Historically, the separately approved foundation-only deployment succeeded with the job disabled. Its preview showed 39 creates, and the original verifier passed 21 checks through 20 read-only ARM requests, including exact job-identity roles, private endpoints/DNS, AMPLS settings and no jobs. That no-job result describes the earlier milestone, not the current pilot. The [foundation review](azure-deployment-review.md) and [original v0.4 snapshot](../governance/local-verification-v0.4.json) preserve the historical evidence; do not use the no-job verifier as a current pilot acceptance test.

Cloud execution does not resolve source units, clock relationships, engineering policy, reviewed cases or independent acceptance. No live model, equipment integration, production availability/latency guarantee, customer acceptance or measured operating benefit is claimed. [Release boundaries](../governance/release_gates.md) remain in force. The versioned pilot record preserves the closure evidence; Git history identifies the published revision.
