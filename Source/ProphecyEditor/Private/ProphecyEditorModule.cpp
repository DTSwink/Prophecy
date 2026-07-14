#include "Animation/Skeleton.h"
#include "AssetToolsModule.h"
#include "Components/SkeletalMeshComponent.h"
#include "CoreMinimal.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/Blueprint.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "FileHelpers.h"
#include "HAL/IConsoleManager.h"
#include "IAssetTools.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "Kismet/KismetMathLibrary.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "MetaHumanCharacter.h"
#include "MetaHumanCharacterEditorSubsystem.h"
#include "Misc/PackageName.h"
#include "Modules/ModuleManager.h"
#include "SkeletalMeshEditorSubsystem.h"
#include "SkeletonModifier.h"
#include "SkinWeightModifier.h"

namespace
{
UEdGraphPin* FindPinChecked(UEdGraphNode* Node, const FName PinName, const EEdGraphPinDirection Direction)
{
	return Node ? Node->FindPin(PinName, Direction) : nullptr;
}

bool IsExternalVariableGet(const UK2Node_VariableGet* Node, const FName VariableName)
{
	return Node
		&& Node->VariableReference.GetMemberName() == VariableName
		&& !Node->VariableReference.IsSelfContext();
}

bool IsSelfVariableSet(const UK2Node_VariableSet* Node, const FName VariableName)
{
	return Node
		&& Node->VariableReference.GetMemberName() == VariableName
		&& Node->VariableReference.IsSelfContext();
}

bool IsCallTo(const UK2Node_CallFunction* Node, const FName FunctionName)
{
	return Node && Node->FunctionReference.GetMemberName() == FunctionName;
}

void FixReachTargetSpace()
{
	constexpr TCHAR AssetPath[] = TEXT("/Game/_mygame/ABP_Reach.ABP_Reach");
	const FName LeftTargetName(TEXT("Target Hand L Location"));
	const FName InverseTransformLocationName = GET_FUNCTION_NAME_CHECKED(UKismetMathLibrary, InverseTransformLocation);
	const FName ComponentToWorldName(TEXT("K2_GetComponentToWorld"));

	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, AssetPath);
	if (!Blueprint)
	{
		UE_LOG(LogTemp, Error, TEXT("Reach fix: could not load %s"), AssetPath);
		return;
	}

	UEdGraph* EventGraph = FBlueprintEditorUtils::FindEventGraph(Blueprint);
	if (!EventGraph)
	{
		UE_LOG(LogTemp, Error, TEXT("Reach fix: ABP_Reach has no EventGraph"));
		return;
	}

	UK2Node_VariableGet* LeftTargetGet = nullptr;
	UK2Node_VariableSet* LeftTargetSet = nullptr;
	UK2Node_CallFunction* ComponentToWorld = nullptr;
	UK2Node_CallFunction* ExistingLeftConversion = nullptr;

	for (UEdGraphNode* GraphNode : EventGraph->Nodes)
	{
		if (UK2Node_VariableGet* VariableGet = Cast<UK2Node_VariableGet>(GraphNode))
		{
			if (IsExternalVariableGet(VariableGet, LeftTargetName))
			{
				LeftTargetGet = VariableGet;
			}
			continue;
		}

		if (UK2Node_VariableSet* VariableSet = Cast<UK2Node_VariableSet>(GraphNode))
		{
			if (IsSelfVariableSet(VariableSet, LeftTargetName))
			{
				LeftTargetSet = VariableSet;
			}
			continue;
		}

		UK2Node_CallFunction* CallFunction = Cast<UK2Node_CallFunction>(GraphNode);
		if (!CallFunction)
		{
			continue;
		}

		if (IsCallTo(CallFunction, ComponentToWorldName))
		{
			ComponentToWorld = CallFunction;
		}
		else if (IsCallTo(CallFunction, InverseTransformLocationName))
		{
			UEdGraphPin* LocationPin = FindPinChecked(CallFunction, TEXT("Location"), EGPD_Input);
			if (LocationPin && LeftTargetGet && LocationPin->LinkedTo.Contains(FindPinChecked(LeftTargetGet, LeftTargetName, EGPD_Output)))
			{
				ExistingLeftConversion = CallFunction;
			}
		}
	}

