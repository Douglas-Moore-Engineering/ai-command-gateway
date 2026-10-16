# Azure foundation deployment review

Prepared 2026-10-15 for the connected **douglas@dmesystems.global** account. The account maps to the current default subscription ending **f609**, in the `douglasdmesystems.onmicrosoft.com` tenant. The user identified this Douglas DME Systems account. Full identifiers and raw read-only results remain under ignored `outputs/azure-discovery/`.

## Approved action and outcome

**Successfully created rg-ai-command-gateway-dev in East US 2** and deployed the private foundation described by [subscription.bicep](../infra/subscription.bicep). Azure reports the subscription and nested foundation deployments as `Succeeded`. The existing `NetworkWatcherRG` and its Network Watcher are outside this deployment.

The foundation contains a VNet, managed identity, private Premium ACR, ZRS Blob storage, private endpoints/DNS and private Monitor/Log Analytics configuration. **The job is disabled in this deployment.** Image publication, source-data uploads, model calls and equipment connections were excluded from this approved action and were not performed. Foundation provisioning does not establish a working cloud workload.

Current retail rates give approximately **$97.49/month of persistent core infrastructure**, or **$101.95/month for the illustrative base workload**, before allowances, tax and the unpriced private builder/access path. The [cost estimate](azure-cost-estimate.md) gives low/base/high assumptions and exclusions. The resources incur charges while idle; a job timeout is not a subscription spending cap. The user explicitly approved the foundation with these costs and risks on 2026-10-15. Approval excludes image publication, source uploads and job execution.

## Actual Azure preview

Authenticated subscription inventory found only `NetworkWatcher_eastus2`; all seven required resource providers were registered. Before application, the project group did not exist and the inventory/preview performed no resource writes. The subsequent approved deployment created the new foundation; no provider registration was needed.

The final subscription-scope ARM what-if used **Provider** validation and returned **Succeeded: 39 Create, 0 Modify, 0 Delete, 0 Unsupported**. Every reported resource ID belongs to the new project group; no job resource is included. Its compiled template and full JSON are retained under `outputs/azure-subscription-validation/` and `outputs/azure-deployment-review/`. What-if predicts changes and checks configuration/permissions; it does not prove runtime behavior, quota availability at apply time or final billing. [Microsoft what-if reference](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/deploy-what-if)

The initial preview could not identify three role assignments because their names used the new identity's runtime principal ID. Their names now use the identity's stable resource ID, while the assigned principal, role and scope remain unchanged. The rerun resolves all three as new resources. If the managed identity is deleted and recreated, its principal changes: review and deliberately replace affected role assignments rather than assuming an in-place update will work. No automatic deletion or identity rotation is implemented.

Both Bicep entrypoints compile. The final static scan remains **19 passed, 0 failed and 4 scoped skips**, explained in [security exceptions](../infra/security-exceptions.md). The deployment scripts passed **40 local contract checks**, including custom network prefixes, containment, nonoverlap and rejection of unsuitable subnet sizes. These checks do not authenticate an operator or constitute production acceptance.

## Conditions carried forward

- Foundation creation, the proposed group/region and stated recurring costs/risks were explicitly approved on 2026-10-15; the fresh pre-apply preview again contained only the same 39 creates.
- Choose and price a private publisher/operator path. The predeployment inventory had no VNet or builder; the deployed foundation now has its own VNet. Peering alone is insufficient without appropriate private DNS resolution; no builder, VPN or DNS forwarding has been provisioned.
- Bind image review to the exact image that is published. A rebuild on another host produces a separately reviewed artifact; do not treat an earlier local scan as proof about the rebuild. Keep the image identity, platform, scanner/database and report hashes, then record the actual registry manifest digest after publication. A local Docker image ID is not assumed to be the registry digest.
- Resolve or explicitly disposition the image's remaining vulnerability findings before enabling a job. The runtime has received the available compression-library fix and the unused pip installer is removed after the controlled build. No suppression or production risk acceptance is implied.
- Control-plane checks passed for service access settings, scoped identity assignments, endpoints and DNS links. Before workload acceptance, verify actual private DNS resolution, image pull, identity data access, denied input writes, artifact completion and diagnostic delivery. The batch runner remains mock-only and does not provide authenticated operational command approval.

## Approved application

The foundation-only review was approved. Group absence, the compiled-template hash and the fresh 39-create preview were checked immediately before application. Non-create changes were rejected for this new-group operation. See [new-group instructions](../infra/subscription-readme.md); existing groups must use the established resource-group workflow.

The approved apply command is:

```powershell
az deployment sub create --subscription $subscriptionId --location eastus2 --name aicg-foundation --template-file outputs/azure-subscription-validation/subscription.json --parameters resourceGroupName=rg-ai-command-gateway-dev location=eastus2 --output json --only-show-errors
```

`$subscriptionId` must be the reviewed Douglas DME Systems subscription. The approved apply completed successfully. All 21 read-only foundation configuration checks passed; [the readiness record](../governance/azure-readiness-v0.4.json) binds the template, deployment result, verifier and supporting evidence. No job was provisioned. The verifier did not test private DNS resolution, service connectivity, data permissions or runtime behavior. A failed deployment can leave billable partial resources; preserve the deployment operations, investigate and review recovery. This workflow does not automatically delete resources or roll back a partial deployment.
