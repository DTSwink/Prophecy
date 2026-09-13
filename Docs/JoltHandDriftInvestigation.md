# Hand drift investigation, 2026-09-11

Follow-up: the later 3 cm / 5 degree NN-feedback setup exposed the remaining inertia-conditioning gap. Skeletal rig admission now applies the authored conditioning policy; see [JoltFeedbackHandDrift.md](JoltFeedbackHandDrift.md). The measurements and accepted velocity correction below describe the earlier checkpoint.

The user's unsaved testNN and BP_ProphecyManualPoseAgent setup was retained in the open editor. Every comparison used fresh PIE, switched the selected backend at 2 simulation seconds, then recorded 25 seconds. Analysis below excludes time before 5 seconds. No assets were saved or retuned during the comparison. The user subsequently reported seeing a perfect result, explicitly identified the corrected Jolt runs as the accepted behavior, and requested installing it. They then saved their current edits and authorized continuation of the editor restart.

The strongly driven actor is BP_ProphecyManualPoseAgent_C_1. Actor C_0 intentionally has 0.02 upper-body magnetisation and is not a full-strength tracking acceptance case.

| Trial | Left hand mean/max angular error | Right hand mean/max angular error |
|---|---:|---:|
| Original Jolt | 27.79 / 88.24 degrees | 10.15 / 28.65 degrees |
| Chaos | 1.79 / 4.64 | 1.84 / 4.77 |
| Jolt self-collision disabled | Same as original | Same as original |
| Jolt angular limits disabled | Same as original | Same as original |
| Jolt target converted to COM endpoint | 5.04 / 16.38 | 4.03 / 10.57 |
| Jolt origin velocity converted using angular velocity cross COM offset | 4.81 / 15.26 | 3.97 / 10.40 |
| Chaos inertia conditioning disabled | 4.40 / 12.76 | 3.91 / 10.29 |

The two corrected Jolt trials ran before the final Chaos-without-conditioning trial. The original Jolt trajectory and both collision/limit exclusion trials match numerically. Existing servo stage samples show most of the hand's corrective angular velocity being cancelled during the native solve. The controller uses body-origin positional error but assigns COM velocity without the rotational point-velocity conversion. Correcting that mismatch greatly reduces the deviation. The residual error is comparable to Chaos with inertia conditioning disabled; this is evidence that missing inertia conditioning also matters, not proof of complete solver equivalence.

Installed correction: the origin-velocity conversion from the `jolt_twist` trial is now unconditional in the velocity servo. After computing the requested angular velocity, it adds `LinearStrength * (AngularVelocity cross WorldCOMOffset)` to COM velocity. This preserves the existing strength blend and disabled-linear-drive behavior, includes retained spin when angular drive is disabled, and uses the captured native shape COM. The old implementation omitted that rigid-body point-velocity term, making joint corrections oppose hand rotation. No special hand rule, extra substeps, pose smoothing, joint tuning or inertia changes were installed.

The diagnostic COMTarget switch, alternative endpoint trial and HandTrace logging have been removed from production source. The prior Chaos inertia-conditioning CVar was restored. The normal Editor build succeeded in `Saved/Diagnostics/HandDrift/Build-Final.log`. The offset-COM test now checks actual origin point velocity, and an additional test covers partial strengths and disabled channels. All 22 Servo, PhysicsCommands, RigWorld and MultiRig automation tests passed after reopening the normal build, with zero errors/warnings (`result.json`, `Automation.log`). Unreal is open on testNN, PIE stopped, with no dirty packages. Residual numerical error is documented above; user visual acceptance is not a claim of zero target error or identical Chaos trajectories. Inertia conditioning remains a separate, unimplemented feature.

Evidence: Saved/Diagnostics/HandDrift contains all per-frame JSON captures, Comparison.txt, native stage traces in Editor-Trials.log, and the exact VelocityServo-Trials.cpp. The pinned Jolt Body.cpp MoveKinematic implementation explicitly converts its desired body origin/rotation into a desired COM position. Jolt's public [body API](https://jrouwe.github.io/JoltPhysics/class_body.html) and [architecture](https://jrouwe.github.io/JoltPhysics/) provide background. UE5.7 Chaos/MassConditioning.cpp and PBDRigidsEvolutionGBF.cpp implement the inertia conditioning used in the comparison.
