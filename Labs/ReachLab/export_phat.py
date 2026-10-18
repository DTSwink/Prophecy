"""Run through Tools/RunUnrealRemote.py. Reads loaded PHAT; never saves assets or changes Play."""
import unreal,json,pathlib,datetime
r=pathlib.Path(unreal.Paths.project_dir());ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Robotics.ExportRig reach-lab.json')
rig=json.loads((r/'Saved/Robotics/reach-lab.json').read_text(encoding='utf-8-sig'))
assert rig['success'],rig.get('error')
wrists=[]
for side in ['l','r']:
 hand='hand_'+side;forearm='lowerarm_'+side
 for j in rig['joints']:
  a=rig['bodies'][j['child']]['name'];b=rig['bodies'][j['parent']]['name']
  if {a,b}=={hand,forearm}:
   wrists.append(dict(hand=hand,handFirst=a==hand,frame1=j['child_frame']['rotation_xyzw'],frame2=j['parent_frame']['rotation_xyzw'],modes=j['angular_modes_twist_swing2_swing1'],limits=j['angular_limits_deg_twist_swing2_swing1']))
assert len(wrists)==2,wrists
result=dict(asset=rig['physics_asset'],exported=datetime.datetime.now(datetime.timezone.utc).isoformat(),wrists=wrists)
(r/'Labs/ReachLab/phat.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

