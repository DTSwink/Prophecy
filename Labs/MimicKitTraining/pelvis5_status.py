import json
import deploy_locomotion_branch as d
run=json.loads((d.OUT/'active_run.json').read_text())['run']
code='''from pathlib import Path
import json
r=Path('/workspace/mimickit_trial');p=r/'runs'/RUN
print('Run files:',[(f.name,f.stat().st_size) for f in p.glob('*')])
for f in [r/(RUN+'.log'),r/'logs'/(RUN+'.log'),p/'train.log']:
 if f.exists():print(str(f),f.read_text()[-3500:])
'''.replace('RUN',repr(run))
print(d.remote(code))
