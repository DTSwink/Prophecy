from pathlib import Path
root=Path(__file__).resolve().parents[3]/'Source/GameAnimationSample3'
# Concrete overrides: inherited Blueprint UFunctions dispatch through these virtual methods.
methods=[
('AddForce','FVector Force, FName BoneName, bool bAccelChange','Force, BoneName, bAccelChange','Force','Force','bAccelChange','bone'),
('AddImpulse','FVector Impulse, FName BoneName, bool bVelChange','Impulse, BoneName, bVelChange','Impulse','Impulse','bVelChange','bone'),
('AddTorqueInRadians','FVector Torque, FName BoneName, bool bAccelChange','Torque, BoneName, bAccelChange','Torque','Torque','bAccelChange','bone'),
('AddAngularImpulseInRadians','FVector Impulse, FName BoneName, bool bVelChange','Impulse, BoneName, bVelChange','AngularImpulse','Impulse','bVelChange','bone'),
('AddForceAtLocation','FVector Force, FVector Location, FName BoneName','Force, Location, BoneName','Force','Force','false','point'),
('AddForceAtLocationLocal','FVector Force, FVector Location, FName BoneName','Force, Location, BoneName','Force','Force','false','local'),
('AddImpulseAtLocation','FVector Impulse, FVector Location, FName BoneName','Impulse, Location, BoneName','Impulse','Impulse','false','point'),
('AddRadialForce','FVector Origin, float Radius, float Strength, ERadialImpulseFalloff Falloff, bool bAccelChange','Origin, Radius, Strength, Falloff, bAccelChange','Force','FVector::ZeroVector','bAccelChange','radial'),
('AddRadialImpulse','FVector Origin, float Radius, float Strength, ERadialImpulseFalloff Falloff, bool bVelChange','Origin, Radius, Strength, Falloff, bVelChange','Impulse','FVector::ZeroVector','bVelChange','radial'),
('SetPhysicsLinearVelocity','FVector NewVel, bool bAddToCurrent, FName BoneName','NewVel, bAddToCurrent, BoneName','LinearVelocity','NewVel','false','velocity'),
('SetPhysicsAngularVelocityInRadians','FVector NewAngVel, bool bAddToCurrent, FName BoneName','NewAngVel, bAddToCurrent, BoneName','AngularVelocity','NewAngVel','false','velocity'),
('SetAllPhysicsLinearVelocity','FVector NewVel, bool bAddToCurrent','NewVel, bAddToCurrent','LinearVelocity','NewVel','false','all'),
('SetAllPhysicsAngularVelocityInRadians','const FVector& NewAngVel, bool bAddToCurrent','NewAngVel, bAddToCurrent','AngularVelocity','NewAngVel','false','all'),
]
below=[
('AddForceToAllBodiesBelow','FVector Force, FName BoneName, bool bAccelChange, bool bIncludeSelf','Force, BoneName, bAccelChange, bIncludeSelf','Force','Force','bAccelChange','below'),
('AddImpulseToAllBodiesBelow','FVector Impulse, FName BoneName, bool bVelChange, bool bIncludeSelf','Impulse, BoneName, bVelChange, bIncludeSelf','Impulse','Impulse','bVelChange','below')]
for base in ('SkeletalMeshComponent','StaticMeshComponent'):
    name='ProphecyPhysics'+base
    selected=methods+(below if base=='SkeletalMeshComponent' else [])
    h=['#pragma once','', '#include "CoreMinimal.h"',f'#include "Components/{base}.h"',f'#include "{name}.generated.h"','',
       '/** Standard UE physics commands use Jolt when it owns this receiver; otherwise use Chaos. */',
       'UCLASS(ClassGroup = Physics, meta = (BlueprintSpawnableComponent))',
       f'class GAMEANIMATIONSAMPLE3_API U{name} : public U{base}', '{','    GENERATED_BODY()','public:']
    cpp=[f'#include "{name}.h"','#include "ProphecyJoltMeshPhysics.h"','', 'using namespace ProphecyJolt::MeshPhysics;','']
    for method,args,call,op,value,independent,selection in selected:
        h.append(f'    virtual void {method}({args}) override;')
        cpp += [f'void U{name}::{method}({args})','{']
        if selection=='radial':
            flag='bIgnoreRadialForce' if op=='Force' else 'bIgnoreRadialImpulse'
            cpp.append(f'    if ({flag}) return;')
        cpp += ['    FProphecyJoltPhysicsCommand Command;',f'    Command.Operation = EProphecyJoltPhysicsCommand::{op};',f'    Command.Value = {value};',f'    Command.bMassIndependent = {independent};','    FSelection Selection;']
        if selection in ('bone','point','local','velocity','below'): cpp.append('    Selection.Bone = BoneName;')
        if selection in ('point','local'): cpp += ['    Command.bAtPosition = true;','    Command.Position = Location;']
        if selection=='local': cpp.append('    Command.bLocalSpace = true;')
        if selection in ('velocity','all'): cpp.append('    Command.bAddToCurrent = bAddToCurrent;')
        if selection=='all': cpp.append('    Selection.Type = ESelection::All;')
        if selection=='below': cpp += ['    Selection.Type = ESelection::Below;','    Selection.bIncludeSelf = bIncludeSelf;']
        if selection=='radial': cpp += ['    Selection.Type = ESelection::Radial;','    Selection.Origin = Origin;','    Selection.Radius = Radius;','    Selection.Strength = Strength;','    Selection.Falloff = Falloff;']
        cpp += [f'    if (!Execute(*this, Command, Selection)) Super::{method}({call});','}','']
    h += ['};','']
    (root/'Public'/f'{name}.h').write_text('\n'.join(h))
    (root/'Private'/f'{name}.cpp').write_text('\n'.join(cpp))
