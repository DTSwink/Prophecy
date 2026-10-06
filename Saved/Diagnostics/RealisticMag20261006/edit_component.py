from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp')
s=p.read_text(encoding='utf-8-sig')
s=s.replace('    TArray<int32> BodyParents;','    TArray<int32> BodyParents;\n    TArray<float> BodyModes;\n    uint64 BodyModeRevision=0;')
s=s.replace('    const float WorldAlpha=ProphecyPhysicalContext::MagnetizationMode(Agent);','''    const auto Modes=ProphecyPhysicalContext::MagnetizationModes(Agent);
    if(Modes.Overrides && State->BodyModeRevision!=Modes.Revision)
    {
        State->BodyModes.SetNumUninitialized(State->BodyNames.Num());
        for(int32 I=0;I<State->BodyNames.Num();++I)
        { const auto* V=Modes.Overrides->Find(State->BodyNames[I]);State->BodyModes[I]=V?*V:Modes.Uniform; }
        State->BodyModeRevision=Modes.Revision;
    }''')
needle='    for (int32 Index = 0; Index < State->Handles.Num(); ++Index)\n    {\n        const int32 TargetIndex'
assert needle in s
s=s.replace(needle,'''    // Dispatch once: the uniform loop has no per-bone mode lookup or branch.
    const auto BuildTargets=[&](auto ModeAt)->bool
    {
    for (int32 Index = 0; Index < State->Handles.Num(); ++Index)
    {
        const float WorldAlpha=ModeAt(Index);
        const int32 TargetIndex''',1)
needle='''        Target.GravityCompensationCmPerSecondSquared = Settings.bCancelGravity ? -Agent->GetWorld()->GetGravityZ() : 0.0f;
    }
    }'''
assert needle in s
s=s.replace(needle,'''        Target.GravityCompensationCmPerSecondSquared = Settings.bCancelGravity ? -Agent->GetWorld()->GetGravityZ() : 0.0f;
    }
    return true;
    };
    if(Modes.Overrides)
    { if(!BuildTargets([&](int32 I){return State->BodyModes[I];}))return false; }
    else
    { if(!BuildTargets([Value=Modes.Uniform](int32){return Value;}))return false; }
    }''',1)
p.write_text(s,encoding='utf-8')