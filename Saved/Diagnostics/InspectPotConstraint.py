import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
rows=[]
for world in [ed.get_editor_world(),ed.get_game_world()]:
 if not world: continue
 for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor):
  if 'pot' not in (a.get_name()+' '+a.get_class().get_name()).lower(): continue
  row=dict(world=world.get_name(),actor=a.get_path_name(),location=str(a.get_actor_location()),components=[])
  for c in a.get_components_by_class(unreal.ActorComponent):
   d=dict(name=c.get_name(),cls=c.get_class().get_name())
   if isinstance(c,unreal.SceneComponent): d.update(location=str(c.get_world_location()),scale=str(c.get_world_scale()))
   if isinstance(c,unreal.PrimitiveComponent):
    d.update(sim=c.is_simulating_physics(),collision=str(c.get_collision_enabled()),profile=str(c.get_collision_profile_name()))
   if isinstance(c,unreal.SkeletalMeshComponent):
    mesh=c.get_editor_property('skeletal_mesh_asset')
    d['asset']=str(mesh)
    d['physics_asset']=str(mesh.get_editor_property('physics_asset'))
   if isinstance(c,unreal.PhysicsConstraintComponent):
    d['endpoints']=str(c.get_constrained_components())
    for p in ['component_name1','component_name2']:
     try:d[p+'_name']=str(c.get_editor_property(p).get_editor_property('component_name'))
     except Exception as e:d[p+'_name']=str(e)
    for p in ['component_name1','component_name2','constraint_actor1','constraint_actor2','constraint_instance']:
     try:d[p]=str(c.get_editor_property(p))
     except Exception as e:d[p]=str(e)
    d['methods']=[m for m in dir(c) if 'constraint' in m or 'constrained' in m]
   row['components'].append(d)
  rows.append(row)
 if world==ed.get_game_world(): unreal.SystemLibrary.execute_console_command(world,'Prophecy.Jolt.ConstraintAudit A_Pot')
print(json.dumps(rows,indent=2))
pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/PotConstraintInspect.json').write_text(json.dumps(rows,indent=2))
