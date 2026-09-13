#include "ProphecyJoltISMBloodFixture.h"

#include "ProphecyBloodTexturePaintManager.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "Helpers/PCGActorHelpers.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "Kismet/KismetSystemLibrary.h"
#include "MaterialShared.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/App.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "NiagaraDataInterfaceExport.h"
#include "PCGComponent.h"
#include "PCGManagedResource.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/UnrealType.h"
#include "UObject/StructOnScope.h"
#if WITH_EDITOR
#include "MaterialShaderPrecompileMode.h"
#endif

namespace ProphecyJolt::ISMBloodFixture
{
namespace
{
constexpr const TCHAR* DecalClassPath = TEXT("/Game/_mygame/blood2/A_DecalManager.A_DecalManager_C");
constexpr const TCHAR* PaintClassPath = TEXT("/Game/Prophecy/BloodTexturePainting/BP_BloodPaintManager.BP_BloodPaintManager_C");
constexpr const TCHAR* BrushPath = TEXT("/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle.M_BloodBrush_Circle");
constexpr const TCHAR* FallbackPath = TEXT("/Game/Prophecy/BloodTexturePainting/M_BloodPaint_RuntimeTest.M_BloodPaint_RuntimeTest");
constexpr int32 Resolution = 256;

struct FOwnedObjects
{
    UWorld& World;
    AActor* Deferred = nullptr;
    AActor* SourceOwner = nullptr;
    AProphecyBloodTexturePaintManager* Paint = nullptr;
    TSet<TWeakObjectPtr<AStaticMeshActor>> PriorStaticActors;

