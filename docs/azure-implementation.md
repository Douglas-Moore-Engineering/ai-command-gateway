# Azure batch implementation

The Azure target is a manually started Container Apps Job. It runs the existing synthetic demo by default, records artifacts in Blob Storage and exits. Dataset analysis is a separate opt-in job mode. There is no web endpoint, equipment connection or hosted-model call in this job. The user approved foundation deployment to `rg-ai-command-gateway-dev` in East US 2; deployment **succeeded** with the job disabled. [Deployment review](azure-deployment-review.md) records the outcome and [results](results.md) distinguishes local checks from Azure verification actually performed.

Foundation approval covers about $98/month in standing core charges, plus usage and an unpriced private builder/access path; the detailed [regional estimate](azure-cost-estimate.md) is $97.49/month before usage. Image publication, dataset uploads, job provision/execution and model inference are outside this approval. The [image findings](image-security.md) remain unresolved for promotion.

The [Bicep template](../infra/main.bicep) defines the resource-group deployment. [ADR-004](../architecture/adr/ADR-004-azure-batch-foundation.md) records the platform choice. The template includes a VNet, private endpoints/DNS, a private Premium container registry, Blob Storage, a user-assigned managed identity, Container Apps environment and Log Analytics with private Monitor access. The job identity receives input-container read access, output-container write access and image-pull permission. No account key or model credential is required.

Private endpoints make connectivity part of deployment. Image pushes and Blob data access need a host with the VNet/private-DNS path; a laptop with only an Azure login is insufficient. Provisioning the foundation first resolves the registry/image bootstrap dependency. [Microsoft ACR private endpoint guidance](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-private-endpoints)

## Container and local check

The [Dockerfile](../Dockerfile) uses Python 3.10 slim pinned by image digest and runs as UID/GID 10001. Core dependencies are pinned in [requirements-runtime.lock](../requirements-runtime.lock), with Azure SDK dependencies in [requirements-azure.lock](../requirements-azure.lock). The [deny-by-default build context](../.dockerignore) admits application code, controlled schemas/inventory/cases and synthetic policy/sample files. It excludes raw datasets, tests, credentials, `.git`, local outputs and environments. Runtime files are read-only to the application user; per-run artifacts use a writable temporary workspace.

From the repository root with a working Docker engine:

```powershell
docker build --platform linux/amd64 --tag ai-command-gateway:local .
docker run --rm ai-command-gateway:local --local-output /tmp/local-verification
```

The local command needs no Azure account. Retain its stdout as smoke-test evidence; the container's temporary output is removed with the container. To update the base, supply a reviewed image digest through `--build-arg PYTHON_IMAGE=python:3.10-slim@sha256:...`, scan the resulting image and retain its exact registry digest. Preserve a digest when overriding the build argument. A successful Windows Python test run is not proof that the Linux container builds or runs.

The final reviewed local build upgrades `liblzma5` to the available fixed version and removes the pip installer from the runtime filesystem. Its [scan evidence](image-security.md) still records 44 high-severity occurrences across eight advisories, with no fixed version available in that scan. The [resource check](azure-runtime-checks.md) runs the actual five-dataset pipeline using local Blob simulation under 1 CPU / 2 GiB, read-only root, UID 10001 and disabled network. All 16 checks passed in 81.363 seconds; this does not verify Azure data-plane behavior.

## Compile and review

The group deployment scripts require an explicit subscription, existing resource group and region. They never log in, create the resource group, choose a default subscription or install tools. The separate [subscription wrapper](../infra/subscription-readme.md) creates a new group and its foundation with the job fixed off; that workflow was used for the approved foundation. Use Azure CLI and an already installed Bicep executable; this workspace's compiler is detected at `.cache/azure-cli/bin/bicep.exe`, or pass `-BicepPath`.

The approved foundation target is:

```powershell
$subscriptionId = 'b31e9bd1-6179-4504-819b-f212ed36f609'
$resourceGroup = 'rg-ai-command-gateway-dev'
$location = 'eastus2'
```

Compile without contacting Azure:

```powershell
./scripts/azure_preflight.ps1 -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup -Location $location -Stage Bootstrap
```

After signing in separately, request an online what-if:

```powershell
./scripts/azure_preflight.ps1 -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup -Location $location -Stage Bootstrap -Online
```

