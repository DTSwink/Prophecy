#include "ProphecyVDBLibrary.h"
#include "ProphecyVDBPlaybackComponent.h"
#include "ProphecyVDBOptimisedComponent.h"
#include "ProphecyVDBColorComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "UObject/StructOnScope.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogProphecyVDB,Log,All);

namespace
{
bool ConfigureVDBColors(UActorComponent* Material,const FLinearColor& Temperature,const FLinearColor& Scattering)
{
    auto* TemperatureProperty=FindFProperty<FStructProperty>(Material->GetClass(),TEXT("TemperatureColor"));
    auto* ScatteringProperty=FindFProperty<FStructProperty>(Material->GetClass(),TEXT("ScatteringColor"));
    if(!TemperatureProperty || !ScatteringProperty
        || TemperatureProperty->Struct!=TBaseStructure<FLinearColor>::Get()
        || ScatteringProperty->Struct!=TBaseStructure<FLinearColor>::Get())return false;
    // Both native defaults use SolidColor. Set before asset assignment/registration so
    // the plugin's existing texture preparation sees the chosen colors from frame zero.
    *TemperatureProperty->ContainerPtrToValuePtr<FLinearColor>(Material)=Temperature;
    *ScatteringProperty->ContainerPtrToValuePtr<FLinearColor>(Material)=Scattering;
    return true;
}

void ConfigureGameplayVDBQuality(UActorComponent* Material)
{
    // Keep the original source clip/timing. These are render resolutions, not animation rates.
    // Gameplay prioritizes cost: retain trilinear 3D smoke/shadows with quarter-resolution
    // render blocks, eighth-resolution illumination and a four-voxel ray step.
    auto* VolumeResolution=FindFProperty<FEnumProperty>(Material->GetClass(),TEXT("VolumeResolution"));
    auto* IlluminationResolution=FindFProperty<FEnumProperty>(Material->GetClass(),TEXT("IlluminationResolution"));
    const int64 Quarter=VolumeResolution?VolumeResolution->GetEnum()->GetValueByNameString(TEXT("Quarter")):INDEX_NONE;
    const int64 Eighth=IlluminationResolution?IlluminationResolution->GetEnum()->GetValueByNameString(TEXT("Eighth")):INDEX_NONE;
    auto* MainStep=FindFProperty<FFloatProperty>(Material->GetClass(),TEXT("RayMarchingMainStepSize"));
    if(Quarter==INDEX_NONE || Eighth==INDEX_NONE || !MainStep)
    {
        UE_LOG(LogProphecyVDB,Warning,TEXT("Spawn VDB Effect: quality properties unavailable; keeping plugin defaults."));
        return;
    }
    VolumeResolution->GetUnderlyingProperty()->SetIntPropertyValue(
        VolumeResolution->ContainerPtrToValuePtr<void>(Material),Quarter);
    IlluminationResolution->GetUnderlyingProperty()->SetIntPropertyValue(
        IlluminationResolution->ContainerPtrToValuePtr<void>(Material),Eighth);
    MainStep->SetPropertyValue_InContainer(Material,4.f);
}

bool CanReuseVDBLighting(const ProphecyVDB::FTimeline& Timeline,uint64 Tick)
{
    return Timeline.TargetDensity==1.f
        || Tick<Timeline.FadeStart || Tick>Timeline.FadeStart+Timeline.FadeDuration;
}

void SetVDBLightingReuse(UActorComponent* Material,bool Reuse)
{
    // Only called at initialization and fade boundaries, never a per-frame property search.
    // Zibra invalidates this cache when the source frame changes. During density fading,
    // lighting must update even if the source clip has already reached its last frame.
    if(auto* StaticLighting=FindFProperty<FBoolProperty>(Material->GetClass(),TEXT("bUseStaticIllumination")))
        StaticLighting->SetPropertyValue_InContainer(Material,Reuse);
}

void HideFinishedVDB(AActor* Actor,UActorComponent* Playback)
{
    Actor->SetActorHiddenInGame(true);
    // Also stop projected-shadow submission, whose plugin guard uses playback visibility.
    if(auto* Visible=FindFProperty<FBoolProperty>(Playback->GetClass(),TEXT("Visible")))
        Visible->SetPropertyValue_InContainer(Playback,false);
}
}