    explicit FOwnedObjects(UWorld& InWorld) : World(InWorld)
    {
        for (TActorIterator<AStaticMeshActor> It(&World); It; ++It) PriorStaticActors.Add(*It);
    }
    ~FOwnedObjects()
    {
        if (Paint) Paint->ClearRuntimePaintState(true);
        // No world ticks, timers or latent commands occur inside this synchronous fixture. The
        // only additional StaticMeshActor spawns during it are the callback's promotion nodes.
        TArray<AStaticMeshActor*> Created;
        for (TActorIterator<AStaticMeshActor> It(&World); It; ++It)
            if (!PriorStaticActors.Contains(*It)) Created.Add(*It);
        for (AStaticMeshActor* Actor : Created) { Actor->SetFlags(RF_Transient); Actor->Destroy(); }
        if (Paint) Paint->Destroy();
        if (Deferred) Deferred->Destroy(); // Deliberately never FinishSpawning this test actor.
        if (SourceOwner) SourceOwner->Destroy();
    }
};

bool ReadMask(UMaterialInstanceDynamic* MID, UWorld& World, UTextureRenderTarget2D*& RT, TArray<FColor>& Pixels)
{
    UTexture* Texture = nullptr;
    if (!MID || !MID->GetTextureParameterValue(FHashedMaterialParameterInfo(FName(TEXT("BloodMaskRT"))), Texture)) return false;
    RT = Cast<UTextureRenderTarget2D>(Texture);
    return RT && RT->SizeX == Resolution && RT->SizeY == Resolution
        && UKismetRenderingLibrary::ReadRenderTarget(&World, RT, Pixels, false) && Pixels.Num() == Resolution * Resolution;
}

int32 NonBlack(const TArray<FColor>& Pixels)
{
    int32 Count = 0;
    for (const FColor& P : Pixels) if (P.R || P.G || P.B) ++Count;
    return Count;
}

UMaterialInterface* PairFor(const AProphecyBloodTexturePaintManager* Manager, UMaterialInterface* Original)
{
    if (Manager) for (const FProphecyBloodMaterialPair& Pair : Manager->BloodEnabledMaterialPairs)
        if (Pair.CleanMaterial == Original && Pair.BloodMaterial) return Pair.BloodMaterial;
    return nullptr;
}

bool PrepareMaterial(UMaterialInterface& Material, UWorld& World, const TSharedPtr<FJsonObject>& Report,
    const FString& Key, FString& Error)
{
    FMaterialResource* Resource = Material.GetMaterialResource(GetFeatureLevelShaderPlatform(World.GetFeatureLevel()));
#if WITH_EDITOR
    // Finish both pending material-DDC/cache work and shader jobs before deciding whether to cache.
    // Do not unconditionally recache: that invalidated the ready brush on a repeated fixture call.
    if (Resource) Resource->FinishCompilation();
    if (!Resource || !Resource->GetGameThreadShaderMap() || !Resource->IsGameThreadShaderMapComplete())
    {
        Material.CacheShaders(EMaterialShaderPrecompileMode::Synchronous);
        Resource = Material.GetMaterialResource(GetFeatureLevelShaderPlatform(World.GetFeatureLevel()));
        if (Resource) Resource->FinishCompilation();
    }
#endif
    auto State = MakeShared<FJsonObject>();
    State->SetStringField(TEXT("material"), Material.GetPathName());
    State->SetBoolField(TEXT("all_render_resources_complete"), Material.IsComplete());
    State->SetBoolField(TEXT("world_resource_present"), Resource != nullptr);
    State->SetBoolField(TEXT("world_shader_map_present"), Resource && Resource->GetGameThreadShaderMap());
    State->SetBoolField(TEXT("world_shader_map_complete"), Resource && Resource->IsGameThreadShaderMapComplete());
    TArray<TSharedPtr<FJsonValue>> Errors;
#if WITH_EDITOR
    if (Resource) for (const FString& CompileError : Resource->GetCompileErrors()) Errors.Add(MakeShared<FJsonValueString>(CompileError));
#endif
    State->SetArrayField(TEXT("compile_errors"), Errors);
    Report->SetObjectField(Key, State);
    if (!Resource || !Resource->GetGameThreadShaderMap() || !Resource->IsGameThreadShaderMapComplete())
    {
        Error = FString::Printf(TEXT("Material %s has no complete shader map for the fixture world; see %s diagnostics."), *Material.GetPathName(), *Key);
        Report->SetStringField(TEXT("error"), Error);
        return false;
    }
    return true;
}

bool Trace(UWorld& World, AActor* IgnoreSelf, const FBasicParticleData& Particle, FHitResult& Hit)
{
    // Exported graph: P + V, then (P + V) + (-2 * V) == P - V. Size==1 selects Query4.
    const ETraceTypeQuery Channel = Particle.Size == 1.0f ? TraceTypeQuery4 : TraceTypeQuery1;
    return UKismetSystemLibrary::LineTraceSingle(&World, Particle.Position + Particle.Velocity,
        Particle.Position - Particle.Velocity, Channel, true, { IgnoreSelf }, EDrawDebugTrace::None,
        Hit, false, FLinearColor::Red, FLinearColor::Green, 0.0f);
}

bool InvokeParticleCallback(UObject& Target, UFunction& Callback, const FBasicParticleData& Particle, FString& Error)
{
    // UE5.7 does not export this Niagara interface's generated Execute_ function from its DLL.
    // Its Blueprint dispatch is ProcessEvent; use the reflected parameter layout, never a guessed ABI.
    FArrayProperty* Data = FindFProperty<FArrayProperty>(&Callback, TEXT("Data"));
    FStructProperty* Element = Data ? CastField<FStructProperty>(Data->Inner) : nullptr;
    FObjectPropertyBase* System = FindFProperty<FObjectPropertyBase>(&Callback, TEXT("NiagaraSystem"));
    FStructProperty* Offset = FindFProperty<FStructProperty>(&Callback, TEXT("SimulationPositionOffset"));
    if (Callback.Script.IsEmpty() || Callback.NumParms != 3 || !Element
        || Element->Struct->GetFName() != FName(TEXT("BasicParticleData"))
        || Element->Struct->GetStructureSize() != sizeof(FBasicParticleData)
        || !System || System->PropertyClass->GetFName() != FName(TEXT("NiagaraSystem"))
        || !Offset || Offset->Struct != TBaseStructure<FVector>::Get())
    {
        Error = TEXT("The existing Niagara Blueprint callback has an unexpected parameter layout.");
        return false;
    }
    FStructOnScope Parameters(&Callback);
    void* Memory = Parameters.GetStructMemory();
    FScriptArrayHelper Values(Data, Data->ContainerPtrToValuePtr<void>(Memory));
    Values.AddValue();
    Element->CopyCompleteValue(Values.GetRawPtr(0), &Particle);
    System->SetObjectPropertyValue_InContainer(Memory, nullptr);
    const FVector ZeroOffset = FVector::ZeroVector;
    Offset->CopyCompleteValue(Offset->ContainerPtrToValuePtr<void>(Memory), &ZeroOffset);
    Target.ProcessEvent(&Callback, Memory);
    return true;
}
}

bool ValidatePromotion(UWorld& World, const FTransform& Placement,
    TSharedPtr<FJsonObject>& OutReport, FString& OutError)
{
    OutError.Reset();
    OutReport = MakeShared<FJsonObject>();
    OutReport->SetBoolField(TEXT("success"), false);
    OutReport->SetStringField(TEXT("scope"), TEXT("Existing Blueprint callback, retained UE complex queries, two promoted per-component blood masks and repeat no-duplicate behavior. No Jolt static ownership, Niagara simulation/export, SCS/BeginPlay, HISM/PCG, screenshots or performance claim."));
    OutReport->SetBoolField(TEXT("asset_saves_requested"), false);
    auto Need = [&](bool Condition, const FString& Message)
    {
        if (Condition) return true;
        OutError = Message;
        OutReport->SetStringField(TEXT("error"), Message);
        return false;
    };
    if (!Need(IsInGameThread() && FApp::CanEverRender(), TEXT("ISM blood pixels require the game thread and a real RHI."))) return false;
    if (!Need(!World.bIsTearingDown && World.IsGameWorld() && World.AreActorsInitialized(),
        TEXT("Deferred BP ProcessEvent requires an initialized game world; this fixture does not enable editor script execution."))) return false;
    if (!Need(!Placement.ContainsNaN() && Placement.GetRotation().IsNormalized()
        && Placement.GetScale3D().Equals(FVector::OneVector, 1.0e-6), TEXT("Use a finite rigid/unit-scale fixture placement."))) return false;

    UClass* DecalClass = LoadClass<AActor>(nullptr, DecalClassPath);
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    UMaterialInterface* Brush = LoadObject<UMaterialInterface>(nullptr, BrushPath);
    UMaterialInterface* Fallback = LoadObject<UMaterialInterface>(nullptr, FallbackPath);
    if (!Need(DecalClass && Cube && Brush && Fallback, TEXT("Existing callback class, cube or blood materials are missing."))) return false;
    if (!Need(DecalClass->ImplementsInterface(UNiagaraParticleCallbackHandler::StaticClass()), TEXT("Current decal-manager class no longer implements the inspected Niagara callback."))) return false;
    FObjectPropertyBase* PaintProperty = FindFProperty<FObjectPropertyBase>(DecalClass, TEXT("paint manager"));
    FObjectPropertyBase* FloorProperty = FindFProperty<FObjectPropertyBase>(DecalClass, TEXT("floor"));
    FFloatProperty* RadiusProperty = FindFProperty<FFloatProperty>(DecalClass, TEXT("brush radius"));
    FArrayProperty* ImpostorsProperty = FindFProperty<FArrayProperty>(DecalClass, TEXT("SM impostors"));
    FObjectPropertyBase* GridProperty = FindFProperty<FObjectPropertyBase>(DecalClass, TEXT("ProphecyFoliageDecalGrid"));
    FObjectPropertyBase* ImpostorElement = ImpostorsProperty ? CastField<FObjectPropertyBase>(ImpostorsProperty->Inner) : nullptr;
    if (!Need(PaintProperty && FloorProperty && RadiusProperty && GridProperty && ImpostorElement
        && AProphecyBloodTexturePaintManager::StaticClass()->IsChildOf(PaintProperty->PropertyClass)
        && AStaticMeshActor::StaticClass()->IsChildOf(FloorProperty->PropertyClass)
        && ImpostorElement->PropertyClass->IsChildOf(AStaticMeshActor::StaticClass()),
        TEXT("Reflected callback properties do not match the exported graph; do not guess or call it."))) return false;

    UMaterialInterface* Original = Cube->GetMaterial(0);
    UMaterialInterface* Template = nullptr;
    FString MappingSource;
    for (TActorIterator<AProphecyBloodTexturePaintManager> It(&World); It && !Template; ++It)
    {
        Template = PairFor(*It, Original);
        if (Template) MappingSource = It->GetPathName();
    }
    if (!Template)
    {
        UClass* PaintClass = LoadClass<AProphecyBloodTexturePaintManager>(nullptr, PaintClassPath);
        Template = PaintClass ? PairFor(Cast<AProphecyBloodTexturePaintManager>(PaintClass->GetDefaultObject()), Original) : nullptr;
        if (Template) MappingSource = PaintClassPath;
    }
    const bool bFallback = Template == nullptr;
    if (!Template) { Template = Fallback; MappingSource = TEXT("explicit_fixture_fallback"); }
    if (!PrepareMaterial(*Brush, World, OutReport, TEXT("brush_shader"), OutError)
        || !PrepareMaterial(*Template, World, OutReport, TEXT("template_shader"), OutError)) return false;
    OutReport->SetStringField(TEXT("brush_asset"), Brush->GetPathName());
    OutReport->SetStringField(TEXT("blood_template"), Template->GetPathName());
    OutReport->SetStringField(TEXT("mapping_source"), MappingSource);
    OutReport->SetBoolField(TEXT("fixture_fallback"), bFallback);

    FOwnedObjects Owned(World);
    FActorSpawnParameters Spawn;
    Spawn.ObjectFlags |= RF_Transient;
    Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    Owned.Paint = World.SpawnActor<AProphecyBloodTexturePaintManager>(FVector::ZeroVector, FRotator::ZeroRotator, Spawn);
    Owned.SourceOwner = World.SpawnActor<AActor>(FVector::ZeroVector, FRotator::ZeroRotator, Spawn);
    if (!Need(Owned.Paint && Owned.SourceOwner, TEXT("Native transient fixture actors could not be spawned."))) return false;
    AProphecyBloodTexturePaintManager& Paint = *Owned.Paint;
    Paint.SetActorTickEnabled(false);
    Paint.bFlushEveryTick = false;
    Paint.bEditorAutoCreateBloodMaterials = false;
    Paint.bEditorAutoUpdateBloodMaterials = false;
    Paint.bEditorAllowGeneratedMaterialOverwrite = false;
    Paint.bEditorSaveGeneratedBloodMaterials = false;
    Paint.bUseDefaultBloodMaterialTemplateForUnmappedMaterials = false;
    Paint.DefaultBloodMaterialTemplate = nullptr;
    Paint.BrushMaterial = Brush;
    FProphecyBloodMaterialPair Pair;
    Pair.CleanMaterial = Original; Pair.BloodMaterial = Template;
    Paint.BloodEnabledMaterialPairs = { Pair };
    Paint.DefaultRTResolutionSmall = Paint.DefaultRTResolutionMedium = Paint.DefaultRTResolutionLarge = Resolution;
    Paint.MaxActivePaintRTs = 2;
    Paint.MaxStampsPerFrame = Paint.MaxStampsPerRTPerFrame = 1;
    Paint.PaintUVChannel = 0;
    Paint.bRequirePaintableTag = false;
    Paint.bDebugMode = Paint.bDebugPrintHits = Paint.bDebugDrawHitLocations = Paint.bDebugLogRejectedHits = false;
    Paint.bDebugShowMaskOnPaintedMaterials = false;

    UInstancedStaticMeshComponent* ISM = NewObject<UInstancedStaticMeshComponent>(Owned.SourceOwner, NAME_None, RF_Transient);
    Owned.SourceOwner->AddInstanceComponent(ISM);
    Owned.SourceOwner->SetRootComponent(ISM);
    ISM->SetStaticMesh(Cube);
    ISM->SetCanEverAffectNavigation(false);
    ISM->SetCollisionProfileName(TEXT("BlockAll"));
    ISM->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    ISM->RegisterComponent();
    const FTransform Transforms[3] = {
        FTransform(FRotator(0.0, 17.0, 0.0), FVector(0.0, 0.0, 0.0), FVector(1.0, 1.25, 1.5)) * Placement,
        FTransform(FRotator(0.0, -29.0, 0.0), FVector(0.0, 300.0, 0.0), FVector(1.5, 0.75, 1.0)) * Placement,
        FTransform(FRotator::ZeroRotator, FVector(0.0, 600.0, 0.0), FVector::OneVector) * Placement
    };
    for (int32 Index = 0; Index < 3; ++Index)
        if (!Need(ISM->AddInstance(Transforms[Index], true) == Index, TEXT("Instance creation order changed."))) return false;

    Spawn.bDeferConstruction = true; // Same engine path as SpawnActorDeferred, with RF_Transient explicit.
    Owned.Deferred = World.SpawnActor<AActor>(DecalClass, FVector::ZeroVector, FRotator::ZeroRotator, Spawn);
    if (!Need(Owned.Deferred && !Owned.Deferred->HasActorBegunPlay() && !Owned.Deferred->IsActorInitialized(),
        TEXT("Callback actor did not remain deferred/uninitialized; do not run its unrelated BeginPlay."))) return false;
    Owned.Deferred->SetActorTickEnabled(false);
    UFunction* Callback = Owned.Deferred->FindFunction(TEXT("ReceiveParticleData"));
    if (!Need(Callback && (Callback->Script.Num() > 0 || Callback->HasAnyFunctionFlags(FUNC_Native)), TEXT("Callback has no executable body."))) return false;
    if (!Need(GridProperty->GetObjectPropertyValue_InContainer(Owned.Deferred) == nullptr,
        TEXT("Deferred grid field is unexpectedly populated; inspect the live class instead of assuming absent SCS."))) return false;
    PaintProperty->SetObjectPropertyValue_InContainer(Owned.Deferred, Owned.Paint);
    FloorProperty->SetObjectPropertyValue_InContainer(Owned.Deferred, nullptr);
    RadiusProperty->SetPropertyValue_InContainer(Owned.Deferred, 5.0f);
    auto Impostors = [&]()
    {
        TArray<AStaticMeshActor*> Result;
        FScriptArrayHelper Array(ImpostorsProperty, ImpostorsProperty->ContainerPtrToValuePtr<void>(Owned.Deferred));
        for (int32 Index = 0; Index < Array.Num(); ++Index)
            Result.Add(Cast<AStaticMeshActor>(ImpostorElement->GetObjectPropertyValue(Array.GetRawPtr(Index))));
        return Result;
    };
    if (!Need(Impostors().IsEmpty(), TEXT("Fresh deferred callback has preexisting promoted actors."))) return false;
    OutReport->SetStringField(TEXT("callback_actor"), Owned.Deferred->GetPathName());
    OutReport->SetBoolField(TEXT("finish_spawning_called"), false);
    OutReport->SetNumberField(TEXT("query1_collision_channel"), UEngineTypes::ConvertToCollisionChannel(TraceTypeQuery1));
    OutReport->SetNumberField(TEXT("query4_collision_channel"), UEngineTypes::ConvertToCollisionChannel(TraceTypeQuery4));
    OutReport->SetStringField(TEXT("particle_branch"), TEXT("Ordinary surface blood (Size=2, Query1). Size=1 selects the project's sword_only channel, ignored by the source BlockAll instance profile, and is outside this generic instance fixture."));

    FBasicParticleData Particles[2];
    UMaterialInstanceDynamic* MIDs[2] = {};
    UTextureRenderTarget2D* RTs[2] = {};
    TArray<FColor> Painted[2];
    TArray<TSharedPtr<FJsonValue>> Rows;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        const FVector LocalOffset(0.0, Index == 0 ? -12.0 : 17.0, Index == 0 ? 9.0 : -14.0);
        const FVector Start = Transforms[Index].TransformPosition(LocalOffset + FVector(-150.0, 0.0, 0.0));
        const FVector End = Transforms[Index].TransformPosition(LocalOffset + FVector(150.0, 0.0, 0.0));
        Particles[Index].Position = (Start + End) * 0.5;
        Particles[Index].Velocity = (Start - End) * 0.5;
        Particles[Index].Size = 2.0f;
        FHitResult SourceHit;
        if (!Need(Trace(World, Owned.Deferred, Particles[Index], SourceHit) && SourceHit.GetComponent() == ISM
            && SourceHit.Item == Index && SourceHit.FaceIndex >= 0,
            TEXT("Inspected particle trace did not identify the intended source instance/face."))) return false;
        if (!Need(InvokeParticleCallback(*Owned.Deferred, *Callback, Particles[Index], OutError), OutError)) return false;
        const TArray<AStaticMeshActor*> Current = Impostors();
        if (!Need(Current.Num() == Index + 1 && IsValid(Current.Last()) && !Owned.Deferred->HasActorBegunPlay()
            && !Owned.Deferred->IsActorInitialized(), TEXT("Deferred callback did not perform exactly one observable promotion, or initialized unexpectedly."))) return false;
        AStaticMeshActor* Promoted = Current.Last();
        Promoted->SetFlags(RF_Transient);
        if (!Need(!Owned.PriorStaticActors.Contains(Promoted) && Promoted->GetStaticMeshComponent()->GetStaticMesh() == Cube
            && Promoted->GetActorTransform().Equals(Transforms[Index], 1.0e-3), TEXT("Promotion lost instance transform or source mesh identity."))) return false;
        FTransform Hidden;
        const bool bReadHidden = ISM->GetInstanceTransform(Index, Hidden, true);
        OutReport->SetStringField(FString::Printf(TEXT("retired_source_transform_%d"), Index), Hidden.ToString());
        // ISM stores matrices. Zeroing all scale axes erases rotation from that matrix; the promoted
        // actor above must retain the authored rotation, while the retired source must lose collision.
        if (!Need(bReadHidden && Hidden.GetScale3D().IsNearlyZero()
            && Hidden.GetLocation().Equals(Transforms[Index].GetLocation(), 1.0e-3), TEXT("Source instance was not hidden at its original location."))) return false;
        FHitResult RetiredHit;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(ProphecyJoltISMBloodFixture), true);
        if (!Need(!ISM->LineTraceComponent(RetiredHit, Start, End, Query), TEXT("Zero-scale original instance retained query collision."))) return false;
        FHitResult PromotedHit;
        FVector2D UV;
        if (!Need(Trace(World, Owned.Deferred, Particles[Index], PromotedHit) && PromotedHit.GetActor() == Promoted
            && UGameplayStatics::FindCollisionUV(PromotedHit, 0, UV), TEXT("Replacement receiver lacks current complex query/UV identity."))) return false;
        MIDs[Index] = Cast<UMaterialInstanceDynamic>(Promoted->GetStaticMeshComponent()->GetMaterial(0));
        TArray<FColor> Before;
        if (!Need(Paint.ActivePaintStates == Index + 1 && Paint.QueuedStampCount == 1 && Paint.UnsupportedHitCount == 0
            && ReadMask(MIDs[Index], World, RTs[Index], Before) && NonBlack(Before) == 0, TEXT("Promotion did not queue one stamp into a fresh bound black mask."))) return false;
        Paint.FlushPendingBloodStamps();
        if (!Need(Paint.StampsFlushedLastFrame == 1 && Paint.QueuedStampCount == 0 && Paint.StampsDroppedLastFrame == 0
            && ReadMask(MIDs[Index], World, RTs[Index], Painted[Index]) && NonBlack(Painted[Index]) > 0
            && NonBlack(Painted[Index]) < Painted[Index].Num(), TEXT("Promoted receiver did not acquire localized real-RHI mask pixels."))) return false;
        if (Index == 1)
        {
            TArray<FColor> PreviousAgain;
            UTextureRenderTarget2D* PreviousRT = nullptr;
            if (!Need(MIDs[0] != MIDs[1] && RTs[0] != RTs[1]
                && ReadMask(MIDs[0], World, PreviousRT, PreviousAgain) && PreviousRT == RTs[0] && PreviousAgain == Painted[0],
                TEXT("Second instance painting changed or shared the first receiver's mask."))) return false;
        }
        auto Row = MakeShared<FJsonObject>();
        Row->SetNumberField(TEXT("source_item"), Index);
        Row->SetNumberField(TEXT("particle_size"), Particles[Index].Size);
        Row->SetNumberField(TEXT("source_face_index"), SourceHit.FaceIndex);
        Row->SetStringField(TEXT("source_transform"), Transforms[Index].ToString());
        Row->SetStringField(TEXT("promoted_actor"), Promoted->GetPathName());
        Row->SetStringField(TEXT("promoted_transform"), Promoted->GetActorTransform().ToString());
        Row->SetStringField(TEXT("mid"), MIDs[Index]->GetPathName());
        Row->SetStringField(TEXT("render_target"), RTs[Index]->GetPathName());
        Row->SetNumberField(TEXT("nonblack_pixels"), NonBlack(Painted[Index]));
        Rows.Add(MakeShared<FJsonValueObject>(Row));
        OutReport->SetArrayField(TEXT("promotions"), Rows);
    }
    FTransform Neighbor;
    if (!Need(ISM->GetInstanceTransform(2, Neighbor, true) && Neighbor.Equals(Transforms[2], 1.0e-3)
        && ISM->GetMaterial(0) == Original && ISM->GetInstanceCount() == 3,
        TEXT("Untouched neighbor or shared source material changed."))) return false;
    const TArray<AStaticMeshActor*> BeforeRepeat = Impostors();
    if (!Need(InvokeParticleCallback(*Owned.Deferred, *Callback, Particles[0], OutError), OutError)) return false;
    if (!Need(Impostors() == BeforeRepeat && Paint.ActivePaintStates == 2 && Paint.QueuedStampCount == 0,
        TEXT("Repeat hit created another receiver or unexpectedly queued texture paint."))) return false;
    TArray<FColor> RepeatPixels;
    UTextureRenderTarget2D* RepeatRT = nullptr;
    if (!Need(ReadMask(MIDs[0], World, RepeatRT, RepeatPixels) && RepeatRT == RTs[0] && RepeatPixels == Painted[0],
        TEXT("Repeat callback corrupted the existing persistent mask."))) return false;
    OutReport->SetArrayField(TEXT("promotions"), Rows);
    OutReport->SetBoolField(TEXT("untouched_neighbor_preserved"), true);
    OutReport->SetBoolField(TEXT("source_query_colliders_retired"), true);
    OutReport->SetBoolField(TEXT("independent_masks"), true);
    OutReport->SetBoolField(TEXT("repeat_no_duplicate"), true);
    OutReport->SetStringField(TEXT("repeat_scope"), TEXT("Existing failed-ISM-cast branch calls null-safe foliage helpers and its debug print. It does not enqueue another TryPaintFromHit stamp; this is baseline behavior, not repeat texture-paint completion."));
    OutReport->SetBoolField(TEXT("success"), true);
    return true;
}

