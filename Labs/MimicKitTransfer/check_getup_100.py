"""Fresh, fixed-seed paired recovery audit. No optimizer or training is created."""
from getup_transfer import *
import hashlib

DEST = OUT/'fresh-100'
SEED = 2026102301

def config_files():
    folder=DEST/'prepared';folder.mkdir(parents=True,exist_ok=True)
    def rewrite(s):
        return s.replace('/workspace/mimickit_trial/prepared',folder.as_posix()).replace('/workspace/mimickit_trial',SOURCE.as_posix())
    for p in (SOURCE/'prepared').iterdir():
        if p.suffix in ('.json','.yaml'): (folder/p.name).write_text(rewrite(p.read_text()))
    cfg=yaml.safe_load(rewrite((OUT/'native/env_config.yaml').read_text()))
    ec=yaml.safe_load(rewrite((OUT/'native/engine_config.yaml').read_text()))
    # Evaluate 100 perturbed cases, rather than spending 30 of the test slots on
    # normals. Only allocation changes; all reset and physics code is production.
    cfg['perturbed_motion']['fraction']=1.
    cfg['perturbed_motion']['getup_ae_regularizer']=False # no rewards evaluated
    return cfg,ec

def native():
    import warp as wp
    from util import mp_util
    from perturbed_omni import PerturbedOmniEnv
    from envs.base_env import EnvMode
    torch.manual_seed(SEED);np.random.seed(SEED)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6795)
    cfg,ec=config_files()
    env=PerturbedOmniEnv(cfg,ec,100,'cuda:0',False)
    env.set_mode(EnvMode.TEST)
    obs,_=env.reset();engine=env._engine
    def read():
        return np.concatenate([engine.get_body_pos(0).cpu().numpy(),engine.get_body_rot(0).cpu().numpy(),
            engine.get_body_vel(0).cpu().numpy(),engine.get_body_ang_vel(0).cpu().numpy()],-1).copy()
    state=read();phase=env._feedback_phase.cpu().numpy().copy();rows=[]
    for i in range(100):
        row=env.recovery_row_metadata(i)
        row.update(case=i,sword_drawn=bool(env._equipment[env._motion_ids[i]]),
                   arm_enabled=env._arm_enabled[i].cpu().tolist(),frame_phase=[phase[i].tolist()])
        rows.append(row)
    assert sum(r['perturbed_plus_row'] for r in rows)==50
    assert sum('front' in r['recovery_motion_file'].lower() for r in rows)==50
    assert all(r['recovery_start_seconds']==0 for r in rows)
    pol=Policy('native')
    reconstructed=observation_batch(state,rows,phase)
    torch.testing.assert_close(reconstructed,obs.cpu(),rtol=1e-4,atol=2e-5)
    np.savez_compressed(DEST/'starts.npz',states=state,phase=phase)
    (DEST/'manifest.json').write_text(json.dumps(dict(seed=SEED,rows=rows,
        starts_sha256=hashlib.sha256((DEST/'starts.npz').read_bytes()).hexdigest(),
        profile='native-pelvismax-spherical32; frozen before sampling; no tuning',
        checkpoint_sha256='0dc58150f87f1cb25816235f9e565638e9972d262b9203c5da0d14c0ea736a2b'),indent=2))
    print('Saved 100 fresh production resets; observations match environment.',flush=True)
    hist=[state];ends=np.zeros(100,int);ticks=np.zeros(100,int)
    for tick in range(1,181):
        action,phase=pol(observation_batch(state,rows,phase))
        engine.set_cmd(0,tensor(action).cuda());engine.step();state=read();hist.append(state)
        assert np.isfinite(state).all()
        for i in range(100):
            if not ends[i]:
                ends[i]=outcome(state[i],tick,rows[i])
                if ends[i]:ticks[i]=tick
        if tick%20==0:print(json.dumps(dict(native_tick=tick,successes=int((ends==2).sum()),failures=int((ends==1).sum()))),flush=True)
        if np.all(ends):break
    np.savez_compressed(DEST/'native.npz',states=hist,terminal=ends,endticks=ticks)
    (DEST/'native.json').write_text(json.dumps([dict(case=i,terminal=int(ends[i]),ticks=int(ticks[i])) for i in range(100)],indent=2))

