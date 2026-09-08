#include "BoneWeights.h"
#include "Animation/Skeleton.h"
#include "AssetToolsModule.h"
#include "Components/SkeletalMeshComponent.h"
#include "CoreMinimal.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/Blueprint.h"
#include "Engine/Engine.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "FileHelpers.h"
#include "GameFramework/Actor.h"
#include "HAL/IConsoleManager.h"
#include "IAssetTools.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Event.h"
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
#include "ProphecyPhysicsConstraintBlueprintLibrary.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "Rendering/SkeletalMeshLODRenderData.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Rendering/SkinWeightVertexBuffer.h"
#include "SkeletalMeshEditorSubsystem.h"
#include "SkeletalMeshAttributes.h"
#include "SkeletalMeshOperations.h"
#include "SkeletalMeshTypes.h"
#include "SkeletonModifier.h"

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

	TArray<FName> BonesToRemove;
	for (int32 BoneIndex = 0; BoneIndex < SourceRef.GetRawBoneNum(); ++BoneIndex)
	{
		const FName BoneName = SourceRef.GetBoneName(BoneIndex);
		if (KeptBoneNames.Contains(BoneName))
		{
			continue;
		}
		BonesToRemove.Add(BoneName);
	}

	const FMeshDescription* UEFNMeshDescription = UEFNMesh->GetMeshDescription(0);
	FMeshDescription* OutputMeshDescription = OutputMesh->GetMeshDescription(0);
	if (!UEFNMeshDescription || !OutputMeshDescription)
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: missing LOD0 mesh description for skin-weight transfer"));
		return;
	}
	TMap<int32, int32> UEFNToMetaHumanBoneIndex;
	for (int32 UEFNBoneIndex = 0; UEFNBoneIndex < UEFNRef.GetRawBoneNum(); ++UEFNBoneIndex)
	{
		const int32 MetaHumanBoneIndex = SourceRef.FindRawBoneIndex(UEFNRef.GetBoneName(UEFNBoneIndex));
		if (MetaHumanBoneIndex != INDEX_NONE)
		{
			UEFNToMetaHumanBoneIndex.Add(UEFNBoneIndex, MetaHumanBoneIndex);
		}
	}
	const FName DefaultSkinWeightProfile = FSkeletalMeshAttributes::DefaultSkinWeightProfileName;
	if (!FSkeletalMeshOperations::CopySkinWeightAttributeFromMesh(
			*UEFNMeshDescription,
			*OutputMeshDescription,
			DefaultSkinWeightProfile,
			DefaultSkinWeightProfile,
			&UEFNToMetaHumanBoneIndex)
		|| !OutputMesh->CommitMeshDescription(0))
	{
		UE_LOG(LogTemp, Error, TEXT("MetaHuman UEFN body: failed to transfer UEFN skin weights onto the fitted MetaHuman surface"));
		return;
	}
	const int32 TransferredVertices = OutputMeshDescription->Vertices().Num();

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
		TEXT("MetaHuman UEFN body: DONE output=%s bones=%d skeleton=%s lods=%d transferred_vertices=%d hierarchy=%s max_local_cm=%.9g max_local_deg=%.9g"),
		*OutputMesh->GetPathName(), FinalRef.GetRawBoneNum(), *OutputMesh->GetSkeleton()->GetPathName(),
		OutputMesh->GetLODNum(), TransferredVertices, bHierarchyMatches ? TEXT("exact") : TEXT("MISMATCH"),
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

