# Deferred plan: Run for movement, Walk for idle

Written September 28, 2026. **Planning only; do not implement until the user explicitly requests it.** The user is fine-tuning Run to cover moving Walk as well. The new checkpoint has not been selected, installed or validated as part of this audit. Current source, checkpoint files, Blueprint wiring and runtime behavior remain unchanged.

## Required behavior

- Nonzero planar movement input selects **Run**, including slow movement, backward movement and strafing. The old `bRun=false` movement mode must no longer force the Walk checkpoint.
- Zero planar movement input selects **Walk for idle**. Releasing input begins the existing Run-to-Walk blend immediately; residual velocity does not postpone it. A facing-only command still has zero movement input.
- Preserve **Set Locomotion Policy Blend Times**, its independent Walk-to-Run / Run-to-Walk durations, smooth reversal from the current mixture, and exact 0/1 completion. Durations remain 60 unpaused game ticks per authored second.
- Only an active transition may need both locomotion checkpoints for one agent. At either settled endpoint, no inference, correction, source-pose decode/copy, or blend pass for the unused checkpoint. Merely retaining a loaded model and its idle calibration is allowed.
- Preserve attack/defense ownership: a region fully supplied by a special needs no ordinary locomotion prediction. Half-attack legs, pending loco-drag feet and parry legs still need their locomotion source. Existing attack, ghost and defense networks are separate consumers, not duplicate Walk/Run locomotion inference.
- No new idle timers, background traces or per-frame allocations. Diagnostics must be opt-in and retire completely.

Here “full mode” means an exact checkpoint endpoint, independently of full-versus-half attack ownership.

## What the audit established

The ordinary endpoint optimization already exists. `RunModelBatch()` aggregates `RecoveryWeights.NeedsRun()/NeedsWalk()` and calls each lower model only if requested. `ApplyOutputBatch()` performs one `CorrectPolicy()` at an endpoint and two only for mixed regional weights. `FProphecyNNPolicyBlend::Reset()` reaches exact endpoints and stops its blend clock. Preserve these properties instead of treating all current frames as unconditional double inference.

The main issues are selection, additional source requests, and batching:

1. Selection still follows mover Walk/Run mode, the slow-speed Walk override, and an automatic Run override based on the encoded future trajectory. These are different from zero-versus-nonzero input.
2. Regional attack/kick recovery, optional Walk foot rotation, hand recovery, and forced Walk loco drag can request Walk while ordinary locomotion is already 100% Run. The inverse also exists: a forced Run recovery source can request Run while ordinary locomotion is 100% idle Walk.
3. Hand recovery can run the ordinary upper checkpoint again for each requested lower source, including when the named source is already the ordinary endpoint. This is additional work beyond the second lower model.
4. The lower models currently run fixed **100-row** tensors. One Walk consumer and one Run consumer cause both models to evaluate the shared tensor, including irrelevant rows. Endpoint gating prevents an unneeded model call when the entire group is homogeneous; it does not prevent unused per-agent evaluation in mixed crowds.

Do not promise a particular FPS gain. Earlier [attack measurements](AttackPerformance.md) demonstrated the shared-batch limitation, not a measured gain from this proposed refactor.

## Code and data map

Line numbers below are audit-time navigation hints; symbols are the durable references. Paths in this table are relative to the project root.

