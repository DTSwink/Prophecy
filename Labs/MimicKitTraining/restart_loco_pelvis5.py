"""Preserved latest-state restart: pelvis linear MSE x5, all locomotion rows."""
import ast
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
import torch
import yaml
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
from perturbed_motion import tracking_blend

KEY = 'all_rows_pelvis_velocity_mse_multiplier'

def patch(source):
    changes = [
        ('        terms[:, :4] *= mse_mix[:, None]\n',
         "        pelvis_scale = float(self._perturb_cfg.get('all_rows_pelvis_velocity_mse_multiplier', 1.))\n"
         "        if pelvis_scale != 1.:\n"
         "            # Keep the existing body/component mean and handoff weighting.\n"
         "            pelvis_error = (vel[:, 0] - target_vel[:, 0]).square().mean(-1)\n"
         "            terms[:, 1] += (pelvis_scale - 1.) * self._loss_weights[1] * pelvis_error / vel.shape[1]\n"
         '        terms[:, :4] *= mse_mix[:, None]\n'),
        ('        self._tracking_mix = torch.ones(n, device=self._device)\n',
         '        self._tracking_mix = torch.ones(n, device=self._device)\n'
         "        pelvis_scale = float(cfg.get('all_rows_pelvis_velocity_mse_multiplier', 1.))\n"
         "        if not math.isfinite(pelvis_scale) or pelvis_scale <= 0:\n"
         "            raise ValueError('Pelvis velocity MSE multiplier must be finite and positive')\n"),
        ("        result['perturbed_curriculum'] = dict(self._perturb_cfg)\n",
         "        result['perturbed_curriculum'] = dict(self._perturb_cfg)\n"
         "        result['all_rows_pelvis_velocity_mse_multiplier'] = float(self._perturb_cfg.get('all_rows_pelvis_velocity_mse_multiplier', 1.))\n")]
    for old,new in changes:
        assert source.count(old)==1, old
        source=source.replace(old,new)
    compile(source,'perturbed_omni.py','exec')
    return source

def test(source):
    class Base:
        def _tracking_losses(self,pos,rot,vel,ang,target_vel,target_ang):
            terms=torch.full((4,5),2.)
            terms[:,1]=(vel-target_vel).square().mean((1,2))*3.2992958902731857
            return terms
    method=next(n for c in ast.parse(source).body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='_tracking_losses')
    cls=ast.ClassDef(name='Trial',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=[method],decorator_list=[])
    ns=dict(torch=torch,Base=Base,tracking_blend=tracking_blend,EnvMode=SimpleNamespace(TRAIN=1),q=SimpleNamespace(quat_to_matrix=lambda x:x))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),'actual-tracking','exec'),ns)
    e=ns['Trial']()
    vars(e).update(_perturb_ready=True,_refresh_reward_rotations=lambda:None,
        _perturbed_ids=torch.tensor([0,1]),_prior_ids=torch.tensor([0,1]),
        _prior=SimpleNamespace(append=lambda *a:None,cost=lambda:torch.ones(2)*5),
        _prior_raw=torch.zeros(4),_mse_only=False,_perturbed_getup=torch.zeros(4,dtype=torch.bool),
        _recovery_rows=torch.zeros(4,dtype=torch.bool),_perturbed_rows=torch.tensor([True,True,False,False]),
        _gaits=torch.tensor([-1.,1.,-1.,1.]),_motion_ids=torch.arange(4),_idle_position_getup=True,
        _tracking_mix=torch.ones(4),_getup_position_weight=10.,reward_target_pos=torch.zeros(4,15,3),
        _ae_weight=.2,_mode=0,_additive_head_reward=False,_loss_weights=torch.tensor([1.,3.2992958902731857,1.,1.]),
        _append_extremity_speed_loss=lambda terms,*a:terms,
        loss_term_names=('position_mse','linear_velocity_mse','rotation_mse','angular_velocity_mse','flat_com_velocity','motion_prior'))
    checks=0
    for tick in (0,15,30,45,60,120):
        e._time_buf=torch.full((4,),tick/30.)
        for body in (0,1,14):
            for axis in range(3):
                v=torch.zeros(4,15,3);v[:,body,axis]=2.
                args=(torch.ones(4,15,3),torch.ones(4,15,4),v,torch.zeros_like(v),torch.zeros_like(v),torch.zeros_like(v))
                e._perturb_cfg=dict(ae_ticks=30,blend_ticks=30,ae_mse_weight=.010628431805636024,idle_pose_mse_multiplier=5.)
                baseline=e._tracking_losses(*args)
                e._perturb_cfg[KEY]=5.
                actual=e._tracking_losses(*args)
                expected=baseline.clone()
                if body==0:expected[:,1]*=5.
                torch.testing.assert_close(actual,expected)
                checks+=1
    return dict(passed=True,cases=checks,scope='normal/perturbed idle/loco, XYZ, pelvis-only x5, limbs unchanged, handoff unchanged')

