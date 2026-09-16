#include "ProphecyDefenseNetwork.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseNeuralParityTest,"Prophecy.NN.Defense.NeuralReference",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseNeuralParityTest::RunTest(const FString&)
{
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/Models");
    auto Load=[&](const FString& Name,TSharedPtr<FJsonObject>& Out)
    {
        FString Text;
        return FFileHelper::LoadFileToString(Text,*(Directory/Name))
            && FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Out) && Out.IsValid();
    };
    TSharedPtr<FJsonObject> Contract,Reference;
    if (!Load(TEXT("networks.json"),Contract) || !Load(TEXT("neural_reference.json"),Reference))
    { AddError(TEXT("Run Tools/NN/ExportDefenseNetworks.py to prepare the immutable local neural fixtures."));return false; }
    auto Report=MakeShared<FJsonObject>();
    for (const auto& Item:Contract->GetObjectField(TEXT("models"))->Values)
    {
        const auto Model=Item.Value->AsObject();
        const int32 IW=Model->GetIntegerField(TEXT("input_dim")),OW=Model->GetIntegerField(TEXT("output_dim"));
        FProphecyDefenseNetwork Network;FString Error;
        if (!Network.Initialize(Directory/Model->GetStringField(TEXT("file")),IW,OW,Error)) { AddError(Error);return false; }
        const auto& Rows=Reference->GetArrayField(Item.Key);
        TArray<float> Input,Expected,Output;
        for (const auto& Value:Rows)
        {
            const auto Row=Value->AsObject();
            const auto& X=Row->GetArrayField(TEXT("input"))[0]->AsArray();
            const auto& Y=Row->GetArrayField(TEXT("expected"))[0]->AsArray();
            if (X.Num()!=IW || Y.Num()!=OW) { AddError(TEXT("Invalid oracle tensor shape."));return false; }
            for (const auto& V:X) Input.Add(float(V->AsNumber()));
            for (const auto& V:Y) Expected.Add(float(V->AsNumber()));
        }
        double Maximum=0;
        for (int32 Batch:{1,Rows.Num()})
        {
            if (!Network.SetBatch(Batch)) { AddError(TEXT("Defense model batch shape failed."));return false; }
            Output.SetNumUninitialized(Batch*OW);
            for (int32 First=0;First<Rows.Num();First+=Batch)
            {
                if (!Network.Run(MakeArrayView(Input.GetData()+First*IW,Batch*IW),Output)) { AddError(TEXT("NNE defense execution failed."));return false; }
                for (int32 I=0;I<Output.Num();++I)
                {
                    const float E=Expected[First*OW+I],A=Output[I];
                    Maximum=FMath::Max(Maximum,double(FMath::Abs(A-E)));
                    if (!FMath::IsFinite(A) || FMath::Abs(A-E)>1.e-5f+1.e-5f*FMath::Abs(E))
                    { AddError(FString::Printf(TEXT("%s batch %d row %d channel %d: %.9g versus %.9g"),*Item.Key,Batch,First+I/OW,I%OW,A,E));return false; }
                }
            }
        }
        Report->SetNumberField(Item.Key,Maximum);
    }
    FString Json;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Json));
    FFileHelper::SaveStringToFile(Json,*(Directory/TEXT("unreal_neural_parity.json")));
    return !HasAnyErrors();
}
#endif
