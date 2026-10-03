import re
from pathlib import Path
t=Path('Saved/BP_ProphecyManualPoseAgent.t3d').read_text(encoding='utf-16')
for b in t.split('      Begin Object Name=')[1:]:
 b=b.split('      End Object')[0]
 if not re.search(r'MemberName="SetWalkPinning',b):continue
 print('\nNODE',b.splitlines()[0])
 print(re.search(r'MemberName="([^"]+)"',b)[1])
 for line in b.splitlines():
  if 'CustomProperties Pin' not in line:continue
  name=re.search(r'PinName="([^"]+)"',line)[1]
  if name in ('self','ReturnValue'):continue
  default=re.search(r'(?<!Auto)DefaultValue="([^"]*)"',line)
  links=re.search(r'LinkedTo=\(([^)]*)\)',line)
  print(name,default[1] if default else '',links[1] if links else '')
