# Bodyflip Lab

Independent desktop lab, created October 24, 2026. Open **Bodyflip Lab** on the
Windows desktop, or run `launch.ps1`. The loopback service is
<http://127.0.0.1:8876/>. It uses its own Edge/Chrome app profile and saved settings.
Unreal is not required for playback. Jolt and the frozen network weights are local.

## Git checkpoint and restore - October 24

The curated checkpoint includes app/server source, desktop shortcut scripts,
Jolt JS/WASM runtime and license, attack/jump recordings, all four locomotion
phase banks, verification scripts/receipts, and `saved-profile.json` containing
the saved tuning and camera at push time. Live `state.json` stays ignored.
On a fresh restore, copy `saved-profile.json` to `state.json` before opening the
lab; do not overwrite an existing profile unless you want that saved snapshot.

Playback requires Python 3 and Edge/Chrome; no Torch, live NN inference or Unreal.
The desktop launcher currently expects the recorded Stepper Python path. If that
path is unavailable, run `python Labs/BodyflipLab/server.py --port 8876` from the
project root and open http://127.0.0.1:8876/ in a browser. Recreate the desktop
icon with `install_shortcut.ps1` after configuring that launcher path.

Original model copies and NPZ seeds, temporary Unreal export project, logs,
browser profile, snapshots and historical preview images are excluded. Model
provenance records their source paths/hashes; these external inputs and the
Stepper runtime are required only to regenerate the included phase banks.
Latest split-blend and foot-roll previews are retained as small review images.

## Independent body and support-leg blends - October 24

Sequence now has Body and Leg sliders (seconds, 0-1). Body starts at PUSH and
blends the other animated joints into the jump; pelvis remains procedural. Leg
starts when ground contact releases and blends live ground reach into the
supporting leg's animation, including Match foot timing when enabled. Neither
control changes the pin duration. Zero selects an immediate handoff.

Existing jumpBlend is retained as Body; missing legBlend inherits the saved
jumpBlend on load. Both therefore start at the user's prior value. Edits preserve
the playhead and save independently. Body blending is masked out of the support
chain even with Match foot disabled. The existing abort/fall blend is unchanged.
33 numerical checks verify independent joint motion, zero, migration and contact
timing; six browser checks verify editing, persistence and retained playhead.
Receipts: split-blend-verification.json, split-blend-browser-verification.json.

## Forward foot placement and adjustable roll - October 24

Support ankle/toe rotations now turn toward root-forward while the foot travels
to the target. More options contains Plant degrees (default10: heel up, negative
values lift toes), Toe-off degrees (default35 heel up), and Roll degrees/second
(default720, range0-3600). Zero speed holds the landing angle. The approach turns
with travel progress; Roll speed applies only during the grounded push.

Landing clearance uses the rotated foot and toe boxes. The actual sole contact,
including its offset from the ankle, must be on available ground; near an edge
this can move the ankle target back. Ground-sweeping rotation is adjusted during
approach without increasing ankle speed. Takeoff requires the final landing
orientation and real sole contact. Foot/toe local geometry is preserved.

The push rolls the rigid foot around the active sole contact instead of pinning
the ankle. Contact vertices transfer continuously across the sole outline; the
marker shows that contact. Angle advances at Roll speed up to Toe-off. The first
leg-reach or invalid-surface boundary releases the foot, even if the requested
angle is not reached. Release blend and frame matching use the final rolled
ankle/orientation. Existing pelvis trajectory, jump selection and cached NN stay.

Saved Phase67%, Foot500, Lead6: initial heel lift33.29 degrees, arrival10 degrees,
toe-off35 degrees; takeoff .945833s and pin .053026s at speed720. Speed360 reaches
27.19 degrees before reach release; speed180 reaches17.15 degrees. Some forced
late RunL plants now abort because the actual toe contact cannot fit before the
edge; do not weaken reach/abort to manufacture a push. Forced-foot comparison
fixtures use Early.3 to leave runway; user's Early.1 is retained.

Ten browser checks pass: speed edits change the displayed pose in21ms, keep
playback time, accept zero, and remain in collapsed More options. Saved settings
and camera restored after verification. `foot-roll-browser-verification.json`.

294 numerical checks cover both gaits/feet, signed landing angles, exact angular
rates including0, actual rendered sole contact, finite ground, pose continuity,
and seeking. Matching80 checks pass. The former fixed-ankle drift requirement is
superseded by rolling contact. No inference, Unreal work, or server restart.
Receipts: `foot-roll-verification.json`, `contact-verification.json`.

## Cached phase changes and real support contact - October 24

A previously unseen Phase/duration combination launched a fresh Python/PyTorch
worker, rebuilt the lower rollout, and reran upper inference. Measured Run43%
request: 4.553 s (2.545 s inference), versus .034 s when already cached. Multiple
edits could queue behind the server inference lock. This was a preparation stall,
not a phase control that did nothing.

`export_phase_bank.py` now prepares every discrete phase once, with the original
phase-specific warmup/seed, for Run/Walk and both equipment states. Single-thread
CPU export; no persistent inference process. Binary float32 banks cover the full
.1-5 s duration range and preserve Python's phase rounding and 100%=0 wrapping.
`run_bank.py` slices these files; server API4 never imports torch or launches a
worker for /run. Existing bounded four-entry caches remain. Re-export only when
the frozen source models/runtime change. The lower export horizon was extended
to cover the largest phase plus five seconds. Phase0/.44/.67 Run points and axes
match the old generated output exactly, including their original upper warmup.

