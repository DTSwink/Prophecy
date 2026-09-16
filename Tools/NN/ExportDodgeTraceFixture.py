"""Export INPUTS ONLY for the full native Dodge trace test."""
from pathlib import Path
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/dodge_unreal_reference/reference')
DEST = ROOT/'Saved/DefenseIntegration/Models'
with np.load(SOURCE/'trace.npz') as trace:
    inputs = {key: trace[key].astype(np.float32).reshape(-1).tolist() for key in trace.files if key.startswith('episode/')}
inputs['limits'] = json.loads((SOURCE/'networks.json').read_text())['limits'][0]
(DEST/'dodge_trace_inputs.json').write_text(json.dumps(inputs)+'\n')
print('Exported episode inputs and initial bank capacities; no predicted reference outputs.')
