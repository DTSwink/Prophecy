"""Fit UEFN-shared-bone skin weights that best reproduce the full MetaHuman rig.

Inputs (produced from the live editor):
  Saved/PoseFit/source_mesh.json    reference vertex positions + full 167-bone weights
  Saved/PoseFit/pose_samples.jsonl  component-space bone transforms over sampled poses
  Tools/MetaHuman/skeleton_snapshots.json  reference hierarchies

Output:
  Saved/PoseFit/reduced_weights.json  per-vertex shared-bone weights (max 8 influences)

Ground truth per pose is the linear-blend-skinned vertex position using the source
mesh's full weights and the recorded pose transforms, which include everything the
MetaHuman post-process rig (RigLogic body) does to helper joints. The fit solves,
per vertex, non-negative sum-to-one least squares restricted to shared UEFN bones.

Convention note: the direct body runs in the UEFN convention (UEFN bind pose and
the UEFN mannequin's pose transforms), while the recorded MetaHuman probe poses
live in the MetaHuman convention, which places shared bones differently (up to
~9 cm on twist pivots, ~15 cm on driven fingers, due to compatible-skeleton
retargeting). The ground truth is therefore built on a synthetic rigid skeleton:

  - each shared bone takes the UEFN motion delta applied to the MetaHuman bind:
    G_shared = U_pose * inv(U_bind) * M_bind, so its truth skinning matrix
    equals the runtime candidate matrix exactly;
  - each MetaHuman-only helper keeps its recorded pose relative to its nearest
    shared ancestor A and is re-rooted onto the synthetic ancestor:
    G_helper = G_A * inv(M_pose_A) * M_pose_helper.

At the rest pose this reduces to the identity, and helper joints preserve the
local behavior RigLogic gave them, so the fit target is exactly achievable for
rigid vertices and locally faithful everywhere else. Per-vertex anchor blending
of frame carries was tried first and rejected: it is non-rigid and produced
visible webbing between fingers.
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
from scipy.optimize import nnls

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POSEFIT = os.path.join(PROJECT, "Saved", "PoseFit")
SNAPSHOT = os.path.join(PROJECT, "Tools", "MetaHuman", "skeleton_snapshots.json")

MAX_INFLUENCES = 8
SUM_CONSTRAINT_SCALE = 25.0
WEIGHT_EPSILON = 5e-4
PRIOR_RIDGE_SCALE = 20.0


def transform_matrix(translation, quaternion, scale):
    x, y, z, w = quaternion
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    rotation = np.array(
        [
            [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy)],
            [2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx)],
            [2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)],
        ]
    )
    matrix = np.eye(4)
    matrix[:3, :3] = rotation * np.asarray(scale)[None, :]
    matrix[:3, 3] = translation
    return matrix


def main():
    started = time.time()
    with open(SNAPSHOT, encoding="utf-8") as handle:
        snapshot = json.load(handle)
    uefn_bones_ref = snapshot["uefn_reference"]["bones"]
    uefn_names = {b["name"] for b in uefn_bones_ref}
    mh_bones = snapshot["fitted_metahuman_body_reference"]["bones"]
    mh_names = [b["name"] for b in mh_bones]
    parent_of = {b["name"]: b["parent"] for b in mh_bones}
    shared = {n for n in mh_names if n in uefn_names}

    ref_component = {}
    for bone in mh_bones:
        g = bone["global"]
        ref_component[bone["name"]] = transform_matrix(
            g["translation_cm"], g["rotation_xyzw"], g["scale_xyz"]
        )
    uefn_ref_component = {}
    for bone in uefn_bones_ref:
        g = bone["global"]
        uefn_ref_component[bone["name"]] = transform_matrix(
            g["translation_cm"], g["rotation_xyzw"], g["scale_xyz"]
        )

    children_of = {}
    for bone in mh_bones:
        children_of.setdefault(bone["parent"], []).append(bone["name"])

    def nearest_shared(name):
        current = name
        while current is not None and current not in shared:
            current = parent_of[current]
        return current

    def shared_children(name):
        result = []
        stack = list(children_of.get(name, []))
        while stack:
            child = stack.pop()
            if child in shared:
                result.append(child)
            else:
                stack.extend(children_of.get(child, []))
        return result

    candidate_cache = {}

    def candidates_for(bone_name):
        """Anchor plus one hop up and down the shared hierarchy, never root.

        Sibling bones (children of the anchor's parent) are intentionally not
        candidates: with a limited pose set they correlate with the anchor and
        NNLS happily assigns cross-limb weights that turn into spikes on poses
        outside the sample set.
        """
        if bone_name in candidate_cache:
            return candidate_cache[bone_name]
        anchor = nearest_shared(bone_name)
        result = set()
        if anchor is not None:
            result.add(anchor)
            anchor_parent = nearest_shared(parent_of[anchor]) if parent_of[anchor] else None
            if anchor_parent:
                result.add(anchor_parent)
            result.update(shared_children(anchor))
        result.discard("root")
        candidate_cache[bone_name] = result
        return result

    with open(os.path.join(POSEFIT, "source_mesh.json"), encoding="utf-8") as handle:
        mesh = json.load(handle)
    positions = np.asarray(mesh["positions"])
    source_weights = mesh["weights"]
    num_vertices = len(source_weights)

    samples = []
    with open(os.path.join(POSEFIT, "pose_samples.jsonl"), encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    num_poses = len(samples)
    print(f"poses={num_poses} vertices={num_vertices}")

    used_bones = sorted({name for weights in source_weights for name in weights})
    bone_index = {name: i for i, name in enumerate(used_bones)}
    shared_used = sorted(
        set(used_bones) | {c for b in used_bones for c in candidates_for(b)}
    )
    shared_used = [b for b in shared_used if b in shared]
    shared_index = {name: i for i, name in enumerate(shared_used)}

    all_needed = sorted(set(used_bones) | set(shared_used))
    needed_index = {name: i for i, name in enumerate(all_needed)}
    hierarchy_order = [b["name"] for b in mh_bones if b["name"] in set(all_needed)]

    # Truth skinning matrices on the synthetic rigid skeleton (see docstring),
    # already multiplied by the inverse MetaHuman bind.
    skin = np.zeros((num_poses, len(all_needed), 4, 4))
    for p, sample in enumerate(samples):
        uefn_pose = sample["uefn_bones"]
        mh_pose = sample["bones"]
        mh_pose_global = {}
        synthetic_global = {}
        for name in hierarchy_order:
            row = mh_pose[name]
            mh_pose_global[name] = transform_matrix(row[0:3], row[3:7], row[7:10])
            if name in shared:
                u_row = uefn_pose[name]
                u_pose = transform_matrix(u_row[0:3], u_row[3:7], u_row[7:10])
                synthetic_global[name] = (
                    u_pose
                    @ np.linalg.inv(uefn_ref_component[name])
                    @ ref_component[name]
                )
            else:
                anchor = nearest_shared(name)
                relative_pose = (
                    np.linalg.inv(mh_pose_global[anchor]) @ mh_pose_global[name]
                )
                synthetic_global[name] = synthetic_global[anchor] @ relative_pose
            skin[p, needed_index[name]] = synthetic_global[name] @ np.linalg.inv(
                ref_component[name]
            )
    skin = skin[:, :, :3, :]

    homogeneous = np.concatenate([positions, np.ones((num_vertices, 1))], axis=1)

    # Ground truth positions per pose using the full source weights, evaluated
    # in the MetaHuman convention. Candidates use the same convention; the
    # runtime discrepancy between MH and UEFN shared-bone placement is treated
    # as a rigid-ish per-bone offset that the weights transfer across. The
    # earlier per-anchor "carry" blend was non-rigid and produced webbing.
    truth = np.zeros((num_vertices, num_poses, 3))
    for v in range(num_vertices):
        vertex = homogeneous[v]
        for name, weight in source_weights[v].items():
            truth[v] += weight * (skin[:, needed_index[name]] @ vertex)
    print(f"ground truth built in {time.time() - started:.1f}s")

    reduced = []
    errors_before = np.zeros(num_vertices)
    errors_after = np.zeros(num_vertices)
    for v in range(num_vertices):
        weights = source_weights[v]
        vertex = homogeneous[v]
        candidate_set = set()
        for name in weights:
            if name in shared:
                candidate_set.add(name)
            candidate_set.update(candidates_for(name))
        candidate_list = sorted(candidate_set & set(shared_used))
        if not candidate_list:
            raise RuntimeError(f"vertex {v} has no shared candidates")

        columns = np.stack(
            [
                (skin[:, needed_index[name]] @ vertex).reshape(-1)
                for name in candidate_list
            ],
            axis=1,
        )
        target = truth[v].reshape(-1)

        # Baseline error: renormalized shared portion of the original weights.
        base = np.array([weights.get(name, 0.0) for name in candidate_list])
        if base.sum() > 1e-6:
            base_n = base / base.sum()
            errors_before[v] = np.sqrt(
                np.mean(
                    np.sum(
                        ((columns @ base_n).reshape(num_poses, 3) - truth[v]) ** 2,
                        axis=1,
                    )
                )
            )

        a = np.vstack([columns, SUM_CONSTRAINT_SCALE * np.ones((1, len(candidate_list)))])
        b = np.concatenate([target, [SUM_CONSTRAINT_SCALE]])
        solution, _ = nnls(a, b)

        # Sparsify to the top influences and re-solve on the kept set.
        if np.count_nonzero(solution > WEIGHT_EPSILON) > MAX_INFLUENCES:
            keep = np.argsort(solution)[-MAX_INFLUENCES:]
            a_kept = np.vstack(
                [columns[:, keep], SUM_CONSTRAINT_SCALE * np.ones((1, len(keep)))]
            )
            solution_kept, _ = nnls(a_kept, b)
            full = np.zeros_like(solution)
            full[keep] = solution_kept
            solution = full

        total = solution.sum()
        if total <= 1e-6:
            raise RuntimeError(f"vertex {v} produced empty weights")
        solution /= total
        solution[solution < WEIGHT_EPSILON] = 0.0
        solution /= solution.sum()

        errors_after[v] = np.sqrt(
            np.mean(
                np.sum(
                    ((columns @ solution).reshape(num_poses, 3) - truth[v]) ** 2,
                    axis=1,
                )
            )
        )
        reduced.append(
            {
                candidate_list[i]: float(solution[i])
                for i in range(len(candidate_list))
                if solution[i] > 0.0
            }
        )
        if v % 1000 == 0:
            print(f"vertex {v} done at {time.time() - started:.1f}s")

    print(
        "errors cm: before mean={:.4f} p99={:.4f} max={:.4f} | after mean={:.4f} p99={:.4f} max={:.4f}".format(
            errors_before.mean(),
            np.percentile(errors_before, 99),
            errors_before.max(),
            errors_after.mean(),
            np.percentile(errors_after, 99),
            errors_after.max(),
        )
    )
    worst = np.argsort(errors_after)[-12:][::-1]
    for v in worst:
        print(
            "worst vertex {} err={:.4f} pos={} bones={}".format(
                v,
                errors_after[v],
                np.round(positions[v], 1).tolist(),
                {k: round(w, 3) for k, w in reduced[v].items()},
            )
        )

    output = os.path.join(POSEFIT, "reduced_weights.json")
    with open(output, "w", encoding="utf-8") as handle:
        json.dump({"weights": reduced}, handle)
    print(f"WROTE {output} in {time.time() - started:.1f}s total")


if __name__ == "__main__":
    main()
