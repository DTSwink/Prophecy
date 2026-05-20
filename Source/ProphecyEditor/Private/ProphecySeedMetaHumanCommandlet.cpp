#include "ProphecySeedMetaHumanCommandlet.h"

#include "FileHelpers.h"
#include "ImageCore.h"
#include "MetaHumanCharacter.h"
#include "MetaHumanCharacterEditorSubsystem.h"
#include "MetaHumanCharacterPaletteProjectSettings.h"
#include "MetaHumanCollectionPipeline.h"
#include "MetaHumanDefaultEditorPipelineBase.h"
#include "Subsystem/MetaHumanCharacterBuild.h"
#include "Engine/Texture2D.h"
#include "UObject/Package.h"

namespace
{
FImage MakeFlatImage(const FColor& Color, int32 Size, EGammaSpace GammaSpace)
{
	FImage Image;
	Image.Init(Size, Size, ERawImageFormat::BGRA8, GammaSpace);

	for (int32 Y = 0; Y < Size; ++Y)
	{
		for (int32 X = 0; X < Size; ++X)
		{
			*static_cast<FColor*>(Image.GetPixelPointer(X, Y)) = Color;
		}
	}

	return Image;
}

FColor PlaceholderSkinColor()
{
	return FColor(154, 111, 82, 255);
}

FColor FaceColor(EFaceTextureType TextureType)
{
	switch (TextureType)
	{
	case EFaceTextureType::Basecolor:
		return PlaceholderSkinColor();
	case EFaceTextureType::Basecolor_Animated_CM1:
	case EFaceTextureType::Basecolor_Animated_CM2:
	case EFaceTextureType::Basecolor_Animated_CM3:
		return FColor(128, 128, 128, 255);
	case EFaceTextureType::Normal:
	case EFaceTextureType::Normal_Animated_WM1:
	case EFaceTextureType::Normal_Animated_WM2:
	case EFaceTextureType::Normal_Animated_WM3:
		return FColor(128, 128, 255, 255);
	case EFaceTextureType::Cavity:
		return FColor(210, 210, 210, 255);
	default:
		return FColor::White;
	}
}

FColor BodyColor(EBodyTextureType TextureType)
{
	switch (TextureType)
	{
	case EBodyTextureType::Body_Basecolor:
	case EBodyTextureType::Chest_Basecolor:
		return PlaceholderSkinColor();
	case EBodyTextureType::Body_Underwear_Basecolor:
	case EBodyTextureType::Chest_Underwear_Basecolor:
		return FColor(70, 66, 62, 255);
	case EBodyTextureType::Body_Normal:
	case EBodyTextureType::Chest_Normal:
	case EBodyTextureType::Body_Underwear_Normal:
	case EBodyTextureType::Chest_Underwear_Normal:
		return FColor(128, 128, 255, 255);
	case EBodyTextureType::Body_Cavity:
	case EBodyTextureType::Chest_Cavity:
		return FColor(210, 210, 210, 255);
	case EBodyTextureType::Body_Underwear_Mask:
		return FColor(255, 255, 255, 255);
	default:
		return FColor::White;
	}
}

int32 FaceTextureSize(EFaceTextureType TextureType)
{
	switch (TextureType)
	{
	case EFaceTextureType::Basecolor:
	case EFaceTextureType::Normal:
	case EFaceTextureType::Cavity:
		return 1024;
	default:
		return 512;
	}
}

int32 BodyTextureSize(EBodyTextureType TextureType)
{
	switch (TextureType)
	{
	case EBodyTextureType::Body_Basecolor:
	case EBodyTextureType::Body_Normal:
	case EBodyTextureType::Body_Cavity:
	case EBodyTextureType::Chest_Basecolor:
	case EBodyTextureType::Chest_Normal:
	case EBodyTextureType::Chest_Cavity:
		return 1024;
	default:
		return 512;
	}
}

EGammaSpace TextureGamma(EFaceTextureType TextureType)
{
	return TextureType == EFaceTextureType::Basecolor ? EGammaSpace::sRGB : EGammaSpace::Linear;
}

EGammaSpace TextureGamma(EBodyTextureType TextureType)
{
	return (TextureType == EBodyTextureType::Body_Basecolor
		|| TextureType == EBodyTextureType::Chest_Basecolor
		|| TextureType == EBodyTextureType::Body_Underwear_Basecolor
		|| TextureType == EBodyTextureType::Chest_Underwear_Basecolor)
		? EGammaSpace::sRGB
		: EGammaSpace::Linear;
}

void SeedPlaceholderTextures(UMetaHumanCharacter* Character)
{
	Character->Modify();

	for (EFaceTextureType TextureType : TEnumRange<EFaceTextureType>())
	{
		Character->StoreSynthesizedFaceTexture(
			TextureType,
			MakeFlatImage(FaceColor(TextureType), FaceTextureSize(TextureType), TextureGamma(TextureType)));
	}

	for (EBodyTextureType TextureType : TEnumRange<EBodyTextureType>())
	{
		Character->StoreHighResBodyTexture(
			TextureType,
			MakeFlatImage(BodyColor(TextureType), BodyTextureSize(TextureType), TextureGamma(TextureType)));
	}

	Character->SetHasHighResolutionTextures(true);
	Character->MarkPackageDirty();
}

void SaveCharacter(UMetaHumanCharacter* Character)
{
	TArray<UPackage*> PackagesToSave;
	PackagesToSave.Add(Character->GetOutermost());
	UEditorLoadingAndSavingUtils::SavePackages(PackagesToSave, false);
}

bool PatchFlatTexture(const TCHAR* TexturePath, const FColor& Color, int32 Size)
{
	UTexture2D* Texture = LoadObject<UTexture2D>(nullptr, TexturePath);
	if (!Texture)
	{
		UE_LOG(LogTemp, Error, TEXT("[ProphecyMetaHuman] Could not load texture '%s'"), TexturePath);
		return false;
	}

	TArray<uint8> Pixels;
	Pixels.SetNumUninitialized(Size * Size * sizeof(FColor));
	for (int32 PixelIndex = 0; PixelIndex < Size * Size; ++PixelIndex)
	{
		FMemory::Memcpy(Pixels.GetData() + PixelIndex * sizeof(FColor), &Color, sizeof(FColor));
	}

	Texture->Modify();
	Texture->Source.Init(Size, Size, 1, 1, TSF_BGRA8, Pixels.GetData());
	Texture->SRGB = true;
	Texture->VirtualTextureStreaming = true;
	Texture->CompressionSettings = TC_Default;
	Texture->LODGroup = TEXTUREGROUP_Character;
	Texture->PostEditChange();
	Texture->MarkPackageDirty();

	UE_LOG(LogTemp, Display, TEXT("[ProphecyMetaHuman] Patched %s color=(%d,%d,%d) SRGB=true VT=true"),
		TexturePath, Color.R, Color.G, Color.B);
	return true;
}

bool PatchBuiltPlaceholderSkinTextures()
{
	constexpr int32 BasecolorSize = 1024;
	bool bPatched = true;
	bPatched &= PatchFlatTexture(
		TEXT("/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor"),
		PlaceholderSkinColor(),
		BasecolorSize);
	bPatched &= PatchFlatTexture(
		TEXT("/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Basecolor"),
		PlaceholderSkinColor(),
		BasecolorSize);

	const bool bSaved = UEditorLoadingAndSavingUtils::SaveDirtyPackages(false, true);
	UE_LOG(LogTemp, Display, TEXT("[ProphecyMetaHuman] Saved patched skin textures=%s"),
		bSaved ? TEXT("true") : TEXT("false"));

	return bPatched && bSaved;
}
}

