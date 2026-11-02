#include "ProphecyFootIKGame.h"
#include "ProphecyFootIKLive.h"
#include "ProphecyFootIKForecast.h"
#include "ProphecyFootIKOwner.h"
#include "ProphecyFootIKSurfaceOwner.h"
#include "ProphecyFootIKNavigation.h"
#include "ProphecyFootIKTerrainReturn.h"
#include "ProphecyBodyflipRuntime.h"
#include "ProphecyGetUp.h"
#include "ProphecyThrowRuntime.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNPoseTypes.h"
#include "Misc/ScopeRWLock.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#endif

namespace ProphecyFootIKGame
{
namespace
{
const FName Names[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
struct FOverlay { TArray<FTransform> World; };
struct FCommand
{
    FVector Move=FVector::ZeroVector,Facing=FVector::ForwardVector;
    double SpeedScale=1,TurnScale=1,TimeScale=1;
    bool Blueprint=false,Run=false;
    bool Equals(const FCommand& Other) const
    {
        return Blueprint==Other.Blueprint&&Run==Other.Run&&Move.Equals(Other.Move,Blueprint?1.e-8:.01)&&
            Facing.Equals(Other.Facing,1.e-5)&&SpeedScale==Other.SpeedScale&&TurnScale==Other.TurnScale&&TimeScale==Other.TimeScale;
    }
};
FCommand CaptureCommand(bool Blueprint,const FProphecyLocomotionInput& I,const FVector& Velocity,const FVector& Facing,bool Run,double TimeScale)
{
    FCommand Out;Out.Move=Velocity;Out.Facing=Facing;Out.Run=Run;Out.TimeScale=TimeScale;
    // Directional speed caps evolve while the SAME held world input turns the
    // body. Those changes are already predicted in the controller root window;
    // treating them as new commands continually cancels the useful forecast.
    // Retain exact caller input/scales, and the resolved facing (which also
    // catches externally retargeted yaw). Non-Blueprint movers keep the
    // conservative resolved-command invalidation contract.
    if(Blueprint)
    {
        Out.Blueprint=true;
        Out.Move=I.WorldMoveInput.ContainsNaN()?FVector::ZeroVector:FVector(I.WorldMoveInput.X,I.WorldMoveInput.Y,0);
        Out.Run=I.bRun;
        Out.SpeedScale=FMath::IsFinite(I.SpeedScale)?FMath::Clamp(double(I.SpeedScale),0.,1.):0.;
        Out.TurnScale=FMath::IsFinite(I.TurnScale)?FMath::Clamp(double(I.TurnScale),0.,1.):0.;
    }
    return Out;
}
FRWLock OverlayLock;
TMap<int32,FOverlay> Overlays;
TAtomic<int32> OverlayCount{0};
struct FGame
{
    int32 PoseId=-1,Tick=0;
    uint64 LastGameTick=MAX_uint64,Revision=1;
    FTransform Space=FTransform::Identity;
    TSharedPtr<FProphecyFootIKForecast,ESPMode::ThreadSafe> Forecast;
    ProphecyFootIKLive::FSourceSample LastTick,PriorTick,LastPolicy,LastActualPolicy;
    FTerrainReturn Return;
    TArray<FTransform> ExitPublication;
    double ExitSourceTime=-1,FirstExitPublicationTime=-1;
    int32 TerrainExits=0;
    bool HasActualPolicy=false,TerrainEpisode=false;
    FCommand Command;
    FString Failure,Terrain;
    uint32 GeometryHash=0;
    bool Prepared=false,Attempted=false,HasPolicy=false,HasCommand=false,HasSubmitted=false,Suspended=false,WaitingPolicy=true;
};
TMap<TWeakObjectPtr<AProphecyAgent>,TUniquePtr<FGame>> States;
void ClearOverlay(int32 Id){FWriteScopeLock Lock(OverlayLock);Overlays.Remove(Id);OverlayCount.Store(Overlays.Num());}
bool ReadRaw(AProphecyAgent* A,ProphecyFootIKLive::FSourceSample& Out,double& SourceTime,ProphecyFootIKLive::FSourceSample& Endpoint)
{
    TArray<FName> BoneNames;TArray<FTransform> Future,World;float Alpha=1;FProphecyNNPoseSnapshot Snapshot;
    if(!A->ReadNNFutureWorldPoseWithSnapshot(BoneNames,Future,World,Alpha,Snapshot,false))return false;
    SourceTime=Snapshot.SourceTimeSeconds;
    Out.RootWorld=A->GetRootLowPoint();Out.HeadingWorld=A->GetActorForwardVector();Out.BodiesWorld.Reset(25);
    const FTransform MeshRelative=A->bManualNNPoseApplication?A->GetAgentMesh()->GetRelativeTransform():A->GetAuthoredMeshRelativeTransform();
    const FTransform FutureCapsule=MeshRelative.Inverse()*Snapshot.ComponentWorldTransform;
    Endpoint.RootWorld=FutureCapsule.GetLocation()-FVector::UpVector*A->GetAgentCapsule()->GetScaledCapsuleHalfHeight();
    Endpoint.HeadingWorld=FutureCapsule.GetRotation().GetForwardVector();Endpoint.BodiesWorld.Reset(25);
    for(FName Name:Names){const int32 I=BoneNames.IndexOfByKey(Name);if(!World.IsValidIndex(I)||!Future.IsValidIndex(I))return false;Out.BodiesWorld.Add(World[I]);Endpoint.BodiesWorld.Add(Future[I]);}
    return true;
}
bool HigherPriority(AProphecyNNLocomotionManager& Manager,AProphecyAgent* A)
{
    bool Parry=false,Dodge=false;Manager.GetAgentAttackDefenseState(A->GetAgentHandle(),Parry,Dodge);
    FName Attack;bool Half=false,Armed=false,Hit=false;int32 Frame=0;
    const bool Attacking=Manager.GetAgentNNAttackState(A->GetAgentHandle(),Attack,Half,Armed,Hit,Frame);
    const bool ReferenceCourse=ProphecyFootIK::Active(A)&&!ProphecyFootIKSurface::Active(A);
    return !A->bNNInferenceEnabled||ProphecyBodyflip::Active(A)||ReferenceCourse||ProphecyGetUp::IsActive(A)||ProphecyThrow::Active(A)||Attacking||Parry||Dodge;
}
}
void Remove(AProphecyAgent* A)
{
    if(IsValid(A))if(auto* Manager=Cast<AProphecyNNLocomotionManager>(A->GetOwner()))Manager->ReleaseFootIKNavigation(A);
    if(ProphecyFootIKSurface::Active(A)&&IsValid(A)&&!A->IsActorBeingDestroyed())
        if(auto* Manager=Cast<AProphecyNNLocomotionManager>(A->GetOwner());IsValid(Manager)&&!Manager->IsActorBeingDestroyed())
        {FString Why;Manager->RestoreFootIKSurfacePolicy(A,Why);}
    ProphecyFootIKSurface::Remove(A);
    if(auto* S=States.Find(A)){ClearOverlay((*S)->PoseId);if((*S)->Forecast)(*S)->Forecast->Cancel();States.Remove(A);}
}
void ConfigurationChanged(AProphecyAgent* A)
{
    Remove(A);
}
void Suspend(AProphecyAgent* A)
{
    if(auto* Manager=Cast<AProphecyNNLocomotionManager>(A->GetOwner()))Manager->ReleaseFootIKNavigation(A);
    if(ProphecyFootIKSurface::Active(A))
    {
        if(auto* Manager=Cast<AProphecyNNLocomotionManager>(A->GetOwner())){FString Why;Manager->RestoreFootIKSurfacePolicy(A,Why);}
    }
    ProphecyFootIKSurface::Remove(A);
    if(auto* Found=States.Find(A)){ClearOverlay((*Found)->PoseId);if((*Found)->Forecast)(*Found)->Forecast->Cancel();(*Found)->Suspended=true;}
}
bool RefreshSurface(AProphecyAgent* A,const FVector& Desired,FString& Error)
{
    auto* Found=States.Find(A);if(!Found){Error=TEXT("Missing live surface epoch");return false;}auto& S=**Found;
    FVector Position,Velocity;float Yaw=0;if(!ProphecyFootIKSurface::Root(A,Position,Yaw,&Velocity))return false;
    TArray<ProphecyFootIKLive::FSourceSample,TInlineAllocator<3>> Bounds;
    for(const FVector P:{Position,Position+Velocity*.5,Position+Desired*.5})Bounds.AddDefaulted_GetRef().RootWorld=P;
    FString Geometry;uint32 Hash=0;
    if(!ProphecyFootIKLive::CaptureSurfaceTerrain(A,S.Space,Bounds,Geometry,Error)||!ProphecyFootIKLive::TerrainGeometryHash(Geometry,Hash,Error))return false;
    if(Hash!=S.GeometryHash)
    {if(!ProphecyFootIKSurface::UpdateGeometry(A,Geometry,Error))return false;S.GeometryHash=Hash;}
    return true;
}
void BeforeActions(AProphecyNNLocomotionManager& Manager,AProphecyAgent* A)
{
    if(IsValid(A)&&ProphecyFootIKLive::Enabled(A)&&HigherPriority(Manager,A))Suspend(A);
}
bool Preparing(const AProphecyAgent* A)
{
    const auto* Found=States.Find(const_cast<AProphecyAgent*>(A));
    // Model warmup is followed by collecting the first real30Hz history pair.
    // That short interval is still preparation, before any live job exists.
    return Found&&(*Found)->Failure.IsEmpty()&&((*Found)->WaitingPolicy||((*Found)->Attempted&&!(*Found)->HasSubmitted));
}
FString Error(const AProphecyAgent* A){const auto* S=States.Find(const_cast<AProphecyAgent*>(A));return S?(*S)->Failure:FString();}
bool Returning(const AProphecyAgent* A){const auto* S=States.Find(const_cast<AProphecyAgent*>(A));return S&&(*S)->Return.BeginTick>=0;}
int32 TerrainExits(const AProphecyAgent* A){const auto* S=States.Find(const_cast<AProphecyAgent*>(A));return S?(*S)->TerrainExits:0;}
void RestoreExitPredecessor(AProphecyAgent* A,double SourceTime,TConstArrayView<FName> BoneNames,
    TArrayView<FTransform> Previous,const FTransform& Carrier)
{
    auto* Found=States.Find(A);if(!Found||(*Found)->ExitPublication.Num()!=25)return;auto& S=**Found;
    auto* Manager=Cast<AProphecyNNLocomotionManager>(A->GetOwner());
    if(!Manager||HigherPriority(*Manager,A)){S.ExitPublication.Reset();return;}
    if(SourceTime<=S.ExitSourceTime+1.e-8)return;
    if(S.FirstExitPublicationTime<0)S.FirstExitPublicationTime=SourceTime;
    if(SourceTime>S.FirstExitPublicationTime+1.e-8){S.ExitPublication.Reset();return;}
    // Reduced NN features cannot retain every interpolated joint transform.
    // Re-decoding also applies locomotion length clamps. Keep the actual seed
    // as the predecessor for exactly one policy interval, including repeated
    // publication at the same source time; subsequent endpoints are ordinary NN.
    for(int32 I=0;I<BoneNames.Num()&&I<Previous.Num();++I)
        for(int32 J=0;J<25;++J)if(BoneNames[I]==Names[J])
        {const FVector Scale=Previous[I].GetScale3D();Previous[I]=S.ExitPublication[J].GetRelativeTransform(Carrier);Previous[I].SetScale3D(Scale);break;}
}
void Apply(int32 Id,TConstArrayView<FName> BoneNames,TArrayView<FTransform> Pose,const FTransform& Carrier)
{
    if(!OverlayCount.Load())return;
    FReadScopeLock Lock(OverlayLock);const auto* Entry=Overlays.Find(Id);if(!Entry||Entry->World.Num()!=25)return;
    for(int32 I=0;I<BoneNames.Num()&&I<Pose.Num();++I)
        for(int32 J=0;J<25;++J)if(BoneNames[I]==Names[J]){const FVector Scale=Pose[I].GetScale3D();Pose[I]=Entry->World[J].GetRelativeTransform(Carrier);Pose[I].SetScale3D(Scale);break;}
}
void Update(AProphecyNNLocomotionManager& Manager,AProphecyAgent* A,int32 PoseId,uint64 GameTick)
{
    if(!ProphecyFootIKLive::Enabled(A)){Remove(A);return;}
    if(ProphecyFootIKSurface::Active(A))return;
    auto& Ptr=States.FindOrAdd(A);if(!Ptr){Ptr=MakeUnique<FGame>();Ptr->PoseId=PoseId;Ptr->Space=FTransform(FRotator(0,A->GetActorRotation().Yaw-90,0),A->GetRootLowPoint());}
    auto& S=*Ptr;if(S.LastGameTick==GameTick)return;S.LastGameTick=GameTick;
    // Higher-level authored actions retain their existing priority. Resume with
    // fresh actual history; a speculative locomotion plan must not replace them.
    if(HigherPriority(Manager,A))
    {Suspend(A);return;}
    if(S.Suspended)
    {
        FString RestartError;ProphecyFootIKLive::Enable(A,false,RestartError);
        ProphecyFootIKLive::Enable(A,true,RestartError);return;
    }
    float WalkWeight=0,RunWeight=0;FVector2f LegWalkWeights;
    S.WaitingPolicy=!Manager.GetAgentLocomotionCheckpointWeights(A->GetAgentHandle(),WalkWeight,RunWeight,&LegWalkWeights)||
        WalkWeight>0||LegWalkWeights.X>0||LegWalkWeights.Y>0;
    // Do not forecast Run from a still-blending Walk history. The normal
    // policy transition keeps moving; capture a fresh pair once it completes.
    if(S.WaitingPolicy){S.HasPolicy=false;ClearOverlay(PoseId);return;}
    ProphecyFootIKLive::FSourceSample Raw,Endpoint;double SourceTime=0;if(!ReadRaw(A,Raw,SourceTime,Endpoint)){S.Failure=TEXT("Foot IK cannot read all25 actual NN body targets");ClearOverlay(PoseId);return;}
    const FString Settings=ProphecyFootIKLive::Settings(A);TSharedPtr<FJsonObject> SettingsObject;
    FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Settings),SettingsObject);FString TerrainMode;
    const bool SurfaceMode=SettingsObject&&SettingsObject->TryGetStringField(TEXT("terrain"),TerrainMode)&&TerrainMode==TEXT("incline");
    if(SurfaceMode)
    {
        if(!S.HasPolicy){S.LastPolicy=Raw;S.HasPolicy=true;S.Tick=0;return;}
        S.Tick+=2;if(S.Tick<4)return;
        TArray<ProphecyFootIKLive::FSourceSample> Samples{S.LastPolicy,Raw};
        FVector V,F;bool Run=false;if(Manager.GetAgentLocomotionState(A->GetAgentHandle(),V,F,Run))
            for(int32 I=1;I<=9;++I){auto P=Raw;P.RootWorld+=V*(I/30.);Samples.Add(MoveTemp(P));}
        FString Geometry;
        if(ProphecyFootIKLive::CaptureSurfaceTerrain(A,S.Space,Samples,Geometry,S.Failure))
        {
            if(ProphecyFootIKSurface::Enable(A,S.Space,S.LastPolicy,Raw,Settings,Geometry,Manager.RuntimeContractPath,Manager.UpperRuntimeContractPath,S.Failure))
                ProphecyFootIKLive::TerrainGeometryHash(Geometry,S.GeometryHash,S.Failure);
        }
        S.LastPolicy=Raw;S.Tick=0;
        return;
    }
    double MaximumIncline=80.;if(SettingsObject)SettingsObject->TryGetNumberField(TEXT("minGravityIncline"),MaximumIncline);
    ProphecyFootIKNavigation::Begin(A,Raw.RootWorld.Z,MaximumIncline);
    if(!S.Attempted)
    {
        S.Attempted=true;S.Forecast=MakeShared<FProphecyFootIKForecast,ESPMode::ThreadSafe>();
        S.Forecast->Prepare(Manager.RuntimeContractPath,S.Failure);
    }
    if(!S.Prepared&&S.Failure.IsEmpty())S.Prepared=S.Forecast->Ready(S.Failure);
    if(!S.Prepared)return;
    // The actual history pair starts only after both solver contexts are warm.
    // Otherwise cold compilation can consume the entire prospective horizon.
    if(!ProphecyFootIKLive::SourceReady(A,S.Failure))return;
    FVector Velocity,Facing;float Speed=0;bool Run=false;
    if(!Manager.GetAgentLocomotionTarget(A->GetAgentHandle(),Velocity,Speed,Facing,Run))return;
    const FCommand Command=CaptureCommand(A->bUseBlueprintLocomotionInput&&!Manager.bSimBridge,A->LocomotionInput,
        Velocity,Facing,Run,Manager.GetAgentTimeDilation(A->GetAgentHandle()));
    if(!S.HasCommand||!Command.Equals(S.Command))
    {++S.Revision;S.Command=Command;S.HasCommand=true;}
    if(!S.HasPolicy){S.LastActualPolicy=S.LastPolicy=S.LastTick=S.PriorTick=Raw;S.HasPolicy=S.HasActualPolicy=true;return;}
    S.Tick+=2;
    auto Final=Raw;const bool Carry=S.Return.Apply(S.Tick,SourceTime,Final,Endpoint);
    if(S.Tick%4==0&&!Carry)
    {
        auto Input=MakeShared<FProphecyFootIKForecastInput,ESPMode::ThreadSafe>();Input->CurrentTick=S.Tick;Input->Previous=S.LastPolicy;Input->Current=Raw;Input->CourseWorld=S.Space;Input->Gait=Run?TEXT("run"):TEXT("walk");
        TArray<float> Times;
        if(Manager.GetAgentContinuousLocomotionRootWindow(A->GetAgentHandle(),Input->RootWorldWindow,Times)&&Input->RootWorldWindow.Num()==9)
        {
            Input->RootWorldWindow.Insert(FTransform(Input->Previous.HeadingWorld.Rotation(),Input->Previous.RootWorld),0);
            // Actual history is authoritative, including the collision-resolved
            // positions. Future rows retain the controller's exact prediction.
            Input->RootWorldWindow[0]=FTransform(Input->Previous.HeadingWorld.Rotation(),Input->Previous.RootWorld);
            Input->RootWorldWindow[1]=FTransform(Input->Current.HeadingWorld.Rotation(),Input->Current.RootWorld);
            TArray<FTransform> Roots;TArray<ProphecyFootIKLive::FSourceSample> Bounds;
            if(FProphecyFootIKForecast::ExtendRoots(*Input,Roots,S.Failure))
            {
                // The manager's known window already follows the real navigation
                // surface. Project only the longer forecast tail from its last
                // known row so terrain IK sees the same future root carrier.
                TArray<FTransform> Tail;
                Tail.Append(Roots.GetData()+9,Roots.Num()-9);
                ProphecyFootIKNavigation::ProjectWindow(A,Tail);
                for(int32 I=1;I<Tail.Num();++I)Roots[I+9]=Tail[I];
                Input->NavRootWindow=Roots;
                Bounds.Reserve(Roots.Num());for(const auto& R:Roots){auto& P=Bounds.AddDefaulted_GetRef();P.RootWorld=R.GetLocation();}
                FString Terrain;
                if(ProphecyFootIKLive::CaptureTerrain(A,S.Space,Bounds,Terrain,S.Failure))
                {
                    uint32 Hash=0;if(!ProphecyFootIKLive::TerrainGeometryHash(Terrain,Hash,S.Failure))return;
                    if(Hash!=S.GeometryHash){S.GeometryHash=Hash;S.Terrain=Terrain;}
                    ProphecyFootIKLive::FInput Request;Request.CurrentTick=S.Tick;Request.SourceStartTick=S.Tick-4;Request.CommandRevision=S.Revision;Request.GeometryRevision=S.GeometryHash;Request.CourseWorld=S.Space;Request.TerrainJson=MoveTemp(Terrain);Request.Forecaster=S.Forecast;Request.ForecastInput=Input;
                    if(S.HasActualPolicy&&!ProphecyFootIKLive::BuildInitialHistory(S.Tick-4,S.Tick,S.LastActualPolicy,Final,S.Space,Request.InitialHistoryJson,S.Failure))return;
                    if(ProphecyFootIKLive::Submit(A,Request,S.Failure))S.HasSubmitted=true;
                }
            }
        }
    }
    if(S.Tick%4==0)S.LastPolicy=Raw;
    ProphecyFootIKLive::FOutput Solved;
    const bool Joined=!Carry&&ProphecyFootIKLive::ConsumeJoined(A,S.Tick,S.Revision,S.LastTick,Raw,Solved,S.Failure)&&Solved.PoseWorld.Num()==26;
    if(Joined)
        for(int32 I=0;I<25;++I)Final.BodiesWorld[I]=Solved.PoseWorld[I+1];
    if(Joined||Carry)
    {
        FOverlay Result;Result.World=Final.BodiesWorld;
        {FWriteScopeLock Lock(OverlayLock);Overlays.Add(PoseId,MoveTemp(Result));OverlayCount.Store(Overlays.Num());}
        if(Carry)ProphecyFootIKLive::PublishContinuation(A,S.Tick);
    }
    else
    {
        ClearOverlay(PoseId);
    }
    if(!Joined){FString ObserveError;ProphecyFootIKLive::ObserveActualPose(A,S.Tick,Final,ObserveError);if(!ObserveError.IsEmpty())S.Failure=ObserveError;}
    if(Joined)
    {
        TSharedPtr<FJsonObject> Frame;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Solved.DiagnosticsJson),Frame);double Influence=0;bool VerifiedRawFallback=false;
        if(Frame)Frame->TryGetBoolField(TEXT("verifiedRawFallback"),VerifiedRawFallback);
        if(Frame&&Frame->TryGetNumberField(TEXT("influence"),Influence)&&Influence>0)S.TerrainEpisode=true;
        // A verified raw fallback only changes readiness reporting. It must
        // not initiate a new recurrent reseed/return while a plan is pending.
        if(!VerifiedRawFallback&&S.TerrainEpisode&&S.Tick>=4&&ProphecyFootIKLive::TerrainExitReady(A,S.Tick,Solved.DiagnosticsJson,S.Failure))
        {
            if(!Manager.ReseedFootIKTerrainExit(A,S.PriorTick,Final,(S.Tick-4)/120.,S.Tick/120.,S.Failure))return;
            S.ExitPublication=Final.BodiesWorld;S.ExitSourceTime=SourceTime;S.FirstExitPublicationTime=-1;
            S.Return.Begin(S.Tick,SourceTime,S.LastTick,Final);++S.TerrainExits;S.TerrainEpisode=false;++S.Revision;
            ProphecyFootIKLive::InvalidatePrediction(A);
        }
    }
    if(S.Tick%4==0){S.LastActualPolicy=Final;S.HasActualPolicy=true;}S.PriorTick=MoveTemp(S.LastTick);S.LastTick=MoveTemp(Final);
}
#if WITH_DEV_AUTOMATION_TESTS
#include "Tests/ProphecyFootIKCommandTests.inl"
#endif
}
