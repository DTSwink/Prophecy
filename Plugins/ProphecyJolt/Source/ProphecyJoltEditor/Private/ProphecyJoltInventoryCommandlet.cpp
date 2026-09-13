#include "ProphecyJoltInventoryCommandlet.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "Engine/Blueprint.h"
#include "GameFramework/Actor.h"
#include "HAL/FileManager.h"
#include "JsonObjectConverter.h"
#include "K2Node_CallFunction.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
#include "NiagaraEmitter.h"
#include "NiagaraEmitterHandle.h"
#include "NiagaraSystem.h"
#include "PhysicsEngine/AggregateGeom.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Class.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogProphecyJoltInventory, Log, All);

namespace ProphecyJoltInventory
{
using FObject = TSharedRef<FJsonObject>;
using FValue = TSharedPtr<FJsonValue>;
using FValues = TArray<FValue>;
using FWriter = TJsonWriter<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>;

FValue Json(const FObject& Object) { return MakeShared<FJsonValueObject>(Object); }
FValue String(const FString& Value) { return MakeShared<FJsonValueString>(Value); }

// Sort every object key, including nested reflected structs; semantic array order is retained.
void WriteValue(const TSharedRef<FWriter>& Writer, const FValue& Value, const FString* Key = nullptr)
{
    if (!Value.IsValid() || Value->Type == EJson::Null)
    {
        if (Key) Writer->WriteNull(*Key); else Writer->WriteNull();
        return;
    }
    switch (Value->Type)
    {
    case EJson::Object:
    {
        if (Key) Writer->WriteObjectStart(*Key); else Writer->WriteObjectStart();
        const TSharedPtr<FJsonObject> Object = Value->AsObject();
        TArray<FString> Keys;
        Object->Values.GetKeys(Keys);
        Keys.Sort();
        for (const FString& Field : Keys) WriteValue(Writer, Object->Values.FindChecked(Field), &Field);
        Writer->WriteObjectEnd();
        break;
    }
    case EJson::Array:
        if (Key) Writer->WriteArrayStart(*Key); else Writer->WriteArrayStart();
        for (const FValue& Item : Value->AsArray()) WriteValue(Writer, Item);
        Writer->WriteArrayEnd();
        break;
    case EJson::String:
        if (Key) Writer->WriteValue(*Key, Value->AsString()); else Writer->WriteValue(Value->AsString());
        break;
    case EJson::Number:
        if (Key) Writer->WriteValue(*Key, Value->AsNumber()); else Writer->WriteValue(Value->AsNumber());
        break;
    case EJson::Boolean:
        if (Key) Writer->WriteValue(*Key, Value->AsBool()); else Writer->WriteValue(Value->AsBool());
        break;
    default:
        if (Key) Writer->WriteNull(*Key); else Writer->WriteNull();
        break;
    }
}

FString CanonicalJson(const FValue& Value)
{
    FString Text;
    const TSharedRef<FWriter> Writer = TJsonWriterFactory<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>::Create(&Text);
    WriteValue(Writer, Value);
    Writer->Close();
    return Text;
}

FValues Strings(TArray<FString> Values, bool bSort = true)
{
    if (bSort) Values.Sort();
    FValues Result;
    for (const FString& Value : Values) Result.Add(String(Value));
    return Result;
}

bool PhysicsHint(const FString& Text)
{
    static const TCHAR* Words[] = { TEXT("physics"), TEXT("collision"), TEXT("trace"), TEXT("sweep"),
        TEXT("overlap"), TEXT("hit"), TEXT("force"), TEXT("impulse"), TEXT("torque"), TEXT("velocity"),
        TEXT("constraint"), TEXT("ragdoll"), TEXT("simulate"), TEXT("niagara"), TEXT("blood"),
        TEXT("replic"), TEXT("dorman"), TEXT("skeletal"), TEXT("bone"), TEXT("weld"), TEXT("mass"),
        TEXT("gravity"), TEXT("damping"), TEXT("physical"), TEXT("radial"), TEXT("socket") };
    for (const TCHAR* Word : Words) if (Text.Contains(Word, ESearchCase::IgnoreCase)) return true;
    return false;
}

struct FContext
{
    TArray<FString> Errors;
    TArray<FString> Gaps;
    FJsonObjectConverter::CustomExportCallback ExportCallback;

