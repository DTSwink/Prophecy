"""Launch independent bounded LR trials on the already authorized GPU only."""
import json,subprocess,time
from pathlib import Path
root=Path('/workspace/mimickit_trial')
control=json.loads((root/'private.json').read_text())
assert time.time()<control['deadline_unix']-300
assert not any('pipeline/train.py' in p.read_text(errors='ignore').replace('\x00',' ') for p in Path('/proc').glob('[0-9]*/cmdline') if p.exists()),'A trainer is still running'
(root/'stop.request').unlink(missing_ok=True)
stamp=time.strftime('%Y%m%d_%H%M%S',time.gmtime(time.time()+7200))
trials=[]
for lr,label in [(3e-7,'3e7'),(1e-6,'1e6'),(3e-6,'3e6')]:
    name=f'{stamp}_continuous_mse_128_lr{label}'
    log=root/(name+'.log')
    with log.open('w') as output:
        process=subprocess.Popen([str(root/'venv/bin/python'),'-u',str(root/'pipeline/train.py'),
            '--task','recovery_pose','--worlds','128','--action-noise','0.005','--actor-lr',str(lr),
            '--output-interval','50','--max-samples','100000000','--seconds','3600','--name',name],
            stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    trials.append(dict(name=name,actor_lr=lr,pid=process.pid,log=str(log)))
manifest=dict(created_unix=time.time(),deadline_unix=control['deadline_unix']-45,worlds_per_trial=128,
    action_noise=.005,critic_lr=.0001,trials=trials)
(root/'sweep.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest),flush=True)
