#include "ProphecyDefenseGeometry.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseGeometryParityTest,"Prophecy.NN.Defense.GeometryReference",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseGeometryParityTest::RunTest(const FString&)
{
    using namespace ProphecyDefense;
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/Models");
    ProphecyDefense::FGeometry Geometry;FString Error,Text;
    if (!Geometry.Load(Directory/TEXT("parry_skeleton.json"),false,Error)) { AddError(Error);return false; }
    TArray<TSharedPtr<FJsonValue>> Cases;
    if (!FFileHelper::LoadFileToString(Text,*(Directory/TEXT("geometry_reference.json"))) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Cases))
    { AddError(TEXT("Run ExportDefenseGeometryReference.py first."));return false; }
    auto ReadArray=[&](const TSharedPtr<FJsonValue>& V,float* Out,int32 Width)
    {
        if (!V || V->Type!=EJson::Array || V->AsArray().Num()!=Width) { AddError(TEXT("Invalid geometry test tensor."));return false; }
        for (int32 I=0;I<Width;++I) Out[I]=float(V->AsArray()[I]->AsNumber());return true;
    };
    double MaxPosition=0,MaxRotation=0;
    auto Compare=[&](const FPose& Pose,const TSharedPtr<FJsonValue>& PV,const TSharedPtr<FJsonValue>& RV,const FString& Key)
    {
        float P[75],R[225];if (!ReadArray(PV,P,75) || !ReadArray(RV,R,225)) return false;
        for (int32 I=0;I<25;++I) for (int32 Channel=0;Channel<12;++Channel)
        {
            const float Actual=Channel<3?Pose.P[I][Channel]:Pose.R[I].V[(Channel-3)/3][(Channel-3)%3];
            const float Expected=Channel<3?P[I*3+Channel]:R[I*9+Channel-3];
            const float Difference=FMath::Abs(Actual-Expected);
            double& Maximum=Channel<3?MaxPosition:MaxRotation;Maximum=FMath::Max(Maximum,double(Difference));
            if (!FMath::IsFinite(Actual) || Difference>1.e-5f+1.e-5f*FMath::Abs(Expected))
            { AddError(FString::Printf(TEXT("%s bone %d channel %d: %.9g expected %.9g"),*Key,I,Channel,Actual,Expected));return false; }
        }
        return true;
    };
    for (const auto& V:Cases)
    {
        const auto C=V->AsObject();const auto& Args=C->GetArrayField(TEXT("args"));const auto& E=C->GetArrayField(TEXT("expected"));
        const FString Key=C->GetStringField(TEXT("key"));
        float Lower[41],Upper[90],Baseline[90],P[3],R[9];FPose Out;
        const bool Raw=C->GetStringField(TEXT("kind"))==TEXT("raw");
        if (Args.Num()!=(Raw?5:4) || E.Num()!=(Raw?4:2) || !ReadArray(Args[0],Lower,41) || !ReadArray(Args[1],Upper,90)
            || !ReadArray(Args[Raw?3:2],P,3) || !ReadArray(Args[Raw?4:3],R,9)) return false;
        if (Raw)
        {
            if (!ReadArray(Args[2],Baseline,90)) return false;
            Geometry.RawPose(Lower,Upper,Read(P),Rows(R),Out);
            if (!Compare(Out,E[0],E[1],Key+TEXT(" first"))) return false;
            Geometry.RawPose(Lower,Baseline,Read(P),Rows(R),Out);
            if (!Compare(Out,E[2],E[3],Key+TEXT(" second"))) return false;
        }
        else
        {
            FPose Frozen;const auto KW=C->GetObjectField(TEXT("kwargs"));
            if (KW->HasField(TEXT("frozen_pos")))
            {
                float FP[75],FR[225];
                if (!ReadArray(KW->TryGetField(TEXT("frozen_pos")),FP,75) || !ReadArray(KW->TryGetField(TEXT("frozen_rot")),FR,225)
                    || !ReadArray(KW->TryGetField(TEXT("baseline_upper")),Baseline,90)) return false;
                for (int32 I=0;I<25;++I) { Frozen.P[I]=Read(FP+I*3);Frozen.R[I]=Rows(FR+I*9); }
            }
            else { Geometry.LowerPose(Lower,Read(P),Rows(R),Frozen);Geometry.EncodeUpper(Frozen,Read(P),Rows(R),Baseline); }
            Geometry.Finish(Lower,Upper,Read(P),Rows(R),Frozen,Baseline,Out);
            if (!Compare(Out,E[0],E[1],Key)) return false;
        }
    }
    AddInfo(FString::Printf(TEXT("%d saved FK calls; max position error %.9g m, rotation element error %.9g"),Cases.Num(),MaxPosition,MaxRotation));
    return !Cases.IsEmpty() && !HasAnyErrors();
}
#endif
