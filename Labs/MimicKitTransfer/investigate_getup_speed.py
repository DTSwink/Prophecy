"""Read-only trajectory analysis and isolated frozen-policy mechanism probes."""
from getup_transfer import *
DEST=OUT/'speed-investigation';DEST.mkdir(exist_ok=True)
FRESH=OUT/'fresh-100'
BASE=dict(TRANSFER_RIG_VELOCITY_STEPS='40',TRANSFER_RIG_POSITION_STEPS='8',
          TRANSFER_TRAINING_CONTACT='1',TRANSFER_FRICTIONLESS_SELF='1',CAND_SPHERICAL='1',CAND_LIMIT_HZ='32')
IDS=[0,1,2,3,24,25,26,27,72,73,74,75]

def stats():
    data=np.load(FRESH/'native.npz');meta=json.loads((FRESH/'manifest.json').read_text())['rows']
    nr=json.loads((FRESH/'native.json').read_text());jr=json.loads((FRESH/'unreal.json').read_text())
    rows=[]
    for i in range(100):
        n=data['states'][:nr[i]['ticks']+1,i];j=np.load(FRESH/f'unreal-{i:03d}.npz')['states']
        common=min(len(n),len(j));row=dict(case=i,front='front' in meta[i]['recovery_motion_file'],plus=meta[i]['perturbed_plus_row'],native_ticks=nr[i]['ticks'],jolt_ticks=jr[i]['ticks'],native_success=nr[i]['terminal']==2)
        for name,s in [('native',n),('jolt',j)]:
            row[name+'_peak_head_zspeed']=float(np.max(np.abs(s[:,2,9])))
            row[name+'_angular_rms_common']=float(np.sqrt(np.mean(s[:common,:,10:13]**2)))
            row[name+'_linear_rms_common']=float(np.sqrt(np.mean(s[:common,:,7:10]**2)))
            row[name+'_mean_head_rise_first10']=float((s[min(10,len(s)-1),2,2]-s[0,2,2])*30/min(10,len(s)-1))
        rows.append(row)
    both=[r for r in rows if r['native_success']]
    summary=dict(native_mean_ticks=float(np.mean([r['native_ticks'] for r in both])),jolt_mean_ticks=float(np.mean([r['jolt_ticks'] for r in both])),
        native_median_ticks=float(np.median([r['native_ticks'] for r in both])),jolt_median_ticks=float(np.median([r['jolt_ticks'] for r in both])),
        jolt_faster=sum(r['jolt_ticks']<r['native_ticks'] for r in both),same=sum(r['jolt_ticks']==r['native_ticks'] for r in both),
        mean_angular_rms_ratio=float(np.mean([r['jolt_angular_rms_common']/r['native_angular_rms_common'] for r in both])),
        mean_linear_rms_ratio=float(np.mean([r['jolt_linear_rms_common']/r['native_linear_rms_common'] for r in both])),
        biggest_time_gaps=sorted(rows,key=lambda r:r['native_ticks']-r['jolt_ticks'],reverse=True)[:10])
    (DEST/'trajectory-stats.json').write_text(json.dumps(dict(summary=summary,rows=rows),indent=2));print(json.dumps(summary,indent=2),flush=True)

