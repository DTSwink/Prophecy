// Shared optional defense path. Included after the normal locomotion/attack
// implementations so all coordinate conversions stay at the UE boundary.
namespace
{
    ProphecyDefense::FRows DefenseAxes(const FQuat& Q)
    {
        auto Axis=[&](const FVector& V) { const auto W=Q.RotateVector(V);return FVector3f(W.X,W.Z,W.Y); };
        return {{Axis(FVector(1,0,0)),Axis(FVector(0,-1,0)),Axis(FVector(0,0,1))}};
    }
    ProphecyDefense::FRootFrame DefenseRoot(const FTransform& Carrier)
    { return {UnrealToTraining(Carrier.GetTranslation()),DefenseAxes(Carrier.GetRotation())}; }
    void DefenseRoot12(const ProphecyDefense::FRootFrame& Root,float* Out)
    { ProphecyDefense::Write(Out,Root.P);for (int32 I=0;I<3;++I) ProphecyDefense::Write(Out+3+I*3,Root.R.V[I]); }
    void DefenseWorldPose(const FTransform* World,const int32* Bones,ProphecyDefense::FPose& Out)
    {
        for (int32 I=0;I<25;++I) { Out.P[I]=UnrealToTraining(World[Bones[I]].GetTranslation());Out.R[I]=DefenseAxes(World[Bones[I]].GetRotation()); }
    }
    ProphecyDefense::FDefenseBox DefenseAttackSample(const FProphecyLiveDefenseRuntime& D,const FTransform* World,int32 Box,float* Pelvis9)
    {
        // Attacker conditioning needs its pelvis and ONE collider, not a full
        // second body collision pass for each defender observing this attack.
        ProphecyDefense::FPose Pose;
        auto Bone=[&](int32 I) { Pose.P[I]=UnrealToTraining(World[D.Bones[I]].GetTranslation());Pose.R[I]=DefenseAxes(World[D.Bones[I]].GetRotation()); };
        Bone(0);
        if (Pelvis9) { ProphecyDefense::Write(Pelvis9,Pose.P[0]);ProphecyDefense::Write(Pelvis9+3,Pose.R[0].V[0]);ProphecyDefense::Write(Pelvis9+6,Pose.R[0].V[1]); }
        const int32 I=D.AttackContacts.Boxes[Box].Bone;Bone(I);
        return D.AttackContacts.BuildAttachedBox(Pose.P[I],Pose.R[I],Box);
    }
    void DefenseComponentPose(const ProphecyDefense::FPose& World,const ProphecyDefense::FRootFrame& Root,const int32* Bones,FTransform* Out)
    {
        using namespace ProphecyDefense;
        for (int32 I=0;I<25;++I)
        {
            FMat3f R;for (int32 J=0;J<3;++J) R.Rows[J]=InTransposedBasis(World.R[I].V[J],Root.R);
            Out[Bones[I]]=FTransform(MatrixToQuat(MirrorYBasis(R)),LocalTrainingToUnreal(InTransposedBasis(World.P[I]-Root.P,Root.R)));
        }
    }
    void DefenseUpperToLocomotion(const float* Input,const FMat3f& Seed,float* Out)
    {
        FMemory::Memcpy(Out,Input,90*sizeof(float));
        for (int32 O:{60,75})
        {
            WriteStateVec3(Out,O,TransformRow(ReadStateVec3(Input,O),Seed));
            for (int32 K:{3,9}) WriteRot6(Multiply(MatrixFromRot6(Input+O+K),Seed),Out+O+K);
        }
    }
    int32 DefenseAttackCollider(const FProphecyLiveDefenseRuntime& D,const AProphecyNNLocomotionManager::FImpl::FAgent::FSlashAttack& Attack)
    {
        // The harness labels pike as a sword thrust and samples the same hand_r
        // blade box as slash. Synthetic spear is a distinct projectile source.
        if (Attack.State.Num()<270) return INDEX_NONE;
        FName Name=TEXT("blade");
        if (Attack.State[269]>.5f) Name=TEXT("head");
        else if (Attack.State[268]>.5f) Name=Attack.Family==TEXT("kickl")?TEXT("calf_l"):TEXT("calf_r");
        else if (Attack.State[267]>.5f)
        {
            const FString Family=Attack.Family.ToString();Name=Family.EndsWith(TEXT("l"),ESearchCase::IgnoreCase)?TEXT("lowerarm_l"):TEXT("lowerarm_r");
        }
        for (int32 I=0;I<D.AttackContacts.Count;++I) if (D.AttackContacts.Boxes[I].Name==Name) return I;
        return INDEX_NONE;
    }

