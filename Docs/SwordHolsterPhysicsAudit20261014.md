# D/S simulated attachment audit — October 14

Status: implemented and numerically verified within the coverage below. Unreal is open on TestNN, outside Play. This report does not claim human motion acceptance or universal physics/lab identity.

## What caused the hitch

The sword's native body used a prediction of next tick's physical pelvis, while the visible holster followed the actual completed pelvis. The constraint was following that inconsistent command. Six simulated S slides departed from the intended holster-local path by **0.4995–1.4075 cm**; the kinematic reference stayed within **0.000028 cm**. Loosening the hand constraint would not correct the two different reference frames.

## Final ownership

| Phase | Sword | Right arm | Rest of character |
| --- | --- | --- | --- |
| S reach | Existing dynamic hand grip | Existing simulated FK drive | Simulated |
| S attached alignment and slide | Child of actual holster; local insertion path | Native upperarm_r, lowerarm_r and hand_r temporarily kinematic | Simulated, including clavicle and pelvis |
| D reach | Remains in holster | Existing simulated FK drive | Simulated |
| D slide | Child of actual holster; local insertion path | Same three native bodies temporarily kinematic | Simulated |
| Release/return | S stays holstered; D returns to hand | Simulation restored at actual pose and velocity | Existing FK return and NN handoff |
| Fully kinematic agent | Existing kinematic path | No temporary native-arm ownership | Unchanged |

After the parent's physics step, the existing small two-bone solve places the arm against the completed physical clavicle and holster. It writes **real native bodies before physical-pose publication**. Display, native sword and query collider agree; this is not a displayed-only correction.

## Changes and audit findings

1. **Removed competing sword authority.** Deleted the separate predicted sword world target during attachment. The holster-local path owns the attached sword. Existing physical prediction during pre-attachment reach remains; reaching was not redesigned.
2. **Removed the attached hand–sword joint.** It is no longer needed when the three arm bodies follow the holster. S reach retains its existing dynamic grip. No moving replacement joint, per-tick joint construction, or extra force path into the torso.
3. **Suspend existing anatomical joints.** Only joints touching the owned three bodies are suspended, and only their previously enabled state is restored. The shoulder joint is included; the clavicle stays dynamic. Warm-start state is reset when those joints resume.
4. **Exclude owned arm servos.** Remove these bodies from both already-published and future servo packets. The native step does not integrate last tick's carried velocity while they are kinematic. No conflict between a servo and explicit body ownership.
5. **Preserve release motion.** Every completed arm pose supplies native COM linear velocity and angular velocity from the preceding pose and actual physics step. Switching back to Dynamic does not overwrite either pose or velocity. The native regression verifies all four are unchanged at the switch.
6. **Seed return from the completed arm.** The existing FK return starts from the actual release pose and its actual preceding pose, rather than an earlier planned pose. D's signed hand-axis turn is initialized at that same boundary. The two previous-pose arrays are captured once at release; inactive agents do not record history.
7. **Preserve the authored motion controls.** D/S-specific body targets, pole behavior, restored elbow IK correction, main inertia strength/duration, hand rotation return, signed sword turn, curves, early torso return and NN blend remain. No new motion knob or smoothing layer. The standard two-bone solve is reused, not replaced by a second planner.
8. **Keep the actual holster behavior.** Existing early-S kinematic fraction, rotation compensation, rest transform, return duration and physical remount remain. Tests cover 0%, 80% and 100% compensation. Translation stays mounted to the pelvis; compensation changes rotation. A physical holster becomes kinematic for grip, returns over the configured duration, then resumes simulation.
9. **Preserve geometry and scale.** SwordRef, blade-base marker, blade axis, class-authored placement, component pivot and blade-axis-only shrink remain the geometry sources. Read the current native body-origin mapping after resize. Removed a redundant scale-removal operation; no asset or tuning changes.
10. **Keep existing collision policy.** Existing D/S right-arm suppression and temporary head/clavicle suppression remain. Neck-limit settings restore exactly. The temporarily kinematic arm deliberately does not provide normal dynamic arm reactions while attached, as requested. This is not a physical grasp/contact solver during that interval.
11. **Handle interruption.** Hide, drop, reset and Sim→Kinematic restore the arm and action settings. Direct sword destruction exposed a real ordering defect: the post-physics arm update ran before ordinary equipment cleanup and treated the missing sword as a world fault. It now releases ownership and lets the existing cancellation path run. The failing capture is retained; both direct-destruction cases pass after the fix.
12. **Avoid re-binding during teardown.** Sword refresh no longer attempts to reconstruct a grip for a destroyed agent or ending world. Ending-world arm entries retire without trying to restore a rig that is being destroyed. Existing unrelated contact-restoration teardown messages remain documented below.
13. **Protect callback boundaries.** Transform updates can invoke removal callbacks. The update snapshots weak agent keys, copies each small arm record, and rechecks ownership rather than retaining map iterators across callbacks. Missing equipment cancels ownership; an actual native/world invariant failure is still reported, not silently hidden.
14. **Keep recurring work bounded.** Empty attachment map exits immediately. No extra NN inference, skeleton search, file parse, guide cache or permanent per-agent timer. Body handles are captured on attachment. Native three-body pose writes and the usual up-to-128-agent key snapshot use inline storage. Profiles and existing staggering remain shared. Above 128 simultaneously attached agents the snapshot may allocate; no unlimited-crowd performance claim.
15. **Measure with standard profiling.** A CSV scope/counter measures the new completed-parent arm stage only while active. It adds no user-facing control. Source and tests do not contain the rejected alternative joint or presentation-only solutions.

