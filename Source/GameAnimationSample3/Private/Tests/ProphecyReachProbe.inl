#if WITH_EDITOR
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ProphecyReachWristProbe.inl"
#include "ProphecyReachLabPortProbe.inl"
#include "ProphecyReachCheckpointProbe.inl"

// Explicit, read-only numerical capture. No polling or shipping-runtime instrumentation.
static FAutoConsoleCommandWithWorldAndArgs ReachInspectCommand(TEXT("Prophecy.Reach.Inspect"),
    TEXT("Write completed finger poses and native grip counts; optional integer capture tag."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* World)
    {
        using namespace ProphecyReach;
        if(!World)return;
        if(Args.Num()&&Args[0]==TEXT("WristMath")){VerifyReachWristMath();return;}
        if(Args.Num()&&Args[0]==TEXT("LabPort")){VerifyReachLabPort();return;}
        if(Args.Num()&&Args[0]==TEXT("Wrists")){InspectReachWrists(World);return;}
        if(Args.Num()&&Args[0]==TEXT("Checkpoint")){ExportReachCheckpoint(World);return;}
        if(Args.Num()&&Args[0]==TEXT("WristClone"))
        {
            // Explicit diagnostic only: a transient copy avoids Content Browser
            // duplication dialogs, package writes and undo-buffer clearing.
            for(const auto& Entry:States)if(auto* A=const_cast<AProphecyAgent*>(Entry.Key.Get());A&&A->GetWorld()==World&&A->IsPlayerControlled()&&A->GetSimulationMode()==EProphecyAgentSimulationMode::Kinematic)
            {
                auto* Mesh=A->GetPoseReferenceMesh();auto* Clone=DuplicateObject<UPhysicsAsset>(Mesh->GetPhysicsAsset(),GetTransientPackage());
                Clone->SetFlags(RF_Transient);Mesh->SetPhysicsAsset(Clone,false);return;
            }
            return;
        }
        FProphecyJoltWorldDiagnostics D;
        if(auto* W=World->GetSubsystem<UProphecyJoltWorldSubsystem>())W->GetDiagnostics(D);
        FString CSV=FString::Printf(TEXT("joints,%u,suppressed_pairs,%u\nagent,side,bone,model_x,model_y,model_z,actual_x,actual_y,actual_z,collider_distance_cm\n"),D.GenericJointCount,D.SuppressedBodyPairCount);
        for(const auto& P:States)
        {
            const auto* A=P.Key.Get();if(!A||A->GetWorld()!=World)continue;
            for(int Side=0;Side<2;++Side)
            {
                const auto& H=P.Value->Hands[Side];TArray<FName> Names;TArray<FTransform> Actual;
                for(const auto& B:H.Fingers)Names.Add(B.Name);
                Actual.SetNum(Names.Num());if(!A->SampleActualComponentPose(Names,Actual))continue;
                for(int I=0;I<Names.Num();++I)
                {
                    const FVector Model=H.Fingers[I].World.GetLocation(),Point=(Actual[I]*A->GetAgentMesh()->GetComponentTransform()).GetLocation();
                    const double Distance=H.Collider.IsValid()?H.Collider->GetShortestDistanceToPoint(Point,TargetFrame(H),true):-1;
                    CSV+=FString::Printf(TEXT("%s,%d,%s,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f\n"),*A->GetName(),Side,*Names[I].ToString(),Model.X,Model.Y,Model.Z,Point.X,Point.Y,Point.Z,Distance);
                }
            }
        }
        const int Tag=Args.IsEmpty()?0:FCString::Atoi(*Args[0]);
        FFileHelper::SaveStringToFile(CSV,*(FPaths::ProjectSavedDir()/FString::Printf(TEXT("Diagnostics/ReachGrasp20261012/native-%d.csv"),Tag)));
    }));

static FAutoConsoleCommandWithWorld ReachBenchmarkCommand(TEXT("Prophecy.Reach.Benchmark"),
    TEXT("Measure reach read/solve/publication and one-time finger fitting on the first active agent. No physics or NN inference included."),
    FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
    {
        using namespace ProphecyReach;
        for(const auto& P:States)
        {
            auto* A=const_cast<AProphecyAgent*>(P.Key.Get());if(!A||A->GetWorld()!=World)continue;
            FState S=*P.Value;S.Debug=false;const auto Space=A->GetAgentMesh()->GetComponentTransform();
            FVector Targets[2];float Speeds[2];for(int K=0;K<2;++K){Targets[K]=Space.InverseTransformPosition(S.Hands[K].Target.GetLocation());Speeds[K]=S.Hands[K].Speed;}
            const auto Mode=S.Hands[0].Enabled?(S.Hands[1].Enabled?EProphecyDoubleReachMode::Both:EProphecyDoubleReachMode::Left):EProphecyDoubleReachMode::Right;
            double Read=0,Solve=0,Publication=0;
            for(int I=0;I<1000;++I)
            {
                double Start=FPlatformTime::Seconds();BasePose(A,S);Read+=FPlatformTime::Seconds()-Start;
                auto Solver=S.Solver;TArray<FTransform> Pose;
                Start=FPlatformTime::Seconds();ProphecyNativeReach::Step(S.Ordered,Mode,Targets,Speeds,Solver,Pose,Dt);Solve+=FPlatformTime::Seconds()-Start;
                Start=FPlatformTime::Seconds();Publish(A,S,Space);Publication+=FPlatformTime::Seconds()-Start;
            }
            double Build=0,Fit=0;int Count=0;
            for(int Side=0;Side<2;++Side)if(S.Hands[Side].Grab)for(int I=0;I<50;++I)
            {
                FHand H;double Start=FPlatformTime::Seconds();BuildFingers(A->GetPoseReferenceMesh()->GetSkeletalMeshAsset(),A->ClosedFistAnimation.LoadSynchronous(),Side,H);Build+=FPlatformTime::Seconds()-Start;
                H=S.Hands[Side];for(auto& B:H.Fingers)B.Curl=0;
                Start=FPlatformTime::Seconds();FitFingers(H);Fit+=FPlatformTime::Seconds()-Start;++Count;
            }
            FString CSV=FString::Printf(TEXT("per_agent_read_us,per_agent_solve_us,per_agent_publish_us,one_hand_reference_us,one_hand_fit_us\n%.9f,%.9f,%.9f,%.9f,%.9f\n"),Read*1000,Solve*1000,Publication*1000,Build*1.e6/FMath::Max(1,Count),Fit*1.e6/FMath::Max(1,Count));
            FFileHelper::SaveStringToFile(CSV,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/ReachGrasp20261012/live-performance.csv")));
            return;
        }
    }));
#endif
