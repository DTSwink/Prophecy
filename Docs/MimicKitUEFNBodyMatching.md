# MimicKit body matching to UEFN PHAT

## Wrist correction — October 15, current model

User explicitly requested restoring the wrists and regenerating the retarget.
This supersedes all fixed-wrist/28-action descriptions below: the model still
has15 bodies and23 colliders, now34 actions and10 coupled ball profiles.
Both wrist joints use their original PHAT frames and coupled twist/swing limits.
User approved stock neck actuator settings for the added wrist axes: velocity
gain10, torque limit50Nm per axis (no position drive in velocity mode).
No other motor settings or body geometry/mass/inertia were changed.

All26 accepted cuts were regenerated from the original recordings, including
the existing independent foot lift with preserved leg poles. Wrist orientation
matches the original recording within6.55e-5degrees; root and ALL nonwrist joint
channels are bit-identical to the previous corrected references. Remaining
position differences come from the other deliberately reduced chains.
Before-wrist model/motions: `Saved/MimicKitUEFN/before-wrists/`.

Using the existing dataset+5% rule, only wrist profiles needed further expansion:
right hand30/23.71/50degrees and left hand40.86/46.31/50degrees, in
twist/swing2/swing1 order. Saved PHAT SHA256
`f948ed9de335c5d55b467ccd667702817c48458fc2e2e3d72773efc74193a4d5`.
Only those angular fields changed; dirty PoseAgent preserved. Separate asset
backup `Saved/MimicKitUEFN/before-wrist-limits/`; source-rig.json refreshed.
Verification:2,183,020 dense joint samples including5% room and34,832 exact-Jolt
reference/margin cases pass;4,200 random profile classifications agree with Jolt.
Direct limit-only solves exercise both wrists and an ankle (480steps each).
Newton import and integrated CPU reset/phase/finite-state checks pass.
The first tests caught a stale hardcoded eight-profile assertion; replaced it
with unique mapping/count validation against the actual metadata, not a bypass.
The independent retarget audit initially used a nonexistent test accessor;
corrected it to get_dof_dim; no runtime workaround.

## Current PHAT limits — October 15, authorized omni expansion

User explicitly requested modifying the original PHAT so the accepted dataset fits with 5% angular leeway. This supersedes the earlier preserve-original-limits instructions below. Saved only `PA_UEFN_Mannequin`, with eight retained profiles expanded against all26 corrected retargeted gait cuts; no geometry, mass, inertia, joint-frame, collision, drive or damping changes. Existing larger limits were retained. Both ankle twists are now LIMITED, not LOCKED. Other14 PHAT constraint profiles are unchanged; omitted articulation is still omitted in the15-body model.

Angles below are degrees in **twist / swing2 / swing1** order (not Euler XYZ):

| Retained model body / PHAT child | New angular limits |
|---|---|
| torso / spine_03 |17.92 /16.59 /15.71|
| head / neck_01 |32.01 /20 /30|
| right_upper_arm / upperarm_r |35.56 /65.67 /70|
| left_upper_arm / upperarm_l |31.19 /65.57 /84.60|
| right_thigh / thigh_r |38.65 /31.36 /80|
| left_thigh / thigh_l |55.07 /33.29 /80|
| right_foot / foot_r |31.15 /23.78 /47.50|
| left_foot / foot_l |26.62 /20.55 /60.17|

Fit method: multiply each measured twist angle and swing-angle magnitude about the retained constraint centre by1.05. Fit the minimum-area axis-aligned ellipse in Jolt swing coordinates containing these expanded samples, bounded below by the existing swing ellipse; round changed limits outward to0.01degree. This handles coupled diagonal swing, not independent-axis maxima. Fit at16 subdivisions per recorded interval; independently verify at128. The one-axis hinges retain their exact existing convention; exported reference rounding below1e-5rad is removed only from the diagnostic hinge calculation, matching the previous Jolt test. No motion clamp/retarget adjustment.

