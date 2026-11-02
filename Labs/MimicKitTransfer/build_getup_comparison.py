"""Publish actual frozen-policy recordings; no training or simulation playback tricks."""
from getup_transfer import *
import shutil

dest=OUT/'comparison';dest.mkdir(exist_ok=True)
bodies=[]
for node in nodes:
    shapes=[]
    for geom in node.findall('geom'):
        shapes.append(dict(type=geom.get('type'),size=np.fromstring(geom.get('size'),sep=' ').tolist(),
            pos=np.fromstring(geom.get('pos','0 0 0'),sep=' ').tolist(),
            quat=np.roll(np.fromstring(geom.get('quat','1 0 0 0'),sep=' '),-1).tolist()))
    bodies.append(dict(name=node.get('name'),shapes=shapes))
before=json.loads((OUT/'jolt-native-original-all.json').read_text())
after=json.loads((OUT/'jolt-native-unreal-native-profile32.json').read_text())
clips=[];errors=[]
for a,b in zip(before,after):
    index=a['row'];assert b['row']==index
    meta,native=replay('native',index)
    old=np.load(OUT/f'native-row{index}-jolt-original-all.npz')['states']
    new=np.load(OUT/f'native-row{index}-jolt-unreal-native-profile32.npz')['states']
    local=np.load(OUT/f'native-row{index}-jolt-sphere32-all.npz')['states']
    errors.append(float(np.max(abs(new-local))));np.testing.assert_array_equal(new,local)
    clips.append(dict(row=index,motion=Path(meta['recovery_motion_file']).stem,
        blend=meta['whole_pose_blend'],plus=meta['perturbed_plus_row'],
        runs=[dict(name='MuJoCo training physics',success=True,states=np.round(native[:,:,:7],6).tolist()),
              dict(name='Previous Jolt limits',success=a['terminal']==2,states=np.round(old[:,:,:7],6).tolist()),
              dict(name='Adjusted Jolt · tested in Unreal',success=b['terminal']==2,states=np.round(new[:,:,:7],6).tolist())]))
(dest/'data.json').write_text(json.dumps(dict(bodies=bodies,clips=clips),separators=(',',':')))
shutil.copyfile(ROOT/'Labs/MimicKitTransfer/getup_comparison.html',dest/'index.html')
report=dict(checkpoint='20261022_131128_uefn_getup_pelvismax7_1024 / 161960_final',
    unchanged_checkpoint_sha256='0dc58150f87f1cb25816235f9e565638e9972d262b9203c5da0d14c0ea736a2b',
    recorded_perturbed_starts=len(after),original_jolt_successes=sum(a['terminal']==2 for a in before),
    adjusted_jolt_unreal_successes=sum(a['terminal']==2 for a in after),
    unreal_vs_standalone_max_full_state_error=max(errors),
    selected_tuning_rows=[3,8,9,16],additional_rows=14,training_performed=False,
    normal_checks=json.loads((OUT/'normal-unreal-native-profile32.json').read_text())
        if (OUT/'normal-unreal-native-profile32.json').exists() else None,
    scope='Opt-in isolated 15-body Unreal Jolt world. Flat floor, frozen checkpoint, deterministic policy; gameplay defaults and RunLR untouched.')
(OUT/'jolt-native-profile/verified.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
