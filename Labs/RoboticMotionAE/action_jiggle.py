"""Direct actor regularizer for sustained motor-command reversals, not reward."""
import torch
SPEC=dict(version=1,window_ticks=13,minimum_reversals=3,minimum_delta=.02,
          curvature_leeway=.04,weight=200.,scope='moving crawl, both legs disabled',
          units='normalized noise-free motor commands',definition='gated squared excess second difference')

def gates(mean,done,enabled,minimum_delta=.02):
    """[T,N,A], [T,N] transition done flags. Never cross episode/buffer boundaries."""
    out=torch.zeros_like(mean,dtype=torch.bool)
    if len(mean)<13:return out
    for t in range(6,len(mean)-6):
        delta=mean[t-5:t+7]-mean[t-6:t+6]
        previous=torch.zeros_like(delta[0]);reversals=torch.zeros_like(previous)
        for change in delta:
            sign=torch.where(change.abs()>minimum_delta,change.sign(),0.)
            reversals+=(sign*previous<0)
            previous=torch.where(sign!=0,sign,previous)
        valid=(done[t-6:t+6]==0).all(0)
        out[t]=(reversals>=3)&valid[:,None]&enabled[t].bool()
    return out

def penalty(previous,current,following,gate,leeway=.04):
    excess=(following-2*current+previous).abs().sub(leeway).clamp_min(0.)
    # Average across all samples and enabled motor slots, not only detected slots.
    return (excess.square()*gate).mean()

def attach(agent,config):
    """Opt-in wrapper; no model/optimizer/observation ABI changes."""
    import types
    spec=dict(config);assert spec==SPEC
    original_build=agent._build_train_data;original_loss=agent._compute_actor_loss
    agent.action_jiggle_spec=spec
    def build(self):
        info=original_build()
        with torch.no_grad():
            obs=self._exp_buffer.get_data('obs');T,N,D=obs.shape
            flat=obs.reshape(-1,D)
            means=torch.cat([self._model.eval_actor(self._obs_norm.normalize(x)).mode for x in flat.split(4096)]).reshape(T,N,-1)
            enabled=self._exp_buffer.get_data('action_jiggle_enabled')
            gate=gates(means,self._exp_buffer.get_data('done'),enabled,spec['minimum_delta'])
            self._exp_buffer.set_data('action_jiggle_gate',gate)
            self._exp_buffer.set_data('action_jiggle_previous_obs',torch.roll(obs,1,0))
            self._exp_buffer.set_data('action_jiggle_following_obs',torch.roll(obs,-1,0))
            info['action_jiggle_detected_fraction']=gate.float().mean()
        return info
    def loss(self,batch):
        info=original_loss(batch)
        # Full gradient through all three current-policy evaluations; no sampled actions.
        joined=torch.cat([batch['action_jiggle_previous_obs'],batch['obs'],batch['action_jiggle_following_obs']])
        mu=self._model.eval_actor(self._obs_norm.normalize(joined)).mode
        previous,current,following=mu.chunk(3)
        raw=penalty(previous,current,following,batch['action_jiggle_gate'],spec['curvature_leeway'])
        weighted=spec['weight']*raw
        info['actor_loss']=info['actor_loss']+weighted
        info['action_jiggle_raw']=raw.detach();info['action_jiggle_weighted']=weighted.detach()
        return info
    record=agent._record_data_pre_step
    def record_pre(self,obs,info,action,action_info):
        record(obs,info,action,action_info)
        env=self._env
        active=(env._motion_ids==env.motion_labels.index('crawl'))&(env._codes==12)&(env._cohort>0)
        self._exp_buffer.record('action_jiggle_enabled',env._motor_enabled_binary.bool()&active[:,None])
    agent._build_train_data=types.MethodType(build,agent)
    agent._compute_actor_loss=types.MethodType(loss,agent)
    agent._record_data_pre_step=types.MethodType(record_pre,agent)
