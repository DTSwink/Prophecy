#include "ProphecyFKReturnData.h"
#include "ProphecyAttackRecovery.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDodgeReturnTest,"Prophecy.NN.DefenseReturn.DodgePublication",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDodgeReturnTest::RunTest(const FString&)
{
    using namespace ProphecyUpperBodyInertia;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    TArray<FName> Names,Core;TArray<int32> Parents;TArray<FTransform> Idle;
    Names.Add(TEXT("pelvis"));Parents.Add(INDEX_NONE);Idle.Add(FTransform::Identity);
    for(const auto& D:ProphecyFKReturn::Data::Bones)
    {
        const int32 Parent=Names.IndexOfByKey(FName(D.Parent));Parents.Add(Parent);Names.Add(FName(D.Name));
        Idle.Add(FTransform(FQuat(D.Q[0],D.Q[1],D.Q[2],D.Q[3]).GetNormalized(),FVector(D.P[0],D.P[1],D.P[2]))*Idle[Parent]);
        const FString N(D.Name);if(!N.Contains(TEXT("arm")) && !N.Contains(TEXT("hand")))Core.Add(FName(D.Name));
    }
    Names.Add(TEXT("thigh_l"));Parents.Add(0);Idle.Add(FTransform(FVector(0,15,-5)));
    auto Outgoing=Idle;
    for(int32 I=1;I<Idle.Num()-1;++I)Outgoing[I]=Idle[I]*FTransform(FQuat(FVector::UpVector,.25));
    const FTransform Carrier(FRotator(0,63,0),FVector(123,456,100));
    auto Start=[&]{BeginDodge(A,Names,Parents,Core,Idle,Outgoing,Carrier,Carrier,0,1./30);};
    Start();TestFalse(TEXT("Unconfigured dodge is free of return state"),HasDodgeReturn(A));
    UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,.25,0,.1,1);
    Start();TestTrue(TEXT("Configured dodge activates"),HasDodgeReturn(A));
    ProphecyAttackRecovery::NotifyEnded(A,NAME_None,false,true,EProphecyAgentState::Dodging);
    TestTrue(TEXT("Dodge end event preserves outgoing inertia"),HasDodgeReturn(A));
    auto Prev=Idle,Now=Outgoing,Local=Idle;bool Fresh=false;
    ApplyDodge(A,Names,Parents,Core,Prev,Now,Local,Carrier,0,1./30,FVector2D(30,30),Fresh);
    TestFalse(TEXT("Same publication does not integrate"),Fresh);
    for(int32 I=0;I<Idle.Num();++I)TestTrue(TEXT("Captured outgoing endpoint is continuous"),Now[I].Equals(Outgoing[I],1.e-6));
    for(int32 Tick=1;Tick<=8;++Tick)
    {
        FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/120);
        Prev=Idle;Now=Idle;Local=Idle;
        const bool Applied=ApplyDodge(A,Names,Parents,Core,Prev,Now,Local,Carrier,Tick,1./30,FVector2D(30,30),Fresh);
        TestTrue(TEXT("Lower body stays byte-equivalent"),Now[0].Equals(Idle[0],0) && Now.Last().Equals(Idle.Last(),0));
        for(const auto& T:Now)TestFalse(TEXT("Finite output"),T.ContainsNaN());
        if(Tick==1)TestTrue(TEXT("Actual inertial result differs from vanilla"),!Now[1].Equals(Idle[1],1.e-5));
        if(Tick>=6)for(int32 I=0;I<Idle.Num();++I)TestTrue(TEXT("Deadline reaches exact vanilla"),Now[I].Equals(Idle[I],0));
        if(Applied)
        {
            const auto Expected=Now;Prev=Idle;Now=Idle;
            ApplyDodge(A,Names,Parents,Core,Prev,Now,Local,Carrier,Tick,1./30,FVector2D(30,30),Fresh);
            TestFalse(TEXT("Duplicate does not integrate or recommit"),Fresh);
            for(int32 I=0;I<Idle.Num();++I)TestTrue(TEXT("Duplicate restores accepted pose"),Now[I].Equals(Expected[I],1.e-8));
        }
    }
    TestFalse(TEXT("Final interval retires"),HasDodgeReturn(A));
    for(auto Kind:{EProphecyAgentState::Attacking,EProphecyAgentState::Parrying})
    {Start();ProphecyAttackRecovery::NotifyEnded(A,NAME_None,false,true,Kind);TestFalse(TEXT("Other exits cannot retain dodge inertia"),HasDodgeReturn(A));}
    Start();ProphecyAttackRecovery::EnterSpecial(A);TestFalse(TEXT("New special immediately cancels"),HasDodgeReturn(A));
    Start();CaptureReset(A);RestoreReset(A);TestFalse(TEXT("Reset clears running return"),HasDodgeReturn(A));
    Start();UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,false);TestFalse(TEXT("Disable clears return"),HasDodgeReturn(A));
    ProphecyAttackRecovery::Remove(A);Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
