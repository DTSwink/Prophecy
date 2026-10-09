# Half-attack reach correction — October 8

`Enable Spine01 Compensation Half Attack` with **Compensate Position** enabled
corrects the attack target before inference. Both the lower and upper models now
receive the **same compensated target**. The correction is resolved once using
the current ghost pelvis and parent-local spine chain, the real next published
pelvis, and the selected single/distributed spine mount. The 30 cm minimum reach
clamp is applied around the real pelvis before inverse mounting.

All previous/current lower and upper histories, the predicted pelvis conditioning,
and both target heights share one held-target frame. The lower target is no longer
the distant original world point beside a nearby displayed upper target. The red
marker is the shared target consumed by the accepted prediction.

There is no additional model pass, retained pose history or per-step allocation.
The old post-lower upper-only rebase is removed. Full attacks and compensation-off,
zero-clamp calls retain the original numerical path. Preview reuse still validates
the real mount and settings and publishes its cached target only upon acceptance.
The shared target uses the **current** ghost pose because the next lower prediction
is not available before lower inference; it is not recomputed separately afterward.
This avoids circular target/pelvis dependence or an extra inference pass.

The initial October 8 implementation intentionally corrected only the upper model.
That lower-isolation contract and its test are superseded by the shared-target
change requested after the absolute195 investigation. See
[diagnosis and follow-up](GhostAttackLean20261008.md).

### Historical ghost target display caveat (fixed October 8)

Before the fix, `Visualize Ghost Attack` drew the raw ghost pose and original requested
target, translated together by World Offset. Its red marker/arrow is the lower
ghost's target, **not the adjusted upper NN target**. Thus the ghost-to-marker
distance can remain much larger than the real torso-to-real-target distance
while reach correction is enabled and working through the upper inference path.
`Get NN Attack Target` also returned that original point for all three outputs.

Both now use the accepted upper target cache. Requested remains unchanged;
Effective is the clamped real target and Ghost is the inverse-mounted upper target.

Pre-fix setup check: connected compensation node had Enabled/Distributed/Position
all true; runtime overR HALF at absolute177 reports all three flags1. Requested,
effective and ghost readbacks are identical `(16.810770,570.560788,145.109582)` cm.
Source confirms the HalfReach context feeds the upper inference independently of
these visualization/readback values. No change or fresh numerical reach-accuracy
claim from this check; owned replay ended, settings/source unchanged. Receipts
`Saved/Diagnostics/HalfReachReadback20261008/`.

This corrects the geometric input mismatch, not every learned prediction error.
The five-link estimate uses current local spine rotations; the upper NN can change
them in its next pose. No additional iterative inference or hand IK is used.

## Historical validation of the upper-only version

Eight focused native tests passed in the running editor: upper/pelvis mounts,
inverse reach, common attacker/target translation, coordinate-frame covariance,
four installed checkpoints' lower isolation, lower-only parity, ghost drawing,
inertia displacement and profile lifecycle. For identical input, corrected versus
uncorrected lower state and pelvis/leg transforms are bit-identical. Disabling the
correction restores the exact original model output in the native test.

Current physical jabR starts at **absolute tick 103**, Armed106, learned Hit114,
unchanged from the preceding diagnosis. Every captured physical bone position
through102 exactly matches that baseline. Closest authored right wrist-to-target
distance improves **15.2397 → 4.0852 cm**; physical wrist-to-target improves
**19.7819 → 14.8818 cm**. These are wrist joint distances, not collider gaps.
A separate owned replay records actual right-hand/head contact at world time1.9s
(absolute114), then115/118/119. The learned Hit flag and physical contacts are
distinct observations; the collision observer confirms contact independently.

Evidence and reproducible scripts: `Saved/Diagnostics/HalfAttackReach20261008/`.
The original comparison is `Saved/Diagnostics/HalfJabKick20261007/baseline.json`.
The later `before.json` in the new directory is a kick capture made while the user
had temporarily changed families; it is not used as the jab baseline.

## Independent kick inertia

**Set Ghost Loco Inertia Kick** uses the existing displacement algorithm with
Enabled=false / Duration Ticks=12 / Multiplier=1 defaults. See
`Docs/GhostLocoDrag.md` for override and reset semantics. General-enabled kickR
and kick-override-enabled/general-disabled kickR have exactly identical captured
physical player poses through180; Armed112/Hit118 in both. Explicitly disabling
both gives Hit120, establishing that the enabled comparison exercises the feature.
The kickL override replay also completes. Saved Blueprint tuning was not changed.

Final Live Coding cleanup build succeeded (122.43s, two units) and its expanded
inertia lifecycle test passed, including cancellation on kick-to-punch family edit.
Blueprint status3, no stale native properties/pins; authored graph unchanged.
Owned Play ended, audit/trace settings and original global build configuration
restored. No restart or asset save. Rebuild the normal DLL before a cold launch.
