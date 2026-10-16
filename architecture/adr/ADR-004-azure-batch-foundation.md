# ADR-004: Azure batch foundation with private data services

Status: bounded pilot foundation explicitly approved and successfully deployed with the job disabled. Operational validation remains pending. Date: 2026-10-15. Trace: REQ-02, REQ-04 and REQ-06; the existing requirement/acceptance IDs retain their proposed status. The user requested continuation through Azure implementation, then approved the concrete foundation costs and risks. [Deployment review](../../docs/azure-deployment-review.md) records that scope and outcome. This decision adds infrastructure and a job wrapper without changing gateway command authority.

## Context and decision

The application is a finite CLI workload: inspect inputs, produce evidence and exit. It has no served API and needs no always-running worker. Use a manually triggered Azure Container Apps Job with a user-assigned identity and private Blob/ACR access. Keep the initial workload synthetic; opt into the supplied dataset analysis separately. No hosted model or equipment integration is part of the job.

Container Apps Jobs support manually started, scheduled and event-driven executions. Manual execution matches this implementation's explicit run boundary. This is an architectural judgement for the current workload, not a measured cost or performance optimum. [Microsoft job documentation](https://learn.microsoft.com/en-us/azure/container-apps/jobs)

| Candidate | Fit and consequence | Decision |
| --- | --- | --- |
| Container Apps Job | Finite container execution with managed identity; private networking and image bootstrap require validation | Selected for the manual pilot |
| App Service/web application | Useful for a served UI/API, but introduces a service lifecycle the current CLI does not need | Revisit if an operator application is implemented |
| AKS | Provides detailed scheduling/network control with additional cluster operations | Deferred until requirements justify that operational responsibility |
| Keep all processing local | Least external data exposure; already runnable and testable | Retained as the development and fallback path |

## Implementation and boundaries

The [template](../../infra/main.bicep) provisions a VNet, delegated Container Apps subnet, private service endpoints/DNS, private Premium ACR, Blob Storage, Log Analytics/private Monitor access and a user-assigned identity. Container scope separates input read permission from output write permission. The workload pulls an immutable image digest. Registry admin-user authentication, storage shared keys and public data-plane access are disabled by the template. No Key Vault is needed for this identity-based workload; adding a provider secret would require a new data/credential-flow review.

Use two deployments: foundation with no job, then the job after an authorized private-network builder pushes the reviewed image. The deployment helper requires explicit subscription/resource group/region, and applies changes only with `-Online -Deploy` after successful what-if. Modifications require the additional explicit `-AllowModify`; deletion and indeterminate change types are blocked. It does not upload datasets or start the job. See the [implementation procedure](../../docs/azure-implementation.md).

The job has no ingress and the container runs as a non-root user. The build context admits only runtime code and controlled synthetic/metadata files. Raw research files remain separate Blob inputs; result upload uses an explicit artifact list. There is one worker per execution, while separate manual executions can overlap. Unique output prefixes isolate evidence; there is no global distributed approval ledger, and this is not an authenticated multiuser command service.

An Azure identity is necessary but insufficient evidence of application authority. Job-start permission can allow template overrides, and therefore access to the attached managed identity; keep it restricted to trusted deployment operators. No ordinary gateway approval role is granted infrastructure authority. [Microsoft job permissions](https://learn.microsoft.com/en-us/azure/container-apps/jobs#permissions)

## Consequences and review triggers

Private services reduce public data-plane exposure and require a working private build/upload/query path. The user approved the East US 2 foundation in `rg-ai-command-gateway-dev`, subscription ending `f609`, with [estimated standing core charges](../../docs/azure-cost-estimate.md) of $97.49/month plus usage and an unpriced private builder/access path. Actual billed costs remain unmeasured. This approval covers foundation only; image publication, dataset uploads and job provision/execution remain separate. The local five-dataset [container check](../../docs/azure-runtime-checks.md) passed at 1 CPU / 2 GiB, but Azure capacity, latency and recovery are unverified; concurrency and retention remain pilot settings.

Local tests, template compilation and static scanning establish limited implementation evidence. The actual foundation preview reported 39 creates and no other changes. Deployment succeeded and all 21 read-only control-plane checks passed. Local image build and scanning are recorded, with [unresolved image findings](../../docs/image-security.md). Image publication/pull, managed-identity data access, private DNS resolution, end-to-end execution, denied-access cases, artifact recovery, actual cost and operational review still require their own results. [Results](../../docs/results.md) reports the boundary actually exercised.

Review the decision before adding schedules/events, public ingress, user APIs, model credentials, operational datasets, multiple tenants, production recovery requirements or any equipment adapter. Independent domain policy, authenticated human authorization and customer acceptance remain separate open work. Preserve the local path while resolving Azure-specific failures.
