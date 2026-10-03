from pathlib import Path
p=Path('Saved/Diagnostics/ArmedSpineHitch/graph.txt');s=p.read_text(encoding='utf-16');lines=s.splitlines()
for i,l in enumerate(lines):
 if 'SetUpperBodyArmedPose' in l:
  print('\n'.join(lines[max(0,i-3):i+48]))