The support gate is now necessary but not sufficient for takeoff: the rendered
sole must reach the floor too. Previously the ankle froze as soon as it came
within Gate, leaving up to that distance of air under the foot. Approach continues
at the requested speed with the root advancing; no final snap. Reach limits and
increasing-distance abort still apply. Current Phase67% / Foot500 had 4.837cm of
hover; contact now occurs at .925s rather than .9125s (12.5ms later), with under
.002mm sole error throughout PIN. After release the leg may lift normally.

End-to-end browser phase edits now take 11-30 ms (four phases), retaining the
playhead. API requests measured10-33ms for1s clips and63ms for5s Walk. All100
rollouts pass full-duration/finite/speed checks, all four default outputs match
exactly, and 100% wraps to0. Ten browser checks pass, including current saved
PIN. Receipts: `phase-bank-verification.json`, `phase-latency-verification.json`,
`fast-phase-browser-verification.json`, `contact-verification.json`. Four bank
files total18.4MB. Export worker exited; only Bodyflip server restarted (API4).

Nine contact cases cover both gaits, both feet/equipment and current saved setup,
using actual renderer boxes independently of the solver. Continuous takeoff,
fixed pin and approach speed checks pass, along with 80 matching and 162 support
checks. Saved tuning and camera are preserved. No Unreal/training changes.

## Playback timeline focus fix - October 24

The playback thumb no longer stops updating when the timeline retains focus
after scrubbing. Display synchronization follows simulation time regardless of
focus; live scrubbing still pauses and previews, and arrows still step frames.
Regression coverage added to `verify-timeline.html` for focused Space resume,
advancement, pause synchronization and arrow stepping. All 21 timeline checks
pass; receipt `timeline-focus-verification.json`. Saved state restored after
the check. No motion changes.

## Closest-foot frame and synchronized leg playback - October 24

Replaced the fixed-endpoint experiment with **Match foot** in More options,
enabled by default. Old endLeg settings are discarded; standing speed selection
and other tuning remain. At release, search the selected trimmed jump's 60 Hz
frames up to the fall transition for the closest support ankle in pelvis-local
space, using the actual hip socket. Equal matches prefer the nearest source time
to release. Search runs once during preparation, never each playback frame.

Support leg then plays actual source frames on its own clock:
`rate = (fallTransition - matchedTime) / (fallTransition - releaseTime)`.
An advanced match slows playback; a behind match speeds it up. Both clocks meet
at the same fall transition, then share the normal loop crossfade. The pelvis,
root and other joints keep their original timing. Existing Blend fades from live
reach into this retimed animation to avoid snapping when the nearest foot pose
is not an exact match. Zero Blend still requests an immediate handoff.

**Anim leg** shows the retimed target, not a fixed endpoint. More options displays
matched source time and rate; hover for remaining ankle mismatch. Current saved
Run R / Foot300 / alpha.03 matches .100 s versus release .034095 s, rate .965601x,
closest ankle gap12.76cm. This is a modest advance/slowdown, not a perfect match.
The long jump itself is not shortened; the leg now follows its motion instead of
interpolating slowly to one end pose. Unchecking Match foot restores normal timing.

80 numerical checks cover nearest-frame optimality, rate/deadline, sampled leg
rotations, unchanged other joints, ghost alignment, release/fall continuity and
seek determinism for Run/Walk, both feet and Run/Stand clips. Seven browser checks
pass for toggle, velocity selection and retained playback time. Legacy live-aim28
checks pass with matching off. Receipts: `match-leg-verification.json`,
`match-leg-browser-verification.json`. No NN/Unreal work or server restart.

## Earlier endpoint experiment (replaced above) / standing selection - October 24

Collapsed **More options** in Sequence contains two saved controls:
- **Stand / Walk**: standing-start cutoff as a fraction of Walk F speed (2 m/s).
  Default .5 selects Stand below 1 m/s; zero disables it. Compare horizontal
  root velocity around support contact, not mode name. Current Walk2 and Run5
  both remain Run-start at default; raising the ratio enables comparison.
- **End pose**: enabled for this experiment. After the ordinary reach-limited
  pin, interpolate support-leg local rotations directly from the released pose
  to a fixed endpoint. The endpoint is the last jump-only pose at loopStart,
  immediately before the fall-loop crossfade. Remaining angular distance over
  remaining time gives slower motion when already close. All four support joints
  reach that pose at the same authored time the rest of the jump reaches it.
  Existing initial body Blend still applies to other joints. Unchecking restores
  the live-IK-to-moving-animation blend over Blend seconds.

End-pose mode uses linear quaternion interpolation with a shared deadline,
not a chase of intermediate leg frames. Arrival is ~1.95 s (Run R) /2.05 s (Run L)
after jump starts. It does not increase ground pin time. Endpoint interpolation
follows pelvis/root heading and air rotation; only the initial pin is world-fixed.
The purple **Anim leg** ghost shows the fixed destination until arrival, then
resumes the current fall animation target. At the boundary the normal .25 s
fall-loop blend continues without a positional snap. Existing trim Out1.8 ends
before this endpoint in the default run, so extend the bracket to see arrival.

Standing L/R assets were sampled read-only to `data/jumps-standing.json`, with
source hashes. These are actual Relaxed Stand clips, trimmed by the same first
root-ascent rule: L .6667 s / R .6167 s. No synthetic symmetry was introduced.
No interactive editor was running; one headless null-RHI commandlet exported
both clips and exited successfully (0 errors/warnings). No asset saves or builds.
Reproduction: `export_standing_jump.py` (also usable via RunUnrealRemote).

