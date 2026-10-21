IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyPikeWoundCorrectionTest,
    "Prophecy.Jolt.Constraints.PikeWoundCorrection", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyPikeWoundCorrectionTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::SceneCollisionTests;
    FWorldFixture Fixture;
    if (!Fixture.World) return false;
    Fixture.World->InitializeActorsForPlay(FURL());
    FString Error;
    if (!UProphecyJoltBlueprintLibrary::InitializeJoltWorld(Fixture.World, Error, 32, 0)) { AddError(Error); return false; }
    auto* Asset = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    auto* Native = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto* Wound = AddMesh(Fixture, *Asset, FTransform(FVector(0,0,500)), false);
    UPhysicsConstraintComponent* Constraints[2];
    UProphecyJoltBodyComponent* Adapters[2];
    for (int32 I=0; I<2; ++I)
    {
        const FVector Position(150+300*I,0,500);
        auto* Sword = AddMesh(Fixture, *Asset, FTransform(FQuat::Identity,Position,FVector(.8,.7,1.3)), true);
        auto* Actor = Fixture.SpawnActor();
        auto* C = NewObject<UPhysicsConstraintComponent>(Actor, NAME_None, RF_Transient);
        Actor->AddInstanceComponent(C);Actor->SetRootComponent(C);
        C->SetWorldTransform(FTransform(FRotator(20,35,10),Position+FVector(3,4,80)));C->RegisterComponent();
        C->SetDisableCollision(true);
        C->SetLinearXLimit(LCM_Locked,0);C->SetLinearYLimit(LCM_Locked,0);C->SetLinearZLimit(LCM_Limited,200);
        C->SetAngularTwistLimit(ACM_Locked,0);C->SetAngularSwing1Limit(ACM_Locked,0);C->SetAngularSwing2Limit(ACM_Locked,0);
        C->SetConstrainedComponents(Wound,NAME_None,Sword,NAME_None);
        Constraints[I]=C;
        auto* Adapter=NewObject<UProphecyJoltBodyComponent>(Sword->GetOwner());
        Sword->GetOwner()->AddInstanceComponent(Adapter);Adapter->bAutomaticStep=false;Adapter->RegisterComponent();
        if (!Adapter->EnableBody(*Sword,Error)) {AddError(Error);return false;}
        Adapters[I]=Adapter;
    }
    auto* SceneActor=Fixture.SpawnActor();
    auto* Scene=NewObject<UProphecyJoltSceneCollisionComponent>(SceneActor);
    SceneActor->AddInstanceComponent(Scene);Scene->bAutomaticScenePhysics=false;Scene->RegisterComponent();
    if (!Scene->EnableSceneCollision(Error)||!Adapters[0]->StepAndPublish(1.f/60,Error)) {AddError(Error);return false;}
    FProphecyJoltJointSettings Settings[2];
    FProphecyJoltBodyState Before[2],After[2];
    for(int32 I=0;I<2;++I)
    {
        FProphecyJoltJointHandle Joint;
        if(!ProphecyJolt::Constraints::GetJoint(Constraints[I],Joint,Error)||!Native->ReadJoint(Joint,Settings[I]).IsSuccess())return false;
        Native->ReadBody(Settings[I].BodyA,Before[I]);
        const FQuat Rotation=FRotator(10,20,30).Quaternion();
        TestTrue(TEXT("Perturb native sword"),Native->SetBodyPose(Settings[I].BodyA,FTransform(Rotation,Before[I].PositionCm+FVector(4,7,9))).IsSuccess());
        Adapters[I]->SetBodyVelocity(FVector(20,30,40),FVector(.2,.3,.4),true,Error);
        Native->ReadBody(Settings[I].BodyA,Before[I]);
    }
    using Library=UProphecyPhysicsConstraintBlueprintLibrary;
    TestFalse(TEXT("Null constraint rejected"),Library::SetPikeWoundCorrection(nullptr,true));
    TestTrue(TEXT("Enable selected joint"),Library::SetPikeWoundCorrection(Constraints[0],true));
    TestTrue(TEXT("Enable is idempotent"),Library::SetPikeWoundCorrection(Constraints[0],true));
    FProphecyJoltBodyState WoundBefore,WoundAfter;
    Native->ReadBody(Settings[0].BodyB,WoundBefore);
    // Admission must not teleport either body. Correction belongs to native Step.
    ProphecyJolt::Constraints::Prepare(Fixture.World);
    for(int32 I=0;I<2;++I)
    {
        Native->ReadBody(Settings[I].BodyA,After[I]);
        TestTrue(TEXT("Admission leaves pose untouched"),After[I].PositionCm.Equals(Before[I].PositionCm,1.e-6));
        TestTrue(TEXT("Admission leaves velocity untouched"),After[I].CenterOfMassVelocityCmPerSecond.Equals(Before[I].CenterOfMassVelocityCmPerSecond,1.e-6));
    }
    for(int32 I=0;I<12;++I)TestTrue(TEXT("Native coupled step"),Native->Step(1.f/60,1).IsSuccess());
    Native->ReadBody(Settings[0].BodyA,After[0]);
    Native->ReadBody(Settings[0].BodyB,WoundAfter);
    const FTransform Blade=Settings[0].FrameA*FTransform(After[0].Rotation,After[0].PositionCm);
    const FTransform WoundFrame=Settings[0].FrameB*FTransform(WoundAfter.Rotation,WoundAfter.PositionCm);
    const FVector Axis=Blade.GetUnitAxis(EAxis::Z),Delta=WoundFrame.GetLocation()-Blade.GetLocation();
    TestTrue(TEXT("Solver aligns rotated wound and blade"),(Delta-Axis*FVector::DotProduct(Delta,Axis)).Size()<.1);
    TestTrue(TEXT("Static wound stays fixed"),WoundAfter.PositionCm.Equals(WoundBefore.PositionCm,1.e-6));
    TestTrue(TEXT("Disable selected joint"),Library::SetPikeWoundCorrection(Constraints[0],false));
    ProphecyJolt::Constraints::Prepare(Fixture.World);
    TestTrue(TEXT("Re-enable selected joint"),Library::SetPikeWoundCorrection(Constraints[0],true));
    ProphecyJolt::Constraints::Prepare(Fixture.World);
    Constraints[0]->BreakConstraint();
    ProphecyJolt::Constraints::Prepare(Fixture.World);
    FProphecyJoltJointHandle Retired;
    TestFalse(TEXT("Broken joint retired"),ProphecyJolt::Constraints::GetJoint(Constraints[0],Retired,Error));
    Constraints[1]->SetLinearXLimit(LCM_Free,0);
    TestFalse(TEXT("Non-slider rejected"),Library::SetPikeWoundCorrection(Constraints[1],true));
    Scene->DisableSceneCollision();for(auto* Adapter:Adapters)Adapter->DisableBody();
    return !HasAnyErrors();
}


