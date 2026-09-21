from pathlib import Path
import re
base=Path(__file__).resolve().parents[2]/'Source/GameAnimationSample3/Private'
for name in ['ProphecyAgentResetPhysics.cpp','ProphecyBlendClock.cpp','ProphecyLowerTemperingLibrary.cpp']:
    p=base/name;s=p.read_text(encoding='utf-8-sig')
    def move(m):
        args=m[1].split(',')
        assert len(args) in (4,6)
        args+=['1.f']*(6-len(args))
        return 'SetLocomotionLowerBodyTempering(Agent,true,'+','.join(args[i] for i in [0,4,1,2,5,3])+')'
    s,n=re.subn(r'SetLocomotionLowerBodyTempering\(Agent,true,([^)]*)\)',move,s)
    assert n
    p.write_text(s,encoding='utf-8')
    print(name,n)
