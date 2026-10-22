// Explicit console diagnostic in a transient world; never touches scene bodies.
#include "Engine/Engine.h"
static void VerifyGrabIndependence()
{
    FString Report;int Checks=0,Failures=0;
    auto Check=[&](bool OK,const TCHAR* Name){++Checks;if(!OK){++Failures;Report+=FString(Name)+TEXT("\n");}return OK;};
    const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    if(!World)return;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    auto* W=World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto Run=[&]()
    {
        FProphecyJoltWorldSettings Config;Config.GravityCmPerSecondSquared=FVector::ZeroVector;
        Config.MaxBodies=16;Config.MaxBodyPairs=Config.MaxContactConstraints=128;
        if(!Check(W&&W->InitializeSimulation(Config).IsSuccess(),TEXT("initialize")))return;
        FProphecyJoltFixtureBodySettings Body;Body.CollisionResponses.SetAllChannels(ECR_Ignore);
        FProphecyJoltBodyHandle A,B;
        if(!Check(W->CreateSphere(10,Body,A).IsSuccess()&&W->CreateSphere(10,Body,B).IsSuccess(),TEXT("bodies")))return;
        FProphecyJoltJointSettings Settings;Settings.BodyA=A;Settings.BodyB=B;
        FProphecyJoltJointHandle Joint;
        if(!Check(W->CreateJoint(Settings,{},Joint).IsSuccess(),TEXT("joint")))return;
        // The same joint changes at runtime, including return to ordinary response.
        for(float Alpha:{0.f,.25f,.5f,.75f,1.f,0.f,1.f})
        {
            if(!Check(W->SetJointGrabIndependence(Joint,Alpha).IsSuccess(),TEXT("set alpha")))return;
            float Read=-1;Check(W->GetJointGrabIndependence(Joint,Read).IsSuccess()&&Read==Alpha,TEXT("read alpha"));
            Check(!W->SetJointGrabIndependence(Joint,-.1f).IsSuccess(),TEXT("reject negative"));
            Check(!W->SetJointGrabIndependence(Joint,1.1f).IsSuccess(),TEXT("reject above one"));
            W->SetBodyVelocity(A,FVector::ZeroVector,FVector::ZeroVector,true);
            W->SetBodyVelocity(B,FVector(100,0,0),FVector(0,0,1),true);
            if(!Check(W->Step(1.f/120,1).IsSuccess(),TEXT("step")))return;
            FProphecyJoltBodyState Hand,Object;W->ReadBody(A,Hand);W->ReadBody(B,Object);
            const double Expected=(1.-Alpha)/(2.-Alpha);
            Check(Hand.CenterOfMassVelocityCmPerSecond.Equals(FVector(100*Expected,0,0),.002),TEXT("linear reaction"));
            Check(Hand.AngularVelocityRadiansPerSecond.Equals(FVector(0,0,Expected),.0002),TEXT("angular reaction"));
            Check(Object.CenterOfMassVelocityCmPerSecond.Equals(Hand.CenterOfMassVelocityCmPerSecond,.002),TEXT("object follows"));
        }
        // Reframing a grab must preserve the requested alpha, joint identity and scope.
        Check(W->UpdateJoint(Joint,Settings).IsSuccess(),TEXT("reframe"));
        float Alpha=-1;Check(W->GetJointGrabIndependence(Joint,Alpha).IsSuccess()&&Alpha==1,TEXT("reframe preserves alpha"));
        Check(!W->SetJointPikeWoundCorrection(Joint,true).IsSuccess(),TEXT("pike cannot reinterpret grab"));
        W->SetBodyVelocity(A,FVector(100,0,0),FVector(0,0,1),true);
        Check(W->SetBodyKinematic(B).IsSuccess(),TEXT("target becomes kinematic"));
        W->SetBodyVelocity(B,FVector::ZeroVector,FVector::ZeroVector,true);
        for(int I=0;I<12;++I)Check(W->Step(1.f/120,1).IsSuccess(),TEXT("kinematic step"));
        FProphecyJoltBodyState Hand;W->ReadBody(A,Hand);
        Check(Hand.CenterOfMassVelocityCmPerSecond.IsNearlyZero(.002)&&Hand.AngularVelocityRadiansPerSecond.IsNearlyZero(.0002),TEXT("kinematic target normal reaction"));
        Check(W->DestroyJoint(Joint).IsSuccess(),TEXT("drop"));
        W->SetBodyVelocity(A,FVector::ZeroVector,FVector::ZeroVector,true);
        Check(W->AddPointImpulse(A,FVector(100,0,0),Hand.CenterOfMassPositionCm).IsSuccess(),TEXT("ordinary impulse"));
        W->ReadBody(A,Hand);Check(Hand.CenterOfMassVelocityCmPerSecond.Equals(FVector(100,0,0),.002),TEXT("body mass unchanged"));
        Check(!W->SetJointGrabIndependence(Joint,1).IsSuccess(),TEXT("stale handle rejected"));
        W->DestroyBody(A);W->DestroyBody(B);
        Body.PositionCm=FVector::ZeroVector;Body.Rotation=FQuat::Identity;
        W->CreateSphere(10,Body,A);
        Body.PositionCm=FVector(25,17,8);Body.Rotation=FRotator(20,40,-30).Quaternion();W->CreateSphere(10,Body,B);
        Settings.BodyA=A;Settings.BodyB=B;Settings.FrameA=Settings.FrameB=FTransform(FVector(7,-3,2));
        if(!Check(W->CreateJoint(Settings,{},Joint).IsSuccess()&&W->SetJointGrabIndependence(Joint,1).IsSuccess(),TEXT("displaced grab")))return;
        for(int I=0;I<90;++I)if(!Check(W->Step(1.f/120,1).IsSuccess(),TEXT("correction step")))return;
        FProphecyJoltBodyState Object;W->ReadBody(A,Hand);W->ReadBody(B,Object);
        Check(Hand.PositionCm.IsNearlyZero(.0001)&&Hand.Rotation.Equals(FQuat::Identity,.0001),TEXT("correction leaves hand alone"));
        Check(Object.PositionCm.IsNearlyZero(.01)&&Object.Rotation.Equals(FQuat::Identity,.001),TEXT("object converges"));
        FProphecyJoltBodyHandle C;Body.PositionCm=FVector::ZeroVector;Body.Rotation=FQuat::Identity;Body.bDynamic=false;
        W->CreateSphere(2,Body,C);FProphecyJoltJointSettings Ordinary;Ordinary.BodyA=A;Ordinary.BodyB=C;
        FProphecyJoltJointHandle Other;W->CreateJoint(Ordinary,{},Other);
        W->SetBodyVelocity(A,FVector(100,0,0),FVector(0,1,0),true);
        for(int I=0;I<12;++I)W->Step(1.f/120,1);
        W->ReadBody(A,Hand);
        Check(Hand.CenterOfMassVelocityCmPerSecond.IsNearlyZero(.002)&&Hand.AngularVelocityRadiansPerSecond.IsNearlyZero(.002),TEXT("other joint unchanged"));
    };
    Run();World->DestroyWorld(false);GEngine->DestroyWorldContext(World);World->MarkAsGarbage();
    Report=FString::Printf(TEXT("checks=%d failures=%d\n"),Checks,Failures)+Report;
    FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/GrabIndependence/solver.txt")));
    UE_LOG(LogTemp,Display,TEXT("Grab independence verification: %s"),*Report);
}
