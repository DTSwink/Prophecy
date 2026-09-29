# Upper inertia and right-hand velocity at attack exit — September 29

Superseded by the implemented [arm/hand inertia extension](UpperBodyInertia.md): the current rollout now preserves the first exit's complete hand velocity and the two competing Blueprint enables have been disabled. The diagnosis below records the previous implementation.

Diagnosis only. Two bounded 235-tick owned captures ended normally; no gameplay source changes, Blueprint edits, compile or full suite. The user configured response 80000, hold 1 second, blend 0.5 seconds, momentum 1 in the upper-end event.

## Finding

`Set Attack Upper Body Inertia` currently implements FK-core angular inertia, not complete upper-body or hand velocity continuity. `ProphecyUpperBodyInertia::Begin` captures only world quaternion/angular velocity for `UpperCoreBoneNames`: spine_01–05, neck_01–02, head, clavicle_l/r. It does not capture the upper-arm, forearm or hand angular velocities, hand translation velocity, or core translation velocity.

On each returning locomotion step, `CorrectLocomotionHands` first decodes the normal upper checkpoint's predicted arm pose. Core inertia then updates the ten core rotations. `CarryCoreArm` attaches that already-predicted arm pose to the modified clavicle. Consequently, torso rotation continues while the arm's motion relative to the clavicle comes directly from locomotion. No outgoing attack hand velocity is used to reconcile these two contributions. Larger Response only weakens the angular spring's damping/attraction; Hold keeps ownership of those same core channels. Neither adds missing arm momentum. This explains continued rotation with a discontinuous hand trajectory.

## Current Blueprint wiring

The new disable-return node (`EventGraph / K2Node_CallFunction_250`) and inertia setter (`251`) are reached, but their execution then continues through `K2Node_Knot_29` into the older hand-tempering setter (`203`, enabled/all zero), its 0.5-second return blend (`204`), and the older **enabled** arm-return setter (`157`, speed400/blend1). Thus the saved live graph still re-enables those controls later in the same callback. Core tempering setter224 is disabled as intended. The graph was inspected without modifying it; see `Saved/Diagnostics/Knee202/upper_inertia_graph.txt`.

## Measurements

Current natural exit is tick191. Future target velocity, using 30 Hz sample differences across world ticks188→190 and190→192:

| Setup | Last attack hand vertical velocity | First locomotion hand vertical velocity |
| --- | ---: | ---: |
| Current graph | −300.65 cm/s | −157.97 cm/s |
| Hand/core tempering and arm return actually disabled | −300.65 cm/s | −579.98 cm/s |

The current graph loses roughly half the downward speed, rather than literally setting it to zero. Physical-hand motion follows the target discontinuity. The isolated case still has a discontinuity, in the opposite direction, proving that simply bypassing those nodes does not provide velocity continuity.

For isolation, the diagnostic called Stop at tick190 after the last outgoing NN sample, one world tick before natural exit/next NN evaluation, then disabled hand/core tempering and arm return after the Blueprint callback completed. The outgoing attack pose and motion matched baseline. Inertia retained the user's response80000/hold1/blend0.5/momentum1; locomotion clamp configuration was retained. This is a controlled handoff comparison, not an identical event-clock replay.

Decomposing hand world displacement into clavicle translation, clavicle rotation, and motion relative to the clavicle makes the missing channel explicit. The outgoing relative-arm contribution to vertical velocity is −113.40 cm/s. On the first isolated locomotion sample it becomes −304.51 cm/s. In the unmodified graph it instead becomes +117.49 cm/s. The corresponding arm-relative horizontal contribution changes from approximately +512.69 cm/s in Y to −80.84 cm/s isolated (−39.01 current graph). These changes are not constrained by the upper-core inertia node.

The appropriate implementation change, if requested, is to extend exit inertia to preserve the arm/hand's outgoing motion as well, with a consistent reference frame and constraints. Merely increasing the existing Response/Hold, or renaming it, cannot solve the hand-velocity handoff. Exact continuity must also account for locomotion clamps and changed FK offsets; this investigation does not claim those secondary effects were removed.

Evidence: `Saved/Diagnostics/Knee202/upper_inertia_current.json`, `upper_inertia_isolated.json`, their `_nn.jsonl` files, `upper_inertia_analysis.txt`, and `upper_inertia_graph.txt`. Capture helpers: `CaptureHand180.py` (baseline copied to the current tag), `CaptureUpperInertiaIsolated.py`; analyzer: `AnalyzeUpperInertiaExit.py`. The earlier hand180 baseline was restored from its matching previous-turn audit capture to keep the prior diagnosis files intact.
