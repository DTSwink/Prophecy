#include "ProphecyJoltBloodFixture.h"
#include "UObject/Package.h"

#include "ProphecyBloodTexturePaintManager.h"
#include "Components/MeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/App.h"
#include "MaterialShaderPrecompileMode.h"
#include "MaterialShared.h"
#include "UObject/UObjectGlobals.h"
#include "UObject/StrongObjectPtr.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Engine/Engine.h"
#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "PhysicsEngine/BodyInstance.h"
#if WITH_EDITOR
#include "UObject/UnrealType.h"
#endif

namespace ProphecyJolt::BloodFixture
{
// Explicit render-validation helper. Only tagged test receivers are eligible;
// normal gameplay never invokes this command or changes ownership through it.
static FAutoConsoleCommandWithWorldAndArgs BloodVisualBodyCommand(
    TEXT("Prophecy.Jolt.BloodVisualBody"),
    TEXT("<receiver-tag> <jolt|chaos|state> [vx vy vz wx wy wz]. Tagged blood visual fixtures only."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        auto Report = MakeShared<FJsonObject>();
        FString Error;
        bool bSuccess = false;
        AActor* Receiver = nullptr;
        if (World && World->IsGameWorld() && Args.Num() >= 2)
            for (TActorIterator<AActor> It(World); It; ++It)
                if (It->ActorHasTag(TEXT("BloodVisual20260910")) && It->ActorHasTag(FName(*Args[0])))
                {
                    if (Receiver) { Error = TEXT("Receiver tag is not unique."); Receiver = nullptr; break; }
                    Receiver = *It;
                }
        auto* Mesh = Receiver ? Cast<UStaticMeshComponent>(Receiver->GetRootComponent()) : nullptr;
        auto* Body = Receiver ? Receiver->FindComponentByClass<UProphecyJoltBodyComponent>() : nullptr;
        if (!Mesh) Error = TEXT("No unique tagged test static-mesh receiver in a gameplay world.");
        else
        {
            if (Args[1] == TEXT("jolt") || Args[1] == TEXT("chaos"))
            {
                if (Body && Body->IsJoltBody()) Body->DisableBody();
                Mesh->SetMobility(EComponentMobility::Movable);
                Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
                Mesh->BodyInstance.SetUseMACD(false);
                Mesh->BodyInstance.SetUseCCD(true);
                Mesh->SetSimulatePhysics(true);
                if (Args[1] == TEXT("jolt"))
                {
                    if (!Body)
                    {
                        Body = NewObject<UProphecyJoltBodyComponent>(Receiver, NAME_None, RF_Transient);
                        Receiver->AddInstanceComponent(Body);
                        Body->RegisterComponent();
                    }
                    bSuccess = Body->EnableBody(*Mesh, Error);
                    if (bSuccess && Body->IsEnablePending())
                    { Error = TEXT("Admission queued; request state after the next gameplay tick."); }
                }
                else bSuccess = Mesh->IsSimulatingPhysics();
                if (bSuccess && Args.Num() == 8)
                {
                    const FVector V(FCString::Atod(*Args[2]), FCString::Atod(*Args[3]), FCString::Atod(*Args[4]));
                    const FVector W(FCString::Atod(*Args[5]), FCString::Atod(*Args[6]), FCString::Atod(*Args[7]));
                    if (Body && Body->IsJoltBody()) bSuccess = Body->SetBodyVelocity(V, W, true, Error);
                    else { Mesh->SetPhysicsLinearVelocity(V); Mesh->SetPhysicsAngularVelocityInRadians(W); }
                }
            }
            else if (Args[1] == TEXT("state")) bSuccess = true;
            else Error = TEXT("Unknown operation.");
            Report->SetStringField(TEXT("receiver"), Receiver->GetPathName());
            Report->SetBoolField(TEXT("jolt"), Body && Body->IsJoltBody());
            Report->SetBoolField(TEXT("chaos_simulating"), Mesh->IsSimulatingPhysics());
            Report->SetNumberField(TEXT("collision_enabled"), static_cast<int32>(Mesh->GetCollisionEnabled()));
            Report->SetStringField(TEXT("component_transform"), Mesh->GetComponentTransform().ToString());
            Report->SetStringField(TEXT("body_error"), Body ? Body->GetLastError() : FString());
            TArray<TSharedPtr<FJsonValue>> Materials;
            for (int32 Slot = 0; Slot < Mesh->GetNumMaterials(); ++Slot)
                Materials.Add(MakeShared<FJsonValueString>(GetPathNameSafe(Mesh->GetMaterial(Slot))));
            Report->SetArrayField(TEXT("materials"), Materials);
        }
        Report->SetBoolField(TEXT("success"), bSuccess);
        Report->SetStringField(TEXT("error"), Error);
        FString Json;
        FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Json));
        const FString Directory = FPaths::ProjectSavedDir() / TEXT("Diagnostics/BloodVisual-20260910");
        IFileManager::Get().MakeDirectory(*Directory, true);
        FFileHelper::SaveStringToFile(Json, *(Directory / TEXT("body-state.json")));
        UE_LOG(LogTemp, Display, TEXT("Blood visual body: %s"), *Json);
    }));
