# Azure infrastructure implementation

This resource-group-scoped Bicep implementation packages the existing batch CLI as a **manual Azure Container Apps Job**. The separately approved nonproduction pilot in `rg-ai-command-gateway-dev`, East US 2, subscription ending `f609`, has published the reviewed image, uploaded and fully read back all five inputs, and completed demo, dataset, identity and expected-failure checks. The retained job is configured for `dataset-analysis`; temporary operator cleanup and retained-configuration checks are complete. The [infrastructure plan](../.azure/infrastructure-plan.json), [workload insights](../.azure/insights.json), [static-check dispositions](security-exceptions.md) and [current results](../docs/results.md) preserve scope and evidence. The original Network Watcher in another group was retained.

Use the [Azure implementation guide](../docs/azure-implementation.md) for the staged operator workflow and scripts. The [example parameters](main.parameters.example.json) default to foundation-only provisioning; they contain no subscription, location choice, image or credential.

## Resources and data paths

| Component | Implemented choice |
|---|---|
| Runtime | Internal workload-profile environment, public access disabled, Consumption profile. Retained manual job uses 1 CPU / 2 GiB, 1 replica per execution, 1,800-second timeout and zero automatic replica retries. |
| Input/output | Private `Standard_ZRS` Blob account; `inputs` is read-only to the job and `outputs` grants Blob Data Contributor. HTTPS/TLS 1.2, anonymous/shared-key/local-user access disabled. |
| Image registry | Private Premium ACR, no admin/anonymous access or trusted-service/task bypass. Explicit registry RBAC mode supports `AcrPull`; immutable image digest required when the job is enabled. |
| Network | New VNet, dedicated delegated `/23` environment subnet, separate `/24` endpoint subnet, NSGs, Blob/ACR/Monitor private endpoints and private DNS links. |
| Identity | One user-assigned managed identity; container-scoped input/output data roles and registry-scoped `AcrPull`. No application secrets or Key Vault needed. |
| Monitoring | Log Analytics local auth and public ingestion/query disabled. AMPLS enables private queries. Environment, Blob and registry diagnostic settings use Azure Monitor. |
| Retention | Derived output lifecycle defaults to 30 days, configurable 7-90; versions/snapshots expire with the same policy. Seven-day soft-delete recovery applies after asynchronous deletion. Inputs are excluded. Logs default to 30 days, separately configurable 30-90. |

The job has no HTTP server or equipment adapter. No ingress private endpoint is necessary for a job without an ingress application. Network security groups retain Azure's default VNet/platform connectivity and outbound behavior; this template is **not an egress firewall**. Platform infrastructure can use outbound public endpoints. Cloud resource identity does not turn local mock approval labels into authenticated human approvals.

Manual `parallelism: 1` limits replicas **within an execution**. Multiple manual starts can overlap; there is no global job lock. The runner generates separate UUID output prefixes. The current Wolfi/Python 3.13 [local bounded container run](../docs/azure-runtime-checks.md) completed all 16 checks in 95.08 seconds at 1 CPU / 2 GiB, with peak cgroup memory 945,270,784 bytes. ARM records a 54-second dataset execution interval for the one live pilot run; this is not a latency/throughput guarantee or a controlled comparison to local duration. Cloud peak memory and production capacity remain unmeasured.