| Area | Relevant files / symbols | Refactoring consequence |
| --- | --- | --- |
| Input and public controls | `Source/GameAnimationSample3/Private/ProphecyAgent.cpp`: `SetLocomotionInput`, `SetLocomotionRunning`, `StopLocomotion`, blend/threshold setters; corresponding `Public/ProphecyAgent.h` | Keep movement intent separate from checkpoint identity. Preserve callable nodes and saved pins during migration. |
| Ordinary selection and clock | `Private/ProphecyNNPolicyBlend.h`: `ProphecySelectWalkCheckpoint`, `FProphecyNNPolicyBlend`; `Private/ProphecyRootPhysicsLibrary.cpp`: `ProphecyAutoRun`; `Private/ProphecyNNLocomotionManager.cpp`: `BuildInputBatch` (~3250, 3436) | Replace speed/mode selection in the future mode with one input-based selector. Retain directional blending and exact endpoint retirement. |
| Lower requests/output | Manager: `RunModelBatch` (~3510), `ApplyOutputBatch` (~3660), `CorrectPolicy`, `BlendLowerPolicyRegion` | Centralize final demand; do not infer one source and later consume stale output from the other. Retain one correction at endpoints. |
| Regional source recovery | `Private/ProphecyAttackRecovery.h`, `ProphecyAttackRecoveryLibrary.cpp`: `FWeights`, `Step`, `FootRotationWeights`; `Public/ProphecyAttackRecoveryLibrary.h` | Existing Normal/Walk/Run and Walk-only rotation can keep a second source alive independently of the ordinary blend. Migrate those source choices. |
| Hand sources | `Private/ProphecyHandRecovery.h`, `ProphecyHandRecoveryLibrary.cpp`: `FFrame::Need`, `Step`; `Private/ProphecyHandInertiaRuntime.inl`: `RunHandRecoverySources` (~220) | Source requests currently cause raw copies, extra lower corrections, full upper input/output scratch arrays and up to two additional upper evaluations. Remove redundant source generation in the future mode. |
| Attack skipping / loco drag | Manager: `AttackOwnsLocomotionOutput`; `Private/ProphecyAttackFootLocomotionLibrary.cpp`: `WalkWeight`, masks; `Private/ProphecyNNSlashRuntime.inl`: handoff/feedback | Keep one-way foot ownership, final locomotion sample feedback, inertia start, kick exclusion and Freeze Blend. Eliminate forced moving-Walk source demand. |
| Walk pin processing | `Private/ProphecyWalkPinningLibrary.cpp`, `ProphecyWalkTickPinningRuntime.inl`, `ProphecyWalkPinning.h`; manager `CorrectPolicy`, `UpdateWalkTickPinning`, `CommitWalkTickPinning` | Keep idle Walk pin semantics; retire active smoothing/tick-pinning work when no visible Walk contribution remains. Do not delete Run boost just because its library is named Walk. |
| Geometry and feedback | Manager: `BlendLimb`, `DecodeLocomotionPose`, `EncodePhysicalLowerSample`, component-pose encoding; `Private/ProphecyNNLowerFeedbackAlignment.inl`, `ProphecyNNPhysicalFeedbackBatch.inl` | Calibration follows the actual source, not requested movement mode. Preserve mixed history and physical feedback; these paths do not independently run Walk inference. |
| Physical settings | `Private/ProphecyPhysicalContext.cpp`, `ProphecyJointDampingLibrary.cpp`, `ProphecyHandInertiaLibrary.cpp`; `Public/ProphecyPhysicalContextTypes.h` | Walk/Run values are physical/inertia profiles driven by published weights. Keep them for idle/movement and transitions; they are not extra checkpoints. |
| Parry and dodge | `Private/ProphecyNNDefenseRuntime.inl`, `ProphecyNNDodgeRuntime.inl`, `ProphecyNNDefenseRuntime.h` | Parry consumes ordinary lower locomotion. Dodge has separate Walk/Run defense models and uses `bUseWalkPolicy` for category selection; decouple this meaning before changing the selector. |
| Startup / reset / bridge | Manager: initialization, `InitializeAgents` (~2770), `ConsumeSimBridgeFrame` (~5458); `Private/ProphecyNNAgentReset.inl`; `ProphecyAgentResetPhysics.cpp`; `ProphecyNativePhysicalAgent.cpp` | Remove mode/checkpoint conflation at every entry point, including first bridge frame and reset. Preserve reset pose/physics baselines. |
| Model loading / calibration | Manager: `FPolicyModel` (~680), `LoadRuntimeContract`, `LoadWalkRuntimeContract`, `InitializeNNE`, `InitializeWalkNNE`; `Public/ProphecyNNLocomotionManager.h` | Both models remain available. Current validation and buffers assume fixed batch 100; loading is startup cost, not a recurring second inference. |
| Export and packaging | `Tools/NN/ExportProphecyLowerBodyPolicy.py`, `ExportProphecyUpperBodyPolicy.py`, `ProphecyOnnxStaticShapes.py`; `Content/locomotion/NN/*runtime.json`; `Config/DefaultGame.ini`, module Build.cs | New Run requires its matching contract. Current lower exporter defaults to a static 100-row graph. Compact dispatch requires compatible exports and contract changes, not merely a smaller loop. |
| Movement implementation / tools | `StandaloneSim/sim_core/src/locomotion.cpp`, `include/prophecy/sim/locomotion.h`, `src/simulation.cpp`; `StandaloneSim/bridge/sim_bridge_protocol.h`, viewer bridge/pose tools | Walk/Run here govern speed caps, acceleration, braking and viewer pose selection. Do not remove these modes as a checkpoint optimization. Bridge already carries movement amplitude. |
| Blueprint migration and evidence | `Source/ProphecyEditor/Private/ProphecyBlendNodeUpgrade.cpp`, `ProphecySpecialRecoverySetup.cpp`, `ProphecySwordCollisionAudit.cpp`; `Tools/NN/TestProphecyPolicyBlend.py`, `TestProphecyCheckpointControls.py`, `AttackPerformance/` | Audit live graph and defaults when implementing; migrate only relevant source controls and preserve values/connections. Update focused tests and observability. |

