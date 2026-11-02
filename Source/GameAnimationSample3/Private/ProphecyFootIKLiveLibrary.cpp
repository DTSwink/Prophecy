#include "ProphecyFootIKLiveLibrary.h"
#include "ProphecyFootIKLive.h"
bool UProphecyFootIKLiveLibrary::SetFootIKEnabled(AProphecyAgent* A,bool Enabled,FString& Error)
{return ProphecyFootIKLive::Enable(A,Enabled,Error);}
bool UProphecyFootIKLiveLibrary::ConfigureLiveFootIK(AProphecyAgent* A,const FString& Settings,FString& Error)
{return ProphecyFootIKLive::Configure(A,Settings,Error);}
bool UProphecyFootIKLiveLibrary::GetLiveFootIKState(AProphecyAgent* A,FProphecyFootIKLiveState& State)
{return ProphecyFootIKLive::Status(A,State);}
