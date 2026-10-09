#pragma once
#include "CoreMinimal.h"
#include "DrawDebugHelpers.h"
#include "PhysicsEngine/AggregateGeom.h"
#include "Chaos/Convex.h"

#if !UE_BUILD_SHIPPING
namespace ProphecyGhostDrawing
{
inline void DrawShapes(UWorld* World,const FKAggregateGeom& Geometry,const FTransform& Body,
    FColor Color,float Duration,float Thickness)
{
    for (const auto& Box:Geometry.BoxElems)
    {
        const FTransform T=Box.GetTransform()*Body;
        DrawDebugBox(World,T.GetLocation(),FVector(Box.X,Box.Y,Box.Z)*0.5*T.GetScale3D().GetAbs(),T.GetRotation(),Color,false,Duration,0,Thickness);
    }
    for (const auto& Sphere:Geometry.SphereElems)
        DrawDebugSphere(World,Body.TransformPosition(Sphere.Center),Sphere.Radius*Body.GetScale3D().GetAbsMax(),16,Color,false,Duration,0,Thickness);
    for (const auto& Capsule:Geometry.SphylElems)
    {
        const FTransform T=Capsule.GetTransform()*Body;
        const FVector Scale=T.GetScale3D().GetAbs();
        const float Radius=Capsule.Radius*FMath::Max(Scale.X,Scale.Y);
        DrawDebugCapsule(World,T.GetLocation(),0.5f*Capsule.Length*Scale.Z+Radius,Radius,T.GetRotation(),Color,false,Duration,0,Thickness);
    }
    for (const auto& Convex:Geometry.ConvexElems)
    {
        const FTransform T=Convex.GetTransform()*Body;
        if (const auto* Hull=Convex.GetChaosConvexMesh().GetReference())
        {
            // Cooked collision topology remains available even when editable triangle
            // indices were discarded (for example after rebuilding the sword hull).
            for (int32 Face=0;Face<Hull->NumPlanes();++Face)
            {
                const int32 Count=Hull->NumPlaneVertices(Face);
                for (int32 Edge=0;Edge<Count;++Edge)
                {
                    const FVector A(Hull->GetVertex(Hull->GetPlaneVertex(Face,Edge)));
                    const FVector B(Hull->GetVertex(Hull->GetPlaneVertex(Face,(Edge+1)%Count)));
                    DrawDebugLine(World,T.TransformPosition(A),T.TransformPosition(B),Color,false,Duration,0,Thickness);
                }
            }
            continue;
        }
        for (int32 I=0;I+2<Convex.IndexData.Num();I+=3) for (int32 Edge=0;Edge<3;++Edge)
        {
            const int32 A=Convex.IndexData[I+Edge],B=Convex.IndexData[I+(Edge+1)%3];
            if (Convex.VertexData.IsValidIndex(A) && Convex.VertexData.IsValidIndex(B))
                DrawDebugLine(World,T.TransformPosition(Convex.VertexData[A]),T.TransformPosition(Convex.VertexData[B]),Color,false,Duration,0,Thickness);
        }
    }
}
}
#endif