void InstallPotenceRetractableComponent()
{
	constexpr TCHAR AssetPath[] = TEXT("/Game/_mygame/assets/hanging/A_Potence.A_Potence");
	constexpr TCHAR ComponentClassPath[] = TEXT("/Script/GameAnimationSample3.ProphecyRetractableSkeletalMeshComponent");
	const FName ComponentName(TEXT("SKM_RopeHang"));
	UClass* RetractableComponentClass = LoadClass<USkeletalMeshComponent>(nullptr, ComponentClassPath);
	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, AssetPath);
	if (!RetractableComponentClass || !Blueprint || !Blueprint->SimpleConstructionScript || !Blueprint->GeneratedClass)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence component install: could not load %s or %s"), AssetPath, ComponentClassPath);
		return;
	}

	USCS_Node* ComponentNode = Blueprint->SimpleConstructionScript->FindSCSNode(ComponentName);
	USkeletalMeshComponent* OldTemplate = ComponentNode
		? Cast<USkeletalMeshComponent>(ComponentNode->ComponentTemplate)
		: nullptr;
	if (!ComponentNode || !OldTemplate)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence component install: %s component template was not found"), *ComponentName.ToString());
		return;
	}
	if (OldTemplate->IsA(RetractableComponentClass))
	{
		Blueprint->Modify();
		FBlueprintEditorUtils::RefreshAllNodes(Blueprint);
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FKismetEditorUtilities::CompileBlueprint(Blueprint, EBlueprintCompileOptions::SkipGarbageCollection);
		if (Blueprint->Status == BS_Error)
		{
			UE_LOG(LogTemp, Error,
				TEXT("Potence component install: refresh FAILED, blueprint_status=%d"),
				static_cast<int32>(Blueprint->Status));
		}
		else
		{
			UE_LOG(LogTemp, Display,
				TEXT("Potence component install: refreshed existing retractable component, blueprint_status=%d"),
				static_cast<int32>(Blueprint->Status));
		}
		return;
	}

	Blueprint->Modify();
	ComponentNode->Modify();
	OldTemplate->Modify();

	const FName TemplateName = OldTemplate->GetFName();
	UObject* TemplateOuter = OldTemplate->GetOuter();
	const EObjectFlags TemplateFlags = OldTemplate->GetFlags();
	UActorComponent* NewTemplate =
		NewObject<UActorComponent>(
			GetTransientPackage(),
			RetractableComponentClass,
			NAME_None,
			TemplateFlags);
	UEngine::CopyPropertiesForUnrelatedObjects(OldTemplate, NewTemplate);

	OldTemplate->Rename(
		nullptr,
		GetTransientPackage(),
		REN_DoNotDirty | REN_DontCreateRedirectors | REN_NonTransactional);
	OldTemplate->MarkAsGarbage();
	NewTemplate->Rename(
		*TemplateName.ToString(),
		TemplateOuter,
		REN_DoNotDirty | REN_DontCreateRedirectors | REN_NonTransactional);

	ComponentNode->ComponentClass = RetractableComponentClass;
	ComponentNode->ComponentTemplate = NewTemplate;
	FBlueprintEditorUtils::RefreshAllNodes(Blueprint);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FKismetEditorUtilities::CompileBlueprint(Blueprint, EBlueprintCompileOptions::SkipGarbageCollection);

	const bool bInstalled = ComponentNode->ComponentTemplate
		&& ComponentNode->ComponentTemplate->IsA(RetractableComponentClass)
		&& Blueprint->Status != BS_Error;
	if (bInstalled)
	{
		UE_LOG(LogTemp, Display,
			TEXT("Potence component install: DONE class=%s blueprint_status=%d (asset remains unsaved for validation)"),
			*GetNameSafe(ComponentNode->ComponentTemplate->GetClass()),
			static_cast<int32>(Blueprint->Status));
	}
	else
	{
		UE_LOG(LogTemp, Error,
			TEXT("Potence component install: FAILED class=%s blueprint_status=%d"),
			*GetNameSafe(ComponentNode->ComponentTemplate ? ComponentNode->ComponentTemplate->GetClass() : nullptr),
			static_cast<int32>(Blueprint->Status));
	}
}

FAutoConsoleCommand GInstallPotenceRetractableComponentCommand(
	TEXT("Prophecy.InstallPotenceRetractableComponent"),
	TEXT("Reclasses only A_Potence.SKM_RopeHang to the single-mesh retractable skeletal component."),
	FConsoleCommandDelegate::CreateStatic(&InstallPotenceRetractableComponent));

