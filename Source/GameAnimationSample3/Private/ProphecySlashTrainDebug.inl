// Explicit diagnostic node only; no tick hooks or normal-path lookups.
bool AProphecyNNLocomotionManager::SetSlashTrainStartingPose(FProphecyAgentHandle Handle,FString& OutError)
{
    OutError.Reset();
#if UE_BUILD_SHIPPING
    OutError=TEXT("Slash train seeding is development-only.");return false;
#else
    auto* Actor=ResolveAgent(Handle);
    if (!IsInGameThread() || !Actor || !Impl || !Impl->bInitialized || IsSimBridgeActive())
    { OutError=TEXT("Initialize the native NN agent first.");return false; }
    auto& A=Impl->Agents[Handle.Index];
    if (Actor->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic || A.Slash.bActive || A.DefensePose || A.AnimationLayer.IsActive())
    { OutError=TEXT("Seed an idle kinematic agent before its first special.");return false; }
    FString Text;TSharedPtr<FJsonObject> Data;
    if (!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectDir()/TEXT("Tools/NN/Fixtures/SlashTrain2026092223.json"))) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data) || !Data.IsValid())
    { OutError=TEXT("Missing slash train initial-history fixture.");return false; }
    const TSharedPtr<FJsonObject>* History=nullptr;
    if (!Data->TryGetObjectField(TEXT("initial_history"),History))
    { OutError=TEXT("Re-extract the slash train fixture with initial history.");return false; }
    const auto& Names=(*History)->GetArrayField(TEXT("bone_names"));
    const auto& Positions=(*History)->GetArrayField(TEXT("positions"));
    const auto& Rotations=(*History)->GetArrayField(TEXT("rotations"));
    SlashTrainFrame::FFrame Reference;
    const TArray<TSharedPtr<FJsonValue>>* ReferenceP=nullptr;const TArray<TSharedPtr<FJsonValue>>* ReferenceR=nullptr;
    if (!(*History)->TryGetArrayField(TEXT("reference_position"),ReferenceP) ||
        !(*History)->TryGetArrayField(TEXT("reference_rotation"),ReferenceR) || ReferenceR->Num()!=3 ||
        !JsonVec3(*ReferenceP,Reference.Position))
    { OutError=TEXT("Re-extract the slash train reference frame.");return false; }
    for (int32 Row=0;Row<3;++Row) if (!JsonVec3((*ReferenceR)[Row]->AsArray(),Reference.Rotation.Rows[Row]))
    { OutError=TEXT("Invalid slash train reference rotation.");return false; }
    if (Names.Num()!=FullBodyBoneCount || Positions.Num()!=2 || Rotations.Num()!=2)
    { OutError=TEXT("Invalid seed dimensions.");return false; }
    TArray<FTransform> Poses[2];
    for (int32 F=0;F<2;++F)
    {
        Poses[F].SetNum(FullBodyBoneCount);
        const auto& P=Positions[F]->AsArray();const auto& R=Rotations[F]->AsArray();
        if (P.Num()!=FullBodyBoneCount || R.Num()!=FullBodyBoneCount) { OutError=TEXT("Invalid seed bone count.");return false; }
        TSet<int32> Seen;
        for (int32 B=0;B<FullBodyBoneCount;++B)
        {
            const int32 I=Impl->BodyNames.IndexOfByKey(FName(Names[B]->AsString()));
            const auto& V=P[B]->AsArray();const auto& M=R[B]->AsArray();
            if (I==INDEX_NONE || Seen.Contains(I) || V.Num()!=3 || M.Num()!=3)
            { OutError=TEXT("Invalid seed bone mapping.");return false; }
            Seen.Add(I);FMat3f Rotation;
            for (int32 Row=0;Row<3;++Row)
            {
                const auto& Values=M[Row]->AsArray();if (Values.Num()!=3) { OutError=TEXT("Invalid rotation.");return false; }
                for (int32 Col=0;Col<3;++Col) Rotation.Rows[Row][Col]=float(Values[Col]->AsNumber());
            }
            const FVector3f Position(float(V[0]->AsNumber()),float(V[1]->AsNumber()),float(V[2]->AsNumber()));
            Poses[F][I]=FTransform(MatrixToQuat(MirrorYBasis(Rotation)),LocalTrainingToUnreal(Position));
            if (Poses[F][I].ContainsNaN()) { OutError=TEXT("Non-finite seed pose.");return false; }
        }
    }
    const int32 I=Handle.Index;
    // A fresh stationary carrier, with actual two-pose skeletal velocity retained.
    ProphecyNNAgentReset::FCheckpoint Root;Root.Root=A.PublishedRoot;Root.Yaw=A.PublishedYaw;Root.bWalk=A.bUseWalkPolicy;
    ProphecyNNAgentReset::ClearMotion(A,Root,1.f/FMath::Max(1.f,NNUpdateHz));
    ProphecyWalkPinning::ResetSmoothing(Actor);
    const FTransform Carrier=SlashComponentWorld(Actor,A.PublishedRoot,A.PublishedYaw);
    Reference.Anchor=Carrier;Reference.RemainingAttacks=Data->GetArrayField(TEXT("rows")).Num();
    SlashTrainFrame::Set(Actor,Reference);
    float Lower[2][StateDim],Upper[2][UpperStateDim];
    for (int32 F=0;F<2;++F) EncodeComponentPoseToNNStates(*Impl,A,Poses[F],Lower[F],Upper[F]);
    auto CopyLower=[&](TArray<float>& Buffer,int32 F) { FMemory::Memcpy(StateSlice(Buffer,I),Lower[F],sizeof(Lower[F])); };
    CopyLower(Impl->PrevStateBuffer,0);CopyLower(Impl->CurStateBuffer,1);CopyLower(Impl->NextStateBuffer,1);
    CopyLower(Impl->PreviousPublishedStateBuffer,0);CopyLower(Impl->PublishedStateBuffer,1);
    CopyLower(Impl->PreviousPhysicalStateBuffer,0);CopyLower(Impl->PhysicalStateBuffer,1);
    auto CopyUpper=[&](TArray<float>& Buffer,int32 F) { FMemory::Memcpy(UpperStateSlice(Buffer,I),Upper[F],sizeof(Upper[F])); };
    CopyUpper(Impl->UpperPreviousStateBuffer,0);CopyUpper(Impl->UpperCurrentStateBuffer,1);
    CopyUpper(Impl->UpperPreviousPublishedStateBuffer,0);CopyUpper(Impl->UpperPublishedStateBuffer,1);
    CopyUpper(Impl->UpperPreviousPhysicalStateBuffer,0);CopyUpper(Impl->UpperPhysicalStateBuffer,1);
    BuildUpperBaseFromLower(Lower[1],*Impl,UpperStateSlice(Impl->UpperCurrentBaseBuffer,I));
    BuildUpperBaseFromLower(Lower[1],*Impl,UpperStateSlice(Impl->UpperNextBaseBuffer,I));
    LowerTransformToHeading(Lower[0],0,3,*Impl,TransformStateSlice(Impl->PreviousPelvisHeadingBuffer,I));
    LowerTransformToHeading(Lower[1],0,3,*Impl,TransformStateSlice(Impl->CurrentPelvisHeadingBuffer,I));
    auto Previous=TransformSlice(Impl->PreviousComponentTransformBuffer,I);
    auto Current=TransformSlice(Impl->ComponentTransformBuffer,I);
    auto Local=TransformSlice(Impl->LocalTransformBuffer,I);
    for (int32 B=0;B<FullBodyBoneCount;++B)
    {
        Previous[B]=Poses[0][B];Current[B]=Poses[1][B];
        Local[B]=Impl->Parents[B]==INDEX_NONE?Current[B]:Current[B].GetRelativeTransform(Current[Impl->Parents[B]]);
    }
    const int32 PoseId=PoseStoreAgentBase+I;
    A.PublishedPoseTimeSeconds=GetWorld()->GetTimeSeconds();
    FProphecyNNPoseStore::ClearAgentPose(PoseId);
    FProphecyNNPoseStore::SetInterpolationMode(PoseId,Actor->GetNNInterpolationMode());
    FProphecyNNPoseStore::SetAgentLocalPose(PoseId,Impl->PublishedBoneNames,Local,Previous,Current,
        Carrier,Carrier,A.PublishedPoseTimeSeconds,true,false,0.f,FVector2D::ZeroVector);
    ProphecyNNPresentation::Publish(PoseId,A.PublishedPoseTimeSeconds,1.f);
    return true;
#endif
}
