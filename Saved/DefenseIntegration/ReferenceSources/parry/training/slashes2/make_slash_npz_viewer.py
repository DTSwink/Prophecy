from __future__ import annotations

import argparse
import base64
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    from .slash_skeleton import keep_slash_source_bone
except ImportError:
    from slash_skeleton import keep_slash_source_bone


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_SLASH_DIR = PROJECT_ROOT / "ue5" / "slashes" / "npz"
DEFAULT_FIXEDROOT_SLASH_DIR = PROJECT_ROOT / "ue5" / "slashes" / "npz_fixedroot"
DEFAULT_CLEAN_SLASH_DIR = PROJECT_ROOT / "ue5" / "slashes" / "npz_fullclean"
DEFAULT_SLASH_DIR = DEFAULT_FIXEDROOT_SLASH_DIR
DEFAULT_SWORD_FBX = PROJECT_ROOT / "ue5" / "slashes" / "slashL.fbx"
DEFAULT_IDLE_NPZ = (
    PROJECT_ROOT
    / "training"
    / "slashes2"
    / "walk_run_sword_prep"
    / "authored_pruned_npz"
    / "run_omni"
    / "M_Neutral_Stand_Idle_Loop.npz"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "slash_npz_viewer.html"
Z_UP_TO_Y_UP = np.asarray(
    [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]],
    dtype=np.float32,
)


@dataclass
class Motion:
    path: Path
    names: list[str]
    parents: np.ndarray
    positions_m: np.ndarray
    basis: np.ndarray
    fps: float


def _as_float_array(data: np.lib.npyio.NpzFile, key: str) -> np.ndarray:
    return np.asarray(data[key], dtype=np.float32).copy()


def canonicalize_positions(pos: np.ndarray, up_axis: int) -> np.ndarray:
    pos = np.asarray(pos, dtype=np.float32)
    if int(up_axis) != 3:
        return pos.copy()
    return (pos @ Z_UP_TO_Y_UP).copy()


def canonicalize_rotations(rot: np.ndarray, up_axis: int) -> np.ndarray:
    rot = np.asarray(rot, dtype=np.float32)
    if int(up_axis) != 3:
        return rot.copy()
    return (Z_UP_TO_Y_UP.T @ rot @ Z_UP_TO_Y_UP).copy()


def filter_motion_bones(
    names: list[str],
    parents: np.ndarray,
    positions_m: np.ndarray,
    basis: np.ndarray,
) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray]:
    keep = [index for index, name in enumerate(names) if keep_slash_source_bone(name)]
    if len(keep) == len(names):
        return names, parents, positions_m, basis
    old_to_new = {old_index: new_index for new_index, old_index in enumerate(keep)}
    remapped_parents: list[int] = []
    for old_index in keep:
        parent = int(parents[old_index])
        while parent >= 0 and parent not in old_to_new:
            parent = int(parents[parent])
        remapped_parents.append(old_to_new[parent] if parent >= 0 else -1)
    return (
        [names[index] for index in keep],
        np.asarray(remapped_parents, dtype=np.int32),
        positions_m[:, keep, :].copy(),
        basis[:, keep, :, :].copy(),
    )


def load_motion(path: Path) -> Motion:
    path = path.resolve()
    with np.load(path, allow_pickle=True) as data:
        names = [str(x) for x in data["bone_names"]]
        parents = np.asarray(data["parents"], dtype=np.int32).copy()
        fps = float(data["fps"])
        if "global_joint_pos" in data.files and "global_matrix" in data.files:
            up_axis = int(data["axis_up_axis"]) if "axis_up_axis" in data.files else 2
            positions_m = canonicalize_positions(_as_float_array(data, "global_joint_pos") * 0.01, up_axis)
            up_axis = int(data["axis_up_axis"]) if "axis_up_axis" in data.files else 2
            basis = canonicalize_rotations(_as_float_array(data, "global_matrix")[:, :, :3, :3], up_axis)
        elif "model_global_joint_pos_m" in data.files and "model_global_matrix" in data.files:
            positions_m = _as_float_array(data, "model_global_joint_pos_m")
            basis = _as_float_array(data, "model_global_matrix")[:, :, :3, :3]
        else:
            raise ValueError(f"{path} does not contain raw or model global slash motion arrays.")
    if positions_m.ndim != 3 or positions_m.shape[-1] != 3:
        raise ValueError(f"{path} does not contain [T,J,3] positions")
    if basis.shape[:2] != positions_m.shape[:2] or basis.shape[-2:] != (3, 3):
        raise ValueError(f"{path} does not contain [T,J,3,3] basis matrices")
    if not np.isfinite(positions_m).all():
        raise ValueError(f"{path} positions contain non-finite values")
    if not np.isfinite(basis).all():
        raise ValueError(f"{path} basis contains non-finite values")
    names, parents, positions_m, basis = filter_motion_bones(names, parents, positions_m, basis)
    return Motion(path=path, names=names, parents=parents, positions_m=positions_m, basis=basis, fps=fps)


def name_index(names: list[str]) -> dict[str, int]:
    return {name: index for index, name in enumerate(names)}


def b64_f32(array: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(array, dtype=np.float32).tobytes()).decode("ascii")


def b64_i32(array: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(array, dtype=np.int32).tobytes()).decode("ascii")


def b64_u8(array: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(array, dtype=np.uint8).tobytes()).decode("ascii")


def motion_payload_clip(motion: Motion, name: str | None = None) -> dict[str, object]:
    return {
        "name": name or motion.path.stem,
        "source_npz": str(motion.path),
        "frame_count": int(motion.positions_m.shape[0]),
        "fps": float(motion.fps),
        "positions_b64": b64_f32(motion.positions_m),
        "basis_b64": b64_f32(motion.basis),
    }


def original_source_npz(path: Path) -> Path | None:
    keys = (
        "final_original_melee_source_npz",
        "final_original_slash_source_npz",
        "final_original_source_npz",
    )
    with np.load(path, allow_pickle=True) as data:
        for key in keys:
            if key in data.files:
                source = Path(str(data[key]))
                if source.exists():
                    return source.resolve()
    return None


def add_original_payload(clip_payload: dict[str, object], baked: Motion, path: Path) -> None:
    source = original_source_npz(path)
    if source is None:
        return
    original = load_motion(source)
    if original.names != baked.names or original.positions_m.shape != baked.positions_m.shape:
        return
    clip_payload["original_source_npz"] = str(source)
    clip_payload["original_positions_b64"] = b64_f32(original.positions_m)
    clip_payload["original_basis_b64"] = b64_f32(original.basis)


def load_fbx_sdk():
    try:
        import fbx  # type: ignore
        import FbxCommon  # type: ignore
    except ImportError:
        sdk_samples = PROJECT_ROOT / ".tools" / "fbx_python_sdk_2020.3.4" / "samples"
        if sdk_samples.exists():
            sys.path.insert(0, str(sdk_samples))
        import fbx  # type: ignore
        import FbxCommon  # type: ignore
    return fbx, FbxCommon


def fbx_matrix_to_np(matrix: object) -> np.ndarray:
    return np.asarray([[matrix.Get(r, c) for c in range(4)] for r in range(4)], dtype=np.float32)


def walk_fbx_nodes(node: object):
    yield node
    for index in range(node.GetChildCount()):
        yield from walk_fbx_nodes(node.GetChild(index))


def find_fbx_node(scene: object, name: str) -> object:
    for node in walk_fbx_nodes(scene.GetRootNode()):
        if node.GetName() == name:
            return node
    raise ValueError(f"FBX node {name!r} not found")


def fbx_geometric_matrix(node: object, fbx: object) -> np.ndarray:
    pivot = fbx.FbxNode.EPivotSet.eSourcePivot
    matrix = fbx.FbxAMatrix()
    matrix.SetT(fbx.FbxVector4(node.GetGeometricTranslation(pivot)))
    matrix.SetR(fbx.FbxVector4(node.GetGeometricRotation(pivot)))
    matrix.SetS(fbx.FbxVector4(node.GetGeometricScaling(pivot)))
    return fbx_matrix_to_np(matrix)


def infer_blade_axis(vertices_m: np.ndarray) -> tuple[int, int, float, float, np.ndarray]:
    mins = vertices_m.min(axis=0)
    maxs = vertices_m.max(axis=0)
    dims = maxs - mins
    axis = int(np.argmax(dims))
    coord = vertices_m[:, axis]
    median = float(np.median(coord))
    low_span = median - float(coord.min())
    high_span = float(coord.max()) - median
    side = -1 if low_span >= high_span else 1
    side_coord = coord[coord <= median] if side < 0 else coord[coord >= median]
    unique = np.unique(np.round(side_coord.astype(np.float64), 6))
    base = float(np.quantile(coord, 0.05 if side < 0 else 0.95))
    if unique.size >= 4:
        gaps = np.diff(unique)
        gap_index = int(np.argmax(gaps))
        gap = float(gaps[gap_index])
        span = float(coord.max() - coord.min())
        if gap > span * 0.12:
            base = float(unique[gap_index + 1] if side < 0 else unique[gap_index])
    tip = float(coord.min() if side < 0 else coord.max())
    if side < 0:
        mask = coord <= base + 1e-7
    else:
        mask = coord >= base - 1e-7
    return axis, side, base, tip, mask.astype(np.uint8)


def load_sword_mesh(path: Path, sword_node_name: str = "Sword_GL01_Baked", hand_node_name: str = "hand_r") -> dict[str, object]:
    fbx, FbxCommon = load_fbx_sdk()
    manager, scene = FbxCommon.InitializeSdkObjects()
    try:
        if not FbxCommon.LoadScene(manager, scene, str(path)):
            raise ValueError(f"Could not load sword FBX {path}")
        hand = find_fbx_node(scene, hand_node_name)
        sword = find_fbx_node(scene, sword_node_name)
        mesh = sword.GetMesh()
        if mesh is None:
            raise ValueError(f"FBX node {sword_node_name!r} does not contain a mesh")

        vertices = np.asarray(
            [[mesh.GetControlPointAt(i)[j] for j in range(3)] for i in range(mesh.GetControlPointsCount())],
            dtype=np.float32,
        )
        geom = fbx_geometric_matrix(sword, fbx)
        vertices_h = np.concatenate([vertices, np.ones((vertices.shape[0], 1), dtype=np.float32)], axis=1)
        vertices = (vertices_h @ geom)[:, :3]

        triangles: list[tuple[int, int, int]] = []
        for polygon_index in range(mesh.GetPolygonCount()):
            polygon_size = mesh.GetPolygonSize(polygon_index)
            if polygon_size < 3:
                continue
            polygon = [int(mesh.GetPolygonVertex(polygon_index, k)) for k in range(polygon_size)]
            for k in range(1, polygon_size - 1):
                triangles.append((polygon[0], polygon[k], polygon[k + 1]))
        if not triangles:
            raise ValueError(f"FBX node {sword_node_name!r} has no triangles")

        zero = fbx.FbxTime()
        hand_global = hand.EvaluateGlobalTransform(zero)
        sword_global = sword.EvaluateGlobalTransform(zero)
        local_to_hand = fbx_matrix_to_np(hand_global.Inverse() * sword_global)
        local_to_hand[3, :3] *= 0.01

        vertices_m = vertices * 0.01
        axis, side, base, tip, blade_mask = infer_blade_axis(vertices_m)
        blade_vertices = vertices_m[blade_mask.astype(bool)]
        dims_m = (vertices_m.max(axis=0) - vertices_m.min(axis=0)).astype(np.float32)
        return {
            "source_fbx": str(path.resolve()),
            "node": sword_node_name,
            "hand_node": hand_node_name,
            "vertex_count": int(vertices_m.shape[0]),
            "triangle_count": int(len(triangles)),
            "vertices_b64": b64_f32(vertices_m),
            "triangles_b64": b64_i32(np.asarray(triangles, dtype=np.int32)),
            "blade_mask_b64": b64_u8(blade_mask),
            "local_to_hand": local_to_hand.astype(float).reshape(-1).tolist(),
            "blade_axis": int(axis),
            "blade_side": int(side),
            "blade_base_m": float(base),
            "blade_tip_m": float(tip),
            "blade_vertex_count": int(blade_mask.sum()),
            "blade_bounds_min_m": blade_vertices.min(axis=0).astype(float).tolist(),
            "blade_bounds_max_m": blade_vertices.max(axis=0).astype(float).tolist(),
            "dims_m": dims_m.astype(float).tolist(),
        }
    finally:
        manager.Destroy()


