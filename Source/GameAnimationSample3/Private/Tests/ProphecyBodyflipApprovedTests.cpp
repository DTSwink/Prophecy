#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyBodyflipVM.h"
#include "ProphecyBodyflipNN.h"
#include "Async/Async.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

namespace BodyflipApprovedTest
{
struct FRun
{
    FProphecyBodyflipVM VM;
    FString Error;
    TArray<TSharedPtr<FJsonValue>> Calls,Frames;
    double Seconds=0;
};
static FString Serialize(const TSharedPtr<FJsonObject>& O){FString S;FJsonSerializer::Serialize(O.ToSharedRef(),TJsonWriterFactory<>::Create(&S));return S;}
static TSharedPtr<FJsonObject> Parse(const FString& S){TSharedPtr<FJsonObject> O;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S),O);return O;}
class FExercise : public IAutomationLatentCommand
{
    FAutomationTestBase* Test;
    TSharedPtr<FRun,ESPMode::ThreadSafe> Run=MakeShared<FRun,ESPMode::ThreadSafe>();
    TFuture<bool> Future;
    double Started=0;
    bool Cancelled=false;
public:
    explicit FExercise(FAutomationTestBase* In):Test(In){}
    virtual bool Update() override
    {
        if(!Future.IsValid()){
            FString Text;if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectDir()/TEXT("Labs/BodyflipLab/approved/2026-10-30/saved-profile.json")))){Test->AddError(TEXT("Missing approved Bodyflip scene"));return true;}
            const auto Profile=Parse(Text);if(!Profile){Test->AddError(TEXT("Invalid approved scene"));return true;}const auto Settings=Profile->GetObjectField(TEXT("settings"));const FString SettingsJson=Serialize(Settings);const int32 End=FMath::RoundToInt(Settings->GetNumberField(TEXT("trimOut"))*60);
            if(!ProphecyBodyflip::PrepareNN(TEXT("run"),true,Run->Error)){Test->AddError(Run->Error);return true;}Started=FPlatformTime::Seconds();const auto Work=Run;
            Future=Async(EAsyncExecution::ThreadPool,[Work,SettingsJson,End]{const double Begin=FPlatformTime::Seconds();FString Out;FRun* Owner=Work.Get();bool Good=Work->VM.Initialize([Owner](const FString& Request,FString& Reply,FString& Error){const double Start=FPlatformTime::Seconds();const bool Okay=ProphecyBodyflip::GenerateNN(nullptr,Request,Reply,Error,[Owner]{return Owner->VM.IsCancelled();});auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("request"),Request);Row->SetStringField(TEXT("reply"),Reply);Row->SetStringField(TEXT("error"),Error);Row->SetNumberField(TEXT("seconds"),FPlatformTime::Seconds()-Start);Owner->Calls.Add(MakeShared<FJsonValueObject>(Row));return Okay;},Work->Error);
                if(Good)Good=Work->VM.Command(TEXT("{\"op\":\"start\",\"settings\":")+SettingsJson+TEXT(",\"horizon\":0.016666666666666666}"),Out,Work->Error);
                if(Good)Good=Work->VM.Command(FString::Printf(TEXT("{\"op\":\"prepare\",\"time\":%.17g}"),End/60.),Out,Work->Error);
                for(int32 I=0;Good&&I<=End;I++){Good=Work->VM.Command(FString::Printf(TEXT("{\"op\":\"sample\",\"time\":%.17g}"),I/60.),Out,Work->Error);if(Good){const auto Frame=Parse(Out);if(Frame)Work->Frames.Add(MakeShared<FJsonValueObject>(Frame));else{Good=false;Work->Error=TEXT("Invalid prepared frame JSON");}}}
                Work->Seconds=FPlatformTime::Seconds()-Begin;return Good;
            });return false;
        }
        if(!Future.IsReady()){if(!Cancelled&&FPlatformTime::Seconds()-Started>120){Cancelled=true;Run->VM.Cancel();}return false;}
        const bool Okay=Future.Get();const auto Stats=Run->VM.Statistics();auto Report=MakeShared<FJsonObject>();Report->SetBoolField(TEXT("passed"),Okay);Report->SetStringField(TEXT("error"),Run->Error);Report->SetNumberField(TEXT("seconds"),Run->Seconds);Report->SetNumberField(TEXT("heapBytes"),double(Stats.HeapBytes));Report->SetNumberField(TEXT("peakHeapBytes"),double(Stats.PeakHeapBytes));Report->SetNumberField(TEXT("nnSeconds"),Stats.NNSeconds);Report->SetArrayField(TEXT("nnCalls"),Run->Calls);Report->SetArrayField(TEXT("frames"),Run->Frames);
        const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/BodyflipPort20261030");IFileManager::Get().MakeDirectory(*Dir,true);FFileHelper::SaveStringToFile(Serialize(Report),*(Dir/TEXT("approved-native.json")));
        Test->AddInfo(FString::Printf(TEXT("Approved scene: %d frames, %.3fs total, %.3fs NN (%u calls), %.1f MiB peak"),Run->Frames.Num(),Run->Seconds,Stats.NNSeconds,Stats.NNCalls,Stats.PeakHeapBytes/1048576.));
        if(!Okay)Test->AddError(Run->Error);else{Test->TestEqual(TEXT("Complete approved trim"),Run->Frames.Num(),260);const auto Last=Run->Frames.Last()->AsObject();Test->TestEqual(TEXT("Both approved jump markers retained"),Last->GetArrayField(TEXT("events")).Num(),2);}
        auto Retired=MoveTemp(Run);Async(EAsyncExecution::ThreadPool,[Retired=MoveTemp(Retired)]() mutable{Retired.Reset();});return true;
    }
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipApprovedScene,"Prophecy.Bodyflip.ApprovedScene",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipApprovedScene::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(BodyflipApprovedTest::FExercise(this));return true;}
#endif
