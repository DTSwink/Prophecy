#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Event.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_ExecutionSequence.h"
#include "K2Node_MakeArray.h"
#include "K2Node_GetArrayItem.h"
#include "K2Node_Self.h"
#include "K2Node_Select.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "UObject/SavePackage.h"

// Author ordinary Blueprint nodes, not a native per-frame demo controller.
namespace ProphecyCombatDemoSetup
{
struct FGraph
{
    UEdGraph* Graph; bool OK=true;
    UEdGraphPin* Pin(UEdGraphNode* N,const TCHAR* Name)
    {
        auto* P=N?N->FindPin(Name):nullptr;
        if (!P) { OK=false;UE_LOG(LogTemp,Error,TEXT("CombatDemo: missing pin %s on %s"),Name,*GetNameSafe(N)); }
        return P;
    }
    void Link(UEdGraphPin* A,UEdGraphPin* B)
    { if (!A || !B || !GetDefault<UEdGraphSchema_K2>()->TryCreateConnection(A,B)) OK=false; }
    void Link(UEdGraphNode* A,const TCHAR* AP,UEdGraphNode* B,const TCHAR* BP) { Link(Pin(A,AP),Pin(B,BP)); }
    void Exec(UEdGraphNode* A,UEdGraphNode* B) { Link(A,TEXT("then"),B,TEXT("execute")); }
    void Default(UEdGraphNode* N,const TCHAR* P,const TCHAR* Value)
    { if(auto* PinValue=Pin(N,P)) GetDefault<UEdGraphSchema_K2>()->TrySetDefaultValue(*PinValue,Value); }
    template<class T> T* Node(int32 X,int32 Y)
    { FGraphNodeCreator<T> C(*Graph);auto* N=C.CreateNode();N->NodePosX=X;N->NodePosY=Y;C.Finalize();return N; }
    UK2Node_CallFunction* Call(UClass* Class,const TCHAR* Name,int32 X,int32 Y)
    {
        UFunction* F=Class?Class->FindFunctionByName(Name):nullptr;
        if (!F) { OK=false;UE_LOG(LogTemp,Error,TEXT("CombatDemo: missing function %s"),Name);return nullptr; }
        FGraphNodeCreator<UK2Node_CallFunction> C(*Graph);auto* N=C.CreateNode();N->SetFromFunction(F);N->NodePosX=X;N->NodePosY=Y;C.Finalize();return N;
    }
    template<class T> T* Variable(const TCHAR* Name,int32 X,int32 Y)
    { FGraphNodeCreator<T> C(*Graph);auto* N=C.CreateNode();N->VariableReference.SetSelfMember(Name);N->NodePosX=X;N->NodePosY=Y;C.Finalize();return N; }
    UK2Node_VariableGet* Get(const TCHAR* Name,int32 X,int32 Y) { return Variable<UK2Node_VariableGet>(Name,X,Y); }
    UK2Node_VariableSet* Set(const TCHAR* Name,int32 X,int32 Y) { return Variable<UK2Node_VariableSet>(Name,X,Y); }
};

void RetireDemoCubeBeforeDisablingCollision(UBlueprint* BP)
{
    for (UEdGraph* Graph:BP->FunctionGraphs) if (Graph->GetFName()==TEXT("KinematicAttackDefenseDemo"))
    {
        UK2Node_CallFunction* Collision=nullptr;
        for (UEdGraphNode* N:Graph->Nodes) if (auto* C=Cast<UK2Node_CallFunction>(N))
        {
            if (C->FunctionReference.GetMemberName()==TEXT("DisableJoltStaticMeshPhysics")) return;
            if (C->FunctionReference.GetMemberName()==TEXT("SetCollisionEnabled")) Collision=C;
        }
        if (!Collision) return;
        auto* Exec=Collision->FindPinChecked(TEXT("execute"));auto* Target=Collision->FindPinChecked(TEXT("self"));
        if (Exec->LinkedTo.Num()!=1 || Target->LinkedTo.Num()!=1) return;
        BP->Modify();Graph->Modify();FGraph G{Graph};
        auto* Before=Exec->LinkedTo[0];auto* Cube=Target->LinkedTo[0];
        auto* Retire=G.Call(FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecyJoltStaticMeshLibrary")),TEXT("DisableJoltStaticMeshPhysics"),Collision->NodePosX,Collision->NodePosY+600);
        G.Link(Cube,G.Pin(Retire,TEXT("Mesh")));Exec->BreakLinkTo(Before);G.Link(Before,G.Pin(Retire,TEXT("execute")));G.Exec(Retire,Collision);
        Retire->NodeComment=TEXT("Retire the imported Jolt body before removing its query receiver. This demo does not need a simulated Magic Cube.");Retire->bCommentBubbleVisible=true;
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
        if (G.OK && BP->Status!=BS_Error)
        {
            FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;
            const FString Filename=FPackageName::LongPackageNameToFilename(BP->GetOutermost()->GetName(),FPackageName::GetAssetPackageExtension());
            UPackage::SavePackage(BP->GetOutermost(),BP,*Filename,Save);
            UE_LOG(LogTemp,Display,TEXT("CombatDemo: cube retirement installed."));
        }
        return;
    }
}

void GuardDemoInitialization(UBlueprint* BP)
{
    for (UEdGraph* Graph:BP->FunctionGraphs) if (Graph->GetFName()==TEXT("KinematicAttackDefenseDemo"))
    {
        UK2Node_VariableGet* Initialized=nullptr;
        for (UEdGraphNode* N:Graph->Nodes)
        {
            if (N->NodeComment==TEXT("Keep the demo kinematic after deferred BeginPlay setup.")) return;
            if (auto* V=Cast<UK2Node_VariableGet>(N);V && V->VariableReference.GetMemberName()==TEXT("CombatDemoInitialized")) Initialized=V;
        }
        auto* Value=Initialized?Initialized->FindPin(TEXT("CombatDemoInitialized")):nullptr;
        if (!Value || Value->LinkedTo.Num()!=1) return;
        BP->Modify();Graph->Modify();FGraph G{Graph};auto* Condition=Value->LinkedTo[0];
        auto* Mode=G.Call(FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecyAgent")),TEXT("GetSimulationMode"),1300,-700);
        auto* Math=FindObject<UClass>(nullptr,TEXT("/Script/Engine.KismetMathLibrary"));
        auto* Equal=G.Call(Math,TEXT("EqualEqual_ByteByte"),1600,-700);G.Link(Mode,TEXT("ReturnValue"),Equal,TEXT("A"));G.Default(Equal,TEXT("B"),TEXT("0"));
        auto* Both=G.Call(Math,TEXT("BooleanAND"),1800,-400);Both->NodeComment=TEXT("Keep the demo kinematic after deferred BeginPlay setup.");Both->bCommentBubbleVisible=true;
        Value->BreakLinkTo(Condition);G.Link(Value,G.Pin(Both,TEXT("A")));G.Link(Equal,TEXT("ReturnValue"),Both,TEXT("B"));G.Link(G.Pin(Both,TEXT("ReturnValue")),Condition);
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
        if (G.OK && BP->Status!=BS_Error)
        {
            FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;
            const FString Filename=FPackageName::LongPackageNameToFilename(BP->GetOutermost()->GetName(),FPackageName::GetAssetPackageExtension());
            UPackage::SavePackage(BP->GetOutermost(),BP,*Filename,Save);
            UE_LOG(LogTemp,Display,TEXT("CombatDemo: deferred startup guard installed."));
        }
        return;
    }
}

void Install()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP || !BP->GeneratedClass) return;
    const FName Name(TEXT("KinematicAttackDefenseDemo"));
    if (BP->GeneratedClass->FindFunctionByName(Name)) { RetireDemoCubeBeforeDisablingCollision(BP);GuardDemoInitialization(BP);UE_LOG(LogTemp,Display,TEXT("CombatDemo: already installed."));return; }
    UClass* Agent=FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecyAgent"));
    UClass* Defense=FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecyNNDefenseLibrary"));
    UClass* Math=FindObject<UClass>(nullptr,TEXT("/Script/Engine.KismetMathLibrary"));
    UClass* System=FindObject<UClass>(nullptr,TEXT("/Script/Engine.KismetSystemLibrary"));
    UClass* Gameplay=FindObject<UClass>(nullptr,TEXT("/Script/Engine.GameplayStatics"));
    UClass* Primitive=FindObject<UClass>(nullptr,TEXT("/Script/Engine.PrimitiveComponent"));
    if (!Agent || !Defense || !Math || !System || !Gameplay || !Primitive) return;
    auto* EventGraph=FBlueprintEditorUtils::FindEventGraph(BP);
    UK2Node_Event* Tick=nullptr;
    for (UEdGraphNode* N:EventGraph->Nodes) if (auto* E=Cast<UK2Node_Event>(N);E && E->EventReference.GetMemberName()==TEXT("ReceiveTick")) Tick=E;
    auto* TickThen=Tick?Tick->FindPin(TEXT("then")):nullptr;
    if (!TickThen || TickThen->LinkedTo.Num()!=1) return;
    UEdGraphPin* OldInput=TickThen->LinkedTo[0];
    auto* InputCall=Cast<UK2Node_CallFunction>(OldInput->GetOwningNode());
    if (!InputCall || InputCall->FunctionReference.GetMemberName()!=TEXT("input debugging")) return;
    const FString Filename=FPackageName::LongPackageNameToFilename(BP->GetOutermost()->GetName(),FPackageName::GetAssetPackageExtension());
    const FString Backup=FPaths::ProjectSavedDir()/TEXT("Diagnostics/CombatDemo/Backup")/FDateTime::Now().ToString(TEXT("%Y%m%d-%H%M%S"));
    IFileManager::Get().MakeDirectory(*Backup,true);
    if (IFileManager::Get().Copy(*(Backup/TEXT("Disk-BP_ProphecyManualPoseAgent.uasset")),*Filename,false)!=COPY_OK) return;
    FSavePackageArgs Snapshot;Snapshot.TopLevelFlags=RF_Public|RF_Standalone;Snapshot.SaveFlags=SAVE_KeepDirty;
    if (!UPackage::SavePackage(BP->GetOutermost(),BP,*(Backup/TEXT("Current-BP_ProphecyManualPoseAgent.uasset")),Snapshot)) return;
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","CombatDemo","Add removable kinematic attack and defense demo"));
    BP->Modify();EventGraph->Modify();Tick->Modify();InputCall->Modify();
    TArray<FName> Added;
    auto Var=[&](const TCHAR* N,const FName Type,const TCHAR* Value,UObject* Sub=nullptr,bool Editable=true)
    {
        FEdGraphPinType T;T.PinCategory=Type;T.PinSubCategoryObject=Sub;
        if (!FBlueprintEditorUtils::AddMemberVariable(BP,N,T,Value)) return false;
        Added.Add(N);FBlueprintEditorUtils::SetBlueprintOnlyEditableFlag(BP,N,!Editable);
        FBlueprintEditorUtils::SetBlueprintVariableCategory(BP,N,nullptr,FText::FromString(TEXT("Debug|Combat Demo")),true);return true;
    };
    bool OK=Var(TEXT("CombatDemoEnabled"),UEdGraphSchema_K2::PC_Boolean,TEXT("false"))
        && Var(TEXT("CombatDemoUseDodge"),UEdGraphSchema_K2::PC_Boolean,TEXT("true"))
        && Var(TEXT("CombatDemoOpponent"),UEdGraphSchema_K2::PC_Object,TEXT("None"),Agent)
        && Var(TEXT("CombatDemoAttackEveryFrames"),UEdGraphSchema_K2::PC_Int,TEXT("60"))
        && Var(TEXT("CombatDemoFrame"),UEdGraphSchema_K2::PC_Int,TEXT("0"),nullptr,false)
        && Var(TEXT("CombatDemoInitialized"),UEdGraphSchema_K2::PC_Boolean,TEXT("false"),nullptr,false)
        && Var(TEXT("CombatDemoLastAttack"),UEdGraphSchema_K2::PC_Name,TEXT("None"),nullptr,false)
        && Var(TEXT("CombatDemoError"),UEdGraphSchema_K2::PC_String,TEXT(""),nullptr,false);
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    UEdGraph* Graph=FBlueprintEditorUtils::CreateNewGraph(BP,Name,UEdGraph::StaticClass(),UEdGraphSchema_K2::StaticClass());
    FBlueprintEditorUtils::AddFunctionGraph<UClass>(BP,Graph,true,nullptr);
    FGraph G{Graph};
    TArray<UK2Node_FunctionEntry*> Entries;Graph->GetNodesOfClass(Entries);
    if (Entries.Num()!=1) return;
    auto* Entry=Entries[0];
    Entry->NodeComment=TEXT("One opt-in demo. Enabled pair skips input debugging; disabled uses the original input path. 60 means actor/game frames, not 30 Hz NN steps. Switch Use Dodge on the possessed attacker.");
    Entry->bCommentBubbleVisible=true;
    auto* Enabled=G.Get(TEXT("CombatDemoEnabled"),0,180);auto* Gate=G.Node<UK2Node_IfThenElse>(300,0);
    G.Exec(Entry,Gate);G.Link(Enabled,TEXT("CombatDemoEnabled"),Gate,TEXT("Condition"));
    auto* Original=G.Call(BP->GeneratedClass,TEXT("input debugging"),600,-240);G.Link(Gate,TEXT("else"),Original,TEXT("execute"));
    auto* Opp=G.Get(TEXT("CombatDemoOpponent"),600,220);
    auto* Valid=G.Call(System,TEXT("IsValid"),600,100);G.Link(Opp,TEXT("CombatDemoOpponent"),Valid,TEXT("Object"));
    auto* ValidGate=G.Node<UK2Node_IfThenElse>(900,0);G.Exec(Gate,ValidGate);G.Link(Valid,TEXT("ReturnValue"),ValidGate,TEXT("Condition"));
    auto* Ready=G.Call(Agent,TEXT("HasValidAgentHandle"),900,250);
    auto* OppReady=G.Call(Agent,TEXT("HasValidAgentHandle"),900,400);G.Link(Opp,TEXT("CombatDemoOpponent"),OppReady,TEXT("self"));
    auto* Both=G.Call(Math,TEXT("BooleanAND"),1200,250);G.Link(Ready,TEXT("ReturnValue"),Both,TEXT("A"));G.Link(OppReady,TEXT("ReturnValue"),Both,TEXT("B"));
    auto* ReadyGate=G.Node<UK2Node_IfThenElse>(1500,0);G.Exec(ValidGate,ReadyGate);G.Link(Both,TEXT("ReturnValue"),ReadyGate,TEXT("Condition"));
    auto* Init=G.Get(TEXT("CombatDemoInitialized"),1500,180);auto* InitGate=G.Node<UK2Node_IfThenElse>(1800,0);G.Exec(ReadyGate,InitGate);G.Link(Init,TEXT("CombatDemoInitialized"),InitGate,TEXT("Condition"));
    auto* Mode=G.Call(Agent,TEXT("SetSimulationMode"),2100,400);G.Default(Mode,TEXT("NewMode"),TEXT("Kinematic"));G.Link(InitGate,TEXT("else"),Mode,TEXT("execute"));
    auto* Cube=G.Get(TEXT("magic Cube"),2100,850);
    auto* Collision=G.Call(Primitive,TEXT("SetCollisionEnabled"),2500,400);G.Default(Collision,TEXT("NewType"),TEXT("NoCollision"));G.Link(Cube,TEXT("magic Cube"),Collision,TEXT("self"));G.Exec(Mode,Collision);
    auto* StopCube=G.Call(Primitive,TEXT("SetSimulatePhysics"),2900,400);G.Default(StopCube,TEXT("bSimulate"),TEXT("false"));G.Link(Cube,TEXT("magic Cube"),StopCube,TEXT("self"));G.Exec(Collision,StopCube);
    auto* StopInput=G.Call(Agent,TEXT("StopLocomotionInput"),3300,400);G.Exec(StopCube,StopInput);
    auto* StopAttack=G.Call(Agent,TEXT("StopNNAttack"),3650,400);G.Exec(StopInput,StopAttack);
    auto* Hide=G.Call(Agent,TEXT("HideSword"),4000,400);G.Exec(StopAttack,Hide);
    auto* Calf=G.Call(Agent,TEXT("SetAttackCalfClamp"),4350,400);G.Default(Calf,TEXT("bEnabled"),TEXT("false"));G.Exec(Hide,Calf);
    auto* Foot=G.Call(Agent,TEXT("SetAttackFootClamp"),4700,400);G.Default(Foot,TEXT("bEnabled"),TEXT("false"));G.Exec(Calf,Foot);
    auto* Done=G.Set(TEXT("CombatDemoInitialized"),5100,400);G.Default(Done,TEXT("CombatDemoInitialized"),TEXT("true"));G.Exec(Foot,Done);
    auto* Sequence=G.Node<UK2Node_ExecutionSequence>(5500,0);G.Exec(InitGate,Sequence);G.Exec(Done,Sequence);
    auto* Pose=G.Call(Agent,TEXT("ApplyNNPoseKinematically"),5900,1000);G.Link(Sequence,TEXT("then_1"),Pose,TEXT("execute"));
    auto* Dt=G.Call(Gameplay,TEXT("GetWorldDeltaSeconds"),5500,1200);G.Link(Dt,TEXT("ReturnValue"),Pose,TEXT("DeltaSeconds"));
    auto* Player=G.Call(Agent,TEXT("IsPlayerControlled"),5500,250);auto* PlayerGate=G.Node<UK2Node_IfThenElse>(5900,0);
    G.Link(Sequence,TEXT("then_0"),PlayerGate,TEXT("execute"));G.Link(Player,TEXT("ReturnValue"),PlayerGate,TEXT("Condition"));
    auto* Count=G.Get(TEXT("CombatDemoFrame"),5900,300);auto* Add=G.Call(Math,TEXT("Add_IntInt"),6200,300);G.Default(Add,TEXT("B"),TEXT("1"));G.Link(Count,TEXT("CombatDemoFrame"),Add,TEXT("A"));
    auto* SetCount=G.Set(TEXT("CombatDemoFrame"),6500,0);G.Exec(PlayerGate,SetCount);G.Link(Add,TEXT("ReturnValue"),SetCount,TEXT("CombatDemoFrame"));
    auto* Period=G.Get(TEXT("CombatDemoAttackEveryFrames"),6200,600);auto* Max=G.Call(Math,TEXT("Max"),6500,600);G.Default(Max,TEXT("B"),TEXT("1"));G.Link(Period,TEXT("CombatDemoAttackEveryFrames"),Max,TEXT("A"));
    auto* Mod=G.Call(Math,TEXT("Percent_IntInt"),6800,300);G.Link(SetCount,TEXT("Output_Get"),Mod,TEXT("A"));G.Link(Max,TEXT("ReturnValue"),Mod,TEXT("B"));
    auto* Eq=G.Call(Math,TEXT("EqualEqual_IntInt"),7100,300);G.Link(Mod,TEXT("ReturnValue"),Eq,TEXT("A"));G.Default(Eq,TEXT("B"),TEXT("0"));
    auto* Due=G.Node<UK2Node_IfThenElse>(7400,0);G.Exec(SetCount,Due);G.Link(Eq,TEXT("ReturnValue"),Due,TEXT("Condition"));
    auto* Attacks=G.Node<UK2Node_MakeArray>(7100,650);
    Attacks->GetOutputPin()->PinType.PinCategory=UEdGraphSchema_K2::PC_Name;
    const TCHAR* Families[]={TEXT("jabL"),TEXT("jabR"),TEXT("hookL"),TEXT("hookR"),TEXT("overL"),TEXT("overR"),TEXT("headbutt"),TEXT("kickL"),TEXT("kickR")};
    for (int32 I=1;I<UE_ARRAY_COUNT(Families);++I) Attacks->AddInputPin();
    for (auto* P:Attacks->Pins) P->PinType.PinCategory=UEdGraphSchema_K2::PC_Name;
    for (int32 I=0;I<UE_ARRAY_COUNT(Families);++I) G.Default(Attacks,*FString::Printf(TEXT("[%d]"),I),Families[I]);
    Attacks->NodeComment=TEXT("Unarmed melee pool. Edit these names to choose attacks. Sword attacks also require equipping the attacker instead of Hide Sword above.");Attacks->bCommentBubbleVisible=true;
    auto* Item=G.Node<UK2Node_GetArrayItem>(7700,650);G.Link(Attacks->GetOutputPin(),Item->GetTargetArrayPin());
    auto* Random=G.Call(Math,TEXT("RandomInteger"),7400,1150);G.Default(Random,TEXT("Max"),TEXT("9"));G.Link(G.Pin(Random,TEXT("ReturnValue")),Item->GetIndexPin());
    auto* Last=G.Set(TEXT("CombatDemoLastAttack"),8000,0);G.Exec(Due,Last);G.Link(Item->GetResultPin(),G.Pin(Last,TEXT("CombatDemoLastAttack")));
    auto* StopDefense=G.Call(Defense,TEXT("StopNNDefense"),8350,0);G.Link(Opp,TEXT("CombatDemoOpponent"),StopDefense,TEXT("Agent"));G.Exec(Last,StopDefense);
    auto* Head=G.Call(Agent,TEXT("GetAuthoredBodyWorldTarget"),8000,1400);G.Default(Head,TEXT("BoneName"),TEXT("head"));G.Link(Opp,TEXT("CombatDemoOpponent"),Head,TEXT("self"));
    auto* Break=G.Call(Math,TEXT("BreakTransform"),8400,1400);G.Link(Head,TEXT("InterpolatedWorldTransform"),Break,TEXT("InTransform"));
    auto* TargetValid=G.Node<UK2Node_IfThenElse>(8700,0);G.Exec(StopDefense,TargetValid);G.Link(Head,TEXT("ReturnValue"),TargetValid,TEXT("Condition"));
    auto* Trigger=G.Call(Agent,TEXT("TriggerNNAttack"),9050,0);G.Exec(TargetValid,Trigger);G.Link(Last,TEXT("Output_Get"),Trigger,TEXT("Attack"));G.Link(Break,TEXT("Location"),Trigger,TEXT("TargetWorldLocation"));G.Default(Trigger,TEXT("bHalfAttack"),TEXT("false"));G.Link(Opp,TEXT("CombatDemoOpponent"),Trigger,TEXT("Victim"));
    Trigger->NodeComment=TEXT("Capture the head at launch. Do not retarget each tick: the reference attacker has a fixed world target.");Trigger->bCommentBubbleVisible=true;
    auto* Started=G.Node<UK2Node_IfThenElse>(9450,0);G.Exec(Trigger,Started);G.Link(Trigger,TEXT("ReturnValue"),Started,TEXT("Condition"));
    auto* UseDodge=G.Get(TEXT("CombatDemoUseDodge"),9450,400);auto* DefenseGate=G.Node<UK2Node_IfThenElse>(9800,0);G.Exec(Started,DefenseGate);G.Link(UseDodge,TEXT("CombatDemoUseDodge"),DefenseGate,TEXT("Condition"));
    auto* Dodge=G.Call(Defense,TEXT("StartNNDodge"),10150,0);auto* Parry=G.Call(Defense,TEXT("StartNNParry"),10150,600);
    G.Exec(DefenseGate,Dodge);G.Link(DefenseGate,TEXT("else"),Parry,TEXT("execute"));
    auto* Self=G.Node<UK2Node_Self>(9800,1000);
    for (auto* N:{Dodge,Parry}) { G.Link(Opp,TEXT("CombatDemoOpponent"),N,TEXT("Agent"));G.Link(Self,TEXT("self"),N,TEXT("Attacker")); }
    for (auto* N:{Dodge,Parry})
    {
        auto* Error=G.Set(TEXT("CombatDemoError"),10600,N->NodePosY);G.Exec(N,Error);G.Link(N,TEXT("OutError"),Error,TEXT("CombatDemoError"));
        auto* Fail=G.Node<UK2Node_IfThenElse>(11000,N->NodePosY);G.Exec(Error,Fail);G.Link(N,TEXT("ReturnValue"),Fail,TEXT("Condition"));
        auto* Print=G.Call(System,TEXT("PrintString"),11350,N->NodePosY);G.Link(Fail,TEXT("else"),Print,TEXT("execute"));G.Link(Error,TEXT("Output_Get"),Print,TEXT("InString"));
    }
    OK &= G.OK;
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);OK &= BP->Status!=BS_Error;
    UK2Node_CallFunction* Demo=nullptr;
    TArray<UEdGraphPin*> Successors=InputCall->FindPinChecked(TEXT("then"))->LinkedTo;
    if (OK)
    {
        FGraph EG{EventGraph};Demo=EG.Call(BP->GeneratedClass,*Name.ToString(),InputCall->NodePosX,InputCall->NodePosY-300);
        Demo->NodeComment=TEXT("COMBAT DEMO: disable Combat Demo Enabled on the pair, or reconnect Event Tick directly to the original input debugging node below.");Demo->bCommentBubbleVisible=true;
        TickThen->BreakLinkTo(OldInput);EG.Link(TickThen,EG.Pin(Demo,TEXT("execute")));
        for (auto* P:Successors) EG.Link(EG.Pin(Demo,TEXT("then")),P);
        OK &= EG.OK;FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
        FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);OK &= BP->Status!=BS_Error;
    }
    if (!OK)
    {
        if (Demo) Demo->DestroyNode();TickThen->MakeLinkTo(OldInput);
        for (auto* P:Successors) InputCall->FindPinChecked(TEXT("then"))->MakeLinkTo(P);
        FBlueprintEditorUtils::RemoveGraph(BP,Graph);
        for (auto V:Added) FBlueprintEditorUtils::RemoveMemberVariable(BP,V);
        FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
        UE_LOG(LogTemp,Error,TEXT("CombatDemo: reverted failed graph installation. Backup %s"),*Backup);return;
    }
    FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;
    UE_LOG(LogTemp,Display,TEXT("CombatDemo: installed function and Tick call; saved=%d; backup=%s"),UPackage::SavePackage(BP->GetOutermost(),BP,*Filename,Save),*Backup);
    RetireDemoCubeBeforeDisablingCollision(BP);
    GuardDemoInitialization(BP);
}
FAutoConsoleCommand Command(TEXT("Prophecy.Debug.InstallCombatDemo"),TEXT("Back up and install the optional one-function kinematic combat demo in the manual agent Blueprint."),FConsoleCommandDelegate::CreateStatic(&Install));

