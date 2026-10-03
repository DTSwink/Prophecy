import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation as R
r=json.loads(pathlib.Path('Saved/Diagnostics/PelvisWide-on-capture.json').read_text())['rows'];r={x['tick']:x for x in r};print('attack',r[350]['attack'],'mode',r[350]['mode'])
for t in range(366,387,2):
 b=r[t]['targets']['pelvis']['target'];a=r[t-2]['targets']['pelvis']['target'];d=(np.array(b['p'])-a['p'])/2;w=(R.from_quat(b['q'])*R.from_quat(a['q']).inv()).as_rotvec()*180/np.pi/2
 print(t,np.round(d,3),np.round(w,3),round(np.linalg.norm(w),3))
