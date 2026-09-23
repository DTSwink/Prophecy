namespace
{
FTransform HandInertiaRoot(const FVector3f& P,float Yaw)
{ return FTransform(FRotator(0,-FMath::RadiansToDegrees(Yaw),0),TrainingToUnreal(P)); }
FTransform HandInertiaCarrier(const AProphecyAgent* Actor,const FTransform& Root)
{
    FTransform Capsule=Root;
    Capsule.AddToTranslation(FVector::UpVector*Actor->GetAgentCapsule()->GetScaledCapsuleHalfHeight());
    return (Actor->bManualNNPoseApplication ? Actor->GetAgentMesh()->GetRelativeTransform()
        : Actor->GetAuthoredMeshRelativeTransform())*Capsule;
}
void StoreInertiaArm(const AProphecyNNLocomotionManager::FImpl& Impl,int32 I,
    TArrayView<const FTransform> Pose,const FMat3f& Heading,float* Upper)
{
    const auto& A=Impl.UpperArms[I]; const int32 O=60+15*I;
    WriteStateVec3(Upper,O,TransformRow(LocalUnrealToTraining(Pose[A.End].GetLocation()),Heading));
    WriteRot6(Multiply(MirrorYBasis(QuatToMatrix(Pose[A.End].GetRotation())),Heading),Upper+O+3);
    WriteRot6(Multiply(MirrorYBasis(QuatToMatrix(Pose[A.Start].GetRotation())),Heading),Upper+O+9);
}
bool CorrectInertiaArm(const AProphecyNNLocomotionManager::FImpl& Impl,AProphecyAgent* Actor,int32 I,
    float W,bool Attack,double Time,double Dt,const FTransform& PreviousRoot,const FTransform& Root,
    const FTransform& PreviousHand,const FTransform& Carrier,TArrayView<FTransform> Pose)
{
    const auto& A=Impl.UpperArms[I];
    FTransform Shoulder=Pose[A.Start]*Carrier,Elbow=Pose[A.Mid]*Carrier,Wrist=Pose[A.End]*Carrier;
    const FVector Pole=Shoulder.GetRotation().RotateVector(LocalTrainingToUnreal(A.LocalPoleAxes[0]));
    if (!ProphecyHandInertia::Apply(Actor,I,W,Attack,Time,Dt,PreviousRoot,Root,PreviousHand,
        Shoulder,Elbow,Wrist,Pole,A.Lengths.Y*100.)) return false;
    Pose[A.Start]=Shoulder.GetRelativeTransform(Carrier);
    Pose[A.Mid]=Elbow.GetRelativeTransform(Carrier);
    Pose[A.End]=Wrist.GetRelativeTransform(Carrier);
    // Use the same hand-derived forearm twist as the ordinary decoder.
    const FMat3f Forearm=ForearmRotationFromHand(Impl.UpperLocalOffsets[A.End],
        LocalUnrealToTraining(Pose[A.End].GetLocation()-Pose[A.Mid].GetLocation()),A.LocalPoleAxes[1],
        MirrorYBasis(QuatToMatrix(Pose[A.End].GetRotation())));
    Pose[A.Mid].SetRotation(MatrixToQuat(MirrorYBasis(Forearm)));
    return true;
}
void MixHandRecoveryUpper(const ProphecyHandRecovery::FFrame& Recovery,float* Upper)
{
    for(int32 I=0;I<2;++I)
    {
        const int32 P=Recovery.Source[I],O=60+15*I;
        if(Recovery.Alpha[I]>=1 || !Recovery.Ready[P]) continue;
        const float* Source=Recovery.Upper[P];const float W=Recovery.Alpha[I];
        WriteStateVec3(Upper,O,FMath::Lerp(ReadStateVec3(Source,O),ReadStateVec3(Upper,O),W));
        for(int32 R:{O+3,O+9}) WriteRot6(QuatToMatrix(FQuat::Slerp(MatrixToQuat(MatrixFromRot6(Source+R)),
            MatrixToQuat(MatrixFromRot6(Upper+R)),W).GetNormalized()),Upper+R);
    }
}
float HandChainFollow(const ProphecyHandRecovery::FTempering* Temper,
    const ProphecyHandRecovery::FFrame* Recovery,int32 Hand,bool TwistOnly=false)
{
    float Follow=1.f;
    if (Temper)
    {
        const auto& T=Temper->Hand[Hand];
        Follow=TwistOnly?T.Rotation:FMath::Min3(T.XY,T.Z,T.Rotation);
    }
    if (Recovery && Recovery->Ready[Recovery->Source[Hand]]) Follow=FMath::Min(Follow,Recovery->Alpha[Hand]);
    return Follow;
}
// Core channels are already parent-local rotations, so FK preserves every
// attachment offset. Arm endpoints are heading-space values; carry them with
// their changed clavicles explicitly before applying spine-local hand controls.
void TemperCoreLocalState(const float* Previous,float* Upper,int32 Count,float Follow)
{
    if(Follow>=1) return;
    if(Follow==0) { FMemory::Memcpy(Upper,Previous,Count*6*sizeof(float));return; }
    for(int32 I=0;I<Count;++I) BlendStateRotation(Upper,Previous,I*6,1-Follow);
}
void CarryCoreArm(const AProphecyNNLocomotionManager::FImpl& Impl,int32 I,
    TArrayView<const FTransform> Before,TArrayView<FTransform> After,float* Upper)
{
    const auto& A=Impl.UpperArms[I];const int32 Parent=Impl.Parents[A.Start];
    for(int32 Bone:{A.Start,A.Mid,A.End})
        After[Bone]=Before[Bone].GetRelativeTransform(Before[Parent])*After[Parent];
    StoreInertiaArm(Impl,I,After,Impl.SeedRootRot,Upper);
}
void CorrectLocomotionHands(AProphecyNNLocomotionManager::FImpl* Impl,AProphecyAgent* Actor,int32 Index,double Time,double Dt,float CoreFollow)
{
    auto& Agent=Impl->Agents[Index];
    float* Upper=UpperStateSlice(Impl->UpperCurrentStateBuffer,Index);
    const auto* Recovery=ProphecyHandRecovery::Frame(Actor);
    const auto* Temper=ProphecyHandRecovery::Tempering(Actor);
    if (Recovery) MixHandRecoveryUpper(*Recovery,Upper);
    FTransform Pose[FullBodyBoneCount],Previous[FullBodyBoneCount];
    const FLocomotionClamps Unclamped;
    DecodeLocomotionPose(Impl,StateSlice(Impl->PublishedStateBuffer,Index),Upper,
        Agent.PublishedWalkWeight,MakeArrayView(Pose),nullptr,Unclamped,&Agent.PublishedLegWalkWeights);
    const bool CoreInertia=ProphecyUpperBodyInertia::Active(Actor);
    if(CoreFollow<1 || CoreInertia)
    {
        FTransform Candidate[FullBodyBoneCount];
        for(int32 B=0;B<FullBodyBoneCount;++B) Candidate[B]=Pose[B];
        TemperCoreLocalState(UpperStateSlice(Impl->UpperPreviousPublishedStateBuffer,Index),Upper,
            Impl->UpperCoreBoneNames.Num(),CoreFollow);
        DecodeLocomotionPose(Impl,StateSlice(Impl->PublishedStateBuffer,Index),Upper,
            Agent.PublishedWalkWeight,MakeArrayView(Pose),nullptr,Unclamped,&Agent.PublishedLegWalkWeights);
        if(CoreInertia)
        {
            const FTransform CoreCarrier=HandInertiaCarrier(Actor,HandInertiaRoot(Agent.PublishedRoot,Agent.PublishedYaw));
            ProphecyUpperBodyInertia::Apply(Actor,Impl->Parents,Impl->BodyNames,Impl->UpperCoreBoneNames,CoreCarrier,MakeArrayView(Pose),Dt);
            for(int32 I=0;I<Impl->UpperCoreBoneNames.Num();++I)
            {
                const int32 B=Impl->BodyNames.IndexOfByKey(Impl->UpperCoreBoneNames[I]),P=Impl->Parents[B];
                WriteRot6(MirrorYBasis(QuatToMatrix(Pose[B].GetRelativeTransform(Pose[P]).GetRotation())),Upper+I*6);
            }
        }
        for(int32 I=0;I<2;++I) CarryCoreArm(*Impl,I,MakeArrayView(Candidate),MakeArrayView(Pose),Upper);
        // Do not run a hand solve when only core tempering was requested.
        if(!Recovery && !Temper && !ProphecySlashReturn::Active(Actor) && !ProphecyHandInertia::IsActive(Actor,Agent.PublishedWalkWeight,false)) return;
    }
    DecodeLocomotionPose(Impl,StateSlice(Impl->PreviousPublishedStateBuffer,Index),
        UpperStateSlice(Impl->UpperPreviousPublishedStateBuffer,Index),Agent.PreviousPublishedWalkWeight,
        MakeArrayView(Previous),nullptr,Unclamped,&Agent.PreviousPublishedLegWalkWeights);
    const FTransform Root=HandInertiaRoot(Agent.PublishedRoot,Agent.PublishedYaw);
    const FTransform PrevRoot=HandInertiaRoot(Agent.PreviousPublishedRoot,Agent.PreviousPublishedYaw);
    const FTransform Carrier=HandInertiaCarrier(Actor,Root),PrevCarrier=HandInertiaCarrier(Actor,PrevRoot);
    // Sample the same decoded torso as the hand targets (not the rendered mesh,
    // which is one interpolation interval behind the policy publication).
    static const FName SpineName(TEXT("spine_05"));
    const int32 Spine=Temper ? Impl->BodyNames.IndexOfByKey(SpineName) : INDEX_NONE;
    const FTransform Reference=Spine!=INDEX_NONE ? Pose[Spine]*Carrier : Root;
    const FTransform PrevReference=Spine!=INDEX_NONE ? Previous[Spine]*PrevCarrier : PrevRoot;
    for (int32 I=0; I<2; ++I)
    {
        const auto& A=Impl->UpperArms[I];
        const bool TemperHand=Temper && !Temper->Hand[I].Normal();
        bool Changed=false;
        if (TemperHand || (Recovery && Recovery->Alpha[I]<1 && Recovery->Ready[Recovery->Source[I]]))
        {
            // Use rebased accepted NN endpoints/shoulder here: the component
            // cache can still belong to the old carrier after a root-only snap.
            // Only the missing forearm twist needs the real publication below.
            FTransform Shoulder=Pose[A.Start]*Carrier,Elbow=Pose[A.Mid]*Carrier,Wrist=Pose[A.End]*Carrier;
            const FTransform& From=TemperHand?PrevReference:PrevRoot;
            const FTransform& To=TemperHand?Reference:Root;
            const FTransform Target=TemperHand?ProphecyHandRecovery::TemperTarget(Temper->Hand[I],From,To,
                Previous[A.End]*PrevCarrier,Wrist):Wrist;
            auto Carry=[&](int32 Bone) { return (Previous[Bone]*PrevCarrier).GetRelativeTransform(From)*To; };
            ProphecyHandChain::Resolve(Carry(A.Start),Carry(A.Mid),Carry(A.End),Shoulder,Elbow,Wrist,Target,
                Shoulder.GetRotation().UnrotateVector(Elbow.GetLocation()-Shoulder.GetLocation()),
                LocalTrainingToUnreal(A.LocalPoleAxes[0]),HandChainFollow(Temper,Recovery,I));
            Pose[A.Start]=Shoulder.GetRelativeTransform(Carrier);Pose[A.Mid]=Elbow.GetRelativeTransform(Carrier);Pose[A.End]=Wrist.GetRelativeTransform(Carrier);
            Changed=true;
        }
        Changed|=CorrectInertiaArm(*Impl,Actor,I,Agent.PublishedWalkWeight,false,Time,Dt,PrevRoot,Root,
            Previous[A.End]*PrevCarrier,Carrier,MakeArrayView(Pose));
        if (Changed)
            StoreInertiaArm(*Impl,I,MakeArrayView(Pose),Impl->SeedRootRot,Upper);
    }
    if(ProphecySlashReturn::Active(Actor))
    {
        float IdleUpper[UpperStateDim];FTransform Idle[FullBodyBoneCount];
        SeedUpperIdleFromLower(StateSlice(Impl->PublishedStateBuffer,Index),*Impl,IdleUpper);
        DecodeLocomotionPose(Impl,StateSlice(Impl->PublishedStateBuffer,Index),IdleUpper,
            Agent.PublishedWalkWeight,MakeArrayView(Idle),nullptr,Unclamped,&Agent.PublishedLegWalkWeights);
        const auto& A=Impl->UpperArms[1];const auto& Left=Impl->UpperArms[0];
        const int32 Parent=Impl->Parents[A.Start];
        // Capture the neutral endpoint on the outgoing clavicle, before the
        // first recovery prediction turns it. ApplyPose uses this only once.
        const FTransform InitialNeutralWrist=Idle[A.End].GetRelativeTransform(Idle[Parent])*Previous[Parent];
        for(int32 B:{A.Start,A.Mid,A.End}) Idle[B]=Idle[B].GetRelativeTransform(Idle[Parent])*Pose[Parent];
        const int32 Neck=Impl->BodyNames.IndexOfByKey(FName(TEXT("neck_01")));
        auto TorsoFrame=[&](const FTransform* P)
        {
            const FVector Up=(P[Neck].GetLocation()-P[0].GetLocation()).GetSafeNormal();
            const FVector Across=P[A.Start].GetLocation()-P[Left.Start].GetLocation();
            const FVector Right=(Across-Up*FVector::DotProduct(Across,Up)).GetSafeNormal();
            return FTransform(FRotationMatrix::MakeFromYZ(Right,Up).ToQuat(),
                (P[A.Start].GetLocation()+P[Left.Start].GetLocation())*.5);
        };
        ProphecySlashReturn::ApplyPose(Actor,TorsoFrame(Pose),TorsoFrame(Previous),
            (Pose[A.Start].GetLocation()-Pose[Left.Start].GetLocation()).Length()*.5,
            Previous[A.Start],Previous[A.Mid],Previous[A.End],Idle[A.Start],Idle[A.Mid],Idle[A.End],InitialNeutralWrist,
            Pose[A.Start],Pose[A.Mid],Pose[A.End],LocalTrainingToUnreal(A.LocalPoleAxes[0]));
        StoreInertiaArm(*Impl,1,MakeArrayView(Pose),Impl->SeedRootRot,Upper);
    }
}

void BuildHandRecoveryUpperInput(const AProphecyNNLocomotionManager::FImpl& Impl,const float* Lower,
    const float* Current,const float* Base,float* In)
{
    float NextBase[UpperStateDim];BuildUpperBaseFromLower(Lower,Impl,NextBase);
    for(int32 J=0;J<UpperStateDim;++J) In[90+J]=NextBase[J]+Current[J]-Base[J];
    CleanUpperState(In+90);
    LowerTransformToHeading(Lower,0,3,Impl,In+198);
    LowerTransformToHeading(Lower,9,12,Impl,In+261);
    LowerTransformToHeading(Lower,25,28,Impl,In+270);
}
bool RunHandRecoverySources(AProphecyNNLocomotionManager* Manager,AProphecyNNLocomotionManager::FImpl* Impl,
    TArrayView<TObjectPtr<AProphecyAgent>> Actors)
{
    if (!ProphecyHandRecovery::HasRecovery()) return true;
    const auto* Clock=ProphecyAgentTime::Context(Manager);
    auto Eligible=[&](int32 I)
    { return (!Clock || Clock->Step->Due[I]) && Actors[I] && Actors[I]->bNNInferenceEnabled &&
        !Impl->Agents[I].Slash.bActive && !Impl->Agents[I].DefensePose; };
    for(int32 P=0;P<2;++P)
    {
        bool Needed=false;
        for(int32 I=0;I<Actors.Num();++I) if(Eligible(I))
            if(const auto* H=ProphecyHandRecovery::Frame(Actors[I])) Needed|=H->Need[P];
        if(!Needed) continue;
        TArray<float> Input=Impl->UpperInputBuffer,Output;
        Output.SetNumUninitialized(Impl->UpperOutputBuffer.Num());
        for(int32 I=0;I<Actors.Num();++I) if(Eligible(I))
        {
            auto* H=ProphecyHandRecovery::Frame(Actors[I]);if(!H || !H->Need[P]) continue;
            float* In=Input.GetData()+I*UpperInputDim;
            const float* Current=UpperStateSlice(Impl->UpperCurrentStateBuffer,I);
            const float* Base=UpperStateSlice(Impl->UpperCurrentBaseBuffer,I);
            BuildHandRecoveryUpperInput(*Impl,H->Lower[P],Current,Base,In);
            // Previous history, equipment, gaze and root window remain identical.
        }
        if(!Impl->UpperModel.Run(Input,Output))
        { UE_LOG(LogProphecyNNLocomotion,Error,TEXT("Hand recovery source inference failed"));Manager->SetActorTickEnabled(false);return false; }
        for(int32 I=0;I<Actors.Num();++I) if(Eligible(I))
        {
            auto* H=ProphecyHandRecovery::Frame(Actors[I]);if(!H || !H->Need[P]) continue;
            for(int32 J=0;J<UpperStateDim;++J) H->Upper[P][J]=Input[I*UpperInputDim+90+J]+Output[I*UpperStateDim+J];
            CleanUpperState(H->Upper[P]);H->Ready[P]=true;
        }
    }
    return true;
}
}

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCoreFKTest,"Prophecy.NN.CoreTempering.FKAndArmAttachment",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyCoreFKTest::RunTest(const FString&)
{
    float Previous[UpperStateDim],Candidate[UpperStateDim],Mixed[UpperStateDim];
    for(int32 I=0;I<UpperStateDim;++I) Previous[I]=Candidate[I]=float(I)*.01f;
    for(int32 I=0;I<10;++I)
    {
        WriteRot6(QuatToMatrix(FRotator(I*2-10,I*3+15,175-I).Quaternion()),Previous+I*6);
        WriteRot6(QuatToMatrix(FRotator(I*3+10,I*5-20,-175+I).Quaternion()),Candidate+I*6);
    }
    // Slots are spine01..05, neck01/02, head, clavicle L/R. Pelvis is external.
    const int32 Parent[10]={-1,0,1,2,3,4,5,6,4,4};
    for(float Follow:{0.f,.1f,.5f,.9f,1.f})
    {
        FMemory::Memcpy(Mixed,Candidate,sizeof(Mixed));TemperCoreLocalState(Previous,Mixed,10,Follow);
        if(Follow==0) TestTrue(TEXT("Zero preserves all ten local rotations exactly"),FMemory::Memcmp(Mixed,Previous,60*sizeof(float))==0);
        if(Follow==1) TestTrue(TEXT("Normal is bit-identical without conversion"),FMemory::Memcmp(Mixed,Candidate,sizeof(Mixed))==0);
        TestTrue(TEXT("Only core state slots are changed by rotation interpolation"),FMemory::Memcmp(Mixed+60,Candidate+60,30*sizeof(float))==0);
        FTransform World[10];
        const FTransform Pelvis(FRotator(25,80,-15),FVector(300,-100,90));
        for(int32 I=0;I<10;++I)
        {
            const FQuat A=MatrixToQuat(MatrixFromRot6(Previous+I*6)),B=MatrixToQuat(MatrixFromRot6(Candidate+I*6));
            const FQuat Actual=MatrixToQuat(MatrixFromRot6(Mixed+I*6));
            TestTrue(TEXT("Each joint uses shortest-arc parent-local slerp"),Actual.AngularDistance(FQuat::Slerp(A,B,Follow))<1.e-5);
            const FTransform& P=Parent[I]<0?Pelvis:World[Parent[I]];
            const FVector Offset(I>=8?8:0,I==8?-5:I==9?5:0,7);
            World[I]=FTransform(Actual,Offset)*P;
            TestTrue(TEXT("Changing joint bends preserves FK parent-space attachment"),World[I].GetRelativeTransform(P).GetLocation().Equals(Offset,1.e-6));
        }
    }
    AProphecyNNLocomotionManager::FImpl Impl;Impl.SeedRootRot=YawMatrix(.6f);Impl.Parents.Init(INDEX_NONE,8);
    FTransform Before[8],After[8];float Upper[UpperStateDim]={};
    for(int32 I=0;I<2;++I)
    {
        const int32 C=I*4;auto& Arm=Impl.UpperArms[I];Arm.Start=C+1;Arm.Mid=C+2;Arm.End=C+3;Impl.Parents[Arm.Start]=C;
        Before[C]=FTransform(FRotator(20,30,-10),FVector(10,I*20,50));
        After[C]=FTransform(FRotator(-30,100,40),FVector(-20,I*40,70));
        for(int32 B:{Arm.Start,Arm.Mid,Arm.End}) Before[B]=FTransform(FRotator(10*B,5*B,-3*B),FVector(12*B,4*B,6))*Before[C];
        CarryCoreArm(Impl,I,MakeArrayView(Before),MakeArrayView(After),Upper);
        for(int32 B:{Arm.Start,Arm.Mid,Arm.End})
            TestTrue(TEXT("Attached arm retains its complete clavicle-local pose"),
                After[B].GetRelativeTransform(After[C]).Equals(Before[B].GetRelativeTransform(Before[C]),1.e-6));
        const FVector Stored=LocalTrainingToUnreal(TransformRow(ReadStateVec3(Upper,60+15*I),Transpose(Impl.SeedRootRot)));
        TestTrue(TEXT("Carried wrist is encoded in accepted NN state, not presentation only"),Stored.Equals(After[Arm.End].GetLocation(),1.e-3));
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyHandSourceInputTest,"Prophecy.NN.HandRecovery.SourceInputsAndIsolation",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyHandSourceInputTest::RunTest(const FString&)
{
    AProphecyNNLocomotionManager::FImpl Impl;
    Impl.SeedRootRot=YawMatrix(0);Impl.RestOffsetsFromPelvis.SetNumZeroed(2);
    Impl.UpperArms[0].End=0;Impl.UpperArms[1].End=1;
    float Lower[StateDim]={},Base[UpperStateDim],Input[UpperInputDim],Original[UpperInputDim];
    for(int32 R:{3,12,18,28,34}) WriteRot6(YawMatrix(0),Lower+R);
    BuildUpperBaseFromLower(Lower,Impl,Base);
    for(int32 J=0;J<UpperInputDim;++J) Input[J]=Original[J]=float(J)/1000;
    WriteStateVec3(Lower,0,FVector3f(1,2,3));WriteStateVec3(Lower,9,FVector3f(4,5,6));WriteStateVec3(Lower,25,FVector3f(7,8,9));
    BuildHandRecoveryUpperInput(Impl,Lower,Base,Base,Input);
    for(int32 J=0;J<UpperInputDim;++J)
        if(!(J>=90&&J<180) && !(J>=198&&J<207) && !(J>=261&&J<279))
            TestEqual(TEXT("History/current pelvis/feet, root, equipment and gaze unchanged"),Input[J],Original[J]);
    TestTrue(TEXT("Future pelvis and both feet come from selected source"),ReadStateVec3(Input,198)==FVector3f(1,2,3) &&
        ReadStateVec3(Input,261)==FVector3f(4,5,6) && ReadStateVec3(Input,270)==FVector3f(7,8,9));
    ProphecyHandRecovery::FFrame H;H.Ready[0]=H.Ready[1]=true;H.Source[0]=1;H.Source[1]=0;H.Alpha[0]=.25f;H.Alpha[1]=1;
    for(int32 P=0;P<2;++P) FMemory::Memcpy(H.Upper[P],Base,sizeof(Base));
    WriteStateVec3(H.Upper[1],60,FVector3f(4,8,12));
    float Mixed[UpperStateDim];FMemory::Memcpy(Mixed,Base,sizeof(Base));MixHandRecoveryUpper(H,Mixed);
    TestTrue(TEXT("Selected left arm alone blends source to normal"),ReadStateVec3(Mixed,60).Equals(FVector3f(3,6,9),1.e-6f));
    TestTrue(TEXT("Core and normal right arm remain bit-identical"),FMemory::Memcmp(Mixed,Base,60*sizeof(float))==0 &&
        FMemory::Memcmp(Mixed+75,Base+75,15*sizeof(float))==0);
    H.Alpha[0]=1;FMemory::Memcpy(Mixed,Base,sizeof(Base));MixHandRecoveryUpper(H,Mixed);
    TestTrue(TEXT("Completed mix is exact normal"),FMemory::Memcmp(Mixed,Base,sizeof(Base))==0);
    return !HasAnyErrors();
}
#endif
