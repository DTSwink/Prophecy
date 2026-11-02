#pragma once
#include "HAL/Platform.h"

namespace ProphecyFootIKMath
{
// Complete per-leg slide contact selection: lower-contact search, connected
// upward-shift search, and temporal travel limit, including all inner chain /
// shoe / finite-plane fitting. Uses the canonical unprofiled two-box shoe only.
// Input flat stream:
// 0 pelvisQ4,parentHipQ4,hip3,knee3,foot3,toe3,hipQ4,kneeQ4,footQ4,toeQ4 (36);
// 36 reference upper,lower,reach,normal3,upperAxis3,lowerAxis3,hipQ4,kneeQ4,
//    kneeLocal3,ankleLocal3,toeLocal3                                (29);
// 65 hip c1[4],c2[4],sinY,sinZ,twist                               (11);
// 76 knee axisParent3,axisChild3,idleBend,min,max,refRelative4       (13);
// 89 foot c1[4],c2[4],sinY,sinZ,twist,refRelative4                  (15);
//104 toe c1[4],c2[4],sinY,sinZ,twist,refRelative4                   (15);
//119 point3,desiredFootQ4,desiredToeQ4,wantedAxis3,wantedPole3,
//    wallUp3,wallNormal3,targetShift3                              (26);
//145 hasPreviousPole,previousAxis3,previousPole3,hasPreviousDrop,
//    previousDrop,hasLastTravel,lastTravel,dt,sideSign              (13);
//158 activePlane record18,terrainPlaneCount,terrainPlane records18 each.
// Plane: origin3,u3,normal3,v3,bounds4,finiteSlab,thickness.
// Output33: hipQ4,knee3,kneeQ4,foot3,footQ4,toe3,toeQ4,
//           contactDrop,contactTravel,poleAxis3,poleDirection3.
// Unsupported/nonfinite inputs fail without publishing an output. The host
// must retain the original JS path for active custom rig profiles.
PROPHECYFOOTIKMATH_API bool LegContact(const double* Input,int Count,double* Output,int OutputCount);
}
