#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyKickRunGhostTest,"Prophecy.NN.KickLocomotion.RunGhost",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyKickRunGhostTest::RunTest(const FString&)
{
    auto Impl=MakeUnique<AProphecyNNLocomotionManager::FImpl>();
    if(!PhysicalRotationCacheTests::LoadLayout(*this,*Impl))return false;
    FRandomStream Random(701017);
    for(int32 Side=0;Side<2;++Side)for(int32 Variant=0;Variant<64;++Variant)
    {
        float Visible[StateDim],Before[StateDim],Oracle[StateDim];
        for(int32 I=0;I<StateDim;++I)Visible[I]=Random.FRandRange(-1.f,1.f);
        CleanState(Visible,*Impl);FMemory::Memcpy(Before,Visible,sizeof(Visible));
        ProphecyKickLocomotion::FRunLegFrame Ghost;
        Ghost.Root=FVector3f(.4f,-.2f,.8f);Ghost.Yaw=.7f;
        for(float& V:Ghost.Leg)V=Random.FRandRange(-1.f,1.f);
        const int32 Offset=9+16*Side;
        FMemory::Memcpy(Oracle,Visible,sizeof(Visible));FMemory::Memcpy(Oracle+Offset,Ghost.Leg,sizeof(Ghost.Leg));
        CleanState(Oracle,*Impl);FMemory::Memcpy(Ghost.Leg,Oracle+Offset,sizeof(Ghost.Leg));
        // A capsule translation/turn must preserve the same hidden world leg.
        const FVector3f Root=Variant?FVector3f(-.3f,.1f,.2f):Ghost.Root;
        const float Yaw=Variant?-.4f:Ghost.Yaw;
        RebaseStateRoot(Oracle,*Impl,TransformRow(Root-Ghost.Root,YawMatrix(Ghost.Yaw)),WrapAngle(Yaw-Ghost.Yaw));
        RestoreKickRunFrame(*Impl,Ghost,Side,Visible,Root,Yaw);
        for(int32 I=0;I<StateDim;++I)
            if(I>=Offset && I<Offset+16)TestNearlyEqual(TEXT("Ghost matches ordinary root rebase"),Visible[I],Oracle[I],2.e-5f);
            else TestEqual(TEXT("Actual pelvis/support stay bit-identical"),Visible[I],Before[I]);
        // A second input restore rejects arbitrary physical/attack contamination.
        for(int32 I=Offset;I<Offset+16;++I)Visible[I]=500.f+I;
        RestoreKickRunFrame(*Impl,Ghost,Side,Visible,Root,Yaw);
        for(int32 I=Offset;I<Offset+16;++I)TestNearlyEqual(TEXT("Visible kick cannot overwrite run input"),Visible[I],Oracle[I],2.e-5f);
    }
    // Kick release requests only lower encoding. It must not dereference an absent upper output.
    AProphecyNNLocomotionManager::FImpl::FAgent Agent;
    TArray<FTransform> Pose;Pose.Init(FTransform::Identity,FullBodyBoneCount);
    float Lower[StateDim],LowerOnly[StateDim],Upper[UpperStateDim];
    EncodeComponentPoseToNNStates(*Impl,Agent,Pose,Lower,Upper);
    EncodeComponentPoseToNNStates(*Impl,Agent,Pose,LowerOnly,nullptr);
    TestTrue(TEXT("Lower-only release encoder equals full encoder"),FMemory::Memcmp(Lower,LowerOnly,sizeof(Lower))==0);
    return !HasAnyErrors();
}
#endif
