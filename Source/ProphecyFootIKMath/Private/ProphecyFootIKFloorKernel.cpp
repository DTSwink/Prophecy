#include "ProphecyFootIKFloorKernel.h"
#include "src/base/ieee754.h"
#include <array>
#include <cmath>
#include <cstring>
#include <limits>

#if defined(_MSC_VER)
#pragma float_control(precise, on, push)
#pragma float_control(except, on)
#pragma fenv_access(on)
#pragma fp_contract(off)
#endif

namespace ProphecyFootIKMath
{
namespace FloorKernel
{
constexpr int MaxTiles = 256;
constexpr int MaxCorners = 64;
constexpr int PolygonCapacity = 64;
constexpr double Epsilon = 1e-9;
constexpr double Infinity = std::numeric_limits<double>::infinity();
using V = std::array<double, 3>;

// ECMAScript min/max preserve zero signs and propagate NaN. Neither the STL
// helpers nor SIMD min/max have all of these semantics.
inline double Min(double A, double B)
{
    if (A < B) return A;
    if (B < A) return B;
    if (A == B) return A == 0.0 ? (std::signbit(A) || std::signbit(B) ? -0.0 : 0.0) : A;
    return std::numeric_limits<double>::quiet_NaN();
}
inline double Max(double A, double B)
{
    if (A > B) return A;
    if (B > A) return B;
    if (A == B) return A == 0.0 ? (std::signbit(A) && std::signbit(B) ? -0.0 : 0.0) : A;
    return std::numeric_limits<double>::quiet_NaN();
}
inline double Dot(const double* A, const double* B)
{
    // recovery.js reduce starts with +0. Keep that operation, including its
    // signed-zero effect, and do not contract these multiplies/adds.
    return ((0.0 + A[0] * B[0]) + A[1] * B[1]) + A[2] * B[2];
}

struct Cut { int Axis; double Bound; double Sign; };

bool Clip(const V* Input, int Count, const Cut& Plane, V* Output, int& OutputCount)
{
    OutputCount = 0;
    if (!Count) return true;
    V A = Input[Count - 1];
    double DA = Plane.Sign * (A[Plane.Axis] - Plane.Bound);
    for (int Index = 0; Index < Count; ++Index)
    {
        const V& B = Input[Index];
        const double DB = Plane.Sign * (B[Plane.Axis] - Plane.Bound);
        if ((DA >= 0.0) != (DB >= 0.0))
        {
            if (OutputCount == PolygonCapacity) return false;
            const double T = DA / (DA - DB);
            V& P = Output[OutputCount++];
            for (int Axis = 0; Axis < 3; ++Axis)
                P[Axis] = A[Axis] + (B[Axis] - A[Axis]) * T;
        }
        if (DB >= 0.0)
        {
            if (OutputCount == PolygonCapacity) return false;
            Output[OutputCount++] = B;
        }
        A = B;
        DA = DB;
    }
    return true;
}

// This is the canonical terrain.js single-tile floor query, including its
// own overlap test and empty-clip fallback. The outer world-frame test is a
// distinct calculation; algebraically combining them changes edge decisions.
bool TileFloor(const V& Ankle, const V* Shape, int CornerCount,
    const double* Bounds, double& Result)
{
    static constexpr int Faces[6][4] = {
        {0, 1, 3, 2}, {4, 6, 7, 5}, {0, 4, 5, 1},
        {2, 3, 7, 6}, {0, 2, 6, 4}, {1, 5, 7, 3}
    };
    double Y = -Infinity;
    for (int Box = 0; Box < CornerCount; Box += 8)
    {
        double X0 = Infinity, X1 = -Infinity, Z0 = Infinity, Z1 = -Infinity, MinY = Infinity;
        for (int Corner = Box; Corner < Box + 8; ++Corner)
        {
            const V& O = Shape[Corner];
            X0 = Min(X0, O[0]); X1 = Max(X1, O[0]);
            Z0 = Min(Z0, O[2]); Z1 = Max(Z1, O[2]); MinY = Min(MinY, O[1]);
        }
        const double LoX = Bounds[0] - Ankle[0], HiX = Bounds[1] - Ankle[0];
        const double LoZ = Bounds[2] - Ankle[2], HiZ = Bounds[3] - Ankle[2];
        if (X1 <= LoX + Epsilon || X0 >= HiX - Epsilon ||
            Z1 <= LoZ + Epsilon || Z0 >= HiZ - Epsilon) continue;
        Cut Cuts[4];
        int CutCount = 0;
        if (X0 < LoX) Cuts[CutCount++] = {0, LoX, 1.0};
        if (X1 > HiX) Cuts[CutCount++] = {0, HiX, -1.0};
        if (Z0 < LoZ) Cuts[CutCount++] = {2, LoZ, 1.0};
        if (Z1 > HiZ) Cuts[CutCount++] = {2, HiZ, -1.0};
        double Lowest = MinY;
        if (CutCount)
        {
            Lowest = Infinity;
            V Polygons[2][PolygonCapacity];
            for (const auto& Face : Faces)
            {
                for (int I = 0; I < 4; ++I) Polygons[0][I] = Shape[Box + Face[I]];
                int PolygonCount = 4, Buffer = 0;
                for (int I = 0; I < CutCount; ++I)
                {
                    int NextCount = 0;
                    if (!Clip(Polygons[Buffer], PolygonCount, Cuts[I], Polygons[1 - Buffer], NextCount)) return false;
                    Buffer = 1 - Buffer;
                    PolygonCount = NextCount;
                    if (!PolygonCount) break;
                }
                for (int I = 0; I < PolygonCount; ++I) Lowest = Min(Lowest, Polygons[Buffer][I][1]);
            }
        }
        // The local query's tile is at +0, rather than a unary negation.
        Y = Max(Y, 0.0 - Lowest);
    }
    Result = std::isfinite(Y) ? Y : Ankle[1];
    return true;
}

bool Evaluate(const double* Input,int TileCount,int CornerCount,const double* Ankle,double& Result)
{
    const double* Offsets = Input + 5 + 13 * TileCount;
    std::array<V, MaxCorners> Shape;
    const double* LastBasis = nullptr;
    double Best = -Infinity;
    for (int Tile = 0; Tile < TileCount; ++Tile)
    {
        const double* Record = Input + 5 + 13 * Tile;
        const double* U = Record + 3;
        const double* W = Record + 6;
        const double* Bounds = Record + 9;
        const V Delta = {Ankle[0] - Record[0], Ankle[1] - Record[1], Ankle[2] - Record[2]};
        const V Local = {Dot(Delta.data(), U), Delta[1], Dot(Delta.data(), W)};
        if (!LastBasis || std::memcmp(LastBasis, U, 6 * sizeof(double)) != 0)
        {
            for (int Corner = 0; Corner < CornerCount; ++Corner)
            {
                const double* O = Offsets + 3 * Corner;
                Shape[Corner] = {Dot(O, U), O[1], Dot(O, W)};
            }
            LastBasis = U;
        }
        bool Overlaps = false;
        for (int Box = 0; Box < CornerCount && !Overlaps; Box += 8)
        {
            double X0 = Infinity, X1 = -Infinity, Z0 = Infinity, Z1 = -Infinity;
            for (int Corner = Box; Corner < Box + 8; ++Corner)
            {
                const V& O = Shape[Corner];
                const double X = Local[0] + O[0], Z = Local[2] + O[2];
                X0 = Min(X0, X); X1 = Max(X1, X);
                Z0 = Min(Z0, Z); Z1 = Max(Z1, Z);
            }
            Overlaps = X1 > Bounds[0] + Epsilon && X0 < Bounds[1] - Epsilon &&
                Z1 > Bounds[2] + Epsilon && Z0 < Bounds[3] - Epsilon;
        }
        if (Overlaps)
        {
            double Floor;
            if (!TileFloor(Local, Shape.data(), CornerCount, Bounds, Floor)) return false;
            Best = Max(Best, Record[1] + Floor);
        }
    }
    Result=std::isfinite(Best)?Best:Ankle[1];return true;
}
double Hypot3(const V& A)
{
    const double A0=std::abs(A[0]),A1=std::abs(A[1]),A2=std::abs(A[2]);
    const double Maximum=Max(Max(0.0,A0),Max(A1,A2));
    if(Maximum==0.0)return 0.0;
    const double X=A0/Maximum,Y=A1/Maximum,Z=A2/Maximum;
    const double X2=X*X,Y2=Y*Y,Compensation=(X2+Y2)-X2-Y2,Z2=Z*Z-Compensation;
    return std::sqrt(X2+Y2+Z2)*Maximum;
}
double Hypot2(double A,double B)
{
    A=std::abs(A);B=std::abs(B);const double Maximum=Max(Max(0.0,A),B);
    if(Maximum==0.0)return 0.0;const double X=A/Maximum,Y=B/Maximum;
    return std::sqrt(X*X+Y*Y)*Maximum;
}
using Q=std::array<double,4>;
using Axes=std::array<V,3>;
double Hypot4(const Q& A)
{
    Q Values;double Maximum=0;
    for(int I=0;I<4;++I){Values[I]=std::abs(A[I]);Maximum=Max(Maximum,Values[I]);}
    if(Maximum==0)return 0;
    double Sum=0,Correction=0;
    for(int I=0;I<4;++I){const double X=Values[I]/Maximum,Summand=X*X-Correction,Preliminary=Sum+Summand;Correction=(Preliminary-Sum)-Summand;Sum=Preliminary;}
    return std::sqrt(Sum)*Maximum;
}
Q Slerp(const Q& A,const Q& B0,double T)
{
    namespace M=v8::base::ieee754;
    Q B=B0;double C=(((0.0+A[0]*B[0])+A[1]*B[1])+A[2]*B[2])+A[3]*B[3];
    if(C<0){for(double& X:B)X=X*-1;C=-C;}
    Q Result;
    if(C>.9995)
    {
        for(int I=0;I<4;++I)Result[I]=A[I]*(1-T)+B[I]*T;
        const double N=Hypot4(Result),Scale=1.0/(N==0.0?1.0:N);
        for(double& X:Result)X=X*Scale;return Result;
    }
    const double Theta=M::acos(Max(-1.0,Min(1.0,C))),S=M::sin(Theta);
    const double AS=M::sin((1-T)*Theta)/S,BS=M::sin(T*Theta)/S;
    for(int I=0;I<4;++I)Result[I]=A[I]*AS+B[I]*BS;
    return Result;
}
V Add(const V& A,const V& B){return {A[0]+B[0],A[1]+B[1],A[2]+B[2]};}
V Scale(const V& A,double S){return {A[0]*S,A[1]*S,A[2]*S};}
V Cross(const V& A,const V& B){return {A[1]*B[2]-A[2]*B[1],A[2]*B[0]-A[0]*B[2],A[0]*B[1]-A[1]*B[0]};}
V Rotate(const Q& Q0,const V& P)
{
    const double X=2*(Q0[1]*P[2]-Q0[2]*P[1]),Y=2*(Q0[2]*P[0]-Q0[0]*P[2]),Z=2*(Q0[0]*P[1]-Q0[1]*P[0]);
    return {P[0]+(X*Q0[3]+Q0[1]*Z-Q0[2]*Y),P[1]+(Y*Q0[3]+Q0[2]*X-Q0[0]*Z),P[2]+(Z*Q0[3]+Q0[0]*Y-Q0[1]*X)};
}
Axes ToAxes(const Q& Q0)
{
    const double X=Q0[0],Y=Q0[1],Z=Q0[2],W=Q0[3];
    return {V{1-2*(Y*Y+Z*Z),2*(X*Y+W*Z),2*(X*Z-W*Y)},V{2*(X*Y-W*Z),1-2*(X*X+Z*Z),2*(Y*Z+W*X)},V{2*(X*Z+W*Y),2*(Y*Z-W*X),1-2*(X*X+Y*Y)}};
}
// Canonical K.geometry -> S.footPoints, including the world toe addition and
// subsequent subtraction. Eliminating that round trip changes edge decisions.
void Shoe(const V& BaseFoot,const V& ToeLocal,double Sign,const Q& Foot,const Q& Toe,double* Output)
{
    const V WorldToe=Add(BaseFoot,Rotate(Foot,ToeLocal));
    const V Delta={WorldToe[0]-BaseFoot[0],WorldToe[1]-BaseFoot[1],WorldToe[2]-BaseFoot[2]};
    const Axes A=ToAxes(Foot),B=ToAxes(Toe);
    const V Forward=Scale(A[1],Dot(A[1].data(),Delta.data())<0?-1.0:1.0),Up=Scale(A[0],Sign);
    const V ToeForward=Scale(B[0],Dot(B[0].data(),Forward.data())<0?-1.0:1.0),ToeUp=Scale(B[1],Sign);
    const V Crossed=Cross(ToeForward,ToeUp);const double N=Hypot3(Crossed);
    const V ToeSide=Scale(Crossed,1.0/(N==0.0?1.0:N));
    int At=0;
    const auto Corners=[&](const V& Centre,const V& F,const V& Side,const V& U,const V& D)
    {
        for(double X:{-1.0,1.0})for(double Y:{-1.0,1.0})for(double Z:{-1.0,1.0})
        {
            const V P=Add(Add(Add(Centre,Scale(F,X*D[0]/2)),Scale(Side,Y*D[1]/2)),Scale(U,Z*D[2]/2));
            for(double Value:P)Output[At++]=Value;
        }
    };
    Corners(Add(Add(Delta,Scale(Forward,-.0875)),Scale(Up,-.006)),Forward,A[2],Up,{.175,.120,.051});
    Corners(Add(Add(Delta,Scale(ToeForward,.024)),Scale(ToeUp,-.006)),ToeForward,ToeSide,ToeUp,{.048,.120,.049});
}
}

bool TerrainFloor(const double* Input, int Count, double* Output, int OutputCount)
{
    using namespace FloorKernel;
    if (!Input || !Output || Count < 5 || OutputCount != 1) return false;
    const double RawTiles = Input[0], RawCorners = Input[1];
    if (!std::isfinite(RawTiles) || !std::isfinite(RawCorners) ||
        RawTiles < 0.0 || RawTiles > MaxTiles || RawCorners < 0.0 || RawCorners > MaxCorners) return false;
    const int TileCount = static_cast<int>(RawTiles), CornerCount = static_cast<int>(RawCorners);
    if (RawTiles != TileCount || RawCorners != CornerCount || CornerCount % 8 ||
        Count != 5 + 13 * TileCount + 3 * CornerCount) return false;
    for (int Index = 2; Index < Count; ++Index) if (!std::isfinite(Input[Index])) return false;
    for (int Tile = 0; Tile < TileCount; ++Tile)
    {
        const double* Bounds = Input + 5 + 13 * Tile + 9;
        if (Bounds[0] >= Bounds[1] || Bounds[2] >= Bounds[3]) return false;
    }

    return Evaluate(Input, TileCount, CornerCount, Input + 2, Output[0]);
}
// Floor input, then hip3 and reach; output is the complete 12-pass projection.
bool TerrainReach(const double* Input,int Count,double* Output,int OutputCount)
{
    using namespace FloorKernel;
    if(!Input||!Output||Count<9||OutputCount!=3)return false;
    const double RawTiles=Input[0],RawCorners=Input[1];
    if(!std::isfinite(RawTiles)||!std::isfinite(RawCorners)||RawTiles<0||RawTiles>MaxTiles||RawCorners<0||RawCorners>MaxCorners)return false;
    const int TileCount=static_cast<int>(RawTiles),CornerCount=static_cast<int>(RawCorners);
    if(RawTiles!=TileCount||RawCorners!=CornerCount||CornerCount%8||Count!=9+13*TileCount+3*CornerCount)return false;
    for(int I=2;I<Count;++I)if(!std::isfinite(Input[I]))return false;
    for(int I=0;I<TileCount;++I){const double* B=Input+5+13*I+9;if(B[0]>=B[1]||B[2]>=B[3])return false;}
    const double* Hip=Input+Count-4;const double Reach=Input[Count-1];if(Reach<0)return false;
    V P={Input[2],Input[3],Input[4]},Last={};double LastFloor=0;bool HasLast=false;
    for(int Pass=0;Pass<12;++Pass)
    {
        const V D={P[0]-Hip[0],P[1]-Hip[1],P[2]-Hip[2]};
        if(Hypot3(D)>Reach)
        {
            const double N=Hypot3(D),Scale=1.0/(N==0.0?1.0:N);
            for(int I=0;I<3;++I)P[I]=Hip[I]+(D[I]*Scale)*Reach;
        }
        double Floor;
        if(HasLast&&std::memcmp(P.data(),Last.data(),sizeof(P))==0)Floor=LastFloor;
        else {if(!Evaluate(Input,TileCount,CornerCount,P.data(),Floor))return false;Last=P;LastFloor=Floor;HasLast=true;}
        P[1]=Max(P[1],Floor);
        const double DY=P[1]-Hip[1],Horizontal=Hypot2(P[0]-Hip[0],P[2]-Hip[2]);
        const double Radius=std::sqrt(Max(0.0,Reach*Reach-DY*DY));
        if(Horizontal>Radius)
        {
            P[0]=Hip[0]+(P[0]-Hip[0])*Radius/Horizontal;
            P[2]=Hip[2]+(P[2]-Hip[2])*Radius/Horizontal;
        }
    }
    for(double X:P)if(!std::isfinite(X))return false;
    for(int I=0;I<3;++I)Output[I]=P[I];return true;
}

bool TerrainRotationClearance(const double* Input,int Count,double* Output,int OutputCount)
{
    using namespace FloorKernel;
    if(!Input||!Output||Count<31||OutputCount!=1)return false;
    if(!std::isfinite(Input[0])||Input[0]<0||Input[0]>MaxTiles||Input[1]!=16)return false;
    const int Tiles=static_cast<int>(Input[0]),Prefix=5+13*Tiles;
    if(Input[0]!=Tiles||Count!=Prefix+26)return false;
    for(int I=2;I<Count;++I)if(!std::isfinite(Input[I]))return false;
    for(int I=0;I<Tiles;++I){const double* B=Input+5+13*I+9;if(B[0]>=B[1]||B[2]>=B[3])return false;}
    const double* P=Input+Prefix;
    if(P[6]!=1&&P[6]!=-1)return false;
    if(P[24]<0||P[24]>1||(P[25]!=0&&P[25]!=1))return false;
    const V BaseFoot={P[0],P[1],P[2]},ToeLocal={P[3],P[4],P[5]};
    const Q FromFoot={P[7],P[8],P[9],P[10]},FromToe={P[11],P[12],P[13],P[14]},ToFoot={P[15],P[16],P[17],P[18]},ToToe={P[19],P[20],P[21],P[22]};
    const double Ceiling=P[23];
    std::array<double,5+13*MaxTiles+48> FloorInput;
    std::memcpy(FloorInput.data(),Input,Prefix*sizeof(double));
    bool Valid=true;
    const auto Clear=[&](double U)
    {
        Shoe(BaseFoot,ToeLocal,P[6],Slerp(FromFoot,ToFoot,U),Slerp(FromToe,ToToe,U),FloorInput.data()+Prefix);
        for(int I=Prefix;I<Prefix+48;++I)if(!std::isfinite(FloorInput[I])){Valid=false;return false;}
        double Floor;if(!Evaluate(FloorInput.data(),Tiles,16,Input+2,Floor)){Valid=false;return false;}
        return Floor<=Ceiling;
    };
    double Amount=P[24];
    if(P[25]==0)
    {
        Amount=1;
        for(int N=1;N<=16;++N)if(!Clear(N/16.0))
        {
            double Lo=(N-1)/16.0,Hi=N/16.0;
            for(int K=0;K<9;++K){const double Mid=(Lo+Hi)/2;if(Clear(Mid))Lo=Mid;else Hi=Mid;}
            Amount=Lo;break;
        }
    }
    else if(!Clear(Amount)&&Clear(0))
    {
        double Lo=0,Hi=Amount;
        for(int N=0;N<16;++N){const double Mid=(Lo+Hi)/2;if(Clear(Mid))Lo=Mid;else Hi=Mid;}
        Amount=Lo;
    }
    if(!Valid||!std::isfinite(Amount))return false;
    Output[0]=Amount;return true;
}
}

#if defined(_MSC_VER)
#pragma float_control(pop)
#endif
