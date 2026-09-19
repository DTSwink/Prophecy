#pragma once
#include "ProphecyParryRuntime.h"
#include "ProphecyDodgeLower.h"
#include "ProphecyDefenseContacts.h"
#include "ProphecyDefensePhysicalContacts.h"
#include "ProphecyDefenseNetwork.h"
#include "ProphecyNNDefenseLibrary.h"
class AProphecyAgent;
struct FProphecyLiveDefensePose
{
    TWeakObjectPtr<AProphecyAgent> Owner,Attacker;
    ProphecyDefense::FContext Context;
    ProphecyDefense::FPose CurrentPose;
    ProphecyDefense::FDefenseBox PreviousBoxes[20],PreviousAttack,NextAttack;
    ProphecyDefense::FFirstContact Order;
    TSharedPtr<FProphecyDefensePhysicalContacts> PhysicalContacts;
    bool bPhysicalContactsFailed=false;
    FTransform PreviousComponent[25],CurrentComponent[25];
    FProphecyNNDefenseStatus Status;
    FVector3f AttackerHalf;
    FName Family;
    int32 AttackerIndex=INDEX_NONE,AttackerCollider=INDEX_NONE,MaxSteps=90;
    uint32 PresentMask=0;
    bool bHasPose=false,bDodge=false;
};
struct FProphecyLiveParry : FProphecyLiveDefensePose
{
    ProphecyDefense::FParryState State;
    ProphecyDefense::FParryWork Work;
    ProphecyDefense::FPose Frozen;
    ProphecyDefense::FRootFrame NextRoot;
    float NextLower[41],NextBaseline[90];
};
struct FProphecyLiveDodge : FProphecyLiveDefensePose
{
    ProphecyDefense::FDodgeState State;
    ProphecyDefense::FDodgeWork Work;
    float NextLower[41],Pins[2];
    FVector3f WorldOrigin,CarrierOffset;
    float InitialNativeYaw=0,InitialManagedYaw=0;
    int32 Category=0;
};
struct FProphecyLiveDefenseRuntime
{
    ProphecyDefense::FGeometry Geometry;
    ProphecyDefense::FContactGeometry Contacts;
    ProphecyDefense::FContactGeometry AttackContacts;
    FProphecyDefenseNetwork ParryNetwork;
    ProphecyDefense::FGeometry DodgeGeometry;
    ProphecyDefense::FContactGeometry DodgeContacts;
    ProphecyDefense::FDodgeLowerSettings DodgeSettings[2];
    FProphecyDefenseNetwork DodgeLower[2],DodgeUpper;
    float DodgeLimits[6]={};
    TMap<int32,TUniquePtr<FProphecyLiveParry>> Parries;
    TMap<int32,TUniquePtr<FProphecyLiveDodge>> Dodges;
    TArray<float> Inputs,Outputs;
    TArray<int32> Prepared;
    TArray<float> DodgeInputs,DodgeOutputs,DodgeLowerInputs,DodgeLowerOutputs;
    TArray<int32> DodgePrepared,DodgeLowerPrepared[2];
    int32 Bones[25];
    int32 ActiveCount=0,ActiveDodgeCount=0;
    bool bInitialized=false,bParryReady=false,bDodgeReady=false;
};
