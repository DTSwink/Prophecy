"""Read-only export of the native BuildFingers inputs; no Play, edits or saves."""
import unreal, json, pathlib, datetime, hashlib

root = pathlib.Path(unreal.Paths.project_dir())
agents = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
          if isinstance(a, unreal.ProphecyAgent)]
agent = agents[0] if agents else unreal.get_default_object(unreal.load_class(None, '/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent_C'))
mesh = agent.get_editor_property('mesh').get_skeletal_mesh_asset()
clip = agent.get_editor_property('closed_fist_animation')
if not isinstance(clip, unreal.AnimSequence):
    clip = unreal.load_asset(str(clip))
assert mesh and clip
modifier = unreal.SkeletonModifier()
assert modifier.set_skeletal_mesh(mesh)
ext = unreal.AnimPoseExtensions
ref = ext.get_reference_pose(clip.get_skeleton())
frame = ext.get_anim_pose_at_time(clip, 0, unreal.AnimPoseEvaluationOptions(
    evaluation_type=unreal.AnimDataEvalType.RAW, should_retarget=False))
world = unreal.AnimPoseSpaces.WORLD

def pack(t):
    assert (t.scale3d-unreal.Vector(1,1,1)).length()<1e-4, 'Scaled finger reference requires explicit scale support'
    p, q = t.translation, t.rotation.normalized()
    return [p.x, p.y, p.z, q.x, q.y, q.z, q.w]

# Export component transforms. The standalone conversion mirrors BuildFingers,
# including reference-basis correction and folded metacarpals.
names = set()
for side in ['l', 'r']:
    names.add('hand_' + side)
    for finger in ['thumb', 'index', 'middle', 'ring', 'pinky']:
        for joint in range(1, 4):
            name = f'{finger}_{joint:02d}_{side}'
            names.add(name)
            names.add(str(modifier.get_parent_name(name)))
bones = {}
for name in sorted(names):
    bones[name] = dict(parent=str(modifier.get_parent_name(name)),
        mesh=pack(modifier.get_bone_transform(name, True)),
        reference=pack(ext.get_ref_bone_pose(ref, name, world)),
        closed=pack(ext.get_bone_pose(frame, name, world)))
out = dict(schema=1, exported=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    mesh=mesh.get_path_name(), clip=clip.get_path_name(), bones=bones,
    nativeSourceSha256=hashlib.sha256((root/'Source/GameAnimationSample3/Private/ProphecyReachLibrary.cpp').read_bytes()).hexdigest())
out['poseSha256'] = hashlib.sha256(json.dumps(bones, sort_keys=True).encode()).hexdigest()
(root/'Labs/ReachLab/fingers.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps(dict(mesh=out['mesh'], clip=out['clip'], bones=len(bones))))