#if !UE_BUILD_SHIPPING
namespace
{
// Explicit console fixtures leave their transient receivers alive for rendered before/after
// comparisons. They never edit a content asset or substitute the raster-test material above.
struct FVisualInstanceRow
{
    FString Kind;
    TWeakObjectPtr<AActor> Actor;
    TWeakObjectPtr<UInstancedStaticMeshComponent> Source;
    TWeakObjectPtr<UPCGComponent> PCG;
    FTransform Transforms[3];
    FProphecyJoltBodyHandle InitialHandles[3];
    FBasicParticleData Particles[2];
    TWeakObjectPtr<AStaticMeshActor> Promoted[2];
    TWeakObjectPtr<UMaterialInstanceDynamic> MIDs[2];
    TWeakObjectPtr<UTextureRenderTarget2D> Masks[2];
    TArray<FColor> Pixels[2];
};

struct FVisualInstances
{
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<AActor> Callback;
    TWeakObjectPtr<AProphecyBloodTexturePaintManager> Paint;
    TWeakObjectPtr<UProphecyJoltSceneCollisionComponent> Scene;
    TWeakObjectPtr<UStaticMesh> Mesh;
    TWeakObjectPtr<UMaterialInterface> Original;
    TArray<FVisualInstanceRow> Rows;
    TSharedPtr<FJsonObject> Report = MakeShared<FJsonObject>();
    FString ReportPath;
    bool bJolt = false;
    bool bPainted = false;
};
TUniquePtr<FVisualInstances> Visual;

bool VisualNeed(bool bCondition, const FString& Error)
{
    if (bCondition) return true;
    if (Visual)
    {
        Visual->Report->SetBoolField(TEXT("success"), false);
        Visual->Report->SetStringField(TEXT("error"), Error);
    }
    UE_LOG(LogTemp, Error, TEXT("BloodInstances: %s"), *Error);
    return false;
}

void WriteVisualReport()
{
    if (!Visual) return;
    FString Json;
    FJsonSerializer::Serialize(Visual->Report.ToSharedRef(), TJsonWriterFactory<>::Create(&Json));
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Visual->ReportPath), true);
    if (!FFileHelper::SaveStringToFile(Json, *Visual->ReportPath))
    {
        UE_LOG(LogTemp, Error, TEXT("BloodInstances could not write %s"), *Visual->ReportPath);
    }
    else
    {
        UE_LOG(LogTemp, Display, TEXT("BloodInstances report: %s"), *Visual->ReportPath);
    }
}

