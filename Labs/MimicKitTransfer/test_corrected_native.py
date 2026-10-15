"""Native closed-loop transfer from corrected-MJ starts; no Unreal interaction."""
import os,json,time
import numpy as np
from scipy.spatial.transform import Rotation as R
import probe
from native_probe import Native,actor,observation,keys,offsets,names

def main(limits=False):
    raw=np.load(probe.OUT/'coupled_integrator_batch/raw.npz');reports=[]
    saved={k:v for k,v in os.environ.items() if k.startswith('TRANSFER_')}
    start=time.perf_counter()
    try:
        modes=[('default',()),('iterations100',('HIGH_ITERATIONS',)),
                              ('iterations100_training_contacts',('HIGH_ITERATIONS','TRAINING_CONTACT')),
                              ('iterations100_speculative',('HIGH_ITERATIONS','RIG_ALLOW_SPECULATIVE'))]
        if limits:modes=[('no_limits',('NO_LIMITS',)),('no_limits_iterations100',('NO_LIMITS','HIGH_ITERATIONS'))]
        for mode,switches in modes:
            for k in list(os.environ):
                if k.startswith('TRANSFER_'):del os.environ[k]
            for k in switches:os.environ['TRANSFER_'+k]='1'
            for phase in range(4):
                n=Native(raw['first_physical'][phase]);current=np.array(n.initial['bodies']);states=[current];dist=[]
                try:
                    for tick in range(1,300):
                        a=actor(observation(current,raw['obs'][tick,phase,-5:]))
                        current=np.array(n.request('step '+' '.join(map(str,a)))['bodies']);states.append(current)
                        target=raw['targets'][tick,phase].copy();target[:,:2]+=current[0,:2]-target[0,:2]
                        actual_c=current[keys,:3]+R.from_quat(current[keys,3:7]).apply(offsets)
                        target_c=target[keys,:3]+R.from_quat(target[keys,3:7]).apply(offsets)
                        dist.append(np.linalg.norm(actual_c-target_c,axis=-1))
                        if np.max(dist[-1])>.27:break
                finally:n.close()
                row=dict(mode=mode,phase=phase/4,ticks=len(dist),peak_distance_m=float(np.max(dist)),
                         worst_body=names[keys[int(np.argmax(dist[-1]))]],
                         survived=len(dist)==299,checks='27cm target distance only')
                reports.append(row);print('NATIVE '+json.dumps(row),flush=True)
                out=probe.OUT/'corrected_native';out.mkdir(exist_ok=True)
                np.savez_compressed(out/f'{mode}_{phase}.npz',states=states,dist=dist)
        (probe.OUT/('corrected-native-no-limits-report.json' if limits else 'corrected-native-report.json')).write_text(json.dumps(dict(seconds=time.perf_counter()-start,cases=reports),indent=2))
    finally:
        for k in list(os.environ):
            if k.startswith('TRANSFER_'):del os.environ[k]
        os.environ.update(saved)

if __name__=='__main__':main()
