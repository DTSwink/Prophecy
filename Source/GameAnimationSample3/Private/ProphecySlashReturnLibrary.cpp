#include "ProphecySlashReturnLibrary.h"
#include "ProphecySlashReturn.h"
#include "ProphecySlashReturnMath.h"
#include "ProphecyHandChainMath.h"
#include "ProphecyAttackRecovery.h"
#include "ProphecyBlendClock.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#if WITH_EDITOR
#include "HAL/IConsoleManager.h"
#endif

namespace ProphecySlashReturn
{
#if WITH_EDITOR
static TAutoConsoleVariable<int32> AuditReturn(TEXT("Prophecy.SlashReturn.Audit"),0,TEXT("Log active attack-arm return stages for diagnosis."),ECVF_Default);
#endif
using K=ProphecyBlendClock::EKind;
struct FConfig { float Hold=.3f,Blend=.5f,Speed=100; };
struct FReturn { FConfig Config; double Elapsed=0;bool Initialized=false; FTransform Wrist; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FReturn> Returns;
// Event-only selection; retain the old FReturn layout across Live Coding.
static TMap<TWeakObjectPtr<const AProphecyAgent>,int32> ReturnArms;
// Separate versioned sidecar: do not resize the retained FReturn allocation
// while Live Coding. Basis is calibrated to the actual held blade's long axis.
struct FWeaponRoute
{
    FQuat Basis=FQuat::Identity;
    FRotator Rotation=FRotator::ZeroRotator,Goal=FRotator::ZeroRotator;
    double Side=1;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FWeaponRoute> WeaponRoutes;
struct FBladeGeometry { FVector Base=FVector::ZeroVector,Tip=FVector::ZeroVector;double Padding=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FBladeGeometry> Blades;
static FWeaponRoute MakeWeaponRoute(const AProphecyAgent* A,const FTransform& Hand,const FTransform& Neutral,double Width)
{
    FWeaponRoute V;FVector Axis=Neutral.GetRotation().UnrotateVector(FVector::ForwardVector);
    FVector Up=Neutral.GetRotation().UnrotateVector(FVector::UpVector);
    // A held sword belongs to the right hand. Its grip/bounds must never be
    // interpreted as left-hand geometry when returning a left hook/overhead.
    if(const auto* Sword=ActiveArm(A)==1 ? A->GetHeldSword() : nullptr)
    {
        TArray<UStaticMeshComponent*> Meshes;Sword->GetComponents(Meshes);
        for(auto* Mesh:Meshes) if(Mesh && Mesh->GetStaticMesh() && (Mesh->GetFName()==TEXT("sword") || Meshes.Num()==1))
        {
            const FBox B=Mesh->GetStaticMesh()->GetBoundingBox();const FVector Size=B.GetSize();
            const int32 I=Size.X>Size.Y ? (Size.X>Size.Z?0:2) : (Size.Y>Size.Z?1:2);
            FVector P=B.GetCenter(),Q=P;P[I]=B.Min[I];Q[I]=B.Max[I];
            P=A->SwordGripTransform.TransformPosition(P);Q=A->SwordGripTransform.TransformPosition(Q);
            if(P.SizeSquared()>Q.SizeSquared()) Swap(P,Q);
            double Radius=0;
            for(int32 J=0;J<3;++J) if(J!=I) Radius+=FMath::Square(Size[J]*A->SwordGripTransform.GetScale3D()[J]*.5);
            Blades.Add(A,FBladeGeometry{P,Q,FMath::Sqrt(Radius)+1.});
            Axis=(Q-P).GetSafeNormal();Up=A->SwordGripTransform.TransformVectorNoScale(FVector::YAxisVector);break;
        }
    }
    V.Basis=FRotationMatrix::MakeFromXZ(Axis,Up).ToQuat();
    V.Rotation=(Hand.GetRotation()*V.Basis).Rotator();
    V.Side=Hand.GetLocation().Y<=0 ? 1. : -1.;
    const FRotator Idle=(Neutral.GetRotation()*V.Basis).Rotator();
    V.Goal=FRotator(0,DirectedHeading(V.Rotation.Yaw,0,V.Side),Idle.Roll);
    if(const auto* Blade=Blades.Find(A))
    {
        // Decide from the swept blade, not side alone: a blade already pointing
        // forward must not make a needless full revolution on the right flank.
        const double Short=V.Rotation.Yaw+FMath::UnwindDegrees(-V.Rotation.Yaw);
        double BestCost=1.e30,BestYaw=V.Goal.Yaw;
        for(double Goal:{Short,Short+360.,Short-360.})
        {
            if(FMath::Abs(Goal-V.Rotation.Yaw)>360.+1.e-6) continue;
            double Cost=0;
            for(int32 I=1;I<=48;++I)
            {
                const double T=I/48.;FRotator End=V.Goal;End.Yaw=Goal;
                const FTransform P((BlendWeaponRotation(V.Rotation,End,T).Quaternion()*V.Basis.Inverse()).GetNormalized(),
                    FrontPath(Hand.GetLocation(),Neutral.GetLocation(),Width+5.,T));
                Cost+=FMath::Max(0.,1.04-BladeClearance(P,Blade->Base,Blade->Tip,Width,Blade->Padding));
            }
            Cost+=FMath::Abs(Goal-V.Rotation.Yaw)*1.e-5;
            if(Cost<BestCost) {BestCost=Cost;BestYaw=Goal;}
        }
        V.Goal.Yaw=BestYaw;
    }
    return V;
}
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& Map) { for(auto It=Map.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W) It.RemoveCurrent(); };
        Clean(Configs);Clean(Baselines);Clean(Returns);Clean(ReturnArms);Clean(WeaponRoutes);Clean(Blades);
    });
}
bool IsSlash(FName N)
{ return N==TEXT("slashL") || N==TEXT("slashR") || N==TEXT("slashLD") || N==TEXT("slashRD") || N==TEXT("slashLU") || N==TEXT("slashRU"); }
int32 ArmForAttack(FName N)
{
    if(IsSlash(N) || N==TEXT("pike") || N==TEXT("jabR") || N==TEXT("hookR") || N==TEXT("overR")) return 1;
    if(N==TEXT("jabL") || N==TEXT("hookL") || N==TEXT("overL")) return 0;
    return INDEX_NONE;
}
bool Active(const AProphecyAgent* A) { return !Returns.IsEmpty() && Returns.Contains(A); }
int32 ActiveArm(const AProphecyAgent* A)
{
    if(!Active(A)) return INDEX_NONE;
    const int32* Arm=ReturnArms.Find(A);
    return Arm ? *Arm : 1; // A slash already returning when this patch loads.
}
void Cancel(const AProphecyAgent* A)
{ ReturnArms.Remove(A);Blades.Remove(A);WeaponRoutes.Remove(A);if(Returns.Remove(A)) ProphecyBlendClock::Stop(A,K::SlashReturn); }
void Begin(const AProphecyAgent* A,FName Attack)
{
    Cancel(A);const int32 Arm=ArmForAttack(Attack);if(Arm==INDEX_NONE) return;
    if(const auto* C=Configs.Find(A))
    { Returns.Add(A,FReturn{*C});ReturnArms.Add(A,Arm);ProphecyBlendClock::Start(A,K::SlashReturn,double(C->Hold)+C->Blend); }
}
void Remove(const AProphecyAgent* A) { Cancel(A);Configs.Remove(A);Baselines.Remove(A); }
void CaptureReset(const AProphecyAgent* A)
{ EnsureCleanup();if(const auto* C=Configs.Find(A)) Baselines.Add(A,*C);else Baselines.Remove(A); }
void RestoreReset(const AProphecyAgent* A)
{ Cancel(A);Configs.Remove(A);if(const auto* C=Baselines.Find(A)) Configs.Add(A,*C); }
void ForgetReset(const AProphecyAgent* A) { Baselines.Remove(A); }
void ApplyPose(const AProphecyAgent* A,const FTransform& Torso,const FTransform& PreviousTorso,
    double HalfWidth,const FTransform& PreviousShoulder,const FTransform& PreviousElbow,
    const FTransform& PreviousWrist,const FTransform& NeutralShoulder,
    const FTransform& NeutralElbow,const FTransform& NeutralWrist,const FTransform& InitialNeutralWrist,
    FTransform& Shoulder,FTransform& Elbow,FTransform& Wrist,const FVector& LocalPole)
{
    auto* R=Returns.Find(A);if(!R) return;
    const double Dt=ProphecyBlendClock::Consume(A,K::SlashReturn);R->Elapsed+=Dt;
    const double T=R->Elapsed+1.e-8<R->Config.Hold ? 0. : R->Config.Blend>0
        ? FMath::Clamp((R->Elapsed-R->Config.Hold)/R->Config.Blend,0.,1.) : 1.;
    // At the exact endpoint use the ordinary NN pose, including its source and
    // tempering controls. No residual controller or extra policy evaluation.
    if(R->Elapsed+1.e-8>=double(R->Config.Hold)+R->Config.Blend) { Cancel(A);return; }
    if(!R->Initialized)
    {
        R->Initialized=true;R->Wrist=PreviousWrist.GetRelativeTransform(PreviousTorso);
        // Capture once from the outgoing pose and idle mounted on that SAME
        // clavicle. Config.Speed is a per-return copy, not the saved setting.
        // Later torso/target motion must not recalculate or compound this scale.
        R->Config.Speed*=float(FVector::Distance(PreviousWrist.GetLocation(),InitialNeutralWrist.GetLocation())/100.);
    }
    const FTransform Neutral=NeutralWrist.GetRelativeTransform(Torso);
    auto* Weapon=WeaponRoutes.Find(A);
    if(!Weapon) Weapon=&WeaponRoutes.Add(A,MakeWeaponRoute(A,R->Wrist,Neutral,HalfWidth));
    const double RouteWidth=HalfWidth+5.;
    const double Step=Advance(R->Wrist.GetLocation(),Neutral.GetLocation(),RouteWidth,R->Config.Speed*Dt,Dt);
    const double RotationStep=1.-FMath::Exp(-R->Config.Speed*Dt/25.);
    R->Wrist.SetLocation(FrontPath(R->Wrist.GetLocation(),Neutral.GetLocation(),RouteWidth,Step));
    // Share route progress: the blade cannot race ahead of its wrist around
    // the body. Bound winding so publication's quaternion interpolation agrees.
    const double YawStep=FMath::Min(Step,120./FMath::Max(1.e-6,FMath::Abs(Weapon->Goal.Yaw-Weapon->Rotation.Yaw)));
    Weapon->Rotation=BlendWeaponRotation(Weapon->Rotation,Weapon->Goal,YawStep);
    R->Wrist.SetRotation((Weapon->Rotation.Quaternion()*Weapon->Basis.Inverse()).GetNormalized());
    const double Alpha=T*T*(3-2*T);
    const FTransform NN=Wrist.GetRelativeTransform(Torso);
    FRotator NNRotation=(NN.GetRotation()*Weapon->Basis).Rotator();
    NNRotation.Yaw=Weapon->Goal.Yaw+FMath::UnwindDegrees(NNRotation.Yaw-Weapon->Goal.Yaw);
    const FQuat Rotation=(BlendWeaponRotation(Weapon->Rotation,NNRotation,Alpha).Quaternion()*Weapon->Basis.Inverse()).GetNormalized();
    FTransform LocalTarget(Rotation,FrontPath(R->Wrist.GetLocation(),NN.GetLocation(),RouteWidth,Alpha));
#if WITH_EDITOR
    const FVector BeforeClear=LocalTarget.GetLocation();
#endif
    if(const auto* Blade=Blades.Find(A))
        LocalTarget.SetLocation(ClearBladePosition(LocalTarget,Blade->Base,Blade->Tip,HalfWidth,Blade->Padding));
    const FTransform Target=LocalTarget*Torso;
    auto Carry=[&](const FTransform& V) { return V.GetRelativeTransform(PreviousTorso)*Torso; };
    const FVector LocalUpper=Shoulder.GetRotation().UnrotateVector(Elbow.GetLocation()-Shoulder.GetLocation());
    FTransform GuideShoulder=Shoulder,GuideElbow=Elbow,GuideWrist=Wrist;
    // Fade the hinge guidance to NN together with ownership. Prior hinge comes
    // from accepted/rebased state, so torso motion and root snaps cannot orbit it.
    ProphecyHandChain::Resolve(NeutralShoulder,NeutralElbow,NeutralWrist,
        GuideShoulder,GuideElbow,GuideWrist,Target,LocalUpper,LocalPole,Alpha);
    ProphecyHandChain::Resolve(Carry(PreviousShoulder),Carry(PreviousElbow),Carry(PreviousWrist),
        GuideShoulder,GuideElbow,GuideWrist,Target,LocalUpper,LocalPole,
        FMath::Lerp(RotationStep,1.,Alpha));
    const FVector S=Torso.InverseTransformPosition(GuideShoulder.GetLocation());
    const FVector E=Torso.InverseTransformPosition(GuideElbow.GetLocation());
    const FVector H=Torso.InverseTransformPosition(GuideWrist.GetLocation());
    const double Turn=ClearElbowAngle(S,E,H,HalfWidth,Dt);
    if(Turn!=0)
    {
        const FQuat Q((GuideWrist.GetLocation()-GuideShoulder.GetLocation()).GetSafeNormal(),Turn);
        GuideElbow.SetLocation(GuideShoulder.GetLocation()+Q.RotateVector(GuideElbow.GetLocation()-GuideShoulder.GetLocation()));
        GuideShoulder.SetRotation((Q*GuideShoulder.GetRotation()).GetNormalized());
        GuideElbow.SetRotation((Q*GuideElbow.GetRotation()).GetNormalized());
    }
    Shoulder=GuideShoulder;Elbow=GuideElbow;Wrist=GuideWrist;
#if WITH_EDITOR
    if(const auto* Audit=IConsoleManager::Get().FindConsoleVariable(TEXT("Prophecy.SlashReturn.Audit"));Audit && Audit->GetInt())
    {
        auto V=[](const FVector& P){return FString::Printf(TEXT("%.6f,%.6f,%.6f"),P.X,P.Y,P.Z);};
        auto Transform=[&](const FTransform& P) { const FTransform L=P.GetRelativeTransform(Torso);const FQuat Q=L.GetRotation();
            return V(L.GetLocation())+FString::Printf(TEXT(",%.9f,%.9f,%.9f,%.9f"),Q.X,Q.Y,Q.Z,Q.W); };
        UE_LOG(LogTemp,Display,TEXT("SlashElbowAudit,%s,%.6f,%.6f,%.6f,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s"),
            *A->GetName(),R->Elapsed,Alpha,Turn,*V(LocalUpper),*V(LocalPole),
            *Transform(Carry(PreviousShoulder)),*Transform(Carry(PreviousElbow)),*Transform(Carry(PreviousWrist)),
            *Transform(NeutralShoulder),*Transform(NeutralElbow),*Transform(NeutralWrist),*V(E),*V(H));
        UE_LOG(LogTemp,Display,TEXT("SlashReturnAudit,%s,%.6f,%.6f,%.6f,%.6f,%.6f,%s,%s,%s,%s,%s,%s,%s,%.6f,%.6f,%.6f"),
            *A->GetName(),R->Elapsed,Dt,Step,Alpha,HalfWidth,
            *V(R->Wrist.GetLocation()),*V(Neutral.GetLocation()),*V(NN.GetLocation()),*V(BeforeClear),
            *V(LocalTarget.GetLocation()),*V(Torso.InverseTransformPosition(Wrist.GetLocation())),
            *V(S),LocalUpper.Length(),(GuideWrist.GetLocation()-GuideElbow.GetLocation()).Length(),R->Config.Speed);
    }
#endif
}
}
bool UProphecySlashReturnLibrary::SetSlashRightArmReturnToNeutral(AProphecyAgent* A,bool Enabled,float Hold,float Blend,float Speed)
{
    using namespace ProphecySlashReturn;
    if(!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed() || !A->GetWorld() || A->GetWorld()->bIsTearingDown ||
        !FMath::IsFinite(Hold) || !FMath::IsFinite(Blend) || !FMath::IsFinite(Speed) || Hold<0 || Blend<0 || Speed<0) return false;
    EnsureCleanup();
    if(Enabled && Hold+Blend>0) if(const auto* Existing=Configs.Find(A))
        if(Existing->Hold==Hold && Existing->Blend==Blend && Existing->Speed==Speed) return true;
    Cancel(A);
    if(Enabled && Hold+Blend>0) Configs.Add(A,FConfig{Hold,Blend,Speed});else Configs.Remove(A);
    if(ProphecyAttackRecovery::IsEndEvent(A)) Begin(A,ProphecyAttackRecovery::EndEventAttack(A));
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySlashReturnTest,"Prophecy.NN.SlashReturn.RouteAndLifecycle",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySlashReturnTest::RunTest(const FString&)
{
    using namespace ProphecySlashReturn;using L=UProphecySlashReturnLibrary;
    for(const TCHAR* Name:{TEXT("slashL"),TEXT("slashR"),TEXT("slashLD"),TEXT("slashRD"),TEXT("slashLU"),TEXT("slashRU")})
    {
        TestTrue(TEXT("All six slash names"),IsSlash(FName(Name)));
        TestEqual(TEXT("All slash directions return the sword arm"),ArmForAttack(FName(Name)),1);
    }
    for(const TCHAR* Name:{TEXT("pike"),TEXT("kickL"),TEXT("hookR"),TEXT("jabL"),TEXT("overR")})
        TestFalse(TEXT("Non-slash classification stays strict"),IsSlash(FName(Name)));
    for(const TCHAR* Name:{TEXT("jabL"),TEXT("hookL"),TEXT("overL")})
        TestEqual(TEXT("Left jab/hook/over selects left arm"),ArmForAttack(FName(Name)),0);
    for(const TCHAR* Name:{TEXT("jabR"),TEXT("hookR"),TEXT("overR"),TEXT("pike")})
        TestEqual(TEXT("Right jab/hook/over and pike select right arm"),ArmForAttack(FName(Name)),1);
    for(const TCHAR* Name:{TEXT("kickL"),TEXT("kickR"),TEXT("headbutt"),TEXT("dodge"),TEXT("parry"),TEXT("")})
        TestEqual(TEXT("Other attacks and defense have no return arm"),ArmForAttack(FName(Name)),INDEX_NONE);
    const FVector From(-3,-25,0),To(-3,25,-30);
    for(int32 I=0;I<=100;++I)
    {
        const FVector V=FrontPath(From,To,17,I/100.);
        if(FMath::Abs(V.Y)<17) TestTrue(TEXT("Cross-body route is in front, not through torso or behind it"),V.X>=15.3);
        const FVector Mirrored=FrontPath(From*FVector(1,-1,1),To*FVector(1,-1,1),17,I/100.);
        TestTrue(TEXT("Left-hand route mirrors around the front of the same torso"),Mirrored.Equals(V*FVector(1,-1,1),1.e-9));
    }
    FVector P=From;
    for(int32 I=0;I<600;++I)
    {
        const FVector Next=FrontPath(P,To,17,Advance(P,To,17,100./60,1./60));
        TestTrue(TEXT("Route respects speed bound"),(Next-P).Length()<=100./60+1.e-6);P=Next;
    }
    TestTrue(TEXT("Route reaches destination"),P.Equals(To,1.e-5));
    TestTrue(TEXT("Zero speed holds"),FrontPath(From,To,17,Advance(From,To,17,0,1./60))==From);
    TestEqual(TEXT("Left-side sketch takes clockwise long turn"),DirectedHeading(135,0,1),360.);
    TestEqual(TEXT("Right-side mirrored sketch takes opposite long turn"),DirectedHeading(-135,0,-1),-360.);
    double LongClear=1.e6,ShortClear=1.e6;
    for(int32 I=0;I<=100;++I)
    {
        const FVector Grip(-20,-25,-20);
        const double T=I/100.;
        const FVector Safe=FRotator(0,FMath::Lerp(135.,360.,T),0).Vector();
        const FVector Unsafe=FRotator(0,FMath::Lerp(135.,0.,T),0).Vector();
        LongClear=FMath::Min(LongClear,TorsoSegmentClearance(Grip,Grip+Safe*110.,17));
        ShortClear=FMath::Min(ShortClear,TorsoSegmentClearance(Grip,Grip+Unsafe*110.,17));
    }
    TestTrue(TEXT("Full blade clears on long winding while shortest rotation crosses torso"),LongClear>1 && ShortClear<1);
    {
    const FVector S(0,17,0),H(26.88,-.14,-22.35);FVector E(8.72,5.17,-20.28);
    const double Upper=(E-S).Length(),Lower=(H-E).Length();
    for(int32 I=0;I<30;++I)
    {
        const double Turn=ClearElbowAngle(S,E,H,17,1./60);
        TestTrue(TEXT("Bounded continuous elbow escape"),FMath::Abs(Turn)<=8./60+1.e-9);
        E=S+FQuat((H-S).GetSafeNormal(),Turn).RotateVector(E-S);
        TestTrue(TEXT("Avoidance keeps both lengths and fixed wrist"),FMath::IsNearlyEqual((E-S).Length(),Upper,1.e-7) && FMath::IsNearlyEqual((H-E).Length(),Lower,1.e-7));
    }
    TestTrue(TEXT("Half-slash inward elbow clears both arm segments"),
        TorsoSegmentClearance(S,E,17)>=1.02-1.e-6 && TorsoSegmentClearance(E,H,17)>=1.02-1.e-6);
    }
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A) return false;
    for(float FPS:{30.f,60.f,120.f})
    {
        TestTrue(TEXT("Configure"),L::SetSlashRightArmReturnToNeutral(A,true,.5,1,100));CaptureReset(A);
        Begin(A,TEXT("kickL"));TestFalse(TEXT("Kick never starts"),Active(A));
        Begin(A,TEXT("slashL"));TestTrue(TEXT("Slash starts"),Active(A));
        FTransform S(FVector(0,17,0)),E(FVector(15,25,-15)),H(FVector(10,22,-35));
        const FTransform PS=S,PE=E,PH=H;
        for(int32 Tick=1;Tick<=90;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
            ApplyPose(A,FTransform::Identity,FTransform::Identity,17,PS,PE,PH,PS,PE,PH,PH,S,E,H,FVector::UpVector);
            if(Tick==30) TestTrue(TEXT("Hold consumes precisely 30 ticks"),Active(A) && FMath::IsNearlyEqual(Returns.FindChecked(A).Elapsed,.5,1.e-6));
            TestFalse(TEXT("Finite valid pose"),S.ContainsNaN() || E.ContainsNaN() || H.ContainsNaN());
        }
        TestFalse(TEXT("90 ticks retire regardless of FPS"),Active(A));
        Begin(A,TEXT("slashRU"));Cancel(A);TestFalse(TEXT("New special cancels"),Active(A));
        L::SetSlashRightArmReturnToNeutral(A,false,0,0,0);RestoreReset(A);Begin(A,TEXT("slashLD"));
        TestTrue(TEXT("Reset restores saved config"),Active(A));
        RestoreReset(A);TestFalse(TEXT("Reset cancels active return"),Active(A));
        L::SetSlashRightArmReturnToNeutral(A,true,0,0,100);Begin(A,TEXT("slashR"));
        TestFalse(TEXT("Zero times retain no active work"),Active(A));
        L::SetSlashRightArmReturnToNeutral(A,true,.25f,0,100);Begin(A,TEXT("slashR"));
        for(int32 Tick=1;Tick<=15;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
            ApplyPose(A,FTransform::Identity,FTransform::Identity,17,PS,PE,PH,PS,PE,PH,PH,S,E,H,FVector::UpVector);
            TestTrue(TEXT("Hold-only arm return retains ownership until tick15 then retires"),Active(A)==(Tick<15));
        }
    }
    {
        const FTransform PS(FVector(0,17,0)),PE(FVector(15,25,-15)),PH(FVector(10,22,-35));
        auto ApplyAt=[&](double Distance)
        {
            FTransform S=PS,E=PE,H=PH,Idle=PH;Idle.AddToTranslation(FVector(Distance,0,0));
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/120);
            ApplyPose(A,FTransform::Identity,FTransform::Identity,17,PS,PE,PH,PS,PE,Idle,Idle,S,E,H,FVector::UpVector);
        };
        L::SetSlashRightArmReturnToNeutral(A,true,.5,1,300);
        Begin(A,TEXT("slashR"));ApplyAt(20);
        TestEqual(TEXT("20cm initial distance scales reference speed300 to60"),Returns.FindChecked(A).Config.Speed,60.f);
        ApplyAt(80);
        TestEqual(TEXT("Later target distance does not change captured speed"),Returns.FindChecked(A).Config.Speed,60.f);
        TestEqual(TEXT("Configured speed is never scaled in place"),Configs.FindChecked(A).Speed,300.f);
        Begin(A,TEXT("slashL"));ApplyAt(80);
        TestEqual(TEXT("Next return captures its own80cm distance"),Returns.FindChecked(A).Config.Speed,240.f);
        Begin(A,TEXT("slashRU"));ApplyAt(0);ApplyAt(80);
        TestEqual(TEXT("Initially idle retains zero positional speed even if goal later moves"),Returns.FindChecked(A).Config.Speed,0.f);
    }
    for(float FPS:{30.f,60.f,120.f}) for(const TCHAR* Name:{TEXT("jabL"),TEXT("jabR"),TEXT("hookL"),TEXT("hookR"),TEXT("overL"),TEXT("overR"),TEXT("pike")})
    {
        const int32 Arm=ArmForAttack(FName(Name));const double Side=Arm==0?-1.:1.;
        L::SetSlashRightArmReturnToNeutral(A,true,.1f,.1f,100);
        Begin(A,FName(Name));TestEqual(TEXT("Eligible return latches the proper hand"),ActiveArm(A),Arm);
        const FTransform PS(FVector(0,Side*17,0)),PE(FVector(15,Side*25,-15)),PH(FVector(10,Side*22,-35));
        FTransform Idle=PH;Idle.AddToTranslation(FVector(20,0,0));
        for(int32 Tick=1;Tick<=12;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
            FTransform S=PS,E=PE,H=PH;
            ApplyPose(A,FTransform::Identity,FTransform::Identity,17,PS,PE,PH,PS,PE,Idle,Idle,S,E,H,FVector::UpVector);
            TestFalse(TEXT("Both-handed returns have finite connected targets"),S.ContainsNaN()||E.ContainsNaN()||H.ContainsNaN());
            if(Tick<12)TestEqual(TEXT("Arm selection survives the hold and blend"),ActiveArm(A),Arm);
        }
        TestFalse(TEXT("Eligible return retires after 12 ticks at every FPS"),Active(A));
        TestFalse(TEXT("No arm-selection sidecar remains after retirement"),ReturnArms.Contains(A));
        Begin(A,FName(Name));Cancel(A);TestEqual(TEXT("New special cancels either arm"),ActiveArm(A),INDEX_NONE);
        L::SetSlashRightArmReturnToNeutral(A,false,.1f,.1f,100);Begin(A,FName(Name));
        TestFalse(TEXT("Disabled eligible return performs no work"),Active(A));
    }
    AddInfo(TEXT("AttackArmReturn: six sword-arm slashes, pike, six sided jab/hook/over returns, front-route mirror and 12-tick retirement at 30/60/120 FPS verified."));
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
