# Azure infrastructure implementation

This resource-group-scoped Bicep implementation packages the existing batch CLI as a **manual Azure Container Apps Job**. It is a nonproduction implementation, with an [infrastructure plan](../.azure/infrastructure-plan.json), [referenced workload insights](../.azure/insights.json), and [four scoped static-check dispositions](security-exceptions.md). The user approved private foundation deployment to the new `rg-ai-command-gateway-dev` group in East US 2, subscription ending `f609`; deployment succeeded with the job disabled. The original Network Watcher in another group was retained. The [deployment review](../docs/azure-deployment-review.md) records scope, approval and actual outcome.

Use the [Azure implementation guide](../docs/azure-implementation.md) for the staged operator workflow and scripts. The [example parameters](main.parameters.example.json) default to foundation-only provisioning; they contain no subscription, location choice, image or credential.

## Resources and data paths

| Component | Implemented choice |
|---|---|
| Runtime | Internal workload-profile environment, public access disabled, Consumption profile. Optional manual job uses 1 CPU / 2 GiB, 1 replica per execution, 1,800-second timeout and zero automatic replica retries. |
| Input/output | Private `Standard_ZRS` Blob account; `inputs` is read-only to the job and `outputs` grants Blob Data Contributor. HTTPS/TLS 1.2, anonymous/shared-key/local-user access disabled. |
| Image registry | Private Premium ACR, no admin/anonymous access or trusted-service/task bypass. Explicit registry RBAC mode supports `AcrPull`; immutable image digest required when the job is enabled. |
| Network | New VNet, dedicated delegated `/23` environment subnet, separate `/24` endpoint subnet, NSGs, Blob/ACR/Monitor private endpoints and private DNS links. |
| Identity | One user-assigned managed identity; container-scoped input/output data roles and registry-scoped `AcrPull`. No application secrets or Key Vault needed. |
| Monitoring | Log Analytics local auth and public ingestion/query disabled. AMPLS enables private queries. Environment, Blob and registry diagnostic settings use Azure Monitor. |
| Retention | Derived output lifecycle defaults to 30 days, configurable 7-90; versions/snapshots expire with the same policy. Seven-day soft-delete recovery applies after asynchronous deletion. Inputs are excluded. Logs default to 30 days, separately configurable 30-90. |

The job has no HTTP server or equipment adapter. No ingress private endpoint is necessary for a job without an ingress application. Network security groups retain Azure's default VNet/platform connectivity and outbound behavior; this template is **not an egress firewall**. Platform infrastructure can use outbound public endpoints. Cloud resource identity does not turn local mock approval labels into authenticated human approvals.

Manual `parallelism: 1` limits replicas **within an execution**. Multiple manual starts can overlap; there is no global job lock. The runner generates separate UUID output prefixes. The [local bounded container run](../docs/azure-runtime-checks.md) completed all 16 checks on the five datasets in 81.363 seconds at 1 CPU / 2 GiB with peak cgroup memory 1,006,088,192 bytes. Azure duration, throughput and memory use remain unmeasured.

