# ManualCrowd: unrecorded Chaos comparison draft

Source-only checkpoint. No build or UE process was run. Apply `ManualCrowdRouting.patch` to the current game benchmark, then add `Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkManualCrowd.cpp`. The complete modified header/cpp are review copies; prefer the isolated patch so later profiling changes are preserved. No launcher, production Agent, profile, physics asset, recorder implementation or Jolt owner source is changed.

Baseline SHA256 at patch generation:

- `Source/GameAnimationSample3/Public/ProphecyPhysicsBenchmark.h`: `8D1829FA8BC917574686598C1FC69F846CD014F9BCE7D004C7987422B25B41FC`.
- `Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmark.cpp`: `0DA7F75909984883E219C5457FC50C48E3B303ABC1F53514A3DBCEC9245E001E`.

The baseline copies include the root task's `FixturePosePublish` timing scope and CSV measured/frame/world-ms markers. The patch retains them. Existing CSV launcher, stdout and process-priority handling remain untouched.

## Execution contract

Explicit `PhysicsBenchMethods=ManualCrowd` selects mode 16. Count is 1..100, repeats 1, warmup at least 30, samples at most 3600, synchronous physics, sole method. Air/floor case selection and the original fixed 60 Hz world/disabled-substepping benchmark setup are unchanged. Use the existing launcher and change the method/count arguments; use the same warmup, samples, floor, renderer, process priority and build as the matched JoltCrowd run. The direct comparison at Count=1 is JoltLive; JoltCrowd currently requires at least two agents.

Both crowd modes call the **same** `PrepareManualAgent` function, including the 22-body/21-joint/88-bone source, separate PhysicalMesh, 600 cm placement, current effective control settings and explicit WorldStatic-only contacts. Both call the **same** `PublishManualPose` branch: stationary warmup, then 30 Hz pose-store updates before the actual Agent publisher at 60 Hz. ManualCrowd leaves the source in Chaos Physical mode throughout measurement. It never calls BeginCapture, publishes replay packets, performs a Jolt handoff, or creates Jolt bodies. The existing callback's opt-in diagnostic branch therefore has no recording buffer or packet/step copy workload.

Initialization after warmup is before `TickStart`. Validation is after the `WorldMs` endpoint. World timing includes synthetic pose generation/publication, Agent work, native Chaos step and normal skeletal/component work. It is **wall latency**, not CPU summed across worker threads. `FrameMs` includes validation and boundary audit cost. The root's CSV markers can select measured rows; engine CPU profiling remains necessary for the user's total CPU target. No claim about rendered FPS or the actual NN manager is made from this fixture.

## Validation and limits

At initialization and each sample, require the original native body identities to remain dynamic and finite, exact 22N world dynamic bodies, original 21N native joint identities with valid/unbroken constraints and unchanged reflected profiles, stable effective body controls, the expected manual source flags/30 Hz pose IDs, and no initialized Jolt world or registered Jolt characters. Read all 88N feedback bones and compare against retained mesh sockets in the inherited feedback frame. This is a presentation/ownership check, not an independent trajectory oracle.

Boundary-only `ReadCapture` verifies the actual callback exists and responds that it is not recording. This read never creates a callback/buffer. It deliberately uses the current diagnostic API's exact negative response; if that response changes, update this check rather than starting capture to make the benchmark pass.

Awake counts are recorded per agent/frame and summarized as minimum awake/all-awake. The benchmark adds no wake calls, impulses or sleep-policy changes. A sleeping Chaos workload must be reported when comparing against an always-active Jolt workload; such a result cannot establish equal active solver cost. Teardown uses the public Kinematic transition and requires zero remaining Chaos dynamic bodies.

The new mode preserves authored Chaos angular profiles. JoltCrowd's authorized hard angular limits are a functional backend choice, so these runs are not a solver trajectory-equivalence test. The generic `Audit` target-error numbers still use their historical instantaneous/phase-offset formula and are explicitly labeled diagnostic; they do not represent the manual interpolated BodyFromBone controller endpoint. Actual NN inference, recurrent feedback, manager scheduling, production root movement, visible rendering and production contacts remain a separate representative performance gate.

## Range-check audit

- Recorder initialization/save are now `IsRecordingMode(12/13)`, excluding 14/15/16 explicitly.
- Jolt-owner shutdown is `IsJoltMode(14/15)`, so mode 16 cannot shut down an unrelated owner.
- Manual preparation, authored publication and rig audit use `IsManualFixtureMode(12/13/14/15/16)`.
- Mode 16 has explicit Initialize/Validate/Save routing and is excluded from default method sweeps unless requested.
- Legacy `Mode>=10` preparation/publication branches remain reachable only for 10/11 because manual modes continue earlier. Legacy `Mode>=2` driver creation remains in the non-agent branch, so 16 cannot reach it.
- Generic audit `Mode>=10` retains its native-agent target diagnostic behavior for 16; the new report explains its limitation. No other numeric mode-range use occurs in the benchmark family.

Required next checks are compilation, a short Count=1 air/floor run, then matched Count=100 runs with the same settings and engine CSV. The draft has no runtime evidence yet.
