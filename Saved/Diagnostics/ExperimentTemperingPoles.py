from ReplayTemperedLeg import *
p=pathlib.Path(sys.argv[1]);rs=json.loads((p/'replay.json').read_text())
def solve(P, B, T, follow, method):
    h,k,a,t=points(T);ph,pk,pa,pt=points(P);bh,bk,ba,bt=points(B)
    ax=unit(a-h);old=unit(pa-ph);dist=np.linalg.norm(a-h);l1=np.linalg.norm(offsets[18]);l2=np.linalg.norm(offsets[19])
    prevpole=project(pk-ph,old)
    c=np.dot(old,ax);transported=project(prevpole-(old+ax)*np.dot(prevpole,ax)/max(1e-6,1+c),ax)
    if method=='knee':pole=project((pk*(1-follow)+bk*follow)-h,ax)
    elif method=='thigh':pole=project((pk-ph)*(1-follow)+(bk-bh)*follow,ax)
    elif method=='foot':pole=project((t-a)*np.array([1,1,0]),ax)
    elif method=='normal':
        g=np.array(config['ik_local_pole_axes'][0][0]);normal=unit(np.cross(offsets[18],g))@rot(B,18)
        normal=normal@rot(B,12).T@rot(T,12)
        new=unit(np.cross(normal,ax));pole=unit(transported*(1-follow)+new*follow)
    along=(l1*l1-l2*l2+dist*dist)/(2*dist);radius=math.sqrt(max(0,l1*l1-along*along))
    upper=ax*along+pole*radius;f=unit((t-a)*np.array([1,1,0]));right=np.cross([0,0,1],f)
    return math.degrees(math.atan2(np.dot(upper,right),np.dot(upper,f)))
for r in rs:
    if not 3.32<r['time']<3.8:continue
    P=np.array(r['previous_state']);B=np.array(r['raw_state']);T=np.array(r['published_state']);f=r['settings'][1]
    print(round(r['time'],3),'old',round(r['published']['yaw'],1),{m:round(solve(P,B,T,f,m),1) for m in ['knee','thigh','foot','normal']})
