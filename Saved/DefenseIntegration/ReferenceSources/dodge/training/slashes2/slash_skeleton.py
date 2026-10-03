from __future__ import annotations

import numpy as np


# Slash controllers use a compact control skeleton. Keep the authored hand/foot
# end effectors, but drop visual/deformation/helper chains that are not part of
# the controller contract.
SLASH_PRUNE_EXACT_NAMES = ("attach",)
SLASH_PRUNE_PREFIXES = (
    "Locator",
    "ik_",
    "weapon_",
    "index_",
    "middle_",
    "pinky_",
    "ring_",
    "thumb_",
    "lowerarm_twist",
    "upperarm_twist",
    "calf_twist",
    "thigh_twist",
)


def keep_slash_source_bone(name: str) -> bool:
    text = str(name)
    if text in SLASH_PRUNE_EXACT_NAMES:
        return False
    return not any(text.startswith(prefix) for prefix in SLASH_PRUNE_PREFIXES)


def slash_runtime_exclude_prefixes() -> tuple[str, ...]:
    return SLASH_PRUNE_PREFIXES


def remap_pruned_parents(parents: np.ndarray, keep_indices: list[int]) -> np.ndarray:
    old_to_new = {old_index: new_index for new_index, old_index in enumerate(keep_indices)}
    remapped: list[int] = []
    for old_index in keep_indices:
        parent = int(parents[old_index])
        while parent >= 0 and parent not in old_to_new:
            parent = int(parents[parent])
        remapped.append(old_to_new[parent] if parent >= 0 else -1)
    return np.asarray(remapped, dtype=np.int32)


def prune_slash_bone_payload(payload: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], list[str]]:
    names = [str(name) for name in payload["bone_names"]]
    parents = np.asarray(payload["parents"], dtype=np.int32)
    keep = [index for index, name in enumerate(names) if keep_slash_source_bone(name)]
    removed = [name for index, name in enumerate(names) if index not in set(keep)]
    if len(keep) == len(names):
        return payload, []

    joint_count = len(names)
    pruned: dict[str, np.ndarray] = {}
    for key, value in payload.items():
        arr = np.asarray(value)
        if key == "bone_names":
            pruned[key] = arr[keep]
        elif key == "parents":
            pruned[key] = remap_pruned_parents(parents, keep)
        elif arr.ndim >= 1 and arr.shape[0] == joint_count:
            pruned[key] = arr[keep, ...]
        elif arr.ndim >= 2 and arr.shape[1] == joint_count:
            pruned[key] = arr[:, keep, ...]
        else:
            pruned[key] = arr
    return pruned, removed
