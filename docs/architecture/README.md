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

## Azure batch foundation

ARCH-004 v0.2, 2026-10-15. Approved private foundation scope with the prepared workload marked separately. The job is not provisioned; image publication and dataset uploads remain pending. Once separately enabled, the manual job defaults to the synthetic demo; dataset mode downloads and verifies all five source objects. [Current results](../results.md) record actual foundation deployment and configuration checks. Azure Blob and registry data paths use private endpoints; the job has no inference or equipment path. The VNet has no dedicated egress firewall. This view shows selected runtime relationships; [the implementation guide](../azure-implementation.md) and [Bicep](../../infra/README.md) cover the complete resource configuration.

```mermaid
%% Approved foundation scope. Dashed paths and the prepared workload remain pending.
%%{init: {"theme":"base","look":"classic","themeVariables":{"fontFamily":"Arial, sans-serif","fontSize":"18px","primaryTextColor":"#111111","lineColor":"#425466","background":"transparent","edgeLabelBackground":"transparent","clusterBkg":"transparent"},"flowchart":{"htmlLabels":false,"curve":"basis","nodeSpacing":28,"rankSpacing":38,"padding":12},"themeCSS":"text { font-family:Arial,sans-serif !important; } .cluster-label text { font-size:16px !important; font-weight:600; }"}}%%
flowchart TB
  subgraph preparation["Build and deployment preparation"]
    source["Reviewed runtime and pinned dependencies"]
    image["Local non-root image<br/>Promotion unresolved"]
    review["Explicit target and cost review<br/>Compile; scan; Azure what-if"]
  end

  subgraph azure["Approved Azure foundation"]
    registry[("Private container registry<br/>Publication pending")]
    inputs[("Private input Blob container<br/>Dataset upload pending")]
    outputs[("Private output Blob container<br/>Runtime artifacts pending")]
    monitor[("Private Azure Monitor scope<br/>Log Analytics workspace")]
    identity["User-assigned managed identity<br/>Scoped role assignments"]
    subgraph vnet["VNet and private endpoint DNS"]
      environment["Internal Container Apps environment"]
      subgraph future["Prepared workload - not provisioned"]
      job["Manual Container Apps Job<br/>Demo or dataset analysis"]
      verify["Verify input identities<br/>Run offline analysis"]
      publish["Allowlisted artifacts only<br/>Write completion last"]
      end
    end
  end
  operator["Authorized deployment and job operator"]

  source -->|"local image build"| image
  image -.->|"reviewed push from connected builder"| registry
  review -->|"approved foundation apply"| azure
  operator -.->|"privileged manual start"| job
  identity -.->|"AcrPull; input read; output write"| job
  registry -.->|"private image pull"| job
  job -.->|"selected mode"| verify
  inputs -.->|"managed identity over private endpoint"| verify
  verify -.->|"summary evidence; mock authority only"| publish
  publish -.->|"unique run prefix; no overwrite"| outputs
  job -.->|"platform and console diagnostics"| monitor

  classDef sourceRole fill:#EAF3F8,stroke:#356079,stroke-width:1.5px,color:#111111
  classDef dataRole fill:#E5F4F2,stroke:#32746E,stroke-width:1.5px,color:#111111
  classDef analysisRole fill:#EDF0FA,stroke:#42558B,stroke-width:1.5px,color:#111111
  classDef policyRole fill:#F8F2E4,stroke:#876A2D,stroke-width:1.5px,color:#111111
  classDef humanRole fill:#EFF6EB,stroke:#4C713E,stroke-width:1.5px,color:#111111
  classDef evidenceRole fill:#F3F0F8,stroke:#6E5B85,stroke-width:1.5px,color:#111111
  class source,image,registry,inputs sourceRole
  class verify dataRole
  class environment,job analysisRole
  class identity,review policyRole
  class operator humanRole
  class publish,outputs,monitor evidenceRole
  style preparation fill:none,stroke:#356079,stroke-width:1.5px,color:#111111
  style azure fill:none,stroke:#42558B,stroke-width:1.5px,color:#111111
  style vnet fill:none,stroke:#32746E,stroke-width:1.5px,color:#111111
  style future fill:none,stroke:#42558B,stroke-width:1.5px,stroke-dasharray:5 5,color:#111111
  environment -.->|"future host"| job
  linkStyle default stroke:#425466,stroke-width:1.5px
```

Color roles: blue/source and image, teal/validation, indigo/job, gold/identity and gates, green/operator, purple/evidence. [Editable source](../diagrams/04-azure-job.mmd), [SVG](../diagrams/04-azure-job.svg), [PNG](../diagrams/04-azure-job.png). Dashed connections describe pending publication and workload behavior. Private connectivity, image pull, identity data permissions and live diagnostics require runtime validation. Job-start permission is privileged and can permit template overrides.
