"""CPU interface to the contained Jolt fixture; root-local policy observations."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import numpy as np
import mujoco
from scipy.spatial.transform import Rotation as R
from provenance import verify_export

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/Robotics'


def initial_states(standing=False,pose_bank='rig-passive.npz'):
    verify_export()
    rig=json.loads((OUT/'rig.json').read_text());meta=json.loads((OUT/'uefn.json').read_text())
    model=mujoco.MjModel.from_xml_path(str(OUT/'uefn.xml'));data=mujoco.MjData(model)
    if standing:
        data.qpos[:]=meta['reference_qpos'];mujoco.mj_kinematics(model,data)
        bottoms=[]
        for name in ('foot_l_shape0','foot_r_shape0'):
            g=model.geom(name).id
            bottoms.append(data.geom_xpos[g,2]-abs(data.geom_xmat[g].reshape(3,3)[2])@model.geom_size[g])
        data.qpos[2]+=.001-min(bottoms)
    else:
        if Path(pose_bank).name!=pose_bank:raise ValueError('Expected a local pose-bank filename')
        bank_path=OUT/pose_bank;proof=json.loads(bank_path.with_suffix('.json').read_text())
        if proof['rig_sha256']!=meta['rig_sha256']:raise ValueError('Pose bank belongs to a different rig')
        digest=hashlib.sha256(bank_path.read_bytes()).hexdigest()
        if proof.get('bank_sha256',digest)!=digest:raise ValueError('Pose bank changed after validation')
        bank=np.load(bank_path);index=np.flatnonzero(abs(bank['qvel']).max(1)<.05)[0]
        data.qpos[:]=bank['qpos'][index]
    mujoco.mj_kinematics(model,data)
    states=[]
    for body in rig['bodies']:
        s=model.site(body['name']+'_bone').id
        states.append(np.r_[data.site_xpos[s],R.from_matrix(data.site_xmat[s].reshape(3,3)).as_quat(),np.zeros(6)])
    return np.asarray(states),rig,meta


class NativeRig:
    def __init__(self,states,label='native-fixture',requested_action_history=False):
        self.requested_action_history=requested_action_history
        self.rig=json.loads((OUT/'rig.json').read_text());self.meta=json.loads((OUT/'uefn.json').read_text())
        proof=json.loads((OUT/'relative-native-no-gyro-tests.json').read_text())
        self.controller_hash=hashlib.sha256(json.dumps(proof['controller'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.names={b['name']:i for i,b in enumerate(self.rig['bodies'])}
        self.joints=[next(j for j in self.rig['joints'] if j['child']==self.names[m['body']]) for m in self.meta['joints']]
        states=np.asarray(states)
        if states.shape!=(len(self.names),13) or not np.isfinite(states).all():raise ValueError('Invalid native initial states')
        if not np.allclose(np.linalg.norm(states[:,3:7],axis=1),1,atol=1e-5):raise ValueError('Invalid native initial rotations')
        path=OUT/(label+'-initial.txt');np.savetxt(path,states,fmt='%.12g')
        process_env=dict(os.environ);process_env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+process_env['PATH']
        self.errors=(OUT/(label+'-native-stderr.log')).open('w',encoding='utf-8')
        self.process=subprocess.Popen([str(OUT/'jolt_rig_fixture.exe'),str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=self.errors,text=True,bufsize=1,env=process_env,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            initial=self.read();self.current=initial['bodies']
            self.ground_impulses=np.asarray(initial['ground_vertical_impulse_ns'])
        except Exception:
            self.close();raise
        self.previous_actions=np.zeros(54,dtype=np.float32)

    def read(self):
        line=self.process.stdout.readline()
        if not line:raise RuntimeError(f'Native fixture ended ({self.process.poll()}); inspect its stderr log')
        result=json.loads(line)
        if 'rig_sha256' in result and result['rig_sha256']!=self.meta['rig_sha256']:
            raise ValueError('Native fixture is stale; regenerate/rebuild for this rig')
        if 'bodies' in result and result.get('controller_sha256')!=self.controller_hash:
            raise ValueError('Native fixture controller is stale; regenerate/rebuild')
        return result

    def send(self,command):
        self.process.stdin.write(command+'\n');self.process.stdin.flush();return self.read()

    def step(self,actions):
        requested=np.asarray(actions,dtype=np.float32)
        if requested.shape!=(54,) or not np.isfinite(requested).all():raise ValueError('Expected 54 finite actions')
        applied=np.clip(requested,-4,4)
        result=self.send('step '+' '.join(format(float(x),'.9g') for x in applied))
        self.current=result['bodies'];self.ground_impulses=np.asarray(result['ground_vertical_impulse_ns'])
        self.external_vertical_impulse=float(result['external_vertical_impulse_ns'])
        self.ground_normal_tilt=float(result['ground_normal_tilt_sin'])
        self.previous_actions=(requested if self.requested_action_history else applied).copy()
        return np.asarray(self.current)

    def coordinates(self):
        state=np.asarray(self.current);pelvis=self.names['pelvis'];root=R.from_quat(state[pelvis,3:7])
        q=[*state[pelvis,:3],*root.as_quat()[[3,0,1,2]]]
        velocities=[*state[pelvis,7:10],*root.inv().apply(state[pelvis,10:13])]
        for j in self.joints:
            parent,child=j['parent'],j['child']
            rp=R.from_quat(state[parent,3:7])*R.from_quat(j['parent_frame']['rotation_xyzw'])
            rc=R.from_quat(state[child,3:7])*R.from_quat(j['child_frame']['rotation_xyzw'])
            q.extend((rp.inv()*rc).as_quat()[[3,0,1,2]])
            velocities.extend(rc.inv().apply(state[child,10:13]-state[parent,10:13]))
        return np.asarray(q),np.asarray(velocities)

    def observation(self):
        q,v=self.coordinates();root=R.from_quat(q[[4,5,6,3]])
        joints=q[7:].reshape(-1,4);joints*=np.where(joints[:,:1]<0,-1,1)
        return np.r_[root.inv().apply([0,0,-1]),v[3:6]*.25,root.inv().apply(v[:3])*.5,q[2],
                     joints.ravel(),v[6:]*.05,self.previous_actions].astype(np.float32)

    def connector_gaps(self):
        state=np.asarray(self.current);gaps=[]
        for j in self.joints:
            points=[]
            for body,frame in ((j['parent'],j['parent_frame']),(j['child'],j['child_frame'])):
                points.append(state[body,:3]+R.from_quat(state[body,3:7]).apply(np.array(frame['position_cm'])*.01))
            gaps.append(np.linalg.norm(points[0]-points[1]))
        return np.asarray(gaps)

    def close(self):
        if self.process.poll() is None:
            try:self.process.stdin.write('quit\n');self.process.stdin.flush()
            except BrokenPipeError:pass
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=5)
        self.process.stdin.close();self.process.stdout.close();self.errors.close()

    def __enter__(self):return self
    def __exit__(self,*_):self.close()
