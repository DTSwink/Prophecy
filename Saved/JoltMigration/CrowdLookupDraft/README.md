# Remaining crowd lookup audit and draft

Source only; no active changes, build or Unreal launch. No measured speed claim.

## Small changes ready for review

Add `ProphecyCrowdNameLookup.h` and `ProphecyCrowdNameLookupTests.cpp` to the game module Private directory.
Apply the three isolated patch files to current source; do not overwrite any full active file.

- `CharacterNameLookup.apply-patch.txt`: exact source/request name-array checks reuse index maps for
  target packets and completed feedback. Per-target missing-index and per-feedback output-range checks
  remain; feedback still validates every requested index before writing any output. Transforms, strengths,
  body handles and feedback carrier remain live. First duplicate-name behavior is unchanged.
- `ManagerLookups.apply-patch.txt`: numbered `FName` construction replaces formatted FString construction
  for debug ghosts. `FindObjectFast` remains live every frame, so external destruction/replacement and
  the existing show/hide behavior are unchanged. Physical resampling tests live mode first and only does
  the manual Chaos-body scan if mode alone did not require resampling. The selected agents, frequencies,
  success/failure counters and actual feedback calls are unchanged.
- `AgentInlineComponents.apply-patch.txt`: the existing live component enumeration uses inline storage
  for four skeletal components, avoiding its small heap allocation in the usual two-mesh character.
  Additional components still work through ordinary TArray growth; no component identity is cached.

Two tests: `Prophecy.Crowd.NameLookup.ExactLayoutsAndMissingNames` compares the old first-name lookup
over 88 source /25 requested bones, stable frames, reorders, duplicate/missing names and empty layouts;
`Prophecy.Crowd.NameLookup.DebugMeshNumericSuffix` verifies both FName identity and displayed suffix
against formatted names, including zero and large indices. Tests are uncompiled/unexecuted here.

UE5.7 source verifies `FName(FName Other, int32 InNumber)` in Core/Public/UObject/NameTypes.h:974,
`NAME_EXTERNAL_TO_INTERNAL(x)` at line161, and allocator-generic Actor::GetComponents plus
TInlineComponentArray in Engine/Classes/GameFramework/Actor.h:201,4023.

## Compiler and profiling audit

The current Editor module response files for ProphecyAgent.cpp, ProphecyJoltPose.cpp and
ProphecyNNLocomotionManager.cpp under Intermediate/Build/Win64/x64/UnrealEditor/Development/GameAnimationSample3
all contain `/Oi /Ob2 /Ox /Ot /fp:fast /MD`. The archived UnrealGame/Development manager response file
has those same optimization flags. No missed `/Od` or disabled optimization was found. This does not
establish executable/editor performance equivalence; runtime, instrumentation and workload still differ.

CharacterProfiling::FScope uses two FPlatformTime::Seconds calls while enabled. WindowsPlatformTime.h:26
uses QueryPerformanceCounter for Seconds. Disabled scopes skip those clock calls. Clock overhead is not
measured here and must not be assigned an invented millisecond cost. Root owns any instrumented/uninstrumented
A/B run. Nested phases must not be added: AgentTick contains target publication, RefreshBones contains the
query hook, and proxy subphases are children of animation/refresh phases.

## Unaccounted completed-publication audit

Current source already has RegistrationOwners.Find in IsStepClientRegistered (coordinator lines273–281).
ResolveClient repeats one lookup for the same GUID; both are O(1). Native FindRig is lifetime/slot/generation
validation (world owner line402), and GetDiagnostics directly copies the diagnostics struct (line1587).
Healthy diagnostics have an empty Failure FString. Neither performs a 100-rig/body traversal.

On the bulk publication path ValidatePublication executes six times: before body reads, after the parallel
evaluation wait, after animation tick, inside the query commit, after refresh/finalizers, and before the final
completed-frame commit. Each intentionally rechecks identity, registration, current mesh/carrier and native
step state across callback-capable boundaries. Weak references are resolved repeatedly within each check,
and registration does one redundant hash lookup; these are small bounded source costs, not proof of the
entire remaining roughly1.5ms. Removing validation boundaries is not justified.

To attribute residual time, root can put a dedicated scope inside ValidatePublication and, if necessary,
around query-hook arming/result retrieval. This draft does not edit the harness or profiling files.
It does not claim these lookup changes solve the 100-agent whole-pipeline target by themselves.
