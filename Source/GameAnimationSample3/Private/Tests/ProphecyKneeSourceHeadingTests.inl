// Captured supporting-leg handoff; independent NN foot yaw must not swivel
// the knee of a tempered foot which has not made that turn.
#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySupportHeadingFrameTest,
    "Prophecy.NN.LowerTempering.SupportHeadingFrame",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySupportHeadingFrameTest::RunTest(const FString&)
{
    const float Previous[41]={-2.661719918e-06f,-2.736225724e-06f,0.9864915013f,-0.03781506047f,0.8417391777f,0.5385586023f,0.8838850856f,0.2795957625f,-0.3749314249f,0.01348114572f,-0.7160716057f,1.295395017f,-0.0196670033f,0.9062265158f,0.4223348498f,0.2382956743f,0.4144918025f,-0.878300488f,0.1480872184f,0.6447983384f,-0.7498701811f,0.275118351f,-0.7551599145f,-0.5950154662f,-1.f,0.1018429995f,0.09590116143f,0.09755589068f,0.008753648959f,-0.04003409669f,-0.9991599917f,-0.7761613131f,0.629720211f,-0.03203143179f,-0.01515630074f,0.06758543104f,-0.99759835f,-0.9846718907f,-0.1743890494f,0.00314537785f,-0.9246169925f};
    const float Source[41]={-0.004497542046f,-0.01958067529f,0.9901415706f,-0.1477288455f,0.4838413596f,0.8625971079f,0.7347930074f,0.6374799013f,-0.231729269f,-0.1204243079f,-0.471137464f,1.09706831f,-0.1809048653f,0.3358987868f,0.9243621826f,0.1692270339f,0.9364827871f,-0.3071841896f,0.2365620583f,0.9173454046f,-0.3201811314f,0.3725744188f,-0.3899891973f,-0.842078805f,-1.f,0.003008849919f,0.08734481037f,0.108939372f,0.03321046755f,0.1551918387f,-0.9873259664f,-0.8498702049f,-0.5154672265f,-0.1096101031f,-0.005783112254f,-0.08551677316f,-0.9963200092f,-0.8281731606f,-0.5579891205f,0.05270076916f,-1.f};
    const float Initial[41]={-0.002250101883f,-0.009791705757f,0.9883165359f,-0.05409058183f,0.8146381378f,0.577441752f,0.8728075027f,0.3194872141f,-0.3689650297f,-0.08019529283f,-0.5447689891f,1.156566381f,-0.1391124427f,0.5486430526f,0.8244019151f,0.2032948732f,0.8305875659f,-0.5184549093f,0.002819150686f,0.4049649835f,-0.9143278003f,-0.2199722826f,-0.8916847706f,-0.395614326f,-1.f,0.09966712445f,0.1005388945f,0.1047274843f,0.02198527381f,-0.02368854918f,-0.9994776249f,-0.8475085497f,0.5298641324f,-0.03120071813f,-0.005783112254f,-0.08551677316f,-0.9963200092f,-0.8281731606f,-0.5579891205f,0.05270078778f,-0.9321553111f};
    auto F=ProphecyStanceGeometryFixtures::Fixtures[0];
    F.Geometry.CalfLength=0.4541135132f;F.Geometry.MinimumAnkleZ=0.09782201052f;
    const ProphecyLowerTempering::FSettings Settings{.1f,.1f,.5f,.1f,.63f,.5f};
    float Baseline[41];FMemory::Memcpy(Baseline,Initial,sizeof(Baseline));
    ResolveTemperedLeg(Settings,Previous,F.Geometry,Baseline,25,F.Forward,F.Up,.15f,false,Source);
    const FVector3f Hip=ReadStateVec3(Source,0)+TransformRow(F.Geometry.HipOffset,MatrixFromRot6(Source+3));
    for (float Yaw:{-.8f,-.2f,.3f,1.2f,3.1f})
    {
        float Other[41],Result[41];FMemory::Memcpy(Other,Source,sizeof(Other));FMemory::Memcpy(Result,Initial,sizeof(Result));
        const FMat3f Turn=AxisAngleMatrix(FVector3f(0,0,1),Yaw);
        WriteStateVec3(Other,25,Hip+TransformRow(ReadStateVec3(Source,25)-Hip,Turn));
        for(int O:{28,34})WriteRot6(Multiply(MatrixFromRot6(Source+O),Turn),Other+O);
        ResolveTemperedLeg(Settings,Previous,F.Geometry,Result,25,F.Forward,F.Up,.15f,false,Other);
        TestTrue(TEXT("Same source stance in another foot heading gives same presented knee"),
            MatrixToQuat(MatrixFromRot6(Result+34)).AngularDistance(MatrixToQuat(MatrixFromRot6(Baseline+34)))<1.e-4);
        TestEqual(TEXT("Pelvis unchanged"),FMemory::Memcmp(Result,Initial,9*sizeof(float)),0);
        TestTrue(TEXT("Reachable ankle retained"),ReadStateVec3(Result,25).Equals(ReadStateVec3(Initial,25),1.e-6));
        TestEqual(TEXT("Foot rotation retained"),FMemory::Memcmp(Result+28,Initial+28,6*sizeof(float)),0);
        const FVector3f TargetHip=ReadStateVec3(Result,0)+TransformRow(F.Geometry.HipOffset,MatrixFromRot6(Result+3));
        const FVector3f Knee=TargetHip+TransformRow(F.Geometry.KneeOffset,MatrixFromRot6(Result+34));
        TestTrue(TEXT("Returning calf length retained"),FMath::Abs((ReadStateVec3(Result,25)-Knee).Size()-F.Geometry.CalfLength)<1.e-5);
    }
    FQuat NearVertical[2];
    for(int I=0;I<2;++I)
    {
        float Other[41],Result[41];FMemory::Memcpy(Other,Source,sizeof(Other));FMemory::Memcpy(Result,Initial,sizeof(Result));
        const FVector3f Toe=SafeNormal(FVector3f(I ? .00001f : -.00001f,0,1));
        WriteRot6(QuatToMatrix(FQuat::FindBetweenNormals(FVector(SafeNormal(F.Forward)),FVector(Toe))),Other+28);
        ResolveTemperedLeg(Settings,Previous,F.Geometry,Result,25,F.Forward,F.Up,.15f,false,Other);
        NearVertical[I]=MatrixToQuat(MatrixFromRot6(Result+34));
    }
    TestTrue(TEXT("Ambiguous NN heading fades without a sign flip"),NearVertical[0].AngularDistance(NearVertical[1])<1.e-5);
    return !HasAnyErrors();
}
#endif
