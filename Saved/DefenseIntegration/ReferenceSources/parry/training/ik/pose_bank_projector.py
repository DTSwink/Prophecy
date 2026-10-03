from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import numpy as np
import torch
import torch.nn as nn


ROOT_FUTURE_WINDOW = 8
NUM_BONES = 26
ROT6D_DIM = NUM_BONES * 6
ROOT_FEAT_DIM = 4
ROOT_WINDOW_DIM = ROOT_FUTURE_WINDOW * ROOT_FEAT_DIM
POSE_DIM = ROT6D_DIM + 3

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINT_DIR = PROJECT_ROOT / "training" / "runs" / "_ae4_pose_bank_projector" / "checkpoints"


class ClipArrays(NamedTuple):
    name: str
    local_rotation_6d: np.ndarray
    local_translation: np.ndarray
    local_matrix: np.ndarray
    global_joint_pos: np.ndarray
    global_matrix: np.ndarray
    parents: np.ndarray
    bone_names: np.ndarray
    fps: float


@dataclass
class DatasetStats:
    pose_mean: np.ndarray
    pose_std: np.ndarray
    root_mean: np.ndarray
    root_std: np.ndarray

    @classmethod
    def load(cls, path: Path) -> "DatasetStats":
        data = np.load(path)
        return cls(
            pose_mean=np.asarray(data["pose_mean"], dtype=np.float32),
            pose_std=np.asarray(data["pose_std"], dtype=np.float32),
            root_mean=np.asarray(data["root_mean"], dtype=np.float32),
            root_std=np.asarray(data["root_std"], dtype=np.float32),
        )


class RootConditionedPoseAE(nn.Module):
    def __init__(
        self,
        pose_dim: int = POSE_DIM,
        root_dim: int = ROOT_WINDOW_DIM,
        latent_dim: int = 64,
        hidden_dim: int = 256,
    ) -> None:
        super().__init__()
        self.pose_dim = int(pose_dim)
        self.root_dim = int(root_dim)
        self.latent_dim = int(latent_dim)

        self.encoder = nn.Sequential(
            nn.Linear(self.pose_dim + self.root_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, latent_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim + self.root_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, self.pose_dim),
        )

    def forward(self, pose: torch.Tensor, root_future: torch.Tensor) -> torch.Tensor:
        latent = self.encoder(torch.cat([pose, root_future], dim=-1))
        return self.decoder(torch.cat([latent, root_future], dim=-1))


def project_rotation_6d(rot6d: np.ndarray) -> np.ndarray:
    a1 = rot6d[..., :3]
    a2 = rot6d[..., 3:6]
    b1 = a1 / (np.linalg.norm(a1, axis=-1, keepdims=True) + 1.0e-8)
    b2 = a2 - np.sum(b1 * a2, axis=-1, keepdims=True) * b1
    b2 = b2 / (np.linalg.norm(b2, axis=-1, keepdims=True) + 1.0e-8)
    return np.concatenate([b1, b2], axis=-1).astype(np.float32)


def project_pose(pose_vector: np.ndarray) -> np.ndarray:
    out = np.asarray(pose_vector, dtype=np.float32).copy()
    if int(out.shape[-1]) < ROT6D_DIM:
        raise ValueError(f"pose vector last dim {int(out.shape[-1])} is smaller than rot payload {ROT6D_DIM}")
    lead_shape = out.shape[:-1]
    rot = out[..., :ROT6D_DIM].reshape(*lead_shape, NUM_BONES, 6)
    out[..., :ROT6D_DIM] = project_rotation_6d(rot).reshape(*lead_shape, ROT6D_DIM)
    return out.astype(np.float32, copy=False)


def rotation_6d_to_matrix(rot6d: np.ndarray) -> np.ndarray:
    rot6d = project_rotation_6d(rot6d)
    b1 = rot6d[..., :3]
    b2 = rot6d[..., 3:6]
    b3 = np.cross(b1, b2)
    return np.stack([b1, b2, b3], axis=-2).astype(np.float32)


