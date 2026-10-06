import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);w=ed.get_game_world() or ed.get_editor_world()
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LimbMaterials20261006';p.mkdir(exist_ok=True)
rows=[]
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
 for c in a.get_components_by_class(unreal.SkinnedMeshComponent):
  m=c.get_skinned_asset()
  rows.append({'agent':a.get_name(),'component':c.get_name(),'asset':m.get_path_name() if m else None,'slots':[str(x) for x in c.get_material_slot_names()],'materials':[x.get_path_name() if x else None for x in c.get_materials()]})
(p/'meshes.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