The environment uses `appLogsConfiguration.destination: azure-monitor`, followed by diagnostic settings. It never supplies a workspace shared key. Microsoft documents that diagnostic settings use a private service channel that is independent of workspace public-ingestion filtering. AMPLS and its five DNS zones provide private client query access; one Blob private DNS zone is shared with the workload Blob endpoint. [Container Apps logging](https://learn.microsoft.com/azure/container-apps/log-options), [Azure Monitor private-link behavior](https://learn.microsoft.com/azure/azure-monitor/fundamentals/private-link-design), [Monitor DNS zones](https://learn.microsoft.com/azure/azure-monitor/fundamentals/private-link-configure).

The runner emits bounded status/error metadata rather than raw dataset contents. Platform diagnostics can include resource names, object paths and access metadata. Restrict log-reader access accordingly. The workspace daily ingestion quota is 1 GB; it can interrupt logging and is not a guaranteed monetary cap.

## Two deployment stages

1. **Bootstrap:** `provisionJob=false` creates private infrastructure and scoped roles without a job or placeholder image.
2. **Publish and verify:** a VNet-connected build/operator machine builds, scans and pushes the exact image into the private registry. Review the digest and its scan evidence. Upload the five original input files, under their pinned names, only when choosing `dataset-analysis` mode. Ordinary external hosted build agents and local laptops without VNet connectivity cannot reach these private endpoints.
3. **Job:** set `provisionJob=true`, `imageDigest=sha256:<64 lowercase hexadecimal characters>` and the intended `jobMode`. The image repository is fixed to `ai-command-gateway` in the generated registry. Deployment creates the job; starting an execution is a separate operator action.

The [deployment scripts](../scripts/deploy_azure.ps1) compile locally by default. `-Online` enables read-only target checks and what-if; `-Online -Deploy` is the explicit apply path after reviewing its result and cost. These group scripts do not create the resource group, publish images, upload datasets or start jobs. The separate [subscription wrapper](subscription-readme.md) creates a reviewed new group and the foundation with the job fixed off; it was used for the approved deployment. Do not use that new-group workflow to modify an existing group. Use incremental deployment only. Inventory and reconcile any existing target resources; this template must not replace an existing enterprise VNet, DNS zone or monitoring scope.

Subnet parameters support reviewed alternatives to the default CIDRs. Script checks require canonical IPv4 network prefixes, containment and non-overlap; the environment and endpoint subnets must each be `/27` or larger. Check reserved ranges and overlaps with connected networks separately. Role-assignment names use the stable managed-identity resource ID; assignment properties use its current principal ID. Recreating the identity requires deliberate role-assignment lifecycle review.

No `az acr build` or implicit ACR task is included. A private registry needs a network-connected publisher; simply enabling public access to make a build work would change the reviewed architecture. [Microsoft private-registry limitations](https://learn.microsoft.com/azure/container-registry/container-registry-private-endpoints).

Runtime environment variables supplied by [job.bicep](modules/job.bicep) are `AZURE_CLIENT_ID`, `AZURE_STORAGE_ACCOUNT_URL`, `AZURE_INPUT_CONTAINER`, `AZURE_OUTPUT_CONTAINER`, `AI_GATEWAY_JOB_MODE`, and `AI_GATEWAY_WORKSPACE`. No OpenAI key, model invocation, Azure CLI credential chain or generic command override is configured.

## Local verification

Run from the repository root with installed Bicep and Checkov:

```powershell
bicep build infra/main.bicep --outfile outputs/azure/main.json
checkov -d infra/ --framework bicep --skip-download --quiet
```

The workspace's isolated tools are Bicep **0.48.1** and Checkov **3.3.29**. `--skip-download` keeps Checkov's remote guideline fetch disabled; no external scanner upload is requested. The compiled ARM output is a local artifact. The scanner's coverage and documented suppressions do not establish security acceptance or deployment success.

The original v0.4 command output and exit status remain in [historical validation evidence](validation.md). Current checks passed Bicep compilation, Checkov 19 passed / 0 failed / 4 exceptions and 40/40 script contracts. The live subscription preview produced 39 creates and no modifications, deletions or unsupported changes. Foundation deployment succeeded and 21/21 read-only control-plane checks passed through 20 ARM requests; [current results](../docs/results.md) record the evidence separately. Data-plane role propagation, DNS resolution, image pulls, source transfer, log access and job execution still require live verification. Checkov and ARM configuration checks do not replace those tests.

## Decisions and remaining inputs

Container Apps avoids operating a cluster for one batch process. Private registry/data endpoints, managed identity, recovery and logs apply the relevant [Container Apps](https://learn.microsoft.com/azure/well-architected/service-guides/azure-container-apps) and [Blob Storage](https://learn.microsoft.com/azure/well-architected/service-guides/azure-blob-storage) architecture guidance. No Key Vault is created because this runtime requires no application secret; no Application Insights resource is needed for the current status-only CLI. Automatic quarantine, image signature enforcement, customer-managed encryption keys, cross-region recovery and outbound inspection are future decisions.

The approved subscription/resource group/region and cost scope are recorded in the [deployment review](../docs/azure-deployment-review.md). Private publisher connectivity and DNS integration remain unresolved. The template defaults location to the target group's region; it does not assume the client's timezone identifies an Azure region. Azure public cloud is the supported runner target. Any new target still requires region/quota/provider checks and role-assignment rights in addition to resource creation rights.

Premium ACR, three private endpoints, private DNS, ZRS storage and monitoring have cost implications, including charges when jobs are idle. The approved [regional estimate](../docs/azure-cost-estimate.md) totals $97.49/month in standing core charges, plus usage and an unpriced private builder/access path. Actual billed cost and savings are unmeasured. Image publication, dataset upload and job execution are outside the foundation approval. This is not a high-availability or production release.

Every generated resource name uses fixed service-compatible prefixes and a deterministic `uniqueString` suffix, or a fixed service-specific child/DNS name. Workload name is a hash seed, not raw name text. Naming constraints and schema references are recorded per resource in the plan; global name availability still requires the real target.
