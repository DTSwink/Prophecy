# Right-hand slowdown during slashR recovery

September 23, 2026. Investigation in the current scene; Blueprint values and
saved assets are unchanged. Temporary ablations affect only owned Play sessions.

The slowdown is present in the NN presentation target, and the kinematic
PhysicalMesh hand follows it exactly. First return at frame134: speed rises
through179/219/227 cm per authored second, then falls to165 at exit+10 ticks,
and rises again to190/209/218. Spine-relative speed falls180.5→86.9 over that
same interval. Subsequent slashR returns reproduce it.

Current graph settings: slash neutral return Hold0.3, BlendToNN1.0, Speed300;
hand and FK-core tempering start0.1 and blend over0.5; forearm clamp starts5.5
and returns to snapshot1 over1.0. Upper-body inertia Response0.82, Hold0,
Blend0.08, Momentum0.69. The visible dip precedes the18-tick slash hold endpoint.

Controlled captures:

- `Saved/Diagnostics/CalfRoll-20260923-175629.json`:600-frame baseline.
- `HandBumpNoInertia-20260923-175819.json`: dip persists (228.5→155.7).
- `HandBumpNoClamps-20260923-180425.json`: disabling ordinary locomotion
  hand/forearm clamps leaves the first return numerically unchanged.
- `HandBumpNoSlash-20260923-175752.json`: disabling slash neutral return changes
  the trajectory substantially and removes that large world-speed dip, though
  smaller variations in the other controls remain.
- `MeasureRightHandBump.py` computes world, spine-local and physical speeds.

An editor-only `Prophecy.SlashReturn.Audit` trace records route, neutral and NN
targets, blade projection and arm-reach output. It defaults off and is queried
only during active slash recovery; no shipping or inactive work. Build17/18
compiled the trace, but only the automation test reached the new body; current
scene still called its previous live-patch entry. Renamed native entry ApplyPose
and rebuilt the manager call site to validate the live scene. Stage diagnosis
confirmed the live scene; no motion algorithm has been changed as a remedy.

## Confirmed cause

`SlashReturnStages-20260923-180941.json` reproduces the baseline exactly while
recording the controller stages. In the first return, Advance's route fraction
is0.158/0.369/0.551/1 at elapsed1/3/5/7 ticks. At tick7 the internal wrist equals
the moving NeutralWrist target exactly and remains equal on subsequent samples.
The controller has a speed cap but no arrival deceleration. Once it catches the
idle arm target, its own catching-up velocity abruptly disappears. The remaining
visible motion is the idle arm being carried by the changing torso/clavicle.
Interpolation presents the sharp speed reduction around exit+9/10 ticks.

Blend alpha is still0 at that point (Hold lasts18 ticks). Blade-clearance and
arm-reach displacement are both0, excluding those geometric corrections for
this dip. It also survives disabling the new upper-body inertia and ordinary
locomotion hand/forearm clamps. The scene is kinematic at the measured return.

The user subsequently chose **speed proportional to the initial distance only**,
instead of continuous arrival easing. That is now implemented: reference speed
at100cm times the outgoing hand-to-idle distance divided by100, captured once.
Changing Hold still only changes when NN ownership returns. The route retains
its existing finite arrival rule; this change scales near/far returns, rather
than promising mathematical velocity continuity for every possible pose.

Patch19 (native entry rename/trace only) compiled146.47s and loaded16:09:30UTC.
The trace is back off; owned Play ended. Pose Blueprint compiled status3 with
zero stale types and no default repairs. No graph edits, explicit saves or restart.

The proportional-speed revision built234.15s and loaded16:22:16UTC. All seven
focused tests passed16:23:06UTC, including one-time sampling, subsequent goal
movement, fresh capture on the next slash and zero initial distance. Pose BP
compiled status3;47 archived library defaults repaired while preserving all
other values/wiring, zero stale native/pin types. No explicit save/restart.

Live current-scene trace `SlashReturnStages-20260923-182322.json` confirms the
first return's19.0723cm initial distance produces57.216839cm/authored-second
from configured300, fixed throughout the episode despite moving idle targets.
The old exit+8→10 speed dip227→165 becomes150→180 in this bounded capture.
Other changes of speed still occur; no universal smoothness claim.

`SlashSwordVariants-20260923-182355.json` covers six full slashes, half slashL
and full/half pike over900frames. Five full slashes and half slashL remain outside
the sampled padded blade envelope throughout recovery; slashLU starts slightly
inside at its attack exit (0.978 normalized squared clearance) and is≥1.266
after four ticks. The already-overlapping starting pose is not instantaneously
removed. Half pike remains excluded. The motion route, clearance rules and
rotation winding were not changed. Diagnostic tracing is off; owned PIE ended.
