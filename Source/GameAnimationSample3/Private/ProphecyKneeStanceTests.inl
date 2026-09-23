// Geometry contracts: included after ProphecyLowerTempering.inl in its namespace.
// Fixtures use recorded world-independent local geometry; no attack/family annotations.
#if WITH_DEV_AUTOMATION_TESTS
namespace ProphecyStanceGeometryFixtures
{
struct FFixture
{
    ProphecyLowerTempering::FSettings Settings;
    FPelvisLegGeometry Geometry;
    FVector3f Forward,Up;
    int32 Offset;
    float Previous[25],Source[25],Target[25];
};
static const FFixture Fixtures[]={
    // PelvisHitch-20260921-172254 policy tick 127
    {
        ProphecyLowerTempering::FSettings{0.1000000015f,0.1000000015f,0.5f,0.1000000015f,0.6299999952f,0.5f},
        {FVector3f(-0.025693262f,0.0001087198034f,0.07750071585f),FVector3f(0.3886490762f,0.001097515225f,4.229974002e-05f),FVector3f(-0.0005922729033f,0.9968895912f,0.07880944759f),0.4256333665f,0.09416952969f},
        FVector3f(0.06159852445f,0.1382641196f,-0.006806043908f),FVector3f(-1.f,0.f,0.f),25,
        {0.1476491988f,-0.07896074653f,0.7645903826f,-0.1314558536f,-0.3578884304f,0.924464941f,0.8542250991f,0.432297051f,0.2888232768f,-0.1016688421f,-0.08496825397f,0.0936396271f,0.0172103364f,-0.01220952719f,-0.9997774363f,0.2103519142f,-0.9775019884f,0.01555852685f,-0.1853425205f,-0.6341214776f,-0.7506917119f,-0.06605115533f,-0.754160881f,0.6533596516f,-0.9767647386f},
        {0.1208560858f,-0.03368096054f,0.8137859106f,-0.08516788053f,-0.2667271518f,0.960001593f,0.6649475759f,0.7023277908f,0.2541267314f,-0.1089698346f,-0.0922405934f,0.04080112651f,0.01330532512f,0.06628885962f,-0.9977117597f,0.03752741764f,-0.9971302131f,-0.06574976148f,-0.177178044f,-0.558564384f,-0.8103170797f,-0.05332073809f,-0.8166861749f,0.5746134272f,-1.f},
        {0.1342526376f,-0.05632085353f,0.7891881466f,-0.1255207807f,-0.3496804535f,0.9284223914f,0.8390574455f,0.4619239569f,0.2874175906f,-0.1023989469f,-0.08569549024f,0.09416952729f,0.01620409451f,-0.004400236066f,-0.999859035f,0.1932933927f,-0.9811127186f,0.007450322155f,0.1103859693f,-0.4368302226f,-0.8927452564f,0.6448119879f,-0.6520611048f,0.3987904787f,-0.9790882468f}
    },
    // PelvisHitch-20260920-203359 policy tick 149
    {
        ProphecyLowerTempering::FSettings{0.1000000015f,0.1000000015f,0.5f,0.1000000015f,0.6299999952f,0.5f},
        {FVector3f(-0.025693262f,0.0001087198034f,0.07750071585f),FVector3f(0.3886490762f,0.001097515225f,4.229974002e-05f),FVector3f(-0.0005922729033f,0.9968895912f,0.07880944759f),0.4256333665f,0.1051705417f},
        FVector3f(0.06159852445f,0.1382641196f,-0.006806043908f),FVector3f(-1.f,0.f,0.f),25,
        {0.05025758222f,0.372923404f,0.9590232372f,-0.06501671672f,0.7730132937f,0.6310493946f,-0.8652522564f,0.2713571191f,-0.4215494394f,0.04552213848f,-0.4017946422f,1.16553247f,-0.08123664558f,-0.717443347f,-0.6918640137f,0.1870896667f,-0.6927958131f,0.696442008f,0.143892765f,-0.8121746182f,0.5653912425f,0.2964183986f,0.5804777741f,0.7584073544f,-1.f},
        {0.05417554686f,0.2760252953f,0.9352192879f,-0.01141638371f,0.2646751258f,0.9642700576f,-0.5613019974f,0.7963723796f,-0.2252356557f,-0.02079271525f,-0.2870433629f,0.907464534f,-0.03256286347f,0.03421660127f,-0.9988838191f,0.1817058126f,-0.9825560342f,-0.03958076891f,-0.08032302922f,-0.7158986712f,-0.6935685284f,0.06003162338f,-0.6980281369f,0.7135495247f,-1.f},
        {0.0522165671f,0.3244743347f,0.9471212626f,-0.04720109701f,0.7344665527f,0.6770014167f,-0.844001174f,0.3331777751f,-0.4203029871f,0.03889065236f,-0.390319556f,1.002949715f,-0.07681061327f,-0.6571569443f,-0.7498298883f,0.1847754717f,-0.7484066486f,0.6369816661f,0.1429112256f,-0.7491756082f,0.6467706561f,0.1697477251f,0.6623485088f,0.7297124863f,-1.f}
    }
};
static void Expand(const float (&Compact)[25],int32 Offset,float (&State)[41])
{
    FMemory::Memzero(State);
    for (int32 O : {3,12,18,28,34}) WriteRot6(FMat3f{},State+O);
    FMemory::Memcpy(State,Compact,9*sizeof(float));FMemory::Memcpy(State+Offset,Compact+9,16*sizeof(float));
}
struct FScopedCandidate
{
#if WITH_EDITOR
    IConsoleVariable* Variable=IConsoleManager::Get().FindConsoleVariable(TEXT("Prophecy.Tempering.KneePlane"));
    int32 Previous=Variable ? Variable->GetInt() : 1;
    FScopedCandidate() { if (Variable) Variable->Set(1,ECVF_SetByConsole); }
    ~FScopedCandidate() { if (Variable) Variable->Set(Previous,ECVF_SetByConsole); }
#endif
};
static float SideOffset(const FFixture& F,const float* State)
{
    const FVector3f Toe=TransformRow(SafeNormal(F.Forward),MatrixFromRot6(State+F.Offset+3));
    const FVector3f Forward=SafeNormal(FVector3f(Toe.X,Toe.Y,0));
    return FVector3f::DotProduct(TransformRow(F.Geometry.KneeOffset,MatrixFromRot6(State+F.Offset+9)),FVector3f(-Forward.Y,Forward.X,0));
}
static void Connect(const FFixture& F,float* State,const float* Previous)
{
    ResolvePelvisLeg(ReadStateVec3(Previous,0),MatrixFromRot6(Previous+3),ReadStateVec3(State,0),MatrixFromRot6(State+3),
        F.Geometry,State,F.Offset,Previous,false,nullptr,.15f,false);
}
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyStancePlaneIdentityTest,
    "Prophecy.NN.LowerTempering.StancePlaneIdentity",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyStancePlaneIdentityTest::RunTest(const FString&)
{
    using namespace ProphecyStanceGeometryFixtures;
    FScopedCandidate Candidate;
    auto F=Fixtures[0];
    float Coherent[41];Expand(F.Previous,F.Offset,Coherent);
    F.Geometry.MinimumAnkleZ=ReadStateVec3(Coherent,F.Offset).Z-1.e-4f;
    // The recorded source has slight calf stretch. Make it connected once
    // before testing identity; repairing that stretch is not an identity case.
    Connect(F,Coherent,Coherent);
    for (int32 Branch=0;Branch<2;++Branch)
    {
        float Source[41];FMemory::Memcpy(Source,Coherent,sizeof(Source));
        if (Branch)
        {
            const FVector3f Hip=ReadStateVec3(Source,0)+TransformRow(F.Geometry.HipOffset,MatrixFromRot6(Source+3));
            const FVector3f Axis=SafeNormal(ReadStateVec3(Source,F.Offset)-Hip);
            WriteRot6(Multiply(MatrixFromRot6(Source+F.Offset+9),AxisAngleMatrix(Axis,PI)),Source+F.Offset+9);
        }
        for (float Follow : {.01f,.25f,.75f,1.f})
        {
            float Target[41];FMemory::Memcpy(Target,Source,sizeof(Target));
            auto S=F.Settings;S.FeetRotation=Follow;
            ResolveTemperedLeg(S,Source,F.Geometry,Target,F.Offset,F.Forward,F.Up,.15f,false,Source);
            TestTrue(TEXT("Either coherent radial branch is an identity"),MatrixToQuat(MatrixFromRot6(Target+F.Offset+9)).AngularDistance(
                MatrixToQuat(MatrixFromRot6(Source+F.Offset+9)))<3.e-5);
            TestTrue(TEXT("Identity keeps the ankle"),ReadStateVec3(Target,F.Offset).Equals(ReadStateVec3(Source,F.Offset),2.e-6f));
            TestEqual(TEXT("Identity keeps pelvis"),FMemory::Memcmp(Target,Source,9*sizeof(float)),0);
            TestEqual(TEXT("Identity keeps foot rotation"),FMemory::Memcmp(Target+F.Offset+3,Source+F.Offset+3,6*sizeof(float)),0);
            TestTrue(TEXT("Identity preserves the source knee-plane offset"),FMath::Abs(SideOffset(F,Target)-SideOffset(F,Source))<3.e-6f);
        }
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyStancePlaneConnectedRegressionTest,
    "Prophecy.NN.LowerTempering.StancePlaneConnectedRegression",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyStancePlaneConnectedRegressionTest::RunTest(const FString&)
{
    using namespace ProphecyStanceGeometryFixtures;
    FScopedCandidate Candidate;
    const auto& F=Fixtures[0];
    float Previous[41],Source[41],Initial[41],Target[41];
    Expand(F.Previous,F.Offset,Previous);Expand(F.Source,F.Offset,Source);Expand(F.Target,F.Offset,Initial);
    FMemory::Memcpy(Target,Initial,sizeof(Target));
    ResolveTemperedLeg(F.Settings,Previous,F.Geometry,Target,F.Offset,F.Forward,F.Up,.15f,false,Source);
    // Independent double-precision fixture evaluation. Hinge/twist admission
    // follows FeetRotation once, just like the stance offset. The final plane
    // correction follows that authored amount too instead of overriding it.
    const float Expected[6]={-.176451077f,-.590883095f,-.787224355f,-.073765539f,-.789586165f,.609189899f};
    TestTrue(TEXT("Wide stance matches independent geometry"),MatrixToQuat(MatrixFromRot6(Target+F.Offset+9)).AngularDistance(
        MatrixToQuat(MatrixFromRot6(Expected)))<3.e-5);
    const float Step=FMath::RadiansToDegrees(MatrixToQuat(MatrixFromRot6(Target+F.Offset+9)).AngularDistance(
        MatrixToQuat(MatrixFromRot6(Previous+F.Offset+9))));
    TestTrue(TEXT("Recorded large snap becomes the independently predicted 3.29 degree step"),FMath::Abs(Step-3.287029f)<.03f);
    const FVector3f Hip=ReadStateVec3(Target,0)+TransformRow(F.Geometry.HipOffset,MatrixFromRot6(Target+3));
    const FVector3f Knee=Hip+TransformRow(F.Geometry.KneeOffset,MatrixFromRot6(Target+F.Offset+9));
    const FVector3f Foot=ReadStateVec3(Target,F.Offset);
    TestTrue(TEXT("Reference thigh length retained"),FMath::Abs((Knee-Hip).Size()-F.Geometry.KneeOffset.Size())<3.e-6f);
    TestTrue(TEXT("Reference calf length retained"),FMath::Abs((Foot-Knee).Size()-F.Geometry.CalfLength)<3.e-6f);
    TestTrue(TEXT("Pinned ankle and floor retained"),Foot.Equals(ReadStateVec3(Initial,F.Offset),3.e-6f)&&Foot.Z>=F.Geometry.MinimumAnkleZ-3.e-6f);
    TestEqual(TEXT("Pelvis untouched"),FMemory::Memcmp(Target,Initial,9*sizeof(float)),0);
    TestEqual(TEXT("Foot rotation untouched"),FMemory::Memcmp(Target+F.Offset+3,Initial+F.Offset+3,6*sizeof(float)),0);
    TestEqual(TEXT("Other leg untouched"),FMemory::Memcmp(Target+9,Initial+9,16*sizeof(float)),0);
    TestEqual(TEXT("Toe untouched"),Target[F.Offset+15],Initial[F.Offset+15]);
    FQuat Last=FQuat::Identity;
    // Double-precision reference values after partial plane guidance, not a
    // demand to reach the plane instantly while following only one quarter.
    const float ExpectedOffsets[]={-.122153614f,-.121991295f,-.121822075f,-.121645956f,-.121462939f};
    for (int32 I=0;I<=4;++I)
    {
        const float Follow=.23f+.01f*I;
        auto S=F.Settings;S.FeetRotation=Follow;
        FMemory::Memcpy(Target,Initial,sizeof(Target));
        ResolveTemperedLeg(S,Previous,F.Geometry,Target,F.Offset,F.Forward,F.Up,.15f,false,Source);
        TestTrue(TEXT("Quarter following matches gradual stance guidance"),FMath::Abs(SideOffset(F,Target)-ExpectedOffsets[I])<5.e-6f);
        const FQuat Current=MatrixToQuat(MatrixFromRot6(Target+F.Offset+9));
        if (I) TestTrue(TEXT("Small quarter-follow changes are continuous"),Current.AngularDistance(Last)<.02);
        Last=Current;
    }
    auto Frozen=F.Settings;Frozen.FeetRotation=0;
    float NullSource[41];FMemory::Memcpy(Target,Initial,sizeof(Target));FMemory::Memcpy(NullSource,Initial,sizeof(NullSource));
    ResolveTemperedLeg(Frozen,Previous,F.Geometry,Target,F.Offset,F.Forward,F.Up,.15f,false,Source);
    ResolveTemperedLeg(Frozen,Previous,F.Geometry,NullSource,F.Offset,F.Forward,F.Up,.15f,false,nullptr);
    TestEqual(TEXT("Zero following ignores NN source bit for bit"),FMemory::Memcmp(Target,NullSource,sizeof(Target)),0);
    // Previously any positive value applied the full final plane correction,
    // so arbitrarily small following jumped away from the exact frozen solve.
    auto NearlyFrozen=Frozen;NearlyFrozen.FeetRotation=1.e-6f;
    FMemory::Memcpy(NullSource,Initial,sizeof(NullSource));
    ResolveTemperedLeg(NearlyFrozen,Previous,F.Geometry,NullSource,F.Offset,F.Forward,F.Up,.15f,false,Source);
    TestTrue(TEXT("Final plane guidance is continuous at zero following"),MatrixToQuat(MatrixFromRot6(Target+F.Offset+9)).AngularDistance(
        MatrixToQuat(MatrixFromRot6(NullSource+F.Offset+9)))<1.e-4);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyStancePlaneRaisedSourceTest,
    "Prophecy.NN.LowerTempering.StancePlaneRaisedSource",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyStancePlaneRaisedSourceTest::RunTest(const FString&)
{
    using namespace ProphecyStanceGeometryFixtures;
    FScopedCandidate Candidate;
    const auto& F=Fixtures[1];
    float Previous[41],Source[41],Target[41],Reversed[41],WithoutNN[41];
    Expand(F.Previous,F.Offset,Previous);Expand(F.Source,F.Offset,Source);Expand(F.Target,F.Offset,Target);
    FMemory::Memcpy(Reversed,Target,sizeof(Target));FMemory::Memcpy(WithoutNN,Target,sizeof(Target));
    const FVector3f SourceHip=ReadStateVec3(Source,0)+TransformRow(F.Geometry.HipOffset,MatrixFromRot6(Source+3));
    const FVector3f Axis=SafeNormal(ReadStateVec3(Source,F.Offset)-SourceHip);
    ResolveTemperedLeg(F.Settings,Previous,F.Geometry,Target,F.Offset,F.Forward,F.Up,.15f,false,Source);
    WriteRot6(Multiply(MatrixFromRot6(Source+F.Offset+9),AxisAngleMatrix(Axis,PI)),Source+F.Offset+9);
    ResolveTemperedLeg(F.Settings,Previous,F.Geometry,Reversed,F.Offset,F.Forward,F.Up,.15f,false,Source);
    ResolveTemperedLeg(F.Settings,Previous,F.Geometry,WithoutNN,F.Offset,F.Forward,F.Up,.15f,false,nullptr);
    TestEqual(TEXT("Raised foot rejects opposite NN knee pole bit for bit"),FMemory::Memcmp(Target,Reversed,sizeof(Target)),0);
    TestEqual(TEXT("Raised foot uses coherent prior source only"),FMemory::Memcmp(Target,WithoutNN,sizeof(Target)),0);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyStancePlaneDegeneracyTest,
    "Prophecy.NN.LowerTempering.StancePlaneDegeneracy",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyStancePlaneDegeneracyTest::RunTest(const FString&)
{
    using namespace ProphecyStanceGeometryFixtures;
    FScopedCandidate Candidate;
    const auto& F=Fixtures[0];
    float Previous[41],Initial[41],Target[41],Connected[41];
    Expand(F.Previous,F.Offset,Previous);Expand(F.Target,F.Offset,Initial);
    // A plane can become unreachable as the knee circle collapses. Retain
    // connected transport rather than normalizing an imaginary intersection.
    FMemory::Memcpy(Target,Initial,sizeof(Target));
    const FVector3f Hip=ReadStateVec3(Target,0)+TransformRow(F.Geometry.HipOffset,MatrixFromRot6(Target+3));
    WriteStateVec3(Target,F.Offset,Hip+FVector3f(F.Geometry.KneeOffset.Size()+F.Geometry.CalfLength-4.e-5f,0,0));
    FMemory::Memcpy(Connected,Target,sizeof(Target));Connect(F,Connected,Previous);
    ResolveTemperedLeg(F.Settings,Previous,F.Geometry,Target,F.Offset,F.Forward,F.Up,.15f,false,nullptr);
    TestTrue(TEXT("Infeasible plane falls back to finite connected transport"),MatrixToQuat(MatrixFromRot6(Target+F.Offset+9)).AngularDistance(
        MatrixToQuat(MatrixFromRot6(Connected+F.Offset+9)))<3.e-5);
    for (float V : Target) TestTrue(TEXT("Infeasible plane remains finite"),FMath::IsFinite(V));
    // A tiny physical rotation across a vertical SOURCE toe direction must not
    // create a 180-degree source heading / stance-offset sign switch.
    FQuat SideResults[2];
    for (int32 I=0;I<2;++I)
    {
        float NearVertical[41];FMemory::Memcpy(NearVertical,Previous,sizeof(Previous));
        const FVector3f Toe=SafeNormal(FVector3f(I ? .001f : -.001f,0,1));
        WriteRot6(QuatToMatrix(FQuat::FindBetweenNormals(FVector(SafeNormal(F.Forward)),FVector(Toe))),NearVertical+F.Offset+3);
        FMemory::Memcpy(Target,Initial,sizeof(Target));
        ResolveTemperedLeg(F.Settings,NearVertical,F.Geometry,Target,F.Offset,F.Forward,F.Up,.15f,false,nullptr);
        SideResults[I]=MatrixToQuat(MatrixFromRot6(Target+F.Offset+9));
    }
    TestTrue(TEXT("Near-vertical source heading crossing does not create a knee jump"),SideResults[0].AngularDistance(SideResults[1])<FMath::DegreesToRadians(1.));
    return !HasAnyErrors();
}
#endif
#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCalfTemperingTest,
    "Prophecy.NN.LowerTempering.CalfTwistContinuity",EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyCalfTemperingTest::RunTest(const FString&)
{
    const FVector Axis=FVector(.2,-.9,.05).GetSafeNormal();
    const FQuat Previous(FVector::UpVector,.7);
    const FQuat Swing(FVector::RightVector,.15);
    const FQuat Carried=(Swing*Previous).GetNormalized();
    const FVector Aim=Carried.RotateVector(Axis);
    const FQuat Decoded=(FQuat(Aim,.8)*Carried).GetNormalized();
    const FQuat Frozen=TemperCalfRotation(Previous,Decoded,Axis,0);
    for (float Follow:{0.f,.1f,.5f,.9f,1.f})
    {
        const FQuat Result=TemperCalfRotation(Previous,Decoded,Axis,Follow);
        TestTrue(TEXT("Following twist preserves the exact calf endpoint"),Result.RotateVector(Axis).Equals(Aim,1.e-6));
        TestTrue(TEXT("Finite normalized rotation"),!Result.ContainsNaN() && Result.IsNormalized());
        TestTrue(TEXT("Only twist difference is blended"),FMath::IsNearlyEqual(
            Result.AngularDistance(Decoded),Frozen.AngularDistance(Decoded)*(1.-Follow),1.e-6));
    }
    TestTrue(TEXT("Normal preserves decoder exactly"),TemperCalfRotation(Previous,Decoded,Axis,1)==Decoded);
    TestTrue(TEXT("Unchanged pose is a fixed point"),TemperCalfRotation(Previous,Previous,Axis,.1).Equals(Previous,1.e-6));
    FQuat Current=Previous;
    double LastError=Current.AngularDistance(Decoded);
    for (int32 I=0;I<30;++I)
    {
        Current=TemperCalfRotation(Current,Decoded,Axis,.1f);
        const double Error=Current.AngularDistance(Decoded);
        TestTrue(TEXT("Repeated following converges without oscillation"),Error<=LastError+1.e-6);
        LastError=Error;
    }
    TestTrue(TEXT("Repeated following approaches normal"),LastError<.04);
    return !HasAnyErrors();
}
#endif
