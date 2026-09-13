#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "K2Node_FunctionEntry.h"
#include "EdGraphSchema_K2.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "KismetCompiler.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Package.h"

namespace ProphecyWorldContextPinRepair
{
constexpr const TCHAR* AssetPath = TEXT("/Game/_mygame/NewFunctionLibrary.NewFunctionLibrary");
const FName ContextName(TEXT("__WorldContext"));
const FGuid EntryGuid(0xD0E3467C, 0x484CED7A, 0x3D689D8E, 0xAF7E676E);

FString UserPinText(const FUserPinInfo& Pin)
{
    FString Text;
    FUserPinInfo::StaticStruct()->ExportText(Text, &Pin, nullptr, nullptr, PPF_None, nullptr);
    return Text;
}

// Stable logical pin/wiring identity: reconstruction may replace pin objects/IDs.
FString Snapshot(UEdGraph& Graph, UK2Node_FunctionEntry* Entry, FJsonObject& Report, bool bAllEntries = false)
{
    TArray<FString> Rows;
    TArray<TSharedPtr<FJsonValue>> Definitions, ContextPins;
    for (UEdGraphNode* Node : Graph.Nodes)
    {
        if (!Node) continue;
        const FString NodeKey = Node->NodeGuid.ToString() + TEXT(":") + Node->GetClass()->GetPathName();
        Rows.Add(NodeKey + TEXT(":") + Node->NodeComment);
        auto* Editable = Cast<UK2Node_EditablePinBase>(Node);
        const bool bContextEntry = Node == Entry || (bAllEntries && Cast<UK2Node_FunctionEntry>(Node));
        if (Editable) for (const auto& Definition : Editable->UserDefinedPins)
            if (Definition.IsValid())
            {
                const FString Text = UserPinText(*Definition);
                if (Node == Entry) Definitions.Add(MakeShared<FJsonValueString>(Text));
                if (!bContextEntry || Definition->PinName != ContextName) Rows.Add(NodeKey + TEXT(":USER:") + Text);
            }
        for (UEdGraphPin* Pin : Node->Pins)
        {
            if (!Pin) continue;
            FString Type;
            FEdGraphPinType::StaticStruct()->ExportText(Type, &Pin->PinType, nullptr, nullptr, PPF_None, nullptr);
            TArray<FString> Links;
            for (const UEdGraphPin* Link : Pin->LinkedTo)
                if (Link) Links.Add(Link->GetOwningNode()->NodeGuid.ToString() + TEXT(":") + Link->PinName.ToString()
                    + FString::FromInt(static_cast<int32>(Link->Direction)));
            Links.Sort();
            if (bContextEntry && Pin->PinName == ContextName)
            {
                auto Row = MakeShared<FJsonObject>();
                Row->SetStringField(TEXT("type"), Type); Row->SetBoolField(TEXT("hidden"), Pin->bHidden);
                Row->SetNumberField(TEXT("direction"), static_cast<int32>(Pin->Direction));
                Row->SetNumberField(TEXT("links"), Pin->LinkedTo.Num());
                Row->SetStringField(TEXT("pin_id"), Pin->PinId.ToString());
                Row->SetStringField(TEXT("entry"), Node->GetName());
                ContextPins.Add(MakeShared<FJsonValueObject>(Row));
                continue;
            }
            Rows.Add(NodeKey + TEXT(":") + Pin->PinName.ToString() + TEXT(":") + Type
                + FString::Printf(TEXT(":%d:%d:%d:"), static_cast<int32>(Pin->Direction), int32(Pin->bHidden), int32(Pin->bOrphanedPin))
                + Pin->DefaultValue + TEXT(":") + Pin->DefaultTextValue.ToString() + TEXT(":")
                + GetPathNameSafe(Pin->DefaultObject) + TEXT(":") + FString::Join(Links, TEXT("|")));
        }
    }
    Rows.Sort();
    const FString Fingerprint = FString::Join(Rows, TEXT("\n"));
    Report.SetArrayField(TEXT("user_defined_pins"), Definitions);
    Report.SetArrayField(TEXT("actual_context_pins"), ContextPins);
    Report.SetNumberField(TEXT("actual_context_pin_count"), ContextPins.Num());
    Report.SetNumberField(TEXT("graph_nodes"), Graph.Nodes.Num());
    Report.SetStringField(TEXT("remaining_pins_and_wires"), Fingerprint);
    Report.SetStringField(TEXT("remaining_pins_and_wires_md5"), FMD5::HashAnsiString(*Fingerprint));
    return Fingerprint;
}

FString LibrarySnapshot(UBlueprint& Blueprint, FJsonObject& Report)
{
    TArray<UEdGraph*> Graphs; Blueprint.GetAllGraphs(Graphs);
    TArray<FString> Fingerprints;
    TArray<TSharedPtr<FJsonValue>> Rows;
    for (UEdGraph* Graph : Graphs) if (Graph)
    {
        auto Row = MakeShared<FJsonObject>();
        Snapshot(*Graph, nullptr, *Row, true);
        Row->SetStringField(TEXT("graph"), Graph->GetPathName());
        Fingerprints.Add(Graph->GetPathName() + TEXT(":") + Row->GetStringField(TEXT("remaining_pins_and_wires_md5")));
        Row->RemoveField(TEXT("remaining_pins_and_wires")); // Compact all-graph comparison; per-entry reports retain details.
        Rows.Add(MakeShared<FJsonValueObject>(Row));
    }
    Fingerprints.Sort();
    const FString Result = FString::Join(Fingerprints, TEXT("\n"));
    Report.SetArrayField(TEXT("graphs"), Rows);
    Report.SetStringField(TEXT("all_graph_remaining_pins_and_wires_md5"), FMD5::HashAnsiString(*Result));
    return Result;
}

void Command(const TArray<FString>& Args)
{
    if (Args.Num() != 2 || (Args[0] != TEXT("Inspect") && Args[0] != TEXT("Repair") && Args[0] != TEXT("RepairLibrary"))
        || FPaths::IsRelative(Args[1]) || FPaths::FileExists(Args[1]))
    { UE_LOG(LogTemp, Error, TEXT("Prophecy.Editor.AngSpringWorldContext requires Inspect|Repair|RepairLibrary and a new absolute JSON path.")); return; }
    auto Report = MakeShared<FJsonObject>();
    Report->SetStringField(TEXT("asset"), AssetPath); Report->SetStringField(TEXT("mode"), Args[0]);
    Report->SetBoolField(TEXT("asset_saved"), false);
    FString Error;
    const bool bSuccess = [&]()
    {
        if (!IsInGameThread() || !GEditor || GEditor->PlayWorld)
        { Error = TEXT("Requires the editor game thread with PIE stopped."); return false; }
        UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, AssetPath);
        if (!Blueprint) { Error = TEXT("Exact function-library asset missing."); return false; }
        Report->SetBoolField(TEXT("initially_dirty"), Blueprint->GetOutermost()->IsDirty());
        TArray<TSharedPtr<FJsonValue>> ReservedEntries;
        TArray<UK2Node_FunctionEntry*> AffectedEntries;
        TArray<FString> AffectedIdentities;
        for (UEdGraph* Candidate : Blueprint->FunctionGraphs)
        {
            TArray<UK2Node_FunctionEntry*> CandidateEntries;
            if (Candidate) Candidate->GetNodesOfClass(CandidateEntries);
            for (UK2Node_FunctionEntry* CandidateEntry : CandidateEntries)
            {
                int32 Count = 0;
                for (const auto& Pin : CandidateEntry->UserDefinedPins)
                    if (Pin.IsValid() && Pin->PinName == ContextName) ++Count;
                if (!Count) continue;
                auto Row = MakeShared<FJsonObject>();
                Row->SetStringField(TEXT("entry"), CandidateEntry->GetPathName());
                Row->SetStringField(TEXT("guid"), CandidateEntry->NodeGuid.ToString());
                Row->SetNumberField(TEXT("definitions"), Count);
                Snapshot(*Candidate, CandidateEntry, *Row);
                Row->SetBoolField(TEXT("static_function"), GetDefault<UEdGraphSchema_K2>()->IsStaticFunctionGraph(Candidate));
                ReservedEntries.Add(MakeShared<FJsonValueObject>(Row));
                AffectedEntries.Add(CandidateEntry);
                AffectedIdentities.Add(Candidate->GetName() + TEXT(".") + CandidateEntry->GetName() + TEXT("|") + CandidateEntry->NodeGuid.ToString());
            }
        }
        Report->SetArrayField(TEXT("library_entries_with_user_defined_world_context"), ReservedEntries);
        Report->SetNumberField(TEXT("library_affected_entry_count"), ReservedEntries.Num());
        AffectedIdentities.Sort([](const FString& A, const FString& B) { return A.Compare(B, ESearchCase::CaseSensitive) < 0; });
        const FString IdentityHash = FMD5::HashAnsiString(*FString::Join(AffectedIdentities, TEXT("\n")));
        Report->SetStringField(TEXT("affected_name_guid_manifest_md5"), IdentityHash);
        auto LibraryBefore = MakeShared<FJsonObject>(); Report->SetObjectField(TEXT("library_before"), LibraryBefore);
        const FString LibraryFingerprint = LibrarySnapshot(*Blueprint, *LibraryBefore);
        UEdGraph* Graph = nullptr;
        for (UEdGraph* Candidate : Blueprint->FunctionGraphs)
            if (Candidate && Candidate->GetFName() == FName(TEXT("Ang Spring"))) Graph = Candidate;
        TArray<UK2Node_FunctionEntry*> Entries;
        if (Graph) Graph->GetNodesOfClass(Entries);
        if (!Graph || Entries.Num() != 1 || Entries[0]->NodeGuid != EntryGuid
            || Blueprint->BlueprintType != BPTYPE_FunctionLibrary || !GetDefault<UEdGraphSchema_K2>()->IsStaticFunctionGraph(Graph))
        { Error = TEXT("Asset/function/entry GUID/static-library contract mismatch."); return false; }
        UK2Node_FunctionEntry* Entry = Entries[0];
        auto Before = MakeShared<FJsonObject>(); Report->SetObjectField(TEXT("before"), Before);
        const FString BeforeFingerprint = Snapshot(*Graph, Entry, *Before);
        if (Args[0] == TEXT("Inspect")) return true;
        if (Blueprint->GetOutermost()->IsDirty())
        { Error = TEXT("Refusing repair of an already dirty asset."); return false; }
        const bool bLibrary = Args[0] == TEXT("RepairLibrary");
        // Exact 34 function-name/entry-name/GUID pairs from the user's live inspect.json, 2026-09-10.
        if (bLibrary && (AffectedEntries.Num() != 34 || !IdentityHash.Equals(TEXT("4E06C683E42DD966D925B822DFCBE99E"), ESearchCase::IgnoreCase)))
        { Error = TEXT("Library repair requires the exact inspected 34-entry name/GUID manifest."); return false; }
        TArray<UK2Node_FunctionEntry*> RepairEntries;
        if (bLibrary) RepairEntries = AffectedEntries; else RepairEntries.Add(Entry);
        TArray<FEdGraphPinType> OriginalTypes;
        TArray<FString> BeforeFingerprints;
        // Preflight every entry before the first Modify/remove; a linked or different pin rejects the whole repair.
        for (UK2Node_FunctionEntry* RepairEntry : RepairEntries)
        {
        TArray<TSharedPtr<FUserPinInfo>> Definitions = RepairEntry->UserDefinedPins.FilterByPredicate(
            [](const auto& Pin) { return Pin.IsValid() && Pin->PinName == ContextName; });
        TArray<UEdGraphPin*> Pins = RepairEntry->Pins.FilterByPredicate(
            [](const UEdGraphPin* Pin) { return Pin && Pin->PinName == ContextName; });
        if (!GetDefault<UEdGraphSchema_K2>()->IsStaticFunctionGraph(RepairEntry->GetGraph())
            || Definitions.Num() != 1 || Pins.Num() != 1 || Pins[0]->LinkedTo.Num() != 0
            || Pins[0]->Direction != EGPD_Output || Definitions[0]->DesiredPinDirection != EGPD_Output
            || Definitions[0]->PinType != Pins[0]->PinType || Pins[0]->PinType.PinCategory != UEdGraphSchema_K2::PC_Object
            || Pins[0]->PinType.PinSubCategoryObject.Get() != UObject::StaticClass() || Pins[0]->PinType.IsContainer())
        { Error = TEXT("Expected exactly one unlinked user-defined output __WorldContext UObject parameter; no repair applied."); return false; }
        OriginalTypes.Add(Pins[0]->PinType);
        FJsonObject EntryBefore;
        BeforeFingerprints.Add(Snapshot(*RepairEntry->GetGraph(), RepairEntry, EntryBefore));
        }
        Blueprint->Modify();
        for (UK2Node_FunctionEntry* RepairEntry : RepairEntries)
        {
            RepairEntry->GetGraph()->Modify(); RepairEntry->Modify();
            RepairEntry->RemoveUserDefinedPinByName(ContextName); RepairEntry->ReconstructNode();
        }
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
        FCompilerResultsLog Results;
        FKismetEditorUtilities::CompileBlueprint(Blueprint, EBlueprintCompileOptions::SkipGarbageCollection, &Results);
        auto After = MakeShared<FJsonObject>(); Report->SetObjectField(TEXT("after"), After);
        bool bPreserved = Snapshot(*Graph, Entry, *After) == BeforeFingerprint;
        bool bGenerated = true;
        TArray<TSharedPtr<FJsonValue>> RepairedEntries;
        for (int32 Index = 0; Index < RepairEntries.Num(); ++Index)
        {
            UK2Node_FunctionEntry* RepairEntry = RepairEntries[Index];
            auto Row = MakeShared<FJsonObject>(); Row->SetStringField(TEXT("entry"), RepairEntry->GetPathName());
            const bool bEntryPreserved = Snapshot(*RepairEntry->GetGraph(), RepairEntry, *Row) == BeforeFingerprints[Index];
            auto Pins = RepairEntry->Pins.FilterByPredicate([](const UEdGraphPin* Pin) { return Pin && Pin->PinName == ContextName; });
            const bool bEntryGenerated = !RepairEntry->UserDefinedPins.ContainsByPredicate(
                [](const auto& Pin) { return Pin.IsValid() && Pin->PinName == ContextName; }) && Pins.Num() == 1 && Pins[0]->bHidden
                && Pins[0]->Direction == EGPD_Output && Pins[0]->LinkedTo.Num() == 0 && Pins[0]->PinType == OriginalTypes[Index];
            Row->SetBoolField(TEXT("remaining_pins_and_wires_unchanged"), bEntryPreserved);
            Row->SetBoolField(TEXT("generated_context_pin_verified"), bEntryGenerated);
            RepairedEntries.Add(MakeShared<FJsonValueObject>(Row));
            bPreserved &= bEntryPreserved; bGenerated &= bEntryGenerated;
        }
        Report->SetArrayField(TEXT("repaired_entries"), RepairedEntries);
        auto LibraryAfter = MakeShared<FJsonObject>(); Report->SetObjectField(TEXT("library_after"), LibraryAfter);
        const bool bLibraryPreserved = LibrarySnapshot(*Blueprint, *LibraryAfter) == LibraryFingerprint;
        Report->SetBoolField(TEXT("all_graph_remaining_pins_and_wires_unchanged"), bLibraryPreserved);
        bPreserved &= bLibraryPreserved;
        Report->SetNumberField(TEXT("compile_errors"), Results.NumErrors);
        Report->SetNumberField(TEXT("compile_warnings"), Results.NumWarnings);
        Report->SetBoolField(TEXT("remaining_pins_and_wires_unchanged"), bPreserved);
        Report->SetBoolField(TEXT("generated_context_pin_verified"), bGenerated);
        if (!bPreserved || !bGenerated || Results.NumErrors != 0 || Blueprint->Status == BS_Error)
        { Error = TEXT("Repair verification failed; asset remains UNSAVED for inspection."); return false; }
        return true;
    }();
    Report->SetBoolField(TEXT("success"), bSuccess); Report->SetStringField(TEXT("error"), Error);
    FString Text;
    const bool bSerialized = FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Text));
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Args[1]), true);
    const bool bSaved = bSerialized && FFileHelper::SaveStringToFile(Text, *Args[1], FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
        &IFileManager::Get(), FILEWRITE_NoReplaceExisting);
    if (!bSuccess || !bSaved)
    { UE_LOG(LogTemp, Error, TEXT("Ang Spring context-pin helper failed: %s; report=%s saved=%d. Asset was not saved."), *Error, *Args[1], bSaved); }
    else
    { UE_LOG(LogTemp, Display, TEXT("Ang Spring context-pin %s passed; report=%s. Asset was not saved."), *Args[0], *Args[1]); }
}
FAutoConsoleCommand ConsoleCommand(TEXT("Prophecy.Editor.AngSpringWorldContext"),
    TEXT("Inspect|Repair Ang Spring, or RepairLibrary for the exact inspected 34 unlinked reserved parameters; new JSON path; never saves assets."),
    FConsoleCommandWithArgsDelegate::CreateStatic(&Command));
}
