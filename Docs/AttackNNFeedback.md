# Attack NN feedback controls

`Set Attack NN Feedback` restores the behavior from immediately before the
October 5 fidelity audit by default. Every checkbox defaults **true**, including
agents that never call the node. It configures feedback, not modifier strength
or enablement; existing modifier settings remain in control.

| Checkbox | Checked | Unchecked |
| --- | --- | --- |
| Start Core Inertia | Original full-attack core/carried-arm write-back | Keep pose effect; skip this write-back |
| Start Hand Inertia | Original full-attack corrected-arm write-back | Keep pose effect; skip this write-back |
| Hand Inertia | Original general-hand corrected-arm write-back | Keep pose effect; skip this write-back |
| Arm Cone | Original selected-attack corrected-arm write-back | Keep pose effect; skip this write-back |
| Left Wrist Constraint | Original native clamp and recurrent wrist rotation | Clamp the final visible/physical wrist after smoothing; leave raw recurrent wrist untouched |

The first four preserve the original full/half ownership: half attacks do not
feed those corrections into their independent ghost, even when checked. The
wrist setting controls both full and half attacks. Model-baked constraints are
unchanged.

These are **direct write-back** switches. With a mixed configuration, a later
modifier that still feeds the NN can encode a pose influenced by an earlier one.
Turn all five off to isolate these upper effects from attack recurrence. Physical
entry seeding, later attacks' starting poses, and intended lower/pelvis/ghost
feedback remain separate influences. This node does not alter the earlier
`Set Attack Motion Inertia` fix; that spring remains presentation-only.

Configure before triggering an attack for a reproducible comparison. A change
during an attack affects subsequent predictions; it does not erase corrections
already in history. Agent reset captures/restores the five choices. The modifier
debug report includes the current feedback mask and conditional history labels.

For default numerical compatibility, the audit's extra general-hand entry reset,
raw-ghost wrist attachment removal and end-extension direction change were also
reverted. The old floating-point work/order is retained behind boolean guards.
No new inference, pose buffer, bone pass, per-tick allocation or timer is added.
Overrides use a sparse per-agent bitmask: default agents take an empty-map fast
path; only opting out stores a value. Configuration/reset/world cleanup own that
storage.

Validation receipts and comparison scripts are under
`Saved/Diagnostics/AttackFeedback20261005/`. The earlier isolated audit is retained
as historical evidence in [AttackFidelity20261005.md](AttackFidelity20261005.md).

## Numerical checks

Normal editor DLL rebuilt and TestNN reopened; existing PoseAgent compiles with
status 3, native_properties 0, pin_types 0 and wiring preserved. The new function
is callable without refreshing or changing existing Blueprint nodes.

All 33 focused headless tests pass, including the 32 mask combinations, default
storage bypass, reset/world cleanup, native recurrent and presentation wrist
limits across four checkpoints, entry inertia, motion inertia and FK return.

The untouched default reproduces saved pre-audit slashL fixtures exactly:
full (19 steps), motion-inertia-on (19), full-to-half (19), pure half (16).
Maximum NN input/output difference is **0**. All recorded future, presented,
physical-body and target positions through tick115 also differ by **0 cm**.
Their recorded rotations are also exactly equal (0 degrees difference).
Calling the node with all default pins yields the same 19-step result.

All switches off reproduces the isolated 17-step NN trace exactly, both with the
user's existing settings and with the audit's combined stress modifiers. Each
of the five isolated modifiers individually preserves those raw predictions
while visibly changing the pose; re-enabling only its feedback changes the
recurrent inputs. This verifies that unchecked does not disable the modifier.
The ten individual controls and seven default/combined controls complete their
119-tick captures. See `analysis.json` for per-path differences.

The complete 1,900-tick saved setup reproduces all **696** recorded old native
steps with **zero input/output difference**. This intentionally includes the old
slashRD slowdown; no hidden automatic isolation remains in the five default paths.
Final editor verification: TestNN outside Play, graph identical, no dirty
packages, tracing restored to -1/0. No node insertion, tuning change or asset save.
