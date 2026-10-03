from __future__ import annotations

"""One continuous frozen-lower rollout per authored animation.

The cache is deliberately a dataset, not a collection of per-window warm
starts.  Every clip begins once at authored frame zero (duplicated previous and
current state), then the accepted frozen lower policy advances
autoregressively through the clip.  Cyclic clips continue far enough to serve
the longest upper-controller rollout; non-cyclic clips stop at their authored
end.
"""

import hashlib
from pathlib import Path
from typing import Any

import torch

try:
    from . import ik_core as tl
    from . import train_simple_ae_controller as lower_ctl
    from . import train_upper_pose_autoencoder as upper_data
    from . import train_upper_pose_controller as runtime_data
    from . import upper_pose_pelvis_contract as contract
except ImportError:
    import ik_core as tl
    import train_simple_ae_controller as lower_ctl
    import train_upper_pose_autoencoder as upper_data
    import train_upper_pose_controller as runtime_data
    import upper_pose_pelvis_contract as contract


CACHE_KIND = "upper_continuous_frozen_lower_dataset"
CACHE_VERSION = 1
DEFAULT_MAXIMUM_K = 32


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _clip_cache_length(clip: tl.MotionClip, maximum_k: int) -> int:
    if bool(clip.cyclic_animation):
        # Largest sampled start is period-1 and K32 needs that frame plus 32
        # successors.  The final tensor index is therefore period+31.
        return int(clip.cyclic_period) + int(maximum_k)
    return int(clip.T)


@torch.inference_mode()
def _rollout_one_clip(
    runtime: runtime_data.CategoryRuntime,
    clip_id: int,
    cache_length: int,
) -> torch.Tensor:
    """Run the accepted frozen policy once, beginning at authored frame zero."""

    runtime.install_policy()
    device = runtime.store.device
    clip_ids = torch.tensor([int(clip_id)], dtype=torch.long, device=device)
    frame_zero = torch.zeros(1, dtype=torch.long, device=device)
    current = runtime.store.get_target_output(clip_ids, frame_zero)
    previous = current.clone()
    payload = lower_ctl.payload_slice(runtime.store)
    previous_pelvis = previous[:, :3]
    current_pelvis = current[:, :3]
    previous_payload = previous[:, payload]
    current_payload = current[:, payload]
    rows = [current]
    for frame in range(max(0, int(cache_length) - 1)):
        index = torch.tensor([frame], dtype=torch.long, device=device)
        values = lower_ctl.build_controller_input(
            runtime.store,
            clip_ids,
            index,
            previous,
            current,
            previous_pelvis,
            current_pelvis,
            previous_payload,
            current_payload,
        )
        raw = lower_ctl.model_raw_output(
            runtime.model, values, current, runtime.store
        )
        transition = lower_ctl.clean_output_vector(
            raw, runtime.store, current, previous
        )
        following, following_pelvis, following_payload = (
            lower_ctl.advance_transition_state(
                runtime.store, clip_ids, index, transition
            )
        )
        rows.append(following)
        previous = current
        current = following
        previous_pelvis = current_pelvis
        current_pelvis = following_pelvis
        previous_payload = current_payload
        current_payload = following_payload
    result = torch.cat(rows, dim=0)
    if tuple(result.shape) != (int(cache_length), int(runtime.store.target_output.shape[-1])):
        raise RuntimeError(
            f"Continuous lower rollout shape changed: {tuple(result.shape)}"
        )
    if not bool(torch.isfinite(result).all()):
        raise RuntimeError(
            f"Continuous lower rollout is non-finite for {runtime.relatives[clip_id]}"
        )
    return result


