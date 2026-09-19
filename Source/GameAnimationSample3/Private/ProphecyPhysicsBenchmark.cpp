#include "ProphecyPhysicsBenchmark.h"
#include "ProphecyGameModuleSimd.h"
#include "ProphecyPhysicsBenchmarkRigAudit.h"
#include "ProphecyAgent.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyManualServoCapture.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltCharacterProfiling.h"
#include "ProphecyJoltBenchmarkProcessorControl.h"
#include "ProphecyJoltBenchmarkChaosPause.h"
#include "ProphecyJoltBenchmarkQueryPadding.h"
#include "ProfilingDebugging/CsvProfiler.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNodeBase.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Dom/JsonObject.h"
#include "HAL/IConsoleManager.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/DefaultValueHelper.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "PhysicsProxy/SingleParticlePhysicsProxy.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace ProphecySterileBench
{
    TSharedPtr<FJsonObject> EngineISPCSettings()
    {
        auto O = MakeShared<FJsonObject>();
        FModuleStatus Engine;
        const bool bEngineLoaded = FModuleManager::Get().QueryModule(FName(TEXT("Engine")), Engine) && Engine.bIsLoaded;
        O->SetBoolField(TEXT("engine_module_loaded"), bEngineLoaded);
        O->SetStringField(TEXT("engine_module_file"), Engine.FilePath);
        const TCHAR* Names[] = { TEXT("a.BonePose.ISPC"), TEXT("a.SkinnedAsset.ISPC"), TEXT("a.SkeletalMesh.ISPC") };
        bool Registered[3] = {}, Enabled[3] = {};
        auto CVars = MakeShared<FJsonObject>();
        for (int32 Index = 0; Index < UE_ARRAY_COUNT(Names); ++Index)
        {
            const IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(Names[Index], false);
            Registered[Index] = CVar && CVar->IsVariableBool();
            Enabled[Index] = Registered[Index] && CVar->GetBool();
            auto Entry = MakeShared<FJsonObject>();
            Entry->SetBoolField(TEXT("registered_bool"), Registered[Index]);
            if (CVar)
            {
                Entry->SetStringField(TEXT("value_text"), CVar->GetString());
                Entry->SetNumberField(TEXT("flags"), CVar->GetFlags());
            }
            if (Registered[Index]) Entry->SetBoolField(TEXT("enabled"), Enabled[Index]);
            else Entry->SetField(TEXT("enabled"), MakeShared<FJsonValueNull>());
            CVars->SetObjectField(Names[Index], Entry);
        }
        O->SetObjectField(TEXT("runtime_cvars"), CVars);
        // Stock UE 5.7 registers these bool refs in Engine only under INTEL_ISPC && !UE_BUILD_SHIPPING.
        // Missing controls cannot distinguish a compiled-out path from a fixed Shipping path.
        const bool bAllRegistered = bEngineLoaded && Registered[0] && Registered[1] && Registered[2];
        if (bAllRegistered) O->SetBoolField(TEXT("compiled_support_proven_by_stock_engine_controls"), true);
        else O->SetField(TEXT("compiled_support_proven_by_stock_engine_controls"), MakeShared<FJsonValueNull>());
        if (bEngineLoaded && Registered[0]) O->SetBoolField(TEXT("bone_pose_effective_enabled"), Enabled[0]);
        else O->SetField(TEXT("bone_pose_effective_enabled"), MakeShared<FJsonValueNull>());
        if (bEngineLoaded && Registered[1] && Registered[2])
            O->SetBoolField(TEXT("component_space_effective_enabled"), Enabled[1] && Enabled[2]);
        else O->SetField(TEXT("component_space_effective_enabled"), MakeShared<FJsonValueNull>());
        O->SetStringField(TEXT("evidence"), TEXT("Read-only loaded-module and stock UE 5.7 runtime controls; deprecated a.SkeletalMesh.ISPC=false overrides a.SkinnedAsset.ISPC. Null means unavailable evidence, not disabled. No game-module INTEL_ISPC inference, ISA-dispatch identification, execution counter, or setting mutation."));
        return O;
    }
    constexpr const TCHAR* QueryPaddingCVar = TEXT("p.aabbtree.DynamicTreeBoundingBoxPadding");
    TSharedPtr<FJsonObject> QueryTreeSettings()
    {
        auto O = MakeShared<FJsonObject>();
        FString Requested;
        const bool bRequested = FParse::Value(FCommandLine::Get(), TEXT("PhysicsBenchQueryTreePaddingCm="), Requested);
        O->SetBoolField(TEXT("padding_override_requested"), bRequested);
        if (bRequested) O->SetStringField(TEXT("requested_padding_cm_text"), Requested);
        auto CVars = MakeShared<FJsonObject>();
        for (const TCHAR* Name : {
            QueryPaddingCVar,
            TEXT("p.aabbtree.DynamicTreeLeafCapacity"),
            TEXT("p.aabbtree.DynamicTreeLeafEnlargePercent"),
            TEXT("p.BroadphaseType"),
            TEXT("p.Chaos.AccelerationStructureSplitStaticDynamic"),
            TEXT("p.Chaos.AccelerationStructureUseDynamicTree"),
            TEXT("p.Chaos.AccelerationStructureIsolateQueryOnlyObjects"),
            TEXT("p.Chaos.AccelerationStructureUseDirtyTreeInsteadOfGrid"),
            TEXT("p.Chaos.AccelerationStructureCacheOverlappingLeaves") })
        {
            const IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(Name);
            if (CVar) CVars->SetNumberField(Name, CVar->GetFloat());
            else CVars->SetField(Name, MakeShared<FJsonValueNull>());
        }
        O->SetObjectField(TEXT("runtime_cvars"), CVars);
        O->SetStringField(TEXT("scope"), TEXT("Read-only boundary snapshots. Padding affects dynamic AABB-tree nodes, not body geometry or exact element bounds. This is not a reinsert counter; larger bounds can increase candidate traversal."));
        return O;
    }
    bool ValidateRequestedQueryPadding(FString& OutError)
    {
        FString RequestedText;
        if (!FParse::Value(FCommandLine::Get(), TEXT("PhysicsBenchQueryTreePaddingCm="), RequestedText)) return true;
        float Requested = 0;
        if (!FDefaultValueHelper::ParseFloat(RequestedText, Requested) || !FMath::IsFinite(Requested)
            || Requested < 0 || Requested > 1000)
        { OutError = TEXT("PhysicsBenchQueryTreePaddingCm must be finite and between 0 and 1000 cm."); return false; }
        const IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(QueryPaddingCVar);
        if (!CVar || !FMath::IsNearlyEqual(CVar->GetFloat(), Requested, 1.e-4f))
        {
            OutError = FString::Printf(TEXT("Requested query tree padding %g cm is not active at the measurement boundary (CVar %s, current %g)."),
                Requested, CVar ? TEXT("present") : TEXT("missing"), CVar ? CVar->GetFloat() : -1.f);
            return false;
        }
        return true;
    }
    void AnimateBone(FTransform& Bone, FName Name, double Time)
    {
        if (Name == TEXT("head") || Name == TEXT("upperarm_l") || Name == TEXT("upperarm_r"))
            Bone.SetRotation((Bone.GetRotation() * FQuat(FVector::UpVector,.12*FMath::Sin(Time*2))).GetNormalized());
        if (Name == TEXT("pelvis")) Bone.AddToTranslation(FVector(0,0,1.5*FMath::Sin(Time*2)));
    }
    const TCHAR* BenchmarkModeNames[] = {TEXT("Empty"), TEXT("Kinematic"), TEXT("NativeWorld"), TEXT("NativeLocal"),
        TEXT("NativeLocalPelvis"), TEXT("JointMotors"), TEXT("JointMotorsPelvis"), TEXT("WorldForcePD"), TEXT("Passive"), TEXT("WorldOneStep"), TEXT("FullSim"), TEXT("AgentHalfSim"), TEXT("ManualCapture"), TEXT("ManualReplay"), TEXT("JoltLive"), TEXT("JoltCrowd"), TEXT("ManualCrowd"), TEXT("NNJoltCrowd")};
    constexpr int32 ManualMode = 12;
    constexpr int32 ManualReplayMode = 13;
    constexpr int32 LiveJoltMode = 14;
    constexpr int32 MultiJoltMode = 15;
    constexpr int32 ManualCrowdMode = 16;
    constexpr int32 NNJoltMode = 17;
    bool IsRecordingMode(int32 Mode) { return Mode == ManualMode || Mode == ManualReplayMode; }
    bool IsJoltMode(int32 Mode) { return Mode == LiveJoltMode || Mode == MultiJoltMode || Mode == NNJoltMode; }
    bool IsManualFixtureMode(int32 Mode) { return IsRecordingMode(Mode) || IsJoltMode(Mode) || Mode == ManualCrowdMode; }
    FTransform AgentTarget(int32 I) { return FTransform(FVector((I%10)*600,(I/10)*600,10)); }
    void PublishAgentPose(USkeletalMesh* Asset, int32 I, double Time, double WorldTime)
    {
        const auto& Ref=Asset->GetRefSkeleton();
        TArray<FName> BoneNames; TArray<FTransform> Local=Ref.GetRefBonePose();
        for(int32 B=0;B<Local.Num();++B) { BoneNames.Add(Ref.GetBoneName(B)); AnimateBone(Local[B],BoneNames.Last(),Time); }
        TArray<FTransform> CS; CS.SetNum(Local.Num());
        for(int32 B=0;B<Local.Num();++B) { const int32 P=Ref.GetParentIndex(B); CS[B]=P==INDEX_NONE?Local[B]:Local[B]*CS[P]; }
        // Full Sim consumes component-space endpoints, not the local-only overload.
        FProphecyNNPoseStore::SetAgentLocalPose(991000+I,BoneNames,Local,CS,CS,AgentTarget(I),AgentTarget(I),WorldTime);
    }
    TArray<TSharedPtr<FJsonValue>> Values(const TArray<double>& In)
    {
        TArray<TSharedPtr<FJsonValue>> Out; Out.Reserve(In.Num());
        for (double V : In) Out.Add(MakeShared<FJsonValueNumber>(V));
        return Out;
    }
    TSharedPtr<FJsonObject> Stats(TArray<double> In)
    {
        auto O = MakeShared<FJsonObject>();
        if (In.IsEmpty()) return O;
        double Sum = 0; for (double V : In) Sum += V;
        In.Sort(); const double Mean = Sum/In.Num();
        O->SetNumberField(TEXT("mean_ms"), Mean);
        O->SetNumberField(TEXT("median_ms"), In[In.Num()/2]);
        O->SetNumberField(TEXT("p95_ms"), In[FMath::Min(In.Num()-1, int32(.95*In.Num()))]);
        O->SetNumberField(TEXT("equivalent_fps"), Mean > 0 ? 1000/Mean : 0);
        return O;
    }
    class FPoseProxy final : public FAnimInstanceProxy
    {
    public:
        FPoseProxy(UAnimInstance* A) : FAnimInstanceProxy(A) {}
        double Time = 0;
        virtual void PreUpdate(UAnimInstance* A, float Dt) override
        { FAnimInstanceProxy::PreUpdate(A, Dt); Time = CastChecked<UProphecyPhysicsBenchAnim>(A)->PoseTime; }
        virtual bool Evaluate(FPoseContext& Out) override
        {
            Out.ResetToRefPose();
            const auto& Container = Out.Pose.GetBoneContainer();
            const auto& Ref = Container.GetReferenceSkeleton();
            for (FCompactPoseBoneIndex I : Out.Pose.ForEachBoneIndex())
            {
                AnimateBone(Out.Pose[I], Ref.GetBoneName(Container.GetSkeletonIndex(I)), Time);
            }
            return true;
        }
    };
}
FAnimInstanceProxy* UProphecyPhysicsBenchAnim::CreateAnimInstanceProxy() { return new ProphecySterileBench::FPoseProxy(this); }
void UProphecyPhysicsBenchAnim::DestroyAnimInstanceProxy(FAnimInstanceProxy* P) { delete P; }

bool UProphecyPhysicsBenchmarkSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
    return Super::ShouldCreateSubsystem(Outer) && FParse::Param(FCommandLine::Get(), TEXT("ProphecyPhysicsBenchmark"));
}

void UProphecyPhysicsBenchmarkSubsystem::OnWorldBeginPlay(UWorld& World)
{
    Super::OnWorldBeginPlay(World);
    if (World.WorldType != EWorldType::Game) return; // Never run this harness in PIE/editor.
    FParse::Value(FCommandLine::Get(), TEXT("PhysicsBenchCount="), Count);
    FParse::Value(FCommandLine::Get(), TEXT("PhysicsBenchWarmup="), Warmup);
    FParse::Value(FCommandLine::Get(), TEXT("PhysicsBenchSamples="), Samples);
    FParse::Value(FCommandLine::Get(), TEXT("PhysicsBenchRepeats="), Repeats);
    Count = FMath::Clamp(Count,1,1000); Warmup = FMath::Max(1,Warmup); Samples = FMath::Max(2,Samples); Repeats = FMath::Clamp(Repeats,1,10);
    Output = FPaths::ProjectSavedDir()/TEXT("Benchmarks/sterile_physics.json");
    FString Override; if (FParse::Value(FCommandLine::Get(),TEXT("PhysicsBenchJson="),Override)) Output = FPaths::ConvertRelativePathToFull(Override);
    FString GameProfileError;
    if (!ProphecyGameModuleSimd::ValidateRequestedProfile(GameProfileError)) { Finish(GameProfileError); return; }
    if (GEngine) { GEngine->bSmoothFrameRate = false; GEngine->bUseFixedFrameRate = false; GEngine->SetMaxFPS(0); }
    FApp::SetUseFixedTimeStep(true); FApp::SetFixedDeltaTime(1./60.);
    // Runtime-only process settings. No project ini or asset edits.
    UPhysicsSettings::Get()->bSubstepping = false;
    for (const TCHAR* C : {TEXT("t.IdleWhenNotForeground"),TEXT("r.VSync")})
        if (auto* V = IConsoleManager::Get().FindConsoleVariable(C)) V->Set(0,ECVF_SetByCode);
    FString NativeQueryPaddingError;
    if (!ProphecyJolt::BenchmarkQueryPadding::Begin(*this, World, NativeQueryPaddingError))
    { Finish(NativeQueryPaddingError); return; }
    MeshAsset = LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if (!MeshAsset || !MeshAsset->GetPhysicsAsset()) { Finish(TEXT("Missing benchmark mesh/physics asset")); return; }
    if (FParse::Param(FCommandLine::Get(),TEXT("PhysicsBenchSwitchTest"))) { ValidateAgentSwitches(); return; }
    // Explicitly refuse arbitrary gameplay maps; sterile Entry plus native GameMode only.
    for (TActorIterator<AActor> It(&World); It; ++It)
        if (It->GetClass()->HasAnyClassFlags(CLASS_CompiledFromBlueprint)) { Finish(TEXT("Blueprint actor present; refusing contaminated benchmark")); return; }
    FString Filter; TArray<FString> Included;
    // Windows startup may remove argument quotes. FParse otherwise stops at
    // the first comma, silently selecting only one controller.
    if(FParse::Value(FCommandLine::Get(),TEXT("PhysicsBenchMethods="),Filter,false)) Filter.ParseIntoArray(Included,TEXT(","));
    if (Included.Contains(TEXT("ManualReplay")))
    { Finish(TEXT("ManualReplay is inserted automatically after a successful ManualCapture")); return; }
    if (Included.Contains(TEXT("ManualCapture")) || Included.Contains(TEXT("JoltLive")))
    {
        if (Count != 1 || Repeats != 1 || Included.Num() != 1 || Warmup < 30 || Samples > 3600)
        { Finish(TEXT("ManualCapture/JoltLive requires Count=1, Repeats=1, Warmup>=30, Samples<=3600 and no other methods")); return; }
        if (UPhysicsSettings::Get()->bTickPhysicsAsync)
        { Finish(TEXT("ManualCapture requires synchronous physics for one callback per fixed frame")); return; }
    }
    if (Included.Contains(TEXT("JoltCrowd")) && (Count < 2 || Count > 100 || Repeats != 1 || Included.Num() != 1
        || Warmup < 30 || Samples > 3600 || UPhysicsSettings::Get()->bTickPhysicsAsync))
    { Finish(TEXT("JoltCrowd requires Count=2..100, Repeats=1, Warmup>=30, Samples<=3600 and synchronous physics as the sole method")); return; }
    if (Included.Contains(TEXT("ManualCrowd")) && (Count < 1 || Count > 100 || Repeats != 1 || Included.Num() != 1
        || Warmup < 30 || Samples > 3600 || UPhysicsSettings::Get()->bTickPhysicsAsync))
    { Finish(TEXT("ManualCrowd requires Count=1..100, Repeats=1, Warmup>=30, Samples<=3600 and synchronous physics as the sole method")); return; }
    if (Included.Contains(TEXT("NNJoltCrowd")) && (Count < 2 || Count > 100 || Repeats != 1 || Included.Num() != 1
        || Warmup < 30 || Samples < 60 || Samples > 3600 || UPhysicsSettings::Get()->bTickPhysicsAsync
        || !FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchFloorOnly"))
        || !FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchMovementOnly"))))
    { Finish(TEXT("NNJoltCrowd requires Count=2..100, Repeats=1, Warmup>=30, Samples=60..3600, synchronous physics, FloorOnly and MovementOnly as the sole method")); return; }
    for (int32 R = 0; R < Repeats; ++R) for (int32 F = 0; F < 2; ++F) for (int32 M = 0; M < UE_ARRAY_COUNT(ProphecySterileBench::BenchmarkModeNames); ++M)
        if (!FParse::Param(FCommandLine::Get(),TEXT("PhysicsBenchFloorOnly")) || F==1)
        if (M != ProphecySterileBench::ManualMode || Included.Contains(TEXT("ManualCapture")))
        if (M != ProphecySterileBench::ManualReplayMode)
        if (M != ProphecySterileBench::LiveJoltMode || Included.Contains(TEXT("JoltLive")))
        if (M != ProphecySterileBench::MultiJoltMode || Included.Contains(TEXT("JoltCrowd")))
        if (M != ProphecySterileBench::ManualCrowdMode || Included.Contains(TEXT("ManualCrowd")))
        if (M != ProphecySterileBench::NNJoltMode || Included.Contains(TEXT("NNJoltCrowd")))
        if(Included.IsEmpty() || Included.Contains(ProphecySterileBench::BenchmarkModeNames[M])) Cases.Add({M,bool(F),R});
    if(Cases.IsEmpty()) { Finish(TEXT("No matching benchmark methods")); return; }
    if (ProphecyJolt::BenchmarkChaosPause::IsRequested()
        && (Included.Num() != 1 || !Included.Contains(TEXT("NNJoltCrowd")) || Cases.Num() != 1
            || UPhysicsSettings::Get()->bSubstepping))
    { Finish(TEXT("PhysicsBenchPauseChaos requires sole NNJoltCrowd, one case, and non-substepped synchronous physics.")); return; }
    FRandomStream Shuffle(90210);
    for (int32 I = Cases.Num()-1; I > 0; --I) Cases.Swap(I,Shuffle.RandRange(0,I));
    RunStart = FPlatformTime::Seconds();
    StartHandle = FWorldDelegates::OnWorldPreActorTick.AddUObject(this,&UProphecyPhysicsBenchmarkSubsystem::StartTick);
    EndHandle = FWorldDelegates::OnWorldPostActorTick.AddUObject(this,&UProphecyPhysicsBenchmarkSubsystem::EndTick);
    UE_LOG(LogTemp,Display,TEXT("STERILE_PHYSICS started count=%d cases=%d fixed_dt=1/60 nullrhi=%d"),Count,Cases.Num(),FParse::Param(FCommandLine::Get(),TEXT("nullrhi")));
}

void UProphecyPhysicsBenchmarkSubsystem::ClearCase()
{
    FString ChaosPauseRestoreError;
    if (!ProphecyJolt::BenchmarkChaosPause::Restore(*this, ChaosPauseRestoreError))
        UE_LOG(LogTemp, Error, TEXT("Benchmark Chaos pause cleanup restoration failed: %s"), *ChaosPauseRestoreError);
    for (UProphecyHalfSimDriveComponent* D : Drivers) if (IsValid(D)) D->Stop();
    for (AActor* A : Actors) if (IsValid(A))
    {
        if (AProphecyAgent* Agent = Cast<AProphecyAgent>(A)) Agent->ReleaseManualFollowerSubstepTargets();
        A->Destroy();
    }
    Actors.Reset(); Meshes.Reset(); Drivers.Reset();
    if (Cases.IsValidIndex(CaseIndex) && ProphecySterileBench::IsJoltMode(Cases[CaseIndex].Mode))
        if (auto* Owner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>()) Owner->ShutdownSimulation();
    LiveJoltFrames.Reset();
    MovementCameraDetachments.Reset();
    LastLiveJoltRevision = 0;
    ManualInitialRig.Reset();
    ManualCrowdState.Reset();
    NNJoltState.Reset();
    for(int32 I=0;I<Count;++I) FProphecyNNPoseStore::ClearAgentPose(991000+I);
}

void UProphecyPhysicsBenchmarkSubsystem::ValidateAgentSwitches()
{
    // Separate functional test, never included in timing samples. Real agent API,
    // native class, synthetic pose-store data only; no NN manager or Blueprint.
    auto* A=GetWorld()->SpawnActorDeferred<AProphecyAgent>(AProphecyAgent::StaticClass(),FTransform::Identity);
    A->bAutoEnsureStandaloneNNManager=false;
    A->bManualNNPoseApplication=false;
    A->bAutoApplyWorldMagnetization=false;
    A->bAutoPublishManualFollowerSubstepTargets=false;
    A->FinishSpawning(FTransform::Identity);
    Actors.Add(A);
    auto* M=A->GetPoseReferenceMesh();
    M->SetSkeletalMesh(MeshAsset);
    const auto& Ref=MeshAsset->GetRefSkeleton();
    TArray<FName> Names; for(int32 I=0; I<Ref.GetNum(); ++I) Names.Add(Ref.GetBoneName(I));
    constexpr int32 PoseId=990909;
    FProphecyNNPoseStore::SetAgentLocalPose(PoseId,Names,Ref.GetRefBonePose());
    A->ConfigureNNPoseDataSource(PoseId,1.f/30.f,false);
    FString Error;
    if (!A->SetSimulationMode(EProphecyAgentSimulationMode::HalfSim) || A->GetSimulationMode()!=EProphecyAgentSimulationMode::HalfSim)
        Error=TEXT("Agent did not enter Half Sim");
    int32 Passed=0;
    double MaxError=0;
    for(int32 From=0; From<8 && Error.IsEmpty(); ++From) for(int32 To=0; To<8 && Error.IsEmpty(); ++To)
    {
        if(From==To) continue;
        A->SetHalfSimDriveMethod(EProphecyHalfSimDriveMethod(From));
        auto* Native=A->FindComponentByClass<UPhysicalAnimationComponent>();
        if(Native->IsComponentTickEnabled()) Native->TickComponent(1.f/60,LEVELTICK_All,nullptr);
        TArray<FBodyInstance*> OldBodies=M->Bodies;
        TArray<FTransform> Transforms; TArray<FVector> Linear,Angular;
        for(auto* B:OldBodies)
        {
            B->SetLinearVelocity(FVector(2,3,4),false);
            B->SetAngularVelocityInRadians(FVector(.1,.2,.3),false);
            Transforms.Add(B->GetUnrealWorldTransform()); Linear.Add(B->GetUnrealWorldVelocity()); Angular.Add(B->GetUnrealWorldAngularVelocityInRadians());
        }
        if (!A->SetHalfSimDriveMethod(EProphecyHalfSimDriveMethod(To)) || A->GetHalfSimDriveMethod()!=EProphecyHalfSimDriveMethod(To))
            { Error=TEXT("Drive selector failed"); break; }
        if(Native->IsComponentTickEnabled()) Native->TickComponent(1.f/60,LEVELTICK_All,nullptr);
        auto* D=A->FindComponentByClass<UProphecyHalfSimDriveComponent>();
        const int32 BCount=OldBodies.Num();
        const int32 Targets=To==0||To==2?BCount:To==1?BCount-1:To==4?1:0;
        if(!D || D->GetNativeTargetCount()!=Targets || M->Bodies.Num()!=BCount)
            { Error=TEXT("Target/body count mismatch"); break; }
        TInlineComponentArray<USkeletalMeshComponent*> Skels(A);
        if(Skels.Num()!=1) { Error=TEXT("Unexpected extra mesh"); break; }
        for(int32 I=0; I<BCount; ++I)
        {
            auto* B=M->Bodies[I];
            if(B!=OldBodies[I] || !B->IsInstanceSimulatingPhysics()) { Error=TEXT("Dynamic bodies recreated or disabled"); break; }
            MaxError=FMath::Max(MaxError,FVector::Distance(B->GetUnrealWorldTransform().GetLocation(),Transforms[I].GetLocation()));
            MaxError=FMath::Max(MaxError,double(B->GetUnrealWorldTransform().GetRotation().GetNormalized().AngularDistance(Transforms[I].GetRotation().GetNormalized())));
            MaxError=FMath::Max(MaxError,FVector::Distance(B->GetUnrealWorldVelocity(),Linear[I]));
            MaxError=FMath::Max(MaxError,FVector::Distance(B->GetUnrealWorldAngularVelocityInRadians(),Angular[I]));
        }
        if(MaxError>1.e-4) { Error=TEXT("Drive switch changed rigid-body state"); break; }
        ++Passed;
    }
    A->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic);
    if(M->IsSimulatingPhysics(TEXT("pelvis"))) Error=TEXT("Could not return to kinematic");
    FProphecyNNPoseStore::ClearAgentPose(PoseId);
    auto O=MakeShared<FJsonObject>(); O->SetNumberField(TEXT("ordered_pairs_passed"),Passed);
    O->SetNumberField(TEXT("max_immediate_state_change"),MaxError);
    O->SetBoolField(TEXT("returned_kinematic"),!M->IsSimulatingPhysics(TEXT("pelvis")));
    Results.Add(MakeShared<FJsonValueObject>(O));
    Finish(Error);
}

void UProphecyPhysicsBenchmarkSubsystem::PrepareCase()
{
    ClearCase();
    CollectGarbage(RF_NoFlags);
    ++CaseIndex; if (!Cases.IsValidIndex(CaseIndex)) { Finish(); return; }
    const FCase C = Cases[CaseIndex];
    if (C.Floor)
    {
        auto* A = GetWorld()->SpawnActor<AActor>(); Actors.Add(A);
        auto* Box = NewObject<UBoxComponent>(A);
        A->SetRootComponent(Box); A->AddInstanceComponent(Box);
        Box->SetBoxExtent(FVector(50000,50000,10)); Box->SetWorldLocation(FVector(0,0,-10));
        Box->SetCollisionObjectType(ECC_WorldStatic); Box->SetCollisionEnabled(ECollisionEnabled::PhysicsOnly);
        Box->SetCollisionResponseToAllChannels(ECR_Block); Box->SetHiddenInGame(true); Box->RegisterComponent();
    }
    if (C.Mode != 0) for (int32 I = 0; I < Count; ++I)
    {
        if (ProphecySterileBench::IsManualFixtureMode(C.Mode))
        {
            FString Error;
            if (!PrepareManualAgent(I, C.Floor, Error)) { Finish(Error); return; }
            continue;
        }
        if(C.Mode>=10)
        {
            auto* Agent=GetWorld()->SpawnActorDeferred<AProphecyAgent>(AProphecyAgent::StaticClass(),FTransform::Identity,nullptr,nullptr,ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
            Agent->bAutoEnsureStandaloneNNManager=false;
            Agent->bManualNNPoseApplication=false;
            Agent->bAutoPublishManualFollowerSubstepTargets=false;
            Agent->bAutoApplyWorldMagnetization=true;
            Agent->FinishSpawning(FTransform::Identity); Actors.Add(Agent);
            auto* M=Agent->GetPoseReferenceMesh(); M->SetSkeletalMesh(MeshAsset);
            M->SetWorldTransform(ProphecySterileBench::AgentTarget(I));
            ProphecySterileBench::PublishAgentPose(MeshAsset,I,I*.031,GetWorld()->GetTimeSeconds());
            Agent->ConfigureNNPoseDataSource(991000+I,1.f/60.f,false);
            M->SetAnimInstanceClass(UProphecyNNLocomotionAnimInstance::StaticClass());
            auto* Anim=Cast<UProphecyNNLocomotionAnimInstance>(M->GetAnimInstance());
            if(!Anim) { Finish(TEXT("Native agent animation failed initialization")); return; }
            Anim->AgentId=991000+I; Anim->NNPoseIntervalSeconds=1.f/60.f; Anim->bInterpolateNNPose=false;
            M->TickAnimation(0,false); M->RefreshBoneTransforms();
            Agent->SetAllBodyMagnetization(true,1,1);
            const auto Mode=C.Mode==10?EProphecyAgentSimulationMode::Physical:EProphecyAgentSimulationMode::HalfSim;
            if(!Agent->SetSimulationMode(Mode) || Agent->GetSimulationMode()!=Mode) { Finish(TEXT("Native agent failed mode entry")); return; }
            M->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
            M->SetCollisionObjectType(ECC_PhysicsBody); M->SetCollisionResponseToAllChannels(ECR_Ignore);
            M->SetCollisionResponseToChannel(ECC_WorldStatic,ECR_Block);
            M->SetGenerateOverlapEvents(false); M->SetNotifyRigidBodyCollision(false);
            M->SetEnableGravity(C.Floor); M->SetCastShadow(false); M->SetHiddenInGame(true); M->SetForcedLOD(1);
            M->bEnableUpdateRateOptimizations=false;
            M->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
            for(auto& Pair:Agent->BodyMagnetizationSettings) Pair.Value.bCancelGravity=C.Floor;
            for(auto* B:M->Bodies) if(B) { B->SetPositionSolverIterationCount(4); B->SetVelocitySolverIterationCount(1); B->SetProjectionSolverIterationCount(0); B->SetUseCCD(false); B->SetUseMACD(false); }
            if(auto* D=Agent->FindComponentByClass<UProphecyHalfSimDriveComponent>()) Drivers.Add(D);
            Meshes.Add(M);
            continue;
        }
        auto* A = GetWorld()->SpawnActor<AActor>(); A->SetActorTickEnabled(false); Actors.Add(A);
        auto* M = NewObject<USkeletalMeshComponent>(A);
        A->SetRootComponent(M); A->AddInstanceComponent(M);
        M->SetSkeletalMesh(MeshAsset); M->SetWorldLocation(FVector((I%10)*600,(I/10)*600,10));
        M->SetCollisionObjectType(ECC_PhysicsBody); M->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        M->SetCollisionResponseToAllChannels(ECR_Ignore);
        M->SetCollisionResponseToChannel(ECC_WorldStatic,ECR_Block);
        // No crowd-to-crowd collision. PHAT's own collision-disable table remains unchanged.
        M->SetGenerateOverlapEvents(false); M->SetNotifyRigidBodyCollision(false);
        M->PhysicsTransformUpdateMode = EPhysicsTransformUpdateMode::ComponentTransformIsKinematic;
        M->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipSimulatingBones;
        M->bEnableUpdateRateOptimizations = false;
        M->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        M->SetCastShadow(false); M->SetHiddenInGame(true); M->SetForcedLOD(1);
        M->RegisterComponent(); M->SetAnimInstanceClass(UProphecyPhysicsBenchAnim::StaticClass());
        M->TickAnimation(0,false); M->RefreshBoneTransforms();
        M->SetEnableGravity(C.Floor); M->SetAllBodiesSimulatePhysics(C.Mode != 1);
        M->SetAllBodiesPhysicsBlendWeight(C.Mode == 1 ? 0.f : 1.f);
        for (FBodyInstance* B : M->Bodies) if (B)
        {
            B->SetPositionSolverIterationCount(4); B->SetVelocitySolverIterationCount(1); B->SetProjectionSolverIterationCount(0);
            B->SetUseCCD(false); B->SetUseMACD(false);
        }
        if (C.Mode >= 2)
        {
            auto* Native = NewObject<UPhysicalAnimationComponent>(A); A->AddInstanceComponent(Native); Native->RegisterComponent();
            auto* D = NewObject<UProphecyHalfSimDriveComponent>(A); A->AddInstanceComponent(D); D->RegisterComponent();
            FPhysicalAnimationData Gains;
            Gains.PositionStrength=40000; Gains.VelocityStrength=400;
            Gains.OrientationStrength=60000; Gains.AngularVelocityStrength=500;
            D->Configure(M,Native,EProphecyHalfSimDriveMethod(C.Mode-2),TEXT("pelvis"),Gains,1);
            Drivers.Add(D);
        }
        Meshes.Add(M);
    }
    if (C.Mode == ProphecySterileBench::NNJoltMode)
    {
        FString Error;
        if (!PrepareNNJoltCase(Error)) { Finish(Error); return; }
    }
    Frame=0; WorldMs.Reset(); FrameMs.Reset(); Before.Reset(); PreviousStart=0;
    UE_LOG(LogTemp,Display,TEXT("STERILE_PHYSICS case=%d/%d mode=%s fixture=%s repeat=%d"),CaseIndex+1,Cases.Num(),ProphecySterileBench::BenchmarkModeNames[C.Mode],C.Floor?TEXT("floor_gravity"):TEXT("air_no_gravity"),C.Repeat);
}

void UProphecyPhysicsBenchmarkSubsystem::StartTick(UWorld* W,ELevelTick,float)
{
    if (W != GetWorld() || Done) return;
    if (FPlatformTime::Seconds()-RunStart > 1800) { Finish(TEXT("30-minute watchdog")); return; }
    if (Advance) { PrepareCase(); Advance=false; if (Done) return; }
    if (FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchPClassGameThread"))
        && Cases[CaseIndex].Mode != ProphecySterileBench::MultiJoltMode
        && Cases[CaseIndex].Mode != ProphecySterileBench::NNJoltMode)
    { Finish(TEXT("PhysicsBenchPClassGameThread requires explicit JoltCrowd or NNJoltCrowd.")); return; }
    if (Frame == Warmup)
    {
        Before=Audit();
        FString QueryPaddingError;
        if (!ProphecySterileBench::ValidateRequestedQueryPadding(QueryPaddingError)) { Finish(QueryPaddingError); return; }
        if (Cases[CaseIndex].Mode == ProphecySterileBench::NNJoltMode)
        {
            FString Error;
            if (!InitializeNNJoltCase(Error)) { Finish(Error); return; }
        }
        else if (Cases[CaseIndex].Mode == ProphecySterileBench::MultiJoltMode)
        {
            FString Error;
            if (!InitializeMultiJoltCase(Error)) { Finish(Error); return; }
        }
        else if (Cases[CaseIndex].Mode == ProphecySterileBench::LiveJoltMode)
        {
            FString Error;
            if (!InitializeLiveJoltCase(Error)) { Finish(Error); return; }
        }
        else if (Cases[CaseIndex].Mode == ProphecySterileBench::ManualCrowdMode)
        {
            FString Error;
            if (!InitializeManualCrowdCase(Error)) { Finish(Error); return; }
        }
        else if (ProphecySterileBench::IsRecordingMode(Cases[CaseIndex].Mode))
        {
            FString Error;
            if (Cases[CaseIndex].Mode == ProphecySterileBench::ManualReplayMode && !RestoreManualReplayState(Error))
            { Finish(Error); return; }
            if (!CaptureManualRig(Error)) { Finish(Error); return; }
            if (!ProphecyManualServoCapture::BeginCapture(CastChecked<AProphecyAgent>(Meshes[0]->GetOwner()), Samples + 2, Samples + 2, Error))
            { Finish(Error); return; }
        }
    }
    if (Frame >= Warmup && (Cases[CaseIndex].Mode == ProphecySterileBench::MultiJoltMode
        || Cases[CaseIndex].Mode == ProphecySterileBench::NNJoltMode))
    {
        FString PlacementError;
        if (!ProphecyJolt::BenchmarkProcessorControl::Begin(*this, PlacementError)) { Finish(PlacementError); return; }
        ProphecyJolt::CharacterProfiling::BeginFrame();
    }
    const double Now=FPlatformTime::Seconds();
    Measuring = Frame >= Warmup;
    if (Measuring && PreviousStart > 0) FrameMs.Add((Now-PreviousStart)*1000);
    PreviousStart=Now; TickStart=Now;
    for (int32 I=0; I<Meshes.Num(); ++I)
    {
        USkeletalMeshComponent* M=Meshes[I];
        if (ProphecySterileBench::IsManualFixtureMode(Cases[CaseIndex].Mode))
        {
            // The real manager owns all source publication, including the entire warmup.
            if (Cases[CaseIndex].Mode == ProphecySterileBench::NNJoltMode) continue;
            // Stationary warmup, then 30 Hz publication before the real agent's
            // automatic PrePhysics publisher. No added per-frame wake/impulse.
            if (Frame == 0 || (Frame >= Warmup && (Frame - Warmup) % 2 == 0))
            {
                ProphecyJolt::CharacterProfiling::FScope PoseTiming(ProphecyJolt::CharacterProfiling::EPhase::FixturePosePublish);
                PublishManualPose(I);
            }
            if (Cases[CaseIndex].Mode == ProphecySterileBench::ManualReplayMode && Frame >= Warmup)
            {
                FString Error;
                if (!PublishManualReplayFrame(Error)) { Finish(Error); return; }
            }
            continue;
        }
        if(Cases[CaseIndex].Mode>=10)
            ProphecySterileBench::PublishAgentPose(MeshAsset,I,double(Frame)/60.+I*.031,GetWorld()->GetTimeSeconds());
        else CastChecked<UProphecyPhysicsBenchAnim>(M->GetAnimInstance())->PoseTime=double(Frame)/60.+I*.031;
        if (Cases[CaseIndex].Mode != 1)
        {
            M->WakeAllRigidBodies(); // Equal awake workload; sleeping is never a performance shortcut.
            if (Frame == Warmup+30)
                if (auto* Head=M->GetBodyInstance(TEXT("head"))) Head->AddImpulse(FVector(30,0,0),true);
        }
    }
}

void UProphecyPhysicsBenchmarkSubsystem::EndTick(UWorld* W,ELevelTick,float)
{
    if (W != GetWorld() || Done) return;
    const double Ms=(FPlatformTime::Seconds()-TickStart)*1000;
    CSV_CUSTOM_STAT_GLOBAL(ProphecyBenchmarkMeasured, Measuring ? 1 : 0, ECsvCustomStatOp::Set);
    CSV_CUSTOM_STAT_GLOBAL(ProphecyBenchmarkFrame, Frame, ECsvCustomStatOp::Set);
    CSV_CUSTOM_STAT_GLOBAL(ProphecyBenchmarkWorldMs, float(Ms), ECsvCustomStatOp::Set);
    if (Measuring) WorldMs.Add(Ms);
    if (Measuring && Cases[CaseIndex].Mode == ProphecySterileBench::NNJoltMode)
    {
        FString Error;
        if (!ValidateNNJoltFrame(Error)) { Finish(Error); return; }
    }
    else if (Measuring && Cases[CaseIndex].Mode == ProphecySterileBench::MultiJoltMode)
    {
        FString Error;
        if (!ValidateMultiJoltFrame(Error)) { Finish(Error); return; }
    }
    else if (Measuring && Cases[CaseIndex].Mode == ProphecySterileBench::LiveJoltMode)
    {
        FString Error;
        if (!ValidateLiveJoltFrame(Error)) { Finish(Error); return; }
    }
    else if (Measuring && Cases[CaseIndex].Mode == ProphecySterileBench::ManualCrowdMode)
    {
        FString Error;
        if (!ValidateManualCrowdFrame(Error)) { Finish(Error); return; }
    }
    ++Frame;
    if (Frame >= Warmup+Samples) { SaveCase(); Advance=true; }
}

TSharedPtr<FJsonObject> UProphecyPhysicsBenchmarkSubsystem::Audit() const
{
    auto O=MakeShared<FJsonObject>();
    O->SetObjectField(TEXT("query_tree_settings"), ProphecySterileBench::QueryTreeSettings());
    O->SetObjectField(TEXT("engine_ispc_settings"), ProphecySterileBench::EngineISPCSettings());
    O->SetArrayField(TEXT("movement_camera_detachments"), MovementCameraDetachments);
    int32 DetachedCameraSubtrees = 0;
    for (const AActor* Actor : Actors)
    {
        const auto* Agent = Cast<AProphecyAgent>(Actor);
        if (!IsValid(Agent)) continue;
        const USpringArmComponent* SpringArm = Agent->GetAgentSpringArm();
        const UCameraComponent* Camera = Agent->GetAgentCamera();
        if (SpringArm && Camera && SpringArm->IsRegistered() && Camera->IsRegistered()
            && !SpringArm->GetAttachParent() && Camera->GetAttachParent() == SpringArm
            && !SpringArm->IsComponentTickEnabled() && !Camera->IsComponentTickEnabled())
            ++DetachedCameraSubtrees;
    }
    O->SetNumberField(TEXT("movement_camera_subtrees_detached"), DetachedCameraSubtrees);
    O->SetNumberField(TEXT("movement_camera_components_retained_in_detached_subtrees"), DetachedCameraSubtrees * 2);
    TMap<FString, int32> SpatialBuckets;
    if ((FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchRigAudit")) ||
        (Cases.IsValidIndex(CaseIndex) && ProphecySterileBench::IsManualFixtureMode(Cases[CaseIndex].Mode))) && !Meshes.IsEmpty())
        O->SetObjectField(TEXT("effective_rig"), ProphecySterileBench::RigAudit::Capture(Meshes[0]));
    int32 Bodies=0,Dynamic=0,Awake=0,Joints=0,Motors=0,Targets=0,NonFinite=0,Blueprints=0;
    double Pos2=0,Ang2=0,MaxPos=0,RootZ=0; int32 Roots=0;
    for (TActorIterator<AActor> It(GetWorld()); It; ++It) Blueprints+=It->GetClass()->HasAnyClassFlags(CLASS_CompiledFromBlueprint);
    for (USkeletalMeshComponent* M:Meshes)
    {
        Joints+=M->Constraints.Num();
        // Independent expected pose. EndPhysics can overwrite the mesh's local
        // buffer with the blended ragdoll; comparing against that hides collapse.
        const auto& Ref=MeshAsset->GetRefSkeleton();
        TArray<FTransform> Local=Ref.GetRefBonePose();
        const int32 MeshIndex=Meshes.IndexOfByKey(M);
        const double Time=Cases[CaseIndex].Mode>=10 ? double(FMath::Max(0,Frame-1))/60.+MeshIndex*.031 : CastChecked<UProphecyPhysicsBenchAnim>(M->GetAnimInstance())->PoseTime;
        for (int32 I=0; I<Local.Num(); ++I) ProphecySterileBench::AnimateBone(Local[I],Ref.GetBoneName(I),Time);
        TArray<FTransform> CS; CS.SetNum(Local.Num());
        for(int32 I=0; I<Local.Num(); ++I) { int32 P=Ref.GetParentIndex(I); CS[I]=P==INDEX_NONE?Local[I]:Local[I]*CS[P]; }
        for(auto* B:M->Bodies) if(B && B->IsValidBodyInstance())
        {
            ++Bodies; Dynamic+=B->IsInstanceSimulatingPhysics(); Awake+=B->IsInstanceAwake();
            if (const auto Actor = B->GetPhysicsActor(); Actor && !Actor->GetMarkedDeleted())
            {
                const auto Index = Actor->GetGameThreadAPI().SpatialIdx();
                ++SpatialBuckets.FindOrAdd(FString::Printf(TEXT("bucket_%u_inner_%u"), uint32(Index.Bucket), uint32(Index.InnerIdx)));
            }
            const FTransform Actual=B->GetUnrealWorldTransform();
            if(Actual.ContainsNaN()) { ++NonFinite; continue; }
            if(CS.IsValidIndex(B->InstanceBoneIndex))
            {
                const FTransform Target=CS[B->InstanceBoneIndex]*(Cases[CaseIndex].Mode>=10?ProphecySterileBench::AgentTarget(MeshIndex):M->GetComponentTransform());
                const double E=FVector::Distance(Target.GetLocation(),Actual.GetLocation());
                const double Angle=FMath::RadiansToDegrees(Target.GetRotation().GetNormalized().AngularDistance(Actual.GetRotation().GetNormalized()));
                Pos2+=E*E; Ang2+=Angle*Angle; MaxPos=FMath::Max(MaxPos,E);
            }
            if(B->BodySetup.IsValid() && B->BodySetup->BoneName==TEXT("pelvis")) { RootZ+=Actual.GetLocation().Z; ++Roots; }
        }
    }
    for(UProphecyHalfSimDriveComponent* D:Drivers) { Targets+=D->GetNativeTargetCount(); Motors+=D->GetJointMotorCount(); }
    auto BucketCounts = MakeShared<FJsonObject>();
    for (const auto& Bucket : SpatialBuckets) BucketCounts->SetNumberField(Bucket.Key, Bucket.Value);
    O->SetObjectField(TEXT("skeletal_actor_spatial_buckets"), BucketCounts);
    O->SetStringField(TEXT("spatial_bucket_scope"), TEXT("Actual native skeletal actor indices read on the game thread; inner 0=Default, 1=Dynamic, 2=DefaultQueryOnly, 3=DynamicQueryOnly. These are placement counts, not actual tree-node padding or reinsert counts."));
    O->SetNumberField(TEXT("skeletal_meshes"),Meshes.Num()); O->SetNumberField(TEXT("bodies"),Bodies);
    O->SetNumberField(TEXT("dynamic_bodies"),Dynamic); O->SetNumberField(TEXT("awake_bodies"),Awake);
    O->SetNumberField(TEXT("anatomical_constraints"),Joints); O->SetNumberField(TEXT("joint_motors"),Motors);
    O->SetNumberField(TEXT("native_target_constraints_configured"),Targets);
    O->SetNumberField(TEXT("blueprint_actors"),Blueprints); O->SetNumberField(TEXT("nonfinite_transforms"),NonFinite);
    O->SetNumberField(TEXT("position_rms_cm"),Bodies?FMath::Sqrt(Pos2/Bodies):0);
    O->SetNumberField(TEXT("angle_rms_degrees"),Bodies?FMath::Sqrt(Ang2/Bodies):0);
    O->SetNumberField(TEXT("max_position_error_cm"),MaxPos); O->SetNumberField(TEXT("mean_pelvis_z_cm"),Roots?RootZ/Roots:0);
    return O;
}

void UProphecyPhysicsBenchmarkSubsystem::SaveCase()
{
    FString QueryPaddingError;
    if (!ProphecySterileBench::ValidateRequestedQueryPadding(QueryPaddingError)) { Finish(QueryPaddingError); return; }
    const FCase C=Cases[CaseIndex]; auto O=MakeShared<FJsonObject>();
    O->SetStringField(TEXT("mode"),ProphecySterileBench::BenchmarkModeNames[C.Mode]);
    O->SetStringField(TEXT("fixture"),C.Floor?TEXT("floor_gravity"):TEXT("air_no_gravity"));
    O->SetNumberField(TEXT("repeat"),C.Repeat); O->SetNumberField(TEXT("samples"),WorldMs.Num());
    O->SetObjectField(TEXT("world_tick"),ProphecySterileBench::Stats(WorldMs));
    O->SetObjectField(TEXT("frame_interval"),ProphecySterileBench::Stats(FrameMs));
    O->SetArrayField(TEXT("world_ms"),ProphecySterileBench::Values(WorldMs));
    O->SetArrayField(TEXT("frame_ms"),ProphecySterileBench::Values(FrameMs));
    const TSharedPtr<FJsonObject> After = Audit();
    O->SetObjectField(TEXT("before"),Before); O->SetObjectField(TEXT("after"),After);
    if (!MovementCameraDetachments.IsEmpty()
        && After->GetIntegerField(TEXT("movement_camera_subtrees_detached")) != MovementCameraDetachments.Num())
    { Finish(TEXT("A movement-only camera subtree was reattached, removed or re-enabled during the fixture.")); return; }
    if (C.Mode == ProphecySterileBench::NNJoltMode)
    {
        FString Error;
        if (!SaveNNJoltCase(O, Error))
        {
            O->SetStringField(TEXT("actual_nn_error"), Error);
            Results.Add(MakeShared<FJsonValueObject>(O));
            Finish(Error);
            return;
        }
    }
    else if (C.Mode == ProphecySterileBench::MultiJoltMode)
    {
        FString Error;
        if (!SaveMultiJoltCase(O, Error))
        {
            O->SetStringField(TEXT("multi_jolt_error"), Error);
            Results.Add(MakeShared<FJsonValueObject>(O));
            Finish(Error);
            return;
        }
    }
    else if (C.Mode == ProphecySterileBench::LiveJoltMode)
    {
        FString Error;
        if (!SaveLiveJoltCase(O, Error))
        {
            O->SetStringField(TEXT("error"), Error);
            Results.Add(MakeShared<FJsonValueObject>(O));
            Finish(Error);
            return;
        }
    }
    else if (C.Mode == ProphecySterileBench::ManualCrowdMode)
    {
        FString Error;
        if (!SaveManualCrowdCase(O, Error))
        {
            O->SetStringField(TEXT("manual_crowd_error"), Error);
            Results.Add(MakeShared<FJsonValueObject>(O));
            Finish(Error);
            return;
        }
    }
    else if (ProphecySterileBench::IsRecordingMode(C.Mode))
    {
        FString Error;
        if (!SaveManualCapture(O, Error))
        {
            O->SetStringField(TEXT("error"), Error);
            Results.Add(MakeShared<FJsonValueObject>(O));
            Finish(Error);
            return;
        }
        O->SetStringField(TEXT("timing_scope"), TEXT("Diagnostic capture includes opt-in recording; not a replay performance comparison"));
        // The generic audit's instantaneous synthetic endpoint is not the
        // manual publisher's interpolated BodyFromBone endpoint.
        O->SetStringField(TEXT("pose_error_scope"), TEXT("Generic reference-pose error is diagnostic only; exact manual body endpoints and pre/post velocities are in the sealed capture"));
        if (C.Mode == ProphecySterileBench::ManualMode) Cases.Insert({ ProphecySterileBench::ManualReplayMode, C.Floor, C.Repeat }, CaseIndex + 1);
    }
    Results.Add(MakeShared<FJsonValueObject>(O));
    UE_LOG(LogTemp,Display,TEXT("STERILE_PHYSICS result mode=%s mean=%.3fms"),ProphecySterileBench::BenchmarkModeNames[C.Mode],O->GetObjectField(TEXT("world_tick"))->GetNumberField(TEXT("mean_ms")));
}

void UProphecyPhysicsBenchmarkSubsystem::Finish(const FString& Error)
{
    ProphecyJolt::CharacterProfiling::Disable();
    if(Done) return; Done=true;
    FString FinalError = Error;
    FString ChaosPauseRestoreError;
    if (!ProphecyJolt::BenchmarkChaosPause::Restore(*this, ChaosPauseRestoreError))
        FinalError += (FinalError.IsEmpty() ? TEXT("") : TEXT("; ")) + ChaosPauseRestoreError;
    FString PlacementRestoreError;
    if (!ProphecyJolt::BenchmarkProcessorControl::Restore(*this, PlacementRestoreError))
        FinalError += (FinalError.IsEmpty() ? TEXT("") : TEXT("; ")) + PlacementRestoreError;
    FString NativeQueryPaddingRestoreError;
    if (!ProphecyJolt::BenchmarkQueryPadding::Restore(*this, NativeQueryPaddingRestoreError))
        FinalError += (FinalError.IsEmpty() ? TEXT("") : TEXT("; ")) + NativeQueryPaddingRestoreError;
    auto O=MakeShared<FJsonObject>(); O->SetStringField(TEXT("error"),FinalError);
    O->SetObjectField(TEXT("native_query_padding_control"), ProphecyJolt::BenchmarkQueryPadding::ToJson());
    if (!FinalError.IsEmpty() && Before.IsValid()) O->SetObjectField(TEXT("failure_boundary_audit"), Before);
    if (!FinalError.IsEmpty() && !WorldMs.IsEmpty())
    {
        namespace Profile = ProphecyJolt::CharacterProfiling;
        auto Partial = MakeShared<FJsonObject>();
        Partial->SetBoolField(TEXT("success"), false);
        Partial->SetStringField(TEXT("scope"), TEXT("Incomplete failed-case diagnostics only, not performance acceptance. World samples may include the failed frame; character means use only previously completed character-validation rows. Actual NN validation is a separate counter below."));
        if (Cases.IsValidIndex(CaseIndex)) Partial->SetStringField(TEXT("mode"), ProphecySterileBench::BenchmarkModeNames[Cases[CaseIndex].Mode]);
        Partial->SetNumberField(TEXT("timed_world_samples"), WorldMs.Num());
        Partial->SetObjectField(TEXT("world_tick"), ProphecySterileBench::Stats(WorldMs));
        Partial->SetArrayField(TEXT("world_ms"), ProphecySterileBench::Values(WorldMs));
        double PhaseSums[Profile::PhaseCount] = {};
        int32 CharacterRows = 0, NNRows = 0;
        TSharedPtr<FJsonObject> LastNN;
        for (const auto& Value : LiveJoltFrames)
        {
            const auto Row = Value.IsValid() ? Value->AsObject() : nullptr;
            if (!Row || !Row->HasTypedField<EJson::Object>(TEXT("character_cpu_ms"))) continue;
            const auto Phases = Row->GetObjectField(TEXT("character_cpu_ms"));
            for (int32 Phase = 0; Phase < Profile::PhaseCount; ++Phase)
                PhaseSums[Phase] += Phases->GetNumberField(Profile::PhaseNames[Phase]);
            ++CharacterRows;
            if (Row->HasTypedField<EJson::Object>(TEXT("actual_nn")))
            { ++NNRows; LastNN = Row->GetObjectField(TEXT("actual_nn")); }
        }
        Partial->SetNumberField(TEXT("completed_character_validation_rows"), CharacterRows);
        Partial->SetNumberField(TEXT("completed_actual_nn_validation_rows"), NNRows);
        if (CharacterRows)
        {
            auto Means = MakeShared<FJsonObject>();
            for (int32 Phase = 0; Phase < Profile::PhaseCount; ++Phase)
                Means->SetNumberField(Profile::PhaseNames[Phase], PhaseSums[Phase] / CharacterRows);
            Partial->SetObjectField(TEXT("character_cpu_mean_ms"), Means);
        }
        if (LastNN) Partial->SetObjectField(TEXT("last_validated_actual_nn_counters"), LastNN);
        O->SetObjectField(TEXT("failed_case_partial_measurements"), Partial);
    }
    O->SetNumberField(TEXT("benchmark_version"),3);
    O->SetObjectField(TEXT("game_module_build_profile"), ProphecyGameModuleSimd::Report());
    O->SetObjectField(TEXT("query_tree_settings_at_finish"), ProphecySterileBench::QueryTreeSettings());
    O->SetObjectField(TEXT("engine_ispc_settings_at_finish"), ProphecySterileBench::EngineISPCSettings());
    O->SetObjectField(TEXT("processor_environment"), ProphecyJolt::CharacterProfiling::ProcessorEnvironmentJson());
    O->SetObjectField(TEXT("game_thread_processor_control"), ProphecyJolt::BenchmarkProcessorControl::ToJson());
    O->SetObjectField(TEXT("paused_chaos_diagnostic"), ProphecyJolt::BenchmarkChaosPause::ToJson());
    O->SetNumberField(TEXT("count"),Count); O->SetNumberField(TEXT("fixed_dt"),1./60.);
    O->SetStringField(TEXT("measurement"),TEXT("Uncapped standalone world actor/physics tick; check nullrhi field for renderer. Diagnostic validation and blood readbacks occur outside timed tick. Not rendered FPS or solver-only CPU sum."));
    O->SetStringField(TEXT("collision"),TEXT("WorldStatic floor contacts only; PhysicsBody channel ignored (no self/crowd contacts)"));
    const bool bActualNN = Cases.ContainsByPredicate([](const FCase& Case) { return Case.Mode == ProphecySterileBench::NNJoltMode; });
    O->SetStringField(TEXT("pose"), bActualNN
        ? TEXT("Actual 30 Hz CPU lower/upper locomotion manager with public walking intent, capsule movement and recurrent physical feedback; 60 Hz Jolt control and full 88-bone presentation. No synthetic publication after manager adoption.")
        : TEXT("Deterministic native ref-pose generator with 1.5cm pelvis bob and 0.12rad head/arm oscillation; no NN/Blueprint"));
    O->SetNumberField(TEXT("warmup_frames"),Warmup); O->SetNumberField(TEXT("sample_frames"),Samples);
    O->SetBoolField(TEXT("nullrhi"),FParse::Param(FCommandLine::Get(),TEXT("nullrhi")));
    O->SetBoolField(TEXT("movement_only"),FParse::Param(FCommandLine::Get(),TEXT("PhysicsBenchMovementOnly")));
    O->SetStringField(TEXT("movement_only_scope"),TEXT("When enabled, native manual fixture agents disable the optional fist overlay and unused camera/spring-arm ticks, and detach their unused camera subtree while retaining both components. All skeletal bones, body/joint simulation, pose cadence and query receivers remain present."));
    O->SetBoolField(TEXT("substepping"),UPhysicsSettings::Get()->bSubstepping);
    O->SetBoolField(TEXT("async_physics"),UPhysicsSettings::Get()->bTickPhysicsAsync);
    O->SetStringField(TEXT("mesh"),MeshAsset?MeshAsset->GetPathName():TEXT(""));
    O->SetArrayField(TEXT("passes"),Results);
    FString Json; auto Writer=TJsonWriterFactory<>::Create(&Json); FJsonSerializer::Serialize(O,Writer);
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Output),true); FFileHelper::SaveStringToFile(Json,*Output);
    ClearCase();
    UE_LOG(LogTemp,Display,TEXT("STERILE_PHYSICS finished error=%s file=%s"),*FinalError,*Output);
    FPlatformMisc::RequestExit(!FinalError.IsEmpty());
}

void UProphecyPhysicsBenchmarkSubsystem::Deinitialize()
{
    FString NativeQueryPaddingRestoreError;
    if (!ProphecyJolt::BenchmarkQueryPadding::Restore(*this, NativeQueryPaddingRestoreError))
        UE_LOG(LogTemp, Error, TEXT("Benchmark native query padding restoration failed: %s"), *NativeQueryPaddingRestoreError);
    FString ChaosPauseRestoreError;
    if (!ProphecyJolt::BenchmarkChaosPause::Restore(*this, ChaosPauseRestoreError))
        UE_LOG(LogTemp, Error, TEXT("Benchmark Chaos pause teardown restoration failed: %s"), *ChaosPauseRestoreError);
    FString PlacementRestoreError;
    if (!ProphecyJolt::BenchmarkProcessorControl::Restore(*this, PlacementRestoreError))
        UE_LOG(LogTemp, Error, TEXT("Benchmark GT affinity teardown restoration failed: %s"), *PlacementRestoreError);
    FWorldDelegates::OnWorldPreActorTick.Remove(StartHandle); FWorldDelegates::OnWorldPostActorTick.Remove(EndHandle);
    ClearCase(); Super::Deinitialize();
}
