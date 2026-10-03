import pathlib,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/'Knee202').mkdir(exist_ok=True)
(p/'Knee202/kick_current_graph.txt').write_bytes((p/'SwordThigh/BlueprintGraph.txt').read_bytes())
src=(p/'CaptureKnee202.py').read_text()
src=src.replace("tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'","tag='kick_current_oct2'")
src=src.replace('clock>=175','clock>=130')
src=src.replace('a.set_foot_pinning_debug_enabled(True)',"unreal.SystemLibrary.execute_console_command(w,'Prophecy.Tempering.PoleTrace 180')")
src=src.replace("if trace.exists():\n  with", "if owned:unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.Tempering.PoleTrace 0')\n if trace.exists():\n  with")
exec(compile(src,'CaptureKickPoleCurrent','exec'))
