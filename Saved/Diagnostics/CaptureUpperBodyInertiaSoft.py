from pathlib import Path
import unreal
upper_inertia_config=(0.4,0.0,0.5,1.0)
exec((Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureUpperBodyInertiaEnabled.py').read_text(),globals())
