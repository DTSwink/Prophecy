import json,pathlib,sys,numpy as np
from scipy.spatial.transform import Rotation
p=pathlib.Path('Saved/Diagnostics')
def load(tag):
 rows=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())['rows'];name=next((r['actor'] for r in rows if r.get('possessed')),None) or 'BP_ProphecyManualPoseAgent_C_1';return [r for r in rows if r['actor']==name]
def metrics(rows):
 out=[]
 for j in range(2,len(rows)):
  r=rows[j];prev=rows[j-1];pp=rows[j-2]
  if r['attack']!='None' or prev['attack']!='None' or pp['attack']!='None':continue
  def xyz(rr,b):return np.array(rr['targets'][b]['target']['p'])
  def qa(b):return float(np.degrees((Rotation.from_quat(r['targets'][b]['target']['q'])*Rotation.from_quat(prev['targets'][b]['target']['q']).inv()).magnitude()))
  v=xyz(r,'pelvis')-xyz(prev,'pelvis');a=v-(xyz(prev,'pelvis')-xyz(pp,'pelvis'));q={'frame':round(r['t']*60),'v':v.tolist(),'a':a.tolist(),'pelvis_accel':float(np.linalg.norm(a))}
  for side in ['l','r']:
   h,k,f=[xyz(r,b+'_'+side) for b in ['thigh','calf','foot']];axis=f-h;axis/=np.linalg.norm(axis);u=k-h;rad=u-axis*np.dot(u,axis)
   toe=xyz(r,'ball_'+side)-f;toe[2]=0;toe/=max(np.linalg.norm(toe),1e-8);lat=np.cross([0,0,1],toe);normal=lat-axis*np.dot(lat,axis);normal/=max(np.linalg.norm(normal),1e-8);forward=np.cross(axis,normal)
   q[side]={'thigh_step':qa('thigh_'+side),'calf_step':qa('calf_'+side),'knee_step':float(np.linalg.norm(k-xyz(prev,'calf_'+side))), 'pole_forward':float(np.dot(rad/max(np.linalg.norm(rad),1e-8),forward)), 'radius':float(np.linalg.norm(rad)),'knee_side':float(np.dot(u,lat)), 'foot_z':float(f[2]),'bend':float(np.degrees(np.arccos(np.clip(np.dot(u,f-k)/np.linalg.norm(u)/np.linalg.norm(f-k),-1,1))))}
  out.append(q)
 summaries={}
 exits=[round(rows[i]['t']*60) for i in range(1,len(rows)) if rows[i-1]['attack']!='None' and rows[i]['attack']=='None']
 for name,selected in [('all',out)]+[(str(f),[r for r in out if f<=r['frame']<f+60]) for f in exits]:
  if not selected:continue
  summaries[name]={'samples':len(selected),'pelvis_accel_max':max(r['pelvis_accel'] for r in selected),'pelvis_z_accel_max':max(abs(r['a'][2]) for r in selected)}
  for side in ['l','r']:
   ss=[r[side] for r in selected];summaries[name][side]={k:max(abs(r[k]) for r in ss) for k in ['thigh_step','calf_step','knee_step','knee_side']};summaries[name][side]['backward']=sum(r['pole_forward']<0 and r['radius']>1 for r in ss)
 return {'summary':summaries,'rows':out}
for tag in sys.argv[1:]:
 rows=load(tag);r=metrics(rows);(p/('Unified159-metrics-'+tag+'.json')).write_text(json.dumps(r,indent=2));print(tag,json.dumps(r['summary']))
 for x in r['rows']:
  if x['frame'] in [155,157,159,161,163]:print(x['frame'],'pelvis',np.round(x['v'],3),'left thigh',round(x['l']['thigh_step'],3),'right thigh',round(x['r']['thigh_step'],3))
