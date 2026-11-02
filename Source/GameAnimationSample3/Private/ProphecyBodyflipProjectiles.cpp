#include "ProphecyBodyflipProjectiles.h"
#include "ProphecyJoltBody.h"
#include "ProphecyJoltPhysicsCommand.h"
#include "ProceduralMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Materials/Material.h"
#include "MaterialDomain.h"
#include "MaterialDomain.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

namespace BodyflipProjectile
{
static FVector V(const TArray<TSharedPtr<FJsonValue>>& A){return A.Num()==3?FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber()):FVector::ZeroVector;}
static FQuat Q(const TArray<TSharedPtr<FJsonValue>>& A){return A.Num()==4?FQuat(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber(),A[3]->AsNumber()).GetNormalized():FQuat::Identity;}
static FVector Point(FVector P){return FVector(P.X,P.Z,P.Y)*100.;}
static FVector Direction(FVector P){return FVector(P.X,P.Z,P.Y);}
static FQuat Rotation(FQuat Q){return FQuat(-Q.X,-Q.Z,-Q.Y,Q.W);}
static bool SameValue(const TSharedPtr<FJsonValue>& A,const TSharedPtr<FJsonValue>& B);
static bool SameLaunch(const TSharedPtr<FJsonObject>& A,const TSharedPtr<FJsonObject>& B)
{
    for(const auto& Pair:A->Values){if(Pair.Key==TEXT("releaseRemainderSeconds"))continue;const auto* Other=B->Values.Find(Pair.Key);if(!Other||!SameValue(Pair.Value,*Other))return false;}
    for(const auto& Pair:B->Values)if(Pair.Key!=TEXT("releaseRemainderSeconds")&&!A->Values.Contains(Pair.Key))return false;return true;
}
static bool SameValue(const TSharedPtr<FJsonValue>& A,const TSharedPtr<FJsonValue>& B)
{
    if(!A||!B||A->Type!=B->Type)return false;
    switch(A->Type){case EJson::Number:return FMath::Abs(A->AsNumber()-B->AsNumber())<=1.e-8;case EJson::String:return A->AsString()==B->AsString();case EJson::Boolean:return A->AsBool()==B->AsBool();case EJson::Null:return true;
    case EJson::Object:return SameLaunch(A->AsObject(),B->AsObject());case EJson::Array:{const auto& X=A->AsArray();const auto& Y=B->AsArray();if(X.Num()!=Y.Num())return false;for(int32 I=0;I<X.Num();I++)if(!SameValue(X[I],Y[I]))return false;return true;}default:return false;}
}
static TArray<FProphecyBodyflipProjectiles::FImpl*> Instances;
struct FEntry
{
    FString Id,Kind;
    TWeakObjectPtr<AActor> Actor;
    FProphecyJoltBodyHandle Body;
    TSharedPtr<FJsonObject> Launch;
    FVector Scale=FVector::OneVector,Principal=FVector::OneVector,Axis=FVector::UpVector;
    FQuat MassRotation=FQuat::Identity;
    double Release=0,Mass=1,Length=0,SideArea=0,AxialArea=0,Pressure=0,Strength=0,Damping=0;
    FProphecyJoltBodyState PausedState;
};
struct FRecordedBody{FString Id;TSharedPtr<FJsonObject> Launch;FProphecyJoltBodyState State;};
struct FRecordedFrame{double Time=0;bool ZeroGravity=false;TArray<FRecordedBody> Bodies;};
#if WITH_DEV_AUTOMATION_TESTS
static TMap<UWorld*,TFunction<void(const ProphecyBodyflip::FProjectileDiagnostic&,const TCHAR*)>> Observers;
static void Observe(FProphecyBodyflipProjectiles::FImpl& Instance,const FEntry& Entry,double Time,const TCHAR* Phase);
#endif
}