	if (!LeftTargetGet || !LeftTargetSet || !ComponentToWorld)
	{
		UE_LOG(LogTemp, Error, TEXT("Reach fix: required ABP_Reach nodes were not found"));
		return;
	}

	if (ExistingLeftConversion)
	{
		UE_LOG(LogTemp, Display, TEXT("Reach fix: left target conversion is already present"));
		return;
	}

	Blueprint->Modify();
	EventGraph->Modify();

	UK2Node_CallFunction* LeftConversion = NewObject<UK2Node_CallFunction>(EventGraph);
	EventGraph->AddNode(LeftConversion, true, false);
	LeftConversion->CreateNewGuid();
	LeftConversion->PostPlacedNewNode();
	LeftConversion->SetFromFunction(UKismetMathLibrary::StaticClass()->FindFunctionByName(InverseTransformLocationName));
	LeftConversion->NodePosX = LeftTargetSet->NodePosX - 224;
	LeftConversion->NodePosY = LeftTargetSet->NodePosY + 320;
	LeftConversion->AllocateDefaultPins();

	const UEdGraphSchema_K2* Schema = GetDefault<UEdGraphSchema_K2>();
	UEdGraphPin* TransformPin = FindPinChecked(LeftConversion, TEXT("T"), EGPD_Input);
	Schema->SplitPin(TransformPin, true);

	auto Connect = [Schema](UEdGraphPin* OutputPin, UEdGraphPin* InputPin, const TCHAR* Description) -> bool
	{
		if (!OutputPin || !InputPin || !Schema->TryCreateConnection(OutputPin, InputPin))
		{
			UE_LOG(LogTemp, Error, TEXT("Reach fix: failed to connect %s"), Description);
			return false;
		}
		return true;
	};

	UEdGraphPin* LeftSetValue = FindPinChecked(LeftTargetSet, LeftTargetName, EGPD_Input);
	if (LeftSetValue)
	{
		LeftSetValue->BreakAllPinLinks(true);
	}

	bool bConnected = true;
	bConnected &= Connect(FindPinChecked(ComponentToWorld, TEXT("ReturnValue_Location"), EGPD_Output), FindPinChecked(LeftConversion, TEXT("T_Location"), EGPD_Input), TEXT("mesh location"));
	bConnected &= Connect(FindPinChecked(ComponentToWorld, TEXT("ReturnValue_Rotation"), EGPD_Output), FindPinChecked(LeftConversion, TEXT("T_Rotation"), EGPD_Input), TEXT("mesh rotation"));
	bConnected &= Connect(FindPinChecked(ComponentToWorld, TEXT("ReturnValue_Scale"), EGPD_Output), FindPinChecked(LeftConversion, TEXT("T_Scale"), EGPD_Input), TEXT("mesh scale"));
	bConnected &= Connect(FindPinChecked(LeftTargetGet, LeftTargetName, EGPD_Output), FindPinChecked(LeftConversion, TEXT("Location"), EGPD_Input), TEXT("left world target"));
	bConnected &= Connect(FindPinChecked(LeftConversion, TEXT("ReturnValue"), EGPD_Output), LeftSetValue, TEXT("left mesh-space target"));

	if (!bConnected)
	{
		LeftConversion->DestroyNode();
		UE_LOG(LogTemp, Error, TEXT("Reach fix: graph was not changed because one or more connections failed"));
		return;
	}

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FKismetEditorUtilities::CompileBlueprint(Blueprint, EBlueprintCompileOptions::SkipGarbageCollection);
	UE_LOG(LogTemp, Display, TEXT("Reach fix: added left-hand world-to-mesh conversion to ABP_Reach"));
}