def rotation_matrix_to_6d(rot: np.ndarray) -> np.ndarray:
    return np.asarray(rot, dtype=np.float32)[..., :2, :].reshape(*rot.shape[:-2], 6)


def normalize_pose(pose: np.ndarray, stats: DatasetStats) -> np.ndarray:
    return (pose - stats.pose_mean) / stats.pose_std


def denormalize_pose(pose: np.ndarray, stats: DatasetStats) -> np.ndarray:
    return pose * stats.pose_std + stats.pose_mean


def normalize_root(root: np.ndarray, stats: DatasetStats) -> np.ndarray:
    return (root - stats.root_mean) / stats.root_std


def yaw_from_matrix(rot: np.ndarray) -> float:
    return float(np.arctan2(rot[0, 2], rot[0, 0]))


def extract_pose_vector(local_rotation_6d: np.ndarray, local_translation: np.ndarray, frame: int) -> np.ndarray:
    rot = local_rotation_6d[frame].reshape(-1)
    pelvis_trans = local_translation[frame, 1]
    return np.concatenate([rot, pelvis_trans], axis=0).astype(np.float32)


def extract_root_future(
    global_matrix: np.ndarray,
    local_translation: np.ndarray,
    frame: int,
    window: int = ROOT_FUTURE_WINDOW,
) -> np.ndarray:
    total_frames = int(global_matrix.shape[0])
    root_rot0 = global_matrix[frame, 0, :3, :3]
    root_pos0 = local_translation[frame, 0].copy()
    yaw0 = yaw_from_matrix(root_rot0)
    feats: list[float] = []
    for step in range(1, window + 1):
        target_frame = min(frame + step, total_frames - 1)
        delta_world = local_translation[target_frame, 0] - root_pos0
        delta_local = root_rot0.T @ delta_world
        yaw_t = yaw_from_matrix(global_matrix[target_frame, 0, :3, :3])
        dyaw = (yaw_t - yaw0 + np.pi) % (2 * np.pi) - np.pi
        feats.extend([float(delta_local[0]), float(delta_local[1]), float(delta_local[2]), float(dyaw)])
    return np.asarray(feats, dtype=np.float32)


def load_clip(npz_path: Path) -> ClipArrays:
    data = np.load(npz_path, allow_pickle=True)
    return ClipArrays(
        name=npz_path.stem,
        local_rotation_6d=np.asarray(data["model_local_rotation_6d"], dtype=np.float32),
        local_translation=np.asarray(data["model_lcl_translation_m"], dtype=np.float32),
        local_matrix=np.asarray(data["model_local_matrix"], dtype=np.float32),
        global_joint_pos=np.asarray(data["model_global_joint_pos_m"], dtype=np.float32),
        global_matrix=np.asarray(data["model_global_matrix"], dtype=np.float32),
        parents=np.asarray(data["parents"], dtype=np.int32),
        bone_names=np.asarray(data["bone_names"]),
        fps=float(data["fps"]),
    )


def update_local_matrix_from_pose(
    base_local_matrix: np.ndarray,
    local_rotation_6d: np.ndarray,
    local_translation: np.ndarray,
) -> np.ndarray:
    out = np.asarray(base_local_matrix, dtype=np.float32).copy()
    out[:, :3, :3] = rotation_6d_to_matrix(local_rotation_6d)
    out[:, 3, :3] = local_translation
    return out


def forward_kinematics(local_matrices: np.ndarray, parents: np.ndarray) -> np.ndarray:
    global_mats = np.zeros_like(local_matrices, dtype=np.float32)
    for joint_index in range(int(local_matrices.shape[0])):
        parent = int(parents[joint_index])
        if parent < 0:
            global_mats[joint_index] = local_matrices[joint_index]
        else:
            global_mats[joint_index] = local_matrices[joint_index] @ global_mats[parent]
    return global_mats


