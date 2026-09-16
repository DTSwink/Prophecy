#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;

namespace ProphecyUpperRootHorizon
{
// Configuration lookup is used at registration/setter time, never in the NN tick.
float Configured(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);

// The 35-value copied upper root feature block: three current velocity values,
// then eight (position x, position z, relative yaw cosine, relative yaw sine) records.
inline void Resample(float* RootFeatures, float Horizon)
{
    if (Horizon == 1.0f) return; // Preserve original bits, including unnormalized input pairs.
    if (Horizon == 0.0f)
    {
        for (int32 I = 0; I < 8; ++I) { RootFeatures[5 + 4*I] = 1.0f; RootFeatures[6 + 4*I] = 0.0f; }
        return;
    }
    double Angles[9] = {0.0};
    double PreviousRaw = 0.0;
    for (int32 I = 0; I < 8; ++I)
    {
        const double Raw = FMath::Atan2(double(RootFeatures[6 + 4*I]), double(RootFeatures[5 + 4*I]));
        Angles[I+1] = Angles[I] + FMath::FindDeltaAngleRadians(PreviousRaw, Raw);
        PreviousRaw = Raw;
    }
    for (int32 I = 0; I < 8; ++I)
    {
        const double Sample = double(I+1) * Horizon;
        const int32 Lower = FMath::FloorToInt(Sample);
        const double Yaw = FMath::Lerp(Angles[Lower], Angles[FMath::Min(Lower+1, 8)], Sample-Lower);
        RootFeatures[5 + 4*I] = float(FMath::Cos(Yaw));
        RootFeatures[6 + 4*I] = float(FMath::Sin(Yaw));
    }
}
}
