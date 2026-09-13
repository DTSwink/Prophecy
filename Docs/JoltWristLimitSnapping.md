# Wrist snapping at runtime angular limits — 2026-09-11

## Player-only scope (subsequent user request)

The extra swing constraint is now restricted to a Prophecy Agent possessed by a PlayerController, and only to eligible limited swing cones. NPCs, unpossessed agents, fully free swing joints, locked swing joints, and twist-only limits use the stock SixDOF directly. The added correction handles swing cones; it does not add a separate predictive twist constraint.

Admission checks the controller once. `NotifyControllerChanged` updates the policy on possession/unpossession, and existing runtime angular-limit updates re-evaluate only changed joints. A wrapper is registered only when needed, around the retained native SixDOF. Removing it re-registers that same native object. Bodies, their handles, poses, velocities, native warm starts and constraint counts are retained.

There are no added per-frame possession checks, joint eligibility scans, allocations or speculative solver callbacks for NPC/free/locked joints. The player's eligible limited cones retain the necessary extra scalar solve. Range/possession transitions perform bounded registration work on the game thread outside physics stepping. This is a structural removal of unnecessary work; no new full-game FPS benchmark was run for this scoping change.

Build and targeted verification for this change are recorded under `Saved/Diagnostics/PlayerSwingLimits/`. The original numerical captures below predate the player-only restriction and demonstrate the correction itself, not an NPC guarantee under the new policy.

The normal Editor build and all six targeted tests passed. The actual character fixture spawns a PlayerController, possesses/unpossesses the agent, applies a 45-degree wrist limit and then locks/frees it, checking the registered wrapper count at each transition. The native rig fixture verifies that policy/range transitions retain body state, handles, native joint count and external grip ownership. No test errors; one existing disconnected `A_Sword` compiler warning. Unreal was left on `testNN` outside PIE with no dirty packages.

## Reproduction and diagnosis

The saved/current `testNN` setup applies Limited 45 degrees to both wrist swings and twist. We recorded both physical bodies, displayed mesh sockets, parent bodies, native angular velocities and presented/future NN targets at each distinct simulation timestamp. The fixed simulation interval remained 1/60 second. Captures run for 90 simulation seconds because the fault is intermittent. Measurements below exclude the first five seconds of world time.

The strong-drive character (`BP_ProphecyManualPoseAgent_C_1`) had real quaternion rotation jumps. Its displayed hand matched its physical body; this was not Euler wrapping or a rendering-only artifact. In the original run the maximum hand rotation per step was 38.393 degrees, with 57.890 rad/s maximum angular velocity. The NN target moved smoothly, with a maximum 12.569-degree step. Relative wrist rotation reached 55.053 degrees per step over the complete capture (49 degrees at the initially investigated event).

Native tracing identified a boundary release. Just before the large step, the wrist was near its cone boundary. On the escaping step all three native rotational constraint impulses were zero, hand speed reached 56.293 rad/s, and the joint moved far outside its range; the cone impulse resumed on the following step. Runtime limit setters only changed the native ranges at startup. Disabling self-collision or native warm starting did not remove the fault. Switching the same setup to Chaos did.

Jolt's `SwingTwistConstraintPart` activates its cone velocity row only when the current orientation needs clamping. An external velocity servo plus the connected linear anchors can accelerate a wrist that is just inside the cone beyond the boundary in one step. The existing position solver then has a large error to correct. This is an interaction between our physical-animation control and the native limit response, not evidence that all native Jolt cone joints are unstable.

Reference implementation: [Jolt SwingTwistConstraintPart](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Constraints/ConstraintPart/SwingTwistConstraintPart.h). The local pinned source and native trace were used for diagnosis.

## Correction

`FSpeculativeJoint` wraps the existing native SixDOF joint and adds one unilateral angular velocity row while inside an eligible swing cone. For its normalized ellipse function `C <= 0`, the row imposes the local first-order bound `dC/dt <= -C/dt`. It allows remaining interior clearance and inward/tangential motion, rather than waiting until the joint has already escaped. Outside the cone, the original native limit and position correction handle the violation.

The original joint retains its anchors, frame offsets, twist/locked-axis solving and position solver. No NN target projection, display smoothing, extra timestep, magnetisation retuning, damping or authored range changes remain in the final implementation. The unsuccessful target-projection trial and all temporary diagnostic console switches were removed. This remains an iterative hard-constraint solver, not a mathematical guarantee of zero angular error for arbitrary forces or timestep sizes.

The range-dependent coefficients and eligibility are cached at creation and actual runtime range changes. Fully free or locked swing configurations take the native path. Eligible limited cones add one scalar velocity row; this is additional solver work, not zero overhead. There is no extra registered joint, per-frame allocation or added actor tick. Runtime changes reset the additional cached impulse; rig handles and body state remain intact. The private wrapper is used for local live rigs; exporting/recreating it through Jolt's generic serialized constraint-settings factory is not implemented.

## Evidence and validation

Files are under `Saved/Diagnostics/WristSnap/`.

| 90-second capture, strong-drive character | Max hand step (degrees) | Max wrist-relative step (degrees) | Max hand angular speed (rad/s) |
| --- | ---: | ---: | ---: |
| Original Jolt (`baseline`) | 38.393 | 55.053 | 57.890 |
| Chaos (`chaos`) | 14.040 | 12.284 | 13.791 |
| Corrected Jolt, normal build (`final`) | 11.621 | 13.783 | 12.911 |

The final normal-build capture reproduced the prototype's rotation statistics. The original strong-drive character had 140 hand steps above 20 degrees; the final run had none (a reporting threshold, not a clamp in the implementation). Its 99th-percentile hand step fell from 33.966 to 10.674 degrees. The other, deliberately weak-drive character's maximum hand step also decreased, from 16.987 to 12.278 degrees. Both rigs retained their 45-degree ranges and a constant 1/60-second simulation interval. `result.json` contains per-character statistics, source capture hashes and the automation outcomes.

The baseline capture's **limits column is invalid**: its initial name-based accessor did not resolve the real `UserConstraint_8` wrist joint. Quaternion/body/target measurements are valid. Subsequent captures select the constraint by its `hand_l`/`lowerarm_l` endpoints, confirm all three 45-degree limits, and native tracing confirms the original cone-boundary failure. Do not infer limit changes from the baseline accessor strings.

`EditorInvestigation.log` and the compact `NativeTrace.log` retain the original diagnosis. The normal Editor build result is in `Build.log`. Final normal-build capture and automation results are recorded separately beside these files.

The native regression `Prophecy.Jolt.Joints.SpeculativeSwingBoundary` reproduces a 30 rad/s outward request from 0.1 degree inside the boundary. Its control confirms the original overshoot; the corrected joint remains within 0.05 degree in the tested cases. Cases cover static/dynamic parents, circular/asymmetric cones, inward/tangential/twist velocity preservation, and runtime Free→Limited→Free transitions. All six selected tests passed in the normal build: this regression, existing joint mapping, angular frame, Locked/Free/Limited, per-child Blueprint controls and atomic live updates. There were no test errors and one existing disconnected `A_Sword` compiler warning. `FinalAutomation.log` retains the run. Unreal was left on `testNN`, outside PIE, with no dirty packages.

Current unsaved Blueprint edits were preserved before the autonomous normal build. Both the prior disk asset and the newly saved current edits are backed up under `UserEditsBackup-20260911-225910/`; no Blueprint wiring or map edits were made by the fix.
