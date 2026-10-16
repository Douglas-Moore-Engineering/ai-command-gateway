# AI Command Gateway architecture

View: ARCH-001 v0.1, 2026-10-15. Local implementation design; verification and acceptance status are recorded in [PROJECT_STATUS](../../PROJECT_STATUS.md). Purpose: show how the supplied research data reaches inspection and replay while deterministic checking, simulated human approval and durable mock outcomes retain distinct responsibilities.

[Implementation baseline](../implementation-baseline.md) · [ADR-001](../../architecture/adr/ADR-001-offline-foundation.md) · [Standards tailoring](../../governance/standards-tailoring.md) · [Requirements](../../requirements/traceability.csv)

## System, data and authority boundaries

All five inputs are profiled locally. Only the S1 process records enter historical replay; their engineering units and command rules remain unqualified, so they escalate. Synthetic fixtures separately exercise the approval path. ARCH-001 describes the offline command path. The optional model adapter added in v0.4 is shown separately in ARCH-003 below; it has no equipment or approval interface.

```mermaid
%% Local implementation view; no physical actuation or model inference.
%% Source dataset replay is unqualified and can only escalate.
%%{init: {"theme":"base","look":"classic","themeVariables":{"fontFamily":"Arial, sans-serif","fontSize":"18px","primaryTextColor":"#111111","lineColor":"#425466","background":"transparent","edgeLabelBackground":"transparent","clusterBkg":"transparent"},"flowchart":{"htmlLabels":false,"curve":"basis","nodeSpacing":28,"rankSpacing":38,"padding":12},"themeCSS":"text { font-family:Arial,sans-serif !important; } .cluster-label text { font-size:16px !important; font-weight:600; }"}}%%
flowchart TB
  files["Five local research inputs"]
  fixture["Synthetic request fixture"]

  subgraph data["Read-only data qualification"]
    inspect["Inspect files and archive metadata"]
    profiles[("Provenance and profiles")]
    replay["Replay S1 recorded targets<br/>Units and rules unqualified"]
  end

  subgraph gateway["Local deterministic gateway"]
    policy["Versioned policy<br/>Unqualified or synthetic demo"]
    evaluate["Validate request and policy<br/>Allow / block / escalate"]
  end

  subgraph authority["Simulated human authority"]
    review["Local reviewer label<br/>Approve eligible demo proposal"]
    recheck["Bind approval; revalidate<br/>Expiry, state, policy and one-use"]
  end

  subgraph evidence["Durable local evidence"]
    ledger[("SQLite ledger<br/>Decisions, approvals, mock outcomes")]
    receipt["Mock outcome receipt<br/>No equipment interface"]
  end

  files -->|"all five inputs"| inspect
  inspect -->|"schema and inspection facts"| profiles
  files -->|"S1 process rows only"| replay
  replay -->|"unqualified request: escalate"| evaluate
  fixture -->|"explicit synthetic state"| evaluate
  policy -->|"rule version and content hash"| evaluate
  evaluate -->|"eligible demo proposal"| review
  review -->|"approval request"| recheck
  evaluate -->|"record every decision"| ledger
  recheck -->|"atomic consumption and mock outcome"| ledger
  ledger -->|"committed outcome only"| receipt

  classDef sourceRole fill:#EAF3F8,stroke:#356079,stroke-width:1.5px,color:#111111
  classDef dataRole fill:#E5F4F2,stroke:#32746E,stroke-width:1.5px,color:#111111
  classDef policyRole fill:#F8F2E4,stroke:#876A2D,stroke-width:1.5px,color:#111111
  classDef humanRole fill:#EFF6EB,stroke:#4C713E,stroke-width:1.5px,color:#111111
  classDef evidenceRole fill:#F3F0F8,stroke:#6E5B85,stroke-width:1.5px,color:#111111
  class files,fixture sourceRole
  class inspect,replay dataRole
  class policy,evaluate,recheck policyRole
  class review humanRole
  class profiles,ledger,receipt evidenceRole
  style data fill:none,stroke:#32746E,stroke-width:1.5px,color:#111111
  style gateway fill:none,stroke:#876A2D,stroke-width:1.5px,color:#111111
  style authority fill:none,stroke:#4C713E,stroke-width:1.5px,color:#111111
  style evidence fill:none,stroke:#6E5B85,stroke-width:1.5px,color:#111111
  linkStyle default stroke:#425466,stroke-width:1.5px
```

