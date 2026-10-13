# Attachment spine pop diagnosis — October13

## Authorized fix and verification

User subsequently requested fixing both implementations. Removed the special
maximum-speed pursuit branch during tip alignment in Unreal and the lab. The
spine and both clavicles now retain the existing reach-curve schedule until
sliding, which still captures the body actually reached. No new controls,
retained fields, extra solves, tuning or Blueprint edits. Drawing is unchanged.

Unreal Live Coding succeeded123.44s, reload00:50:55UTC, no restart. Current
220tick Sim and Kinematic captures across all3agents finish S and show smooth
attachment continuation. Player at64: commanded spine8.23498→.94009deg,
physical7.13835→.90408deg; kinematic8.23459→.94012deg. NPC Sim first-alignment
steps10.54283→1.33901deg and9.91931→1.39725deg. Right clavicle continuity
assertions pass too. Mesh/native separation stays<.000006cm. The pre-attachment
window remains numerically identical in the before/after captures.

`test_attach_body_schedule.cjs` passes12 cases across both planners,
idle/walk/run, current and linear reach curves, checking all3 authored body
targets through alignment (41samples,max angular residual.00000342deg).
Saved-profile sequence replay now has first alignment spine steps1.05–1.32deg
instead of6.49–11.32deg. `test_tipalign.cjs` completes its36 motion/curve/shrink
cases, then fails its No-cheat-off D→S sequence-completion assertion. Replaying
the pre-fix `online.js` reproduces that same completion failure; it was reported
to the user, not weakened or declared fixed. Causal sequence completion timings
remain unchanged in the comparison. This patch validates the attachment spike,
not complete lab/Unreal1:1 parity.

Evidence/backups are in `Saved/Diagnostics/SpineAttach20261013/`, especially
`before-fix`, `lab-fix-comparison.json`, `live-fix-results.json` and the new live
captures. Lab refresh required. Editor13688 remains open outside Play; user's
dirty PoseAgent/TestNN/Fab imports left unsaved. Normal DLLs stale—build before
next cold launch. No push.

## Original diagnosis

User reports spine_05 pop at64 and requests diagnosis only, with explicit
rejection of hidden lab/Unreal differences or unsupported parity claims.
No implementation, lab/tuning, Blueprint, asset or build changes made.

Owned current-setup160tick Sim and Kinematic captures reproduce it. Player
attaches at63; spine_05 target step is .9653deg at63,8.23498deg at64,.03615deg
at65. Physical step at64 is7.13835deg. Kinematic target/physical step is8.23459deg
at64. NPC target jumps are10.54283deg at67 and9.91931deg at70 in Sim. This is
in the authored pose before Jolt, not an unexplained physical constraint kick.

`ProphecySwordHolsterAuthored.inl::AdvanceAuthored` changes from scheduled
Entry→Destination interpolation through the reach curve to Current→Destination
at `Speed/60` as soon as `Status.Aligning` becomes true. Current saved S speed
is1000deg/s, allowing16.6667deg/tick. The remaining turn is smaller, so the entire
remainder is consumed immediately. This turns the user's speed ceiling into
the requested speed at the phase boundary. Descendant bones are carried by FK.
No inertia fade is active at this player transition (action tick49 versus
.5s/30ticks entry inertia duration).

The current saved **No cheat=true** lab has the same rule in `online.js`:
`dock ? Body.advance(dockBody,desired,maxSpineClavicleAngularSpeed)`; `bodyreach.js`
advances each target quaternion by maxSpeed/60. Offline replay of current saved
settings gives8.19013deg at57 for standalone S (attachment56), and13.02340deg
at local44 for S in saved D→S (attachment43). The latter global location follows
the first D return. This is evidence about current disk code and saved settings;
no browser motion observation or assertion that the user perceived it is made.
The live desktop report confirms the same saved settings and No cheat enabled;
its JS runtime source identity was not independently verified. No future gait
sample is required to explain this particular speed discontinuity.

Evidence: `Saved/Diagnostics/SpineAttach20261013/` contains the two captures,
`compare.cjs`, and `comparison.json`; script reads lab modules without edits.
Owned PIE ended, FPS restored, editor remains open. No user Play was present
when capture started.

Prior synchronization verification was limited to mesh/native pose agreement,
completion, grip ownership and cleanup. Its Kinematic comparison was against
the prior Unreal capture, **not a same-input full lab/Unreal comparison**. It
therefore preserved this existing pop and did not establish smooth motion or
1:1 lab parity. For an honest future parity claim, compare per-tick authored
bone transforms and phase transitions using identical captured input streams
and settings, forbid future-input dependence, and check phase-boundary velocity
continuity. Sim target agreement and physical tracking error are separate
measurements; exact simulated body equality to a kinematic lab is not assumed.
