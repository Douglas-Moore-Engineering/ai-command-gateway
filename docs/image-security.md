# Container image review - 2026-10-15

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
