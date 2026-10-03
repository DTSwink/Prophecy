"""Restore tensor dimensions on the native dump, then run the original comparator.

The reference supplies shapes only; every candidate value comes from Unreal.
Missing keys stay missing and surplus/misshaped arrays are not repaired.
"""
from pathlib import Path
import json
import sys
import numpy as np

base=Path(__file__).resolve().parent
sys.path.insert(0,r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/ParryAndDodge')
from compare_ue5_dodge_reference import compare
reference=Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/dodge_unreal_reference/reference/trace.npz')
flat=json.loads((base/'Models/ue_dodge_trace_flat.json').read_text())
candidate={}
with np.load(reference) as expected:
    for key,values in flat.items():
        value=np.asarray(values,dtype=np.float32)
        candidate[key]=value.reshape(expected[key].shape) if key in expected and value.size==expected[key].size else value
np.savez(base/'Models/ue_dodge_candidate.npz',**candidate)
result=compare(reference,base/'Models/ue_dodge_candidate.npz')
(base/'Models/unreal_dodge_full_comparison.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['passed'] else 1)
