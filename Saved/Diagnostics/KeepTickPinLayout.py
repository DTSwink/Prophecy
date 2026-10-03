from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyWalkTickPinning.h');s=p.read_text().replace('    FVector WorldOffset[2]={FVector::ZeroVector,FVector::ZeroVector};\n','');s=s.replace('FTickPinning* FindTickPinning','struct FTickPinOffsets {FVector WorldOffset[2]={FVector::ZeroVector,FVector::ZeroVector};};\nFTickPinOffsets& TickOffsets(const AProphecyAgent* Agent);\nFTickPinning* FindTickPinning');p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyWalkPinningLibrary.cpp');s=p.read_text().replace('static TMap<TWeakObjectPtr<const AProphecyAgent>,FTickPinning> TickPins;', '''static TMap<TWeakObjectPtr<const AProphecyAgent>,FTickPinning> TickPins;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FTickPinOffsets> TickPinOffsets;
FTickPinOffsets& TickOffsets(const AProphecyAgent* A) {return TickPinOffsets.FindOrAdd(A);}''');s=s.replace('void ResetTickPinning(const AProphecyAgent* A)\n{','void ResetTickPinning(const AProphecyAgent* A)\n{\n    TickPinOffsets.Remove(A);');s=s.replace('for (auto It=TickPins.CreateIterator();It;++It)','for (auto It=TickPinOffsets.CreateIterator();It;++It)\n                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();\n            for (auto It=TickPins.CreateIterator();It;++It)');p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyWalkTickPinningRuntime.inl');s=p.read_text().replace('T->WorldOffset[I]','Offsets.WorldOffset[I]');s=s.replace('''        const FVector2f Value(S->Current[0],S->Current[1]);''','''        auto& Offsets=ProphecyWalkPinning::TickOffsets(A);
        const FVector2f Value(S->Current[0],S->Current[1]);''');s=s.replace('''        if(!A->bNNInferenceEnabled || Agent.Slash.bActive || Agent.DefensePose)continue;
        for''','''        if(!A->bNNInferenceEnabled || Agent.Slash.bActive || Agent.DefensePose)continue;
        auto& Offsets=ProphecyWalkPinning::TickOffsets(A);
        for''');p.write_text(s)
