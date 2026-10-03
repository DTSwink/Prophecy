"""Compact reconstruction labels and the learned dodge input contract.

No global/body duplicate, shifted fake root, attacker skeleton, unused attack
slot, per-frame type repetition, or repeated hit masks are stored.
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
SCHEMA = "defense_imitation_root_relative_v3"
ATTACK_LABEL_NAMES = ("attack_angle", "is_pike", "is_melee", "is_kick", "is_headbutt", "is_spear")
ATTACK_INPUT_DIM = 9  # Sticky target3 + canonical attack controls6.
LEGACY_KEYS = {"time", "root", "body", "attack", "attack_half", "target", "attack_type", "hit_time", "carrier_command"}
PRE_PIN_KEYS = LEGACY_KEYS | {"attacker_pelvis", "root_tail"}
KEYS = PRE_PIN_KEYS | {"pin"}
FUTURE_WINDOW = 8
PIN_SLIDE_DISTANCE_THRESHOLD_M = 0.0115
PIN_BODY_INDICES = (19, 20, 23, 24)  # foot_l, ball_l, foot_r, ball_r


def attack_labels(name: str) -> np.ndarray:
    if name.lower() == "spear":
        return np.array([0, 0, 0, 0, 0, 1], np.float32)
    if str(HERE.parent) not in sys.path:
        sys.path.insert(0, str(HERE.parent))
    from ae4_pose_prior import attack_labels as legacy_labels
    return np.array([*legacy_labels(name), 0], np.float32)


def matrices_from_rot6(values: np.ndarray) -> np.ndarray:
    first = values[..., :3]
    second = values[..., 3:6]
    # Keep the native first two axes, including their tiny floating-point
    # nonorthogonality; only the omitted third axis is reconstructed.
    return np.stack((first, second, np.cross(first, second)), axis=-2)


def pin_labels_from_world(
    body_positions: np.ndarray,
    body_rotations: np.ndarray,
) -> np.ndarray:
    """Exact old AE3 pin detector, aligned as frame t -> frame t+1.

    The detector is intentionally horizontal-only and has no ground-height
    gate, matching the accepted Slash2 label source without reinterpretation.
    """

    import torch
    ik_root = HERE.parents[1] / "ik"
    if str(ik_root) not in sys.path:
        sys.path.insert(0, str(ik_root))
    import contact_physics as cp

    positions = torch.as_tensor(np.asarray(body_positions), dtype=torch.float64)
    rotations = torch.as_tensor(np.asarray(body_rotations), dtype=torch.float64)
    if (
        positions.ndim != 3
        or positions.shape[-1] != 3
        or rotations.shape != (*positions.shape[:2], 3, 3)
        or positions.shape[1] <= max(PIN_BODY_INDICES)
    ):
        raise ValueError("Pin labels require complete world body transforms")
    result = np.zeros((positions.shape[0], 2), dtype=np.uint8)
    if positions.shape[0] < 2:
        return result
    geometry = cp.ContactGeometryConfig(
        foot_length=0.175,
        foot_width=0.120,
        foot_height=0.051,
        toe_length=0.048,
        toe_width=0.120,
        toe_height=0.049,
        sole_vertical_offset=-0.006,
        ground_y=0.0,
        height_threshold_m=0.025,
        speed_threshold_mps=0.350,
    )
    speed = cp.foot_slide_speeds(
        positions[:-1], rotations[:-1], positions[1:], rotations[1:],
        (PIN_BODY_INDICES[0], PIN_BODY_INDICES[2]),
        (PIN_BODY_INDICES[1], PIN_BODY_INDICES[3]),
        30.0,
        geometry,
    )
    result[:-1] = (
        speed / 30.0 <= PIN_SLIDE_DISTANCE_THRESHOLD_M
    ).to(torch.uint8).cpu().numpy()
    return result


def pack_motion(raw: dict, attack_name: str, preview: dict, *, root_tail, labels=None, com_weights=None) -> dict[str, np.ndarray]:
    if com_weights is not None:
        from imitation_com_root import rebase_raw_com
        raw, root_tail = rebase_raw_com(raw, root_tail, com_weights)
    positions = np.asarray(raw["poses"], np.float64)
    rotations = np.asarray(raw["axes"], np.float64)
    root_pos = np.asarray(raw["roots"], np.float64)
    root_rot = np.asarray(raw["rootAxes"], np.float64)
    inverse = np.linalg.inv(root_rot)
    # Row-axis convention: world = root_position + local @ root_rotation.
    body_pos = np.einsum("fbi,fij->fbj", positions[:, 1:] - root_pos[:, None], inverse)
    body_rot = rotations[:, 1:] @ inverse[:, None]
    attack_pos = np.einsum("fi,fij->fj", np.asarray(raw["attacks"]) - root_pos, inverse)
    attack_rot = np.asarray(raw["attackAxes"]) @ inverse
    pelvis_pos = np.einsum("fi,fij->fj", np.asarray(raw["attackerPelvis"]) - root_pos, inverse)
    pelvis_rot = np.asarray(raw["attackerPelvisAxes"]) @ inverse
    pelvis = np.concatenate((pelvis_pos, pelvis_rot[..., :2, :].reshape(-1, 6)), axis=-1).astype(np.float32)
    if attack_name.lower() == 'spear':
        pelvis.fill(0)  # Absent attacker, including after coordinate conversion.
    hit_root = raw["hitRoot"]
    target = (np.asarray(raw["targetWorld"]) - hit_root["point"]) @ np.linalg.inv(hit_root["axes"])
    result = {
        "time": np.asarray(raw["times"], np.float64),
        # Root orientation always remains authored, including signed axes.
        # New zero-tolerance COM exports change position only, before packing.
        "root": np.concatenate((root_pos, root_rot.reshape(-1, 9)), axis=-1).astype(np.float32),
        "body": np.concatenate((body_pos, body_rot[..., :2, :].reshape(*body_pos.shape[:2], 6)), axis=-1).astype(np.float32),
        "attack": np.concatenate((attack_pos, attack_rot[..., :2, :].reshape(-1, 6)), axis=-1).astype(np.float32),
        "attacker_pelvis": pelvis,
        "root_tail": np.asarray(root_tail, np.float32),
        "attack_half": np.asarray(raw["attackHalf"], np.float32),
        "target": target.astype(np.float32),
        "target_world": np.asarray(raw['targetWorld'], np.float32),
        "attack_type": attack_labels(attack_name) if labels is None else np.asarray(labels, np.float32),
        "hit_time": np.asarray(raw["hitTime"], np.float64),
        "carrier_command": np.asarray([float(preview["mode"] == "drawn"), *preview["gaze_normalized"]], np.float32),
        "pin": pin_labels_from_world(positions[:, 1:], rotations[:, 1:]),
    }
    if "motionKind" in raw:
        result["motion_kind"] = np.asarray(raw["motionKind"], np.uint8)
    validate(result)
    rebuilt, _ = world_motion(result)
    expected = positions.copy()
    expected[:, 0] = root_pos
    if np.max(np.abs(rebuilt - expected)) > 2e-5:
        raise ValueError("root-relative label round-trip changed joint positions")
    return result


def validate(data: dict[str, np.ndarray]) -> None:
    if set(data) - {"motion_kind", "target_world"} not in (KEYS, PRE_PIN_KEYS, LEGACY_KEYS):
        raise ValueError(f"unexpected NPZ keys: {set(data) ^ KEYS}")
    n = len(data["time"])
    if 'target_world' in data and (data['target_world'].shape!=(3,) or
            data['target_world'].dtype!=np.float32 or not np.isfinite(data['target_world']).all()):
        raise ValueError('Invalid fixed world target')
    shapes = {"time": (n,), "root": (n, 12), "body": (n, 25, 9), "attack": (n, 9),
              "attack_half": (3,), "target": (3,), "attack_type": (6,), "hit_time": (), "carrier_command": (3,)}
    if 'attacker_pelvis' in data:
        shapes.update(attacker_pelvis=(n, 9), root_tail=(FUTURE_WINDOW, 12))
        if data['attack_type'][-1] == 1 and np.any(data['attacker_pelvis']):
            raise ValueError('Spear attacker pelvis must be exactly zero')
    if 'pin' in data:
        shapes.update(pin=(n, 2))
    if 'motion_kind' in data:
        if data['motion_kind'].dtype != np.uint8 or int(data['motion_kind']) not in (0, 1):
            raise ValueError('Invalid Dodge response-kind ID')
        shapes.update(motion_kind=())
    for key, shape in shapes.items():
        if data[key].shape != shape or not np.isfinite(data[key]).all():
            raise ValueError(f"invalid {key} shape/numbers")
    if n < 3 or not np.array_equal(data["time"][:3], [0, 1, 2]) or np.any(np.diff(data["time"]) <= 0):
        raise ValueError("invalid primer or frame timing")
    if not 2 <= data["hit_time"] <= data["time"][-1]:
        raise ValueError("hit outside armed/final window")
    if np.any(data["attack_half"] <= 0):
        raise ValueError("invalid attack box")
    if data["attack_type"][-1] not in (0, 1) or (data["attack_type"][-1] == 1 and np.any(data["attack_type"][:-1])):
        raise ValueError("invalid spear encoding")
    if 'pin' in data and (
        data['pin'].dtype != np.uint8
        or np.any((data['pin'] != 0) & (data['pin'] != 1))
        or np.any(data['pin'][-1])
    ):
        raise ValueError("invalid binary transition pin labels")


def load_motion(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        result = {key: archive[key] for key in archive.files}
    validate(result)
    return result


def attack_input(data: dict[str, np.ndarray]) -> np.ndarray:
    """One always-present attack: sticky target3 + controls5 + is_spear."""
    result = np.concatenate((data["target"], data["attack_type"])).astype(np.float32)
    if result.shape != (ATTACK_INPUT_DIM,):
        raise ValueError(f"invalid attack input width {result.shape}")
    return result


def event_inputs(data: dict[str, np.ndarray]) -> np.ndarray:
    """Hit only. Armed is constant over controlled frames and is not observed."""
    return (data["time"] >= data["hit_time"]).astype(np.float32)[:, None]


def world_motion(data: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    root = data["root"]
    root_rot = root[:, 3:].reshape(-1, 3, 3)
    body = data["body"]
    pos = body[..., :3] @ root_rot + root[:, None, :3]
    rot = matrices_from_rot6(body[..., 3:]) @ root_rot[:, None]
    return np.concatenate((root[:, None, :3], pos), axis=1), np.concatenate((root_rot[:, None], rot), axis=1)


def world_attack(data: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    root = data["root"]
    root_rot = root[:, 3:].reshape(-1, 3, 3)
    pos = np.einsum("fi,fij->fj", data["attack"][:, :3], root_rot) + root[:, :3]
    return pos, matrices_from_rot6(data["attack"][:, 3:]) @ root_rot


def causal_attack_inputs(data: dict[str, np.ndarray], frame: int) -> np.ndarray:
    """37 inputs: pelvis current/end, collider current/end, hit at end.

    The attacker speaks first. `frame+1` is its desired end pose for this same
    delta, not an extra future prediction. Both transforms use frame's root.
    """
    if 'attacker_pelvis' not in data:
        raise ValueError('v1 data lacks attacker pelvis; not valid for new training')
    if not 1 <= frame < len(data['time'])-1:
        raise ValueError('Expected a controlled interval after the two primers')
    roots = data['root'][frame:frame+2].astype(np.float64)
    bases = roots[:, 3:].reshape(2, 3, 3)
    held_inverse = np.linalg.inv(bases[0])
    values = []
    for key in ('attacker_pelvis', 'attack'):
        local = data[key][frame:frame+2].astype(np.float64)
        if key == 'attacker_pelvis' and data['attack_type'][-1] == 1:
            values.append(np.zeros(18))
            continue
        world_pos = np.einsum('fi,fij->fj', local[:, :3], bases) + roots[:, :3]
        pos = (world_pos - roots[0, :3]) @ held_inverse
        # No need to rebuild the omitted third axis for rotation6 rebasing.
        rot6 = (local[:, 3:].reshape(2, 2, 3) @ bases @ held_inverse).reshape(2, 6)
        values.append(np.concatenate((pos, rot6), axis=-1).reshape(-1))
    values.append(event_inputs(data)[frame+1])
    return np.concatenate(values).astype(np.float32)


def authored_root_features(data: dict[str, np.ndarray], frame: int) -> np.ndarray:
    """Canonical 3 current root deltas + 8 future (x,z,cos yaw,sin yaw).

    Use authored 30-Hz integer samples; fractional attack Final is a label,
    never a duplicate route sample. Tail starts at floor(Final)+1.
    """
    if 'root_tail' not in data:
        raise ValueError('v1 data lacks authored future route; refusing crop-end clamping')
    if not 1 <= frame < len(data['time'])-1 or data['time'][frame] != frame:
        raise ValueError('Expected an integer controlled-interval start')
    integer = data['time'] == np.floor(data['time'])
    route = np.concatenate((data['root'][integer], data['root_tail'])).astype(np.float64)
    pos = route[:, :3]
    basis = route[:, 3:].reshape(-1, 3, 3)
    forward = -basis[:, 1]
    yaw = np.arctan2(forward[:, 0], forward[:, 2])
    def heading(angle):
        c, s = np.cos(angle), np.sin(angle)
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    wrap = lambda angle: (angle + np.pi) % (2*np.pi) - np.pi
    speed = 5.0 / 30
    turn = np.deg2rad(720) / 30
    delta = (pos[frame]-pos[frame-1]) @ heading(yaw[frame-1])
    current = [delta[0]/speed, delta[2]/speed, wrap(yaw[frame]-yaw[frame-1])/turn]
    k = np.arange(1, FUTURE_WINDOW+1)
    future = (pos[frame+k]-pos[frame]) @ heading(yaw[frame])
    dyaw = wrap(yaw[frame+k]-yaw[frame])
    window = np.stack((np.clip(future[:, 0]/(k*speed), -2, 2),
                       np.clip(future[:, 2]/(k*speed), -2, 2), np.cos(dyaw), np.sin(dyaw)), axis=-1)
    return np.concatenate((current, window.reshape(-1))).astype(np.float32)


def defense_conditioning(data: dict[str, np.ndarray], frame: int) -> np.ndarray:
    """Shared 81 inputs, used identically by learned lower AND learned upper."""
    return np.concatenate((causal_attack_inputs(data, frame), authored_root_features(data, frame), attack_input(data)))
