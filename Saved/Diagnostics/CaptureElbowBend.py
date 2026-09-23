import unreal
from pathlib import Path
base=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureHandChain.py').read_text()
base=base.replace(" if str(n) in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')",'')
base=base.replace("'HandChain-'","'ElbowBend-'").replace('self.frame>=360','self.frame>=600')
exec(base,globals())
