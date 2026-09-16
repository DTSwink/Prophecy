#include "Engine/CollisionProfile.h"
#include "Editor.h"
#include "HAL/IConsoleManager.h"
#include "Misc/ConfigCacheIni.h"

// Reload project channel labels after editing DefaultEngine.ini without restarting the editor.
static FAutoConsoleCommand ReloadProphecyCollisionChannels(
    TEXT("Prophecy.Collision.ReloadChannels"),TEXT("Reload collision channel configuration outside PIE."),
    FConsoleCommandDelegate::CreateLambda([]
    {
        if (!GEditor || GEditor->PlayWorld) return;
        FConfigCacheIni::LoadGlobalIniFile(GEngineIni,TEXT("Engine"),nullptr,true);
        auto* Profile=UCollisionProfile::Get();
        Profile->ReloadConfig();
        Profile->LoadProfileConfig(true);
        UE_LOG(LogTemp,Display,TEXT("Collision channel 11: %s"),
            *Profile->ReturnChannelNameFromContainerIndex(ECC_GameTraceChannel11).ToString());
    }));
