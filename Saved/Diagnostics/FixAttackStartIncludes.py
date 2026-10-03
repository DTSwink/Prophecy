from pathlib import Path
for name in ['ProphecyNNLocomotionManager.cpp','ProphecyAgent.cpp','ProphecyNNLocomotionAnimInstance.cpp','ProphecyAgentResetPhysics.cpp']:
 p=Path('Source/GameAnimationSample3/Private')/name;s=p.read_text(encoding='utf-8');lines=s.splitlines();assert lines[0]=='#include "ProphecyAttackStartInertia.h"';lines[0],lines[1]=lines[1],lines[0];p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
