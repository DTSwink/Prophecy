#include "ProphecyFootIKArmKernel.h"
#include "src/base/ieee754.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <limits>

#if defined(_MSC_VER)
#pragma float_control(precise,on,push)
#pragma float_control(except,on)
#pragma fenv_access(on)
#pragma fp_contract(off)
#endif

namespace ProphecyFootIKMath
{
namespace ArmKernel
{
namespace M=v8::base::ieee754;
using V=std::array<double,3>;
using Q=std::array<double,4>;
constexpr Q Identity={0,0,0,1};
constexpr double Pi=3.141592653589793238462643383279502884;
double Max(double A,double B){if(A>B)return A;if(B>A)return B;if(A==B)return A==0?(std::signbit(A)&&std::signbit(B)?-0.:0.):A;return std::numeric_limits<double>::quiet_NaN();}
double Min(double A,double B){if(A<B)return A;if(B<A)return B;if(A==B)return A==0?(std::signbit(A)||std::signbit(B)?-0.:0.):A;return std::numeric_limits<double>::quiet_NaN();}
double Clamp(double X,double A,double B){return Max(A,Min(B,X));}
template<size_t N>std::array<double,N> Scale(const std::array<double,N>& A,double S){std::array<double,N> R;for(size_t I=0;I<N;++I)R[I]=A[I]*S;return R;}
V Add(const V&A,const V&B){return {A[0]+B[0],A[1]+B[1],A[2]+B[2]};}
V Sub(const V&A,const V&B){return {A[0]-B[0],A[1]-B[1],A[2]-B[2]};}
template<size_t N>double Dot(const std::array<double,N>&A,const std::array<double,N>&B){double S=0;for(size_t I=0;I<N;++I)S=S+A[I]*B[I];return S;}
V Cross(const V&A,const V&B){return {A[1]*B[2]-A[2]*B[1],A[2]*B[0]-A[0]*B[2],A[0]*B[1]-A[1]*B[0]};}
// The2/3argument V8 fast paths differ from its general Kahan path. Do not
// replace this with std::hypot, squared length or a reassociated sum.
template<size_t N>double Hypot(const std::array<double,N>& A)
{
    std::array<double,N> Values;double Maximum=0;
    for(size_t I=0;I<N;++I){Values[I]=std::abs(A[I]);Maximum=Max(Maximum,Values[I]);}
    if(Maximum==0)return 0;
    if constexpr(N==2){const double X=Values[0]/Maximum,Y=Values[1]/Maximum;return std::sqrt(X*X+Y*Y)*Maximum;}
    if constexpr(N==3)
    {
        const double X=Values[0]/Maximum,Y=Values[1]/Maximum,Z=Values[2]/Maximum;
        const double A2=X*X,B2=Y*Y,Compensation=(A2+B2)-A2-B2,C2=Z*Z-Compensation;
        return std::sqrt(A2+B2+C2)*Maximum;
    }
    double Sum=0,Correction=0;
    for(size_t I=0;I<N;++I){const double X=Values[I]/Maximum,Summand=X*X-Correction,Preliminary=Sum+Summand;Correction=(Preliminary-Sum)-Summand;Sum=Preliminary;}
    return std::sqrt(Sum)*Maximum;
}
template<size_t N>std::array<double,N> Unit(const std::array<double,N>&A){const double Nrm=Hypot(A);return Scale(A,1/(Nrm==0?1:Nrm));}
Q Inverse(const Q&A){return {-A[0],-A[1],-A[2],A[3]};}
Q Multiply(const Q&A,const Q&B)
{
    return {A[3]*B[0]+A[0]*B[3]+A[1]*B[2]-A[2]*B[1],A[3]*B[1]-A[0]*B[2]+A[1]*B[3]+A[2]*B[0],
        A[3]*B[2]+A[0]*B[1]-A[1]*B[0]+A[2]*B[3],A[3]*B[3]-(A[0]*B[0]+A[1]*B[1]+A[2]*B[2])};
}
V Rotate(const Q&Q0,const V&P)
{
    const double X=2*(Q0[1]*P[2]-Q0[2]*P[1]),Y=2*(Q0[2]*P[0]-Q0[0]*P[2]),Z=2*(Q0[0]*P[1]-Q0[1]*P[0]);
    return {P[0]+(X*Q0[3]+Q0[1]*Z-Q0[2]*Y),P[1]+(Y*Q0[3]+Q0[2]*X-Q0[0]*Z),P[2]+(Z*Q0[3]+Q0[0]*Y-Q0[1]*X)};
}
Q Exp(const V&A)
{
    const double N=Hypot(A);if(N<1.e-10)return Unit(Q{A[0]*.5,A[1]*.5,A[2]*.5,1});
    const V P=Scale(A,M::sin(N*.5)/N);return {P[0],P[1],P[2],M::cos(N*.5)};
}
Q Positive(const Q&A){return A[3]<0?Scale(A,-1):A;}
V Tangent(const V&V0,const V&N){return Sub(V0,Scale(N,Dot(V0,N)));}
Q FromTo(V A,V B)
{
    A=Unit(A);B=Unit(B);const double C=Dot(A,B);
    if(C<-.999999){V Axis=Cross(A,V{1,0,0});if(Hypot(Axis)<1.e-5)Axis=Cross(A,V{0,1,0});Axis=Unit(Axis);return {Axis[0],Axis[1],Axis[2],0};}
    const V Axis=Cross(A,B);return Unit(Q{Axis[0],Axis[1],Axis[2],1+C});
}
Q FromAxes(const V&A,const V&B,const V&C)
{
    const double M00=A[0],M01=B[0],M02=C[0],M10=A[1],M11=B[1],M12=C[1],M20=A[2],M21=B[2],M22=C[2],Trace=M00+M11+M22;double S;Q R;
    if(Trace>0){S=std::sqrt(Trace+1)*2;R={(M21-M12)/S,(M02-M20)/S,(M10-M01)/S,S/4};}
    else if(M00>M11&&M00>M22){S=std::sqrt(1+M00-M11-M22)*2;R={S/4,(M01+M10)/S,(M02+M20)/S,(M21-M12)/S};}
    else if(M11>M22){S=std::sqrt(1+M11-M00-M22)*2;R={(M01+M10)/S,S/4,(M12+M21)/S,(M02-M20)/S};}
    else{S=std::sqrt(1+M22-M00-M11)*2;R={(M02+M20)/S,(M12+M21)/S,S/4,(M10-M01)/S};}return Unit(R);
}
struct SwingJoint{Q C1,C2,Reference;double SinY,SinZ,Twist;};
struct HingeJoint{V Axis;Q Reference;double Idle,Minimum,Maximum;};
struct Parts{Q Swing,Twist;};
Parts Decompose(Q R)
{
    R=Unit(R);const double N=Hypot(std::array<double,2>{R[0],R[3]});const Q T=N>1.e-12?Q{R[0]/N,0,0,R[3]/N}:Identity;
    return {Positive(Unit(Multiply(R,Inverse(T)))),Positive(T)};
}
Q HingeRelative(const HingeJoint&J,double Bend){return Unit(Multiply(Exp(Scale(J.Axis,Bend-J.Idle)),J.Reference));}
Q ProjectHinge(const HingeJoint&J,const Q&Parent,const Q&Child)
{
    const Q Relative=Unit(Multiply(Inverse(Parent),Child)),Delta=Positive(Unit(Multiply(Relative,Inverse(J.Reference))));
    const double Bend=J.Idle+2*M::atan2(Dot(V{Delta[0],Delta[1],Delta[2]},J.Axis),Delta[3]);
    Q R=Unit(Multiply(Parent,HingeRelative(J,Clamp(Bend,J.Minimum,J.Maximum))));if(Dot(R,Child)<0)R=Scale(R,-1);return R;
}
std::array<double,2> Ellipse(double Y,double Z,double A,double B)
{
    const double U=Y/A,V0=Z/B;if(U*U+V0*V0<=1)return {Y,Z};
    const double A2=A*A,B2=B*B;double Lo=0,Hi=Hypot(std::array<double,2>{A*Y,B*Z});
    for(int K=0;K<38;++K){const double T=(Lo+Hi)*.5,EY=A*Y/(T+A2),EZ=B*Z/(T+B2);if(EY*EY+EZ*EZ>1)Lo=T;else Hi=T;}
    return {A2*Y/(Hi+A2),B2*Z/(Hi+B2)};
}
Q ProjectSwing(const SwingJoint&J,const Q&Parent,const Q&Child)
{
    const Q Relative=Unit(Multiply(Inverse(Multiply(Parent,J.C1)),Multiply(Child,J.C2)));const Parts P=Decompose(Relative);
    const auto YZ=Ellipse(P.Swing[1],P.Swing[2],J.SinY,J.SinZ);
    const Q Swing{0,YZ[0],YZ[1],std::sqrt(Max(0,1-YZ[0]*YZ[0]-YZ[1]*YZ[1]))};
    const Q Twist=Exp(V{Clamp(2*M::atan2(P.Twist[0],P.Twist[3]),-J.Twist,J.Twist),0,0});
    Q R=Unit(Multiply(Multiply(Multiply(Parent,J.C1),Multiply(Swing,Twist)),Inverse(J.C2)));if(Dot(R,Child)<0)R=Scale(R,-1);return R;
}
struct Polynomial{std::array<double,5> Data{};int N=0;};
Polynomial AddPolynomial(const Polynomial&A,const Polynomial&B,double Sign=1)
{
    Polynomial P;P.N=std::max(A.N,B.N);for(int I=0;I<P.N;++I){const double X=I<A.N&&A.Data[I]!=0?A.Data[I]:0,Y=I<B.N&&B.Data[I]!=0?B.Data[I]:0;P.Data[I]=X+Sign*Y;}return P;
}
Polynomial Product(const Polynomial&A,const Polynomial&B)
{
    Polynomial P;P.N=A.N+B.N-1;for(int I=0;I<A.N;++I)for(int J=0;J<B.N;++J)P.Data[I+J]+=A.Data[I]*B.Data[J];return P;
}
struct Roots{std::array<double,16> Data{};int N=0;void Add(double V0){if(N<16)Data[N++]=V0;}};
Roots RealRoots(const Polynomial&Input)
{
    Roots Result;double Scale0=0;for(int I=0;I<Input.N;++I)Scale0=Max(Scale0,std::abs(Input.Data[I]));if(Scale0<1.e-16)return Result;
    Polynomial P=Input;for(int I=0;I<P.N;++I)P.Data[I]/=Scale0;while(P.N>1&&std::abs(P.Data[P.N-1])<1.e-13)--P.N;
    const int N=P.N-1;if(!N)return Result;if(N==1){Result.Add(-P.Data[0]/P.Data[1]);return Result;}
    auto Value=[&](double X){double Y=P.Data[N];for(int I=N-1;I>=0;--I)Y=Y*X+P.Data[I];return Y;};
    double Bound=0;for(int I=0;I<N;++I)Bound=Max(Bound,std::abs(P.Data[I]/P.Data[N]));Bound=1+Bound;
    Polynomial Derivative;Derivative.N=N;for(int I=0;I<N;++I)Derivative.Data[I]=P.Data[I+1]*(I+1);
    const Roots AllCritical=RealRoots(Derivative);Roots Critical;for(int I=0;I<AllCritical.N;++I)if(AllCritical.Data[I]>-Bound&&AllCritical.Data[I]<Bound)Critical.Add(AllCritical.Data[I]);
    std::stable_sort(Critical.Data.begin(),Critical.Data.begin()+Critical.N);Roots Cuts;Cuts.Add(-Bound);for(int I=0;I<Critical.N;++I)Cuts.Add(Critical.Data[I]);Cuts.Add(Bound);
    for(int I=0;I<Critical.N;++I)if(std::abs(Value(Critical.Data[I]))<1.e-10)Result.Add(Critical.Data[I]);
    for(int I=1;I<Cuts.N;++I)
    {
        double Lo=Cuts.Data[I-1],Hi=Cuts.Data[I],FLo=Value(Lo),FHi=Value(Hi);if(FLo==0)Result.Add(Lo);if(FHi==0)Result.Add(Hi);if((FLo<0)==(FHi<0))continue;
        for(int K=0;K<90;++K){const double Mid=(Lo+Hi)*.5;if(Mid==Lo||Mid==Hi)break;const double FMid=Value(Mid);if((FLo<0)==(FMid<0)){Lo=Mid;FLo=FMid;}else Hi=Mid;}Result.Add((Lo+Hi)*.5);
    }
    std::stable_sort(Result.Data.begin(),Result.Data.begin()+Result.N);Roots Unique;for(int I=0;I<Result.N;++I)if(!I||std::abs(Result.Data[I]-Result.Data[I-1])>1.e-9*(1+std::abs(Result.Data[I])))Unique.Add(Result.Data[I]);return Unique;
}
double Swivel(const SwingJoint&J,const Q&Left,const Q&Upper,const V&Axis,const V&CurrentPole,const V&DesiredPole)
{
    auto Within=[&](const Q&Child){const Parts P=Decompose(Unit(Multiply(Left,Multiply(Child,J.C2))));const double Y=P.Swing[1]/J.SinY,Z=P.Swing[2]/J.SinZ,Ellipse0=Y*Y+Z*Z,Twist=2*M::atan2(P.Twist[0],P.Twist[3]);return Ellipse0<=1+1.e-8&&std::abs(Twist)<=J.Twist+1.e-8;};
    if(Within(Upper))return 0;
    const Q Right=Multiply(Upper,J.C2),Q0=Multiply(Left,Right),Q1=Multiply(Multiply(Left,Q{Axis[0],Axis[1],Axis[2],0}),Right);
    std::array<Polynomial,4> C;for(int I=0;I<4;++I){C[I].N=2;C[I].Data[0]=Q0[I];C[I].Data[1]=Q1[I];}
    const Polynomial XX=Product(C[0],C[0]),WW=Product(C[3],C[3]),Norm=AddPolynomial(XX,WW);
    const Polynomial Y=AddPolynomial(Product(C[3],C[1]),Product(C[0],C[2]),-1),Z=AddPolynomial(Product(C[3],C[2]),Product(C[0],C[1]));
    Polynomial YY=Product(Y,Y),ZZ=Product(Z,Z),Factor;Factor.N=3;Factor.Data={1,0,1,0,0};
    for(int I=0;I<YY.N;++I)YY.Data[I]/=J.SinY*J.SinY;for(int I=0;I<ZZ.N;++I)ZZ.Data[I]/=J.SinZ*J.SinZ;
    const Polynomial Swing=AddPolynomial(AddPolynomial(YY,ZZ),Product(Norm,Factor),-1);
    const double Sin=M::sin(J.Twist/2),Cos=M::cos(J.Twist/2);Polynomial XT=XX,WT=WW;for(int I=0;I<XT.N;++I)XT.Data[I]=XT.Data[I]*Cos*Cos;for(int I=0;I<WT.N;++I)WT.Data[I]=WT.Data[I]*Sin*Sin;
    const Roots SwingRoots=RealRoots(Swing),TwistRoots=RealRoots(AddPolynomial(XT,WT,-1));Roots Angles;
    for(int I=0;I<SwingRoots.N;++I)Angles.Add(2*M::atan(SwingRoots.Data[I]));for(int I=0;I<TwistRoots.N;++I)Angles.Add(2*M::atan(TwistRoots.Data[I]));std::stable_sort(Angles.Data.begin(),Angles.Data.begin()+Angles.N);
    Roots Cuts;Cuts.Add(-Pi);for(int I=0;I<Angles.N;++I)if(!I||Angles.Data[I]-Angles.Data[I-1]>1.e-10)Cuts.Add(Angles.Data[I]);Cuts.Add(Pi);
    auto Valid=[&](double T){return Within(Multiply(Exp(Scale(Axis,T)),Upper));};const V Prior=Unit(Tangent(CurrentPole,Axis));
    double Best=0,Distance=std::numeric_limits<double>::infinity(),Continuity=-std::numeric_limits<double>::infinity();
    for(int I=1;I<Cuts.N;++I)
    {
        const double Lo=Cuts.Data[I-1],Hi=Cuts.Data[I],Mid=(Lo+Hi)*.5;if(!Valid(Mid))continue;double T=Clamp(0,Lo,Hi);
        if(!Valid(T)){double Bad=T,Good=Mid;for(int K=0;K<40;++K){const double M0=(Bad+Good)*.5;if(Valid(M0))Good=M0;else Bad=M0;}T=Good;}
        const double D=std::abs(T),C0=Dot(Prior,Rotate(Exp(Scale(Axis,T)),DesiredPole));
        if(D<Distance-1.e-8||(std::abs(D-Distance)<1.e-8&&C0>Continuity)){Best=T;Distance=D;Continuity=C0;}
    }
    return Best;
}
struct Input
{
    V Shoulder,Elbow,Wrist;Q Parent,UpperQ,LowerQ,HandQ;SwingJoint Upper,Hand;HingeJoint Lower;
    Q Basis;V Forearm,Nearest,Requested,Normal,WallUp,ShoulderOut;double Sign,Reach;Q Desired;bool HasPrior;V BraceAxis,BracePole;
    // Immutable across every candidate/iteration in this complete brace fit.
    // Each expression is evaluated in the same order as its former call site.
    double UpperLength,LowerLength,MinimumReach;Q ParentInverse,ShoulderLeft;V OriginalPole;
};
struct Pose{V Elbow,Wrist;Q Upper,Lower,Hand;};
Pose SolveArm(const Input&I,const V&Target,const V&Pole,const Q&Hand)
{
    const double L1=I.UpperLength,L2=I.LowerLength;
    if(L1<1.e-8||L2<1.e-8)return {I.Elbow,I.Wrist,I.UpperQ,I.LowerQ,I.HandQ};
    const V Offset=Sub(Target,I.Shoulder);const double Distance=Hypot(Offset);const V Axis=Distance>1.e-8?Scale(Offset,1/Distance):Unit(Sub(I.Wrist,I.Shoulder));
    const double D=Clamp(Distance,Max(1.e-7,I.MinimumReach),L1+L2),Bend=M::acos(Clamp((D*D-L1*L1-L2*L2)/(2*L1*L2),-1,1));
    V P=Tangent(Pole,Axis);if(Hypot(P)<1.e-8)P=Tangent(I.OriginalPole,Axis);
    P=Hypot(P)>1.e-8?Unit(P):Unit(Cross(Axis,std::abs(Axis[0])<.8?V{1,0,0}:V{0,1,0}));
    const double Along=(L1*L1-L2*L2+D*D)/(2*D),Height=std::sqrt(Max(0,L1*L1-Along*Along));
    V Elbow=Add(I.Shoulder,Add(Scale(Axis,Along),Scale(P,Height))),UpperDir=Unit(Sub(Elbow,I.Shoulder));
    const V Normal=Unit(Scale(Cross(Axis,P),-1));Q Upper=Unit(Multiply(FromAxes(UpperDir,Normal,Cross(UpperDir,Normal)),I.Basis));
    const double TurnAngle=Swivel(I.Upper,I.ShoulderLeft,Upper,Axis,I.OriginalPole,P);
    if(std::abs(TurnAngle)>1.e-12){const Q Turn=Exp(Scale(Axis,TurnAngle));P=Rotate(Turn,P);Elbow=Add(I.Shoulder,Add(Scale(Axis,Along),Scale(P,Height)));Upper=Unit(Multiply(Turn,Upper));}
    const Q Lower=Unit(Multiply(Upper,HingeRelative(I.Lower,Bend))),Wrist=ProjectSwing(I.Hand,Lower,Hand);
    return {Elbow,Add(Elbow,Scale(Rotate(Lower,I.Forearm),L2)),Upper,Lower,Wrist};
}
struct Result{std::array<Q,3> Local;Pose World;V Point;double Gap;};
Result LegalArm(const Input&I,const Pose&P)
{
    Result R;R.Local[0]=ProjectSwing(I.Upper,Identity,Unit(Multiply(I.ParentInverse,P.Upper)));
    R.Local[1]=ProjectHinge(I.Lower,Identity,Unit(Multiply(Inverse(P.Upper),P.Lower)));
    R.Local[2]=ProjectSwing(I.Hand,Identity,Unit(Multiply(Inverse(P.Lower),P.Hand)));
    const V LowerOffset=Rotate(Inverse(P.Upper),Sub(P.Elbow,I.Shoulder)),HandOffset=Rotate(Inverse(P.Lower),Sub(P.Wrist,P.Elbow));
    R.World.Upper=Unit(Multiply(I.Parent,R.Local[0]));R.World.Lower=Unit(Multiply(R.World.Upper,R.Local[1]));R.World.Hand=Unit(Multiply(R.World.Lower,R.Local[2]));
    R.World.Elbow=Add(I.Shoulder,Rotate(R.World.Upper,LowerOffset));R.World.Wrist=Add(R.World.Elbow,Rotate(R.World.Lower,HandOffset));return R;
}
V Palm(const Q&Q0,double Sign){return Add(Scale(Rotate(Q0,V{Sign,0,0}),.0725),Scale(Rotate(Q0,V{0,1,0}),Sign==1?.020:-.025));}
Result Fit(const Input&I,double T,const Q&Orientation)
{
    const V Point=Add(I.Nearest,Scale(Sub(I.Requested,I.Nearest),T));V Wrist=Sub(Point,Palm(Orientation,I.Sign));Result R;
    for(int K=0;K<24;++K)
    {
        const V Off=Sub(Wrist,I.Shoulder);const double D=Hypot(Off),Margin=I.Reach*.01,Maximum=I.Reach*.996,X=(Maximum-D)/Margin;
        const double Safe=Maximum-Margin*(Max(X,0)+M::log1p(M::exp(-std::abs(X))));
        const V Axis=Unit(Off),Authored=Unit(Tangent(Add(Scale(I.Normal,.65),I.ShoulderOut),Axis));
        const V Prior=I.HasPrior?Rotate(FromTo(I.BraceAxis,Axis),I.BracePole):Authored;
        const V Pole=Unit(Tangent(Add(Scale(Prior,.98),Scale(Authored,.02)),Axis));
        R=LegalArm(I,SolveArm(I,Add(I.Shoulder,Scale(Axis,Max(0,Safe))),Pole,Orientation));
        const V Error=Sub(Point,Add(R.World.Wrist,Palm(R.World.Hand,I.Sign)));if(Hypot(Error)<.0003)break;
        const V Next=Add(Wrist,Scale(Error,.35));if(Hypot(Sub(Next,Wrist))<1.e-7)break;Wrist=Next;
    }
    R.Point=Point;R.Gap=Hypot(Sub(Add(R.World.Wrist,Palm(R.World.Hand,I.Sign)),Point));return R;
}
Result Select(const Input&I)
{
    Result Best=Fit(I,1,I.Desired);
    if(Best.Gap>.003)
    {
        const Result Neutral=Fit(I,0,I.Desired);
        if(Neutral.Gap<Best.Gap){Best=Neutral;if(Neutral.Gap<.003){double Lo=0,Hi=1;for(int K=0;K<9;++K){const double T=(Lo+Hi)*.5;const Result Candidate=Fit(I,T,I.Desired);if(Candidate.Gap<.003){Lo=T;Best=Candidate;}else Hi=T;}}}
    }
    if(Best.Gap>.003)for(double Amount:{.4,.8,1.5,3.})
    {
        const V Finger=Unit(Sub(I.WallUp,Scale(I.Normal,Amount))),PalmAxis=Unit(Tangent(Scale(I.Normal,-I.Sign),Finger));
        const V X=Scale(Finger,I.Sign);const Q Orientation=FromAxes(X,PalmAxis,Cross(X,PalmAxis));const Result Candidate=Fit(I,0,Orientation);if(Candidate.Gap<Best.Gap)Best=Candidate;
    }
    return Best;
}
}
bool ArmFit(const double* In,int Count,double* Out,int OutputCount)
{
    using namespace ArmKernel;if(!In||!Out||Count!=96||OutputCount!=34)return false;for(int I=0;I<Count;++I)if(!std::isfinite(In[I]))return false;
    auto VAt=[&](int I){return V{In[I],In[I+1],In[I+2]};};auto QAt=[&](int I){return Q{In[I],In[I+1],In[I+2],In[I+3]};};
    Input I;I.Shoulder=VAt(0);I.Elbow=VAt(3);I.Wrist=VAt(6);I.Parent=QAt(9);I.UpperQ=QAt(13);I.LowerQ=QAt(17);I.HandQ=QAt(21);
    I.Upper={QAt(25),QAt(29),Identity,In[33],In[34],In[35]};I.Lower={VAt(36),QAt(42),In[39],In[40],In[41]};
    I.Hand={QAt(46),QAt(50),QAt(57),In[54],In[55],In[56]};I.Basis=QAt(61);I.Forearm=VAt(65);I.Nearest=VAt(68);I.Requested=VAt(71);I.Normal=VAt(74);I.WallUp=VAt(77);I.ShoulderOut=VAt(80);I.Sign=In[83];I.Reach=In[84];I.Desired=QAt(85);I.HasPrior=In[89]!=0;I.BraceAxis=VAt(90);I.BracePole=VAt(93);
    if(I.Upper.SinY<=0||I.Upper.SinZ<=0||I.Hand.SinY<=0||I.Hand.SinZ<=0||I.Reach<=0||I.Lower.Maximum<=0||!(I.Sign==1||I.Sign==-1))return false;
    I.OriginalPole=Sub(I.Elbow,I.Shoulder);I.UpperLength=Hypot(I.OriginalPole);I.LowerLength=Hypot(Sub(I.Wrist,I.Elbow));
    I.MinimumReach=std::sqrt(Max(0,I.UpperLength*I.UpperLength+I.LowerLength*I.LowerLength+2*I.UpperLength*I.LowerLength*M::cos(I.Lower.Maximum)));
    I.ParentInverse=Inverse(I.Parent);I.ShoulderLeft=Inverse(Multiply(I.Parent,I.Upper.C1));
    const Result R=Select(I);double Values[34];int At=0;auto Write=[&](const auto&A){for(double V0:A)Values[At++]=V0;};
    for(const Q&Q0:R.Local)Write(Q0);Write(R.World.Upper);Write(R.World.Lower);Write(R.World.Hand);Write(R.World.Elbow);Write(R.World.Wrist);Write(R.Point);Values[At++]=R.Gap;
    for(double Value:Values)if(!std::isfinite(Value))return false;std::copy(Values,Values+34,Out);return true;
}
}
#if defined(_MSC_VER)
#pragma float_control(pop)
#endif
