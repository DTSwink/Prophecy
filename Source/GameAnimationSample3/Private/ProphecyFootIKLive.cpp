#include "ProphecyFootIKLive.h"
#include "ProphecyFootIKLiveLibrary.h"
#include "ProphecyFootIKOwner.h"
#include "ProphecyFootIKVM.h"
#include "ProphecyFootIKForecast.h"
#include "ProphecyFootIKPreparation.h"
#include "ProphecyFootIKGame.h"
#include "ProphecyFootIKLiveGeometry.h"
#include "ProphecyFootIKCollision.h"
#include "ProphecyFootIKSurfaceOwner.h"
#include "ProphecyThrowMath.h"
#include "ProphecyAgent.h"
#include "Async/Async.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "Engine/OverlapResult.h"
#include "Misc/ScopeLock.h"
#include "Misc/Crc.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "PhysicsEngine/BodySetup.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonSerializer.h"

namespace ProphecyFootIKLive
{
namespace
{
using FValues=TArray<TSharedPtr<FJsonValue>>;
using FActualText=TSharedPtr<const FString,ESPMode::ThreadSafe>;
FString Json(const TSharedPtr<FJsonObject>& O){FString S;FJsonSerializer::Serialize(O.ToSharedRef(),TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&S));return S;}
TSharedPtr<FJsonObject> Parse(const FString& S){TSharedPtr<FJsonObject> O;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S),O);return O;}
bool UniformNavigationTerrain(const TSharedPtr<FJsonObject>& Terrain)
{
    const FValues *Tiles=nullptr,*Rows=nullptr;
    if(!Terrain||!Terrain->TryGetArrayField(TEXT("tiles"),Tiles)||Tiles->IsEmpty()||!Terrain->TryGetArrayField(TEXT("rootRows"),Rows)||Rows->Num()<2)return false;
    const auto Numbers=[](const TSharedPtr<FJsonObject>& O,const TCHAR* Key,int32 Count,TArray<double>& Out)
    {
        const FValues* Values=nullptr;if(!O||!O->TryGetArrayField(Key,Values)||Values->Num()!=Count)return false;Out.Reset(Count);
        for(const auto& Value:*Values){double N=0;if(!Value||!Value->TryGetNumber(N)||!FMath::IsFinite(N))return false;Out.Add(N);}return true;
    };
    TArray<double> Heights,Position;double LastTime=-TNumericLimits<double>::Max();
    for(const auto& Value:*Rows)
    {
        if(!Value||Value->Type!=EJson::Object)return false;const auto Row=Value->AsObject();double Time=0;
        if(!Row||!Row->TryGetNumberField(TEXT("time"),Time)||!FMath::IsFinite(Time)||Time<=LastTime||!Numbers(Row,TEXT("position"),3,Position))return false;
        LastTime=Time;Heights.Add(Position[1]);
    }
    for(const auto& Value:*Tiles)
    {
        if(!Value||Value->Type!=EJson::Object)return false;const auto Tile=Value->AsObject();FString Id;double Height=0;TArray<double> Point,U,V,Bounds;
        if(!Tile||!Tile->TryGetStringField(TEXT("id"),Id))return false;
        if(Tile->HasField(TEXT("point")))
        {
            if(!Numbers(Tile,TEXT("point"),3,Point)||!Numbers(Tile,TEXT("u"),3,U)||!Numbers(Tile,TEXT("v"),3,V)||!Numbers(Tile,TEXT("bounds"),4,Bounds))return false;
            const FVector A(U[0],U[1],U[2]),B(V[0],V[1],V[2]);
            if(FMath::Abs(A.Y)+FMath::Abs(B.Y)>1.e-8||FMath::Abs(A.Size()-1)>1.e-8||FMath::Abs(B.Size()-1)>1.e-8||FMath::Abs(FVector::DotProduct(A,B))>1.e-8)return false;
            Height=Point[1];
        }
        else
        {
            for(const TCHAR* Key:{TEXT("x0"),TEXT("x1"),TEXT("z0"),TEXT("z1")}){double N=0;if(!Tile->TryGetNumberField(Key,N)||!FMath::IsFinite(N))return false;Bounds.Add(N);}
            if(!Tile->TryGetNumberField(TEXT("y"),Height)||!FMath::IsFinite(Height))return false;
        }
        if(Bounds[0]>=Bounds[1]||Bounds[2]>=Bounds[3])return false;
        bool Shaped=true;Tile->TryGetBoolField(TEXT("shaped"),Shaped);
        if(Shaped)for(double Y:Heights)if(FMath::Abs(Height-Y)>.005)return false;
    }
    return true;
}
FValues Array(const FVector& P){return {MakeShared<FJsonValueNumber>(P.X),MakeShared<FJsonValueNumber>(P.Y),MakeShared<FJsonValueNumber>(P.Z)};}
FValues Axes(const FQuat& Q)
{
    const double X=Q.X,Y=Q.Y,Z=Q.Z,W=Q.W;
    return {MakeShared<FJsonValueArray>(Array(FVector(1-2*(Y*Y+Z*Z),2*(X*Y+W*Z),2*(X*Z-W*Y)))),
        MakeShared<FJsonValueArray>(Array(FVector(2*(X*Y-W*Z),1-2*(X*X+Z*Z),2*(Y*Z+W*X)))),
        MakeShared<FJsonValueArray>(Array(FVector(2*(X*Z+W*Y),2*(Y*Z-W*X),1-2*(X*X+Y*Y))))};
}
TSharedPtr<FJsonObject> ObservedFrame(const FSourceSample& Sample,const FTransform& Space)
{
    FValues Points={MakeShared<FJsonValueArray>(Array(ProphecyThrow::FromUnrealPoint(Space.InverseTransformPosition(Sample.RootWorld))))},Q,Basis;
    Q.Add(MakeShared<FJsonValueArray>(FValues{MakeShared<FJsonValueNumber>(0),MakeShared<FJsonValueNumber>(0),MakeShared<FJsonValueNumber>(0),MakeShared<FJsonValueNumber>(1)}));Basis.Add(MakeShared<FJsonValueArray>(Axes(FQuat::Identity)));
    for(const auto& World:Sample.BodiesWorld)
    {
        const auto P=ToSolverBody(World,Space);const auto R=P.GetRotation();Points.Add(MakeShared<FJsonValueArray>(Array(P.GetLocation())));Basis.Add(MakeShared<FJsonValueArray>(Axes(R)));
        Q.Add(MakeShared<FJsonValueArray>(FValues{MakeShared<FJsonValueNumber>(R.X),MakeShared<FJsonValueNumber>(R.Y),MakeShared<FJsonValueNumber>(R.Z),MakeShared<FJsonValueNumber>(R.W)}));
    }
    auto Pose=MakeShared<FJsonObject>(),Frame=MakeShared<FJsonObject>();Pose->SetArrayField(TEXT("points"),Points);Pose->SetArrayField(TEXT("q"),Q);Pose->SetArrayField(TEXT("axes"),Basis);
    Frame->SetObjectField(TEXT("pose"),Pose);Frame->SetObjectField(TEXT("raw"),Pose);Frame->SetField(TEXT("root"),Points[0]);Frame->SetNumberField(TEXT("pelvisOffset"),0);Frame->SetNumberField(TEXT("influence"),0);
    Frame->SetArrayField(TEXT("rootHeading"),Array(ProphecyThrow::FromUnrealPoint(Space.InverseTransformVectorNoScale(Sample.HeadingWorld)).GetSafeNormal()));
    FValues Feet;for(int32 Side=0;Side<2;++Side){auto Foot=MakeShared<FJsonObject>();Foot->SetStringField(TEXT("side"),Side?TEXT("R"):TEXT("L"));Foot->SetStringField(TEXT("state"),TEXT("NN"));Foot->SetField(TEXT("target"),Points[Side?24:20]);Foot->SetField(TEXT("contact"),MakeShared<FJsonValueNull>());Foot->SetNumberField(TEXT("error"),0);Foot->SetNumberField(TEXT("penetration"),0);Feet.Add(MakeShared<FJsonValueObject>(Foot));}Frame->SetArrayField(TEXT("feet"),Feet);return Frame;
}
constexpr int32 Parents[]={-1,0,1,2,3,4,5,6,7,8,9,6,11,12,13,6,15,16,1,18,19,20,1,22,23,24};
constexpr const TCHAR* BodyNames[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
FCriticalSection LiveLane;
struct FWork
{
    FProphecyFootIKVM VM;
    TSharedPtr<FProphecyFootIKVM,ESPMode::ThreadSafe> Publication;
    FCriticalSection PublicationMutex;
    TAtomic<bool> Cancelled{false};
    TAtomic<uint64> LatestCommand{0},LatestConfiguration{0};
    uint64 PlannerConfiguration=MAX_uint64; // worker-owned; warmup has no planner
    bool Initialized=false;
    void Cancel(){Cancelled.Store(true);VM.Cancel();FScopeLock Lock(&PublicationMutex);if(Publication)Publication->Cancel();}
};
struct FResult
{
    ProphecyFootIKLiveGeometry::FSnapshot Scene;
    TMap<int32,FString> Frames;
    uint64 Command=0,Configuration=0,Geometry=0;
    int32 Through=-1,ImportedThrough=-1,ActualFrameCount=0,PayloadCharacters=0;
    double Seconds=0;
    double QueueMs=0,InitializeMs=0,ForecastMs=0,PayloadMs=0,PlannerMs=0,ExportMs=0;
    FProphecyFootIKForecast::FTiming ForecastTiming;
    FString Error,Diagnostics;
    bool Ready=false;
    TSharedPtr<FProphecyFootIKVM,ESPMode::ThreadSafe> Publication;
};
struct FRequest
{
    ProphecyFootIKLiveGeometry::FSnapshot Scene;
    FString Json;
    uint64 Command=0,Configuration=0,Geometry=0;
    int32 First=0,AcceptedThrough=-1;
    bool InitializeOnly=false;
    bool HistoryCheckpoint=false;
    TArray<TPair<int32,FActualText>> AcceptedFrames;
    TSharedPtr<FProphecyFootIKForecast,ESPMode::ThreadSafe> Forecaster;
    TSharedPtr<const FProphecyFootIKForecastInput,ESPMode::ThreadSafe> ForecastInput;
};
FResult Solve(const TSharedPtr<FWork,ESPMode::ThreadSafe>& W,const FRequest& R)
{
    FResult Out;Out.Command=R.Command;Out.Configuration=R.Configuration;Out.Geometry=R.Geometry;Out.Scene=R.Scene;
    const auto Obsolete=[&]{return W->Cancelled.Load()||(!R.InitializeOnly&&(W->LatestCommand.Load()!=R.Command||W->LatestConfiguration.Load()!=R.Configuration));};
    if(Obsolete())return Out;
    const double QueueStarted=FPlatformTime::Seconds();FScopeLock Lock(&LiveLane);if(Obsolete())return Out;
    Out.QueueMs=(FPlatformTime::Seconds()-QueueStarted)*1000;
    const double Started=FPlatformTime::Seconds();
    if(!W->Initialized)
    {
        W->Initialized=W->VM.Initialize([](const FString&,FString&,FString& Error){Error=TEXT("Live Foot IK requires the manager's real prospective NN source");return false;},Out.Error);
        if(!W->Initialized)return Out;
    }
    if(!W->Publication)
    {
        auto Publication=MakeShared<FProphecyFootIKVM,ESPMode::ThreadSafe>();
        if(!Publication->Initialize([](const FString&,FString&,FString& Error){Error=TEXT("Publication join never invokes a neural policy");return false;},Out.Error)||W->Cancelled.Load())return Out;
        FScopeLock PublicationLock(&W->PublicationMutex);if(W->Cancelled.Load())return Out;W->Publication=Publication;
    }
    Out.Publication=W->Publication;
    Out.InitializeMs=(FPlatformTime::Seconds()-Started)*1000;
    if(R.InitializeOnly){Out.Seconds=FPlatformTime::Seconds()-Started;return Out;}
    double StageStarted=FPlatformTime::Seconds();
    FString InputJson=R.Json,Reply,Source;
    if(R.Forecaster&&R.ForecastInput)
    {
        // Commands that changed while this speculative job ran can never be
        // published. Retire them between inferences, preserving the warm model
        // and its saved recurrence for the newest pending actual-history pair.
        if(!R.Forecaster->Predict(*R.ForecastInput,Source,Out.Error,&Out.ForecastTiming,Obsolete)||Obsolete())return Out;
    }
    Out.ForecastMs=(FPlatformTime::Seconds()-StageStarted)*1000;StageStarted=FPlatformTime::Seconds();
    // Every fragment was already produced by our JSON serializer or by the
    // validated solver. Preserve its exact numeric spelling instead of parsing
    // and rewriting thousands of body scalars just to form an envelope.
    if(!InputJson.StartsWith(TEXT("{"))||!InputJson.EndsWith(TEXT("}"))||(!Source.IsEmpty()&&(!Source.StartsWith(TEXT("{"))||!Source.EndsWith(TEXT("}")))))
    {Out.Error=TEXT("Invalid serialized live request");return Out;}
    // On the first solve, accept() ignores receipts before sourceStartTick.
    // Flat locomotion may have accumulated seconds of those records while its
    // exact identity branch needed no planner. Do not transport discarded past.
    // Existing models and explicit recovery checkpoints retain every receipt.
    const int32 FirstReceipt=W->PlannerConfiguration!=R.Configuration&&!R.HistoryCheckpoint?R.First:MIN_int32;
    int64 RequiredCharacters=int64(InputJson.Len())+Source.Len()+256;
    for(const auto& Sample:R.AcceptedFrames)
    {
        if(Sample.Key<FirstReceipt)continue;
        if(!Sample.Value||!Sample.Value->StartsWith(TEXT("{"))||!Sample.Value->EndsWith(TEXT("}"))){Out.Error=TEXT("Invalid serialized actual frame");return Out;}
        RequiredCharacters+=Sample.Value->Len()+64;
    }
    if(RequiredCharacters>MAX_int32){Out.Error=TEXT("Live request exceeds the string transport bound");return Out;}
    InputJson.Reserve(int32(RequiredCharacters));InputJson.LeftChopInline(1,EAllowShrinking::No);
    const auto Property=[&InputJson]{if(InputJson.Len()>1)InputJson.AppendChar(TEXT(','));};
    if(!Source.IsEmpty()){Property();InputJson.Append(TEXT("\"source\":"));InputJson.Append(Source);}
    if(R.AcceptedThrough>=0)
    {
        Property();InputJson.Appendf(TEXT("\"acceptedThrough\":%d,\"acceptedFrames\":["),R.AcceptedThrough);bool FirstFrame=true;
        for(const auto& Sample:R.AcceptedFrames)
        {
            if(Sample.Key<FirstReceipt)continue;
            if(W->Cancelled.Load())return Out;
            ++Out.ActualFrameCount;
            if(!FirstFrame)InputJson.AppendChar(TEXT(','));FirstFrame=false;
            InputJson.Appendf(TEXT("{\"tick\":%d,\"frame\":"),Sample.Key);InputJson.Append(*Sample.Value);InputJson.AppendChar(TEXT('}'));
        }
        InputJson.AppendChar(TEXT(']'));
        if(R.HistoryCheckpoint&&!R.AcceptedFrames.IsEmpty())
            InputJson.Appendf(TEXT(",\"acceptedHistoryCheckpoint\":{\"startTick\":%d,\"endTick\":%d}"),R.AcceptedFrames[0].Key,R.AcceptedFrames.Last().Key);
    }
    InputJson.AppendChar(TEXT('}'));Out.PayloadCharacters=InputJson.Len();Out.PayloadMs=(FPlatformTime::Seconds()-StageStarted)*1000;StageStarted=FPlatformTime::Seconds();
    if(Obsolete())return Out;
    W->PlannerConfiguration=R.Configuration;
    if(!W->VM.Command(InputJson,Reply,Out.Error)||W->Cancelled.Load())return Out;
    Out.PlannerMs=(FPlatformTime::Seconds()-StageStarted)*1000;
    // Explicit diagnostic only: one bounded, overwritten envelope, after the
    // timed solve. Retain the slowest real request instead of reconstructing it
    // from an output pose that lacks the actual accepted contact history.
    static double CapturedPlannerMs=0;
    if(FParse::Param(FCommandLine::Get(),TEXT("FootIKCaptureSlowPlan"))&&Out.PlannerMs>CapturedPlannerMs&&InputJson.Len()<=8*1024*1024)
    {
        const FString Path=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030/slow-live-request.json");
        if(FFileHelper::SaveStringToFile(InputJson,*Path,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))CapturedPlannerMs=Out.PlannerMs;
    }
    StageStarted=FPlatformTime::Seconds();
    const auto Status=Parse(Reply);if(!Status){Out.Error=TEXT("Invalid live Foot IK reply");return Out;}
    // The VM has consumed this exact displayed history even when the proposed
    // future is not yet safe. A finished request, not game age, acknowledges it.
    Out.ImportedThrough=R.AcceptedThrough;
    Out.Diagnostics=Reply;Status->TryGetBoolField(TEXT("ready"),Out.Ready);
    if(Out.Ready)
    {
        double Through=-1;Status->TryGetNumberField(TEXT("throughTick"),Through);Out.Through=int32(Through);
        const int32 Count=FMath::Clamp(Out.Through-R.First+1,0,240);
        if(Count&&!W->VM.Command(FString::Printf(TEXT("{\"op\":\"liveFrameTexts\",\"start\":%d,\"count\":%d}"),R.First,Count),Reply,Out.Error))return Out;
        if(W->Cancelled.Load())return Out;
        FValues Frames;if(Count&&(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Reply),Frames)||Frames.Num()!=Count))
        {Out.Error=TEXT("Live Foot IK did not return its prospective frames");return Out;}
        for(int32 I=0;I<Frames.Num();++I)
        {
            FString Frame;if(!Frames[I]->TryGetString(Frame)||!Frame.StartsWith(TEXT("{"))||!Frame.EndsWith(TEXT("}"))){Out.Error=TEXT("Invalid serialized live Foot IK frame");return Out;}
            Out.Frames.Add(R.First+I,MoveTemp(Frame));
        }
    }
    Out.ExportMs=(FPlatformTime::Seconds()-StageStarted)*1000;Out.Seconds=FPlatformTime::Seconds()-Started;return Out;
}
struct FState
{
    TSharedPtr<FWork,ESPMode::ThreadSafe> Work=MakeShared<FWork,ESPMode::ThreadSafe>();
    TFuture<FResult> Future;
    TOptional<FRequest> Pending;
    TMap<int32,FString> Frames;
    TMap<int32,FActualText> AcceptedFrames;
    FString Epoch=FGuid::NewGuid().ToString(),Settings=TEXT("{\"enabled\":true,\"terrain\":\"stairs\",\"gait\":\"walk\"}"),Terrain;
    FTransform Space=FTransform::Identity;
    FProphecyFootIKLiveState Status;
    uint64 LatestCommand=0,CacheCommand=0,Configuration=0,LatestGeometry=0,CacheGeometry=0;
    int32 AcceptedThrough=-1,LatestTick=-1,WorkerImportedThrough=-1;
    int32 ObservedTick=-1;
    int32 CompletedJobs=0,DiscardedJobs=0,JoinAttempts=0,JoinedFrames=0,VerifiedIdentityFrames=0,JoinTick=-1;
    FString JoinMiss,LastWorkerDiagnostics;
    FSourceSample LastObserved;
    TSharedPtr<FProphecyFootIKForecast,ESPMode::ThreadSafe> Forecaster;
    TSharedPtr<FProphecyFootIKVM,ESPMode::ThreadSafe> Publication;
    bool HasSpace=false,NoInfluence=false;
    ProphecyFootIKLiveGeometry::FSnapshot LatestScene,CacheScene;
    ~FState()
    {
        if(Forecaster)Forecaster->Cancel();Work->Cancel();
        // Idle/completed work can otherwise own the final V8 references on GT.
        // Do not wait for an in-flight future on the retirement queue: its
        // producer already retains the worker and releases it after cancellation.
        FProphecyFootIKPreparation::Retire([RetiredWork=MoveTemp(Work),RetiredPublication=MoveTemp(Publication),RetiredFuture=MoveTemp(Future)]() mutable
        {RetiredFuture=TFuture<FResult>();RetiredPublication.Reset();RetiredWork.Reset();});
    }
};
TMap<TWeakObjectPtr<AProphecyAgent>,TUniquePtr<FState>> States;
TMap<TWeakObjectPtr<AProphecyAgent>,FString> Configurations;
FDelegateHandle Cleanup;
void RefreshCleanup()
{
    if(States.IsEmpty()){FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();return;}
    if(!Cleanup.IsValid())Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        for(auto I=States.CreateIterator();I;++I)if(!I.Key().IsValid()||I.Key()->GetWorld()==W){if(auto* A=I.Key().Get())ProphecyFootIKGame::Remove(A);I.RemoveCurrent();}
        for(auto I=Configurations.CreateIterator();I;++I)if(!I.Key().IsValid()||I.Key()->GetWorld()==W)I.RemoveCurrent();
        RefreshCleanup();
    });
}
void PruneAcknowledgedHistory(FState& S)
{
    // Keep one second for publication/contact joins AND every frame the worker
    // has not imported yet, up to a bounded10s backlog. Beyond that, Dispatch
    // sends an explicit authoritative checkpoint, never an ordinary gapped list.
    const int32 FirstNeeded=FMath::Max(S.AcceptedThrough-1200,FMath::Min(S.AcceptedThrough-120,S.WorkerImportedThrough+1));
    for(auto It=S.AcceptedFrames.CreateIterator();It;++It)if(It.Key()<FirstNeeded)It.RemoveCurrent();
}
void Dispatch(FState& S)
{
    if(S.Future.IsValid()||!S.Pending.IsSet())return;
    FRequest R=MoveTemp(S.Pending.GetValue());S.Pending.Reset();
    // The accepted boundary may advance while an older job runs. Capture it at
    // actual dispatch, not when this replaceable pending request was created.
    if(!R.InitializeOnly&&S.AcceptedThrough>=0)
    {
        R.AcceptedThrough=S.AcceptedThrough;
        TArray<int32> Ticks;S.AcceptedFrames.GetKeys(Ticks);Ticks.Sort();R.AcceptedFrames.Reserve(Ticks.Num());
        R.HistoryCheckpoint=!Ticks.IsEmpty()&&Ticks[0]>S.WorkerImportedThrough+1;
        // The worker already owns acknowledged history. Retain its last60Hz
        // pair in case this tick was replaced after dispatch; every newer
        // actual frame remains mandatory. A capped checkpoint stays complete.
        for(int32 Tick:Ticks)if(R.HistoryCheckpoint||Tick>=S.WorkerImportedThrough-2)R.AcceptedFrames.Emplace(Tick,S.AcceptedFrames[Tick]);
    }
    // Embedded V8/solver recursion requires more than UE's128KB pool stack.
    // The temporary worker self-retires; no resident thread survives disable.
    // Cold preparation can yield to the editor. A running prediction has a
    // finite gameplay deadline; starving its single serial lane also discards
    // all that work once the predicted contact has passed.
    const EThreadPriority Priority=R.InitializeOnly?TPri_BelowNormal:TPri_Normal;
    auto Work=S.Work;S.Future=AsyncThread([Work,R=MoveTemp(R)]{return Solve(Work,R);},1024*1024,Priority);S.Status.Preparing=true;
}
void WarmVMs(FState& S)
{
    FString Terrain;const auto Settings=Parse(S.Settings);
    if(Settings&&Settings->TryGetStringField(TEXT("terrain"),Terrain)&&Terrain==TEXT("incline"))return;
    // Compile both contexts before taking the first real forecast snapshot.
    // Warming does not advance NN, root, planner history or the game clock.
    FRequest Request;Request.InitializeOnly=true;Request.Configuration=S.Configuration;
    S.Pending=MoveTemp(Request);Dispatch(S);
}
void Poll(FState& S)
{
    if(S.Future.IsValid()&&S.Future.IsReady())
    {
        FResult R=S.Future.Get();S.Future=TFuture<FResult>();S.Status.SolveMilliseconds=float(R.Seconds*1000);if(R.Publication)S.Publication=R.Publication;
        ++S.CompletedJobs;
        auto Timing=MakeShared<FJsonObject>();Timing->SetNumberField(TEXT("queueMs"),R.QueueMs);Timing->SetNumberField(TEXT("initializeMs"),R.InitializeMs);Timing->SetNumberField(TEXT("forecastMs"),R.ForecastMs);Timing->SetNumberField(TEXT("payloadMs"),R.PayloadMs);Timing->SetNumberField(TEXT("plannerMs"),R.PlannerMs);Timing->SetNumberField(TEXT("exportMs"),R.ExportMs);
        Timing->SetNumberField(TEXT("completedAtTick"),S.LatestTick);Timing->SetNumberField(TEXT("throughTick"),R.Through);Timing->SetNumberField(TEXT("importedThrough"),R.ImportedThrough);Timing->SetNumberField(TEXT("command"),double(R.Command));Timing->SetNumberField(TEXT("geometry"),double(R.Geometry));Timing->SetBoolField(TEXT("ready"),R.Ready);Timing->SetStringField(TEXT("error"),R.Error);
        Timing->SetNumberField(TEXT("actualFrameCount"),R.ActualFrameCount);Timing->SetNumberField(TEXT("payloadCharacters"),R.PayloadCharacters);
        const auto& N=R.ForecastTiming.NN;
        Timing->SetNumberField(TEXT("nnOrtMs"),N.OrtSeconds*1000);Timing->SetNumberField(TEXT("nnTensorMs"),N.TensorSeconds*1000);Timing->SetNumberField(TEXT("nnPoseMs"),N.PoseSeconds*1000);Timing->SetNumberField(TEXT("nnSerializeMs"),N.SerializeSeconds*1000);Timing->SetNumberField(TEXT("nnParseMs"),N.ParseSeconds*1000);Timing->SetNumberField(TEXT("nnInitializeMs"),N.InitializeSeconds*1000);Timing->SetNumberField(TEXT("nnTotalMs"),N.TotalSeconds*1000);Timing->SetNumberField(TEXT("nnInferences"),N.Inferences);
        Timing->SetNumberField(TEXT("forecastRequestMs"),R.ForecastTiming.RequestSeconds*1000);Timing->SetNumberField(TEXT("forecastDecodeMs"),R.ForecastTiming.DecodeSeconds*1000);Timing->SetNumberField(TEXT("forecastPostprocessMs"),R.ForecastTiming.PostprocessSeconds*1000);Timing->SetNumberField(TEXT("forecastSerializeMs"),R.ForecastTiming.SerializeSeconds*1000);S.LastWorkerDiagnostics=Json(Timing);
        if(R.Configuration==S.Configuration&&R.ImportedThrough>=0)
        {S.WorkerImportedThrough=FMath::Max(S.WorkerImportedThrough,R.ImportedThrough);PruneAcknowledgedHistory(S);}
        // Changed commands/settings never publish an obsolete prospective tail.
        if(R.Command==S.LatestCommand&&R.Configuration==S.Configuration&&
            (R.Geometry==S.LatestGeometry||ProphecyFootIKLiveGeometry::Compatible(R.Scene,S.LatestScene)))
        {
            S.Status.Error=R.Error;S.Status.DiagnosticsJson=R.Diagnostics;
            if(R.Error.IsEmpty()&&R.Ready)
            {
                // Publication uses liveJoin against the actual current NN. A
                // full-body equality gate here would starve while time moves.
                S.Frames=MoveTemp(R.Frames);S.CacheCommand=R.Command;S.CacheGeometry=S.LatestGeometry;S.CacheScene=MoveTemp(R.Scene);
                S.Status.PreparedThroughFrame=R.Through/2;S.Status.Ready=true;
            }
        }
        else ++S.DiscardedJobs;
    }
    Dispatch(S);S.Status.Preparing=S.Future.IsValid()||S.Pending.IsSet();
}
bool ReadPose(const TSharedPtr<FJsonObject>& Frame,const TCHAR* Key,const FTransform& Space,TArray<FTransform>& Out,FString& Error)
{
    const TSharedPtr<FJsonObject>* P=nullptr;const FValues *Points=nullptr,*Quats=nullptr;
    if(!Frame->TryGetObjectField(Key,P)||!(*P)->TryGetArrayField(TEXT("points"),Points)||!(*P)->TryGetArrayField(TEXT("q"),Quats)||Points->Num()!=26||Quats->Num()!=26)
    {Error=TEXT("Incomplete live Foot IK body pose");return false;}
    Out.SetNum(26);
    for(int32 I=0;I<26;++I)
    {
        const auto& V=(*Points)[I]->AsArray();const auto& Q=(*Quats)[I]->AsArray();
        if(V.Num()!=3||Q.Num()!=4){Error=TEXT("Invalid live Foot IK transform");return false;}
        Out[I]=ProphecyThrow::ToUnreal(FTransform(FQuat(Q[0]->AsNumber(),Q[1]->AsNumber(),Q[2]->AsNumber(),Q[3]->AsNumber()),FVector(V[0]->AsNumber(),V[1]->AsNumber(),V[2]->AsNumber())))*Space;
        if(Out[I].ContainsNaN()){Error=TEXT("Nonfinite live Foot IK result");return false;}
    }
    return true;
}
}

