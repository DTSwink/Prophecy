#include "ProphecyFootIKSurfaceOwner.h"
#include "ProphecyFootIKRuntime.h"
#include "ProphecyFootIKNN.h"
#include "ProphecyFootIKPreparation.h"
#include "ProphecyFootIKLiveLibrary.h"
#include "ProphecyThrowMath.h"
#include "ProphecyAgent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

namespace ProphecyFootIKSurface
{
namespace Detail
{
using FValues=TArray<TSharedPtr<FJsonValue>>;
static const FName Names[]={TEXT("root"),TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
static const int32 Parents[]={-1,0,1,2,3,4,5,6,7,8,9,6,11,12,13,6,15,16,1,18,19,20,1,22,23,24};
FString Json(const TSharedPtr<FJsonObject>& Value){FString Text;FJsonSerializer::Serialize(Value.ToSharedRef(),TJsonWriterFactory<>::Create(&Text));return Text;}
TSharedPtr<FJsonObject> Parse(const FString& Text){TSharedPtr<FJsonObject> Value;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Value);return Value;}
FValues Array(const FVector& V){return {MakeShared<FJsonValueNumber>(V.X),MakeShared<FJsonValueNumber>(V.Y),MakeShared<FJsonValueNumber>(V.Z)};}
FVector Vector(const FValues& A){return A.Num()==3?FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber()):FVector::ZeroVector;}
FQuat Quaternion(const FValues& A){return A.Num()==4?FQuat(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber(),A[3]->AsNumber()):FQuat::Identity;}
bool CheckContract(const FString& Relative,const TCHAR* Expected,const TCHAR* Label,FString& Error,double* Height=nullptr)
{
    const FString Path=FPaths::IsRelative(Relative)?FPaths::ProjectDir()/Relative:Relative;FString Text,Hash;
    if(!FFileHelper::LoadFileToString(Text,*Path)){Error=FString::Printf(TEXT("Cannot read the selected %s runtime contract: %s"),Label,*Path);return false;}
    const auto Meta=Parse(Text);if(!Meta||!Meta->TryGetStringField(TEXT("checkpoint_sha256"),Hash)||!Hash.Equals(Expected,ESearchCase::IgnoreCase))
    {Error=FString::Printf(TEXT("The selected %s checkpoint differs from the validated Foot IK native policy"),Label);return false;}
    if(Height)
    {
        const FValues* Offsets=nullptr;if(!Meta->TryGetArrayField(TEXT("local_offsets_m"),Offsets)||Offsets->IsEmpty()||(*Offsets)[0]->AsArray().Num()!=3)
        {Error=TEXT("The game rig contract has no pelvis calibration");return false;}
        *Height=(*Offsets)[0]->AsArray()[2]->AsNumber();if(!FMath::IsFinite(*Height)||*Height<=0){Error=TEXT("Invalid rig pelvis calibration");return false;}
    }
    return true;
}
bool SupportedUpper(const AProphecyAgent* A,FString& Error)
{
    if(A->bUpperNNHasSword||FMath::Abs(A->UpperNNGazeYawNormalized)>1.e-6||FMath::Abs(A->UpperNNGazePitchNormalized)>1.e-6)
    {Error=TEXT("The current native surface policy supports unarmed neutral gaze only; the selected upper commands require matching graph inputs");return false;}return true;
}
struct FFrame
{
    int32 Tick=0;TArray<FTransform> Pose;
    FVector Root=FVector::ZeroVector,Velocity=FVector::ZeroVector;float Yaw=0;
};
struct FState
{
    FProphecyFootIKRuntime Runtime;
    TSharedPtr<FProphecyFootIKNN,ESPMode::ThreadSafe> NN;
    FTransform Space=FTransform::Identity;
    FFrame Current,Previous30;
    TArray<FFrame> History;
    TSharedPtr<FJsonObject> Geometry;
    FString Json,Error;
    uint64 LastGameTick=MAX_uint64,GeometryRevision=0;
    int32 NextTick=0;
    bool GeometryDirty=false;
    ~FState(){FProphecyFootIKPreparation::Retire(MoveTemp(NN),Runtime.ReleaseVM());}
};
TMap<TWeakObjectPtr<AProphecyAgent>,TUniquePtr<FState>> States;
struct FPending
{
    TUniquePtr<FProphecyFootIKPreparation> Warm;
    FString Settings,Lower,Upper,ActivationError;
    double ReferenceHeight=0;
};
TMap<TWeakObjectPtr<AProphecyAgent>,TUniquePtr<FPending>> Pending;
FDelegateHandle Cleanup;
void RefreshCleanup()
{
    if(States.IsEmpty()&&Pending.IsEmpty()){FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();return;}
    if(!Cleanup.IsValid())Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for(auto It=States.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==World)It.RemoveCurrent();
        for(auto It=Pending.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==World)It.RemoveCurrent();
        RefreshCleanup();
    });
}
bool ReadGeometry(const FString& Text,TSharedPtr<FJsonObject>& Result,FString& Error)
{
    Result=Parse(Text);const FValues* Surfaces=nullptr;
    if(!Result||!Result->TryGetArrayField(TEXT("surfaces"),Surfaces))
    {Error=TEXT("Live surface ownership requires actual finite collider surfaces");return false;}return true;
}
bool Decode(FState& State,const TSharedPtr<FJsonObject>& Output,FFrame& Frame,FString& Error)
{
    const TSharedPtr<FJsonObject>* Solved=nullptr;const TSharedPtr<FJsonObject>* Pose=nullptr;const TSharedPtr<FJsonObject>* Root=nullptr;
    const FValues *Points=nullptr,*Rotations=nullptr,*Position=nullptr,*Velocity=nullptr;double Tick=0,Yaw=0;
    if(!Output||!Output->TryGetNumberField(TEXT("tick"),Tick)||!Output->TryGetObjectField(TEXT("frame"),Solved)||!(*Solved)->TryGetObjectField(TEXT("pose"),Pose)
      ||!(*Pose)->TryGetArrayField(TEXT("points"),Points)||!(*Pose)->TryGetArrayField(TEXT("q"),Rotations)||Points->Num()!=26||Rotations->Num()!=26
      ||!Output->TryGetObjectField(TEXT("root"),Root)||!(*Root)->TryGetArrayField(TEXT("position"),Position)||!(*Root)->TryGetArrayField(TEXT("velocity"),Velocity)||!(*Root)->TryGetNumberField(TEXT("yaw"),Yaw))
    {Error=TEXT("Causal Foot IK returned an incomplete pose/root interval");return false;}
    Frame.Tick=int32(Tick);Frame.Pose.SetNum(26);
    for(int32 I=0;I<26;++I)
    {
        const auto& P=(*Points)[I]->AsArray();const auto& Q=(*Rotations)[I]->AsArray();if(P.Num()!=3||Q.Num()!=4){Error=TEXT("Invalid Foot IK bone transform");return false;}
        Frame.Pose[I]=ProphecyThrow::ToUnreal(FTransform(Quaternion(Q),Vector(P)))*State.Space;
        if(Frame.Pose[I].ContainsNaN()){Error=TEXT("Nonfinite live Foot IK pose");return false;}
    }
    Frame.Root=State.Space.TransformPosition(ProphecyThrow::ToUnrealPoint(Vector(*Position)));
    Frame.Velocity=State.Space.TransformVectorNoScale(ProphecyThrow::ToUnrealPoint(Vector(*Velocity)));
    const double Angle=FMath::DegreesToRadians(Yaw);const FVector Heading=State.Space.TransformVectorNoScale(ProphecyThrow::ToUnrealPoint(FVector(FMath::Sin(Angle),0,FMath::Cos(Angle))));
    Frame.Yaw=float(FMath::RadiansToDegrees(FMath::Atan2(Heading.Y,Heading.X)));
    if(Frame.Root.ContainsNaN()||Frame.Velocity.ContainsNaN()||!FMath::IsFinite(Frame.Yaw)){Error=TEXT("Nonfinite live Foot IK carrier");return false;}return true;
}
bool Consume(FState& State,const FString& Text,FString& Error)
{
    const auto Reply=Parse(Text);const FValues* Outputs=nullptr;double Next=-1;
    if(!Reply||!Reply->TryGetArrayField(TEXT("outputs"),Outputs)||Outputs->IsEmpty()||!Reply->TryGetNumberField(TEXT("tick"),Next))
    {Error=TEXT("Missing causal Foot IK interval");return false;}
    for(const auto& Value:*Outputs)
    {
        FFrame Frame;if(!Decode(State,Value->AsObject(),Frame,Error))return false;
        if(Frame.Tick!=State.NextTick){Error=TEXT("Causal Foot IK frame gap");return false;}
        ++State.NextTick;State.History.Add(MoveTemp(Frame));
    }
    if(int32(Next)!=State.NextTick){Error=TEXT("Causal Foot IK clock mismatch");return false;}
    State.Current=State.History.Last();
    for(const auto& Frame:State.History)if(Frame.Tick==State.Current.Tick-4){State.Previous30=Frame;break;}
    while(State.History.Num()>5)State.History.RemoveAt(0,1,EAllowShrinking::No);
    State.Json=Text;return true;
}
TSharedPtr<FJsonObject> Seed(const TSharedPtr<FJsonObject>& Source,int32 Row)
{
    const auto Pose=Source->GetArrayField(TEXT("poses"))[Row]->AsObject();auto Points=Pose->GetArrayField(TEXT("points")),Axes=Pose->GetArrayField(TEXT("axes"));
    Points.Insert(Source->GetArrayField(TEXT("roots"))[Row],0);
    Axes.Insert(MakeShared<FJsonValueArray>(FValues{MakeShared<FJsonValueArray>(Array(FVector(1,0,0))),MakeShared<FJsonValueArray>(Array(FVector(0,1,0))),MakeShared<FJsonValueArray>(Array(FVector(0,0,1)))}),0);
    auto Result=MakeShared<FJsonObject>();Result->SetArrayField(TEXT("points"),Points);Result->SetArrayField(TEXT("axes"),Axes);return Result;
}
}
bool AnyActive(){return !Detail::States.IsEmpty();}
bool Active(const AProphecyAgent* A){return Detail::States.Contains(const_cast<AProphecyAgent*>(A));}
void Remove(AProphecyAgent* A){check(IsInGameThread());Detail::Pending.Remove(A);Detail::States.Remove(A);Detail::RefreshCleanup();}
bool Enable(AProphecyAgent* A,const FTransform& Space,const ProphecyFootIKLive::FSourceSample& Previous,const ProphecyFootIKLive::FSourceSample& Current,
    const FString& SettingsJson,const FString& GeometryJson,const FString& LowerPath,const FString& UpperPath,FString& Error)
{
    using namespace Detail;check(IsInGameThread());Error.Reset();
    if(!IsValid(A)||!A->GetWorld()||!A->GetWorld()->IsGameWorld()||!A->HasValidAgentHandle()||Space.ContainsNaN()||!Space.GetScale3D().Equals(FVector::OneVector,1.e-8))
    {Error=TEXT("A registered game agent and fixed unit-scale course frame are required");return false;}
    if(Active(A))return true;
    if(!SupportedUpper(A,Error)){Pending.Remove(A);RefreshCleanup();return false;}
    auto Settings=Parse(SettingsJson.IsEmpty()?TEXT("{}"):SettingsJson);if(!Settings){Pending.Remove(A);RefreshCleanup();Error=TEXT("Invalid live Foot IK settings");return false;}
    Settings->SetBoolField(TEXT("enabled"),true);Settings->SetStringField(TEXT("direction"),TEXT("forward"));
    FString Gait=TEXT("walk");Settings->TryGetStringField(TEXT("gait"),Gait);Settings->SetStringField(TEXT("gait"),Gait);
    auto* Existing=Pending.Find(A);
    if(Existing&&((*Existing)->Settings!=SettingsJson||(*Existing)->Lower!=LowerPath||(*Existing)->Upper!=UpperPath)){Pending.Remove(A);Existing=nullptr;}
    if(!Existing)
    {
        auto P=MakeUnique<FPending>();P->Settings=SettingsJson;P->Lower=LowerPath;P->Upper=UpperPath;
        if(!CheckContract(LowerPath,TEXT("0F2565AC72C5209153CBD910135209487F9EF8A0E234ED0C6D99DF2FF30A299E"),TEXT("Run181751 lower"),Error,&P->ReferenceHeight)
          ||!CheckContract(UpperPath,TEXT("02E73800B8E63DC1B79E3E9C67C0A5F269EB830D3A330FE81C2D11480AC6F5B4"),TEXT("Upper82500"),Error))return false;
        P->Warm=MakeUnique<FProphecyFootIKPreparation>(Json(Settings),true,EProphecyFootIKNNWarmup::Stream);Pending.Add(A,MoveTemp(P));RefreshCleanup();return false;
    }
    auto& Preparation=**Existing;
    if(!Preparation.ActivationError.IsEmpty()){Error=Preparation.ActivationError;return false;}
    if(Preparation.Warm->State(Error)!=FProphecyFootIKPreparation::EState::Ready)return false;
    double ReferenceHeight=Preparation.ReferenceHeight;
    if(!CheckContract(LowerPath,TEXT("0F2565AC72C5209153CBD910135209487F9EF8A0E234ED0C6D99DF2FF30A299E"),TEXT("Run181751 lower"),Error,&ReferenceHeight)
      ||!CheckContract(UpperPath,TEXT("02E73800B8E63DC1B79E3E9C67C0A5F269EB830D3A330FE81C2D11480AC6F5B4"),TEXT("Upper82500"),Error))
    {Pending.Remove(A);RefreshCleanup();return false;}
    // History and collision come from THIS call, after cold preparation. No
    // pose was captured when the worker began, and ordinary NN kept moving.
    auto State=MakeUnique<FState>();State->Space=Space;if(!ReadGeometry(GeometryJson,State->Geometry,Error))return false;
    const ProphecyFootIKLive::FSourceSample Samples[]={Previous,Current};FString SourceJson;
    if(!ProphecyFootIKLive::BuildSource(MakeArrayView(Names+1,25),MakeArrayView(Samples),Space,Gait,SourceJson,Error))return false;
    auto Source=Parse(SourceJson);Source->SetNumberField(TEXT("referenceHeight"),ReferenceHeight);Source->GetObjectField(TEXT("directionMeta"))->SetNumberField(TEXT("referenceHeight"),ReferenceHeight);
    auto Pair=MakeShared<FJsonObject>();Pair->SetObjectField(TEXT("previous"),Seed(Source,0));Pair->SetObjectField(TEXT("current"),Seed(Source,1));
    auto Input=MakeShared<FJsonObject>();Input->SetStringField(TEXT("op"),TEXT("init"));Input->SetObjectField(TEXT("source"),Source);Input->SetObjectField(TEXT("initialPair"),Pair);Input->SetObjectField(TEXT("settings"),Settings);
    FValues ParentValues;for(int32 Parent:Parents)ParentValues.Add(MakeShared<FJsonValueNumber>(Parent));Input->SetArrayField(TEXT("parents"),ParentValues);
    Input->SetArrayField(TEXT("surfaces"),State->Geometry->GetArrayField(TEXT("surfaces")));const FValues* Navigation=nullptr;if(State->Geometry->TryGetArrayField(TEXT("rootSurfaces"),Navigation))Input->SetArrayField(TEXT("rootSurfaces"),*Navigation);
    const FVector Position=ProphecyThrow::FromUnrealPoint(Space.InverseTransformPosition(Current.RootWorld));const FVector Velocity=ProphecyThrow::FromUnrealPoint(Space.InverseTransformVectorNoScale((Current.RootWorld-Previous.RootWorld)*30));
    TSharedPtr<FJsonObject> Root=MakeShared<FJsonObject>();Root->SetArrayField(TEXT("position"),Array(Position));Root->SetArrayField(TEXT("velocity"),Array(Velocity));Root->SetArrayField(TEXT("normal"),Array(FVector(0,1,0)));
    const TSharedPtr<FJsonObject>* SuppliedRoot=nullptr;if(State->Geometry->TryGetObjectField(TEXT("root"),SuppliedRoot))Root=*SuppliedRoot;
    Input->SetObjectField(TEXT("root"),Root);Input->SetArrayField(TEXT("travelVelocity"),Array(FVector(Velocity.X,0,Velocity.Z)));Input->SetNumberField(TEXT("rootYaw"),Source->GetArrayField(TEXT("rootYawDegrees"))[1]->AsNumber());
    Input->SetArrayField(TEXT("previousRoot"),Array(ProphecyThrow::FromUnrealPoint(Space.InverseTransformPosition(Previous.RootWorld))));
    TUniquePtr<FProphecyFootIKVM> VM;if(!Preparation.Warm->Take(State->NN,VM,Error))return false;
    FString Reply;if(!State->Runtime.EnablePrepared(MoveTemp(VM),Json(Input),Reply,Error)){Preparation.ActivationError=Error;return false;}
    FFrame Prior,Now;Prior.Root=Previous.RootWorld;Prior.Velocity=(Current.RootWorld-Previous.RootWorld)*30;Prior.Yaw=Previous.HeadingWorld.Rotation().Yaw;Prior.Tick=-4;
    Now.Root=Current.RootWorld;Now.Velocity=Prior.Velocity;Now.Yaw=Current.HeadingWorld.Rotation().Yaw;Now.Tick=0;
    Prior.Pose.Add(FTransform(FQuat::Identity,Previous.RootWorld));Prior.Pose.Append(Previous.BodiesWorld);Now.Pose.Add(FTransform(FQuat::Identity,Current.RootWorld));Now.Pose.Append(Current.BodiesWorld);
    State->Previous30=Prior;
    // Seed the actual half-step history, so disabling during the first interval
    // still has a genuine30Hz pair rather than a duplicated or stale endpoint.
    for(int32 Tick=-4;Tick<0;++Tick)
    {
        const double Alpha=(Tick+4)/4.;FFrame F=Prior;F.Tick=Tick;F.Root=FMath::Lerp(Prior.Root,Now.Root,Alpha);F.Yaw=Prior.Yaw+FMath::FindDeltaAngleDegrees(Prior.Yaw,Now.Yaw)*Alpha;F.Pose.SetNum(26);
        for(int32 I=0;I<26;++I){const int32 Parent=Parents[I];const auto P=Parent<0?Prior.Pose[I]:Prior.Pose[I].GetRelativeTransform(Prior.Pose[Parent]);const auto C=Parent<0?Now.Pose[I]:Now.Pose[I].GetRelativeTransform(Now.Pose[Parent]);FTransform Local;Local.Blend(P,C,Alpha);F.Pose[I]=Parent<0?Local:Local*F.Pose[Parent];}State->History.Add(MoveTemp(F));
    }
    if(!State->Runtime.Step(TEXT("{\"op\":\"tick\",\"currentTick\":0,\"ticks\":1}"),Reply,Error)||!Consume(*State,Reply,Error)){Preparation.ActivationError=Error;return false;}
    Pending.Remove(A);States.Add(A,MoveTemp(State));RefreshCleanup();return true;
}
bool Tick(AProphecyAgent* A,const FVector& Desired,TConstArrayView<FTransform> Window,uint64 GameTick,FString& Error)
{
    using namespace Detail;check(IsInGameThread());Error.Reset();auto* Found=States.Find(A);if(!Found){Error=TEXT("Live surface owner is disabled");return false;}auto& S=**Found;
    if(!SupportedUpper(A,Error))return false;
    if(S.LastGameTick==GameTick)return true;if(S.LastGameTick!=MAX_uint64&&GameTick!=S.LastGameTick+1){Error=TEXT("Live surface game clock skipped; reseed from actual history");return false;}
    if(Desired.ContainsNaN()||Window.Num()!=10){Error=TEXT("Live surface tick needs finite desired velocity and10 controller headings");return false;}
    auto Input=MakeShared<FJsonObject>();Input->SetStringField(TEXT("op"),TEXT("tick"));Input->SetNumberField(TEXT("currentTick"),S.NextTick);Input->SetNumberField(TEXT("ticks"),2);
    const FVector V=ProphecyThrow::FromUnrealPoint(S.Space.InverseTransformVectorNoScale(Desired));Input->SetArrayField(TEXT("travelVelocity"),Array(V));Input->SetNumberField(TEXT("commandSpeed"),FVector2D(V.X,V.Z).Size());
    FValues Headings;double Prior=0;for(int32 I=0;I<Window.Num();++I)
    {
        if(Window[I].ContainsNaN()){Error=TEXT("Nonfinite controller heading");return false;}
        const FVector H=ProphecyThrow::FromUnrealPoint(S.Space.InverseTransformVectorNoScale(Window[I].GetRotation().GetForwardVector()));
        if(FMath::Square(H.X)+FMath::Square(H.Z)<1.e-12){Error=TEXT("Controller heading cannot be vertical");return false;}
        double Yaw=FMath::RadiansToDegrees(FMath::Atan2(H.X,H.Z));if(I)Yaw=Prior+FMath::FindDeltaAngleDegrees(Prior,Yaw);Prior=Yaw;
        auto Row=MakeShared<FJsonObject>();Row->SetNumberField(TEXT("yaw"),Yaw);if(I==0)Row->SetNumberField(TEXT("time"),S.Current.Tick/120.-1./30.);Headings.Add(MakeShared<FJsonValueObject>(Row));
    }
    Input->SetArrayField(TEXT("futureRoots"),Headings);
    if(S.GeometryDirty){Input->SetArrayField(TEXT("surfaces"),S.Geometry->GetArrayField(TEXT("surfaces")));const FValues* Nav=nullptr;if(S.Geometry->TryGetArrayField(TEXT("rootSurfaces"),Nav))Input->SetArrayField(TEXT("rootSurfaces"),*Nav);Input->SetNumberField(TEXT("surfaceRevision"),double(S.GeometryRevision));}
    FString Reply;if(!S.Runtime.Step(Json(Input),Reply,Error)||!Consume(S,Reply,Error)){S.Error=Error;return false;}
    S.LastGameTick=GameTick;S.GeometryDirty=false;S.Error.Reset();return true;
}
bool UpdateGeometry(AProphecyAgent* A,const FString& Text,FString& Error)
{
    check(IsInGameThread());auto* Found=Detail::States.Find(A);if(!Found){Error=TEXT("Live surface owner is disabled");return false;}
    TSharedPtr<FJsonObject> Geometry;if(!Detail::ReadGeometry(Text,Geometry,Error))return false;auto& S=**Found;S.Geometry=MoveTemp(Geometry);S.GeometryDirty=true;++S.GeometryRevision;return true;
}
bool Root(AProphecyAgent* A,FVector& P,float& Y,FVector* V)
{const auto* Found=Detail::States.Find(A);if(!Found)return false;const auto& F=(*Found)->Current;P=F.Root;Y=F.Yaw;if(V)*V=F.Velocity;return true;}
bool History(AProphecyAgent* A,FVector& P,float& Y)
{const auto* Found=Detail::States.Find(A);if(!Found)return false;P=(*Found)->Previous30.Root;Y=(*Found)->Previous30.Yaw;return true;}
bool Apply(AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local,const FTransform& World)
{
    const auto* Found=Detail::States.Find(A);if(!Found||Names.Num()!=Parents.Num()||Names.Num()!=Previous.Num()||Names.Num()!=Current.Num()||Names.Num()!=Local.Num())return false;
    const auto& Pose=(*Found)->Current.Pose;const auto& Prior=(*Found)->Previous30.Pose;TArray<int32,TInlineAllocator<26>> Mapping;for(FName Name:Names){int32 Index=INDEX_NONE;for(int32 K=0;K<26;++K)if(Detail::Names[K]==Name){Index=K;break;}if(Index<0||!Prior.IsValidIndex(Index))return false;Mapping.Add(Index);}
    for(int32 I=0;I<Names.Num();++I){Previous[I]=Prior[Mapping[I]].GetRelativeTransform(World);Current[I]=Pose[Mapping[I]].GetRelativeTransform(World);}
    for(int32 I=0;I<Names.Num();++I)Local[I]=Parents[I]<0?Current[I]:Current[I].GetRelativeTransform(Current[Parents[I]]);return true;
}
FString Diagnostics(const AProphecyAgent* A){const auto* Found=Detail::States.Find(const_cast<AProphecyAgent*>(A));return Found?(*Found)->Json:FString();}
double LastSeconds(const AProphecyAgent* A){const auto* Found=Detail::States.Find(const_cast<AProphecyAgent*>(A));return Found?(*Found)->Runtime.LastSeconds():0.;}
bool Status(const AProphecyAgent* A,FProphecyFootIKLiveState& Out)
{
    Out={};const auto* Found=Detail::States.Find(const_cast<AProphecyAgent*>(A));
    if(!Found)
    {
        const auto* P=Detail::Pending.Find(const_cast<AProphecyAgent*>(A));if(!P)return false;
        Out.Enabled=true;if(!(*P)->ActivationError.IsEmpty()){Out.Error=(*P)->ActivationError;return true;}
        const auto State=(*P)->Warm->State(Out.Error);
        Out.Preparing=State!=FProphecyFootIKPreparation::EState::Failed;return true;
    }
    const auto& S=**Found;
    Out.Enabled=true;Out.Ready=S.Error.IsEmpty();Out.AppliedFrame=Out.PreparedThroughFrame=S.Current.Tick/2;Out.SolveMilliseconds=float(S.Runtime.LastSeconds()*1000);Out.Error=S.Error;Out.DiagnosticsJson=S.Json;return true;
}
bool ReadPolicyHandoff(AProphecyAgent* A,FPolicyHandoff& Out,FString& Error)
{
    using namespace Detail;check(IsInGameThread());Out={};Error.Reset();auto* Found=States.Find(A);if(!Found){Error=TEXT("Live surface owner is disabled");return false;}auto& S=**Found;
    FString Text;if(!S.Runtime.Command(TEXT("{\"op\":\"policyHandoff\"}"),Text,Error))return false;
    const auto Value=Parse(Text);if(!Value){Error=TEXT("Invalid surface policy handoff");return false;}
    const TCHAR* PoseKeys[]={TEXT("previous"),TEXT("current")};const TCHAR* RootKeys[]={TEXT("previousRoot"),TEXT("root")};const TCHAR* YawKeys[]={TEXT("previousYaw"),TEXT("yaw")};
    ProphecyFootIKLive::FSourceSample* Samples[]={&Out.Previous,&Out.Current};
    for(int32 Row=0;Row<2;++Row)
    {
        const TSharedPtr<FJsonObject>* P=nullptr;const FValues *Points=nullptr,*Quats=nullptr,*Root=nullptr;double Yaw=0;
        if(!Value->TryGetObjectField(PoseKeys[Row],P)||!(*P)->TryGetArrayField(TEXT("points"),Points)||!(*P)->TryGetArrayField(TEXT("q"),Quats)||Points->Num()!=26||Quats->Num()!=26
           ||!Value->TryGetArrayField(RootKeys[Row],Root)||Root->Num()!=3||!Value->TryGetNumberField(YawKeys[Row],Yaw))
        {Error=TEXT("Incomplete actual surface policy history");return false;}
        auto& Sample=*Samples[Row];const FVector ActualRoot=Vector(*Root),VirtualRoot=Vector((*Points)[0]->AsArray());Sample.RootWorld=S.Space.TransformPosition(ProphecyThrow::ToUnrealPoint(ActualRoot));
        const double Angle=FMath::DegreesToRadians(Yaw);Sample.HeadingWorld=S.Space.TransformVectorNoScale(ProphecyThrow::ToUnrealPoint(FVector(FMath::Sin(Angle),0,FMath::Cos(Angle)))).GetSafeNormal();
        for(int32 I=1;I<26;++I)
        {
            if((*Points)[I]->AsArray().Num()!=3||(*Quats)[I]->AsArray().Num()!=4){Error=TEXT("Invalid raw policy bone");return false;}
            const FVector Position=ActualRoot+Vector((*Points)[I]->AsArray())-VirtualRoot;
            const FTransform World=ProphecyThrow::ToUnreal(FTransform(Quaternion((*Quats)[I]->AsArray()),Position))*S.Space;
            if(World.ContainsNaN()){Error=TEXT("Nonfinite raw policy handoff");return false;}Sample.BodiesWorld.Add(World);
        }
    }
    double Tick=0;const FValues* Velocity=nullptr;if(!Value->TryGetNumberField(TEXT("tick"),Tick)||!Value->TryGetArrayField(TEXT("velocity"),Velocity)||Velocity->Num()!=3){Error=TEXT("Missing policy handoff carrier");return false;}
    Out.Tick=int32(Tick);Out.VelocityWorld=S.Space.TransformVectorNoScale(ProphecyThrow::ToUnrealPoint(Vector(*Velocity)));Value->TryGetBoolField(TEXT("sliding"),Out.WasSliding);Out.Json=MoveTemp(Text);return true;
}
}