`fit_motion_limits.py` creates the plan; `apply_motion_limits_unreal.py` backs up the original asset, checks source hashes/no active Play/no dirty PHAT, applies through Unreal's constraint-accessor API and verifies the live export differs only in those angular fields before saving. Preexisting dirty PoseAgent remains unsaved. Backup: `Saved/MimicKitUEFN/before-omni-limits/`. New saved asset SHA256 `a89128ea603499a968f2567302fa765dd99b70725637b3746bc05492253e2c35`.

Current model provenance is `Saved/MimicKitUEFN/source-rig.json`; build.py/prepare_physics.py use it and metadata records its path. Historical `Saved/Robotics/rig.json` remains byte-identical for old experiment evidence; its saved-PHAT fingerprint is intentionally historical now. Do not rebuild this new asset from that stale export. Regenerated limits/physics/overlay metadata; actual humanoid XML is byte-identical because only external ball profiles changed. All26 motion files are byte-identical.

Verification:1,871,160 densely sampled joint poses within limits including5% margin;29,856 original/margin cases independently accepted by the exact project Jolt DLL;3,600 random cases agree between the adapter math and Jolt. CPU480-step limit solve passes (swing ellipse radius1.000505, ordinary iterative solver tolerance). Newton import preserves15bodies/28actions/23colliders and max collider-position discrepancy6.209e-7m; eight ball profiles, now zero locked-ball rows. Receipts: `omni-limit-plan.json`, `applied-omni-limits.json`, `omni-limit-verification.json`, `validation.json` under Saved/MimicKitUEFN, plus Labs/MimicKitUEFN/newton-validation.json. These are admissibility/setup checks, not a trained policy or proof of full-body Jolt parity.

Requested October 15, 2026. Status: separate model and interactive overlay implemented in `Labs/MimicKitUEFN`; original model and live training unchanged. User explicitly clarified that additional colliders may be attached to existing bodies, without adding bodies/bones/joints.

## Agent handoff: integrate the skeleton and scoped physics changes

Updated October 15 at the user's request for forwarding to another agent. This section is the current integration brief; the original asset-only scope and unchanged-run notes below describe the earlier delivery. Drafting this brief has not changed any running experiment. Read `ProjectJournal.md` opening, this document, `Labs/MimicKitUEFN/README.md`, and the destination experiment's current dedicated journal before implementation. Do not confuse the separate walking and get-up runs or assume an old pod/deadline is current.

### Objective and exclusions

Adopt the separate UEFN-proportioned humanoid in the destination MimicKit/Newton experiment and implement the applicable Jolt physics differences described below. Preserve the original humanoid as a selectable, reproducible baseline. Keep the existing 15-body hierarchy and 28 action dimensions; multiple collision shapes on a body are intentional.

Explicitly OUT OF SCOPE per the user: maximum body-speed matching/clamping, motor-response or motor-saturation matching, and ground-contact mismatch/calibration. Leave the destination experiment's control mode, gains, torque budgets, armature and ground/contact solver settings unchanged. Do not switch to the historical PhysicalRecovery controller. This work also does not request a network-size change, reward redesign, phase input, discriminator, new training schedule, or cloud allocation. Any training restart/resume must follow the receiving chat's authorization and budget.

### 1. Use the existing asset, do not recreate it

- Asset: `Labs/MimicKitUEFN/humanoid_uefn.xml`. Companion metadata: `limits.json`. Runtime limits: `runtime.py`. The direct-MuJoCo `humanoid_uefn_physics.xml` is an independent test counterpart, not a substitute for the MimicKit asset loader.
- Source: `Saved/Robotics/rig.json`, verified when built against the saved UEFN mesh and PHAT hashes. Recheck hashes before adoption. If assets changed, regenerate from a fresh export; do not silently overwrite the user's Unreal assets with the old export.
- All 23 PHAT shapes appear once, distributed over 15 existing bodies. Preserve the ownership table below, sizes, rest transforms, corresponding joint anchors, and retained constraint frames. Added shapes are not additional free bodies or unpowered joints.
- Preserve the already aggregated mass, COM and effective inertia (total mass 78.2545296 kg). Do not let a loader recalculate these from shape density or count their mass twice. Verify the *loaded Newton model*, not just the XML.
- Coordinates: metres, proper +90-degree rotation about Z from exported UE coordinates; UE forward -Y becomes MimicKit +X. Do not introduce a reflection or apply centimetre conversion twice. Quaternion order depends on the API; do not assume Warp helpers and serialized MuJoCo quaternions use the same order.
- This is a reduced articulated model. The omitted spine, neck and clavicle articulation stays rigid within its owner; wrists stay fixed. It matches PHAT collider placement in rest pose, not all 23-body articulated dynamics.

