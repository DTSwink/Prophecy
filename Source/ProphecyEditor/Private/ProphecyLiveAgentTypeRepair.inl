// Explicit editor repair for native agent references retained by Live Coding.
// No startup hook, polling, gameplay code, node replacement or asset saves.
#include "Editor.h"
#include "UObject/UObjectIterator.h"
#include "UObject/UnrealType.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "Kismet/BlueprintFunctionLibrary.h"

namespace ProphecyLiveAgentTypeRepair
{
bool Stale(const UObject* Object)
{
    return Object && (Object->GetOutermost()->GetName()==TEXT("/Script/GameAnimationSample3")
        || Object->GetOutermost()->GetName()==TEXT("/Engine/Transient"))
        && Object->GetName().StartsWith(TEXT("LIVECODING_ProphecyAgent_"));
}
TArray<FString> Wiring(UBlueprint* BP)
{
    TArray<UEdGraph*> Graphs; BP->GetAllGraphs(Graphs);
    TArray<FString> Rows;
    for (const auto* G:Graphs) for (const UEdGraphNode* N:G->Nodes)
    {
        if (!N) continue;
        const FString Key=G->GetName()+TEXT(":")+N->NodeGuid.ToString();
        Rows.Add(Key+TEXT(":")+N->GetClass()->GetPathName());
        for (const auto* P:N->Pins) if (P)
        {
            const FString Pin=Key+TEXT(":")+P->PinName.ToString()+FString::FromInt(int32(P->Direction));
            Rows.Add(Pin+TEXT("=")+P->DefaultValue+TEXT(":")+P->DefaultTextValue.ToString()+TEXT(":")+GetPathNameSafe(P->DefaultObject));
            for (const auto* L:P->LinkedTo) if (L)
                Rows.Add(Pin+TEXT("->")+L->GetOwningNode()->NodeGuid.ToString()+TEXT(":")+L->PinName.ToString());
        }
    }
    Rows.Sort();return Rows;
}
void Run(const TArray<FString>& Args)
{
    if (Args.Num()!=1 || (Args[0]!=TEXT("Inspect") && Args[0]!=TEXT("Repair"))) return;
    const bool Repair=Args[0]==TEXT("Repair");
    if (!GEditor || (Repair && GEditor->PlayWorld)) return;
    auto* Current=FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecyAgent"));
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!Current || !BP || BP->ParentClass!=Current) return;
    FString Report=FString::Printf(TEXT("mode=%s parent=%s\n"),*Args[0],*BP->ParentClass->GetPathName());
    int32 Properties=0,Pins=0;
    // Repair referenced native signatures first; otherwise node reconstruction
    // simply recreates pins pointing to the obsolete temporary class.
    for (TObjectIterator<UStruct> It;It;++It)
    {
        if (It->GetOutermost()->GetName()!=TEXT("/Script/GameAnimationSample3")) continue;
        const auto* Owner=Cast<UClass>(*It)?Cast<UClass>(*It):It->GetTypedOuter<UClass>();
        if (!Owner || Owner->GetName().StartsWith(TEXT("LIVECODING_"))) continue;
        for (TFieldIterator<FProperty> P(*It,EFieldIteratorFlags::ExcludeSuper);P;++P)
        {
            auto Visit=[&](auto&& Self,FProperty* Property)->void
            {
                if (auto* Object=CastField<FObjectPropertyBase>(Property); Object && Stale(Object->PropertyClass))
                {
                    ++Properties;Report+=TEXT("property=")+Object->GetPathName()+TEXT("\n");
                    if (Repair) Object->SetPropertyClass(Current);
                }
                if (auto* Array=CastField<FArrayProperty>(Property)) Self(Self,Array->Inner);
                if (auto* Set=CastField<FSetProperty>(Property)) Self(Self,Set->ElementProp);
                if (auto* Map=CastField<FMapProperty>(Property)) {Self(Self,Map->KeyProp);Self(Self,Map->ValueProp);}
            };
            Visit(Visit,*P);
        }
    }
    const auto Before=Wiring(BP);
    FScopedTransaction Transaction(NSLOCTEXT("Prophecy","RepairLiveAgentTypes","Repair stale Live Coding agent pin types"),Repair);
    if (Repair) BP->Modify();
    auto FixType=[&](FEdGraphPinType& Type)
    {
        if (Stale(Type.PinSubCategoryObject.Get())) {++Pins;if (Repair) Type.PinSubCategoryObject=Current;}
        if (Stale(Type.PinValueType.TerminalSubCategoryObject.Get())) {++Pins;if (Repair) Type.PinValueType.TerminalSubCategoryObject=Current;}
    };
    for (auto& Variable:BP->NewVariables) FixType(Variable.VarType);
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    for (auto* G:Graphs) for (UEdGraphNode* N:G->Nodes) if (N)
    {
        if (Repair) N->Modify();
        for (auto* P:N->Pins) if (P) FixType(P->PinType);
    }
    if (Repair)
    {
        FBlueprintEditorUtils::MarkBlueprintAsModified(BP);
        FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    }
    Report+=FString::Printf(TEXT("native_properties=%d pin_types=%d status=%d wiring_preserved=%d\n"),Properties,Pins,int32(BP->Status),int32(Wiring(BP)==Before));
    FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/LiveAgentTypes-")+Args[0]+TEXT(".txt")));
    UE_LOG(LogTemp,Display,TEXT("LiveAgentTypes: %s"),*Report.RightChop(Report.Find(TEXT("native_properties="))));
}
FAutoConsoleCommand Command(TEXT("Prophecy.Editor.LiveAgentTypes"),TEXT("Inspect|Repair obsolete Live Coding agent signatures and pose-agent pins; preserves wiring and leaves assets unsaved."),FConsoleCommandWithArgsDelegate::CreateStatic(&Run));

