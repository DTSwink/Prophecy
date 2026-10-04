from pathlib import Path
root=Path('Source/GameAnimationSample3/Private')
for p in root.glob('*.cpp'):
 s=p.read_text(encoding='utf-8-sig')
 prefix='#include "ProphecyNNModifierDebug.h"\n'
 if s.startswith(prefix) and p.name!='ProphecyNNModifierInputs.cpp':
  s=s[len(prefix):]; a=s.index('\n')+1
  s=s[:a]+prefix+s[a:];p.write_text(s,encoding='utf-8')
