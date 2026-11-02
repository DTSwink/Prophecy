#pragma once
#include "HAL/Platform.h"

namespace ProphecyFootIKMath
{
// Exact immutable-node portion of slide-entry.create: coordinate descent and
// the subsequent correct() pass. Source sampling, live residual retirement,
// seed selection, output interpolation and diagnostics stay in canonical JS.
// Input is a flat double stream, in this order:
//   quality, nodeCount (25 or 33);
//   hip c1[4],c2[4],sinY,sinZ,twist;
//   knee axisParent[3],idleBend,max,refRelative[4];
//   foot c1[4],c2[4],sinY,sinZ,twist;                         (33 total)
// For each node:
//   u,parentQ[4],hipPoint[3],kneeOffset[3],footOffset[3],
//   hipResidual[4],kneeResidual[4],footResidual[4],
//   wanted[7],initialVariables[7],cornerCount,planeCount;    (42 per node)
//   cornerCount local shoe corners[3];
//   planeCount records: origin[3],u[3],normal[3],v[3],bounds[4],
//                       finiteSlab,thickness.              (18 per plane)
// Surfaces are captured at (node.u,false); their local() must be the canonical
// finite rectangle's dot-product transform. No surface order is changed.
// Output is nodeCount*7 final coordinates, including unchanged endpoints.
// Unsupported dimensions/invalid values fail without publishing output.
PROPHECYFOOTIKMATH_API bool EntrySolve(const double* Input,int Count,double* Output,int OutputCount);
}
