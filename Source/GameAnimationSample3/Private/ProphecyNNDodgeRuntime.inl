// Optional full-body Dodge. Native recurrence stays in reference coordinates;
// only this boundary translates the episode origin and publishes UE carriers.
namespace
{
float DodgeRootYaw(const ProphecyDefense::FRootFrame& Root)
{ return FMath::Atan2(-Root.R.V[1].X,-Root.R.V[1].Z); }
FVector3f DodgeManagedPosition(const FProphecyLiveDodge& P,const ProphecyDefense::FRootFrame& Root)
{ return Root.P+P.WorldOrigin-ProphecyDefense::Transform(P.CarrierOffset,Root.R); }
float DodgeManagedYaw(const FProphecyLiveDodge& P,const ProphecyDefense::FRootFrame& Root)
{ return P.InitialManagedYaw+WrapAngle(DodgeRootYaw(Root)-P.InitialNativeYaw); }
bool InitializeDodgeRuntime(FProphecyLiveDefenseRuntime& D,FString& Error)
{
    if (D.bDodgeReady) return true;
    const FString Dir=FPaths::ProjectContentDir()/TEXT("locomotion/NN/defense");
    if (!D.DodgeGeometry.Load(Dir/TEXT("dodge_skeleton.json"),true,Error)
        || !D.DodgeContacts.Load(Dir/TEXT("dodge_colliders.json"),Error)
        || !D.DodgeUpper.Initialize(Dir/TEXT("prophecy_dodge_upper.onnx"),362,112,Error)) return false;
    for (int32 I=0;I<2;++I)
    {
        const FString Kind=I?TEXT("run"):TEXT("walk");
        if (!D.DodgeSettings[I].Load(Dir/TEXT("dodge_lower_settings.json"),Kind,Error)
            || !D.DodgeLower[I].Initialize(Dir/(TEXT("prophecy_dodge_")+Kind+TEXT(".onnx")),152,43,Error)) return false;
    }
    FString Text;TSharedPtr<FJsonObject> Config;const TArray<TSharedPtr<FJsonValue>>* Limits=nullptr;
    if (!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("dodge_banks.json")))
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Config) || !Config
        || !Config->TryGetArrayField(TEXT("limits"),Limits) || Limits->Num()!=6)
    { Error=TEXT("Invalid saved Dodge bank capacities.");return false; }
    for (int32 I=0;I<6;++I)
    {
        double V;if (!(*Limits)[I]->TryGetNumber(V) || !FMath::IsFinite(V) || V<0 || V>MAX_flt)
        { Error=TEXT("Nonfinite or negative Dodge bank capacity.");return false; }
        D.DodgeLimits[I]=float(V);
    }
    D.bDodgeReady=true;return true;
}
}