`Private/` and `Public/` abbreviations in the table refer to `Source/GameAnimationSample3/`. The audit searched the first-party game/editor sources, StandaloneSim, project tools, plugin sources and configuration for checkpoint/source dependencies, then inspected the relevant implementations. No reason to change third-party physics, rendering or unrelated plugins was found.

## Implementation sequence, when requested

### 1. Establish the model contract and the input rule

Obtain the final fine-tuned Run checkpoint/export the user wants installed. Compare its 152-input / 43-output / 41-state layout, normalization, residual/reference frame, root scaling/horizon, skeleton/seed geometry, pin decoding, floor and foot-roll settings with the current runtime. The checked-in/current local lower contracts have batch 100; Walk variants declare `legacy_logit_selected`. The new Run contract must determine its own pin semantics. Do not reuse Walk decoding solely because Run now covers slow movement.

Introduce one explicit input-based selection policy for the new setup, with the current setup retained only as a comparison/rollback route during migration. Production activation waits for the user's implementation request and chosen checkpoint. No new checkpoint path should be guessed from the training folders.

Use sanitized XY movement input, with the same small zero tolerance used by input handling. Select Walk only when that requested input is zero; otherwise select Run. Do not infer idle from measured pelvis/root speed, blocked collision motion, low-speed thresholds, root-window freeze or turning alone. Nonzero input with `SpeedScale=0` is still nonzero input under this literal rule; changing that to “zero effective speed” would be a separate behavior decision.

Capture the requested-input classification **before** full attacks zero `MoverIntent.speed_amplitude` for their braking behavior. Otherwise every full attack with loco drag would accidentally select idle Walk. For AI/route/bridge ownership, derive the same predicate from its requested `speed_amplitude` before special ownership modifies it. Blueprint input retains precedence over bridge data. Keep sanitization consistent across these paths.

Keep `bRun` and `LocomotionMode` controlling the existing mover. A slow Walk-mode trajectory will be authored by the new Run checkpoint without being accelerated to running speed. Root magic, smoothing, balancing, freeze and limits still build their trajectory as before; they do not silently override the input-based checkpoint choice. Zero-input external motion/impulses need a focused visual check because the requested rule deliberately differs from speed-based selection.

The old **Set Locomotion Walk Checkpoint Speed Threshold** and **Set Locomotion Auto Run Speed Threshold** must not override the new selector. Keep serialized nodes loadable, mark their selection behavior as legacy in tooltips/docs, and report active uses in the migration audit. Their math and lookups should be absent from the new selection path.

