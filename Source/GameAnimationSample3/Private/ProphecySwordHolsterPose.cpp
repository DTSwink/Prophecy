#include "ProphecySwordHolsterPose.h"
#include "ProphecySwordTipAlignment.h"
#include "ProphecySwordHolsterLibrary.h"
#include "ProphecySwordComponent.h"
#include "DrawDebugHelpers.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyBlendClock.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeRWLock.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "ProphecyFKReturnMath.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNPhysicalTargetPose.h"
#include "ProphecyNNInterpolation.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "ProphecySwordHolsterSchedule.h"
#include "ProphecySwordHolsterSchedule.inl"

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

// A fixed pair needs its shortest arc calculated once, not at every sample.
static void ShortArcSinCos(double X,double& Sin,double& Cos)
{
 // Only [-pi/2,pi/2]. Taylor remainders below 3e-16 on this bounded
 // interval; no general-purpose range reduction in the inner pose loops.
 const double Z=X*X;
 Sin=X*(1+Z*(-1./6+Z*(1./120+Z*(-1./5040+Z*(1./362880+Z*(-1./39916800+Z*(1./6227020800.+Z*(-1./1307674368000.+Z*(1./355687428096000.+Z*(-1./121645100408832000.))))))))));
 Cos=1+Z*(-1./2+Z*(1./24+Z*(-1./720+Z*(1./40320+Z*(-1./3628800+Z*(1./479001600+Z*(-1./87178291200.+Z*(1./20922789888000.+Z*(-1./6402373705728000.+Z*(1./2432902008176640000.))))))))));
}
static FQuat PreparedRotation(FVector Axis,double Radians)
{
 double Sin,Cos;if(FMath::Abs(Radians)<=PI)ShortArcSinCos(Radians*.5,Sin,Cos);else FMath::SinCos(&Sin,&Cos,Radians*.5);
 return FQuat(Axis.X*Sin,Axis.Y*Sin,Axis.Z*Sin,Cos);
}
static FQuat ShortExp(FVector V)
{const double Length=V.Size();return Length<1.e-12?FQuat::Identity:PreparedRotation(V/Length,Length);}
static FQuat QuaternionThird(FQuat Q)
{
 if(Q.W<0)Q=Q*-1.;
 if(Q.W>=.9999)return (FQuat::Identity*(2./3)+Q*(1./3)).GetNormalized();
 // cos(theta/3) solves 4c^3-3c=cos(theta). On the shortest quaternion
 // arc c is in [sqrt(3)/2,1]; four Newton steps reach double precision.
 double C=1-(1-Q.W)/9;
 for(int I=0;I<4;++I)C-=(4*C*C*C-3*C-Q.W)/(12*C*C-3);
 const double Scale=1/(4*C*C-1);return FQuat(Q.X*Scale,Q.Y*Scale,Q.Z*Scale,C).GetNormalized();
}
struct FRotationArc
{
 FQuat A=FQuat::Identity,B=FQuat::Identity,Tangent=FQuat(0,0,0,0);
 double Theta=0;bool Linear=true,Constant=true;
 void Prepare(FQuat From,FQuat To)
 {
  A=From;B=To;double Dot=A|B;if(Dot<0){B=B*-1.;Dot=-Dot;}
  Constant=(A-B).SizeSquared()<1.e-24;Linear=Dot>=.9999;
  if(!Linear){Theta=FMath::Acos(FMath::Clamp(Dot,-1.,1.));Tangent=(B-A*Dot)*(1/FMath::Sin(Theta));}
 }
 FQuat At(double T) const
 {
  if(Constant)return A;
  if(Linear)return (A*(1-T)+B*T).GetNormalized();
  double Sin,Cos;ShortArcSinCos(T*Theta,Sin,Cos);return (A*Cos+Tangent*Sin).GetNormalized();
 }
};
struct FOffsetArc
{
 FVector A=FVector::ZeroVector,B=FVector::ZeroVector,Unit=FVector::ZeroVector;
 FRotationArc Rotation;double LengthA=0,LengthB=0;bool Constant=true,Linear=false;
 void Prepare(FVector From,FVector To)
 {
  A=From;B=To;LengthA=A.Size();LengthB=B.Size();Constant=(A-B).SizeSquared()<1.e-20;Linear=LengthA<1.e-8||LengthB<1.e-8;
  if(!Constant&&!Linear){Unit=A/LengthA;Rotation.Prepare(FQuat::Identity,FQuat::FindBetweenVectors(A,B));}
 }
 FVector At(double T) const{return Constant?A:Linear?FMath::Lerp(A,B,T):Rotation.At(T).RotateVector(Unit)*FMath::Lerp(LengthA,LengthB,T);}
};
struct FPreparedRate
{
 FVector Axis=FVector::ForwardVector;double Speed=0;
 void Prepare(FVector V){Speed=V.Size();if(Speed>1.e-12)Axis=V/Speed;}
 FQuat At(double T) const{return Speed*T<1.e-12?FQuat::Identity:PreparedRotation(Axis,Speed*T);}
};
struct FReturnBone
{
 FRotationArc Rotation;FOffsetArc Offset;FPreparedRate Angular,Translation,World;
 bool OffsetAlongIdle=false;int Child=INDEX_NONE;
};
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
 P.RotationTolerance=Number(J,TEXT("sheatheRotationTolerance"),15,0,90);P.RotationCorrection=Number(J,TEXT("slideRotationCorrection"),.1,0,1);
 P.HeadTargetAlpha=Number(J,TEXT("sheatheHeadTargetAlpha"),1,0,1);P.HeadSpeedAlpha=Number(J,TEXT("headLookInSpeedAlpha"),1,0,1);
 P.HeadInMaxGaze=Number(J,TEXT("maxHeadLookInVelocityAtMaxGaze"),P.HeadInSpeed,.01,10000);P.HeadOutMaxGaze=Number(J,TEXT("maxHeadLookOutVelocityAtMaxGaze"),P.HeadOutSpeed,.01,10000);
 P.HeadMaxTilt=Number(J,TEXT("headMaxDownAngle"),70,0,90);
 P.EntryInertia=Number(J,TEXT("entryInertia"),0,0,1);P.EntryDuration=Number(J,TEXT("entryInertiaDuration"),.2,0,1);
 P.ShrinkDuration=Number(J,TEXT("shrinkDuration"),.25,.01,60);
 P.Stabilization=Number(J,TEXT("holsterRotationStabilization"),0,0,1);P.HolsterReturnDuration=Number(J,TEXT("holsterReturnDuration"),.25,0,10);
 P.TipTolerance=Number(J,TEXT("sheatheTipTolerance"),2,0,100);J->TryGetBoolField(TEXT("leewayPhase"),P.LeewayPhase);
 P.Shrink=Number(J,TEXT("shrinkPercent"),10,0,99.9);P.Unshrink=Number(J,TEXT("unshrinkDuration"),.25,0,10);
 const TCHAR* BodyKeys[]={TEXT("spine"),TEXT("right"),TEXT("left")};
 const TSharedPtr<FJsonObject>* Reference;const bool HasReference=J->TryGetObjectField(TEXT("bodyReference"),Reference);
 if(HasReference)for(int K=0;K<3;++K){const TArray<TSharedPtr<FJsonValue>>* Q;
  if(!(*Reference)->TryGetArrayField(BodyKeys[K],Q)||Q->Num()!=4){Error=TEXT("Invalid authored body reference");return false;}
  P.BodyReference[K]=FQuat((*Q)[0]->AsNumber(),(*Q)[1]->AsNumber(),(*Q)[2]->AsNumber(),(*Q)[3]->AsNumber()).GetNormalized();
 }

 for(int A=0;A<2;++A)
 {
  const FString Prefix=A?TEXT("sheathe"):TEXT("draw");
  auto& B=P.Body[A];TSharedPtr<FJsonObject> Values=J;const TSharedPtr<FJsonObject>* Action;
  if(J->TryGetObjectField(Prefix+TEXT("Body"),Action))Values=*Action;
  B.Speed=Number(Values,TEXT("maxSpineClavicleAngularSpeed"),P.BodySpeed,.01,10000);
  B.Compensation=Number(Values,TEXT("pelvisRotationCompensation"),1,0,1);B.PoleSpeed=Number(Values,TEXT("maxElbowPoleAngularSpeed"),180,0,10000);
  Values->TryGetBoolField(TEXT("swordRelativeSlidePole"),B.SwordPole);
  B.HasSpeeds=HasReference;B.Reach=Number(Values,TEXT("maxReachSpeed"),100,.01,10000);
  B.Rotation=Number(Values,TEXT("maxReachRotationSpeed"),180,.01,10000);B.Sliding=Number(Values,TEXT("slidingSpeed"),60,.01,10000);
  const TSharedPtr<FJsonObject>* Targets;
  if(Values->TryGetObjectField(TEXT("bodyTargets"),Targets)&&HasReference){
   B.Authored=true;
   for(int E=0;E<2;++E){const TSharedPtr<FJsonObject>* Endpoint;
    if(!(*Targets)->TryGetObjectField(E?TEXT("seated"):TEXT("clear"),Endpoint)){Error=TEXT("Missing authored body endpoint");return false;}
    B.Pole[E]=Number(*Endpoint,TEXT("pole"),0,-180,180);
    for(int K=0;K<3;++K){const TArray<TSharedPtr<FJsonValue>>* V;
     if(!(*Endpoint)->TryGetArrayField(BodyKeys[K],V)||V->Num()!=3){Error=TEXT("Invalid authored body angles");return false;}
     const FQuat X(FVector::ForwardVector,FMath::DegreesToRadians((*V)[0]->AsNumber())),Y(FVector::RightVector,FMath::DegreesToRadians((*V)[1]->AsNumber())),Z(FVector::UpVector,FMath::DegreesToRadians((*V)[2]->AsNumber()));
     B.Targets[E][K]=(Z*Y*X*P.BodyReference[K]).GetNormalized();
    }
   }
  }

  for(int Phase=0;Phase<2;++Phase)
  {
   auto& C=Phase?P.Slide[A]:P.Reach[A];const TArray<TSharedPtr<FJsonValue>>* CurveValues;
   if(J->TryGetArrayField(Prefix+(Phase?TEXT("SlideCurve"):TEXT("Curve")),CurveValues)&&CurveValues->Num()==4)
    for(int I=0;I<4;++I){const TArray<TSharedPtr<FJsonValue>>* Pair;if(!(*CurveValues)[I]->TryGetArray(Pair)||Pair->Num()!=2){Error=TEXT("Invalid curve point");return false;}
     C.Points[I+1]={FMath::Clamp((*Pair)[0]->AsNumber(),C.Points[I].X+.01,1-(4-I)*.01),FMath::Clamp((*Pair)[1]->AsNumber(),C.Points[I].Y,1.)};}
   C.Prepare();
  }
  if(J->TryGetObjectField(Prefix+TEXT("Return"),Nested))
  {
   const auto& V=*Nested;auto& R=P.Return[A];V->TryGetBoolField(TEXT("enabled"),R.Enabled);V->TryGetBoolField(TEXT("worldInertia"),R.World);V->TryGetBoolField(TEXT("springReturn"),R.Spring);
   R.StartFraction=Number(V,TEXT("startFraction"),.9,0,1);R.Duration=Number(V,TEXT("duration"),1,.1,5);R.Easing=Number(V,TEXT("returnEasing"),1,0,1);R.Inertia=Number(V,TEXT("inertia"),1,0,1);R.Hold=Number(V,TEXT("inertiaHold"),0,0,.8);R.Decay=Number(V,TEXT("inertiaDecay"),1,0,4);R.AngleTime=Number(V,TEXT("angleTimeSeconds"),.29,0,4);R.TwistRemoval=Number(V,TEXT("upperArmTwistRemoval"),0,0,1);
   const TSharedPtr<FJsonObject>* Weights;if(V->TryGetObjectField(TEXT("boneInertia"),Weights))
   {const TCHAR* Keys[]={TEXT("spine"),TEXT("clavicle"),TEXT("upperarm"),TEXT("lowerarm"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("hand")};for(int I=0;I<8;++I)R.Weights[I]=Number(*Weights,Keys[I],1,0,1);}
  }
 }
 P.AttachedSpeed=Number(J,TEXT("maxAttachedSpeed"),P.Body[1].Reach,.01,10000);
 P.AttachedRotation=Number(J,TEXT("maxAttachedRotationSpeed"),P.Body[1].Rotation,.01,10000);
 return true;
}
struct FReturnTrack
{
 TArray<FTransform> ReturnStart,ReturnIdle;
 TArray<FVector> Velocity,OffsetVelocity,WorldVelocity,WorldCorrection;
 TArray<FQuat> ReturnWorld,ReturnBaselineWorld,ReturnActualWorld;
 TArray<FReturnBone> PreparedReturn;
 TArray<TArray<FTransform>> SpringFrames;TArray<double> SpringTimes;
 TArray<FVector> SpringRates,SpringOffsetRates,SpringParentRates;TArray<FQuat> SpringWorld,SpringPreviousWorld;int32 SpringStep=0,SpringCount=0;
 double ReturnDuration=1;bool OnlyGrip=false;
};
struct FAuthoredState
{
 int Left=INDEX_NONE;TArray<FTransform> Local;TArray<uint8> Driven;TArray<int32> InertiaBones;
 FQuat Frame=FQuat::Identity,Pelvis=FQuat::Identity,Spine[5],Entry[3],Current[3],Destination[3];
 FVector PoleDirection=FVector::ForwardVector,PoleZero=FVector::RightVector,SwordDown=FVector::RightVector;
 bool PoleValid=false,UseSword=false;double PoleAngle=0,PoleReachSpeed=0,EntryTime=0;
 TArray<FVector> EntryAngular,EntryOffset;
};
struct FActive : FReturnTrack
{
 FAuthoredState Authored;FProfile Profile;FStatus Status;int32 PoseId=INDEX_NONE,Pelvis=0,Spine[5],Clav,Arm[3],Neck[3];
 TArray<FName> Names;TArray<int32> Parents,Upper,Groups,GripUpper;
 TArray<FTransform> Base,Pose,Before,Entry,LastBase,LastBody,Work,HeadWork,Future,SlidePose;
 TArray<FName> ReadNames;FProphecyNNPoseSnapshot Snapshot;
 FTransform Clear,Seat;FVector Mouth,SpineAxis,ClavU,ClavV,Body=FVector::ZeroVector,Desired=FVector::ZeroVector;
 FTransform SourceArm[3],DestinationArm[3],SlideA[3],SlideB[3],HeldArm[3];
 FQuat Head=FQuat::Identity,HeadStart=FQuat::Identity;bool Sheathe=true,Sliding=false,HeadOut=false,HeadDone=false,Initialized=false;
 // Retained legacy cap fields remain used by the development benchmark oracle.
 double HeadCapSpeed=-1,HeadCapSin=0,HeadCapCos=1;
 FQuat HeadReference=FQuat::Identity,NeutralHead=FQuat::Identity;
 FVector HeadDelta=FVector::ZeroVector,HeadFrom=FVector::ZeroVector,HeadTargetDelta=FVector::ZeroVector,HeadAim=FVector::ZeroVector;
 FVector HeadBaseDelta=FVector::ZeroVector,NeckParentDelta=FVector::ZeroVector;
 bool HeadInitialized=false,HeadTargetValid=false,HeadAimValid=false;
 double Gaze=0,StartGaze=0;FVector2D GazeInput=FVector2D::ZeroVector;
 FProphecySwordTipAlignment TipAlignment;FQuat SlideBody[3];
 FTransform NeutralMount;FQuat StableHolster=FQuat::Identity;bool Stabilizing=false,OriginalAbsoluteRotation=false;
 FGeometry Geometry;FTransform Full,HolsterFrame;FQuat EntryRotation=FQuat::Identity;FVector EntryTipError=FVector::ZeroVector;
 double EntryScale=1,EntryInsertion=0,Scale=1,GuideA=0,GuideB=0;
 FReturnTrack ArmReturn;bool ArmReturning=false;int ReturnTick=-1;double BodyElapsed=0;
 int32 SlideStart=-1,HeadStartTick=0,LastGuide=-1;double ReachSpeed=100,RotationSpeed=180,SlideSpeed=60,SlideLength=1,HeadDuration=-1;
};
struct FCached {TMap<FName,FTransform> Bones;};
// Physical target lists follow PHAT body order, not skeleton order (head can
// precede neck_02). Build traversal indices without reordering the source pose.
using FBoneOrder=TArray<int32,TInlineAllocator<32>>;
static bool HierarchyOrder(TConstArrayView<int32> Parents,FBoneOrder& Order)
{
 Order.Reset();TArray<uint8,TInlineAllocator<32>> State;State.Init(0,Parents.Num());FBoneOrder Path;
 for(int J=0;J<Parents.Num();++J){Path.Reset();int P=J;
  while(P!=INDEX_NONE){
   if(!Parents.IsValidIndex(P)||State[P]==1)return false;
   if(State[P]==2)break;
   State[P]=1;Path.Add(P);P=Parents[P];
  }
  for(int K=Path.Num()-1;K>=0;--K){State[Path[K]]=2;Order.Add(Path[K]);}
 }
 return true;
}
static bool PrepareUpperOrder(FActive& S)
{
 FBoneOrder Order;if(!HierarchyOrder(S.Parents,Order))return false;
 S.Upper.Reset();
 for(int J:Order)for(int P=J;P>=0;P=S.Parents[P])if(P==S.Spine[0]){S.Upper.Add(J);break;}
 S.GripUpper.Reset();for(int J:Order)for(int P=J;P>=0;P=S.Parents[P])if(P==S.Clav){S.GripUpper.Add(J);break;}
 return true;
}
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
bool ActionSpeeds(const AProphecyAgent* A,bool Sheathe,float& Reach,float& Rotation,float& Slide)
{
 const auto* P=Profiles.Find(A);if(!P||!P->Body[Sheathe].HasSpeeds)return false;
 const auto& B=P->Body[Sheathe];Reach=B.Reach;Rotation=B.Rotation;Slide=B.Sliding;return true;
}
static void RestoreHolsterMount(FActive& S,bool PreserveSword=false)
{
 if(!S.Stabilizing)return;
 if(auto* H=S.Geometry.Holster.Get()){
  // Cancelling a gripped action must restore the mount without carrying a
  // released/dropped sword through that restoration. Normal return follows it.
  USceneComponent* Blade=nullptr;FTransform SwordWorld;
  if(PreserveSword)if(const auto* A=Cast<AProphecyAgent>(H->GetOwner()))if(const auto* C=A->FindComponentByClass<UProphecySwordComponent>())
   if(auto* Sword=C->GetSword())if(auto* Root=Sword->GetRootComponent();Root&&Root->GetAttachParent()==H){Blade=Root;SwordWorld=Root->GetComponentTransform();}
  H->SetUsingAbsoluteRotation(S.OriginalAbsoluteRotation);H->SetRelativeLocationAndRotation(S.NeutralMount.GetLocation(),S.NeutralMount.GetRotation());
  if(Blade)Blade->SetWorldTransform(SwordWorld,false,nullptr,ETeleportType::TeleportPhysics);
 }
 S.Stabilizing=false;
}
void RestoreHolsterMount(const AProphecyAgent* A){if(auto* P=Active.Find(A))RestoreHolsterMount(**P,true);}
static double HolsterWeight(const FActive& S)
{
 if(!S.Stabilizing)return 0;
 const double ReturnTicks=FMath::CeilToDouble(S.Geometry.HolsterReturnDuration*60-1.e-5);
 const int Release=S.SlideStart+S.Status.SlideTicks;
 const double Remaining=!S.Sliding||S.Status.Tick<=Release?1:ReturnTicks>0?1-Clamp(double(S.Status.Tick-Release)/ReturnTicks):0;
 return S.Geometry.GripStabilization*Remaining;
}
static FTransform MountedHolster(const FActive& S,const FTransform& Parent)
{
 FTransform T=S.NeutralMount*Parent;
 T.SetRotation(FQuat::Slerp(T.GetRotation(),S.StableHolster,HolsterWeight(S)).GetNormalized());
 return T;
}
static void BeginHolsterGrip(FActive& S)
{
 if(S.Stabilizing||S.Geometry.GripStabilization<=0)return;
 if(auto* H=S.Geometry.Holster.Get()){
  S.NeutralMount=H->GetRelativeTransform();S.OriginalAbsoluteRotation=H->IsUsingAbsoluteRotation();
  S.StableHolster=H->GetComponentQuat();S.Stabilizing=true;
  H->SetUsingAbsoluteRotation(true);H->SetWorldRotation(S.StableHolster);
 }
}
void UpdateHolsterMount(const AProphecyAgent* A)
{
 auto* P=Active.Find(A);if(!P)return;auto& S=**P;if(!S.Stabilizing)return;
 if(HolsterWeight(S)<=0){RestoreHolsterMount(S);return;}
 if(auto* H=S.Geometry.Holster.Get())if(auto* Parent=H->GetAttachParent())
  {const FTransform Mount=MountedHolster(S,Parent->GetSocketTransform(H->GetAttachSocketName()));
   H->SetWorldLocationAndRotation(Mount.GetLocation(),Mount.GetRotation());}
}
void Remove(const AProphecyAgent* A,bool ClearProfile)
{
 if(auto* S=Active.Find(A)){RestoreHolsterMount(**S,true);FWriteScopeLock Lock(OutputLock);Outputs.Remove((*S)->PoseId);AnyOutput.Store(!Outputs.IsEmpty());}
 Active.Remove(A);ProphecyBlendClock::Stop(A,ProphecyBlendClock::EKind::SwordHolster);
 ProphecySwordHolsterSchedule::Remove(A);
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
#include "ProphecySwordHolsterAuthored.inl"
static void BodyPose(const FActive& S,TConstArrayView<FTransform> Base,FVector V,TArray<FTransform>& Out,bool ShoulderOnly=false,const FQuat* Authored=nullptr)
{
 if(S.Profile.Body[S.Sheathe].Authored){AuthoredBodyPose(S,Base,Authored?Authored:S.Authored.Current,Out);return;}

 Out.SetNum(Base.Num());if(ShoulderOnly)Out[S.Pelvis]=Base[S.Pelvis];else for(int I=0;I<Base.Num();++I)Out[I]=Base[I];const FQuat Top=Base[S.Spine[4]].GetRotation();const FVector WorldAxis=Top.RotateVector(S.SpineAxis);const FQuat Swing=Exp(S.ClavU*V.Y+S.ClavV*V.Z);
 auto Bone=[&](int J){const int P=S.Parents[J];const FQuat Carry=(Out[P].GetRotation()*Base[P].GetRotation().Inverse()).GetNormalized();FQuat Q=(Carry*Base[J].GetRotation()).GetNormalized();
  for(int K=0;K<5;++K)if(J==S.Spine[K])Q=(PreparedRotation(WorldAxis,V.X*(K+1)/5.)*Base[J].GetRotation()).GetNormalized();
  if(J==S.Clav)Q=(Q*Swing).GetNormalized();Out[J]=FTransform(Q,Out[P].GetLocation()+Carry.RotateVector(Base[J].GetLocation()-Base[P].GetLocation()));};
 if(ShoulderOnly){for(int J:S.Spine)Bone(J);Bone(S.Clav);Bone(S.Arm[0]);}else for(int J:S.Upper)Bone(J);
}
static FVector Bounded(FVector V,double Limit)
{V.X=FMath::Clamp(V.X,-Limit,Limit);const double L=FMath::Sqrt(V.Y*V.Y+V.Z*V.Z);if(L>Limit){V.Y*=Limit/L;V.Z*=Limit/L;}return V;}
static FVector Optimize(FActive& S)
{
 const double Limit=FMath::DegreesToRadians(S.Profile.AngleLimit);

 // Only the shoulder position enters the objective. All unchanging geometry
 // is factored out of the candidate loop; no pose arrays or bone rotations.
 bool Chain=S.Parents[S.Spine[0]]==S.Pelvis&&S.Parents[S.Clav]==S.Spine[4]&&S.Parents[S.Arm[0]]==S.Clav;
 for(int K=1;K<5;++K)Chain&=S.Parents[S.Spine[K]]==S.Spine[K-1];
 const FVector Axis=S.Base[S.Spine[4]].GetRotation().RotateVector(S.SpineAxis),Origin=S.Base[S.Spine[0]].GetLocation();
 FVector Links[5];for(int K=0;K<4;++K)Links[K]=S.Base[S.Spine[K+1]].GetLocation()-S.Base[S.Spine[K]].GetLocation();
 Links[4]=S.Base[S.Clav].GetLocation()-S.Base[S.Spine[4]].GetLocation();
 const FQuat ClavRotation=S.Base[S.Clav].GetRotation();const FVector ShoulderLocal=ClavRotation.UnrotateVector(S.Base[S.Arm[0]].GetLocation()-S.Base[S.Clav].GetLocation());
 double LastTwist=DBL_MAX,LastSwingY=DBL_MAX,LastSwingZ=DBL_MAX;FVector TargetLocal,ShoulderOffset;TArray<FTransform> Scratch;
 auto Score=[&](FVector V){
  if(!Chain){BodyPose(S,S.Base,V,Scratch,true);return FVector::DistSquared(Scratch[S.Arm[0]].GetLocation(),S.Clear.GetLocation());}
  if(V.X!=LastTwist){
   const FQuat Q1=PreparedRotation(Axis,V.X/5),Q2=Q1*Q1,Q3=Q2*Q1,Q4=Q2*Q2,Twist=Q4*Q1;
   const FVector ClavPosition=Origin+Q1.RotateVector(Links[0])+Q2.RotateVector(Links[1])+Q3.RotateVector(Links[2])+Q4.RotateVector(Links[3])+Twist.RotateVector(Links[4]);
   TargetLocal=ClavRotation.UnrotateVector(Twist.UnrotateVector(S.Clear.GetLocation()-ClavPosition));LastTwist=V.X;
  }
  if(V.Y!=LastSwingY||V.Z!=LastSwingZ){ShoulderOffset=ShortExp(S.ClavU*V.Y+S.ClavV*V.Z).RotateVector(ShoulderLocal);LastSwingY=V.Y;LastSwingZ=V.Z;}
  return FVector::DistSquared(ShoulderOffset,TargetLocal);
 };
 auto LimitSwing=[&](FVector V){const double Twist=V.X;V=Bounded(V,Limit);V.X=Twist;return V;};
 FVector Best=LimitSwing(S.Desired);double Cost=Score(Best);if(Score(FVector::ZeroVector)<Cost){Best=FVector::ZeroVector;Cost=Score(Best);}
 for(double Degrees:{16.,8.,4.,2.,1.,.5,.125,.03125})for(int Sweep=0;Sweep<4;++Sweep){bool Improved=false;
  for(int K=0;K<3;++K)for(double Sign:{-1.,1.}){FVector V=Best;V[K]+=Sign*FMath::DegreesToRadians(Degrees);V=LimitSwing(V);if(V==Best)continue;const double C=Score(V);if(C<Cost-1.e-9){Best=V;Cost=C;Improved=true;}}
  if(!Improved)break;
 }return Best;
}
static void CaptureArm(const FActive& S,TConstArrayView<FTransform> Pose,FTransform (&Out)[3])
{for(int K=0;K<3;++K)Out[K]=Pose[S.Arm[K]].GetRelativeTransform(Pose[S.Parents[S.Arm[K]]]);}
static void ApplyArm(const FActive& S,TArray<FTransform>& Pose,const FTransform (&Local)[3])
{
 for(int K=0;K<3;++K){const int J=S.Arm[K],P=S.Parents[J];const FVector Original=Pose[J].GetLocation();FTransform L=Local[K];
  if(K>0)L.SetTranslation(L.GetLocation().GetSafeNormal()*(S.Profile.Body[S.Sheathe].Authored?S.Authored.Local[J].GetLocation().Size():FVector::Distance(S.Base[J].GetLocation(),S.Base[P].GetLocation())));
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
static void PreserveArmRoll(FActive& S,const FTransform (&Before)[3])
{
 // Pole placement determines the elbow, not an extra axial rotation. Near
 // full extension that rotation is undefined and can inject a half-turn.
 for(int K=0;K<2;++K){const FVector From=Before[K+1].GetLocation()-Before[K].GetLocation(),To=S.Pose[S.Arm[K+1]].GetLocation()-S.Pose[S.Arm[K]].GetLocation();
  S.Pose[S.Arm[K]].SetRotation((FQuat::FindBetweenVectors(From,To)*Before[K].GetRotation()).GetNormalized());}
}
static double ArmDuration(const FTransform (&A)[3],const FTransform (&B)[3],double Linear,double Angular)
{
 FRotationArc Rotation[3];FOffsetArc Translation[2];double Seconds=1./60.;
 for(int J=0;J<3;++J){Rotation[J].Prepare(A[J].GetRotation(),B[J].GetRotation());if(J)Translation[J-1].Prepare(A[J].GetLocation(),B[J].GetLocation());
  // Linear source progress; normalized-linear near-equal quaternions peak
  // at the centre interval. Keep the same 96-sample budget as the lab.
  Seconds=FMath::Max(Seconds,Angle(Rotation[J].At(47./96),Rotation[J].At(.5))*96/Angular);
 }
 FTransform Initial=A[0];Initial.SetTranslation(FVector::ZeroVector);Initial=A[1]*Initial;Initial=A[2]*Initial;
 FQuat LastHand=Initial.GetRotation();FVector LastPosition=Initial.GetLocation();
 for(int I=1;I<=96;++I){const double T=I/96.;FQuat Q[3];
  for(int J=0;J<3;++J)Q[J]=Rotation[J].At(T);
  const FQuat Forearm=Q[0]*Q[1],Hand=Forearm*Q[2];const FVector Position=Q[0].RotateVector(Translation[0].At(T))+Forearm.RotateVector(Translation[1].At(T));
  Seconds=FMath::Max3(Seconds,FVector::Distance(Position,LastPosition)*96/Linear,Angle(LastHand,Hand)*96/Angular);LastPosition=Position;LastHand=Hand;
 }return Seconds*1.002;
}
static FTransform Goal(const FActive& S,double Progress)
{return FTransform(S.Seat.GetRotation(),FMath::Lerp(S.Clear.GetLocation(),S.Seat.GetLocation(),S.Sheathe?Progress:1-Progress));}
static double Correction(double Progress,double Fraction)
{return Fraction>0?Clamp(Progress/Fraction):Progress>0?1:0;}
static FTransform GripAt(const FActive& S,double Scale)
{
 FTransform G=S.Geometry.Grip;const FQuat Q=G.GetRotation();
 G.SetTranslation(Q.RotateVector(Q.UnrotateVector(G.GetLocation())*FVector(1,1,Scale)));G.SetScale3D(S.Geometry.AssetScale*FVector(1,1,Scale));return G;
}
static FTransform HandAtTip(const FActive& S,double Scale,FVector Tip,FQuat Rotation)
{
 const FTransform G=GripAt(S,Scale);const FQuat Q=(Rotation*G.GetRotation().Inverse()).GetNormalized();
 return FTransform(Q,Tip-Rotation.RotateVector(G.GetScale3D()*S.Geometry.TipLocal)-Q.RotateVector(G.GetLocation()));
}
static FTransform AlignmentGoal(const FActive& S)
{
 FVector Tip;FQuat Rotation;S.TipAlignment.Sample(S.HolsterFrame,S.Status.Tick,Tip,Rotation);
 return HandAtTip(S,S.TipAlignment.Scale,Tip,Rotation);
}
static void CaptureGrip(FActive& S,const FTransform& Blade,const FTransform& Hand,double Scale)
{
 // Store the actual grip in the same unshrunk convention used by GripAt.
 S.Geometry.Grip=Blade.GetRelativeTransform(Hand);const FQuat Q=S.Geometry.Grip.GetRotation();
 S.Geometry.Grip.SetTranslation(Q.RotateVector(Q.UnrotateVector(S.Geometry.Grip.GetLocation())/FVector(1,1,Scale)));
}
static void RefreshGeometry(FActive& S,bool ForPose=true)
{
 if(!S.Geometry.Valid)return;
 if(auto* H=S.Geometry.Holster.Get()){
  FTransform Holster=H->GetComponentTransform();
  // Author for the upcoming physics step, not the completed one. A simulated
  // holster has its own velocity; transporting it with the NN pelvis erases
  // lag or mispredicts its rotation during a turn. Read its native state once.
  if(ForPose){bool Predicted=false;
   // Keep the exact local mount. Sim follows its physical parent, predicted one
   // step from native velocity; substituting the NN pelvis displaces equipment
   // from the real holster. Kinematic mode uses the authored pelvis directly.
   if(H->GetAttachSocketName()==TEXT("pelvis"))if(const auto* A=Cast<AProphecyAgent>(H->GetOwner());A&&H->GetAttachParent()==A->GetPoseReferenceMesh()){
    FTransform Parent=S.Base[S.Pelvis];
    if(A->IsJoltPhysicalAnimationEnabled()){
     Parent=A->GetPoseReferenceMesh()->GetSocketTransform(TEXT("pelvis"));
     auto* World=A->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();const auto* Character=A->GetJoltCharacterComponent();
     FProphecyJoltBodyHandle Handle;FProphecyJoltBodyState State;
     if(World&&Character&&Character->GetBodyHandle(TEXT("pelvis"),Handle)&&World->ReadBody(Handle,State).IsSuccess()){
      const FQuat Turn=Exp(State.AngularVelocityRadiansPerSecond/60.);
      Parent.SetLocation(State.CenterOfMassPositionCm+State.CenterOfMassVelocityCmPerSecond/60.+Turn.RotateVector(Parent.GetLocation()-State.CenterOfMassPositionCm));
      Parent.SetRotation((Turn*Parent.GetRotation()).GetNormalized());
     }
    }
    Holster=S.Stabilizing?MountedHolster(S,Parent):H->GetRelativeTransform()*Parent;Predicted=true;
   }
   if(const auto* A=Cast<AProphecyAgent>(H->GetOwner());!Predicted&&A&&A->IsJoltPhysicalAnimationEnabled()){
    TInlineComponentArray<UProphecyJoltBodyComponent*> Bodies(A);
    for(const auto* B:Bodies)if(B->GetSourceComponent()==H){FProphecyJoltBodyState State;
     if(B->GetBodyState(State)){
      const FQuat Turn=Exp(State.AngularVelocityRadiansPerSecond/60.);
      Holster.SetLocation(State.CenterOfMassPositionCm+State.CenterOfMassVelocityCmPerSecond/60.+Turn.RotateVector(Holster.GetLocation()-State.CenterOfMassPositionCm));
      Holster.SetRotation((Turn*Holster.GetRotation()).GetNormalized());Predicted=true;
     }break;
    }
   }
   if(!Predicted&&S.LastBase.IsValidIndex(S.Pelvis))Holster=Holster.GetRelativeTransform(S.LastBase[S.Pelvis])*S.Base[S.Pelvis];
  }
  S.HolsterFrame=Holster;S.Full=S.Geometry.Seated*Holster;
 }
 S.Mouth=S.Full.TransformPosition(S.Geometry.BaseLocal);
 const double Scale=S.Geometry.Retained;const FTransform G=GripAt(S,Scale);
 const FQuat Q=(S.Full.GetRotation()*G.GetRotation().Inverse()).GetNormalized();
 S.Seat=FTransform(Q,S.Mouth-S.Full.GetRotation().RotateVector(G.GetScale3D()*S.Geometry.BaseLocal)-Q.RotateVector(G.GetLocation()));
 S.Clear=S.Sheathe?HandAtTip(S,Scale,S.Mouth,S.Full.GetRotation()):FTransform(Q,S.Seat.GetLocation()-S.Full.GetRotation().GetAxisZ()*S.SlideLength);
}
static double ReachScale(const FActive& S)
{return S.Geometry.ShrinkDuration<=0?S.Geometry.Retained:1-(1-S.Geometry.Retained)*Clamp(S.Status.Tick/(60*S.Geometry.ShrinkDuration));}
static double Insertion(const FActive& S,double Progress)
{return S.Sheathe?FMath::Lerp(S.EntryInsertion,1.,Progress):1-Progress;}
static double SlideScale(const FActive& S,double Progress)
{return S.Geometry.Valid?FMath::Lerp(S.EntryScale,S.Geometry.Retained,Correction(Progress,S.Profile.RotationCorrection)):1;}
static FTransform SlideGoal(const FActive& S,double Progress,double Time)
{
 if(!S.Sheathe||!S.Geometry.Valid)return Goal(S,Progress);
 const double Scale=SlideScale(S,Progress);const FTransform G=GripAt(S,Scale);
 const FVector SeatedTip=S.Mouth+S.Full.GetRotation().RotateVector(G.GetScale3D()*(S.Geometry.TipLocal-S.Geometry.BaseLocal));
 const FQuat Q=(S.Full.GetRotation()*FQuat::Slerp(S.EntryRotation,FQuat::Identity,Correction(Time,S.Profile.RotationCorrection))).GetNormalized();
 const FVector Tip=FMath::Lerp(S.Mouth,SeatedTip,Insertion(S,Progress))+S.Full.GetRotation().RotateVector(S.EntryTipError)*(1-Correction(Progress,S.Profile.RotationCorrection));
 return HandAtTip(S,Scale,Tip,Q);
}
static FVector ContinuousLog(FQuat Q,const FVector* Reference=nullptr)
{
 const FVector V=Log(Q);const double A=V.Size();if(!Reference)return V;
 const FVector Axis=A>1.e-8?V/A:Reference->Size()>1.e-8?Reference->GetSafeNormal():FVector::ForwardVector;
 return Axis*(A+2*PI*FMath::FloorToDouble((FVector::DotProduct(*Reference,Axis)-A)/(2*PI)+.5));
}
static void NeutralFacing(FActive& S)
{
 // Inverse of the trained local-X yaw overlay. Keep the live NN's local detail.
 const double Yaw=FMath::DegreesToRadians(S.GazeInput.X*170);
 FQuat Parent=S.Base[S.Parents[S.Spine[0]]].GetRotation();
 for(int K=0;K<8;++K){const int J=K<5?S.Spine[K]:S.Neck[K-5],P=S.Parents[J];
  FQuat Local=(S.Base[P].GetRotation().Inverse()*S.Base[J].GetRotation()).GetNormalized();
  if(K>=5&&S.GazeInput.Y!=0){const double Weight=K==7?.4:.6*K/13.;Local=Local*FQuat(FVector::UpVector,FMath::DegreesToRadians(85*S.GazeInput.Y*Weight));}
  Parent=(Parent*Local*FQuat(FVector::ForwardVector,-Yaw*(K+1)/36.)).GetNormalized();
 }
 S.NeutralHead=Parent;
}
static void NeutralNeck(FActive& S,FTransform (&Out)[3])
{
 S.NeckParentDelta=ContinuousLog(S.Pose[S.Spine[4]].GetRotation()*S.Base[S.Spine[4]].GetRotation().Inverse(),&S.NeckParentDelta);
 const FQuat Third=Exp(S.NeckParentDelta/3.);
 FTransform Parent=S.Pose[S.Spine[4]];
 for(int K=0;K<3;++K){const int J=S.Neck[K],P=S.Parents[J];const FQuat D=(Parent.GetRotation()*S.Base[P].GetRotation().Inverse()).GetNormalized();
  Out[K]=FTransform(((K==0?Third*Third:K==1?Third:FQuat::Identity)*S.Base[J].GetRotation()).GetNormalized(),Parent.GetLocation()+D.RotateVector(S.Base[J].GetLocation()-S.Base[P].GetLocation()).GetSafeNormal()*FVector::Distance(S.Pose[J].GetLocation(),S.Pose[P].GetLocation()));Parent=Out[K];
 }
}
static void HeadFactors(const FActive& S,const FQuat& BaseThird,FQuat& Third,FQuat& Two)
{
 // Separate signed head/base factors cancel exactly throughout the neck.
 const FQuat HeadThird=Exp(S.HeadDelta/3.);
 Third=HeadThird*BaseThird;Two=(HeadThird*HeadThird)*(BaseThird*BaseThird);
}
static FQuat LimitHeadTilt(const FActive& S,FQuat Q)
{
 if(S.Profile.HeadMaxTilt>=90)return Q;
 const FVector Up=S.Pose[S.Spine[4]].GetRotation().GetAxisX(),HeadUp=Q.GetAxisX();
 const double Vertical=FVector::DotProduct(HeadUp,Up),Limit=FMath::DegreesToRadians(S.Profile.HeadMaxTilt);
 if(Vertical>=FMath::Cos(Limit))return Q;
 FVector Horizontal=HeadUp-Up*Vertical;
 if(Horizontal.Size()<1.e-8){const FVector Forward=Q.GetAxisY();Horizontal=Forward-Up*FVector::DotProduct(Forward,Up);}
 const FVector Target=Horizontal.GetSafeNormal()*FMath::Sin(Limit)+Up*FMath::Cos(Limit);
 return (FQuat::FindBetweenVectors(HeadUp,Target)*Q).GetNormalized();
}
static void HeadStep(FActive& S)
{
 NeutralFacing(S);FTransform Neck[3];NeutralNeck(S,Neck);
 if(!S.HeadInitialized){S.HeadReference=S.NeutralHead;S.HeadDelta=Log(S.Head*S.HeadReference.Inverse());S.HeadBaseDelta=S.HeadDelta;S.HeadFrom=S.HeadDelta;S.HeadInitialized=true;}
 S.HeadBaseDelta=ContinuousLog(S.Base[S.Neck[2]].GetRotation()*S.HeadReference.Inverse(),&S.HeadBaseDelta);
 const FQuat BaseThird=Exp(-S.HeadBaseDelta/3.);
 const bool Out=S.Sliding&&(S.Sheathe?S.Status.Insertion:S.Status.SlideProgress)>=(S.Sheathe?S.Profile.SheatheHeadOut:S.Profile.DrawHeadOut)-1.e-8;
 if(Out!=S.HeadOut){S.HeadOut=Out;S.HeadFrom=S.HeadDelta;S.HeadStartTick=S.Status.Tick-1;S.HeadDuration=-1;S.HeadTargetValid=S.HeadAimValid=false;}
 const double Speed=Out?FMath::Lerp(S.Profile.HeadOutSpeed,S.Profile.HeadOutMaxGaze,Clamp(S.Gaze)):FMath::Lerp(S.Profile.HeadInSpeed,S.Profile.HeadInMaxGaze,Clamp(S.StartGaze));
 const double Exponent=Out?S.Profile.HeadOutExponent:S.Profile.HeadInExponent,Cap=FMath::DegreesToRadians(Speed)/60;
 const FQuat Previous=S.Head,Forward=Out?S.Base[S.Neck[2]].GetRotation():S.NeutralHead;const FVector PreviousDelta=S.HeadDelta;
 FVector TargetPosition=S.Mouth;
 if(S.Sheathe&&S.Geometry.Valid&&S.Profile.HeadTargetAlpha<1){
  const double U=S.Sliding?Clamp(double(S.Status.Tick-S.SlideStart)/S.Status.SlideTicks):0;
  const double Scale=S.Status.Aligning?S.TipAlignment.Scale:S.Sliding?SlideScale(S,S.Status.SlideProgress):ReachScale(S);
  const FTransform Sword=GripAt(S,Scale)*(S.Status.Aligning?AlignmentGoal(S):S.Sliding?SlideGoal(S,S.Status.SlideProgress,U):S.Pose[S.Arm[2]]);
  TargetPosition=FMath::Lerp(Sword.TransformPosition(S.Geometry.TipLocal),S.Mouth,S.Profile.HeadTargetAlpha);
 }
 FQuat Desired=Forward;
 for(int I=0;I<(Out?1:8);++I){
  Desired=Forward;
  if(!Out){FQuat Third,Two;HeadFactors(S,BaseThird,Third,Two);const FVector Position=Neck[0].GetLocation()+Third.RotateVector(Neck[1].GetLocation()-Neck[0].GetLocation())+Two.RotateVector(Neck[2].GetLocation()-Neck[1].GetLocation()),Direction=TargetPosition-Position;
   if(!Direction.IsNearlyZero()){S.HeadAim=ContinuousLog(FQuat::FindBetweenVectors(Forward.GetAxisY(),Direction),S.HeadAimValid?&S.HeadAim:nullptr);S.HeadAimValid=true;Desired=(Exp(S.HeadAim*S.Profile.HeadAlpha)*Forward).GetNormalized();}
  }
  Desired=LimitHeadTilt(S,Desired);
  S.HeadTargetDelta=ContinuousLog(Desired*S.HeadReference.Inverse(),S.HeadTargetValid?&S.HeadTargetDelta:Out?&S.HeadBaseDelta:nullptr);S.HeadTargetValid=true;
  FVector Wanted=S.HeadTargetDelta;const bool WithHand=!Out&&S.Profile.HeadSpeedAlpha<1;
  if(Exponent>1||WithHand){if(S.HeadDuration<0){const double Fast=FMath::Max(1.,Exponent*FMath::RadiansToDegrees((Wanted-S.HeadFrom).Size())/Speed*60);S.HeadDuration=WithHand?FMath::Lerp(Fast,FMath::Max(Fast,double(S.Status.ReachTicks)),1-S.Profile.HeadSpeedAlpha):Fast;}
   const double U=Clamp((S.Status.Tick-S.HeadStartTick)/S.HeadDuration),X=FMath::Pow(U,Exponent),Y=FMath::Pow(1-U,Exponent);Wanted=FMath::Lerp(S.HeadFrom,Wanted,X/(X+Y));}
  const FVector Change=Wanted-PreviousDelta;S.HeadDelta=PreviousDelta+Change.GetClampedToMaxSize(Cap);const FQuat Last=S.Head;S.Head=(Exp(S.HeadDelta)*S.HeadReference).GetNormalized();
  const FQuat Limited=LimitHeadTilt(S,S.Head);
  if(Limited!=S.Head){
   S.Head=Limited;
   if(Angle(Previous,S.Head)>Speed/60+1.e-8){
    FQuat Best=LimitHeadTilt(S,Previous);double Lo=0,Hi=1;
    if(Angle(Previous,Best)<=Speed/60){const FVector Delta=S.HeadDelta-PreviousDelta;
     for(int K=0;K<20;++K){const double U=(Lo+Hi)*.5;const FQuat Q=LimitHeadTilt(S,(Exp(PreviousDelta+Delta*U)*S.HeadReference).GetNormalized());
      if(Angle(Previous,Q)<=Speed/60){Lo=U;Best=Q;}else Hi=U;}}
    S.Head=Best;
   }
   S.HeadDelta=ContinuousLog(S.Head*S.HeadReference.Inverse(),&S.HeadDelta);
  }
  if(FMath::Min((S.Head-Last).SizeSquared(),(S.Head+Last).SizeSquared())<1.e-24)break;
 }
 S.Status.HeadStep=Angle(Previous,S.Head);S.HeadDone=Out&&FMath::Max(Angle(S.Head,Desired),FMath::RadiansToDegrees((S.HeadDelta-S.HeadTargetDelta).Size()))<.001;
 FQuat Third,Two;HeadFactors(S,BaseThird,Third,Two);const FVector P1=Neck[0].GetLocation()+Third.RotateVector(Neck[1].GetLocation()-Neck[0].GetLocation());
 S.Pose[S.Neck[0]]=FTransform((Third*Neck[0].GetRotation()).GetNormalized(),Neck[0].GetLocation());
 S.Pose[S.Neck[1]]=FTransform((Two*Neck[1].GetRotation()).GetNormalized(),P1);
 S.Pose[S.Neck[2]]=FTransform(S.Head,P1+Two.RotateVector(Neck[2].GetLocation()-Neck[1].GetLocation()));
}

static void Endpoint(FActive& S,FVector Body,const FTransform& Target,const FTransform (&Seed)[3],FTransform (&Out)[3],const FQuat* Authored=nullptr)
{
 BodyPose(S,S.Base,Body,S.Work,false,Authored?Authored:S.Authored.Destination);ApplyArm(S,S.Work,Seed);Solve(S,S.Work,Target);CaptureArm(S,S.Work,Out);
}
static void PlanReach(FActive& S)
{
 CaptureArm(S,S.Base,S.SourceArm);
 const auto& B=S.Profile.Body[S.Sheathe];const FTransform& Goal=S.Sheathe?S.Clear:S.Seat;
 if(B.Authored){
  // The lab first plans against the maximum-speed torso turn, then schedules
  // that turn across the accepted arm deadline. Keep its conservative deadline
  // when the fully turned shoulder subsequently shortens the arm path.
  const int BodyTicks=FMath::CeilToInt(AuthoredDistance(S.Authored.Entry,S.Authored.Destination)/B.Speed*60);
  S.Status.ReachTicks=1;
  for(int Pass=0;Pass<16;++Pass){FQuat Body[3];for(int K=0;K<3;++K){const double Degrees=Angle(S.Authored.Entry[K],S.Authored.Destination[K]);Body[K]=FQuat::Slerp(S.Authored.Entry[K],S.Authored.Destination[K],Degrees>0?FMath::Min(1.,B.Speed*S.Status.ReachTicks/60/Degrees):1.).GetNormalized();}
   Endpoint(S,FVector::ZeroVector,Goal,S.SourceArm,S.DestinationArm,Body);
   const int Required=FMath::Max(BodyTicks,FMath::CeilToInt(ArmDuration(S.SourceArm,S.DestinationArm,S.ReachSpeed,S.RotationSpeed)*60));
   if(Required<=S.Status.ReachTicks)break;S.Status.ReachTicks=Required;
  }
  Endpoint(S,FVector::ZeroVector,Goal,S.SourceArm,S.DestinationArm);return;
 }
 S.Desired=Optimize(S);Endpoint(S,S.Desired,Goal,S.SourceArm,S.DestinationArm);
 const double BodyTicks=FMath::Max(FMath::Abs(S.Desired.X),FVector2D(S.Desired.Y,S.Desired.Z).Size())/FMath::DegreesToRadians(S.Profile.BodySpeed)*60;
 S.Status.ReachTicks=FMath::Max(FMath::CeilToInt(ArmDuration(S.SourceArm,S.DestinationArm,S.ReachSpeed,S.RotationSpeed)*60),FMath::CeilToInt(BodyTicks));
}
// Reach and slide never run together. Reuse the guide buffers for the filtered
// destination during reach; SetSliding resets their key before slide sampling.
// Keep destination quaternion signs continuous across refits: choosing a new
// shortest arc from the original source can reverse a nearly completed wrist.
template<typename FEndpoint>
static void ReachArm(FActive& S,bool Refit,FEndpoint&& Fit)
{
 // The reach deadline is not arrival. Keep filtering new destinations while
 // pursuing a moving target; shortening this window forces a deadline snap.
 constexpr double Window=4;
 if(S.LastGuide<0){
  for(int K=0;K<3;++K){auto& D=S.DestinationArm[K];if((S.SourceArm[K].GetRotation()|D.GetRotation())<0)D.SetRotation(D.GetRotation()*-1.);S.SlideA[K]=D;}
  S.LastGuide=0;
 }
 if(Refit||S.Status.ReachDone){
  const double T=Clamp(double(S.Status.Tick-S.LastGuide)/Window);
  FTransform Destination[3];Fit(Destination);
  for(int K=0;K<3;++K){
   S.SlideA[K]=Blend(S.SlideA[K],S.DestinationArm[K],T);
   const FQuat Q=Destination[K].GetRotation();Destination[K].SetRotation((S.DestinationArm[K].GetRotation()|Q)<0?Q*-1.:Q);
   S.DestinationArm[K]=Destination[K];
  }
  S.LastGuide=S.Status.Tick;
 }
 const double T=Clamp(double(S.Status.Tick-S.LastGuide+1)/Window);FTransform Local[3];
 for(int K=0;K<3;++K){const FTransform Destination=T>=1?S.DestinationArm[K]:Blend(S.SlideA[K],S.DestinationArm[K],T);
  Local[K]=FTransform(FQuat::SlerpFullPath(S.SourceArm[K].GetRotation(),Destination.GetRotation(),S.Status.Progress).GetNormalized(),
   Offset(S.SourceArm[K].GetLocation(),Destination.GetLocation(),S.Status.Progress));
 }
 ApplyArm(S,S.Pose,Local);
}
static void PrepareEntryInertia(FActive& S,TConstArrayView<FTransform> Prior)
{
 if(!S.Profile.Body[S.Sheathe].Authored||S.Profile.EntryInertia<=0||S.Profile.EntryDuration<=0)return;
 check(Prior.Num()==S.Base.Num());
 const double Dt=1.e-4;TArray<FTransform> Before=S.Base,After=S.Base;
 for(int J=0;J<S.Names.Num();++J){
  const auto& Current=S.Base[J];const FVector Move=(Current.GetLocation()-Prior[J].GetLocation())*(Dt*60);
  const FQuat Delta=Exp(Log(Prior[J].GetRotation().Inverse()*Current.GetRotation())*(Dt*60));
  Before[J]=FTransform((Current.GetRotation()*Delta.Inverse()).GetNormalized(),Current.GetLocation()-Move);
  After[J]=FTransform((Current.GetRotation()*Delta).GetNormalized(),Current.GetLocation()+Move);
 }
 // Use a tiny forward procedural sample to subtract its outgoing FK velocity.
 FActive Next=S;Next.Base=After;const double Fraction=S.Profile.Reach[S.Sheathe].Sample(Dt*60/FMath::Max(1,S.Status.ReachTicks));
 AdvanceAuthored(Next,Fraction);BodyPose(Next,Next.Base,FVector::ZeroVector,Next.Pose);
 FTransform Arm[3];for(int K=0;K<3;++K)Arm[K]=Blend(S.SourceArm[K],S.DestinationArm[K],Fraction);ApplyArm(Next,Next.Pose,Arm);
 const double Want=WrappedDegrees(PoleTarget(S,S.Sheathe?0:1)-Next.Authored.PoleAngle);Next.Authored.PoleAngle+=FMath::Clamp(Want,-Next.Authored.PoleReachSpeed*Dt,Next.Authored.PoleReachSpeed*Dt);ApplyPole(Next,false);
 SeedEntryInertia(S,Before,Next.Pose,Dt);
}
bool CaptureEntryPose(AProphecyAgent* A,FEntryPose& Out)
{
 if(!IsValid(A))return false;float Alpha;TArray<FTransform> Future;FProphecyNNPoseSnapshot Snapshot;
 TGuardValue<bool> Guard(ReadingBase,true);
 return A->ReadNNFutureWorldPoseWithSnapshot(Out.Names,Future,Out.Pose,Alpha,Snapshot);
}
static void SetRootFrame(FActive& S,const FQuat& Frame)
{
 // Keep the complete head history root-local. Its stored world-space form
 // must move with the root before spending this tick's look-in/out budget.
 // Transport signed rotation vectors too; moving only the head quaternion
 // leaves the old world winding in the neck distribution and return target.
 const FQuat Delta=(Frame*S.Authored.Frame.Inverse()).GetNormalized();
 S.Authored.Frame=Frame;
 if(Delta.Equals(FQuat::Identity,1.e-12))return;
 // Stabilize pelvis motion inside the root frame, never the root turn itself.
 if(S.Stabilizing)S.StableHolster=(Delta*S.StableHolster).GetNormalized();
 if(!S.HeadInitialized)return;
 S.Head=(Delta*S.Head).GetNormalized();S.HeadStart=(Delta*S.HeadStart).GetNormalized();S.HeadReference=(Delta*S.HeadReference).GetNormalized();
 for(FVector* V:{&S.HeadDelta,&S.HeadFrom,&S.HeadTargetDelta,&S.HeadAim,&S.HeadBaseDelta,&S.NeckParentDelta})*V=Delta.RotateVector(*V);
}
static bool ReadBase(AProphecyAgent* A,FActive& S)
{
 float Alpha;TGuardValue<bool> Guard(ReadingBase,true);
 if(!A->ReadNNFutureWorldPoseWithSnapshot(S.ReadNames,S.Future,S.Base,Alpha,S.Snapshot)||S.ReadNames!=S.Names)return false;
 if(const auto* Mesh=A->GetAgentMesh())SetRootFrame(S,Mesh->GetComponentQuat());
 return true;
}
bool Begin(AProphecyAgent* A,bool Sheathe,double Reach,double Rotation,double Slide,double Length,const FTransform& Clear,const FTransform& Seat,const FVector& Mouth,const FGeometry& Geometry,const FEntryPose* Previous)
{
 const auto* Mesh=A?A->GetPoseReferenceMesh():nullptr;
 if(!Mesh||!Mesh->GetSkeletalMeshAsset())return false;
 // A queued start owns its slot already. Retire only a previous pose here.
 if(Active.Contains(A))Remove(A);
 auto S=MakeUnique<FActive>();S->Sheathe=Sheathe;S->ReachSpeed=Reach;S->RotationSpeed=Rotation;S->SlideSpeed=Slide;S->SlideLength=Length;S->Clear=Clear;S->Seat=Seat;S->Mouth=Mouth;
 if(const auto* P=Profiles.Find(A))S->Profile=*P;
 float Interval=1.f/30,Alpha;bool Interpolate;if(!A->GetNNPoseDataSource(S->PoseId,Interval,Interpolate))
 {const auto* Anim=Cast<UProphecyNNLocomotionAnimInstance>(Mesh->GetAnimInstance());if(!Anim)return false;S->PoseId=Anim->AgentId;}
 TArray<FTransform> Future;{TGuardValue<bool> Guard(ReadingBase,true);if(!A->ReadNNFutureWorldPoseWithSnapshot(S->Names,Future,S->Base,Alpha,S->Snapshot))return false;}
 auto Find=[&](const TCHAR* N){return S->Names.IndexOfByKey(FName(N));};S->Pelvis=Find(TEXT("pelvis"));S->Clav=Find(TEXT("clavicle_r"));
 for(int I=0;I<5;++I)S->Spine[I]=Find(*FString::Printf(TEXT("spine_0%d"),I+1));
 const TCHAR* Arm[]={TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};const TCHAR* Neck[]={TEXT("neck_01"),TEXT("neck_02"),TEXT("head")};
 for(int I=0;I<3;++I){S->Arm[I]=Find(Arm[I]);S->Neck[I]=Find(Neck[I]);if(S->Arm[I]<0||S->Neck[I]<0)return false;}for(int J:S->Spine)if(J<0)return false;if(S->Pelvis<0||S->Clav<0)return false;
 const auto& Ref=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();S->Parents.SetNum(S->Names.Num());S->Groups.Init(-1,S->Names.Num());
 for(int J=0;J<S->Names.Num();++J){int B=Ref.FindBoneIndex(S->Names[J]),P=INDEX_NONE;while(B>=0){B=Ref.GetParentIndex(B);if(B>=0){P=S->Names.IndexOfByKey(Ref.GetBoneName(B));if(P>=0)break;}}S->Parents[J]=P;

  const FString N=S->Names[J].ToString();if(N.StartsWith(TEXT("spine_")))S->Groups[J]=0;else if(N.StartsWith(TEXT("clavicle_")))S->Groups[J]=1;else if(N.StartsWith(TEXT("upperarm_")))S->Groups[J]=2;else if(N.StartsWith(TEXT("lowerarm_")))S->Groups[J]=3;else if(J==S->Neck[0])S->Groups[J]=4;else if(J==S->Neck[1])S->Groups[J]=5;else if(J==S->Neck[2])S->Groups[J]=6;
 }
 if(!PrepareUpperOrder(*S))return false;
 if(S->Profile.EntryInertia>0&&(!Previous||Previous->Names!=S->Names||Previous->Pose.Num()!=S->Base.Num()))return false;
 if(const auto* AgentMesh=A->GetAgentMesh())S->Authored.Frame=AgentMesh->GetComponentQuat();
 if(S->Profile.Body[Sheathe].Authored&&!PrepareAuthored(*S))return false;
 if(!Sheathe&&S->Profile.Body[Sheathe].Authored)S->Groups[S->Arm[2]]=7;
 const FQuat Top=S->Base[S->Spine[4]].GetRotation();S->SpineAxis=Top.UnrotateVector(S->Base[S->Neck[0]].GetLocation()-S->Base[S->Spine[4]].GetLocation()).GetSafeNormal();
 const FVector Axis=S->Base[S->Clav].GetRotation().UnrotateVector(S->Base[S->Arm[0]].GetLocation()-S->Base[S->Clav].GetLocation()).GetSafeNormal();S->ClavU=FVector::CrossProduct(Axis,FMath::Abs(Axis.X)<.8?FVector::ForwardVector:FVector::RightVector).GetSafeNormal();S->ClavV=FVector::CrossProduct(Axis,S->ClavU);
 S->Geometry=Geometry;RefreshGeometry(*S);
 S->GazeInput={-double(A->UpperNNGazeYawNormalized),double(A->UpperNNGazePitchNormalized)};S->StartGaze=S->Gaze=FMath::Abs(S->GazeInput.X);NeutralFacing(*S);
 PlanReach(*S);
 S->Status.SlideTicks=FMath::Max(1,FMath::CeilToInt(Length/Slide*60));
 if(S->Profile.Body[Sheathe].Authored){PreparePole(*S);if(Previous)PrepareEntryInertia(*S,Previous->Pose);}
 S->Pose=S->Before=S->Entry=S->LastBase=S->LastBody=S->Base;S->Head=S->Base[S->Neck[2]].GetRotation();S->HeadStart=S->Head;S->Status.Ready=true;
 S->HeadReference=S->NeutralHead;S->HeadDelta=Log(S->Head*S->HeadReference.Inverse());S->HeadBaseDelta=S->HeadDelta;S->HeadFrom=S->HeadDelta;
 S->HeadInitialized=true;
 Publish(*S);Active.Add(A,MoveTemp(S));EnsureCleanup();ProphecyBlendClock::Start(A,ProphecyBlendClock::EKind::SwordHolster);return true;
}
bool Status(const AProphecyAgent* A,FStatus& Out){const auto* S=Active.IsEmpty()?nullptr:Active.Find(A);if(!S)return false;Out=(*S)->Status;return true;}
static void StartSlide(FActive& S);
void SetSliding(const AProphecyAgent* A,bool Value){if(auto* P=Active.Find(A)){auto& S=**P;if(Value&&!S.Sliding){StartSlide(S);}}}
static bool SheatheReady(const FActive& S,const FTransform& Blade)
{return Angle(Blade.GetRotation(),S.Full.GetRotation())<=S.Profile.RotationTolerance+1.e-5&&
 (S.Geometry.LeewayPhase||FVector::Distance(Blade.TransformPosition(S.Geometry.TipLocal),S.Mouth)<=S.Geometry.TipTolerance);}
bool TrySheathe(const AProphecyAgent* A,const FTransform& Blade)
{
 auto* P=Active.Find(A);if(!P)return false;auto& S=**P;if(!S.Sheathe||S.Sliding||S.Status.Aligning||!S.Geometry.Valid)return false;
 RefreshGeometry(S,false);if(!SheatheReady(S,Blade))return false;
 S.EntryScale=ReachScale(S);
 const auto* Mesh=A->GetPoseReferenceMesh();const FTransform HandWorld=Mesh->GetSocketTransform(A->SwordHandSocket);const FVector Hand=HandWorld.GetLocation();
 CaptureGrip(S,Blade,HandWorld,S.EntryScale);
 CaptureArm(S,S.Pose,S.HeldArm);
 if(S.Geometry.LeewayPhase){
  S.TipAlignment.Begin(S.HolsterFrame,S.Full,Blade,S.Geometry.TipLocal,S.Geometry.BaseLocal,S.Mouth,Hand,S.EntryScale,S.Status.Tick,S.Profile.RotationTolerance,S.Geometry.AttachedSpeed,S.Geometry.AttachedRotation);
  S.Status.Aligning=true;BeginHolsterGrip(S);
 }else{
  S.EntryRotation=(S.Full.GetRotation().Inverse()*Blade.GetRotation()).GetNormalized();
  S.EntryTipError=S.Full.GetRotation().UnrotateVector(Blade.TransformPosition(S.Geometry.TipLocal)-S.Mouth);StartSlide(S);
 }
 return true;
}
static FTransform SwordHandTarget(const FActive& S,double& Scale)
{
 // After capture, the holster-local sword path owns the grip target. The
 // solved arm follows it; arm reach must never pull the sword off that path.
 if(S.Status.Aligning){Scale=S.TipAlignment.Scale;return AlignmentGoal(S);}
 Scale=S.Sheathe?(S.Sliding?SlideScale(S,S.Status.SlideProgress):ReachScale(S)):S.Geometry.Retained;
 return S.Sliding?SlideGoal(S,S.Status.SlideProgress,Clamp(double(S.Status.Tick-S.SlideStart)/S.Status.SlideTicks)):S.Sheathe?S.Clear:S.Seat;
}
bool SwordTarget(const AProphecyAgent* A,FTransform& Hand,double& Scale)
{
 const auto* P=Active.Find(A);if(!P)return false;Hand=SwordHandTarget(**P,Scale);return true;
}
bool PhysicsSwordTarget(const AProphecyAgent* A,FTransform& Blade)
{
 const auto* P=Active.Find(A);if(!P||(!(**P).Sliding&&!(**P).Status.Aligning)||!(**P).Geometry.Valid)return false;
 FTransform Hand;double Scale;if(!SwordTarget(A,Hand,Scale))return false;
 Blade=GripAt(**P,Scale)*Hand;return true;
}
void SetTargets(const AProphecyAgent* A,const FTransform& Clear,const FTransform& Seat,const FVector& Mouth){if(auto* P=Active.Find(A)){if((*P)->Geometry.Valid)RefreshGeometry(**P,false);else{(*P)->Clear=Clear;(*P)->Seat=Seat;(*P)->Mouth=Mouth;}}}
static void BeginReturn(FActive& S,FReturnTrack& Track)
{
 FBoneOrder Order;if(!HierarchyOrder(S.Parents,Order))return; // Validated at admission.
 const auto& R=S.Profile.Return[S.Sheathe];const int N=S.Base.Num();Track.ReturnStart.SetNum(N);Track.ReturnIdle.SetNum(N);Track.Velocity.SetNumZeroed(N);Track.OffsetVelocity.SetNumZeroed(N);Track.WorldVelocity.SetNumZeroed(N);Track.WorldCorrection.SetNumZeroed(N);Track.ReturnWorld.SetNum(N);Track.ReturnBaselineWorld.SetNum(N);Track.ReturnActualWorld.SetNum(N);
 TArray<FQuat> PreviousWorld;PreviousWorld.SetNum(N);
 for(int J:Order){const int P=S.Parents[J];Track.ReturnStart[J]=P>=0?S.Pose[J].GetRelativeTransform(S.Pose[P]):S.Pose[J];Track.ReturnIdle[J]=P>=0?S.Base[J].GetRelativeTransform(S.Base[P]):S.Base[J];
  const FTransform Before=P>=0?S.LastBody[J].GetRelativeTransform(S.LastBody[P]):S.LastBody[J],BaseBefore=P>=0?S.LastBase[J].GetRelativeTransform(S.LastBase[P]):S.LastBase[J];
  const FQuat Previous=(Track.ReturnIdle[J].GetRotation()*BaseBefore.GetRotation().Inverse()*Before.GetRotation()).GetNormalized();
  const FVector PreviousOffset=FQuat::FindBetweenVectors(BaseBefore.GetLocation(),Track.ReturnIdle[J].GetLocation()).RotateVector(Before.GetLocation());
  Track.OffsetVelocity[J]=Log(FQuat::FindBetweenVectors(PreviousOffset,Track.ReturnStart[J].GetLocation()))*60;
  Track.ReturnWorld[J]=P>=0?(Track.ReturnWorld[P]*Track.ReturnStart[J].GetRotation()).GetNormalized():Track.ReturnStart[J].GetRotation();
  PreviousWorld[J]=P>=0?(PreviousWorld[P]*Previous).GetNormalized():Previous;
  Track.WorldVelocity[J]=Log(Track.ReturnWorld[J]*PreviousWorld[J].Inverse())*60;
 }
 Track.ReturnDuration=R.Duration+R.AngleTime*Angle(Track.ReturnStart[S.Spine[0]].GetRotation(),Track.ReturnIdle[S.Spine[0]].GetRotation())/90;
 TArray<FVector> ActualRate,BaseRate;ActualRate.Init(FVector::ZeroVector,N);BaseRate.Init(FVector::ZeroVector,N);
 // Even a grip-only return inherits the torso's incoming rotation. Evaluate
 // its ancestor rates before subtracting them from the clavicle/arm rates.
 for(int J:S.Upper){const int P=S.Parents[J],G=S.Groups[J];const FVector IdleVelocity=Log(Track.ReturnStart[J].GetRotation().Inverse()*Track.ReturnIdle[J].GetRotation())*((1-R.Easing)/Track.ReturnDuration);
  BaseRate[J]=(P>=0?BaseRate[P]:FVector::ZeroVector)+Track.ReturnWorld[J].RotateVector(IdleVelocity);
  Track.WorldCorrection[J]=Track.WorldVelocity[J]-BaseRate[J];const bool Inertial=G>=0&&R.Inertia*R.Weights[G]>0;
  Track.Velocity[J]=Inertial?Track.ReturnWorld[J].UnrotateVector(Track.WorldVelocity[J]-(P>=0?ActualRate[P]:FVector::ZeroVector))-IdleVelocity:FVector::ZeroVector;
  ActualRate[J]=(P>=0?ActualRate[P]:FVector::ZeroVector)+Track.ReturnWorld[J].RotateVector(IdleVelocity+Track.Velocity[J]);
 }
 Track.PreparedReturn.SetNum(N);
 for(int J:(Track.OnlyGrip?S.GripUpper:S.Upper)){auto& C=Track.PreparedReturn[J];const auto& Start=Track.ReturnStart[J];const auto& Idle=Track.ReturnIdle[J];
  C.Rotation.Prepare(Start.GetRotation(),Idle.GetRotation());C.Offset.Prepare(Start.GetLocation(),Idle.GetLocation().GetSafeNormal()*Start.GetLocation().Size());
  C.Angular.Prepare(Track.Velocity[J]);C.Translation.Prepare(Track.OffsetVelocity[J]);C.World.Prepare(Track.WorldCorrection[J]);
  C.OffsetAlongIdle=C.Offset.Constant&&(Start.GetLocation().GetSafeNormal()-Idle.GetLocation().GetSafeNormal()).SizeSquared()<1.e-24;
  C.Child=S.Groups[J]==2?S.Names.IndexOfByKey(FName(*S.Names[J].ToString().Replace(TEXT("upperarm"),TEXT("lowerarm")))):INDEX_NONE;
 }
 S.Status.Returning=true;
}
static void MountReturn(FActive& S,FReturnTrack& Track,const TArray<FTransform>& Locals)
{
 for(int J:(Track.OnlyGrip?S.GripUpper:S.Upper)){const int P=S.Parents[J];const auto Moving=S.Base[J].GetRelativeTransform(S.Base[P]);const auto& Idle=Track.ReturnIdle[J];
  const FQuat Q=(Moving.GetRotation()*Idle.GetRotation().Inverse()*Locals[J].GetRotation()).GetNormalized();
  const FVector V=FQuat::FindBetweenVectors(Idle.GetLocation(),Moving.GetLocation()).RotateVector(Locals[J].GetLocation());S.Pose[J]=FTransform(Q,V)*S.Pose[P];}
}
static void AdvanceSpring(FActive& S,FReturnTrack& Track,double Elapsed)
{
 const auto& R=S.Profile.Return[S.Sheathe];const int N=S.Base.Num();
 if(Track.SpringFrames.IsEmpty()){
  Track.SpringCount=FMath::CeilToInt(Track.ReturnDuration*480);Track.SpringStep=0;Track.SpringFrames.Add(Track.ReturnStart);Track.SpringFrames.Add(Track.ReturnStart);Track.SpringTimes={0,0};
  Track.SpringRates=Track.Velocity;Track.SpringOffsetRates=Track.OffsetVelocity;Track.SpringParentRates.Init(FVector::ZeroVector,N);Track.SpringWorld=Track.ReturnWorld;
  for(int J:(Track.OnlyGrip?S.GripUpper:S.Upper))Track.SpringRates[J]=R.World?Track.WorldVelocity[J]:Track.Velocity[J]+Log(Track.ReturnStart[J].GetRotation().Inverse()*Track.ReturnIdle[J].GetRotation())*((1-R.Easing)/Track.ReturnDuration);
 }
 // Only two neighbouring samples are retained. No per-agent 480-Hz pose bank.
 while(Track.SpringTimes[1]<Elapsed&&Track.SpringStep<Track.SpringCount){
  ++Track.SpringStep;Track.SpringFrames[0]=Track.SpringFrames[1];Track.SpringTimes[0]=Track.SpringTimes[1];
  const double Time=Track.ReturnDuration*(1-FMath::Square(1-double(Track.SpringStep)/Track.SpringCount)),Dt=Time-Track.SpringTimes[0],X=Time/Track.ReturnDuration,Ordinary=X+(Ease(X)-X)*R.Easing;
  const double Frequency=(.15+6*FMath::Pow(X,1+3*R.Easing))/FMath::Max(Track.ReturnDuration-Time,Dt);Track.SpringPreviousWorld=Track.SpringWorld;
  auto& Local=Track.SpringFrames[1];auto& World=Track.SpringWorld;auto& Rates=Track.SpringRates;auto& OffsetRates=Track.SpringOffsetRates;auto& ParentRates=Track.SpringParentRates;const auto& Previous=Track.SpringPreviousWorld;
  for(int J:(Track.OnlyGrip?S.GripUpper:S.Upper)){const int P=S.Parents[J],G=S.Groups[J];const double Effective=G>=0?R.Inertia*R.Weights[G]:0;
   if(Effective>0){const double K=Frequency*Frequency/FMath::Max(.05,Effective),C=2*FMath::Sqrt(K)*((.35+.65*R.Decay)*(1-X*X)+X*X),Den=1+C*Dt+K*Dt*Dt;
    if(R.World){const FQuat Target=(World[P]*Track.ReturnIdle[J].GetRotation()).GetNormalized();Rates[J]=(Rates[J]+(Log(Target*Previous[J].Inverse())*K+ParentRates[P]*C)*Dt)/Den;World[J]=(Exp(Rates[J]*Dt)*Previous[J]).GetNormalized();Local[J].SetRotation((World[P].Inverse()*World[J]).GetNormalized());}
    else{Rates[J]=(Rates[J]+Log(Local[J].GetRotation().Inverse()*Track.ReturnIdle[J].GetRotation())*(K*Dt))/Den;Local[J].SetRotation((Local[J].GetRotation()*Exp(Rates[J]*Dt)).GetNormalized());World[J]=(World[P]*Local[J].GetRotation()).GetNormalized();}
    OffsetRates[J]=(OffsetRates[J]+Log(FQuat::FindBetweenVectors(Local[J].GetLocation(),Track.ReturnIdle[J].GetLocation()))*(K*Dt))/Den;Local[J].SetTranslation(Exp(OffsetRates[J]*Dt).RotateVector(Local[J].GetLocation()));
   }else{Local[J]=Blend(Track.ReturnStart[J],Track.ReturnIdle[J],Ordinary);World[J]=(World[P]*Local[J].GetRotation()).GetNormalized();}
   ParentRates[J]=Log(World[J]*Previous[J].Inverse())/Dt;
  }
  Track.SpringTimes[1]=Time;
  if(Track.SpringStep==Track.SpringCount)for(int J:(Track.OnlyGrip?S.GripUpper:S.Upper)){auto& End=Local[J];End=Track.ReturnIdle[J];End.SetTranslation(End.GetLocation().GetSafeNormal()*Track.ReturnStart[J].GetLocation().Size());}
 }
}
static void ReturnStep(FActive& S,FReturnTrack& Track,double Elapsed)
{
 const auto& R=S.Profile.Return[S.Sheathe];if(!R.Enabled){MountReturn(S,Track,Track.ReturnStart);return;}const double X=Clamp(Elapsed/Track.ReturnDuration);if(X>=1){
  if(!Track.OnlyGrip)S.Pose=S.Base;
  else for(int J:S.GripUpper){const int P=S.Parents[J];S.Pose[J]=S.Base[J].GetRelativeTransform(S.Base[P])*S.Pose[P];}
  return;
 }
 auto& Locals=S.Work;
 if(R.Spring&&R.Inertia>0){Locals=Track.ReturnStart;AdvanceSpring(S,Track,Elapsed);const double T=Clamp((Elapsed-Track.SpringTimes[0])/FMath::Max(1.e-12,Track.SpringTimes[1]-Track.SpringTimes[0]));for(int J:(Track.OnlyGrip?S.GripUpper:S.Upper))Locals[J]=Blend(Track.SpringFrames[0][J],Track.SpringFrames[1][J],T);MountReturn(S,Track,Locals);return;}
 const double BlendAlpha=X+(Ease(X)-X)*R.Easing,Fade=Clamp((X-R.Hold)/(1-R.Hold)),Phase=R.Hold>0?Fade*Fade:X,Envelope=Elapsed*FMath::Pow(1-Phase,3);
 double GroupEnvelope[8];for(int G=0;G<8;++G){const double Effective=R.Inertia*R.Weights[G];GroupEnvelope[G]=G>0&&R.Weights[G]==R.Weights[0]?GroupEnvelope[0]:Effective>0?Envelope*FMath::Exp(-R.Decay*Phase/(.025+.45*Effective)):0;}
 // Local return needs neither world-inertia hierarchies nor an intermediate
 // pose. Unchanged offsets only follow the moving bone direction, retaining
 // the captured length even when the live NN changes its segment lengths.
 if(!R.World&&R.TwistRemoval==0){
  for(int J:(Track.OnlyGrip?S.GripUpper:S.Upper)){const int P=S.Parents[J],G=S.Groups[J];const auto& C=Track.PreparedReturn[J];const double M=G>=0?GroupEnvelope[G]:0;
   const auto& Base=S.Base[J];const auto& ParentBase=S.Base[P];const auto& Parent=S.Pose[P];const FQuat Carry=Parent.GetRotation()*ParentBase.GetRotation().Inverse();
   if(ParentBase.GetScale3D()!=FVector::OneVector||Parent.GetScale3D()!=FVector::OneVector){
    const auto Moving=Base.GetRelativeTransform(ParentBase);FQuat Local=C.Rotation.At(BlendAlpha);FVector V=C.Offset.At(BlendAlpha);
    if(M>0){Local=(Local*C.Angular.At(M)).GetNormalized();V=C.Translation.At(M).RotateVector(V);}
    S.Pose[J]=FTransform((Moving.GetRotation()*Track.ReturnIdle[J].GetRotation().Inverse()*Local).GetNormalized(),FQuat::FindBetweenVectors(Track.ReturnIdle[J].GetLocation(),Moving.GetLocation()).RotateVector(V))*Parent;continue;
   }
   FQuat Q;
   if(C.Rotation.Constant&&(M==0||C.Angular.Speed<1.e-12))Q=(Carry*Base.GetRotation()).GetNormalized();
   else{Q=C.Rotation.At(BlendAlpha);if(M>0&&C.Angular.Speed>1.e-12)Q=(Q*C.Angular.At(M)).GetNormalized();Q=(Carry*Base.GetRotation()*Track.ReturnIdle[J].GetRotation().Inverse()*Q).GetNormalized();}
   FVector Position;
   if(C.OffsetAlongIdle&&(M==0||C.Translation.Speed<1.e-12))Position=Parent.GetLocation()+Carry.RotateVector((Base.GetLocation()-ParentBase.GetLocation()).GetSafeNormal()*C.Offset.LengthA);
   else{FVector V=C.Offset.At(BlendAlpha);if(M>0&&C.Translation.Speed>1.e-12)V=C.Translation.At(M).RotateVector(V);const FVector Moving=ParentBase.GetRotation().UnrotateVector(Base.GetLocation()-ParentBase.GetLocation());
    Position=Parent.GetLocation()+Parent.GetRotation().RotateVector(FQuat::FindBetweenVectors(Track.ReturnIdle[J].GetLocation(),Moving).RotateVector(V));}
   S.Pose[J]=FTransform(Q,Position);
  }
  return;
 }
 Locals=Track.ReturnStart;
 if(R.World){Track.ReturnBaselineWorld=Track.ReturnWorld;Track.ReturnActualWorld=Track.ReturnWorld;}
 for(int J:(Track.OnlyGrip?S.GripUpper:S.Upper)){const int P=S.Parents[J],G=S.Groups[J];const auto& C=Track.PreparedReturn[J];const FQuat Baseline=C.Rotation.At(BlendAlpha);FQuat Q=Baseline;FVector V=C.Offset.At(BlendAlpha);
  const double M=G>=0?GroupEnvelope[G]:0;
  if(R.World)Track.ReturnBaselineWorld[J]=(Track.ReturnBaselineWorld[P]*Baseline).GetNormalized();
  if(M>0){if(!R.World)Q=(Q*C.Angular.At(M)).GetNormalized();V=C.Translation.At(M).RotateVector(V);}
  if(R.World){Track.ReturnActualWorld[J]=M>0?(C.World.At(M)*Track.ReturnBaselineWorld[J]).GetNormalized():(Track.ReturnActualWorld[P]*Baseline).GetNormalized();Q=(Track.ReturnActualWorld[P].Inverse()*Track.ReturnActualWorld[J]).GetNormalized();}
  Locals[J]=FTransform(Q,V);
 }
 if(R.TwistRemoval>0&&Envelope>0){
  TArray<FQuat,TInlineAllocator<32>> Corrected,Carry;
  if(R.World){Corrected.Append(Track.ReturnActualWorld);Carry.Init(FQuat::Identity,S.Names.Num());}
  for(int J:(Track.OnlyGrip?S.GripUpper:S.Upper)){const int P=S.Parents[J],G=S.Groups[J];
   if(R.World)Carry[J]=Carry[P];
   if(G==2&&R.Inertia*R.Weights[G]>0){const int Child=Track.PreparedReturn[J].Child;if(Child>=0){
    const FQuat Baseline=R.World?Track.ReturnBaselineWorld[J]:Track.PreparedReturn[J].Rotation.At(BlendAlpha);
    const FQuat Raw=R.World?Track.ReturnActualWorld[J]:Locals[J].GetRotation();
    const FQuat Q=FQuat(ProphecyFKReturn::RemoveAxialInertia(FQuat4f(Baseline),FQuat4f(Raw),FVector3f(Locals[Child].GetLocation().GetSafeNormal()),R.TwistRemoval));
    if(R.World){Corrected[J]=Q;Carry[J]=(Q*Raw.Inverse()).GetNormalized();}else Locals[J].SetRotation(Q);
   }}else if(R.World)Corrected[J]=(Carry[J]*Track.ReturnActualWorld[J]).GetNormalized();
   if(R.World)Locals[J].SetRotation((Corrected[P].Inverse()*Corrected[J]).GetNormalized());
  }
 }
 MountReturn(S,Track,Locals);
}
static void BeginReturn(FActive& S){BeginReturn(S,S);}
static void ReturnStep(FActive& S,double Elapsed){ReturnStep(S,S,Elapsed);}
static void StartSlide(FActive& S)
{
 BeginHolsterGrip(S);
 if(S.Profile.Body[S.Sheathe].Authored)for(int K=0;K<3;++K)S.SlideBody[K]=S.Authored.Current[K];
 S.Status.Aligning=false;S.Sliding=true;S.Desired=S.Body;S.SlideStart=S.Status.Tick;S.LastGuide=-1;
 if(S.Sheathe){S.SlideLength*=FMath::Abs(1-S.EntryInsertion);S.Status.SlideTicks=FMath::Max(1,FMath::CeilToInt(S.SlideLength/S.SlideSpeed*60));}
 S.Status.Insertion=Insertion(S,0);
 if(S.Profile.Body[S.Sheathe].Authored)for(int K=0;K<3;++K)S.SlideA[K]=S.HeldArm[K];else CaptureArm(S,S.Pose,S.SlideA);
 for(int K=0;K<3;++K)S.SlideB[K]=S.SlideA[K];S.GuideA=S.GuideB=0;
 // Capture the sword-relative pole at the transfer pose, not after the first
 // sliding step. Reframing does not advance the angle or consume a tick.
 if(S.Profile.Body[S.Sheathe].Authored&&S.Profile.Body[S.Sheathe].SwordPole)ApplyPole(S,false);
}
static void SlideArm(FActive& S)
{
 const double Tick=FMath::Min(double(S.Status.SlideTicks),double(S.Status.Tick-S.SlideStart));
 // Two rolling FK destinations. Refine where insertion and rotation have
 // different clocks, without retaining a pose bank or solving in consumers.
 if(S.LastGuide<0){if(!S.Profile.Body[S.Sheathe].Authored)CaptureArm(S,S.LastBody,S.SlideA);for(int K=0;K<3;++K)S.SlideB[K]=S.SlideA[K];S.LastGuide=0;}
 while(Tick>S.GuideB){
  S.GuideA=S.GuideB;for(int K=0;K<3;++K)S.SlideA[K]=S.SlideB[K];
  const double Spacing=FMath::Clamp(2*S.Status.SlideTicks/FMath::Max(S.SlideLength,1.),1.,4.);
  S.GuideB=FMath::Min(double(S.Status.SlideTicks),FMath::Max(Tick,(FMath::FloorToDouble(S.GuideA/Spacing+1.e-8)+1)*Spacing));
  const double Cut=S.Status.SlideTicks*S.Profile.RotationCorrection;
  if(S.Sheathe&&Cut>S.GuideA&&Cut<S.GuideB)S.GuideB=Cut;
  const double U=S.GuideB/S.Status.SlideTicks,P=S.Profile.Slide[S.Sheathe].Sample(U);
  FVector Body=S.Desired;if(S.Sheathe){Body.Y*=1-P;Body.Z*=1-P;}
  FQuat Authored[3];if(S.Profile.Body[S.Sheathe].Authored){AuthoredTarget(S,S.Sheathe?P:1-P,Authored);if(S.Sheathe)for(int K=0;K<3;++K)Authored[K]=FQuat::Slerp(S.SlideBody[K],S.Profile.Body[1].Targets[1][K],P).GetNormalized();}
  Endpoint(S,Body,SlideGoal(S,P,U),S.SlideA,S.SlideB,S.Profile.Body[S.Sheathe].Authored?Authored:nullptr);
 }
 FTransform Local[3];const double T=Clamp((Tick-S.GuideA)/FMath::Max(1.e-12,S.GuideB-S.GuideA));
 for(int K=0;K<3;++K)Local[K]=Blend(S.SlideA[K],S.SlideB[K],T);ApplyArm(S,S.Pose,Local);
}
static void TransplantGrip(FActive& S,const TArray<FTransform>& Donor)
{
 for(int J:S.GripUpper){const int P=S.Parents[J];S.Pose[J]=Donor[J].GetRelativeTransform(Donor[P])*S.Pose[P];}
}
static bool GripReachable(const FActive& S,const FTransform& Target)
{
 const double Length=FVector::Distance(S.Pose[S.Arm[1]].GetLocation(),S.Pose[S.Arm[0]].GetLocation())+FVector::Distance(S.Pose[S.Arm[2]].GetLocation(),S.Pose[S.Arm[1]].GetLocation());
 return FVector::Distance(S.Pose[S.Arm[0]].GetLocation(),Target.GetLocation())<=Length-.001;
}
static void Advance(FActive& S,int Steps)
{
 for(int Step=0;Step<Steps;++Step){const bool WasAligning=S.Status.Aligning;++S.Status.Tick;S.Before=S.Pose;S.Pose=S.Base;RefreshGeometry(S);
  const bool Refit=!S.Sliding&&!S.Status.Aligning&&S.Status.Tick%4==0;
  if(Refit&&!S.Profile.Body[S.Sheathe].Authored)S.Desired=Optimize(S);
  const double ReachFraction=S.Profile.Reach[S.Sheathe].Sample(double(S.Status.Tick)/FMath::Max(1,S.Status.ReachTicks));S.Status.Progress=ReachFraction;S.Status.ReachDone=S.Status.Tick>=S.Status.ReachTicks;
  const double SlideTime=S.Sliding?Clamp(double(S.Status.Tick-S.SlideStart)/S.Status.SlideTicks):0;
  S.Status.SlideProgress=S.Sliding?S.Profile.Slide[S.Sheathe].Sample(SlideTime):0;
  S.Status.Insertion=Insertion(S,S.Status.SlideProgress);
  const double SourceReachTicks=S.Status.Tick>=S.Status.ReachTicks?S.Status.Tick:ReachFraction*S.Status.ReachTicks;
  if(S.Profile.Body[S.Sheathe].Authored)AdvanceAuthored(S,ReachFraction);
  else if(!S.Sliding){
   const FVector Scheduled=Bounded(S.Desired*ReachFraction,FMath::DegreesToRadians(S.Profile.BodySpeed)*SourceReachTicks/60);
   const double PreviousSource=S.Status.Tick-1>=S.Status.ReachTicks?S.Status.Tick-1:S.Profile.Reach[S.Sheathe].Sample(double(S.Status.Tick-1)/S.Status.ReachTicks)*S.Status.ReachTicks;
   S.Body+=Bounded(Scheduled-S.Body,FMath::DegreesToRadians(S.Profile.BodySpeed)*FMath::Max(1.,SourceReachTicks-PreviousSource)/60);
  }else{S.Body=S.Desired;if(S.Sheathe){S.Body.Y*=1-S.Status.SlideProgress;S.Body.Z*=1-S.Status.SlideProgress;}}
  if(!S.Sheathe&&!S.Sliding)S.Status.ReachDone&=FMath::Max(FMath::Abs(S.Desired.X-S.Body.X),FVector2D(S.Desired.Y-S.Body.Y,S.Desired.Z-S.Body.Z).Size())<FMath::DegreesToRadians(.25);
  const int Release=S.SlideStart+S.Status.SlideTicks;const bool Holding=S.Sliding&&S.Status.Tick<=Release;
  if(!S.Status.Returning||Holding)BodyPose(S,S.Base,S.Body,S.Pose);
  if(S.Status.Aligning){
   ApplyArm(S,S.Pose,S.HeldArm);FTransform Seed[3];for(int K=0;K<3;++K)Seed[K]=S.Pose[S.Arm[K]];
   Solve(S,S.Pose,AlignmentGoal(S));if(S.Profile.Body[S.Sheathe].Authored)ApplyPole(S);
   PreserveArmRoll(S,Seed);
   CaptureArm(S,S.Pose,S.HeldArm);
   const FTransform Sword=GripAt(S,S.TipAlignment.Scale)*AlignmentGoal(S);
   if(S.Status.Tick>=S.TipAlignment.Start+S.TipAlignment.Ticks&&FVector::Distance(Sword.TransformPosition(S.Geometry.TipLocal),S.HolsterFrame.GetLocation()+S.HolsterFrame.GetRotation().RotateVector(S.TipAlignment.TargetTip))<=1.e-4){
    S.EntryScale=S.TipAlignment.Scale;S.EntryInsertion=S.TipAlignment.Insertion;S.EntryRotation=(S.Full.GetRotation().Inverse()*Sword.GetRotation()).GetNormalized();
    const FVector StartTip=S.Mouth+S.Full.GetRotation().RotateVector(GripAt(S,S.EntryScale).GetScale3D()*(S.Geometry.TipLocal-S.Geometry.BaseLocal))*S.EntryInsertion;
    S.EntryTipError=S.Full.GetRotation().UnrotateVector(Sword.TransformPosition(S.Geometry.TipLocal)-StartTip);StartSlide(S);
   }
  }
  else if(!S.Sliding)ReachArm(S,Refit,[&](FTransform (&Destination)[3]){
   // Refit from the captured reach pose, as in the lab. Feeding a previous
   // solution back into the solve accumulates axial arm rotation as gait moves.
   Endpoint(S,S.Desired,S.Sheathe?S.Clear:S.Seat,S.Profile.Body[S.Sheathe].Authored?S.SourceArm:S.DestinationArm,Destination);
  });
  else if(Holding&&!S.Status.Returning)SlideArm(S);
  if(S.Profile.Body[S.Sheathe].Authored&&!S.Status.Returning&&!WasAligning){
   // Keep guide construction independent of its final pole overlay, as in the
   // lab. Feeding the corrected arm back into the next guide accumulates twist.
   if(!S.Sliding)CaptureArm(S,S.Pose,S.HeldArm);
   ApplyPole(S);ApplyEntryInertia(S);
  }
  const auto& Profile=S.Profile.Return[S.Sheathe];
  if(S.Sliding&&!S.Status.Returning&&(S.Sheathe?S.Status.Insertion:S.Status.SlideProgress)>=Profile.StartFraction-1.e-8&&(Profile.Enabled||SlideTime>=1)){
   BeginReturn(S);S.ReturnTick=S.Status.Tick;S.BodyElapsed=0;CaptureArm(S,S.Pose,S.HeldArm);
  }
  if(S.Status.Returning&&S.Status.Tick>S.ReturnTick){
   if(Holding&&S.ReturnTick<Release){
    S.SlidePose=S.Pose;const FTransform Target=SlideGoal(S,S.Status.SlideProgress,SlideTime);
    TOptional<FReturnTrack> SpringBefore;if(Profile.Spring&&Profile.Inertia>0)SpringBefore=static_cast<const FReturnTrack&>(S);
    auto At=[&](double Time){if(SpringBefore)static_cast<FReturnTrack&>(S)=SpringBefore.GetValue();S.Pose=S.Base;ReturnStep(S,Time);TransplantGrip(S,S.SlidePose);};
    const double Next=S.BodyElapsed+1./60.;At(Next);
    double Accepted=Next;
    if(!GripReachable(S,Target)){
     double Lo=S.BodyElapsed,Hi=Next;At(Lo);
     if(GripReachable(S,Target))for(int I=0;I<8;++I){const double Mid=(Lo+Hi)*.5;At(Mid);if(GripReachable(S,Target))Lo=Mid;else Hi=Mid;}
     Accepted=Lo;At(Accepted);
    }
    S.BodyElapsed=Accepted;ApplyArm(S,S.Pose,S.HeldArm);FTransform Seed[3];for(int K=0;K<3;++K)Seed[K]=S.Pose[S.Arm[K]];
    Solve(S,S.Pose,Target);if(S.Profile.Body[S.Sheathe].Authored)ApplyPole(S);PreserveArmRoll(S,Seed);CaptureArm(S,S.Pose,S.HeldArm);
   }else{S.BodyElapsed+=1./60.;ReturnStep(S,S.BodyElapsed);}
  }
  if(S.Sliding&&S.Status.Tick==Release&&S.ReturnTick<Release&&Profile.Enabled){
   S.ArmReturn.OnlyGrip=true;BeginReturn(S,S.ArmReturn);S.ArmReturning=true;
  }
  if(S.ArmReturning&&S.Status.Tick>Release)ReturnStep(S,S.ArmReturn,double(S.Status.Tick-Release)/60);
  const FTransform Target=S.Status.Aligning?AlignmentGoal(S):S.Sliding?SlideGoal(S,S.Status.SlideProgress,SlideTime):S.Sheathe?S.Clear:S.Seat;
  S.Status.HandError=FVector::Distance(S.Pose[S.Arm[2]].GetLocation(),Target.GetLocation());
  S.Status.Blocked=!S.Sliding&&S.Status.ReachDone&&S.Status.HandError>2;S.LastBody=S.Pose;HeadStep(S);S.LastBase=S.Base;
  S.Status.Finished=S.Sliding&&SlideTime>=1&&HolsterWeight(S)<=0&&S.HeadDone&&(!Profile.Enabled||(S.BodyElapsed>=S.ReturnDuration&&(!S.ArmReturning||double(S.Status.Tick-Release)/60>=S.ArmReturn.ReturnDuration)));
 }
}

void Update(AProphecyAgent* A,int32 Id)
{
 auto* Ptr=Active.IsEmpty()?nullptr:Active.Find(A);if(!Ptr)return;auto& S=**Ptr;if(S.Status.Finished)return;
 const int Steps=FMath::RoundToInt(ProphecyBlendClock::Consume(A,ProphecyBlendClock::EKind::SwordHolster)*60);if(Steps<=0)return;
 S.PoseId=Id;if(!ReadBase(A,S))return;
 S.GazeInput={-double(A->UpperNNGazeYawNormalized),double(A->UpperNNGazePitchNormalized)};S.Gaze=FMath::Abs(S.GazeInput.X);
 Advance(S,Steps);UpdateHolsterMount(A);Publish(S);if(S.Status.Finished){ProphecyBlendClock::Stop(A,ProphecyBlendClock::EKind::SwordHolster);ProphecySwordHolsterSchedule::Remove(A);}
}
#if WITH_EDITOR
static FAutoConsoleCommand GeometryBenchCommand(TEXT("Prophecy.Sword.BenchGeometry"),TEXT("On-demand active holster sampling cost; owned diagnostics only."),FConsoleCommandDelegate::CreateLambda([]{
 FString Text=TEXT("agent,repeat,samples,microseconds_per_sample\n");
 for(const auto& Item:Active)if(const auto* A=Item.Key.Get()){
  FActive S=*Item.Value;if(!S.Geometry.Valid)continue;
  for(int Repeat=-1;Repeat<7;++Repeat){const double Start=FPlatformTime::Seconds();
   for(int K=0;K<1000;++K)RefreshGeometry(S);
   const double Microseconds=(FPlatformTime::Seconds()-Start)*1000.;
   if(Repeat>=0)Text+=FString::Printf(TEXT("%s,%d,1000,%.9f\n"),*A->GetName(),Repeat,Microseconds);
  }
 }
 FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordOvernight20261011/geometry-benchmark.csv")));
}));
static FAutoConsoleCommand PoseReportCommand(TEXT("Prophecy.Sword.PoseReport"),TEXT("On-demand numerical D/S inputs; no recurring capture."),FConsoleCommandDelegate::CreateLambda([]{
 auto Root=MakeShared<FJsonObject>();
 auto Vector=[](FVector V){TArray<TSharedPtr<FJsonValue>> R;for(int K=0;K<3;++K)R.Add(MakeShared<FJsonValueNumber>(V[K]));return R;};
 for(const auto& Item:Active)if(const auto* A=Item.Key.Get()){
  const auto& S=*Item.Value;auto J=MakeShared<FJsonObject>();J->SetNumberField(TEXT("tick"),S.Status.Tick);
  J->SetBoolField(TEXT("aligning"),S.Status.Aligning);J->SetNumberField(TEXT("alignmentStart"),S.TipAlignment.Start);J->SetNumberField(TEXT("alignmentTicks"),S.TipAlignment.Ticks);
  J->SetNumberField(TEXT("slideStart"),S.SlideStart);J->SetNumberField(TEXT("holsterWeight"),HolsterWeight(S));
  J->SetArrayField(TEXT("mouth"),Vector(S.Mouth));J->SetArrayField(TEXT("tipLocal"),Vector(S.Geometry.TipLocal));
  J->SetArrayField(TEXT("body"),Vector(S.Body));J->SetArrayField(TEXT("desired"),Vector(S.Desired));
  J->SetArrayField(TEXT("baseDelta"),Vector(S.HeadBaseDelta));J->SetArrayField(TEXT("headDelta"),Vector(S.HeadDelta));J->SetArrayField(TEXT("parentDelta"),Vector(S.NeckParentDelta));
  auto Poses=[&](const TArray<FTransform>& P){auto Out=MakeShared<FJsonObject>();for(int I=0;I<S.Names.Num();++I){auto Values=Vector(P[I].GetLocation());const auto Q=P[I].GetRotation();for(double V:{Q.X,Q.Y,Q.Z,Q.W})Values.Add(MakeShared<FJsonValueNumber>(V));Out->SetArrayField(S.Names[I].ToString(),Values);}return Out;};
  J->SetObjectField(TEXT("base"),Poses(S.Base));J->SetObjectField(TEXT("bodyPose"),Poses(S.LastBody));
  auto Arm=[&](const FTransform (&Local)[3]){TArray<TSharedPtr<FJsonValue>> Out;for(const auto& T:Local){auto Values=Vector(T.GetLocation());const auto Q=T.GetRotation();for(double V:{Q.X,Q.Y,Q.Z,Q.W})Values.Add(MakeShared<FJsonValueNumber>(V));Out.Add(MakeShared<FJsonValueArray>(Values));}return Out;};
  J->SetArrayField(TEXT("sourceArm"),Arm(S.SourceArm));J->SetArrayField(TEXT("destinationArm"),Arm(S.DestinationArm));
  J->SetArrayField(TEXT("guideA"),Arm(S.SlideA));J->SetArrayField(TEXT("guideB"),Arm(S.SlideB));J->SetArrayField(TEXT("heldArm"),Arm(S.HeldArm));
  J->SetNumberField(TEXT("poleAngle"),S.Authored.PoleAngle);J->SetArrayField(TEXT("poleZero"),Vector(S.Authored.PoleZero));J->SetArrayField(TEXT("poleDirection"),Vector(S.Authored.PoleDirection));
  J->SetArrayField(TEXT("swordDown"),Vector(S.Authored.SwordDown));J->SetBoolField(TEXT("swordPole"),S.Authored.UseSword);
  J->SetNumberField(TEXT("guideTickA"),S.GuideA);J->SetNumberField(TEXT("guideTickB"),S.GuideB);
  Root->SetObjectField(A->GetName(),J);
 }
 FString Text;FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Text));
 FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordOvernight20261011/pose-detail.json")));
}));
#endif
}
bool UProphecySwordHolsterLibrary::VisualizeSheathingLeeway(AProphecyAgent* A,float DisplayLength,float Duration)
{
#if ENABLE_DRAW_DEBUG
 using namespace ProphecySwordHolsterPose;
 if(!IsInGameThread()||!IsValid(A)||!A->GetWorld()||!FMath::IsFinite(DisplayLength)||DisplayLength<=0||!FMath::IsFinite(Duration)||Duration<0)return false;
 const auto* P=Active.Find(A);if(!P)return false;const auto& S=**P;
 if(!S.Sheathe||S.Sliding||!S.Geometry.Valid||S.Status.Finished)return false;
 const auto* H=S.Geometry.Holster.Get();const auto* C=A->FindComponentByClass<UProphecySwordComponent>();
 const auto* Sword=C?C->GetSword():nullptr;const auto* Root=IsValid(Sword)?Sword->GetRootComponent():nullptr;
 if(!IsValid(H)||!IsValid(Root))return false;
 // Exactly the component transforms used by TrySheathe, including axial shrink.
 // Do not refresh/mutate the planner or evaluate its predicted next-tick holster.
 const FTransform Full=S.Geometry.Seated*H->GetComponentTransform(),Blade=Root->GetComponentTransform();
 const FVector Mouth=Full.TransformPosition(S.Geometry.BaseLocal),Tip=Blade.TransformPosition(S.Geometry.TipLocal);
 const FVector LocalAxis=(S.Geometry.BaseLocal-S.Geometry.TipLocal).GetSafeNormal();if(LocalAxis.IsNearlyZero())return false;
 FVector LocalU,LocalV;LocalAxis.FindBestAxisVectors(LocalU,LocalV);
 const FVector Axis=Full.GetRotation().RotateVector(LocalAxis),U=Full.GetRotation().RotateVector(LocalU),V=FVector::CrossProduct(Axis,U);
 const FVector ActualAxis=Blade.GetRotation().RotateVector(LocalAxis);
 const double Limit=S.Profile.RotationTolerance,Error=Angle(Blade.GetRotation(),Full.GetRotation()),TipError=FVector::Dist(Tip,Mouth);
 const double TipLimit=S.Geometry.LeewayPhase?2:S.Geometry.TipTolerance;
 const bool RotationOK=Error<=Limit+1.e-5,TipOK=TipError<=TipLimit;
 const FColor Cyan(70,220,255),Green(90,255,110),Red(255,75,70),Amber(255,195,65),Gray(100,110,125);
 const FColor RotationColor=RotationOK?Green:Red;
 auto* World=A->GetWorld();const double Length=FMath::Clamp(double(DisplayLength),1.,500.);
 auto Line=[&](FVector From,FVector To,FColor Color,float Width=1.f){DrawDebugLine(World,From,To,Color,false,Duration,1,Width);};
 auto Label=[&](FVector At,const FString& Text,FColor Color){DrawDebugString(World,At,Text,nullptr,Color,Duration,true,1.f);};
 const double Radians=FMath::DegreesToRadians(Limit);
 auto Rim=[&](double T){return Mouth+Length*(Axis*FMath::Cos(Radians)+(U*FMath::Cos(T)+V*FMath::Sin(T))*FMath::Sin(Radians));};
 for(int I=0;I<48;++I)Line(Rim(2*PI*I/48),Rim(2*PI*(I+1)/48),RotationOK?Green:Cyan);
 for(int I=0;I<4;++I)Line(Mouth,Rim(PI*I/2),RotationOK?Green:Cyan);
 Line(Mouth,Mouth+Axis*Length,Cyan);
 Line(Mouth,Mouth+ActualAxis*Length,RotationColor,2.5f);
 DrawDebugSphere(World,Mouth,TipLimit,16,TipOK?Green:Amber,false,Duration,1,.7f);
 DrawDebugPoint(World,Tip,9,TipOK?Green:Amber,false,Duration,1);
 Line(Tip,Mouth,TipOK?Green:Amber,1.5f);

 // SO(3) tolerance is a coupled swing/twist budget, not two independent limits:
 // cos(error/2) = cos(tilt/2) * cos(roll/2). Transport the zero-roll frame with
 // the blade's minimal swing so a pure tilt reads zero roll on this dial.
 const double Tilt=FMath::Acos(FMath::Clamp(FVector::DotProduct(Axis,ActualAxis),-1.,1.));
 const FQuat Swing=FQuat::FindBetweenNormals(Axis,ActualAxis);
 const FVector DialU=Swing.RotateVector(U),DialV=FVector::CrossProduct(ActualAxis,DialU);
 const FVector ActualU=Blade.GetRotation().RotateVector(LocalU);
 const double Roll=FMath::Atan2(FVector::DotProduct(ActualU,DialV),FVector::DotProduct(ActualU,DialU));
 const double RollBudget=Tilt<=Radians?2*FMath::Acos(FMath::Clamp(FMath::Cos(Radians/2)/FMath::Max(1.e-8,FMath::Cos(Tilt/2)),0.,1.)):0;
 const double Radius=Length*.18;
 const FVector Dial=Mouth+Axis*(Length*.7)+U*(Length*.75);
 auto Circle=[&](double T){return Dial+(DialU*FMath::Cos(T)+DialV*FMath::Sin(T))*Radius;};
 for(int I=0;I<48;++I)Line(Circle(2*PI*I/48),Circle(2*PI*(I+1)/48),Gray);
 if(RollBudget>0)for(int I=0;I<24;++I)Line(Circle(FMath::Lerp(-RollBudget,RollBudget,I/24.)),Circle(FMath::Lerp(-RollBudget,RollBudget,(I+1)/24.)),Cyan,3);
 Line(Dial,Circle(0),Cyan);Line(Dial,Circle(Roll),RotationColor,2.5f);
 Label(Dial+FVector(0,0,Radius+3),FString::Printf(TEXT("Roll %.1f / +/-%.1f deg"),FMath::RadiansToDegrees(Roll),FMath::RadiansToDegrees(RollBudget)),RotationColor);
 Label(Mouth+Axis*(Length+5),FString::Printf(TEXT("S rotation %.1f / %.1f deg (includes roll)\nTip distance %.3f cm\n%s"),Error,Limit,TipError,S.Status.Aligning?TEXT("Attached: aligning tip"):RotationOK?TEXT("Capture rotation satisfied"):TEXT("Waiting for rotation")),RotationOK?Green:Amber);
 return true;
#else
 return false;
#endif
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
namespace ProphecySwordHolsterPose
{
static FVector JsonVector(const TArray<TSharedPtr<FJsonValue>>& A){return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());}
static FQuat JsonQuat(const TArray<TSharedPtr<FJsonValue>>& A){return FQuat(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber(),A[3]->AsNumber());}
static FTransform JsonPose(const TSharedPtr<FJsonObject>& J){return FTransform(JsonQuat(J->GetArrayField(TEXT("q"))),JsonVector(J->GetArrayField(TEXT("p"))));}
static TArray<FTransform> JsonPoses(const TArray<TSharedPtr<FJsonValue>>& A){TArray<FTransform> Out;for(const auto& V:A)Out.Add(JsonPose(V->AsObject()));return Out;}
#include "Tests/ProphecySwordHolsterChannelsTests.inl"
#include "Tests/ProphecySwordHolsterRollTests.inl"
#include "Tests/ProphecySwordHolsterHeadRootTests.inl"
#include "Tests/ProphecySwordHolsterLegacy.inl"
#include "Tests/ProphecySwordHolsterOptimizationTests.inl"
#include "Tests/ProphecySwordHolsterStaggerTests.inl"
#include "Tests/ProphecySwordHolsterOrderTests.inl"
#include "Tests/ProphecySwordHolsterReachTests.inl"
#include "Tests/ProphecySwordHolsterAuthoredTests.inl"
#include "Tests/ProphecySwordAcceptedMotionTests.inl"
#include "Tests/ProphecySwordTipAlignmentTests.inl"
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
  LoadProfile(FPaths::ProjectDir()/TEXT("Tools/Recovery/SwordLabCheckpoint20261010/lab-state.json"),S.Profile,Error);
  S.Profile.HeadMaxTilt=90; // Frozen pre-limit oracle.
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
