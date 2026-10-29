#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyThrowMath.h"
#include "ProphecyThrowLibrary.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyThrowLabParity,"Prophecy.Throws.LabParity",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyThrowLabParity::RunTest(const FString&)
{
    using namespace ProphecyThrow;
    FString Text,Error;TSharedPtr<FJsonObject> Root;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/ThrowPort20261029/reference.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)){AddError(TEXT("Run node Tools/Throws/export.mjs to generate the independent lab reference"));return false;}
    auto Vec=[](const TArray<TSharedPtr<FJsonValue>>& A){return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());};
    double MaxPosition=0,MaxRotation=0,MaxVelocity=0;int Samples=0;
    for(const auto& Case:Root->GetArrayField(TEXT("cases"))){const auto C=Case->AsObject();const auto* P=Profile(C->GetStringField(TEXT("id"))==TEXT("small-throw"),Error);if(!P){AddError(Error);return false;}
        FModel M;M.Prepare(*P,C->GetNumberField(TEXT("amount")),Vec(C->GetArrayField(TEXT("target"))));
        TestTrue(TEXT("Fractional release matches lab"),FMath::Abs(M.Release-C->GetNumberField(TEXT("release")))<1.e-9);
        for(const auto& Sample:C->GetArrayField(TEXT("samples"))){const auto S=Sample->AsObject();const auto Actual=M.Sample(S->GetNumberField(TEXT("frame")));const auto& Expected=S->GetArrayField(TEXT("pose"));
            for(int J=0;J<Actual.Num();++J){const auto& A=Expected[J]->AsArray();const FQuat Q(A[3]->AsNumber(),A[4]->AsNumber(),A[5]->AsNumber(),A[6]->AsNumber());
                MaxPosition=FMath::Max(MaxPosition,(Actual[J].GetLocation()-Vec(A)).Size());MaxRotation=FMath::Max(MaxRotation,1-FMath::Abs(Actual[J].GetRotation()|Q));}
            ++Samples;
        }
        FVector V,W;const auto Held=M.Launch(V,W);const auto Launch=C->GetObjectField(TEXT("launch"));
        MaxPosition=FMath::Max(MaxPosition,(Held.GetLocation()-Vec(Launch->GetArrayField(TEXT("p")))).Size());
        MaxVelocity=FMath::Max(MaxVelocity,(V-Vec(Launch->GetArrayField(TEXT("v")))).Size());MaxVelocity=FMath::Max(MaxVelocity,(W-Vec(Launch->GetArrayField(TEXT("omega")))).Size());
    }
    AddInfo(FString::Printf(TEXT("%d poses; max position %.12g m, quaternion error %.12g, velocity %.12g"),Samples,MaxPosition,MaxRotation,MaxVelocity));
    TestTrue(TEXT("All-bone lab position parity"),MaxPosition<2.e-6);TestTrue(TEXT("All-bone lab rotation parity"),MaxRotation<1.e-10);TestTrue(TEXT("Launch velocity/twist parity"),MaxVelocity<2.e-6);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyThrowNodeReflection,"Prophecy.Throws.NodeReflection",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyThrowNodeReflection::RunTest(const FString&)
{
    for(const FName Name:{FName(TEXT("BeginLabThrow")),FName(TEXT("PlayLabThrow"))})TestNotNull(TEXT("Async throw control node"),UProphecyThrowAction::StaticClass()->FindFunctionByName(Name));
    for(const FName Name:{FName(TEXT("ReleaseLabThrow")),FName(TEXT("CancelLabThrow")),FName(TEXT("GetLabThrowState"))})TestNotNull(TEXT("Throw control/status node"),UProphecyThrowLibrary::StaticClass()->FindFunctionByName(Name));
    return !HasAnyErrors();
}
#endif
