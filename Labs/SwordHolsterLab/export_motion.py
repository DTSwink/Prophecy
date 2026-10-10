import unreal,pathlib,json
out=pathlib.Path(unreal.Paths.project_dir())/'Labs/SwordHolsterLab/data'
names=['root','pelvis','spine_01','spine_02','spine_03','spine_04','spine_05','clavicle_l','upperarm_l','lowerarm_l','hand_l','clavicle_r','upperarm_r','lowerarm_r','hand_r','neck_01','neck_02','head','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r']
parents=[-1,0,1,2,3,4,5,6,7,8,9,6,11,12,13,6,15,16,1,18,19,20,1,22,23,24]
result={'names':names,'parents':parents,'fps':30,'coordinates':'Unreal component XYZ centimetres, quaternion XYZW','motions':{}}
options=unreal.AnimPoseEvaluationOptions(evaluation_type=unreal.AnimDataEvalType.RAW,should_retarget=False)
for key,name in [('idle','M_Neutral_Stand_Idle_Loop'),('walk','M_Neutral_Walk_Loop_F')]:
 asset=unreal.load_asset('/Game/_mygame/'+name)
 if not asset:
  paths=unreal.EditorAssetLibrary.list_assets('/Game',recursive=True,include_folder=False)
  path=next(p for p in paths if p.rsplit('/',1)[-1].split('.')[0]==name)
  asset=unreal.load_asset(path)
 length=asset.get_play_length();frames=[]
 for f in range(round(length*30)+1):
  pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(asset,min(length,f/30),options)
  row=[]
  for bone in names:
   x=unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.WORLD)
   row.append([x.translation.x,x.translation.y,x.translation.z,x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w])
  frames.append(row)
 result['motions'][key]={'asset':asset.get_path_name(),'duration':length,'frames':frames}
 print('DS_MOTION',key,len(frames))
(out/'motions.json').write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
