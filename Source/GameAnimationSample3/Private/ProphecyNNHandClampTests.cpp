#include "ProphecyNNPoseTypes.h"
#include "ProphecyAgent.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyNNHandClampTest,
	"Prophecy.NN.PhysicalTargets.AttackHandClamp", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyNNHandClampTest::RunTest(const FString&)
{
	const AProphecyAgent* Defaults = GetDefault<AProphecyAgent>();
	TestTrue(TEXT("Default retains exact attack attachment"), Defaults->bAttackHandClamp && Defaults->AttackHandClampLeewayCm == 0);
	constexpr int32 Id = 1900000042;
	const TArray<FName> Names = {TEXT("lowerarm_l"), TEXT("hand_l"), TEXT("lowerarm_r"), TEXT("hand_r")};
	TArray<FTransform> Local = {FTransform::Identity, FTransform(FVector(30,0,0)), FTransform::Identity, FTransform(FVector(-30,0,0))};
	FProphecyNNAttackHandClamp Settings;
	Settings.ReferenceOffsets[0] = FVector(30,0,0);
	Settings.ReferenceOffsets[1] = FVector(-30,0,0);
	for (bool Enabled : {false, true})
	for (float Leeway : {0.f, 1.f})
	for (double Deviation : {0., .5, 1., 5.})
	{
		Settings.bEnabled = Enabled;
		Settings.LeewayCm = Leeway;
		TArray<FTransform> Pose = {FTransform(FRotator(10,60,30),FVector(10,20,30)), FTransform::Identity,
			FTransform(FRotator(-25,15,40),FVector(-50,20,30)), FTransform::Identity};
		for (int32 Side=0; Side<2; ++Side)
			Pose[2*Side+1] = FTransform(FRotator(20,-30,10), Pose[2*Side].TransformPosition(Settings.ReferenceOffsets[Side]) + FVector(0,Deviation,0));
		const auto Original = Pose;
		FProphecyNNPoseStore::SetAgentLocalPose(Id,Names,Local,Pose,Pose,FTransform::Identity,FTransform::Identity,
			0,true,false,0,FVector2D::ZeroVector,Settings);
		FProphecyNNPoseSnapshot Snapshot;
		FProphecyNNPoseStore::GetAgentLocalPose(Id,Snapshot);
		FProphecyNNPoseStore::ApplyRigidForearms(Id,Snapshot,Names,Pose);
		TestTrue(TEXT("Attack classification independent of hand clamp"), FProphecyNNPoseStore::UsesAttackPresentation(Id));
		for (int32 Side=0; Side<2; ++Side)
		{
			const FVector Attachment = Pose[Side*2].TransformPosition(Settings.ReferenceOffsets[Side]);
			const double Expected = Enabled ? FMath::Min(Deviation, double(Leeway)) : Deviation;
			TestTrue(TEXT("Both hands obey positional deadband"), FMath::IsNearlyEqual(FVector::Distance(Pose[Side*2+1].GetTranslation(),Attachment),Expected,1e-7));
			TestTrue(TEXT("Forearm and hand rotation unchanged"), Pose[Side*2].Equals(Original[Side*2],0)
				&& Pose[Side*2+1].GetRotation().Equals(Original[Side*2+1].GetRotation(),0));
			if (!Enabled || Deviation<=Leeway)
				TestTrue(TEXT("Inside band and disabled poses untouched"), Pose[Side*2+1].Equals(Original[Side*2+1],0));
		}
	}
	FProphecyNNPoseStore::ClearAgentPose(Id);
	return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyNNForearmClampTest,
	"Prophecy.NN.PhysicalTargets.LocomotionForearmClamp", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyNNForearmClampTest::RunTest(const FString&)
{
	TestFalse(TEXT("Opt-in default"), GetDefault<AProphecyAgent>()->bLocomotionForearmClamp);
	constexpr int32 Id = 1900000043;
	const TArray<FName> Names = {TEXT("lowerarm_l"), TEXT("hand_l"), TEXT("lowerarm_r"), TEXT("hand_r")};
	const TArray<FTransform> Local = {FTransform::Identity,FTransform(FVector(30,0,0)),FTransform::Identity,FTransform(FVector(-30,0,0))};
	FProphecyNNForearmClamp Settings;
	Settings.bEnabled = true; Settings.LengthsCm = FVector2D(30,30);
	for (float Leeway : {0.f,1.f})
	for (double Radius : {0.,20.,29.,29.5,30.,30.5,31.,40.})
	{
		Settings.LeewayCm = Leeway;
		TArray<FTransform> Pose = {FTransform(FRotator(0,45,0)),FTransform(FRotator(20,30,40),FVector(Radius,0,0)),
			FTransform(FRotator(0,-60,0)),FTransform(FRotator(-20,10,50),FVector(-Radius,0,0))};
		const auto Original = Pose;
		FProphecyNNPoseStore::SetAgentLocalPose(Id,Names,Local,Pose,Pose,FTransform::Identity,FTransform::Identity,0,
			false,false,0,FVector2D::ZeroVector,FProphecyNNAttackHandClamp(),Settings);
		FProphecyNNPoseSnapshot Snapshot;
		FProphecyNNPoseStore::GetAgentLocalPose(Id,Snapshot);
		FProphecyNNPoseStore::ApplyRigidForearms(Id,Snapshot,Names,Pose);
		for (int32 Side=0;Side<2;++Side)
		{
			const int32 H=Side*2+1;
			TestTrue(TEXT("Both sides obey minimum and maximum length"), FMath::IsNearlyEqual(Pose[H].GetTranslation().Length(),FMath::Clamp(Radius,30.-Leeway,30.+Leeway),1e-8));
			TestTrue(TEXT("Rotations preserved"),Pose[H].GetRotation().Equals(Original[H].GetRotation(),0));
			// Rotated nominal vectors can change boundary comparisons by double roundoff.
			if (Radius>=30-Leeway && Radius<=30+Leeway) TestTrue(TEXT("Inside band untouched"),Pose[H].Equals(Original[H],1e-8));
		}
		Snapshot.ForearmClamp.bEnabled=false;
		Pose=Original;
		FProphecyNNPoseStore::ApplyRigidForearms(Id,Snapshot,Names,Pose);
		TestTrue(TEXT("Disabled locomotion pass unchanged"),Pose[1].Equals(Original[1],0) && Pose[3].Equals(Original[3],0));
	}
	FProphecyNNPoseStore::ClearAgentPose(Id);
	return true;
}
#endif
