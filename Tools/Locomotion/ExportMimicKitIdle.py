"""Read the project's actual standing idle, without changing editor/Play/assets."""
import json,math,os
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/MimicKitUEFN/idle';out.mkdir(exist_ok=True)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
def state():
    return dict(process_id=os.getpid(),world=editor.get_editor_world().get_path_name() if editor.get_editor_world() else None,
        play=editor.get_game_world().get_path_name() if editor.get_game_world() else None,
        dirty=sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
                     +unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
before=state()
assets=unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_class(
    unreal.TopLevelAssetPath('/Script/Engine','AnimSequence'),True)
paths=[str(a.package_name) for a in assets if str(a.asset_name)=='M_Neutral_Stand_Idle_Loop']
# Same original UEFN clip used by the existing breathing exporter. Avoid the
# separate /_mygame duplicate rather than relying on asset registry ordering.
path='/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop'
assert path in paths,paths
asset=unreal.load_asset(path);duration=asset.get_play_length();fps=60
count=round(duration*fps)+1
assert abs((count-1)/fps-duration)<1e-5,'Idle duration must preserve original frame timing'
names=json.loads((root/'Labs/SwordHolsterLab/data/motions.json').read_text())['names']
options=unreal.AnimPoseEvaluationOptions(evaluation_type=unreal.AnimDataEvalType.RAW,
    should_retarget=False,extract_root_motion=False)
rows=[]
for tick in range(count):
    pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(asset,tick/fps,options)
    frame=[]
    for name in names:
        t=unreal.AnimPoseExtensions.get_bone_pose(pose,name,unreal.AnimPoseSpaces.WORLD)
        v,q=t.translation,t.rotation
        frame.append([v.x,v.y,v.z,q.x,q.y,q.z,q.w])
    assert all(math.isfinite(v) for bone in frame for v in bone)
    rows.append(dict(tick=tick,pose=frame))
assert state()==before,'Read-only idle export unexpectedly changed editor state'
result=dict(asset=path,source='Original project idle animation; not an NN continuation',
    fps=fps,seconds=duration,names=names,velocity_mesh_cm_s=[0,0,0],rows=rows)
(out/'M_Neutral_Stand_Idle_Loop.json').write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
(out/'export-receipt.json').write_text(json.dumps(dict(asset=path,frames=count,seconds=duration,
    source=result['source'],editor_unchanged=True,editor=before),indent=2),encoding='utf-8')
print(json.dumps(dict(asset=path,frames=count,seconds=duration,editor_unchanged=True)))
