# Upper and lower special-end events

September 26, 2026. This replaces the combined Special Ended dispatch.

| Ownership transition | Event(s) |
| --- | --- |
| Half attack ends | Upper Special Ended |
| Full attack ends | Lower Special Ended, then Upper Special Ended |
| Full attack switches to half | Lower Special Ended immediately |
| Half attack switches to full | None at the switch; both when it ends |
| Parry or dodge ends | Both, consecutively |
| Repeated same-mode setter or inactive Stop | None |

This follows current ownership, so repeated full/half switches work without a
start-mode latch. Each full-to-half release sends lower once. A later half-to-full
switch reacquires the lower body and cancels only its active recovery. Final
completion releases whichever regions the attack still owns.

Both events expose Special, Attack, Half Attack and Returning To Locomotion.
At a full-to-half switch, Half Attack is true and Returning To Locomotion is true
for the **lower region**, while the agent as a whole remains Attacking. Existing
Armed/Hit state, policy frame, attack history and target are retained by switches.
The ordinary On Attack Ended gameplay event fires only when the attack ends,
after regional recovery; it does not fire at a full-to-half switch.

Lower end starts regional Walk/Run source recovery, lower tempering profile
restoration and leg reconstruction. Full-body root recentering, magic-cube root
handoff and calf-length recovery accompany this lower release. Upper end starts
hand recovery, FK-core recovery and attack arm return to neutral. Upper exit
inertia remains attached to actual upper completion. Special-to-special
interruptions emit the appropriate events with Returning To Locomotion false and
do not start return motion. Reset/replacement from a callback wins over pending
recovery; a replacement started by the lower callback suppresses the stale upper
recovery dispatch.

Pure half attacks do not clear or restart lower recovery at entry or exit and do
not recenter the root at exit. During half attacks, the lower body retains its
normal pin smoothing, bounds, optional every-tick pinning, lower tempering and
reconstruction clocks. Lower presentation also stays in locomotion mode while
upper presentation uses the attack mode. This separates knee smoothing and calf
render scaling from the upper body's attack state.

The old OnNNSpecialEnded interface function remains loadable for old Blueprint
nodes but is no longer dispatched. The current pose Blueprint migration replaces
its event with Lower Special Ended, keeps the existing lower chain and all values,
and connects the user's newly separated hand-tempering/arm-return chain to Upper
Special Ended. Both branches have a Returning To Locomotion guard. The connected
attack-timer cleanup follows upper completion; disconnected historical branches
remain untouched. The user rearranged this graph during implementation, so the
final migration uses the latest prepared layout rather than the earlier mixed chain.
Migration is undoable, exports the original graph and does not save the asset.

There are no per-frame event bindings or new recovery timers. Existing recovery
clocks retain the 60-unpaused-tick timing contract and retire as before.

Validation scripts: Saved/Diagnostics/InstallRegionalRecovery.py and
Saved/Diagnostics/TestRegionalRecoveryLive.py. Native regression:
Prophecy.NN.SpecialRecovery.RegionalOwnership, alongside the existing recovery
tests and the upper/lower presentation classification assertions in AttackHandClamp.

## Loaded validation

Runtime Live Coding loaded **21:20:59 UTC**; the final editor migration helper loaded
**21:24:47 UTC**. The pose Blueprint migration compiled with status 3 at
**21:25:22 UTC**, and its upper/lower execution paths were audited separately.
There was no explicit asset save, editor restart or push. Unreal's automatic
autosave ran before migration; it is not a saved final Blueprint backup.

Native validation at **21:21:38 UTC**: **34/38 passed**, including both
SpecialRecovery tests, AttackRecovery, upper recovery/arm-return tests and the
new half-attack presentation checks. The four failures are the previously
documented RootLocalPinAndChain, StancePlaneConnectedRegression, StancePlaneIdentity
and SupportHeadingFrame tests. Their older geometry expectations conflict with
the accepted solver; the solver and those assertions were not modified here.
See [the pre-existing identical failure set](Pelvis380Diagnosis.md).

The owned kinematic scene test completed **21:26:19 UTC**. It verified:

- Half stop: upper only; full stop: lower then upper.
- Full-to-half: lower at the switch, upper at final stop.
- Half-to-full: no event on reacquisition, both at final stop.
- Full-to-half-to-full-to-half: lower twice, upper once at final stop.
- Idempotent mode calls and repeated inactive Stop emitted no duplicate events.
- Mode switches retained frame and Armed/Hit state.
- Pure-half exit retained the root and all captured lower future/presented
  positions exactly in the same-frame before/after comparison.

Parry/dodge paired dispatch and leg/arm recovery ownership were verified by the
native regional test; they were not recaptured in a separate live defense scene.
This is not a claim that simulated knees cannot move from physical forces.
Owned Play ended; RegionAudit is off. User visual acceptance remains pending.
Evidence: Saved/Diagnostics/RegionalRecovery/{live.json,live.log,summary.json,graph.json}
and Saved/Diagnostics/RegionalNativeTests.json. The original graph export is
Saved/Diagnostics/BeforeRegionalRecovery-20260926-232521.txt.
