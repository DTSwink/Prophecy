"""Add an opt-in world-horizontal pelvis-origin excess-speed cost."""
import ast
import hashlib
import json
import pickle
import zipfile
from pathlib import Path
import numpy as np
import yaml
from getup_foot_regularizers import once

OUT=Path(__file__).resolve().parents[2]/'Saved/MimicKitEquipment'
HELPER='''@torch.jit.script
def getup_pelvis_horizontal_cost(velocity: torch.Tensor, limit: torch.Tensor):
    # Physics is Z-up. velocity is world-space BODY ORIGIN velocity, not COM.
    return (velocity[..., :2].norm(p=2, dim=-1)-limit).clamp_min(0.).square()


'''

def patch(s):
    s=s.replace('\r\n','\n')
    s=once(s,'@torch.jit.script\ndef getup_foot_costs(',HELPER+'@torch.jit.script\ndef getup_foot_costs(')
    anchor="        foot_cfg = cfg.get('getup_foot_regularizers')\n"
    s=once(s,anchor,'''        pelvis_cfg = cfg.get('getup_pelvis_horizontal_regularizer')
        self._pelvis_horizontal_enabled = pelvis_cfg is not None
        if self._pelvis_horizontal_enabled:
            if names[0] != 'pelvis' or not self._idle_position_getup:
                raise ValueError('Pelvis speed cost requires pelvis-first idle-position get-ups')
            gravity = torch.as_tensor(self._engine.get_gravity(), device=self._device)
            torch.testing.assert_close(gravity[:2], torch.zeros(2, device=self._device))
            if not gravity[2] < 0:
                raise ValueError('Expected world Z-up physics')
            lib = self._recovery_lib
            limits = []
            for motion in range(lib.get_num_motions()):
                entry = pelvis_cfg['motions'][Path(lib.get_motion_file(motion)).stem]
                start = int(lib._motion_start_idx[motion])
                count = int(lib._motion_num_frames[motion])
                peak = lib._frame_root_vel[start:start+count, :2].norm(p=2, dim=-1).max()
                limit = float(entry['peak_horizontal_m_s'])
                torch.testing.assert_close(peak, torch.tensor(limit, device=self._device), atol=1e-6, rtol=1e-6)
                limits.append(limit)
            # Either get-up can roll into the other: one common peak for all rows.
            self._pelvis_horizontal_limits = torch.full((len(limits),), max(limits), device=self._device)
            self._pelvis_horizontal_weight = float(pelvis_cfg['weight'])
            if not math.isfinite(self._pelvis_horizontal_weight) or self._pelvis_horizontal_weight <= 0:
                raise ValueError('Pelvis horizontal weight must be finite and positive')
'''+anchor)
    anchor='        self.loss_terms = torch.zeros((n, len(self.loss_term_names)), device=self._device)\n'
    s=once(s,anchor,'''        if self._pelvis_horizontal_enabled:
            self.loss_term_names = (*self.loss_term_names, 'pelvis_horizontal_speed_excess')
            self.loss_weights['pelvis_horizontal_speed_excess'] = self._pelvis_horizontal_weight
'''+anchor)
    old='''        if not self._perturb_ready or not self._foot_regularizers_enabled:
            return terms
        costs = self._foot_regularizer_raw(rot) * self._foot_cost_weights
        costs = torch.where(self._perturbed_getup[:, None], costs, 0.)
        return torch.cat((terms, costs), -1)
'''
    new='''        if not self._perturb_ready:
            return terms
        if self._foot_regularizers_enabled:
            costs = self._foot_regularizer_raw(rot) * self._foot_cost_weights
            costs = torch.where(self._perturbed_getup[:, None], costs, 0.)
            terms = torch.cat((terms, costs), -1)
        if self._pelvis_horizontal_enabled:
            # absolute_walk already subtracts omega x COM-offset from engine COM velocity.
            raw = getup_pelvis_horizontal_cost(vel[:, 0], self._pelvis_horizontal_limits[self._recovery_motion])
            cost = torch.where(self._perturbed_getup, raw*self._pelvis_horizontal_weight, 0.)
            terms = torch.cat((terms, cost[:, None]), -1)
        return terms
'''
    s=once(s,old,new)
    s=once(s,"                self._reward_buf[rows] -= self.loss_terms[rows, -2:].sum(-1)\n",'''                for term in ('feet_target_velocity', 'feet_idle_local_rotation'):
                    self._reward_buf[rows] -= self.loss_terms[rows, self.loss_term_names.index(term)]
            if self._pelvis_horizontal_enabled:
                self._reward_buf[rows] -= self.loss_terms[rows, self.loss_term_names.index('pelvis_horizontal_speed_excess')]
''')
    anchor="                result['reward_definition'] += ' - weighted ankle target-velocity cost - weighted ankle idle-local rotation cost'\n"
    s=once(s,anchor,anchor+'''            if self._pelvis_horizontal_enabled:
                result['active_loss_terms'] += ['pelvis_horizontal_speed_excess']
                result['pelvis_horizontal_speed_limit_m_s'] = float(self._pelvis_horizontal_limits[self._recovery_motion[world]])
                result['reward_definition'] += ' - weighted squared pelvis horizontal speed excess'
''')
    anchor="        result['perturbed_curriculum'] = dict(self._perturb_cfg)\n"
    s=once(s,anchor,anchor+'''        if self._pelvis_horizontal_enabled:
            result['pelvis_horizontal_regularizer'] = dict(self._perturb_cfg['getup_pelvis_horizontal_regularizer'])
            result['pelvis_horizontal_speed_excess_definition'] = 'weight * max(sqrt(vx^2+vy^2)-max_reference_clip_peak,0)^2; world Z-up pelvis BODY ORIGIN velocity in m/s; perturbed get-ups including plus only'
''')
    ast.parse(s)
    return s

