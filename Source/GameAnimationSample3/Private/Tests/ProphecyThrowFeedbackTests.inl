// Exercises the real manager encoder/history bridge with the actual mirrored throw poses.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyThrowFeedbackTest,"Prophecy.Throws.NNFeedback",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyThrowFeedbackTest::RunTest(const FString&)
{
    const auto Impl=MakeUnique<AProphecyNNLocomotionManager::FImpl>();
    if(!PhysicalFeedbackBatchTests::Initialize(*this,*Impl,1))return false;
    Impl->PublishedStateBuffer.SetNumZeroed(StateDim);Impl->UpperPublishedStateBuffer.SetNumZeroed(UpperStateDim);
    FString Error;
    for(bool Small:{false,true}){
        const auto* Profile=ProphecyThrow::Profile(Small,Error);if(!Profile){AddError(Error);return false;}
        ProphecyThrow::FModel Model;Model.Prepare(*Profile,Small?.37:1.,Profile->Target);
        for(double Frame:{0.,6.66,12.,25.,34.,50.,68.}){
            const auto Sample=Model.Sample(Frame);TArray<FTransform> Pose;Pose.SetNum(FullBodyBoneCount);
            for(int J=0;J<FullBodyBoneCount;++J){const int K=Profile->Names.IndexOfByKey(Impl->BodyNames[J]);if(K<0)return false;Pose[J]=ProphecyThrow::ToUnreal(Sample[K]);}
            auto& Agent=Impl->Agents[0];Agent.PublishedRoot=FVector3f(1,2,0);Agent.CurRootPos=FVector3f(1.04f,2.01f,0);Agent.PublishedYaw=.5f;Agent.CurRootYaw=.55f;
            const auto Previous=Impl->UpperPreviousStateBuffer;
            CommitBreathingPose(*Impl,0,Pose,EProphecyBreathingMode::UpperAndPelvis);
            float Lower[StateDim],Upper[UpperStateDim];FSampledTrainingRotations Rotations(Pose);
            EncodePhysicalLowerSample(*Impl,Agent,Pose,Rotations,Lower);EncodePhysicalUpperSample(*Impl,Pose,Rotations,Upper);
            const FVector3f Delta=TransformRow(Agent.CurRootPos-Agent.PublishedRoot,YawMatrix(Agent.PublishedYaw));
            RebaseStateRoot(Lower,*Impl,Delta,WrapAngle(Agent.CurRootYaw-Agent.PublishedYaw));RebaseUpperHeadingState(Upper,Delta,WrapAngle(Agent.CurRootYaw-Agent.PublishedYaw));
            for(int J=0;J<StateDim;++J)TestTrue(TEXT("Accepted throw feeds lower recurrence"),FMath::IsNearlyEqual(Lower[J],Impl->CurStateBuffer[J],2.e-5f));
            for(int J=0;J<UpperStateDim;++J)TestTrue(TEXT("Accepted throw feeds upper recurrence"),FMath::IsNearlyEqual(Upper[J],Impl->UpperCurrentStateBuffer[J],2.e-5f));
            TestTrue(TEXT("Previous accepted history is preserved"),Previous==Impl->UpperPreviousStateBuffer);
        }
    }return !HasAnyErrors();
}