### 2. Wire the existing PHAT limit adapter into the actual engine

After constructing the new model's `SolverMuJoCo`, call `Labs/MimicKitUEFN/runtime.py`'s `install_limits(solver.mj_model, solver.mjw_model)` before stepping or CUDA graph capture. Register only the new model. XML alone is insufficient: Newton's triple-hinge conversion otherwise creates unrestricted ball joints.

Package its dependency `Labs/PhysicalRecoveryLab/phat_constraints.py` with the new asset. Do not invoke the old pipeline's installed-library patcher. The current adapter is an in-process, version-checked hook; preserve its fail-fast behavior for unsupported versions or ambiguous mappings. Verified versions: Newton 1.0.0, MuJoCo 3.5.0, MuJoCo Warp 3.5.0.2; adapter also supports the older 3.6.0 fixture.

Expected: four native elbow/knee hinge profiles, eight coupled twist/elliptical-swing profiles, including two bilateral locked ankle-twist rows. Preserve reference offsets and the new asset's tested angular-stop regularization. Do not replace coupled limits by independent Euler clamps, clip poses after stepping, or add root forces. Current Jolt imports the PHAT angular bounds as hard limits; do not silently implement Chaos soft-limit semantics instead.

### 3. Match the applicable free-body physics

**Gyroscopic behavior:** the earlier exact-project-DLL calibration found Jolt gyroscopic forces disabled, while MuJoCo includes them. Verify this remains true for the intended game bodies. If so, cancel MuJoCo's gyroscopic term each physics substep by adding world torque `omega cross (I_world * omega)` using the new compound body's actual principal inertia and current inertial-frame orientation. This cancels the existing term; it is not a damping force. Do not remove every Coriolis/bias force or apply it only at policy frequency. Integrate additively with existing external forces and refresh/clear the owned contribution each substep so it cannot accumulate. Check CUDA graph execution follows the same path.

Reuse the mathematics and independent checks from `Labs/PhysicalRecoveryLab/calibrate_gyroscope.py` and the body-force kernel in `joint_pd.py`; port only the relevant force calculation, not the old motors or controller. Historical evidence: `Saved/Robotics/gyroscope-calibration.json` and `relative-native-no-gyro-tests.json` (verify actual receipt location before use). The isolated one-body comparison improved from 80.391 degrees maximum rotation discrepancy to 6.24e-5 degrees. That does not establish whole-character parity.

**Passive body drag:** preserve the exported per-body linear/angular damping, separately from motor/joint damping. The prior export has zero angular damping and mostly 0.01/s linear damping, with exceptions; read values rather than assigning a blanket value. The earlier implementation uses `F = -mass * damping * COM_velocity`. For a compound, compute each source member's rigidly carried COM velocity, sum its drag force, and sum the moments about the compound COM. A single averaged damping coefficient at the compound COM can lose rotational drag. Do not double-apply native fluid drag or repurpose joint damping. Validate the aggregated force and torque independently; if current source angular damping is nonzero, establish its Jolt mapping before adding it.

**Gravity and stepping:** verify source/runtime gravity and units; historical fixture used -9.81 m/s². Preserve the current experiment's 240 Hz physics and 30 Hz policy stepping unless the receiving task specifies otherwise. Do not copy the old explicit-Euler integrator choice: it depended on an older actuator implementation. Keep current integration, solver iterations and contact settings; report an unrepresentable difference rather than silently tuning it away.

