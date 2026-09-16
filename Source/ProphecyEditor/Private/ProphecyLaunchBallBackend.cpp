#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_IfThenElse.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "UObject/SavePackage.h"

namespace ProphecyLaunchBallBackend
{
void Wire()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP = LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP || !BP->GeneratedClass) return;
    UEdGraph* Graph = nullptr;
    for (UEdGraph* Candidate : BP->FunctionGraphs)
        if (Candidate && Candidate->GetName()==TEXT("launch ball debug")) Graph=Candidate;
    if (!Graph) return;
    const FString Marker=TEXT("Launch projectile using the character's active physics backend.");
    for (UEdGraphNode* Node : Graph->Nodes)
        if (Node && Node->NodeComment==Marker) { UE_LOG(LogTemp,Display,TEXT("LaunchBackend: already wired.")); return; }
    UK2Node_CallFunction* CCD=nullptr;
    for (UEdGraphNode* Node : Graph->Nodes)
        if (auto* Call=Cast<UK2Node_CallFunction>(Node); Call && Call->FunctionReference.GetMemberName()==TEXT("SetUseCCD"))
        { if (CCD) return; CCD=Call; }
    UClass* Library=FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecyJoltStaticMeshLibrary"));
    UFunction* Enable=Library ? Library->FindFunctionByName(TEXT("EnableJoltStaticMeshPhysics")) : nullptr;
    UFunction* Active=BP->GeneratedClass->FindFunctionByName(TEXT("IsJoltPhysicalAnimationEnabled"));
    auto* Then=CCD ? CCD->FindPin(UEdGraphSchema_K2::PN_Then) : nullptr;
    auto* Target=CCD ? CCD->FindPin(UEdGraphSchema_K2::PN_Self) : nullptr;
    if (!Enable || !Active || !Then || !Target || Target->LinkedTo.Num()!=1 || !Then->LinkedTo.IsEmpty())
    { UE_LOG(LogTemp,Error,TEXT("LaunchBackend: graph no longer matches the audited terminal CCD setup; no edits.")); return; }
    auto* Mesh=Target->LinkedTo[0];
    const FString Filename=FPackageName::LongPackageNameToFilename(BP->GetOutermost()->GetName(),FPackageName::GetAssetPackageExtension());
    const FString Backup=FPaths::ProjectSavedDir()/TEXT("Diagnostics/LaunchBackend")/FDateTime::Now().ToString(TEXT("%Y%m%d-%H%M%S"));
    IFileManager::Get().MakeDirectory(*Backup,true);
    if (IFileManager::Get().Copy(*(Backup/TEXT("Disk-BP_ProphecyManualPoseAgent.uasset")),*Filename,false)!=COPY_OK) return;
    FSavePackageArgs Snapshot; Snapshot.TopLevelFlags=RF_Public|RF_Standalone; Snapshot.SaveFlags=SAVE_KeepDirty;
    if (!UPackage::SavePackage(BP->GetOutermost(),BP,*(Backup/TEXT("Current-BP_ProphecyManualPoseAgent.uasset")),Snapshot)) return;
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","LaunchBackend","Use active physics backend for debug projectile"));
    BP->Modify(); Graph->Modify(); CCD->Modify(); Mesh->GetOwningNode()->Modify();
    FGraphNodeCreator<UK2Node_IfThenElse> BranchCreator(*Graph);
    auto* Branch=BranchCreator.CreateNode(); Branch->NodePosX=CCD->NodePosX+350; Branch->NodePosY=CCD->NodePosY;
    Branch->NodeComment=Marker; BranchCreator.Finalize();
    FGraphNodeCreator<UK2Node_CallFunction> ActiveCreator(*Graph);
    auto* Check=ActiveCreator.CreateNode(); Check->SetFromFunction(Active);
    Check->NodePosX=Branch->NodePosX; Check->NodePosY=Branch->NodePosY+180; ActiveCreator.Finalize();
    FGraphNodeCreator<UK2Node_CallFunction> EnableCreator(*Graph);
    auto* Transfer=EnableCreator.CreateNode(); Transfer->SetFromFunction(Enable);
    Transfer->NodePosX=Branch->NodePosX+330; Transfer->NodePosY=Branch->NodePosY; EnableCreator.Finalize();
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();
    const bool bLinked=Schema->TryCreateConnection(Then,Branch->GetExecPin())
        && Schema->TryCreateConnection(Check->FindPinChecked(UEdGraphSchema_K2::PN_ReturnValue),Branch->GetConditionPin())
        && Schema->TryCreateConnection(Branch->GetThenPin(),Transfer->FindPinChecked(UEdGraphSchema_K2::PN_Execute))
        && Schema->TryCreateConnection(Mesh,Transfer->FindPinChecked(TEXT("Mesh")));
    FBlueprintEditorUtils::MarkBlueprintAsModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    if (!bLinked || BP->Status==BS_Error)
    {
        Transfer->DestroyNode(); Check->DestroyNode(); Branch->DestroyNode();
        FBlueprintEditorUtils::MarkBlueprintAsModified(BP);
        FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
        UE_LOG(LogTemp,Error,TEXT("LaunchBackend: wiring/compile failed; original graph restored. Backup: %s"),*Backup);
        return;
    }
    FSavePackageArgs Save; Save.TopLevelFlags=RF_Public|RF_Standalone;
    const bool bSaved=UPackage::SavePackage(BP->GetOutermost(),BP,*Filename,Save);
    UE_LOG(LogTemp,Display,TEXT("LaunchBackend: wired=1 compiled=1 saved=%d; original launch inputs/nodes unchanged; Jolt-active branch only. Backup: %s"),bSaved,*Backup);
}
FAutoConsoleCommand Command(TEXT("Prophecy.Debug.WireLaunchBackend"),
    TEXT("Back up and wire the audited launch ball debug function to the active character backend; compile and save only its Blueprint."),
    FConsoleCommandDelegate::CreateStatic(&Wire));
}
