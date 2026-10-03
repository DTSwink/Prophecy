from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyWalkTickPinning.h');s=p.read_text().replace('FVector2f Last=FVector2f(-1,-1);','FVector2f Last=FVector2f(-1,-1),Effective=FVector2f::ZeroVector;\n    double SampleTime=-1;');p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyWalkTickPinningRuntime.inl');s=p.read_text();s=s.replace('''        if(auto* D=Impl->PinningDebug.Find(Index))if(D->Owner.Get()==A)
        {D->Locomotion.EffectivePinning=FVector2D(Effective);D->Locomotion.SampleTimeSeconds=GetWorld()->GetTimeSeconds();}''','''        T->Effective=Effective;T->SampleTime=GetWorld()->GetTimeSeconds();''');p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyNNInputDebug.inl');s=p.read_text().replace('''\tSample = Cached;
\treturn true;''','''\tSample = Cached;
    if(!bAttack) if(const auto* T=ProphecyWalkPinning::FindTickPinning(Actor))
        if(T->HasBase && T->SampleTime>=0 && !T->Dirty)
        {Sample.EffectivePinning=FVector2D(T->Effective);Sample.SampleTimeSeconds=T->SampleTime;}
\treturn true;''',1);p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyNNPoseTypes.cpp');s=p.read_text();s=s.replace('''        const int32 I=Indices[J];P->PreviousComponentTransforms[I]=Previous[J];P->ComponentTransforms[I]=Current[J];''','''        const int32 I=Indices[J];
        // Adding a linear endpoint correction to Hermite adds its world delta to
        // both tangents. Preserve the existing curve and make restoration reversible.
        if(P->InterpolationStartTangents.IsValidIndex(I) && P->InterpolationEndTangents.IsValidIndex(I))
        {
            const FVector Old=(P->ComponentTransforms[I]*P->ComponentWorldTransform).GetLocation()
                -(P->PreviousComponentTransforms[I]*P->PreviousComponentWorldTransform).GetLocation();
            const FVector New=(Current[J]*P->ComponentWorldTransform).GetLocation()
                -(Previous[J]*P->PreviousComponentWorldTransform).GetLocation();
            P->InterpolationStartTangents[I]+=New-Old;P->InterpolationEndTangents[I]+=New-Old;
        }
        P->PreviousComponentTransforms[I]=Previous[J];P->ComponentTransforms[I]=Current[J];''');p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyWalkPinningLibrary.cpp');s=p.read_text().replace('else Smoothing.Remove(Agent);','else {ResetTickPinning(Agent);Smoothing.Remove(Agent);}');p.write_text(s)
