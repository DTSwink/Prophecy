"""Measure short repeated bend reversals, not merely distance from straight."""
import json,pathlib,math
p=pathlib.Path(__file__).parent
def bend(row,side):
 b=row['meshes']['PhysicalMesh'];h,k,f=[b[n+'_'+side]['p']for n in ('thigh','calf','foot')]
 u=[k[i]-h[i]for i in range(3)];v=[f[i]-k[i]for i in range(3)]
 return math.degrees(math.acos(max(-1,min(1,sum(a*b for a,b in zip(u,v))/math.sqrt(sum(x*x for x in u)*sum(x*x for x in v))))))
out={}
for tag in ('pin-jiggle-current','pin-jiggle-final'):
 rows=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())['rows'];events=[]
 for side in ('l','r'):
  angles=[bend(r,side)for r in rows]
  # Each monotonic run ends at a turning point; measure the complete bounce
  # between consecutive extrema. Keep both directions (bend or straighten).
  turns=[i for i in range(1,len(rows)-1)if (angles[i]-angles[i-1])*(angles[i+1]-angles[i])<0]
  for a,b,c in zip(turns,turns[1:],turns[2:]):
   if c-a>12 or a<120 or any(r['attack']!='None'for r in rows[a:c+1]):continue
   amplitude=min(abs(angles[b]-angles[a]),abs(angles[c]-angles[b]))
   if amplitude<1:continue
   events.append(dict(side=side,frames=[a+1,b+1,c+1],bend_degrees=[round(angles[x],3)for x in (a,b,c)],
    amplitude=round(amplitude,3),duration_frames=c-a,
    pins=[rows[x].get('pinning',{}).get('effective',[])for x in (a,b,c)]))
 out[tag]=events
 print(tag,json.dumps(events,indent=1))
(p/'KneeFlexReversals-comparison.json').write_text(json.dumps(out,indent=2))
