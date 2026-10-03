import unreal
from pathlib import Path
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Leave user Play untouched'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary'))
configured=set()
script=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureSlashSword.py').read_text()
script=script.replace("'SlashSword-'","'SlashSwordEnabled-'")
script=script.replace('exec(source,globals())','''source=source.replace('                pose=a.read_nn_future_world_pose()',
"""                if a.get_name() not in configured:
                    assert lib.call_method('SetSlashRightArmReturnToNeutral',args=(a,True,.3,.5,100.))
                    configured.add(a.get_name())
                pose=a.read_nn_future_world_pose()""")
exec(source,globals())''')
exec(script,globals())