def make_payload(
    slash_dir: Path,
    sword_fbx: Path | None = DEFAULT_SWORD_FBX,
    idle_npz: Path | None = DEFAULT_IDLE_NPZ,
) -> dict[str, object]:
    slash_paths = sorted(path.resolve() for path in slash_dir.glob("*.npz"))
    if not slash_paths:
        raise FileNotFoundError(f"No slash NPZ files found in {slash_dir}")
    clips: list[dict[str, object]] = []
    all_bounds: list[np.ndarray] = []
    canonical_names: list[str] | None = None
    canonical_parents: list[int] | None = None

    for path in slash_paths:
        slash = load_motion(path)
        if canonical_names is None:
            canonical_names = slash.names
            canonical_parents = slash.parents.astype(int).tolist()
        elif slash.names != canonical_names:
            raise ValueError(f"{path.name} skeleton differs from the first slash clip")
        all_bounds.append(slash.positions_m.reshape(-1, 3))
        clip_payload = motion_payload_clip(slash, path.stem)
        add_original_payload(clip_payload, slash, path)
        clips.append(clip_payload)

    assert canonical_names is not None and canonical_parents is not None
    bounds = np.concatenate(all_bounds, axis=0)
    payload: dict[str, object] = {
        "title": "Slash / Fullbody True Anims",
        "slash_dir": str(slash_dir.resolve()),
        "bone_names": canonical_names,
        "parents": canonical_parents,
        "bone_count": len(canonical_names),
        "composition": "raw fullbody slash motion directly from the converted FBX NPZ files; no idle-foot composite is applied",
        "bounds": {
            "min": bounds.min(axis=0).astype(float).tolist(),
            "max": bounds.max(axis=0).astype(float).tolist(),
        },
        "clips": clips,
    }
    if idle_npz is not None:
        idle_npz = idle_npz.resolve()
        if idle_npz.exists():
            idle = load_motion(idle_npz)
            if idle.names != canonical_names:
                raise ValueError(f"{idle_npz.name} skeleton differs from the slash clips")
            payload["idle"] = motion_payload_clip(idle, idle.path.stem)
    if sword_fbx is not None:
        payload["sword"] = load_sword_mesh(sword_fbx.resolve())
    return payload


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Slash Fullbody True Anims</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #101216;
      --panel: #1a1d22;
      --panel2: #23272f;
      --text: #edf1f7;
      --muted: #a1a9b8;
      --line: #313846;
      --accent: #5ed6b2;
      --left: #74a8ff;
      --right: #ff986c;
      --center: #e6df83;
      --volume: rgba(223, 203, 186, 0.30);
      --volume-line: rgba(255, 238, 222, 0.50);
      --detail: rgba(199, 207, 224, 0.76);
      --helper: rgba(161, 255, 228, 0.78);
      --weapon: rgba(255, 232, 122, 0.92);
      --sword-blade: rgba(220, 237, 245, 0.88);
      --sword-edge: rgba(249, 255, 255, 0.78);
      --sword-hilt: rgba(255, 185, 88, 0.88);
      --attack-box: rgba(95, 206, 255, 0.86);
      --attack-box-fill: rgba(95, 206, 255, 0.10);
      --attack-red: rgba(255, 78, 78, 0.95);
      --attack-green: rgba(84, 238, 132, 0.95);
      --attack-purple: rgba(192, 118, 255, 0.96);
      --phase-armed: #c076ff;
      --phase-hit: #ff4e4e;
      --target: rgba(192, 118, 255, 0.34);
      --target-line: rgba(224, 184, 255, 0.92);
      --armed-target: rgba(90, 210, 255, 0.34);
      --armed-target-line: rgba(170, 235, 255, 0.92);
      --armed-hand-target: rgba(255, 200, 80, 0.34);
      --armed-hand-target-line: rgba(255, 230, 145, 0.92);
      --foot-left: #ff5a5a;
      --foot-left-fill: rgba(255, 90, 90, 0.34);
      --foot-right: #57dd86;
      --foot-right-fill: rgba(87, 221, 134, 0.32);
      --hand-fill: rgba(236, 218, 202, 0.34);
    }
    * { box-sizing: border-box; }
    html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; }
    body {
      font: 13px/1.35 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: var(--bg);
    }
    #app { width: 100vw; height: 100vh; display: grid; grid-template-rows: 1fr auto; }
    #viewport { position: relative; min-height: 0; }
    canvas { width: 100%; height: 100%; display: block; background: #0f1217; cursor: grab; }
    canvas:active { cursor: grabbing; }
    .hud {
      position: absolute;
      top: 12px;
      left: 12px;
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      pointer-events: none;
    }
    .pill {
      background: rgba(26, 29, 34, 0.9);
      border: 1px solid rgba(255,255,255,0.08);
      padding: 6px 8px;
      border-radius: 6px;
      color: var(--muted);
    }
    .pill strong { color: var(--text); font-weight: 600; }
    .attack-panel {
      position: absolute;
      top: 56px;
      right: 12px;
      z-index: 4;
      width: min(324px, calc(100vw - 24px));
      max-height: calc(100% - 136px);
      display: grid;
      gap: 7px;
      padding: 10px;
      overflow: auto;
      opacity: 0.46;
      background: rgba(26, 29, 34, 0.84);
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 6px;
      box-shadow: 0 12px 28px rgba(0,0,0,0.26);
      transition: opacity 120ms ease, width 120ms ease, padding 120ms ease;
    }
    .attack-panel:hover,
    .attack-panel:focus-within {
      opacity: 0.96;
      background: rgba(26, 29, 34, 0.93);
    }
    .attack-panel.collapsed {
      width: auto;
      min-width: 0;
      padding: 6px;
      opacity: 0.78;
      overflow: visible;
    }
    .attack-panel.collapsed .attack-grid,
    .attack-panel.collapsed .attack-save {
      display: none;
    }
    .attack-title {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      color: var(--text);
      font-weight: 650;
    }
    #attackToggle {
      height: 28px;
      min-width: 58px;
      padding: 0 9px;
      font-weight: 650;
    }
    .attack-grid { display: grid; gap: 5px; }
    .attack-row {
      display: grid;
      grid-template-columns: 64px 1fr 41px;
      gap: 7px;
      align-items: center;
      color: var(--muted);
    }
    .attack-row input[type="range"] { height: 24px; }
    .attack-row input[type="number"] {
      width: 100%;
      min-width: 0;
      height: 26px;
      padding: 0 7px;
    }
    .attack-row output {
      text-align: right;
      font-variant-numeric: tabular-nums;
      color: var(--text);
    }
    .attack-row.limb-row { grid-template-columns: 64px 1fr; }
    #meleeTargetLimbText {
      color: var(--text);
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .attack-save {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 8px;
    }
    #saveAttack, #saveHit, #snapBetween { height: 28px; min-width: 52px; }
    #attackSaveState { color: var(--muted); font-size: 12px; min-height: 16px; }
    #controls {
      display: grid;
      grid-template-columns: minmax(72px, 120px) minmax(78px, 120px) minmax(140px, 260px) minmax(180px, 1fr) auto auto auto;
      gap: 10px;
      align-items: center;
      padding: 10px 12px;
      background: var(--panel);
      border-top: 1px solid var(--line);
    }
    .controls-body { display: contents; }
    #controls.controls-collapsed .controls-body { display: none; }
    #controlsToggle {
      min-width: 104px;
      font-weight: 650;
    }
    button, select, input {
      font: inherit;
      color: var(--text);
      background: var(--panel2);
      border: 1px solid var(--line);
      border-radius: 6px;
      height: 32px;
    }
    button { min-width: 42px; padding: 0 11px; cursor: pointer; }
    button:hover, select:hover { border-color: #596273; }
    input[type="range"] { width: 100%; accent-color: var(--accent); }
    input[type="checkbox"] { width: 16px; height: 16px; accent-color: var(--accent); }
    #blade { width: 128px; }
    #between { width: 88px; }
    #frame { grid-column: 1 / -1; min-width: 180px; }
    .foot-lock input[type="range"] { width: 118px; }
    #saveFootLock { min-width: 76px; }
    #footLockSaveState { color: var(--muted); font-size: 12px; min-height: 16px; }
    .tune-control {
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: 118px minmax(220px, 360px) 44px;
      justify-content: start;
      min-width: 0;
      gap: 10px;
    }
    .tune-control input[type="range"] { width: 100%; min-width: 0; }
    .tune-control span { text-align: right; font-variant-numeric: tabular-nums; }
    .pelvis-extra {
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: 118px repeat(3, minmax(82px, 108px));
      justify-content: start;
      align-items: center;
      gap: 10px;
      color: var(--muted);
    }
    .pelvis-extra label { gap: 4px; }
    .pelvis-extra input { width: 68px; padding: 0 6px; }
    label { color: var(--muted); display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
    .num { width: 74px; padding: 0 7px; }
    .viewer-hidden { display: none !important; }
    @media (max-width: 860px) {
      #controls { grid-template-columns: minmax(72px, 110px) minmax(120px, 1fr) auto; }
      #frame { grid-column: 1 / -1; }
    }
  </style>
</head>
<body>
  <div id="app">
    <div id="viewport">
      <canvas id="canvas"></canvas>
      <div class="hud">
        <div class="pill"><strong id="clipTitle">slash</strong></div>
        <div class="pill"><strong id="frameText">0</strong> / <span id="lastFrameText">0</span></div>
        <div class="pill"><span id="fpsText">30</span> FPS</div>
        <div class="pill"><span id="bonesText">0</span> bones</div>
      </div>
      <div id="attackPanel" class="attack-panel collapsed">
        <div class="attack-title">
          <button id="attackToggle" type="button" aria-expanded="false">Attack</button>
          <div class="attack-save"><button id="saveAttack" type="button">Save</button><button id="saveHit" type="button">Save Hit</button><button id="saveArmed" type="button">Save Armed</button><button id="snapBetween" type="button">Snap Between to Config</button><span id="attackSaveState"></span></div>
        </div>
        <div class="attack-grid">
          <label class="attack-row"><span>Width cm</span><input id="attackWidth" type="range" min="-10" max="30" value="0" step="0.1"><output id="attackWidthText">0.0</output></label>
          <label class="attack-row"><span>Thick cm</span><input id="attackThickness" type="range" min="-10" max="30" value="0" step="0.1"><output id="attackThicknessText">0.0</output></label>
          <label class="attack-row"><span>Length cm</span><input id="attackLength" type="range" min="-40" max="80" value="0" step="0.1"><output id="attackLengthText">0.0</output></label>
          <label class="attack-row"><span>Target cm</span><input id="targetRadius" type="range" min="1" max="80" value="10" step="0.1"><output id="targetRadiusText">10.0</output></label>
          <label class="attack-row"><span>Armed cm</span><input id="armedRadius" type="range" min="1" max="80" value="10" step="0.1"><output id="armedRadiusText">10.0</output></label>
          <label class="attack-row limb-row melee-only"><span>Limb</span><output id="meleeTargetLimbText">n/a</output></label>
          <label class="attack-row melee-only"><span>Target X</span><input id="meleeTargetX" type="number" value="0" step="0.1"><output id="meleeTargetXText">0.0</output></label>
          <label class="attack-row melee-only"><span>Target Y</span><input id="meleeTargetY" type="number" value="0" step="0.1"><output id="meleeTargetYText">0.0</output></label>
          <label class="attack-row melee-only"><span>Target Z</span><input id="meleeTargetZ" type="number" value="0" step="0.1"><output id="meleeTargetZText">0.0</output></label>
          <label class="attack-row"><span>Bound A</span><input id="attackBoundStart" type="range" min="0" max="1" value="0" step="0.001"><output id="attackBoundStartText">0.000</output></label>
          <label class="attack-row"><span>Bound B</span><input id="attackBoundEnd" type="range" min="0" max="1" value="1" step="0.001"><output id="attackBoundEndText">1.000</output></label>
          <label class="attack-row"><span>Frame +</span><input id="attackFrameBlend" type="range" min="0" max="1" value="0" step="0.001"><output id="attackFrameBlendText">0.000</output></label>
          <label class="attack-row"><span>Hit</span><input id="attackHit" type="range" min="0" max="1" value="0.5" step="0.001"><output id="attackHitText">0.500</output></label>
        </div>
      </div>
    </div>
    <div id="controls">
      <button id="play" title="Play or pause">Play</button>
      <button id="snapArmedFrame" title="Jump to the saved fractional armed frame" disabled>Snap Armed</button>
      <button id="snapHitFrame" title="Jump to the saved fractional hit frame" disabled>Snap Hit</button>
      <select id="clip"></select>
      <button id="controlsToggle" type="button" aria-expanded="true" title="Collapse or expand controls">Controls down</button>
      <input id="frame" type="range" min="0" max="1" value="0" step="1">
      <div id="controlsBody" class="controls-body">
      <label><input id="showIdle" type="checkbox"> Show Idle</label>
      <label><input id="showOriginal" type="checkbox"> Show Original</label>
      <label><input id="showModified" type="checkbox" checked> Show Modified</label>
      <label><input id="idleFootIk" type="checkbox" checked> IK Foot Offset</label>
      <label><input id="showPoleVectors" type="checkbox"> Pole Vector</label>
      <label class="foot-lock">L Foot <input id="leftFootLock" type="range" min="0" max="1" value="0" step="0.01"><span id="leftFootLockText">0.00</span></label>
      <label class="foot-lock">R Foot <input id="rightFootLock" type="range" min="0" max="1" value="0" step="0.01"><span id="rightFootLockText">0.00</span></label>
      <button id="saveFootLock" title="Save current foot slider values for this animation">Save Feet</button><span id="footLockSaveState"></span>
      <label class="tune-control">Pelvis Offset <input id="pelvisOffset" type="range" min="0" max="1" value="1" step="0.01"><span id="pelvisOffsetText">1.00</span></label>
      <label class="tune-control">Mean->Support <input id="pelvisSource" type="range" min="0" max="1" value="0" step="0.01"><span id="pelvisSourceText">0.00</span></label>
      <div class="pelvis-extra">
        <span>Extra Pelvis cm</span>
        <label>X <input id="extraPelvisX" type="number" value="0" step="0.1"></label>
        <label>Y <input id="extraPelvisY" type="number" value="0" step="0.1"></label>
        <label>Z <input id="extraPelvisZ" type="number" value="0" step="0.1"></label>
      </div>
      <label class="viewer-hidden between-control">Between <input id="between" type="range" min="0" max="1" value="0" step="0.001"><span id="betweenText">0.000</span></label>
      <label class="viewer-hidden">Speed <input id="speed" class="num" type="number" value="1" min="0.1" max="4" step="0.1"></label>
      <button id="reset" class="viewer-hidden" title="Reset camera">Reset Camera</button>
      <button id="volumes" class="viewer-hidden" title="Toggle colliders">Hide Colliders</button>
      <button id="labels" class="viewer-hidden" title="Toggle bone labels">Labels</button>
      <label class="viewer-hidden blade-control">Blade <input id="blade" type="range" min="0" max="100" value="100" step="1"><span id="bladeText">100%</span></label>
      </div>
    </div>
  </div>
  <script>
    const payload = __PAYLOAD_JSON__;
    window.__SLASH_PAYLOAD__ = payload;
    const clips = payload.clips;
    const names = payload.bone_names;
    const parents = payload.parents;
    const J = payload.bone_count;
    const nameToIndex = new Map(names.map((name, index) => [name, index]));

    for (const clip of clips) {
      clip.positions = decodeF32(clip.positions_b64);
      clip.basis = decodeF32(clip.basis_b64);
      delete clip.positions_b64;
      delete clip.basis_b64;
      if (clip.original_positions_b64 && clip.original_basis_b64) {
        clip.originalPositions = decodeF32(clip.original_positions_b64);
        clip.originalBasis = decodeF32(clip.original_basis_b64);
        delete clip.original_positions_b64;
        delete clip.original_basis_b64;
      }
    }
    const idleClip = payload.idle || null;
    if (idleClip) {
      idleClip.positions = decodeF32(idleClip.positions_b64);
      idleClip.basis = decodeF32(idleClip.basis_b64);
      delete idleClip.positions_b64;
      delete idleClip.basis_b64;
    }
    const sword = payload.sword || null;
    const meleeClipNames = new Set(["headbutt", "hookl", "hookr", "jabl", "jabr", "kickl", "kickr", "overl", "overr"]);
    const isMeleeClip = clip => meleeClipNames.has(String(clip?.name || "").toLowerCase());
    const hasMeleeClips = clips.some(clip => isMeleeClip(clip));
    const hasSlashClips = clips.some(clip => !isMeleeClip(clip));
    const isMeleeClipSet = hasMeleeClips && !hasSlashClips;
    const isCombinedAttackSet = hasMeleeClips && hasSlashClips;
    const isFinalOriginalClipSet = String(payload.slash_dir || "").toLowerCase().includes("final_original");
    const attackConfigFileName = isMeleeClipSet ? "melee_attack_config.json" : "slash_attack_config.json";
    if (sword) {
      sword.vertices = decodeF32(sword.vertices_b64);
      sword.triangles = decodeI32(sword.triangles_b64);
      sword.bladeMask = decodeU8(sword.blade_mask_b64);
      delete sword.vertices_b64;
      delete sword.triangles_b64;
      delete sword.blade_mask_b64;
    }

    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    const playButton = document.getElementById("play");
    const snapArmedFrameButton = document.getElementById("snapArmedFrame");
    const snapHitFrameButton = document.getElementById("snapHitFrame");
    const clipSelect = document.getElementById("clip");
    const controlsElement = document.getElementById("controls");
    const controlsToggleButton = document.getElementById("controlsToggle");
    const frameSlider = document.getElementById("frame");
    const betweenSlider = document.getElementById("between");
    const betweenText = document.getElementById("betweenText");
    const speedInput = document.getElementById("speed");
    const showIdleInput = document.getElementById("showIdle");
    const showOriginalInput = document.getElementById("showOriginal");
    const showModifiedInput = document.getElementById("showModified");
    const idleFootIkInput = document.getElementById("idleFootIk");
    const showPoleVectorsInput = document.getElementById("showPoleVectors");
    const footLockInputs = {
      left: document.getElementById("leftFootLock"),
      right: document.getElementById("rightFootLock")
    };
    const footLockTexts = {
      left: document.getElementById("leftFootLockText"),
      right: document.getElementById("rightFootLockText")
    };
    const saveFootLockButton = document.getElementById("saveFootLock");
    const footLockSaveState = document.getElementById("footLockSaveState");
    const pelvisOffsetInput = document.getElementById("pelvisOffset");
    const pelvisOffsetText = document.getElementById("pelvisOffsetText");
    const pelvisSourceInput = document.getElementById("pelvisSource");
    const pelvisSourceText = document.getElementById("pelvisSourceText");
    const extraPelvisInputs = {
      x: document.getElementById("extraPelvisX"),
      y: document.getElementById("extraPelvisY"),
      z: document.getElementById("extraPelvisZ")
    };
    const resetButton = document.getElementById("reset");
    const volumesButton = document.getElementById("volumes");
    const labelsButton = document.getElementById("labels");
    const controlsCollapseKey = "slashNpzViewer:controlsCollapsed";
    function setControlsCollapsed(collapsed, options = {}) {
      controlsElement.classList.toggle("controls-collapsed", collapsed);
      controlsToggleButton.textContent = collapsed ? "Controls up" : "Controls down";
      controlsToggleButton.setAttribute("aria-expanded", String(!collapsed));
      if (options.persist !== false) {
        window.localStorage.setItem(controlsCollapseKey, collapsed ? "1" : "0");
      }
      if (options.resize !== false && typeof resize === "function") {
        resize();
      }
    }
    setControlsCollapsed(window.localStorage.getItem(controlsCollapseKey) === "1", { persist: false, resize: false });
    const attackPanel = document.getElementById("attackPanel");
    const attackToggle = document.getElementById("attackToggle");
    const attackFrameBlendSlider = document.getElementById("attackFrameBlend");
    const attackFrameBlendText = document.getElementById("attackFrameBlendText");
    const bladeSlider = document.getElementById("blade");
    const bladeText = document.getElementById("bladeText");
    const attackInputs = {
      widthOffsetCm: document.getElementById("attackWidth"),
      thicknessOffsetCm: document.getElementById("attackThickness"),
      lengthOffsetCm: document.getElementById("attackLength"),
      targetRadiusCm: document.getElementById("targetRadius"),
      armedRadiusCm: document.getElementById("armedRadius"),
      meleeTargetXCm: document.getElementById("meleeTargetX"),
      meleeTargetYCm: document.getElementById("meleeTargetY"),
      meleeTargetZCm: document.getElementById("meleeTargetZ"),
      boundStart: document.getElementById("attackBoundStart"),
      boundEnd: document.getElementById("attackBoundEnd"),
      hit: document.getElementById("attackHit")
    };
    const attackOutputs = {
      widthOffsetCm: document.getElementById("attackWidthText"),
      thicknessOffsetCm: document.getElementById("attackThicknessText"),
      lengthOffsetCm: document.getElementById("attackLengthText"),
      targetRadiusCm: document.getElementById("targetRadiusText"),
      armedRadiusCm: document.getElementById("armedRadiusText"),
      meleeTargetXCm: document.getElementById("meleeTargetXText"),
      meleeTargetYCm: document.getElementById("meleeTargetYText"),
      meleeTargetZCm: document.getElementById("meleeTargetZText"),
      boundStart: document.getElementById("attackBoundStartText"),
      boundEnd: document.getElementById("attackBoundEndText"),
      hit: document.getElementById("attackHitText")
    };
    const meleeTargetLimbText = document.getElementById("meleeTargetLimbText");
    const saveAttackButton = document.getElementById("saveAttack");
    const saveHitButton = document.getElementById("saveHit");
    const saveArmedButton = document.getElementById("saveArmed");
    const snapBetweenButton = document.getElementById("snapBetween");
    const attackSaveState = document.getElementById("attackSaveState");
    const clipTitle = document.getElementById("clipTitle");
    const frameText = document.getElementById("frameText");
    const lastFrameText = document.getElementById("lastFrameText");
    const fpsText = document.getElementById("fpsText");
    const bonesText = document.getElementById("bonesText");

    let activeClipIndex = 0;
    let activeClip = clips[0];
    let frame = 0;
    let frameCursor = 0;
    let frameBlend = 0;
    let playing = false;
    let showVolumes = true;
    let showLabels = false;
    let showIdle = false;
    let showOriginal = false;
    let showModified = true;
    let useIdleFootIk = Boolean(idleClip) && !isFinalOriginalClipSet;
    let showPoleVectors = false;
    let pelvisOffsetScale = idleClip ? 1 : 0;
    let pelvisSourceBlend = 0;
    let extraPelvisOffsetM = [0, 0, 0];
    let workingFootFrame0Lerp = { left: 0, right: 0 };
    let workingMeleeTargetOffsetM = [0, 0, 0];
    let bladeScale = 1.0;
    let attackConfig = defaultAttackConfig();
    let slashAttackConfig = defaultAttackConfig();
    let meleeAttackConfig = defaultAttackConfig();
    let yaw = -0.75;
    let pitch = -0.18;
    let zoom = 1.45;
    let panX = 0;
    let panY = 0;
    let lastTime = performance.now();
    let playTimer = null;
    let drag = null;
    let pointsCache = [];
    let renderSampleOverride = null;
    let renderRootOffset = [0, 0, 0];

    const boundsMin = payload.bounds.min;
    const boundsMax = payload.bounds.max;
    const center = [
      (boundsMin[0] + boundsMax[0]) * 0.5,
      (boundsMin[1] + boundsMax[1]) * 0.5,
      (boundsMin[2] + boundsMax[2]) * 0.5
    ];
    const extent = Math.max(0.25, boundsMax[0] - boundsMin[0], boundsMax[1] - boundsMin[1], boundsMax[2] - boundsMin[2]);
    const cameraTarget = [center[0], 0.0, center[2]];
    const rootIndex = nameToIndex.get("root") ?? nameToIndex.get("pelvis") ?? 0;
    const pelvisIndex = nameToIndex.get("pelvis") ?? rootIndex;
    function updateClipModeUi() {
      for (const el of document.querySelectorAll(".melee-only")) {
        el.classList.toggle("viewer-hidden", !isMeleeClip(activeClip));
      }
    }
    if (!idleClip) {
      showIdleInput.disabled = true;
      showIdleInput.checked = false;
      showIdleInput.closest("label").title = "Idle NPZ was not embedded in this viewer";
      idleFootIkInput.disabled = true;
      idleFootIkInput.checked = false;
      idleFootIkInput.closest("label").title = "Idle NPZ was not embedded in this viewer";
      showPoleVectorsInput.disabled = true;
      showPoleVectorsInput.checked = false;
      showPoleVectorsInput.closest("label").title = "Idle NPZ was not embedded in this viewer";
      pelvisOffsetInput.disabled = true;
      pelvisOffsetInput.value = "0";
      pelvisOffsetText.textContent = "0.00";
      pelvisOffsetInput.closest("label").title = "Idle NPZ was not embedded in this viewer";
      pelvisSourceInput.disabled = true;
      pelvisSourceInput.value = "0";
      pelvisSourceText.textContent = "0.00";
      pelvisSourceInput.closest("label").title = "Idle NPZ was not embedded in this viewer";
      for (const input of Object.values(footLockInputs)) {
        input.disabled = true;
        input.closest("label").title = "Idle NPZ was not embedded in this viewer";
      }
      saveFootLockButton.disabled = true;
      saveFootLockButton.title = "Idle NPZ was not embedded in this viewer";
    } else if (isFinalOriginalClipSet) {
      useIdleFootIk = false;
      idleFootIkInput.checked = false;
      idleFootIkInput.disabled = true;
      idleFootIkInput.closest("label").title = "Final-original viewers show the baked NPZs directly";
      for (const input of Object.values(footLockInputs)) input.disabled = true;
      saveFootLockButton.disabled = true;
      saveFootLockButton.title = "Final-original viewers do not apply another live cleanup pass";
      pelvisOffsetInput.disabled = true;
      pelvisSourceInput.disabled = true;
      for (const input of Object.values(extraPelvisInputs)) input.disabled = true;
      pelvisOffsetInput.closest("label").title = "Final-original viewers show the baked NPZs directly";
      pelvisSourceInput.closest("label").title = "Final-original viewers show the baked NPZs directly";
    }
    const floorColors = {
      base: "rgba(31,58,97,0.42)",
      subtle: "rgba(141,185,210,0.14)",
      minor: "rgba(117,169,203,0.24)",
      major: "rgba(166,204,224,0.42)"
    };
    const footDims = [0.175, 0.120, 0.051];
    const toeDims = [0.048, 0.120, 0.049];

    for (let i = 0; i < clips.length; i++) {
      const opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = clips[i].name;
      clipSelect.appendChild(opt);
    }

    function decodeF32(text) {
      const bin = atob(text);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      return new Float32Array(bytes.buffer);
    }

    function decodeI32(text) {
      const bin = atob(text);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      return new Int32Array(bytes.buffer);
    }

    function decodeU8(text) {
      const bin = atob(text);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      return bytes;
    }

    function css(name) {
      return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    function colorFor(name) {
      const n = name.toLowerCase();
      if (n.startsWith("weapon")) return css("--weapon");
      if (n.startsWith("ik_") || n === "attach" || n.includes("locator")) return css("--helper");
      if (isDetailName(n) || n.includes("_twist_")) return css("--detail");
      if (n.endsWith("_l") || n.includes("left")) return css("--left");
      if (n.endsWith("_r") || n.includes("right")) return css("--right");
      return css("--center");
    }

    function isDetailName(name) {
      return name.includes("thumb") ||
        name.includes("index") ||
        name.includes("middle") ||
        name.includes("ring") ||
        name.includes("pinky") ||
        name.includes("metacarpal");
    }

    function isHelperName(name) {
      return name.startsWith("ik_") ||
        name.startsWith("weapon") ||
        name === "attach" ||
        name.includes("locator") ||
        name.includes("_twist_");
    }

    function frameCountFromPositions(arr) {
      return Math.max(1, Math.floor(arr.length / (J * 3)));
    }

    function frameCountFromBasis(arr) {
      return Math.max(1, Math.floor(arr.length / (J * 9)));
    }

    function sampleInfo(count, f) {
      const maxFrame = Math.max(0, count - 1);
      const x = Math.max(0, Math.min(maxFrame, Number(f) || 0));
      const base = Math.floor(x);
      const next = Math.min(maxFrame, base + 1);
      return { base, next, t: x - base };
    }

    function viewFrame() {
      return Math.max(0, Math.min(activeClip.frame_count - 1, frame + frameBlend));
    }

    function formatFrameValue(value) {
      const rounded = Math.round(value);
      return Math.abs(value - rounded) < 1e-6 ? String(rounded) : value.toFixed(3);
    }

    function posAt(arr, f, j) {
      const s = sampleInfo(frameCountFromPositions(arr), f);
      const i0 = (s.base * J + j) * 3;
      if (s.t <= 1e-7 || s.base === s.next) return [arr[i0], arr[i0 + 1], arr[i0 + 2]];
      const i1 = (s.next * J + j) * 3;
      return [
        arr[i0] + (arr[i1] - arr[i0]) * s.t,
        arr[i0 + 1] + (arr[i1 + 1] - arr[i0 + 1]) * s.t,
        arr[i0 + 2] + (arr[i1 + 2] - arr[i0 + 2]) * s.t
      ];
    }

    function rawBasisAxis(arr, f, j, axis) {
      const i = (f * J + j) * 9 + axis * 3;
      return normalize3([arr[i], arr[i + 1], arr[i + 2]]);
    }

    function orthonormalAxes(x, y, z) {
      x = normalize3(x);
      y = sub3(y, mul3(x, dot3(y, x)));
      if (norm3(y) < 1e-6) y = normalize3(cross3(z, x));
      else y = normalize3(y);
      let fixedZ = normalize3(cross3(x, y));
      if (dot3(fixedZ, z) < 0) fixedZ = mul3(fixedZ, -1);
      const fixedY = normalize3(cross3(fixedZ, x));
      return [x, fixedY, fixedZ];
    }

    function quatNormalize(q) {
      const n = Math.hypot(q[0], q[1], q[2], q[3]);
      return n > 1e-8 ? [q[0] / n, q[1] / n, q[2] / n, q[3] / n] : [1, 0, 0, 0];
    }

    function quatDot(a, b) {
      return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3];
    }

    function quatFromAxes(x, y, z) {
      [x, y, z] = orthonormalAxes(x, y, z);
      const m00 = x[0], m01 = y[0], m02 = z[0];
      const m10 = x[1], m11 = y[1], m12 = z[1];
      const m20 = x[2], m21 = y[2], m22 = z[2];
      const trace = m00 + m11 + m22;
      let qw, qx, qy, qz;
      if (trace > 0) {
        const s = Math.sqrt(trace + 1.0) * 2.0;
        qw = 0.25 * s;
        qx = (m21 - m12) / s;
        qy = (m02 - m20) / s;
        qz = (m10 - m01) / s;
      } else if (m00 > m11 && m00 > m22) {
        const s = Math.sqrt(1.0 + m00 - m11 - m22) * 2.0;
        qw = (m21 - m12) / s;
        qx = 0.25 * s;
        qy = (m01 + m10) / s;
        qz = (m02 + m20) / s;
      } else if (m11 > m22) {
        const s = Math.sqrt(1.0 + m11 - m00 - m22) * 2.0;
        qw = (m02 - m20) / s;
        qx = (m01 + m10) / s;
        qy = 0.25 * s;
        qz = (m12 + m21) / s;
      } else {
        const s = Math.sqrt(1.0 + m22 - m00 - m11) * 2.0;
        qw = (m10 - m01) / s;
        qx = (m02 + m20) / s;
        qy = (m12 + m21) / s;
        qz = 0.25 * s;
      }
      return quatNormalize([qw, qx, qy, qz]);
    }

    function axesFromQuat(q) {
      const [w, x, y, z] = quatNormalize(q);
      const xx = x * x, yy = y * y, zz = z * z;
      const xy = x * y, xz = x * z, yz = y * z;
      const wx = w * x, wy = w * y, wz = w * z;
      const m00 = 1 - 2 * (yy + zz);
      const m01 = 2 * (xy - wz);
      const m02 = 2 * (xz + wy);
      const m10 = 2 * (xy + wz);
      const m11 = 1 - 2 * (xx + zz);
      const m12 = 2 * (yz - wx);
      const m20 = 2 * (xz - wy);
      const m21 = 2 * (yz + wx);
      const m22 = 1 - 2 * (xx + yy);
      return [
        normalize3([m00, m10, m20]),
        normalize3([m01, m11, m21]),
        normalize3([m02, m12, m22])
      ];
    }

    function quatSlerp(a, b, t) {
      a = quatNormalize(a);
      b = quatNormalize(b);
      let cosTheta = quatDot(a, b);
      if (cosTheta < 0) {
        b = [-b[0], -b[1], -b[2], -b[3]];
        cosTheta = -cosTheta;
      }
      if (cosTheta > 0.9995) {
        return quatNormalize([
          a[0] + (b[0] - a[0]) * t,
          a[1] + (b[1] - a[1]) * t,
          a[2] + (b[2] - a[2]) * t,
          a[3] + (b[3] - a[3]) * t
        ]);
      }
      const theta = Math.acos(Math.max(-1, Math.min(1, cosTheta)));
      const sinTheta = Math.sin(theta);
      const wa = Math.sin((1 - t) * theta) / sinTheta;
      const wb = Math.sin(t * theta) / sinTheta;
      return quatNormalize([
        a[0] * wa + b[0] * wb,
        a[1] * wa + b[1] * wb,
        a[2] * wa + b[2] * wb,
        a[3] * wa + b[3] * wb
      ]);
    }

    function quatNegate(q) {
      return [-q[0], -q[1], -q[2], -q[3]];
    }

    function quatIsFinite(q) {
      return q.every(v => Number.isFinite(v));
    }

    function quatSlerpFixedBranch(a, b, t) {
      a = quatNormalize(a);
      b = quatNormalize(b);
      const cosTheta = Math.max(-0.999999, Math.min(0.999999, quatDot(a, b)));
      if (cosTheta < -0.9995) return null;
      if (Math.abs(cosTheta) > 0.9995) {
        const q = quatNormalize([
          a[0] + (b[0] - a[0]) * t,
          a[1] + (b[1] - a[1]) * t,
          a[2] + (b[2] - a[2]) * t,
          a[3] + (b[3] - a[3]) * t
        ]);
        return quatIsFinite(q) ? q : null;
      }
      const theta = Math.acos(cosTheta);
      const sinTheta = Math.sin(theta);
      const wa = Math.sin((1 - t) * theta) / sinTheta;
      const wb = Math.sin(t * theta) / sinTheta;
      const q = quatNormalize([
        a[0] * wa + b[0] * wb,
        a[1] * wa + b[1] * wb,
        a[2] * wa + b[2] * wb,
        a[3] * wa + b[3] * wb
      ]);
      return quatIsFinite(q) ? q : null;
    }

    function continuousBlendQuat(idleQuat, targetQuat, alpha, previousQuat) {
      let best = null;
      for (const candidate of [targetQuat, quatNegate(targetQuat)]) {
        const q = quatSlerpFixedBranch(idleQuat, candidate, alpha);
        if (!q) continue;
        const reference = previousQuat || idleQuat;
        const score = Math.abs(quatDot(q, reference));
        if (!best || score > best.score) best = { q, score };
      }
      if (!best) return quatSlerp(idleQuat, targetQuat, alpha);
      let q = best.q;
      if (previousQuat && quatDot(q, previousQuat) < 0) q = quatNegate(q);
      return q;
    }

    function rawBasisAxes(arr, f, j) {
      return orthonormalAxes(
        rawBasisAxis(arr, f, j, 0),
        rawBasisAxis(arr, f, j, 1),
        rawBasisAxis(arr, f, j, 2)
      );
    }

    function basisAxesAt(arr, f, j) {
      const s = sampleInfo(frameCountFromBasis(arr), f);
      const a = rawBasisAxes(arr, s.base, j);
      if (s.t <= 1e-7 || s.base === s.next) return a;
      const b = rawBasisAxes(arr, s.next, j);
      return axesFromQuat(quatSlerp(
        quatFromAxes(a[0], a[1], a[2]),
        quatFromAxes(b[0], b[1], b[2]),
        s.t
      ));
    }

    function basisAxisAt(arr, f, j, axis) {
      return basisAxesAt(arr, f, j)[axis];
    }

    function add3(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
    function sub3(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
    function mul3(a, s) { return [a[0] * s, a[1] * s, a[2] * s]; }
    function lerp3(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
    function dot3(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
    function cross3(a, b) {
      return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]
      ];
    }
    function norm3(a) { return Math.hypot(a[0], a[1], a[2]); }
    function normalize3(a) {
      const n = norm3(a);
      return n > 1e-8 ? [a[0] / n, a[1] / n, a[2] / n] : [1, 0, 0];
    }

    function currentRenderSample() {
      return renderSampleOverride === null ? viewFrame() : renderSampleOverride;
    }

    function renderPosAt(arr, f, j) {
      return add3(posAt(arr, f, j), renderRootOffset);
    }

    function withRenderPose(sampleOverride, rootOffset, fn) {
      const previousSample = renderSampleOverride;
      const previousOffset = renderRootOffset;
      renderSampleOverride = sampleOverride;
      renderRootOffset = rootOffset || [0, 0, 0];
      try {
        return fn();
      } finally {
        renderSampleOverride = previousSample;
        renderRootOffset = previousOffset;
      }
    }

    function writePosAt(arr, f, j, value) {
      const i = (f * J + j) * 3;
      arr[i] = value[0];
      arr[i + 1] = value[1];
      arr[i + 2] = value[2];
    }

    function copyBasisAt(dst, src, dstFrame, srcFrame, j) {
      const dstIndex = (dstFrame * J + j) * 9;
      const srcIndex = (srcFrame * J + j) * 9;
      for (let k = 0; k < 9; k++) dst[dstIndex + k] = src[srcIndex + k];
    }

    function fallbackPoleFor(direction) {
      let pole = cross3(direction, [0, 1, 0]);
      if (norm3(pole) < 1e-5) pole = cross3(direction, [1, 0, 0]);
      return normalize3(pole);
    }

    function legPoleFromKnee(hip, knee, foot) {
      const direction = normalize3(sub3(foot, hip));
      const hipToKnee = sub3(knee, hip);
      const pole = sub3(hipToKnee, mul3(direction, dot3(hipToKnee, direction)));
      return norm3(pole) > 1e-5 ? normalize3(pole) : fallbackPoleFor(direction);
    }

    function basisVectorToLocal(v, basis, frame, joint) {
      return [
        dot3(v, basisAxisAt(basis, frame, joint, 0)),
        dot3(v, basisAxisAt(basis, frame, joint, 1)),
        dot3(v, basisAxisAt(basis, frame, joint, 2))
      ];
    }

    function basisVectorToWorldRaw(v, basis, frame, joint) {
      return add3(
        add3(
          mul3(basisAxisAt(basis, frame, joint, 0), v[0]),
          mul3(basisAxisAt(basis, frame, joint, 1), v[1])
        ),
        mul3(basisAxisAt(basis, frame, joint, 2), v[2])
      );
    }

    function basisVectorToWorld(v, basis, frame, joint) {
      return normalize3(basisVectorToWorldRaw(v, basis, frame, joint));
    }

    function vectorToWorldFromAxes(v, axes) {
      return add3(add3(mul3(axes[0], v[0]), mul3(axes[1], v[1])), mul3(axes[2], v[2]));
    }

    function basisAxesInLocal(srcBasis, srcFrame, srcJoint, targetBasis, targetFrame, targetJoint) {
      return [0, 1, 2].map(axis => basisVectorToLocal(
        basisAxisAt(targetBasis, targetFrame, targetJoint, axis),
        srcBasis,
        srcFrame,
        srcJoint
      ));
    }

    function carriedBasisAxes(srcBasis, srcFrame, srcJoint, localAxes) {
      return orthonormalAxes(
        basisVectorToWorldRaw(localAxes[0], srcBasis, srcFrame, srcJoint),
        basisVectorToWorldRaw(localAxes[1], srcBasis, srcFrame, srcJoint),
        basisVectorToWorldRaw(localAxes[2], srcBasis, srcFrame, srcJoint)
      );
    }

    function writeBasisAxesAt(dst, f, j, axes) {
      const i = (f * J + j) * 9;
      for (let axis = 0; axis < 3; axis++) {
        dst[i + axis * 3] = axes[axis][0];
        dst[i + axis * 3 + 1] = axes[axis][1];
        dst[i + axis * 3 + 2] = axes[axis][2];
      }
    }

    function footLocalPoleForTarget(srcPositions, srcBasis, targetBasis, srcFrame, targetFrame, spec) {
      const hip = posAt(srcPositions, srcFrame, spec.thigh);
      const knee = posAt(srcPositions, srcFrame, spec.calf);
      const foot = posAt(srcPositions, srcFrame, spec.foot);
      const rawPole = legPoleFromKnee(hip, knee, foot);
      const localPole = basisVectorToLocal(rawPole, srcBasis, srcFrame, spec.foot);
      return basisVectorToWorld(localPole, targetBasis, targetFrame, spec.foot);
    }

    function twoBonePoleInfoWithPole(hip, knee, foot, footTarget, poleHint, upperOverride = null, lowerOverride = null) {
      const upperLength = Math.max(1e-5, upperOverride === null ? norm3(sub3(knee, hip)) : upperOverride);
      const lowerLength = Math.max(1e-5, lowerOverride === null ? norm3(sub3(foot, knee)) : lowerOverride);
      const toTarget = sub3(footTarget, hip);
      const actualDistance = norm3(toTarget);
      if (actualDistance < 1e-5) return null;

      const direction = normalize3(toTarget);
      let pole = poleHint || legPoleFromKnee(hip, knee, foot);
      pole = sub3(pole, mul3(direction, dot3(pole, direction)));
      pole = norm3(pole) > 1e-5 ? normalize3(pole) : fallbackPoleFor(direction);

      const minReach = Math.abs(upperLength - lowerLength) + 1e-5;
      const maxReach = upperLength + lowerLength - 1e-5;
      const solvedDistance = clamp(actualDistance, minReach, maxReach);
      const along = (upperLength * upperLength - lowerLength * lowerLength + solvedDistance * solvedDistance) / (2 * solvedDistance);
      const height = Math.sqrt(Math.max(0, upperLength * upperLength - along * along));
      const bendBase = add3(hip, mul3(direction, along));
      const solvedKnee = add3(bendBase, mul3(pole, height));
      return { upperLength, lowerLength, actualDistance, direction, pole, along, height, bendBase, solvedKnee };
    }

    function twoBonePoleInfo(hip, knee, foot, footTarget, kneeHint = null) {
      const poleHint = kneeHint ? sub3(kneeHint, hip) : legPoleFromKnee(hip, knee, foot);
      return twoBonePoleInfoWithPole(hip, knee, foot, footTarget, poleHint);
    }

    function solveTwoBoneKnee(hip, knee, foot, footTarget, kneeHint = null) {
      const info = twoBonePoleInfo(hip, knee, foot, footTarget, kneeHint);
      return info ? info.solvedKnee : knee;
    }

    function solveTwoBoneKneeWithPole(hip, knee, foot, footTarget, poleHint, upperOverride = null, lowerOverride = null) {
      const info = twoBonePoleInfoWithPole(hip, knee, foot, footTarget, poleHint, upperOverride, lowerOverride);
      return info ? info.solvedKnee : knee;
    }

    function clamp(x, lo, hi) {
      return Math.max(lo, Math.min(hi, x));
    }

    function cleanVec3(raw, fallback = null, scale = 1) {
      const values = Array.isArray(raw) ? raw.map(Number) : [];
      if (values.length !== 3 || values.some(v => !Number.isFinite(v))) return fallback ? fallback.slice() : null;
      return values.map(v => v * scale);
    }

    function round6Vec3(v) {
      return v.map(x => Math.round(x * 1_000_000) / 1_000_000);
    }

    function defaultAttackConfig() {
      return {
        blade_length: 1,
        collider: {
          width_offset_cm: 0,
          thickness_offset_cm: 0,
          length_offset_cm: 0
        },
        bound: {
          start: 0,
          end: 1
        },
        hit: 0.5,
        armed_radius_cm: 10,
        melee_target_offset_m: [0, 0, 0],
        melee_target_offset_by_clip: {},
        armed_by_clip: {},
        foot_frame0_lerp_by_clip: {},
        cleanup_by_clip: {},
        target: {
          radius_cm: 10,
          hits_by_clip: {}
        }
      };
    }

    function sanitizeAttackConfig(raw) {
      const cfg = defaultAttackConfig();
      if (!raw || typeof raw !== "object") return cfg;
      const rawBladeLength = raw.blade_length ?? raw.blade?.length;
      if (rawBladeLength !== undefined) {
        const value = Number(rawBladeLength);
        if (Number.isFinite(value)) cfg.blade_length = clamp(value, 0, 1);
      }
      if (raw.collider && typeof raw.collider === "object") {
        cfg.collider.width_offset_cm = clamp(Number(raw.collider.width_offset_cm) || 0, -10, 30);
        cfg.collider.thickness_offset_cm = clamp(Number(raw.collider.thickness_offset_cm) || 0, -10, 30);
        cfg.collider.length_offset_cm = clamp(Number(raw.collider.length_offset_cm) || 0, -40, 80);
      }
      if (raw.bound && typeof raw.bound === "object") {
        cfg.bound.start = clamp(Number(raw.bound.start) || 0, 0, 1);
        cfg.bound.end = clamp(Number(raw.bound.end) || 0, 0, 1);
      }
      cfg.hit = clamp(Number(raw.hit) || 0, 0, 1);
      const rawArmedRadius = raw.armed_radius_cm ?? raw.armed?.radius_cm ?? raw.target?.armed_radius_cm;
      if (rawArmedRadius !== undefined) {
        const value = Number(rawArmedRadius);
        if (Number.isFinite(value)) cfg.armed_radius_cm = clamp(value, 1, 80);
      }
      const meleeOffset = cleanVec3(raw.melee_target_offset_m ?? raw.target?.limb_offset_m ?? raw.target?.melee_offset_m, null);
      if (meleeOffset) cfg.melee_target_offset_m = meleeOffset.map(v => clamp(v, -2, 2));
      const rawMeleeOffsetsByClip = raw.melee_target_offset_by_clip ?? raw.target?.limb_offset_by_clip ?? raw.target?.melee_offset_by_clip;
      if (rawMeleeOffsetsByClip && typeof rawMeleeOffsetsByClip === "object") {
        cfg.melee_target_offset_by_clip = {};
        for (const [clipName, value] of Object.entries(rawMeleeOffsetsByClip)) {
          const offset = cleanVec3(value, null);
          if (!offset) continue;
          cfg.melee_target_offset_by_clip[clipName] = offset.map(v => clamp(v, -2, 2));
        }
      }
      const rawArmed = raw.armed_by_clip ?? raw.armed?.by_clip ?? raw.target?.armed_by_clip;
      if (rawArmed && typeof rawArmed === "object") {
        cfg.armed_by_clip = {};
        for (const [clipName, entry] of Object.entries(rawArmed)) {
          const frameValue = Number(typeof entry === "object" && entry !== null ? entry.frame : entry);
          if (!Number.isFinite(frameValue) || frameValue < 0) continue;
          const clean = {
            frame: Math.round(frameValue * 1_000_000) / 1_000_000,
            radius_cm: clamp(Number(entry?.radius_cm ?? cfg.armed_radius_cm) || cfg.armed_radius_cm, 1, 80),
            hit_t: clamp(Number(entry?.hit_t ?? cfg.hit) || 0, 0, 1),
            blade_length: clamp(Number(entry?.blade_length ?? cfg.blade_length) || 0, 0, 1),
            saved_at: typeof entry === "object" && entry !== null && typeof entry.saved_at === "string" ? entry.saved_at : ""
          };
          const bladePelvis = Array.isArray(entry?.armed_blade_pelvis_m)
            ? entry.armed_blade_pelvis_m.map(Number)
            : [];
          if (bladePelvis.length === 3 && !bladePelvis.some(v => !Number.isFinite(v))) {
            clean.armed_blade_pelvis_m = bladePelvis;
          }
          const handPelvis = Array.isArray(entry?.armed_hand_pelvis_m)
            ? entry.armed_hand_pelvis_m.map(Number)
            : [];
          if (handPelvis.length === 3 && !handPelvis.some(v => !Number.isFinite(v))) {
            clean.armed_hand_pelvis_m = handPelvis;
          }
          if (typeof entry?.target_mode === "string") clean.target_mode = entry.target_mode;
          if (typeof entry?.target_space === "string") clean.target_space = entry.target_space;
          if (typeof entry?.armed_limb_joint === "string") clean.armed_limb_joint = entry.armed_limb_joint;
          const limbIndex = Number(entry?.armed_limb_index);
          if (Number.isInteger(limbIndex) && limbIndex >= 0) clean.armed_limb_index = limbIndex;
          const limbPelvis = cleanVec3(entry?.armed_limb_pelvis_m, null);
          if (limbPelvis) clean.armed_limb_pelvis_m = limbPelvis;
          const limbOffset = cleanVec3(entry?.armed_limb_local_offset_m, null);
          if (limbOffset) clean.armed_limb_local_offset_m = limbOffset;
          const targetFrameOrigin = cleanVec3(entry?.armed_target_frame_origin_m, null);
          if (targetFrameOrigin) clean.armed_target_frame_origin_m = targetFrameOrigin;
          cfg.armed_by_clip[clipName] = clean;
        }
      }
      const rawFootLocks = raw.foot_frame0_lerp_by_clip ?? raw.foot_locks_by_clip;
      if (rawFootLocks && typeof rawFootLocks === "object") {
        cfg.foot_frame0_lerp_by_clip = {};
        for (const [clipName, entry] of Object.entries(rawFootLocks)) {
          if (!entry || typeof entry !== "object") continue;
          cfg.foot_frame0_lerp_by_clip[clipName] = {
            left: clamp(Number(entry.left ?? entry.l ?? entry.foot_l ?? 0) || 0, 0, 1),
            right: clamp(Number(entry.right ?? entry.r ?? entry.foot_r ?? 0) || 0, 0, 1)
          };
        }
      }
      const rawCleanup = raw.cleanup_by_clip ?? raw.cleanup?.by_clip ?? raw.pelvis_cleanup_by_clip;
      if (rawCleanup && typeof rawCleanup === "object") {
        cfg.cleanup_by_clip = {};
        for (const [clipName, entry] of Object.entries(rawCleanup)) {
          if (!entry || typeof entry !== "object") continue;
          const extraOffset = cleanVec3(entry.extra_pelvis_offset_m ?? entry.extraPelvisOffsetM, null)
            || cleanVec3(entry.extra_pelvis_offset_cm, [0, 0, 0], 0.01);
          cfg.cleanup_by_clip[clipName] = {
            pelvis_offset_scale: clamp(Number(entry.pelvis_offset_scale ?? entry.pelvisOffsetScale ?? 1) || 0, 0, 1),
            pelvis_source_blend: clamp(Number(entry.pelvis_source_blend ?? entry.pelvisSourceBlend ?? 0) || 0, 0, 1),
            extra_pelvis_offset_m: extraOffset.map(v => clamp(v, -2, 2))
          };
        }
      }
      if (raw.target && typeof raw.target === "object") {
        cfg.target.radius_cm = clamp(Number(raw.target.radius_cm) || 10, 1, 80);
        if (raw.target.hits_by_clip && typeof raw.target.hits_by_clip === "object") {
          cfg.target.hits_by_clip = {};
          for (const [clipName, entries] of Object.entries(raw.target.hits_by_clip)) {
            if (!Array.isArray(entries)) continue;
            const cleanEntries = [];
            for (const entry of entries) {
              if (!entry || typeof entry !== "object") continue;
              const frameValue = Number(entry.frame);
              if (!Number.isFinite(frameValue) || frameValue < 0) continue;
              const hitWorld = Array.isArray(entry.hit_world_m) ? entry.hit_world_m.map(Number) : [];
              if (hitWorld.length !== 3 || hitWorld.some(v => !Number.isFinite(v))) continue;
              cleanEntries.push({
                frame: Math.round(frameValue * 1_000_000) / 1_000_000,
                hit_t: clamp(Number(entry.hit_t) || 0, 0, 1),
                blade_length: clamp(Number(entry.blade_length ?? 1) || 0, 0, 1),
                hit_world_m: hitWorld,
                saved_at: typeof entry.saved_at === "string" ? entry.saved_at : ""
              });
              const clean = cleanEntries[cleanEntries.length - 1];
              if (typeof entry.target_mode === "string") clean.target_mode = entry.target_mode;
              if (typeof entry.target_space === "string") clean.target_space = entry.target_space;
              if (typeof entry.hit_joint === "string") clean.hit_joint = entry.hit_joint;
              const hitJointIndex = Number(entry.hit_joint_index);
              if (Number.isInteger(hitJointIndex) && hitJointIndex >= 0) clean.hit_joint_index = hitJointIndex;
              const hitOffset = cleanVec3(entry.hit_local_offset_m, null);
              if (hitOffset) clean.hit_local_offset_m = hitOffset;
              const limbWorld = cleanVec3(entry.hit_limb_world_m, null);
              if (limbWorld) clean.hit_limb_world_m = limbWorld;
              const targetFrameOrigin = cleanVec3(entry.hit_target_frame_origin_m, null);
              if (targetFrameOrigin) clean.hit_target_frame_origin_m = targetFrameOrigin;
            }
            cleanEntries.sort((a, b) => {
              const at = Date.parse(a.saved_at || "") || 0;
              const bt = Date.parse(b.saved_at || "") || 0;
              if (at !== bt) return at - bt;
              return a.frame - b.frame;
            });
            cfg.target.hits_by_clip[clipName] = cleanEntries.length ? [cleanEntries[cleanEntries.length - 1]] : [];
          }
        }
      }
      return cfg;
    }

    function attackConfigFromUi() {
      return sanitizeAttackConfig({
        blade_length: (Number(bladeSlider.value) || 0) / 100,
        collider: {
          width_offset_cm: Number(attackInputs.widthOffsetCm.value) || 0,
          thickness_offset_cm: Number(attackInputs.thicknessOffsetCm.value) || 0,
          length_offset_cm: Number(attackInputs.lengthOffsetCm.value) || 0
        },
        bound: {
          start: Number(attackInputs.boundStart.value) || 0,
          end: Number(attackInputs.boundEnd.value) || 0
        },
        hit: Number(attackInputs.hit.value) || 0,
        armed_radius_cm: Number(attackInputs.armedRadiusCm.value) || attackConfig.armed_radius_cm,
        melee_target_offset_m: attackConfig.melee_target_offset_m,
        melee_target_offset_by_clip: attackConfig.melee_target_offset_by_clip,
        armed_by_clip: attackConfig.armed_by_clip,
        foot_frame0_lerp_by_clip: attackConfig.foot_frame0_lerp_by_clip,
        cleanup_by_clip: attackConfig.cleanup_by_clip,
        target: {
          radius_cm: Number(attackInputs.targetRadiusCm.value) || attackConfig.target.radius_cm,
          hits_by_clip: attackConfig.target.hits_by_clip
        }
      });
    }

    function writeAttackUi(options = {}) {
      const writeMeleeTargetInputs = options.writeMeleeTargetInputs !== false;
      attackInputs.widthOffsetCm.value = String(attackConfig.collider.width_offset_cm);
      attackInputs.thicknessOffsetCm.value = String(attackConfig.collider.thickness_offset_cm);
      attackInputs.lengthOffsetCm.value = String(attackConfig.collider.length_offset_cm);
      attackInputs.targetRadiusCm.value = String(attackConfig.target.radius_cm);
      attackInputs.armedRadiusCm.value = String(attackConfig.armed_radius_cm);
      if (writeMeleeTargetInputs) {
        attackInputs.meleeTargetXCm.value = String(workingMeleeTargetOffsetM[0] * 100);
        attackInputs.meleeTargetYCm.value = String(workingMeleeTargetOffsetM[1] * 100);
        attackInputs.meleeTargetZCm.value = String(workingMeleeTargetOffsetM[2] * 100);
      }
      attackInputs.boundStart.value = String(attackConfig.bound.start);
      attackInputs.boundEnd.value = String(attackConfig.bound.end);
      attackInputs.hit.value = String(attackConfig.hit);
      attackOutputs.widthOffsetCm.value = attackConfig.collider.width_offset_cm.toFixed(1);
      attackOutputs.thicknessOffsetCm.value = attackConfig.collider.thickness_offset_cm.toFixed(1);
      attackOutputs.lengthOffsetCm.value = attackConfig.collider.length_offset_cm.toFixed(1);
      attackOutputs.targetRadiusCm.value = attackConfig.target.radius_cm.toFixed(1);
      attackOutputs.armedRadiusCm.value = attackConfig.armed_radius_cm.toFixed(1);
      attackOutputs.meleeTargetXCm.value = (workingMeleeTargetOffsetM[0] * 100).toFixed(1);
      attackOutputs.meleeTargetYCm.value = (workingMeleeTargetOffsetM[1] * 100).toFixed(1);
      attackOutputs.meleeTargetZCm.value = (workingMeleeTargetOffsetM[2] * 100).toFixed(1);
      attackOutputs.boundStart.value = attackConfig.bound.start.toFixed(3);
      attackOutputs.boundEnd.value = attackConfig.bound.end.toFixed(3);
      attackOutputs.hit.value = attackConfig.hit.toFixed(3);
      const meleeInfo = isMeleeClip(activeClip) ? meleeStrikeJointInfo() : null;
      const meleeLabel = meleeInfo ? meleeInfo.name : "n/a";
      meleeTargetLimbText.value = meleeLabel;
      meleeTargetLimbText.textContent = meleeLabel;
      bladeScale = attackConfig.blade_length;
      bladeSlider.value = String(Math.round(bladeScale * 100));
      bladeText.textContent = `${Math.round(bladeScale * 100)}%`;
      refreshSnapArmedFrameButton();
      refreshSnapHitFrameButton();
    }

    function configFileNameForClip(clip) {
      return isMeleeClip(clip) ? "melee_attack_config.json" : "slash_attack_config.json";
    }

    function setAttackConfigForActiveClip() {
      attackConfig = isMeleeClip(activeClip) ? meleeAttackConfig : slashAttackConfig;
    }

    async function fetchAttackConfig(fileName) {
      try {
        const response = await fetch(fileName, { cache: "no-store" });
        if (response.ok) return sanitizeAttackConfig(await response.json());
      } catch {
      }
      return defaultAttackConfig();
    }

    async function loadAttackConfig() {
      if (isCombinedAttackSet) {
        slashAttackConfig = await fetchAttackConfig("slash_attack_config.json");
        meleeAttackConfig = await fetchAttackConfig("melee_attack_config.json");
      } else if (isMeleeClipSet) {
        meleeAttackConfig = await fetchAttackConfig("melee_attack_config.json");
        slashAttackConfig = defaultAttackConfig();
      } else {
        slashAttackConfig = await fetchAttackConfig("slash_attack_config.json");
        meleeAttackConfig = defaultAttackConfig();
      }
      setAttackConfigForActiveClip();
      attackSaveState.textContent = "";
      loadMeleeTargetOffsetFromActiveClip();
      loadCleanupFromActiveClip();
      writeAttackUi();
      loadFootLockFromActiveClip();
      prepareIdleFootIkForAllClips();
      draw();
    }

    async function persistAttackConfig(successText) {
      saveAttackButton.disabled = true;
      saveHitButton.disabled = true;
      saveArmedButton.disabled = true;
      snapBetweenButton.disabled = true;
      snapArmedFrameButton.disabled = true;
      snapHitFrameButton.disabled = true;
      saveFootLockButton.disabled = true;
      attackSaveState.textContent = "saving";
      let ok = false;
      try {
        if (isMeleeClip(activeClip)) {
          meleeAttackConfig = attackConfig;
        } else {
          slashAttackConfig = attackConfig;
        }
        const response = await fetch(configFileNameForClip(activeClip), {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(attackConfig, null, 2)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        attackSaveState.textContent = successText;
        ok = true;
      } catch {
        attackSaveState.textContent = "save failed";
      } finally {
        saveAttackButton.disabled = false;
        saveHitButton.disabled = false;
        saveArmedButton.disabled = false;
        snapBetweenButton.disabled = false;
        saveFootLockButton.disabled = false;
        refreshSnapArmedFrameButton();
        refreshSnapHitFrameButton();
      }
      return ok;
    }

    async function saveAttackConfig() {
      updateWorkingMeleeTargetOffsetFromUi();
      updateWorkingCleanupFromUi();
      attackConfig = attackConfigFromUi();
      saveWorkingMeleeTargetOffsetToActiveClip();
      saveWorkingCleanupToActiveClip();
      writeAttackUi();
      await persistAttackConfig("saved");
    }

    async function saveHitConfig() {
      updateWorkingMeleeTargetOffsetFromUi();
      updateWorkingCleanupFromUi();
      attackConfig = attackConfigFromUi();
      saveWorkingMeleeTargetOffsetToActiveClip();
      saveWorkingCleanupToActiveClip();
      const hitWorld = currentHitWorldPoint();
      if (!hitWorld) {
        attackSaveState.textContent = "no target";
        return;
      }
      const sample = Math.round(viewFrame() * 1_000_000) / 1_000_000;
      const meleeInfo = isMeleeClip(activeClip) ? meleeStrikeJointInfo() : null;
      const arr = activePositions();
      const bas = activeBasis();
      const targetFrame = meleeInfo ? meleeTargetFrame(arr, bas, sample, meleeInfo) : null;
      const clipName = activeClip.name;
      const entry = {
        frame: sample,
        hit_t: Math.round(attackConfig.hit * 1_000_000) / 1_000_000,
        blade_length: Math.round(attackConfig.blade_length * 1_000_000) / 1_000_000,
        hit_world_m: round6Vec3(hitWorld),
        saved_at: new Date().toISOString()
      };
      if (meleeInfo) {
        entry.target_mode = "limb_local";
        entry.target_space = targetFrame?.space || "joint_local";
        entry.hit_joint = meleeInfo.name;
        entry.hit_joint_index = meleeInfo.index;
        entry.hit_local_offset_m = round6Vec3(meleeTargetOffsetM());
        entry.hit_limb_world_m = round6Vec3(posAt(arr, sample, meleeInfo.index));
        if (targetFrame) entry.hit_target_frame_origin_m = round6Vec3(targetFrame.origin);
      }
      attackConfig.target.hits_by_clip[clipName] = [entry];
      writeAttackUi();
      draw();
      await persistAttackConfig("hit saved");
    }

    async function saveArmedConfig() {
      updateWorkingMeleeTargetOffsetFromUi();
      updateWorkingCleanupFromUi();
      attackConfig = attackConfigFromUi();
      saveWorkingMeleeTargetOffsetToActiveClip();
      saveWorkingCleanupToActiveClip();
      const hitWorld = currentHitWorldPoint();
      if (!hitWorld) {
        attackSaveState.textContent = "no target";
        return;
      }
      const sample = Math.round(viewFrame() * 1_000_000) / 1_000_000;
      const arr = activePositions();
      const bas = activeBasis();
      const meleeInfo = isMeleeClip(activeClip) ? meleeStrikeJointInfo() : null;
      const targetFrame = meleeInfo ? meleeTargetFrame(arr, bas, sample, meleeInfo) : null;
      const limbIndex = meleeInfo ? meleeInfo.index : swordHandIndex;
      if (limbIndex === undefined) {
        attackSaveState.textContent = "no limb";
        return;
      }
      const bladePelvis = round6Vec3(worldToPelvisLocalAt(hitWorld, arr, bas, sample));
      const limbWorld = posAt(arr, sample, limbIndex);
      const limbPelvis = round6Vec3(worldToPelvisLocalAt(limbWorld, arr, bas, sample));
      const entry = {
        frame: sample,
        radius_cm: Math.round(attackConfig.armed_radius_cm * 1_000_000) / 1_000_000,
        hit_t: Math.round(attackConfig.hit * 1_000_000) / 1_000_000,
        blade_length: Math.round(attackConfig.blade_length * 1_000_000) / 1_000_000,
        armed_blade_pelvis_m: bladePelvis,
        armed_hand_pelvis_m: limbPelvis,
        saved_at: new Date().toISOString()
      };
      if (meleeInfo) {
        entry.target_mode = "limb_local";
        entry.target_space = targetFrame?.space || "joint_local";
        entry.armed_limb_joint = meleeInfo.name;
        entry.armed_limb_index = meleeInfo.index;
        entry.armed_limb_pelvis_m = limbPelvis;
        entry.armed_limb_local_offset_m = round6Vec3(meleeTargetOffsetM());
        if (targetFrame) entry.armed_target_frame_origin_m = round6Vec3(targetFrame.origin);
      }
      attackConfig.armed_by_clip[activeClip.name] = entry;
      writeAttackUi();
      prepareIdleFootIkForAllClips();
      draw();
      await persistAttackConfig("armed saved");
    }

    function snapBetweenToConfig() {
      updateWorkingMeleeTargetOffsetFromUi();
      attackConfig = attackConfigFromUi();
      snapToHitFrame();
    }

    function hitEntriesForActiveClip() {
      const hits = attackConfig.target.hits_by_clip[activeClip.name] || [];
      return hits
        .map(entry => ({
          frame: Number(entry.frame),
          hit_t: Number(entry.hit_t),
          blade_length: Number(entry.blade_length)
        }))
        .filter(entry => Number.isFinite(entry.frame));
    }

    function nearestHitEntryForActiveClip() {
      const validHits = hitEntriesForActiveClip();
      if (!validHits.length) {
        return null;
      }
      const baseFrame = frame;
      const current = viewFrame();
      const sameBase = validHits.filter(entry => Math.floor(entry.frame) === baseFrame);
      const pool = sameBase.length ? sameBase : validHits;
      let best = pool[0];
      let bestDistance = Math.abs(pool[0].frame - current);
      for (const entry of pool.slice(1)) {
        const distance = Math.abs(entry.frame - current);
        if (distance < bestDistance) {
          best = entry;
          bestDistance = distance;
        }
      }
      return best;
    }

    function refreshSnapHitFrameButton() {
      const entry = nearestHitEntryForActiveClip();
      snapHitFrameButton.disabled = !entry;
      snapHitFrameButton.title = entry
        ? `Jump to saved hit frame ${formatFrameValue(entry.frame)}`
        : "No saved hit frame for this clip";
    }

    function armedEntryForActiveClip() {
      const entry = attackConfig.armed_by_clip?.[activeClip.name];
      if (!entry) return null;
      const frameValue = Number(entry.frame);
      if (!Number.isFinite(frameValue)) return null;
      return {
        frame: frameValue,
        hit_t: Number(entry.hit_t),
        blade_length: Number(entry.blade_length)
      };
    }

    function refreshSnapArmedFrameButton() {
      const entry = armedEntryForActiveClip();
      snapArmedFrameButton.disabled = !entry;
      snapArmedFrameButton.title = entry
        ? `Jump to saved armed frame ${formatFrameValue(entry.frame)}`
        : "No saved armed frame for this clip";
    }

    function snapToArmedFrame() {
      const entry = armedEntryForActiveClip();
      if (!entry) {
        attackSaveState.textContent = "no armed config";
        refreshSnapArmedFrameButton();
        return;
      }
      setPlaying(false);
      if (Number.isFinite(entry.hit_t)) attackConfig.hit = clamp(entry.hit_t, 0, 1);
      if (Number.isFinite(entry.blade_length)) attackConfig.blade_length = clamp(entry.blade_length, 0, 1);
      writeAttackUi();
      setFrameExact(entry.frame);
      attackSaveState.textContent = `armed ${formatFrameValue(viewFrame())}`;
    }

    function snapToHitFrame() {
      const best = nearestHitEntryForActiveClip();
      if (!best) {
        attackSaveState.textContent = "no hit config";
        refreshSnapHitFrameButton();
        return;
      }
      setPlaying(false);
      if (Number.isFinite(best.hit_t)) attackConfig.hit = clamp(best.hit_t, 0, 1);
      if (Number.isFinite(best.blade_length)) attackConfig.blade_length = clamp(best.blade_length, 0, 1);
      writeAttackUi();
      setFrameExact(best.frame);
      attackSaveState.textContent = `snapped ${formatFrameValue(viewFrame())}`;
    }

    function bladeCrossAxes() {
      const axes = [0, 1, 2].filter(axis => axis !== sword.blade_axis);
      axes.sort((a, b) => {
        const da = sword.blade_bounds_max_m[a] - sword.blade_bounds_min_m[a];
        const db = sword.blade_bounds_max_m[b] - sword.blade_bounds_min_m[b];
        return db - da;
      });
      return { width: axes[0], thickness: axes[1] };
    }

    const edgePairs = parents.map((parent, child) => [parent, child]).filter(([parent]) => parent >= 0);

    const volumeSpecs = [
      ["pelvis", "spine_01", 0.125], ["spine_01", "spine_02", 0.135], ["spine_02", "spine_03", 0.145],
      ["spine_03", "spine_04", 0.145], ["spine_04", "spine_05", 0.135], ["spine_05", "neck_01", 0.085],
      ["neck_02", "head", 0.100],
      ["clavicle_l", "upperarm_l", 0.055], ["upperarm_l", "lowerarm_l", 0.058], ["lowerarm_l", "hand_l", 0.048],
      ["clavicle_r", "upperarm_r", 0.055], ["upperarm_r", "lowerarm_r", 0.058], ["lowerarm_r", "hand_r", 0.048],
      ["pelvis", "thigh_l", 0.095], ["thigh_l", "calf_l", 0.083], ["calf_l", "foot_l", 0.062],
      ["pelvis", "thigh_r", 0.095], ["thigh_r", "calf_r", 0.083], ["calf_r", "foot_r", 0.062]
    ].map(([a, b, r]) => ({ a: nameToIndex.get(a), b: nameToIndex.get(b), r })).filter(v => v.a !== undefined && v.b !== undefined);

    const footSpecs = [
      { ankle: nameToIndex.get("foot_l"), toe: nameToIndex.get("ball_l"), side: 0 },
      { ankle: nameToIndex.get("foot_r"), toe: nameToIndex.get("ball_r"), side: 1 }
    ].filter(v => v.ankle !== undefined && v.toe !== undefined);

    const handSpecs = [
      { hand: nameToIndex.get("hand_l"), lower: nameToIndex.get("lowerarm_l"), side: 0 },
      { hand: nameToIndex.get("hand_r"), lower: nameToIndex.get("lowerarm_r"), side: 1 }
    ].filter(v => v.hand !== undefined && v.lower !== undefined);
    const swordHandIndex = sword ? nameToIndex.get(sword.hand_node) : undefined;
    const swordCrossAxes = sword ? bladeCrossAxes() : null;
    const FOOT_IK_TARGET_FRAME = 0;
    const IDLE_FOOT_REFERENCE_FRAME = 0;
    const legIkSpecs = [
      {
        side: "left",
        thigh: nameToIndex.get("thigh_l"),
        calf: nameToIndex.get("calf_l"),
        foot: nameToIndex.get("foot_l"),
        ball: nameToIndex.get("ball_l")
      },
      {
        side: "right",
        thigh: nameToIndex.get("thigh_r"),
        calf: nameToIndex.get("calf_r"),
        foot: nameToIndex.get("foot_r"),
        ball: nameToIndex.get("ball_r")
      }
    ].filter(spec => spec.thigh !== undefined && spec.calf !== undefined && spec.foot !== undefined && spec.ball !== undefined);

    function isDescendantOf(index, ancestor) {
      for (let j = index; j >= 0; j = parents[j]) {
        if (j === ancestor) return true;
      }
      return false;
    }

    const pelvisDescendantBones = Array.from({ length: J }, (_, index) => index)
      .filter(index => isDescendantOf(index, pelvisIndex));

    function freeLegSideForClip(clip) {
      const name = String(clip?.name || "").toLowerCase();
      if (name.includes("kickr")) return "right";
      if (name.includes("kickl")) return "left";
      return null;
    }

    function pelvisOffsetBonesForClip(clip) {
      const excluded = new Set();
      for (const spec of legIkSpecs) {
        excluded.add(spec.calf);
        excluded.add(spec.foot);
        excluded.add(spec.ball);
      }
      return pelvisDescendantBones.filter(index => !excluded.has(index));
    }

    function firstFrameFootDeltas(clip, targetFrame, idleFrame, rootOffset, freeLegSide = null) {
      const legTargets = [];
      let freeLegTarget = null;
      let meanFootDelta = [0, 0, 0];
      let meanFootCount = 0;
      for (const spec of legIkSpecs) {
        const footTarget = add3(posAt(idleClip.positions, idleFrame, spec.foot), rootOffset);
        const footDelta = sub3(footTarget, posAt(clip.positions, targetFrame, spec.foot));
        const target = {
          spec,
          footIkDelta: footDelta,
          footLocalAxes: basisAxesInLocal(clip.basis, targetFrame, spec.foot, idleClip.basis, idleFrame, spec.foot),
          idlePoleLocal: basisVectorToLocal(
            legPoleFromKnee(
              posAt(idleClip.positions, idleFrame, spec.thigh),
              posAt(idleClip.positions, idleFrame, spec.calf),
              posAt(idleClip.positions, idleFrame, spec.foot)
            ),
            idleClip.basis,
            idleFrame,
            spec.foot
          ),
          idleBallLocal: basisVectorToLocal(
            sub3(posAt(idleClip.positions, idleFrame, spec.ball), posAt(idleClip.positions, idleFrame, spec.foot)),
            idleClip.basis,
            idleFrame,
            spec.foot
          ),
          idleBallLocalAxes: basisAxesInLocal(idleClip.basis, idleFrame, spec.foot, idleClip.basis, idleFrame, spec.ball)
        };
        meanFootDelta = add3(meanFootDelta, footDelta);
        meanFootCount += 1;
        if (spec.side === freeLegSide) {
          freeLegTarget = target;
          continue;
        }
        legTargets.push(target);
      }
      if (meanFootCount > 0) meanFootDelta = mul3(meanFootDelta, 1 / meanFootCount);
      return {
        legTargets,
        freeLegTarget,
        meanGroundDelta: [meanFootDelta[0], 0, meanFootDelta[2]]
      };
    }

    function savedFootFrame0LerpForClip(clip) {
      const entry = attackConfig.foot_frame0_lerp_by_clip?.[clip.name] || {};
      return {
        left: clamp(Number(entry.left) || 0, 0, 1),
        right: clamp(Number(entry.right) || 0, 0, 1)
      };
    }

    function footFrame0LerpForClip(clip) {
      if (clip === activeClip) return workingFootFrame0Lerp;
      return savedFootFrame0LerpForClip(clip);
    }

    function savedCleanupForClip(clip) {
      const entry = attackConfig.cleanup_by_clip?.[clip.name] || {};
      const extraOffset = cleanVec3(entry.extra_pelvis_offset_m ?? entry.extraPelvisOffsetM, null)
        || cleanVec3(entry.extra_pelvis_offset_cm, [0, 0, 0], 0.01);
      return {
        pelvis_offset_scale: clamp(Number(entry.pelvis_offset_scale ?? entry.pelvisOffsetScale ?? 1) || 0, 0, 1),
        pelvis_source_blend: clamp(Number(entry.pelvis_source_blend ?? entry.pelvisSourceBlend ?? 0) || 0, 0, 1),
        extra_pelvis_offset_m: extraOffset.map(v => clamp(v, -2, 2))
      };
    }

    function cleanupForClip(clip) {
      if (clip === activeClip) {
        return {
          pelvis_offset_scale: pelvisOffsetScale,
          pelvis_source_blend: pelvisSourceBlend,
          extra_pelvis_offset_m: extraPelvisOffsetM.slice()
        };
      }
      return savedCleanupForClip(clip);
    }

    function writeCleanupUi() {
      pelvisOffsetInput.value = String(pelvisOffsetScale);
      pelvisOffsetText.textContent = pelvisOffsetScale.toFixed(2);
      pelvisSourceInput.value = String(pelvisSourceBlend);
      pelvisSourceText.textContent = pelvisSourceBlend.toFixed(2);
      extraPelvisInputs.x.value = String(Math.round(extraPelvisOffsetM[0] * 1000) / 10);
      extraPelvisInputs.y.value = String(Math.round(extraPelvisOffsetM[1] * 1000) / 10);
      extraPelvisInputs.z.value = String(Math.round(extraPelvisOffsetM[2] * 1000) / 10);
    }

    function readExtraPelvisOffsetUi() {
      const readCm = input => {
        const value = Number(input.value);
        return Number.isFinite(value) ? value * 0.01 : 0;
      };
      return [
        clamp(readCm(extraPelvisInputs.x), -2, 2),
        clamp(readCm(extraPelvisInputs.y), -2, 2),
        clamp(readCm(extraPelvisInputs.z), -2, 2)
      ];
    }

    function updateWorkingCleanupFromUi() {
      pelvisOffsetScale = clamp(Number(pelvisOffsetInput.value) || 0, 0, 1);
      pelvisSourceBlend = clamp(Number(pelvisSourceInput.value) || 0, 0, 1);
      extraPelvisOffsetM = readExtraPelvisOffsetUi();
      pelvisOffsetText.textContent = pelvisOffsetScale.toFixed(2);
      pelvisSourceText.textContent = pelvisSourceBlend.toFixed(2);
    }

    function loadCleanupFromActiveClip() {
      const values = savedCleanupForClip(activeClip);
      pelvisOffsetScale = values.pelvis_offset_scale;
      pelvisSourceBlend = values.pelvis_source_blend;
      extraPelvisOffsetM = values.extra_pelvis_offset_m.slice();
      writeCleanupUi();
    }

    function saveWorkingCleanupToActiveClip() {
      attackConfig.cleanup_by_clip[activeClip.name] = {
        pelvis_offset_scale: pelvisOffsetScale,
        pelvis_source_blend: pelvisSourceBlend,
        extra_pelvis_offset_m: extraPelvisOffsetM.slice()
      };
    }

    function savedMeleeTargetOffsetForClip(clip) {
      const byClipOffset = cleanVec3(attackConfig.melee_target_offset_by_clip?.[clip.name], null);
      if (byClipOffset) return byClipOffset;
      const hits = attackConfig.target.hits_by_clip?.[clip.name] || [];
      if (hits.length) {
        const hitOffset = cleanVec3(hits[hits.length - 1]?.hit_local_offset_m, null);
        if (hitOffset) return hitOffset;
      }
      return [0, 0, 0];
    }

    function readMeleeTargetOffsetUi() {
      const readCm = input => {
        const value = Number(input.value);
        return Number.isFinite(value) ? value * 0.01 : 0;
      };
      return [
        clamp(readCm(attackInputs.meleeTargetXCm), -2, 2),
        clamp(readCm(attackInputs.meleeTargetYCm), -2, 2),
        clamp(readCm(attackInputs.meleeTargetZCm), -2, 2)
      ];
    }

    function loadMeleeTargetOffsetFromActiveClip() {
      workingMeleeTargetOffsetM = isMeleeClip(activeClip) ? savedMeleeTargetOffsetForClip(activeClip) : [0, 0, 0];
    }

    function updateWorkingMeleeTargetOffsetFromUi() {
      workingMeleeTargetOffsetM = readMeleeTargetOffsetUi();
      return workingMeleeTargetOffsetM;
    }

    function saveWorkingMeleeTargetOffsetToActiveClip() {
      if (!isMeleeClip(activeClip)) return;
      attackConfig.melee_target_offset_by_clip[activeClip.name] = workingMeleeTargetOffsetM.slice();
    }

    function writeFootLockUi() {
      const values = workingFootFrame0Lerp;
      footLockInputs.left.value = String(values.left);
      footLockInputs.right.value = String(values.right);
      footLockTexts.left.textContent = values.left.toFixed(2);
      footLockTexts.right.textContent = values.right.toFixed(2);
    }

    function loadFootLockFromActiveClip() {
      workingFootFrame0Lerp = savedFootFrame0LerpForClip(activeClip);
      writeFootLockUi();
      footLockSaveState.textContent = "";
    }

    function readFootLockUi() {
      return {
        left: clamp(Number(footLockInputs.left.value) || 0, 0, 1),
        right: clamp(Number(footLockInputs.right.value) || 0, 0, 1)
      };
    }

    function updateWorkingFootLockFromUi() {
      const values = readFootLockUi();
      workingFootFrame0Lerp = values;
      footLockTexts.left.textContent = values.left.toFixed(2);
      footLockTexts.right.textContent = values.right.toFixed(2);
      footLockSaveState.textContent = "";
      return workingFootFrame0Lerp;
    }

    function saveWorkingFootLockToActiveClip() {
      attackConfig.foot_frame0_lerp_by_clip[activeClip.name] = {
        left: workingFootFrame0Lerp.left,
        right: workingFootFrame0Lerp.right
      };
    }

    function slerpAxes(a, b, t) {
      if (t <= 1e-7) return a;
      if (t >= 1 - 1e-7) return b;
      return axesFromQuat(quatSlerp(
        quatFromAxes(a[0], a[1], a[2]),
        quatFromAxes(b[0], b[1], b[2]),
        t
      ));
    }

    function carriedChildAxesFromParent(parentAxes, childLocalAxes) {
      return orthonormalAxes(
        vectorToWorldFromAxes(childLocalAxes[0], parentAxes),
        vectorToWorldFromAxes(childLocalAxes[1], parentAxes),
        vectorToWorldFromAxes(childLocalAxes[2], parentAxes)
      );
    }

    function applyFootFrame0Lerp(clip, positions, basis) {
      const values = footFrame0LerpForClip(clip);
      if (values.left <= 1e-7 && values.right <= 1e-7) return;
      const freeSide = freeLegSideForClip(clip);
      for (const spec of legIkSpecs) {
        if (spec.side === freeSide) continue;
        const amount = spec.side === "left" ? values.left : values.right;
        if (amount <= 1e-7) continue;
        const footPos0 = posAt(positions, 0, spec.foot);
        const footAxes0 = basisAxesAt(basis, 0, spec.foot);
        const poleLocal0 = normalize3(basisVectorToLocal(
          legPoleFromKnee(
            posAt(positions, 0, spec.thigh),
            posAt(positions, 0, spec.calf),
            footPos0
          ),
          basis,
          0,
          spec.foot
        ));
        for (let f = 0; f < clip.frame_count; f++) {
          const hip = posAt(positions, f, spec.thigh);
          const knee = posAt(positions, f, spec.calf);
          const foot = posAt(positions, f, spec.foot);
          const ball = posAt(positions, f, spec.ball);
          const footTarget = lerp3(foot, footPos0, amount);
          const footTargetAxes = slerpAxes(basisAxesAt(basis, f, spec.foot), footAxes0, amount);
          const ballLocal = basisVectorToLocal(sub3(ball, foot), basis, f, spec.foot);
          const ballTarget = add3(footTarget, vectorToWorldFromAxes(ballLocal, footTargetAxes));
          const ballLocalAxes = basisAxesInLocal(basis, f, spec.foot, basis, f, spec.ball);
          const ballTargetAxes = carriedChildAxesFromParent(footTargetAxes, ballLocalAxes);
          const rawPole = legPoleFromKnee(hip, knee, foot);
          const poleLocal = normalize3(basisVectorToLocal(rawPole, basis, f, spec.foot));
          const targetPoleLocal = normalize3(lerp3(poleLocal, poleLocal0, amount));
          const carriedPole = normalize3(vectorToWorldFromAxes(targetPoleLocal, footTargetAxes));
          const solvedKnee = solveTwoBoneKneeWithPole(hip, knee, foot, footTarget, carriedPole);

          writePosAt(positions, f, spec.calf, solvedKnee);
          writePosAt(positions, f, spec.foot, footTarget);
          writePosAt(positions, f, spec.ball, ballTarget);
          writeBasisAxesAt(basis, f, spec.foot, footTargetAxes);
          writeBasisAxesAt(basis, f, spec.ball, ballTargetAxes);
        }
      }
    }

    function armedFrameForClip(clip) {
      const entry = attackConfig.armed_by_clip[clip.name];
      const value = Number(entry?.frame);
      if (!Number.isFinite(value) || value <= 0) return null;
      return Math.min(clip.frame_count - 1, Math.max(0, value));
    }

    function blendIdleToArmed(clip, positions, basis, idleFrame, rootOffset) {
      if (!idleClip) return;
      if (isMeleeClip(clip)) return;
      const armedFrame = armedFrameForClip(clip);
      if (armedFrame === null) return;
      const fullFrame = Math.max(0, Math.floor(armedFrame + 1e-6));
      if (fullFrame <= 0) return;
      const idleAxesByJoint = Array.from({ length: J }, (_, j) => rawBasisAxes(idleClip.basis, idleFrame, j));
      const idleQuatByJoint = idleAxesByJoint.map(axes => quatFromAxes(axes[0], axes[1], axes[2]));
      const previousBlendQuatByJoint = new Array(J).fill(null);

      for (let f = 0; f <= fullFrame && f < clip.frame_count; f++) {
        const alpha = f >= fullFrame ? 1 : clamp(f / armedFrame, 0, 1);
        for (let j = 0; j < J; j++) {
          const idlePos = add3(posAt(idleClip.positions, idleFrame, j), rootOffset);
          const targetPos = posAt(positions, f, j);
          writePosAt(positions, f, j, lerp3(idlePos, targetPos, alpha));

          const targetAxes = basisAxesAt(basis, f, j);
          const blendedQuat = continuousBlendQuat(
            idleQuatByJoint[j],
            quatFromAxes(targetAxes[0], targetAxes[1], targetAxes[2]),
            alpha,
            previousBlendQuatByJoint[j]
          );
          previousBlendQuatByJoint[j] = blendedQuat;
          const blendedAxes = axesFromQuat(blendedQuat);
          writeBasisAxesAt(basis, f, j, blendedAxes);
        }
      }
    }

    function prepareIdleFootIkForClip(clip) {
      if (!idleClip || legIkSpecs.length === 0 || clip.frame_count <= FOOT_IK_TARGET_FRAME) return;
      const targetFrame = FOOT_IK_TARGET_FRAME;
      const idleFrame = Math.min(IDLE_FOOT_REFERENCE_FRAME, idleClip.frame_count - 1);
      const sourcePositions = clip.originalPositions || clip.positions;
      const sourceBasis = clip.originalBasis || clip.basis;
      const sourceClip = { ...clip, positions: sourcePositions, basis: sourceBasis };
      const positions = new Float32Array(sourcePositions);
      const basis = new Float32Array(sourceBasis);
      const rootOffset = sub3(
        posAt(sourcePositions, targetFrame, rootIndex),
        posAt(idleClip.positions, idleFrame, rootIndex)
      );
      const freeSide = freeLegSideForClip(clip);
      const { legTargets, freeLegTarget, meanGroundDelta } = firstFrameFootDeltas(sourceClip, targetFrame, idleFrame, rootOffset, freeSide);
      const armedFrame = armedFrameForClip(clip);
      const isKickClip = !!freeLegTarget && armedFrame !== null;
      const cleanup = cleanupForClip(clip);
      let pelvisSourceDelta = meanGroundDelta;
      if (isKickClip && legTargets.length > 0) {
        const supportDelta = legTargets[0].footIkDelta;
        const supportGroundDelta = [supportDelta[0], 0, supportDelta[2]];
        pelvisSourceDelta = lerp3(meanGroundDelta, supportGroundDelta, cleanup.pelvis_source_blend);
      }
      const bodyDelta = mul3(pelvisSourceDelta, cleanup.pelvis_offset_scale);
      const pelvisOffsetBones = pelvisOffsetBonesForClip(clip);

      for (let f = 0; f < clip.frame_count; f++) {
        const poseAlpha = freeLegTarget && armedFrame !== null ? clamp(f / Math.max(1e-7, armedFrame), 0, 1) : 1;
        const pelvisExtraAlpha = armedFrame !== null ? 1 - clamp(f / Math.max(1e-7, armedFrame), 0, 1) : 1;
        const extraPelvisDelta = mul3(cleanup.extra_pelvis_offset_m, pelvisExtraAlpha);
        for (const joint of pelvisOffsetBones) {
          const targetPos = add3(add3(posAt(sourcePositions, f, joint), bodyDelta), extraPelvisDelta);
          const targetAxes = basisAxesAt(sourceBasis, f, joint);
          writePosAt(positions, f, joint, targetPos);
          writeBasisAxesAt(basis, f, joint, targetAxes);
        }
        for (const target of legTargets) {
          const spec = target.spec;
          const supportMode = isKickClip ? cleanup.pelvis_source_blend : 0;
          const rawHip = posAt(sourcePositions, f, spec.thigh);
          const rawKnee = posAt(sourcePositions, f, spec.calf);
          const rawFoot = posAt(sourcePositions, f, spec.foot);
          const rawBall = posAt(sourcePositions, f, spec.ball);
          const hip = posAt(positions, f, spec.thigh);
          const kneeSeed = add3(rawKnee, bodyDelta);
          const footSeed = add3(rawFoot, bodyDelta);
          const lockedFootTarget = add3(posAt(sourcePositions, targetFrame, spec.foot), target.footIkDelta);
          const carriedFootTarget = add3(rawFoot, isKickClip ? bodyDelta : target.footIkDelta);
          const footTarget = isKickClip ? lerp3(lockedFootTarget, carriedFootTarget, supportMode) : carriedFootTarget;
          const lockedFootAxes = carriedBasisAxes(sourceBasis, targetFrame, spec.foot, target.footLocalAxes);
          const carriedFootAxes = isKickClip
            ? basisAxesAt(sourceBasis, f, spec.foot)
            : carriedBasisAxes(sourceBasis, f, spec.foot, target.footLocalAxes);
          const footTargetAxes = isKickClip ? slerpAxes(lockedFootAxes, carriedFootAxes, supportMode) : carriedFootAxes;
          const rawBallLocal = basisVectorToLocal(sub3(rawBall, rawFoot), sourceBasis, f, spec.foot);
          const ballLocal = isKickClip ? lerp3(target.idleBallLocal, rawBallLocal, supportMode) : rawBallLocal;
          const ballTarget = add3(footTarget, vectorToWorldFromAxes(ballLocal, footTargetAxes));
          const rawBallLocalAxes = basisAxesInLocal(sourceBasis, f, spec.foot, sourceBasis, f, spec.ball);
          const lockedBallAxes = carriedChildAxesFromParent(footTargetAxes, target.idleBallLocalAxes);
          const carriedBallAxes = carriedChildAxesFromParent(footTargetAxes, rawBallLocalAxes);
          const ballTargetAxes = isKickClip
            ? slerpAxes(lockedBallAxes, carriedBallAxes, supportMode)
            : carriedChildAxesFromParent(footTargetAxes, rawBallLocalAxes);
          const rawPole = legPoleFromKnee(rawHip, rawKnee, rawFoot);
          const rawPoleLocal = basisVectorToLocal(rawPole, sourceBasis, f, spec.foot);
          const poleLocal = isKickClip ? normalize3(lerp3(target.idlePoleLocal, rawPoleLocal, supportMode)) : normalize3(rawPoleLocal);
          const carriedPole = normalize3(vectorToWorldFromAxes(poleLocal, footTargetAxes));
          const upperLength = norm3(sub3(rawKnee, rawHip));
          const lowerLength = norm3(sub3(rawFoot, rawKnee));
          const solvedKnee = solveTwoBoneKneeWithPole(hip, kneeSeed, footSeed, footTarget, carriedPole, upperLength, lowerLength);

          writePosAt(positions, f, spec.calf, solvedKnee);
          writePosAt(positions, f, spec.foot, footTarget);
          writePosAt(positions, f, spec.ball, ballTarget);
          writeBasisAxesAt(basis, f, spec.foot, footTargetAxes);
          writeBasisAxesAt(basis, f, spec.ball, ballTargetAxes);
        }
        if (freeLegTarget) {
          const spec = freeLegTarget.spec;
          const alpha = poseAlpha;
          const legDelta = lerp3(freeLegTarget.footIkDelta, bodyDelta, alpha);
          const rawHip = posAt(sourcePositions, f, spec.thigh);
          const rawKnee = posAt(sourcePositions, f, spec.calf);
          const rawFoot = posAt(sourcePositions, f, spec.foot);
          const rawBall = posAt(sourcePositions, f, spec.ball);
          const hip = posAt(positions, f, spec.thigh);
          const kneeSeed = add3(rawKnee, bodyDelta);
          const footSeed = add3(rawFoot, bodyDelta);
          const footTarget = add3(rawFoot, legDelta);
          const idleFootAxes = carriedBasisAxes(sourceBasis, f, spec.foot, freeLegTarget.footLocalAxes);
          const rawFootAxes = basisAxesAt(sourceBasis, f, spec.foot);
          const footTargetAxes = slerpAxes(idleFootAxes, rawFootAxes, alpha);
          const rawBallLocal = basisVectorToLocal(sub3(rawBall, rawFoot), sourceBasis, f, spec.foot);
          const ballLocal = lerp3(freeLegTarget.idleBallLocal, rawBallLocal, alpha);
          const ballTarget = add3(footTarget, vectorToWorldFromAxes(ballLocal, footTargetAxes));
          const rawBallLocalAxes = basisAxesInLocal(sourceBasis, f, spec.foot, sourceBasis, f, spec.ball);
          const idleBallAxes = carriedChildAxesFromParent(footTargetAxes, freeLegTarget.idleBallLocalAxes);
          const rawBallAxes = carriedChildAxesFromParent(footTargetAxes, rawBallLocalAxes);
          const ballTargetAxes = slerpAxes(idleBallAxes, rawBallAxes, alpha);
          const rawPole = legPoleFromKnee(rawHip, rawKnee, rawFoot);
          const rawPoleLocal = basisVectorToLocal(rawPole, sourceBasis, f, spec.foot);
          const poleLocal = normalize3(lerp3(freeLegTarget.idlePoleLocal, rawPoleLocal, alpha));
          const carriedPole = normalize3(vectorToWorldFromAxes(poleLocal, footTargetAxes));
          const upperLength = norm3(sub3(rawKnee, rawHip));
          const lowerLength = norm3(sub3(rawFoot, rawKnee));
          const solvedKnee = solveTwoBoneKneeWithPole(hip, kneeSeed, footSeed, footTarget, carriedPole, upperLength, lowerLength);

          writePosAt(positions, f, spec.calf, solvedKnee);
          writePosAt(positions, f, spec.foot, footTarget);
          writePosAt(positions, f, spec.ball, ballTarget);
          writeBasisAxesAt(basis, f, spec.foot, footTargetAxes);
          writeBasisAxesAt(basis, f, spec.ball, ballTargetAxes);
        }
      }

      blendIdleToArmed(clip, positions, basis, idleFrame, rootOffset);
      applyFootFrame0Lerp(clip, positions, basis);

      clip.idleFootIkPositions = positions;
      clip.idleFootIkBasis = basis;
      clip.idleFootIkMeanGroundDelta = meanGroundDelta;
      clip.idleFootIkPelvisSourceDelta = pelvisSourceDelta;
      clip.idleFootIkPelvisOffset = bodyDelta;
    }

    function prepareIdleFootIkForAllClips() {
      if (!idleClip) return;
      for (const clip of clips) prepareIdleFootIkForClip(clip);
    }

    function activePositions() {
      return useIdleFootIk && activeClip.idleFootIkPositions ? activeClip.idleFootIkPositions : activeClip.positions;
    }

    function activeBasis() {
      return useIdleFootIk && activeClip.idleFootIkBasis ? activeClip.idleFootIkBasis : activeClip.basis;
    }

    prepareIdleFootIkForAllClips();

    function cameraState() {
      const rect = canvas.getBoundingClientRect();
      const distance = Math.max(0.01, extent * 2.9 / Math.max(1e-6, zoom));
      const target = cameraTarget;
      const eye = [
        target[0] + Math.sin(yaw) * distance,
        target[1] + distance * (0.35 - pitch * 0.55),
        target[2] + Math.cos(yaw) * distance
      ];
      const forward = normalize3(sub3(target, eye));
      let right = normalize3(cross3(forward, [0, 1, 0]));
      if (norm3(right) < 1e-6) right = [1, 0, 0];
      const up = normalize3(cross3(right, forward));
      const focal = (rect.height * 0.5) / Math.tan(45 * Math.PI / 360);
      return { rect, eye, forward, right, up, focal };
    }

    function rotateProject(p) {
      const cam = cameraState();
      const rel = sub3(p, cam.eye);
      const xCam = dot3(rel, cam.right);
      const yCam = dot3(rel, cam.up);
      const zCam = Math.max(0.01, dot3(rel, cam.forward));
      const scalePx = cam.focal / zCam;
      return {
        x: cam.rect.width * 0.5 + panX + xCam * scalePx,
        y: cam.rect.height * 0.48 + panY - yCam * scalePx,
        z: zCam,
        p: Math.min(1.8, Math.max(0.35, scalePx / Math.max(1, cam.focal / Math.max(0.01, extent * 2.9 / Math.max(1e-6, zoom))))),
        scalePx
      };
    }

    function projectWorld(p) { return rotateProject(p); }

    function drawWorldLine(a, b, color, width) {
      const pa = projectWorld(a);
      const pb = projectWorld(b);
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.stroke();
    }

    function drawWorldDashedLine(a, b, color, width, dash = [6, 5]) {
      ctx.save();
      ctx.setLineDash(dash);
      drawWorldLine(a, b, color, width);
      ctx.restore();
    }

    function drawWorldArrow(a, b, color, label) {
      const pa = projectWorld(a);
      const pb = projectWorld(b);
      const dx = pb.x - pa.x;
      const dy = pb.y - pa.y;
      const len = Math.hypot(dx, dy);
      if (len < 1e-5) return;
      const ux = dx / len;
      const uy = dy / len;
      const nx = -uy;
      const ny = ux;
      const size = 10;
      ctx.save();
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(pb.x, pb.y);
      ctx.lineTo(pb.x - ux * size + nx * size * 0.52, pb.y - uy * size + ny * size * 0.52);
      ctx.lineTo(pb.x - ux * size - nx * size * 0.52, pb.y - uy * size - ny * size * 0.52);
      ctx.closePath();
      ctx.fill();
      if (label) {
        ctx.font = "12px system-ui, sans-serif";
        ctx.fillText(label, pb.x + 7, pb.y - 5);
      }
      ctx.restore();
    }

    function drawWorldDot(p, color, label) {
      const q = projectWorld(p);
      ctx.save();
      ctx.fillStyle = color;
      ctx.strokeStyle = "rgba(7,10,14,0.82)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(q.x, q.y, Math.max(4, 5.5 * q.p), 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      if (label) {
        ctx.font = "11px system-ui, sans-serif";
        ctx.fillStyle = color;
        ctx.fillText(label, q.x + 7, q.y + 4);
      }
      ctx.restore();
    }

    function floorCenter() {
      const root = posAt(activeClip.positions, viewFrame(), rootIndex);
      return [root[0], 0.0, root[2]];
    }

    function drawGrid() {
      const c = floorCenter();
      const radius = 6.5;
      const x0 = c[0] - radius, x1 = c[0] + radius;
      const z0 = c[2] - radius, z1 = c[2] + radius;
      const corners = [
        projectWorld([x0, 0, z0]),
        projectWorld([x1, 0, z0]),
        projectWorld([x1, 0, z1]),
        projectWorld([x0, 0, z1])
      ];
      ctx.save();
      ctx.fillStyle = floorColors.base;
      ctx.beginPath();
      ctx.moveTo(corners[0].x, corners[0].y);
      for (let i = 1; i < corners.length; i++) ctx.lineTo(corners[i].x, corners[i].y);
      ctx.closePath();
      ctx.fill();

      const drawLayer = (spacing, color, width, skipEvery, onlyEvery) => {
        const startX = Math.floor(x0 / spacing) * spacing;
        const endX = Math.ceil(x1 / spacing) * spacing;
        const startZ = Math.floor(z0 / spacing) * spacing;
        const endZ = Math.ceil(z1 / spacing) * spacing;
        for (let x = startX; x <= endX + spacing * 0.5; x += spacing) {
          const ix = Math.round(x / spacing);
          if ((skipEvery && ix % skipEvery === 0) || (onlyEvery && ix % onlyEvery !== 0)) continue;
          drawWorldLine([x, 0.002, z0], [x, 0.002, z1], color, width);
        }
        for (let z = startZ; z <= endZ + spacing * 0.5; z += spacing) {
          const iz = Math.round(z / spacing);
          if ((skipEvery && iz % skipEvery === 0) || (onlyEvery && iz % onlyEvery !== 0)) continue;
          drawWorldLine([x0, 0.002, z], [x1, 0.002, z], color, width);
        }
      }
      drawLayer(0.25, floorColors.minor, 1.0, 4, null);
      drawLayer(1.0, floorColors.major, 1.5, null, 1);
      ctx.restore();
    }

    function drawCapsule(arr, a, b, radiusWorld, fill, stroke, alpha) {
      const sample = currentRenderSample();
      const pa = rotateProject(renderPosAt(arr, sample, a));
      const pb = rotateProject(renderPosAt(arr, sample, b));
      const radiusPx = Math.max(3, radiusWorld * 0.5 * (pa.scalePx + pb.scalePx));
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = fill;
      ctx.lineWidth = radiusPx * 2;
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.stroke();
      ctx.strokeStyle = stroke;
      ctx.lineWidth = Math.max(1, radiusPx * 0.08);
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.stroke();
      ctx.restore();
    }

    function drawAxisTick(centerPoint, axis, length, color, alpha) {
      const a = projectWorld(centerPoint);
      const b = projectWorld(add3(centerPoint, mul3(axis, length)));
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
      ctx.restore();
    }

    function drawOrientedBox(centerPoint, axisX, axisY, axisZ, dims, stroke, fill, alpha) {
      const hx = dims[0] * 0.5, hy = dims[1] * 0.5, hz = dims[2] * 0.5;
      const corners = [
        [-hx,-hy,-hz], [ hx,-hy,-hz], [ hx, hy,-hz], [-hx, hy,-hz],
        [-hx,-hy, hz], [ hx,-hy, hz], [ hx, hy, hz], [-hx, hy, hz]
      ].map(c => projectWorld(add3(add3(add3(centerPoint, mul3(axisX, c[0])), mul3(axisY, c[1])), mul3(axisZ, c[2]))));
      const faces = [
        [0,1,2,3], [4,5,6,7], [0,1,5,4], [1,2,6,5], [2,3,7,6], [3,0,4,7]
      ].map(face => ({ face, z: face.reduce((acc, i) => acc + corners[i].z, 0) / face.length }))
       .sort((a, b) => a.z - b.z);
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = fill;
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1.1;
      for (const item of faces) {
        ctx.beginPath();
        for (let k = 0; k < item.face.length; k++) {
          const p = corners[item.face[k]];
          if (k === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
      ctx.restore();
    }

    function dynamicFootBlockSpecAt(arr, basis, sample, ankle, toe, rootOffset = [0, 0, 0]) {
      const foot = add3(posAt(arr, sample, ankle), rootOffset);
      const toePos = add3(posAt(arr, sample, toe), rootOffset);
      let up = basisAxisAt(basis, sample, ankle, 0);
      let forward = basisAxisAt(basis, sample, ankle, 1);
      const side = basisAxisAt(basis, sample, ankle, 2);
      const toeVector = sub3(toePos, foot);
      if (dot3(forward, toeVector) < 0) forward = mul3(forward, -1);
      if (up[1] < 0) up = mul3(up, -1);
      const length = footDims[0];
      const heelBack = add3(toePos, mul3(forward, -length));
      const centerPoint = add3(add3(heelBack, mul3(forward, length * 0.5)), mul3(up, -0.006));
      return { center: centerPoint, forward, side, up, dims: footDims };
    }

    function footBlockLocalSpec(arr, basis, ankle, toe) {
      const base = dynamicFootBlockSpecAt(arr, basis, 0, ankle, toe);
      const foot = posAt(arr, 0, ankle);
      const centerRel = sub3(base.center, foot);
      return {
        centerLocal: [
          dot3(centerRel, basisAxisAt(basis, 0, ankle, 0)),
          dot3(centerRel, basisAxisAt(basis, 0, ankle, 1)),
          dot3(centerRel, basisAxisAt(basis, 0, ankle, 2))
        ],
        forwardLocal: basisVectorToLocal(base.forward, basis, 0, ankle),
        sideLocal: basisVectorToLocal(base.side, basis, 0, ankle),
        upLocal: basisVectorToLocal(base.up, basis, 0, ankle)
      };
    }

    function footBlockSpecAt(arr, basis, sample, ankle, toe, rootOffset = [0, 0, 0]) {
      const local = footBlockLocalSpec(arr, basis, ankle, toe);
      const foot = add3(posAt(arr, sample, ankle), rootOffset);
      const axes = [
        basisAxisAt(basis, sample, ankle, 0),
        basisAxisAt(basis, sample, ankle, 1),
        basisAxisAt(basis, sample, ankle, 2)
      ];
      return {
        center: pointFromFrame(foot, axes, local.centerLocal),
        forward: normalize3(vectorToWorldFromAxes(local.forwardLocal, axes)),
        side: normalize3(vectorToWorldFromAxes(local.sideLocal, axes)),
        up: normalize3(vectorToWorldFromAxes(local.upLocal, axes)),
        dims: footDims
      };
    }

    function footBlockSpec(arr, basis, ankle, toe) {
      return footBlockSpecAt(arr, basis, currentRenderSample(), ankle, toe, renderRootOffset);
    }

    function dynamicToeBlockSpecAt(arr, basis, sample, ankle, toe, rootOffset = [0, 0, 0]) {
      const foot = add3(posAt(arr, sample, ankle), rootOffset);
      const toePos = add3(posAt(arr, sample, toe), rootOffset);
      const toeVector = sub3(toePos, foot);
      let footForward = basisAxisAt(basis, sample, ankle, 1);
      if (dot3(footForward, toeVector) < 0) footForward = mul3(footForward, -1);
      let forward = basisAxisAt(basis, sample, toe, 0);
      if (dot3(forward, footForward) < 0) forward = mul3(forward, -1);
      let up = basisAxisAt(basis, sample, toe, 1);
      const referenceSide = basisAxisAt(basis, sample, toe, 2);
      if (up[1] < 0) up = mul3(up, -1);
      let side = normalize3(cross3(forward, up));
      if (norm3(side) < 1e-6) side = referenceSide;
      if (dot3(side, referenceSide) < 0) side = mul3(side, -1);
      up = normalize3(cross3(side, forward));
      if (up[1] < 0) {
        up = mul3(up, -1);
        side = mul3(side, -1);
      }
      const centerPoint = add3(add3(toePos, mul3(forward, toeDims[0] * 0.5)), mul3(up, -0.006));
      return { center: centerPoint, forward, side, up, dims: toeDims };
    }

    function toeBlockSpecAt(arr, basis, sample, ankle, toe, rootOffset = [0, 0, 0]) {
      return dynamicToeBlockSpecAt(arr, basis, sample, ankle, toe, rootOffset);
    }

    function toeBlockSpec(arr, basis, ankle, toe) {
      return toeBlockSpecAt(arr, basis, currentRenderSample(), ankle, toe, renderRootOffset);
    }

    function drawFootBoxes(arr, basis, alpha) {
      for (const f of footSpecs) {
        const color = f.side === 0 ? css("--foot-left") : css("--foot-right");
        const fill = f.side === 0 ? css("--foot-left-fill") : css("--foot-right-fill");
        const foot = footBlockSpec(arr, basis, f.ankle, f.toe);
        const toe = toeBlockSpec(arr, basis, f.ankle, f.toe);
        drawOrientedBox(foot.center, foot.forward, foot.side, foot.up, foot.dims, color, fill, alpha);
        drawOrientedBox(toe.center, toe.forward, toe.side, toe.up, toe.dims, color, fill, alpha * 0.88);
        drawAxisTick(foot.center, foot.forward, foot.dims[0] * 0.5, color, alpha);
      }
    }

    function phaseForFrame(clipName, frameValue) {
      const armed = attackConfig.armed_by_clip[clipName];
      const hits = attackConfig.target.hits_by_clip[clipName] || [];
      const armedFrame = armed && Number.isFinite(Number(armed.frame)) ? Number(armed.frame) : Infinity;
      const hitFrames = hits
        .map(entry => Number(entry?.frame))
        .filter(value => Number.isFinite(value));
      const hitFrame = hitFrames.length ? Math.min(...hitFrames) : Infinity;
      if (frameValue >= hitFrame) return "hit";
      if (frameValue >= armedFrame) return "armed";
      return "pre";
    }

    function handPhaseColor(baseColor, phase) {
      if (phase === "hit") return css("--phase-hit");
      if (phase === "armed") return css("--phase-armed");
      return baseColor;
    }

    function handBoxFromPose(hand, lower, axes, referenceForward = null) {
      const wristDir = normalize3(sub3(hand, lower));
      let forward = axes[0];
      const refForward = Array.isArray(referenceForward) ? normalize3(referenceForward) : null;
      if (refForward) {
        if (dot3(forward, refForward) < 0) forward = mul3(forward, -1);
      } else if (dot3(forward, wristDir) < 0) {
        forward = mul3(forward, -1);
      }

      let palmNormal = axes[1];
      let side = axes[2];
      if (palmNormal[1] < 0) {
        palmNormal = mul3(palmNormal, -1);
        side = mul3(side, -1);
      }
      side = normalize3(cross3(palmNormal, forward));
      const referenceSide = axes[2];
      if (dot3(side, referenceSide) < 0) side = mul3(side, -1);
      palmNormal = normalize3(cross3(forward, side));
      if (palmNormal[1] < 0) {
        palmNormal = mul3(palmNormal, -1);
        side = mul3(side, -1);
      }

      const dims = [0.145, 0.090, 0.045];
      const centerPoint = add3(add3(hand, mul3(forward, dims[0] * 0.5)), mul3(palmNormal, -0.0025));
      return { center: centerPoint, forward, side, palmNormal, dims };
    }

    function handBoxSpec(arr, basis, h, referenceForward = null) {
      const sample = currentRenderSample();
      return handBoxFromPose(
        renderPosAt(arr, sample, h.hand),
        renderPosAt(arr, sample, h.lower),
        [
          basisAxisAt(basis, sample, h.hand, 0),
          basisAxisAt(basis, sample, h.hand, 1),
          basisAxisAt(basis, sample, h.hand, 2)
        ],
        referenceForward
      );
    }

    function drawHandBoxes(arr, basis, alpha, phase = "pre") {
      for (const h of handSpecs) {
        const baseColor = h.side === 0 ? css("--left") : css("--right");
        const color = handPhaseColor(baseColor, phase);
        const box = handBoxSpec(arr, basis, h);
        drawOrientedBox(box.center, box.forward, box.side, box.palmNormal, box.dims, color, css("--hand-fill"), alpha);
        drawAxisTick(box.center, box.forward, 0.080, color, alpha);
      }
    }

    function swordLocalVertex(index) {
      const i = index * 3;
      const v = [sword.vertices[i], sword.vertices[i + 1], sword.vertices[i + 2]];
      if (sword.bladeMask[index]) {
        const axis = sword.blade_axis;
        v[axis] = sword.blade_base_m + bladeScale * (v[axis] - sword.blade_base_m);
      }
      return v;
    }

    function swordLocalToHand(v) {
      const m = sword.local_to_hand;
      return [
        v[0] * m[0] + v[1] * m[4] + v[2] * m[8] + m[12],
        v[0] * m[1] + v[1] * m[5] + v[2] * m[9] + m[13],
        v[0] * m[2] + v[1] * m[6] + v[2] * m[10] + m[14]
      ];
    }

    function handLocalToWorld(v, handPos, handAxes) {
      return add3(add3(add3(handPos, mul3(handAxes[0], v[0])), mul3(handAxes[1], v[1])), mul3(handAxes[2], v[2]));
    }

    function swordLocalPointToWorld(v, handPos, handAxes) {
      return handLocalToWorld(swordLocalToHand(v), handPos, handAxes);
    }

    function meleeStrikeJointName(clipName) {
      const n = String(clipName || "").toLowerCase();
      if (n.includes("headbutt") || n.includes("head")) return "head";
      if (n.includes("kickl") || n.includes("kick_l") || n.includes("leftkick")) return "foot_l";
      if (n.includes("kickr") || n.includes("kick_r") || n.includes("rightkick")) return "foot_r";
      if (n.endsWith("l") || n.includes("_l") || n.includes("left")) return "hand_l";
      if (n.endsWith("r") || n.includes("_r") || n.includes("right")) return "hand_r";
      return "hand_r";
    }

    function firstExistingJoint(candidates) {
      for (const name of candidates) {
        const index = nameToIndex.get(name);
        if (index !== undefined) return { name, index };
      }
      return null;
    }

    function meleeStrikeJointInfo(clip = activeClip) {
      const preferred = meleeStrikeJointName(clip?.name || "");
      if (preferred === "foot_l") return firstExistingJoint(["foot_l", "ball_l", "hand_l", "hand_r"]);
      if (preferred === "foot_r") return firstExistingJoint(["foot_r", "ball_r", "hand_r", "hand_l"]);
      if (preferred === "hand_l") return firstExistingJoint(["hand_l", "lowerarm_l", "hand_r"]);
      if (preferred === "hand_r") return firstExistingJoint(["hand_r", "lowerarm_r", "hand_l"]);
      if (preferred === "head") return firstExistingJoint(["head", "neck_02", "neck_01", "hand_r"]);
      return firstExistingJoint([preferred, "hand_r", "hand_l", "head"]);
    }

    function meleeTargetOffsetM() {
      return workingMeleeTargetOffsetM.slice();
    }

    function jointLocalPointToWorld(v, arr, basis, atFrame, joint) {
      const f = Math.max(0, Math.min(activeClip.frame_count - 1, Number(atFrame) || 0));
      const p = posAt(arr, f, joint);
      return add3(add3(add3(
        p,
        mul3(basisAxisAt(basis, f, joint, 0), v[0])
      ), mul3(basisAxisAt(basis, f, joint, 1), v[1])),
        mul3(basisAxisAt(basis, f, joint, 2), v[2])
      );
    }

    function pointFromFrame(origin, axes, v) {
      return add3(add3(add3(origin, mul3(axes[0], v[0])), mul3(axes[1], v[1])), mul3(axes[2], v[2]));
    }

    function meleeTargetFrame(arr, basis, atFrame, info) {
      const f = Math.max(0, Math.min(activeClip.frame_count - 1, Number(atFrame) || 0));
      return {
        origin: posAt(arr, f, info.index),
        axes: [
          basisAxisAt(basis, f, info.index, 0),
          basisAxisAt(basis, f, info.index, 1),
          basisAxisAt(basis, f, info.index, 2)
        ],
        space: "joint_local"
      };
    }

    function rootLocalToWorldAt(v, arr, basis, atFrame) {
      const f = Math.max(0, Math.min(activeClip.frame_count - 1, Number(atFrame) || 0));
      const rootPos = posAt(arr, f, rootIndex);
      const axes = [
        basisAxisAt(basis, f, rootIndex, 0),
        basisAxisAt(basis, f, rootIndex, 1),
        basisAxisAt(basis, f, rootIndex, 2)
      ];
      return add3(add3(add3(rootPos, mul3(axes[0], v[0])), mul3(axes[1], v[1])), mul3(axes[2], v[2]));
    }

    function worldToRootLocalAt(p, arr, basis, atFrame) {
      const f = Math.max(0, Math.min(activeClip.frame_count - 1, Number(atFrame) || 0));
      const rootPos = posAt(arr, f, rootIndex);
      const rel = sub3(p, rootPos);
      return [
        dot3(rel, basisAxisAt(basis, f, rootIndex, 0)),
        dot3(rel, basisAxisAt(basis, f, rootIndex, 1)),
        dot3(rel, basisAxisAt(basis, f, rootIndex, 2))
      ];
    }

    function pelvisLocalToWorldAt(v, arr, basis, atFrame) {
      const f = Math.max(0, Math.min(activeClip.frame_count - 1, Number(atFrame) || 0));
      const pelvisPos = posAt(arr, f, pelvisIndex);
      const axes = [
        basisAxisAt(basis, f, pelvisIndex, 0),
        basisAxisAt(basis, f, pelvisIndex, 1),
        basisAxisAt(basis, f, pelvisIndex, 2)
      ];
      return add3(add3(add3(pelvisPos, mul3(axes[0], v[0])), mul3(axes[1], v[1])), mul3(axes[2], v[2]));
    }

    function worldToPelvisLocalAt(p, arr, basis, atFrame) {
      const f = Math.max(0, Math.min(activeClip.frame_count - 1, Number(atFrame) || 0));
      const pelvisPos = posAt(arr, f, pelvisIndex);
      const rel = sub3(p, pelvisPos);
      return [
        dot3(rel, basisAxisAt(basis, f, pelvisIndex, 0)),
        dot3(rel, basisAxisAt(basis, f, pelvisIndex, 1)),
        dot3(rel, basisAxisAt(basis, f, pelvisIndex, 2))
      ];
    }

    function currentHitWorldPoint() {
      const sample = viewFrame();
      const arr = activePositions();
      const bas = activeBasis();
      if (isMeleeClip(activeClip)) {
        const info = meleeStrikeJointInfo();
        if (!info) return null;
        const frame = meleeTargetFrame(arr, bas, sample, info);
        return pointFromFrame(frame.origin, frame.axes, meleeTargetOffsetM());
      }
      if (!sword || swordHandIndex === undefined) return null;
      const handPos = posAt(arr, sample, swordHandIndex);
      const handAxes = [
        basisAxisAt(bas, sample, swordHandIndex, 0),
        basisAxisAt(bas, sample, swordHandIndex, 1),
        basisAxisAt(bas, sample, swordHandIndex, 2)
      ];
      return swordLocalPointToWorld(bladeCenterLocalAt(attackConfig.hit), handPos, handAxes);
    }

    function currentBladeTip() {
      return sword.blade_base_m + bladeScale * (sword.blade_tip_m - sword.blade_base_m);
    }

    function bladeParamCoord(t) {
      return sword.blade_base_m + clamp(t, 0, 1) * (currentBladeTip() - sword.blade_base_m);
    }

    function bladeCenterLocalAt(t) {
      const v = [
        (sword.blade_bounds_min_m[0] + sword.blade_bounds_max_m[0]) * 0.5,
        (sword.blade_bounds_min_m[1] + sword.blade_bounds_max_m[1]) * 0.5,
        (sword.blade_bounds_min_m[2] + sword.blade_bounds_max_m[2]) * 0.5
      ];
      v[sword.blade_axis] = bladeParamCoord(t);
      return v;
    }

    function expandedAttackBoundsLocal() {
      const mn = sword.blade_bounds_min_m.slice();
      const mx = sword.blade_bounds_max_m.slice();
      const axis = sword.blade_axis;
      const tip = currentBladeTip();
      mn[axis] = Math.min(sword.blade_base_m, tip);
      mx[axis] = Math.max(sword.blade_base_m, tip);
      const expandAxis = (targetAxis, cm) => {
        const margin = cm * 0.01;
        mn[targetAxis] -= margin;
        mx[targetAxis] += margin;
        if (mx[targetAxis] - mn[targetAxis] < 0.001) {
          const mid = (mx[targetAxis] + mn[targetAxis]) * 0.5;
          mn[targetAxis] = mid - 0.0005;
          mx[targetAxis] = mid + 0.0005;
        }
      };
      expandAxis(swordCrossAxes.width, attackConfig.collider.width_offset_cm);
      expandAxis(swordCrossAxes.thickness, attackConfig.collider.thickness_offset_cm);
      expandAxis(axis, attackConfig.collider.length_offset_cm);
      return { mn, mx };
    }

    function drawSwordLocalBox(mn, mx, handPos, handAxes, stroke, fill, alpha) {
      const cornersLocal = [
        [mn[0], mn[1], mn[2]], [mx[0], mn[1], mn[2]], [mx[0], mx[1], mn[2]], [mn[0], mx[1], mn[2]],
        [mn[0], mn[1], mx[2]], [mx[0], mn[1], mx[2]], [mx[0], mx[1], mx[2]], [mn[0], mx[1], mx[2]]
      ];
      const corners = cornersLocal.map(v => projectWorld(swordLocalPointToWorld(v, handPos, handAxes)));
      const faces = [
        [0,1,2,3], [4,5,6,7], [0,1,5,4], [1,2,6,5], [2,3,7,6], [3,0,4,7]
      ].map(face => ({ face, z: face.reduce((acc, i) => acc + corners[i].z, 0) / face.length }))
       .sort((a, b) => b.z - a.z);
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = fill;
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1.6;
      for (const item of faces) {
        ctx.beginPath();
        for (let k = 0; k < item.face.length; k++) {
          const p = corners[item.face[k]];
          if (k === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
      ctx.restore();
    }

    function drawAttackMarker(t, color, handPos, handAxes, radiusPx, alpha) {
      const bounds = expandedAttackBoundsLocal();
      const center = bladeCenterLocalAt(t);
      const widthAxis = swordCrossAxes.width;
      const thickAxis = swordCrossAxes.thickness;
      const widthHalf = Math.max(0.006, (bounds.mx[widthAxis] - bounds.mn[widthAxis]) * 0.5);
      const thickHalf = Math.max(0.004, (bounds.mx[thickAxis] - bounds.mn[thickAxis]) * 0.5);
      const a = center.slice();
      const b = center.slice();
      const c = center.slice();
      const d = center.slice();
      a[widthAxis] -= widthHalf;
      b[widthAxis] += widthHalf;
      c[thickAxis] -= thickHalf;
      d[thickAxis] += thickHalf;
      const pa = projectWorld(swordLocalPointToWorld(a, handPos, handAxes));
      const pb = projectWorld(swordLocalPointToWorld(b, handPos, handAxes));
      const pc = projectWorld(swordLocalPointToWorld(c, handPos, handAxes));
      const pd = projectWorld(swordLocalPointToWorld(d, handPos, handAxes));
      const p = projectWorld(swordLocalPointToWorld(center, handPos, handAxes));
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.moveTo(pc.x, pc.y);
      ctx.lineTo(pd.x, pd.y);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(p.x, p.y, radiusPx, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    function drawMeleeTargetOverlay(arr, basis, alpha) {
      const info = meleeStrikeJointInfo();
      if (!info) return;
      const sample = viewFrame();
      const targetFrame = meleeTargetFrame(arr, basis, sample, info);
      const limb = targetFrame.origin;
      const target = pointFromFrame(targetFrame.origin, targetFrame.axes, meleeTargetOffsetM());
      const radiusM = attackConfig.target.radius_cm * 0.01;
      if (norm3(sub3(target, limb)) > 0.001) {
        drawWorldDashedLine(limb, target, css("--target-line"), 1.5, [5, 4]);
      }
      drawTargetSphere(target, radiusM, true);
      const p = projectWorld(limb);
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = css("--target-line");
      ctx.beginPath();
      ctx.arc(p.x, p.y, Math.max(3, 4.5 * p.p), 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    function drawAttackOverlays(arr, basis, alpha) {
      if (isMeleeClip(activeClip)) {
        drawMeleeTargetOverlay(arr, basis, alpha);
        return;
      }
      if (!sword || swordHandIndex === undefined || !swordCrossAxes) return;
      const sample = viewFrame();
      const handPos = posAt(arr, sample, swordHandIndex);
      const handAxes = [
        basisAxisAt(basis, sample, swordHandIndex, 0),
        basisAxisAt(basis, sample, swordHandIndex, 1),
        basisAxisAt(basis, sample, swordHandIndex, 2)
      ];
      const bounds = expandedAttackBoundsLocal();
      drawSwordLocalBox(bounds.mn, bounds.mx, handPos, handAxes, css("--attack-box"), css("--attack-box-fill"), alpha);
      drawAttackMarker(attackConfig.bound.start, css("--attack-red"), handPos, handAxes, 4.0, 0.96);
      drawAttackMarker(attackConfig.bound.end, css("--attack-green"), handPos, handAxes, 4.0, 0.96);
      drawAttackMarker(attackConfig.hit, css("--attack-purple"), handPos, handAxes, 5.0, 0.96);
    }

    function drawTargetSphere(center, radiusM, active, fillColor = css("--target"), lineColor = css("--target-line")) {
      const p = projectWorld(center);
      const radiusPx = Math.max(4, radiusM * p.scalePx);
      ctx.save();
      ctx.globalAlpha = active ? 0.82 : 0.48;
      ctx.fillStyle = fillColor;
      ctx.strokeStyle = lineColor;
      ctx.lineWidth = active ? 2.2 : 1.4;
      ctx.beginPath();
      ctx.arc(p.x, p.y, radiusPx, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.globalAlpha = active ? 0.62 : 0.34;
      ctx.beginPath();
      ctx.ellipse(p.x, p.y, radiusPx, radiusPx * 0.34, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.ellipse(p.x, p.y, radiusPx * 0.34, radiusPx, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    function drawSavedTargets(arr, basis) {
      const armed = attackConfig.armed_by_clip[activeClip.name];
      const hits = attackConfig.target.hits_by_clip[activeClip.name] || [];
      const sample = viewFrame();
      if (armed && typeof armed === "object") {
        const bladePelvis = armed.armed_blade_pelvis_m;
        if (Array.isArray(bladePelvis) && bladePelvis.length === 3) {
          const center = pelvisLocalToWorldAt(bladePelvis, arr, basis, armed.frame);
          const radiusM = (Number(armed.radius_cm) || attackConfig.armed_radius_cm) * 0.01;
          drawTargetSphere(center, radiusM, Math.abs(Number(armed.frame) - sample) < 0.0005, css("--armed-target"), css("--armed-target-line"));
        }
        const handPelvis = armed.armed_hand_pelvis_m;
        if (Array.isArray(handPelvis) && handPelvis.length === 3) {
          const center = pelvisLocalToWorldAt(handPelvis, arr, basis, armed.frame);
          const radiusM = (Number(armed.radius_cm) || attackConfig.armed_radius_cm) * 0.01;
          drawTargetSphere(center, radiusM, Math.abs(Number(armed.frame) - sample) < 0.0005, css("--armed-hand-target"), css("--armed-hand-target-line"));
        }
      }
      for (const hitEntry of hits) {
        const hitWorld = hitEntry.hit_world_m;
        if (!Array.isArray(hitWorld) || hitWorld.length !== 3) continue;
        const radiusM = attackConfig.target.radius_cm * 0.01;
        const center = hitWorld;
        drawTargetSphere(center, radiusM, Math.abs(Number(hitEntry.frame) - sample) < 0.0005);
      }
    }

    function drawSwordMesh(arr, basis, alpha) {
      if (!sword || swordHandIndex === undefined) return;
      const sample = currentRenderSample();
      const handPos = renderPosAt(arr, sample, swordHandIndex);
      const handAxes = [
        basisAxisAt(basis, sample, swordHandIndex, 0),
        basisAxisAt(basis, sample, swordHandIndex, 1),
        basisAxisAt(basis, sample, swordHandIndex, 2)
      ];
      const projected = new Array(sword.vertex_count);
      for (let i = 0; i < sword.vertex_count; i++) {
        const local = swordLocalVertex(i);
        const handLocal = swordLocalToHand(local);
        projected[i] = projectWorld(handLocalToWorld(handLocal, handPos, handAxes));
      }
      const faces = [];
      for (let i = 0; i < sword.triangles.length; i += 3) {
        const a = sword.triangles[i];
        const b = sword.triangles[i + 1];
        const c = sword.triangles[i + 2];
        const pa = projected[a], pb = projected[b], pc = projected[c];
        const area = (pb.x - pa.x) * (pc.y - pa.y) - (pb.y - pa.y) * (pc.x - pa.x);
        if (Math.abs(area) < 0.08) continue;
        faces.push({
          a, b, c,
          z: (pa.z + pb.z + pc.z) / 3,
          blade: sword.bladeMask[a] || sword.bladeMask[b] || sword.bladeMask[c]
        });
      }
      faces.sort((a, b) => b.z - a.z);
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.lineJoin = "round";
      for (const f of faces) {
        const pa = projected[f.a], pb = projected[f.b], pc = projected[f.c];
        ctx.fillStyle = f.blade ? css("--sword-blade") : css("--sword-hilt");
        ctx.strokeStyle = f.blade ? css("--sword-edge") : "rgba(92, 52, 24, 0.74)";
        ctx.lineWidth = f.blade ? 0.55 : 0.75;
        ctx.beginPath();
        ctx.moveTo(pa.x, pa.y);
        ctx.lineTo(pb.x, pb.y);
        ctx.lineTo(pc.x, pc.y);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
      ctx.restore();
    }

    function drawPoleVectorOverlay() {
      if (!showPoleVectors || !idleClip || legIkSpecs.length === 0) return;
      const sample = viewFrame();
      const displayPositions = activePositions();
      const displayBasis = activeBasis();

      for (let i = 0; i < legIkSpecs.length; i++) {
        const spec = legIkSpecs[i];
        const color = spec.foot === nameToIndex.get("foot_l") ? "rgba(116,168,255,0.96)" : "rgba(255,152,108,0.96)";
        const displayHip = posAt(displayPositions, sample, spec.thigh);
        const displayKnee = posAt(displayPositions, sample, spec.calf);
        const displayFoot = posAt(displayPositions, sample, spec.foot);
        const carriedPole = footLocalPoleForTarget(activeClip.positions, activeClip.basis, displayBasis, sample, sample, spec);
        const info = twoBonePoleInfoWithPole(displayHip, displayKnee, displayFoot, displayFoot, carriedPole);
        if (!info) continue;

        const arrowLength = Math.max(0.18, norm3(sub3(displayKnee, displayHip)) * 0.55);
        drawWorldArrow(displayKnee, add3(displayKnee, mul3(info.pole, arrowLength)), color);
      }
    }

    function drawIdleOverlay() {
      if (!showIdle || !idleClip) return;
      const sample = 0;
      const offset = sub3(
        posAt(activePositions(), viewFrame(), rootIndex),
        posAt(idleClip.positions, sample, rootIndex)
      );
      drawSkeleton(idleClip.positions, idleClip.basis, 0.42, true, sample, offset, true);
      withRenderPose(sample, offset, () => drawSwordMesh(idleClip.positions, idleClip.basis, 0.34));
    }

    function drawOriginalOverlay() {
      if (!showOriginal) return;
      const positions = activeClip.originalPositions || activeClip.positions;
      const basis = activeClip.originalBasis || activeClip.basis;
      const sample = viewFrame();
      drawSkeleton(positions, basis, 0.38, true, sample, null, true);
      withRenderPose(sample, null, () => drawSwordMesh(positions, basis, 0.34));
    }

    function drawSkeleton(arr, basis, alpha, ghost, sampleOverride = null, rootOffset = null, drawGhostColliders = false) {
      withRenderPose(sampleOverride, rootOffset, () => {
        const sample = currentRenderSample();
        const phase = ghost ? "pre" : phaseForFrame(activeClip.name, sample);
        const points = Array.from({ length: J }, (_, j) => rotateProject(renderPosAt(arr, sample, j)));
        if (!ghost) pointsCache = points;
        if (showVolumes && (!ghost || drawGhostColliders)) {
          const volumeAlpha = ghost ? alpha * 0.48 : alpha;
          const sortedVolumes = volumeSpecs.slice().sort((a, b) => points[a.a].z + points[a.b].z - points[b.a].z - points[b.b].z);
          for (const v of sortedVolumes) {
            drawCapsule(
              arr,
              v.a,
              v.b,
              v.r,
              ghost ? "rgba(190,198,214,0.22)" : css("--volume"),
              ghost ? "rgba(220,226,240,0.42)" : css("--volume-line"),
              volumeAlpha
            );
          }
          drawHandBoxes(arr, basis, ghost ? alpha * 0.58 : alpha, phase);
          drawFootBoxes(arr, basis, ghost ? alpha * 0.58 : alpha);
        }
        const edges = edgePairs.slice().sort((a, b) => points[a[0]].z + points[a[1]].z - points[b[0]].z - points[b[1]].z);
        ctx.save();
        ctx.globalAlpha = alpha;
        for (const [parent, child] of edges) {
          const a = points[parent], b = points[child];
          const childName = names[child].toLowerCase();
          const helper = isHelperName(childName) || isDetailName(childName);
          ctx.strokeStyle = ghost ? "rgba(190,198,214,0.58)" : colorFor(names[child]);
          ctx.lineWidth = Math.max(0.8, (ghost ? 1.5 : (helper ? 1.35 : 3.0)) * b.p);
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
        for (let j = 0; j < J; j++) {
          const q = points[j];
          const jointName = names[j].toLowerCase();
          const helper = isHelperName(jointName) || isDetailName(jointName);
          ctx.fillStyle = ghost ? "rgba(190,198,214,0.58)" : colorFor(names[j]);
          ctx.beginPath();
          ctx.arc(q.x, q.y, Math.max(1.5, (ghost ? 2.4 : (helper ? 2.4 : 3.8)) * q.p), 0, Math.PI * 2);
          ctx.fill();
          if (!ghost && showLabels && q.p > 0.55) {
            ctx.fillStyle = "rgba(236,239,244,0.72)";
            ctx.font = "11px system-ui, sans-serif";
            ctx.fillText(names[j], q.x + 6, q.y - 5);
          }
        }
        ctx.restore();
      });
    }

    function draw() {
      const rect = canvas.getBoundingClientRect();
      ctx.clearRect(0, 0, rect.width, rect.height);
      drawGrid();
      drawIdleOverlay();
      drawOriginalOverlay();
      const positions = activePositions();
      const basis = activeBasis();
      window.__MELEE_VIEWER_DEBUG__ = {
        activeClip: activeClip.name,
        useIdleFootIk,
        pelvisOffsetScale,
        pelvisSourceBlend,
        extraPelvisOffsetM,
        pelvisDelta: activeClip.idleFootIkPelvisOffset ? Array.from(activeClip.idleFootIkPelvisOffset) : null,
        pelvisSourceDelta: activeClip.idleFootIkPelvisSourceDelta ? Array.from(activeClip.idleFootIkPelvisSourceDelta) : null
      };
      if (showModified) {
        drawSkeleton(positions, basis, 0.92, false);
        drawSwordMesh(positions, basis, 0.96);
        drawAttackOverlays(positions, basis, 0.92);
        drawSavedTargets(positions, basis);
        drawPoleVectorOverlay();
      }
      frameText.textContent = formatFrameValue(viewFrame());
      frameSlider.value = String(frame);
      betweenSlider.value = String(frameBlend);
      betweenText.textContent = frameBlend.toFixed(3);
      attackFrameBlendSlider.value = String(frameBlend);
      attackFrameBlendText.value = frameBlend.toFixed(3);
    }

    function setFrameExact(value) {
      const maxFrame = Math.max(0, activeClip.frame_count - 1);
      frameCursor = Math.max(0, Math.min(maxFrame, Number(value) || 0));
      frame = Math.max(0, Math.min(maxFrame, Math.floor(frameCursor)));
      frameBlend = Math.max(0, Math.min(1, frameCursor - frame));
      if (frame >= maxFrame) {
        frame = maxFrame;
        frameBlend = 0;
        frameCursor = frame;
      }
      draw();
    }

    function setFrame(value) {
      const maxFrame = Math.max(0, activeClip.frame_count - 1);
      frameCursor = Math.max(0, Math.min(maxFrame, Math.floor(Number(value) || 0)));
      frame = Math.max(0, Math.min(maxFrame, Math.floor(frameCursor)));
      frameBlend = 0;
      draw();
    }

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw();
    }

    function setClip(index) {
      activeClipIndex = index;
      activeClip = clips[index];
      clipSelect.value = String(index);
      frameCursor = Math.min(frameCursor, activeClip.frame_count - 1);
      frame = Math.max(0, Math.min(activeClip.frame_count - 1, Math.floor(frameCursor)));
      frameBlend = Math.max(0, Math.min(1, frameCursor - frame));
      clipTitle.textContent = activeClip.name;
      fpsText.textContent = String(Math.round(activeClip.fps * 1000) / 1000);
      bonesText.textContent = String(J);
      frameSlider.max = String(activeClip.frame_count - 1);
      lastFrameText.textContent = String(activeClip.frame_count - 1);
      setAttackConfigForActiveClip();
      updateClipModeUi();
      refreshSnapHitFrameButton();
      loadMeleeTargetOffsetFromActiveClip();
      loadCleanupFromActiveClip();
      writeAttackUi();
      loadFootLockFromActiveClip();
      if (idleClip) prepareIdleFootIkForClip(activeClip);
      draw();
    }

    function advancePlayback(now) {
      const dt = Math.min(0.1, (now - lastTime) / 1000);
      lastTime = now;
      if (playing) {
        const speed = Number(speedInput.value) || 1;
        frameCursor = (frameCursor + dt * activeClip.fps * speed) % activeClip.frame_count;
        frame = Math.floor(frameCursor);
        frameBlend = frameCursor - frame;
        draw();
      }
    }

    function setPlaying(next) {
      playing = Boolean(next);
      playButton.textContent = playing ? "Pause" : "Play";
      if (playing) {
        lastTime = performance.now();
        if (playTimer === null) {
          playTimer = window.setInterval(() => advancePlayback(performance.now()), 1000 / 60);
        }
      } else if (playTimer !== null) {
        window.clearInterval(playTimer);
        playTimer = null;
      }
    }

    function resetCamera() {
      yaw = -0.75;
      pitch = -0.18;
      zoom = 1.45;
      panX = 0;
      panY = 0;
      draw();
    }

    playButton.addEventListener("click", () => {
      setPlaying(!playing);
    });
    snapArmedFrameButton.addEventListener("click", snapToArmedFrame);
    snapHitFrameButton.addEventListener("click", snapToHitFrame);
    clipSelect.addEventListener("change", () => setClip(Number(clipSelect.value)));
    frameSlider.addEventListener("input", () => {
      setFrame(Number(frameSlider.value) || 0);
    });
    betweenSlider.addEventListener("input", () => {
      frameBlend = Math.max(0, Math.min(1, Number(betweenSlider.value) || 0));
      frameCursor = Math.max(0, Math.min(activeClip.frame_count - 1, frame + frameBlend));
      draw();
    });
    attackFrameBlendSlider.addEventListener("input", () => {
      frameBlend = Math.max(0, Math.min(1, Number(attackFrameBlendSlider.value) || 0));
      frameCursor = Math.max(0, Math.min(activeClip.frame_count - 1, frame + frameBlend));
      draw();
    });
    resetButton.addEventListener("click", resetCamera);
    volumesButton.addEventListener("click", () => {
      showVolumes = !showVolumes;
      volumesButton.textContent = showVolumes ? "Hide Colliders" : "Colliders";
      draw();
    });
    labelsButton.addEventListener("click", () => {
      showLabels = !showLabels;
      labelsButton.textContent = showLabels ? "Hide Labels" : "Labels";
      draw();
    });
    showIdleInput.addEventListener("change", () => {
      showIdle = Boolean(showIdleInput.checked && idleClip);
      draw();
    });
    showOriginalInput.addEventListener("change", () => {
      showOriginal = Boolean(showOriginalInput.checked);
      draw();
    });
    showModifiedInput.addEventListener("change", () => {
      showModified = Boolean(showModifiedInput.checked);
      draw();
    });
    idleFootIkInput.addEventListener("change", () => {
      useIdleFootIk = Boolean(idleFootIkInput.checked && idleClip);
      draw();
    });
    showPoleVectorsInput.addEventListener("change", () => {
      showPoleVectors = Boolean(showPoleVectorsInput.checked && idleClip);
      draw();
    });
    function handleFootLockInput() {
      enableLiveCleanupPreview();
      updateWorkingFootLockFromUi();
      if (idleClip) prepareIdleFootIkForClip(activeClip);
      draw();
    }
    async function saveFootLockForActiveClip() {
      updateWorkingFootLockFromUi();
      updateWorkingCleanupFromUi();
      attackConfig = attackConfigFromUi();
      saveWorkingFootLockToActiveClip();
      saveWorkingCleanupToActiveClip();
      footLockSaveState.textContent = "saving";
      const ok = await persistAttackConfig("feet saved");
      footLockSaveState.textContent = ok ? `saved ${activeClip.name}` : "save failed";
    }
    footLockInputs.left.addEventListener("input", handleFootLockInput);
    footLockInputs.right.addEventListener("input", handleFootLockInput);
    saveFootLockButton.addEventListener("click", saveFootLockForActiveClip);
    function enableLiveCleanupPreview() {
      if (!idleClip || isFinalOriginalClipSet) return;
      useIdleFootIk = true;
      idleFootIkInput.checked = true;
      showModified = true;
      showModifiedInput.checked = true;
    }
    pelvisOffsetInput.addEventListener("input", () => {
      enableLiveCleanupPreview();
      updateWorkingCleanupFromUi();
      prepareIdleFootIkForClip(activeClip);
      draw();
    });
    pelvisSourceInput.addEventListener("input", () => {
      enableLiveCleanupPreview();
      updateWorkingCleanupFromUi();
      prepareIdleFootIkForClip(activeClip);
      draw();
    });
    for (const input of Object.values(extraPelvisInputs)) {
      input.addEventListener("input", () => {
        enableLiveCleanupPreview();
        updateWorkingCleanupFromUi();
        prepareIdleFootIkForClip(activeClip);
        draw();
      });
    }
    attackToggle.addEventListener("click", () => {
      const collapsed = attackPanel.classList.toggle("collapsed");
      attackToggle.setAttribute("aria-expanded", String(!collapsed));
    });
    for (const input of Object.values(attackInputs)) {
      input.addEventListener("input", () => {
        const isMeleeTargetInput =
          input === attackInputs.meleeTargetXCm ||
          input === attackInputs.meleeTargetYCm ||
          input === attackInputs.meleeTargetZCm;
        updateWorkingMeleeTargetOffsetFromUi();
        attackConfig = attackConfigFromUi();
        writeAttackUi({ writeMeleeTargetInputs: !isMeleeTargetInput });
        attackSaveState.textContent = "";
        draw();
      });
    }
    saveAttackButton.addEventListener("click", saveAttackConfig);
    saveHitButton.addEventListener("click", saveHitConfig);
    saveArmedButton.addEventListener("click", saveArmedConfig);
    snapBetweenButton.addEventListener("click", snapBetweenToConfig);
    if (sword) {
      bladeSlider.addEventListener("input", () => {
        bladeScale = Math.max(0, Math.min(1, (Number(bladeSlider.value) || 0) / 100));
        attackConfig.blade_length = bladeScale;
        bladeText.textContent = `${Math.round(bladeScale * 100)}%`;
        attackSaveState.textContent = "";
        draw();
      });
    } else {
      bladeSlider.disabled = true;
      bladeText.textContent = "n/a";
    }

    canvas.addEventListener("mousedown", e => {
      drag = { x: e.clientX, y: e.clientY, button: e.button };
    });
    window.addEventListener("mouseup", () => { drag = null; });
    window.addEventListener("mousemove", e => {
      if (!drag) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      drag.x = e.clientX;
      drag.y = e.clientY;
      if (e.buttons & 2 || e.shiftKey) {
        panX += dx;
        panY += dy;
      } else {
        yaw -= dx * 0.006;
        pitch = Math.max(-1.35, Math.min(1.35, pitch - dy * 0.006));
      }
      draw();
    });
    canvas.addEventListener("contextmenu", e => e.preventDefault());
    canvas.addEventListener("wheel", e => {
      e.preventDefault();
      zoom *= Math.exp(-e.deltaY * 0.001);
      zoom = Math.max(0.12, Math.min(8, zoom));
      draw();
    }, { passive: false });
    window.addEventListener("keydown", e => {
      if (e.code === "Space") {
        e.preventDefault();
        playButton.click();
      } else if (e.code === "ArrowRight") {
        e.preventDefault();
        e.stopPropagation();
        setFrame(frame + 1);
      } else if (e.code === "ArrowLeft") {
        e.preventDefault();
        e.stopPropagation();
        setFrame(frame - 1);
      }
    });
    window.addEventListener("resize", resize);
    controlsToggleButton.addEventListener("click", () => {
      setControlsCollapsed(!controlsElement.classList.contains("controls-collapsed"));
    });

    function applyUrlState() {
      const params = new URLSearchParams(window.location.search);
      const clipParam = params.get("clip");
      let clipIndex = 0;
      if (clipParam) {
        const numeric = Number(clipParam);
        if (Number.isInteger(numeric) && clips[numeric]) {
          clipIndex = numeric;
        } else {
          const wanted = clipParam.toLowerCase();
          const found = clips.findIndex(c => c.name.toLowerCase() === wanted);
          if (found >= 0) clipIndex = found;
        }
      }
      setClip(clipIndex);
      const pelvisOffsetParam = Number(params.get("pelvisOffset"));
      if (Number.isFinite(pelvisOffsetParam)) {
        enableLiveCleanupPreview();
        pelvisOffsetScale = Math.max(0, Math.min(1, pelvisOffsetParam));
        pelvisOffsetInput.value = String(pelvisOffsetScale);
        pelvisOffsetText.textContent = pelvisOffsetScale.toFixed(2);
      }
      const pelvisSourceParam = Number(params.get("pelvisSource"));
      if (Number.isFinite(pelvisSourceParam)) {
        enableLiveCleanupPreview();
        pelvisSourceBlend = Math.max(0, Math.min(1, pelvisSourceParam));
        pelvisSourceInput.value = String(pelvisSourceBlend);
        pelvisSourceText.textContent = pelvisSourceBlend.toFixed(2);
      }
      if (Number.isFinite(pelvisOffsetParam) || Number.isFinite(pelvisSourceParam)) {
        prepareIdleFootIkForClip(activeClip);
      }
      const frameParam = Number(params.get("frame"));
      if (Number.isFinite(frameParam)) setFrameExact(frameParam);
      const yawParam = Number(params.get("yaw"));
      const pitchParam = Number(params.get("pitch"));
      const zoomParam = Number(params.get("zoom"));
      const panXParam = Number(params.get("panX"));
      const panYParam = Number(params.get("panY"));
      if (Number.isFinite(yawParam)) yaw = yawParam;
      if (Number.isFinite(pitchParam)) pitch = Math.max(-1.35, Math.min(1.35, pitchParam));
      if (Number.isFinite(zoomParam)) zoom = Math.max(0.12, Math.min(8, zoomParam));
      if (Number.isFinite(panXParam)) panX = panXParam;
      if (Number.isFinite(panYParam)) panY = panYParam;
      draw();
    }

    applyUrlState();
    resize();
    loadAttackConfig();
  </script>
</body>
</html>
"""


def write_viewer(payload: dict[str, object], output: Path) -> None:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    html = HTML_TEMPLATE.replace("__PAYLOAD_JSON__", json.dumps(payload, separators=(",", ":")))
    output.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a raw fullbody slash HTML viewer.")
    parser.add_argument("--slash-dir", type=Path, default=DEFAULT_SLASH_DIR)
    parser.add_argument("--sword-fbx", type=Path, default=DEFAULT_SWORD_FBX)
    parser.add_argument("--no-sword", action="store_true")
    parser.add_argument("--idle-npz", type=Path, default=DEFAULT_IDLE_NPZ)
    parser.add_argument("--no-idle", action="store_true")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    idle_npz = None if args.no_idle else args.idle_npz.resolve()
    sword_fbx = None if args.no_sword else args.sword_fbx.resolve()
    payload = make_payload(args.slash_dir.resolve(), sword_fbx, idle_npz)
    write_viewer(payload, args.output)
    print(args.output.resolve())
    for clip in payload["clips"]:
        print(f"{clip['name']}: {clip['frame_count']} frames")
    if "sword" in payload:
        sword = payload["sword"]
        print(
            "sword:"
            f" {sword['vertex_count']} verts,"
            f" {sword['triangle_count']} tris,"
            f" blade axis {sword['blade_axis']},"
            f" base {sword['blade_base_m']:.4f} m,"
            f" tip {sword['blade_tip_m']:.4f} m"
        )


if __name__ == "__main__":
    main()
