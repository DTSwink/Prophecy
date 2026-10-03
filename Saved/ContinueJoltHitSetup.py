from pathlib import Path
p=Path('Saved/FinishJoltHitBridge.py');s=p.read_text()
head=s[:s.index("f='Source/GameAnimationSample3/Private/ProphecyAgent.cpp'")]
tail=s[s.index('# Locate state construction.'):]
# Remove duplicate prefix edits caused by the interrupted generator before completing its tail.
paths=['Source/GameAnimationSample3/Private/ProphecyAgent.cpp',
       'Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp',
       'Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkNNJolt.cpp']
blocks=['\t\tPhysicalMesh->OnComponentHit.AddUniqueDynamic(this, &AProphecyAgent::HandleMeshHit);\n',
        '    Mesh->OnComponentHit.AddUniqueDynamic(Agent, &AProphecyAgent::HandleMeshHit);\n',
        '#include "ProphecyHitEventTestSink.h"\n#include "UObject/StrongObjectPtr.h"\n#include "ProphecyJoltWorldSubsystem.h"\n',
        '    TStrongObjectPtr<UProphecyHitEventTestSink> HitSink;\n    int64 InitialHits = 0;\n    bool bHitEvents = false;\n',
        '        Agent->SetGeneratePhysicalHitEvents(FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchHitEvents")));\n']
for file in paths:
 q=Path(file);text=q.read_text()
 for block in blocks:
  while block+block in text:text=text.replace(block+block,block)
 q.write_text(text,newline='\n')
exec(head+"f='Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkNNJolt.cpp'\n"+tail)
