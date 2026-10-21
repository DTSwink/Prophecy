#include "ProphecyVDBOptimisedComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/TextureRenderTargetVolume.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/UnrealType.h"

UProphecyVDBOptimisedComponent::UProphecyVDBOptimisedComponent()
{
    PrimaryComponentTick.bCanEverTick=true;
    PrimaryComponentTick.bStartWithTickEnabled=false;
    PrimaryComponentTick.TickGroup=TG_PostUpdateWork;
}

bool UProphecyVDBOptimisedComponent::Initialize(UActorComponent* InPlayback,UActorComponent* InMaterial,UActorComponent* Clock,int32 Frames)
{
    Playback=InPlayback;Material=InMaterial;FrameCount=Frames;
    SourceMesh=GetOwner()->FindComponentByClass<UStaticMeshComponent>();
    auto* Template=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/_mygame/animations/VDB/M_ProphecyVDBOptimisedTail.M_ProphecyVDBOptimisedTail"));
    if(!Playback || !Material || !SourceMesh || !Template || !Clock || Frames<=0)return false;
    FrameProperty=FindFProperty<FFloatProperty>(Playback->GetClass(),TEXT("CurrentFrame"));
    DensityProperty=FindFProperty<FFloatProperty>(Material->GetClass(),TEXT("DensityScale"));
    VisibleProperty=FindFProperty<FBoolProperty>(Playback->GetClass(),TEXT("Visible"));
    auto* ProjectedShadows=FindFProperty<FBoolProperty>(Material->GetClass(),TEXT("bEnableProjectedShadows"));
    if(!FrameProperty || !DensityProperty || !VisibleProperty || !ProjectedShadows)return false;
    // Allocate the small renderer/MID up front. GPU volume textures are reused, not copied.
    CachedMaterial=UMaterialInstanceDynamic::Create(Template,this);
    CachedMesh=NewObject<UStaticMeshComponent>(GetOwner(),TEXT("OptimisedVDBTail"));
    GetOwner()->AddInstanceComponent(CachedMesh);
    CachedMesh->SetMobility(EComponentMobility::Movable);
    CachedMesh->SetupAttachment(GetOwner()->GetRootComponent());
    CachedMesh->SetStaticMesh(SourceMesh->GetStaticMesh());
    CachedMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    CachedMesh->SetGenerateOverlapEvents(false);
    CachedMesh->SetCanEverAffectNavigation(false);
    CachedMesh->SetCastShadow(false);
    CachedMesh->SetVisibility(false);
    CachedMesh->SetMaterial(0,CachedMaterial);
    CachedMesh->RegisterComponent();
    ProjectedShadows->SetPropertyValue_InContainer(Material,false);
    AddTickPrerequisiteComponent(Clock);
    AddTickPrerequisiteComponent(Material);
    AddTickPrerequisiteComponent(Playback);
    AddTickPrerequisiteActor(GetOwner());
    LastGameFrame=GFrameCounter;
    SetComponentTickEnabled(true);
    return true;
}

bool UProphecyVDBOptimisedComponent::CapturePreparedVolume()
{
    auto* SourceMaterial=Cast<UMaterialInstanceDynamic>(SourceMesh->GetMaterial(0));
    if(!SourceMaterial || !SourceMesh->GetStaticMesh())return false;
    // Do not hand off a volume whose sparse resources have not been allocated/rendered.
    for(const TCHAR* Name:{TEXT("SparseBlocksRGB"),TEXT("SparseBlocksDensity"),TEXT("MaxDensityPerBlockTexture"),TEXT("BlockIndexBuffer"),TEXT("WorldToBoxTransform")})
    {
        UTexture* Texture=nullptr;
        if(!SourceMaterial->GetTextureParameterValue(FMaterialParameterInfo(Name),Texture) || !Texture || !Texture->GetResource())return false;
    }
    CachedMaterial->CopyParameterOverrides(SourceMaterial);
    CachedMaterial->SetScalarParameterValue(TEXT("ProphecyCachedDensityRatio"),1.f);
    CachedMesh->SetWorldTransform(SourceMesh->GetComponentTransform());
    CachedMesh->SetTranslucentSortPriority(SourceMesh->TranslucencySortPriority);
    CachedMesh->SetTranslucencySortDistanceOffset(SourceMesh->TranslucencySortDistanceOffset);
    VisibleProperty->SetPropertyValue_InContainer(Playback,false);
    // Zibra's actor tick publishes playback visibility to its render proxy. Publish
    // once now, then retire plugin ticking without waiting for another game frame.
    bActorTickWasEnabled=GetOwner()->IsActorTickEnabled();
    GetOwner()->Tick(0.f);
    GetOwner()->SetActorTickEnabled(false);
    for(UActorComponent* Component:GetOwner()->GetComponents())
    {
        if(Component && Component->IsComponentTickEnabled() && Component->GetClass()->GetName().StartsWith(TEXT("ZibraVDB")))
        {SuspendedComponents.Add(Component);Component->SetComponentTickEnabled(false);}
    }
    SourceMesh->SetVisibility(false);
    CachedMesh->SetVisibility(true);
    bCached=true;
    return true;
}