@torch.inference_mode()
def _rollout_all_clips(
    runtime: runtime_data.CategoryRuntime,
    cache_lengths: list[int],
) -> list[torch.Tensor]:
    """Advance all independent clips in one row-wise-equivalent frame sweep."""

    runtime.install_policy()
    device = runtime.store.device
    clip_count = len(runtime.lower_clips)
    lengths = torch.tensor(cache_lengths, dtype=torch.long, device=device)
    maximum_length = int(lengths.max().item())
    clip_ids = torch.arange(clip_count, dtype=torch.long, device=device)
    zero = torch.zeros(clip_count, dtype=torch.long, device=device)
    current = runtime.store.get_target_output(clip_ids, zero)
    previous = current.clone()
    payload = lower_ctl.payload_slice(runtime.store)
    previous_pelvis = previous[:, :3]
    current_pelvis = current[:, :3]
    previous_payload = previous[:, payload]
    current_payload = current[:, payload]
    output = current.new_zeros(
        (clip_count, maximum_length, int(current.shape[-1]))
    )
    output[:, 0].copy_(current)
    for frame in range(maximum_length - 1):
        active = torch.nonzero(lengths > frame + 1, as_tuple=False).flatten()
        active_ids = clip_ids.index_select(0, active)
        index = torch.full_like(active_ids, frame)
        active_previous = previous.index_select(0, active)
        active_current = current.index_select(0, active)
        values = lower_ctl.build_controller_input(
            runtime.store,
            active_ids,
            index,
            active_previous,
            active_current,
            previous_pelvis.index_select(0, active),
            current_pelvis.index_select(0, active),
            previous_payload.index_select(0, active),
            current_payload.index_select(0, active),
        )
        raw = lower_ctl.model_raw_output(
            runtime.model, values, active_current, runtime.store
        )
        transition = lower_ctl.clean_output_vector(
            raw, runtime.store, active_current, active_previous
        )
        following, following_pelvis, following_payload = (
            lower_ctl.advance_transition_state(
                runtime.store, active_ids, index, transition
            )
        )
        output[:, frame + 1].index_copy_(0, active, following)
        previous = previous.index_copy(0, active, active_current)
        current = current.index_copy(0, active, following)
        previous_pelvis = previous_pelvis.index_copy(
            0, active, current_pelvis.index_select(0, active)
        )
        current_pelvis = current_pelvis.index_copy(0, active, following_pelvis)
        previous_payload = previous_payload.index_copy(
            0, active, current_payload.index_select(0, active)
        )
        current_payload = current_payload.index_copy(0, active, following_payload)
    return [
        output[clip_id, : int(cache_lengths[clip_id])].contiguous()
        for clip_id in range(clip_count)
    ]


