import sys,pathlib,json,numpy as np
from scipy.spatial.transform import Rotation
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from CompareRecoveryLegs import load,pose_metrics,direction_angle,rot,OFF,WALK,unit,angle

def maxi(vals):
 return {'value':max(vals,key=lambda x:x[1])[1],'tick':max(vals,key=lambda x:x[1])[0]} if vals else None

def metrics(m,start,end,side):
 out={'direction':[],'rotation':[],'knee_step':[],'knee_accel':[],'foot_step':[],'foot_accel':[],'thigh_length_error':[],'calf_length_error':[]}
 hip='thigh_'+side;knee='calf_'+side;foot='foot_'+side;h=17 if side=='l' else 21
 length1=np.linalg.norm(OFF[h+1])*100;length2=np.linalg.norm(OFF[h+2])*100
 p=lambda t,b:np.array(m[t]['bones'][b]['target']['p'])
 for t in range(start,end+1):
  if t not in m or t-1 not in m:continue
  d=direction_angle(p(t-1,knee)-p(t-1,hip),p(t,knee)-p(t,hip));qs=Rotation.from_quat([m[k]['bones'][hip]['target']['q'] for k in [t-1,t]])
  out['direction'].append((t,d));out['rotation'].append((t,float(np.degrees((qs[1]*qs[0].inv()).magnitude()))))
  out['knee_step'].append((t,float(np.linalg.norm(p(t,knee)-p(t-1,knee)))));out['foot_step'].append((t,float(np.linalg.norm(p(t,foot)-p(t-1,foot)))))
  if t-2 in m:
   out['knee_accel'].append((t,float(np.linalg.norm(p(t,knee)-2*p(t-1,knee)+p(t-2,knee)))))
   out['foot_accel'].append((t,float(np.linalg.norm(p(t,foot)-2*p(t-1,foot)+p(t-2,foot)))))
  out['thigh_length_error'].append((t,float(abs(np.linalg.norm(p(t,knee)-p(t,hip))-length1))))
  out['calf_length_error'].append((t,float(abs(np.linalg.norm(p(t,foot)-p(t,knee))-length2))))
 return {k:maxi(v) for k,v in out.items()}

def report(name):
 p,q,m=load(name);exits=[t for t in sorted(m) if t-1 in m and m[t-1]['attack'] and not m[t]['attack']];ans={'name':p.name,'exits':[]}
 for ex in exits:
  nextattack=next((t for t in sorted(m) if t>ex and m[t]['attack']),max(m)+1)
  retire=next((t for t in sorted(q) if ex<=t<nextattack and not q[t].get('tempering')),None)
  r={'tick':ex,'retire':retire,'end':nextattack-1,'legs':{}}
  for i,side in enumerate(['l','r']):
   activeend=(retire or nextattack)-1;pm=pose_metrics(q,ex,activeend);rows=[x['legs'][['left','right'][i]] for x in pm]
   # Branch score only meaningful when knee has appreciable bend radius.
   signs=[];errors=[];sidecm=[];positions=[]
   for t in sorted(q):
    if not ex<=t<=activeend:continue
    a=np.array(q[t]['published_lower']);o=9+i*16;h=17+i*4;hip=a[:3]+OFF[h]@rot(a[3:9]);upper=OFF[h+1]@rot(a[o+9:o+15]);axis=unit(a[o:o+3]-hip);radial=upper-axis*(axis@upper);toe=unit(np.array(WALK['ik_toe_offsets_m'][i]))@rot(a[o+3:o+9]);forward=unit(toe*[1,1,0]);sideaxis=np.cross([0,0,1],forward);n=unit(sideaxis-axis*(sideaxis@axis));hinge=unit(np.cross(axis,n));score=float(unit(radial)@hinge)
    if np.linalg.norm(radial)>.02:signs.append((t,score))
    errors.append((t,float(abs(np.linalg.norm(a[o:o+3]-hip-upper)-np.linalg.norm(OFF[h+2]))*100)));sidecm.append(float(upper@sideaxis*100));positions.append({'tick':t,'foot_from_hip_cm':((a[o:o+3]-hip)*100).tolist(),'knee_from_hip_cm':(upper*100).tolist(),'branch_score':score,'bend_radius_cm':float(np.linalg.norm(radial)*100)})
   r['legs'][side]={'initial':metrics(m,ex,ex+1,side),'active':metrics(m,ex,activeend,side),'full':metrics(m,ex,nextattack-1,side),'retirement':metrics(m,retire-2,min(retire+4,nextattack-1),side) if retire else None,
      'minimum_bent_branch_score':min([v for t,v in signs],default=None),'negative_bent_branch_frames':[t for t,v in signs if v<0],
      'max_active_calf_error_cm':maxi(errors),'knee_side_range_cm':[min(sidecm),max(sidecm)] if sidecm else None,'positions':positions}
  ans['exits'].append(r)
 return ans
if __name__=='__main__':
 all=[report(a) for a in sys.argv[1:]];outfile=pathlib.Path(__file__).parent/'FullRecoveryComparison.json';outfile.write_text(json.dumps(all,indent=2))
 for a in all:
  print(a['name'])
  for ex in a['exits']:
   print('EXIT',ex['tick'],'retire',ex['retire'],'end',ex['end'])
   for side,l in ex['legs'].items():
    print(side,'active dir/rot',l['active']['direction'],l['active']['rotation'],'full dir/rot',l['full']['direction'],l['full']['rotation'],'retire',l['retirement']['direction'] if l['retirement'] else None,'branch',l['minimum_bent_branch_score'],'neg',l['negative_bent_branch_frames'],'lengtherr',l['max_active_calf_error_cm'])
 print(outfile)
