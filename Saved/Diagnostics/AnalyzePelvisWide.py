import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics')
def load(mode):
 d=json.loads((p/f'PelvisWide-{mode}-capture.json').read_text());print(mode,d['reason'],len(d['rows']));return {x['tick']:x for x in d['rows']}
def series(rows,start,end,source='target'):
 ts=[t for t in sorted(rows) if start<=t<=end and t%2==0]
 def bone(x):return x['targets']['pelvis']['target'] if source=='target' else x['meshes'][source]['pelvis']
 pp=np.array([bone(rows[t])['p'] for t in ts]);qq=R.from_quat([bone(rows[t])['q'] for t in ts]);v=np.diff(pp,axis=0)/2
 w=(qq[1:]*qq[:-1].inv()).as_rotvec()*180/np.pi/2
 return np.array(ts[1:]),v,w
def summary(rows,start,end):
 t,v,w=series(rows,start,end);a=np.diff(v,axis=0);aw=np.diff(w,axis=0)
 return {'horizontal_velocity_change_peak_cm_per_tick':float(max(np.linalg.norm(a[:,:2],axis=1))),'vertical_velocity_change_peak_cm_per_tick':float(max(abs(a[:,2]))),'angular_velocity_change_peak_deg_per_tick':float(max(np.linalg.norm(aw,axis=1))),'horizontal_velocity_change_rms':float(np.sqrt(np.mean(np.sum(a[:,:2]**2,axis=1)))),'angular_velocity_change_rms':float(np.sqrt(np.mean(np.sum(aw**2,axis=1)))),'angular_speed_peak':float(max(np.linalg.norm(w,axis=1)))}
on=load('on');off=load('off320');modes={'on':on,'off320':off}
if (p/'PelvisWide-offearly-capture.json').exists():modes['offearly']=load('offearly')
print('Prefix max authored position discrepancy through320',max(np.linalg.norm(np.array(on[t]['targets'][b]['target']['p'])-off[t]['targets'][b]['target']['p']) for t in on if t<=320 for b in on[t]['targets']))
report={}
for mode,r in modes.items():
 report[mode]={}
 for start,end in ((324,386),(350,386),(368,386),(146,206)):
  s=summary(r,start,end);report[mode][f'{start}-{end}']=s;print(mode,start,end,s)
 t,v,w=series(r,350,386)
 print('tick horizontal vertical rotvector xyz, speed')
 for ti,vi,wi in zip(t,v,w):print(mode,ti,*np.round([np.linalg.norm(vi[:2]),vi[2],*wi,np.linalg.norm(wi)],4))
(p/'PelvisWide-summary.json').write_text(json.dumps(report,indent=2))
