#include "Modules/ModuleManager.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "BumblebeeTestDirector.h"
#include "BirdTestDirector.h"

/** Spawns the headless verification directors only when the game is launched with -BeeTest=<scene> / -BirdTest=<scene>. */
class FProphecyAmbientModule : public IModuleInterface
{
public:
	virtual void StartupModule() override
	{
		FString Scene;
		if (FParse::Value(FCommandLine::Get(), TEXT("BeeTest="), Scene))
		{
			Handle = FWorldDelegates::OnWorldInitializedActors.AddLambda([Scene](const FActorsInitializedParams& Params)
			{
				UWorld* World = Params.World;
				if (!World || !World->IsGameWorld()) return;
				FActorSpawnParameters P;
				P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
				if (ABumblebeeTestDirector* D = World->SpawnActor<ABumblebeeTestDirector>(P))
				{
					D->Scene = Scene;
				}
			});
		}
		FString BirdScene;
		if (FParse::Value(FCommandLine::Get(), TEXT("BirdTest="), BirdScene))
		{
			BirdHandle = FWorldDelegates::OnWorldInitializedActors.AddLambda([BirdScene](const FActorsInitializedParams& Params)
			{
				UWorld* World = Params.World;
				if (!World || !World->IsGameWorld()) return;
				FActorSpawnParameters P;
				P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
				if (ABirdTestDirector* D = World->SpawnActor<ABirdTestDirector>(P))
				{
					D->Scene = BirdScene;
				}
			});
		}
	}

	virtual void ShutdownModule() override
	{
		if (Handle.IsValid()) FWorldDelegates::OnWorldInitializedActors.Remove(Handle);
		if (BirdHandle.IsValid()) FWorldDelegates::OnWorldInitializedActors.Remove(BirdHandle);
	}

private:
	FDelegateHandle Handle;
	FDelegateHandle BirdHandle;
};

IMPLEMENT_MODULE(FProphecyAmbientModule, ProphecyAmbient)
