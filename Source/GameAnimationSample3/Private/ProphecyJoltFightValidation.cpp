#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/Level.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "Misc/AssertionMacros.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace ProphecyJolt::FightValidation
{
namespace
{
FDelegateHandle PostInitHandle;
FTSTicker::FDelegateHandle TickHandle;
FString RequestedDirectory;

bool Save(const FString& Path, const TSharedRef<FJsonObject>& Report)
{
    FString Text;
    return FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Text))
        && FFileHelper::SaveStringToFile(Text, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
            &IFileManager::Get(), FILEWRITE_NoReplaceExisting);
}

bool CheckSavedFloor(FJsonObject& Report, FString& Error)
{
    // Read the packaged map without starting its gameplay or saving anything.
    UWorld* Map = LoadObject<UWorld>(nullptr, TEXT("/Game/testNN.testNN"));
    if (!Map || !Map->PersistentLevel)
    { Error = TEXT("The final package is missing the testNN map."); return false; }
    AActor* FloorActor = nullptr;
    for (AActor* Actor : Map->PersistentLevel->Actors)
        if (Actor && Actor->GetFName() == FName(TEXT("Floor_0"))) FloorActor = Actor;
    auto* Floor = FloorActor ? FloorActor->FindComponentByClass<UStaticMeshComponent>() : nullptr;
    if (!Floor || !Floor->GetStaticMesh())
    { Error = TEXT("The saved testNN floor actor or mesh component is missing."); return false; }
    Report.SetStringField(TEXT("mesh"), Floor->GetStaticMesh()->GetPathName());
    Report.SetStringField(TEXT("relative_transform"), Floor->GetRelativeTransform().ToString());
    Report.SetBoolField(TEXT("static"), Floor->Mobility == EComponentMobility::Static);
    const bool bValid = Floor->Mobility == EComponentMobility::Static
        && !Floor->BodyInstance.bSimulatePhysics
        && Floor->GetStaticMesh()->GetPathName() == TEXT("/Engine/MapTemplates/SM_Template_Map_Floor.SM_Template_Map_Floor")
        && Floor->GetRelativeLocation().Equals(FVector(0, 0, -0.5), 0.001)
        && Floor->GetRelativeScale3D().Equals(FVector(8), 0.001)
        && Floor->GetRelativeRotation().IsNearlyZero(0.001);
    if (!bValid) Error = TEXT("The saved testNN floor no longer matches the approved fixed transform/mobility.");
    return bValid;
}

