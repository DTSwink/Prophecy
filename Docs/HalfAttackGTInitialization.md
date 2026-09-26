# Half attacks: independent current-agent ghost

## Current contract — September 26 evening

**Trigger NN Attack / Half Attack = true** now initializes the entire ghost from
the current agent's full-body pose and previous world-space pose, using the same
encoding as a normal full attack. Its initial carrier is the agent's carrier;
there is no target-facing reseed or GT Armed lower-body replacement. The explicit
Static initialization option still duplicates the current history frame.

The attack then advances its own history in that fixed carrier. Real locomotion
continues independently. Half-mode hand-inertia corrections remain presentation
corrections and are no longer written back into the ghost history. There is no
extra inference, physics simulation or inactive recurring work.

The ghost's target is always the exact requested **world-space target**, including
updates through Set NN Attack Target or an active Trigger NN Attack. There is no
pelvis-relative target remapping and no half-attack radius clamp. Requested,
Effective and Ghost outputs of Get NN Attack Target now agree. The old global
half-target-radius nodes remain available for Blueprint compatibility but no
longer affect attack targeting; their retained tooltips describe the old behavior.

Only the spine_01 subtree is still mounted onto the real pelvis using full
pelvis-relative position/rotation. Real pelvis/legs remain locomotion-owned.
Consequently the independently aimed ghost and the mounted real hand can differ
in world position as the real agent moves. The exact-world-target guarantee is
for the ghost policy, not a guarantee of physical hand contact.

Active retriggers and half/full ownership switches retain history, phases and
frame count. Stop then Trigger starts fresh. Half kicks remain rejected. The
existing half-to-full rejoin uses the current locomotion carrier.

Recovery now follows [regional ownership](RegionalSpecialRecovery.md): ending a
pure half attack emits Upper Special Ended only. Full-to-half emits Lower Special
Ended at the switch, starting leg recovery while the upper attack continues.
Half-to-full reacquires the legs and both events fire at completion. Pure half
entry/exit does not clear/restart leg recovery or recenter the locomotion root.

The visualization below still draws the ghost and its actual target, both shifted
by World Offset. Use zero offset to compare the red marker with the real target.

Live Coding compiled successfully (98.88 seconds) and loaded **20:45:16 UTC**.
The owned moving/turning-agent capture covered hookL, slashR, headbutt and pike,
including a world-target change at frame 5 beyond the former 125 cm clamp.
Requested/Effective/Ghost query outputs agreed exactly; decoded policy target
error was at most 0.000068 cm. Initial pelvis/feet/hands matched the captured
agent pose within 0.000059 cm. Across subsequent samples, all 262 recurrent
history values matched the preceding ghost input/output exactly.

All four attacks reached Armed and Hit. Anatomical hip-heading spans were
67.52, 209.15, 57.78 and 94.73 degrees respectively: no full spinning revolution
in these bounded captures. SlashR still turned back and forth before Hit; this
does not claim all model-generated motion is ideal. Measure heading from the
hip line, not pelvis-bone Euler yaw (its near-vertical axis creates singularities).
The pre-change baseline showed headbutt/pike exceeding nine net revolutions and
ghost/requested target separation up to 543.56 cm. Since initialization changes
the rollout, those totals are observations, not a same-prefix causal comparison.

The separate lifecycle capture passed all 14 supported families, fresh frame-1
entry, idempotent and half/full switches, active-trigger retargeting without
phase reset, and rejection of invalid/half-kick replacements without disturbing
the running attack. Owned Play ended, tracing was disabled; no assets were
saved, no editor restart or push occurred. User visual acceptance is pending.
This remains a Live Coding patch until the next normal editor build.

Evidence: Saved/Diagnostics/IndependentHalfGhost/{baseline,fixed}-trace.jsonl,
{baseline,fixed}.json, fixed-summary.json and lifecycle.json. Reproduction:
Saved/Diagnostics/TestIndependentHalfGhost.py, AnalyzeIndependentHalfGhost.py
and TestIndependentHalfLifecycle.py. The old GT exporter/cache file and legacy
paired-test switches are historical tooling, not normal half-attack inputs.

## Superseded GT initialization and target mapping

