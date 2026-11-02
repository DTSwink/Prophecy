#include "ProphecyOil.h"
#include "ProphecyOilCoverage.h"
#include "ProphecyPhysicsStaticMeshComponent.h"
#include "ProphecyJoltStaticMeshLibrary.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/DecalComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "ProceduralMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "NiagaraSystemInstanceController.h"
#include "UObject/ConstructorHelpers.h"

struct FProphecyOilSpillState
{
    struct FPatch {uint64 Id=0;FProphecyJoltBodyHandle Body;FVector Point,Normal;float Radius=0,Applied=-1;uint64 Born=0;bool bLanding=false;TSharedPtr<FProphecyOilCoverageStamp> Coverage;};
    struct FDrop
    {
        FVector Position,Velocity,LocalLanding,LandingNormal;
        FProphecyJoltBodyHandle LandingBody;
        float Size=1,Radius=20;int32 Delay=0;uint64 Landed=0;
        bool bAlive=true,bMovingLanding=false;
    };
    TArray<FPatch> Patches;
    TArray<FDrop> Flight;
    TWeakObjectPtr<UNiagaraComponent> Spray;
    bool bSprayStarted=false;
    TWeakObjectPtr<UProceduralMeshComponent> Sheet;
    TArray<FVector> SheetVertices,SheetNormals;
    TArray<FVector2D> SheetUV;
    TArray<FLinearColor> SheetColors;
    TArray<FProcMeshTangent> SheetTangents;
    TArray<int32> SheetTriangles;
    FVector Origin,Normal;
    int32 SheetSpokes=0,SheetNodes=0;
    uint64 Age=0;
};
void FProphecyOilSpillStateDeleter::operator()(FProphecyOilSpillState* P) const {delete P;}
AProphecyOilSpill::AProphecyOilSpill()
{
    PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.bStartWithTickEnabled=false;PrimaryActorTick.TickGroup=TG_PrePhysics;
}
AProphecyOilSpill::~AProphecyOilSpill()=default;
bool AProphecyOilSpill::Prepare(const FVector& Location,const FVector& Normal,const FProphecyOilSettings& In)
{
    if(State || Location.ContainsNaN() || Normal.ContainsNaN() || !Normal.IsNormalized()
        || !FMath::IsFinite(In.Radius) || In.Radius<10 || In.Radius>600 || !FMath::IsFinite(In.Slipperiness)
        || In.Slipperiness<0 || In.Slipperiness>1 || !FMath::IsFinite(In.HoldDuration) || In.HoldDuration<0
        || !FMath::IsFinite(In.FadeDuration) || In.FadeDuration<0 || In.HoldDuration+In.FadeDuration>86400
        || In.DropletCount<8 || In.DropletCount>64)return false;
    auto* World=GetWorld();auto* Native=World?World->GetSubsystem<UProphecyJoltWorldSubsystem>():nullptr;if(!Native)return false;
    Settings=In;State.Reset(new FProphecyOilSpillState());
    return true;
}
bool AProphecyOilSpill::Deposit(const FProphecyJoltRayHit& Ray,float Radius,bool bFreshLanding)
{
    auto* Native=GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltBodyState Body;if(!Native || !Native->ReadBody(Ray.Handle,Body).IsSuccess())return false;
    const FTransform T(Body.Rotation,Body.PositionCm);
    const FVector LocalPoint=T.InverseTransformPosition(Ray.PositionCm),LocalNormal=T.InverseTransformVectorNoScale(Ray.Normal);
    // A drop wholly inside a fresh wet footprint needs no duplicate decal/contact patch.
    if(bFreshLanding)for(const auto& P:State->Patches)
        if(P.Id && P.Body.Slot==Ray.Handle.Slot && P.Body.Generation==Ray.Handle.Generation
            && FVector::DotProduct(P.Normal,LocalNormal)>.98 && State->Age-P.Born<30
            && FVector::Distance(P.Point,LocalPoint)+Radius<=P.Radius*.9f)return true;
    uint64 Id=0;
    if(!Native->AddOilPatch(Ray.Handle,Ray.PositionCm,Ray.Normal,Radius,bFreshLanding?0.f:Settings.Slipperiness,Id).IsSuccess())return false;
    auto& Patch=State->Patches.AddDefaulted_GetRef();Patch.Id=Id;Patch.Body=Ray.Handle;
    Patch.Point=LocalPoint;Patch.Normal=LocalNormal;Patch.Radius=Radius;Patch.Born=State->Age;Patch.bLanding=bFreshLanding;
    UObject* Receiver=nullptr;Native->ResolveAssociatedObject(Ray.Handle,Receiver);
    const auto* Component=Cast<USceneComponent>(Receiver);
    const bool Moving=Body.bDynamic || (Component && Component->Mobility!=EComponentMobility::Static);
    Patch.Coverage=ProphecyOilCoverage::Add(GetWorld(),Ray.Handle,LocalPoint,LocalNormal,Radius,Moving,bFreshLanding,Settings);
    return true;
}
bool AProphecyOilSpill::Initialize(const FVector& Location,const FVector& Normal,const FProphecyOilSettings& In)
{
    if(!Prepare(Location,Normal,In))return false;
    auto* World=GetWorld();auto* Native=World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FVector U,V;Normal.FindBestAxisVectors(U,V);
    // Nine bounded surface samples at impact. No recurring traces or particle readback.
    TArray<FProphecyJoltRayHit,TInlineAllocator<9>> Samples;
    bool bFlat=In.Radius<=300;
    for(int32 I=0;I<9;++I)
    {
        const float Angle=(I-1)*PI/4.f;
        const FVector P=Location+(I?(.6f*In.Radius)*(U*FMath::Cos(Angle)+V*FMath::Sin(Angle)):FVector::ZeroVector);
        FProphecyJoltRayHit Ray;bool bHit=false;
        if(!Native->RayCast(P+Normal*80,P-Normal*100,Ray,bHit,TEXT("OilBottleFragment")).IsSuccess() || !bHit || FVector::DotProduct(Ray.Normal,Normal)<.5){bFlat=false;continue;}
        Samples.Add(Ray);
    }
    for(const auto& Ray:Samples)
        if(Ray.Handle.Slot!=Samples[0].Handle.Slot || Ray.Handle.Generation!=Samples[0].Handle.Generation
            || FVector::DotProduct(Ray.Normal,Samples[0].Normal)<.9999
            || FMath::Abs(FVector::DotProduct(Ray.PositionCm-Samples[0].PositionCm,Samples[0].Normal))>.5)bFlat=false;
    // The common flat-floor case needs one decal/contact patch, not nine overlapping ones.
    if(bFlat && Samples.Num()==9)Samples.SetNum(1);else bFlat=false;
    for(const auto& Ray:Samples)Deposit(Ray,bFlat?In.Radius:In.Radius*.5f,false);
    if(State->Patches.IsEmpty()){State.Reset();return false;}
    if(In.SplashSystem)UNiagaraFunctionLibrary::SpawnSystemAtLocation(World,In.SplashSystem,Location,Normal.Rotation(),FVector(1),true,true);
    SetActorTickEnabled(true);return true;
}
bool AProphecyOilSpill::InitializeSplash(const FVector& Location,const FVector& Normal,const FVector& Velocity,const FProphecyOilSettings& In)
{
    if(Velocity.ContainsNaN() || !Prepare(Location,Normal,In))return false;
    FVector U,V;Normal.FindBestAxisVectors(U,V);
    FRandomStream R(HashCombine(GetTypeHash(Location),1739));
    // Collision samples deposit oil; the separate Niagara spray is cosmetic only.
    State->Flight.Reserve(In.DropletCount);
    const FVector Drift=FVector::VectorPlaneProject(Velocity,Normal).GetClampedToMaxSize(500)*.2;
    State->Origin=Location+Normal*3;State->Normal=Normal;
    // Spend the existing particle/query budget on a filled radial sheet.
    // Three rings plus a center cover the interior; a few separate drops form its fringe.
    State->SheetSpokes=In.DropletCount>=13?FMath::Min(16,(In.DropletCount-1)/3):0;
    State->SheetNodes=State->SheetSpokes?1+3*State->SheetSpokes:0;
    for(int32 I=0;I<In.DropletCount;++I)
    {
        const bool bSheet=I<State->SheetNodes;
        const int32 Ring=bSheet && I>0?(I-1)/State->SheetSpokes:0;
        const float A=bSheet && I>0?((I-1)%State->SheetSpokes)*2*PI/State->SheetSpokes:I*2.399963f;
        const float Shape=1.f+.15f*FMath::Sin(3*A+.8f)+.075f*FMath::Sin(5*A);
        const float Out=bSheet?(I==0?0.f:(.22f+.25f*Ring)*Shape):R.FRandRange(.74f,.92f);
        // A coherent sheet shares its flight arc. The old 110/140/170/200
        // center-to-rim speeds left a separate puddle beneath an airborne ring.
        const float Ripple=I>0?(3.f*FMath::Sin(3*A+1.2f)+2.f*FMath::Sin(5*A)):0.f;
        const float Up=bSheet?180.f+Ripple:R.FRandRange(210,250);
        auto& D=State->Flight.AddDefaulted_GetRef();D.Position=State->Origin;
        D.Velocity=Normal*Up+(U*FMath::Cos(A)+V*FMath::Sin(A))*(In.Radius*Out/(2.f*Up/980.f))+Drift;
        D.Size=bSheet?1.4f:R.FRandRange(.7f,1.3f);
        D.Radius=FMath::Clamp(In.Radius*(bSheet?.24f:R.FRandRange(.12f,.16f)),4.f,180.f);
        D.Delay=bSheet?0:I%4;
    }
    if(In.DropletMaterial && State->SheetNodes)
    {
        // Traced sheet samples carry area, while free fringe samples are drops.
        // On contact that area transfers to the coating without a second overlay.
        auto* Sheet=NewObject<UProceduralMeshComponent>(this);State->Sheet=Sheet;
        Sheet->SetCollisionEnabled(ECollisionEnabled::NoCollision);Sheet->SetCanEverAffectNavigation(false);
        Sheet->SetCastShadow(false);Sheet->bReceivesDecals=false;Sheet->RegisterComponent();Sheet->SetMaterial(0,In.DropletMaterial);
        const int32 RenderSpokes=State->SheetSpokes*4,Count=1+RenderSpokes*3;
        State->SheetVertices.Init(State->Origin,Count);State->SheetNormals.Init(Normal,Count);
        State->SheetColors.Init(FLinearColor(1,1,1,0),Count);State->SheetUV.SetNumZeroed(Count);State->SheetTangents.SetNum(Count);
        for(int32 I=0;I<RenderSpokes;++I)
        {
            const int32 Next=(I+1)%RenderSpokes;
            State->SheetTriangles.Append({0,1+I,1+Next});
            for(int32 Row=0;Row<3;++Row)
            {
                const int32 A=1+Row*RenderSpokes+I,B=1+Row*RenderSpokes+Next;
                State->SheetUV[A]=FVector2D(float(I)/RenderSpokes,(Row+1)/3.f);
                if(Row<2)State->SheetTriangles.Append({A,A+RenderSpokes,B,B,A+RenderSpokes,B+RenderSpokes});
            }
        }
        Sheet->CreateMeshSection_LinearColor(0,State->SheetVertices,State->SheetTriangles,State->SheetNormals,State->SheetUV,State->SheetColors,State->SheetTangents,false);
    }
    if(In.SplashSystem)
    {
        auto* Spray=NewObject<UNiagaraComponent>(this);State->Spray=Spray;
        Spray->SetAsset(In.SplashSystem);Spray->SetAutoActivate(false);Spray->SetForceSolo(true);
        Spray->SetWorldLocationAndRotation(State->Origin,FRotationMatrix::MakeFromZ(Normal).Rotator());
        Spray->SetWorldScale3D(FVector(In.Radius/150.f));Spray->SetCastShadow(false);
        Spray->SetCanEverAffectNavigation(false);Spray->RegisterComponent();Spray->Activate(true);
        // No independent wall-clock tick: advance once per authored game tick.
        Spray->SetComponentTickEnabled(false);
#if !UE_BUILD_SHIPPING
        if(FParse::Param(FCommandLine::Get(),TEXT("ProphecyOilNiagaraFlower")))
            UE_LOG(LogTemp,Display,TEXT("OilNiagara spawn ready=%d valid=%d active=%d complete=%d asset=%s"),In.SplashSystem->IsReadyToRun(),In.SplashSystem->IsValid(),Spray->IsActive(),Spray->IsComplete(),*In.SplashSystem->GetName());
#endif
    }
    SetActorTickEnabled(true);return true;
}
float AProphecyOilSpill::GetOilAmount() const
{
    if(!State)return 0;
    float Amount=0;for(const auto& P:State->Patches)if(P.Id)Amount=FMath::Max(Amount,ProphecyOilCoverage::Amount(P.Coverage));
    return Amount;
}
void AProphecyOilSpill::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);if(!State || GetWorld()->IsPaused())return;
    ++State->Age;auto* Native=GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    if(!Native){Destroy();return;}
    if(auto* Spray=State->Spray.Get())
    {
        if(!State->bSprayStarted && Spray->GetAsset()->IsReadyToRun())
        {
            Spray->Activate(true);Spray->SetComponentTickEnabled(false);
            State->bSprayStarted=Spray->GetSystemInstanceController().IsValid();
            if(State->bSprayStarted)Spray->AdvanceSimulation(int32(State->Age),1.f/60.f);
        }
        else if(State->bSprayStarted)Spray->AdvanceSimulation(1,1.f/60.f);
#if !UE_BUILD_SHIPPING
        if(State->Age<4 && FParse::Param(FCommandLine::Get(),TEXT("ProphecyOilNiagaraFlower")))
            UE_LOG(LogTemp,Display,TEXT("OilNiagara age=%llu sim=%.4f active=%d complete=%d"),State->Age,Spray->GetSystemInstanceController()?Spray->GetSystemInstanceController()->GetAge():-1.f,Spray->IsActive(),Spray->IsComplete());
#endif
        if((State->bSprayStarted && Spray->IsComplete()) || State->Age>=90){Spray->DestroyComponent();State->Spray.Reset();}
    }
    int32 Flying=0;
    for(int32 I=0;I<State->Flight.Num();++I)
    {
        auto& D=State->Flight[I];if(!D.bAlive)continue;
        if(State->Age<=uint64(D.Delay)){++Flying;continue;}
        constexpr double Dt=1./60.;const FVector Next=D.Position+D.Velocity*Dt+FVector(0,0,-490)*Dt*Dt;
        FProphecyJoltRayHit Ray;bool bHit=false;
        if(Native->RayCast(D.Position,Next,Ray,bHit,TEXT("OilBottleFragment")).IsSuccess() && bHit)
        {
            Deposit(Ray,D.Radius,I>=State->SheetNodes);D.bAlive=false;D.Landed=State->Age;
            D.Position=Ray.PositionCm+Ray.Normal*.3;D.LandingBody=Ray.Handle;
            FProphecyJoltBodyState B;
            if(Native->ReadBody(Ray.Handle,B).IsSuccess())
            {
                const FTransform T(B.Rotation,B.PositionCm);D.LocalLanding=T.InverseTransformPosition(D.Position);
                D.LandingNormal=T.InverseTransformVectorNoScale(Ray.Normal);D.bMovingLanding=B.bDynamic;
            }
        }
        else if(State->Age>=120)D.bAlive=false;
        else {D.Position=Next;D.Velocity.Z-=980*Dt;++Flying;}
    }
    if(auto* Sheet=State->Sheet.Get())
    {
        auto Opacity=[](const FProphecyOilSpillState::FDrop& D){return D.bAlive?1.f:0.f;};
        bool Visible=false;
        for(int32 I=0;I<State->SheetNodes;++I)
        {
            auto& D=State->Flight[I];
            const float Alpha=Opacity(D);
            Visible|=Alpha>0;
            if(Alpha>0 && D.Landed && D.bMovingLanding)
            {
                FProphecyJoltBodyState B;if(Native->ReadBody(D.LandingBody,B).IsSuccess())
                    D.Position=FTransform(B.Rotation,B.PositionCm).TransformPosition(D.LocalLanding);
            }
        }
        if(!Visible)
        {
            Sheet->DestroyComponent();State->Sheet.Reset();State->SheetVertices.Empty();State->SheetNormals.Empty();
            State->SheetColors.Empty();State->SheetUV.Empty();State->SheetTangents.Empty();State->SheetTriangles.Empty();
        }
        else
        {
            // Smooth display-only samples between traced nodes; no extra rays.
            // At contact use linear interpolation to avoid undershooting the surface.
            const int32 RenderSpokes=State->SheetSpokes*4;
            for(int32 I=0;I<State->SheetVertices.Num();++I)
            {
                FVector P=State->Flight[0].Position;float Alpha=Opacity(State->Flight[0]);
                if(I>0)
                {
                    const int32 Ring=(I-1)/RenderSpokes,K=(I-1)%RenderSpokes,Spoke=K/4;
                    const float T=(K%4)*.25f;
                    auto Node=[&](int32 Offset)->const FProphecyOilSpillState::FDrop&
                    {return State->Flight[1+Ring*State->SheetSpokes+(Spoke+Offset+State->SheetSpokes)%State->SheetSpokes];};
                    const auto& A=Node(-1);const auto& B=Node(0);const auto& C=Node(1);const auto& D=Node(2);
                    P=FMath::Lerp(B.Position,C.Position,T);Alpha=FMath::Lerp(Opacity(B),Opacity(C),T);
                    if(A.bAlive && B.bAlive && C.bAlive && D.bAlive)
                        P=.5*(2*B.Position+(C.Position-A.Position)*T+(2*A.Position-5*B.Position+4*C.Position-D.Position)*T*T
                            +(-A.Position+3*B.Position-3*C.Position+D.Position)*T*T*T);
                }
                // Flared crown: low center, rising curved petals, collapsing to the
                // actual landing surface. Display only; deposit trajectories stay exact.
                const float Radial=I>0?float(1+(I-1)/RenderSpokes)/3.f:0.f;
                const float Angle=I>0?2.f*PI*((I-1)%RenderSpokes)/RenderSpokes:0.f;
                const float Height=FMath::Max(0.f,float(FVector::DotProduct(P-State->Origin,State->Normal)));
                const float Profile=.12f+2.6f*Radial*Radial*(1.f+.18f*FMath::Sin(5.f*Angle+.7f));
                P+=State->Normal*(Height*(Profile-1.f)*Alpha);
                State->SheetVertices[I]=P;State->SheetNormals[I]=FVector::ZeroVector;
                State->SheetColors[I]=FLinearColor(1,1,1,Alpha*FMath::Clamp(float(State->Age)/3.f,0.f,1.f));
            }
            for(int32 I=0;I<State->SheetTriangles.Num();I+=3)
            {
                const int32 A=State->SheetTriangles[I],B=State->SheetTriangles[I+1],C=State->SheetTriangles[I+2];
                const FVector N=FVector::CrossProduct(State->SheetVertices[B]-State->SheetVertices[A],State->SheetVertices[C]-State->SheetVertices[A]);
                State->SheetNormals[A]+=N;State->SheetNormals[B]+=N;State->SheetNormals[C]+=N;
            }
            for(auto& N:State->SheetNormals)N=N.GetSafeNormal();
            Sheet->UpdateMeshSection_LinearColor(0,State->SheetVertices,State->SheetNormals,State->SheetUV,State->SheetColors,State->SheetTangents,false);
        }
    }
    if(!State->Flight.IsEmpty())
    {
        if(!Flying)
        {
            if(!State->Sheet.IsValid())State->Flight.Empty();
        }
    }
    ProphecyOilCoverage::Tick(GetWorld());
    int32 Alive=0;
    for(auto& P:State->Patches)
    {
        if(!P.Id)continue;
        const float Ramp=P.bLanding?FMath::Clamp(float(State->Age-P.Born)/6.f,0.f,1.f):1.f;
        const float Amount=ProphecyOilCoverage::Amount(P.Coverage);
        const float Strength=Amount*Ramp*Settings.Slipperiness;
        if(Amount<=0 || !Native->OwnsBody(P.Body)
            || (Strength!=P.Applied && !Native->SetOilStrength(P.Id,Strength).IsSuccess()))
        {
            Native->RemoveOilPatch(P.Id);P.Id=0;
            ProphecyOilCoverage::Remove(GetWorld(),P.Coverage);P.Coverage.Reset();continue;
        }
        P.Applied=Strength;++Alive;
    }
    if(!Alive && !Flying && !State->Sheet.IsValid() && !State->Spray.IsValid())Destroy();
}
void AProphecyOilSpill::EndPlay(const EEndPlayReason::Type Reason)
{
    if(State)for(const auto& P:State->Patches)if(P.Id)
    {
        if(auto* Native=GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>())Native->RemoveOilPatch(P.Id);
        ProphecyOilCoverage::Remove(GetWorld(),P.Coverage);
    }
    State.Reset();Super::EndPlay(Reason);
}
AProphecyOilSpill* UProphecyOilLibrary::SpawnOilSpill(UObject* Context,FVector Location,FVector Normal,const FProphecyOilSettings& Settings)
{
    auto* World=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    if(!World || !World->IsGameWorld())return nullptr;
    auto* Spill=World->SpawnActor<AProphecyOilSpill>();
    if(Spill && !Spill->Initialize(Location,Normal,Settings)){Spill->Destroy();return nullptr;}return Spill;
}