69 focused endpoint/selection checks pass across both gaits, both support feet,
Run/Stand targets, synthetic low velocities, monotonic angular progress, exact
arrival, both boundary continuities and capped fall. Seven browser checks verify
collapsed controls, real Stand/Run selection, toggle and preserved time. Legacy
pelvis184 and live-aim28 checks pass with End pose disabled. Receipts:
`end-leg-verification.json`, `jump-options-browser-verification.json`.
Other saved settings/camera retained. No NN inference or server restart.

## Animation support-leg ghost - October 24

Viewport checkbox **Anim leg** shows a purple x-ray skeleton of the chosen
support leg's jump-animation target (hip/knee/ankle/toe), attached to the current
displayed pelvis. It excludes locomotion crossfade, support IK and release blend.
It follows the jump clip and later the transition to the prolonged-fall clip.
This is the animation destination, not the procedural reach or ground target.
Visible from jump start onward; absent before jumping, on abort and in Space.
Default off, saved independently of the existing whole-body Ghost. Toggle only
redraws/saves, without replanning or resetting playback. No target sampling while
off; lightweight leg overlay stays visible through the body.
16 numerical checks cover both feet/gaits, raw local target alignment, unchanged
input poses and differing IK-vs-animation feet; 3 browser checks confirm toggle,
unchanged time/pose and no runtime errors. Preview: `anim-leg-preview.png`.

## Live support aim through release - October 24

During RISE/BLEND the leg previously blended from a frozen root-local release
pose, so pelvis movement carried the leg away from its ground target. The blend
source is now a fresh two-bone IK solve from the current hip toward the original
planted ankle each sample, clamped to Reach. Solve after any air flip/twist so
the ground target remains world-fixed. Blend fades this live reach into the
animation over the existing duration; FREE remains fully animated.
The pin still releases at the reach boundary: out-of-reach feet aim toward the
target instead of stretching or claiming continued ground contact.

28 focused checks cover live target alignment, rejection of the frozen-pose
regression, leg lengths, Run/Walk, both feet and air rotation. At 50 ms into a
1 s diagnostic blend, unrotated aim errors are .07-.18 degrees versus 3.8-12.5
degrees for the old frozen direction. 184 pelvis and 162 support checks pass.
`release-aim-verification.json` records results. Settings unchanged; cached
motion only, no server/Unreal/NN restart.

## Procedural pelvis during jump - October 24

The pelvis is excluded from both the jump-start and prolonged-fall pose blends.
It keeps its takeoff root-local position and orientation while the root follows
jump height, forward travel and capped fall. Air flip/twist still rotate around
that procedural pelvis. The jump animation can no longer introduce a hip drop.

The supporting thigh/calf/foot/toe are excluded from the initial animation blend
while planted. The hip socket stays fixed relative to the pelvis; two-bone IK
owns the leg until the existing Reach boundary. At release the existing Blend
hands that leg back to local animation rotations. Other joints blend as before.
Locomotion, support approach and failure paths are unchanged. Current saved
Blend .08 and all other controls/camera are preserved. No new slider required.

Verification: 184 checks across Run/Walk, unarmed/drawn, L/R support and Blend
0/.08/.2/1; zero hip drop throughout the push, stable pelvis through ascent and
prolonged fall, pinned ankle/reach, continuous nonzero-blend release, and local
animation recovery. Existing 162 support and 15 walk checks also pass.
Receipts: `pelvis-verification.json`, `support-verification.json`.
Cached files only, no NN/Unreal processes or server restart.

## Walk + jump and run push timing - October 24

Sequence now offers Run + jump, Walk + jump and Space. Walk uses the frozen
Walk July5 latest lower checkpoint (8bae21c5b315), the existing Upper 82500,
and matching unarmed/drawn walking seeds. Actual NN forward speed is 2 m/s;
Run stays 5 m/s. Duration and Phase work for either gait; walking phase covers
29 policy samples (about .967 s, based on the accepted 57-game-tick stride).
Trim, frame keys, attacks, support pin/abort, fall and COM follow are shared.
No changes to jump timing or saved tuning. Internal mode `walk` persists.

Default one-second walk variants are cached on disk. Other durations/phases use
one transient, single-thread CPU worker, serialized by the existing lock; gait
is included in both caches. No GPU/training/editor work. Server API version 3.
Only the Bodyflip loopback server was restarted to load the route change.

Earlier measurement, before the procedural pelvis correction above: saved Foot300, alpha.03, Blend.2, Early.1, Phase0:
preparation starts at .900 s, root ascent at .9125 s, support releases at
1.02136 s. Approach .0125 s, pin .10886 s, then support-leg blend .2 s.
While root rises, blending into the authored jump pose lowers the support hip
from .861 m to .676 m over the first .1 s, causing knee flexion then extension
against the pinned foot. This is pose blending plus IK, not a physics delay.
The original .333 s source lead-in remains trimmed. At saved playback .3x,
pin plus leg blend occupies about 1.03 real seconds. `jump-timing.json` records
hip/root heights, knee flexion and timestamps. Behavior was explained, not retimed.

At saved Foot300, walk Auto/L misses contact and aborts as designed; R succeeds.
Walk Auto succeeds at the default Foot800. Tests preserve saved settings.
15 motion checks and 7 browser checks pass (`walk-verification.json`,
`walk-browser-verification.json`); API checks also covered Walk1.2/Phase.5 and
switching back to cached Run. Models/exports are contained in this lab.

## Alpha sensitivity corrected - October 24

