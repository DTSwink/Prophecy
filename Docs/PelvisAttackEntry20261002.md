# Backward pelvis step at attack entry

October 2 current TestNN setup: reproduced in the first Pike, entering at tick
169. The principal backward step is an entry timing mismatch between physical
seeding and the already-published locomotion endpoint. It is present in the
authored target; physics follows that target closely.

`Set Special Start From Physical` is enabled. Its sampled pelvis is
(-88.776, 22.355, 86.788) cm in the first attack input. Playback still completes
the outgoing locomotion interval, reaching (-91.847, 14.149, 87.728) at tick 170.
The attack's first actual prediction (policy frame 2) lands at
(-89.161, 22.564, 85.247), close to its physical seed but behind that completed
locomotion endpoint. Interpolation toward this prediction moves the pelvis
backward by **8.8333 cm horizontally** across ticks 170–172 (about 4.42 cm per
game tick), plus 2.48 cm downward.

The raw NN decoded pelvis output matches the future pelvis target. The physical
pelvis stays within 0.333 cm horizontally of its target during ticks 170–174.
This identifies an authored handoff reversal, not a collision dragging the
physical body away from an otherwise forward-moving target. The first prediction
also brakes the incoming velocity substantially; the timing mismatch makes that
braking into the large visible backward step.

## Controlled comparison

Two owned 300-tick replays use the current unsaved Blueprint and scene. The second
only disables `Set Special Start From Physical` on the player after recording
tick 168, before entry. No asset or persistent preference was changed.

| Measurement | Current physical seed | Temporary authored seed |
| --- | ---: | ---: |
| First backward horizontal step, ticks 170–172 | 8.8333 cm | 1.0418 cm |
| Maximum physical/target XY error, ticks 170–174 | 0.3328 cm | 0.3386 cm |

All physical pelvis samples through tick 169 are identical. Root positions
through ticks 169–177 are also identical. Loco drag and smoothing configuration
were retained. Removing physical seeding eliminates most of the reversal, but
the remaining small backward prediction means it is not a complete zero-motion
fix. It also changes which pose initializes the network, so disabling this
setting permanently was not installed as a fix.

The earlier entry change in `ProphecyNNSlashRuntime.inl` deliberately retained the
outgoing render endpoint to avoid rewinding an in-flight interval to an older
physical sample. This capture shows the other side of that boundary: the first
physical-seeded attack prediction can remain behind the retained endpoint. Any
fix needs coherent entry sampling/presentation timing while keeping the user's
actual-pose seeding intent, rather than merely adding damping or changing root
smoothing. No production fix was installed during that initial investigation.

Evidence: `Saved/Diagnostics/PelvisAttackEntry20261002/` contains baseline and
`no_physical_seed` pose captures, raw NN input/output traces, graph snapshots,
analysis scripts and `comparison.json`. `CapturePelvisAttackEntry.py` owns and
ends only its exact diagnostic world, preserves user/replacement Play, bounds
capture to 300 ticks/45 real seconds, and restores the two diagnostic trace
variables. Both captures completed; no build, Blueprint/map edit, or user Play
interruption occurred.

## Installed fix

User then requested the fix. On a full physically seeded attack's first
prediction only, `AdvanceSlashAttacks` captures the last presented NN target and
uses it as the start of the attack interpolation. Sampling at prediction time
rather than Trigger avoids a stale endpoint when Trigger falls between policy
steps. Physical seed/history, NN inference and prediction, attack phase clocks,
root movement and the full-to-half path remain unchanged. No extra inference,
timer, retained state or ongoing smoothing is added; one pose read occurs at entry.

Pending loco-drag legs retain their outgoing locomotion endpoints and reconnect
to the sampled entry hips with the existing length-preserving solve. Sampling
their foot endpoints from presentation too would accelerate the first drag step;
the first comparison caught that (14.84 -> 21.72 cm), and the final patch retains
the original 14.84 cm. Attack-owned legs use the sampled entry target.

Final Live Coding build succeeded in 30.04 seconds and loaded **21:34:58 UTC**.
The owned 300-tick current-scene replay and `check_fix.py` passed:

- Entry pelvis discontinuity at tick 170: numerical zero (3.6e-15 cm).
- First backward XY movement: **8.8333 -> 0.8186 cm** over ticks 170–172.
- First six attack NN inputs and outputs are exactly identical to baseline.
- Pre-entry physical pelvis and root positions through tick 177 are identical.
- Maximum pending-foot step over ticks 169–174 stays **14.8354 cm**.

The residual sub-centimetre backward motion belongs to the unchanged attack
prediction; this fix removes the large handoff overshoot rather than suppressing
authored motion. Evidence: `fixed.json`, `fixed-nn.jsonl`, `fix-verification.json`
in the same diagnostic folder. `initial-fix*` is the superseded comparison before
the drag-leg endpoint correction. User physical-start setting remains enabled;
no Blueprint/map edits or saves, no user Play interruption, no broad test suite.
Normal editor DLL rebuild is required before a cold launch.
