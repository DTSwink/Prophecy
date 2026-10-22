#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_InputKey.h"
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
#include "Kismet/KismetStringLibrary.h"
#include "Kismet/KismetSystemLibrary.h"

namespace ProphecySwordHolsterSetup
{
static void RemoveSwordTabShortcut()
{
 if(!GEditor||GEditor->PlayWorld)return;
 auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/sword/A_Sword.A_Sword"));if(!BP)return;
 TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);TArray<UK2Node_InputKey*> Nodes;
 for(auto* G:Graphs)for(UEdGraphNode* N:G->Nodes)if(auto* Key=Cast<UK2Node_InputKey>(N))if(Key->InputKey.GetFName()==TEXT("Tab"))Nodes.Add(Key);
 if(Nodes.IsEmpty())return;
 const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","SwordTabShortcut","Remove conflicting sword Tab shortcut"));BP->Modify();
 for(auto* N:Nodes){N->Modify();FBlueprintEditorUtils::RemoveNode(BP,N,true);}
 FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
 FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
 UE_LOG(LogTemp,Display,TEXT("Removed %d conflicting sword Tab events; BP status=%d; not saved."),Nodes.Num(),int32(BP->Status));
}
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
static void RepairSwordDebugFrameCap()
{
 if(!GEditor||GEditor->PlayWorld)return;
 auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/sword/A_Sword.A_Sword"));if(!BP)return;
 UEdGraph* Graph=nullptr;for(UEdGraph* G:BP->UbergraphPages)if(G->GetFName()==TEXT("EventGraph"))Graph=G;if(!Graph)return;
 auto Pin=[&](const TCHAR* Node,const TCHAR* Name)->UEdGraphPin*{
  for(UEdGraphNode* N:Graph->Nodes)if(N->GetFName()==Node)return N->FindPin(Name);return nullptr;
 };
 UEdGraphPin* Events[]={Pin(TEXT("K2Node_InputKey_2"),TEXT("Pressed")),Pin(TEXT("K2Node_InputKey_2"),TEXT("Released"))};
 UEdGraphPin* Old[]={Pin(TEXT("K2Node_CallFunction_161"),TEXT("execute")),Pin(TEXT("K2Node_CallFunction_162"),TEXT("execute"))};
 UEdGraphPin* Caps[]={Pin(TEXT("K2Node_CallFunction_150"),TEXT("execute")),Pin(TEXT("K2Node_CallFunction_146"),TEXT("execute"))};
 for(int I=0;I<2;++I)if(!Events[I]||!Old[I]||!Caps[I]||Events[I]->LinkedTo.Num()!=1||Events[I]->LinkedTo[0]!=Old[I]||!Caps[I]->LinkedTo.IsEmpty()){
  UE_LOG(LogTemp,Warning,TEXT("Sword debug FPS bindings differ from the audited graph; nothing changed."));return;
 }
 const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","SwordDebugFrameCap","Keep simulation timestep unchanged during sword slow-FPS debugging"));
 BP->Modify();Graph->Modify();
 for(int I=0;I<2;++I){
  Events[I]->GetOwningNode()->Modify();Old[I]->GetOwningNode()->Modify();Caps[I]->GetOwningNode()->Modify();
  Events[I]->BreakLinkTo(Old[I]);Events[I]->MakeLinkTo(Caps[I]);
 }
 FBlueprintEditorUtils::MarkBlueprintAsModified(BP);FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
 UE_LOG(LogTemp,Display,TEXT("Sword right-click now uses existing FPS-cap nodes; simulation clock and tuning unchanged; status=%d; not saved."),int32(BP->Status));
}
static void RepairSwordSlowStartFrameCap()
{
 if(!GEditor||GEditor->PlayWorld)return;
 auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/sword/A_Sword.A_Sword"));if(!BP)return;
 UEdGraph* Start=nullptr;UEdGraph* Events=nullptr;
 for(UEdGraph* G:BP->FunctionGraphs)if(G->GetFName()==TEXT("begin play f"))Start=G;
 for(UEdGraph* G:BP->UbergraphPages)if(G->GetFName()==TEXT("EventGraph"))Events=G;
 if(!Start||!Events)return;
 auto Node=[](UEdGraph* G,const TCHAR* Name)->UK2Node_CallFunction*{
  for(UEdGraphNode* N:G->Nodes)if(N->GetFName()==Name)return Cast<UK2Node_CallFunction>(N);return nullptr;
 };
 if(Node(Start,TEXT("ProphecySlowStartCap"))){UE_LOG(LogTemp,Display,TEXT("Sword Slow Start cap already installed."));return;}
 auto* Slow=Node(Start,TEXT("K2Node_CallFunction_2"));
 auto* Normal=Node(Start,TEXT("K2Node_CallFunction_159"));
 auto* End=Node(Events,TEXT("K2Node_CallFunction_159"));
 for(auto* N:{Slow,Normal,End})if(!N||N->FunctionReference.GetMemberName()!=TEXT("SetFixedFrameRateRuntime"))return;
 auto* FPS=Slow->FindPin(TEXT("FPS"));
 if(!FPS||FPS->LinkedTo.Num()!=1||Slow->GetThenPin()->LinkedTo.Num()!=1||
    Normal->GetThenPin()->LinkedTo.Num()!=1||!End->GetThenPin()->LinkedTo.IsEmpty())return;
 auto* SlowSource=FPS->LinkedTo[0];
 auto* SlowNext=Slow->GetThenPin()->LinkedTo[0];
 auto* NormalNext=Normal->GetThenPin()->LinkedTo[0];
 if(!UKismetStringLibrary::StaticClass()->FindFunctionByName(TEXT("BuildString_Double"))||
    !UKismetSystemLibrary::StaticClass()->FindFunctionByName(TEXT("ExecuteConsoleCommand")))return;
 const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","SwordSlowStartFrameCap","Keep sword Slow Start on the 60-tick physics clock"));
 BP->Modify();Start->Modify();Events->Modify();
 for(auto* N:{Slow,Normal,End})N->Modify();
 SlowSource->GetOwningNode()->Modify();SlowNext->GetOwningNode()->Modify();NormalNext->GetOwningNode()->Modify();
 auto Call=[](UEdGraph* G,UClass* Owner,const TCHAR* Function,const TCHAR* Name,int X,int Y){
  FGraphNodeCreator<UK2Node_CallFunction> Creator(*G);auto* N=Creator.CreateNode();
  N->SetFromFunction(Owner->FindFunctionByName(Function));N->Rename(Name,G);
  N->NodePosX=X;N->NodePosY=Y;Creator.Finalize();return N;
 };
 auto* Text=Call(Start,UKismetStringLibrary::StaticClass(),TEXT("BuildString_Double"),TEXT("ProphecySlowStartText"),-2200,650);
 auto* SlowCap=Call(Start,UKismetSystemLibrary::StaticClass(),TEXT("ExecuteConsoleCommand"),TEXT("ProphecySlowStartCap"),-1800,112);
 auto* NormalCap=Call(Start,UKismetSystemLibrary::StaticClass(),TEXT("ExecuteConsoleCommand"),TEXT("ProphecyNormalStartCap"),-1800,400);
 auto* EndCap=Call(Events,UKismetSystemLibrary::StaticClass(),TEXT("ExecuteConsoleCommand"),TEXT("ProphecyEndPlayCap"),-2800,1264);
 const auto* Schema=GetDefault<UEdGraphSchema_K2>();
 auto Link=[Schema](UEdGraphPin* A,UEdGraphPin* B){return A&&B&&Schema->TryCreateConnection(A,B);};
 auto Default=[Schema](UEdGraphPin* P,const TCHAR* Value){if(!P)return false;Schema->TrySetDefaultValue(*P,Value);return true;};
 bool OK=Default(Text->FindPin(TEXT("Prefix")),TEXT("t.MaxFPS "))&&
     Default(NormalCap->FindPin(TEXT("Command")),TEXT("t.MaxFPS 60"))&&
     Default(EndCap->FindPin(TEXT("Command")),TEXT("t.MaxFPS 60"))&&
     Link(SlowSource,Text->FindPin(TEXT("InDouble")))&&Link(Text->GetReturnValuePin(),SlowCap->FindPin(TEXT("Command")));
 if(OK){
  Slow->GetThenPin()->BreakLinkTo(SlowNext);Normal->GetThenPin()->BreakLinkTo(NormalNext);
  OK=Link(Slow->GetThenPin(),SlowCap->GetExecPin())&&Link(SlowCap->GetThenPin(),SlowNext)&&
     Link(Normal->GetThenPin(),NormalCap->GetExecPin())&&Link(NormalCap->GetThenPin(),NormalNext)&&
     Link(End->GetThenPin(),EndCap->GetExecPin());
 }
 if(OK){FPS->BreakLinkTo(SlowSource);Schema->TrySetDefaultValue(*FPS,TEXT("60.000000"));}
 else{
  for(auto* N:{Text,SlowCap,NormalCap,EndCap})FBlueprintEditorUtils::RemoveNode(BP,N,true);
  Link(Slow->GetThenPin(),SlowNext);Link(Normal->GetThenPin(),NormalNext);
 }
 FBlueprintEditorUtils::MarkBlueprintAsModified(BP);
 FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
 UE_LOG(LogTemp,Display,TEXT("Sword Slow Start cap: %s; status=%d; not saved."),OK?TEXT("connected"):TEXT("FAILED"),int32(BP->Status));
}
static void InstallCleanPike()
{
 if(!GEditor||GEditor->PlayWorld)return;
 auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/sword/A_Sword.A_Sword"));
 auto* Lib=FindObject<UClass>(nullptr,TEXT("/Script/ProphecyJolt.ProphecyJoltHitImpactLibrary"));
 if(!BP||!Lib)return;
 auto* EnableFunction=Lib->FindFunctionByName(TEXT("EnableCleanHitContinuation"));
 auto* AcceptFunction=Lib->FindFunctionByName(TEXT("AcceptPikeHit"));
 if(!EnableFunction||!AcceptFunction)return;
 UEdGraph* G=nullptr;for(UEdGraph* Graph:BP->UbergraphPages)if(Graph->GetFName()==TEXT("EventGraph"))G=Graph;
 if(!G)return;
 auto Find=[G](const TCHAR* Name)->UEdGraphNode*{for(UEdGraphNode* N:G->Nodes)if(N->GetFName()==Name)return N;return nullptr;};
 if(Find(TEXT("ProphecyAcceptPike"))){UE_LOG(LogTemp,Display,TEXT("Clean pike already installed."));return;}
 auto Pin=[&](const TCHAR* N,const TCHAR* P)->UEdGraphPin*{auto* Node=Find(N);return Node?Node->FindPin(P):nullptr;};
 auto* Begin=Pin(TEXT("K2Node_Event_0"),TEXT("then"));
 auto* Pike=Pin(TEXT("K2Node_IfThenElse_5"),TEXT("then"));
 auto* AfterPose=Pin(TEXT("K2Node_VariableSet_5"),TEXT("execute"));
 auto* Velocity=Pin(TEXT("K2Node_CallFunction_105"),TEXT("execute"));
 auto* AfterVelocity=Pin(TEXT("K2Node_Knot_26"),TEXT("InputPin"));
 auto* Sword=Pin(TEXT("K2Node_VariableGet_44"),TEXT("sword"));
 auto* IsPike=Pin(TEXT("K2Node_VariableGet_22"),TEXT("temp pike"));
 if(!Begin||!Pike||!AfterPose||!Velocity||!AfterVelocity||!Sword||!IsPike
    ||Begin->LinkedTo.Num()!=1||Pike->LinkedTo.Num()!=1||Velocity->LinkedTo.Num()!=1
    ||Pike->LinkedTo[0]!=Pin(TEXT("K2Node_Knot_6"),TEXT("InputPin")))
 {UE_LOG(LogTemp,Error,TEXT("Clean pike preflight failed; current graph differs, nothing edited."));return;}
 auto* BeginNext=Begin->LinkedTo[0];auto* PikeNext=Pike->LinkedTo[0];auto* BeforeVelocity=Velocity->LinkedTo[0];
 const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","CleanPike","Continue accepted pikes without changing Blueprint conditions"));
 BP->Modify();G->Modify();for(UEdGraphNode* N:G->Nodes)N->Modify();
 auto Call=[&](UFunction* F,const TCHAR* Name,int X,int Y){FGraphNodeCreator<UK2Node_CallFunction> C(*G);auto* N=C.CreateNode();
  N->SetFromFunction(F);N->Rename(Name,G);N->NodePosX=X;N->NodePosY=Y;C.Finalize();return N;};
 auto Branch=[&](const TCHAR* Name,int X,int Y){FGraphNodeCreator<UK2Node_IfThenElse> C(*G);auto* N=C.CreateNode();
  N->Rename(Name,G);N->NodePosX=X;N->NodePosY=Y;C.Finalize();return N;};
 auto* Enable=Call(EnableFunction,TEXT("ProphecyEnableCleanPike"),Begin->GetOwningNode()->NodePosX+250,Begin->GetOwningNode()->NodePosY-200);
 auto* Accept=Call(AcceptFunction,TEXT("ProphecyAcceptPike"),Pike->GetOwningNode()->NodePosX+250,Pike->GetOwningNode()->NodePosY-200);
 auto* Accepted=Branch(TEXT("ProphecyPikeAccepted"),Accept->NodePosX+320,Accept->NodePosY);
 auto* SkipRestore=Branch(TEXT("ProphecyPikeSkipRestore"),Velocity->GetOwningNode()->NodePosX-250,Velocity->GetOwningNode()->NodePosY-200);
 const auto* Schema=GetDefault<UEdGraphSchema_K2>();
 auto Link=[Schema](UEdGraphPin* A,UEdGraphPin* B){return A&&B&&Schema->TryCreateConnection(A,B);};
 bool OK=Link(Sword,Enable->FindPin(TEXT("Component")))&&Link(Sword,Accept->FindPin(TEXT("HitReceiver")))
  &&Link(Accept->GetReturnValuePin(),Accepted->GetConditionPin())&&Link(IsPike,SkipRestore->GetConditionPin());
 if(OK){
  Begin->BreakLinkTo(BeginNext);Pike->BreakLinkTo(PikeNext);BeforeVelocity->BreakLinkTo(Velocity);
  OK=Link(Begin,Enable->GetExecPin())&&Link(Enable->GetThenPin(),BeginNext)
   &&Link(Pike,Accept->GetExecPin())&&Link(Accept->GetThenPin(),Accepted->GetExecPin())
   &&Link(Accepted->GetThenPin(),AfterPose)&&Link(BeforeVelocity,SkipRestore->GetExecPin())
   &&Link(SkipRestore->GetThenPin(),AfterVelocity)&&Link(SkipRestore->GetElsePin(),Velocity);
 }
 if(!OK){
  const TArray<UEdGraphNode*> Added={Enable,Accept,Accepted,SkipRestore};
  for(UEdGraphNode* N:Added)FBlueprintEditorUtils::RemoveNode(BP,N,true);
  Link(Begin,BeginNext);Link(Pike,PikeNext);Link(BeforeVelocity,Velocity);
 }
 FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
 FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
 UE_LOG(LogTemp,Display,TEXT("Clean pike connections=%d status=%d saved=0"),OK,int32(BP->Status));
}
static void InstallPikeWoundCorrection()
{
 if(!GEditor||GEditor->PlayWorld)return;
 auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/sword/A_Sword.A_Sword"));
 auto* Lib=FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecyPhysicsConstraintBlueprintLibrary"));
 auto* Function=Lib?Lib->FindFunctionByName(TEXT("SetPikeWoundCorrection")):nullptr;
 if(!BP||!Function)return;
 UEdGraph* G=nullptr;for(UEdGraph* Graph:BP->UbergraphPages)if(Graph->GetFName()==TEXT("EventGraph"))G=Graph;
 if(!G)return;
 auto Find=[G](const TCHAR* Name)->UEdGraphNode*{for(UEdGraphNode* N:G->Nodes)if(N->GetFName()==Name)return N;return nullptr;};
 if(Find(TEXT("ProphecyPikeWoundCorrection")))return;
 auto Pin=[&](const TCHAR* N,const TCHAR* P)->UEdGraphPin*{auto* Node=Find(N);return Node?Node->FindPin(P):nullptr;};
 auto* Before=Pin(TEXT("K2Node_CallFunction_50"),TEXT("then"));
 auto* After=Pin(TEXT("K2Node_IfThenElse_1"),TEXT("execute"));
 auto* Constraint=Pin(TEXT("K2Node_AddComponent_0"),TEXT("ReturnValue"));
 auto* IsPike=Pin(TEXT("K2Node_VariableGet_22"),TEXT("temp pike"));
 if(!Before||!After||!Constraint||!IsPike||Before->LinkedTo.Num()!=1||Before->LinkedTo[0]!=After)
 {UE_LOG(LogTemp,Error,TEXT("Pike wound preflight: graph differs; no edits."));return;}
 const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","PikeWoundCorrection","Opt accepted pike constraints into wound correction"));
 BP->Modify();G->Modify();for(UEdGraphNode* N:G->Nodes)N->Modify();
 FGraphNodeCreator<UK2Node_IfThenElse> GateCreator(*G);auto* Gate=GateCreator.CreateNode();
 Gate->Rename(TEXT("ProphecyPikeCorrectionGate"),G);
 Gate->NodePosX=Before->GetOwningNode()->NodePosX+300;Gate->NodePosY=Before->GetOwningNode()->NodePosY-200;GateCreator.Finalize();
 FGraphNodeCreator<UK2Node_CallFunction> Creator(*G);auto* Node=Creator.CreateNode();
 Node->SetFromFunction(Function);Node->Rename(TEXT("ProphecyPikeWoundCorrection"),G);
 Node->NodePosX=Gate->NodePosX+300;Node->NodePosY=Gate->NodePosY;Creator.Finalize();
 const auto* Schema=GetDefault<UEdGraphSchema_K2>();
 auto Link=[Schema](UEdGraphPin* A,UEdGraphPin* B){return A&&B&&Schema->TryCreateConnection(A,B);};
 Schema->TrySetDefaultValue(*Node->FindPin(TEXT("Enabled")),TEXT("true"));
 bool OK=Link(Constraint,Node->FindPin(TEXT("Constraint")))&&Link(IsPike,Gate->GetConditionPin());
 if(OK){Before->BreakLinkTo(After);OK=Link(Before,Gate->GetExecPin())&&Link(Gate->GetThenPin(),Node->GetExecPin())
  &&Link(Gate->GetElsePin(),After)&&Link(Node->GetThenPin(),After);}
 if(!OK){FBlueprintEditorUtils::RemoveNode(BP,Node,true);FBlueprintEditorUtils::RemoveNode(BP,Gate,true);Link(Before,After);}
 FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
 FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
 UE_LOG(LogTemp,Display,TEXT("Pike wound correction installed=%d status=%d saved=0"),OK,int32(BP->Status));
}
static void RemoveSwordEndPlayFPS()
{
 if(!GEditor||GEditor->PlayWorld)return;
 auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/sword/A_Sword.A_Sword"));if(!BP)return;
 UEdGraph* Graph=nullptr;for(UEdGraph* G:BP->UbergraphPages)if(G->GetFName()==TEXT("EventGraph"))Graph=G;
 if(!Graph)return;
 auto Find=[&](const TCHAR* Name)->UK2Node_CallFunction*{for(UEdGraphNode* N:Graph->Nodes)if(N->GetFName()==Name)return Cast<UK2Node_CallFunction>(N);return nullptr;};
 auto* Fixed=Find(TEXT("K2Node_CallFunction_159"));auto* Cap=Find(TEXT("ProphecyEndPlayCap"));
 if(!Fixed&&!Cap){UE_LOG(LogTemp,Display,TEXT("Sword End Play FPS reset already absent."));return;}
 if(!Fixed||!Cap||Fixed->FunctionReference.GetMemberName()!=TEXT("SetFixedFrameRateRuntime"))return;
 if(Cap->FunctionReference.GetMemberName()!=TEXT("ExecuteConsoleCommand"))return;
 auto* Command=Cap->FindPin(TEXT("Command"));
 if(!Command||!Command->LinkedTo.IsEmpty()||!Command->DefaultValue.Equals(TEXT("t.MaxFPS 60"),ESearchCase::IgnoreCase))return;
 if(Fixed->GetExecPin()->LinkedTo.Num()!=1||Fixed->GetExecPin()->LinkedTo[0]->GetOwningNode()->GetFName()!=TEXT("K2Node_Event_4")
    ||Fixed->GetThenPin()->LinkedTo.Num()!=1||Fixed->GetThenPin()->LinkedTo[0]!=Cap->GetExecPin()
    ||Cap->GetExecPin()->LinkedTo.Num()!=1||!Cap->GetThenPin()->LinkedTo.IsEmpty())return;
 const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","RemoveSwordEndPlayFPS","Remove global FPS resets from sword End Play"));
 BP->Modify();Graph->Modify();Fixed->GetExecPin()->LinkedTo[0]->GetOwningNode()->Modify();
 FBlueprintEditorUtils::RemoveNode(BP,Cap,true);FBlueprintEditorUtils::RemoveNode(BP,Fixed,true);
 FBlueprintEditorUtils::MarkBlueprintAsModified(BP);
 FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
 UE_LOG(LogTemp,Display,TEXT("Removed sword End Play FPS/timestep reset; status=%d; not saved."),int32(BP->Status));
}
static void RefreshGripProfilePins(const TArray<FString>& Args)
{
 if(!GEditor||GEditor->PlayWorld)return;
 if(Args.Num()==1&&Args[0]==TEXT("RemoveSwordEndPlayFPS")){RemoveSwordEndPlayFPS();return;}
 if(Args.Num()==1&&Args[0]==TEXT("PikeWoundCorrection")){InstallPikeWoundCorrection();return;}
 if(Args.Num()==1&&Args[0]==TEXT("SwordDebugFrameCap")){RepairSwordDebugFrameCap();return;}
 if(Args.Num()==1&&Args[0]==TEXT("SwordSlowStartFrameCap")){RepairSwordSlowStartFrameCap();return;}
 if(Args.Num()==1&&Args[0]==TEXT("CleanPike")){InstallCleanPike();return;}
 if(Args.Num()==1&&Args[0]==TEXT("RemoveSwordTab")){RemoveSwordTabShortcut();return;}
 const bool Migrate=Args.Num()==3&&Args[0]==TEXT("ReturnRanges");
 const bool UpdateSpeeds=Args.Num()==3&&Args[0]==TEXT("SetSlideSpeeds");
 const bool Speeds=UpdateSpeeds||(Args.Num()==3&&Args[0]==TEXT("SlideSpeeds"));
 double Ends[2]={1,1};
 if(Migrate||Speeds)for(int I=0;I<2;++I){if(!LexTryParseString(Ends[I],*Args[I+1])||!FMath::IsFinite(Ends[I])||(Speeds?Ends[I]<=0:Ends[I]<.5||Ends[I]>1))return;}
 auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));if(!BP)return;
 TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);TArray<UK2Node_CallFunction*> Nodes;
 for(auto* G:Graphs)for(UEdGraphNode* N:G->Nodes)if(auto* C=Cast<UK2Node_CallFunction>(N))
  if(C->FunctionReference.GetMemberName()==TEXT("SetSwordHolsterProfile")&&(Speeds?(UpdateSpeeds||!C->FindPin(TEXT("DrawSlidingSpeed"))||!C->FindPin(TEXT("SheatheSlidingSpeed"))):(Migrate||!C->FindPin(TEXT("DrawNNBlendRange")))))Nodes.Add(C);
 if(Nodes.IsEmpty())return;
 if(UpdateSpeeds)for(auto* N:Nodes)for(const TCHAR* Name:{TEXT("DrawSlidingSpeed"),TEXT("SheatheSlidingSpeed")})
  if(const auto* Pin=N->FindPin(Name))if(!Pin->LinkedTo.IsEmpty()){UE_LOG(LogTemp,Error,TEXT("Slide speed update requires unlinked literals; nothing changed."));return;}
 if(!Speeds)for(auto* N:Nodes)for(const TCHAR* Name:{TEXT("FKReturnCutoff"),TEXT("SheatheFKReturnCutoff"),TEXT("DrawNNBlendRange"),TEXT("SheatheNNBlendRange")})
  if(const auto* Pin=N->FindPin(Name))if(!Pin->LinkedTo.IsEmpty()){UE_LOG(LogTemp,Error,TEXT("Return range migration requires unlinked literals; nothing changed."));return;}
 const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","HolsterProfilePins","Refresh sword holster profile pins"));BP->Modify();
 for(auto* N:Nodes){N->Modify();
  const TCHAR* SpeedNames[]={TEXT("DrawSlidingSpeed"),TEXT("SheatheSlidingSpeed")};
  const bool HadSpeed[]={N->FindPin(SpeedNames[0])!=nullptr,N->FindPin(SpeedNames[1])!=nullptr};
  if(!Speeds)for(const TCHAR* Name:{TEXT("FKReturnCutoff"),TEXT("SheatheFKReturnCutoff")})if(auto* Pin=N->FindPin(Name))N->RemovePin(Pin);
  if(!UpdateSpeeds||!HadSpeed[0]||!HadSpeed[1])N->ReconstructNode();
  if(Speeds)for(int I=0;I<2;++I)if(UpdateSpeeds||!HadSpeed[I])if(auto* Pin=N->FindPin(SpeedNames[I]))N->GetSchema()->TrySetDefaultValue(*Pin,FString::SanitizeFloat(Ends[I]));
  if(Migrate){const TCHAR* Names[]={TEXT("DrawNNBlendRange"),TEXT("SheatheNNBlendRange")};
   for(int I=0;I<2;++I)if(auto* Pin=N->FindPin(Names[I]))N->GetSchema()->TrySetDefaultValue(*Pin,FString::Printf(TEXT("(X=0.500000,Y=%.6f)"),Ends[I]));}
 }
 FBlueprintEditorUtils::MarkBlueprintAsModified(BP);FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
 UE_LOG(LogTemp,Display,TEXT("Refreshed %d existing holster profile nodes; not saved."),Nodes.Num());
}
static FAutoConsoleCommand GripProfilePins(TEXT("Prophecy.Editor.RefreshHolsterGripPins"),TEXT("Refresh profile pins; ReturnRanges <draw-end> <sheathe-end> migrates unlinked cutoffs. SlideSpeeds <draw> <sheathe> initializes only missing speed pins; SetSlideSpeeds updates existing unlinked literals. No save."),FConsoleCommandWithArgsDelegate::CreateStatic(&RefreshGripProfilePins));
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
