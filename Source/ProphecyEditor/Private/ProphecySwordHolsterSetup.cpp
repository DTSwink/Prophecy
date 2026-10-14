#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_IfThenElse.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SCS_Node.h"
#include "EngineUtils.h"
#include "Components/SkeletalMeshComponent.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"

namespace ProphecySwordHolsterSetup
{
static void RefreshDrawPins()
{
 if(!GEditor||GEditor->PlayWorld)return;
 auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));if(!BP)return;
 TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);TArray<UK2Node_CallFunction*> Nodes;
 for(auto* G:Graphs)for(UEdGraphNode* N:G->Nodes)if(auto* C=Cast<UK2Node_CallFunction>(N))
  if(C->FunctionReference.GetMemberName()==TEXT("DrawSword"))Nodes.Add(C);
 for(auto* N:Nodes)for(const TCHAR* Name:{TEXT("MaxReachSpeed"),TEXT("MaxReachRotationSpeed"),TEXT("SlidingSpeed")})
  if(const auto* P=N->FindPin(Name))if(!P->LinkedTo.IsEmpty()){UE_LOG(LogTemp,Error,TEXT("Draw Sword speed pin is wired; no migration performed."));return;}
 const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","DrawSwordPins","Remove obsolete Draw Sword speed pins"));BP->Modify();
 for(auto* N:Nodes){N->Modify();
  for(const TCHAR* Name:{TEXT("MaxReachSpeed"),TEXT("MaxReachRotationSpeed"),TEXT("SlidingSpeed")})if(auto* P=N->FindPin(Name))N->RemovePin(P);
  N->ReconstructNode();
 }
 FBlueprintEditorUtils::MarkBlueprintAsModified(BP);FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
 UE_LOG(LogTemp,Display,TEXT("Refreshed %d Draw Sword nodes; BP status=%d; not saved."),Nodes.Num(),int32(BP->Status));
}
static FAutoConsoleCommand DrawPinsCommand(TEXT("Prophecy.Editor.RefreshDrawSwordPins"),TEXT("Remove unlinked obsolete speed pins from existing Draw Sword nodes; preserves other wiring, no save."),FConsoleCommandDelegate::CreateStatic(&RefreshDrawPins));
static void RefreshGripProfilePins(const TArray<FString>& Args)
{
 if(!GEditor||GEditor->PlayWorld)return;
 const bool Migrate=Args.Num()==3&&Args[0]==TEXT("ReturnRanges");
 double Ends[2]={1,1};
 if(Migrate)for(int I=0;I<2;++I){if(!LexTryParseString(Ends[I],*Args[I+1])||!FMath::IsFinite(Ends[I])||Ends[I]<.5||Ends[I]>1)return;}
 auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));if(!BP)return;
 TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);TArray<UK2Node_CallFunction*> Nodes;
 for(auto* G:Graphs)for(UEdGraphNode* N:G->Nodes)if(auto* C=Cast<UK2Node_CallFunction>(N))
  if(C->FunctionReference.GetMemberName()==TEXT("SetSwordHolsterProfile")&&(Migrate||!C->FindPin(TEXT("DrawNNBlendRange"))))Nodes.Add(C);
 if(Nodes.IsEmpty())return;
 for(auto* N:Nodes)for(const TCHAR* Name:{TEXT("FKReturnCutoff"),TEXT("SheatheFKReturnCutoff"),TEXT("DrawNNBlendRange"),TEXT("SheatheNNBlendRange")})
  if(const auto* Pin=N->FindPin(Name))if(!Pin->LinkedTo.IsEmpty()){UE_LOG(LogTemp,Error,TEXT("Return range migration requires unlinked literals; nothing changed."));return;}
 const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","HolsterReturnRanges","Expose independent sword NN blend ranges"));BP->Modify();
 for(auto* N:Nodes){N->Modify();
  for(const TCHAR* Name:{TEXT("FKReturnCutoff"),TEXT("SheatheFKReturnCutoff")})if(auto* Pin=N->FindPin(Name))N->RemovePin(Pin);
  N->ReconstructNode();
  if(Migrate){const TCHAR* Names[]={TEXT("DrawNNBlendRange"),TEXT("SheatheNNBlendRange")};
   for(int I=0;I<2;++I)if(auto* Pin=N->FindPin(Names[I]))N->GetSchema()->TrySetDefaultValue(*Pin,FString::Printf(TEXT("(X=0.500000,Y=%.6f)"),Ends[I]));}
 }
 FBlueprintEditorUtils::MarkBlueprintAsModified(BP);FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
 UE_LOG(LogTemp,Display,TEXT("Refreshed %d existing holster profile nodes; not saved."),Nodes.Num());
}
static FAutoConsoleCommand GripProfilePins(TEXT("Prophecy.Editor.RefreshHolsterGripPins"),TEXT("Refresh existing profile pins; ReturnRanges <draw-end> <sheathe-end> explicitly migrates unlinked cutoffs to ranges starting at .5. No save."),FConsoleCommandWithArgsDelegate::CreateStatic(&RefreshGripProfilePins));
// Explicit editor operation for the user's temporary, non-physical pelvis mount.
// If the obsolete joint still exists, retain its settings but remove its endpoints.
static void MountRigidHolster()
{
 if(!GEditor||GEditor->PlayWorld)return;
 auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
 if(!BP||!BP->SimpleConstructionScript)return;
 USCS_Node* HolsterNode=nullptr;USCS_Node* JointNode=nullptr;
 for(auto* N:BP->SimpleConstructionScript->GetAllNodes()){
  if(N->GetVariableName()==TEXT("holster"))HolsterNode=N;
  if(N->GetVariableName()==TEXT("PhysicsConstraint"))JointNode=N;
 }
 auto* Template=HolsterNode?Cast<UPrimitiveComponent>(HolsterNode->ComponentTemplate):nullptr;
 auto* Joint=JointNode?Cast<UPhysicsConstraintComponent>(JointNode->ComponentTemplate):nullptr;
 if(!Template||Template->BodyInstance.bSimulatePhysics||Template->GetCollisionEnabled()!=ECollisionEnabled::NoCollision)return;
 FTransform Local;bool Found=false;
 for(TActorIterator<AActor> It(GEditor->GetEditorWorldContext().World());It;++It)if(It->GetClass()==BP->GeneratedClass){
  TInlineComponentArray<UPrimitiveComponent*> Parts(*It);UPrimitiveComponent* H=nullptr;USkeletalMeshComponent* M=nullptr;
  for(auto* C:Parts){if(C->GetFName()==TEXT("holster"))H=C;if(C->GetFName()==TEXT("PhysicalMesh"))M=Cast<USkeletalMeshComponent>(C);}
  if(H&&M&&H->GetAttachParent()==M&&M->DoesSocketExist(TEXT("pelvis"))){
   const FTransform Candidate=H->GetComponentTransform().GetRelativeTransform(M->GetSocketTransform(TEXT("pelvis")));
   if(Found&&!Local.Equals(Candidate,.001)){UE_LOG(LogTemp,Error,TEXT("Rigid holster: differing actor placements; no changes."));return;}
   Local=Candidate;Found=true;
  }
 }
 if(!Found)return;
 const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","RigidHolster","Attach non-physical holster to pelvis"));
 BP->Modify();HolsterNode->Modify();Template->Modify();
 HolsterNode->AttachToName=TEXT("pelvis");Template->SetRelativeTransform(Local);
 if(Joint){
  Joint->Modify();
  Joint->ComponentName1.ComponentName=NAME_None;Joint->ComponentName2.ComponentName=NAME_None;
  Joint->ConstraintActor1=nullptr;Joint->ConstraintActor2=nullptr;Joint->OverrideComponent1=nullptr;Joint->OverrideComponent2=nullptr;
 }
 // Clear placed-instance copies too; otherwise their inherited old endpoint values
 // can survive the reconstruction and recreate the pelvis motor in PIE.
 for(TActorIterator<AActor> It(GEditor->GetEditorWorldContext().World());It;++It)if(It->GetClass()==BP->GeneratedClass){
  TInlineComponentArray<UPhysicsConstraintComponent*> Joints(*It);
  for(auto* C:Joints)if(C->GetFName()==TEXT("PhysicsConstraint")){C->Modify();C->BreakConstraint();C->ComponentName1.ComponentName=NAME_None;C->ComponentName2.ComponentName=NAME_None;C->OverrideComponent1=nullptr;C->OverrideComponent2=nullptr;}
 }
 FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
 FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
 for(TActorIterator<AActor> It(GEditor->GetEditorWorldContext().World());It;++It)if(It->GetClass()==BP->GeneratedClass){
  TInlineComponentArray<UPrimitiveComponent*> Parts(*It);
  for(auto* C:Parts)if(C->GetFName()==TEXT("holster")){C->Modify();C->SetRelativeTransform(Local);}
 }
 UE_LOG(LogTemp,Display,TEXT("Rigid holster: pelvis socket, saved local placement, old motor endpoints cleared. BP status=%d; not saved."),int32(BP->Status));
}
static FAutoConsoleCommand RigidCommand(TEXT("Prophecy.Editor.MountRigidHolster"),TEXT("Preserve current placed holster placement as a pelvis socket mount; disable its old motor endpoints. Does not save."),FConsoleCommandDelegate::CreateStatic(&MountRigidHolster));

