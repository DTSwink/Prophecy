// Included after the real event helper. No inference/session/physics is needed:
// exercise the manager's actual feature packer against independent pose encoding.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFootIKTerrainExitTest,"Prophecy.FootIK.Live.TerrainExitHistory",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFootIKTerrainExitTest::RunTest(const FString&)
{
    const auto WorldValues=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).SetTransactional(false);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&WorldValues);
    if(!TestNotNull(TEXT("Private feature-test world"),World))return false;
    auto* Manager=World->SpawnActor<AProphecyNNLocomotionManager>();
    auto Cleanup=[&]{World->DestroyWorld(false);World->MarkAsGarbage();};
    if(!TestNotNull(TEXT("Actual manager feature builder"),Manager)){Cleanup();return false;}
    auto& Impl=*Manager->Impl;
    if(!PhysicalFeedbackBatchTests::Initialize(*this,Impl,LocomotionBatchSize)){Cleanup();return false;}
    Impl.PublishedStateBuffer.SetNumZeroed(LocomotionBatchSize*StateDim);
    Impl.PreviousPublishedStateBuffer.SetNumZeroed(LocomotionBatchSize*StateDim);
    Impl.UpperPublishedStateBuffer.SetNumZeroed(LocomotionBatchSize*UpperStateDim);
    Impl.UpperPreviousPublishedStateBuffer.SetNumZeroed(LocomotionBatchSize*UpperStateDim);
    Manager->bSimBridge=false;Manager->CrowdSize=LocomotionBatchSize;
    Manager->bShowFutureRootDebug=false;Manager->AgentActors.SetNum(LocomotionBatchSize);
    Impl.bSimpleLocomotionTest=true;Impl.InputBuffer.SetNumZeroed(LocomotionBatchSize*InputDim);
    FTransform MeshRelative(FRotator(0,-90,0),FVector(0,0,-90));
    constexpr double HalfHeight=90.,Step=1./30.;
    const auto Carrier=[&](const FVector& Root,double Yaw){return MeshRelative*FTransform(FRotator(0,Yaw,0),Root+FVector(0,0,HalfHeight));};
    for(int32 Case=0;Case<4;++Case)
    {
        MeshRelative.SetRotation(FRotator(0,Case==0?0:Case==2?37:-90,0).Quaternion());
        const auto CheckEncoding=[&](const TCHAR* Part,int32 Sample,int32 Index,float Actual,float Expected)
        {
            TestTrue(FString::Printf(TEXT("%s case%d sample%d value%d: actual%.9g expected%.9g"),Part,Case,Sample,Index,double(Actual),double(Expected)),
                FMath::IsNearlyEqual(Actual,Expected,3.e-5f));
        };
        auto& A=Impl.Agents[0];
        A.PrevRootPos=FVector3f(1.1f,.13f,-.4f);A.CurRootPos=A.PrevRootPos+FVector3f(.06f,0,.03f);
        A.PrevRootYaw=.3f+Case*.8f;A.CurRootYaw=A.PrevRootYaw+.07f;
        A.PublishedRoot=A.CurRootPos-FVector3f(.03f,0,.015f);A.PublishedYaw=A.CurRootYaw-.035f;
        A.PreviousPublishedRoot=A.PublishedRoot-FVector3f(.06f,0,.03f);A.PreviousPublishedYaw=A.PublishedYaw-.07f;
        A.MoverState.position={A.CurRootPos.X,A.CurRootPos.Z};A.MoverState.velocity={1.7,-.35};
        A.MoverState.yaw_radians=A.CurRootYaw;A.MoverState.previous_yaw_radians=A.PrevRootYaw;
        A.MoverIntent.mode=prophecy::sim::LocomotionMode::Run;A.MoverIntent.orientation_yaw_radians=A.CurRootYaw+.4;
        A.MoverIntent.speed_amplitude=0.;A.bUseWalkPolicy=false;
        Manager->BuildInputBatch(float(Step));
        const auto RootsBefore=A;const auto InputBefore=Impl.InputBuffer;
        ProphecyFootIKLive::FSourceSample Samples[2];FTransform Carriers[2],PublishedCarrier;
        float ExpectedLower[2][StateDim],ExpectedUpper[2][UpperStateDim],ExpectedPublishedLower[StateDim],ExpectedPublishedUpper[UpperStateDim];
        for(int32 S=0;S<2;++S)
        {
            const auto TargetRoot=S?A.CurRootPos:A.PrevRootPos;
            const double TargetYaw=-FMath::RadiansToDegrees(S?A.CurRootYaw:A.PrevRootYaw);
            // Different actual navigation heights and a half-frame carrier lag.
            const double Lift=Case%2?144.-S*16.:80.+S*16.;
            auto& Sample=Samples[S];Sample.RootWorld=TrainingToUnreal(TargetRoot)+FVector(-2.6,1.3,Lift);
            const double SampleYaw=TargetYaw+7.;Sample.HeadingWorld=FRotator(0,SampleYaw,0).Vector();
            Carriers[S]=Carrier(Sample.RootWorld,SampleYaw);
            TArray<FTransform> Local;Local.SetNum(25);PhysicalFeedbackBatchTests::FillPose(Local,1,Case*2+S);
            Sample.BodiesWorld.SetNum(25);
            TArray<FTransform> ExpectedComponent;ExpectedComponent.SetNum(25);
            const FTransform RecurrentCarrier=Carrier(TrainingToUnreal(TargetRoot),TargetYaw);
            for(int32 B=0;B<25;++B)
            {
                Local[B].NormalizeRotation();Local[B].SetScale3D(FVector::OneVector);
                Sample.BodiesWorld[B]=Local[B]*Carriers[S];
                FTransform Flat=Sample.BodiesWorld[B];Flat.AddToTranslation(FVector(0,0,-Lift));
                ExpectedComponent[B]=Flat.GetRelativeTransform(RecurrentCarrier);
            }
            FSampledTrainingRotations RotationCache(ExpectedComponent);
            EncodePhysicalLowerSample(Impl,A,ExpectedComponent,RotationCache,ExpectedLower[S]);
            EncodePhysicalUpperSample(Impl,ExpectedComponent,RotationCache,ExpectedUpper[S]);
            if(S==1)
            {
                // The pending endpoint can be higher/lower than the actual
                // displayed carrier while crossing a ramp/landing boundary.
                const double PublishedLift=Lift+(Case-1.5)*8.;
                PublishedCarrier=Carrier(TrainingToUnreal(A.PublishedRoot)+FVector(0,0,PublishedLift),-FMath::RadiansToDegrees(A.PublishedYaw));
                for(int32 B=0;B<25;++B)
                {
                    ExpectedComponent[B]=Sample.BodiesWorld[B].GetRelativeTransform(PublishedCarrier);
                }
                FSampledTrainingRotations PublishedRotationCache(ExpectedComponent);
                EncodePhysicalLowerSample(Impl,A,ExpectedComponent,PublishedRotationCache,ExpectedPublishedLower);
                EncodePhysicalUpperSample(Impl,ExpectedComponent,PublishedRotationCache,ExpectedPublishedUpper);
            }
        }
        FString Error;
        auto Reject=[&](const ProphecyFootIKLive::FSourceSample& Current,double Time,const TCHAR* Label)
        {
            TArray<TArray<float>> Before;for(const auto& Buffer:PhysicalFeedbackBatchTests::Buffers)Before.Add(Impl.*Buffer.Member);
            const auto PublishedBefore=Impl.PublishedStateBuffer,UpperPublishedBefore=Impl.UpperPublishedStateBuffer;
            const bool WasPhysical=A.bHasPhysicalSample;
            TestFalse(Label,SeedFootIKTerrainExitHistory(Impl,0,Samples[0],Current,Carriers[0],Carriers[1],PublishedCarrier,2.,Time,Step,Error));
            TestFalse(TEXT("Rejected handoff explains the failure"),Error.IsEmpty());
            int32 I=0;for(const auto& Buffer:PhysicalFeedbackBatchTests::Buffers)TestTrue(TEXT("Rejected pair mutates no history"),Before[I++]==Impl.*Buffer.Member);
            TestEqual(TEXT("Rejected pair keeps physical history validity"),A.bHasPhysicalSample,WasPhysical);
            TestTrue(TEXT("Rejected pair cannot alter pending publication"),PublishedBefore==Impl.PublishedStateBuffer&&UpperPublishedBefore==Impl.UpperPublishedStateBuffer);
        };
        auto Invalid=Samples[1];Invalid.BodiesWorld.Pop();Reject(Invalid,2.+Step,TEXT("Incomplete pair rejected atomically"));
        Invalid=Samples[1];Invalid.BodiesWorld[24].SetRotation(FQuat(0,0,0,0));
        Reject(Invalid,2.+Step,TEXT("Late invalid bone rejected atomically"));
        Reject(Samples[1],2.+Step*.5,TEXT("60Hz pair cannot masquerade as30Hz history"));
        if(!TestTrue(TEXT("Accepted actual corrected pair"),SeedFootIKTerrainExitHistory(Impl,0,Samples[0],Samples[1],Carriers[0],Carriers[1],PublishedCarrier,2.,2.+Step,Step,Error)))
        {AddError(Error);Cleanup();return false;}
        TestTrue(TEXT("Actual mover and command remain byte-identical"),
            FMemory::Memcmp(&RootsBefore.MoverState,&A.MoverState,sizeof(A.MoverState))==0&&
            FMemory::Memcmp(&RootsBefore.MoverIntent,&A.MoverIntent,sizeof(A.MoverIntent))==0);
        TestTrue(TEXT("Policy root positions and headings were not reassigned"),RootsBefore.PrevRootPos==A.PrevRootPos&&RootsBefore.CurRootPos==A.CurRootPos&&RootsBefore.PrevRootYaw==A.PrevRootYaw&&RootsBefore.CurRootYaw==A.CurRootYaw);
        TestTrue(TEXT("Published carriers were not reassigned"),RootsBefore.PublishedRoot==A.PublishedRoot&&RootsBefore.PreviousPublishedRoot==A.PreviousPublishedRoot&&RootsBefore.PublishedYaw==A.PublishedYaw&&RootsBefore.PreviousPublishedYaw==A.PreviousPublishedYaw);
        for(int32 I=0;I<StateDim;++I)
            CheckEncoding(TEXT("Next lower publication predecessor"),1,I,Impl.PublishedStateBuffer[I],ExpectedPublishedLower[I]);
        for(int32 I=0;I<UpperStateDim;++I)
            CheckEncoding(TEXT("Next upper publication predecessor"),1,I,Impl.UpperPublishedStateBuffer[I],ExpectedPublishedUpper[I]);
        TestTrue(TEXT("Already published previous endpoints remain untouched"),
            Impl.PreviousPublishedStateBuffer.ContainsByPredicate([](float V){return V!=0;})==false&&
            Impl.UpperPreviousPublishedStateBuffer.ContainsByPredicate([](float V){return V!=0;})==false);
        TestTrue(TEXT("Fed root windows remain byte-identical"),RootsBefore.FedInputRoot==A.FedInputRoot&&RootsBefore.FedInputYaw==A.FedInputYaw&&
            FMemory::Memcmp(RootsBefore.FedFutureRootPositions,A.FedFutureRootPositions,sizeof(A.FedFutureRootPositions))==0&&
            FMemory::Memcmp(RootsBefore.FedFutureRootYaws,A.FedFutureRootYaws,sizeof(A.FedFutureRootYaws))==0);
        Manager->BuildInputBatch(float(Step)); // Real next-input packer, not a mirrored test encoder.
        for(int32 I=0;I<StateDim;++I)
        {
            CheckEncoding(TEXT("Next lower input current"),1,I,Impl.InputBuffer[I],ExpectedLower[1][I]);
            CheckEncoding(TEXT("Next lower input history"),0,I,Impl.InputBuffer[StateDim+I],ExpectedLower[0][I]);
        }
        for(int32 I=117;I<InputDim;++I)TestEqual(TEXT("Actual root velocity and all8 future commands unchanged"),Impl.InputBuffer[I],InputBefore[I]);
        float UpperInput[2*UpperStateDim];WriteUpperPoseHistory(Impl.UpperPreviousStateBuffer.GetData(),Impl.UpperCurrentStateBuffer.GetData(),Impl.UpperCurrentBaseBuffer.GetData(),Impl.UpperCurrentBaseBuffer.GetData(),UpperInput);
        for(int32 S=0;S<2;++S)for(int32 I=0;I<UpperStateDim;++I)
            CheckEncoding(TEXT("Next upper input"),S,I,UpperInput[S*UpperStateDim+I],ExpectedUpper[S][I]);
        for(int32 S=0;S<2;++S)
        {
            float Heading[9];LowerTransformToHeading(ExpectedLower[S],0,3,Impl,Heading);
            const auto& Actual=S?Impl.CurrentPelvisHeadingBuffer:Impl.PreviousPelvisHeadingBuffer;
            for(int32 I=0;I<9;++I)CheckEncoding(TEXT("Upper pelvis history"),S,I,Actual[I],Heading[I]);
        }
    }
    Cleanup();return !HasAnyErrors();
}