def ablate():
    pol=Policy('native');starts=np.load(FRESH/'starts.npz');meta=json.loads((FRESH/'manifest.json').read_text())['rows']
    os.environ['GETUP_JOLT_FIXTURE']=str(OUT/'jolt-native-candidates/fixture.exe')
    variants={'baseline':{},'no_drag':{'TRANSFER_NO_DRAG':'1'},'gyro':{'CAND_GYRO':'1'},
        'limit16':{'CAND_LIMIT_HZ':'16'},'limit8':{'CAND_LIMIT_HZ':'8'},
        'gain_half':{'CAND_GAIN':'.5'},'native_motor':{'CAND_NATIVE_MOTOR':'1'}}
    reports=[]
    for label,flags in variants.items():
        for k in list(os.environ):
            if k.startswith(('TRANSFER_','CAND_')):del os.environ[k]
        os.environ.update(BASE|flags);results=[]
        for i in IDS:
            s=starts['states'][i];phase=starts['phase'][i];row=meta[i];sim=Jolt(s);s=np.asarray(sim.initial['bodies']);hist=[s];acts=[]
            try:
                for tick in range(1,181):
                    act,pred=pol(observation(s,row,phase));phase=pred[0];acts.append(act[0])
                    s=np.asarray(sim.request('step '+' '.join(map(str,act[0])))['bodies']);hist.append(s)
                    result=outcome(s,tick,row)
                    if result:break
            finally:sim.close()
            if label=='baseline':
                existing=np.load(FRESH/f'unreal-{i:03d}.npz')['states']
                np.testing.assert_array_equal(hist,existing)
            np.savez_compressed(DEST/f'{label}-{i:03d}.npz',states=hist,actions=acts)
            results.append(dict(case=i,terminal=result,ticks=tick))
        reports.append(dict(label=label,flags=flags,success=sum(r['terminal']==2 for r in results),mean_ticks=float(np.mean([r['ticks'] for r in results])),results=results))
        (DEST/'ablations.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports[-1]),flush=True)

def details():
    meta=json.loads((FRESH/'manifest.json').read_text())['rows'];n=np.load(FRESH/'native.npz');initial=np.load(FRESH/'starts.npz');pol=Policy('native');report=[]
    for i in [0,94]:
        row=meta[i];entry=dict(case=i)
        command_sequences=[]
        for name,s in [('native',n['states'][:int(n['endticks'][i])+1,i]),('jolt',np.load(FRESH/f'unreal-{i:03d}.npz')['states'])]:
            off=R.from_quat(s[:,2,3:7]).apply(np.tile(com[2],(len(s),1)))
            vz=s[:,2,9]-np.cross(s[:,2,10:13],off)[:,2]
            head=s[:,2,2]>row['head_reset_height_m'];feet=np.max(s[:,[11,14],2],axis=1)<row['success_max_feet_height_m'];speed=abs(vz)<row['success_max_head_vertical_speed_m_s']
            crossing=np.flatnonzero(head);first=int(crossing[0]) if len(crossing) else None
            phase=initial['phase'][i];actions=[]
            for state in s[:-1]:
                act,pred=pol(observation(state,row,phase));phase=pred[0];actions.append(act[0])
            command_sequences.append(np.asarray(actions))
            entry[name]=dict(success_tick=len(s)-1,first_head_above_target=first,
                head_up_but_feet_too_high_ticks=np.flatnonzero(head&~feet).tolist(),
                head_up_but_too_fast_ticks=np.flatnonzero(head&~speed).tolist(),
                first_10_tick_head_height=s[:11,2,2].tolist(),
                peak_head_origin_vertical_speed=float(np.max(abs(vz))))
        a,b=command_sequences;entry['action_rms_difference']={str(t):float(np.sqrt(np.mean((a[t]-b[t])**2))) for t in [0,1,5,10,15] if t<min(len(a),len(b))}
        report.append(entry)
    (DEST/'case-details.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)

def model():
    import warp as wp
    from util import mp_util
    from engines.engine import ObjType
    from uefn_engine import build_uefn_engine
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6797)
    cfg=yaml.safe_load((OUT/'native/engine_config.yaml').read_text().replace('/workspace/mimickit_trial',SOURCE.as_posix()))
    engine=build_uefn_engine(cfg,1,'cuda:0',False);e=engine.create_env()
    engine.create_obj(e,ObjType.articulated,str(ASSET/'humanoid_uefn.xml'),'character',enable_self_collisions=True);engine.initialize_sim()
    m=engine._solver.mj_model
    report=dict(timestep=m.opt.timestep,viscosity=m.opt.viscosity,density=m.opt.density,
        passive_damping=m.dof_damping.tolist(),armature=m.dof_armature.tolist(),
        joint_solref=m.jnt_solref.tolist(),geom_solref=np.unique(m.geom_solref,axis=0).tolist(),
        motor_gains=engine.native_profile_report['gains'],motor_caps=engine.native_profile_report['torque_caps_nm'],
        explicit_external_drag_hook=type(engine)._pre_sim_step.__qualname__)
    (DEST/'native-model.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':{'stats':stats,'ablate':ablate,'details':details,'model':model}[sys.argv[1]]()
