#include "Misc/AutomationTest.h"
#include "ProphecyBodyflipVM.h"
#include "ProphecyBodyflipPlanner.h"
#include "Async/Async.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "Misc/ScopeLock.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipRuntimeParity,"Prophecy.Bodyflip.EmbeddedRuntimeParity",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipRuntimeParity::RunTest(const FString&)
{
    FString Text,Error,Result;TSharedPtr<FJsonObject> Fixture;
    const FString Path=FPaths::ProjectSavedDir()/TEXT("Diagnostics/BodyflipPort20261030/embedded-fixture.json");
    if(!TestTrue(TEXT("Independent Node parity fixture"),FFileHelper::LoadFileToString(Text,*Path)&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Fixture)))return false;
    FProphecyBodyflipVM VM;if(!TestTrue(TEXT("Embedded V8 initializes without external process"),VM.Initialize({},Error))){AddError(Error);return false;}
    const auto& Cases=Fixture->GetArrayField(TEXT("cases"));const auto& Expected=Fixture->GetObjectField(TEXT("expected"))->GetArrayField(TEXT("results"));
    double WorstPosition=0,WorstRotation=0;int32 Frames=0;
    for(int32 Scenario=0;Scenario<3;Scenario++)
    {
        FString Settings;FJsonSerializer::Serialize(Cases[Scenario]->AsObject()->GetObjectField(TEXT("settings")).ToSharedRef(),TJsonWriterFactory<>::Create(&Settings));
        if(!VM.Command(TEXT("{\"op\":\"start\",\"settings\":")+Settings+TEXT(",\"horizon\":0.016666666666666666}"),Result,Error)){AddError(Error);return false;}
        for(const auto& Entry:Expected[Scenario]->AsObject()->GetArrayField(TEXT("samples")))
        {
            const auto E=Entry->AsObject();const double Time=E->GetNumberField(TEXT("time"));
            if(!VM.Command(FString::Printf(TEXT("{\"op\":\"sample\",\"time\":%.17g}"),Time),Result,Error)){AddError(Error);return false;}
            TSharedPtr<FJsonObject> Actual;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Result),Actual)){AddError(TEXT("Native runtime emitted invalid JSON"));return false;}
            TestEqual(TEXT("Exact phase"),Actual->GetStringField(TEXT("phase")),E->GetStringField(TEXT("phase")));
            const auto A=Actual->GetObjectField(TEXT("pose")),B=E->GetObjectField(TEXT("pose"));const auto& AP=A->GetArrayField(TEXT("points"));const auto& BP=B->GetArrayField(TEXT("points"));const auto& AQ=A->GetArrayField(TEXT("q"));const auto& BQ=B->GetArrayField(TEXT("q"));
            for(int32 Bone=0;Bone<AP.Num();Bone++){double Distance=0,Dot=0;for(int32 I=0;I<3;I++)Distance+=FMath::Square(AP[Bone]->AsArray()[I]->AsNumber()-BP[Bone]->AsArray()[I]->AsNumber());for(int32 I=0;I<4;I++)Dot+=AQ[Bone]->AsArray()[I]->AsNumber()*BQ[Bone]->AsArray()[I]->AsNumber();WorstPosition=FMath::Max(WorstPosition,FMath::Sqrt(Distance));WorstRotation=FMath::Max(WorstRotation,1-FMath::Abs(Dot));}Frames++;
        }
    }
    TestTrue(TEXT("Node/native position parity under10nm"),WorstPosition<1.e-8);TestTrue(TEXT("Node/native quaternion parity"),WorstRotation<1.e-10);
    AddInfo(FString::Printf(TEXT("%d authored runtime frames; max position %.12g m; quaternion %.12g"),Frames,WorstPosition,WorstRotation));return true;
}
// Exercise a runtime moving between serial worker jobs: extending a trim must
// retain the exact prepared prefix instead of reinitializing its recurrence.
class FBodyflipPlannerExtension : public IAutomationLatentCommand
{
    FAutomationTestBase* Test;
    TUniquePtr<FProphecyBodyflipPlanner> Planner=MakeUnique<FProphecyBodyflipPlanner>();
    FString First;int32 Stage=0;double Began=FPlatformTime::Seconds();
public:
    explicit FBodyflipPlannerExtension(FAutomationTestBase* In):Test(In){}
    virtual bool Update() override
    {
        FString Error;
        if(FPlatformTime::Seconds()-Began>90){Test->AddError(TEXT("Async Bodyflip preparation timed out"));return true;}
        const FString Settings=TEXT("{\"mode\":\"spaceGym\",\"trimOut\":0.2,\"jumpEvents\":[{\"id\":\"spin\",\"time\":0,\"flip\":120,\"twist\":60,\"spinVersion\":2}]}");
        if(Stage==0){if(!Planner->Prepare(Settings,TEXT(""),.1,true,Error)){Test->AddError(Error);return true;}Stage=1;return false;}
        if(!Planner->Poll(Error)){Test->AddError(Error);return true;}if(Planner->Busy())return false;
        if(Stage==1){Test->TestTrue(TEXT("Prepared prefix frame"),Planner->Frame(3,First));if(!Planner->Prepare(Settings,TEXT(""),.2,false,Error)){Test->AddError(Error);return true;}Stage=2;return false;}
        FString Again,End;Test->TestTrue(TEXT("Prefix retained"),Planner->Frame(3,Again));Test->TestEqual(TEXT("Prefix exactly unchanged"),Again,First);Test->TestTrue(TEXT("New trim edge prepared"),Planner->Frame(12,End));return true;
    }
};
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipPlannerExtensionTest,"Prophecy.Bodyflip.AsyncTrimExtension",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipPlannerExtensionTest::RunTest(const FString&)
{
    ADD_LATENT_AUTOMATION_COMMAND(FBodyflipPlannerExtension(this));return true;
}

