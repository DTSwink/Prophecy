#include "ProphecyOil.h"
#include "ProphecyOilDebris.h"
#include "ProphecyOilLiquid.h"
#include "ProphecyPhysicsStaticMeshComponent.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltStaticMeshLibrary.h"
#include "ProphecyJoltHitImpactLibrary.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

AProphecyOilBottle::AProphecyOilBottle()
{
    PrimaryActorTick.bCanEverTick=false;
    Bottle=CreateDefaultSubobject<UProphecyPhysicsStaticMeshComponent>(TEXT("Bottle"));RootComponent=Bottle;
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Shape(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    if(Shape.Succeeded())Bottle->SetStaticMesh(Shape.Object);
    Bottle->SetRelativeScale3D(FVector(.09,.09,.22));Bottle->SetCollisionProfileName(TEXT("PhysicsActor"));
    Bottle->SetSimulatePhysics(true);Bottle->SetNotifyRigidBodyCollision(true);Bottle->BodyInstance.bUseCCD=true;
    auto* Liquid=CreateDefaultSubobject<UProphecyOilLiquid>(TEXT("OilInside"));Liquid->SetupAttachment(Bottle);
}
void AProphecyOilBottle::BeginPlay()
{
    Super::BeginPlay();Bottle->OnComponentHit.AddUniqueDynamic(this,&ThisClass::Hit);
    if(bLaunchOnPlay)Bottle->SetPhysicsLinearVelocity(LaunchVelocity,false,NAME_None);
}
void AProphecyOilBottle::Hit(UPrimitiveComponent*,AActor* Other,UPrimitiveComponent*,FVector,const FHitResult& H)
{
    if(bBroken || !bBreakOnHit || !Other || Other==this)return;
    double Speed=0;FVector Relative;
    // Sample supplied by the current Jolt hit, before the contact solver slowed the body.
    // No polling/history and no resting-force accumulation. Manual Break Bottle also remains available.
    if(!UProphecyJoltHitImpactLibrary::GetHitImpactSpeed(this,Speed,Relative))return;
    LastImpactSpeed=Speed;
    if(FMath::IsFinite(BreakImpactSpeed) && Speed>=FMath::Max(0.f,BreakImpactSpeed))
        BreakBottle(H.ImpactPoint,H.ImpactNormal.GetSafeNormal());
}
void AProphecyOilBottle::BreakBottle(const FVector& Location,const FVector& Normal)
{
    if(bBroken || !GetWorld() || !GetWorld()->IsGameWorld() || Location.ContainsNaN() || Normal.ContainsNaN())return;
    bBroken=true;
    FVector Velocity=Bottle->GetPhysicsLinearVelocity(),Angular=Bottle->GetPhysicsAngularVelocityInRadians(),COM=Bottle->GetCenterOfMass();
    TInlineComponentArray<UProphecyJoltBodyComponent*> Adapters(this);
    for(auto* Adapter:Adapters)if(Adapter->GetSourceComponent()==Bottle)
    {
        FProphecyJoltBodyState B;
        if(Adapter->GetBodyState(B)){Velocity=B.CenterOfMassVelocityCmPerSecond;Angular=B.AngularVelocityRadiansPerSecond;COM=B.CenterOfMassPositionCm;}
    }
    FVector Incoming,Tip,Origin,IncomingAngular;FRotator Rotation;
    if(UProphecyJoltHitImpactLibrary::GetHitPreImpactState(this,0,Incoming,Tip,IncomingAngular,Origin,Rotation))
    {Angular=IncomingAngular;Velocity=Incoming+FVector::CrossProduct(Angular,COM-Bottle->GetComponentLocation());}
    for(auto* Adapter:Adapters)if(Adapter->GetSourceComponent()==Bottle)Adapter->DisableBody();
    UProphecyJoltStaticMeshLibrary::DisableJoltStaticMeshPhysics(Bottle);
    Bottle->SetSimulatePhysics(false);Bottle->SetCollisionEnabled(ECollisionEnabled::NoCollision);Bottle->SetVisibility(false);
    if(bSpawnFragments && Bottle->GetStaticMesh() && FragmentLifetime>0 && FMath::IsFinite(FragmentLifetime) && !FragmentMeshes.IsEmpty())
        if(auto* Debris=GetWorld()->SpawnActor<AProphecyOilDebris>())Debris->Initialize(*this,Velocity,Angular,COM);
    auto* Spill=GetWorld()->SpawnActor<AProphecyOilSpill>();
    if(Spill && !Spill->InitializeSplash(Location,Normal,Velocity,Oil))Spill->Destroy();
    Destroy();
}
AProphecyOilDebris::AProphecyOilDebris()
{
    PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickGroup=TG_PostUpdateWork;
}
void AProphecyOilDebris::Initialize(AProphecyOilBottle& Source,const FVector& Velocity,const FVector& Angular,const FVector& COM)
{
    Lifetime=FMath::Max(1,FMath::RoundToInt(FMath::Clamp(Source.FragmentLifetime,0.f,600.f)*60));
    Fade=FMath::IsFinite(Source.FragmentFadeDuration)?FMath::Clamp(FMath::RoundToInt(FMath::Clamp(Source.FragmentFadeDuration,0.f,600.f)*60),0,Lifetime):0;
    LastFrame=GFrameCounter;
    const auto Transform=Source.Bottle->GetComponentTransform();
    const FVector Center=Transform.TransformPosition(Source.Bottle->GetStaticMesh()->GetBounds().Origin);
    TArray<UMaterialInterface*> Slots;
    for(int32 I=0;I<Source.Bottle->GetNumMaterials();++I)
    {
        auto* Material=Source.Bottle->GetMaterial(I);float Opacity=1;
        if(Fade && Material && Material->GetScalarParameterValue(FMaterialParameterInfo(TEXT("FragmentOpacity")),Opacity))
        {
            // UE rejects dynamic instances as parents. Retain the actual shader/
            // static permutation, then copy the bottle's current uniform overrides.
            UMaterialInterface* Parent=Material;
            while(auto* Live=Cast<UMaterialInstanceDynamic>(Parent))Parent=Live->Parent;
            auto* Dynamic=UMaterialInstanceDynamic::Create(Parent,this);
            Dynamic->CopyMaterialUniformParameters(Material);
            Dynamic->SetScalarParameterValue(TEXT("FragmentOpacity"),1);Materials.Add(Dynamic);Slots.Add(Dynamic);
        }
        else
        {
            Slots.Add(Material);
            if(Fade && Material)UE_LOG(LogTemp,Warning,TEXT("Oil debris: %s has no FragmentOpacity parameter; retaining its appearance until expiry."),*Material->GetPathName());
        }
    }
    const float Kick=FMath::IsFinite(Source.FragmentVelocity)?FMath::Max(0.f,Source.FragmentVelocity):0;
    // Bounded precomputed meshes, no runtime fracturing or component tick per piece.
    for(int32 I=0;I<FMath::Min(64,Source.FragmentMeshes.Num());++I)
    {
        UStaticMesh* Mesh=Source.FragmentMeshes[I];if(!Mesh)continue;
        auto* A=GetWorld()->SpawnActorDeferred<AStaticMeshActor>(AStaticMeshActor::StaticClass(),Transform,nullptr,nullptr,ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if(!A)continue;
        auto* C=A->GetStaticMeshComponent();C->SetMobility(EComponentMobility::Movable);C->SetStaticMesh(Mesh);
        for(int32 Slot=0;Slot<Slots.Num();++Slot)C->SetMaterial(Slot,Slots[Slot]);
        C->SetCollisionProfileName(TEXT("PhysicsActor"));C->SetGenerateOverlapEvents(false);C->SetCanEverAffectNavigation(false);
        C->BodyInstance.bUseCCD=true;
        A->FinishSpawning(Transform);C->SetSimulatePhysics(true);
        const FVector PieceCOM=C->GetCenterOfMass();
        C->SetPhysicsLinearVelocity(Velocity+FVector::CrossProduct(Angular,PieceCOM-COM)+(PieceCOM-Center).GetSafeNormal()*Kick);
        C->SetPhysicsAngularVelocityInRadians(Angular);
        FString Error;
        if(!UProphecyJoltStaticMeshLibrary::EnableJoltStaticMeshPhysics(C,Error))
        {UE_LOG(LogTemp,Warning,TEXT("Oil debris admission failed: %s"),*Error);A->Destroy();continue;}
        A->Tags.Add(TEXT("OilBottleFragment"));Pieces.Add(A);
    }
    if(Pieces.IsEmpty())Destroy();
}
void AProphecyOilDebris::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(DeltaSeconds<=0 || GetWorld()->IsPaused() || LastFrame==GFrameCounter)return;
    LastFrame=GFrameCounter;++Age;
    if(Fade && Age>=Lifetime-Fade)
        for(UMaterialInstanceDynamic* Material:Materials)Material->SetScalarParameterValue(TEXT("FragmentOpacity"),FMath::Clamp(float(Lifetime-Age)/Fade,0.f,1.f));
    if(Age>=Lifetime)Destroy();
}
void AProphecyOilDebris::EndPlay(const EEndPlayReason::Type Reason)
{
    for(AStaticMeshActor* Piece:Pieces)if(IsValid(Piece))Piece->Destroy();
    Pieces.Empty();Materials.Empty();Super::EndPlay(Reason);
}
