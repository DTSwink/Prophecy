# Hook L / Dodge comparison — 2026-09-17

## Current implementation

Defense still waits for the attack NN's **Armed** output. Waiting requests capture the two completed defender poses before the next policy update. Activation consumes the Armed attack frame in that same policy step. Locomotion/attack ownership remains free before Armed; there is no early defense inference or hidden warmup.

Kinematic Parry/Dodge termination now queries the **actual PHAT shapes and held sword simple collision**, independently of training colliders. Punches use the striking forearm/hand bodies; kicks use calf/foot/ball; headbutt uses head; weapon attacks use the held sword. Eligible defender shapes come from its current pose-reference mesh's physics asset and held sword. Selected Parry blockers still take precedence only when contact occurs before harmful contact. The sweep follows both translation and rotation between policy poses, using authored spheres, capsules, boxes and convex hulls with no training enlargement. Sim/HalfSim continue to leave collision stopping to gameplay Hit events.

Training conditioning still uses the original six-entry enlarged attacker catalog. Do not replace it with PHAT geometry: that would change checkpoint inputs. Collision-query shapes are prepared only for active kinematic defense and retained for that episode. No additional physics bodies or simulation world are created.

## Identified mismatches

1. The UE attack input formerly used defender-specific added hand/foot boxes and reconstruction. Corrected to training's raw lowerarm attachment for punches, calf for kicks, head for headbutt, and blade for sword/pike. Original training size factors remain 1.5 and blade transverse factor 2. Exporter: `Tools/NN/ExportDefenseAttackerGeometry.py`; native attachment fixture passes 90 samples, maximum error 8.94e-8.
2. UE formerly generated its first defense output one frame after Armed. Corrected to the Armed frame with aligned previous/current history. Current Hook L Arms at frame 5; the first defense output is now frame 5 rather than 6.
3. The old kinematic stop used enlarged training contact volumes, ending the response at head contact even when the visible hand missed. At the user's request, stopping remains enabled but now uses authored PHAT/sword collision.

## Updated viewer and numerical comparison

The viewer was subsequently corrected by the user to start on Armed and use training conditions. Earlier results from the viewer's frame-2 activation are obsolete; they must not be used to dismiss the UE mismatch.

The one-frame timing error matters even if an enlarged collider still records a hit: with the viewer's same initial pose and attack, delaying the first output from Armed to the next frame reduced head lowering near contact from about 7 cm to 2 cm.

Exact captured UE state/inputs replayed through the original Python networks match native execution. Across the seven-frame autoregressive comparison using the same saved native geometry, maximum joint-position difference was **0.000526 mm**. The temporary viewer's different skeleton fixture caused a separate decoder comparison discrepancy; using the original accepted native fixture removes it. Do not replace native geometry with a temporary viewer fixture to force a visual match.

The live UE upper-body starting pose is different from the viewer's idle primer and produces a shallower duck even in Python. Swapping the initial upper pose changes the duck much more than swapping the incoming attack. Identical checkpoints do not imply identical trajectories with different recurrent initialization.

Evidence under `Saved/Diagnostics/DodgeMismatch`: `timing_normal_ue.json`, `timing_continue_ue.json`, `input_isolation_first5_native.json`, `native_geometry_replay.json`, `updated_viewer_82.json`, and the comparison scripts. `NativeTraceBeforePHAT` preserves the pre-PHAT-stop trace.

## Validation and installation

Focused geometry regression: `Prophecy.NN.Defense.PhysicalContactShapes` checks an empty capsule corner, actual surface contact, fast crossing, a near miss, equal translations, rotating sword contact, and scale without enlargement. Runtime capture scripts `capture_phat_normal.py` and `capture_phat_parry.py` exercise the current saved scene in disposable PIE.

The new exported query helper crosses the Jolt/game module boundary. Live Coding compiled it but could not link the new imports, requiring a normal build and one editor restart. This does not change the normal preference for Live Coding. Blueprint/map and training/viewer files are unchanged.

Focused checks passed. The current saved first Hook L Dodge consumes frames5-14 without a PHAT hit; the former training-box stop was frame8. The same setup in Parry still detects head contact and stops on frame8 after four steps (contact time0.119132593s). The shared Dodge frames5-8 match pre-change NN inputs, outputs, positions and rotations exactly (maximum difference0). This verifies the stop-only change without changing the learned motion. Evidence: `phat_normal_ue.json`, `phat_parry_ue.json`, `phat_input_comparison.json`. Editor left open on testNN, PIE off, no dirty maps/content, diagnostics off.
