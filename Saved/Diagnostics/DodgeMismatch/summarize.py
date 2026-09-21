import json
from pathlib import Path
p=Path(__file__).parent
for name in ['current_ue.json','corrected_ue.json']:
 d=json.loads((p/name).read_text());print(name,'error:',d['error']);seen=set()
 for r in d['rows']:
  if not r['attack']:continue
  key=(r['attack'][-1],str(r.get('defense')))
  if key in seen:continue
  seen.add(key)
  print('t',round(r['time'],4),'attack',r['attack'],'defense',r.get('defense'))
