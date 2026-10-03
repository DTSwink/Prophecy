import json,pathlib,math
p=pathlib.Path(__file__).parent
def read(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error']
 return {r['tick']:r for r in d['rows'] if r['player']}
off=read('fixed_feedback')
out={}
for tag in ['twist_reenabled_before','twist_isolated_after','twist_isolated_final']:
 if not (p/(tag+'.json')).exists():continue
 rows=read(tag)
 result={}
 for region,lo,hi in [('pre_exit',1,182),('recovery',183,280),('after',281,350)]:
  values=[(math.dist(r[phase][bone]['p'],off[t][phase][bone]['p']),t,bone,phase) for t,r in rows.items() if lo<=t<=hi for phase in ['future','presented'] for bone in ['upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r']]
  result[region+'_max_cm']=max(values)
 result['samples_hand_position_error_cm']={t:[round(math.dist(rows[t]['future'][h]['p'],off[t]['future'][h]['p']),7) for h in ['hand_l','hand_r']] for t in [183,195,210,230,240,260,280]}
 result['max_wrist_rotation_difference_degrees']=max(math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(r['future'][h]['q'],off[t]['future'][h]['q'])))))) for t,r in rows.items() if 183<=t<=280 for h in ['hand_l','hand_r'])
 out[tag]=result
print(json.dumps(out,indent=2));(p/'twist_analysis.json').write_text(json.dumps(out,indent=2))