void SimplifyPotenceShrinkRopeGraph()
{
	constexpr TCHAR AssetPath[] = TEXT("/Game/_mygame/assets/hanging/A_Potence.A_Potence");
	const FName GraphName(TEXT("ShrinkRope"));
	const FName RopeComponentName(TEXT("SKM_RopeHang"));
	const FName UpdateFunctionName(TEXT("UpdatePotenceRopePhysics"));

	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, AssetPath);
	UEdGraph* ShrinkGraph = nullptr;
	if (Blueprint)
	{
		for (UEdGraph* Graph : Blueprint->FunctionGraphs)
		{
			if (Graph && Graph->GetFName() == GraphName)
			{
				ShrinkGraph = Graph;
				break;
			}
		}
	}
	if (!Blueprint || !ShrinkGraph)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence ShrinkRope cleanup: asset or function graph was not found"));
		return;
	}

	UK2Node_FunctionEntry* Entry = nullptr;
	UK2Node_VariableGet* RopeGet = nullptr;
	UK2Node_CallFunction* UpdateCall = nullptr;
	for (UEdGraphNode* Node : ShrinkGraph->Nodes)
	{
		if (!Entry)
		{
			Entry = Cast<UK2Node_FunctionEntry>(Node);
		}
		if (UK2Node_VariableGet* VariableGet = Cast<UK2Node_VariableGet>(Node);
			!RopeGet && VariableGet && VariableGet->VariableReference.GetMemberName() == RopeComponentName)
		{
			RopeGet = VariableGet;
		}
		if (UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node);
			!UpdateCall && IsCallTo(Call, UpdateFunctionName))
		{
			UpdateCall = Call;
		}
	}
	if (!Entry || !RopeGet || !UpdateCall)
	{
		UE_LOG(LogTemp, Error,
			TEXT("Potence ShrinkRope cleanup: required nodes missing entry=%s rope_get=%s update=%s"),
			*GetNameSafe(Entry), *GetNameSafe(RopeGet), *GetNameSafe(UpdateCall));
		return;
	}

	Blueprint->Modify();
	ShrinkGraph->Modify();
	const TSet<UEdGraphNode*> NodesToKeep = {Entry, RopeGet, UpdateCall};
	const TArray<UEdGraphNode*> ExistingNodes = ShrinkGraph->Nodes;
	int32 RemovedNodeCount = 0;
	for (UEdGraphNode* Node : ExistingNodes)
	{
		if (Node && !NodesToKeep.Contains(Node))
		{
			Node->Modify();
			Node->DestroyNode();
			++RemovedNodeCount;
		}
	}

	UEdGraphPin* EntryThen = Entry->FindPin(UEdGraphSchema_K2::PN_Then, EGPD_Output);
	UEdGraphPin* UpdateExec = UpdateCall->GetExecPin();
	if (!EntryThen || !UpdateExec)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence ShrinkRope cleanup: execution pins were not found"));
		return;
	}
	EntryThen->BreakAllPinLinks();
	UpdateExec->BreakAllPinLinks();
	const UEdGraphSchema* Schema = ShrinkGraph->GetSchema();
	if (!Schema || !Schema->TryCreateConnection(EntryThen, UpdateExec))
	{
		UE_LOG(LogTemp, Error, TEXT("Potence ShrinkRope cleanup: could not connect entry to native update"));
		return;
	}

	FBlueprintEditorUtils::RefreshAllNodes(Blueprint);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FKismetEditorUtilities::CompileBlueprint(Blueprint, EBlueprintCompileOptions::SkipGarbageCollection);

	int32 UpdateCallCount = 0;
	int32 LegacySwapCount = 0;
	for (UEdGraphNode* Node : ShrinkGraph->Nodes)
	{
		if (const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node))
		{
			UpdateCallCount += IsCallTo(Call, UpdateFunctionName) ? 1 : 0;
			LegacySwapCount +=
				(IsCallTo(Call, TEXT("SetSkeletalMeshAsset")) || IsCallTo(Call, TEXT("SetAnimInstanceClass"))) ? 1 : 0;
		}
	}
	if (Blueprint->Status == BS_Error || UpdateCallCount != 1 || LegacySwapCount != 0)
	{
		UE_LOG(LogTemp, Error,
			TEXT("Potence ShrinkRope cleanup: FAILED status=%d nodes=%d updates=%d legacy_swaps=%d"),
			static_cast<int32>(Blueprint->Status), ShrinkGraph->Nodes.Num(), UpdateCallCount, LegacySwapCount);
		return;
	}

	UE_LOG(LogTemp, Display,
		TEXT("Potence ShrinkRope cleanup: DONE status=%d nodes=%d removed=%d updates=%d legacy_swaps=%d (asset remains unsaved for validation)"),
		static_cast<int32>(Blueprint->Status), ShrinkGraph->Nodes.Num(), RemovedNodeCount, UpdateCallCount, LegacySwapCount);
}

FAutoConsoleCommand GSimplifyPotenceShrinkRopeGraphCommand(
	TEXT("Prophecy.SimplifyPotenceShrinkRopeGraph"),
	TEXT("Removes the obsolete runtime mesh/AnimBP swap from A_Potence.ShrinkRope and keeps one native rope update."),
	FConsoleCommandDelegate::CreateStatic(&SimplifyPotenceShrinkRopeGraph));

void AuditPotenceRopeTerminalWeights()
{
	constexpr TCHAR MeshPath[] = TEXT("/Game/_mygame/assets/hanging/SKM_RopeHang.SKM_RopeHang");
	USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, MeshPath);
	const FSkeletalMeshRenderData* RenderData = Mesh ? Mesh->GetResourceForRendering() : nullptr;
	if (!Mesh || !RenderData || RenderData->LODRenderData.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("Potence rope weight audit: render data unavailable"));
		return;
	}

	const FSkeletalMeshLODRenderData& LOD = RenderData->LODRenderData[0];
	const FPositionVertexBuffer& Positions = LOD.StaticVertexBuffers.PositionVertexBuffer;
	const FSkinWeightVertexBuffer& Weights = LOD.SkinWeightVertexBuffer;
	float MinZ = TNumericLimits<float>::Max();
	float MaxZ = TNumericLimits<float>::Lowest();
	for (uint32 VertexIndex = 0; VertexIndex < Positions.GetNumVertices(); ++VertexIndex)
	{
		const float Z = Positions.VertexPosition(VertexIndex).Z;
		MinZ = FMath::Min(MinZ, Z);
		MaxZ = FMath::Max(MaxZ, Z);
	}

	auto AuditRing = [&](const TCHAR* RingName, const float RingZ)
	{
		TMap<FName, uint64> WeightByBone;
		TMap<FName, int32> DominantCountByBone;
		int32 RingVertexCount = 0;
		for (const FSkelMeshRenderSection& Section : LOD.RenderSections)
		{
			const uint32 SectionEnd = Section.BaseVertexIndex + Section.NumVertices;
			for (uint32 VertexIndex = Section.BaseVertexIndex; VertexIndex < SectionEnd; ++VertexIndex)
			{
				if (!FMath::IsNearlyEqual(Positions.VertexPosition(VertexIndex).Z, RingZ, 0.05f))
				{
					continue;
				}

				++RingVertexCount;
				const FSkinWeightInfo SkinWeightInfo = Weights.GetVertexSkinWeights(VertexIndex);
				uint16 DominantWeight = 0;
				FName DominantBone = NAME_None;
				for (int32 InfluenceIndex = 0; InfluenceIndex < MAX_TOTAL_INFLUENCES; ++InfluenceIndex)
				{
					const uint16 Weight = SkinWeightInfo.InfluenceWeights[InfluenceIndex];
					const int32 SectionBoneIndex = static_cast<int32>(SkinWeightInfo.InfluenceBones[InfluenceIndex]);
					if (Weight == 0 || !Section.BoneMap.IsValidIndex(SectionBoneIndex))
					{
						continue;
					}
					const int32 SkeletonBoneIndex = Section.BoneMap[SectionBoneIndex];
					const FName BoneName = Mesh->GetRefSkeleton().GetBoneName(SkeletonBoneIndex);
					WeightByBone.FindOrAdd(BoneName) += Weight;
					if (Weight > DominantWeight)
					{
						DominantWeight = Weight;
						DominantBone = BoneName;
					}
				}
				DominantCountByBone.FindOrAdd(DominantBone)++;
			}
		}

		WeightByBone.ValueSort([](const uint64 Left, const uint64 Right) { return Left > Right; });
		DominantCountByBone.ValueSort([](const int32 Left, const int32 Right) { return Left > Right; });
		FString WeightSummary;
		for (const TPair<FName, uint64>& Pair : WeightByBone)
		{
			WeightSummary += FString::Printf(TEXT("%s=%llu "), *Pair.Key.ToString(), Pair.Value);
		}
		FString DominantSummary;
		for (const TPair<FName, int32>& Pair : DominantCountByBone)
		{
			DominantSummary += FString::Printf(TEXT("%s=%d "), *Pair.Key.ToString(), Pair.Value);
		}
		UE_LOG(LogTemp, Display,
			TEXT("Potence rope weight audit: %s z=%.3f vertices=%d total_weights=[%s] dominant=[%s]"),
			RingName, RingZ, RingVertexCount, *WeightSummary, *DominantSummary);
	};

	AuditRing(TEXT("min_z_ring"), MinZ);
	AuditRing(TEXT("max_z_ring"), MaxZ);
}

