#include "ProphecyBodyflipLibrary.h"
#include "ProphecyBodyflipRuntime.h"
#include "ProphecyBodyflipDrive.h"
#include "ProphecyBodyflipPlanner.h"
#include "ProphecyBodyflipProjectiles.h"
#include "ProphecyBodyflipNN.h"
#include "ProphecyBodyflipRigProfile.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyFootIKOwner.h"
#include "ProphecyFootIKGame.h"
#include "ProphecyFootIKSurfaceOwner.h"
#include "ProphecyNNDefenseLibrary.h"
#include "ProphecyDefenseArmedGate.h"
#include "ProphecyArmedPose.h"
#include "ProphecySwordHolster.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyThrowMath.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyThrowRuntime.h"
#include "ProphecyReachRuntime.h"
#include "ProphecyGetUp.h"
#include "ProphecySwordHolsterPose.h"
#include "Components/SkeletalMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "Engine/SkeletalMesh.h"
#include "EngineUtils.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

namespace ProphecyBodyflip
{
static FString Json(const TSharedPtr<FJsonObject>& O){FString S;FJsonSerializer::Serialize(O.ToSharedRef(),TJsonWriterFactory<>::Create(&S));return S;}
static TSharedPtr<FJsonObject> Parse(const FString& S){TSharedPtr<FJsonObject> O;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S),O);return O;}
static TArray<TSharedPtr<FJsonValue>> Array(const FVector& V){return {MakeShared<FJsonValueNumber>(V.X),MakeShared<FJsonValueNumber>(V.Y),MakeShared<FJsonValueNumber>(V.Z)};}
static FVector Vector(const TArray<TSharedPtr<FJsonValue>>& V){return V.Num()==3?FVector(V[0]->AsNumber(),V[1]->AsNumber(),V[2]->AsNumber()):FVector::ZeroVector;}
static FQuat Quaternion(const TArray<TSharedPtr<FJsonValue>>& V){return V.Num()==4?FQuat(V[0]->AsNumber(),V[1]->AsNumber(),V[2]->AsNumber(),V[3]->AsNumber()):FQuat::Identity;}
static FVector WorldDirectionToLab(const FTransform& Space,const FVector& Direction)
{return ProphecyThrow::FromUnrealPoint(Space.InverseTransformVectorNoScale(Direction.GetSafeNormal())).GetSafeNormal();}

