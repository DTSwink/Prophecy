from pathlib import Path
import unreal
capture_path=Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureFootEntryInertia.py'
exec(compile(capture_path.read_text(), str(capture_path), 'exec'), {'__name__':'foot_entry_capture'})
