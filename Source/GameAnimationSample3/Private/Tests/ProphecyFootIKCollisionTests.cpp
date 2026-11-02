#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyFootIKCollision.h"
#include "Algo/Reverse.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKConvexCollisionTest,"Prophecy.FootIK.Live.ConvexCollision",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKConvexCollisionTest::RunTest(const FString&)
{
    for(int32 Case=0;Case<20;++Case)
    {
        const FTransform Actual(FRotator(Case*13.7,Case*29.1,Case*7.3),FVector(Case*113.,-Case*71.,25.));
        const FVector E(10+Case*3,80+Case*7,4+Case);TArray<FVector> Vertices;
        for(int32 I=0;I<8;++I)Vertices.Add(Actual.TransformPosition(FVector((I&1)?E.X:-E.X,(I&2)?E.Y:-E.Y,(I&4)?E.Z:-E.Z)));
        if(Case&1){Algo::Reverse(Vertices);const FVector Duplicate=Vertices[0];Vertices.Add(Duplicate);}
        FTransform Box;FVector Extent;
        if(!TestTrue(TEXT("Exact rotated rectangular convex is recovered"),ProphecyFootIKCollision::ConvexBox(Vertices,Box,Extent)))continue;
        for(const FVector& V:Vertices)
        {
            const FVector Local=Box.InverseTransformPosition(V).GetAbs();TestTrue(TEXT("Recovered box contains every actual hull corner"),Local.Equals(Extent,1.e-8));
        }
        Vertices[3]+=FVector(.1,.2,.3);
        TestFalse(TEXT("General hull cannot become an AABB floor"),ProphecyFootIKCollision::ConvexBox(Vertices,Box,Extent));
    }
    TArray<FVector> Wedge={FVector(-10,-10,0),FVector(10,-10,0),FVector(-10,10,0),FVector(10,10,0),FVector(-10,10,20),FVector(10,10,20)};
    FTransform Box;FVector Extent;TestFalse(TEXT("Triangular ramp is not misrepresented as a box"),ProphecyFootIKCollision::ConvexBox(Wedge,Box,Extent));
    return !HasAnyErrors();
}
#endif
