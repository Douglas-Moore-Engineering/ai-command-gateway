# Container image review - 2026-10-15

The current reviewed local image is **`sha256:e323bfcba037b00d0ac7ca409b0e8ba271e8a4cff2e492d3808e2157145a099e`**, tagged `ai-command-gateway:0.4.0-wolfi`. The unfiltered Trivy scan reports **zero findings across 34 OS and 34 Python packages**. The exact image passed **480 tests plus 44 subtests**, all five synthetic demo checks, and all 16 checks over the five supplied datasets. This record covers local remediation and verification; it does not record registry publication or Azure job execution.

The later approved pilot published these exact bytes to private ACR by the platform digest below and executed them successfully in Azure. [Current cloud results](results.md) and the pilot governance record carry that separate publication/runtime evidence; the captured local scan summary remains unchanged.

## Current runtime and evidence

The [Dockerfile](../Dockerfile) uses a digest-pinned Wolfi base and vendor-maintained Python 3.13.16 (`python-3.13-base=3.13.16_git20261009-r0`). Python 3.10 reached upstream end of life on October 1, 2026; Python 3.13 remains in security maintenance. The Wolfi package uses a pinned upstream maintenance commit plus explicit vendor patches, rather than claiming an unmodified python.org release. [Python lifecycle](https://devguide.python.org/versions/), [vendor build recipe](https://github.com/wolfi-dev/os/blob/main/python-3.13.yaml).

All 34 OS package versions are pinned in [wolfi-packages.lock](../containers/wolfi-packages.lock). APK verifies signed packages, and their downloaded SHA-256 values remain in `/opt/buildinfo/apk-sha256.txt`. The final image retains its actual APK and Python package metadata. The existing application and Azure dependency versions are unchanged; the image-specific [Python wheel lock](../containers/python-linux-amd64.lock) enforces exact Linux amd64/CPython 3.13 wheel hashes. Build reports remain under `/opt/buildinfo/`. Base digest pinning was verified; a Cosign signature check was not performed.

The minimal runtime uses patched `ncurses=6.6.20261010-r0` and `libuuid=2.42.4-r0`; the Debian util-linux command, systemd, Perl and ACL packages are absent. System timezone data (`tzdata=2026e-r0`) fixes the timestamp-conversion omission found by regression testing. No package metadata was removed to evade scanning, and no finding suppression or risk acceptance was applied.

Pip is not importable from the final virtual environment. The vendor Python package still requires a **pip 26.2.1 bootstrap wheel**, so this image does not claim that all installer code is absent. Direct archive inspection confirms patched msgpack 1.2.1 and urllib3 2.8.0. Its `setuptools==70.3.0` vendor label refers only to `pkg_resources`; the archive contains neither the affected `setuptools/package_index.py` nor setuptools distribution-building modules. This supplemental inventory supports the scope of the previous installer findings; it is not an exhaustive source audit. [PackageIndex advisory](https://github.com/pypa/setuptools/security/advisories/GHSA-5rjg-fvgr-3xxf), [distribution manifest advisory](https://github.com/pypa/setuptools/security/advisories/GHSA-h35f-9h28-mq5c).

Current raw evidence is in ignored `outputs/azure-image-scan-wolfi-final/`, including the unfiltered report, CycloneDX SBOM, package/import probe, bootstrap-wheel review and hash-bound `scan-summary.json`. Full regression evidence is `outputs/image-remediation/pytest-exact-image.xml`; [runtime checks](azure-runtime-checks.md) record the constrained dataset run. Historical images and raw reports remain available.

The scan used Trivy **0.76.0**, the same database snapshot updated **2026-10-15 at 19:09 UTC** used for the earlier comparison, local Docker lookup and offline dependency matching. All severities and unfixed findings were included. No image, source, dataset or SBOM was sent to a hosted scanner. Zero findings means no known vulnerabilities were reported by this scanner/database and detection scope; it does not establish that no vulnerabilities exist. Refresh the database and repeat the scan when the artifact or vulnerability evidence changes.

## Publish the reviewed bytes

The exact reviewed image was saved locally as `outputs/azure-pilot-transfer/image.tar`:

| Identity | Value |
| --- | --- |
| Archive bytes | 161,288,192 |
| Archive SHA-256 | `3cf028716ed9b32c2f7d8f86ccc6db2acdd72152164bb788adc6bc5c71a8250a` |
| Reviewed OCI platform manifest | `sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad` |
| Configuration digest | `sha256:8962dafbaf9b7555be34d1c9f503c31a55f4f868d4ea71d0dab6a575e8c697f0` |
| Platform / layers | Linux amd64 / 24 |

`image-identity.json` in the same directory records every ordered compressed-layer digest and uncompressed DiffID. All archive blob hashes, configuration hashes and DiffIDs were verified. The archive has exactly 31 unique members: the `blobs` directories, SHA-256-named regular blob files, `index.json`, `manifest.json` and `oci-layout`. No links, absolute paths, parent traversal or duplicate members were found.

After an authorized transfer, check the whole archive SHA-256 again before extraction. Extract into a new empty directory using an extractor that accepts only those exact member forms and regular files/directories, rejects links and traversal, and verifies every blob against its SHA-256 filename. Preserve the extracted OCI layout without modification. Run `crane push DIRECTORY ACR_REFERENCE` **without `--index`**, then verify the returned registry manifest digest equals the reviewed OCI platform digest above and that its configuration and ordered layer digests match `image-identity.json`. Deploy using that verified registry digest.

Crane 0.22.1 accepts an OCI-layout directory and preserves its image manifest. Passing the tar file directly uses Docker archive parsing, which can rewrite manifest media types and change the manifest digest even when configuration/layer bytes are unchanged. The directory procedure avoids that conversion. [Crane 0.22.1 implementation](https://github.com/google/go-containerregistry/blob/v0.22.1/cmd/crane/cmd/push.go).

## Historical Debian image review - superseded locally

The following preserved review describes the earlier Debian image and its unresolved findings at that time. It is not the current image gate result.

The final local image is `sha256:b2bc076451a10eb7708cdb4ed0127ab4243f7b09e8596ec661d7dd9efa3e6952`, tagged `ai-command-gateway:0.4.0-reviewed` for convenience. Its merged runtime contains the fixed Debian `liblzma5` package and no pip installer. **Image promotion remains unresolved:** 44 high-severity package mappings correspond to eight distinct Debian advisories without a stable fix in the captured database. None has been suppressed or accepted for production.

## Actual scan and remediation

| Local image | Total package/advisory occurrences | Critical | High | Medium | Low | Unknown | Fixed version available |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Initial `aabf26d5…` | 173 | 0 | 44 | 64 | 62 | 3 | 9 |
| Patched installer/compression library `92c9c164…` | 170 | 0 | 48 | 60 | 61 | 1 | 6 |
| Final runtime, installer removed `b2bc0764…` | 164 | 0 | 44 | 58 | 61 | 1 | 0 |

The nine initial fixable findings were seven pip advisories and two compression-library advisory mappings. The intermediate patched installer included an embedded component inventory that produced six additional detections. Removing the unused pip installer after building the application removed those detections from the final runtime. This removes actual installed code and metadata; it is not a scanner exclusion. Earlier image layers can retain the removed installer, so no all-layer erasure claim is made.

The final scan detected 87 Debian packages and 37 Python packages. All 164 remaining findings map to Debian packages; no findings were reported for the detected Python packages. A separate network-disabled, read-only probe confirmed pip cannot be imported and has no installed distribution or launchers. Azure identity and Blob SDK imports still succeed. The final image retains `liblzma5=5.8.1-1+deb13u2`, setuptools 84.0.0 and urllib3 2.8.0.

All three scans used **Trivy 0.76.0** and the same database, updated 2026-10-15 at 19:09 UTC. The scanner archive matched the official release checksum and GitHub asset digest. Analysis used local Docker lookup, offline dependency matching, disabled telemetry and no severity/unfixed exclusions. No image, source files, datasets or SBOM was uploaded by the scanner. [Official Trivy release](https://github.com/aquasecurity/trivy/releases/tag/v0.76.0), [offline scan documentation](https://trivy.dev/docs/latest/guide/advanced/air-gap/).

## Remaining high advisories

| Advisory | Debian source package | Package mappings | Current stable handling |
| --- | --- | ---: | --- |
| [CVE-2026-76642](https://security-tracker.debian.org/tracker/CVE-2026-76642) | util-linux | 9 | No stable fix; Debian marks minor issue/no DSA |
| [CVE-2026-78408](https://security-tracker.debian.org/tracker/CVE-2026-78408) | util-linux | 9 | No stable fix; minor issue/no DSA |
| [CVE-2026-78409](https://security-tracker.debian.org/tracker/CVE-2026-78409) | util-linux | 9 | No stable fix; minor issue/no DSA |
| [CVE-2026-78410](https://security-tracker.debian.org/tracker/CVE-2026-78410) | util-linux | 9 | No stable fix; minor issue/no DSA |
| [CVE-2026-54369](https://security-tracker.debian.org/tracker/CVE-2026-54369) | acl | 1 | Future point-release update; ABI change prevents isolated backport |
| [CVE-2025-69720](https://security-tracker.debian.org/tracker/CVE-2025-69720) | ncurses | 4 | No stable fix; minor issue/no DSA |
| [CVE-2026-16742](https://security-tracker.debian.org/tracker/CVE-2026-16742) | systemd | 2 | No stable fix; minor issue/no DSA |
| [CVE-2026-9538](https://security-tracker.debian.org/tracker/CVE-2026-9538) | perl | 1 | Postponed while upstream regressions are resolved |

Debian's stable-release disposition is not application-specific acceptance. Package matching alone does not establish vulnerable-code presence or reachability. Review the affected binaries and input paths, then either select a supported patched base or record an owned, time-limited disposition with a recheck date. No unstable Debian packages were mixed into this stable image to remove scanner findings.

## Evidence and scope

Raw reports, complete finding sets, SBOMs, comparisons and scanner/database hashes remain in ignored `outputs/azure-image-scan/`, `outputs/azure-image-scan-reviewed/` and `outputs/azure-image-scan-final/`. The final report SHA-256 is `efab41edbcf0447893b94ac6f8493befcb0e9347f0e67e808378d62002510c80`; the CycloneDX SBOM SHA-256 is `af1a1c140c54f8e8c96db0dc1700002e087aea03138116f04acc4e16bc739f75`.

This is package/database evidence, not a source-code audit, secret scan, exploitability assessment or production release approval. Foundation deployment does not publish or run this image. Before any later promotion, preserve the raw evidence bundle, refresh the scan and bind the reviewed artifact to the actual registry manifest digest. Rebuilding on a different host requires reviewing the resulting image separately.
