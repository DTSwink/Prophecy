#include "Modules/ModuleManager.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "BumblebeeTestDirector.h"

/** Spawns the headless verification director only when the game is launched with -BeeTest=<scene>. */
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
	}

	virtual void ShutdownModule() override
	{
		if (Handle.IsValid()) FWorldDelegates::OnWorldInitializedActors.Remove(Handle);
	}

private:
	FDelegateHandle Handle;
};

IMPLEMENT_MODULE(FProphecyAmbientModule, ProphecyAmbient)