### 2. Make all consumers obey the same source decision

Resolve lower ownership and the ordinary blend first, once per due agent. From that compute `None`, `Run`, `Walk` or `Both` demand. The exact endpoints are authoritative for every locomotion consumer, including recovery. A legacy source option must not quietly turn a settled endpoint back into dual inference.

Recommended migration for this new setup:

- **Attack/kick regional recovery:** use the ordinary idle/movement source for pelvis and both legs. Retire independent checkpoint-source holds/blends in the new mode; preserve independent pose/inertia/leg reconstruction recovery and its lower-end event timing. Keep the old serialized source enums/pins loadable, with an explicit migration report that their forced checkpoint behavior is replaced. Do not implement this by abruptly clamping a still-active forced Walk region at the ordinary blend endpoint; all checkpoint contributions must follow the ordinary continuous blend.
- **Walk foot-rotation recovery:** disable/retire the Walk-only source override in the new mode. It must not ask for a whole Walk evaluation just for foot orientation during moving Run. Existing foot rotation tempering, foot inertia and geometry remain available without another checkpoint.
- **Hand recovery:** default to the ordinary lower/upper prediction and preserve the hand's spatial recovery/tempering. Retire forced Walk/Run alternate source inference in the new mode. Skip `FFrame::Need` work, raw copies, duplicate `CorrectPolicy` and `RunHandRecoverySources` when no alternate prediction is needed. Sharing a source output is safe only when its conditioning/history/corrections are identical; do not alias different upper inputs merely because both say Run.
- **Loco drag:** use the ordinary current blend driven by pre-attack requested input. Migrate existing forced Walk/Run mode choices to that rule in the new setup, preserving enum serialization. This prevents moving drag from requesting Walk and idle drag from forcing Run. Keep thresholds, one-way release, mixed-foot feedback on both NN sides, kick exclusion, and Freeze Blend unchanged. After the last foot releases, demand becomes None on subsequent established full-attack steps.

This deliberately changes the old **source-choice** controls to satisfy “Walk only for idle, both only for the general transition.” Keeping those old controls fully effective would contradict that performance contract. Document it in the migration report rather than hiding the change. Do not discard unrelated recovery duration settings or erase the old graph nodes wholesale.

Continue preserving shared current/previous recurrent state, applied-root rebasing and actual authored mixed-foot feedback. A skipped model needs no private “keep warm” recurrence: it resumes from the accepted shared state when a transition next needs it. Do not seed from its old raw output or reset to an idle clip on every switch.

### 3. Tighten the endpoint hot paths

- Use the resolved demand consistently for dispatch, output validity and correction. At pure Run, never read old Walk output, perform Walk correction, copy Walk scratch or interpolate policy poses; pure Walk has the symmetric guarantee. None preserves only the existing ownership-required mover/history work.
- Replace Walk-to-Run-output-buffer copying with direct selected-source access where practical. Do not remove that copy until every consumer of `OutputBuffer`, including recovery rotations and hand raw caches, has been converted. Current hand code preserves Run output before that buffer is overwritten for Walk lanes.
- Reuse corrected endpoint output instead of calculating it again for a nominal recovery source. Keep separate candidates only during a real transition when they are actually distinct.
- Keep Walk pin configuration for idle, but deactivate its runtime smoothing/tick-pinning state once its visible contribution reaches zero. Current code already gates several paths with `NeedsWalk()` and resets smoothing; further gains are mainly avoiding repeated inactive map scans/reset calls and retiring active entries. Apply/commit any pending presentation offset exactly once before retirement so a foot does not snap. Preserve optional reach guards and bounds when their active source genuinely uses them.
- Keep Run pinning boost and lower-end recovery boost: `ProphecyWalkPinningLibrary.cpp` contains both Walk-specific and Run-specific code. Library/file names are not deletion criteria.
- Physical profiles, joint damping, hand inertia and IK calibration must read the actual published source weights. Cheap scalar profile selection is not two NN evaluations. Keep the required endpoint profile and geometry; skip interpolation/secondary work where already settled.
- Keep debug readbacks observational. Report both the requested input selection and actual published blend when needed; do not equate `GetLocomotionState().bRun` with checkpoint identity. No debug request should create a second source prediction.

