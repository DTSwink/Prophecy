# Half-attack reach correction — October 8

`Enable Spine01 Compensation Half Attack` with **Compensate Position** enabled
now corrects the upper NN's target frame before inference. It previously turned
the completed upper pose toward the target while preserving an extension learned
for the hidden full-body attack, even when the running torso was much closer.

The lower ghost still predicts against the requested world target. After that
prediction, the current five parent-local spine rotations are placed on its next
pelvis. The real next published pelvis and the selected single/distributed spine
mount determine the corresponding real torso. Inverting this mount supplies the
upper NN with the real torso-to-target distance and direction. Its previous/current
upper history and all three pelvis samples use that same held-target frame.
The former extra post-prediction positional turn is removed. Existing pelvis
rotation compensation and spine distribution remain.

There is one existing upper inference, no new model, persistent pose history or
per-step heap allocation. Full attacks and position-compensation-disabled paths
retain their existing model path. The exact lower prediction is retained rather
than round-tripped through the changed upper frame. Attack-end preview reuse now
also checks the real mount, so a prediction cannot be reused after the torso moves.
Requested/effective target and lower ghost target readbacks remain the actual
requested world point; the virtual upper-only point is internal to inference.

This corrects the geometric input mismatch, not every learned prediction error.
The five-link estimate uses current local spine rotations; the upper NN can change
them in its next pose. No additional iterative inference or hand IK is used.

## Validation

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
