# Reproduce the constrained container check

The current Wolfi/Python 3.13 image **`sha256:e323bfcba037b00d0ac7ca409b0e8ba271e8a4cff2e492d3808e2157145a099e`** passed **all 16 dataset checks in 95.08 seconds**, with **945,270,784 bytes (about 0.88 GiB)** of peak cgroup memory and no out-of-memory event. All five supplied datasets were processed in the actual Linux image at one CPU, 2 GiB and no swap. This is a local Blob-filesystem simulation under desktop load, not an Azure latency or capacity guarantee.

The exact image also passed **480 regression tests plus 44 subtests in 37.93 seconds**, with pytest and its dependencies mounted read-only, networking disabled and the runtime unchanged. All five synthetic allow/block/escalate/approval/replay checks passed. Azure identity and Blob SDK imports, scientific-library imports, UID 10001 and UTC timezone data passed a separate probe. The [image review](image-security.md) records the zero-finding package scan, exact provenance and its limits.

From the repository root, with Docker running and the reviewed image present:

```powershell
./scripts/test_azure_container.ps1 -InputDir "C:/Users/moore/Downloads" -Image sha256:e323bfcba037b00d0ac7ca409b0e8ba271e8a4cff2e492d3808e2157145a099e
```

The [PowerShell runner](../scripts/test_azure_container.ps1) resolves and records the image ID once and disables image pulls. It starts the exact image with `--network none`, a read-only root filesystem, one CPU, a 2-GiB memory limit and no swap. Only the five fixed source files and two verification scripts are mounted read-only; a fresh directory under ignored `outputs/azure-container-resources-reviewed/` receives evidence. No Azure service is contacted.

The [in-container probe](../scripts/verify_azure_container.py) checks the cgroup limits, UID 10001, read-only root and absence of a network interface other than loopback. It executes the existing [dataset verifier](../scripts/verify_azure_local.py), which blocks Azure SDK imports and socket operations while running the actual dataset-analysis code with filesystem Blob doubles. Source hashes, seven output artifact hashes, completion ordering, 12 advice cases and 20 durable qualification escalations are checked.

The host runner records the Docker command, image metadata, exit status, resource measurements and evidence hashes. A missing or failed report causes failure; a previous successful run is not reused. `summary.json` points to the latest run, while each run keeps its own directory. The current reviewed-image run ID is **`a09434e8-3685-43c4-8870-8ebc715bc930`**. Regression XML/logs are in `outputs/image-remediation/`; scan and import evidence is in `outputs/azure-image-scan-wolfi-final/`.

Subsequent approved Azure executions separately verified image pull, private DNS, managed-identity permissions, declared outputs and one failure path; see [current cloud results](results.md). These local records retain their filesystem-simulation scope and do not substitute for the cloud records. The application remains version 0.4.0, with unchanged scientific/Azure dependency versions and application source; the runtime moved from upstream-EOL Python 3.10 to vendor-maintained Python 3.13. Timezone data was added after regression testing found it missing from the minimal base.

## Historical Debian runtime check

The earlier image `sha256:b2bc076451a10eb7708cdb4ed0127ab4243f7b09e8596ec661d7dd9efa3e6952` passed 16 dataset checks in **81.363 seconds**, with **1,006,088,192 bytes (about 0.94 GiB)** of peak cgroup memory and no OOM event. That run remains under `outputs/azure-container-resources-reviewed/41f1ece4-6055-48e9-8e1f-a612bf19351d/`; its summary was preserved at `outputs/image-remediation/prior-container-summary.json`. These single runs are not a controlled performance comparison between the images.
