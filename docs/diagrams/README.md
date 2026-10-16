# Architecture diagram sources and rendering

ARCH-001 v0.1, 2026-10-15: **AI Command Gateway — local data and authority boundaries**. This view explains read-only qualification of five supplied files, unqualified historical replay, deterministic checks, simulated human approval and a durable mock outcome. Its scope and limitations are in the [architecture index](../architecture/README.md).

Artifacts: [editable Mermaid](01-offline-authority.mmd), [SVG](01-offline-authority.svg), [PNG](01-offline-authority.png), [renderer configuration](mermaid-config.json) and [export script](render.mjs). The GitHub-rendered Mermaid in the architecture index must match the editable source. The export adds a title, status and visible color-role legend without changing topology.

The DME visual standard governs this view: transparent canvas/group backgrounds, squared component boxes, actual data-store cylinders, named groups, curved connectors, explicit authority and consistent role colors. The colors used are blue/source, teal/data, gold/policy, green/human and purple/evidence.

## Reproduce

The documentation renderer is optional and separate from the Python application's dependencies. The inspected local toolchain used Node 24.16.0, Mermaid CLI 12.0.0 and Puppeteer 25.14.0. Dependencies and browser downloads reside in ignored `.cache/` directories. From the repository root in PowerShell:

```powershell
$env:PUPPETEER_CACHE_DIR = Join-Path (Get-Location) '.cache\puppeteer'
npm install --prefix .cache/diagram-renderer --cache .cache/npm @mermaid-js/mermaid-cli@12.0.0 --no-audit --no-fund
node docs/diagrams/render.mjs
```

The export script renders Mermaid, wraps its SVG with metadata/legend, and exports PNG with a transparent background. A white inspection surface is saved only under ignored `.cache/`; it is not baked into the delivered SVG/PNG.

## Inspection

The source was accepted by the connected Mermaid renderer and rendered locally from the same source. The local preview was visually checked for readable labels, named-group clearance, authority flow, evidence linkage, consistent palette and visible legend. Export verification checks transparent corner alpha; the PNG color type and alpha are checked separately. The diagram is a design/implementation view, not evidence of equipment safety, domain acceptance or production deployment.

## Grounded observations view

ARCH-002 v0.1, 2026-10-15 covers typed catalog construction, verified local retrieval, exact citations/abstention and regression evidence. [Mermaid](02-grounded-advice.mmd), [SVG](02-grounded-advice.svg), [PNG](02-grounded-advice.png). Indigo identifies retrieval. The source is embedded verbatim in the architecture index. Render this view with `node docs/diagrams/render.mjs 02-grounded-advice`.

The local white-surface preview was inspected for label readability, group spacing, connector direction and visible legend. The delivered SVG/PNG retain a transparent canvas. No hosted model, operating recommendation or equipment connection is represented.

## Optional model adapter view

ARCH-003 v0.1, 2026-10-15 covers the explicit provider request, offline preview, local exact-claim validation and fallback/rejection. [Mermaid](03-guarded-model-advice.mmd), [SVG](03-guarded-model-advice.svg), [PNG](03-guarded-model-advice.png). Render with `node docs/diagrams/render.mjs 03-guarded-model-advice`. The light-surface preview was inspected and the delivered transparent exports measured 877 by 2807 pixels with corner alpha zero. Live provider behavior remains unverified.

## Azure job view

ARCH-004 v0.3, 2026-10-16 UTC shows the verified bounded pilot: the exact OCI image is published, all five original inputs passed complete hash readback, and demo, dataset, identity and expected-failure checks are verified. The job retains `dataset-analysis` as its default. The disposable operator VM/Bastion resource group, two peerings, six additional DNS links and four scoped operator roles have been removed. The foundation, job, image, five inputs and results are retained. Dashed paths show the completed, retired temporary publication and verification path. [Mermaid](04-azure-job.mmd), [SVG](04-azure-job.svg), [PNG](04-azure-job.png). Render with `node docs/diagrams/render.mjs 04-azure-job`. The light-surface preview was inspected for labeled connections, group placement and the seven-color legend. The exports retain a transparent canvas and unfilled groups. [Results](../results.md) record the cloud evidence and open production gates. The source matches the architecture index exactly.
