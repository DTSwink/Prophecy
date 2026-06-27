#include "ProphecyWireBloodStainCommandlet.h"

#include "ProphecyBloodStainRenderer.h"

#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNodeUtils.h"
#include "EdGraphSchema_K2.h"
#include "FileHelpers.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Event.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "UObject/SavePackage.h"

namespace
{
constexpr TCHAR DecalManagerPath[] = TEXT("/Game/_mygame/blood2/A_DecalManager.A_DecalManager");

UEdGraphPin* FindPinLenient(UEdGraphNode* Node, const TArray<FName>& CandidateNames, EEdGraphPinDirection Direction)
{
	if (!Node)
	{
		return nullptr;
	}

	for (FName CandidateName : CandidateNames)
	{
		if (UEdGraphPin* Pin = Node->FindPin(CandidateName, Direction))
		{
			return Pin;
		}
	}

	auto Normalize = [](const FString& Input)
	{
		FString Out = Input;
		Out.ReplaceInline(TEXT(" "), TEXT(""));
		Out.ReplaceInline(TEXT("_"), TEXT(""));
		return Out.ToLower();
	};

	TSet<FString> NormalizedCandidates;
	for (FName CandidateName : CandidateNames)
	{
		NormalizedCandidates.Add(Normalize(CandidateName.ToString()));
	}

	for (UEdGraphPin* Pin : Node->Pins)
	{
		if (Pin && Pin->Direction == Direction && NormalizedCandidates.Contains(Normalize(Pin->PinName.ToString())))
		{
			return Pin;
		}
	}

	return nullptr;
}

UK2Node_Event* FindReceiveParticleDataEvent(UBlueprint* Blueprint, UEdGraph*& OutGraph)
{
	if (!Blueprint)
	{
		return nullptr;
	}

	for (UEdGraph* Graph : Blueprint->UbergraphPages)
	{
		if (!Graph)
		{
			continue;
		}

		for (UEdGraphNode* Node : Graph->Nodes)
		{
			UK2Node_Event* EventNode = Cast<UK2Node_Event>(Node);
			if (!EventNode)
			{
				continue;
			}

			const FName EventMemberName = EventNode->EventReference.GetMemberName();
			const FString EventMember = EventMemberName.ToString();
			const FString CustomFunction = EventNode->CustomFunctionName.ToString();
			if (EventMember.Contains(TEXT("ReceiveParticleData")) || CustomFunction.Contains(TEXT("ReceiveParticleData")))
			{
				OutGraph = Graph;
				return EventNode;
			}
		}
	}

	return nullptr;
}

bool GraphAlreadyCallsBloodRenderer(UBlueprint* Blueprint)
{
	const UFunction* TargetFunction = UProphecyBloodStainBlueprintLibrary::StaticClass()->FindFunctionByName(GET_FUNCTION_NAME_CHECKED(UProphecyBloodStainBlueprintLibrary, AddBloodParticleDataToWorld));
	if (!Blueprint || !TargetFunction)
	{
		return false;
	}

	for (UEdGraph* Graph : Blueprint->UbergraphPages)
	{
		if (!Graph)
		{
			continue;
		}

		for (UEdGraphNode* Node : Graph->Nodes)
		{
			const UK2Node_CallFunction* CallNode = Cast<UK2Node_CallFunction>(Node);
			if (CallNode && CallNode->GetTargetFunction() == TargetFunction)
			{
				return true;
			}
		}
	}

	return false;
}

bool SaveBlueprint(UBlueprint* Blueprint)
{
	if (!Blueprint)
	{
		return false;
	}

	UPackage* Package = Blueprint->GetOutermost();
	if (!Package)
	{
		return false;
	}

	const FString PackageFilename = FPackageName::LongPackageNameToFilename(Package->GetName(), FPackageName::GetAssetPackageExtension());
	FSavePackageArgs SaveArgs;
	SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
	SaveArgs.SaveFlags = SAVE_NoError;
	return UPackage::SavePackage(Package, nullptr, *PackageFilename, SaveArgs);
}
}

UProphecyWireBloodStainCommandlet::UProphecyWireBloodStainCommandlet()
{
	IsClient = false;
	IsEditor = true;
	IsServer = false;
	LogToConsole = true;
}

