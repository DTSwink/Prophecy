#pragma once
#include "ProphecyPhysicalContextTypes.h"
class AProphecyAgent;

namespace ProphecyPhysicalContext
{
enum class EKind : uint8 { Magnetization, Feedback, Damping, Mode };
bool IsManaged(const AProphecyAgent* Agent,FName Bone,EKind Kind);
bool IsApplying();
float MagnetizationMode(const AProphecyAgent* Agent);
float MagnetizationMode(const AProphecyAgent* Agent,FName Bone);
struct FModeView
{
    float Uniform=1.f;
    const TMap<FName,float>* Overrides=nullptr;
    uint64 Revision=0;
};
FModeView MagnetizationModes(const AProphecyAgent* Agent);
bool Set(AProphecyAgent& Agent,FName Bone,EKind Kind,bool Enabled,FVector2f Value,float Duration,
    EProphecyLocomotionSelection Locomotion=EProphecyLocomotionSelection::Both,
    EProphecyEquipmentSelection Equipment=EProphecyEquipmentSelection::Both);
void Update(AProphecyAgent* Agent);
void AttackChanged(AProphecyAgent* Agent);
// Event-only: restore every saved physical-profile value from slot "1".
bool EnterSpecial(AProphecyAgent* Agent);
void ExitSpecial(const AProphecyAgent* Agent);
void AdoptBlend(AProphecyAgent& Agent,FName Bone,EKind Kind,FVector2f Start,FVector2f Target,double Elapsed,double Duration);
void Cancel(AProphecyAgent* Agent,FName Bone,EKind Kind);
void Discard(AProphecyAgent* Agent,EKind Kind);
bool RestoreResetSnapshot(AProphecyAgent* Agent,FName SnapshotName);
void DeleteSnapshot(const AProphecyAgent* Agent,FName SnapshotName);
void Remove(const AProphecyAgent* Agent);
bool Valid(EProphecyLocomotionSelection Locomotion,EProphecyEquipmentSelection Equipment);
}
