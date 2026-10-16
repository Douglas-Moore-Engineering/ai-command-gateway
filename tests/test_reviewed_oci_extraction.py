"""Focused extraction safety tests with tiny, explicitly pinned OCI fixtures."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_reviewed_oci.py"
spec = importlib.util.spec_from_file_location("reviewed_oci_extractor", SCRIPT)
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)


def encoded(value):
    return json.dumps(value, separators=(",", ":")).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    def build(*, rename=None, member_type=None, bad_blob=False, duplicate=False):
        layers, blobs = [], {}
        for position in range(24):
            raw = (f"synthetic layer {position}\n").encode()
            compressed = gzip.compress(raw, mtime=0)
            compressed_digest = digest(compressed)
            member = "blobs/sha256/" + compressed_digest[7:]
            blobs[member] = compressed
            layers.append({"position": position, "compressed_digest": compressed_digest,
                "docker_save_member": member, "size_bytes": len(compressed), "gzip_compressed": True,
                "diff_id": digest(raw), "oci_media_type": "application/vnd.oci.image.layer.v1.tar+gzip"})
        config = encoded({"architecture": "amd64", "os": "linux", "rootfs": {"type": "layers", "diff_ids": [layer["diff_id"] for layer in layers]}})
        config_digest = digest(config)
        blobs["blobs/sha256/" + config_digest[7:]] = config
        manifest = encoded({"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {"digest": config_digest, "size": len(config), "mediaType": "application/vnd.oci.image.config.v1+json"},
            "layers": [{"digest": layer["compressed_digest"], "size": layer["size_bytes"], "mediaType": layer["oci_media_type"]} for layer in layers]})
        manifest_digest = digest(manifest)
        blobs["blobs/sha256/" + manifest_digest[7:]] = manifest
        index = {"schemaVersion": 2, "mediaType": "application/vnd.oci.image.index.v1+json", "manifests": [{
            "digest": manifest_digest, "size": len(manifest), "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "platform": {"architecture": "amd64", "os": "linux"}}]}
        files = {**blobs, "index.json": encoded(index), "oci-layout": encoded({"imageLayoutVersion": "1.0.0"}),
                 "manifest.json": encoded([{"Config": "blobs/sha256/" + config_digest[7:], "Layers": [layer["docker_save_member"] for layer in layers]}])}
        if bad_blob:
            name = layers[0]["docker_save_member"]
            files[name] = b"x" * len(files[name])
        path = tmp_path / "image.tar"
        with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
            for name in ("blobs", "blobs/sha256"):
                item = tarfile.TarInfo(name)
                item.type = tarfile.DIRTYPE
                archive.addfile(item)
            for name, data in files.items():
                item = tarfile.TarInfo(rename if name == "oci-layout" and rename else name)
                item.size = len(data)
                if name == "oci-layout" and member_type:
                    item.type = member_type
                    item.size = 0
                archive.addfile(item, io.BytesIO(data) if item.type == tarfile.REGTYPE else None)
            if duplicate:
                item = tarfile.TarInfo("index.json")
                item.size = len(files["index.json"])
                archive.addfile(item, io.BytesIO(files["index.json"]))
        archive_bytes = path.read_bytes()
        identity = {"archive_sha256": hashlib.sha256(archive_bytes).hexdigest(), "archive_bytes": len(archive_bytes),
                    "platform_manifest_digest": manifest_digest, "configuration_digest": config_digest,
                    "platform": {"architecture": "amd64", "os": "linux"}, "archive_member_count": 31,
                    "layers": layers, "oci_index": index, "docker_save_config_member": "blobs/sha256/" + config_digest[7:]}
        identity_path = tmp_path / "image-identity.json"
        identity_raw = encoded(identity)
        identity_path.write_bytes(identity_raw)
        for name, value in {"ARCHIVE_SHA256": identity["archive_sha256"], "ARCHIVE_BYTES": len(archive_bytes),
                            "IDENTITY_SHA256": hashlib.sha256(identity_raw).hexdigest(),
                            "MANIFEST_DIGEST": manifest_digest, "CONFIG_DIGEST": config_digest}.items():
            monkeypatch.setattr(extractor, name, value)
        return path, identity_path, tmp_path / "new-layout"
    return build


def test_verified_layout_is_extracted_and_content_addressed(fixture):
    archive, identity, destination = fixture()
    report = extractor.extract_reviewed(archive, destination, identity)
    assert report["passed"] and report["member_count"] == 31 and report["layer_count"] == 24
    assert len(list(destination.rglob("*"))) == 31
    for blob in (destination / "blobs" / "sha256").iterdir():
        assert hashlib.sha256(blob.read_bytes()).hexdigest() == blob.name
    assert json.loads((destination / "index.json").read_text())["manifests"][0]["digest"] == report["platform_manifest_digest"]


def test_bad_archive_digest_creates_nothing(fixture):
    archive, identity, destination = fixture()
    raw = bytearray(archive.read_bytes())
    raw[1000] ^= 1
    archive.write_bytes(raw)
    with pytest.raises(extractor.ReviewError, match="archive_digest_mismatch"):
        extractor.extract_reviewed(archive, destination, identity)
    assert not destination.exists()


def test_bad_identity_digest_creates_nothing(fixture):
    archive, identity, destination = fixture()
    identity.write_bytes(identity.read_bytes() + b"\n")
    with pytest.raises(extractor.ReviewError, match="identity_digest_mismatch"):
        extractor.extract_reviewed(archive, destination, identity)
    assert not destination.exists()


@pytest.mark.parametrize("name", ["../escaped", "/absolute", "C:/drive", "blobs\\escaped"])
def test_unsafe_paths_are_rejected_even_if_archive_was_pinned(fixture, name):
    archive, identity, destination = fixture(rename=name)
    with pytest.raises(extractor.ReviewError, match="unsafe_member_path"):
        extractor.extract_reviewed(archive, destination, identity)
    assert not destination.exists()


@pytest.mark.parametrize("member_type", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE])
def test_link_and_special_file_types_are_never_extracted(fixture, member_type):
    archive, identity, destination = fixture(member_type=member_type)
    with pytest.raises(extractor.ReviewError, match="non_regular_member"):
        extractor.extract_reviewed(archive, destination, identity)
    assert not destination.exists()


def test_existing_empty_destination_is_refused(fixture):
    archive, identity, destination = fixture()
    destination.mkdir()
    with pytest.raises(extractor.ReviewError, match="destination_already_exists"):
        extractor.extract_reviewed(archive, destination, identity)
    assert list(destination.iterdir()) == []


def test_blob_hash_mismatch_is_caught_before_destination_creation(fixture):
    archive, identity, destination = fixture(bad_blob=True)
    with pytest.raises(extractor.ReviewError, match="blob_content_digest_mismatch"):
        extractor.extract_reviewed(archive, destination, identity)
    assert not destination.exists()


def test_duplicate_member_is_refused(fixture):
    archive, identity, destination = fixture(duplicate=True)
    with pytest.raises(extractor.ReviewError, match="archive_member_limit|unexpected_or_duplicate_member"):
        extractor.extract_reviewed(archive, destination, identity)
    assert not destination.exists()