namespace
{
constexpr const TCHAR* BrushPath = TEXT("/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle.M_BloodBrush_Circle");
constexpr const TCHAR* FallbackPath = TEXT("/Game/Prophecy/BloodTexturePainting/M_BloodPaint_RuntimeTest.M_BloodPaint_RuntimeTest");
constexpr const TCHAR* ManagerClassPath = TEXT("/Game/Prophecy/BloodTexturePainting/BP_BloodPaintManager.BP_BloodPaintManager_C");
constexpr const TCHAR* CubePath = TEXT("/Engine/BasicShapes/Cube.Cube");
constexpr int32 Resolution = 256;

bool Fail(const TSharedPtr<FJsonObject>& Report, FString& Error, const FString& Message)
{
    Error = Message;
    Report->SetBoolField(TEXT("success"), false);
    Report->SetStringField(TEXT("error"), Message);
    return false;
}

TArray<TSharedPtr<FJsonValue>> VectorJson(const FVector& V)
{
    return { MakeShared<FJsonValueNumber>(V.X), MakeShared<FJsonValueNumber>(V.Y), MakeShared<FJsonValueNumber>(V.Z) };
}

bool Ready(UWorld& World, TSharedPtr<FJsonObject>& Report, FString& Error, const TCHAR* Kind)
{
    Error.Reset();
    Report = MakeShared<FJsonObject>();
    Report->SetNumberField(TEXT("schema"), 1);
    Report->SetStringField(TEXT("fixture"), Kind);
    Report->SetBoolField(TEXT("success"), false);
    Report->SetBoolField(TEXT("asset_saves_requested"), false);
    Report->SetBoolField(TEXT("source_asset_usage_changes_requested"), false);
    Report->SetBoolField(TEXT("existing_shader_preparation_requested"), true);
    Report->SetBoolField(TEXT("rasterized_surface_validated"), false);
    Report->SetStringField(TEXT("scope"), TEXT("Supplied receiver identity, existing paint UV acceptance, real-RHI render-target pixels and scoped material restoration. No screenshot, motion-attachment, Niagara producer, ISM or performance claim."));
    if (!IsInGameThread()) return Fail(Report, Error, TEXT("Blood fixture must run on the game thread."));
    Report->SetStringField(TEXT("world"), World.GetPathName());
    Report->SetBoolField(TEXT("can_ever_render"), FApp::CanEverRender());
    if (!FApp::CanEverRender()) return Fail(Report, Error, TEXT("Blood pixel validation requires a real RHI. NullRHI/server/non-rendering commandlets cannot draw the manager's canvas stamps."));
    if (World.bIsTearingDown || (World.WorldType != EWorldType::Game && World.WorldType != EWorldType::PIE))
        return Fail(Report, Error, TEXT("Blood fixture requires a live Game or PIE world."));
    return true;
}

class FScopedPaint final
{
public:
    FScopedPaint(UMeshComponent& InMesh, const TSharedPtr<FJsonObject>& InReport) : Mesh(InMesh), Report(InReport)
    {
        OriginalOverrides = Mesh.OverrideMaterials;
        for (int32 Slot = 0; Slot < Mesh.GetNumMaterials(); ++Slot) OriginalMaterials.Add(Mesh.GetMaterial(Slot));
    }
    ~FScopedPaint() { Report->SetBoolField(TEXT("material_restored"), Cleanup()); }
    bool Cleanup()
    {
        if (bCleaned) return bRestored;
        bCleaned = true;
        if (Manager)
        {
            Manager->ClearRuntimePaintState(true);
            Manager->Destroy();
            Manager = nullptr;
        }
        if (bPaintAttempted)
        {
            // Use public APIs: direct writes to OverrideMaterials are unsafe for render-thread/GC ownership.
            Mesh.EmptyOverrideMaterials();
            for (int32 Slot = 0; Slot < OriginalOverrides.Num(); ++Slot)
                if (OriginalOverrides[Slot]) Mesh.SetMaterial(Slot, OriginalOverrides[Slot]);
        }
        bRestored = Mesh.GetNumMaterials() == OriginalMaterials.Num();
        for (int32 Slot = 0; Slot < OriginalMaterials.Num(); ++Slot)
            bRestored &= Mesh.GetMaterial(Slot) == OriginalMaterials[Slot];
        return bRestored;
    }
    UMeshComponent& Mesh;
    AProphecyBloodTexturePaintManager* Manager = nullptr;
    TArray<UMaterialInterface*> OriginalMaterials;
    TArray<TStrongObjectPtr<UMaterial>> TransientTemplates;
    bool bPaintAttempted = false;
private:
    TSharedPtr<FJsonObject> Report;
    TArray<TObjectPtr<UMaterialInterface>> OriginalOverrides;
    bool bCleaned = false;
    bool bRestored = false;
};

UMaterialInterface* FindPair(const AProphecyBloodTexturePaintManager* Manager, UMaterialInterface* Original)
{
    if (Manager)
        for (const FProphecyBloodMaterialPair& Pair : Manager->BloodEnabledMaterialPairs)
            if (Pair.CleanMaterial == Original && Pair.BloodMaterial) return Pair.BloodMaterial;
    return nullptr;
}

TSharedPtr<FJsonObject> ShaderResourceState(const FMaterialResource* Resource)
{
    auto State = MakeShared<FJsonObject>();
    State->SetBoolField(TEXT("present"), Resource != nullptr);
    if (Resource)
    {
        State->SetNumberField(TEXT("shader_platform"), static_cast<uint32>(Resource->GetShaderPlatform()));
        State->SetNumberField(TEXT("feature_level"), static_cast<uint8>(Resource->GetFeatureLevel()));
        State->SetNumberField(TEXT("quality_level"), static_cast<uint8>(Resource->GetQualityLevel()));
        State->SetStringField(TEXT("owner"), GetPathNameSafe(Resource->GetMaterialInterface()));
        State->SetBoolField(TEXT("shader_map_present"), Resource->GetGameThreadShaderMap() != nullptr);
        State->SetBoolField(TEXT("shader_map_complete"), Resource->IsGameThreadShaderMapComplete());
#if WITH_EDITOR
        State->SetBoolField(TEXT("caching_shaders"), Resource->IsCachingShaders());
        TArray<TSharedPtr<FJsonValue>> Errors;
        for (const FString& CompileError : Resource->GetCompileErrors()) Errors.Add(MakeShared<FJsonValueString>(CompileError));
        State->SetArrayField(TEXT("compile_errors"), Errors);
#endif
    }
    return State;
}

bool PrepareMaterial(UMaterialInterface& Material, UWorld& World, const TSharedPtr<FJsonObject>& Report,
    const FString& Key, FString& Error)
{
    const EShaderPlatform WorldShaderPlatform = GetFeatureLevelShaderPlatform(World.GetFeatureLevel());
    FMaterialResource* Resource = Material.GetMaterialResource(WorldShaderPlatform);
    auto State = MakeShared<FJsonObject>();
    State->SetStringField(TEXT("material"), Material.GetPathName());
    State->SetNumberField(TEXT("world_feature_level"), static_cast<uint8>(World.GetFeatureLevel()));
    State->SetNumberField(TEXT("maximum_rhi_feature_level"), static_cast<uint8>(GMaxRHIFeatureLevel));
    State->SetNumberField(TEXT("requested_shader_platform"), static_cast<uint32>(WorldShaderPlatform));
    State->SetObjectField(TEXT("before_preparation"), ShaderResourceState(Resource));
    State->SetBoolField(TEXT("material_cache_requested"), false);
    State->SetBoolField(TEXT("exact_resource_cache_requested"), false);
#if WITH_EDITOR
    if (Resource) Resource->FinishCompilation(); // Also completes pending asynchronous DDC/cache work.
    State->SetObjectField(TEXT("after_pending_compilation"), ShaderResourceState(Resource));
    if (!Resource)
    {
        // Let the material create its normal rendering resources before targeting this world's resource.
        State->SetBoolField(TEXT("material_cache_requested"), true);
        Material.CacheShaders(EMaterialShaderPrecompileMode::Synchronous);
        Resource = Material.GetMaterialResource(WorldShaderPlatform);
        if (Resource) Resource->FinishCompilation();
    }
    if (Resource && (!Resource->GetGameThreadShaderMap() || !Resource->IsGameThreadShaderMapComplete()))
    {
        // Cache only an incomplete resource. Re-caching a ready resource can discard its current map
        // while UE resolves DDC work again. The resource already carries its shader platform in 5.7.
        State->SetBoolField(TEXT("exact_resource_cache_requested"), true);
        State->SetBoolField(TEXT("exact_resource_cache_return"), Resource->CacheShaders(EMaterialShaderPrecompileMode::Synchronous));
        State->SetObjectField(TEXT("after_exact_resource_cache"), ShaderResourceState(Resource));
        Resource->FinishCompilation();
    }
#endif
    State->SetObjectField(TEXT("after_preparation"), ShaderResourceState(Resource));
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
        return Fail(Report, Error, FString::Printf(TEXT("Material %s has no complete shader map for the fixture world; see %s diagnostics."), *Material.GetPathName(), *Key));
    return true;
}

bool Configure(FScopedPaint& Scope, UWorld& World, bool bSkinned, const TSharedPtr<FJsonObject>& Report, FString& Error)
{
    UMaterialInterface* Brush = LoadObject<UMaterialInterface>(nullptr, BrushPath);
    UMaterialInterface* Fallback = LoadObject<UMaterialInterface>(nullptr, FallbackPath);
    if (!Brush || !Fallback) return Fail(Report, Error, TEXT("Existing blood brush or explicit runtime-test fallback material is missing."));
    // UE can defer shader jobs until a material is used. Submit the existing material's remaining
    // shaders synchronously, without regenerating its ID or editing its graph/usage flags.
    if (!PrepareMaterial(*Brush, World, Report, TEXT("brush_shader"), Error)) return false;

    // Read existing authoring mappings; changing these transient actor properties never changes the CDO.
    const UClass* MappingClass = LoadClass<AProphecyBloodTexturePaintManager>(nullptr, ManagerClassPath);
    const AProphecyBloodTexturePaintManager* MappingDefaults = MappingClass
        ? Cast<AProphecyBloodTexturePaintManager>(MappingClass->GetDefaultObject()) : nullptr;
    TArray<FProphecyBloodMaterialPair> Pairs;
    TArray<TSharedPtr<FJsonValue>> Materials;
    bool bAnyFallback = false;
    for (int32 Slot = 0; Slot < Scope.OriginalMaterials.Num(); ++Slot)
    {
        UMaterialInterface* Original = Scope.OriginalMaterials[Slot];
        UMaterialInterface* Selected = nullptr;
        FString MappingSource;
        for (TActorIterator<AProphecyBloodTexturePaintManager> It(&World); It && !Selected; ++It)
        {
            Selected = FindPair(*It, Original);
            if (Selected) MappingSource = It->GetPathName();
        }
        if (!Selected)
        {
            Selected = FindPair(MappingDefaults, Original);
            if (Selected) MappingSource = ManagerClassPath;
        }
        const bool bFallback = Selected == nullptr;
        if (bFallback) { Selected = Fallback; MappingSource = TEXT("explicit_fixture_fallback"); bAnyFallback = true; }
        UMaterial* Base = Selected->GetMaterial();
        bool bTransientSkeletalTemplate = false;
#if WITH_EDITOR
        if (bSkinned && bFallback && Base && !Base->GetUsageByFlag(MATUSAGE_SkeletalMesh))
        {
            FBoolProperty* UsageProperty = FindFProperty<FBoolProperty>(UMaterial::StaticClass(), GET_MEMBER_NAME_CHECKED(UMaterial, bUsedWithSkeletalMesh));
            if (!UsageProperty) return Fail(Report, Error, TEXT("UMaterial skeletal usage property is unavailable for the transient fixture copy."));
            const FGuid SourceStateId = Base->StateId;
            const bool bSourceSkeletalUsage = Base->bUsedWithSkeletalMesh;
            // The diagnostic fallback was authored for static meshes. Compile a transient copy
            // for skeletal use; never change or save its source asset or the character materials.
            UMaterial* Copy = DuplicateObject<UMaterial>(Base, GetTransientPackage());
            if (!Copy || Copy == Base || Copy->GetOuter() != GetTransientPackage())
                return Fail(Report, Error, TEXT("Could not create an isolated transient blood template."));
            Copy->SetFlags(RF_Transient);
            Copy->ClearFlags(RF_Public | RF_Standalone);
            Scope.TransientTemplates.Emplace(Copy);
            // SetMaterialUsage deliberately refuses automatic changes in -game, even in an editor
            // binary. Invoke the native property-change lifecycle only on the isolated copy: this
            // cancels old compilation and recreates resources for the changed usage permutation.
            FMaterialUpdateContext Update(FMaterialUpdateContext::EOptions::SyncWithRenderingThread);
            Update.AddMaterial(Copy);
            Copy->bUsedWithSkeletalMesh = true;
            FPropertyChangedEvent UsageChanged(UsageProperty, EPropertyChangeType::ValueSet);
            Copy->PostEditChangeProperty(UsageChanged);
            auto Preparation = MakeShared<FJsonObject>();
            Preparation->SetStringField(TEXT("source_material"), Base->GetPathName());
            Preparation->SetStringField(TEXT("transient_copy"), Copy->GetPathName());
            Preparation->SetStringField(TEXT("lifecycle"), TEXT("PostEditChangeProperty:bUsedWithSkeletalMesh:ValueSet"));
            Preparation->SetBoolField(TEXT("source_usage_and_state_id_preserved"), Base->StateId == SourceStateId && Base->bUsedWithSkeletalMesh == bSourceSkeletalUsage);
            Preparation->SetBoolField(TEXT("copy_skeletal_usage"), Copy->bUsedWithSkeletalMesh);
            Report->SetObjectField(FString::Printf(TEXT("transient_template_preparation_%d"), Slot), Preparation);
            if (!Preparation->GetBoolField(TEXT("source_usage_and_state_id_preserved")))
                return Fail(Report, Error, TEXT("Transient template preparation unexpectedly changed the source material's usage or state ID."));
            Selected = Base = Copy;
            bTransientSkeletalTemplate = true;
        }
#endif
        if (!Base || !PrepareMaterial(*Selected, World, Report, FString::Printf(TEXT("template_shader_%d"), Slot), Error)) return false;
        if (bSkinned && !Base->GetUsageByFlag(MATUSAGE_SkeletalMesh))
            return Fail(Report, Error, FString::Printf(TEXT("Blood template %s lacks existing SkeletalMesh material usage; this fixture will not mutate usage or compile the asset."), *Selected->GetPathName()));
        UTexture* DefaultMask = nullptr;
        if (!Selected->GetTextureParameterValue(FHashedMaterialParameterInfo(TEXT("BloodMaskRT")), DefaultMask))
            return Fail(Report, Error, FString::Printf(TEXT("Blood template %s does not expose BloodMaskRT."), *Selected->GetPathName()));
        FProphecyBloodMaterialPair Pair;
        Pair.CleanMaterial = Original;
        Pair.BloodMaterial = Selected;
        Pairs.Add(Pair);
        auto Row = MakeShared<FJsonObject>();
        Row->SetNumberField(TEXT("slot"), Slot);
        Row->SetStringField(TEXT("original_material"), GetPathNameSafe(Original));
        Row->SetStringField(TEXT("blood_template"), Selected->GetPathName());
        Row->SetStringField(TEXT("mapping_source"), MappingSource);
        Row->SetBoolField(TEXT("fixture_fallback"), bFallback);
        Row->SetBoolField(TEXT("transient_skeletal_usage_copy"), bTransientSkeletalTemplate);
        Materials.Add(MakeShared<FJsonValueObject>(Row));
    }
    if (Pairs.IsEmpty()) return Fail(Report, Error, TEXT("Receiver has no material slots."));
    Report->SetArrayField(TEXT("material_mappings"), Materials);
    Report->SetBoolField(TEXT("uses_fixture_fallback"), bAnyFallback);
    Report->SetBoolField(TEXT("authored_appearance_preservation_validated"), false);
    Report->SetStringField(TEXT("brush_asset"), Brush->GetPathName());

    FActorSpawnParameters Spawn;
    Spawn.ObjectFlags |= RF_Transient;
    Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    Scope.Manager = World.SpawnActor<AProphecyBloodTexturePaintManager>(FVector::ZeroVector, FRotator::ZeroRotator, Spawn);
    if (!Scope.Manager) return Fail(Report, Error, TEXT("Could not spawn transient native blood paint manager."));
    AProphecyBloodTexturePaintManager& Manager = *Scope.Manager;
    Manager.SetActorTickEnabled(false);
    Manager.bFlushEveryTick = false;
    Manager.bEditorAutoCreateBloodMaterials = false;
    Manager.bEditorAutoUpdateBloodMaterials = false;
    Manager.bEditorAllowGeneratedMaterialOverwrite = false;
    Manager.bEditorSaveGeneratedBloodMaterials = false;
    Manager.bUseDefaultBloodMaterialTemplateForUnmappedMaterials = false;
    Manager.BloodEnabledMaterialPairs = MoveTemp(Pairs);
    Manager.BrushMaterial = Brush;
    Manager.DefaultBloodMaterialTemplate = nullptr;
    Manager.DefaultRTResolutionSmall = Resolution;
    Manager.DefaultRTResolutionMedium = Resolution;
    Manager.DefaultRTResolutionLarge = Resolution;
    Manager.MaxActivePaintRTs = 1;
    Manager.MaxStampsPerFrame = 1;
    Manager.MaxStampsPerRTPerFrame = 1;
    Manager.PaintUVChannel = 0;
    Manager.bRequirePaintableTag = false;
    Manager.bDebugMode = false;
    Manager.bDebugPrintHits = false;
    Manager.bDebugDrawHitLocations = false;
    Manager.bDebugLogRejectedHits = false;
    Manager.bDebugShowMaskOnPaintedMaterials = false;
    Report->SetStringField(TEXT("manager"), Manager.GetPathName());
    return true;
}

bool PaintAndRead(FScopedPaint& Scope, const FHitResult& Hit, const TSharedPtr<FJsonObject>& Report, FString& Error)
{
    AProphecyBloodTexturePaintManager& Manager = *Scope.Manager;
    Scope.bPaintAttempted = true;
    const bool bAccepted = Manager.TryPaintFromHit(Hit, 5.0f, 1.0f, INDEX_NONE);
    Report->SetBoolField(TEXT("paint_accepted"), bAccepted);
    Report->SetNumberField(TEXT("brush_radius_cm"), 5.0);
    Report->SetNumberField(TEXT("queued_before_flush"), Manager.QueuedStampCount);
    Report->SetNumberField(TEXT("active_paint_states"), Manager.ActivePaintStates);
    Report->SetNumberField(TEXT("unsupported_hits"), Manager.UnsupportedHitCount);
    if (!bAccepted || Manager.QueuedStampCount != 1 || Manager.ActivePaintStates != 1 || Manager.UnsupportedHitCount != 0)
        return Fail(Report, Error, FString::Printf(TEXT("Existing TryPaintFromHit did not accept exactly one stamp: %s"), *Manager.GetDebugStatsString()));

    UTextureRenderTarget2D* RT = Manager.GetFirstPaintRenderTarget();
    int32 PaintedSlot = INDEX_NONE;
    UMaterialInstanceDynamic* PaintedMID = nullptr;
    for (int32 Slot = 0; Slot < Scope.Mesh.GetNumMaterials(); ++Slot)
    {
        UMaterialInstanceDynamic* MID = Cast<UMaterialInstanceDynamic>(Scope.Mesh.GetMaterial(Slot));
        UTexture* Texture = nullptr;
        if (MID && MID != Scope.OriginalMaterials[Slot]
            && MID->GetTextureParameterValue(FHashedMaterialParameterInfo(Manager.BloodMaskTextureParameter), Texture) && Texture == RT)
        {
            if (PaintedSlot != INDEX_NONE) return Fail(Report, Error, TEXT("One stamp unexpectedly installed the same mask on multiple slots."));
            PaintedSlot = Slot;
            PaintedMID = MID;
        }
    }
    if (!RT || !PaintedMID || RT->SizeX != Resolution || RT->SizeY != Resolution)
        return Fail(Report, Error, TEXT("Accepted stamp did not bind the expected per-component 256x256 mask."));
    Report->SetNumberField(TEXT("painted_slot"), PaintedSlot);
    Report->SetStringField(TEXT("painted_mid"), PaintedMID->GetPathName());
    Report->SetStringField(TEXT("render_target"), RT->GetPathName());
    Report->SetNumberField(TEXT("resolution"), Resolution);
    TArray<FColor> Before, After, Persistent;
    if (!UKismetRenderingLibrary::ReadRenderTarget(&Scope.Mesh, RT, Before, false) || Before.Num() != Resolution * Resolution)
        return Fail(Report, Error, TEXT("Real-RHI mask readback before flush failed."));
    int32 BeforeNonBlack = 0;
    for (const FColor& Pixel : Before) if (Pixel.R || Pixel.G || Pixel.B) ++BeforeNonBlack;
    Report->SetNumberField(TEXT("before_nonblack_rgb_pixels"), BeforeNonBlack);
    if (BeforeNonBlack != 0) return Fail(Report, Error, TEXT("New mask was not black before flushing its first stamp."));

    Manager.FlushPendingBloodStamps();
    Report->SetNumberField(TEXT("flushed_stamps"), Manager.StampsFlushedLastFrame);
    Report->SetNumberField(TEXT("queued_after_flush"), Manager.QueuedStampCount);
    Report->SetNumberField(TEXT("deferred_stamps"), Manager.StampsDeferredLastFrame);
    Report->SetNumberField(TEXT("dropped_stamps"), Manager.StampsDroppedLastFrame);
    if (Manager.StampsFlushedLastFrame != 1 || Manager.QueuedStampCount != 0
        || Manager.StampsDeferredLastFrame != 0 || Manager.StampsDroppedLastFrame != 0)
        return Fail(Report, Error, TEXT("The rendered paint flush did not consume exactly one stamp."));
    if (!UKismetRenderingLibrary::ReadRenderTarget(&Scope.Mesh, RT, After, false) || After.Num() != Before.Num())
        return Fail(Report, Error, TEXT("Real-RHI mask readback after flush failed."));
    int32 Changed = 0, NonBlack = 0;
    uint8 MaxRed = 0;
    FIntPoint MinPixel(Resolution, Resolution), MaxPixel(-1, -1);
    for (int32 Index = 0; Index < After.Num(); ++Index)
    {
        const FColor& Pixel = After[Index];
        if (Pixel.R != Before[Index].R || Pixel.G != Before[Index].G || Pixel.B != Before[Index].B) ++Changed;
        if (Pixel.R || Pixel.G || Pixel.B)
        {
            ++NonBlack;
            const FIntPoint XY(Index % Resolution, Index / Resolution);
            MinPixel.X = FMath::Min(MinPixel.X, XY.X); MinPixel.Y = FMath::Min(MinPixel.Y, XY.Y);
            MaxPixel.X = FMath::Max(MaxPixel.X, XY.X); MaxPixel.Y = FMath::Max(MaxPixel.Y, XY.Y);
        }
        MaxRed = FMath::Max(MaxRed, Pixel.R);
    }
    Report->SetNumberField(TEXT("changed_rgb_pixels"), Changed);
    Report->SetNumberField(TEXT("after_nonblack_rgb_pixels"), NonBlack);
    Report->SetNumberField(TEXT("maximum_red"), MaxRed);
    Report->SetArrayField(TEXT("paint_pixel_bounds"), { MakeShared<FJsonValueNumber>(MinPixel.X), MakeShared<FJsonValueNumber>(MinPixel.Y),
        MakeShared<FJsonValueNumber>(MaxPixel.X), MakeShared<FJsonValueNumber>(MaxPixel.Y) });
    if (Changed <= 0 || NonBlack <= 0 || NonBlack >= After.Num() || MaxRed == 0)
        return Fail(Report, Error, TEXT("The queued hit did not produce a localized nonblack RGB mask stamp."));
    Manager.FlushPendingBloodStamps();
    if (!UKismetRenderingLibrary::ReadRenderTarget(&Scope.Mesh, RT, Persistent, false) || Persistent != After)
        return Fail(Report, Error, TEXT("An empty flush changed or lost the completed mask."));
    Report->SetBoolField(TEXT("empty_flush_preserves_pixels"), true);
    Report->SetBoolField(TEXT("material_restored"), Scope.Cleanup());
    if (!Report->GetBoolField(TEXT("material_restored"))) return Fail(Report, Error, TEXT("Scoped fixture failed to restore original material identities."));
    Report->SetBoolField(TEXT("success"), true);
    return true;
}
}

