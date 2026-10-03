# Upper-body exit inertia

Current contract **October 2, 2026**; diagnosis below is from October 1. Earlier implementations and their measurements are preserved in the [historical snapshot](Journal/UpperBodyInertia-history-through-2026-10-01.md). Wrist-position springs, exit-arm IK, variable forearm length and old scene settings in that archive are superseded.

## Latest diagnosis

**Yes: the NN requests the remaining bent arm at attack exit.** The network does not directly output lowerarm rotation. Its upperarm rotation and hand prediction are decoded into the forearm pose. The old inertia implementation amplified this bend by independently springing the wrist position and then solving the elbow. The connected angular implementation below reduces that extra fold; it does **not** fully eliminate the visible straight-to-bent transition reported by the user in Kinematic mode.

Current first slashLD runs ticks 148–183, holding final attack frame 18 at 181/182. At the first exit prediction, the raw NN hand delta is **(21.901, -0.133, -13.892) cm**, approximately 25.94 cm, before runtime inertia. Upperarm rotation delta is **22.632 degrees**, hand rotation delta **31.355 degrees**. This is direct evidence of a large incoming pose change. It does not establish a bad history, codec or model parity bug. Upper-checkpoint trace values during attack are stale because that checkpoint is skipped; do not treat them as executed predictions.

Scene settings: inertia Enabled, Response **0.07**, Hold **0**, Blend **0.5**, Momentum **1**, Spine Local, **Alpha 0.5**. The existing Alpha meaning mixes in 50% of the incoming normal pose immediately; the later fade removes the remaining inertia. No entry ramp or full outgoing-pose preservation at partial Alpha has been implemented. The user accepted the NN attribution and requested journal cleanup, not a redesign of Alpha.

Right neutral return remains enabled; left optional return for slashLD is unselected. Wrist recoil is disabled. Upper-arm cone is enabled (60 degrees, recoil 150, damping 20, hold 1.5, blend 0.5), with no left correction logged. These are observed scene settings, not defaults. No Blueprint, model, tuning or collision changes were made in this investigation.

## Current implementation

`Set Attack Upper Body Inertia` controls ten FK core rotations and both connected arm chains. **Hand Inertia Space** selects Root Local (default: NN locomotion root position/heading) or Spine Local (`spine_05`, including its tilt after core inertia). Outgoing samples are expressed in their own reference frames before measuring angular velocities, so reference movement is not counted twice. Configure before or at special end; configuration changes during a return cancel it, except Alpha-only changes preserve its clock and spring motion.

Core and arms now have independent response and blend controls:

| Pin | Scope / default |
| --- | --- |
| Core Response Time Seconds | Ten FK core joints; existing response pin, default 0.25 |
| Core Blend To Normal Duration Seconds | Core ownership fade; existing blend pin, default 0.5 |
| Arms Response Time Seconds | Both arms together; -1 inherits core response |
| Arms Blend To Normal Duration Seconds | Both arms together; -1 inherits core blend |

Hold Duration remains shared, as do Momentum Scale and Alpha. Existing core pin identities, values and wiring are retained; new arm pins default to -1 so existing nodes retain their timing. Each arm override can inherit independently. Response 0, or Hold + Blend 0, bypasses only that region. Positive Hold with Blend 0 remains valid. Each region retires its own spring state at its own Hold + Blend endpoint; the shared 60-tick clock ends when the last active region finishes. Finished core processing stops while longer arm inertia continues, and vice versa. Both arms always use the same timing values. These controls belong to attack-exit inertia, separate from Set Attack Start Hand Inertia.

`ApplyArms` in `Source/GameAnimationSample3/Private/ProphecyUpperBodyInertiaLibrary.cpp`:

1. Read the incoming normal arm, normalize wrist attachment to anatomical forearm length, and include the current left-wrist angular constraint in the destination.
2. Advance the existing upperarm, forearm and hand angular springs in the selected reference frame.
3. Form the completed inertial upperarm world rotation and elbow/wrist joint-local rotations.
4. Fade those rotations toward the normal arm, then reconstruct elbow/hand positions using the attached joint hierarchy.

There is **no separate wrist-position spring, exit-arm IK or reach projection** in this path. Hand positional momentum follows the rotating connected arm. The shoulder follows the incoming torso. Core inertia is unchanged. Ordinary upper inference supplies the destination; arm inertia runs after the existing recovery/tempering/neutral-return stages. Accepted transforms feed recurrence and publication through the existing caller. World-space publication caches are not the inertia reference space.

Rotation fading retains a continuous unwrapped rotation-vector offset instead of independently picking the shortest arc each update. This prevents the previously measured branch flip at 180 degrees. The fade reaches the normal destination exactly, subject to the same fixed attachment and wrist constraint used to prepare that destination; later modifiers can still affect the final published pose.

**Alpha** defaults to 1 and is clamped to 0–1. Effective influence is `Alpha * (1 - smoothstep(blend progress))`. It is a pose influence, not an entry blend or a speed cap. Alpha 0 cancels active inertia and bypasses future inertia work. Momentum scales outgoing angular velocities; Momentum 0 still permits spring/hold behavior. Response controls spring attraction/damping: small values can return rapidly even during Hold. Hold keeps ownership while the springs evolve; Blend fades ownership to the moving normal destination. All authored durations follow [60 unpaused game ticks per second](BlendTickTiming.md).

