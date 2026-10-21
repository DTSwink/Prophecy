#include "CoreMinimal.h"
#include "HAL/IConsoleManager.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "K2Node_DynamicCast.h"
#include "Kismet/KismetMathLibrary.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "ScopedTransaction.h"

namespace ProphecySwordBloodSetup
{
bool WireDepthRead(UEdGraph* G)
{
    for(UEdGraphNode* N:G->Nodes)if(N->GetFName()==TEXT("BladeBloodSeedVariation"))return true;
    UK2Node_CallFunction *Read=nullptr,*Write=nullptr;
    for(UEdGraphNode* N:G->Nodes) if(auto* F=Cast<UK2Node_CallFunction>(N))
    {
        if(F->FunctionReference.GetMemberName()==TEXT("K2_GetScalarParameterValue")) Read=F;
        if(F->FunctionReference.GetMemberName()==TEXT("SetScalarParameterValue") && F->FindPin(TEXT("ParameterName"))->DefaultValue==TEXT("BladeBloodDepth")) Write=F;
    }
    if(!Read || !Write)return false;
    auto* Before=Read->FindPin(TEXT("execute"));auto* After=Read->FindPin(TEXT("then"));auto* Target=Write->FindPin(TEXT("execute"));
    if(!Before || !After || !Target)return false;
    if(Target->LinkedTo.Contains(After))return true;
    const auto Sources=Target->LinkedTo;Target->BreakAllPinLinks();
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();bool OK=true;
    for(auto* Source:Sources)OK=Schema->TryCreateConnection(Source,Before)&&OK;
    return Schema->TryCreateConnection(After,Target)&&OK;
}
bool MakeAdditive(UBlueprint* BP)
{
    UEdGraph* G=nullptr;
    for(UEdGraph* Graph:BP->FunctionGraphs) if(Graph->GetFName()==TEXT("Stain Blade")) G=Graph;
    if(!G) return false;
    for(UEdGraphNode* N:G->Nodes) if(N->GetFName()==TEXT("BladeBloodAccumulatedDepth")) return WireDepthRead(G);
    auto* Material=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Prophecy/BloodTexturePainting/Generated/_mygame_sword_geometry_M_Sword_BloodPaint"));
    UK2Node_CallFunction *SetDepth=nullptr,*Valid=nullptr,*Create=nullptr;
    UK2Node_FunctionEntry* Entry=nullptr;UK2Node_IfThenElse* Branch=nullptr;
    UK2Node_VariableGet *Sword=nullptr,*Cache=nullptr;
    for(UEdGraphNode* N:G->Nodes)
    {
        if(auto* F=Cast<UK2Node_CallFunction>(N))
        {
            const auto Name=F->FunctionReference.GetMemberName();
            if(Name==TEXT("IsValid")) Valid=F;
            if(Name==TEXT("CreateDynamicMaterialInstance")) Create=F;
            if(Name==TEXT("SetScalarParameterValue") && F->FindPin(TEXT("ParameterName"))->DefaultValue==TEXT("BladeBloodDepth")) SetDepth=F;
        }
        if(auto* E=Cast<UK2Node_FunctionEntry>(N)) Entry=E;
        if(auto* B=Cast<UK2Node_IfThenElse>(N)) Branch=B;
        if(auto* V=Cast<UK2Node_VariableGet>(N))
        {
            if(V->VariableReference.GetMemberName()==TEXT("sword")) Sword=V;
            if(V->VariableReference.GetMemberName()==TEXT("BladeBloodMID")) Cache=V;
        }
    }
    if(!Material || !SetDepth || !Valid || !Create || !Entry || !Branch || !Sword || !Cache) return false;
    BP->Modify();G->Modify();
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();bool OK=true;
    auto Link=[&](UEdGraphPin* A,UEdGraphPin* B){OK=(A&&B&&Schema->TryCreateConnection(A,B))&&OK;};
    auto Call=[&](UClass* C,const TCHAR* Name,int32 X,int32 Y)
    {
        FGraphNodeCreator<UK2Node_CallFunction> NC(*G);auto* N=NC.CreateNode();
        N->SetFromFunction(C->FindFunctionByName(Name));N->NodePosX=X;N->NodePosY=Y;NC.Finalize();return N;
    };
    auto* Current=Call(UPrimitiveComponent::StaticClass(),TEXT("GetMaterial"),0,1000);
    Link(Sword->FindPin(TEXT("sword")),Current->FindPin(TEXT("self")));
    FGraphNodeCreator<UK2Node_DynamicCast> DC(*G);auto* CastMID=DC.CreateNode();
    CastMID->TargetType=UMaterialInstanceDynamic::StaticClass();CastMID->NodePosX=250;CastMID->NodePosY=1000;DC.Finalize();CastMID->SetPurity(true);
    Link(Current->FindPin(TEXT("ReturnValue")),CastMID->GetCastSourcePin());
    Valid->FindPin(TEXT("Object"))->BreakAllPinLinks();Link(CastMID->GetCastResultPin(),Valid->FindPin(TEXT("Object")));
    FGraphNodeCreator<UK2Node_VariableSet> SC(*G);auto* CurrentCache=SC.CreateNode();
    CurrentCache->VariableReference.SetSelfMember(TEXT("BladeBloodMID"));CurrentCache->NodePosX=800;CurrentCache->NodePosY=-250;SC.Finalize();
    Branch->FindPin(TEXT("then"))->BreakAllPinLinks();
    Link(Branch->FindPin(TEXT("then")),CurrentCache->FindPin(TEXT("execute")));
    Link(CastMID->GetCastResultPin(),CurrentCache->FindPin(TEXT("BladeBloodMID")));
    Link(CurrentCache->FindPin(TEXT("then")),SetDepth->FindPin(TEXT("execute")));
    Schema->TrySetDefaultObject(*Create->FindPin(TEXT("SourceMaterial")),Material);
    auto* Previous=Call(UMaterialInstanceDynamic::StaticClass(),TEXT("K2_GetScalarParameterValue"),1100,800);
    Schema->TrySetDefaultValue(*Previous->FindPin(TEXT("ParameterName")),TEXT("BladeBloodDepth"));
    Link(Cache->FindPin(TEXT("BladeBloodMID")),Previous->FindPin(TEXT("self")));
    auto* Clamp=Call(UKismetMathLibrary::StaticClass(),TEXT("FClamp"),1100,1100);
    Schema->TrySetDefaultValue(*Clamp->FindPin(TEXT("Min")),TEXT("0"));Schema->TrySetDefaultValue(*Clamp->FindPin(TEXT("Max")),TEXT("1"));
    Link(Entry->FindPin(TEXT("Depth")),Clamp->FindPin(TEXT("Value")));
    auto* Max=Call(UKismetMathLibrary::StaticClass(),TEXT("FMax"),1400,800);
    Max->Rename(TEXT("BladeBloodAccumulatedDepth"),G);
    Link(Previous->FindPin(TEXT("ReturnValue")),Max->FindPin(TEXT("A")));Link(Clamp->FindPin(TEXT("ReturnValue")),Max->FindPin(TEXT("B")));
    SetDepth->FindPin(TEXT("Value"))->BreakAllPinLinks();Link(Max->FindPin(TEXT("ReturnValue")),SetDepth->FindPin(TEXT("Value")));
    Entry->MetaData.ToolTip=FText::FromString(TEXT("Add blood from tip toward hilt; preserves painted stains and deepest prior coverage. Depth 0 adds nothing, 0.5 reaches halfway, 1 reaches hilt."));
    return WireDepthRead(G)&&OK;
}
void Upgrade()
{
    if(GEditor && GEditor->PlayWorld){UE_LOG(LogTemp,Warning,TEXT("SwordBlood: preserve active Play"));return;}
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/sword/A_Sword"));if(!BP)return;
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","AdditiveSwordBlood","Make blade blood additive"));
    const bool OK=MakeAdditive(BP);
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    UE_LOG(LogTemp,Display,TEXT("SwordBlood additive: wiring=%d BlueprintStatus=%d; left unsaved"),OK,int32(BP->Status));
}
bool AddSeed(UBlueprint* BP)
{
    UEdGraph* G=nullptr;for(UEdGraph* Graph:BP->FunctionGraphs)if(Graph->GetFName()==TEXT("Stain Blade"))G=Graph;
    if(!G)return false;
    UK2Node_FunctionEntry* Entry=nullptr;UK2Node_VariableGet* Cache=nullptr;
    UK2Node_CallFunction *Read=nullptr,*Write=nullptr,*SetLength=nullptr,*DivideLength=nullptr;
    for(UEdGraphNode* N:G->Nodes)
    {
        if(N->GetFName()==TEXT("BladeBloodSeedVariation"))return true;
        if(auto* E=Cast<UK2Node_FunctionEntry>(N))Entry=E;
        if(auto* V=Cast<UK2Node_VariableGet>(N))if(V->VariableReference.GetMemberName()==TEXT("BladeBloodMID"))Cache=V;
        if(auto* F=Cast<UK2Node_CallFunction>(N))
        {
            const auto Name=F->FunctionReference.GetMemberName();
            if(Name==TEXT("K2_GetScalarParameterValue"))Read=F;
            if(Name==TEXT("SetScalarParameterValue"))
            {
                if(F->FindPin(TEXT("ParameterName"))->DefaultValue==TEXT("BladeBloodDepth"))Write=F;
                if(F->FindPin(TEXT("ParameterName"))->DefaultValue==TEXT("BladeLengthLocal"))SetLength=F;
            }
            if(Name==TEXT("Divide_DoubleDouble"))DivideLength=F;
        }
    }
    if(!Entry||!Cache||!Read||!Write||!SetLength||!DivideLength||Entry->FindPin(TEXT("Seed")))return false;
    auto* ScalePin=DivideLength->FindPin(TEXT("B"));
    if(ScalePin->LinkedTo.Num()!=1)return false;
    auto* Scale=ScalePin->LinkedTo[0]->GetOwningNode();
    if(!Scale->FindPin(TEXT("Y"))||!Scale->FindPin(TEXT("Z")))return false;
    BP->Modify();G->Modify();Entry->Modify();
    FEdGraphPinType Int;Int.PinCategory=UEdGraphSchema_K2::PC_Int;
    auto* Seed=Entry->CreateUserDefinedPin(TEXT("Seed"),Int,EGPD_Output);Seed->DefaultValue=TEXT("0");
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();bool OK=true;
    auto Link=[&](UEdGraphPin* A,UEdGraphPin* B){OK=(A&&B&&Schema->TryCreateConnection(A,B))&&OK;};
    auto Call=[&](UClass* C,const TCHAR* Name,int32 X,int32 Y)
    {
        FGraphNodeCreator<UK2Node_CallFunction> NC(*G);auto* N=NC.CreateNode();
        N->SetFromFunction(C->FindFunctionByName(Name));N->NodePosX=X;N->NodePosY=Y;NC.Finalize();return N;
    };
    auto* Stream=Call(UKismetMathLibrary::StaticClass(),TEXT("MakeRandomStream"),250,1550);
    Link(Seed,Stream->FindPin(TEXT("InitialSeed")));
    auto* Random=Call(UKismetMathLibrary::StaticClass(),TEXT("RandomFloatFromStream"),500,1550);
    Link(Stream->FindPin(TEXT("ReturnValue")),Random->FindPin(TEXT("Stream")));
    auto* SetSeed=Call(UMaterialInstanceDynamic::StaticClass(),TEXT("SetScalarParameterValue"),1400,1400);
    SetSeed->Rename(TEXT("BladeBloodSeedVariation"),G);
    Schema->TrySetDefaultValue(*SetSeed->FindPin(TEXT("ParameterName")),TEXT("BladeBloodVariation"));
    Link(Cache->FindPin(TEXT("BladeBloodMID")),SetSeed->FindPin(TEXT("self")));Link(Random->FindPin(TEXT("ReturnValue")),SetSeed->FindPin(TEXT("Value")));
    auto* Empty=Call(UKismetMathLibrary::StaticClass(),TEXT("LessEqual_DoubleDouble"),850,1550);
    Link(Read->FindPin(TEXT("ReturnValue")),Empty->FindPin(TEXT("A")));Schema->TrySetDefaultValue(*Empty->FindPin(TEXT("B")),TEXT("0"));
    FGraphNodeCreator<UK2Node_IfThenElse> BC(*G);auto* Branch=BC.CreateNode();Branch->NodePosX=1100;Branch->NodePosY=1400;BC.Finalize();
    Link(Empty->FindPin(TEXT("ReturnValue")),Branch->FindPin(TEXT("Condition")));
    Read->FindPin(TEXT("then"))->BreakAllPinLinks();
    Link(Read->FindPin(TEXT("then")),Branch->FindPin(TEXT("execute")));
    Link(Branch->FindPin(TEXT("then")),SetSeed->FindPin(TEXT("execute")));
    Link(SetSeed->FindPin(TEXT("then")),Write->FindPin(TEXT("execute")));Link(Branch->FindPin(TEXT("else")),Write->FindPin(TEXT("execute")));
    auto* Ratio=Call(UKismetMathLibrary::StaticClass(),TEXT("Divide_DoubleDouble"),3500,1500);
    Link(Scale->FindPin(TEXT("Y")),Ratio->FindPin(TEXT("A")));Link(Scale->FindPin(TEXT("Z")),Ratio->FindPin(TEXT("B")));
    auto* SetRatio=Call(UMaterialInstanceDynamic::StaticClass(),TEXT("SetScalarParameterValue"),3900,1500);
    Schema->TrySetDefaultValue(*SetRatio->FindPin(TEXT("ParameterName")),TEXT("BladeLateralScale"));
    Link(Cache->FindPin(TEXT("BladeBloodMID")),SetRatio->FindPin(TEXT("self")));Link(Ratio->FindPin(TEXT("ReturnValue")),SetRatio->FindPin(TEXT("Value")));
    const auto Downstream=SetLength->FindPin(TEXT("then"))->LinkedTo;SetLength->FindPin(TEXT("then"))->BreakAllPinLinks();
    Link(SetLength->FindPin(TEXT("then")),SetRatio->FindPin(TEXT("execute")));for(auto* P:Downstream)Link(SetRatio->FindPin(TEXT("then")),P);
    Entry->MetaData.ToolTip=FText::FromString(TEXT("Add blood from tip toward hilt. Seed chooses a repeatable -20 to +20 degree wavy edge, locked on the first positive stain. Keep the same seed per sword/agent. Depth never shrinks; 0 adds nothing, 1 covers the blade."));
    return OK;
}
void SeedUpgrade()
{
    if(GEditor&&GEditor->PlayWorld){UE_LOG(LogTemp,Warning,TEXT("SwordBlood: preserve active Play"));return;}
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/sword/A_Sword"));if(!BP)return;
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","SeedSwordBlood","Seed the blade stain edge"));
    const bool OK=AddSeed(BP);
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    // Refresh existing callers so their Depth wiring survives and Seed is exposed.
    TArray<UK2Node_CallFunction*> Calls;FBlueprintEditorUtils::GetAllNodesOfClass(BP,Calls);
    for(auto* Call:Calls)if(Call->FunctionReference.GetMemberName()==TEXT("Stain Blade"))Call->ReconstructNode();
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    UE_LOG(LogTemp,Display,TEXT("SwordBlood seeded: wiring=%d BlueprintStatus=%d; left unsaved"),OK,int32(BP->Status));
}
void Install()
{
    if (GEditor && GEditor->PlayWorld) { UE_LOG(LogTemp, Warning, TEXT("SwordBlood: preserve active Play")); return; }
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/sword/A_Sword"));
    auto* Material=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/_mygame/sword/geometry/M_Sword_BloodDepth"));
    if (!BP || !BP->GeneratedClass || !Material) return;
    const FName FunctionName(TEXT("Stain Blade")), CacheName(TEXT("BladeBloodMID"));
    if (BP->GeneratedClass->FindFunctionByName(FunctionName) || FindFProperty<FProperty>(BP->GeneratedClass,CacheName))
    { UE_LOG(LogTemp,Warning,TEXT("SwordBlood: already present; no edits")); return; }
    auto* Limits=BP->GeneratedClass->FindFunctionByName(TEXT("get limits location"));
    if (!Limits || !FindFProperty<FObjectPropertyBase>(BP->GeneratedClass,TEXT("sword")) ||
        !FindFProperty<FProperty>(BP->GeneratedClass,TEXT("blade length"))) return;
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","SwordBlood","Add Stain Blade function"));
    BP->Modify();
    FEdGraphPinType ObjectType; ObjectType.PinCategory=UEdGraphSchema_K2::PC_Object;
    ObjectType.PinSubCategoryObject=UMaterialInstanceDynamic::StaticClass();
    if (!FBlueprintEditorUtils::AddMemberVariable(BP,CacheName,ObjectType)) return;
    FBlueprintEditorUtils::SetBlueprintVariableCategory(BP,CacheName,nullptr,FText::FromString(TEXT("Blood")),true);
    auto* G=FBlueprintEditorUtils::CreateNewGraph(BP,FunctionName,UEdGraph::StaticClass(),UEdGraphSchema_K2::StaticClass());
    FBlueprintEditorUtils::AddFunctionGraph<UClass>(BP,G,true,nullptr);
    TArray<UK2Node_FunctionEntry*> Entries; G->GetNodesOfClass(Entries);
    if (Entries.Num()!=1) return;
    auto* Entry=Entries[0];
    FEdGraphPinType FloatType; FloatType.PinCategory=UEdGraphSchema_K2::PC_Real; FloatType.PinSubCategory=UEdGraphSchema_K2::PC_Double;
    auto* Depth=Entry->CreateUserDefinedPin(TEXT("Depth"),FloatType,EGPD_Output);
    Depth->DefaultValue=TEXT("0.5");
    Entry->MetaData.Category=FText::FromString(TEXT("Blood"));
    Entry->MetaData.ToolTip=FText::FromString(TEXT("Set stained fraction from tip towards hilt. 0 cleans, 0.5 covers half, 1 covers the blade. Does not alter collision or physics."));
    int32 X=250;
    bool OK=true;
    auto Call=[&](UClass* Class,const TCHAR* Name)->UK2Node_CallFunction*
    {
        auto* Fn=Class->FindFunctionByName(Name); if (!Fn) { OK=false; return nullptr; }
        FGraphNodeCreator<UK2Node_CallFunction> C(*G); auto* N=C.CreateNode();N->SetFromFunction(Fn);
        N->NodePosX=X;X+=260;C.Finalize();return N;
    };
    auto Get=[&](FName Name,int32 Y)->UK2Node_VariableGet*
    {
        FGraphNodeCreator<UK2Node_VariableGet> C(*G);auto* N=C.CreateNode();N->VariableReference.SetSelfMember(Name);
        N->NodePosX=0;N->NodePosY=Y;C.Finalize();return N;
    };
    auto Pin=[](UEdGraphNode* N,const TCHAR* Name)->UEdGraphPin* {return N?N->FindPin(Name):nullptr;};
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();
    auto Link=[&](UEdGraphPin* A,UEdGraphPin* B){OK=(A && B && Schema->TryCreateConnection(A,B)) && OK;};
    auto Default=[&](UEdGraphNode* N,const TCHAR* P,const TCHAR* V){auto* Pn=Pin(N,P);if(Pn)Schema->TrySetDefaultValue(*Pn,V);else OK=false;};
    auto* Sword=Get(TEXT("sword"),300);auto* Cache=Get(CacheName,500);
    auto* Valid=Call(UKismetSystemLibrary::StaticClass(),TEXT("IsValid"));
    Link(Pin(Cache,TEXT("BladeBloodMID")),Pin(Valid,TEXT("Object")));
    FGraphNodeCreator<UK2Node_IfThenElse> BC(*G);auto* Branch=BC.CreateNode();Branch->NodePosX=550;BC.Finalize();
    Link(Pin(Entry,TEXT("then")),Pin(Branch,TEXT("execute")));Link(Pin(Valid,TEXT("ReturnValue")),Pin(Branch,TEXT("Condition")));
    auto* Create=Call(UPrimitiveComponent::StaticClass(),TEXT("CreateDynamicMaterialInstance"));
    Link(Pin(Sword,TEXT("sword")),Pin(Create,TEXT("self")));Default(Create,TEXT("ElementIndex"),TEXT("0"));
    if (auto* P=Pin(Create,TEXT("SourceMaterial"))) Schema->TrySetDefaultObject(*P,Material);else OK=false;
    FGraphNodeCreator<UK2Node_VariableSet> SC(*G);auto* SetCache=SC.CreateNode();SetCache->VariableReference.SetSelfMember(CacheName);SetCache->NodePosX=1100;SC.Finalize();
    Link(Pin(Branch,TEXT("else")),Pin(Create,TEXT("execute")));Link(Pin(Create,TEXT("then")),Pin(SetCache,TEXT("execute")));
    Link(Pin(Create,TEXT("ReturnValue")),Pin(SetCache,TEXT("BladeBloodMID")));
    auto* SetDepth=Call(UMaterialInstanceDynamic::StaticClass(),TEXT("SetScalarParameterValue"));
    Default(SetDepth,TEXT("ParameterName"),TEXT("BladeBloodDepth"));
    Link(Pin(Cache,TEXT("BladeBloodMID")),Pin(SetDepth,TEXT("self")));Link(Depth,Pin(SetDepth,TEXT("Value")));
    Link(Pin(Branch,TEXT("then")),Pin(SetDepth,TEXT("execute")));Link(Pin(SetCache,TEXT("then")),Pin(SetDepth,TEXT("execute")));
    auto* Hilt=Call(BP->GeneratedClass,TEXT("get limits location"));Default(Hilt,TEXT("hilt"),TEXT("true"));Default(Hilt,TEXT("current"),TEXT("false"));
    auto* Transform=Call(USceneComponent::StaticClass(),TEXT("K2_GetComponentToWorld"));Link(Pin(Sword,TEXT("sword")),Pin(Transform,TEXT("self")));
    auto* Local=Call(UKismetMathLibrary::StaticClass(),TEXT("InverseTransformLocation"));
    Link(Pin(Transform,TEXT("ReturnValue")),Pin(Local,TEXT("T")));Link(Pin(Hilt,TEXT("location")),Pin(Local,TEXT("Location")));
    auto* BaseZ=Call(UKismetMathLibrary::StaticClass(),TEXT("BreakVector"));Link(Pin(Local,TEXT("ReturnValue")),Pin(BaseZ,TEXT("InVec")));
    auto* SetBase=Call(UMaterialInstanceDynamic::StaticClass(),TEXT("SetScalarParameterValue"));Default(SetBase,TEXT("ParameterName"),TEXT("BladeBaseLocalZ"));
    Link(Pin(Cache,TEXT("BladeBloodMID")),Pin(SetBase,TEXT("self")));Link(Pin(BaseZ,TEXT("Z")),Pin(SetBase,TEXT("Value")));
    Link(Pin(SetDepth,TEXT("then")),Pin(SetBase,TEXT("execute")));
    auto* Scale=Call(USceneComponent::StaticClass(),TEXT("K2_GetComponentScale"));Link(Pin(Sword,TEXT("sword")),Pin(Scale,TEXT("self")));
    auto* ScaleZ=Call(UKismetMathLibrary::StaticClass(),TEXT("BreakVector"));Link(Pin(Scale,TEXT("ReturnValue")),Pin(ScaleZ,TEXT("InVec")));
    auto* Length=Get(TEXT("blade length"),700);
    auto* Divide=Call(UKismetMathLibrary::StaticClass(),TEXT("Divide_DoubleDouble"));
    Link(Pin(Length,TEXT("blade length")),Pin(Divide,TEXT("A")));Link(Pin(ScaleZ,TEXT("Z")),Pin(Divide,TEXT("B")));
    auto* SetLength=Call(UMaterialInstanceDynamic::StaticClass(),TEXT("SetScalarParameterValue"));Default(SetLength,TEXT("ParameterName"),TEXT("BladeLengthLocal"));
    Link(Pin(Cache,TEXT("BladeBloodMID")),Pin(SetLength,TEXT("self")));Link(Pin(Divide,TEXT("ReturnValue")),Pin(SetLength,TEXT("Value")));
    Link(Pin(SetBase,TEXT("then")),Pin(SetLength,TEXT("execute")));
    if (!OK)
    {
        FBlueprintEditorUtils::RemoveGraph(BP,G);
        FBlueprintEditorUtils::RemoveMemberVariable(BP,CacheName);
    }
    if(OK) OK=MakeAdditive(BP);
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    UE_LOG(LogTemp,Display,TEXT("SwordBlood: wiring=%d BlueprintStatus=%d; left unsaved"),OK,int32(BP->Status));
}
static FAutoConsoleCommand Command(TEXT("Prophecy.Blood.InstallSwordDepth"),TEXT("Add the unwired Stain Blade function, preserving existing sword graphs."),FConsoleCommandDelegate::CreateStatic(&Install));
static FAutoConsoleCommand UpgradeCommand(TEXT("Prophecy.Blood.MakeSwordDepthAdditive"),TEXT("Keep accumulated blade depth and existing paint MID."),FConsoleCommandDelegate::CreateStatic(&Upgrade));
static FAutoConsoleCommand SeedCommand(TEXT("Prophecy.Blood.SeedSwordDepth"),TEXT("Add a deterministic seeded blade stain edge."),FConsoleCommandDelegate::CreateStatic(&SeedUpgrade));
}
