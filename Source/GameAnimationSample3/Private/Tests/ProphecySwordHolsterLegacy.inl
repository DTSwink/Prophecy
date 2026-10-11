// Generic reference kernels. Body semantics track the accepted unlimited spine;
// the old head/lifecycle below remain historical performance baselines only.
// Lifecycle uses the current shared reach-continuity staging.
// Included only by development automation tests, never gameplay.
static void LegacyBodyPose(const FActive& S,TConstArrayView<FTransform> Base,FVector V,TArray<FTransform>& Out,bool ShoulderOnly=false)
{
 Out.SetNum(Base.Num());if(ShoulderOnly)Out[S.Pelvis]=Base[S.Pelvis];else for(int I=0;I<Base.Num();++I)Out[I]=Base[I];const FQuat Top=Base[S.Spine[4]].GetRotation();const FVector WorldAxis=Top.RotateVector(S.SpineAxis);const FQuat Swing=Exp(S.ClavU*V.Y+S.ClavV*V.Z);
 auto Bone=[&](int J){const int P=S.Parents[J];const FQuat Carry=(Out[P].GetRotation()*Base[P].GetRotation().Inverse()).GetNormalized();FQuat Q=(Carry*Base[J].GetRotation()).GetNormalized();
  for(int K=0;K<5;++K)if(J==S.Spine[K])Q=(Exp(WorldAxis*(V.X*(K+1)/5.))*Base[J].GetRotation()).GetNormalized();
  if(J==S.Clav)Q=(Q*Swing).GetNormalized();Out[J]=FTransform(Q,Out[P].GetLocation()+Carry.RotateVector(Base[J].GetLocation()-Base[P].GetLocation()));};
 if(ShoulderOnly){for(int J:S.Spine)Bone(J);Bone(S.Clav);Bone(S.Arm[0]);}else for(int J:S.Upper)Bone(J);
}
static FVector LegacyBounded(FVector V,double Limit)
{V.X=FMath::Clamp(V.X,-Limit,Limit);const double L=FMath::Sqrt(V.Y*V.Y+V.Z*V.Z);if(L>Limit){V.Y*=Limit/L;V.Z*=Limit/L;}return V;}
static FVector LegacyOptimize(FActive& S)
{
 const double Limit=FMath::DegreesToRadians(S.Profile.AngleLimit);TArray<FTransform> Scratch;Scratch.Reserve(S.Base.Num());
 auto Score=[&](FVector V){LegacyBodyPose(S,S.Base,V,Scratch,true);return FVector::DistSquared(Scratch[S.Arm[0]].GetLocation(),S.Clear.GetLocation());};
 auto LimitSwing=[&](FVector V){const double Twist=V.X;V=LegacyBounded(V,Limit);V.X=Twist;return V;};
 FVector Best=LimitSwing(S.Desired);double Cost=Score(Best);if(Score(FVector::ZeroVector)<Cost){Best=FVector::ZeroVector;Cost=Score(Best);}
 for(double Degrees:{16.,8.,4.,2.,1.,.5,.125,.03125})for(int Sweep=0;Sweep<4;++Sweep){bool Improved=false;
  for(int K=0;K<3;++K)for(double Sign:{-1.,1.}){FVector V=Best;V[K]+=Sign*FMath::DegreesToRadians(Degrees);V=LimitSwing(V);const double C=Score(V);if(C<Cost-1.e-9){Best=V;Cost=C;Improved=true;}}
  if(!Improved)break;
 }return Best;
}
static void LegacyCaptureArm(const FActive& S,TConstArrayView<FTransform> Pose,FTransform (&Out)[3])
{for(int K=0;K<3;++K)Out[K]=Pose[S.Arm[K]].GetRelativeTransform(Pose[S.Parents[S.Arm[K]]]);}
static void LegacyApplyArm(const FActive& S,TArray<FTransform>& Pose,const FTransform (&Local)[3])
{
 for(int K=0;K<3;++K){const int J=S.Arm[K],P=S.Parents[J];const FVector Original=Pose[J].GetLocation();FTransform L=Local[K];
  if(K>0)L.SetTranslation(L.GetLocation().GetSafeNormal()*FVector::Distance(S.Base[J].GetLocation(),S.Base[P].GetLocation()));
  Pose[J]=L*Pose[P];if(K==0)Pose[J].SetTranslation(Original);}
}
static void LegacySolve(FActive& S,TArray<FTransform>& P,const FTransform& LegacyGoal)
{
 const int A=S.Arm[0],B=S.Arm[1],C=S.Arm[2];const FVector X=P[A].GetLocation(),Y=P[B].GetLocation(),Z=P[C].GetLocation();
 const double L1=(Y-X).Size(),L2=(Z-Y).Size();const FVector D=(LegacyGoal.GetLocation()-X).GetSafeNormal(SMALL_NUMBER,FVector::ForwardVector);
 const double L=FMath::Clamp((LegacyGoal.GetLocation()-X).Size(),FMath::Abs(L1-L2)+.001,L1+L2-.001),Along=(L1*L1+L*L-L2*L2)/(2*L);
 FVector Pole=FVector::VectorPlaneProject(Y-X,D).GetSafeNormal();if(Pole.IsNearlyZero())Pole=FVector::CrossProduct(D,FMath::Abs(D.Z)<.9?FVector::UpVector:FVector::RightVector).GetSafeNormal();
 const FVector E=X+D*Along+Pole*FMath::Sqrt(FMath::Max(0.,L1*L1-Along*Along)),H=X+D*L;
 P[A].SetRotation((FQuat::FindBetweenVectors(Y-X,E-X)*P[A].GetRotation()).GetNormalized());P[B]=FTransform((FQuat::FindBetweenVectors(Z-Y,H-E)*P[B].GetRotation()).GetNormalized(),E);P[C]=FTransform(LegacyGoal.GetRotation(),H);
}
static double LegacyArmDuration(const FTransform (&A)[3],const FTransform (&B)[3],double Linear,double Angular)
{
 FTransform Last[3],PrevLocal[3];for(int J=0;J<3;++J){PrevLocal[J]=A[J];FTransform L=A[J];if(!J)L.SetTranslation(FVector::ZeroVector);Last[J]=J?L*Last[J-1]:L;}
 double Seconds=1./60.;for(int I=1;I<=96;++I){FTransform Pose[3],Local[3];for(int J=0;J<3;++J){Local[J]=Blend(A[J],B[J],Ease(I/96.));FTransform L=Local[J];if(!J)L.SetTranslation(FVector::ZeroVector);Pose[J]=J?L*Pose[J-1]:L;
  Seconds=FMath::Max(Seconds,Angle(PrevLocal[J].GetRotation(),Local[J].GetRotation())*96/Angular);}
  Seconds=FMath::Max3(Seconds,FVector::Distance(Pose[2].GetLocation(),Last[2].GetLocation())*96/Linear,Angle(Last[2].GetRotation(),Pose[2].GetRotation())*96/Angular);
  for(int J=0;J<3;++J){Last[J]=Pose[J];PrevLocal[J]=Local[J];}
 }return Seconds*1.002;
}
static FTransform LegacyGoal(const FActive& S,double Progress)
{return FTransform(S.Seat.GetRotation(),FMath::Lerp(S.Clear.GetLocation(),S.Seat.GetLocation(),S.Sheathe?Progress:1-Progress));}
static void LegacyEndpoint(FActive& S,FVector Body,const FTransform& Target,const FTransform (&Seed)[3],FTransform (&Out)[3])
{
 LegacyBodyPose(S,S.Base,Body,S.Work);LegacyApplyArm(S,S.Work,Seed);LegacySolve(S,S.Work,Target);LegacyCaptureArm(S,S.Work,Out);
}
static void LegacyHeadPose(FActive& S,const TArray<FTransform>& Input,FQuat Q,TArray<FTransform>& Out)
{
 Out=Input;const FQuat Correction=(Q*Input[S.Neck[2]].GetRotation().Inverse()).GetNormalized();
 for(int K=0;K<3;++K){const int J=S.Neck[K],P=S.Parents[J];const FQuat Carry=(Out[P].GetRotation()*Input[P].GetRotation().Inverse()).GetNormalized();
  Out[J]=FTransform((FQuat::Slerp(FQuat::Identity,Correction,(K+1)/3.)*Input[J].GetRotation()).GetNormalized(),Out[P].GetLocation()+Carry.RotateVector(Input[J].GetLocation()-Input[P].GetLocation()));}
}
static void LegacyHeadStep(FActive& S)
{
 const bool Out=S.Sliding&&S.Status.SlideProgress>=(S.Sheathe?S.Profile.SheatheHeadOut:S.Profile.DrawHeadOut)-1.e-8;
 if(Out!=S.HeadOut){S.HeadOut=Out;S.HeadStart=S.Head;S.HeadStartTick=S.Status.Tick-1;S.HeadDuration=-1;}
 const double Speed=Out?S.Profile.HeadOutSpeed:S.Profile.HeadInSpeed,Exponent=Out?S.Profile.HeadOutExponent:S.Profile.HeadInExponent;
 const FQuat Previous=S.Head,Forward=S.Base[S.Neck[2]].GetRotation();FQuat Desired=Forward;auto& Temp=S.HeadWork;
 for(int I=0;I<(Out?1:8);++I){LegacyHeadPose(S,S.Pose,S.Head,Temp);const FVector Direction=S.Mouth-Temp[S.Neck[2]].GetLocation();
  Desired=Out||Direction.IsNearlyZero()?Forward:FQuat::Slerp(Forward,(FQuat::FindBetweenVectors(Forward.RotateVector(FVector::RightVector),Direction)*Forward).GetNormalized(),S.Profile.HeadAlpha).GetNormalized();
  FQuat Target=Desired;if(Exponent>1){if(S.HeadDuration<0)S.HeadDuration=FMath::Max(1.,Exponent*Angle(S.HeadStart,Desired)/Speed*60);const double U=Clamp((S.Status.Tick-S.HeadStartTick)/S.HeadDuration),X=FMath::Pow(U,Exponent),Y=FMath::Pow(1-U,Exponent);Target=FQuat::Slerp(S.HeadStart,Desired,X/(X+Y)).GetNormalized();}
  const double D=Angle(Previous,Target);S.Head=FQuat::Slerp(Previous,Target,D>Speed/60?Speed/60/D:1).GetNormalized();
 }
 S.Status.HeadStep=Angle(Previous,S.Head);S.HeadDone=Out&&Angle(S.Head,Desired)<.001;LegacyHeadPose(S,S.Pose,S.Head,Temp);Swap(S.Pose,Temp);
}
static void LegacyBeginReturn(FActive& S)
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
static void LegacyMountReturn(FActive& S,const TArray<FTransform>& Locals)
{
 for(int J:S.Upper){const int P=S.Parents[J];const auto Moving=S.Base[J].GetRelativeTransform(S.Base[P]);const auto& Idle=S.ReturnIdle[J];
  const FQuat Q=(Moving.GetRotation()*Idle.GetRotation().Inverse()*Locals[J].GetRotation()).GetNormalized();
  const FVector V=FQuat::FindBetweenVectors(Idle.GetLocation(),Moving.GetLocation()).RotateVector(Locals[J].GetLocation());S.Pose[J]=FTransform(Q,V)*S.Pose[P];}
}
static void LegacyAdvanceSpring(FActive& S,double Elapsed)
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
static void LegacyReturnStep(FActive& S,double Elapsed)
{
 const auto& R=S.Profile.Return[S.Sheathe];if(!R.Enabled){LegacyMountReturn(S,S.ReturnStart);return;}const double X=Clamp(Elapsed/S.ReturnDuration);if(X>=1){S.Pose=S.Base;return;}
 auto& Locals=S.Work;Locals=S.ReturnStart;
 if(R.Spring&&R.Inertia>0){LegacyAdvanceSpring(S,Elapsed);const double T=Clamp((Elapsed-S.SpringTimes[0])/FMath::Max(1.e-12,S.SpringTimes[1]-S.SpringTimes[0]));for(int J:S.Upper)Locals[J]=Blend(S.SpringFrames[0][J],S.SpringFrames[1][J],T);LegacyMountReturn(S,Locals);return;}
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
 LegacyMountReturn(S,Locals);
}
static void LegacyAdvance(FActive& S,int Steps)
{
 for(int Step=0;Step<Steps;++Step){++S.Status.Tick;S.Before=S.Pose;S.Pose=S.Base;
  if(!S.Sliding&&S.Status.Tick%4==0)S.Desired=LegacyOptimize(S);
  const double ReachFraction=S.Profile.Reach[S.Sheathe].Sample(double(S.Status.Tick)/S.Status.ReachTicks);S.Status.Progress=Ease(ReachFraction);S.Status.ReachDone=S.Status.Tick>=S.Status.ReachTicks;
  S.Status.SlideProgress=S.Sliding?S.Profile.Slide[S.Sheathe].Sample(double(S.Status.Tick-S.SlideStart)/S.Status.SlideTicks):0;
  const double SourceReachTicks=S.Status.Tick>=S.Status.ReachTicks?S.Status.Tick:ReachFraction*S.Status.ReachTicks;
  const FVector Scheduled=LegacyBounded(S.Desired*ReachFraction,FMath::DegreesToRadians(S.Profile.BodySpeed)*SourceReachTicks/60);
  if(!S.Sliding){
   const double PreviousSource=S.Status.Tick-1>=S.Status.ReachTicks?S.Status.Tick-1:S.Profile.Reach[S.Sheathe].Sample(double(S.Status.Tick-1)/S.Status.ReachTicks)*S.Status.ReachTicks;
   const FVector Delta=LegacyBounded(Scheduled-S.Body,FMath::DegreesToRadians(S.Profile.BodySpeed)*FMath::Max(1.,SourceReachTicks-PreviousSource)/60);
   S.Body+=Delta;
  }else S.Body=Scheduled;
  if(S.Sheathe&&S.Sliding){S.Body.Y*=1-S.Status.SlideProgress;S.Body.Z*=1-S.Status.SlideProgress;}
  if(!S.Sheathe&&!S.Sliding)S.Status.ReachDone&=FMath::Max(FMath::Abs(S.Desired.X-S.Body.X),FVector2D(S.Desired.Y-S.Body.Y,S.Desired.Z-S.Body.Z).Size())<FMath::DegreesToRadians(.25);
  LegacyBodyPose(S,S.Base,S.Body,S.Pose);
  // Share current reach staging; the pre-optimization endpoint kernel remains
  // independent. Historical performance receipts predate this continuity fix.
  if(!S.Sliding){ReachArm(S,S.Status.Tick%4==0,[&](FTransform (&Destination)[3]){LegacyEndpoint(S,S.Desired,S.Sheathe?S.Clear:S.Seat,S.SourceArm,Destination);});
  }else if(!S.Status.Returning){
   if(S.Status.Tick==S.SlideStart+1)S.LastGuide=-1;
   const double SourceTick=S.Status.SlideProgress*S.Status.SlideTicks;
   const int Count=FMath::Min(S.Status.SlideTicks,FMath::Max3<int32>(1,FMath::CeilToInt(S.Status.SlideTicks/4.),FMath::CeilToInt(S.SlideLength/2.)));
   int Guide=FMath::Min(Count-1,FMath::FloorToInt(SourceTick*Count/S.Status.SlideTicks));
   while(Guide>0&&FMath::RoundToInt(double(Guide)*S.Status.SlideTicks/Count)>SourceTick)--Guide;
   while(Guide<Count-1&&FMath::RoundToInt(double(Guide+1)*S.Status.SlideTicks/Count)<SourceTick)++Guide;
   const double TickA=FMath::RoundToInt(double(Guide)*S.Status.SlideTicks/Count),TickB=FMath::RoundToInt(double(Guide+1)*S.Status.SlideTicks/Count);
   if(Guide!=S.LastGuide){const double A0=TickA/S.Status.SlideTicks,B0=TickB/S.Status.SlideTicks;FVector BodyA=S.Desired,BodyB=S.Desired;
    if(S.Sheathe){BodyA.Y*=1-A0;BodyA.Z*=1-A0;BodyB.Y*=1-B0;BodyB.Z*=1-B0;}
    LegacyEndpoint(S,BodyA,LegacyGoal(S,A0),S.DestinationArm,S.SlideA);LegacyEndpoint(S,BodyB,LegacyGoal(S,B0),S.SlideA,S.SlideB);S.LastGuide=Guide;}
   const double T=Clamp((SourceTick-TickA)/FMath::Max(1.,TickB-TickA));FTransform L[3];for(int K=0;K<3;++K)L[K]=Blend(S.SlideA[K],S.SlideB[K],T);LegacyApplyArm(S,S.Pose,L);
   if(S.Status.SlideProgress>=1)LegacyBeginReturn(S);
  }
  const double ReturnElapsed=S.Sliding?FMath::Max(0.,double(S.Status.Tick-S.SlideStart-S.Status.SlideTicks)/60):0;
  if(S.Status.Returning&&ReturnElapsed>0)LegacyReturnStep(S,ReturnElapsed);
  S.Status.HandError=FVector::Distance(S.Pose[S.Arm[2]].GetLocation(),(S.Sliding?LegacyGoal(S,S.Status.SlideProgress):S.Sheathe?S.Clear:S.Seat).GetLocation());
  S.Status.Blocked=!S.Sliding&&S.Status.ReachDone&&S.Status.HandError>2;S.LastBody=S.Pose;LegacyHeadStep(S);S.LastBase=S.Base;
  S.Status.Finished=S.Status.Returning&&S.HeadDone&&(!S.Profile.Return[S.Sheathe].Enabled||ReturnElapsed>=S.ReturnDuration);
 }
}
