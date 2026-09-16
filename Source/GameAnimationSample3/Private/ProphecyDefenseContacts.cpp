#include "ProphecyDefenseContacts.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"

namespace ProphecyDefense
{
namespace
{
float Dot(const FVector3f& A,const FVector3f& B) { return FVector3f::DotProduct(A,B); }
FVector3f Cross(const FVector3f& A,const FVector3f& B) { return FVector3f::CrossProduct(A,B); }
FVector3f Unit(const FVector3f& V) { return V/FMath::Max(V.Size(),1.e-12f); }
FVector3f SameSide(const FVector3f& A,const FVector3f& B) { return Dot(A,B)<0?-A:A; }
FVector3f Up(const FVector3f& V) { return V.Y<0?-V:V; }
FRows Proper(const FVector3f& F,const FVector3f& U)
{
    const auto Forward=Unit(F),Side=Unit(Cross(U,Forward));
    return {{Forward,Side,Unit(Cross(Forward,Side))}};
}
bool Floats(const TSharedPtr<FJsonObject>& O,const TCHAR* Name,float* Out,int32 Count)
{
    const TArray<TSharedPtr<FJsonValue>>* A=nullptr;
    if (!O->TryGetArrayField(Name,A) || A->Num()!=Count) return false;
    for (int32 I=0;I<Count;++I)
    {
        double V;if (!(*A)[I]->TryGetNumber(V) || !FMath::IsFinite(V)) return false;Out[I]=float(V);
        if (!FMath::IsFinite(Out[I])) return false;
    }
    return true;
}
// Match the reference's largest-candidate row-basis conversion. UE's generic
// conversion chooses a different branch near the float32 contact boundary.
FVector4f Quaternion(const FRows& R)
{
    const auto& A=R.V[0];const auto& B=R.V[1];const auto& C=R.V[2];
    const float D[]={1+A.X+B.Y+C.Z,1+A.X-B.Y-C.Z,1-A.X+B.Y-C.Z,1-A.X-B.Y+C.Z};
    int32 K=0;for (int32 I=1;I<4;++I) if (D[I]>D[K]) K=I;
    const FVector4f Choices[]={
        FVector4f(D[0],B.Z-C.Y,C.X-A.Z,A.Y-B.X),FVector4f(B.Z-C.Y,D[1],B.X+A.Y,C.X+A.Z),
        FVector4f(C.X-A.Z,B.X+A.Y,D[2],C.Y+B.Z),FVector4f(A.Y-B.X,C.X+A.Z,C.Y+B.Z,D[3])};
    auto Q=Choices[K]/(2*FMath::Max(FMath::Sqrt(FMath::Max(D[K],1.e-8f)),.1f));
    return Q/FMath::Max(FMath::Sqrt(Q.SizeSquared()),1.e-12f);
}
FRows Matrix(FVector4f Q)
{
    Q/=FMath::Max(FMath::Sqrt(Q.SizeSquared()),1.e-12f);
    const float W=Q.X,X=Q.Y,Y=Q.Z,Z=Q.W;
    return {{{1-2*(Y*Y+Z*Z),2*(X*Y+Z*W),2*(X*Z-Y*W)},
        {2*(X*Y-Z*W),1-2*(X*X+Z*Z),2*(Y*Z+X*W)},
        {2*(X*Z+Y*W),2*(Y*Z-X*W),1-2*(X*X+Y*Y)}}};
}
struct FSweep
{
    FVector3f Anchor0,Delta,Offset;FVector4f Q0,Q1;float Angle,Sine,Speed;
    FSweep(const FDefenseBox& A,const FDefenseBox& B,const FVector3f& Half,const FVector3f& O):Offset(O)
    {
        Anchor0=A.Center-Transform(O,A.Axes);Delta=B.Center-Transform(O,B.Axes)-Anchor0;
        Q0=Quaternion(A.Axes);Q1=Quaternion(B.Axes);
        float D=Q0.X*Q1.X+Q0.Y*Q1.Y+Q0.Z*Q1.Z+Q0.W*Q1.W;
        if (D<0) Q1=-Q1;
        D=FMath::Min(FMath::Abs(D),1.f);
        Angle=D>.9995f?0:FMath::Acos(D);Sine=FMath::Sin(Angle);
        const float Trace=Dot(A.Axes.V[0],B.Axes.V[0])+Dot(A.Axes.V[1],B.Axes.V[1])+Dot(A.Axes.V[2],B.Axes.V[2]);
        Speed=Delta.Size()+(Half.Size()+O.Size())*FMath::Acos(FMath::Clamp((Trace-1)*.5f,-1.f,1.f));
        // The CPU oracle computes its bound using the input axes, but samples
        // around anchors reconstructed from the cleaned quaternion axes.
        Anchor0=A.Center-Transform(O,Matrix(Q0));Delta=B.Center-Transform(O,Matrix(Q1))-Anchor0;
    }
    FDefenseBox At(float T) const
    {
        const auto Q=Angle==0?Q0+T*(Q1-Q0):
            (FMath::Sin((1-T)*Angle)/FMath::Max(Sine,1.e-8f))*Q0+(FMath::Sin(T*Angle)/FMath::Max(Sine,1.e-8f))*Q1;
        const auto R=Matrix(Q);return {Anchor0+T*Delta+Transform(Offset,R),R};
    }
};
}

bool FContactGeometry::Load(const FString& Filename,FString& Error)
{
    Count=BaseCount=0;FString Text;TSharedPtr<FJsonObject> Doc;
    if (!FFileHelper::LoadFileToString(Text,*Filename) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Doc) || !Doc)
    { Error=TEXT("Cannot read defense collider geometry: ")+Filename;return false; }
    const TArray<TSharedPtr<FJsonValue>>* Records=nullptr;double Version,Base;
    if (!Doc->TryGetNumberField(TEXT("version"),Version) || Version!=1 || !Doc->TryGetNumberField(TEXT("base_count"),Base)
        || (Base!=13 && Base!=14) || !Doc->TryGetArrayField(TEXT("colliders"),Records)
        || (Records->Num()!=int32(Base)+6 && !(Base==13 && Records->Num()==13)) || Records->Num()>MaxBoxes)
    { Error=TEXT("Unsupported defense collider layout.");return false; }
    for (int32 I=0;I<Records->Num();++I)
    {
        const auto O=(*Records)[I]->AsObject();FString Name;float Half[3],Center[3],Offset[3],Axes[9];double Bone=0;
        if (!O || !O->TryGetStringField(TEXT("name"),Name) || !Floats(O,TEXT("half"),Half,3) || !Floats(O,TEXT("center_offset"),Center,3)
            || (I<Base && (!O->TryGetNumberField(TEXT("bone"),Bone) || Bone<0 || Bone>=25 || Bone!=FMath::FloorToDouble(Bone)
                || !Floats(O,TEXT("offset"),Offset,3) || !Floats(O,TEXT("axes"),Axes,9))))
        { Error=TEXT("Invalid defense collider attachment.");return false; }
        if (Half[0]<=0 || Half[1]<=0 || Half[2]<=0) { Error=TEXT("Invalid collider half size.");return false; }
        auto& B=Boxes[I];B.Name=FName(Name);B.Half=Read(Half);B.CenterOffset=Read(Center);
        if (I<Base) { B.Bone=int32(Bone);B.BoneOffset=Read(Offset);B.LocalAxes=Rows(Axes); }
    }
    static const FName Extras[]={TEXT("hand_l"),TEXT("hand_r"),TEXT("foot_l"),TEXT("ball_l"),TEXT("foot_r"),TEXT("ball_r")};
    for (int32 I=int32(Base);I<Records->Num();++I) if (Boxes[I].Name!=Extras[I-int32(Base)]) { Error=TEXT("Unexpected end-effector collider order.");return false; }
    Count=Records->Num();BaseCount=int32(Base);Error.Reset();return true;
}

