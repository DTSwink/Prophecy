from pathlib import Path
p=Path(__file__).parent
s=(p/'capture_forward.py').read_text()
s=s.replace('   data=a.read_nn_future_world_pose()', '''   if a.is_player_controlled() and int(a.get_editor_property('tick debug'))>=181:
    lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary'))
    lib.call_method('SetBothArmsReturnToNeutralEnabled',(a,False))
   data=a.read_nn_future_world_pose()''')
(p/'capture_left_no_extra.py').write_text(s)
