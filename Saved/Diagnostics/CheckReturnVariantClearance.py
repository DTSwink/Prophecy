from pathlib import Path
import sys,json
exec(Path('Saved/Diagnostics/AnalyzePikeReturn.py').read_text().split("a,b=load('legacy')")[0])
tag=sys.argv[1] if len(sys.argv)>1 else 'smooth_variants';data=load(tag);out=[];last='None';current=None
for tick,row in sorted(data.items()):
 state=row['attack'];name=state.split(',')[0]
 if state=='None' and last!='None':
  current=dict(attack=last,end=tick,minimum=1e6,post4_minimum=1e6);out.append(current)
 if state!='None':current=None
 if current and tick-1 in data:
  h,q,w=local(row,'presented');ph,pq,pw=local(data[tick-1],'presented');base,tip,pad=geometry(row)
  interp=Slerp([0,1],R.from_quat([pq.as_quat(),q.as_quat()]))
  for alpha in np.linspace(0,1,9):
   score=clearance(ph+(h-ph)*alpha,interp(alpha),pw+(w-pw)*alpha,base,tip,pad)
   current['minimum']=min(current['minimum'],score)
   if tick>current['end']+4:current['post4_minimum']=min(current['post4_minimum'],score)
 last=name
print(json.dumps(out,indent=2));(p/(tag+'-clearance.json')).write_text(json.dumps(out,indent=2))
