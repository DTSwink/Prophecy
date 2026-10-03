#pragma once
#include "CoreMinimal.h"

// Single-precision, allocation-free sampling. Transcendentals depending only on
// attack data are cached once; decay is shared by all bones in each symmetric group.
namespace ProphecyFKReturn
{
constexpr int32 BoneCount=16, GroupCount=7;
struct FArc
{
    FVector3f Axis=FVector3f::ZeroVector;
    float HalfAngle=0;
    void Set(FQuat4f Q,float Rate=1.f)
    {
        Q.Normalize();if(Q.W<0)Q=Q*-1.f;
        const float N=FMath::Sqrt(Q.X*Q.X+Q.Y*Q.Y+Q.Z*Q.Z);
        if(N<1.e-8f){Axis=FVector3f::ZeroVector;HalfAngle=0;return;}
        Axis=FVector3f(Q.X,Q.Y,Q.Z)/N;HalfAngle=FMath::Atan2(N,Q.W)*Rate;
    }
    FQuat4f At(float T) const
    {
        if(HalfAngle==0 || T==0)return FQuat4f::Identity;
        float S,C;FMath::SinCos(&S,&C,HalfAngle*T);return FQuat4f(Axis.X*S,Axis.Y*S,Axis.Z*S,C);
    }
};
inline FQuat4f Swing(FVector3f A,FVector3f B)
{
    if(!A.Normalize() || !B.Normalize())return FQuat4f::Identity;
    const float D=FVector3f::DotProduct(A,B);
    // Match the lab's deterministic antiparallel choice, including +/-179 degree tests.
    if(D<-.999999f)
    {
        FVector3f Axis=FVector3f::CrossProduct(A,FVector3f(1,0,0));
        if(Axis.SizeSquared()<1.e-10f)Axis=FVector3f::CrossProduct(A,FVector3f(0,1,0));
        Axis.Normalize();return FQuat4f(Axis.X,Axis.Y,Axis.Z,0);
    }
    const FVector3f C=FVector3f::CrossProduct(A,B);
    return FQuat4f(C.X,C.Y,C.Z,1+D).GetNormalized();
}
inline FVector3f BlendOffset(const FVector3f& A,const FVector3f& B,float T)
{
    if(T<=0)return A;if(T>=1)return B;
    const float LA=A.Size(),LB=B.Size();
    if(LA<1.e-7f || LB<1.e-7f)return FMath::Lerp(A,B,T);
    const FQuat4f Q=Swing(A,B);
    return FQuat4f::Slerp(FQuat4f::Identity,Q,T).RotateVector(A/LA)*FMath::Lerp(LA,LB,T);
}
struct FBone
{
    int32 Index=INDEX_NONE,Parent=INDEX_NONE;
    uint8 Group=GroupCount; // Hands: no angular OR offset inertia.
    FQuat4f Start=FQuat4f::Identity;
    FVector3f Offset=FVector3f::ZeroVector;
    FArc Return,Velocity,OffsetReturn,OffsetVelocity;
};
struct FCurve
{
    FBone Bones[BoneCount];
    float InverseDuration=1.f/.26f,Easing=.12f,Coefficient=1.f;
    float AlphaHold=0.f,InverseTakeoverWindow=1.f;
    void SetAlphaHold(float Value){AlphaHold=Value;InverseTakeoverWindow=Value<1.f?1.f/(1.f-Value):0.f;}
    float NNWeight(float X) const
    {
        const float U=X>=1.f?1.f:FMath::Clamp((X-AlphaHold)*InverseTakeoverWindow,0.f,1.f);
        return Coefficient==1.f?U:Coefficient==2.f?U*U:FMath::Pow(U,Coefficient);
    }
    float Decay[GroupCount]{};
    uint8 DecaySource[GroupCount]={0,1,2,3,4,5,6};
    struct FSample { float Blend,NN,Momentum[GroupCount+1]{}; };
    FSample Weights(float Elapsed) const
    {
        const float X=FMath::Clamp(Elapsed*InverseDuration,0.f,1.f),Y=1-X;
        FSample S;S.Blend=X+(X*X*X*(10+X*(-15+6*X))-X)*Easing;
        S.NN=NNWeight(X);
        const float Base=FMath::Max(0.f,Elapsed)*Y*Y*Y;
        for(int32 G=0;G<GroupCount;++G)if(Decay[G]>0 && Base>0)
            S.Momentum[G]=DecaySource[G]<G?S.Momentum[DecaySource[G]]:Base*FMath::Exp(-Elapsed*Decay[G]);
        return S;
    }
    static void Local(const FBone& B,const FSample& S,FQuat4f& Q,FVector3f& P)
    {
        Q=B.Start*B.Return.At(S.Blend);
        P=B.OffsetReturn.At(S.Blend).RotateVector(B.Offset);
        const float M=S.Momentum[B.Group];
        if(M>0){Q=Q*B.Velocity.At(M);P=B.OffsetVelocity.At(M).RotateVector(P);}
        Q.Normalize();
    }
    void Apply(float Elapsed,TArrayView<FTransform> Pose,TArrayView<FTransform> Locals={}) const
    {
        if(Elapsed*InverseDuration>=1.f)return; // Exact NN, no round trip at completion.
        const FSample S=Weights(Elapsed);
        // Read all NN locals before overwriting their parents. Stack storage only.
        FTransform Target[BoneCount];
        if(S.NN>0)for(int32 J=0;J<BoneCount;++J)
        {const auto& B=Bones[J];Target[J]=Pose[B.Index].GetRelativeTransform(Pose[B.Parent]);}
        for(int32 J=0;J<BoneCount;++J)
        {
            const auto& B=Bones[J];FQuat4f Q;FVector3f P;Local(B,S,Q,P);
            if(S.NN>0)
            {
                Q=FQuat4f::Slerp(Q,FQuat4f(Target[J].GetRotation()),S.NN).GetNormalized();
                P=BlendOffset(P,FVector3f(Target[J].GetTranslation()),S.NN);
            }
            FTransform L(FQuat(Q),FVector(P),S.NN>0?Target[J].GetScale3D():FVector::OneVector);
            Pose[B.Index]=L*Pose[B.Parent];
            if(!Locals.IsEmpty())Locals[B.Index]=L;
        }
    }
};
}
