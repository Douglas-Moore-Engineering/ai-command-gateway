# Azure pilot cost estimate

Azure retirement verified at `2026-10-16T05:13:03.027368+00:00`: subscription ending `f609` remains Enabled, with zero active resource groups and zero active resources. The user explicitly requested "keep the subscription and delete other resources in azure." The foundation, managed Container Apps network group and original Network Watcher are removed, including the Azure image, dataset and result copies. Local originals, downloaded evidence, image archive, source code and GitHub repository remain. [Retirement evidence](../governance/azure-retirement-v0.4.json) supersedes the retained-resource statements below. The prior pilot remains historical evidence; redeployment requires a new scope and spending decision. Accrued charges may arrive later, and provider recovery retention is distinct from active resource existence. All deployment and cost statements below describe the historical review.

This record preserves the original foundation review and estimate. The later approved private operator and workload pilot are recorded in the [private access review](azure-private-access-plan.md) and [current results](results.md).

**The prepared infrastructure is approximately USD 98/month before meaningful workload activity; the illustrative base workload is about USD 102/month.** This is a partial cloud-service estimate for the current [Bicep implementation](../infra/main.bicep), not an all-in operating budget. A private builder and the operator's private-network access are still unpriced and could materially increase the total.

Prepared **2026-10-15, America/New_York**, using public Microsoft retail prices retrieved at **20:00–20:03 EDT** (2026-10-16 00:00–00:03 UTC). The estimate initially used East US 2 as a candidate. The user subsequently approved that target and approximately $98/month of core standing costs plus usage, the unpriced private access path and partial-deployment risks. The private foundation is now deployed in `rg-ai-command-gateway-dev` under the connected Douglas DME Systems subscription ending f609. No job was provisioned or started. This approval is not a subscription spending cap; actual billing and agreement discounts remain unmeasured. See [the deployment review](azure-deployment-review.md).

This supplements [COST-001](../customer/COST-001.md); it does not close OPEN-08, authorize spending or replace the lifecycle-cost record. Actual spend and engineering effort remain unmeasured. Prices are USD pay-as-you-go retail, before taxes, negotiated discounts, credits and shared free allowances. The monthly comparison uses 730 hours, or 30.4167 days; actual calendar-month charges vary. The [Microsoft Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) supplies rates, while the linked service documentation supplies billing rules.

## Persistent infrastructure

| Item and template basis | Rate used | 730-hour estimate |
| --- | ---: | ---: |
| One Premium ACR, no geo-replica | $1.6666/day | $50.69 |
| Three private endpoints: ACR, Blob, Azure Monitor | $0.01/endpoint-hour | $21.90 |
| Six private DNS zones; Blob's zone is shared with Monitor | $0.50/zone-month | $3.00 |
| One platform-managed Standard load balancer, assuming at most five rules | $0.025/hour | $18.25 |
| Allowance for one platform-managed Standard static egress IPv4 address | $0.005/hour | $3.65 |
| **Persistent subtotal** | | **$97.49** |

