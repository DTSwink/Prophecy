# Optional knee-pop smoothing

`Set Knee Pop Smoothing` takes Agent, Enabled and Soft Zone Cm (4 cm suggested).
The feature is off until explicitly enabled after NN pose-source initialization.
Disable it or set the zone to zero to remove its setting. There is no callback,
timer, retained pose history or additional inference; disabled calls skip the
extra bone traversal and math after a guard in the existing presentation path.

This is soft IK near maximum leg extension, for both legs during locomotion.
Normal attack, parry and dodge presentation bypass it. The exception is an
active attack-start pelvis inertia correction: smoothing runs once AFTER that
correction, with the same configured zone, and stops when inertia retires. Given current thigh/calf lengths `a,b`, reach `r=a+b`, soft zone `s`, and
hip-to-ankle distance `d`, there is no change below `r-s`. Above that boundary,
the desired distance is `r-s*exp(-(d-(r-s))/s)`. Value and first derivative match
at the boundary. The zone is capped at one quarter of the current reach.

Move the ankle directly toward the hip to this distance: this is the shortest
position correction to the softened reach. Reconstruct the knee on the same
bend side with both current segment lengths unchanged. Carry thigh/calf
rotations with the changed segment directions; preserve foot rotation and
shift the toe with the foot. The pelvis is unchanged. As requested, **the foot
may lift from the floor, including a pinned foot**. No floor-height constraint
is imposed. This prevents extension collapse; it is not a general time filter.

The locomotion correction runs after existing calf recovery/clamps on interpolated
presentation. The attack-entry exception runs after pelvis inertia instead.
Both paths are shared by rendered pose and physical targets. It does not edit
raw checkpoint outputs or recurrent state. While enabled, remember each leg's
reliable bend direction in thigh space at pose publication, refreshing it outside
the soft region. Carry it with the thigh and smoothly guide the extra knee bend
with it, preventing near-straight point noise or a reversed branch from being
amplified. Readers never mutate that reference. With no observable reference or
current pole, leave the pose unchanged rather than invent one. Disable/pose-source
reset/teardown removes both settings and reference directions.

## Reproduction and validation

The unchanged scene was captured in `CalfAnkleConnection-knee617-before.json`.
Possessed agent left PhysicalMesh knee bend at frames 617/618/619:
7.799 / 0.071 / 14.363 degrees. The interpolated target also collapses (0.018
degrees at 618): this is present before physics.

The native `Prophecy.NN.PhysicalTargets.KneePopSmoothing` test embeds those exact
three world-space samples. It checks reduced rebound, segment lengths, radial
displacement, foot rotation, toe offset, coordinate covariance, vertical legs,
disabled bypass and setting cleanup; it is also invoked by the existing recovery
calf regression so these checks run in a Live Coding session.

An initial radial-only prototype reproduced the desired 617–619 improvement but
amplified an existing near-straight right-knee branch reversal at 457–458. That
prototype is superseded by the stable thigh-frame direction described above.
Final Live Coding build succeeded in 88.03 seconds and loaded at 12:59:07 UTC
on 2026-09-24. AttackLegClamps and RecoveryCalfLength (including the new smoothing
checks) passed at 12:59:39. The new standalone test's registration is not exposed
by this Live Coding session; its same checks ran through RecoveryCalfLength.

Final unchanged-scene replay `CalfAnkleConnection-knee617-final4.json` covers 692
game frames. Left physical knee bend at 617/618/619 is now 22.204 / 21.683 /
23.528 degrees. The 618-to-619 rebound falls from 14.292 to 1.845 degrees (87%).
At 618 the ankle moves about 1.47 cm toward the hip, including 1.26 cm upward.
Raw previous/future checkpoint poses are identical across the entire replay.
Both target segment lengths remain unchanged within 9e-14 cm.

The final right-thigh steps at 457/458 are 5.82/2.06 degrees, versus baseline
6.68/7.51 and rejected prototype 19.70/24.25. Across this capture, the largest
increase over baseline in a thigh step is 2.17 degrees (left, frame54); this is
not a claim that every motion becomes slower or that all knee problems are solved.
Evidence: `Knee617-comparison-knee617-final4.json` and
`Knee617-final-whole-replay-check.json` under Saved/Diagnostics.

Final disabled replay (`knee617-final-disabled`) matches every captured mesh
position, quaternion and scale for all three agents across all 692 frames
exactly (maximum difference 0). Enabled replay's raw previous/future transforms
also match exactly. Receipt: `Knee617-final-equivalence.json`. Diagnostic Play
ended, tracing is off and Python capture memory was released.

The feature is left unwired/off in user assets. Include this Live Coding change
in the next authorized normal editor build before relying on a fresh process.

## Current Walk check, 2026-09-25

Read-only Blueprint dump shows tick debugging / K2Node_CallFunction_209: Enabled=true but SoftZoneCm=0.000000. Zero removes the smoothing setting, so this walk does not run the correction. Owned capture20–360 contains pure Walk/no attacks. Identical-prefix same-frame disable at320 changes both feet0cm and both knee bends0degrees (right5.51710685degrees before/after), confirming bypass. No gameplay changes or saves; diagnostic PIE ended. Evidence: Saved/Diagnostics/WalkKneeNow-verification.json and SwordThigh/BlueprintGraph.txt (fresh read-only dump).
