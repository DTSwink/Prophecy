// Optional full-body Dodge. Native recurrence stays in reference coordinates;
// only this boundary translates the episode origin and publishes UE carriers.
#if !UE_BUILD_SHIPPING
namespace ProphecyDodgeAudit
{
static TAutoConsoleVariable<int32> Enabled(TEXT("Prophecy.Debug.DodgeTrace"),0,TEXT("Development-only live Dodge boundary trace."));
static TAutoConsoleVariable<int32> ContinueAfterContact(TEXT("Prophecy.Debug.DodgeContinueAfterContact"),0,TEXT("Development-only isolation: do not end Dodge on predicted contact."));
void Array(const TSharedPtr<FJsonObject>& Doc,const TCHAR* Key,const float* Data,int32 Count)
{
    TArray<TSharedPtr<FJsonValue>> Values;Values.Reserve(Count);
    for (int32 I=0;I<Count;++I) Values.Add(MakeShared<FJsonValueNumber>(Data[I]));
    Doc->SetArrayField(Key,Values);
}
void Vector(const TSharedPtr<FJsonObject>& Doc,const TCHAR* Key,const FVector3f& V)
{ const float A[]={V.X,V.Y,V.Z};Array(Doc,Key,A,3); }
void Root(const TSharedPtr<FJsonObject>& Doc,const TCHAR* Key,const ProphecyDefense::FRootFrame& R)
{ float A[12];DefenseRoot12(R,A);Array(Doc,Key,A,12); }
TSharedPtr<FJsonObject> State(const ProphecyDefense::FDodgeState& S)
{
    auto Doc=MakeShared<FJsonObject>();
    Array(Doc,TEXT("previous_lower"),S.PreviousLower,41);Array(Doc,TEXT("current_lower"),S.CurrentLower,41);
    Array(Doc,TEXT("previous_upper"),S.PreviousUpper,90);Array(Doc,TEXT("current_upper"),S.CurrentUpper,90);
    Root(Doc,TEXT("previous_root"),S.PreviousRoot);Root(Doc,TEXT("current_root"),S.CurrentRoot);
    Vector(Doc,TEXT("initial_delta_world"),S.InitialWorldDelta);Vector(Doc,TEXT("root_shift"),S.RootShift);
    Doc->SetNumberField(TEXT("initial_delta_yaw"),S.InitialYawDelta);Doc->SetNumberField(TEXT("yaw_offset"),S.YawOffset);
    Array(Doc,TEXT("remaining"),S.Remaining,6);Doc->SetNumberField(TEXT("steps"),double(S.CompletedSteps));return Doc;
}
void Save(const FProphecyLiveDodge& P,int32 Frame,const TCHAR* Stage,const TSharedPtr<FJsonObject>& Doc)
{
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/DodgeMismatch/NativeTrace");
    IFileManager::Get().MakeDirectory(*Dir,true);
    const FString Path=Dir/FString::Printf(TEXT("%s_%s_%03d_%s.json"),ContinueAfterContact.GetValueOnGameThread()?TEXT("continue"):TEXT("normal"),*GetNameSafe(P.Owner.Get()),Frame,Stage);
    FString Json;FJsonSerializer::Serialize(Doc.ToSharedRef(),TJsonWriterFactory<>::Create(&Json));
    FFileHelper::SaveStringToFile(Json,*Path);
}
}
#endif
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
    if (!Attack.bActive || Attack.VisibleWorldPose.Num()!=25 || Attack.State.Num()!=SlashInputDim)
    { Error=TEXT("Start the incoming attack first.");return false; }
    if (Attack.HitFrame!=INDEX_NONE && Attack.Frame-Attack.HitFrame>=ProphecyDefenseControls::GetDodgeFramesAfterHit(Actor))
    { Error=TEXT("The incoming attack's post-Hit Dodge window has ended.");return false; }
    if (Attack.State[270]<=0.5f)
    {
        StopAgentNNDefense(Handle);
        ProphecyDefenseArmedGate::Queue(this,Actor,Attacker,true,MaximumSeconds);
        Error.Reset();return true;
    }
    if (Agent.AnimationLayer.IsActive())
    { Error=TEXT("Defender has an active animation layer.");return false; }
    if (!InitializeDefenseRuntime(*Impl,Error) || !InitializeDodgeRuntime(*Impl->Defense,Error)) return false;
    auto& D=*Impl->Defense;const int32 AttackCollider=DefenseAttackCollider(D,Attack);
    if (AttackCollider==INDEX_NONE) { Error=TEXT("Unsupported attack collider for Dodge.");return false; }
    ProphecyDefenseArmedGate::Cancel(Actor);
    if (Agent.Slash.bActive) StopAgentNNAttack(Handle, false);
    PublishAgentPose(Handle.Index,Agent.PublishedPoseTimeSeconds);
    const auto* History=ProphecyDefenseArmedGate::ActivationHistory(Actor);
    auto New=MakeUnique<FProphecyLiveDodge>();auto& P=*New;
    P.bDodge=true;P.Owner=Actor;P.Attacker=Attacker;P.AttackerIndex=AttackerIndex;P.AttackerCollider=AttackCollider;P.Family=Attack.Family;
    P.Category=Agent.bUseWalkPolicy?0:1;P.AttackerHalf=D.AttackContacts.Boxes[AttackCollider].Half;
    P.MaxSteps=FMath::Clamp(FMath::CeilToInt(MaximumSeconds*30),1,18000);
    // Ground is zero in the checkpoint. A fixed episode origin puts the local
    // scene floor there and avoids large-world float32 cancellation.
    P.WorldOrigin=History?History->Root[1]:Agent.PublishedRoot;P.Context.TargetWorld=UnrealToTraining(Attack.TargetWorld)-P.WorldOrigin;
    FMemory::Memcpy(P.Context.AttackControls,Attack.State.GetData()+265,5*sizeof(float));
    float L[2][41],U[2][90],Roots[2][12];
    for (int32 I=0;I<2;++I)
    {
        const TArrayView<const FTransform> Pose=History?MakeArrayView(History->Pose[I]):TArrayView<const FTransform>(TransformSlice(I?Impl->ComponentTransformBuffer:Impl->PreviousComponentTransformBuffer,Handle.Index));
        EncodeSlashPose(*Impl,Agent,Pose,L[I],U[I]);
        auto Root=DefenseRoot(SlashComponentWorld(Actor,History?History->Root[I]:(I?Agent.PublishedRoot:Agent.PreviousPublishedRoot),History?History->Yaw[I]:(I?Agent.PublishedYaw:Agent.PreviousPublishedYaw)));
        Root.P-=P.WorldOrigin;DefenseRoot12(Root,Roots[I]);
        for (int32 J=0;J<25;++J) (I?P.CurrentComponent:P.PreviousComponent)[J]=Pose[J];
        if (I) { P.CarrierOffset=InTransposedBasis(Root.P,Root.R);P.InitialNativeYaw=DodgeRootYaw(Root);P.InitialManagedYaw=History?History->Yaw[1]:Agent.PublishedYaw; }
    }
    P.State.Initialize(L[0],U[0],Roots[0],L[1],U[1],Roots[1],D.DodgeLimits);
    if (History)
    {
        Agent.PublishedRoot=History->Root[1];Agent.PublishedYaw=History->Yaw[1];
        FMemory::Memcpy(StateSlice(Impl->PublishedStateBuffer,Handle.Index),L[1],sizeof(L[1]));
        DefenseUpperToLocomotion(U[1],Impl->SeedRootRot,UpperStateSlice(Impl->UpperPublishedStateBuffer,Handle.Index));
    }
    FTransform World[25];const auto Carrier=SlashComponentWorld(Actor,Agent.PublishedRoot,Agent.PublishedYaw);
    for (int32 I=0;I<25;++I) World[I]=P.CurrentComponent[I]*Carrier;
    DefenseWorldPose(World,D.Bones,P.CurrentPose);for (auto& Point:P.CurrentPose.P) Point-=P.WorldOrigin;
    D.DodgeContacts.Build(P.CurrentPose,P.PreviousBoxes);
    P.PreviousAttack=DefenseAttackSample(D,(History?Attack.PreviousVisibleWorldPose:Attack.VisibleWorldPose).GetData(),AttackCollider,nullptr);P.PreviousAttack.Center-=P.WorldOrigin;
    P.Status.Active=true;P.Status.AttackerFrame=Attack.Frame-(History?1:0);P.bHasPose=true;
    if (Agent.DefensePose) StopAgentNNDefense(Handle, false);
    Agent.PolicyBlend.Reset(P.Category==0);
    ProphecyAttackRecovery::EnterSpecial(Actor);
    ProphecyRootBalance::CancelKickException(Actor);
    D.Parries.Remove(Handle.Index);Agent.DefensePose=New.Get();D.Dodges.Add(Handle.Index,MoveTemp(New));
    SetAgentTimeDilation(Handle,1.f);
    ProphecyLimbCollision::DefenseChanged(Actor,true);
    ++D.ActiveCount;++D.ActiveDodgeCount;Error.Reset();return true;
}