void RepairLibraryDefaults()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    auto Expected=Wiring(BP);
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","RepairLibraryDefaults","Repair Live Coding library defaults"));
    BP->Modify();int32 Count=0;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    for (auto* G:Graphs) for (UEdGraphNode* N:G->Nodes) if (N) for (auto* P:N->Pins)
    {
        if (!P || P->PinName!=TEXT("self") || !P->LinkedTo.IsEmpty() || !P->DefaultObject
            || !P->DefaultObject->GetName().StartsWith(TEXT("BPGC_ARCH_FOR_CDO_"))) continue;
        auto* Class=Cast<UClass>(P->PinType.PinSubCategoryObject.Get());
        if (!Class || !Class->IsChildOf(UBlueprintFunctionLibrary::StaticClass())
            || Class->GetOutermost()->GetName()!=TEXT("/Script/GameAnimationSample3")) continue;
        const FString OldPath=P->DefaultObject->GetPathName();
        N->Modify();P->DefaultObject=Class->GetDefaultObject();++Count;
        for (auto& Row:Expected) Row.ReplaceInline(*OldPath,*P->DefaultObject->GetPathName());
    }
    Expected.Sort();
    const bool Preserved=Expected==Wiring(BP);
    FBlueprintEditorUtils::MarkBlueprintAsModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("repaired_defaults=%d status=%d other_values_and_wiring_preserved=%d asset_saved=0\n"),Count,int32(BP->Status),int32(Preserved));
    FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/LiveLibraryDefaults.txt")));
    UE_LOG(LogTemp,Display,TEXT("LiveLibraryDefaults: %s"),*Report);
}
FAutoConsoleCommand LibraryDefaultsCommand(TEXT("Prophecy.Editor.RepairLibraryDefaults"),TEXT("Repair archived Live Coding library CDOs on unlinked self pins; preserve values/connections and leave asset unsaved."),FConsoleCommandDelegate::CreateStatic(&RepairLibraryDefaults));

void RepairAttackCheckpointEnum()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* Enum=FindObject<UEnum>(nullptr,TEXT("/Script/GameAnimationSample3.EProphecyAttackCheckpoint"));
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!Enum || !BP) return;
    const auto Before=Wiring(BP);
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","RepairAttackCheckpointEnum","Refresh attack checkpoint enum pins"));
    BP->Modify();int32 Count=0;
    auto Fix=[&](FEdGraphPinType& Type)
    {
        auto* Old=Type.PinSubCategoryObject.Get();
        if (Old && Old!=Enum && Old->GetName().Contains(TEXT("EProphecyAttackCheckpoint")))
        { Type.PinSubCategoryObject=Enum;++Count; }
    };
    for (auto& Variable:BP->NewVariables) Fix(Variable.VarType);
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    for (auto* G:Graphs) for (UEdGraphNode* N:G->Nodes) if(N)
    {
        N->Modify();
        const auto* Call=Cast<UK2Node_CallFunction>(N);
        const bool CheckpointCall=Call && (Call->FunctionReference.GetMemberName()==TEXT("SetAttackCheckpoint")
            || Call->FunctionReference.GetMemberName()==TEXT("GetAttackCheckpoint"));
        for (auto* P:N->Pins) if(P)
        {
            Fix(P->PinType);
            // A saved transient enum may resolve to null after a clean restart.
            if (CheckpointCall && (P->PinName==TEXT("Checkpoint") || P->PinName==TEXT("Selected") || P->PinName==TEXT("Effective"))
                && P->PinType.PinSubCategoryObject.Get()!=Enum)
            { P->PinType.PinSubCategoryObject=Enum;++Count; }
        }
        // Live enum reinstancing can retain an unconnected obsolete duplicate
        // beside the valid checkpoint pin. Keep the valid pin's selection and
        // all wiring; never discard a linked orphan or the only copy of a pin.
        if (CheckpointCall)
        {
            const auto Pins=N->Pins;
            for (auto* P:Pins) if (P && P->bOrphanedPin && P->LinkedTo.IsEmpty()
                && P->PinName==TEXT("Checkpoint"))
            {
                const bool HasReplacement=N->Pins.ContainsByPredicate([&](const UEdGraphPin* Other)
                { return Other && Other!=P && !Other->bOrphanedPin && Other->PinName==P->PinName
                    && Other->PinType.PinSubCategoryObject.Get()==Enum; });
                if (HasReplacement) { N->RemovePin(P);++Count; }
            }
        }
    }
    FBlueprintEditorUtils::MarkBlueprintAsModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    UE_LOG(LogTemp,Display,TEXT("AttackCheckpointEnum: repaired=%d choices=%d status=%d wiring_preserved=%d asset_saved=0"),
        Count,Enum->NumEnums()-1,int32(BP->Status),int32(Wiring(BP)==Before));
}
FAutoConsoleCommand AttackCheckpointEnumCommand(TEXT("Prophecy.Editor.RepairAttackCheckpointEnum"),TEXT("Repair obsolete attack checkpoint enum pins without changing selections, wiring or saving."),FConsoleCommandDelegate::CreateStatic(&RepairAttackCheckpointEnum));
}