**Color legend:** Blue — source records/fixtures; Teal — data qualification; Gold — policy and decision checks; Green — simulated human decisions; Purple — evidence and outcomes. Group backgrounds and diagram canvas are transparent; node colors retain their meaning across exports.

The whole runtime sits inside one trusted workstation boundary. The reviewer label is not an authenticated identity, and SQLite is not a protected evidence store against a user who can edit it. The diagram shows application workflow separation; production separation of duties remains an open requirement.

An `allow` decision means eligibility under synthetic rules. Approval binds the complete request, including state, and the current policy hash. The mock execution path rechecks expiry, state freshness and policy, then commits approval consumption and the mock outcome atomically. Changed request/state requires a new approval. On audit failure, no success receipt is returned; diagnostic output takes the place of an unavailable ledger entry.

## Sources and exports

- [Editable Mermaid source](../diagrams/01-offline-authority.mmd)
- [Renderer configuration](../diagrams/mermaid-config.json)
- [Rendered SVG preview](../diagrams/01-offline-authority.svg)
- [Render and inspection record](../diagrams/README.md)

Keep the source and embedded Mermaid synchronized. Revisit this view if a provider, real identity, additional dataset adapter, policy-authority boundary, network listener or equipment integration is added. A new component needs implementation/evidence and a corresponding architecture decision before it is represented as operational.

## Cited local observations

ARCH-002 v0.1, 2026-10-15. Typed profiles produce a locally verified catalog. Retrieval returns exact cited observations or abstains; every fact retains unresolved engineering qualification. The advisor has no approval or execution interface. See [ADR-002](../../architecture/adr/ADR-002-cited-observations.md) and [catalog trust boundaries](../evidence-design.md).

