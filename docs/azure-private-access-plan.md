# Temporary private publisher and operator

Azure retirement verified at `2026-10-16T05:13:03.027368+00:00`: subscription ending `f609` remains Enabled, with zero active resource groups and zero active resources. The user explicitly requested "keep the subscription and delete other resources in azure." The foundation, managed Container Apps network group and original Network Watcher are removed, including the Azure image, dataset and result copies. Local originals, downloaded evidence, image archive, source code and GitHub repository remain. [Retirement evidence](../governance/azure-retirement-v0.4.json) supersedes the retained-resource statements below. The prior pilot remains historical evidence; redeployment requires a new scope and spending decision. Accrued charges may arrive later, and provider recovery retention is distinct from active resource existence.

## Historical completed pilot and scoped cleanup

The user approved deployment, testing and scoped cleanup with the reviewed costs and risks. The repaired operator deployment succeeded at 2026-10-16T03:03:37.926917+00:00. It published the exact reviewed OCI manifest, uploaded all five originals with full hash readbacks, and enabled the completed demo, dataset, identity and deliberate-failure tests. [Results](results.md) and [the pilot record](../governance/azure-pilot-v0.4.json) bind the observed outcomes to their evidence.

The temporary operator group and all eleven foundation additions were removed. All 31 post-cleanup configuration checks passed; explicit child and temporary-role absence was verified. Cleanup completed at `2026-10-16T04:01:02.3014045Z`. Before cleanup, all 31 operator-present checks passed through 25 GET requests. The local Bastion tunnel was stopped when evidence transfers were finished; the generated private SSH key was removed after resource-group absence was confirmed. The final verifier retried one recognized transient GET failure; it did not retry any job start or change resources.

The retained foundation, reviewed image, five inputs, manual dataset-analysis job and outputs remain in Azure. The temporary workstation private-data access path is gone; future private queries/transfers need an authorized access path again. Core standing and variable usage charges continue. Actual billed operator cost has not been measured; the four-hour estimate and $5 proposed allowance below were never an automatic cap.

## Original review baseline

Prepared 2026-10-15. This adds a short-lived operator path to the existing private foundation in `rg-ai-command-gateway-dev`, East US 2, subscription ending `f609`. The local preparation and Azure preview do not create the operator resources or transfer any dataset. Deployment and cleanup require the concrete approval recorded for this follow-on work.

## Proposed topology