FAutoConsoleCommand GFixReachTargetSpaceCommand(
	TEXT("Prophecy.FixReachTargetSpace"),
	TEXT("Adds the missing left-hand target-space conversion to ABP_Reach."),
	FConsoleCommandDelegate::CreateStatic(&FixReachTargetSpace));

void RemoveMetaHumanRigs(const TArray<FString>& Args)
{
	if (Args.Num() != 1)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman rig removal: expected one character asset path"));
		return;
	}

	UMetaHumanCharacter* Character = LoadObject<UMetaHumanCharacter>(nullptr, *Args[0]);
	if (!Character)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman rig removal: could not load %s"), *Args[0]);
		return;
	}

	UMetaHumanCharacterEditorSubsystem* Subsystem = UMetaHumanCharacterEditorSubsystem::Get();
	if (!Subsystem->IsObjectAddedForEditing(Character) && !Subsystem->TryAddObjectToEdit(Character))
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman rig removal: could not register %s for editing"), *Args[0]);
		return;
	}

	if (Character->bFixedBodyType)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman rig removal: %s uses a fixed body and cannot be refit parametrically"), *Args[0]);
		return;
	}

	if (Character->HasBodyDNA())
	{
		Subsystem->RemoveBodyRig(Character);
	}
	if (Character->HasFaceDNA())
	{
		Subsystem->RemoveFaceRig(Character);
	}

	UE_LOG(LogTemp, Display, TEXT("MetaHuman rig removal: cleared body and face rigs from %s"), *Args[0]);
}

FAutoConsoleCommand GRemoveMetaHumanRigsCommand(
	TEXT("Prophecy.MetaHuman.RemoveRigs"),
	TEXT("Clears body and face rigs from a parametric MetaHuman Character asset."),
	FConsoleCommandWithArgsDelegate::CreateStatic(&RemoveMetaHumanRigs));

void SetMetaHumanBodyJointsFromCarrier(const TArray<FString>& Args)
{
	if (Args.Num() != 2)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman joint import: expected character and carrier skeletal mesh asset paths"));
		return;
	}

	UMetaHumanCharacter* Character = LoadObject<UMetaHumanCharacter>(nullptr, *Args[0]);
	USkeletalMesh* CarrierMesh = LoadObject<USkeletalMesh>(nullptr, *Args[1]);
	if (!Character || !CarrierMesh)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman joint import: could not load character %s or carrier %s"), *Args[0], *Args[1]);
		return;
	}

	UMetaHumanCharacterEditorSubsystem* Subsystem = UMetaHumanCharacterEditorSubsystem::Get();
	if (!Subsystem->IsObjectAddedForEditing(Character) && !Subsystem->TryAddObjectToEdit(Character))
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman joint import: could not register %s for editing"), *Args[0]);
		return;
	}

	TArray<FVector3f> JointTranslations;
	TArray<FVector3f> JointRotations;
	const EImportErrorCode ImportResult = Subsystem->GetJointsForBodyConforming(CarrierMesh, JointTranslations, JointRotations);
	if (ImportResult != EImportErrorCode::Success)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman joint import: carrier extraction failed with code %d"), static_cast<int32>(ImportResult));
		return;
	}

	constexpr bool bImportHelperJoints = true;
	if (!Subsystem->SetBodyJoints(Character, JointTranslations, JointRotations, bImportHelperJoints))
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman joint import: failed to apply carrier joints to %s"), *Args[0]);
		return;
	}

	UE_LOG(LogTemp, Display, TEXT("MetaHuman joint import: applied %d carrier joints to %s"), JointTranslations.Num(), *Args[0]);
}

FAutoConsoleCommand GSetMetaHumanBodyJointsFromCarrierCommand(
	TEXT("Prophecy.MetaHuman.SetBodyJointsFromCarrier"),
	TEXT("Applies MetaHuman-compatible body joints from a carrier skeletal mesh."),
	FConsoleCommandWithArgsDelegate::CreateStatic(&SetMetaHumanBodyJointsFromCarrier));

