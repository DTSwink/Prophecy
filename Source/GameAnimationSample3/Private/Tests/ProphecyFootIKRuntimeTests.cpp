#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyFootIKVM.h"
#include "ProphecyFootIKNN.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"

namespace ProphecyFootIKParity
{
bool Parse(const FString& Text,TSharedPtr<FJsonObject>& Object)
{
    return FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Object)&&Object.IsValid();
}
bool Read(const FString& File,TSharedPtr<FJsonObject>& Object)
{
    FString Text;return FFileHelper::LoadFileToString(Text,*File)&&Parse(Text,Object);
}
FString Encode(const TSharedPtr<FJsonObject>& Object)
{
    FString Text;FJsonSerializer::Serialize(Object.ToSharedRef(),TJsonWriterFactory<>::Create(&Text));return Text;
}
bool AppendDiagnostic(const FString& File,const TSharedPtr<FJsonObject>& Object)
{
    FString Text;FJsonSerializer::Serialize(Object.ToSharedRef(),TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text));Text+=LINE_TERMINATOR;
    return FFileHelper::SaveStringToFile(Text,*File,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
}
TSharedPtr<FJsonValue> Value(const FString& Text)
{
    TSharedPtr<FJsonObject> Wrapper;if(!Parse(TEXT("{\"value\":")+Text+TEXT("}"),Wrapper))return nullptr;return Wrapper->Values.FindRef(TEXT("value"));
}
TSharedPtr<FJsonValue> ArrayResult(const FString& Text,const FString& Field)
{
    auto Result=Value(Text);if(Result.IsValid()&&Result->Type==EJson::Object)return Result->AsObject()->Values.FindRef(Field);return Result;
}
struct FComparison
{
    FString Error;
    double MaxNumber=0,MaxPosition=0,MaxQuaternion=0;
    int64 Numbers=0;
    bool Fail(const FString& Path,const FString& Reason){if(Error.IsEmpty())Error=Path+TEXT(": ")+Reason;return false;}
    bool Compare(const TSharedPtr<FJsonValue>& Actual,const TSharedPtr<FJsonValue>& Expected,const FString& Path)
    {
        if(!Actual.IsValid()||!Expected.IsValid())return Fail(Path,TEXT("missing value"));
        if(Actual->Type!=Expected->Type)return Fail(Path,TEXT("JSON type differs"));
        if(Expected->Type==EJson::Number){const double Difference=FMath::Abs(Actual->AsNumber()-Expected->AsNumber());++Numbers;MaxNumber=FMath::Max(MaxNumber,Difference);return Difference<=1.e-8||Fail(Path,FString::Printf(TEXT("numeric error %.12g"),Difference));}
        if(Expected->Type==EJson::Boolean)return Actual->AsBool()==Expected->AsBool()||Fail(Path,TEXT("boolean differs"));
        if(Expected->Type==EJson::String)return Actual->AsString()==Expected->AsString()||Fail(Path,TEXT("state/string differs"));
        if(Expected->Type==EJson::Null)return true;
        if(Expected->Type==EJson::Array){
            const auto& A=Actual->AsArray();const auto& E=Expected->AsArray();
            if(A.Num()!=E.Num())return Fail(Path,TEXT("array length differs"));
            if(Path.EndsWith(TEXT(".pose.points"))||Path.EndsWith(TEXT(".pose.q"))){
                const bool Quaternion=Path.EndsWith(TEXT(".q"));
                for(int32 Bone=0;Bone<E.Num();++Bone){
                    if(A[Bone]->Type!=EJson::Array||E[Bone]->Type!=EJson::Array)return Fail(Path,TEXT("invalid bone array"));
                    const auto& AV=A[Bone]->AsArray();const auto& EV=E[Bone]->AsArray();const int32 Width=Quaternion?4:3;
                    if(AV.Num()!=Width||EV.Num()!=Width)return Fail(Path,TEXT("invalid bone width"));
                    double Sum=0;for(int32 Axis=0;Axis<Width;++Axis){const double X=AV[Axis]->AsNumber(),Y=EV[Axis]->AsNumber();Sum+=Quaternion?X*Y:FMath::Square(X-Y);++Numbers;}
                    const double Difference=Quaternion?FMath::Abs(1-FMath::Abs(Sum)):FMath::Sqrt(Sum);
                    if(Quaternion)MaxQuaternion=FMath::Max(MaxQuaternion,Difference);else MaxPosition=FMath::Max(MaxPosition,Difference);
                    if(Difference>(Quaternion?1.e-10:1.e-8))return Fail(Path,FString::Printf(TEXT("bone %d error %.12g"),Bone,Difference));
                }
                return true;
            }
            for(int32 I=0;I<E.Num();++I)if(!Compare(A[I],E[I],Path+FString::Printf(TEXT("[%d]"),I)))return false;
            return true;
        }
        if(Expected->Type==EJson::Object){
            const auto A=Actual->AsObject(),E=Expected->AsObject();
            // The oracle deliberately omits large raw/axes duplicate fields.
            // Every retained scalar/state/contact is still checked recursively.
            for(const auto& Entry:E->Values)if(!Compare(A->Values.FindRef(Entry.Key),Entry.Value,Path+TEXT(".")+Entry.Key))return false;
            return true;
        }
        return Fail(Path,TEXT("unsupported JSON type"));
    }
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFootIKRuntimeParity,"Prophecy.FootIK.EmbeddedRuntimeParity",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFootIKRuntimeParity::RunTest(const FString&)
{
    using namespace ProphecyFootIKParity;
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030");TSharedPtr<FJsonObject> Manifest;
    if(!Read(Directory/TEXT("manifest.json"),Manifest)){AddError(TEXT("Generate the independent oracle first: node Tools/FootIK/parity-export.cjs"));return false;}
    FComparison Comparison;int64 Frames=0,Windows=0;int32 Cases=0;
    for(const auto& CaseValue:Manifest->GetArrayField(TEXT("cases"))){
        const auto Case=CaseValue->AsObject();const FString Name=Case->GetStringField(TEXT("name"));
        TSharedPtr<FJsonObject> Input,Expected;
        if(!Read(Directory/Case->GetStringField(TEXT("input")),Input)||!Read(Directory/Case->GetStringField(TEXT("expected")),Expected)){AddError(Name+TEXT(": missing generated fixture"));return false;}
        FProphecyFootIKVM VM;FString Result,Error;int32 PolicyIndex=0;
        TArray<TSharedPtr<FJsonValue>> Replies;
        if(Input->HasField(TEXT("policySteps"))){Replies=Input->GetArrayField(TEXT("policySteps"));Input->RemoveField(TEXT("policySteps"));Input->SetBoolField(TEXT("coupled"),true);}
        if(Input->HasField(TEXT("handoffReply"))){Replies.Add(Input->Values.FindRef(TEXT("handoffReply")));Input->RemoveField(TEXT("handoffReply"));}
        const auto& Requests=Expected->GetArrayField(TEXT("requests"));
        FProphecyFootIKVM::FNN Infer=[&](const FString& Json,FString& Out,FString& CallbackError){
            const int32 I=PolicyIndex++;
            if(!Replies.IsValidIndex(I)||!Requests.IsValidIndex(I)){CallbackError=Name+TEXT(": unexpected policy callback");return false;}
            if(!Comparison.Compare(Value(Json),Requests[I],Name+FString::Printf(TEXT(".requests[%d]"),I))){CallbackError=Comparison.Error;return false;}
            Out=Encode(Replies[I]->AsObject());return true;
        };
        if(!VM.Initialize(MoveTemp(Infer),Error)||!VM.Command(Encode(Input),Result,Error)){AddError(Name+TEXT(": ")+Error);return false;}
        TSharedPtr<FJsonObject> Prepared;
        if(!Parse(Result,Prepared)||!Comparison.Compare(Prepared->Values.FindRef(TEXT("events")),Expected->Values.FindRef(TEXT("events")),Name+TEXT(".events"))){AddError(Name+TEXT(": ")+Comparison.Error);return false;}
        const auto& ExpectedFrames=Expected->GetArrayField(TEXT("frames"));
        // Small sequential batches bound temporary JS strings/JSON memory.
        for(int32 Start=0;Start<ExpectedFrames.Num();Start+=24){
            const int32 Count=FMath::Min(24,ExpectedFrames.Num()-Start);
            const FString Command=FString::Printf(TEXT("{\"op\":\"frames\",\"start\":%d,\"count\":%d}"),Start,Count);
            if(!VM.Command(Command,Result,Error)){AddError(Name+TEXT(": ")+Error);return false;}
            const auto Actual=ArrayResult(Result,TEXT("frames"));
            if(!Actual.IsValid()||Actual->Type!=EJson::Array||Actual->AsArray().Num()!=Count){AddError(Name+TEXT(": wrong frame batch size"));return false;}
            for(int32 I=0;I<Count;++I)if(!Comparison.Compare(Actual->AsArray()[I],ExpectedFrames[Start+I],Name+FString::Printf(TEXT(".frame[%d]"),Start+I))){AddError(Comparison.Error);return false;}
            Frames+=Count;
        }
        if(!VM.Command(TEXT("{\"op\":\"windows\"}"),Result,Error)){AddError(Name+TEXT(": ")+Error);return false;}
        const auto ExpectedWindows=Expected->Values.FindRef(TEXT("windows"));
        if(!Comparison.Compare(ArrayResult(Result,TEXT("windows")),ExpectedWindows,Name+TEXT(".windows"))){AddError(Comparison.Error);return false;}
        Windows+=ExpectedWindows->AsArray().Num();++Cases;
        if(PolicyIndex!=Requests.Num()){AddError(Name+TEXT(": policy callback count differs"));return false;}
        if(!VM.Command(TEXT("{\"op\":\"close\"}"),Result,Error)){AddError(Name+TEXT(": close: ")+Error);return false;}
    }
    AddInfo(FString::Printf(TEXT("%d cases; %lld full120Hz frames; %lld policy windows; %lld numbers; max position %.12gm, quaternion %.12g, other numeric %.12g"),Cases,Frames,Windows,Comparison.Numbers,Comparison.MaxPosition,Comparison.MaxQuaternion,Comparison.MaxNumber));
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFootIKBoundedExtension,"Prophecy.FootIK.BoundedExtension",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFootIKBoundedExtension::RunTest(const FString&)
{
    using namespace ProphecyFootIKParity;
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030");TSharedPtr<FJsonObject> Input,Expected;
    if(!Read(Directory/TEXT("current-yaw-stop10.input.json"),Input)||!Read(Directory/TEXT("current-yaw-stop10.expected.json"),Expected)){AddError(TEXT("Generate current-yaw-stop10 using Tools/FootIK/parity-export.cjs"));return false;}
    FProphecyFootIKVM VM;FString Result,Error;FComparison Comparison;
    Input->SetNumberField(TEXT("endTime"),1.0/30.0);
    if(!VM.Initialize({},Error)||!VM.Command(Encode(Input),Result,Error)){AddError(Error);return false;}
    TSharedPtr<FJsonObject> Status;
    if(!Parse(Result,Status)||Status->GetIntegerField(TEXT("frames"))!=5){AddError(TEXT("An exact policy boundary should prepare only five120Hz frames"));return false;}
    if(!VM.Command(TEXT("{\"op\":\"windows\"}"),Result,Error)){AddError(Error);return false;}
    const auto Windows=ArrayResult(Result,TEXT("windows"));
    if(!Windows.IsValid()||Windows->AsArray().Num()!=0){AddError(TEXT("The unused next policy endpoint was generated beyond the requested boundary"));return false;}
    if(!VM.Command(TEXT("{\"op\":\"frames\",\"start\":0,\"count\":5}"),Result,Error)){AddError(Error);return false;}
    const FString Prefix=Result;
    // Includes a non-policy and a non60Hz boundary, then crosses slide entry.
    for(const double End:{0.05,0.3,1.017,2.1,3.3666666666666667}){
        if(!VM.Command(FString::Printf(TEXT("{\"op\":\"extend\",\"endTime\":%.17g}"),End),Result,Error)){AddError(Error);return false;}
        const int32 Count=FMath::CeilToInt(End*120-1.e-8)+1;
        if(!Parse(Result,Status)||Status->GetIntegerField(TEXT("frames"))!=Count){AddError(TEXT("Extension generated outside its requested120Hz boundary"));return false;}
        if(!VM.Command(TEXT("{\"op\":\"frames\",\"start\":0,\"count\":5}"),Result,Error)){AddError(Error);return false;}
        if(Result!=Prefix){AddError(TEXT("Extension changed an already published prefix"));return false;}
    }
    if(!VM.Command(TEXT("{\"op\":\"frames\",\"start\":0,\"count\":405}"),Result,Error)){AddError(Error);return false;}
    if(!Comparison.Compare(ArrayResult(Result,TEXT("frames")),Expected->Values.FindRef(TEXT("frames")),TEXT("split.frames"))){AddError(Comparison.Error);return false;}
    if(!VM.Command(TEXT("{\"op\":\"windows\"}"),Result,Error)){AddError(Error);return false;}
    const FString BeforeShrink=Result;
    if(!VM.Command(TEXT("{\"op\":\"extend\",\"endTime\":0.1}"),Result,Error)||!Parse(Result,Status)||Status->GetIntegerField(TEXT("frames"))!=405){AddError(TEXT("Shrinking regenerated or discarded the retained prefix"));return false;}
    if(!VM.Command(TEXT("{\"op\":\"windows\"}"),Result,Error)||Result!=BeforeShrink){AddError(TEXT("Shrinking performed additional policy work"));return false;}
    if(!VM.Command(TEXT("{\"op\":\"close\"}"),Result,Error)||!VM.Command(TEXT("{\"op\":\"status\"}"),Result,Error)||!Parse(Result,Status)||Status->GetBoolField(TEXT("enabled"))){AddError(TEXT("Closed session retained active runtime state"));return false;}
    AddInfo(TEXT("Exact split generation, untouched prefix, no unused boundary inference, no work on shrink, and close checked."));
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFootIKCoupledNNDiagnostic,"Prophecy.FootIK.CoupledNativeNNDiagnostic",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFootIKCoupledNNDiagnostic::RunTest(const FString&)
{
    using namespace ProphecyFootIKParity;
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030");
    auto Report=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> Cases;
    Report->SetStringField(TEXT("schema"),TEXT("footik-native-nn-closed-loop-diagnostic-v2"));
    Report->SetStringField(TEXT("oracleDirectory"),TEXT("coupled-current"));
    Report->SetStringField(TEXT("note"),TEXT("Finite output and exact semantic states/contact identities are required. Continuous NN drift is measured, not certified as parity. Actual frames and NN requests/replies are retained for first-divergence analysis."));
    auto VectorError=[](const TSharedPtr<FJsonValue>& A,const TSharedPtr<FJsonValue>& B){
        const auto& X=A->AsArray();const auto& Y=B->AsArray();double Sum=0;
        for(int32 I=0;I<3;++I){const double D=X[I]->AsNumber()-Y[I]->AsNumber();Sum+=D*D;}return FMath::Sqrt(Sum);
    };
    auto ContactKey=[](const TSharedPtr<FJsonObject>& Foot,const FString& Field){
        const auto C=Foot->Values.FindRef(Field);
        if(!C.IsValid()||C->Type==EJson::Null)return FString(TEXT("none"));
        FString Surface;if(C->Type==EJson::Object)C->AsObject()->TryGetStringField(TEXT("surface"),Surface);
        return FString(TEXT("contact:"))+Surface;
    };
    // Prepare resets all recurrence for each case. Reuse only the immutable
    // matching-direction graph sessions; every case still owns a fresh VM.
    FProphecyFootIKNN NN;
    for(const FString Name:{TEXT("current-yaw-stop10"),TEXT("coupled-wall-walk"),TEXT("coupled-wall-run")})for(const bool NativeSource:{false,true}){
        TSharedPtr<FJsonObject> Input,Expected;
        // A complete-system oracle pairs today's canonical root forecast with
        // its actual Torch reply. Historic fixed replies remain a separate
        // solver-only proof; they must not stand in for live NN answers.
        const FString OracleDirectory=Directory/TEXT("coupled-current");
        if(!Read(OracleDirectory/(Name+TEXT(".input.json")),Input)||!Read(OracleDirectory/(Name+TEXT(".expected.json")),Expected)){AddError(Name+TEXT(": run Tools/FootIK/re-record-coupled.py to generate the current coupled oracle"));return false;}
        auto Settings=Input->GetObjectField(TEXT("settings"));const auto Source=Input->GetObjectField(TEXT("source"));
        FString Direction;if(Source->TryGetStringField(TEXT("direction"),Direction))Settings->SetStringField(TEXT("direction"),Direction);
        FString Error,Result;
        if(!NN.Prepare(Encode(Settings),Error)){AddError(Name+TEXT(": ")+Error);return false;}
        if(NativeSource){FString SourceJson;TSharedPtr<FJsonObject> Generated;if(!NN.Initialize(SourceJson,Error)||!Parse(SourceJson,Generated)){AddError(Name+TEXT(": source: ")+Error);return false;}Input->SetObjectField(TEXT("source"),Generated);}
        Input->RemoveField(TEXT("policySteps"));Input->SetBoolField(TEXT("coupled"),true);
        const FString CaptureDirectory=Directory/TEXT("native-nn-captures");IFileManager::Get().MakeDirectory(*CaptureDirectory,true);
        const FString Prefix=CaptureDirectory/(Name+(NativeSource?TEXT("-native-source"):TEXT("-recorded-source"))),FramesFile=Prefix+TEXT(".frames.jsonl"),CallsFile=Prefix+TEXT(".nn.jsonl");
        bool Captured=FFileHelper::SaveStringToFile(FString(),*FramesFile)&&FFileHelper::SaveStringToFile(FString(),*CallsFile)&&FFileHelper::SaveStringToFile(Encode(Input),*(Prefix+TEXT(".input.json")));
        int32 NNCalls=0;FProphecyFootIKVM VM;
        auto Infer=[&](const FString& Request,FString& Response,FString& CallbackError){
            const int32 Index=NNCalls++;const bool Succeeded=NN.Generate(Request,Response,CallbackError);auto Call=MakeShared<FJsonObject>();Call->SetNumberField(TEXT("index"),Index);Call->SetField(TEXT("request"),Value(Request));
            if(Succeeded)Call->SetField(TEXT("response"),Value(Response));else Call->SetStringField(TEXT("error"),CallbackError);
            Captured=AppendDiagnostic(CallsFile,Call)&&Captured;return Succeeded;
        };
        if(!VM.Initialize(Infer,Error)||!VM.Command(Encode(Input),Result,Error)){AddError(Name+TEXT(": generate: ")+Error);return false;}
        TSharedPtr<FJsonObject> Prepared;if(!Parse(Result,Prepared)){AddError(TEXT("Invalid prepare diagnostic"));return false;}
        const auto& Oracle=Expected->GetArrayField(TEXT("frames"));const int32 Count=Prepared->GetIntegerField(TEXT("frames"));
        if(Count!=Oracle.Num()){AddError(Name+TEXT(": frame count differs"));return false;}
        double MaxPosition=0,MaxRoot=0,MaxAngle=0,MaxContactPoint=0,MaxSlideContactPoint=0,MaxTarget=0;int32 WorstFrame=-1,WorstBone=-1,StateDifferences=0,ContactDifferences=0,SlideContactDifferences=0,ModeDifferences=0,FirstState=-1,FirstContact=-1,FirstSlideContact=-1,FirstMode=-1;
        const double Thresholds[]={1.e-7,1.e-5,1.e-4,1.e-3,1.e-2};int32 FirstAbove[]={-1,-1,-1,-1,-1};
        for(int32 Start=0;Start<Count;Start+=24){
            const int32 BatchCount=FMath::Min(24,Count-Start);
            if(!VM.Command(FString::Printf(TEXT("{\"op\":\"frames\",\"start\":%d,\"count\":%d}"),Start,BatchCount),Result,Error)){AddError(Error);return false;}
            const auto Batch=ArrayResult(Result,TEXT("frames"));if(!Batch.IsValid()||Batch->AsArray().Num()!=BatchCount){AddError(TEXT("Invalid frame batch"));return false;}
            auto FrameRecord=MakeShared<FJsonObject>();FrameRecord->SetNumberField(TEXT("start"),Start);FrameRecord->SetField(TEXT("frames"),Batch);Captured=AppendDiagnostic(FramesFile,FrameRecord)&&Captured;
            for(int32 J=0;J<BatchCount;++J){
                const int32 Index=Start+J;const auto A=Batch->AsArray()[J]->AsObject(),E=Oracle[Index]->AsObject();
                const auto AP=A->GetObjectField(TEXT("pose")),EP=E->GetObjectField(TEXT("pose"));
                const auto& AX=AP->GetArrayField(TEXT("points"));const auto& EX=EP->GetArrayField(TEXT("points"));
                const auto& AQ=AP->GetArrayField(TEXT("q"));const auto& EQ=EP->GetArrayField(TEXT("q"));
                if(AX.Num()!=EX.Num()||AQ.Num()!=EQ.Num()){AddError(TEXT("Invalid pose dimensions"));return false;}
                for(int32 Bone=0;Bone<AX.Num();++Bone){
                    const double Distance=VectorError(AX[Bone],EX[Bone]);
                    double Dot=0,NA=0,NE=0;for(int32 K=0;K<4;++K){const double X=AQ[Bone]->AsArray()[K]->AsNumber(),Y=EQ[Bone]->AsArray()[K]->AsNumber();Dot+=X*Y;NA+=X*X;NE+=Y*Y;}
                    const double Angle=2*FMath::Acos(FMath::Clamp(FMath::Abs(Dot)/FMath::Sqrt(NA*NE),0.0,1.0))*180/UE_DOUBLE_PI;
                    if(!FMath::IsFinite(Distance)||!FMath::IsFinite(Angle)){AddError(Name+TEXT(": non-finite displayed pose"));return false;}
                    if(Distance>MaxPosition){MaxPosition=Distance;WorstFrame=Index;WorstBone=Bone;}MaxAngle=FMath::Max(MaxAngle,Angle);
                    for(int32 T=0;T<UE_ARRAY_COUNT(Thresholds);++T)if(FirstAbove[T]<0&&Distance>Thresholds[T])FirstAbove[T]=Index;
                }
                MaxRoot=FMath::Max(MaxRoot,VectorError(A->Values.FindRef(TEXT("root")),E->Values.FindRef(TEXT("root"))));
                const auto& AF=A->GetArrayField(TEXT("feet"));const auto& EF=E->GetArrayField(TEXT("feet"));
                for(int32 Side=0;Side<FMath::Min(AF.Num(),EF.Num());++Side){
                    const auto AFoot=AF[Side]->AsObject(),EFoot=EF[Side]->AsObject();
                    if(AFoot->GetStringField(TEXT("state"))!=EFoot->GetStringField(TEXT("state"))){++StateDifferences;if(FirstState<0)FirstState=Index;}
                    if(ContactKey(AFoot,TEXT("contact"))!=ContactKey(EFoot,TEXT("contact"))){++ContactDifferences;if(FirstContact<0)FirstContact=Index;}
                    if(ContactKey(AFoot,TEXT("slideContact"))!=ContactKey(EFoot,TEXT("slideContact"))){++SlideContactDifferences;if(FirstSlideContact<0)FirstSlideContact=Index;}
                    if(AFoot->HasTypedField<EJson::Array>(TEXT("target"))&&EFoot->HasTypedField<EJson::Array>(TEXT("target")))MaxTarget=FMath::Max(MaxTarget,VectorError(AFoot->Values.FindRef(TEXT("target")),EFoot->Values.FindRef(TEXT("target"))));
                    for(const FString Field:{TEXT("contact"),TEXT("slideContact")})if(AFoot->HasTypedField<EJson::Object>(Field)&&EFoot->HasTypedField<EJson::Object>(Field)){
                        const auto AC=AFoot->GetObjectField(Field),EC=EFoot->GetObjectField(Field);if(AC->HasTypedField<EJson::Array>(TEXT("point"))&&EC->HasTypedField<EJson::Array>(TEXT("point"))){const double D=VectorError(AC->Values.FindRef(TEXT("point")),EC->Values.FindRef(TEXT("point")));if(Field==TEXT("slideContact"))MaxSlideContactPoint=FMath::Max(MaxSlideContactPoint,D);else MaxContactPoint=FMath::Max(MaxContactPoint,D);}
                    }
                }
                if(A->GetObjectField(TEXT("surface"))->GetStringField(TEXT("mode"))!=E->GetObjectField(TEXT("surface"))->GetStringField(TEXT("mode"))){++ModeDifferences;if(FirstMode<0)FirstMode=Index;}
            }
        }
        auto Item=MakeShared<FJsonObject>();Item->SetStringField(TEXT("name"),Name);Item->SetBoolField(TEXT("nativeSourceInitialization"),NativeSource);Item->SetNumberField(TEXT("frames120Hz"),Count);Item->SetNumberField(TEXT("nnCalls"),NNCalls);Item->SetNumberField(TEXT("maxPositionM"),MaxPosition);Item->SetNumberField(TEXT("maxRootM"),MaxRoot);Item->SetNumberField(TEXT("maxJointDegrees"),MaxAngle);Item->SetNumberField(TEXT("worstFrame120Hz"),WorstFrame);Item->SetNumberField(TEXT("worstBone"),WorstBone);Item->SetNumberField(TEXT("footStateDisagreements"),StateDifferences);Item->SetNumberField(TEXT("contactDisagreements"),ContactDifferences);Item->SetNumberField(TEXT("rootModeDisagreements"),ModeDifferences);Item->SetNumberField(TEXT("firstStateFrame120Hz"),FirstState);Item->SetNumberField(TEXT("firstContactFrame120Hz"),FirstContact);
        Item->SetStringField(TEXT("capturePrefix"),Prefix);Item->SetBoolField(TEXT("captured"),Captured);Item->SetNumberField(TEXT("slideContactDisagreements"),SlideContactDifferences);Item->SetNumberField(TEXT("firstSlideContactFrame120Hz"),FirstSlideContact);Item->SetNumberField(TEXT("firstRootModeFrame120Hz"),FirstMode);Item->SetNumberField(TEXT("maxContactPointM"),MaxContactPoint);Item->SetNumberField(TEXT("maxSlideContactPointM"),MaxSlideContactPoint);Item->SetNumberField(TEXT("maxFootTargetM"),MaxTarget);
        TArray<TSharedPtr<FJsonValue>> Crossings;for(int32 T=0;T<UE_ARRAY_COUNT(Thresholds);++T){auto Crossing=MakeShared<FJsonObject>();Crossing->SetNumberField(TEXT("thresholdM"),Thresholds[T]);Crossing->SetNumberField(TEXT("firstFrame120Hz"),FirstAbove[T]);Crossings.Add(MakeShared<FJsonValueObject>(Crossing));}Item->SetArrayField(TEXT("positionThresholdCrossings"),Crossings);
        Cases.Add(MakeShared<FJsonValueObject>(Item));Report->SetArrayField(TEXT("cases"),Cases);FFileHelper::SaveStringToFile(Encode(Report),*(Directory/TEXT("native-nn-closed-loop-diagnostic.json")));
        AddInfo(FString::Printf(TEXT("Diagnostic %s nativeSource=%d: pose %.9gm root %.9gm rotation %.9gdeg states %d contacts %d slide contacts %d modes %d"),*Name,NativeSource,MaxPosition,MaxRoot,MaxAngle,StateDifferences,ContactDifferences,SlideContactDifferences,ModeDifferences));
        if(!Captured)AddError(Name+TEXT(": failed to retain diagnostic evidence"));
        if(StateDifferences||ContactDifferences||SlideContactDifferences||ModeDifferences)AddError(Name+TEXT(": native NN changed a contact/state/transition; inspect retained first-divergence evidence"));
    }
    AddWarning(TEXT("CoupledNativeNNDiagnostic requires exact semantic behavior but still reports continuous NN drift separately. Completion is not a numerical 1:1 pass. Read native-nn-closed-loop-diagnostic.json and native-nn-captures."));
    return !HasAnyErrors();
}
#endif
