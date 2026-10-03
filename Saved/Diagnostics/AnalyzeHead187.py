import json,pathlib,sys,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics');mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
d=json.loads((p/f'Head187-{mode}-capture.json').read_text());r={x['tick']:x for x in d['rows']};print(d['reason'],len(r));print('bones',list(r[181]['targets']));print('meshes',list(r[181]['meshes']))
def b(t,n,kind='target'):
 if kind=='target':return r[t]['targets'][n]['target']
 if kind=='future':return r[t]['targets'][n]['future']
 return r[t]['meshes'][kind][n]
def v(t,n,kind='target'):return (np.array(b(t,n,kind)['p'])-b(t-2,n,kind)['p'])/2
def rel(t,kind='target'):
 pelvis=b(t,'pelvis',kind);head=b(t,'head',kind)
 return R.from_quat(pelvis['q']).inv().apply(np.array(head['p'])-pelvis['p'])
for t in range(1,max(r)+1):
 if t-1 in r and t in r and r[t]['attack']=='None' and r[t-1]['attack']!='None':print('EXIT',t,r[t-1]['attack'])
for kind in ['target']+list(r[181]['meshes']):
 if 'head' not in (r[181]['targets'] if kind=='target' else r[181]['meshes'][kind]):continue
 print('SOURCE',kind)
 for t in range(170,196,2):
  hv=v(t,'head',kind);pv=v(t,'pelvis',kind);rv=(rel(t,kind)-rel(t-2,kind))/2
  qw=(R.from_quat(b(t,'pelvis',kind)['q'])*R.from_quat(b(t-2,'pelvis',kind)['q']).inv()).as_rotvec()*180/np.pi/2
  print(t,'headV',np.round(hv,3),'speed',round(np.linalg.norm(hv),3),'dV',round(np.linalg.norm(hv-v(t-2,'head',kind)),3),'pelvisV',np.round(pv,3),'pelvisW',np.round(qw,3),'headLocalV',np.round(rv,3),'weights',r[t]['weights'])
print('Upper local angular steps per2 ticks')
chain=['pelvis','spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head']
for t in range(172,194,2):
 vals=[]
 for n,parent in zip(chain[1:],chain):
  q=R.from_quat(b(t,parent)['q']).inv()*R.from_quat(b(t,n)['q']);old=R.from_quat(b(t-2,parent)['q']).inv()*R.from_quat(b(t-2,n)['q'])
  vals.append(round(np.degrees((q*old.inv()).magnitude()),3))
 print(t,vals)
