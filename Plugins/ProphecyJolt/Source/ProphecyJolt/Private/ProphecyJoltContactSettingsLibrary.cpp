#include "ProphecyJoltContactSettingsLibrary.h"
#include "ProphecyJoltWorldSubsystem.h"

bool UProphecyJoltContactSettingsLibrary::SetJoltPenetrationSlop(const UObject* Context, float SlopCm)
{
    return UProphecyJoltWorldSubsystem::SetJoltPenetrationSlop(Context, SlopCm);
}

float UProphecyJoltContactSettingsLibrary::GetJoltPenetrationSlop(const UObject* Context)
{
    return UProphecyJoltWorldSubsystem::GetJoltPenetrationSlop(Context);
}
