import unreal,builtins,json
s=builtins._blood_visual
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world();assert w.get_path_name().startswith('/Engine/Maps/Entry.')
assert unreal.EditorLoadingAndSavingUtils.load_map('/Game/testNN')
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
r=[]
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
 if isinstance(a,unreal.ProphecyBloodTexturePaintManager) or 'DecalManager' in a.get_class().get_name():
  item={'actor':a.get_path_name(),'class':a.get_class().get_path_name()}
  if isinstance(a,unreal.ProphecyBloodTexturePaintManager):item['pairs']=[str(p) for p in a.blood_enabled_material_pairs]
  else:
   for p in ('paint manager','paint_manager','floor'):
    try:item[p]=str(a.get_editor_property(p))
    except:pass
  r.append(item)
(s['out']/'fight-ownership.json').write_text(json.dumps(r,indent=2));print('FIGHT_BLOOD_OWNERS',json.dumps(r))
