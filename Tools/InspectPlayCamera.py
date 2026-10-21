import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
r={'play':bool(w)}
if w:
    pc=unreal.GameplayStatics.get_player_controller(w,0)
    if pc:
        for key,o in [('controller',pc),('pawn',pc.get_pawn()),('view_target',pc.get_view_target())]:
            r[key]=None if o is None else {'path':o.get_path_name(),'class':o.get_class().get_path_name()}
else:
    w=ed.get_editor_world()
    settings=w.get_world_settings()
    r['game_mode_override']=str(settings.get_editor_property('default_game_mode'))
    r['pawns']=[{'name':a.get_actor_label(),'class':a.get_class().get_path_name()} for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Pawn)]
inp=unreal.get_default_object(unreal.InputSettings)
r['camera_mappings']=[{'axis':str(x.axis_name),'key':str(x.key),'scale':x.scale} for name in ['FlyCam_MoveFB','FlyCam_MoveLR','DefaultPawn_MoveForward','DefaultPawn_MoveRight'] for x in inp.get_axis_mapping_by_name(name)]
print(json.dumps(r))
