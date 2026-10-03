exec(open('Saved/Diagnostics/AnalyzeSlashParity.py').read().split('summary=[]')[0])
live=json.loads((base/f'SlashTrainParity-{label}.json').read_text())['rows']
times=np.array([r['time'] for r in rows]);source_p=np.array(source['root_position']);source_r=np.array(source['root_rotation']);S=np.diag(axis)
expected=np.array(oracle['expected'])
P=np.concatenate([(np.array(fixture['initial_history']['positions'][1])@source_r+source_p)[None],expected[:,131:206].reshape(-1,25,3)])
R=np.concatenate([(np.array(fixture['initial_history']['rotations'][1])@source_r)[None],expected[:,206:431].reshape(-1,25,3,3)])
max_p=np.zeros(3);max_r=np.zeros(3);count=0;bad=[];worst=None;polar_error=0
for sample in live:
 j=int(np.searchsorted(times,sample['t']+1e-6)-1)
 if j<0 or j>=len(rows) or sample['t']-times[j]>.034:continue
 if sample['index']>=30 and sample['attack'] is None:continue
 previous=P[j];future=P[j+1]
 before=Rotation.from_matrix(R[j]);after=Rotation.from_matrix(R[j+1]);alpha=sample['targets'][names[0]]['alpha']
 rotation=(before*Rotation.from_rotvec((before.inv()*after).as_rotvec()*alpha)).as_matrix()
 for k,key in enumerate(['previous','future','target']):
  wanted_p=[previous,future,previous+(future-previous)*alpha][k];wanted_r=[R[j],R[j+1],rotation][k]
  actual=np.array([sample['targets'][b][key]['p'] for b in names]);actual_r=np.array([Rotation.from_quat(sample['targets'][b][key]['q']).as_matrix().T for b in names])
  aligned=(((actual-a0p)@a0r)/100*axis)@source_r+source_p
  aligned_r=S@actual_r@a0r@S@source_r
  pe=float(np.max(np.linalg.norm(aligned-wanted_p,axis=-1))*1000)
  re=float(np.max(np.degrees((Rotation.from_matrix(wanted_r).inv()*Rotation.from_matrix(aligned_r)).magnitude())))
  max_p[k]=max(max_p[k],pe);max_r[k]=max(max_r[k],re)
  if k==2:
   if worst is None or re>worst[0]:worst=(re,sample['tick'],alpha,int(np.argmax(np.degrees((Rotation.from_matrix(wanted_r).inv()*Rotation.from_matrix(aligned_r)).magnitude()))))
   vector=(before.inv()*after).as_rotvec();theta=np.linalg.norm(vector,axis=1)
   beta=np.arctan2(alpha*np.sin(theta),(1-alpha)+alpha*np.cos(theta))
   polar=(before*Rotation.from_rotvec(vector*(beta/np.maximum(theta,1e-12))[:,None])).as_matrix()
   polar_error=max(polar_error,float(np.max(np.degrees((Rotation.from_matrix(polar).inv()*Rotation.from_matrix(aligned_r)).magnitude()))))
  if pe>1:bad.append((sample['tick'],j,key,pe,alpha))
 count+=1
print('interpolation',count,'max mm prev future target',max_p,'max degrees',max_r,'bad',bad[:15],'worst',worst,'max polar deg',polar_error)
