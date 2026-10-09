#include "ProphecyHalfAttackMount.h"
#include "ProphecyDefenseFeatures.h"
#include "ProphecyDefenseControls.h"
#include "ProphecyNNDefenseLibrary.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "HAL/IConsoleManager.h"
#include "Misc/AutomationTest.h"
static bool VerifyDefenseCombatMath()
{
    int32 Checks=0,Failures=0;
    auto Check=[&](bool Pass,const TCHAR* What){++Checks;if(!Pass){++Failures;UE_LOG(LogTemp,Error,TEXT("DefenseCombatMath: %s"),What);}};
    using namespace ProphecyHalfAttackMount;
    const FVector P(120,-350,90),Up=FVector::UpVector,Forward=FVector::ForwardVector;
    for(double Radius:{0.,.01,15.,30.,45.})for(double Height:{-500.,0.,500.})
    {
        const FVector T=P+FVector(.6*Radius,.8*Radius,Height);
        const auto C=ClampHorizontalReach(T,P,Up,Forward,30);
        Check(FMath::IsNearlyEqual(FVector::DistXY(C,P),FMath::Max(30.,Radius),1.e-7),TEXT("Horizontal radius"));
        Check(C.Z==T.Z,TEXT("Vertical target untouched"));
        Check(ClampHorizontalReach(T,P,Up,Forward,0)==T,TEXT("Zero exact bypass"));
        if(Radius>=30)Check(C==T,TEXT("Outside clamp exact bypass"));
        const FTransform Frame(FRotator(21,78,-33),FVector(500,100,-200));
        Check(ClampHorizontalReach(Frame.TransformPosition(T),Frame.TransformPosition(P),Frame.TransformVectorNoScale(Up),Frame.TransformVectorNoScale(Forward),30).Equals(Frame.TransformPosition(C),1.e-6),TEXT("World horizontal invariant in rotated anchor"));
    }
    using namespace ProphecyDefenseFeatures;
    for(bool Spear:{false,true})
    {
        FContext C;for(int32 F=0;F<2;++F)for(int32 I=0;I<9;++I){C.AttackerPelvis[F][I]=float(F*10+I);C.AttackerCollider[F][I]=float(F*30+I*2);}
        C.AttackControls[5]=Spear?1:0;const FContext Original=C;
        RemoveAttackerHorizontalVelocity(C);
        if(Spear)Check(FMemory::Memcmp(&C,&Original,sizeof(C))==0,TEXT("Spear exact bypass"));
        else
        {
            for(int32 Axis:{0,2})
            {
                Check(C.AttackerPelvis[0][Axis]==C.AttackerPelvis[1][Axis],TEXT("No perceived horizontal pelvis velocity"));
                Check(C.AttackerCollider[1][Axis]-C.AttackerCollider[0][Axis]==20,TEXT("Collider retains relative velocity"));
            }
            for(int32 I=0;I<9;++I)
            {
                Check(C.AttackerPelvis[1][I]==Original.AttackerPelvis[1][I] && C.AttackerCollider[1][I]==Original.AttackerCollider[1][I],TEXT("Current pose unchanged"));
                if(I!=0 && I!=2)Check(C.AttackerPelvis[0][I]==Original.AttackerPelvis[0][I] && C.AttackerCollider[0][I]==Original.AttackerCollider[0][I],TEXT("Height and rotations unchanged"));
            }
        }
    }
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    for(bool Spear:{false,true})for(bool Half:{false,true})for(bool Enabled:{false,true})for(bool UseRoot:{false,true})
    {
        FContext C;for(int F=0;F<2;++F)for(int I=0;I<9;++I){C.AttackerPelvis[F][I]=F*10+I;C.AttackerCollider[F][I]=F*30+I*2;}
        C.AttackControls[5]=Spear?1:0;const FContext Original=C;
        UProphecyNNDefenseLibrary::SetDefenseHalfAttackHorizontalVelocity(A,Enabled,UseRoot);
        const FVector3f PreviousRoot(100,200,300),RootDelta(2,40,-3);
        ProphecyDefenseControls::FilterHalfAttack(A,Half,C,PreviousRoot,PreviousRoot+RootDelta);
        if(Spear || !Half || !Enabled)Check(FMemory::Memcmp(&C,&Original,sizeof(C))==0,TEXT("Disabled/full/spear exact bypass for both modes"));
        else
        {
            for(int Axis:{0,2})
            {
                const float Removed=UseRoot?RootDelta[Axis]:10.f;
                Check(C.AttackerPelvis[1][Axis]-C.AttackerPelvis[0][Axis]==10.f-Removed,TEXT("Root mode retains pelvis relative motion"));
                Check(C.AttackerCollider[1][Axis]-C.AttackerCollider[0][Axis]==30.f-Removed,TEXT("Same root motion removed from collider"));
            }
            for(int I=0;I<9;++I)
            {
                Check(C.AttackerPelvis[1][I]==Original.AttackerPelvis[1][I] && C.AttackerCollider[1][I]==Original.AttackerCollider[1][I],TEXT("Current endpoints unchanged"));
                if(I!=0 && I!=2)Check(C.AttackerPelvis[0][I]==Original.AttackerPelvis[0][I] && C.AttackerCollider[0][I]==Original.AttackerCollider[0][I],TEXT("Vertical/rotation untouched"));
            }
        }
    }
    ProphecyDefenseControls::Remove(A);W->DestroyWorld(false);
    UE_LOG(LogTemp,Display,TEXT("DefenseCombatMath checks=%d failures=%d"),Checks,Failures);return Failures==0;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseCombatMathTest,"Prophecy.NN.Defense.CombatMath",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseCombatMathTest::RunTest(const FString&){return TestTrue(TEXT("Math verification"),VerifyDefenseCombatMath());}
static FAutoConsoleCommand VerifyDefenseCombatMathCommand(TEXT("Prophecy.Defense.VerifyCombatMath"),TEXT("Verify half reach/perception without entering global automation mode."),FConsoleCommandDelegate::CreateLambda([](){VerifyDefenseCombatMath();}));
#endif