Lead now uses `root forward speed * alpha / 200`, keeping the original
root-local support targets and finite-ground clamp. At 5 m/s, alpha 0.1 gives
2.5 mm, 0.5 gives 1.25 cm, and 1 gives 2.5 cm. Numeric settings are preserved.
The interrupted pelvis-anchor/extra-blue-marker changes were reverted: both
larger offsets had correctly saturated at the ledge; no target redesign was needed.
162 cached-run support checks pass, including alpha 0, 0.1, 0.5, 1 and 20.

## Root-speed lead and global frame keys — October 24

**Lead α** controls scaled root-speed lead: `local forward offset = root
speed × alpha / 200`. At 5 m/s, alpha **4** gives **10 cm**. COM velocity, foot
distance and approach speed no longer influence the offset. Both feet get the
same forward shift; root heading carries it, and valid-ground projection still
limits the final target. Saved alpha values are preserved; input step is .01.

**Left / Right** pause and scrub backward / forward by exactly **1/60 s**,
including when a slider, selector, button, checkbox or trim bracket has focus.
Those widgets cannot consume any arrow key; Up/Down are reserved. A focused
writable text/number field, textarea or contenteditable area retains its arrows.
Held/repeated keys accumulate frames; rewind clamps at zero. Manual scrubbing
can inspect outside the trim range; Play and the Step button retain trim bounds.
Brackets remain draggable; arrows now scrub playback rather than moving them.

Verification: 152 motion/lead checks, six grounding checks and 43 browser checks
for controls, editable exceptions, repeats, exact frame times and lead invariance.
The 17 timeline checks also pass with bracket dragging, loop bounds and live scrub.
Receipts: `support-verification.json`, `ground-verification.json`,
`keys-verification.json`.

## Run height correction — October 24

Removed the erroneous **+5.5 cm root lift** applied to the entire run. The NN
gait is already ground-referenced. Run bone heights now match the source exactly;
normal airborne running phases remain. This is a constant-offset correction,
without per-frame ground snapping or changes to animation/IK settings.
`verify-ground.mjs` measures the actual renderer foot/toe boxes: six checks pass
for source heights, stance contact and retained airborne phases across both
cached runs. Stance gaps are within 3.1 mm; pre-existing interpolation dips up to
9.4 mm remain. The 144 support/abort checks also pass.

## Root-relative support approach and missed-edge abort — October 24

The ideal contact is now stored in the root frame at support preparation, before
the finite-ground clamp. Each authored substep carries it with the current root
and finds the closest valid ground point. The foot approaches in that same root
frame at **Foot cm/s**; its world velocity also includes root movement. Lead is
computed once from the preparation pose, avoiding feedback from the moving foot.
Only after contact is reached does the planted foot become fixed in world space.

Locomotion continues during approach: the old reachability-based body hold is
removed. Other limbs use the remaining cached run; after its endpoint, the last
pose continues forward at run speed. No additional NN inference is requested.

Every 240 Hz substep records the actual ankle-to-valid-target distance. The first
increase greater than 0.01 mm cancels the attempt (tiny tolerance for numerical
noise). Contact must still meet Gate and Reach before jumping. On failure, the
HUD shows **ABORT - RUN** until the ledge, then **ABORT - FALL**. IK blends out,
forward momentum continues, and gravity uses the existing fall-speed cap. No
jump-height animation runs on failure. Hover the phase for the failure reason
or current approach gap. Distance history is available in
`BodyflipLab.state.flight.supportHistory` with authored timestamps.

With zero lead, Foot300 / Early.10 launches at .9125 s after 6.25 cm of approach
travel. A zero-lead 10 cm/s case aborts at 1.0125 s as its gap grows. Other alpha
values use the new root-speed formula above. The fixed ledge and plant rules remain.
144 numerical and 27 browser support checks pass, including no hold, target projection,
per-tick distance history, first-increase abort, continuity and deterministic replay.

## Pelvis placement, foot speed units and orbit — October 24

The rendered pelvis box is centered between the two thigh sockets instead of
using the erroneous 7 cm downward offset from the pelvis bone. Its orientation
still follows the pelvis; skeleton, IK and physics bodies are unchanged.

**Foot cm/s** now uses centimetres per second: **800 means 8 m/s**. Approach
movement and lead prediction both convert to metres per second. The default
remains the displayed number 800. Earlier claims that 800 m/s was intentional
were wrong. The former unreachable-target wait is superseded by the moving-root
approach and explicit abort above. Current user tuning is preserved.
Alpha remains uncapped; contacts still clamp to the fixed ledge.

Left-button orbit now inverts vertical dragging. Horizontal orbit, middle-button
pan and right-button target dragging retain their controls. Verification:
122 numerical support, 22 browser support/orbit and 20 editing checks passed.

## Earlier jump, fixed ledge restored — October 24

The automatic ledge movement introduced during alpha troubleshooting is reverted.
The original edge is again `run speed × Run seconds − 0.12 m`, independent of alpha.
Alpha's agreed formula, acceptance of values above 1, and lead readout remain.
The previous tiny response came from the erroneous m/s interpretation, now corrected.

**Early s**, beside Run, starts support preparation earlier by that many authored
seconds. Default **0.10 s**; **0** restores the original timing. Run 1.00 / Early
0.10 samples the cached gait at 0.90 s, chooses support there, and waits for the
existing distance gate before root ascent. The default cached run now launches
after the foot approaches at 8 m/s. The ledge stays put, so preparation is farther back.
Early is limited to leave at least one 60 Hz frame of running. It does not bypass
reach or contact requirements; infeasible gait poses still wait for support.
Changing Early retains the playback time and reuses the prepared run without NN
inference. Click-away and Enter commits remain fixed.

## Editing at the current playback time — October 24

