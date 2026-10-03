import pathlib,unreal
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
wrapper=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='hand180_audit'")
extra="src=src.replace(\"   clock=int(a.get_editor_property('tick debug'))\",\"   clock=int(a.get_editor_property('tick debug'))\\n   if clock==185:unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashReturn.Audit 1')\")\nsrc=src.replace(\" if trace.exists():\",\" unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.SlashReturn.Audit 0')\\n if trace.exists():\")\n"
wrapper=wrapper.replace("exec(compile(src,'CaptureHand180','exec'))",extra+"exec(compile(src,'CaptureHand180','exec'))")
exec(compile(wrapper,'Hand180Audit','exec'))
