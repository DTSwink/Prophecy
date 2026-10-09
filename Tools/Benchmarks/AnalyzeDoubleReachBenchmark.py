"""Summarize the retained matched-pose reach benchmark; never include smoke runs."""
import json,pathlib,statistics,random,csv,hashlib
p=pathlib.Path(__file__).resolve().parents[2]
folder=p/'Saved/Benchmarks/DoubleReach20261008/final'
methods=['direct','native_animation_bridge','control_rig_anim_node']
rows=[];data=[]
for file in sorted(folder.glob('*_parallel*.json')):
 d=json.loads(file.read_text(encoding='utf-8-sig'))
 assert d['max_position_error_cm']<.001 and d['max_angle_error_deg']<.001
 assert d['pose_adapter'] and d['mesh_bones']==88
 assert d['checked_pose_pairs']>=2*(d['frames_per_repeat']+d['agents']-1)+6*d['agents']
 row={k:d[k] for k in ['agents','workload','parallel','max_position_error_cm','max_angle_error_deg','checked_pose_pairs']}
 for m in methods:
  for stat in ['median_ms','mean_ms','p95_ms']:row[m+'_'+stat]=d[m][stat]
 row['rig_over_direct']=d['control_rig_anim_node']['median_ms']/d['direct']['median_ms']
 row['direct_reduction_percent']=100*(1-d['direct']['median_ms']/d['control_rig_anim_node']['median_ms'])
 diffs=[r['control_rig_anim_node']['mean_ms']-r['direct']['mean_ms'] for r in d['rounds']]
 row['round_mean_saved_ms']=diffs
 rng=random.Random(8102026);boot=sorted(statistics.mean(rng.choices(diffs,k=len(diffs))) for _ in range(10000))
 row['saved_ms_round_bootstrap95']=[boot[250],boot[9749]]
 row['relative_raw_file']=str(file.relative_to(p));rows.append(row);data.append(d)
expected={(n,w,b) for n in [1,10,50,100] for w in ['easy','balls','hard'] for b in [False,True]}
assert {(x['agents'],x['workload'],x['parallel']) for x in rows}==expected,'Suite incomplete'
manifest=json.loads((folder/'manifest.json').read_text())
assert all(x['exit_code']==0 for x in manifest['runs'])
assert manifest['production_source_sha256']==hashlib.sha256((p/'Source/GameAnimationSample3/Private/ProphecyDoubleReachAnimInstance.cpp').read_bytes()).hexdigest()
summary={
 'date':'2026-10-08','cpu':data[0]['cpu'],'logical_cores':data[0]['logical_cores'],
 'build':'Unreal 5.7.4 Development Editor, clean standalone NullRHI process per configuration',
 'scope':'CPU wall time of reaching only, not a gameplay FPS benchmark. Independent agent pose jobs and Control Rig instances, all active; no NN inference, physics, rendering, Blueprint Tick, asset loading, rig construction or animation decompression inside the measured region.',
 'method':'Exact accepted double-reach solver copied by hash into one shared non-inlined C++ function. Direct 26-bone component-space pose path; native animation pose bridge matching the existing proxy; genuine Control Rig Blueprint/RigVM native solve unit through FAnimNode_ControlRigBase on the full 88-bone mesh with UE5.7 pose adapter enabled. An efficient Control Rig implementation, not the different saved 392-node CR_Reach graph.',
 'settings':'Steady Both-hand solve; identical compressed idle inputs sampled at 60Hz and phase-offset per agent; transition/hand/elbow/body smoothing omitted equally to isolate the common solve and transport. Frame0 has the existing idle; targets: easy reachable, reflected moving-ball harness, unreachable asymmetric hard targets.',
 'parallelism':'Serial loops or identical UE ParallelFor dispatch over independent agent state. This measures both frameworks with parallelism, not a multithreaded-versus-single-threaded comparison.',
 'sampling':'30 warm-up batches per method; 240 samples x5 repeats per configuration; ABC/BCA/CAB order rotates each frame. Every unique input and three complete crowd frames checked outside timings; finite transforms, pose error thresholds .001cm/.001deg. Shared immutable bone-container data; mutable RigVM/hierarchy/cache/output per agent.',
 'power':manifest['power_start'],'rows':rows,
 'max_position_error_cm':max(x['max_position_error_cm'] for x in rows),
 'max_angle_error_deg':max(x['max_angle_error_deg'] for x in rows),
 'checked_pose_pairs':sum(x['checked_pose_pairs'] for x in rows),
 'source_sha256':manifest['production_source_sha256'],
 'production_changed':False,
}
dest=p/'Docs/DoubleReachPerformance20261008.json';dest.write_text(json.dumps(summary,indent=2))
with (folder/'summary.csv').open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
lines=['DOUBLE REACH: DIRECT NN POSE VS CONTROL RIG - 8 OCTOBER 2026','',
 'Recommendation: keep this fixed solver native, and use the NN component-space pose buffer directly when integrating it.',
 '', 'Median CPU milliseconds for 100 active agent pose jobs:','',
 'Workload   Execution   Direct     Native pose bridge   Control Rig   Direct saving']
for w in ['easy','balls','hard']:
 for parallel in [False,True]:
  r=next(x for x in rows if x['agents']==100 and x['workload']==w and x['parallel']==parallel)
  lines.append(f"{w:10s} {'parallel' if parallel else 'serial':10s} {r['direct_median_ms']:8.3f} {r['native_animation_bridge_median_ms']:16.3f} {r['control_rig_anim_node_median_ms']:14.3f} {r['direct_reduction_percent']:10.1f}%")
lines+=['',summary['scope'],'',summary['method'],'',summary['settings'],'',summary['parallelism'],'',summary['sampling'],'',
 f"Hardware: {summary['cpu']}; {summary['logical_cores']} logical cores; AC connected={manifest['power_start']['ACLineStatus']==1}.",
 f"Validation: {summary['checked_pose_pairs']} pose pairs; max difference {summary['max_position_error_cm']:.9g} cm / {summary['max_angle_error_deg']:.9g} degrees.",
 'The original double-reach runtime already uses native C++ in an animation proxy. The native-bridge column measures that transport pattern with the common solver, not its complete animation instance with all optional limits enabled.',
 'The Control Rig graph has one native solve unit. This is deliberately favorable to Control Rig; the existing CR_Reach uses different math and was inspected but not ranked against this solver.',
 'Large target distances make the iterative body solve dominate. Moving the same math into a different framework does not remove that cost.',
 'These Development Editor CPU costs do not establish packaged Shipping FPS, GPU cost, collision behavior or a live NN feedback-integration result. No production reaching/NN behavior was changed.',
 '', 'All 1/10/50/100-agent serial and parallel results: Docs/DoubleReachPerformance20261008.json',
 'Raw samples and process logs: Saved/Benchmarks/DoubleReach20261008/final/',
 'Reproduce: Tools/Benchmarks/PrepareDoubleReachBenchmark.py; normal Editor build; Tools/Benchmarks/RunDoubleReachBenchmark.py --tag <new-tag>.',
 'Production source SHA256: '+summary['source_sha256']]
(p/'Docs/DoubleReachPerformance20261008.txt').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines[:14]))