void LabelVisual(AActor& Actor, const FString& Label)
{
    Actor.SetFlags(RF_Transient);
    Actor.Tags.AddUnique(FName(TEXT("ProphecyBloodVisualInstanceFixture")));
#if WITH_EDITOR
    Actor.SetActorLabel(Label, false);
#endif
}

TArray<AStaticMeshActor*> VisualImpostors()
{
    TArray<AStaticMeshActor*> Result;
    AActor* Callback = Visual ? Visual->Callback.Get() : nullptr;
    FArrayProperty* Property = Callback ? FindFProperty<FArrayProperty>(Callback->GetClass(), TEXT("SM impostors")) : nullptr;
    FObjectPropertyBase* Element = Property ? CastField<FObjectPropertyBase>(Property->Inner) : nullptr;
    if (Element)
    {
        FScriptArrayHelper Array(Property, Property->ContainerPtrToValuePtr<void>(Callback));
        for (int32 I = 0; I < Array.Num(); ++I)
            Result.Add(Cast<AStaticMeshActor>(Element->GetObjectPropertyValue(Array.GetRawPtr(I))));
    }
    return Result;
}

bool SameVisualHandle(const FProphecyJoltBodyHandle& A, const FProphecyJoltBodyHandle& B)
{
    return A.WorldLifetime == B.WorldLifetime && A.Slot == B.Slot && A.Generation == B.Generation;
}

