# D/S native port and Sim release investigation — October 10, 2026

## Result and important limit

The post-sheathing wrist runaway is fixed in the tested saved tick25 Sim sequence. It was a feedback loop between the procedural upper-body pose and NN recurrence, not a PHAT angular-limit problem. In the final saved15% sequence, sheath-return hand tracking error peaked at0.2073cm, compared with about13.5cm before isolation. The initial complete S/D cycle reaches Holstered at161 and Held at284.

This is **not a claim of perfect motion or universal reachability**. With the saved15% shrink and45-degree body limits, the current true kinematic starting pose and a second Sim sheath can remain roughly4–6cm short. The live NN pose differs from the lab's recorded idle/walk clips. Increasing speed cannot remove that geometric shortfall. Saved tuning was preserved;25% shrink was used explicitly in isolated PIE tests to verify the mechanics with reachable geometry. Those temporary values were never saved into the Blueprint, JSON profile or lab.

## Measures taken

1. Read the project handoff and sword contract; preserved the current Blueprint wiring, assets, tuning and unrelated work. Earlier checkpoint commits4fbd4dc/9dae6c03 already contain the lab, user assets and scripts.
2. Ported the lab controller into `ProphecySwordHolsterPose`, reading a live NN base and publishing the same accepted upper-body target to visual and physical consumers. Added the corresponding single-bone target path too.
3. Removed the previous manager's per-sample Cartesian hand-path IK and its commit of the authored arm back into upper NN recurrence. Reaching now samples parent-local FK interpolation; solves generate destinations and sparse sliding guides.
4. Kept the NN's locomotion clock running normally. D/S curves remap only the procedural reach/slide channels, as authorized.
5. Imported all four independent monotone curves: D reach, S reach, D sliding and S sliding. The four interior points and endpoints match the lab's Hermite interpolation.
6. Imported the complete body/head/FK-return profile through `Set Sword Holster Lab Profile`, before the existing profile and Draw Sword calls in the saved tick25 Blueprint chain. The five existing numeric literals now match the captured lab checkpoint:15, .5,250,2500,150. All other graph wiring/defaults are preserved.
7. Staged the profile JSON as a runtime dependency so the native port does not depend on an untracked local lab state file. Explicit configuration caches parsing across agents and invalidates the cached profile on file timestamp changes.
8. Retained axial-only shrinking, the authored asset scale exactly once, the blade-base mouth pivot and the same sword actor throughout transfers. No global physical-asset or sword-asset retuning was used to hide symptoms.
9. Sized FK reach duration from sampled wrist displacement and joint/wrist rotation, respecting both maximum reach knobs for the reference transition.
10. Ported spine twist, two-axis clavicle swing and shoulder-distance fitting. Pelvis is untouched; lower spines retain their NN motion with20/40/60/80/100% net correction. Live target refits are rate bounded. Drawing waits for the body turn; S clavicle releases from its actual slide-entry correction as insertion advances.
11. Ported mouth-directed head look, alpha, separate in/out angular speeds and sigmoid exponents, independent D/S look-out thresholds and the neck's1/3,2/3,full-head sharing. Head time is independent of curve modulation.
12. Ported independent D/S FK returns at slide completion, including local/world inertia, ordinary/spring return, easing, duration, hold/decay, angle-added time, bone weights and upperarm axial-inertia removal. Head return and FK return use their own clocks.
13. Corrected tiny quaternion rotation-log calculations so small angular velocities are retained instead of being lost by axis/angle extraction.
14. Diagnosed the release problem by separating raw NN, presented target and physical hand transforms. Temporarily freeing arm angular limits did not improve it. Isolating upper feedback at return reduced the error; isolating the entire action removed the contaminated incoming wrist target too. Diagnostic PHAT/tolerance changes existed only in owned PIE instances.
15. During active D/S, retain the exact upper NN recurrent pair instead of feeding the authored physical upper pose back into it. Lower feedback remains unchanged. Refresh the prior-physical upper baseline so restoring normal feedback does not use stale procedural history.
16. Apply that isolation consistently in legacy serial, prepared serial and parallel feedback paths. Workers receive immutable flags; they do not query actors or controller maps. Skip upper encoding/tolerance work when its result would be discarded.
17. Keep exactly one reusable temporary grip joint. Avoid updating unchanged grip frames every tick. Five repeated calls during sliding leave the joint generation, count and transfer state unchanged.
18. Remove the extra physics-publication wait at slide completion. Joint destruction and parenting now occur on the same authored endpoint that starts FK return, rather than leaving the joint alive into the first return tick.
19. Keep right-arm collision suppressed through reach, sliding and return; restore the underlying settings at completion and cancellation. Left arm and torso are unaffected. Verified actual native responses across19 exposed channels.
20. Make the holster follow the pelvis in kinematic mode. Restore its prior attachment/simulation preference when switching back to Sim. Verified restoration for60 further ticks without the holster falling away.
21. Retire the pose overlay and its presentation ownership as soon as FK/head finish, even if drawing is still unshrinking. This lets ordinary NN presentation resume during long unshrink intervals.
22. Count unshrink in integral authored ticks. A3-second test exposed the old float accumulation completing at181 ticks; it now completes at180. Zero-duration unshrink is applied at the actual parent handoff.
23. Use60 unpaused ticks per authored second. Pausing leaves feature state unchanged. Head/FK timing never inherits reach/slide curve acceleration.
24. Stop completed pose clocks and work. Remove per-agent output caches and expired weak keys during teardown. Reuse scratch arrays and retain only two rolling spring integration frames rather than a whole per-agent spring pose bank.
25. Verify kinematic and Sim cycles, repeat transfers, duplicate requests, cancellation in all three active phases, mode restoration, long/zero unshrink and moving locomotion. Distinguish reachable diagnostic fixtures from the saved15% geometry rather than claiming a stalled case passed.
26. Add reproducible native math/feedback regressions and a non-saving owned-PIE driver. All test-generated pose captures remain under Saved; compact results are included in the tracked receipt.
27. Preserve user packages before required native builds, use Live Coding for the intermediate implementation patch, verify compile **and** reload, and perform actual Play after the new admission-path crash was corrected to use validated `GetPoseReferenceMesh()` rather than the unused mesh pointer.
28. Audit the entire agent/sword Blueprint graph after the final cold launch: exact match with the saved imported graph, status3, zero stale native properties/pin types. The user TestNN save and original A_Sword bytes remain preserved.
29. Keep unrelated ONNX picker downloads and the PDF out of staging. Push only the intended source, profile, Blueprint/map, scripts and documentation.

