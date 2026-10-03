from pathlib import Path
Path('Source/GameAnimationSample3/Private/ProphecyWalkTickPinningRuntime.inl').write_text('''// Re-evaluate only the cached Walk pin contribution at presentation cadence.
// Source predictions, recurrence, inference and all blend clocks remain untouched.
void AProphecyNNLocomotionManager::UpdateWalkTickPinning()
{
    if(!GetWorld() || GetWorld()->IsPaused() || IsSimBridgeActive())return;
    for(int32 Index=0;Index<AgentActors.Num();++Index)
    {
        const auto* A=AgentActors[Index];auto* T=ProphecyWalkPinning::FindTickPinning(A);
        if(!T || !T->HasBase)continue;
        const auto* S=ProphecyWalkPinning::FindSmoothing(A);
        auto& Agent=Impl->Agents[Index];
        if(!S || Agent.Slash.bActive || Agent.DefensePose || !A->bNNInferenceEnabled)
        {ProphecyWalkPinning::ResetTickPinning(A);continue;}
        const FVector2f Value(S->Current[0],S->Current[1]);
        if(!T->Dirty && T->Last==Value)continue;
        T->Last=Value;T->Dirty=false;
        FTransform Result[2][8];
        FLocomotionClamps C;
        C.bClampFoot=A->bOverrideLocomotionFootClamp?A->bLocomotionFootClamp:bClampFoot;
        C.FootClampLengthMultiplier=A->bOverrideLocomotionFootClamp?1.f:FootClampLengthMultiplier;
        C.FootLeeway=A->bOverrideLocomotionFootClamp?A->LocomotionFootClampLeewayCm/100.f:0.f;
        C.bClampCalf=A->bOverrideLocomotionCalfClamp?A->bLocomotionCalfClamp:bClampCalf;
        C.CalfClampLengthMultiplier=A->bOverrideLocomotionCalfClamp?1.f:CalfClampLengthMultiplier;
        C.CalfLeeway=A->bOverrideLocomotionCalfClamp?A->LocomotionCalfClampLeewayCm/100.f:0.f;
        for(int32 End=0;End<2;++End)
        {
            const auto& Frame=End?T->Current:T->Previous;
            const auto* Base=End?T->BaseCurrent:T->BasePrevious;
            for(int32 J=0;J<8;++J)Result[End][J]=Base[J];
            const FVector3f Shift[]={Frame.Shift(0,Value.X),Frame.Shift(1,Value.Y)};
            if(Shift[0].IsNearlyZero(1.e-9f) && Shift[1].IsNearlyZero(1.e-9f))continue;
            const float* Lower=StateSlice(End?Impl->PublishedStateBuffer:Impl->PreviousPublishedStateBuffer,Index);
            const float* Upper=UpperStateSlice(End?Impl->UpperPublishedStateBuffer:Impl->UpperPreviousPublishedStateBuffer,Index);
            const float W=End?Agent.PublishedWalkWeight:Agent.PreviousPublishedWalkWeight;
            const FVector2f Weights=End?Agent.PublishedLegWalkWeights:Agent.PreviousPublishedLegWalkWeights;
            float Changed[StateDim];FMemory::Memcpy(Changed,Lower,sizeof(Changed));
            for(int32 I=0;I<2;++I)
            {
                if(Shift[I].IsNearlyZero(1.e-9f))continue;
                const int32 O=9+16*I;WriteStateVec3(Changed,O,ReadStateVec3(Lower,O)+Shift[I]);
                // Reuse the existing connected solve only where the normal pipeline
                // already reconstructs. Never introduce a new pole/leg algorithm.
                const bool Reconstruct=ProphecyLegChainDebug::IsEnabled(A) &&
                    (ProphecyLowerTempering::Find(A) || ProphecyNNPresentation::HasRecoveryCalfLengths(T->PoseId) || Weights[I]!=W);
                if(Reconstruct)
                {
                    const auto L=Impl->BlendLimb(I,Weights[I]);const FVector3f Ankle=ReadStateVec3(Changed,O);
                    const auto Axes=Impl->BuildFootAxes(L,Ankle,MatrixFromRot6(Changed+O+3),Changed[O+15]);
                    const FPelvisLegGeometry G{Impl->LocalOffsets[L.Start],Impl->LocalOffsets[L.Mid],L.LocalPoleAxes[0],
                        Impl->LocalOffsets[L.End].Size()+ProphecyKickFootLeeway::ReturningLengthDeltaCm(A,I)/100.f,
                        Ankle.Z+Impl->GroundHeight-ExactFootMinimum(Axes,Impl->FootHalfDims,Impl->ToeHalfDims)+1.e-5f};
                    ResolvePelvisLeg(ReadStateVec3(Lower,0),MatrixFromRot6(Lower+3),ReadStateVec3(Lower,0),MatrixFromRot6(Lower+3),
                        G,Changed,O,nullptr,false,nullptr,0.f,C.bClampCalf);
                }
            }
            FTransform Before[FullBodyBoneCount],After[FullBodyBoneCount];
            DecodeLocomotionPose(Impl,Lower,Upper,W,MakeArrayView(Before),nullptr,C,&Weights);
            DecodeLocomotionPose(Impl,Changed,Upper,W,MakeArrayView(After),nullptr,C,&Weights);
            for(int32 J=0;J<8;++J)
            {
                if(Shift[J/4].IsNearlyZero(1.e-9f))continue;
                const int32 B=T->Bones[J];
                Result[End][J].AddToTranslation(After[B].GetLocation()-Before[B].GetLocation());
                Result[End][J].SetRotation((After[B].GetRotation()*Before[B].GetRotation().Inverse()*Base[J].GetRotation()).GetNormalized());
            }
        }
        FProphecyNNPoseStore::UpdateTickPinningLegs(T->PoseId,MakeArrayView(T->Bones),MakeArrayView(Result[0]),MakeArrayView(Result[1]));
        FVector2f Effective;
        for(int32 I=0;I<2;++I) Effective[I]=T->Current.OtherPin[I]+T->Current.WalkWeight[I]*T->Current.Effective(I,Value[I]);
        Agent.PinProbability=Effective;
        if(auto* D=Impl->PinningDebug.Find(Index))if(D->Owner.Get()==A)
        {D->Locomotion.EffectivePinning=FVector2D(Effective);D->Locomotion.SampleTimeSeconds=GetWorld()->GetTimeSeconds();}
    }
}
''')
p=Path('Source/GameAnimationSample3/Private/ProphecyWalkPinningLibrary.cpp');s=p.read_text();ix=s.index('IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningSmoothingTest');s=s[:ix]+'''IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningTickTest,"Prophecy.NN.WalkPinning.EveryTick",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyWalkPinningTickTest::RunTest(const FString&)
{
    using namespace ProphecyWalkPinning;
    FTickPinFrame F;F.Valid=true;F.Delta[0]=FVector3f(-.06f,.02f,0);F.Applied=FVector2f(1,0);F.WalkWeight=FVector2f(1,.5f);
    TestTrue(TEXT("Policy-time sample preserves existing endpoint"),F.Shift(0,1).IsZero());
    TestTrue(TEXT("Next tick can remove cached pin without another NN prediction"),F.Shift(0,0).Equals(FVector3f(.06f,-.02f,0),1.e-7f));
    TestEqual(TEXT("Pinning never changes vertical target"),F.Shift(0,.5f).Z,0.f);
    F.Cap.X=.4f;F.Minimum.X=.6f;
    TestEqual(TEXT("Receiving own bound still wins"),F.Effective(0,.1f),.4f);
    F.Cap.X=1;TestEqual(TEXT("Opposite transfer remains a lower bound"),F.Effective(0,.8f),.8f);
    F.Cap.X=0;TestEqual(TEXT("Reach rejection remains immediate"),F.Effective(0,1),0.f);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);AProphecyAgent* A=World?World->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    TestNull(TEXT("Experimental path defaults off"),FindTickPinning(A));
    UProphecyWalkPinningLibrary::SetWalkPinningEveryTick(A,true);
    UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(A,true,3,1);
    auto* S=FindSmoothing(A);S->Current[0]=S->Target[0]=1;
    float L=0,R=1;SmoothPins(*S,L,R);
    TestEqual(TEXT("527 retains last value at new decision"),L,1.f);
    TickSmoothing(World,LEVELTICK_All,1.f/60);
    TestEqual(TEXT("528 unpins with cached decision, no NN call"),S->Current[0],0.f);
    TestEqual(TEXT("Other foot progresses independently between NN calls"),S->Current[1],1.f/3);
    L=1;R=0;SmoothPins(*S,L,R);TestEqual(TEXT("Reversal begins from actual current value"),L,0.f);
    TickSmoothing(World,LEVELTICK_All,1.f/120);TestEqual(TEXT("Authored game tick, not wall seconds"),S->Current[0],1.f/3);
    ResetSmoothing(A);TestNotNull(TEXT("Special/reset preserves toggle"),FindTickPinning(A));
    TestFalse(TEXT("Special/reset clears pose cache"),FindTickPinning(A)->HasBase);
    UProphecyWalkPinningLibrary::SetWalkPinningEveryTick(A,false);
    TestNull(TEXT("Disabled retires cache"),FindTickPinning(A));
    UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(A,false,3,1);World->DestroyWorld(false);
    return !HasAnyErrors();
}
'''+s[ix:];p.write_text(s)