bool Enabled(const AProphecyAgent* A){return States.Contains(const_cast<AProphecyAgent*>(A));}
bool AnyEnabled(){return !States.IsEmpty();}
bool HasCallbacks(){return Cleanup.IsValid();}
FString Settings(const AProphecyAgent* A)
{
    if(const auto* State=States.Find(const_cast<AProphecyAgent*>(A)))return (*State)->Settings;
    if(const auto* Configured=Configurations.Find(const_cast<AProphecyAgent*>(A)))return *Configured;
    return TEXT("{\"enabled\":true,\"terrain\":\"stairs\",\"gait\":\"walk\"}");
}
void Remove(AProphecyAgent* A){ProphecyFootIKGame::Remove(A);States.Remove(A);RefreshCleanup();}
bool Enable(AProphecyAgent* A,bool Value,FString& Error)
{
    Error.Reset();if(!Value){Remove(A);return true;}if(Enabled(A))return true;
    if(!IsValid(A)||!A->GetWorld()||!A->GetWorld()->IsGameWorld()||!A->HasValidAgentHandle())
    {Error=TEXT("A registered game agent is required for live Foot IK");return false;}
    if(ProphecyFootIK::Active(A)){Error=TEXT("Stop the Foot IK reference course before enabling the live controller");return false;}
    auto S=MakeUnique<FState>();if(const auto* Settings=Configurations.Find(A))S->Settings=*Settings;S->Status.Enabled=true;
    WarmVMs(*S);States.Add(A,MoveTemp(S));RefreshCleanup();return true;
}
bool Configure(AProphecyAgent* A,const FString& Text,FString& Error)
{
    Error.Reset();auto Settings=Parse(Text.IsEmpty()?TEXT("{\"enabled\":true,\"terrain\":\"stairs\",\"gait\":\"walk\"}"):Text);
    if(!IsValid(A)||!Settings){Error=TEXT("A valid agent and JSON settings object are required");return false;}
    Settings->SetBoolField(TEXT("enabled"),true);const FString Serialized=Json(Settings);
    Configurations.Add(A,Serialized);
    if(States.Contains(A))
    {
        // Configuration starts a complete epoch. Old forecasts retain only
        // their canceled worker-owned state and cannot publish into this one.
        // The manager adapter reacquires the actual current/history pair.
        ProphecyFootIKGame::Remove(A);States.Remove(A);
        auto Next=MakeUnique<FState>();Next->Settings=Serialized;Next->Status.Enabled=true;WarmVMs(*Next);States.Add(A,MoveTemp(Next));RefreshCleanup();
    }
    return true;
}
bool Status(const AProphecyAgent* A,FProphecyFootIKLiveState& Out)
{if(ProphecyFootIKSurface::Status(A,Out))return true;auto* S=States.Find(const_cast<AProphecyAgent*>(A));if(!S){Out={};return false;}Poll(**S);Out=(*S)->Status;Out.Preparing=Out.Preparing||ProphecyFootIKGame::Preparing(A);const FString GameError=ProphecyFootIKGame::Error(A);if(!GameError.IsEmpty())Out.Error=GameError;return true;}
bool SourceReady(AProphecyAgent* A,FString& Error)
{
    Error.Reset();auto* Found=States.Find(A);if(!Found){Error=TEXT("Live Foot IK is disabled");return false;}
    auto& S=**Found;Poll(S);Error=S.Status.Error;return Error.IsEmpty()&&S.Publication.IsValid();
}
void InvalidatePrediction(AProphecyAgent* A)
{
    auto* Found=States.Find(A);if(!Found)return;auto& S=**Found;
    ++S.Configuration;S.Work->LatestConfiguration.Store(S.Configuration);S.Epoch=FGuid::NewGuid().ToString();S.Pending.Reset();S.Frames.Reset();S.AcceptedFrames.Reset();
    S.AcceptedThrough=S.LatestTick=S.WorkerImportedThrough=S.ObservedTick=-1;S.HasSpace=false;S.NoInfluence=false;
    S.Status.Ready=false;S.Status.PreparedThroughFrame=-1;
}
bool TerrainExitReady(AProphecyAgent* A,int32 Tick,const FString& FrameJson,FString& Error)
{
    Error.Reset();auto* Found=States.Find(A);if(!Found)return false;auto& S=**Found;
    if(!S.Publication||S.Terrain.IsEmpty())return false;
    const auto Frame=Parse(FrameJson),Terrain=Parse(S.Terrain);if(!Frame||!Terrain)return false;
    auto Request=MakeShared<FJsonObject>();Request->SetStringField(TEXT("op"),TEXT("liveExitReady"));
    Request->SetObjectField(TEXT("frame"),Frame);Request->SetObjectField(TEXT("terrain"),Terrain);Request->SetNumberField(TEXT("currentTick"),Tick);
    FString Reply;if(!S.Publication->Command(Json(Request),Reply,Error))return false;
    const auto Result=Parse(Reply);bool Ready=false;return Result&&Result->TryGetBoolField(TEXT("eligible"),Ready)&&Ready;
}
void PublishContinuation(AProphecyAgent* A,int32 Tick)
{
    auto* Found=States.Find(A);if(!Found)return;auto& S=**Found;
    S.Status.AppliedFrame=Tick/2;S.Status.Ready=true;
    S.Status.DiagnosticsJson=TEXT("{\"terrainExitContinuation\":true}");
}
FString DiagnosticSnapshot(const AProphecyAgent* A)
{
    const auto* Found=States.Find(const_cast<AProphecyAgent*>(A));if(!Found)return TEXT("{}");const auto& S=**Found;auto O=MakeShared<FJsonObject>();
    O->SetNumberField(TEXT("latestTick"),S.LatestTick);O->SetNumberField(TEXT("acceptedThrough"),S.AcceptedThrough);O->SetNumberField(TEXT("workerImportedThrough"),S.WorkerImportedThrough);O->SetNumberField(TEXT("retainedActualFrames"),S.AcceptedFrames.Num());O->SetNumberField(TEXT("cachedFrames"),S.Frames.Num());
    O->SetNumberField(TEXT("completedJobs"),S.CompletedJobs);O->SetNumberField(TEXT("discardedJobs"),S.DiscardedJobs);O->SetNumberField(TEXT("joinAttempts"),S.JoinAttempts);O->SetNumberField(TEXT("joinedFrames"),S.JoinedFrames);O->SetNumberField(TEXT("joinTick"),S.JoinTick);O->SetStringField(TEXT("joinMiss"),S.JoinMiss);
    O->SetNumberField(TEXT("verifiedIdentityFrames"),S.VerifiedIdentityFrames);
    O->SetNumberField(TEXT("terrainExits"),ProphecyFootIKGame::TerrainExits(A));O->SetBoolField(TEXT("returning"),ProphecyFootIKGame::Returning(A));O->SetBoolField(TEXT("identityTerrain"),S.NoInfluence);
    O->SetNumberField(TEXT("latestCommand"),double(S.LatestCommand));O->SetNumberField(TEXT("cacheCommand"),double(S.CacheCommand));O->SetNumberField(TEXT("latestGeometry"),double(S.LatestGeometry));O->SetNumberField(TEXT("cacheGeometry"),double(S.CacheGeometry));
    if(auto Last=Parse(S.LastWorkerDiagnostics))O->SetObjectField(TEXT("lastWorker"),Last);if(auto Last=Parse(S.Status.DiagnosticsJson))O->SetObjectField(TEXT("lastReply"),Last);return Json(O);
}
bool Submit(AProphecyAgent* A,const FInput& I,FString& Error)
{
    Error.Reset();auto* Found=States.Find(A);if(!Found){Error=TEXT("Live Foot IK is disabled");return false;}auto& S=**Found;
    auto Source=Parse(I.SourceJson),Terrain=Parse(I.TerrainJson);const FValues* Poses=nullptr;const bool Predict=I.Forecaster&&I.ForecastInput;
    const int32 SourceStart=Predict?I.ForecastInput->CurrentTick-4:I.SourceStartTick;
    const bool SourceValid=Predict?(I.ForecastInput->CurrentTick==I.CurrentTick&&I.CurrentTick%4==0&&I.ForecastInput->RootWorldWindow.Num()==10&&I.ForecastInput->CourseWorld.Equals(I.CourseWorld,1.e-8)):(Source&&Source->TryGetArrayField(TEXT("poses"),Poses)&&Poses->Num()>=2&&Poses->Num()<=241&&I.CurrentTick<=SourceStart+(Poses->Num()-1)*4);
    if(!SourceValid||!Terrain||I.CurrentTick<0||SourceStart<0||SourceStart%4||SourceStart>I.CurrentTick||I.CourseWorld.ContainsNaN()||!I.CourseWorld.GetScale3D().Equals(FVector::OneVector,1.e-8))
    {Error=TEXT("Live Foot IK needs a bounded real NN source covering this tick and a unit-scale fixed course frame");return false;}
    if(Predict&&S.Forecaster&&S.Forecaster!=I.Forecaster){Error=TEXT("Re-enable live Foot IK before replacing its forecast model");return false;}
    if(S.HasSpace&&!S.Space.Equals(I.CourseWorld,1.e-8)){Error=TEXT("Disable/re-enable live Foot IK before changing its course coordinate frame");return false;}
    auto InitialHistory=I.InitialHistoryJson.IsEmpty()?TSharedPtr<FJsonObject>():Parse(I.InitialHistoryJson);
    if(!S.HasSpace&&!InitialHistory&&Predict){FString History;if(!BuildInitialHistory(SourceStart,I.CurrentTick,I.ForecastInput->Previous,I.ForecastInput->Current,I.CourseWorld,History,Error))return false;InitialHistory=Parse(History);}
    if(!S.HasSpace&&!InitialHistory){Error=TEXT("First live Foot IK source requires the actual displayed current and previous pose pair");return false;}
    if(I.CurrentTick<S.LatestTick){Error=TEXT("Live Foot IK cannot rewind the game clock");return false;}
    const bool FirstInput=!S.HasSpace;
    S.HasSpace=true;S.Space=I.CourseWorld;S.LatestTick=I.CurrentTick;S.LatestCommand=I.CommandRevision;S.LatestGeometry=I.GeometryRevision;
    S.Work->LatestCommand.Store(S.LatestCommand);S.Work->LatestConfiguration.Store(S.Configuration);
    if(FirstInput)
    {
        // This owner has no displayed history before its source epoch. A
        // nonzero starting tick is not a discarded asynchronous backlog.
        S.WorkerImportedThrough=SourceStart-1;
        for(const auto& Pair:{TPair<const TCHAR*,const TCHAR*>(TEXT("previous"),TEXT("previousTick")),TPair<const TCHAR*,const TCHAR*>(TEXT("current"),TEXT("currentTick"))})
        {
            const TSharedPtr<FJsonObject>* Pose=nullptr;double Tick=0;auto Wrapper=MakeShared<FJsonObject>();TArray<FTransform> World;
            if(!InitialHistory->TryGetObjectField(Pair.Key,Pose)||!InitialHistory->TryGetNumberField(Pair.Value,Tick)){Error=TEXT("Invalid initial actual history");S.HasSpace=false;return false;}
            Wrapper->SetObjectField(TEXT("pose"),*Pose);if(!ReadPose(Wrapper,TEXT("pose"),S.Space,World,Error)){S.HasSpace=false;return false;}
            FSourceSample Actual;Actual.RootWorld=World[0].GetLocation();for(int32 J=1;J<26;++J)Actual.BodiesWorld.Add(World[J]);
            if(Predict)Actual.HeadingWorld=FCString::Strcmp(Pair.Key,TEXT("previous"))==0?I.ForecastInput->Previous.HeadingWorld:I.ForecastInput->Current.HeadingWorld;
            else
            {
                const FValues* Heading=nullptr;
                if((*Pose)->TryGetArrayField(TEXT("rootHeading"),Heading)&&Heading->Num()==3)
                    Actual.HeadingWorld=S.Space.TransformVectorNoScale(ProphecyThrow::ToUnrealPoint(FVector((*Heading)[0]->AsNumber(),(*Heading)[1]->AsNumber(),(*Heading)[2]->AsNumber()))).GetSafeNormal();
            }
            if(!ObserveActualPose(A,int32(Tick),Actual,Error)){S.HasSpace=false;return false;}
        }
    }
    S.LatestScene=ProphecyFootIKLiveGeometry::Read(Terrain);
    if(S.CacheGeometry!=I.GeometryRevision&&ProphecyFootIKLiveGeometry::Compatible(S.CacheScene,S.LatestScene))S.CacheGeometry=I.GeometryRevision;
    if(S.CacheCommand!=I.CommandRevision||S.CacheGeometry!=I.GeometryRevision){S.Frames.Reset();S.Status.Ready=false;}
    Poll(S);auto Request=MakeShared<FJsonObject>();Request->SetStringField(TEXT("op"),TEXT("liveEvaluate"));Request->SetStringField(TEXT("epoch"),S.Epoch);
    Request->SetNumberField(TEXT("currentTick"),I.CurrentTick);Request->SetNumberField(TEXT("sourceStartTick"),SourceStart);Request->SetNumberField(TEXT("time"),I.CurrentTick/120.);
    Request->SetArrayField(TEXT("origin"),Array(FVector::ZeroVector));
    Request->SetNumberField(TEXT("commandRevision"),double(I.CommandRevision));Request->SetNumberField(TEXT("geometryRevision"),double(I.GeometryRevision));
    if(Terrain->HasField(TEXT("rootRows")))Terrain->SetNumberField(TEXT("rootStartTick"),SourceStart);
    S.Terrain=Json(Terrain);
    // This is the canonical planner's exact noInfluence branch. If every
    // finite tread is at every navigation row's height, K returns the actual
    // NN pose unchanged. There is no reason to run37 speculative inferences
    // and two whole-course IK passes to rediscover that identity result.
    S.NoInfluence=UniformNavigationTerrain(Terrain);
    if(S.NoInfluence){S.Pending.Reset();return true;}
    if(Source&&!Predict)Request->SetObjectField(TEXT("source"),Source);Request->SetObjectField(TEXT("terrain"),Terrain);Request->SetObjectField(TEXT("settings"),Parse(S.Settings));
    if(InitialHistory)Request->SetObjectField(TEXT("initialHistory"),InitialHistory);
    FValues Rig;for(int32 P:Parents)Rig.Add(MakeShared<FJsonValueNumber>(P));Request->SetArrayField(TEXT("parents"),Rig);
    FRequest R;R.Scene=S.LatestScene;R.Json=Json(Request);R.First=FMath::Max(SourceStart,I.CurrentTick-4);R.Command=I.CommandRevision;R.Geometry=I.GeometryRevision;R.Configuration=S.Configuration;R.Forecaster=I.Forecaster;R.ForecastInput=I.ForecastInput;
    if(Predict)S.Forecaster=I.Forecaster;
    S.Pending=MoveTemp(R);Dispatch(S);return true;
}
bool Consume(AProphecyAgent* A,int32 Tick,uint64 Revision,FOutput& Out,FString& Error)
{
    Error.Reset();auto* Found=States.Find(A);if(!Found)return false;auto& S=**Found;Poll(S);
    if(Revision!=S.CacheCommand||Revision!=S.LatestCommand||S.CacheGeometry!=S.LatestGeometry||Tick<S.AcceptedThrough)return false;
    const FString* Text=S.Frames.Find(Tick);if(!Text)return false;auto Frame=Parse(*Text);FOutput Result;Result.Tick=Tick;Result.CommandRevision=Revision;
    if(!Frame||!ReadPose(Frame,TEXT("pose"),S.Space,Result.PoseWorld,Error)||!ReadPose(Frame,TEXT("raw"),S.Space,Result.RawWorld,Error))return false;
    Result.DiagnosticsJson=*Text;Out=MoveTemp(Result);
    // Retain the exact displayed plan while a newer candidate is being solved.
    // Its material contacts must not be replaced by the candidate at commit.
    const int32 First=S.AcceptedThrough<0?Tick:FMath::Max(S.AcceptedThrough+1,Tick-4);
    for(int32 I=First;I<=Tick;++I)if(const FString* Accepted=S.Frames.Find(I))S.AcceptedFrames.Add(I,MakeShared<const FString,ESPMode::ThreadSafe>(*Accepted));
    S.AcceptedThrough=Tick;S.Status.AppliedFrame=Tick/2;
    S.ObservedTick=Tick;S.LastObserved.RootWorld=Out.PoseWorld[0].GetLocation();S.LastObserved.BodiesWorld.Reset(25);for(int32 I=1;I<26;++I)S.LastObserved.BodiesWorld.Add(Out.PoseWorld[I]);
    PruneAcknowledgedHistory(S);
    for(auto It=S.Frames.CreateIterator();It;++It)if(It.Key()<Tick-4)It.RemoveCurrent();return true;
}
bool ConsumeJoined(AProphecyAgent* A,int32 Tick,uint64 Revision,const FSourceSample& PreviousActual,const FSourceSample& CurrentActual,FOutput& Out,FString& Error)
{
    Error.Reset();auto* Found=States.Find(A);if(!Found)return false;auto& S=**Found;Poll(S);
    ++S.JoinAttempts;S.JoinTick=Tick;
    if(!S.Publication){S.JoinMiss=TEXT("publication VM is preparing");return false;}
    if(Revision!=S.LatestCommand){S.JoinMiss=TEXT("command revision mismatch");return false;}
    if(Tick<S.AcceptedThrough){S.JoinMiss=TEXT("requested tick precedes actual history");return false;}
    const auto* Text=S.Frames.Find(Tick);
    for(const auto* Actual:{&PreviousActual,&CurrentActual})
    {
        if(Actual->BodiesWorld.Num()!=25||Actual->RootWorld.ContainsNaN()){Error=TEXT("Publication join requires actual60Hz pose history");return false;}
        for(const auto& Body:Actual->BodiesWorld)if(Body.ContainsNaN()){Error=TEXT("Nonfinite live publication pose");return false;}
    }
    if(S.NoInfluence)
    {
        if(!ObserveActualPose(A,Tick,CurrentActual,Error))return false;
        FOutput Result;Result.Tick=Tick;Result.CommandRevision=Revision;Result.PoseWorld.Add(FTransform(CurrentActual.RootWorld));Result.PoseWorld.Append(CurrentActual.BodiesWorld);Result.RawWorld=Result.PoseWorld;
        Result.DiagnosticsJson=Json(ObservedFrame(CurrentActual,S.Space));Out=MoveTemp(Result);
        ++S.JoinedFrames;S.JoinMiss.Reset();S.Status.AppliedFrame=Tick/2;S.Status.PreparedThroughFrame=Tick/2;S.Status.Ready=true;return true;
    }
    if(Revision!=S.CacheCommand||S.CacheGeometry!=S.LatestGeometry||!Text)
    {
        S.JoinMiss=Revision!=S.CacheCommand?TEXT("command revision mismatch"):
            S.CacheGeometry!=S.LatestGeometry?TEXT("geometry revision mismatch"):
            Tick>S.Status.PreparedThroughFrame*2?TEXT("forecast tail expired"):TEXT("requested frame is absent from cache");
        // This only verifies the raw fallback already displayed without a
        // usable candidate. Never replace an available correction or a return.
        // NN foot states alone are insufficient: canonical recovery can still
        // have a nonzero weight, so the preceding actual target must be raw.
        if(!S.LatestScene.Valid||ProphecyFootIKGame::Returning(A))return false;
        const auto* PriorText=S.AcceptedFrames.Find(Tick-2);const auto Prior=PriorText?Parse(**PriorText):nullptr;
        const TSharedPtr<FJsonObject> *PriorPose=nullptr,*PriorRaw=nullptr;const FValues* PriorFeet=nullptr;double PriorInfluence=0;
        if(!Prior||!Prior->TryGetObjectField(TEXT("pose"),PriorPose)||!Prior->TryGetObjectField(TEXT("raw"),PriorRaw)||
            !Prior->TryGetArrayField(TEXT("feet"),PriorFeet)||PriorFeet->Num()!=2||Json(*PriorPose)!=Json(*PriorRaw)||
            (Prior->TryGetNumberField(TEXT("influence"),PriorInfluence)&&PriorInfluence!=0))return false;
        const auto Terrain=Parse(S.Terrain);if(!Terrain)return false;
        auto CurrentFrame=ObservedFrame(CurrentActual,S.Space);auto Request=MakeShared<FJsonObject>(),Coverage=MakeShared<FJsonObject>();
        Request->SetStringField(TEXT("op"),TEXT("liveIdentity"));Request->SetObjectField(TEXT("current"),CurrentFrame->GetObjectField(TEXT("pose")));
        Request->SetObjectField(TEXT("terrain"),Terrain);Request->SetArrayField(TEXT("previousFeet"),*PriorFeet);
        const auto& Query=S.LatestScene.WorldQuery;
        Coverage->SetArrayField(TEXT("center"),Array(ProphecyThrow::FromUnrealPoint(S.Space.InverseTransformPosition(Query.GetCenter()))));
        Coverage->SetArrayField(TEXT("extent"),Array(Query.GetExtent()*.01));FValues Axes,Rig,Names;
        for(const FVector Axis:{FVector::ForwardVector,FVector::RightVector,FVector::UpVector})
            Axes.Add(MakeShared<FJsonValueArray>(Array(ProphecyThrow::FromUnrealPoint(S.Space.InverseTransformVectorNoScale(Axis*100.)))));
        Coverage->SetArrayField(TEXT("axes"),Axes);Request->SetObjectField(TEXT("coverage"),Coverage);
        for(int32 P:Parents)Rig.Add(MakeShared<FJsonValueNumber>(P));Names.Add(MakeShared<FJsonValueString>(TEXT("root")));
        for(const auto* Name:BodyNames)Names.Add(MakeShared<FJsonValueString>(Name));Request->SetArrayField(TEXT("parents"),Rig);Request->SetArrayField(TEXT("names"),Names);
        FString Reply;if(!S.Publication->Command(Json(Request),Reply,Error))return false;const auto Result=Parse(Reply);bool Identity=false;
        if(!Result||!Result->TryGetBoolField(TEXT("identity"),Identity)||!Identity)return false;
        if(!ObserveActualPose(A,Tick,CurrentActual,Error))return false;
        FOutput IdentityOutput;IdentityOutput.Tick=Tick;IdentityOutput.CommandRevision=Revision;
        IdentityOutput.PoseWorld.Add(FTransform(CurrentActual.RootWorld));IdentityOutput.PoseWorld.Append(CurrentActual.BodiesWorld);IdentityOutput.RawWorld=IdentityOutput.PoseWorld;
        CurrentFrame->SetBoolField(TEXT("verifiedRawFallback"),true);IdentityOutput.DiagnosticsJson=Json(CurrentFrame);Out=MoveTemp(IdentityOutput);
        ++S.VerifiedIdentityFrames;S.JoinMiss.Reset();S.Status.AppliedFrame=Tick/2;S.Status.Ready=true;S.Status.DiagnosticsJson=Out.DiagnosticsJson;return true;
    }
    // A compatible moving broadphase may extend beyond the old prediction's
    // collision coverage. Never publish its pose outside that original query.
    if(S.CacheScene.Valid)
        for(const auto& Body:CurrentActual.BodiesWorld)
            if(!S.CacheScene.WorldQuery.IsInsideOrOn(Body.GetLocation()))
            {S.JoinMiss=TEXT("actual pose left prediction collision coverage");return false;}
    auto Candidate=Parse(*Text),CurrentFrame=ObservedFrame(CurrentActual,S.Space),PreviousFrame=ObservedFrame(PreviousActual,S.Space);auto Request=MakeShared<FJsonObject>();
    if(!Candidate){Error=TEXT("Invalid live Foot IK candidate");return false;}
    Request->SetStringField(TEXT("op"),TEXT("liveJoin"));Request->SetObjectField(TEXT("candidate"),Candidate);Request->SetObjectField(TEXT("current"),CurrentFrame->GetObjectField(TEXT("pose")));Request->SetObjectField(TEXT("previous"),PreviousFrame->GetObjectField(TEXT("pose")));
    if(S.CacheScene.Valid)
    {
        auto Coverage=MakeShared<FJsonObject>();const auto& Query=S.CacheScene.WorldQuery;
        Coverage->SetArrayField(TEXT("center"),Array(ProphecyThrow::FromUnrealPoint(S.Space.InverseTransformPosition(Query.GetCenter()))));
        Coverage->SetArrayField(TEXT("extent"),Array(Query.GetExtent()*.01));FValues Axes;
        for(const FVector Axis:{FVector::ForwardVector,FVector::RightVector,FVector::UpVector})
            Axes.Add(MakeShared<FJsonValueArray>(Array(ProphecyThrow::FromUnrealPoint(S.Space.InverseTransformVectorNoScale(Axis*100.)))));
        Coverage->SetArrayField(TEXT("axes"),Axes);Request->SetObjectField(TEXT("coverage"),Coverage);
    }
    FValues Rig,Names;for(int32 P:Parents)Rig.Add(MakeShared<FJsonValueNumber>(P));Names.Add(MakeShared<FJsonValueString>(TEXT("root")));for(const auto* Name:BodyNames)Names.Add(MakeShared<FJsonValueString>(Name));Request->SetArrayField(TEXT("parents"),Rig);Request->SetArrayField(TEXT("names"),Names);
    FValues Contacts;const FValues& Feet=Candidate->GetArrayField(TEXT("feet"));const auto* PriorText=S.AcceptedFrames.Find(Tick-2);const auto Prior=PriorText?Parse(**PriorText):nullptr;
    for(int32 Side=0;Side<Feet.Num();++Side)
    {
        const auto Planned=Feet[Side]->AsObject();auto Contact=Planned->TryGetField(TEXT("contact"));
        const TSharedPtr<FJsonObject> *PC=nullptr,*AC=nullptr;
        if(Prior&&Planned->TryGetObjectField(TEXT("contact"),PC))
        {
            const auto Actual=Prior->GetArrayField(TEXT("feet"))[Side]->AsObject();
            if(Actual->TryGetObjectField(TEXT("contact"),AC))
            {
                bool Same=true;for(const TCHAR* Key:{TEXT("surface"),TEXT("stanceId"),TEXT("pivotKey")})
                {const auto X=(*PC)->TryGetField(Key),Y=(*AC)->TryGetField(Key);if(bool(X)!=bool(Y)||(X&&((X->Type!=Y->Type)||(X->Type==EJson::String&&X->AsString()!=Y->AsString())||(X->Type==EJson::Number&&X->AsNumber()!=Y->AsNumber()))))Same=false;}
                if(Same)Contact=MakeShared<FJsonValueObject>(*AC);
            }
        }
        Contacts.Add(Contact?Contact:MakeShared<FJsonValueNull>());
    }
    Request->SetArrayField(TEXT("contacts"),Contacts);FString Reply;
    if(!S.Publication->Command(Json(Request),Reply,Error))return false;const auto Joined=Parse(Reply);const TSharedPtr<FJsonObject>* Frame=nullptr;
    if(!Joined||!Joined->TryGetObjectField(TEXT("frame"),Frame)){Error=TEXT("Publication join returned no pose");return false;}
    if(S.CacheScene.Valid)
    {
        bool Covered=false;if(!Joined->TryGetBoolField(TEXT("covered"),Covered)||!Covered)
        {S.JoinMiss=TEXT("shoe or influence neighborhood left prediction collision coverage");return false;}
    }
    // Actual heading accompanies the raw30Hz sample; delayed workers must not
    // infer it from a stale forecast or a pose's virtual root-bone rotation.
    (*Frame)->SetArrayField(TEXT("rootHeading"),Array(ProphecyThrow::FromUnrealPoint(S.Space.InverseTransformVectorNoScale(CurrentActual.HeadingWorld)).GetSafeNormal()));
    FOutput Result;Result.Tick=Tick;Result.CommandRevision=Revision;
    if(!ReadPose(*Frame,TEXT("pose"),S.Space,Result.PoseWorld,Error)||!ReadPose(*Frame,TEXT("raw"),S.Space,Result.RawWorld,Error))return false;
    Result.DiagnosticsJson=Json(*Frame);Out=MoveTemp(Result);
    FSourceSample Final=CurrentActual;Final.RootWorld=Out.PoseWorld[0].GetLocation();for(int32 J=0;J<25;++J)Final.BodiesWorld[J]=Out.PoseWorld[J+1];
    // The game publishes60Hz. Its intervening120Hz boundary is the actual
    // interpolation between those final targets, not an unshown worker frame.
    const int32 First=FMath::Max(S.AcceptedThrough+1,Tick-1);
    for(int32 I=First;I<Tick;++I)
    {
        const double Alpha=double(I-(Tick-2))/2;FSourceSample Middle=Final;Middle.RootWorld=FMath::Lerp(PreviousActual.RootWorld,Final.RootWorld,Alpha);
        Middle.HeadingWorld=FMath::Lerp(PreviousActual.HeadingWorld,Final.HeadingWorld,Alpha).GetSafeNormal();
        for(int32 J=0;J<25;++J)Middle.BodiesWorld[J].Blend(PreviousActual.BodiesWorld[J],Final.BodiesWorld[J],Alpha);
        auto MiddleFrame=ObservedFrame(Middle,S.Space);FValues MiddleFeet;
        for(int32 Side=0;Side<2;++Side)
        {
            auto Foot=Parse(Json((*Frame)->GetArrayField(TEXT("feet"))[Side]->AsObject()));
            // Keep only contacts already present in the preceding real target.
            const TSharedPtr<FJsonObject>* OldContact=nullptr;
            if(!Prior||!Prior->GetArrayField(TEXT("feet"))[Side]->AsObject()->TryGetObjectField(TEXT("contact"),OldContact)){Foot->SetField(TEXT("contact"),MakeShared<FJsonValueNull>());Foot->SetStringField(TEXT("state"),TEXT("SWING"));}
            MiddleFeet.Add(MakeShared<FJsonValueObject>(Foot));
        }
        MiddleFrame->SetArrayField(TEXT("feet"),MiddleFeet);S.AcceptedFrames.Add(I,MakeShared<const FString,ESPMode::ThreadSafe>(Json(MiddleFrame)));
    }
    S.AcceptedFrames.Add(Tick,MakeShared<const FString,ESPMode::ThreadSafe>(Out.DiagnosticsJson));S.AcceptedThrough=S.ObservedTick=Tick;S.LastObserved=MoveTemp(Final);S.Status.AppliedFrame=Tick/2;S.Status.DiagnosticsJson=Reply;
    ++S.JoinedFrames;S.JoinMiss.Reset();
    PruneAcknowledgedHistory(S);for(auto I=S.Frames.CreateIterator();I;++I)if(I.Key()<Tick-4)I.RemoveCurrent();return true;
}
bool ObserveActualPose(AProphecyAgent* A,int32 Tick,const FSourceSample& Sample,FString& Error)
{
    Error.Reset();auto* Found=States.Find(A);if(!Found)return false;auto& S=**Found;
    if(!S.HasSpace)return false;if(Tick<=S.ObservedTick)return Tick==S.ObservedTick;
    if(Sample.BodiesWorld.Num()!=25||Sample.RootWorld.ContainsNaN()){Error=TEXT("Actual live Foot IK publication is incomplete");return false;}
    for(const auto& Body:Sample.BodiesWorld)if(Body.ContainsNaN()){Error=TEXT("Nonfinite actual live Foot IK publication");return false;}
    if(S.ObservedTick>=0&&Tick-S.ObservedTick>4){Error=TEXT("Actual live Foot IK history has a gap; re-enable from the current pose pair");return false;}
    const int32 First=S.ObservedTick<0?Tick:S.ObservedTick+1;
    for(int32 I=First;I<=Tick;++I)
    {
        FSourceSample Between=Sample;
        if(I<Tick)
        {
            const double Alpha=double(I-S.ObservedTick)/(Tick-S.ObservedTick);Between.RootWorld=FMath::Lerp(S.LastObserved.RootWorld,Sample.RootWorld,Alpha);
            Between.HeadingWorld=FMath::Lerp(S.LastObserved.HeadingWorld,Sample.HeadingWorld,Alpha).GetSafeNormal();
            for(int32 J=0;J<25;++J)Between.BodiesWorld[J].Blend(S.LastObserved.BodiesWorld[J],Sample.BodiesWorld[J],Alpha);
        }
        S.AcceptedFrames.Add(I,MakeShared<const FString,ESPMode::ThreadSafe>(Json(ObservedFrame(Between,S.Space))));
    }
    S.LastObserved=Sample;S.ObservedTick=S.AcceptedThrough=Tick;
    PruneAcknowledgedHistory(S);return true;
}
FTransform ToSolverBody(const FTransform& World,const FTransform& Space)
{
    const FTransform Local=World.GetRelativeTransform(Space);const FQuat Q=Local.GetRotation();
    const FQuat Solver=(FQuat(FVector(1,0,0),-UE_DOUBLE_PI/2)*FQuat(-Q.X,Q.Y,-Q.Z,Q.W)).GetNormalized();
    return FTransform(Solver,ProphecyThrow::FromUnrealPoint(Local.GetLocation()));
}
bool BuildInitialHistory(int32 PreviousTick,int32 CurrentTick,const FSourceSample& Previous,const FSourceSample& Current,const FTransform& Space,FString& Out,FString& Error)
{
    Error.Reset();if(PreviousTick<0||CurrentTick<=PreviousTick||CurrentTick-PreviousTick!=4||Previous.BodiesWorld.Num()!=25||Current.BodiesWorld.Num()!=25||Space.ContainsNaN())
    {Error=TEXT("Initial live Foot IK history requires consecutive actual30Hz pose samples");return false;}
    auto History=MakeShared<FJsonObject>();History->SetNumberField(TEXT("previousTick"),PreviousTick);History->SetNumberField(TEXT("currentTick"),CurrentTick);
    auto Encode=[&](const FSourceSample& Sample)
    {
        FValues Points={MakeShared<FJsonValueArray>(Array(ProphecyThrow::FromUnrealPoint(Space.InverseTransformPosition(Sample.RootWorld))))};
        FValues Rotations={MakeShared<FJsonValueArray>(FValues{MakeShared<FJsonValueNumber>(0),MakeShared<FJsonValueNumber>(0),MakeShared<FJsonValueNumber>(0),MakeShared<FJsonValueNumber>(1)})};
        for(const auto& Body:Sample.BodiesWorld)
        {
            const auto Solver=ToSolverBody(Body,Space);const auto Q=Solver.GetRotation();Points.Add(MakeShared<FJsonValueArray>(Array(Solver.GetLocation())));
            Rotations.Add(MakeShared<FJsonValueArray>(FValues{MakeShared<FJsonValueNumber>(Q.X),MakeShared<FJsonValueNumber>(Q.Y),MakeShared<FJsonValueNumber>(Q.Z),MakeShared<FJsonValueNumber>(Q.W)}));
        }
        auto Pose=MakeShared<FJsonObject>();Pose->SetArrayField(TEXT("points"),Points);Pose->SetArrayField(TEXT("q"),Rotations);Pose->SetArrayField(TEXT("rootHeading"),Array(ProphecyThrow::FromUnrealPoint(Space.InverseTransformVectorNoScale(Sample.HeadingWorld)).GetSafeNormal()));return Pose;
    };
    if(Previous.RootWorld.ContainsNaN()||Current.RootWorld.ContainsNaN()){Error=TEXT("Nonfinite initial root history");return false;}
    for(const auto* Sample:{&Previous,&Current})for(const auto& Body:Sample->BodiesWorld)if(Body.ContainsNaN()){Error=TEXT("Nonfinite initial body history");return false;}
    History->SetObjectField(TEXT("previous"),Encode(Previous));History->SetObjectField(TEXT("current"),Encode(Current));Out=Json(History);return true;
}
bool BuildSource(TConstArrayView<FName> Names,TConstArrayView<FSourceSample> Samples,const FTransform& Space,const FString& Gait,FString& Out,FString& Error)
{
    Error.Reset();if(Names.Num()!=25||Samples.Num()<2||Samples.Num()>241||Space.ContainsNaN()||!Space.GetScale3D().Equals(FVector::OneVector,1.e-8))
    {Error=TEXT("Expected canonical 25-body real NN samples at30Hz and a unit-scale course frame");return false;}
    for(int32 I=0;I<25;++I)if(Names[I]!=FName(BodyNames[I])){Error=TEXT("Live Foot IK bone order must match the canonical rig");return false;}
    FValues PoseRows,Roots,Yaws,JsonNames;for(FName Name:Names)JsonNames.Add(MakeShared<FJsonValueString>(Name.ToString()));
    double PriorYaw=0,Travel=0,ReferenceHeight=0;FVector PriorRoot=FVector::ZeroVector;
    for(int32 Row=0;Row<Samples.Num();++Row)
    {
        const auto& Sample=Samples[Row];if(Sample.BodiesWorld.Num()!=25||Sample.RootWorld.ContainsNaN()||Sample.HeadingWorld.ContainsNaN())
        {Error=TEXT("Incomplete or nonfinite real NN source sample");return false;}
        const FVector Root=ProphecyThrow::FromUnrealPoint(Space.InverseTransformPosition(Sample.RootWorld));
        if(Row)Travel+=FVector2D(Root.X-PriorRoot.X,Root.Z-PriorRoot.Z).Size();PriorRoot=Root;
        FValues Points,Basis;
        for(const FTransform& Body:Sample.BodiesWorld)
        {
            if(Body.ContainsNaN()){Error=TEXT("Nonfinite real NN body transform");return false;}
            FTransform Solver=ToSolverBody(Body,Space);FVector P=Solver.GetLocation();P.Y-=Root.Y;
            Points.Add(MakeShared<FJsonValueArray>(Array(P)));Basis.Add(MakeShared<FJsonValueArray>(Axes(Solver.GetRotation())));
        }
        ReferenceHeight+=Points[0]->AsArray()[1]->AsNumber();
        auto Pose=MakeShared<FJsonObject>();Pose->SetArrayField(TEXT("points"),Points);Pose->SetArrayField(TEXT("axes"),Basis);PoseRows.Add(MakeShared<FJsonValueObject>(Pose));
        Roots.Add(MakeShared<FJsonValueArray>(Array(FVector(Root.X,0,Root.Z))));
        const FVector H=ProphecyThrow::FromUnrealPoint(Space.InverseTransformVectorNoScale(Sample.HeadingWorld));
        if(FMath::Square(H.X)+FMath::Square(H.Z)<1.e-12){Error=TEXT("Live root heading must have a horizontal component");return false;}
        double Yaw=FMath::RadiansToDegrees(FMath::Atan2(H.X,H.Z));if(Row)Yaw=PriorYaw+FMath::FindDeltaAngleDegrees(PriorYaw,Yaw);PriorYaw=Yaw;Yaws.Add(MakeShared<FJsonValueNumber>(Yaw));
    }
    const double Duration=(Samples.Num()-1)/30.;auto Source=MakeShared<FJsonObject>(),Meta=MakeShared<FJsonObject>();
    Meta->SetNumberField(TEXT("commandSpeed"),Travel/Duration);Meta->SetNumberField(TEXT("facingDegrees"),0);Meta->SetNumberField(TEXT("referenceHeight"),ReferenceHeight/Samples.Num());Meta->SetNumberField(TEXT("totalDuration"),Duration);
    Source->SetArrayField(TEXT("names"),JsonNames);Source->SetArrayField(TEXT("poses"),PoseRows);Source->SetArrayField(TEXT("roots"),Roots);Source->SetArrayField(TEXT("rootYawDegrees"),Yaws);Source->SetNumberField(TEXT("fps"),30);Source->SetNumberField(TEXT("duration"),Duration);Source->SetNumberField(TEXT("totalDuration"),Duration);Source->SetBoolField(TEXT("nnRootWindow"),true);Source->SetStringField(TEXT("gait"),Gait);Source->SetStringField(TEXT("direction"),TEXT("forward"));Source->SetStringField(TEXT("source"),TEXT("live game NN/controller"));Source->SetObjectField(TEXT("directionMeta"),Meta);Out=Json(Source);return true;
}
bool CaptureTerrain(AProphecyAgent* A,const FTransform& Space,TConstArrayView<FSourceSample> Samples,FString& Out,FString& Error)
{
    Error.Reset();if(!IsInGameThread()||!IsValid(A)||!A->GetWorld()||Samples.Num()<2||Space.ContainsNaN()||!Space.GetScale3D().Equals(FVector::OneVector,1.e-8))
    {Error=TEXT("Terrain capture requires the game thread, live agent and navigation root forecast");return false;}
    const ECollisionChannel RootChannel=A->GetAgentCapsule()?A->GetAgentCapsule()->GetCollisionObjectType():ECC_GameTraceChannel8;
    FBox Bounds(ForceInit);FValues RootRows;
    for(int32 Row=0;Row<Samples.Num();++Row)
    {
        const auto& Sample=Samples[Row];if(Sample.RootWorld.ContainsNaN()){Error=TEXT("Nonfinite navigation root");return false;}Bounds+=Sample.RootWorld;
        auto Root=MakeShared<FJsonObject>();Root->SetNumberField(TEXT("time"),Row/30.);Root->SetArrayField(TEXT("position"),Array(ProphecyThrow::FromUnrealPoint(Space.InverseTransformPosition(Sample.RootWorld))));RootRows.Add(MakeShared<FJsonValueObject>(Root));
    }
    Bounds=Bounds.ExpandBy(FVector(160,160,220));FCollisionObjectQueryParams Objects;Objects.AddObjectTypesToQuery(ECC_WorldStatic);Objects.AddObjectTypesToQuery(ECC_WorldDynamic);
    FCollisionQueryParams Query(SCENE_QUERY_STAT(ProphecyFootIKLiveTerrain),false,A);TArray<FOverlapResult> Hits;
    A->GetWorld()->OverlapMultiByObjectType(Hits,Bounds.GetCenter(),FQuat::Identity,Objects,FCollisionShape::MakeBox(Bounds.GetExtent()),Query);
    TSet<UPrimitiveComponent*> Seen;TArray<TSharedPtr<FJsonObject>> Tiles;bool Unsupported=false;
    auto AddBox=[&](UPrimitiveComponent* C,const FTransform& Local,const FVector& Extent,int32 Index)
    {
        const FTransform World=Local*C->GetComponentTransform();const FVector E=Extent*World.GetScale3D().GetAbs();if(E.GetMin()<=0)return;
        const FVector Up=Space.InverseTransformVectorNoScale(World.GetRotation().GetAxisZ());
        if(FMath::Abs(Up.Z)<1-1.e-7){Unsupported=true;return;}
        const FVector Normal=World.GetRotation().GetAxisZ()*(Up.Z>=0?1.:-1.);
        const FVector Point=ProphecyThrow::FromUnrealPoint(Space.InverseTransformPosition(World.GetLocation()+Normal*E.Z));
        const FVector U=ProphecyThrow::FromUnrealPoint(Space.InverseTransformVectorNoScale(World.GetRotation().GetAxisX())).GetSafeNormal();
        const FVector V=ProphecyThrow::FromUnrealPoint(Space.InverseTransformVectorNoScale(World.GetRotation().GetAxisY())).GetSafeNormal();
        auto T=MakeShared<FJsonObject>();T->SetStringField(TEXT("id"),FString::Printf(TEXT("%u:%d"),C->GetUniqueID(),Index));T->SetArrayField(TEXT("point"),Array(Point));T->SetArrayField(TEXT("u"),Array(U));T->SetArrayField(TEXT("v"),Array(V));
        T->SetArrayField(TEXT("bounds"),{MakeShared<FJsonValueNumber>(-E.X*.01),MakeShared<FJsonValueNumber>(E.X*.01),MakeShared<FJsonValueNumber>(-E.Y*.01),MakeShared<FJsonValueNumber>(E.Y*.01)});
        T->SetBoolField(TEXT("shaped"),true);Tiles.Add(T);
    };
    for(const auto& Hit:Hits)
    {
        auto* C=Hit.GetComponent();if(!C||Seen.Contains(C)||Cast<AProphecyAgent>(C->GetOwner()))continue;Seen.Add(C);
        const bool Feet=C->ComponentHasTag(TEXT("FootIKFeet")),Root=C->ComponentHasTag(TEXT("FootIKRoot"));
        if((Root&&!Feet)||(!Feet&&C->GetCollisionResponseToChannel(RootChannel)!=ECR_Block))continue;
        if(auto* Box=Cast<UBoxComponent>(C)){AddBox(C,FTransform::Identity,Box->GetUnscaledBoxExtent(),0);continue;}
        if(auto* Setup=C->GetBodySetup())
        {
            if(Setup->CollisionTraceFlag==CTF_UseComplexAsSimple||(Setup->AggGeom.BoxElems.IsEmpty()&&Setup->AggGeom.ConvexElems.IsEmpty())||!Setup->AggGeom.SphereElems.IsEmpty()||!Setup->AggGeom.SphylElems.IsEmpty()){Unsupported=true;continue;}
            for(int32 I=0;I<Setup->AggGeom.BoxElems.Num();++I){const auto& B=Setup->AggGeom.BoxElems[I];AddBox(C,B.GetTransform(),FVector(B.X,B.Y,B.Z)*.5,I);}
            for(int32 I=0;I<Setup->AggGeom.ConvexElems.Num();++I)
            {
                const auto& Hull=Setup->AggGeom.ConvexElems[I];FTransform Box;FVector Extent;
                if(!ProphecyFootIKCollision::ConvexBox(Hull.VertexData,Box,Extent)){Unsupported=true;continue;}
                AddBox(C,Box*Hull.GetTransform(),Extent,Setup->AggGeom.BoxElems.Num()+I);
            }
        }
        else Unsupported=true;
    }
    if(Unsupported){Error=TEXT("Foot IK tread collision must contain horizontal box tops. Tag a separate navigation ramp FootIKRoot; tag query-only treads FootIKFeet. Sloped contact uses surface mode.");return false;}
    Tiles.Sort([](const auto& L,const auto& R){return L->GetStringField(TEXT("id"))<R->GetStringField(TEXT("id"));});
    FValues Values;for(auto& T:Tiles)Values.Add(MakeShared<FJsonValueObject>(T));
    FBox Capture(ForceInit);
    for(double X:{Bounds.Min.X,Bounds.Max.X})for(double Y:{Bounds.Min.Y,Bounds.Max.Y})for(double Z:{Bounds.Min.Z,Bounds.Max.Z})
        Capture+=ProphecyThrow::FromUnrealPoint(Space.InverseTransformPosition(FVector(X,Y,Z)));
    FValues CaptureBounds=Array(Capture.Min);CaptureBounds.Append(Array(Capture.Max));
    FValues WorldBounds=Array(Bounds.Min);WorldBounds.Append(Array(Bounds.Max));
    auto Terrain=MakeShared<FJsonObject>();Terrain->SetArrayField(TEXT("tiles"),Values);Terrain->SetArrayField(TEXT("rootRows"),RootRows);Terrain->SetArrayField(TEXT("captureBounds"),CaptureBounds);Terrain->SetArrayField(TEXT("captureWorldBounds"),WorldBounds);Terrain->SetNumberField(TEXT("rootStartTick"),0);Out=Json(Terrain);return true;
}
bool CaptureSurfaceTerrain(AProphecyAgent* A,const FTransform& Space,TConstArrayView<FSourceSample> Samples,FString& Out,FString& Error)
{
    Error.Reset();if(!IsInGameThread()||!IsValid(A)||!A->GetWorld()||Samples.IsEmpty()||Space.ContainsNaN()||!Space.GetScale3D().Equals(FVector::OneVector,1.e-8))
    {Error=TEXT("Surface capture requires a live game-thread agent and fixed unit-scale course frame");return false;}
    const ECollisionChannel RootChannel=A->GetAgentCapsule()?A->GetAgentCapsule()->GetCollisionObjectType():ECC_GameTraceChannel8;
    FBox Bounds(ForceInit);for(const auto& S:Samples){if(S.RootWorld.ContainsNaN()){Error=TEXT("Nonfinite surface query root");return false;}Bounds+=S.RootWorld;}
    Bounds=Bounds.ExpandBy(FVector(200,200,220));FCollisionObjectQueryParams Types;Types.AddObjectTypesToQuery(ECC_WorldStatic);Types.AddObjectTypesToQuery(ECC_WorldDynamic);
    FCollisionQueryParams Query(SCENE_QUERY_STAT(ProphecyFootIKLiveSurfaces),false,A);TArray<FOverlapResult> Hits;A->GetWorld()->OverlapMultiByObjectType(Hits,Bounds.GetCenter(),FQuat::Identity,Types,FCollisionShape::MakeBox(Bounds.GetExtent()),Query);
    TArray<TSharedPtr<FJsonObject>> Planes,Navigation;TSet<UPrimitiveComponent*> Seen;bool Unsupported=false,CaptureFeet=true,CaptureRoot=true;
    auto AddBox=[&](UPrimitiveComponent* C,const FTransform& Local,const FVector& Extent,int32 Element)
    {
        const FTransform World=Local*C->GetComponentTransform();const FVector Scale=World.GetScale3D();
        const FVector E=Extent*Scale.GetAbs();if(E.GetMin()<=0)return;
        FVector AxesWorld[3]={World.GetRotation().GetAxisX(),World.GetRotation().GetAxisY(),World.GetRotation().GetAxisZ()};
        for(int32 Axis=0;Axis<3;++Axis)if(Scale[Axis]<0)AxesWorld[Axis]*=-1;
        for(int32 Axis=0;Axis<3;++Axis)for(int32 Sign:{-1,1})
        {
            const int32 U=(Axis+1)%3,V=(Axis+2)%3;const FVector NormalWorld=AxesWorld[Axis]*Sign;
            const FVector OriginWorld=World.GetLocation()+NormalWorld*E[Axis];
            // Skip distant side faces of very large floors, but retain every
            // physically reachable face including walls and undersides.
            double Closest2=DBL_MAX;
            for(const auto& S:Samples)
            {
                const FVector D=S.RootWorld-OriginWorld;
                const FVector P=OriginWorld+AxesWorld[U]*FMath::Clamp(FVector::DotProduct(D,AxesWorld[U]),-E[U],E[U])+AxesWorld[V]*FMath::Clamp(FVector::DotProduct(D,AxesWorld[V]),-E[V],E[V]);
                Closest2=FMath::Min(Closest2,FVector::DistSquared(S.RootWorld,P));
            }
            if(Closest2>FMath::Square(300.))continue;
            const FVector Origin=ProphecyThrow::FromUnrealPoint(Space.InverseTransformPosition(OriginWorld));
            const FVector Normal=ProphecyThrow::FromUnrealPoint(Space.InverseTransformVectorNoScale(NormalWorld)).GetSafeNormal();
            const FVector Tangent=ProphecyThrow::FromUnrealPoint(Space.InverseTransformVectorNoScale(AxesWorld[U])).GetSafeNormal();
            auto Plane=MakeShared<FJsonObject>();Plane->SetStringField(TEXT("id"),FString::Printf(TEXT("%u:%d:%d:%d"),C->GetUniqueID(),Element,Axis,Sign));
            Plane->SetArrayField(TEXT("origin"),Array(Origin));Plane->SetArrayField(TEXT("normal"),Array(Normal));Plane->SetArrayField(TEXT("tangent"),Array(Tangent));
            Plane->SetArrayField(TEXT("bounds"),{MakeShared<FJsonValueNumber>(-E[U]*.01),MakeShared<FJsonValueNumber>(E[U]*.01),MakeShared<FJsonValueNumber>(-E[V]*.01),MakeShared<FJsonValueNumber>(E[V]*.01)});
            Plane->SetNumberField(TEXT("thickness"),E[Axis]*.02);if(CaptureFeet)Planes.Add(Plane);if(CaptureRoot)Navigation.Add(Plane);
        }
    };
    for(const auto& Hit:Hits)
    {
        auto* C=Hit.GetComponent();if(!C||Seen.Contains(C)||Cast<AProphecyAgent>(C->GetOwner()))continue;Seen.Add(C);
        const bool Feet=C->ComponentHasTag(TEXT("FootIKFeet")),Root=C->ComponentHasTag(TEXT("FootIKRoot"));
        if(!Feet&&!Root&&C->GetCollisionResponseToChannel(RootChannel)!=ECR_Block)continue;
        CaptureFeet=Feet||!Root;CaptureRoot=Root||!Feet;
        if(auto* Box=Cast<UBoxComponent>(C)){AddBox(C,FTransform::Identity,Box->GetUnscaledBoxExtent(),0);continue;}
        auto* Setup=C->GetBodySetup();if(!Setup||Setup->CollisionTraceFlag==CTF_UseComplexAsSimple||(Setup->AggGeom.BoxElems.IsEmpty()&&Setup->AggGeom.ConvexElems.IsEmpty())||!Setup->AggGeom.SphereElems.IsEmpty()||!Setup->AggGeom.SphylElems.IsEmpty()){Unsupported=true;continue;}
        for(int32 I=0;I<Setup->AggGeom.BoxElems.Num();++I){const auto& Box=Setup->AggGeom.BoxElems[I];AddBox(C,Box.GetTransform(),FVector(Box.X,Box.Y,Box.Z)*.5,I);}
        for(int32 I=0;I<Setup->AggGeom.ConvexElems.Num();++I)
        {
            const auto& Hull=Setup->AggGeom.ConvexElems[I];FTransform Box;FVector Extent;
            if(!ProphecyFootIKCollision::ConvexBox(Hull.VertexData,Box,Extent)){Unsupported=true;continue;}
            AddBox(C,Box*Hull.GetTransform(),Extent,Setup->AggGeom.BoxElems.Num()+I);
        }
    }
    if(Unsupported){Error=TEXT("Live surface capture encountered non-box collision; its actual finite faces must be supplied by a mesh adapter");return false;}
    Planes.Sort([](const auto& L,const auto& R){return L->GetStringField(TEXT("id"))<R->GetStringField(TEXT("id"));});FValues Values;for(const auto& P:Planes)Values.Add(MakeShared<FJsonValueObject>(P));
    Navigation.Sort([](const auto& L,const auto& R){return L->GetStringField(TEXT("id"))<R->GetStringField(TEXT("id"));});FValues RootValues;for(const auto& P:Navigation)RootValues.Add(MakeShared<FJsonValueObject>(P));
    auto Terrain=MakeShared<FJsonObject>();Terrain->SetArrayField(TEXT("surfaces"),Values);Terrain->SetArrayField(TEXT("rootSurfaces"),RootValues);Out=Json(Terrain);return true;
}
bool TerrainGeometryHash(const FString& Text,uint32& Hash,FString& Error)
{
    Error.Reset();const auto Terrain=Parse(Text);const FValues* Input=nullptr;
    const bool Surface=Terrain&&Terrain->TryGetArrayField(TEXT("surfaces"),Input);
    if(!Surface&&(!Terrain||!Terrain->TryGetArrayField(TEXT("tiles"),Input)))
    {Error=TEXT("Terrain geometry needs finite tile or surface records");return false;}
    // Reconstruct in an explicit field order: neither JSON map iteration nor
    // broadphase overlap order is an identity change.
    TArray<TSharedPtr<FJsonObject>> Records;TSet<FString> Ids;
    for(const auto& Value:*Input)
    {
        const auto Record=Value->AsObject();FString Id;
        if(!Record||!Record->TryGetStringField(TEXT("id"),Id)||Ids.Contains(Id))
        {Error=TEXT("Terrain collider IDs must be unique");return false;}
        Ids.Add(Id);Records.Add(Record);
    }
    Records.Sort([](const auto& L,const auto& R){return L->GetStringField(TEXT("id"))<R->GetStringField(TEXT("id"));});
    FValues Ordered;
    for(const auto& Record:Records)
    {
        auto Canonical=MakeShared<FJsonObject>();Canonical->SetStringField(TEXT("id"),Record->GetStringField(TEXT("id")));
        if(Surface)
        {
            for(const TCHAR* Key:{TEXT("origin"),TEXT("normal"),TEXT("tangent"),TEXT("bounds")})
            {
                const FValues* Numbers=nullptr;const int32 Count=FCString::Strcmp(Key,TEXT("bounds"))==0?4:3;
                if(!Record->TryGetArrayField(Key,Numbers)||Numbers->Num()!=Count){Error=TEXT("Incomplete finite surface geometry");return false;}
                for(const auto& Number:*Numbers)if(Number->Type!=EJson::Number||!FMath::IsFinite(Number->AsNumber())){Error=TEXT("Nonfinite surface geometry");return false;}
                Canonical->SetArrayField(Key,*Numbers);
            }
            double Thickness=0;if(!Record->TryGetNumberField(TEXT("thickness"),Thickness)||!FMath::IsFinite(Thickness)){Error=TEXT("Invalid surface thickness");return false;}
            Canonical->SetNumberField(TEXT("thickness"),Thickness);
        }
        else if(Record->HasField(TEXT("point")))
        {
            for(const TCHAR* Key:{TEXT("point"),TEXT("u"),TEXT("v"),TEXT("bounds")})
            {
                const FValues* Numbers=nullptr;const int32 Count=FCString::Strcmp(Key,TEXT("bounds"))==0?4:3;
                if(!Record->TryGetArrayField(Key,Numbers)||Numbers->Num()!=Count){Error=TEXT("Incomplete oriented tread geometry");return false;}
                for(const auto& Number:*Numbers)if(Number->Type!=EJson::Number||!FMath::IsFinite(Number->AsNumber())){Error=TEXT("Nonfinite tread geometry");return false;}
                Canonical->SetArrayField(Key,*Numbers);
            }
            bool Shaped=true;Record->TryGetBoolField(TEXT("shaped"),Shaped);Canonical->SetBoolField(TEXT("shaped"),Shaped);
        }
        else for(const TCHAR* Key:{TEXT("x0"),TEXT("x1"),TEXT("z0"),TEXT("z1"),TEXT("y")})
        {
            double Number=0;if(!Record->TryGetNumberField(Key,Number)||!FMath::IsFinite(Number)){Error=TEXT("Incomplete finite tile geometry");return false;}
            Canonical->SetNumberField(Key,Number);
        }
        Ordered.Add(MakeShared<FJsonValueObject>(Canonical));
    }
    auto Canonical=MakeShared<FJsonObject>();Canonical->SetArrayField(Surface?TEXT("surfaces"):TEXT("tiles"),Ordered);
    const FValues* Navigation=nullptr;if(Surface&&Terrain->TryGetArrayField(TEXT("rootSurfaces"),Navigation))
    {
        auto Root=MakeShared<FJsonObject>();Root->SetArrayField(TEXT("surfaces"),*Navigation);uint32 RootHash=0;
        if(!TerrainGeometryHash(Json(Root),RootHash,Error))return false;Canonical->SetNumberField(TEXT("rootSurfaceHash"),double(RootHash));
    }
    Hash=FCrc::StrCrc32(*Json(Canonical));return true;
}
}