FAutoConsoleCommand GAuditPotenceRopeTerminalWeightsCommand(
	TEXT("Prophecy.AuditPotenceRopeTerminalWeights"),
	TEXT("Reports which skeleton bones actually skin the two terminal vertex rings of SKM_RopeHang."),
	FConsoleCommandDelegate::CreateStatic(&AuditPotenceRopeTerminalWeights));

void RepairPotenceRopeTerminalWeights()
{
	constexpr TCHAR MeshPath[] = TEXT("/Game/_mygame/assets/hanging/SKM_RopeHang.SKM_RopeHang");
	const FName TerminalBoneName(TEXT("joint27"));
	USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, MeshPath);
	FMeshDescription* MeshDescription = Mesh ? Mesh->GetMeshDescription(0) : nullptr;
	const int32 TerminalBoneIndex = Mesh ? Mesh->GetRefSkeleton().FindBoneIndex(TerminalBoneName) : INDEX_NONE;
	if (!Mesh || !MeshDescription || TerminalBoneIndex == INDEX_NONE)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence rope terminal repair: mesh description or joint27 unavailable"));
		return;
	}

	FSkeletalMeshAttributes Attributes(*MeshDescription);
	FSkinWeightsVertexAttributesRef SkinWeights = Attributes.GetVertexSkinWeights();
	if (!SkinWeights.IsValid())
	{
		UE_LOG(LogTemp, Error, TEXT("Potence rope terminal repair: default skin-weight attribute unavailable"));
		return;
	}

	const TVertexAttributesRef<FVector3f> Positions = MeshDescription->GetVertexPositions();
	float MaxZ = TNumericLimits<float>::Lowest();
	for (const FVertexID VertexID : MeshDescription->Vertices().GetElementIDs())
	{
		MaxZ = FMath::Max(MaxZ, Positions[VertexID].Z);
	}

	Mesh->Modify();
	int32 ChangedVertexCount = 0;
	{
		FScopedSkeletalMeshPostEditChange PostEditChangeScope(Mesh);
		const TArray<UE::AnimationCore::FBoneWeight> TerminalWeights = {
			UE::AnimationCore::FBoneWeight(TerminalBoneIndex, 1.0f)};
		for (const FVertexID VertexID : MeshDescription->Vertices().GetElementIDs())
		{
			if (FMath::IsNearlyEqual(Positions[VertexID].Z, MaxZ, 0.05f))
			{
				SkinWeights.Set(VertexID, MakeArrayView(TerminalWeights));
				++ChangedVertexCount;
			}
		}
		Mesh->CommitMeshDescription(0);
	}
	Mesh->MarkPackageDirty();

	UE_LOG(LogTemp, Display,
		TEXT("Potence rope terminal repair: DONE z=%.3f changed_vertices=%d bone=%s (asset remains unsaved for validation)"),
		MaxZ, ChangedVertexCount, *TerminalBoneName.ToString());
}

FAutoConsoleCommand GRepairPotenceRopeTerminalWeightsCommand(
	TEXT("Prophecy.RepairPotenceRopeTerminalWeights"),
	TEXT("Weights only the terminal vertex ring of the existing SKM_RopeHang asset rigidly to joint27."),
	FConsoleCommandDelegate::CreateStatic(&RepairPotenceRopeTerminalWeights));

