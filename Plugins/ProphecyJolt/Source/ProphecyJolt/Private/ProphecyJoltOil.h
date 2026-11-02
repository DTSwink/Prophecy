#pragma once
#include "CoreMinimal.h"
#include <Jolt/Jolt.h>
#include <Jolt/Physics/Body/Body.h>
#include <Jolt/Physics/Collision/ContactListener.h>

// Written only between synchronous updates; contact workers read immutable POD.
namespace ProphecyJolt::Oil
{
constexpr float CellCm = 200.f;
constexpr int32 MaxPatches = 4096;
struct FPatch
{
    uint32 Body = 0;
    FVector Center, Normal;
    float Radius = 100, Strength = 1;
    TArray<FIntVector> Cells;
};
struct FSurface { TMap<FIntVector,TArray<uint64>> Cells; };
struct FRegistry
{
    TMap<uint64,FPatch> Patches;
    TMap<uint32,FSurface> Surfaces;
    uint64 NextId = 1;
    static FIntVector Cell(const FVector& P)
    { return FIntVector(FMath::FloorToInt(P.X/CellCm),FMath::FloorToInt(P.Y/CellCm),FMath::FloorToInt(P.Z/CellCm)); }
    uint64 Add(uint32 Body,const FVector& Center,const FVector& Normal,float Radius,float Strength)
    {
        const uint64 Id=NextId++;
        FPatch P;P.Body=Body;P.Center=Center;P.Normal=Normal;P.Radius=Radius;P.Strength=Strength;
        // Conservative sphere bounds include the surface depth band.
        const FIntVector Lo=Cell(Center-FVector(Radius+8)),Hi=Cell(Center+FVector(Radius+8));
        auto& Surface=Surfaces.FindOrAdd(Body);
        for(int32 X=Lo.X;X<=Hi.X;++X)for(int32 Y=Lo.Y;Y<=Hi.Y;++Y)for(int32 Z=Lo.Z;Z<=Hi.Z;++Z)
        {const FIntVector C(X,Y,Z);P.Cells.Add(C);Surface.Cells.FindOrAdd(C).Add(Id);}
        Patches.Add(Id,MoveTemp(P));return Id;
    }
    bool Remove(uint64 Id)
    {
        const auto* P=Patches.Find(Id);if(!P)return false;
        if(auto* S=Surfaces.Find(P->Body))
        {
            for(const auto& C:P->Cells)if(auto* Bucket=S->Cells.Find(C))
            {Bucket->RemoveSingleSwap(Id);if(Bucket->IsEmpty())S->Cells.Remove(C);}
            if(S->Cells.IsEmpty())Surfaces.Remove(P->Body);
        }
        Patches.Remove(Id);return true;
    }
    void Forget(uint32 Body)
    {
        if(!Surfaces.Contains(Body))return;
        TArray<uint64> Gone;for(const auto& P:Patches)if(P.Value.Body==Body)Gone.Add(P.Key);
        for(uint64 Id:Gone)Remove(Id);
    }
    float Coverage(uint32 Body,const FVector& Point,const FVector& Normal) const
    {
        const auto* S=Surfaces.Find(Body);if(!S)return 0;
        const auto* Bucket=S->Cells.Find(Cell(Point));if(!Bucket)return 0;
        float Result=0;
        for(uint64 Id:*Bucket)
        {
            const auto& P=Patches.FindChecked(Id);
            if(P.Strength<=Result || FVector::DotProduct(P.Normal,Normal)<.65)continue;
            const FVector D=Point-P.Center;const double Height=FVector::DotProduct(D,P.Normal);
            if(FMath::Abs(Height)>8.)continue;
            const double R2=FMath::Max(0.,D.SizeSquared()-Height*Height)/(P.Radius*P.Radius);
            // Same five-percent rim as the placeholder decal material.
            const float Mask=FMath::Clamp(float((1.-FMath::Sqrt(R2))/.05),0.f,1.f);
            Result=FMath::Max(Result,Mask*P.Strength);if(Result>=1.f)return 1.f;
        }
        return Result;
    }
    float OnSurface(const JPH::Body& B,const JPH::ContactManifold& M,bool First) const
    {
        const uint32 Id=B.GetID().GetIndexAndSequenceNumber();if(!Surfaces.Contains(Id))return 0;
        const auto Inv=B.GetWorldTransform().InversedRotationTranslation();
        const auto N=Inv.Multiply3x3(First?M.mWorldSpaceNormal:-M.mWorldSpaceNormal);
        const FVector Normal(N.GetX(),N.GetY(),N.GetZ());
        const uint32 Count=M.mRelativeContactPointsOn1.size();float Sum=0;
        for(uint32 I=0;I<Count;++I)
        {
            const auto P=Inv*(First?M.GetWorldSpaceContactPointOn1(I):M.GetWorldSpaceContactPointOn2(I));
            Sum+=Coverage(Id,FVector(P.GetX(),P.GetY(),P.GetZ())*100.,Normal);
        }
        return Count?Sum/Count:0;
    }
    void Apply(const JPH::Body& A,const JPH::Body& B,const JPH::ContactManifold& M,JPH::ContactSettings& S) const
    {
        if(Patches.IsEmpty())return;
        S.mCombinedFriction*=1.f-FMath::Max(OnSurface(A,M,true),OnSurface(B,M,false));
    }
};
}
