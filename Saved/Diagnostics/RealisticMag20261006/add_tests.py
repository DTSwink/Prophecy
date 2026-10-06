from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyPhysicalContext.cpp')
s=p.read_text(encoding='utf-8-sig')
pos=s.rfind('#endif')
test=r'''
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBoneModesTest,"Prophecy.Agent.PhysicalContext.BoneModes",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyBoneModesTest::RunTest(const FString&)
{
    using namespace ProphecyPhysicalContext;using P=UProphecyPhysicalProfileLibrary;
    const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .CreateFXSystem(false).SetTransactional(false);
    auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    if(!TestNotNull(TEXT("World"),World))return false;
    if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    auto* A=World->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT{Remove(A);World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);};
    if(!TestNotNull(TEXT("Agent"),A))return false;
    A->bAutoEnsureStandaloneNNManager=false;
    auto* Mesh=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if(!TestNotNull(TEXT("Mesh"),Mesh))return false;
    A->GetAgentMesh()->SetSkeletalMeshAsset(Mesh);
    auto Value=[&](const TCHAR* B){return P::GetBodyMagnetizationMode(A,B);};
    auto Advance=[&](int N){for(int I=0;I<N;++I){FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/60);Update(A);}};
    TestTrue(TEXT("Uniform set"),P::SetMagnetizationMode(A,.2f));
    TestNull(TEXT("Uniform has no body lookup"),MagnetizationModes(A).Overrides);
    TestFalse(TEXT("Invalid body rejected"),P::SetBodyMagnetizationMode(A,TEXT("not_a_bone"),0));
    TestEqual(TEXT("Right arm subtree has three bodies"),P::SetMagnetizationModeBelow(A,TEXT("upperarm_r"),0,true),3);
    TestEqual(TEXT("Right hand follows selected subtree"),Value(TEXT("hand_r")),0.f);
    TestEqual(TEXT("Left hand isolated"),Value(TEXT("hand_l")),.2f);
    TestEqual(TEXT("Exclude parent selects forearm and hand"),P::SetMagnetizationModeBelow(A,TEXT("upperarm_r"),.8f,false),2);
    TestEqual(TEXT("Parent excluded"),Value(TEXT("upperarm_r")),0.f);
    P::SetBodyMagnetizationMode(A,TEXT("hand_r"),.6f);
    TestEqual(TEXT("Single body leaves forearm alone"),Value(TEXT("lowerarm_r")),.8f);
    TestTrue(TEXT("Save mixed snapshot"),P::SavePhysicalProfileSnapshot(A,TEXT("1")));
    P::SetMagnetizationMode(A,1);
    TestNull(TEXT("All setter removes sparse overrides"),MagnetizationModes(A).Overrides);
    TestEqual(TEXT("Below restore count"),P::BlendMagnetizationModeBelowToSnapshot(A,TEXT("upperarm_r"),true,1,TEXT("1"),.5f),3);
    Advance(30);TestEqual(TEXT("Body modes hold unchanged"),Value(TEXT("hand_r")),1.f);
    Advance(30);TestEqual(TEXT("Hand halfway after hold"),Value(TEXT("hand_r")),.8f);
    TestEqual(TEXT("Unselected arm unchanged"),Value(TEXT("hand_l")),1.f);
    P::SetMagnetizationMode(A,0);Advance(90);
    TestEqual(TEXT("All setter cancels pending subtree returns"),Value(TEXT("hand_r")),0.f);
    TestNull(TEXT("Cancelled uniform has no body lookup"),MagnetizationModes(A).Overrides);
    P::BlendMagnetizationModeToSnapshot(A,0,TEXT("1"));
    TestEqual(TEXT("Full restore keeps mixed hand"),Value(TEXT("hand_r")),.6f);
    TestEqual(TEXT("Full restore keeps mixed forearm"),Value(TEXT("lowerarm_r")),.8f);
    TestEqual(TEXT("Full restore restores baseline elsewhere"),Value(TEXT("hand_l")),.2f);
    P::SetMagnetizationMode(A,1);P::BlendMagnetizationModeToSnapshot(A,1,TEXT("1"));Advance(30);
    TestEqual(TEXT("Mixed return midpoint"),Value(TEXT("hand_r")),.8f);
    const float Pin=Value(TEXT("upperarm_l"));P::SetBodyMagnetizationMode(A,TEXT("upperarm_l"),Pin);
    Advance(30);TestEqual(TEXT("Fixed body survives moving fallback even when equal at assignment"),Value(TEXT("upperarm_l")),Pin);
    TestEqual(TEXT("Other bodies finish their return"),Value(TEXT("hand_l")),.2f);
    P::SetMagnetizationMode(A,.25f);P::SavePhysicalProfileSnapshot(A,TEXT("Uniform"));
    P::SetMagnetizationMode(A,.75f);P::BlendMagnetizationModeToSnapshot(A,1,TEXT("Uniform"));Advance(30);
    TestNull(TEXT("Uniform snapshot blend keeps scalar path"),MagnetizationModes(A).Overrides);
    TestEqual(TEXT("Uniform midpoint"),Value(TEXT("head")),.5f);
    P::SetBodyMagnetizationMode(A,TEXT("head"),.5f);Advance(30);
    TestEqual(TEXT("Body setter pins scalar-blend midpoint"),Value(TEXT("head")),.5f);
    TestEqual(TEXT("Uniform fallback finishes independently"),Value(TEXT("hand_l")),.25f);
    P::BlendBodyMagnetizationModeToSnapshot(A,TEXT("head"),0,TEXT("Uniform"));
    TestNull(TEXT("Restoring last differing bone collapses to uniform"),MagnetizationModes(A).Overrides);
    P::SetMagnetizationModeBelow(A,TEXT("pelvis"),.3f,true);
    TestNull(TEXT("Whole pelvis subtree uses uniform path"),MagnetizationModes(A).Overrides);
    TestEqual(TEXT("Whole subtree configured mode"),P::GetMagnetizationMode(A),.3f);
    TestTrue(TEXT("Special restores mixed snapshot1"),EnterSpecial(A));
    TestEqual(TEXT("Special restores right hand"),Value(TEXT("hand_r")),.6f);
    TestEqual(TEXT("Special restores left hand"),Value(TEXT("hand_l")),.2f);
    return !HasAnyErrors();
}
'''
s=s[:pos]+test+s[pos:];p.write_text(s,encoding='utf-8')