struct FPhysicsResolution
{
    TArray<int32> PoseIndices,Parents;
    TArray<FQuat> StartLocal,EndLocal;
    uint64 MotionFrame=MAX_uint64;
    float CachedSeconds=-1;
    int32 CachedCount=1;
    bool Build(const FString& Profile,TConstArrayView<FName> Names,const FReferenceSkeleton& Skeleton,FString& Error)
    {
        const auto Rig=Parse(Profile);if(!Rig){Error=TEXT("Missing Bodyflip physics-resolution rig");return false;}
        TArray<int32> Bones;
        for(const auto& Body:Rig->GetArrayField(TEXT("bodies")))
        {
            const FName Name(*Body->AsObject()->GetStringField(TEXT("name")));const int32 Bone=Skeleton.FindBoneIndex(Name);
            if(Bone==INDEX_NONE||Names.IndexOfByKey(Name)==INDEX_NONE){Error=TEXT("Bodyflip physical body is missing from its pose: ")+Name.ToString();return false;}
            Bones.Add(Bone);
        }
        Bones.Sort();PoseIndices.Reset();Parents.Reset();
        for(int32 Bone:Bones)
        {
            PoseIndices.Add(Names.IndexOfByKey(Skeleton.GetBoneName(Bone)));int32 Parent=INDEX_NONE;
            if(Skeleton.GetBoneName(Bone)!=TEXT("pelvis"))for(int32 P=Skeleton.GetParentIndex(Bone);P!=INDEX_NONE;P=Skeleton.GetParentIndex(P))
            {Parent=Bones.IndexOfByKey(P);if(Parent!=INDEX_NONE)break;}
            Parents.Add(Parent);
        }
        return true;
    }
    void ClearMotion(){MotionFrame=MAX_uint64;CachedSeconds=-1;}
    void Record(TConstArrayView<FTransform> Before,TConstArrayView<FTransform> After,uint64 Frame=GFrameCounter)
    {
        StartLocal.SetNum(PoseIndices.Num());EndLocal.SetNum(PoseIndices.Num());
        for(int32 I=0;I<PoseIndices.Num();++I)
        {
            const int32 B=PoseIndices[I],P=Parents[I]==INDEX_NONE?INDEX_NONE:PoseIndices[Parents[I]];
            StartLocal[I]=P==INDEX_NONE?Before[B].GetRotation():(Before[P].GetRotation().Inverse()*Before[B].GetRotation()).GetNormalized();
            EndLocal[I]=P==INDEX_NONE?After[B].GetRotation():(After[P].GetRotation().Inverse()*After[B].GetRotation()).GetNormalized();
        }
        MotionFrame=Frame;CachedSeconds=-1;
    }
    int32 Count(float Seconds,uint64 Frame=GFrameCounter)
    {
        if(!FMath::IsFinite(Seconds)||Seconds<=0)return 1;
        // Lab playback advances at240Hz. Each such interval may split32 times;
        // that is a per-interval cap, not a32-step cap on a60Hz native frame.
        const double Scaled=double(Seconds)*240.,Whole=FMath::FloorToDouble(Scaled);
        // Seconds arrives as float: nominal1/60 can lie just above the exact
        // four-step boundary. Accept that boundary only within the float's lower
        // half-ULP rounding interval; the next representable input still adds a step.
        const double HalfUlp=.5*(double(Seconds)-double(FMath::AsFloat(FMath::AsUInt(Seconds)-1u)));
        const double Rounded=Scaled-Whole<=HalfUlp*240.?Whole:FMath::CeilToDouble(Scaled);
        const int32 Base=int32(FMath::Clamp(Rounded,1.,double(MAX_int32/32)));
        if(MotionFrame!=Frame||StartLocal.IsEmpty())return Base;
        if(CachedSeconds==Seconds)return CachedCount;
        TArray<FQuat,TInlineAllocator<32>> Previous,Current;Previous.SetNum(StartLocal.Num());Current.SetNum(StartLocal.Num());
        int32 Extra=1;
        for(int32 Step=0;Step<=Base;++Step)
        {
            for(int32 I=0;I<StartLocal.Num();++I)
            {
                const FQuat Local=FQuat::Slerp(StartLocal[I],EndLocal[I],double(Step)/Base).GetNormalized();
                Current[I]=Parents[I]==INDEX_NONE?Local:(Current[Parents[I]]*Local).GetNormalized();
                if(Step)Extra=FMath::Max(Extra,FMath::Clamp(FMath::CeilToInt(Previous[I].AngularDistance(Current[I])/.06),1,32));
            }
            Swap(Previous,Current);
        }
        // Shared Jolt steps are uniform. The maximum of the lab's interval
        // demands keeps every interval at least as fine, including curved local paths.
        CachedSeconds=Seconds;CachedCount=Base*Extra;return CachedCount;
    }
};
struct FActive
{
    FProphecyBodyflipPlanner Planner;
    FProphecyBodyflipProjectiles Projectiles;
    FTransform Space=FTransform::Identity;
    TWeakObjectPtr<AProphecyAgent> Agent;
    FVector InitialLowPoint=FVector::ZeroVector;
    TOptional<FVector> WorldTarget;
    TArray<FTransform> WorldPlatforms;
    TArray<FVector> WorldPlatformSizes;
    bool Aligned=false,HasWorldPlatforms=false,AttackFree=false;
    TSharedPtr<FJsonObject> Settings,Run;
    FString RigProfile;
    TArray<FName> Names;
    TArray<FTransform> Previous,Current,Next;
    FPhysicsResolution PhysicsResolution;
    FProphecyBodyflipState Status;
    FProphecyBodyflipState BeforeSeek;
    double Time=0,Applied=-1,End=600,SeekTime=-1;
    double BeforeSeekApplied=-1;
    bool Playing=true,RebuildPending=false,ExtendPending=false,SeekRejected=false,Rebuilding=false;
    float Yaw=0,InitialYaw=0,PreviousYaw=0;
    FVector PreviousRoot=FVector::ZeroVector;
};
static TMap<TWeakObjectPtr<AProphecyAgent>,TUniquePtr<FActive>> States;
bool Drive::AttackFree(const AProphecyAgent* Agent)
{const auto* S=States.Find(Agent);return S&&(*S)->AttackFree;}
static FDelegateHandle TickHandle,CleanupHandle;
static void Refresh();
static bool Rebuild(FActive& S,FString& Error,bool PreserveSeek=false);
static void EncodePlatforms(FActive& S)
{
    TArray<TSharedPtr<FJsonValue>> Platforms;
    for(int I=0;I<S.WorldPlatforms.Num();I++){const auto& Transform=S.WorldPlatforms[I];auto P=MakeShared<FJsonObject>();P->SetStringField(TEXT("id"),FString::Printf(TEXT("platform%d"),I));P->SetArrayField(TEXT("position"),Array(ProphecyThrow::FromUnrealPoint(S.Space.InverseTransformPosition(Transform.GetLocation()))));const auto Q=S.Space.GetRotation().Inverse()*Transform.GetRotation();const FQuat Lab(-Q.X,-Q.Z,-Q.Y,Q.W);P->SetArrayField(TEXT("rotation"),{MakeShared<FJsonValueNumber>(Lab.X),MakeShared<FJsonValueNumber>(Lab.Y),MakeShared<FJsonValueNumber>(Lab.Z),MakeShared<FJsonValueNumber>(Lab.W)});P->SetArrayField(TEXT("size"),Array(ProphecyThrow::FromUnrealPoint(S.WorldPlatformSizes[I]*Transform.GetScale3D().GetAbs())));Platforms.Add(MakeShared<FJsonValueObject>(P));}
    S.Settings->SetArrayField(TEXT("platforms"),Platforms);
}
static bool AlignSpace(FActive& S,FString& Error)
{
    if(S.Aligned)return true;FString Cached;if(!S.Planner.Frame(0,Cached))return false;const auto First=Parse(Cached);if(!First){Error=TEXT("Invalid first Bodyflip frame");return false;}
    const FVector Origin=ProphecyThrow::ToUnrealPoint(Vector(First->GetArrayField(TEXT("root"))));S.Space.SetTranslation(S.InitialLowPoint-S.Space.TransformVector(Origin));
    if(!S.Agent.IsValid()||!S.Projectiles.Initialize(S.Agent->GetWorld(),S.Space,Error))return false;S.Aligned=true;
    // World setters may arrive while the first NN/scene preparation is pending.
    // Keep their world coordinates exact after the source origin becomes known.
    if(S.WorldTarget.IsSet())S.Settings->SetArrayField(TEXT("target"),Array(ProphecyThrow::FromUnrealPoint(S.Space.InverseTransformPosition(S.WorldTarget.GetValue()))));
    if(S.HasWorldPlatforms)EncodePlatforms(S);
    if(S.WorldTarget.IsSet()||S.HasWorldPlatforms){Rebuild(S,Error,true);return false;}
    return true;
}
static bool CarrierHeading(const FActive& S,const TSharedPtr<FJsonObject>& Frame,float& Yaw,FString& Error)
{
    double Radians=0;
    if(!Frame||!Frame->TryGetNumberField(TEXT("heading"),Radians)||!FMath::IsFinite(Radians))
    {Error=TEXT("Bodyflip prepared frame is missing a finite carrier heading");return false;}
    Yaw=S.InitialYaw-float(FMath::RadiansToDegrees(Radians));return true;
}
static bool Sample(FActive& S,double Time,FString& Error,bool Seeking=false)
{
    // The previous generation remains cached so the current display can hold
    // still. It is never eligible for a seek while an edit is being prepared.
    if(S.Planner.Busy()||S.RebuildPending||S.ExtendPending)return false;
    if(!AlignSpace(S,Error))return false;
    FString Cached;if(!S.Planner.Frame(FMath::RoundToInt(Time*60),Cached)){S.Status.Phase=TEXT("PREPARING");return false;}const auto Out=Parse(Cached);if(!Out){Error=TEXT("Invalid Bodyflip prepared frame");return false;}
    const auto P=Out->GetObjectField(TEXT("pose"));const auto& Points=P->GetArrayField(TEXT("points"));const auto& Q=P->GetArrayField(TEXT("q"));
    if(Points.Num()!=S.Names.Num()||Q.Num()!=S.Names.Num()){Error=TEXT("Bodyflip pose does not match the agent rig");return false;}
    float Yaw=0,PreviousYaw=0;if(!CarrierHeading(S,Out,Yaw,Error))return false;PreviousYaw=Yaw;
    FString Prior;TSharedPtr<FJsonObject> Old;
    if(S.Planner.Frame(FMath::Max(0,FMath::RoundToInt(Time*60)-2),Prior))
    {
        Old=Parse(Prior);
        if(!CarrierHeading(S,Old,PreviousYaw,Error))return false;
    }
    if(Seeking&&!S.Projectiles.CanSeek(Out,Time,Error))return false;
    S.Projectiles.SetPaused(!S.Playing);
    if(!(Seeking?S.Projectiles.Seek(Out,Time,Error):S.Projectiles.Update(Out,Time,Error)))return false;
    S.Next.SetNum(S.Names.Num());for(int I=0;I<S.Names.Num();I++)S.Next[I]=ProphecyThrow::ToUnreal(FTransform(Quaternion(Q[I]->AsArray()),Vector(Points[I]->AsArray())))*S.Space;
    const auto* Physical=S.Agent.IsValid()?S.Agent->GetJoltCharacterComponent():nullptr;
    if(Physical&&Physical->IsJoltPhysical()&&!Physical->IsSteppingStopped())S.PhysicsResolution.Record(S.Current,S.Next);
    else S.PhysicsResolution.ClearMotion();
    S.AttackFree=false;Out->TryGetBoolField(TEXT("attackFree"),S.AttackFree);
    Swap(S.Current,S.Next);
    // The policy history is 30 Hz even though presentation is 60 Hz. Do not
    // accidentally halve the inferred joint velocities when handing back to NN.
    S.Previous=S.Current;S.PreviousRoot=S.Space.TransformPosition(ProphecyThrow::ToUnrealPoint(Vector(Out->GetArrayField(TEXT("root")))));S.PreviousYaw=PreviousYaw;
    if(Old){const auto Pose=Old->GetObjectField(TEXT("pose"));const auto& PP=Pose->GetArrayField(TEXT("points"));const auto& PQ=Pose->GetArrayField(TEXT("q"));
        S.PreviousRoot=S.Space.TransformPosition(ProphecyThrow::ToUnrealPoint(Vector(Old->GetArrayField(TEXT("root")))));
        if(PP.Num()==S.Names.Num()&&PQ.Num()==S.Names.Num())for(int I=0;I<S.Names.Num();I++)S.Previous[I]=ProphecyThrow::ToUnreal(FTransform(Quaternion(PQ[I]->AsArray()),Vector(PP[I]->AsArray())))*S.Space;
    }
    S.Time=Time;S.Applied=Time;S.Status.Time=float(Time);S.Status.Active=true;S.Status.Playing=S.Playing;S.Status.Grounded=Out->GetBoolField(TEXT("grounded"));S.Status.Phase=Out->GetStringField(TEXT("phase"));
    S.Status.Root=S.Space.TransformPosition(ProphecyThrow::ToUnrealPoint(Vector(Out->GetArrayField(TEXT("root")))));
    S.Status.Velocity=S.Space.TransformVectorNoScale(ProphecyThrow::ToUnrealPoint(Vector(Out->GetArrayField(TEXT("velocity")))));
    // Keep the carrier's heading separate from the spinning pelvis.
    S.Yaw=Yaw;
    S.Status.DiagnosticsJson=Json(Out);S.Status.Error.Reset();return true;
}
static bool Rebuild(FActive& S,FString& Error,bool PreserveSeek)
{
    S.PhysicsResolution.ClearMotion();
    if(!PreserveSeek){S.SeekTime=-1;S.SeekRejected=false;}
    S.Rebuilding=true;S.Status.Error.Reset();S.Status.Phase=TEXT("PREPARING");S.Status.Playing=false;S.Applied=-1;S.Projectiles.SetPaused(true);S.Projectiles.InvalidateHistory();
    S.ExtendPending=false;if(S.Planner.Busy()){S.RebuildPending=true;return true;}S.RebuildPending=false;
    const bool Good=S.Planner.Prepare(Json(S.Settings),S.Run?Json(S.Run):FString(),FMath::Max3(S.End,S.Time,S.SeekTime),true,Error,S.RigProfile);
    if(!Good){S.Playing=false;S.Status.Error=Error;}return Good;
}
static bool Extend(FActive& S,FString& Error)
{
    S.PhysicsResolution.ClearMotion();
    S.Status.Error.Reset();S.Status.Phase=TEXT("PREPARING");S.Status.Playing=false;S.Applied=-1;S.Projectiles.SetPaused(true);
    if(S.Planner.Busy()){S.ExtendPending=true;return true;}S.ExtendPending=false;
    return S.Planner.Prepare(Json(S.Settings),S.Run?Json(S.Run):FString(),FMath::Max3(S.End,S.Time,S.SeekTime),false,Error,S.RigProfile);
}
static void RejectSeek(FActive& S,const FString& Error)
{
    S.Status=S.BeforeSeek;S.Applied=S.BeforeSeekApplied;S.SeekTime=-1;S.ExtendPending=false;
    S.Status.Playing=S.Playing;S.Status.Error=Error;S.SeekRejected=true;S.Projectiles.SetPaused(!S.Playing);
    UE_LOG(LogTemp,Warning,TEXT("Bodyflip seek rejected without changing playback: %s"),*Error);
}
static void Tick(UWorld* W,ELevelTick Type,float Delta)
{
    if(!W||W->IsPaused()||Type!=LEVELTICK_All||Delta<=0)return;
    for(auto It=States.CreateIterator();It;++It){auto* A=It.Key().Get();if(!A||A->IsActorBeingDestroyed()){It.RemoveCurrent();continue;}auto& S=*It.Value();if(A->GetWorld()!=W)continue;S.PhysicsResolution.ClearMotion();if(!S.Status.Error.IsEmpty()&&!S.SeekRejected)continue;
        FString Error;if(!S.Planner.Poll(Error)){if(S.SeekTime>=0&&!S.Rebuilding)RejectSeek(S,Error);else{S.Playing=false;S.Status.Playing=false;S.Status.Error=Error;S.Projectiles.SetPaused(true);}continue;}
        if(S.Planner.Busy())continue;
        if(S.RebuildPending||S.ExtendPending){const bool Good=S.RebuildPending?Rebuild(S,Error,true):Extend(S,Error);if(!Good){S.Playing=false;S.Status.Error=Error;}continue;}
        S.Rebuilding=false;S.Status.SolveMilliseconds=float(S.Planner.LastSeconds()*1000);
        const double Next=S.SeekTime>=0?S.SeekTime:(S.Playing&&S.Applied>=0?FMath::Min(S.Time+1./60,S.End):S.Time);
        if(Sample(S,Next,Error,S.SeekTime>=0)){if(S.SeekTime>=0)S.End=FMath::Max(S.End,S.SeekTime);S.SeekTime=-1;S.SeekRejected=false;if(Next>=S.End){S.Playing=false;S.Status.Playing=false;}}
        else if(Error.IsEmpty()&&S.SeekTime>=0&&!S.Planner.Busy()){
            // A seek requested during a shorter rebuild is prepared only after
            // that rebuild finishes; it cannot use the preceding generation.
            if(!Extend(S,Error))RejectSeek(S,Error);
        }
        else if(!Error.IsEmpty()){if(S.SeekTime>=0)RejectSeek(S,Error);else{S.Playing=false;S.Status.Playing=false;S.Status.Error=Error;S.Projectiles.SetPaused(true);UE_LOG(LogTemp,Error,TEXT("Bodyflip paused: %s"),*Error);}}}
    Refresh();
}
static void Refresh()
{
    if(States.IsEmpty()){FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);TickHandle.Reset();FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset();return;}
    if(!TickHandle.IsValid())TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
    if(!CleanupHandle.IsValid())CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool){for(auto It=States.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();Refresh();});
}
bool AnyActive(){return !States.IsEmpty();}
bool Active(const AProphecyAgent* A){return !States.IsEmpty()&&States.Contains(const_cast<AProphecyAgent*>(A));}
int32 PhysicsSubsteps(const UWorld* World,float FrameSeconds)
{
    int32 Count=1;
    for(auto& Pair:States)
    {
        const auto* Agent=Pair.Key.Get();if(!IsValid(Agent)||Agent->IsActorBeingDestroyed()||Agent->GetWorld()!=World)continue;
        const auto* Character=Agent->GetJoltCharacterComponent();
        if(!Character||!Character->IsJoltPhysical()||Character->IsSteppingStopped())continue;
        Count=FMath::Max(Count,Pair.Value->PhysicsResolution.Count(FrameSeconds));
    }
    return Count;
}
bool Root(AProphecyAgent* A,FVector& Position,float& Yaw,FVector* Velocity){const auto* S=States.Find(A);if(!S)return false;Position=(*S)->Status.Root;Yaw=(*S)->Yaw;if(Velocity)*Velocity=(*S)->Status.Playing?(*S)->Status.Velocity:FVector::ZeroVector;return true;}
bool History(AProphecyAgent* A,FVector& PreviousLowPoint,float& PreviousYaw){const auto* S=States.Find(A);if(!S)return false;PreviousLowPoint=(*S)->Status.Playing?(*S)->PreviousRoot:(*S)->Status.Root;PreviousYaw=(*S)->Status.Playing?(*S)->PreviousYaw:(*S)->Yaw;return true;}
bool Apply(AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local,const FTransform& ComponentWorld,double SourceTime)
{
    const auto* Found=States.Find(A);if(!Found)return false;auto& S=**Found;
    for(int I=0;I<Names.Num();I++){const int K=S.Names.IndexOfByKey(Names[I]);if(K==INDEX_NONE)return false;Previous[I]=(S.Status.Playing?S.Previous[K]:S.Current[K]).GetRelativeTransform(ComponentWorld);Current[I]=S.Current[K].GetRelativeTransform(ComponentWorld);Local[I]=Parents[I]<0?Current[I]:Current[I].GetRelativeTransform(Current[Parents[I]]);}return true;
}
}

