from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyDoubleReachAnimInstance.cpp');s=p.read_text();Path('Saved/Diagnostics/GoldenRulesFix/before/'+p.name).write_text(s)
s='#include "Engine/World.h"\n#include "ProphecyBlendClock.h"\n'+s
s=s.replace('EvaluationDeltaSeconds = FMath::Clamp(DeltaSeconds, 0.0f, 0.1f);','''const UWorld* World = Instance->GetWorld();
		const bool Advance = World && !World->IsPaused() && DeltaSeconds > 0 && LastGameFrame != GFrameCounter;
		EvaluationDeltaSeconds = Advance ? float(ProphecyBlendClock::TickSeconds) : 0.f;
		if (Advance) LastGameFrame = GFrameCounter;''')
s=s.replace('ModeBlendLinear + DeltaSeconds / TransitionDuration','ModeBlendLinear + EvaluationDeltaSeconds / TransitionDuration').replace('AnimationTimeSeconds += DeltaSeconds * AnimationPlayRate;','AnimationTimeSeconds += EvaluationDeltaSeconds * AnimationPlayRate;')
s=s.replace('float EvaluationDeltaSeconds = 0.0f;', 'float EvaluationDeltaSeconds = 0.0f;\n\tuint64 LastGameFrame = MAX_uint64;')
p.write_text(s)
for name in ['TestProphecySword.py','TestFistDeformation.py','TestProphecyInterpolation.py']:
 p=Path('Tools/NN')/name;s=p.read_text();Path('Saved/Diagnostics/GoldenRulesFix/before/'+name).write_text(s)
 pos=s.index('state=') if name!='TestProphecyInterpolation.py' else s.index('state =')
 s=s[:pos]+'''# Never attach this mutating test to the user's Play session.
editor_guard = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor_guard.get_game_world() is None, 'Stop your Play session before running this test'
import time
owned_world = None
watchdog_start = time.monotonic()
finished = False

'''+s[pos:]
 s=s.replace('def finish(error=None):', 'def finish(error=None):\n    global finished\n    if finished: return\n    finished = True')
 s=s.replace('def finish(reason):', 'def finish(reason):\n    global finished\n    if finished: return\n    finished = True')
 s=s.replace("    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()", "    if owned_world is not None and editor_guard.get_game_world() == owned_world:\n        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()")
 marker='    try:\n'
 idx=s.index(marker,s.index('def tick('))
 s=s[:idx]+s[idx:].replace(marker,'''    global owned_world
    try:
        if time.monotonic() - watchdog_start > 60:
            raise RuntimeError('Diagnostic timed out (Play failed, stopped, or paused)')
        current_world = editor_guard.get_game_world()
        if owned_world is not None and current_world != owned_world:
            raise RuntimeError('Owned Play session ended or was replaced')
        if current_world is not None and owned_world is None:
            owned_world = current_world
''',1)
 # Record directories even when startup fails.
 if name=='TestProphecyInterpolation.py':
  s=s.replace("    path.write_text", "    path.parent.mkdir(parents=True, exist_ok=True)\n    path.write_text")
 p.write_text(s)