Both forearms remain at their fixed anatomical lengths; latest measured left/right lengths are **22.349146 / 22.349243 cm**. Alpha cannot stretch or shorten them. See [fixed attachments](FixedArmAttachments.md) for NN/physical scope and physical solver limitations.

Sparse sidecars retain Live Coding compatibility. Disabled, canceled and retired paths skip arm spring/pose work behind the existing cheap guard; no extra inference. Legacy position/velocity/pole fields remain in the retained arm layout and some initialization still seeds them, but `ApplyArms` no longer runs a position spring. Do not claim a complete dead-field cleanup. Editor-only `Prophecy.UpperInertia.DebugDisable` defaults to 0 and exists for a genuine no-inertia reference; DebugResponse/DebugNoTwist also remain diagnostic-only overrides.

## Verification and limits

Independent core/arm controls: Live Coding loaded **October 1, 22:17:21 UTC** (October 2 local). All four focused `Prophecy.NN.UpperBodyInertia` tests passed **22:18:02 UTC**: `CoreArmSettings`, `HandVelocityAndReach`, `ReferenceFrames`, and `SpringAndRetirement`. New coverage checks separate response, shared left/right values, -1 inheritance, both retirement orders at 30/60/120 FPS, per-region bypass, reset/removal and Alpha-only clock preservation. Existing coverage includes reference movement, angular motion, joint influence weights, exact fade destination and fixed lengths. The existing Blueprint node was reconstructed and compiled status 3, with old values/wiring preserved and both new pins defaulting to -1 (`Saved/Diagnostics/UpperInertiaControlsPins.txt`). Live Coding library defaults were repaired (48 archived defaults); initial missing-pin compile errors cleared after reconstruction. No explicit asset save, gameplay replay, full suite or normal-DLL rebuild for this addition.

The connected-chain implementation used for the following October 1 measurements loaded **19:41:57 UTC**, with its three focused tests passing **19:42:35 UTC**. The new timing controls do not constitute a new visual verification of that diagnosis.

Matched Kinematic 320-tick replay preserves all target positions/rotations before tick 183 bit-for-bit. Elbow bend is the angle between shoulder-to-elbow and elbow-to-hand; zero means straight. It is not the full forearm quaternion step.

| Tick | Superseded completed-IK fade | Current connected angular chain |
| --- | ---: | ---: |
| 181 | 32.620 degrees | 32.620 degrees |
| 183 | 52.445 degrees | 42.578 degrees |
| 185 | 68.080 degrees | 47.110 degrees |
| 187 | 74.650 degrees | 50.310 degrees |
| 193 | 75.050 degrees | 56.890 degrees |

First bend increment falls **19.825 to 9.958 degrees**, next **15.635 to 4.532 degrees**. Latest `left_exit_current` recapture confirms the remaining bend, including presented bend 32.62 at 182 and 42.58 at 184. This is reduction, not visual acceptance of a fully seamless exit. Forearm orientation steps at fade ticks 209/211/213/215 are **11.88 / 5.92 / 3.03 / 5.15 degrees**; no isolated fade-end spike was measured there.

A separate earlier Physical-mode probe isolated extra self-contact response: disabling only left lowerarm self-collisions at tick 180 reduced physical peak forearm step **49.157 to 16.059 degrees**, with the target unchanged. That does not explain the user's Kinematic bend. No production collision change was made; do not resume that separate probe automatically.

Both final connected captures ran **Kinematic**, including the misleadingly named `left_exit_connected_sim`. Owned sessions ended; audits, trace and debug overrides were restored to 0. No claim of physical verification for the latest connected implementation.

## Reproduction and history

- Graph snapshot: `Saved/Diagnostics/SwordThigh/BlueprintGraph.txt` (inertia EventGraph node 251; graph dumps may be UTF-16LE).
- Capture/analysis: `Saved/Diagnostics/LeftExit/capture.py`, `analyze_connected.py`, `connected_verification.json`. Read capture variants before reuse; some intentionally alter temporary PIE settings. Do not rerun during user-owned Play.
- Captures under `Saved/Diagnostics/RunHandThigh/`: `left_exit_kin_trace`, `left_exit_connected_kin`, `left_exit_connected_sim`, latest `left_exit_current`. Raw first-exit proof: `left_exit_kin_trace_nn.jsonl`, time 3.049999818, `upper_delta[60:63] * 100` for the hand translation. Matching connected trace retains raw proof.
- Before the investigation: `Saved/Diagnostics/LeftExit/UpperInertiaBefore.cpp`. Before connected-chain simplification: `UpperInertiaBeforeConnected.cpp` in the same directory. Never restore the whole source from Git: unrelated accepted changes coexist.
- Superseded trial loaded 19:26:27 UTC moved fading after a full wrist/IK solve. It reduced some orientation jumps but still added elbow folding. Evidence `final_blend_verification.json` describes that trial, not current code.
- Initial diagnostic `summary.json` and `left_exit_{base,no_twist,slow_response,no_inertia}` distinguish original behavior and temporary ablations. No-twist did not remove the bend; slower Response only partly reduced it. A no-inertia reference still bent abruptly.
- Earlier continuous-offset fix loaded 14:45:31 UTC remains active. Its right-wrist step at tick 201 fell 131.414 to 30.974 degrees in that earlier setup. Full measurements and September 29 reference/Alpha history remain in the [archive](Journal/UpperBodyInertia-history-through-2026-10-01.md).