    FContext()
    {
        ExportCallback.BindLambda([this](FProperty* Property, const void* Value) -> FValue
        {
            // Keep object references as references, even for instanced properties. Do not descend into assets.
            if (CastField<FObjectPropertyBase>(Property))
            {
                FString Reference;
                Property->ExportTextItem_Direct(Reference, Value, nullptr, nullptr, PPF_None);
                return String(Reference);
            }
            if (FSetProperty* Set = CastField<FSetProperty>(Property))
            {
                FScriptSetHelper Helper(Set, Value);
                TArray<TPair<FString, FValue>> Sorted;
                for (int32 Index = 0; Index < Helper.GetMaxIndex(); ++Index)
                {
                    if (!Helper.IsValidIndex(Index)) continue;
                    const FValue Item = FJsonObjectConverter::UPropertyToJsonValue(Set->ElementProp,
                        Helper.GetElementPtr(Index), 0, CPF_Transient | CPF_Deprecated, &ExportCallback);
                    if (!Item.IsValid()) Errors.Add(FString::Printf(TEXT("Cannot reflect set element: %s"), *Property->GetPathName()));
                    Sorted.Emplace(CanonicalJson(Item), Item.IsValid() ? Item : MakeShared<FJsonValueNull>());
                }
                Sorted.Sort([](const auto& A, const auto& B) { return A.Key < B.Key; });
                FValues Items;
                for (const auto& Pair : Sorted) Items.Add(Pair.Value);
                return MakeShared<FJsonValueArray>(Items);
            }
            return nullptr;
        });
    }

    FValue Struct(const UStruct* Type, const void* Data, const FString& Where)
    {
        FObject Result = MakeShared<FJsonObject>();
        if (!FJsonObjectConverter::UStructToJsonObject(Type, Data, Result, 0,
            CPF_Transient | CPF_Deprecated, &ExportCallback, EJsonObjectConversionFlags::SkipStandardizeCase))
        {
            Errors.Add(TEXT("Cannot reflect struct: ") + Where);
            return MakeShared<FJsonValueNull>();
        }
        return Json(Result);
    }

    FValue Property(FProperty* Field, const void* Container, const FString& Where)
    {
        const FValue Result = FJsonObjectConverter::UPropertyToJsonValue(Field,
            Field->ContainerPtrToValuePtr<void>(Container), 0, CPF_Transient | CPF_Deprecated, &ExportCallback);
        if (!Result.IsValid()) Errors.Add(TEXT("Cannot reflect property: ") + Where + TEXT(".") + Field->GetName());
        return Result.IsValid() ? Result : MakeShared<FJsonValueNull>();
    }

