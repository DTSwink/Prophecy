// Fixed-elevation interception and bounded closest approach. No retained state or tick work.
namespace ProphecyHitTrajectory
{
using FPoly = TArray<double,TInlineAllocator<9>>;
using FRoots = TArray<double,TInlineAllocator<16>>;

static FPoly Add(FPoly A,const FPoly& B,double Scale=1.)
{
    if (A.Num()<B.Num()) A.SetNumZeroed(B.Num());
    for (int32 I=0;I<B.Num();++I) A[I]+=Scale*B[I];
    return A;
}
static FPoly Mul(const FPoly& A,const FPoly& B,double Scale=1.)
{
    FPoly R;R.SetNumZeroed(A.Num()+B.Num()-1);
    for (int32 I=0;I<A.Num();++I)
        for (int32 J=0;J<B.Num();++J) R[I+J]+=Scale*A[I]*B[J];
    return R;
}
static FPoly Derivative(const FPoly& P)
{
    FPoly R;R.SetNumZeroed(FMath::Max(1,P.Num()-1));
    for (int32 I=1;I<P.Num();++I) R[I-1]=I*P[I];
    return R;
}
static double Eval(const FPoly& P,double X)
{
    double R=0.;for (int32 I=P.Num()-1;I>=0;--I) R=R*X+P[I];return R;
}
static bool NearZero(const FPoly& P,double X,double Value)
{
    double Bound=0.;
    for (int32 I=P.Num()-1;I>=0;--I) Bound=Bound*FMath::Abs(X)+FMath::Abs(P[I]);
    return FMath::Abs(Value)<=2.e-13*Bound;
}
// Derivative roots partition [0,1] into monotone intervals. Also retain tangent
// roots: a sign-change-only search misses the limiting reachable trajectory.
static void Roots(FPoly P,FRoots& Out)
{
    while (P.Num()>1 && P.Last()==0.) P.Pop(EAllowShrinking::No);
    if (P.Num()<2) return;
    double Scale=0.;for (double C:P) Scale=FMath::Max(Scale,FMath::Abs(C));
    if (!FMath::IsFinite(Scale) || Scale==0.) return;
    for (double& C:P) C/=Scale;
    if (P.Num()==2)
    {
        const double X=-P[0]/P[1];if (X>=0. && X<=1.) Out.Add(X);return;
    }
    FRoots Critical;Roots(Derivative(P),Critical);Critical.Sort();
    Critical.Add(1.);
    double Lo=0.,FLo=Eval(P,Lo);
    if (NearZero(P,Lo,FLo)) Out.Add(Lo);
    for (double Hi:Critical)
    {
        const double FHi=Eval(P,Hi);
        if (NearZero(P,Hi,FHi)) Out.Add(Hi);
        if ((FLo<0. && FHi>0.) || (FLo>0. && FHi<0.))
        {
            double A=Lo,B=Hi,FA=FLo;
            for (int32 I=0;I<64;++I)
            {
                const double Mid=(A+B)*.5,FM=Eval(P,Mid);
                if (Mid==A || Mid==B) break;
                if (FM==0.) { A=B=Mid;break; }
                if ((FA<0.)==(FM<0.)) { A=Mid;FA=FM; } else B=Mid;
            }
            Out.Add((A+B)*.5);
        }
        Lo=Hi;FLo=FHi;
    }
}
struct FResult
{
    FVector Velocity=FVector::ZeroVector;
    double Time=0.,Miss=-1.;
    bool Exact=false;
};
static FResult Solve(const FVector& D,const FVector& V,double Angle,double GravityZ,double MaxSpeed,double Horizon)
{
    FResult Result;
    if (D.ContainsNaN() || V.ContainsNaN() || !FMath::IsFinite(Angle)
        || !FMath::IsFinite(GravityZ) || !FMath::IsFinite(MaxSpeed) || MaxSpeed<=0.
        || !FMath::IsFinite(Horizon) || Horizon<=0.) return Result;
    Angle=FMath::Clamp(Angle,-90.,90.);
    const double C=FMath::Abs(Angle)==90. ? 0. : FMath::Cos(FMath::DegreesToRadians(Angle));
    const double S=Angle==0. ? 0. : FMath::Sin(FMath::DegreesToRadians(Angle));
    const FVector W=V*Horizon;
    const double G=-.5*GravityZ*Horizon*Horizon,K=MaxSpeed*Horizon;
    // x=t/Horizon. Required gravity-compensated displacement is (Dxy+Wxy*x,Z(x)).
    const FPoly H{D.X*D.X+D.Y*D.Y,2.*(D.X*W.X+D.Y*W.Y),W.X*W.X+W.Y*W.Y};
    const FPoly Z{D.Z,W.Z,G},X{0.,1.};
    const FPoly DH=Derivative(H),DZ=Derivative(Z);
    const FPoly B=Add(Mul(Z,DZ),DH,.5);
    const FPoly A=Add(Add(B,X,K*K),Add(Z,Mul(X,DZ)),-K*S);
    const FPoly H2=Add(Add(H,H),Mul(X,DH));
    // All extrema of squared miss, plus the boundaries of the three speed regimes:
    // speed=0, 0<speed<MaxSpeed, speed=MaxSpeed. Squaring adds harmless extra candidates;
    // evaluate every candidate with the ORIGINAL objective, never the squared equation.
    const FPoly Equations[]{
        Add(Mul(Z,Z,C*C),H,-S*S),                            // exact intercept
        Add(Mul(DH,DH,S*S),Mul(Mul(DZ,DZ),H),-4.*C*C),        // interior stationary miss
        Add(Mul(H,Mul(A,A),4.),Mul(H2,H2),-K*K*C*C),          // capped-speed stationary miss
        B,                                                   // zero-speed stationary miss
        Add(Mul(Z,Z,S*S),H,-C*C),                            // projection=0 boundary
        Add(Mul(Add(Mul(X,FPoly{K}),Z,-S),Add(Mul(X,FPoly{K}),Z,-S)),H,-C*C),
        DH                                                   // horizontal-distance cusp
    };
    for (const FPoly& P:Equations)
        for (double Value:P) if (!FMath::IsFinite(Value)) return Result;
    double BestError=TNumericLimits<double>::Max();
    auto Consider=[&](double Fraction)
    {
        const double T=Fraction*Horizon;
        const FVector Q=D+V*T+FVector(0.,0.,-.5*GravityZ*T*T);
        const double Horizontal=FMath::Sqrt(Q.X*Q.X+Q.Y*Q.Y);
        const FVector Heading=Horizontal>1.e-12 ? FVector(Q.X/Horizontal,Q.Y/Horizontal,0.) : FVector::ForwardVector;
        const FVector Direction=Heading*C+FVector::UpVector*S;
        const double Projection=C*Horizontal+S*Q.Z;
        const double Speed=T>0. ? FMath::Clamp(Projection/T,0.,MaxSpeed) : MaxSpeed;
        const FVector Velocity=Direction*Speed;
        const double Error=(Velocity*T-Q).SizeSquared();
        if (Error<BestError-1.e-12 || (FMath::Abs(Error-BestError)<=1.e-12 && T<Result.Time))
        { BestError=Error;Result.Velocity=Velocity;Result.Time=T; }
    };
    Consider(0.);Consider(1.);
    for (const FPoly& P:Equations)
    {
        FRoots Candidates;Roots(P,Candidates);
        for (double T:Candidates) Consider(T);
    }
    Result.Miss=FMath::Sqrt(BestError);
    Result.Exact=Result.Miss<=.01;
    return Result;
}
}
