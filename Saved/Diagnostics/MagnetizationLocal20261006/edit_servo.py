from pathlib import Path
p=Path('Plugins/ProphecyJolt/Source/ProphecyJolt/Public/ProphecyJoltWorldSubsystem.h');s=p.read_text();at=s.index('struct FProphecyJoltRigVelocityTarget');i=s.index('\n};',at);s=s[:i]+'''
    // Optional physical-parent reference. WorldAlpha=1 keeps the original world servo.
    FProphecyJoltBodyHandle Parent;
    FTransform ParentStart = FTransform::Identity;
    FTransform ParentTarget = FTransform::Identity;
    float WorldAlpha = 1.f;
'''+s[i:];p.write_text(s)
p=Path('Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltVelocityServo.h');s=p.read_text().replace('double TrajectoryElapsedSeconds = 0.0;','''double TrajectoryElapsedSeconds = 0.0;
        JPH::BodyID Parent;
        FTransform ParentStart = FTransform::Identity, ParentTarget = FTransform::Identity;
        float WorldAlpha = 1.f;''');s=s.replace('    struct FSample','''    struct FParentSample
    {
        FTransform Pose;
        FVector COM=FVector::ZeroVector, Linear=FVector::ZeroVector, Angular=FVector::ZeroVector;
        bool Valid=false;
    };
    struct FSample''',1);s=s.replace('TArray<FSample> Samples;', 'TArray<FSample> Samples;\n    TArray<FParentSample> ParentSamples;\n    bool HasLocalTargets=false;');p.write_text(s)
p=Path('Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltVelocityServo.cpp');s=p.read_text();needle='bool CalculateRewrite(';idx=s.index(needle);s=s[:idx]+'''bool ReadParent(const FVelocityServo::FTarget& Target,const JPH::BodyLockInterface& Locks,FVelocityServo::FParentSample& Sample)
{
    using namespace Conversions;
    Sample.Valid=false;
    if(Target.WorldAlpha>=1.f)return true;
    JPH::BodyLockRead Lock(Locks,Target.Parent);
    if(!Lock.SucceededAndIsInBroadPhase())return false;
    const auto& B=Lock.GetBody();
    Sample.Pose=FTransform(FromJoltRotation(B.GetRotation()),FromJoltPosition(B.GetPosition()));
    Sample.COM=FromJoltPosition(B.GetCenterOfMassPosition());
    Sample.Linear=FromJoltLinearVelocity(B.GetLinearVelocity());
    Sample.Angular=FromJoltAngularVelocity(B.GetAngularVelocity());Sample.Valid=true;return true;
}

'''+s[idx:];s=s.replace('const FTransform* TargetOffset)\n{','const FTransform* TargetOffset,const FVelocityServo::FParentSample* Parent=nullptr)\n{',1)
needle='    // The authored target is the body origin;';i=s.index(needle);s=s[:i]+'''    FVector ParentLinear=FVector::ZeroVector,ParentAngular=FVector::ZeroVector;
    if(Target.WorldAlpha<1.f)
    {
        if(!Parent || !Parent->Valid)return false;
        const double Alpha=Target.TrajectoryDurationSeconds>0
            ? FMath::Clamp(TrajectoryElapsedSeconds/Target.TrajectoryDurationSeconds,0.,1.) : 1.;
        const FTransform AuthoredParent(FQuat::Slerp(Target.ParentStart.GetRotation(),Target.ParentTarget.GetRotation(),Alpha).GetNormalized(),
            FMath::Lerp(Target.ParentStart.GetLocation(),Target.ParentTarget.GetLocation(),Alpha));
        const FTransform LocalTarget=FTransform(TargetRotation,TargetPositionCm).GetRelativeTransform(AuthoredParent)*Parent->Pose;
        TargetPositionCm=FMath::Lerp(LocalTarget.GetLocation(),TargetPositionCm,Target.WorldAlpha);
        TargetRotation=FQuat::Slerp(LocalTarget.GetRotation(),TargetRotation,Target.WorldAlpha).GetNormalized();
        // Parent motion is measured before ANY servo writes: target order cannot change the result.
        ParentLinear=(Parent->Linear+Parent->Angular.Cross(Sample.PositionCm-Parent->COM))*(1.-Target.WorldAlpha);
        ParentAngular=Parent->Angular*(1.-Target.WorldAlpha);
    }
'''+s[i:];s=s.replace('const FVector Desired = (TargetPositionCm - Sample.PositionCm) / DenominatorSeconds;', 'const FVector Desired = (TargetPositionCm - Sample.PositionCm) / DenominatorSeconds + ParentLinear;')
s=s.replace('const FVector Desired = Axis.GetSafeNormal() * (Angle / DenominatorSeconds);','const FVector Desired = Axis.GetSafeNormal() * (Angle / DenominatorSeconds) + ParentAngular;')
# Transactional validation of the optional local packet.
s=s.replace('if (Target.Body.IsInvalid() || UniqueBodies', '''if (!FMath::IsFinite(Target.WorldAlpha) || Target.WorldAlpha<0 || Target.WorldAlpha>1 ||
            (Target.WorldAlpha<1 && (Target.Parent.IsInvalid() || Target.Parent==Target.Body ||
                Target.ParentStart.ContainsNaN() || Target.ParentTarget.ContainsNaN() ||
                !Target.ParentStart.GetRotation().IsNormalized() || !Target.ParentTarget.GetRotation().IsNormalized())) ||
            Target.Body.IsInvalid() || UniqueBodies''',1)
