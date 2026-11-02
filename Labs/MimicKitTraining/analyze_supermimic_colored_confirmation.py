"""Actual simulator learning curves, separately by independent training seed."""
import argparse
import json
import re
from pathlib import Path
import numpy as np
from analyze_supermimic_pilots import paired,GROUPS


def rate(evaluation,group=2):
    rows=[f for r in evaluation['rows'] for g,f in zip(r['row_group'],r['row_failed']) if g==group]
    return 100*float(np.mean(rows))


def curve(report,mode='noisy'):
    points=[(0.,rate(report['initial'][mode]))]
    points.extend((ev['training_seconds'],rate(ev[mode])) for ev in report['evaluations'])
    points.append((report['learning_seconds_excluding_checks'],rate(report['final'][mode])))
    return np.array(sorted(points),dtype=float)


def compare_curves(first,second):
    end=min(first[-1,0],second[-1,0]);assert end>0
    times=np.unique(np.r_[0.,first[:,0],second[:,0],end]);times=times[times<=end]
    a=np.interp(times,first[:,0],first[:,1]);b=np.interp(times,second[:,0],second[:,1])
    delta=b-a;adjusted=delta-(second[0,1]-first[0,1])
    integrate=getattr(np,'trapezoid',None) or np.trapz
    return dict(common_learning_seconds=float(end),times=times.tolist(),white_failure=a.tolist(),colored_failure=b.tolist(),
                mean_failure_difference_pp=float(integrate(delta,times)/end),
                mean_start_adjusted_difference_pp=float(integrate(adjusted,times)/end),
                interpolation='Piecewise linear over measured checks; no smoothing or missing values treated as zeros')


def elapsed_curve(events,label,initial_failure):
    """Measurements when available, including setup and evaluation overhead."""
    starts=[e['time'] for e in events if re.search(r'\bWORKER_STARTED '+re.escape(label)+r'\s+gpu\s+\d+',e.get('data',''))]
    assert len(starts)==1,(label,'ambiguous worker start')
    origin=float(starts[0]);points=[(0.,initial_failure)];baseline=0;complete=0
    pattern=re.compile(r'\['+re.escape(label)+r'\] (STUDENT_BASELINE|STUDENT_CHECK|STUDENT_COMPLETE) (\{[^\n]+\})')
    for event in events:
        for match in pattern.finditer(event.get('data','')):
            marker,raw=match.groups();item=json.loads(raw)
            if marker=='STUDENT_BASELINE':
                baseline+=1;assert abs(item['noisy']-initial_failure)<1e-8
            if marker=='STUDENT_COMPLETE':complete+=1
            points.append((float(event['time'])-origin,float(item['noisy'])))
    assert baseline==1 and complete==1,(label,baseline,complete)
    points=np.array(sorted(points),dtype=float)
    assert np.all(np.diff(points[:,0])>0)
    return points


