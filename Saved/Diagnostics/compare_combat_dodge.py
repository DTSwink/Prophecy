from pathlib import Path
import json,sys,shutil,numpy as np
root=Path(__file__).resolve().parents[2];folder=root/'Saved/Diagnostics/CombatDemo'
base=Path('C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/dodge_unreal_reference/attack_nn/reference')
sys.path.insert(0,str(base.parents[3]/'ParryAndDodge'))
from compare_ue5_dodge_reference import compare
source=root/'Saved/DefenseIntegration/Models/ue_dodge_trace_flat.json'
flat=json.loads(source.read_text());candidate={}
with np.load(base/'trace.npz') as expected:
 for k,v in flat.items():
  a=np.asarray(v,dtype=np.float32)
  candidate[k]=a.reshape(expected[k].shape) if k in expected and a.size==expected[k].size else a
 positions_expected=expected['trajectory/positions'].copy()
np.savez(folder/'native_attack_and_dodge.npz',**candidate)
result=compare(base/'trace.npz',folder/'native_attack_and_dodge.npz')
result['trajectory_max_joint_mm']=float(np.linalg.norm(candidate['trajectory/positions']-positions_expected,axis=-1).max()*1000)
(folder/'native_attack_and_dodge_comparison.json').write_text(json.dumps(result,indent=2))
shutil.copy2(folder/'original_dodge_trace_inputs.json',root/'Saved/DefenseIntegration/Models/dodge_trace_inputs.json')
print(json.dumps(result,indent=2))