    FObject NamedProperties(UObject* Object, const TArray<FString>& Names)
    {
        FObject Result = MakeShared<FJsonObject>();
        for (const FString& Name : Names)
        {
            FProperty* Field = Object->GetClass()->FindPropertyByName(FName(*Name));
            if (Field) Result->SetField(Name, Property(Field, Object, Object->GetPathName()));
            else
            {
                Result->SetField(Name, MakeShared<FJsonValueNull>());
                Gaps.Add(TEXT("Property unavailable: ") + Object->GetPathName() + TEXT(".") + Name);
            }
        }
        return Result;
    }
};

FObject PinReference(const UEdGraphPin* Pin)
{
    FObject Result = MakeShared<FJsonObject>();
    Result->SetStringField(TEXT("pinId"), Pin->PinId.ToString());
    Result->SetStringField(TEXT("pinName"), Pin->PinName.ToString());
    const UEdGraphNode* Node = Pin->GetOwningNode();
    Result->SetStringField(TEXT("nodePath"), GetPathNameSafe(Node));
    if (Node) Result->SetStringField(TEXT("nodeGuid"), Node->NodeGuid.ToString());
    return Result;
}

FObject ExportBlueprint(UBlueprint* Blueprint, FContext& Context)
{
    FObject Result = MakeShared<FJsonObject>();
    Result->SetStringField(TEXT("path"), Blueprint->GetPathName());
    Result->SetStringField(TEXT("parentClass"), GetPathNameSafe(Blueprint->ParentClass));
    Result->SetNumberField(TEXT("blueprintType"), static_cast<int32>(Blueprint->BlueprintType));
    Result->SetStringField(TEXT("generatedClass"), GetPathNameSafe(Blueprint->GeneratedClass));
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    if (Graphs.Contains(nullptr)) Context.Errors.Add(TEXT("Null graph returned by GetAllGraphs: ") + Blueprint->GetPathName());
    Graphs.RemoveAll([](const UEdGraph* Graph) { return Graph == nullptr; });
    Graphs.Sort([](const UEdGraph& A, const UEdGraph& B) { return A.GetPathName() < B.GetPathName(); });
    FValues GraphItems;
    for (const UEdGraph* Graph : Graphs)
    {
        FObject GraphItem = MakeShared<FJsonObject>();
        GraphItem->SetStringField(TEXT("path"), Graph->GetPathName());
        GraphItem->SetStringField(TEXT("class"), Graph->GetClass()->GetPathName());
        FValues Nodes;
        // Graph array indices are retained; every node is exported irrespective of keyword classification.
        for (int32 NodeIndex = 0; NodeIndex < Graph->Nodes.Num(); ++NodeIndex)
        {
            UEdGraphNode* Node = Graph->Nodes[NodeIndex];
            if (!Node)
            {
                Context.Errors.Add(FString::Printf(TEXT("Null graph node: %s[%d]"), *Graph->GetPathName(), NodeIndex));
                Nodes.Add(MakeShared<FJsonValueNull>());
                continue;
            }
            FObject Item = MakeShared<FJsonObject>();
            Item->SetNumberField(TEXT("index"), NodeIndex);
            Item->SetStringField(TEXT("path"), Node->GetPathName());
            Item->SetStringField(TEXT("class"), Node->GetClass()->GetPathName());
            Item->SetStringField(TEXT("guid"), Node->NodeGuid.ToString());
            const FString Title = Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString();
            Item->SetStringField(TEXT("title"), Title);
            Item->SetStringField(TEXT("comment"), Node->NodeComment);
            FObject Members = MakeShared<FJsonObject>();
            for (TFieldIterator<FProperty> It(Node->GetClass()); It; ++It)
            {
                const FStructProperty* StructField = CastField<FStructProperty>(*It);
                if (StructField && StructField->Struct->GetName().Contains(TEXT("MemberReference")))
                    Members->SetField(It->GetName(), Context.Property(*It, Node, Node->GetPathName()));
            }
            Item->SetObjectField(TEXT("memberReferences"), Members);
            bool bPhysicsHint = PhysicsHint(Node->GetClass()->GetPathName() + Title + CanonicalJson(Json(Members)));
            if (const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node))
            {
                Item->SetStringField(TEXT("functionName"), Call->GetFunctionName().ToString());
                // Do not resolve functions here: resolution can load or repair references.
                bPhysicsHint |= PhysicsHint(Call->GetFunctionName().ToString());
            }
            FValues Pins;
            for (int32 PinIndex = 0; PinIndex < Node->Pins.Num(); ++PinIndex)
            {
                const UEdGraphPin* Pin = Node->Pins[PinIndex];
                if (!Pin)
                {
                    Context.Errors.Add(FString::Printf(TEXT("Null graph pin: %s[%d]"), *Node->GetPathName(), PinIndex));
                    Pins.Add(MakeShared<FJsonValueNull>());
                    continue;
                }
                FObject PinItem = PinReference(Pin);
                PinItem->SetNumberField(TEXT("index"), PinIndex);
                PinItem->SetNumberField(TEXT("direction"), static_cast<int32>(Pin->Direction));
                PinItem->SetField(TEXT("type"), Context.Struct(FEdGraphPinType::StaticStruct(), &Pin->PinType, Node->GetPathName()));
                PinItem->SetStringField(TEXT("defaultValue"), Pin->DefaultValue);
                PinItem->SetStringField(TEXT("autogeneratedDefaultValue"), Pin->AutogeneratedDefaultValue);
                PinItem->SetStringField(TEXT("defaultObject"), GetPathNameSafe(Pin->DefaultObject));
                PinItem->SetStringField(TEXT("defaultText"), Pin->DefaultTextValue.ToString());
                PinItem->SetBoolField(TEXT("hidden"), Pin->bHidden);
                PinItem->SetBoolField(TEXT("orphaned"), Pin->bOrphanedPin);
                TArray<TPair<FString, FValue>> Links;
                for (const UEdGraphPin* Link : Pin->LinkedTo)
                {
                    if (Link)
                    {
                        const FValue Reference = Json(PinReference(Link));
                        Links.Emplace(CanonicalJson(Reference), Reference);
                    }
                    else Context.Errors.Add(TEXT("Null linked pin: ") + Node->GetPathName() + TEXT(".") + Pin->PinName.ToString());
                }
                Links.Sort([](const auto& A, const auto& B) { return A.Key < B.Key; });
                FValues LinkItems;
                for (const auto& Link : Links) LinkItems.Add(Link.Value);
                PinItem->SetArrayField(TEXT("links"), LinkItems);
                bPhysicsHint |= PhysicsHint(Pin->PinName.ToString() + Pin->DefaultValue);
                Pins.Add(Json(PinItem));
            }
            Item->SetBoolField(TEXT("physicsKeywordHintOnly"), bPhysicsHint);
            Item->SetArrayField(TEXT("pins"), Pins);
            Nodes.Add(Json(Item));
        }
        GraphItem->SetArrayField(TEXT("nodes"), Nodes);
        GraphItems.Add(Json(GraphItem));
    }
    Result->SetArrayField(TEXT("graphs"), GraphItems);

