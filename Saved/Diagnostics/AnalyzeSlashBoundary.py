exec(open('Saved/Diagnostics/AnalyzeSlashParity.py').read().split('summary=[]')[0])
def world(p,row):
 a=np.array(row['anchor']);return np.array(p)*axis*100@Rotation.from_quat(a[3:]).as_matrix().T+a[:3]
for i in range(1,min(5,len(groups))):
 prev=groups[i-1];next=groups[i][0];print('\nBOUNDARY',i,prev[-1]['time'],next['time'])
 for f in range(2):
  old=prev[-2+f];oldout=np.array(old['output']);newinput=np.array(next['input'])
  for name,a,b in [('pelvis',0,41*f),('foot_l',9,41*f+9),('foot_r',25,41*f+25),('hand_l',101,82+90*f+60),('hand_r',116,82+90*f+75)]:
   d=world(newinput[b:b+3],next)-world(oldout[a:a+3],old)
   print('previous' if f==0 else 'current',name,np.round(d,5),np.linalg.norm(d))
live=json.loads((base/f'SlashTrainParity-{label}.json').read_text())['rows']
for row in live:
 if 60<=row['tick']<=77:
  print('tick',row['tick'],'index',row['index'],'state',row['attack'], 'pelvis',row['targets']['pelvis']['future']['p'],'hand_l',row['targets']['hand_l']['future']['p'])
