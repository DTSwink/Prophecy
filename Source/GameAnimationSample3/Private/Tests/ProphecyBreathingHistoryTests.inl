// Uses the manager's real accepted-pose encoders and input-history builder.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBreathingHistoryTest,"Prophecy.Breathing.NNHistory",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBreathingHistoryTest::RunTest(const FString&)
{
    using FImpl=AProphecyNNLocomotionManager::FImpl;
    const auto Impl=MakeUnique<FImpl>();
    if(!PhysicalFeedbackBatchTests::Initialize(*this,*Impl,1))return false;
    Impl->PublishedStateBuffer.SetNumZeroed(StateDim);
    Impl->UpperPublishedStateBuffer.SetNumZeroed(UpperStateDim);
    TArray<FTransform> Pose;Pose.SetNum(FullBodyBoneCount);
    for(int Step=0;Step<12;++Step){
        auto& A=Impl->Agents[0];A.bUseWalkPolicy=Step%2!=0;
        A.PublishedRoot=FVector3f(.1f*Step,2,.3f);A.CurRootPos=A.PublishedRoot+FVector3f(.04f,-.02f,0);
        A.PublishedYaw=.3f+Step*.07f;A.CurRootYaw=A.PublishedYaw+.09f;
        PhysicalFeedbackBatchTests::FillPose(Pose,1,Step);
        const auto PreviousLower=Impl->PrevStateBuffer,PreviousUpper=Impl->UpperPreviousStateBuffer;
        const auto PreviousHeading=Impl->PreviousPelvisHeadingBuffer;
        const auto LowerBefore=Impl->CurStateBuffer;
        const auto Mode=Step%3==0?EProphecyBreathingMode::UpperOnly:EProphecyBreathingMode::UpperAndPelvis;
        CommitBreathingPose(*Impl,0,Pose,Mode);
        float ExpectedLower[StateDim],ExpectedUpper[UpperStateDim];
        FSampledTrainingRotations Rotations(Pose);
        EncodePhysicalLowerSample(*Impl,A,Pose,Rotations,ExpectedLower);
        EncodePhysicalUpperSample(*Impl,Pose,Rotations,ExpectedUpper);
        if(Mode==EProphecyBreathingMode::UpperAndPelvis)
            for(int J=0;J<StateDim;++J)TestTrue(TEXT("Publication contains accepted breathing lower pose"),FMath::IsNearlyEqual(ExpectedLower[J],Impl->PublishedStateBuffer[J],1.e-5f));
        for(int J=0;J<UpperStateDim;++J)TestTrue(TEXT("Publication contains accepted breathing upper pose"),FMath::IsNearlyEqual(ExpectedUpper[J],Impl->UpperPublishedStateBuffer[J],1.e-5f));
        const FVector3f Delta=TransformRow(A.CurRootPos-A.PublishedRoot,YawMatrix(A.PublishedYaw));
        RebaseStateRoot(ExpectedLower,*Impl,Delta,WrapAngle(A.CurRootYaw-A.PublishedYaw));
        RebaseUpperHeadingState(ExpectedUpper,Delta,WrapAngle(A.CurRootYaw-A.PublishedYaw));
        if(Mode==EProphecyBreathingMode::UpperAndPelvis){
            for(int J=0;J<StateDim;++J)TestTrue(TEXT("Lower recurrence retains accepted breathing in mover frame"),FMath::IsNearlyEqual(ExpectedLower[J],Impl->CurStateBuffer[J],1.e-5f));
            float Heading[9];LowerTransformToHeading(ExpectedLower,0,3,*Impl,Heading);
            for(int J=0;J<9;++J)TestTrue(TEXT("Upper pelvis feature includes breathing"),FMath::IsNearlyEqual(Heading[J],Impl->CurrentPelvisHeadingBuffer[J],1.e-5f));
        }else TestTrue(TEXT("Upper-only leaves lower recurrence unchanged"),LowerBefore==Impl->CurStateBuffer);
        float Input[2*UpperStateDim];
        WriteUpperPoseHistory(Impl->UpperPreviousStateBuffer.GetData(),Impl->UpperCurrentStateBuffer.GetData(),
            Impl->UpperCurrentBaseBuffer.GetData(),Impl->UpperCurrentBaseBuffer.GetData(),Input);
        for(int J=0;J<UpperStateDim;++J){
            TestEqual(TEXT("Previous upper sample preserved for velocity"),Input[J],PreviousUpper[J]);
            TestTrue(TEXT("Next upper input uses accepted breathing"),FMath::IsNearlyEqual(Input[UpperStateDim+J],ExpectedUpper[J],2.e-5f));
        }
        TestTrue(TEXT("Previous lower sample preserved for velocity"),PreviousLower==Impl->PrevStateBuffer);
        TestTrue(TEXT("Previous pelvis feature preserved"),PreviousHeading==Impl->PreviousPelvisHeadingBuffer);
        // Perfect physical tracking cannot remove breathing from accepted history.
        float Feedback[StateDim];ApplyLowerPhysicalDeviation(ExpectedLower,ExpectedLower,Impl->CurStateBuffer.GetData(),Feedback);
        for(int J=0;J<StateDim;++J)TestTrue(TEXT("Aligned physics keeps accepted breathing"),FMath::IsNearlyEqual(Feedback[J],Impl->CurStateBuffer[J],1.e-5f));
    }
    return !HasAnyErrors();
}
