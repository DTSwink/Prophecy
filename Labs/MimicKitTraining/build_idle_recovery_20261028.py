"""Isolated overlay on the verified locomotion package, never recovery working files."""
import json,zipfile,hashlib,copy,pickle
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitLocomotion/idle-recovery-20261028'

def main():
 OUT.mkdir(exist_ok=True)
 old=json.loads((ROOT/'Saved/MimicKitLocomotion/getup-success-prepared.json').read_text())
 assert old['source']['sha256']=='a757d51c66b09a5a50bdaaabe5df12f81def79fa352bde02a760761773f5f979'
 (OUT/'previous-plan.json').write_text(json.dumps(old,indent=2))
 changed={}
 def one(s,a,b):
  assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
 with zipfile.ZipFile(old['source']['local']) as z:
  def read(n):return z.read('pipeline/'+n).decode().replace('\r\n','\n')
  module=(ROOT/'Labs/MimicKitTraining/idle_recovery_reward.py').read_text()
  changed['pipeline/idle_recovery_reward.py']=module.encode()
  s='from idle_recovery_reward import idle_recovery_reward\n'+read('perturbed_omni.py')
  anchor='        self._com2_reward_values = torch.zeros((n, 3), device=self._device)'
  s=one(s,anchor,"""        self._idle_objective_terms = ('idle_stop', 'idle_pose', 'idle_smooth', 'idle_steps', 'idle_slip', 'idle_posture')
        self.loss_term_names = (*self.loss_term_names, *self._idle_objective_terms)
        for term in self._idle_objective_terms: self.loss_weights[term] = 1.
        self._idle_core_ids = torch.tensor([self.loss_term_names.index(n) for n in ('position_mse', 'rotation_mse', 'linear_velocity_mse', 'angular_velocity_mse', 'motion_prior')],device=self._device)
"""+anchor)
  anchor="        self._pushed_idle_prior_handoff = bool(cfg.get('pushed_idle_prior_handoff', False))"
  s=one(s,anchor,"""        self._idle_objective_rows = (self._gaits[self._fixed_motion_ids] == -1) & (self._perturbed_rows | self._final.minus)
"""+anchor)
  anchor='        return torch.cat((terms, foot_terms, leg_cost[:, None]), -1)'
  s=one(s,anchor,"""        original = torch.cat((terms, foot_terms, leg_cost[:, None]), -1)
        # Independent bounded costs: large COM2 error cannot hide better foot control.
        speed_sq = (com2_velocity(self._engine.get_body_vel(self._get_char_id())[:, self._com2_ids], self._com2_masses) - self._com2_targets[self._motion_ids]).square().sum(-1)
        pose = original[:, self._idle_core_ids].sum(-1)
        # Exact lowest box support point; v is already body-origin velocity.
        qr = rot[:, ids]
        centers = self._walking_foot_centers.expand(len(pos), -1, -1)
        axes = self._walking_foot_half_axes.expand(len(pos), -1, -1, -1)
        center_world = q.quat_rotate(qr, centers)
        axes_world = q.quat_rotate(qr[:, :, None, :].expand(-1, -1, 3, -1).reshape(-1,4), axes.reshape(-1,3)).reshape(len(pos),2,3,3)
        support = center_world - (axes_world * axes_world[..., 2:].sign()).sum(-2)
        support_vel = vel[:, ids] + torch.cross(ang[:, ids], support, dim=-1)
        contact = (1-bottoms/.01).clamp(0,1)
        slip_sq = (support_vel[..., :2].square().sum(-1)*contact).mean(-1)
        relative = q.quat_mul(rot[:, 0], q.quat_conjugate(self._idle_frame0_rot[self._motion_ids,0]))
        up_dot = 1-2*(relative[:,0].square()+relative[:,1].square())
        _, bounded = idle_recovery_reward(speed_sq, pose, raw[:,1:], leg_raw, self._head_reversal.raw,
            raw[:,0], slip_sq, pos[:,self._head_id,2]/self._idle_head_height[self._motion_ids].clamp_min(.1), up_dot, bottoms.amin(-1))
        mask = self._idle_objective_rows[:,None]
        return torch.cat((torch.where(mask, torch.zeros_like(original), original), torch.where(mask, bounded, torch.zeros_like(bounded))),-1)""")
  anchor='            self._com2_reward_values.copy_(torch.stack((factor, distance, angle), -1))'
  s=one(s,anchor,"""            factor = torch.where(self._idle_objective_rows, torch.ones_like(factor), factor)
            self._reward_buf.copy_(torch.where(self._idle_objective_rows, (1-self.loss_terms.sum(-1)).clamp(0,1), self._reward_buf))
"""+anchor)
  anchor="        result['leg_reversal'] = self._perturb_cfg['leg_reversal']['description']"
  s=one(s,anchor,anchor+"""
        if bool(self._idle_objective_rows[world]):
            result['reward_from_loss'] = 'idle_recovery_bounded'
            result['idle_recovery_objective'] = self._perturb_cfg['idle_recovery_objective']
""")
  s=one(s,"        perturbed = bool(self._perturbed_rows[world])", """        if bool(self._idle_objective_rows[world]):
            result['com2_reward_gate']['active'] = 'replaced by independent idle_stop cost; multiplier1'
            result['com2_loss']['active'] = 'replaced by independent idle_stop cost'
        perturbed = bool(self._perturbed_rows[world])""")
  changed['pipeline/perturbed_omni.py']=s.encode()
  s=read('final_locomotion.py');anchor='        error=self.kicker.apply(rows,desired)'
  s=one(s,anchor,anchor+"""
        # Do not compare externally injected motion against pre-push reversal history.
        idle_rows=rows[e._idle_objective_rows[rows]]
        for state in (e._head_reversal,e._foot_regularizers,e._leg_reversal):
            state.history[idle_rows]=0
        # Keep contact/cadence ages: this does not grant a new free-step window.
""");changed['pipeline/final_locomotion.py']=s.encode()
  s=read('uefn_package.py');s=one(s,"('train.py','resume.py'","('idle_recovery_reward.py','train.py','resume.py'");changed['pipeline/uefn_package.py']=s.encode()
  s=read('observe.py')
  s=one(s,"                row_info = getattr(self, 'equipment_metadata', {})", """                row_info = getattr(self, 'equipment_metadata', {})
                if row_info.get('reward_from_loss') == 'idle_recovery_bounded':
                    metadata.update(reward_from_loss='idle_recovery_bounded', reward_definition='1 - sum bounded idle costs, then unchanged failure penalty', idle_recovery_objective=row_info['idle_recovery_objective'])
                    for field in ('com2_reward_gate','com2_loss'):metadata[field]=row_info[field]
""")
  changed['pipeline/observe.py']=s.encode()
  cfg=yaml.safe_load(z.read('prepared/env_config.yaml'))
  cfg['perturbed_motion']['idle_recovery_objective']=dict(version=1,scope='idle P/P+/P-minus only',weights=dict(stop=.55,pose=.10,smooth=.15,steps=.10,slip=.10),description='Independent bounded costs; 1-sum costs, head-height/upright gate; existing terminal penalties unchanged. Prior/MSE timing retained within pose term. Speed-dependent quieting, no timing observations. Cross-push reversal histories cleared, cadence retained.')
  changed['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
  for name,data in changed.items():
   if name.endswith('.py'):compile(data,name,'exec')
   p=OUT/'candidate'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
  source=OUT/'source.zip'
  with zipfile.ZipFile(source,'w') as dest:
   for info in z.infolist():dest.writestr(copy.copy(info),changed.get(info.filename,z.read(info.filename)))
   for name in set(changed)-set(z.namelist()):dest.writestr(name,changed[name])
 with zipfile.ZipFile(source) as built,zipfile.ZipFile(OUT/'overlay.zip','w',zipfile.ZIP_DEFLATED) as overlay:
  overlay.writestr('infos.pkl',pickle.dumps(built.infolist()))
  for name,data in changed.items():overlay.writestr(name,data)
 sha=hashlib.sha256(source.read_bytes()).hexdigest();plan=copy.deepcopy(old)
 plan.update(source=dict(local=str(source),sha256=sha,key='mimickit/pipeline_20261014/idle-recovery/source_'+sha[:12]+'.zip'),worlds=2048,run_suffix='uefn_locomotion_idle_recovery_2048')
 (OUT/'prepared.json').write_text(json.dumps(plan,indent=2));print(json.dumps(dict(source=plan['source'],changed=list(changed))))

if __name__=='__main__':main()
