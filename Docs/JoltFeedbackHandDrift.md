# Feedback hand drift and imported inertia conditioning

The current testNN Blueprint sets physical feedback tolerances below both upper arms to 3 cm / 5 degrees. With the prior Jolt build, the strongly driven character's hands periodically rotated upward as physical deviations were fed into the recurrent NN state. This was reproduced over 25 seconds after a fresh Play session; switching the same setup to Chaos suppressed it.

The feedback encoding, tolerance and reference-frame paths were inspected. Jolt samples its completed world-space physical pose and converts it to the inherited AgentMesh frame, the same reference used by the Chaos path. Both then use the same feedback tolerance code. The useful causal difference was the effective rotational inertia: all bodies in this rig opt into UE inertia conditioning, but Jolt preparation previously retained only their raw inertia. Native joint corrections rotated the small hand bodies much more, exceeding the feedback tolerance and changing subsequent NN output.

Matched trials on BP_ProphecyManualPoseAgent_C_1 (full strength; samples after 5 seconds):

| Backend / condition | Left hand mean / max angular target error | Right hand mean / max |
|---|---:|---:|
| Prior Jolt, feedback enabled | 13.70 / 25.71 degrees | 10.19 / 28.32 degrees |
| Chaos, same feedback settings | 1.64 / 3.84 | 2.07 / 5.60 |
| Chaos with inertia conditioning disabled | 22.85 / 54.55 | 14.14 / 49.79 |
| Jolt with imported inertia conditioning | 1.61 / 4.39 | 2.04 / 5.25 |
| Final normal build, 60-second capture | 1.59 / 4.39 | 2.06 / 5.25 |

Disabling conditioning in Chaos reproduces the feedback instability. Restoring the authored conditioning policy in Jolt brings the tracking and hand angular speeds into the stable Chaos range. No feedback tolerance, NN recurrence, magnetisation, PHAT limit, collision or timestep setting was changed. The other actor deliberately has 0.02 upper-body drives; its large pose errors are not a full-strength acceptance case.

Implementation is in ProphecyJoltRig.cpp. During rig preparation it reads the current engine conditioning policy once and respects each captured body's bInertiaConditioning flag. It computes collision-bound extents and attached joint arms in the principal mass frame, calls the engine's CalculateInertiaConditioning helper in centimetre units, and applies the resulting principal inertia to the prepared Jolt mass properties. It preserves the COM, principal-frame orientation and mass. Free linear joints are excluded according to engine policy. Invalid policy or unrepresentable native inertia rejects preparation before replacing an existing prepared rig. No runtime polling or per-step conditioning was added; diagnostic switches/logging are removed.

This applies to admitted skeletal rigs. Settings are sampled when enabling/rebinding Jolt; changing the conditioning policy or adding unrelated external grips after admission does not automatically recompute it. Standalone rigid-body conditioning and dynamic recomputation are outside this fix. Jolt uses the resulting inertia for its native body's angular dynamics, including physical torque/impulse response; UE's query-body inertia getters continue to report raw captured properties. This is an effective native-body approximation of the UE conditioning policy, not an identical internal Chaos solver implementation.

Source basis: Epic documents that [inertia conditioning stabilizes small or thin bodies and depends on attached joints](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/PhysicsEngine/FBodyInstance/bInertiaConditioning?application_version=5.5). The installed UE5.7 MassConditioning.cpp and PBDRigidsEvolutionGBF.cpp provide the exact calculation, thresholds and defaults used here. Raw BodyInstance inertia does not include Chaos's conditioned solver inertia.

Validation: all 21 selected tests passed with zero errors/warnings in the fresh normal build. They cover analytical physical impulse response with conditioning on/off, geometry-only/free-joint and attached-arm conditioning, shifted COM, principal-frame rotation, rejected policy atomicity, velocity-servo behavior, existing force nodes/Chaos fallback, per-bone materials and feedback tolerance math. The final 60-second capture contains 7,202 actor samples (3,601 per actor), with no growth in strong-drive hand error beyond the 25-second trial's range. Final hand angular-speed maxima were 4.35 / 3.19 rad/s versus Chaos's 4.30 / 3.12 rad/s. This is numerical verification of the user's setup, not a human visual-quality assertion or a new performance benchmark.

Evidence: Saved/Diagnostics/FeedbackHandDrift contains the matched per-frame captures, native trial scale logs, normal Build-Final.log, result.json, Automation.log, jolt_final.json and Comparison.txt. User-authored unsaved Blueprint edits were preserved before the authorized autonomous restart; both original disk and current saved revisions are backed up in UserEditsBackup-20260911-102132 with hashes. No Blueprint wiring was changed by this fix. Unreal is open on testNN, PIE stopped, with no dirty packages.