## Numerical verification

- **11 live motion captures, 4,705 recorded ticks, 123 completed D/S slides**, across three agents. Current setup, fully kinematic, idle/walk/run/turn, physical holster, leeway alignment, compensation extremes, and frame-rate caps. No missing recorded ticks, nonfinite native poses, or incorrect arm ownership in these captures.
- Across these captures, maximum post-correction S path error is **0.00004615 cm**. Maximum rendered/native and query/native position discrepancy is **0.00000417 cm**. Native arm bones and physical mesh agree within **0.000000016 cm**.
- After the first grip-admission sample, maximum measured simulated hand/grip position residual is **0.00000927 cm** across the movement/compensation cases. The admission tolerance itself is unchanged; see limitations.
- On the release frame in idle/walk/turn checks, actual hand position and the pose used to begin return differ by at most **0.0000000000032 cm**. The native unit test independently verifies unchanged pose and linear/angular velocity across the mode switch. Subsequent motion still follows the user's authored return and NN behavior; this does not impose zero acceleration on those curves.
- **10 interruption cases pass:** hide, drop, reset, mode switch and direct sword destruction, each during attached alignment and sliding. Arm ownership and limits restore; physical holster return completes. World/actor teardown also exercised by every owned Play session; native rig teardown has a focused regression.
- **Frame-rate check:** 415 matched ticks at measured **9.998 FPS versus 24.693 FPS** have exactly identical captured physical transforms and D/S report values. Both use the fixed 1/60 game step. The 30-cap versus uncapped pair also matched, but both ran near25 FPS, so it was not used alone as evidence of frame-rate independence.
- **Native automation:** 26 tests passed in the broad run, including new KinematicLimbHandoff, generic joints, standalone body/query cleanup, bone order, head/hand root frames, return/pole continuity, staggering and tip alignment. ElbowIKParity covers128 variants/4,800 samples.
- **Fresh math reference:** 64 supported full-motion combinations match the unchanged lab math within **0.00008675 cm / 0.00021190 degrees**, with exact event ticks. This validates the procedural calculation; simulated parents still move physically.

### Tests that are not green

The broad run had two failures, and their outputs were retained. AcceptedMotion initially used a stale reference from before the latest inertia changes. After refreshing only diagnostic reference data, the64 supported full-motion combinations pass; the three short recorded-return clips still are not valid full-action-controller fixtures in that harness. They have a separate passing return regression. AuthoredLab still uses October12 tuning and obsolete phase assumptions. It was not rewritten to manufacture a passing result. This is therefore **not an all-green claim for the legacy suite**.