void AProphecyNNLocomotionManager::AdvanceNNDodges()
{
    using namespace ProphecyDefense;
    auto& D=*Impl->Defense;if (!D.ActiveDodgeCount) return;
    D.DodgePrepared.Reset();for (auto& Group:D.DodgeLowerPrepared) Group.Reset();
    TArray<int32,TInlineAllocator<16>> DodgeIndices;
    for(const auto& Pair:D.Dodges) DodgeIndices.Add(Pair.Key);
    // Dispatch exit callbacks before preparing any inference lanes: Blueprint
    // can start/stop another special and mutate either defense map.
    for(int32 Index:DodgeIndices)
    {
        auto* Entry=D.Dodges.Find(Index);if(!Entry || !(*Entry)->Status.Active)continue;
        auto& P=**Entry;auto* Actor=P.Owner.Get();auto* Attacker=P.Attacker.Get();
        if(!IsValid(Actor) || !IsValid(Attacker) || !Actor->bNNInferenceEnabled || !Attacker->bNNInferenceEnabled || !Impl->Agents.IsValidIndex(P.AttackerIndex))continue;
        const auto& Attack=Impl->Agents[P.AttackerIndex].Slash;
        if(Attack.bActive && Attack.Family==P.Family && Attack.HitFrame!=INDEX_NONE && Attack.Frame-Attack.HitFrame>=ProphecyDefenseControls::GetDodgeFramesAfterHit(Actor))
        {
            P.Status.AttackerFrame=Attack.Frame;StopAgentNNDefense(Actor->GetAgentHandle());
            if(IsValid(Actor) && ResolveAgent(Actor->GetAgentHandle())==Actor) PublishAgentPose(Index,Impl->Agents[Index].PublishedPoseTimeSeconds);
        }
    }
    for (int32 Index:DodgeIndices)
    {
        const auto* Entry=D.Dodges.Find(Index);if(!Entry)continue;
        auto& P=**Entry;if (!P.Status.Active) continue;
        AProphecyAgent* Actor=P.Owner.Get();AProphecyAgent* Attacker=P.Attacker.Get();
        if (!IsValid(Actor) || !IsValid(Attacker) || !Impl->Agents.IsValidIndex(P.AttackerIndex)
            || ResolveAgent(Actor->GetAgentHandle())!=Actor || ResolveAgent(Attacker->GetAgentHandle())!=Attacker)
        { P.Status.Active=false;continue; }
        const auto& Attack=Impl->Agents[P.AttackerIndex].Slash;
        auto& Agent=Impl->Agents[Index];
        if (!Actor->bNNInferenceEnabled || !Attacker->bNNInferenceEnabled) continue;
        if (!Attack.bActive || Attack.Family!=P.Family || Attack.Frame<P.Status.AttackerFrame || P.Status.CompletedSteps>=P.MaxSteps)
        { P.Status.Active=false;continue; }
        if (Attack.HitFrame!=INDEX_NONE && Attack.Frame-Attack.HitFrame>=ProphecyDefenseControls::GetDodgeFramesAfterHit(Actor))
        {
            P.Status.AttackerFrame=Attack.Frame;
            P.Status.Active=false;
            continue;
        }
        if (Attack.Frame==P.Status.AttackerFrame) continue;
        for (int32 Frame=0;Frame<2;++Frame)
        {
            auto Box=DefenseAttackSample(D,(Frame?Attack.VisibleWorldPose:Attack.PreviousVisibleWorldPose).GetData(),P.AttackerCollider,P.Context.AttackerPelvis[Frame]);
            Write(P.Context.AttackerPelvis[Frame],Read(P.Context.AttackerPelvis[Frame])-P.WorldOrigin);
            Box.Center-=P.WorldOrigin;if (Frame) P.NextAttack=Box;
            Write(P.Context.AttackerCollider[Frame],Box.Center);Write(P.Context.AttackerCollider[Frame]+3,Box.Axes.V[0]);Write(P.Context.AttackerCollider[Frame]+6,Box.Axes.V[1]);
        }
        P.Context.Event=Attack.HitFrame!=INDEX_NONE?1.f:0.f;
        P.Context.TargetWorld=UnrealToTraining(Attack.TargetWorld)-P.WorldOrigin;
        P.Category=Agent.bUseWalkPolicy?0:1;
        P.PresentMask=D.DodgeContacts.PresentMask(IsValid(Actor->GetHeldSword()));
        D.DodgeLowerPrepared[P.Category].Add(Index);
    }
    D.DodgeInputs.SetNumUninitialized(D.ActiveDodgeCount*362,EAllowShrinking::No);
    D.DodgeOutputs.SetNumUninitialized(D.ActiveDodgeCount*112,EAllowShrinking::No);
    for (int32 Category=0;Category<2;++Category)
    {
        const auto& Group=D.DodgeLowerPrepared[Category];const int32 Count=Group.Num();if (!Count) continue;
        D.DodgeLowerInputs.SetNumUninitialized(Count*152,EAllowShrinking::No);D.DodgeLowerOutputs.SetNumUninitialized(Count*43,EAllowShrinking::No);
        for (int32 Lane=0;Lane<Count;++Lane)
        {
            const int32 Index=Group[Lane];auto& P=*D.Dodges.FindChecked(Index);
            float* Input=D.DodgeLowerInputs.GetData()+Lane*152;
            DodgeLowerInput(P.State,D.DodgeSettings[Category],Input);
            // Use all eight live mover predictions, with this frozen checkpoint's
            // normalization. History still comes from Dodge's corrected recurrence.
            const float* Future=Impl->InputBuffer.GetData()+Index*InputDim+120;
            const auto& Agent=Impl->Agents[Index];
            const auto Heading=DodgeYaw(-DodgeRootYaw(P.State.CurrentRoot));
            const auto CarrierOffset=Transform(P.CarrierOffset,P.State.CurrentRoot.R);
            for (int32 I=0;I<8;++I)
            {
                const float Scale=(I+1)*Impl->MaxSpeedScaleFinal;
                const float Yaw=FMath::Atan2(Future[4*I+3],Future[4*I+2]);
                auto Axes=P.State.CurrentRoot.R;const auto Rotation=DodgeYaw(Yaw);
                for (auto& Row:Axes.V) Row=Transform(Row,Rotation);
                const auto WorldDelta=TransformRow(FVector3f(Future[4*I]*Scale,Agent.WindowVerticalVelocity*(I+1)*Agent.WindowStepSeconds,Future[4*I+1]*Scale),Transpose(YawMatrix(Agent.FedInputYaw)))
                    +Transform(P.CarrierOffset,Axes)-CarrierOffset;
                const auto Local=Transform(WorldDelta,Heading);
                const float NativeScale=(I+1)*D.DodgeSettings[Category].SpeedScale;
                Input[120+4*I]=FMath::Clamp(Local.X/NativeScale,-2.f,2.f);
                Input[121+4*I]=FMath::Clamp(Local.Z/NativeScale,-2.f,2.f);
                Input[122+4*I]=Future[4*I+2];Input[123+4*I]=Future[4*I+3];
            }
        }
        if (!D.DodgeLower[Category].SetBatch(Count) || !D.DodgeLower[Category].Run(D.DodgeLowerInputs,D.DodgeLowerOutputs))
        { for (int32 Index:Group) D.Dodges.FindChecked(Index)->Status.Active=false;UE_LOG(LogProphecyNNLocomotion,Error,TEXT("Dodge lower batch failed."));continue; }
        for (int32 Lane=0;Lane<Count;++Lane)
        {
            const int32 Index=Group[Lane];auto& P=*D.Dodges.FindChecked(Index);const float* Raw=D.DodgeLowerOutputs.GetData()+Lane*43;
            bool Finite=true;for (int32 I=0;I<43;++I) Finite&=FMath::IsFinite(Raw[I]);
            if (!Finite) { P.Status.Active=false;continue; }
            CleanDodgeLower(Raw,P.State.CurrentLower,D.DodgeGeometry,D.DodgeSettings[Category],P.NextLower,P.Pins);
#if !UE_BUILD_SHIPPING
            if (ProphecyDodgeAudit::Enabled.GetValueOnGameThread())
            {
                using namespace ProphecyDodgeAudit;auto Doc=MakeShared<FJsonObject>();Doc->SetObjectField(TEXT("state"),State(P.State));
                Doc->SetNumberField(TEXT("category"),Category);Array(Doc,TEXT("input"),D.DodgeLowerInputs.GetData()+Lane*152,152);
                Array(Doc,TEXT("raw"),Raw,43);Array(Doc,TEXT("cleaned"),P.NextLower,41);Array(Doc,TEXT("pins"),P.Pins,2);
                Save(P,Impl->Agents[P.AttackerIndex].Slash.Frame,TEXT("lower"),Doc);
            }
#endif
            const auto& Agent=Impl->Agents[Index];
            auto PlannedRoot=DefenseRoot(SlashComponentWorld(AgentActors[Index],Agent.CurRootPos,Agent.CurRootYaw));PlannedRoot.P-=P.WorldOrigin;
            if (!PrepareDodge(P.State,P.NextLower,P.Context,P.Work,D.DodgeInputs.GetData()+D.DodgePrepared.Num()*362,&PlannedRoot))
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
        AProphecyAgent* Actor=AgentActors[Index];
        auto PlannedRoot=DefenseRoot(SlashComponentWorld(Actor,Agent.CurRootPos,Agent.CurRootYaw));PlannedRoot.P-=P.WorldOrigin;
#if !UE_BUILD_SHIPPING
        TSharedPtr<FJsonObject> Audit;
        if (ProphecyDodgeAudit::Enabled.GetValueOnGameThread())
        {
            using namespace ProphecyDodgeAudit;Audit=MakeShared<FJsonObject>();Audit->SetObjectField(TEXT("before"),State(P.State));
            Array(Audit,TEXT("input"),D.DodgeInputs.GetData()+Lane*362,362);Array(Audit,TEXT("output"),Output,112);
            Array(Audit,TEXT("pelvis"),&P.Context.AttackerPelvis[0][0],18);Array(Audit,TEXT("collider"),&P.Context.AttackerCollider[0][0],18);
            Vector(Audit,TEXT("target"),P.Context.TargetWorld);Vector(Audit,TEXT("world_origin"),P.WorldOrigin);
            Array(Audit,TEXT("attack_controls"),P.Context.AttackControls,5);Audit->SetNumberField(TEXT("event"),P.Context.Event);
            Root(Audit,TEXT("planned_root"),PlannedRoot);
        }
#endif
        if (!Finite || !CompleteDodge(P.State,P.Work,P.NextLower,Output,D.DodgeGeometry,Pose,Modified,Upper,&PlannedRoot,
            ProphecyLegChainDebug::IsEnabled(AgentActors[Index]))) { P.Status.Active=false;continue; }
#if !UE_BUILD_SHIPPING
        if (Audit)
        {
            using namespace ProphecyDodgeAudit;Audit->SetObjectField(TEXT("after"),State(P.State));float Positions[75],Rotations[225];
            for (int32 I=0;I<25;++I) { Write(Positions+I*3,Pose.P[I]);for (int32 J=0;J<3;++J) Write(Rotations+I*9+J*3,Pose.R[I].V[J]); }
            Array(Audit,TEXT("positions"),Positions,75);Array(Audit,TEXT("rotations"),Rotations,225);
            Save(P,Impl->Agents[P.AttackerIndex].Slash.Frame,TEXT("upper"),Audit);
        }
#endif
        FMemory::Memcpy(P.PreviousComponent,P.CurrentComponent,sizeof(P.CurrentComponent));
        DefenseForearmRoll(*Impl,D.Bones,Pose);
        const bool bContactStop=DefensePhysicalStop(*Impl,P,P.CurrentPose,Pose,P.WorldOrigin);
        DefenseComponentPose(Pose,PoseRoot,D.Bones,P.CurrentComponent);P.CurrentPose=Pose;
        Agent.PreviousPublishedRoot=Agent.PublishedRoot;Agent.PreviousPublishedYaw=Agent.PublishedYaw;
        Agent.PublishedRoot=DodgeManagedPosition(P,PoseRoot);Agent.PublishedYaw=DodgeManagedYaw(P,PoseRoot);
        Agent.PrevRootPos=Agent.PublishedRoot;Agent.PrevRootYaw=Agent.PublishedYaw;
        const FVector3f Correction=DodgeManagedPosition(P,P.State.CurrentRoot)-Agent.CurRootPos;
        const float YawCorrection=WrapAngle(DodgeManagedYaw(P,P.State.CurrentRoot)-Agent.CurRootYaw);
        // Add the learned displacement without turning it into mover momentum or
        // applying player/magic velocity a second time. Keep both yaw history ends.
        Agent.CurRootPos+=Correction;Agent.CurRootYaw+=YawCorrection;
        Agent.MoverState.position.x+=Correction.X;Agent.MoverState.position.z+=Correction.Z;
        Agent.MoverState.yaw_radians+=YawCorrection;Agent.MoverState.previous_yaw_radians+=YawCorrection;
        Agent.MoverIntent.orientation_yaw_radians+=YawCorrection;
        ResolvedMoverTargets.FindChecked(this)[Index].Target.orientation_yaw_radians+=YawCorrection;
        Agent.MoverState.distance_travelled+=FVector2f(Correction.X,Correction.Z).Size();
        if (YawCorrection!=0)
        {
            if (auto* Smoothing=ProphecyNNRootWindow::Find(Actor))
                for (auto& Sample:Smoothing->Samples) Sample.Direction+=YawCorrection;
            if (float* History=RootImpulseSmoothingYaw.Find(Actor)) *History+=YawCorrection;
            if (Actor->bUseBlueprintLocomotionInput && !Actor->LocomotionInput.FacingWorldDirection.IsNearlyZero())
                Actor->LocomotionInput.FacingWorldDirection=FQuat(FVector::UpVector,-double(YawCorrection)).RotateVector(Actor->LocomotionInput.FacingWorldDirection);
        }
        // Expose the corrected future trajectory, keeping root0 at the current
        // causal pose. This correction is not rerun through the lower NN.
        float* Future=Impl->InputBuffer.GetData()+Index*InputDim+120;
        const auto LocalCorrection=TransformRow(Correction,YawMatrix(Agent.FedInputYaw));
        for (int32 I=1;I<=FutureWindow;++I,Future+=4)
        {
            Future[0]+=LocalCorrection.X/(I*Impl->MaxSpeedScaleFinal);
            Future[1]+=LocalCorrection.Z/(I*Impl->MaxSpeedScaleFinal);
            const float Yaw=FMath::Atan2(Future[3],Future[2])+YawCorrection;
            Future[2]=FMath::Cos(Yaw);Future[3]=FMath::Sin(Yaw);
        }
        Agent.PinProbability={P.Pins[0],P.Pins[1]};Agent.bHasFedFutureRoots=false;
        Agent.bPreviousPublishedUseWalkPolicy=Agent.bPublishedUseWalkPolicy;Agent.PreviousPublishedWalkWeight=Agent.PublishedWalkWeight;Agent.PreviousPublishedLegWalkWeights=Agent.PublishedLegWalkWeights;
        Agent.bPublishedUseWalkPolicy=P.Category==0;Agent.PublishedWalkWeight=P.Category==0?1.f:0.f;Agent.PublishedLegWalkWeights=FVector2f(Agent.PublishedWalkWeight,Agent.PublishedWalkWeight);
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
        ++P.Status.CompletedSteps;P.Status.AttackerFrame=Impl->Agents[P.AttackerIndex].Slash.Frame;
        if (bContactStop)
        {
#if !UE_BUILD_SHIPPING
            if (!ProphecyDodgeAudit::ContinueAfterContact.GetValueOnGameThread())
#endif
                P.Status.Active=false;
        }
    }
}