@torch.inference_mode()
def build_category_cache(
    runtime: runtime_data.CategoryRuntime,
    checkpoint_path: Path,
    maximum_k: int = DEFAULT_MAXIMUM_K,
) -> dict[str, Any]:
    """Materialize the synthetic lower dataset for one lower policy."""

    runtime.store.prepare_root_state_cache(int(maximum_k))
    device = runtime.store.device
    offsets = [0]
    vectors: list[torch.Tensor] = []
    root_positions: list[torch.Tensor] = []
    root_rotations: list[torch.Tensor] = []
    headings: list[torch.Tensor] = []
    root_features: list[torch.Tensor] = []
    pelvis: list[torch.Tensor] = []
    feet: list[torch.Tensor] = []
    lower_positions: list[torch.Tensor] = []
    lower_rotations: list[torch.Tensor] = []
    bases: dict[float, list[torch.Tensor]] = {
        mode: [] for mode in runtime_data.MODE_ORDER
    }
    cache_lengths: list[int] = []

    cache_lengths = [
        _clip_cache_length(clip, int(maximum_k)) for clip in runtime.lower_clips
    ]
    rolled_vectors = _rollout_all_clips(runtime, cache_lengths)

    for clip_id, clip in enumerate(runtime.lower_clips):
        cache_length = cache_lengths[clip_id]
        vector = rolled_vectors[clip_id]
        indices = torch.arange(cache_length, dtype=torch.long, device=device)
        clip_ids = torch.full_like(indices, int(clip_id))
        root_position, root_rotation, heading = runtime_data.root_state(
            runtime, indices, clip_ids
        )
        pelvis_heading = runtime_data.pelvis_heading_features(
            vector, root_rotation, heading
        )
        foot_heading = runtime_data.foot_heading_features(
            runtime.store, vector, root_rotation, heading
        )
        pose, _ = tl.output_to_pose(vector, clip)
        positions, rotations, _ = tl.fk_from_pose(
            clip,
            root_position,
            root_rotation,
            pose,
            device,
        )
        by_name = {name: index for index, name in enumerate(clip.body_names)}
        selected_positions = torch.stack(
            [positions[:, by_name[name]] for name in contract.CACHED_LOWER_PHYSICAL_BONES],
            dim=1,
        )
        selected_rotations = torch.stack(
            [rotations[:, by_name[name]] for name in contract.CACHED_LOWER_PHYSICAL_BONES],
            dim=1,
        )
        for mode in runtime_data.MODE_ORDER:
            full_clip = runtime.full_clips_by_mode[mode][clip_id]
            rest = runtime.rest_offsets_by_mode[mode][clip_id]
            bases[mode].append(
                runtime_data.base_upper_from_lower(
                    vector,
                    root_position,
                    root_rotation,
                    heading,
                    full_clip,
                    rest,
                ).cpu()
            )
        vectors.append(vector.cpu())
        root_positions.append(root_position.cpu())
        root_rotations.append(root_rotation.cpu())
        headings.append(heading.cpu())
        root_features.append(
            runtime.store.get_input_root_features(clip_ids, indices).cpu()
        )
        pelvis.append(pelvis_heading.cpu())
        feet.append(foot_heading.cpu())
        lower_positions.append(selected_positions.cpu())
        lower_rotations.append(selected_rotations.cpu())
        offsets.append(offsets[-1] + cache_length)

    tensors = {
        "lower_vector": torch.cat(vectors, dim=0).contiguous(),
        "root_position": torch.cat(root_positions, dim=0).contiguous(),
        "root_rotation": torch.cat(root_rotations, dim=0).contiguous(),
        "heading": torch.cat(headings, dim=0).contiguous(),
        "root_features": torch.cat(root_features, dim=0).contiguous(),
        "pelvis_heading": torch.cat(pelvis, dim=0).contiguous(),
        "feet_heading": torch.cat(feet, dim=0).contiguous(),
        "cached_lower_position": torch.cat(lower_positions, dim=0).contiguous(),
        "cached_lower_rotation": torch.cat(lower_rotations, dim=0).contiguous(),
        "base_upper_sheathed": torch.cat(
            bases[runtime_data.MODE_SHEATHED], dim=0
        ).contiguous(),
        "base_upper_drawn": torch.cat(
            bases[runtime_data.MODE_DRAWN], dim=0
        ).contiguous(),
    }
    total = offsets[-1]
    for name, value in tensors.items():
        if int(value.shape[0]) != total or not bool(torch.isfinite(value).all()):
            raise RuntimeError(
                f"Cached tensor {name} failed: shape={tuple(value.shape)} total={total}"
            )
    return {
        "relatives": list(runtime.relatives),
        "clip_offsets": torch.tensor(offsets[:-1], dtype=torch.long),
        "cache_lengths": torch.tensor(cache_lengths, dtype=torch.long),
        "source_lengths": torch.tensor(
            [int(clip.T) for clip in runtime.lower_clips], dtype=torch.long
        ),
        "periods": torch.tensor(
            [int(clip.cyclic_period) for clip in runtime.lower_clips], dtype=torch.long
        ),
        "cyclic": torch.tensor(
            [bool(clip.cyclic_animation) for clip in runtime.lower_clips], dtype=torch.bool
        ),
        "lower_checkpoint": str(Path(checkpoint_path).resolve()),
        "lower_checkpoint_sha256": sha256_file(Path(checkpoint_path)),
        "initialization": "authored_frame_zero_duplicated_previous_current",
        "rollout": "one_continuous_autoregressive_pass_per_clip",
        "tensors": tensors,
    }


