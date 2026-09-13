# Wide wrist limits and forearm motion — 2026-09-12

**Root-cause interpretation superseded:** the matched Boolean test and validated isolated replay in [JoltWristLimitActivationDiagnosis.md](JoltWristLimitActivationDiagnosis.md) establish that altered solve order and cleared translation warm starts initiate the pose difference. Later angular boundary contact recorded below is real, but was incorrectly treated as the initiating cause. Retain this document as historical measurements, not the final diagnosis.

Diagnosis only, at the user's request. No gameplay fix, Blueprint rewiring, joint tuning, target clamping, or solver change was applied.

The right wrist's native twist limit is reached in the current testNN setup. Its reaction acts on the hand and forearm, and the physical-feedback loop subsequently changes the requested pose. The measurements do not support a wrist angular-limit impulse acting while its native twist is inside the configured range, or the hand node mistakenly editing the elbow joint.

## Native evidence

Temporary private C++ instrumentation read the actual Jolt SixDOF constraint rotation, connector frames, rotation limits, accumulated angular/anchor impulses, and the player-only speculative swing impulse immediately before and after each synchronous physics update. The actual current Blueprint was run for 30 simulation seconds. This is solver data, not visual estimation or Euler angles reconstructed using an assumed bone axis.

For player `BP_ProphecyManualPoseAgent_C_1`, the wrist is `hand_r` connected to `lowerarm_r`. Both elbow joints remained angularly Free. Neither elbow generated a native angular-limit impulse. The left wrist generated no angular-limit impulse. The added speculative swing correction generated exactly zero impulse throughout this capture, on both wrists.

The right wrist first generated a resisting **velocity** twist impulse at 1.633333 seconds:

| Simulation time | Pre-step native wrist twist | Post-step native wrist twist | Twist impulse (N·m·s) |
| --- | ---: | ---: | ---: |
| 1.600000 | -152.593° | -164.027° | 0 |
| 1.616667 | -164.027° | -173.737° | 0 |
| 1.633333 | -173.737° | -172.927° | -0.013784 |
| 1.650000 | -172.927° | -172.369° | -0.021191 |
| 1.666667 | -172.369° | -172.024° | -0.028234 |

The configured native bounds are ±170°. Across the complete capture there were **zero samples with a nonzero native twist velocity impulse and pre-step twist inside ±169.99°**. Native swing impulses were zero too. Jolt's position solver can also correct an excursion after velocity integration crosses the boundary; its incremental corrections are not represented by the retained velocity impulse. The physical difference begins on the crossing step at 1.616667, before the first resisting velocity impulse on the next step.

The startup pose briefly lies outside the boundary when the Blueprint first applies 170° at 0.083333 seconds, with inward motion and zero resisting velocity impulse. Thus 1.633333 is the first resisting velocity impulse, not the first out-of-range orientation in the entire startup sequence.

## Why a steady-looking hand reaches a wrist limit

The constraint limits the hand **relative to the forearm, using the PHAT connector frames**. It does not measure the hand's error from its animated target or its rotation in world space.

Between 1.3 and 1.6 seconds, the actual right forearm changes world orientation by 65.27°, while the hand changes by only 5.42°. Their requested orientations change by 65.31° and 5.72° respectively. The hand can therefore remain close to its world target while substantial relative wrist twist accumulates. At 1.616667 the requested relative twist is already -176.60°; the target crosses the excluded part of the ±170° range.

The measured native parent connector quaternion (x,y,z,w) is `(0.705090523,-0.0826141685,0.034603674,0.703437746)` and the child connector is identity. These were read directly from the live constraint. Their center is the PHAT frame, not the current animation pose. Earlier calculations using historical rig-audit frames were insufficient evidence by themselves; the direct native trace confirms the frames and boundary crossing here.

A wrist stop constrains two simulated bodies. Its torque acts on both endpoints, so an angularly Free elbow does not protect the forearm from the wrist's reaction. The node did not change the elbow's limits.

