import unreal
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureCalfRoll.py').read_text()
# The log is gated off again by the capture's completion, including exceptions.
base=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureHandChain.py').read_text()
base=base.replace(" if str(n) in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')",'')
base=base.replace("'HandChain-'","'SlashReturnStages-'")
base=base.replace('        unreal.unregister_slate_post_tick_callback(self.cb)',"        unreal.SystemLibrary.execute_console_command(self.ed.get_editor_world(),'Prophecy.SlashReturn.Audit 0')\n        unreal.unregister_slate_post_tick_callback(self.cb)")
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.Audit 1')
exec(base,globals())
