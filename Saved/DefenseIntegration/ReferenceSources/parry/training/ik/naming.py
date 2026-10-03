from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path


STAMP_RE = re.compile(r"^\d{8}_\d{6}_(?:ik_)?")
MAX_IK_RUN_ID_CHARS = 80
RUN_ID_HASH_CHARS = 8


def clean_label(label: str) -> str:
    text = STAMP_RE.sub("", str(label).strip())
    text = text.replace("\\", "_").replace("/", "_").strip("_")
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    return text or "run"


def bounded_ik_label(label: str, prefix_chars: int) -> str:
    cleaned = clean_label(label)
    budget = max(1, int(MAX_IK_RUN_ID_CHARS) - int(prefix_chars))
    if len(cleaned) <= budget:
        return cleaned
    hash_chars = max(4, min(int(RUN_ID_HASH_CHARS), budget))
    digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:hash_chars]
    if budget <= hash_chars + 1:
        return digest[:budget]
    head = cleaned[: budget - hash_chars - 1].rstrip("_.-")
    return f"{head}_{digest}"


def ik_run_id(label: str, now: float | None = None) -> str:
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now or time.time()))
    prefix = f"{stamp}_ik_"
    return f"{prefix}{bounded_ik_label(label, len(prefix))}"


def checkpoint_path(run_dir: Path, run_id: str, tag: str) -> Path:
    if re.match(r"^t\d{4}_\d{6}_s\d+$", str(tag)):
        return run_dir / "checkpoints" / f"{tag}.pt"
    return run_dir / "checkpoints" / f"{run_id}_{tag}.pt"