def unreal():
    from getup_unreal import Channel, UnrealJolt
    for key,value in dict(TRANSFER_NATIVE_BALL_LIMITS='1',TRANSFER_RIG_VELOCITY_STEPS='40',
            TRANSFER_RIG_POSITION_STEPS='8',TRANSFER_TRAINING_CONTACT='1',TRANSFER_FRICTIONLESS_SELF='1').items():os.environ[key]=value
    data=np.load(DEST/'starts.npz');rows=json.loads((DEST/'manifest.json').read_text())['rows'];pol=Policy('native');results=[]
    for first in range(0,100,20):
        channel=Channel();UnrealJolt.channel=channel
        try:
            for i in range(first,first+20):
                state=data['states'][i];phase=data['phase'][i];row=rows[i]
                sim=UnrealJolt(state);actual=np.asarray(sim.initial['bodies'])
                np.testing.assert_allclose(actual,state,atol=1e-5,rtol=1e-5)
                history=[actual];terminal=0
                for tick in range(1,181):
                    action,pred=pol(observation(actual,row,phase));phase=pred[0]
                    actual=np.asarray(sim.request('step '+' '.join(map(str,action[0])))['bodies'])
                    assert np.isfinite(actual).all()
                    history.append(actual);terminal=outcome(actual,tick,row)
                    if terminal:break
                np.savez_compressed(DEST/f'unreal-{i:03d}.npz',states=history)
                results.append(dict(case=i,terminal=terminal,ticks=tick,ipc=str(channel.directory)))
                (DEST/'unreal.json').write_text(json.dumps(results,indent=2))
                print(json.dumps(results[-1]),flush=True)
        finally:
            if channel.process.poll() is None:channel.request('quit');channel.process.wait(60)
        assert channel.process.returncode==0
    native_results=json.loads((DEST/'native.json').read_text())
    report=dict(total=100,native_success=sum(r['terminal']==2 for r in native_results),
        unreal_success=sum(r['terminal']==2 for r in results),
        both_success=sum(a['terminal']==b['terminal']==2 for a,b in zip(native_results,results)),
        native_only=[a['case'] for a,b in zip(native_results,results) if a['terminal']==2 and b['terminal']!=2],
        unreal_only=[a['case'] for a,b in zip(native_results,results) if a['terminal']!=2 and b['terminal']==2])
    (DEST/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

def report():
    manifest=json.loads((DEST/'manifest.json').read_text());rows=manifest['rows']
    a=json.loads((DEST/'native.json').read_text());b=json.loads((DEST/'unreal.json').read_text())
    assert len(a)==len(b)==100
    summary=json.loads((DEST/'summary.json').read_text())
    summary['cohorts']=[]
    for motion in ('front','back'):
        for plus in (False,True):
            ids=[i for i,r in enumerate(rows) if motion in r['recovery_motion_file'].lower() and r['perturbed_plus_row']==plus]
            summary['cohorts'].append(dict(motion=motion,plus=plus,count=len(ids),
                native_success=sum(a[i]['terminal']==2 for i in ids),
                unreal_success=sum(b[i]['terminal']==2 for i in ids)))
    native_states=np.load(DEST/'native.npz')['states'];clips=[];failures=[]
    for i,row in enumerate(rows):
        old=native_states[:a[i]['ticks']+1,i];new=np.load(DEST/f'unreal-{i:03d}.npz')['states']
        clips.append(dict(row=i,motion=Path(row['recovery_motion_file']).stem,blend=row['whole_pose_blend'],plus=row['perturbed_plus_row'],
            runs=[dict(name='MuJoCo · frozen pelvismax',success=a[i]['terminal']==2,states=np.round(old[:,:,:7],6).tolist()),
                  dict(name='Jolt in Unreal · spherical32',success=b[i]['terminal']==2,states=np.round(new[:,:,:7],6).tolist())]))
        for name,result,states in (('native',a[i],old),('unreal',b[i],new)):
            if result['terminal']!=2:
                s=states[-1]
                failures.append(dict(case=i,backend=name,ticks=result['ticks'],terminal=result['terminal'],pelvis_z=float(s[0,2]),
                    head_z=float(s[2,2]),head_failure_below=row['head_height_loss_target_m']*.5,
                    pelvis_ceiling=row['getup_failure_pelvis_height_m']))
    summary['failures']=failures;summary['seed']=SEED;summary['training_performed']=False
    summary['scope']='100 fresh perturbed starts from production reset code; same frozen checkpoint and initial states; deterministic policy; flat floor; gameplay defaults unchanged'
    (DEST/'summary.json').write_text(json.dumps(summary,indent=2))
    bodies=json.loads((OUT/'comparison/data.json').read_text())['bodies']
    (DEST/'data.json').write_text(json.dumps(dict(bodies=bodies,clips=clips),separators=(',',':')))
    html=(ROOT/'Labs/MimicKitTransfer/getup_comparison.html').read_text(encoding='utf-8')
    html=html.replace('repeat(3,1fr)','repeat(2,1fr)').replace('k<3','k<2').replace('let selected=1','let selected=0')
    html=html.replace('Same pelvismax checkpoint. Different joint limits.','100 fresh get-up starts · paired transfer test')
    html=html.replace('Previous Jolt: 1/18 successes · adjusted Jolt inside Unreal: 18/18 · no retraining',
        f"MuJoCo: {summary['native_success']}/100 · adjusted Jolt inside Unreal: {summary['unreal_success']}/100 · no retraining · seed {SEED}")
    (DEST/'index.html').write_text(html,encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':
    DEST.mkdir(parents=True,exist_ok=True)
    {'native':native,'unreal':unreal,'report':report}[sys.argv[1]]()
