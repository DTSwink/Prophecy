exec(open('Saved/Diagnostics/AnalyzeSlashParity.py').read().split('summary=[]')[0])
live=json.loads((base/f'SlashTrainParity-{label}.json').read_text())['rows']
live_times=np.array([r['t'] for r in live]);S=np.diag(axis)
rot_error=np.zeros(25);pos_error=np.zeros(25);viewer_rot=np.zeros(25);matches=0
max_time=0
for i,group in enumerate(groups):
 if i>=30:break
 seg=oracle['segments'][i];reference=oracle['expected'][seg['startFrame']-2:seg['finalFrame']-1]
 for k,row in enumerate(group):
  if k>=len(reference):break
  sample=live[np.argmin(np.abs(live_times-row['time']))]
  if abs(sample['t']-row['time'])>1e-6:continue
  matches+=1
  a=np.array(row['anchor']);AR=Rotation.from_quat(a[3:]).as_matrix()
  np0=np.array(row.get('native_position',native['root_position']));nr=np.array(row.get('native_rotation',native['root_rotation'])).reshape(3,3)
  raw=np.array(row['output']);P=(raw[131:206].reshape(25,3)-np0)@nr.T
  world=P*axis*100@AR.T+a[:3]
  R=S@(raw[206:431].reshape(25,3,3)@nr.T)@S@AR.T
  T=np.array([Rotation.from_quat(sample['targets'][b]['future']['q']).as_matrix().T for b in names])
  D=(Rotation.from_matrix(R).inv()*Rotation.from_matrix(T)).magnitude()*180/np.pi
  Q=np.array([sample['targets'][b]['future']['p'] for b in names])
  pos_error=np.maximum(pos_error,np.linalg.norm(Q-world,axis=-1))
  rot_error=np.maximum(rot_error,D)
  expected=np.array(reference[k][206:431]).reshape(25,3,3)
  aligned=S@T@a0r@S@sr
  DV=(Rotation.from_matrix(expected).inv()*Rotation.from_matrix(aligned)).magnitude()*180/np.pi
  viewer_rot=np.maximum(viewer_rot,DV)
print('Matched policy endpoints',matches)
for j,b in enumerate(names):print(b,'display minus raw cm',round(pos_error[j],7),'display minus raw deg',round(rot_error[j],5),'display versus viewer deg',round(viewer_rot[j],5))
(base/f'SlashTrainParity-{label}-visible.json').write_text(json.dumps(dict(matches=matches,bones=names,position_error_cm=pos_error.tolist(),rotation_error_degrees=rot_error.tolist(),viewer_rotation_error_degrees=viewer_rot.tolist()),indent=2))
