#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyNNModifierDebug
{
// Observers only: no Consume/Step/Prepare/Resolve calls and no pose/body sampling.
struct FRow { FString Key,Stage,Label,Details;FColor Color; };
struct FReport
{
    const AProphecyAgent* Agent=nullptr;
    int32 PoseId=INDEX_NONE;
    bool Attack=false,Half=false,Defense=false,Dodge=false,LowerLoco=false,UpperLoco=false;
    bool WalkFeet=false,Regional=false,RecoveryPresentation=true;
    float Walk=1;
    TArray<FRow> Rows;
    void Add(const TCHAR* Key,const TCHAR* Stage,const TCHAR* Label,FString Details=FString());
    FString Text() const;
};
void Entry(FReport& R);
void EntryCore(FReport& R);
void EntryHands(FReport& R);
void AttackMotion(FReport& R);
void FKReturn(FReport& R);
void DodgeReturn(FReport& R);
void HandInertia(FReport& R);
void PelvisInertia(FReport& R);
void Lower(FReport& R);
void Drag(FReport& R);
void Forearm(FReport& R);
void Armed(FReport& R);
void Presentation(FReport& R);
void Fists(FReport& R);
void PosePresentation(FReport& R);
void Pinning(FReport& R);
void ClampBlends(FReport& R);
void Roots(FReport& R);
}
