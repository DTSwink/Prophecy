import json,pathlib
p=pathlib.Path('Saved/Diagnostics');d=json.loads((p/'RecoveryHoldOnly-capture.json').read_text());print(d['reason'],len(d['rows']));assert d['reason']=='Complete'
r=d['rows'];exits=[]
for i in range(1,len(r)):
 if r[i]['attack']=='None' and r[i-1]['attack']!='None':
  print('EXIT',r[i]['tick'],r[i-1]['attack']);exits.append(r[i]['tick'])
  print([(x['tick'],x['weights']) for x in r[i:i+22]])
assert exits
