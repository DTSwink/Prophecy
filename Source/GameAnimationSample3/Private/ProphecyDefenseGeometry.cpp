#include "ProphecyDefenseGeometry.h"
#include "ProphecyDodgeBanks.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"

namespace ProphecyDefense
{
namespace
{
constexpr int32 Parents[]={-1,0,1,2,3,4,5,6,7,8,5,10,11,12,5,14,15,0,17,18,19,0,21,22,23};
constexpr int32 Core[]={1,2,3,4,5,14,15,16,6,10};
FRows Transpose(const FRows& A)
{ return {{{A.V[0].X,A.V[1].X,A.V[2].X},{A.V[0].Y,A.V[1].Y,A.V[2].Y},{A.V[0].Z,A.V[1].Z,A.V[2].Z}}}; }
FRows Multiply(const FRows& A,const FRows& B)
{ return {{Transform(A.V[0],B),Transform(A.V[1],B),Transform(A.V[2],B)}}; }
void Write6(float* Out,const FRows& R) { Write(Out,R.V[0]);Write(Out+3,R.V[1]); }
FVector3f Plane(const FVector3f& V,const FVector3f& Axis)
{ const auto N=Normalize(Axis);return Normalize(V-N*FVector3f::DotProduct(V,N)); }
FVector3f Rotate(const FVector3f& V,const FVector3f& Axis,float Angle)
{
    const auto N=Normalize(Axis);const float C=FMath::Cos(Angle),S=FMath::Sin(Angle);
    return V*C+FVector3f::CrossProduct(N,V)*S+N*FVector3f::DotProduct(N,V)*(1-C);
}
FRows AxisAngle(const FVector3f& Axis,float Angle)
{ return {{Rotate({1,0,0},Axis,Angle),Rotate({0,1,0},Axis,Angle),Rotate({0,0,1},Axis,Angle)}}; }
FRows AxisPole(const FVector3f& Axis,const FVector3f& Pole)
{
    const auto Main=Normalize(Axis);auto Up=FVector3f::CrossProduct(Main,Plane(Pole,Main));
    if (Up.SizeSquared()<=1.e-16f)
    {
        const auto Perp=Normalize(FVector3f::CrossProduct(Main,FMath::Abs(Main.Z)<.8f?FVector3f(0,0,1):FVector3f(1,0,0)));
        Up=FVector3f::CrossProduct(Main,Perp);
    }
    Up=Normalize(Up);return {{Main,Normalize(FVector3f::CrossProduct(Up,Main)),Up}};
}
void CleanLower(float* Lower)
{
    for (int32 I:{3,12,18,28,34}) Clean6(Lower+I);
    Lower[24]=FMath::Clamp(Lower[24],-1.f,1.f);Lower[40]=FMath::Clamp(Lower[40],-1.f,1.f);
}
void Limb(FPose& Pose,int32 Start,int32 Mid,int32 End,int32 Toe,const float* State,
    const FGeometry::FLimb& G,const FVector3f* Offsets,const FVector3f& RootP,const FRows& RootR,bool Signed,bool Hemisphere)
{
    const FRows SR=Multiply(Rot6(State+9),RootR),ER=Rot6(State+3);
    const FVector3f EndRoot=Read(State);
    Pose.R[Start]=SR;Pose.P[Mid]=Transform(Offsets[Mid],SR)+Pose.P[Start];
    Pose.P[End]=Transform(EndRoot,RootR)+RootP;
    FVector3f Axis=Pose.P[End]-Pose.P[Mid];
    if (Axis.SizeSquared()<=1.e-16f) Axis=Transform(Offsets[End],SR);
    FVector3f WorldPole=Transform(G.Pole[0],SR),LocalPole=G.Pole[1];
    if (Signed && Toe!=INDEX_NONE)
    {
        WorldPole=Normalize(FVector3f::CrossProduct(Pose.P[Mid]-Pose.P[Start],WorldPole));
        LocalPole=Normalize(FVector3f::CrossProduct(Offsets[End],LocalPole));
    }
    Pose.R[Mid]=Multiply(Transpose(AxisPole(Offsets[End],LocalPole)),AxisPole(Axis,WorldPole));
    if (Hemisphere && !Signed && Toe!=INDEX_NONE && FVector3f::DotProduct(Pose.R[Mid].V[2],SR.V[2])<0)
    {
        const auto N=Normalize(Axis),A=Plane(Pose.R[Mid].V[2],N),B=Plane(SR.V[2],N);
        const float Angle=FMath::Atan2(FVector3f::DotProduct(FVector3f::CrossProduct(A,B),N),FVector3f::DotProduct(A,B));
        for (auto& Row:Pose.R[Mid].V) Row=Rotate(Row,N,Angle);
    }
    Pose.R[End]=Multiply(ER,RootR);
    if (Toe!=INDEX_NONE)
    {
        Pose.P[Toe]=Transform(EndRoot+Transform(G.ToeOffset,ER),RootR)+RootP;
        Pose.R[Toe]=Multiply(Multiply(AxisAngle(G.ToeAxis,FMath::Clamp(State[15],-1.f,1.f)*(PI/2.f)),ER),RootR);
    }
}
bool Flatten(const TSharedPtr<FJsonValue>& V,TArray<float>& Out)
{
    if (!V) return false;
    if (V->Type==EJson::Number)
    { const float F=float(V->AsNumber());if (!FMath::IsFinite(F)) return false;Out.Add(F);return true; }
    if (V->Type!=EJson::Array) return false;
    for (const auto& A:V->AsArray()) if (!Flatten(A,Out)) return false;
    return true;
}
}

bool FGeometry::Load(const FString& Filename,bool bDodge,FString& Error)
{
    Error.Reset();FString Text;TSharedPtr<FJsonObject> Document;
    if (!FFileHelper::LoadFileToString(Text,*Filename) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Document) || !Document)
    { Error=TEXT("Cannot read saved defense skeleton: ")+Filename;return false; }
    const TArray<TSharedPtr<FJsonValue>>* ParentValues=nullptr;
    const TSharedPtr<FJsonObject>* Geometry=nullptr;
    if (!Document->TryGetArrayField(TEXT("parents"),ParentValues) || ParentValues->Num()!=25 || !Document->TryGetObjectField(TEXT("geometry"),Geometry))
    { Error=TEXT("Defense skeleton does not have the expected hierarchy and geometry.");return false; }
    for (int32 I=0;I<25;++I) if (int32((*ParentValues)[I]->AsNumber())!=Parents[I])
    { Error=TEXT("Defense skeleton hierarchy mismatch.");return false; }
    FGeometry Next;Next.bSignedLegHinge=bDodge;
    auto ReadField=[&](const FString& Name,TArray<float>& Out,int32 Count)
    {
        Out.Reset();
        if (!Flatten((*Geometry)->TryGetField(Name),Out) || Out.Num()!=Count)
        { Error=TEXT("Invalid defense geometry field: ")+Name;return false; }
        return true;
    };
    for (int32 Pass=0;Pass<2;++Pass)
    {
        const FString Prefix=Pass==0?TEXT("lower/"):TEXT("full/");
        const int32 Count=Pass==0?2:4;
        FLimb* Limbs=Pass==0?Next.LowerLegs:Next.FullLimbs;
        FVector3f* Offsets=Pass==0?Next.LowerOffsets:Next.FullOffsets;
        TArray<float> Values;
        if (!ReadField(Prefix+TEXT("local_offsets"),Values,75)) return false;
        for (int32 I=0;I<25;++I) Offsets[I]=Read(Values.GetData()+3*I);
        if (!ReadField(Prefix+TEXT("ik_limb_lengths"),Values,Count*2)) return false;
        for (int32 I=0;I<Count;++I) for (int32 J=0;J<2;++J)
        { Limbs[I].Length[J]=Values[I*2+J];if (Limbs[I].Length[J]<=1.e-5f) { Error=TEXT("Invalid limb length.");return false; } }
        if (!ReadField(Prefix+TEXT("ik_local_pole_axis"),Values,Count*6)) return false;
        for (int32 I=0;I<Count;++I) for (int32 J=0;J<2;++J) Limbs[I].Pole[J]=Read(Values.GetData()+I*6+J*3);
        if (!ReadField(Prefix+TEXT("ik_toe_offsets"),Values,Count*3)) return false;
        for (int32 I=0;I<Count;++I) Limbs[I].ToeOffset=Read(Values.GetData()+I*3);
        if (!ReadField(Prefix+TEXT("ik_toe_axis"),Values,Count*3)) return false;
        for (int32 I=0;I<Count;++I) Limbs[I].ToeAxis=Read(Values.GetData()+I*3);
    }
    TArray<float> Projection;
    if (!ReadField(TEXT("projection/ik_toe_offsets"),Projection,6)) return false;
    for (int32 I=0;I<2;++I) Next.ProjectionToeOffsets[I]=Read(Projection.GetData()+3*I);
    if (!ReadField(TEXT("projection/ik_toe_axis"),Projection,6)) return false;
    for (int32 I=0;I<2;++I) Next.ProjectionToeAxes[I]=Read(Projection.GetData()+3*I);
    *this=Next;return true;
}
void FGeometry::LowerPose(const float* Input,const FVector3f& RootP,const FRows& RootR,FPose& Out,bool bIncludeLegs) const
{
    float Lower[41];FMemory::Memcpy(Lower,Input,sizeof(Lower));if (bIncludeLegs) CleanLower(Lower);else Clean6(Lower+3);
    Out.P[0]=Transform(Read(Lower),RootR)+RootP;Out.R[0]=Multiply(Rot6(Lower+3),RootR);
    // The lower clip takes ik_core's fallback FK path: accumulate each local
    // offset in hierarchy order, rather than replacing it with a rest sum.
    for (int32 I=1;I<(bIncludeLegs?25:17);++I)
    { Out.R[I]=Out.R[Parents[I]];Out.P[I]=Transform(LowerOffsets[I],Out.R[Parents[I]])+Out.P[Parents[I]]; }
    for (int32 Leg=0;Leg<(bIncludeLegs?2:0);++Leg)
    { const int32 Start=17+4*Leg;Limb(Out,Start,Start+1,Start+2,Start+3,Lower+9+16*Leg,LowerLegs[Leg],LowerOffsets,RootP,RootR,bSignedLegHinge,true); }
}
void FGeometry::EncodeUpper(const FPose& Pose,const FVector3f& RootP,const FRows& RootR,float* Upper)
{
    for (int32 I=0;I<10;++I) Write6(Upper+6*I,Multiply(Pose.R[Core[I]],Transpose(Pose.R[Parents[Core[I]]])));
    for (int32 Arm=0;Arm<2;++Arm)
    {
        const int32 Start=7+Arm*4,End=Start+2,O=60+Arm*15;
        Write(Upper+O,InTransposedBasis(Pose.P[End]-RootP,RootR));
        Write6(Upper+O+3,Multiply(Pose.R[End],Transpose(RootR)));
        Write6(Upper+O+9,Multiply(Pose.R[Start],Transpose(RootR)));
    }
    CleanUpper(Upper);
}
void FGeometry::RawPose(const float* InputLower,const float* InputUpper,const FVector3f& RootP,const FRows& RootR,FPose& Out,bool bIncludeLegs) const
{
    float Lower[41],Upper[90];FMemory::Memcpy(Lower,InputLower,sizeof(Lower));FMemory::Memcpy(Upper,InputUpper,sizeof(Upper));
    // compose_full_vector cleans once; output_to_pose cleans a second time.
    for (int32 Pass=0;Pass<2;++Pass) { if (bIncludeLegs) CleanLower(Lower);else Clean6(Lower+3);CleanUpper(Upper); }
    Out.P[0]=Transform(Read(Lower),RootR)+RootP;Out.R[0]=Multiply(Rot6(Lower+3),RootR);
    for (int32 Slot=0;Slot<10;++Slot)
    {
        const int32 I=Core[Slot],Parent=Parents[I];
        Out.P[I]=Transform(FullOffsets[I],Out.R[Parent])+Out.P[Parent];
        Out.R[I]=Multiply(Rot6(Upper+6*Slot),Out.R[Parent]);
    }
    for (int32 L=0;L<(bIncludeLegs?4:2);++L)
    {
        const bool Leg=L>=2;const int32 Start=Leg?17+4*(L-2):7+4*L;
        Out.P[Start]=Transform(FullOffsets[Start],Out.R[Parents[Start]])+Out.P[Parents[Start]];
        Limb(Out,Start,Start+1,Start+2,Leg?Start+3:INDEX_NONE,Leg?Lower+9+16*(L-2):Upper+60+15*L,
            FullLimbs[L],FullOffsets,RootP,RootR,bSignedLegHinge,false);
    }
}
void FGeometry::Finish(const float* Lower,const float* Upper,const FVector3f& RootP,const FRows& RootR,
    const FPose& Frozen,const float* BaselineUpper,FPose& Out) const
{
    // Both decoder passes have identical legs. Keep the supplied lower pose
    // directly, without solving those four unnecessary leg chains per agent.
    FPose Base,Candidate;RawPose(Lower,BaselineUpper,RootP,RootR,Base,false);RawPose(Lower,Upper,RootP,RootR,Candidate,false);
    for (int32 I=0;I<25;++I)
    {
        if (I==0 || I>=17) { Out.P[I]=Frozen.P[I];Out.R[I]=Frozen.R[I];continue; }
        Out.P[I]=Frozen.P[I]+(Candidate.P[I]-Base.P[I]);
        Out.R[I]=Multiply(Multiply(Candidate.R[I],Transpose(Base.R[I])),Frozen.R[I]);
    }
}

