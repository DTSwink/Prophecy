from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyGetUpRuntime.inl')
s=p.read_text(encoding='utf-8')
def cut(a,b):
 global s
 assert s.count(a)==1 and s.count(b)==1,(a,b)
 start=s.index(a);end=s.index(b,start);s=s[:start]+s[end:]
s=s.replace('#include "PhysicsEngine/PhysicsAsset.h"\n','').replace('#include "PhysicsEngine/SkeletalBodySetup.h"\n','')
cut('void AddGetUpGroundSupports(', 'FTransform GetUpCarrier(')
cut('        // Translate the connected clip hierarchy before regional handoff.', '        if(S->Published)')
cut('    if(Profile.FloorCorrection)', '    // Resolve all fall/animation data before interrupting anything.')
cut('IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyGetUpGroundFitTest,', 'IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyGetUpPoseMathTest,')
p.write_text(s,encoding='utf-8')
