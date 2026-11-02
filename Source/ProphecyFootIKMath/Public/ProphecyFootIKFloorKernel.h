#pragma once
#include "HAL/Platform.h"

namespace ProphecyFootIKMath
{
// Complete LiveTerrain.floorFor query for finite horizontal rectangles.
// Input: tileCount, cornerCount, ankle3; tile records (point3,u3,v3,bounds4);
// then corner offsets3. Corners are ordered groups of eight, matching the
// canonical terrain.js box faces. Tiles and corners retain their input order.
// Supports <=256 tiles and <=64 corners (a multiple of eight). OutputCount
// must equal one. Output[0] is
// the exact ankle floor height, or the supplied ankle Y if no tile overlaps.
// Invalid/unsupported input fails without writing any output; JS remains the
// fallback. Input and output views may alias: publishing happens last.
PROPHECYFOOTIKMATH_API bool TerrainFloor(const double* Input, int Count,
    double* Output, int OutputCount);
// Complete canonical 12-pass hip reach/floor projection. Input has the same
// floor-query layout followed by hip3 and nonnegative reach. OutputCount must
// equal 3. All iterations and arithmetic order are retained; unchanged pure
// floor queries can reuse their value within the call. Invalid/unsupported
// input does not publish a partial result. Input/output views may alias.
PROPHECYFOOTIKMATH_API bool TerrainReach(const double* Input, int Count,
    double* Output, int OutputCount);
// Same tile prefix as TerrainFloor (cornerCount fixed16), then baseFoot3,
// toeLocal3, anatomical side sign, fromFootQ4/fromToeQ4/toFootQ4/toToeQ4,
// floor ceiling, initial amount and mode. Mode0 scans16 samples then bisects9;
// mode1 checks the anticipated amount/zero and bisects16 when required.
// All canonical sample/operation order is retained. OutputCount must equal1;
// failed calls do not publish. Input/output views may alias.
PROPHECYFOOTIKMATH_API bool TerrainRotationClearance(const double* Input,
    int Count, double* Output, int OutputCount);
}
