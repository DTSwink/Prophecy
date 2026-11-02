#include "ProphecyFootIKRootBridge.h"
#include "ProphecyFootIKVM.h"
#include "ProphecyThrowMath.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Policies/CondensedJsonPrintPolicy.h"

namespace
{
using FRootBridgeValues=TArray<TSharedPtr<FJsonValue>>;
TSharedPtr<FJsonObject> RootBridgeParse(const FString& Text)
{
    TSharedPtr<FJsonObject> Object;
    return FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Object)?Object:nullptr;
}
FString RootBridgeJson(const TSharedPtr<FJsonObject>& Object)
{
    FString Text;FJsonSerializer::Serialize(Object.ToSharedRef(),TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text));return Text;
}
FString RootBridgeJson(const FRootBridgeValues& Array)
{
    FString Text;FJsonSerializer::Serialize(Array,TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text));return Text;
}
FRootBridgeValues RootBridgeNumbers(const FVector& P){return {MakeShared<FJsonValueNumber>(P.X),MakeShared<FJsonValueNumber>(P.Y),MakeShared<FJsonValueNumber>(P.Z)};}
FRootBridgeValues RootBridgeNumbers(const FQuat& Q){return {MakeShared<FJsonValueNumber>(Q.X),MakeShared<FJsonValueNumber>(Q.Y),MakeShared<FJsonValueNumber>(Q.Z),MakeShared<FJsonValueNumber>(Q.W)};}
bool RootBridgeReadNumbers(const TSharedPtr<FJsonObject>& O,const TCHAR* Key,double* Values,int32 Count)
{
    const FRootBridgeValues* A=nullptr;if(!O->TryGetArrayField(Key,A)||A->Num()!=Count)return false;
    for(int32 I=0;I<Count;++I){if((*A)[I]->Type!=EJson::Number||!FMath::IsFinite((*A)[I]->AsNumber()))return false;Values[I]=(*A)[I]->AsNumber();}return true;
}
bool RootBridgeAddJson(const TSharedPtr<FJsonObject>& To,const TCHAR* Key,const FString& Text,EJson Type,FString& Error)
{
    if(Text.IsEmpty())return true;
    const auto Wrapper=RootBridgeParse(TEXT("{\"value\":")+Text+TEXT("}"));const auto V=Wrapper?Wrapper->Values.FindRef(TEXT("value")):nullptr;
    if(!V||V->Type!=Type){Error=FString(TEXT("Invalid root "))+Key+TEXT(" JSON");return false;}To->SetField(Key,V);return true;
}
bool RootBridgeAddGeometry(const TSharedPtr<FJsonObject>& To,const FString& Text,FString& Error)
{
    if(Text.IsEmpty())return true;
    const auto O=RootBridgeParse(Text);const FRootBridgeValues* Surfaces=nullptr;
    if(!O||!O->TryGetArrayField(TEXT("surfaces"),Surfaces)){Error=TEXT("Root geometry requires the finite surfaces from CaptureSurfaceTerrain");return false;}
    To->SetArrayField(TEXT("surfaces"),*Surfaces);
    if(O->HasField(TEXT("rootSurfaces"))){const FRootBridgeValues* Roots=nullptr;if(!O->TryGetArrayField(TEXT("rootSurfaces"),Roots)){Error=TEXT("Invalid root navigation surfaces");return false;}To->SetArrayField(TEXT("rootSurfaces"),*Roots);}return true;
}
FVector RootBridgeSwap(const FVector& V){return FVector(V.X,V.Z,V.Y);}
bool RootBridgeGameThread(FString& Error){if(IsInGameThread())return true;Error=TEXT("Foot IK root bridge is game-thread only");return false;}
}

