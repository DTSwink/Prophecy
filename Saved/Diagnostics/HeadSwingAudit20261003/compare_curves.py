import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).parent
report={}
fig,axs=plt.subplots(4,3,figsize=(16,14),constrained_layout=True)
for row,name in enumerate(('baseline','viewer_F_R_sword_gaze0','viewer_F_L_sword_gaze0','viewer_B_R_sword_gaze0')):
 if name=='baseline':
  a=json.loads((p/(name+'.json')).read_text())['rows'];a=[z for z in a if 195<=z['tick']<=280]
  frames=np.array([z['tick'] for z in a]);fps=60
  head=R.from_quat([z['bones']['head']['presented']['q'] for z in a]);neck=R.from_quat([z['bones']['neck_02']['presented']['q'] for z in a]);pel=R.from_quat([z['bones']['pelvis']['presented']['q'] for z in a])
  local=neck.inv()*head;rel=pel.inv().apply(np.array([z['bones']['head']['presented']['p'] for z in a])-np.array([z['bones']['pelvis']['presented']['p'] for z in a]))
  tr=[z for z in map(json.loads,(p/'baseline-inputs.jsonl').read_text().splitlines()) if z['actor']=='BP_ProphecyManualPoseAgent_C_0']
  tt=np.array([min(a,key=lambda r:abs(r['time']-z['time']))['tick'] for z in tr]);mask=(tt>=196)&(tt<280)
  axs[row,0].plot(tt[mask],np.abs(np.array([z['upper_input'][209] for z in tr])[mask])*24*30,label='root yaw speed')
  target=None
 else:
  z=np.load(p/(name+'.npz'));names=list(z['names']);h=names.index('head');n=names.index('neck_02');b=names.index('pelvis');fps=30
  def locals(pos,rot):
   head=R.from_matrix(rot[:,h].transpose(0,2,1));neck=R.from_matrix(rot[:,n].transpose(0,2,1));pel=R.from_matrix(rot[:,b].transpose(0,2,1))
   return neck.inv()*head,pel.inv().apply(pos[:,h]-pos[:,b])*100
  local,rel=locals(z['positions'],z['rotations']);target,tpos=locals(z['target_positions'],z['target_rotations']);frames=np.arange(len(rel))
  root=R.from_matrix(z['root_rotations'].transpose(0,2,1));rs=np.degrees((root[:-1].inv()*root[1:]).magnitude())*fps
  axs[row,0].plot(frames[1:],rs,label='root yaw speed')
 speed=np.degrees((local[:-1].inv()*local[1:]).magnitude())*fps
 axs[row,1].plot(frames[1:],speed,label='NN / presented')
 axs[row,2].plot(frames[1:],np.linalg.norm(np.diff(rel,axis=0),axis=1)*fps,label='NN / presented')
 if target is not None:
  ts=np.degrees((target[:-1].inv()*target[1:]).magnitude())*fps
  axs[row,1].plot(frames[1:],ts,label='authored')
  axs[row,2].plot(frames[1:],np.linalg.norm(np.diff(tpos,axis=0),axis=1)*fps,label='authored')
  report[name]=dict(root_speed=rs.tolist(),head_speed=speed.tolist(),authored_head_speed=ts.tolist(),last_large_turn_frame=int(np.where(rs>10)[0][-1]+1),peak_generated_after_seed=float(speed[2:].max()),peak_authored_after_seed=float(ts[2:].max()))
 for col in range(3):axs[row,col].set_title(name+'\n'+['Root speed (deg/s)','Head relative neck (deg/s)','Head relative pelvis (cm/s)'][col]);axs[row,col].set_xlabel('game tick' if name=='baseline' else '30 Hz source frame');axs[row,col].grid(alpha=.25);axs[row,col].legend()
fig.savefig(p/'head-curves.png',dpi=145)
(p/'curve-analysis.json').write_text(json.dumps(report,indent=2))
for k,z in report.items():print(k,'last root >10deg/s',z['last_large_turn_frame'],'peaks',z['peak_generated_after_seed'],z['peak_authored_after_seed'])
