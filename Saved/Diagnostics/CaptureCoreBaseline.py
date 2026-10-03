from pathlib import Path
import unreal
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureCoreTempering.py').read_text(encoding='utf-8')
source=source.replace("\"'CoreTempering-'\"", "\"'CoreBaseline-'\"")
source=source.replace("args=(a,True,0.)", "args=(a,False,1.)")
exec(source,globals())