FProphecyFootIKRootBridge::FProphecyFootIKRootBridge()=default;
FProphecyFootIKRootBridge::~FProphecyFootIKRootBridge(){Disable();}
FVector FProphecyFootIKRootBridge::ToCoursePosition(const FVector& P,const FTransform& S){return ProphecyThrow::FromUnrealPoint(S.InverseTransformPosition(P));}
FVector FProphecyFootIKRootBridge::ToWorldPosition(const FVector& P,const FTransform& S){return S.TransformPosition(ProphecyThrow::ToUnrealPoint(P));}
FVector FProphecyFootIKRootBridge::ToCourseVelocity(const FVector& V,const FTransform& S){return ProphecyThrow::FromUnrealPoint(S.InverseTransformVectorNoScale(V));}
FVector FProphecyFootIKRootBridge::ToWorldVelocity(const FVector& V,const FTransform& S){return S.TransformVectorNoScale(ProphecyThrow::ToUnrealPoint(V));}
FQuat FProphecyFootIKRootBridge::ToCourseRotation(const FQuat& Q,const FTransform& S){const FQuat L=S.GetRotation().Inverse()*Q;return FQuat(-L.X,-L.Z,-L.Y,L.W);}
FQuat FProphecyFootIKRootBridge::ToWorldRotation(const FQuat& Q,const FTransform& S){return S.GetRotation()*FQuat(-Q.X,-Q.Z,-Q.Y,Q.W);}