```mermaid
%% Implemented local observation retrieval; no model inference or equipment advice.
%%{init: {"theme":"base","look":"classic","themeVariables":{"fontFamily":"Arial, sans-serif","fontSize":"18px","primaryTextColor":"#111111","lineColor":"#425466","background":"transparent","edgeLabelBackground":"transparent","clusterBkg":"transparent"},"flowchart":{"htmlLabels":false,"curve":"basis","nodeSpacing":28,"rankSpacing":38,"padding":12},"themeCSS":"text { font-family:Arial,sans-serif !important; } .cluster-label text { font-size:16px !important; font-weight:600; }"}}%%
flowchart TB
  profile["Dataset profile"]
  inventory["Pinned source inventory"]

  subgraph build["Evidence preparation"]
    validate["Check identity and typed observations"]
    catalog[("Catalog, snapshot and manifest")]
  end

  subgraph retrieval["Local observation retrieval"]
    question["User question and source filter"]
    verify["Verify catalog and rebuild facts"]
    retrieve["Match subject and requested metrics"]
  end

  subgraph response["Response boundary"]
    eligible{"Matching, consistent observations?"}
    answer["Exact observation extracts and citations"]
    abstain["Abstain with a reason"]
  end

  subgraph evidence["Regression evidence"]
    cases["Frozen questions and expected facts"]
    assess["Check claims, citations and abstention"]
    report[("Versioned evaluation report")]
  end

  profile -->|"structured observations only"| validate
  inventory -->|"expected identities"| validate
  validate -->|"canonical facts and content hashes"| catalog
  catalog -->|"local artifacts"| verify
  question -->|"question remains input data"| retrieve
  verify -->|"verified facts"| retrieve
  verify -->|"unavailable or altered"| abstain
  retrieve -->|"matching facts and conflicts"| eligible
  eligible -->|"yes; observation only"| answer
  eligible -->|"no; or operational request"| abstain
  answer -->|"claim and source bindings"| assess
  abstain -->|"reason and empty claims"| assess
  cases -->|"fixed expectations"| assess
  assess -->|"case results and artifact hashes"| report

  classDef sourceRole fill:#EAF3F8,stroke:#356079,stroke-width:1.5px,color:#111111
  classDef dataRole fill:#E5F4F2,stroke:#32746E,stroke-width:1.5px,color:#111111
  classDef analysisRole fill:#EDF0FA,stroke:#42558B,stroke-width:1.5px,color:#111111
  classDef policyRole fill:#F8F2E4,stroke:#876A2D,stroke-width:1.5px,color:#111111
  classDef humanRole fill:#EFF6EB,stroke:#4C713E,stroke-width:1.5px,color:#111111
  classDef evidenceRole fill:#F3F0F8,stroke:#6E5B85,stroke-width:1.5px,color:#111111
  class profile,inventory sourceRole
  class validate,verify dataRole
  class retrieve analysisRole
  class eligible,abstain policyRole
  class question humanRole
  class catalog,answer,cases,assess,report evidenceRole
  style build fill:none,stroke:#32746E,stroke-width:1.5px,color:#111111
  style retrieval fill:none,stroke:#42558B,stroke-width:1.5px,color:#111111
  style response fill:none,stroke:#876A2D,stroke-width:1.5px,color:#111111
  style evidence fill:none,stroke:#6E5B85,stroke-width:1.5px,color:#111111
  linkStyle default stroke:#425466,stroke-width:1.5px
```

Color roles: blue/source inputs, teal/validation, indigo/retrieval, gold/decision, green/user input, purple/evidence. [Editable source](../diagrams/02-grounded-advice.mmd), [SVG](../diagrams/02-grounded-advice.svg), [PNG](../diagrams/02-grounded-advice.png). The local manifest checks consistency, not authenticity; the frozen cases are development regressions, not independent acceptance.

## Optional guarded model adapter

ARCH-003 v0.1, 2026-10-15. Implemented adapter tested with injected provider responses; live API behavior and model quality remain unverified. Default advice stays offline. The explicit provider path receives only a question, selected observation IDs/statements and catalog identity. It can reorder exact facts; it cannot expand their meaning or grant authority. [ADR-003](../../architecture/adr/ADR-003-guarded-model-advice.md) records the contract and limitations.

