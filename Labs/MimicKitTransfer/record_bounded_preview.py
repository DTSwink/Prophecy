"""Record corrected-MJ/native comparison, preserving previous experiment evidence."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
for key in list(os.environ):
    if key.startswith('TRANSFER_'): del os.environ[key]
from native_probe import OUT,Native,actor,observation,keys,offsets,R,np,json,runtime,fixture_path
from build_skin_preview import map_pose,bones
import hashlib

def main(live=False):
    batch="coupled_live_dt_batch" if live else "coupled_integrator_batch"
    suffix="LiveMotor" if live else "Bounded"
    report_stem="live-motor" if live else "bounded"
    raw=np.load(OUT/batch/'raw.npz')
    native=Native(raw['first_physical'][0]);current=np.array(native.initial['bodies'])
    states=[current];distances=[];actions=[]
    try:
        for tick in range(1,121):
            action=actor(observation(current,raw['obs'][tick,0,-5:]))
            current=np.array(native.request('step '+' '.join(map(str,action)))['bodies'])
            assert np.isfinite(current).all()
            states.append(current);actions.append(action)
            target=raw['targets'][tick,0].copy();target[:,:2]+=current[0,:2]-target[0,:2]
            actual=current[keys,:3]+R.from_quat(current[keys,3:7]).apply(offsets)
            desired=target[keys,:3]+R.from_quat(target[keys,3:7]).apply(offsets)
            distances.append(np.linalg.norm(actual-desired,axis=-1))
    finally:native.close()
    states=np.array(states);distances=np.array(distances)
    if live:
        repeat=Native(raw['first_physical'][0]);check=[np.array(repeat.initial['bodies'])]
        try:
            for tick in range(1,5):
                a=actor(observation(check[-1],raw['obs'][tick,0,-5:]))
                check.append(np.array(repeat.request('step '+' '.join(map(str,a)))['bodies']))
        finally:repeat.close()
        original=np.array(check)
    else:original=np.load(OUT/'corrected_native/default_0.npz')['states']
    checked=min(5,len(original)) if live else len(original)
    prefix_error=float(np.max(np.abs(states[:checked]-original[:checked])))
    np.testing.assert_allclose(states[:checked],original[:checked],atol=1e-8,rtol=0)
    native_file=OUT/('jolt_'+report_stem+'_continued.npz')
    np.savez_compressed(native_file,states=states,dist=distances,actions=actions)
    clips=[('Jolt'+suffix,states,native_file,'JOLT | bounded motors'),
           ('Newton'+suffix,raw['states'][1:122,0],OUT/batch/'raw.npz','MJ | corrected bounded motors')]
    for tag,s,path,title in clips:
        assert len(s)==121
        poses=np.array([map_pose(row)[0] for row in s]);tracks=[]
        for i,b in enumerate(bones):
            q=R.from_matrix(poses[:,i,:3,:3]).as_quat()
            for t in range(1,len(q)):
                if q[t]@q[t-1]<0:q[t]*=-1
            tracks.append(dict(name=b['name'],positions=(poses[:,i,:3,3]*100).tolist(),rotations=q.tolist()))
        by_name={t['name']:t for t in tracks}
        by_name['root']['positions']=[[-p[0],-p[1],0] for p in by_name['pelvis']['positions']]
        payload=dict(title=title+' - recorded physics; XY centered only',fps=30,frames=len(s),
                     asset=f'/Game/_mygame/Tests/MimicKitTransfer/AS_{tag}_3913',
                     source=str(path.relative_to(OUT)),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),tracks=tracks)
        (OUT/f'skin_{tag}.json').write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8')
    report=dict(ticks=120,first_failure_tick=int(np.flatnonzero(distances.max(1)>.27)[0])+1,
                max_error_m=float(distances.max()),prefix_max_error=prefix_error,prefix_checked_frames=checked,fixture=str(fixture_path),
                starting_phase=0,source_tick=1,checkpoint='unchanged no-armature-3913',
                note='Continue native after failure without reset or support. Both clips 4s; XY centered for display only.')
    (OUT/(report_stem+'-map-recording.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
 import sys
 main('--live' in sys.argv)
