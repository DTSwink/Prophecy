# Captured custom slash harness

Current status: the caller phase was corrected after the investigation below.
Both complete 19-step attack rollouts now match the original native trace within
5.8e-6, with Motion Inertia disabled. The original hard slowdown is reproduced.

`BP_ProphecyManualPoseAgent` -> `codex custom attack` repeats the problematic
sixth slashL from the October 3 corrected capture (trigger 731, first prediction
732, right-hand brake 743). The existing `tick debugging` caller is retained.

- `Cool Out Seconds`: wait after the actual attack finishes; default 1 second.
- `Show Target`: cyan target sphere; default enabled.
- It runs a live full slashL using the currently selected checkpoint and attack
  tuning, including the optional `Set Attack Motion Inertia` setting. Original
  capture used Predictive Pin 184064.
- Each repeat restores both captured NN history frames, reconstructs the entry
  skeletal pose, places the physical rig and held sword, and then triggers the
  attack. Existing simulation mode and tuning are retained.
- It does not replay cached future motion or automatically enable inertia.
- Preparation/trigger errors print their reason and latch `Codex Custom Failed`.
  Restart Play after fixing the cause, or clear that variable to retry.

`Tools/NN/Fixtures/ProblemSlashL743.json` holds the 272-value first native input,
expected first output, target, checkpoint identity and source SHA256. History is
consumed once by the following Trigger NN Attack; ordinary attacks retain their
existing history and physical-entry sampling. The fixture reconstructs skeletal
history, not the full preceding physical world/contact state.

`Prepare Problem Slash` is also available as a development Blueprint node. Call
it immediately before Trigger NN Attack (`slashL`, Half Attack false), using its
returned target. The editor-only `Prophecy.Editor.BuildCustomAttack` command can
rebuild an empty function; it refuses to overwrite a populated one and backs up
the live Blueprint first.

Evidence and the pre-edit live Blueprint backup are under
`Saved/Diagnostics/CustomAttack20261003/`. Normalized graph comparison confirms
that all graphs outside this function and its one caller remain unchanged.

Loaded through Live Coding. A normal Development Editor build is required before
a cold launch; preserve unsaved Blueprint/map work first. Do not launch an older
DLL with these reflected nodes saved in the Blueprint.

## Verification (October 3)

Two owned 360-tick Sim replays (inertia off and full-upper 0.03) each completed
two slashL attacks, beginning at ticks 60 and 240 under the existing caller.
Both repeats restore all 262 pose/history channels exactly. Maximum whole-input
difference from the original first prediction is 2.3842e-7 (target roundoff);
maximum native output difference is 3.1591e-6. Every captured pose is finite.
The baseline hand slowdown is visible at ticks 73-74 (2.603/2.072 cm travel).
With inertia enabled those intervals travel 7.112/6.786 cm; the maximum change
in displacement vector over ticks 68-77 falls from 11.634 to 7.425 cm. These are
this isolated replay's figures, not a claim of identical physical contact history.

Blueprint compiled with status 3 and zero stale native-property/pin types, and
was saved. All other graph wiring/values match the live pre-edit backup after
normalizing Live Coding CDO identities. Tests ended their own Play sessions and
restored tracing; inertia was enabled only on the temporary test actor. Editor
remains outside Play, ready for the user's test.

Jolt placement uses an explicit development-only rig teleport path, enabled only
around the synchronous setup call. It retains rig bodies, joints and ownership;
the independent-body API otherwise continues to reject rig handles. The scoped
console bridge avoids importing a newly added cross-module symbol during Live
Coding. The permission switch was verified restored to zero after testing.

## Follow-up: isolated replay is not a full reproduction

User noticed the baseline looks less abrupt without enabling Motion Inertia.
Comparing the complete original sixth slash to the isolated run confirms this:
first native input/output match, but the next input already differs in the upper
state by 0.04142964; lower history still matches within 1.5e-7. Thus first-step
parity does not establish complete motion parity. Original trigger731 is followed
by prediction732; isolated trigger60 is followed by prediction62, a different
phase relative to the 30 Hz policy clock. Existing attack-start hand inertia
(Blend .2, Response1) and FK-core inertia (Blend .1, Response .25) are still
configured in both graphs. They initialize from outgoing presentation snapshots
and feed their accepted upper pose back into the model; the fixture reconstructs
these snapshots and restarts their clocks rather than restoring the original
runtime entry. Exact contribution of pose reconstruction versus clock phase has
not been separately ablated.

