import pathlib,re,json,math,sys
import numpy as np
p=pathlib.Path(__file__).parent
log=pathlib.Path('Saved/Logs/GameAnimationSample3.log')
lines=[x[x.index('WRISTNATIVE ')+12:] for x in log.read_text(errors='replace').rsplit('WIDE_WRIST_START',1)[-1].splitlines() if 'WRISTNATIVE ' in x]
(p/'NativeTrace.log').write_text('\n'.join(lines))
rows=[]
def twist(q):return (math.degrees(2*math.atan2(q[0],q[3]))+180)%360-180
def swing(q):return math.degrees(2*math.acos(min(1,math.hypot(q[0],q[3]))))
for line in lines:
    r=dict(v.split('=',1) for v in line.split())
    for k in ('q','lambda','poslambda','hi','targetq','f1','f2'):r[k]=[float(x) for x in r[k].split(',')]
    for k in ('t','dt','spec'):r[k]=float(r[k])
    for k in ('step','rig','sub'):r[k]=int(r[k])
    r['twist']=twist(r['q']);r['swing']=swing(r['q']);r['target_twist']=twist(r['targetq'])
    rows.append(r)
(p/'native_parsed.json').write_text(json.dumps(rows,separators=(',',':')))
print('Rows',len(rows))
for bone in ('hand_r','hand_l','lowerarm_r','lowerarm_l'):
    pre=[r for r in rows if r['child']==bone and r['phase']=='pre']
    post=[r for r in rows if r['child']==bone and r['phase']=='post']
    if not pre:continue
    first=next((i for i,r in enumerate(post) if np.linalg.norm(r['lambda'])>1e-8),None)
    print('\n',bone,'frame1',pre[0]['f1'],'frame2',pre[0]['f2'],'firstlambda',first)
    print('maxlambda',max(np.linalg.norm(r['lambda']) for r in post),'maxspec',max(abs(r['spec']) for r in post),'maxtwist',max(abs(r['twist']) for r in pre),'maxswing',max(r['swing'] for r in pre))
    invalid=[(a,b) for a,b in zip(pre,post) if abs(a['twist'])<169.99 and abs(b['lambda'][0])>1e-7]
    print('Inside170 with twist impulse',len(invalid))
    inds=[0]+list(range(max(0,(first or 0)-5),min(len(pre),(first or 0)+8)))
    for i in dict.fromkeys(inds):
        a,b=pre[i],post[i]
        print(f"t={a['t']:.6f} step={a['step']} pre={a['twist']:.6f}/{a['swing']:.6f} post={b['twist']:.6f} lambda={b['lambda']} spec={b['spec']:.9g} target={a['target_twist']:.6f}")