bool UProphecyBodyflipLibrary::StartBodyflip(AProphecyAgent* A,const FString& SettingsJson,const FString& RunJson,FString& Error)
{
    using namespace ProphecyBodyflip;
    if(!IsValid(A)||!A->GetWorld()||!A->GetWorld()->IsGameWorld()||!A->GetAgentMesh()||!A->HasValidAgentHandle()){Error=TEXT("A live registered Prophecy agent is required");return false;}
    if(Active(A)){Error=TEXT("Stop this agent's Bodyflip controller before starting another");return false;}
    if(ProphecyFootIK::Active(A)&&!ProphecyFootIKSurface::Active(A)){Error=TEXT("Stop this agent's Foot IK reference course before starting Bodyflip");return false;}
    const auto* Overlay=A->GetProphecyAnimInstance();
    if(UProphecyNNDefenseLibrary::GetAgentState(A)!=EProphecyAgentState::Locomotion||ProphecyDefenseArmedGate::IsWaiting(A)||ProphecyArmedPose::Active(A)||(Overlay&&Overlay->bOverlayEnabled&&Overlay->OverlayAnimation)){
        Error=TEXT("Finish the agent's current defense, pending defense, armed pose or animation overlay before starting Bodyflip");return false;
    }
    FName CurrentAttack;bool Half=false,Armed=false,Hit=false;int32 AttackFrame=0;ProphecySwordHolsterPose::FStatus Holster;
    if(ProphecySwordHolster::HasPendingAction(A)||ProphecyThrow::Active(A)||A->GetNNAttackState(CurrentAttack,Half,Armed,Hit,AttackFrame)||A->IsNNAnimationLayerActive()||ProphecyReach::Active(A)||ProphecyGetUp::IsActive(A)||(ProphecySwordHolsterPose::Status(A,Holster)&&!Holster.Finished)){
        Error=TEXT("Finish the agent's current throw, attack, animation layer, reach, get-up or sword action before starting Bodyflip");return false;
    }
    auto S=MakeUnique<FActive>();S->Agent=A;S->InitialLowPoint=A->GetRootLowPoint();S->Settings=Parse(SettingsJson.IsEmpty()?TEXT("{\"mode\":\"idle\",\"jumpEvents\":[]}"):SettingsJson);if(!S->Settings){Error=TEXT("Invalid Bodyflip settings JSON");return false;}
    if(!RunJson.IsEmpty()){S->Run=Parse(RunJson);if(!S->Run){Error=TEXT("Invalid Bodyflip NN rollout JSON");return false;}}
    if(!CaptureRigProfile(A,S->RigProfile,Error))return false;
    S->Space=(A->bManualNNPoseApplication?A->GetAgentMesh()->GetRelativeTransform():A->GetAuthoredMeshRelativeTransform())*A->GetActorTransform();
    if(!S->Projectiles.Initialize(A->GetWorld(),S->Space,Error))return false;
    FString Mode=TEXT("jump"),Attack=TEXT("slashLD");S->Settings->TryGetStringField(TEXT("mode"),Mode);S->Settings->TryGetStringField(TEXT("attack"),Attack);const bool Drawn=Attack==TEXT("pike")||Attack.StartsWith(TEXT("slash"));
    if(Mode!=TEXT("spaceGym")&&!PrepareNN(Mode==TEXT("jump")?TEXT("run"):TEXT("walk"),Drawn,Error))return false;
    const TCHAR* BoneNames[]={TEXT("root"),TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
    for(const TCHAR* Name:BoneNames){S->Names.Add(FName(Name));S->Current.Add(A->GetPoseReferenceMesh()->GetSocketTransform(FName(Name),RTS_World));}S->Previous=S->Current;
    // Preparation holds this pose. Convert it once into the same lab frame as
    // the planner, relative to the carrier low point used by AlignSpace.
    auto Entry=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> EntryPoints,EntryRotations;
    const FQuat UndoBasis(FVector::ForwardVector,-UE_PI/2);
    for(int32 I=0;I<S->Current.Num();++I)
    {
        const FVector P=I==0?FVector::ZeroVector:ProphecyThrow::FromUnrealPoint(
            S->Space.InverseTransformVector(S->Current[I].GetLocation()-S->InitialLowPoint));
        const FQuat Native=(S->Space.GetRotation().Inverse()*S->Current[I].GetRotation()).GetNormalized();
        const FQuat Q=(UndoBasis*FQuat(-Native.X,Native.Y,-Native.Z,Native.W)).GetNormalized();
        EntryPoints.Add(MakeShared<FJsonValueArray>(Array(P)));
        EntryRotations.Add(MakeShared<FJsonValueArray>(TArray<TSharedPtr<FJsonValue>>{
            MakeShared<FJsonValueNumber>(Q.X),MakeShared<FJsonValueNumber>(Q.Y),MakeShared<FJsonValueNumber>(Q.Z),MakeShared<FJsonValueNumber>(Q.W)}));
    }
    Entry->SetArrayField(TEXT("points"),EntryPoints);Entry->SetArrayField(TEXT("q"),EntryRotations);
    S->Settings->SetObjectField(TEXT("nativeEntry"),Entry);
    if(!S->PhysicsResolution.Build(S->RigProfile,S->Names,A->GetPoseReferenceMesh()->GetSkeletalMeshAsset()->GetRefSkeleton(),Error))return false;
    S->Status.Root=A->GetRootLowPoint();S->InitialYaw=S->PreviousYaw=S->Yaw=float(A->GetActorRotation().Yaw);S->PreviousRoot=S->Status.Root;S->Status.Active=true;S->End=3;S->Settings->TryGetNumberField(TEXT("trimOut"),S->End);S->End=FMath::Clamp(S->End,1./60,600.);
    if(!Rebuild(*S,Error))return false;
    // Admit transactionally: a rejected action must leave live terrain intact.
    // Release its carrier/history before Bodyflip can publish its own root.
    ProphecyFootIKGame::Suspend(A);
    States.Add(A,MoveTemp(S));Refresh();return true;
}
bool UProphecyBodyflipLibrary::StartBodyflipSavedLabSetup(AProphecyAgent* A,FString& Error)
{
    FString Text;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("BodyflipLab/LabSettings.json"))))
    {Error=TEXT("Missing packaged Bodyflip lab settings");return false;}
    const auto Preset=ProphecyBodyflip::Parse(Text);FString Schema;const TSharedPtr<FJsonObject>* Settings=nullptr;
    if(!Preset||!Preset->TryGetStringField(TEXT("schema"),Schema)||Schema!=TEXT("bodyflip-lab-settings-v1")||!Preset->TryGetObjectField(TEXT("settings"),Settings))
    {Error=TEXT("Invalid packaged Bodyflip lab settings");return false;}
    return StartBodyflip(A,ProphecyBodyflip::Json(*Settings),FString(),Error);
}
bool UProphecyBodyflipLibrary::StopBodyflip(AProphecyAgent* A)
{
    if(IsValid(A)&&ProphecyBodyflip::Active(A)&&A->GetWorld()&&!A->GetWorld()->bIsTearingDown&&!A->IsActorBeingDestroyed())for(TActorIterator<AProphecyNNLocomotionManager> It(A->GetWorld());It;++It)if(It->ResolveAgent(A->GetAgentHandle())==A){It->CommitBodyflipPose(A->GetAgentHandle());break;}
    const bool Removed=ProphecyBodyflip::States.Remove(A)>0;ProphecyBodyflip::Refresh();return Removed;
}
bool UProphecyBodyflipLibrary::PauseBodyflip(AProphecyAgent* A,bool Paused){auto* S=ProphecyBodyflip::States.Find(A);if(!S)return false;(*S)->PhysicsResolution.ClearMotion();(*S)->Playing=!Paused;(*S)->Status.Playing=!Paused&&!(*S)->Planner.Busy()&&!(*S)->RebuildPending&&!(*S)->ExtendPending&&!(*S)->Rebuilding&&((*S)->Status.Error.IsEmpty()||(*S)->SeekRejected);(*S)->Projectiles.SetPaused(!(*S)->Status.Playing);return true;}
namespace ProphecyBodyflip
{
static bool SeekActive(FActive& S,double Requested,FString& Error)
{
    Error.Reset();
    // A failed generation cannot be replaced by a frame from its old cache.
    // An explicit edit/rebuild is the recovery operation.
    if(!S.Status.Error.IsEmpty()&&!S.SeekRejected){Error=S.Status.Error;return false;}
    const auto Before=S.Status;const double Applied=S.Applied;
    if(Sample(S,Requested,Error,true)){S.SeekTime=-1;S.SeekRejected=false;S.End=FMath::Max(S.End,Requested);return true;}
    if(!Error.IsEmpty())return false;
    if(S.SeekTime<0){S.BeforeSeek=Before;S.BeforeSeekApplied=Applied;}
    S.SeekTime=Requested;
    // Poll commits the new generation before Tick can evaluate the desired
    // seek. Extend only if that generation does not contain the destination.
    if(S.Planner.Busy()||S.RebuildPending||S.ExtendPending)return true;
    if(Extend(S,Error))return true;RejectSeek(S,Error);return false;
}
}
bool UProphecyBodyflipLibrary::SeekBodyflip(AProphecyAgent* A,float Time,FString& Error)
{
    using namespace ProphecyBodyflip;auto* Found=States.Find(A);if(!Found||!FMath::IsFinite(Time)||Time<0||Time>600){Error=TEXT("Bodyflip seek requires an active agent and time in 0..600 seconds");return false;}
    return SeekActive(**Found,FMath::RoundToDouble(Time*60)/60,Error);
}
bool UProphecyBodyflipLibrary::SetBodyflipTarget(AProphecyAgent* A,FVector World,FString& Error)
{using namespace ProphecyBodyflip;auto* Found=States.Find(A);if(!Found||World.ContainsNaN()){Error=TEXT("Active Bodyflip agent and finite target required");return false;}auto& S=**Found;if(S.WorldTarget.IsSet()&&S.WorldTarget.GetValue()==World)return true;S.WorldTarget=World;const auto Target=Array(ProphecyThrow::FromUnrealPoint(S.Space.InverseTransformPosition(World)));S.Settings->SetArrayField(TEXT("target"),Target);return Rebuild(S,Error);}
bool UProphecyBodyflipLibrary::GetBodyflipState(AProphecyAgent* A,FProphecyBodyflipState& Out){const auto* S=ProphecyBodyflip::States.Find(A);if(!S){Out={};return false;}Out=(*S)->Status;return true;}
bool UProphecyBodyflipLibrary::QueueBodyflipJump(AProphecyAgent* A,float Time,const FString& JumpJson,FString& Error)
{
    using namespace ProphecyBodyflip;auto* S=States.Find(A);auto Event=Parse(JumpJson);
    if(!S||!Event||!FMath::IsFinite(Time)||Time<0||Time>600){Error=TEXT("Invalid Bodyflip jump");return false;}
    const TArray<TSharedPtr<FJsonValue>>* WorldDirection=nullptr;
    if(Event->TryGetArrayField(TEXT("worldThrowDirection"),WorldDirection))
    {
        const FVector Direction=Vector(*WorldDirection);
        if(WorldDirection->Num()!=3||Direction.ContainsNaN()||Direction.IsNearlyZero())
        {Error=TEXT("Authored throw direction must be finite and nonzero");return false;}
        // Transform only the direction, never a point. Alignment can still be preparing;
        // its later translation must not change this fixed world-space ray.
        const FVector Local=WorldDirectionToLab((*S)->Space,Direction);
        Event->SetArrayField(TEXT("throwDirection"),Array(Local));Event->RemoveField(TEXT("worldThrowDirection"));
    }
    const TArray<TSharedPtr<FJsonValue>>* Old=nullptr;TArray<TSharedPtr<FJsonValue>> Events;
    if((*S)->Settings->TryGetArrayField(TEXT("jumpEvents"),Old))Events=*Old;
    if(Events.Num()>=32){Error=TEXT("Bodyflip supports 32 markers per scene");return false;}
    Event->SetNumberField(TEXT("time"),Time);Event->SetStringField(TEXT("id"),FGuid::NewGuid().ToString(EGuidFormats::Digits));Event->SetNumberField(TEXT("spinVersion"),2);
    Events.Add(MakeShared<FJsonValueObject>(Event));(*S)->Settings->SetArrayField(TEXT("jumpEvents"),Events);return Rebuild(**S,Error);
}
bool UProphecyBodyflipLibrary::SetBodyflipPlatforms(AProphecyAgent* A,const TArray<FTransform>& Transforms,const TArray<FVector>& Sizes,FString& Error)
{
    using namespace ProphecyBodyflip;auto* Found=States.Find(A);if(!Found||Transforms.Num()!=Sizes.Num()||Transforms.Num()>128){Error=TEXT("Supply equal platform transforms/sizes (maximum128)");return false;}auto& S=**Found;
    for(int I=0;I<Transforms.Num();I++)if(Transforms[I].ContainsNaN()||Sizes[I].ContainsNaN()||Sizes[I].GetMin()<=0){Error=TEXT("Platform values must be finite and positive");return false;}
    S.WorldPlatforms=Transforms;S.WorldPlatformSizes=Sizes;S.HasWorldPlatforms=true;EncodePlatforms(S);return Rebuild(S,Error);
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipCarrierHeadingTest,"Prophecy.Bodyflip.Controls.CarrierHeading",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipCarrierHeadingTest::RunTest(const FString&)
{
    using namespace ProphecyBodyflip;
    FActive State;State.InitialYaw=37.f;State.Yaw=-81.f;FString Error;
    const TArray<double> Radians={0.,PI/2.,-PI,PI/4.};
    const TArray<float> Expected={37.f,-53.f,217.f,-8.f};
    TArray<TSharedPtr<FJsonObject>> Frames;
    for(const double Angle:Radians)
    {
        // The virtual root carries an authored FBX basis and may spin in air.
        // Neither is a valid source for the controller's horizontal heading.
        auto Frame=Parse(TEXT("{\"pose\":{\"q\":[[0.1,0.2,0.3,0.9]]}}"));
        Frame->SetNumberField(TEXT("heading"),Angle);Frames.Add(Frame);
    }
    for(const int32 Index:{3,0,2,1,3,0})
    {
        float Actual=0;
        TestTrue(TEXT("Prepared heading is available in either seek order"),CarrierHeading(State,Frames[Index],Actual,Error));
        TestTrue(TEXT("Initial facing and backward landing convert in the original world frame"),FMath::IsNearlyEqual(Actual,Expected[Index],1.e-4f));
    }
    TestEqual(TEXT("Queries do not accumulate or overwrite carrier state"),State.Yaw,-81.f);
    float Unchanged=12.f;
    TestFalse(TEXT("Old packets cannot silently infer heading from an animation bone"),CarrierHeading(State,Parse(TEXT("{\"heading\":null}")),Unchanged,Error));
    TestEqual(TEXT("A missing heading leaves the displayed yaw intact"),Unchanged,12.f);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipPhysicsResolutionTest,"Prophecy.Bodyflip.Physics.SubstepResolution",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipPhysicsResolutionTest::RunTest(const FString&)
{
    using namespace ProphecyBodyflip;
    FPhysicsResolution Policy;Policy.PoseIndices={0};Policy.Parents={INDEX_NONE};
    TestEqual(TEXT("Inactive world does not request extra physics"),PhysicsSubsteps(nullptr,1.f/60),1);
    TestEqual(TEXT("Physical hold retains240Hz at60Hz presentation"),Policy.Count(1.f/60,10),4);
    TestEqual(TEXT("120Hz presentation has two base intervals"),Policy.Count(1.f/120,10),2);
    TestEqual(TEXT("240Hz presentation has one base interval"),Policy.Count(1.f/240,10),1);
    const uint32 SixtiethBits=FMath::AsUInt(1.f/60);
    TestEqual(TEXT("The next float above1/60 needs another base interval"),Policy.Count(FMath::AsFloat(SixtiethBits+1u),10),5);
    TestEqual(TEXT("The previous float below1/60 still fits four intervals"),Policy.Count(FMath::AsFloat(SixtiethBits-1u),10),4);
    TestEqual(TEXT("Nonintegrating interval requests no extra work"),Policy.Count(0,10),1);
    TArray<FTransform> Before{FTransform::Identity},After{FTransform(FQuat(FVector::UpVector,.12))};
    Policy.Record(Before,After,10);
    TestEqual(TEXT("The mixed-parent fixture turn resolves within four base steps"),Policy.Count(1.f/60,10),4);
    After[0].SetRotation(FQuat(FVector::UpVector,3.));Policy.Record(Before,After,10);
    TestEqual(TEXT("Fast turn subdivides each240Hz interval"),Policy.Count(1.f/60,10),52);
    TestEqual(TEXT("Repeated publication uses the same demand"),Policy.Count(1.f/60,10),52);
    TestEqual(TEXT("The32 cap applies within one240Hz interval"),Policy.Count(1.f/240,10),32);
    TestEqual(TEXT("Old motion is not replayed on the next frame"),Policy.Count(1.f/60,11),4);
    Policy.ClearMotion();
    TestEqual(TEXT("Pause and preparation clear angular demand but retain hold quality"),Policy.Count(1.f/60,10),4);
    Policy.PoseIndices={0,1,2};Policy.Parents={INDEX_NONE,0,1};
    Before={FTransform::Identity,FTransform::Identity,FTransform::Identity};
    After={FTransform(FQuat(FVector::UpVector,3.)),FTransform(FQuat(FVector::UpVector,6.)),FTransform(FQuat(FVector::UpVector,9.))};
    Policy.Record(Before,After,11);
    TestEqual(TEXT("Four base intervals may each use32 subdivisions"),Policy.Count(1.f/60,11),128);

    // Noncommuting local turns describe a curved world path. Dividing only the
    // final world-space angle by four misses its larger intermediate motion.
    Policy.PoseIndices={0,1};Policy.Parents={INDEX_NONE,0};
    Before={FTransform::Identity,FTransform::Identity};
    After={FTransform(FQuat(FVector::ForwardVector,3.)),FTransform(FQuat(FVector::RightVector,3.))};
    Policy.Record(Before,After,12);const int32 Curved=Policy.Count(1.f/60,12);
    TestTrue(TEXT("Local-chain path receives more resolution than endpoint-only interpolation"),Curved>52);
    const FQuat WorldTurn(FVector(1,2,3).GetSafeNormal(),.7);
    for(auto& Pose:Before)Pose.SetRotation((WorldTurn*Pose.GetRotation()).GetNormalized());
    for(auto& Pose:After)Pose.SetRotation((WorldTurn*Pose.GetRotation()).GetNormalized());
    Policy.Record(Before,After,13);
    TestEqual(TEXT("Changing the world basis preserves physical resolution"),Policy.Count(1.f/60,13),Curved);
    for(auto& Pose:After)Pose.SetRotation(Pose.GetRotation()*-1.);
    Policy.Record(Before,After,14);
    TestEqual(TEXT("Equivalent quaternion signs preserve physical resolution"),Policy.Count(1.f/60,14),Curved);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipFailedSeekTest,"Prophecy.Bodyflip.Controls.FailedGenerationRetainsError",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipFailedSeekTest::RunTest(const FString&)
{
    ProphecyBodyflip::FActive State;State.Aligned=true;State.Time=State.Applied=.2;
    State.Status.Time=.2f;State.Status.Phase=TEXT("PREPARING");State.Status.Error=TEXT("original preparation failure");
    State.Current.Add(FTransform(FVector(10,20,30)));const auto Before=State.Current[0];FString Error;
    TestFalse(TEXT("Seeking cannot clear a failed generation"),ProphecyBodyflip::SeekActive(State,.1,Error));
    TestEqual(TEXT("Original failure is retained"),Error,State.Status.Error);
    TestEqual(TEXT("Failed seek does not move source time"),State.Time,.2);
    TestTrue(TEXT("Failed seek leaves displayed pose intact"),State.Current[0].Equals(Before,0));
    TestFalse(TEXT("Failed seek starts no replacement generation"),State.Planner.Busy());
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipThrowDirectionTest,"Prophecy.Bodyflip.Controls.WorldThrowDirection",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipThrowDirectionTest::RunTest(const FString&)
{
    const FVector World(3,-2,1);FTransform Space(FQuat(FVector::UpVector,.9),FVector(100,200,300));
    const FVector Lab=ProphecyBodyflip::WorldDirectionToLab(Space,World);
    const FVector RoundTrip=Space.TransformVectorNoScale(ProphecyThrow::ToUnrealPoint(Lab)).GetSafeNormal();
    TestTrue(TEXT("Authored ray retains absolute world direction"),RoundTrip.Equals(World.GetSafeNormal(),1.e-12));
    Space.SetTranslation(FVector(-500,700,1000));Space.SetScale3D(FVector(2,3,4));
    TestTrue(TEXT("Entry alignment and scale cannot steer the ray"),ProphecyBodyflip::WorldDirectionToLab(Space,World).Equals(Lab,1.e-12));
    TestTrue(TEXT("Direction magnitude does not change aim"),ProphecyBodyflip::WorldDirectionToLab(Space,World*.001).Equals(Lab,1.e-12));
    return !HasAnyErrors();
}
#endif
