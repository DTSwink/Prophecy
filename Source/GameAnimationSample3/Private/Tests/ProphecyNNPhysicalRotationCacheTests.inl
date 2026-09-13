// Included only under WITH_DEV_AUTOMATION_TESTS in the manager's private translation unit.
namespace PhysicalRotationCacheTests
{
using FImpl = AProphecyNNLocomotionManager::FImpl;

TSharedPtr<FJsonObject> ReadContract(FAutomationTestBase& Test, const TCHAR* Filename)
{
    const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("locomotion/NN"), Filename);
    FString Text;
    TSharedPtr<FJsonObject> Root;
    if (!FFileHelper::LoadFileToString(Text, *Path)
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
    {
        Test.AddError(FString(TEXT("Cannot read raw-encoder fixture contract: ")) + Path);
        return nullptr;
    }
    return Root;
}

bool LoadLayout(FAutomationTestBase& Test, FImpl& Impl)
{
    const auto Run = ReadContract(Test, TEXT("prophecy_lower_body_runtime.json"));
    const auto Walk = ReadContract(Test, TEXT("prophecy_lower_body_walk_runtime.json"));
    const auto Upper = ReadContract(Test, TEXT("prophecy_upper_body_runtime.json"));
    if (!Run || !Walk || !Upper) return false;
    const TArray<TSharedPtr<FJsonValue>>* Names = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* Parents = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* RootRows = nullptr;
    if (!Run->TryGetArrayField(TEXT("body_names"), Names) || Names->Num() != FullBodyBoneCount
        || !Run->TryGetArrayField(TEXT("parents_body"), Parents) || Parents->Num() != FullBodyBoneCount
        || !Run->TryGetArrayField(TEXT("seed_root_rotation_rows"), RootRows) || RootRows->Num() != 3) return false;
    for (int32 Index = 0; Index < FullBodyBoneCount; ++Index)
    {
        Impl.BodyNames.Add(FName((*Names)[Index]->AsString()));
        Impl.Parents.Add(int32((*Parents)[Index]->AsNumber()));
    }
    for (int32 Row = 0; Row < 3; ++Row)
        if (!JsonVec3((*RootRows)[Row]->AsArray(), Impl.SeedRootRot.Rows[Row])) return false;
    for (const auto& Root : { Walk, Upper })
    {
        if (!Root->TryGetArrayField(TEXT("body_names"), Names) || Names->Num() != FullBodyBoneCount
            || !Root->TryGetArrayField(TEXT("parents_body"), Parents) || Parents->Num() != FullBodyBoneCount) return false;
        for (int32 Index = 0; Index < FullBodyBoneCount; ++Index)
            if (Impl.BodyNames[Index] != FName((*Names)[Index]->AsString())
                || Impl.Parents[Index] != int32((*Parents)[Index]->AsNumber())) return false;
    }
    auto ReadLimbs = [&](const TSharedPtr<FJsonObject>& Root, FImpl::FLimb* Limbs)
    {
        const TArray<TSharedPtr<FJsonValue>>* Specs = nullptr;
        const TArray<TSharedPtr<FJsonValue>>* Axes = nullptr;
        if (!Root->TryGetArrayField(TEXT("ik_limb_specs"), Specs) || Specs->Num() != 2
            || !Root->TryGetArrayField(TEXT("ik_toe_axes"), Axes) || Axes->Num() != 2) return false;
        for (int32 Index = 0; Index < 2; ++Index)
        {
            const auto Spec = (*Specs)[Index]->AsObject();
            if (!Spec) return false;
            Limbs[Index].Start = int32(Spec->GetNumberField(TEXT("start")));
            Limbs[Index].Mid = int32(Spec->GetNumberField(TEXT("mid")));
            Limbs[Index].End = int32(Spec->GetNumberField(TEXT("end")));
            Limbs[Index].Toe = int32(Spec->GetNumberField(TEXT("toe")));
            for (const int32 Bone : { Limbs[Index].Start, Limbs[Index].Mid, Limbs[Index].End, Limbs[Index].Toe })
                if (!Impl.BodyNames.IsValidIndex(Bone)) return false;
            if (!JsonVec3((*Axes)[Index]->AsArray(), Limbs[Index].ToeAxis)) return false;
        }
        return true;
    };
    if (!ReadLimbs(Run, Impl.Limbs) || !ReadLimbs(Walk, Impl.WalkLimbs)) return false;
    const TArray<TSharedPtr<FJsonValue>>* Core = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* Arms = nullptr;
    if (!Upper->TryGetArrayField(TEXT("core_bones"), Core) || Core->Num() != 10
        || !Upper->TryGetArrayField(TEXT("arm_specs"), Arms) || Arms->Num() != 2) return false;
    for (const auto& Value : *Core)
    {
        const FName Bone(Value->AsString());
        const int32 Index = Impl.BodyNames.IndexOfByKey(Bone);
        if (!Impl.Parents.IsValidIndex(Index) || !Impl.BodyNames.IsValidIndex(Impl.Parents[Index])) return false;
        Impl.UpperCoreBoneNames.Add(Bone);
    }
    for (int32 Index = 0; Index < 2; ++Index)
    {
        const auto Spec = (*Arms)[Index]->AsObject();
        if (!Spec) return false;
        auto& Arm = Impl.UpperArms[Index];
        Arm.Start = int32(Spec->GetNumberField(TEXT("start")));
        Arm.Mid = int32(Spec->GetNumberField(TEXT("mid")));
        Arm.End = int32(Spec->GetNumberField(TEXT("end")));
        for (const int32 Bone : { Arm.Start, Arm.Mid, Arm.End })
            if (!Impl.BodyNames.IsValidIndex(Bone)) return false;
    }
    return true;
}

bool SameFloatBits(FAutomationTestBase& Test, const TCHAR* Part, const float* Expected,
    const float* Actual, int32 Count, int32 Variant, bool bWalk)
{
    for (int32 Index = 0; Index < Count; ++Index)
    {
        if (!FMath::IsFinite(Expected[Index]) || !FMath::IsFinite(Actual[Index])
            || FMemory::Memcmp(Expected + Index, Actual + Index, sizeof(float)) != 0)
        {
            Test.AddError(FString::Printf(TEXT("%s float %d differs at variant %d / walk %d: oracle %.9g, cached %.9g"),
                Part, Index, Variant, bWalk, double(Expected[Index]), double(Actual[Index])));
            return false;
        }
    }
    return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyNNPhysicalRotationCacheOracleTest,
    "Prophecy.NN.PhysicalFeedback.RotationCacheRawEncoder",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyNNPhysicalRotationCacheOracleTest::RunTest(const FString& Parameters)
{
    using namespace PhysicalRotationCacheTests;
    const auto Impl = MakeUnique<FImpl>();
    if (!TestTrue(TEXT("Load matching real run/walk/upper encoder contracts"), LoadLayout(*this, *Impl))) return false;
    FImpl::FAgent Agent;
    FRandomStream Random(0x507259);
    TArray<FTransform> Pose;
    Pose.SetNum(FullBodyBoneCount);
    const FMat3f AuthoredSeedRoot = Impl->SeedRootRot;
    for (int32 Variant = 0; Variant < 128; ++Variant)
    {
        // Reuse the same source allocation with entirely new values; a cache must be sample-local.
        for (int32 Bone = 0; Bone < FullBodyBoneCount; ++Bone)
        {
            FVector Axis(Random.FRandRange(-1.0f, 1.0f), Random.FRandRange(-1.0f, 1.0f), Random.FRandRange(-1.0f, 1.0f));
            Axis = Axis.GetSafeNormal();
            if (Axis.IsNearlyZero()) Axis = FVector::ForwardVector;
            double Angle = double(Random.FRandRange(-UE_PI, UE_PI)) + (Bone + 1) * 1.0e-10;
            if (Variant == 0) Angle = 0.0;
            if (Variant == 1) { Axis = Bone % 3 == 0 ? FVector::ForwardVector : Bone % 3 == 1 ? FVector::RightVector : FVector::UpVector; Angle = UE_DOUBLE_PI * 0.5; }
            if (Variant == 2) Angle = UE_DOUBLE_PI;
            if (Variant == 3) Angle = 1.0e-9;
            FQuat Rotation(Axis, Angle);
            if (Variant % 2) Rotation = Rotation * -1.0;
            if (Variant == 4) Rotation = Rotation * 2.3; // Exact existing normalization route.
            if (Variant == 5) Rotation = FQuat(0.0, 0.0, 0.0, 0.0);
            if (Variant == 6) Rotation = Rotation * 1.0e-12; // Existing near-zero fallback.
            if (Variant == 7) Rotation = FQuat(-0.0, 0.0, -0.0, 1.0);
            FVector Position(Random.FRandRange(-500.0f, 500.0f), Random.FRandRange(-500.0f, 500.0f), Random.FRandRange(-500.0f, 500.0f));
            if (Variant % 17 == 0) Position *= 10000.0;
            if (Variant == 7) Position.X = -0.0;
            Pose[Bone].SetRotation(Rotation);
            Pose[Bone].SetTranslation(Position);
            Pose[Bone].SetScale3D(FVector(0.3 + Bone * 0.03, 1.1, 2.7));
        }
        // Exercise both authored and changed finite seed frames; multiplication order must stay exact.
        Impl->SeedRootRot = Variant % 3 == 0 ? AuthoredSeedRoot : Multiply(AuthoredSeedRoot, YawMatrix(0.37f));
        for (int32 Policy = 0; Policy < 2; ++Policy)
        {
            Agent.bUseWalkPolicy = Policy != 0;
            TArray<FTransform> OraclePose = Pose;
            TArray<FTransform> CachedPose = Pose;
            float OracleLower[StateDim], OracleUpper[UpperStateDim];
            float CachedLower[StateDim], CachedUpper[UpperStateDim];
            for (float& Value : OracleLower) Value = -12345.0f;
            for (float& Value : OracleUpper) Value = -12345.0f;
            for (float& Value : CachedLower) Value = 67890.0f;
            for (float& Value : CachedUpper) Value = 67890.0f;
            EncodeComponentPoseToNNStates(*Impl, Agent, OraclePose, OracleLower, OracleUpper);
            FSampledTrainingRotations Cache(CachedPose);
            EncodePhysicalLowerSample(*Impl, Agent, CachedPose, Cache, CachedLower);
            EncodePhysicalUpperSample(*Impl, CachedPose, Cache, CachedUpper);
            if (!SameFloatBits(*this, TEXT("lower"), OracleLower, CachedLower, StateDim, Variant, Agent.bUseWalkPolicy)
                || !SameFloatBits(*this, TEXT("upper"), OracleUpper, CachedUpper, UpperStateDim, Variant, Agent.bUseWalkPolicy)) return false;
            if (Variant == 0)
                AddInfo(FString::Printf(TEXT("%s raw sample uses %d cached rotations from %d supplied transforms"),
                    Policy ? TEXT("walk") : TEXT("run"), FPlatformMath::CountBits(Cache.CachedMaskForTests()), FullBodyBoneCount));
            // The cache accepts every supplied index, including the four rotations unused by current raw encoders.
            for (int32 Bone = FullBodyBoneCount - 1; Bone >= 0; --Bone)
            {
                const FMat3f Original = MirrorYBasis(QuatToMatrix(OraclePose[Bone].GetRotation()));
                const FMat3f& Actual = Cache.Get(Bone);
                for (int32 Row = 0; Row < 3; ++Row)
                {
                    const float ExpectedRow[] = { Original.Rows[Row].X, Original.Rows[Row].Y, Original.Rows[Row].Z };
                    const float ActualRow[] = { Actual.Rows[Row].X, Actual.Rows[Row].Y, Actual.Rows[Row].Z };
                    if (!SameFloatBits(*this, TEXT("cached matrix"), ExpectedRow, ActualRow, 3, Variant, Agent.bUseWalkPolicy)) return false;
                }
            }
        }
    }
    AddInfo(TEXT("256 full raw encodings matched all 41 lower and 90 upper floats bitwise; every sampled rotation was also checked."));
    return true;
}
