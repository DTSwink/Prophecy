"""Independent locomotion branch; never controls the recovery pod or state."""
import ast,hashlib,json,os,shlex,subprocess,sys,tempfile,time,zipfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import yaml
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitLocomotion'
EQUIPMENT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
from backup import verified_readback
from uefn_package import verify_package,runtime_files

def remote(code,timeout=45):
    return cloud.ssh('python -c '+shlex.quote(code),timeout=timeout)
def save(name,data):
    (OUT/(name+'.json')).write_text(json.dumps(data,indent=2))

def prepare():
    OUT.mkdir(exist_ok=True)
    parent=json.loads((EQUIPMENT/'recovery-split-parent-run.json').read_text())
    cp=json.loads((EQUIPMENT/'recovery-split-loco-fork-checkpoint.json').read_text())['checkpoint']
    assert cp['sha256']=='221ed14975999aab1846e53758113bb228418827acd4edbf8403ca1b05ba3699'
    assert hashlib.sha256(Path(cp['local']).read_bytes()).hexdigest()==cp['sha256']
    with zipfile.ZipFile(cp['local']) as z:assert z.testzip() is None
    with zipfile.ZipFile(parent['prepared']['source']['local']) as z:
        entries={n:z.read(n) for n in z.namelist() if not n.startswith('assets/motion_prior/')}
    # Keep the existing physical assets. Any unrelated asset change must be
    # reconciled, not silently brought into this branch.
    for entry,path in runtime_files(ROOT).items():
        if entry.startswith('pipeline/'):
            entries[entry]=path.read_bytes()
        else:
            assert entries[entry]==path.read_bytes(),'Physical asset differs from split: '+entry
    env=yaml.safe_load(entries['prepared/env_config.yaml'])
    env['idle_row_fraction']=.07
    env['idle_recovery']['fraction']=0.
    env['idle_recovery']['pelvis_linear_velocity_multiplier']=1.
    cfg=env['perturbed_motion']
    cfg.update(mse_only=True,episode_ticks=120,yaw_degrees=180.,ae_weight=0.,ae_ticks=0,blend_ticks=0,
        normal='7% ordinary idle/93% locomotion, each30%normal/70%perturbed; no recovery rows',
        phase='perturbed predicted phase feeds input and MSE target from tick0; normal authored clock',
        auxiliary='No AE model or AE loss; retain existing COM2 termination and failure penalty')
    assert env['episode_length']==10. and cfg['fraction']==.7 and cfg['loco_failure_penalty']==100.
    entries['prepared/env_config.yaml']=yaml.safe_dump(env,sort_keys=False).encode()
    # Run actual resume compatibility code against the immutable split checkpoint.
    tree=ast.parse(Path(__file__).with_name('train.py').read_text())
    loop=next(n for n in ast.walk(tree) if isinstance(n,ast.For) and isinstance(n.iter,ast.List)
        and any(isinstance(x,ast.Constant) and x.value=='engine_config.yaml' for x in n.iter.elts))
    class Args(SimpleNamespace):
        def __getattr__(self,key):return None
    with tempfile.TemporaryDirectory() as tmp,zipfile.ZipFile(cp['local']) as bundle:
        directory=Path(tmp)
        for name in ['engine_config.yaml','env_config.yaml','agent_config.yaml']:
            (directory/name).write_bytes(entries['prepared/'+name])
        exec(compile(ast.Module(body=[loop],type_ignores=[]),'production_resume','exec'),dict(
            yaml=yaml,bundle=bundle,directory=directory,config=env,
            a=Args(omni_run_lr=True,equipment_omni=True,resume_perturbed_motion=True)))
    source=OUT/'locomotion-mse-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    with zipfile.ZipFile(source) as z:verify_package(z,ROOT)
    data=source.read_bytes();sha=hashlib.sha256(data).hexdigest()
    key='mimickit/pipeline_20261014/locomotion-mse/source_'+sha[:12]+'.zip'
    client=cloud.s3()
    verified_readback(client,cloud.rp.VOLUME_ID,cp['preserved_key'],cp['sha256'])
    client.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=data,Metadata={'sha256':sha})
    verified_readback(client,cloud.rp.VOLUME_ID,key,sha)
    plan=dict(checkpoint=cp,source=dict(local=str(source),key=key,sha256=sha),
        run_suffix='uefn_locomotion_mse_yaw180_512',until_stopped=True,ceiling=.59)
    save('getup-success-prepared',plan)
    (OUT/'geometry.json').write_bytes((EQUIPMENT/'geometry.json').read_bytes())
    save('recovery-state-untouched-baseline',dict(active=json.loads((EQUIPMENT/'active_run.json').read_text()),
        pod_sha=hashlib.sha256((EQUIPMENT/'pod.json').read_bytes()).hexdigest(),
        control_sha=hashlib.sha256((EQUIPMENT/'runtime_control.json').read_bytes()).hexdigest()))
    print('Split checkpoint73832 and source verified; no AE asset included; production resume checks passed',flush=True)

