# Reproduce the constrained container check

The Azure job's initial 1 CPU/2 GiB configuration has been exercised locally against all five supplied datasets in the actual Linux image. The final image passed all 16 dataset checks in **81.363 seconds**, with **1,006,088,192 bytes (about 0.94 GiB)** of peak cgroup memory and no recorded out-of-memory event. This is a single local Blob-filesystem simulation under desktop load, not an Azure latency or capacity guarantee.

From the repository root, with Docker running and the reviewed image present:

```powershell
./scripts/test_azure_container.ps1 -InputDir "C:/Users/moore/Downloads" -Image sha256:b2bc076451a10eb7708cdb4ed0127ab4243f7b09e8596ec661d7dd9efa3e6952
```

The [PowerShell runner](../scripts/test_azure_container.ps1) resolves and records the image ID once and disables image pulls. It starts the exact image with `--network none`, a read-only root filesystem, one CPU, a 2-GiB memory limit and no swap. Only the five fixed source files and two verification scripts are mounted read-only; a fresh directory under ignored `outputs/azure-container-resources-reviewed/` receives evidence. No Azure service is contacted.

The [in-container probe](../scripts/verify_azure_container.py) checks the cgroup limits, UID 10001, read-only root and absence of a network interface other than loopback. It executes the existing [dataset verifier](../scripts/verify_azure_local.py), which blocks Azure SDK imports and socket operations while running the actual dataset-analysis code with filesystem Blob doubles. Source hashes, seven output artifact hashes, completion ordering, 12 advice cases and 20 durable qualification escalations are checked.

The host runner records the Docker command, image metadata, exit status, resource measurements and evidence hashes. A missing or failed report causes failure; a previous successful run is not reused. `summary.json` points to the latest run, while each run keeps its own directory. The final reviewed-image run ID was `41f1ece4-6055-48e9-8e1f-a612bf19351d`.

Actual Azure startup, transfer time, permissions, private DNS and logging still require cloud execution after image promotion and private connectivity are reviewed. A separate final-image probe confirmed Azure SDK imports and the compression-library fix; [image security](image-security.md) records unresolved findings. The application version remains 0.4.0; these changes concern container packaging and deployment readiness.