bool ReconcileVisual()
{
    if (!Visual->bJolt) return true;
    FString Error;
    auto* Scene = Visual->Scene.Get();
    return VisualNeed(Scene && Scene->IsSceneCollisionEnabled(), TEXT("Jolt scene owner is not enabled."))
        && VisualNeed(Scene->PrepareJoltWorldStep(0.0f, false, Error), Error);
}

void CleanupVisual()
{
    if (!Visual) return;
    TArray<FProphecyJoltBodyHandle> Handles;
    auto* Scene = Visual->Scene.Get();
    if (Scene) for (const FVisualInstanceRow& Row : Visual->Rows)
    {
        for (int32 I = 0; I < 3; ++I)
        {
            FProphecyJoltBodyHandle Handle;
            if (Row.Source.IsValid() && Scene->GetBodyHandle(*Row.Source, I, Handle)) Handles.Add(Handle);
        }
        for (const auto& Actor : Row.Promoted)
        {
            FProphecyJoltBodyHandle Handle;
            if (Actor.IsValid() && Scene->GetBodyHandle(*Actor->GetStaticMeshComponent(), INDEX_NONE, Handle)) Handles.Add(Handle);
        }
    }
    if (Visual->Paint.IsValid()) Visual->Paint->ClearRuntimePaintState(true);
    for (AStaticMeshActor* Actor : VisualImpostors()) if (IsValid(Actor)) Actor->Destroy();
    for (FVisualInstanceRow& Row : Visual->Rows)
    {
        if (Row.PCG.IsValid()) Row.PCG->CleanupLocalImmediate(true);
        if (Row.Actor.IsValid()) Row.Actor->Destroy();
    }
    if (Visual->Callback.IsValid()) Visual->Callback->Destroy();
    if (Visual->Paint.IsValid()) Visual->Paint->Destroy();
    bool bRetired = true;
    UWorld* World = Visual->World.Get();
    if (World && !World->bIsTearingDown && Visual->bJolt)
    {
        bRetired = ReconcileVisual();
        auto* Owner = World->GetSubsystem<UProphecyJoltWorldSubsystem>();
        for (const auto& Handle : Handles) bRetired &= Owner && !Owner->OwnsBody(Handle);
    }
    Visual->Report->SetBoolField(TEXT("cleanup_native_handles_retired"), bRetired);
    if (!bRetired) Visual->Report->SetBoolField(TEXT("success"), false);
    Visual->Report->SetNumberField(TEXT("cleanup_native_handle_count"), Handles.Num());
    Visual->Report->SetBoolField(TEXT("fixture_cleanup_complete"), true);
    WriteVisualReport();
    Visual.Reset();
}

