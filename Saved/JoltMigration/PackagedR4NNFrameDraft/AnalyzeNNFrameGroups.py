"""Read-only timing diagnosis: retain every row, classify by actual counter deltas."""
import collections, hashlib, json, math, pathlib, statistics
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCES = {
    'packaged_r4': ROOT/'Saved/JoltMigration/NNCrowd-20260909-144331-647/Runs/Development-C100-20260909-183617-557/benchmark.json',
    'editor_proxy': ROOT/'Saved/Benchmarks/nn_jolt_proxy_traversal_100_20260909_2019.json',
    'editor_feedback_original': ROOT/'Saved/Benchmarks/nn_jolt_feedback_original_100_20260909_1641.json',
}
TIMERS = ('build_seconds','inference_seconds','output_seconds','store_seconds')
def corr(xs, ys):
    if len(xs)<2 or min(statistics.pvariance(xs),statistics.pvariance(ys))==0: return None
    return statistics.correlation(xs,ys)
def stats(xs):
    ys=sorted(xs); n=len(xs)
    return dict(n=n,mean=statistics.fmean(xs),median=statistics.median(xs),upper_median=ys[n//2],p95=ys[int(n*.95)],min=min(xs),max=max(xs),over10=sum(v>10 for v in xs))
result={'scope':'Separate historical sessions and binaries, observational associations only. R4 diagnostic export and callback restoration defects remain historical limitations. No rows excluded, no timing claims about unmeasured R5.', 'runs':{}}
for label,path in SOURCES.items():
    raw=path.read_bytes(); d=json.loads(raw); p=d['passes'][0]; rows=p['multi_jolt_frames']; previous=p['before']['actual_nn_initial']; flat=[]
    for index,(r,world) in enumerate(zip(rows,p['world_ms'])):
        current=r['actual_nn']; step=current['completed_nn_steps']-previous['completed_nn_steps']; samples=current['completed_physical_samples']-previous['completed_physical_samples']
        assert step in (0,1) and samples==100*step
        timers={k.removesuffix('_seconds'):1000*(current[k]-previous[k]) for k in TIMERS}
        assert all(math.isfinite(v) and v>=-1e-9 for v in timers.values())
        if not step: assert all(abs(v)<1e-9 for v in timers.values())
        phase=dict(r['character_cpu_ms']); calls=r['character_cpu_calls']
        assert calls['manager_pose_publish']==100*step and calls['manager_physical_resample']==step and calls['physical_sample_read']==100*step and calls['physical_raw_encode']==200*step
        phase.update({'nn_'+k:v for k,v in timers.items()})
        phase['nn_build_excluding_resample']=timers['build']-phase['manager_physical_resample']
        phase['nn_store_outside_pose_publish']=timers['store']-phase['manager_pose_publish']
        phase['manager_other']=phase['manager_tick_total']-phase['manager_visual_roots']-sum(timers.values())
        phase['world_other']=world-phase['manager_tick_total']-phase['agent_tick_total']-phase['coordinator_total']
        phase['world']=world
        for key,value in r['jolt']['step_parts_ms'].items(): phase['native_'+key]=value
        flat.append({'frame':index,'step':step,'ms':phase,'processor_begin':r['processor_provenance']['begin'],'processor_end':r['processor_provenance']['end']})
        previous=current
    assert len(flat)==360 and sum(v['step'] for v in flat)==180
    groups={}
    for step in (0,1):
        group=[r for r in flat if r['step']==step]; world=[r['ms']['world'] for r in group]
        groups['nn' if step else 'interstitial']={'world':stats(world),'mean_ms':{k:statistics.fmean(r['ms'][k] for r in group) for k in group[0]['ms']},'world_correlations':{k:corr(world,[r['ms'][k] for r in group]) for k in group[0]['ms']},'phase_stats':{k:stats([r['ms'][k] for r in group]) for k in group[0]['ms']}}
    delta={k:groups['nn']['mean_ms'][k]-groups['interstitial']['mean_ms'][k] for k in groups['nn']['mean_ms']}
    result['runs'][label]={'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'world':stats([r['ms']['world'] for r in flat]),'nn_step_world_correlation':corr([r['step'] for r in flat],[r['ms']['world'] for r in flat]),'groups':groups,'nn_minus_interstitial_mean_ms':delta,'nn_step_pattern_first12':[r['step'] for r in flat[:12]],'rows':flat}
(HERE/'NNFrameGroups.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
keys=['world','manager_tick_total','nn_inference','manager_physical_resample','nn_build_excluding_resample','nn_output','nn_store','manager_visual_roots','manager_other','agent_tick_total','coordinator_total','native_step_total','compose_batch_wall','refresh_bones','query_update','world_other']
for label,run in result['runs'].items():
    print(label,run['world'],'step_corr',run['nn_step_world_correlation'])
    print('group',*(f'{k}={run["groups"][k]["world"]}' for k in ('interstitial','nn')))
    for k in keys:
        print(k,*[round(run['groups'][g]['mean_ms'][k],6) for g in ('interstitial','nn')],round(run['nn_minus_interstitial_mean_ms'][k],6))
