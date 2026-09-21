#include "GameAnimationSample3.h"
#include "Modules/ModuleManager.h"
#include "Private/ProphecyDebugCameraInput.inl"

namespace ProphecyJolt::DefaultPhysics { void Startup(); void Shutdown(); }

namespace ProphecyJolt::FightValidation
{
    void RegisterCommandLine();
    void UnregisterCommandLine();
}

class FProphecyGameModule : public FDefaultGameModuleImpl
{
    virtual void StartupModule() override
    {
        FDefaultGameModuleImpl::StartupModule();
#if WITH_EDITOR
        ProphecyDebugCameraInput::Startup();
#endif
        ProphecyJolt::FightValidation::RegisterCommandLine();
        ProphecyJolt::DefaultPhysics::Startup();
    }
    virtual void ShutdownModule() override
    {
#if WITH_EDITOR
        ProphecyDebugCameraInput::Shutdown();
#endif
        ProphecyJolt::FightValidation::UnregisterCommandLine();
        ProphecyJolt::DefaultPhysics::Shutdown();
        FDefaultGameModuleImpl::ShutdownModule();
    }
};

IMPLEMENT_PRIMARY_GAME_MODULE(FProphecyGameModule, GameAnimationSample3, "GameAnimationSample3");
