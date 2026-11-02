#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyFootIKTerrainReturn.h"
#include "ProphecyFootIKLiveGeometry.h"
#include "Misc/AutomationTest.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKTerrainReturnTest,"Prophecy.FootIK.Live.TerrainReturnContinuity",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKTerrainReturnTest::RunTest(const FString&)
{
    using namespace ProphecyFootIKGame;
    const auto Sample=[](double T,double ExtraHeight=0)
    {
        ProphecyFootIKLive::FSourceSample S;S.RootWorld=FVector(200*T,80*T,168);S.HeadingWorld=FRotator(0,37+30*T,0).Vector();
        const auto Root=FTerrainReturn::Carrier(S);
        for(int32 I=0;I<25;++I)
        {
            const int32 Parent=FTerrainReturn::Parent[I];const FQuat Q(FVector::UpVector,(I==7?T*.2:0));
            const FTransform Local(Q,Parent<0?FVector(0,0,90+ExtraHeight):FVector(5,0,10));
            S.BodiesWorld.Add(Local*(Parent<0?Root:S.BodiesWorld[Parent]));
        }
        return S;
    };
    FTerrainReturn Return;Return.Begin(100,10,Sample(-1./60.),Sample(0));double MaxIdentity=0;
    for(int32 I=1;I<=6;++I)
    {
        auto Actual=Sample(I/60.),Expected=Actual;const bool Active=Return.Apply(100+I*2,10+I/30.,Actual,Sample(1./30.));
        TestEqual(TEXT("Carry has a fixed six-game-frame lifetime"),Active,I<6);
        TestTrue(TEXT("Controller root is unchanged"),Actual.RootWorld.Equals(Expected.RootWorld,0));
        for(int32 B=0;B<25;++B)
        {
            MaxIdentity=FMath::Max(MaxIdentity,FVector::Distance(Actual.BodiesWorld[B].GetLocation(),Expected.BodiesWorld[B].GetLocation()));
            TestTrue(TEXT("A matching incoming/outgoing gait remains unchanged"),Actual.BodiesWorld[B].GetRotation().AngularDistance(Expected.BodiesWorld[B].GetRotation())<1.e-6);
        }
    }
    TestTrue(TEXT("Local velocity carry does not introduce drift with translating/turning roots"),MaxIdentity<1.e-6);
    Return.Begin(200,20,Sample(-1./60.,4.9),Sample(0,5));
    auto Pending=Sample(1./60.);Return.Apply(202,20,Pending,Sample(1./30.));
    const auto Local=FTerrainReturn::Local(Pending);
    TestTrue(TEXT("The intervening pre-publication tick retains incoming pelvis velocity"),FMath::Abs(Local[0].GetLocation().Z-95.1)<1.e-6);
    auto End=Sample(.1),ExpectedEnd=End;TestFalse(TEXT("The carry retires at100ms"),Return.Apply(212,21,End,Sample(.1)));
    for(int32 B=0;B<25;++B)TestTrue(TEXT("No residual old-pose target after carry"),End.BodiesWorld[B].Equals(ExpectedEnd.BodiesWorld[B],0));
    Return.Begin(300,30,Sample(-1./60.,1),Sample(0,1));
    auto First=Sample(0,1);Return.Apply(302,31,First,Sample(1./30.,1));
    TestTrue(TEXT("A stationary corrected pelvis does not jump on a new Alpha0 publication"),FMath::Abs(FTerrainReturn::Local(First)[0].GetLocation().Z-91)<1.e-6);
    Return.Begin(400,40,Sample(-1./60.,1-1./60.),Sample(0,1));
    auto Moving=Sample(0,1);Return.Apply(402,41,Moving,Sample(1./30.,1+3./30.));
    TestTrue(TEXT("A faster outgoing NN cannot reverse a forward incoming motion at Alpha0"),FMath::Abs(FTerrainReturn::Local(Moving)[0].GetLocation().Z-(91+1./60.))<1.e-6);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKLiveGeometryTest,"Prophecy.FootIK.Live.GeometryCoverage",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKLiveGeometryTest::RunTest(const FString&)
{
    using namespace ProphecyFootIKLiveGeometry;
    const auto Snapshot=[](double Begin,double End,std::initializer_list<int32> Ids)
    {
        FSnapshot S;S.Valid=true;S.Query=S.WorldQuery=FBox(FVector(-2,-2,Begin),FVector(2,2,End));
        for(int32 Id:Ids){FTile T;T.Values={double(Id),0,0};T.Bounds=FBox(FVector(-1,0,Id),FVector(1,0,Id+.25));S.Tiles.Add(FString::FromInt(Id),MoveTemp(T));}return S;
    };
    const auto Original=Snapshot(-2,4,{-1,0,1,2,3});
    auto Advanced=Snapshot(0,6,{0,1,2,3,4,5});
    // Tile4 touches the old query boundary, so it is conservatively relevant.
    TestFalse(TEXT("New face inside/on old coverage invalidates prediction"),Compatible(Original,Advanced));
    Advanced.Tiles.Remove(TEXT("4"));
    TestTrue(TEXT("Only faces outside the overlapping captures may enter/leave"),Compatible(Original,Advanced));
    Advanced.Tiles.Remove(TEXT("2"));
    TestFalse(TEXT("Deleting a face in shared coverage invalidates prediction"),Compatible(Original,Advanced));
    Advanced=Snapshot(0,6,{0,1,2,3,5});Advanced.Tiles[TEXT("2")].Values[1]=.16;
    TestFalse(TEXT("Moving or resizing a shared face invalidates prediction"),Compatible(Original,Advanced));
    Advanced=Snapshot(0,6,{0,1,2,3,5});Advanced.Tiles[TEXT("2")].Values.Add(1);
    TestFalse(TEXT("Changing a face representation invalidates prediction"),Compatible(Original,Advanced));
    Advanced=Snapshot(-2,4,{-1,0,1,2,3});
    TestTrue(TEXT("Identical faces remain valid"),Compatible(Original,Advanced));
    Advanced.Valid=false;TestFalse(TEXT("Unknown capture coverage cannot loosen geometry identity"),Compatible(Original,Advanced));
    TSharedPtr<FJsonObject> O;
    const FString Json=TEXT("{\"captureBounds\":[-2,-2,-2,2,2,4],\"captureWorldBounds\":[100,200,300,500,600,900],\"tiles\":[{\"id\":\"a\",\"point\":[0,0,1],\"u\":[0.6,0,0.8],\"v\":[-0.8,0,0.6],\"bounds\":[-1,1,-2,2],\"shaped\":true}]}");
    FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),O);const auto Parsed=Read(O);
    TestTrue(TEXT("Finite yawed treads and world capture bounds parse"),Parsed.Valid&&Parsed.Tiles.Num()==1);
    if(Parsed.Valid)
    {
        TestTrue(TEXT("Rotated face uses all four footprint corners"),Parsed.Tiles[TEXT("a")].Bounds.Min.Equals(FVector(-2.2,0,-1),1.e-12));
        TestTrue(TEXT("Actual pose coverage uses exact world query, not its enlarged solver AABB"),Parsed.WorldQuery.IsInsideOrOn(FVector(200,300,400))&&!Parsed.WorldQuery.IsInsideOrOn(FVector(0,0,1)));
    }
    O->RemoveField(TEXT("captureWorldBounds"));TestFalse(TEXT("Missing native query proof retains strict identity fallback"),Read(O).Valid);
    return true;
}
#endif