    bool DefensePhysicalStop(AProphecyNNLocomotionManager::FImpl& Impl,FProphecyLiveDefensePose& P,
        const ProphecyDefense::FPose& Before,const ProphecyDefense::FPose& After,const FVector3f& Origin)
    {
        auto* Actor=P.Owner.Get();auto* Attacker=P.Attacker.Get();
        if (Actor->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic)
        {
            P.Order={};
            P.Status.ContactCollider=NAME_None;P.Status.ContactTimeSeconds=-1;return false;
        }
        auto& D=*Impl.Defense;
        if (!P.PhysicalContacts && !P.bPhysicalContactsFailed)
        {
            auto Contacts=MakeShared<FProphecyDefensePhysicalContacts>();FString Error;
            if (Contacts->Build(*Actor,*Attacker,D.AttackContacts.Boxes[P.AttackerCollider].Name,Impl.BodyNames,Error))
                P.PhysicalContacts=MoveTemp(Contacts);
            else
            {
                P.bPhysicalContactsFailed=true;
                UE_LOG(LogProphecyNNLocomotion,Error,TEXT("PHAT defense contact setup failed for %s: %s"),*Actor->GetName(),*Error);
            }
        }
        if (!P.PhysicalContacts) return false;
        FTransform Previous[25],Current[25];
        auto Convert=[&](const ProphecyDefense::FPose& Pose,FTransform* Out)
        {
            for (int32 I=0;I<25;++I)
            {
                const auto& R=Pose.R[I];const FVector X(R.V[0].X,R.V[0].Z,R.V[0].Y),Y(-R.V[1].X,-R.V[1].Z,-R.V[1].Y);
                const auto V=Pose.P[I]+Origin;
                Out[D.Bones[I]]=FTransform(FRotationMatrix::MakeFromXY(X,Y).ToQuat(),FVector(V.X,V.Z,V.Y)*100.);
            }
        };
        Convert(Before,Previous);Convert(After,Current);
        const auto& Attack=Impl.Agents[P.AttackerIndex].Slash;
        P.PhysicalContacts->Sweep(Previous,Current,Attack.PreviousVisibleWorldPose.GetData(),Attack.VisibleWorldPose.GetData(),P.Order,P.Status.CompletedSteps);
        const int32 Contact=P.Order.Collider;
        if (Contact==INDEX_NONE) return false;
        P.Status.ContactCollider=P.PhysicalContacts->Defender[Contact].Name;
        P.Status.ContactTimeSeconds=float(P.Order.Time/30.);
        return true;
    }
}

namespace
{
bool InitializeDefenseRuntime(AProphecyNNLocomotionManager::FImpl& Impl,FString& Error)
{
    if (!Impl.Defense) Impl.Defense=MakeUnique<FProphecyLiveDefenseRuntime>();
    auto& D=*Impl.Defense;
    if (!D.bInitialized)
    {
        const FString Dir=FPaths::ProjectContentDir()/TEXT("locomotion/NN/defense");
        if (!D.Geometry.Load(Dir/TEXT("parry_skeleton.json"),false,Error) || !D.Contacts.Load(Dir/TEXT("parry_colliders.json"),Error)
            || !D.AttackContacts.Load(Dir/TEXT("attacker_colliders.json"),Error,true)) return false;
        static const FName Names[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),
            TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),
            TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
        for (int32 I=0;I<25;++I) { D.Bones[I]=Impl.BodyNames.IndexOfByKey(Names[I]);if (D.Bones[I]==INDEX_NONE) { Error=TEXT("Defense skeleton bone is missing.");return false; } }
        D.bInitialized=true;
    }
    return true;
}
}

