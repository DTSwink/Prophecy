"""Independent frozen MimicKit observations for the native Unreal encoder test."""
from pathlib import Path
import os, sys, json, importlib.util
ROOT=Path(__file__).resolve().parents[2]
os.environ['OMP_NUM_THREADS']='1'
import types
transfer=types.ModuleType('transfer')
transfer.__file__=str(ROOT/'Labs/MimicKitTransfer/getup_transfer.py')
source=Path(transfer.__file__).read_text().split('class Policy:')[0].replace('from omni_policy import OmniPPOModel','')
exec(compile(source,transfer.__file__,'exec'),transfer.__dict__)
import numpy as np
from scipy.spatial.transform import Rotation as R
z=np.load(ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023/native-native-baseline-4.npz')
rows=[]
basis=R.from_euler('z',-90,degrees=True)
rig=json.loads((ROOT/'Content/locomotion/NN/robots/rig.json').read_text())
for tick in [0,1,10,25,44]:
    for lane in [0,3]:
        state=z['states'][tick,lane].copy()
        phase=z['phase'][tick,lane]
        expected=transfer.observation(state,{'sword_drawn':False,'arm_enabled':[1,1]},phase).numpy()[0]
        ue=state.copy();ue[:,:3]=basis.apply(state[:,:3])*100
        ue[:,3:7]=(basis*R.from_quat(state[:,3:7])).as_quat()
        ue[:,7:10]=basis.apply(state[:,7:10])*100;ue[:,10:13]=basis.apply(state[:,10:13])
        rows.append({'states':ue.tolist(),'phase':phase.tolist(),'expected':expected.tolist()})
out=ROOT/'Saved/Diagnostics/RobotLocomotion20261026/observation-vectors.json'
out.write_text(json.dumps(rows))
print('Wrote',len(rows),'independent observation checks',out)