    FObject Replication = MakeShared<FJsonObject>();
    UClass* Class = Blueprint->GeneratedClass;
    UObject* CDO = Class ? Class->GetDefaultObject(false) : nullptr;
    Replication->SetBoolField(TEXT("existingCdoAvailable"), CDO != nullptr);
    if (!CDO) Context.Gaps.Add(TEXT("Generated class or existing CDO unavailable; replication defaults unknown: ") + Blueprint->GetPathName());
    if (AActor* Actor = Cast<AActor>(CDO))
    {
        Replication->SetBoolField(TEXT("actorReplicates"), Actor->GetIsReplicated());
        Replication->SetBoolField(TEXT("replicateMovement"), Actor->IsReplicatingMovement());
        Replication->SetObjectField(TEXT("actorDefaults"), Context.NamedProperties(Actor,
            { TEXT("bAlwaysRelevant"), TEXT("bOnlyRelevantToOwner"), TEXT("bNetUseOwnerRelevancy"),
              TEXT("NetDormancy"), TEXT("NetUpdateFrequency"), TEXT("MinNetUpdateFrequency"), TEXT("NetPriority") }));
    }
    FValues ReplicatedProperties;
    FValues NetFunctions;
    if (Class)
    {
        TArray<FProperty*> Fields;
        for (TFieldIterator<FProperty> It(Class); It; ++It) if (It->HasAnyPropertyFlags(CPF_Net)) Fields.Add(*It);
        Fields.Sort([](const FProperty& A, const FProperty& B) { return A.GetPathName() < B.GetPathName(); });
        for (FProperty* Field : Fields)
        {
            FObject Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("path"), Field->GetPathName());
            Item->SetStringField(TEXT("type"), Field->GetCPPType());
            Item->SetStringField(TEXT("flagsHex"), FString::Printf(TEXT("0x%016llx"), static_cast<unsigned long long>(Field->GetPropertyFlags())));
            Item->SetStringField(TEXT("repNotifyFunction"), Field->RepNotifyFunc.ToString());
            if (CDO) Item->SetField(TEXT("cdoValue"), Context.Property(Field, CDO, CDO->GetPathName()));
            else Item->SetField(TEXT("cdoValue"), MakeShared<FJsonValueNull>());
            ReplicatedProperties.Add(Json(Item));
        }
        TArray<UFunction*> Functions;
        for (TFieldIterator<UFunction> It(Class); It; ++It) if (It->HasAnyFunctionFlags(FUNC_Net)) Functions.Add(*It);
        Functions.Sort([](const UFunction& A, const UFunction& B) { return A.GetPathName() < B.GetPathName(); });
        for (const UFunction* Function : Functions)
        {
            FObject Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("path"), Function->GetPathName());
            Item->SetStringField(TEXT("flagsHex"), FString::Printf(TEXT("0x%08x"), static_cast<uint32>(Function->FunctionFlags)));
            Item->SetBoolField(TEXT("server"), Function->HasAnyFunctionFlags(FUNC_NetServer));
            Item->SetBoolField(TEXT("client"), Function->HasAnyFunctionFlags(FUNC_NetClient));
            Item->SetBoolField(TEXT("multicast"), Function->HasAnyFunctionFlags(FUNC_NetMulticast));
            Item->SetBoolField(TEXT("reliable"), Function->HasAnyFunctionFlags(FUNC_NetReliable));
            NetFunctions.Add(Json(Item));
        }
    }
    Replication->SetArrayField(TEXT("properties"), ReplicatedProperties);
    Replication->SetArrayField(TEXT("functions"), NetFunctions);
    Result->SetObjectField(TEXT("replication"), Replication);
    return Result;
}