Clicking outside a number field, including on the 3D canvas, commits the edit and
removes its focus. Enter does the same. The canvas previously prevented the
browser's normal focus change, so pending values could remain unapplied.
Support controls, Early, Foot, Blend, Fall cap, Run and Phase rebuild at the current
timeline time instead of frame zero. Paused edits stay paused; support-number
edits made during playback resume from the same time. Cached support edits do
not request NN inference. Reset still explicitly returns to frame zero.

Alpha comparisons now show **Lead … cm** beside the selected support foot, with
requested/applied distances on hover and an **edge** suffix if limited. Actual contact clamps
to the restored fixed ledge. The agreed formula and leg-length limits are unchanged.

`editing-verification.json` covers commits, focus and retained playback time.
`support-verification.json` now has 144 checks including early timing, unchanged
ledge, root ascent, foot gate and the earlier support-motion checks.

## Procedural support foot — October 24

Kinematic remains selected. At Run minus Early, project the pelvis onto the
closest point of the finite platform. Project the left/right hip direction onto
that surface and place two ideal contacts at half the hip-to-hip distance on
either side. Auto picks the foot closest to its corresponding target; Foot L/R
overrides the choice and selects the matching trimmed jump clip.

Each target receives a root-local forward offset: `root speed × Lead α / 200`.
Alpha / 200 is the lead time in seconds; foot distance, COM velocity and foot approach
speed do not enter that calculation. Targets are clamped back onto the actual
platform, including its edge. The ground query exposes a surface normal for a
later wall extension; this version supports the horizontal platform only.

| Control | Default | Meaning |
| --- | --- | --- |
| Reach | 0.99 | Maximum pinned hip-to-ankle distance as a fraction of thigh + calf length. |
| Gate cm | 5 | Maximum remaining foot-to-target distance before jump and plant. |
| Lead α | 1 | Scaled lead time (alpha / 200 seconds); no upper cap. At 5 m/s, 4 gives 10 cm. |
| Foot cm/s | 800 | Procedural approach speed, in centimetres per second (8 m/s). |

The former alpha cap of 10 is removed in both the number field and settings
validation. Larger values can be typed directly. The finite ground edge still
limits the actual contact, regardless of alpha.

The chosen foot approaches at the configured speed while the body advances.
The root-local ideal is reprojected onto valid ground during approach. The body
keeps moving even if contact becomes unreachable; an increasing gap aborts the
jump attempt and continues into a fall at the ledge. The ankle target accounts
for the displayed foot/toe sole clearance; the green ring marks the surface.

At the distance gate, plant **the reached foot position** without a last-frame
snap: the gate also permits up to that much contact gap. At the default speed
the foot approaches at most 3.33 cm per 240 Hz step relative to the root. Root ascent begins only when
the distance gate is met. The foot stays fixed in world space during **PUSH**, with a two-bone
knee solve preserving both segment lengths. At Reach, release it and blend its
local leg rotations back to the jump animation using the existing Blend duration.
Other limbs blend at the jump trigger. Optional Air flip begins after release.

Planning uses the cached run once on control changes; playback and random seeks
sample the same deterministic plan. No inference for support-control edits,
no background IK while paused, and no Unreal or training changes. Saved trim
brackets are preserved. `support-verification.json`: **144 checks**;
`support-browser-verification.json`: **27 checks** including both feet, Auto,
slow approach, abort/fall, distance history, exact kinematic poses and live scrubbing.
Run `node Labs/BodyflipLab/verify-support.mjs`, or open `verify-support.html`.
The old takeoff check entry points route to these replacement checks.

## Playback trim loop — October 24

The timeline leaves room on its right for **Speed**, a 0.1×–2.0× slider (default
1.0×, saved). It changes the whole playback clock immediately without restarting
the sequence or preparing another NN run. Scrub times, trim brackets and Step
remain in authored seconds/frames. Fixed simulation steps and bounded frame work
remain; changing speed clears accumulated wall time to avoid a catch-up hitch.

The playback bar has draggable **[ / ] brackets directly on the timeline**, with
a highlighted range and a compact Loop checkbox next to transport. The separate
In/Out row and seconds fields were removed; the footer is back to 56 px. Hover or
focus a bracket to see its time. Drag the bracket to adjust its endpoint.
Home/End move a focused bracket to its allowed boundary; arrows scrub playback.
Bounds cannot cross. Existing saved ranges
are retained. This control applies to Run + jump; attack Loop remains independent.

**Dragging the playhead updates the Kinematic scene continuously before release.**
Bracket dragging also previews its endpoint. Input is coalesced to the newest
position once per animation frame; it does not queue NN requests or full replay.
Kinematic seeking directly samples the prepared sequence and flip/twist phase.
**Brackets always constrain playback**, even with Loop off: Play starts at In
when outside the range; reaching Out repeats with Loop on, or pauses with Loop
off. Moving a bracket automatically enables Loop. Step also respects Out. Each pass clears
transient attacks/hit state. Sim retains yielding reconstruction when selected.
Paused/hidden windows stop playback and hidden windows cancel pending preview.

`verify-timeline.html` / `timeline-verification.json` cover compact layout, live
input without a change/release event, newest-position wins, bracket adjustment,
range looping and kinematic membership. The old `verify-loop.html` entry redirects
to this replacement fixture; its old receipt is historical.

## Trimmed takeoff — earlier October 24 behavior

Kinematic remains selected and is now the fresh-settings default. Both authored
opposite-foot jump assets were already exported: **Lfoot** and **Rfoot**. They are
separate authored variants, not a newly synthesized mathematical mirror.