struct FProphecyBodyflipProjectiles::FImpl
{
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<UProphecyJoltWorldSubsystem> Physics;
    FTransform Space=FTransform::Identity;
    TSharedPtr<FJsonObject> Assets,Physical;
    TMap<FString,TUniquePtr<BodyflipProjectile::FEntry>> Entries;
    TArray<BodyflipProjectile::FRecordedFrame> History;
    int32 FirstHistory=0,RecordedBodies=0;
    double Previous=0,Time=0;
    bool Paused=false,ZeroGravity=false;
    FTransform Transform(const TSharedPtr<FJsonObject>& O) const
    {using namespace BodyflipProjectile;return FTransform(Rotation(Q(O->GetArrayField(TEXT("q")))),Point(V(O->GetArrayField(TEXT("p")))))*Space;}
    void Clear()
    {for(auto& Pair:Entries){auto& E=*Pair.Value;if(Physics.IsValid()&&Physics->OwnsBody(E.Body))Physics->DestroyBody(E.Body);if(E.Actor.IsValid())E.Actor->Destroy();}Entries.Reset();}
    void ClearHistory(){History.Reset();FirstHistory=RecordedBodies=0;}
    const BodyflipProjectile::FRecordedFrame* Recorded(double At) const
    {
        int32 Lo=FirstHistory,Hi=History.Num();while(Lo<Hi){const int32 Mid=Lo+(Hi-Lo)/2;if(History[Mid].Time<At-1.e-7)Lo=Mid+1;else Hi=Mid;}
        return History.IsValidIndex(Lo)&&FMath::Abs(History[Lo].Time-At)<1.e-7?&History[Lo]:nullptr;
    }
    void Record()
    {
        using namespace BodyflipProjectile;if(Paused||!Physics.IsValid())return;
        while(History.Num()>FirstHistory&&History.Last().Time>=Time-1.e-7){RecordedBodies-=History.Last().Bodies.Num();History.Pop(EAllowShrinking::No);}
        FRecordedFrame Frame;Frame.Time=Time;Frame.ZeroGravity=ZeroGravity;
        for(auto& Pair:Entries){auto& E=*Pair.Value;if(!E.Body.IsSet()||!E.Launch)continue;FProphecyJoltBodyState State;if(Physics->ReadBody(E.Body,State).IsSuccess())Frame.Bodies.Add({E.Id,E.Launch,State});}
        if(Frame.Bodies.IsEmpty())return;RecordedBodies+=Frame.Bodies.Num();History.Add(MoveTemp(Frame));
        // Bound retained history by body states, not by scene duration. Eviction
        // is explicit at seek; never substitute a newly spawned release pose.
        while(RecordedBodies>32768&&FirstHistory<History.Num()){RecordedBodies-=History[FirstHistory].Bodies.Num();History[FirstHistory].Bodies.Reset();FirstHistory++;}
        if(FirstHistory>1024&&FirstHistory>History.Num()/2){History.RemoveAt(0,FirstHistory,EAllowShrinking::No);FirstHistory=0;}
    }
    bool Visual(const TSharedPtr<FJsonObject>& O,BodyflipProjectile::FEntry*& Out,FString& Error)
    {
        using namespace BodyflipProjectile;const FString Id=O->GetStringField(TEXT("id"));if(auto* Found=Entries.Find(Id)){Out=Found->Get();return true;}
        const FString Kind=O->GetStringField(TEXT("kind"));const auto* Source=Assets->Values.Find(Kind);if(!Source){Error=TEXT("Unknown Bodyflip projectile");return false;}const auto Asset=(*Source)->AsObject();
        auto E=MakeUnique<FEntry>();E->Id=Id;E->Kind=Kind;E->Scale=V(O->GetArrayField(TEXT("scale")));if(E->Scale.GetMin()<=0||E->Scale.ContainsNaN()){Error=TEXT("Invalid throw mesh scale");return false;}
        FActorSpawnParameters Spawn;Spawn.ObjectFlags|=RF_Transient;Spawn.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        auto* A=World->SpawnActor<AActor>(Spawn);if(!A){Error=TEXT("Unable to spawn held throw visual");return false;}A->Tags.Add(TEXT("BodyflipProjectile"));A->Tags.Add(FName(*Id));
        auto* Mesh=NewObject<UProceduralMeshComponent>(A);A->SetRootComponent(Mesh);A->AddInstanceComponent(Mesh);Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);Mesh->RegisterComponent();
        TArray<FVector> Vertices,Normals;TArray<int32> Triangles;TArray<FLinearColor> Colors;TArray<FVector2D> UV;TArray<FProcMeshTangent> Tangents;
        for(const auto& P:Asset->GetArrayField(TEXT("vertices")))Vertices.Add(Point(V(P->AsArray())*E->Scale));Normals.Init(FVector::ZeroVector,Vertices.Num());
        const auto& Indices=Asset->GetArrayField(TEXT("triangles"));for(int I=0;I+2<Indices.Num();I+=3){const int X=int(Indices[I]->AsNumber()),Y=int(Indices[I+2]->AsNumber()),Z=int(Indices[I+1]->AsNumber());Triangles.Append({X,Y,Z});const auto N=FVector::CrossProduct(Vertices[Y]-Vertices[X],Vertices[Z]-Vertices[X]).GetSafeNormal();Normals[X]+=N;Normals[Y]+=N;Normals[Z]+=N;}
        for(auto& N:Normals)N.Normalize();for(const auto& Color:Asset->GetArrayField(TEXT("colors"))){const auto P=V(Color->AsArray());Colors.Emplace(P.X,P.Y,P.Z,1);}
        Mesh->CreateMeshSection_LinearColor(0,Vertices,Triangles,Normals,UV,Colors,Tangents,false);
        auto* Material=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/BodyflipLab/M_ProjectileVertexColor.M_ProjectileVertexColor"));
        Mesh->SetMaterial(0,Material?Material:UMaterial::GetDefaultMaterial(MD_Surface));A->SetActorTransform(Transform(O));E->Actor=A;
        Out=E.Get();Entries.Add(Id,MoveTemp(E));return true;
    }
    FProphecyJoltWorldStatus Release(BodyflipProjectile::FEntry& E)
    {
        using namespace BodyflipProjectile;if(E.Body.IsSet())return {};auto* P=Physics.Get();if(!P)return {EProphecyJoltWorldResult::NotInitialized,TEXT("No shared Jolt world")};
        const auto Asset=Assets->GetObjectField(E.Kind),Mass=Physical->GetObjectField(E.Kind);if(!V(Mass->GetArrayField(TEXT("scale"))).Equals(E.Scale,1.e-8))return {EProphecyJoltWorldResult::InvalidArgument,TEXT("Throw physical scale does not match mesh")};
        FProphecyJoltBodySnapshot Snapshot;Snapshot.CaptureId=FGuid::NewGuid();auto& B=Snapshot.Body;B.bSimulating=B.bAwake=B.bCCD=true;B.bGravityEnabled=!ZeroGravity;B.MassKg=Mass->GetNumberField(TEXT("mass"));B.PrincipalInertiaKgCmSquared=Direction(V(Mass->GetArrayField(TEXT("principal"))))*10000.;B.MassFrameToBodyOrigin=FTransform(Rotation(Q(Mass->GetArrayField(TEXT("rotation")))),Point(V(Mass->GetArrayField(TEXT("com")))));
        B.BodyOriginToWorld=Transform(E.Launch);B.CenterOfMassVelocityCmPerSecond=Space.TransformVectorNoScale(Point(V(E.Launch->GetArrayField(TEXT("v")))));B.AngularVelocityRadiansPerSecond=Space.TransformVectorNoScale(-Direction(V(E.Launch->GetArrayField(TEXT("omega")))));B.CollisionEnabled=ECollisionEnabled::QueryAndPhysics;B.ObjectType=ECC_PhysicsBody;B.CollisionResponses.SetAllChannels(ECR_Block);B.MaxLinearVelocityCmPerSecond=100000;B.MaxAngularVelocityRadiansPerSecond=1000;B.LinearDamping=0;B.AngularDamping=.03;B.Friction=B.StaticFriction=.55;B.Restitution=.25;
        const TArray<TSharedPtr<FJsonValue>>* Hulls=nullptr;TArray<TSharedPtr<FJsonValue>> Fallback;if(!Asset->TryGetArrayField(TEXT("hulls"),Hulls)){Fallback.Add(MakeShared<FJsonValueArray>(Asset->GetArrayField(TEXT("collision"))));Hulls=&Fallback;}
        for(const auto& H:*Hulls){auto& Shape=B.Shapes.AddDefaulted_GetRef();Shape.Kind=EProphecyJoltRigShape::Convex;Shape.SourceElementIndex=B.Shapes.Num()-1;Shape.AuthoredCollisionEnabled=Shape.CurrentCollisionEnabled=ECollisionEnabled::QueryAndPhysics;for(const auto& Vtx:H->AsArray())Shape.ConvexVerticesCm.Add(Point(V(Vtx->AsArray())*E.Scale));}
        Snapshot.SourceWorld=World;Snapshot.SourceComponent=E.Actor.IsValid()?Cast<UPrimitiveComponent>(E.Actor->GetRootComponent()):nullptr;Snapshot.ComponentToWorld=B.BodyOriginToWorld;Snapshot.ComponentPath=GetPathNameSafe(Snapshot.SourceComponent.Get());
        FProphecyJoltPreparedBody Prepared;FString Error;if(!Prepared.BuildAuthoredConvex(Snapshot,Direction(E.Scale),.1,Error))return {EProphecyJoltWorldResult::ShapeCreationFailed,Error};TArray<FString> Notes;auto Status=P->CreateBody(Snapshot,Prepared,E.Body,Notes);if(!Status.IsSuccess())return Status;Status=P->SetBodyGyroscopic(E.Body,true);if(!Status.IsSuccess())return Status;
        E.Mass=B.MassKg;E.Principal=Direction(V(Mass->GetArrayField(TEXT("principal"))));E.MassRotation=B.MassFrameToBodyOrigin.GetRotation();const TArray<TSharedPtr<FJsonValue>>* AxisArray=nullptr;E.Axis=Asset->TryGetArrayField(TEXT("longAxis"),AxisArray)?Direction(V(*AxisArray)).GetSafeNormal():FVector::UpVector;
        const auto Aero=E.Launch->GetObjectField(TEXT("aero"));if(E.Kind==TEXT("spear")&&Aero->GetBoolField(TEXT("enabled"))){E.Pressure=Aero->GetNumberField(TEXT("pressure"));E.Strength=Aero->GetNumberField(TEXT("strength"));E.Damping=Aero->GetNumberField(TEXT("damping"));const auto Axis=V(Asset->GetArrayField(TEXT("longAxis")));const double Long=(Axis*E.Scale).Size(),Area=E.Scale.X*E.Scale.Y*E.Scale.Z/Long;double Lo=DBL_MAX,Hi=-DBL_MAX;for(const auto& H:*Hulls)for(const auto& Pnt:H->AsArray()){const double X=FVector::DotProduct(V(Pnt->AsArray())*E.Scale,Axis);Lo=FMath::Min(Lo,X);Hi=FMath::Max(Hi,X);}E.Length=Hi-Lo;E.SideArea=.96*Long*FMath::Sqrt(Area);E.AxialArea=.001*Area;}
        #if WITH_DEV_AUTOMATION_TESTS
        Observe(*this,E,E.Release,TEXT("release"));
        #endif
        return {};
    }
    FProphecyJoltWorldStatus Before(double Fraction,double Dt)
    {
        using namespace BodyflipProjectile;auto* P=Physics.Get();if(!P||Paused)return {};const double At=FMath::Lerp(Previous,Time,Fraction);
        for(auto& Pair:Entries){auto& E=*Pair.Value;if(!E.Launch||E.Release>At+1.e-8)continue;auto Status=Release(E);if(!Status.IsSuccess())return Status;if(Dt<=0||E.Strength<=0)continue;
            FProphecyJoltBodyState State;Status=P->ReadBody(E.Body,State);if(!Status.IsSuccess())return Status;if(!State.bActive)continue;
            const FVector V=State.CenterOfMassVelocityCmPerSecond*.01,W=State.AngularVelocityRadiansPerSecond,Axis=State.Rotation.RotateVector(E.Axis).GetSafeNormal(),R=Axis*(-E.Pressure*E.Length),PV=V+FVector::CrossProduct(W,R),Along=Axis*FVector::DotProduct(PV,Axis),Side=PV-Along;const double Density=.5*1.225*E.Strength;const FQuat Principal=State.Rotation*E.MassRotation;
            auto Inverse=[&](FVector X){return Principal.RotateVector(Principal.UnrotateVector(X)/E.Principal);};
            auto Drag=[&](FVector X,double Area,double Flow){const double Speed=X.Size();if(Speed<1.e-10)return FVector::ZeroVector;const auto Normal=X/Speed,Moment=FVector::CrossProduct(R,Normal);const double Inv=1/E.Mass+FVector::DotProduct(Moment,Inverse(Moment)),K=Density*Area*Flow;return X*(-K/(1+Dt*K*Inv));};
            const FVector Force=Drag(Side,E.SideArea,PV.Size())+Drag(Along,E.AxialArea,Along.Size()),Swing=W-Axis*FVector::DotProduct(W,Axis);FVector Torque=FVector::CrossProduct(R,Force);const double Rate=Swing.Size();if(Rate>1.e-10&&E.Damping>0){const auto Normal=Swing/Rate;const double K=Density*E.SideArea*E.Length*E.Length/12*FMath::Max(V.Size(),Rate*E.Length)*E.Damping;Torque-=Swing*(K/(1+Dt*K*FVector::DotProduct(Normal,Inverse(Normal))));}
            FProphecyJoltPhysicsCommand Command;Command.Operation=EProphecyJoltPhysicsCommand::Force;Command.Value=Force*100;Status=P->ExecutePhysicsCommand(E.Body,Command);if(!Status.IsSuccess())return Status;Command.Operation=EProphecyJoltPhysicsCommand::Torque;Command.Value=Torque*10000;Status=P->ExecutePhysicsCommand(E.Body,Command);if(!Status.IsSuccess())return Status;
        }return {};
    }
    void After(double Fraction)
    {
        if(Paused||!Physics.IsValid())return;
        for(auto& Pair:Entries){auto& E=*Pair.Value;if(!E.Body.IsSet()||!E.Actor.IsValid())continue;FProphecyJoltBodyState S;
            if(Physics->ReadBody(E.Body,S).IsSuccess())E.Actor->SetActorTransform(FTransform(S.Rotation,S.PositionCm));
            #if WITH_DEV_AUTOMATION_TESTS
            BodyflipProjectile::Observe(*this,E,FMath::Lerp(Previous,Time,Fraction),TEXT("after-integration"));
            #endif
        }
        if(Fraction>=1.-1.e-9)Record();
    }
};

