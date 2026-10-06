import json,pathlib,math,ast
p=pathlib.Path(__file__).parent
modes=['baseline','motion_off','feedback_off','core_feedback_off','hand_feedback_off']
data={m:json.loads((p/(m+'.json')).read_text()) for m in modes}
raw={m:[json.loads(x) for x in (p/(m+'-nn.jsonl')).read_text().splitlines()] for m in modes}
baseline={(x['tick'],x['actor']):x for x in data['baseline']['rows']}
out={}
for m,d in data.items():
 assert d['reason']=='complete',(m,d['reason'])
 player=[x for x in d['rows'] if x['player']]
 attack=[x for x in player if x['attack'] and x['attack'][0]=='headbutt']
 prefix=0.
 for r in d['rows']:
  if r['tick']>418:continue
  b=baseline[(r['tick'],r['actor'])]
  for bone in r['bones']:
   for stage in ['future','presented','body','target']:
    x=r['bones'][bone][stage];y=b['bones'][bone][stage]
    if x and y:prefix=max(prefix,math.dist(x['p'],y['p']),max(abs(u-v) for u,v in zip(x['q'],y['q'])))
 br=[x for x in raw['baseline'] if x['time']<=418/60+1e-5]
 mr=[x for x in raw[m] if x['time']<=418/60+1e-5]
 assert len(br)==len(mr)
 prefix_nn=max(abs(a-b) for x,y in zip(br,mr) for k in ['input','output'] for a,b in zip(x[k],y[k]))
 first=next(x for x in raw[m] if x['family']=='headbutt')
 first_base=next(x for x in raw['baseline'] if x['family']=='headbutt')
 first_error=max(abs(a-b) for k in ['input','output'] for a,b in zip(first[k],first_base[k]))
 assert prefix==prefix_nn==first_error==0,(m,prefix,prefix_nn,first_error)
 out[m]={'start':attack[0]['tick'],'armed':next(x['tick'] for x in attack if x['attack'][2]),'hit':next(x['tick'] for x in attack if x['attack'][3]),'prefix_pose_max_error':prefix,'prefix_nn_max_error':prefix_nn,'first_headbutt_input_output_max_error':first_error,'head_motion_cm_per_tick':{str(x['tick']):{stage:math.dist(y['bones']['head'][stage]['p'],x['bones']['head'][stage]['p']) for stage in ['future','presented','body']} for y,x in zip(player,player[1:]) if 420<=x['tick']<=446}}
 if m=='motion_off':
  matching=[x for x in raw['baseline'] if x['time']<=470/60+1e-5]
  assert len(matching)==len(raw[m])
  err=max(abs(a-b) for x,y in zip(matching,raw[m]) for k in ['input','output'] for a,b in zip(x[k],y[k]))
  assert err==0
  assert all(r['bones']==baseline[(r['tick'],r['actor'])]['bones'] for r in d['rows'])
  out[m]['whole_capture_native_and_bones_exact']=True
 for r in player:
  if r['tick'] in [420,430,440]:out[m]['report_'+str(r['tick'])]=ast.literal_eval(r['report'])[1]
(p/'analysis.json').write_text(json.dumps(out,indent=2))
print(json.dumps({m:{k:v for k,v in d.items() if k in ['start','armed','hit','prefix_pose_max_error','prefix_nn_max_error','first_headbutt_input_output_max_error','whole_capture_native_and_bones_exact']} for m,d in out.items()},indent=2))
