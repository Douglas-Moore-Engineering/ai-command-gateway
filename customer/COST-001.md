# COST-001 — lifecycle cost planning v0.1

Source: DISC-001; USD, 2026-10-14 base date; undiscounted 12-month horizon. USD 30,000 and eight weeks are fictional constraints, not calculated costs, quotes or spending authorization. Actual cost and benefits: not measured.

| Category | Payer/estimate owner | Calculation and gap |
| --- | --- | --- |
| One-time delivery | DME / DME lead | hours × rate for discovery, design, data, development, V&V, security, training and handoff; quantities/rates TBD |
| Internal review | Fictional customer sponsor | controls/operator/security/platform hours × internal cost; separate from DME fees |
| Recurring third party | Platform owner | inference + storage + monitoring + licenses + backup + support; hosting and workload TBD |
| Change and exit | DME/service owner | policy/model revalidation, upgrades, export and retirement; quantities TBD |

OPEN-08 requires low/base/high scenarios, contingency, cost sources/dates, one-time/recurring separation and affordability review before implementation commitment. Future estimates must include actuals-to-date, forecast remaining, sensitivity and review history. No ROI is calculated without measured benefit inputs. Next update: scope/hosting review. Approval authority remains unassigned for this portfolio scenario.

## v0.2 local increment update - 2026-10-15

The user authorized local construction. This increment uses existing hardware, local storage and downloaded Python dependencies; no new cloud/model subscription was provisioned. Labor, electricity, installation bandwidth, total actual cost and remaining forecast are not measured. This does not imply zero lifecycle cost or approved affordability. The v0.1 USD/12-month basis and OPEN-08 remain in force; next update is domain/policy scope review before any paid or operational continuation. No competing cost model is introduced.

## v0.4 Azure foundation estimate and approval - 2026-10-15

The user explicitly approved: "Approve foundation deployment with these costs and risks" after reviewing the new `rg-ai-command-gateway-dev` group in East US 2, approximately $98/month in core standing charges, usage charges, an unpriced private builder/access path and the possibility of billable partial resources after failure. The target uses the existing `douglas@dmesystems.global` Azure account and subscription ending `f609`. Foundation deployment succeeded; its persistent resources can now incur charges. No actual bill has been measured. [Deployment review](../docs/azure-deployment-review.md)

The [regional estimate](../docs/azure-cost-estimate.md) records Microsoft retail meter sources and calculation assumptions. Standing core charges total **$97.49/month** for Premium ACR, three private endpoints, six private DNS zones and allowances for the managed load balancer/egress IPv4. Illustrative low/base/high core workloads are **$97.91 / $101.95 / $208.09 per month** before the documented 20% allowance. These are planning scenarios, not a measured bill or cap. Private builder/VPN/Bastion/DNS resolver, other bandwidth, support, engineering labor and further assurance remain excluded or unpriced.

Post-deployment inventory found 27 resources in the project group and one Standard Load Balancer in the Container Apps managed group. It found no standalone public-IP resource; the IPv4 amount remains a conservative planning allowance pending billing evidence. The original Network Watcher was retained. Resource counts from this inventory differ from the ARM preview's child-resource accounting.

The approval covers the private foundation only. Image publication, dataset transfers, job provision/execution and model inference are outside this approval. The deployed foundation disables the job; storage/registry/network charges can continue while idle. The local five-dataset container run completed in 81.363 seconds at 1 CPU / 2 GiB, but Azure runtime, transfer and operating cost remain unmeasured. Derived artifact retention defaults to 30 days.

This real spending approval does not convert the fictional USD 30,000 discovery constraint into a budget or close OPEN-08. Record actual billed charges, private-access options and a remaining-work forecast before the next spending decision. No ROI or whole-project affordability claim is supported.

## v0.4 temporary access and workload approval - 2026-10-16 UTC

The user approved: "Approve deployment, testing and scoped cleanup with these costs and risks" against the [reviewed private access plan](../docs/azure-private-access-plan.md). The estimate was approximately $1.55 for four hours plus usage, a proposed $5 allowance rather than an automatic cap, or $282.94/month if retained. Scope included the operator, image publication, all five original uploads, cloud tests and deletion of the operator group plus its eleven enumerated foundation additions. The foundation, image, datasets, job and evidence are retained. A first apply failed, its narrowly reviewed repair succeeded, and the approved workload tests completed. The temporary operator group and all eleven foundation additions were removed. All 31 post-cleanup configuration checks passed; explicit child and temporary-role absence was verified.

This is spending authorization and measured execution evidence, not an actual bill. The $97.49/month core estimate remains standing after temporary cleanup; dataset storage, registry content, job and monitoring usage add variable cost. The planned four-hour operator estimate is not substituted for measured billed duration. DME should reconcile Azure billing after charges settle and update actuals/remaining forecast; OPEN-08 and broader lifecycle affordability remain open. No model inference or benefit/ROI measurement was performed.