void InstallPotenceNooseWeld()
{
	constexpr TCHAR AssetPath[] = TEXT("/Game/_mygame/assets/hanging/A_Potence.A_Potence");
	const FName OldFunctionName(TEXT("SetConstrainedComponents"));
	const FName WeldFunctionName = GET_FUNCTION_NAME_CHECKED(
		UProphecyPhysicsConstraintBlueprintLibrary, WeldNooseToRopeEnd);

	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, AssetPath);
	UEdGraph* ConstructionGraph = Blueprint
		? FBlueprintEditorUtils::FindUserConstructionScript(Blueprint)
		: nullptr;
	if (!Blueprint || !ConstructionGraph)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence noose weld install: ConstructionScript was not found"));
		return;
	}

	UK2Node_CallFunction* OldCall = nullptr;
	UK2Node_CallFunction* ExistingWeldCall = nullptr;
	for (UEdGraphNode* Node : ConstructionGraph->Nodes)
	{
		if (UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node))
		{
			if (IsCallTo(Call, OldFunctionName))
			{
				OldCall = Call;
			}
			else if (IsCallTo(Call, WeldFunctionName))
			{
				ExistingWeldCall = Call;
			}
		}
	}

	if (ExistingWeldCall)
	{
		UE_LOG(LogTemp, Display, TEXT("Potence noose weld install: weld node already present"));
		return;
	}
	if (!OldCall)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence noose weld install: SetConstrainedComponents node was not found"));
		return;
	}

	UFunction* WeldFunction = UProphecyPhysicsConstraintBlueprintLibrary::StaticClass()->FindFunctionByName(WeldFunctionName);
	if (!WeldFunction)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence noose weld install: native weld function was not reflected"));
		return;
	}

	Blueprint->Modify();
	ConstructionGraph->Modify();
	OldCall->Modify();

	FGraphNodeCreator<UK2Node_CallFunction> NodeCreator(*ConstructionGraph);
	UK2Node_CallFunction* WeldCall = NodeCreator.CreateNode();
	WeldCall->SetFromFunction(WeldFunction);
	WeldCall->NodePosX = OldCall->NodePosX;
	WeldCall->NodePosY = OldCall->NodePosY;
	WeldCall->NodeComment = TEXT("One-time rigid weld: no extra solver joint or per-frame correction");
	WeldCall->bCommentBubbleVisible = true;
	NodeCreator.Finalize();

	const UEdGraphSchema* Schema = ConstructionGraph->GetSchema();
	auto FindVariableOutput = [ConstructionGraph](const FName VariableName) -> UEdGraphPin*
	{
		for (UEdGraphNode* Node : ConstructionGraph->Nodes)
		{
			if (UK2Node_VariableGet* VariableGet = Cast<UK2Node_VariableGet>(Node);
				VariableGet && VariableGet->VariableReference.GetMemberName() == VariableName)
			{
				if (UEdGraphPin* NamedPin = VariableGet->FindPin(VariableName, EGPD_Output))
				{
					return NamedPin;
				}
				for (UEdGraphPin* Pin : VariableGet->Pins)
				{
					if (Pin && Pin->Direction == EGPD_Output
						&& Pin->PinType.PinCategory != UEdGraphSchema_K2::PC_Exec)
					{
						return Pin;
					}
				}
			}
		}
		return nullptr;
	};
	auto MoveLinks = [Schema](UEdGraphPin* From, UEdGraphPin* To) -> bool
	{
		if (!Schema || !From || !To)
		{
			return false;
		}
		const TArray<UEdGraphPin*> LinkedPins = From->LinkedTo;
		From->BreakAllPinLinks();
		bool bConnected = true;
		for (UEdGraphPin* LinkedPin : LinkedPins)
		{
			bConnected &= Schema->TryCreateConnection(LinkedPin, To);
		}
		return bConnected;
	};
	auto MoveLinksOrConnect = [Schema, &MoveLinks](
		UEdGraphPin* From,
		UEdGraphPin* FallbackOutput,
		UEdGraphPin* To) -> bool
	{
		if (!Schema || !To)
		{
			return false;
		}
		if (From && !From->LinkedTo.IsEmpty())
		{
			return MoveLinks(From, To);
		}
		return FallbackOutput && Schema->TryCreateConnection(FallbackOutput, To);
	};

	UEdGraphPin* FallbackExec = nullptr;
	int32 BestExecDistance = TNumericLimits<int32>::Max();
	for (UEdGraphNode* Node : ConstructionGraph->Nodes)
	{
		if (UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node);
			Call && IsCallTo(Call, TEXT("K2_SetWorldRotation")))
		{
			UEdGraphPin* ThenPin = Call->GetThenPin();
			const int32 Distance = FMath::Abs(Call->NodePosX - OldCall->NodePosX)
				+ FMath::Abs(Call->NodePosY - OldCall->NodePosY);
			if (ThenPin && ThenPin->LinkedTo.IsEmpty() && Distance < BestExecDistance)
			{
				FallbackExec = ThenPin;
				BestExecDistance = Distance;
			}
		}
	}

	bool bWired = true;
	bWired &= MoveLinksOrConnect(OldCall->GetExecPin(), FallbackExec, WeldCall->GetExecPin());
	// The old constraint call was terminal in this Construction Script, so an
	// unlinked Then pin is valid and requires no replacement connection.
	if (OldCall->GetThenPin() && !OldCall->GetThenPin()->LinkedTo.IsEmpty())
	{
		bWired &= MoveLinks(OldCall->GetThenPin(), WeldCall->GetThenPin());
	}
	bWired &= MoveLinksOrConnect(
		OldCall->FindPin(UEdGraphSchema_K2::PN_Self, EGPD_Input),
		FindVariableOutput(TEXT("PhysicsConstraint")),
		WeldCall->FindPin(TEXT("Constraint"), EGPD_Input));
	bWired &= MoveLinksOrConnect(
		OldCall->FindPin(TEXT("Component1"), EGPD_Input),
		FindVariableOutput(TEXT("Noose")),
		WeldCall->FindPin(TEXT("Noose"), EGPD_Input));
	bWired &= MoveLinksOrConnect(
		OldCall->FindPin(TEXT("Component2"), EGPD_Input),
		FindVariableOutput(TEXT("SKM_RopeHang")),
		WeldCall->FindPin(TEXT("Rope"), EGPD_Input));

	if (UEdGraphPin* TerminalBonePin = WeldCall->FindPin(TEXT("TerminalBone"), EGPD_Input))
	{
		TerminalBonePin->DefaultValue = TEXT("joint27");
	}

	if (!bWired)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence noose weld install: failed to preserve one or more graph links"));
		ConstructionGraph->RemoveNode(WeldCall);
		return;
	}

	FBlueprintEditorUtils::RemoveNode(Blueprint, OldCall, true);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FKismetEditorUtilities::CompileBlueprint(Blueprint, EBlueprintCompileOptions::SkipGarbageCollection);

	int32 WeldCallCount = 0;
	int32 OldCallCount = 0;
	for (UEdGraphNode* Node : ConstructionGraph->Nodes)
	{
		if (const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node))
		{
			WeldCallCount += IsCallTo(Call, WeldFunctionName) ? 1 : 0;
			OldCallCount += IsCallTo(Call, OldFunctionName) ? 1 : 0;
		}
	}

	if (Blueprint->Status == BS_Error || WeldCallCount != 1 || OldCallCount != 0)
	{
		UE_LOG(LogTemp, Error,
			TEXT("Potence noose weld install: FAILED status=%d welds=%d old_constraints=%d"),
			static_cast<int32>(Blueprint->Status), WeldCallCount, OldCallCount);
		return;
	}

	UE_LOG(LogTemp, Display,
		TEXT("Potence noose weld install: DONE status=%d welds=%d old_constraints=%d (asset remains unsaved for validation)"),
		static_cast<int32>(Blueprint->Status), WeldCallCount, OldCallCount);
}