void WireVictim()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    for (UEdGraph* Graph:BP->FunctionGraphs) if (Graph->GetFName()==TEXT("KinematicAttackDefenseDemo"))
    {
        UK2Node_CallFunction* Trigger=nullptr;UK2Node_VariableGet* Opp=nullptr;
        for (UEdGraphNode* N:Graph->Nodes)
        {
            if (auto* C=Cast<UK2Node_CallFunction>(N);C && C->FunctionReference.GetMemberName()==TEXT("TriggerNNAttack")) Trigger=C;
            if (auto* V=Cast<UK2Node_VariableGet>(N);V && V->VariableReference.GetMemberName()==TEXT("CombatDemoOpponent")) Opp=V;
        }
        if (!Trigger || !Opp) return;
        if (auto* Pin=Trigger->FindPin(TEXT("Victim"));Pin && !Pin->LinkedTo.IsEmpty()) return;
        const FString Filename=FPackageName::LongPackageNameToFilename(BP->GetOutermost()->GetName(),FPackageName::GetAssetPackageExtension());
        const FString Backup=FPaths::ProjectSavedDir()/TEXT("Diagnostics/CombatDemo/Backup")/FDateTime::Now().ToString(TEXT("%Y%m%d-%H%M%S"));
        IFileManager::Get().MakeDirectory(*Backup,true);
        FSavePackageArgs Snapshot;Snapshot.TopLevelFlags=RF_Public|RF_Standalone;Snapshot.SaveFlags=SAVE_KeepDirty;
        if (!UPackage::SavePackage(BP->GetOutermost(),BP,*(Backup/TEXT("BeforeVictimPin.uasset")),Snapshot)) return;
        const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","CombatVictim","Connect combat demo victim"));
        BP->Modify();Graph->Modify();Trigger->Modify();Trigger->ReconstructNode();
        FGraph G{Graph};G.Link(Opp,TEXT("CombatDemoOpponent"),Trigger,TEXT("Victim"));
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
        if (!G.OK || BP->Status==BS_Error) return;
        FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;
        UE_LOG(LogTemp,Display,TEXT("CombatDemo: victim pin connected, saved=%d; backup=%s"),UPackage::SavePackage(BP->GetOutermost(),BP,*Filename,Save),*Backup);
        return;
    }
}
FAutoConsoleCommand VictimCommand(TEXT("Prophecy.Debug.WireCombatDemoVictim"),TEXT("Connect only the existing combat demo attack's Victim pin to CombatDemoOpponent."),FConsoleCommandDelegate::CreateStatic(&WireVictim));

