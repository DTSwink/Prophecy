// Explicit editor repair for native agent references retained by Live Coding.
// No startup hook, polling, gameplay code, node replacement or asset saves.
#include "Editor.h"
#include "UObject/UObjectIterator.h"
#include "UObject/UnrealType.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"

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
}