## Evidence

`Receipt20261010.json` contains final test outcomes, timings, metrics, hashes and the procedural benchmark. Full raw captures/build logs are local in `Saved/Diagnostics/SwordLabPort20261010/`.

- Seven isolated native Automation tests pass. The new isolation test exercises100 mixed active/inactive lanes and release across serial/parallel paths, checking the exact upper recurrent pair and unchanged lower feedback.
- Native math checks cover4 idle/walk × D/S cases and32 return combinations. Maximum differences: curve3.33e-16, body1.24e-16 radians, reach duration1.34e-14 seconds, head0.0000593degrees, FK return0.00000725degrees /0.00000437cm.
- Saved15% sequence: S reach68, slide-end/release99, return complete161; D reach191, slide-end/reparent222, completion284. The lab's different recorded base gives different reach ticks; slide and independent return durations use the same authored contract.
- Reachable25% repeated-cycle checks: Sim completion279/528 and kinematic280/529, with27-tick slides and62-tick FK returns in these fixtures. Kinematic target/mesh error is numerical roundoff. The Sim test verified492 suppression frames and restored collision at both endpoints.
- Straight walking also passes:433.61cm pelvis travel in Sim and446.37cm kinematic. The first diagnostic mistakenly refreshed direction from the rotating actor every tick; it was corrected to a fixed world direction before these checks. No physics tuning was changed for that test error.
- Actual3-second unshrink now ends at218+180=398; zero-duration scale is1 on the handoff frame218, while FK return continues independently through280.
- Cancellation during reach, slide and FK return clears the temporary joint and restores contacts. Paused feature reports are unchanged. Mode restoration kept holster-to-pelvis distance near42.55→43.54cm after60 ticks.
- Final100-agent procedural-only benchmark: approximately0.84–0.87ms mean per tick and4.18–4.41ms synchronized-fit peaks. Includes the actual procedural update; excludes admission fitting, NN reads/inference, cache publication, rendering and physics. This is not a whole-game FPS result.

## Reproduce

Run `node Tools/SwordHolster/export_parity.cjs`, then `Tools/SwordHolster/RunParity.ps1` against current normal DLLs. The latter launches a separate headless test process.

For actual Play, use the configured Python with `Tools/RunUnrealRemote.py Tools/SwordHolster/VerifyPlay.py`. Options include `--kinematic`, `--walk`, `--repeat 2`, `--pause`, `--cancel-phase 1|2|4`, `--unshrink 3` and `--switch-back`. `--shrink-percent 25` explicitly enables the temporary cancel/re-equip diagnostic fixture. The driver refuses an existing Play session, never saves assets, cleans up only the Play session it created and writes its result under Saved.

Movement quality still deserves human playback inspection. Numerical agreement and stable tracking do not establish that every pose, clearance or aesthetic choice looks perfect. The unresolved saved-profile reach limitation above is real and must not be described as a physics stall or hidden with silent tuning changes.