bool SetupVisual(UWorld* World, const TArray<FString>& Args)
{
    if (!VisualNeed(World && World->IsGameWorld() && World->AreActorsInitialized()
        && !World->bIsTearingDown && FApp::CanEverRender(), TEXT("Use an initialized Game/PIE world with a real RHI."))) return false;
    CleanupVisual();
    Visual = MakeUnique<FVisualInstances>();
    Visual->World = World;
    Visual->bJolt = Args.IsEmpty() || !Args[0].Equals(TEXT("chaos"), ESearchCase::IgnoreCase);
    const FVector Origin(Args.Num() > 1 ? FCString::Atod(*Args[1]) : 0.0,
        Args.Num() > 2 ? FCString::Atod(*Args[2]) : 0.0, Args.Num() > 3 ? FCString::Atod(*Args[3]) : 200.0);
    Visual->ReportPath = FPaths::ProjectSavedDir() / TEXT("Diagnostics/BloodVisual")
        / FString::Printf(TEXT("instances-%s.json"), Visual->bJolt ? TEXT("jolt") : TEXT("chaos"));
    Visual->Report->SetBoolField(TEXT("success"), false);
    Visual->Report->SetStringField(TEXT("backend"), Visual->bJolt ? TEXT("Jolt") : TEXT("Chaos"));
    Visual->Report->SetStringField(TEXT("scope"), TEXT("Transient actual-rock ISM, HISM and CPU-PCG managed output; existing Blueprint particle callback and production blood material. Persistent actors for rendered comparison. PCG helper/resource path, not graph execution or GPU procedural ISM; no Niagara simulation/export or callback BeginPlay claim."));
    Visual->Report->SetBoolField(TEXT("fallback_material_used"), false);
    Visual->Report->SetBoolField(TEXT("asset_saves_requested"), false);
    Visual->Report->SetStringField(TEXT("origin"), Origin.ToString());
    UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Fab/Megascans/3D/Rock_shopk/Medium/shopk_tier_2/StaticMeshes/rock3.rock3"));
    UMaterialInterface* Template = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/BloodTexturePainting/Generated/Fab_Megascans_3D_Rock_shopk_Medium_shopk_tier_2_Materials_MI_shopk_BloodPaint.Fab_Megascans_3D_Rock_shopk_Medium_shopk_tier_2_Materials_MI_shopk_BloodPaint"));
    UMaterialInterface* Brush = LoadObject<UMaterialInterface>(nullptr, BrushPath);
    UClass* DecalClass = LoadClass<AActor>(nullptr, DecalClassPath);
    if (!VisualNeed(Mesh && Mesh->GetMaterial(0) && Template && Brush && DecalClass, TEXT("Actual rock, preserving blood variant, brush or callback class is missing."))) return false;
    Visual->Mesh = Mesh;
    Visual->Original = Mesh->GetMaterial(0);
    FString Error;
    if (!PrepareMaterial(*Template, *World, Visual->Report, TEXT("template_shader"), Error)
        || !PrepareMaterial(*Brush, *World, Visual->Report, TEXT("brush_shader"), Error)) return VisualNeed(false, Error);
    Visual->Report->SetStringField(TEXT("source_mesh"), Mesh->GetPathName());
    Visual->Report->SetStringField(TEXT("source_material"), Visual->Original->GetPathName());
    Visual->Report->SetStringField(TEXT("blood_material"), Template->GetPathName());
    for (TActorIterator<AActor> It(World); It && !Visual->Scene.IsValid(); ++It)
    {
        TArray<UProphecyJoltSceneCollisionComponent*> Components;
        It->GetComponents(Components);
        for (auto* Component : Components) if (Component->IsSceneCollisionEnabled()) { Visual->Scene = Component; break; }
    }
    if (Visual->bJolt)
    {
        if (!VisualNeed(Visual->Scene.IsValid(), TEXT("Enable the existing Jolt fight/static-scene owner before Jolt setup."))) return false;
    }
    else if (!VisualNeed(!Visual->Scene.IsValid(), TEXT("Chaos baseline requires the Jolt scene importer disabled so these instances are owned only by Chaos."))) return false;
    FActorSpawnParameters Spawn;
    Spawn.ObjectFlags |= RF_Transient;
    Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    auto* Paint = World->SpawnActor<AProphecyBloodTexturePaintManager>(AProphecyBloodTexturePaintManager::StaticClass(), FTransform::Identity, Spawn);
    if (!VisualNeed(Paint != nullptr, TEXT("Could not spawn transient paint manager."))) return false;
    Visual->Paint = Paint;
    LabelVisual(*Paint, TEXT("BloodVisual_InstancePaintManager"));
    Paint->SetActorTickEnabled(false);
    Paint->bFlushEveryTick = false;
    Paint->bEditorAutoCreateBloodMaterials = Paint->bEditorAutoUpdateBloodMaterials = false;
    Paint->bEditorAllowGeneratedMaterialOverwrite = Paint->bEditorSaveGeneratedBloodMaterials = false;
    Paint->bUseDefaultBloodMaterialTemplateForUnmappedMaterials = false;
    Paint->DefaultBloodMaterialTemplate = nullptr;
    Paint->BrushMaterial = Brush;
    FProphecyBloodMaterialPair Pair;
    Pair.CleanMaterial = Visual->Original.Get(); Pair.BloodMaterial = Template;
    Paint->BloodEnabledMaterialPairs = { Pair };
    Paint->DefaultRTResolutionSmall = Paint->DefaultRTResolutionMedium = Paint->DefaultRTResolutionLarge = Resolution;
    Paint->MaxActivePaintRTs = 6;
    Paint->MaxStampsPerFrame = Paint->MaxStampsPerRTPerFrame = 8;
    Paint->PaintUVChannel = 0;
    Paint->bRequirePaintableTag = false;
    Paint->bDebugMode = Paint->bDebugPrintHits = Paint->bDebugDrawHitLocations = Paint->bDebugLogRejectedHits = false;
    Paint->bDebugShowMaskOnPaintedMaterials = false;
    Spawn.bDeferConstruction = true;
    AActor* Callback = World->SpawnActor<AActor>(DecalClass, FTransform::Identity, Spawn);
    Visual->Callback = Callback;
    if (!VisualNeed(Callback && !Callback->IsActorInitialized() && !Callback->HasActorBegunPlay(), TEXT("Callback must remain deferred."))) return false;
    LabelVisual(*Callback, TEXT("BloodVisual_InstanceDecalCallback"));
    Callback->SetActorTickEnabled(false);
    FObjectPropertyBase* PaintProperty = FindFProperty<FObjectPropertyBase>(DecalClass, TEXT("paint manager"));
    FObjectPropertyBase* FloorProperty = FindFProperty<FObjectPropertyBase>(DecalClass, TEXT("floor"));
    FFloatProperty* RadiusProperty = FindFProperty<FFloatProperty>(DecalClass, TEXT("brush radius"));
    FArrayProperty* ImpostorsProperty = FindFProperty<FArrayProperty>(DecalClass, TEXT("SM impostors"));
    if (!VisualNeed(PaintProperty && FloorProperty && RadiusProperty && ImpostorsProperty
        && CastField<FObjectPropertyBase>(ImpostorsProperty->Inner)
        && AProphecyBloodTexturePaintManager::StaticClass()->IsChildOf(PaintProperty->PropertyClass),
        TEXT("Existing callback reflected properties changed."))) return false;
    PaintProperty->SetObjectPropertyValue_InContainer(Callback, Paint);
    FloorProperty->SetObjectPropertyValue_InContainer(Callback, nullptr);
    RadiusProperty->SetPropertyValue_InContainer(Callback, 15.0f);
    Spawn.bDeferConstruction = false;
    const double Scale = 120.0 / FMath::Max(Mesh->GetBoundingBox().GetSize().GetMax(), 1.0);
    for (int32 Kind = 0; Kind < 3; ++Kind)
    {
        FVisualInstanceRow& Row = Visual->Rows.AddDefaulted_GetRef();
        Row.Kind = Kind == 0 ? TEXT("ISM") : Kind == 1 ? TEXT("HISM") : TEXT("PCG_CPU");
        AActor* Actor = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Spawn);
        if (!VisualNeed(Actor != nullptr, TEXT("Could not spawn instance row."))) return false;
        Row.Actor = Actor;
        LabelVisual(*Actor, TEXT("BloodVisual_") + Row.Kind + TEXT("_Source"));
        USceneComponent* Root = NewObject<USceneComponent>(Actor, NAME_None, RF_Transient);
        Actor->AddInstanceComponent(Root); Actor->SetRootComponent(Root);
        Root->SetMobility(EComponentMobility::Static); Root->RegisterComponent();
        UInstancedStaticMeshComponent* Source = nullptr;
        if (Kind == 2)
        {
            UPCGComponent* PCG = NewObject<UPCGComponent>(Actor, NAME_None, RF_Transient);
            Actor->AddInstanceComponent(PCG); Row.PCG = PCG;
            PCG->GenerationTrigger = EPCGComponentGenerationTrigger::GenerateOnDemand;
            PCG->RegisterComponent();
            FPCGISMComponentBuilderParams Params;
            Params.bTransient = true;
            Params.bAllowDescriptorChanges = false;
            Params.Descriptor.StaticMesh = Mesh;
            Params.Descriptor.ComponentClass = UInstancedStaticMeshComponent::StaticClass();
            Params.Descriptor.Mobility = EComponentMobility::Static;
            Params.Descriptor.BodyInstance.SetCollisionProfileName(TEXT("BlockAll"));
            Source = UPCGActorHelpers::GetOrCreateISMC(Actor, PCG, Params);
            int32 ManagedCount = 0;
            PCG->ForEachManagedResource([&](UPCGManagedResource* Resource)
            {
                auto* Managed = Cast<UPCGManagedISMComponent>(Resource);
                if (Managed && Managed->GetComponent() == Source) ++ManagedCount;
            });
            Visual->Report->SetNumberField(TEXT("pcg_matching_managed_ism_resources"), ManagedCount);
            if (!VisualNeed(ManagedCount == 1, TEXT("PCG helper did not create its real managed ISM resource."))) return false;
        }
        else
        {
            Source = Kind == 0 ? NewObject<UInstancedStaticMeshComponent>(Actor, NAME_None, RF_Transient)
                : NewObject<UHierarchicalInstancedStaticMeshComponent>(Actor, NAME_None, RF_Transient);
            Actor->AddInstanceComponent(Source); Source->SetupAttachment(Root);
            Source->SetStaticMesh(Mesh); Source->SetMobility(EComponentMobility::Static);
        }
        if (!VisualNeed(Source != nullptr, TEXT("Could not create requested instance component."))) return false;
        Row.Source = Source;
        Source->SetCanEverAffectNavigation(false);
        Source->SetCollisionProfileName(TEXT("BlockAll"));
        Source->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Source->SetGenerateOverlapEvents(false);
        if (!Source->IsRegistered()) Source->RegisterComponent();
        for (int32 I = 0; I < 3; ++I)
        {
            const FVector RelativeScale = I == 0 ? FVector(1, 1.15, 0.9) : I == 1 ? FVector(0.9, 1, 1.1) : FVector::OneVector;
            Row.Transforms[I] = FTransform(FRotator(0, I == 0 ? 17 : I == 1 ? -29 : 0, 0),
                Origin + FVector(I * 300.0, Kind * 400.0, 0), RelativeScale * Scale);
            if (!VisualNeed(Source->AddInstance(Row.Transforms[I], true) == I, TEXT("Unexpected instance indices."))) return false;
        }
        if (auto* HISM = Cast<UHierarchicalInstancedStaticMeshComponent>(Source)) HISM->BuildTreeIfOutdated(false, true);
    }
    if (!ReconcileVisual()) return false;
    if (Visual->bJolt) for (auto& Row : Visual->Rows) for (int32 I = 0; I < 3; ++I)
        if (!VisualNeed(Visual->Scene->GetBodyHandle(*Row.Source, I, Row.InitialHandles[I]),
            FString::Printf(TEXT("%s instance %d has no initial native Jolt ownership."), *Row.Kind, I))) return false;
    Visual->Report->SetBoolField(TEXT("setup_complete"), true);
    Visual->Report->SetNumberField(TEXT("source_instance_count"), 9);
    return true;
}