FAutoConsoleCommand GInstallPotenceNooseWeldCommand(
	TEXT("Prophecy.InstallPotenceNooseWeld"),
	TEXT("Replaces A_Potence's external noose constraint with one rigid joint27 weld."),
	FConsoleCommandDelegate::CreateStatic(&InstallPotenceNooseWeld));

void MovePotenceNooseWeldToBeginPlay()
{
	constexpr TCHAR AssetPath[] = TEXT("/Game/_mygame/assets/hanging/A_Potence.A_Potence");
	const FName WeldFunctionName = GET_FUNCTION_NAME_CHECKED(
		UProphecyPhysicsConstraintBlueprintLibrary, WeldNooseToRopeEnd);
	const FName BeginPlayFunctionName(TEXT("ReceiveBeginPlay"));

	UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, AssetPath);
	UEdGraph* ConstructionGraph = Blueprint
		? FBlueprintEditorUtils::FindUserConstructionScript(Blueprint)
		: nullptr;
	UEdGraph* EventGraph = Blueprint
		? FBlueprintEditorUtils::FindEventGraph(Blueprint)
		: nullptr;
	if (!Blueprint || !ConstructionGraph || !EventGraph)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence noose BeginPlay install: required graph was not found"));
		return;
	}

	UK2Node_CallFunction* ConstructionWeld = nullptr;
	UK2Node_CallFunction* ExistingEventWeld = nullptr;
	for (UEdGraphNode* Node : ConstructionGraph->Nodes)
	{
		if (UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node);
			Call && IsCallTo(Call, WeldFunctionName))
		{
			ConstructionWeld = Call;
			break;
		}
	}
	for (UEdGraphNode* Node : EventGraph->Nodes)
	{
		if (UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node);
			Call && IsCallTo(Call, WeldFunctionName))
		{
			ExistingEventWeld = Call;
			break;
		}
	}
	if (ExistingEventWeld)
	{
		// A Blueprint restored after a Live Coding/session boundary can retain the
		// old pins while the native function is temporarily unavailable. Rebuild
		// the existing call from the current reflected signature instead of
		// returning and leaving a permanently red node behind.
		Blueprint->Modify();
		EventGraph->Modify();
		ExistingEventWeld->Modify();
		ExistingEventWeld->ReconstructNode();
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FKismetEditorUtilities::CompileBlueprint(
			Blueprint, EBlueprintCompileOptions::SkipGarbageCollection);

		if (Blueprint->Status == BS_Error)
		{
			UE_LOG(LogTemp, Error,
				TEXT("Potence noose BeginPlay install: existing weld node refresh FAILED"));
			return;
		}

		UE_LOG(LogTemp, Display,
			TEXT("Potence noose BeginPlay install: refreshed existing weld node (asset remains unsaved for validation)"));
		return;
	}
	if (!ConstructionWeld)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence noose BeginPlay install: ConstructionScript weld node was not found"));
		return;
	}

	UK2Node_Event* BeginPlayEvent = nullptr;
	for (UEdGraphNode* Node : EventGraph->Nodes)
	{
		if (UK2Node_Event* Event = Cast<UK2Node_Event>(Node);
			Event && Event->EventReference.GetMemberName() == BeginPlayFunctionName)
		{
			BeginPlayEvent = Event;
			break;
		}
	}
	if (!BeginPlayEvent)
	{
		int32 NodePosY = 0;
		BeginPlayEvent = FKismetEditorUtilities::AddDefaultEventNode(
			Blueprint, EventGraph, BeginPlayFunctionName, AActor::StaticClass(), NodePosY);
	}
	UFunction* WeldFunction = UProphecyPhysicsConstraintBlueprintLibrary::StaticClass()->FindFunctionByName(WeldFunctionName);
	if (!BeginPlayEvent || !WeldFunction)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence noose BeginPlay install: event or native function unavailable"));
		return;
	}

	Blueprint->Modify();
	ConstructionGraph->Modify();
	EventGraph->Modify();
	BeginPlayEvent->Modify();

	auto AddVariableGet = [EventGraph](const FName VariableName, const int32 X, const int32 Y) -> UK2Node_VariableGet*
	{
		UK2Node_VariableGet* VariableGet = NewObject<UK2Node_VariableGet>(EventGraph);
		EventGraph->AddNode(VariableGet, true, false);
		VariableGet->CreateNewGuid();
		VariableGet->PostPlacedNewNode();
		VariableGet->VariableReference.SetSelfMember(VariableName);
		VariableGet->NodePosX = X;
		VariableGet->NodePosY = Y;
		VariableGet->AllocateDefaultPins();
		return VariableGet;
	};

	const int32 WeldX = BeginPlayEvent->NodePosX + 360;
	const int32 WeldY = BeginPlayEvent->NodePosY;
	UK2Node_VariableGet* ConstraintGet = AddVariableGet(TEXT("PhysicsConstraint"), WeldX - 220, WeldY + 160);
	UK2Node_VariableGet* NooseGet = AddVariableGet(TEXT("Noose"), WeldX - 220, WeldY + 260);
	UK2Node_VariableGet* RopeGet = AddVariableGet(TEXT("SKM_RopeHang"), WeldX - 220, WeldY + 360);

	UK2Node_CallFunction* WeldCall = NewObject<UK2Node_CallFunction>(EventGraph);
	EventGraph->AddNode(WeldCall, true, false);
	WeldCall->CreateNewGuid();
	WeldCall->PostPlacedNewNode();
	WeldCall->SetFromFunction(WeldFunction);
	WeldCall->NodePosX = WeldX;
	WeldCall->NodePosY = WeldY;
	WeldCall->NodeComment = TEXT("One-time BeginPlay weld after Chaos bodies exist; no per-frame correction");
	WeldCall->bCommentBubbleVisible = true;
	WeldCall->AllocateDefaultPins();

	const UEdGraphSchema* Schema = EventGraph->GetSchema();
	UEdGraphPin* BeginThen = BeginPlayEvent->FindPin(UEdGraphSchema_K2::PN_Then, EGPD_Output);
	UEdGraphPin* WeldExec = WeldCall->GetExecPin();
	UEdGraphPin* WeldThen = WeldCall->GetThenPin();
	if (!Schema || !BeginThen || !WeldExec || !WeldThen)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence noose BeginPlay install: execution pins unavailable"));
		return;
	}

	const TArray<UEdGraphPin*> ExistingBeginPlayLinks = BeginThen->LinkedTo;
	BeginThen->BreakAllPinLinks();
	bool bWired = Schema->TryCreateConnection(BeginThen, WeldExec);
	for (UEdGraphPin* ExistingPin : ExistingBeginPlayLinks)
	{
		bWired &= Schema->TryCreateConnection(WeldThen, ExistingPin);
	}
	bWired &= Schema->TryCreateConnection(
		ConstraintGet->FindPin(TEXT("PhysicsConstraint"), EGPD_Output),
		WeldCall->FindPin(TEXT("Constraint"), EGPD_Input));
	bWired &= Schema->TryCreateConnection(
		NooseGet->FindPin(TEXT("Noose"), EGPD_Output),
		WeldCall->FindPin(TEXT("Noose"), EGPD_Input));
	bWired &= Schema->TryCreateConnection(
		RopeGet->FindPin(TEXT("SKM_RopeHang"), EGPD_Output),
		WeldCall->FindPin(TEXT("Rope"), EGPD_Input));
	if (UEdGraphPin* TerminalBonePin = WeldCall->FindPin(TEXT("TerminalBone"), EGPD_Input))
	{
		TerminalBonePin->DefaultValue = TEXT("joint27");
	}
	if (!bWired)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence noose BeginPlay install: graph wiring failed"));
		return;
	}

	FBlueprintEditorUtils::RemoveNode(Blueprint, ConstructionWeld, true);
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FKismetEditorUtilities::CompileBlueprint(Blueprint, EBlueprintCompileOptions::SkipGarbageCollection);

	int32 EventWeldCount = 0;
	int32 ConstructionWeldCount = 0;
	for (UEdGraphNode* Node : EventGraph->Nodes)
	{
		if (const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node))
		{
			EventWeldCount += IsCallTo(Call, WeldFunctionName) ? 1 : 0;
		}
	}
	for (UEdGraphNode* Node : ConstructionGraph->Nodes)
	{
		if (const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node))
		{
			ConstructionWeldCount += IsCallTo(Call, WeldFunctionName) ? 1 : 0;
		}
	}
	if (Blueprint->Status == BS_Error || EventWeldCount != 1 || ConstructionWeldCount != 0)
	{
		UE_LOG(LogTemp, Error,
			TEXT("Potence noose BeginPlay install: FAILED status=%d event=%d construction=%d"),
			static_cast<int32>(Blueprint->Status), EventWeldCount, ConstructionWeldCount);
		return;
	}

	UE_LOG(LogTemp, Display,
		TEXT("Potence noose BeginPlay install: DONE status=%d event=%d construction=%d (asset remains unsaved for validation)"),
		static_cast<int32>(Blueprint->Status), EventWeldCount, ConstructionWeldCount);
}

