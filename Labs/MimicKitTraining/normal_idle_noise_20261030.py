"""Pinned resume: ordinary idle >=2%, one-third exploration; PPO-consistent std."""
import json, hashlib, zipfile, pickle, sys
from pathlib import Path
import yaml
import idle_leg_velocity5_20261029 as h

h.OUT = h.d.OUT / 'normal-idle-noise-20261030'
NOISE = '''"""Cohort exploration offsets carried with shuffled PPO samples."""
import torch
from learning.distribution_gaussian_diag import DistributionGaussianDiag

def normal_idle_mask(env):
    return ((env._gaits[env._fixed_motion_ids] == -1) &
            ~env._perturbed_rows & ~env._recovery_rows & ~env._final.minus)

def apply_noise_offset(dist, offset):
    if offset is None:
        return dist
    return DistributionGaussianDiag(dist.mean, dist.logstd + offset[..., None])
'''

def prepare():
    h.OUT.mkdir(exist_ok=True)
    old=json.loads((h.d.OUT/'getup-success-prepared.json').read_text());h.save('previous-plan',old)
    assert old['source']['sha256']=='1c2d2b9be73da94f6fbf12d19d9d35ebd53a5a0ee81809bc23a2674c70a66513'
    with zipfile.ZipFile(old['source']['local']) as z: entries={n:z.read(n) for n in z.namelist()}
    changed=[]
    def edit(name, fn):
        s=fn(entries[name].decode());compile(s,name,'exec');entries[name]=s.encode();changed.append(name)
    one=h.one
    edit('pipeline/idle_minus_allocation.py',lambda s:one(s,
        '    return idle+extra, normal_idle+extra, minus',
        '''    ordinary = normal_idle-old_minus
    minimum = math.ceil(worlds*config['perturbed_motion'].get('normal_idle_min_fraction', 0))
    extra_normal = max(0, minimum-ordinary)
    if idle+extra+extra_normal > worlds:
        raise ValueError('Requested idle cohorts exceed batch size')
    return idle+extra+extra_normal, normal_idle+extra+extra_normal, minus'''))
    def omni(s):
        s=one(s,'from learning.ppo_agent import PPOAgent','from learning.ppo_agent import PPOAgent\nfrom cohort_noise import normal_idle_mask, apply_noise_offset')
        s=one(s,"        self._actor_kl_limit = float(config.get('actor_kl_limit', 0.))", """        self._normal_idle_noise_multiplier = float(config.get('normal_idle_action_noise_multiplier', 1.))
        assert 0 < self._normal_idle_noise_multiplier <= 1
        self._actor_kl_limit = float(config.get('actor_kl_limit', 0.))""")
        s=one(s,"        self._model = OmniPPOModel(config['model'], self._env)","""        self._model = OmniPPOModel(config['model'], self._env)
        # Static fixed-motion cohorts; no checkpoint parameter or observation change.
        self._action_noise_offset = torch.where(normal_idle_mask(self._env),
            math.log(self._normal_idle_noise_multiplier), 0.)
        self._env._normal_idle_action_noise_multiplier = self._normal_idle_noise_multiplier

    def _apply_action_noise_offset(self, dist, offset):
        return apply_noise_offset(dist, offset)""")
        s=one(s,"        self._exp_buffer.record('next_phase', self._env.next_phase_target())", "        self._exp_buffer.record('action_logstd_offset', self._action_noise_offset)\n        self._exp_buffer.record('next_phase', self._env.next_phase_target())")
        s=one(s,'    dist = agent._model._action_dist(hidden)',"    dist = apply_noise_offset(agent._model._action_dist(hidden), batch.get('action_logstd_offset'))")
        return s
    edit('pipeline/omni_policy.py',omni)
    def ppo(s):
        s=one(s,'        norm_action_dist = self._model.eval_actor(norm_obs)', '''        norm_action_dist = self._model.eval_actor(norm_obs)
        if hasattr(self, '_action_noise_offset'):
            norm_action_dist = self._apply_action_noise_offset(norm_action_dist, self._action_noise_offset)''')
        return one(s,'        a_dist = self._model.eval_actor(norm_obs)', '''        a_dist = self._model.eval_actor(norm_obs)
        if 'action_logstd_offset' in batch:
            a_dist = self._apply_action_noise_offset(a_dist, batch['action_logstd_offset'][rand_action_mask])''')
    edit('MimicKit/mimickit/learning/ppo_agent.py',ppo)
    def kl(s):
        s=one(s,'from util import torch_util','from util import torch_util\nfrom cohort_noise import apply_noise_offset')
        s=one(s,'    probe = obs[indices]',"""    probe = obs[indices]
    offset = (agent._exp_buffer.get_data_flat('action_logstd_offset')
              if 'action_logstd_offset' in agent._exp_buffer._buffers else None)
    def actor(observations, rows=None):
        selected = offset if rows is None or offset is None else offset[rows]
        return apply_noise_offset(agent._model.eval_actor(observations), selected)""")
        s=one(s,'old = agent._model.eval_actor(obs)','old = actor(obs)')
        s=one(s,'agent._model.eval_actor(probe)','actor(probe, indices)')
        return one(s,'gaussian_kl(old_mean, old_logstd, agent._model.eval_actor(obs))','gaussian_kl(old_mean, old_logstd, actor(obs))')
    edit('pipeline/kl_guard.py',kl)
    def train(s):
        s=one(s,"                    if name=='agent_config.yaml' and new.get('actor_kl_limit',0)>0:", """                    if (name=='agent_config.yaml' and a.equipment_omni and a.resume_perturbed_motion
                            and 'normal_idle_action_noise_multiplier' in new):
                        # Explicit October30 ordinary-idle exploration experiment.
                        assert new['normal_idle_action_noise_multiplier'] == 1/3
                        old['normal_idle_action_noise_multiplier'] = new['normal_idle_action_noise_multiplier']
                    if name=='agent_config.yaml' and new.get('actor_kl_limit',0)>0:""")
        return one(s,"    rollout_sigma=noise_metadata['training_action_noise_std']", """    if hasattr(agent, '_action_noise_offset'):
        from cohort_noise import normal_idle_mask
        noise_metadata['normal_idle_action_noise_std'] = float(agent_config['model']['action_std'])*agent._normal_idle_noise_multiplier
        atomic_json(directory/'normal_idle_noise.json',dict(
            normal_idle_rows=int(normal_idle_mask(env).sum()), worlds=a.worlds,
            normal_idle_fraction=float(normal_idle_mask(env).float().mean()),
            multiplier=agent._normal_idle_noise_multiplier,
            normal_idle_std=noise_metadata['normal_idle_action_noise_std'],
            other_std=noise_metadata['training_action_noise_std']))
    rollout_sigma=noise_metadata['training_action_noise_std']""")
    edit('pipeline/train.py',train)
    def replay(s):
        return one(s,'            metas.append(meta)',"""            if hasattr(self.env, '_normal_idle_action_noise_multiplier'):
                from cohort_noise import normal_idle_mask
                if bool(normal_idle_mask(self.env)[w]):
                    meta['training_action_noise_std'] *= self.env._normal_idle_action_noise_multiplier
            metas.append(meta)""")
    edit('pipeline/observe_many.py',replay)
    entries['pipeline/cohort_noise.py']=NOISE.encode();changed.append('pipeline/cohort_noise.py')
    cfg=yaml.safe_load(entries['prepared/env_config.yaml']);cfg['perturbed_motion']['normal_idle_min_fraction']=.02
    ac=yaml.safe_load(entries['prepared/agent_config.yaml']);ac['normal_idle_action_noise_multiplier']=1/3
    assert ac['model']['action_std']==.075
    for name,c in [('env',cfg),('agent',ac)]:
        path='prepared/'+name+'_config.yaml';entries[path]=yaml.safe_dump(c,sort_keys=False).encode();changed.append(path)
    source=h.OUT/'source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    h.save('prepared',dict(old,source=dict(local=str(source),sha256=sha,key='mimickit/pipeline_20261014/normal-idle-noise/source_'+sha[:12]+'.zip'),run_suffix='uefn_locomotion_idle2_noise025_4000ada_2048'))
    h.save('delta',dict(files=changed,normal_idle_fraction=.02,normal_idle_noise_multiplier=1/3))
    with zipfile.ZipFile(source) as z,zipfile.ZipFile(h.OUT/'overlay.zip','w',zipfile.ZIP_DEFLATED) as delta:
        delta.writestr('infos.pkl',pickle.dumps(z.infolist()))
        for n in changed:delta.writestr(n,entries[n])
    # Unit test only needs these production modules; no physics dependencies.
    testroot=h.OUT/'unit_source'
    for n in ['pipeline/cohort_noise.py','pipeline/idle_minus_allocation.py','MimicKit/mimickit/learning/distribution_gaussian_diag.py']:
        p=testroot/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(entries[n])
    print(json.dumps(dict(source_sha256=sha,files=changed)))

