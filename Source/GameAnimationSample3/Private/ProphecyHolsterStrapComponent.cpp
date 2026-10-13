#include "ProphecyHolsterStrapComponent.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNodeSpaceConversions.h"
#include "AnimNodes/AnimNode_RefPose.h"
#include "BoneControllers/AnimNode_AnimDynamics.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"

static TAutoConsoleVariable<int32> CVarHolsterStrap(TEXT("prophecy.HolsterStrap"),1,
    TEXT("0 pauses all cosmetic holster straps at rest; 1 permits enabled nearby straps."));

class FHolsterStrapProxy final : public FAnimInstanceProxy
{
public:
    explicit FHolsterStrapProxy(UAnimInstance* Instance):FAnimInstanceProxy(Instance)
    {
        ToComponent.LocalPose.SetLinkNode(&Reference);
        Dynamics.ComponentPose.SetLinkNode(&ToComponent);
        ToLocal.ComponentPose.SetLinkNode(&Dynamics);
        Dynamics.BoundBone.BoneName=TEXT("strap_01");Dynamics.ChainEnd.BoneName=TEXT("strap_05");
        Dynamics.bChain=true;Dynamics.SimulationSpace=AnimPhysSimSpaceType::Component;
        Dynamics.bAngularSpring=true;Dynamics.bLinearSpring=false;
        Dynamics.bUsePlanarLimit=false;Dynamics.bUseSphericalLimits=false;Dynamics.bEnableWind=false;
        Dynamics.bOverrideLinearDamping=true;Dynamics.bOverrideAngularDamping=true;
        Dynamics.ComponentLinearAccScale=FVector(1);Dynamics.ComponentLinearVelScale=FVector::ZeroVector;
        Dynamics.ComponentAppliedLinearAccClamp=FVector(3000);
        Dynamics.SimSpaceSettings.SimSpaceAngularAlpha=1.f;
        Dynamics.SimSpaceSettings.MaxAngularVelocity=10.f;Dynamics.SimSpaceSettings.MaxAngularAcceleration=100.f;
        Dynamics.NumSolverIterationsPreUpdate=8;Dynamics.NumSolverIterationsPostUpdate=2;
    }
protected:
    virtual void Initialize(UAnimInstance* Instance) override
    {
        if(const auto* C=Cast<UProphecyHolsterStrapComponent>(Instance->GetSkelMeshComponent()))
        if(const auto* Mesh=C->GetSkeletalMeshAsset()){
            const auto& Ref=Mesh->GetRefSkeleton();Dynamics.PhysicsBodyDefinitions.SetNum(5);
            for(int32 I=0;I<5;++I){
                auto& D=Dynamics.PhysicsBodyDefinitions[I];D.BoundBone.BoneName=FName(*FString::Printf(TEXT("strap_%02d"),I+1));
                const FName Next=I==4?FName(TEXT("strap_tip")):FName(*FString::Printf(TEXT("strap_%02d"),I+2));
                const int32 Child=Ref.FindBoneIndex(Next);
                const FVector Segment=Child!=INDEX_NONE?Ref.GetRefBonePose()[Child].GetTranslation():FVector(0,3,0);
                const FVector Axis=Segment.GetSafeNormal();D.LocalJointOffset=Segment*.5;
                // These boxes define inertia only (no contacts). The visible
                // leather thickness gives a near-singular twist inertia.
                D.BoxExtents=FVector(2)+Axis.GetAbs()*Segment.Length();
                const int32 K=Axis.GetAbs().GetMax()==FMath::Abs(Axis.X)?0:Axis.GetAbs().GetMax()==FMath::Abs(Axis.Y)?1:2;
                // The engine tests the positive body axis. A negative segment
                // direction must not turn the rest spring target through 180 degrees.
                D.ConstraintSetup.AngularTarget=K==0?FVector::XAxisVector:K==1?FVector::YAxisVector:FVector::ZAxisVector;
                D.ConstraintSetup.AngularTargetAxis=K==0?AnimPhysTwistAxis::AxisX:K==1?AnimPhysTwistAxis::AxisY:AnimPhysTwistAxis::AxisZ;
                D.ConstraintSetup.TwistAxis=D.ConstraintSetup.AngularTargetAxis;
            }
            Configure(*C);
        }
        FAnimInstanceProxy::Initialize(Instance);
    }
    virtual FAnimNode_Base* GetCustomRootNode() override { return &ToLocal; }
    virtual void GetCustomNodes(TArray<FAnimNode_Base*>& Out) override { Out.Append({&Reference,&ToComponent,&Dynamics,&ToLocal}); }
    virtual void PreUpdate(UAnimInstance* Instance,float DeltaSeconds) override
    {
        if(const auto* C=Cast<UProphecyHolsterStrapComponent>(Instance->GetSkelMeshComponent()))Configure(*C);
        FAnimInstanceProxy::PreUpdate(Instance,DeltaSeconds);
    }
private:
    void Configure(const UProphecyHolsterStrapComponent& C)
    {
        const float Spring=FMath::Max(0.f,C.Stiffness),Drag=FMath::Clamp(C.Damping,.7f,10.f),Gravity=FMath::Max(0.f,C.StrapGravityScale),Bend=FMath::Clamp(C.MaxBendAngle,0.f,180.f);
        if(Spring==LastSpring&&Drag==LastDrag&&Gravity==LastGravity&&Bend==LastBend)return;
        LastSpring=Spring;LastDrag=Drag;LastGravity=Gravity;LastBend=Bend;
        // AnimDynamics expects the fraction removed per second, not a damping rate.
        // Its solver uses Pow(1 - damping, dt), so values above one produce NaNs.
        const float DampingFraction=1.f-FMath::Exp(-Drag);
        Dynamics.AngularSpringConstant=Spring;Dynamics.LinearDampingOverride=DampingFraction;Dynamics.AngularDampingOverride=DampingFraction;Dynamics.GravityScale=Gravity;
        for(auto& D:Dynamics.PhysicsBodyDefinitions){
            D.ConstraintSetup.AngularLimitsMin=FVector(-Bend);
            D.ConstraintSetup.AngularLimitsMax=FVector(Bend);
        }
        Dynamics.RequestInitialise(ETeleportType::ResetPhysics);
    }
    FAnimNode_RefPose Reference;
    FAnimNode_ConvertLocalToComponentSpace ToComponent;
    FAnimNode_AnimDynamics Dynamics;
    FAnimNode_ConvertComponentToLocalSpace ToLocal;
    float LastSpring=-1,LastDrag=-1,LastGravity=-1,LastBend=-1;
};