The following initialization, radius-clamp and target-remapping rules describe
the earlier September 26 implementation. They are historical, not current.

Updated 2026-09-26. Use the existing **Trigger NN Attack** node with
**Half Attack = true**. No new Blueprint node or per-frame Blueprint work is needed.

## Starting a half attack

The separate attack history now starts its lower body at the original animation's
**Armed** frame, with its previous lower body at **Armed − 1**. These are actual GT
controller rows, not an idle approximation or a pose copied from the moving agent.
Both rows use the GT Armed root frame, preserving original lower-body velocity.

The current upper pose, relative to the real pelvis, initializes both upper history frames, transported through
the corresponding GT pelvis. This deliberately avoids importing the runner's
previous upper/lower locomotion velocity. The physical mesh is not teleported;
only the data-only attack ghost receives the GT lower body. Real legs and pelvis
continue their own locomotion NN and mover.

Each new half attack gets a target-facing ghost frame. Only `spine_01` and its
descendants are grafted onto the real agent, using the shared skeleton's parent
indices. The graft is `ghost bone relative to ghost pelvis * real pelvis`, including
both position and rotation. The real pelvis and legs remain locomotion-authored.
This preserves the ghost's spine-to-pelvis pose instead of freezing torso orientation
in world space while the real pelvis turns. Initial upper seeding uses the inverse
mapping, so the first graft reproduces the current real upper pose.

The ordinary radius-limited world target is transformed through that same full
pelvis transform into the current ghost pelvis frame. Turning the real pelvis
therefore changes the ghost's target appropriately. Pelvis-relative target and pose
mapping are inverses; target radius, inference schedule and phase rules are unchanged.

The lower ghost, neural inference and Armed/Hit decisions remain self-fed. GT
Armed is an initialization pose, **not a forced Armed signal**. No extra model
evaluation, physics step, camera component, smoothing or phase delay is added.

## Source data and cost

`Tools/NN/ExportProphecyHalfAttackGT.py` reads the accepted Slash checkpoint recipe's
original-family controller-v3 clips. It verifies Armed/fps against the corresponding
original animations in Stepper's `training/slashes2/final_gt_attack_dataset_npz`.
It writes `Content/locomotion/NN/prophecy_slash_half_gt.json`, including source
hashes and explicit coordinate/bone metadata. The source animations and weights
are unchanged. The JSON is declared as a UFS runtime dependency for packaging.

| Family | Previous / current GT frame, zero based |
|---|---|
| Hook L/R, Jab L/R, Over R | 4 / 5 |
| Headbutt, Over L | 6 / 7 |
| Pike | 8 / 9 |
| Slash L | 9 / 10 |
| Slash LD / LU | 12 / 13; 11 / 12 |
| Slash R | 15 / 16 |
| Slash RD / RU | 14 / 15; 13 / 14 |

Data is loaded into one shared immutable cache on first use. Per-trigger work is
two small pose encodes and copying the GT lower rows. Ongoing work reuses the
existing attack batch and upper-pose publication. Legacy quaternion storage is kept
unused for Live Coding layout compatibility. Half kicks remain rejected.

## Existing mode switches

**Set NN Half Attack Enabled** changes an attack already in progress without
resetting its ghost history, learned latches or frame count. It does not restart
the attack at GT Armed. Switching full to half starts the same pelvis-relative graft
without reseeding. Switching half to full retains the existing rejoin behavior using
the current ground-aligned locomotion carrier; the full ghost takes ownership of
the pelvis/legs again. This is not a new pose-matched transition feature.

Rejected families/half kicks leave the current attack intact. Active Trigger calls
update target/family/mode without restarting history/latches/frame; fresh GT seeding
requires an inactive attack (use Stop first to restart). Invalid/missing GT data refuses a fresh half
attack instead of silently falling back to a moving lower-body seed.

## Visualize Ghost Attack