void BuildUEFNSkeletonMetaHumanBody(const TArray<FString>& Args)
{
	FString SourcePath = TEXT("/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh");
	FString UEFNPath = TEXT("/Game/_mygame/SKM_UEFN_Mannequin");
	FString OutputPath = TEXT("/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody");
	if (Args.Num() != 0 && Args.Num() != 3)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: expected zero arguments or SourceMesh UEFNMesh OutputAsset"));
		return;
	}
	if (Args.Num() == 3)
	{
		SourcePath = Args[0];
		UEFNPath = Args[1];
		OutputPath = Args[2];
	}

	USkeletalMesh* SourceMesh = LoadObject<USkeletalMesh>(nullptr, *SourcePath);
	USkeletalMesh* UEFNMesh = LoadObject<USkeletalMesh>(nullptr, *UEFNPath);
	if (!SourceMesh || !UEFNMesh || !SourceMesh->GetSkeleton() || !UEFNMesh->GetSkeleton())
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: could not load source/UEFN mesh and skeleton"));
		return;
	}
	const int32 TargetLODCount = SourceMesh->GetLODNum();
	if (FindObject<UObject>(nullptr, *OutputPath) || FPackageName::DoesPackageExist(OutputPath))
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: output already exists: %s"), *OutputPath);
		return;
	}

	const FString OutputName = FPackageName::GetLongPackageAssetName(OutputPath);
	const FString OutputPackagePath = FPackageName::GetLongPackagePath(OutputPath);
	USkeletalMesh* OutputMesh = Cast<USkeletalMesh>(
		FAssetToolsModule::GetModule().Get().DuplicateAsset(OutputName, OutputPackagePath, SourceMesh));
	if (!OutputMesh)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: failed to duplicate %s"), *SourcePath);
		return;
	}

	USkeleton* WorkingSkeleton = DuplicateObject<USkeleton>(
		SourceMesh->GetSkeleton(), GetTransientPackage(),
		MakeUniqueObjectName(GetTransientPackage(), USkeleton::StaticClass(), TEXT("UEFNDirectWorkingSkeleton")));
	if (!WorkingSkeleton)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: failed to make isolated working skeleton"));
		return;
	}
	OutputMesh->SetSkeleton(WorkingSkeleton);

	const FReferenceSkeleton& SourceRef = SourceMesh->GetRefSkeleton();
	const FReferenceSkeleton& UEFNRef = UEFNMesh->GetRefSkeleton();
	TSet<FName> KeptBoneNames;
	for (const FMeshBoneInfo& BoneInfo : UEFNRef.GetRawRefBoneInfo())
	{
		if (SourceRef.FindRawBoneIndex(BoneInfo.Name) != INDEX_NONE)
		{
			KeptBoneNames.Add(BoneInfo.Name);
		}
	}

	TMap<FName, FName> RemovedBoneRemap;
	TArray<FName> BonesToRemove;
	for (int32 BoneIndex = 0; BoneIndex < SourceRef.GetRawBoneNum(); ++BoneIndex)
	{
		const FName BoneName = SourceRef.GetBoneName(BoneIndex);
		if (KeptBoneNames.Contains(BoneName))
		{
			continue;
		}
		BonesToRemove.Add(BoneName);
		int32 AncestorIndex = SourceRef.GetParentIndex(BoneIndex);
		while (AncestorIndex != INDEX_NONE && !KeptBoneNames.Contains(SourceRef.GetBoneName(AncestorIndex)))
		{
			AncestorIndex = SourceRef.GetParentIndex(AncestorIndex);
		}
		if (AncestorIndex == INDEX_NONE)
		{
			UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: no surviving ancestor for %s"), *BoneName.ToString());
			return;
		}
		RemovedBoneRemap.Add(BoneName, SourceRef.GetBoneName(AncestorIndex));
	}

	USkinWeightModifier* WeightModifier = NewObject<USkinWeightModifier>();
	if (!WeightModifier->SetSkeletalMesh(OutputMesh))
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: could not load source skin weights"));
		return;
	}
	int32 RemappedVertices = 0;
	int32 RemappedInfluences = 0;
	for (int32 VertexIndex = 0; VertexIndex < WeightModifier->GetNumVertices(); ++VertexIndex)
	{
		const TMap<FName, float> OldWeights = WeightModifier->GetVertexWeights(VertexIndex);
		TMap<FName, float> NewWeights;
		bool bChanged = false;
		for (const TPair<FName, float>& Pair : OldWeights)
		{
			const FName* RemappedName = RemovedBoneRemap.Find(Pair.Key);
			const FName Destination = RemappedName ? *RemappedName : Pair.Key;
			NewWeights.FindOrAdd(Destination) += Pair.Value;
			if (RemappedName)
			{
				bChanged = true;
				++RemappedInfluences;
			}
		}
		if (bChanged)
		{
			++RemappedVertices;
			WeightModifier->SetVertexWeights(VertexIndex, NewWeights, true);
		}
	}
	if (!WeightModifier->CommitWeightsToSkeletalMesh())
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: failed to commit folded skin weights"));
		return;
	}

	USkeletonModifier* SkeletonModifier = NewObject<USkeletonModifier>();
	if (!SkeletonModifier->SetSkeletalMesh(OutputMesh)
		|| !SkeletonModifier->RemoveBones(BonesToRemove, false))
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: failed to prune non-UEFN bones"));
		return;
	}

	TArray<FName> CommonBoneNames;
	TArray<FTransform> UEFNLocalTransforms;
	for (int32 BoneIndex = 0; BoneIndex < UEFNRef.GetRawBoneNum(); ++BoneIndex)
	{
		const FName BoneName = UEFNRef.GetBoneName(BoneIndex);
		if (KeptBoneNames.Contains(BoneName))
		{
			CommonBoneNames.Add(BoneName);
			UEFNLocalTransforms.Add(UEFNRef.GetRawRefBonePose()[BoneIndex]);
		}
	}
	if (!SkeletonModifier->SetBonesTransforms(CommonBoneNames, UEFNLocalTransforms, true)
		|| !SkeletonModifier->CommitSkeletonToSkeletalMesh())
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: failed to apply the pruned UEFN hierarchy"));
		return;
	}

	OutputMesh->Modify();
	OutputMesh->SetSkeleton(UEFNMesh->GetSkeleton());
	OutputMesh->SetPostProcessAnimBlueprint(nullptr);
	OutputMesh->CalculateInvRefMatrices();
	OutputMesh->PostEditChange();

	if (TargetLODCount > 1)
	{
		TArray<int32> LowerLODs;
		LowerLODs.Reserve(TargetLODCount - 1);
		for (int32 LODIndex = 1; LODIndex < TargetLODCount; ++LODIndex)
		{
			LowerLODs.Add(LODIndex);
		}
		if (!USkeletalMeshEditorSubsystem::RemoveLODs(OutputMesh, LowerLODs)
			|| !USkeletalMeshEditorSubsystem::RegenerateLOD(OutputMesh, TargetLODCount, true, false))
		{
			UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: failed to regenerate lower LODs from corrected LOD0"));
			return;
		}
		OutputMesh->CalculateInvRefMatrices();
		OutputMesh->PostEditChange();
	}
	OutputMesh->MarkPackageDirty();

	const FReferenceSkeleton& FinalRef = OutputMesh->GetRefSkeleton();
	bool bHierarchyMatches = FinalRef.GetRawBoneNum() == CommonBoneNames.Num();
	double MaxLocalTranslationError = 0.0;
	double MaxLocalRotationErrorDegrees = 0.0;
	for (const FName BoneName : CommonBoneNames)
	{
		const int32 FinalIndex = FinalRef.FindRawBoneIndex(BoneName);
		const int32 TargetIndex = UEFNRef.FindRawBoneIndex(BoneName);
		if (FinalIndex == INDEX_NONE || TargetIndex == INDEX_NONE)
		{
			bHierarchyMatches = false;
			continue;
		}
		const int32 FinalParentIndex = FinalRef.GetParentIndex(FinalIndex);
		const int32 TargetParentIndex = UEFNRef.GetParentIndex(TargetIndex);
		const FName FinalParent = FinalParentIndex == INDEX_NONE ? NAME_None : FinalRef.GetBoneName(FinalParentIndex);
		const FName TargetParent = TargetParentIndex == INDEX_NONE ? NAME_None : UEFNRef.GetBoneName(TargetParentIndex);
		bHierarchyMatches &= FinalParent == TargetParent;
		const FTransform& FinalTransform = FinalRef.GetRawRefBonePose()[FinalIndex];
		const FTransform& TargetTransform = UEFNRef.GetRawRefBonePose()[TargetIndex];
		MaxLocalTranslationError = FMath::Max(MaxLocalTranslationError,
			FVector::Distance(FinalTransform.GetTranslation(), TargetTransform.GetTranslation()));
		MaxLocalRotationErrorDegrees = FMath::Max(MaxLocalRotationErrorDegrees,
			FMath::RadiansToDegrees(FinalTransform.GetRotation().AngularDistance(TargetTransform.GetRotation())));
	}

	TArray<UPackage*> PackagesToSave = {OutputMesh->GetOutermost()};
	FEditorFileUtils::PromptForCheckoutAndSave(PackagesToSave, false, false);
	UE_LOG(LogTemp, Display,
		TEXT("MetaHuman UEFN body: DONE output=%s bones=%d skeleton=%s lods=%d remapped_vertices=%d remapped_influences=%d hierarchy=%s max_local_cm=%.9g max_local_deg=%.9g"),
		*OutputMesh->GetPathName(), FinalRef.GetRawBoneNum(), *OutputMesh->GetSkeleton()->GetPathName(),
		OutputMesh->GetLODNum(), RemappedVertices, RemappedInfluences, bHierarchyMatches ? TEXT("exact") : TEXT("MISMATCH"),
		MaxLocalTranslationError, MaxLocalRotationErrorDegrees);
}