UProphecyVDBPlaybackComponent::UProphecyVDBPlaybackComponent()
{
    PrimaryComponentTick.bCanEverTick=true;
    PrimaryComponentTick.bStartWithTickEnabled=true;
    PrimaryComponentTick.TickGroup=TG_PrePhysics;
}

bool UProphecyVDBPlaybackComponent::Initialize(UActorComponent* InPlayback,UActorComponent* InMaterial,
    int32 Frames,float FPS,float FadeStart,float FadeDuration,float Target)
{
    // The installed plugin omits exports on its material class. Bind its reflected properties once,
    // without importing private SDK headers or forcing their defines into the entire game module.
    if(!InPlayback || !InMaterial || Frames<=0)return false;
    FrameProperty=FindFProperty<FFloatProperty>(InPlayback->GetClass(),TEXT("CurrentFrame"));
    DensityProperty=FindFProperty<FFloatProperty>(InMaterial->GetClass(),TEXT("DensityScale"));
    auto* Animate=FindFProperty<FBoolProperty>(InPlayback->GetClass(),TEXT("Animate"));
    auto* Rate=FindFProperty<FFloatProperty>(InPlayback->GetClass(),TEXT("Framerate"));
    if(!FrameProperty || !DensityProperty || !Animate || !Rate)return false;
    Playback=InPlayback; Material=InMaterial;
    Timeline.Init(Frames,FPS,FadeStart,FadeDuration,Target);
    ElapsedTicks=0; LastGameFrame=GFrameCounter;
    Animate->SetPropertyValue_InContainer(Playback,false);
    Rate->SetPropertyValue_InContainer(Playback,FPS);
    FrameProperty->SetPropertyValue_InContainer(Playback,0.f);
    DensityProperty->SetPropertyValue_InContainer(Material,Timeline.Density(0));
    SetVDBLightingReuse(Material,CanReuseVDBLighting(Timeline,0));
    if(Timeline.Density(0)==0.f)HideFinishedVDB(GetOwner(),Playback);
    // Publish the selected frame/density before Zibra updates its renderer this tick.
    Playback->AddTickPrerequisiteComponent(this);
    Material->AddTickPrerequisiteComponent(this);
    return true;
}

void UProphecyVDBPlaybackComponent::TickComponent(float DeltaSeconds,ELevelTick TickType,FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaSeconds,TickType,TickFunction);
    UWorld* World=GetWorld();
    if(!World || World->IsPaused() || TickType!=LEVELTICK_All || DeltaSeconds<=0 || LastGameFrame==GFrameCounter)return;
    LastGameFrame=GFrameCounter;
    if(!IsValid(Playback) || !IsValid(Material) || !FrameProperty || !DensityProperty)
    { GetOwner()->Destroy();return; }
    ++ElapsedTicks;
    if(ElapsedTicks>=Timeline.Finish)
    { GetOwner()->Destroy();return; }
    const uint64 FadeEnd=Timeline.FadeStart+Timeline.FadeDuration;
    if(ElapsedTicks==Timeline.FadeStart || ElapsedTicks==FadeEnd || ElapsedTicks==FadeEnd+1)
    {
        SetVDBLightingReuse(Material,CanReuseVDBLighting(Timeline,ElapsedTicks));
        // Both supported clips have no independent flames channel. Zero density means
        // zero scattering/temperature emission: keep lifetime semantics, skip GPU work.
        if(Timeline.Density(ElapsedTicks)==0.f)HideFinishedVDB(GetOwner(),Playback);
    }
    FrameProperty->SetPropertyValue_InContainer(Playback,Timeline.Frame(ElapsedTicks));
    DensityProperty->SetPropertyValue_InContainer(Material,Timeline.Density(ElapsedTicks));
}

