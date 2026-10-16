"""Fixed-project private operator transfers; Python standard library only.

Commands: preflight; publish --layout DIR --crane FILE --image-identity FILE;
upload-inputs --input-dir DIR --inventory FILE; download-run --run-id UUID
--mode demo|dataset-analysis --destination NEW_DIR. All require --client-id UUID
before the subcommand. No endpoint, container, repository or tag overrides.
query-logs --workspace-id UUID --execution-name job-aicg-sn5edmznrgh7s-SUFFIX [--table ContainerAppConsoleLogs]
reads only that execution's console records from the last 24 hours.

The helper does not build images or execute downloaded SQLite/archive content.
Blob writes use If-None-Match:*. ACR publication addresses the reviewed digest,
not a mutable tag. Failures can leave partial uploads/downloads; nothing is
automatically overwritten or deleted. Tokens and provider error bodies are not
printed. IMDS is direct, and TLS requests reject nonprivate peers and redirects.

Protocol references:
https://learn.microsoft.com/en-us/rest/api/storageservices/put-blob
https://github.com/Azure/acr/blob/main/docs/AAD-OAuth.md
https://github.com/google/go-containerregistry/blob/v0.22.1/cmd/crane/cmd/push.go
https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/containerappconsolelogs
https://learn.microsoft.com/en-us/azure/container-apps/log-monitoring
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile
import time
from urllib.parse import urlencode
import uuid


BLOB_HOST = "staicgsn5edmznrgh7s.blob.core.windows.net"
ACR_HOST = "craicgsn5edmznrgh7s.azurecr.io"
ACR_DATA_HOST = "craicgsn5edmznrgh7s.eastus2.data.azurecr.io"
LOG_HOST = "api.loganalytics.io"
PRIVATE_HOSTS = (BLOB_HOST, ACR_HOST, ACR_DATA_HOST, LOG_HOST)
PRIVATE_NETWORK = ipaddress.ip_network("10.42.0.0/16")
TENANT_ID = "add03129-5b4d-4ed0-96bc-bd56141358cd"
OPERATOR_CLIENT_ID = "3eb688bc-2d29-4776-8775-24b0410fd2eb"
PLATFORM_DIGEST = "sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad"
CRANE_SHA256 = "8e75c326adb43b053cfd78b9b987663f8f4fe4557f4d3915905643f25c730992"
IMAGE_IDENTITY_SHA256 = "49fade3d4ff5536f5980f067bbdfb1acf669e718f05adab5893369d03eb872ed"
INVENTORY_SHA256 = "3f26f0c1a3fd57ef5c58e4f63f535321fe2da504ba797de8bd0e1d6db31dbdde"
SOURCE_NAMES = {"logs_dataset.parquet", "packets_dataset.parquet", "process_dataset.parquet",
                "n76t439f65-1.zip", "doi-10.34810-data2936.zip"}
ARTIFACTS = {
    "demo": {"demo/demo-report.json", "demo/audit.sqlite3"},
    "dataset-analysis": {"profiles/profile-summary.json", "qualification/source-qualification.json",
        "advice/evidence-catalog.json", "advice/evidence-manifest.json", "advice/evidence-profile.json",
        "advice-evaluation/advice-evaluation.json", "replay/replay-summary.json"},
}
CHUNK = 1024 * 1024
MAX_ARTIFACT = 16 * CHUNK
MAX_TOTAL_ARTIFACTS = 64 * CHUNK
MAX_MANIFEST = 64 * 1024
STORAGE_RESOURCE = "https://storage.azure.com/"
ARM_RESOURCE = "https://management.azure.com/"
LOG_RESOURCE = "https://api.loganalytics.io"
MAX_LOG_RESPONSE = 16 * CHUNK
MAX_LOG_ROWS = 2000
LOG_COLUMNS = ("TimeGenerated", "SourceTable", "ContainerGroupName", "ReplicaName", "JobName", "Stream", "Log")
LOG_TABLES = ("ContainerAppConsoleLogs", "ContainerAppConsoleLogs_CL")


class TransferFailure(Exception):
    """Fixed diagnostic code and an optional HTTP status, never provider text."""

    def __init__(self, code, status=None):
        self.code, self.status = code, status
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise TransferFailure(code)


def canonical_uuid(value):
    require(type(value) is str and str(uuid.UUID(value)) == value, "invalid_uuid")
    return value


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def json_object(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def nonfinite(_):
        raise TransferFailure("invalid_json_number")

    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    require(type(result) is dict, "invalid_json_object")
    pending = [(result, 0)]
    while pending:
        value, depth = pending.pop()
        require(depth <= 32, "json_nesting_limit")
        if type(value) is float:
            require(math.isfinite(value), "invalid_json_number")
        if isinstance(value, dict):
            pending.extend((v, depth + 1) for v in value.values())
        elif isinstance(value, list):
            pending.extend((v, depth + 1) for v in value)
    return result


def safe_path(path):
    path = Path(path).absolute()
    require(".." not in path.parts, "unsafe_local_path")
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            require(not stat.S_ISLNK(info.st_mode)
                    and not getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT,
                    "linked_local_path")
    return path


def read_small(path, limit):
    path = safe_path(path)
    require(path.is_file() and 0 < path.stat().st_size <= limit, "invalid_local_file_size")
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    require(len(raw) <= limit, "local_file_size_limit")
    return raw


def hash_file(path, expected_size=None):
    path = safe_path(path)
    require(path.is_file(), "local_file_missing")
    if expected_size is not None:
        require(path.stat().st_size == expected_size, "local_file_size_mismatch")
    result, count = hashlib.sha256(), 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            count += len(block)
            require(count <= 512 * CHUNK, "local_file_size_limit")
            result.update(block)
    if expected_size is not None:
        require(count == expected_size, "local_file_size_mismatch")
    return result.hexdigest()


def preflight(resolver=socket.getaddrinfo):
    records = []
    for hostname in PRIVATE_HOSTS:
        answers = resolver(hostname, 443, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        require(0 < len(answers) <= 32, "dns_response_invalid")
        addresses = sorted({str(ipaddress.ip_address(answer[4][0])) for answer in answers})
        require(all(ipaddress.ip_address(address) in PRIVATE_NETWORK for address in addresses), "dns_not_private")
        records.append({"hostname": hostname, "addresses": addresses})
    return {"status": "passed", "scope": "DNS only; not effective permissions", "private_dns": records}


class Response:
    def __init__(self, connection, response):
        self.connection, self.response, self.status = connection, response, response.status

    def read(self, size):
        return self.response.read(size)

    def getheader(self, name):
        return self.response.getheader(name)

    def close(self):
        self.response.close()
        self.connection.close()


class Transport:
    """No proxy/environment URL handling and no redirects."""

    def request(self, method, hostname, path, headers=None, body=None):
        require(hostname in (*PRIVATE_HOSTS, "169.254.169.254"), "endpoint_not_allowed")
        require(path.startswith("/") and "\r" not in path and "\n" not in path, "request_path_invalid")
        local = hostname == "169.254.169.254"
        connection = (http.client.HTTPConnection if local else http.client.HTTPSConnection)(hostname, timeout=120)
        try:
            connection.connect()
            peer = ipaddress.ip_address(connection.sock.getpeername()[0])
            require(str(peer) == "169.254.169.254" if local else peer in PRIVATE_NETWORK, "connection_not_private")
            connection.request(method, path, body=body, headers=headers or {})
            return Response(connection, connection.getresponse())
        except Exception:
            connection.close()
            raise


def response_bytes(response, limit, statuses=(200,)):
    try:
        if response.status not in statuses:
            raise TransferFailure("http_request_failed", response.status)
        raw = response.read(limit + 1)
        require(len(raw) <= limit, "response_size_limit")
        return raw
    finally:
        response.close()


class Identity:
    def __init__(self, client_id, transport):
        self.client_id, self.transport, self.cache = canonical_uuid(client_id), transport, {}
        require(self.client_id == OPERATOR_CLIENT_ID, "operator_identity_mismatch")

    def token(self, resource):
        require(resource in (ARM_RESOURCE, STORAGE_RESOURCE, LOG_RESOURCE), "resource_not_allowed")
        cached = self.cache.get(resource)
        if cached and cached[1] > time.time() + 300:
            return cached[0]
        query = urlencode({"api-version": "2018-02-01", "resource": resource, "client_id": self.client_id})
        response = self.transport.request("GET", "169.254.169.254", "/metadata/identity/oauth2/token?" + query,
                                          {"Metadata": "true"})
        document = json_object(response_bytes(response, 128 * 1024))
        require(document.get("resource") == resource and document.get("token_type") == "Bearer", "identity_response_invalid")
        token = secret_token(document.get("access_token"))
        expires = int(document["expires_on"])
        require(expires > time.time() + 60, "identity_token_expired")
        self.cache[resource] = (token, expires)
        return token


def secret_token(value):
    require(type(value) is str and 0 < len(value) <= 64 * 1024
            and re.fullmatch(r"[A-Za-z0-9._~+-]+", value) is not None, "token_shape_invalid")
    return value


class Blob:
    def __init__(self, identity, transport):
        self.identity, self.transport = identity, transport

    def request(self, method, container, name, *, body=None, size=None):
        require(container in ("inputs", "outputs") and re.fullmatch(r"[A-Za-z0-9_./-]+", name) is not None
                and all(part not in ("", ".", "..") for part in name.split("/")), "blob_path_invalid")
        headers = {"Authorization": "Bearer " + self.identity.token(STORAGE_RESOURCE), "x-ms-version": "2023-11-03",
                   "x-ms-date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")}
        if method == "PUT":
            require(container == "inputs" and name in SOURCE_NAMES and type(size) is int and size > 0,
                    "blob_write_not_allowed")
            headers.update({"Content-Length": str(size), "x-ms-blob-type": "BlockBlob", "If-None-Match": "*"})
        else:
            require(method in ("GET", "HEAD"), "blob_method_not_allowed")
        return self.transport.request(method, BLOB_HOST, f"/{container}/{name}", headers, body)


def verify_stream(response, size, expected_digest, output=None):
    try:
        require(response.status == 200, "blob_read_failed")
        require(response.getheader("Content-Length") == str(size), "remote_size_mismatch")
        result, count = hashlib.sha256(), 0
        while True:
            block = response.read(min(CHUNK, size - count + 1))
            if not block:
                break
            count += len(block)
            require(count <= size, "remote_size_mismatch")
            result.update(block)
            if output is not None:
                output.write(block)
        require(count == size and result.hexdigest() == expected_digest, "remote_hash_mismatch")
    finally:
        response.close()


def source_inventory(path):
    raw = read_small(path, MAX_MANIFEST)
    require(digest(raw) == INVENTORY_SHA256, "inventory_hash_mismatch")
    items = json_object(raw).get("files")
    require(type(items) is list and len(items) == 5 and {item["filename"] for item in items} == SOURCE_NAMES,
            "inventory_names_mismatch")
    for item in items:
        require(type(item["size_bytes"]) is int and 0 < item["size_bytes"] < 256 * CHUNK
                and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None, "inventory_metadata_invalid")
    return items


def upload_inputs(input_dir, inventory_path, blob):
    sources = source_inventory(inventory_path)
    directory = safe_path(input_dir)
    # Finish all five local hashes before requesting a token or writing anything.
    for item in sources:
        require(hash_file(directory / item["filename"], item["size_bytes"]) == item["sha256"], "input_hash_mismatch")
    receipts = []
    for item in sources:
        name, size, checksum = item["filename"], item["size_bytes"], item["sha256"]
        response = blob.request("HEAD", "inputs", name)
        try:
            exists = response.status == 200
            require(exists or (response.status == 404 and response.getheader("x-ms-error-code") == "BlobNotFound"),
                    "input_metadata_request_failed")
            if exists:
                require(response.getheader("Content-Length") == str(size), "existing_input_size_mismatch")
        finally:
            response.close()
        if not exists:
            with (directory / name).open("rb") as source:
                response = blob.request("PUT", "inputs", name, body=source, size=size)
                try:
                    require(response.status in (201, 409, 412), "input_upload_failed")
                    operation = "created" if response.status == 201 else "concurrent_existing_verified"
                finally:
                    response.close()
        else:
            operation = "existing_verified"
        verify_stream(blob.request("GET", "inputs", name), size, checksum)
        receipts.append({"filename": name, "size_bytes": size, "sha256": checksum,
                         "operation": operation, "full_readback_verified": True})
    return {"status": "passed", "inventory_sha256": INVENTORY_SHA256, "inputs": receipts}


def download_run(run_id, mode, destination, blob):
    canonical_uuid(run_id)
    require(mode in ARTIFACTS, "invalid_mode")
    destination = safe_path(destination)
    require(not destination.exists() and destination.parent.is_dir(), "download_directory_must_be_new")
    prefix = f"runs/{run_id}/"
    raw = response_bytes(blob.request("GET", "outputs", prefix + "completion.json"), MAX_MANIFEST)
    manifest = json_object(raw)
    require(manifest.get("schema_version") == "1.0.0" and manifest.get("run_id") == run_id
            and manifest.get("mode") == mode and manifest.get("status") == "completed"
            and manifest.get("error_code") is None, "completion_binding_invalid")
    artifacts = manifest.get("artifacts")
    require(type(artifacts) is list and len(artifacts) == len(ARTIFACTS[mode]), "artifact_list_invalid")
    names, total = set(), 0
    for item in artifacts:
        require(type(item) is dict and set(item) == {"name", "size_bytes", "sha256"}
                and type(item["name"]) is str and item["name"] in ARTIFACTS[mode] and item["name"] not in names,
                "artifact_list_invalid")
        require(type(item["size_bytes"]) is int and 0 < item["size_bytes"] <= MAX_ARTIFACT
                and type(item["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None,
                "artifact_metadata_invalid")
        names.add(item["name"])
        total += item["size_bytes"]
    require(names == ARTIFACTS[mode] and total <= MAX_TOTAL_ARTIFACTS, "artifact_list_invalid")
    destination.mkdir(mode=0o700)
    for item in artifacts:
        path = destination / item["name"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as output:
            verify_stream(blob.request("GET", "outputs", prefix + item["name"]),
                          item["size_bytes"], item["sha256"], output)
    # A failed transfer leaves no local completion marker.
    with (destination / "completion.json").open("xb") as output:
        output.write(raw)
    return {"status": "passed", "run_id": run_id, "mode": mode, "directory": str(destination),
            "completion_sha256": digest(raw), "artifacts": artifacts, "server_prefix_enumerated": False,
            "semantic_results_verified": False, "arm_execution_success_verified": False}


def verify_layout(layout, identity_path):
    identity_raw = read_small(identity_path, MAX_MANIFEST)
    require(digest(identity_raw) == IMAGE_IDENTITY_SHA256, "image_identity_hash_mismatch")
    identity = json_object(identity_raw)
    require(identity["platform_manifest_digest"] == PLATFORM_DIGEST, "image_identity_digest_mismatch")
    layout = safe_path(layout)
    require(layout.is_dir(), "oci_layout_directory_required")
    require(json_object(read_small(layout / "oci-layout", 1024)) == {"imageLayoutVersion": "1.0.0"}, "oci_layout_invalid")
    index = json_object(read_small(layout / "index.json", MAX_MANIFEST))
    entries = index.get("manifests")
    require(index.get("schemaVersion") == 2 and type(entries) is list and len(entries) == 1
            and entries[0].get("digest") == PLATFORM_DIGEST
            and entries[0].get("mediaType") == "application/vnd.oci.image.manifest.v1+json", "oci_index_invalid")
    raw = read_small(layout / "blobs/sha256" / PLATFORM_DIGEST.split(":")[1], MAX_MANIFEST)
    require(digest(raw) == PLATFORM_DIGEST.split(":")[1], "oci_manifest_hash_mismatch")
    manifest = json_object(raw)
    require(manifest["config"]["digest"] == identity["configuration_digest"]
            and [layer["digest"] for layer in manifest["layers"]]
            == [layer["compressed_digest"] for layer in identity["layers"]], "oci_identity_mismatch")
    require(len(manifest["layers"]) <= 64, "oci_layer_limit")
    total = 0
    for item in [manifest["config"], *manifest["layers"]]:
        require(type(item["size"]) is int and 0 < item["size"] <= 512 * CHUNK
                and re.fullmatch(r"sha256:[0-9a-f]{64}", item["digest"]) is not None, "oci_descriptor_invalid")
        total += item["size"]
        require(total <= 512 * CHUNK, "oci_total_size_limit")
        require(hash_file(layout / "blobs/sha256" / item["digest"].split(":")[1], item["size"])
                == item["digest"].split(":")[1], "oci_blob_hash_mismatch")
    return {"platform_manifest_digest": PLATFORM_DIGEST, "configuration_digest": identity["configuration_digest"],
            "layer_count": len(manifest["layers"]), "referenced_bytes": total}


def crane_call(executable, arguments, environment, *, stdin=None, runner=subprocess.run):
    result = runner([str(executable), *arguments], input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=environment, timeout=1800, check=False)
    require(result.returncode == 0, "crane_command_failed")
    require(len(result.stdout) <= MAX_MANIFEST, "crane_output_limit")
    return result.stdout.decode("utf-8").strip()


def publish(layout, crane, identity_path, identity, transport, runner=subprocess.run):
    evidence = verify_layout(layout, identity_path)
    crane = safe_path(crane)
    require(hash_file(crane) == CRANE_SHA256, "crane_binary_hash_mismatch")
    with tempfile.TemporaryDirectory(prefix="aicg-crane-auth-") as temporary:
        environment = {"PATH": os.defpath, "HOME": temporary, "DOCKER_CONFIG": temporary}
        version = crane_call(crane, ["version"], environment, runner=runner)
        require(version in ("0.22.1", "v0.22.1"), "crane_version_mismatch")
        form = urlencode({"grant_type": "access_token", "service": ACR_HOST, "tenant": TENANT_ID,
                          "access_token": identity.token(ARM_RESOURCE)}).encode()
        response = transport.request("POST", ACR_HOST, "/oauth2/exchange",
                                     {"Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(form))}, form)
        refresh = secret_token(json_object(response_bytes(response, 128 * 1024)).get("refresh_token"))
        crane_call(crane, ["auth", "login", ACR_HOST, "--username", "00000000-0000-0000-0000-000000000000",
                           "--password-stdin"], environment, stdin=(refresh + "\n").encode(), runner=runner)
        reference = ACR_HOST + "/ai-command-gateway@" + PLATFORM_DIGEST
        crane_call(crane, ["push", str(safe_path(layout)), reference], environment, runner=runner)
        actual = crane_call(crane, ["digest", reference], environment, runner=runner)
        require(actual == PLATFORM_DIGEST, "published_digest_mismatch")
    return {"status": "passed", "registry_reference": reference, "registry_digest": actual,
            "crane_version": version, "crane_sha256": CRANE_SHA256, "image_identity_sha256": IMAGE_IDENTITY_SHA256,
            "local_image": evidence, "rebuilt": False, "mutable_tag_written": False}


def execution_name(value):
    require(type(value) is str and re.fullmatch(r"job-aicg-sn5edmznrgh7s-[a-z0-9]{1,32}", value) is not None,
            "execution_name_invalid")
    return value


def log_query(name, table=None):
    execution_name(name)
    require(table is None or (type(table) is str and table in LOG_TABLES), "log_table_invalid")
    # Both table names and all columns are fixed. Identifier validation makes
    # interpolation a literal name, never user-supplied KQL.
    source = ("union isfuzzy=true withsource=SourceTable " + ", ".join(LOG_TABLES) if table is None
              else f'{table}\n| extend SourceTable = "{table}"')
    return f'''let execution = "{name}";
{source}
| where TimeGenerated >= ago(24h)
| extend ContainerGroupName = coalesce(tostring(column_ifexists("ContainerGroupName", "")), tostring(column_ifexists("ContainerGroupName_s", "")), tostring(column_ifexists("ContainerGroupName_g", ""))),
         ReplicaName = coalesce(tostring(column_ifexists("ReplicaName", "")), tostring(column_ifexists("ReplicaName_s", ""))),
         JobName = coalesce(tostring(column_ifexists("JobName", "")), tostring(column_ifexists("JobName_s", "")))
| where ContainerGroupName == execution or ContainerGroupName startswith strcat(execution, "-")
     or ReplicaName == execution or ReplicaName startswith strcat(execution, "-") or JobName == execution
| project TimeGenerated, SourceTable, ContainerGroupName, ReplicaName, JobName,
          Stream = coalesce(tostring(column_ifexists("Stream", "")), tostring(column_ifexists("Stream_s", ""))),
          Log = coalesce(tostring(column_ifexists("Log", "")), tostring(column_ifexists("Log_s", "")))
| order by TimeGenerated asc
| take {MAX_LOG_ROWS}'''


def query_logs(workspace_id, name, identity, transport, table=None):
    canonical_uuid(workspace_id)
    query = log_query(name, table)
    raw = json.dumps({"query": query, "timespan": "P1D"}, allow_nan=False).encode()
    headers = {"Authorization": "Bearer " + identity.token(LOG_RESOURCE), "Content-Type": "application/json",
               "Content-Length": str(len(raw))}
    response = transport.request("POST", LOG_HOST, f"/v1/workspaces/{workspace_id}/query", headers, raw)
    response_raw = response_bytes(response, MAX_LOG_RESPONSE)
    document = json_object(response_raw)
    # A successful HTTP response can still contain a PartialError. Never print
    # provider error bodies or count partial results as completed verification.
    require(set(document) == {"tables"} and type(document["tables"]) is list and len(document["tables"]) == 1,
            "log_query_result_invalid_or_partial")
    result_table = document["tables"][0]
    require(type(result_table) is dict and result_table.get("name") == "PrimaryResult" and type(result_table.get("columns")) is list
            and [item.get("name") for item in result_table["columns"]] == list(LOG_COLUMNS)
            and type(result_table.get("rows")) is list and len(result_table["rows"]) <= MAX_LOG_ROWS, "log_query_schema_invalid")
    for row in result_table["rows"]:
        require(type(row) is list and len(row) == len(LOG_COLUMNS)
                and all(type(value) is str for value in row), "log_query_row_invalid")
        require(table is None or row[1] == table, "log_table_binding_mismatch")
        group, replica, job = row[2:5]
        require(group == name or group.startswith(name + "-") or replica == name
                or replica.startswith(name + "-") or job == name, "log_execution_binding_mismatch")
    return {"status": "passed", "scope": "bounded execution console query; not ARM execution or domain acceptance",
            "workspace_id": workspace_id, "execution_name": name, "table": table, "query": query,
            "query_sha256": digest(query.encode()), "response_sha256": digest(response_raw),
            "response_size_bytes": len(response_raw), "row_count": len(result_table["rows"]),
            "execution_logs_present": bool(result_table["rows"]), "arm_execution_success_verified": False,
            "row_limit": MAX_LOG_ROWS, "row_limit_reached": len(result_table["rows"]) == MAX_LOG_ROWS,
            "result": document}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    upload = commands.add_parser("upload-inputs")
    upload.add_argument("--input-dir", required=True, type=Path)
    upload.add_argument("--inventory", required=True, type=Path)
    download = commands.add_parser("download-run")
    download.add_argument("--run-id", required=True)
    download.add_argument("--mode", required=True, choices=sorted(ARTIFACTS))
    download.add_argument("--destination", required=True, type=Path)
    publication = commands.add_parser("publish")
    publication.add_argument("--layout", required=True, type=Path)
    publication.add_argument("--crane", required=True, type=Path)
    publication.add_argument("--image-identity", required=True, type=Path)
    logs = commands.add_parser("query-logs")
    logs.add_argument("--workspace-id", required=True)
    logs.add_argument("--execution-name", required=True)
    logs.add_argument("--table", choices=LOG_TABLES, help="Use the console table confirmed by workspace metadata; omitted uses the fixed union.")
    args = parser.parse_args(argv)
    try:
        canonical_uuid(args.client_id)
        require(args.client_id == OPERATOR_CLIENT_ID, "operator_identity_mismatch")
        dns = preflight()
        transport = Transport()
        identity = Identity(args.client_id, transport)
        if args.command == "preflight":
            result = dns
        elif args.command == "upload-inputs":
            result = upload_inputs(args.input_dir, args.inventory, Blob(identity, transport))
        elif args.command == "download-run":
            result = download_run(args.run_id, args.mode, args.destination, Blob(identity, transport))
        elif args.command == "query-logs":
            result = query_logs(args.workspace_id, args.execution_name, identity, transport, table=args.table)
        else:
            result = publish(args.layout, args.crane, args.image_identity, identity, transport)
        result.update(client_id=args.client_id, recorded_at_utc=datetime.now(timezone.utc).isoformat(),
                      operator_script_sha256=hash_file(Path(__file__)), private_dns=dns["private_dns"])
    except TransferFailure as exc:
        result = {"status": "failed", "error_code": exc.code, "http_status": exc.status,
                  "partial_transfers_may_remain": args.command in ("publish", "upload-inputs", "download-run")}
    except Exception:
        result = {"status": "failed", "error_code": "transfer_failed",
                  "partial_transfers_may_remain": args.command in ("publish", "upload-inputs", "download-run")}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
