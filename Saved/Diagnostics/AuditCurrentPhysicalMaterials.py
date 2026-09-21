import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
def mat(m):
    if not m:return None
    return dict(path=m.get_path_name(),**{p:str(m.get_editor_property(p)) for p in ['friction','static_friction','restitution','friction_combine_mode','override_friction_combine_mode','restitution_combine_mode','override_restitution_combine_mode']})
result={}
for name,w in [('editor',ed.get_editor_world()),('play',ed.get_game_world())]:
    rows=[]
    if w:
        for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
            for c in a.get_components_by_class(unreal.SkeletalMeshComponent):
                if c.get_name()=='PhysicalMesh':
                    rows.append(dict(agent=a.get_name(),mesh_class=c.get_class().get_name(),override=mat(c.get_editor_property('body_instance').get_editor_property('phys_material_override'))))
    result[name]=rows
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/current_physical_materials.json'
p.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