The environment uses `appLogsConfiguration.destination: azure-monitor`, followed by diagnostic settings. It never supplies a workspace shared key. Microsoft documents that diagnostic settings use a private service channel that is independent of workspace public-ingestion filtering. AMPLS and its five DNS zones provide private client query access; one Blob private DNS zone is shared with the workload Blob endpoint. [Container Apps logging](https://learn.microsoft.com/azure/container-apps/log-options), [Azure Monitor private-link behavior](https://learn.microsoft.com/azure/azure-monitor/fundamentals/private-link-design), [Monitor DNS zones](https://learn.microsoft.com/azure/azure-monitor/fundamentals/private-link-configure).

The runner emits bounded status/error metadata rather than raw dataset contents. Platform diagnostics can include resource names, object paths and access metadata. Restrict log-reader access accordingly. The workspace daily ingestion quota is 1 GB; it can interrupt logging and is not a guaranteed monetary cap.

## Staged deployment

1. **Bootstrap:** `provisionJob=false` creates private infrastructure and scoped roles without a job or placeholder image.
2. **Publish and verify:** the approved temporary operator transfers and publishes the already reviewed OCI layout without rebuilding, then uploads the five pinned inputs using create-only writes and full readback hash checks. The registry digest is `sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad`. A new build requires separate image review. Ordinary external hosted build agents and laptops without private connectivity cannot reach these data-plane endpoints.
3. **Job:** use `-Stage Job -ImageDigest sha256:<64 lowercase hexadecimal characters> -JobMode dataset-analysis`. The scripts compile [job-only.bicep](job-only.bicep), which references the existing foundation and deploys only the manual job. Its four parameters are `location`, `workloadName`, `imageDigest` and `jobMode`. The image repository is fixed to `ai-command-gateway`; starting an execution is a separate operator action.

The [deployment scripts](../scripts/deploy_azure.ps1) compile locally by default. `-Online` enables read-only target checks and what-if; `-Online -Deploy` is the explicit apply path after review. Job stage refuses foundation Create/Modify changes even with `-AllowModify`. The corrected job-only preview showed one create and 33 ignores; an earlier full-foundation preview with unwanted peering changes was not applied. These scripts do not create the resource group, publish images, upload datasets or start jobs. The separate [subscription wrapper](subscription-readme.md) created the initial foundation with its job fixed off; do not rerun it against the existing group. Use incremental deployment only and review existing target resources before repairs.

Subnet parameters support reviewed alternatives to the default CIDRs. Script checks require canonical IPv4 network prefixes, containment and non-overlap; the environment and endpoint subnets must each be `/27` or larger. Check reserved ranges and overlaps with connected networks separately. Role-assignment names use the stable managed-identity resource ID; assignment properties use its current principal ID. Recreating the identity requires deliberate role-assignment lifecycle review.

No `az acr build` or implicit ACR task is included. A private registry needs a network-connected publisher; simply enabling public access to make a build work would change the reviewed architecture. [Microsoft private-registry limitations](https://learn.microsoft.com/azure/container-registry/container-registry-private-endpoints).

Runtime environment variables supplied by [job.bicep](modules/job.bicep) are `AZURE_CLIENT_ID`, `AZURE_STORAGE_ACCOUNT_URL`, `AZURE_INPUT_CONTAINER`, `AZURE_OUTPUT_CONTAINER`, `AI_GATEWAY_JOB_MODE`, and `AI_GATEWAY_WORKSPACE`. No OpenAI key, model invocation, Azure CLI credential chain or generic command override is configured.

## Local verification

Run from the repository root with installed Bicep and Checkov:

```powershell
bicep build infra/main.bicep --outfile outputs/azure/main.json
bicep build infra/job-only.bicep --outfile outputs/azure/job-only.json
checkov -d infra/ --framework bicep --skip-download --quiet
```

The workspace's isolated tools are Bicep **0.48.1** and Checkov **3.3.29**. `--skip-download` keeps Checkov's remote guideline fetch disabled; no external scanner upload is requested. The compiled ARM output is a local artifact. The scanner's coverage and documented suppressions do not establish security acceptance or deployment success.

The original v0.4 command output remains [historical validation evidence](validation.md). Current Bicep compilation and all 46 deployment-script contracts passed; those contracts use a simulated Azure CLI. Whole-infrastructure Checkov reports **39 passed, zero failed, four scoped skips and one parser error** in `operator-foundation-links.bicep`. Focused job scans have zero applicable checks. The [operator plan](../docs/azure-private-access-plan.md) identifies the parser limitation and raw reports; process exit zero is not evidence of complete scan coverage. Separate actual records establish private DNS, image pull, input transfer/readback, private logs, completed artifact checks, nine identity-probe checks and an expected configuration failure.

## Retained configuration after cleanup

The temporary operator group and its 11 enumerated foundation children are removed. All 31 retained-configuration checks passed. To recheck, use the read-only [pilot verifier](../scripts/verify_azure_pilot.ps1) **without `-OperatorPresent`**:

```powershell
./scripts/verify_azure_pilot.ps1 -SubscriptionId b31e9bd1-6179-4504-819b-f212ed36f609 -ResourceGroup rg-ai-command-gateway-dev -ExpectedImageDigest sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad -ExpectedJobMode dataset-analysis
```

This checks ARM configuration and temporary-resource absence, not a new data-plane run. Add `-OperatorPresent` only when temporary resources intentionally remain. The retained foundation, image, five inputs, manual job and run evidence are outside temporary cleanup scope. Removing the operator removes the temporary workstation path to the private endpoints; any future data-plane access needs another reviewed private path.

### Historical foundation-only milestone

The initial foundation approval excluded image publication, uploads and execution. Deployment succeeded with the job disabled; the preview showed 39 creates and all 21 read-only checks passed through 20 ARM requests. Those results remain in the [foundation review](../docs/azure-deployment-review.md). The later explicit pilot approval extended scope. The original foundation verifier expects no job and is unsuitable for the current retained pilot.

## Decisions and remaining inputs

Container Apps avoids operating a cluster for one batch process. Private registry/data endpoints, managed identity, recovery and logs apply the relevant [Container Apps](https://learn.microsoft.com/azure/well-architected/service-guides/azure-container-apps) and [Blob Storage](https://learn.microsoft.com/azure/well-architected/service-guides/azure-blob-storage) architecture guidance. No Key Vault is created because this runtime requires no application secret; no Application Insights resource is needed for the current status-only CLI. Automatic quarantine, image signature enforcement, customer-managed encryption keys, cross-region recovery and outbound inspection are future decisions.

The approved subscription/resource group/region and original cost scope are recorded in the [deployment review](../docs/azure-deployment-review.md); the [operator plan](../docs/azure-private-access-plan.md) records the later private-access and workload approval. Private publisher connectivity and DNS integration were verified for this temporary path. The template defaults location to the target group's region; it does not infer a region from the client's timezone. Azure public cloud is the supported runner target. A new target still requires region/quota/provider checks and role-assignment rights.

Premium ACR, three private endpoints, private DNS, ZRS storage and monitoring incur charges when jobs are idle. The approved [regional estimate](../docs/azure-cost-estimate.md) is $97.49/month in standing core charges plus usage. The separately approved temporary operator adds about $0.38759/hour while present; cleanup is complete. Actual billed cost and savings are unmeasured. The pilot does not establish high availability, recovery targets, domain correctness or production acceptance.

Every generated resource name uses fixed service-compatible prefixes and a deterministic `uniqueString` suffix, or a fixed service-specific child/DNS name. Workload name is a hash seed, not raw name text. Naming constraints and schema references are recorded per resource in the plan; global name availability still requires the real target.