FDefenseBox FContactGeometry::BuildBox(const FPose& P,int32 I) const
{
    check(I>=0 && I<Count);
    if (I<BaseCount)
    {
        const auto& B=Boxes[I];auto R=P.R[B.Bone];
        if (B.Bone==8 || B.Bone==12)
        {
            const auto Segment=P.P[B.Bone+1]-P.P[B.Bone];const float Length=Segment.Size();
            if (Length>=1.e-8f)
            {
                const auto First=Segment*(B.BoneOffset.X<0?-1.f:1.f)/FMath::Max(Length,1.e-12f);
                auto Second=R.V[1]-Dot(R.V[1],First)*First;
                if (Second.Size()<1.e-8f) Second=R.V[2]-Dot(R.V[2],First)*First;
                Second=Unit(Second);auto Third=Unit(Cross(First,Second));
                if (Dot(Third,R.V[2])<0) { Second=-Second;Third=-Third; }
                R={{First,Second,Third}};
            }
        }
        FDefenseBox Out;Out.Center=P.P[B.Bone]+Transform(B.BoneOffset,R);
        for (int32 J=0;J<3;++J) Out.Axes.V[J]=Unit(Transform(B.LocalAxes.V[J],R));
        return Out;
    }
    const int32 Extra=I-BaseCount;
    if (Extra<2)
    {
        const int32 Hand=Extra?13:9;const auto& R=P.R[Hand];auto F=Unit(R.V[0]);
        const auto U=Unit(R.V[1]-Dot(R.V[1],F)*F);if (Extra) F=-F;
        return {P.P[Hand]+F*.0725f+U*(-.0025f),Proper(F,U)};
    }
    const int32 Foot=Extra>=4?23:19,Toe=Foot+1;
    const auto Forward=SameSide(P.R[Foot].V[1],P.P[Toe]-P.P[Foot]),Upward=Up(P.R[Foot].V[0]);
    if ((Extra&1)==0) return {P.P[Toe]-Forward*.0875f-Upward*.006f,Proper(Forward,Upward)};
    const auto TF=SameSide(P.R[Toe].V[0],Forward);auto TU=Up(P.R[Toe].V[1]);const auto Ref=P.R[Toe].V[2];
    const auto C=Cross(TF,TU);auto TS=C.Size()<1.e-6f?Ref:Unit(C);TS=SameSide(TS,Ref);TU=Up(Unit(Cross(TS,TF)));
    return {P.P[Toe]+TF*.024f-TU*.006f,Proper(TF,TU)};
}
void FContactGeometry::Build(const FPose& P,FDefenseBox* Out) const
{
    for (int32 I=0;I<Count;++I) Out[I]=BuildBox(P,I);
}
uint32 FContactGeometry::PresentMask(bool bDrawn) const
{
    uint32 Mask=0;for (int32 I=0;I<Count;++I) if (bDrawn || Boxes[I].Name!=TEXT("blade")) Mask|=1u<<I;return Mask;
}
uint32 FContactGeometry::BlockingMask(int32 Label,bool bDrawn) const
{
    uint32 Mask=0;
    for (int32 I=0;I<Count;++I)
    {
        const auto N=Boxes[I].Name;
        if (((Label==16 || Label==17) && bDrawn && N==TEXT("blade"))
            || ((Label==18 || Label==20 || Label==22) && (N==TEXT("upperarm_l") || N==TEXT("lowerarm_l") || N==TEXT("hand_l")))
            || ((Label==19 || Label==21 || Label==23) && (N==TEXT("upperarm_r") || N==TEXT("lowerarm_r") || N==TEXT("hand_r")))) Mask|=1u<<I;
    }
    return Mask;
}
float BoxGap(const FDefenseBox& A,const FVector3f& HA,const FDefenseBox& B,const FVector3f& HB)
{
    const auto Delta=B.Center-A.Center;float Gap=-std::numeric_limits<float>::infinity();
    for (int32 I=0;I<3;++I)
    {
        float RA=0,RB=0;
        for (int32 J=0;J<3;++J) { RA+=HB[J]*FMath::Abs(Dot(A.Axes.V[I],B.Axes.V[J]));RB+=HA[J]*FMath::Abs(Dot(B.Axes.V[I],A.Axes.V[J])); }
        Gap=FMath::Max(Gap,FMath::Abs(Dot(Delta,A.Axes.V[I]))-HA[I]-RA);
        Gap=FMath::Max(Gap,FMath::Abs(Dot(Delta,B.Axes.V[I]))-HB[I]-RB);
        for (int32 J=0;J<3;++J)
        {
            auto Axis=Cross(A.Axes.V[I],B.Axes.V[J]);const float N=Axis.Size();if (N<=1.e-8f) continue;Axis/=FMath::Max(N,1.e-12f);
            float R0=0,R1=0;for (int32 K=0;K<3;++K) { R0+=HA[K]*FMath::Abs(Dot(A.Axes.V[K],Axis));R1+=HB[K]*FMath::Abs(Dot(B.Axes.V[K],Axis)); }
            Gap=FMath::Max(Gap,FMath::Abs(Dot(Delta,Axis))-R0-R1);
        }
    }
    return Gap;
}
FContactPair SweepBoxes(const FDefenseBox& A0,const FDefenseBox& A1,const FVector3f& HA,const FVector3f& OA,
    const FDefenseBox& B0,const FDefenseBox& B1,const FVector3f& HB,const FVector3f& OB,int32 MaxIterations)
{
    constexpr float Epsilon=1.e-7f;const FSweep A(A0,A1,HA,OA),B(B0,B1,HB,OB);const float Speed=A.Speed+B.Speed;
    FContactPair Result;MaxIterations=FMath::Max(MaxIterations,1);
    for (int32 I=0;I<MaxIterations;++I)
    {
        Result.Iterations=I+1;Result.Gap=BoxGap(A.At(Result.Fraction),HA,B.At(Result.Fraction),HB);
        if (!FMath::IsFinite(Result.Gap) || !FMath::IsFinite(Speed)) break;
        if (Result.Gap<=Epsilon)
        {
            Result.bPossible=true;Result.bResolved=Result.Iterations<MaxIterations;Result.bConfirmed=Result.bResolved;return Result;
        }
        const float Next=Result.Fraction+FMath::Max(Result.Gap,0.f)/FMath::Max(Speed,1.e-12f);
        if (Speed<=1.e-12f || Next>=1)
        {
            Result.Fraction=1;Result.Gap=BoxGap(A1,HA,B1,HB);
            Result.bPossible=Result.Gap<=Epsilon;Result.bResolved=Result.Iterations<MaxIterations;
            Result.bConfirmed=Result.bPossible&&Result.bResolved;return Result;
        }
        Result.Fraction=Next;
    }
    Result.bPossible=true;Result.bConfirmed=false;Result.bResolved=false;return Result;
}
void FContactOrder::Include(const FContactPair& Pair,int32 Collider,bool bBlocking,double Start,double End)
{
    if (!Pair.bResolved) ++Unresolved;
    const double Time=Start+Pair.Fraction*(End-Start);
    if (bBlocking && Pair.bConfirmed && Time<BlockTime) { BlockTime=Time;BlockCollider=Collider;BlockFraction=Pair.Fraction; }
    if (!bBlocking && Pair.bPossible && Time<HarmTime) { HarmTime=Time;HarmCollider=Collider;HarmFraction=Pair.Fraction; }
    bProtected=FMath::IsFinite(BlockTime)&&BlockTime+2./8192.<HarmTime;
    bHarmful=FMath::IsFinite(HarmTime)&&!bProtected;
}
}
