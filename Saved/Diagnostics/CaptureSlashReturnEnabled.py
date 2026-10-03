import unreal
from pathlib import Path
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Do not change a user-owned Play session'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary'))
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureHandChain.py').read_text(encoding='utf-8')
source=source.replace("if str(n) in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')",'')
source=source.replace("'HandChain-'","'SlashReturnEnabled-'")
source=source.replace('self.rows=[];self.frame=0;','self.configured=set();self.rows=[];self.frame=0;')
source=source.replace('                pose=a.read_nn_future_world_pose()',
'''                if a.get_name() not in self.configured:
                    assert lib.call_method('SetSlashRightArmReturnToNeutral',args=(a,True,.3,.5,100.))
                    self.configured.add(a.get_name())
                pose=a.read_nn_future_world_pose()''')
exec(source,globals())