The ACR price includes 500 GB of registry storage; the scenarios assume image storage stays within it and do not add a second storage charge for those images. No ACR Tasks, replication or connected-registry charge is included. [ACR pricing and included capacity](https://azure.microsoft.com/en-us/pricing/details/container-registry/), [ACR East US 2 retail meters](https://prices.azure.com/api/retail/prices?$filter=armRegionName%20eq%20%27eastus2%27%20and%20serviceName%20eq%20%27Container%20Registry%27%20and%20priceType%20eq%20%27Consumption%27).

Private Link rates use the API's `Global` commercial meters. DNS uses `Zone 1`, which includes East US 2, and assumes the first-25-zone tier. Monitor needs five DNS zones, but one is the already-counted Blob zone: the template creates six distinct zones overall. The estimate includes no DNS Private Resolver. [Private Link pricing](https://azure.microsoft.com/en-us/pricing/details/private-link/), [Private Link retail meters](https://prices.azure.com/api/retail/prices?$filter=productName%20eq%20%27Virtual%20Network%20Private%20Link%27%20and%20priceType%20eq%20%27Consumption%27), [DNS billing and regions](https://azure.microsoft.com/en-us/pricing/details/dns/), [DNS retail meters](https://prices.azure.com/api/retail/prices?$filter=serviceName%20eq%20%27Azure%20DNS%27%20and%20priceType%20eq%20%27Consumption%27).

The managed load balancer and egress-IP allowance account for platform resources beyond those explicitly declared in Bicep. Microsoft's current VNet documentation lists one Standard load balancer and an egress public IP as billable for workload-profile environments. The same page describes the internal environment's managed resource group as containing only a load balancer; therefore retain the $3.65 IP allowance until actual managed resources and billing meters are inspected. If no egress-IP charge applies, subtract $3.65/month. More than five load-balancer rules would add charges. [Container Apps managed network resources](https://learn.microsoft.com/en-us/azure/container-apps/custom-virtual-networks?tabs=workload-profiles-env#managed-resources), [load-balancer retail meters](https://prices.azure.com/api/retail/prices?$filter=serviceName%20eq%20%27Load%20Balancer%27%20and%20priceType%20eq%20%27Consumption%27), [East US 2 IP meters](https://prices.azure.com/api/retail/prices?$filter=armRegionName%20eq%20%27eastus2%27%20and%20serviceName%20eq%20%27Virtual%20Network%27%20and%20priceType%20eq%20%27Consumption%27).

The postdeployment ARM inventory observed one Standard load balancer, `capp-svc-lb`, in the Container Apps managed group, and no standalone public-IP resource there. The $3.65 allowance is retained conservatively until billing is reconciled; the current inventory does not establish the final billed meter set. Raw inventory is retained under ignored `outputs/azure-deployment-review/` and bound into the readiness record.

No dedicated workload profile, planned-maintenance feature or **Container Apps environment private endpoint** is configured. Consequently this estimate does not add the Container Apps $0.10/hour environment/private-endpoint management meter. The three endpoints above connect to other services. This applicability assessment follows the current template and should be checked against the deployed bill; enabling an ACA-specific private endpoint would change the estimate. [Container Apps billing](https://learn.microsoft.com/en-us/azure/container-apps/billing), [Container Apps private-endpoint billing](https://learn.microsoft.com/en-us/azure/container-apps/private-endpoints-with-dns#billing).

## Workload rates and calculation

| Usage | Retail rate used | Application |
| --- | ---: | --- |
| Active job CPU | $0.000024/vCPU-second | 1 vCPU per running replica |
| Active job memory | $0.000003/GiB-second | 2 GiB per running replica |
| Analytics Logs ingestion | $2.76/GB | Gross cost before the shared 5-GB allowance |
| Hot ZRS Blob capacity | $0.023/GB-month | First capacity tier; average stored amount |
| Blob writes / lists / container creation | $0.0625/10,000 | Count actual transactions, including multipart uploads |
| Blob reads / other operations | $0.004/10,000 each | Separate transaction categories |
| Private DNS queries | $0.40/million | First query tier |
| Private Link data | $0.01/GB in each direction | Aggregate processed bytes across endpoints/directions |
| Standard load-balancer data | $0.005/GB | Metered traffic, including applicable management traffic |

Rates are from [Container Apps East US 2 meters](https://prices.azure.com/api/retail/prices?$filter=armRegionName%20eq%20%27eastus2%27%20and%20productName%20eq%20%27Azure%20Container%20Apps%27%20and%20priceType%20eq%20%27Consumption%27), [Log Analytics East US 2 meters](https://prices.azure.com/api/retail/prices?$filter=armRegionName%20eq%20%27eastus2%27%20and%20serviceName%20eq%20%27Log%20Analytics%27%20and%20priceType%20eq%20%27Consumption%27), [Hot ZRS East US 2 meters](https://prices.azure.com/api/retail/prices?$filter=armRegionName%20eq%20%27eastus2%27%20and%20productName%20eq%20%27General%20Block%20Blob%20v2%27%20and%20skuName%20eq%20%27Hot%20ZRS%27%20and%20priceType%20eq%20%27Consumption%27), and the DNS/network meters above. The Analytics Logs ingestion meter at tier minimum 5 GB is used, not the legacy Standard/Data Analyzed meter that also appears in the API.

For `N` executions of `t` billed seconds, gross compute is `N × t × (1 × 0.000024 + 2 × 0.000003)` dollars. Thus a 10-minute run is **$0.018** and a 30-minute run is **$0.054**, before shared allowances. These are configured-resource estimates, not measured Azure runtimes. Jobs use active rates, stop consuming compute after completion and have no ingress-request charge. The subscription-wide monthly grants are 180,000 vCPU-seconds and 360,000 GiB-seconds; this estimate reserves neither for this workload. [Job billing and shared grants](https://learn.microsoft.com/en-us/azure/container-apps/billing).

An initial local Linux container check with the actual five datasets, 1 CPU and 2 GiB completed in **49.299 seconds**, with about **1.02 GiB cgroup peak memory** and no recorded out-of-memory event. At 50 seconds, the above compute formula is $0.0015 per run. This is a sizing observation from local filesystem Blob simulation, not a measured Azure execution or transfer time; the 10-minute base scenario deliberately leaves room for cloud startup and I/O. The supplied evidence is `outputs/azure-container-resources/resource-summary.json`.

The default 30-day log retention is within Analytics Logs' included 31 days, so no extended-retention charge is added. The first 5 GB/month ingestion allowance is shared per billing account; it is not subtracted independently for each workspace or scenario. If fully available, it reduces the low/base/high log amounts below by $0.28/$2.76/$13.80 respectively. [Azure Monitor pricing](https://azure.microsoft.com/en-us/pricing/details/monitor/).

## Low, base and high illustrations

These are explicit planning assumptions, not forecasts from observed cloud usage. Each includes the same persistent infrastructure. Blob capacity includes originals, derived artifacts, versions and soft-deleted objects. The 30-day output lifecycle plus seven-day soft-delete setting does not mean bytes stop being billable at day 30. Input files are not expired by that lifecycle rule.

| Monthly assumption | Low | Base | High |
| --- | ---: | ---: | ---: |
| Manual executions × seconds each | 10 × 60 | 30 × 600 | 300 × 1,800 |
| Average Blob capacity | 1 GB | 5 GB | 50 GB |
| Log ingestion | 0.1 GB | 1 GB | 30 GB |
| Writes/lists, reads and other operations, **each category** | 10,000 | 100,000 | 1,000,000 |
| DNS queries | 10,000 | 100,000 | 1,000,000 |
| Aggregate Private Link processed data | 2 GB | 20 GB | 200 GB |
| Load-balancer processed data | 2 GB | 20 GB | 200 GB |
| Persistent infrastructure | $97.49 | $97.49 | $97.49 |
| Job compute, before grants | $0.02 | $0.54 | $16.20 |
| Logs, before allowance | $0.28 | $2.76 | $82.80 |
| Blob capacity and operations | $0.09 | $0.82 | $8.20 |
| DNS and network data processing | $0.03 | $0.34 | $3.40 |
| **Core monthly subtotal** | **$97.91** | **$101.95** | **$208.09** |
| Core subtotal + illustrative 20% uncertainty allowance | $117.50 | $122.34 | $249.71 |
| Core subtotal × 12, unchanged usage/rates | $1,174.97 | $1,223.43 | $2,497.11 |

Totals use unrounded arithmetic; rounded line items may differ by a cent. The 20% allowance is an engineering planning choice, not a vendor charge, confidence interval or substitute for the exclusions below. If both compute grants were wholly unused elsewhere, the job-compute entries would instead be $0/$0/$10.80. No grant is counted twice in the main totals.

The high case is not a spending ceiling. Manual starts can overlap, and the template's one-replica setting is per execution. The 1-GB/day Log Analytics cap may overshoot and does not cap other services' costs. [Daily-cap limitations](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/daily-cap). Every additional 10 GB of billable logs adds $27.60; every extra private endpoint held for 730 hours adds $7.30 before data. These are more material for this pilot than one additional short job run.

## Costs still to add before deployment

- **Private builder and operator connectivity:** a VNet-connected build host or agent, disks, image-scanning service, and any VPN, ExpressRoute, Bastion, NAT gateway or DNS Private Resolver chosen for access. The current template provides none of these. Existing access could have marginal cost; newly provisioned access needs a separate estimate.
- **Data transfer:** Internet and inter-region bandwidth, additional routing meters and any image distribution outside this region. Private Link data-processing premiums do not replace bandwidth charges. The scenario amounts for load-balancer and private-endpoint traffic are independently metered assumptions, not an assertion that every byte crosses both. [Private Link pricing terms](https://azure.microsoft.com/en-us/pricing/details/private-link/).
- **Additional assurance and operations:** paid Defender or other scanning, backup beyond the declared versioning/soft delete, alerts, support, incident response, retention changes and disaster recovery. No paid model inference occurs in the implemented Azure job modes.
- **One-time and ongoing labor:** delivery, customer review, testing in Azure, operation, updates and retirement remain hours × rate inputs in COST-001. No labor estimate, actual cost, ROI or affordability claim is made here.

The foundation target and stated recurring costs were approved. Before expanding to workload publication or execution, price the private build/access path, review subscription-level benefits and select a cost-monitoring owner. After the first controlled run, reconcile billed meters, managed networking, runtime, logs, storage and traffic with this estimate. Refresh the forecast when the region, topology, retention, frequency or image size changes. Reusing the reviewed registry and networking across authorized workloads could reduce the allocated fixed cost, but requires an explicit isolation and ownership decision.

## Evidence and reproducibility

Local JSON evidence is under `outputs/azure-cost-review/` (ignored generated outputs). `estimate.json` contains the exact selected Microsoft meter records, retrieval timestamps, source URLs, input-template SHA-256 values, formulas' inputs and unrounded calculations. Raw responses are retained as `acr_eastus2.json`, `blob_eastus2.json`, `container_apps_eastus2.json`, `logs_eastus2.json`, `dns.json`, `private_link_global.json`, `lb_global.json` and `private_link_eastus2.json` (the last includes the IP meter). Earlier `eastus` responses are exploratory only and are not used in the final estimate. API throttling was retried; every rate used in `estimate.json` has a successful response record.

The API needs no Azure credentials. Follow each linked query, follow `NextPageLink` until empty, select the exact meter/SKU/region/tier and use `retailPrice` in its stated unit. DNS and network global/zone meters are intentionally selected instead of substituting a nonexistent East US 2-specific row. Recalculate the tables from the saved scenario inputs. A price response is not evidence that the target subscription has quota, regional capacity or permission to provision that service.
