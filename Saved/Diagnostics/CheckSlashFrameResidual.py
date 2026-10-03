exec(open('Saved/Diagnostics/AnalyzeSlashParity.py').read().split('summary=[]')[0])
maximum=[]
for i,group in enumerate(groups):
 seg=oracle['segments'][i]
 for k,row in enumerate(group):
  ref=np.array(oracle['expected'][seg['startFrame']-2+k]);v=np.array(row['output'])
  R=v[206:431].reshape(25,3,3);E=ref[206:431].reshape(25,3,3)
  d=(Rotation.from_matrix(R).inv()*Rotation.from_matrix(E)).magnitude()*180/np.pi
  maximum.append((float(d.max()),i+1,k+2,names[int(d.argmax())],float(np.max(np.abs(R-E)))))
print('worst raw rotations', sorted(maximum,reverse=True)[:12])
print('first raw rotations',maximum[:5])
