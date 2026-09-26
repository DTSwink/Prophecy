"""Compare the native wrist math automation capture to the training implementation."""
from pathlib import Path
import sys, json
import numpy as np
import torch
sys.path.insert(0, r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2')
from slash2_wrist_neutral import WristNeutral
p=Path(__file__).resolve().parents[2]/'Saved/Diagnostics'
a=np.loadtxt(p/'AttackWristMath.csv',delimiter=',',skiprows=1,dtype=np.float32)
r=torch.from_numpy(a[:,:9].reshape(-1,3,3).copy())
d=torch.from_numpy(a[:,9:12].copy())
with torch.inference_mode(): expected=WristNeutral(55)(r,torch.zeros_like(d),d,torch.ones(len(d))).numpy()
error=float(np.abs(expected-a[:,12:].reshape(-1,3,3)).max())
assert error<3e-6,error
result=dict(samples=len(d),maximum_basis_error=error,oracle='slash2_wrist_neutral.WristNeutral(55)',passed=True)
(p/'AttackWristMath-oracle.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
