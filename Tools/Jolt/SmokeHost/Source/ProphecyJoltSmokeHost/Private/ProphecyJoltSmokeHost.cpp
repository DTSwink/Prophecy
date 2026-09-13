#include "CoreMinimal.h"

#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
#include "ProphecyJoltShapeAsset.h"
#include "Serialization/JsonWriter.h"
#include "UObject/UObjectGlobals.h"

#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#endif

DEFINE_LOG_CATEGORY_STATIC(LogProphecyJoltSmokeHost, Log, All);

namespace ProphecyJoltSmokeHost
{
constexpr TCHAR FixtureObjectPath[] = TEXT("/Game/Fixture/DA_CompoundFixture.DA_CompoundFixture");

void EmitResult(bool bSuccess, const FString& Detail)
{
	const FString Line = FString::Printf(TEXT("PROPHECY_JOLT_FIXTURE_VALIDATION_%s %s\n"), bSuccess ? TEXT("SUCCESS") : TEXT("FAILED"), *Detail);
	// Shipping may compile UE_LOG out. Write directly to the inherited stdout
	// handle so redirected process output still receives the result marker.
#if PLATFORM_WINDOWS
	const HANDLE Output = ::GetStdHandle(STD_OUTPUT_HANDLE);
	if (Output != nullptr && Output != INVALID_HANDLE_VALUE)
	{
		const FTCHARToUTF8 Utf8(*Line);
		DWORD Written = 0;
		::WriteFile(Output, Utf8.Get(), static_cast<DWORD>(Utf8.Length()), &Written, nullptr);
	}
#endif
	FPlatformMisc::LowLevelOutputDebugString(*Line);
	if (bSuccess)
	{
		UE_LOG(LogProphecyJoltSmokeHost, Display, TEXT("%s"), *Line);
	}
	else
	{
		UE_LOG(LogProphecyJoltSmokeHost, Error, TEXT("%s"), *Line);
	}
}

bool WriteResultFile(const FString& Filename, bool bSuccess, const UProphecyJoltShapeAsset* Asset, const FString& Error, FString& OutWriteError)
{
	if (Filename.IsEmpty() || FPaths::IsRelative(Filename))
	{
		OutWriteError = TEXT("ProphecyJoltFixtureResult must be an absolute filename.");
		return false;
	}
	if (IFileManager::Get().FileExists(*Filename))
	{
		OutWriteError = TEXT("Result report already exists; refusing to overwrite it.");
		return false;
	}
	FString Json;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
	Writer->WriteObjectStart();
	Writer->WriteValue(TEXT("success"), bSuccess);
	Writer->WriteValue(TEXT("asset"), FixtureObjectPath);
	Writer->WriteValue(TEXT("archive_bytes"), Asset ? Asset->ArchiveByteCount : 0);
	Writer->WriteValue(TEXT("archive_sha1"), Asset ? Asset->ArchiveSha1 : FString());
	Writer->WriteValue(TEXT("error"), Error);
	Writer->WriteValue(TEXT("os_exit_code_is_not_validation_evidence"), true);
	Writer->WriteObjectEnd();
	Writer->Close();
	if (!FFileHelper::SaveStringToFile(Json, *Filename, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
		&IFileManager::Get(), FILEWRITE_NoReplaceExisting))
	{
		OutWriteError = TEXT("Could not create the result report; its directory must exist and the filename must be unused.");
		return false;
	}
	return true;
}
}

class FProphecyJoltSmokeHostModule final : public FDefaultGameModuleImpl
{
public:
	virtual void StartupModule() override
	{
		if (FParse::Param(FCommandLine::Get(), TEXT("ProphecyJoltValidateFixture")) && !IsRunningCommandlet())
		{
			PostEngineInitHandle = FCoreDelegates::OnPostEngineInit.AddRaw(this, &FProphecyJoltSmokeHostModule::ValidateFixture);
		}
	}

	virtual void ShutdownModule() override
	{
		RemoveInitDelegate();
	}

private:
	void RemoveInitDelegate()
	{
		if (PostEngineInitHandle.IsValid())
		{
			FCoreDelegates::OnPostEngineInit.Remove(PostEngineInitHandle);
			PostEngineInitHandle.Reset();
		}
	}

	void ValidateFixture()
	{
		using namespace ProphecyJoltSmokeHost;
		RemoveInitDelegate();
		const UProphecyJoltShapeAsset* Asset = LoadObject<UProphecyJoltShapeAsset>(nullptr, FixtureObjectPath);
		FString Error;
		bool bSuccess = false;
		if (Asset == nullptr)
		{
			Error = TEXT("Cooked fixture asset could not be loaded.");
		}
		else
		{
			bSuccess = Asset->ValidateCompoundFixture(Error);
		}
		FString ResultFilename;
		if (FParse::Value(FCommandLine::Get(), TEXT("ProphecyJoltFixtureResult="), ResultFilename))
		{
			FString WriteError;
			if (!WriteResultFile(ResultFilename, bSuccess, Asset, Error, WriteError))
			{
				bSuccess = false;
				Error = Error.IsEmpty() ? WriteError : Error + TEXT(" ") + WriteError;
			}
		}
		const FString Detail = bSuccess
			? FString::Printf(TEXT("asset=%s bytes=%d sha1=%s"), FixtureObjectPath, Asset->ArchiveByteCount, *Asset->ArchiveSha1)
			: FString::Printf(TEXT("asset=%s error=%s"), FixtureObjectPath, *Error);
		EmitResult(bSuccess, Detail);
		// On Windows this graceful request may not propagate a nonzero status
		// from engine init. The runner must require the marker and JSON result.
		FPlatformMisc::RequestExitWithStatus(false, bSuccess ? 0 : 1, TEXT("ProphecyJoltSmokeHostFixtureValidation"));
	}

	FDelegateHandle PostEngineInitHandle;
};

IMPLEMENT_PRIMARY_GAME_MODULE(FProphecyJoltSmokeHostModule, ProphecyJoltSmokeHost, "ProphecyJoltSmokeHost");
