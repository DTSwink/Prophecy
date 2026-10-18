#include "ProphecyVDBLibrary.h"
#include "ProphecyVDBPlaybackComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "UObject/StructOnScope.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogProphecyVDB,Log,All);

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
    FrameProperty->SetPropertyValue_InContainer(Playback,Timeline.Frame(ElapsedTicks));
    DensityProperty->SetPropertyValue_InContainer(Material,Timeline.Density(ElapsedTicks));
}

AActor* UProphecyVDBLibrary::SpawnVDBEffect(const UObject* Context,EProphecyVDBEffect Effect,FVector Location,
    float Scale,float Framerate,float DensityFadeStart,float TargetDensity,float DensityFadeDuration,FRotator Rotation)
{
    if(!IsInGameThread() || !IsValid(Context) || Location.ContainsNaN() || Rotation.ContainsNaN()
        || !FMath::IsFinite(Scale) || Scale<=0 || !FMath::IsFinite(Framerate) || Framerate<=0
        || !FMath::IsFinite(DensityFadeStart) || DensityFadeStart<0 || DensityFadeStart>1.e6f
        || !FMath::IsFinite(DensityFadeDuration) || DensityFadeDuration<0 || DensityFadeDuration>1.e6f
        || !FMath::IsFinite(TargetDensity) || TargetDensity<0)return nullptr;
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
    FStructOnScope Args(SetVolume);
    VolumeArgument->SetObjectPropertyValue_InContainer(Args.GetStructMemory(),Volume);
    Asset->ProcessEvent(SetVolume,Args.GetStructMemory());
    auto* Controller=NewObject<UProphecyVDBPlaybackComponent>(Actor);
    Actor->AddInstanceComponent(Controller);
    if(!Controller->Initialize(Playback,Material,Frames,Framerate,DensityFadeStart,DensityFadeDuration,TargetDensity))
    { Actor->Destroy();UE_LOG(LogProphecyVDB,Warning,TEXT("Spawn VDB Effect: incompatible playback/material properties."));return nullptr; }
    Actor->FinishSpawning(Transform);
    Controller->RegisterComponent();
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
    return !HasAnyErrors();
}
#endif
