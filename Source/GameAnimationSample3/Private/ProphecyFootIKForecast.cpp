#include "ProphecyFootIKForecast.h"
#include "ProphecyFootIKNN.h"
#include "ProphecyFootIKPreparation.h"
#include "ProphecyThrowMath.h"
#include "Dom/JsonObject.h"
#include "HAL/CriticalSection.h"
#include "HAL/PlatformTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeLock.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonSerializer.h"

namespace
{
using FValues=TArray<TSharedPtr<FJsonValue>>;
constexpr int32 ForecastFrames=37,ForecastRootCount=ForecastFrames+9;
const TCHAR* ForecastNames[]={TEXT("root"),TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
FString ForecastJson(const TSharedPtr<FJsonObject>& O){FString S;FJsonSerializer::Serialize(O.ToSharedRef(),TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&S));return S;}
TSharedPtr<FJsonObject> ForecastParse(const FString& S){TSharedPtr<FJsonObject> O;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S),O);return O;}
FValues ForecastVector(const FVector& P){return {MakeShared<FJsonValueNumber>(P.X),MakeShared<FJsonValueNumber>(P.Y),MakeShared<FJsonValueNumber>(P.Z)};}
FValues ForecastAxes(const FQuat& Q)
{
 const double X=Q.X,Y=Q.Y,Z=Q.Z,W=Q.W;
 return {MakeShared<FJsonValueArray>(ForecastVector(FVector(1-2*(Y*Y+Z*Z),2*(X*Y+W*Z),2*(X*Z-W*Y)))),MakeShared<FJsonValueArray>(ForecastVector(FVector(2*(X*Y-W*Z),1-2*(X*X+Z*Z),2*(Y*Z+W*X)))),MakeShared<FJsonValueArray>(ForecastVector(FVector(2*(X*Z+W*Y),2*(Y*Z-W*X),1-2*(X*X+Y*Y))))};
}
TSharedPtr<FJsonObject> ForecastSeed(const ProphecyFootIKLive::FSourceSample& S,const FTransform& Space)
{
 FVector Root=ProphecyThrow::FromUnrealPoint(Space.InverseTransformPosition(S.RootWorld));const double NavigationY=Root.Y;Root.Y=0;
 FValues Points={MakeShared<FJsonValueArray>(ForecastVector(Root))},Basis={MakeShared<FJsonValueArray>(ForecastAxes(FQuat::Identity))};
 for(const auto& Body:S.BodiesWorld){const auto B=ProphecyFootIKLive::ToSolverBody(Body,Space);FVector Position=B.GetLocation();Position.Y-=NavigationY;Points.Add(MakeShared<FJsonValueArray>(ForecastVector(Position)));Basis.Add(MakeShared<FJsonValueArray>(ForecastAxes(B.GetRotation())));}
 auto P=MakeShared<FJsonObject>();P->SetArrayField(TEXT("points"),Points);P->SetArrayField(TEXT("axes"),Basis);return P;
}
}
struct FProphecyFootIKForecast::FImpl
{
    TSharedPtr<FProphecyFootIKNN,ESPMode::ThreadSafe> NN;
    TUniquePtr<FProphecyFootIKPreparation> Warm;
    bool Prepared=false;
    FThreadSafeBool Stopped=false;
    FCriticalSection Mutex,StateMutex;
    ~FImpl(){FProphecyFootIKPreparation::Retire(MoveTemp(NN),TUniquePtr<FProphecyFootIKVM>());}
};
FProphecyFootIKForecast::FProphecyFootIKForecast():Impl(MakeUnique<FImpl>()){}
FProphecyFootIKForecast::~FProphecyFootIKForecast(){Cancel();}
void FProphecyFootIKForecast::Cancel()
{
    Impl->Stopped=true;FScopeLock Lock(&Impl->StateMutex);
    if(Impl->Warm)Impl->Warm->Cancel();if(Impl->NN)Impl->NN->Cancel();
}
bool FProphecyFootIKForecast::Ready(FString& Error)
{
    Error.Reset();FScopeLock Lock(&Impl->StateMutex);
    if(Impl->Stopped){Error=TEXT("Foot IK forecast canceled");return false;}
    if(Impl->NN)return true;if(!Impl->Warm)return false;
    if(Impl->Warm->State(Error)!=FProphecyFootIKPreparation::EState::Ready)return false;
    TUniquePtr<FProphecyFootIKVM> Unused;return Impl->Warm->Take(Impl->NN,Unused,Error);
}
bool FProphecyFootIKForecast::Prepare(const FString& ContractPath,FString& Error)
{
    Error.Reset();if(!IsInGameThread()){Error=TEXT("Prepare the live Foot IK forecast on the game thread");return false;}
    if(Impl->Prepared){Error=TEXT("Create a fresh Foot IK forecaster for a new configuration");return false;}
    const FString Path=FPaths::IsRelative(ContractPath)?FPaths::ProjectDir()/ContractPath:ContractPath;FString Text;
    if(!FFileHelper::LoadFileToString(Text,*Path)){Error=TEXT("Cannot read the active game NN runtime contract: ")+Path;return false;}
    const auto Metadata=ForecastParse(Text);FString Hash;
    if(!Metadata||!Metadata->TryGetStringField(TEXT("checkpoint_sha256"),Hash)||!Hash.Equals(TEXT("0F2565AC72C5209153CBD910135209487F9EF8A0E234ED0C6D99DF2FF30A299E"),ESearchCase::IgnoreCase))
    {Error=TEXT("Live Foot IK forecasting requires the active Run181751 checkpoint; the selected game checkpoint differs");return false;}
    // Forward describes the fixed course coordinate convention, not locomotion
    // facing. Actual yaw and all future turns are supplied on every inference.
    Impl->Warm=MakeUnique<FProphecyFootIKPreparation>(TEXT("{\"gait\":\"run\",\"direction\":\"forward\",\"liveLowerOnly\":true}"),false,EProphecyFootIKNNWarmup::Continuation);Impl->Prepared=true;return true;
}
bool FProphecyFootIKForecast::ExtendRoots(const FProphecyFootIKForecastInput& I,TArray<FTransform>& Out,FString& Error)
{
    Error.Reset();if(I.RootWorldWindow.Num()!=10||I.CurrentTick<4||I.CurrentTick%4||I.CourseWorld.ContainsNaN()||!I.CourseWorld.GetScale3D().Equals(FVector::OneVector,1.e-8))
    {Error=TEXT("Live forecast requires actual previous/current/eight future30Hz roots and a fixed unit-scale course frame");return false;}
    for(const auto& Root:I.RootWorldWindow)if(Root.ContainsNaN()){Error=TEXT("Nonfinite real root window");return false;}
    if(!I.NavRootWindow.IsEmpty())
    {
        if(I.NavRootWindow.Num()!=ForecastRootCount){Error=TEXT("Navigation forecast must contain all46 root samples");return false;}
        for(int32 Row=0;Row<I.NavRootWindow.Num();++Row)
            if(I.NavRootWindow[Row].ContainsNaN()||(Row<10&&!I.NavRootWindow[Row].Equals(I.RootWorldWindow[Row],0)))
            {Error=TEXT("Navigation forecast changed an actual/controller root or supplied a nonfinite sample");return false;}
        Out=I.NavRootWindow;return true;
    }
    Out=I.RootWorldWindow;const FVector Delta=Out[9].GetLocation()-Out[8].GetLocation();
    const double Turn=FMath::FindDeltaAngleDegrees(Out[8].Rotator().Yaw,Out[9].Rotator().Yaw);
    while(Out.Num()<ForecastRootCount){FTransform Next=Out.Last();Next.SetLocation(Next.GetLocation()+Delta);FRotator Rotation=Next.Rotator();Rotation.Yaw+=Turn;Next.SetRotation(Rotation.Quaternion());Out.Add(Next);}return true;
}
bool FProphecyFootIKForecast::BuildRequest(const FProphecyFootIKForecastInput& I,FString& Out,FString& Error)
{
    TArray<FTransform> Roots;if(!ExtendRoots(I,Roots,Error))return false;
    for(const auto* S:{&I.Previous,&I.Current})
    {
        if(S->BodiesWorld.Num()!=25||S->RootWorld.ContainsNaN()){Error=TEXT("Forecast seeds must be the actual previous/current25-body poses");return false;}
        for(const auto& Body:S->BodiesWorld)if(Body.ContainsNaN()){Error=TEXT("Nonfinite actual NN history");return false;}
    }
    if(!I.Previous.RootWorld.Equals(Roots[0].GetLocation(),.001)||!I.Current.RootWorld.Equals(Roots[1].GetLocation(),.001))
    {Error=TEXT("Actual pose history and root-window timestamps do not match");return false;}
    auto R=MakeShared<FJsonObject>();FValues Positions,Yaws,BodyNames;double Prior=0;
    for(int32 Index=0;Index<Roots.Num();++Index)
    {
        // Navigation height is a separate carrier. The normal game NN receives
        // flat virtual roots, so the speculative copy must receive the same.
        // K's timed rootRows restores actual support elevation exactly once.
        FVector Position=ProphecyThrow::FromUnrealPoint(I.CourseWorld.InverseTransformPosition(Roots[Index].GetLocation()));Position.Y=0;
        Positions.Add(MakeShared<FJsonValueArray>(ForecastVector(Position)));
        const FVector H=ProphecyThrow::FromUnrealPoint(I.CourseWorld.InverseTransformVectorNoScale(Roots[Index].GetRotation().GetForwardVector()));
        if(FMath::Square(H.X)+FMath::Square(H.Z)<1.e-12){Error=TEXT("Controller heading cannot be vertical in the horizontal live forecast");return false;}
        double Yaw=FMath::RadiansToDegrees(FMath::Atan2(H.X,H.Z));if(Index)Yaw=Prior+FMath::FindDeltaAngleDegrees(Prior,Yaw);Prior=Yaw;Yaws.Add(MakeShared<FJsonValueNumber>(Yaw));
    }
    for(const auto* Name:ForecastNames)BodyNames.Add(MakeShared<FJsonValueString>(Name));
    R->SetStringField(TEXT("policy"),TEXT("run"));R->SetStringField(TEXT("gait"),I.Gait);R->SetStringField(TEXT("direction"),TEXT("forward"));R->SetNumberField(TEXT("frames"),ForecastFrames);R->SetBoolField(TEXT("reset"),true);R->SetArrayField(TEXT("names"),BodyNames);R->SetArrayField(TEXT("roots"),Positions);R->SetArrayField(TEXT("rootYawDegrees"),Yaws);R->SetArrayField(TEXT("seeds"),{MakeShared<FJsonValueObject>(ForecastSeed(I.Previous,I.CourseWorld)),MakeShared<FJsonValueObject>(ForecastSeed(I.Current,I.CourseWorld))});Out=ForecastJson(R);return true;
}
bool FProphecyFootIKForecast::Predict(const FProphecyFootIKForecastInput& I,FString& Out,FString& Error,FTiming* Timing,const TFunction<bool()>& Superseded)
{
    FScopeLock Lock(&Impl->Mutex);if(Timing)*Timing={};Error.Reset();if(!Impl->Prepared){Error=TEXT("Prepare the matching live NN forecast first");return false;}
    if(!Ready(Error))
    {
        if(!Error.IsEmpty()||!Impl->Warm||!Impl->Warm->Wait(Error)||!Ready(Error))return false;
    }
    double Started=Timing?FPlatformTime::Seconds():0;FString Request;if(!BuildRequest(I,Request,Error))return false;
    if(Timing)Timing->RequestSeconds=FPlatformTime::Seconds()-Started;
    TSharedPtr<FJsonObject> Source;if(!Impl->NN->GenerateResult(Request,Source,Error,Timing?&Timing->NN:nullptr,Superseded))return false;
    Started=Timing?FPlatformTime::Seconds():0;auto Command=ForecastParse(Request);
    if(Timing){Timing->DecodeSeconds=FPlatformTime::Seconds()-Started;Started=FPlatformTime::Seconds();}
    if(!Source||!Command){Error=TEXT("Invalid live forecast response");return false;}
    // Keep actual previous/current exactly, then the speculative continuation.
    // The selected game upper policy remains authoritative: this source's upper
    // body is only solver context, never a replacement for live presentation.
    const auto Old=Command->GetArrayField(TEXT("seeds"))[0]->AsObject();auto Previous=MakeShared<FJsonObject>();FValues Points,Axes;
    for(int32 J=1;J<26;++J){Points.Add(Old->GetArrayField(TEXT("points"))[J]);Axes.Add(Old->GetArrayField(TEXT("axes"))[J]);}Previous->SetArrayField(TEXT("points"),Points);Previous->SetArrayField(TEXT("axes"),Axes);
    auto Poses=Source->GetArrayField(TEXT("poses")),Roots=Source->GetArrayField(TEXT("roots"));FValues Yaw;
    Poses.Insert(MakeShared<FJsonValueObject>(Previous),0);Roots.Insert(Command->GetArrayField(TEXT("roots"))[0],0);
    for(int32 PoseIndex=0;PoseIndex<Poses.Num();++PoseIndex)Yaw.Add(Command->GetArrayField(TEXT("rootYawDegrees"))[PoseIndex]);
    auto Pins=Source->GetArrayField(TEXT("pins"));Pins.Insert(MakeShared<FJsonValueNull>(),0);Source->SetArrayField(TEXT("pins"),Pins);
    double Height=0,Travel=0;FVector Prior=FVector::ZeroVector;
    for(int32 Row=0;Row<Poses.Num();++Row)
    {
        auto Root=Roots[Row]->AsArray();const double Y=Root[1]->AsNumber();const FVector Position(Root[0]->AsNumber(),Y,Root[2]->AsNumber());if(Row)Travel+=FVector2D(Position.X-Prior.X,Position.Z-Prior.Z).Size();Prior=Position;
        Root[1]=MakeShared<FJsonValueNumber>(0);Roots[Row]=MakeShared<FJsonValueArray>(Root);
        auto Pose=Poses[Row]->AsObject();auto P=Pose->GetArrayField(TEXT("points"));for(auto& Value:P){auto V=Value->AsArray();V[1]=MakeShared<FJsonValueNumber>(V[1]->AsNumber()-Y);Value=MakeShared<FJsonValueArray>(V);}Pose->SetArrayField(TEXT("points"),P);Height+=P[0]->AsArray()[1]->AsNumber();
    }
    const double Duration=(Poses.Num()-1)/30.;auto Meta=MakeShared<FJsonObject>();Meta->SetNumberField(TEXT("commandSpeed"),Travel/Duration);Meta->SetNumberField(TEXT("referenceHeight"),Height/Poses.Num());Meta->SetNumberField(TEXT("facingDegrees"),0);Meta->SetNumberField(TEXT("totalDuration"),Duration);
    Source->SetArrayField(TEXT("poses"),Poses);Source->SetArrayField(TEXT("roots"),Roots);Source->SetArrayField(TEXT("rootYawDegrees"),Yaw);Source->SetObjectField(TEXT("directionMeta"),Meta);Source->SetNumberField(TEXT("duration"),Duration);Source->SetNumberField(TEXT("totalDuration"),Duration);Source->SetStringField(TEXT("gait"),I.Gait);Source->SetStringField(TEXT("source"),TEXT("actual game history + matched Run181751 speculative recurrence"));
    if(Timing){Timing->PostprocessSeconds=FPlatformTime::Seconds()-Started;Started=FPlatformTime::Seconds();}
    Out=ForecastJson(Source);if(Timing)Timing->SerializeSeconds=FPlatformTime::Seconds()-Started;return true;
}
