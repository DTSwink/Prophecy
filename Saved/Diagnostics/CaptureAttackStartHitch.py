import unreal
from pathlib import Path
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureCalfRoll.py').read_text()
base=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureHandChain.py').read_text()
base=base.replace("'HandChain-'","'AttackStartHitch-'").replace('self.frame>=360','self.frame>=600')
base=base.replace(" if str(n) in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')",'')
base=base.replace("'frame':self.frame,","'frame':self.frame,'wall':time.monotonic(),'delta':dt,")
exec(base,globals())
