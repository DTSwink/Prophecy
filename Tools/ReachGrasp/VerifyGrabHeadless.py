"""Cold-build check before reopening the user's editor; use -ProphecyGrabCheck."""
from pathlib import Path
import runpy
import unreal

assert '-ProphecyGrabCheck' in unreal.SystemLibrary.get_command_line()
root = Path(unreal.Paths.project_dir()).resolve()
runpy.run_path(str(root / 'Tools/ReachGrasp/GrabIndependence.py'), run_name='__main__')
runpy.run_path(str(root / 'Tools/ReachGrasp/TestGrabIndependence.py'), run_name='__main__')