## Controlled comparisons and feedback

Four initial 30-second runs separated the axes, with PIE-only controls applied after initialization:

| Wrist axes | Right forearm maximum target error after t=5 s |
| --- | ---: |
| Swing1/Swing2/Twist Limited170 | 102.80° |
| All Free | 1.84° |
| Swing Free, Twist Limited170 | 102.80° |
| Swing Limited170, Twist Free | 1.84° |

The twist-only case registers the stock native SixDOF, with no speculative swing wrapper. It reproduces the fault. The swing-only case retains the eligible swing wrapper and behaves like Free. Angular-speed maxima alone did not distinguish these cases and were explicitly discarded as a diagnosis.

A further startup control releases the wrists at t=0.216667, before the walking boundary crossing. At t=1.6 the forearm orientations differ by only 0.015° and their targets differ by 0.015°. At t=1.633333 the physical forearms differ by 7.234°, while their targets still differ by only 0.0012°. This establishes that the physical constraint reaction precedes the large divergence in later targets. At t=1.8 the forearm targets differ by 71.01°.

The current hand feedback settings are 0 cm linear tolerance and 10° angular tolerance. Upper-arm tolerances are 3 cm and 5°. `GetPhysicalFeedbackTolerance(lowerarm_r)` returns no supported entry; this must **not** be interpreted as evidence of a direct zero-tolerance forearm feedback channel. Upper-body feedback consumes the supported core and arm endpoint/start state, and arm reconstruction produces the forearm pose.

For a diagnostic control, all physical-feedback tolerances were set to 1,000,000 cm / 360° in fresh PIE copies, leaving magnetisation and the normal target-generation code intact. Paired Limited170 and Free runs check whether the physical-feedback loop is necessary for the observed difference. Results are recorded in `Saved/Diagnostics/WideWrist/openloop_analysis.json`.

Both feedback-disabled runs completed 30 seconds. After the initial second, their requested orientations are identical. The maximum difference between the physical right forearms is 0.000134°, and between the hands 0.000022°. Forearm target error remains below 1.969° in both cases. Wrist twist reaches only 93.284° in magnitude, safely inside 170°. Thus, with feedback suppressed, this target trajectory does not hit the stop and the large limited/free discrepancy disappears. This is a diagnostic result, not a recommendation to disable feedback in gameplay.

This establishes the initiating mechanism in this setup. It does not establish that every later full-circle motion is caused exclusively by feedback, or determine a preferred gameplay change. No parent-dominance policy, Free twist substitution, damping, or feedback retuning was installed.

## Evidence and reproduction

`Saved/Diagnostics/WideWrist/` contains:

- `native_current.json`, `NativeCurrentTrace.log`, `native_current_parsed.json`: 30-second current-setup capture and actual native pre/post solver data.
- `native_free.json`, `NativeFreeTrace.log`, `native_free_parsed.json`: successful startup Free control. An earlier attempt ran before player rig initialization, failed to change its limits, and was excluded/replaced. Successful native limits switch to Free at t=0.233333.
- `current.json`, `free.json`, `twist_only.json`, `swing_only.json`: the four 30-second axis-isolation runs.
- `openloop_current.json`, `openloop_free.json`, `openloop_analysis.json`: paired feedback-disabled controls.
- `metadata.json`: current runtime settings from a separate unmodified PIE run.
- `Capture.py`, `StartNative.py`, `AnalyzeNative.py`, `CompareStartup.py`, `OpenLoop.py`, `AnalyzeOpenLoop.py`: diagnostic capture/analysis scripts. `StartNative.py` requires the temporary native instrumentation, preserved as a snippet in `NativeTraceInstrumentation.txt`.

All experimental settings were restricted to transient PIE actors. User Blueprint edits were preserved. Temporary native trace code was removed after capture; it is not part of the gameplay integration.
