from pathlib import Path
import json,sys,math,numpy as np
tag=sys.argv[1] if len(sys.argv)>1 else 'before'
d=json.loads(Path('Saved/Diagnostics/ArmReach/'+tag+'.json').read_text());print('CAPTURE',d['reason'],d['owned'])
rows=d['rows'];by={r['tick']:r for r in rows}
def bend(p):
 a,b,c=p;u=b-a;v=c-b
 return math.degrees(math.acos(np.clip(u@v/(np.linalg.norm(u)*np.linalg.norm(v)),-1,1)))
last=None
for r in rows:
 a=r['attack'].split(',')[0]
 if a!=last:print('ATTACK',r['tick'],a);last=a
for arm in ['l','r']:
 vals=[]
 for r in rows:
  if r['attack']!='None':continue
  p=np.array([r['pose'][n+'_'+arm]['future']['p'] for n in ['upperarm','lowerarm','hand']]);vals.append((r['tick'],bend(p)))
 print('STRAIGHTEST',arm,sorted(vals,key=lambda v:v[1])[:12])
# Paired per-arm audit rows: left then right for a shared elapsed timestamp.
lines=Path('Saved/Diagnostics/ArmReach/'+tag+'.log').read_text(errors='replace').splitlines()
groups={}
for line in lines:
 if 'SlashElbowAudit,' not in line:continue
 v=line.split('SlashElbowAudit,')[1].split(',');k=(v[0],float(v[1]));groups.setdefault(k,[]).append(v)
name=rows[0]['actor']
for key,arms in groups.items():
 if key[0]!=name:continue
 v=arms[0];elapsed=float(v[1])
 if len(arms)<2 or elapsed>.55:continue
 # header actor,time,alpha,turn; upper3,pole3; prev S/E/H7 each, neutral S/E/H7 each, final E/H3
 ns=np.array(v[31:34],float);ne=np.array(v[38:41],float);nh=np.array(v[45:48],float)
 print('NEUTRAL_LEFT',round(elapsed,3),'bend',round(bend([ns,ne,nh]),2),'reach',round(np.linalg.norm(nh-ns),2),'positions',ns.round(2),ne.round(2),nh.round(2))
