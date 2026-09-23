# Half attacks: GT initialization and independent upper motion

Implemented 2026-09-12. Use the existing **Trigger NN Attack** node with
**Half Attack = true**. No new Blueprint node or per-frame Blueprint work is needed.

## Starting a half attack

The separate attack history now starts its lower body at the original animation's
**Armed** frame, with its previous lower body at **Armed − 1**. These are actual GT
controller rows, not an idle approximation or a pose copied from the moving agent.
Both rows use the GT Armed root frame, preserving original lower-body velocity.

The current upper pose initializes both upper history frames, transported through
the corresponding GT pelvis. This deliberately avoids importing the runner's
previous upper/lower locomotion velocity. The physical mesh is not teleported;
only the data-only attack ghost receives the GT lower body. Real legs and pelvis
continue their own locomotion NN and mover.

Each new half attack gets a target-facing ghost frame. Its starting frame depends
on the requested target and upper pose, rather than the real lower body's heading.
The upper mounting orientation then stays fixed in world space for that attack.
The mount follows **pelvis translation only**, keeping the torso attached while
preventing real pelvis sway or root turning from rotating the attack's arms.

The ordinary radius-limited world target is transformed through that same mount
into the current ghost pelvis frame. Thus equivalent targets relative to the
translated upper body give equivalent ghost inputs. A stationary world target
correctly changes relative to a character moving past it; independence does not
mean ignoring genuine changes in the target's position.

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
existing attack batch and upper-pose publication; one quaternion per attack stores
the fixed mounting orientation. Half kicks remain rejected.

## Existing mode switches

**Set NN Half Attack Enabled** changes an attack already in progress without
resetting its ghost history, learned latches or frame count. It does not restart
the attack at GT Armed. Switching full to half freezes the current attack mounting
orientation. Switching half to full retains the existing rejoin behavior using
the current ground-aligned locomotion carrier; the full ghost takes ownership of
the pelvis/legs again. This is not a new pose-matched transition feature.

Rejected families/half kicks leave the current attack intact. Active Trigger calls
update target/family/mode without restarting history/latches/frame; fresh GT seeding
requires an inactive attack (use Stop first to restart). Invalid/missing GT data refuses a fresh half
attack instead of silently falling back to a moving lower-body seed.

## Numerical verification

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
