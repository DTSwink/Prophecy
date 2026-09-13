#include "ProphecyJoltCookFixtureCommandlet.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "HAL/FileManager.h"
#include "Misc/App.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "ProphecyJoltShapeAsset.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UObjectGlobals.h"

DEFINE_LOG_CATEGORY_STATIC(LogProphecyJoltCookFixture, Log, All);

UProphecyJoltCookFixtureCommandlet::UProphecyJoltCookFixtureCommandlet()
{
	IsClient = false;
	IsServer = false;
	IsEditor = true;
	LogToConsole = true;
	ShowErrorCount = true;
}

int32 UProphecyJoltCookFixtureCommandlet::Main(const FString& Params)
{
	if (FCString::Strcmp(FApp::GetProjectName(), TEXT("ProphecyJoltSmokeHost")) != 0)
	{
		UE_LOG(LogProphecyJoltCookFixture, Error, TEXT("Refusing fixture save: this commandlet runs only in ProphecyJoltSmokeHost."));
		return 1;
	}
	constexpr TCHAR PackageName[] = TEXT("/Game/Fixture/DA_CompoundFixture");
	constexpr TCHAR AssetName[] = TEXT("DA_CompoundFixture");
	const FString Filename = FPaths::ConvertRelativePathToFull(FPackageName::LongPackageNameToFilename(PackageName, FPackageName::GetAssetPackageExtension()));
	const FString ContentDirectory = FPaths::ConvertRelativePathToFull(FPaths::ProjectContentDir());
	if (!FPaths::IsUnderDirectory(Filename, ContentDirectory))
	{
		UE_LOG(LogProphecyJoltCookFixture, Error, TEXT("Fixture filename is outside this host's Content directory."));
		return 1;
	}
	const bool bExists = FPackageName::DoesPackageExist(PackageName) || IFileManager::Get().FileExists(*Filename);
	if (bExists && !FParse::Param(*Params, TEXT("OverwriteFixture")))
	{
		UE_LOG(LogProphecyJoltCookFixture, Error, TEXT("Fixture already exists. Refusing overwrite; use -OverwriteFixture only to regenerate this fixture."));
		return 1;
	}

	UProphecyJoltShapeAsset* Source = NewObject<UProphecyJoltShapeAsset>(GetTransientPackage());
	FString Error;
	if (!Source->BuildCompoundFixture(Error) || !Source->ValidateCompoundFixture(Error))
	{
		UE_LOG(LogProphecyJoltCookFixture, Error, TEXT("Fixture creation/validation failed before save: %s"), *Error);
		return 1;
	}
	UPackage* Package = bExists ? LoadPackage(nullptr, PackageName, LOAD_None) : CreatePackage(PackageName);
	if (Package == nullptr)
	{
		UE_LOG(LogProphecyJoltCookFixture, Error, TEXT("Could not create/load the fixed fixture package."));
		return 1;
	}
	if (bExists)
	{
		UObject* Existing = FindObject<UObject>(Package, AssetName);
		if (Existing == nullptr || !Existing->IsA<UProphecyJoltShapeAsset>())
		{
			UE_LOG(LogProphecyJoltCookFixture, Error, TEXT("Existing package does not contain the expected Jolt fixture asset; refusing replacement."));
			return 1;
		}
	}
	UProphecyJoltShapeAsset* Asset = DuplicateObject<UProphecyJoltShapeAsset>(Source, Package, AssetName);
	if (Asset == nullptr || !Asset->ValidateCompoundFixture(Error))
	{
		UE_LOG(LogProphecyJoltCookFixture, Error, TEXT("Destination fixture validation failed before save: %s"), *Error);
		return 1;
	}
	Asset->SetFlags(RF_Public | RF_Standalone);
	Package->MarkPackageDirty();
	if (!bExists)
	{
		FAssetRegistryModule::AssetCreated(Asset);
	}
	if (!IFileManager::Get().MakeDirectory(*FPaths::GetPath(Filename), true))
	{
		UE_LOG(LogProphecyJoltCookFixture, Error, TEXT("Could not create the fixture directory."));
		return 1;
	}
	FSavePackageArgs SaveArgs;
	SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
	SaveArgs.SaveFlags = SAVE_NoError;
	if (!UPackage::SavePackage(Package, Asset, *Filename, SaveArgs))
	{
		UE_LOG(LogProphecyJoltCookFixture, Error, TEXT("Could not save fixture package: %s"), *Filename);
		return 1;
	}
	UE_LOG(LogProphecyJoltCookFixture, Display, TEXT("PROPHECY_JOLT_FIXTURE_SAVED package=%s bytes=%d sha1=%s"), PackageName, Asset->ArchiveByteCount, *Asset->ArchiveSha1);
	return 0;
}
