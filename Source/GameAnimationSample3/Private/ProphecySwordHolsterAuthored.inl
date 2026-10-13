// Included by the D/S controller. All geometry is captured only while active.
static double WrappedDegrees(double X){return FMath::Fmod(FMath::Fmod(X+180.,360.)+360.,360.)-180.;}
static double AuthoredDistance(const FQuat* A,const FQuat* B)
{return FMath::Max3(Angle(A[0],B[0]),Angle(A[1],B[1]),Angle(A[2],B[2]));}
static void AuthoredTarget(const FActive& S,double Insertion,FQuat* Out)
{const auto& B=S.Profile.Body[S.Sheathe];for(int K=0;K<3;++K)Out[K]=FQuat::Slerp(B.Targets[0][K],B.Targets[1][K],Clamp(Insertion)).GetNormalized();}
static bool PrepareAuthored(FActive& S)
{
 auto& A=S.Authored;const int N=S.Base.Num();A.Left=S.Names.IndexOfByKey(FName(TEXT("clavicle_l")));if(A.Left<0)return false;
 A.Local.SetNum(N);A.Driven.Init(0,N);A.InertiaBones.Reset();const FQuat Pelvis=S.Base[S.Pelvis].GetRotation();
 A.Pelvis=(A.Frame.Inverse()*Pelvis).GetNormalized();
 for(int J=0;J<N;++J){const int P=S.Parents[J];A.Local[J]=P>=0?S.Base[J].GetRelativeTransform(S.Base[P]):S.Base[J];}
 for(int K=0;K<5;++K){A.Spine[K]=(Pelvis.Inverse()*S.Base[S.Spine[K]].GetRotation()).GetNormalized();A.Driven[S.Spine[K]]=1;}
 for(int J:S.GripUpper)A.Driven[J]=1;
 for(int J:S.Upper){const auto Name=S.Names[J].ToString();if(A.Driven[J]||Name==TEXT("clavicle_l")||Name==TEXT("upperarm_l")||Name==TEXT("lowerarm_l")||Name==TEXT("hand_l"))A.InertiaBones.Add(J);}
 A.Entry[0]=A.Spine[4];A.Entry[1]=(S.Base[S.Spine[4]].GetRotation().Inverse()*S.Base[S.Clav].GetRotation()).GetNormalized();A.Entry[2]=S.Profile.BodyReference[2];
 for(int K=0;K<3;++K)A.Current[K]=A.Entry[K];AuthoredTarget(S,S.Sheathe?0:1,A.Destination);
 return true;
}
static void AuthoredBodyPose(const FActive& S,TConstArrayView<FTransform> Base,const FQuat* Target,TArray<FTransform>& Out)
{
 const auto& A=S.Authored;const auto& B=S.Profile.Body[S.Sheathe];Out.Reset();Out.Append(Base.GetData(),Base.Num());
 // The lab's world is the imported character-mesh frame. Cancel the pelvis's
 // gait rotation inside that frame, while still following character heading.
 const FQuat Stable=(A.Frame*A.Pelvis).GetNormalized();
 const FQuat Frame=B.Compensation==1?Stable:B.Compensation==0?Base[S.Pelvis].GetRotation():FQuat::Slerp(Base[S.Pelvis].GetRotation(),Stable,B.Compensation).GetNormalized();
 const FQuat Delta=(Target[0]*A.Spine[4].Inverse()).GetNormalized();
 for(int J:S.Upper){const int P=S.Parents[J];const FTransform Local=A.Driven[J]?A.Local[J]:Base[J].GetRelativeTransform(Base[P]);
  FQuat Q=(Out[P].GetRotation()*Local.GetRotation()).GetNormalized();
  for(int K=0;K<5;++K)if(J==S.Spine[K])Q=(Frame*FQuat::Slerp(FQuat::Identity,Delta,(K+1)/5.)*A.Spine[K]).GetNormalized();
  if(J==S.Clav)Q=(Out[S.Spine[4]].GetRotation()*Target[1]).GetNormalized();
  if(J==A.Left)Q=(Out[S.Spine[4]].GetRotation()*Target[2]*S.Profile.BodyReference[2].Inverse()*Local.GetRotation()).GetNormalized();
  Out[J]=FTransform(Q,Out[P].GetLocation()+(P==S.Pelvis?Frame:Out[P].GetRotation()).RotateVector(Local.GetLocation()));
 }
}
static void AdvanceAuthored(FActive& S,double ReachFraction)
{
 if(S.Sliding){AuthoredTarget(S,S.Sheathe?S.Status.SlideProgress:1-S.Status.SlideProgress,S.Authored.Current);if(S.Sheathe)for(int K=0;K<3;++K)S.Authored.Current[K]=FQuat::Slerp(S.SlideBody[K],S.Profile.Body[1].Targets[1][K],S.Status.SlideProgress).GetNormalized();return;}
 // The initial deadline includes all three angular caps; curve time only retimes this authored path.
 for(int K=0;K<3;++K)S.Authored.Current[K]=FQuat::Slerp(S.Authored.Entry[K],S.Authored.Destination[K],ReachFraction).GetNormalized();
}
static void PoleFrame(FActive& S,const FQuat& Reference,const FVector& Down)
{
 auto& A=S.Authored;const FVector Direction=Reference.UnrotateVector(S.Pose[S.Arm[2]].GetLocation()-S.Pose[S.Arm[0]].GetLocation()).GetSafeNormal();
 const FVector Carried=A.PoleValid?FVector::VectorPlaneProject(FQuat::FindBetweenNormals(A.PoleDirection,Direction).RotateVector(A.PoleZero),Direction).GetSafeNormal():FVector::ZeroVector;
 FVector Zero=FVector::VectorPlaneProject(Down,Direction);
 if(Zero.Size()<1.e-4){Zero=A.PoleValid?Carried:FVector::VectorPlaneProject(Reference.UnrotateVector(S.Pose[S.Arm[1]].GetLocation()-S.Pose[S.Arm[0]].GetLocation()),Direction);
  if(Zero.Size()<1.e-7)Zero=FVector::VectorPlaneProject(Reference.UnrotateVector(S.Pose[S.Arm[0]].GetRotation().GetAxisY()),Direction);
  if(Zero.Size()<1.e-7)Zero=FVector::VectorPlaneProject(Reference.UnrotateVector(S.Pose[S.Arm[0]].GetRotation().GetAxisZ()),Direction);
 }
 Zero.Normalize();if(A.PoleValid&&FVector::DotProduct(Zero,Carried)<0)Zero=-Zero;
 A.PoleDirection=Direction;A.PoleZero=Zero;A.PoleValid=true;
}
static double PoleTarget(const FActive& S,double Insertion)
{const auto& B=S.Profile.Body[S.Sheathe];return B.Pole[0]+WrappedDegrees(B.Pole[1]-B.Pole[0])*Insertion;}
static void PreparePole(FActive& S)
{
 S.Pose=S.Base;const FQuat Reference=S.Pose[S.Spine[4]].GetRotation();PoleFrame(S,Reference,-FVector::ForwardVector);
 auto& A=S.Authored;const FVector Existing=FVector::VectorPlaneProject(Reference.UnrotateVector(S.Pose[S.Arm[1]].GetLocation()-S.Pose[S.Arm[0]].GetLocation()),A.PoleDirection).GetSafeNormal();
 A.PoleAngle=FMath::RadiansToDegrees(FMath::Atan2(FVector::DotProduct(A.PoleDirection,FVector::CrossProduct(A.PoleZero,Existing)),FVector::DotProduct(A.PoleZero,Existing)));
 A.PoleReachSpeed=FMath::Min(S.Profile.Body[S.Sheathe].PoleSpeed,FMath::Abs(WrappedDegrees(PoleTarget(S,S.Sheathe?0:1)-A.PoleAngle))*60/FMath::Max(1,S.Status.ReachTicks));
}
static void ApplyPole(FActive& S,bool Advance=true)
{
 auto& A=S.Authored;const auto& B=S.Profile.Body[S.Sheathe];FQuat Reference=S.Pose[S.Spine[4]].GetRotation();FVector Down=-FVector::ForwardVector;
 if(S.Sliding&&B.SwordPole){
  const FQuat Sword=(S.Pose[S.Arm[2]].GetRotation()*S.Geometry.Grip.GetRotation()).GetNormalized();
  if(!A.UseSword){PoleFrame(S,Reference,Down);const FQuat Change=(Sword.Inverse()*Reference).GetNormalized();A.PoleDirection=Change.RotateVector(A.PoleDirection);A.PoleZero=Change.RotateVector(A.PoleZero);A.SwordDown=A.PoleZero;A.UseSword=true;}
  Reference=Sword;Down=A.SwordDown;
 }
 PoleFrame(S,Reference,Down);
 if(Advance){const double Target=PoleTarget(S,S.Sliding?S.Status.Insertion:(S.Sheathe?0:1));
  const double Speed=S.Sliding?B.PoleSpeed:A.PoleReachSpeed;A.PoleAngle+=FMath::Clamp(WrappedDegrees(Target-A.PoleAngle),-Speed/60,Speed/60);}
 const int U=S.Arm[0],E=S.Arm[1],H=S.Arm[2];const FVector Origin=S.Pose[U].GetLocation(),Direction=(S.Pose[H].GetLocation()-Origin).GetSafeNormal();
 const FVector Existing=FVector::VectorPlaneProject(S.Pose[E].GetLocation()-Origin,Direction).GetSafeNormal();
 const FVector Wanted=Reference.RotateVector(FQuat(A.PoleDirection,FMath::DegreesToRadians(A.PoleAngle)).RotateVector(A.PoleZero));
 const double Turn=FMath::Atan2(FVector::DotProduct(Direction,FVector::CrossProduct(Existing,Wanted)),FVector::DotProduct(Existing,Wanted));const FQuat Q(Direction,Turn);
 S.Pose[U].SetRotation((Q*S.Pose[U].GetRotation()).GetNormalized());S.Pose[E]=FTransform((Q*S.Pose[E].GetRotation()).GetNormalized(),Origin+Q.RotateVector(S.Pose[E].GetLocation()-Origin));
}
static void SeedEntryInertia(FActive& S,TConstArrayView<FTransform> Before,TConstArrayView<FTransform> Next,double Dt)
{
 auto& A=S.Authored;A.EntryTime=FMath::Min(S.Profile.EntryDuration,double(S.Status.ReachTicks)/60);
 A.EntryAngular.Init(FVector::ZeroVector,S.Base.Num());A.EntryOffset.Init(FVector::ZeroVector,S.Base.Num());
 for(int J:A.InertiaBones){const int P=S.Parents[J];const auto Prev=Before[J].GetRelativeTransform(Before[P]),After=Next[J].GetRelativeTransform(Next[P]);const auto& First=A.Local[J];
  A.EntryAngular[J]=(Log(Prev.GetRotation().Inverse()*First.GetRotation())-Log(First.GetRotation().Inverse()*After.GetRotation()))*(S.Profile.EntryInertia/Dt);
  A.EntryOffset[J]=(Log(FQuat::FindBetweenVectors(Prev.GetLocation(),First.GetLocation()))-Log(FQuat::FindBetweenVectors(First.GetLocation(),After.GetLocation())))*(S.Profile.EntryInertia/Dt);
 }
}
static void ApplyEntryInertia(FActive& S)
{
 const auto& A=S.Authored;const double Time=double(S.Status.Tick)/60;
 if(S.Sliding||A.EntryTime<=0||Time>=A.EntryTime||A.EntryAngular.IsEmpty())return;
 const double Momentum=Time*FMath::Pow(1-Time/A.EntryTime,3);S.Work.SetNum(S.Pose.Num());
 for(int J:S.Upper){const int P=S.Parents[J];S.Work[J]=S.Pose[J].GetRelativeTransform(S.Pose[P]);}
 for(int J:A.InertiaBones){auto& L=S.Work[J];L.SetRotation((L.GetRotation()*Exp(A.EntryAngular[J]*Momentum)).GetNormalized());L.SetTranslation(Exp(A.EntryOffset[J]*Momentum).RotateVector(L.GetLocation()));}
 for(int J:S.Upper)S.Pose[J]=S.Work[J]*S.Pose[S.Parents[J]];
}