def prepare():
    base=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    active=json.loads((d.OUT/'active_run.json').read_text())
    with zipfile.ZipFile(base['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    assert hashlib.sha256(Path(base['source']['local']).read_bytes()).hexdigest()==base['source']['sha256']
    code=patch(entries['pipeline/perturbed_omni.py'].decode());tests=test(code)
    entries['pipeline/perturbed_omni.py']=code.encode()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml']);cfg['perturbed_motion'][KEY]=5.
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    source=d.OUT/'locomotion-pelvis5-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries.items():z.writestr(name,data)
    data=source.read_bytes();sha=hashlib.sha256(data).hexdigest()
    key='mimickit/pipeline_20261014/locomotion-pelvis5/source_'+sha[:12]+'.zip'
    c=d.cloud.s3();c.put_object(Bucket=d.cloud.rp.VOLUME_ID,Key=key,Body=data)
    d.verified_readback(c,d.cloud.rp.VOLUME_ID,key,sha)
    shared=Path(__file__).with_name('perturbed_omni.py');shared.write_text(patch(shared.read_text()))
    d.save('pelvis5-before-plan',base);d.save('pelvis5-old-launch',json.loads((d.OUT/'launch.json').read_text()))
    plan=dict(old_run=active['run'],pod=active['pod'],source=dict(local=str(source),key=key,sha256=sha))
    d.save('ae30-switch',plan);d.save('pelvis5-source-verification',dict(plan=plan,tests=tests))
    print(json.dumps(dict(plan=plan,tests=tests)),flush=True)

def capture():
    r.capture()
    d.save('pelvis5-preserved-checkpoint',json.loads((d.OUT/'ae30-switch.json').read_text())['checkpoint'])

def launch():
    p=json.loads((d.OUT/'ae30-switch.json').read_text());source=p['source'];cp=p['checkpoint']
    code='''import json,hashlib,zipfile,io
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial');p=json.loads((r/'private.json').read_text())
c=boto3.client('s3',**p['s3']);data=c.get_object(Bucket='aj7d2jzwuq',Key=SOURCE_KEY)['Body'].read()
assert hashlib.sha256(data).hexdigest()==SOURCE_SHA
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==CP_SHA
(r/'source.zip').write_bytes(data)
with zipfile.ZipFile(io.BytesIO(data)) as z:z.extractall(r)
p['resume_checkpoint']=CHECKPOINT
(r/'private.json').write_text(json.dumps(p))
(r/'stop.request').unlink(missing_ok=True)
print('Source and latest checkpoint verified')
'''.replace('SOURCE_KEY',repr(source['key'])).replace('SOURCE_SHA',repr(source['sha256'])).replace('CP_SHA',repr(cp['sha256'])).replace('CHECKPOINT',repr(dict(key=cp['key'],sha256=cp['sha256'])))
    print(r.remote(code),flush=True)
    base=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    base.update(source=source,checkpoint=cp,worlds=1024,run_suffix='uefn_locomotion_pelvis_velocity5_1024')
    d.save('getup-success-prepared',base);d.launch()

if __name__=='__main__':
    if sys.argv[1]=='stop':r.stop()
    else:globals()[sys.argv[1]]()
