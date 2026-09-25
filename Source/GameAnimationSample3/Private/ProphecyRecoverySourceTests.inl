// Frozen current-scene recovery input at tick175; no replay timing dependency.
#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCleanRecoverySourceTest,
    "Prophecy.NN.LowerTempering.CleanRecoverySource",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyCleanRecoverySourceTest::RunTest(const FString&)
{
    const float Raw[41]={0.03096270561f,0.0581192039f,0.8413606817f,0.06993592617f,-0.05963476766f,0.9957673728f,0.6413006905f,0.7672891205f,0.0009110066299f,0.1111656725f,-0.1112999776f,0.1950188242f,-0.07451561209f,-0.0550058137f,0.9957016541f,-0.1177393667f,0.9919790649f,0.04598887073f,0.1990089278f,0.768806853f,0.6077264758f,0.2602345125f,0.5564090678f,-0.7891051564f,-1.f,-0.2831724212f,0.5209623799f,0.1129722968f,0.2858803236f,0.2712961333f,-0.9190597634f,-0.8947708088f,-0.2677334378f,-0.3573569727f,-0.4654451488f,0.3899645151f,-0.7945366514f,-0.8012237614f,-0.5670443242f,0.1910529208f,-1.f};
    const float Pinned[41]={0.03096270561f,0.0581192039f,0.8413606882f,0.0699359253f,-0.05963476375f,0.995767355f,0.6413007379f,0.7672891021f,0.0009109976236f,0.1111656725f,-0.1112999767f,0.1950188279f,-0.07451561838f,-0.05500582233f,0.9957017303f,-0.1177393869f,0.9919791818f,0.04598887637f,0.2205458134f,0.8114694953f,0.5411815047f,0.2430366278f,0.4916241765f,-0.836204946f,-1.f,-0.3407668769f,0.5545637012f,0.1819760203f,0.2858803272f,0.2712961435f,-0.9190597534f,-0.8947708011f,-0.2677334547f,-0.3573569655f,-0.3718967736f,0.5257425904f,-0.7650409937f,-0.8629959822f,-0.4994142652f,0.07631234825f,-1.f};
    const FPelvisLegGeometry G{FVector3f(-0.025693262f,0.0001087198034f,0.07750071585f),FVector3f(0.3886490762f,0.001097515225f,4.229974002e-05f),FVector3f(-0.0005922729033f,0.9968895912f,0.07880944759f),0.4514286855f,0.f};
    float Clean[41],Corrupted[41];FMemory::Memcpy(Clean,Pinned,sizeof(Clean));FMemory::Memcpy(Corrupted,Pinned,sizeof(Corrupted));
    FMemory::Memcpy(Corrupted+34,Raw+34,6*sizeof(float));
    const FVector3f P=ReadStateVec3(Pinned,0);const FMat3f R=MatrixFromRot6(Pinned+3);
    FVector3f CleanPole,OldPole;
    ResolvePelvisLeg(ReadStateVec3(Raw,0),MatrixFromRot6(Raw+3),P,R,G,Clean,25,Raw,false,&CleanPole);
    ResolvePelvisLeg(P,R,P,R,G,Corrupted,25,nullptr,false,&OldPole);
    const FVector3f H=P+TransformRow(G.HipOffset,R),Axis=SafeNormal(ReadStateVec3(Clean,25)-H);
    const FVector3f SourceH=ReadStateVec3(Raw,0)+TransformRow(G.HipOffset,MatrixFromRot6(Raw+3));
    const FVector3f SourceAxis=SafeNormal(ReadStateVec3(Raw,25)-SourceH);
    const FVector3f SourcePole=ProjectToPlane(TransformRow(G.KneeOffset,MatrixFromRot6(Raw+34)),SourceAxis);
    const FVector3f Expected=ProjectToPlane(SourcePole-(SourceAxis+Axis)*(FVector3f::DotProduct(SourcePole,Axis)/(1.f+FVector3f::DotProduct(SourceAxis,Axis))),Axis);
    TestTrue(TEXT("Unmodified NN hinge transports to the pinned endpoint"),FVector3f::DotProduct(CleanPole,Expected)>.99999f);
    const float Difference=FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector3f::DotProduct(CleanPole,OldPole),-1.f,1.f)));
    TestTrue(TEXT("Recorded post-pin source mixes incompatible frames"),Difference>20.f);
    TestTrue(TEXT("Pin position is preserved"),ReadStateVec3(Clean,25).Equals(ReadStateVec3(Pinned,25),1.e-5f));
    TestEqual(TEXT("Pelvis unchanged"),FMemory::Memcmp(Clean,Pinned,9*sizeof(float)),0);
    TestEqual(TEXT("Foot rotation unchanged"),FMemory::Memcmp(Clean+28,Pinned+28,6*sizeof(float)),0);
    TestEqual(TEXT("Other leg unchanged"),FMemory::Memcmp(Clean+9,Pinned+9,16*sizeof(float)),0);
    const FVector3f K=H+TransformRow(G.KneeOffset,MatrixFromRot6(Clean+34));
    TestTrue(TEXT("Calf remains connected"),FMath::Abs((ReadStateVec3(Clean,25)-K).Size()-G.CalfLength)<2.e-6f);
    AddInfo(FString::Printf(TEXT("Same endpoints: incompatible source changes knee pole by %.6f degrees"),Difference));
    return !HasAnyErrors();
}
#endif
