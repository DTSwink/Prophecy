from pathlib import Path
import re
root=Path(__file__).resolve().parents[2]
header=(root/'Source/GameAnimationSample3/Public/ProphecyPhysicsStaticMeshComponent.h').read_text()
impl=(root/'Source/GameAnimationSample3/Private/ProphecyPhysicsStaticMeshComponent.cpp').read_text()
methods=re.findall(r'virtual void (\w+)\((.*?)\) override;',header)
decl=[]
for name,args in methods:
    decl.append('    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))\n    static void '+name+'(UPrimitiveComponent* Component, '+args+');')
extra=[
('void','SetSimulatePhysics','UPrimitiveComponent* Component, bool bSimulate'),
('void','SetMassOverrideInKg','UPrimitiveComponent* Component, FName BoneName, float MassInKg, bool bOverrideMass'),
('FVector','GetPhysicsLinearVelocity','UPrimitiveComponent* Component, FName BoneName'),
('FVector','GetPhysicsLinearVelocityAtPoint','UPrimitiveComponent* Component, FVector Point, FName BoneName'),
('FVector','GetPhysicsAngularVelocityInRadians','UPrimitiveComponent* Component, FName BoneName'),
('FVector','GetPhysicsAngularVelocityInDegrees','UPrimitiveComponent* Component, FName BoneName'),
('bool','IsSimulatingPhysics','UPrimitiveComponent* Component, FName BoneName'),
('void','AddTorqueInDegrees','UPrimitiveComponent* Component, FVector Torque, FName BoneName, bool bAccelChange'),
('void','AddAngularImpulseInDegrees','UPrimitiveComponent* Component, FVector Impulse, FName BoneName, bool bVelChange'),
('void','SetPhysicsAngularVelocityInDegrees','UPrimitiveComponent* Component, FVector NewAngVel, bool bAddToCurrent, FName BoneName'),
('void','K2_SetWorldLocation','USceneComponent* Component, FVector NewLocation, bool bSweep, FHitResult& SweepHitResult, bool bTeleport'),
('void','K2_SetWorldRotation','USceneComponent* Component, FRotator NewRotation, bool bSweep, FHitResult& SweepHitResult, bool bTeleport'),
('void','K2_SetWorldTransform','USceneComponent* Component, const FTransform& NewTransform, bool bSweep, FHitResult& SweepHitResult, bool bTeleport')]
for ret,name,args in extra:
    spec='BlueprintCallable' if ret=='void' else 'BlueprintPure'
    decl.append(f'    UFUNCTION({spec}, meta=(BlueprintInternalUseOnly="true"))\n    static {ret} {name}({args});')
out='''#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Components/PrimitiveComponent.h"
#include "ProphecyJoltStandardPhysicsLibrary.generated.h"

/** Internal compiler targets. Users retain the standard Unreal Blueprint nodes and component references. */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyJoltStandardPhysicsLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
'''+ '\n'.join(decl)+'\n};\n'
(root/'Source/GameAnimationSample3/Public/ProphecyJoltStandardPhysicsLibrary.h').write_text(out)
impl=impl.replace('#include "ProphecyPhysicsStaticMeshComponent.h"','#include "ProphecyJoltStandardPhysicsLibrary.h"')
impl=impl.replace('UProphecyPhysicsStaticMeshComponent::','UProphecyJoltStandardPhysicsLibrary::')
for name,args in methods:
    impl=impl.replace(f'::{name}({args})\n{{',f'::{name}(UPrimitiveComponent* Component, {args})\n{{\n    if (!IsValid(Component)) return;')
impl=impl.replace('Execute(*this,','Execute(*Component,').replace('Super::','Component->').replace('if (bIgnoreRadial','if (Component->bIgnoreRadial')
(root/'Source/GameAnimationSample3/Private/ProphecyJoltStandardPhysicsLibrary.cpp').write_text(impl)
