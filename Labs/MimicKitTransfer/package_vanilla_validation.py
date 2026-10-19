"""Minimal reproducible native GPU diagnostic packet; no trainer or credentials."""
import json,tarfile,shutil
from pathlib import Path
import calibrate_vanilla as c
import numpy as np,torch,mujoco


def main():
    ref,native=c.load();root=c.OUT/'gpu-packet';root.mkdir(exist_ok=True)
    configs={'native_default':{}}
    configs['native_centered']=json.loads((c.OUT/'finalists-settings.json').read_text())['native_centered']
    configs.update(json.loads((c.OUT/'confirm-settings.json').read_text()))
    meta=dict(candidates=configs,names=c.policy.names,parents=c.policy.parents,
              rest_xyzw=[r.as_quat().tolist() for r in c.policy.local],keys=c.policy.keys,
              offsets=c.policy.offsets.tolist(),ball=[False]+[len(n.findall('joint'))==3 for n in c.policy.nodes[1:]])
    data=dict(initial=ref['initial'].astype(np.float32),commands=ref['obs'][:,:,-5:].astype(np.float32),
              targets=ref['targets'].astype(np.float32),initial_obs=ref['obs'][0],initial_actions=ref['actions'][0])
    for name,settings in configs.items():
        m,_=c.build(settings);q,v=zip(*(c.encode(m,state) for state in ref['initial']))
        data[name+'_q']=np.asarray(q,np.float32);data[name+'_v']=np.asarray(v,np.float32)
        mujoco.mj_saveModel(m,str(root/(name+'.mjb')))
    torch.save({k:v for k,v in c.policy.checkpoint.items() if k.startswith(('_model._actor_layers.','_model._action_dist.','_obs_norm.','_a_norm.'))},root/'actor.pt')
    np.savez_compressed(root/'packet.npz',**data);(root/'packet.json').write_text(json.dumps(meta,indent=2))
    shutil.copy2(Path(__file__).with_name('validate_vanilla_gpu.py'),root/'validate_vanilla_gpu.py')
    with tarfile.open(c.OUT/'gpu-packet.tar.gz','w:gz') as t:
        for path in root.iterdir():t.add(path,arcname=path.name)
    print(json.dumps(dict(packet=str(root),bytes=(c.OUT/'gpu-packet.tar.gz').stat().st_size)))

if __name__=='__main__':main()