bool ValidateCharacterHit(UWorld& World, USkeletalMeshComponent& PhysicalMesh, const FHitResult& Hit,
    TSharedPtr<FJsonObject>& OutReport, FString& OutError)
{
    if (!Ready(World, OutReport, OutError, TEXT("live_jolt_character_blood_mask"))) return false;
    if (PhysicalMesh.GetWorld() != &World || !PhysicalMesh.IsRegistered() || !PhysicalMesh.GetSkeletalMeshAsset()
        || Hit.GetComponent() != &PhysicalMesh || Hit.GetActor() != PhysicalMesh.GetOwner() || !Hit.bBlockingHit
        || Hit.BoneName.IsNone() || PhysicalMesh.GetBoneIndex(Hit.BoneName) == INDEX_NONE || Hit.FaceIndex != INDEX_NONE
        || Hit.Location.ContainsNaN() || Hit.ImpactPoint.ContainsNaN() || Hit.ImpactNormal.ContainsNaN() || Hit.ImpactNormal.IsNearlyZero())
        return Fail(OutReport, OutError, TEXT("Character fixture requires a valid blocking hit on the supplied live PhysicalMesh, matching actor and bone, finite point/normal, and no fabricated UE face index."));
    if (PhysicalMesh.IsAnySimulatingPhysics())
        return Fail(OutReport, OutError, TEXT("Character paint receiver still has Chaos simulation enabled; supply the completed Jolt PhysicalMesh."));
    OutReport->SetStringField(TEXT("component"), PhysicalMesh.GetPathName());
    OutReport->SetStringField(TEXT("actor"), GetPathNameSafe(Hit.GetActor()));
    OutReport->SetStringField(TEXT("skeletal_mesh"), GetPathNameSafe(PhysicalMesh.GetSkeletalMeshAsset()));
    OutReport->SetStringField(TEXT("bone"), Hit.BoneName.ToString());
    OutReport->SetNumberField(TEXT("face_index"), Hit.FaceIndex);
    OutReport->SetArrayField(TEXT("impact_point_cm"), VectorJson(Hit.ImpactPoint));
    OutReport->SetArrayField(TEXT("impact_normal"), VectorJson(Hit.ImpactNormal));
    OutReport->SetStringField(TEXT("uv_scope"), TEXT("Existing approximate bone-local reference-triangle fallback, not Jolt triangle collision."));
    FScopedPaint Scope(PhysicalMesh, OutReport);
    if (!Configure(Scope, World, true, OutReport, OutError)) return false;
    return PaintAndRead(Scope, Hit, OutReport, OutError);
}

