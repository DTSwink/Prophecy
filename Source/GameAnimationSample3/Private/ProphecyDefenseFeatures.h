#pragma once
#include "CoreMinimal.h"

// These recurrent features have a saved float32 arithmetic contract. The game
// module's /fp:fast otherwise rewrites division and reassociates reductions.
#if defined(_MSC_VER)
#pragma float_control(precise, on, push)
#endif

// Training-space float32, metres, Y-up, row bases. No UE retarget conversion or
// basis cleanup belongs in this causal input encoder.
namespace ProphecyDefenseFeatures
{
struct FRows { FVector3f V[3]; };
inline FVector3f Read(const float* P) { return {P[0],P[1],P[2]}; }
inline void Write(float* P,const FVector3f& V) { P[0]=V.X;P[1]=V.Y;P[2]=V.Z; }
inline FRows Rows(const float* P) { return {{Read(P),Read(P+3),Read(P+6)}}; }
inline FVector3f InTransposedBasis(const FVector3f& V,const FRows& R)
{ return {FVector3f::DotProduct(V,R.V[0]),FVector3f::DotProduct(V,R.V[1]),FVector3f::DotProduct(V,R.V[2])}; }
inline FVector3f Transform(const FVector3f& V,const FRows& R)
{ return V.X*R.V[0]+V.Y*R.V[1]+V.Z*R.V[2]; }
inline FVector3f Normalize(const FVector3f& V)
{
    const float Length=FMath::Max(FMath::Sqrt(V.SizeSquared()),1.e-8f);
    // The reference divides each tensor element by the norm. TVector's scalar
    // division instead rounds a reciprocal then multiplies; repeated cleanup
    // feeds that extra rounding back into the next policy's velocity features.
    return {V.X/Length,V.Y/Length,V.Z/Length};
}
inline FRows Rot6(const float* P)
{
    const FVector3f A=Read(P),B=Read(P+3);
    const FVector3f X=A.SizeSquared()>1.e-16f?Normalize(A):FVector3f(1,0,0);
    FVector3f Y=B-FVector3f::DotProduct(X,B)*X;
    if (Y.SizeSquared()<=1.e-16f)
    {
        int32 Axis=0;
        if (FMath::Abs(X.Y)<FMath::Abs(X.X)) Axis=1;
        if (FMath::Abs(X.Z)<FMath::Abs(X[Axis])) Axis=2;
        FVector3f Basis=FVector3f::ZeroVector;Basis[Axis]=1;
        Y=Basis-FVector3f::DotProduct(X,Basis)*X;
    }
    Y=Normalize(Y);
    return {{X,Y,FVector3f::CrossProduct(X,Y)}};
}
inline void Clean6(float* P)
{ const auto R=Rot6(P);Write(P,R.V[0]);Write(P+3,R.V[1]); }
inline void CleanUpper(float* P)
{
    for (int32 I=0;I<60;I+=6) Clean6(P+I);
    for (int32 I:{63,69,78,84}) Clean6(P+I);
}
inline void CarryUpper(const float* Current,const float* CurrentBaseline,const float* NextBaseline,float* Out)
{
    for (int32 I=0;I<90;++I) Out[I]=NextBaseline[I]+(Current[I]-CurrentBaseline[I]);
    CleanUpper(Out);
}
inline void Rebase6(float* P,const FRows& From,const FRows& To)
{
    const auto R=Rot6(P);
    Write(P,InTransposedBasis(Transform(R.V[0],From),To));
    Write(P+3,InTransposedBasis(Transform(R.V[1],From),To));
}
inline void RebasePosition(float* P,const FVector3f& FromP,const FRows& From,const FVector3f& ToP,const FRows& To)
{ Write(P,InTransposedBasis(Transform(Read(P),From)+FromP-ToP,To)); }
inline void RebaseUpper(const float* Input,float* Out,const FVector3f& FromP,const FRows& From,const FVector3f& ToP,const FRows& To)
{
    if (Input!=Out) FMemory::Memcpy(Out,Input,90*sizeof(float));
    for (int32 I=0;I<60;I+=6) Clean6(Out+I);
    for (int32 I:{60,75})
    {
        RebasePosition(Out+I,FromP,From,ToP,To);
        Rebase6(Out+I+3,From,To);Rebase6(Out+I+9,From,To);
    }
}
inline void RebaseLower(const float* Input,float* Out,const FVector3f& FromP,const FRows& From,const FVector3f& ToP,const FRows& To)
{
    if (Input!=Out) FMemory::Memcpy(Out,Input,41*sizeof(float));
    for (int32 I:{3,12,18,28,34}) Clean6(Out+I);
    Out[24]=FMath::Clamp(Out[24],-1.f,1.f);Out[40]=FMath::Clamp(Out[40],-1.f,1.f);
    for (int32 I:{0,9,25}) RebasePosition(Out+I,FromP,From,ToP,To);
    for (int32 I:{3,12,18,28,34}) Rebase6(Out+I,From,To);
    // Native lower payload is cleaned again after its root-frame change.
    for (int32 I:{12,18,28,34}) Clean6(Out+I);
}
struct FContext
{
    float AttackerPelvis[2][9] = {};
    float AttackerCollider[2][9] = {};
    float Event=0, InitialYawDelta=0;
    FVector3f InitialWorldDelta=FVector3f::ZeroVector;
    FVector3f RootPosition=FVector3f::ZeroVector;
    FRows RootAxes;
    FVector3f TargetWorld=FVector3f::ZeroVector;
    float AttackControls[6] = {};
};
inline bool Conditioning(const FContext& C,float* Out50)
{
    const auto& R=C.RootAxes;
    const FVector3f BC=FVector3f::CrossProduct(R.V[1],R.V[2]);
    const FVector3f CA=FVector3f::CrossProduct(R.V[2],R.V[0]);
    const FVector3f AB=FVector3f::CrossProduct(R.V[0],R.V[1]);
    const float Det=FVector3f::DotProduct(R.V[0],BC);
    if (!FMath::IsFinite(Det) || FMath::Abs(Det)<1.e-8f) return false;
    for (int32 I=0;I<4;++I)
    {
        float* Out=Out50+9*I;
        // Synthetic spear has no pelvis; translated root must not make one.
        if (I<2 && C.AttackControls[5]>=.5f) { FMemory::Memzero(Out,9*sizeof(float));continue; }
        const float* In=I<2?C.AttackerPelvis[I]:C.AttackerCollider[I-2];
        Write(Out,InTransposedBasis(Read(In)-C.RootPosition,R));
        Write(Out+3,InTransposedBasis(Read(In+3),R));
        Write(Out+6,InTransposedBasis(Read(In+6),R));
    }
    Out50[36]=C.Event;
    Write(Out50+37,InTransposedBasis(C.InitialWorldDelta,R));
    Out50[40]=C.InitialYawDelta;
    // The fixed target deliberately uses the actual inverse, whereas the other
    // conditioning/history transformations use the native transpose contract.
    const FVector3f Delta=C.TargetWorld-C.RootPosition;
    Write(Out50+41,FVector3f(FVector3f::DotProduct(Delta,BC),FVector3f::DotProduct(Delta,CA),FVector3f::DotProduct(Delta,AB))/Det);
    FMemory::Memcpy(Out50+44,C.AttackControls,6*sizeof(float));
    return true;
}
inline void UpperInput(const float* PreviousUpper,const float* CurrentUpper,const float* PreviousLower,
    const float* CurrentLower,const float* NextLower,const float* Context,float* Out257)
{
    FMemory::Memcpy(Out257,PreviousUpper,90*sizeof(float));
    FMemory::Memcpy(Out257+90,CurrentUpper,90*sizeof(float));
    FMemory::Memcpy(Out257+180,PreviousLower,9*sizeof(float));
    FMemory::Memcpy(Out257+189,CurrentLower,9*sizeof(float));
    FMemory::Memcpy(Out257+198,NextLower,9*sizeof(float));
    FMemory::Memcpy(Out257+207,Context,50*sizeof(float));
}
inline void InitialRootCommand(const float* Root0,const float* Root1,FVector3f& Delta,float& Yaw)
{
    Delta=Read(Root1)-Read(Root0);
    const float Difference=FMath::Atan2(-Root1[6],-Root1[8])-FMath::Atan2(-Root0[6],-Root0[8]);
    Yaw=FMath::Atan2(FMath::Sin(Difference),FMath::Cos(Difference));
}
}
#if defined(_MSC_VER)
#pragma float_control(pop)
#endif
