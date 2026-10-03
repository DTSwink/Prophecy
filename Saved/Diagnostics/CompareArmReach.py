from pathlib import Path
exec(Path('Saved/Diagnostics/AnalyzePikeReturn.py').read_text().split("a,b=load('legacy')")[0])
import sys
p=Path('Saved/Diagnostics/ArmReach')
def read(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert d['reason']=='Complete'
 return {r['tick']:r for r in d['rows']}
tags=sys.argv[1:] or ['before','target']
datasets=[read(tag) for tag in tags]
end=next(t for t in sorted(datasets[0]) if t>90 and datasets[0][t]['attack']=='None')
result={'end':end,'metrics':{}}
for tag,d in zip(tags,datasets):
 vals={}
 for arm in ['l','r']:
  angles=[]
  for t in range(end,180):
   coords=np.array([d[t]['pose'][n+'_'+arm]['future']['p'] for n in ['upperarm','lowerarm','hand']]);u=coords[1]-coords[0];v=coords[2]-coords[1]
   angles.append(np.degrees(np.arccos(np.clip(u@v/np.linalg.norm(u)/np.linalg.norm(v),-1,1))))
  pts=np.array([d[t]['pose']['hand_'+arm]['presented']['p'] for t in range(end,180)])
  chord=pts[-1]-pts[0];along=np.clip((pts-pts[0])@chord/(chord@chord),0,1)
  detour=np.linalg.norm(pts-pts[0]-along[:,None]*chord,axis=1)
  vals[arm]=dict(min_bend=float(min(angles)),straight_ticks=[end+i for i,a in enumerate(angles) if a<1.],max_world_detour_cm=float(max(detour)),path_cm=float(sum(np.linalg.norm(np.diff(pts,axis=0),axis=1))),max_step_cm=float(max(np.linalg.norm(np.diff(pts,axis=0),axis=1))),max_step_change_cm=float(max(np.linalg.norm(np.diff(pts,n=2,axis=0),axis=1))))
 minimum=1e6
 for t in range(end,180):
  h,q,w=local(d[t],'presented');ph,pq,pw=local(d[t-1],'presented');base,tip,pad=geometry(d[t]);interp=Slerp([0,1],R.from_quat([pq.as_quat(),q.as_quat()]))
  for alpha in np.linspace(0,1,9):minimum=min(minimum,clearance(ph+(h-ph)*alpha,interp(alpha),pw+(w-pw)*alpha,base,tip,pad))
 vals['blade_clearance']=minimum
 vals['prefix_cm']=max(float(np.linalg.norm(np.array(v['future']['p'])-datasets[0][t]['pose'][n]['future']['p'])) for t in d if t<end for n,v in d[t]['pose'].items())
 result['metrics'][tag]=vals
print(json.dumps(result,indent=2));(p/('compare_'+tags[-1]+'.json')).write_text(json.dumps(result,indent=2))