FAnimInstanceProxy* UProphecyHolsterStrapAnimInstance::CreateAnimInstanceProxy(){return new FHolsterStrapProxy(this);}
void UProphecyHolsterStrapAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy){delete Proxy;}

UProphecyHolsterStrapComponent::UProphecyHolsterStrapComponent()
{
    PrimaryComponentTick.bCanEverTick=true;PrimaryComponentTick.TickGroup=TG_PostUpdateWork;
    SetCollisionEnabled(ECollisionEnabled::NoCollision);SetGenerateOverlapEvents(false);
    SetCanEverAffectNavigation(false);SetEnableGravity(false);
    VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    bEnableUpdateRateOptimizations=false;
}
void UProphecyHolsterStrapComponent::BeginPlay()
{
    Super::BeginPlay();SetCollisionEnabled(ECollisionEnabled::NoCollision);SetGenerateOverlapEvents(false);
    // Respect the editable Animation Blueprint assigned by the asset.
    if(!AnimClass)SetAnimInstanceClass(UProphecyHolsterStrapAnimInstance::StaticClass());
    LastTransform=GetComponentTransform();GateTicks=0;SetStrapEnabled(bStrapEnabled);
}
void UProphecyHolsterStrapComponent::SetRunning(bool bRun)
{
    if(bRun==bRunning&&bForceRefpose==!bRun)return;
    bRunning=bRun;SetForceRefPose(!bRun);ResetAnimInstanceDynamics(ETeleportType::ResetPhysics);
    LastTransform=GetComponentTransform();
    if(!bRun&&IsRegistered()&&GetSkeletalMeshAsset())RefreshBoneTransforms();
}
void UProphecyHolsterStrapComponent::UpdateEligibility()
{
    bool bRun=bStrapEnabled&&CVarHolsterStrap.GetValueOnGameThread()!=0;
    if(bRun&&MaxSimulationDistance>0){
        const auto* World=GetWorld();
        const float Range=MaxSimulationDistance*(bRunning?1.1f:1.f);
#if WITH_EDITOR
        // SIE observes the scene through editor viewports; its unpossessed game
        // camera may be far away. No rendered view yet means defer this gate.
        if(World->GetGameViewport()&&World->GetGameViewport()->IsSimulateInEditorViewport()){
            if(!World->ViewLocationsRenderedLastFrame.IsEmpty()){
                bRun=false;
                for(const FVector& View:World->ViewLocationsRenderedLastFrame)
                    if(FVector::DistSquared(View,GetComponentLocation())<=FMath::Square(Range)){bRun=true;break;}
            }
        }else
#endif
        if(auto* PC=World->GetFirstPlayerController()){
            FVector View;FRotator Rotation;PC->GetPlayerViewPoint(View,Rotation);
            bRun=FVector::DistSquared(View,GetComponentLocation())<=FMath::Square(Range);
        }
    }
    SetRunning(bRun);
}
void UProphecyHolsterStrapComponent::SetStrapEnabled(bool bEnabled)
{
    bStrapEnabled=bEnabled;SetComponentTickEnabled(bEnabled);
    if(IsRegistered()&&GetWorld()){UpdateEligibility();GateTicks=0;}
}
void UProphecyHolsterStrapComponent::ResetStrap()
{
    LastTransform=GetComponentTransform();ResetAnimInstanceDynamics(ETeleportType::ResetPhysics);
}
void UProphecyHolsterStrapComponent::TickComponent(float DeltaTime,ELevelTick TickType,FActorComponentTickFunction* TickFunction)
{
    if(!bStrapEnabled){SetStrapEnabled(false);return;}
    if(++GateTicks>=15){GateTicks=0;UpdateEligibility();}
    if(!bRunning)return; // No Super: no animation update/evaluation or solver when culled.
    const FTransform Current=GetComponentTransform();
    if(FVector::DistSquared(Current.GetLocation(),LastTransform.GetLocation())>FMath::Square(100.f)
        ||Current.GetRotation().AngularDistance(LastTransform.GetRotation())>PI*.5)ResetStrap();
    LastTransform=Current;
    Super::TickComponent(DeltaTime,TickType,TickFunction);
}
