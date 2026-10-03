exec(open('Saved/Diagnostics/AnalyzeSlashParity.py').read().split('summary=[]')[0])
live=json.loads((base/f'SlashTrainParity-{label}.json').read_text())['rows']
for sample in [groups[0][0],groups[0][-1]]:
 r=min(live,key=lambda r:abs(r['t']-sample['time']))
 a=np.array(sample['anchor']);rot=Rotation.from_quat(a[3:]).as_matrix()
 raw=((np.array(sample['output'][131:206]).reshape(25,3)-np0)@nr.T*axis*100)@rot.T+a[:3]
 print('PRESENTATION',r['tick'],sample['frame'])
 for b in names:
  d=np.array(r['targets'][b]['future']['p'])-raw[names.index(b)]
  if np.linalg.norm(d)>.001:print(b,d,np.linalg.norm(d))