UProphecySeedMetaHumanCommandlet::UProphecySeedMetaHumanCommandlet()
{
	IsClient = false;
	IsEditor = true;
	IsServer = false;
	LogToConsole = true;
}

int32 UProphecySeedMetaHumanCommandlet::Main(const FString& Params)
{
	FString CharacterPath = TEXT("/Game/Prophecy/MetaHumanPipeline/MHC_ProphecyPlaceholder");
	FString BuildRoot = TEXT("/Game/Prophecy/MetaHumans");
	FString CommonRoot = TEXT("/Game/Prophecy/MetaHumans/Common");
	FString NameOverride = TEXT("ProphecyPlaceholder");

	FParse::Value(*Params, TEXT("Character="), CharacterPath);
	FParse::Value(*Params, TEXT("BuildRoot="), BuildRoot);
	FParse::Value(*Params, TEXT("CommonRoot="), CommonRoot);
	FParse::Value(*Params, TEXT("NameOverride="), NameOverride);
	const bool bBuild = FParse::Param(*Params, TEXT("Build"));
	if (FParse::Param(*Params, TEXT("PatchBuiltTextures")))
	{
		return PatchBuiltPlaceholderSkinTextures() ? 0 : 1;
	}

	UE_LOG(LogTemp, Display, TEXT("[ProphecyMetaHuman] Loading %s"), *CharacterPath);
	UMetaHumanCharacter* Character = LoadObject<UMetaHumanCharacter>(nullptr, *CharacterPath);
	if (!Character)
	{
		UE_LOG(LogTemp, Error, TEXT("[ProphecyMetaHuman] Could not load MetaHuman Character '%s'"), *CharacterPath);
		return 1;
	}

	SeedPlaceholderTextures(Character);
	SaveCharacter(Character);

	UMetaHumanCharacterEditorSubsystem* Subsystem = GEditor->GetEditorSubsystem<UMetaHumanCharacterEditorSubsystem>();
	if (!Subsystem)
	{
		UE_LOG(LogTemp, Error, TEXT("[ProphecyMetaHuman] MetaHumanCharacterEditorSubsystem unavailable"));
		return 1;
	}

	const bool bAdded = Subsystem->TryAddObjectToEdit(Character);
	UE_LOG(LogTemp, Display, TEXT("[ProphecyMetaHuman] TryAddObjectToEdit=%s"), bAdded ? TEXT("true") : TEXT("false"));
	UE_LOG(LogTemp, Display, TEXT("[ProphecyMetaHuman] HasFaceDNA=%s HasHighResolutionTextures=%s"),
		Character->HasFaceDNA() ? TEXT("true") : TEXT("false"),
		Character->HasHighResolutionTextures() ? TEXT("true") : TEXT("false"));

	if (!Subsystem->CanBuildMetaHuman(Character, true))
	{
		UE_LOG(LogTemp, Error, TEXT("[ProphecyMetaHuman] Character is still not buildable after seeding placeholder textures"));
		return 1;
	}

	if (bBuild)
	{
		FMetaHumanCharacterEditorBuildParameters BuildParameters;
		BuildParameters.PipelineType = EMetaHumanDefaultPipelineType::Optimized;
		BuildParameters.PipelineQuality = EMetaHumanQualityLevel::High;
		BuildParameters.AnimationSystemName = FName(TEXT("AnimBP"));
		BuildParameters.AbsoluteBuildPath = BuildRoot;
		BuildParameters.CommonFolderPath = CommonRoot;
		BuildParameters.NameOverride = NameOverride;

		TSoftClassPtr<UMetaHumanCollectionPipeline> PipelineClass;
		if (const UMetaHumanCharacterPaletteProjectSettings* Settings = GetDefault<UMetaHumanCharacterPaletteProjectSettings>())
		{
			if (const TSoftClassPtr<UMetaHumanCollectionPipeline>* FoundPipeline =
				Settings->DefaultCharacterLegacyPipelines.Find(BuildParameters.PipelineQuality))
			{
				PipelineClass = *FoundPipeline;
			}
		}

		if (!PipelineClass.IsNull())
		{
			if (UClass* LoadedPipelineClass = PipelineClass.LoadSynchronous())
			{
				BuildParameters.PipelineOverride = NewObject<UMetaHumanCollectionPipeline>(Character, LoadedPipelineClass);
				if (BuildParameters.PipelineOverride)
				{
					if (UMetaHumanDefaultEditorPipelineBase* DefaultEditorPipeline =
						Cast<UMetaHumanDefaultEditorPipelineBase>(BuildParameters.PipelineOverride->GetMutableEditorPipeline()))
					{
						DefaultEditorPipeline->bBakeMaterials = false;
						DefaultEditorPipeline->HairProperties.bUsePreBakedGrooms = false;
						UE_LOG(LogTemp, Display, TEXT("[ProphecyMetaHuman] Disabled material and groom texture baking for placeholder assembly"));
					}
				}
			}
		}

		UE_LOG(LogTemp, Display, TEXT("[ProphecyMetaHuman] Building optimized MetaHuman to %s"), *BuildRoot);
		Subsystem->BuildMetaHuman(Character, BuildParameters);

		const bool bSavedGeneratedPackages = UEditorLoadingAndSavingUtils::SaveDirtyPackages(false, true);
		UE_LOG(LogTemp, Display, TEXT("[ProphecyMetaHuman] Saved generated content packages=%s"),
			bSavedGeneratedPackages ? TEXT("true") : TEXT("false"));
	}

	SaveCharacter(Character);
	UE_LOG(LogTemp, Display, TEXT("[ProphecyMetaHuman] DONE"));
	return 0;
}
