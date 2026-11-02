#include "ProphecyFootIKLegKernel.h"
#include "src/base/ieee754.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <vector>

#if defined(_MSC_VER)
#pragma float_control(precise,on,push)
#pragma float_control(except,on)
#pragma fenv_access(on)
#pragma fp_contract(off)
#endif

namespace ProphecyFootIKMath
{
namespace LegKernel
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

// This batch is the unprofiled canonical slide leg path. It deliberately keeps
// the two-box shoe, each candidate order and every feasibility fallback.
using Axes=std::array<V,3>;
struct Plane{V Origin,U,Normal,W;std::array<double,4> Bounds;bool Finite;double Thickness;};
struct Pose{V Hip,Knee,Foot,Toe;Q HipQ,KneeQ,FootQ,ToeQ;};
struct Reference{double Upper,Lower,Reach;V Normal,UpperAxis,LowerAxis;Q HipQ,KneeQ;V KneeLocal,AnkleLocal,ToeLocal;};
struct Rotation{Q Foot,Toe;};
struct Input
{
    Q PelvisQ,ParentHipQ,HipConstraintLeft;Pose Initial;Reference Leg;
    SwingJoint Hip,Foot,Toe;HingeJoint Knee;V KneeAxisChild;
    V Point,WantedAxis,WantedPole,WallUp,WallNormal,Shift;Rotation Desired;
    bool HasPreviousPole,HasPreviousDrop,HasLastTravel;V PreviousAxis,PreviousPole;
    double PreviousDrop,LastTravel,Dt,Sign;Plane Active;std::vector<Plane> Surfaces;
};
struct Result{Pose Body;double Drop,Travel;V PoleAxis,Pole;};
Q Slerp(const Q&A,const Q& B0,double T)
{
    Q B=B0;double C=Dot(A,B);if(C<0){B=Scale(B,-1);C=-C;}
    if(C>.9995){Q R;for(int I=0;I<4;++I)R[I]=A[I]*(1-T)+B[I]*T;return Unit(R);}
    const double Theta=M::acos(Clamp(C,-1,1)),S=M::sin(Theta),AS=M::sin((1-T)*Theta)/S,BS=M::sin(T*Theta)/S;
    Q R;for(int I=0;I<4;++I)R[I]=A[I]*AS+B[I]*BS;return R;
}
Axes ToAxes(const Q&Q0)
{
    const double X=Q0[0],Y=Q0[1],Z=Q0[2],W=Q0[3];
    return {V{1-2*(Y*Y+Z*Z),2*(X*Y+W*Z),2*(X*Z-W*Y)},V{2*(X*Y-W*Z),1-2*(X*X+Z*Z),2*(Y*Z+W*X)},V{2*(X*Z+W*Y),2*(Y*Z-W*X),1-2*(X*X+Y*Y)}};
}
V Local(const Plane& P,const V& Point){const V D=Sub(Point,P.Origin);return {Dot(D,P.U),Dot(D,P.Normal),Dot(D,P.W)};}
V World(const Plane& P,const V& At){return Add(P.Origin,Add(Scale(P.U,At[0]),Add(Scale(P.Normal,At[1]),Scale(P.W,At[2]))));}
V Project(const Plane& P,const V& Point){V At=Local(P,Point);At[1]=0;return World(P,At);}
V Closest(const Plane& P,const V& Point){const V At=Local(P,Point);return World(P,V{Clamp(At[0],P.Bounds[0],P.Bounds[1]),0,Clamp(At[2],P.Bounds[2],P.Bounds[3])});}
bool Inside(const Plane& P,const V& At){return !(P.Finite&&At[1]<-P.Thickness-.04)&&At[0]>=P.Bounds[0]&&At[0]<=P.Bounds[1]&&At[2]>=P.Bounds[2]&&At[2]<=P.Bounds[3];}
double Smooth(double X){X=Clamp(X,0,1);return X*X*(3-2*X);}
Q Basis(V Direction,V Normal){Direction=Unit(Direction);Normal=Unit(Sub(Normal,Scale(Direction,Dot(Normal,Direction))));return FromAxes(Direction,Normal,Cross(Direction,Normal));}
Pose Solve(const Input&I,Pose P,const V&Target,const Rotation&Rotation0,const V&NormalRequest)
{
    const V Axis0=Unit(Sub(Target,P.Hip)),Pole0=Unit(Tangent(NormalRequest,Axis0));const Q InversePelvis=Inverse(I.PelvisQ);
    // Preserve the canonical pelvis-local roundtrip, including its rounding.
    const V AxisLocal=Rotate(InversePelvis,Axis0),PoleLocal=Rotate(InversePelvis,Pole0);
    const V Delta=Sub(Target,P.Hip);const double A=I.Leg.Upper,B=I.Leg.Lower;
    const double D=Clamp(Hypot(Delta),std::abs(A-B)+1.e-6,A+B-1.e-7);const V Axis=Unit(Delta);
    const V OriginalAxis=Rotate(I.PelvisQ,AxisLocal),OriginalPole=Rotate(I.PelvisQ,PoleLocal);
    const V Pole=Rotate(FromTo(OriginalAxis,Axis),OriginalPole),Normal=Unit(Cross(Axis,Pole));
    const double Along=(A*A-B*B+D*D)/(2*D),Bend=std::sqrt(Max(0,A*A-Along*Along));
    const V Knee=Add(P.Hip,Add(Scale(Axis,Along),Scale(Pole,Bend))),Foot=Add(P.Hip,Scale(Axis,D));
    const Q HQ=Multiply(Multiply(Basis(Sub(Knee,P.Hip),Normal),Inverse(Basis(I.Leg.UpperAxis,I.Leg.Normal))),I.Leg.HipQ);
    const Q KQ=Multiply(Multiply(Basis(Sub(Foot,Knee),Normal),Inverse(Basis(I.Leg.LowerAxis,I.Leg.Normal))),I.Leg.KneeQ);
    P.HipQ=Unit(HQ);P.KneeQ=Unit(KQ);P.FootQ=Unit(Rotation0.Foot);P.ToeQ=Unit(Rotation0.Toe);
    P.Knee=Add(P.Hip,Rotate(P.HipQ,I.Leg.KneeLocal));P.Foot=Add(P.Knee,Rotate(P.KneeQ,I.Leg.AnkleLocal));P.Toe=Add(P.Foot,Rotate(P.FootQ,I.Leg.ToeLocal));
    const double Angle=Swivel(I.Hip,I.HipConstraintLeft,P.HipQ,Axis0,Pole0,Pole0);
    if(std::abs(Angle)>1.e-10)
    {
        const Q Turn=Exp(Scale(Axis0,Angle));P.Knee=Add(P.Hip,Rotate(Turn,Sub(P.Knee,P.Hip)));
        P.HipQ=Multiply(Turn,P.HipQ);P.KneeQ=Multiply(Turn,P.KneeQ);
    }
    return P;
}
Pose ShoePose(const Input&I,Pose P,const Rotation&R)
{
    P.Toe=Add(P.Foot,Rotate(R.Foot,I.Leg.ToeLocal));P.FootQ=R.Foot;P.ToeQ=R.Toe;return P;
}
std::array<V,16> Corners(const Input&I,const Pose&P)
{
    const Axes A=ToAxes(P.FootQ),B=ToAxes(P.ToeQ);const V Delta=Sub(P.Toe,P.Foot);
    const V Forward=Scale(A[1],Dot(A[1],Delta)<0?-1:1),Up=Scale(A[0],I.Sign),Side=A[2];
    const V TF=Scale(B[0],Dot(B[0],Forward)<0?-1:1),TU=Scale(B[1],I.Sign),TS=Unit(Cross(TF,TU));
    std::array<V,16> Out;int At=0;
    auto Box=[&](const V&C,const V&F,const V&S,const V&U,const V&Size)
    {
        for(double X:{-1.,1.})for(double Y:{-1.,1.})for(double Z:{-1.,1.})
        {
            const double FA=X*Size[0]/2,SB=Y*Size[1]/2,UC=Z*Size[2]/2;
            Out[At++]={((C[0]+F[0]*FA)+S[0]*SB)+U[0]*UC,((C[1]+F[1]*FA)+S[1]*SB)+U[1]*UC,((C[2]+F[2]*FA)+S[2]*SB)+U[2]*UC};
        }
    };
    Box(Add(Add(Delta,Scale(Forward,-.0875)),Scale(Up,-.006)),Forward,Side,Up,V{.175,.120,.051});
    Box(Add(Add(Delta,Scale(TF,.024)),Scale(TU,-.006)),TF,TS,TU,V{.048,.120,.049});return Out;
}
V Lowest(const std::array<V,16>& C,const V& Normal)
{
    double Height=std::numeric_limits<double>::infinity();for(const V&P:C)Height=Min(Height,Dot(P,Normal));
    V Total{0,0,0};int Count=0;for(const V&P:C)if(Dot(P,Normal)<Height+1.e-8){Total=Add(Total,P);++Count;}return Scale(Total,1./Count);
}
V Constrain(const Input&I,const Pose&P,const V&Target,const std::array<V,16>& Corners0)
{
    const double Reach=I.Leg.Reach*.985,Minimum=Min(I.Leg.Reach*.27,Hypot(Sub(P.Foot,P.Hip)));V Result=Target;
    std::vector<std::array<V,16>> Projected(I.Surfaces.size());
    for(size_t J=0;J<I.Surfaces.size();++J)for(int K=0;K<16;++K){const V&O=Corners0[K];const Plane&S=I.Surfaces[J];Projected[J][K]={Dot(O,S.U),Dot(O,S.Normal),Dot(O,S.W)};}
    for(int Pass=0;Pass<12;++Pass)
    {
        const V Before=Result,V0=Sub(Result,P.Hip);const double Distance=Hypot(V0);
        if(Distance>Reach)Result=Add(P.Hip,Scale(Unit(V0),Reach));
        else if(Distance<Minimum){const V Axis=Distance>1.e-8?Unit(V0):Unit(Sub(P.Foot,P.Hip));Result=Add(P.Hip,Scale(Axis,Minimum));}
        for(size_t J=0;J<I.Surfaces.size();++J)
        {
            const Plane&S=I.Surfaces[J];const V Origin=Local(S,Result);double Penetration=0;
            for(const V&O:Projected[J]){const V At{Origin[0]+O[0],Origin[1]+O[1],Origin[2]+O[2]};if(Inside(S,At))Penetration=Max(Penetration,-At[1]);}
            if(Penetration>0)Result=Add(Result,Scale(S.Normal,Penetration+1.e-5));
        }
        if(Hypot(Sub(Result,Before))<1.e-8)break;
    }
    return Result;
}
Rotation Ankle(const Input&I,const Pose&P){const Q Relaxed=Multiply(P.KneeQ,I.Foot.Reference);return {Relaxed,Multiply(Relaxed,I.Toe.Reference)};}
Pose Contact(const Input&I,Pose P,const V&Wanted,const Rotation&Desired,const V&Pole,int Iterations=14)
{
    Rotation R=Desired;V Target=Wanted;
    const V InitialAxis=Unit(Sub(Wanted,P.Hip)),InitialPole=Unit(Tangent(Pole,InitialAxis));
    auto SolveCurrent=[&](){return Solve(I,P,Target,R,Rotate(FromTo(InitialAxis,Unit(Sub(Target,P.Hip))),InitialPole));};
    for(int K=0;K<Iterations;++K)
    {
        P=SolveCurrent();R=Ankle(I,P);const auto Shoe=Corners(I,ShoePose(I,P,R));const V Offset=Lowest(Shoe,I.Active.Normal),Fitted=Sub(Closest(I.Active,Add(Wanted,Offset)),Offset);
        const double Gap=Dot(Sub(Wanted,Fitted),I.Active.Normal),Capture=1-Smooth(Max(0,Gap)/.06);
        const V Candidate=Add(Wanted,Scale(I.Active.Normal,Dot(Sub(Fitted,Wanted),I.Active.Normal)*Capture));
        const V Safe=Constrain(I,P,Candidate,Shoe);const double Error=Hypot(Sub(Safe,Target));Target=Safe;
        if(K>1&&Error<1.e-7)break;
    }
    P=SolveCurrent();R=Ankle(I,P);return ShoePose(I,P,R);
}
V Bend(const Pose&P){const V Axis=Unit(Sub(P.Foot,P.Hip));return Unit(Tangent(Sub(P.Knee,P.Hip),Axis));}
bool WithinSwing(const SwingJoint&J,const Q& Parent,const Q& Child)
{
    const Q Relative=Unit(Multiply(Inverse(Multiply(Parent,J.C1)),Multiply(Child,J.C2)));const Parts P=Decompose(Relative);
    const double Y=P.Swing[1]/J.SinY,Z=P.Swing[2]/J.SinZ,Twist=2*M::atan2(P.Twist[0],P.Twist[3]);return Y*Y+Z*Z<=1+1.e-8&&std::abs(Twist)<=J.Twist+1.e-8;
}
bool WithinHinge(const HingeJoint&J,const Q& Parent,const Q& Child)
{
    const Q Relative=Unit(Multiply(Inverse(Parent),Child)),Delta=Positive(Unit(Multiply(Relative,Inverse(J.Reference))));
    const double Bend0=J.Idle+2*M::atan2(Dot(V{Delta[0],Delta[1],Delta[2]},J.Axis),Delta[3]);
    const Q Error=Multiply(Inverse(Relative),HingeRelative(J,Bend0));const double HingeError=2*M::atan2(Hypot(V{Error[0],Error[1],Error[2]}),std::abs(Error[3]));
    return Bend0>=J.Minimum-1.e-8&&Bend0<=J.Maximum+1.e-8&&HingeError<1.e-7;
}
double Penetration(const Input&I,const Pose&P,const std::array<V,16>& Shoe)
{
    double Result0=0;for(const Plane&S:I.Surfaces)for(const V&O:Shoe){const V At=Local(S,Add(P.Foot,O));if(Inside(S,At))Result0=Max(Result0,-At[1]);}return Result0;
}
bool Valid(const Input&I,const Pose&P)
{
    const double KneeGap=Dot(Sub(P.Knee,Project(I.Active,P.Knee)),I.WallNormal);
    const auto Shoe=Corners(I,P);const V Sole=Add(P.Foot,Lowest(Shoe,I.WallNormal));const double Gap=Dot(Sub(Sole,Project(I.Active,Sole)),I.WallNormal);
    if(KneeGap<.086||std::abs(Gap)>=.003||Penetration(I,P,Shoe)>.001)return false;
    if(I.HasPreviousPole)
    {
        const V Axis=Unit(Sub(P.Foot,P.Hip)),Transported=Rotate(FromTo(I.PreviousAxis,Axis),I.PreviousPole);
        if(Dot(Bend(P),Transported)<.98)return false;
    }
    for(const Plane&S:I.Surfaces){const V At=Local(S,P.Knee);if(Inside(S,At)&&At[1]<.086)return false;}
    return WithinSwing(I.Hip,I.ParentHipQ,P.HipQ)&&WithinHinge(I.Knee,P.HipQ,P.KneeQ)&&WithinSwing(I.Foot,P.KneeQ,P.FootQ)&&WithinSwing(I.Toe,P.FootQ,P.ToeQ);
}
Pose ReachShift(const Input&I,const Pose&Neutral,const V&ContactPoint,const V&NeutralAxis,const V&NeutralPole)
{
    auto Build=[&](double T,bool Probe=false)
    {
        if(T==0)return Neutral;
        const V Wanted=Add(ContactPoint,Scale(I.Shift,T)),Pole=Rotate(FromTo(NeutralAxis,Unit(Sub(Wanted,Neutral.Hip))),NeutralPole);
        return Contact(I,Neutral,Wanted,I.Desired,Pole,Probe?3:14);
    };
    auto IsValid=[&](const Pose&P,const Pose&Base){return Valid(I,P)&&Dot(Bend(P),Bend(Base))>.1;};
    const double Distance=Hypot(I.Shift);if(Distance<1.e-10)return Build(0);
    const double Margin=.03/Distance;const Pose Base=Build(0,true);const double End=1+2*Margin;const int Steps=int(std::ceil((Distance+.06)/.04));
    auto Feasible=[&](double T){return IsValid(Build(T,true),Base)||IsValid(Build(T),Base);};
    double Lo=0,Hi=End;
    for(int K=1;K<=Steps;++K){const double T=End*K/Steps;if(!Feasible(T)){Hi=T;break;}Lo=T;}
    if(Lo==End){const Pose P=Build(1);if(IsValid(P,Base))return P;Lo=0;}
    for(int K=0;K<9;++K){const double T=(Lo+Hi)*.5;if(Feasible(T))Lo=T;else Hi=T;}
    const double Allowed=Max(0,Lo-Margin),H=Max(Margin-std::abs(1-Allowed),0)/Margin,Amount=Max(0,Min(1,Allowed)-H*H*Margin/4);
    const Pose Exact=Build(Amount);if(IsValid(Exact,Base))return Exact;
    double Left=0,Right=Amount;Pose Best=Build(0);if(!IsValid(Best,Base))return Best;
    for(int K=0;K<10;++K){const double Mid=(Left+Right)*.5;const Pose P=Build(Mid);if(IsValid(P,Base)){Left=Mid;Best=P;}else Right=Mid;}return Best;
}
Result Select(const Input&I)
{
    auto Lowered=[&](double Amount){const V Wanted=Sub(I.Point,Scale(I.WallUp,Amount)),Axis=Unit(Sub(Wanted,I.Initial.Hip));return Contact(I,I.Initial,Wanted,I.Desired,Rotate(FromTo(I.WantedAxis,Axis),I.WantedPole));};
    Pose Neutral=Lowered(0);double Lower=0;
    if(!Valid(I,Neutral))
    {
        double Lo=0,Hi=0;Pose Best;bool HasBest=false;
        if(I.HasPreviousDrop&&I.PreviousDrop!=0){const Pose Candidate=Lowered(I.PreviousDrop);if(Valid(I,Candidate)){Hi=I.PreviousDrop;Best=Candidate;HasBest=true;}}
        if(!HasBest)for(int K=1;K<=16;++K)
        {
            const double Amount=I.Leg.Reach*K/24;
            for(double Sign:{1.,-1.}){const Pose Candidate=Lowered(Amount*Sign);if(Valid(I,Candidate)){Hi=Amount*Sign;Lo=I.Leg.Reach*(K-1)/24*Sign;Best=Candidate;HasBest=true;break;}}
            if(HasBest)break;
        }
        if(HasBest){for(int K=0;K<5;++K){const double Mid=(Lo+Hi)*.5;const Pose Candidate=Lowered(Mid);if(Valid(I,Candidate)){Hi=Mid;Best=Candidate;}else Lo=Mid;}Neutral=Best;Lower=Hi;}
    }
    if(I.HasPreviousDrop&&I.Dt>0&&Valid(I,Neutral))
    {
        const double Eased=I.PreviousDrop+Clamp(Lower-I.PreviousDrop,-I.Dt*.45,I.Dt*.45);const Pose Candidate=Lowered(Eased);
        if(Valid(I,Candidate)){Neutral=Candidate;Lower=Eased;}
    }
    const V Point=Sub(I.Point,Scale(I.WallUp,Lower)),Axis=Unit(Sub(Neutral.Foot,Neutral.Hip)),Pole=Bend(Neutral);
    Pose Goal=ReachShift(I,Neutral,Point,Axis,Pole);
    const double WantedTravel=Dot(Sub(Goal.Foot,Goal.Hip),I.WallUp);
    if(I.HasLastTravel&&I.Dt>0&&Valid(I,Goal))
    {
        const double Travel=I.LastTravel+Clamp(WantedTravel-I.LastTravel,-I.Dt*.8,I.Dt*.8);
        if(std::abs(Travel-WantedTravel)>1.e-8)
        {
            const V Target=Add(Goal.Foot,Scale(I.WallUp,Travel-WantedTravel)),TargetAxis=Unit(Sub(Target,Neutral.Hip));
            const Pose Candidate=Contact(I,Neutral,Target,I.Desired,Rotate(FromTo(Axis,TargetAxis),Pole));
            if(Valid(I,Candidate))Goal=Candidate;
            else
            {
                const V HeldTarget=Add(Goal.Foot,Scale(I.WallUp,I.LastTravel-WantedTravel)),HeldAxis=Unit(Sub(HeldTarget,Neutral.Hip));
                const Pose Held=Contact(I,Neutral,HeldTarget,I.Desired,Rotate(FromTo(Axis,HeldAxis),Pole));
                if(Valid(I,Held))Goal=Held;else if(Valid(I,Neutral))Goal=Neutral;
            }
        }
    }
    return {Goal,Lower,Dot(Sub(Goal.Foot,Goal.Hip),I.WallUp),Unit(Sub(Goal.Foot,Goal.Hip)),Bend(Goal)};
}
}
bool LegContact(const double* In,int Count,double* Out,int OutputCount)
{
    using namespace LegKernel;
    if(!In||!Out||Count<177||OutputCount!=33)return false;for(int K=0;K<Count;++K)if(!std::isfinite(In[K]))return false;
    const double PlaneCount=In[176];if(PlaneCount<0||PlaneCount>64||std::floor(PlaneCount)!=PlaneCount||Count!=177+int(PlaneCount)*18)return false;
    int At=0;auto Number=[&](){return In[At++];};auto ReadV=[&](){const V X{In[At],In[At+1],In[At+2]};At+=3;return X;};auto ReadQ=[&](){const Q X{In[At],In[At+1],In[At+2],In[At+3]};At+=4;return X;};
    auto ReadSwing=[&](bool Reference0){SwingJoint J;J.C1=ReadQ();J.C2=ReadQ();J.SinY=Number();J.SinZ=Number();J.Twist=Number();J.Reference=Reference0?ReadQ():Identity;return J;};
    auto ReadPlane=[&](){Plane P;P.Origin=ReadV();P.U=ReadV();P.Normal=ReadV();P.W=ReadV();for(double& X:P.Bounds)X=Number();P.Finite=Number()!=0;P.Thickness=Number();return P;};
    Input I;I.PelvisQ=ReadQ();I.ParentHipQ=ReadQ();I.Initial.Hip=ReadV();I.Initial.Knee=ReadV();I.Initial.Foot=ReadV();I.Initial.Toe=ReadV();I.Initial.HipQ=ReadQ();I.Initial.KneeQ=ReadQ();I.Initial.FootQ=ReadQ();I.Initial.ToeQ=ReadQ();
    I.Leg.Upper=Number();I.Leg.Lower=Number();I.Leg.Reach=Number();I.Leg.Normal=ReadV();I.Leg.UpperAxis=ReadV();I.Leg.LowerAxis=ReadV();I.Leg.HipQ=ReadQ();I.Leg.KneeQ=ReadQ();I.Leg.KneeLocal=ReadV();I.Leg.AnkleLocal=ReadV();I.Leg.ToeLocal=ReadV();
    I.Hip=ReadSwing(false);I.Knee.Axis=ReadV();I.KneeAxisChild=ReadV();I.Knee.Idle=Number();I.Knee.Minimum=Number();I.Knee.Maximum=Number();I.Knee.Reference=ReadQ();I.Foot=ReadSwing(true);I.Toe=ReadSwing(true);
    I.Point=ReadV();I.Desired.Foot=ReadQ();I.Desired.Toe=ReadQ();I.WantedAxis=ReadV();I.WantedPole=ReadV();I.WallUp=ReadV();I.WallNormal=ReadV();I.Shift=ReadV();
    I.HasPreviousPole=Number()!=0;I.PreviousAxis=ReadV();I.PreviousPole=ReadV();I.HasPreviousDrop=Number()!=0;I.PreviousDrop=Number();I.HasLastTravel=Number()!=0;I.LastTravel=Number();I.Dt=Number();I.Sign=Number();I.Active=ReadPlane();++At;
    for(int K=0;K<int(PlaneCount);++K)I.Surfaces.push_back(ReadPlane());if(At!=Count||!(I.Sign==1||I.Sign==-1)||I.Leg.Upper<=0||I.Leg.Lower<=0||I.Leg.Reach<=0)return false;
    for(const SwingJoint* J:{&I.Hip,&I.Foot,&I.Toe})if(J->SinY<=0||J->SinZ<=0)return false;
    I.HipConstraintLeft=Inverse(Multiply(I.ParentHipQ,I.Hip.C1));
    const Result R=Select(I);double Values[33];At=0;auto Write=[&](const auto& A){for(double X:A)Values[At++]=X;};
    Write(R.Body.HipQ);Write(R.Body.Knee);Write(R.Body.KneeQ);Write(R.Body.Foot);Write(R.Body.FootQ);Write(R.Body.Toe);Write(R.Body.ToeQ);Values[At++]=R.Drop;Values[At++]=R.Travel;Write(R.PoleAxis);Write(R.Pole);
    for(double X:Values)if(!std::isfinite(X))return false;std::copy(Values,Values+33,Out);return true;
}
}
#if defined(_MSC_VER)
#pragma float_control(pop)
#endif

