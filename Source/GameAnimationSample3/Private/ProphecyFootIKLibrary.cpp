#include "ProphecyFootIKLibrary.h"
#include "ProphecyFootIKOwner.h"
#include "ProphecyFootIKSurfaceOwner.h"
#include "ProphecyFootIKPlanner.h"
#include "ProphecyFootIKNN.h"
#include "ProphecyBodyflipRuntime.h"
#include "ProphecyThrowMath.h"
#include "ProphecyAgent.h"
#include "ProphecyThrowRuntime.h"
#include "ProphecyReachRuntime.h"
#include "ProphecyGetUp.h"
#include "ProphecySwordHolsterPose.h"
#include "Components/SkeletalMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "Serialization/JsonSerializer.h"

namespace ProphecyFootIK
{
static FString Json(const TSharedPtr<FJsonObject>& O){FString S;FJsonSerializer::Serialize(O.ToSharedRef(),TJsonWriterFactory<>::Create(&S));return S;}
static TSharedPtr<FJsonObject> Parse(const FString& S){TSharedPtr<FJsonObject> O;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S),O);return O;}
static TArray<TSharedPtr<FJsonValue>> Array(const FVector& V){return {MakeShared<FJsonValueNumber>(V.X),MakeShared<FJsonValueNumber>(V.Y),MakeShared<FJsonValueNumber>(V.Z)};}
static FVector Vector(const TArray<TSharedPtr<FJsonValue>>& V){return V.Num()==3?FVector(V[0]->AsNumber(),V[1]->AsNumber(),V[2]->AsNumber()):FVector::ZeroVector;}
static FQuat Quaternion(const TArray<TSharedPtr<FJsonValue>>& V){return V.Num()==4?FQuat(V[0]->AsNumber(),V[1]->AsNumber(),V[2]->AsNumber(),V[3]->AsNumber()):FQuat::Identity;}
static const TCHAR* BoneNames[]={TEXT("root"),TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
static const int32 RigParents[]={-1,0,1,2,3,4,5,6,7,8,9,6,11,12,13,6,15,16,1,18,19,20,1,22,23,24};
struct FActive
{
    FProphecyFootIKPlanner Planner;
    TSharedPtr<FProphecyFootIKNN,ESPMode::ThreadSafe> NN;
    FTransform Space=FTransform::Identity;
    TSharedPtr<FJsonObject> Settings;
    TArray<FName> Names;
    TArray<FTransform> Previous,Current;
    FProphecyFootIKState Status;
    int32 Cursor=0,Applied=-1,End=300;
    bool Playing=true;
    float InitialYaw=0,Yaw=0,PreviousYaw=0;
    FVector PreviousRoot=FVector::ZeroVector;
};
static TMap<TWeakObjectPtr<AProphecyAgent>,TUniquePtr<FActive>> States;
static TMap<TWeakObjectPtr<AProphecyAgent>,FString> Configurations;
static FDelegateHandle TickHandle,CleanupHandle;
static void Refresh();
static bool Conflicting(AProphecyAgent* A)
{
    FName Attack;bool Half=false,Armed=false,Hit=false;int32 Frame=0;ProphecySwordHolsterPose::FStatus Holster;
    return ProphecyBodyflip::Active(A)||ProphecyThrow::Active(A)||A->GetNNAttackState(Attack,Half,Armed,Hit,Frame)||A->IsNNAnimationLayerActive()||ProphecyReach::Active(A)||ProphecyGetUp::IsActive(A)||(ProphecySwordHolsterPose::Status(A,Holster)&&!Holster.Finished);
}
static float Heading(const FActive& S,const TSharedPtr<FJsonObject>& Frame)
{
    const TArray<TSharedPtr<FJsonValue>>* H=nullptr;if(!Frame->TryGetArrayField(TEXT("rootHeading"),H))return S.InitialYaw;
    const FVector Forward=S.Space.TransformVectorNoScale(ProphecyThrow::ToUnrealPoint(Vector(*H)));
    if(FMath::Square(Forward.X)+FMath::Square(Forward.Y)<1.e-12)return S.Yaw;
    return float(FMath::RadiansToDegrees(FMath::Atan2(Forward.Y,Forward.X)));
}
static bool ReadPose(FActive& S,const TSharedPtr<FJsonObject>& Frame,TArray<FTransform>& Pose,FString& Error)
{
    const TSharedPtr<FJsonObject>* P=nullptr;const TArray<TSharedPtr<FJsonValue>>* Points=nullptr;const TArray<TSharedPtr<FJsonValue>>* Q=nullptr;
    if(!Frame->TryGetObjectField(TEXT("pose"),P)||!(*P)->TryGetArrayField(TEXT("points"),Points)||!(*P)->TryGetArrayField(TEXT("q"),Q)||Points->Num()!=26||Q->Num()!=26)
    {Error=TEXT("Foot IK returned an incomplete rig");return false;}
    Pose.SetNum(26);
    for(int32 I=0;I<26;++I){Pose[I]=ProphecyThrow::ToUnreal(FTransform(Quaternion((*Q)[I]->AsArray()),Vector((*Points)[I]->AsArray())))*S.Space;if(Pose[I].ContainsNaN()){Error=TEXT("Foot IK produced a nonfinite pose");return false;}}
    return true;
}
static bool Sample(FActive& S,int32 Cursor,FString& Error)
{
    FString Text;if(!S.Planner.Frame(Cursor*2,Text))return false;
    auto Frame=Parse(Text);if(!Frame||!ReadPose(S,Frame,S.Current,Error))return false;
    S.Previous=S.Current;S.Status.Root=S.Space.TransformPosition(ProphecyThrow::ToUnrealPoint(Vector(Frame->GetArrayField(TEXT("root")))));
    S.PreviousRoot=S.Status.Root;S.PreviousYaw=S.Yaw=Heading(S,Frame);
    FString Prior;if(S.Planner.Frame(FMath::Max(0,Cursor*2-4),Prior))
    {auto Old=Parse(Prior);if(!Old||!ReadPose(S,Old,S.Previous,Error))return false;S.PreviousRoot=S.Space.TransformPosition(ProphecyThrow::ToUnrealPoint(Vector(Old->GetArrayField(TEXT("root")))));S.PreviousYaw=Heading(S,Old);}
    S.Status.Velocity=(S.Status.Root-S.PreviousRoot)*30.;S.Status.Phase=TEXT("FOOT IK");
    const TSharedPtr<FJsonObject>* Surface=nullptr;if(Frame->TryGetObjectField(TEXT("surface"),Surface))
    {const TArray<TSharedPtr<FJsonValue>>* V=nullptr;if((*Surface)->TryGetArrayField(TEXT("velocity"),V))S.Status.Velocity=S.Space.TransformVector(ProphecyThrow::ToUnrealPoint(Vector(*V)));(*Surface)->TryGetStringField(TEXT("mode"),S.Status.Phase);}
    S.Cursor=S.Applied=Cursor;S.Status.Frame=Cursor;S.Status.Preparing=false;S.Status.Playing=S.Playing;S.Status.DiagnosticsJson=Text;return true;
}
static bool Prepare(FActive& S,FString& Error)
{
    S.Settings->SetNumberField(TEXT("totalDuration"),FMath::Max(5.,S.End/60.));
    auto NN=MakeShared<FProphecyFootIKNN,ESPMode::ThreadSafe>();if(!NN->Prepare(Json(S.Settings),Error))return false;
    auto Input=MakeShared<FJsonObject>();Input->SetObjectField(TEXT("settings"),S.Settings);
    TArray<TSharedPtr<FJsonValue>> Parents;for(int32 Parent:RigParents)Parents.Add(MakeShared<FJsonValueNumber>(Parent));Input->SetArrayField(TEXT("parents"),Parents);
    FString Terrain=TEXT("flat");S.Settings->TryGetStringField(TEXT("terrain"),Terrain);const TSharedPtr<FJsonObject>* Layouts=nullptr;
    const bool Coupled=Terrain==TEXT("incline")||(S.Settings->TryGetObjectField(TEXT("platformLayouts"),Layouts)&&(*Layouts)->HasField(Terrain));Input->SetBoolField(TEXT("coupled"),Coupled);
    Input->SetBoolField(TEXT("handoff"),!Coupled);
    if(!S.Planner.Prepare(Json(Input),[NN](FString& Source,FString& E){return NN->Initialize(Source,E);},[NN](const FString& Request,FString& Response,FString& E){return NN->Generate(Request,Response,E);},S.End/60.,Error,[NN]{NN->Cancel();}))return false;
    S.NN=MoveTemp(NN);S.Status.Preparing=true;S.Status.Playing=false;S.Status.Error.Reset();S.Applied=-1;return true;
}
static void Tick(UWorld* W,ELevelTick Type,float Delta)
{
    if(!W||W->IsPaused()||Type!=LEVELTICK_All||Delta<=0)return;
    for(auto It=States.CreateIterator();It;++It)
    {
        auto* A=It.Key().Get();if(!A||A->IsActorBeingDestroyed()){It.RemoveCurrent();continue;}if(A->GetWorld()!=W)continue;
        if(Conflicting(A)){It.RemoveCurrent();continue;}auto& S=*It.Value();if(!S.Status.Error.IsEmpty())continue;
        FString Error;if(!S.Planner.Poll(Error)){S.Playing=false;S.Status.Playing=false;S.Status.Preparing=false;S.Status.Error=Error;UE_LOG(LogTemp,Error,TEXT("Foot IK preparation failed: %s"),*Error);continue;}
        if(S.Planner.Busy())continue;
        S.Status.SolveMilliseconds=float(S.Planner.LastSeconds()*1000);
        const int32 Next=S.Playing&&S.Applied>=0?FMath::Min(S.Cursor+1,S.End):S.Cursor;
        if((Next!=S.Applied||S.Status.Preparing)&&!Sample(S,Next,Error)){S.Playing=false;S.Status.Playing=false;S.Status.Error=Error.IsEmpty()?TEXT("Foot IK course frame is unavailable"):Error;}
        if(Next>=S.End){S.Playing=false;S.Status.Playing=false;}
    }
    Refresh();
}
static void Refresh()
{
    if(States.IsEmpty()){FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);TickHandle.Reset();FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset();return;}
    if(!TickHandle.IsValid())TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
    if(!CleanupHandle.IsValid())CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool){for(auto It=States.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();for(auto It=Configurations.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();Refresh();});
}
bool AnyActive(){return !States.IsEmpty()||ProphecyFootIKSurface::AnyActive();}
bool HasCallbacks(){return TickHandle.IsValid()||CleanupHandle.IsValid();}
bool Active(const AProphecyAgent* A){return (!States.IsEmpty()&&States.Contains(const_cast<AProphecyAgent*>(A)))||ProphecyFootIKSurface::Active(A);}
void Remove(AProphecyAgent* A){States.Remove(A);ProphecyFootIKSurface::Remove(A);Refresh();}
bool Root(AProphecyAgent* A,FVector& P,float& Y,FVector* V){const auto* S=States.Find(A);if(!S)return ProphecyFootIKSurface::Root(A,P,Y,V);P=(*S)->Status.Root;Y=(*S)->Yaw;if(V)*V=(*S)->Playing&&!(*S)->Status.Preparing?(*S)->Status.Velocity:FVector::ZeroVector;return true;}
bool History(AProphecyAgent* A,FVector& P,float& Y){const auto* S=States.Find(A);if(!S)return ProphecyFootIKSurface::History(A,P,Y);const bool Moving=(*S)->Playing&&!(*S)->Status.Preparing;P=Moving?(*S)->PreviousRoot:(*S)->Status.Root;Y=Moving?(*S)->PreviousYaw:(*S)->Yaw;return true;}
bool Apply(AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local,const FTransform& World)
{
    auto* Found=States.Find(A);if(!Found)return ProphecyFootIKSurface::Apply(A,Names,Parents,Previous,Current,Local,World);const auto& S=**Found;
    if(Names.Num()!=Previous.Num()||Names.Num()!=Current.Num()||Names.Num()!=Local.Num()||Names.Num()!=Parents.Num())return false;
    for(int32 I=0;I<Names.Num();++I){const int32 K=S.Names.IndexOfByKey(Names[I]);if(K<0)return false;Previous[I]=(S.Playing&&!S.Status.Preparing?S.Previous[K]:S.Current[K]).GetRelativeTransform(World);Current[I]=S.Current[K].GetRelativeTransform(World);Local[I]=Parents[I]<0?Current[I]:Current[I].GetRelativeTransform(Current[Parents[I]]);}return true;
}
}

