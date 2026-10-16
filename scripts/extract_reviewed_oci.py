#!/usr/bin/env python3
"""Extract only the exact reviewed pilot OCI archive, using the Python stdlib.

No Docker invocation, network access, archive permissions or layer extraction.
An unsuccessful run may leave its newly created destination; never publish it.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile


ARCHIVE_SHA256 = "3cf028716ed9b32c2f7d8f86ccc6db2acdd72152164bb788adc6bc5c71a8250a"
ARCHIVE_BYTES = 161288192
IDENTITY_SHA256 = "49fade3d4ff5536f5980f067bbdfb1acf669e718f05adab5893369d03eb872ed"
MANIFEST_DIGEST = "sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad"
CONFIG_DIGEST = "sha256:8962dafbaf9b7555be34d1c9f503c31a55f4f868d4ea71d0dab6a575e8c697f0"
MEMBER_COUNT = 31
LAYER_COUNT = 24
CHUNK = 1024 * 1024
MAX_JSON = 1024 * 1024
MAX_LAYER_UNCOMPRESSED = 1024 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ReviewError(ValueError):
    """The supplied bytes or destination differ from the reviewed transfer."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ReviewError(code)


def sha_stream(stream, *, maximum: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    while chunk := stream.read(CHUNK):
        count += len(chunk)
        require(count <= maximum, "stream_byte_limit")
        digest.update(chunk)
    return digest.hexdigest(), count


def blob_name(digest: str) -> str:
    require(isinstance(digest, str) and DIGEST_PATTERN.fullmatch(digest) is not None, "invalid_blob_digest")
    return "blobs/sha256/" + digest[7:]


def load_identity(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink(), "identity_not_regular_file")
    require(path.stat().st_size <= MAX_JSON, "identity_too_large")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == IDENTITY_SHA256, "identity_digest_mismatch")
    identity = json.loads(raw)
    require(isinstance(identity, dict), "identity_schema")
    require(identity["archive_sha256"] == ARCHIVE_SHA256 and identity["archive_bytes"] == ARCHIVE_BYTES, "identity_archive_mismatch")
    require(identity["platform_manifest_digest"] == MANIFEST_DIGEST and identity["configuration_digest"] == CONFIG_DIGEST, "identity_image_mismatch")
    require(identity["platform"] == {"architecture": "amd64", "os": "linux"}, "identity_platform_mismatch")
    require(identity["archive_member_count"] == MEMBER_COUNT and len(identity["layers"]) == LAYER_COUNT, "identity_count_mismatch")
    return identity


def checked_members(archive: tarfile.TarFile, identity: dict) -> dict[str, tarfile.TarInfo]:
    expected_blobs = {blob_name(MANIFEST_DIGEST), blob_name(CONFIG_DIGEST)}
    for position, layer in enumerate(identity["layers"]):
        require(layer["position"] == position, "identity_layer_order")
        member = blob_name(layer["compressed_digest"])
        require(layer["docker_save_member"] == member and member not in expected_blobs, "identity_layer_member")
        expected_blobs.add(member)
    expected = expected_blobs | {"blobs", "blobs/sha256", "index.json", "manifest.json", "oci-layout"}
    require(len(expected) == MEMBER_COUNT, "identity_unique_member_count")
    members = {}
    total = 0
    for member in archive:
        require(len(members) < MEMBER_COUNT, "archive_member_limit")
        name = member.name
        path = PurePosixPath(name)
        require(name and "\\" not in name and ":" not in name and not path.is_absolute()
                and all(part not in ("", ".", "..") for part in name.split("/"))
                and path.as_posix() == name, "unsafe_member_path")
        require(name in expected and name not in members, "unexpected_or_duplicate_member")
        require(not member.linkname and not member.pax_headers and not member.issparse(), "unsupported_member_metadata")
        if name in ("blobs", "blobs/sha256"):
            require(member.type == tarfile.DIRTYPE and member.size == 0, "invalid_directory_member")
        else:
            require(member.type == tarfile.REGTYPE, "non_regular_member")
            require(type(member.size) is int and 0 <= member.size <= ARCHIVE_BYTES, "member_byte_limit")
            if name in ("index.json", "manifest.json", "oci-layout", blob_name(CONFIG_DIGEST), blob_name(MANIFEST_DIGEST)):
                require(member.size <= MAX_JSON, "metadata_byte_limit")
            total += member.size
            require(total <= ARCHIVE_BYTES, "archive_payload_byte_limit")
        members[name] = member
    require(len(members) == MEMBER_COUNT and set(members) == expected, "archive_member_set_mismatch")
    return members


