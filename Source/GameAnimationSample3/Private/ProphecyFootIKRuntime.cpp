#include "ProphecyFootIKRuntime.h"

bool FProphecyFootIKRuntime::Enable(const FString& InitJson,FNN Generator,FString& Result,FString& Error)
{
    if(VM){Error=TEXT("Foot IK is already enabled for this owner");return false;}
    auto Candidate=MakeUnique<FProphecyFootIKVM>();
    if(!Candidate->Initialize(MoveTemp(Generator),Error)||!Candidate->Command(InitJson,Result,Error))return false;
    VM=MoveTemp(Candidate);Commands=1;return true;
}
bool FProphecyFootIKRuntime::EnablePrepared(TUniquePtr<FProphecyFootIKVM> Prepared,const FString& InitJson,FString& Result,FString& Error)
{
    if(VM||!Prepared){Error=TEXT("Foot IK prepared runtime cannot be activated");return false;}
    VM=MoveTemp(Prepared);Commands=1;
    return VM->Command(InitJson,Result,Error);
}
TUniquePtr<FProphecyFootIKVM> FProphecyFootIKRuntime::ReleaseVM(){Commands=0;return MoveTemp(VM);}
bool FProphecyFootIKRuntime::Step(const FString& TickJson,FString& Result,FString& Error)
{return Command(TickJson,Result,Error);}
bool FProphecyFootIKRuntime::Command(const FString& Json,FString& Result,FString& Error)
{
    if(!VM){Error=TEXT("Foot IK is disabled");return false;}
    ++Commands;return VM->Command(Json,Result,Error);
}
void FProphecyFootIKRuntime::Disable(){VM.Reset();}
double FProphecyFootIKRuntime::LastSeconds() const{return VM?VM->LastSeconds():0.;}