#if WITH_DEV_AUTOMATION_TESTS
namespace BodyflipProjectile
{
static ProphecyBodyflip::FProjectileDiagnostic Diagnostic(FProphecyBodyflipProjectiles::FImpl& I,const FEntry& E,double Time)
{
    ProphecyBodyflip::FProjectileDiagnostic D;D.Id=E.Id;D.Kind=E.Kind;D.Time=Time;D.ReleaseTime=E.Launch?E.Release:-1;D.Space=I.Space;D.Launch=E.Launch;
    if(E.Actor.IsValid())D.Visual=E.Actor->GetActorTransform();
    D.HasBody=I.Physics.IsValid()&&E.Body.IsSet()&&I.Physics->ReadBody(E.Body,D.Body).IsSuccess();return D;
}
static void Observe(FProphecyBodyflipProjectiles::FImpl& I,const FEntry& E,double Time,const TCHAR* Phase)
{
    if(auto* Observer=Observers.Find(I.World.Get()))(*Observer)(Diagnostic(I,E,Time),Phase);
}
}
void ProphecyBodyflip::ReadProjectileDiagnostics(UWorld* World,TArray<FProjectileDiagnostic>& Out)
{
    Out.Reset();for(auto* I:BodyflipProjectile::Instances)if(I->World==World)
        for(const auto& Pair:I->Entries)Out.Add(BodyflipProjectile::Diagnostic(*I,*Pair.Value,I->Time));
}
void ProphecyBodyflip::SetProjectileDiagnosticObserver(UWorld* World,TFunction<void(const FProjectileDiagnostic&,const TCHAR*)> Observer)
{
    if(Observer)BodyflipProjectile::Observers.Add(World,MoveTemp(Observer));else BodyflipProjectile::Observers.Remove(World);
}
#endif