FObject ExportPhysicsAsset(UPhysicsAsset* Asset, FContext& Context)
{
    FObject Result = MakeShared<FJsonObject>();
    Result->SetStringField(TEXT("path"), Asset->GetPathName());
    Result->SetObjectField(TEXT("assetSettings"), Context.NamedProperties(Asset,
        { TEXT("PreviewSkeletalMesh"), TEXT("PhysicalAnimationProfiles"), TEXT("ConstraintProfiles"),
          TEXT("BoundsBodies"), TEXT("SolverSettings"), TEXT("SolverType"), TEXT("bNotForDedicatedServer") }));
    FValues Bodies;
    for (int32 Index = 0; Index < Asset->SkeletalBodySetups.Num(); ++Index)
    {
        USkeletalBodySetup* Body = Asset->SkeletalBodySetups[Index];
        if (!Body)
        {
            Context.Errors.Add(FString::Printf(TEXT("Null body setup: %s[%d]"), *Asset->GetPathName(), Index));
            Bodies.Add(MakeShared<FJsonValueNull>());
            continue;
        }
        FObject Item = MakeShared<FJsonObject>();
        Item->SetNumberField(TEXT("index"), Index);
        Item->SetStringField(TEXT("path"), Body->GetPathName());
        Item->SetStringField(TEXT("boneName"), Body->BoneName.ToString());
        Item->SetField(TEXT("aggregateGeometry"), Context.Struct(FKAggregateGeom::StaticStruct(), &Body->AggGeom, Body->GetPathName()));
        Item->SetField(TEXT("defaultBodyInstance"), Context.Struct(FBodyInstance::StaticStruct(), &Body->DefaultInstance, Body->GetPathName()));
        Item->SetObjectField(TEXT("bodySettings"), Context.NamedProperties(Body,
            { TEXT("PhysicsType"), TEXT("CollisionTraceFlag"), TEXT("PhysMaterial"), TEXT("bConsiderForBounds"),
              TEXT("bDoubleSidedGeometry"), TEXT("bGenerateMirroredCollision"), TEXT("bGenerateNonMirroredCollision"),
              TEXT("bSkipScaleFromAnimation") }));
        FValues Profiles;
        for (const FPhysicalAnimationProfile& Profile : Body->GetPhysicalAnimationProfiles())
            Profiles.Add(Context.Struct(FPhysicalAnimationProfile::StaticStruct(), &Profile, Body->GetPathName()));
        Item->SetArrayField(TEXT("physicalAnimationProfiles"), Profiles);
        Bodies.Add(Json(Item));
    }
    Result->SetArrayField(TEXT("bodies"), Bodies);
    FValues Constraints;
    for (int32 Index = 0; Index < Asset->ConstraintSetup.Num(); ++Index)
    {
        UPhysicsConstraintTemplate* Constraint = Asset->ConstraintSetup[Index];
        if (!Constraint)
        {
            Context.Errors.Add(FString::Printf(TEXT("Null constraint: %s[%d]"), *Asset->GetPathName(), Index));
            Constraints.Add(MakeShared<FJsonValueNull>());
            continue;
        }
        FObject Item = MakeShared<FJsonObject>();
        Item->SetNumberField(TEXT("index"), Index);
        Item->SetStringField(TEXT("path"), Constraint->GetPathName());
        Item->SetField(TEXT("defaultInstance"), Context.Struct(FConstraintInstance::StaticStruct(), &Constraint->DefaultInstance, Constraint->GetPathName()));
        FValues Profiles;
        for (const FPhysicsConstraintProfileHandle& Profile : Constraint->ProfileHandles)
            Profiles.Add(Context.Struct(FPhysicsConstraintProfileHandle::StaticStruct(), &Profile, Constraint->GetPathName()));
        Item->SetArrayField(TEXT("profiles"), Profiles);
        Constraints.Add(Json(Item));
    }
    Result->SetArrayField(TEXT("constraints"), Constraints);
    TArray<FRigidBodyIndexPair> PairKeys;
    Asset->CollisionDisableTable.GetKeys(PairKeys);
    PairKeys.Sort([](const FRigidBodyIndexPair& A, const FRigidBodyIndexPair& B)
    {
        return A.Indices[0] == B.Indices[0] ? A.Indices[1] < B.Indices[1] : A.Indices[0] < B.Indices[0];
    });
    FValues Pairs;
    for (const FRigidBodyIndexPair& Pair : PairKeys)
    {
        FObject Item = MakeShared<FJsonObject>();
        Item->SetNumberField(TEXT("bodyA"), Pair.Indices[0]);
        Item->SetNumberField(TEXT("bodyB"), Pair.Indices[1]);
        Item->SetBoolField(TEXT("storedValue"), Asset->CollisionDisableTable.FindChecked(Pair));
        if (!Asset->SkeletalBodySetups.IsValidIndex(Pair.Indices[0]) || !Asset->SkeletalBodySetups.IsValidIndex(Pair.Indices[1]))
            Context.Errors.Add(TEXT("Collision-disable pair has invalid body index: ") + Asset->GetPathName());
        Pairs.Add(Json(Item));
    }
    Result->SetArrayField(TEXT("collisionDisableTable"), Pairs);
    return Result;
}

FObject ExportNiagara(UNiagaraSystem* System, FContext& Context)
{
    FObject Result = MakeShared<FJsonObject>();
    Result->SetStringField(TEXT("path"), System->GetPathName());
    FValues Emitters;
    const TArray<FNiagaraEmitterHandle>& Handles = System->GetEmitterHandles();
    for (int32 Index = 0; Index < Handles.Num(); ++Index)
    {
        const FNiagaraEmitterHandle& Handle = Handles[Index];
        FObject Item = MakeShared<FJsonObject>();
        Item->SetNumberField(TEXT("index"), Index);
        Item->SetStringField(TEXT("id"), Handle.GetId().ToString());
        Item->SetStringField(TEXT("name"), Handle.GetName().ToString());
        Item->SetBoolField(TEXT("enabled"), Handle.GetIsEnabled());
        Item->SetBoolField(TEXT("valid"), Handle.IsValid());
        Item->SetNumberField(TEXT("emitterMode"), static_cast<int32>(Handle.GetEmitterMode()));
        if (Handle.GetEmitterMode() == ENiagaraEmitterMode::Standard)
        {
            const FVersionedNiagaraEmitter Instance = Handle.GetInstance();
            Item->SetStringField(TEXT("emitterObject"), GetPathNameSafe(Instance.Emitter));
            Item->SetStringField(TEXT("selectedVersionGuid"), Instance.Version.ToString());
            // This accessor follows the handle's selected version, not the emitter's latest version.
            const FVersionedNiagaraEmitterData* Data = Handle.GetEmitterData();
            if (Data)
            {
                Item->SetNumberField(TEXT("simulationTarget"), static_cast<int32>(Data->SimTarget));
                Item->SetBoolField(TEXT("localSpace"), Data->bLocalSpace);
                Item->SetBoolField(TEXT("deterministic"), Data->bDeterminism);
                Item->SetNumberField(TEXT("randomSeed"), Data->RandomSeed);
                Item->SetNumberField(TEXT("interpolatedSpawnMode"), static_cast<int32>(Data->InterpolatedSpawnMode));
            }
            else Context.Errors.Add(TEXT("Niagara standard emitter version data unavailable: ") + System->GetPathName() + TEXT("/") + Handle.GetName().ToString());
        }
        else Context.Gaps.Add(TEXT("Stateless Niagara emitter internals not inspected: ") + System->GetPathName() + TEXT("/") + Handle.GetName().ToString());
        Emitters.Add(Json(Item));
    }
    Result->SetArrayField(TEXT("emitters"), Emitters);
    return Result;
}