Both starts now skip **20 samples / 0.333 s** of preparation. Sampling begins at
the frame immediately before the first meaningful root ascent (5 mm threshold to
ignore export noise). Root height is rebased to that frame, so ascent starts as
soon as Run ends, without a vertical position jump. Apex is now **0.467 s (L)** or
**0.533 s (R)** after the run ends. The platform edge, fall-loop timing and optional
air-flip clock use this trimmed timeline. Blend still controls the run-to-jump pose
interpolation and does not delay the root ascent.

The earlier **Foot Auto** compared the final run pose's left ankle with the trimmed L start's
support ankle, and its right ankle with the trimmed R start's support ankle. It
chooses the smaller 3D distance in a common root-relative frame. Swing-leg/whole-leg
scores and the untrimmed first frames no longer affect selection. **L/R** remain
manual overrides. The status line shows the selected **L support / R support**.

`verify-takeoff.mjs` checks source trimming, immediate rise, blend continuity,
exact source rotations, both overrides, synthetic exact support matches and both
choices across real gait positions. Browser receipt: `takeoff-browser-verification.json`.
No NN inference, Unreal process, asset changes or simulation tuning needed.

## Tracking, kinematic comparison and responsiveness — October 24 correction

**Motion → Sim / Kinematic** restarts the same sequence with the same decoded NN
segment. Kinematic presents the exact target transforms, without a physics solve
or collision response, and follows that pose's mass-weighted COM. Sim retains
physical joints/contact. Both work in Run + jump and Space. Ghost can also expose
the target during simulated playback. Space captures keydown **and** keyup before
buttons, checkboxes, sliders or selectors; holding it does not retrigger. Text
editing retains its normal keys.

The original Run + jump tracking was incorrect for the requested native contract:
it used spring constraint motors, which accumulated angular lag along the chain.
Sim now follows `ProphecyJoltVelocityServo.cpp`'s `CalculateRewrite` and
`PredictCommandFrame`: parent-first predicted angular endpoints, shortest-arc
rotation error divided by the substep, strength 1, and no extra stale target
feed-forward. Only the pelvis gets a positional velocity correction, gravity
compensation and body-origin → COM velocity conversion. Dynamic-mode joint motors
are off; the constraints still enforce hinge/other limits and attachment. Original
Space-mode motors remain. Lab shapes/limits still differ from the native rig.

The same frozen one-second unarmed NN run, before → after mean angular errors:
upper spine **28.10° → 1.60°**, left hand **54.20° → 6.17°**. Hinge/contact-limited
errors remain (left forearm mean **17.47°**); this is not perfect pose matching.
`inspect-tracking.mjs` and `tracking-before/after.json` retain the evidence.

The sword now caches its fixed geometry/normals and transforms each unique vertex
once per draw; GPU buffers reuse capacity. Source local transforms are cached for
sampling; jump-height derivatives no longer evaluate the whole skeleton. HUD text
updates at 10 Hz during play. Physics remains 240 Hz. Catch-up is bounded to three
60 Hz ticks per render callback. Decoded NN segments are cached in the browser,
so blend/foot/cap/reset changes reuse the existing segment. Equipment changes
prepare the matching unarmed/drawn segment. Timeline dragging previews the time;
release reconstructs simulation in short yielding batches so the UI stays usable.

Measured with `profile.html`, 60 frames after 10 warm-up frames at the same 1000×700
viewport and sword selection: mean **22.40 → 9.38 ms**, p95 **25.30 → 12.80 ms**,
maximum **42.50 → 14.90 ms**. This includes physics, rendering submission and test
diagnostics; it is a local measurement, not a GPU-present FPS guarantee. Cached
Reset measured **3.5 ms**. Paused/hidden behavior and transient NN workers remain.

`verify-comparison.html`: **27/27** focused checks (exact kinematic poses, COM,
Space ownership/repeat/release, dynamic membership, cached reset, yielding seek,
fall, Space mode and runtime errors). Real browser Space presses from a focused
Step button also toggled Play/Pause correctly. Updated twelve-second physics test:
max anchor **4.111 mm**, pelvis position **1.172 cm**, pelvis angle **19.05°**;
12 m/s cap respected. Previous 16/39 check receipts below describe the earlier
version; the sequence fixture now awaits asynchronous scrubbing.

## Run / jump / void — base October 24 implementation

The default **Run + jump** mode runs forward for **1 s**, blends into an actual
GASP running-jump start, follows its root's upward arc, and falls indefinitely
past a physical platform edge. The camera follows the **mass-weighted simulated
body COM**, including vertical motion. No ground exists below the platform.

| Control | Behavior |
| --- | --- |
| Run | 0.1–5 authored seconds; default 1. Releasing a sequence slider rebuilds the run at the current playback time. |
| Phase | 0–100% of a full forward-running stride (38 game ticks / 19 policy frames); 100% wraps to 0. |
| Blend | Run-to-jump pose interpolation, 0–1 s; default 0.2 s. Root rise remains authored. |
| Fall cap | Downward speed limit, 2–50 m/s; default 20. Also clamps actual mass-weighted body COM downward velocity. |
| Foot | Auto chooses the nearest procedural ground contact; L/R overrides. See support controls above. |
| Air flip | Off by default for reviewing the jump. When enabled, existing flip/twist clocks begin at physical lift-off. |
| Space | Select the original stationary, zero-gravity experiment. |
| Timeline | In Run + jump, pause and deterministically replay physics from the start to the requested time. |
| Target Reset | In Run + jump, bring the draggable target near the current pelvis. XYZ accepts positions beyond the original ±5 m area. |

