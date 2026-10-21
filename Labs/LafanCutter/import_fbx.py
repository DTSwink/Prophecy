"""Append a full FBX animation to a Cutter dataset, preserving its source rig.

Requires Stepper's existing Autodesk FBX SDK environment. No retargeting or cleanup.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from motion import atomic_json, clip_record, read_motion, save_dataset

STEPPER = Path.home() / 'Documents/Cursor/stepper'
sys.path.insert(0, str(STEPPER / 'fbx_npz_pipeline'))
import fbx_to_npz as sdk


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def convert(source, target):
    manager, scene = sdk.load_scene(source)
    try:
        source_axis, output_axis, converted = sdk.normalize_scene_axis_system(scene)
        units = sdk.get_system_unit(scene)
        factor = units['scale_factor_cm'] * units['multiplier']
        nodes = sdk.collect_skeleton_nodes(scene)
        parents = sdk.get_parent_indices(nodes)
        if not nodes or sum(parents < 0) != 1 or parents[0] != -1:
            raise ValueError('Expected one connected skeleton')
        times, fps, start, stop = sdk.make_sample_times(scene)
        names = [re.sub(r'[\s{}]', '_', n.GetName()) for n in nodes]
        if len(set(names)) != len(names):
            raise ValueError('Duplicate joint names')
        pos = np.empty((len(times), len(nodes), 3))
        rot = np.empty((len(times), len(nodes), 3, 3))
        max_scale_error = 0.
        scaled_leaf_helpers = {}
        for f, time in enumerate(times):
            for j, node in enumerate(nodes):
                matrix = node.EvaluateGlobalTransform(time)
                pos[f, j] = list(matrix.GetT())[:3]
                rot[f, j] = Rotation.from_quat(list(matrix.GetQ())).as_matrix()
                scale = np.array(list(matrix.GetS())[:3])
                error = np.max(np.abs(scale-1))
                max_scale_error = max(max_scale_error, error)
                if error > 1e-5:
                    if j in parents or not names[j].lower().startswith('locator'):
                        raise ValueError('Scaled skeletal joint requires explicit scale handling')
                    # A leaf locator's display size does not affect skeletal FK.
                    # Keep it in the archived FBX and disclose its omitted scale.
                    scaled_leaf_helpers[names[j]] = scale.tolist()
        pos *= factor
        local_pos, local_rot = pos.copy(), rot.copy()
        for j, p in enumerate(parents):
            if p >= 0:
                inverse = rot[:, p].transpose(0, 2, 1)
                local_pos[:, j] = np.einsum('fij,fj->fi', inverse, pos[:, j]-pos[:, p])
                local_rot[:, j] = inverse @ rot[:, j]
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Gimbal lock detected')
            angles = Rotation.from_matrix(local_rot.reshape(-1, 3, 3)).as_euler('ZYX', degrees=True).reshape(len(times), len(nodes), 3)
        order = []
        lines = ['HIERARCHY']

        def hierarchy(j, depth=0):
            pad = '  '*depth
            lines.extend([pad+('ROOT ' if depth == 0 else 'JOINT ')+names[j], pad+'{',
                          pad+'  OFFSET 0 0 0', pad+'  CHANNELS 6 Xposition Yposition Zposition Zrotation Yrotation Xrotation'])
            order.append(j)
            children = np.flatnonzero(parents == j)
            for child in children:
                hierarchy(child, depth+1)
            if not len(children):
                lines.extend([pad+'  End Site', pad+'  {', pad+'    OFFSET 0 0 0', pad+'  }'])
            lines.append(pad+'}')

        hierarchy(0)
        values = np.concatenate([local_pos[:, order], angles[:, order]], axis=-1).reshape(len(times), -1)
        lines.extend(['MOTION', f'Frames: {len(times)}', f'Frame Time: {1/fps:.17g}'])
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('w', encoding='utf-8', newline='\n') as out:
            out.write('\n'.join(lines)+'\n')
            np.savetxt(out, values, fmt='%.10f')
        decoded = read_motion(target)
        indices = [decoded.names.index(n) for n in names]
        position_error = float(np.max(np.abs(decoded.positions[:, indices]*100-pos)))
        # Independently reconstruct orientations from the serialized Euler channels.
        exported = decoded.values.reshape(len(times), len(nodes), 6)
        rebuilt = np.empty_like(rot)
        for k, j in enumerate(order):
            r = Rotation.from_euler('ZYX', exported[:, k, 3:], degrees=True).as_matrix()
            rebuilt[:, j] = r if parents[j] < 0 else rebuilt[:, parents[j]] @ r
        angle_error = float(np.max(Rotation.from_matrix((rebuilt.transpose(0, 1, 3, 2) @ rot).reshape(-1, 3, 3)).magnitude()))
        if position_error > .001 or angle_error > 1e-6:
            raise ValueError(f'FBX/BVH round-trip failed: {position_error} cm, {angle_error} rad')
        return dict(source_fbx=str(source), source_fbx_sha256=digest(source), frames=len(times), fps=fps,
                    source_frame_range=[start, stop], skeleton_joints=len(nodes), source_axis=source_axis,
                    output_axis=output_axis, axis_converted=converted, source_units=units,
                    max_global_scale_error=float(max_scale_error), max_position_error_cm=position_error,
                    leaf_locator_display_scales_not_in_bvh=scaled_leaf_helpers,
                    max_rotation_error_rad=angle_error, conversion='SDK global transforms; Y-up centimetres; full local translation and ZYX rotation; no retargeting')
    finally:
        manager.Destroy()


def append(source, manifest):
    original = manifest.read_bytes()
    doc = json.loads(original)
    source_hash = digest(source)
    if any(c.get('source_fbx_sha256') == source_hash for c in doc['clips']):
        raise ValueError('This exact FBX is already in the dataset')
    folder = manifest.parent / 'imports' / (source.stem+'_'+source_hash[:12])
    folder.mkdir(parents=True, exist_ok=True)
    archived_source = folder / source.name
    shutil.copy2(source, archived_source)
    exported = folder / (source.stem+'.bvh')
    receipt = convert(archived_source, exported)
    receipt['original_source_fbx'] = str(source)
    motion = read_motion(exported)
    entry = {**clip_record(motion, 0, motion.count-1), 'label': source.stem+' · full clip',
             'source_fbx': str(source), 'source_fbx_sha256': source_hash,
             'archived_fbx': str(archived_source), 'conversion_report': str(folder/'conversion.json')}
    atomic_json(folder / 'conversion.json', receipt)
    # Existing selections and their provenance are reused; saved cuts stay byte-identical.
    for row in doc['clips']:
        if digest(manifest.parent / row['file']) != row['sha256']:
            raise ValueError('An existing dataset cut changed')
    if manifest.read_bytes() != original:
        raise ValueError('Dataset changed during conversion; retry from the current revision')
    atomic_json(folder / 'dataset-before-import.json', doc)
    result = save_dataset(manifest.parent.parent, doc['name'], doc['clips']+[entry])
    after = json.loads(result.read_text(encoding='utf-8'))
    assert [c['sha256'] for c in after['clips'][:-1]] == [c['sha256'] for c in doc['clips']]
    assert digest(source) == source_hash == digest(archived_source)
    receipt.update(dataset=str(result), total_clips=len(after['clips']), existing_cut_hashes_unchanged=True,
                   original_fbx_unchanged=True)
    atomic_json(folder / 'conversion.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('dataset', type=Path)
    args = parser.parse_args()
    print(json.dumps(append(args.source.resolve(), args.dataset.resolve()), indent=2))