### 4. Remove wasted rows in mixed crowds

This is needed for the strict **per-agent** no-second-checkpoint guarantee. With the existing static batch, selecting endpoints alone is only a partial performance refactor.

Build reusable Run and Walk index lists from **due, enabled, locomotion-owned** agents. Gather the existing shared input row only into the needed model's input. A transitioning agent is in both lists; a settled agent is in exactly one; a fully overridden agent is in neither. Scatter outputs back by stable agent identity and mark which outputs were produced this step. Keep indices distinct from padded tensor rows and validate actor bounds—the earlier attack optimization already exposed how unsafe padded actor access can be.

Re-export compatible dynamic-batch lower models, or select measured fixed-size buckets if the chosen runtime handles those better. Validate actual runtime shape support before choosing; `FPolicyModel::ResizeBatch()` existing in C++ is not proof that today's static lower ONNX can resize. Update contract validation, binding sizes and output storage accordingly. Do not change weights or fake an ONNX shape edit over batch-dependent operations. Reuse gather/scatter storage; avoid allocating or recompiling model shapes every frame. If fixed buckets retain padding, report the padding explicitly and do not claim exact active-row execution.

Idle and moving agents in the same scene legitimately require **two scene-level calls**. The goal is Walk on idle/transition rows and Run on moving/transition rows, without evaluating each settled agent in both models. One model call for an entire mixed crowd would require a different model architecture and is outside this plan.

Do not make upper-model compaction a prerequisite for input-based selection. There is one ordinary locomotion upper checkpoint, not separate Walk and Run upper checkpoints. Eliminate unnecessary recovery-source re-evaluations first; compact ordinary upper rows later only if measurements justify the extra work. Preserve attack, half-attack and defense skips, independent time-dilation due masks and initial attack seeding exceptions.

### 5. Close lifecycle and compatibility gaps

- Startup and first bridge frame must select/seeding-consistently use zero/nonzero requested input. Both models can stay resident to avoid first-idle or first-move load stalls; residency is not recurring inference.
- `ProphecyNNAgentReset::FCheckpoint::bWalk` currently also reconstructs mover mode. Separate saved mover intent from saved checkpoint identity. Reset restores the intended pose/physics baseline and selects idle for the cleared input without deriving movement mode from a model flag. Verify the first post-reset prediction and interpolation endpoints.
- Audit model flags used by physical lower feedback, animation layers and geometry. `bUseWalkPolicy` must not keep two incompatible meanings: old movement mode and new checkpoint source. Preserve common coordinate/rotation conventions and the correct calibration through transitions.
- Preserve full/half switches, lower/upper end events, Armed blocking, recovery boost, inertias and the ghost's own attack networks. Parry still needs the accepted ordinary lower pose.
- Dodge's `prophecy_dodge_walk.onnx` / `prophecy_dodge_run.onnx` are separate defense checkpoints, not the ordinary Walk model. Keep them unless separately retrained/authorized. Since category currently reads `bUseWalkPolicy`, choose and store its intended movement/defense category independently before repurposing that flag. Verify slow movement and idle dodge; do not assume the locomotion fine-tune covers dodge.
- Keep existing idle Walk model variants/seed calibration and startup validation. The current manager selects a July5 Walk variant through Blueprint defaults; the native physical-agent creation path also sets a Walk path. Retain the user's accepted idle variant, selected explicitly at installation.
- Audit loaded Blueprints, class defaults, placed managers, tests and benchmark launch scripts when implementing. Preserve enum values, node connections and unrelated tuning. Use a normal editor build for retained native layout/model-dispatch changes; do not rely on changing live allocations through Live Coding.

