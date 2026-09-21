import pathlib,json,math,sys,statistics
def sub(a,b):return [x-y for x,y in zip(a,b)]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(a):return math.sqrt(dot(a,a))
def unit(a):return [x/max(1e-12,norm(a)) for x in a]
def angle(a,b):return math.degrees(math.acos(max(-1,min(1,dot(a,b)/max(1e-12,norm(a)*norm(b))))))
def quantile(xs,q):return sorted(xs)[min(len(xs)-1,int(q*(len(xs)-1)))] if xs else None
for directory in sys.argv[1:]:
    p=pathlib.Path(directory);rs=[json.loads(l) for l in (p/'metrics.jsonl').open()]
    rs=[r for r in rs if r['agent']=='BP_ProphecyManualPoseAgent_C_1' and r['side']=='l']; rows=[];prior=None;end=None;attacks=0
    for r in rs:
        if r['attack'] and (not prior or not prior['attack']):attacks+=1
        if prior and prior['attack'] and not r['attack']:end=r['frame']
        if not r['attack'] and end is not None and r['frame']>60:
            m=r.get('poses',r['metrics']).get('presented');before=prior.get('poses',prior['metrics']).get('presented') if prior else None
            if m:
                h,k,a,t=m['points'];u=sub(k,h);f=sub(t,a);hf=unit([f[0],f[1],0]);side=[-hf[1],hf[0],0]
                yaw=math.degrees(math.atan2(dot(u,side),dot(u,hf))) if math.hypot(*u[:2])>5 and math.hypot(*f[:2])>3 else None
                lateral=dot(u,side)
                rec={'frame':r['frame'],'age':r['frame']-end,'yaw':yaw,'ankleZ':a[2],'mode':r['mode'],
                     'lateral_cm':lateral,'abduction':math.degrees(math.asin(min(1,abs(lateral)/max(1e-12,norm(u)))))}
                if before and not prior['attack']:
                    old=sub(before['points'][1],before['points'][0]); rec['step']=angle(u,old)
                    if 'rotations' in m and 'rotations' in before:
                        rec['calf_rotation']=math.degrees(2*math.acos(min(1,abs(dot(m['rotations'][1],before['rotations'][1])))))
                rows.append(rec)
        prior=r
    yaws=[abs(r['yaw']) for r in rows if r['yaw'] is not None];steps=[r['step'] for r in rows if 'step' in r];late=[abs(r['yaw']) for r in rows if r['age']>=10 and r['yaw'] is not None]
    summary={'capture':str(p),'attacks':attacks,'recovery_frames':len(rows),'outward_over_60':sum(v>60 for v in yaws),'yaw_median':quantile(yaws,.5),'yaw_p95':quantile(yaws,.95),'late_yaw_p95':quantile(late,.95),'thigh_step_max':max(steps,default=0),'thigh_step_p95':quantile(steps,.95),'worst_steps':sorted(rows,key=lambda r:r.get('step',0),reverse=True)[:3],'modes':sorted(set(r['mode'] for r in rows))}
    abduction=[r['abduction'] for r in rows];side=[abs(r['lateral_cm']) for r in rows]
    summary.update(abduction_median=quantile(abduction,.5),abduction_p95=quantile(abduction,.95),abduction_max=max(abduction,default=0),side_cm_p95=quantile(side,.95))
    print(json.dumps(summary));(p/'recovery-summary.json').write_text(json.dumps(summary,indent=2))