bool FindVisualParticle(FVisualInstanceRow& Row, int32 Index, FHitResult& Hit)
{
    const FBox Bounds = Visual->Mesh->GetBoundingBox();
    // Mesh-space face samples, transformed with the rotated/nonuniform instance. Use the actual
    // complex trace identity, not guessed UV coordinates or an invented FHitResult.
    for (double Y : { 0.0, -0.25, 0.25 }) for (double Z : { 0.0, 0.25, -0.25 })
    {
        const FVector Offset = Bounds.GetCenter() + FVector(0, Bounds.GetExtent().Y * Y, Bounds.GetExtent().Z * Z);
        const FVector Start = Row.Transforms[Index].TransformPosition(Offset - FVector(Bounds.GetSize().X + 10, 0, 0));
        const FVector End = Row.Transforms[Index].TransformPosition(Offset + FVector(Bounds.GetSize().X + 10, 0, 0));
        FBasicParticleData& Particle = Row.Particles[Index];
        Particle.Position = (Start + End) * 0.5;
        Particle.Velocity = (Start - End) * 0.5;
        Particle.Size = 2;
        if (Trace(*Visual->World, Visual->Callback.Get(), Particle, Hit) && Hit.GetComponent() == Row.Source.Get()
            && Hit.Item == Index && Hit.FaceIndex >= 0) return true;
    }
    return false;
}

bool PaintVisual()
{
    if (!VisualNeed(Visual && Visual->World.IsValid() && Visual->Paint.IsValid()
        && Visual->Callback.IsValid() && !Visual->bPainted, TEXT("Run Setup first; Paint is single-use until Cleanup/Setup."))) return false;
    UFunction* Callback = Visual->Callback->FindFunction(TEXT("ReceiveParticleData"));
    if (!VisualNeed(Callback != nullptr, TEXT("Existing particle callback is missing."))) return false;
    int32 Count = 0;
    FString Error;
    TArray<TSharedPtr<FJsonValue>> Reports;
    for (FVisualInstanceRow& Row : Visual->Rows)
    {
        for (int32 I = 0; I < 2; ++I)
        {
            FHitResult SourceHit;
            if (!VisualNeed(FindVisualParticle(Row, I, SourceHit), Row.Kind + TEXT(" could not trace intended source face."))) return false;
            if (!VisualNeed(InvokeParticleCallback(*Visual->Callback, *Callback, Row.Particles[I], Error), Error)) return false;
            const auto Promoted = VisualImpostors();
            if (!VisualNeed(Promoted.Num() == ++Count && IsValid(Promoted.Last()), TEXT("Callback did not perform exactly one promotion."))) return false;
            auto* Actor = Promoted.Last();
            Row.Promoted[I] = Actor;
            LabelVisual(*Actor, FString::Printf(TEXT("BloodVisual_%s_Painted_%d"), *Row.Kind, I));
            if (!VisualNeed(Actor->GetStaticMeshComponent()->GetStaticMesh() == Visual->Mesh.Get()
                && Actor->GetActorTransform().Equals(Row.Transforms[I], 1.e-3), TEXT("Promotion changed mesh/rotation/scale."))) return false;
            FHitResult PaintedHit;
            FVector2D UV;
            if (!VisualNeed(Trace(*Visual->World, Visual->Callback.Get(), Row.Particles[I], PaintedHit)
                && PaintedHit.GetActor() == Actor && UGameplayStatics::FindCollisionUV(PaintedHit, 0, UV),
                TEXT("Promoted receiver lost complex trace/UV identity."))) return false;
            Row.MIDs[I] = Cast<UMaterialInstanceDynamic>(Actor->GetStaticMeshComponent()->GetMaterial(0));
            UTextureRenderTarget2D* RT = nullptr;
            TArray<FColor> Before;
            if (!VisualNeed(Visual->Paint->QueuedStampCount == 1 && ReadMask(Row.MIDs[I].Get(), *Visual->World, RT, Before)
                && NonBlack(Before) == 0, TEXT("New instance did not receive exactly one fresh black mask/stamp."))) return false;
            Visual->Paint->FlushPendingBloodStamps();
            if (!VisualNeed(Visual->Paint->StampsFlushedLastFrame == 1 && Visual->Paint->QueuedStampCount == 0
                && ReadMask(Row.MIDs[I].Get(), *Visual->World, RT, Row.Pixels[I])
                && NonBlack(Row.Pixels[I]) > 0 && NonBlack(Row.Pixels[I]) < Row.Pixels[I].Num(), TEXT("No localized rendered mask after callback."))) return false;
            Row.Masks[I] = RT;
            auto Report = MakeShared<FJsonObject>();
            Report->SetStringField(TEXT("kind"), Row.Kind);
            Report->SetStringField(TEXT("source_component_class"), Row.Source->GetClass()->GetPathName());
            Report->SetStringField(TEXT("source_actor"), Row.Actor->GetPathName());
            Report->SetNumberField(TEXT("source_instance"), I);
            Report->SetNumberField(TEXT("source_face"), SourceHit.FaceIndex);
            Report->SetStringField(TEXT("hit_world"), SourceHit.ImpactPoint.ToString());
            Report->SetStringField(TEXT("hit_uv"), UV.ToString());
            Report->SetStringField(TEXT("promoted_actor"), Actor->GetPathName());
            Report->SetStringField(TEXT("transform"), Actor->GetActorTransform().ToString());
            Report->SetStringField(TEXT("mid"), Row.MIDs[I]->GetPathName());
            Report->SetNumberField(TEXT("nonblack_pixels"), NonBlack(Row.Pixels[I]));
            Reports.Add(MakeShared<FJsonValueObject>(Report));
            Visual->Report->SetArrayField(TEXT("promotions"), Reports);
        }
        const auto BeforeRepeat = VisualImpostors();
        if (!VisualNeed(InvokeParticleCallback(*Visual->Callback, *Callback, Row.Particles[0], Error), Error)
            || !VisualNeed(VisualImpostors() == BeforeRepeat && Visual->Paint->QueuedStampCount == 0,
                TEXT("Repeat callback unexpectedly duplicated/repainted the promoted actor."))) return false;
    }
    Visual->bPainted = true;
    Visual->Report->SetBoolField(TEXT("paint_complete"), true);
    Visual->Report->SetStringField(TEXT("repeat_behavior"), TEXT("The current Chaos baseline callback avoids duplicate promotion but queues no further texture stamp on a promoted StaticMeshActor. This fixture preserves and reports that behavior."));
    return true;
}

