"""Start low-data observers for the explicitly named owned Run LR trial."""
import argparse,json,subprocess,sys
from datetime import datetime
from pathlib import Path
import cloud

p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args()
assert a.name.endswith('_uefn_runLR_velocity_512')
assert (cloud.OUT/(a.name+'-launch.json')).exists()
state=cloud.state();root=cloud.ROOT
source=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+a.name)
stamp=datetime.strptime(a.name[:15],'%Y%m%d_%H%M%S').strftime('%Y-%m-%d_%H-%M-%S')
manifest=dict(output=str(root/'Saved/MimicKit/TensorBoardRuns'),
    runtime_control=dict(path=str(cloud.OUT/'runtime_control.json'),pod_id=state['pod_id']),
    runs=[dict(name=stamp+('_no_armature' if '_no_armature_' in a.name else '')+'_UEFN_RunLR_velocity_512',objective='uefn_omni_absolute_walk',sources=[str(source)])])
path=cloud.OUT/(a.name+'-dashboard.json');path.write_text(json.dumps(manifest,indent=2))
receipt={}
for kind,args in [('bridge',['--name',a.name]),('dashboard',[str(path)])]:
    with (cloud.OUT/(a.name+'-'+kind+'.log')).open('ab',buffering=0) as log:
        proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name(kind+'.py'))]+args,
            stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    receipt[kind]=proc.pid
receipt.update(run=a.name,manifest=str(path))
(cloud.OUT/'observers.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
