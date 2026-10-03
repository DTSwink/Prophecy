import json,pathlib,sys,contextlib,io,math
p=pathlib.Path(__file__).parent
tag=sys.argv[1] if len(sys.argv)>1 else 'pin-jiggle-current'
sys.argv=['a',tag]
with contextlib.redirect_stdout(io.StringIO()):import AnalyzeRecoveryKnee as a
r=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())['rows']
def bend(b,s):
 h,k,f=[b[v+'_'+s]['p']for v in ('thigh','calf','foot')]
 u=a.unit(a.sub(k,h));v=a.unit(a.sub(f,k))
 return math.degrees(math.acos(max(-1,min(1,a.dot(u,v)))))
data=[]
for i,x in enumerate(r):
 b=x['meshes']['PhysicalMesh'];pin=x.get('pinning',{})
 data.append(dict(frame=i+1,t=x['t'],attack=x['attack'],angles=[bend(b,s)for s in ('l','r')],
  radii=[a.geom(b,s)[2]for s in ('l','r')],pin=pin))
print('actor',r[0]['actor'],'first time',r[0]['t'])
for side,s in enumerate(('l','r')):
 peaks=[]
 for i in range(2,len(data)-8):
  if data[i]['attack']!='None' or data[i]['t']<1.5:continue
  z=data[i]['angles'][side]
  if z<data[i-1]['angles'][side] and z<=data[i+1]['angles'][side]:
   before=max(d['angles'][side]for d in data[max(0,i-6):i]);after=max(d['angles'][side]for d in data[i+1:i+7]);amp=min(before-z,after-z)
   if amp>8:peaks.append(dict(frame=i+1,t=data[i]['t'],angle=z,before=before,after=after,amp=amp,pin=data[i]['pin']))
 print('SIDE',s,'DIPS',json.dumps(peaks,indent=1))
print('FRAME ANGLE_LEFT RADIUS PIN_SEL PIN_EFF PIN_TIME')
for x in data[235:280]:print(x['frame'],round(x['angles'][0],2),round(x['radii'][0],2),x['pin'].get('selected'),x['pin'].get('effective'),round(x['pin'].get('time',0)*60,1))
(p/('PinJiggle-'+tag+'.json')).write_text(json.dumps(data,indent=2))