The script compiles Bicep, writes explicit parameters under `outputs/azure/`, verifies the selected account/resource-group identity and saves ARM what-if JSON. It rejects failed what-if, deletion, unsupported or unknown change types. Existing-resource modifications stop by default; after reviewing the saved changes, repeat deliberately with `-AllowModify` if they are intended. `Create`, `NoChange` and out-of-template `Ignore` are allowed. Review role assignments, private DNS, regional availability and expected cost before applying. What-if predicts changes; it is not a runtime connectivity or capacity test. [Microsoft what-if reference](https://learn.microsoft.com/en-us/cli/azure/deployment/group?view=azure-cli-latest#az-deployment-group-what-if)

The deployment principal needs resource-deployment permissions and permission to create the declared role assignments. A logged-in account is not evidence of those permissions. The scripts use explicit `--subscription` on every Azure command and incremental deployment mode.

Run `./scripts/test_azure_scripts.ps1` to exercise the script gates locally with a real Bicep compiler and an isolated fake Azure CLI. All 40 current checks passed, including review/apply flags, negative what-if cases and CIDR round trips; the report is written under `outputs/azure-script-verification/`. These are script-contract tests. Separately, the live subscription preview for the approved foundation reported 39 creates and no modifications, deletions or unsupported changes.

Optional `-VnetAddressPrefix`, `-EnvironmentSubnetPrefix` and `-PrivateEndpointSubnetPrefix` parameters retain the `/16`, `/23` and `/24` defaults. Validation requires canonical IPv4 network prefixes, contained non-overlapping subnets and environment/endpoint subnet sizes of `/27` or larger. Review reserved ranges and conflicts with connected networks separately. Use identical reviewed CIDRs for preview and apply.

## Bootstrap, publish and provision the job

The following commands describe the deployment stages. The approved new-group foundation deployment already succeeded; do not rerun that bootstrap against the existing group. Image publication and job deployment/start remain future actions outside the current approval.

1. For an already existing group, the foundation uses `provisionJob=false`:

   ```powershell
   ./scripts/deploy_azure.ps1 -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup -Location $location -Stage Bootstrap -Online -Deploy
   ```

   Without `-Deploy`, the script only compiles/reviews. `-Deploy` requires `-Online` and repeats successful what-if before applying. It does not start a job, upload data or push an image. The current first deployment instead used the [new-group subscription workflow](../infra/subscription-readme.md). Do not rerun that workflow against a group that now exists; review group-scoped changes for repairs.

2. On a VNet-connected builder, obtain registry outputs and publish a reviewed container:

   This stage requires the private access path and an accepted image-release decision. The current local scan does not pass that decision. If rebuilding on the builder, scan and review the new image before pushing it; a previous local image scan does not cover a new build.

   ```powershell
   $registryName = az deployment group show --subscription $subscriptionId --resource-group $resourceGroup --name aicg-bootstrap --query properties.outputs.registryName.value --output tsv
   $registryLoginServer = az deployment group show --subscription $subscriptionId --resource-group $resourceGroup --name aicg-bootstrap --query properties.outputs.registryLoginServer.value --output tsv
   az acr login --subscription $subscriptionId --name $registryName
   docker build --platform linux/amd64 --tag "${registryLoginServer}/ai-command-gateway:pilot" .
   docker push "${registryLoginServer}/ai-command-gateway:pilot"
   $imageDigest = az acr repository show --subscription $subscriptionId --name $registryName --image ai-command-gateway:pilot --query digest --output tsv
   ```

   Validate that every command succeeded and that the digest matches the reviewed image. The builder needs registry push permission independently of the job's pull identity. This repository does not provision a builder or enable public ACR access to work around private connectivity. [Microsoft ACR image metadata reference](https://learn.microsoft.com/en-us/cli/azure/acr/repository?view=azure-cli-latest#az-acr-repository-show)

3. Review and then add the job using the immutable digest:

   ```powershell
   ./scripts/azure_preflight.ps1 -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup -Location $location -Stage Job -ImageDigest $imageDigest -Online
   ./scripts/deploy_azure.ps1 -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup -Location $location -Stage Job -ImageDigest $imageDigest -Online -Deploy
   ```

   The image reference is the deployed registry's `ai-command-gateway@sha256:...`. Mutable tags are not accepted by the Job stage. The job remains manual and defaults to the synthetic demo.

After inspecting the deployed job configuration, an authorized operator can start it:

```powershell
$jobName = az deployment group show --subscription $subscriptionId --resource-group $resourceGroup --name aicg-job --query properties.outputs.jobName.value --output tsv
az containerapp job start --subscription $subscriptionId --resource-group $resourceGroup --name $jobName
az containerapp job execution list --subscription $subscriptionId --resource-group $resourceGroup --name $jobName --output table
```

Treat job-start permission as privileged deployment authority: Azure permits a caller with `Microsoft.App/jobs/start/action` to override the execution template, potentially using the job's managed identity. A job operator is not merely an application command approver. Restrict and review that role separately. [Microsoft job permissions](https://learn.microsoft.com/en-us/azure/container-apps/jobs#permissions)

## Data and outputs

The default `demo` mode uses only bundled synthetic inputs. `dataset-analysis` requires the five original supplied files under their exact inventory filenames in the private `inputs` container. The runner verifies byte identities before analysis. No raw input upload is automated or performed by the deployment scripts. Review permission to transfer those files, then use a private-network upload path with Entra authentication; storage keys are disabled.

Select analysis deliberately with `-Stage Job -JobMode dataset-analysis -ImageDigest $imageDigest` during review/deployment. The runner performs profiling, qualification, catalog construction, advice regression and unqualified-policy replay. Output upload is restricted to declared aggregate artifacts and a run manifest; raw source rows, source prose, replay observation records and the replay database are excluded. Demo artifacts can include the synthetic audit backup. No output artifact establishes equipment policy or production safety.

| Runtime input | Meaning |
| --- | --- |
| `AI_GATEWAY_JOB_MODE` | `demo` by default, or explicit `dataset-analysis` |
| `AZURE_STORAGE_ACCOUNT_URL` | Storage account Blob endpoint supplied by the template |
| `AZURE_CLIENT_ID` | User-assigned managed identity client ID |
| `AZURE_INPUT_CONTAINER` / `AZURE_OUTPUT_CONTAINER` | `inputs` / `outputs` |
| `AI_GATEWAY_WORKSPACE` | Writable temporary root; container default `/tmp/ai-command-gateway` |

Each run uses a new identifier and output prefix. The template configures one worker per execution; separate manual starts can overlap. Unique prefixes isolate their artifacts, but there is no global lock or shared approval ledger. Inspect the manifest, job exit status and upload completion before treating artifacts as complete. Logs and artifacts have separate retention parameters; review them against the intended evidence-retention obligation. The workstation SQLite gateway ledger is not migrated into a multiuser Azure service.

## Verification still required in Azure

Check the deployed foundation's actual ARM configuration without accessing data-plane services:

```powershell
./scripts/verify_azure_foundation.ps1 -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup
```

The [foundation verifier](../scripts/verify_azure_foundation.ps1) makes read-only ARM requests and writes a fresh report under `outputs/azure-foundation-verification/`. The recorded run passed **21/21 checks through 20 ARM GET requests**: deployment state, private service settings, three exact scoped identity roles, three approved/succeeded private endpoints, six DNS zones and VNet links, AMPLS private-only access without exclusions, and no jobs. It requested no secrets and did not resolve private DNS or test image/Blob/log access. The [deployment record](azure-deployment-review.md) distinguishes this observed result from the remaining runtime checks.

Before calling the pilot operational, verify the actual image pull, private DNS/connectivity, managed-identity read/write scope, denied input writes, artifact upload, log access and deliberate failure behavior in the selected subscription. Review quota/region support, dependency and image scans, workload duration/memory, retention/recovery and cost using the deployed configuration. Azure Monitor private connectivity is a separate control from Blob/ACR networking. [Microsoft Monitor Private Link guidance](https://learn.microsoft.com/en-us/azure/azure-monitor/fundamentals/private-link-security)

Stopping or deleting resources is a separate operator action. The scripts do not automatically roll back partial deployments or delete resource groups. Preserve deployment operations and evidence on failure, correct the cause, then review a new what-if. Re-run Job stage with a previously reviewed image digest for an image rollback; deployment success still requires a separate execution check. No production availability, latency, operating-policy or customer acceptance claim follows from local compilation.

## Recorded implementation checks

The original [v0.4 verification snapshot](../governance/local-verification-v0.4.json) records 452 Python tests plus 44 subtests, 14 then-current deployment-script checks, the initial container smoke and static IaC validation. It remains historical evidence. Current [results](results.md) add 40/40 script checks, the live 39-create foundation preview, Bicep compilation and Checkov 19 passed / 0 failed / 4 scoped exceptions, final image findings and resource-bounded container verification.

The complete dataset runner passed 16 checks using local filesystem Blob simulation. Reproduce that simulation without Azure credentials or network access:

```powershell
.venv/Scripts/python.exe scripts/verify_azure_local.py --input-dir "C:/Users/moore/Downloads"
```

The verifier executes the actual dataset-analysis code, streams all five originals through a fake Blob service, independently checks artifact hashes and completion ordering, and blocks Azure SDK imports/socket operations. Its `azure_blob` result label refers to the exercised runner branch; the reported storage operations were local. It does not prove live Azure behavior. [ARCH-004](architecture/README.md#azure-batch-foundation) documents the intended service relationships.

Use `./scripts/test_azure_container.ps1 -InputDir 'C:/Users/moore/Downloads' -Image <reviewed-local-image-id>` for the bounded Linux-container variant. Follow the [runtime evidence procedure](azure-runtime-checks.md) for the exact image and recorded limits. Control-plane deployment verification and data-plane execution remain distinct evidence.