**Networks:** immutable copies of installed **Run 181751** and **Upper 82500**
PyTorch checkpoints, verified against their installation hashes. `locomotion.py`
uses the original Stepper encoder/decoder and real CPU network evaluation at
30 Hz. The lower network generates one continuous run; upper inference is
conditioned on that lower output, neutral gaze, and the selected attack's sword
equipment state at preparation. The lower has two seconds of settling; upper
has one stride of warm-up. Forward speed is the seed's **5 m/s**. Settings changes
request a finite NN segment, which the browser then feeds to Jolt at 240 Hz.
This is **not a recorded gallery loop**, and no network is retrained. It is also
not an online policy receiving physical feedback: recurrence uses accepted NN
poses. An uncached request starts a single-CPU worker which exits after preparing
the segment; the server retains at most four segments, not Torch or NN models.
Default 1 s / phase 0 unarmed and sword runs are already prepared. An uncached
request took 16.9 s under current laptop load; its cached repeat took 12 ms.
The idle server measured 18.5 MB. No inference runs while paused, and hiding the
window pauses playback. One worker at a time keeps preparation contained.

`models/provenance.json` records original checkpoint/seed paths and hashes.
The small frozen models and seeds are stored under `models/` (ignored by Git).
The existing local Stepper Python 3.10/Torch runtime and encoder/decoder sources
remain a read-only dependency; Python bytecode writes are disabled for that import.
The loopback server adds only `/run`, serialized in its own inference lock.
No training process, remote GPU, model pointer or installed Unreal model changes.

**Sim mode 0:** the journal's magnetization mode **0** is parent-relative;
mode 1 is world-relative. This lab implements that requested arrangement using
**25 dynamic Jolt bodies**, parent-relative angular velocity tracking, 24 physical joints, and one
world-space pelvis velocity servo. It reuses the native mode-0 control principle;
it does not load or claim exact tuning parity with the native Unreal adapter.
There are no independent limb position magnets. Gravity is 9.81 m/s²; joint
limits, mass profile and motor strengths are the existing lab profile. Only reset
or explicit scrub reconstruction teleports the body. Ordinary play stays dynamic.
The descent cap applies a uniform linear velocity correction to all bodies,
preserving their relative velocities and angular motion.

**Jump sources:** `data/jumps.json` contains 60 Hz component-space samples and
source `.uasset` hashes for:

- `/Game/Characters/UEFN_Mannequin/Animations/Jump/M_Relaxed_Jump_F_Start_Run_Lfoot`
- `/Game/Characters/UEFN_Mannequin/Animations/Jump/M_Relaxed_Jump_F_Start_Run_Rfoot`
- `/Game/Characters/UEFN_Mannequin/Animations/Jump/M_Relaxed_Jump_Loop_Fall`

The original starts rise approximately **1.033 m** in root space. The current
trim removes their first 0.333 s; apex times are 0.467 s and 0.533 s after Run
ends. The platform edge and lift-off use the run boundary.
After the apex, a continuous ballistic trajectory takes over and reaches the
chosen terminal speed. The start pose crossfades into the fall loop over 0.25 s
near the end of the start clip. Both animations' root translation is removed
from the posed body before applying that one trajectory, so the fall loop's
authored downward translation is never added a second time.