bool Run(const FString& Directory)
{
    if (!IsInGameThread() || FPaths::IsRelative(Directory) || Directory.IsEmpty()
        || IFileManager::Get().DirectoryExists(*Directory) || FPaths::FileExists(Directory))
    { UE_LOG(LogTemp, Error, TEXT("Fight validation requires a new absolute output directory on the game thread.")); return false; }
    if (GEngine)
        for (const FWorldContext& Context : GEngine->GetWorldContexts())
            if (Context.WorldType == EWorldType::PIE)
            { UE_LOG(LogTemp, Error, TEXT("End PIE before running the isolated fight validation fixtures.")); return false; }
    if (!IFileManager::Get().MakeDirectory(*Directory, true)) return false;
    auto Report = MakeShared<FJsonObject>();
    Report->SetStringField(TEXT("scope"), TEXT("Current saved map/floor and actual sword/PHAT functional fixtures. No saved startup wiring, NN timing, rendering, cutting or complete game acceptance."));
    Report->SetStringField(TEXT("engine"), FEngineVersion::Current().ToString());
    Report->SetBoolField(TEXT("editor"), GIsEditor);
#if UE_BUILD_SHIPPING
    Report->SetStringField(TEXT("configuration"), TEXT("Shipping"));
#else
    Report->SetStringField(TEXT("configuration"), TEXT("Development"));
#endif
    const SIZE_T InitialEnsures = FDebug::GetNumEnsureFailures();
    FString Error;
    auto Floor = MakeShared<FJsonObject>();
    bool bSuccess = CheckSavedFloor(*Floor, Error);
    Report->SetObjectField(TEXT("saved_floor"), Floor);
    TArray<TSharedPtr<FJsonValue>> Results;
    const TCHAR* Commands[] = { TEXT("Prophecy.Jolt.SwordFixture"), TEXT("Prophecy.Jolt.SwordContactFixture"),
        TEXT("Prophecy.Jolt.SwordFighterContactFixture") };
    for (int32 Index = 0; bSuccess && Index < UE_ARRAY_COUNT(Commands); ++Index)
    {
        auto Row = MakeShared<FJsonObject>();
        const FString Path = FPaths::Combine(Directory, FString::Printf(TEXT("fixture_%d.json"), Index));
        Row->SetStringField(TEXT("command"), Commands[Index]);
        Row->SetStringField(TEXT("report"), Path);
        IConsoleObject* Object = IConsoleManager::Get().FindConsoleObject(Commands[Index]);
        IConsoleCommand* Command = Object ? Object->AsCommand() : nullptr;
        TArray<FString> Args;
        Args.Add(Path);
        FString Text;
        TSharedPtr<FJsonObject> Result;
        bool bFixtureSuccess = false;
        bSuccess = Command && Command->Execute(Args, nullptr, *GLog)
            && FFileHelper::LoadFileToString(Text, *Path)
            && FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Result)
            && Result.IsValid() && Result->TryGetBoolField(TEXT("success"), bFixtureSuccess) && bFixtureSuccess;
        Row->SetBoolField(TEXT("success"), bSuccess);
        if (!bSuccess)
        {
            if (!Result.IsValid() || !Result->TryGetStringField(TEXT("error"), Error) || Error.IsEmpty())
                Error = FString::Printf(TEXT("%s failed or did not produce a successful fresh report."), Commands[Index]);
        }
        Results.Add(MakeShared<FJsonValueObject>(Row));
    }
    Report->SetArrayField(TEXT("fixtures"), Results);
    Report->SetBoolField(TEXT("success"), bSuccess);
    Report->SetStringField(TEXT("error"), Error);
    // Functional success is separate from handled engine/Blueprint diagnostics.
    Report->SetNumberField(TEXT("ensure_count_delta"), double(FDebug::GetNumEnsureFailures() - InitialEnsures));
    const FString ReportPath = FPaths::Combine(Directory, TEXT("validation.json"));
    const bool bSaved = Save(ReportPath, Report);
    UE_LOG(LogTemp, Display, TEXT("JOLT_FIGHT_VALIDATION %s report=%s error=%s"),
        bSaved && bSuccess ? TEXT("SUCCESS") : TEXT("FAILED"), *ReportPath, *Error);
    return bSaved && bSuccess;
}

void Command(const TArray<FString>& Args)
{
    if (Args.Num() != 1)
    { UE_LOG(LogTemp, Error, TEXT("Prophecy.Jolt.ValidateFight requires one new absolute directory.")); return; }
    Run(Args[0]);
}
FAutoConsoleCommand Console(TEXT("Prophecy.Jolt.ValidateFight"),
    TEXT("Saved floor plus actual sword functional/contact fixtures; one new absolute output directory, no PIE."),
    FConsoleCommandWithArgsDelegate::CreateStatic(&Command));

void AfterEngineInit()
{
    TickHandle = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float)
    {
        TickHandle.Reset();
        const bool bSuccess = Run(RequestedDirectory);
        FPlatformMisc::RequestExitWithStatus(false, bSuccess ? 0 : 1);
        return false;
    }));
}
}

void RegisterCommandLine()
{
    // Shipping ignores ExecCmds; explicit opt-in native dispatch works in both configurations.
    if (!GIsEditor && FParse::Value(FCommandLine::Get(), TEXT("JoltFightValidationDir="), RequestedDirectory))
        PostInitHandle = FCoreDelegates::OnPostEngineInit.AddStatic(&AfterEngineInit);
}

void UnregisterCommandLine()
{
    FCoreDelegates::OnPostEngineInit.Remove(PostInitHandle);
    PostInitHandle.Reset();
    if (TickHandle.IsValid()) FTSTicker::RemoveTicker(TickHandle);
    TickHandle.Reset();
}
}
