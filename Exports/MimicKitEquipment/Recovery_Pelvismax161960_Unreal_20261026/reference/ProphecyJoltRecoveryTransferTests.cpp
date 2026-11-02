#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/PlatformProcess.h"

// Uses the project-loaded Jolt DLL and a separate frozen 15-body test world.
// No game map, active world, PHAT asset or gameplay body is modified.
THIRD_PARTY_INCLUDES_START
#include "../../../../../../Labs/MimicKitTransfer/generated/recovery_fixture.inl"
THIRD_PARTY_INCLUDES_END

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRecoveryTransfer,
    "Prophecy.Jolt.RecoveryTransfer", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyRecoveryTransfer::RunTest(const FString&)
{
    FString Directory;
    if (!FParse::Value(FCommandLine::Get(), TEXT("RecoveryAuditDir="), Directory))
    {
        AddInfo(TEXT("Opt-in audit: supply -RecoveryAuditDir with the policy bridge running."));
        return true;
    }
    if (!TestTrue(TEXT("Jolt ABI matches the installed module"), JPH::VerifyJoltVersionID()) ||
        !TestNotNull(TEXT("Runtime owns the Jolt factory"), JPH::Factory::sInstance)) return false;
    TUniquePtr<ProphecyRecoveryAudit::Fixture> Simulation;
    const double Deadline = FPlatformTime::Seconds() + 600.0;
    int32 Sequence = 0, Ticks = 0, Episodes = 0;
    while (FPlatformTime::Seconds() < Deadline)
    {
        const FString Request = Directory / FString::Printf(TEXT("request_%d.txt"), Sequence);
        FString Command;
        if (!FFileHelper::LoadFileToString(Command, *Request))
        { FPlatformProcess::Sleep(0.002f); continue; }
        std::istringstream Input(TCHAR_TO_UTF8(*Command));
        std::string Verb; Input >> Verb;
        std::ostringstream Output;
        Output << std::setprecision(12);
        std::streambuf* Previous = std::cout.rdbuf(Output.rdbuf());
        std::cout << std::setprecision(12);
        bool bQuit = false;
        if (Verb == "reset")
        {
            std::string Path; std::getline(Input >> std::ws, Path);
            Simulation.Reset();
            Simulation = MakeUnique<ProphecyRecoveryAudit::Fixture>(Path.c_str());
            Simulation->Print(); ++Episodes;
        }
        else if (Verb == "inspect" && Simulation) Simulation->Inspect();
        else if (Verb == "step" && Simulation)
        {
            std::vector<float> Actions(34);
            for (float& Value : Actions) Input >> Value;
            Simulation->Step(Actions); Simulation->Print(); ++Ticks;
        }
        else if (Verb == "quit") { Output << "{}"; bQuit = true; }
        else { Output << "{\"error\":\"Invalid command\"}"; }
        std::cout.rdbuf(Previous);
        const FString Response = Directory / FString::Printf(TEXT("response_%d.json"), Sequence);
        const FString Temporary = Response + TEXT(".tmp");
        FFileHelper::SaveStringToFile(UTF8_TO_TCHAR(Output.str().c_str()), *Temporary, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        FPlatformFileManager::Get().GetPlatformFile().MoveFile(*Response, *Temporary);
        ++Sequence;
        if (bQuit)
        { AddInfo(FString::Printf(TEXT("Completed %d frozen-policy episodes, %d policy ticks."), Episodes, Ticks)); return true; }
    }
    AddError(TEXT("Recovery policy bridge timed out after 600 seconds."));
    return false;
}
#endif
