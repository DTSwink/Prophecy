"""Opt-in position/rotation MSE multiplier for perturbed ordinary idle rows."""
import ast
from types import SimpleNamespace
import torch
from perturbed_motion import tracking_blend


def patch_source(source):
    anchor = "        terms[:, :4] *= mse_mix[:, None]\n"
    replacement = anchor + """        idle_pose_scale = float(self._perturb_cfg.get('idle_pose_mse_multiplier', 1.))
        if idle_pose_scale != 1.:
            idle_rows = self._perturbed_rows & ~self._recovery_rows & (self._gaits[self._motion_ids] == -1)
            scale = torch.where(idle_rows, idle_pose_scale, 1.)
            terms[:, 0] *= scale
            terms[:, 2] *= scale
"""
    changes = [(anchor, replacement),
        ("        self._tracking_mix = torch.ones(n, device=self._device)\n",
         "        self._tracking_mix = torch.ones(n, device=self._device)\n"
         "        idle_scale = float(cfg.get('idle_pose_mse_multiplier', 1.))\n"
         "        if not math.isfinite(idle_scale) or idle_scale <= 0:\n"
         "            raise ValueError('Perturbed idle pose MSE multiplier must be finite and positive')\n"),
        ("        result['perturbed_curriculum'] = dict(self._perturb_cfg)\n",
         "        result['perturbed_curriculum'] = dict(self._perturb_cfg)\n"
         "        result['perturbed_idle_pose_mse_multiplier'] = float(self._perturb_cfg.get('idle_pose_mse_multiplier', 1.))\n"
         "        result['perturbed_idle_pose_mse_scope'] = 'position and rotation, ordinary perturbed idle only, all episode ticks; applied after early/handoff weighting'\n")]
    for old, new in changes:
        if source.count(old) != 1:
            raise ValueError('Pinned source does not match idle multiplier patch')
        source = source.replace(old, new)
    compile(source, 'perturbed_omni.py', 'exec')
    return source


def check(before, after):
    class Base:
        def _tracking_losses(self, *args):
            return torch.full((6, 5), 2.)
    def build(source, tick, multiplier):
        method = next(n for c in ast.parse(source).body if isinstance(c, ast.ClassDef)
                      for n in c.body if isinstance(n, ast.FunctionDef) and n.name == '_tracking_losses')
        scope = dict(torch=torch, Base=Base, tracking_blend=tracking_blend,
                     EnvMode=SimpleNamespace(TRAIN=1), q=SimpleNamespace(quat_to_matrix=lambda x:x))
        cls=ast.ClassDef(name='Trial',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=[method],decorator_list=[])
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])), 'actual-method', 'exec'),scope)
        e=scope['Trial']()
        vars(e).update(_perturb_ready=True,_refresh_reward_rotations=lambda:None,
            _perturbed_ids=torch.tensor([0,1,2,4]),_prior_ids=torch.tensor([0,1,2]),
            _prior=SimpleNamespace(append=lambda *a:None,cost=lambda:torch.ones(3)*5),
            _prior_raw=torch.zeros(6),_time_buf=torch.full((6,),tick/30.),_mse_only=False,
            _perturb_cfg=dict(ae_ticks=30,blend_ticks=30,ae_mse_weight=.010628431805636024,idle_pose_mse_multiplier=multiplier),
            _perturbed_getup=torch.tensor([False,False,False,False,True,False]),
            _recovery_rows=torch.tensor([False,False,False,False,True,True]),
            _perturbed_rows=torch.tensor([True,True,True,False,True,False]),
            _gaits=torch.tensor([-1.,-1.,1.,-1.,-1.,-1.]),_motion_ids=torch.arange(6),
            _idle_position_getup=True,_tracking_mix=torch.ones(6),_getup_position_weight=10.,
            reward_target_pos=torch.zeros(6,15,3),_ae_weight=.2,_mode=0,_additive_head_reward=False,
            loss_term_names=('position_mse','linear_velocity_mse','rotation_mse','angular_velocity_mse','flat_com_velocity','motion_prior'))
        return e._tracking_losses(torch.ones(6,15,3),torch.ones(6,15,4),None,None,None,None)
    for tick in (0,2,29,30,45,59,60,120):
        baseline=build(before,tick,1.)
        torch.testing.assert_close(build(after,tick,1.),baseline)
        expected=baseline.clone();expected[:2,0]*=5;expected[:2,2]*=5
        torch.testing.assert_close(build(after,tick,5.),expected)
    return True
