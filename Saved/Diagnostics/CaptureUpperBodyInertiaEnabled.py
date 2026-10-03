import unreal
from pathlib import Path
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureCalfRoll.py').read_text()
# CaptureCalfRoll expands CaptureHandChain; inject configuration into that source.
source=source.replace('exec(source,globals())', '''source=source.replace("'CalfRoll-'","'UpperInertiaEnabled-'")
source=source.replace('self.rows=[];self.frame=0;', 'self.configured=set();self.rows=[];self.frame=0;')
source=source.replace('                pose=a.read_nn_future_world_pose()', """                if a.get_name() not in self.configured:
                    lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyUpperBodyInertiaLibrary'))
                    ok=lib.call_method('SetAttackUpperBodyInertia',args=(a,True,*globals().get('upper_inertia_config',(0.25,0.0,0.5,1.0))))
                    assert ok,'Inertia configuration rejected'
                    self.configured.add(a.get_name())
                    print('UPPER_INERTIA_ENABLED',a.get_name())
                pose=a.read_nn_future_world_pose()""")
exec(source,globals())''')
exec(source,globals())
