import json,pathlib,sys,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent));from ReplayOverLSolver import *

def wrap(a):return np.arctan2(np.sin(a),np.cos(a))
def error(s,i,policy):
 o=9+16*i;h=17+4*i;hip=s[:3]+OFF[h]@rot(s[3:9]);axis=unit(s[o:o+3]-hip);upper=OFF[h+1]@rot(s[o+9:o+15]);along=upper@axis;radial=upper-axis*along;radius=np.linalg.norm(radial);pole=unit(radial);toe=unit(np.array(policy['ik_toe_offsets_m'][i]))@rot(s[o+3:o+9]);flat=toe*[1,1,0];forward=unit(flat);side=np.cross([0,0,1],forward);na=side-axis*(side@axis);nlen=np.linalg.norm(na);n=unit(na);hinge=unit(np.cross(axis,n));Q=-along*(axis@side)/max(1e-12,radius*nlen);strength=smooth(flat@flat*4)*smooth(nlen*nlen*4)*smooth((1-abs(Q))*4);des=n*np.clip(Q,-1,1)+hinge*np.sqrt(max(0,1-np.clip(Q,-1,1)**2));e=np.arctan2(axis@np.cross(pole,des),np.clip(pole@des,-1,1));return e,strength

def evalcap(name):
 rows=[json.loads(x) for x in (ROOT/'Saved/Diagnostics'/name/'pipeline.jsonl').read_text().splitlines()];out=[]
 for r in rows:
  if not r['actor'].endswith('_C_1') or r['attack'] or 'tempering' not in r:continue
  t=round(r['time']*60);rec={'tick':t,'legs':{}}
  for i,side in enumerate(['left','right']):
   st=solve_record(r,i);raw,policy=policy_source(r,i);prev=np.array(r['previous_lower']);o=9+16*i;ep,cp=error(prev,i,policy);en,cn=error(raw,i,policy);follow=st['source_follow']*r['tempering'][1];source=ep+wrap(en-ep)*follow;target=np.deg2rad(st['guidance_full_turn_deg']);correction=wrap(target-source)*st['strength'];r0=np.array(st['transported_rotation']);candidate=r0@axis_angle(np.array(st['axis']),correction);old=rot(np.array(r['published_lower'])[o+9:o+15]);previous=rot(prev[o+9:o+15]);rec['legs'][side]={'previous_guide_deg':float(np.degrees(ep)),'previous_confidence':cp,'raw_guide_deg':float(np.degrees(en)),'raw_confidence':cn,'mixed_guide_deg':float(np.degrees(source)),'new_guide_deg':float(np.degrees(correction)),'old_step':angle(previous,old),'new_step':angle(previous,candidate),'pose_difference':angle(old,candidate),'old_replay_error':st['replay_error_deg']}
  out.append(rec)
 return out
if __name__=='__main__':
 result={n:evalcap(n) for n in sys.argv[1:]};(pathlib.Path(__file__).parent/'angular-residual-counterfactual.json').write_text(json.dumps(result,indent=2))
 for n,rows in result.items():
  print(n)
  for r in rows[:8]:print(r['tick'],{s:{k:round(v,3) for k,v in d.items()} for s,d in r['legs'].items()})
