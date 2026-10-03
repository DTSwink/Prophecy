from pathlib import Path
exec(Path('Saved/Diagnostics/AnalyzePikeReturn.py').read_text().split("a,b=load('legacy')")[0])
import sys
tag=sys.argv[1] if len(sys.argv)>1 else 'variants'
p=Path('Saved/Diagnostics/ArmReach');d=json.loads((p/(tag+'.json')).read_text());assert d['reason']=='Complete'
rows={r['frame']:r for r in d['rows']};result=[]
for start,name in zip(range(90,631,90),['slashL','slashR','slashLD','slashRD','slashLU','slashRU','pike']):
 end=next(t for t in rows if t>start and rows[t]['attack']=='None');minimum=1e6;post=1e6;angles=[[],[]]
 for t in range(end,start+90):
  h,q,w=local(rows[t],'presented');ph,pq,pw=local(rows[t-1],'presented');base,tip,pad=geometry(rows[t]);interp=Slerp([0,1],R.from_quat([pq.as_quat(),q.as_quat()]))
  for alpha in np.linspace(0,1,9):
   score=clearance(ph+(h-ph)*alpha,interp(alpha),pw+(w-pw)*alpha,base,tip,pad);minimum=min(minimum,score)
   if t>end+4:post=min(post,score)
  for i,arm in enumerate(['l','r']):
   pts=np.array([rows[t]['pose'][n+'_'+arm]['future']['p'] for n in ['upperarm','lowerarm','hand']]);assert np.isfinite(pts).all()
   u=pts[1]-pts[0];v=pts[2]-pts[1];angles[i].append(float(np.degrees(np.arccos(np.clip(u@v/np.linalg.norm(u)/np.linalg.norm(v),-1,1)))))
 result.append(dict(attack=name,end=end,blade_clearance=minimum,post4_clearance=post,left_min_bend=min(angles[0]),right_min_bend=min(angles[1])))
print(json.dumps(result,indent=2));(p/(tag+'_summary.json')).write_text(json.dumps(result,indent=2))