bool AProphecyNNLocomotionManager::StartAgentNNParry(FProphecyAgentHandle Handle,AProphecyAgent* Attacker,
    float MaximumSeconds,FString& Error)
{
    AProphecyAgent* Actor=ResolveAgent(Handle);
    if (!Actor || !IsValid(Attacker) || Actor==Attacker || ResolveAgent(Attacker->GetAgentHandle())!=Attacker
        || !Actor->bNNInferenceEnabled || !Attacker->bNNInferenceEnabled || !FMath::IsFinite(MaximumSeconds) || MaximumSeconds<=0)
    { Error=TEXT("Parry needs two distinct, initialized agents in this manager and a positive duration.");return false; }
    if (!FMath::IsNearlyEqual(NNUpdateHz,30.f)) { Error=TEXT("This saved defense checkpoint requires the 30 Hz policy clock.");return false; }
    auto& Agent=Impl->Agents[Handle.Index];const int32 AttackerIndex=Attacker->GetAgentHandle().Index;const auto& Attack=Impl->Agents[AttackerIndex].Slash;
    if (!Attack.bActive || Attack.VisibleWorldPose.Num()!=25 || Attack.State.Num()!=SlashInputDim)
    { Error=TEXT("Start the incoming attack first.");return false; }
    if (Attack.HitFrame!=INDEX_NONE)
    { Error=TEXT("The incoming attack has already output Hit; its parry window has ended.");return false; }
    if (Attack.State[270]<=0.5f)
    {
        StopAgentNNDefense(Handle);
        ProphecyDefenseArmedGate::Queue(this,Actor,Attacker,false,MaximumSeconds);
        Error.Reset();return true;
    }
    if (Agent.AnimationLayer.IsActive())
    { Error=TEXT("Defender has an active animation layer.");return false; }
    if (!InitializeDefenseRuntime(*Impl,Error)) return false;
    auto& D=*Impl->Defense;
    if (!D.bParryReady)
    {
        if (!D.ParryNetwork.Initialize(FPaths::ProjectContentDir()/TEXT("locomotion/NN/defense/prophecy_parry_upper.onnx"),258,90,Error)) return false;
        D.bParryReady=true;
    }
    const int32 AttackCollider=DefenseAttackCollider(D,Attack);
    const bool Drawn=IsValid(Actor->GetHeldSword());
    if (AttackCollider==INDEX_NONE)
    { Error=TEXT("Unsupported attack collider.");return false; }
    ProphecyDefenseArmedGate::Cancel(Actor);
    if (Agent.Slash.bActive) StopAgentNNAttack(Handle, false);
    PublishAgentPose(Handle.Index,Agent.PublishedPoseTimeSeconds);
    const auto* History=ProphecyDefenseArmedGate::ActivationHistory(Actor);
    auto New=MakeUnique<FProphecyLiveParry>();auto& P=*New;
    P.Owner=Actor;P.Attacker=Attacker;P.AttackerIndex=AttackerIndex;P.AttackerCollider=AttackCollider;P.Family=Attack.Family;
    P.AttackerHalf=D.AttackContacts.Boxes[AttackCollider].Half;P.MaxSteps=FMath::Clamp(FMath::CeilToInt(MaximumSeconds*30),1,18000);
    P.PresentMask=D.Contacts.PresentMask(Drawn);P.Context.TargetWorld=UnrealToTraining(Attack.TargetWorld);
    FMemory::Memcpy(P.Context.AttackControls,Attack.State.GetData()+265,5*sizeof(float));
    float L[2][41],U[2][90],Roots[2][12],Base[90];ProphecyDefense::FPose BasePose;
    for (int32 I=0;I<2;++I)
    {
        const TArrayView<const FTransform> Pose=History?MakeArrayView(History->Pose[I]):TArrayView<const FTransform>(TransformSlice(I?Impl->ComponentTransformBuffer:Impl->PreviousComponentTransformBuffer,Handle.Index));
        EncodeSlashPose(*Impl,Agent,Pose,L[I],U[I]);
        const auto Root=DefenseRoot(SlashComponentWorld(Actor,History?History->Root[I]:(I?Agent.PublishedRoot:Agent.PreviousPublishedRoot),History?History->Yaw[I]:(I?Agent.PublishedYaw:Agent.PreviousPublishedYaw)));
        DefenseRoot12(Root,Roots[I]);
        for (int32 J=0;J<25;++J) (I?P.CurrentComponent:P.PreviousComponent)[J]=Pose[J];
        if (I) { D.Geometry.LowerPose(L[I],Root.P,Root.R,BasePose);D.Geometry.EncodeUpper(BasePose,Root.P,Root.R,Base); }
    }
    P.State.Initialize(L[0],U[0],Roots[0],L[1],U[1],Roots[1],Base);
    FTransform World[25];const auto Carrier=SlashComponentWorld(Actor,History?History->Root[1]:Agent.PublishedRoot,History?History->Yaw[1]:Agent.PublishedYaw);
    for (int32 I=0;I<25;++I) World[I]=P.CurrentComponent[I]*Carrier;
    DefenseWorldPose(World,D.Bones,P.CurrentPose);D.Contacts.Build(P.CurrentPose,P.PreviousBoxes);
    P.PreviousAttack=DefenseAttackSample(D,(History?Attack.PreviousVisibleWorldPose:Attack.VisibleWorldPose).GetData(),AttackCollider,nullptr);
    P.Status.Active=true;P.Status.AttackerFrame=Attack.Frame-(History?1:0);P.bHasPose=true;
    if (Agent.DefensePose) StopAgentNNDefense(Handle, false);
    D.Dodges.Remove(Handle.Index);
    ProphecyAttackRecovery::Cancel(Actor);
    Agent.DefensePose=New.Get();D.Parries.Add(Handle.Index,MoveTemp(New));++D.ActiveCount;
    ProphecyLimbCollision::DefenseChanged(Actor,true);Error.Reset();return true;
}