Epic describes GASP as using motion matching and character state to choose
locomotion/jump/fall animation. This lab explicitly selects the three assets;
it does not recreate the whole GASP chooser/motion-matching graph.
[Official GASP documentation](https://dev.epicgames.com/documentation/unreal-engine/game-animation-sample-project-in-unreal-engine).

The Unreal editor was closed. Remote discovery was attempted without a live
node; `export_jump.py` sampled assets in a separate, content-only headless project,
with no gameplay C++ modules, PIE, build, or asset saves. Exported transforms and
source hashes are independently checked. The temporary project's dependency
loading also reported unrelated content/config diagnostics; those are not
gameplay-project build failures or claims that the entire content project validates.

`verify-flight.mjs`: 12 simulated seconds, root rise, indefinite descent, terminal
cap, finite poses, joints, and switching back to Space. Latest maximum anchor
error **4.111 mm**, pelvis target error **1.172 cm**, pelvis angular error **19.05°**,
12 m/s test cap respected to
float precision. `verify-sequence.html`: **16/16** browser integration checks,
including phase, duration, blend/scrub, COM camera, low cap, flips and airborne
attacks. `nn-verification.json` covers 0.1 and 5 s generation at endpoint phases.
Original 320-clip physics verification and **39/39** browser regressions also pass.
Test fixtures restore saved settings and must not run while the user edits the lab.

## Controls

| Control | Action |
| --- | --- |
| Flip grid | 12 directed horizontal axes, at 30-degree intervals. Back, Front, Left, Right and eight intermediate directions. Selection starts that flip at zero angle. |
| Flip Speed / Angle | Signed degrees per second; direct angle adjustment. Zero speed holds the flip. |
| Pelvis twist | Separate angle and signed speed around the pelvis's own vertical axis. This axis follows the flip. Zero clears only twist. |
| Attack / 01–20 | All 16 existing melee/sword families, with 20 variants each. |
| Attack / A | Start the selected attack and playback. Does not restart the flip. |
| Cancel / Loop / Rate | Return to idle, repeat attacks, or change attack playback rate independently of rotation. |
| Aim | Optional bounded joint aim correction toward the target. Slider controls its strength. |
| Right-drag | Move the target in the camera plane. Works anywhere in the viewport. |
| Shift + right-drag | Move the target along camera depth. XYZ and radius are also editable. |
| Left-drag / middle-drag / wheel | Orbit / pan / zoom. Double-click or View resets the camera. |
| Play / Space | Start or pause; ordinary playback flips the idle body until Attack is pressed. |
| Step / right arrow | Advance one 60 Hz authored tick, including four physics steps. |
| Reset / R | Stop, return to neutral angles/idle and retain speeds, target and selected attack. |
| Timeline | Pause and inspect an attack pose at the current flip/twist angles. |
| Ghost / Two-tone / Bones | Desired pose, the D/S limb orientation colors, or skeleton display. |
| Save / Refresh / Snapshot | Save settings, reload local code, or save the viewport PNG plus exact pose/settings JSON. |

The pale gold endpoint marks the active strike point. The target turns green on
a detected hit; **Miss** reports the closest surface separation for the current
attack. These are lab geometric measurements, not Unreal's Armed/Hit signals.

## Reuse and isolation

- `renderer.js` and `recovery.js` were copied from `Labs/SwordHolsterLab`.
  The renderer retains the D/S body, face, limb shading, camera math and WebGL
  geometry. Its camera pivot and camera basis export are the two base-renderer
  changes. `reuse.json` records original hashes.
- All 320 existing full-body attack recordings and the sword mesh were copied
  from `Labs/AttackRecoveryLab/data`; recorded clip hashes are checked unchanged.
  This lab samples and returns **every body joint**, including both legs.
- New UI, target handling, animation controller and physics live only here.
  There is no import of another lab's mutable state, shared server endpoint,
  native build, gameplay asset edit or training request. Jump assets were sampled
  read-only as described above.
- `state.json` and `snapshots/` belong only to this lab. Launching checks port
  ownership before opening. Browser profile: `%LOCALAPPDATA%/BodyflipLab`.
- Refresh is user-operated. Pausing/hidden tabs stop animation and physics;
  there is no polling, timer-driven skeleton work or cloud compute. NN inference
  occurs only when preparing an explicitly requested run segment.

## Physics and aiming

Jolt Physics JS **1.1.1**, single-thread WebAssembly, is vendored in `vendor/`.
The official npm tarball SHA-512 was verified. License and package/module hashes
are retained. Upstream: [JoltPhysics.js](https://github.com/jrouwe/JoltPhysics.js),
[constraint examples](https://github.com/jrouwe/JoltPhysics.js/blob/main/Examples/constraints.html).

In **Space** mode there are **25 rigid bodies and 24 real Jolt constraints**. The pelvis is
kinematic and rotates analytically at the requested speeds; the other 24 bodies
are dynamic. Knees and elbows use four limited Hinge constraints; the remaining
20 joints use limited SwingTwist constraints and position motors. Motors use
50 Hz critical damping and 2000 Nm caps. The neutral posture tracks the rotating
pelvis; it is not a rigid visual overlay of an unconstrained skeleton.

In **Space** mode gravity is zero, physics is 240 Hz, and pelvis position stays at `[0, 1.5, 0]` m.
The floor is a visual reference. Lab coordinates are X/Z horizontal and Y up.
Flip axes are fixed relative to the initial facing direction; positive Back
tips the torso backward. Twist is about the current pelvis local X bone axis
(its vertical axis), not a fixed world-up spin. Attack rate never retimes either
rotation controller. Physics updates and motor changes happen only when playing,
stepping, or explicitly reconstructing a paused pose.

The capsule geometry, masses, motor strengths, collision exclusions and angular
bounds form a **dedicated lab profile** around the shared idle pose. This is not
an exact import of the current game PHAT or its native Jolt DLL. Overlapping torso,
shoulder and adjacent-chain shapes are filtered; separate limbs still collide.
Knee bounds represent approximately 0–150 degrees of anatomical bend, relative
to the slightly bent idle reference. Elbows similarly allow 0–155 degrees.

Source clips drive local motor targets across the whole body, with the authored
pelvis rotation removed so it cannot change the chosen flip clock. Aim uses three
bounded CCD passes on the selected strike chain, with small distributed spine
correction for hand/head attacks and hip correction for kicks. The hinge axes are
never replaced by unconstrained knee/elbow rotations. The Jolt solver enforces
the physical joint limits. Aim is experimental steering, not a promise that an
arbitrary target is reachable during every flip phase. No NN was retrained.

The sword remains the existing hand-attached visual mesh; hit checking uses its
blade segment and swept endpoint. Melee uses the selected hand, foot or head
endpoint. The target is a movable non-blocking aiming marker, not an impact prop.
Hits include a 2.5 cm strike-point tolerance. Scrubbing reconstructs and settles
the requested constrained pose; it does not replay a recorded physics history.

## Verification

Run `node Labs/BodyflipLab/verify.mjs` from the project root. It checks all 320
source hashes and decodes, all 12 flip axes with independent twist, every attack
family through real Jolt, full-body return, aim response, finite poses, joint
anchors, knee/elbow limits and neutral tracking. The latest receipt is
`verification.json`. Initial final-profile run: maximum anchor separation
1.536 mm, hinge-bound excess 0.053 degrees; all checks passed.

Open `verify.html` and press Run checks for the separate browser fixture. It
exercises the production controls, 60-tick clock increments, grid switches,
right-drag/depth/orbit pointer handlers, all 16 attack selections, scrub and
cancel. It uses synthetic pointer events for deterministic dragging and restores
the saved settings afterward. Do not run it while another user edits this lab.
This fixture is separate from the normal application UI.

`install_shortcut.ps1` reinstalls the desktop shortcut with the local purple/orange
bodyflip icon. The launcher uses the existing Python 3.10 runtime and Edge or
Chrome. It does not start, close, build or save an Unreal project.
