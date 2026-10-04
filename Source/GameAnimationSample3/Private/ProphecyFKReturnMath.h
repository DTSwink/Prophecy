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
    int32 Index=INDEX_NONE,Parent=INDEX_NONE,ParentSlot=INDEX_NONE;
    uint8 Group=GroupCount; // Hands: no angular OR offset inertia.
    FQuat4f Start=FQuat4f::Identity;
    FVector3f Offset=FVector3f::ZeroVector;
    FArc Return,Velocity,OffsetReturn,OffsetVelocity,WorldCorrection;
};
struct FCurve
{
    FBone Bones[BoneCount];
    float InverseDuration=1.f/.26f,Easing=.12f,Coefficient=1.f;
    float InertiaHold=0.f,InertiaDecay=1.f;
    bool WorldInertia=false;
    FQuat SeedFrame=FQuat::Identity;
    FQuat4f StartPelvis=FQuat4f::Identity;
    float AlphaHold=0.f,InverseTakeoverWindow=1.f;
    float TakeoverTimeScale=1.f; // Trim scales NN progress, never authored FK/inertia time.
    void SetAlphaHold(float Value){AlphaHold=Value;InverseTakeoverWindow=Value<1.f?1.f/(1.f-Value):0.f;}
    float NNWeight(float X) const
    {
        X*=TakeoverTimeScale;
        const float U=X>=1.f?1.f:FMath::Clamp((X-AlphaHold)*InverseTakeoverWindow,0.f,1.f);
        return Coefficient==1.f?U:Coefficient==2.f?U*U:FMath::Pow(U,Coefficient);
    }
    float Decay[GroupCount]{};
    uint8 DecaySource[GroupCount]={0,1,2,3,4,5,6};
    struct FSample { float Blend,NN,Momentum[GroupCount+1]{}; };
    FSample Weights(float Elapsed) const
    {
        const float X=Elapsed>=1.f/InverseDuration?1.f:FMath::Clamp(Elapsed*InverseDuration,0.f,1.f);
        const float Fade=FMath::Clamp((X-InertiaHold)/(1-InertiaHold),0.f,1.f);
        const float Phase=InertiaHold>0?Fade*Fade:X,Y=1-Phase;
        FSample S;S.Blend=X+(X*X*X*(10+X*(-15+6*X))-X)*Easing;
        S.NN=NNWeight(X);
        const float Base=FMath::Max(0.f,Elapsed)*Y*Y*Y;
        for(int32 G=0;G<GroupCount;++G)if(Decay[G]>0 && Base>0)
            S.Momentum[G]=DecaySource[G]<G?S.Momentum[DecaySource[G]]:Base*FMath::Exp(-InertiaDecay*Phase*Decay[G]);
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
    // Build the pure lab hierarchy before NN mixing. An excluded hand/zero-weight
    // bone inherits its actual parent, while active world axes do not inherit inertia.
    void SampleLocals(const FSample& S,const FQuat4f& Pelvis,const FQuat4f& FrameDelta,
        FQuat4f (&Q)[BoneCount],FVector3f (&P)[BoneCount]) const
    {
        FQuat4f Base[BoneCount],World[BoneCount];
        // The lab freezes the pelvis. In game it keeps moving: gradually acquire
        // that moving idle frame rather than add its angular rate a second time
        // at entry. Static pelvis reproduces the lab exactly; endpoint is local idle.
        const FQuat4f BaselinePelvis=FQuat4f::Slerp((FrameDelta*StartPelvis).GetNormalized(),Pelvis,S.Blend).GetNormalized();
        for(int32 J=0;J<BoneCount;++J)
        {
            const auto& B=Bones[J];Local(B,S,Q[J],P[J]);
            if(!WorldInertia)continue;
            const FQuat4f LocalBase=(B.Start*B.Return.At(S.Blend)).GetNormalized();
            const FQuat4f ParentBase=B.ParentSlot<0?BaselinePelvis:Base[B.ParentSlot];
            const FQuat4f ParentWorld=B.ParentSlot<0?Pelvis:World[B.ParentSlot];
            Base[J]=(ParentBase*LocalBase).GetNormalized();
            const float M=S.Momentum[B.Group];
            World[J]=M>0?(FrameDelta*B.WorldCorrection.At(M)*FrameDelta.Inverse()*Base[J]).GetNormalized()
                :(ParentWorld*LocalBase).GetNormalized();
            Q[J]=(ParentWorld.Inverse()*World[J]).GetNormalized();
        }
    }
    void Apply(float Elapsed,TArrayView<FTransform> Pose,TArrayView<FTransform> Locals={},
        const FQuat& Frame=FQuat::Identity) const
    {
        if(Elapsed>=(1.f/InverseDuration)/TakeoverTimeScale)return;
        const FSample S=Weights(Elapsed);
        FTransform Target[BoneCount];FQuat4f Q[BoneCount];FVector3f P[BoneCount];
        if(S.NN>0)for(int32 J=0;J<BoneCount;++J)
        {const auto& B=Bones[J];Target[J]=Pose[B.Index].GetRelativeTransform(Pose[B.Parent]);}
        SampleLocals(S,FQuat4f(Pose[Bones[0].Parent].GetRotation()),FQuat4f(Frame.Inverse()*SeedFrame),Q,P);
        for(int32 J=0;J<BoneCount;++J)
        {
            const auto& B=Bones[J];
            if(S.NN>0)
            {
                Q[J]=FQuat4f::Slerp(Q[J],FQuat4f(Target[J].GetRotation()),S.NN).GetNormalized();
                P[J]=BlendOffset(P[J],FVector3f(Target[J].GetTranslation()),S.NN);
            }
            FTransform L(FQuat(Q[J]),FVector(P[J]),S.NN>0?Target[J].GetScale3D():FVector::OneVector);
            Pose[B.Index]=L*Pose[B.Parent];
            if(!Locals.IsEmpty())Locals[B.Index]=L;
        }
    }
};
}