The first cancellation harness also assumed immediate rest restoration and used world-relative values from a detached physical holster. It was corrected to test the actual timed-return contract. The original failure and corrected results are retained separately.

## Performance

A lightweight owned650-tick run recorded644 CSV frames without per-tick pose dumps. The new attached-arm stage was active for117 frames:

| Measurement | Time |
| --- | --- |
| Active-frame mean, entire three-agent test stage | **0.262 ms** |
| Median | **0.250 ms** |
| 95th percentile | **0.358 ms** |
| Maximum | **0.474 ms** |
| Frames with all three arms attached: mean | **0.272 ms** |
| No attached arm | No solver/body-publication work; measured scope0 ms |

This includes the completed-parent solve, native poses and holster/sword component publication. It excludes the ordinary NN, existing controller work, native physics step and rendering. Different numbers of arms overlap across the run; these figures must not be multiplied into a claimed100-agent benchmark. A focused native one-body pose-write microbenchmark separately measured0.278–0.438 microseconds per call over seven1,000-call batches; that excludes solve/presentation/physics and is not the complete feature cost. The new stage is measurable, not free. No net full-game speedup is claimed.

## Remaining boundaries

- D still admits grip within the existing **2 cm / 5 degree** arrival rule. First admission samples can have up to1.77cm hand residual before the first completed attached-arm solve; fully kinematic already uses this rule too. I did not silently tighten it or add another blend. Release is the boundary fixed here.
- Unreachable targets still respect arm length; the sword is not dragged off its holster path or the arm stretched to conceal that condition.
- No new simultaneous attack/get-up/grasp ownership policy was introduced or certified. An existing external grip prevents admission of the temporary native limb; cleanup must still be able to restore an already-owned limb.
- Startup still reports pre-existing unsupported MACD admissions, and some existing contact-restoration calls log during world teardown. Successful live captures have no new active-play attached-arm failure. These messages were not hidden with asset changes or broad log suppression.
- Numeric checks do not replace the user's motion judgment. The lab was not modified to make the tests pass.

## Rejected trials and test incident

Component-local presentation alone left a running hand behind by up to18.50cm. A moving hand–pelvis joint introduced a new reaction path and repeated joint rebuilding. Both trials were removed before the accepted implementation; their captures remain evidence.

I added a new CSV category through Live Coding and then started profiling. Unreal crashed in `FCsvProfiler::BeginStat` at category lookup. That native global registration needed cold initialization; treating it as a safe live patch was my mistake. No user Play or unsaved asset was involved. The subsequent normal build/reopen initialized it correctly, and two CSV captures then passed. The first rebuild was briefly blocked by the crash reporter holding the DLL/PDB; only the reporter monitoring our crashed process was closed, and the link retry succeeded. Stack/build records are retained. The journal now records this initialization requirement.

## Save/build state and evidence

- User's dirty TestNN was backed up and saved before the initial required retained-layout restart. No Blueprint graph/tuning, lab state or profile changes. Full Blueprint graph hash remains identical; lab/profile hashes remain identical.
- Editor **19216** is open on TestNN, outside Play; no dirty packages; original `t.MaxFPS60` restored. Native Blueprint health: status3, no stale property/pin types.
- One planned normal restart for retained layouts, plus recovery from the profiler-test crash. The final direct-destruction guard loaded with successful implementation-only Live Coding, without another restart. **Normal DLLs need a normal build before the next cold launch** to include that final guard.
- No Git push requested or made for this turn. Unrelated training/recovery and other-agent changes were preserved.
- Compact receipt: [AttachmentPhysics20261014.json](../Tools/SwordHolster/AttachmentPhysics20261014.json).
- Full local evidence: `Saved/Diagnostics/HolsterAttachmentAudit20261014/`: live captures and metrics, native/refreshed-native reports, lifecycle results including retained failures, frame-rate comparison, profiler CSV/summary, build logs, graph snapshots and saved-map backup. Original hitch baseline: `Saved/Diagnostics/SheatheHitch20261014/`.