void UProphecyVDBOptimisedComponent::RestoreLiveRenderer()
{
    CachedMesh->SetVisibility(false);
    VisibleProperty->SetPropertyValue_InContainer(Playback,true);
    for(UActorComponent* Component:SuspendedComponents)if(IsValid(Component))Component->SetComponentTickEnabled(true);
    SuspendedComponents.Reset();
    GetOwner()->SetActorTickEnabled(bActorTickWasEnabled);
    GetOwner()->Tick(0.f);
    bCached=false;Phase=0;
}

void UProphecyVDBOptimisedComponent::TickComponent(float DeltaSeconds,ELevelTick TickType,FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaSeconds,TickType,TickFunction);
    if(TickType!=LEVELTICK_All || DeltaSeconds<=0 || !GetWorld() || GetWorld()->IsPaused() || LastGameFrame==GFrameCounter)return;
    LastGameFrame=GFrameCounter;
    if(!IsValid(Playback) || !IsValid(Material) || !IsValid(SourceMesh) || !IsValid(CachedMesh)){SetComponentTickEnabled(false);return;}
    const float Density=DensityProperty->GetPropertyValue_InContainer(Material);
    if(bCached)
    {
        if(Density<=0 || GetOwner()->IsHidden())
        {CachedMesh->SetVisibility(false);SetComponentTickEnabled(false);return;}
        // A moved effect needs a fresh world-to-volume transform and lighting.
        if(!PreparedTransform.Equals(GetOwner()->GetActorTransform())){RestoreLiveRenderer();return;}
        const float Ratio=Density/PreparedDensity;
        // Zibra's shader density includes an internal multiplier (currently1.5).
        // Preserve the captured uniform instead of substituting the raw node value.
        float PreparedShaderDensity=PreparedDensity;
        SourceMesh->GetMaterial(0)->GetScalarParameterValue(FMaterialParameterInfo(TEXT("DensityScale")),PreparedShaderDensity);
        CachedMaterial->SetScalarParameterValue(TEXT("DensityScale"),PreparedShaderDensity*Ratio);
        CachedMaterial->SetScalarParameterValue(TEXT("ProphecyCachedDensityRatio"),Ratio);
        return;
    }
    if(Density<=0 || GetOwner()->IsHidden()) {SetComponentTickEnabled(false);return;}
    if(FrameProperty->GetPropertyValue_InContainer(Playback)<float(FrameCount-1))return;
    const FTransform Transform=GetOwner()->GetActorTransform();
    // Never capture textures while their density/transform inputs are changing.
    // Early overlapping fades remain live; the common held-before-fade path caches.
    if(Phase==0 || Density!=PreparedDensity || !PreparedTransform.Equals(Transform))
    {
        PreparedDensity=Density;PreparedTransform=Transform;
        CandidateFrame=GFrameCounter;CandidateRenderTime=SourceMesh->GetLastRenderTime();Phase=1;return;
    }
    if(Phase==1)
    {
        // Observe a real render after the final source frame, including SceneCapture.
        // Offscreen effects wait instead of caching stale/uninitialised source data.
        if(GFrameCounter<=CandidateFrame || SourceMesh->GetLastRenderTime()<=CandidateRenderTime)return;
        PreparationFence.BeginFence();Phase=2;return;
    }
    if(!PreparationFence.IsFenceComplete())return; // Never wait/stall the game thread.
    if(CapturePreparedVolume())Phase=3;
}
