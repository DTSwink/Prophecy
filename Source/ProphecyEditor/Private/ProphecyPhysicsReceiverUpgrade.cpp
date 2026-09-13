#include "CoreMinimal.h"
#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "Engine/Blueprint.h"
#include "Engine/Engine.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "Editor.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "UObject/SavePackage.h"
#include "ProphecyPhysicsSkeletalMeshComponent.h"
#include "ProphecyPhysicsStaticMeshComponent.h"

namespace
{
TArray<FString> Wiring(UBlueprint* BP)
{
    TArray<UEdGraph*> Graphs;
    BP->GetAllGraphs(Graphs);
    TArray<FString> Result;
    for (const UEdGraph* Graph : Graphs) for (const UEdGraphNode* Node : Graph->Nodes)
    {
        if (!Node) continue;
        Result.Add(Node->NodeGuid.ToString() + TEXT(":") + Node->GetClass()->GetPathName());
        for (const UEdGraphPin* Pin : Node->Pins)
        {
            if (!Pin) continue;
            const FString Prefix = Node->NodeGuid.ToString() + TEXT(":") + Pin->PinName.ToString();
            Result.Add(Prefix + TEXT("=") + Pin->DefaultValue + TEXT(":") + GetPathNameSafe(Pin->DefaultObject));
            for (const UEdGraphPin* Link : Pin->LinkedTo)
                if (Link) Result.Add(Prefix + TEXT("->") + Link->GetOwningNode()->NodeGuid.ToString() + TEXT(":") + Link->PinName.ToString());
        }
    }
    Result.Sort();
    return Result;
}

void Inspect(const TArray<FString>& Args)
{
    if (Args.Num() != 1) return;
    UBlueprint* BP = LoadObject<UBlueprint>(nullptr, *Args[0]);
    if (!BP || !BP->SimpleConstructionScript) return;
    for (const auto* Node : BP->SimpleConstructionScript->GetAllNodes())
        UE_LOG(LogTemp, Display, TEXT("PhysicsReceiver template: %s %s %s"), *BP->GetPathName(),
            *Node->GetVariableName().ToString(), *GetPathNameSafe(Node->ComponentClass));
}

void Upgrade(const TArray<FString>& Args)
{
    if (Args.Num() != 2 || !GEditor || GEditor->PlayWorld) return;
    UBlueprint* BP = LoadObject<UBlueprint>(nullptr, *Args[0]);
    if (!BP || !BP->SimpleConstructionScript)
    {
        UE_LOG(LogTemp, Error, TEXT("PhysicsReceiver upgrade refused: Blueprint/SCS unavailable."));
        return;
    }
    USCS_Node* Node = BP->SimpleConstructionScript->FindSCSNode(FName(*Args[1]));
    UActorComponent* Old = Node ? Node->ComponentTemplate.Get() : nullptr;
    UClass* NewClass = Old && Old->GetClass() == USkeletalMeshComponent::StaticClass()
        ? UProphecyPhysicsSkeletalMeshComponent::StaticClass()
        : (Old && Old->GetClass() == UStaticMeshComponent::StaticClass() ? UProphecyPhysicsStaticMeshComponent::StaticClass() : nullptr);
    if (!NewClass)
    {
        UE_LOG(LogTemp, Display, TEXT("PhysicsReceiver upgrade skipped: component already upgraded, missing or has custom behavior."));
        return;
    }
    const FString Filename = FPackageName::LongPackageNameToFilename(BP->GetOutermost()->GetName(), FPackageName::GetAssetPackageExtension());
    const FString BackupFolder = FPaths::ProjectSavedDir() / TEXT("Diagnostics/ForceNodes/Backups") / FDateTime::Now().ToString(TEXT("%Y%m%d-%H%M%S"));
    IFileManager::Get().MakeDirectory(*BackupFolder, true);
    if (IFileManager::Get().Copy(*(BackupFolder / FPaths::GetCleanFilename(Filename)), *Filename, false) != COPY_OK)
    {
        UE_LOG(LogTemp, Error, TEXT("PhysicsReceiver upgrade refused: backup failed."));
        return;
    }
    // Preserve the loaded revision too, including any current unsaved edits. Only this
    // explicitly selected Blueprint is saved by the upgrade; never reload/discard it.
    FSavePackageArgs SnapshotSave;
    SnapshotSave.TopLevelFlags = RF_Public | RF_Standalone;
    SnapshotSave.SaveFlags = SAVE_KeepDirty;
    if (!UPackage::SavePackage(BP->GetOutermost(), BP,
        *(BackupFolder / (TEXT("Current-") + FPaths::GetCleanFilename(Filename))), SnapshotSave))
    {
        UE_LOG(LogTemp, Error, TEXT("PhysicsReceiver upgrade refused: loaded-revision backup failed."));
        return;
    }
    const TArray<FString> Before = Wiring(BP);
    const FName Name = Old->GetFName();
    UObject* Outer = Old->GetOuter();
    UClass* OldClass = Old->GetClass();
    UActorComponent* Replacement = NewObject<UActorComponent>(GetTransientPackage(), NewClass, NAME_None, Old->GetFlags());
    UEngine::CopyPropertiesForUnrelatedObjects(Old, Replacement);
    BP->Modify(); Node->Modify();
    Old->Rename(nullptr, GetTransientPackage(), REN_DontCreateRedirectors | REN_NonTransactional);
    Replacement->Rename(*Name.ToString(), Outer, REN_DontCreateRedirectors | REN_NonTransactional);
    Node->ComponentTemplate = Replacement;
    Node->ComponentClass = NewClass;
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    // Rebuild the inherited component-reference pin types against the new skeleton class.
    // Their existing links to Primitive/SkeletalMeshComponent methods remain compatible.
    FBlueprintEditorUtils::RefreshAllNodes(BP);
    FKismetEditorUtilities::CompileBlueprint(BP, EBlueprintCompileOptions::SkipGarbageCollection);
    if (BP->Status == BS_Error || Wiring(BP) != Before)
    {
        Replacement->Rename(nullptr, GetTransientPackage(), REN_DontCreateRedirectors | REN_NonTransactional);
        Old->Rename(*Name.ToString(), Outer, REN_DontCreateRedirectors | REN_NonTransactional);
        Node->ComponentTemplate = Old; Node->ComponentClass = OldClass;
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
        FBlueprintEditorUtils::RefreshAllNodes(BP);
        FKismetEditorUtilities::CompileBlueprint(BP, EBlueprintCompileOptions::SkipGarbageCollection);
        UE_LOG(LogTemp, Error, TEXT("PhysicsReceiver upgrade failed compile/wiring verification; original class restored, asset not saved. Backup: %s"), *BackupFolder);
        return;
    }
    FSavePackageArgs Save;
    Save.TopLevelFlags = RF_Public | RF_Standalone;
    const bool Saved = UPackage::SavePackage(BP->GetOutermost(), BP, *Filename, Save);
    UE_LOG(LogTemp, Display, TEXT("PhysicsReceiver upgrade: saved=%d asset=%s component=%s class=%s wiring_preserved=1 backup=%s"),
        Saved, *BP->GetPathName(), *Args[1], *NewClass->GetPathName(), *BackupFolder);
}
FAutoConsoleCommand InspectCommand(TEXT("Prophecy.PhysicsReceiver.Inspect"), TEXT("Inspect a Blueprint's SCS receiver classes."), FConsoleCommandWithArgsDelegate::CreateStatic(&Inspect));
FAutoConsoleCommand UpgradeCommand(TEXT("Prophecy.PhysicsReceiver.Upgrade"), TEXT("Upgrade one saved plain mesh SCS component; retain name, properties and Blueprint wiring. Args: BlueprintPath ComponentName."), FConsoleCommandWithArgsDelegate::CreateStatic(&Upgrade));
}