bool AProphecyNNLocomotionManager::StartAgentNNDodge(FProphecyAgentHandle Handle,AProphecyAgent* Attacker,
    float MaximumSeconds,FString& Error)
{
    using namespace ProphecyDefense;
    AProphecyAgent* Actor=ResolveAgent(Handle);
    if (!Actor || !IsValid(Attacker) || Actor==Attacker || ResolveAgent(Attacker->GetAgentHandle())!=Attacker
        || !Actor->bNNInferenceEnabled || !Attacker->bNNInferenceEnabled || !FMath::IsFinite(MaximumSeconds) || MaximumSeconds<=0)
    { Error=TEXT("Dodge needs two distinct, initialized agents in this manager and a positive duration.");return false; }
    if (!FMath::IsNearlyEqual(NNUpdateHz,30.f)) { Error=TEXT("This saved Dodge checkpoint requires the 30 Hz policy clock.");return false; }
    auto& Agent=Impl->Agents[Handle.Index];const int32 AttackerIndex=Attacker->GetAgentHandle().Index;const auto& Attack=Impl->Agents[AttackerIndex].Slash;
    if (Agent.Slash.bActive || Agent.AnimationLayer.IsActive() || !Attack.bActive || Attack.VisibleWorldPose.Num()!=25)
    { Error=TEXT("Start the attack first; defender must not have an active attack or animation layer.");return false; }
    if (!InitializeDefenseRuntime(*Impl,Error) || !InitializeDodgeRuntime(*Impl->Defense,Error)) return false;
    auto& D=*Impl->Defense;const int32 AttackCollider=DefenseAttackCollider(D,Attack);
    if (AttackCollider==INDEX_NONE) { Error=TEXT("Unsupported attack collider for Dodge.");return false; }
    PublishAgentPose(Handle.Index,Agent.PublishedPoseTimeSeconds);
    auto New=MakeUnique<FProphecyLiveDodge>();auto& P=*New;
    P.bDodge=true;P.Owner=Actor;P.Attacker=Attacker;P.AttackerIndex=AttackerIndex;P.AttackerCollider=AttackCollider;P.Family=Attack.Family;
    P.Category=Agent.bUseWalkPolicy?0:1;P.AttackerHalf=D.Contacts.Boxes[AttackCollider].Half;
    P.MaxSteps=FMath::Clamp(FMath::CeilToInt(MaximumSeconds*30),1,18000);
    // Ground is zero in the checkpoint. A fixed episode origin puts the local
    // scene floor there and avoids large-world float32 cancellation.
    P.WorldOrigin=Agent.PublishedRoot;P.Context.TargetWorld=UnrealToTraining(Attack.TargetWorld)-P.WorldOrigin;
    FMemory::Memcpy(P.Context.AttackControls,Attack.State.GetData()+265,5*sizeof(float));
    float L[2][41],U[2][90],Roots[2][12];
    for (int32 I=0;I<2;++I)
    {
        const auto Pose=TransformSlice(I?Impl->ComponentTransformBuffer:Impl->PreviousComponentTransformBuffer,Handle.Index);
        EncodeSlashPose(*Impl,Agent,Pose,L[I],U[I]);
        auto Root=DefenseRoot(SlashComponentWorld(Actor,I?Agent.PublishedRoot:Agent.PreviousPublishedRoot,I?Agent.PublishedYaw:Agent.PreviousPublishedYaw));
        Root.P-=P.WorldOrigin;DefenseRoot12(Root,Roots[I]);
        for (int32 J=0;J<25;++J) (I?P.CurrentComponent:P.PreviousComponent)[J]=Pose[J];
        if (I) { P.CarrierOffset=InTransposedBasis(Root.P,Root.R);P.InitialNativeYaw=DodgeRootYaw(Root);P.InitialManagedYaw=Agent.PublishedYaw; }
    }
    P.State.Initialize(L[0],U[0],Roots[0],L[1],U[1],Roots[1],D.DodgeLimits);
    FTransform World[25];const auto Carrier=SlashComponentWorld(Actor,Agent.PublishedRoot,Agent.PublishedYaw);
    for (int32 I=0;I<25;++I) World[I]=P.CurrentComponent[I]*Carrier;
    DefenseWorldPose(World,D.Bones,P.CurrentPose);for (auto& Point:P.CurrentPose.P) Point-=P.WorldOrigin;
    D.DodgeContacts.Build(P.CurrentPose,P.PreviousBoxes);
    P.PreviousAttack=DefenseAttackSample(D,Attack.VisibleWorldPose.GetData(),AttackCollider,nullptr);P.PreviousAttack.Center-=P.WorldOrigin;
    P.Status.Active=true;P.Status.AttackerFrame=Attack.Frame;P.bHasPose=true;
    if (Agent.DefensePose) StopAgentNNDefense(Handle);
    Agent.PolicyBlend.Reset(P.Category==0);
    D.Parries.Remove(Handle.Index);Agent.DefensePose=New.Get();D.Dodges.Add(Handle.Index,MoveTemp(New));
    ProphecyLimbCollision::DefenseChanged(Actor,true);
    ++D.ActiveCount;++D.ActiveDodgeCount;Error.Reset();return true;
}

