#pragma once
#include "CoreMinimal.h"

// Runtime-generated presentation cache. Source simulation remains continuous
// at240Hz; each60Hz result is evaluated exactly, never resampled from a bake.
class FProphecyBodyflipPlanner
{
public:
    FProphecyBodyflipPlanner();
    ~FProphecyBodyflipPlanner();
    bool Prepare(const FString& SettingsJson,const FString& RunJson,double Horizon,bool Reset,FString& Error,const FString& RigProfileJson=FString());
    bool Poll(FString& Error);
    bool Busy() const;
    bool Frame(int32 Index,FString& Out) const;
    double LastSeconds() const;
private:
    struct FImpl;
    TUniquePtr<FImpl> Impl;
};
