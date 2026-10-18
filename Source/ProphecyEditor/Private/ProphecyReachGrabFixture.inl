// Explicit Blueprint-only fixture installation. No native retained state or startup registration.
#include "K2Node_IfThenElse.h"
#include "K2Node_Self.h"
#include "K2Node_Knot.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Engine/StaticMeshActor.h"
#include "Components/StaticMeshComponent.h"
#include "EdGraphUtilities.h"
#include "UObject/SavePackage.h"

namespace ProphecyReachGrabFixture
{
void PrepareBeforeGrab(UBlueprint* BP,UEdGraph* Graph)
{
    for(UEdGraphNode* N:Graph->Nodes)if(N->NodeComment==TEXT("Reach grab fixture: activate balls at tick 29; grab once at tick 30."))return;
    auto Find=[&](FName Name)->UEdGraphNode* {for(UEdGraphNode* N:Graph->Nodes)if(N->GetFName()==Name)return N;return nullptr;};
    auto* Trigger=Cast<UK2Node_IfThenElse>(Find(TEXT("K2Node_IfThenElse_5")));
    auto* OldTick=Cast<UK2Node_CallFunction>(Find(TEXT("K2Node_CallFunction_31")));
    UK2Node_CallFunction* Takes[2]={};UK2Node_CallFunction* Admits[2]={};UK2Node_CallFunction* Sims[2]={};UEdGraphPin* Starts[2]={};
    for(UEdGraphNode* N:Graph->Nodes)if(auto* C=Cast<UK2Node_CallFunction>(N))if(C->FunctionReference.GetMemberName()==TEXT("GrabObject"))
    {
        const int Side=C->FindPinChecked(TEXT("Hand"))->DefaultValue==TEXT("Left")?0:1;
        if(C->GetExecPin()->LinkedTo.Num()!=1)return;
        Takes[Side]=C;Admits[Side]=Cast<UK2Node_CallFunction>(C->GetExecPin()->LinkedTo[0]->GetOwningNode());
        if(!Admits[Side]||Admits[Side]->FunctionReference.GetMemberName()!=TEXT("EnableJoltStaticMeshPhysics")||Admits[Side]->GetExecPin()->LinkedTo.Num()!=1)return;
        Sims[Side]=Cast<UK2Node_CallFunction>(Admits[Side]->GetExecPin()->LinkedTo[0]->GetOwningNode());
        if(!Sims[Side]||Sims[Side]->FunctionReference.GetMemberName()!=TEXT("SetSimulatePhysics")||Sims[Side]->GetExecPin()->LinkedTo.Num()!=1)return;
        Starts[Side]=Sims[Side]->GetExecPin()->LinkedTo[0];
    }
    if(!Trigger||!OldTick||!Takes[0]||!Takes[1]||!Trigger->GetElsePin()->LinkedTo.IsEmpty())return;
    const FScopedTransaction Tx(NSLOCTEXT("Prophecy","PrepareReachGrabFixture","Prepare grab spheres one tick before reaching"));
    BP->Modify();Graph->Modify();Trigger->Modify();
    auto* Schema=GetDefault<UEdGraphSchema_K2>();bool OK=true;
    auto Link=[&](UEdGraphPin*A,UEdGraphPin*B){OK&=A&&B&&Schema->TryCreateConnection(A,B);};
    FGraphNodeCreator<UK2Node_CallFunction> TC(*Graph);auto* Tick=TC.CreateNode();Tick->SetFromFunction(OldTick->GetTargetFunction());Tick->NodePosX=Trigger->NodePosX;Tick->NodePosY=Trigger->NodePosY+400;TC.Finalize();
    Schema->TrySetDefaultValue(*Tick->FindPinChecked(TEXT("i")),TEXT("29"));Schema->TrySetDefaultValue(*Tick->FindPinChecked(TEXT("modulo")),TEXT("-1"));
    FGraphNodeCreator<UK2Node_IfThenElse> GC(*Graph);auto* Gate=GC.CreateNode();Gate->NodePosX=Trigger->NodePosX+300;Gate->NodePosY=Trigger->NodePosY+400;GC.Finalize();
    Gate->NodeComment=TEXT("Reach grab fixture: activate balls at tick 29; grab once at tick 30.");Gate->bCommentBubbleVisible=true;
    Link(Trigger->GetElsePin(),Gate->GetExecPin());Link(Tick->FindPin(TEXT("=")),Gate->GetConditionPin());
    UEdGraphPin* Exec=Gate->GetThenPin();
    for(int Side=0;Side<2;++Side)
    {
        Sims[Side]->Modify();Admits[Side]->Modify();Takes[Side]->Modify();Starts[Side]->GetOwningNode()->Modify();
        Starts[Side]->BreakLinkTo(Sims[Side]->GetExecPin());Admits[Side]->GetThenPin()->BreakLinkTo(Takes[Side]->GetExecPin());
        Link(Starts[Side],Takes[Side]->GetExecPin());
        auto* Object=Takes[Side]->FindPinChecked(TEXT("Object"));if(Object->LinkedTo.Num()!=1)return;
        FGraphNodeCreator<UK2Node_CallFunction> VC(*Graph);auto* Valid=VC.CreateNode();Valid->SetFromFunction(UKismetSystemLibrary::StaticClass()->FindFunctionByName(TEXT("IsValid")));Valid->NodePosX=Gate->NodePosX+300+Side*1000;Valid->NodePosY=Gate->NodePosY+220;VC.Finalize();
        FGraphNodeCreator<UK2Node_IfThenElse> BC(*Graph);auto* Check=BC.CreateNode();Check->NodePosX=Valid->NodePosX;Check->NodePosY=Gate->NodePosY;BC.Finalize();
        Link(Object->LinkedTo[0],Valid->FindPin(TEXT("Object")));Link(Valid->GetReturnValuePin(),Check->GetConditionPin());Link(Exec,Check->GetExecPin());Link(Check->GetThenPin(),Sims[Side]->GetExecPin());
        Sims[Side]->NodePosX=Check->NodePosX+300;Sims[Side]->NodePosY=Gate->NodePosY;
        Admits[Side]->NodePosX=Check->NodePosX+600;Admits[Side]->NodePosY=Gate->NodePosY;
        Exec=Admits[Side]->GetThenPin();
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    FFileHelper::SaveStringToFile(FString::Printf(TEXT("connections_ok=%d status=%d prepare_tick=29 grab_tick=30 saved=0\n"),OK,int32(BP->Status)),*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/ReachGrabWiring20261015/preparation.txt")));
}
void Install()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP || !BP->GeneratedClass) return;
    UEdGraph* Graph=nullptr;
    for (UEdGraph* G:BP->FunctionGraphs) if (G->GetFName()==TEXT("tick debugging")) Graph=G;
    if (!Graph) return;
    auto Find=[&](FName Name)->UEdGraphNode* {for (UEdGraphNode* N:Graph->Nodes) if(N->GetFName()==Name)return N;return nullptr;};
    auto* Branch=Cast<UK2Node_IfThenElse>(Find(TEXT("K2Node_IfThenElse_5")));
    auto* Tick=Cast<UK2Node_CallFunction>(Find(TEXT("K2Node_CallFunction_31")));
    auto* Tail=Find(TEXT("K2Node_Knot_58"));
    for(UEdGraphNode* N:Graph->Nodes)if(N->NodeComment.StartsWith(TEXT("Reach grab fixture"))){PrepareBeforeGrab(BP,Graph);return;}
    if (!Branch || !Tick || !Tail || Tick->FunctionReference.GetMemberName()!=TEXT("is tick") ||
        Tick->FindPinChecked(TEXT("i"))->DefaultValue!=TEXT("30") || Tick->FindPinChecked(TEXT("modulo"))->DefaultValue!=TEXT("-1") ||
        Branch->GetThenPin()->LinkedTo.Num()!=1 || Branch->GetThenPin()->LinkedTo[0]!=Tail->FindPin(TEXT("InputPin")) ||
        !Tail->FindPinChecked(TEXT("OutputPin"))->LinkedTo.IsEmpty())
    { UE_LOG(LogTemp,Error,TEXT("Reach fixture: tick-30 graph differs; nothing changed."));return; }
    const FName Variables[]={TEXT("Left Grab Ball"),TEXT("Right Grab Ball")};
    for(FName V:Variables)if(FindFProperty<FProperty>(BP->GeneratedClass,V))return;
    auto Function=[](const TCHAR* ClassPath,FName Name)->UFunction* {
        auto* Class=LoadObject<UClass>(nullptr,ClassPath);return Class?Class->FindFunctionByName(Name):nullptr;
    };
    UFunction* Grab=Function(TEXT("/Script/GameAnimationSample3.ProphecyReachLibrary"),TEXT("GrabObject"));
    UFunction* Enable=Function(TEXT("/Script/GameAnimationSample3.ProphecyJoltStaticMeshLibrary"),TEXT("EnableJoltStaticMeshPhysics"));
    UFunction* Pose=BP->ParentClass->FindFunctionByName(TEXT("GetPoseReferenceMesh"));
    UFunction* Socket=USceneComponent::StaticClass()->FindFunctionByName(TEXT("GetSocketLocation"));
    UFunction* Closest=UPrimitiveComponent::StaticClass()->FindFunctionByName(TEXT("GetClosestPointOnCollision"));
    UFunction* Sim=UPrimitiveComponent::StaticClass()->FindFunctionByName(TEXT("SetSimulatePhysics"));
    UFunction* Visual=Function(TEXT("/Script/GameAnimationSample3.ProphecyReachLibrary"),TEXT("SetReachVisualization"));
    UFunction* Valid=UKismetSystemLibrary::StaticClass()->FindFunctionByName(TEXT("IsValid"));
    UFunction* Hide=BP->ParentClass->FindFunctionByName(TEXT("HideSword"));
    if(!Grab||!Enable||!Pose||!Socket||!Closest||!Sim||!Visual||!Valid||!Hide)return;
    const FString Folder=FPaths::ProjectSavedDir()/TEXT("Diagnostics/ReachGrabWiring20261015");
    IFileManager::Get().MakeDirectory(*Folder,true);
    FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;Save.SaveFlags=SAVE_KeepDirty;
    if(!UPackage::SavePackage(BP->GetOutermost(),BP,*(Folder/TEXT("PoseAgent-live-before.uasset")),Save))return;
    TSet<UObject*> OldNodes;for(UEdGraphNode* N:Graph->Nodes)OldNodes.Add(N);
    FString Export;FEdGraphUtilities::ExportNodesToText(OldNodes,Export);
    FFileHelper::SaveStringToFile(Export,*(Folder/TEXT("tick-before-export.txt")));
    const FScopedTransaction Tx(NSLOCTEXT("Prophecy","ReachGrabFixture","Wire two-ball grab at tick 30"));
    BP->Modify();Graph->Modify();Tail->Modify();
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();
    FEdGraphPinType Type;Type.PinCategory=UEdGraphSchema_K2::PC_Object;Type.PinSubCategoryObject=AStaticMeshActor::StaticClass();
    for(FName V:Variables){FBlueprintEditorUtils::AddMemberVariable(BP,V,Type);FBlueprintEditorUtils::SetBlueprintOnlyEditableFlag(BP,V,false);FBlueprintEditorUtils::SetBlueprintVariableCategory(BP,V,nullptr,FText::FromString(TEXT("Reach Grab Experiment")));}
    TArray<UEdGraphNode*> Added;
    const int32 X=Tail->NodePosX+320,Y=Tail->NodePosY;
    auto Call=[&](UFunction* F,int32 DX,int32 DY){FGraphNodeCreator<UK2Node_CallFunction>C(*Graph);auto* N=C.CreateNode();N->SetFromFunction(F);N->NodePosX=X+DX;N->NodePosY=Y+DY;C.Finalize();Added.Add(N);return N;};
    auto Get=[&](FName Name,UClass* Owner,int32 DX,int32 DY){FGraphNodeCreator<UK2Node_VariableGet>C(*Graph);auto* N=C.CreateNode();if(Owner)N->VariableReference.SetExternalMember(Name,Owner);else N->VariableReference.SetSelfMember(Name);N->NodePosX=X+DX;N->NodePosY=Y+DY;C.Finalize();Added.Add(N);return N;};
    auto Gate=[&](int32 DX,int32 DY){FGraphNodeCreator<UK2Node_IfThenElse>C(*Graph);auto*N=C.CreateNode();N->NodePosX=X+DX;N->NodePosY=Y+DY;C.Finalize();Added.Add(N);return N;};
    FGraphNodeCreator<UK2Node_Self> SC(*Graph);auto* Self=SC.CreateNode();Self->NodePosX=X;Self->NodePosY=Y-200;SC.Finalize();Added.Add(Self);
    bool OK=true;
    auto Link=[&](UEdGraphPin*A,UEdGraphPin*B){OK&=A&&B&&Schema->TryCreateConnection(A,B);};
    auto Set=[&](UEdGraphNode*N,FName Name,const TCHAR* Value){auto*P=N->FindPin(Name);if(P)Schema->TrySetDefaultValue(*P,Value);else OK=false;};
    auto* Mesh=Call(Pose,0,-400);
    UEdGraphPin* Exec=Tail->FindPin(TEXT("OutputPin"));
    for(int32 Side=0;Side<2;++Side)
    {
        const int32 DX=Side*1900;
        auto* Ball=Get(Variables[Side],nullptr,DX,250);
        auto* IsValid=Call(Valid,DX+200,250);Link(Ball->FindPin(Variables[Side]),IsValid->FindPin(TEXT("Object")));
        auto* Check=Gate(DX+400,0);Link(Exec,Check->GetExecPin());Link(IsValid->GetReturnValuePin(),Check->GetConditionPin());
        Check->NodeComment=TEXT("Reach grab fixture: assign this hand's sphere on the agent instance. Unassigned agents skip it.");
        auto* Component=Get(TEXT("StaticMeshComponent"),AStaticMeshActor::StaticClass(),DX+400,300);
        Link(Ball->FindPin(Variables[Side]),Component->FindPin(TEXT("self")));
        auto* ComponentPin=Component->FindPin(TEXT("StaticMeshComponent"));
        UEdGraphPin* Start=Check->GetThenPin();
        if(Side==0){auto* HideSword=Call(Hide,DX+500,-180);Link(Start,HideSword->GetExecPin());Start=HideSword->GetThenPin();}
        auto* Simulate=Call(Sim,DX+650,0);Set(Simulate,TEXT("bSimulate"),TEXT("true"));Link(Start,Simulate->GetExecPin());Link(ComponentPin,Simulate->FindPin(TEXT("self")));
        auto* Admit=Call(Enable,DX+900,0);Link(Simulate->GetThenPin(),Admit->GetExecPin());Link(ComponentPin,Admit->FindPin(TEXT("Mesh")));
        auto* Wrist=Call(Socket,DX+650,650);Set(Wrist,TEXT("InSocketName"),Side==0?TEXT("hand_l"):TEXT("hand_r"));Link(Mesh->GetReturnValuePin(),Wrist->FindPin(TEXT("self")));
        auto* Surface=Call(Closest,DX+950,400);Link(ComponentPin,Surface->FindPin(TEXT("self")));Link(Wrist->GetReturnValuePin(),Surface->FindPin(TEXT("Point")));
        auto* Take=Call(Grab,DX+1300,0);Set(Take,TEXT("Hand"),Side==0?TEXT("Left"):TEXT("Right"));Set(Take,TEXT("MaxReachSpeed"),TEXT("120"));Set(Take,TEXT("MaxRotationSpeed"),TEXT("180"));Set(Take,TEXT("UseSurfacePoint"),TEXT("true"));
        Link(Admit->GetThenPin(),Take->GetExecPin());Link(Self->FindPin(TEXT("self")),Take->FindPin(TEXT("Agent")));Link(ComponentPin,Take->FindPin(TEXT("Object")));Link(Surface->FindPin(TEXT("OutPointOnBody")),Take->FindPin(TEXT("SurfacePoint")));
        Take->AdvancedPinDisplay=ENodeAdvancedPins::Shown;
        Exec=Take->GetThenPin();
    }
    auto* Show=Call(Visual,3800,0);Link(Exec,Show->GetExecPin());Link(Self->FindPin(TEXT("self")),Show->FindPin(TEXT("Agent")));Set(Show,TEXT("Enabled"),TEXT("true"));
    if(!OK){for(auto*N:Added)FBlueprintEditorUtils::RemoveNode(BP,N,true);for(FName V:Variables)FBlueprintEditorUtils::RemoveMemberVariable(BP,V);UE_LOG(LogTemp,Error,TEXT("Reach fixture: pin connection failed; additions rolled back."));return;}
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    FFileHelper::SaveStringToFile(FString::Printf(TEXT("connections_ok=1 status=%d nodes=%d saved=0\n"),int32(BP->Status),Added.Num()),*(Folder/TEXT("wiring.txt")));
    PrepareBeforeGrab(BP,Graph);
}
}
