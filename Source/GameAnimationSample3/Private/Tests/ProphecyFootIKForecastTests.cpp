#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyFootIKForecast.h"
#include "ProphecyThrowMath.h"
#include "Async/Async.h"
#include "Dom/JsonObject.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

namespace
{
FVector V(const TArray<TSharedPtr<FJsonValue>>& A){return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());}
TSharedPtr<FJsonObject> ParseForecastTest(const FString& Text){TSharedPtr<FJsonObject> O;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),O);return O;}
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKForecastContractTest,"Prophecy.FootIK.Live.ActualHistoryForecast",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKForecastContractTest::RunTest(const FString&)
{
    FString Text,Error;const FString Fixture=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030/NN/app-walk-stairs-continuation.json");
    if(!FFileHelper::LoadFileToString(Text,*Fixture)){AddError(TEXT("Canonical actual-history fixture is missing"));return false;}
    const auto Data=ParseForecastTest(Text);if(!Data){AddError(TEXT("Invalid forecast fixture"));return false;}
    const auto Request=Data->GetObjectField(TEXT("request"));FProphecyFootIKForecastInput Input;Input.CourseWorld=FTransform(FRotator(0,37,0),FVector(300,800,20));
    for(int32 I=0;I<10;++I)
    {
        const auto Root=V(Request->GetArrayField(TEXT("roots"))[I]->AsArray());const double A=FMath::DegreesToRadians(Request->GetArrayField(TEXT("rootYawDegrees"))[I]->AsNumber());
        const auto Heading=Input.CourseWorld.TransformVectorNoScale(ProphecyThrow::ToUnrealPoint(FVector(FMath::Sin(A),0,FMath::Cos(A))));
        Input.RootWorldWindow.Emplace(Heading.Rotation(),Input.CourseWorld.TransformPosition(ProphecyThrow::ToUnrealPoint(Root)));
    }
    for(int32 I=0;I<2;++I)
    {
        auto& Sample=I?Input.Current:Input.Previous;Sample.RootWorld=Input.RootWorldWindow[I].GetLocation();Sample.HeadingWorld=Input.RootWorldWindow[I].GetRotation().GetForwardVector();
        const auto Seed=Request->GetArrayField(TEXT("seeds"))[I]->AsObject();
        for(int32 J=1;J<26;++J)
        {
            const auto& Axes=Seed->GetArrayField(TEXT("axes"))[J]->AsArray();FMatrix M=FMatrix::Identity;const FVector X=V(Axes[0]->AsArray()),Y=V(Axes[1]->AsArray()),Z=V(Axes[2]->AsArray());M.SetAxes(&X,&Y,&Z);
            const FTransform Body(FQuat(M).GetNormalized(),V(Seed->GetArrayField(TEXT("points"))[J]->AsArray()));Sample.BodiesWorld.Add(ProphecyThrow::ToUnreal(Body)*Input.CourseWorld);
        }
    }
    TArray<FTransform> Extended;TestTrue(TEXT("Actual root window extends"),FProphecyFootIKForecast::ExtendRoots(Input,Extended,Error));
    TestEqual(TEXT("Bounded1.2secondforecast plus NN root lookahead"),Extended.Num(),46);
    for(int32 I=0;I<10;++I)TestTrue(TEXT("Every controller-authored root remains exact"),Extended[I].Equals(Input.RootWorldWindow[I],0));
    auto Stop=Input;Stop.RootWorldWindow[9]=Stop.RootWorldWindow[8];TestTrue(TEXT("Root stop forecast"),FProphecyFootIKForecast::ExtendRoots(Stop,Extended,Error));
    TestTrue(TEXT("A stopped tail does not invent translation or yaw"),Extended.Last().Equals(Stop.RootWorldWindow[9],1.e-10));
    auto Reverse=Input;Reverse.RootWorldWindow[9].SetLocation(Reverse.RootWorldWindow[8].GetLocation()-(Input.RootWorldWindow[8].GetLocation()-Input.RootWorldWindow[7].GetLocation()));
    TestTrue(TEXT("Reverse root forecast"),FProphecyFootIKForecast::ExtendRoots(Reverse,Extended,Error));
    TestTrue(TEXT("Reverse tail keeps the real signed velocity"),(Extended.Last().GetLocation()-Extended[9].GetLocation()).Equals((Extended[9].GetLocation()-Extended[8].GetLocation())*36,1.e-8));
    FString Packed;TestTrue(TEXT("Actual pair packs without any canned seed"),FProphecyFootIKForecast::BuildRequest(Input,Packed,Error));
    const auto PackedObject=ParseForecastTest(Packed);if(!PackedObject){AddError(Error);return false;}
    for(int32 I=0;I<2;++I)
    {
        const auto& Sample=I?Input.Current:Input.Previous;const auto Seed=PackedObject->GetArrayField(TEXT("seeds"))[I]->AsObject();
        const double RootY=ProphecyThrow::FromUnrealPoint(Input.CourseWorld.InverseTransformPosition(Sample.RootWorld)).Y;
        for(int32 J=0;J<25;++J){auto Position=ProphecyFootIKLive::ToSolverBody(Sample.BodiesWorld[J],Input.CourseWorld).GetLocation();Position.Y-=RootY;TestTrue(TEXT("Supplied actual body retains its height relative to navigation root"),V(Seed->GetArrayField(TEXT("points"))[J+1]->AsArray()).Equals(Position,1.e-12));}
    }
    // Raising only the actual navigation carrier must not create a vertical
    // disturbance in the separate flat game-NN forecast.
    auto Rising=Input;
    for(int32 I=0;I<10;++I)Rising.RootWorldWindow[I].AddToTranslation(FVector(0,0,12.*I));
    for(int32 I=0;I<2;++I){auto& S=I?Rising.Current:Rising.Previous;S.RootWorld+=FVector(0,0,12.*I);for(auto& Body:S.BodiesWorld)Body.AddToTranslation(FVector(0,0,12.*I));}
    FString RisingText;TestTrue(TEXT("Actual ramp carrier packs"),FProphecyFootIKForecast::BuildRequest(Rising,RisingText,Error));
    const auto RisingObject=ParseForecastTest(RisingText);
    if(!RisingObject){AddError(Error);return false;}
    for(const auto& Root:RisingObject->GetArrayField(TEXT("roots")))TestEqual(TEXT("No navigation Y enters normal NN future roots"),V(Root->AsArray()).Y,0.);
    for(int32 I=0;I<2;++I)for(int32 J=0;J<26;++J)
        TestTrue(TEXT("Each history row independently removes its own carrier lift"),V(RisingObject->GetArrayField(TEXT("seeds"))[I]->AsObject()->GetArrayField(TEXT("points"))[J]->AsArray()).Equals(V(PackedObject->GetArrayField(TEXT("seeds"))[I]->AsObject()->GetArrayField(TEXT("points"))[J]->AsArray()),1.e-12));
    TestTrue(TEXT("Prospective navigation root window extends"),FProphecyFootIKForecast::ExtendRoots(Rising,Rising.NavRootWindow,Error));
    for(int32 I=10;I<Rising.NavRootWindow.Num();++I){FVector P=Rising.NavRootWindow[I].GetLocation();P.Z=Rising.NavRootWindow[9].GetLocation().Z;Rising.NavRootWindow[I].SetLocation(P);}
    TestTrue(TEXT("Actual ramp-to-landing projection is retained"),FProphecyFootIKForecast::ExtendRoots(Rising,Extended,Error));
    TestTrue(TEXT("Forecast does not extrapolate uphill beyond actual landing"),Extended.Last().Equals(Rising.NavRootWindow.Last(),0));
    auto InvalidNav=Rising;InvalidNav.NavRootWindow[1].AddToTranslation(FVector(0,0,1));
    TestFalse(TEXT("Navigation cannot replace actual history"),FProphecyFootIKForecast::ExtendRoots(InvalidNav,Extended,Error));
    FProphecyFootIKForecast NN;
    if(!NN.Prepare(TEXT("Content/locomotion/NN/prophecy_lower_body_runtime.json"),Error)){AddError(Error);return false;}
    FString Source;auto Work=AsyncThread([&]{return NN.Predict(Input,Source,Error);},1024*1024,TPri_BelowNormal);
    if(!Work.Get()){AddError(Error);return false;}
    const auto Actual=ParseForecastTest(Source);if(!Actual){AddError(TEXT("Invalid native forecast source"));return false;}
    TestEqual(TEXT("History plus current plus36future samples"),Actual->GetArrayField(TEXT("poses")).Num(),38);
    for(int32 I=0;I<2;++I)
    {
        const auto& Sample=I?Input.Current:Input.Previous;const auto Pose=Actual->GetArrayField(TEXT("poses"))[I]->AsObject();
        const double RootY=ProphecyThrow::FromUnrealPoint(Input.CourseWorld.InverseTransformPosition(Sample.RootWorld)).Y;
        for(int32 J=0;J<25;++J){auto Expected=ProphecyFootIKLive::ToSolverBody(Sample.BodiesWorld[J],Input.CourseWorld).GetLocation();Expected.Y-=RootY;TestTrue(TEXT("Forecast starts at both actual seeds exactly"),V(Pose->GetArrayField(TEXT("points"))[J]->AsArray()).Equals(Expected,1.e-12));}
    }
    NN.Cancel();TestFalse(TEXT("Cancelled forecast performs no new inference"),NN.Predict(Input,Source,Error));
    return !HasAnyErrors();
}
#endif