FProphecyBodyflipProjectiles::FProphecyBodyflipProjectiles():Impl(MakeUnique<FImpl>()){}
FProphecyBodyflipProjectiles::~FProphecyBodyflipProjectiles(){BodyflipProjectile::Instances.Remove(Impl.Get());Impl->Clear();}
bool FProphecyBodyflipProjectiles::Initialize(UWorld* W,const FTransform& Space,FString& Error)
{
    static TWeakPtr<FJsonObject> CachedAssets,CachedPhysical;Impl->Assets=CachedAssets.Pin();Impl->Physical=CachedPhysical.Pin();
    if(!W){Error=TEXT("Bodyflip projectile world is missing");return false;}
    if(!Impl->Assets||!Impl->Physical){FString Json;TSharedPtr<FJsonObject> Root;if(!FFileHelper::LoadFileToString(Json,*(FPaths::ProjectContentDir()/TEXT("BodyflipLab/Projectiles.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),Root)){Error=TEXT("Missing Bodyflip projectile package");return false;}Impl->Assets=Root->GetObjectField(TEXT("assets"));Impl->Physical=Root->GetObjectField(TEXT("physical"));CachedAssets=Impl->Assets;CachedPhysical=Impl->Physical;}
    Impl->World=W;Impl->Physics=W->GetSubsystem<UProphecyJoltWorldSubsystem>();Impl->Space=Space;BodyflipProjectile::Instances.AddUnique(Impl.Get());return true;
}
bool FProphecyBodyflipProjectiles::Update(const TSharedPtr<FJsonObject>& Result,double At,FString& Error)
{
    Error.Reset();
    if(At<Impl->Time-1.e-8)return Seek(Result,At,Error);
    const TArray<TSharedPtr<FJsonValue>>* Releases=nullptr;Result->TryGetArrayField(TEXT("releases"),Releases);
    // Preflight before touching clock, bodies or visuals. A changed past throw
    // cannot be physically recomputed by inserting its release pose at 'now'.
    if(Releases)for(const auto& P:*Releases){const auto Packet=P->AsObject();const auto* Found=Impl->Entries.Find(Packet->GetStringField(TEXT("id")));const auto* E=Found?Found->Get():nullptr;
        if(E&&E->Launch&&!BodyflipProjectile::SameLaunch(E->Launch,Packet)){Error=TEXT("Cannot change a released throw in place. Restart Bodyflip to simulate the changed launch.");return false;}
        if((!E||!E->Launch)&&Packet->GetNumberField(TEXT("releaseTime"))<Impl->Time-1.e-8){Error=TEXT("Projectile release is in an uncomputed past interval. Seek a recorded frame or restart and play forward.");return false;}}
    Impl->Previous=Impl->Time;Impl->Time=At;Result->TryGetBoolField(TEXT("zeroGravity"),Impl->ZeroGravity);
    const TArray<TSharedPtr<FJsonValue>>* Held=nullptr;if(Result->TryGetArrayField(TEXT("held"),Held))for(const auto& H:*Held){BodyflipProjectile::FEntry* E=nullptr;if(!Impl->Visual(H->AsObject(),E,Error))return false;if(!E->Body.IsSet()&&E->Actor.IsValid())E->Actor->SetActorTransform(Impl->Transform(H->AsObject()));}
    if(Releases)for(const auto& P:*Releases){BodyflipProjectile::FEntry* E=nullptr;if(!Impl->Visual(P->AsObject(),E,Error))return false;if(!E->Launch){E->Launch=P->AsObject();E->Release=E->Launch->GetNumberField(TEXT("releaseTime"));}}
    return true;
}
bool FProphecyBodyflipProjectiles::CanSeek(const TSharedPtr<FJsonObject>& Result,double At,FString& Error) const
{
    Error.Reset();
    if(!Result||!FMath::IsFinite(At)||At<0){Error=TEXT("Invalid projectile seek time or frame.");return false;}
    const TArray<TSharedPtr<FJsonValue>>* Releases=nullptr;if(!Result->TryGetArrayField(TEXT("releases"),Releases)||Releases->IsEmpty())return true;
    const auto* Frame=Impl->Recorded(At);if(!Frame){Error=FString::Printf(TEXT("Cannot seek to %.3f s: projectile physics has not been recorded there, or that history was evicted. Play forward from a recorded state."),At);return false;}
    bool ZeroGravity=false;Result->TryGetBoolField(TEXT("zeroGravity"),ZeroGravity);
    if(ZeroGravity!=Frame->ZeroGravity||Releases->Num()!=Frame->Bodies.Num()){Error=TEXT("Cannot seek: recorded projectile physics belongs to different scene settings. Restart and play the changed scene.");return false;}
    for(const auto& Value:*Releases){const auto Packet=Value->AsObject();const auto* Body=Frame->Bodies.FindByPredicate([&](const auto& B){return B.Id==Packet->GetStringField(TEXT("id"));});if(!Body||!BodyflipProjectile::SameLaunch(Body->Launch,Packet)){Error=TEXT("Cannot seek: the throw differs from its recorded launch. Restart and play the changed scene.");return false;}}
    return true;
}
bool FProphecyBodyflipProjectiles::Seek(const TSharedPtr<FJsonObject>& Result,double At,FString& Error)
{
    if(!CanSeek(Result,At,Error))return false;
    Result->TryGetBoolField(TEXT("zeroGravity"),Impl->ZeroGravity);
    const TArray<TSharedPtr<FJsonValue>>* Releases=nullptr;Result->TryGetArrayField(TEXT("releases"),Releases);const TArray<TSharedPtr<FJsonValue>>* Held=nullptr;Result->TryGetArrayField(TEXT("held"),Held);
    TSet<FString> Keep;if(Releases)for(const auto& V:*Releases)Keep.Add(V->AsObject()->GetStringField(TEXT("id")));if(Held)for(const auto& V:*Held)Keep.Add(V->AsObject()->GetStringField(TEXT("id")));
    for(auto It=Impl->Entries.CreateIterator();It;++It)if(!Keep.Contains(It.Key())){auto& E=*It.Value();if(Impl->Physics.IsValid()&&Impl->Physics->OwnsBody(E.Body))Impl->Physics->DestroyBody(E.Body);if(E.Actor.IsValid())E.Actor->Destroy();It.RemoveCurrent();}
    if(Held)for(const auto& Value:*Held){const auto Packet=Value->AsObject();BodyflipProjectile::FEntry* E=nullptr;if(!Impl->Visual(Packet,E,Error))return false;if(Impl->Physics.IsValid()&&Impl->Physics->OwnsBody(E->Body))Impl->Physics->DestroyBody(E->Body);E->Body={};E->Launch.Reset();E->Actor->SetActorTransform(Impl->Transform(Packet));}
    if(Releases&&!Releases->IsEmpty()){const auto* Frame=Impl->Recorded(At);for(const auto& Saved:Frame->Bodies){BodyflipProjectile::FEntry* E=nullptr;if(!Impl->Visual(Saved.Launch,E,Error))return false;E->Launch=Saved.Launch;E->Release=Saved.Launch->GetNumberField(TEXT("releaseTime"));auto Status=Impl->Release(*E);if(Status.IsSuccess())Status=Impl->Physics->RestoreBodyState(E->Body,Saved.State,Impl->Paused);if(!Status.IsSuccess()){Error=Status.Message;return false;}E->PausedState=Saved.State;E->Actor->SetActorTransform(FTransform(Saved.State.Rotation,Saved.State.PositionCm));}}
    Impl->Previous=Impl->Time=At;Result->TryGetBoolField(TEXT("zeroGravity"),Impl->ZeroGravity);return true;
}
void FProphecyBodyflipProjectiles::InvalidateHistory(){Impl->ClearHistory();}
void FProphecyBodyflipProjectiles::SetPaused(bool Paused)
{
    if(Impl->Paused==Paused)return;Impl->Paused=Paused;if(!Impl->Physics.IsValid())return;for(auto& Pair:Impl->Entries){auto& E=*Pair.Value;if(!E.Body.IsSet())continue;if(Paused&& !Impl->Physics->ReadBody(E.Body,E.PausedState).IsSuccess())continue;Impl->Physics->RestoreBodyState(E.Body,E.PausedState,Paused);}
}
void FProphecyBodyflipProjectiles::Reset(){Impl->Clear();Impl->ClearHistory();Impl->Previous=Impl->Time=0;}
bool ProphecyBodyflip::ProjectileStepSchedule(UWorld* World,FProphecyJoltStepSchedule& Out)
{
    TArray<FProphecyBodyflipProjectiles::FImpl*> Live;for(auto* I:BodyflipProjectile::Instances)if(I->World==World&&!I->Paused){bool Active=false;for(auto& Pair:I->Entries){const auto& E=*Pair.Value;if(!E.Launch)continue;Active=true;if(!E.Body.IsSet()&&I->Time>I->Previous){const double F=(E.Release-I->Previous)/(I->Time-I->Previous);if(F>0&&F<1)Out.Fractions.Add(F);}}if(Active)Live.Add(I);}
    if(Live.IsEmpty())return false;Out.Before=[Live](double Fraction,double Dt){for(auto* I:Live){auto S=I->Before(Fraction,Dt);if(!S.IsSuccess())return S;}return FProphecyJoltWorldStatus{};};Out.After=[Live](double F){for(auto* I:Live)I->After(F);};return true;
}
