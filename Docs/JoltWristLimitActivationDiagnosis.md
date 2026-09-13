# Wrist-limit activation changes forearm motion — matched Boolean diagnosis

2026-09-12. Activation-continuity repair installed; the full forearm-motion issue remains reproduced. See the follow-up below before treating the original diagnosis as a complete explanation.

**The initiating disturbance is a change to the existing joint solve when the angular limits are enabled. The angular stop is not responsible for the first differing step.** The integration changes constraint registration order, and native Jolt clears the wrist's translation warm-start impulses when its angular modes change. Those changes alter the forces that keep the hand attached to the forearm, even when the angular bounds produce no correction. The resulting pose difference enters the physical-feedback loop and later targets diverge.

This supersedes the earlier root-cause interpretation in `JoltWideWristLimitDiagnosis.md`. Its later boundary-contact measurements were real, but they did not establish what initiated the movement. In particular, changing an already-running limited rig to Free after startup was not a clean comparison with never executing the user's limit nodes.

## Matched user graph

The user added `bool codex` to gate exactly the two wrist-limit calls. A read-only graph dump confirms the chain:

`tick debugging` → `is tick(i=5, modulo=-1)` equality → existing setup chain → `bool codex` → hand_r Limited170 on all axes → hand_l Limited170 on all axes → disconnected end.

The other setup calls are before the Boolean gate. The lowerarm-limit nodes are disconnected. No graph wiring or node inputs were edited for these tests.

The Boolean is not editor-instance-editable, so Python's `set_editor_property` rejected the initial write. A temporary console command writes only the reflected Boolean on the named PIE actor and verifies its value. No direct limit-setter, magnetisation, feedback, mode, or collision calls are made by the matched capture script.

Two fresh 35-second PIE captures compare False throughout against True set before the fifth debug tick. They are identical before the limit application. A separate attempt toggling the Boolean at 10 seconds left the limits Free and produced bit-identical motion throughout, because the one-time application branch had already run. The user clarified that the branch sets persistent limits for the rest of the simulation; the correct comparison therefore sets the Boolean before that branch.

The first physical difference is at t=0.083333, the exact application step. Animation targets are still identical:

| Bone | Physical orientation difference, True versus False |
| --- | ---: |
| lowerarm_r | 0.239336° |
| hand_r | 0.290051° |
| lowerarm_l | 0.045651° |
| hand_l | 0.027377° |

The right forearm difference exceeds 2.51° at t=0.116667; target divergence is already beginning by then. The left wrist produces no native angular-limit or speculative swing impulse throughout the full capture, yet its pose also diverges.

## Isolated replay establishes causality

A temporary diagnostic copies the native world immediately before the first differing step. It copies bodies with the same IDs, shapes and settings, constraints, full native state including contacts and cached impulses, the velocity servo, collision policies and simulation-shape filter. The original world is not advanced or modified by the replay. Six variants advance only the isolated copies by one step.

Validation matters: the final unmodified replica matches the live orientations within 0.000012°. Running the diagnostic leaves the live result bit-identical to the earlier Boolean-True capture. An initial replica omitted the simulation-shape filter and did not match the live world; that version was rejected and is not used as evidence.

| Replay variant | Right forearm difference from actual Boolean-False result |
| --- | ---: |
| 0: current Limited170 implementation | 0.239333° |
| 1: angular bounds removed, same registration order and cleared caches | 0.239333° |
| 2: Limited170, original registration order restored | 0.096394° |
| 3: Limited170, original cached impulses restored | 0.230507° |
| 4: Limited170, original order **and** cached impulses restored | **0.0000061°** |
| 5: Free, original order and cached impulses restored | **0.0000061°** |

Variants 0 and 1 are identical on all four measured hand/forearm orientations. Variants 4 and 5 are also identical. Keeping the 170° limits while preserving both the existing order and caches reproduces False to numerical precision on the first divergent step. Changing the angular bounds alone does not change that step's result.

This distinguishes the initiating disturbance from later genuine limit contact. The native right-wrist twist is already 171.586° just before the first application step, but that angle alone did not prove which mechanism altered the output. The controlled replay does.

## Code responsible

- `SixDOFConstraint::SetRotationLimits` calls `UpdateFixedFreeAxis`. When the free/fixed mask changes, Jolt deactivates **all** its constraint parts, including `mPointConstraintPart`. That clears the translation/anchor warm start even though the anchors and translation limits did not change.
- `RefreshSpeculativeJoint` removes the current constraint and adds its player-specific wrapper. Jolt's constraint manager fills the removed slot with its last constraint and appends the replacement. Its solver sorts equal-priority constraints by this index, so the existing solve order changes.
- An iterative joint solver depends on its starting impulses and solve order. A wrist's translation constraints apply forces at offsets from each body's center of mass, so changed anchor forces also change forearm rotation. No angular-limit impulse is required for that effect.

