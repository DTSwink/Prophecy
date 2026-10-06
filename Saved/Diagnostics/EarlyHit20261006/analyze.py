import pathlib,json,math
p=pathlib.Path(__file__).parent
out={}
data={m:json.loads((p/(m+'.json')).read_text()) for m in ['baseline','sweeps_off','sweeps_off_late']}
for m,d in data.items():
 assert d['reason']=='complete'
 h=json.loads((p/(m+'-hits.json')).read_text())
 rows=d['rows'];clock={round(r['time'],5):r['tick'] for r in rows}
 events=[dict(x,absolute_tick=clock[round(x['time'],5)]) for x in h['contacts'] if x['not_self'] and x['active'] and x['attack']=='hookL']
 out[m]={'first_hook_contact_absolute_tick':min(x['absolute_tick'] for x in events),'contacts':events,'first_hook_nn_hit_absolute_tick':next(r['tick'] for r in rows if r['player'] and r['attack'] and r['attack'][0]=='hookL' and r['attack'][3])}
base={(r['tick'],r['actor']):r for r in data['baseline']['rows']}
diff=[]
for r in data['sweeps_off']['rows']:
 if r['bones']!=base[(r['tick'],r['actor'])]['bones']:diff.append(r['tick'])
out['first_physical_pose_difference_absolute_tick']=min(diff)
late_differences=[r['tick'] for r in data['sweeps_off_late']['rows'] if r['bones']!=base[(r['tick'],r['actor'])]['bones']]
out['late_control_first_physical_pose_difference_absolute_tick']=min(late_differences)
assert min(late_differences)==47
out['graphs_identical']=(p/'baseline-graph.txt').read_bytes()==(p/'sweeps_off-graph.txt').read_bytes()
assert out['graphs_identical']
out['interpretation']='Predictive PHAT sweep impulses use the same hit bridge as solved contacts. Disabling only sweeps delays first hand/head-neck event 47 to 48. This does not establish an exact baseline shape-touch instant; response differs after the predictive pass. No longer early-event interval reproduced. NN Hit flag is separately at 46.'
(p/'analysis.json').write_text(json.dumps(out,indent=2))
print(json.dumps({m:{k:v for k,v in x.items() if k!='contacts'} if isinstance(x,dict) else x for m,x in out.items()},indent=2))
