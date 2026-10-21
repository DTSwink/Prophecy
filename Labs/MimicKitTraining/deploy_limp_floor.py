"""Latest-checkpoint handoff with reset-only floor clearance."""
import ast,hashlib,json,sys,time,zipfile
from pathlib import Path
import yaml
import deploy_normal_balanced as previous
from backup import verified_readback
from uefn_package import verify_package
cloud,ROOT,OUT=previous.cloud,previous.ROOT,previous.OUT
remote=previous.remote
def save(name,value):
    (OUT/('limp-floor-'+name+'.json')).write_text(json.dumps(value,indent=2))
def prepare():
    plan=json.loads((OUT/'getup-success-prepared.json').read_text())
    with zipfile.ZipFile(plan['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    entries['pipeline/perturbed_omni.py']=Path(__file__).with_name('perturbed_omni.py').read_bytes()
    env=yaml.safe_load(entries['prepared/env_config.yaml'])
    assert env['perturbed_motion']['fraction']==.7
    env['perturbed_motion'].update(getup_floor_clearance_after_blend=True,
        getup_floor_model='/workspace/mimickit_trial/assets/uefn/humanoid_uefn.xml')
    entries['prepared/env_config.yaml']=yaml.safe_dump(env,sort_keys=False).encode()
    path=OUT/'limp-floor-source.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    with zipfile.ZipFile(path) as z:verify_package(z,ROOT)
    data=path.read_bytes();sha=hashlib.sha256(data).hexdigest()
    key='mimickit/pipeline_20261014/equipment/limp-floor/source_'+sha[:12]+'.zip'
    client=cloud.s3();client.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=data,Metadata={'sha256':sha})
    verified_readback(client,cloud.rp.VOLUME_ID,key,sha)
    save('source',dict(local=str(path),key=key,sha256=sha,verified_unix=time.time()))
    print('Corrected source and persistent readback verified',flush=True)
def run_previous(name):
    source=Path(previous.__file__).read_text()
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name)
    code=ast.get_source_segment(source,node).replace("'rovwuwstkm0s7r'","'new5546ihvxeax'")
    code=code.replace('normal_balanced_no_leeway','limp_floor').replace('normal-balanced-no-leeway','limp-floor')
    code=code.replace('action_noise=.05,gae_lambda=.95','action_noise=.075,gae_lambda=.98')
    scope=dict(previous.__dict__);scope['save']=save
    exec(code,scope);scope[name]()
def stop():
    active=json.loads((OUT/'active_run.json').read_text())
    assert active['run']=='20261020_190959_uefn_limp_blend_balanced_512'
    run_previous('stop')
def capture():
    run_previous('capture')
if __name__=='__main__':globals()[sys.argv[1]]()
