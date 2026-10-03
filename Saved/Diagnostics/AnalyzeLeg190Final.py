import json,pathlib,numpy as np
from AnalyzeLeg190Paired import bend
p=pathlib.Path('Saved/Diagnostics');r=json.loads((p/'Leg190-final.json').read_text())['rows']
print('FINAL')
for x in r:
 if 187<=x['tick']<=203:print(x['tick'],round(bend(x['targets'],'r'),2))