def verify():
    (h.d.OUT/'latest-restart-receipt.txt').write_text(str(h.OUT))
    script=Path(__file__).with_name('verify_loco_unchanged_resume.py').read_text()
    script=h.one(script,"  assert yaml.safe_load(cp.read(name))==yaml.safe_load((p/name).read_text()),name", """  expected=yaml.safe_load(cp.read(name));actual=yaml.safe_load((p/name).read_text())
  if name=='env_config.yaml':expected['perturbed_motion']['normal_idle_min_fraction']=.02
  if name=='agent_config.yaml':expected['normal_idle_action_noise_multiplier']=1/3
  assert expected==actual,name""")
    script=h.one(script,"dispatch=json.loads((p/'lossless_dispatch.json').read_text())", """noise=json.loads((p/'normal_idle_noise.json').read_text())
assert noise['normal_idle_rows']==41 and abs(noise['normal_idle_std']-.025)<1e-8
assert abs(noise['other_std']-.075)<1e-8
dispatch=json.loads((p/'lossless_dispatch.json').read_text())""")
    scope={'__name__':'isolated_normal_idle_verification'};exec(compile(script,'normal_idle_verify','exec'),scope);scope['main']()
    if json.loads((h.OUT/'live-verification.json').read_text())['ready']:
        print(h.r.remote("from pathlib import Path;Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch();print('Handoff verified')",timeout=20))

if __name__=='__main__':
    action=sys.argv[1]
    (globals()[action] if action in ['prepare','verify'] else getattr(h,action))()