Use a separate **`rg-ai-command-gateway-operator`** containing a private Ubuntu VM and Azure Bastion Standard. Bastion provides the authenticated native SSH tunnel from this Windows workstation; SCP carries the reviewed image archive, verified tools and exactly five original dataset files. Registry, Blob and Monitor connections from the VM use the existing private endpoints. There is no public staging bucket, external relay or public IP on the VM. The Bastion management service itself has a Standard public IP and HTTPS endpoint. [Microsoft native file-transfer procedure](https://learn.microsoft.com/en-us/azure/bastion/vm-upload-download-native)

| Decision | Concrete setting |
| --- | --- |
| Operator VNet | `vnet-aicg-operator`, `10.43.0.0/24` |
| VM subnet | `snet-operator`, `10.43.0.0/26`, default outbound access disabled |
| Bastion subnet | `AzureBastionSubnet`, `10.43.0.64/26` |
| Foundation integration | Two reciprocal VNet peerings; six additional links to the existing private DNS zones |
| VM | `vm-aicg-operator`, regional `Standard_D2ls_v6`, 2 vCPUs / 4 GiB |
| OS | Canonical Ubuntu 24.04, exact image `24.04.202609040`, x64 / Generation 2 |
| Disk | 32 GiB Standard SSD LRS, encrypted managed disk; delete with VM |
| VM security | Trusted Launch, Secure Boot, vTPM, encryption at host, SSH key only, extension operations disabled |
| Bastion | Standard, two scale units, native tunneling and file transfer enabled; shareable links and IP-based target connections disabled |
| VM network | SSH only from the Bastion subnet; outbound HTTPS only to foundation private endpoint subnet `10.42.2.0/24`, plus platform DNS, IMDS and VM-agent traffic |
| Identity | Separate `id-aicg-operator`; never attach or broaden the job identity |
| Provisioning entry point | [operator-subscription.bicep](../infra/operator-subscription.bicep), with [operator.bicep](../infra/operator.bicep) and [operator-foundation-links.bicep](../infra/operator-foundation-links.bicep) |

The VM performs transfer and verification, rather than rebuilding the application. Tools arrive through SCP; managed-identity tokens come from the local Azure Instance Metadata Service. This avoids VM internet egress, package installation during the session, a NAT gateway and a standing VPN. Archive hashes must match on both ends. A publication digest is accepted only after the registry manifest/configuration/layers are tied to the reviewed artifact; a tag or an archive hash alone is insufficient.

The separate VNet avoids changing the foundation's two inline subnet declarations. Existing foundation resources are referenced with Bicep `existing`; only new child peerings, DNS links and role assignments are added. A Job-stage preview must still show no removal or unintended change to those additions before applying. VNet peering carries private traffic on Microsoft's backbone. [Peering overview](https://learn.microsoft.com/en-us/azure/virtual-network/virtual-network-peering-overview)

The eight required Bastion platform NSG rules follow Microsoft's service requirements. The VM has its own stricter NSG. Bastion availability and provisioning duration are separate from VM quota and can still fail during apply. [Bastion NSG requirements](https://learn.microsoft.com/en-us/azure/bastion/bastion-nsg)

## Access scope

The temporary identity receives only these new assignments:

| Role | Existing resource scope | Purpose |
| --- | --- | --- |
| AcrPush | `craicgsn5edmznrgh7s` | Publish and read the reviewed application image |
| Storage Blob Data Contributor | `staicgsn5edmznrgh7s/default/inputs` | Upload and verify the five authorized inputs |
| Storage Blob Data Reader | `staicgsn5edmznrgh7s/default/outputs` | Read completed run artifacts and validate hashes |
| Log Analytics Reader | `log-aicg-sn5edmznrgh7s` | Query execution logs through private Monitor access |

Input Contributor includes delete/write capabilities, so upload commands must use create-only semantics and verify existing object content before any replacement is considered. The operator identity receives no job-start or resource-deployment rights. The signed-in human's existing ARM authority performs reviewed job deployment/start. The job identity retains its exact original three assignments.

The generated SSH key lives under ignored `.cache/azure-operator/`; the private key must not be committed, uploaded to a storage service, or printed. The parameter file contains only the public key. Verify the SSH host key through trusted boot-diagnostic/control-plane evidence before accepting the session; preserve a task-specific known-hosts file. Bastion authenticates Azure access; SSH separately authenticates the VM account.

## Availability and cost evidence

Authenticated, read-only checks found 0/10 regional vCPU usage and 0/10 Dlsv6-family usage. `Standard_D2ls_v6` has no location restriction in East US 2; its zone restrictions mean this plan deliberately uses a **regional** VM. The image is active and supports Trusted Launch; `EncryptionAtHost` is already registered. This verifies current eligibility, not reserved capacity. The cheaper original B-series sizes are location-restricted, and Bsv2-family quota is zero, so no quota increase or region change is assumed. The selected size has 2 vCPUs and 4 GiB. [Microsoft Dlsv6 specification](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/dlsv6-series)

Live Microsoft Retail Prices API responses are retained under ignored `outputs/azure-private-access-review/prices.json` and `additional-prices.json`. USD pay-as-you-go rates in East US 2:

| Incremental resource | Rate | Four-hour illustration |
| --- | ---: | ---: |
| Bastion Standard, base two scale units | $0.2900/hour | $1.1600 |
| Linux Standard_D2ls_v6 | $0.0893/hour | $0.3572 |
| Standard IPv4 public IP for Bastion | $0.0050/hour | $0.0200 |
| 32 GiB E4 Standard SSD LRS | $2.40/month; $0.00329/hour at 730 hours | $0.0132 |
| **Standing subtotal while present** | **$0.38759/hour** | **$1.5504** |

This excludes disk transactions ($0.002 per 10,000 operations), VNet peering traffic, Bastion outbound transfer, ordinary Blob/private-endpoint transactions and job/log usage. It is an estimate, not a spending limit. A **$5 incremental session allowance** covers the four-hour illustration plus contingency, but continued provisioning or failed cleanup can exceed it. If retained for 730 hours, these operator resources alone would cost approximately **$282.94/month**, in addition to the existing foundation. Deallocating the VM does not stop Bastion, disk or public-IP charges. [Retail API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices), [Bastion billing](https://azure.microsoft.com/en-us/pricing/details/azure-bastion/)

No new DNS zones or private endpoints are created. The six links reuse already-billed zones. No premium Bastion, NAT gateway, VPN, Defender plan or always-running agent pool is included. Bastion Developer is free but lacks native client/file-transfer support; Basic also lacks the required native tunnel. A public-SSH VM could cost less but adds an internet-facing workload management surface. ACR dedicated agent pools do not provide the full original-dataset upload, artifact-read and Monitor-query path. [Bastion SKU comparison](https://learn.microsoft.com/en-us/azure/bastion/bastion-sku-comparison)

## Review, execution and cleanup

Compile and preview use the ignored parameter file generated from the reviewed key and selected VM size:

```powershell
.cache/azure-cli/bin/bicep.exe build infra/operator-subscription.bicep --outfile outputs/azure-private-access-review/operator.json
az deployment sub what-if --subscription b31e9bd1-6179-4504-819b-f212ed36f609 --location eastus2 --name aicg-operator-review --template-file outputs/azure-private-access-review/operator.json --parameters '@outputs/azure-private-access-review/operator.parameters.json' --validation-level Provider --no-pretty-print --output json
```

The new-group wrapper must not be applied if the operator group already exists unexpectedly. Review the exact compiled hash, current what-if and resource list before applying. A failed deployment may leave billable partial resources. The local Bicep compiler completed with zero warnings/errors; Checkov 3.3.29 on the operator template reports **19 passed, 0 failed, 0 skipped, 0 parsing errors**. The real Provider-level Azure preview succeeded with **21 Create, 28 Ignore, 0 Modify, 0 Delete and 0 Unsupported**. Eleven creates are the intended foundation children; the other ten are in the new operator group, including the group itself. The VM also creates its managed OS disk. The compiled template SHA-256 is `5c9d01469d5d292439efe3b74657ffc9000c2941e6337b3ac63120b0b6a3ea85`. These checks do not attest to VM or application vulnerability freedom. Full preview evidence is retained in the ignored review directory.

After approved apply, establish the native tunnel and use OpenSSH SCP:

```powershell
az network bastion tunnel --subscription b31e9bd1-6179-4504-819b-f212ed36f609 --resource-group rg-ai-command-gateway-operator --name bas-aicg-operator --target-resource-id /subscriptions/b31e9bd1-6179-4504-819b-f212ed36f609/resourceGroups/rg-ai-command-gateway-operator/providers/Microsoft.Compute/virtualMachines/vm-aicg-operator --resource-port 22 --port 50022
```

The tunnel is a long-running local process. Keep it in a hidden process with task-specific logs, then use port 50022 with a pinned known-hosts file and `.cache/azure-operator/id_rsa`. Transfer only explicitly enumerated artifacts. Before publishing/uploading, check private DNS answers and HTTPS connectivity for ACR, Blob and the Log Analytics endpoint from the VM. Preserve evidence for managed identity, read/write scope, expected denied input write by the job, successful demo/dataset runs, completion artifacts and a deliberate failure.

Cleanup scope is **only** the temporary operator group and its **11 enumerated children in the foundation group**: four role assignments, six `link-aicg-operator` DNS links and `to-aicg-operator` VNet peering. Validate each child's current identity or VNet target before deletion. Then delete `rg-ai-command-gateway-operator`, which removes VM, disk, NIC, identity, Bastion, public IP, NSGs, operator VNet and its reverse peering. Do not delete the foundation group, foundation services, the retained reviewed registry image, input datasets, job or execution evidence. Keep the deployment/cleanup audit records and remove the local private key only after the temporary access path is confirmed removed.

The project-specific [cleanup helper](../scripts/remove_azure_operator.ps1) defaults to a read-only check. Its `-Delete` switch is for the explicitly approved cleanup: it verifies group tags, refuses unexpected group resources, and checks all 11 child targets against the temporary identity/VNet before deleting anything. It preserves partial-deletion evidence and leaves the group if a child deletion fails; a partial cleanup needs a reviewed repair. It does not delete the SSH key. All 18 mocked cleanup behavior tests pass, including unexpected resources, identity/scope mismatches, partial deletion, empty inventory and an unrelated resource appearing before final group deletion. The tests do not call Azure. The cleanup script SHA-256 is `a236246f7f911be6b31af2671007e81212b7abff1fd08830a881e2a24a34d95f`. The machine-readable [operator plan](../.azure/operator-plan.json) preserves the original preview alongside the later approval, execution and cleanup status.

Removing the disposable VM disk also removes its temporary copies of the original datasets and transfer tools. Cleanup is part of the proposed approval, not an unannounced deletion of existing resources. Verify that the operator group, all 11 foundation child IDs and the temporary identity's assignments are gone, then recheck the retained foundation and job configuration. Preserve evidence if cleanup fails and report which resources can continue to incur charges.

## Approved execution and repair

The user explicitly approved deployment, testing and scoped cleanup with the reviewed costs and risks. The original `aicg-operator` apply failed with `SecurityRuleInvalidAccessType` after creating the temporary group, identity, Bastion NSG and public IP. Azure platform DNS/IMDS service tags accept Deny overrides only; the preflight did not detect this provider constraint. The repair removes the two invalid Allow rules and retains the normal platform exceptions plus private-endpoint-only HTTPS egress. [Microsoft NSG platform exceptions](https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview).

The repaired template compiled with zero diagnostics and passed Checkov 19/0/0. Its SHA-256 is `b949b49ca5671773c4b6a83bb1f0ec8e978d496e5d6ba8ff411c099bd0dbb3d8`. The repair preview shows 17 remaining creates, 28 ignores, 2 unchanged and 2 default-property differences confined to the newly created operator identity/public IP; no foundation modifications or deletions. The original preview and failed-operation evidence are preserved. The observed repair and cleanup outcomes are recorded in the completed-pilot section above; original failed-operation evidence remains preserved.

## Current static-check scope and isolated job deployment

The subsequent full `infra/` scan with Checkov 3.3.29 reports **39 passed, 0 failed, 4 skipped and 1 parsing error**. The earlier 19-check operator-template results above do not cover every file in the operator deployment. Checkov's `pycep-parser` 0.5.1 / Lark 1.3.1 rejects the inline array argument to `concat()` in [operator-foundation-links.bicep](../infra/operator-foundation-links.bicep), line 84, column 3: `[peering.id, acrPush.id, inputWriter.id, outputReader.id, logReader.id]`. Its exception is `UnexpectedToken`, token `LSQB`; it skips the entire file, including its peerings, DNS links and role assignments. The parser also rejects the newline before the closing parenthesis after moving that array to a variable in an in-memory diagnostic. Using a separate variable and a single-line `concat()` parses in that diagnostic; the deployed source was not changed and no suppression was added. Bicep compilation and Azure deployment validation use the actual source and are separate evidence from this third-party parser limitation.

Raw scan and diagnostic evidence is retained in ignored `outputs/azure-job-only-validation/checkov-full.json`, `checkov-operator-parser.log` and `parser-diagnostic.json`. Checkov returns exit code zero for this scan despite the parsing error, so its process status is not evidence of complete scan coverage. Actual role-assignment scopes, DNS links, private resolution, managed-identity behavior and deployment state must be established by their separate control-plane and runtime records; the static scan does not attest to those controls.

The original Job-stage preview against `main.bicep` proposed foundation modifications, including removal of the operator VNet peering, and was not applied. The [job-only wrapper](../infra/job-only.bicep) now references the existing identity, environment, registry and storage account and deploys only the unchanged job module. Job-stage preflight accepts only `location`, `workloadName`, `imageDigest` and `jobMode` as template parameters. It blocks proposed Create or Modify changes outside the manual job even when `-AllowModify` is supplied; Bootstrap still uses the original foundation template. The real Provider-level preview for this wrapper succeeded with **1 Create, 33 Ignore, 0 Modify and 0 Delete**, retained at ignored `outputs/azure/job.what-if.json`. A preview confirms proposed scope, not successful deployment or job execution.

Local Bicep compilation completed without warnings or errors. All **46** PowerShell contract checks passed with real local compilation and a simulated Azure CLI; these tests make no Azure calls. Checkov parses both the wrapper and the unchanged job module without errors, but focused scans report **zero applicable checks and zero counted resources**; these are not security-check passes for the Container Apps job. Direct parser diagnostics identify the four existing-resource references and one module in the wrapper, and the job resource in the module. Focused reports are retained as `checkov-job-only.json` and `checkov-job-module.json` in the same ignored validation directory; the contract-test record is `outputs/azure-script-verification/summary.json`.
