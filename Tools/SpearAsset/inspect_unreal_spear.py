import os,json,pathlib,unreal
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip()),'Refusing another agent/editor process'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert not ed.get_game_world()
bp=unreal.load_asset('/Game/_mygame/sword/A_Sword');cdo=unreal.get_default_object(bp.generated_class())
fields={}
for name in ('blade length','hilt half length','blade half width','Optimised','debug mode','freeze tick','unfreeze tick','velocity cut dampings','tags','gravity','type cut','cuts'):
 try:fields[name]=str(cdo.get_editor_property(name))
 except Exception as e:fields[name]=str(e)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
text=(root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_text(encoding='utf-16')
(out/'A_Sword_graph_before.txt').write_text('\n\n'.join(b for b in text.split('\n\n') if '/Game/_mygame/sword/A_Sword' in b),encoding='utf-8')
subs=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem);components=[]
for handle in subs.k2_gather_subobject_data_for_blueprint(bp):
 data=unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle)
 obj=unreal.SubobjectDataBlueprintFunctionLibrary.get_object(data)
 row={'path':obj.get_path_name(),'class':obj.get_class().get_name()}
 for key in ('relative_scale3d','relative_location','relative_rotation','static_mesh','override_materials'):
  try:row[key]=str(obj.get_editor_property(key))
  except Exception:pass
 components.append(row)
assets=unreal.EditorAssetLibrary.list_assets('/Game',recursive=True,include_folder=False)
result={'pid':os.getpid(),'map':ed.get_editor_world().get_path_name(),'fields':fields,'components':components,'existing_spear_assets':[a for a in assets if 'spear' in a.lower() or 'imperial' in a.lower()],'dirty':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}
(out/'inspect.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
