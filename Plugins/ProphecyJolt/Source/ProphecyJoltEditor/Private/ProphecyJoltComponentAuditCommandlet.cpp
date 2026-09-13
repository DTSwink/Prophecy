#include "ProphecyJoltComponentAuditCommandlet.h"

#include "Components/ActorComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/CollisionProfile.h"
#include "Engine/InheritableComponentHandler.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/Actor.h"
#include "HAL/FileManager.h"
#include "Misc/DateTime.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogProphecyJoltComponentAudit, Log, All);

namespace ProphecyJoltComponentAudit
{
using FObject = TSharedRef<FJsonObject>;
using FValues = TArray<TSharedPtr<FJsonValue>>;

constexpr TCHAR TargetPath[] = TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent");

FString Path(const UObject* Object) { return Object ? Object->GetPathName() : TEXT("None"); }
TSharedPtr<FJsonValue> Json(const FObject& Object) { return MakeShared<FJsonValueObject>(Object); }

FValues Strings(const TArray<FString>& Values)
{
    FValues Result;
    for (const FString& Value : Values) Result.Add(MakeShared<FJsonValueString>(Value));
    return Result;
}

bool ActorProperty(const FProperty* Property)
{
    // Deliberately excludes runtime target caches, delegates and object internals.
    static const TSet<FName> Names = {
        TEXT("bManualNNPoseApplication"), TEXT("bAutoPublishManualFollowerSubstepTargets"),
        TEXT("bAutoApplyWorldMagnetization"), TEXT("bAutoInitializeAgentRuntime"),
        TEXT("bAutoEnsureStandaloneNNManager"), TEXT("bShowKinematicDebugMesh"),
        TEXT("bNNInferenceEnabled"), TEXT("bUpperNNHasSword"), TEXT("bEnableAttackFists"),
        TEXT("SimulationMode"), TEXT("HalfSimDriveMethod"), TEXT("PhysicalRootBodyName"),
        TEXT("PhysicalDriveMode"), TEXT("PhysicalDriveSettings"), TEXT("PhysicalDriveStrengthMultiplier"),
        TEXT("bGeneratePhysicalHitEvents"), TEXT("PhysicalPositionSolverIterations"),
        TEXT("PhysicalVelocitySolverIterations"), TEXT("PhysicalProjectionSolverIterations"),
        TEXT("PhysicalAngularLimitDegrees"), TEXT("bEnablePhysicalMassConditioning"),
        TEXT("bDisablePhysicalConstraintMotors"), TEXT("bUpdatePhysicalJointsFromAnimation"),
        TEXT("bWorldMagnetizationEnabled"), TEXT("WorldMagnetizationLinearStrengthScale"),
        TEXT("WorldMagnetizationAngularStrengthScale"), TEXT("BodyMagnetizationSettings"),
        TEXT("bMACDEnabled"), TEXT("AutoPossessPlayer"), TEXT("AutoPossessAI"),
        TEXT("PhysicalFeedbackTolerances")
    };
    if (Names.Contains(Property->GetFName())) return true;
    // Blueprint variable names are authored freely (including spaces). Limit this fallback
    // to properties declared by the one selected Blueprint's ancestor classes.
    if (!Cast<UBlueprintGeneratedClass>(Property->GetOwnerStruct())) return false;
    const FString Name = Property->GetName();
    static const TCHAR* Tokens[] = { TEXT("physical"), TEXT("physics"), TEXT("manual"),
        TEXT("magnet"), TEXT("simulat"), TEXT("half sim"), TEXT("half_sim"), TEXT("halfSim"),
        TEXT("bone"), TEXT("strength"), TEXT("nn"), TEXT("gravity"), TEXT("collision"), TEXT("macd") };
    for (const TCHAR* Token : Tokens) if (Name.Contains(Token, ESearchCase::IgnoreCase)) return true;
    return false;
}

bool ComponentProperty(const FProperty* Property)
{
    static const TSet<FName> Names = {
        TEXT("bAutoActivate"), TEXT("bEditableWhenInherited"), TEXT("Mobility"),
        TEXT("bAbsoluteLocation"), TEXT("bAbsoluteRotation"), TEXT("bAbsoluteScale"),
        TEXT("RelativeLocation"), TEXT("RelativeRotation"), TEXT("RelativeScale3D"),
        TEXT("bVisible"), TEXT("bHiddenInGame"), TEXT("bGenerateOverlapEvents"),
        TEXT("bAlwaysCreatePhysicsState"), TEXT("bMultiBodyOverlap"),
        TEXT("PhysicsAssetOverride"), TEXT("AnimClass"), TEXT("AnimationMode"),
        TEXT("bEnableUpdateRateOptimizations"), TEXT("VisibilityBasedAnimTickOption"),
        TEXT("bUpdateJointsFromAnimation"), TEXT("bBlendPhysics"),
        TEXT("PhysicsTransformUpdateMode"), TEXT("KinematicBonesUpdateType"),
        TEXT("bDeferKinematicBoneUpdate"), TEXT("bDisablePostProcessBlueprint"),
        TEXT("bEnablePerPolyCollision"), TEXT("ForcedLodModel"), TEXT("MinLodModel"),
        TEXT("bComponentUseFixedSkelBounds"), TEXT("StrengthMultiplyer"),
        TEXT("CapsuleHalfHeight"), TEXT("CapsuleRadius")
    };
    return Names.Contains(Property->GetFName());
}

bool BodyProperty(const FProperty* Property)
{
    // These are component BodyInstance defaults, not instantiated PHAT bone bodies.
    static const TSet<FName> Names = {
        TEXT("bSimulatePhysics"), TEXT("bEnableGravity"), TEXT("bAutoWeld"), TEXT("bStartAwake"),
        TEXT("bGenerateWakeEvents"), TEXT("bNotifyRigidBodyCollision"), TEXT("bUseCCD"), TEXT("bUseMACD"),
        TEXT("bOverrideIterationCounts"), TEXT("PositionSolverIterationCount"),
        TEXT("VelocitySolverIterationCount"), TEXT("ProjectionSolverIterationCount"),
        TEXT("bInertiaConditioning"), TEXT("InertiaTensorScale"), TEXT("MassScale"),
        TEXT("bOverrideMass"), TEXT("MassInKgOverride"), TEXT("COMNudge"),
        TEXT("LinearDamping"), TEXT("AngularDamping"), TEXT("PhysMaterialOverride"),
        TEXT("SleepFamily"), TEXT("CustomSleepThresholdMultiplier"),
        TEXT("StabilizationThresholdMultiplier"), TEXT("bUpdateMassWhenScaleChanges"),
        TEXT("bGyroscopicTorqueEnabled"), TEXT("bUpdateKinematicFromSimulation"), TEXT("bOneWayInteraction"),
        TEXT("bOverrideSolverAsyncDeltaTime"), TEXT("SolverAsyncDeltaTime"),
        TEXT("bOverrideMaxAngularVelocity"), TEXT("MaxAngularVelocity"),
        TEXT("bOverrideMaxDepenetrationVelocity"), TEXT("MaxDepenetrationVelocity"),
        TEXT("CollisionProfileName"), TEXT("CollisionEnabled"), TEXT("ObjectType"),
        TEXT("DOFMode"), TEXT("CustomDOFPlaneNormal"),
        TEXT("bLockXTranslation"), TEXT("bLockYTranslation"), TEXT("bLockZTranslation"),
        TEXT("bLockXRotation"), TEXT("bLockYRotation"), TEXT("bLockZRotation"),
        TEXT("bLockTranslation"), TEXT("bLockRotation")
    };
    return Names.Contains(Property->GetFName());
}

FValues Properties(const UStruct* Type, const void* Container, UObject* ExportOwner,
    const FString& SourceLevel, bool (*Select)(const FProperty*), TArray<FString>& Errors)
{
    TArray<const FProperty*> Selected;
    for (TFieldIterator<FProperty> It(Type); It; ++It)
    {
        const FProperty* Property = *It;
        if (!Property->HasAnyPropertyFlags(CPF_Transient | CPF_Deprecated | CPF_DuplicateTransient | CPF_NonPIEDuplicateTransient)
            && Select(Property)) Selected.Add(Property);
    }
    Selected.Sort([](const FProperty& A, const FProperty& B) { return A.GetName() < B.GetName(); });
    FValues Result;
    for (const FProperty* Property : Selected)
    {
        FString Value;
        // Export the value itself: ExportText_InContainer can omit values identical
        // to the implicit zero default (false, zero, null or an empty map).
        Property->ExportTextItem_Direct(Value, Property->ContainerPtrToValuePtr<void>(Container),
            nullptr, ExportOwner, PPF_None);
        FObject Item = MakeShared<FJsonObject>();
        Item->SetStringField(TEXT("name"), Property->GetName());
        Item->SetStringField(TEXT("cppType"), Property->GetCPPType());
        Item->SetStringField(TEXT("propertyClass"), Property->GetClass()->GetName());
        Item->SetStringField(TEXT("declaringType"), Path(Property->GetOwnerStruct()));
        Item->SetStringField(TEXT("sourceLevel"), SourceLevel);
        Item->SetStringField(TEXT("sourceObject"), Path(ExportOwner));
        Item->SetStringField(TEXT("exportText"), Value);
        Result.Add(Json(Item));
    }
    return Result;
}

FObject Component(UActorComponent* Value, const FString& SourceLevel, TArray<FString>& Errors)
{
    FObject Result = MakeShared<FJsonObject>();
    Result->SetStringField(TEXT("sourceLevel"), SourceLevel);
    Result->SetStringField(TEXT("path"), Path(Value));
    if (!Value) return Result;
    Result->SetStringField(TEXT("name"), Value->GetName());
    Result->SetStringField(TEXT("class"), Path(Value->GetClass()));
    Result->SetStringField(TEXT("archetype"), Path(Value->GetArchetype()));
    Result->SetNumberField(TEXT("creationMethod"), static_cast<int32>(Value->CreationMethod));
    Result->SetArrayField(TEXT("selectedProperties"), Properties(Value->GetClass(), Value, Value, SourceLevel, ComponentProperty, Errors));
    if (const USceneComponent* Scene = Cast<USceneComponent>(Value))
    {
        Result->SetStringField(TEXT("relativeTransform"), Scene->GetRelativeTransform().ToString());
        Result->SetStringField(TEXT("relativeScale3D"), Scene->GetRelativeScale3D().ToString());
        Result->SetStringField(TEXT("templateAttachParent"), Path(Scene->GetAttachParent()));
        Result->SetStringField(TEXT("templateAttachSocket"), Scene->GetAttachSocketName().ToString());
    }
    if (UPrimitiveComponent* Primitive = Cast<UPrimitiveComponent>(Value))
    {
        FObject Collision = MakeShared<FJsonObject>();
        Collision->SetStringField(TEXT("profile"), Primitive->GetCollisionProfileName().ToString());
        Collision->SetNumberField(TEXT("enabled"), static_cast<int32>(Primitive->GetCollisionEnabled()));
        Collision->SetNumberField(TEXT("objectType"), static_cast<int32>(Primitive->GetCollisionObjectType()));
        FValues Responses;
        // ECC_MAX includes the deprecated overlap sentinel; response storage has 32 real channels.
        for (int32 Index = 0; Index < static_cast<int32>(ECC_OverlapAll_Deprecated); ++Index)
        {
            FObject Response = MakeShared<FJsonObject>();
            Response->SetNumberField(TEXT("channel"), Index);
            Response->SetStringField(TEXT("configuredChannelName"), UCollisionProfile::Get()->ReturnChannelNameFromContainerIndex(Index).ToString());
            Response->SetNumberField(TEXT("response"), static_cast<int32>(Primitive->GetCollisionResponseToChannel(static_cast<ECollisionChannel>(Index))));
            Responses.Add(Json(Response));
        }
        Collision->SetArrayField(TEXT("responses"), Responses);
        Result->SetObjectField(TEXT("collisionDefaults"), Collision);
        Result->SetArrayField(TEXT("componentBodyInstanceDefaults"), Properties(FBodyInstance::StaticStruct(),
            &Primitive->BodyInstance, Value, SourceLevel + TEXT(".BodyInstance"), BodyProperty, Errors));
    }
    if (const USkeletalMeshComponent* Mesh = Cast<USkeletalMeshComponent>(Value))
    {
        Result->SetStringField(TEXT("skeletalMesh"), Path(Mesh->GetSkeletalMeshAsset()));
        Result->SetStringField(TEXT("resolvedPhysicsAsset"), Path(Mesh->GetPhysicsAsset()));
        // This count is authored asset topology, never a live-body/constraint count.
        if (const UPhysicsAsset* Asset = Mesh->GetPhysicsAsset())
        {
            Result->SetNumberField(TEXT("authoredBodyCount"), Asset->SkeletalBodySetups.Num());
            Result->SetNumberField(TEXT("authoredConstraintCount"), Asset->ConstraintSetup.Num());
        }
    }
    return Result;
}
}

