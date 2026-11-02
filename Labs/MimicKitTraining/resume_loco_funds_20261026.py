"""Resume immutable current locomotion settings after billing shutdown."""
import io,json,sys,zipfile
from pathlib import Path
import torch,yaml
import deploy_locomotion_branch as d
import restore_prior_mse_20261025 as check
OUT=d.OUT/'funds-resume-20261026'

def launch():
    OUT.mkdir(exist_ok=True)
    plan=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    cp=json.loads((d.OUT/'funds-resume-checkpoint.json').read_text())
    with zipfile.ZipFile(cp['local']) as z,zipfile.ZipFile(plan['source']['local']) as src:
        for name in ['engine_config.yaml','env_config.yaml','agent_config.yaml']:
            expected=yaml.safe_load(src.read('prepared/'+name))
            if name=='agent_config.yaml':
                expected['actor_optimizer']['learning_rate']=1.125e-6  # Existing launch override.
            assert yaml.safe_load(z.read(name))==expected,name
        s=torch.load(io.BytesIO(z.read('resume_state.pt')),map_location='cpu',weights_only=False)
    cp['finished']=dict(iteration=s['completed_iteration']+1,samples=s['samples'])
    plan['checkpoint']=cp
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2))
    d.save('getup-success-prepared',plan);d.save('final-phase-prepared',plan)
    d.launch()

def verify():
    check.OUT=OUT;check.verify()
    (d.OUT/'setup-verified').touch()
    (d.OUT/'funds-resume-verified').touch()

if __name__=='__main__':globals()[sys.argv[1]]()