def read_json(archive, members, name):
    member = members[name]
    require(member.size <= MAX_JSON, "metadata_byte_limit")
    with archive.extractfile(member) as stream:
        raw = stream.read(MAX_JSON + 1)
    require(len(raw) == member.size and len(raw) <= MAX_JSON, "metadata_size_mismatch")
    return json.loads(raw)


def verify_layout(archive, members, identity) -> int:
    index = read_json(archive, members, "index.json")
    require(index == identity["oci_index"], "oci_index_mismatch")
    require(index["schemaVersion"] == 2 and index["mediaType"] == "application/vnd.oci.image.index.v1+json"
            and len(index["manifests"]) == 1, "oci_index_schema")
    descriptor = index["manifests"][0]
    require(descriptor["digest"] == MANIFEST_DIGEST and descriptor["platform"] == identity["platform"]
            and descriptor["mediaType"] == "application/vnd.oci.image.manifest.v1+json"
            and descriptor["size"] == members[blob_name(MANIFEST_DIGEST)].size, "manifest_descriptor_mismatch")
    manifest = read_json(archive, members, blob_name(MANIFEST_DIGEST))
    require(manifest["schemaVersion"] == 2 and manifest["mediaType"] == "application/vnd.oci.image.manifest.v1+json", "manifest_schema")
    require(manifest["config"]["digest"] == CONFIG_DIGEST
            and manifest["config"]["size"] == members[blob_name(CONFIG_DIGEST)].size
            and manifest["config"]["mediaType"] == "application/vnd.oci.image.config.v1+json", "configuration_descriptor_mismatch")
    require(len(manifest["layers"]) == LAYER_COUNT, "manifest_layer_count")
    for descriptor, layer in zip(manifest["layers"], identity["layers"]):
        require(descriptor["digest"] == layer["compressed_digest"]
                and descriptor["mediaType"] == layer["oci_media_type"] == "application/vnd.oci.image.layer.v1.tar+gzip"
                and descriptor["size"] == layer["size_bytes"] == members[layer["docker_save_member"]].size
                and layer["gzip_compressed"] is True, "layer_descriptor_mismatch")
    config = read_json(archive, members, blob_name(CONFIG_DIGEST))
    require(config["architecture"] == "amd64" and config["os"] == "linux"
            and config["rootfs"]["type"] == "layers"
            and config["rootfs"]["diff_ids"] == [layer["diff_id"] for layer in identity["layers"]], "configuration_layer_mismatch")
    require(read_json(archive, members, "oci-layout") == {"imageLayoutVersion": "1.0.0"}, "oci_layout_version")
    docker = read_json(archive, members, "manifest.json")
    require(isinstance(docker, list) and len(docker) == 1
            and docker[0]["Config"] == identity["docker_save_config_member"] == blob_name(CONFIG_DIGEST)
            and docker[0]["Layers"] == [layer["docker_save_member"] for layer in identity["layers"]], "docker_manifest_mismatch")

    # Validate all compressed blobs, including the configuration and manifest,
    # before creating the destination. Layer tar contents are never unpacked.
    for name, member in members.items():
        if name.startswith("blobs/sha256/"):
            with archive.extractfile(member) as stream:
                digest, size = sha_stream(stream, maximum=member.size)
            require(size == member.size and digest == name.rsplit("/", 1)[1], "blob_content_digest_mismatch")
    total_uncompressed = 0
    for layer in identity["layers"]:
        with archive.extractfile(members[layer["docker_save_member"]]) as compressed:
            with gzip.GzipFile(fileobj=compressed, mode="rb") as expanded:
                digest, size = sha_stream(expanded, maximum=min(MAX_LAYER_UNCOMPRESSED, MAX_TOTAL_UNCOMPRESSED - total_uncompressed))
        require("sha256:" + digest == layer["diff_id"], "layer_diff_id_mismatch")
        total_uncompressed += size
    return total_uncompressed


