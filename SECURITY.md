# Security

Report suspected vulnerabilities privately to info@dmesystems.global. Do not include credentials, equipment identifiers or restricted records in public issues. No response-time commitment or continuous support is implied.

The v0.4 CLI stays offline by default. Explicit OpenAI advice sends only the selected observations and question to a fixed HTTPS endpoint. It exposes no tools or execution interface and reconstructs accepted citations locally. Azure batch code uses managed identity and container-scoped Blob permissions. Local tests and infrastructure validation do not establish deployed isolation. [Threats and trust boundaries](docs/implementation-baseline.md) describe remaining gaps.

Local actor strings are not authenticated identity; state is supplied by the caller. OS access to policy/database files controls this demonstration's boundary. SQLite audit is durable local evidence, not a signed or tamper-proof ledger. The local core is not an isolation sandbox. No security certification, comprehensive penetration test, independent assessment or production authorization is claimed.

Raw dataset/archive text is untrusted. Ingestion does not execute scripts or extract member paths. Source metadata and attack labels never authorize policy changes or equipment actions. The model adapter accepts only exact retrieved claims; malformed responses, provider failures and catalog changes have explicit fallback or rejection outcomes. No model-produced prose enters an execution path.

Azure jobs have no application ingress. A principal allowed to start a Container Apps Job can override its execution template and use its managed identity; treat that principal as a privileged data operator, not as an authenticated gateway approver. The initial job contains no provider key and performs no hosted inference. See [Azure implementation](docs/azure-implementation.md) for network, image, storage and remaining deployment checks. [Microsoft job permissions](https://learn.microsoft.com/en-us/azure/container-apps/jobs#permissions)
