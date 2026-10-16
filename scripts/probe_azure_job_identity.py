"""One-time, fixed-target Container Apps Job identity probe.

Execute only as the reviewed job identity. The probe creates two small output
blobs and attempts one create-only input blob that must be denied. It never
deletes blobs, prints tokens, provider messages, or downloaded dataset bytes.
Its source can be injected with python -c; it does not depend on __file__.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import logging
import socket
import uuid

from ai_command_gateway.evidence import PINNED_SOURCES


ACCOUNT_URL = "https://staicgsn5edmznrgh7s.blob.core.windows.net"
BLOB_HOST = "staicgsn5edmznrgh7s.blob.core.windows.net"
REGISTRY_HOST = "craicgsn5edmznrgh7s.azurecr.io"
CLIENT_ID = "9ff8b26e-c113-4fe3-80ef-bd0d3273d2c7"
PRIVATE_RANGE = ipaddress.ip_network("10.42.0.0/16")
PROBE_BYTES = b"AI Command Gateway managed identity validation; no dataset content.\n"
MAX_REPORT_BYTES = 32 * 1024
SAFE_ERROR_CODES = frozenset({
    "AuthorizationPermissionMismatch", "AuthorizationFailure", "AuthenticationFailed",
    "InvalidAuthenticationInfo", "BlobNotFound", "ContainerNotFound", "BlobAlreadyExists",
})


class ProbeFailure(Exception):
    """Fixed local diagnostics; never contains provider text."""


def _bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _provider_error(exc):
    from azure.core.exceptions import HttpResponseError

    status = getattr(exc, "status_code", None) if isinstance(exc, HttpResponseError) else None
    code = getattr(exc, "error_code", None) if isinstance(exc, HttpResponseError) else None
    code = getattr(code, "value", code)
    return {"http_status": status if type(status) is int and 100 <= status <= 599 else None,
            "service_error_code": code if type(code) is str and code in SAFE_ERROR_CODES else "unclassified"}


def _private_addresses(hostname, resolver):
    answers = resolver(hostname, 443, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
    if not 1 <= len(answers) <= 32:
        raise ProbeFailure("dns_response_invalid")
    addresses = sorted({str(ipaddress.ip_address(answer[4][0])) for answer in answers})
    if not addresses or any(ipaddress.ip_address(address) not in PRIVATE_RANGE for address in addresses):
        raise ProbeFailure("dns_not_exclusively_private")
    return addresses


def _client():
    from azure.identity import ManagedIdentityCredential
    from azure.storage.blob import BlobServiceClient

    identity = ManagedIdentityCredential(client_id=CLIENT_ID)
    try:
        service = BlobServiceClient(account_url=ACCOUNT_URL, credential=identity,
                                    max_single_get_size=4096, max_chunk_get_size=4096,
                                    connection_timeout=10, read_timeout=15, retry_total=0,
                                    logging_enable=False)
    except Exception:
        identity.close()
        raise
    return service, identity


def _download_exact(blob, length):
    # Each request is range-bound and accumulated only up to its declared size.
    received = bytearray()
    stream = blob.download_blob(offset=0, length=length, max_concurrency=1, timeout=15)
    for chunk in stream.chunks():
        if type(chunk) is not bytes or not chunk or len(received) + len(chunk) > length:
            raise ProbeFailure("range_read_invalid")
        received.extend(chunk)
    if len(received) != length:
        raise ProbeFailure("range_read_invalid")
    return bytes(received)


def _upload(blob, raw):
    blob.upload_blob(data=raw, overwrite=False, length=len(raw), max_concurrency=1, timeout=15)


def run_probe(*, service=None, resolver=socket.getaddrinfo, uuid_factory=uuid.uuid4, client_factory=_client):
    """Dependencies are injectable for offline tests; CLI accepts no targets."""
    probe_id = str(uuid_factory())
    if str(uuid.UUID(probe_id)) != probe_id:
        raise ProbeFailure("invalid_probe_id")
    report = {
        "schema_version": "1.0.0", "probe_id": probe_id,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "fixed-target private DNS and managed-identity Blob permission probe; not workload or domain acceptance",
        "client_id": CLIENT_ID, "storage_account_url": ACCOUNT_URL, "registry_hostname": REGISTRY_HOST,
        "expected_private_range": str(PRIVATE_RANGE), "checks": [],
        "input_write_probe_blob": f"validation-probe-{probe_id}.txt",
        "unexpected_input_blob_created": None, "input_write_creation_uncertain": False,
        "output_constant_blob": f"validation/{probe_id}/write-read.txt",
        "output_report_blob": f"validation/{probe_id}/identity-probe.json",
        "dataset_contents_logged": False, "full_source_hashes_verified": False,
        "registry_data_plane_authenticated": False, "deletions_performed": False,
        "all_probe_checks_passed": False,
    }
    envelope = {"status": "failed", "report_published": False, "report_sha256": None, "report": report}
    checks = report["checks"]

    for name, hostname in (("blob_private_dns", BLOB_HOST), ("registry_private_dns", REGISTRY_HOST)):
        try:
            addresses = _private_addresses(hostname, resolver)
            checks.append({"name": name, "passed": True, "addresses": addresses})
        except Exception as exc:
            code = str(exc) if isinstance(exc, ProbeFailure) else "dns_resolution_failed"
            checks.append({"name": name, "passed": False, "error_code": code})
    if not all(item["passed"] for item in checks):
        return envelope  # Do not contact storage when its private path is unresolved.

    identity, owns_client = None, service is None
    try:
        if owns_client:
            try:
                service, identity = client_factory()
            except Exception:
                checks.append({"name": "managed_identity_client", "passed": False, "error_code": "client_initialization_failed"})
                return envelope
        for filename, (_, _, size, _) in PINNED_SOURCES.items():
            check = {"name": "input_metadata_and_one_byte_read", "filename": filename, "expected_size_bytes": size,
                     "passed": False}
            try:
                blob = service.get_blob_client(container="inputs", blob=filename)
                observed = blob.get_blob_properties(timeout=15).size
                if type(observed) is not int or observed != size:
                    raise ProbeFailure("input_size_mismatch")
                _download_exact(blob, 1)  # Never retained in the report or printed.
                check.update(passed=True, observed_size_bytes=observed, bytes_read=1)
            except Exception as exc:
                check.update(error_code=str(exc) if isinstance(exc, ProbeFailure) else "input_read_failed",
                             **_provider_error(exc))
            checks.append(check)

        denied = {"name": "input_create_denied_by_permission", "passed": False}
        try:
            blob = service.get_blob_client(container="inputs", blob=report["input_write_probe_blob"])
            _upload(blob, PROBE_BYTES)
            report["unexpected_input_blob_created"] = report["input_write_probe_blob"]
            denied["error_code"] = "unexpected_input_write_success"
        except Exception as exc:
            safe = _provider_error(exc)
            denied.update(safe)
            denied["passed"] = safe == {"http_status": 403, "service_error_code": "AuthorizationPermissionMismatch"}
            if not denied["passed"]:
                denied["error_code"] = "input_write_denial_not_proven"
                # Transport failures can leave an acknowledged-by-server write uncertain.
                report["input_write_creation_uncertain"] = safe["http_status"] is None or safe["http_status"] >= 500
        checks.append(denied)

        output_check = {"name": "output_create_and_read", "passed": False}
        try:
            blob = service.get_blob_client(container="outputs", blob=report["output_constant_blob"])
            _upload(blob, PROBE_BYTES)
            if _download_exact(blob, len(PROBE_BYTES)) != PROBE_BYTES:
                raise ProbeFailure("output_readback_mismatch")
            output_check.update(passed=True, size_bytes=len(PROBE_BYTES), sha256=hashlib.sha256(PROBE_BYTES).hexdigest())
        except Exception as exc:
            output_check.update(error_code=str(exc) if isinstance(exc, ProbeFailure) else "output_write_or_read_failed",
                                **_provider_error(exc))
        checks.append(output_check)
        report["all_probe_checks_passed"] = all(check["passed"] for check in checks)
        raw = _bytes(report)
        if len(raw) > MAX_REPORT_BYTES:
            raise ProbeFailure("report_size_limit")
        envelope["report_sha256"] = hashlib.sha256(raw).hexdigest()
        try:
            blob = service.get_blob_client(container="outputs", blob=report["output_report_blob"])
            _upload(blob, raw)
            envelope["report_published"] = True
            envelope["status"] = "passed" if report["all_probe_checks_passed"] else "failed"
        except Exception as exc:
            envelope["report_publish_error"] = {"error_code": "report_upload_failed", **_provider_error(exc)}
        return envelope
    finally:
        if owns_client:
            for client in (service, identity):
                if client is not None:
                    try:
                        client.close()
                    except Exception:
                        pass


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    logger = logging.getLogger("azure")
    logger.handlers = [logging.NullHandler()]
    logger.propagate = False
    logger.setLevel(logging.CRITICAL)
    try:
        result = run_probe()
    except Exception:
        result = {"status": "failed", "report_published": False, "error_code": "probe_internal_failure"}
    print(_bytes(result).decode(), end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