void AProphecyNNLocomotionManager::RebaseDefenseAfterRootCollision(int32 Index,const FVector3f& PreviousRoot,float PreviousYaw,const FVector3f& Root,float Yaw)
{
    using namespace ProphecyDefense;
    auto& Agent=Impl->Agents[Index];auto& P=*Agent.DefensePose;const AProphecyAgent* Actor=AgentActors[Index];
    const auto PreviousCarrier=SlashComponentWorld(Actor,Agent.PreviousPublishedRoot,Agent.PreviousPublishedYaw);
    const auto CurrentCarrier=SlashComponentWorld(Actor,Agent.PublishedRoot,Agent.PublishedYaw);
    const auto NewCarrier=SlashComponentWorld(Actor,Root,Yaw);
    auto Before=DefenseRoot(SlashComponentWorld(Actor,PreviousRoot,PreviousYaw));auto Current=DefenseRoot(NewCarrier);
    if (P.bDodge)
    {
        auto& Dodge=static_cast<FProphecyLiveDodge&>(P);Before.P-=Dodge.WorldOrigin;Current.P-=Dodge.WorldOrigin;
    }
    auto Rebase=[&](float* Lower,float* Upper,FRootFrame& Old,const FRootFrame& New)
    {
        RebaseLower(Lower,Lower,Old.P,Old.R,New.P,New.R);RebaseUpper(Upper,Upper,Old.P,Old.R,New.P,New.R);Old=New;
    };
    if (P.bDodge)
    {
        auto& S=static_cast<FProphecyLiveDodge&>(P).State;
        Rebase(S.PreviousLower,S.PreviousUpper,S.PreviousRoot,Before);Rebase(S.CurrentLower,S.CurrentUpper,S.CurrentRoot,Current);
    }
    else
    {
        auto& S=static_cast<FProphecyLiveParry&>(P).State;
        RebaseUpper(S.CurrentBaseline,S.CurrentBaseline,S.CurrentRoot.P,S.CurrentRoot.R,Current.P,Current.R);
        Rebase(S.PreviousLower,S.PreviousUpper,S.PreviousRoot,Before);Rebase(S.CurrentLower,S.CurrentUpper,S.CurrentRoot,Current);
    }
    for (int32 I=0;I<25;++I)
    {
        P.PreviousComponent[I]=(P.PreviousComponent[I]*PreviousCarrier).GetRelativeTransform(NewCarrier);
        P.CurrentComponent[I]=(P.CurrentComponent[I]*CurrentCarrier).GetRelativeTransform(NewCarrier);
    }
}

EProphecyAgentState AProphecyNNLocomotionManager::GetAgentActivityState(FProphecyAgentHandle Handle) const
{
    if (!ResolveAgent(Handle)) return EProphecyAgentState::Locomotion;
    const auto& Agent=Impl->Agents[Handle.Index];
    if (Agent.DefensePose && Agent.DefensePose->Status.Active)
        return Agent.DefensePose->bDodge ? EProphecyAgentState::Dodging : EProphecyAgentState::Parrying;
    return Agent.Slash.bActive ? EProphecyAgentState::Attacking : EProphecyAgentState::Locomotion;
}