FObject AssetRecord(const FAssetData& Asset)
{
    FObject Result = MakeShared<FJsonObject>();
    Result->SetStringField(TEXT("objectPath"), Asset.GetObjectPathString());
    Result->SetStringField(TEXT("packageName"), Asset.PackageName.ToString());
    Result->SetStringField(TEXT("packagePath"), Asset.PackagePath.ToString());
    Result->SetStringField(TEXT("assetName"), Asset.AssetName.ToString());
    Result->SetStringField(TEXT("classPath"), Asset.AssetClassPath.ToString());
    Result->SetStringField(TEXT("packageFlagsHex"), FString::Printf(TEXT("0x%08x"), Asset.PackageFlags));
    FObject Tags = MakeShared<FJsonObject>();
    Asset.EnumerateTags([&Tags](const auto& Tag) { Tags->SetStringField(Tag.Key.ToString(), Tag.Value.AsString()); });
    Result->SetObjectField(TEXT("tags"), Tags);
    TArray<int32> ChunkIDs;
    for (const int32 Chunk : Asset.GetChunkIDs()) ChunkIDs.Add(Chunk);
    ChunkIDs.Sort();
    FValues Chunks;
    for (const int32 Chunk : ChunkIDs) Chunks.Add(MakeShared<FJsonValueNumber>(Chunk));
    Result->SetArrayField(TEXT("chunkIds"), Chunks);
    return Result;
}
} // namespace ProphecyJoltInventory

UProphecyJoltInventoryCommandlet::UProphecyJoltInventoryCommandlet()
{
    IsClient = false;
    IsServer = false;
    IsEditor = true;
    LogToConsole = true;
    ShowErrorCount = true;
}