def extract_reviewed(archive_path: Path, destination: Path, identity_path: Path) -> dict:
    archive_path, destination, identity_path = map(Path, (archive_path, destination, identity_path))
    require(not os.path.lexists(destination), "destination_already_exists")
    require(destination.parent.is_dir() and not destination.parent.is_symlink(), "destination_parent_invalid")
    # Resolve the existing parent once, and create exactly one new child there.
    destination = destination.parent.resolve(strict=True) / destination.name
    require(not os.path.lexists(destination), "destination_already_exists")
    identity = load_identity(identity_path)
    require(archive_path.is_file() and not archive_path.is_symlink(), "archive_not_regular_file")
    with archive_path.open("rb") as source:
        initial = os.fstat(source.fileno())
        require(stat.S_ISREG(initial.st_mode) and initial.st_size == ARCHIVE_BYTES, "archive_size_mismatch")
        digest, size = sha_stream(source, maximum=ARCHIVE_BYTES)
        require(digest == ARCHIVE_SHA256 and size == ARCHIVE_BYTES, "archive_digest_mismatch")
        source.seek(0)
        with tarfile.open(fileobj=source, mode="r:") as archive:
            members = checked_members(archive, identity)
            uncompressed_bytes = verify_layout(archive, members, identity)
            destination.mkdir(mode=0o700, exist_ok=False)
            (destination / "blobs").mkdir(mode=0o700)
            (destination / "blobs" / "sha256").mkdir(mode=0o700)
            extracted_bytes = 0
            for name, member in members.items():
                if member.type == tarfile.DIRTYPE:
                    continue
                target = destination.joinpath(*PurePosixPath(name).parts)
                require(target.parent.resolve(strict=True).is_relative_to(destination), "destination_escape")
                remaining = member.size
                digest = hashlib.sha256()
                with archive.extractfile(member) as content, target.open("xb") as output:
                    while remaining:
                        chunk = content.read(min(CHUNK, remaining))
                        require(bool(chunk), "truncated_member")
                        output.write(chunk)
                        digest.update(chunk)
                        remaining -= len(chunk)
                        extracted_bytes += len(chunk)
                        require(extracted_bytes <= ARCHIVE_BYTES, "extraction_byte_limit")
                    require(content.read(1) == b"", "member_size_mismatch")
                target.chmod(0o600)
                if name.startswith("blobs/sha256/"):
                    require(digest.hexdigest() == name.rsplit("/", 1)[1], "extracted_blob_digest_mismatch")
        source.seek(0)
        final_digest, final_size = sha_stream(source, maximum=ARCHIVE_BYTES)
        final = os.fstat(source.fileno())
        require(final_digest == ARCHIVE_SHA256 and final_size == ARCHIVE_BYTES
                and (initial.st_size, initial.st_mtime_ns) == (final.st_size, final.st_mtime_ns), "archive_changed_during_extraction")
    return {"passed": True, "archive_sha256": ARCHIVE_SHA256, "archive_bytes": ARCHIVE_BYTES,
            "identity_sha256": IDENTITY_SHA256, "member_count": len(members), "regular_files": len(members) - 2,
            "extracted_bytes": extracted_bytes, "layer_count": LAYER_COUNT, "uncompressed_layer_bytes_verified": uncompressed_bytes,
            "platform_manifest_digest": MANIFEST_DIGEST, "configuration_digest": CONFIG_DIGEST,
            "destination": str(destination), "network_accessed": False, "image_published": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path, help="New directory; it must not already exist.")
    parser.add_argument("--identity", type=Path, help="Pinned image-identity.json, default beside archive.")
    args = parser.parse_args()
    try:
        result = extract_reviewed(args.archive, args.destination, args.identity or args.archive.parent / "image-identity.json")
    except (ReviewError, OSError, ValueError, KeyError, TypeError, tarfile.TarError, EOFError) as error:
        # Archive metadata or raw filesystem error strings are not reflected.
        code = str(error) if isinstance(error, ReviewError) else type(error).__name__
        print(json.dumps({"passed": False, "error_code": code, "image_published": False}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
