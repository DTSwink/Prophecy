#include "ProphecyBombLibrary.h"
#include "ProphecyBombComponent.h"
#include "ProphecyBombFragmentFadeComponent.h"
#include "ProphecyBombFuseCapComponent.h"
#include "ProphecyVDBOptimisedComponent.h"
#include "ProphecyVDBColorComponent.h"
#include "ProphecyBombGeometry.h"
#include "ProphecyBombFuseCurve.h"
#include "ProphecyVDBTiming.h"
#include "ProphecyExplosionLibrary.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/Material.h"
#include "PhysicsEngine/BodyInstance.h"

UProphecyBombFuseCapComponent::UProphecyBombFuseCapComponent()
{
    PrimaryComponentTick.bCanEverTick=false;
    PrimaryComponentTick.bStartWithTickEnabled=false;
}
UProphecyBombComponent::UProphecyBombComponent()
{
    PrimaryComponentTick.bCanEverTick=true;
    PrimaryComponentTick.bStartWithTickEnabled=true;
    PrimaryComponentTick.TickGroup=TG_PostUpdateWork;
}
void UProphecyBombComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if(IsValid(Sparks)){Sparks->Deactivate();Sparks=nullptr;}
    Super::EndPlay(Reason);
}
bool UProphecyBombComponent::GetBurnTip(FVector& Position,FVector& Tangent) const
{
    if(!IsValid(Bomb))return false;
    const double Length=BombFuseArc[UE_ARRAY_COUNT(BombFuseArc)-1];
    const double Distance=Length*(1.-FMath::Clamp(double(Elapsed)/FMath::Max(uint64(1),BurnTicks),0.,1.));
    int32 Ring=0;while(Ring+2<UE_ARRAY_COUNT(BombFuseArc) && BombFuseArc[Ring+1]<Distance)++Ring;
    const FTransform Transform=Bomb->GetComponentTransform();
    const FVector A=Transform.TransformPosition(BombFuseCenters[Ring]);
    const FVector B=Transform.TransformPosition(BombFuseCenters[Ring+1]);
    Position=FMath::Lerp(A,B,(Distance-BombFuseArc[Ring])/(BombFuseArc[Ring+1]-BombFuseArc[Ring]));
    Tangent=(B-A).GetSafeNormal();return !Position.ContainsNaN() && !Tangent.IsNearlyZero();
}
void UProphecyBombComponent::TickComponent(float DeltaSeconds,ELevelTick Type,FActorComponentTickFunction* Tick)
{
    Super::TickComponent(DeltaSeconds,Type,Tick);
    if(Type!=LEVELTICK_All || DeltaSeconds<=0 || GetWorld()->IsPaused() || LastFrame==GFrameCounter)return;
    LastFrame=GFrameCounter;++Elapsed;
    if(bDebris)
    {
        if(auto* Fade=GetOwner()->FindComponentByClass<UProphecyBombFragmentFadeComponent>();Fade && Fade->Material && Fade->FadeTicks)
        {
            const uint64 Duration=FMath::Min(Fade->FadeTicks,DebrisTicks);
            const uint64 Start=DebrisTicks-Duration;
            if(Elapsed>=Start)
            {
                if(!Fade->bApplied)
                {
                    for(AActor* Actor:Debris)if(auto* Piece=Cast<AStaticMeshActor>(Actor);IsValid(Piece))
                        Piece->GetStaticMeshComponent()->SetMaterial(0,Fade->Material);
                    Fade->bApplied=true;
                }
                const float Opacity=Elapsed>=DebrisTicks?0.f:float(double(DebrisTicks-Elapsed)/Duration);
                Fade->Material->SetScalarParameterValue(TEXT("FragmentOpacity"),Opacity);
            }
        }
        if(Elapsed>=DebrisTicks)
        {
            for(AActor* Actor:Debris)if(IsValid(Actor))Actor->Destroy();
            GetOwner()->Destroy();
        }
        return;
    }
    if(!IsValid(Bomb) || !IsValid(Material) || !IsValid(Visual))
    {if(IsValid(Sparks))Sparks->Deactivate();if(IsValid(Visual))Visual->DestroyComponent();DestroyComponent();return;}
    if(IsValid(ShellVisual) && ShellVisual->GetMaterial(0)!=Bomb->GetMaterial(0))ShellVisual->SetMaterial(0,Bomb->GetMaterial(0));
    if(!bBurning){Elapsed=0;return;}
    if(const auto* Cap=GetOwner()->FindComponentByClass<UProphecyBombFuseCapComponent>();Cap && Elapsed>=Cap->DetonationTicks)
    {Detonate();return;}
    if(Elapsed>=BurnTicks){Detonate();return;}
    if(!bFuseHidden)Material->SetScalarParameterValue(TEXT("FuseRemaining"),1.f-float(double(Elapsed)/BurnTicks)*.99f);
    if(IsValid(Sparks))
    {
        FVector Position,Tangent;
        if(GetBurnTip(Position,Tangent))Sparks->SetWorldLocationAndRotation(Position,FQuat::Identity);
    }
}
void UProphecyBombComponent::Detonate()
{
    SetComponentTickEnabled(false);
    if(IsValid(Sparks)){Sparks->Deactivate();Sparks=nullptr;}
    const FTransform Transform=Bomb->GetComponentTransform();
    const FVector Centre=Transform.TransformPosition(FVector(-1.0239047,0,-1.2153458));
    const FVector Velocity=Bomb->GetPhysicsLinearVelocity();
    const FVector Angular=Bomb->GetPhysicsAngularVelocityInRadians();
    const FVector COM=Bomb->GetCenterOfMass();
    // Read the effective slot at detonation, including component overrides and live MIDs.
    UMaterialInterface* ShellMaterial=Bomb->GetMaterial(0);
    // Consume the intact collider before applying the blast; fragments have their own explicit kick.
    Bomb->SetSimulatePhysics(false);Bomb->SetCollisionEnabled(ECollisionEnabled::NoCollision);Bomb->SetVisibility(false,true);
    UProphecyExplosionLibrary::StartExplosion(this,Centre,Intensity,Radius,FalloffExponent,ExplosionVelocity);
    const bool bOptimised=GetOwner()->FindComponentByClass<UProphecyBombVDBOptimisedComponent>()!=nullptr;
    const auto* Colors=GetOwner()->FindComponentByClass<UProphecyBombVDBColorComponent>();
    UProphecyVDBLibrary::SpawnVDBEffect(this,Effect,Centre,Scale,Framerate,FadeStart,TargetDensity,FadeDuration,Rotation,bOptimised,
        Colors?Colors->TemperatureColor:ProphecyVDB::DefaultTemperatureColor(),Colors?Colors->ScatteringColor:FLinearColor::White);
    if(Fragments.IsEmpty()){GetOwner()->Destroy();return;}
    auto* CleanupActor=GetWorld()->SpawnActor<AActor>();
    auto* Cleanup=NewObject<UProphecyBombComponent>(CleanupActor);
    CleanupActor->AddInstanceComponent(Cleanup);Cleanup->bDebris=true;Cleanup->DebrisTicks=DebrisTicks;Cleanup->LastFrame=GFrameCounter;
    if(auto* Settings=GetOwner()->FindComponentByClass<UProphecyBombFragmentFadeComponent>();Settings && Settings->FadeTicks)
    {
        // A custom translucent material can opt in with FragmentOpacity. For the imported
        // glTF family, use the prepared shader and copy current texture/scalar/vector values.
        float ExistingOpacity=1.f;
        UMaterialInterface* Parent=nullptr;
        if(ShellMaterial && ShellMaterial->GetBlendMode()==BLEND_Translucent && ShellMaterial->GetScalarParameterValue(FMaterialParameterInfo(TEXT("FragmentOpacity")),ExistingOpacity))Parent=ShellMaterial;
        else if(ShellMaterial && ShellMaterial->GetMaterial()->GetPathName()==TEXT("/InterchangeAssets/gltf/M_Default.M_Default"))Parent=Settings->Template;
        if(Parent)
        {
            auto* Fade=NewObject<UProphecyBombFragmentFadeComponent>(CleanupActor);CleanupActor->AddInstanceComponent(Fade);
            Fade->FadeTicks=Settings->FadeTicks;Fade->Material=UMaterialInstanceDynamic::Create(Parent,Fade);
            Fade->Material->CopyMaterialUniformParameters(ShellMaterial);
            Fade->Material->SetScalarParameterValue(TEXT("FragmentOpacity"),1.f);Fade->RegisterComponent();
        }
        else UE_LOG(LogTemp,Warning,TEXT("Bomb fragment fade: material %s needs a translucent FragmentOpacity parameter; preserving its appearance and normal expiry."),*GetPathNameSafe(ShellMaterial));
    }
    for(UStaticMesh* Mesh:Fragments)
    {
        auto* Actor=GetWorld()->SpawnActorDeferred<AStaticMeshActor>(AStaticMeshActor::StaticClass(),Transform,nullptr,nullptr,ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if(!Actor)continue;
        auto* Component=Actor->GetStaticMeshComponent();
        Component->SetMobility(EComponentMobility::Movable);Component->SetStaticMesh(Mesh);
        Component->SetMaterial(0,ShellMaterial);
        Component->SetCollisionProfileName(TEXT("PhysicsActor"));
        // Fragments collide with the world/characters, not with adjacent fragments at detonation.
        Component->SetCollisionResponseToChannel(ECC_PhysicsBody,ECR_Ignore);
        Component->BodyInstance.bUseCCD=true;
        Actor->FinishSpawning(Transform);
        Component->SetSimulatePhysics(true);
        const FVector FragmentCOM=Component->GetCenterOfMass();
        Component->SetPhysicsLinearVelocity(Velocity+FVector::CrossProduct(Angular,FragmentCOM-COM)+(FragmentCOM-Centre).GetSafeNormal()*FragmentVelocity);
        Cleanup->Debris.Add(Actor);
    }
    Cleanup->RegisterComponent();
    GetOwner()->Destroy();
}
static UProphecyBombComponent* PrepareStaticBomb(UStaticMeshComponent* Bomb)
{
    if(!IsInGameThread() || !IsValid(Bomb) || !Bomb->GetWorld() || !Bomb->GetWorld()->IsGameWorld() || !Bomb->GetOwner())return nullptr;
    UStaticMesh* Original=Bomb->GetStaticMesh();
    if(!Original || Original->GetPathName()!=TEXT("/Game/Fab/CC0_-_Bomb/cc0_bomb/StaticMeshes/cc0_bomb.cc0_bomb"))return nullptr;
    if(auto* Existing=Bomb->GetOwner()->FindComponentByClass<UProphecyBombComponent>())return Existing->Bomb==Bomb?Existing:nullptr;
    auto* Mesh=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/_mygame/BombGenerated/SM_BombFuse.SM_BombFuse"));
    auto* BurnMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/_mygame/BombGenerated/MI_BombBurn.MI_BombBurn"));
    auto* ShellMesh=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/_mygame/BombGenerated/SM_BombShell.SM_BombShell"));
    if(!Mesh || !BurnMaterial || !ShellMesh)return nullptr;
    auto* Controller=NewObject<UProphecyBombComponent>(Bomb->GetOwner());Bomb->GetOwner()->AddInstanceComponent(Controller);Controller->Bomb=Bomb;
    const auto MakeVisual=[&](UStaticMesh* Asset,UMaterialInterface* Material)
    {
        auto* C=NewObject<UStaticMeshComponent>(Bomb->GetOwner());Bomb->GetOwner()->AddInstanceComponent(C);
        C->SetStaticMesh(Asset);C->SetMobility(EComponentMobility::Movable);C->SetupAttachment(Bomb);
        C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetGenerateOverlapEvents(false);
        C->SetCanEverAffectNavigation(false);C->SetComponentTickEnabled(false);
        C->SetMaterial(0,Material);C->SetCastShadow(Bomb->CastShadow);
        C->SetCustomDepthStencilValue(Bomb->CustomDepthStencilValue);C->SetRenderCustomDepth(Bomb->bRenderCustomDepth);
        C->RegisterComponent();return C;
    };
    Controller->Material=UMaterialInstanceDynamic::Create(BurnMaterial,Controller);
    Controller->Material->SetScalarParameterValue(TEXT("FuseRemaining"),1.f);
    Controller->Visual=MakeVisual(Mesh,Controller->Material);
    Controller->ShellVisual=MakeVisual(ShellMesh,Bomb->GetMaterial(0));
    Controller->AddTickPrerequisiteComponent(Bomb);Controller->LastFrame=GFrameCounter;
    Bomb->SetVisibility(false,false);Controller->RegisterComponent();return Controller;
}
bool UProphecyBombLibrary::HideBombFuse(UStaticMeshComponent* Bomb)
{
    auto* Controller=PrepareStaticBomb(Bomb);if(!Controller || !Controller->Visual)return false;
    Controller->bFuseHidden=true;Controller->Material->SetScalarParameterValue(TEXT("FuseRemaining"),-1.f);
    Controller->Visual->SetVisibility(false);
    if(IsValid(Controller->Sparks)){Controller->Sparks->DestroyComponent();Controller->Sparks=nullptr;}
    if(!Controller->bBurning)Controller->SetComponentTickEnabled(false);
    return true;
}
bool UProphecyBombLibrary::LightBombFuse(UStaticMeshComponent* Bomb,float FuseBurnSpeed,float FragmentVelocity,
    float Intensity,float Radius,float FalloffExponent,float ExplosionVelocity,EProphecyVDBEffect Effect,float Scale,
    float Framerate,float DensityFadeStart,float TargetDensity,float DensityFadeDuration,FRotator Rotation,float FragmentLifetime,
    UNiagaraSystem* FuseSparks,bool bInstantExplosion,bool bSpawnFragments,float FragmentFadeDuration,float FuseCap,bool bOptimised,
    FLinearColor TemperatureColor,FLinearColor ScatteringColor)
{
    if(!IsInGameThread() || !IsValid(Bomb) || !Bomb->GetWorld() || !Bomb->GetWorld()->IsGameWorld() || !Bomb->GetOwner()
       || Rotation.ContainsNaN() || !ProphecyVDB::IsValidColor(TemperatureColor) || !ProphecyVDB::IsValidColor(ScatteringColor))return false;
    if(!FMath::IsFinite(FuseCap))return false;
    FuseCap=FMath::Clamp(FuseCap,0.f,1.f);
    bInstantExplosion=bInstantExplosion || FuseCap>=1.f;
    auto* Existing=Bomb->GetOwner()->FindComponentByClass<UProphecyBombComponent>();
    if(Existing && ((!bInstantExplosion && Existing->bBurning) || Existing->Bomb!=Bomb))return false;
    for(float X:{FuseBurnSpeed,FragmentVelocity,Intensity,Radius,FalloffExponent,ExplosionVelocity,Scale,Framerate,DensityFadeStart,TargetDensity,DensityFadeDuration,FragmentLifetime,FragmentFadeDuration})
        if(!FMath::IsFinite(X) || X<0)return false;
    if((!bInstantExplosion && FuseBurnSpeed<=0) || Scale<=0 || Framerate<=0 || FragmentLifetime<=0 || Radius<=0 || Intensity<=0
       || DensityFadeStart>1.e6f || DensityFadeDuration>1.e6f || FragmentLifetime>1.e6f || FragmentFadeDuration>1.e6f
       || (Effect!=EProphecyVDBEffect::Shockwave && Effect!=EProphecyVDBEffect::ShockwaveExplosion))return false;
    UStaticMesh* Original=Bomb->GetStaticMesh();
    if(!Original || Original->GetPathName()!=TEXT("/Game/Fab/CC0_-_Bomb/cc0_bomb/StaticMeshes/cc0_bomb.cc0_bomb"))return false;
    double Length=0;for(const FVector& Segment:BombFuseSegments)Length+=Bomb->GetComponentTransform().TransformVector(Segment).Length();
    if((!bInstantExplosion && (Length<=0 || Length/FuseBurnSpeed>1.e6)) || 180./Framerate>1.e6)return false;
    TArray<TObjectPtr<UStaticMesh>> Meshes;
    for(int32 I=0;bSpawnFragments && I<20;++I)
    {
        const FString Path=FString::Printf(TEXT("/Game/_mygame/BombGenerated/SM_BombFragment_%02d.SM_BombFragment_%02d"),I,I);
        auto* Mesh=LoadObject<UStaticMesh>(nullptr,*Path);if(!Mesh)return false;Meshes.Add(Mesh);
    }
    // Load effect data at ignition, avoiding disk I/O during detonation.
    const TCHAR* VDB=Effect==EProphecyVDBEffect::Shockwave?TEXT("/Game/_mygame/animations/VDB/Shockwave.Shockwave"):TEXT("/Game/_mygame/animations/VDB/ShockwaveExplosion.ShockwaveExplosion");
    UObject* EffectAsset=LoadObject<UObject>(nullptr,VDB);
    if(!EffectAsset)return false;
    UMaterialInterface* FadeTemplate=nullptr;
    if(bSpawnFragments && FragmentFadeDuration>0)
    {
        FadeTemplate=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/_mygame/BombGenerated/MI_BombFragmentFade.MI_BombFragmentFade"));
        if(!FadeTemplate)return false;
    }
    auto* Controller=Existing;
    if(!Controller && bInstantExplosion)
    {Controller=NewObject<UProphecyBombComponent>(Bomb->GetOwner());Bomb->GetOwner()->AddInstanceComponent(Controller);}
    if(!Controller)Controller=PrepareStaticBomb(Bomb);if(!Controller)return false;
    Controller->Bomb=Bomb;Controller->Fragments=MoveTemp(Meshes);
    Controller->EffectAsset=EffectAsset;
    Controller->FragmentVelocity=FragmentVelocity;Controller->Intensity=Intensity;Controller->Radius=Radius;
    Controller->FalloffExponent=FalloffExponent;Controller->ExplosionVelocity=ExplosionVelocity;Controller->Effect=Effect;
    Controller->Scale=Scale;Controller->Framerate=Framerate;Controller->FadeStart=DensityFadeStart;
    Controller->TargetDensity=TargetDensity;Controller->FadeDuration=DensityFadeDuration;Controller->Rotation=Rotation;
    Controller->BurnTicks=bInstantExplosion?0:FMath::Max(uint64(1),ProphecyVDB::DurationTicks(Length/FuseBurnSpeed));
    Controller->DebrisTicks=FMath::Max(uint64(1),ProphecyVDB::DurationTicks(FragmentLifetime));Controller->LastFrame=GFrameCounter;
    Controller->Elapsed=0;Controller->bBurning=true;
    auto* Fade=Bomb->GetOwner()->FindComponentByClass<UProphecyBombFragmentFadeComponent>();
    if(FadeTemplate)
    {
        if(!Fade){Fade=NewObject<UProphecyBombFragmentFadeComponent>(Bomb->GetOwner());Bomb->GetOwner()->AddInstanceComponent(Fade);Fade->RegisterComponent();}
        Fade->FadeTicks=ProphecyVDB::DurationTicks(FragmentFadeDuration);Fade->Template=FadeTemplate;
    }
    else if(Fade)Fade->DestroyComponent();
    auto* VDBOptions=Bomb->GetOwner()->FindComponentByClass<UProphecyBombVDBOptimisedComponent>();
    if(bOptimised && !VDBOptions)
    {VDBOptions=NewObject<UProphecyBombVDBOptimisedComponent>(Bomb->GetOwner());Bomb->GetOwner()->AddInstanceComponent(VDBOptions);VDBOptions->RegisterComponent();}
    else if(!bOptimised && VDBOptions)VDBOptions->DestroyComponent();
    auto* Colors=Bomb->GetOwner()->FindComponentByClass<UProphecyBombVDBColorComponent>();
    if(TemperatureColor!=ProphecyVDB::DefaultTemperatureColor() || ScatteringColor!=FLinearColor::White)
    {
        if(!Colors){Colors=NewObject<UProphecyBombVDBColorComponent>(Bomb->GetOwner());Bomb->GetOwner()->AddInstanceComponent(Colors);Colors->RegisterComponent();}
        Colors->TemperatureColor=TemperatureColor;Colors->ScatteringColor=ScatteringColor;
    }
    else if(Colors)Colors->DestroyComponent();
    if(bInstantExplosion){Controller->Detonate();return true;}
    if(FuseCap>0.f)
    {
        auto* Cap=NewObject<UProphecyBombFuseCapComponent>(Bomb->GetOwner());Bomb->GetOwner()->AddInstanceComponent(Cap);
        Cap->DetonationTicks=FMath::Max(uint64(1),ProphecyVDB::DurationTicks(Length*(1.-FuseCap)/FuseBurnSpeed));
        Cap->RegisterComponent();
    }
    Controller->SetComponentTickEnabled(true);
    if(FuseSparks && !Controller->bFuseHidden)
    {
        FVector Position,Tangent;
        if(Controller->GetBurnTip(Position,Tangent))
        {
            const FRotator Orientation=FRotator::ZeroRotator;
            Controller->Sparks=UNiagaraFunctionLibrary::SpawnSystemAtLocation(Bomb,FuseSparks,Position,Orientation,FVector(1),true,true,ENCPoolMethod::None,false);
            if(Controller->Sparks)
            {
                Controller->Sparks->AttachToComponent(Bomb,FAttachmentTransformRules::KeepWorldTransform);
                Controller->Sparks->SetAbsolute(false,true,true);
                Controller->Sparks->AddTickPrerequisiteComponent(Controller);
            }
        }
    }
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "ProphecyJoltWorldSubsystem.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBombContract,"Prophecy.Bomb.FuseAndDetonation",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBombContract::RunTest(const FString&)
{
    struct FTestWorld
    {
        UWorld* W;
        FTestWorld()
        {
            auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
                .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).CreateFXSystem(false).SetTransactional(false);
            W=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(W);
        }
        ~FTestWorld(){W->DestroyWorld(false);GEngine->DestroyWorldContext(W);W->MarkAsGarbage();}
    } Fixture;
    auto* W=Fixture.W;auto* Physics=W->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldSettings Settings;Settings.GravityCmPerSecondSquared=FVector::ZeroVector;
    if(!TestTrue(TEXT("Initialize isolated Jolt fixture"),Physics->InitializeSimulation(Settings).IsSuccess()))return false;
    FProphecyJoltFixtureBodySettings Body;Body.PositionCm=FVector(100,0,100);
    FProphecyJoltBodyHandle Handle;
    if(!TestTrue(TEXT("Create recipient"),Physics->CreateSphere(10,Body,Handle).IsSuccess()))return false;
    auto* Actor=W->SpawnActor<AStaticMeshActor>();auto* Mesh=Actor->GetStaticMeshComponent();
    Mesh->SetMobility(EComponentMobility::Movable);Actor->SetActorLocation(FVector(0,0,100));
    Mesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Game/Fab/CC0_-_Bomb/cc0_bomb/StaticMeshes/cc0_bomb.cc0_bomb")));
    TestFalse(TEXT("Reject zero burn speed"),UProphecyBombLibrary::LightBombFuse(Mesh,0));
    auto* Prepared=PrepareStaticBomb(Mesh);
    if(!TestNotNull(TEXT("Prepared static controller"),Prepared))return false;
    TestFalse(TEXT("Preparation does not ignite"),Prepared->bBurning);
    TestFalse(TEXT("Static fuse has no animation tick"),Prepared->Visual->IsComponentTickEnabled());
    TestEqual(TEXT("Cosmetic fuse has no collision"),Prepared->Visual->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
    FVector Tip,Tangent;TestTrue(TEXT("Initial tip available"),Prepared->GetBurnTip(Tip,Tangent));
    TestTrue(TEXT("Initial tip matches original curved geometry"),Tip.Equals(Mesh->GetComponentTransform().TransformPosition(BombFuseCenters[28]),.001));
    if(!TestTrue(TEXT("Ignite prepared original"),UProphecyBombLibrary::LightBombFuse(Mesh,10,700)))return false;
    TestFalse(TEXT("Cannot ignite twice"),UProphecyBombLibrary::LightBombFuse(Mesh));
    auto* Fuse=Actor->FindComponentByClass<UProphecyBombComponent>();
    TestTrue(TEXT("Ignition reuses static visual"),Fuse==Prepared);
    TestNull(TEXT("Empty Niagara input creates no emitter"),Fuse->Sparks.Get());
    TestEqual(TEXT("Curved length timing"),Fuse->BurnTicks,uint64(60));
    Fuse->LastFrame=GFrameCounter-1;Fuse->TickComponent(1.f/60,LEVELTICK_All,nullptr);
    TestTrue(TEXT("Burn scalar advances"),Fuse->Material->K2_GetScalarParameterValue(TEXT("FuseRemaining"))<1);
    TestFalse(TEXT("Original remains before completion"),Actor->IsActorBeingDestroyed());
    // A replacement after ignition must propagate, not the baked or ignition-time material.
    auto* ShellOverride=UMaterialInstanceDynamic::Create(Mesh->GetMaterial(0),Actor);
    Mesh->SetMaterial(0,ShellOverride);
    Fuse->LastFrame=GFrameCounter-1;Fuse->TickComponent(1.f/60,LEVELTICK_All,nullptr);
    TestTrue(TEXT("Burning static body inherits current material"),Fuse->ShellVisual && Fuse->ShellVisual->GetMaterial(0)==ShellOverride);
    Fuse->Elapsed=Fuse->BurnTicks-1;Fuse->LastFrame=GFrameCounter-1;Fuse->TickComponent(1.f/60,LEVELTICK_All,nullptr);
    TestTrue(TEXT("Bomb consumed exactly at endpoint"),Actor->IsActorBeingDestroyed());
    FProphecyJoltBodyState State;Physics->ReadBody(Handle,State);
    TestTrue(TEXT("Fuse completion applies actual native physical blast"),State.CenterOfMassVelocityCmPerSecond.X>0);
    int32 Pieces=0,Effects=0;UProphecyBombComponent* Cleanup=nullptr;
    const FVector Centre(-1.0239047,0,98.7846542);
    for(TActorIterator<AActor> It(W);It;++It)
    {
        auto* A=*It;if(A->IsActorBeingDestroyed())continue;
        if(A->GetClass()->GetName()==TEXT("ZibraVDBActor"))++Effects;
        auto* C=A->FindComponentByClass<UProphecyBombComponent>();if(C && C->bDebris)Cleanup=C;
        auto* S=Cast<AStaticMeshActor>(A);
        if(!S || !S->GetStaticMeshComponent()->GetStaticMesh()->GetName().StartsWith(TEXT("SM_BombFragment_")))continue;
        ++Pieces;auto* P=S->GetStaticMeshComponent();
        TestTrue(TEXT("Fragment inherits current bomb material instance"),P->GetMaterial(0)==ShellOverride);
        TestTrue(TEXT("Fragment simulating"),P->IsSimulatingPhysics());
        TestTrue(TEXT("Radial fragment velocity"),P->GetPhysicsLinearVelocity().Equals((P->GetCenterOfMass()-Centre).GetSafeNormal()*700,.05));
    }
    TestEqual(TEXT("Twenty original shell fragments"),Pieces,20);TestEqual(TEXT("One VDB effect"),Effects,1);
    if(TestNotNull(TEXT("Bounded debris cleanup"),Cleanup))
    {
        auto* Fade=Cleanup->GetOwner()->FindComponentByClass<UProphecyBombFragmentFadeComponent>();
        if(TestNotNull(TEXT("Shared fragment fade controller"),Fade))
        {
            TestFalse(TEXT("No extra fragment fade tick"),Fade->IsComponentTickEnabled());
            TestEqual(TEXT("Default one-second fade"),Fade->FadeTicks,uint64(60));
            TestEqual(TEXT("Real translucent material"),Fade->Material->GetBlendMode(),BLEND_Translucent);
            Cleanup->Elapsed=Cleanup->DebrisTicks-31;Cleanup->LastFrame=GFrameCounter-1;Cleanup->TickComponent(1.f/60,LEVELTICK_All,nullptr);
            TestEqual(TEXT("Halfway opacity"),Fade->Material->K2_GetScalarParameterValue(TEXT("FragmentOpacity")),.5f);
            for(AActor* A:Cleanup->Debris)
            {
                TestFalse(TEXT("Fading debris remains physical until lifetime endpoint"),A->IsActorBeingDestroyed());
                TestTrue(TEXT("All fragments share one fade material"),CastChecked<AStaticMeshActor>(A)->GetStaticMeshComponent()->GetMaterial(0)==Fade->Material);
            }
        }
        Cleanup->Elapsed=Cleanup->DebrisTicks-1;Cleanup->LastFrame=GFrameCounter-1;Cleanup->TickComponent(1.f/60,LEVELTICK_All,nullptr);
        if(Fade)TestEqual(TEXT("Exact zero opacity endpoint"),Fade->Material->K2_GetScalarParameterValue(TEXT("FragmentOpacity")),0.f);
        for(AActor* A:Cleanup->Debris)TestTrue(TEXT("Fragment expires"),A->IsActorBeingDestroyed());
    }
    auto* HiddenActor=W->SpawnActor<AStaticMeshActor>();auto* HiddenMesh=HiddenActor->GetStaticMeshComponent();
    HiddenMesh->SetMobility(EComponentMobility::Movable);HiddenMesh->SetStaticMesh(Mesh->GetStaticMesh());
    TestTrue(TEXT("Hide unlit fuse"),UProphecyBombLibrary::HideBombFuse(HiddenMesh));
    auto* Hidden=HiddenActor->FindComponentByClass<UProphecyBombComponent>();
    if(!TestNotNull(TEXT("Hidden controller"),Hidden))return false;
    TestFalse(TEXT("Hidden unlit controller does not tick"),Hidden->IsComponentTickEnabled());
    TestFalse(TEXT("Hidden fuse dynamics does not tick"),Hidden->Visual->IsComponentTickEnabled());
    TestTrue(TEXT("Hidden fuse can still start a timer"),UProphecyBombLibrary::LightBombFuse(HiddenMesh));
    Hidden->LastFrame=GFrameCounter-1;Hidden->TickComponent(1.f/60,LEVELTICK_All,nullptr);
    TestEqual(TEXT("Burn timer does not unhide fuse"),Hidden->Material->K2_GetScalarParameterValue(TEXT("FuseRemaining")),-1.f);
    TestTrue(TEXT("Instant detonation overrides active timer and ignores zero burn speed"),
        UProphecyBombLibrary::LightBombFuse(HiddenMesh,0,700,1000,500,2,0,EProphecyVDBEffect::ShockwaveExplosion,1,30,3,0,1,FRotator::ZeroRotator,8,nullptr,true));
    TestTrue(TEXT("Instant destroys bomb synchronously"),HiddenActor->IsActorBeingDestroyed());
    const auto CountLive=[&](bool bEffects)
    {
        int32 Count=0;
        for(TActorIterator<AActor> It(W);It;++It)
        {
            if(It->IsActorBeingDestroyed())continue;
            if(bEffects){if(It->GetClass()->GetName()==TEXT("ZibraVDBActor"))++Count;}
            else if(auto* S=Cast<AStaticMeshActor>(*It))
                if(S->GetStaticMeshComponent()->GetStaticMesh() && S->GetStaticMeshComponent()->GetStaticMesh()->GetName().StartsWith(TEXT("SM_BombFragment_")))++Count;
        }
        return Count;
    };
    for(bool bInstant:{false,true})
    {
        auto* NoDebrisActor=W->SpawnActor<AStaticMeshActor>();auto* NoDebrisMesh=NoDebrisActor->GetStaticMeshComponent();
        NoDebrisMesh->SetMobility(EComponentMobility::Movable);NoDebrisMesh->SetStaticMesh(Mesh->GetStaticMesh());
        const int32 PreviousPieces=CountLive(false),PreviousEffects=CountLive(true);
        Physics->SetBodyVelocity(Handle,FVector::ZeroVector,FVector::ZeroVector,true);
        TestTrue(TEXT("Start without fragments"),UProphecyBombLibrary::LightBombFuse(NoDebrisMesh,10,700,1000,500,2,0,EProphecyVDBEffect::ShockwaveExplosion,1,30,3,0,1,FRotator::ZeroRotator,8,nullptr,bInstant,false));
        if(!bInstant)
        {
            auto* NoDebris=NoDebrisActor->FindComponentByClass<UProphecyBombComponent>();
            TestTrue(TEXT("Disabled fragments are not preloaded"),NoDebris->Fragments.IsEmpty());
            NoDebris->Elapsed=NoDebris->BurnTicks-1;NoDebris->LastFrame=GFrameCounter-1;NoDebris->TickComponent(1.f/60,LEVELTICK_All,nullptr);
        }
        TestTrue(TEXT("No-fragment explosion consumes bomb"),NoDebrisActor->IsActorBeingDestroyed());
        TestEqual(TEXT("No fragments spawned"),CountLive(false),PreviousPieces);
        TestEqual(TEXT("VDB still spawned without fragments"),CountLive(true),PreviousEffects+1);
        Physics->ReadBody(Handle,State);TestTrue(TEXT("Physical force still applies without fragments"),State.CenterOfMassVelocityCmPerSecond.X>0);
    }
    for(float CapValue:{0.f,.25f,.5f,1.f})
    {
        auto* CapActor=W->SpawnActor<AStaticMeshActor>();auto* CapMesh=CapActor->GetStaticMeshComponent();
        CapMesh->SetMobility(EComponentMobility::Movable);CapMesh->SetStaticMesh(Mesh->GetStaticMesh());
        const int32 PreviousEffects=CountLive(true);
        Physics->SetBodyVelocity(Handle,FVector::ZeroVector,FVector::ZeroVector,true);
        TestTrue(TEXT("Start capped fuse"),UProphecyBombLibrary::LightBombFuse(CapMesh,CapValue==1.f?0.f:10.f,700,1000,500,2,0,
            EProphecyVDBEffect::ShockwaveExplosion,1,30,3,0,1,FRotator::ZeroRotator,8,nullptr,false,false,1,CapValue));
        if(CapValue<1.f)
        {
            auto* Controller=CapActor->FindComponentByClass<UProphecyBombComponent>();
            if(!TestNotNull(TEXT("Capped burn controller"),Controller))return false;
            TestEqual(TEXT("Cap preserves full-length burn speed"),Controller->BurnTicks,uint64(60));
            const uint64 Deadline=uint64(60*(1-CapValue));
            auto* Cap=CapActor->FindComponentByClass<UProphecyBombFuseCapComponent>();
            if(CapValue>0)
            {
                if(!TestNotNull(TEXT("Optional cap deadline"),Cap))return false;
                TestEqual(TEXT("Cap deadline follows remaining fraction"),Cap->DetonationTicks,Deadline);
                TestFalse(TEXT("Cap has no separate tick"),Cap->IsComponentTickEnabled());
            }
            else TestNull(TEXT("Default cap needs no extra component"),Cap);
            Controller->Elapsed=Deadline-2;Controller->LastFrame=GFrameCounter-1;Controller->TickComponent(1.f/60,LEVELTICK_All,nullptr);
            TestFalse(TEXT("Capped fuse survives until deadline"),CapActor->IsActorBeingDestroyed());
            TestEqual(TEXT("Visible burn is not sped up by cap"),Controller->Material->K2_GetScalarParameterValue(TEXT("FuseRemaining")),1.f-float(double(Deadline-1)/60)*.99f);
            TestNull(TEXT("Cap does not create optional sparks"),Controller->Sparks.Get());
            Controller->LastFrame=GFrameCounter-1;Controller->TickComponent(1.f/60,LEVELTICK_All,nullptr);
        }
        TestTrue(TEXT("Cap consumes bomb at deadline (1 is synchronous)"),CapActor->IsActorBeingDestroyed());
        TestEqual(TEXT("Cap triggers exactly one VDB"),CountLive(true),PreviousEffects+1);
        Physics->ReadBody(Handle,State);TestTrue(TEXT("Cap also applies physical blast"),State.CenterOfMassVelocityCmPerSecond.X>0);
    }
    // Verify travelling force remains delayed and uses the original propagation contract.
    Physics->SetBodyVelocity(Handle,FVector::ZeroVector,FVector::ZeroVector,true);
    TestEqual(TEXT("Travelling blast scheduled"),UProphecyExplosionLibrary::StartExplosion(W,FVector(0,0,100),1000,500,2,100),1);
    Physics->ReadBody(Handle,State);TestTrue(TEXT("No early travelling impact"),State.CenterOfMassVelocityCmPerSecond.IsNearlyZero());
    for(int I=0;I<61;++I)Physics->Step(1.f/60,1);
    Physics->ReadBody(Handle,State);TestTrue(TEXT("Impact after wave arrival"),State.CenterOfMassVelocityCmPerSecond.X>0);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyStaticFuse,"Prophecy.Bomb.StaticFuse",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyStaticFuse::RunTest(const FString&)
{
    auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).CreateFXSystem(false).SetTransactional(false);
    auto* W=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(W);
    auto* A=W->SpawnActor<AStaticMeshActor>();auto* M=A->GetStaticMeshComponent();
    M->SetMobility(EComponentMobility::Movable);
    M->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Game/Fab/CC0_-_Bomb/cc0_bomb/StaticMeshes/cc0_bomb.cc0_bomb")));
    auto* C=PrepareStaticBomb(M);
    if(!C){AddError(TEXT("Static fuse assets missing"));W->DestroyWorld(false);GEngine->DestroyWorldContext(W);return false;}
    TestFalse(TEXT("Fuse has no recurring animation work"),C->Visual->IsComponentTickEnabled());
    TestFalse(TEXT("Fuse has no physics"),C->Visual->IsSimulatingPhysics());
    TestEqual(TEXT("Fuse is original-shape static mesh"),C->Visual->GetStaticMesh()->GetFName(),FName(TEXT("SM_BombFuse")));
    TestTrue(TEXT("Shell retains bomb material"),C->ShellVisual->GetMaterial(0)==M->GetMaterial(0));
    // No explosions or particle simulations: exercise the actual attachment update
    // with a non-activating Niagara component, suitable for isolated -nullrhi.
    auto* FX=NewObject<UNiagaraComponent>(A);A->AddInstanceComponent(FX);
    FX->SetAutoActivate(false);FX->SetupAttachment(M);FX->SetAbsolute(false,true,true);FX->RegisterComponent();C->Sparks=FX;
    C->BurnTicks=1200;C->bBurning=true;
    for(int32 I=0;I<180;++I)
    {
        A->SetActorLocationAndRotation(FVector(I*.3,2,100),FRotator(I*3,I*5,I*7));
        C->LastFrame=GFrameCounter-1;C->TickComponent(1.f/60,LEVELTICK_All,nullptr);
        FVector Tip,Tangent;TestTrue(TEXT("Static burn tip"),C->GetBurnTip(Tip,Tangent));
        TestTrue(TEXT("Emitter follows cut"),FX->GetComponentLocation().Equals(Tip,.0001));
        TestTrue(TEXT("Emitter always world upright"),FX->GetComponentQuat().Equals(FQuat::Identity,.0001));
        TestTrue(TEXT("Fuse keeps original local shape"),C->Visual->GetRelativeTransform().Equals(FTransform::Identity));
        TestFalse(TEXT("No fuse animation tick while burning"),C->Visual->IsComponentTickEnabled());
    }
    TestTrue(TEXT("Fuse clips progressively"),C->Material->K2_GetScalarParameterValue(TEXT("FuseRemaining"))<1.f);
    auto* Override=UMaterialInstanceDynamic::Create(M->GetMaterial(0),A);M->SetMaterial(0,Override);
    C->LastFrame=GFrameCounter-1;C->TickComponent(1.f/60,LEVELTICK_All,nullptr);
    TestTrue(TEXT("Shell inherits live bomb material"),C->ShellVisual->GetMaterial(0)==Override);
    TestTrue(TEXT("Permanent hide"),UProphecyBombLibrary::HideBombFuse(M));
    TestFalse(TEXT("Hidden static fuse invisible"),C->Visual->IsVisible());TestNull(TEXT("Hide removes sparks"),C->Sparks.Get());
    C->LastFrame=GFrameCounter-1;C->TickComponent(1.f/60,LEVELTICK_All,nullptr);
    TestEqual(TEXT("Burn cannot reveal hidden fuse"),C->Material->K2_GetScalarParameterValue(TEXT("FuseRemaining")),-1.f);
    AddInfo(TEXT("180 moving/rotating-bomb samples: static fuse, upright emitter, progressive clipping, material propagation and permanent hide."));
    W->DestroyWorld(false);GEngine->DestroyWorldContext(W);W->MarkAsGarbage();return !HasAnyErrors();
}
#endif
