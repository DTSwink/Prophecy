#include "GameAnimationSample3.h"
#include "Modules/ModuleManager.h"

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
    }
    virtual void ShutdownModule() override
    {
        ProphecyJolt::FightValidation::UnregisterCommandLine();
        FDefaultGameModuleImpl::ShutdownModule();
    }
};

IMPLEMENT_PRIMARY_GAME_MODULE(FProphecyGameModule, GameAnimationSample3, "GameAnimationSample3");