bool FProphecyFootIKRootBridge::Initialize(const FInit& I,FOutput& Out,FString& Error)
{
    if(!RootBridgeGameThread(Error))return false;
    if(I.PositionWorld.ContainsNaN()||I.VelocityWorld.ContainsNaN()||I.NormalWorld.ContainsNaN()||I.NormalWorld.IsNearlyZero()||I.TravelVelocityWorld.ContainsNaN()||!FMath::IsFinite(I.HeightCm)||I.HeightCm<=0||!FMath::IsFinite(I.SpeedCmPerSecond)||!FMath::IsFinite(I.GravityCmPerSecondSquared)||I.GravityCmPerSecondSquared<0||!FMath::IsFinite(I.Time)||I.Time<0||(I.PreviousRootWorld.IsSet()&&I.PreviousRootWorld->ContainsNaN())||(I.BodyRotationWorld.IsSet()&&I.BodyRotationWorld->ContainsNaN()))
    {Error=TEXT("Invalid finite Foot IK root initialization");return false;}
    if((I.VirtualRootWorld.IsSet()&&I.VirtualRootWorld->ContainsNaN())||(I.PreviousVirtualRootWorld.IsSet()&&I.PreviousVirtualRootWorld->ContainsNaN())){Error=TEXT("Nonfinite virtual root initialization");return false;}
    auto CommandObject=MakeShared<FJsonObject>(),Root=MakeShared<FJsonObject>();
    CommandObject->SetNumberField(TEXT("height"),I.HeightCm*.01);CommandObject->SetNumberField(TEXT("speed"),I.SpeedCmPerSecond*.01);CommandObject->SetNumberField(TEXT("gravity"),I.GravityCmPerSecondSquared*.01);CommandObject->SetNumberField(TEXT("time"),I.Time);
    Root->SetArrayField(TEXT("position"),RootBridgeNumbers(ToCoursePosition(I.PositionWorld,I.CourseWorld)));Root->SetArrayField(TEXT("velocity"),RootBridgeNumbers(ToCourseVelocity(I.VelocityWorld,I.CourseWorld)));
    Root->SetArrayField(TEXT("normal"),RootBridgeNumbers(RootBridgeSwap(I.CourseWorld.InverseTransformVectorNoScale(I.NormalWorld))));
    if(I.BodyRotationWorld.IsSet())Root->SetArrayField(TEXT("bodyRotation"),RootBridgeNumbers(ToCourseRotation(*I.BodyRotationWorld,I.CourseWorld)));
    if(!I.Surface.IsEmpty())Root->SetStringField(TEXT("surface"),I.Surface);
    CommandObject->SetObjectField(TEXT("root"),Root);CommandObject->SetArrayField(TEXT("travelVelocity"),RootBridgeNumbers(ToCourseVelocity(I.TravelVelocityWorld,I.CourseWorld)));
    if(!I.RootYawDegrees.IsEmpty()){if(I.RootYawDegrees.Num()!=10){Error=TEXT("Root heading requires ten angles");return false;}FRootBridgeValues Yaw;for(double Angle:I.RootYawDegrees){if(!FMath::IsFinite(Angle)){Error=TEXT("Nonfinite root heading");return false;}Yaw.Add(MakeShared<FJsonValueNumber>(Angle));}CommandObject->SetArrayField(TEXT("rootYawDegrees"),Yaw);}
    if(I.PreviousRootWorld.IsSet())CommandObject->SetArrayField(TEXT("previousRoot"),RootBridgeNumbers(ToCoursePosition(*I.PreviousRootWorld,I.CourseWorld)));
    if(I.VirtualRootWorld.IsSet())CommandObject->SetArrayField(TEXT("virtualRoot"),RootBridgeNumbers(ToCoursePosition(*I.VirtualRootWorld,I.CourseWorld)));
    if(I.PreviousVirtualRootWorld.IsSet())CommandObject->SetArrayField(TEXT("previousVirtualRoot"),RootBridgeNumbers(ToCoursePosition(*I.PreviousVirtualRootWorld,I.CourseWorld)));
    if(!RootBridgeAddJson(CommandObject,TEXT("settings"),I.SettingsJson,EJson::Object,Error)||!RootBridgeAddGeometry(CommandObject,I.GeometryJson,Error)||!RootBridgeAddJson(CommandObject,TEXT("snapshot"),I.SnapshotJson,EJson::Object,Error))return false;
    return InitializeJson(RootBridgeJson(CommandObject),I.CourseWorld,Out,Error);
}
bool FProphecyFootIKRootBridge::InitializeJson(const FString& Input,const FTransform& CourseWorld,FOutput& Out,FString& Error)
{
    Error.Reset();if(!RootBridgeGameThread(Error))return false;
    if(CourseWorld.ContainsNaN()||!CourseWorld.GetScale3D().Equals(FVector::OneVector,1.e-8)){Error=TEXT("Root course transform must have finite unit scale");return false;}
    const auto Init=RootBridgeParse(Input);if(!Init){Error=TEXT("Invalid root initialization JSON");return false;}Init->SetStringField(TEXT("op"),TEXT("rootInit"));
    Disable();Space=CourseWorld;VM=MakeUnique<FProphecyFootIKVM>();
    if(!VM->Initialize([](const FString&,FString&,FString& E){E=TEXT("The canonical root bridge must never invoke an NN");return false;},Error)||!Command(RootBridgeJson(Init),Out,Error)){Disable();return false;}return true;
}
bool FProphecyFootIKRootBridge::UpdateCommand(const TCHAR* Op,const FUpdate& I,int32 Ticks,FOutput& Out,FString& Error)
{
    Error.Reset();if(!RootBridgeGameThread(Error))return false;
    auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("op"),Op);O->SetNumberField(TEXT("ticks"),Ticks);
    if(!RootBridgeAddJson(O,TEXT("supports"),I.SupportsJson,EJson::Array,Error)||!RootBridgeAddJson(O,TEXT("supportsByTick"),I.SupportsByTickJson,EJson::Array,Error)||!RootBridgeAddJson(O,TEXT("settings"),I.SettingsJson,EJson::Object,Error)||!RootBridgeAddGeometry(O,I.GeometryJson,Error))return false;
    if(I.SurfaceRevision.IsSet())O->SetNumberField(TEXT("surfaceRevision"),*I.SurfaceRevision);
    if(I.TravelVelocityWorld.IsSet()){if(I.TravelVelocityWorld->ContainsNaN()){Error=TEXT("Nonfinite root drive velocity");return false;}O->SetArrayField(TEXT("travelVelocity"),RootBridgeNumbers(ToCourseVelocity(*I.TravelVelocityWorld,Space)));}
    // Send [] as well: otherwise the adapter retains a prior future command
    // window and ignores a new immediate controller velocity.
    FRootBridgeValues Rows;for(const auto& D:I.FutureDrive){if(!FMath::IsFinite(D.Time)||D.VelocityWorld.ContainsNaN()){Error=TEXT("Nonfinite future root drive");return false;}auto Row=MakeShared<FJsonObject>();Row->SetNumberField(TEXT("time"),D.Time);Row->SetArrayField(TEXT("velocity"),RootBridgeNumbers(ToCourseVelocity(D.VelocityWorld,Space)));Rows.Add(MakeShared<FJsonValueObject>(Row));}O->SetArrayField(TEXT("futureDrive"),Rows);
    if(!I.RootYawDegrees.IsEmpty()){if(I.RootYawDegrees.Num()!=10){Error=TEXT("Root heading requires previous/current plus eight future angles");return false;}FRootBridgeValues Yaw;for(double Angle:I.RootYawDegrees){if(!FMath::IsFinite(Angle)){Error=TEXT("Nonfinite root heading");return false;}Yaw.Add(MakeShared<FJsonValueNumber>(Angle));}O->SetArrayField(TEXT("rootYawDegrees"),Yaw);}
    return Command(RootBridgeJson(O),Out,Error);
}
bool FProphecyFootIKRootBridge::Forecast(const FUpdate& I,int32 Ticks,FOutput& Out,FString& Error){return UpdateCommand(TEXT("rootForecast"),I,Ticks,Out,Error);}
bool FProphecyFootIKRootBridge::Step(const FUpdate& I,int32 Ticks,FOutput& Out,FString& Error){return UpdateCommand(TEXT("rootStep"),I,Ticks,Out,Error);}
bool FProphecyFootIKRootBridge::Status(FOutput& Out,FString& Error){return Command(TEXT("{\"op\":\"rootStatus\"}"),Out,Error);}
bool FProphecyFootIKRootBridge::Command(const FString& Input,FOutput& Out,FString& Error)
{
    Error.Reset();if(!RootBridgeGameThread(Error))return false;if(!VM){Error=TEXT("Foot IK root bridge is disabled");return false;}
    FString Result;if(!VM->Command(Input,Result,Error))return false;return Decode(Result,Out,Error);
}
void FProphecyFootIKRootBridge::Disable(){if(VM){VM->Cancel();VM.Reset();}}
double FProphecyFootIKRootBridge::LastSeconds() const{return VM?VM->LastSeconds():0;}
FString FProphecyFootIKRootBridge::EncodeSupports(TConstArrayView<FSupport> Supports) const
{
    FRootBridgeValues Values;for(const auto& S:Supports){auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("surface"),S.Surface);O->SetArrayField(TEXT("point"),RootBridgeNumbers(ToCoursePosition(S.PointWorld,Space)));if(S.NormalWorld.IsSet())O->SetArrayField(TEXT("normal"),RootBridgeNumbers(RootBridgeSwap(Space.InverseTransformVectorNoScale(*S.NormalWorld))));Values.Add(MakeShared<FJsonValueObject>(O));}return RootBridgeJson(Values);
}
bool FProphecyFootIKRootBridge::Decode(const FString& Text,FOutput& Out,FString& Error) const
{
    const auto O=RootBridgeParse(Text);if(!O){Error=TEXT("Invalid canonical root response");return false;}
    FOutput Result;Result.Json=Text;double Tick=0;O->TryGetNumberField(TEXT("tick"),Tick);Result.Tick=int32(Tick);O->TryGetNumberField(TEXT("time"),Result.Time);
    auto Context=[&](const TSharedPtr<FJsonObject>& R,FContext& C){
        if(!R)return false;double P[3],V[3],N[3],B[4],G[4],M[3],U[3];
        if(!RootBridgeReadNumbers(R,TEXT("position"),P,3)||!RootBridgeReadNumbers(R,TEXT("velocity"),V,3)||!RootBridgeReadNumbers(R,TEXT("normal"),N,3)||!RootBridgeReadNumbers(R,TEXT("bodyRotation"),B,4)||!RootBridgeReadNumbers(R,TEXT("gaitRotation"),G,4)||!RootBridgeReadNumbers(R,TEXT("mass"),M,3)||!RootBridgeReadNumbers(R,TEXT("bodyUp"),U,3))return false;
        C.PositionWorld=ToWorldPosition(FVector(P[0],P[1],P[2]),Space);C.VelocityWorld=ToWorldVelocity(FVector(V[0],V[1],V[2]),Space);C.MassWorld=ToWorldPosition(FVector(M[0],M[1],M[2]),Space);
        double Virtual[3];C.VirtualPositionWorld=RootBridgeReadNumbers(R,TEXT("virtualRoot"),Virtual,3)?ToWorldPosition(FVector(Virtual[0],Virtual[1],Virtual[2]),Space):C.PositionWorld;R->TryGetNumberField(TEXT("yaw"),C.YawDegrees);
        C.NormalWorld=Space.TransformVectorNoScale(RootBridgeSwap(FVector(N[0],N[1],N[2])));C.BodyUpWorld=Space.TransformVectorNoScale(RootBridgeSwap(FVector(U[0],U[1],U[2])));
        C.BodyRotationWorld=ToWorldRotation(FQuat(B[0],B[1],B[2],B[3]),Space);C.GaitRotationWorld=ToWorldRotation(FQuat(G[0],G[1],G[2],G[3]),Space);
        R->TryGetNumberField(TEXT("time"),C.Time);R->TryGetStringField(TEXT("surface"),C.Surface);R->TryGetStringField(TEXT("courseSurface"),C.CourseSurface);R->TryGetBoolField(TEXT("hasFloor"),C.HasFloor);R->TryGetBoolField(TEXT("useEdited"),C.UseEdited);
        C.Sliding=R->HasTypedField<EJson::Object>(TEXT("slide"));C.Json=RootBridgeJson(R);return true;
    };
    const TSharedPtr<FJsonObject>* Root=nullptr;
    if(O->TryGetObjectField(TEXT("root"),Root)&&!Context(*Root,Result.Root)){Error=TEXT("Incomplete canonical root context");return false;}
    const FRootBridgeValues* Frames=nullptr;if(O->TryGetArrayField(TEXT("frames"),Frames)){for(const auto& F:*Frames){if(F->Type!=EJson::Object||!Context(F->AsObject(),Result.Frames.AddDefaulted_GetRef())){Error=TEXT("Invalid canonical forecast context");return false;}}Result.FramesJson=RootBridgeJson(*Frames);if(!Root&&!Result.Frames.IsEmpty())Result.Root=Result.Frames[0];}
    const FRootBridgeValues* Roots=nullptr;if(O->TryGetArrayField(TEXT("roots"),Roots)){for(const auto& R:*Roots){if(R->Type!=EJson::Array||R->AsArray().Num()!=3){Error=TEXT("Invalid canonical root window");return false;}const auto& A=R->AsArray();for(const auto& N:A)if(N->Type!=EJson::Number||!FMath::IsFinite(N->AsNumber())){Error=TEXT("Nonfinite root window");return false;}Result.RootsWorld.Add(ToWorldPosition(FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber()),Space));}}
    const FRootBridgeValues* VirtualRoots=nullptr;if(O->TryGetArrayField(TEXT("virtualRoots"),VirtualRoots)){for(const auto& R:*VirtualRoots){if(R->Type!=EJson::Array||R->AsArray().Num()!=3){Error=TEXT("Invalid virtual root window");return false;}const auto& A=R->AsArray();for(const auto& N:A)if(N->Type!=EJson::Number||!FMath::IsFinite(N->AsNumber())){Error=TEXT("Nonfinite virtual root window");return false;}Result.VirtualRootsWorld.Add(ToWorldPosition(FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber()),Space));}}
    const FRootBridgeValues* Yaw=nullptr;if(O->TryGetArrayField(TEXT("rootYawDegrees"),Yaw)){for(const auto& A:*Yaw){if(A->Type!=EJson::Number||!FMath::IsFinite(A->AsNumber())){Error=TEXT("Nonfinite root heading window");return false;}Result.RootYawDegrees.Add(A->AsNumber());}}
    const TSharedPtr<FJsonObject>* Snapshot=nullptr;if(O->TryGetObjectField(TEXT("snapshot"),Snapshot))Result.SnapshotJson=RootBridgeJson(*Snapshot);
    const FRootBridgeValues* Receipts=nullptr;if(O->TryGetArrayField(TEXT("receipts"),Receipts))Result.ReceiptsJson=RootBridgeJson(*Receipts);
    Out=MoveTemp(Result);return true;
}