bool AProphecyNNLocomotionManager::StopAgentNNDefense(FProphecyAgentHandle Handle, bool bReturnToLocomotion)
{
    AProphecyAgent* Actor=ResolveAgent(Handle);
    if (!Actor) return false;
    const bool bCancelled=ProphecyDefenseArmedGate::Cancel(Actor);
    if (!Impl->Agents[Handle.Index].DefensePose) return bCancelled;
    auto& Agent=Impl->Agents[Handle.Index];
    FVector ReturnTarget;
    if (bReturnToLocomotion && ProphecyRootBalance::GetFlatFeetTarget(Actor,ReturnTarget))
        SetAgentLocomotionRootWindowLocation(Handle,ReturnTarget,true);
    if (Agent.DefensePose->bDodge)
    {
        --Impl->Defense->ActiveDodgeCount;Agent.bHasPhysicalSample=false;
        if (auto* Smoothing=ProphecyNNRootWindow::Find(ResolveAgent(Handle)))
            for (auto& Sample:Smoothing->Samples) Sample.bInitialized=false;
    }
    Agent.DefensePose->Status.Active=false;Agent.DefensePose=nullptr;
    if (bReturnToLocomotion) ProphecyRootPelvisBounds::ResetMagicCubeToRoot(Actor);
    ProphecyLimbCollision::DefenseChanged(ResolveAgent(Handle),false);
    --Impl->Defense->ActiveCount;return true;
}
bool AProphecyNNLocomotionManager::GetAgentNNDefenseStatus(FProphecyAgentHandle Handle,FProphecyNNDefenseStatus& Status) const
{
    Status={};if (!ResolveAgent(Handle)) return false;
    if (ProphecyDefenseArmedGate::IsWaiting(ResolveAgent(Handle))) return true;
    if (!Impl->Defense) return false;
    if (const auto* P=Impl->Defense->Parries.Find(Handle.Index))
        if ((*P)->Owner.Get()==ResolveAgent(Handle)) { Status=(*P)->Status;return true; }
    if (const auto* P=Impl->Defense->Dodges.Find(Handle.Index))
        if ((*P)->Owner.Get()==ResolveAgent(Handle)) { Status=(*P)->Status;return true; }
    return false;
}

void AProphecyNNLocomotionManager::GetAgentAttackDefenseState(FProphecyAgentHandle Handle,bool& bParry,bool& bDodge) const
{
    bParry=bDodge=false;
    const auto* Actor=ResolveAgent(Handle);
    if (!Actor || !Impl->Agents[Handle.Index].Slash.bActive) return;
    const auto* Victim=ProphecyDefenseArmedGate::GetVictim(Actor);
    ProphecyDefenseArmedGate::WaitingResponses(Actor,Victim,bParry,bDodge);
    if (!Impl->Defense) return;
    for (const auto& Pair:Impl->Defense->Parries)
        if (Pair.Value->Status.Active && Pair.Value->Owner.IsValid() && Pair.Value->Attacker.Get()==Actor && (!Victim || Pair.Value->Owner.Get()==Victim)) bParry=true;
    for (const auto& Pair:Impl->Defense->Dodges)
        if (Pair.Value->Status.Active && Pair.Value->Owner.IsValid() && Pair.Value->Attacker.Get()==Actor && (!Victim || Pair.Value->Owner.Get()==Victim)) bDodge=true;
}

