"""Create the editable graph once, then connect it without changing holster placement."""
import unreal, pathlib, json, shutil
r=pathlib.Path(unreal.Paths.project_dir()).resolve()
out=r/'Saved/Diagnostics/HolsterStrap20261013'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
folder='/Game/_mygame/assets/holster/Animated'
bp=unreal.load_asset(folder+'/BP_HolsterWithStrap');assert bp
sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem);lib=unreal.SubobjectDataBlueprintFunctionLibrary
def components():
 result={}
 for h in sub.k2_gather_subobject_data_for_blueprint(bp):
  c=lib.get_object_for_blueprint(lib.get_data(h),bp)
  if isinstance(c,unreal.SceneComponent):result[c.get_path_name()]=c
 return result
def placement():
 result={}
 for name,c in components().items():
  t=c.get_relative_transform();p,q,s=t.translation,t.rotation,t.scale3d
  result[name]={'translation':[p.x,p.y,p.z],'rotation':[q.x,q.y,q.z,q.w],'scale':[s.x,s.y,s.z],'sim':c.get_editor_property('body_instance').get_editor_property('simulate_physics') if isinstance(c,unreal.PrimitiveComponent) else None}
 return result
before=placement()
disk=r/'Content/_mygame/assets/holster/Animated/BP_HolsterWithStrap.uasset'
backup=out/'BP_HolsterWithStrap-before-animbp.uasset'
if not backup.exists():shutil.copy2(disk,backup)
(out/'before-animbp-placement.json').write_text(json.dumps(before,indent=2))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.HolsterAnimBlueprint Create')
report=(out/'anim-blueprint.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in report and 'bodies=5' in report, report
anim=unreal.load_asset(folder+'/ABP_HolsterStrap');assert anim
cls=unreal.load_class(None,folder+'/ABP_HolsterStrap.ABP_HolsterStrap_C');assert cls
assert unreal.EditorAssetLibrary.save_loaded_asset(anim,only_if_is_dirty=True)
count=0
for c in components().values():
 if isinstance(c,unreal.SkeletalMeshComponent) and c.get_name()=='Strap_GEN_VARIABLE':
  c.set_anim_instance_class(cls);count+=1
assert count==1,count
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
assert placement()==before, 'Do not save if user component placement or simulation changed'
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True)
print('EDITABLE_STRAP_CONNECTED',anim.get_path_name(),'placement_preserved',True)
