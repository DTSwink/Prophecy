#pragma once
// Standalone double-precision transport for the extracted UE numerical kernel.
// No Unreal libraries, UObject state, physics simulation, or editor dependency.
#include <array>
#include <vector>
#include <cmath>
#include <algorithm>
#include <cstdint>
#include <utility>
using int32=int32_t; using uint8=uint8_t; using FName=const char*;
#define TEXT(x) x
#define UE_ARRAY_COUNT(x) (sizeof(x)/sizeof((x)[0]))
constexpr double UE_PI=3.14159265358979323846, UE_DOUBLE_SMALL_NUMBER=1.e-8;
#define MoveTemp(x) std::move(x)
template<class T,size_t N>using TStaticArray=std::array<T,N>;
struct FVector {
 double X=0,Y=0,Z=0;
 FVector()=default; FVector(double x,double y,double z):X(x),Y(y),Z(z){}
 FVector operator+(FVector b)const{return {X+b.X,Y+b.Y,Z+b.Z};}
 FVector operator-(FVector b)const{return {X-b.X,Y-b.Y,Z-b.Z};}
 FVector operator-()const{return {-X,-Y,-Z};}
 FVector operator*(double s)const{return {X*s,Y*s,Z*s};}
 FVector operator/(double s)const{return *this*(1/s);}
 FVector& operator+=(FVector b){return *this=*this+b;}
 FVector& operator-=(FVector b){return *this=*this-b;}
 FVector& operator*=(double s){return *this=*this*s;}
 FVector& operator/=(double s){return *this=*this/s;}
 double Length()const{return std::sqrt(X*X+Y*Y+Z*Z);}
 static double DotProduct(FVector a,FVector b){return a.X*b.X+a.Y*b.Y+a.Z*b.Z;}
 static FVector CrossProduct(FVector a,FVector b){return {a.Y*b.Z-a.Z*b.Y,a.Z*b.X-a.X*b.Z,a.X*b.Y-a.Y*b.X};}
 static double Distance(FVector a,FVector b){return (a-b).Length();}
 static const FVector ZeroVector,ForwardVector,RightVector,UpVector;
};
inline const FVector FVector::ZeroVector={},FVector::ForwardVector={1,0,0},FVector::RightVector={0,1,0},FVector::UpVector={0,0,1};
struct FVector2D{double X,Y;FVector2D(double x,double y):X(x),Y(y){}double Length()const{return std::sqrt(X*X+Y*Y);}};
struct FQuat {
 double X=0,Y=0,Z=0,W=1;
 FQuat()=default;FQuat(double x,double y,double z,double w):X(x),Y(y),Z(z),W(w){}
 FQuat(FVector a,double t){double s=std::sin(t*.5);X=a.X*s;Y=a.Y*s;Z=a.Z*s;W=std::cos(t*.5);}
 FQuat operator*(const FQuat& b)const{return {W*b.X+X*b.W+Y*b.Z-Z*b.Y,W*b.Y-X*b.Z+Y*b.W+Z*b.X,W*b.Z+X*b.Y-Y*b.X+Z*b.W,W*b.W-X*b.X-Y*b.Y-Z*b.Z};}
 FQuat GetNormalized()const{double s=X*X+Y*Y+Z*Z+W*W;if(s<1.e-8)return {};s=1/std::sqrt(s);return {X*s,Y*s,Z*s,W*s};}
 FVector RotateVector(FVector v)const{FVector q(X,Y,Z),t=FVector::CrossProduct(q,v)*2;return v+t*W+FVector::CrossProduct(q,t);}
 static FQuat FindBetweenNormals(FVector a,FVector b){double w=1+FVector::DotProduct(a,b);FVector v;if(w>=1.e-6f)v=FVector::CrossProduct(a,b);else {w=0;FVector axis=(std::abs(a.X)>std::abs(a.Y)&&std::abs(a.X)>std::abs(a.Z))?FVector::RightVector:-FVector::ForwardVector;v=FVector::CrossProduct(a,axis);}return FQuat(v.X,v.Y,v.Z,w).GetNormalized();}
};
struct FTransform {
 FVector P;FQuat Q;
 FVector GetLocation()const{return P;}FQuat GetRotation()const{return Q;}
 void SetLocation(FVector p){P=p;}void SetTranslation(FVector p){P=p;}void SetRotation(FQuat q){Q=q;}void NormalizeRotation(){Q=Q.GetNormalized();}
 bool ContainsNaN()const{return !(std::isfinite(P.X)&&std::isfinite(P.Y)&&std::isfinite(P.Z)&&std::isfinite(Q.X)&&std::isfinite(Q.Y)&&std::isfinite(Q.Z)&&std::isfinite(Q.W));}
};
namespace FMath {
 template<class T> T Clamp(T x,T a,T b){return std::clamp(x,a,b);}
 template<class T> T Max(T a,T b){return std::max(a,b);}template<class T>T Min(T a,T b){return std::min(a,b);}
 template<class T>T Abs(T x){return std::abs(x);}inline double Sqrt(double x){return std::sqrt(x);}inline double Asin(double x){return std::asin(x);}
 inline double Pow(double x,double y){return std::pow(x,y);}inline double Exp(double x){return std::exp(x);}inline double Lerp(double a,double b,double t){return a+(b-a)*t;}
 inline double DegreesToRadians(double x){return x*UE_PI/180;}
 inline FVector VInterpConstantTo(FVector a,FVector b,float dt,float speed){auto d=b-a;double n=d.Length(),step=speed*dt;return n>step?(step>0?a+d/n*step:a):b;}
}
template<class T>struct TConstArrayView{const T* P;int32 N;int32 Num()const{return N;}const T&operator[](int32 i)const{return P[i];}};
template<class T>struct TArray:std::vector<T>{void Reset(int n){this->clear();this->reserve(n);}void Add(const T&v){this->push_back(v);}};
enum class EProphecyDoubleReachMode:uint8{Off,Left,Right,Both};
namespace ProphecyNativeReach {
struct FState{double Body[6]={};FVector Targets[2]={},Elbows[2]={};bool Active[2]={};};
bool Step(TConstArrayView<FTransform>,EProphecyDoubleReachMode,const FVector(&)[2],const float(&)[2],FState&,TArray<FTransform>&,double,double=1.0);
}