int32 UProphecyJoltInventoryCommandlet::Main(const FString& Params)
{
    using namespace ProphecyJoltInventory;
    FString Output;
    if (!FParse::Value(*Params, TEXT("Output="), Output))
        Output = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("JoltMigration/AssetManifest.json"));
    Output = FPaths::ConvertRelativePathToFull(Output);
    FPaths::NormalizeFilename(Output);
    const bool bOverwrite = FParse::Param(*Params, TEXT("Overwrite"));
    if (!FPaths::GetExtension(Output).Equals(TEXT("json"), ESearchCase::IgnoreCase))
    {
        UE_LOG(LogProphecyJoltInventory, Error, TEXT("Output must be a .json report: %s"), *Output);
        return 1;
    }
    if (!bOverwrite && IFileManager::Get().FileExists(*Output))
    {
        UE_LOG(LogProphecyJoltInventory, Error, TEXT("Report exists; use an unused -Output path or explicit -Overwrite: %s"), *Output);
        return 1;
    }

    FContext Context;
    FObject Report = MakeShared<FJsonObject>();
    Report->SetNumberField(TEXT("schemaVersion"), 1);
    Report->SetStringField(TEXT("engineVersion"), FEngineVersion::Current().ToString());
    Report->SetBoolField(TEXT("assetsSavedOrModifiedByExporter"), false);
    Report->SetArrayField(TEXT("coverage"), Strings({
        TEXT("On-disk AssetRegistry metadata; package dependency closure includes hard/soft and game/editor references, across mounted content roots."),
        TEXT("Seeds: exact /Game/mybasic and /Game/testNN packages; recursive /Game/_mygame Blueprint (including subclasses), PhysicsAsset and NiagaraSystem records."),
        TEXT("Only reachable Blueprint, PhysicsAsset and NiagaraSystem asset records are explicitly loaded. Their normal hard-reference loads and PostLoad work remain engine behavior."),
        TEXT("All GetAllGraphs nodes and pins are exported; physicsKeywordHintOnly is a search aid, not a completeness filter."),
        TEXT("PHAT reflected authored aggregate shapes, body defaults, constraint frames/limits/drives, profiles, and nonreflected collision-disable pairs."),
        TEXT("Replication: existing generated CDO actor defaults, CPF_Net properties, and FUNC_Net function flags including inherited members."),
        TEXT("Niagara: emitter handle validity/enabled/mode and selected-version CPU/GPU target, local space, determinism, seed and interpolation mode."),
        TEXT("Stable object-key ordering, sorted registry records/edges/sets; authored graph, pin, body, constraint and emitter array indices are preserved. No timestamp is emitted.") }));
    Context.Gaps = {
        TEXT("AssetRegistry package closure is not a runtime reachability proof. Dynamic string loads, generated assets, config references, searchable-name/management dependencies and missing registry edges are not inferred."),
        TEXT("Map/WorldPartition actor instances, external actor descriptors, level Blueprint graph objects not represented as standalone Blueprint assets, placed component overrides and construction-script effects are not loaded or inspected."),
        TEXT("Blueprint inherited graphs are represented only when their owning Blueprint asset is independently reachable; macro/function library implementation and native C++ behavior require source review."),
        TEXT("Blueprint CDO inventory does not evaluate GetLifetimeReplicatedProps conditions, replication graph/Iris configuration, runtime replication changes or SCS/inheritable component template defaults."),
        TEXT("Reflected struct exports omit transient/deprecated and non-UPROPERTY fields. Cooked collision payloads, level-set grids, ML/skinned shape internals and evaluated mass/inertia/reference-pose transforms are not reconstructed."),
        TEXT("Niagara collision modules and method inputs, data interfaces/export callbacks, parameter bindings, script graphs, overrides, scalability, GPU readback and stateless emitter internals need a separate targeted inspection; absence is never inferred from this report."),
        TEXT("Asset load/PostLoad may reconstruct or dirty in-memory objects. The exporter calls no asset mutation, compilation or package-save API and never persists these in-memory changes.") };

    IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
    Registry.SearchAllAssets(true);
    TSet<FTopLevelAssetPath> SelectedClasses;
    const TArray<FTopLevelAssetPath> Bases = { UBlueprint::StaticClass()->GetClassPathName(),
        UPhysicsAsset::StaticClass()->GetClassPathName(), UNiagaraSystem::StaticClass()->GetClassPathName() };
    Registry.GetDerivedClassNames(Bases, TSet<FTopLevelAssetPath>(), SelectedClasses);
    for (const FTopLevelAssetPath& Base : Bases) SelectedClasses.Add(Base);

    const TArray<FString> Roots = { TEXT("/Game/mybasic"), TEXT("/Game/testNN") };
    Report->SetArrayField(TEXT("rootPackages"), Strings(Roots));
    TSet<FName> SeedPackages;
    for (const FString& Root : Roots)
    {
        TArray<FAssetData> Assets;
        Registry.GetAssetsByPackageName(FName(*Root), Assets, true, false);
        if (Assets.IsEmpty()) Context.Errors.Add(TEXT("Required root package has no on-disk AssetRegistry asset: ") + Root);
        else SeedPackages.Add(FName(*Root));
    }
    TArray<FAssetData> GameAssets;
    Registry.GetAssetsByPath(FName(TEXT("/Game/_mygame")), GameAssets, true, true);
    for (const FAssetData& Asset : GameAssets)
        if (SelectedClasses.Contains(Asset.AssetClassPath)) SeedPackages.Add(Asset.PackageName);

    TArray<FString> SeedNames;
    for (const FName Seed : SeedPackages) SeedNames.Add(Seed.ToString());
    SeedNames.Sort();
    Report->SetArrayField(TEXT("seedPackages"), Strings(SeedNames));
    TArray<FName> Queue;
    TSet<FName> Seen;
    for (const FString& Seed : SeedNames) { Queue.Add(FName(*Seed)); Seen.Add(FName(*Seed)); }
    TMap<FString, FAssetData> ReachableAssets;
    TArray<TPair<FString, FValue>> PackageItems;
    for (int32 QueueIndex = 0; QueueIndex < Queue.Num(); ++QueueIndex)
    {
        const FName Package = Queue[QueueIndex];
        const FString PackageName = Package.ToString();
        FObject Item = MakeShared<FJsonObject>();
        Item->SetStringField(TEXT("package"), PackageName);
        Item->SetBoolField(TEXT("seed"), SeedPackages.Contains(Package));
        TArray<FAssetData> Assets;
        Registry.GetAssetsByPackageName(Package, Assets, true, false);
        Assets.Sort([](const FAssetData& A, const FAssetData& B) { return A.GetObjectPathString() < B.GetObjectPathString(); });
        FValues AssetItems;
        for (const FAssetData& Asset : Assets)
        {
            AssetItems.Add(Json(AssetRecord(Asset)));
            ReachableAssets.Add(Asset.GetObjectPathString(), Asset);
        }
        Item->SetArrayField(TEXT("assets"), AssetItems);
        TArray<FAssetDependency> Dependencies;
        const bool bHasDependencyNode = Registry.GetDependencies(FAssetIdentifier(Package), Dependencies,
            UE::AssetRegistry::EDependencyCategory::Package);
        Item->SetBoolField(TEXT("registryDependencyNodeAvailable"), bHasDependencyNode);
        if (!bHasDependencyNode && !PackageName.StartsWith(TEXT("/Script/")))
            Context.Gaps.Add(TEXT("Registry dependency node unavailable (not assumed dependency-free): ") + PackageName);
        Dependencies.Sort([](const FAssetDependency& A, const FAssetDependency& B) { return A.LexicalLess(B); });
        FValues Edges;
        for (const FAssetDependency& Dependency : Dependencies)
        {
            FObject Edge = MakeShared<FJsonObject>();
            Edge->SetStringField(TEXT("identifier"), Dependency.AssetId.ToString());
            Edge->SetStringField(TEXT("package"), Dependency.AssetId.PackageName.ToString());
            Edge->SetNumberField(TEXT("categoryFlags"), static_cast<uint32>(Dependency.Category));
            Edge->SetNumberField(TEXT("propertyFlags"), static_cast<uint32>(Dependency.Properties));
            Edge->SetBoolField(TEXT("hard"), EnumHasAnyFlags(Dependency.Properties, UE::AssetRegistry::EDependencyProperty::Hard));
            Edge->SetBoolField(TEXT("game"), EnumHasAnyFlags(Dependency.Properties, UE::AssetRegistry::EDependencyProperty::Game));
            Edge->SetBoolField(TEXT("build"), EnumHasAnyFlags(Dependency.Properties, UE::AssetRegistry::EDependencyProperty::Build));
            Edges.Add(Json(Edge));
            const FName Target = Dependency.AssetId.PackageName;
            if (!Target.IsNone() && !Seen.Contains(Target)) { Seen.Add(Target); Queue.Add(Target); }
        }
        Item->SetArrayField(TEXT("packageDependencies"), Edges);
        PackageItems.Emplace(PackageName, Json(Item));
    }
    PackageItems.Sort([](const auto& A, const auto& B) { return A.Key < B.Key; });
    FValues Packages;
    for (const auto& Pair : PackageItems) Packages.Add(Pair.Value);
    Report->SetArrayField(TEXT("packages"), Packages);

    TArray<FString> AssetPaths;
    ReachableAssets.GetKeys(AssetPaths);
    AssetPaths.Sort();
    FValues Blueprints, PhysicsAssets, NiagaraSystems;
    for (const FString& Path : AssetPaths)
    {
        const FAssetData& Asset = ReachableAssets.FindChecked(Path);
        if (!SelectedClasses.Contains(Asset.AssetClassPath)) continue;
        UObject* Object = Asset.GetAsset();
        if (!Object) { Context.Errors.Add(TEXT("Failed to load selected asset: ") + Path); continue; }
        if (UBlueprint* Blueprint = Cast<UBlueprint>(Object)) Blueprints.Add(Json(ExportBlueprint(Blueprint, Context)));
        else if (UPhysicsAsset* PhysicsAsset = Cast<UPhysicsAsset>(Object)) PhysicsAssets.Add(Json(ExportPhysicsAsset(PhysicsAsset, Context)));
        else if (UNiagaraSystem* NiagaraSystem = Cast<UNiagaraSystem>(Object)) NiagaraSystems.Add(Json(ExportNiagara(NiagaraSystem, Context)));
        else Context.Errors.Add(TEXT("Selected registry class loaded as unexpected type: ") + Path + TEXT(" -> ") + Object->GetClass()->GetPathName());
    }
    Report->SetArrayField(TEXT("blueprints"), Blueprints);
    Report->SetArrayField(TEXT("physicsAssets"), PhysicsAssets);
    Report->SetArrayField(TEXT("niagaraSystems"), NiagaraSystems);
    Report->SetBoolField(TEXT("successWithinDeclaredScope"), Context.Errors.IsEmpty());
    Report->SetArrayField(TEXT("errors"), Strings(Context.Errors));
    Report->SetArrayField(TEXT("gaps"), Strings(Context.Gaps));
    const FString Text = CanonicalJson(Json(Report));
    const FString Directory = FPaths::GetPath(Output);
    if (!IFileManager::Get().DirectoryExists(*Directory) && !IFileManager::Get().MakeDirectory(*Directory, true))
    {
        UE_LOG(LogProphecyJoltInventory, Error, TEXT("Cannot create report directory: %s"), *Directory);
        return 1;
    }
    // NoReplaceExisting closes the race between the initial existence check and report creation.
    if (!FFileHelper::SaveStringToFile(Text, *Output, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
        &IFileManager::Get(), bOverwrite ? 0 : FILEWRITE_NoReplaceExisting))
    {
        UE_LOG(LogProphecyJoltInventory, Error, TEXT("Cannot write report: %s"), *Output);
        return 1;
    }
    for (const FString& Error : Context.Errors) UE_LOG(LogProphecyJoltInventory, Error, TEXT("%s"), *Error);
    UE_LOG(LogProphecyJoltInventory, Display, TEXT("Wrote %s: %d packages, %d Blueprints, %d PhysicsAssets, %d Niagara systems, %d errors; inspect declared gaps."),
        *Output, Packages.Num(), Blueprints.Num(), PhysicsAssets.Num(), NiagaraSystems.Num(), Context.Errors.Num());
    return Context.Errors.IsEmpty() ? 0 : 1;
}
