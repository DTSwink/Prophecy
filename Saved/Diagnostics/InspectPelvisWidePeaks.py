import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics')
for mode in ('on','off320','offearly'):
 r={x['tick']:x for x in json.loads((p/f'PelvisWide-{mode}-capture.json').read_text())['rows']}
 for src in ('target','PhysicalMesh'):
  ts=list(range(350,388,2));b=[r[t]['targets']['pelvis']['target'] if src=='target' else r[t]['meshes'][src]['pelvis'] for t in ts]
  pos=np.array([x['p'] for x in b]);q=R.from_quat([x['q'] for x in b]);v=np.diff(pos,axis=0)/2;w=(q[1:]*q[:-1].inv()).as_rotvec()*180/np.pi/2
  da=np.linalg.norm(np.diff(v[:,:2],axis=0),axis=1);dw=np.linalg.norm(np.diff(w,axis=0),axis=1)
  print(mode,src,'xy peak',round(max(da),4),'at',ts[np.argmax(da)+2],'rot peak',round(max(dw),4),'at',ts[np.argmax(dw)+2])
 print(mode,'yaw per tick 370-382',[(t,round(float((R.from_quat(r[t]['targets']['pelvis']['target']['q'])*R.from_quat(r[t-2]['targets']['pelvis']['target']['q']).inv()).as_rotvec()[2]*180/np.pi/2),3)) for t in range(370,384,2)])
