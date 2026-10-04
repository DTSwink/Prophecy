# Right-arm stop at slashR exit — October 4

This symptom originates in the FK lab return, unlike the preceding left-arm
locomotion hesitation. The outgoing samples and velocity are captured correctly;
the configured parent-bone weights and the lab momentum envelope brake the motion
strongly at the start of the return.

## Current setup and reproduction

Current attack is **slashR**, not the slashLU from the preceding investigation.
Its profile override is return time .3 seconds, inertia 1, easing 1. The global
takeover uses coefficient 2, alpha hold 0, trim .35. Effective per-bone weights
are spine 0, clavicle .19, upperarm 1, forearm .63; hands have deliberately no
local inertia. Easing 1 uses quintic smoothstep, whose idle-return velocity starts
at zero. Global inertia multiplies those bone weights; it does not override them.

The final attack endpoint is published at tick 132. The first FK endpoint is
published at 134, with elapsed 2/60 seconds and NN weight .02922054. Presentation
reaches the first FK interval at ticks 135–136. Right-hand displacement relative
to the pelvis drops from 5.320 cm at 134 to 1.195 cm at 135. This is a marked
slowdown, rather than a literal repeated pose. The relevant interval is Kinematic.

## Controlled replays

Each valid condition completed 260 game ticks. Captured bone poses through tick
133 are identical, and all lower-body/root data remain identical throughout.
Overrides affect only temporary PIE actors; the editor Blueprint was not changed.

| Condition | Hand/pelvis displacement at tick 135 |
| --- | ---: |
| Current settings | 1.195 cm |
| Only spine inertia changed from 0 to 1 | 2.561 cm |
| All inertia groups changed to 1 | 2.749 cm |
| Pure lab through the return (NN alpha hold 1) | 1.049 cm |
| FK return disabled | 10.417 cm |

The pure-lab condition reproduces the stop without NN mixing. Spine inertia
restores a substantial part of the lost inherited motion, but even all groups at
1 still brake sharply. Disabling FK return is a diagnostic, not a proposed fix:
its first locomotion step accelerates abruptly instead.

The first `spine_one` experiment wrote the profile at tick 132, where the user's
per-tick profile setter overwrote it before exit. Its unchanged momentum readback
made that experiment invalid as an ablation. The valid `spine_one_fixed` override
is applied after tick 133 and its latched spine momentum is verified. An initial
run under that filename lacked the mode dispatch; it was replaced by the valid
complete run. No ineffective condition is used in the conclusions.

## Why maximum inertia still slows so much

The lab multiplies outgoing local angular velocity by this displacement envelope:

`M(t) = t * (1 - t/T)^3 * exp(-t / (T * (.025 + .45*I)))`

Here `T=.3` and upperarm `I=1`. At the first 2-tick sample, M is .018528 seconds,
although .033333 seconds have elapsed. That is only **55.584%** of constant-velocity
angular displacement. Clavicles retain 25.695%, forearms 48.992%, spine and hands
0%. These percentages describe the momentum contribution, not the total motion
after the idle curve and NN blend.

The upperarm momentum offset peaks around .052 seconds (3.1 ticks), then decreases.
At two ticks it is .018528; at four ticks .019647; at six ticks .014688 seconds.
Thus this is a brief outgoing offset that is pulled back, not sustained coasting
at inertia 1. Easing 1 simultaneously suppresses the idle curve's starting speed.
Spine weight 0 cuts the substantial outgoing parent rotation immediately, which
also removes inherited sword-hand movement. Hands still have no local inertia,
as explicitly requested earlier.

The .35 trim shortens full-NN takeover to .195 seconds (12 ticks), but retains the
original .3-second FK/inertia timing. It is not the source of the first-step brake.

## Handoff verification and state

An independent numerical reconstruction uses actual outgoing endpoints 130/132,
canonical idle data, exact curve weights and the matching return-disabled NN
endpoint at 134. It reproduces all 16 first-return local rotations within
**9.89e-6 degrees**. This verifies the seed, velocity interval, curve time and blend;
there is no missing-velocity or repeated-start-sample explanation for this stop.

No runtime algorithm, Blueprint, profile or asset was saved/changed. All owned
sessions ended and diagnostic CVars were restored. Evidence and scripts:
`Saved/Diagnostics/RightArmReturn20261004/`, notably `curve-audit.json`, baseline,
no_return, spine_one_fixed, all_one and lab_only captures. Improving continuity
would require changing the retained parent weights and/or the lab momentum decay,
not adding another hand inertia system.
