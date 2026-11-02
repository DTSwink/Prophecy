IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKHeldCommandTest,"Prophecy.FootIK.Live.HeldCommand",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKHeldCommandTest::RunTest(const FString&)
{
    FProphecyLocomotionInput Input;Input.WorldMoveInput=FVector::ForwardVector;Input.bRun=false;Input.SpeedScale=Input.TurnScale=1;
    const FVector Facing=FVector::RightVector;
    const auto Read=[&](FVector V=FVector(200,0,0),FVector F=FVector::RightVector,double T=1.,bool Blueprint=true)
    {return CaptureCommand(Blueprint,Input,V,F,Input.bRun,T);};
    const FCommand Held=Read();
    for(double Speed:{200.,195.,187.,180.})
        TestTrue(TEXT("One held turn survives its predicted directional speed-cap changes"),Held.Equals(Read(FVector(Speed,0,0))));
    Input.WorldMoveInput=-FVector::ForwardVector;TestFalse(TEXT("Movement reversal cancels"),Held.Equals(Read()));
    Input.WorldMoveInput=FVector(.5,0,0);TestFalse(TEXT("Stick magnitude change cancels"),Held.Equals(Read()));
    Input.WorldMoveInput=FVector::ForwardVector;Input.bRun=true;TestFalse(TEXT("Walk/run change cancels"),Held.Equals(Read()));
    Input.bRun=false;Input.SpeedScale=.5;TestFalse(TEXT("Speed tuning change cancels"),Held.Equals(Read()));
    Input.SpeedScale=1;Input.TurnScale=.5;TestFalse(TEXT("Turn tuning change cancels"),Held.Equals(Read()));
    Input.TurnScale=1;TestFalse(TEXT("Resolved heading change cancels"),Held.Equals(Read(FVector(200,0,0),FVector::ForwardVector)));
    TestFalse(TEXT("Agent time scale change cancels"),Held.Equals(Read(FVector(200,0,0),Facing,.5)));
    TestFalse(TEXT("Input owner change cancels"),Held.Equals(Read(FVector(200,0,0),Facing,1.,false)));
    TestFalse(TEXT("Non-Blueprint resolved-speed changes still cancel"),Read(FVector(200,0,0),Facing,1.,false).Equals(Read(FVector(180,0,0),Facing,1.,false)));
    return !HasAnyErrors();
}
