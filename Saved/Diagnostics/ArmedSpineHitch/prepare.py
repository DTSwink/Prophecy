from pathlib import Path
s=Path('Saved/Diagnostics/ArmedSpineHitch/graph.txt').read_text(encoding='utf-16');blocks=s.split('\n\n')
for b in blocks:
 if ' | NewFunction | K2Node_CallFunction_21 |' in b or ' | NewFunction | K2Node_CallFunction_16 |' in b:print(b)
p=Path('Source/GameAnimationSample3/Private/ProphecyArmedPoseLibrary.cpp');(Path('Saved/Diagnostics/ArmedSpineHitch')/'before.cpp').write_bytes(p.read_bytes())