def prepare():
    plan=json.loads((OUT/'getup-success-prepared.json').read_text())
    with zipfile.ZipFile(plan['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    motions={}
    for kind in ('front','back'):
        name=f'getUp_{kind}_quick_robotic';raw=entries[f'motions/recovery/{name}.pkl'];d=pickle.loads(raw)
        # Exactly MotionLib's forward difference, with duplicated final velocity.
        vel=np.diff(d['frames'][:,:3],axis=0)*d['fps'];speed=np.linalg.norm(vel[:,:2],axis=-1);peak=int(speed.argmax())
        motions[name]=dict(peak_horizontal_m_s=float(speed[peak]),peak_frame=peak,peak_velocity_xyz_m_s=vel[peak].tolist(),
            frames=len(d['frames']),fps=d['fps'],motion_sha256=hashlib.sha256(raw).hexdigest())
    cfg=yaml.safe_load(entries['prepared/env_config.yaml'])
    cfg['perturbed_motion']['getup_pelvis_horizontal_regularizer']=dict(weight=1.,fixed_weight=True,target_fraction=.07,
        calibration_pending=True,scope='perturbed get-ups including perturbed+',axes='world XY horizontal; Z vertical',
        velocity_point='pelvis body origin, not COM',form='max(horizontal_speed-max_reference_peak,0)^2',
        limit_mode='shared_maximum_over_both_getups',shared_limit_m_s=max(x['peak_horizontal_m_s'] for x in motions.values()),motions=motions)
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    entries['pipeline/perturbed_omni.py']=patch(entries['pipeline/perturbed_omni.py'].decode()).encode()
    path=OUT/'getup-pelvis-candidate.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    (OUT/'getup-pelvis-previous-plan.json').write_text(json.dumps(plan,indent=2))
    (OUT/'getup-pelvis-reference.json').write_text(json.dumps(cfg['perturbed_motion']['getup_pelvis_horizontal_regularizer'],indent=2))
    p=Path(__file__).with_name('perturbed_omni.py');p.write_text(patch(p.read_text()),encoding='utf-8')
    print(json.dumps(motions))

if __name__=='__main__':prepare()
