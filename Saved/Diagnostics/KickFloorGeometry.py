import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world() or ed.get_editor_world()
rows=[]
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
 if a.get_actor_label()=='Floor':
  m=a.get_component_by_class(unreal.StaticMeshComponent)
  print('FLOOR',m.get_local_bounds(),m.get_world_transform())
for obj in unreal.ObjectIterator():
 if not obj or not obj.get_class() or obj.get_class().get_name()!='SkeletalBodySetup' or 'PA_UEFN_Mannequin.' not in obj.get_path_name():continue
 bone=str(obj.get_editor_property('bone_name'))
 if bone not in ('foot_l','foot_r','ball_l','ball_r'):continue
 row={'bone':bone,'boxes':[]}
 for e in obj.get_editor_property('agg_geom').get_editor_property('box_elems'):
  x={}
  for p in ('center','rotation','x','y','z'):
   try:x[p]=str(e.get_editor_property(p))
   except Exception as exc:x[p]=str(exc)
  row['boxes'].append(x)
 rows.append(row)
print(json.dumps(rows))
pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/KickFloorGeometry.json').write_text(json.dumps(rows,indent=2))
