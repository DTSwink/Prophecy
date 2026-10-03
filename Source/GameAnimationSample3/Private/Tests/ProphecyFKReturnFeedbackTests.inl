// Included in the manager after its real encoding/input helpers and layout fixtures.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFKReturnFeedbackTest,"Prophecy.NN.FKReturn.FeedbackInput",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFKReturnFeedbackTest::RunTest(const FString&)
{
    using FImpl=AProphecyNNLocomotionManager::FImpl;
    const auto Impl=MakeUnique<FImpl>();
    if(!PhysicalRotationCacheTests::LoadLayout(*this,*Impl))return false;
    Impl->Agents.SetNum(1);
    Impl->UpperPublishedStateBuffer.SetNumZeroed(UpperStateDim);
    Impl->UpperCurrentStateBuffer.SetNumZeroed(UpperStateDim);
    Impl->UpperPreviousStateBuffer.SetNumZeroed(UpperStateDim);
    Impl->CurStateBuffer.Init(123.f,StateDim);const auto LowerBefore=Impl->CurStateBuffer;
    TArray<FTransform> Pose;Pose.SetNum(FullBodyBoneCount);
    float LastAccepted[UpperStateDim],Base[UpperStateDim],Input[2*UpperStateDim];
    PhysicalFeedbackBatchTests::IdentityUpper(LastAccepted);
    PhysicalFeedbackBatchTests::IdentityUpper(Base);
    for(int32 Step=0;Step<12;++Step)
    {
        auto& A=Impl->Agents[0];A.PublishedRoot=FVector3f(Step*.1f,2.f,.3f);
        A.CurRootPos=A.PublishedRoot+FVector3f(.04f,-.02f,0);
        A.PublishedYaw=.4f+Step*.07f;A.CurRootYaw=A.PublishedYaw+.09f;
        PhysicalFeedbackBatchTests::FillPose(Pose,0,Step);
        FMemory::Memcpy(Impl->UpperPreviousStateBuffer.GetData(),LastAccepted,sizeof(LastAccepted));
        // Stand-in raw prediction deliberately far from the accepted pose.
        Impl->UpperCurrentStateBuffer.Init(-17.f,UpperStateDim);
        CommitFKReturnUpperPose(*Impl,0,Pose);
        // Independent cached physical encoder gives the same accepted upper state.
        float Expected[UpperStateDim];FSampledTrainingRotations Rotations(Pose);
        EncodePhysicalUpperSample(*Impl,Pose,Rotations,Expected);
        for(int32 J=0;J<UpperStateDim;++J)
            TestTrue(TEXT("Published state contains accepted FK pose"),FMath::IsNearlyEqual(Expected[J],Impl->UpperPublishedStateBuffer[J],1.e-5f));
        RebaseUpperHeadingState(Expected,TransformRow(A.CurRootPos-A.PublishedRoot,YawMatrix(A.PublishedYaw)),WrapAngle(A.CurRootYaw-A.PublishedYaw));
        WriteUpperPoseHistory(Impl->UpperPreviousStateBuffer.GetData(),Impl->UpperCurrentStateBuffer.GetData(),Base,Base,Input);
        for(int32 J=0;J<UpperStateDim;++J)
        {
            TestTrue(TEXT("Next inference gets accepted current pose in mover frame"),FMath::IsNearlyEqual(Input[UpperStateDim+J],Expected[J],2.e-5f));
            TestEqual(TEXT("Next inference preserves preceding accepted sample"),Input[J],LastAccepted[J]);
        }
        FMemory::Memcpy(LastAccepted,Impl->UpperCurrentStateBuffer.GetData(),sizeof(LastAccepted));
        TestTrue(TEXT("Feedback leaves lower recurrence byte-identical"),Impl->CurStateBuffer==LowerBefore);
    }
    return !HasAnyErrors();
}
