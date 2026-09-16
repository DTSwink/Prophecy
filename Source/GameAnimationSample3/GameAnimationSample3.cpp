#include "GameAnimationSample3.h"
#include "Modules/ModuleManager.h"

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
        ProphecyJolt::FightValidation::RegisterCommandLine();
        ProphecyJolt::DefaultPhysics::Startup();
    }
    virtual void ShutdownModule() override
    {
        ProphecyJolt::FightValidation::UnregisterCommandLine();
        ProphecyJolt::DefaultPhysics::Shutdown();
        FDefaultGameModuleImpl::ShutdownModule();
    }
};

IMPLEMENT_PRIMARY_GAME_MODULE(FProphecyGameModule, GameAnimationSample3, "GameAnimationSample3");
