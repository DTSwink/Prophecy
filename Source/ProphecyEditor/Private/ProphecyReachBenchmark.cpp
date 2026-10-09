#include "ProphecyReachBenchmark.h"
#include "ProphecyDoubleReachTypes.h"
#include "ProphecyDoubleReachAnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimSequence.h"
#include "AnimNode_ControlRigBase.h"
#include "AnimPose.h"
#include "ControlRig.h"
#include "ControlRigBlueprintFactory.h"
#include "ControlRigBlueprintLegacy.h"
#include "Rigs/RigHierarchyController.h"
#include "RigVMModel/RigVMController.h"
#include "Units/Execution/RigUnit_BeginExecution.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Async/ParallelFor.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "HAL/PlatformMisc.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/StrongObjectPtr.h"
#include "Containers/StaticArray.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetCompilingManager.h"

#include "Benchmarks/DoubleReachKernel.inl"

namespace ReachPerf
{
using namespace ProphecyReachBenchmarkKernel;
// Shared, non-inlined call: both methods execute the very same machine code.
FORCENOINLINE void Solve(const FJointTransforms& Input,const FVector& Left,const FVector& Right,FJointTransforms& Output)
{
    FSourcePose Source;Source.ComponentTransforms=Input;
    for(int32 I=0;I<JointCount;++I)Source.Positions[I]=Input[I].GetTranslation()*.01;
    Source.Arms[0]=MakeArmSpec(Source,true);Source.Arms[1]=MakeArmSpec(Source,false);
    Source.Legs[0]=MakeLegSpec(Source,true);Source.Legs[1]=MakeLegSpec(Source,false);
    const FVector Targets[]={Left*.01,Right*.01};
    BuildEndpointTransforms(Source,SolveMode(Source,Targets,EProphecyDoubleReachMode::Both),EProphecyDoubleReachMode::Both,Output);
}
const FName TargetNames[]={TEXT("benchmark_target_l"),TEXT("benchmark_target_r")};

struct FFrame
{
    FJointTransforms Core;
    TArray<FTransform> Local;
    FVector Left,Right;
};
struct FProxy : FAnimInstanceProxy
{
    using FAnimInstanceProxy::FAnimInstanceProxy;
    using FAnimInstanceProxy::Initialize;
    using FAnimInstanceProxy::Uninitialize;
};
struct FRigNode : FAnimNode_ControlRigBase
{
    UControlRig* Rig=nullptr;
    virtual UControlRig* GetControlRig() const override{return Rig;}
    virtual TSubclassOf<UControlRig> GetControlRigClass() const override{return Rig?Rig->GetClass():nullptr;}
    void Setup(FAnimInstanceProxy& Proxy,UAnimInstance* Instance,UControlRig* InRig)
    {
        Rig=InRig;bTransferPoseInGlobalSpace=false;bTransferInputCurves=false;bResetInputPoseToInitial=false;
        OnInitializeAnimInstance(&Proxy,Instance);
        Initialize_AnyThread(FAnimationInitializeContext(&Proxy));
        CacheBones_AnyThread(FAnimationCacheBonesContext(&Proxy));
    }
    void Run(FPoseContext& Pose){ExecuteControlRig(Pose);}
    bool Adapter()const{return ControlRigHierarchyMappings.IsPoseAdapterEnabled();}
};
struct FLane
{
    TStrongObjectPtr<UControlRig> Rig;
    TUniquePtr<FRigNode> Node;
    int32 Targets[2];
    FJointTransforms Output;
};
TSharedRef<FJsonObject> Stats(const TArray<double>& Values)
{
    TArray<double> Sorted=Values;Sorted.Sort();
    auto O=MakeShared<FJsonObject>();double Sum=0;for(double V:Values)Sum+=V;
    O->SetNumberField(TEXT("mean_ms"),Sum/FMath::Max(1,Values.Num()));
    O->SetNumberField(TEXT("median_ms"),Sorted[Sorted.Num()/2]);
    O->SetNumberField(TEXT("p95_ms"),Sorted[FMath::Min(Sorted.Num()-1,int32(Sorted.Num()*.95))]);
    TArray<TSharedPtr<FJsonValue>> Samples;for(double V:Values)Samples.Add(MakeShared<FJsonValueNumber>(V));
    O->SetArrayField(TEXT("samples_ms"),Samples);return O;
}
FVector Ball(double T,bool Left)
{
    // Exact reflection in the existing ball harness bounds, without physics cost.
    const FVector Start=Left?FVector(-55,-48,28):FVector(48,44,-24);
    const FVector Velocity=(Left?FVector(.72,.46,.52):FVector(-.58,.70,-.41)).GetSafeNormal()*165;
    const FVector Half(133,108,93);FVector P;
    for(int32 I=0;I<3;++I){double X=FMath::Fmod(Start[I]+Velocity[I]*T+Half[I],4*Half[I]);if(X<0)X+=4*Half[I];P[I]=X<2*Half[I]?X-Half[I]:3*Half[I]-X;}
    // Character mesh yaw=-90 and at ground height in the authored ball harness.
    return FVector(-P.Y,P.X,125+P.Z);
}
void Run(const TArray<FString>& Args)
{
    if(Args.Num()!=6){UE_LOG(LogTemp,Error,TEXT("Usage: Prophecy.ReachBenchmark count frames repeat workload parallel output.json"));return;}
    const int32 Count=FMath::Clamp(FCString::Atoi(*Args[0]),1,256),Frames=FMath::Clamp(FCString::Atoi(*Args[1]),1,1800);
    const int32 Repeat=FMath::Clamp(FCString::Atoi(*Args[2]),1,9);const FString Workload=Args[3];const bool Parallel=Args[4]==TEXT("1");
    const FString Path=FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(),Args[5]);
    UE_LOG(LogTemp,Display,TEXT("ReachBenchmark preparing count=%d frames=%d repeats=%d workload=%s parallel=%d"),Count,Frames,Repeat,*Workload,Parallel);
    FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get().WaitForCompletion();
    auto* Mesh=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    auto* Idle=LoadObject<UAnimSequence>(nullptr,TEXT("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop.M_Neutral_Stand_Idle_Loop"));
    if(!Mesh || !Idle){UE_LOG(LogTemp,Error,TEXT("ReachBenchmark missing source assets"));return;}
    const auto& Ref=Mesh->GetRefSkeleton();const int32 Bones=Ref.GetNum();
    int32 CoreToMesh[JointCount];for(int32 I=0;I<JointCount;++I){CoreToMesh[I]=Ref.FindBoneIndex(JointNames[I]);if(CoreToMesh[I]<0){UE_LOG(LogTemp,Error,TEXT("ReachBenchmark missing bone"));return;}}
    TStrongObjectPtr<USkeletalMeshComponent> Component(NewObject<USkeletalMeshComponent>());Component->SetSkeletalMeshAsset(Mesh);
    TStrongObjectPtr<UAnimInstance> Instance(NewObject<UAnimInstance>(Component.Get()));
    FProxy Proxy(Instance.Get());Proxy.Initialize(Instance.Get());
    TArray<FBoneIndexType> Required;for(int32 I=0;I<Bones;++I)Required.Add(FBoneIndexType(I));
    Proxy.GetRequiredBones().InitializeTo(Required,UE::Anim::FCurveFilterSettings(),*Mesh);
    // Precompute inputs once, outside every measured region. Same changing source
    // animation and target trajectory for each paired method, offset per agent.
    TArray<FFrame> Inputs;Inputs.SetNum(Frames+Count+60);
    FAnimPoseEvaluationOptions Options;Options.OptionalSkeletalMesh=Mesh;Options.EvaluationType=EAnimDataEvalType::Compressed;Options.bEvaluateCurves=false;
    for(int32 F=0;F<Inputs.Num();++F)
    {
        FAnimPose Pose;UAnimPoseExtensions::GetAnimPoseAtTime(Idle,FMath::Fmod(F/60.,Idle->GetPlayLength()),Options,Pose);
        auto& Input=Inputs[F];Input.Local.SetNum(Bones);
        for(int32 I=0;I<Bones;++I)Input.Local[I]=UAnimPoseExtensions::GetBonePose(Pose,Ref.GetBoneName(I),EAnimPoseSpaces::Local);
        // Canonicalize through the actual compact pose once. Comparing the
        // editor AnimPose world cache with runtime FK adds unrelated rounding.
        {FMemMark Mark(FMemStack::Get());FPoseContext RuntimePose(&Proxy);RuntimePose.ResetToRefPose();
        for(int32 I=0;I<Bones;++I)RuntimePose.Pose[FCompactPoseBoneIndex(I)]=Input.Local[I];
        FCSPose<FCompactPose> CS;CS.InitPose(RuntimePose.Pose);
        for(int32 I=0;I<JointCount;++I)Input.Core[I]=CS.GetComponentSpaceTransform(FCompactPoseBoneIndex(CoreToMesh[I]));}
        if(Workload==TEXT("easy"))
        {
            Input.Left=Input.Core[JointIndex(EJoint::UpperArmL)].GetTranslation()+FVector(20,25+5*FMath::Sin(F*.04),-15);
            Input.Right=Input.Core[JointIndex(EJoint::UpperArmR)].GetTranslation()+FVector(-20,25+5*FMath::Cos(F*.04),-15);
        }
        else if(Workload==TEXT("hard")){Input.Left=FVector(140,180+20*FMath::Sin(F*.04),190);Input.Right=FVector(-140,180+20*FMath::Cos(F*.04),40);}
        else{Input.Left=Ball(F/60.,true);Input.Right=Ball(F/60.,false);}
    }
    // Transient genuine Control Rig Blueprint / RigVM, native solve unit, full
    // Manny hierarchy. No authored rig, map or AnimBP is changed or saved.
    TStrongObjectPtr<UControlRigBlueprintFactory> Factory(NewObject<UControlRigBlueprintFactory>());
    TStrongObjectPtr<UControlRigBlueprint> BP(Cast<UControlRigBlueprint>(Factory->FactoryCreateNew(UControlRigBlueprint::StaticClass(),GetTransientPackage(),MakeUniqueObjectName(GetTransientPackage(),UControlRigBlueprint::StaticClass(),TEXT("ReachBenchmarkRig")),RF_Transient,nullptr,GWarn)));
    if(!BP.IsValid()){UE_LOG(LogTemp,Error,TEXT("ReachBenchmark rig creation failed"));return;}
    auto* HC=BP->GetHierarchyController();
    TArray<FTransform> RefGlobal;RefGlobal.SetNum(Bones);
    for(int32 I=0;I<Bones;++I)
    {
        const int32 P=Ref.GetParentIndex(I);RefGlobal[I]=P>=0?Ref.GetRefBonePose()[I]*RefGlobal[P]:Ref.GetRefBonePose()[I];
        HC->AddBone(Ref.GetBoneName(I),P>=0?FRigElementKey(Ref.GetBoneName(P),ERigElementType::Bone):FRigElementKey(),RefGlobal[I],true,ERigBoneType::Imported,false,false);
    }
    for(FName Name:TargetNames)HC->AddBone(Name,FRigElementKey(),FTransform::Identity,true,ERigBoneType::User,false,false);
    auto* Controller=BP->GetController();
    auto* Begin=Controller->AddUnitNode(FRigUnit_BeginExecution::StaticStruct(),TEXT("Execute"),FVector2D::ZeroVector,TEXT("Begin"),false);
    auto* Unit=Controller->AddUnitNode(FRigUnit_ProphecyDoubleReachBenchmark::StaticStruct(),TEXT("Execute"),FVector2D(200,0),TEXT("DoubleReach"),false);
    if(!Begin || !Unit || !Controller->AddLink(Begin->GetName()+TEXT(".ExecuteContext"),Unit->GetName()+TEXT(".ExecuteContext"),false)){UE_LOG(LogTemp,Error,TEXT("ReachBenchmark graph construction failed"));return;}
    BP->RecompileVM();
    TArray<TUniquePtr<FLane>> Lanes;
    for(int32 A=0;A<Count;++A)
    {
        auto Lane=MakeUnique<FLane>();Lane->Rig.Reset(BP->CreateControlRig());Lane->Rig->Initialize();
        Lane->Rig->SetDeltaTime(1.f/60.f);Lane->Node=MakeUnique<FRigNode>();Lane->Node->Setup(Proxy,Instance.Get(),Lane->Rig.Get());
        for(int32 K=0;K<2;++K)Lane->Targets[K]=Lane->Rig->GetHierarchy()->GetIndex(FRigElementKey(TargetNames[K],ERigElementType::Bone));
        Lanes.Add(MoveTemp(Lane));
    }
    auto One=[&](int32 Method,int32 Frame,int32 A)
    {
        FMemMark Mark(FMemStack::Get());auto& Lane=*Lanes[A];const auto& Input=Inputs[Frame+A];
        if(Method==0){Solve(Input.Core,Input.Left,Input.Right,Lane.Output);return;}
        FPoseContext Pose(&Proxy);Pose.ResetToRefPose();
        for(int32 I=0;I<Bones;++I)Pose.Pose[FCompactPoseBoneIndex(I)]=Input.Local[I];
        if(Method==1)
        {
            auto* H=Lane.Rig->GetHierarchy();H->SetGlobalTransform(Lane.Targets[0],FTransform(Input.Left));H->SetGlobalTransform(Lane.Targets[1],FTransform(Input.Right));
            Lane.Node->Run(Pose);
        }
        else
        {
            // Same pose bridge used by the accepted native animation proxy.
            FCSPose<FCompactPose> ComponentPose;ComponentPose.InitPose(Pose.Pose);
            FJointTransforms In,Out;for(int32 I=0;I<JointCount;++I)In[I]=ComponentPose.GetComponentSpaceTransform(FCompactPoseBoneIndex(CoreToMesh[I]));
            Solve(In,Input.Left,Input.Right,Out);
            TArray<FBoneTransform,TInlineAllocator<JointCount>> Changes;
            for(int32 I=1;I<JointCount;++I)Changes.Emplace(FCompactPoseBoneIndex(CoreToMesh[I]),Out[I]);
            Changes.Sort([](const FBoneTransform& A,const FBoneTransform& B){return A.BoneIndex<B.BoneIndex;});
            ComponentPose.LocalBlendCSBoneTransforms(Changes,1.f);
            FCSPose<FCompactPose>::ConvertComponentPosesToLocalPosesSafe(ComponentPose,Pose.Pose);Pose.Pose.NormalizeRotations();
        }
        FCSPose<FCompactPose> CS;CS.InitPose(Pose.Pose);
        for(int32 I=0;I<JointCount;++I)Lane.Output[I]=CS.GetComponentSpaceTransform(FCompactPoseBoneIndex(CoreToMesh[I]));
    };
    double PositionError=0,AngleError=0,Motion=0;int32 CheckedPoses=0;FString WorstAngle;
    double MethodPosition[3]={},MethodAngle[3]={};
    auto Compare=[&](const FJointTransforms& Expected,int32 Method,int32 F,int32 A)
    {
        ++CheckedPoses;for(int32 I=0;I<JointCount;++I)
        {
            if(Expected[I].ContainsNaN() || Lanes[A]->Output[I].ContainsNaN()){PositionError=1.e10;return;}
            const double P=FVector::Dist(Expected[I].GetTranslation(),Lanes[A]->Output[I].GetTranslation());
            const double Q=FMath::RadiansToDegrees(Expected[I].GetRotation().GetNormalized().AngularDistance(Lanes[A]->Output[I].GetRotation().GetNormalized()));
            if(Q>AngleError)WorstAngle=FString::Printf(TEXT("method=%d input=%d bone=%s"),Method,F+A,*JointNames[I].ToString());
            PositionError=FMath::Max(PositionError,P);AngleError=FMath::Max(AngleError,Q);
            MethodPosition[Method]=FMath::Max(MethodPosition[Method],P);MethodAngle[Method]=FMath::Max(MethodAngle[Method],Q);
            Motion=FMath::Max(Motion,FVector::Dist(Expected[I].GetTranslation(),Inputs[F+A].Core[I].GetTranslation()));
        }
    };
    // Every distinct input used by any timed agent, not a few sampled frames.
    for(int32 InputIndex=0;InputIndex<Frames+Count-1;++InputIndex)
    {
        const int32 A=InputIndex%Count,F=InputIndex-A;
        One(0,F,A);const auto Expected=Lanes[A]->Output;
        for(int32 Method=1;Method<3;++Method){One(Method,F,A);Compare(Expected,Method,F,A);}
    }
    UE_LOG(LogTemp,Display,TEXT("ReachBenchmark equivalence max_cm=%.9f max_deg=%.9f motion_cm=%.5f adapter=%d worst=%s"),PositionError,AngleError,Motion,Lanes[0]->Node->Adapter(),*WorstAngle);
    if(PositionError>.001 || AngleError>.01 || Motion<1){UE_LOG(LogTemp,Error,TEXT("ReachBenchmark equivalence FAILED; no timings reported"));return;}
    auto Batch=[&](int32 Method,int32 F){if(Parallel)ParallelFor(Count,[&](int32 A){One(Method,F,A);});else for(int32 A=0;A<Count;++A)One(Method,F,A);};
    for(int32 F:{0,Frames/2,Frames-1})
    {
        Batch(0,F);TArray<FJointTransforms> Expected;for(const auto& Lane:Lanes)Expected.Add(Lane->Output);
        for(int32 Method=1;Method<3;++Method){Batch(Method,F);for(int32 A=0;A<Count;++A)Compare(Expected[A],Method,F,A);}
    }
    if(PositionError>.001 || AngleError>.01){UE_LOG(LogTemp,Error,TEXT("ReachBenchmark crowd/parallel equivalence FAILED cm=%.9f deg=%.9f worst=%s"),PositionError,AngleError,*WorstAngle);return;}
    FlushAsyncLoading();FAssetCompilingManager::Get().FinishAllCompilation();
    for(int32 F=0;F<30;++F)for(int32 Method=0;Method<3;++Method)Batch(Method,F);
    TArray<double> Samples[3];TArray<TSharedPtr<FJsonValue>> Rounds;double Checksum=0;
    for(int32 R=0;R<Repeat;++R)
    {
        TArray<double> Round[3];
        // Rotate ABC/BCA/CAB order each frame to counter cache and thermal drift.
        for(int32 F=0;F<Frames;++F)for(int32 K=0;K<3;++K)
        {
            const int32 Method=(K+F+R)%3;const double Start=FPlatformTime::Seconds();Batch(Method,F);
            const double Ms=(FPlatformTime::Seconds()-Start)*1000;Samples[Method].Add(Ms);Round[Method].Add(Ms);
            for(const auto& Lane:Lanes)Checksum+=Lane->Output[JointIndex(EJoint::HandR)].GetTranslation().X;
        }
        auto O=MakeShared<FJsonObject>();O->SetObjectField(TEXT("direct"),Stats(Round[0]));O->SetObjectField(TEXT("control_rig_anim_node"),Stats(Round[1]));O->SetObjectField(TEXT("native_animation_bridge"),Stats(Round[2]));Rounds.Add(MakeShared<FJsonValueObject>(O));
    }
    auto Root=MakeShared<FJsonObject>();Root->SetNumberField(TEXT("agents"),Count);Root->SetNumberField(TEXT("frames_per_repeat"),Frames);Root->SetNumberField(TEXT("repeats"),Repeat);
    Root->SetStringField(TEXT("workload"),Workload);Root->SetBoolField(TEXT("parallel"),Parallel);Root->SetNumberField(TEXT("mesh_bones"),Bones);Root->SetBoolField(TEXT("pose_adapter"),Lanes[0]->Node->Adapter());
    Root->SetNumberField(TEXT("max_position_error_cm"),PositionError);Root->SetNumberField(TEXT("max_angle_error_deg"),AngleError);Root->SetNumberField(TEXT("max_reach_motion_cm"),Motion);Root->SetNumberField(TEXT("checksum"),Checksum);
    Root->SetNumberField(TEXT("checked_pose_pairs"),CheckedPoses);Root->SetStringField(TEXT("worst_angle"),WorstAngle);
    auto Errors=MakeShared<FJsonObject>();for(int32 M=1;M<3;++M){auto E=MakeShared<FJsonObject>();E->SetNumberField(TEXT("cm"),MethodPosition[M]);E->SetNumberField(TEXT("degrees"),MethodAngle[M]);Errors->SetObjectField(M==1?TEXT("control_rig"):TEXT("native_bridge"),E);}Root->SetObjectField(TEXT("pose_errors"),Errors);
    Root->SetObjectField(TEXT("direct"),Stats(Samples[0]));Root->SetObjectField(TEXT("control_rig_anim_node"),Stats(Samples[1]));Root->SetObjectField(TEXT("native_animation_bridge"),Stats(Samples[2]));Root->SetArrayField(TEXT("rounds"),Rounds);
    Root->SetStringField(TEXT("cpu"),FPlatformMisc::GetCPUBrand());Root->SetNumberField(TEXT("logical_cores"),FPlatformMisc::NumberOfCoresIncludingHyperthreads());
    FString Json;FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Json));IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path),true);FFileHelper::SaveStringToFile(Json,*Path);
    UE_LOG(LogTemp,Display,TEXT("ReachBenchmark DONE %s"),*Path);
    Lanes.Reset();Proxy.Uninitialize(Instance.Get());
}
static FAutoConsoleCommand Command(TEXT("Prophecy.ReachBenchmark"),TEXT("Isolated paired double-reach CPU benchmark."),FConsoleCommandWithArgsDelegate::CreateStatic(&Run));
}

FRigUnit_ProphecyDoubleReachBenchmark_Execute()
{
    using namespace ProphecyReachBenchmarkKernel;
    if(!Solve)return;
    auto* H=ExecuteContext.Hierarchy;if(!H)return;
    if(CachedIndices.Num()!=JointCount+2)
    {
        CachedIndices.Reset();
        for(FName Name:JointNames)CachedIndices.Add(H->GetIndex(FRigElementKey(Name,ERigElementType::Bone)));
        for(FName Name:ReachPerf::TargetNames)CachedIndices.Add(H->GetIndex(FRigElementKey(Name,ERigElementType::Bone)));
    }
    FJointTransforms Input,Output;
    for(int32 I=0;I<JointCount;++I){if(CachedIndices[I]<0)return;Input[I]=H->GetGlobalTransform(CachedIndices[I]);}
    ReachPerf::Solve(Input,H->GetGlobalTransform(CachedIndices[JointCount]).GetTranslation(),H->GetGlobalTransform(CachedIndices[JointCount+1]).GetTranslation(),Output);
    for(int32 I=1;I<JointCount;++I)H->SetGlobalTransform(CachedIndices[I],Output[I]);
}