bool ValidateStaticCube(UWorld& World, const FTransform& CubeToWorld,
    TSharedPtr<FJsonObject>& OutReport, FString& OutError)
{
    if (!Ready(World, OutReport, OutError, TEXT("retained_ue_static_cube_blood_mask"))) return false;
    if (CubeToWorld.ContainsNaN() || !CubeToWorld.GetRotation().IsNormalized() || CubeToWorld.GetScale3D().GetMin() <= 0.0)
        return Fail(OutReport, OutError, TEXT("Static cube placement must be finite with normalized rotation and positive scale."));
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, CubePath);
    if (!Cube) return Fail(OutReport, OutError, TEXT("Existing engine cube mesh is missing."));
    FActorSpawnParameters Spawn;
    Spawn.ObjectFlags |= RF_Transient;
    Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AStaticMeshActor* Actor = World.SpawnActor<AStaticMeshActor>(FVector::ZeroVector, FRotator::ZeroRotator, Spawn);
    if (!Actor) return Fail(OutReport, OutError, TEXT("Could not spawn transient static cube receiver."));
    struct FActorCleanup { AActor* Actor; ~FActorCleanup() { if (Actor) Actor->Destroy(); } } Cleanup{Actor};
    UStaticMeshComponent* Mesh = Actor->GetStaticMeshComponent();
    Mesh->SetMobility(EComponentMobility::Movable);
    Mesh->SetStaticMesh(Cube);
    Actor->SetActorTransform(CubeToWorld, false, nullptr, ETeleportType::TeleportPhysics);
    Mesh->SetCollisionProfileName(TEXT("BlockAll"));
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    FCollisionQueryParams Query(SCENE_QUERY_STAT(ProphecyJoltBloodFixture), true);
    Query.bReturnFaceIndex = true;
    FHitResult Hit;
    const FVector Start = CubeToWorld.TransformPosition(FVector(-150.0, 0.0, 0.0));
    const FVector End = CubeToWorld.TransformPosition(FVector(150.0, 0.0, 0.0));
    if (!World.LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Query) || Hit.GetComponent() != Mesh || Hit.FaceIndex < 0)
        return Fail(OutReport, OutError, TEXT("Complex UE trace did not hit the transient cube with a source face; choose a clear fixture placement."));
    FVector2D UV;
    if (!UGameplayStatics::FindCollisionUV(Hit, 0, UV) || UV.ContainsNaN())
        return Fail(OutReport, OutError, TEXT("Cube source collision face did not resolve UV0; check Support UV From Hit Results/cooked collision UV data."));
    OutReport->SetStringField(TEXT("component"), Mesh->GetPathName());
    OutReport->SetStringField(TEXT("mesh_asset"), CubePath);
    OutReport->SetNumberField(TEXT("face_index"), Hit.FaceIndex);
    OutReport->SetArrayField(TEXT("collision_uv"), { MakeShared<FJsonValueNumber>(UV.X), MakeShared<FJsonValueNumber>(UV.Y) });
    OutReport->SetArrayField(TEXT("impact_point_cm"), VectorJson(Hit.ImpactPoint));
    OutReport->SetStringField(TEXT("query_scope"), TEXT("Retained UE complex static geometry query and FindCollisionUV; no Jolt face mapping claim."));
    FScopedPaint Scope(*Mesh, OutReport);
    if (!Configure(Scope, World, false, OutReport, OutError)) return false;
    return PaintAndRead(Scope, Hit, OutReport, OutError);
}
}