def pose_vector_to_global_pose(clip: ClipArrays, frame: int, pose_vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    frame = max(0, min(int(frame), int(clip.local_rotation_6d.shape[0]) - 1))
    pose_vector = project_pose(pose_vector)
    local_rot6 = clip.local_rotation_6d[frame].copy()
    local_trans = clip.local_translation[frame].copy()
    local_rot6[:] = pose_vector[:ROT6D_DIM].reshape(NUM_BONES, 6)
    local_trans[1] = pose_vector[ROT6D_DIM : ROT6D_DIM + 3]
    local_mats = update_local_matrix_from_pose(clip.local_matrix[frame], local_rot6, local_trans)
    global_mats = forward_kinematics(local_mats, clip.parents)
    return global_mats[:, 3, :3].astype(np.float32), global_mats[:, :3, :3].astype(np.float32)


def pose_vector_from_global_pose(
    clip: ClipArrays,
    frame: int,
    positions: np.ndarray,
    rotations: np.ndarray,
    query_bone_names: list[str] | tuple[str, ...] | np.ndarray | None = None,
) -> np.ndarray:
    frame = max(0, min(int(frame), int(clip.local_rotation_6d.shape[0]) - 1))
    positions = np.asarray(positions, dtype=np.float32)
    rotations = np.asarray(rotations, dtype=np.float32)
    if query_bone_names is not None:
        query_names = [str(name) for name in query_bone_names]
        clip_names = [str(name) for name in clip.bone_names]
        if len(query_names) != int(positions.shape[0]) or len(query_names) != int(rotations.shape[0]):
            raise ValueError(
                f"query bone name count {len(query_names)} does not match pose shape "
                f"{positions.shape[0]}/{rotations.shape[0]}"
            )
        if query_names != clip_names:
            full_positions = clip.global_joint_pos[frame].astype(np.float32, copy=True)
            full_rotations = clip.global_matrix[frame, :, :3, :3].astype(np.float32, copy=True)
            query_by_name = {name: i for i, name in enumerate(query_names)}
            for clip_i, name in enumerate(clip_names):
                query_i = query_by_name.get(name)
                if query_i is None:
                    continue
                full_positions[clip_i] = positions[query_i]
                full_rotations[clip_i] = rotations[query_i]
            positions = full_positions
            rotations = full_rotations
    if int(positions.shape[0]) != NUM_BONES or int(rotations.shape[0]) != NUM_BONES:
        raise ValueError(f"expected {NUM_BONES} bones, got positions={positions.shape[0]} rotations={rotations.shape[0]}")
    local_rot = np.zeros((NUM_BONES, 3, 3), dtype=np.float32)
    for joint_index in range(NUM_BONES):
        parent = int(clip.parents[joint_index])
        if parent < 0:
            local_rot[joint_index] = rotations[joint_index]
        else:
            local_rot[joint_index] = rotations[joint_index] @ rotations[parent].T
    root_pos = positions[0]
    root_rot = rotations[0]
    pelvis_local = (positions[1] - root_pos) @ root_rot.T
    return np.concatenate([rotation_matrix_to_6d(local_rot).reshape(-1), pelvis_local], axis=0).astype(np.float32)


def load_pose_bank(path: Path) -> dict[str, np.ndarray]:
    data = np.load(path)
    return {
        "poses": np.asarray(data["poses"], dtype=np.float32),
        "roots": np.asarray(data["roots"], dtype=np.float32),
        "pose_norm": np.asarray(data["pose_norm"], dtype=np.float32),
        "root_norm": np.asarray(data["root_norm"], dtype=np.float32),
    }


def build_clip_pose_bank(clip: ClipArrays, stats: DatasetStats) -> dict[str, np.ndarray]:
    poses: list[np.ndarray] = []
    roots: list[np.ndarray] = []
    frames: list[int] = []
    total_frames = int(clip.local_rotation_6d.shape[0])
    for frame in range(total_frames):
        poses.append(extract_pose_vector(clip.local_rotation_6d, clip.local_translation, frame))
        roots.append(extract_root_future(clip.global_matrix, clip.local_translation, frame))
        frames.append(frame)
    pose_array = np.stack(poses, axis=0).astype(np.float32)
    root_array = np.stack(roots, axis=0).astype(np.float32)
    pose_norm = np.stack([normalize_pose(project_pose(pose), stats) for pose in pose_array], axis=0).astype(np.float32)
    root_norm = np.stack([normalize_root(root, stats) for root in root_array], axis=0).astype(np.float32)
    return {
        "poses": pose_array,
        "roots": root_array,
        "pose_norm": pose_norm,
        "root_norm": root_norm,
        "frames": np.asarray(frames, dtype=np.int32),
    }


def find_closest_dataset_pose(
    query_pose: np.ndarray,
    query_root: np.ndarray,
    bank: dict[str, np.ndarray],
    stats: DatasetStats,
    root_weight: float = 0.35,
) -> tuple[int, np.ndarray, float]:
    q_pose = normalize_pose(project_pose(query_pose), stats)
    q_root = normalize_root(query_root, stats)
    pose_d = np.sum((bank["pose_norm"] - q_pose) ** 2, axis=1)
    root_d = np.sum((bank["root_norm"] - q_root) ** 2, axis=1)
    dist = pose_d + float(root_weight) * root_d
    idx = int(np.argmin(dist))
    return idx, np.asarray(bank["poses"][idx], dtype=np.float32), float(dist[idx])


def find_closest_dataset_pose_batch(
    query_pose: np.ndarray,
    query_root: np.ndarray,
    bank: dict[str, np.ndarray],
    stats: DatasetStats,
    root_weight: float = 0.35,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    q_pose = normalize_pose(project_pose(query_pose), stats)
    q_root = normalize_root(query_root, stats)
    pose_d = np.sum((bank["pose_norm"][None, :, :] - q_pose[:, None, :]) ** 2, axis=-1)
    root_d = np.sum((bank["root_norm"][None, :, :] - q_root[:, None, :]) ** 2, axis=-1)
    dist = pose_d + float(root_weight) * root_d
    idx = np.argmin(dist, axis=1).astype(np.int32)
    rows = np.arange(int(idx.shape[0]), dtype=np.int32)
    poses = np.asarray(bank["poses"][idx], dtype=np.float32)
    distances = np.asarray(dist[rows, idx], dtype=np.float32)
    return idx, poses, distances


def pose_vectors_to_global_pose_batch(
    clip: ClipArrays,
    frames: np.ndarray,
    pose_vectors: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    frames = np.asarray(frames, dtype=np.int32).reshape(-1)
    pose_vectors = np.asarray(pose_vectors, dtype=np.float32)
    positions: list[np.ndarray] = []
    rotations: list[np.ndarray] = []
    for row_i, frame in enumerate(frames.tolist()):
        row_pos, row_rot = pose_vector_to_global_pose(clip, int(frame), pose_vectors[row_i])
        positions.append(row_pos)
        rotations.append(row_rot)
    return (
        np.stack(positions, axis=0).astype(np.float32, copy=False),
        np.stack(rotations, axis=0).astype(np.float32, copy=False),
    )


class PoseBankProjector:
    def __init__(self, checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR) -> None:
        checkpoint_dir = Path(checkpoint_dir)
        ckpt = torch.load(checkpoint_dir / "best_model.pt", map_location="cpu", weights_only=False)
        self.stats = DatasetStats.load(checkpoint_dir / "stats.npz")
        self.bank = load_pose_bank(checkpoint_dir / "pose_bank.npz")
        self.model = RootConditionedPoseAE(
            latent_dim=int(ckpt["latent_dim"]),
            hidden_dim=int(ckpt.get("hidden_dim", 256)),
        )
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval()
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)
        self.checkpoint_dir = checkpoint_dir
        self.clip_cache: dict[str, ClipArrays] = {}
        self.clip_bank_cache: dict[str, dict[str, np.ndarray]] = {}

    def clip(self, npz_path: Path) -> ClipArrays:
        path = Path(npz_path).resolve()
        key = str(path).lower()
        cached = self.clip_cache.get(key)
        if cached is None:
            cached = load_clip(path)
            self.clip_cache[key] = cached
        return cached

    def clip_pose_bank(self, npz_path: Path, clip: ClipArrays) -> dict[str, np.ndarray]:
        key = str(Path(npz_path).resolve()).lower()
        cached = self.clip_bank_cache.get(key)
        if cached is None:
            cached = build_clip_pose_bank(clip, self.stats)
            self.clip_bank_cache[key] = cached
        return cached

    @torch.no_grad()
    def reconstruct_pose(
        self,
        query_pose: np.ndarray,
        query_root: np.ndarray,
        source_bank: dict[str, np.ndarray] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, int, float, str, int | None]:
        pose_n = normalize_pose(project_pose(query_pose), self.stats)
        root_n = normalize_root(query_root, self.stats)
        pred_n = self.model(
            torch.from_numpy(pose_n).unsqueeze(0),
            torch.from_numpy(root_n).unsqueeze(0),
        ).squeeze(0).numpy()
        ae_pose = project_pose(denormalize_pose(pred_n, self.stats))
        lookup_bank = source_bank if source_bank is not None else self.bank
        bank_index, dataset_pose, bank_distance = find_closest_dataset_pose(
            ae_pose,
            query_root,
            lookup_bank,
            self.stats,
        )
        bank_source = "source" if source_bank is not None else "global"
        bank_frame: int | None = None
        if source_bank is not None:
            frames = source_bank.get("frames")
            if isinstance(frames, np.ndarray) and 0 <= bank_index < int(frames.shape[0]):
                bank_frame = int(frames[bank_index])
        return ae_pose, project_pose(dataset_pose), bank_index, bank_distance, bank_source, bank_frame

    @torch.no_grad()
    def reconstruct_pose_batch(
        self,
        query_pose: np.ndarray,
        query_root: np.ndarray,
        source_bank: dict[str, np.ndarray] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str, np.ndarray | None]:
        query_pose = np.asarray(query_pose, dtype=np.float32)
        query_root = np.asarray(query_root, dtype=np.float32)
        if query_pose.ndim != 2 or query_root.ndim != 2:
            raise ValueError(
                f"expected batched query pose/root arrays, got pose={query_pose.shape} root={query_root.shape}"
            )
        pose_n = normalize_pose(project_pose(query_pose), self.stats)
        root_n = normalize_root(query_root, self.stats)
        pred_n = self.model(
            torch.from_numpy(pose_n),
            torch.from_numpy(root_n),
        ).cpu().numpy()
        ae_pose = project_pose(denormalize_pose(pred_n, self.stats))
        lookup_bank = source_bank if source_bank is not None else self.bank
        bank_index, dataset_pose, bank_distance = find_closest_dataset_pose_batch(
            ae_pose,
            query_root,
            lookup_bank,
            self.stats,
        )
        bank_source = "source" if source_bank is not None else "global"
        bank_frames: np.ndarray | None = None
        if source_bank is not None:
            frames = source_bank.get("frames")
            if isinstance(frames, np.ndarray):
                bank_frames = np.asarray(frames[bank_index], dtype=np.int32)
        return ae_pose, project_pose(dataset_pose), bank_index, bank_distance, bank_source, bank_frames

    def project_frame(
        self,
        npz_path: Path,
        frame: int,
        query_positions: np.ndarray | None = None,
        query_rotations: np.ndarray | None = None,
        query_bone_names: list[str] | tuple[str, ...] | np.ndarray | None = None,
    ) -> dict[str, object]:
        clip = self.clip(npz_path)
        frame = max(0, min(int(frame), int(clip.local_rotation_6d.shape[0]) - 1))
        if query_positions is not None and query_rotations is not None:
            query_pose = pose_vector_from_global_pose(
                clip,
                frame,
                query_positions,
                query_rotations,
                query_bone_names=query_bone_names,
            )
        else:
            query_pose = extract_pose_vector(clip.local_rotation_6d, clip.local_translation, frame)
        source_bank = self.clip_pose_bank(npz_path, clip)
        query_root = extract_root_future(clip.global_matrix, clip.local_translation, frame)
        ae_pose, dataset_pose, bank_index, bank_distance, bank_source, bank_frame = self.reconstruct_pose(
            query_pose,
            query_root,
            source_bank=source_bank,
        )
        positions, rotations = pose_vector_to_global_pose(clip, frame, dataset_pose)
        ae_positions, ae_rotations = pose_vector_to_global_pose(clip, frame, ae_pose)
        gt_positions = clip.global_joint_pos[frame].astype(np.float32)
        err = float(np.sqrt(np.mean((positions - gt_positions) ** 2)))
        return {
            "pose": (positions, rotations),
            "ae_pose": (ae_positions, ae_rotations),
            "frame": frame,
            "bank_index": bank_index,
            "bank_source": bank_source,
            "bank_frame": bank_frame,
            "bank_distance": bank_distance,
            "rmse_m": err,
            "checkpoint_dir": str(self.checkpoint_dir),
            "bone_names": [str(name) for name in clip.bone_names],
        }

    def project_frames(
        self,
        npz_path: Path,
        frames: np.ndarray,
        query_positions: np.ndarray | None = None,
        query_rotations: np.ndarray | None = None,
        query_bone_names: list[str] | tuple[str, ...] | np.ndarray | None = None,
    ) -> dict[str, object]:
        clip = self.clip(npz_path)
        frames = np.asarray(frames, dtype=np.int32).reshape(-1)
        max_frame = int(clip.local_rotation_6d.shape[0]) - 1
        frames = np.clip(frames, 0, max_frame)
        if query_positions is not None and query_rotations is not None:
            query_positions = np.asarray(query_positions, dtype=np.float32)
            query_rotations = np.asarray(query_rotations, dtype=np.float32)
            query_pose = np.stack(
                [
                    pose_vector_from_global_pose(
                        clip,
                        int(frame),
                        query_positions[row_i],
                        query_rotations[row_i],
                        query_bone_names=query_bone_names,
                    )
                    for row_i, frame in enumerate(frames.tolist())
                ],
                axis=0,
            ).astype(np.float32, copy=False)
        else:
            query_pose = np.stack(
                [extract_pose_vector(clip.local_rotation_6d, clip.local_translation, int(frame)) for frame in frames.tolist()],
                axis=0,
            ).astype(np.float32, copy=False)
        source_bank = self.clip_pose_bank(npz_path, clip)
        query_root = np.asarray(source_bank["roots"][frames], dtype=np.float32)
        ae_pose, dataset_pose, bank_index, bank_distance, bank_source, bank_frame = self.reconstruct_pose_batch(
            query_pose,
            query_root,
            source_bank=source_bank,
        )
        positions, rotations = pose_vectors_to_global_pose_batch(clip, frames, dataset_pose)
        ae_positions, ae_rotations = pose_vectors_to_global_pose_batch(clip, frames, ae_pose)
        gt_positions = np.asarray(clip.global_joint_pos[frames], dtype=np.float32)
        err = np.sqrt(np.mean((positions - gt_positions) ** 2, axis=(1, 2))).astype(np.float32)
        return {
            "pose": (positions, rotations),
            "ae_pose": (ae_positions, ae_rotations),
            "frames": frames,
            "bank_index": bank_index,
            "bank_source": bank_source,
            "bank_frame": bank_frame,
            "bank_distance": bank_distance,
            "rmse_m": err,
            "checkpoint_dir": str(self.checkpoint_dir),
            "bone_names": [str(name) for name in clip.bone_names],
        }