# Identify actual commit source below.
s=s.replace('Samples.SetNum(Targets.Num());','''Samples.SetNum(Targets.Num());
    HasLocalTargets=Targets.ContainsByPredicate([](const FTarget& T){return T.WorldAlpha<1.f;});
    ParentSamples.SetNum(HasLocalTargets?Targets.Num():0);''')
s=s.replace('        const JPH::BodyLockRead Lock(ReadLocks, Target.Body);','''        FParentSample Parent;
        if(!ReadParent(Target,ReadLocks,Parent))
        { ++InvalidBodies;OutError=TEXT("Invalid physical parent in servo packet.");return false; }
        const JPH::BodyLockRead Lock(ReadLocks, Target.Body);''',1)
s=s.replace('Offsets ? Offsets->Find(Target.Body.GetIndexAndSequenceNumber()) : nullptr))','Offsets ? Offsets->Find(Target.Body.GetIndexAndSequenceNumber()) : nullptr, &Parent))',1)
s=s.replace('    Samples.Reset();','    Samples.Reset();ParentSamples.Reset();HasLocalTargets=false;',1)
idx=s.index('void FVelocityServo::OnStep');before=s[:idx];rest=s[idx:];rest=rest.replace('    for (int32 Index = 0; Index < Targets.Num(); ++Index)','''    if(HasLocalTargets)for(int32 I=0;I<Targets.Num();++I)
        ReadParent(Targets[I],Context.mPhysicsSystem->GetBodyLockInterfaceNoLock(),ParentSamples[I]);
    for (int32 Index = 0; Index < Targets.Num(); ++Index)''',1);rest=rest.replace('Offsets ? Offsets->Find(Target.Body.GetIndexAndSequenceNumber()) : nullptr)','Offsets ? Offsets->Find(Target.Body.GetIndexAndSequenceNumber()) : nullptr,HasLocalTargets?&ParentSamples[Index]:nullptr)',1);s=before+rest;p.write_text(s)
p=Path('Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltWorldSubsystem.cpp');s=p.read_text();needle='        UniqueSlots.Add(Target.Handle.Slot);';idx=s.index(needle,s.index('UProphecyJoltWorldSubsystem::PublishRigVelocityTargets'));s=s[:idx]+'''        const FBodySlot* Parent=Target.WorldAlpha<1.f?Native->Find(Target.Parent):nullptr;
        if(!FMath::IsFinite(Target.WorldAlpha) || Target.WorldAlpha<0 || Target.WorldAlpha>1 ||
            (Target.WorldAlpha<1.f && (!Parent || !SameRig(Parent->OwnerRig,Handle) || Parent->Body==Slot->Body ||
                Target.ParentStart.ContainsNaN() || Target.ParentTarget.ContainsNaN() ||
                !Target.ParentStart.GetRotation().IsNormalized() || !Target.ParentTarget.GetRotation().IsNormalized())))
            return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Local servo targets require a different valid parent in the same rig and finite parent frames."));
'''+s[idx:];needle='        NativeTarget.Body = Slot->Body;';s=s.replace(needle,needle+'''
        if(Parent)
        { NativeTarget.Parent=Parent->Body;NativeTarget.ParentStart=Target.ParentStart;NativeTarget.ParentTarget=Target.ParentTarget; }
        NativeTarget.WorldAlpha=Target.WorldAlpha;''',1);p.write_text(s)
# Character caches closest physical ancestor at admission, then publishes parent authored frames in O(1).
p=Path('Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp');s=p.read_text();s='#include "ProphecyPhysicalContext.h"\n'+s;s=s.replace('    TArray<int32> Parents;', '    TArray<int32> Parents;\n    TArray<int32> BodyParents;');idx=s.index('    if (!Pending->ComposeLayout.Build');s=s[:idx]+'''    Pending->BodyParents.Init(INDEX_NONE,Pending->BodyNames.Num());
    for(int32 I=0;I<Pending->BodyNames.Num();++I)
    {
        if(Pending->BodyNames[I]==TEXT("pelvis"))continue;
        for(int32 B=Skeleton.GetParentIndex(Pending->Mappings[I].BoneIndex);B!=INDEX_NONE;B=Skeleton.GetParentIndex(B))
        {
            const int32 P=Pending->BodyNames.IndexOfByKey(Skeleton.GetBoneName(B));
            if(P!=INDEX_NONE){Pending->BodyParents[I]=P;break;}
        }
    }
'''+s[idx:];s=s.replace('    const float CalfFootLeeway=', '    const float WorldAlpha=ProphecyPhysicalContext::MagnetizationMode(Agent);\n    const float CalfFootLeeway=',1)
needle='        Target.TargetRotation = BodyWorld.GetRotation();';s=s.replace(needle,needle+'''
        const int32 Parent=State->BodyParents[Index];
        if(WorldAlpha<1.f && Parent!=INDEX_NONE)
        {
            const int32 P=State->TargetNameLookup.GetIndices()[Parent];
            if(!Interpolated.IsValidIndex(P))return Fail(OutError,TEXT("Missing authored physical-parent target."));
            Target.Parent=State->Handles[Parent];Target.ParentTarget=Interpolated[P];
            const auto* Start=State->AuthoredTargetHistory.GetStart(Parent,State->ExpectedWorldSteps);
            Target.ParentStart=Start?*Start:Target.ParentTarget;Target.WorldAlpha=WorldAlpha;
        }''',1);p.write_text(s)
