import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics');root=p.parents[1]
off=np.array(json.loads((root/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())['local_offsets_m'])
def unit(x):return x/max(np.linalg.norm(x),1e-12)
def rot(s,o):
 a=unit(s[o:o+3]);b=unit(s[o+3:o+6]-a*(s[o+3:o+6]@a));return np.array([a,b,np.cross(a,b)])
def error(a,b):return float(np.degrees(R.from_matrix(a@b.T).magnitude()))
def load(tag):
 rows=json.loads((p/(tag+'-capture.json')).read_text())['rows'];actor=rows[0]['actor']
 trace={round(n['time']*60):n for n in map(json.loads,(p/(tag+'-nn.jsonl')).read_text(encoding='utf-8').splitlines()) if n['actor']==actor}
 return {r['clock']:r for r in rows},trace
a,ta=load('KneeHistoricalBaseline');b,tb=load('KneeHistorical11')
prefix=max(np.linalg.norm(np.array(a[t]['targets'][bone]['target']['p'])-b[t]['targets'][bone]['target']['p']) for t in a if t<175 for bone in a[t]['targets'])
print('prefix through174 cm',prefix)
r=ta[175];raw=np.array(r['lower_input'][:41])+r['lower_delta'][:41];target=np.array(r['published_lower']);candidate=np.array(tb[175]['published_lower']);results=[]
print('same NN input175',np.max(np.abs(np.array(r['lower_input'])-tb[175]['lower_input'])))
print('same NN delta175',np.max(np.abs(np.array(r['lower_delta'])-tb[175]['lower_delta'])))
for i in (0,1):
 o=9+16*i;ho=off[17+4*i];ko=off[18+4*i];hip=target[:3]+ho@rot(target,3);ax=unit(target[o:o+3]-hip)
 nativepole=unit(ko@rot(target,o+9)-ax*((ko@rot(target,o+9))@ax))
 def solve(source):
  h=source[:3]+ho@rot(source,3);up=ko@rot(source,o+9);axis=unit(source[o:o+3]-h);pole=unit(up-axis*(up@axis))
  transport=unit(pole-(axis+ax)*(pole@ax)/max(1+axis@ax,1e-6))
  upper=ko@rot(target,o+9);along=upper@ax;radius=np.linalg.norm(upper-ax*along);newup=ax*along+transport*radius
  on=unit(np.cross(axis,pole));nn=unit(np.cross(ax,transport));ob=np.array([unit(up),unit(np.cross(on,unit(up))),on]);nb=np.array([unit(newup),unit(np.cross(nn,unit(newup))),nn])
  return rot(source,o+9)@ob.T@nb
 corrupted=target.copy();corrupted[o+9:o+15]=rot(raw,o+9)[:2].ravel()
 old=solve(corrupted);new=solve(raw)
 rec=dict(side=i,old_replay_error=error(old,rot(target,o+9)),clean_replay_error=error(new,rot(candidate,o+9)),frozen_old_to_clean=error(old,new),ankle_change_cm=float(np.linalg.norm(target[o:o+3]-candidate[o:o+3])*100))
 print(rec);results.append(rec)
(p/'KneeCleanSource-frozen.json').write_text(json.dumps(dict(prefix_cm=prefix,rows=results),indent=2))