The appropriate repair must preserve the existing solve order and unaffected translation warm starts across angular-mode changes. It must still discard genuinely invalid angular warm starts and enforce real angular limits. Loosening the limits, disabling physical feedback, adding damping, or clamping the resulting pose would not address the initiating state change.

This is a one-step causal diagnosis plus full-length reproduction, not a validated long-run repair. Once implemented, the repair needs the same Boolean comparison and continued observation of the later feedback trajectory. No such repair is claimed here.

## Evidence

All files are under `Saved/Diagnostics/WideWrist/`:

- `BoolCapture.py`, `bool_false.json`, `bool_early.json`, `bool_early_analysis.json`: matched 35-second comparison; only the user's Boolean changes in live actors.
- `CurrentBlueprintGraph.txt`: read-only graph wiring and literal values.
- `BoolEarlyNative.log`: actual native pre/post constraint data.
- `bool_replay.json`, `FirstStepReplay.log`, `first_step_replay_analysis.json`: validated isolated replay and live-result check. Variants are numbered as in the table above.
- `ValidatedReplayInstrumentation.cpp.txt`: exact temporary diagnostic implementation, retained for audit; removed from production source afterward.
- `WorldSubsystemBeforeBool.cpp.txt`, `SpeculativeBeforeBool.h.txt`: source before temporary instrumentation, restored after capture.

The native debug commands and replay instrumentation were removed after diagnosis. No Blueprint assets were saved or edited by the diagnostic scripts. Runtime Boolean writes existed only on transient PIE actors.

## Repair and remaining motion (2026-09-12, follow-up)

Implemented the two identified continuity corrections in the maintained Jolt patch: SixDOF invalidates only the affected translation/angular block; PhysicsSystem/ConstraintManager can replace a constraint in its existing registration slot. RefreshSpeculativeJoint uses this constant-time replacement outside Update. No ordinary stepping, gains, feedback, target clamp, angular ranges, or player-only wrapper eligibility changed. Development and Shipping SSE2 dependencies rebuilt; Development Editor normal build succeeded. All six Joints tests, including new RuntimeLimitContinuity, passed without warnings/errors. All six RigWorld tests passed in the editor, including LiveAngularLimitsAtomic and player-wrapper transitions.

**This fixes the original application-step disturbance, but does not fix the user's full visible symptom.** The repaired 35-second Boolean-on run still reaches 97.14 degrees of right-forearm target error (after 10 seconds), versus 1.84 in the Boolean-off reference. User independently confirmed the remaining rotation. Do not report the task complete.

The repaired run is bit-identical to the matched old Boolean-off reference through t=0.083333, including the exact limit-application step. The next step at t=0.100000 differs by 0.043987 degrees on the right forearm and 0.037487 on the hand, while the targets are still identical. The right wrist begins that step at 171.406 degrees of native relative twist, outside its 170-degree bound. The full read-only trace shows zero speculative swing impulses; right wrist swing remains below 84.56 degrees. Genuine twist velocity reactions appear at t=1.633333 after the wrist reaches -173.735 degrees. No in-range twist velocity impulse was recorded over the 35 seconds. Position correction is not represented by those accumulated velocity-impulse fields.

A second isolated replay at t=0.100000 establishes the remaining causal mechanism. Its unchanged replica matches live within 0.000012 degrees; enabling replay leaves the real run bit-identical to the original repaired run. Variant 0 retains Limited170; variant 1 removes wrist angular bounds; variant 2 removes only wrist twist bounds while retaining Limited170 swing. Neither changes order, bodies, targets or attachment caches. Variants 1 and 2 give identical results and reproduce the Boolean-off reference within 0.000012 degrees. Thus the remaining first disturbance is caused by actual wrist twist enforcement, independently of the repaired activation bookkeeping. Both endpoints can rotate under a wrist's angular reaction; later physical feedback changes the NN targets. Preventing that reaction on the parent, weakening the limit, or changing feedback/target policy would be a further behavior decision, not another fix for the proven registration/cache defect.

Evidence: `Saved/Diagnostics/WideWrist/bool_fixed.json`, `bool_fixedtrace.json` (35 seconds), `bool_false_beforefix.json` (matched reference), `bool_fixedtrace_analysis.json`, `FixedNativeTrace.log`, `fixed_native_parsed.json`, `SecondStepReplay.log`, `second_step_replay_analysis.json`, `SecondStepInstrumentation.cpp.txt`. The first post-editor-restart False run had different startup physical state and was excluded from the matched comparison; a later False capture was interrupted while the user tested and is also excluded. The repaired True runs match each other exactly and match the older reference before the relevant transition.

Temporary replay/trace code was removed and Live Coding succeeded with no object reinstancing. The Boolean helper source was removed; its old development-module registration can remain resident until editor restart, but is not part of the production source or stepping. The user continued testing/changing the Boolean (latest inspection False); BP/map edits remain unsaved. No further restart or asset save was performed. Blood work remains paused.
