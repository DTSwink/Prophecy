import json,pathlib,collections,re
p=pathlib.Path('Saved/Diagnostics/NNModifiers20261004')
s=json.loads((p/'before.json').read_text());r=s['rows']
ph=collections.Counter('loco' if not x['attack'] else str(x['attack'][0])+('/half' if x['attack'][1] else '/full') for x in r)
print('Baseline:',s['reason'],'samples',len(r),'ticks',r[0]['tick'],r[-1]['tick'],'phases',dict(ph))
# Evidence that deleted helpers only referenced each other in their removed tests.
import subprocess
old=subprocess.check_output(['git','show','9b4c03f:Source/GameAnimationSample3/Private/ProphecyHandInertiaRuntime.inl'],text=True)
print('Removed superseded helper/test lines:',len(old.splitlines())-len(pathlib.Path('Source/GameAnimationSample3/Private/ProphecyHandInertiaRuntime.inl').read_text().splitlines()))
