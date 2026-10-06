#include "ProphecyDefenseGeometry.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "ProphecyDefenseNetwork.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseOctoberCheckpointTest,"Prophecy.NN.Defense.CheckpointUpdate20261005",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseOctoberCheckpointTest::RunTest(const FString&)
{
    using namespace ProphecyDefense;
    const FString Stage=FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/CheckpointUpdates/Defense20261005");
    const FString Content=FPaths::ProjectContentDir()/TEXT("locomotion/NN/defense");
    FString Text,Error;TSharedPtr<FJsonObject> Document;
    if(!FFileHelper::LoadFileToString(Text,*(Stage/TEXT("validation.json"))) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Document))
    {AddError(TEXT("Stage checkpoints with InstallDefenseCheckpoints.py first."));return false;}
    auto ReadValues=[](const TArray<TSharedPtr<FJsonValue>>& Values)
    {TArray<float> Out;for(const auto& V:Values)Out.Add(float(V->AsNumber()));return Out;};
    double MaxNetwork=0,MaxForearm=0;
    for(const auto& Value:Document->GetArrayField(TEXT("networks")))
    {
        const auto C=Value->AsObject();const FString Name=C->GetStringField(TEXT("model"));
        const int32 Width=C->GetIntegerField(TEXT("width")),Out=C->GetIntegerField(TEXT("out")),Batch=C->GetIntegerField(TEXT("batch"));
        // Actual installed models, not the staging copy.
        FProphecyDefenseNetwork Network;
        if(!Network.Initialize(Content/Name,Width,Out,Error)){AddError(Error);return false;}
        TestEqual(TEXT("Exact forearm contract latched with upper model"),Network.UsesExactForearms(),Name.Contains(TEXT("upper")));
        const auto Input=ReadValues(C->GetArrayField(TEXT("input"))),Expected=ReadValues(C->GetArrayField(TEXT("expected")));
        TArray<float> Actual;Actual.SetNumUninitialized(Batch*Out);
        if(!Network.SetBatch(Batch) || !Network.Run(Input,Actual)){AddError(TEXT("Installed defense NNE execution failed"));return false;}
        for(int32 I=0;I<Actual.Num();++I)
        {
            const float E=FMath::Abs(Actual[I]-Expected[I]);MaxNetwork=FMath::Max(MaxNetwork,double(E));
            if(!FMath::IsFinite(Actual[I]) || E>1.e-5f+1.e-5f*FMath::Abs(Expected[I]))
            {AddError(FString::Printf(TEXT("%s neural parity index %d error %.9g"),*Name,I,E));return false;}
        }
    }
    for(const auto& Value:Document->GetArrayField(TEXT("forearms")))
    {
        const auto C=Value->AsObject();const FString Kind=C->GetStringField(TEXT("kind"));ProphecyDefense::FGeometry G;
        if(!G.Load(Content/(Kind+TEXT("_skeleton.json")),Kind==TEXT("dodge"),Error)){AddError(Error);return false;}
        const auto Lower=ReadValues(C->GetArrayField(TEXT("lower"))),Expected=ReadValues(C->GetArrayField(TEXT("expected")));
        auto Upper=ReadValues(C->GetArrayField(TEXT("upper")));const auto Before=Upper;
        G.ClampExactForearms(Lower.GetData(),Upper.GetData());
        for(int32 I=0;I<90;++I)
        {
            const float E=FMath::Abs(Upper[I]-Expected[I]);MaxForearm=FMath::Max(MaxForearm,double(E));
            if(!FMath::IsFinite(Upper[I]) || E>1.e-5f+1.e-5f*FMath::Abs(Expected[I]))
            {AddError(FString::Printf(TEXT("%s trainer forearm parity index %d error %.9g"),*Kind,I,E));return false;}
            if(!(I>=60&&I<63) && !(I>=75&&I<78))TestEqual(TEXT("Non-position channels unchanged"),Upper[I],Before[I]);
        }
    }
    AddInfo(FString::Printf(TEXT("Installed 4 models at batches1/4; 24 trainer forearm cases. Max neural %.9g; forearm %.9g m"),MaxNetwork,MaxForearm));
    return !HasAnyErrors();
}

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
