// Checkpoint programs 659cd1c8 (pelvis/feet) and f58ff405 (hands), evaluated
// directly instead of thousands of small ONNX tensor operators. No new state.
namespace SlashFastGeometry
{
#if WITH_EDITOR
static TAutoConsoleVariable<int32> Enabled(TEXT("Prophecy.Attack.NativeGeometry"),1,
    TEXT("Native checkpoint constraints. Latched on model load; 0 selects original ONNX for parity captures."));
#endif
static bool Use(const FString& Directory,const TSharedPtr<FJsonObject>& Contract,FString& UpperFile)
{
#if WITH_EDITOR
    if(!Enabled.GetValueOnGameThread())return false;
#endif
    FString Text;TSharedPtr<FJsonObject> M;
    if(!FFileHelper::LoadFileToString(Text,*(Directory/TEXT("prophecy_slash_fast.json"))) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),M) || !M.IsValid())return false;
    if(M->GetStringField(TEXT("schema"))!=TEXT("native_attack_geometry_v1") ||
        M->GetStringField(TEXT("checkpoint_sha256"))!=Contract->GetStringField(TEXT("checkpoint_sha256")) ||
        M->GetStringField(TEXT("source_upper_sha256"))!=Contract->GetObjectField(TEXT("networks"))->GetObjectField(TEXT("upper"))->GetStringField(TEXT("sha256")) ||
        M->GetStringField(TEXT("cone_program_sha256"))!=TEXT("659cd1c8d2a5e27628fbbb04024a71b599ad183ec684281d9f903f6ce866a772") ||
        M->GetStringField(TEXT("hand_program_sha256"))!=TEXT("f58ff4058f9cfe78cdebcc393d106e9251f71eb82a19dd98aeba35a98cb13e4d"))return false;
    UpperFile=M->GetStringField(TEXT("upper_file"));return FPaths::FileExists(Directory/UpperFile);
}
static float Wrap(float A){A+=PI;return A-FMath::FloorToFloat(A/(2.f*PI))*(2.f*PI)-PI;}
static float Heading(float X,float Z){return X*X+Z*Z>1.e-16f?FMath::Atan2(X,Z):0.f;}
static FVector3f Unit(const FVector3f& V){return V/FMath::Max(V.Size(),1.e-12f);}
static bool Cone(const float* Old,const float* Candidate,const FVector3f* ToeOffsets,float* Out)
{
    for(int32 I=0;I<41;++I)if(!FMath::IsFinite(Old[I]) || !FMath::IsFinite(Candidate[I]))return false;
    const FMat3f OldPelvis=MatrixFromRot6(Old+3),NewPelvis=MatrixFromRot6(Candidate+3);
    const auto OP=OldPelvis.Rows[1],NP=NewPelvis.Rows[1];
    const float OldYaw=Heading(-OP.X,-OP.Z),NewYaw=Heading(-NP.X,-NP.Z);
    constexpr float Bound=134.98f*PI/180.f,SeedBound=135.0001f*PI/180.f;
    float Lo=-3.141591f,Hi=3.141591f,HoldLo=-3.141591f,HoldHi=3.141591f;
    bool SeedValid=OP.X*OP.X+OP.Z*OP.Z>1.e-16f;
    bool Valid=NP.X*NP.X+NP.Z*NP.Z>1.e-16f;
    for(int32 Side=0;Side<2;++Side)
    {
        if(ToeOffsets[Side].ContainsNaN())return false;
        const int32 O=12+16*Side;
        const auto A=MatrixFromRot6(Old+O),B=MatrixFromRot6(Candidate+O);
        const auto T0=TransformRow(ToeOffsets[Side],A),DT=TransformRow(ToeOffsets[Side],B)-T0;
        const auto DX=B.Rows[0]-A.Rows[0],DY=B.Rows[1]-A.Rows[1];
        float LastHeading=0,Change=0,Initial=0;
        for(int32 Sample=0;Sample<257;++Sample)
        {
            const float T=float(Sample)*(1.f/256.f);
            const auto YRaw=A.Rows[1]+T*DY,Y=Unit(YRaw);
            const auto X=A.Rows[0]+T*DX,XRaw=X-FVector3f::DotProduct(X,Y)*Y;
            const auto Up=Unit(XRaw)*(Side==0?1.f:-1.f),Toe=T0+T*DT;
            const FVector3f K(-Up.Z,0,Up.X);
            const float Den=1.f+Up.Y;
            const auto Cross=FVector3f::CrossProduct(K,Toe);
            const auto Level=Toe+Cross+FVector3f::CrossProduct(K,Cross)/FMath::Max(Den,1.e-8f);
            const bool Geometry=Den>1.e-8f && YRaw.SizeSquared()>1.e-16f && XRaw.SizeSquared()>1.e-16f && Level.X*Level.X+Level.Z*Level.Z>1.e-16f;
            const float H=Heading(Level.X,Level.Z);
            if(Sample==0)
            {
                Initial=Wrap(OldYaw-H);SeedValid&=Geometry && FMath::Abs(Initial)<=SeedBound;
                HoldLo=FMath::Max(HoldLo,-Bound-Initial);HoldHi=FMath::Min(HoldHi,Bound-Initial);
            }
            else
            {
                Change+=Wrap(H-LastHeading);
                const float Offset=Initial-Change;
                Lo=FMath::Max(Lo,(-Bound-Offset)/T);Hi=FMath::Min(Hi,(Bound-Offset)/T);
            }
            Valid&=Geometry;LastHeading=H;
        }
    }
    if(!SeedValid)return false;
    const float Requested=Wrap(NewYaw-OldYaw);
    const bool Accept=Valid && Lo<=Hi;
    const float Chosen=Accept?FMath::Min(FMath::Max(Requested,Lo),Hi):
        HoldLo<=HoldHi?FMath::Min(FMath::Max(Requested,HoldLo),HoldHi):0.f;
    const float* Source=Accept?Candidate:Old;
    FMemory::Memcpy(Out,Source,41*sizeof(float));
    if(Accept?Requested==Chosen:Chosen==0.f)return true;
    const float Turn=Accept?Wrap(OldYaw+Chosen-NewYaw):Chosen;
    WriteRot6(Multiply(Accept?NewPelvis:OldPelvis,YawMatrix(-Turn)),Out+3);
    return true;
}
}