**Self-collision:** verify the generated source pair exclusions survive Newton import. Grouping makes body-pair exclusions coarser, and shapes inside one compound do not self-collide. Document this known reduction; do not invent new blanket limb exclusions to make a test pass. Ground-contact tuning remains excluded.

### 4. Reconnect task data without changing the task

Keep actor/critic architecture, action order, observation layout, PPO, noise, loss formulas and weights unchanged unless separately authorized. The current get-up task has physical-state inputs, no phase/time input and no discriminator. Preserve that contract when adopting this model.

Rebuild any geometry-dependent standing target, floor-start bank, foot-width reference and viewer geometry against the new kinematics. Do not reuse old world-space target arrays, old floor clearance, or old body-index assumptions. Preserve the intended approved pose and objective; if retaining that pose requires a new retargeting choice, present it to the user instead of silently substituting the PHAT rest pose. Joint-angle/action dimensions matching does not prove old learned actions or normalizers transfer unchanged. Record the checkpoint/model contract and follow the receiving user's choice of restart, resume or fresh weights.

### 5. Acceptance checks before training

1. Re-run `build.py`, `test_model.py`, and `test_newton.py` in the documented environments. Existing receipts under `Saved/MimicKitUEFN/` provide baselines: 23 shapes, 15 bodies, 28 actions; independent Newton rest-position discrepancy at most 6.21e-7 m; 3,600 retained-joint classification cases against the exact Jolt DLL passed. Preserve failed evidence rather than widening bounds.
2. Test the *integrated engine*, including its captured GPU path, for active limits, locked axes, additive forces, gravity, loaded mass/COM/inertia and collider transforms. The earlier CPU tests do not prove this wiring is complete.
3. Repeat isolated anisotropic-body gyro validation and compound-drag force/torque checks. Exercise rest and nonzero angular velocities; no actuators or contacts in those diagnostic comparisons.
4. Run bounded finite-state checks with the new full body and unchanged controller, including standing and admitted floor starts. Test resets and independent worlds. If instability appears, diagnose and report it; do not secretly change gains, add a speed clamp or increase physics frequency.
5. Verify target and simulated body transforms share units/frames in the replayer and losses. Preserve the plain name/value per-tick display and all current loss terms. Use the existing overlay at `http://127.0.0.1:8842/` for geometry; it is not a physics test.
6. Measure physics/rollout throughput before and after at the same world count, hardware and warm-up, separately reporting compilation and one-time preparation. Preserve batched forces and CUDA graph capture; avoid per-world Python or per-substep host transfers. Save code, model metadata and validation receipts with any authorized run/checkpoint.

Report exactly what is integrated and tested, plus the deliberately excluded speed-cap, motor-response and ground-contact differences. Do not claim 1:1 Jolt simulation: the reduced body topology and those excluded differences remain.

## Implemented result

See [model README](../Labs/MimicKitUEFN/README.md) for the exact mapping, files and adapter entry point. 15 bodies, 28 action dimensions, 23 PHAT colliders. Pelvis owns pelvis/spine_01/spine_02; torso owns spine_03..05 and clavicles; head owns neck_01/neck_02/head. Remaining limb colliders map one-to-one. Torso keeps the spine_03 joint profile, head keeps neck_01; omitted chains are not replaced by invented summed limits. Wrists remain fixed as in the original training model.

Source mesh/PHAT hashes verified against the current saved files. Generated collider surface/transform error versus exported PHAT is 1.10e-13 cm in double precision; effective mass/COM/inertia aggregated without duplication, total78.2545296kg. Original source humanoid hash unchanged. Same kinematic names/hierarchy/action size verified over30 nonzero poses (maximum FK position discrepancy5.58e-7m). 3,600 retained-profile cases match the actual project Jolt DLL's admissibility classification. Constraint-only480step CPU test passes, locked ankle twist3.53e-6rad and swing ellipse radius1.00177; limits remain iterative solver constraints, not hard post-step clipping.

