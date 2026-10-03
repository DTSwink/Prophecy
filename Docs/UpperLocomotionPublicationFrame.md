# Upper locomotion hand/thigh discrepancy — October 1

Numerical investigation and subsequent fix of the current ordinary running setup, with no attacks. Blueprint tuning and installed models are unchanged.

## Confirmed publication-frame mismatch

`BuildUpperInputBatch` takes the next pelvis and feet from `CurStateBuffer`, after `AdvanceAgentMover` rebases the lower output into the next root frame. Upper inference therefore produces heading-space arm endpoints and rotations in that next frame. `ApplyUpperOutputBatch` copies those values directly into `UpperPublishedStateBuffer`. `PublishAgentPose` decodes them with `PublishedStateBuffer`, whose pelvis is still in the preceding publication root frame. The necessary next-root-to-publication-root conversion is missing on ordinary upper output. Core parent-local rotations do not need that conversion; heading-space wrist positions and arm rotations do.

At constant 5 m/s and 30 Hz this is a 16.6656 cm translation discrepancy. One captured sample has upper-input pelvis Z=-0.1165925 m, while the lower pelvis used to decode that same upper output has Z=+0.0500632 m. The misplaced hand target is behind its elbow; the fixed-length forearm projection then bends the hand inward. The visible kinematic mesh follows the NN pose, so this is not physical tracking lag.

Offline reconstruction of the existing decoder matches the captured NN left hand within 0.0000255 cm. Changing only the wrist target's frame, using the measured pelvis/root displacement (yaw is zero in this straight run), changes minimum hand-to-thigh bone-segment distance from **3.9421 cm to 14.3211 cm** over the capture. At the original closest frame, tick241, clearance changes **3.9421 to 15.2166 cm**. These are joint-to-bone-segment distances, not mesh-surface collision measurements. The closest thigh in skeletal naming is thigh_l; the opposite thigh stays farther away.

Evidence: `Saved/Diagnostics/RunHandThigh/publication_frame_probe.json`, `baseline_nn.jsonl`, `baseline.json`, and `meshes.json`. Capture covers360 game ticks /179 upper updates per player, Run100%, Kinematic, held sword, zero attacks.

## Viewer comparison and eliminated explanations

The user's selected viewer actor has target gaze approximately-133.3 degrees and initialization gaze-119.2 degrees. The initial screenshot's unselected UI zero was misleading and is NOT an explanation. Replaying the actual Stepper upper viewer with those values gives minimum left hand/thigh distance17.01 cm with sword. Even using Unreal's measured steady gaze-120.42 degrees and initialization0 gives16.82 cm in Stepper. Source is M_Neutral_Run_Loop_F.npz. Results: `stepper_gaze_comparison.json` and corresponding NPZs.

Stepper clamps forearm length before recurrent feedback whereas ordinary Unreal locomotion only clamps decoded positions. This is a separate contract discrepancy, but an isolated temporary model wrapper applying the exact Stepper clamp did not resolve the observed crossing (minimum3.64 cm). Changing only sword input also did not resolve it (5.10 cm). Zero gaze increases clearance but does not explain the actual viewer/Unreal comparison. All probe ONNX/JSON files were restored byte-for-byte after capture; installed upper SHA256 remains EEF317C42ECC094F3628CCA891E16BAD511EF0F7EBED1E2C252BD28CC24D49AE.

## Implemented fix and verification

`ApplyUpperOutputBatch` now preserves ordinary upper recurrence in the next-root frame and converts its publication copy into the published lower/root frame. Recovery source blending occurs before conversion, while both inputs share the next-root frame. Hand recovery, inertia and neutral-return corrections operate on the published upper state with the matching lower pose; their accepted result is converted back for recurrence only when that modifier path runs. Animation-layer feedback now converts its upper pose to the next-root frame alongside its lower pose. Existing attack/armed-pose feedback retains its explicit conversion. No additional inference calls, Blueprint edits, model replacement or collision corrections.

Live Coding succeeded and loaded13:56:21 UTC. A matched360-tick replay (`frame_fixed.json`, `frame_fixed_nn.jsonl`, `frame_fixed_verification.json`) verifies minimum future NN hand/thigh bone-segment clearance **14.32105cm**, presented clearance14.32109cm and visible PhysicalMesh clearance14.32087cm, versus3.94206cm before. Both hands match the independently reconstructed corrected decoder within0.0000306cm; forearm length error is below7e-12cm. All179 player NN input tensors and lower published outputs are bit-identical to baseline, confirming ordinary recurrence and lower motion are unchanged. Owned PIE ended, trace CVar restored0. No automation suite or images. The separate viewer forearm-feedback discrepancy remains outside this fix.
