#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyFootIKPreparation.h"
#include "ProphecyFootIKNN.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

namespace FootIKPreparationTest
{
FString Encode(const TSharedPtr<FJsonObject>& O){FString S;FJsonSerializer::Serialize(O.ToSharedRef(),TJsonWriterFactory<>::Create(&S));return S;}
TSharedPtr<FJsonObject> Parse(const FString& S){TSharedPtr<FJsonObject> O;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S),O);return O;}
void Numbers(const TSharedPtr<FJsonValue>& V,TArray<double>& Out)
{if(V->Type==EJson::Number)Out.Add(V->AsNumber());else if(V->Type==EJson::Array)for(const auto& C:V->AsArray())Numbers(C,Out);else if(V->Type==EJson::Object){TArray<FString> Keys;V->AsObject()->Values.GetKeys(Keys);Keys.Sort();for(const auto& K:Keys)Numbers(V->AsObject()->Values[K],Out);}}
class FExercise final:public IAutomationLatentCommand
{
    FAutomationTestBase* Test;
    TUniquePtr<FProphecyFootIKPreparation> Warm;
    double Started=FPlatformTime::Seconds();int32 Polls=0;
public:
    explicit FExercise(FAutomationTestBase* T):Test(T),Warm(MakeUnique<FProphecyFootIKPreparation>(TEXT("{\"gait\":\"walk\",\"direction\":\"forward\"}"),true)){}
    bool Update() override
    {
        FString Error;const auto State=Warm->State(Error);++Polls;
        if(State==FProphecyFootIKPreparation::EState::Pending)
        {if(FPlatformTime::Seconds()-Started<600)return false;Warm->Cancel();Test->AddError(TEXT("Async Foot IK preparation timed out"));return true;}
        if(State!=FProphecyFootIKPreparation::EState::Ready){Test->AddError(Error);return true;}
        TSharedPtr<FProphecyFootIKNN,ESPMode::ThreadSafe> NN;TUniquePtr<FProphecyFootIKVM> VM;
        if(!Warm->Take(NN,VM,Error)){Test->AddError(Error);return true;}Warm.Reset();
        bool Good=true;FString Raw,Out;
        if(!FFileHelper::LoadFileToString(Raw,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030/NN/forward-stream.json")))){Test->AddError(TEXT("Missing frozen first-step fixture"));Good=false;}
        const auto Fixture=Good?Parse(Raw):nullptr;
        if(Good&&!Fixture){Test->AddError(TEXT("Invalid first-step fixture"));Good=false;}
        if(Good)
        {
            const auto Row=Fixture->GetArrayField(TEXT("steps"))[0]->AsObject(),Request=Row->GetObjectField(TEXT("request"));
            auto WithoutSeeds=Parse(Encode(Request));WithoutSeeds->RemoveField(TEXT("seeds"));WithoutSeeds->RemoveField(TEXT("names"));WithoutSeeds->SetBoolField(TEXT("reset"),false);
            Test->TestFalse(TEXT("Warming sessions never initializes recurrent gait"),NN->Generate(Encode(WithoutSeeds),Out,Error));
            Test->TestTrue(TEXT("The first measured pair is still required"),Error.Contains(TEXT("history seeds")));
            if(!NN->Generate(Encode(Request),Out,Error))Test->AddError(Error);
            else
            {
                TArray<double> Actual,Expected;const auto Result=Parse(Out);
                if(!Result){Test->AddError(TEXT("Invalid warm NN response JSON"));FProphecyFootIKPreparation::Retire(MoveTemp(NN),MoveTemp(VM));return true;}
                Numbers(MakeShared<FJsonValueObject>(Result),Actual);Numbers(MakeShared<FJsonValueObject>(Row->GetObjectField(TEXT("expected"))),Expected);
                Test->TestEqual(TEXT("Warm first-step output layout"),Actual.Num(),Expected.Num());double Maximum=0;
                if(Actual.Num()==Expected.Num())for(int32 I=0;I<Actual.Num();++I)Maximum=FMath::Max(Maximum,FMath::Abs(Actual[I]-Expected[I]));
                Test->TestTrue(TEXT("Cold preparation retains frozen first-step fidelity"),Maximum<=Fixture->GetNumberField(TEXT("tolerance")));
            }
            Test->TestTrue(TEXT("Warm VM moves to game thread and remains callable"),VM&&VM->Command(TEXT("{\"op\":\"close\"}"),Out,Error));
        }
        FProphecyFootIKPreparation::Retire(MoveTemp(NN),MoveTemp(VM));
        Test->AddInfo(FString::Printf(TEXT("Cold sessions/VM prepared asynchronously across%d latent polls; no canned gait generated"),Polls));return true;
    }
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKColdPreparation,"Prophecy.FootIK.AsyncPreparation",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKColdPreparation::RunTest(const FString&)
{
    // Cancelled queued work must never become a ready heap or acquire history.
    for(int32 I=0;I<32;++I)
    {
        FProphecyFootIKPreparation Canceled(TEXT("{\"direction\":\"invalid\"}"),false);Canceled.Cancel();FString Error;
        TSharedPtr<FProphecyFootIKNN,ESPMode::ThreadSafe> NN;TUniquePtr<FProphecyFootIKVM> VM;
        TestFalse(TEXT("Canceled preparation cannot publish"),Canceled.Take(NN,VM,Error));
    }
    ADD_LATENT_AUTOMATION_COMMAND(FootIKPreparationTest::FExercise(this));return true;
}
#endif