bool UProphecyFootIKLibrary::SetFootIKEnabled(AProphecyAgent* A,bool Enabled,FString& Error)
{
    using namespace ProphecyFootIK;Error.Reset();
    if(!Enabled){Remove(A);return true;}if(Active(A))return true;
    if(!IsValid(A)||!A->GetWorld()||!A->GetWorld()->IsGameWorld()||!A->HasValidAgentHandle()||!A->GetPoseReferenceMesh()){Error=TEXT("A registered live Prophecy agent is required");return false;}
    if(Conflicting(A)){Error=TEXT("Finish this agent's current Bodyflip, attack, throw, get-up, reach or sword action first");return false;}
    auto S=MakeUnique<FActive>();const FString* Config=Configurations.Find(A);S->Settings=Parse(Config?*Config:TEXT("{\"gait\":\"walk\",\"terrain\":\"flat\",\"enabled\":true,\"trimOut\":5}"));if(!S->Settings){Error=TEXT("Invalid Foot IK settings");return false;}
    S->Settings->SetBoolField(TEXT("enabled"),true);double End=5;S->Settings->TryGetNumberField(TEXT("trimOut"),End);if(!FMath::IsFinite(End)||End<1./60||End>600){Error=TEXT("Foot IK trimOut must be between1frame and600seconds");return false;}S->End=FMath::RoundToInt(End*60);
    S->Space=(A->bManualNNPoseApplication?A->GetAgentMesh()->GetRelativeTransform():A->GetAuthoredMeshRelativeTransform())*A->GetActorTransform();
    const FVector Scale=S->Space.GetScale3D();if(Scale.GetMin()<=0||Scale.GetMax()-Scale.GetMin()>1.e-6){Error=TEXT("Foot IK requires a positive uniform authored mesh scale");return false;}
    for(const TCHAR* Name:BoneNames){S->Names.Add(FName(Name));S->Current.Add(A->GetPoseReferenceMesh()->GetSocketTransform(FName(Name),RTS_World));}S->Previous=S->Current;
    S->Status.Enabled=true;S->Status.Root=S->PreviousRoot=A->GetRootLowPoint();S->InitialYaw=S->PreviousYaw=S->Yaw=float(A->GetActorRotation().Yaw);
    if(!Prepare(*S,Error))return false;States.Add(A,MoveTemp(S));Refresh();return true;
}
bool UProphecyFootIKLibrary::ConfigureFootIK(AProphecyAgent* A,const FString& SettingsJson,FString& Error)
{
    using namespace ProphecyFootIK;Error.Reset();auto Settings=Parse(SettingsJson.IsEmpty()?TEXT("{\"gait\":\"walk\",\"terrain\":\"flat\",\"enabled\":true,\"trimOut\":5}"):SettingsJson);
    if(!IsValid(A)||!Settings){Error=TEXT("A valid agent and Foot IK settings object are required");return false;}
    double End=5;Settings->TryGetNumberField(TEXT("trimOut"),End);if(!FMath::IsFinite(End)||End<1./60||End>600){Error=TEXT("Invalid Foot IK course horizon");return false;}
    if(auto* Found=States.Find(A)){auto& S=**Found;const auto Old=S.Settings;const int32 OldEnd=S.End;S.Settings=Settings;S.End=FMath::Max(S.Cursor,FMath::RoundToInt(End*60));if(!Prepare(S,Error)){S.Settings=Old;S.End=OldEnd;return false;}}
    Configurations.Add(A,Json(Settings));return true;
}
bool UProphecyFootIKLibrary::PauseFootIK(AProphecyAgent* A,bool Paused){auto* Found=ProphecyFootIK::States.Find(A);if(!Found)return false;(*Found)->Playing=!Paused;(*Found)->Status.Playing=!Paused&&!(*Found)->Status.Preparing;return true;}
bool UProphecyFootIKLibrary::SeekFootIK(AProphecyAgent* A,int32 Frame,FString& Error){using namespace ProphecyFootIK;Error.Reset();auto* Found=States.Find(A);if(!Found||Frame<0||Frame>(*Found)->End){Error=TEXT("Foot IK seek must stay inside the configured course; extend trimOut through Configure Foot IK first");return false;}auto& S=**Found;S.Cursor=Frame;if(S.Planner.Busy())return true;if(Sample(S,Frame,Error))return true;if(!Error.IsEmpty())return false;S.Status.Preparing=true;return S.Planner.Extend(Frame/60.,Error);}
bool UProphecyFootIKLibrary::GetFootIKState(AProphecyAgent* A,FProphecyFootIKState& Out){const auto* Found=ProphecyFootIK::States.Find(A);if(!Found){Out={};return false;}Out=(*Found)->Status;if(!Out.Playing||Out.Preparing)Out.Velocity=FVector::ZeroVector;return true;}
bool UProphecyFootIKLibrary::SetFootIKPlatforms(AProphecyAgent* A,const TArray<FTransform>& Transforms,const TArray<FVector>& Sizes,FString& Error)
{
    using namespace ProphecyFootIK;auto* Found=States.Find(A);if(!Found||Transforms.Num()!=Sizes.Num()||Transforms.Num()>128){Error=TEXT("Enabled Foot IK and equal platform transforms/sizes (maximum128) required");return false;}auto& S=**Found;TArray<TSharedPtr<FJsonValue>> Platforms;
    for(int32 I=0;I<Transforms.Num();++I){if(Transforms[I].ContainsNaN()||Sizes[I].ContainsNaN()||Sizes[I].GetMin()<=0){Error=TEXT("Platform values must be finite and positive");return false;}auto P=MakeShared<FJsonObject>();P->SetStringField(TEXT("id"),FString::Printf(TEXT("native%d"),I));P->SetArrayField(TEXT("position"),Array(ProphecyThrow::FromUnrealPoint(S.Space.InverseTransformPosition(Transforms[I].GetLocation()))));const FQuat Q=S.Space.GetRotation().Inverse()*Transforms[I].GetRotation();P->SetArrayField(TEXT("rotation"),{MakeShared<FJsonValueNumber>(-Q.X),MakeShared<FJsonValueNumber>(-Q.Z),MakeShared<FJsonValueNumber>(-Q.Y),MakeShared<FJsonValueNumber>(Q.W)});P->SetArrayField(TEXT("size"),Array(ProphecyThrow::FromUnrealPoint(Sizes[I]*Transforms[I].GetScale3D().GetAbs()/S.Space.GetScale3D().X)));Platforms.Add(MakeShared<FJsonValueObject>(P));}
    auto Settings=Parse(Json(S.Settings));const TSharedPtr<FJsonObject>* Existing=nullptr;auto Layouts=Settings->TryGetObjectField(TEXT("platformLayouts"),Existing)?Parse(Json(*Existing)):MakeShared<FJsonObject>();FString Terrain=TEXT("flat");Settings->TryGetStringField(TEXT("terrain"),Terrain);Layouts->SetArrayField(Terrain,Platforms);Settings->SetObjectField(TEXT("platformLayouts"),Layouts);return ConfigureFootIK(A,Json(Settings),Error);
}