namespace BodyflipVMTests
{
static const TCHAR* EmptySpace=TEXT("{\"op\":\"start\",\"settings\":{\"mode\":\"spaceGym\",\"aim\":false,\"jumpEvents\":[]},\"horizon\":0.016666666666666666}");
struct FInterruptWork
{
    FCriticalSection Mutex;TSharedPtr<FProphecyBodyflipVM,ESPMode::ThreadSafe> Runtime;
    TAtomic<bool> Entered{false},CancelIssued{false};
    bool Initialized=false,CommandSucceeded=false,Recreated=false;FString Error,RecreateError,Output;
    void Cancel()
    {
        // Keep the context alive across the interrupt, then drop this reference
        // before allowing the native callback to finish and dispose it.
        {TSharedPtr<FProphecyBodyflipVM,ESPMode::ThreadSafe> Copy;{FScopeLock Lock(&Mutex);Copy=Runtime;}if(Copy)Copy->Cancel();}
        CancelIssued.Store(true);
    }
};
class FInterrupt : public IAutomationLatentCommand
{
    FAutomationTestBase* Test;TSharedRef<FInterruptWork,ESPMode::ThreadSafe> Work=MakeShared<FInterruptWork,ESPMode::ThreadSafe>();
    TFuture<void> Future;double Began=FPlatformTime::Seconds();bool TimedOut=false;
public:
    explicit FInterrupt(FAutomationTestBase* In):Test(In){}
    bool Update() override
    {
        if(!Future.IsValid())
        {
            Future=Async(EAsyncExecution::ThreadPool,[W=Work]
            {
                TSharedPtr<FProphecyBodyflipVM,ESPMode::ThreadSafe> Runtime=MakeShared<FProphecyBodyflipVM,ESPMode::ThreadSafe>();{FScopeLock Lock(&W->Mutex);W->Runtime=Runtime;}
                W->Initialized=Runtime->Initialize([W](const FString&,FString&,FString& Error)
                {
                    W->Entered.Store(true);const double Until=FPlatformTime::Seconds()+10;
                    while(!W->CancelIssued.Load()&&FPlatformTime::Seconds()<Until)FPlatformProcess::SleepNoStats(.001f);
                    Error=W->CancelIssued.Load()?TEXT("Native test callback cancelled"):TEXT("Bounded native test callback expired");return false;
                },W->Error);
                if(W->Initialized)W->CommandSucceeded=Runtime->Command(TEXT("{\"op\":\"start\",\"settings\":{\"mode\":\"jump\",\"aim\":false},\"horizon\":0.016666666666666666}"),W->Output,W->Error);
                {FScopeLock Lock(&W->Mutex);W->Runtime.Reset();}Runtime.Reset();
                // Disposal must finish before a fresh context runs. This also
                // catches stale callback tables, timer handles or termination.
                FProphecyBodyflipVM Fresh;FString Result;W->Recreated=Fresh.Initialize({},W->RecreateError)&&Fresh.Command(EmptySpace,Result,W->RecreateError)&&Fresh.Command(TEXT("{\"op\":\"sample\",\"time\":0}"),Result,W->RecreateError);
            });return false;
        }
        if(Work->Entered.Load()&&!Work->CancelIssued.Load())Work->Cancel();
        if(Future.IsReady())
        {
            Future.Get();Test->TestTrue(TEXT("V8 reached the bounded native callback"),Work->Initialized&&Work->Entered.Load());
            Test->TestFalse(TEXT("Asynchronously interrupted command cannot publish success"),Work->CommandSucceeded);
            Test->TestTrue(TEXT("V8 interruption reports cancellation"),Work->Error.Contains(TEXT("cancelled")));Test->TestTrue(TEXT("Interrupted command clears its partial output"),Work->Output.IsEmpty());
            Test->TestTrue(TEXT("Interrupted V8 context disposes and recreates cleanly"),Work->Recreated);if(!Work->Recreated)Test->AddError(Work->RecreateError);return true;
        }
        if(FPlatformTime::Seconds()-Began>45&&!TimedOut){TimedOut=true;Test->AddError(TEXT("V8 interruption fixture exceeded its bounded duration"));Work->Cancel();}
        return TimedOut&&FPlatformTime::Seconds()-Began>60;
    }
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipV8Interruption,"Prophecy.Bodyflip.V8.InterruptAndRecreate",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipV8Interruption::RunTest(const FString&)
{ADD_LATENT_AUTOMATION_COMMAND(BodyflipVMTests::FInterrupt(this));return true;}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipV8Budget,"Prophecy.Bodyflip.V8.BudgetAndRecreate",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipV8Budget::RunTest(const FString&)
{
    FString Error,Result;uint64 Peak=0;
    {
        // The production parser supplies ordinary, trusted assets. An 8 MiB
        // soft budget must stop it far below the unchanged 448 MiB hard limit;
        // this does not allocate a synthetic bomb or trigger a real OOM.
        FProphecyBodyflipVM Small(8ull*1024*1024);TestFalse(TEXT("Small private heap budget aborts authored asset loading"),Small.Initialize({},Error));Peak=Small.Statistics().PeakHeapBytes;
        TestTrue(TEXT("Heap abort gives a memory-budget error"),Error.Contains(TEXT("memory budget")));TestTrue(TEXT("Aborted heap stays cancelled"),Small.IsCancelled());
        TestFalse(TEXT("Aborted heap rejects later commands"),Small.Command(BodyflipVMTests::EmptySpace,Result,Error));TestTrue(TEXT("Heap abort publishes no command output"),Result.IsEmpty());
    }
    TestTrue(TEXT("Bounded heap failure occurs below128MiB"),Peak<128ull*1024*1024);
    FProphecyBodyflipVM Fresh;const bool Good=Fresh.Initialize({},Error)&&Fresh.Command(BodyflipVMTests::EmptySpace,Result,Error)&&Fresh.Command(TEXT("{\"op\":\"sample\",\"time\":0}"),Result,Error);
    TestTrue(TEXT("Heap-limited V8 context disposes and recreates cleanly"),Good);if(!Good)AddError(Error);AddInfo(FString::Printf(TEXT("Bounded failure sampled peak %.2f MiB"),Peak/1048576.));return !HasAnyErrors();
}
#endif
