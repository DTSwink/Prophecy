from pathlib import Path
def edit(f,a,b):
 p=Path(f);s=p.read_text();assert s.count(a)==1,(f,a[:70],s.count(a));p.write_text(s.replace(a,b),newline='\n')
f='Source/GameAnimationSample3/Private/ProphecyAgent.cpp'
edit(f,'void AProphecyAgent::SetGeneratePhysicalHitEvents(bool bEnabled)\n{', 'void AProphecyAgent::SetGeneratePhysicalHitEvents(bool bEnabled)\n{') if False else None
a='''\tif (JoltCharacter) JoltCharacter->SetHitEventsEnabled(bEnabled);
\tif (USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh())
\t{'''
edit(f,a,a+'\n\t\tPhysicalMesh->OnComponentHit.AddUniqueDynamic(this, &AProphecyAgent::HandleMeshHit);')
f='Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp'
edit(f,'    Owner->SetRigHitEvents(Pending->RigHandle, Mesh, Agent->bGeneratePhysicalHitEvents);','''    Mesh->OnComponentHit.AddUniqueDynamic(Agent, &AProphecyAgent::HandleMeshHit);
    Owner->SetRigHitEvents(Pending->RigHandle, Mesh, Agent->bGeneratePhysicalHitEvents);''')
# Explicit benchmark observer counts the actual Agent delegate, not just queued contacts.
f='Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkNNJolt.cpp'
edit(f,'#include "ProphecyAgent.h"', '#include "ProphecyAgent.h"\n#include "ProphecyHitEventTestSink.h"\n#include "UObject/StrongObjectPtr.h"\n#include "ProphecyJoltWorldSubsystem.h"')
edit(f,'    int32 ValidatedFrames = 0, FramesWithoutNNStep = 0;','''    int32 ValidatedFrames = 0, FramesWithoutNNStep = 0;
    TStrongObjectPtr<UProphecyHitEventTestSink> HitSink;
    int64 InitialHits = 0;
    bool bHitEvents = false;''')
edit(f,'        Agent->bAutoEnsureStandaloneNNManager = true;', '''        Agent->SetGeneratePhysicalHitEvents(FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchHitEvents")));
        Agent->bAutoEnsureStandaloneNNManager = true;''')
# Locate state construction.
p=Path(f);s=p.read_text();a=next(l for l in s.splitlines() if 'Pending = MakeShared<FProphecyNNJoltBenchmarkState>' in l)
edit(f,a,a+'''
    Pending->bHitEvents = FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchHitEvents"));
    Pending->HitSink.Reset(NewObject<UProphecyHitEventTestSink>());
    for (auto* Mesh : Meshes)
        CastChecked<AProphecyAgent>(Mesh->GetOwner())->OnPhysicalHit.AddDynamic(
            Pending->HitSink.Get(), &UProphecyHitEventTestSink::PhysicalHit);''')
edit(f,'    NNJoltState->LastStats = NNJoltState->InitialStats;', '''    NNJoltState->LastStats = NNJoltState->InitialStats;
    NNJoltState->InitialHits = NNJoltState->HitSink->PhysicalHits;''')
edit(f,'    Summary->SetBoolField(TEXT("success"), false);','''    Summary->SetBoolField(TEXT("success"), false);
    const int64 DeliveredHits = NNJoltState->HitSink->PhysicalHits - NNJoltState->InitialHits;
    Summary->SetBoolField(TEXT("hit_events_enabled"), NNJoltState->bHitEvents);
    Summary->SetNumberField(TEXT("physical_hit_delegates_delivered"), double(DeliveredHits));
    Summary->SetNumberField(TEXT("physical_hits_per_frame"), double(DeliveredHits) / Samples);
    if ((NNJoltState->bHitEvents ? DeliveredHits <= 0 : DeliveredHits != 0) || !NNJoltState->HitSink->bOnlyGameThread)
    { Error = TEXT("Hit-event benchmark did not observe the requested real game-thread Agent delegate delivery."); return false; }''')
f='Tools/NN/RunSterilePhysicsBenchmark.ps1'
edit(f,'    [switch]$MovementOnly,','    [switch]$MovementOnly,\n    [switch]$HitEvents,')
edit(f,"if ($MovementOnly) { $benchArgs+=' -PhysicsBenchMovementOnly' }", "if ($MovementOnly) { $benchArgs+=' -PhysicsBenchMovementOnly' }\nif ($HitEvents) { $benchArgs+=' -PhysicsBenchHitEvents' }")
print('Bound Agent forwarding and benchmark event counter.')
