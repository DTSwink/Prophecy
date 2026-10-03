from pathlib import Path
import unreal
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/VerifyUpperBodyInertia.py').read_text()
source=source.replace("tests=['Prophecy.NN.UpperBodyInertia'","tests=['Prophecy.NN.SpecialRecovery','Prophecy.NN.UpperBodyInertia'")
exec(source,globals())
