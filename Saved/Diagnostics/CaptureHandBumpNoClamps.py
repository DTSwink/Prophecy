import unreal
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureHandChain.py').read_text()
source=source.replace(" if str(n) in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')",'')
source=source.replace("'HandChain-'","'HandBumpNoClamps-'")
source=source.replace('                pose=a.read_nn_future_world_pose()', "                a.set_locomotion_forearm_clamp(False,0.)\n                a.set_locomotion_hand_clamp(False,0.)\n                pose=a.read_nn_future_world_pose()")
exec(source,globals())
