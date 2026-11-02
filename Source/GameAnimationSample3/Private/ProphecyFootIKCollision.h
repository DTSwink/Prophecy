#pragma once
#include "CoreMinimal.h"

namespace ProphecyFootIKCollision
{
// Recover an actual rectangular convex collider. This accepts rotated vertex
// data and duplicate cooked vertices, but never replaces a wedge or general
// convex hull with its bounding box. Transform/extent are in vertex space.
inline bool ConvexBox(TConstArrayView<FVector> Vertices,FTransform& Transform,FVector& Extent)
{
    if(Vertices.Num()<8||Vertices.Num()>64)return false;
    constexpr double Tolerance=1.e-5; // centimetres, below collision precision
    TArray<FVector,TInlineAllocator<8>> Points;
    for(const FVector& V:Vertices)
    {
        if(V.ContainsNaN())return false;
        bool Duplicate=false;for(const auto& P:Points)if(V.Equals(P,Tolerance)){Duplicate=true;break;}
        if(!Duplicate){if(Points.Num()==8)return false;Points.Add(V);}
    }
    if(Points.Num()!=8)return false;
    // At most35 triples; every accepted triple must reconstruct every actual
    // vertex bijectively. The test therefore cannot accept an AABB approximation.
    const FVector Corner=Points[0];
    for(int32 I=1;I<6;++I)for(int32 J=I+1;J<7;++J)for(int32 K=J+1;K<8;++K)
    {
        FVector E[3]={Points[I]-Corner,Points[J]-Corner,Points[K]-Corner};
        const FVector Lengths(E[0].Size(),E[1].Size(),E[2].Size());if(Lengths.GetMin()<=Tolerance)continue;
        FVector A[3]={E[0]/Lengths.X,E[1]/Lengths.Y,E[2]/Lengths.Z};
        if(FMath::Abs(FVector::DotProduct(A[0],A[1]))>1.e-8||FMath::Abs(FVector::DotProduct(A[0],A[2]))>1.e-8||FMath::Abs(FVector::DotProduct(A[1],A[2]))>1.e-8)continue;
        uint32 Matched=0;bool Complete=true;
        for(int32 C=0;C<8;++C)
        {
            const FVector V=Corner+((C&1)?E[0]:FVector::ZeroVector)+((C&2)?E[1]:FVector::ZeroVector)+((C&4)?E[2]:FVector::ZeroVector);
            int32 Match=INDEX_NONE;for(int32 P=0;P<8;++P)if(!(Matched&(1u<<P))&&V.Equals(Points[P],Tolerance)){Match=P;break;}
            if(Match==INDEX_NONE){Complete=false;break;}Matched|=1u<<Match;
        }
        if(!Complete)continue;
        if(FVector::DotProduct(FVector::CrossProduct(A[0],A[1]),A[2])<0){Swap(A[1],A[2]);Swap(E[1],E[2]);}
        FMatrix Basis=FMatrix::Identity;Basis.SetAxes(&A[0],&A[1],&A[2]);
        Transform=FTransform(FQuat(Basis).GetNormalized(),Corner+(E[0]+E[1]+E[2])*.5);
        Extent=FVector(E[0].Size(),E[1].Size(),E[2].Size())*.5;return true;
    }
    return false;
}
}
