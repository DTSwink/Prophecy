# High-magnetization crash containment

The reported joint-rotation crash is guarded. The actual tenfold-magnetization character regression also exposed a finite-position broadphase overflow; that path is now guarded before a shape crosses Jolt's numeric bounds. Unreal stays alive, retains the last published pose and refuses further simulation steps after a numerical fault. Stop Play and start a new simulation to reset it. Requested strength, PHAT settings, CCD and backend selection are unchanged.

## Implementation

- Pinned Jolt 5.6.0 source patch: `Tools/Jolt/Patches/NumericalSafety.patch`, SHA256 `38D9BC1F0E9F288486689398E13BC50227300E258171B72FE2EDC6E28B4B4F09`.
- Position and rotation corrections validate before mutation. Point constraints preflight both endpoints. Rotation corrections above 10,000 radians use double norm/scalar trigonometry to avoid float-norm overflow and SIMD quadrant-reduction failure; ordinary calculations keep the original path.
- Candidate transforms check the full shape against Jolt's actual `+/-cLargeFloat` broadphase range, including shape offset, rotation and outward float rounding. This fixed the additional crash reproduced in `EditorFirstStressCrash.log` / `Saved/Crashes/UECC-Windows-CB3EDC2F436FC7BAA9CE9F8E521933F7_0000/`.
- Solver-velocity writes and clamps reject nonfinite or overflowing values before their former assertions. Sticky failure flags fit an unused Body bit and existing MotionProperties padding; native size checks compile in both configurations.
- Failed endpoints stop solving. Workers still finish batches and release dependencies. Later collision substeps deactivate bodies and skip listeners, then return `EPhysicsUpdateError::NumericalFailure` (bit 3). Unrelated native assertions retain their original policy.
- `UProphecyJoltWorldSubsystem::Step` catches the result before sample capture/publication and faults the shared world. The existing character coordinator stops every registered client and retains the last published pose.
- `BuildJolt.ps1` applies and verifies the exact patch without overwriting unrelated source changes. UBT verifies patch, DLL and import-library hashes. Editor staging keeps matching native copies in both plugin and project executable directories, preventing a stale monolithic-build DLL from shadowing the selected library.

## Verification

`result.json` records **78/78 successful Jolt automation tests**, including all three native numerical-safety tests and the real-character high-gain test. `Automation.log` and `EditorSafety.log` preserve the actual run.

| Real 22-body / 21-joint character | Result |
| --- | --- |
| Gain 1, 60 Hz | 360/360 steps; active movement; finite pose and velocities |
| Gain 1, 30 Hz, two collision substeps | 360/360 steps; active movement; finite pose and velocities |
| Gain 10, 60 Hz | Safely stopped after 13 completed steps; failed step not published |
| Gain 10, 30 Hz, two collision substeps | Safely stopped after 6 completed steps; failed step not published |

Each high-gain fault retains the requested gain and passes three repeated-step rejections, unchanged published pose/revision, native failure diagnostics and ordinary ownership cleanup. These are moving authored-target fixtures with two workers, not a claim that extreme strength is stable or visually usable.

Native tests verify exact ordinary quaternion results, huge finite rotations, invalid/overflowing corrections and shape-edge bounds. Thirty-six worker cases cover positive controls plus position and velocity fault injection, 2/160 connected bodies, one/three substeps and actual large-island splitting. Workers return, callbacks stop on later substeps, poses/velocities stay finite, and teardown succeeds.

Build evidence:

- Final Development native build: `NativeBoundsBuild.log`.
- Final Shipping native build: `NativeShippingBoundsBuild.log`.
- Normal Editor build: `EditorBuild.log`; corrected staging: `EditorStagingBuild.log`; final runtime bounds build: `EditorBoundsBuild.log` (35.76 seconds).
- Two final shape-edge test cases were added after the normal build and loaded with a successful one-file Live Coding patch in `EditorSafety.log` (07:00:34 UTC). Production protection is in the normal Editor/native binaries. The normal build now uses the consistent `WITH_LIVE_CODING=1` configuration.

Ten logged test warnings remain: the existing disconnected sword Blueprint warning, shared transient-world teardown warnings, and the two expected contained-fault warnings. No assertion suppression or warning-free claim is made. Shipping native compilation passed; no new packaged runtime or performance test was performed.

At handoff Unreal is open on `/Game/testNN`, outside PIE, with no dirty maps/content (`result.json`). The original crash investigation remains in `Investigation.md`; its initial no-fix statement describes that earlier investigation only.
