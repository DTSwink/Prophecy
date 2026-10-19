"""CPU checks of the production cohort allocation and pelvis-only weighting."""
import ast,json,zipfile
from pathlib import Path
import torch,yaml

HERE=Path(__file__).parent
scope={'torch':torch}
tree=ast.parse((HERE/'omni_walk.py').read_text())
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('row_motion_weights','fixed_motion_rows')]
exec(compile(ast.Module(body=nodes,type_ignores=[]),'<production rows>','exec'),scope)
with zipfile.ZipFile(HERE.parents[1]/'Saved/MimicKitEquipment/main337-native-source.zip') as z:
    cfg=yaml.safe_load(z.read('prepared/env_config.yaml'))
    motions=yaml.safe_load(z.read('prepared/motions.yaml'))['motions']
    manifest={m['id']:m for m in json.loads(z.read('prepared/manifest.json'))['motions']}
gaits=torch.tensor([manifest[Path(m['file']).stem]['gait'] for m in motions])
weights=torch.tensor([m['weight'] for m in motions])
idle,pools=scope['row_motion_weights'](gaits,weights,.6,512)
assigned=scope['fixed_motion_rows'](pools,idle,512)
counts={name:int((gaits[assigned]==g).sum()) for name,g in [('idle',-1),('walk',0),('run',1)]}
assert idle==307 and abs(counts['walk']-counts['run'])==1
assert round(idle*.95)==292 and idle-round(idle*.95)==15
assert cfg['idle_recovery']['start_at_frame_zero'] and cfg['idle_recovery']['reset_at_getup_end']
assert cfg['idle_recovery']['target_radius_m']==.30 and cfg['target_radius_m']==.27
assert cfg['idle_recovery']['absolute_target'] is False and cfg['tracking_reward_form']=='reciprocal_sum'
assert 'termination_penalty_per_tick' not in cfg['idle_recovery']

class Base:
    def _tracking_losses(self,pos,rot,vel,ang,target_vel,target_ang):
        values=torch.zeros((len(vel),5))
        values[:,1]=(vel-target_vel).square().mean((1,2))*3.
        values[:,3]=(ang-target_ang).square().mean((1,2))*7.
        return values

tree=ast.parse((HERE/'recovery_omni.py').read_text())
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_tracking_losses')
scope.update(Base=Base)
testcls=ast.ClassDef(name='ProductionLoss',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=[method],decorator_list=[])
exec(compile(ast.fix_missing_locations(ast.Module(body=[testcls],type_ignores=[])),'<production loss>','exec'),scope)
env=scope['ProductionLoss']();env._flat_com_config=False
env._recovery_pelvis_velocity_multiplier=2.;env._recovery_rows=torch.tensor([True,False])
env.loss_weights={'pelvis_velocity_extra':3./15}
vel=torch.zeros(2,15,3);vel[:,0]=2.;vel[:,3]=5.
ang=torch.ones_like(vel);target=torch.zeros_like(vel)
result=env._tracking_losses(None,None,vel,ang,target,target)
torch.testing.assert_close(result[:,-1],torch.tensor([.8,0.]))
torch.testing.assert_close(result[:,1],torch.full((2,),5.8))
torch.testing.assert_close(result[:,3],torch.full((2,),7.))
assert not any(isinstance(n,ast.FunctionDef) and n.name=='_apply_termination_penalty' for n in cls.body)
print('PASS: actual row counts',counts,'recovery292 / ordinary idle15; pelvis contribution doubled only on recovery; angular/limb terms unchanged; penalty removed')
