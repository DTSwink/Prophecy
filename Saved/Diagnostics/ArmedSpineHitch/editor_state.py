import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
print('ARMED_HITCH_STATE',bool(w))
if w:
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  if a.is_player_controlled():print(a.get_path_name(),a.get_editor_property('tick debug'),str(a.get_nn_attack_state()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
(p/'ArmedSpineHitch/graph.txt').write_bytes((p/'SwordThigh/BlueprintGraph.txt').read_bytes())