int32 UProphecyWireBloodStainCommandlet::Main(const FString& Params)
{
	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, DecalManagerPath);
	if (!Blueprint)
	{
		UE_LOG(LogTemp, Error, TEXT("[ProphecyWireBloodStain] Could not load %s"), DecalManagerPath);
		return 1;
	}

	if (GraphAlreadyCallsBloodRenderer(Blueprint))
	{
		UE_LOG(LogTemp, Display, TEXT("[ProphecyWireBloodStain] A_DecalManager already calls AddBloodParticleDataToWorld; no graph edit needed."));
		return 0;
	}

	UEdGraph* EventGraph = nullptr;
	UK2Node_Event* EventNode = FindReceiveParticleDataEvent(Blueprint, EventGraph);
	if (!EventNode || !EventGraph)
	{
		UE_LOG(LogTemp, Error, TEXT("[ProphecyWireBloodStain] Could not find ReceiveParticleData event in A_DecalManager."));
		return 2;
	}

	const UEdGraphSchema_K2* Schema = Cast<UEdGraphSchema_K2>(EventGraph->GetSchema());
	if (!Schema)
	{
		UE_LOG(LogTemp, Error, TEXT("[ProphecyWireBloodStain] Event graph is not a K2 graph."));
		return 3;
	}

	UFunction* TargetFunction = UProphecyBloodStainBlueprintLibrary::StaticClass()->FindFunctionByName(GET_FUNCTION_NAME_CHECKED(UProphecyBloodStainBlueprintLibrary, AddBloodParticleDataToWorld));
	if (!TargetFunction)
	{
		UE_LOG(LogTemp, Error, TEXT("[ProphecyWireBloodStain] Could not find AddBloodParticleDataToWorld function."));
		return 4;
	}

	EventGraph->Modify();
	EventNode->Modify();

	FGraphNodeCreator<UK2Node_CallFunction> NodeCreator(*EventGraph);
	UK2Node_CallFunction* CallNode = NodeCreator.CreateNode();
	CallNode->SetFromFunction(TargetFunction);
	CallNode->NodePosX = EventNode->NodePosX + 360;
	CallNode->NodePosY = EventNode->NodePosY - 20;
	NodeCreator.Finalize();
	CallNode->Modify();

	UEdGraphPin* EventThenPin = EventNode->FindPin(UEdGraphSchema_K2::PN_Then, EGPD_Output);
	UEdGraphPin* EventDataPin = FindPinLenient(EventNode, {TEXT("Data")}, EGPD_Output);
	UEdGraphPin* EventOffsetPin = FindPinLenient(EventNode, {TEXT("SimulationPositionOffset"), TEXT("Simulation Position Offset")}, EGPD_Output);
	UEdGraphPin* CallExecPin = CallNode->GetExecPin();
	UEdGraphPin* CallThenPin = CallNode->GetThenPin();
	UEdGraphPin* CallDataPin = FindPinLenient(CallNode, {TEXT("Data")}, EGPD_Input);
	UEdGraphPin* CallOffsetPin = FindPinLenient(CallNode, {TEXT("SimulationPositionOffset"), TEXT("Simulation Position Offset")}, EGPD_Input);

	if (!EventThenPin || !EventDataPin || !EventOffsetPin || !CallExecPin || !CallThenPin || !CallDataPin || !CallOffsetPin)
	{
		UE_LOG(LogTemp, Error, TEXT("[ProphecyWireBloodStain] Missing expected pins while wiring graph."));
		return 5;
	}

	TArray<UEdGraphPin*> PreviousExecLinks = EventThenPin->LinkedTo;
	EventThenPin->BreakAllPinLinks();

	bool bOk = true;
	bOk &= Schema->TryCreateConnection(EventThenPin, CallExecPin);
	bOk &= Schema->TryCreateConnection(EventDataPin, CallDataPin);
	bOk &= Schema->TryCreateConnection(EventOffsetPin, CallOffsetPin);

	for (UEdGraphPin* PreviousExecLink : PreviousExecLinks)
	{
		if (PreviousExecLink && PreviousExecLink != CallExecPin)
		{
			bOk &= Schema->TryCreateConnection(CallThenPin, PreviousExecLink);
		}
	}

	if (!bOk)
	{
		UE_LOG(LogTemp, Error, TEXT("[ProphecyWireBloodStain] One or more graph connections failed."));
		return 6;
	}

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FKismetEditorUtilities::CompileBlueprint(Blueprint);

	if (!SaveBlueprint(Blueprint))
	{
		UE_LOG(LogTemp, Error, TEXT("[ProphecyWireBloodStain] Graph was modified but save failed."));
		return 7;
	}

	UE_LOG(LogTemp, Display, TEXT("[ProphecyWireBloodStain] Wired A_DecalManager ReceiveParticleData into AddBloodParticleDataToWorld and saved the Blueprint."));
	return 0;
}
