"""Read UE's actual omni animations and their root velocities. No asset writes."""
import unreal,json,pathlib
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/OmniRecord20261015';out.mkdir(parents=True,exist_ok=True)
registry=unreal.AssetRegistryHelpers.get_asset_registry()
assets=registry.get_assets_by_class(unreal.TopLevelAssetPath('/Script/Engine','AnimSequence'),True)
paths=sorted(str(a.package_name) for a in assets if str(a.asset_name).startswith(('M_Neutral_Run_Loop_','M_Neutral_Walk_Loop_')))
options=unreal.AnimPoseEvaluationOptions(evaluation_type=unreal.AnimDataEvalType.RAW,should_retarget=False,extract_root_motion=False)
clips=[]
for path in paths:
 a=unreal.load_asset(path);duration=a.get_play_length()
 poses=[unreal.AnimPoseExtensions.get_anim_pose_at_time(a,t,options) for t in (0,duration*.5,duration)]
 roots=[unreal.AnimPoseExtensions.get_bone_pose(p,'root',unreal.AnimPoseSpaces.WORLD) for p in poses]
 v=(roots[-1].translation-roots[0].translation)/duration
 clips.append({'asset':path,'seconds':duration,'velocity_mesh_cm_s':[v.x,v.y,v.z],'root_quats':[[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w] for t in roots]})
(out/'clips.json').write_text(json.dumps(clips,indent=2),encoding='utf-8');print('OMNI_CLIPS',len(clips))
