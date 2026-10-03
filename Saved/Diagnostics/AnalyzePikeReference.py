from pathlib import Path
exec(Path('Saved/Diagnostics/AnalyzePikeReturn.py').read_text().split("a,b=load('legacy')")[0])
p=Path('Saved/Diagnostics/PikeReference')
a,b=load('torso_pike'),load('pelvis_pike')
end=next(t for t in sorted(a) if t>90 and a[t]['attack']=='None')
prefix=max(float(np.linalg.norm(np.array(v['future']['p'])-b[t]['pose'][n]['future']['p'])) for t in a if t<end for n,v in a[t]['pose'].items())
result={'return_start':end,'prefix_max_cm':prefix,'variants':{}}
for tag,data in [('torso',a),('pelvis',b)]:
 metrics={}
 for kind in ['future','presented']:
  for arm in ['hand_l','hand_r']:
   pts=np.array([data[t]['pose'][arm][kind]['p'] for t in range(end,180)])
   chord=pts[-1]-pts[0];along=np.clip((pts-pts[0])@chord/(chord@chord),0,1)
   detour=np.linalg.norm(pts-(pts[0]+along[:,None]*chord),axis=1)
   metrics[kind+'_'+arm]=dict(path_cm=float(sum(np.linalg.norm(np.diff(pts,axis=0),axis=1))),max_world_detour_cm=float(max(detour)),max_step_cm=float(max(np.linalg.norm(np.diff(pts,axis=0),axis=1))),max_velocity_change=float(max(np.linalg.norm(np.diff(pts,n=2,axis=0),axis=1))))
 minimum=1e6
 for t in range(end,180):
  h,q,w=local(data[t],'presented');ph,pq,pw=local(data[t-1],'presented');base,tip,pad=geometry(data[t]);interp=Slerp([0,1],R.from_quat([pq.as_quat(),q.as_quat()]))
  for alpha in np.linspace(0,1,9):minimum=min(minimum,clearance(ph+(h-ph)*alpha,interp(alpha),pw+(w-pw)*alpha,base,tip,pad))
 metrics['blade_clearance']=minimum
 result['variants'][tag]=metrics
print(json.dumps(result,indent=2));(p/'summary.json').write_text(json.dumps(result,indent=2))
