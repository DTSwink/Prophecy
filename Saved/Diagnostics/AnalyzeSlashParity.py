import json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

label=sys.argv[1] if len(sys.argv)>1 else 'seeded'
base=Path('Saved/Diagnostics')
rows=[json.loads(x) for x in (base/f'SlashTrainParity-{label}-nn.jsonl').read_text().splitlines()]
fixture=json.loads(Path('Tools/NN/Fixtures/SlashTrain2026092223.json').read_text())
oracle=json.loads(Path('Saved/SlashTrain2223/chain_audit.json').read_text())
native=json.loads(Path('Content/locomotion/NN/Attack184064/prophecy_slash_native.json').read_text())
source=json.loads(Path('Saved/SlashTrain2223/source_native_geometry.json').read_text())
np0,nr=np.array(native['root_position']),np.array(native['root_rotation'])
sp0,sr=np.array(source['root_position']),np.array(source['root_rotation'])
if label.startswith('ground'):sp0[1]=0
axis=np.array([1,-1,1]);names=fixture['initial_history']['bone_names']
first=np.array(rows[0]['anchor']);a0p=first[:3];a0r=Rotation.from_quat(first[3:]).as_matrix()
groups=[]
for row in rows:
 if not groups or row['frame']<=groups[-1][-1]['frame']:groups.append([])
 groups[-1].append(row)
summary=[]
for i,group in enumerate(groups):
 if i>=len(oracle['segments']):break
 seg=oracle['segments'][i];ref=np.array(oracle['expected'][seg['startFrame']-2:seg['finalFrame']-1])
 n=min(len(group),len(ref));err=[]
 for k,row in enumerate(group[:n]):
  np0=np.array(row.get('native_position',native['root_position']));nr=np.array(row.get('native_rotation',native['root_rotation'])).reshape(3,3)
  anchor=np.array(row['anchor']);ar=Rotation.from_quat(anchor[3:]).as_matrix()
  local=(np.array(row['output'][131:206]).reshape(25,3)-np0)@nr.T
  world=(local*axis*100)@ar.T+anchor[:3]
  sourceworld=(((world-a0p)@a0r)/100*axis)@sr+sp0
  errors=np.linalg.norm(sourceworld-ref[k,131:206].reshape(25,3),axis=-1)*100
  err.append(errors)
 err=np.array(err)
 record=dict(index=i+1,family=seg['family'],unreal_steps=len(group),viewer_steps=len(ref),
   first_max_cm=float(err[0].max()),max_cm=float(err.max()),last_max_cm=float(err[-1].max()),
   first_worst_bone=names[int(err[0].argmax())],last_worst_bone=names[int(err[-1].argmax())])
 summary.append(record)
 print(record)
 if i==0:
  actual=np.array(group[0]['input']);wanted=np.array(oracle['inputs'][0]);d=np.abs(actual-wanted)
  print('first seed max abs excluding world target',np.max(d[:262]), 'index',np.argmax(d[:262]))
  for start,end in [(0,41),(41,82),(82,172),(172,262)]:
   print('input',start,end,'max',d[start:end].max(), 'top', sorted([(int(x),float(d[x]),float(actual[x]),float(wanted[x])) for x in range(start,end)],key=lambda x:-x[1])[:5])
  target=((actual[262:265]-np0)@nr.T)@sr+sp0
  print('target error cm',(target-wanted[262:265])*100)
  for k,errors in enumerate(err):print('firststep',k+2,'maxcm',errors.max(),'pelviscm',errors[0],'bone',names[int(errors.argmax())])
(base/f'SlashTrainParity-{label}-summary.json').write_text(json.dumps(summary,indent=2))
