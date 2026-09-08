"""Mirror only right finger edits to left in closed_fist; run in Unreal Python.

Defaults to inspection. Set APPLY=True in exec globals to publish, with backup.
Uses UE AnimationRuntime::MirrorPose reference-rotation correction (X plane).
"""
import json
import math
import shutil
from datetime import datetime
from pathlib import Path
import unreal

asset = unreal.load_asset('/Game/_mygame/closed_fist')
model = asset.data_model_interface
ext = unreal.AnimPoseExtensions
local, world = unreal.AnimPoseSpaces.LOCAL, unreal.AnimPoseSpaces.WORLD
ref = ext.get_reference_pose(asset.get_skeleton())
names = [str(n) for n in model.get_bone_track_names()]
right = [n for n in names if n.endswith('_r') and n.split('_')[0] in
         ('index', 'middle', 'ring', 'pinky', 'thumb')]
left = [n[:-1]+'l' for n in right]
assert len(right) == 19 and all(n in names for n in left)
assert model.get_number_of_frames() == 1, 'This script expects the authored static pose.'
rate = model.get_frame_rate()
end = rate.denominator / rate.numerator
times = [0.0, end / 2, end]
raw_options = unreal.AnimPoseEvaluationOptions(evaluation_type=unreal.AnimDataEvalType.RAW, should_retarget=False)
source_options = unreal.AnimPoseEvaluationOptions(evaluation_type=unreal.AnimDataEvalType.SOURCE, should_retarget=False)
before = [ext.get_anim_pose_at_time(asset, t, raw_options) for t in times]
source = [ext.get_anim_pose_at_time(asset, t, source_options) for t in times]

def parent(n):
    finger, joint, side = n.split('_')
    if joint == 'metacarpal' or (finger == 'thumb' and joint == '01'):
        return 'hand_' + side
    return finger + '_' + ('metacarpal' if joint == '01' else '%02d' % (int(joint)-1)) + '_' + side

def rq(n):
    return ext.get_ref_bone_pose(ref, n, world).rotation

def mirror(q):
    return unreal.Quat(q.x, -q.y, -q.z, q.w)

def mirrored_rotation(pose, r, l):
    q = rq(parent(r)) * ext.get_bone_pose(pose, r, local).rotation
    return (rq(parent(l)).inversed() * mirror(q) * mirror(rq(r)).inversed() * rq(l)).normalized()

def mirrored_translation(pose, r, l):
    v = rq(parent(r)).rotate_vector(ext.get_bone_pose(pose,r,local).translation)
    return rq(parent(l)).unrotate_vector(unreal.Vector(-v.x,v.y,v.z))

def angle(q, p):
    d = min(1.0, abs(q.x*p.x + q.y*p.y + q.z*p.z + q.w*p.w))
    return math.degrees(2*math.acos(d))

def error(t, u):
    return max((t.translation-u.translation).length(), (t.scale3d-u.scale3d).length(), angle(t.rotation, u.rotation))

def curve_id(n):
    identifier = unreal.AnimationCurveIdentifier()
    identifier.set_curve_identifier(n, unreal.RawCurveTrackTypes.RCT_TRANSFORM)
    return identifier

# Preserve authored finger-position edits too, but do not introduce scale edits.
trs_error = max(max((ext.get_bone_pose(p,r,local).translation-ext.get_bone_pose(s,r,local).translation).length(),
                    (ext.get_bone_pose(p,r,local).scale3d-ext.get_bone_pose(s,r,local).scale3d).length())
                for p,s in zip(before,source) for r in right)
assert max((ext.get_bone_pose(p,r,local).scale3d-ext.get_bone_pose(s,r,local).scale3d).length()
           for p,s in zip(before,source) for r in right) < 1e-4
assert max(error(ext.get_bone_pose(p,l,local),ext.get_bone_pose(s,l,local))
           for p,s in zip(before,source) for l in left) < .002, 'Left hand already has edits; inspect first.'
assert max(error(ext.get_bone_pose(before[0],n,local),ext.get_bone_pose(before[-1],n,local))
           for n in names) < .002, 'Pose is not static.'
values = {}
for r,l in zip(right,left):
    base = ext.get_bone_pose(source[0],l,local)
    q = (base.rotation.inversed() * mirrored_rotation(before[0],r,l)).normalized()
    delta = base.rotation.unrotate_vector(mirrored_translation(before[0],r,l)-base.translation)
    delta = unreal.Vector(delta.x/base.scale3d.x,delta.y/base.scale3d.y,delta.z/base.scale3d.z)
    values[l] = unreal.Transform(rotation=q.rotator(), location=delta, scale=unreal.Vector(1,1,1))

report = {'asset':asset.get_path_name(), 'left_finger_bones':left, 'mirror_plane':'component X=0',
          'original_transform_curves':model.get_number_of_transform_curves(), 'right_translation_scale_edit_error':trs_error,
          'max_left_rotation_change_degrees':max(angle(mirrored_rotation(before[0],r,l),ext.get_bone_pose(before[0],l,local).rotation) for r,l in zip(right,left))}
if globals().get('APPLY', False):
    root = Path(unreal.Paths.project_dir()).resolve()
    backup = root/'Saved'/'ClosedFistMirror'/datetime.now().strftime('%Y%m%d_%H%M%S')
    backup.mkdir(parents=True, exist_ok=False)
    # Save and back up this animation only, never other open/dirty assets.
    assert unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=True)
    shutil.copy2(root/'Content/_mygame/closed_fist.uasset', backup/'closed_fist.uasset')
    ctl = asset.controller
    added = []
    ctl.open_bracket('Mirror right fist onto left fingers', True)
    try:
        for l in left:
            assert ctl.add_curve(curve_id(l), 0x24, True)  # Editable | DriveTrack
            added.append(l)
            assert ctl.set_transform_curve_keys(curve_id(l), [values[l], values[l]], [0.0,end], True)
    finally:
        ctl.close_bracket(True)
    after = [ext.get_anim_pose_at_time(asset,t,raw_options) for t in times]
    unchanged = max(error(ext.get_bone_pose(p,n,local),ext.get_bone_pose(b,n,local))
                    for p,b in zip(after,before) for n in names if n not in left)
    mirror_error = max(angle(ext.get_bone_pose(p,l,local).rotation,mirrored_rotation(b,r,l))
                       for p,b in zip(after,before) for r,l in zip(right,left))
    left_trs = max(max((ext.get_bone_pose(p,l,local).translation-mirrored_translation(b,r,l)).length(),
                      (ext.get_bone_pose(p,l,local).scale3d-ext.get_bone_pose(b,l,local).scale3d).length())
                   for p,b in zip(after,before) for r,l in zip(right,left))
    report.update(backup=str(backup), unchanged_bone_max_error=unchanged,
                  mirrored_rotation_max_error_degrees=mirror_error,left_translation_scale_error=left_trs)
    if unchanged > .002 or mirror_error > .002 or left_trs > 1e-4:
        for l in added:
            ctl.remove_curve(curve_id(l), True)
        raise RuntimeError('Validation failed; removed new curves: '+json.dumps(report))
    assert unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)
    report['saved'] = True
    (backup/'audit.json').write_text(json.dumps(report,indent=2))
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([asset])
print(json.dumps(report))
