#pragma once
#include "CoreMinimal.h"
#include "ProphecyJoltWorldSubsystem.h"
struct FProphecyOilSettings;
struct FProphecyOilCoverageStamp;
namespace ProphecyOilCoverage
{
TSharedPtr<FProphecyOilCoverageStamp> Add(UWorld* World,const FProphecyJoltBodyHandle& Body,const FVector& Point,const FVector& Normal,float Radius,bool Moving,bool Landing,const FProphecyOilSettings& Settings);
void Tick(UWorld* World);
float Amount(const TSharedPtr<FProphecyOilCoverageStamp>& Stamp);
void Remove(UWorld* World,const TSharedPtr<FProphecyOilCoverageStamp>& Stamp);
#if !UE_BUILD_SHIPPING
struct FStats {int32 Groups=0,Stamps=0,Rebuilds=0;double RasterMs=0;};
FStats Stats(UWorld* World);
#endif
}
