#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyFootIKRootBridge.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"

namespace
{
using FRootValues=TArray<TSharedPtr<FJsonValue>>;
TSharedPtr<FJsonObject> RootParse(const FString& Text){TSharedPtr<FJsonObject> O;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),O);return O;}
FString RootJson(const TSharedPtr<FJsonObject>& O){FString S;FJsonSerializer::Serialize(O.ToSharedRef(),TJsonWriterFactory<>::Create(&S));return S;}
FString RootJson(const FRootValues& A){FString S;FJsonSerializer::Serialize(A,TJsonWriterFactory<>::Create(&S));return S;}
bool ExactRootValue(const TSharedPtr<FJsonValue>& A,const TSharedPtr<FJsonValue>& E,const FString& Path,FString& Error)
{
    auto Fail=[&](const TCHAR* Why){Error=Path+TEXT(": ")+Why;return false;};
    if(!A||!E||A->Type!=E->Type)return Fail(TEXT("type/missing value"));
    if(E->Type==EJson::Number){const double X=A->AsNumber(),Y=E->AsNumber();return FMemory::Memcmp(&X,&Y,sizeof(double))==0||Fail(TEXT("nonidentical double"));}
    if(E->Type==EJson::String)return A->AsString()==E->AsString()||Fail(TEXT("string differs"));
    if(E->Type==EJson::Boolean)return A->AsBool()==E->AsBool()||Fail(TEXT("bool differs"));
    if(E->Type==EJson::Null)return true;
    if(E->Type==EJson::Array){const auto& AV=A->AsArray();const auto& EV=E->AsArray();if(AV.Num()!=EV.Num())return Fail(TEXT("array size"));for(int32 I=0;I<EV.Num();++I)if(!ExactRootValue(AV[I],EV[I],Path+FString::Printf(TEXT("[%d]"),I),Error))return false;return true;}
    if(E->Type==EJson::Object){for(const auto& Entry:E->AsObject()->Values)if(!ExactRootValue(A->AsObject()->Values.FindRef(Entry.Key),Entry.Value,Path+TEXT(".")+Entry.Key,Error))return false;return true;}
    return Fail(TEXT("unsupported value"));
}
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFootIKRootBridgeParity,"Prophecy.FootIK.RootBridgeExact",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFootIKRootBridgeParity::RunTest(const FString&)
{
    FString Text,Error;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030/root-support-capture.json")))){AddError(TEXT("Generate independent root support capture with Tools/FootIK/verify-root-runtime.cjs"));return false;}
    const auto Fixture=RootParse(Text);if(!Fixture){AddError(TEXT("Invalid independent root fixture"));return false;}
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030/current-yaw-stop10.expected.json")))){AddError(TEXT("Missing original NN window oracle"));return false;}
    const auto Original=RootParse(Text);if(!Original){AddError(TEXT("Invalid original NN window oracle"));return false;}
    const auto& Windows=Original->GetArrayField(TEXT("windows"));const auto& Requests=Original->GetArrayField(TEXT("requests"));int32 VirtualWindows=0;
    const auto Parameters=Fixture->GetObjectField(TEXT("parameters"));auto Init=MakeShared<FJsonObject>();Init->SetBoolField(TEXT("canonicalTerrain"),true);Init->SetObjectField(TEXT("settings"),Parameters->GetObjectField(TEXT("s")));
    const double Height=Parameters->GetNumberField(TEXT("height")),Speed=Parameters->GetNumberField(TEXT("speed")),Gravity=Parameters->GetNumberField(TEXT("gravity")),Duration=Parameters->GetNumberField(TEXT("duration"));
    Init->SetNumberField(TEXT("height"),Height);Init->SetNumberField(TEXT("speed"),Speed);Init->SetNumberField(TEXT("gravity"),Gravity);Init->SetNumberField(TEXT("extent"),FMath::Max(28.,Speed*Duration+.5*FMath::Abs(Gravity)*Duration*Duration+2*Height));
    FProphecyFootIKRootBridge Bridge;FProphecyFootIKRootBridge::FOutput Current,Predicted,After;
    if(!Bridge.InitializeJson(RootJson(Init),FTransform::Identity,Current,Error)){AddError(Error);return false;}
    const auto& Records=Fixture->GetArrayField(TEXT("records"));const auto& Forecasts=Fixture->GetArrayField(TEXT("forecasts"));int32 ForecastCount=0;
    for(int32 I=0;I<Records.Num();++I)
    {
        const auto Record=Records[I]->AsObject(),Status=RootParse(Current.Json);const auto Actual=Status->GetObjectField(TEXT("root"));
        if(!ExactRootValue(MakeShared<FJsonValueObject>(Actual),Record->Values.FindRef(TEXT("context")),FString::Printf(TEXT("root[%d]"),I),Error)){AddError(Error);return false;}
        for(const auto& F:Forecasts)
        {
            const auto Forecast=F->AsObject();if(Forecast->GetIntegerField(TEXT("tick"))!=I)continue;
            FProphecyFootIKRootBridge::FUpdate Update;Update.SupportsJson=RootJson(Forecast->GetArrayField(TEXT("supports")));const FString Before=Current.SnapshotJson;
            if(!Bridge.Forecast(Update,Forecast->GetIntegerField(TEXT("ticks")),Predicted,Error)||!Bridge.Status(After,Error)){AddError(Error);return false;}
            if(After.SnapshotJson!=Before){AddError(TEXT("Forecast mutated root dynamics"));return false;}
            FRootValues Positions;const auto P=RootParse(Predicted.Json);for(const auto& V:P->GetArrayField(TEXT("frames")))Positions.Add(V->AsObject()->Values.FindRef(TEXT("position")));
            if(!ExactRootValue(MakeShared<FJsonValueArray>(Positions),Forecast->Values.FindRef(TEXT("positions")),TEXT("forecast"),Error)){AddError(Error);return false;}++ForecastCount;
        }
        for(int32 W=0;W<Windows.Num();++W)
        {
            if(FMath::RoundToInt(Windows[W]->AsObject()->GetNumberField(TEXT("frame"))*2)!=I)continue;
            const auto Request=Requests[W]->AsObject();FRootValues ExpectedRoots,ExpectedYaw;
            FProphecyFootIKRootBridge::FUpdate Update;
            for(const auto& F:Forecasts){const auto Forecast=F->AsObject();if(Forecast->GetIntegerField(TEXT("tick"))==I&&Forecast->GetIntegerField(TEXT("ticks"))==40){Update.SupportsJson=RootJson(Forecast->GetArrayField(TEXT("supports")));break;}}
            for(int32 K=0;K<10;++K){ExpectedRoots.Add(Request->GetArrayField(TEXT("roots"))[K]);ExpectedYaw.Add(Request->GetArrayField(TEXT("rootYawDegrees"))[K]);Update.RootYawDegrees.Add(ExpectedYaw.Last()->AsNumber());}
            if(!Bridge.Forecast(Update,32,Predicted,Error)){AddError(Error);return false;}
            const auto PredictedJson=RootParse(Predicted.Json);
            if(!ExactRootValue(PredictedJson->Values.FindRef(TEXT("virtualRoots")),MakeShared<FJsonValueArray>(ExpectedRoots),TEXT("NN virtual roots"),Error)||!ExactRootValue(PredictedJson->Values.FindRef(TEXT("rootYawDegrees")),MakeShared<FJsonValueArray>(ExpectedYaw),TEXT("NN future heading"),Error)){AddError(Error);return false;}++VirtualWindows;
        }
        FProphecyFootIKRootBridge::FUpdate Update;Update.SupportsJson=RootJson(Record->GetArrayField(TEXT("supports")));
        if(!Bridge.Step(Update,1,Current,Error)){AddError(Error);return false;}
        const auto Step=RootParse(Current.Json);if(!ExactRootValue(Step->GetArrayField(TEXT("receipts"))[0],Record->Values.FindRef(TEXT("receipt")),FString::Printf(TEXT("receipt[%d]"),I),Error)){AddError(Error);return false;}
    }
    Bridge.Disable();TestFalse(TEXT("Disable releases root VM"),Bridge.IsEnabled());TestFalse(TEXT("Disabled root does no work"),Bridge.Status(Current,Error));
    AddInfo(FString::Printf(TEXT("%d canonical root contexts/force receipts, %d physical forecasts and %d actual NN virtual-root/heading windows match every double exactly; NN prohibited"),Records.Num(),ForecastCount,VirtualWindows));return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFootIKRootBridgeCoordinates,"Prophecy.FootIK.RootBridgeCoordinates",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFootIKRootBridgeCoordinates::RunTest(const FString&)
{
    using B=FProphecyFootIKRootBridge;
    const FTransform Space(FRotator(0,73,0),FVector(240,-190,33));const FVector P(4,-2,8),V(-2,3,7);const FQuat Q=FQuat(FVector(1,2,3).GetSafeNormal(),.71);
    TestTrue(TEXT("Position inverse"),B::ToCoursePosition(B::ToWorldPosition(P,Space),Space).Equals(P,1.e-12));TestTrue(TEXT("Velocity inverse"),B::ToCourseVelocity(B::ToWorldVelocity(V,Space),Space).Equals(V,1.e-12));
    TestTrue(TEXT("Root rotation inverse"),B::ToCourseRotation(B::ToWorldRotation(Q,Space),Space).Equals(Q,1.e-12));
    const FVector CourseUp=Q.RotateVector(FVector(0,1,0));const FVector WorldUp=B::ToWorldVelocity(CourseUp,Space)*.01;
    TestTrue(TEXT("Root alignment has no skeletal bind offset"),B::ToWorldRotation(Q,Space).RotateVector(FVector::UpVector).Equals(WorldUp,1.e-12));
    B Bridge;B::FInit Init;Init.CourseWorld=Space;Init.PositionWorld=B::ToWorldPosition(FVector(0,1,0),Space);Init.NormalWorld=Space.TransformVectorNoScale(FVector(0,-1,0));Init.TravelVelocityWorld=B::ToWorldVelocity(FVector(0,0,2),Space);Init.SettingsJson=TEXT("{\"enabled\":true,\"inclineGravity\":true,\"minGravityIncline\":80,\"fullGravity\":0,\"slideEnabled\":false}");Init.GeometryJson=TEXT("{\"surfaces\":[{\"id\":\"wall\",\"origin\":[0,0,0],\"normal\":[0,0,-1],\"tangent\":[1,0,0],\"bounds\":[-5,5,-50,50],\"thickness\":0.2}]}");
    B::FOutput Output;FString Error;if(!Bridge.Initialize(Init,Output,Error)){AddError(Error);return false;}
    B::FSupport Support;Support.Surface=TEXT("wall");Support.PointWorld=Init.PositionWorld;B::FUpdate Update;TArray<B::FSupport> Supports={Support};Update.SupportsJson=Bridge.EncodeSupports(Supports);
    if(!Bridge.Forecast(Update,32,Output,Error)){AddError(Error);return false;}TestEqual(TEXT("Full NN root window"),Output.RootsWorld.Num(),10);
    if(!Bridge.Step(Update,1,Output,Error)){AddError(Error);return false;}
    const auto Result=RootParse(Output.Json);TestTrue(TEXT("Toward-wall command becomes uphill thrust"),Result->GetArrayField(TEXT("receipts"))[0]->AsObject()->GetArrayField(TEXT("drive"))[1]->AsNumber()>0);
    Bridge.Disable();return !HasAnyErrors();
}
#endif
