"""Generate a hash-bound native fixture from the same PHAT export as training."""
import json
import hashlib
from pathlib import Path
import numpy as np
from joint_pd import motor_gains_for
from provenance import verify_export

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/Robotics'


def f(x):
    value=format(float(x),'.12g')
    if '.' not in value and 'e' not in value:value+='.0'
    return value+'f'


def v(values,kind='Vec3'):return kind+'('+','.join(f(x) for x in values)+')'


def main():
    verify_export()
    rig=json.loads((OUT/'rig.json').read_text());meta=json.loads((OUT/'uefn.json').read_text())
    supplemental=json.loads((OUT/'rig-provenance.json').read_text())
    assert supplemental['supplements_rig_sha256']==meta['rig_sha256']
    native={b['name']:b for b in supplemental['bodies']}
    proof=json.loads((OUT/'relative-native-no-gyro-tests.json').read_text())
    assert proof['passed'] and proof['rig_sha256']==meta['rig_sha256']
    assert proof['controller']['joint_gains_kp_kd_max_nm']==[list(motor_gains_for(j['body'])) for j in meta['joints']]
    expected_actions=[j['body']+':'+axis for j in meta['joints'] for mode,axis in zip(j['modes'],('twist','swing_y','swing_z')) if mode!=2]
    assert proof['controller']['action_names']==expected_actions
    controller_hash=hashlib.sha256(json.dumps(proof['controller'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    lines=['// Generated; regenerate after original PHAT export changes.',
           'const char* kRigHash='+json.dumps(meta['rig_sha256'])+';',
           'const char* kControllerHash='+json.dumps(controller_hash)+';',
           'const BodySpec kBodies[] = {']
    for b in rig['bodies']:
        assert len(b['shapes'])==1,'Extend fixture explicitly for compound geometry'
        shape=b['shapes'][0];assert shape['simulated']
        assert shape['kind'] in ('capsule','box','sphere')
        n=native[b['name']];assert n['gravity_enabled'] and not n['ccd'] and not n['macd']
        size={'capsule':[shape['radius_cm']*.01,shape['cylinder_length_cm']*.005,0],
              'box':np.array(shape['half_extent_cm'])*.01,'sphere':[shape['radius_cm']*.01,0,0]}[shape['kind']]
        fields=[json.dumps(b['name']),str(('capsule','box','sphere').index(shape['kind'])),v(size),
            v(np.array(shape['local']['position_cm'])*.01),v(shape['local']['rotation_xyzw'],'Quat'),
            v(np.array(b['mass_frame']['position_cm'])*.01),v(b['jolt_inertia_rotation_xyzw'],'Quat'),
            v(np.array(b['jolt_inertia_kg_cm2'])*1e-4),f(b['jolt_mass_kg']),
            f(b['linear_damping']),f(b['angular_damping']),f(n['max_angular_velocity_rad_s']),f(n['max_linear_velocity_cm_s']*.01)]
        lines.append('{'+','.join(fields)+'},')
    lines+=['};','const JointSpec kJoints[] = {'];action=0
    for m in meta['joints']:
        j=next(j for j in rig['joints'] if rig['bodies'][j['child']]['name']==m['body'])
        assert j['linear_modes']==[2,2,2]
        ids=[]
        for mode in m['modes']:
            assert mode in (1,2)
            ids.append(action if mode==1 else -1)
            action+=int(mode==1)
        frames=[]
        for frame in (j['parent_frame'],j['child_frame']):
            frames +=[v(np.array(frame['position_cm'])*.01),v(frame['rotation_xyzw'],'Quat')]
        fields=[str(j['parent']),str(j['child']),*frames,
            '{'+','.join(map(str,m['modes']))+'}',v(m['limits_rad']),
            '{'+','.join(map(str,ids))+'}',v(motor_gains_for(m['body']))]
        lines.append('{'+','.join(fields)+'},')
    lines+=['};','const int kDisabledPairs[][2] = {']
    lines+=['{'+','.join(map(str,p))+'},' for p in rig['disabled_pairs']]
    lines+=['};',f'const int kActionCount={action};']
    (OUT/'jolt-rig-generated.h').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Generated {len(rig["bodies"])} exact bodies, {len(meta["joints"])} joints, {action} policy inputs; {meta["rig_sha256"]}')


if __name__=='__main__':main()
