# Attack fidelity audit — October 5, 2026

**Superseded default at the user's request:** [Set Attack NN Feedback](AttackNNFeedback.md)
restores the pre-audit paths by default, with five checked feedback switches.
Uncheck them to opt out. The numerical findings below describe the isolated
audit implementation, not the current default configuration.

The attack checkpoint now retains its own upper-body recurrent prediction while
the existing upper modifiers shape the accepted visible/physical pose. This
addresses the feedback interactions found in the overL and slashRD investigations
without removing the user's modifiers, changing their pins/defaults, forcing
Armed/Hit, or adding inference.

## Changes

| Path | Finding and change |
| --- | --- |
| Extra left-wrist limit | The configured runtime limit modified the native output and six recurrent wrist-rotation channels. It now constrains the final accepted hand after upper smoothing. The checkpoint's trained 55-degree limit remains inside the model. |
| Attack-start FK core inertia | Full attacks re-encoded filtered core and carried arms into the ghost/history. Removed those writes; full and half both retain the visible effect without changing attack recurrence. |
| Attack-start hand inertia | Removed filtered arm writes to the full-attack ghost/history. Entry timing, spaces and configuration remain. |
| General hand inertia | Removed filtered arm feedback. Reset its dormant spring state at a new full/half special entry so a prior attack cannot supply stale motion. Configuration is retained. |
| Arm repellant cone | Preserved selected-attack pose correction and outgoing accepted endpoints; removed full-attack arm re-encoding. |
| Fixed wrist attachment | Removed the duplicate correction from the raw ghost decode. Existing presentation attachment remains, including the explicit wrist freedom/forearm stretch controls. |
| End extension | Compare raw ghost forearm direction against raw predicted forearm direction. Removed the presentation attachment from the candidate side so fixed/free wrist settings do not mix conventions in this decision. |
| Attack motion inertia | Retains the previous fix: final pose filtering with independent attack history and a source cache for the earlier modifiers. |
| Modifier debug report | Updated affected rows to describe pose/physics effects instead of recurrent history. |

Removed the now-unused `StoreInertiaArm` helper and native extra-wrist settings.
The final wrist correction uses cached arm indices once per accepted policy
endpoint. There is no new inference, per-tick allocation, or extra full-bone pass;
the removed feedback blocks included repeated pose encoding and bone searches.
General hand reset is event-only.

## Audited and preserved

New special entry already cancels FK return, forearm length recovery, old upper
tempering/recovery, hand/core entry inertia, motion inertia, arm-cone recovery and
manual Armed pose. Full entry also cancels lower recovery; half entry deliberately
leaves lower locomotion ownership intact. Upper return is gated off while attacks
own the upper body. FK return still captures the final two accepted poses.

Ghost loco drag, ghost-foot inertia, real pelvis inertia, locomotion-owned leg
feedback, foot pinning/clamps and lower tempering retain their established paths.
These intentionally alter lower inputs seen by the attack model. Model-baked
geometry, forearm leeway, root/target coordinate mapping, half mounting, physical
entry seeding, explicit static/Armed controls, learned phase gates, tail/trim/end
extension, Jolt contacts/drives and manual authored layers retain their controls.
Physics can affect a later attack's entry pose; this is not a claim of a vanilla
full-body rollout under all gameplay settings.

## Verification

Normal Development Editor build succeeded. Cold TestNN launch compiled the saved
PoseAgent Blueprint: status 3, zero native-property/pin-type problems, wiring
preserved. No Blueprint/map graph or tuning changes were made by this audit.

Eight owned physical fixture replays cover full, full-to-half at Armed, pure
half, and fixed-wrist full attacks, each with upper modifiers off versus all on.
The enabled stress case combines hand/core entry inertia, general hand inertia,
the selected arm cone, motion inertia with After Hit, and the 10-degree wrist
limit. For each pair all 17 native steps have **bit-identical complete inputs and
outputs**; Armed 66, Hit 82 and last attack tick 93 match. Visible right-hand
positions differ substantially, proving the effects are active; all captured
future/presented/body/target transforms remain finite. Maximum accepted left-wrist
bend is 10.000024 degrees, including the fixed-attachment test.

The saved current setup ran 2,200 ticks with its existing settings and completed
50 attacks across 14 families, including repeated overL/slashRD. Every completed
attack reached Armed and Hit. Longest pre-Armed interval was 19 game ticks. The
51st attack began near the capture cutoff and was still active at the cutoff.
The jabL -> slashRD request corresponding to the earlier stall now starts 1201,
Arms 1220, Hits 1228 and ends 1240; earlier attacks also finish sooner, so this is
a new sequence trajectory, not the original exact-entry counterfactual.

All 32 selected native checks pass after refreshing an obsolete reference:
wrist math/modes/all four checkpoints, entry hand/core inertia, general-hand
entry reset, seven motion-inertia tests (including return handoff), and FK return
lifecycle/timing/feedback/parity. The initial run passed 31 and failed the FK lab
runtime comparison because its saved slashLD fixture still used duration .28,
easing .87/inertia .76/hold .05 instead of accepted .37/0/1/.08. The native
algorithm comparison already passed. `ExportFKReturnLab.cjs --reference-only`
now regenerates independent JS reference poses using the accepted header profiles
in memory, without writing the header or user's lab state. The failed test then
passed across 320 variants and 6,133 runtime samples: max position error
.001156 cm, max angular error .000319 degrees. No return algorithm/profile was
changed or test tolerance weakened.

The final normal-DLL rebuild also passes the complete 32-test selection in one
headless run (`automation-final/index.json`, zero failures).
Six more final-build captures recheck the slash stress pair and compare hookL /
overL with free versus fixed wrists, using a .001-degree extension threshold.
Both pairs have bit-identical native arrays, matching phases/end, and accept
exactly one extension (hook angle 28.240633 degrees; over angle 7.290783).
Final TestNN inspection confirms no Play session, no dirty packages, an identical
Blueprint graph, and tracing restored to -1/0. Fourteen fixture captures total.

Receipts: `Saved/Diagnostics/AttackFidelity20261005/` (`analysis.json`,
`sequence-analysis.json`, automation reports, build/editor logs and replay
scripts). Baseline/after cost captures are under
`Saved/Diagnostics/AttackPerformance/fidelity_*`.

The first whole-scene cost comparison is inconclusive: full-attack world time
rose 17.99 -> 21.82 ms, but locomotion-only frames also rose 13.60 -> 17.29 ms and
unchanged network/physics stages slowed. The trajectories and mode sample counts
also differ because attacks finish earlier. This is not evidence of a measured
speedup or a controlled overhead bound. The established cost claim is structural:
no added inference/allocation/bone pass, and removed redundant encoding work.
A second warm capture remains similarly noisy (22.03 ms full / 17.11 ms
locomotion); it does not justify a stronger performance claim.

Coverage is controlled numerical/runtime testing, not a guarantee that every
possible NN input or extreme modifier configuration produces a successful or
visually pleasing attack. The physical sequence covers 14 of 16 families;
headbutt and kickR were not selected in that sequence.
