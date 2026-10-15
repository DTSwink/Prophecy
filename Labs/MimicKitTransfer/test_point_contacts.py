"""Check rig-only contact filtering and unchanged non-opted-in dynamics."""
import os,json
from pathlib import Path
os.environ['MIMICKIT_TRANSFER_OUT']=str(Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913')
import native_probe
from native_probe import OUT,Native,np,R,actor,observation,keys,offsets


def clean():
    for k in list(os.environ):
        if k.startswith('TRANSFER_'): del os.environ[k]


def main():
    out=OUT/'point-contact'; raw=np.load(OUT/'coupled_live_dt_batch/raw.npz')
    reference=np.load(OUT/'causal_transfer/reference.npz')
    clean(); os.environ['TRANSFER_RIG_ALLOW_SPECULATIVE']='1'
    copies=[]
    for executable in [OUT/'contact-observation.exe',out/'fixture.exe']:
        native_probe.fixture_path=executable
        n=Native(reference['states'][0]); states=[]
        try:
            for action in reference['actions'][1:]: states.append(n.request('step '+' '.join(map(str,action)))['bodies'])
        finally:n.close()
        copies.append(np.array(states))
    np.testing.assert_array_equal(copies[0],copies[1])
    print('Default dynamics: all body states identical over 31 policy ticks',flush=True)
    clean(); rows=[]
    for phase in range(4):
        n=Native(raw['first_physical'][phase]); current=np.array(n.initial['bodies']); states=[current];dist=[]
        try:
            for tick in range(1,300):
                a=actor(observation(current,raw['obs'][tick,phase,-5:]))
                current=np.array(n.request('step '+' '.join(map(str,a)))['bodies']); states.append(current)
                target=raw['targets'][tick,phase].copy(); target[:,:2]+=current[0,:2]-target[0,:2]
                actual=current[keys,:3]+R.from_quat(current[keys,3:7]).apply(offsets)
                desired=target[keys,:3]+R.from_quat(target[keys,3:7]).apply(offsets)
                dist.append(np.linalg.norm(actual-desired,axis=1))
                if max(dist[-1])>.27:break
        finally:n.close()
        row=dict(phase=phase/4,ticks=len(dist),passed=len(dist)==299,max_distance_m=float(np.max(dist)))
        rows.append(row); print(json.dumps(row),flush=True)
        np.savez_compressed(out/f'closed_{phase}.npz',states=states,dist=dist)
    (out/'verification.json').write_text(json.dumps(dict(default_31_ticks_identical=True,phases=rows),indent=2),encoding='utf-8')


if __name__=='__main__': main()
