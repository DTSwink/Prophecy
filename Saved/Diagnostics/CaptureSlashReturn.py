import unreal
from pathlib import Path
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureHandChain.py').read_text(encoding='utf-8')
source=source.replace("if str(n) in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')",'')
source=source.replace("'HandChain-'","'SlashReturn-'")
exec(source,globals())
