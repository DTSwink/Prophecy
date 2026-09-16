#include "ProphecyStandardPhysicsCompiler.h"
#include "ProphecyJoltStandardPhysicsLibrary.h"
#include "BlueprintCompilationManager.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Self.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Editor.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"
#include "UObject/UObjectIterator.h"

namespace
{
TSet<TWeakObjectPtr<UBlueprint>> Compiled;
FDelegateHandle BeforePIE;
UFunction* ReplacementFor(const UK2Node_CallFunction& Node)
{
    UFunction* Original = Node.GetTargetFunction();
    if (!Original || Original->GetOutermost()->GetName() != TEXT("/Script/Engine")) return nullptr;
    UFunction* Replacement = UProphecyJoltStandardPhysicsLibrary::StaticClass()->FindFunctionByName(Original->GetFName());
    if (!Replacement || Replacement->GetOuterUClass() != UProphecyJoltStandardPhysicsLibrary::StaticClass()) return nullptr;
    // Both the name AND declaring receiver must agree. Never rewrite unrelated same-name methods.
    for (TFieldIterator<FObjectPropertyBase> It(Replacement); It && (It->PropertyFlags & CPF_Parm); ++It)
        return Original->GetOuterUClass()->IsChildOf(It->PropertyClass) ? Replacement : nullptr;
    return nullptr;
}
void CompileLoaded()
{
    if (!GEditor || GEditor->PlayWorld) return;
    TArray<TWeakObjectPtr<UBlueprint>> Candidates;
    for (TObjectIterator<UBlueprint> It; It; ++It)
    {
        UBlueprint* BP = *It;
        if (!BP->GeneratedClass || !BP->GetPathName().StartsWith(TEXT("/Game/")) || Compiled.Contains(BP)) continue;
        TArray<UEdGraph*> Graphs; BP->GetAllGraphs(Graphs);
        bool bNeeds = false;
        for (auto* Graph : Graphs) for (UEdGraphNode* Node : Graph->Nodes)
            if (auto* Call = Cast<UK2Node_CallFunction>(Node); Call && ReplacementFor(*Call)) bNeeds = true;
        if (bNeeds) Candidates.Add(BP);
    }
    for (const auto& BP : Candidates) if (BP.IsValid() && !Compiled.Contains(BP))
        FKismetEditorUtilities::CompileBlueprint(BP.Get(), EBlueprintCompileOptions::SkipGarbageCollection);
    UE_LOG(LogTemp, Display, TEXT("Jolt standard Blueprint dispatch: compiled %d loaded candidates; authored graphs unchanged."), Candidates.Num());
}
FAutoConsoleCommand CompileCommand(TEXT("Prophecy.Physics.CompileLoaded"),
    TEXT("Compile loaded gameplay Blueprints through the standard Jolt command dispatcher."), FConsoleCommandDelegate::CreateStatic(&CompileLoaded));
}

void UProphecyStandardPhysicsCompiler::ProcessBlueprintCompiled(const FKismetCompilerContext& Context, const FBlueprintCompiledData& Data)
{
    if (!Context.Blueprint || !Context.Blueprint->GetPathName().StartsWith(TEXT("/Game/"))) return;
    auto& Compiler = const_cast<FKismetCompilerContext&>(Context);
    for (UEdGraph* Graph : Data.IntermediateGraphs)
    {
        if (!Graph) continue;
        const auto Nodes = Graph->Nodes;
        for (UEdGraphNode* Node : Nodes)
        {
            auto* Old = Cast<UK2Node_CallFunction>(Node);
            UFunction* Target = Old ? ReplacementFor(*Old) : nullptr;
            if (!Target) continue;
            auto* Call = Compiler.SpawnIntermediateNode<UK2Node_CallFunction>(Old, Graph);
            Call->SetFromFunction(Target); Call->AllocateDefaultPins();
            FName Receiver;
            for (TFieldIterator<FProperty> It(Target); It && (It->PropertyFlags & CPF_Parm); ++It)
            { Receiver = It->GetFName(); break; }
            for (auto* Pin : Old->Pins)
            {
                if (Pin->ParentPin) continue;
                const FName Name = Pin->PinName == UEdGraphSchema_K2::PN_Self ? Receiver : Pin->PinName;
                auto* NewPin = Call->FindPin(Name, Pin->Direction);
                if (!NewPin)
                {
                    Compiler.MessageLog.Error(TEXT("Jolt standard node could not preserve pin @@"), Pin);
                    continue;
                }
                if (Pin->PinName == UEdGraphSchema_K2::PN_Self && Pin->LinkedTo.IsEmpty() && !Pin->DefaultObject)
                {
                    auto* Self = Compiler.SpawnIntermediateNode<UK2Node_Self>(Old, Graph);
                    Self->AllocateDefaultPins(); Self->FindPinChecked(UEdGraphSchema_K2::PN_Self)->MakeLinkTo(NewPin);
                }
                else Compiler.MovePinLinksToIntermediate(*Pin, *NewPin);
            }
            Old->BreakAllNodeLinks(); Graph->RemoveNode(Old);
        }
    }
    Compiled.Add(Context.Blueprint);
}

void RegisterProphecyStandardPhysicsCompiler()
{
    FBlueprintCompilationManager::RegisterCompilerExtension(UBlueprint::StaticClass(), NewObject<UProphecyStandardPhysicsCompiler>());
    BeforePIE = FEditorDelegates::PreBeginPIE.AddLambda([](bool) { CompileLoaded(); });
}
void UnregisterProphecyStandardPhysicsCompiler()
{ FEditorDelegates::PreBeginPIE.Remove(BeforePIE); Compiled.Reset(); }
