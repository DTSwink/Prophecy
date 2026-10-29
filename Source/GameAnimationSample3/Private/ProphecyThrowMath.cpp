#include "ProphecyThrowMath.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace ProphecyThrow
{
static double Clamp(double V){return FMath::Clamp(V,0.,1.);}
static double Smooth(double V){V=Clamp(V);return V*V*V*(10+V*(-15+6*V));}
static FVector Log(FQuat Q){if(Q.W<0)Q=Q*-1.;const FVector V(Q.X,Q.Y,Q.Z);const double N=V.Size();return V*(N<1.e-10?2.:2*FMath::Atan2(N,Q.W)/N);}
static FQuat Exp(FVector V){const double N=V.Size();if(N<1.e-10)return FQuat(V.X*.5,V.Y*.5,V.Z*.5,1).GetNormalized();return FQuat(V/N,N);}
static FQuat Slerp(FQuat A,FQuat B,double T)
{
    double C=A|B;if(C<0){B=B*-1.;C=-C;}
    if(C>.9995)return (A*(1-T)+B*T).GetNormalized();
    const double Theta=FMath::Acos(FMath::Clamp(C,-1.,1.)),S=FMath::Sin(Theta);
    return A*(FMath::Sin((1-T)*Theta)/S)+B*(FMath::Sin(T*Theta)/S);
}
static FQuat FromTo(FVector A,FVector B)
{
    A=A.GetSafeNormal(1.e-24);B=B.GetSafeNormal(1.e-24);const double D=A|B;
    if(D<-.999999){FVector Axis=A^FVector(1,0,0);if(Axis.Size()<1.e-5)Axis=A^FVector(0,1,0);Axis.Normalize();return FQuat(Axis.X,Axis.Y,Axis.Z,0);}
    const FVector Axis=A^B;return FQuat(Axis.X,Axis.Y,Axis.Z,1+D).GetNormalized();
}
static FVector Offset(FVector A,FVector B,double T)
{
    const double LA=A.Size(),LB=B.Size();if(LA<1.e-9||LB<1.e-9)return FMath::Lerp(A,B,T);
    return Slerp(FQuat::Identity,FromTo(A,B),T).RotateVector(A/LA)*FMath::Lerp(LA,LB,T);
}
FQuat Euler(const FVector& D){return Exp(FVector(D.X,0,0)*UE_DOUBLE_PI/180)*Exp(FVector(0,D.Y,0)*UE_DOUBLE_PI/180)*Exp(FVector(0,0,D.Z)*UE_DOUBLE_PI/180);}
static FPose Local(const FPose& P,const FProfile& C)
{
    FPose L;L.SetNum(P.Num());for(int J=0;J<P.Num();++J)L[J]=C.Parents[J]<0?P[J]:P[J].GetRelativeTransform(P[C.Parents[J]]);return L;
}
static FPose FK(FPose P,const FProfile& C)
{
    for(int J=0;J<P.Num();++J)if(C.Parents[J]>=0){P[J]=P[J]*P[C.Parents[J]];P[J].NormalizeRotation();}return P;
}
static FPose Half(const FPose& Source,const FPose& Initial,const FProfile& C)
{
    FPose L=Local(Source,C),I=Local(Initial,C);
    for(int J=0;J<L.Num();++J)if(J<2||J>=18)L[J]=I[J];
    L[2].SetRotation((Initial[1].GetRotation().Inverse()*Source[2].GetRotation()).GetNormalized());
    return FK(MoveTemp(L),C);
}
static FQuat Correction(double Yaw,double Pitch,double Heading)
{return Exp(FVector(FMath::Cos(Heading+Yaw),0,-FMath::Sin(Heading+Yaw))*Pitch)*Exp(FVector(0,Yaw,0));}
static FPose Turn(const FPose& Source,const FProfile& C,const FPlan& Plan,double Weight=1)
{
    if(Weight==0||(Plan.Yaw==0&&Plan.Pitch==0))return Source;
    const auto L=Local(Source,C);FPose Out;Out.SetNum(L.Num());
    const double Y=Plan.Yaw*Weight,P=Plan.Pitch*Weight;const FQuat Yaw=Exp(FVector(0,Y,0));
    const FVector Right(FMath::Cos(Plan.Heading+Y),0,-FMath::Sin(Plan.Heading+Y));
    for(int J=0;J<L.Num();++J){const int Parent=C.Parents[J];
        if(Parent<0)Out[J]=Plan.Half?L[J]:FTransform(Yaw*L[J].GetRotation(),Plan.Initial[J].GetLocation()+Yaw.RotateVector(L[J].GetLocation()-Plan.Initial[J].GetLocation()));
        else Out[J]=L[J]*Out[Parent];
        if(J>=2&&J<=6){const double A=double(J-1)/5.;Out[J].SetRotation((Exp(Right*(P*A))*(Plan.Half?Exp(FVector(0,Y*A,0)):Yaw)*Source[J].GetRotation()).GetNormalized());}
    }return Out;
}
static FPlan MakePlan(const FProfile& C,const FPose& Initial,const FPose& Release,const FVector& Velocity,const FVector& Target,double Armed,const FTransform* Weapon,const FPose* ArmedPose)
{
    FPlan P;P.Initial=Initial;P.Half=C.Half;P.Armed=Armed;
    const FPose Base=C.Half?Half(Release,Initial,C):Release;
    const FVector Reference=Weapon?Weapon->GetRotation().RotateVector(C.Axis):Velocity,Direction=Reference.GetSafeNormal(1.e-24);
    P.Heading=FMath::Atan2(Direction.X,Direction.Z);
    const FVector LocalPoint=Weapon?Release[10].InverseTransformPosition(Weapon->GetLocation()):FVector::ZeroVector;
    auto Origin=[&](const FPose& Pose){return Weapon?Pose[10].TransformPosition(LocalPoint):Pose[6].GetLocation();};
    P.Valid=C.Aim&&Reference.Size()>1.e-8&&(Target-Origin(Base)).Size()>1.e-8;
    if(P.Valid){const FVector Toward=(Target-Origin(Base)).GetSafeNormal(1.e-24);
        const double Heading=FVector2D(Toward.X,Toward.Z).Size()>1.e-8?FMath::Atan2(Toward.X,Toward.Z):P.Heading;
        P.Yaw=FMath::Atan2(FMath::Sin(Heading-P.Heading),FMath::Cos(Heading-P.Heading));P.Pitch=FMath::Asin(FMath::Clamp(Direction.Y,-1.,1.))-FMath::Asin(FMath::Clamp(Toward.Y,-1.,1.));
        auto Residual=[&](double Y,double Pitch){FPlan Test=P;Test.Yaw=Y;Test.Pitch=Pitch;return Correction(Y,Pitch,P.Heading).RotateVector(Direction)-(Target-Origin(Turn(Base,C,Test))).GetSafeNormal(1.e-24);};
        FVector R=Residual(P.Yaw,P.Pitch);
        for(int I=0;I<24&&R.Size()>1.e-9;++I){const double H=1.e-5;const FVector A=(Residual(P.Yaw+H,P.Pitch)-R)/H,B=(Residual(P.Yaw,P.Pitch+H)-R)/H;
            const double AA=(A|A)+1.e-6,AB=A|B,BB=(B|B)+1.e-6,AR=A|R,BR=B|R,D=AA*BB-AB*AB;if(D<1.e-14)break;
            double DY=(-BB*AR+AB*BR)/D,DP=(AB*AR-AA*BR)/D,Limit=FMath::Max(1.,FVector2D(DY,DP).Size()/.5);DY/=Limit;DP/=Limit;
            bool Accepted=false;for(double Step=1;Step>=1./64;Step/=2){const FVector Next=Residual(P.Yaw+DY*Step,P.Pitch+DP*Step);if(Next.Size()<R.Size()){P.Yaw+=DY*Step;P.Pitch+=DP*Step;R=Next;Accepted=true;break;}}if(!Accepted)break;
        }
    }
    P.Rotation=Correction(P.Yaw,P.Pitch,P.Heading);P.Entry=P.Valid&&ArmedPose;if(P.Entry)P.ArmedLocal=Local(*ArmedPose,C);return P;
}
static FPose Apply(FPose Source,const FProfile& C,const FPlan& P,double Frame)
{
    if(!P.Half&&!P.Valid)return Source;
    if(P.Entry&&P.Armed>0&&Frame<P.Armed){auto L=Local(P.Initial,C);const double U=Smooth(Frame/P.Armed);
        for(int J=0;J<L.Num();++J)L[J]=FTransform(Slerp(L[J].GetRotation(),P.ArmedLocal[J].GetRotation(),U),J<2?FMath::Lerp(L[J].GetLocation(),P.ArmedLocal[J].GetLocation(),U):Offset(L[J].GetLocation(),P.ArmedLocal[J].GetLocation(),U));Source=FK(MoveTemp(L),C);}
    if(P.Half)Source=Half(Source,P.Initial,C);return P.Valid?Turn(Source,C,P,P.Armed>0?Smooth(Frame/P.Armed):1):Source;
}
FPose FModel::Raw(double F) const
{
    const auto& C=*Profile;F=FMath::Clamp(F,0.,C.End)*C.FPS/60.;const int I=FMath::Min(C.Locals.Num()-2,FMath::FloorToInt(F));const double U=Clamp(F-I);
    FPose P;P.SetNum(C.Names.Num());for(int J=0;J<P.Num();++J)P[J]=FTransform(Slerp(C.Locals[I][J].GetRotation(),C.Locals[I+1][J].GetRotation(),U),FMath::Lerp(C.Locals[I][J].GetLocation(),C.Locals[I+1][J].GetLocation(),U));return FK(MoveTemp(P),C);
}
static FPose Key(FPose P,const FProfile& C,int Joint,const TMap<int32,FQuat>& Keys,double Frame,bool ParentSpace)
{
    if(Keys.IsEmpty())return P;Frame=FMath::Min(Frame,C.End);if(FMath::Abs(Frame-FMath::RoundToDouble(Frame))<1.e-7)Frame=FMath::RoundToDouble(Frame);
    const int A=FMath::FloorToInt(Frame),B=FMath::CeilToInt(Frame);const FQuat* QA=Keys.Find(A),*QB=Keys.Find(B);
    const FQuat Q=Slerp(QA?*QA:FQuat::Identity,QB?*QB:FQuat::Identity,Frame-A),Old=P[Joint].GetRotation(),Parent=P[C.Parents[Joint]].GetRotation();
    const FQuat Next=(ParentSpace?Parent*Q*Parent.Inverse()*Old:Old*Q).GetNormalized(),Delta=Next*Old.Inverse();const FVector Origin=P[Joint].GetLocation();
    for(int J=0;J<P.Num();++J){int K=J;while(K>=0&&K!=Joint)K=C.Parents[K];if(K!=Joint)continue;P[J]=FTransform((Delta*P[J].GetRotation()).GetNormalized(),Origin+Delta.RotateVector(P[J].GetLocation()-Origin));}return P;
}
FPose FModel::Keys(FPose Pose,double Frame) const {return Key(Key(MoveTemp(Pose),*Profile,9,Profile->ForearmKeys,Frame,true),*Profile,10,Profile->HandKeys,Frame,false);}
FPose FModel::Full(double Frame) const{return Apply(Raw(Frame),*Profile,FullPlan,FMath::Clamp(Frame,0.,Profile->End));}
FTransform FModel::Held(const FPose& Pose) const {return Profile->Grip*Profile->Bind*Pose[10];}
static double Lookup(const TArray<FVector2D>& Rows,double Value,bool Angle=false)
{
    const int Key=Angle?1:0,Result=1-Key;if(Value<=Rows[0][Key])return Rows[0][Result];if(Value>=Rows.Last()[Key])return Rows.Last()[Result];
    int Lo=0,Hi=Rows.Num()-1;while(Hi-Lo>1){const int M=(Lo+Hi)/2;if(Rows[M][Key]<Value)Lo=M;else Hi=M;}
    return FMath::Lerp(Rows[Lo][Result],Rows[Hi][Result],(Value-Rows[Lo][Key])/(Rows[Hi][Key]-Rows[Lo][Key]));
}
void FModel::Prepare(const FProfile& C,double InAmount,const FVector& Target)
{
    Profile=&C;Amount=Clamp(InAmount);Trigger=C.Armed*Amount;Speed=1;
    StartSource=Amount==0?0:Lookup(C.Forward,Lookup(C.Curve,Trigger),true);EndSource=Amount==0?0:Lookup(C.Forward,Amount*Lookup(C.Curve,C.Peak),true);
    if(Amount>0&&Amount<1&&C.Peak-C.Armed>1.e-9&&EndSource-StartSource>1.e-9){const double Rate=(EndSource-StartSource)/(C.Peak-C.Armed);Speed=FMath::Lerp(Rate,1.,C.Slowdown)/Rate;}
    Release=Trigger+(C.Release-C.Armed)/Speed;Finish=Trigger+(C.Peak-C.Armed)/Speed;
    const auto Initial=Raw(0),ArmedPose=Raw(C.Armed),ReleasePose=Keys(Raw(C.Release),C.Release);const auto Weapon=Held(ReleasePose);
    FullPlan=MakePlan(C,Initial,ReleasePose,C.Velocity,Target,C.Armed,C.Kind==TEXT("bomb")?nullptr:&Weapon,&ArmedPose);
    Neutral=Local(Full(0),C);Reached=Local(Full(Trigger),C);const double H=FMath::Min(1.e-4,Trigger);const auto Previous=Local(Full(Trigger-H),C);
    const int N=C.Names.Num();Rotation.SetNum(N);Angular.SetNum(N);Translation.SetNum(N);Linear.SetNum(N);
    for(int J=0;J<N;++J){Rotation[J]=Log(Neutral[J].GetRotation().Inverse()*Reached[J].GetRotation());Angular[J]=(Rotation[J]-Log(Neutral[J].GetRotation().Inverse()*Previous[J].GetRotation()))*(H>0?1/H:0);Translation[J]=Reached[J].GetLocation()-Neutral[J].GetLocation();Linear[J]=(Reached[J].GetLocation()-Previous[J].GetLocation())*(H>0?1/H:0);}
    auto Carry=[&](double F,double Duration,bool Entry){FCarry Result;Result.Frame=F;Result.Duration=Duration;const double Step=1.e-4;
        const auto At=Local(Entry?Full(F):Motion(F,false),C),Before=Local(Entry?Full(F-Step):Motion(F-Step,false),C),After=Local(Motion(F+Step,false),C);
        for(int I=0;I<3;++I){const int J=8+I;Result.Angular[I]=(Log(Before[J].GetRotation().Inverse()*At[J].GetRotation())-Log(At[J].GetRotation().Inverse()*After[J].GetRotation()))/Step;Result.Offset[I]=(Log(FromTo(Before[J].GetLocation(),At[J].GetLocation()))-Log(FromTo(At[J].GetLocation(),After[J].GetLocation())))/Step;}return Result;};
    if(Amount>0&&Amount<1){EntryCarry=Carry(Trigger,FMath::Min(4.,C.Release-C.Armed)/Speed,true);ExitCarry=Carry(Finish,FMath::Min(8.,C.End-Finish),false);}
    PartialPlan=FPlan();if(Amount!=1&&C.Aim){const auto RP=Keys(Motion(Release),Release);const auto W=Held(RP);PartialPlan=MakePlan(C,Initial,RP,FullPlan.Rotation.RotateVector(C.Velocity),Target,Release-Trigger,C.Kind==TEXT("bomb")?nullptr:&W,nullptr);}
}
FPose FModel::Body(double Frame) const
{
    const auto& C=*Profile;auto L=Local(Full(Frame),C);if(Amount==1||Frame<=Trigger)return L;if(Amount==0)return Neutral;
    const double Effort=Amount*Amount,Settle=FMath::Min(4.,FMath::Max(1.e-9,(C.End-Trigger)/3));
    const double U=Clamp((Frame-Trigger)/Settle),Travel=Settle*(U-2.5*FMath::Pow(U,4)+3*FMath::Pow(U,5)-FMath::Pow(U,6));
    const double Return=FMath::Clamp(C.Release,Trigger+Settle,C.End-Settle),ClavEnd=FMath::Clamp(C.Release,Trigger+2*Settle,C.End);
    const double BodyResidual=(1-Effort)*(1-Smooth((Frame-Return)/FMath::Max(1.e-9,C.End-Return))),ClavResidual=(1-Effort)*(1-Smooth((Frame-Trigger)/FMath::Max(1.e-9,ClavEnd-Trigger)));
    for(int J=0;J<L.Num();++J)if(J<8||J>10){const double W=(J==7||J==11)?ClavResidual:BodyResidual;
        const FVector D=Log(Neutral[J].GetRotation().Inverse()*L[J].GetRotation());const double Length=L[J].GetLocation().Size();
        FVector P=Neutral[J].GetLocation()+(L[J].GetLocation()-Neutral[J].GetLocation())*Effort+(Translation[J]+Linear[J]*Travel)*W;if(J>=2)P=P.GetSafeNormal(1.e-24)*Length;
        L[J]=FTransform((Neutral[J].GetRotation()*Exp(D*Effort+(Rotation[J]+Angular[J]*Travel)*W)).GetNormalized(),P);}
    return L;
}
FPose FModel::Motion(double Frame,bool Carry) const
{
    const auto& C=*Profile;Frame=FMath::Clamp(Frame,0.,C.End);if(Amount==1)return Raw(Frame);if(Frame<=Trigger)return Full(Frame);
    const double Entry=(Frame-Trigger)*Speed/FMath::Max(1.e-9,FMath::Min(4.,C.Release-C.Armed)),Blend=Smooth(Entry),Recover=Smooth((Frame-Finish)/FMath::Max(1.e-9,C.End-Finish));
    const double Source=FMath::Lerp(StartSource,EndSource,Clamp((Frame-Trigger)*Speed/FMath::Max(1.e-9,C.Peak-C.Armed)));
    const auto Charged=Full(Trigger),Action=Full(Source),Start=Local(Charged,C),MotionLocal=Local(Action,C),End=Local(Full(C.End),C);auto L=Body(FMath::Min(Frame,Finish));
    for(int J=8;J<=10;++J){const auto& M=Amount==0?Start[J]:MotionLocal[J];L[J]=FTransform(Slerp(Start[J].GetRotation(),M.GetRotation(),Blend),Offset(Start[J].GetLocation(),M.GetLocation(),Blend).GetSafeNormal(1.e-24)*L[J].GetLocation().Size());}
    if(Amount>0){const auto Pose=FK(L,C);L[8].SetRotation((Pose[7].GetRotation().Inverse()*Slerp(Charged[8].GetRotation(),Action[8].GetRotation(),Blend)).GetNormalized());}
    for(int J=8;J<=10;++J)L[J]=FTransform(Slerp(L[J].GetRotation(),End[J].GetRotation(),Recover),Offset(L[J].GetLocation(),End[J].GetLocation(),Recover));
    if(Frame>Finish){const auto Current=Body(Frame);for(int J=0;J<L.Num();++J)if(J<8||J>10)L[J]=Current[J];}
    if(Carry&&Amount>0){const auto& K=Entry<1?EntryCarry:ExitCarry;const double Elapsed=Frame-K.Frame;
        if(Elapsed>0&&Elapsed<K.Duration&&(Entry<1||Frame>Finish)){const double U=Elapsed/K.Duration,M=K.Duration*(U-6*U*U*U+8*FMath::Pow(U,4)-3*FMath::Pow(U,5));
            for(int I=0;I<3;++I){const int J=8+I;L[J]=FTransform((L[J].GetRotation()*Exp(K.Angular[I]*M)).GetNormalized(),Exp(K.Offset[I]*M).RotateVector(L[J].GetLocation()));}}}
    return FK(MoveTemp(L),C);
}
FPose FModel::Sample(double Frame) const
{Frame=FMath::Clamp(Frame,0.,Profile->End);auto Pose=Motion(Frame);if(Amount==1)Pose=Apply(MoveTemp(Pose),*Profile,FullPlan,Frame);else if(PartialPlan.Valid&&Frame>Trigger)Pose=Apply(MoveTemp(Pose),*Profile,PartialPlan,Frame-Trigger);return Keys(MoveTemp(Pose),Frame);}
FTransform FModel::Launch(FVector& Velocity,FVector& Omega) const
{const auto HeldPose=Held(Sample(Release));Velocity=(PartialPlan.Rotation*FullPlan.Rotation).RotateVector(Profile->Velocity)*Amount;Omega=HeldPose.GetRotation().RotateVector(Profile->Axis)*(Profile->Twist*UE_DOUBLE_PI/3);return HeldPose;}
FVector ToUnrealPoint(const FVector& P){return FVector(P.X,P.Z,P.Y)*100.;}
FVector FromUnrealPoint(const FVector& P){return FVector(P.X,P.Z,P.Y)*.01;}
FTransform ToUnreal(const FTransform& T)
{
    // UE's FBX importer: Maya Y-up -> Z-up (-Y forward), then mirror Y.
    const FQuat Q=FQuat(FVector(1,0,0),UE_DOUBLE_PI/2)*T.GetRotation();
    return FTransform(FQuat(-Q.X,Q.Y,-Q.Z,Q.W).GetNormalized(),ToUnrealPoint(T.GetLocation()));
}
static FVector Vec(const TArray<TSharedPtr<FJsonValue>>& A){return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());}
static FQuat Quat(const TArray<TSharedPtr<FJsonValue>>& A,int I=0){return FQuat(A[I]->AsNumber(),A[I+1]->AsNumber(),A[I+2]->AsNumber(),A[I+3]->AsNumber()).GetNormalized();}
const FProfile* Profile(bool Small,FString& Error)
{
    static TArray<FProfile> Profiles;if(!Profiles.IsEmpty())return &Profiles[Small?1:0];
    FString Text;TSharedPtr<FJsonObject> Root;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("ThrowLab/Profile.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)||!Root.IsValid()){Error=TEXT("Cannot read the approved Throw Lab profile");return nullptr;}
    const TArray<TSharedPtr<FJsonValue>>* Rows=nullptr;if(!Root->TryGetArrayField(TEXT("profiles"),Rows)||Rows->Num()!=2){Error=TEXT("Invalid Throw Lab profile schema");return nullptr;}
    for(const auto& Value:*Rows){const auto O=Value->AsObject();FProfile C;C.Id=O->GetStringField(TEXT("id"));C.Kind=O->GetStringField(TEXT("kind"));C.FPS=O->GetNumberField(TEXT("fps"));C.End=O->GetNumberField(TEXT("end"));C.Release=O->GetNumberField(TEXT("release"));C.Mass=O->GetNumberField(TEXT("mass"));C.Twist=O->GetNumberField(TEXT("twist"));
        for(const auto& N:O->GetArrayField(TEXT("names")))C.Names.Add(FName(*N->AsString()));for(const auto& N:O->GetArrayField(TEXT("parents")))C.Parents.Add(int(N->AsNumber()));
        for(const auto& Row:O->GetArrayField(TEXT("locals"))){FPose P;for(const auto& B:Row->AsArray()){const auto& A=B->AsArray();P.Emplace(Quat(A,3),Vec(A));}C.Locals.Add(MoveTemp(P));}
        const auto Controls=O->GetObjectField(TEXT("controls"));C.Armed=Controls->GetNumberField(TEXT("armed"));C.Amount=Controls->GetNumberField(TEXT("throwPercent"))*.01;C.Slowdown=Controls->GetNumberField(TEXT("slowdownBlend"));C.Half=Controls->GetBoolField(TEXT("halfAttack"));C.Aim=Controls->GetBoolField(TEXT("aimAtTarget"));
        auto ReadKeys=[&](const TCHAR* Name,TMap<int32,FQuat>& Out){for(const auto& K:Controls->GetArrayField(Name)){const auto Key=K->AsObject();Out.Add(int(Key->GetNumberField(TEXT("frame"))),Euler(Vec(Key->GetArrayField(TEXT("rotation")))));}};ReadKeys(TEXT("keys"),C.HandKeys);ReadKeys(TEXT("forearmKeys"),C.ForearmKeys);
        C.Velocity=Vec(O->GetArrayField(TEXT("velocity")));C.Axis=Vec(O->GetArrayField(TEXT("longAxis")));C.Scale=Vec(O->GetArrayField(TEXT("scale")));C.COM=Vec(O->GetArrayField(TEXT("com")));C.Target=Vec(O->GetArrayField(TEXT("target")));
        const auto Bind=O->GetObjectField(TEXT("bind")),Grip=O->GetObjectField(TEXT("grip"));C.Bind=FTransform(Quat(Bind->GetArrayField(TEXT("rotation"))),Vec(Bind->GetArrayField(TEXT("position"))));C.Grip=FTransform(Euler(Vec(Grip->GetArrayField(TEXT("rotation")))),Vec(Grip->GetArrayField(TEXT("position"))));
        const auto Curve=O->GetObjectField(TEXT("curve"));C.Peak=Curve->GetNumberField(TEXT("peak"));auto ReadCurve=[&](const TCHAR* Name,TArray<FVector2D>& Out){for(const auto& V:Curve->GetArrayField(Name)){const auto P=V->AsObject();Out.Emplace(P->GetNumberField(TEXT("frame")),P->GetNumberField(TEXT("angle")));}};ReadCurve(TEXT("samples"),C.Curve);ReadCurve(TEXT("forward"),C.Forward);
        if(C.Names.Num()!=26||C.Parents.Num()!=26||C.Locals.Num()<2||C.Curve.IsEmpty()||C.Forward.IsEmpty()||C.Armed>C.Release||C.Release>C.End){Profiles.Reset();Error=TEXT("Incompatible Throw Lab skeleton/timing");return nullptr;}Profiles.Add(MoveTemp(C));
    }return &Profiles[Small?1:0];
}
}