```mermaid
%% Optional provider path; transport exercised with fixtures, no live inference verified.
%%{init: {"theme":"base","look":"classic","themeVariables":{"fontFamily":"Arial, sans-serif","fontSize":"18px","primaryTextColor":"#111111","lineColor":"#425466","background":"transparent","edgeLabelBackground":"transparent","clusterBkg":"transparent"},"flowchart":{"htmlLabels":false,"curve":"basis","nodeSpacing":28,"rankSpacing":38,"padding":12},"themeCSS":"text { font-family:Arial,sans-serif !important; } .cluster-label text { font-size:16px !important; font-weight:600; }"}}%%
flowchart TB
  question["Question and explicit provider option"]

  subgraph local["Local evidence preparation"]
    catalog[("Verified observation catalog")]
    retrieve["Retrieve exact cited observations"]
    eligible{"Supported observations?"}
    request["Bounded structured request<br/>Selected facts; no tools"]
  end

  subgraph provider["Optional OpenAI boundary"]
    route{"Dry run?"}
    preview["Show request locally<br/>No credential or network use"]
    api["Responses API adapter<br/>Fixed HTTPS; one attempt"]
  end

  subgraph validation["Local response validation"]
    recheck["Recheck catalog and response<br/>Exact claims and full coverage"]
    valid{"Verified claims?"}
    accepted["Locally reconstructed citations<br/>Model status: validated"]
    fallback["Local observations or abstention<br/>Explicit skipped / fallback / rejected"]
  end

  question -->|"question and source filter"| retrieve
  catalog -->|"context-only facts"| retrieve
  retrieve -->|"local result"| eligible
  eligible -->|"yes"| request
  eligible -->|"no; no provider call"| fallback
  request -->|"bounded JSON"| route
  route -->|"yes"| preview
  route -->|"no; credential required"| api
  api -->|"untrusted output or failure"| recheck
  recheck -->|"current evidence and exact binding"| valid
  valid -->|"yes"| accepted
  valid -->|"no; reason retained"| fallback

  classDef sourceRole fill:#EAF3F8,stroke:#356079,stroke-width:1.5px,color:#111111
  classDef dataRole fill:#E5F4F2,stroke:#32746E,stroke-width:1.5px,color:#111111
  classDef analysisRole fill:#EDF0FA,stroke:#42558B,stroke-width:1.5px,color:#111111
  classDef policyRole fill:#F8F2E4,stroke:#876A2D,stroke-width:1.5px,color:#111111
  classDef humanRole fill:#EFF6EB,stroke:#4C713E,stroke-width:1.5px,color:#111111
  classDef evidenceRole fill:#F3F0F8,stroke:#6E5B85,stroke-width:1.5px,color:#111111
  class question humanRole
  class request sourceRole
  class recheck dataRole
  class retrieve,api analysisRole
  class eligible,route,valid policyRole
  class catalog,preview,accepted,fallback evidenceRole
  style local fill:none,stroke:#32746E,stroke-width:1.5px,color:#111111
  style provider fill:none,stroke:#42558B,stroke-width:1.5px,color:#111111
  style validation fill:none,stroke:#876A2D,stroke-width:1.5px,color:#111111
  linkStyle default stroke:#425466,stroke-width:1.5px
```

Color roles: blue/request data, teal/validation, indigo/retrieval and model adapter, gold/decision checks, green/user input, purple/evidence and responses. [Editable source](../diagrams/03-guarded-model-advice.mmd), [SVG](../diagrams/03-guarded-model-advice.svg), [PNG](../diagrams/03-guarded-model-advice.png). The provider receives no tools or execution endpoint. Application checks do not isolate the process from a user who controls its code or environment.

<a id="azure-batch-foundation"></a>

## Historical private Azure pilot

**Azure deployment retired; subscription retained.** ARCH-004 v0.4, 2026-10-16 UTC is the historical verified pilot and reference architecture. The foundation, managed Container Apps environment, job, registry image, storage objects, monitoring workspace and remaining Azure network resources have been removed from subscription ending `f609`. The earlier disposable operator VM/Bastion path was already removed. The subscription itself remains available. Local application and infrastructure code, the five original datasets, reviewed local image and downloaded verification evidence are preserved. This diagram does not describe a currently deployed service.

[Retirement verification](../../governance/azure-retirement-v0.4.json) at 2026-10-16 05:13:03 UTC recorded an enabled subscription, zero active resource groups/resources and zero project role assignments; the two subscription Owner assignments were unchanged. Azure recovery metadata still includes the deleted project storage account. Retirement describes active resources; it does not establish physical erasure of provider-retained data.

Before retirement, the reviewed platform manifest `sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad` was published without changing its OCI digest, and all five cloud input objects passed complete readback SHA-256 verification. [Image evidence](../image-security.md) records the exact local image, scan database and compatibility checks. The former job defaulted to `dataset-analysis`; synthetic demo, identity probe and expected configuration-failure tests used reviewed execution overrides through the [start helper](../../scripts/start_azure_pilot_test.ps1), without changing its template.

