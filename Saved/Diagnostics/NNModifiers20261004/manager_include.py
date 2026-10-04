from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp')
s=p.read_text(encoding='utf-8-sig')
s='#include "ProphecyNNModifierDebug.h"\n'+s
s+='\n#include "ProphecyNNModifierManager.inl"\n'
p.write_text(s,encoding='utf-8')
