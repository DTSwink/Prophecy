#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyBodyflipVM.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBodyflipCurrentPortTest,"Prophecy.Bodyflip.CurrentLabParity",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FBodyflipCurrentPortTest::RunTest(const FString&)
{
    FString Path,Text,Error,Reply;TSharedPtr<FJsonObject> Fixture;
    if(!FParse::Value(FCommandLine::Get(),TEXT("BodyflipPortFixture="),Path)||!FFileHelper::LoadFileToString(Text,*Path)||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Fixture))
    {AddError(TEXT("Supply -BodyflipPortFixture= with the current app/V8 reference"));return false;}
    int32 Frames=0,Numbers=0;double Worst=0;
    TFunction<bool(const TSharedPtr<FJsonValue>&,const TSharedPtr<FJsonValue>&,const FString&)> Compare;
    Compare=[&](const auto& A,const auto& B,const FString& Where)->bool
    {
        if(A->Type!=B->Type){AddError(Where+TEXT(" type mismatch"));return false;}
        switch(A->Type)
        {
        case EJson::Number:
        {
            const double X=A->AsNumber(),Y=B->AsNumber(),D=FMath::Abs(X-Y);++Numbers;Worst=FMath::Max(Worst,D);
            if(!FMath::IsFinite(X)||!FMath::IsFinite(Y)||D>1.e-7+1.e-10*FMath::Max(FMath::Abs(X),FMath::Abs(Y)))
            {AddError(FString::Printf(TEXT("%s differs: %.17g versus %.17g"),*Where,X,Y));return false;}return true;
        }
        case EJson::Object:
        {
            const auto X=A->AsObject(),Y=B->AsObject();if(X->Values.Num()!=Y->Values.Num()){AddError(Where+TEXT(" field count"));return false;}
            for(const auto& Pair:X->Values){const auto* Value=Y->Values.Find(Pair.Key);if(!Value||!Compare(Pair.Value,*Value,Where+TEXT(".")+Pair.Key))return false;}return true;
        }
        case EJson::Array:
        {
            const auto& X=A->AsArray();const auto& Y=B->AsArray();if(X.Num()!=Y.Num()){AddError(Where+TEXT(" array length"));return false;}
            for(int32 I=0;I<X.Num();++I)if(!Compare(X[I],Y[I],Where+FString::Printf(TEXT("[%d]"),I)))return false;return true;
        }
        case EJson::String:return TestEqual(*Where,A->AsString(),B->AsString());
        case EJson::Boolean:return TestEqual(*Where,A->AsBool(),B->AsBool());
        default:return true;
        }
    };
    for(const auto& Row:Fixture->GetArrayField(TEXT("cases")))
    {
        const auto C=Row->AsObject();const auto Spec=C->GetObjectField(TEXT("fixture"));
        FProphecyBodyflipVM VM;if(!VM.Initialize({},Error)){AddError(Error);return false;}
        auto Start=MakeShared<FJsonObject>();Start->SetStringField(TEXT("op"),TEXT("start"));Start->SetObjectField(TEXT("settings"),Spec->GetObjectField(TEXT("settings")));
        Start->SetNumberField(TEXT("horizon"),Spec->GetObjectField(TEXT("settings"))->GetNumberField(TEXT("trimOut")));
        Text.Reset();FJsonSerializer::Serialize(Start,TJsonWriterFactory<>::Create(&Text));
        if(!VM.Command(Text,Reply,Error)){AddError(Error);return false;}
        for(const auto& Expected:C->GetArrayField(TEXT("frames")))
        {
            const double Time=Expected->AsObject()->GetNumberField(TEXT("time"));
            if(!VM.Command(FString::Printf(TEXT("{\"op\":\"sample\",\"time\":%.17g}"),Time),Reply,Error)){AddError(Error);return false;}
            TSharedPtr<FJsonObject> Actual;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Reply),Actual)){AddError(TEXT("Invalid native packet"));return false;}
            if(!Compare(MakeShared<FJsonValueObject>(Actual),Expected,Spec->GetStringField(TEXT("name"))))return false;++Frames;
        }
    }
    AddInfo(FString::Printf(TEXT("Current lab parity: %d frames, %d numeric values, maximum difference %.17g"),Frames,Numbers,Worst));return !HasAnyErrors();
}

#if WITH_EDITOR
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "Kismet2/KismetEditorUtilities.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBodyflipBlueprintCompatibilityTest,"Prophecy.Bodyflip.ExistingBlueprintCompatibility",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FBodyflipBlueprintCompatibilityTest::RunTest(const FString&)
{
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!TestNotNull(TEXT("Existing manual agent Blueprint loads"),BP))return false;
    auto Snapshot=[&]()
    {
        TMap<FString,FString> Pins;TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
        for(const auto* Graph:Graphs)for(const UEdGraphNode* Node:Graph->Nodes)if(Node)for(const auto* Pin:Node->Pins)if(Pin)
        {
            const FString Key=Node->NodeGuid.ToString()+TEXT("/")+Pin->PinName.ToString()+FString::FromInt(int32(Pin->Direction));
            TArray<FString> Links;for(const auto* Link:Pin->LinkedTo)if(Link&&Link->GetOwningNode())Links.Add(Link->GetOwningNode()->NodeGuid.ToString()+TEXT("/")+Link->PinName.ToString());Links.Sort();
            Pins.Add(Key,Pin->DefaultValue+TEXT("|")+GetPathNameSafe(Pin->DefaultObject)+TEXT("|")+Pin->DefaultTextValue.ToString()+TEXT("|")+FString::Join(Links,TEXT(";")));
        }
        return Pins;
    };
    const auto Before=Snapshot();
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipSave);
    TestTrue(TEXT("Existing full graph compiles against updated reflection"),BP->Status==BS_UpToDate||BP->Status==BS_UpToDateWithWarnings);
    const auto After=Snapshot();
    for(const auto& Pin:Before)
    {
        const auto* Value=After.Find(Pin.Key);
        if(!Value||*Value!=Pin.Value){AddError(TEXT("Existing Blueprint pin default or link changed: ")+Pin.Key);return false;}
    }
    AddInfo(FString::Printf(TEXT("Compiled existing Blueprint; all %d original pins retain defaults and links. SkipSave; no asset written."),Before.Num()));
    return !HasAnyErrors();
}
#endif
#endif
