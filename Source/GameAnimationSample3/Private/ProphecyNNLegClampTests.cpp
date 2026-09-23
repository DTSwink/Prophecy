#include "ProphecyNNLegClamps.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNPresentation.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyNNLegClampsTest,
	"Prophecy.NN.PhysicalTargets.AttackLegClamps", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyNNLegClampsTest::RunTest(const FString&)
{
	for (double Side : {-1., 1.})
	{
		const FVector Reference(Side * 40, 0, 0), Knee(0, 0, -40), End(30, 20, -170);
		FTransform Calf(FQuat::FindBetweenNormals(Reference.GetSafeNormal(), (End-Knee).GetSafeNormal()), Knee);
		FTransform Foot(FRotator(15, 32, 8), End), Toe(FRotator(30, 32, 8), End+FVector(12, 4, -1));
		const FTransform OriginalCalf=Calf, OriginalFoot=Foot, OriginalToe=Toe;
		ProphecyNNLegClamps::Apply(FVector::ZeroVector, Calf, Foot, Toe, Reference, 40, false, 1, false, 1);
		TestTrue(TEXT("Disabled clamps preserve decoded pose"), Calf.Equals(OriginalCalf, 0) && Foot.Equals(OriginalFoot, 0) && Toe.Equals(OriginalToe, 0));
		ProphecyNNLegClamps::Apply(FVector::ZeroVector, Calf, Foot, Toe, Reference, 40, true, 1, true, 1);
		TestTrue(TEXT("Attack foot attached to authored calf end"), Foot.GetTranslation().Equals(Calf.TransformPosition(Reference), 1e-8));
		TestTrue(TEXT("Total reach bounded"), Foot.GetTranslation().Length() <= 80+1e-8);
		TestTrue(TEXT("Toe follows moved foot"), (Toe.GetTranslation()-Foot.GetTranslation()).Equals(OriginalToe.GetTranslation()-OriginalFoot.GetTranslation(), 1e-8));
		TestTrue(TEXT("Foot/toe rotations preserved"), Foot.GetRotation().Equals(OriginalFoot.GetRotation(), 1e-10) && Toe.GetRotation().Equals(OriginalToe.GetRotation(), 1e-10));
		TestTrue(TEXT("No mesh scaling"), Calf.GetScale3D()==FVector::OneVector && Foot.GetScale3D()==FVector::OneVector);
		ProphecyNNLegClamps::Apply(FVector::ZeroVector, Calf, Foot, Toe, Reference, 40, false, 1, true, .75f);
		TestTrue(TEXT("Runtime calf multiplier"), FMath::IsNearlyEqual((Foot.GetTranslation()-Knee).Length(), 30., 1e-8));
		Foot.SetTranslation(Knee);
		ProphecyNNLegClamps::Apply(FVector::ZeroVector, Calf, Foot, Toe, Reference, 40, false, 1, true, 1);
		TestTrue(TEXT("Coincident knee/foot has finite authored direction"), !Foot.ContainsNaN() && Foot.GetTranslation().Equals(Calf.TransformPosition(Reference), 1e-8));
	}
	// World-space position lerp follows a chord, while calf rotation follows an arc.
	// The attachment must remain exact even halfway between widely separated policy poses.
	constexpr int32 Id = 1900000041;
	const TArray<FName> Names = { TEXT("calf_r"), TEXT("foot_r"), TEXT("ball_r") };
	TArray<FTransform> Local = { FTransform::Identity, FTransform(FVector(40, 0, 0)), FTransform(FVector(10, 0, 0)) };
	TArray<FTransform> Previous = { FTransform::Identity, FTransform(FVector(40,0,0)), FTransform(FVector(50,0,0)) };
	TArray<FTransform> Current = { FTransform(FRotator(0,90,0)), FTransform(FVector(0,40,0)), FTransform(FVector(0,50,0)) };
	FProphecyNNPoseStore::SetAgentLocalPose(Id, Names, Local, Previous, Current, FTransform::Identity, FTransform::Identity, 0, false, true);
	FProphecyNNPoseSnapshot Snapshot;
	FProphecyNNPoseStore::GetAgentLocalPose(Id, Snapshot);
	for (float Alpha : {0.f, .1f, .5f, .9f, 1.f})
	{
		TArray<FTransform> Blended;
		for (int32 Index=0; Index<3; ++Index) { FTransform T; T.Blend(Previous[Index],Current[Index],Alpha); Blended.Add(T); }
		const FVector ToeOffset = Blended[2].GetTranslation()-Blended[1].GetTranslation();
		FProphecyNNPoseStore::ApplyRigidCalves(Id, Snapshot, Names, Blended);
		TestTrue(TEXT("Interpolated calf attachment exact"), Blended[1].GetTranslation().Equals(Blended[0].TransformPosition(FVector(40,0,0)),1e-8));
		TestTrue(TEXT("Interpolated toe moves with foot"), (Blended[2].GetTranslation()-Blended[1].GetTranslation()).Equals(ToeOffset,1e-8));
	}
	FProphecyNNPoseStore::SetAgentLocalPose(Id, Names, Local, Previous, Current, FTransform::Identity, FTransform::Identity, 1, false, false);
	TArray<FTransform> Disabled=Current;
	Disabled[1].SetTranslation(FVector(0,100,0));
	FProphecyNNPoseStore::ApplyRigidCalves(Id, Snapshot, Names, Disabled);
	TestEqual(TEXT("Runtime disabling restores unconstrained presentation"), Disabled[1].GetTranslation(), FVector(0,100,0));
	FProphecyNNPoseStore::ClearAgentPose(Id);
	// Centimetre leeway is a deadband, not a blend back to the exact rest length.
	for (double Radius : {38., 39., 39.5, 40., 40.5, 41., 42.})
	{
		FTransform Calf(FVector(40,0,0));
		FTransform Foot(FVector(40+Radius,0,0)), Toe(FVector(50+Radius,0,0));
		const FTransform BeforeFoot = Foot;
		ProphecyNNLegClamps::Apply(FVector::ZeroVector,Calf,Foot,Toe,FVector(40,0,0),40,false,1,true,1,0,1);
		TestTrue(TEXT("One cm bounds only excessive calf extension/shortening"),
			FMath::IsNearlyEqual((Foot.GetTranslation()-Calf.GetTranslation()).Length(),FMath::Clamp(Radius,39.,41.),1e-8));
		if (Radius>=39 && Radius<=41) TestTrue(TEXT("Inside calf band unchanged"),Foot.Equals(BeforeFoot,0));
		TestTrue(TEXT("Toe follows tolerance correction"),(Toe.GetTranslation()-Foot.GetTranslation()).Equals(FVector(10,0,0),1e-8));
	}
	{
		FTransform Calf(FVector(40,0,0)), Foot(FVector(90,0,0)), Toe(FVector(100,0,0));
		ProphecyNNLegClamps::Apply(FVector::ZeroVector,Calf,Foot,Toe,FVector(40,0,0),40,true,1,false,1,2,0);
		TestEqual(TEXT("Foot reach includes two cm leeway"),Foot.GetTranslation(),FVector(82,0,0));
	}
	// Current publication can already be at the edge of the band. Never use that
	// edge as a new rest length and accidentally permit another centimetre.
	Local[1].SetTranslation(FVector(41,0,0));
	FProphecyNNPoseStore::SetAgentLocalPose(Id,Names,Local,Previous,Current,FTransform::Identity,FTransform::Identity,2,false,true,1,FVector2D(40,40));
	FProphecyNNPoseStore::GetAgentLocalPose(Id,Snapshot);
	for (double Radius : {38.,39.5,40.5,42.})
	{
		TArray<FTransform> Pose = {FTransform::Identity,FTransform(FVector(Radius,0,0)),FTransform(FVector(Radius+10,0,0))};
		FProphecyNNPoseStore::ApplyRigidCalves(Id,Snapshot,Names,Pose);
		TestTrue(TEXT("Interpolation honors original band"),FMath::IsNearlyEqual(Pose[1].GetTranslation().X,FMath::Clamp(Radius,39.,41.),1e-8));
	}
	FProphecyNNPoseStore::ClearAgentPose(Id);
	return true;
}
#endif
