#include "ProphecyFootIKEntryKernel.h"
#include "src/base/ieee754.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <vector>
#include <cstring>

#if defined(_MSC_VER)
#pragma float_control(precise,on,push)
#pragma float_control(except,on)
#pragma fenv_access(on)
#pragma fp_contract(off)
#endif

namespace ProphecyFootIKMath
{
namespace EntryKernel
{
namespace M=v8::base::ieee754;
using V=std::array<double,3>;
using Q=std::array<double,4>;
constexpr Q Identity={0,0,0,1};
constexpr double Pi=3.141592653589793238462643383279502884;
double Max(double A,double B){if(A>B)return A;if(B>A)return B;if(A==B)return A==0?(std::signbit(A)&&std::signbit(B)?-0.:0.):A;return std::numeric_limits<double>::quiet_NaN();}
double Min(double A,double B){if(A<B)return A;if(B<A)return B;if(A==B)return A==0?(std::signbit(A)||std::signbit(B)?-0.:0.):A;return std::numeric_limits<double>::quiet_NaN();}
double Clamp(double X,double A,double B){return Max(A,Min(B,X));}
double Pow(double X,double Y){if(Y==2)return X*X;if(Y==.5)return std::sqrt(X+0.0);return std::pow(X,Y);}
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

// Fixed-node optimizer. All interiors have live=false and 0<u<1, therefore the
// canonical retireResidual() and final-endpoint project() branches are inactive.
using Variables=std::array<double,7>;
struct SwingJoint{Q C1,C2;double SinY,SinZ,Twist;};
struct HingeJoint{V Axis;double Idle,Maximum;Q Reference;};
struct Plane{V Origin,U,Normal,W;std::array<double,4> Bounds;bool Finite;double Thickness;};
constexpr int MaxPlanes=64,MaxCorners=32,MaxNodes=33;
struct Node
{
    double U;Q Parent;V Hip,KneeOffset,FootOffset;Q HipResidual,KneeResidual,FootResidual;
    Variables Wanted,Value;std::vector<V> Corners;std::vector<Plane> Planes;
    bool Cached=false;Variables Last;Q HipQ,KneeQ,FootQ,KneeRotation,FootRotation;
    V KneePoint,FootPoint;std::array<V,MaxCorners> WorldCorners;
};
struct Context{SwingJoint Hip,Foot;HingeJoint Knee;bool Quality;std::vector<Node> Nodes;};
Variables Project(Variables Value)
{
    Value[2]=Clamp(Value[2],-1,1);Value[3]=Clamp(Value[3],0,1);Value[6]=Clamp(Value[6],-1,1);
    for(int I:{0,4}){const double R=Hypot(std::array<double,2>{Value[I],Value[I+1]});if(R>1){Value[I]/=R;Value[I+1]/=R;}}
    return Value;
}
Q JointRotation(const SwingJoint& Joint,const Variables& Value,int At=0)
{
    const double Y=Value[At]*Joint.SinY,Z=Value[At+1]*Joint.SinZ;
    return Unit(Multiply(Multiply(Joint.C1,Multiply(Q{0,Y,Z,std::sqrt(Max(0,1-Y*Y-Z*Z))},
        Exp(V{Value[At+2]*Joint.Twist,0,0}))),Inverse(Joint.C2)));
}
Q HingeRelative(const HingeJoint& Joint,double Bend)
{
    return Unit(Multiply(Exp(Scale(Joint.Axis,Bend-Joint.Idle)),Joint.Reference));
}
bool Same(double A,double B){return std::memcmp(&A,&B,sizeof(double))==0;}
bool Same3(const Variables&A,const Variables&B,int At){return Same(A[At],B[At])&&Same(A[At+1],B[At+1])&&Same(A[At+2],B[At+2]);}
void Geometry(const Context& C,Node& N,const Variables& Value)
{
    const bool HipChanged=!N.Cached||!Same3(N.Last,Value,0),KneeChanged=!N.Cached||!Same(N.Last[3],Value[3]),FootChanged=!N.Cached||!Same3(N.Last,Value,4);
    if(HipChanged)
    {
        const Q Rotation=Unit(Multiply(N.HipResidual,JointRotation(C.Hip,Value)));
        N.HipQ=Multiply(N.Parent,Rotation);N.KneePoint=Add(N.Hip,Rotate(N.HipQ,N.KneeOffset));
    }
    if(KneeChanged)N.KneeRotation=Unit(Multiply(N.KneeResidual,HingeRelative(C.Knee,Value[3]*C.Knee.Maximum)));
    if(HipChanged||KneeChanged){N.KneeQ=Multiply(N.HipQ,N.KneeRotation);N.FootPoint=Add(N.KneePoint,Rotate(N.KneeQ,N.FootOffset));}
    if(FootChanged)N.FootRotation=Unit(Multiply(N.FootResidual,JointRotation(C.Foot,Value,4)));
    if(HipChanged||KneeChanged||FootChanged)
    {
        N.FootQ=Multiply(N.KneeQ,N.FootRotation);
        for(size_t I=0;I<N.Corners.size();++I)N.WorldCorners[I]=Add(N.FootPoint,Rotate(N.FootQ,N.Corners[I]));
        N.Last=Value;N.Cached=true;
    }
}
struct Errors
{
    double Shoe=0,Knee=0;
    std::array<double,MaxPlanes*2> Constraints{};
    int Count=0;
};
V Local(const Plane& P,const V& Point){const V D=Sub(Point,P.Origin);return {Dot(D,P.U),Dot(D,P.Normal),Dot(D,P.W)};}
bool Inside(const Plane& P,const V& Point)
{
    return !(P.Finite&&Point[1]<-P.Thickness-.04)&&Point[0]>=P.Bounds[0]&&Point[0]<=P.Bounds[1]&&Point[2]>=P.Bounds[2]&&Point[2]<=P.Bounds[3];
}
Errors EvaluateGeometry(const Context& C,Node& N,const Variables& Value)
{
    Geometry(C,N,Value);Errors E;
    for(const Plane& P:N.Planes)
    {
        double Shoe=0,Knee=0;
        for(size_t I=0;I<N.Corners.size();++I)
        {
            const V D=Sub(N.WorldCorners[I],P.Origin);const double Y=Dot(D,P.Normal),Depth=.012-Y;
            // A corner which cannot increase this plane's positive maximum
            // has no effect on either the cost or correction constraints.
            // Preserve unordered values on the full path; no tolerance is used.
            if(Depth<=Shoe||(P.Finite&&Y<-P.Thickness-.04))continue;
            const V At{Dot(D,P.U),Y,Dot(D,P.W)};if(!Inside(P,At))continue;
            E.Shoe=Max(E.Shoe,Depth);Shoe=Max(Shoe,Depth);
        }
        const V At=Local(P,N.KneePoint);
        if(Inside(P,At)){E.Knee=Max(E.Knee,.085-At[1]);Knee=Max(Knee,.085-At[1]);}
        E.Constraints[E.Count++]=Shoe;E.Constraints[E.Count++]=Knee;
    }
    E.Shoe=Max(0,E.Shoe);E.Knee=Max(0,E.Knee);return E;
}
Variables Correct(const Context& C,Node& N,Variables Value)
{
    // Exact correct(c,input) defaults: margin=.012, iterations=18.
    auto Cost=[](const Errors& E){double Sum=0;for(int I=0;I<E.Count;++I){const double X=Max(0,E.Constraints[I]+(I%2?0:.012-.012));Sum=Sum+X*X;}return Sum;};
    for(int Step=0;Step<18;++Step)
    {
        const Errors Base=EvaluateGeometry(C,N,Value);std::array<double,MaxPlanes*2> Error{};
        double Maximum=-std::numeric_limits<double>::infinity();
        for(int J=0;J<Base.Count;++J){Error[J]=Max(0,Base.Constraints[J]+(J%2?0:.012-.012));Maximum=Max(Maximum,Error[J]);}
        if(Maximum<1.e-5)break;
        std::array<Variables,MaxPlanes*2> Rows{};constexpr double Epsilon=.0002;
        for(int Axis=0;Axis<7;++Axis)
        {
            Variables A=Value,B=Value;A[Axis]+=Epsilon;B[Axis]-=Epsilon;
            const Errors GA=EvaluateGeometry(C,N,Project(A)),GB=EvaluateGeometry(C,N,Project(B));
            for(int J=0;J<Base.Count;++J)Rows[J][Axis]=(GA.Constraints[J]-GB.Constraints[J])/(2*Epsilon);
        }
        // No fixed-size quadratic matrix on the stack; at the maximum supported
        // planes that would exceed the game worker's conservative stack budget.
        std::vector<double> H(size_t(Base.Count)*Base.Count);std::array<double,MaxPlanes*2> Lambda{};
        for(int J=0;J<Base.Count;++J)for(int K=0;K<Base.Count;++K)H[size_t(J)*Base.Count+K]=Dot(Rows[J],Rows[K]);
        for(int Sweep=0;Sweep<16;++Sweep)for(int J=0;J<Base.Count;++J)
        {
            if(!Error[J])continue;double Response=0;
            for(int K=0;K<Base.Count;++K)Response=Response+H[size_t(J)*Base.Count+K]*Lambda[K];
            Lambda[J]=Max(0,Lambda[J]+(Error[J]-Response)/(H[size_t(J)*Base.Count+J]+1.e-6));
        }
        Variables Delta{};
        for(int Axis=0;Axis<7;++Axis){double Sum=0;for(int J=0;J<Base.Count;++J)Sum=Sum+Lambda[J]*Rows[J][Axis];Delta[Axis]=-Sum;}
        const double Norm=Hypot(Delta);if(Norm>.25)for(double& X:Delta)X=X*.25/Norm;
        Variables Best=Value;double BestCost=Cost(Base);bool Changed=false;
        for(double Amount:{1.,.5,.25,.125})
        {
            Variables Candidate;for(int J=0;J<7;++J)Candidate[J]=Value[J]+Delta[J]*Amount;Candidate=Project(Candidate);
            const double Score=Cost(EvaluateGeometry(C,N,Candidate));
            if(Score<BestCost){Best=Candidate;BestCost=Score;Changed=true;}
        }
        if(!Changed)break;Value=Best;
    }
    return Value;
}
double Cost(const Context&C,Node& N,const Variables& Value,const Node& Previous,const Node& Next,double Weight,double Ceiling=std::numeric_limits<double>::infinity())
{
    double Regularity=0;
    for(int J=0;J<7;++J)
    {
        const double A=Value[J]-N.Wanted[J],B=Value[J]-Previous.Value[J],D=Value[J]-Next.Value[J];
        Regularity=Regularity+A*A*.002+B*B*4+D*D*4;
    }
    // Positive obstacle penalties can only increase this lower bound. A tie
    // also cannot win the canonical strict-less comparison. Unordered values
    // retain the original geometry path. Memo state has no effect on its math.
    if(Regularity>=Ceiling)return Regularity;
    const Errors E=EvaluateGeometry(C,N,Value);
    return Weight*(E.Shoe*E.Shoe+E.Knee*E.Knee)+Regularity;
}
void Optimize(Context& C)
{
    const int N=int(C.Nodes.size())-1,Passes=C.Quality?240:96;
    for(int Iteration=0;Iteration<Passes;++Iteration)
    {
        // V8's current Math.pow delegates these finite, positive arguments to
        // the same platform pow as the native compatibility module.
        const double Weight=1000*Pow(100.,double(Iteration)/(Passes-1));
        for(int P=1;P<N;++P)
        {
            const int I=Iteration%2?P:N-P;Node& Current=C.Nodes[I];Variables Best=Current.Value;
            double BestCost=Cost(C,Current,Best,C.Nodes[I-1],C.Nodes[I+1],Weight);
            for(int Refine=0;Refine<4;++Refine)
            {
                const double Step=.12*Pow(C.Quality?.993:.982,Iteration)*Pow(.5,Refine);
                for(int Axis=0;Axis<7;++Axis)for(double Sign:{-1.,1.})
                {
                    Variables Candidate=Best;Candidate[Axis]+=Step*Sign;Candidate=Project(Candidate);
                    const double Score=Cost(C,Current,Candidate,C.Nodes[I-1],C.Nodes[I+1],Weight,BestCost);
                    if(Score<BestCost){Best=Candidate;BestCost=Score;}
                }
            }
            Current.Value=Best;
        }
    }
    for(int I=1;I<N;++I)C.Nodes[I].Value=Correct(C,C.Nodes[I],C.Nodes[I].Value);
}
}
bool EntrySolve(const double* In,int Count,double* Out,int OutputCount)
{
    using namespace EntryKernel;
    if(!In||!Out||Count<33)return false;
    for(int I=0;I<Count;++I)if(!std::isfinite(In[I]))return false;
    if((In[0]!=0&&In[0]!=1)||(In[1]!=25&&In[1]!=33)||OutputCount!=int(In[1])*7)return false;
    Context C;C.Quality=In[0]!=0;const int NodeCount=int(In[1]);if(NodeCount!=(C.Quality?33:25))return false;
    int At=2;
    auto Number=[&](){return In[At++];};
    auto ReadV=[&](){const V Value{In[At],In[At+1],In[At+2]};At+=3;return Value;};
    auto ReadQ=[&](){const Q Value{In[At],In[At+1],In[At+2],In[At+3]};At+=4;return Value;};
    auto ReadJoint=[&](){SwingJoint J;J.C1=ReadQ();J.C2=ReadQ();J.SinY=Number();J.SinZ=Number();J.Twist=Number();return J;};
    C.Hip=ReadJoint();C.Knee.Axis=ReadV();C.Knee.Idle=Number();C.Knee.Maximum=Number();C.Knee.Reference=ReadQ();C.Foot=ReadJoint();
    if(C.Hip.SinY<=0||C.Hip.SinZ<=0||C.Foot.SinY<=0||C.Foot.SinZ<=0||C.Knee.Maximum<=0)return false;
    C.Nodes.reserve(NodeCount);
    for(int Index=0;Index<NodeCount;++Index)
    {
        if(At+42>Count)return false;Node N;N.U=Number();N.Parent=ReadQ();N.Hip=ReadV();N.KneeOffset=ReadV();N.FootOffset=ReadV();N.HipResidual=ReadQ();N.KneeResidual=ReadQ();N.FootResidual=ReadQ();
        for(double& X:N.Wanted)X=Number();for(double& X:N.Value)X=Number();
        const double Corners=Number(),Planes=Number();
        if(Corners<0||Corners>MaxCorners||std::floor(Corners)!=Corners||Planes<0||Planes>MaxPlanes||std::floor(Planes)!=Planes)return false;
        if(At+int(Corners)*3+int(Planes)*18>Count)return false;
        if(Index>0&&Index<NodeCount-1&&!(N.U>0&&N.U<1))return false;
        N.Corners.reserve(int(Corners));for(int I=0;I<int(Corners);++I)N.Corners.push_back(ReadV());
        N.Planes.reserve(int(Planes));for(int I=0;I<int(Planes);++I)
        {
            Plane P;P.Origin=ReadV();P.U=ReadV();P.Normal=ReadV();P.W=ReadV();for(double& X:P.Bounds)X=Number();
            const double Finite=Number();if(Finite!=0&&Finite!=1)return false;P.Finite=Finite!=0;P.Thickness=Number();N.Planes.push_back(P);
        }
        C.Nodes.push_back(std::move(N));
    }
    if(At!=Count)return false;Optimize(C);
    for(const Node& N:C.Nodes)for(double X:N.Value)if(!std::isfinite(X))return false;
    At=0;for(const Node& N:C.Nodes)for(double X:N.Value)Out[At++]=X;return true;
}
}
#if defined(_MSC_VER)
#pragma float_control(pop)
#endif

