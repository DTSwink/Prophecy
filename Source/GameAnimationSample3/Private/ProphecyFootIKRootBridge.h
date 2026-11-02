#pragma once
#include "CoreMinimal.h"

class FProphecyFootIKVM;

// Game-thread-only canonical root physics. One heap per enabled agent, no NN
// and no limb solving. World quantities are Unreal centimetres; JSON quantities
// are the canonical Y-up metre course frame, fixed for this enable epoch.
class FProphecyFootIKRootBridge
{
public:
    struct FContext
    {
        double Time=0;
        FVector PositionWorld=FVector::ZeroVector,VelocityWorld=FVector::ZeroVector;
        FVector VirtualPositionWorld=FVector::ZeroVector;
        double YawDegrees=0;
        FVector NormalWorld=FVector::UpVector,BodyUpWorld=FVector::UpVector,MassWorld=FVector::ZeroVector;
        FQuat BodyRotationWorld=FQuat::Identity,GaitRotationWorld=FQuat::Identity;
        FString Surface,CourseSurface,Json;
        bool Sliding=false,HasFloor=false,UseEdited=false;
    };
    struct FOutput
    {
        int32 Tick=0;
        double Time=0;
        FContext Root;
        TArray<FVector> RootsWorld; // previous/current + eight future at 30Hz
        TArray<FVector> VirtualRootsWorld; // exact NN C.transport root trajectory
        TArray<double> RootYawDegrees; // same previous/current/future window
        TArray<FContext> Frames; // every forecast sample at 120Hz
        FString Json,FramesJson,SnapshotJson,ReceiptsJson;
    };
    struct FInit
    {
        FTransform CourseWorld=FTransform::Identity;
        FVector PositionWorld=FVector::ZeroVector,VelocityWorld=FVector::ZeroVector,NormalWorld=FVector::UpVector;
        TOptional<FVector> PreviousRootWorld;
        TOptional<FVector> VirtualRootWorld,PreviousVirtualRootWorld;
        // Root alignment only: unlike imported skeletal bones, no FBX bind offset.
        TOptional<FQuat> BodyRotationWorld;
        FVector TravelVelocityWorld=FVector::ZeroVector;
        TArray<double> RootYawDegrees;
        double HeightCm=90,SpeedCmPerSecond=200,GravityCmPerSecondSquared=981,Time=0;
        FString SettingsJson=TEXT("{}"),GeometryJson,Surface,SnapshotJson;
    };
    struct FDrive { double Time=0; FVector VelocityWorld=FVector::ZeroVector; };
    struct FUpdate
    {
        // Exact material contacts from the accepted pose; omitted differs from []:
        // omitted retains prior supports, [] explicitly releases every support.
        FString SupportsJson,SupportsByTickJson,GeometryJson,SettingsJson;
        TOptional<FVector> TravelVelocityWorld;
        TArray<FDrive> FutureDrive;
        // Ten angles in the canonical fixed course basis, independent of travel.
        // Empty retains the previous heading window in the root adapter.
        TArray<double> RootYawDegrees;
        TOptional<uint32> SurfaceRevision;
    };
    struct FSupport { FString Surface; FVector PointWorld=FVector::ZeroVector; TOptional<FVector> NormalWorld; };

    FProphecyFootIKRootBridge();
    ~FProphecyFootIKRootBridge();
    bool Initialize(const FInit& Input,FOutput& Out,FString& Error);
    // Raw form also permits exact saved snapshots and independent oracle replay.
    bool InitializeJson(const FString& Input,const FTransform& CourseWorld,FOutput& Out,FString& Error);
    bool Forecast(const FUpdate& Input,int32 Ticks,FOutput& Out,FString& Error);
    bool Step(const FUpdate& Input,int32 Ticks,FOutput& Out,FString& Error);
    bool Status(FOutput& Out,FString& Error);
    void Disable();
    bool IsEnabled() const { return VM.IsValid(); }
    double LastSeconds() const;
    FString EncodeSupports(TConstArrayView<FSupport> Supports) const;

    static FVector ToCoursePosition(const FVector& World,const FTransform& CourseWorld);
    static FVector ToWorldPosition(const FVector& Course,const FTransform& CourseWorld);
    static FVector ToCourseVelocity(const FVector& World,const FTransform& CourseWorld);
    static FVector ToWorldVelocity(const FVector& Course,const FTransform& CourseWorld);
    static FQuat ToCourseRotation(const FQuat& World,const FTransform& CourseWorld);
    static FQuat ToWorldRotation(const FQuat& Course,const FTransform& CourseWorld);
private:
    bool UpdateCommand(const TCHAR* Op,const FUpdate& Input,int32 Ticks,FOutput& Out,FString& Error);
    bool Command(const FString& Input,FOutput& Out,FString& Error);
    bool Decode(const FString& Json,FOutput& Out,FString& Error) const;
    FTransform Space=FTransform::Identity;
    TUniquePtr<FProphecyFootIKVM> VM;
};