bool CheckVisual()
{
    if (!VisualNeed(Visual && Visual->World.IsValid() && Visual->bPainted, TEXT("Run Setup and Paint first."))) return false;
    if (!ReconcileVisual()) return false;
    auto* Owner = Visual->World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    TSet<UTextureRenderTarget2D*> Masks;
    for (const FVisualInstanceRow& Row : Visual->Rows)
    {
        FTransform Neighbor;
        if (!VisualNeed(Row.Source.IsValid() && Row.Source->GetInstanceCount() == 3
            && Row.Source->GetMaterial(0) == Visual->Original.Get()
            && Row.Source->GetInstanceTransform(2, Neighbor, true) && Neighbor.Equals(Row.Transforms[2], 1.e-3),
            Row.Kind + TEXT(" untouched neighbor/material changed."))) return false;
        for (int32 I = 0; I < 2; ++I)
        {
            FTransform Retired;
            FHitResult CurrentHit;
            UTextureRenderTarget2D* CurrentMask = nullptr;
            TArray<FColor> CurrentPixels;
            if (!VisualNeed(Row.Promoted[I].IsValid() && Row.Source->GetInstanceTransform(I, Retired, true)
                && Retired.GetScale3D().IsNearlyZero()
                && Trace(*Visual->World, Visual->Callback.Get(), Row.Particles[I], CurrentHit)
                && CurrentHit.GetActor() == Row.Promoted[I].Get()
                && ReadMask(Row.MIDs[I].Get(), *Visual->World, CurrentMask, CurrentPixels)
                && CurrentMask == Row.Masks[I].Get() && CurrentPixels == Row.Pixels[I] && !Masks.Contains(CurrentMask),
                Row.Kind + TEXT(" lost receiver identity or changed/shared its persistent mask."))) return false;
            Masks.Add(CurrentMask);
            if (Visual->bJolt)
            {
                FProphecyJoltBodyHandle Absent, Replacement;
                FProphecyJoltRayHit NativeHit;
                bool bHit = false;
                if (!VisualNeed(Owner && !Owner->OwnsBody(Row.InitialHandles[I])
                    && !Visual->Scene->GetBodyHandle(*Row.Source, I, Absent)
                    && Visual->Scene->GetBodyHandle(*Row.Promoted[I]->GetStaticMeshComponent(), INDEX_NONE, Replacement)
                    && Owner->RayCast(Row.Particles[I].Position + Row.Particles[I].Velocity,
                        Row.Particles[I].Position - Row.Particles[I].Velocity, NativeHit, bHit).IsSuccess()
                    && bHit && SameVisualHandle(NativeHit.Handle, Replacement),
                    Row.Kind + TEXT(" native source retirement/replacement ray identity failed."))) return false;
            }
        }
        if (Visual->bJolt)
        {
            FProphecyJoltBodyHandle NeighborHandle;
            if (!VisualNeed(Visual->Scene->GetBodyHandle(*Row.Source, 2, NeighborHandle)
                && SameVisualHandle(NeighborHandle, Row.InitialHandles[2]) && Owner->OwnsBody(NeighborHandle),
                Row.Kind + TEXT(" untouched neighbor changed native ownership."))) return false;
        }
    }
    Visual->Report->SetBoolField(TEXT("independent_persistent_masks"), true);
    Visual->Report->SetBoolField(TEXT("untouched_neighbors_preserved"), true);
    Visual->Report->SetBoolField(TEXT("repeat_no_duplicate"), true);
    Visual->Report->SetBoolField(TEXT("native_retirement_replacement_verified"), Visual->bJolt);
    Visual->Report->SetBoolField(TEXT("success"), true);
    Visual->Report->RemoveField(TEXT("error"));
    UE_LOG(LogTemp, Display, TEXT("BloodInstances verified six independent painted receivers and three clean neighbors (%s); inspect rendered actors for appearance."), Visual->bJolt ? TEXT("Jolt") : TEXT("Chaos"));
    return true;
}

FAutoConsoleCommandWithWorldAndArgs SetupVisualCommand(TEXT("prophecy.Jolt.BloodInstances.Setup"),
    TEXT("Transient production-rock rows for visual inspection: Setup [jolt|chaos] [x y z]. Requires initialized Game/PIE; Jolt requires an enabled scene owner."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    { SetupVisual(World, Args); WriteVisualReport(); }));
FAutoConsoleCommandWithWorldAndArgs PaintVisualCommand(TEXT("prophecy.Jolt.BloodInstances.Paint"),
    TEXT("Paint two of three rocks per ISM/HISM/CPU-PCG row through existing particle callback; leave actors for screenshots."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
    { if (VisualNeed(Visual && Visual->World.Get() == World, TEXT("Fixture belongs to another/no world."))) PaintVisual(); WriteVisualReport(); }));
FAutoConsoleCommandWithWorldAndArgs CheckVisualCommand(TEXT("prophecy.Jolt.BloodInstances.Check"),
    TEXT("Verify persistent instance masks and Jolt ownership after painting; optional JSON output path."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (VisualNeed(Visual && Visual->World.Get() == World, TEXT("Fixture belongs to another/no world.")))
        { if (!Args.IsEmpty()) Visual->ReportPath = Args[0]; CheckVisual(); }
        WriteVisualReport();
    }));
FAutoConsoleCommandWithWorldAndArgs CleanupVisualCommand(TEXT("prophecy.Jolt.BloodInstances.Cleanup"),
    TEXT("Destroy only transient instance fixture actors, retire their native handles, and record cleanup."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld*) { CleanupVisual(); }));
}
#endif
}
