#pragma once
#include "ProphecyPhysicalContextTypes.h"
class AProphecyAgent;

namespace ProphecyPhysicalContext
{
enum class EKind : uint8 { Magnetization, Feedback, Damping };
bool IsManaged(const AProphecyAgent* Agent,FName Bone,EKind Kind);
bool IsApplying();
bool Set(AProphecyAgent& Agent,FName Bone,EKind Kind,bool Enabled,FVector2f Value,float Duration,
    EProphecyLocomotionSelection Locomotion=EProphecyLocomotionSelection::Both,
    EProphecyEquipmentSelection Equipment=EProphecyEquipmentSelection::Both);
void Update(AProphecyAgent* Agent);
void AttackChanged(AProphecyAgent* Agent);
void AdoptBlend(AProphecyAgent& Agent,FName Bone,EKind Kind,FVector2f Start,FVector2f Target,double Elapsed,double Duration);
void Cancel(AProphecyAgent* Agent,FName Bone,EKind Kind);
void Discard(AProphecyAgent* Agent,EKind Kind);
bool RestoreResetSnapshot(AProphecyAgent* Agent,FName SnapshotName);
void DeleteSnapshot(const AProphecyAgent* Agent,FName SnapshotName);
void Remove(const AProphecyAgent* Agent);
bool Valid(EProphecyLocomotionSelection Locomotion,EProphecyEquipmentSelection Equipment);
}
