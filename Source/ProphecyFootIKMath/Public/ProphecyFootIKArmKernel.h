#pragma once
#include "HAL/Platform.h"

namespace ProphecyFootIKMath
{
// Complete slide-arms brace selection, including the iterative constrained palm
// fit, reach bisection and wrist-tilt alternatives. One call per arm/tick.
// Input96 doubles:
//  0 shoulder3,3 elbow3,6 wrist3,9 parentQ4,13 upperQ4,17 lowerQ4,21 handQ4;
// 25 shoulder.c1[4],29 c2[4],33 sinY,34 sinZ,35 twist;
// 36 elbow.axisParent3,39 idleBend,40 min,41 max,42 refRelative4;
// 46 wrist.c1[4],50 c2[4],54 sinY,55 sinZ,56 twist,57 refRelative4;
// 61 basisToBody4,65 forearmDirection3;
// 68 nearest3,71 requestedPoint3,74 normal3,77 wallUp3,80 shoulderOut3;
// 83 sign,84 reach,85 desiredHandQ4,89 hasPrior,90 braceAxis3,93 bracePole3.
// Output34 doubles: local upper/lower/wrist q (12), world q (12),
// elbow3,wrist3,selected contact point3,full palm gap1.
// Arithmetic follows the accepted JS operation order and V8 scalar math.
// Nonfinite/invalid input returns false without publishing output.
PROPHECYFOOTIKMATH_API bool ArmFit(const double* Input,int Count,double* Output,int OutputCount);
}