def plot_curves(result,folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=list(result['seeds'].items());fig,axes=plt.subplots(len(rows),2,figsize=(11,3.6*len(rows)),squeeze=False)
    for i,(seed,item) in enumerate(rows):
        for j,key in enumerate(['noisy_learning_curve','noisy_elapsed_curve']):
            ax=axes[i,j]
            if key not in item:ax.set_visible(False);continue
            c=item[key];t=np.array(c['times'])/60
            ax.plot(t,c['white_failure'],label='Current PPO',color='#3b566e',lw=2)
            ax.plot(t,c['colored_failure'],label='Correlated exploration',color='#d87825',lw=2)
            ax.set(title=f'Training seed {seed}',xlabel='Learning minutes' if j==0 else 'Worker minutes, including setup/checks',ylabel='Perturbed locomotion failure (%)')
            ax.grid(alpha=.25);ax.legend(frameon=False)
    fig.suptitle('Real MuJoCo evaluation with original exploration · lower is better')
    fig.tight_layout();fig.savefig(folder/'learning-comparison.png',dpi=160);plt.close(fig)


def analyze(folder,live_log=None,plot=False):
    folder=Path(folder);manifest=json.loads((folder/'confirmation.json').read_text());assert manifest['complete']
    result=dict(kind='verified_colored_ppo_confirmation',seeds={},pooled={},
        limitation='Two independent training seeds planned; report each. Motion-cluster intervals describe evaluation variation, not a precise estimate of training-seed variation. No cross-framework or SuperMimic speed claim.')
    pooled={a:{m:{'rows':[]} for m in ['noisy','deterministic']} for a in ['white','colored']}
    events=None
    if live_log is not None:
        import hashlib
        live_bytes=Path(live_log).read_bytes();events=json.loads(live_bytes)
        result['elapsed_timing_source']=dict(path=str(live_log),sha256=hashlib.sha256(live_bytes).hexdigest(),
            meaning='Per-worker wall clock from actual WORKER_STARTED to measurements becoming available. Includes environment setup, initial checks, intermediate and final evaluations, saving. Common notebook bootstrap listed separately; no learned model preparation reused. Initial checkpoint unchanged during setup. Lines interpolate measured outcomes, not individual updates.')
        first_worker=min(float(e['time']) for e in events if e.get('data','').startswith('WORKER_STARTED '))
        bootstrap=min(float(e['time']) for e in events if 'BOOTSTRAP_STARTED' in e.get('data',''))
        result['elapsed_timing_source']['common_bootstrap_seconds_before_first_worker']=first_worker-bootstrap
    passes=[];curve_differences=[];failure_differences=[];complete_count=0
    for stage in manifest['stages']:
        seed=stage['seed'];runs={a:json.loads((folder/(a+'_'+str(seed))/'result.json').read_text()) for a in ['white','colored']}
        assert len({r['checkpoint_sha256'] for r in runs.values()})==1
        item={'arms':{},'comparison':{}}
        for name,r in runs.items():
            assert r['complete'] and r['training_seed']==seed and r['accepted_actor_updates']>0 and r['actor_parameter_delta_l2']>0
            n=r['noise_audit'];assert n['calls']==32*r['accepted_actor_updates'] and .95<n['rms']<1.05
            assert n['beta']==(0 if name=='white' else .5)
            assert (abs(n['lag1_product'])<.02) if name=='white' else (n['lag1_product']>.2)
            assert r['evaluation_preserves_training_rng']
            item['arms'][name]={k:r[k] for k in ['accepted_actor_updates','actor_parameter_delta_l2','critic_parameter_delta_l2','learning_seconds_excluding_checks','intermediate_evaluation_seconds','setup_and_baseline_seconds','final_evaluation_seconds','total_worker_seconds','stop_reason','noise_audit']}
            item['arms'][name]['start_to_final']={m:paired(r['initial'][m],r['final'][m],'perturbed_loco') for m in pooled[name]}
            for mode in pooled[name]:pooled[name][mode]['rows']+=r['final'][mode]['rows']
        for mode in ['noisy','deterministic']:
            item['comparison'][mode]={g:paired(runs['white']['final'][mode],runs['colored']['final'][mode],g) for g in GROUPS}
        item['noisy_learning_curve']=compare_curves(curve(runs['white']),curve(runs['colored']))
        if events is not None:
            elapsed={a:elapsed_curve(events,a+'_'+str(seed),rate(runs[a]['initial']['noisy'])) for a in runs}
            item['noisy_elapsed_curve']=compare_curves(elapsed['white'],elapsed['colored'])
            item['noisy_elapsed_curve']['common_elapsed_seconds']=item['noisy_elapsed_curve'].pop('common_learning_seconds')
            item['noisy_elapsed_curve']['worker_start_times_note']='Each seed pair starts concurrently; second seed reuses compilation caches. Report seed pairs separately.'
        full=all(not r['stop_reason'] and r['learning_seconds_excluding_checks']>=900 for r in runs.values())
        matched=abs(runs['white']['learning_seconds_excluding_checks']-runs['colored']['learning_seconds_excluding_checks'])<=5
        item.update(completed_full_budget=full,matched_learning_time=matched)
        noisy=item['comparison']['noisy'];det=item['comparison']['deterministic']
        failure_differences.append(noisy['perturbed_loco']['failure_change_percentage_points'])
        curve_differences.append(item['noisy_learning_curve']['mean_start_adjusted_difference_pp'])
        passes.append(full and matched and failure_differences[-1]<=0
            and item['arms']['colored']['start_to_final']['noisy']['failure_change_percentage_points']<0
            and det['perturbed_loco']['failure_change_percentage_points']<=1
            and all(m['normal_loco']['failure_change_percentage_points']<=1 for m in [noisy,det]))
        complete_count+=int(full);result['seeds'][str(seed)]=item
    for mode in ['noisy','deterministic']:
        result['pooled'][mode]={g:paired(pooled['white'][mode],pooled['colored'][mode],g) for g in GROUPS}
    result['promising_faster_learning']=bool(complete_count==2 and all(passes) and np.mean(failure_differences)<=-1
        and np.mean(curve_differences)<0
        and result['pooled']['noisy']['perturbed_loco']['return_change_motion_cluster_interval_95'][0]>0)
    result['completed_training_seed_pairs']=complete_count
    if events is not None:
        result['mean_elapsed_failure_difference_pp']=float(np.mean([s['noisy_elapsed_curve']['mean_failure_difference_pp'] for s in result['seeds'].values()]))
        result['mean_elapsed_start_adjusted_difference_pp']=float(np.mean([s['noisy_elapsed_curve']['mean_start_adjusted_difference_pp'] for s in result['seeds'].values()]))
        result['elapsed_curves_favor_candidate']=result['mean_elapsed_start_adjusted_difference_pp']<0
    (folder/'verified-confirmation.json').write_text(json.dumps(result,indent=2))
    if plot:plot_curves(result,folder)
    print(json.dumps({k:v for k,v in result.items() if k!='seeds'},indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('--live-log');p.add_argument('--plot',action='store_true')
    args=p.parse_args();analyze(args.folder,args.live_log,args.plot)
