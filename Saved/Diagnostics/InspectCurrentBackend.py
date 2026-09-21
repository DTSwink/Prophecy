import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
def prop(obj,key):
    try:return str(obj.get_editor_property(key))
    except:return None
def actors(world):
    rows=[]
    for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor):
        if isinstance(a,unreal.ProphecyAgent):
            rows.append({'actor':a.get_path_name(),'label':a.get_actor_label(),'mode':str(a.get_simulation_mode()),'jolt_enabled':a.is_jolt_physical_animation_enabled(),'jolt_selected':a.is_jolt_physical_animation_selected(),'manual':prop(a,'manual_nn_pose_application')})
        elif isinstance(a,unreal.ProphecyJoltFightSetup):
            rows.append({'setup':a.get_path_name(),'enabled':prop(a,'enable_jolt'),'started':prop(a,'started_agent_count'),'error':prop(a,'last_error')})
    return rows
print('BACKEND',json.dumps({'editor':actors(ed.get_editor_world()),'game':actors(ed.get_game_world()) if ed.get_game_world() else None,'default_cvar':unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Jolt.DefaultPhysics')}))
print('DIRTY',[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
