"""Restart the stale recovery run from its preserved initial checkpoint."""
import ast, hashlib, json, shlex, sys, tempfile, time, zipfile
from pathlib import Path
from types import SimpleNamespace
import yaml
import deploy_normal_balanced as previous
from backup import verified_readback
from uefn_package import verify_package
cloud, ROOT, OUT = previous.cloud, previous.ROOT, previous.OUT
remote = previous.remote
PREFIX = 'limp-blend'

def save(name, value):
    (OUT/(PREFIX+'-'+name+'.json')).write_text(json.dumps(value, indent=2))

def prepare():
    plan = json.loads((OUT/'getup-success-prepared.json').read_text())
    cp = json.loads((OUT/'normal-balanced-no-leeway-preserved.json').read_text())
    assert cp['sha256'] == '4f8a2a285cdc74de1a1f499960924a5eaf9c56561cc646290439856b58a70baa'
    assert hashlib.sha256(Path(cp['local']).read_bytes()).hexdigest() == cp['sha256']
    with zipfile.ZipFile(plan['source']['local']) as z:
        entries = {n:z.read(n) for n in z.namelist()}
    for name in ['train.py','recovery_omni.py','perturbed_omni.py']:
        entries['pipeline/'+name] = Path(__file__).with_name(name).read_bytes()
    agent = yaml.safe_load(entries['prepared/agent_config.yaml'])
    agent['model']['action_std'] = .075
    agent['td_lambda'] = .98
    entries['prepared/agent_config.yaml'] = yaml.safe_dump(agent,sort_keys=False).encode()
    env = yaml.safe_load(entries['prepared/env_config.yaml'])
    with zipfile.ZipFile(cp['local']) as z:
        initial = yaml.safe_load(z.read('env_config.yaml'))
    env['position_mse_leeway'] = initial['position_mse_leeway']
    assert env['idle_row_fraction'] == env['idle_recovery']['fraction'] == 1.
    env['idle_recovery'].update(back_row_fraction=.5, random_start_fraction=.5, start_at_frame_zero=False)
    cfg = env['perturbed_motion']
    cfg.pop('getup_normal_only',None)
    corpus = (OUT/'limp-inits/corpus.npz').read_bytes()
    sha = hashlib.sha256(corpus).hexdigest()
    assert sha == '683193642d2350eedaef7cade16811f4f5161055b0296955bc5f539f18aca163'
    entries['assets/initializations/limp-inits.npz'] = corpus
    cfg.update(fraction=.7, normal_getup_random_start_fraction=.5,
        getup_pose_blend='uniform_0_1', getup_upper_half_probability=.5,
        getup_limp_dataset='/workspace/mimickit_trial/assets/initializations/limp-inits.npz',
        getup_limp_sha256=sha, getup_low_head_failure_tick=80,
        getup_pose='Uniform alpha [0,1], vanilla frame0 to random limp whole pose; linear root/local DOFs, shortest-arc root rotation; authored velocities unchanged',
        normal='Normal recoveries; half frame0 and half random source frame',
        getup_reset='Head above90% idle height pays known success continuation once, zero bootstrap')
    assert cfg['getup_start_frame']==0 and cfg['getup_failure_penalty']==100
    entries['prepared/env_config.yaml'] = yaml.safe_dump(env,sort_keys=False).encode()
    # Execute the production compatibility checks against the actual restart bundle.
    tree = ast.parse(Path(__file__).with_name('train.py').read_text())
    loop = next(n for n in ast.walk(tree) if isinstance(n,ast.For) and isinstance(n.iter,ast.List)
                and any(isinstance(x,ast.Constant) and x.value=='engine_config.yaml' for x in n.iter.elts))
    class Args(SimpleNamespace):
        def __getattr__(self, key): return None
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(cp['local']) as bundle:
        directory = Path(tmp)
        for name in ['engine_config.yaml','env_config.yaml','agent_config.yaml']:
            (directory/name).write_bytes(entries['prepared/'+name])
        scope = dict(yaml=yaml,bundle=bundle,directory=directory,config=env,
            a=Args(omni_run_lr=True,equipment_omni=True,resume_perturbed_motion=True,
                   resume_position_leeway=True,action_noise=.075,gae_lambda=.98))
        exec(compile(ast.Module(body=[loop],type_ignores=[]),'resume_config_check','exec'),scope)
    path=OUT/'limp-blend-source.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries.items(): z.writestr(name,data)
    with zipfile.ZipFile(path) as z: verify_package(z,ROOT)
    data=path.read_bytes();sha=hashlib.sha256(data).hexdigest()
    key='mimickit/pipeline_20261014/equipment/limp-blend/source_'+sha[:12]+'.zip'
    client=cloud.s3()
    verified_readback(client,cloud.rp.VOLUME_ID,cp['preserved_key'],cp['sha256'])
    client.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=data,Metadata={'sha256':sha})
    verified_readback(client,cloud.rp.VOLUME_ID,key,sha)
    plan=dict(run_suffix='uefn_limp_blend_balanced_512',checkpoint=cp,
        source=dict(local=str(path),key=key,sha256=sha),
        training_overrides=dict(action_noise=.075,gae_lambda=.98,resume_position_leeway=True),
        verified_unix=time.time())
    save('prepared',plan)
    print('Initial checkpoint, resume compatibility, source package and persistent readbacks verified',flush=True)

def stop():
    active=json.loads((OUT/'active_run.json').read_text())
    assert active['pod']==cloud.state()['pod_id']=='new5546ihvxeax'
    assert active['run']=='20261020_183047_uefn_normal_balanced_no_leeway_512'
    # Reuse the audited bounded handoff, substituting only ownership and marker.
    source=Path(previous.__file__).read_text()
    tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='stop')
    code=ast.get_source_segment(source,node).replace("'rovwuwstkm0s7r'","'new5546ihvxeax'")
    code=code.replace('normal_balanced_no_leeway_handoff_complete','limp_blend_handoff_complete')
    code=code.replace('normal-balanced-no-leeway','limp-blend')
    scope=dict(previous.__dict__);scope['save']=save
    exec(code,scope);scope['stop']()

def stage():
    old=json.loads((OUT/'limp-blend-handoff.json').read_text())['old_run']
    plan=json.loads((OUT/'limp-blend-prepared.json').read_text())
    code="""import json,hashlib,boto3
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/OLD
assert (p/'finished.json').exists(),'Old trainer still saving'
assert not (p/'failure.json').exists(),'Old trainer failure'
b=json.loads((p/'backup_status.json').read_text());assert b['key'].endswith('_final.zip')
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
for label,item in ITEMS.items():
 data=c.get_object(Bucket=BUCKET,Key=item['key'])['Body'].read()
 assert hashlib.sha256(data).hexdigest()==item['sha256']
 (r/(label+'.zip')).write_bytes(data)
print(json.dumps(dict(stale_final_backup=b,initial_checkpoint_staged=True)))
""".replace('OLD',repr(old)).replace('BUCKET',repr(cloud.rp.VOLUME_ID)).replace('ITEMS',repr(dict(
        source=plan['source'],resume=dict(key=plan['checkpoint']['preserved_key'],sha256=plan['checkpoint']['sha256']))))
    result=json.loads(remote(code));save('staged',result)
    (OUT/'getup-success-prepared.json').write_text(json.dumps(plan,indent=2))
    print(json.dumps(result))

if __name__=='__main__':
    globals()[sys.argv[1]]()