void AProphecyNNLocomotionManager::AdvanceNNDodges()
{
    using namespace ProphecyDefense;
    auto& D=*Impl->Defense;if (!D.ActiveDodgeCount) return;
    D.DodgePrepared.Reset();for (auto& Group:D.DodgeLowerPrepared) Group.Reset();
    for (auto& Pair:D.Dodges)
    {
        auto& P=*Pair.Value;if (!P.Status.Active) continue;
        AProphecyAgent* Actor=P.Owner.Get();AProphecyAgent* Attacker=P.Attacker.Get();
        if (!IsValid(Actor) || !IsValid(Attacker) || !Impl->Agents.IsValidIndex(P.AttackerIndex)
            || ResolveAgent(Actor->GetAgentHandle())!=Actor || ResolveAgent(Attacker->GetAgentHandle())!=Attacker)
        { P.Status.Active=false;continue; }
        const auto& Attack=Impl->Agents[P.AttackerIndex].Slash;
        if (!Actor->bNNInferenceEnabled || !Attacker->bNNInferenceEnabled) continue;
        if (!Attack.bActive || Attack.Family!=P.Family || Attack.Frame<=P.Status.AttackerFrame || P.Status.CompletedSteps>=P.MaxSteps)
        { P.Status.Active=false;continue; }
        for (int32 Frame=0;Frame<2;++Frame)
        {
            auto Box=DefenseAttackSample(D,(Frame?Attack.VisibleWorldPose:Attack.PreviousVisibleWorldPose).GetData(),P.AttackerCollider,P.Context.AttackerPelvis[Frame]);
            Write(P.Context.AttackerPelvis[Frame],Read(P.Context.AttackerPelvis[Frame])-P.WorldOrigin);
            Box.Center-=P.WorldOrigin;if (Frame) P.NextAttack=Box;
            Write(P.Context.AttackerCollider[Frame],Box.Center);Write(P.Context.AttackerCollider[Frame]+3,Box.Axes.V[0]);Write(P.Context.AttackerCollider[Frame]+6,Box.Axes.V[1]);
        }
        P.Context.Event=Attack.HitFrame!=INDEX_NONE?1.f:0.f;
        P.PresentMask=D.DodgeContacts.PresentMask(IsValid(Actor->GetHeldSword()));
        D.DodgeLowerPrepared[P.Category].Add(Pair.Key);
    }
    D.DodgeInputs.SetNumUninitialized(D.ActiveDodgeCount*362,EAllowShrinking::No);
    D.DodgeOutputs.SetNumUninitialized(D.ActiveDodgeCount*112,EAllowShrinking::No);
    for (int32 Category=0;Category<2;++Category)
    {
        const auto& Group=D.DodgeLowerPrepared[Category];const int32 Count=Group.Num();if (!Count) continue;
        D.DodgeLowerInputs.SetNumUninitialized(Count*152,EAllowShrinking::No);D.DodgeLowerOutputs.SetNumUninitialized(Count*43,EAllowShrinking::No);
        for (int32 Lane=0;Lane<Count;++Lane) DodgeLowerInput(D.Dodges.FindChecked(Group[Lane])->State,D.DodgeSettings[Category],D.DodgeLowerInputs.GetData()+Lane*152);
        if (!D.DodgeLower[Category].SetBatch(Count) || !D.DodgeLower[Category].Run(D.DodgeLowerInputs,D.DodgeLowerOutputs))
        { for (int32 Index:Group) D.Dodges.FindChecked(Index)->Status.Active=false;UE_LOG(LogProphecyNNLocomotion,Error,TEXT("Dodge lower batch failed."));continue; }
        for (int32 Lane=0;Lane<Count;++Lane)
        {
            const int32 Index=Group[Lane];auto& P=*D.Dodges.FindChecked(Index);const float* Raw=D.DodgeLowerOutputs.GetData()+Lane*43;
            bool Finite=true;for (int32 I=0;I<43;++I) Finite&=FMath::IsFinite(Raw[I]);
            if (!Finite) { P.Status.Active=false;continue; }
            CleanDodgeLower(Raw,P.State.CurrentLower,D.DodgeGeometry,D.DodgeSettings[Category],P.NextLower,P.Pins);
            if (!PrepareDodge(P.State,P.NextLower,P.Context,P.Work,D.DodgeInputs.GetData()+D.DodgePrepared.Num()*362))
            { P.Status.Active=false;continue; }
            D.DodgePrepared.Add(Index);
        }
    }
    const int32 Count=D.DodgePrepared.Num();if (!Count) return;
    if (!D.DodgeUpper.SetBatch(Count) || !D.DodgeUpper.Run(MakeArrayView(D.DodgeInputs.GetData(),Count*362),MakeArrayView(D.DodgeOutputs.GetData(),Count*112)))
    { for (int32 Index:D.DodgePrepared) D.Dodges.FindChecked(Index)->Status.Active=false;UE_LOG(LogProphecyNNLocomotion,Error,TEXT("Dodge upper batch failed."));return; }
    for (int32 Lane=0;Lane<Count;++Lane)
    {
        const int32 Index=D.DodgePrepared[Lane];auto& P=*D.Dodges.FindChecked(Index);auto& Agent=Impl->Agents[Index];
        const float* Output=D.DodgeOutputs.GetData()+Lane*112;bool Finite=true;for (int32 I=0;I<112;++I) Finite&=FMath::IsFinite(Output[I]);
        const auto PoseRoot=P.State.CurrentRoot;FPose Pose;float Modified[41],Upper[90];
        if (!Finite || !CompleteDodge(P.State,P.Work,P.NextLower,Output,D.DodgeGeometry,Pose,Modified,Upper)) { P.Status.Active=false;continue; }
        FMemory::Memcpy(P.PreviousComponent,P.CurrentComponent,sizeof(P.CurrentComponent));
        DefenseComponentPose(Pose,PoseRoot,D.Bones,P.CurrentComponent);P.CurrentPose=Pose;
        Agent.PreviousPublishedRoot=Agent.PublishedRoot;Agent.PreviousPublishedYaw=Agent.PublishedYaw;
        Agent.PublishedRoot=DodgeManagedPosition(P,PoseRoot);Agent.PublishedYaw=DodgeManagedYaw(P,PoseRoot);
        Agent.PrevRootPos=Agent.PublishedRoot;Agent.PrevRootYaw=Agent.PublishedYaw;
        Agent.CurRootPos=DodgeManagedPosition(P,P.State.CurrentRoot);Agent.CurRootYaw=DodgeManagedYaw(P,P.State.CurrentRoot);
        const auto Delta=Agent.CurRootPos-Agent.PrevRootPos;
        Agent.MoverState.position={Agent.CurRootPos.X,Agent.CurRootPos.Z};Agent.MoverState.velocity={double(Delta.X)*30,double(Delta.Z)*30};
        Agent.MoverState.previous_yaw_radians=Agent.PrevRootYaw;Agent.MoverState.yaw_radians=Agent.CurRootYaw;
        Agent.MoverIntent.orientation_yaw_radians=Agent.CurRootYaw;
        Agent.MoverState.distance_travelled+=FVector2f(Delta.X,Delta.Z).Size();
        Agent.PinProbability={P.Pins[0],P.Pins[1]};Agent.bHasFedFutureRoots=false;
        Agent.bPreviousPublishedUseWalkPolicy=Agent.bPublishedUseWalkPolicy;Agent.PreviousPublishedWalkWeight=Agent.PublishedWalkWeight;
        Agent.bPublishedUseWalkPolicy=P.Category==0;Agent.PublishedWalkWeight=P.Category==0?1.f:0.f;
        FMemory::Memcpy(StateSlice(Impl->PreviousPublishedStateBuffer,Index),StateSlice(Impl->PublishedStateBuffer,Index),sizeof(Modified));
        FMemory::Memcpy(StateSlice(Impl->PublishedStateBuffer,Index),Modified,sizeof(Modified));
        FMemory::Memcpy(StateSlice(Impl->PrevStateBuffer,Index),P.State.PreviousLower,sizeof(Modified));
        FMemory::Memcpy(StateSlice(Impl->CurStateBuffer,Index),P.State.CurrentLower,sizeof(Modified));
        FMemory::Memcpy(StateSlice(Impl->NextStateBuffer,Index),P.State.CurrentLower,sizeof(Modified));
        FMemory::Memcpy(UpperStateSlice(Impl->UpperPreviousPublishedStateBuffer,Index),UpperStateSlice(Impl->UpperPublishedStateBuffer,Index),sizeof(Upper));
        DefenseUpperToLocomotion(Upper,Impl->SeedRootRot,UpperStateSlice(Impl->UpperPublishedStateBuffer,Index));
        DefenseUpperToLocomotion(P.State.PreviousUpper,Impl->SeedRootRot,UpperStateSlice(Impl->UpperPreviousStateBuffer,Index));
        DefenseUpperToLocomotion(P.State.CurrentUpper,Impl->SeedRootRot,UpperStateSlice(Impl->UpperCurrentStateBuffer,Index));
        BuildUpperBaseFromLower(P.State.CurrentLower,*Impl,UpperStateSlice(Impl->UpperCurrentBaseBuffer,Index));
        LowerTransformToHeading(P.State.PreviousLower,0,3,*Impl,TransformStateSlice(Impl->PreviousPelvisHeadingBuffer,Index));
        LowerTransformToHeading(P.State.CurrentLower,0,3,*Impl,TransformStateSlice(Impl->CurrentPelvisHeadingBuffer,Index));
        FDefenseBox Boxes[20];D.DodgeContacts.Build(Pose,Boxes);
        for (int32 I=0;I<D.DodgeContacts.Count;++I) if (P.PresentMask&(1u<<I))
        {
            const auto& G=D.DodgeContacts.Boxes[I];const auto Contact=SweepBoxes(P.PreviousBoxes[I],Boxes[I],G.Half,G.CenterOffset,
                P.PreviousAttack,P.NextAttack,P.AttackerHalf,FVector3f::ZeroVector);
            P.Order.Include(Contact,I,false,P.Status.CompletedSteps,P.Status.CompletedSteps+1);
        }
        FMemory::Memcpy(P.PreviousBoxes,Boxes,D.DodgeContacts.Count*sizeof(FDefenseBox));P.PreviousAttack=P.NextAttack;
        ++P.Status.CompletedSteps;P.Status.AttackerFrame=Impl->Agents[P.AttackerIndex].Slash.Frame;P.Status.HarmfulContact=P.Order.bHarmful;
        if (P.Order.bHarmful)
        {
            P.Status.ContactCollider=D.DodgeContacts.Boxes[P.Order.HarmCollider].Name;
            P.Status.ContactTimeSeconds=float(P.Order.HarmTime/30.);P.Status.Active=false;
        }
    }
}
