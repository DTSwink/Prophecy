import sys,pathlib,json,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from CompareRecoveryLegs import load,pose_metrics,direction_angle,rot,OFF,WALK,unit

def inspect(name):
 p,q,m=load(name); exits=[t for t in sorted(m) if t-1 in m and m[t-1]['attack'] and not m[t]['attack']];out={'capture':str(p),'exits':[]}
 for t in exits:
  window=[k for k in sorted(m) if t<=k<min(t+12,max(m)+1)];rec={'tick':t,'time':m[t]['time'],'mode':m[t]['mode'],'attack':m[t-1]['attack'][0],'legs':{}}
  for i,side in enumerate(['l','r']):
   data=[]
   for k in window:
    prev=m[k-1];r=m[k];d={'tick':k}
    for kind in ['future','target','visible','body']:
     pp=lambda rr,b:np.array(rr['bones'][b][kind]['p'])
     d[kind+'_direction_step_deg']=direction_angle(pp(prev,'calf_'+side)-pp(prev,'thigh_'+side),pp(r,'calf_'+side)-pp(r,'thigh_'+side))
     d[kind+'_knee_step_cm']=float(np.linalg.norm(pp(r,'calf_'+side)-pp(prev,'calf_'+side)))
    data.append(d)
   rec['legs'][side]={'frames':data}
  if t in q:
   pipe=q[t];s=np.array(pipe['published_lower']);prev=np.array(pipe['previous_lower']);raw=np.array(pipe['lower_input'][:41])+pipe['lower_delta'][:41]
   rec['weights']={k:pipe[k] for k in ['walk_weight','left_walk_weight','right_walk_weight']}
   for i,side in enumerate(['l','r']):
    o=9+16*i;h=17+4*i;gd={}
    for kind,v in [('previous',prev),('raw',raw),('published',s)]:
     upper=OFF[h+1]@rot(v[o+9:o+15]);hip=v[:3]+OFF[h]@rot(v[3:9]);toe=unit(np.array(WALK['ik_toe_offsets_m'][i]))@rot(v[o+3:o+9]);fwd=unit(toe*[1,1,0]);lateral=np.cross([0,0,1],fwd)
     gd[kind]={'knee_lateral_cm':float(100*upper@lateral),'knee_forward_cm':float(100*upper@fwd),'upper':upper.tolist(),'hip':hip.tolist(),'ankle':v[o:o+3].tolist()}
    gd['raw_direction_step_deg']=direction_angle(gd['previous']['upper'],gd['raw']['upper']);gd['published_direction_step_deg']=direction_angle(gd['previous']['upper'],gd['published']['upper']);rec['legs'][side]['pipeline']=gd
  out['exits'].append(rec)
 return out
if __name__=='__main__':
 reports=[inspect(a) for a in sys.argv[1:]]
 dst=pathlib.Path(__file__).parent/'CaptureComparison.json';dst.write_text(json.dumps(reports,indent=2))
 for report in reports:
  print(pathlib.Path(report['capture']).name)
  for ex in report['exits']:
   print('exit',ex['tick'],ex['attack'],{side:{'first_target_steps':[round(d['target_direction_step_deg'],3) for d in data['frames'][:2]],'raw_step':round(data.get('pipeline',{}).get('raw_direction_step_deg',-1),3),'lateral_before':round(data.get('pipeline',{}).get('previous',{}).get('knee_lateral_cm',-1),3),'lateral_after':round(data.get('pipeline',{}).get('published',{}).get('knee_lateral_cm',-1),3)} for side,data in ex['legs'].items()})
 print(dst)