void RemoveDebugSeedOverride()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    for (UEdGraph* Graph:BP->FunctionGraphs) if (Graph->GetFName()==TEXT("begin_f"))
    {
        auto* Node=FindObjectFast<UK2Node_CallFunction>(Graph,TEXT("K2Node_CallFunction_6"));
        if (!Node) return;
        const auto* Seed=Node->FindPin(TEXT("NewSeed"));
        const auto* Then=Node->FindPin(TEXT("then"));
        const auto* Stream=Node->FindPin(TEXT("Stream"));
        const auto* Variable=Stream && Stream->LinkedTo.Num()==1 ? Cast<UK2Node_VariableGet>(Stream->LinkedTo[0]->GetOwningNode()) : nullptr;
        if (Node->FunctionReference.GetMemberName()!=TEXT("SetRandomStreamSeed") || !Seed || !Seed->LinkedTo.IsEmpty()
            || Seed->DefaultValue!=TEXT("1") || !Then || !Then->LinkedTo.IsEmpty() || !Variable
            || Variable->VariableReference.GetMemberName()!=TEXT("Random Stream debug"))
        { UE_LOG(LogTemp,Warning,TEXT("Seed override repair: graph changed; left untouched."));return; }
        const FString Backup=FPaths::ProjectSavedDir()/TEXT("Diagnostics/RandomStreamSeed")/FDateTime::Now().ToString(TEXT("%Y%m%d-%H%M%S"));
        IFileManager::Get().MakeDirectory(*Backup,true);
        FSavePackageArgs Snapshot;Snapshot.TopLevelFlags=RF_Public|RF_Standalone;Snapshot.SaveFlags=SAVE_KeepDirty;
        if (!UPackage::SavePackage(BP->GetOutermost(),BP,*(Backup/TEXT("BeforeSeedOverrideRemoval.uasset")),Snapshot)) return;
        const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","RemoveDebugSeedOverride","Use authored random stream seed"));
        BP->Modify();Graph->Modify();Node->Modify();
        FBlueprintEditorUtils::RemoveNode(BP,Node,true);
        FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
        if (BP->Status==BS_Error) { UE_LOG(LogTemp,Error,TEXT("Seed repair compile failed; backup: %s"),*Backup);return; }
        const FString Filename=FPackageName::LongPackageNameToFilename(BP->GetOutermost()->GetName(),FPackageName::GetAssetPackageExtension());
        FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;
        UE_LOG(LogTemp,Display,TEXT("Seed override repair: removed only terminal forced-seed-1 node; saved=%d; backup=%s"),
            UPackage::SavePackage(BP->GetOutermost(),BP,*Filename,Save),*Backup);
        return;
    }
}
FAutoConsoleCommand SeedCommand(TEXT("Prophecy.Debug.RemoveDebugSeedOverride"),TEXT("Remove the audited terminal seed=1 test override; preserve all other Blueprint logic."),FConsoleCommandDelegate::CreateStatic(&RemoveDebugSeedOverride));