def allocate():
    assert (OUT/'getup-success-prepared.json').exists()
    cloud.allocate('NVIDIA L4',.59,'SECURE',seconds=600,name='mimickit-locomotion-mse-'+str(int(time.time())))
    state=cloud.state()
    control=dict(pod_id=state['pod_id'],hard_stop_unix=time.time()+600,until_stopped=False,updated_unix=time.time())
    save('runtime_control',control)
    marker=OUT/'setup-verified'
    marker.unlink(missing_ok=True)
    code=f"""import sys,time
from pathlib import Path
sys.path.insert(0,{str(ROOT/'Labs/MimicKitTraining')!r})
import cloud
from billing_stop import stop_and_confirm
end={control['hard_stop_unix']!r}
while time.time()<end and not Path({str(marker)!r}).exists():time.sleep(2)
if not Path({str(marker)!r}).exists():stop_and_confirm({state['pod_id']!r},cloud.rp.load_api_key(),Path({str(OUT/'setup-timeout.json')!r}),'Locomotion setup not verified within10minutes')
"""
    with (OUT/'setup-guard.log').open('ab') as log:
        p=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
    save('setup-guard',dict(pid=p.pid,deadline=control['hard_stop_unix']))
    cloud.connect()
    cloud.ssh('mkdir -p /workspace/mimickit_trial')

def reuse_provision_function(name):
    # Reuse transfer/cache mechanics without importing its recovery-specific
    # globals or allocation/launch functions.
    path=Path(__file__).with_name('resume_getup_success.py')
    source=path.read_text();tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    scope=dict(globals());exec(ast.get_source_segment(source,node),scope);scope[name]()
def provision():reuse_provision_function('provision')
def runtime():reuse_provision_function('runtime')

def launch():
    plan=json.loads((OUT/'getup-success-prepared.json').read_text())
    state=cloud.state();cp=plan['checkpoint'];r='/workspace/mimickit_trial'
    with zipfile.ZipFile(plan['source']['local']) as source:
        expected_ae=not yaml.safe_load(source.read('prepared/env_config.yaml'))['perturbed_motion'].get('mse_only',False)
    assert state['pod_id'] != json.loads((EQUIPMENT/'pod.json').read_text())['pod_id']
    print(remote("""from pathlib import Path
import hashlib
r=Path('/workspace/mimickit_trial')
assert (r/'venv/bin/python').exists()
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==SHA
assert (r/'assets/motion_prior/motion_scorer.pt').exists()==EXPECTED_AE
print('Checkpoint and isolated runtime verified; expected AE asset state verified')
""".replace('SHA',repr(cp['sha256'])).replace('EXPECTED_AE',repr(expected_ae))),flush=True)
    from extend_runtime import extend
    extend(until_stopped=True)
    now=datetime.now().astimezone();name=now.strftime('%Y%m%d_%H%M%S')+'_'+plan['run_suffix']
    args=['--name',name,'--seconds','86400','--worlds',str(plan.get('worlds',512)),'--control-mode','vel','--absolute-walk',
        '--equipment-omni',r+'/prepared','--evaluate','--output-interval','100','--replay-rows','20',
        '--resume',r+'/resume.zip','--actor-lr','1.125e-6','--resume-perturbed-motion']
    subprocess.run([sys.executable,str(Path(__file__).with_name('start_training.py')),
        '--keep-deadline','--source-package',plan['source']['local'],
        '--source-sha256',plan['source']['sha256'],'--seconds','86400','--',*args],check=True)
    manifest=json.loads((EQUIPMENT/'20261020_094614_uefn_getup_skew_linear_512-dashboard.json').read_text())
    manifest['runtime_control']=dict(path=str(OUT/'runtime_control.json'),pod_id=state['pod_id'],
        fallback_unix=253402300799.)
    manifest['runs']=[dict(name=now.strftime('%Y-%m-%d_%H-%M-%S')+'_'+plan['run_suffix'],
        objective='uefn_omni_absolute_walk',training_outcomes=True,
        sources=[str(Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name))])]
    path=OUT/(name+'-dashboard.json');path.write_text(json.dumps(manifest,indent=2))
    pids={}
    for kind,argv in [('bridge',['--name',name]),('dashboard',[str(path)])]:
        with (OUT/(name+'-'+kind+'.log')).open('ab') as log:
            p=subprocess.Popen([sys.executable,str(Path(__file__).with_name(kind+'.py')),*argv],
                stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
            pids[kind]=p.pid
    (OUT/'current-run.txt').write_text(name)
    save('launch',dict(run=name,pod=state['pod_id'],observers=pids,prepared=plan))
    print(json.dumps(dict(run=name,pod=state['pod_id'],observers=pids)))

if __name__=='__main__':globals()[sys.argv[1]]()