FAutoConsoleCommand GMovePotenceNooseWeldToBeginPlayCommand(
	TEXT("Prophecy.MovePotenceNooseWeldToBeginPlay"),
	TEXT("Moves the Potence noose weld from Construction Script to BeginPlay after Chaos bodies exist."),
	FConsoleCommandDelegate::CreateStatic(&MovePotenceNooseWeldToBeginPlay));

void AuthorPotenceRopeSolverIterations()
{
	constexpr TCHAR PhysicsAssetPath[] =
		TEXT("/Game/_mygame/assets/hanging/PHAT_RopeHang.PHAT_RopeHang");
	constexpr uint8 PositionIterations = 12;
	constexpr uint8 VelocityIterations = 2;
	constexpr uint8 ProjectionIterations = 24;

	UPhysicsAsset* PhysicsAsset = LoadObject<UPhysicsAsset>(nullptr, PhysicsAssetPath);
	if (!PhysicsAsset)
	{
		UE_LOG(LogTemp, Error, TEXT("Potence rope solver authoring: physics asset was not found"));
		return;
	}

	PhysicsAsset->Modify();
	int32 ChangedBodyCount = 0;
	auto ConfigureBone = [PhysicsAsset, &ChangedBodyCount](const FName BoneName)
	{
		const int32 BodyIndex = PhysicsAsset->FindBodyIndex(BoneName);
		if (!PhysicsAsset->SkeletalBodySetups.IsValidIndex(BodyIndex))
		{
			UE_LOG(LogTemp, Error,
				TEXT("Potence rope solver authoring: body '%s' was not found"),
				*BoneName.ToString());
			return;
		}

		USkeletalBodySetup* BodySetup = PhysicsAsset->SkeletalBodySetups[BodyIndex];
		BodySetup->Modify();
		BodySetup->DefaultInstance.SetOverrideIterationCounts(true);
		BodySetup->DefaultInstance.SetPositionSolverIterationCount(PositionIterations);
		BodySetup->DefaultInstance.SetVelocitySolverIterationCount(VelocityIterations);
		BodySetup->DefaultInstance.SetProjectionSolverIterationCount(ProjectionIterations);
		++ChangedBodyCount;
	};

	ConfigureBone(TEXT("joint"));
	for (int32 SegmentIndex = 1; SegmentIndex <= 27; ++SegmentIndex)
	{
		ConfigureBone(FName(*FString::Printf(TEXT("joint%d"), SegmentIndex)));
	}

	PhysicsAsset->RefreshPhysicsAssetChange();
	PhysicsAsset->MarkPackageDirty();
	UE_LOG(LogTemp, Display,
		TEXT("Potence rope solver authoring: DONE bodies=%d position=%d velocity=%d projection=%d"),
		ChangedBodyCount, PositionIterations, VelocityIterations, ProjectionIterations);
}

FAutoConsoleCommand GAuthorPotenceRopeSolverIterationsCommand(
	TEXT("Prophecy.AuthorPotenceRopeSolverIterations"),
	TEXT("Authors stable long-chain solver iteration overrides into PHAT_RopeHang."),
	FConsoleCommandDelegate::CreateStatic(&AuthorPotenceRopeSolverIterations));


}

class FProphecyEditorModule final : public IModuleInterface
{
};

IMPLEMENT_MODULE(FProphecyEditorModule, ProphecyEditor)