void AddReverseRoles()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP || !BP->GeneratedClass) return;
    if (FindFProperty<FBoolProperty>(BP->GeneratedClass,TEXT("CombatDemoReverseRoles")))
    { UE_LOG(LogTemp,Display,TEXT("CombatDemo reverse roles already installed."));return; }
    UEdGraph* Graph=nullptr;
    for (UEdGraph* Candidate:BP->FunctionGraphs) if (Candidate->GetFName()==TEXT("KinematicAttackDefenseDemo")) Graph=Candidate;
    if (!Graph) return;
    TArray<UK2Node_CallFunction*> Calls;Graph->GetNodesOfClass(Calls);
    UK2Node_CallFunction *Trigger=nullptr,*Parry=nullptr,*Dodge=nullptr,*Head=nullptr,*Stop=nullptr;
    for (auto* C:Calls)
    {
        const FName F=C->FunctionReference.GetMemberName();
        if (F==TEXT("TriggerNNAttack")) Trigger=C;
        if (F==TEXT("StartNNParry")) Parry=C;
        if (F==TEXT("StartNNDodge")) Dodge=C;
        if (F==TEXT("GetAuthoredBodyWorldTarget")) Head=C;
        if (F==TEXT("StopNNDefense")) Stop=C;
    }
    if (!Trigger || !Parry || !Dodge || !Head || !Stop) return;
    const FString Backup=FPaths::ProjectSavedDir()/TEXT("Diagnostics/CombatReverseRoles")/FDateTime::Now().ToString(TEXT("%Y%m%d-%H%M%S"));
    IFileManager::Get().MakeDirectory(*Backup,true);
    FSavePackageArgs Snapshot;Snapshot.TopLevelFlags=RF_Public|RF_Standalone;Snapshot.SaveFlags=SAVE_KeepDirty;
    if (!UPackage::SavePackage(BP->GetOutermost(),BP,*(Backup/TEXT("Before.uasset")),Snapshot)) return;
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","CombatReverseRoles","Add combat demo reverse roles"));
    BP->Modify();Graph->Modify();
    FEdGraphPinType Bool;Bool.PinCategory=UEdGraphSchema_K2::PC_Boolean;
    if (!FBlueprintEditorUtils::AddMemberVariable(BP,TEXT("CombatDemoReverseRoles"),Bool,TEXT("false"))) return;
    FBlueprintEditorUtils::SetBlueprintOnlyEditableFlag(BP,TEXT("CombatDemoReverseRoles"),false);
    FBlueprintEditorUtils::SetBlueprintVariableCategory(BP,TEXT("CombatDemoReverseRoles"),nullptr,FText::FromString(TEXT("Debug|Combat Demo")),true);
    FGraph G{Graph};auto* Reverse=G.Get(TEXT("CombatDemoReverseRoles"),7900,-1100);
    auto* Opp=G.Get(TEXT("CombatDemoOpponent"),7900,-800);auto* Self=G.Node<UK2Node_Self>(7900,-950);
    auto* Agent=FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecyAgent"));
    auto Select=[&](bool bAttacker,int32 Y)
    {
        auto* N=G.Node<UK2Node_Select>(8250,Y);
        N->GetIndexPin()->PinType=Bool;N->ChangePinType(N->GetIndexPin());
        auto* Return=N->GetReturnValuePin();Return->PinType.PinCategory=UEdGraphSchema_K2::PC_Object;Return->PinType.PinSubCategoryObject=Agent;
        N->ChangePinType(Return);
        G.Link(G.Pin(Reverse,TEXT("CombatDemoReverseRoles")),N->GetIndexPin());
        TArray<UEdGraphPin*> Options;N->GetOptionPins(Options);
        if (Options.Num()!=2) { G.OK=false;return N; }
        G.Link(bAttacker?G.Pin(Self,TEXT("self")):G.Pin(Opp,TEXT("CombatDemoOpponent")),Options[0]);
        G.Link(bAttacker?G.Pin(Opp,TEXT("CombatDemoOpponent")):G.Pin(Self,TEXT("self")),Options[1]);
        N->NodeComment=bAttacker?TEXT("ATTACKER: Self normally, opponent when Reverse Roles is true."):TEXT("DEFENDER: opponent normally, Self when Reverse Roles is true.");
        N->bCommentBubbleVisible=true;return N;
    };
    auto* AttackRole=Select(true,-1100);auto* DefendRole=Select(false,-650);
    auto Rewire=[&](UK2Node_CallFunction* C,const TCHAR* Name,UK2Node_Select* Role)
    {
        C->Modify();auto* P=G.Pin(C,Name);if (!P) return;P->BreakAllPinLinks();G.Link(Role->GetReturnValuePin(),P);
    };
    Rewire(Trigger,TEXT("self"),AttackRole);
    // Preserve the user's choice to leave Victim unconnected for an air attack.
    if (auto* V=Trigger->FindPin(TEXT("Victim"));V && !V->LinkedTo.IsEmpty()) Rewire(Trigger,TEXT("Victim"),DefendRole);
    Rewire(Head,TEXT("self"),DefendRole);Rewire(Stop,TEXT("Agent"),DefendRole);
    for (auto* C:{Parry,Dodge}) { Rewire(C,TEXT("Agent"),DefendRole);Rewire(C,TEXT("Attacker"),AttackRole); }
    // Keep existing per-role clamp tuning when swapping. Unconnected/Self pins
    // retain their prior attacker role; opponent pins follow the selected defender.
    for (auto* C:Calls)
    {
        const FString F=C->FunctionReference.GetMemberName().ToString();
        if ((!F.StartsWith(TEXT("SetParry")) && !F.StartsWith(TEXT("SetDodge"))) || !F.EndsWith(TEXT("Clamp"))) continue;
        auto* P=C->FindPin(TEXT("Agent"));if (!P) continue;
        if (P->LinkedTo.IsEmpty()) Rewire(C,TEXT("Agent"),AttackRole);
        else if (const auto* V=Cast<UK2Node_VariableGet>(P->LinkedTo[0]->GetOwningNode());V && V->VariableReference.GetMemberName()==TEXT("CombatDemoOpponent"))
            Rewire(C,TEXT("Agent"),DefendRole);
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    if (!G.OK || BP->Status==BS_Error)
    { UE_LOG(LogTemp,Error,TEXT("Reverse roles graph failed validation; NOT saved. Undo transaction or restore %s"),*Backup);return; }
    FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;
    const FString Filename=FPackageName::LongPackageNameToFilename(BP->GetOutermost()->GetName(),FPackageName::GetAssetPackageExtension());
    UE_LOG(LogTemp,Display,TEXT("CombatDemo reverse roles installed, default false; saved=%d; backup=%s"),UPackage::SavePackage(BP->GetOutermost(),BP,*Filename,Save),*Backup);
}
FAutoConsoleCommand ReverseRolesCommand(TEXT("Prophecy.Debug.AddCombatReverseRoles"),TEXT("Back up and add a default-off role reversal to the current combat demo without rebuilding it."),FConsoleCommandDelegate::CreateStatic(&AddReverseRoles));