def save_cache(
    path: Path,
    categories: dict[str, dict[str, Any]],
    maximum_k: int = DEFAULT_MAXIMUM_K,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(
        {
            "kind": CACHE_KIND,
            "version": CACHE_VERSION,
            "maximum_k": int(maximum_k),
            "physical_lower_bones": list(contract.CACHED_LOWER_PHYSICAL_BONES),
            "categories": categories,
        },
        temporary,
    )
    temporary.replace(path)


class CachedLowerCategory:
    def __init__(
        self,
        payload: dict[str, Any],
        runtime: runtime_data.CategoryRuntime,
        checkpoint_path: Path,
        device: torch.device,
    ) -> None:
        cached_relatives = list(payload.get("relatives", []))
        try:
            source_ids = [cached_relatives.index(value) for value in runtime.relatives]
        except ValueError as exc:
            raise RuntimeError(
                "Runtime clip is absent from the continuous lower cache"
            ) from exc
        expected_sha = sha256_file(Path(checkpoint_path))
        if str(payload.get("lower_checkpoint_sha256", "")).upper() != expected_sha:
            raise RuntimeError(
                "Cached lower checkpoint SHA mismatch: "
                f"cache={payload.get('lower_checkpoint_sha256')} runtime={expected_sha}"
            )
        self.relatives = list(runtime.relatives)
        source_ids_tensor = torch.tensor(source_ids, dtype=torch.long)
        self.clip_offsets = payload["clip_offsets"].index_select(
            0, source_ids_tensor
        ).to(device=device)
        self.cache_lengths = payload["cache_lengths"].index_select(
            0, source_ids_tensor
        ).to(device=device)
        self.source_lengths = payload["source_lengths"].index_select(
            0, source_ids_tensor
        ).to(device=device)
        self.periods = payload["periods"].index_select(0, source_ids_tensor).to(
            device=device
        )
        self.cyclic = payload["cyclic"].index_select(0, source_ids_tensor).to(
            device=device
        )
        self.tensors = {
            name: value.to(device=device, dtype=torch.float32).contiguous()
            for name, value in dict(payload["tensors"]).items()
        }

    def frame_index(self, clip_ids: torch.Tensor, indices: torch.Tensor) -> torch.Tensor:
        clip_ids = clip_ids.long()
        indices = indices.long()
        return self.clip_offsets.index_select(0, clip_ids) + indices

    def gather(
        self, name: str, clip_ids: torch.Tensor, indices: torch.Tensor
    ) -> torch.Tensor:
        return self.tensors[name].index_select(0, self.frame_index(clip_ids, indices))

    def base_upper(
        self, mode: float, clip_ids: torch.Tensor, indices: torch.Tensor
    ) -> torch.Tensor:
        name = (
            "base_upper_drawn"
            if float(mode) == float(runtime_data.MODE_DRAWN)
            else "base_upper_sheathed"
        )
        return self.gather(name, clip_ids, indices)


def load_cache(
    path: Path,
    runtimes: dict[str, runtime_data.CategoryRuntime],
    checkpoint_paths: dict[str, Path],
    device: torch.device,
    maximum_k: int = DEFAULT_MAXIMUM_K,
) -> dict[str, CachedLowerCategory]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=False)
    if payload.get("kind") != CACHE_KIND or int(payload.get("version", -1)) != CACHE_VERSION:
        raise RuntimeError(f"Not a {CACHE_KIND} v{CACHE_VERSION} cache: {path}")
    if int(payload.get("maximum_k", -1)) < int(maximum_k):
        raise RuntimeError(
            f"Cached maximum K {payload.get('maximum_k')} is below {maximum_k}"
        )
    if list(payload.get("physical_lower_bones", [])) != list(
        contract.CACHED_LOWER_PHYSICAL_BONES
    ):
        raise RuntimeError("Cached lower physical-bone contract changed")
    categories = dict(payload.get("categories", {}))
    if set(categories) != set(runtimes):
        raise RuntimeError(
            f"Cached/runtime categories differ: {set(categories)} != {set(runtimes)}"
        )
    return {
        category: CachedLowerCategory(
            dict(categories[category]),
            runtime,
            Path(checkpoint_paths[category]),
            device,
        )
        for category, runtime in runtimes.items()
    }


def load_category(
    path: Path,
    category: str,
    runtime: runtime_data.CategoryRuntime,
    checkpoint_path: Path,
    device: torch.device,
    maximum_k: int = DEFAULT_MAXIMUM_K,
) -> CachedLowerCategory:
    """Load one category for the standalone viewer without the other policy."""

    payload = torch.load(Path(path), map_location="cpu", weights_only=False)
    if payload.get("kind") != CACHE_KIND or int(payload.get("version", -1)) != CACHE_VERSION:
        raise RuntimeError(f"Not a {CACHE_KIND} v{CACHE_VERSION} cache: {path}")
    if int(payload.get("maximum_k", -1)) < int(maximum_k):
        raise RuntimeError(
            f"Cached maximum K {payload.get('maximum_k')} is below {maximum_k}"
        )
    categories = dict(payload.get("categories", {}))
    if category not in categories:
        raise RuntimeError(f"Lower cache has no {category!r} category")
    return CachedLowerCategory(
        dict(categories[category]), runtime, Path(checkpoint_path), device
    )
