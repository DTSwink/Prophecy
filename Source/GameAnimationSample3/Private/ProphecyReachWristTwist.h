#pragma once

// REACH wrist.js: feasible axial twist for a prescribed forearm direction.
// Kept local to the reach implementation; no retained objects or heap search.
namespace ProphecyReachWristTwist
{
struct FPolynomial
{
    double C[5]={};int N=0;
    FPolynomial()=default;
    FPolynomial(std::initializer_list<double> Values) { for(double V:Values)C[N++]=V;--N; }
    double At(double T) const { double V=C[N];for(int I=N-1;I>=0;--I)V=V*T+C[I];return V; }
    FPolynomial Scale(double S) const { auto R=*this;for(int I=0;I<=N;++I)R.C[I]*=S;return R; }
};
inline FPolynomial Add(const FPolynomial& A,const FPolynomial& B,double S=1.)
{ FPolynomial R;R.N=FMath::Max(A.N,B.N);for(int I=0;I<=R.N;++I)R.C[I]=A.C[I]+S*B.C[I];return R; }
inline FPolynomial Multiply(const FPolynomial& A,const FPolynomial& B)
{ FPolynomial R;R.N=A.N+B.N;for(int I=0;I<=A.N;++I)for(int J=0;J<=B.N;++J)R.C[I+J]+=A.C[I]*B.C[J];return R; }
using FRoots=TArray<double,TInlineAllocator<8>>;
inline FRoots Roots(FPolynomial A)
{
    FRoots Out;double Scale=0;for(int I=0;I<=A.N;++I)Scale=FMath::Max(Scale,FMath::Abs(A.C[I]));if(Scale<1.e-24)return Out;
    A=A.Scale(1./Scale);while(A.N>0&&FMath::Abs(A.C[A.N])<1.e-13)--A.N;
    if(A.N==0)return Out;if(A.N==1){Out.Add(-A.C[0]/A.C[1]);return Out;}
    double Bound=0;for(int I=0;I<A.N;++I)Bound=FMath::Max(Bound,FMath::Abs(A.C[I]/A.C[A.N]));Bound+=1.;
    FPolynomial D;D.N=A.N-1;for(int I=0;I<=D.N;++I)D.C[I]=A.C[I+1]*(I+1);
    const auto Critical=Roots(D);FRoots Breaks;Breaks.Add(-Bound);
    for(double T:Critical)if(FMath::Abs(T)<Bound){Breaks.Add(T);if(FMath::Abs(A.At(T))<1.e-10)Out.Add(T);}Breaks.Add(Bound);
    for(int I=1;I<Breaks.Num();++I)
    {
        double Lo=Breaks[I-1],Hi=Breaks[I],F=A.At(Lo);if(F*A.At(Hi)>=0)continue;
        for(int K=0;K<64;++K){const double M=(Lo+Hi)*.5,V=A.At(M);if(F*V<=0)Hi=M;else{Lo=M;F=V;}if(Hi-Lo<1.e-11*(1+FMath::Abs(M)))break;}
        Out.Add((Lo+Hi)*.5);
    }
    Out.Sort();for(int I=Out.Num()-1;I>0;--I)if(FMath::Abs(Out[I]-Out[I-1])<=1.e-8*(1+FMath::Abs(Out[I])))Out.RemoveAt(I);
    return Out;
}
struct FResult { FQuat Forearm=FQuat::Identity;double Roll=0;bool Feasible=false,IntervalSolve=false; };
inline FResult Fit(const FConstraintInstance& J,bool First,FQuat Desired,FVector LocalLower,FVector Direction,double Prior)
{
    const FQuat F1=J.GetRefFrame(EConstraintFrame::Frame1).GetRotation(),F2=J.GetRefFrame(EConstraintFrame::Frame2).GetRotation();
    const FQuat Neutral=First?Desired*F1*F2.Inverse():Desired*F2*F1.Inverse();
    const FQuat Aligned=ProphecyReachArm::Align(Neutral,Neutral.RotateVector(LocalLower),Direction);
    auto Relative=[&](FQuat Forearm){const FQuat Q1=(First?Desired:Forearm)*F1,Q2=(First?Forearm:Desired)*F2;return (Q2.Inverse()*Q1).GetNormalized();};
    // The half-turn coefficient must be orthogonal to A at double precision.
    // UE_PI is a float: its residual cosine changes quaternion length and can
    // falsely reject an otherwise feasible twist in the interval validity test.
    const FQuat A=Relative(Aligned),B=Relative(FQuat(Direction,UE_DOUBLE_PI)*Aligned);
    auto At=[&](double T){return A*FMath::Cos(T*.5)+B*FMath::Sin(T*.5);};
    auto Valid=[&](double T){const FQuat Q=At(T);return 1-FMath::Abs(Q|ProphecyReachWristLimits::Project(Q,J.ProfileInstance))<1.e-12;};
    auto Wrap=[](double T){return FMath::Atan2(FMath::Sin(T),FMath::Cos(T));};
    const double Ref=Wrap(Prior);
    if(Valid(Ref))return {(FQuat(Direction,Ref)*Aligned).GetNormalized(),Ref,true,false};
    const auto& P=J.ProfileInstance;
    const double BX=ProphecyReachWristLimits::Bound(P.TwistLimit.TwistMotion,P.TwistLimit.TwistLimitDegrees);
    const double RY=FMath::Sin(ProphecyReachWristLimits::Bound(P.ConeLimit.Swing2Motion,P.ConeLimit.Swing2LimitDegrees)*.5);
    const double RZ=FMath::Sin(ProphecyReachWristLimits::Bound(P.ConeLimit.Swing1Motion,P.ConeLimit.Swing1LimitDegrees)*.5);
    const FPolynomial X{A.X,B.X},Y{A.Y,B.Y},Z{A.Z,B.Z},W{A.W,B.W};
    const FPolynomial SY=Add(Multiply(Y,W),Multiply(Z,X),-1),SZ=Add(Multiply(Z,W),Multiply(Y,X));
    const FPolynomial Den=Multiply(Add(Multiply(X,X),Multiply(W,W)),FPolynomial{1,0,1});
    TArray<FPolynomial,TInlineAllocator<4>> Constraints;
    if(BX<UE_DOUBLE_PI)Constraints.Add(Add(Multiply(X,X).Scale(FMath::Square(FMath::Cos(BX*.5))),Multiply(W,W).Scale(FMath::Square(FMath::Sin(BX*.5))),-1));
    Constraints.Add(Add(Add(RY>1.e-12?Multiply(SY,SY).Scale(1/(RY*RY)):FPolynomial{},RZ>1.e-12?Multiply(SZ,SZ).Scale(1/(RZ*RZ)):FPolynomial{}),Den,-1));
    if(RY<1.e-12)Constraints.Add(SY);if(RZ<1.e-12)Constraints.Add(SZ);
    TArray<double,TInlineAllocator<24>> Cuts;Cuts.Add(-UE_DOUBLE_PI);Cuts.Add(UE_DOUBLE_PI);
    for(const auto& C:Constraints)for(double T:Roots(C))Cuts.Add(2*FMath::Atan(T));
    Cuts.Sort();for(int I=Cuts.Num()-1;I>0;--I)if(Cuts[I]-Cuts[I-1]<=1.e-9)Cuts.RemoveAt(I);
    double Roll=Ref,Best=DBL_MAX;bool Feasible=false;
    auto Choose=[&](double T){const double Distance=FMath::Abs(Wrap(T-Ref));if(!Feasible||Distance<Best){Feasible=true;Best=Distance;Roll=T;}};
    for(int I=1;I<Cuts.Num();++I)if(Valid((Cuts[I-1]+Cuts[I])*.5))for(double R:{Ref-2*UE_DOUBLE_PI,Ref,Ref+2*UE_DOUBLE_PI})Choose(FMath::Clamp(R,Cuts[I-1],Cuts[I]));
    for(double T:Cuts)if(Valid(T))Choose(T);
    if(!Feasible)
    {
        // This direction has no feasible twist. Keep the best boundary and let
        // the actual hand projection enforce PHAT; never widen the grab gates.
        Best=DBL_MAX;
        auto Closest=[&](double T){const FQuat Q=At(T);const double Error=1-FMath::Abs(Q|ProphecyReachWristLimits::Project(Q,P));if(Error<Best-1.e-12){Best=Error;Roll=T;}};
        Closest(Ref);Closest(0);for(double T:Cuts)Closest(T);
    }
    return {(FQuat(Direction,Roll)*Aligned).GetNormalized(),Roll,Feasible,true};
}
}