AActor* UProphecyVDBLibrary::SpawnVDBEffect(const UObject* Context,EProphecyVDBEffect Effect,FVector Location,
    float Scale,float Framerate,float DensityFadeStart,float TargetDensity,float DensityFadeDuration,FRotator Rotation,bool bOptimised,
    FLinearColor TemperatureColor,FLinearColor ScatteringColor)
{
    if(!IsInGameThread() || !IsValid(Context) || Location.ContainsNaN() || Rotation.ContainsNaN()
        || !FMath::IsFinite(Scale) || Scale<=0 || !FMath::IsFinite(Framerate) || Framerate<=0
        || !FMath::IsFinite(DensityFadeStart) || DensityFadeStart<0 || DensityFadeStart>1.e6f
        || !FMath::IsFinite(DensityFadeDuration) || DensityFadeDuration<0 || DensityFadeDuration>1.e6f
        || !FMath::IsFinite(TargetDensity) || TargetDensity<0
        || !ProphecyVDB::IsValidColor(TemperatureColor) || !ProphecyVDB::IsValidColor(ScatteringColor))return nullptr;
    auto* World=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    if(!World || !World->IsGameWorld())return nullptr;
    const TCHAR* Path=nullptr;
    switch(Effect)
    {
    case EProphecyVDBEffect::Shockwave: Path=TEXT("/Game/_mygame/animations/VDB/Shockwave.Shockwave");break;
    case EProphecyVDBEffect::ShockwaveExplosion: Path=TEXT("/Game/_mygame/animations/VDB/ShockwaveExplosion.ShockwaveExplosion");break;
    default:return nullptr;
    }
    UObject* Volume=LoadObject<UObject>(nullptr,Path);
    auto* ActorClass=LoadClass<AActor>(nullptr,TEXT("/Script/ZibraVDBRuntime.ZibraVDBActor"));
    auto* FrameCount=Volume?FindFProperty<FIntProperty>(Volume->GetClass(),TEXT("FrameCount")):nullptr;
    const int32 Frames=FrameCount?FrameCount->GetPropertyValue_InContainer(Volume):0;
    if(!ActorClass || !Volume || Frames<=0 || double(Frames)/double(Framerate)>1.e6)
    { UE_LOG(LogProphecyVDB,Warning,TEXT("Spawn VDB Effect: asset/plugin unavailable or invalid framerate."));return nullptr; }
    const FTransform Transform(Rotation,Location,FVector(Scale));
    auto* Actor=World->SpawnActorDeferred<AActor>(ActorClass,Transform,nullptr,nullptr,ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if(!Actor)return nullptr;
    auto* Asset=Cast<UActorComponent>(Actor->GetDefaultSubobjectByName(TEXT("AssetComponent")));
    auto* Playback=Cast<UActorComponent>(Actor->GetDefaultSubobjectByName(TEXT("PlaybackComponent")));
    auto* Material=Cast<UActorComponent>(Actor->GetDefaultSubobjectByName(TEXT("MaterialComponent")));
    UFunction* SetVolume=Asset?Asset->FindFunction(TEXT("SetZibraVDBVolume")):nullptr;
    auto* VolumeArgument=SetVolume?FindFProperty<FObjectPropertyBase>(SetVolume,TEXT("InZibraVDBVolume")):nullptr;
    if(!VolumeArgument || !Volume->IsA(VolumeArgument->PropertyClass) || !Playback || !Material)
    { Actor->Destroy();UE_LOG(LogProphecyVDB,Warning,TEXT("Spawn VDB Effect: incompatible Zibra component API."));return nullptr; }
    // Configure before assigning the asset so its first render allocations use the cheap sizes.
    ConfigureGameplayVDBQuality(Material);
    if(!ConfigureVDBColors(Material,TemperatureColor,ScatteringColor))
    {Actor->Destroy();UE_LOG(LogProphecyVDB,Warning,TEXT("Spawn VDB Effect: incompatible color properties."));return nullptr;}
    FStructOnScope Args(SetVolume);
    VolumeArgument->SetObjectPropertyValue_InContainer(Args.GetStructMemory(),Volume);
    Asset->ProcessEvent(SetVolume,Args.GetStructMemory());
    auto* Controller=NewObject<UProphecyVDBPlaybackComponent>(Actor);
    Actor->AddInstanceComponent(Controller);
    if(!Controller->Initialize(Playback,Material,Frames,Framerate,DensityFadeStart,DensityFadeDuration,TargetDensity))
    { Actor->Destroy();UE_LOG(LogProphecyVDB,Warning,TEXT("Spawn VDB Effect: incompatible playback/material properties."));return nullptr; }
    Actor->FinishSpawning(Transform);
    Controller->RegisterComponent();
    if(bOptimised)
    {
        auto* Cache=NewObject<UProphecyVDBOptimisedComponent>(Actor);Actor->AddInstanceComponent(Cache);Cache->RegisterComponent();
        if(!Cache->Initialize(Playback,Material,Controller,Frames))
        {Cache->DestroyComponent();UE_LOG(LogProphecyVDB,Warning,TEXT("Optimised VDB renderer unavailable; retaining live rendering."));}
    }
    return Actor;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyVDBTimingTest,"Prophecy.VDB.PlaybackTiming",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyVDBTimingTest::RunTest(const FString&)
{
    ProphecyVDB::FTimeline T;
    T.Init(180,30,4,2,.2f);
    TestEqual(TEXT("180 frames at 30 finish at authored 6 seconds"),T.Finish,uint64(360));
    TestEqual(TEXT("Starts at first frame"),T.Frame(0),0.f);
    TestEqual(TEXT("30 source frames after 60 game ticks"),T.Frame(60),30.f);
    TestEqual(TEXT("Density remains 1 before fade"),T.Density(239),1.f);
    TestEqual(TEXT("Density is 1 at fade start"),T.Density(240),1.f);
    TestTrue(TEXT("Linear density midpoint"),FMath::IsNearlyEqual(T.Density(300),.6f));
    TestTrue(TEXT("Exact target at endpoint"),FMath::IsNearlyEqual(T.Density(360),.2f));
    TestEqual(TEXT("Never wraps past last frame"),T.Frame(600),179.f);
    T.Init(120,60,3,2,0);
    TestEqual(TEXT("Fade can outlast clip"),T.Finish,uint64(300));
    TestEqual(TEXT("Final frame held through late fade"),T.Frame(240),119.f);
    TestEqual(TEXT("Late fade midpoint"),T.Density(240),.5f);
    T.Init(120,30,0,0,.4f);
    TestEqual(TEXT("Zero-duration immediate density"),T.Density(0),.4f);
    TestEqual(TEXT("Early fade still plays clip once"),T.Finish,uint64(240));
    TestEqual(TEXT("Decimal seconds have no floating tick tail"),ProphecyVDB::DurationTicks(.1),uint64(6));
    T.Init(180,120,3,1,0);
    TestTrue(TEXT("Reuse lighting while final frame is held"),CanReuseVDBLighting(T,150));
    TestFalse(TEXT("Refresh lighting at fade start"),CanReuseVDBLighting(T,180));
    TestFalse(TEXT("Refresh lighting throughout fade"),CanReuseVDBLighting(T,239));
    TestFalse(TEXT("Refresh exact fade endpoint"),CanReuseVDBLighting(T,240));
    TestTrue(TEXT("Reuse lighting after endpoint refresh"),CanReuseVDBLighting(T,241));
    T.Init(180,30,0,1,.2f);
    TestFalse(TEXT("Immediate fade needs live lighting"),CanReuseVDBLighting(T,0));
    T.Init(180,30,0,1,1.f);
    TestTrue(TEXT("Constant density needs no fade invalidation"),CanReuseVDBLighting(T,30));
    T.Init(180,30,1,0,.2f);
    TestFalse(TEXT("Density snap invalidates lighting once"),CanReuseVDBLighting(T,60));
    TestTrue(TEXT("Reuse lighting after density snap"),CanReuseVDBLighting(T,61));
    return !HasAnyErrors();
}
#endif
