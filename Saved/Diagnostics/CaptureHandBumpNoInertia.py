import unreal
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureHandChain.py').read_text()
source=source.replace(" if str(n) in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')",'')
source=source.replace("'HandChain-'","'HandBumpNoInertia-'")
source=source.replace('                pose=a.read_nn_future_world_pose()', "                unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyUpperBodyInertiaLibrary')).call_method('SetAttackUpperBodyInertia',args=(a,False,0.,0.,0.,1.))\n                pose=a.read_nn_future_world_pose()")
exec(source,globals())
