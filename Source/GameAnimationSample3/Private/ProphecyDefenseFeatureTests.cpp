#include "ProphecyDefenseFeatures.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseFeatureParityTest,"Prophecy.NN.Defense.ConditioningReference",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseFeatureParityTest::RunTest(const FString&)
{
    using namespace ProphecyDefenseFeatures;
    FString Text;
    if (!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/Models/feature_reference.json"))))
    { AddError(TEXT("ExportDefenseNetworks.py must prepare the local reference inputs first."));return false; }
    TArray<TSharedPtr<FJsonValue>> Cases;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Cases) || Cases.IsEmpty()) return false;
    double Maximum=0;
    for (const auto& Value:Cases)
    {
        const auto Case=Value->AsObject();const auto& Args=Case->GetArrayField(TEXT("args"));
        const int32 Widths[]={9,9,9,9,1,3,1,3,9,3,6};
        float Input[11][9]={};
        if (Args.Num()!=11) { AddError(TEXT("Invalid reference argument count."));return false; }
        for (int32 I=0;I<11;++I)
        {
            const auto& A=Args[I]->AsArray();
            if (A.Num()!=Widths[I]) { AddError(TEXT("Invalid reference argument shape."));return false; }
            for (int32 J=0;J<A.Num();++J) Input[I][J]=float(A[J]->AsNumber());
        }
        FContext C;
        FMemory::Memcpy(C.AttackerPelvis[0],Input[0],9*sizeof(float));
        FMemory::Memcpy(C.AttackerPelvis[1],Input[1],9*sizeof(float));
        FMemory::Memcpy(C.AttackerCollider[0],Input[2],9*sizeof(float));
        FMemory::Memcpy(C.AttackerCollider[1],Input[3],9*sizeof(float));
        C.Event=Input[4][0];C.InitialWorldDelta=Read(Input[5]);C.InitialYawDelta=Input[6][0];
        C.RootPosition=Read(Input[7]);C.RootAxes=Rows(Input[8]);C.TargetWorld=Read(Input[9]);
        FMemory::Memcpy(C.AttackControls,Input[10],6*sizeof(float));
        float Actual[50];
        if (!Conditioning(C,Actual)) { AddError(TEXT("Saved reference has an invalid root."));return false; }
        const auto& Expected=Case->GetArrayField(TEXT("expected"));
        if (Expected.Num()!=50) { AddError(TEXT("Invalid expected conditioning shape."));return false; }
        for (int32 I=0;I<50;++I)
        {
            const float E=float(Expected[I]->AsNumber());
            Maximum=FMath::Max(Maximum,double(FMath::Abs(E-Actual[I])));
            if (!FMath::IsFinite(Actual[I]) || FMath::Abs(E-Actual[I])>1.e-5f+1.e-5f*FMath::Abs(E))
            { AddError(FString::Printf(TEXT("%s channel %d mismatch: %.9g expected %.9g"),*Case->GetStringField(TEXT("key")),I,Actual[I],E));return false; }
        }
        // Same translated/nonorthogonal root, synthetic spear: no fake pelvis.
        C.AttackControls[5]=1;
        if (!Conditioning(C,Actual)) return false;
        for (int32 I=0;I<18;++I) if (Actual[I]!=0) { AddError(TEXT("Spear pelvis is not exactly zero."));return false; }
    }
    AddInfo(FString::Printf(TEXT("%d saved conditioning calls; maximum absolute error %.9g"),Cases.Num(),Maximum));
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseStateParityTest,"Prophecy.NN.Defense.StateReference",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseStateParityTest::RunTest(const FString&)
{
    using namespace ProphecyDefenseFeatures;
    FString Text;TSharedPtr<FJsonObject> Reference;
    if (!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/Models/state_reference.json")))
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Reference) || !Reference)
    { AddError(TEXT("Export the saved state-reference tensors first."));return false; }
    auto ReadArray=[&](const TSharedPtr<FJsonValue>& V,float* Out,int32 Width)
    {
        const auto& A=V->AsArray();
        if (A.Num()!=Width) { AddError(TEXT("Reference state tensor has wrong shape."));return false; }
        for (int32 I=0;I<Width;++I) Out[I]=float(A[I]->AsNumber());
        return true;
    };
    double Maximum=0;
    auto Compare=[&](const float* Actual,const TSharedPtr<FJsonValue>& Expected,int32 Width,const FString& Key)
    {
        const auto& E=Expected->AsArray();
        if (E.Num()!=Width) { AddError(TEXT("Reference result tensor has wrong shape."));return false; }
        for (int32 I=0;I<Width;++I)
        {
            const float Value=float(E[I]->AsNumber()),Difference=FMath::Abs(Actual[I]-Value);
            Maximum=FMath::Max(Maximum,double(Difference));
            if (!FMath::IsFinite(Actual[I]) || Difference>1.e-5f+1.e-5f*FMath::Abs(Value))
            { AddError(FString::Printf(TEXT("%s channel %d: %.9g versus %.9g"),*Key,I,Actual[I],Value));return false; }
        }
        return true;
    };
    int32 Count=0;
    for (const auto& V:Reference->GetArrayField(TEXT("rebases")))
    {
        const auto Case=V->AsObject();const auto& Args=Case->GetArrayField(TEXT("args"));
        if (Args.Num()!=6) return false;
        float Lower[41],Upper[90],FromP[3],FromR[9],ToP[3],ToR[9],OutLower[41],OutUpper[90];
        if (!ReadArray(Args[0],Lower,41) || !ReadArray(Args[1],Upper,90) || !ReadArray(Args[2],FromP,3)
            || !ReadArray(Args[3],FromR,9) || !ReadArray(Args[4],ToP,3) || !ReadArray(Args[5],ToR,9)) return false;
        RebaseLower(Lower,OutLower,Read(FromP),Rows(FromR),Read(ToP),Rows(ToR));
        RebaseUpper(Upper,OutUpper,Read(FromP),Rows(FromR),Read(ToP),Rows(ToR));
        const auto& Expected=Case->GetArrayField(TEXT("expected"));
        if (Expected.Num()!=2 || !Compare(OutLower,Expected[0],41,Case->GetStringField(TEXT("key")))
            || !Compare(OutUpper,Expected[1],90,Case->GetStringField(TEXT("key")))) return false;
        ++Count;
    }
    for (const auto& V:Reference->GetArrayField(TEXT("carries")))
    {
        const auto Case=V->AsObject();const auto& Args=Case->GetArrayField(TEXT("args"));
        float Current[90],CurrentBase[90],NextBase[90],Out[90];
        if (Args.Num()!=3 || !ReadArray(Args[0],Current,90) || !ReadArray(Args[1],CurrentBase,90) || !ReadArray(Args[2],NextBase,90)) return false;
        CarryUpper(Current,CurrentBase,NextBase,Out);
        if (!Compare(Out,Case->TryGetField(TEXT("expected")),90,Case->GetStringField(TEXT("key")))) return false;
        ++Count;
    }
    AddInfo(FString::Printf(TEXT("%d native rebase/carry calls; max absolute error %.9g"),Count,Maximum));
    return Count>0 && !HasAnyErrors();
}
#endif
