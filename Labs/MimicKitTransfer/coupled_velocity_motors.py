"""Compatibility import for isolated diagnostics; implementation lives with the UEFN asset."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'MimicKitUEFN'))
from velocity_motors import CoupledVelocityMotors
