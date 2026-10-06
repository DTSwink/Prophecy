from pathlib import Path
p=Path('Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltVelocityServo.cpp');s=p.read_text().replace('for (FTarget& Target : Targets) Target.DenominatorSeconds = FMath::Max(Target.DenominatorSeconds, UE_SMALL_NUMBER);', 'HasLocalTargets=false;\n    for (FTarget& Target : Targets)\n    { Target.DenominatorSeconds = FMath::Max(Target.DenominatorSeconds, UE_SMALL_NUMBER);HasLocalTargets|=Target.WorldAlpha<1.f; }').replace('    HasLocalTargets=Targets.ContainsByPredicate([](const FTarget& T){return T.WorldAlpha<1.f;});\n','');p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyPhysicalContext.cpp');s=p.read_text();s=s.replace('    TestTrue(TEXT("Save requested slot 1"),', '    Profiles::SetMagnetizationMode(Agent,.25f);\n    TestTrue(TEXT("Save requested slot 1"),',1);s=s.replace('    TestTrue(TEXT("Other default snapshot must not be selected"),', '    Profiles::SetMagnetizationMode(Agent,1.f);\n    TestTrue(TEXT("Other default snapshot must not be selected"),',1)
s=s.replace('        ProphecyAttackRecovery::EnterSpecial(Agent,Kind==1);','''        Profiles::SetMagnetizationMode(Agent,.9f);
        TestTrue(TEXT("Mode return with hold schedules"),Profiles::BlendMagnetizationModeToSnapshot(Agent,10,NAME_None,5));
        ProphecyAttackRecovery::EnterSpecial(Agent,Kind==1);
        TestEqual(TEXT("Special entry immediately restores saved mode despite hold"),Profiles::GetMagnetizationMode(Agent),.25f);''',1)
s=s.replace('        TestEqual(TEXT("Old blend cannot overwrite restored values"),','        TestEqual(TEXT("Old mode hold cannot overwrite special snapshot"),Profiles::GetMagnetizationMode(Agent),.25f);\n        TestEqual(TEXT("Old blend cannot overwrite restored values"),',1)
needle='    // Legacy authored attack entry also snaps';i=s.index(needle);s=s[:i]+'''    Profiles::SetMagnetizationMode(Agent,1);
    TestFalse(TEXT("Invalid hold cannot mutate mode"),Profiles::BlendMagnetizationModeToSnapshot(Agent,1,TEXT("1"),-1));
    TestFalse(TEXT("Invalid mode rejected"),Profiles::SetMagnetizationMode(Agent,2));
    TestTrue(TEXT("Mode blend scheduled"),Profiles::BlendMagnetizationModeToSnapshot(Agent,1,TEXT("1"),.5f));
    for(int I=0;I<30;++I){FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/120.f);Update(Agent);}
    TestEqual(TEXT("Mode holds for 30 authored ticks"),Profiles::GetMagnetizationMode(Agent),1.f);
    for(int I=0;I<30;++I){FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/30.f);Update(Agent);}
    TestEqual(TEXT("Mode halfway after hold"),Profiles::GetMagnetizationMode(Agent),.625f);
    Profiles::SavePhysicalProfileSnapshot(Agent,TEXT("ModeMid"));
    for(int I=0;I<30;++I){FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/60.f);Update(Agent);}
    TestEqual(TEXT("Mode reaches saved endpoint"),Profiles::GetMagnetizationMode(Agent),.25f);
    Profiles::BlendMagnetizationModeToSnapshot(Agent,0,TEXT("ModeMid"));
    TestEqual(TEXT("Snapshot captures current mode, not pending destination"),Profiles::GetMagnetizationMode(Agent),.625f);
'''+s[i:];p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyClampProfiles.inl');s=p.read_text();needle='    TestTrue(TEXT("No ticking work remains"),';i=s.index(needle);s=s[:i]+'''    A->SetLocomotionFootClamp(false,23);
    TestTrue(TEXT("Schedule clamp hold"),Lib::BlendClampToSnapshot(A,EProphecyClampType::Foot,1,TEXT("ClampBase"),EMode::Locomotion,.5f));
    for(int I=0;I<29;++I)Advance(W,LEVELTICK_All,1.f/60.f);
    TestTrue(TEXT("Hold preserves disabled flag and remembered allowance"),!A->bLocomotionFootClamp && A->LocomotionFootClampLeewayCm==23);
    for(int I=0;I<61;++I)Advance(W,LEVELTICK_All,1.f/60.f);
    TestTrue(TEXT("Clamp reaches saved endpoint after hold plus duration"),A->bLocomotionFootClamp && A->LocomotionFootClampLeewayCm==3);
    A->SetLocomotionCalfClamp(true,17);
    Lib::BlendClampToSnapshot(A,EProphecyClampType::Calf,0,TEXT("ClampBase"),EMode::Locomotion,.5f);
    for(int I=0;I<29;++I)Advance(W,LEVELTICK_All,1.f/60.f);
    TestEqual(TEXT("Zero-duration clamp waits"),A->LocomotionCalfClampLeewayCm,17.f);
    Advance(W,LEVELTICK_All,1.f/60.f);
    TestEqual(TEXT("Zero-duration clamp snaps after hold"),A->LocomotionCalfClampLeewayCm,4.f);
'''+s[i:];p.write_text(s)
