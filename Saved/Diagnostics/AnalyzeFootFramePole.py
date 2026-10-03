import json,pathlib,numpy as np,sys
p=pathlib.Path('Saved/Diagnostics');mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
def u(v):return v/max(np.linalg.norm(v),1e-12)
def rot(s,o):
 a=u(s[o:o+3]);b=u(s[o+3:o+6]-a*np.dot(s[o+3:o+6],a));return np.array([a,b,np.cross(a,b)])
def geom(s,r):
 o=r['offset'];h=s[:3]+np.array(r['hip'])@rot(s,3);up=np.array(r['knee'])@rot(s,o+9);axis=u(s[o:o+3]-h);rad=up-axis*np.dot(up,axis);return h,axis,up,u(rad),np.linalg.norm(rad)
def signed(a,b,axis):return float(np.rad2deg(np.arctan2(np.dot(axis,np.cross(a,b)),np.clip(np.dot(a,b),-1,1))))
out=[]
for line in (p/('PunchPole-'+mode+'-frozen.jsonl')).read_text().splitlines():
 r=json.loads(line);pr,b,a=[np.array(r[n]) for n in ('previous','before','after')];o=r['offset'];hp,ap,up,pp,rp=geom(pr,r);hb,axis,ub,pb,rb=geom(b,r);ha,aa,ua,pa,ra=geom(a,r)
 if rb<1e-5:continue
 if rp<1e-5:
  raw=np.array(r['pole'])@rot(pr,o+9);pp=u(raw-ap*np.dot(raw,ap))
 change=rot(pr,o+3).T@rot(a,o+3);ca=u(ap@change);cp=u(pp@change);c=np.clip(ca@axis,-1,1)
 transport=-cp if c<-1+1e-6 else cp-(ca+axis)*(np.dot(cp,axis)/max(1e-6,1+c));fr=u(transport-axis*np.dot(transport,axis))
 before=signed(fr,pb,axis);after=signed(fr,pa,axis)
 mask=np.ones(41,dtype=bool);mask[o+9:o+15]=False
 assert np.array_equal(b[mask],a[mask])
 assert abs(after)<=12.002,(r['time'],before,after)
 calf_err=abs(np.linalg.norm(b[o:o+3]-hb-ub)-np.linalg.norm(a[o:o+3]-ha-ua))*100
 assert calf_err<.0001,calf_err
 out.append(dict(time=r['time'],side='l' if o==9 else 'r',before=before,after=after,knee_shift_cm=float(np.linalg.norm(ub-ua)*100),calf_error_cm=calf_err))
(p/('PunchPole-'+mode+'-frozen-analysis.json')).write_text(json.dumps(out,indent=2))
print('pairs',len(out),'modified',sum(x['knee_shift_cm']>.0001 for x in out),'worst before',max(abs(x['before']) for x in out),'after',max(abs(x['after']) for x in out))
print('largest',sorted(out,key=lambda x:abs(x['before']),reverse=True)[:8])
