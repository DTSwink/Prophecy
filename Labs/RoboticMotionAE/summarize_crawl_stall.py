"""Summarize the no-update crawl learning-signal audit."""
from pathlib import Path
import json,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

P=Path(__file__).resolve().parents[2]/'Saved/MimicKitSlowLoco/crawl-stall-audit-20261102'
z=np.load(P/'rollout.npz');m=json.loads((P/'probe-metadata.json').read_text());groups={}
for code in (4,8,12):
    mask=z['codes']==code;loss=z['loss'][mask];reward=np.exp(-loss.sum(-1));done=z['done'][mask];age=z['age'][mask]
    failures=z['sphere_ratio'][mask][done==1]>1
    bounds=np.array(m['bands'][code]);zero_excess=np.maximum(bounds[0],0)+np.maximum(-bounds[1],0)
    groups[str(code)]=dict(transitions=int(mask.sum()),observed_failure_events=int(sum(done==1)),
        completed_episode_ticks_quantiles=np.quantile(age[done!=0],[0,.5,1]).tolist(),
        mean_actual_pelvis_velocity_m_s=z['root_velocity'][mask].mean(0).tolist(),
        mean_target_pelvis_velocity_m_s=z['target_velocity'][mask].mean(0).tolist(),
        mean_loss_terms=loss.mean(0).tolist(),pose_share_of_mean_loss=float(loss[:,:][:,[0,2]].sum()/loss.sum()),
        median_dense_reward=float(np.median(reward)),fraction_dense_reward_below_001=float(np.mean(reward<.001)),
        median_reward_after_best_uniform_velocity_correction=float(np.median(z['reward_best_drift'][mask])),
        median_absolute_reward_gain_from_best_uniform_velocity_correction=float(np.median(z['reward_best_drift'][mask]-reward)),
        critic_quantiles=np.quantile(z['value'][mask],[.1,.5,.9]).tolist(),
        upper_command_rms_rad_s=float(np.sqrt((z['action_mode'][mask][:,:20]**2).mean())),
        upper_actual_joint_velocity_rms_rad_s=float(np.sqrt((z['joint_velocity'][mask][:,:20]**2).mean())),
        failed_boundary_counts=dict(zip(['head','right_hand','left_hand','right_foot','left_foot','pelvis'],failures.sum(0).tolist())),
        com_band_m_s=bounds.tolist(),stationary_com_loss=float(np.mean(zero_excess**2)*.6771039952430788))
ppo=json.loads((P/'ppo.json').read_text());terminal=[]
for batch in ppo:
    done=np.array(batch['done']);target=np.array(batch['return_target']);terminal.extend(target[done==1].tolist())
report=dict(checkpoint=19886,worlds=96,ticks=256,transitions=24576,mode='TRAIN with original0.05 exploration, no optimizer updates',
    groups=groups,terminal_target_min_max=[min(terminal),max(terminal)],
    hidden_sphere_observation_change=m['hidden_sphere_state_test']['max_observation_change'],
    passive_torque_max=m['passive_leg_torque_max'],
    limitations=['Fixed checkpoint, not a learning ablation; establishes signal imbalance and wiring, not proof that a proposed reward change will learn a full gait.',
        '32worlds per disabled-mask code, actual random init bank/reset path; episodes still active at final tick are censored. Failure-event counts are not failure probabilities.',
        'Best uniform velocity correction changes reward inputs algebraically, not a physically simulated intervention.',
        'PPO diagnostic advantage normalization is crawl-only; production batch contains other motions.',
        'Critic cannot observe accumulated sphere error or reanchor timing; this is a secondary observability limitation, not sole cause of the stall.'],
    recommendation='For two-leg-disabled moving crawl, add a separate dense forward-motion reward towards the real scaled target speed so pose error cannot suppress it. Retain bounded pose imitation and existing failure penalty initially. Do not increase the penalty or upper-body caps based on this evidence alone. Validate in an isolated comparison before changing the live run.')
(P/'analysis.json').write_text(json.dumps(report,indent=2))
fig,ax=plt.subplots(1,3,figsize=(12,4.2));labels=['Right leg off','Left leg off','Both legs off'];x=np.arange(3)
actual=[groups[str(c)]['mean_actual_pelvis_velocity_m_s'][0]*100 for c in (4,8,12)];target=[groups[str(c)]['mean_target_pelvis_velocity_m_s'][0]*100 for c in (4,8,12)]
ax[0].bar(x-.18,actual,.36,label='Actual',color='#168c96');ax[0].bar(x+.18,target,.36,label='Target',color='#9ab7bb');ax[0].set_ylabel('Forward speed (cm/s)');ax[0].legend(fontsize=8)
r=[groups[str(c)]['median_dense_reward'] for c in (4,8,12)];ax[1].bar(x,r,color=['#168c96','#168c96','#cd5656']);ax[1].set_yscale('log');ax[1].set_ylabel('Median reward before failure penalty')
pose=[sum(groups[str(c)]['mean_loss_terms'][i] for i in (0,2)) for c in (4,8,12)];other=[sum(groups[str(c)]['mean_loss_terms'][i] for i in (1,3,4)) for c in (4,8,12)]
ax[2].bar(x,pose,color='#cd5656',label='Position + rotation');ax[2].bar(x,other,bottom=pose,color='#168c96',label='Velocity terms');ax[2].set_ylabel('Mean weighted loss');ax[2].legend(fontsize=8)
for a in ax:a.set_xticks(x,labels,rotation=20);a.grid(axis='y',alpha=.2)
fig.suptitle('Two passive legs: weak movement signal under dominant pose error',fontsize=13)
fig.text(.5,.01,'Checkpoint19886 · 32 worlds per mask · 256 ticks with resets and training noise · no learning updates',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.04,1,.94));fig.savefig(P/'signal-comparison.png',dpi=160);plt.close(fig)
print(json.dumps({k:{'speed_cm_s':v['mean_actual_pelvis_velocity_m_s'][0]*100,'pose_share':v['pose_share_of_mean_loss'],'median_reward':v['median_dense_reward'],'stationary_com_loss':v['stationary_com_loss']} for k,v in groups.items()},indent=2))