All four pilot modes were verified against ARM execution records and private artifacts or diagnostics before retirement. The synthetic demo passed five cases. Dataset analysis produced 154 facts and passed 12 advice cases and 20 qualification escalations. The identity probe passed nine checks, including a denied input write with `403 AuthorizationPermissionMismatch` and no unexpected input object. Its console row was unavailable; its persisted report was verified by hash and execution time. The configuration-failure execution failed as expected with the bounded `configuration_invalid` diagnostic. [Results](../results.md) record the preserved evidence, retirement verification and their limits. These remain bounded engineering checks; production acceptance and the qualification and assurance gates remain open.

```mermaid
%% ARCH-004 v0.4. Historical verified pilot; all deployed Azure resources retired.
%% Subscription and local code, originals, image and evidence are preserved.
%% Solid paths show historical runtime; dashed paths show historical transfer/access.
%% Reviewed platform digest: sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad
%%{init: {"theme":"base","look":"classic","themeVariables":{"fontFamily":"Arial, sans-serif","fontSize":"18px","primaryTextColor":"#111111","lineColor":"#425466","background":"transparent","edgeLabelBackground":"transparent","clusterBkg":"transparent"},"flowchart":{"htmlLabels":false,"curve":"basis","nodeSpacing":28,"rankSpacing":38,"padding":12},"themeCSS":"text { font-family:Arial,sans-serif !important; } .cluster-label text { font-size:16px !important; font-weight:600; }"}}%%
flowchart TB
  subgraph local["Preserved local pilot assets"]
    image["Preserved local image<br/>Historical scan: zero findings<br/>Platform: 99ae6d8...aabad"]
    datasets["Five local original datasets<br/>Preserved hashes and sizes"]
    operator["Historical pilot operations<br/>Code and helper preserved"]
  end

  subgraph access["Historical operator access - removed"]
    bastion["Bastion tunnel removed<br/>Pinned SSH/SCP used"]
    vm["Operator VM removed<br/>Former address: 10.43.0.4<br/>No VM public IP"]
    operatorIdentity["Operator identity removed<br/>Four scoped roles removed"]
  end

  subgraph azure["Historical Azure pilot - resources retired"]
    network["Former private endpoints and DNS<br/>Azure network resources removed"]
    registry[("Former private ACR<br/>Published OCI image removed")]
    inputs[("Former input Blob container<br/>Verified cloud copies removed")]
    identity["Former job identity<br/>AcrPull; input Blob Reader<br/>Output Blob Contributor"]
    job["Former Container Apps Job<br/>Internal environment<br/>Default: dataset-analysis<br/>One CPU; 2 GiB; no retries"]
    verify["Verify all five source identities<br/>Offline analysis; mock authority"]
    publish["Allowlisted run artifacts<br/>Write completion last"]
    outputs[("Former output Blob container<br/>Cloud artifacts removed")]
    monitor[("Former Azure Monitor<br/>Workspace removed")]
  end
  validation["Preserved local pilot evidence<br/>Artifact hashes and semantics<br/>Identity and failure checks"]

  image -.->|"reviewed archive transferred"| bastion
  datasets -.->|"five originals transferred"| bastion
  operator -.->|"retired authenticated tunnel"| bastion
  bastion -.->|"VM host key verified"| vm
  operatorIdentity -.->|"former ACR push; input write; output/log read"| vm
  vm -.->|"temporary 10.43.0.0/24 route removed"| network
  network -.->|"reviewed OCI publication"| registry
  network -.->|"hash-pinned uploads; no overwrite"| inputs
  operator -->|"manual start; fixed test overrides"| job
  identity -->|"verified scoped runtime access"| job
  registry -->|"private pull by immutable digest"| job
  job -->|"default dataset-analysis mode"| verify
  inputs -->|"private read; verify hashes and sizes"| verify
  verify -->|"summaries and bounded evidence"| publish
  publish -->|"unique prefix; no overwrite"| outputs
  job -->|"platform and console diagnostics"| monitor
  outputs -.->|"artifacts retrieved before retirement"| validation
  monitor -.->|"diagnostics retrieved before retirement"| validation

  classDef sourceRole fill:#EAF3F8,stroke:#356079,stroke-width:1.5px,color:#111111
  classDef dataRole fill:#E5F4F2,stroke:#32746E,stroke-width:1.5px,color:#111111
  classDef analysisRole fill:#EDF0FA,stroke:#42558B,stroke-width:1.5px,color:#111111
  classDef policyRole fill:#F8F2E4,stroke:#876A2D,stroke-width:1.5px,color:#111111
  classDef humanRole fill:#EFF6EB,stroke:#4C713E,stroke-width:1.5px,color:#111111
  classDef evidenceRole fill:#F3F0F8,stroke:#6E5B85,stroke-width:1.5px,color:#111111
  classDef securityRole fill:#FBEFED,stroke:#9B534C,stroke-width:1.5px,color:#111111
  class image,datasets,registry,inputs sourceRole
  class verify dataRole
  class job analysisRole
  class identity,operatorIdentity policyRole
  class operator,vm humanRole
  class publish,outputs,monitor,validation evidenceRole
  class bastion,network securityRole
  style local fill:none,stroke:#356079,stroke-width:1.5px,color:#111111
  style access fill:none,stroke:#4C713E,stroke-width:1.5px,stroke-dasharray:5 5,color:#111111
  style azure fill:none,stroke:#42558B,stroke-width:1.5px,stroke-dasharray:5 5,color:#111111
  style bastion stroke-dasharray:5 5
  style vm stroke-dasharray:5 5
  style operatorIdentity stroke-dasharray:5 5
  linkStyle default stroke:#425466,stroke-width:1.5px
```