void AProphecyNNLocomotionManager::AdvanceNNDefenses()
{
    using namespace ProphecyDefense;
    auto& D=*Impl->Defense;if (D.ActiveCount==D.ActiveDodgeCount) return;D.Prepared.Reset();
    const int32 ParryCount=D.ActiveCount-D.ActiveDodgeCount;
    D.Inputs.SetNumUninitialized(ParryCount*258,EAllowShrinking::No);D.Outputs.SetNumUninitialized(ParryCount*90,EAllowShrinking::No);
    for (auto& Pair:D.Parries)
    {
        auto& P=*Pair.Value;const int32 Index=Pair.Key;if (!P.Status.Active) continue;
        AProphecyAgent* Actor=P.Owner.Get();AProphecyAgent* Attacker=P.Attacker.Get();
        if (!IsValid(Actor) || !IsValid(Attacker) || !Impl->Agents.IsValidIndex(P.AttackerIndex)
            || ResolveAgent(Actor->GetAgentHandle())!=Actor || ResolveAgent(Attacker->GetAgentHandle())!=Attacker)
        { P.Status.Active=false;continue; }
        auto& Agent=Impl->Agents[Index];const auto& Attack=Impl->Agents[P.AttackerIndex].Slash;
        if (!Actor->bNNInferenceEnabled || !Attacker->bNNInferenceEnabled) continue;
        if (!Attack.bActive || Attack.Family!=P.Family || Attack.Frame<P.Status.AttackerFrame || P.Status.CompletedSteps>=P.MaxSteps)
        { P.Status.Active=false;continue; }
        if (Attack.HitFrame!=INDEX_NONE)
        {
            // Hit is a learned attack output, independent of physical contact.
            // Release ownership on this very policy step, not after the attack tail.
            P.Status.AttackerFrame=Attack.Frame;
            StopAgentNNDefense(Actor->GetAgentHandle());
            PublishAgentPose(Index,Agent.PublishedPoseTimeSeconds);
            continue;
        }
        if (Attack.Frame==P.Status.AttackerFrame) continue;
        const auto Root=DefenseRoot(SlashComponentWorld(Actor,Agent.PublishedRoot,Agent.PublishedYaw));P.NextRoot=Root;
        FMemory::Memcpy(P.NextLower,StateSlice(Impl->PublishedStateBuffer,Index),sizeof(P.NextLower));
        D.Geometry.LowerPose(P.NextLower,Root.P,Root.R,P.Frozen);
        // Preserve the actual accepted locomotion leg decoder and its per-agent
        // presentation clamps; only the upper candidate belongs to parry.
        FLocomotionClamps C;C.bClampFoot=Actor->bOverrideLocomotionFootClamp?Actor->bLocomotionFootClamp:bClampFoot;
        C.FootClampLengthMultiplier=Actor->bOverrideLocomotionFootClamp?1.f:FootClampLengthMultiplier;
        C.FootLeeway=Actor->bOverrideLocomotionFootClamp?Actor->LocomotionFootClampLeewayCm/100.f:0;
        C.bClampCalf=Actor->bOverrideLocomotionCalfClamp?Actor->bLocomotionCalfClamp:bClampCalf;
        C.CalfClampLengthMultiplier=Actor->bOverrideLocomotionCalfClamp?1.f:CalfClampLengthMultiplier;
        C.CalfLeeway=Actor->bOverrideLocomotionCalfClamp?Actor->LocomotionCalfClampLeewayCm/100.f:0;
        if (const auto* Clamps=ProphecyDefenseControls::Find(Actor,false))
        {
            if (Clamps->Foot.bOverride) { C.bClampFoot=Clamps->Foot.bEnabled;C.FootLeeway=Clamps->Foot.LeewayCm/100.f;C.FootClampLengthMultiplier=1; }
            if (Clamps->Calf.bOverride) { C.bClampCalf=Clamps->Calf.bEnabled;C.CalfLeeway=Clamps->Calf.LeewayCm/100.f;C.CalfClampLengthMultiplier=1; }
        }
        float BaseHeading[90];BuildUpperBaseFromLower(P.NextLower,*Impl,BaseHeading);FTransform FrozenComponent[25];
        DecodeLocomotionPose(Impl,P.NextLower,BaseHeading,Agent.PublishedWalkWeight,MakeArrayView(FrozenComponent),nullptr,C);
        const auto Carrier=SlashComponentWorld(Actor,Agent.PublishedRoot,Agent.PublishedYaw);
        for (int32 Bone:{0,17,18,19,20,21,22,23,24})
        {
            const auto World=FrozenComponent[D.Bones[Bone]]*Carrier;
            P.Frozen.P[Bone]=UnrealToTraining(World.GetTranslation());P.Frozen.R[Bone]=DefenseAxes(World.GetRotation());
        }
        D.Geometry.EncodeUpper(P.Frozen,Root.P,Root.R,P.NextBaseline);
        for (int32 Frame=0;Frame<2;++Frame)
        {
            const auto Box=DefenseAttackSample(D,(Frame?Attack.VisibleWorldPose:Attack.PreviousVisibleWorldPose).GetData(),P.AttackerCollider,P.Context.AttackerPelvis[Frame]);
            if (Frame) P.NextAttack=Box;
            Write(P.Context.AttackerCollider[Frame],Box.Center);
            Write(P.Context.AttackerCollider[Frame]+3,Box.Axes.V[0]);Write(P.Context.AttackerCollider[Frame]+6,Box.Axes.V[1]);
        }
        P.Context.Event=Attack.Frame>=2?1.f:0.f;
        P.Context.TargetWorld=UnrealToTraining(Attack.TargetWorld);
        const auto PlannedRoot=DefenseRoot(SlashComponentWorld(Actor,Agent.CurRootPos,Agent.CurRootYaw));
        P.State.InitialWorldDelta=PlannedRoot.P-Root.P;
        const float PlannedYaw=FMath::Atan2(-PlannedRoot.R.V[1].X,-PlannedRoot.R.V[1].Z);
        const float CurrentYaw=FMath::Atan2(-Root.R.V[1].X,-Root.R.V[1].Z);
        P.State.InitialYawDelta=WrapAngle(PlannedYaw-CurrentYaw);
        const bool Drawn=IsValid(Actor->GetHeldSword());P.PresentMask=D.Contacts.PresentMask(Drawn);
        const int32 Lane=D.Prepared.Num();
        if (!PrepareParry(P.State,P.NextLower,P.NextBaseline,Root,P.Context,Drawn?1.f:0.f,P.Work,D.Inputs.GetData()+Lane*258))
        { P.Status.Active=false;continue; }
        P.Status.AttackerFrame=Attack.Frame;D.Prepared.Add(Index);
    }
    if (D.Prepared.IsEmpty()) return;
    const int32 Count=D.Prepared.Num();
    if (!D.ParryNetwork.SetBatch(Count) || !D.ParryNetwork.Run(MakeArrayView(D.Inputs.GetData(),Count*258),MakeArrayView(D.Outputs.GetData(),Count*90)))
    { for (int32 Index:D.Prepared) D.Parries.FindChecked(Index)->Status.Active=false;UE_LOG(LogProphecyNNLocomotion,Error,TEXT("Parry batch failed."));return; }
    for (int32 Lane=0;Lane<Count;++Lane)
    {
        const int32 Index=D.Prepared[Lane];auto& P=*D.Parries.FindChecked(Index);auto& Agent=Impl->Agents[Index];
        const float* Delta=D.Outputs.GetData()+Lane*90;bool Finite=true;for (int32 I=0;I<90;++I) Finite&=FMath::IsFinite(Delta[I]);
        FPose Pose;if (!Finite || !CompleteParry(P.State,P.Work,Delta,P.NextLower,P.NextBaseline,P.NextRoot,P.Frozen,D.Geometry,Pose))
        { P.Status.Active=false;continue; }
        const bool bContactStop=DefensePhysicalStop(*Impl,P,P.CurrentPose,Pose,FVector3f::ZeroVector);
        FMemory::Memcpy(P.PreviousComponent,P.CurrentComponent,sizeof(P.CurrentComponent));
        DefenseComponentPose(Pose,P.NextRoot,D.Bones,P.CurrentComponent);P.CurrentPose=Pose;P.bHasPose=true;
        float Upper[90];DefenseUpperToLocomotion(P.State.CurrentUpper,Impl->SeedRootRot,Upper);
        FMemory::Memcpy(UpperStateSlice(Impl->UpperPreviousPublishedStateBuffer,Index),UpperStateSlice(Impl->UpperPublishedStateBuffer,Index),sizeof(Upper));
        FMemory::Memcpy(UpperStateSlice(Impl->UpperPublishedStateBuffer,Index),Upper,sizeof(Upper));
        FMemory::Memcpy(UpperStateSlice(Impl->UpperPreviousStateBuffer,Index),UpperStateSlice(Impl->UpperCurrentStateBuffer,Index),sizeof(Upper));
        FMemory::Memcpy(UpperStateSlice(Impl->UpperCurrentStateBuffer,Index),Upper,sizeof(Upper));
        BuildUpperBaseFromLower(StateSlice(Impl->CurStateBuffer,Index),*Impl,UpperStateSlice(Impl->UpperCurrentBaseBuffer,Index));
        FMemory::Memcpy(TransformStateSlice(Impl->PreviousPelvisHeadingBuffer,Index),TransformStateSlice(Impl->CurrentPelvisHeadingBuffer,Index),9*sizeof(float));
        LowerTransformToHeading(StateSlice(Impl->CurStateBuffer,Index),0,3,*Impl,TransformStateSlice(Impl->CurrentPelvisHeadingBuffer,Index));
        ++P.Status.CompletedSteps;
        if (bContactStop) P.Status.Active=false;
    }
}