bool FGeometry::SolveDodgeLower(const float* Baseline,const FDodgeControls& C,const FVector3f& RootP,
    const FRows& RootR,float* Out,bool bFootFloor,bool bReconstructLegs) const
{
    check(bSignedLegHinge);
    if (!C.bEnabled && !bFootFloor) { FMemory::Memcpy(Out,Baseline,41*sizeof(float));return false; }
    FPose Pose;LowerPose(Baseline,RootP,RootR,Pose);
    const FVector3f Pelvis=Pose.P[0]+DodgeHorizontal(C.PelvisHorizontal,RootR)-FVector3f(0,C.Drop,0);
    // Match the reference rotation-vector polynomial, including the identity.
    const float Angle=C.PelvisRotation.Size();
    const float A=Angle>1.e-8f?FMath::Sin(Angle)/Angle:1.f;
    const float HalfSinc=Angle>1.e-8f?FMath::Sin(Angle*.5f)/(Angle*.5f):1.f;
    const float B=.5f*HalfSinc*HalfSinc;
    const auto V=C.PelvisRotation;
    const FRows K={{{0,V.Z,-V.Y},{-V.Z,0,V.X},{V.Y,-V.X,0}}},K2=Multiply(K,K);
    FRows Rotation={{{1,0,0},{0,1,0},{0,0,1}}};
    for (int32 I=0;I<3;++I) Rotation.V[I]+=A*K.V[I]+B*K2.V[I];
    const FRows PelvisR=Multiply(Multiply(Rot6(Baseline+3),Rotation),RootR),Inverse=Transpose(RootR);
    float Result[41];FMemory::Memcpy(Result,Baseline,sizeof(Result));
    Write(Result,Transform(Pelvis-RootP,Inverse));Write6(Result+3,Multiply(PelvisR,Inverse));
    if (!bReconstructLegs)
    {
        // Diagnostic: retain learned endpoint/pelvis changes, but keep baseline
        // thigh frames and skip all corrective reach/floor/hinge reconstruction.
        for (int32 Leg=0;Leg<2;++Leg)
            Write(Result+9+16*Leg,Read(Baseline+9+16*Leg)+C.Foot[Leg]);
        FMemory::Memcpy(Out,C.bEnabled?Result:Baseline,41*sizeof(float));
        return C.bEnabled;
    }
    bool FloorApplied=false;
    for (int32 Leg=0;Leg<2;++Leg)
    {
        const int32 Hip=17+Leg*4,Knee=Hip+1,Foot=Hip+2,O=9+16*Leg;
        const FVector3f NewHip=Pelvis+Transform(LowerOffsets[Hip],PelvisR);
        const FVector3f OldAxis=Normalize(Pose.P[Foot]-Pose.P[Hip]);
        FVector3f OldBend=Pose.P[Knee]-Pose.P[Hip];OldBend-=OldAxis*FVector3f::DotProduct(OldBend,OldAxis);
        const FVector3f OldPole=OldBend.SizeSquared()>1.e-10f?Normalize(OldBend):Plane(Transform(LowerLegs[Leg].Pole[0],Pose.R[Hip]),OldAxis);
        const float L1=LowerOffsets[Knee].Size(),L2=LowerLegs[Leg].Length[1];
        FVector3f Ankle=Pose.P[Foot]+Transform(C.Foot[Leg],RootR),Delta=Ankle-NewHip;
        float Radius=Delta.Size();
        Ankle=NewHip+(Radius>1.e-8f?Delta/FMath::Max(Radius,1.e-8f):OldAxis)*FMath::Clamp(Radius,FMath::Abs(L1-L2)+2.e-5f,L1+L2-2.e-5f);
        if (bFootFloor)
        {
            const auto& FootR=Pose.R[Foot];const FVector3f ToeDelta=Transform(ProjectionToeOffsets[Leg],FootR);
            const FVector3f ToePosition=Pose.P[Foot]+ToeDelta;
            FVector3f FUp=FootR.V[0],FForward=FootR.V[1],FSide=FootR.V[2];
            if (FVector3f::DotProduct(FForward,ToeDelta)<0) FForward=-FForward;
            if (FUp.Y<0) FUp=-FUp;
            const FVector3f FC=ToePosition-FForward*.0875f-FUp*.006f;
            const FRows TR=Multiply(AxisAngle(ProjectionToeAxes[Leg],FMath::Clamp(Baseline[O+15],-1.f,1.f)*(PI/2.f)),FootR);
            FVector3f TForward=TR.V[0],TUp=TR.V[1],TSide=TR.V[2];
            if (FVector3f::DotProduct(TForward,ToeDelta)<0) TForward=-TForward;
            if (TUp.Y<0) TUp=-TUp;
            const FVector3f TC=ToePosition+TForward*.024f-TUp*.006f;
            const float Lowest=FMath::Min(FC.Y-(FMath::Abs(FForward.Y)*.0875f+FMath::Abs(FSide.Y)*.060f+FMath::Abs(FUp.Y)*.0255f),
                TC.Y-(FMath::Abs(TForward.Y)*.024f+FMath::Abs(TSide.Y)*.060f+FMath::Abs(TUp.Y)*.0245f));
            const float Minimum=Pose.P[Foot].Y-Lowest+1.e-5f;
            if (Ankle.Y<Minimum)
            {
                const float DY=Minimum-NewHip.Y;
                FVector2f Horizontal(Ankle.X-NewHip.X,Ankle.Z-NewHip.Z),Backup(OldAxis.X,OldAxis.Z);
                const float HRadius=Horizontal.Size(),BackupLength=Backup.Size();
                Backup=BackupLength>1.e-8f?Backup/FMath::Max(BackupLength,1.e-8f):FVector2f(1,0);
                const auto Direction=HRadius>1.e-8f?Horizontal/FMath::Max(HRadius,1.e-8f):Backup;
                const float Low2=FMath::Square(FMath::Abs(L1-L2)+2.e-5f)-DY*DY,High2=FMath::Square(L1+L2-2.e-5f)-DY*DY;
                const float Low=Low2>0?FMath::Sqrt(FMath::Max(Low2,1.e-12f)):0.f,High=FMath::Sqrt(FMath::Max(High2,1.e-12f));
                Horizontal=FVector2f(NewHip.X,NewHip.Z)+Direction*FMath::Max(FMath::Min(HRadius,High),Low);
                Ankle={Horizontal.X,Minimum,Horizontal.Y};FloorApplied=true;
            }
        }
        // Carry the foot-local pole even when the foot itself did not rotate:
        // the oracle uses R^T*R, which is not exactly identity in float32.
        const FRows Change=Multiply(Transpose(Pose.R[Foot]),Pose.R[Foot]);
        const auto Source=Normalize(Transform(OldAxis,Change)),Target=Normalize(Ankle-NewHip);
        const auto P=Plane(Transform(OldPole,Change),Source);
        const float Cosine=FMath::Clamp(FVector3f::DotProduct(Source,Target),-1.f,1.f);
        const auto Transported=Cosine<(-1.f+1.e-6f)?-P:P-FVector3f::DotProduct(P,Target)*(Source+Target)/FMath::Max(1.f+Cosine,1.e-6f);
        const auto Pole=Plane(Transported,Target);
        const float Distance=FMath::Clamp(FMath::Max((Ankle-NewHip).Size(),1.e-8f),FMath::Abs(L1-L2)+1.e-5f,L1+L2-1.e-5f);
        const float Along=(L1*L1-L2*L2+Distance*Distance)/(2*Distance),Height=FMath::Sqrt(FMath::Max(0.f,L1*L1-Along*Along));
        const auto Solved=NewHip+Target*Along+Plane(Pole,Target)*Height;
        const auto OldUpper=Normalize(Pose.P[Knee]-Pose.P[Hip]),NewUpper=Normalize(Solved-NewHip);
        const auto OldNormal=Normalize(FVector3f::CrossProduct(OldAxis,OldPole)),NewNormal=Normalize(FVector3f::CrossProduct(Target,Pole));
        const FRows OldBasis={{OldUpper,Normalize(FVector3f::CrossProduct(OldNormal,OldUpper)),OldNormal}};
        const FRows NewBasis={{NewUpper,Normalize(FVector3f::CrossProduct(NewNormal,NewUpper)),NewNormal}};
        const auto Thigh=Multiply(Multiply(Pose.R[Hip],Transpose(OldBasis)),NewBasis);
        Write(Result+O,Transform(Ankle-RootP,Inverse));Write6(Result+O+9,Multiply(Thigh,Inverse));
    }
    const bool Applied=C.bEnabled || FloorApplied;
    FMemory::Memcpy(Out,Applied?Result:Baseline,41*sizeof(float));return Applied;
}
}
