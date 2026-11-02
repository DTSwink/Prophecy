"""Compare isolated race reports; never reads/writes live training state."""
import argparse,json
from pathlib import Path
import numpy as np

GROUPS=['normal_loco','normal_idle','perturbed_loco','perturbed_idle']

def outcomes(evaluation,group,seeds=None):
    result={}
    for row in evaluation['rows']:
        if seeds is not None and row['seed'] not in seeds:continue
        for i,g in enumerate(row['row_group']):
            if GROUPS[g]==group:
                result[(row['seed'],i)]=(bool(row['row_failed'][i]),row['row_motion'][i])
    return result

def summarize(folder):
    folder=Path(folder)
    runs={name:json.loads((folder/name/'result.json').read_text()) for name in ['ppo','world_model']}
    assert all(r['complete'] for r in runs.values()),'Comparison not finished'
    assert runs['ppo']['checkpoint_sha256']==runs['world_model']['checkpoint_sha256']
    assert runs['ppo']['gpu']==runs['world_model']['gpu']
    finals={n:r['evaluations'][-1] for n,r in runs.items()}
    initial={n:r['evaluations'][0] for n,r in runs.items()}
    hashes=lambda ev:{r['seed']:r['initial_observation_sha256'] for r in ev['rows']}
    matched=hashes(finals['ppo'])==hashes(finals['world_model'])
    summary=dict(common_checkpoint=runs['ppo']['checkpoint_sha256'],
        matched_final_initial_observations=matched,
        actor_ever_updated=runs['world_model']['actor_ever_updated'],groups={},runs={})
    for n,r in runs.items():
        summary['runs'][n]=dict(seconds=r['training_seconds'],updates=len(r['updates']),
            real_transitions=r['updates'][-1]['transitions'],
            setup_and_initial_eval_seconds=r['common_setup_and_initial_evaluation_seconds'])
    rng=np.random.default_rng(820417)
    for group in GROUPS:
        a,b=[outcomes(finals[n],group) for n in ['ppo','world_model']]
        assert a.keys()==b.keys()
        assert all(a[k][1]==b[k][1] for k in a),'Motion assignments differ'
        keys=sorted(a);pa=np.array([a[k][0] for k in keys]);pb=np.array([b[k][0] for k in keys])
        d=(pa.astype(float)-pb.astype(float))*100
        # Resample motion groups, retaining within-motion reset correlation.
        motions=np.array([a[k][1] for k in keys]);clusters=np.unique(motions)
        boot=[]
        for _ in range(2000):
            chosen=rng.choice(clusters,len(clusters),replace=True)
            sample=np.concatenate([d[motions==m] for m in chosen]);boot.append(sample.mean())
        summary['groups'][group]=dict(episodes=len(keys),ppo_failure_percent=pa.mean()*100,
            world_model_failure_percent=pb.mean()*100,
            world_model_reduction_percentage_points=d.mean(),
            motion_cluster_interval_95=np.quantile(boot,[.025,.975]).tolist(),
            limitation='Evaluation reset variability only; one training seed per method')
    (folder/'comparison.json').write_text(json.dumps(summary,indent=2))
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(9,5),layout='constrained')
        for name,label,color in [('ppo','Existing PPO','#168ca6'),('world_model','World-model adaptation','#d66b34')]:
            r=runs[name];xs=[];ys=[]
            for e in r['evaluations']:
                values=outcomes(e,'perturbed_loco',seeds={481031,481032})
                xs.append(e['training_seconds']/60);ys.append(np.mean([v[0] for v in values.values()])*100)
            ax.plot(xs,ys,'o-',label=label,color=color,linewidth=2)
        ax.set(xlabel='Training time (minutes, including model fitting)',ylabel='Perturbed locomotion failures (%)',
               title='Same checkpoint and reset seeds • real MuJoCo evaluation')
        ax.grid(alpha=.2);ax.legend();ax.set_ylim(bottom=0)
        fig.savefig(folder/'learning-comparison.png',dpi=160)
        plt.close(fig)
    except ImportError:pass
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');summarize(p.parse_args().folder)
