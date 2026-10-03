import json,math,re
from pathlib import Path
p=Path('Saved/Diagnostics/Knee202')
for tag in ('foot131_before','foot131'):
 d=json.loads((p/(tag+'.json')).read_text());rows={r['tick']:r for r in d['rows']}
 print(tag,d['reason'],len(rows))
 for tick in range(128,134):
  r=rows[tick];last=rows[tick-1]
  actual=r['meshes']['PhysicalMesh']['foot_r']['p'];old=last['meshes']['PhysicalMesh']['foot_r']['p']
  target=r['targets']['foot_r'];lasttarget=last['targets']['foot_r']
  mismatch=math.dist(target['previous']['p'],lasttarget['future']['p'])
  print(tick,'owner',r['foot_owner'],'step_cm',round(math.dist(actual,old),3),'forward_cm',round(actual[1]-old[1],3),'previous_endpoint_gap_cm',round(mismatch,3),'physical_vel',re.findall(r"'Vector'.*?x: ([^}]+)",r['foot_physical'])[:1])
before={r['tick']:r for r in json.loads((p/'foot131_before.json').read_text())['rows']}
after={r['tick']:r for r in json.loads((p/'foot131.json').read_text())['rows']}
print('future_target_change_at131',math.dist(before[131]['targets']['foot_r']['future']['p'],after[131]['targets']['foot_r']['future']['p']))