UProphecyJoltComponentAuditCommandlet::UProphecyJoltComponentAuditCommandlet()
{
    IsClient = false;
    IsServer = false;
    IsEditor = true;
    LogToConsole = true;
    ShowErrorCount = true;
}

int32 UProphecyJoltComponentAuditCommandlet::Main(const FString& Params)
{
    using namespace ProphecyJoltComponentAudit;
    FString Output;
    if (!FParse::Value(*Params, TEXT("Output="), Output) || Output.IsEmpty() || FPaths::IsRelative(Output)
        || !FPaths::GetExtension(Output).Equals(TEXT("json"), ESearchCase::IgnoreCase))
    {
        UE_LOG(LogProphecyJoltComponentAudit, Error, TEXT("Require -Output=<absolute .json path>. Scope is fixed to BP_ProphecyManualPoseAgent."));
        return 1;
    }
    FPaths::NormalizeFilename(Output);
    if (IFileManager::Get().FileExists(*Output))
    {
        UE_LOG(LogProphecyJoltComponentAudit, Error, TEXT("Refusing to overwrite report: %s"), *Output);
        return 1;
    }

    TArray<FString> Errors;
    FObject Report = MakeShared<FJsonObject>();
    Report->SetNumberField(TEXT("schemaVersion"), 1);
    Report->SetStringField(TEXT("engineVersion"), FEngineVersion::Current().ToString());
    Report->SetStringField(TEXT("recordedAtUtc"), FDateTime::UtcNow().ToIso8601());
    Report->SetStringField(TEXT("targetBlueprint"), TargetPath);
    Report->SetBoolField(TEXT("assetsSavedByCommandlet"), false);
    Report->SetBoolField(TEXT("constructionScriptsExecutedByCommandlet"), false);
    Report->SetBoolField(TEXT("mapsLoadedOrActorsSpawnedByCommandlet"), false);
    Report->SetBoolField(TEXT("blueprintCompilationRequestedByCommandlet"), false);
    Report->SetArrayField(TEXT("gaps"), Strings({
        TEXT("CDO and template defaults only. No construction scripts, BeginPlay, maps or spawned actors are evaluated."),
        TEXT("Placed overrides, runtime mode/profile history, actual joints/bodies, mass/inertia and controller execution remain unobserved."),
        TEXT("Component BodyInstance defaults are not instantiated PHAT bone-body settings."),
        TEXT("Loading the selected Blueprint and its dependencies can trigger engine PostLoad work and the existing Blueprint ensure; inspect process outcome and log separately."),
        TEXT("Only selected nontransient reflected properties are exported as text; object references are not recursively expanded."),
        TEXT("No asset package is saved. Engine load-time in-memory fixups are not classified as commandlet edits."),
        TEXT("Success within declared scope is not a promise that the enclosing commandlet process completed without unrelated engine errors.")
    }));

    UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, TargetPath);
    UBlueprintGeneratedClass* ChildClass = Blueprint ? Cast<UBlueprintGeneratedClass>(Blueprint->GeneratedClass) : nullptr;
    AActor* Defaults = ChildClass ? Cast<AActor>(ChildClass->GetDefaultObject()) : nullptr;
    if (!Blueprint || !ChildClass || !Defaults)
    {
        Errors.Add(TEXT("Selected Blueprint, generated actor class or CDO could not be loaded. No compilation was requested."));
    }
    else
    {
        Report->SetStringField(TEXT("generatedClass"), Path(ChildClass));
        Report->SetStringField(TEXT("actorCDO"), Path(Defaults));
        Report->SetBoolField(TEXT("blueprintPackageDirtyAfterLoad"), Blueprint->GetOutermost()->IsDirty());
        Report->SetArrayField(TEXT("actorCDOSelectedProperties"), Properties(ChildClass, Defaults, Defaults, TEXT("ChildBlueprintCDO"), ActorProperty, Errors));
        for (const TCHAR* Required : { TEXT("bManualNNPoseApplication"), TEXT("SimulationMode"),
            TEXT("HalfSimDriveMethod"), TEXT("PhysicalDriveMode"), TEXT("BodyMagnetizationSettings") })
        {
            if (!FindFProperty<FProperty>(ChildClass, Required)) Errors.Add(FString(TEXT("Expected actor property is missing: ")) + Required);
        }

        TArray<UActorComponent*> CDOComponents;
        Defaults->GetComponents(CDOComponents);
        CDOComponents.Sort([](const UActorComponent& A, const UActorComponent& B) { return A.GetPathName() < B.GetPathName(); });
        FValues CDOItems;
        for (UActorComponent* Value : CDOComponents) CDOItems.Add(Json(Component(Value, TEXT("ChildBlueprintCDOComponent"), Errors)));
        Report->SetArrayField(TEXT("actorCDOComponents"), CDOItems);

        FValues Hierarchy, Nodes, Overrides;
        for (UClass* Class = ChildClass; Class; Class = Class->GetSuperClass())
        {
            FObject Level = MakeShared<FJsonObject>();
            Level->SetStringField(TEXT("class"), Path(Class));
            Level->SetStringField(TEXT("superClass"), Path(Class->GetSuperClass()));
            UBlueprintGeneratedClass* BPGC = Cast<UBlueprintGeneratedClass>(Class);
            Level->SetBoolField(TEXT("blueprintGenerated"), BPGC != nullptr);
            Hierarchy.Add(Json(Level));
            if (!BPGC) continue;

            if (USimpleConstructionScript* SCS = BPGC->SimpleConstructionScript)
            {
                for (USCS_Node* Node : SCS->GetAllNodes())
                {
                    if (!Node) { Errors.Add(TEXT("Null SCS node in ") + Path(BPGC)); continue; }
                    UActorComponent* Actual = Node->GetActualComponentTemplate(ChildClass);
                    if (!Actual) Errors.Add(TEXT("No effective template for SCS node: ") + Path(Node));
                    FObject Item = MakeShared<FJsonObject>();
                    Item->SetStringField(TEXT("sourceLevel"), BPGC == ChildClass ? TEXT("ChildSCS") : TEXT("InheritedSCS"));
                    Item->SetStringField(TEXT("declaringClass"), Path(BPGC));
                    Item->SetStringField(TEXT("node"), Path(Node));
                    Item->SetStringField(TEXT("variableName"), Node->GetVariableName().ToString());
                    Item->SetStringField(TEXT("variableGuid"), Node->VariableGuid.ToString(EGuidFormats::Digits));
                    Item->SetStringField(TEXT("parentVariable"), Node->ParentComponentOrVariableName.ToString());
                    Item->SetStringField(TEXT("parentOwnerClassName"), Node->ParentComponentOwnerClassName.ToString());
                    Item->SetBoolField(TEXT("parentIsNative"), Node->bIsParentComponentNative);
                    Item->SetStringField(TEXT("attachSocket"), Node->AttachToName.ToString());
                    TArray<FString> Children;
                    for (const USCS_Node* Child : Node->GetChildNodes()) Children.Add(Path(Child));
                    Item->SetArrayField(TEXT("childNodes"), Strings(Children));
                    Item->SetObjectField(TEXT("declaredTemplate"), Component(Node->ComponentTemplate.Get(), TEXT("SCSDeclaredTemplate"), Errors));
                    Item->SetObjectField(TEXT("effectiveTemplateForSelectedClass"), Component(Actual, TEXT("SCSEffectiveTemplateForChildBlueprint"), Errors));
                    Item->SetBoolField(TEXT("hasEffectiveOverride"), Actual != Node->ComponentTemplate.Get());
                    Nodes.Add(Json(Item));
                }
            }
            // false prevents handler creation. Reading records does not run UCS or create templates.
            if (UInheritableComponentHandler* Handler = BPGC->GetInheritableComponentHandler(false))
            {
                for (auto It = Handler->CreateRecordIterator(); It; ++It)
                {
                    const FComponentOverrideRecord& Record = *It;
                    FObject Item = MakeShared<FJsonObject>();
                    Item->SetStringField(TEXT("sourceLevel"), TEXT("InheritedComponentOverrideRecord"));
                    Item->SetStringField(TEXT("declaringClass"), Path(BPGC));
                    Item->SetStringField(TEXT("componentOwnerClass"), Path(Record.ComponentKey.GetComponentOwner()));
                    Item->SetStringField(TEXT("variableName"), Record.ComponentKey.GetSCSVariableName().ToString());
                    Item->SetStringField(TEXT("associatedGuid"), Record.ComponentKey.GetAssociatedGuid().ToString(EGuidFormats::Digits));
                    Item->SetBoolField(TEXT("isSCSKey"), Record.ComponentKey.IsSCSKey());
                    Item->SetBoolField(TEXT("isUCSKey"), Record.ComponentKey.IsUCSKey());
                    Item->SetObjectField(TEXT("template"), Component(Record.ComponentTemplate.Get(), TEXT("InheritedOverrideTemplate"), Errors));
                    Overrides.Add(Json(Item));
                }
            }
        }
        Report->SetArrayField(TEXT("classHierarchyChildFirst"), Hierarchy);
        Report->SetArrayField(TEXT("scsNodes"), Nodes);
        Report->SetArrayField(TEXT("inheritedComponentOverrideRecords"), Overrides);
    }

    Report->SetArrayField(TEXT("errors"), Strings(Errors));
    Report->SetBoolField(TEXT("successWithinDeclaredScope"), Errors.IsEmpty());
    FString Text;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
    if (!FJsonSerializer::Serialize(Report, Writer))
    {
        UE_LOG(LogProphecyJoltComponentAudit, Error, TEXT("Could not serialize the report."));
        return 1;
    }
    const FString Directory = FPaths::GetPath(Output);
    if ((!IFileManager::Get().DirectoryExists(*Directory) && !IFileManager::Get().MakeDirectory(*Directory, true))
        || !FFileHelper::SaveStringToFile(Text, *Output, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
            &IFileManager::Get(), FILEWRITE_NoReplaceExisting))
    {
        UE_LOG(LogProphecyJoltComponentAudit, Error, TEXT("Cannot create report (no overwrite allowed): %s"), *Output);
        return 1;
    }
    for (const FString& Error : Errors) UE_LOG(LogProphecyJoltComponentAudit, Error, TEXT("%s"), *Error);
    UE_LOG(LogProphecyJoltComponentAudit, Display, TEXT("PROPHECY_JOLT_COMPONENT_AUDIT report=%s errors=%d; CDO/templates only; no asset saves."), *Output, Errors.Num());
    return Errors.IsEmpty() ? 0 : 1;
}
