import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);w=ed.get_editor_world()
settings=unreal.get_default_object(unreal.PhysicsSettings)
data={'pie':bool(ed.get_game_world()),'max_substep':settings.get_editor_property('max_substep_delta_time'),'substepping':settings.get_editor_property('substepping'),'actors':[]}
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
    if isinstance(a,unreal.ProphecyAgent) or a.get_actor_label()=='Cube':
        p=a.get_actor_location();d={'name':a.get_name(),'pos':[p.x,p.y,p.z]}
        if isinstance(a,unreal.ProphecyAgent):d['debug1']=a.get_editor_property('bool debug 1')
        data['actors'].append(d)
pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/CombatRestoration.json').write_text(json.dumps(data,indent=2));print(json.dumps(data))
