import json,pathlib,math
p=pathlib.Path(__file__).parent
base=json.loads((p/'blend_0.2.json').read_text())
br={(x['tick'],x['actor']):x for x in base['rows']}
bn=[json.loads(x) for x in (p/'blend_0.2-nn.jsonl').read_text().splitlines()]
out={}
for mode in ['blend_0.2','blend_0.1','blend_0.05']:
 d=json.loads((p/(mode+'.json')).read_text());assert d['reason']=='complete'
 r=[x for x in d['rows'] if x['player']]
 for x in d['rows']:
  if x['tick']<=418:assert x['bones']==br[(x['tick'],x['actor'])]['bones']
 nn=[json.loads(x) for x in (p/(mode+'-nn.jsonl')).read_text().splitlines()]
 prior=[x for x in nn if x['time']<=418/60+1e-5];prior_b=[x for x in bn if x['time']<=418/60+1e-5]
 assert len(prior)==len(prior_b)
 assert all(x[k]==y[k] for x,y in zip(prior,prior_b) for k in ['input','output'])
 first=next(x for x in nn if x['family']=='headbutt');first_b=next(x for x in bn if x['family']=='headbutt')
 assert first['input']==first_b['input'] and first['output']==first_b['output']
 attack=[x for x in r if x['attack'] and x['attack'][0]=='headbutt']
 out[mode]={'prefix_and_first_prediction_exact':True,'start':attack[0]['tick'],'armed':next(x['tick'] for x in attack if x['attack'][2]),'hit':next(x['tick'] for x in attack if x['attack'][3]),'head_cm_per_tick':{str(x['tick']):{stage:math.dist(x['bones']['head'][stage]['p'],y['bones']['head'][stage]['p']) for stage in ['presented','body']} for y,x in zip(r,r[1:]) if 419<=x['tick']<=446}}
(p/'blend-analysis.json').write_text(json.dumps(out,indent=2))
print(json.dumps({m:{k:v for k,v in x.items() if k!='head_cm_per_tick'} for m,x in out.items()},indent=2))
