#include "ProphecyCrowdNameLookup.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCrowdNameLookupTest,
    "Prophecy.Crowd.NameLookup.ExactLayoutsAndMissingNames",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyCrowdNameLookupTest::RunTest(const FString&)
{
    TArray<FName> Source, Requested;
    for (int32 Index = 0; Index < 88; ++Index) Source.Add(FName(*FString::Printf(TEXT("bone_%02d"), Index)));
    for (int32 Index = 0; Index < 25; ++Index) Requested.Add(Source[(Index * 3) % Source.Num()]);
    ProphecyCrowd::FNameIndexLookup Lookup;
    auto Check = [&]()
    {
        Lookup.Update(Source, Requested);
        const TArray<int32>& Actual = Lookup.GetIndices();
        if (!TestEqual(TEXT("Every requested name has an index result"), Actual.Num(), Requested.Num())) return false;
        for (int32 Index = 0; Index < Requested.Num(); ++Index)
            if (!TestEqual(TEXT("Exact legacy first-name lookup"), Actual[Index], Source.IndexOfByKey(Requested[Index]))) return false;
        return true;
    };
    if (!Check()) return false;
    const int32* Allocation = Lookup.GetIndices().GetData();
    for (int32 Frame = 0; Frame < 100; ++Frame)
    {
        TestFalse(TEXT("Stable frame reuses indices"), Lookup.Update(Source, Requested));
        TestTrue(TEXT("Stable frame reuses allocation"), Allocation == Lookup.GetIndices().GetData());
    }
    Source.Swap(0, 19);
    if (!Check()) return false;
    const FName Duplicate = Source[7];
    Source.Insert(Duplicate, 0);
    Requested.Add(Duplicate);
    Requested.Add(TEXT("missing_name"));
    if (!Check()) return false;
    Requested.Swap(0, 12);
    if (!Check()) return false;
    Source[0] = TEXT("renamed_name");
    if (!Check()) return false;
    Source.Reset();
    if (!Check()) return false;
    Requested.Reset();
    return Check();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCrowdDebugNameTest,
    "Prophecy.Crowd.NameLookup.DebugMeshNumericSuffix",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyCrowdDebugNameTest::RunTest(const FString&)
{
    for (const int32 Index : {0, 1, 9, 10, 99, 100, 9999, 1000000})
    {
        const FString LegacyString = FString::Printf(TEXT("KinematicDebugMesh_%d"), Index);
        const FName Actual = ProphecyCrowd::KinematicDebugMeshName(Index);
        TestEqual(TEXT("Same FName identity"), Actual, FName(*LegacyString));
        TestEqual(TEXT("Same displayed numeric suffix"), Actual.ToString(), LegacyString);
    }
    return true;
}
#endif