The new `runtime.py` supplies coupled twist/elliptical swing rows and locked axes. This is necessary because current Newton drops triple-hinge limits when importing ball joints. It hooks only the new registered model in the test process, writes no installed libraries, rejects unsupported versions/layouts, and reuses old verified row mathematics. Vanilla zero boundary stiffness failed the initial dynamic test; the new asset uses the previous PHAT adapter's regularization, documented in the README. No active training deployment or claim of identical Jolt motor/contact response.

Interactive viewer at `http://127.0.0.1:8842/`: independently loaded generated colliders versus original PHAT data, plus optional old humanoid; orbit, separation, opacity, body isolation, skeletons and bounded joint sliders. These are pose previews, not simulation. Receipts: `Saved/MimicKitUEFN/validation.json` and Newton-specific verification alongside it. No Unreal/BP/D-S changes.

Exact current Newton1.0.0 / MuJoCo3.5.0 / MuJoCoWarp3.5.0.2 CPU import/forward check also passes:15 bodies,34 generalized velocities including6 root,8 ball profiles,2 locked-axis rows,23 colliders, maximum collider-position discrepancy6.209e-7m (6.209e-5cm). A first test needed correction for Newton's prefixed/suffixed imported names; a cold CPU compilation exceeded the initial55s diagnostic timeout, so the cached bounded retry completed. No GPU probe/training, library-file edits or deadline extension. Report `Saved/MimicKitUEFN/newton-validation.json`; screenshot `Saved/MimicKitUEFN/overlay.png`. Viewer controls verified interactively, including ankle swing, reset and original-model toggle. Local serverPID17832, bound127.0.0.1:8842.

## User intent

Adapt the current training humanoid's proportions and existing physical bodies to the project's UEFN PHAT in rest pose, including joint limits. Keep the current framework and skeleton topology: **do not add bones, bodies or joints to reproduce the full UEFN skeleton.** Match the bodies that already exist.

- Match corresponding joint locations and segment proportions in the UEFN reference/rest pose.
- Match corresponding PHAT collider shapes, dimensions, orientations and placements in that pose. Match physical geometry, not only the rendered appearance.
- Match corresponding joint limits and their constraint frames, including which axes are locked, twist bounds and swing bounds. Numeric angle values alone are insufficient if the axes differ.
- Preserve existing bone/body identities, hierarchy and action/observation layout. Do not silently introduce extra degrees of freedom to accommodate a different joint type.
- Treat the project's UEFN PHAT as the source of truth. Read its current state before implementation; old exports are evidence, not permission to overwrite newer asset edits. Leave the Unreal assets themselves unchanged.

## Mapping requirements

Keep the explicit current-body-to-PHAT-body mapping in the generated metadata. The user approved multiple colliders on the existing bodies after the initial clarification. Preserve each collider's exact rest transform. Do not distribute multiple joint limits onto one joint or add missing neck/spine joints. The compound ownership and retained-profile choices are listed above and in the README.

Record and numerically verify rest-pose joint positions, collider transforms/dimensions and angular-limit behavior in consistent units and frames. If the current backend cannot represent an original limit faithfully, report the limitation rather than substituting a different one without agreement.

This request is about proportions, existing colliders and joint limits. Broader Jolt parity work (gyroscopic dynamics, body-speed caps, motor saturation and contact solver behavior) is separate. Do not bundle those changes, reward changes or controller tuning into this task. Report any required mass/inertia consequence of changing geometry instead of silently claiming those properties are unchanged.

Historical technical evidence: [PhysicalRecovery.md](PhysicalRecovery.md), especially the source export, collider checks and custom twist/elliptical-swing constraint tests. Those old patches are not automatically present in the current MimicKit/Newton pipeline.

## Current run remains unchanged

The user withdrew the proposed constant termination cost and said the current run is learning and should continue. Do not implement the proposed 1.5-times-mean constant penalty. Retain the current termination formula, training settings and existing runtime deadline. The separate asset/overlay request does not authorize a training restart, deployment or deadline extension.