**Color legend:** Blue - source datasets and image; Teal - input and analysis checks; Indigo - finite job runtime; Gold - identity and authorization; Green - historical pilot operations; Purple - artifacts and diagnostics; Rose - private access controls. [Editable source](../diagrams/04-azure-job.mmd), [SVG](../diagrams/04-azure-job.svg), [PNG](../diagrams/04-azure-job.png). All Azure components and connections are historical. Solid paths show the former runtime; dashed paths show the completed transfer and temporary access path. The local inputs, code and verification evidence remain preserved.

The former operator and job used distinct managed identities. The operator used four scoped assignments: AcrPush on the registry, Storage Blob Data Contributor on the input container, Storage Blob Data Reader on the output container, and Log Analytics Reader on the workspace. Reciprocal VNet peering and six additional private DNS links connected the operator VNet (`10.43.0.0/24`) with foundation services (`10.42.0.0/16`). The operator group, both peerings, six extra links and four assignments were removed during the earlier temporary-access cleanup. Subsequent retirement removed the foundation and remaining cloud resources. The [private access plan](../azure-private-access-plan.md) and [operator Bicep](../../infra/operator-subscription.bicep) preserve that historical disposable design.

The application has no model-inference or equipment interface in this job path. The former job identity had AcrPull on the registry, Storage Blob Data Reader on inputs, and Storage Blob Data Contributor on outputs. The contributor role included read and delete; application checks restricted this runner to allowlisted, create-only output artifacts. Source identity checks preceded offline analysis and completion was written last under a unique run prefix. Artifacts and private diagnostics were retrieved through the temporary operator and saved locally before the cloud resources were deleted. The former foundation VNet had no dedicated egress firewall.

Job-start permission was privileged and could permit template overrides; the retained helper accepts only four fixed pilot modes. The last helper refinement tightened the type check for Azure's optional ephemeral-storage field. It passed 61 offline mocked checks after the cloud runs and was not rerun in Azure; the preserved cloud execution records retain the earlier helper hash. A future deployment would require recreating and validating resources; the preserved IaC and this historical view do not imply a running service.
