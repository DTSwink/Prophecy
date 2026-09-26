# Simulated pose rotation agreement

2026-09-26 investigation of the current simulated random attack chain, sampled for360 ticks without Blueprint edits. Samples include25 NN bones, the visible PhysicalMesh, KinematicDebugMesh, single-bone authored targets and the full physical-target pose. Captures and analysis are under `Saved/Diagnostics/SimRotationMismatch-*`.

## Confirmed presentation errors and correction

The optimized full target pose returned only the22 PHAT bodies. NN-authored `ball_l`, `ball_r` and `neck_02` were omitted because they have no PHAT body. Consequently the debug mesh rendered these bones in their reference local pose. Jolt used their newest NN local pose, independently of the current interpolated presentation phase. Both differed from the single-bone target reader.

The shared target builder now retains the NN-authored helper bones, preserving PHAT ordering and all original body targets. Jolt derives helper locals from that same presented world pose relative to the presented parent; they then inherit the *actual simulated* parent, preserving physical deflection. Helpers absent from NN data keep their reference locals; fist/finger overrides still apply afterward. Initial admission follows the same rule. No animation checkpoints, reconstruction rules, drives, authored colliders, constraints or Blueprint settings were retuned.

Measured baseline debug rotation errors reached60.044degrees at the right toe and37.472degrees at neck_02. After correction, both debug errors are below1e-12degrees. Excluding initial admission (ticks1–30), physical-parent-relative errors changed as follows:

| Bone | Before, max degrees | After, max degrees |
| --- | ---: | ---: |
| ball_l relative to foot_l | 2.895 | <1e-12 |
| ball_r relative to foot_r | 19.608 | <1e-12 |
| neck_02 relative to neck_01 | 19.635 | <1e-12 |

All22 original body targets are exactly unchanged across the360-frame before/after replay (maximum position and angular differences0). The physical right-foot transform is also identical frame-for-frame. This isolates the helper correction rather than concealing the issue by changing the rollout. Small late-query thigh/calf differences below1degree occur at first-frame attack entry when the Blueprint has already changed presentation flags; these are distinct from the persistent helper errors.

## Separate physical foot deviation

Foot rotations were already identical between the kinematic display and authored physical targets. With collisions active, the right physical foot differed by up to23.426degrees after tick30. Both feet have angular magnetisation1/global1 and free ankle angular limits in the tested setup.

A controlled diagnostic disables collision responses only after capturing tick55. The prefix through55 is identical. Ignoring all collision channels reduces right-foot angular error at tick60 from14.558 to1.203degrees and at65 from15.349 to0.203degrees, with exactly unchanged targets through70. Disabling self-collision or ignoring World Static/World Dynamic separately does not remove the deviation. The floor component `Floor_0.StaticMeshComponent0` uses the custom `ECC_FLOOR` channel23. Ignoring only that Floor channel reproduces the improvement:12.528→1.603degrees at56,14.558→1.202degrees at60 and15.349→0.203degrees at65, again with an identical prefix through55. This identifies floor contact as the main source of that deviation, not a different rotation target. Later points also improve (23.426→1.646degrees at290), but are not used as identical-target proof because subsequent feedback can change the rollout.

All experimental changes are runtime-only in owned diagnostic sessions; no collision setting is saved or changed in the user's Blueprint. Contact-induced physical deflection must not be disguised by forcing the displayed skeleton to the kinematic pose.

## Validation

Live build214.24s, patch loaded2026-09-25 at22:04:20UTC. All16 `Prophecy.NN.PhysicalTargets` and `Prophecy.NN.Interpolation` tests pass22:05:23UTC, including the new AuthoredHelpers test across Current, Attack Viewer and Hermite modes, an intermediate reference-only parent, physical-parent inheritance and unchanged reference helpers. Existing sparse-body oracle, rigid forearms/calves, clamps, knee smoothing and interpolation tests pass. Pose Blueprint compiles status3, wiring/defaults preserved, unsaved. No restart. Include the changes in the next authorized normal build.
