#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "UObject/SavePackage.h"

namespace ProphecyInputRecorderSetup
{
void Install()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP = LoadObject<UBlueprint>(nullptr, TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP || !BP->GeneratedClass) return;
    auto* InputStruct = FindObject<UScriptStruct>(nullptr, TEXT("/Script/GameAnimationSample3.ProphecyReplayedInput"));
    auto* Library = FindObject<UClass>(nullptr, TEXT("/Script/GameAnimationSample3.ProphecyInputRecorderLibrary"));
    auto* Initialize = Library ? Library->FindFunctionByName(TEXT("InitializeInputRecorder")) : nullptr;
    if (!InputStruct || !Initialize) return;
    const FName FunctionName(TEXT("InitializeInputRecording"));
    if (BP->GeneratedClass->FindFunctionByName(FunctionName))
    { UE_LOG(LogTemp, Display, TEXT("InputRecorderSetup: initialization function already exists; no edits.")); return; }
    const FName Names[] = { TEXT("RecordingInput"), TEXT("PlayingInput"), TEXT("RecordingSlot"), TEXT("ReplayedInput") };
    for (const auto Name : Names) if (FindFProperty<FProperty>(BP->GeneratedClass, Name))
    { UE_LOG(LogTemp, Error, TEXT("InputRecorderSetup: existing %s must be inspected before editing; no edits."), *Name.ToString()); return; }
    const FString Filename = FPackageName::LongPackageNameToFilename(BP->GetOutermost()->GetName(), FPackageName::GetAssetPackageExtension());
    const FString Backup = FPaths::ProjectSavedDir()/TEXT("Diagnostics/InputRecorderBackup")/FDateTime::Now().ToString(TEXT("%Y%m%d-%H%M%S"));
    IFileManager::Get().MakeDirectory(*Backup, true);
    if (IFileManager::Get().Copy(*(Backup/TEXT("Disk-BP_ProphecyManualPoseAgent.uasset")), *Filename, false) != COPY_OK) return;
    FSavePackageArgs Snapshot; Snapshot.TopLevelFlags = RF_Public|RF_Standalone; Snapshot.SaveFlags = SAVE_KeepDirty;
    if (!UPackage::SavePackage(BP->GetOutermost(), BP, *(Backup/TEXT("Current-BP_ProphecyManualPoseAgent.uasset")), Snapshot)) return;
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy", "InputRecorderSetup", "Add manual input recorder controls"));
    BP->Modify();
    TArray<FName> Added;
    bool OK = true;
    for (int32 I=0; I<4; ++I)
    {
        FEdGraphPinType Type;
        Type.PinCategory = I < 2 ? UEdGraphSchema_K2::PC_Boolean : (I == 2 ? UEdGraphSchema_K2::PC_Int : UEdGraphSchema_K2::PC_Struct);
        if (I == 3) Type.PinSubCategoryObject = InputStruct;
        if (!FBlueprintEditorUtils::AddMemberVariable(BP, Names[I], Type, I < 2 ? TEXT("false") : (I == 2 ? TEXT("0") : TEXT("")))) { OK = false; break; }
        Added.Add(Names[I]);
        FBlueprintEditorUtils::SetBlueprintOnlyEditableFlag(BP, Names[I], false);
        FBlueprintEditorUtils::SetBlueprintVariableCategory(BP, Names[I], nullptr, FText::FromString(TEXT("Debug|Input Recording")), true);
    }
    UEdGraph* Graph = nullptr;
    if (OK)
    {
        Graph = FBlueprintEditorUtils::CreateNewGraph(BP, FunctionName, UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());
        FBlueprintEditorUtils::AddFunctionGraph<UClass>(BP, Graph, true, nullptr);
        TArray<UK2Node_FunctionEntry*> Entries; Graph->GetNodesOfClass(Entries);
        FGraphNodeCreator<UK2Node_CallFunction> Creator(*Graph);
        auto* Call = Creator.CreateNode();
        Call->SetFromFunction(Initialize);
        Call->NodePosX = 300;
        Call->NodeComment = TEXT("Opt-in debug input recorder. Call this function from BeginPlay when wanted; gameplay wiring remains yours.");
        Creator.Finalize();
        OK = Entries.Num() == 1 && GetDefault<UEdGraphSchema_K2>()->TryCreateConnection(
            Entries[0]->FindPinChecked(UEdGraphSchema_K2::PN_Then), Call->FindPinChecked(UEdGraphSchema_K2::PN_Execute));
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
        FKismetEditorUtilities::CompileBlueprint(BP, EBlueprintCompileOptions::SkipGarbageCollection);
        OK &= BP->Status != BS_Error;
    }
    if (!OK)
    {
        if (Graph) FBlueprintEditorUtils::RemoveGraph(BP, Graph);
        for (const auto Name : Added) FBlueprintEditorUtils::RemoveMemberVariable(BP, Name);
        FKismetEditorUtilities::CompileBlueprint(BP, EBlueprintCompileOptions::SkipGarbageCollection);
        UE_LOG(LogTemp, Error, TEXT("InputRecorderSetup: setup failed; additions removed. Backup: %s"), *Backup);
        return;
    }
    FSavePackageArgs Save; Save.TopLevelFlags = RF_Public|RF_Standalone;
    const bool Saved = UPackage::SavePackage(BP->GetOutermost(), BP, *Filename, Save);
    UE_LOG(LogTemp, Display, TEXT("InputRecorderSetup: four variables and unwired initialization function compiled; saved=%d. Backup: %s"), Saved, *Backup);
}
FAutoConsoleCommand Command(TEXT("Prophecy.Debug.InstallInputRecorder"), TEXT("Back up and add recorder controls only to the manual debug Blueprint; do not wire BeginPlay."), FConsoleCommandDelegate::CreateStatic(&Install));
}
