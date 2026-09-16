#include "ProphecyInputRecorder.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"
#include "UObject/UnrealType.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyInputRecorderCodecTest, "Prophecy.Debug.InputRecorder.Codec",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyInputRecorderCodecTest::RunTest(const FString&)
{
    FProphecyReplayedInput Input;
    int32 Index=0;
    for (TFieldIterator<FBoolProperty> It(FProphecyReplayedInput::StaticStruct()); It; ++It)
        It->SetPropertyValue_InContainer(&Input, (++Index % 3) != 0);
    Input.Gamepad_LeftX=-.375f; Input.Gamepad_RightY=.8125f; Input.Gamepad_RightTriggerAxis=.456789f;
    Input.Gamepad_Special_Left_X=-.875f; Input.Tilt=FVector(.12345,-.5,1.25);
    Input.RotationRate=FVector(-.4,.321,-.12); Input.Gravity=FVector(0,0,-1); Input.Acceleration=FVector(1,2,3);
    TArray<uint8> Bytes;
    FMemoryWriter Writer(Bytes); Input.SerializeFrame(Writer);
    TestEqual(TEXT("Version-one frame has stable packed size"),Bytes.Num(),144);
    FProphecyReplayedInput Output; FMemoryReader Reader(Bytes); Output.SerializeFrame(Reader);
    TestFalse(TEXT("Valid frame decodes without error"),Reader.IsError());
    TestTrue(TEXT("Every bool, analog and motion channel survives exactly"),
        FProphecyReplayedInput::StaticStruct()->CompareScriptStruct(&Input,&Output,0));
    Bytes.SetNum(Bytes.Num()-1);
    FMemoryReader Truncated(Bytes); Output.SerializeFrame(Truncated);
    TestTrue(TEXT("Truncated frame is rejected"),Truncated.IsError());
    return !HasAnyErrors();
}
#endif
