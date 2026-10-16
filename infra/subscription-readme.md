# Foundation in a new resource group

[subscription.bicep](subscription.bicep) creates a new resource group and calls the existing [main.bicep](main.bicep) foundation within it. `provisionJob` is fixed to `false`: the wrapper creates no job, publishes no image and uploads no data. All private-service controls remain in the existing modules. The nested deployment is named `aicg-bootstrap`, preserving the output lookup used by the [implementation guide](../docs/azure-implementation.md).

**Use this wrapper only for a resource group that does not exist.** Bicep cannot enforce create-only semantics: applying it to an existing group could change that group's tags. For an existing group, use [azure_preflight.ps1](../scripts/azure_preflight.ps1) and [deploy_azure.ps1](../scripts/deploy_azure.ps1). Check absence again immediately before any future apply. An account selection or successful what-if does not authorize provisioning.

The approved deployment created `rg-ai-command-gateway-dev` in `eastus2`; neither value is hardcoded. This group now exists, so do not reuse the new-group workflow for it. [The deployment review](../docs/azure-deployment-review.md) records the successful apply and configuration checks. Every future target still needs its own subscription, region, address-space, permission and cost review. The template exposes the workload name, three CIDRs and artifact/log retention. When supplying custom CIDRs, use the existing preflight's offline structural validation with the same values; it does not require the group to exist unless `-Online` is used. Reserved ranges, existing networks, DNS integration and service availability remain separate checks.

Compile and scan locally from the repository root:

```powershell
New-Item -ItemType Directory -Path outputs/azure-subscription-validation -Force | Out-Null
./.cache/azure-cli/bin/bicep.exe build infra/subscription.bicep --outfile outputs/azure-subscription-validation/subscription.json
./.cache/checkov-venv/Scripts/python.exe ./.cache/checkov-venv/Scripts/checkov -d infra/ --framework bicep --quiet --skip-download
```

The following example reproduces the original review pattern. For a future approved new target, choose an absent group before running it; the deployed project group intentionally fails this guard. After signing in, this example checks group absence and requests **read-only** subscription-scope what-if. Replace the subscription placeholder before running it. Use the same reviewed parameter values for structural validation, what-if and any later application.

```powershell
$subscriptionId = '<reviewed-subscription-id>'
$resourceGroup = 'rg-ai-command-gateway-dev'
$location = 'eastus2'
$exists = az group exists --subscription $subscriptionId --name $resourceGroup --output tsv --only-show-errors
if ($LASTEXITCODE -ne 0 -or $exists -ne 'false') {
    throw 'The resource group already exists or its absence could not be verified; do not use this wrapper.'
}
az deployment sub what-if --subscription $subscriptionId --location $location --name aicg-foundation-review --template-file outputs/azure-subscription-validation/subscription.json --parameters "resourceGroupName=$resourceGroup" "location=$location" --validation-level Provider --no-pretty-print --output json --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'Subscription what-if failed; inspect the result.' }
```

Review the entire what-if, including nested changes; reject deletion, unsupported results and unreviewed modifications. Creating the group and foundation requires subscription-level resource-group/deployment permission, resource creation permission and the declared role-assignment rights. The subscription deployment location stores deployment metadata and is independent of the resources' location. These commands contain no apply step. [Microsoft subscription deployment guidance](https://learn.microsoft.com/azure/azure-resource-manager/bicep/deploy-to-subscription)

After an authorized foundation deployment, use the existing resource-group workflow for image publication and the Job stage. The original [four scoped Checkov dispositions](security-exceptions.md) still apply. Compilation and static scanning do not verify private connectivity, quotas, costs, image safety or successful Azure execution.
