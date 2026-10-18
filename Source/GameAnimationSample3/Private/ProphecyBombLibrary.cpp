#include "ProphecyBombLibrary.h"
#include "ProphecyBombComponent.h"
#include "ProphecyBombFragmentFadeComponent.h"
#include "ProphecyBombGeometry.h"
#include "ProphecyBombFuseCurve.h"
#include "ProphecyHolsterStrapComponent.h"
#include "ProphecyVDBTiming.h"
#include "ProphecyExplosionLibrary.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "Engine/SkeletalMesh.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/Material.h"
#include "PhysicsEngine/BodyInstance.h"

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
    if(!IsValid(Visual) || FuseReferenceTransforms.Num()!=7)return false;
    const double Length=BombFuseArc[UE_ARRAY_COUNT(BombFuseArc)-1];
    const double Distance=Length*(1.-FMath::Clamp(double(Elapsed)/BurnTicks,0.,1.));
    int32 Ring=0;while(Ring+2<UE_ARRAY_COUNT(BombFuseArc) && BombFuseArc[Ring+1]<Distance)++Ring;
    // Only the two rings straddling the cut are evaluated, not the entire skin.
    const auto SkinCenter=[&](int32 I)
    {
        const double U=BombFuseArc[I]/Length*5.;const int32 J=FMath::Min(4,int32(U));const double T=U-J;
        const FVector P=BombFuseCenters[I];
        const FVector A=Visual->GetBoneTransform(J).TransformPosition(FuseReferenceTransforms[J].InverseTransformPosition(P));
        const FVector B=Visual->GetBoneTransform(J+1).TransformPosition(FuseReferenceTransforms[J+1].InverseTransformPosition(P));
        return FMath::Lerp(A,B,T);
    };
    const FVector A=SkinCenter(Ring),B=SkinCenter(Ring+1);
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
    if(Visual->GetMaterial(0)!=Bomb->GetMaterial(0))Visual->SetMaterial(0,Bomb->GetMaterial(0));
    if(!bBurning){Elapsed=0;return;}
    if(Elapsed>=BurnTicks){Detonate();return;}
    if(!bFuseHidden)Material->SetScalarParameterValue(TEXT("FuseRemaining"),1.f-float(double(Elapsed)/BurnTicks)*.99f);
    if(IsValid(Sparks))
    {
        FVector Position,Tangent;
        if(GetBurnTip(Position,Tangent))Sparks->SetWorldLocationAndRotation(Position,Tangent.ToOrientationQuat()*SparkRotationOffset.Quaternion());
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
    UProphecyVDBLibrary::SpawnVDBEffect(this,Effect,Centre,Scale,Framerate,FadeStart,TargetDensity,FadeDuration,Rotation);
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
static UProphecyBombComponent* PrepareFlexibleBomb(UStaticMeshComponent* Bomb)
{
    if(!IsInGameThread() || !IsValid(Bomb) || !Bomb->GetWorld() || !Bomb->GetWorld()->IsGameWorld() || !Bomb->GetOwner())return nullptr;
    UStaticMesh* Original=Bomb->GetStaticMesh();
    if(!Original || Original->GetPathName()!=TEXT("/Game/Fab/CC0_-_Bomb/cc0_bomb/StaticMeshes/cc0_bomb.cc0_bomb"))return nullptr;
    if(auto* Existing=Bomb->GetOwner()->FindComponentByClass<UProphecyBombComponent>())return Existing->Bomb==Bomb?Existing:nullptr;
    auto* Mesh=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/BombGenerated/SK_BombFuse.SK_BombFuse"));
    auto* BurnMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/_mygame/BombGenerated/MI_BombBurn.MI_BombBurn"));
    if(!Mesh || !BurnMaterial || Mesh->GetRefSkeleton().GetNum()!=7)return nullptr;
    auto* Controller=NewObject<UProphecyBombComponent>(Bomb->GetOwner());Bomb->GetOwner()->AddInstanceComponent(Controller);Controller->Bomb=Bomb;
    const auto& Ref=Mesh->GetRefSkeleton();Controller->FuseReferenceTransforms=Ref.GetRefBonePose();
    for(int32 I=1;I<7;++I)Controller->FuseReferenceTransforms[I]*=Controller->FuseReferenceTransforms[Ref.GetParentIndex(I)];
    auto* Visual=NewObject<UProphecyHolsterStrapComponent>(Bomb->GetOwner());Bomb->GetOwner()->AddInstanceComponent(Visual);Controller->Visual=Visual;
    Visual->SetSkeletalMesh(Mesh);Visual->SetAnimInstanceClass(UProphecyHolsterStrapAnimInstance::StaticClass());
    Visual->SetMobility(EComponentMobility::Movable);Visual->SetupAttachment(Bomb);Visual->SetBoundsScale(2.f);
    Controller->Material=UMaterialInstanceDynamic::Create(BurnMaterial,Controller);
    Controller->Material->SetScalarParameterValue(TEXT("FuseRemaining"),1.f);
    Visual->SetMaterial(0,Bomb->GetMaterial(0));Visual->SetMaterial(1,Controller->Material);
    Visual->RegisterComponent();Visual->SetStrapEnabled(true);Visual->AddTickPrerequisiteComponent(Bomb);
    Controller->AddTickPrerequisiteComponent(Visual);Controller->LastFrame=GFrameCounter;
    Bomb->SetVisibility(false,false);Controller->RegisterComponent();return Controller;
}
bool UProphecyBombLibrary::SetBombFuseStiffness(UStaticMeshComponent* Bomb,float Stiffness)
{
    if(!FMath::IsFinite(Stiffness) || Stiffness<0)return false;
    auto* Controller=PrepareFlexibleBomb(Bomb);if(!Controller || !Controller->Visual || Controller->bFuseHidden)return false;
    Controller->Visual->Stiffness=FMath::Min(Stiffness,10000.f);return true;
}
bool UProphecyBombLibrary::HideBombFuse(UStaticMeshComponent* Bomb)
{
    auto* Controller=PrepareFlexibleBomb(Bomb);if(!Controller || !Controller->Visual)return false;
    Controller->bFuseHidden=true;Controller->Material->SetScalarParameterValue(TEXT("FuseRemaining"),-1.f);
    Controller->Visual->SetStrapEnabled(false);
    if(IsValid(Controller->Sparks)){Controller->Sparks->DestroyComponent();Controller->Sparks=nullptr;}
    if(!Controller->bBurning)Controller->SetComponentTickEnabled(false);
    return true;
}
bool UProphecyBombLibrary::LightBombFuse(UStaticMeshComponent* Bomb,float FuseBurnSpeed,float FragmentVelocity,
    float Intensity,float Radius,float FalloffExponent,float ExplosionVelocity,EProphecyVDBEffect Effect,float Scale,
    float Framerate,float DensityFadeStart,float TargetDensity,float DensityFadeDuration,FRotator Rotation,float FragmentLifetime,
    UNiagaraSystem* FuseSparks,FRotator SparkRotationOffset,bool bInstantExplosion,bool bSpawnFragments,float FragmentFadeDuration)
{
    if(!IsInGameThread() || !IsValid(Bomb) || !Bomb->GetWorld() || !Bomb->GetWorld()->IsGameWorld() || !Bomb->GetOwner()
       || Rotation.ContainsNaN() || SparkRotationOffset.ContainsNaN())return false;
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
    if(!Controller)Controller=PrepareFlexibleBomb(Bomb);if(!Controller)return false;
    Controller->Bomb=Bomb;Controller->Fragments=MoveTemp(Meshes);
    Controller->EffectAsset=EffectAsset;
    Controller->FragmentVelocity=FragmentVelocity;Controller->Intensity=Intensity;Controller->Radius=Radius;
    Controller->FalloffExponent=FalloffExponent;Controller->ExplosionVelocity=ExplosionVelocity;Controller->Effect=Effect;
    Controller->Scale=Scale;Controller->Framerate=Framerate;Controller->FadeStart=DensityFadeStart;
    Controller->TargetDensity=TargetDensity;Controller->FadeDuration=DensityFadeDuration;Controller->Rotation=Rotation;
    Controller->BurnTicks=bInstantExplosion?0:FMath::Max(uint64(1),ProphecyVDB::DurationTicks(Length/FuseBurnSpeed));
    Controller->DebrisTicks=FMath::Max(uint64(1),ProphecyVDB::DurationTicks(FragmentLifetime));Controller->LastFrame=GFrameCounter;
    Controller->Elapsed=0;Controller->bBurning=true;Controller->SparkRotationOffset=SparkRotationOffset;
    auto* Fade=Bomb->GetOwner()->FindComponentByClass<UProphecyBombFragmentFadeComponent>();
    if(FadeTemplate)
    {
        if(!Fade){Fade=NewObject<UProphecyBombFragmentFadeComponent>(Bomb->GetOwner());Bomb->GetOwner()->AddInstanceComponent(Fade);Fade->RegisterComponent();}
        Fade->FadeTicks=ProphecyVDB::DurationTicks(FragmentFadeDuration);Fade->Template=FadeTemplate;
    }
    else if(Fade)Fade->DestroyComponent();
    if(bInstantExplosion){Controller->Detonate();return true;}
    Controller->SetComponentTickEnabled(true);
    if(FuseSparks && !Controller->bFuseHidden)
    {
        FVector Position,Tangent;
        if(Controller->GetBurnTip(Position,Tangent))
        {
            const FRotator Orientation=(Tangent.ToOrientationQuat()*SparkRotationOffset.Quaternion()).Rotator();
            Controller->Sparks=UNiagaraFunctionLibrary::SpawnSystemAtLocation(Bomb,FuseSparks,Position,Orientation,FVector(1),true,true,ENCPoolMethod::None,false);
            if(Controller->Sparks)Controller->Sparks->AddTickPrerequisiteComponent(Controller);
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
    TestFalse(TEXT("Reject negative stiffness"),UProphecyBombLibrary::SetBombFuseStiffness(Mesh,-1));
    TestTrue(TEXT("Flexible fuse before ignition"),UProphecyBombLibrary::SetBombFuseStiffness(Mesh,5));
    auto* Prepared=Actor->FindComponentByClass<UProphecyBombComponent>();
    if(!TestNotNull(TEXT("Prepared flexible controller"),Prepared))return false;
    TestFalse(TEXT("Stiffness does not ignite"),Prepared->bBurning);
    TestEqual(TEXT("Spring applied"),Prepared->Visual->Stiffness,5.f);
    TestEqual(TEXT("Cosmetic fuse has no collision"),Prepared->Visual->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
    FVector Tip,Tangent;TestTrue(TEXT("Initial tip available"),Prepared->GetBurnTip(Tip,Tangent));
    TestTrue(TEXT("Initial tip matches original curved geometry"),Tip.Equals(Mesh->GetComponentTransform().TransformPosition(BombFuseCenters[28]),.001));
    if(!TestTrue(TEXT("Ignite prepared original"),UProphecyBombLibrary::LightBombFuse(Mesh,10,700)))return false;
    TestFalse(TEXT("Cannot ignite twice"),UProphecyBombLibrary::LightBombFuse(Mesh));
    auto* Fuse=Actor->FindComponentByClass<UProphecyBombComponent>();
    TestTrue(TEXT("Ignition reuses flexible pose"),Fuse==Prepared);
    TestNull(TEXT("Empty Niagara input creates no emitter"),Fuse->Sparks.Get());
    TestTrue(TEXT("Stiffness adjustable while burning"),UProphecyBombLibrary::SetBombFuseStiffness(Mesh,40));
    TestEqual(TEXT("Live spring applied"),Fuse->Visual->Stiffness,40.f);
    TestEqual(TEXT("Curved length timing"),Fuse->BurnTicks,uint64(60));
    Fuse->LastFrame=GFrameCounter-1;Fuse->TickComponent(1.f/60,LEVELTICK_All,nullptr);
    TestTrue(TEXT("Burn scalar advances"),Fuse->Material->K2_GetScalarParameterValue(TEXT("FuseRemaining"))<1);
    TestFalse(TEXT("Original remains before completion"),Actor->IsActorBeingDestroyed());
    // A replacement after ignition must propagate, not the baked or ignition-time material.
    auto* ShellOverride=UMaterialInstanceDynamic::Create(Mesh->GetMaterial(0),Actor);
    Mesh->SetMaterial(0,ShellOverride);
    Fuse->LastFrame=GFrameCounter-1;Fuse->TickComponent(1.f/60,LEVELTICK_All,nullptr);
    TestTrue(TEXT("Burning body inherits current material"),Fuse->Visual->GetMaterial(0)==ShellOverride);
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
    TestFalse(TEXT("Stiffness cannot reveal permanently hidden fuse"),UProphecyBombLibrary::SetBombFuseStiffness(HiddenMesh,20));
    TestTrue(TEXT("Hidden fuse can still start a timer"),UProphecyBombLibrary::LightBombFuse(HiddenMesh));
    Hidden->LastFrame=GFrameCounter-1;Hidden->TickComponent(1.f/60,LEVELTICK_All,nullptr);
    TestEqual(TEXT("Burn timer does not unhide fuse"),Hidden->Material->K2_GetScalarParameterValue(TEXT("FuseRemaining")),-1.f);
    TestTrue(TEXT("Instant detonation overrides active timer and ignores zero burn speed"),
        UProphecyBombLibrary::LightBombFuse(HiddenMesh,0,700,1000,500,2,0,EProphecyVDBEffect::ShockwaveExplosion,1,30,3,0,1,FRotator::ZeroRotator,8,nullptr,FRotator::ZeroRotator,true));
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
        TestTrue(TEXT("Start without fragments"),UProphecyBombLibrary::LightBombFuse(NoDebrisMesh,10,700,1000,500,2,0,EProphecyVDBEffect::ShockwaveExplosion,1,30,3,0,1,FRotator::ZeroRotator,8,nullptr,FRotator::ZeroRotator,bInstant,false));
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
    // Verify travelling force remains delayed and uses the original propagation contract.
    Physics->SetBodyVelocity(Handle,FVector::ZeroVector,FVector::ZeroVector,true);
    TestEqual(TEXT("Travelling blast scheduled"),UProphecyExplosionLibrary::StartExplosion(W,FVector(0,0,100),1000,500,2,100),1);
    Physics->ReadBody(Handle,State);TestTrue(TEXT("No early travelling impact"),State.CenterOfMassVelocityCmPerSecond.IsNearlyZero());
    for(int I=0;I<61;++I)Physics->Step(1.f/60,1);
    Physics->ReadBody(Handle,State);TestTrue(TEXT("Impact after wave arrival"),State.CenterOfMassVelocityCmPerSecond.X>0);
    return !HasAnyErrors();
}
#endif
