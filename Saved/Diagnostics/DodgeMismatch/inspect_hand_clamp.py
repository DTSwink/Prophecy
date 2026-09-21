import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world() or ed.get_editor_world()
print('PIE',bool(ed.get_game_world()))
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
 m=a.get_pose_reference_mesh();asset=m.get_skeletal_mesh_asset()
 print(a.get_name(),'mode',a.get_simulation_mode(),'demo',a.get_editor_property('CombatDemoUseDodge'),'state',unreal.ProphecyNNDefenseLibrary.get_agent_state(a))
 print('ASSET_API',[n for n in dir(asset) if 'ref_pose' in n or 'reference' in n or 'skeleton' in n])
 break