FAutoConsoleCommand GBuildUEFNSkeletonMetaHumanBodyCommand(
	TEXT("Prophecy.MetaHuman.BuildUEFNBody"),
	TEXT("Duplicates the fitted MetaHuman body, folds helper weights to UEFN ancestors, prunes to common UEFN bones, regenerates lower LODs, and assigns the UEFN Skeleton asset."),
	FConsoleCommandWithArgsDelegate::CreateStatic(&BuildUEFNSkeletonMetaHumanBody));

void BuildUEFNSkeletonMetaHumanBlueprint(const TArray<FString>& Args)
{
	FString SourcePath = TEXT("/Game/MetaHumans/test_UEFNExactFull/BP_test_UEFNExactFull");
	FString BodyPath = TEXT("/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody");
	FString FaceAnimPath = TEXT("/Game/MetaHumans/Common/Face/Face_AnimBP");
	FString OutputPath = TEXT("/Game/_mygame/MetaHumans/BP_test_UEFNDirect");
	if (Args.Num() != 0 && Args.Num() != 4)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN blueprint: expected zero arguments or SourceBlueprint BodyMesh FaceAnimBlueprint OutputBlueprint"));
		return;
	}
	if (Args.Num() == 4)
	{
		SourcePath = Args[0];
		BodyPath = Args[1];
		FaceAnimPath = Args[2];
		OutputPath = Args[3];
	}

	UBlueprint* SourceBlueprint = LoadObject<UBlueprint>(nullptr, *SourcePath);
	USkeletalMesh* BodyMesh = LoadObject<USkeletalMesh>(nullptr, *BodyPath);
	UBlueprint* FaceAnimBlueprint = LoadObject<UBlueprint>(nullptr, *FaceAnimPath);
	if (!SourceBlueprint || !BodyMesh || !FaceAnimBlueprint || !FaceAnimBlueprint->GeneratedClass)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN blueprint: could not load source blueprint, body mesh, or face AnimBP"));
		return;
	}
	if (FindObject<UObject>(nullptr, *OutputPath) || FPackageName::DoesPackageExist(OutputPath))
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN blueprint: output already exists: %s"), *OutputPath);
		return;
	}

	const FString OutputName = FPackageName::GetLongPackageAssetName(OutputPath);
	const FString OutputPackagePath = FPackageName::GetLongPackagePath(OutputPath);
	UBlueprint* OutputBlueprint = Cast<UBlueprint>(
		FAssetToolsModule::GetModule().Get().DuplicateAsset(OutputName, OutputPackagePath, SourceBlueprint));
	if (!OutputBlueprint || !OutputBlueprint->SimpleConstructionScript)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN blueprint: failed to duplicate %s"), *SourcePath);
		return;
	}

	USkeletalMeshComponent* BodyTemplate = nullptr;
	USkeletalMeshComponent* FaceTemplate = nullptr;
	for (USCS_Node* Node : OutputBlueprint->SimpleConstructionScript->GetAllNodes())
	{
		if (!Node)
		{
			continue;
		}
		USkeletalMeshComponent* ComponentTemplate = Cast<USkeletalMeshComponent>(Node->ComponentTemplate);
		if (Node->GetVariableName() == TEXT("Body"))
		{
			BodyTemplate = ComponentTemplate;
		}
		else if (Node->GetVariableName() == TEXT("Face"))
		{
			FaceTemplate = ComponentTemplate;
		}
	}
	if (!BodyTemplate || !FaceTemplate)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN blueprint: Body or Face component template was not found"));
		return;
	}

	OutputBlueprint->Modify();
	BodyTemplate->Modify();
	BodyTemplate->SetSkeletalMeshAsset(BodyMesh);
	BodyTemplate->SetAnimInstanceClass(nullptr);
	BodyTemplate->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	FaceTemplate->Modify();
	FaceTemplate->SetAnimInstanceClass(FaceAnimBlueprint->GeneratedClass);

	UEdGraph* ConstructionGraph = FBlueprintEditorUtils::FindUserConstructionScript(OutputBlueprint);
	UK2Node_FunctionEntry* EntryNode = nullptr;
	if (ConstructionGraph)
	{
		for (UEdGraphNode* Node : ConstructionGraph->Nodes)
		{
			if (UK2Node_FunctionEntry* Candidate = Cast<UK2Node_FunctionEntry>(Node))
			{
				EntryNode = Candidate;
				break;
			}
		}
	}
	if (!ConstructionGraph || !EntryNode)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN blueprint: construction script entry was not found"));
		return;
	}

	ConstructionGraph->Modify();
	UK2Node_VariableGet* FaceGet = NewObject<UK2Node_VariableGet>(ConstructionGraph);
	ConstructionGraph->AddNode(FaceGet, true, false);
	FaceGet->CreateNewGuid();
	FaceGet->PostPlacedNewNode();
	FaceGet->VariableReference.SetSelfMember(TEXT("Face"));
	FaceGet->NodePosX = EntryNode->NodePosX + 240;
	FaceGet->NodePosY = EntryNode->NodePosY + 160;
	FaceGet->AllocateDefaultPins();

	UK2Node_CallFunction* ReinitializeFace = NewObject<UK2Node_CallFunction>(ConstructionGraph);
	ConstructionGraph->AddNode(ReinitializeFace, true, false);
	ReinitializeFace->CreateNewGuid();
	ReinitializeFace->PostPlacedNewNode();
	ReinitializeFace->SetFromFunction(USkeletalMeshComponent::StaticClass()->FindFunctionByName(
		GET_FUNCTION_NAME_CHECKED(USkeletalMeshComponent, SetAnimInstanceClass)));
	ReinitializeFace->NodePosX = EntryNode->NodePosX + 480;
	ReinitializeFace->NodePosY = EntryNode->NodePosY;
	ReinitializeFace->AllocateDefaultPins();

	const UEdGraphSchema_K2* Schema = GetDefault<UEdGraphSchema_K2>();
	UEdGraphPin* FaceOutput = FindPinChecked(FaceGet, TEXT("Face"), EGPD_Output);
	UEdGraphPin* FaceTarget = FindPinChecked(ReinitializeFace, UEdGraphSchema_K2::PN_Self, EGPD_Input);
	UEdGraphPin* FaceClass = FindPinChecked(ReinitializeFace, TEXT("NewClass"), EGPD_Input);
	UEdGraphPin* CallExec = FindPinChecked(ReinitializeFace, UEdGraphSchema_K2::PN_Execute, EGPD_Input);
	UEdGraphPin* CallThen = FindPinChecked(ReinitializeFace, UEdGraphSchema_K2::PN_Then, EGPD_Output);
	UEdGraphPin* InsertionExec = FindPinChecked(EntryNode, UEdGraphSchema_K2::PN_Then, EGPD_Output);
	TSet<UEdGraphNode*> TraversedNodes;
	while (InsertionExec && InsertionExec->LinkedTo.Num() == 1)
	{
		UEdGraphNode* NextNode = InsertionExec->LinkedTo[0]->GetOwningNode();
		if (!NextNode || TraversedNodes.Contains(NextNode))
		{
			break;
		}
		TraversedNodes.Add(NextNode);
		UEdGraphPin* NextThen = FindPinChecked(NextNode, UEdGraphSchema_K2::PN_Then, EGPD_Output);
		if (!NextThen)
		{
			break;
		}
		InsertionExec = NextThen;
	}
	if (!FaceOutput || !FaceTarget || !FaceClass || !CallExec || !CallThen || !InsertionExec)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN blueprint: required construction script pins were not found"));
		return;
	}
	FaceClass->DefaultObject = FaceAnimBlueprint->GeneratedClass;
	TArray<UEdGraphPin*> ExistingExecLinks = InsertionExec->LinkedTo;
	InsertionExec->BreakAllPinLinks(true);
	bool bConnected = Schema->TryCreateConnection(FaceOutput, FaceTarget)
		&& Schema->TryCreateConnection(InsertionExec, CallExec);
	for (UEdGraphPin* ExistingInput : ExistingExecLinks)
	{
		bConnected &= Schema->TryCreateConnection(CallThen, ExistingInput);
	}
	if (!bConnected)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN blueprint: failed to connect face reinitialization nodes"));
		return;
	}

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(OutputBlueprint);
	FKismetEditorUtilities::CompileBlueprint(OutputBlueprint, EBlueprintCompileOptions::SkipGarbageCollection);
	OutputBlueprint->MarkPackageDirty();
	TArray<UPackage*> PackagesToSave = {OutputBlueprint->GetOutermost()};
	FEditorFileUtils::PromptForCheckoutAndSave(PackagesToSave, false, false);
	UE_LOG(LogTemp, Display, TEXT("MetaHuman UEFN blueprint: DONE output=%s body=%s face_anim=%s"),
		*OutputBlueprint->GetPathName(), *BodyMesh->GetPathName(), *FaceAnimBlueprint->GeneratedClass->GetPathName());
}

FAutoConsoleCommand GBuildUEFNSkeletonMetaHumanBlueprintCommand(
	TEXT("Prophecy.MetaHuman.BuildUEFNBlueprint"),
	TEXT("Duplicates the fitted MetaHuman Blueprint, installs the UEFN-skeleton body, and reinitializes Face_AnimBP after construction."),
	FConsoleCommandWithArgsDelegate::CreateStatic(&BuildUEFNSkeletonMetaHumanBlueprint));
}

class FProphecyEditorModule final : public IModuleInterface
{
};

IMPLEMENT_MODULE(FProphecyEditorModule, ProphecyEditor)
