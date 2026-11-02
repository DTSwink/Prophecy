// Included by ProphecyRobotTests.cpp; exercises production rig/contact/NNE paths.
#include "Misc/CommandLine.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRobotContactTransfer,"Prophecy.Robotics.ContactTransfer",ProphecyRobotTests::Flags)
bool FProphecyRobotContactTransfer::RunTest(const FString&)
{
    FString Error,Text;const auto* P=ProphecyRobot::Profile(Error);if(!P){AddError(Error);return false;}
    int32 Updates=2;FParse::Value(FCommandLine::Get(),TEXT("RobotAuditUpdates="),Updates);
    if(Updates!=1&&Updates!=2&&Updates!=8){AddError(TEXT("RobotAuditUpdates must be 1, 2 or 8."));return false;}
    AddInfo(FString::Printf(TEXT("ContactTransfer policy30Hz, %d updates/policy, %d collision steps/update"),Updates,8/Updates));
    TArray<TSharedPtr<FJsonValue>> Trace;
    TArray<TSharedPtr<FJsonValue>> Rows;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/RobotLocomotion20261026/contact-transfer-vectors.json")))||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Rows))
    {AddError(TEXT("Run Tools/Robotics/PrepareContactCheck.py first."));return false;}
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true).CreateFXSystem(false).SetTransactional(false);
    auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);if(!World)return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    struct FCleanup{UWorld* W;~FCleanup(){W->DestroyWorld(false);GEngine->DestroyWorldContext(W);W->MarkAsGarbage();}}Cleanup{World};
    auto* Owner=World->GetSubsystem<UProphecyJoltWorldSubsystem>();FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared=FVector(0,0,-981);
    if(!Owner->InitializeSimulation(Settings).IsSuccess())return false;
    FProphecyJoltFixtureBodySettings Floor;Floor.bDynamic=false;Floor.PositionCm=FVector(0,0,-5);Floor.Friction=1;
    FProphecyJoltBodyHandle Ground;if(!Owner->CreateBox(FVector(10000,10000,5),0,Floor,Ground).IsSuccess())return false;
    auto* Actor=World->SpawnActor<AActor>();auto* Mesh=NewObject<USkeletalMeshComponent>(Actor);
    Actor->AddInstanceComponent(Mesh);Actor->SetRootComponent(Mesh);
    Mesh->SetSkeletalMesh(LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin")));
    Mesh->SetPhysicsAsset(LoadObject<UPhysicsAsset>(nullptr,TEXT("/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.PA_UEFN_Mannequin")));
    Mesh->SetCollisionProfileName(TEXT("PhysicsActor"));Mesh->SetCollisionResponseToAllChannels(ECR_Block);
    Mesh->RegisterComponent();Mesh->SetAllBodiesSimulatePhysics(true);
    int32 GetUpSuccess=0,WalkSuccess=0,NativeWalkSuccess=0,WalkTransfers=0;
    for(const auto& Value:Rows)
    {
        const auto Row=Value->AsObject();const bool Clanker=Row->GetBoolField(TEXT("clanker"));
        const int32 Case=Row->GetIntegerField(TEXT("case"));
        const auto Meta=Clanker?TSharedPtr<FJsonObject>():Row->GetObjectField(TEXT("metadata"));
        const FVector Direction=Clanker?ProphecyRobotTests::V(Row->GetArrayField(TEXT("direction")),0):FVector::ZeroVector;
        TArray<ProphecyRobot::FBodyState> Bodies;
        for(const auto& V:Row->GetArrayField(TEXT("states")))
        {
            const auto& A=V->AsArray();auto& B=Bodies.AddDefaulted_GetRef();
            B.World=FTransform(FQuat(A[3]->AsNumber(),A[4]->AsNumber(),A[5]->AsNumber(),A[6]->AsNumber()).GetNormalized(),ProphecyRobotTests::V(A,0));
            B.COMVelocity=ProphecyRobotTests::V(A,7);B.AngularVelocity=ProphecyRobotTests::V(A,10);
        }
        FProphecyJoltRigSnapshot Snapshot;if(!ProphecyJolt::Rig::CaptureLiveRig(*Mesh,Snapshot,Error)||
            !ProphecyRobot::MakeSnapshot(*P,*Mesh,Bodies,Snapshot,Error)){AddError(Error);return false;}
        FProphecyJoltPreparedRig Prepared;if(!Prepared.Build(Snapshot,Error)){AddError(Error);return false;}
        FProphecyJoltRigHandle Rig;TArray<FProphecyJoltBodyHandle> Handles;TArray<FString> Notes;
        auto Status=Owner->CreateRig(Snapshot,Prepared,Rig,Handles,Notes);if(!Status.IsSuccess()){AddError(Status.Message);return false;}
        TArray<FProphecyJoltRobotMotor> Motors;for(const auto& J:P->Joints)Motors.Add(J.Motor[Clanker?1:0]);
        TArray<FProphecyJoltRobotDrag> Drag;for(const auto& B:P->Bodies)Drag.Add(B.Drag);
        Status=Owner->ConfigureRobotRig(Rig,Motors,Drag);if(!Status.IsSuccess()){AddError(Status.Message);return false;}
        const auto& Seed=Row->GetArrayField(TEXT("phase"));FVector2f Phase(Seed[0]->AsNumber(),Seed[1]->AsNumber());
        const FVector Start=Bodies[0].World.GetLocation();double Minimum=Start.Z;int32 Terminal=0,Tick=0;
        const int32 MaxTicks=Clanker?150:Meta->GetIntegerField(TEXT("getup_max_ticks"));
        // Reading native initialization also includes its float quaternion normalization.
        auto Read=[&](){for(int32 I=0;I<15;++I){FProphecyJoltBodyState B;auto R=Owner->ReadBody(Handles[I],B);
            if(!R.IsSuccess()){AddError(R.Message);return false;}
            Bodies[I]={FTransform(B.Rotation,B.PositionCm),B.CenterOfMassVelocityCmPerSecond,B.AngularVelocityRadiansPerSecond};}return true;};
        if(!Read())return false;
        for(Tick=1;Tick<=MaxTicks;++Tick)
        {
            float Obs[154],Action[34];ProphecyRobot::Observation(*P,Bodies,Clanker,Clanker?0:-1,Direction,
                !Clanker&&Meta->GetBoolField(TEXT("sword_drawn")),Phase,MakeArrayView(Obs));
            if(!ProphecyRobot::EvaluatePolicy(Clanker,MakeArrayView(Obs),MakeArrayView(Action),Phase,Error)){AddError(Error);return false;}
            if((Clanker&&(Case==0||Case==10)||!Clanker&&Case==71)&&Tick<=10)
            {
                auto Sample=MakeShared<FJsonObject>();Sample->SetBoolField(TEXT("clanker"),Clanker);Sample->SetNumberField(TEXT("case"),Case);Sample->SetNumberField(TEXT("tick"),Tick);
                TArray<TSharedPtr<FJsonValue>> States,Inputs,Actions;
                for(const auto& B:Bodies){TArray<TSharedPtr<FJsonValue>> A;const auto V=B.World.GetLocation();const auto Q=B.World.GetRotation();
                    for(double X:{V.X,V.Y,V.Z,Q.X,Q.Y,Q.Z,Q.W,B.COMVelocity.X,B.COMVelocity.Y,B.COMVelocity.Z,B.AngularVelocity.X,B.AngularVelocity.Y,B.AngularVelocity.Z})A.Add(MakeShared<FJsonValueNumber>(X));
                    States.Add(MakeShared<FJsonValueArray>(A));}
                for(float X:Obs)Inputs.Add(MakeShared<FJsonValueNumber>(X));for(float X:Action)Actions.Add(MakeShared<FJsonValueNumber>(X));
                Sample->SetArrayField(TEXT("states"),States);Sample->SetArrayField(TEXT("observation"),Inputs);Sample->SetArrayField(TEXT("action"),Actions);
                Trace.Add(MakeShared<FJsonValueObject>(Sample));
            }
            for(int32 I=0;I<14;++I){const auto& J=P->Joints[I];Motors[I].Velocity=J.Motor[0].bBall?
                FVector(Action[J.Action],Action[J.Action+1],Action[J.Action+2]):FVector(0,0,Action[J.Action]);}
            Status=Owner->PublishRobotMotors(Rig,Motors,1);if(!Status.IsSuccess()){AddError(Status.Message);return false;}
            for(int32 U=0;U<Updates;++U){Status=Owner->Step((1.f/30)/Updates,8/Updates);if(!Status.IsSuccess()){AddError(Status.Message);return false;}}
            if(!Read())return false;Minimum=FMath::Min(Minimum,Bodies[0].World.GetLocation().Z);
            if(!Clanker)
            {
                const auto& Head=Bodies[2];const double Height=Head.World.GetLocation().Z;
                const FVector OriginV=Head.COMVelocity-FVector::CrossProduct(Head.AngularVelocity,Head.World.GetRotation().RotateVector(P->Bodies[2].MassFrame.GetLocation()));
                const bool Success=Height>100*Meta->GetNumberField(TEXT("head_reset_height_m"))&&
                    FMath::Max(Bodies[11].World.GetLocation().Z,Bodies[14].World.GetLocation().Z)<100*Meta->GetNumberField(TEXT("success_max_feet_height_m"))&&
                    FMath::Abs(OriginV.Z)<100*Meta->GetNumberField(TEXT("success_max_head_vertical_speed_m_s"));
                const bool Fail=(Tick>Meta->GetIntegerField(TEXT("getup_failure_pelvis_after_tick"))&&Bodies[0].World.GetLocation().Z>=100*Meta->GetNumberField(TEXT("getup_failure_pelvis_height_m")))||
                    (Tick>=Meta->GetIntegerField(TEXT("getup_low_head_failure_tick"))&&Height<=50*Meta->GetNumberField(TEXT("head_height_loss_target_m")));
                Terminal=Fail?1:Success?2:Tick>=MaxTicks?3:0;if(Terminal)break;
            }
        }
        const double Travel=FVector::DotProduct(Bodies[0].World.GetLocation()-Start,Direction);
        const bool Pass=Clanker?(Minimum>=60&&Travel>100):Terminal==2;
        if(Clanker){WalkSuccess+=Pass;const bool Native=Row->GetBoolField(TEXT("native_success"));NativeWalkSuccess+=Native;WalkTransfers+=Native&&Pass;
            if(Native)TestTrue(*FString::Printf(TEXT("Native walking success transfers, case %d"),Case),Pass);}
        else {GetUpSuccess+=Pass;TestTrue(*FString::Printf(TEXT("Get Up success, case %d"),Case),Pass);}
        AddInfo(FString::Printf(TEXT("ContactTransfer %s case %d: pass=%d terminal=%d ticks=%d min_pelvis=%.3f travel=%.3f"),
            Clanker?TEXT("Clanker"):TEXT("GetUp"),Case,Pass,Terminal,FMath::Min(Tick,MaxTicks),Minimum,Travel));
        Owner->DestroyRig(Rig);
    }
    AddInfo(FString::Printf(TEXT("ContactTransfer GetUp %d/100; Walk %d/16; native walking successes transferred %d/%d"),GetUpSuccess,WalkSuccess,WalkTransfers,NativeWalkSuccess));
    FString TraceText;FJsonSerializer::Serialize(Trace,TJsonWriterFactory<>::Create(&TraceText));
    FFileHelper::SaveStringToFile(TraceText,*(FPaths::ProjectSavedDir()/FString::Printf(TEXT("Diagnostics/RobotLocomotion20261026/contact-trace-%d.json"),Updates)));
    TestEqual(TEXT("100 Get Up cases"),GetUpSuccess,100);TestEqual(TEXT("15 native successful walking controls"),NativeWalkSuccess,15);
    return !HasAnyErrors();
}
