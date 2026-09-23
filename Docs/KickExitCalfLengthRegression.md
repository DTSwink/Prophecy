# Kick-exit calf length regression — September 23

Confirmed in the current kinematic kickR setup. No gameplay code or Blueprint
wiring was changed during diagnosis. The new Walk foot-rotation node has no
execution connection in the audited graph and is not responsible.

At the second kick exit (3.333333 game seconds), left calf-to-foot target length
is 47.56334 cm, then 45.01230, then 42.56340 on successive game ticks. The first
new locomotion publication already requests 42.56335 cm. Kinematic physical
positions match that target; this is not a physical solver issue.

The clamp snapshot blend is still running correctly: calf leeway is 20 at exit,
19.99 at tick1, 19.94 at tick2, 17.19 at tick15, 11 at tick30, and 2 at tick60.
The foot clamp blends toward its saved disabled setting. These allowances do not
force elongation, and cannot recover length already removed upstream.

`ApplyOutputBatch` builds `FPelvisLegGeometry` for tempered/regional reconstruction
with the reference calf length (`LocalOffsets[Limb.End].Size()`). It solves the
calf at exactly that length even while the clamp allowance is generous. Pelvis
inertia geometry likewise uses reference length. The earlier outgoing-length
capture/recovery was removed with the extension-only NN correction when installing
checkpoint123793. Removing that correction during attacks was justified by the
new checkpoint's symmetric range; removing recovery-length continuity also exposed
this exit regression.

An isolated reconstruction-disabled comparison eliminates that specific left-calf
collapse (47.56334 → 47.31762 → 47.12843), but severely breaks the kicking right
leg. Disabling reconstruction is not a fix. Any correction must preserve coherent
knee reconstruction while carrying outgoing calf length through recovery, including
compression supported by the new checkpoint. Do not reinstate the old attack-time
extension-only projection that could lower planted feet.

Evidence: `Saved/Diagnostics/CurrentKickLengthDiagnosis.json`, captures
`KickFootSnap-currentRotation.json` (15 exits),
`KickFootSnap-currentRotation-no_reconstruction.json` (4 exits), and
`KickFootSnap-currentRotation-profile.json` (4 exits). Capture script:
`CaptureCurrentKickRotationLength.py`; summary: `SummarizeCurrentKickLength.py`.
All diagnostic Play sessions were owned and ended; transient changes were discarded.

## Repair and bounded validation

Kick exit now captures the two actual outgoing calf lengths, including negative
differences from rest. The existing physical-leeway return clock fades those
differences to zero. Tempering/regional and pelvis-inertia reconstruction use the
same effective length. A recovery-only interpolation correction preserves the
ankle position and orientation while resolving the knee and segment aims on the
existing bend side. This avoids restoring the old attack-time foot projection.
No new timer/inference, reflected node, agent layout, attack-family heuristic or
knee-pole rule was added. New specials/reset/completion remove recovery state.

Gameplay patch25 compiled in273.65s and loaded18:35:46UTC. Six focused tests passed
18:36:07UTC, covering signed length math, lifecycle/tick durations, ordinary attack
clamps and the Walk rotation feature. Blueprint status3, zero stale types.

Identical24-second kinematic capture completed15 kickR exits. Maximum physical
calf-length change over the first two recovery ticks is0.016285cm left and
0.006254cm right (previously about5cm). Physical lengths follow the60-tick smoothstep
curve within0.004708cm left/0.002168cm right across the captured windows. The second
exit's left sequence is47.4545→47.4505→47.4386cm; it starts at the actually displayed
outgoing length, rather than the later raw30Hz endpoint. Physical compression
constraints remain unchanged; this is kinematic scene validation.

The first replay also exposed a diagnostic API gap: single-bone authored target
reads applied the old foot-only correction and omitted the newly corrected knee,
although full-pose/animation/physical consumers agreed. The follow-up getter patch
uses the same complete leg during active recovery, retaining the ordinary path
otherwise. The raw previous/future publication outputs remain raw; the interpolated
target reports the corrected pose.

Patch25 evidence is preserved in `KickFootSnap-currentRotation-patch25.json`.

Getter patch26 compiled in184.84s and loaded18:42:33UTC. Final7-second capture
completed4 exits (3 complete60-tick windows). Both signed returns pass numerical
curve checks: maximum target error0.003929cm left/0.001689cm right; target versus
kinematic physical length differs by less than0.00065cm. The captured second
exit exercises a shortened right calf returning40.51→42.56cm as well as an
extended left calf. Largest two-tick target-length change is0.015546cm left and
0.006688cm right. Completed paths retire state; no graph edits, asset saves or
restart. Final diagnostic Play ended. Evidence:
`KickFootSnap-currentRotation-verified.json`,
`CurrentKickLengthRecoveryComparison.json`,
`CompareCurrentKickLengthRecovery.py`. Native checks are queued by
`VerifyKickLengthRecovery.py`. Patches need incorporation in the next authorized
normal editor build.

## Remaining visible snap: render scale, not segment distance

The user's follow-up correctly identified a gap in that verification: joint-centre
length continuity did not cover visible calf-tip continuity. A direct evaluated
`PhysicalMesh` capture found locomotion's `ExtendCalfToFoot` scales the calf
uniformly on the first recovery publication, whereas attacks leave its authored
scale unchanged. At the second exit, scale X jumps1→1.1066006 (YZ1.12→1.2393927)
and a4.5411cm calf-tip/ankle gap closes in one tick, despite a smooth calf length.
This explains why the previous target/physical-centre measurements passed while
the user still saw snapping. They must not be cited as proving render continuity.

The recovery now keeps the authored calf scale instead of invoking the ordinary
locomotion stretch during the finite length return. Axis alignment remains; the
existing signed length curve closes the gap. At completion the calf is back at
rest length and ordinary locomotion stretching resumes. No new blend, timer,
checkpoint change or knee-guidance change is introduced.

Direct mesh evidence: `Saved/Diagnostics/CalfAnkleConnection-before.json`,
captured by `CaptureCalfAnkleConnection.py`, measured by
`AnalyzeCalfAnkleConnection.py` against the reference foot offset transformed
through the evaluated calf's world rotation and scale. This includes the user's
authored transverse scale1.12 rather than assuming uniform scale.

The authorized save/restart incorporated the recovery and render fix into the
normal Editor DLL: 24 build actions succeeded in247.24s. The pose Blueprint was
saved before closing; `/Game/testNN` reopened without graph changes.

Post-restart direct mesh capture completed six kick exits, with five complete
60-tick recovery windows. Both calves retain exactly the same evaluated scale
through each return. Maximum first-tick left tip-gap change fell from4.907983cm
to0.004045cm (right2.051872→0.001691cm). Maximum change anywhere in the return
was0.122654cm left/0.051278cm right, consistent with gradual gap closure rather
than one-tick scaling. All five windows finish within0.02cm of the ankle.
`CompareCalfAnkleConnection.py` asserts entry scale/gap continuity, scale stability
through the return, and final convergence; all assertions passed. Evidence:
`CalfAnkleConnection-after.json` and `CalfAnkleConnection-comparison.json`.
This validates the current kinematic setup, not every possible pose or dynamic
collision. Diagnostic Play ended and capture memory was released; Unreal remains open.
The six focused recovery/clamp/rotation/60-tick regressions also passed against
the normal DLL at19:07:52UTC. Pose Blueprint inspection reports status3, zero stale
native properties/pin types and preserved wiring.
