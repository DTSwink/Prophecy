"""Legacy entry point; reward contract is now covered by test_minimum_peaks.py."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name("test_minimum_peaks.py")),run_name="__main__")
