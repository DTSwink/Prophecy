from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyHandInertiaRuntime.inl');s=p.read_text()
a=s.index('FTransform HandInertiaCarrier(');b=s.index('void StoreInertiaArm(',a);s=s[:a]+s[b:]
s=s[:s.index('void MixHandRecoveryUpper(')]+'}\n'
p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyNNModifierInputs.cpp');s=p.read_text().replace('TEXT("Prophecy.Tempering.KneePlane"),1','TEXT("Prophecy.Tempering.KneePlane"),3');p.write_text(s)
p=Path('Saved/Diagnostics/NNModifiers20261004/capture.py');s=Path('Saved/Diagnostics/GhostLocoInertia20261004/capture.py').read_text()
s=s.replace('Diagnostics/GhostLocoInertia20261004','Diagnostics/NNModifiers20261004')
s=s.replace("mode=sys.argv[1] if len(sys.argv)>1 else 'full_0.03'","mode=sys.argv[1] if len(sys.argv)>1 else 'before'")
a=s.index("   if clock==29 and not mode.startswith('before'):")
b=s.index('  if s[\'frames\']>=',a)
s=s[:a]+'''   if mode=='observe':
    lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNModifierDebugLibrary'))
    first=lib.call_method('PrintNNModifiers',(a,));second=lib.call_method('PrintNNModifiers',(a,))
    assert first==second, 'Observer changed its own accepted state'
    if s['rows']:s['rows'][-1]['report']=str(first)
'''+s[b:]
s=s.replace("(240 if mode.startswith('stress') else 160)","260")
p.write_text(s)
