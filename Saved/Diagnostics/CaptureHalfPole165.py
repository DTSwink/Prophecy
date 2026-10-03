import pathlib
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
src=(p/'CaptureKnee202.py').read_text()
src=src.replace("tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'","tag='half165_trace'")
src=src.replace("clock>=175","clock>=145").replace("s['frame']>=280","s['frame']>=235")
src=src.replace("a.set_foot_pinning_debug_enabled(True)","a.set_foot_pinning_debug_enabled(True)\n    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Tempering.PoleTrace 100')")
src=src.replace("if trace.exists():\n  with", "unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.Tempering.PoleTrace 0')\n if trace.exists():\n  with")
exec(compile(src,'CaptureHalfPole165','exec'))
