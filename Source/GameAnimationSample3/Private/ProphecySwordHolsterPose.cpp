#include "ProphecySwordHolsterPose.h"
#include "ProphecyAgent.h"
#include "ProphecyBlendClock.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeRWLock.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "ProphecyFKReturnMath.h"
#include "ProphecyNNPoseTypes.h"

namespace ProphecySwordHolsterPose
{
static double Clamp(double X){return FMath::Clamp(X,0.,1.);}
float UnshrinkAlpha(float& ElapsedTicks,float Duration)
{
 // Integral authored ticks prevent a three-second duration becoming181 ticks.
 ElapsedTicks+=1;
 return Duration<=0?1:float(Clamp(double(ElapsedTicks)/FMath::Max(1.,FMath::CeilToDouble(double(Duration)*60-1.e-5))));
}
static double Ease(double X){return X*X*X*(10+X*(-15+6*X));}
static double Angle(FQuat A,FQuat B){return FMath::RadiansToDegrees(A.AngularDistance(B));}
static FQuat Exp(FVector V){const double L=V.Size();return L<1.e-12?FQuat::Identity:FQuat(V/L,L);}
static FVector Log(FQuat Q){Q.Normalize();if(Q.W<0)Q=Q*-1.;const FVector V(Q.X,Q.Y,Q.Z);const double L=V.Size();return L<1.e-12?FVector::ZeroVector:V*(2*FMath::Atan2(L,Q.W)/L);}
static FVector Offset(FVector A,FVector B,double T)
{
 const double LA=A.Size(),LB=B.Size();if(LA<1.e-8||LB<1.e-8)return FMath::Lerp(A,B,T);
 return FQuat::Slerp(FQuat::Identity,FQuat::FindBetweenVectors(A,B),T).RotateVector(A/LA)*FMath::Lerp(LA,LB,T);
}
static FTransform Blend(const FTransform& A,const FTransform& B,double T)
{return FTransform(FQuat::Slerp(A.GetRotation(),B.GetRotation(),T).GetNormalized(),Offset(A.GetLocation(),B.GetLocation(),T));}
void FCurve::Prepare()
{
 double H[5],D[5];for(int I=0;I<5;++I){H[I]=Points[I+1].X-Points[I].X;D[I]=(Points[I+1].Y-Points[I].Y)/H[I];}
 Slopes[0]=D[0];Slopes[5]=D[4];for(int I=1;I<5;++I){const double A=2*H[I]+H[I-1],B=H[I]+2*H[I-1];Slopes[I]=D[I-1]*D[I]<=0?0:(A+B)/(A/D[I-1]+B/D[I]);}
}
double FCurve::Sample(double X) const
{
 X=Clamp(X);int I=0;while(I<4&&X>Points[I+1].X)++I;
 const double H=Points[I+1].X-Points[I].X,T=(X-Points[I].X)/H,T2=T*T,T3=T2*T;
 return FMath::Clamp((2*T3-3*T2+1)*Points[I].Y+(T3-2*T2+T)*H*Slopes[I]+(-2*T3+3*T2)*Points[I+1].Y+(T3-T2)*H*Slopes[I+1],Points[I].Y,Points[I+1].Y);
}
static double Number(const TSharedPtr<FJsonObject>& J,const TCHAR* Key,double Default,double Min,double Max)
{double V;return J->TryGetNumberField(Key,V)&&FMath::IsFinite(V)?FMath::Clamp(V,Min,Max):Default;}
bool LoadProfile(const FString& Path,FProfile& P,FString& Error)
{
 FString Text;if(!FFileHelper::LoadFileToString(Text,*Path)){Error=TEXT("Cannot read holster profile: ")+Path;return false;}
 TSharedPtr<FJsonObject> J;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),J)||!J){Error=TEXT("Invalid holster JSON");return false;}
 const TSharedPtr<FJsonObject>* Nested;if(J->TryGetObjectField(TEXT("parameters"),Nested))J=*Nested;
 P.AngleLimit=Number(J,TEXT("spineClavicleAngleLimit"),45,0,90);P.BodySpeed=Number(J,TEXT("maxSpineClavicleAngularSpeed"),90,.01,10000);
 P.HeadAlpha=Number(J,TEXT("headLookAtAlpha"),1,0,1);P.HeadInSpeed=Number(J,TEXT("maxHeadLookInVelocity"),180,.01,10000);P.HeadOutSpeed=Number(J,TEXT("maxHeadLookOutVelocity"),180,.01,10000);
 P.HeadInExponent=Number(J,TEXT("headLookInExponent"),1,1,8);P.HeadOutExponent=Number(J,TEXT("headLookOutExponent"),1,1,8);P.DrawHeadOut=Number(J,TEXT("drawHeadLookOutThreshold"),.3,0,1);P.SheatheHeadOut=Number(J,TEXT("sheatheHeadLookOutThreshold"),.5,0,1);
 for(int A=0;A<2;++A)
 {
  const FString Prefix=A?TEXT("sheathe"):TEXT("draw");
  for(int Phase=0;Phase<2;++Phase)
  {
   auto& C=Phase?P.Slide[A]:P.Reach[A];const TArray<TSharedPtr<FJsonValue>>* Values;
   if(J->TryGetArrayField(Prefix+(Phase?TEXT("SlideCurve"):TEXT("Curve")),Values)&&Values->Num()==4)
    for(int I=0;I<4;++I){const TArray<TSharedPtr<FJsonValue>>* Pair;if(!(*Values)[I]->TryGetArray(Pair)||Pair->Num()!=2){Error=TEXT("Invalid curve point");return false;}
     C.Points[I+1]={FMath::Clamp((*Pair)[0]->AsNumber(),C.Points[I].X+.01,1-(4-I)*.01),FMath::Clamp((*Pair)[1]->AsNumber(),C.Points[I].Y,1.)};}
   C.Prepare();
  }
  if(J->TryGetObjectField(Prefix+TEXT("Return"),Nested))
  {
   const auto& V=*Nested;auto& R=P.Return[A];V->TryGetBoolField(TEXT("enabled"),R.Enabled);V->TryGetBoolField(TEXT("worldInertia"),R.World);V->TryGetBoolField(TEXT("springReturn"),R.Spring);
   R.Duration=Number(V,TEXT("duration"),1,.1,5);R.Easing=Number(V,TEXT("returnEasing"),1,0,1);R.Inertia=Number(V,TEXT("inertia"),1,0,1);R.Hold=Number(V,TEXT("inertiaHold"),0,0,.8);R.Decay=Number(V,TEXT("inertiaDecay"),1,0,4);R.AngleTime=Number(V,TEXT("angleTimeSeconds"),.29,0,4);R.TwistRemoval=Number(V,TEXT("upperArmTwistRemoval"),0,0,1);
   const TSharedPtr<FJsonObject>* Weights;if(V->TryGetObjectField(TEXT("boneInertia"),Weights))
   {const TCHAR* Keys[]={TEXT("spine"),TEXT("clavicle"),TEXT("upperarm"),TEXT("lowerarm"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head")};for(int I=0;I<7;++I)R.Weights[I]=Number(*Weights,Keys[I],1,0,1);}
  }
 }
 return true;
}
struct FActive
{
 FProfile Profile;FStatus Status;int32 PoseId=INDEX_NONE,Pelvis=0,Spine[5],Clav,Arm[3],Neck[3];
 TArray<FName> Names;TArray<int32> Parents,Upper,Groups;TArray<FTransform> Base,Pose,Before,Entry,LastBase,ReturnStart,ReturnIdle,LastBody;
 TArray<FVector> Velocity,OffsetVelocity,WorldVelocity,WorldCorrection;
 TArray<FQuat> ReturnWorld,ReturnBaselineWorld,ReturnActualWorld;
 TArray<FTransform> Work,HeadWork,Future;TArray<FName> ReadNames;FProphecyNNPoseSnapshot Snapshot;
 TArray<TArray<FTransform>> SpringFrames;TArray<double> SpringTimes;
 TArray<FVector> SpringRates,SpringOffsetRates,SpringParentRates;TArray<FQuat> SpringWorld,SpringPreviousWorld;int32 SpringStep=0,SpringCount=0;
 FTransform Clear,Seat;FVector Mouth,SpineAxis,ClavU,ClavV,Body=FVector::ZeroVector,Desired=FVector::ZeroVector;
 FTransform SourceArm[3],DestinationArm[3],SlideA[3],SlideB[3];
 FQuat Head=FQuat::Identity,HeadStart=FQuat::Identity;bool Sheathe=true,Sliding=false,HeadOut=false,HeadDone=false,Initialized=false;
 int32 SlideStart=-1,HeadStartTick=0,LastGuide=-1;double ReachSpeed=100,RotationSpeed=180,SlideSpeed=60,SlideLength=1,HeadDuration=-1,ReturnDuration=1;
};
struct FCached {TMap<FName,FTransform> Bones;};
static TMap<TWeakObjectPtr<const AProphecyAgent>,TUniquePtr<FActive>> Active;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FProfile> Profiles;
static TMap<int32,FCached> Outputs;
static FRWLock OutputLock;static TAtomic<bool> AnyOutput(false);static thread_local bool ReadingBase=false;
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
 if(Cleanup.IsValid())return;
 Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool){
  {FWriteScopeLock Lock(OutputLock);for(auto It=Active.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==W){
    Outputs.Remove(It.Value()->PoseId);if(It.Key().IsValid())ProphecyBlendClock::Stop(It.Key().Get(),ProphecyBlendClock::EKind::SwordHolster);It.RemoveCurrent();
   }AnyOutput.Store(!Outputs.IsEmpty());}
  for(auto It=Profiles.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
 });
}
void Configure(const AProphecyAgent* A,const FProfile& P){Profiles.Add(A,P);EnsureCleanup();}
void Remove(const AProphecyAgent* A,bool ClearProfile)
{
 if(auto* S=Active.Find(A)){FWriteScopeLock Lock(OutputLock);Outputs.Remove((*S)->PoseId);AnyOutput.Store(!Outputs.IsEmpty());}
 Active.Remove(A);ProphecyBlendClock::Stop(A,ProphecyBlendClock::EKind::SwordHolster);
 if(ClearProfile)Profiles.Remove(A);
}
void Apply(int32 Id,TConstArrayView<FName> Names,TArrayView<FTransform> Pose,const FTransform& Space)
{
 if(ReadingBase||!AnyOutput.Load())return;FReadScopeLock Lock(OutputLock);const auto* C=Outputs.Find(Id);if(!C)return;
 for(int I=0;I<Names.Num();++I)if(const auto* T=C->Bones.Find(Names[I]))Pose[I]=T->GetRelativeTransform(Space);
}
static void Publish(FActive& S)
{
 FWriteScopeLock Lock(OutputLock);
 if(S.Status.Finished){Outputs.Remove(S.PoseId);AnyOutput.Store(!Outputs.IsEmpty());return;}
 auto& C=Outputs.FindOrAdd(S.PoseId);for(int J:S.Upper)C.Bones.FindOrAdd(S.Names[J])=S.Pose[J];AnyOutput.Store(true);
}
static void BodyPose(const FActive& S,TConstArrayView<FTransform> Base,FVector V,TArray<FTransform>& Out,bool ShoulderOnly=false)
{
 Out.SetNum(Base.Num());if(ShoulderOnly)Out[S.Pelvis]=Base[S.Pelvis];else for(int I=0;I<Base.Num();++I)Out[I]=Base[I];const FQuat Top=Base[S.Spine[4]].GetRotation();const FQuat World=(Top*Exp(S.SpineAxis*V.X)*Top.Inverse()).GetNormalized(),Swing=Exp(S.ClavU*V.Y+S.ClavV*V.Z);
 auto Bone=[&](int J){const int P=S.Parents[J];const FQuat Carry=(Out[P].GetRotation()*Base[P].GetRotation().Inverse()).GetNormalized();FQuat Q=(Carry*Base[J].GetRotation()).GetNormalized();
  for(int K=0;K<5;++K)if(J==S.Spine[K])Q=(FQuat::Slerp(FQuat::Identity,World,(K+1)/5.)*Base[J].GetRotation()).GetNormalized();
  if(J==S.Clav)Q=(Q*Swing).GetNormalized();Out[J]=FTransform(Q,Out[P].GetLocation()+Carry.RotateVector(Base[J].GetLocation()-Base[P].GetLocation()));};
 if(ShoulderOnly){for(int J:S.Spine)Bone(J);Bone(S.Clav);Bone(S.Arm[0]);}else for(int J:S.Upper)Bone(J);
}
static FVector Bounded(FVector V,double Limit)
{V.X=FMath::Clamp(V.X,-Limit,Limit);const double L=FMath::Sqrt(V.Y*V.Y+V.Z*V.Z);if(L>Limit){V.Y*=Limit/L;V.Z*=Limit/L;}return V;}
static FVector Optimize(FActive& S)
{
 const double Limit=FMath::DegreesToRadians(S.Profile.AngleLimit);TArray<FTransform> Scratch;Scratch.Reserve(S.Base.Num());
 auto Score=[&](FVector V){BodyPose(S,S.Base,V,Scratch,true);return FVector::DistSquared(Scratch[S.Arm[0]].GetLocation(),S.Clear.GetLocation());};
 FVector Best=Bounded(S.Desired,Limit);double Cost=Score(Best);if(Score(FVector::ZeroVector)<Cost){Best=FVector::ZeroVector;Cost=Score(Best);}
 for(double Degrees:{16.,8.,4.,2.,1.,.5,.125,.03125})for(int Sweep=0;Sweep<4;++Sweep){bool Improved=false;
  for(int K=0;K<3;++K)for(double Sign:{-1.,1.}){FVector V=Best;V[K]+=Sign*FMath::DegreesToRadians(Degrees);V=Bounded(V,Limit);const double C=Score(V);if(C<Cost-1.e-9){Best=V;Cost=C;Improved=true;}}
  if(!Improved)break;
 }return Best;
}
static void CaptureArm(const FActive& S,TConstArrayView<FTransform> Pose,FTransform (&Out)[3])
{for(int K=0;K<3;++K)Out[K]=Pose[S.Arm[K]].GetRelativeTransform(Pose[S.Parents[S.Arm[K]]]);}
static void ApplyArm(const FActive& S,TArray<FTransform>& Pose,const FTransform (&Local)[3])
{
 for(int K=0;K<3;++K){const int J=S.Arm[K],P=S.Parents[J];const FVector Original=Pose[J].GetLocation();FTransform L=Local[K];
  if(K>0)L.SetTranslation(L.GetLocation().GetSafeNormal()*FVector::Distance(S.Base[J].GetLocation(),S.Base[P].GetLocation()));
  Pose[J]=L*Pose[P];if(K==0)Pose[J].SetTranslation(Original);}
}
static void Solve(FActive& S,TArray<FTransform>& P,const FTransform& Goal)
{
 const int A=S.Arm[0],B=S.Arm[1],C=S.Arm[2];const FVector X=P[A].GetLocation(),Y=P[B].GetLocation(),Z=P[C].GetLocation();
 const double L1=(Y-X).Size(),L2=(Z-Y).Size();const FVector D=(Goal.GetLocation()-X).GetSafeNormal(SMALL_NUMBER,FVector::ForwardVector);
 const double L=FMath::Clamp((Goal.GetLocation()-X).Size(),FMath::Abs(L1-L2)+.001,L1+L2-.001),Along=(L1*L1+L*L-L2*L2)/(2*L);
 FVector Pole=FVector::VectorPlaneProject(Y-X,D).GetSafeNormal();if(Pole.IsNearlyZero())Pole=FVector::CrossProduct(D,FMath::Abs(D.Z)<.9?FVector::UpVector:FVector::RightVector).GetSafeNormal();
 const FVector E=X+D*Along+Pole*FMath::Sqrt(FMath::Max(0.,L1*L1-Along*Along)),H=X+D*L;
 P[A].SetRotation((FQuat::FindBetweenVectors(Y-X,E-X)*P[A].GetRotation()).GetNormalized());P[B]=FTransform((FQuat::FindBetweenVectors(Z-Y,H-E)*P[B].GetRotation()).GetNormalized(),E);P[C]=FTransform(Goal.GetRotation(),H);
}
static double ArmDuration(const FTransform (&A)[3],const FTransform (&B)[3],double Linear,double Angular)
{
 FTransform Last[3],PrevLocal[3];for(int J=0;J<3;++J){PrevLocal[J]=A[J];FTransform L=A[J];if(!J)L.SetTranslation(FVector::ZeroVector);Last[J]=J?L*Last[J-1]:L;}
 double Seconds=1./60.;for(int I=1;I<=96;++I){FTransform Pose[3],Local[3];for(int J=0;J<3;++J){Local[J]=Blend(A[J],B[J],Ease(I/96.));FTransform L=Local[J];if(!J)L.SetTranslation(FVector::ZeroVector);Pose[J]=J?L*Pose[J-1]:L;
  Seconds=FMath::Max(Seconds,Angle(PrevLocal[J].GetRotation(),Local[J].GetRotation())*96/Angular);}
  Seconds=FMath::Max3(Seconds,FVector::Distance(Pose[2].GetLocation(),Last[2].GetLocation())*96/Linear,Angle(Last[2].GetRotation(),Pose[2].GetRotation())*96/Angular);
  for(int J=0;J<3;++J){Last[J]=Pose[J];PrevLocal[J]=Local[J];}
 }return Seconds*1.002;
}
static FTransform Goal(const FActive& S,double Progress)
{return FTransform(S.Seat.GetRotation(),FMath::Lerp(S.Clear.GetLocation(),S.Seat.GetLocation(),S.Sheathe?Progress:1-Progress));}
static void Endpoint(FActive& S,FVector Body,const FTransform& Target,const FTransform (&Seed)[3],FTransform (&Out)[3])
{
 BodyPose(S,S.Base,Body,S.Work);ApplyArm(S,S.Work,Seed);Solve(S,S.Work,Target);CaptureArm(S,S.Work,Out);
}
static bool ReadBase(AProphecyAgent* A,FActive& S)
{
 float Alpha;TGuardValue<bool> Guard(ReadingBase,true);
 return A->ReadNNFutureWorldPoseWithSnapshot(S.ReadNames,S.Future,S.Base,Alpha,S.Snapshot)&&S.ReadNames==S.Names;
}
bool Begin(AProphecyAgent* A,bool Sheathe,double Reach,double Rotation,double Slide,double Length,const FTransform& Clear,const FTransform& Seat,const FVector& Mouth)
{
 const auto* Mesh=A?A->GetPoseReferenceMesh():nullptr;
 if(!Mesh||!Mesh->GetSkeletalMeshAsset())return false;
 Remove(A);auto S=MakeUnique<FActive>();S->Sheathe=Sheathe;S->ReachSpeed=Reach;S->RotationSpeed=Rotation;S->SlideSpeed=Slide;S->SlideLength=Length;S->Clear=Clear;S->Seat=Seat;S->Mouth=Mouth;
 if(const auto* P=Profiles.Find(A))S->Profile=*P;
 float Interval,Alpha;bool Interpolate;if(!A->GetNNPoseDataSource(S->PoseId,Interval,Interpolate))
 {const auto* Anim=Cast<UProphecyNNLocomotionAnimInstance>(Mesh->GetAnimInstance());if(!Anim)return false;S->PoseId=Anim->AgentId;}
 TArray<FTransform> Future;{TGuardValue<bool> Guard(ReadingBase,true);if(!A->ReadNNFutureWorldPose(S->Names,Future,S->Base,Alpha))return false;}
 auto Find=[&](const TCHAR* N){return S->Names.IndexOfByKey(FName(N));};S->Pelvis=Find(TEXT("pelvis"));S->Clav=Find(TEXT("clavicle_r"));
 for(int I=0;I<5;++I)S->Spine[I]=Find(*FString::Printf(TEXT("spine_0%d"),I+1));
 const TCHAR* Arm[]={TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};const TCHAR* Neck[]={TEXT("neck_01"),TEXT("neck_02"),TEXT("head")};
 for(int I=0;I<3;++I){S->Arm[I]=Find(Arm[I]);S->Neck[I]=Find(Neck[I]);if(S->Arm[I]<0||S->Neck[I]<0)return false;}for(int J:S->Spine)if(J<0)return false;if(S->Pelvis<0||S->Clav<0)return false;
 const auto& Ref=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();S->Parents.SetNum(S->Names.Num());S->Groups.Init(-1,S->Names.Num());
 for(int J=0;J<S->Names.Num();++J){int B=Ref.FindBoneIndex(S->Names[J]),P=INDEX_NONE;while(B>=0){B=Ref.GetParentIndex(B);if(B>=0){P=S->Names.IndexOfByKey(Ref.GetBoneName(B));if(P>=0)break;}}S->Parents[J]=P;

  const FString N=S->Names[J].ToString();if(N.StartsWith(TEXT("spine_")))S->Groups[J]=0;else if(N.StartsWith(TEXT("clavicle_")))S->Groups[J]=1;else if(N.StartsWith(TEXT("upperarm_")))S->Groups[J]=2;else if(N.StartsWith(TEXT("lowerarm_")))S->Groups[J]=3;else if(J==S->Neck[0])S->Groups[J]=4;else if(J==S->Neck[1])S->Groups[J]=5;else if(J==S->Neck[2])S->Groups[J]=6;
 }
 for(int J=0;J<S->Names.Num();++J){for(int K=J;K>=0;K=S->Parents[K])if(K==S->Spine[0]){S->Upper.Add(J);break;}}
 const FQuat Top=S->Base[S->Spine[4]].GetRotation();S->SpineAxis=Top.UnrotateVector(S->Base[S->Neck[0]].GetLocation()-S->Base[S->Spine[4]].GetLocation()).GetSafeNormal();
 const FVector Axis=S->Base[S->Clav].GetRotation().UnrotateVector(S->Base[S->Arm[0]].GetLocation()-S->Base[S->Clav].GetLocation()).GetSafeNormal();S->ClavU=FVector::CrossProduct(Axis,FMath::Abs(Axis.X)<.8?FVector::ForwardVector:FVector::RightVector).GetSafeNormal();S->ClavV=FVector::CrossProduct(Axis,S->ClavU);
 S->Desired=Optimize(*S);CaptureArm(*S,S->Base,S->SourceArm);Endpoint(*S,S->Desired,Sheathe?Clear:Seat,S->SourceArm,S->DestinationArm);
 S->Status.ReachTicks=FMath::CeilToInt(ArmDuration(S->SourceArm,S->DestinationArm,Reach,Rotation)*60);
 const double BodyTicks=FMath::Max(FMath::Abs(S->Desired.X),FVector2D(S->Desired.Y,S->Desired.Z).Size())/FMath::DegreesToRadians(S->Profile.BodySpeed)*60;
 // Drawing waits for the turn before grip. Sheathing may arrive earlier when
 // the body speed cap prevents matching the wrist deadline, as in the lab.
 if(!Sheathe)S->Status.ReachTicks=FMath::Max(S->Status.ReachTicks,FMath::CeilToInt(BodyTicks));
 S->Status.SlideTicks=FMath::Max(1,FMath::CeilToInt(Length/Slide*60));
 S->Pose=S->Before=S->Entry=S->LastBase=S->LastBody=S->Base;S->Head=S->Base[S->Neck[2]].GetRotation();S->HeadStart=S->Head;S->Status.Ready=true;
 Publish(*S);Active.Add(A,MoveTemp(S));EnsureCleanup();ProphecyBlendClock::Start(A,ProphecyBlendClock::EKind::SwordHolster);return true;
}
bool Status(const AProphecyAgent* A,FStatus& Out){const auto* S=Active.IsEmpty()?nullptr:Active.Find(A);if(!S)return false;Out=(*S)->Status;return true;}
void SetSliding(const AProphecyAgent* A,bool Value){if(auto* P=Active.Find(A)){auto& S=**P;if(Value&&!S.Sliding){S.Sliding=true;S.Desired=S.Body;S.SlideStart=S.Status.Tick;S.LastGuide=-1;}}}
void SetTargets(const AProphecyAgent* A,const FTransform& Clear,const FTransform& Seat,const FVector& Mouth){if(auto* P=Active.Find(A)){(*P)->Clear=Clear;(*P)->Seat=Seat;(*P)->Mouth=Mouth;}}
static void HeadPose(FActive& S,const TArray<FTransform>& Input,FQuat Q,TArray<FTransform>& Out)
{
 Out=Input;const FQuat Correction=(Q*Input[S.Neck[2]].GetRotation().Inverse()).GetNormalized();
 for(int K=0;K<3;++K){const int J=S.Neck[K],P=S.Parents[J];const FQuat Carry=(Out[P].GetRotation()*Input[P].GetRotation().Inverse()).GetNormalized();
  Out[J]=FTransform((FQuat::Slerp(FQuat::Identity,Correction,(K+1)/3.)*Input[J].GetRotation()).GetNormalized(),Out[P].GetLocation()+Carry.RotateVector(Input[J].GetLocation()-Input[P].GetLocation()));}
}
static void HeadStep(FActive& S)
{
 const bool Out=S.Sliding&&S.Status.SlideProgress>=(S.Sheathe?S.Profile.SheatheHeadOut:S.Profile.DrawHeadOut)-1.e-8;
 if(Out!=S.HeadOut){S.HeadOut=Out;S.HeadStart=S.Head;S.HeadStartTick=S.Status.Tick-1;S.HeadDuration=-1;}
 const double Speed=Out?S.Profile.HeadOutSpeed:S.Profile.HeadInSpeed,Exponent=Out?S.Profile.HeadOutExponent:S.Profile.HeadInExponent;
 const FQuat Previous=S.Head,Forward=S.Base[S.Neck[2]].GetRotation();FQuat Desired=Forward;auto& Temp=S.HeadWork;
 for(int I=0;I<(Out?1:8);++I){HeadPose(S,S.Pose,S.Head,Temp);const FVector Direction=S.Mouth-Temp[S.Neck[2]].GetLocation();
  Desired=Out||Direction.IsNearlyZero()?Forward:FQuat::Slerp(Forward,(FQuat::FindBetweenVectors(Forward.RotateVector(FVector::RightVector),Direction)*Forward).GetNormalized(),S.Profile.HeadAlpha).GetNormalized();
  FQuat Target=Desired;if(Exponent>1){if(S.HeadDuration<0)S.HeadDuration=FMath::Max(1.,Exponent*Angle(S.HeadStart,Desired)/Speed*60);const double U=Clamp((S.Status.Tick-S.HeadStartTick)/S.HeadDuration),X=FMath::Pow(U,Exponent),Y=FMath::Pow(1-U,Exponent);Target=FQuat::Slerp(S.HeadStart,Desired,X/(X+Y)).GetNormalized();}
  const double D=Angle(Previous,Target);S.Head=FQuat::Slerp(Previous,Target,D>Speed/60?Speed/60/D:1).GetNormalized();
 }
 S.Status.HeadStep=Angle(Previous,S.Head);S.HeadDone=Out&&Angle(S.Head,Desired)<.001;HeadPose(S,S.Pose,S.Head,Temp);Swap(S.Pose,Temp);
}
static void BeginReturn(FActive& S)
{
 const auto& R=S.Profile.Return[S.Sheathe];const int N=S.Base.Num();S.ReturnStart.SetNum(N);S.ReturnIdle.SetNum(N);S.Velocity.SetNumZeroed(N);S.OffsetVelocity.SetNumZeroed(N);S.WorldVelocity.SetNumZeroed(N);S.WorldCorrection.SetNumZeroed(N);S.ReturnWorld.SetNum(N);S.ReturnBaselineWorld.SetNum(N);S.ReturnActualWorld.SetNum(N);
 TArray<FQuat> PreviousWorld;PreviousWorld.SetNum(N);
 for(int J=0;J<N;++J){const int P=S.Parents[J];S.ReturnStart[J]=P>=0?S.Pose[J].GetRelativeTransform(S.Pose[P]):S.Pose[J];S.ReturnIdle[J]=P>=0?S.Base[J].GetRelativeTransform(S.Base[P]):S.Base[J];
  const FTransform Before=P>=0?S.LastBody[J].GetRelativeTransform(S.LastBody[P]):S.LastBody[J],BaseBefore=P>=0?S.LastBase[J].GetRelativeTransform(S.LastBase[P]):S.LastBase[J];
  const FQuat Previous=(S.ReturnIdle[J].GetRotation()*BaseBefore.GetRotation().Inverse()*Before.GetRotation()).GetNormalized();
  const FVector PreviousOffset=FQuat::FindBetweenVectors(BaseBefore.GetLocation(),S.ReturnIdle[J].GetLocation()).RotateVector(Before.GetLocation());
  S.OffsetVelocity[J]=Log(FQuat::FindBetweenVectors(PreviousOffset,S.ReturnStart[J].GetLocation()))*60;
  S.ReturnWorld[J]=P>=0?(S.ReturnWorld[P]*S.ReturnStart[J].GetRotation()).GetNormalized():S.ReturnStart[J].GetRotation();
  PreviousWorld[J]=P>=0?(PreviousWorld[P]*Previous).GetNormalized():Previous;
  S.WorldVelocity[J]=Log(S.ReturnWorld[J]*PreviousWorld[J].Inverse())*60;
 }
 S.ReturnDuration=R.Duration+R.AngleTime*Angle(S.ReturnStart[S.Spine[0]].GetRotation(),S.ReturnIdle[S.Spine[0]].GetRotation())/90;
 TArray<FVector> ActualRate,BaseRate;ActualRate.Init(FVector::ZeroVector,N);BaseRate.Init(FVector::ZeroVector,N);
 for(int J:S.Upper){const int P=S.Parents[J],G=S.Groups[J];const FVector IdleVelocity=Log(S.ReturnStart[J].GetRotation().Inverse()*S.ReturnIdle[J].GetRotation())*((1-R.Easing)/S.ReturnDuration);
  BaseRate[J]=(P>=0?BaseRate[P]:FVector::ZeroVector)+S.ReturnWorld[J].RotateVector(IdleVelocity);
  S.WorldCorrection[J]=S.WorldVelocity[J]-BaseRate[J];const bool Inertial=G>=0&&R.Inertia*R.Weights[G]>0;
  S.Velocity[J]=Inertial?S.ReturnWorld[J].UnrotateVector(S.WorldVelocity[J]-(P>=0?ActualRate[P]:FVector::ZeroVector))-IdleVelocity:FVector::ZeroVector;
  ActualRate[J]=(P>=0?ActualRate[P]:FVector::ZeroVector)+S.ReturnWorld[J].RotateVector(IdleVelocity+S.Velocity[J]);
 }
 S.Status.Returning=true;
}
static void MountReturn(FActive& S,const TArray<FTransform>& Locals)
{
 for(int J:S.Upper){const int P=S.Parents[J];const auto Moving=S.Base[J].GetRelativeTransform(S.Base[P]);const auto& Idle=S.ReturnIdle[J];
  const FQuat Q=(Moving.GetRotation()*Idle.GetRotation().Inverse()*Locals[J].GetRotation()).GetNormalized();
  const FVector V=FQuat::FindBetweenVectors(Idle.GetLocation(),Moving.GetLocation()).RotateVector(Locals[J].GetLocation());S.Pose[J]=FTransform(Q,V)*S.Pose[P];}
}
static void AdvanceSpring(FActive& S,double Elapsed)
{
 const auto& R=S.Profile.Return[S.Sheathe];const int N=S.Base.Num();
 if(S.SpringFrames.IsEmpty()){
  S.SpringCount=FMath::CeilToInt(S.ReturnDuration*480);S.SpringStep=0;S.SpringFrames.Add(S.ReturnStart);S.SpringFrames.Add(S.ReturnStart);S.SpringTimes={0,0};
  S.SpringRates=S.Velocity;S.SpringOffsetRates=S.OffsetVelocity;S.SpringParentRates.Init(FVector::ZeroVector,N);S.SpringWorld=S.ReturnWorld;
  for(int J:S.Upper)S.SpringRates[J]=R.World?S.WorldVelocity[J]:S.Velocity[J]+Log(S.ReturnStart[J].GetRotation().Inverse()*S.ReturnIdle[J].GetRotation())*((1-R.Easing)/S.ReturnDuration);
 }
 // Only two neighbouring samples are retained. No per-agent 480-Hz pose bank.
 while(S.SpringTimes[1]<Elapsed&&S.SpringStep<S.SpringCount){
  ++S.SpringStep;S.SpringFrames[0]=S.SpringFrames[1];S.SpringTimes[0]=S.SpringTimes[1];
  const double Time=S.ReturnDuration*(1-FMath::Square(1-double(S.SpringStep)/S.SpringCount)),Dt=Time-S.SpringTimes[0],X=Time/S.ReturnDuration,Ordinary=X+(Ease(X)-X)*R.Easing;
  const double Frequency=(.15+6*FMath::Pow(X,1+3*R.Easing))/FMath::Max(S.ReturnDuration-Time,Dt);S.SpringPreviousWorld=S.SpringWorld;
  auto& Local=S.SpringFrames[1];auto& World=S.SpringWorld;auto& Rates=S.SpringRates;auto& OffsetRates=S.SpringOffsetRates;auto& ParentRates=S.SpringParentRates;const auto& Previous=S.SpringPreviousWorld;
  for(int J:S.Upper){const int P=S.Parents[J],G=S.Groups[J];const double Effective=G>=0?R.Inertia*R.Weights[G]:0;
   if(Effective>0){const double K=Frequency*Frequency/FMath::Max(.05,Effective),C=2*FMath::Sqrt(K)*((.35+.65*R.Decay)*(1-X*X)+X*X),Den=1+C*Dt+K*Dt*Dt;
    if(R.World){const FQuat Target=(World[P]*S.ReturnIdle[J].GetRotation()).GetNormalized();Rates[J]=(Rates[J]+(Log(Target*Previous[J].Inverse())*K+ParentRates[P]*C)*Dt)/Den;World[J]=(Exp(Rates[J]*Dt)*Previous[J]).GetNormalized();Local[J].SetRotation((World[P].Inverse()*World[J]).GetNormalized());}
    else{Rates[J]=(Rates[J]+Log(Local[J].GetRotation().Inverse()*S.ReturnIdle[J].GetRotation())*(K*Dt))/Den;Local[J].SetRotation((Local[J].GetRotation()*Exp(Rates[J]*Dt)).GetNormalized());World[J]=(World[P]*Local[J].GetRotation()).GetNormalized();}
    OffsetRates[J]=(OffsetRates[J]+Log(FQuat::FindBetweenVectors(Local[J].GetLocation(),S.ReturnIdle[J].GetLocation()))*(K*Dt))/Den;Local[J].SetTranslation(Exp(OffsetRates[J]*Dt).RotateVector(Local[J].GetLocation()));
   }else{Local[J]=Blend(S.ReturnStart[J],S.ReturnIdle[J],Ordinary);World[J]=(World[P]*Local[J].GetRotation()).GetNormalized();}
   ParentRates[J]=Log(World[J]*Previous[J].Inverse())/Dt;
  }
  S.SpringTimes[1]=Time;
  if(S.SpringStep==S.SpringCount)for(int J:S.Upper){auto& End=Local[J];End=S.ReturnIdle[J];End.SetTranslation(End.GetLocation().GetSafeNormal()*S.ReturnStart[J].GetLocation().Size());}
 }
}
static void ReturnStep(FActive& S,double Elapsed)
{
 const auto& R=S.Profile.Return[S.Sheathe];if(!R.Enabled){MountReturn(S,S.ReturnStart);return;}const double X=Clamp(Elapsed/S.ReturnDuration);if(X>=1){S.Pose=S.Base;return;}
 auto& Locals=S.Work;Locals=S.ReturnStart;
 if(R.Spring&&R.Inertia>0){AdvanceSpring(S,Elapsed);const double T=Clamp((Elapsed-S.SpringTimes[0])/FMath::Max(1.e-12,S.SpringTimes[1]-S.SpringTimes[0]));for(int J:S.Upper)Locals[J]=Blend(S.SpringFrames[0][J],S.SpringFrames[1][J],T);MountReturn(S,Locals);return;}
 const double BlendAlpha=X+(Ease(X)-X)*R.Easing,Fade=Clamp((X-R.Hold)/(1-R.Hold)),Phase=R.Hold>0?Fade*Fade:X,Envelope=Elapsed*FMath::Pow(1-Phase,3);
 S.ReturnBaselineWorld=S.ReturnWorld;S.ReturnActualWorld=S.ReturnWorld;
 for(int J:S.Upper){const int P=S.Parents[J],G=S.Groups[J];const auto& Start=S.ReturnStart[J];const auto& Idle=S.ReturnIdle[J];const FQuat Baseline=FQuat::Slerp(Start.GetRotation(),Idle.GetRotation(),BlendAlpha).GetNormalized();FQuat Q=Baseline;FVector V=Offset(Start.GetLocation(),Idle.GetLocation().GetSafeNormal()*Start.GetLocation().Size(),BlendAlpha);
  const double Effective=G>=0?R.Inertia*R.Weights[G]:0,M=Effective>0?Envelope*FMath::Exp(-R.Decay*Phase/(.025+.45*Effective)):0;
  S.ReturnBaselineWorld[J]=(S.ReturnBaselineWorld[P]*Baseline).GetNormalized();
  if(M>0){if(!R.World)Q=(Q*Exp(S.Velocity[J]*M)).GetNormalized();V=Exp(S.OffsetVelocity[J]*M).RotateVector(V);}
  if(R.World){S.ReturnActualWorld[J]=M>0?(Exp(S.WorldCorrection[J]*M)*S.ReturnBaselineWorld[J]).GetNormalized():(S.ReturnActualWorld[P]*Baseline).GetNormalized();Q=(S.ReturnActualWorld[P].Inverse()*S.ReturnActualWorld[J]).GetNormalized();}
  Locals[J]=FTransform(Q,V);
 }
 if(R.TwistRemoval>0&&Envelope>0){
  TArray<FQuat,TInlineAllocator<32>> Corrected,Carry;
  if(R.World){Corrected.Append(S.ReturnActualWorld);Carry.Init(FQuat::Identity,S.Names.Num());}
  for(int J:S.Upper){const int P=S.Parents[J],G=S.Groups[J];
   if(R.World)Carry[J]=Carry[P];
   if(G==2&&R.Inertia*R.Weights[G]>0){const int Child=S.Names.IndexOfByKey(FName(*S.Names[J].ToString().Replace(TEXT("upperarm"),TEXT("lowerarm"))));if(Child>=0){
    const FQuat Baseline=R.World?S.ReturnBaselineWorld[J]:FQuat::Slerp(S.ReturnStart[J].GetRotation(),S.ReturnIdle[J].GetRotation(),BlendAlpha).GetNormalized();
    const FQuat Raw=R.World?S.ReturnActualWorld[J]:Locals[J].GetRotation();
    const FQuat Q=FQuat(ProphecyFKReturn::RemoveAxialInertia(FQuat4f(Baseline),FQuat4f(Raw),FVector3f(Locals[Child].GetLocation().GetSafeNormal()),R.TwistRemoval));
    if(R.World){Corrected[J]=Q;Carry[J]=(Q*Raw.Inverse()).GetNormalized();}else Locals[J].SetRotation(Q);
   }}else if(R.World)Corrected[J]=(Carry[J]*S.ReturnActualWorld[J]).GetNormalized();
   if(R.World)Locals[J].SetRotation((Corrected[P].Inverse()*Corrected[J]).GetNormalized());
  }
 }
 MountReturn(S,Locals);
}
static void Advance(FActive& S,int Steps)
{
 for(int Step=0;Step<Steps;++Step){++S.Status.Tick;S.Before=S.Pose;S.Pose=S.Base;
  if(!S.Sliding&&S.Status.Tick%4==0)S.Desired=Optimize(S);
  const double ReachFraction=S.Profile.Reach[S.Sheathe].Sample(double(S.Status.Tick)/S.Status.ReachTicks);S.Status.Progress=Ease(ReachFraction);S.Status.ReachDone=S.Status.Tick>=S.Status.ReachTicks;
  S.Status.SlideProgress=S.Sliding?S.Profile.Slide[S.Sheathe].Sample(double(S.Status.Tick-S.SlideStart)/S.Status.SlideTicks):0;
  const double SourceReachTicks=S.Status.Tick>=S.Status.ReachTicks?S.Status.Tick:ReachFraction*S.Status.ReachTicks;
  const FVector Scheduled=Bounded(S.Desired*ReachFraction,FMath::DegreesToRadians(S.Profile.BodySpeed)*SourceReachTicks/60);
  if(!S.Sliding){
   const double PreviousSource=S.Status.Tick-1>=S.Status.ReachTicks?S.Status.Tick-1:S.Profile.Reach[S.Sheathe].Sample(double(S.Status.Tick-1)/S.Status.ReachTicks)*S.Status.ReachTicks;
   const FVector Delta=Bounded(Scheduled-S.Body,FMath::DegreesToRadians(S.Profile.BodySpeed)*FMath::Max(1.,SourceReachTicks-PreviousSource)/60);
   S.Body+=Delta;
  }else S.Body=Scheduled;
  if(S.Sheathe&&S.Sliding){S.Body.Y*=1-S.Status.SlideProgress;S.Body.Z*=1-S.Status.SlideProgress;}
  if(!S.Sheathe&&!S.Sliding)S.Status.ReachDone&=FMath::Max(FMath::Abs(S.Desired.X-S.Body.X),FVector2D(S.Desired.Y-S.Body.Y,S.Desired.Z-S.Body.Z).Size())<FMath::DegreesToRadians(.25);
  BodyPose(S,S.Base,S.Body,S.Pose);
  if(!S.Sliding){if(S.Status.Tick%4==0||S.Status.ReachDone)Endpoint(S,S.Desired,S.Sheathe?S.Clear:S.Seat,S.SourceArm,S.DestinationArm);
   FTransform L[3];for(int K=0;K<3;++K)L[K]=Blend(S.SourceArm[K],S.DestinationArm[K],S.Status.Progress);ApplyArm(S,S.Pose,L);
  }else if(!S.Status.Returning){
   const double SourceTick=S.Status.SlideProgress*S.Status.SlideTicks;
   const int Count=FMath::Min(S.Status.SlideTicks,FMath::Max3<int32>(1,FMath::CeilToInt(S.Status.SlideTicks/4.),FMath::CeilToInt(S.SlideLength/2.)));
   int Guide=FMath::Min(Count-1,FMath::FloorToInt(SourceTick*Count/S.Status.SlideTicks));
   while(Guide>0&&FMath::RoundToInt(double(Guide)*S.Status.SlideTicks/Count)>SourceTick)--Guide;
   while(Guide<Count-1&&FMath::RoundToInt(double(Guide+1)*S.Status.SlideTicks/Count)<SourceTick)++Guide;
   const double TickA=FMath::RoundToInt(double(Guide)*S.Status.SlideTicks/Count),TickB=FMath::RoundToInt(double(Guide+1)*S.Status.SlideTicks/Count);
   if(Guide!=S.LastGuide){const double A0=TickA/S.Status.SlideTicks,B0=TickB/S.Status.SlideTicks;FVector BodyA=S.Desired,BodyB=S.Desired;
    if(S.Sheathe){BodyA.Y*=1-A0;BodyA.Z*=1-A0;BodyB.Y*=1-B0;BodyB.Z*=1-B0;}
    Endpoint(S,BodyA,Goal(S,A0),S.DestinationArm,S.SlideA);Endpoint(S,BodyB,Goal(S,B0),S.SlideA,S.SlideB);S.LastGuide=Guide;}
   const double T=Clamp((SourceTick-TickA)/FMath::Max(1.,TickB-TickA));FTransform L[3];for(int K=0;K<3;++K)L[K]=Blend(S.SlideA[K],S.SlideB[K],T);ApplyArm(S,S.Pose,L);
   if(S.Status.SlideProgress>=1)BeginReturn(S);
  }
  const double ReturnElapsed=S.Sliding?FMath::Max(0.,double(S.Status.Tick-S.SlideStart-S.Status.SlideTicks)/60):0;
  if(S.Status.Returning&&ReturnElapsed>0)ReturnStep(S,ReturnElapsed);
  S.Status.HandError=FVector::Distance(S.Pose[S.Arm[2]].GetLocation(),(S.Sliding?Goal(S,S.Status.SlideProgress):S.Sheathe?S.Clear:S.Seat).GetLocation());
  S.Status.Blocked=!S.Sliding&&S.Status.ReachDone&&S.Status.HandError>2;S.LastBody=S.Pose;HeadStep(S);S.LastBase=S.Base;
  S.Status.Finished=S.Status.Returning&&S.HeadDone&&(!S.Profile.Return[S.Sheathe].Enabled||ReturnElapsed>=S.ReturnDuration);
 }
}
void Update(AProphecyAgent* A,int32 Id)
{
 auto* Ptr=Active.IsEmpty()?nullptr:Active.Find(A);if(!Ptr)return;auto& S=**Ptr;if(S.Status.Finished)return;
 const int Steps=FMath::RoundToInt(ProphecyBlendClock::Consume(A,ProphecyBlendClock::EKind::SwordHolster)*60);if(Steps<=0)return;
 S.PoseId=Id;if(!ReadBase(A,S))return;
 Advance(S,Steps);Publish(S);if(S.Status.Finished)ProphecyBlendClock::Stop(A,ProphecyBlendClock::EKind::SwordHolster);
}
}
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
namespace ProphecySwordHolsterPose
{
static FVector JsonVector(const TArray<TSharedPtr<FJsonValue>>& A){return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());}
static FQuat JsonQuat(const TArray<TSharedPtr<FJsonValue>>& A){return FQuat(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber(),A[3]->AsNumber());}
static FTransform JsonPose(const TSharedPtr<FJsonObject>& J){return FTransform(JsonQuat(J->GetArrayField(TEXT("q"))),JsonVector(J->GetArrayField(TEXT("p"))));}
static TArray<FTransform> JsonPoses(const TArray<TSharedPtr<FJsonValue>>& A){TArray<FTransform> Out;for(const auto& V:A)Out.Add(JsonPose(V->AsObject()));return Out;}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterNativeParity,"Prophecy.SwordHolster.NativeParity",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterNativeParity::RunTest(const FString&)
{
 for(float Duration:{0.f,.25f,.5f,3.f,5.f}){
  float Ticks=0;const int Count=FMath::Max(1,FMath::CeilToInt(Duration*60-1.e-5));
  for(int Tick=1;Tick<=Count;++Tick){const float Alpha=UnshrinkAlpha(Ticks,Duration);
   TestEqual(TEXT("Unshrink completes at the exact authored tick"),Alpha>=1,Tick==Count);}
 }
 FString Text,Error;const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordLabPort20261010");
 if(!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("parity.json")))){AddError(TEXT("Run Tools/SwordHolster/export_parity.cjs first"));return false;}
 TSharedPtr<FJsonObject> Root;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return false;
 double MaxBody=0,MaxHead=0,MaxReturn=0,MaxPosition=0,DurationError=0,CurveError=0;FString Performance;
 for(const auto& CV:Root->GetArrayField(TEXT("curves"))){const auto C=CV->AsObject();FCurve Curve;const auto& P=C->GetArrayField(TEXT("points"));for(int I=0;I<4;++I){const auto& V=P[I]->AsArray();Curve.Points[I+1]={V[0]->AsNumber(),V[1]->AsNumber()};}Curve.Prepare();const auto& Values=C->GetArrayField(TEXT("values"));for(int I=0;I<Values.Num();++I)CurveError=FMath::Max(CurveError,FMath::Abs(Curve.Sample(I/100.)-Values[I]->AsNumber()));}
 for(const auto& RV:Root->GetArrayField(TEXT("rows"))){const auto Row=RV->AsObject();FActive S;
  LoadProfile(FPaths::ProjectContentDir()/TEXT("locomotion/SwordHolsterProfile.json"),S.Profile,Error);
  for(const auto& N:Root->GetArrayField(TEXT("names")))S.Names.Add(FName(*N->AsString()));for(const auto& P:Root->GetArrayField(TEXT("parents")))S.Parents.Add(int(P->AsNumber()));
  S.Base=JsonPoses(Row->GetArrayField(TEXT("base")));S.Clear=JsonPose(Row->GetObjectField(TEXT("clear")));S.Seat=JsonPose(Row->GetObjectField(TEXT("seat")));S.Mouth=JsonVector(Row->GetArrayField(TEXT("mouth")));S.Sheathe=Row->GetBoolField(TEXT("sheathe"));
  auto Find=[&](const TCHAR* N){return S.Names.IndexOfByKey(FName(N));};S.Pelvis=Find(TEXT("pelvis"));S.Clav=Find(TEXT("clavicle_r"));for(int I=0;I<5;++I)S.Spine[I]=Find(*FString::Printf(TEXT("spine_0%d"),I+1));
  const TCHAR* Arm[]={TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};const TCHAR* Neck[]={TEXT("neck_01"),TEXT("neck_02"),TEXT("head")};for(int I=0;I<3;++I){S.Arm[I]=Find(Arm[I]);S.Neck[I]=Find(Neck[I]);}
  S.Groups.Init(-1,S.Names.Num());for(int J=0;J<S.Names.Num();++J){for(int K=J;K>=0;K=S.Parents[K])if(K==S.Spine[0]){S.Upper.Add(J);break;}const FString N=S.Names[J].ToString();if(N.StartsWith(TEXT("spine_")))S.Groups[J]=0;else if(N.StartsWith(TEXT("clavicle_")))S.Groups[J]=1;else if(N.StartsWith(TEXT("upperarm_")))S.Groups[J]=2;else if(N.StartsWith(TEXT("lowerarm_")))S.Groups[J]=3;else if(J==S.Neck[0])S.Groups[J]=4;else if(J==S.Neck[1])S.Groups[J]=5;else if(J==S.Neck[2])S.Groups[J]=6;}
  S.SpineAxis=S.Base[S.Spine[4]].GetRotation().UnrotateVector(S.Base[S.Neck[0]].GetLocation()-S.Base[S.Spine[4]].GetLocation()).GetSafeNormal();const FVector Axis=S.Base[S.Clav].GetRotation().UnrotateVector(S.Base[S.Arm[0]].GetLocation()-S.Base[S.Clav].GetLocation()).GetSafeNormal();S.ClavU=FVector::CrossProduct(Axis,FMath::Abs(Axis.X)<.8?FVector::ForwardVector:FVector::RightVector).GetSafeNormal();S.ClavV=FVector::CrossProduct(Axis,S.ClavU);
  S.Desired=Optimize(S);MaxBody=FMath::Max(MaxBody,(S.Desired-JsonVector(Row->GetArrayField(TEXT("body")))).Size());CaptureArm(S,S.Base,S.SourceArm);Endpoint(S,S.Desired,S.Sheathe?S.Clear:S.Seat,S.SourceArm,S.DestinationArm);
  const auto& Profile=Root->GetObjectField(TEXT("profile"));const double Duration=ArmDuration(S.SourceArm,S.DestinationArm,Profile->GetNumberField(TEXT("maxReachSpeed")),Profile->GetNumberField(TEXT("maxReachRotationSpeed")));DurationError=FMath::Max(DurationError,FMath::Abs(Duration-Row->GetNumberField(TEXT("duration"))));
  S.Head=S.HeadStart=S.Base[S.Neck[2]].GetRotation();S.Status.SlideProgress=0;
  // Measure the actual procedural update over independent active state. Asset
  // loading, NN readers, pose publication and physics are deliberately excluded.
  for(int Count:{1,10,100}){
   TArray<FActive> Crowd;Crowd.Reserve(Count);
   for(int I=0;I<Count;++I){auto& C=Crowd.Add_GetRef(S);C.Pose=C.LastBody=C.LastBase=C.Base;C.Status.ReachTicks=FMath::Max<int32>(1,FMath::CeilToInt(Duration*60));C.SlideLength=FVector::Dist(C.Clear.GetLocation(),C.Seat.GetLocation());C.Status.SlideTicks=FMath::Max<int32>(1,FMath::CeilToInt(C.SlideLength/Profile->GetNumberField(TEXT("slidingSpeed"))*60));}
   double Total=0,Peak=0;int Frames=0;
   for(int Frame=0;Frame<240;++Frame){const double Start=FPlatformTime::Seconds();bool Running=false;for(auto& C:Crowd){if(C.Status.Finished)continue;Running=true;if(C.Status.ReachDone&&!C.Sliding){C.Sliding=true;C.SlideStart=C.Status.Tick;}Advance(C,1);}const double Ms=(FPlatformTime::Seconds()-Start)*1000;if(!Running)break;Total+=Ms;Peak=FMath::Max(Peak,Ms);++Frames;}
   for(const auto& C:Crowd)TestTrue(TEXT("Bench cycle completed"),C.Status.Finished);
   Performance+=FString::Printf(TEXT("%s S%d agents=%d frames=%d mean_ms=%.6f peak_ms=%.6f\n"),*Row->GetStringField(TEXT("motion")),S.Sheathe,Count,Frames,Total/FMath::Max(Frames,1),Peak);
  }
  const auto& Heads=Row->GetArrayField(TEXT("heads"));for(int Tick=1;Tick<Heads.Num();++Tick){S.Status.Tick=Tick;S.Sliding=Tick>=90;S.Status.SlideProgress=S.Sliding?1:0;S.Pose=S.Base;HeadStep(S);MaxHead=FMath::Max(MaxHead,Angle(S.Head,JsonQuat(Heads[Tick]->AsArray())));TestTrue(TEXT("Head speed bound"),S.Status.HeadStep<=(S.HeadOut?S.Profile.HeadOutSpeed:S.Profile.HeadInSpeed)/60+.001);}
  for(const auto& R:Row->GetArrayField(TEXT("returns"))){const auto Ref=R->AsObject();S.Pose=JsonPoses(Row->GetArrayField(TEXT("end")));S.LastBody=JsonPoses(Row->GetArrayField(TEXT("before")));S.LastBase=S.Base;auto& P=S.Profile.Return[S.Sheathe];P.World=Ref->GetBoolField(TEXT("world"));P.Spring=Ref->GetBoolField(TEXT("spring"));P.TwistRemoval=Ref->GetNumberField(TEXT("twist"));S.SpringFrames.Reset();S.SpringTimes.Reset();BeginReturn(S);
   TestTrue(TEXT("FK return duration"),FMath::Abs(S.ReturnDuration-Ref->GetNumberField(TEXT("duration")))<1.e-5);
   double CaseAngle=0,CasePosition=0;FName WorstBone;
   for(const auto& Sample:Ref->GetArrayField(TEXT("samples"))){const auto V=Sample->AsObject();const auto Expected=JsonPoses(V->GetArrayField(TEXT("pose")));S.Pose=S.Base;ReturnStep(S,V->GetNumberField(TEXT("time")));for(int J:S.Upper){const double D=Angle(S.Pose[J].GetRotation(),Expected[J].GetRotation());if(D>CaseAngle){CaseAngle=D;WorstBone=S.Names[J];}CasePosition=FMath::Max(CasePosition,FVector::Distance(S.Pose[J].GetLocation(),Expected[J].GetLocation()));}}
   MaxReturn=FMath::Max(MaxReturn,CaseAngle);MaxPosition=FMath::Max(MaxPosition,CasePosition);
   AddInfo(FString::Printf(TEXT("%s S%d world%d spring%d deg=%.9g cm=%.9g bone=%s"),*Row->GetStringField(TEXT("motion")),S.Sheathe,P.World,P.Spring,CaseAngle,CasePosition,*WorstBone.ToString()));
  }
 }
 TestTrue(TEXT("Curve parity"),CurveError<1.e-10);TestTrue(TEXT("Body fitting parity radians"),MaxBody<1.e-4);TestTrue(TEXT("FK speed-duration parity seconds"),DurationError<.001);TestTrue(TEXT("Head parity degrees"),MaxHead<.03);TestTrue(TEXT("FK return parity degrees"),MaxReturn<.05);TestTrue(TEXT("FK return parity cm"),MaxPosition<.05);
 const FString Result=FString::Printf(TEXT("curve=%.12g body_rad=%.9g duration_seconds=%.9g head_deg=%.9g return_deg=%.9g return_cm=%.9g\n"),CurveError,MaxBody,DurationError,MaxHead,MaxReturn,MaxPosition);AddInfo(Result);FFileHelper::SaveStringToFile(Result,*(Dir/TEXT("native-parity.txt")));FFileHelper::SaveStringToFile(Performance,*(Dir/TEXT("performance.txt")));return !HasAnyErrors();
}
}
#endif
