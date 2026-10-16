# Azure IaC validation evidence

Local verification on 2026-10-15 used Bicep **0.48.1** and Checkov **3.3.29**. This record covers static infrastructure checks. It is not an Azure deployment or production security acceptance record.

Compiler command, from the repository root:

```powershell
.\.cache\azure-cli\bin\bicep.exe build infra/main.bicep --outfile .cache/azure-main.json
```

Actual final output: no stdout or stderr; **exit status 0**. All seven Bicep files compiled together without warnings.

Scanner command:

```powershell
.\.cache\checkov-venv\Scripts\python.exe .\.cache\checkov-venv\Scripts\checkov -d infra/ --framework bicep --quiet --skip-download
```

Actual final output, **exit status 0**:

```text
bicep scan results:

Passed checks: 19, Failed checks: 0, Skipped checks: 4
```

The four scoped skips are CKV_AZURE_36, CKV_AZURE_43, CKV_AZURE_166 and CKV_AZURE_206. Their resource-specific reasoning, evidence and remaining work are in [security-exceptions.md](security-exceptions.md). The scanner result must be reported with these skips; it does not prove all security requirements or absence of high/critical vulnerabilities. In particular, automatic image scan/quarantine/release enforcement remains unimplemented. A first scan attempted a blocked remote guideline download; the final command disables downloads and uses installed local checks.

The [plan](../.azure/infrastructure-plan.json) contains 41 logical resource records, including inline subnets and individual DNS zones/links. A local JSON check confirmed unique logical names, resolved dependency references and an acyclic dependency graph. The example parameter names correspond to the template, and all required module outputs are type-checked by Bicep. The `provisionJob` default is false; no placeholder image is provisioned.

Phase 6 completion check:

- **PASS:** Bicep validation exited cleanly, with actual command/output above.
- **PASS WITH FOUR DISPOSITIONS:** Checkov exited 0 with 19 passed, 0 failed and 4 scoped skips. No severity-based security acceptance is claimed.
- **PASS:** Implemented private Blob/ACR/Monitor connectivity, disabled public data access, managed identity/scoped RBAC, storage TLS 1.2 and no application secrets. The job has no ingress service. Outbound traffic inspection is outside this nonproduction design.
- **PASS FOR PROVIDED CONTEXT:** No existing Azure resource was supplied by ID or reconstructed from a live inventory, so none is recreated by reference. Actual target inventory and what-if remain prerequisites; the template is intended for new isolated infrastructure.
- **PASS:** IaC is under `infra/`; original dataset files and source records are untouched by this work.
- **NOT RUN:** Azure what-if, deployment, registry publication, Azure source upload, DNS/RBAC/log-delivery checks and live job execution.

No infrastructure has been created or destroyed, and the plan remains `draft`. See the [implementation guide](../docs/azure-implementation.md) for the remaining target-specific steps.
