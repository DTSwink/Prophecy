"""Persistent-volume attestation and crash-safe publication, never in a CUDA step."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import uuid

STORAGE_SCHEMA = "slash2_persistent_checkpoint_storage_v1"
VOLUME_ID = "aj7d2jzwuq"
DEFAULT_ROOT = "/workspace/slash2/training_runs"


def validate_mount(row: dict, volume_id: str = VOLUME_ID) -> None:
    source = str(row.get("source", "")).rstrip("]")
    if (row.get("target") != "/workspace"
            or row.get("fstype") not in {"fuse", "fuse.mfs", "nfs", "nfs4"}
            or not source.endswith(f"/networkvolumes/{volume_id}")
            or "rw" not in str(row.get("options", "")).split(",")):
        raise RuntimeError(f"Refusing nonpersistent or wrong-volume storage: {row}")


def attest_persistent_paths(root: Path, paths: list[Path]) -> dict:
    root = root.resolve()
    workspace = Path("/workspace").resolve()
    if root == workspace or not root.is_relative_to(workspace):
        raise RuntimeError("Persistent run root must be strictly beneath /workspace")
    # Resolve every path before mkdir/open so symlinks cannot redirect saves to /tmp.
    resolved = [p.resolve() for p in paths]
    for path in [root, *resolved]:
        if path != root and not path.is_relative_to(root):
            raise RuntimeError(f"Artifact escapes persistent run root: {path}")
    for path in [root, *resolved]:
        probe = path
        while not probe.exists():
            probe = probe.parent
        mount = json.loads(subprocess.check_output(
            ["findmnt", "-J", "-T", str(probe)], text=True))["filesystems"][0]
        validate_mount(mount)
    return {"schema": STORAGE_SCHEMA, "root": str(root), "volumeId": VOLUME_ID,
            "mount": mount, "artifactPaths": [str(p) for p in resolved],
            "publish": "fsync_file_then_atomic_replace_then_fsync_directory"}


def enforce_checkpoint_path(path: Path) -> dict | None:
    root = os.environ.get("SLASH2_PERSISTENT_RUNS_ROOT")
    return attest_persistent_paths(Path(root), [path]) if root else None


def fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return  # Local Windows tools retain the atomic replace; production is Linux.
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_publish(temporary: Path, destination: Path) -> None:
    if temporary.parent.resolve() != destination.parent.resolve():
        raise ValueError("Atomic publication requires a same-directory temporary")
    with temporary.open("r+b") as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, destination)
    fsync_directory(destination.parent)


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    durable_publish(temporary, path)


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")
