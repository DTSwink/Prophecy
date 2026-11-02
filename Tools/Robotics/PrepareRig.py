"""Generate the single shared robot rig from the accepted Get Up handoff."""
from pathlib import Path
import json, sys, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Saved/MimicKitUEFN/dependencies'))
import numpy as np
from scipy.spatial.transform import Rotation as R
import yaml
REC=ROOT/'Exports/MimicKitEquipment/Recovery_Pelvismax161960_Unreal_20261026'
LOC=ROOT/'Saved/MimicKitLocomotion/unreal-handoff-20261026'
meta=json.loads((REC/'rig/limits.json').read_text())
physical=json.loads((REC/'rig/physics.json').read_text())
nodes=list(ET.parse(REC/'rig/humanoid_uefn.xml').getroot().find('worldbody').iter('body'))
names=[n.get('name') for n in nodes]
caps=[yaml.safe_load((p/'engine_config.yaml').read_text())['uefn_motor_torque_caps_nm'] for p in (REC/'policy',LOC)]
def vec(x):return [float(v) for v in x]
def vals(n,k,d):return np.fromstring(n.get(k,d),sep=' ')
def transform(p,q):return {'p':vec(p),'q':vec(q)}
def xmltransform(n):return transform(vals(n,'pos','0 0 0'),np.roll(vals(n,'quat','1 0 0 0'),-1))
data={'schema':1,'source_sha256':meta['source_sha256'],'limit_profile':'spherical32',
      'limit_hz':32,'velocity_iterations':40,'position_iterations':8,'bodies':[],'joints':[],
      'disabled_pairs':[[names.index(a),names.index(b)] for a,b in meta['collision_exclusions']]}
action=0
for n in nodes:
    name=n.get('name');g=meta['groups'][name];b=physical['bodies'][name]
    f=meta['body_frames'][name];s=meta['source_body_frames'][g['anchor']]
    sq=R.from_quat(s['quaternion']);fq=R.from_quat(f['quaternion'])
    offset=transform(sq.inv().apply(np.array(f['position'])-s['position']),(sq.inv()*fq).as_quat())
    inertial=n.find('inertial')
    body={'name':name,'bone':g['anchor'],'aliases':g['colliders_from'],'body_from_bone':offset,
          'mass':float(inertial.get('mass')),'mass_frame':xmltransform(inertial),
          'inertia':vec(vals(inertial,'diaginertia','0 0 0')),
          'drag':[b['drag_mass'],b['drag_first'],b['drag_second']], 'shapes':[]}
    for geom in n.findall('geom'):
        body['shapes'].append({'kind':geom.get('type'),'frame':xmltransform(geom),'size':vec(vals(geom,'size','0'))})
    data['bodies'].append(body)
    if name==names[0]:continue
    j=next(x for x in meta['joints'] if x['body']==name);p=meta['body_frames'][j['parent']];pq=R.from_quat(p['quaternion']);sf=j['source_parent_frame']
    ball=j['kind']=='ball';motor=n.find('joint');default=max(abs(vals(motor,'actuatorfrcrange','0 0')))
    data['joints'].append({'name':j['source_joint'],'child':names.index(name),'parent':names.index(j['parent']),
        'parent_frame':transform(pq.inv().apply(np.array(sf['position'])-p['position']),(pq.inv()*R.from_quat(sf['quaternion'])).as_quat()),
        'bounds':j['limits_rad'] if ball else [0,0,j['limits_rad'][2]],'ball':ball,'action':action,
        'rest':vec(vals(n,'quat','1 0 0 0')),
        'gain':float(motor.get('damping')),
        'caps':[[c.get(f'{name}:{axis}' if ball else name,default) for axis in range(3)] for c in caps]})
    action+=3 if ball else 1
assert action==34 and len(data['bodies'])==15 and len(data['joints'])==14
out=ROOT/'Content/locomotion/NN/robots/rig.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(data,indent=2)+'\n')
print(out)
