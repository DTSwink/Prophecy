#include "ProphecyBodyflipRigProfile.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltRig.h"
#include "ProphecyFootColliderTrim.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/BodyInstance.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/ScopeExit.h"

namespace ProphecyBodyflip::RigProfilePrivate
{
using FObject=TSharedPtr<FJsonObject>;
static TArray<TSharedPtr<FJsonValue>> V(FVector A){return {MakeShared<FJsonValueNumber>(A.X),MakeShared<FJsonValueNumber>(A.Y),MakeShared<FJsonValueNumber>(A.Z)};}
static TArray<TSharedPtr<FJsonValue>> Q(FQuat A){return {MakeShared<FJsonValueNumber>(A.X),MakeShared<FJsonValueNumber>(A.Y),MakeShared<FJsonValueNumber>(A.Z),MakeShared<FJsonValueNumber>(A.W)};}
static FObject T(FTransform A){auto O=MakeShared<FJsonObject>();O->SetArrayField(TEXT("position_cm"),V(A.GetTranslation()));O->SetArrayField(TEXT("rotation_xyzw"),Q(A.GetRotation()));return O;}
static TArray<TSharedPtr<FJsonValue>> JointRows(TConstArrayView<FProphecyJoltRigJoint> Joints)
{
 TArray<TSharedPtr<FJsonValue>> Rows;
 for(const auto& J:Joints){auto O=MakeShared<FJsonObject>();const auto& P=J.CurrentProfile;
  O->SetNumberField(TEXT("child"),J.Body1Index);O->SetNumberField(TEXT("parent"),J.Body2Index);
  O->SetObjectField(TEXT("child_frame"),T(J.Frame1));O->SetObjectField(TEXT("parent_frame"),T(J.Frame2));
  O->SetArrayField(TEXT("angular_modes_twist_swing2_swing1"),V(FVector(P.TwistLimit.TwistMotion,P.ConeLimit.Swing2Motion,P.ConeLimit.Swing1Motion)));
  O->SetArrayField(TEXT("angular_limits_deg_twist_swing2_swing1"),V(FVector(P.TwistLimit.TwistLimitDegrees,P.ConeLimit.Swing2LimitDegrees,P.ConeLimit.Swing1LimitDegrees)));
  O->SetArrayField(TEXT("linear_modes"),V(FVector(P.LinearLimit.XMotion,P.LinearLimit.YMotion,P.LinearLimit.ZMotion)));Rows.Add(MakeShared<FJsonValueObject>(O));
 }return Rows;
}
}
bool ProphecyBodyflip::SerializeRigProfile(const FProphecyJoltRigSnapshot& S,const FProphecyJoltPreparedRig& Prepared,FString& Json,FString& Error)
{
 using namespace RigProfilePrivate;auto Root=MakeShared<FJsonObject>();Root->SetStringField(TEXT("schema"),TEXT("bodyflip-native-rig-v1"));Root->SetStringField(TEXT("physics_asset"),S.PhysicsAssetPath);
 TArray<TSharedPtr<FJsonValue>> Bodies;
 for(int I=0;I<S.Bodies.Num();I++){const auto& B=S.Bodies[I];double Mass;FQuat InertiaRotation;FVector Inertia,COM;FBox Bounds;
  if(!Prepared.GetBodyMassSummary(I,Mass,InertiaRotation,Inertia)||!Prepared.GetBodyGeometrySummary(I,COM,Bounds,Error))return false;
  auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("name"),B.BodyName.ToString());O->SetNumberField(TEXT("mass_kg"),Mass);O->SetObjectField(TEXT("mass_frame"),T(FTransform(FQuat::Identity,COM)));O->SetArrayField(TEXT("jolt_inertia_rotation_xyzw"),Q(InertiaRotation));O->SetArrayField(TEXT("jolt_inertia_kg_cm2"),V(Inertia));
  TArray<TSharedPtr<FJsonValue>> Shapes;
  for(const auto& Shape:B.Shapes){if(!Shape.bNativeSimulationEnabled)continue;if(Shape.Kind==EProphecyJoltRigShape::Convex){Error=TEXT("Bodyflip native profile does not support convex body colliders");return false;}
   auto G=MakeShared<FJsonObject>();G->SetStringField(TEXT("kind"),Shape.Kind==EProphecyJoltRigShape::Box?TEXT("box"):Shape.Kind==EProphecyJoltRigShape::Capsule?TEXT("capsule"):TEXT("sphere"));G->SetObjectField(TEXT("local"),T(Shape.LocalToBodyOrigin));G->SetArrayField(TEXT("half_extent_cm"),V(Shape.BoxHalfExtentCm));G->SetNumberField(TEXT("radius_cm"),Shape.RadiusCm);G->SetNumberField(TEXT("cylinder_length_cm"),Shape.CapsuleCylinderLengthCm);Shapes.Add(MakeShared<FJsonValueObject>(G));
  }O->SetArrayField(TEXT("shapes"),Shapes);
  if(B.BodyName==TEXT("foot_l")||B.BodyName==TEXT("foot_r")){auto* Mesh=S.SourceComponent.Get();const auto* Asset=Mesh?Mesh->GetSkeletalMeshAsset():nullptr;if(!Asset){Error=TEXT("Foot profile lacks source skeleton");return false;}const auto& Ref=Asset->GetRefSkeleton();const int Foot=Ref.FindBoneIndex(B.BodyName),Toe=Ref.FindBoneIndex(B.BodyName==TEXT("foot_l")?TEXT("ball_l"):TEXT("ball_r"));FTransform Relative=FTransform::Identity;int K=Toe;for(;K!=INDEX_NONE&&K!=Foot;K=Ref.GetParentIndex(K))Relative=Relative*Ref.GetRefBonePose()[K];if(K!=Foot){Error=TEXT("Native foot lacks toe direction");return false;}O->SetArrayField(TEXT("toe_direction"),V(Relative.GetLocation()));}
  Bodies.Add(MakeShared<FJsonValueObject>(O));
 }
 Root->SetArrayField(TEXT("bodies"),Bodies);Root->SetArrayField(TEXT("joints"),JointRows(S.Joints));Json.Reset();return FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Json));
}
bool ProphecyBodyflip::RefreshRigProfile(const FString& Original,TConstArrayView<FProphecyJoltRigJoint> Joints,float FootTrimCm,FString& Json,FString& Error)
{
 TSharedPtr<FJsonObject> Root;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Original),Root)||!Root){Error=TEXT("Native Bodyflip profile capture is unavailable");return false;}Root->SetArrayField(TEXT("joints"),RigProfilePrivate::JointRows(Joints));Root->SetNumberField(TEXT("foot_front_trim_cm"),FootTrimCm);Json.Reset();return FJsonSerializer::Serialize(Root.ToSharedRef(),TJsonWriterFactory<>::Create(&Json));
}
bool ProphecyBodyflip::CaptureRigProfile(AProphecyAgent* Agent,FString& Json,FString& Error)
{
 if(!IsInGameThread()||!IsValid(Agent)){Error=TEXT("Bodyflip rig capture requires a live agent on the game thread");return false;}
 if(auto* Jolt=Agent->GetJoltCharacterComponent();Jolt&&Jolt->IsJoltPhysical())return Jolt->GetBodyflipRigProfile(Json,Error);
 auto* Source=Agent->GetPoseReferenceMesh();if(!Source||!Source->GetSkeletalMeshAsset()||!Source->GetPhysicsAsset()||!Agent->GetWorld()){Error=TEXT("Bodyflip rig capture needs the agent mesh and PHAT");return false;}
 // The real kinematic mesh has NoCollision. A transient, non-simulating clone
 // lets the same native capture/preparation code resolve mass, scale and shapes.
 auto* Clone=NewObject<USkeletalMeshComponent>(GetTransientPackage(),NAME_None,RF_Transient);Clone->BodyInstance.bSimulatePhysics=false;Clone->SetSkeletalMesh(Source->GetSkeletalMeshAsset());Clone->SetPhysicsAsset(Source->GetPhysicsAsset());Clone->SetWorldTransform(Source->GetComponentTransform());Clone->SetCollisionProfileName(TEXT("PhysicsActor"));Clone->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);Clone->SetCollisionResponseToAllChannels(ECR_Ignore);Clone->SetComponentTickEnabled(false);Clone->SetVisibility(false);
 // Match the component override and material fallback even when NoCollision
 // has removed all live source bodies; preserve Unreal's material priority.
 Clone->SetPhysMaterialOverride(Source->BodyInstance.GetPhysMaterialOverride());Clone->SetMaterial(0,Source->GetMaterial(0));Clone->RegisterComponentWithWorld(Agent->GetWorld());Clone->SetAllBodiesSimulatePhysics(false);
 ON_SCOPE_EXIT {Clone->DestroyComponent();};
 for(int I=0;I<Clone->Bodies.Num()&&I<Source->Bodies.Num();I++){auto* B=Clone->Bodies[I];const auto* Original=Source->Bodies[I];if(!B||!Original)continue;B->COMNudge=Original->COMNudge;B->InertiaTensorScale=Original->InertiaTensorScale;B->MassScale=Original->MassScale;B->SetInertiaConditioningEnabled(Original->IsInertiaConditioningEnabled());B->SetMassOverride(Original->GetMassOverride(),Original->bOverrideMass);B->SetPhysMaterialOverride(Original->GetSimplePhysicalMaterial());B->UpdateMassProperties();}
 for(int I=0;I<Clone->Constraints.Num()&&I<Source->Constraints.Num();I++)if(Clone->Constraints[I]&&Source->Constraints[I]){Clone->Constraints[I]->CopyProfilePropertiesFrom(Source->Constraints[I]->ProfileInstance);for(auto Frame:{EConstraintFrame::Frame1,EConstraintFrame::Frame2})Clone->Constraints[I]->SetRefFrame(Frame,Source->Constraints[I]->GetRefFrame(Frame));}
 FProphecyJoltRigSnapshot Snapshot;FProphecyJoltPreparedRig Prepared;if(!ProphecyJolt::Rig::CaptureLiveRig(*Clone,Snapshot,Error)||!Prepared.Build(Snapshot,Error))return false;
 FString Original;if(!SerializeRigProfile(Snapshot,Prepared,Original,Error))return false;return RefreshRigProfile(Original,Snapshot.Joints,ProphecyFootColliderTrim::Get(Agent),Json,Error);
}
