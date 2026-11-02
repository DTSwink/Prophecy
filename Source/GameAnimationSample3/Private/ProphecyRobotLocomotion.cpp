#include "ProphecyRobotLocomotion.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltCharacterWorldSubsystem.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyAttackCamera.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "PhysicsEngine/BodyInstance.h"
#include "NNE.h"
#include "NNEModelData.h"
#include "NNERuntimeCPU.h"
#include "NNERuntimeRunSync.h"
#include "UObject/StrongObjectPtr.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace ProphecyRobot
{
struct FModel
{
    TStrongObjectPtr<UNNEModelData> Data;
    TSharedPtr<UE::NNE::IModelInstanceCPU> Instance;
    bool Load(bool Clanker,FString& Error)
    {
        if(Instance)return true;
        TArray<uint8> Bytes;
        const FString Path=FPaths::ProjectContentDir()/TEXT("locomotion/NN/robots")/(Clanker?TEXT("clanker_214358.onnx"):TEXT("getup_161960.onnx"));
        if(!FFileHelper::LoadFileToArray(Bytes,*Path)){Error=TEXT("Cannot read robot ONNX: ")+Path;return false;}
        Data.Reset(NewObject<UNNEModelData>());Data->Init(TEXT("onnx"),Bytes);
        auto Runtime=UE::NNE::GetRuntime<INNERuntimeCPU>(TEXT("NNERuntimeORTCpu"));
        auto Model=Runtime.IsValid()?Runtime->CreateModelCPU(Data.Get()):nullptr;
        if(Model)Instance=Model->CreateModelInstanceCPU();
        const uint32 Dims[]={1,154};const auto Shape=UE::NNE::FTensorShape::Make(MakeArrayView(Dims));
        if(!Instance || Instance->SetInputTensorShapes(MakeArrayView(&Shape,1))!=UE::NNE::EResultStatus::Ok)
        {Instance.Reset();Data.Reset();Error=TEXT("Robot CPU inference runtime could not initialize [1,154].");return false;}
        const auto Outputs=Instance->GetOutputTensorDescs();
        if(Outputs.Num()!=2 || Outputs[0].GetDataType()!=ENNETensorDataType::Float || Outputs[1].GetDataType()!=ENNETensorDataType::Float)
        {Instance.Reset();Data.Reset();Error=TEXT("Robot policy outputs must be 34 velocities and two phase values.");return false;}
        // ORT resolves these exported dynamic output dimensions only on the first run.
        // Prewarm once before admitting a robot, without changing any agent's phase.
        float Input[154]={},Action[34];FVector2f Phase;
        if(!Run(MakeArrayView(Input),MakeArrayView(Action),Phase,Error)){Instance.Reset();Data.Reset();return false;}
        const auto Shapes=Instance->GetOutputTensorShapes();
        if(Shapes.Num()!=2 || Shapes[0].Volume()!=34 || Shapes[1].Volume()!=2)
        {Instance.Reset();Data.Reset();Error=TEXT("Robot policy resolved an unexpected output shape.");return false;}
        return true;
    }
    bool Run(TArrayView<float> Observation,TArrayView<float> Action,FVector2f& Phase,FString& Error)
    {
        UE::NNE::FTensorBindingCPU Input{Observation.GetData(),154*sizeof(float)};
        float Next[2];UE::NNE::FTensorBindingCPU Output[]={{Action.GetData(),34*sizeof(float)},{Next,2*sizeof(float)}};
        if(Instance->RunSync(MakeArrayView(&Input,1),MakeArrayView(Output))!=UE::NNE::EResultStatus::Ok)
        {Error=TEXT("Robot inference failed; no motor packet was applied.");return false;}
        for(float V:Action)if(!FMath::IsFinite(V)){Error=TEXT("Robot policy returned a nonfinite action.");return false;}
        if(!FMath::IsFinite(Next[0])||!FMath::IsFinite(Next[1])){Error=TEXT("Robot policy returned a nonfinite phase.");return false;}
        Phase=FVector2f(Next[0],Next[1]);return true;
    }
};
static FModel Models[2];
bool EvaluatePolicy(bool Clanker,TArrayView<float> Input,TArrayView<float> Action,FVector2f& Phase,FString& Error)
{
    if(Input.Num()!=154||Action.Num()!=34){Error=TEXT("Invalid robot tensor dimensions.");return false;}
    auto& M=Models[Clanker?1:0];return M.Load(Clanker,Error)&&M.Run(Input,Action,Phase,Error);
}
struct FState
{
    EProphecyLocomotionType Type=EProphecyLocomotionType::NN;
    EProphecyAgentSimulationMode PreviousMode=EProphecyAgentSimulationMode::Kinematic;
    bool PreviousInference=true;
    TArray<FBodyState> Entry,Bodies;
    TArray<FTransform> EntryLocal;
    TArray<FProphecyJoltRobotMotor> Motors;
    FVector2f Phase=FVector2f(1,0);
    uint64 Frame=MAX_uint64;
    int32 Ticks=0;
    bool Configured=false,PolicyDirty=true;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,TUniquePtr<FState>> States;
static TMap<TWeakObjectPtr<const AProphecyAgent>,TArray<FBodyState>> ExitMotion;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FReturnSettings> Settings;
static TMap<TWeakObjectPtr<AProphecyAgent>,FDelegateHandle> Admissions;
static FDelegateHandle Cleanup;
static void CancelAdmission(AProphecyAgent* A)
{if(auto* H=Admissions.Find(A)){FWorldDelegates::OnWorldPreActorTick.Remove(*H);Admissions.Remove(A);}}
static void EnsureCleanup()
{
    if(Cleanup.IsValid())return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for(auto It=Admissions.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==World)
        {FWorldDelegates::OnWorldPreActorTick.Remove(It.Value());It.RemoveCurrent();}
        for(auto It=States.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==World)It.RemoveCurrent();
        for(auto It=ExitMotion.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==World)It.RemoveCurrent();
        for(auto It=Settings.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==World)It.RemoveCurrent();
    });
}
bool IsActive(const AProphecyAgent* A){return States.Contains(A);}
bool HasRobot(const UWorld* W){for(const auto& It:States)if(It.Key.IsValid()&&It.Key->GetWorld()==W)return true;return false;}
bool ExitToSimulationMode(AProphecyAgent* A,EProphecyAgentSimulationMode Mode,FString& Error)
{
    if(auto* S=States.Find(A))(*S)->PreviousMode=Mode;
    return UProphecyLocomotionTypeLibrary::SetLocomotionType(A,EProphecyLocomotionType::NN,Error);
}
void Forget(AProphecyAgent* A){States.Remove(A);ExitMotion.Remove(A);Settings.Remove(A);CancelAdmission(A);ForgetReturn(A);}
void EntryHelpers(AProphecyAgent* A,TArray<FTransform>& Local)
{if(const auto* S=States.Find(A);S&&(*S)->EntryLocal.Num()==Local.Num())Local=(*S)->EntryLocal;}
FReturnSettings ReturnSettings(const AProphecyAgent* A){if(const auto* S=Settings.Find(A))return *S;return {};}
bool OverrideSnapshot(AProphecyAgent* A,USkeletalMeshComponent& Mesh,FProphecyJoltRigSnapshot& Snapshot,FString& Error)
{
    if(const auto* Motion=ExitMotion.Find(A))
    {
        const auto* P=Profile(Error);if(!P||!Mesh.GetSkeletalMeshAsset())return false;
        const auto& Skeleton=Mesh.GetSkeletalMeshAsset()->GetRefSkeleton();
        for(auto& Body:Snapshot.Bodies)
        {
            int32 Group=INDEX_NONE;
            for(int32 Bone=Skeleton.FindBoneIndex(Body.BodyName);Bone!=INDEX_NONE&&Group==INDEX_NONE;Bone=Skeleton.GetParentIndex(Bone))
                Group=P->Bodies.IndexOfByPredicate([&](const auto& Spec){return Spec.Aliases.Contains(Skeleton.GetBoneName(Bone));});
            if(Group==INDEX_NONE){Error=TEXT("NN return body has no captured robot parent.");return false;}
            const auto& Old=(*Motion)[Group];
            const FVector Center=Old.World.TransformPosition(P->Bodies[Group].MassFrame.GetLocation());
            const FVector NewCenter=Body.BodyOriginToWorld.TransformPosition(Body.MassFrameToBodyOrigin.GetLocation());
            Body.CenterOfMassVelocityCmPerSecond=Old.COMVelocity+FVector::CrossProduct(Old.AngularVelocity,NewCenter-Center);
            Body.AngularVelocityRadiansPerSecond=Old.AngularVelocity;
        }
        ExitMotion.Remove(A);return true;
    }
    const auto* S=States.Find(A);if(!S)return true;
    const auto* P=Profile(Error);return P&&MakeSnapshot(*P,Mesh,(*S)->Entry,Snapshot,Error);
}
bool Configure(AProphecyAgent* A,UProphecyJoltWorldSubsystem& W,const FProphecyJoltRigHandle& Rig,FString& Error)
{
    auto* It=States.Find(A);if(!It)return true;auto& S=**It;const auto* P=Profile(Error);if(!P)return false;
    TArray<FProphecyJoltRobotDrag> Drag;for(const auto& B:P->Bodies)Drag.Add(B.Drag);
    S.Motors.Reset();for(const auto& J:P->Joints)S.Motors.Add(J.Motor[S.Type==EProphecyLocomotionType::Clanker?1:0]);
    const auto Result=W.ConfigureRobotRig(Rig,S.Motors,Drag);if(!Result.IsSuccess()){Error=Result.Message;return false;}
    S.Configured=true;return true;
}
bool Prepare(AProphecyAgent* A,UProphecyJoltWorldSubsystem& W,const FProphecyJoltRigHandle& Rig,FString& Error)
{
    auto* It=States.Find(A);if(!It)return true;auto& S=**It;
    if(S.Frame==GFrameCounter)return true;
    const auto* P=Profile(Error);if(!P||!S.Configured){Error=TEXT("Robot motors were not configured.");return false;}
    const bool Clanker=S.Type==EProphecyLocomotionType::Clanker;
    const bool PolicyDue=S.PolicyDirty||(S.Ticks%2)==0;
    if(PolicyDue)
    {
        S.Bodies.SetNum(15);auto* C=A->GetJoltCharacterComponent();
        for(int32 I=0;I<15;++I)
        {
            bool Sim=false;auto& B=S.Bodies[I];
            if(!C || !C->GetBodyState(P->Bodies[I].Bone,B.World,B.COMVelocity,B.AngularVelocity,Sim))
            {Error=TEXT("Robot observation lost a physical body.");return false;}
        }
        FVector Velocity,Direction;float Speed=0;bool Run=false;
        A->GetLocomotionTarget(Velocity,Speed,Direction,Run);
        if(A->bUseBlueprintLocomotionInput)
        {
            const auto Command=A->GetLocomotionInput();Velocity=Command.WorldMoveInput*Command.SpeedScale;
            Speed=Velocity.SizeSquared2D()>1.e-6?100:0;Run=Command.bRun;
        }
        float Input[154],Action[34];
        Observation(*P,S.Bodies,Clanker,Speed<1?-1.f:Run?1.f:0.f,Velocity,A->GetHeldSword()!=nullptr,S.Phase,MakeArrayView(Input));
        if(!Models[Clanker?1:0].Run(MakeArrayView(Input),MakeArrayView(Action),S.Phase,Error))return false;
        for(int32 I=0;I<14;++I)
        {
            const auto& J=P->Joints[I];S.Motors[I]=J.Motor[Clanker?1:0];
            S.Motors[I].Velocity=J.Motor[0].bBall?FVector(Action[J.Action],Action[J.Action+1],Action[J.Action+2]):FVector(0,0,Action[J.Action]);
        }
    }
    const float T=FMath::Clamp(float(S.Ticks+1)/24.f,0.f,1.f),Alpha=T*T*(3-2*T);
    if(PolicyDue||S.Ticks<24)
    {
        const auto Result=W.PublishRobotMotors(Rig,S.Motors,Alpha);
        if(!Result.IsSuccess()){Error=Result.Message;return false;}
    }
    S.PolicyDirty=false;
    S.Frame=GFrameCounter;++S.Ticks;return true;
}
static AProphecyNNLocomotionManager* Manager(AProphecyAgent* A)
{
    for(TActorIterator<AProphecyNNLocomotionManager> It(A->GetWorld());It;++It)if(It->ResolveAgent(A->GetAgentHandle())==A)return *It;
    return nullptr;
}
static bool Capture(AProphecyAgent* A,FState& S,const FProfile& P,FString& Error)
{
    auto* Mesh=A->GetPoseReferenceMesh();if(!Mesh||!Mesh->GetSkeletalMeshAsset()){Error=TEXT("The agent has no Physical Mesh.");return false;}
    Mesh->HandleExistingParallelEvaluationTask(true,true);
    const auto& Space=Mesh->GetComponentSpaceTransforms();const auto& Skeleton=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
    if(Space.Num()!=Skeleton.GetNum()){Error=TEXT("Physical Mesh pose is incomplete.");return false;}
    S.EntryLocal.SetNum(Space.Num());
    for(int32 I=0;I<Space.Num();++I)
    {const int32 Parent=Skeleton.GetParentIndex(I);S.EntryLocal[I]=Parent<0?Space[I]:Space[I].GetRelativeTransform(Space[Parent]);}
    TArray<FName> Names;TArray<FTransform> Future,Presented;float Alpha=1;FProphecyNNPoseSnapshot History;
    A->ReadNNFutureWorldPoseWithSnapshot(Names,Future,Presented,Alpha,History);
    S.Entry.SetNum(15);
    const bool Physical=A->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic;
    auto* C=A->GetJoltCharacterComponent();auto* W=A->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    for(int32 I=0;I<15;++I)
    {
        const auto& Spec=P.Bodies[I];auto& B=S.Entry[I];FTransform Bone=Mesh->GetSocketTransform(Spec.Bone);
        FVector V,WAng;bool Sim=false;
        if(Physical&&A->GetPhysicalBodyState(Spec.Bone,Bone,V,WAng,Sim)&&Sim)
        {
            FVector OldCOM=Bone.GetLocation();FProphecyJoltBodyHandle H;FProphecyJoltBodyState Native;
            if(C&&C->GetBodyHandle(Spec.Bone,H)&&W&&W->ReadBody(H,Native).IsSuccess())OldCOM=Native.CenterOfMassPositionCm;
            else if(auto* BI=Mesh->GetBodyInstance(Spec.Bone))OldCOM=BI->GetCOMPosition();
            B.World=Spec.BodyFromBone*Bone;B.AngularVelocity=WAng;
            const FVector NewCOM=B.World.TransformPosition(Spec.MassFrame.GetLocation());
            B.COMVelocity=V+FVector::CrossProduct(WAng,NewCOM-OldCOM);
        }
        else
        {
            B.World=Spec.BodyFromBone*Bone;
            const int32 Index=History.BoneNames.IndexOfByKey(Spec.Bone);const double Dt=History.InterpolationIntervalSeconds;
            if(Index!=INDEX_NONE&&History.PreviousComponentTransforms.IsValidIndex(Index)&&History.ComponentTransforms.IsValidIndex(Index)&&Dt>SMALL_NUMBER)
            {
                const FTransform Last=Spec.BodyFromBone*History.PreviousComponentTransforms[Index]*History.PreviousComponentWorldTransform;
                const FTransform Next=Spec.BodyFromBone*History.ComponentTransforms[Index]*History.ComponentWorldTransform;
                FQuat D=(Next.GetRotation()*Last.GetRotation().Inverse()).GetNormalized();if(D.W<0)D=-D;
                B.AngularVelocity=D.ToRotationVector()/Dt;
                B.COMVelocity=(Next.GetLocation()-Last.GetLocation())/Dt+FVector::CrossProduct(B.AngularVelocity,B.World.GetRotation().RotateVector(Spec.MassFrame.GetLocation()));
            }
        }
        B.World.SetScale3D(FVector::OneVector);
    }
    return true;
}
static bool SwitchNow(AProphecyAgent* A,EProphecyLocomotionType Type,FString& Error)
{
    const auto Old=UProphecyLocomotionTypeLibrary::GetLocomotionType(A);if(Old==Type)return true;
    auto* M=Manager(A);if(!M){Error=TEXT("The agent must be registered with its NN manager before switching locomotion.");return false;}
    const auto* P=Profile(Error);if(!P)return false;
    auto* World=A->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();FProphecyJoltWorldDiagnostics D;
    if(!World||!World->GetDiagnostics(D).IsSuccess()||!D.bInitialized||D.bFaulted)
    {Error=TEXT("Initialize a healthy Jolt world and its scene collision before switching to a robot.");return false;}
    if(Type!=EProphecyLocomotionType::NN&&!Models[Type==EProphecyLocomotionType::Clanker?1:0].Load(Type==EProphecyLocomotionType::Clanker,Error))return false;
    if(Old!=EProphecyLocomotionType::NN&&Type!=EProphecyLocomotionType::NN)
    {
        auto& S=**States.Find(A);S.Type=Type;S.Frame=MAX_uint64;S.PolicyDirty=true;
        A->OnLocomotionTypeChanged(Old,Type);return true;
    }
    if(Type==EProphecyLocomotionType::NN)
    {
        auto& S=**States.Find(A);const auto PreviousMode=S.PreviousMode;const bool Inference=S.PreviousInference;
        FVector COM=FVector::ZeroVector,Velocity=FVector::ZeroVector;double Mass=0;
        TArray<FBodyState> Bodies;
        for(int32 I=0;I<15;++I)
        {
            FTransform Body;FVector V,W;bool Sim;
            if(!A->GetJoltCharacterComponent()->GetBodyState(P->Bodies[I].Bone,Body,V,W,Sim)){Error=TEXT("Cannot capture robot exit state.");return false;}
            const double Kg=P->Bodies[I].Mass;Mass+=Kg;COM+=Kg*Body.TransformPosition(P->Bodies[I].MassFrame.GetLocation());Velocity+=Kg*V;
            Bodies.Add({Body,V,W});
        }
        COM/=Mass;Velocity/=Mass;double YawMomentum=0,YawInertia=0;
        for(int32 I=0;I<15;++I)
        {
            const auto& B=Bodies[I];const auto& Spec=P->Bodies[I];
            const FQuat Q=B.World.GetRotation()*Spec.MassFrame.GetRotation();
            const FVector Axis=Q.UnrotateVector(FVector::UpVector),Offset=B.World.TransformPosition(Spec.MassFrame.GetLocation())-COM;
            YawMomentum+=Q.RotateVector(Spec.Inertia*Q.UnrotateVector(B.AngularVelocity)).Z+
                Spec.Mass*FVector::CrossProduct(Offset,B.COMVelocity-Velocity).Z;
            YawInertia+=FVector::DotProduct(Axis,Spec.Inertia*Axis)+Spec.Mass*Offset.SizeSquared2D();
        }
        const FVector CameraPivot=ProphecyAttackCamera::CaptureLocomotionSwitch(M,A);
        // Seed before disabling: the ordinary mesh restoration evaluates the NN immediately.
        if(!M->SeedLocomotionFromPhysical(A->GetAgentHandle(),COM,Velocity,YawInertia>SMALL_NUMBER?YawMomentum/YawInertia:0,Error))return false;
        States.Remove(A);A->bNNInferenceEnabled=Inference;
        if(!A->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)){Error=TEXT("Cannot restore NN mesh ownership.");return false;}
        if(PreviousMode==EProphecyAgentSimulationMode::Physical)ExitMotion.Add(A,MoveTemp(Bodies));
        if(PreviousMode!=EProphecyAgentSimulationMode::Kinematic&&!A->SetSimulationMode(PreviousMode))
        {ExitMotion.Remove(A);Error=TEXT("NN pose restored, but the previous simulation mode could not be restored.");return false;}
        ProphecyAttackCamera::LocomotionSwitched(M,A,CameraPivot);
        A->OnLocomotionTypeChanged(Old,Type);return true;
    }
    auto S=MakeUnique<FState>();S->PreviousMode=A->GetSimulationMode();S->PreviousInference=A->bNNInferenceEnabled;S->Type=Type;
    ExitMotion.Remove(A);
    if(!Capture(A,*S,*P,Error))return false;
    const auto Previous=S->PreviousMode;
    const FVector CameraPivot=ProphecyAttackCamera::CaptureLocomotionSwitch(M,A);
    ForgetReturn(A);
    // Keep the captured entry immutable through the normal mode restoration.
    if(Previous!=EProphecyAgentSimulationMode::Kinematic&&!A->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic))
    {Error=TEXT("Cannot release the current simulation owner.");return false;}
    States.Add(A,MoveTemp(S));A->bNNInferenceEnabled=false;
    if(!A->IsJoltPhysicalAnimationSelected()&&!A->EnableJoltPhysicalAnimation())
    {const bool Inference=(*States.Find(A))->PreviousInference;States.Remove(A);A->bNNInferenceEnabled=Inference;
        A->SetSimulationMode(Previous);Error=TEXT("Cannot select Jolt for robot locomotion.");return false;}
    if(!A->SetSimulationMode(EProphecyAgentSimulationMode::Physical)||!A->IsJoltPhysicalAnimationEnabled())
    {
        const bool WasInference=(*States.Find(A))->PreviousInference;States.Remove(A);A->bNNInferenceEnabled=WasInference;
        Error=TEXT("Robot admission failed: ")+(A->GetJoltCharacterComponent()?A->GetJoltCharacterComponent()->GetLastError():TEXT("No character component"));
        A->SetSimulationMode(Previous);return false;
    }
    ProphecyAttackCamera::LocomotionSwitched(M,A,CameraPivot);
    A->OnLocomotionTypeChanged(Old,Type);return true;
}
}
EProphecyLocomotionType UProphecyLocomotionTypeLibrary::GetLocomotionType(AProphecyAgent* Agent)
{const auto* S=ProphecyRobot::States.Find(Agent);return S?(*S)->Type:EProphecyLocomotionType::NN;}
bool UProphecyLocomotionTypeLibrary::SetLocomotionSwitchBlend(AProphecyAgent* A,float LowerDuration,float UpperDuration,
    float UpperInertia,float UpperEasing,float NNAlphaHold,float NNTakeoverCoefficient)
{
    if(!IsValid(A)||!IsInGameThread())return false;
    for(float V:{LowerDuration,UpperDuration,UpperInertia,UpperEasing,NNAlphaHold,NNTakeoverCoefficient})if(!FMath::IsFinite(V)||V<0)return false;
    ProphecyRobot::EnsureCleanup();ProphecyRobot::Settings.Add(A,{LowerDuration,UpperDuration,FMath::Min(UpperInertia,1.f),FMath::Min(UpperEasing,1.f),FMath::Min(NNAlphaHold,1.f),FMath::Max(.01f,NNTakeoverCoefficient)});return true;
}
bool UProphecyLocomotionTypeLibrary::SetLocomotionType(AProphecyAgent* A,EProphecyLocomotionType Type,FString& Error)
{
    Error.Reset();if(!IsInGameThread()||!IsValid(A)||A->IsActorBeingDestroyed()||Type>EProphecyLocomotionType::Clanker)
    {Error=TEXT("Select a live agent and locomotion type.");return false;}
    if(!A->GetWorld()||!A->GetWorld()->IsGameWorld()||A->GetWorld()->bIsTearingDown)
    {Error=TEXT("Locomotion can switch only in a live game world.");return false;}
    ProphecyRobot::EnsureCleanup();ProphecyRobot::CancelAdmission(A);
    if(GetLocomotionType(A)==Type)return true;
    if(!A->GetWorld()->bInTick)return ProphecyRobot::SwitchNow(A,Type,Error);
    // Mode changes replace a registered rig, so defer them to the next admission window.
    // No second character component or permanently running tick is necessary.
    const TWeakObjectPtr<AProphecyAgent> Weak=A;
    const auto Handle=FWorldDelegates::OnWorldPreActorTick.AddLambda([Weak,Type](UWorld* W,ELevelTick,float)
    {
        if(!Weak.IsValid()||Weak->GetWorld()!=W)return;
        ProphecyRobot::CancelAdmission(Weak.Get());FString E;
        if(!ProphecyRobot::SwitchNow(Weak.Get(),Type,E))UE_LOG(LogTemp,Error,TEXT("Locomotion switch: %s"),*E);
    });
    ProphecyRobot::Admissions.Add(A,Handle);return true;
}
bool UProphecyLocomotionTypeLibrary::SetLocomotionSwitchUpperBlend(AProphecyAgent* A,float Duration,float Inertia,
    float Easing,float NNAlphaHold,float NNTakeoverCoefficient)
{
    if(!IsValid(A)||!IsInGameThread())return false;
    for(float V:{Duration,Inertia,Easing,NNAlphaHold,NNTakeoverCoefficient})if(!FMath::IsFinite(V)||V<0)return false;
    ProphecyRobot::EnsureCleanup();auto& S=ProphecyRobot::Settings.FindOrAdd(A);
    S.Upper=Duration;S.Inertia=FMath::Min(Inertia,1.f);S.Easing=FMath::Min(Easing,1.f);
    S.Hold=FMath::Min(NNAlphaHold,1.f);S.Coefficient=FMath::Max(.01f,NNTakeoverCoefficient);return true;
}
bool UProphecyLocomotionTypeLibrary::SetLocomotionSwitchLowerBlend(AProphecyAgent* A,float Duration,float HoldDuration)
{
    if(!IsValid(A)||!IsInGameThread()||!FMath::IsFinite(Duration)||Duration<0||!FMath::IsFinite(HoldDuration)||HoldDuration<0)return false;
    ProphecyRobot::EnsureCleanup();auto& S=ProphecyRobot::Settings.FindOrAdd(A);S.Lower=Duration;S.LowerHold=HoldDuration;return true;
}
