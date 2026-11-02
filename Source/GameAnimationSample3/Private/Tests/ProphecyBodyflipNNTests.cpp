#include "ProphecyBodyflipNN.h"
#include "Async/Async.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

#if WITH_DEV_AUTOMATION_TESTS
namespace BodyflipNNTest
{
using FValues=TArray<TSharedPtr<FJsonValue>>;
static FString Json(const TSharedPtr<FJsonObject>& Object)
{FString Result;FJsonSerializer::Serialize(Object.ToSharedRef(),TJsonWriterFactory<>::Create(&Result));return Result;}
static TSharedPtr<FJsonObject> Parse(const FString& Text)
{TSharedPtr<FJsonObject> Result;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Result);return Result;}
static TSharedPtr<FJsonValue> Vector(double X,double Y,double Z)
{return MakeShared<FJsonValueArray>(FValues{MakeShared<FJsonValueNumber>(X),MakeShared<FJsonValueNumber>(Y),MakeShared<FJsonValueNumber>(Z)});}
static TSharedPtr<FJsonValue> Seed(const TSharedPtr<FJsonValue>& Pose,const TSharedPtr<FJsonValue>& Root)
{
    auto Result=MakeShared<FJsonObject>();FValues Points=Pose->AsObject()->GetArrayField(TEXT("points")),Axes=Pose->AsObject()->GetArrayField(TEXT("axes"));Points.Insert(Root,0);
    Axes.Insert(MakeShared<FJsonValueArray>(FValues{Vector(1,0,0),Vector(0,1,0),Vector(0,0,1)}),0);Result->SetArrayField(TEXT("points"),Points);Result->SetArrayField(TEXT("axes"),Axes);return MakeShared<FJsonValueObject>(Result);
}
static void Numbers(const TSharedPtr<FJsonValue>& Value,TArray<double>& Out)
{if(Value->Type==EJson::Number)Out.Add(Value->AsNumber());else if(Value->Type==EJson::Array)for(const auto& X:Value->AsArray())Numbers(X,Out);}
static double Difference(const TSharedPtr<FJsonValue>& A,const TSharedPtr<FJsonValue>& B)
{
    TArray<double> X,Y;for(const TCHAR* Key:{TEXT("points"),TEXT("axes")}){Numbers(A->AsObject()->Values[Key],X);Numbers(B->AsObject()->Values[Key],Y);}if(X.Num()!=Y.Num())return 1e9;
    double Max=0;for(int32 I=0;I<X.Num();I++)Max=FMath::Max(Max,FMath::Abs(X[I]-Y[I]));return Max;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBodyflipNNContinuationTest,"Prophecy.Bodyflip.NN.InitialAndContinuation",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FBodyflipNNContinuationTest::RunTest(const FString& Parameters)
{
    using namespace BodyflipNNTest;(void)Parameters;double Maximum=0;
    for(const FString Gait:{FString(TEXT("run")),FString(TEXT("walk"))})for(const bool Drawn:{false,true})
    {
        const FString Stem=Gait+(Drawn?TEXT("-drawn"):TEXT("-unarmed"));FString Text,Error,Out;
        const FString BankPath=FPaths::ProjectContentDir()/TEXT("BodyflipLab/NN")/(Stem+TEXT("-seeds.json"));
        if(!FFileHelper::LoadFileToString(Text,*BankPath)){AddError(TEXT("Missing exported NN bank: ")+Stem);return false;}
        const auto Bank=Parse(Text);if(!Bank){AddError(TEXT("Invalid NN bank"));return false;}
        const double PrepareStarted=FPlatformTime::Seconds();
        if(!ProphecyBodyflip::PrepareNN(Gait,Drawn,Error)){AddError(Error);return false;}
        const double PrepareSeconds=FPlatformTime::Seconds()-PrepareStarted;
        auto Initial=MakeShared<FJsonObject>();Initial->SetStringField(TEXT("gait"),Gait);Initial->SetBoolField(TEXT("drawn"),Drawn);Initial->SetNumberField(TEXT("phase"),.5);Initial->SetNumberField(TEXT("duration"),.2);
        // Prepare only the UObject boundary on GT; exercise cold ORT model and
        // instance creation on the same worker path used by native playback.
        const double WorkerStarted=FPlatformTime::Seconds();
        auto InitialFuture=Async(EAsyncExecution::ThreadPool,[Initial,&Out,&Error]{return ProphecyBodyflip::GenerateNN(nullptr,Json(Initial),Out,Error);});
        if(!InitialFuture.Get()){AddError(Error);return false;}const auto InitialResult=Parse(Out);
        AddInfo(FString::Printf(TEXT("%s GT prepare %.3fs; first worker init/rollout %.3fs"),*Stem,PrepareSeconds,FPlatformTime::Seconds()-WorkerStarted));
        if(Gait==TEXT("run")&&!Drawn)
        {
            int32 Checks=0;
            TestFalse(TEXT("Native rollout observes cancellation during recurrent work"),ProphecyBodyflip::GenerateNN(nullptr,Json(Initial),Out,Error,[&Checks]{return ++Checks>=10;}));
            TestTrue(TEXT("Cancelled native rollout reports cancellation"),Error.Contains(TEXT("cancelled")));
            TestTrue(TEXT("Cancelled native rollout publishes no partial result"),Out.IsEmpty());
            if(!ProphecyBodyflip::GenerateNN(nullptr,Json(Initial),Out,Error)){AddError(Error);return false;}
            const auto Resumed=Parse(Out);const auto& Before=InitialResult->GetArrayField(TEXT("poses"));const auto& After=Resumed->GetArrayField(TEXT("poses"));
            TestEqual(TEXT("Cancelled rollout leaves private model reusable"),After.Num(),Before.Num());
            for(int32 I=0;I<After.Num()&&I<Before.Num();I++)Maximum=FMath::Max(Maximum,Difference(After[I],Before[I]));
        }
        const int32 HalfStride=int32(Bank->GetNumberField(TEXT("stride")))/2,Slot=HalfStride+(HalfStride&1);const auto Phase=Bank->GetArrayField(TEXT("phases"))[Slot]->AsObject();
        TestEqual(Stem+TEXT(" initial frame count"),InitialResult->GetArrayField(TEXT("poses")).Num(),8);
        TestEqual(Stem+TEXT(" exact first seed"),Difference(InitialResult->GetArrayField(TEXT("poses"))[0],Phase->GetArrayField(TEXT("seeds"))[1]),0.0);
        const auto& SeedRoots=Phase->GetArrayField(TEXT("roots"));FValues Roots;for(int32 I=0;I<25;I++)
        {
            float V[3];for(int32 K=0;K<3;K++){const float Previous=float(SeedRoots[0]->AsArray()[K]->AsNumber()),Current=float(SeedRoots[1]->AsArray()[K]->AsNumber());V[K]=Current+float(I-1)*(Current-Previous);}Roots.Add(Vector(V[0],V[1],V[2]));
        }
        FValues Names=Bank->GetArrayField(TEXT("names"));Names.Insert(MakeShared<FJsonValueString>(TEXT("root")),0);const auto& BankSeeds=Phase->GetArrayField(TEXT("seeds"));
        auto Request=MakeShared<FJsonObject>();Request->SetStringField(TEXT("gait"),Gait);Request->SetBoolField(TEXT("drawn"),Drawn);Request->SetArrayField(TEXT("names"),Names);Request->SetArrayField(TEXT("roots"),Roots);Request->SetArrayField(TEXT("seeds"),{Seed(BankSeeds[0],Roots[0]),Seed(BankSeeds[1],Roots[1])});Request->SetNumberField(TEXT("frames"),16);
        if(!ProphecyBodyflip::GenerateNN(nullptr,Json(Request),Out,Error)){AddError(Error);return false;}const auto Full=Parse(Out);
        const FString Folder=FPaths::ProjectSavedDir()/TEXT("Diagnostics/BodyflipPort20261030/NN");IFileManager::Get().MakeDirectory(*Folder,true);auto Receipt=MakeShared<FJsonObject>();Receipt->SetObjectField(TEXT("request"),Parse(Json(Request)));Receipt->SetObjectField(TEXT("actual"),Full);FFileHelper::SaveStringToFile(Json(Receipt),*(Folder/(Stem+TEXT("-native.json"))));
        Request->SetNumberField(TEXT("frames"),8);if(!ProphecyBodyflip::GenerateNN(nullptr,Json(Request),Out,Error)){AddError(Error);return false;}const auto Prefix=Parse(Out);
        const auto& PrefixPoses=Prefix->GetArrayField(TEXT("poses"));const auto& PrefixRoots=Prefix->GetArrayField(TEXT("roots"));const auto& FullPoses=Full->GetArrayField(TEXT("poses"));
        for(int32 I=0;I<8;I++)Maximum=FMath::Max(Maximum,Difference(PrefixPoses[I],FullPoses[I]));
        FValues TailRoots;TailRoots.Append(Roots.GetData()+7,Roots.Num()-7);Request->SetArrayField(TEXT("roots"),TailRoots);Request->SetArrayField(TEXT("seeds"),{Seed(PrefixPoses[6],PrefixRoots[6]),Seed(PrefixPoses[7],PrefixRoots[7])});Request->SetNumberField(TEXT("frames"),9);Request->SetObjectField(TEXT("continuation"),Prefix->GetObjectField(TEXT("continuation")));
        if(!ProphecyBodyflip::GenerateNN(nullptr,Json(Request),Out,Error)){AddError(Error);return false;}const auto Tail=Parse(Out);
        for(int32 I=0;I<9;I++)Maximum=FMath::Max(Maximum,Difference(Tail->GetArrayField(TEXT("poses"))[I],FullPoses[I+7]));
        Request->GetObjectField(TEXT("continuation"))->RemoveField(TEXT("current"));TestFalse(Stem+TEXT(" rejects incomplete recurrent history"),ProphecyBodyflip::GenerateNN(nullptr,Json(Request),Out,Error));
    }
    TestTrue(TEXT("Untrim extension equals uninterrupted native rollout"),Maximum<1e-7);AddInfo(FString::Printf(TEXT("Maximum continuation difference %.9g"),Maximum));return !HasAnyErrors();
}
#endif