Call **Visualize Ghost Attack** from Tick while debugging. Cyan shows the full raw
ghost with authored PHAT colliders, yellow shows its equipped/training
sword geometry at the calibrated grip, and red shows its actual ghost-policy target.
`World Offset` defaults to `(150,0,0)` cm and shifts the ghost and target together;
set zero to draw at the ghost's simulation location. `Duration=0` draws one frame.
It displays the latest policy pose before the upper graft, presentation clamps and
roll corrections, without render interpolation. No actor is spawned and no tick
callback is registered. Disabled/inactive/Shipping calls draw nothing. Foot collider
trimming is a physical-only feature, so this ghost uses the original PHAT geometry.
The fallback training sword can load on the first explicit visualization call if
not already loaded. Convex wire edges use the cooked collision hull when available.

## September 26 verification

Live build loaded10:27:51UTC. `Prophecy.NN.HalfAttack.PelvisMount` passed10:28:23UTC:
subtree selection, local-pose preservation under yaw/pitch/roll, target inverse mapping
and initialization. The owned scene capture compares published upper/pelvis relative
transforms with the actual ghost decoder while locomotion turns: hookL14, slashR24,
headbutt59 and pike14 matched policy samples. Across spine_01 through head and both
clavicles, maximum position error was0.0000363cm and rotation error0.000064degrees.
Repeated half-enable retained phases/frame, visualization returned true for active
attacks and false when disabled/stopped. Owned Play ended and trace CVars reset.
Evidence: `Saved/Diagnostics/HalfPelvisMount/{live,summary}.json` and `trace.jsonl`;
scripts `Saved/Diagnostics/TestHalfPelvisMount.py` and `AnalyzeHalfPelvisMount.py`.
Library-default refresh repaired59 stale Live Coding CDO references, retaining all
other Blueprint values/wiring; compile status3, asset unsaved. No restart or saved
scene changes. Final debug-drawing build loaded10:39:54UTC (98.22s); both
`Prophecy.NN.HalfAttack.PelvisMount` and `GhostSwordDrawing` passed10:41UTC.
The sword test uses the actual training sword's cooked hull with editable indices
deliberately removed and verifies generated wire lines. Its first fixture omitted
the cooked pointer when copying the geometry; corrected fixture now retains it.
Include these Live Coding changes in the next normal editor build before reopening.

## Historical September 12 verification (superseded mount contract)

The following tests describe the former world-fixed torso design. Their independence
from real pelvis rotation is precisely the behavior removed on September 26; they are
retained as provenance, not current acceptance criteria.

`Tools/NN/TestProphecyHalfAttackPair.py` runs the actual scene for 28 game seconds,
using one idle and one independently walking/running agent. The runner starts
facing another direction and turns during Headbutt. The opt-in test copies only
the current upper world pose, translated to the runner's pelvis; it never copies
lower poses, recurrent states or model outputs. Targets are equivalent world
offsets, passed through the normal radius/ghost mapping. Saved Blueprint/map
settings are untouched.

`Tools/NN/AnalyzeProphecyHalfAttackPair.py` checks exact GT lower initialization,
paired neural inputs/outputs, and the published upper positions/rotations after
subtracting pelvis translation. See `Saved/Diagnostics/SlashContacts/HalfPairSummary.json`
for final measured values. Physical contact forces are not part of this kinematic
target-invariance test; two different collision situations can still move physical
followers differently.

`Tools/NN/TestProphecyHalfAttackLifecycle.py` checks all 14 permitted families,
half/full/idempotent switching without resetting frame/latches, invalid replacement
rejection, stop and PIE teardown. Evidence is `HalfLifecycle.json` in the same
diagnostics directory. The source-exact full-attack chain remains a separate check
in `ExactChain/ExactSummary.json`.

Final normal-build result: the Hook, Headbutt and Slash comparisons covered
12, 10 and 23 paired policy steps respectively, with **identical float inputs
and outputs** and zero GT lower-seed error. All three reached Armed/Hit and
completed together. Published upper-body differences were below 1e-9 mm and
1e-9 degrees (double-precision transform roundoff), while real pelvis rotations
differed by up to **125.01 degrees**. The idle root stayed fixed; the runner
travelled independently. The paired scene ran for 28 game seconds; attacks
naturally occupied shorter portions of that capture.

The separate lifecycle run passed all 14 accepted families and invalid-request
checks. Mode switches retained frame/latch values, including an idempotent
half-to-half call. Both runs ended PIE cleanly. This verifies target/NN behavior;
it is not a claim that different physical collisions produce identical motion.
