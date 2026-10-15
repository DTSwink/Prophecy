"""Continue the existing native test past its failure threshold for visible diagnosis."""
import os
from pathlib import Path
os.environ['MIMICKIT_TRANSFER_OUT']=str(Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913')
from native_probe import OUT,Native,actor,observation,keys,offsets,R,np,json,runtime,fixture_path
from build_skin_preview import map_pose,bones
import hashlib

def main():
    contact=runtime.get('tag')=='jolt_contact_only'
    stem='jolt_contact_continued' if contact else 'jolt_failure_continued'
    data=np.load(OUT/'newton_phase_0.000.npz');current=data['physical'][1].copy()
    native=Native(current);current=np.array(native.initial['bodies']);states=[current];distances=[];actions=[]
    try:
        for tick in range(1,121):
            action=actor(observation(current,data['obs'][tick,0,-5:]))
            current=np.array(native.request('step '+' '.join(map(str,action)))['bodies'])
            assert np.isfinite(current).all()
            states.append(current);actions.append(action)
            target=data['targets'][tick].copy();target[:,:2]+=current[0,:2]-target[0,:2]
            actual=current[keys,:3]+R.from_quat(current[keys,3:7]).apply(offsets)
            desired=target[keys,:3]+R.from_quat(target[keys,3:7]).apply(offsets)
            distances.append(np.linalg.norm(actual-desired,axis=-1))
    finally:native.close()
    states=np.array(states);distances=np.array(distances)
    original=np.load(OUT/(runtime.get('tag','jolt')+'_phase_0.000.npz'))['states']
    np.testing.assert_allclose(states[:len(original)],original,atol=1e-8,rtol=0)
    np.savez_compressed(OUT/(stem+'.npz'),states=states,dist=distances,actions=actions)
    report=dict(ticks=120,first_failure_tick=int(np.nonzero(distances.max(1)>.27)[0][0])+1,
                max_error_m=float(distances.max()),final_pelvis_height_m=float(states[-1,0,2]),
                minimum_pelvis_height_m=float(states[:,0,2].min()),original_prefix_matches=True,
                fixture=str(fixture_path),rig_predictive_contact_disabled=contact,
                note='Policy remains closed-loop after threshold; no reset, no support or posture correction. Playback is recorded, at 0.25x.')
    clips=[('JoltContact' if contact else 'JoltFailure',states,'JOLT - rig predictive contacts off' if contact else 'JOLT - recorded failure')]
    if not contact:clips.append(('NewtonCompare',data['states'][1:122],'TRAINING SIMULATOR - same checkpoint'))
    for tag,s,title in clips:
        poses=np.array([map_pose(row)[0] for row in s]);tracks=[]
        for i,b in enumerate(bones):
            q=R.from_matrix(poses[:,i,:3,:3]).as_quat()
            for t in range(1,len(q)):
                if q[t]@q[t-1]<0:q[t]*=-1
            tracks.append(dict(name=b['name'],positions=(poses[:,i,:3,3]*100).tolist(),rotations=q.tolist()))
        track_by_name={t['name']:t for t in tracks}
        track_by_name['root']['positions']=[[-p[0],-p[1],0] for p in track_by_name['pelvis']['positions']]
        payload=dict(title=title+' - XY-centered display, original height and rotations',fps=30,frames=len(s),asset=f'/Game/_mygame/Tests/MimicKitTransfer/AS_{tag}_3913',
                     source=stem+'.npz' if tag.startswith('Jolt') else 'newton_phase_0.000.npz',tracks=tracks)
        payload['source_sha256']=hashlib.sha256((OUT/payload['source']).read_bytes()).hexdigest()
        (OUT/f'skin_{tag}.json').write_text(json.dumps(payload,separators=(',',':')))
    (OUT/('contact-map-recording.json' if contact else 'failure-map-recording.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
