from pathlib import Path
import re
p=Path('Source/GameAnimationSample3/Private/ProphecyWalkPinningLibrary.cpp');s=p.read_text();s=re.sub(r'SmoothPins\(Agent,\*S,\d,\d,L,R\)',r'SmoothPins(*S,L,R)',s);s=s.replace('TestEqual(TEXT("Raw limit immediately vetoes residual smoothing"),L,0.f);','TestEqual(TEXT("Release retains smoothing instead of an obsolete raw veto"),L,1.f);');p.write_text(s)