static void Wire()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    auto* Library=FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecySwordHolsterLibrary"));
    if(!Library)return;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    UEdGraph* Tick=nullptr;UK2Node_IfThenElse* Branch=nullptr;
    TArray<UK2Node_FunctionEntry*> Entries;
    for(auto* G:Graphs)
    {
        if(G->GetFName()==TEXT("tick debugging"))Tick=G;
        for(UEdGraphNode* N:G->Nodes)
        {
            if(auto* Call=Cast<UK2Node_CallFunction>(N))if(Call->FunctionReference.GetMemberName()==TEXT("DrawSword"))
            {UE_LOG(LogTemp,Warning,TEXT("Sword holster wiring already exists; no changes."));return;}
            if(G->GetFName()==TEXT("begin_f") || G->GetFName()==TEXT("UserConstructionScript"))
                if(auto* E=Cast<UK2Node_FunctionEntry>(N))Entries.Add(E);
            if(G==Tick && N->GetFName()==TEXT("K2Node_IfThenElse_5"))Branch=Cast<UK2Node_IfThenElse>(N);
        }
    }
    auto* Condition=Branch?Branch->GetConditionPin():nullptr;
    auto* At=Condition && Condition->LinkedTo.Num()==1?Cast<UK2Node_CallFunction>(Condition->LinkedTo[0]->GetOwningNode()):nullptr;
    if(!Branch || !Branch->GetThenPin()->LinkedTo.IsEmpty() || Entries.Num()!=2 || !At ||
        At->FunctionReference.GetMemberName()!=TEXT("is tick") || !At->FindPin(TEXT("i")) || At->FindPin(TEXT("i"))->DefaultValue!=TEXT("25"))
    {UE_LOG(LogTemp,Error,TEXT("Sword holster: expected unused tick25 branch and construction/begin entries; no changes."));return;}
    for(auto* E:Entries)if(!E->FindPin(UEdGraphSchema_K2::PN_Then) || E->FindPin(UEdGraphSchema_K2::PN_Then)->LinkedTo.Num()>1)return;
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","SwordHolster","Wire procedural sword holster"));
    BP->Modify();Tick->Modify();Branch->Modify();
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();
    auto Call=[&](UEdGraph* G,FName Function,int32 X,int32 Y)
    {
        FGraphNodeCreator<UK2Node_CallFunction> C(*G);auto* N=C.CreateNode();
        N->SetFromFunction(Library->FindFunctionByName(Function));
        N->NodePosX=X;N->NodePosY=Y;C.Finalize();return N;
    };
    bool OK=true;
    auto Link=[&](UEdGraphPin* A,UEdGraphPin* B){OK&=A && B && Schema->TryCreateConnection(A,B);};
    for(auto* E:Entries)
    {
        E->GetGraph()->Modify();E->Modify();auto* Out=E->FindPinChecked(UEdGraphSchema_K2::PN_Then);
        auto* Next=Out->LinkedTo.IsEmpty()?nullptr:Out->LinkedTo[0];
        if(Next)Next->GetOwningNode()->Modify();
        auto* Capture=Call(E->GetGraph(),TEXT("CaptureSwordHolsterReference"),E->NodePosX+250,E->NodePosY-180);
        Out->BreakAllPinLinks();Link(Out,Capture->GetExecPin());if(Next)Link(Capture->GetThenPin(),Next);
    }
    auto* Profile=Call(Tick,TEXT("SetSwordHolsterProfile"),Branch->NodePosX+300,Branch->NodePosY+130);
    auto* Draw=Call(Tick,TEXT("DrawSword"),Branch->NodePosX+640,Branch->NodePosY+130);
    Schema->TrySetDefaultValue(*Draw->FindPinChecked(TEXT("Sheathe")),TEXT("true"));
    Link(Branch->GetThenPin(),Profile->GetExecPin());Link(Profile->GetThenPin(),Draw->GetExecPin());
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    FFileHelper::SaveStringToFile(FString::Printf(TEXT("connections=%d status=%d saved=0 added=4\n"),OK,int32(BP->Status)),
        *(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordDraw20261010/wiring.txt")));
}
static FAutoConsoleCommand Command(TEXT("Prophecy.Editor.WireSwordHolster"),TEXT("Wire audited tick25 sword holster and capture reference; compile without saving."),FConsoleCommandDelegate::CreateStatic(&Wire));
}
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
namespace ProphecySwordHolsterSetup
{
static void ImportLab()
{
 if(!GEditor||GEditor->PlayWorld)return;
 FString Text;if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectDir()/TEXT("Tools/Recovery/SwordLabCheckpoint20261010/lab-state.json"))))return;
 TSharedPtr<FJsonObject> Root;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return;const auto P=Root->GetObjectField(TEXT("parameters"));
 auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
 auto* Lib=FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecySwordHolsterLibrary"));if(!BP||!Lib)return;
 TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);UK2Node_CallFunction* Draw=nullptr;UK2Node_CallFunction* Profile=nullptr;
 for(auto* G:Graphs)for(UEdGraphNode* N:G->Nodes)if(auto* C=Cast<UK2Node_CallFunction>(N))
 {const auto F=C->FunctionReference.GetMemberName();if(F==TEXT("SetSwordHolsterLabProfile"))return;if(G->GetFName()==TEXT("tick debugging")){if(F==TEXT("DrawSword"))Draw=C;if(F==TEXT("SetSwordHolsterProfile"))Profile=C;}}
 if(!Draw||!Profile||Profile->GetExecPin()->LinkedTo.Num()!=1)return;
 for(auto N:{TEXT("ShrinkPercent"),TEXT("UnshrinkDuration")})if(!Profile->FindPin(N)||!Profile->FindPin(N)->LinkedTo.IsEmpty())return;
 const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","ImportHolsterLab","Import sword holster lab controls"));BP->Modify();Profile->GetGraph()->Modify();Profile->Modify();Draw->Modify();
 auto* Previous=Profile->GetExecPin()->LinkedTo[0];Previous->GetOwningNode()->Modify();
 FGraphNodeCreator<UK2Node_CallFunction> Create(*Profile->GetGraph());auto* Node=Create.CreateNode();Node->SetFromFunction(Lib->FindFunctionByName(TEXT("SetSwordHolsterLabProfile")));Node->NodePosX=Profile->NodePosX-320;Node->NodePosY=Profile->NodePosY+220;Create.Finalize();
 const auto* Schema=GetDefault<UEdGraphSchema_K2>();Schema->TrySetDefaultValue(*Node->FindPinChecked(TEXT("ProfileFile")),TEXT("Content/locomotion/SwordHolsterProfile.json"));
 Profile->GetExecPin()->BreakAllPinLinks();bool OK=Schema->TryCreateConnection(Previous,Node->GetExecPin())&&Schema->TryCreateConnection(Node->GetThenPin(),Profile->GetExecPin());
 Schema->TrySetDefaultValue(*Profile->FindPinChecked(TEXT("ShrinkPercent")),FString::SanitizeFloat(P->GetNumberField(TEXT("shrinkPercent"))));Schema->TrySetDefaultValue(*Profile->FindPinChecked(TEXT("UnshrinkDuration")),FString::SanitizeFloat(P->GetNumberField(TEXT("unshrinkDuration"))));
 FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
 FFileHelper::SaveStringToFile(FString::Printf(TEXT("connections=%d status=%d added=1 saved=0\n"),OK,int32(BP->Status)),*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordLabPort20261010/import.txt")));
}
static FAutoConsoleCommand ImportCommand(TEXT("Prophecy.Editor.ImportSwordHolsterLab"),TEXT("Import captured lab profile into existing sword nodes; compile without saving."),FConsoleCommandDelegate::CreateStatic(&ImportLab));
static void RefreshLabValues()
{
 if(!GEditor||GEditor->PlayWorld)return;
 FString Text;if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("locomotion/SwordHolsterProfile.json"))))return;
 TSharedPtr<FJsonObject> Root;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return;
 const TSharedPtr<FJsonObject>* Nested;const auto P=Root->TryGetObjectField(TEXT("parameters"),Nested)?*Nested:Root;
 auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));if(!BP)return;
 TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);TArray<UEdGraphPin*> Pins;TArray<FString> Values;
 const TCHAR* Names[]={TEXT("ShrinkPercent"),TEXT("UnshrinkDuration"),TEXT("GripHolsterStabilizationPercent"),TEXT("HolsterReturnDuration"),TEXT("ShrinkDuration"),TEXT("MaxAttachedSpeed"),TEXT("MaxAttachedRotationSpeed"),TEXT("LeewayAttachmentPhase"),TEXT("SheatheTipDistanceThreshold")};
 const TCHAR* Keys[]={TEXT("shrinkPercent"),TEXT("unshrinkDuration"),TEXT("holsterRotationStabilization"),TEXT("holsterReturnDuration"),TEXT("shrinkDuration"),TEXT("maxAttachedSpeed"),TEXT("maxAttachedRotationSpeed"),TEXT("leewayPhase"),TEXT("sheatheTipTolerance")};
 for(int I=0;I<UE_ARRAY_COUNT(Names);++I){UEdGraphPin* Pin=nullptr;
  for(auto* G:Graphs)if(G->GetFName()==TEXT("tick debugging"))for(UEdGraphNode* N:G->Nodes)if(auto* C=Cast<UK2Node_CallFunction>(N))if(C->FunctionReference.GetMemberName()==TEXT("SetSwordHolsterProfile")){
   if(Pin)return;Pin=C->FindPin(Names[I]);}
  if(!Pin||!Pin->LinkedTo.IsEmpty())return;
  FString Value;
  if(I==7){bool V;if(!P->TryGetBoolField(Keys[I],V))return;Value=V?TEXT("true"):TEXT("false");}
  else {double V;if(!P->TryGetNumberField(Keys[I],V)||!FMath::IsFinite(V))return;Value=FString::SanitizeFloat(I==2?100*V:V);}
  Pins.Add(Pin);Values.Add(Value);
 }
 const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","RefreshHolsterValues","Refresh sword holster lab values"));BP->Modify();
 for(int I=0;I<Pins.Num();++I){Pins[I]->GetOwningNode()->Modify();GetDefault<UEdGraphSchema_K2>()->TrySetDefaultValue(*Pins[I],Values[I]);}
 FBlueprintEditorUtils::MarkBlueprintAsModified(BP);FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
}
static FAutoConsoleCommand RefreshCommand(TEXT("Prophecy.Editor.RefreshSwordHolsterValues"),TEXT("Refresh existing basic profile literals from the accepted lab export; preserve wiring and action-specific speeds; compile without saving."),FConsoleCommandDelegate::CreateStatic(&RefreshLabValues));
}