void RefreshParryWithoutBlocker()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    const FString Backup=FPaths::ProjectSavedDir()/TEXT("Diagnostics/RemoveParryBlocker")/FDateTime::Now().ToString(TEXT("%Y%m%d-%H%M%S"));
    IFileManager::Get().MakeDirectory(*Backup,true);
    FSavePackageArgs Snapshot;Snapshot.TopLevelFlags=RF_Public|RF_Standalone;Snapshot.SaveFlags=SAVE_KeepDirty;
    if (!UPackage::SavePackage(BP->GetOutermost(),BP,*(Backup/TEXT("Before.uasset")),Snapshot)) return;
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","RemoveParryBlocker","Remove obsolete Parry blocker pin"));
    BP->Modify();int32 Count=0;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    for (auto* Graph:Graphs)
    {
        TArray<UK2Node_CallFunction*> Calls;Graph->GetNodesOfClass(Calls);
        for (auto* Node:Calls) if (Node->FunctionReference.GetMemberName()==TEXT("StartNNParry"))
        {
            Graph->Modify();Node->Modify();
            if (auto* Pin=Node->FindPin(TEXT("Blocker"))) { Pin->BreakAllPinLinks();Node->RemovePin(Pin); }
            Node->ReconstructNode();++Count;
        }
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    // Keep existing unsaved user edits unsaved; the backup includes the live graph.
    UE_LOG(LogTemp,Display,TEXT("Parry blocker removal: refreshed %d calls, compile_ok=%d; left Blueprint unsaved; backup=%s"),Count,BP->Status!=BS_Error,*Backup);
}
FAutoConsoleCommand RemoveBlockerCommand(TEXT("Prophecy.Debug.RefreshParryWithoutBlocker"),TEXT("Remove obsolete Blocker pins from the current Blueprint; preserve all other wiring and leave unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshParryWithoutBlocker));
}