## Verification and completion criteria

Use short focused tests and bounded profiling. No full suite by default. Do not stop user-owned Play or save unrelated assets.

| Case, after any requested blend completes | Ordinary lower work per eligible due agent |
| --- | --- |
| Zero input, either `bRun` value | Walk once; Run zero; one source correction |
| Nonzero input, either `bRun` value, any positive movement magnitude | Run once; Walk zero; one source correction |
| Input release/start or reversal within a blend | Both only while weight is strictly between endpoints; exact completion retires unused work |
| Settled endpoint with old recovery/foot-rotation/hand-source settings still serialized | Same endpoint guarantee; no hidden alternate upper pass |
| Established full attack without drag / after last drag-foot release | Neither ordinary lower model for this agent; preserve required special networks |
| Half attack or pending loco drag | One ordinary lower source at endpoints, both only for a real general transition; established attack upper remains skipped |
| Parry / dodge | Parry uses ordinary lower rule; dodge retains its separate defense behavior and skips ordinary lower as today |
| Mixed idle/moving crowd | Both scene-level model calls may run; each endpoint agent is submitted only to its required source |

Focused checks:

1. Extend selector/blend tests for input zero/nonzero, tiny sanitized input, slow/backward/diagonal motion, turning-only, blocked movement, speed-scale zero, residual velocity and irrelevant old thresholds. Test reversal, zero duration, pause and 30/60/120 FPS with the 60-tick duration contract.
2. Check ordinary and regional source demand together, including hand/foot overrides, full/half transitions, one-foot drag, Freeze Blend 0/1, final handoff, reset/retrigger and disabled inference. Ensure no stale or uncomputed output is read.
3. Exercise mixed crowds and different per-agent time dilations. Assert gather/scatter mapping, exact input/output sizes, no work for non-due/disabled agents and no actor lookup on padding. Compare compact versus full-batch outputs for identical inputs and checkpoint weights within an established numerical tolerance.
4. Visually verify starts/stops, slow turns, contacts, knees/pelvis, attack exits and zero-input external root motion. The new fine-tune intentionally changes moving poses; compare dispatch optimizations against the same new-checkpoint reference, not against the old Walk animation as a required identical result.
5. Extend the existing bounded `Prophecy.AttackPerf.Capture` instrumentation to label **Run versus Walk identity**, request reasons, eligible rows, submitted rows/padding, correction counts and alternate upper runs. It currently groups network calls by input width/batch/backend, which cannot distinguish both 152-input lower checkpoints. Disabled instrumentation must read no clocks or allocate.
6. Profile homogeneous Run, homogeneous idle Walk, start/stop transitions, a mixed crowd and attack recovery. Report actual calls/rows and frame-time distributions; distinguish policy-step cost from whole-frame FPS and model memory. Do not promise a gain from counts alone.

Done means the chosen new Run model is installed with its matching contract, the requested selector works across every input/lifecycle path, legacy source consumers cannot defeat endpoint gating, and measured dispatch shows no unused-model work for settled agents. If batching is postponed, report the refactor as **endpoint selection complete, mixed-crowd row optimization pending**, not as fulfilling the strict per-agent guarantee.

## Audit limitations and future handoff

This was a source/dependency audit, not a runtime benchmark or a model-quality evaluation. An attempted read-only live Blueprint audit could not discover an Unreal remote-execution node; the existing `Saved/Diagnostics/SwordThigh/BlueprintGraph.txt` is dated September 27 and is not treated as current wiring evidence. Re-audit live assets when implementation is requested. No editor launch, compile, test suite, asset save, checkpoint install or runtime change was performed for this plan.

Related contracts: [ordinary blending](LocomotionPolicyBlending.md), [regional recovery](AttackRecoveryBlend.md), [hand recovery](HandRecovery.md), [loco drag](AttackFootLocomotion.md), [regional special ownership](RegionalSpecialRecovery.md), [attack performance](AttackPerformance.md).
