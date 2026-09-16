#include "ProphecyDodgeLower.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"

namespace ProphecyDefense
{
namespace
{
FRows TransposeLower(const FRows& A)
{ return {{{A.V[0].X,A.V[1].X,A.V[2].X},{A.V[0].Y,A.V[1].Y,A.V[2].Y},{A.V[0].Z,A.V[1].Z,A.V[2].Z}}}; }
FRows MultiplyLower(const FRows& A,const FRows& B)
{ return {{Transform(A.V[0],B),Transform(A.V[1],B),Transform(A.V[2],B)}}; }
FRows RotationVector(const FVector3f& V)
{
    const float Angle=V.Size(),C=FMath::Cos(Angle),S=FMath::Sin(Angle);const auto N=Normalize(V);
    FRows R={{{1,0,0},{0,1,0},{0,0,1}}};
    for (auto& Row:R.V) Row=Row*C+FVector3f::CrossProduct(N,Row)*S+N*FVector3f::DotProduct(N,Row)*(1-C);
    return R;
}
struct FBox { FVector3f C,F,S,U; };
struct FFootBoxes { FBox Foot,Toe; };
FFootBoxes Boxes(int32 Leg,const FRows& R,float Toe,const FGeometry& G)
{
    FFootBoxes Out;const FVector3f T=Transform(G.ProjectionToeOffsets[Leg],R);
    auto& F=Out.Foot;F.U=R.V[0];F.F=R.V[1];F.S=R.V[2];
    if (FVector3f::DotProduct(F.F,T)<0) F.F=-F.F;if (F.U.Z<0) F.U=-F.U;
    F.C=T-F.F*.0875f-F.U*.006f;
    // axis_angle_to_row_matrix normalizes the axis independently of angle.
    const FVector3f N=Normalize(G.ProjectionToeAxes[Leg]);const float Angle=FMath::Clamp(Toe,-1.f,1.f)*PI/2.f;
    FRows H={{{1,0,0},{0,1,0},{0,0,1}}};
    for (auto& Row:H.V) Row=Row*FMath::Cos(Angle)+FVector3f::CrossProduct(N,Row)*FMath::Sin(Angle)+N*FVector3f::DotProduct(N,Row)*(1-FMath::Cos(Angle));
    const auto TR=MultiplyLower(H,R);auto& B=Out.Toe;B.F=TR.V[0];B.U=TR.V[1];B.S=TR.V[2];
    if (FVector3f::DotProduct(B.F,T)<0) B.F=-B.F;if (B.U.Z<0) B.U=-B.U;
    B.C=T+B.F*.024f-B.U*.006f;return Out;
}
FVector3f Contact(const FBox& B,const FVector3f& Half,float Blend,FVector3f& Support)
{
    auto Sign=[](float V) { return V>1.e-5f?-1.f:V< -1.e-5f?1.f:0.f; };
    const float Magnitude=FMath::Clamp(FMath::Abs(B.S.Z),0.f,1.f);
    const float Side= Magnitude>=FMath::Sin(Blend)?1.f:FMath::Asin(Magnitude)/Blend;
    Support={Sign(B.F.Z)*Half.X,Sign(B.S.Z)*Half.Y*Side,-Half.Z};
    return B.C+B.F*Support.X+B.S*Support.Y+B.U*Support.Z;
}
FVector3f FromSupport(const FBox& B,const FVector3f& S) { return B.C+B.F*S.X+B.S*S.Y+B.U*S.Z; }
float Lowest(const FFootBoxes& B,float Blend)
{
    FVector3f S;return FMath::Min(Contact(B.Foot,{.0875f,.060f,.0255f},Blend,S).Z,Contact(B.Toe,{.024f,.060f,.0245f},Blend,S).Z);
}
void Clean(float* Values)
{ for (int32 I:{3,12,18,28,34}) Clean6(Values+I);Values[24]=FMath::Clamp(Values[24],-1.f,1.f);Values[40]=FMath::Clamp(Values[40],-1.f,1.f); }
}

bool FDodgeLowerSettings::Load(const FString& Filename,const FString& Policy,FString& Error)
{
    Error.Reset();FString Text;TSharedPtr<FJsonObject> Document;const TSharedPtr<FJsonObject>* P=nullptr;
    if (!FFileHelper::LoadFileToString(Text,*Filename) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Document)
        || !Document || !Document->TryGetObjectField(Policy,P)) { Error=TEXT("Cannot read saved dodge lower settings.");return false; }
    FDodgeLowerSettings Next;
    auto Number=[&](const TCHAR* Name,float& Out)
    { double V;if (!(*P)->TryGetNumberField(Name,V) || !FMath::IsFinite(V)) return false;Out=float(V);return true; };
    float Steps=0;
    if (!Number(TEXT("pose_delta_scale"),Next.PoseDeltaScale) || !Number(TEXT("speed_scale"),Next.SpeedScale) || !Number(TEXT("turn_scale"),Next.TurnScale)
        || !Number(TEXT("ground"),Next.Ground) || !Number(TEXT("side_blend"),Next.SideBlend) || !Number(TEXT("full_height"),Next.FullHeight)
        || !Number(TEXT("fade_height"),Next.FadeHeight) || !Number(TEXT("minimum_pin"),Next.MinimumPin) || !Number(TEXT("steps"),Steps)
        || !(*P)->TryGetBoolField(TEXT("legacy_pin"),Next.bLegacyPin) || !(*P)->TryGetBoolField(TEXT("height_gate"),Next.bHeightGate)
        || Next.PoseDeltaScale<=0 || Next.SpeedScale<=0 || Next.TurnScale<=0 || Next.SideBlend<=0 || Next.SideBlend>PI/2
        || Steps<1 || Steps>1024 || Next.FadeHeight<Next.FullHeight || Next.MinimumPin<0 || Next.MinimumPin>1)
    { Error=TEXT("Invalid dodge lower normalization/projection settings.");return false; }
    Next.IntegrationSteps=int32(Steps);*this=Next;return true;
}
void DodgeLowerInput(const FDodgeState& S,const FDodgeLowerSettings& C,float* Out)
{
    FMemory::Memcpy(Out,S.CurrentLower,41*sizeof(float));FMemory::Memcpy(Out+41,S.PreviousLower,41*sizeof(float));
    for (int32 I=0;I<3;++I) Out[82+I]=(S.CurrentLower[I]-S.PreviousLower[I])/C.PoseDeltaScale;
    for (int32 I=0;I<32;++I) Out[85+I]=(S.CurrentLower[9+I]-S.PreviousLower[9+I])/C.PoseDeltaScale;
    const float PYaw=FMath::Atan2(-S.PreviousRoot.R.V[1].X,-S.PreviousRoot.R.V[1].Z);
    const float CYaw=FMath::Atan2(-S.CurrentRoot.R.V[1].X,-S.CurrentRoot.R.V[1].Z);
    const auto History=Transform(S.CurrentRoot.P-S.PreviousRoot.P,DodgeYaw(-PYaw));
    Out[117]=History.X/C.SpeedScale;Out[118]=History.Z/C.SpeedScale;
    Out[119]=FMath::Atan2(FMath::Sin(CYaw-PYaw),FMath::Cos(CYaw-PYaw))/C.TurnScale;
    const auto Command=DodgeCommand(S.InitialWorldDelta,S.YawOffset);
    const auto Heading=DodgeYaw(-CYaw);
    for (int32 I=1;I<=8;++I)
    {
        // Preserve reference addition/subtraction order at nonzero world origins.
        const auto Future=S.CurrentRoot.P+float(I)*Command;
        const auto Local=Transform(Future-S.CurrentRoot.P,Heading);const float Scale=float(I)*C.SpeedScale;
        Out[120+(I-1)*4]=FMath::Clamp(Local.X/Scale,-2.f,2.f);Out[121+(I-1)*4]=FMath::Clamp(Local.Z/Scale,-2.f,2.f);
        Out[122+(I-1)*4]=FMath::Cos(float(I)*S.InitialYawDelta);Out[123+(I-1)*4]=FMath::Sin(float(I)*S.InitialYawDelta);
    }
}
void CleanDodgeLower(const float* Raw,const float* Current,const FGeometry& G,const FDodgeLowerSettings& C,float* Out,float* Pins)
{
    for (int32 I=0;I<41;++I) Out[I]=Current[I]+Raw[I];Clean(Out);
    FRows Rotations[2];FFootBoxes EndBoxes[2];float Heights[2],LowestPoints[2];
    for (int32 Leg=0;Leg<2;++Leg)
    {
        const int32 O=9+16*Leg;Rotations[Leg]=Rot6(Out+O+3);EndBoxes[Leg]=Boxes(Leg,Rotations[Leg],Out[O+15],G);
        LowestPoints[Leg]=Lowest(EndBoxes[Leg],C.SideBlend)+Out[O+2];Heights[Leg]=FMath::Max(0.f,LowestPoints[Leg]-C.Ground);
        Pins[Leg]=1.f/(1.f+FMath::Exp(Raw[41+Leg]*8.f));
    }
    if (C.bLegacyPin)
    {
        const bool Both=Raw[41]<0 && Raw[42]<0;
        Pins[0]=Both || Raw[41]<=Raw[42]?1.f:0.f;Pins[1]=Both || Raw[42]<Raw[41]?1.f:0.f;
    }
    else
    {
        const bool Both=Heights[0]<C.FadeHeight && Heights[1]<C.FadeHeight;
        const int32 Selected=Both?(Raw[41]<=Raw[42]?0:1):(Heights[0]<=Heights[1]?0:1);
        const float Alpha=FMath::Clamp((C.FadeHeight-Heights[Selected])/FMath::Max(1.e-6f,C.FadeHeight-C.FullHeight),0.f,1.f);
        Pins[Selected]=FMath::Max(Pins[Selected],C.MinimumPin*Alpha);
    }
    float Cur[41];FMemory::Memcpy(Cur,Current,sizeof(Cur));Clean(Cur);
    for (int32 Leg=0;Leg<2;++Leg)
    {
        const int32 O=9+16*Leg;float Weight=Pins[Leg];
        if (C.bHeightGate) Weight*=FMath::Clamp((.01f-Heights[Leg])/.005f,0.f,1.f);
        if (Weight>0)
        {
            const auto CR=Rot6(Cur+O+3),Relative=MultiplyLower(Rotations[Leg],TransposeLower(CR));
            const FVector3f Vee(Relative.V[1].Z-Relative.V[2].Y,Relative.V[2].X-Relative.V[0].Z,Relative.V[0].Y-Relative.V[1].X);
            const float Norm=Vee.Size(),Cosine=FMath::Clamp((Relative.V[0].X+Relative.V[1].Y+Relative.V[2].Z-1)*.5f,-1.f,1.f);
            const auto RV=Vee*(Norm>1.e-7f?FMath::Atan2(Norm*.5f,Cosine)/FMath::Max(Norm,1.e-7f):.5f);
            auto Previous=Boxes(Leg,CR,Cur[O+15],G);FVector3f Delta=FVector3f::ZeroVector;
            for (int32 Step=1;Step<=C.IntegrationSteps;++Step)
            {
                const float T=float(Step)/float(C.IntegrationSteps);
                const auto SR=MultiplyLower(RotationVector(RV*T),CR);
                const auto Next=Boxes(Leg,SR,Cur[O+15]+(Out[O+15]-Cur[O+15])*T,G);
                FVector3f FS,TS;const auto FP=Contact(Next.Foot,{.0875f,.060f,.0255f},C.SideBlend,FS),TP=Contact(Next.Toe,{.024f,.060f,.0245f},C.SideBlend,TS);
                Delta+=TP.Z<FP.Z?FromSupport(Previous.Toe,TS)-TP:FromSupport(Previous.Foot,FS)-FP;Previous=Next;
            }
            Out[O]+=Weight*(Cur[O]+Delta.X-Out[O]);Out[O+1]+=Weight*(Cur[O+1]+Delta.Y-Out[O+1]);
        }
        // Horizontal projection cannot change the vertical support height.
        Out[O+2]+=FMath::Max(0.f,C.Ground-LowestPoints[Leg]);
    }
}
}
