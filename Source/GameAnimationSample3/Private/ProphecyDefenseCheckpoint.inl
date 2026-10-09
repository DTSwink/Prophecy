#include "ProphecyDefenseCheckpoint.h"
#include "ProphecyNNLocomotionManager.h"

namespace ProphecyDefenseCheckpoint
{
struct FSelection
{
    int32 Index=0;
    FProphecyDefenseNetwork* Live=nullptr;
    TUniquePtr<FProphecyDefenseNetwork> Pending;
};
struct FSelections { FSelection Modes[2]; };
// Destructor cleanup runs after UObject has lost its object-array index. Use
// identity only: constructing a weak key there asserts. The manager destructor
// always removes this non-owning entry before its address can be reused.
static TMap<const AProphecyNNLocomotionManager*,TUniquePtr<FSelections>> Selections;
static FString ModelPath(bool Dodge,int32 Index)
{
    FString Dir=FPaths::ProjectContentDir()/TEXT("locomotion/NN/defense");
    if(Index)
    {
        static const TCHAR* Parry[]={TEXT("Parry1149700"),TEXT("Parry1178405"),TEXT("Parry1216457")};
        static const TCHAR* Dodges[]={TEXT("Dodge322925"),TEXT("Dodge151341")};
        Dir=Dir/TEXT("pickers")/(Dodge?Dodges[Index-1]:Parry[Index-1]);
    }
    return Dir/(Dodge?TEXT("prophecy_dodge_upper.onnx"):TEXT("prophecy_parry_upper.onnx"));
}
static bool Load(bool Dodge,int32 Index,FProphecyDefenseNetwork& Network,FString& Error)
{
    const int32 In=Dodge?362:258,Out=Dodge?112:90;
    if(!Network.Initialize(ModelPath(Dodge,Index),In,Out,Error))return false;
    if(!Network.UsesExactForearms()) {Error=TEXT("Defense picker requires the exact-forearm checkpoint contract.");return false;}
    // Selection-time shape/finite-output validation, never extra gameplay inference.
    TArray<float> Inputs,Outputs;Inputs.SetNumZeroed(4*In);Outputs.SetNumUninitialized(4*Out);
    for(int32 Batch:{1,4})
    {
        if(!Network.SetBatch(Batch) || !Network.Run(MakeArrayView(Inputs.GetData(),Batch*In),MakeArrayView(Outputs.GetData(),Batch*Out)))
        {Error=TEXT("Defense checkpoint startup inference failed.");return false;}
        for(int32 I=0;I<Batch*Out;++I)if(!FMath::IsFinite(Outputs[I]))
        {Error=TEXT("Defense checkpoint produced nonfinite output.");return false;}
    }
    Network.SetBatch(1);return true;
}
static FSelection& Entry(const AProphecyNNLocomotionManager* Manager,bool Dodge)
{
    auto& Pair=Selections.FindOrAdd(Manager);if(!Pair)Pair=MakeUnique<FSelections>();
    return Pair->Modes[int32(Dodge)];
}
int32 Get(const AProphecyNNLocomotionManager* Manager,bool Dodge)
{
    const auto* Pair=Selections.Find(Manager);return Pair?(*Pair)->Modes[int32(Dodge)].Index:0;
}
bool Set(AProphecyNNLocomotionManager* Manager,bool Dodge,int32 Index,FString& Error)
{
    Error.Reset();
    if(!IsInGameThread() || !IsValid(Manager) || Manager->IsActorBeingDestroyed() || Index<0 || Index>(Dodge?2:3))
    {Error=TEXT("Invalid defense checkpoint selection or manager.");return false;}
    if(Get(Manager,Dodge)==Index)return true;
    auto Next=MakeUnique<FProphecyDefenseNetwork>();
    if(!Load(Dodge,Index,*Next,Error))return false;
    auto& Selected=Entry(Manager,Dodge);
    if(Selected.Live)Selected.Live->SwapWith(*Next);
    else Selected.Pending=MoveTemp(Next);
    Selected.Index=Index;return true;
}
bool Initialize(AProphecyNNLocomotionManager* Manager,bool Dodge,FProphecyDefenseNetwork& Network,FString& Error)
{
    auto& Selected=Entry(Manager,Dodge);
    if(Selected.Live==&Network)return true;
    if(Selected.Pending)
    {Network.SwapWith(*Selected.Pending);Selected.Pending.Reset();}
    else
    {
        // Untouched project defaults keep the original lazy initialization path.
        if(!Network.Initialize(ModelPath(Dodge,Selected.Index),Dodge?362:258,Dodge?112:90,Error))return false;
    }
    Selected.Live=&Network;return true;
}
void Remove(const AProphecyNNLocomotionManager* Manager){Selections.Remove(Manager);}
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "UObject/GarbageCollection.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefensePickerTest,"Prophecy.NN.Defense.CheckpointPickers",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefensePickerTest::RunTest(const FString&)
{
    using namespace ProphecyDefenseCheckpoint;
    TStrongObjectPtr<AProphecyNNLocomotionManager> Manager(NewObject<AProphecyNNLocomotionManager>());
    TStrongObjectPtr<AProphecyNNLocomotionManager> Other(NewObject<AProphecyNNLocomotionManager>());
    ON_SCOPE_EXIT {Remove(Manager.Get());Remove(Other.Get());};
    FString Error,Text;TSharedPtr<FJsonObject> Oracle;
    const FString File=FPaths::ProjectSavedDir()/TEXT("Diagnostics/DefensePickers20261008/export/validation.json");
    if(!FFileHelper::LoadFileToString(Text,*File) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Oracle))
    {AddError(TEXT("BuildDefensePickers.py must prepare the checkpoint oracles."));return false;}
    double MaxError=0.;int32 Cases=0;
    auto Check=[&](bool Dodge,int32 Index,FProphecyDefenseNetwork& Network)
    {
        const FString Folder=FPaths::GetCleanFilename(FPaths::GetPath(ModelPath(Dodge,Index?Index:1)));
        int32 Matched=0;
        for(const auto& V:Oracle->GetArrayField(TEXT("networks")))
        {
            const auto R=V->AsObject();if(R->GetStringField(TEXT("folder"))!=Folder)continue;
            ++Matched;++Cases;
            TArray<float> X,Y,Output;
            for(const auto& F:R->GetArrayField(TEXT("input")))X.Add(float(F->AsNumber()));
            for(const auto& F:R->GetArrayField(TEXT("expected")))Y.Add(float(F->AsNumber()));
            Output.SetNumUninitialized(Y.Num());
            if(!Network.SetBatch(R->GetIntegerField(TEXT("batch"))) || !Network.Run(X,Output))
            {AddError(TEXT("Selected model inference failed: ")+Folder);return false;}
            for(int32 I=0;I<Y.Num();++I)
            {
                const double E=FMath::Abs(Output[I]-Y[I]);MaxError=FMath::Max(MaxError,E);
                if(!FMath::IsFinite(Output[I]) || E>1.e-5+1.e-5*FMath::Abs(Y[I]))
                {AddError(TEXT("Selected network differs from PyTorch: ")+Folder);return false;}
            }
        }
        TestTrue(TEXT("Oracle covers selected checkpoint"),Matched>=2);
        TestTrue(TEXT("Exact forearm mode retained"),Network.UsesExactForearms());return true;
    };
    TestEqual(TEXT("Default Parry unchanged"),Get(Manager.Get(),false),0);
    TestEqual(TEXT("Default Dodge unchanged"),Get(Manager.Get(),true),0);
    if(!TestTrue(TEXT("Select before lazy initialization"),Set(Manager.Get(),false,2,Error))) {AddError(Error);return false;}
    auto* Pending=Entry(Manager.Get(),false).Pending.Get();
    TestTrue(TEXT("Pending model cached"),Pending!=nullptr);
    TestTrue(TEXT("Same choice succeeds"),Set(Manager.Get(),false,2,Error));
    TestTrue(TEXT("Same choice reuses loaded model"),Entry(Manager.Get(),false).Pending.Get()==Pending);
    FProphecyDefenseNetwork Parry,Dodge;
    if(!TestTrue(TEXT("Bind pending Parry"),Initialize(Manager.Get(),false,Parry,Error)))return false;
    TestFalse(TEXT("Pending allocation consumed once"),bool(Entry(Manager.Get(),false).Pending));
    if(!Check(false,2,Parry))return false;
    for(int32 Index:{1,3,0,2})
    {
        if(!Set(Manager.Get(),false,Index,Error)){AddError(Error);return false;}
        TestEqual(TEXT("Parry getter"),Get(Manager.Get(),false),Index);
        if(!Check(false,Index,Parry))return false;
        TestEqual(TEXT("Parry does not switch Dodge"),Get(Manager.Get(),true),0);
    }
    if(!Initialize(Manager.Get(),true,Dodge,Error)){AddError(Error);return false;}
    for(int32 Index:{0,2,1,0})
    {
        if(!Set(Manager.Get(),true,Index,Error)){AddError(Error);return false;}
        TestEqual(TEXT("Dodge getter"),Get(Manager.Get(),true),Index);
        if(!Check(true,Index,Dodge))return false;
        TestEqual(TEXT("Dodge does not switch Parry"),Get(Manager.Get(),false),2);
    }
    TestFalse(TEXT("Invalid choice rejected"),Set(Manager.Get(),false,255,Error));
    TestFalse(TEXT("Null manager rejected"),Set(nullptr,false,1,Error));
    TestEqual(TEXT("Failure preserves previous choice"),Get(Manager.Get(),false),2);
    if(!Check(false,2,Parry))return false;
    TestEqual(TEXT("Other manager isolated"),Get(Other.Get(),false),0);
    if(!Set(Other.Get(),true,2,Error)){AddError(Error);return false;}
    TestEqual(TEXT("Other manager choice independent"),Get(Manager.Get(),true),0);
    Remove(Other.Get());TestFalse(TEXT("Cleanup drops pending model"),Selections.Contains(Other.Get()));
    Remove(Manager.Get());TestFalse(TEXT("Cleanup drops live bindings"),Selections.Contains(Manager.Get()));
    // Reproduce autosave's full purge, including destructor cleanup after the
    // UObject array index is invalid. One manager still owns a selection entry.
    const auto* Retiring=Other.Get();
    Entry(Retiring,false);
    Manager.Reset();Other.Reset();
    CollectGarbage(RF_NoFlags,true);
    TestFalse(TEXT("Garbage collection removes selection without weak-key access"),Selections.Contains(Retiring));
    AddInfo(FString::Printf(TEXT("Defense picker parity: %d batches, max abs error %.9g"),Cases,MaxError));
    return !HasAnyErrors();
}
#endif