The original switches full-to-half at Armed742. The isolated run stays full
throughout, and Arms at native frame6 instead of7. The shared caller-selection
boolean gates the user's existing half-switch branch; the new custom function
does not reproduce that transition. No new Motion Inertia call exists in either
baseline graph. At the main slowdown the original hand travel drops15.955 to
3.542 cm/tick, while isolated drops12.031 to2.603; it is entering the stop more
slowly. This harness is useful for an isolated related slash, but should not be
presented as an exact reproduction until presentation entry/history, policy
phase, and half-switch behavior are matched. This follow-up changed no runtime
code, tuning, Blueprint or Play session.

## Resolved: older entry-inertia clock phase (October 3)

The earlier uncertainty about pose reconstruction versus timing is resolved by
controlled replays. Pose reconstruction was sufficient for native trajectory
parity; changing only trigger phase restored the entire original attack.

Both baseline graphs already enable `Set Attack Start Hand Inertia` (Hold0,
Blend0.2, Response1, Alpha1) and `Set Attack Start FK Core Inertia` (Hold0,
Blend0.1, Response0.25, Alpha1). The newly added Motion Inertia is off and was
explicitly disabled on every temporary experimental actor.

These older inertias consume the 60 Hz world-tick blend clock when a 30 Hz policy
prediction is published. Their accepted upper pose is written back into the
attack state. Original trigger731 -> first prediction732 consumes one tick;
custom trigger60 -> prediction62 consumed two. With the same seed and prediction,
the first hand weight is consequently0.980324 versus0.925926, and the first core
weight0.925926 versus0.740741. The first accepted upper feedback differs; the
following prediction consumes it. Armed consequently moved from native frame7
to6 in the faulty isolated harness. This is a phase sensitivity of the existing
entry blending, not a change to the new Motion Inertia node.

Five completed owned controls in `Saved/Diagnostics/CustomAttackParity20261003/`:

- `even`: manual trigger58 -> prediction60 reproduces the faulty two-tick entry,
  including the0.04142964 right-arm feedback difference at the second input.
- `odd`: trigger59 -> prediction60 restores all19 original native steps within
  max input1.4901e-6/output5.7817e-6. Full attack throughout still reproduces the
  stop, reconfirming that the half switch is not its cause.
- `even_entry_off` and `odd_entry_off`: disable only older hand/core entry
  inertias. Complete paired NN inputs and outputs are bit-identical. Pelvis,
  ghost-loco and the rest of the pipeline remain enabled/configured.
- `wired`: final360-tick Blueprint replay, with new Motion Inertia disabled,
  produces two19-step attacks with the same whole-rollout parity figures.
  Starts59/239, Armed+half70/250, Hit86/266, ends98/278; phase frames7/15 match
  the original. All captured poses finite. Original hand slowdown15.955->3.542
  cm/tick becomes16.106->3.625 in the isolated physical scene.

The native lower/pelvis trajectory remains within floating-point precision in
both even/odd cases; it does not explain the divergent upper recurrence. The
prior learned-braking diagnosis also remains valid: separate bare-network
replays already showed braking without entry inertias. Entry feedback changes
which upper trajectory/timing/severity the checkpoint produces.

Repair: `Prophecy.Editor.MatchCustomAttackPhase` backs up the live Blueprint,
then adds one Select Int on the existing periodic trigger. Original/random mode
retains tick%60==0; selected custom mode uses tick%60==59, matching the captured
one-tick wait. Also decouples the original Armed-to-half branch from the attack
selector so selecting custom no longer disables that transition. No runtime NN,
ghost-loco, pelvis, inference schedule or inertia algorithm was changed. The
fix assumes the existing60 Hz game/30 Hz policy setup and60-tick test cadence.
The helper `Prepare Problem Slash` alone does not establish this call phase.

There are known visual differences outside the native attack: seeding publishes
alpha1 rather than the original halfway display, causing a7.752cm initial
presented-pelvis offset in aligned attack space that decays to0.060cm at the brake.
The preceding run and mover trajectory are not restored; after half release,
real locomotion/pelvis motion differs even while native attack outputs match.
Do not claim identical full-world physics or rendered motion through attack end.
The repaired harness reproduces the native attack and sharp slowdown, not the
whole preceding world trajectory.

Phase-only editor patch loaded20:56:46UTC. Final Blueprint compiled status3 with
zero stale native-property/pin types and was saved. Graph diff is limited to the
one selector, periodic-test input and Armed-branch condition. Pre-repair live BP:
`Saved/Diagnostics/CustomAttackParity20261003/BeforePhaseRepair.uasset`. Owned Play
ended; trace restored. Existing cold-launch rebuild requirement still applies.
