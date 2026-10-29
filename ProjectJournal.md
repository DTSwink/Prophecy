# Prophecy — current handoff

Updated **October 19, 2026**, after static-fuse verification. This file and the current sections of linked topics take precedence over dated archives.

## Resume here

**Main-menu scene October29 — real horizontal smoke width and checkpoint:**
Air Horizontal width replaces the ineffective Spread slider with0.25–8x actual
source scaling on world Y. Native Grid3D_Gas_SphereSource Non Uniform Scale is
linked to User.SmokeSourceScale=(1,width,1); vertical/depth radius and source
velocity stay unchanged. New smoke_horizontal_width defaults1, preserving saved
source shape; legacy haze_spread remains as compatibility baseline. Grid grows
only to fit the widened source plus450cm each end; resolution tracks previous
cell size with512-axis cap. Resizes debounce300ms; source-only changes keep the
field, domain changes reset gas once and need seconds to reform.
Normal build and Niagara CPU/GPU preparation pass. Native source/grid bounds,
unchanged vertical/depth dimensions, save/reload and existing controls pass.
1x/4x/8x captures visually verify widening; at8x source radius227.87cm unchanged,
grid Y4545.916cm versus2884.702cm at1x. Curated receipts in the lab's Verification/.
SaveLive preserved user rain_amount4, smoke shift7.4628cm and current water tuning
before closing28136. Resources/scene.json matches Saved/SmokeWidth20261029/live-saved.json.
Review20344 reopened on Air; current ready status in UI handoff. User requested
push: curate this isolated scene, its required content, settings and handoff only;
exclude all other workstreams and generated caches/recovery files.
[Current UI handoff](Docs/WeaponWheelUI.md).


**Foot IK October28 - accepted wall-gait checkpoint:**
User approved the corrected wall ground frame, pelvis height and signed NN knee
hinges. Includes prior terrain, yaw/distance, root gravity, platform editing,
persistence and actual-root recurrent NN work, with focused sources/fixtures.
Walk uses the Run checkpoint at walking velocity.15 frame/hinge,17 coupling,
697 surface,101 endpoint and1368 shared-adapter checks passed. Profile captured
in Labs/FootIKLab/approved/2026-10-28/profile.json; live state is excluded.
NN weights/runtime dependencies remain as documented in the lab README.
Late unbounded-speed falling is outside a trained locomotion gait.
[Current lab handoff](Labs/FootIKLab/README.md).


**Throw Lab October27 - approved throw checkpoint:** standalone lab and exact
user-approved scene library saved in `Labs/ThrowLab/approved/2026-10-27/`.
Includes both source FBXs (cache hashes verified), runtime animation/object
caches, Jolt, tools, desktop launcher and complete saved tuning/undo history.
Current big throw uses Imperial Spear with Throw F34. Whole-frame rotation
editing, quaternion interpolation, Ctrl precision, inline axis readout, fixed
world target, free/orbit camera and1x playback cap included. Source and focused
mouse/physics checks pass. Snapshot inventory verifies the selected commit.
Aerodynamic investigation is separate; approved projectile behavior unchanged.
See [lab handoff and restore steps](Labs/ThrowLab/README.md).


**Bodyflip October27 - approved kick and attack-entry checkpoint:**
User approved full-body airborne kicks, pelvis-only post-Hit recovery and
Direct to Armed for all16 attacks. Viewer, timeline and manual paths share the
same motion. The existing viewport checkbox (after Raw leg) skips pre-Armed
motion, reaches Armed no earlier than authored timing, then retains the native
strike/follow-through. Upper14 retain opposite-angle compensation and inertial
legs; kicks retain recorded striking-leg dynamics and articulated balance.
2596 all-attack direct-entry samples,1182 direct-kick samples,1314 original-kick
samples and84 off-mode cases/5100 samples pass. Manual variants/rates/aim,
moving baseline, COM/hinges, native upper motion, Armed continuity and seek
checked.90 sequence checks pass;32 overlaps2764ms. Scoped source/tests/receipts,
viewers and docs only; live scenes, screenshots, unrelated work remain local.
No desktop/browser control or Unreal/NN/server restart. User Refresh loads it.
Recovery inventory regenerated for the approved checkpoint on codex/standalone-sim.
[Current details](Labs/BodyflipLab/README.md),
[prior notes](Docs/Journal/Bodyflip-2026-10-27-pre-checkpoint.md).

**Bodyflip October25 - approved motion checkpoint:** user accepted the knee fix
and requested a push. Includes Idle/shared jump controls, flat new scenes, capsule
collision with actual NN landing continuation, free camera, matched whole-body
jumps, opaque animation-leg overlays, motion-preserving blends and knee braking.
Walk frame59 now bends28.67deg normally instead of71.66deg backwards; no straight
hold or repeated recoil, original blend deadlines/contact/root retained.265
automated checks pass. User accepted the result; agent visual tools were blocked.
Source, idle recording and verification files are included; live scenes/settings,
previews, inference caches and unrelated sessions stay local. Landing requires the
existing frozen models/seeds and Stepper/Torch runtime; see restore notes.
[Bodyflip details](Labs/BodyflipLab/README.md), [recovery](Docs/Recovery.md).

**Foot IK October25 - approved checkpoint:** standalone Foot IK Lab preserved
with frozen Walk/Run NN phase banks, terrain placement, grounded heel/toe pins,
smooth swing recovery, full-body/ghost rendering, desktop launcher and regression
fixtures. Includes gentler right155 toe-off (35deg on NN-return departures,
45deg on retained-contact transfers);307 checks passed. Live playback state,
screenshots and unrelated session work excluded. Pelvis stair-transfer work
starts AFTER this checkpoint; see Labs/FootIKLab/README.md for current behavior.

**Bodyflip October25 - named scenes and curated checkpoint:** added scene picker,
Copy and Rename after existing header controls. Legacy current setup becomes
Inclines. Copies retain tuning/platforms/jumps/target/camera/playback/brackets and
start paused; switching saves outgoing work then reloads the selected scene.
Library stored locally in state.json, current state kept top-level for compatibility.
Save writes serialize; failure leaves current scene open. Reload isolates undo.
Current user setup also preserved in tracked saved-profile.json. Scenes16,
refresh14, pacing24 checks pass; visual QA unavailable (kernel-assets error).
Refresh required. Bodyflip source, focused tests/receipts, fixture, saved profile
and Bodyflip-only journal updates prepared for requested push; unrelated Unreal,
FootIK, training and audio work excluded. No new process, server restart or
Unreal activity. [Controls and restore](Labs/BodyflipLab/README.md).

**Bodyflip October25 - anticipate pelvis reach during foot approach:** user
requested slowing the foot before it spends available extension, retaining
root-local motion. Foot cm/s is now a maximum. Each prepared step measures
remaining travel inside the selected reach sphere and estimates time until the
plant target is reachable using one frame of existing incoming body motion.
Travel is paced over that interval; no new option, gate or root/pelvis path edit.
Saved Phase.30/Load50/Foot400/Reach.99 markers F53/F95/F125 all now push; third
captures F137.25, versus previous Distance-growing abort F136.75. Approach max
hip-ankle79.01cm <80.63cm limit; no sampled sole penetration or bone-length error.
Pacing24, selection37, alignment36, bounce140 checks and syntax pass. Cached
three-jump preparation about120ms, no added playback integration/inference.
Tooltip and diagnostics explain/report pacing; control layout/settings retained.
Refresh required; visual QA unverified. No Unreal/training/server work or push.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - compare feet after cone constraint:** selection retains
ankle-to-planted-ankle metric, now against each foot's cone-constrained contact,
not its theoretical ideal. Original ideal distance retained for approach rotation
timing; no new gate, fallback or exception. Phase tooltip labels post-cone scores.
Frozen reported F146/Load50 pose picks R3.53cm versus L31.53cm (old ideal metric
picked L47.47cm versus R55.07cm). New rule also changes FIRST jump to grounded L,
capturing at F53 instead of later. Therefore saved F115/F146 now MISS after the
different first launch; markers/tuning deliberately unchanged. Do not claim all
three saved jumps still succeed or silently add an exception to keep old motion.
Selection37, alignment36, bounce140 and syntax pass. Small frozen incoming-pose
fixture preserves the reported regression independent of upstream flight changes.
Refresh required; visual QA unverified. No UI moves, saved-state changes, Unreal,
training or server work, commit or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - remove unrequested penetration rejection:** removed the
hardcoded signed-height cutoff from cone validity; no replacement depth threshold.
At saved F115 the right foot is34.3cm from its ideal versus left56.5cm, but its
lowest shoe corner is9.5mm inside the incline. The old5mm cutoff wrongly excluded
it. Jump2 now selects R/left incline and captures immediately at F115, followed
by LOAD/PUSH. Existing distance trigger, finite surfaces and reach retained.
All original three markers succeed. Selection34, bounce148, alignment47 and
contact40 checks pass; syntax checked. Prior tests that required R rejection
were validating the bug and have been corrected. Refresh required; no saved
state/tuning/marker/platform changes, UI additions, Unreal work or push.
Standing user instruction: implement requested behavior without inventing gates,
fallbacks or exceptions; ask about ambiguity and explain proposed changes first.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - centered gizmo / continuous contact alignment:** platform
gizmo and transform pivot now use slab center; orbit clears selection, including
an older selected slab. Scale axes remain local. Captured shoe bank continues
leveling through LOAD/PUSH, with moving sole pivots and the same ankle trajectory
in loading physics and IK. Retains captured pitch; existing heel/toe speed starts
at PUSH. Both ideal rings now shown (green selected/red other), smaller green
contact ring; phase tooltip gives selection-time distances/eligibility. Saved
jump3 selection was correct before edits (L50.1cm/R60.4cm), so selection rule kept.
Original three markers still push floor/left/right; jump3 bank dot normal goes
from0.731 to0 before release, no sole gap or bone-length error in sampled contact.
Alignment47, bounce148, selection23, platform101, contact40, skew105, arrow18
checks pass. Cached preparation about50-70ms; no new options/processes/inference.
Visual tools fail with kernel-assets os error3; refresh lab to load. Saved state,
markers/platforms/tuning untouched; no Unreal/training activity or push.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - jump2 surface/foot mismatch:** surface availability used
either foot's cone, then planner could choose the invalid other foot. Shared
candidates now choose an eligible foot by own-ideal distance per surface, then
rank surfaces by that foot's actual contact gap. Unreachable valid-cone slabs
excluded; explicit overrides retained. Saved F115 picks L/left incline23.0cm,
versus R/right29.4cm; all three ORIGINAL markers succeed. Earlier F114 retiming
advice is superseded. Selection23, bounce148, contact40 pass; syntax checked,
visual QA unavailable. Refresh required. No saved settings/platform/marker edits,
Unreal/training work, new process or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - loading/rebound prototype:** implemented kinematic pelvis
spring loading with incoming momentum+gravity, pinned foot, then finite-duration
drive and ballistic release. LOAD precedes PUSH; jump blend, roll and arrow wait
for extension. Two options appended after Translucency: Load ms100 (0 restores
old launch), Rebound50%. Geometry/energy/stiffness bounded; root path replaces
clip height, no double launch.148 focused checks; Load0 platform93/skew105/arrow18
and refresh14 pass. Cached three-jump preparation about42ms; visual QA unavailable.
Saved second marker F115 now misses; read-only F114 trial makes all three succeed.
Markers/settings/layout not overwritten. Refresh required. No Unreal/training,
new process, server restart or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - forward foot on inclines:** plant heading now comes from
anatomical pelvis forward, flattened then projected onto the surface; imported
jump root +Z was lateral. Pitch/roll retained with corrected roll axis. Saved
frame151/jump3 capture heading error2.28deg; heading58, target71, contact39,
schedule136, cone88, skew105 pass. Visual QA unavailable. Refresh required;
no tuning/marker/platform reset or Unreal/training work. Bounce remains a proposal:
spring/damper pelvis loading under incoming momentum+gravity, then extension,
bounded compression/rebound; no bounce implementation yet.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - inclined alpha / knee / frame diagnostics:** alpha uses
incoming root velocity projected onto the selected surface, scaled by1/200;
root-local carry and finite bounds retained. Red circle shows the other foot's
ideal; green remains actual selected contact. Knee bend pole follows pelvis/aim,
thigh and calf share a hinge plane. F counter beside seconds is zero-based60Hz,
updated before HUD throttling. Saved frame149 reproduced; corrected jump3 selects
R60.7cm versus L63.9cm (previous L73.8/R77.6). No marker/tuning reset. Target71,
contact39, schedule136, skew105, cone88, platform93, arrow18, refresh14 pass.
Cached data only; live browser visual QA unavailable. Refresh required. No Unreal,
training or server activity. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - platform side translucency:** More options ends with
Translucency %, default80; sides/undersides blend, local walkable tops stay
opaque from the front. Top backs/grid omitted when viewed from underneath.
Sorted transparent pass retains depth testing, disables depth writes, restores
render state. Appearance-only edit, persists without replan/pause.25 focused
checks plus platform93 and syntax pass; live GPU visual QA unavailable.
Refresh to load. No physics/layout/tuning reset or Unreal/training changes.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - Refresh playback / alpha step:** app Refresh saves time,
playing state, attack time, runtime angles and hit readout before pausing; boot
restores after flight setup. Authored angles stay separate to prevent double air
rotation. Queued previews/delayed saves cancelled before reload; trim/speed/camera
preserved. Alpha native numeric step now1 (fractions still typeable). 14 focused
checks and syntax pass; visual QA unavailable. First reload loads this feature;
older running code cannot snapshot its unsaved playhead. No live-state overwrite,
Unreal/training/server action or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - sole orientation / second-push momentum:** foot and toe
frames use anatomical rig signs, replacing world-Y flips. Query geometry and
rendered boxes agree; inverted nearby capture aligns sole-first. Saved third
contact foot-only regression changes from inverted up dot normal=-0.959 to
+0.861. Incoming velocity now retains only motion tangent to BOTH physical
surface and skewed push axis, superseding the earlier push-axis-only rule.
Jump2's carried surface-normal component is zero. Corrected trajectory makes
the existing third marker miss (Distance growing); timings preserved. Contact37,
motion105, schedule136, platform93 and arrow18 checks pass. Cached NN data only,
visual QA unavailable. Refresh required; no saved-state reset or Unreal/training.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - trim preview return:** bracket drags retain their live
boundary preview, then restore the pre-drag playhead on release/cancel/lost
capture. New trim bounds remain; pending preview callbacks cannot override the
return. Seven handler checks and syntax pass. Refresh lab; no saved-state reset.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - Up skew COM trajectory fix:** retained incoming velocity
now uses the effective skewed push axis, not the physical surface normal. Old
slope projection converted downward arrival into sideways drift even at100%.
100% now matches flat-ground root/pelvis motion for identical incoming velocity
and clip, retaining horizontal momentum;0% is unchanged. Physical contacts/IK
still use the actual surface. Measured45-degree-slope drift0.20m over0.1s removed.
102 trajectory checks, arrow18 and platform93 pass; live visual QA unavailable.
Refresh required. No tuning/layout reset, inference, Unreal/training or push.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - Show jump:** checkbox appended after Cone, persisted and
off by default. Large yellow1.4m arrow starts at support contact and follows
actual authored push direction including Up skew. Visible for3 frames at60Hz
from push onset, determined by playback time for pause/seek/loop consistency.
Misses draw nothing. Reused overlay mesh, no timers or replans. 18 focused checks
and syntax pass; browser visual QA unavailable. Refresh and enable Show jump.
No Unreal/training/server activity or saved layout reset.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - immediate platform gizmo:** user clarified the complaint
was elapsed click-to-gizmo time, not drag distance. Gizmo now previews on mouse
press without waiting for release or pausing playback. A completed click pauses;
orbit/cancel/lost capture restores the previous selection. Original4 CSS-pixel
jitter threshold restored, undoing the mistaken4-to1 change. No Alt required;
gizmo transforms unchanged. 93 focused checks plus syntax pass; live visual QA
unavailable. Refresh lab. No saved layout/tuning reset, Unreal or training activity.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - distinguish gizmos:** W Move now has large arrowheads
and a round center; R Scale has outlined square endpoints and a square center.
Colors/orientation/interaction unchanged. Syntax and82 checks pass; visual QA
still unavailable. Refresh lab for appearance update. Lab-only, no state reset.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - W gizmo keyboard fix:** platform W/E/R and Ctrl+Z now
use printed letters, fixing physical W/Z mapping on AZERTY. Viewport/gizmo
pointerdown transfers focus to canvas, leaving dropdowns and committing numeric
edits. Writable controls retain editing shortcuts. R gizmo remains local;
W/E remain world. 82 focused checks pass, including visible Move handle output
and focus routing; browser visual QA unavailable. Refresh required; no saved
layout/tuning change, Unreal/training work or push.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - platform reset / Ctrl+Z:** user-requested saved layout
reset to original floor and both45-degree ramps; all other state preserved by
/state readback. Backup: Saved/BodyflipLab/platforms-before-reset-20261025.json.
Startup reset version prevents an older tab's Refresh save from restoring the
old layout; subsequent edits persist. Ctrl+Z undoes one completed transform,
up to100 in-session operations; cancels active drag, ignores no-op drags, retains
text-field undo and playhead. Add/delete are outside transform history. 72 focused
checks and syntax pass; browser visual QA still unavailable. Refresh lab once.
Contained lab-only changes; no Unreal/training/server restart or push.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - platform editor / upward push skew:** + Platform below
phase at viewport top left; click a slab for gizmo. W move, E rotate, R scale;
Delete/Backspace remove, Escape cancels/deselects. Text editing retains its keys.
Gizmo pivots at clicked point to stay accessible on long ramps. Alt-left-drag
orbits over geometry. Preview during drag, single replan/save at release with
playhead retained. Layouts persist, including empty scenes. Wheel dezoom cap
removed and clipping expands with distance. More options ends with Up skew %,
default50: authored wall push45 degrees toward up; incoming tangent retained.
50 focused platform/wall/zoom checks plus136 legacy-skew schedule and19 marker
checks pass. UI runtime still fails initialization, so visual QA unverified.
No live-state overwrite or Unreal/training activity. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - ramps and manual jump markers:** two finite45-degree
ramps form a V beyond the ledge. Support cones, sole clearance/roll, rendering
and Jolt share oriented surfaces. Repeated scheduled pushes continue incoming
motion; missed contacts add no lift. User confirmed markers start SUPPORT,
then contact starts PUSH. UI correction: markers are on the EXISTING playback
bar, with + Jump beside Loop at the START of the timeline (same-sized mouse
target as transport buttons). User rejected the far-right placement: keep
related actions near their working area. Select a marker for time/Delete;
no second timeline, After or Gap controls. Preserve this minimal UI.
136 geometry/motion and19 control checks pass, including three successive
pushes; previous cone88/blend33/abort36 checks pass. Browser layout remains
unverified because both UI runtimes failed at initialization. Tuning/camera
preserved, no Unreal/training/server action or push. Details/receipts:
[Labs/BodyflipLab/README.md](Labs/BodyflipLab/README.md).

## October 24 - Bodyflip curated Git checkpoint

User requested pushing the lab. Checkpoint includes Bodyflip code, Jolt runtime,
attack/jump recordings, exact phase banks, verification scripts/receipts and
saved-profile.json (tuning/camera snapshot). Live state, local model copies,
temporary exports and full captures remain local. Only Bodyflip journal sections
are staged; concurrent Unreal/training/other-lab work stays outside this commit.
Restore instructions: [Bodyflip README](Labs/BodyflipLab/README.md) and
[Recovery](Docs/Recovery.md). Existing split-blend33 +browser6 checks passed;
no new build, inference, editor action or process restart for the checkpoint.

## October 24 - Bodyflip separate Body / Leg blend durations

Sequence now exposes Body (existing jumpBlend) and Leg (new legBlend), seconds
0-1. Body starts at PUSH; Leg starts at contact release. Pelvis stays procedural,
pin timing unchanged. Body blend excludes support chain with Match foot on/off.
Old saved Leg inherits Body (.2s currently); zero supported. Edits retain time.
33 numerical +6 browser checks pass; settings/camera preserved. Lab only, no
NN inference, Unreal changes or server restart. [Details](Labs/BodyflipLab/README.md).

## October 24 - Bodyflip SUPPORT upper-body freeze investigation

Current saved Phase.67/Foot500/Lead6/Roll400: SUPPORT .900-.945833s.
Compared 21 samples against unmodified NN locomotion: all joints outside the
support leg match within numerical precision (position <5e-16m, angle <7e-14deg).
Arms move4.41/5.46deg during approach. No SUPPORT freeze in this setup; no motion
change warranted. PUSH starts the existing .2s smoothstep blend from a held
takeoff pose, so upper-body angular motion eases in there (left upper-arm local
change .00276deg at1ms, .272deg at10ms). This can read as a pause at PUSH.
Verification is specific to this saved setup, not a claim about every tuning.
Receipt: Labs/BodyflipLab/support-locomotion-verification.json. State untouched;
no NN inference, Unreal work, or process restart.

## October 24 - Bodyflip forward foot approach / configurable heel roll

Support foot turns root-forward toward Plant10 degrees heel-up while approaching.
More options: Plant(-25..35), Toe-off35 degrees(0..60), Roll720 degrees/s(0..3600).
Zero Roll holds landing angle. Rotation adjusts for ground clearance; ankle speed
is unchanged. Actual sole contact must fit on platform, so ankle clamps back at
edge. Push rolls around sole contact (ankle moves); marker follows contact.
Release obeys reach/ground, then live blend/frame matching uses final rolled pose.
Saved phase.67/Foot500/Lead6:10 to35 degrees over53ms pin. Slower roll may release
before35. Some forced late plants now correctly abort; comparison tests useEarly.3,
userEarly.1 preserved. 294 roll +80 matching +10 browser checks pass. Speed edits
keep frame and take21ms; saved camera/tuning retained. NoNN/UE/server restart.
[Details](Labs/BodyflipLab/README.md).


## October 24 - Bodyflip phase stalls / planted sole contact

Phase was applying correctly but uncached requests took 4.55s because /run
started fresh NN inference. Phase/duration playback now reads exact precomputed
binary NN rollouts (all Run/Walk phases, both equipment states, through5s).
Server API4 removes runtime worker launches; export is one-shot single-thread CPU.
Original phase seeds/warmups preserved; three recorded Run phases match exactly.
Support no longer freezes at the distance gate while hovering: also requires
actual sole contact, retaining approach speed/reach/root advance/abort. Current
phase.67, Foot500: 4.84cm gap fixed, jump12.5ms later. Nine renderer-contact cases,
80 matching and162 support checks pass. Browser edits11-30ms; API10-63ms.
All100 cached rollouts validated; ten browser checks pass. Export exited; only
Bodyflip server restarted toAPI4. Current user tuning/camera retained. [Details](Labs/BodyflipLab/README.md).


## October 24 - Bodyflip gait phase clarification / verification

Phase selects the gait starting pose; user confirms the rest is working.
Verified 0 versus .44 through the UI handlers at time zero: displayed poses
differ by up to .67964m root-local, four checks pass. Also verified at .5s.
No runtime changes warranted. Phase applies on slider release and preserves
current playback time; it does not scrub the jump animation. Saved state restored.
Receipt: Labs/BodyflipLab/phase-verification.json.


## October 24 - Bodyflip playback timeline focus fix

Removed the focus guard that froze the timeline thumb after scrubbing and
resuming with Space. Timeline now follows displayed time even while focused,
including paused frame stepping. All 21 timeline browser checks pass. Motion
and saved tuning unchanged.
[Lab details](Labs/BodyflipLab/README.md).


## October 24 - Bodyflip closest-foot frame matching replaces endpoint blend

Removed fixed End pose experiment. More options now has Match foot (defaulton):
at release search trimmed jump frames for closest support ankle in pelvis-local
space, using actual hip socket. Play that leg from matched frame at rate
(end-match)/(end-release), synchronizing at existing fall transition. Other joints
and procedural pelvis retain clocks. Existing short Blend prevents snap from
imperfect match; off restores previous ordinary timing. Ghost shows retimed pose.
Current saved RunR matches .100s vsrelease.034095s, rate.965601x, gap12.76cm.
UI displays matched time/rate and tooltip gap. Standing cutoff remains. Old endLeg
setting removed; user tuning/camera retained. 80 numerical/7 browser checks pass,
plus28 legacy live-aim checks. Cached lab only, no NN/Unreal/server restart.
[Details](Labs/BodyflipLab/README.md); match-leg-preview.png.


## October 24 - Bodyflip velocity jump choice / endpoint support-leg experiment

More options (collapsed) now contains Stand / Walk ratio default.5 (WalkF2m/s,
cutoff1m/s) and End pose (enabled). Standing clip selected from measured horizontal
root velocity at support contact; existing Walk2/Run5 remain Run-start at default.
Exported actual Stand L/R read-only via one headless nullRHI commandlet, exited
successfully; no interactive editor running, no asset saves/builds. Separate
jumps-standing.json preserves old exports. Both retain automatic source trim.
End pose moves released support joints directly to last jump-only pose at the
fall-loop transition, arriving with other joints (~1.95/2.05s after jump starts).
Not extra pin time. Purple Anim leg shows that fixed destination. Off restores
live-target Blend behavior. User trimOut1.8 ends before arrival: extend bracket
for full experiment. Other tuning/camera preserved; option edits keep time.
69 numerical/7 browser checks pass, plus184 pelvis/28 aim legacy-mode checks.
[Details](Labs/BodyflipLab/README.md); jump-options-preview.png. No NN/server restart.


## October 24 - Bodyflip animation-target support-leg ghost

Added **Anim leg** viewport checkbox: purple x-ray hip/knee/ankle/toe for the
jump animation's supporting leg, anchored to current pelvis. User clarified this
means animation target, not procedural reach. No initial/support blends or IK;
includes later fall-loop transition. Default off, saved; no reset/replan on toggle
and no sampling while off. Hidden before jump/abort/Space. Existing Ghost unchanged.
16 numerical and3 browser checks pass. User tuning preserved, contained lab only.
[Details](Labs/BodyflipLab/README.md); anim-leg-preview.png.


## October 24 - Bodyflip released leg keeps aiming at ground

Fixed RISE/BLEND using a frozen release-local pose that translated with pelvis.
Blend source now recomputes IK from current hip toward planted ankle every sample,
within Reach, after air rotation. Existing release time and blend duration remain;
FREE returns to animation. No leg stretch or false contact after reach is exceeded.
28 live-aim checks pass across Run/Walk/L/R/flip plus184 pelvis and162 support
checks. User settings preserved, contained lab/cached motion only.
[Details](Labs/BodyflipLab/README.md); release-aim-verification.json.


## October 24 - Bodyflip procedural pelvis / masked jump blend

Pelvis now retains its takeoff root-local position/orientation throughout jump
and prolonged fall; root supplies height/forward trajectory. Animation cannot
lower it. Initial pose blend excludes pelvis and planted support leg. Support
hip socket remains fixed; existing IK pin/reach determines release, then Blend
hands the leg back to local animation. Other joints blend normally; air flip
still works around the procedural pelvis. Locomotion and abort paths unchanged.
184 pelvis checks (both gaits/equipment/feet, Blend0/.08/.2/1) show zero hip drop;
162 support and15 walk checks pass. Current user Blend.08/tuning/camera preserved.
Contained lab, cached files only; no NN/Unreal processes or server restart.
[Current behavior](Labs/BodyflipLab/README.md); pelvis-verification.json.


## October 24 - Bodyflip Walk + jump / measured push timing

Added Walk + jump to the existing selector. Frozen Walk July5 latest lower NN
plus Upper82500 at2m/s, equipment variants and cached defaults; Run stays5m/s.
Duration/phase, support, trim, arrows and COM follow shared. Server API3; only
Bodyflip server restarted. Transient single-thread CPU inference, no GPU/Unreal.
Saved tuning/camera preserved. Walk Auto with saved Foot300 misses and aborts;
FootR succeeds at300, Auto succeeds at800. No silent contact-rule changes.
Run investigation: saved blend.2/playback.3 gives approach.0125s, pin.10886s,
then leg blend.2s (~1.03s wall-time pin+blend). Jump root rises immediately, but
pose blending lowers support hip ~18cm in first.1s, so pinned leg flexes then
extends. Source lead-in.333s already trimmed. Explained without changing timing.
15 motion/7 browser checks and duration/phase API checks pass. Details and
jump-timing.json in [Bodyflip Lab](Labs/BodyflipLab/README.md).


## October 24 - Bodyflip alpha sensitivity / keep intended target behavior

User clarified that alpha was working: 0.1 and 0.5 both requested points beyond
available ground and therefore shared the same edge-clamped contact. Do not
redesign working behavior to agree with a reported bug; explain the constraint.
Only sensitivity changes: local forward lead = root speed * alpha / 200.
At 5 m/s: alpha 0.1 = 2.5 mm, 0.5 = 1.25 cm, 1 = 2.5 cm. Saved numbers preserved.
Reverted interrupted current-pelvis anchor and extra ideal-marker work; retain
prepared root-local targets, half-hip spacing, moving gait, clamp and abort.
162 cached-run support checks pass. Tooltip/docs updated. Contained lab only;
no Unreal/NN processes launched. This supersedes the unscaled formula below.


## October 24 — Bodyflip root-speed alpha / global frame arrows

Lead is now root-local forward speed times alpha (seconds), with no COM velocity,
foot lateral-distance factor or division by approach speed. Alpha.02 at5m/s
requests10cm for either foot. Root heading carries the offset; actual contact
still projects to valid ground. Saved alpha/tuning preserved; numeric step.01.
Left/Right now pause and scrub exactly one authored1/60s frame globally, even
with sliders, selectors, buttons or trim brackets focused. Capture keydown AND
keyup; Up/Down are reserved rather than changing those controls. Focused writable
text/number/contenteditable fields keep normal arrows; readonly fields do not.
Manual frame scrubbing can inspect outside trim; Play/Step retain bracket bounds.
Repeated keys accumulate without lost frames; backward scrub clamps at zero.
152 motion/lead,6 grounding,43 browser key/lead and17 timeline checks pass.
Real keyboard verified on focused speed slider and foot selector: timeline moves,
speed.3 and FootAuto unchanged. Saved alpha2 retained.
Contained lab only, cached runs; no NN or Unreal processes launched.
[Current lab details](Labs/BodyflipLab/README.md); keys-verification.json.

## October 24 — Bodyflip run levitation fixed

Removed the lab's extra +5.5cm world-Y translation from the NN run in flight.js.
The cached NN gait is already ground-referenced; the extra lift raised stance
feet roughly5cm. Run bone heights now match the source exactly, retaining its
normal airborne gait phases. No per-frame root snapping or animation edits.
Measured actual renderer foot/toe boxes across both cached runs: stance gaps
within3.1mm; existing interpolation dips up to9.4mm below ground are unchanged.
Six grounding checks plus144 support/abort checks pass. Visual stance verified.
Current Foot300/alpha1/Early.10 now launches at.9125s after6.25cm forward approach.
Only contained lab/docs; settings preserved, no NN/Unreal processes started.
[Details](Labs/BodyflipLab/README.md); ground-verification.json in the lab.

## October 24 — Bodyflip root-local support / no freeze / missed-edge abort

Ideal support contact is stored root-local before finite-ground projection;
every authored240Hz step transforms it with the root and queries valid ground.
Foot approach is root-relative at Foot cm/s, carrying root momentum. Lead is
fixed from the preparation pose instead of feeding moving-foot displacement back
into the target. Removed the body hold; cached gait continues while approaching.
After the cached endpoint, carry its last pose forward without another NN call.
Actual foot-to-valid-target distance recorded every substep; first increase
over0.01mm aborts. Gate/reach still required for takeoff. Failed attempts release
IK with Blend, run to the ledge if still on ground, then fall with the speed cap;
HUD ABORT - RUN/FALL, no jump ascent and no frozen WAIT SUPPORT state.
History: BodyflipLab.state.flight.supportHistory. Replay/seek is deterministic.
Current user Foot300 / alpha1 / Early.10 retained: jump.9167s, root advances8.33cm
during approach. Foot10 miss abort1.0083s as gap grows8.28→8.73cm.
144 numerical and27 browser checks pass. Contained lab only; no NN/Unreal processes.
[Current lab behavior](Labs/BodyflipLab/README.md).

## October 24 — Bodyflip pelvis / cm/s / inverted vertical orbit

Pelvis render box now centers on the two thigh sockets, removing the hard-coded
7 cm downward bone offset. Skeleton, IK and physics bodies unchanged.
**Foot cm/s** uses the intended 800 cm/s = 8 m/s. Both approach and COM lead
prediction convert to metres per second. Current Foot set to 800; other tuning
and camera retained. Earlier claims that 800 m/s was intentional were wrong.
Default approach spans several 240 Hz steps, at most 3.33 cm each; root ascent
still waits for the gate. Saved alpha20.1 at Early.10 now requests an unreachable
target: WAIT SUPPORT is expected; user informed, alpha preserved. Alpha1/default
configuration verified to jump. Left-drag vertical orbit inverted; horizontal
orbit, middle pan and right-target drag unchanged.
122 numerical, 22 browser support/orbit and 20 editing checks passed, cached runs only.
No NN/Unreal processes. Preview: Labs/BodyflipLab/pelvis-units-preview.jpg.
[Current lab details](Labs/BodyflipLab/README.md).

## October 24 — Bodyflip earlier jump option / alpha ledge workaround reverted

User correctly noted alpha was functioning; reverted the automatic platform-edge
expansion introduced last turn. Edge is again speed × Run − .12 m, independent
of alpha. Existing alpha formula, uncapped values and lead readout remain.
Added **Early s** beside Run, default **.10 s**; 0 restores old timing. Support
preparation uses the cached gait at Run − Early, then still waits for the foot
gate. Default cached takeoff .904 s instead of 1.004 s, same fixed ledge.
Early leaves at least one authored frame of running; unreachable support still
waits. Click-away/Enter commits and edit-in-place playback fixes are retained.
120 numerical and 20 browser editing checks pass. Direct keyboard edits at
0.95 s show RUN with Early 0 and PUSH with Early .10, preserving playback time.
Only contained lab/docs; no NN or Unreal processes.
[Current behavior](Labs/BodyflipLab/README.md).

## October 24 — Bodyflip commit edits / retain playback time / alpha feedback

Number fields now blur/commit on outside pointer-down, including canvas clicks
whose default focus change is prevented. Enter also commits/unfocuses. Sequence
parameter edits rebuild at the current time; paused remains paused and playing
support edits resume there. Reset remains explicit. Cached support edits use no NN.
Measured alpha 1→20: previous final contact shifted only 8 mm and hit the old
ledge; at Foot 800 m/s the requested lead itself is only ~1 cm. The finite ledge
now allows a 12 cm margin after predicted contacts, capped by leg forward reach.
Lead readout reports actual cm and marks edge limiting; formula is unchanged.
Verified 104 support checks plus 17 editing checks (`editing-verification.json`),
and real canvas-click / Enter commits at 1.05 s without a time reset. Alpha 1→20
moves the planted foot forward 0.912 cm at that same time. Original alpha 20.1
and other saved tuning restored. No NN/Unreal processes launched.
Details: [Bodyflip README](Labs/BodyflipLab/README.md). Contained lab only.

## October 24 — Bodyflip support alpha uncapped

Removed the upper bound of 10 from **Lead alpha**, both UI and settings sanitizer.
Any finite nonnegative value, including values above 1 and 10, is accepted/saved.
Default remains 1. At Foot 800 m/s, alpha 10 yields only about 5 mm of forward
lead for the cached gait. Actual contact remains clamped to the finite platform;
its edge is unchanged. Only contained lab controls/docs changed; refresh the lab.

## October 24 — Bodyflip playback speed

Shortened the timeline on the right for a compact **Speed 0.1×–2.0×** slider,
default 1.0× and saved. Changes playback speed live without restarting; authored
timeline/trim/Step and fixed simulation step sizes remain unchanged. Bounded
frame work is retained. Only Bodyflip lab UI/clock and current docs changed.
Refresh the desktop lab. [Details](Labs/BodyflipLab/README.md).

## October 24 — Bodyflip procedural support plant

Replaced authored support preparation / jump-pose distance selection with a
procedural ground contact in **Kinematic**. Pelvis projects to the finite platform;
ideal L/R contacts sit half a hip width along its tangent. Auto selects the nearer
corresponding foot; L/R overrides remain. Prediction is COM tangent velocity ×
alpha × lateral foot distance **divided by foot speed**, as clarified by user.
Controls: **Reach .99**, **Gate 5 cm**, **Lead alpha 1**, **Foot 800 m/s**.
Speed-limited approach gates root ascent; plant the reached position without a
final snap, hold in world space with fixed-length two-bone IK, release at reach
limit, then blend that leg into its matching jump clip using Blend. Other limbs
blend at takeoff; Air flip starts after foot release. Green ring shows contact.
Unreachable contact waits; slow-foot approach can hold the body at the ledge.
Read [Bodyflip README](Labs/BodyflipLab/README.md) for contact-gap and geometry
details. **104 numerical / 20 browser / 17 bracket checks passed** using cached
runs only. Preview: `Labs/BodyflipLab/support-preview.jpg`.
No NN worker, Unreal, native build, shared assets or other sessions changed.
Existing bracket settings preserved; refresh the desktop lab to load this change.

## October 24 — Bodyflip playback stays inside brackets

Fixed replay ignoring the visible range when Loop was off. In/Out now always
bound Run + jump playback: Loop repeats; without Loop playback pauses at Out.
Moving either bracket enables Loop automatically; Step also respects Out.
Kinematic remains active. `timeline-verification.json` passes **17 checks**,
including actual animation-frame playback, repeat wrapping, Loop-off stopping,
Step bounds and live drag previews. Only the contained lab and this handoff
changed; no NN or Unreal processes started. Refresh the desktop lab to load it.

## October 24 — Bodyflip inline trim brackets / live scrubbing

User rejected the extra trim row. Replaced it with draggable **[ / ] brackets on
the playback timeline**, highlighted range and compact Loop beside transport.
Footer restored to **56 px**; separate sliders/numeric fields removed. Hover/focus
shows endpoint time; arrows move one frame (Shift ten); saved ranges preserved.
Kinematic playhead and bracket dragging now update the scene **before release**,
coalescing pointer inputs once per animation frame without NN/replay work.
Current details: [Bodyflip README](Labs/BodyflipLab/README.md).
`verify-timeline.html` checks input-only live preview, latest-position wins, bracket
adjustments, compact layout, loop wrapping and kinematic membership; receipt
`timeline-verification.json`. Old loop test routes to the replacement fixture.
Only contained lab files changed. Refresh the existing desktop app.

## October 24 — Bodyflip playback In/Out loop

Run + jump playback bar now has **In / Out** sliders plus seconds fields and a
separate **Loop** checkbox. Edit boundaries, enable Loop, Play/Space to repeat.
Edits pause/preview that endpoint; bounds snap to 60 Hz frames and cannot cross.
Defaults 0–3 s, Loop off; values persist. Numeric fields extend range up to 600 s.
Kinematic remains selected. Seeking/wrapping directly samples the prepared sequence
and flip/twist phase without NN work or simulation replay; transient attack/hit
state clears per pass. Sim uses the existing yielding reconstruction if selected.
Attack Loop remains independent. [Bodyflip README](Labs/BodyflipLab/README.md).
`loop-verification.json`: 11 checks passed, including three wraps, exact restart,
boundary guards, pause and Loop-off behavior. Only lab files changed; no heavy
processes started. Refresh the existing desktop app.

## October 24 — Bodyflip kinematic takeoff trimmed / support-foot Auto

Current work remains **Kinematic**, now also the fresh-settings default. Both
authored Lfoot/Rfoot jump variants already existed. Each now skips **20 frames /
0.333 s** before meaningful root ascent; root height is rebased at the cut. Run
ends directly in ascent, with no preparation delay or root-position discontinuity.
Blend still interpolates the body without delaying the root. Apex is 0.467 s (L)
or 0.533 s (R) after Run; edge/fall-loop/air-flip timing use the trimmed timeline.
**Foot Auto** chooses the smaller root-relative 3D supporting-ankle distance:
final-run left foot versus trimmed L support, right foot versus trimmed R support.
Removed the old whole-leg score at the untrimmed first frame. L/R remain explicit
overrides; status shows the chosen support. These are two authored opposite-foot
variants, not a claim of exact mathematical mirror symmetry.
Read [Bodyflip Lab](Labs/BodyflipLab/README.md). Focused sampling checks cover
immediate ascent, continuity, source pose fidelity, both overrides, exact support
matches and both choices across gait positions: `takeoff-verification.json`.
Browser results: `takeoff-browser-verification.json` (**20/20**). Also fixed timeline
pointer input losing its requested value during the pause redraw; real clicking
now seeks to 1.17 s and visibly shows RISE. No NN worker, Unreal process,
asset edits or physics tuning. Refresh the existing desktop lab.

## October 24 — Bodyflip tracking correction / kinematic comparison / hitching

User found button-focus Space conflicts, hitching and poor simulated gait. Changes
remain in `Labs/BodyflipLab`; [current details](Labs/BodyflipLab/README.md).
**Motion → Sim / Kinematic** compares identical decoded NN targets and restarts the
sequence. Kinematic has no solve/contact response; Sim has 25 dynamic bodies.
Space now captures keydown/keyup and suppresses repeats, including with a
button/slider/checkbox/selector focused. Text editing keeps normal keys.

Diagnosis confirmed: initial Run + jump used spring joint motors, NOT the native
velocity tracking functions. Corrected to `ProphecyJoltVelocityServo.cpp`'s angular
error/substep command and parent-first predicted endpoints, with world position
tracking on pelvis only, gravity compensation and origin-to-COM velocity correction.
Joint motors are off in this mode; real constraints/contact remain. Original Space
motors remain. One-second frozen NN comparison: upper-spine mean angular error
28.10°→1.60°, left-hand 54.20°→6.17°. Hinge/contact errors remain; lab rig/tuning is
not native-rig parity. Source NN is unchanged. Kinematic exposes its exact poses.

Optimization: cached sword geometry/normals, unique vertex transforms, reused GPU
buffers, cached local pose sampling, scalar root-height derivatives, 10 Hz HUD,
bounded catch-up. Decoded NN cache makes reset/blend/foot/cap edits reuse a segment;
timeline reconstructs on release in short yielding batches. Measured same local
1000×700 fixture: mean frame work 22.40→9.38 ms; p95 25.30→12.80 ms. Cached Reset
3.5 ms. These include test diagnostics/render submission, not GPU-present FPS.

Validation: **27/27** focused comparison checks, real focused-button Space toggle,
tracking regression, and 12 simulated seconds. Max anchor 4.111 mm, pelvis position
1.172 cm, pelvis angle 19.05°; fall cap respected. Receipts in lab:
`comparison-verification.json`, `tracking-before/after.json`,
`performance-before/after.json`, updated `flight-verification.json`.
Prior 16/39 UI receipts below are historical; sequence fixture adapted to async seek.
Only the small existing server remains resident; no NN/Unreal/build/training process
started for these fixes. Existing desktop icon; refresh the lab to load changes.

## October 24 — Bodyflip Lab simulated run → jump → void complete

Contained in `Labs/BodyflipLab`; desktop **Bodyflip Lab**, loopback **8876**.
Current details: [Bodyflip Lab README](Labs/BodyflipLab/README.md).
Default **Run + jump** uses frozen installed Run **181751** + Upper **82500** NN
weights through the original Stepper encoder/decoder (CPU, read-only dependency).
Run duration defaults to **1 s**, gait phase and jump blend have sliders. Real
GASP L/R running jump starts supply the root rise; the prolonged fall uses
`M_Relaxed_Jump_Loop_Fall`. Platform ends at lift-off; below it is an infinite void.
Downward speed defaults to **20 m/s**, with a configurable cap on actual body COM.
Camera follows mass-weighted simulated COM. All **25 bodies are dynamic**;
mode **0** principle means parent-relative limb angular motors and world-space
pelvis attraction only. This is the lab's Jolt implementation/tuning, not exact
native Unreal adapter parity. NN recurrence prepares a segment without physics
feedback. Original Space mode, attacks, draggable target, flip/twist remain.
Air flip is off by default and, when enabled, starts at lift-off.

Laptop containment: single-CPU inference workers exit after preparation; default
unarmed/drawn segments and four recent requests are cached. Idle server measured
**18.5 MB**, no resident Torch/NN; cached repeat **12 ms** (uncached **16.9 s** under
current load). Paused/hidden lab does no continuous rendering or simulation.
Export-only headless processes have exited and their Content junction was removed.
No gameplay C++ build, asset saves, training/model-pointer changes, or changes to
other labs/sessions. Export had unrelated dependency/config diagnostics; all three
source asset hashes and exported transforms independently verified.

Validation: final **16/16** sequence browser checks, original **39/39** UI checks,
320 attack clips and 12 axes verified. Twelve simulated seconds: maximum joint
anchor error **4.147 mm**, pelvis target error **8.779 cm**, pelvis angle error
**12.6°**; terminal COM speed respects the 12 m/s test cap to float precision.
Receipts: `flight-verification.json`, `sequence-browser-verification.json`,
`nn-verification.json`, `jump-export-verification.json` in the lab. No NN worker
is intentionally kept running after verification. Existing desktop shortcut remains.


## October 24 - approved isolated UI checkpoint

User approved and saved the pause menu and requested this UI work pushed.
Includes Labs/PauseMenuLab, Labs/WeaponWheelLab, saved presets, fonts/artwork,
font study and pause concept galleries. See Docs/WeaponWheelUI.md and lab
READMEs for build/open instructions. Tuning controls are chronological, with
new controls appended at bottom. Pause saved unselected opacity0.8032181263,
selected whiteness0, right extension200. Fixed underline retained. Final
pause build12.31s and351/351 native input checks passed. No gameplay hookup.
Generated builds/caches/captures and unrelated concurrent work are excluded.
User cancelled the separate disaster-recovery audit; no audit claim is made.


**October22 curated checkpoint prepared:** user requested pushing current work
before switching to UI. Includes current source/tests/tools/docs, saved PoseAgent
and A_Sword, required physical-mesh Python label helper, and current lightweight
MimicKit/Sound Studio source. TestNN's local modification, generated models,
environments, full captures/diagnostics and unrelated PDF remain local. No editor
mutation or new build for this checkpoint. Recovery inventory regenerated from
the staged tree; Git history/remote identify the final checkpoint. See Recovery
opening for external dependencies and scope.

**October22 Sound Studio — INSTALLED/VERIFIED:** independent native Windows WAV
editor at `Labs/SoundStudio`, desktop **Prophecy Sound Studio**. Default source
`Documents/Sounds`, target `Documents/Sounds Mixed`; editable export name, unique
numbered files, source/target lists, double-click remix with all controls reset.
Waveform trim/fades, independent offline R3 pitch/speed, five-band EQ, reverb tails,
optional local polish/denoise; dithered48kHz/16-bit default,24/float options and
estimated true-peak protection. Dedicated `Saved/SoundStudio/env`; matching shortcut
and process AppUserModelID plus native icon handles verified.26 signal/UI checks
passed, including short-transient latency compensation and preview/export equality.
No Unreal/assets/training changes. [Workflow, research and limits](Labs/SoundStudio/README.md);
receipts `Saved/Diagnostics/SoundStudio20261022/`.

**October22 shared pelvis speed threshold corrected — RUNNING:** user requires
max of both get-up peaks for all perturbed rows, since front can roll into back.
Shared149.516cm/s replaces per-motion limits. Resumed latest130296 as
20261022_131128_uefn_getup_pelvismax7_1024, same L4/1,024agents until stopped.
Fixed loss weight recalibrated7%; all18perturbed replay rows share threshold.
New backup/reward/progress verified130307,~15.15k transitions/s. See training
journal opening and getup-pelvis-max receipts. Other settings/loco unchanged.

**October22 local idle push viewer — ready/paused:** http://127.0.0.1:8850/ .
Frozen latest-at-capture locomotion checkpoint0122776, one local CPU agent with
real idle inputs, native240Hz physics/30Hz policy. Limb selection, directional
mass-independent velocity kicks, strength control, reset and pause. Pause/hide
stops simulation and continuous drawing. Verified30.18updates/s and equal1m/s
kicks across hand/foot/pelvis. No cloud/training/Unreal changes. Restart with
Labs/MimicKitIdleLive/start.ps1; see its README and MimicKitTraining opening.


**October22 per-arm grab independence — INSTALLED/VERIFIED:** Joint
Independance0..1 on Grab Object/Bone plus per-hand live Set/Get nodes. Reuses only
the isolated projection experiment's constraint solver; other special-attack
features remain isolated. Live Coding new cross-module imports failed; authorized
normal incremental build30actions269.60s passed, all normal DLLs current. Isolated
headless TestNN:174native checks pass; held clavicle alpha0/.25/.5/1/0 preserves
physical joint identity, right setting.75 unchanged. Three existing grab nodes
refreshed/saved, other wires/tuning identical; reflection/status healthy. Editor8096
closed cleanly, current M_JoltTransferFailure already saved. Test process exited;
interactive6904 verified on that map, Play off/dirty[], all4API signatures loaded.
See ReachGrasp opening and GrabIndependence
receipts; Tools/ReachGrasp/GrabIndependence.py / TestGrabIndependence.py.

**October22 recovery horizontal pelvis speed cost — RUNNING:** resumed latest
129835 on same L4,1,024agents until stopped. Run20261022_124925_uefn_getup_pelvis7_1024.
Perturbed/perturbed+ only: squared excess above front0.473/back1.495m/s reference
peaks, fixed weight calibrated7%. Verified XY horizontal/Z vertical and pelvis
origin vs COM; pure vertical speed contributes zero. New backup/replay/TB and
129846progress verified (~15.1k transitions/s). Existing foot/AE weights and
normal/loco/physics unchanged. See MimicKitTraining opening and pelvis receipts.

**October22 recovery foot penalties — RUNNING:** resumed latest129347 on existing
L4 0to3wg3r3n926h,1,024 agents until stopped. New run
20261022_122519_uefn_getup_feet7_1024 adds ankle target-velocity and idle-relative
foot rotation costs to perturbed/perturbed+ only, fixed weights calibrated to
7% EACH. Normal/loco/physics unchanged. Latest checkpoint locally/S3 preserved;
new backup, advancing129358 and replay/TB terms verified (~15.2k transitions/s).
See MimicKitTraining opening and getup-foot calibration/verification receipts.

**October22 clavicle grab fixed — loaded/verified:** correct Self/closest-agent
wiring was rejected by StartGrab's fixed4cm open-finger clearance cap. Replaced
that cap with a collider/hand geometry bound, one-time admission work only.
Live Coding1action161.75s, reload10:46:44UTC. Exact current TestNN owned PIE:
BP starts at absolute30, reaches by60, grips by90 and holds through180. No tuning,
wiring, save or restart; dirty agent BP/TestNN preserved, owned Play ended.
Slow startup is existing sword Start Slow FPS=true/Slow FPS=5; removal of its
EndPlay reset now preserves that cap. Startup values unchanged. Normal DLLs
remain stale. See ReachGrasp opening and GrabDefaultsSelf diagnostic receipts.

**October22 all grab nodes default Self — loaded/saved:** added DefaultToSelf Agent
to Grab Object/Bone, Release Grab, Get Grab Status, Set/Get Grab Angle Tolerances.
Explicit overrides remain supported. Runtime/editor Live Coding4actions314.31s,
reload10:25:37UTC. All6metadata entries verified;4existing nodes refreshed and
agent BP saved. User had already removed GrabBone304's incorrect Agent link;
it now defaults Self, target Mesh and automatic surface selection preserved.
Graph unchanged except object/Object FName casing; BP types/status healthy.
No Play/restart or retained layout changes. Tools/ReachGrasp/GrabDefaultsToSelf.py
and GrabDefaultsSelf receipts. Normal DLLs remain stale; see ReachGrasp opening.

**October22 sword End Play FPS reset removed/saved:** deleted fixed60 and
t.MaxFPS60 reset nodes from A_Sword End Play, so HideSword/destruction no longer
changes global clock. Exact graph comparison confirms only those two nodes and
their exec links removed. Existing startup/RMB debug controls unchanged. Saved
A_Sword only; TestNN remains dirty, no Play/restart. Editor helper1action80.60s,
reload09:50:55UTC. Normal DLLs remain stale. Tools/SwordHolster/RemoveEndPlayFPS.py,
Saved/Diagnostics/SwordEndPlayFPS/verification.json; see SwordHolster opening.

**October22 Grab Bone optional surface point — loaded:** new visible Use
Surface Point bool, default true for compatibility. False ignores supplied point
and uses Grab Object's automatic collider selection toward the upper arm.
No retained layout change. Runtime3actions162.05s; editor refresh helper1action
119.54s (after compile correction), reload09:39:31UTC. Current node refreshed,
all existing graph wiring/defaults verified unchanged, agent BP saved. No Play
or restart. Tools/ReachGrasp/UpgradeGrabBone.py and GrabBoneSurface receipts.
Normal DLLs remain stale. No FPS behavior changes: diagnosed HideSword destroys sword and
A_Sword EndPlay unconditionally restores60FPS; current Grab Bone also had the
victim wired as grabber (self-grab rejection). See ReachGrasp topic opening.

**October22 physical mesh getter renamed:** Blueprint display name is now Get
Physical Mesh for all instances of native GetPoseReferenceMesh. Serialized
identity/wiring unchanged. Existing editor Python startup reapplies the label;
Tools/ReachGrasp/RenamePhysicalMesh.py reapplies after any future Agent reflection
replacement. Verified all3TestNN agents return PhysicalMesh. No build/restart,
graph edits or saves; user dirty agent BP/TestNN preserved. Normal DLLs remain
stale from preceding tasks. See ReachGrasp topic opening.

**October22 closest-agent node — loaded:** added pure Get Closest Agent
in existing Reach library, Prophecy|Agent category. Same-world3D actor-position
distance, excludes self/destroying agents, returns None when unavailable. No
retained state or background work. Dirty BP_ProphecyManualPoseAgent preserved to
disk before reload; previous saved bytes in Saved/Diagnostics/ClosestAgent.
Live Coding3actions178.65s, reload09:18:36UTC. Verified correct nearest-other
references for all3TestNN agents and None input; Blueprint types healthy after
compiling the dirty agent BP. TestNN consequently dirty, left unsaved. No Play,
restart or wiring edits. Tools/ReachGrasp/VerifyClosestAgent.py and diagnostic
verification.json retain the check. Normal DLLs remain stale. See ReachGrasp topic.

**October22 recovery resumed after funds outage:** latest127054 locally verified;
replacement L4 0to3wg3r3n926h, $0.59/hour until stopped, exact existing1024-agent
settings. Run20261022_104951_uefn_getup_perturbed_plus_1024 advanced127055->127065,
15.49k transitions/s; new persistent backup/replay/TB verified. Old retained pod
upszb03gy35fzj remains stopped. Locomotion independently resumed by its own chat;
both current TB streams verified. See MimicKitTraining opening and recovery
funds-resume-verification.json. Supersedes prior recovery running-pod status.

**October22 locomotion resumed after funds shutdown — RUNNING:** latest119475
(2,409,365,504samples) locally/persistently verified, optimizer/normalizer restored.
Old L4q764mqd40pabiq unavailable after Runpod shutdown; retained disk preserved.
Replacement L4leuh8va7hfcevy,$0.59/hour,1,024agents until stopped, exact previous
settings/source. Run20261022_104557_uefn_locomotion_pelvis_velocity5_1024,
verified119476->119486 and first backup. TB10-45-57, bridge/dashboard publishing.
Recovery unchanged. See MimicKitTraining opening and funds-resume-* receipts.
Supersedes locomotion status below.

**October22 reach/grab pelvis floor — loaded:** minimum commanded pelvis height
is now40cm vertically above the root, replacing the animation-relative72cm drop
cap. New Set/Get Reach Minimum Pelvis Height Blueprint nodes allow per-agent
live overrides for both hands. Candidate body solve applies the floor before
arms/legs; no extra solver iterations or retained-state layout changes.
Isolated kernel21cases/2520frames passed. Live Coding4compile actions338.41s;
reload08:11:45UTC, nodes/default and Blueprint types verified. Editor8096 remains
TestNN/outside Play, dirty[], no asset/wiring edits. **Normal DLLs stale: normal
incremental build before next cold launch.** Lab untouched. See ReachGrasp topic
opening and Saved/Diagnostics/ReachPelvisHeight/ receipts.

**October22 TestNN reopened:** editor8096 verified on /Game/testNN.testNN,
outside Play, no dirty packages. Existing normal DLLs current; no build or
asset edits. Startup rebuilt missing engine-material shaders before opening.

**October22 locomotion TB refreshed:** local observers restarted; missing event
history restored through2.324B samples, live cards verified17seconds old. Current
run23-17-29 selected. L4 training remained uninterrupted at~19.25ktransitions/s.
Dashboard skips unnecessary replay scans when full-batch counters are available;
bridge polling30seconds,TB cap10unchanged. See MimicKitTraining opening and
Saved/MimicKitLocomotion/tb-refresh-20261022.json.

**October22 scheduled perturbed+ switch — RUNNING:** resumed latest recovery
113353_final (2,076,229,632 samples), locally SHA256-verified and persistent,
as 20261022_013025_uefn_getup_perturbed_plus_1024 on same L4 upszb03gy35fzj,
$0.59/hour until stopped. 307 normal /359 ordinary perturbed /358 perturbed+;
plus179 front and179 back. Root linear and local joint velocities use two
different random locomotion frames; independent isotropic spin magnitude uniform
0–700deg/s. Plus head50% failure begins tick100; ordinary stays80. Other settings
unchanged. GPU reset checks passed, advancing113354->113364 at early14.96k
transitions/s; first backup readback verified. Replayer20rows includes9 correctly
labelled perturbed+; TB/bridge publishing. Schedule paused after completion.
See Docs/MimicKitTraining.md and getup-plus-verification.json. Supersedes scheduled
entry below. Locomotion branch untouched.

**October21 pelvis velocity MSE x5 — RUNNING:** pelvis-only 3D linear velocity
contribution multiplied by5 on every locomotion-branch row (normal/perturbed,
idle/loco), retaining body mean and AE/MSE handoff. Latest99574_final
(1,757,249,536samples) locally/persistently verified and resumed as
20261021_231729_uefn_locomotion_pelvis_velocity5_1024, sameL4q764mqd40pabiq,
1,024agents,$0.59/hour until stopped. Verified99575->99585 at18.56ktransitions/s,
first backup verified, actual20row replay confirms new weighting. Other losses
and recovery branch unchanged. TB23-17-29; see MimicKitTraining opening and
Saved/MimicKitLocomotion/pelvis5-* receipts. Supersedes loco status below.

**October21 recovery perturbed+ switch scheduled:** in two hours, approximately
October22 01:16 Europe/Warsaw, resume latest with half the perturbed rows assigned
new initial velocities. Root linear velocity and local joint velocities come
from two different random locomotion frames; independent random 3D spin has
uniform magnitude 0–700 deg/s. Only these rows delay the 50% head-height failure
check from tick80 to100. Other settings unchanged. Implementation is scheduled,
not yet deployed. Plan Saved/MimicKitEquipment/perturbed-plus-switch.json;
heartbeat switch-half-of-perturbed-get-ups-to-perturbed. Preserve loco branch.

**October21 speed-loss TB card fixed:** dashboard whitelist omitted the already
logged loss/extremity_speed_excess. Added mapping, backfilled31points exactly,
restarted local dashboard only(PID2912), ongoing updates enabled. Trainer/GPU
uninterrupted. TB22-48-04 filtered to new card; see MimicKitTraining opening.

**October21 locomotion soft speed loss — RUNNING:** both hard speed-limit tries
stale. Restored pre-change98733_final(1,729,691,648samples), optimizer/normalizer
included. Keep150%foot/hand thresholds; idle uses walk backward. Speed no longer
terminates: squared excess cost with fixed3.20399479weight, calibrated to15%of
existing loss on violating frames. COM2 conditions unchanged. New run
20261021_224804_uefn_locomotion_speed_loss_1024 on sameL4q764mqd40pabiq,
1,024agents,$0.59/hour until stopped. Verified98734->98754,18.53ktransitions/s,
new backup verified; replay15overspeed frames continue and reward matches cost.
TB22-48-04. Recovery untouched. See MimicKitTraining opening and speed-loss receipts.
Supersedes hard speed termination entries below.

**October21 locomotion speed limits both150% — RUNNING:** feet raised135->150%,
hands unchanged150%, idle still uses matching walk backward. Latest99151_final
(1.743B) locally/persistently preserved, resumed20261021_221827_uefn_locomotion_extremity150_1024
on same L4q764mqd40pabiq,1,024agents,$0.59/hour until stopped. Verified99152->99172
at18.47ktransitions/s, first backup verified. TB22-18-27. Only speed-reference
artifact changed; recovery unchanged. See MimicKitTraining opening and speed150 receipts.
Supersedes earlier locomotion135%foot limit below.

**October21 persistent replay/checkpoint cleanup completed:** user approved deleting
the 468 intermediate physical UEFN checkpoint archives containing old replays.
Deleted exactly that list: 21,375,033,969 bytes (21.38 GB). Verified every deleted
key absent and all 14 protected latest/final saves present, including newer saves
found during execution. Training was not interrupted; local files, datasets,
source packages and TensorBoard logs untouched. Receipt:
Saved/MimicKitEquipment/replay-cleanup-20261021/completed.json.
This was a one-time cleanup, not a change to automatic retention.

**October21 locomotion extremity-speed limits — RUNNING:** perturbed rows fail
above135%foot/150%hand reference maximum in moving pelvis frame; idle uses
matching walk backward. Latest98733_final locally/persistently preserved;
resumed20261021_220225_uefn_locomotion_extremity_speed_1024 on replacement
L4q764mqd40pabiq,$0.59/hour,1,024agents until stopped. Verified98734->98754,
18.44k transitions/s, first backup readback verified. Replay5speed crossings
all terminate at first eligible tick. TB22-02-25. Initial startup table-shadowing
bug fixed/tested; old A40 stopped and unavailable. Recovery unchanged.
See MimicKitTraining opening. Supersedes loco status below.

**October21 locomotion perturbed idle pose MSE x5 — RUNNING:** position and
rotation only, perturbed ordinary idle only, across early MSE/handoff/full MSE.
Existing early coefficient0.01062843 retained; AE/velocities/normals/loco and
recovery untouched. Resumed preserved97272_final (1.682B samples) as
20261021_205453_uefn_locomotion_perturbed_idle_pose5_1024, same A40,$0.59/hour,
1,024agents until stopped. Advancing97273->97283,early14.0k transitions/s;
new backup persistent-verified. TB20-54-53. Scope tests and receipt details in
MimicKitTraining opening; Saved/MimicKitLocomotion/idle-pose5-*.
Supersedes earlier locomotion status below.

**October21 perturbed get-up jump termination — running:** pelvis worldZ
>=93.457782cm fails from tick6; first5ticks exempt, normals untouched. Existing
100failure cost/no success bonus. Latest104663_final locally/persistently
preserved, resumed20261021_200623_uefn_getup_pelvis_ceiling_1024 on sameL4,
1,024agents/until stopped. Verified104674 at~15.31ktransitions/s,backup and
11actual replay jumps terminated on first eligible crossing with penalty.
Previous success gates/all other settings retained; locomotion untouched.
See MimicKitTraining opening and pelvis-ceiling-verification.json.


**October21 locomotion early MSE+AE RUNNING:** user-requested added MSE
shares the AE fade: (1-mix)*AE + [mix+0.01062843*(1-mix)]*bodyMSE,
30ticks early/30ticks handoff. Calibration matches mean early costs~0.299 each;
late MSE, normals, physics/optimizers unchanged. Resumed preserved96009_final
(1.640B samples) on same A40wjxv6qigq3dy9o,$0.59/hour until stopped,1,024agents.
Run20261021_200213_uefn_locomotion_ae_earlymse_yaw180_1024, TB20-02-13.
Advancing96010->96020,early14.3k transitions/s,new backup persistent-verified.
Recovery untouched. See MimicKitTraining opening and early-mse verification
receipts in Saved/MimicKitLocomotion. Supersedes earlier locomotion status.

**October21 optimisation cleanup / TestNN reopen:** recycled disposable
Intermediate/PikeJointLab (3,985,596bytes); source and benchmark receipts kept.
Optimised diagnostics only11.318MiB, no large dumps from this arc. Map switch
hit Unreal's old-world GC fatal: Python retained /Game/explosionVFX Package.
All assets saved/no Play before switch. Inspection scripts now use function
scope; cut capture releases world references on finish. Never keep editor
actors/packages in remote Python globals across map loads. Incremental normal
build succeeded (10actions,251.60s); normal DLLs now current. Recycled today's
27 obsolete Live Coding patch files (479.34MiB) after build/before launch.
Editor27876 verified on /Game/testNN.testNN, outside Play, no dirty packages.
Total recycled483.14MiB; retained small diagnostics, benchmarks and source.

**October21 perturbed recovery success tightened / running:** exact screenshot
rollout103985 gives feet threshold13.034895cm and |head vertical speed|<2.103453m/s,
in addition to head>90%idle height. Both feet must pass; body-origin worldZ.
Latest104197_final saved locally/persistently before same-L4 restart as
20261021_194738_uefn_getup_success_gates_1024,1,024agents,until stopped.
Verified104208 at~15.85ktransitions/s, new persistent backup, all6recorded
successes satisfy new gates. Other settings unchanged; locomotion untouched.
See MimicKitTraining opening and success-gates-verification.json.


**October21 current head-pike entry fixed before requested backup:** Optimised
was recentering the accepted contact6.221cm onto the blade centreline, causing
an upward solver kick. It now retains the pike's transverse contact offset at
the hilt plane. Ten exact-prefix samples; first post-contact deviation from
legacy4.751deg ->0.019deg. Stain reaches1; withdrawal removes joint/cut/NS at
0.35s. Current fixture transient hilt overshoot4.945mm (earlier0.432mm belonged
to a different approach). No BP/scene tuning edits. One implementation compile
119.98s, Live Coding loaded17:09:35UTC, no restart; normal DLLs remain stale.
Owned Play ended; latest user A_Sword/map edits saved for the requested backup.
Curated snapshot targets codex/standalone-sim: scripts/source/docs/config plus
all346 Blueprint/Niagara/ControlRig assets and lightweight supporting assets.
No new LFS pointers or files over25MiB; bulk meshes/textures/animation libraries,
VDB volumes, training checkpoints and generated diagnostics excluded. Remote
push receipt lives in Saved/Diagnostics/Backup20261021 after verification. See
[current correction and evidence](Docs/OptimisedSwordCuts.md).

**October21 Optimised sword cuts — saved, loaded and tested:** A_Sword has
instance-editable Optimised=true (select before Play); false retains old BP path.
User-confirmed velocity cut dampings, easier withdrawal, matter0-only frame5
depth cap, and one-time accepted-slash width overshoot correction implemented.
Native travel releases cuts/NS; flesh pikes publish progressive blade stain.
Slash plane/swing3x3 solve leaves twist free; hard blade limits solved in existing
iterations. Wall width2.779678cm held; cube cap frame5/natural ejection0.68333s;
head pike NS/stain1.0/withdrawal cleanup pass, hilt residual0.432mm.3976 original
pins compared/nine expected changes. Only A_Sword saved, map hash unchanged.
Editor21708 explosionVFX stopped/no dirty packages. Normal layout build/restart
completed earlier; final implementation-only plugin patch33.21s loaded16:52:35UTC.
Normal DLLs stale: incremental build before next cold launch. Standalone100-cut
world~0.45–0.73ms physics CPU, not an Unreal FPS comparison. Shared opted-in pike
hard-stop correction also tightened; ordinary joints unchanged. See
[implementation, measurements and exclusions](Docs/OptimisedSwordCuts.md).

**October21 locomotion RUNNING with1,024 agents:** user-selected resume from
preserved production91895_final (1.506B samples), not sweep weights. New A40
wjxv6qigq3dy9o at$0.59/hour until stopped; L4 unavailable. Run
20261021_171453_uefn_locomotion_ae30_mse30_yaw180_1024. Settings unchanged except
agent count; pinned512-only startup gate corrected. First attempt failed before
training and stopped billing automatically; corrected run advances91896->91906,
early13.6k transitions/s. First checkpoint persistent-readback verified. Both
optimizer states/normalization restored. Recovery stays stopped. TB17-14-53;
Saved/MimicKitLocomotion/worlds1024-live-verification.json; topic opening has
source/backup/setup details. Supersedes stopped-production statements below.

**October21 recovery resumed with1,024 agents:** latest99984_final retained;
new20261021_171139_uefn_getup_ae10_1024 on L4upszb03gy35fzj/$0.59hour,
until stopped. Optimizer/normalizer restored; other training settings unchanged.
Verified99985→99995 (~15.15k transitions/s early), persistent backup and replay.
Removed obsolete equipment512-agent launch restriction after first attempt
stopped automatically before training. Original/replacement retained pods
unavailable; both stopped. Locomotion untouched. See MimicKitTraining opening
and Saved/MimicKitEquipment/getup1024-verification.json.


**October 21 isolated locomotion sweeps — finished; GPU stopped:** ten
configurations screened from protected checkpoint91895_final. No verified
learning-speed winner: rollout64+LRx2 gave27.40% failures versus baseline27.67%,
within evaluation uncertainty. 1,024 worlds processed transitions1.68x faster,
but evaluation velocity/observation hashes differed; learning result excluded.
User requested wrapping up; longer confirmation cancelled without a completed
comparison. Separate A40a9y7igarhig19j confirmed EXITED, estimated GPU cost$1.14.
All seven production checkpoint/source/control files rehashed unchanged. Both
production branches stay stopped; no settings promoted. Evidence and stop/
backup receipts: Saved/MimicKitLocomotionSweeps/20261021. Final research/report:
Saved/MimicKitLocomotion/research-20261021/results.md. See topic opening.

**October21 first wound ray — fixed, saved and tested in current head-pike scene:**
NS_bloodwound Fountain001 now uses wound-only synchronous CPU collision copies;
trace multiplier1 instead of5. Local space, speed, lifetime and other emitters
unchanged. Stock asynchronous hits were stale by the paint callback: original
1cm retrace missed100/100 sampled first-emitter exports; fixed100/100 hit head.
First stamp at0.283333s, three game ticks after head pike at0.233333s; first-only
normal callback and full two-emitter test agree. Visible head stain verified
against same-view BloodIntensity0 capture. Temporary wider retrace removed;
A_DecalManager keeps +/-1cm, scalar pin repaired/compiled/saved. Only wound NS,
two companion modules and manager saved; A_Sword user edits remain dirty.
Owned tests ended, explosionVFX open, no restart. Editor helper Live Coding
loaded (API/link repair retries; final installer guard build109.16s); normal editor DLL stale before
future cold launch. Runtime uses saved Niagara assets, no native tick hook.
See Docs/BloodExperiments opening and compact Saved/Diagnostics/WoundRay evidence.

**October21 recovery stopped / latest preserved:** user requested download then
stop. Final99984 at1,638,154,240samples verified locally and in persistent storage;
L4w9aq90rzkg1d0g confirmed EXITED. Prepared recovery resume pointer updated.
Final TB/replay synced; recovery bridge stopped. Locomotion untouched (its pod
independently reported EXITED). See Docs/MimicKitTraining opening and
Saved/MimicKitEquipment/stopped-latest-20261021.json. Supersedes running entry.


**October21 locomotion STOPPED by user:** final91895 checkpoint downloaded
and SHA/ZIP verified locally, preserved in persistent storage. L4rjsan0uitu03qd
confirmed EXITED; GPU billing stopped, local observers/active marker cleared.
Saved/MimicKitLocomotion/preserved-latest/20261021_091005_uefn_locomotion_ae30_mse30_yaw180_512/checkpoint_0091895_final.zip.
Recovery branch untouched. See MimicKitTraining opening and user-stop receipts.

**October21 original arm-pike scene placement restored/saved:** user requested
the problematic arm-hit setup again. Only A_Sword1 actor placement restored in
explosionVFX: position(2007.955873660,172.688569383,171.148856237)cm, original
rotation/actor scale retained. Mannequin already matches CleanPike saved-map
reference exactly. Reconstructed launch using old map start plus constant offset
between CleanPike and PikeSlide recordings; all15 precontact samples agree within
2.274e-13cm. Saved map only; current BPs, correction toggle and tuning untouched.
No Play started. Small reference-map copy loaded without opening/replacing current
scene, then unloaded/deleted. Receipt Saved/Diagnostics/PikeSlide/restored-scene.json;
Tools/SwordHolster/RestoreArmPikeScene.py. Historical arm hit was upperarm_l,t0.266667.

**October21 coupled pike solver — built, loaded, measured:** replaces unswept
post-Step sword teleport with a per-joint five-row physical solve of transverse
motion and rotation, inside Jolt's normal iterations before contacts. Existing
Set Pike Wound Correction node/tag retained; only marked hard X/Y+angular locks
with Z free/limited qualify. Stock axial motor/limit and reaction/break reporting
retained. No iteration override, new scans, mass overwrite or collision-filter
change. Native case rejects unsupported constrained body axes/singular mass matrix
while retaining original joint. Old broad Python preview absent after restart.
**Saved A_Sword node Enabled is FALSE (user setting), preserved.** User must tick
it to try the new solve; no BP/map/tuning saves or wiring edits in this task.
Exact restored arm comparison: same15-frame precontact prefix/upperarm_l hit at
0.266667s;74 joint samples. Off peak lateral5.223108cm/RMS2.339469cm/rotation44.3044deg;
on peak.0751295cm (0.7513mm)/RMS.0119437cm/rotation.684620deg. Both owned captures
ended; no user Play stopped. Independent blade/wall and spin fixtures retain wall
blocking; strongest tested contact leaves~3mm transient joint error, so no claim
of universally exact alignment or collision-proof arbitrary configurations.
Isolated UE automation Prophecy.Jolt.Constraints.PikeWoundCorrection passed;
node/Blueprint reflection status3/native_properties0/pin_types0 verified. Saved
map/sword hashes match pre-restart; editor2612 open /Game/explosionVFX, stopped,
no dirty packages at final check. User authorized restart for RAM. Clean Slate
shutdown; cancelled own in-flight LC UBT to release shutdown wait. Normal build
30actions found one PI namespace error;5-action retry passed18.32s. Normal DLLs
current. Source + small standalone fixture Tools/Jolt/PikeJointLab; procedures,
measurements and caveats in Docs/JoltSkeletalProps and Saved/Diagnostics/CoupledPike
(~1.1MB). No video/user Play demo started beyond the two diagnostic captures.

**October21 Play-camera ZQSD — loaded and bindings verified:** user requested
ZQSD instead of WASD. DefaultInput FlyCam mappings changed; native DefaultPawn
requires the existing editor helper's new3-key remap (Q descent moved to A).
Only ProphecyDebugCameraInput.inl/config/tools changed; no maps/BPs/Play touched.
After the shared Live Coding build succeeded, Tools/SetPlayCameraZQSD.py installed
the helper at09:06UTC. Log verified changed=3 ZQSD=1 QDescends=0; loaded FlyCam
axes verified Z/S and Q/D. No Play started/stopped, no asset saves or restart.
Normal DLLs remain stale: normal build needed before future cold launch.
See Docs/DebugCameraInput.md. User retains motion testing.

**October21 wound correction left enabled — supersedes one-shot demo:** user
explicitly requested keeping it in. ShowPikeWoundProjection.py --keep-enabled
now stays registered across Stop/Play in this editor, with no demo timeout or
automatic Play control. Attached to existing user Play without stopping it.
Same lateral-only Python prototype, no native build/BP edits/saves; normal
iteration budget. Clears world references between Play sessions, rebinds next
Play. Editor restart still needs reinstalling this helper; not packaged runtime
code. Dirty A_Sword preserved. Do not revert to one-shot behavior unless asked.

**October21 wound demo rearmed — user controls start:** previous demo was stopped
by user; callback retired. User missed the motion while assistant launched it.
ShowPikeWoundProjection.py --arm now waits for their next Play press (up to10min),
then applies the same temporary correction through that Play only. Do not launch
Play for them. No save/build/wiring changes; dirty A_Sword preserved. Stop Play
retires the callback. Receipt show-wound-anchor.json records armed/active/retired.

**October21 wound-line visual demo — Play left running for user:** user asked to
judge the temporary post-solve sword translation. ShowPikeWoundProjection.py now
runs it in the current scene; first cut t0.266667, 74 corrections over1.2s,
maximum shift0.807332cm, same as prior prototype. Normal iteration budget;
no rotation/velocity edits, native build, asset save or BP changes. Callback
retires on Stop Play/world replacement/error or10minute safety timeout. Do not
stop this user inspection session. Initial owned attempt hit a Python validity
API error before any correction; ended only that failed owned Play and reran
with SystemLibrary.is_valid. Receipt Saved/Diagnostics/PikeSlide/show-wound-anchor.json.

**October21 wound-pivot follow-up — transient prototype only:** user rejected
higher iterations and suggested rotation should preserve wound contact. No Play
was active when removal checked, so overrides were already discarded. Current
joint stores arm wound anchor, not an explicit hilt hinge; native SixDOF linear
Jacobian uses wound lever arm, but finite solver leaves lateral residual. Tested
post-step lateral-only wound-to-blade-line projection at normal budgets, same
first-contact prefix. Maximum residual0.000003915cm (by construction), maximum
per-frame correction0.8073cm; max rotation error21.768deg vs44.304deg baseline.
Keeps orientation, axial travel and velocities from native solve. Existing physical
adapter forwards the translated sword pose. Owned Play ended; no production
code/wiring/asset change or build. This is a Python prototype, not a deployed fix
or a conservation/performance claim. See JoltSkeletalProps/PikeSlide receipts.

**October21 user visual iteration trial — Play left running:** user asked to see
the higher-iteration effect. ShowPikeIterations.py started Play and applied
transient10velocity/32position to victim mannequin at first cut,t0.266667;
native log verified10/32. Callback unregistered after application. This Play is
now for user inspection: do not stop it. No saved tuning, BP or camera changes;
dirty A_Sword present before starting. Stopping Play discards iteration overrides.
Receipt Saved/Diagnostics/PikeSlide/show-iterations.json.

**October21 sword depth stain — additive, installed/saved:** A_Sword
**Stain Blade(Depth, Seed)** keeps Max(previous,Clamp(input,0,1));0 adds nothing,
.5tip-to-half,1tip-to-hilt. Seed(int0 default) chooses a repeatable±20deg/slightly
wavy edge, locked on first positive stain; shape translates unchanged with depth.
Blade-local Y and scaleY/Z compensate nonuniform scale. Seed upgrade compiled
status3/saved,1editor compile173.52s/no restart; existing caller Depth links intact.
Existing paint MID/RT retained; generated sword blood
material unions painted mask with depth using shared blood shading. Later paint
recognizes/reuses depth MID. No tick/traces or event rewiring;24other graphs
verbatim, BP status3/saved. Original M_Sword untouched; first companion superseded.
Live Coding runtime/editor2actions and editor repair1action passed/no restart.
NORMAL DLLS STALE: next normal build must include paint-manager resolver/reset
changes before cold launch. No visual Play test. See BloodExperiments opening
and Saved/Diagnostics/SwordBloodDepth; user scene unchanged.

**October21 arm pike lateral drift — investigated, no production change:** current
upperarm_l cut starts aligned; X/Y and all rotation axes Locked, blade Z Limited.
Both frames stay fixed but native/visible error reaches5.223cm/44.304deg.
Same-prefix transient10velocity/32position comparison reduces to0.550cm/14.006deg;
confirms convergence sensitivity, not an approved high-cost fix. Unreal projection
is enabled in profile but not implemented by Jolt adapter (linear alpha1;
angular alpha0). No build/restart/assets saved; owned Play ended, transient solver
settings retired. Dirty NS_bloodwound/map preserved. See JoltSkeletalProps opening
and Saved/Diagnostics/PikeSlide. Next fix should be scoped to cut/slider behavior.

**October21 recovery AE regularizer running:** user restores frozen AE on
perturbed get-ups only, additive to full position MSE. Fixed weight.2752568
calibrated for10% combined pose+AE cost on latest88363_final's evaluation.
Latest saved locally/S3 before resume; normal rows/settings unchanged. Live
20261021_091317_uefn_getup_ae10_512 on L4w9aq90rzkg1d0g until stopped, $.59/hr;
trainer696/guard697,bridge13512/dashboard1724. Verified88384 at~9.29ktransitions/s,
new checkpoint readback and actual18perturbed AE/2normal zero-AE replay rows.
See MimicKitTraining opening and getup-ae calibration/verification receipts.

**October21 locomotion AE30/MSE30 — running/verified:** latest78988_final
(1.294B) preserved locally/persistently, resumed sameL4rjsan0uitu03qd until-stopped.
Perturbed only:AE through30ticks,linear blend toMSE at60;originalAEweight6.94265826.
Normal rows/settings unchanged. Live20261021_091005_uefn_locomotion_ae30_mse30_yaw180_512,
trainer701/guard702;78989→79009 verified,~11.65k transitions/s,newbackup verified.
Replay confirms0/.5/1tracking weights at30/45/60. Recovery branch untouched.
See MimicKitTraining opening and Saved/MimicKitLocomotion/ae30-verification.json.

**October21 node rename — live, no restart/build:** Accept Pike Hit now displays
**Cancel Hit Reaction**. Updated native UFunction DisplayName metadata through
remote Python and the narrow header's DisplayName for future builds; underlying
AcceptPikeHit function, pins and behavior unchanged. Native graph audit confirms
new title; full live A_Sword exports SHA-identical before/after. User's dirty
A_Sword preserved unsaved. No Play/compile/save/restart. Metadata-only source
change is not yet in normal DLLs: next normal build incorporates it; until then
`Tools/SwordHolster/RenameHitReaction.py --apply` reapplies after a cold launch.
Receipt Saved/Diagnostics/CleanPike/rename.json.

**October21 clean pike entry — installed/verified:** Blueprint acceptance stays
editable; joint settings untouched. New Enable Clean Hit Continuation at sword
BeginPlay and Accept Pike Hit after existing pike gates replace pose/velocity
together before rendering. Accepted pikes bypass old teleport/additive velocity
correction; slash path preserved.24graphs/3,937 original pins/defaults retained,
four added nodes/ten link changes. Scope: free dynamic sword, one collision
substep, no existing joint/weld or second solved pair; refusal exposes Reason.
Normal build11actions/200.87s passed; CleanPike and existing HitEvents tests pass.
Actual unchanged scene accepted at0.266667s: velocity exactly incoming
(997.336864,0,-260.963416)cm/s, forward continuation. A_Sword saved; map hash
preserved. Editor15456 open explosionVFX/A_Sword, owned Play ended/no dirty assets,
reflection status3/native_properties0/pin_types0. Normal DLLs current.
See Docs/JoltSkeletalProps.md and Saved/Diagnostics/CleanPike.

**October21 blood mesh shadows — user verified:** active Fountain001 mesh renderer
in NS_bloodsplat2 uses new M_Blood_ShadowOnly, masked ShadowPassSwitch(0 visible,
1 shadow); original sprites/material and mesh geometry/scale retained. Only
material and NS saved; user confirmed shadows work. See Docs/BloodExperiments.md.

**October21 recovery resumed:** verified85149(1.395B) after storage cleanup,
same settings, replacement L4w9aq90rzkg1d0g at$0.59/hour until-stopped.
Old recovery GPU unavailable; retained disk preserved. Locomotion managed in
separate chat. Run20261021_074429_uefn_limp_floor_512,trainer479/exitguard480;
verified85150→85170 at~10.63k transitions/s and new85150 persistent readback.
Bridge18464/dashboard7392; TB and20-row replay available. Exact saved recovery
source retained via SHA-pinned launcher verification. See MimicKitTraining.

**October21 locomotion resumed:** latest75533 (1.238B samples), unchanged
settings and until-stopped authorization. Old L4 could not restart; replacement
L4rjsan0uitu03qd at$0.59/hour, live20261021_074500_uefn_locomotion_mse_yaw180_512.
Trainer481/exitguard482,bridge4900/dashboard22724. First75534 checkpoint
backup verified after fresh checkpoint-sized storage write/readback. Recovery
branch untouched. See MimicKitTraining opening and locomotion resume receipt.

**October21 authorized checkpoint cleanup:** latest recovery85149(1.395B) and
locomotion75533(1.238B) downloaded, SHA256/ZIP verified, preserved locally in
each branch's preserved-latest folder and in persistent storage. User-authorized
older physical loco/get-up checkpoints/replays removed:46.58GB persistent,
5.26GB local. Datasets, code, TB history, crawl/other Unreal models untouched.
No training restart. See MimicKitTraining opening and cleanup-20261021 receipts.

**October21 training status correction:** both Runpod pods are now EXITED.
Follow-up confirms shared persistent storage quota exhausted: even18-byte
PutObject fails QuotaExceeded. Failed-backup shutdown is the strong common
explanation; exact exit logs still unavailable. Free safe storage and verify
checkpoint-sized backup before any paid restart; no user files deleted here.
Locomotion stopped October20 22:01:00 Warsaw; recovery stopped22:01:37.
Runpod labels both `Exited by user`, but the caller/cause remains unidentified;
do not infer a user instruction or a training crash from that label. Recovery
control still says until-stopped. No restart performed. Recovery replay and
saved evaluation metrics recovered through85149 (1.395B samples); missing raw
training events remain unavailable. See MimicKitTraining opening for evidence.

**Independent locomotion branch — October20, running and verified:**
User resumes preserved pre-split73832_final(1.210B samples) on a NEW L4,
cb2i8leh2qpjdf at.59/hour until user stops it ("ad vitam" supersedes8hours).
All controls in Saved/MimicKitLocomotion, separate from recovery
Saved/MimicKitEquipment/new5546ihvxeax; recovery training untouched.
7%idle/93%loco, each30%normal/70%perturbed; no get-ups or AE.
Pure tracking MSE fromtick0; perturbation yaw[-180,+180],initialCOM2 velocity
preserved;120tick perturbed horizon,300normal. Existing termination rules/
penalties,50/50walk/run and split-checkpoint optimizer settings retained.
Live run 20261020_211208_uefn_locomotion_mse_yaw180_512, trainer435/exitguard436.
Verified advancing73833→73913, persistent checkpoint73833 readback, actual AE
not loaded, correct row allocation and120tick replay horizon; ~11.4–11.6k
training transitions/s. Bridge25868/dashboard27124; setup watchdog released
only after progress/backup verification. Recovery pod/control hashes unchanged.
See MimicKitTraining opening and deploy_locomotion_branch.py.

**Sword Slow Start clock — October20 fixed/verified:** user's true/5 startup
still called SetFixedFrameRateRuntime(5), yielding0.2s physics steps while
authored clocks spent1/60. Startup now retains fixed60 and uses t.MaxFPS with
existing slow value; normal startup and End Play restore cap60. Four added BP
nodes, six existing pin changes only;24graphs/3911live original pins preserved.
Actual Play true/5: all deltas1/60, cap5, measured4.636FPS;0.2simulation seconds
over2.588wall seconds. End Play cap60 verified. A_Sword saved; no map/tuning
or runtime-physics changes. Helper's first application crashed on obsolete
BuildString_Float lookup before save; corrected to Double with safe preflight,
normal one-unit build65.34s passed, isolated graph/compile validation completed,
then live edit/test/save passed. Prior saved sword hash preserved through crash.
Normal DLLs current. Editor29136 reopened explosionVFX, outside Play, cap60,
no dirty assets; reflection status3/native_properties0/pin_types0.
See Docs/SwordHolster.md October20 and Saved/Diagnostics/SceneClock.

**Separate skeletal blood brush — October20 installed/verified:** placed
**the decal manager** now exposes Blood Paint > Skeletal Brush Radius (3cm).
Ordinary/floor brush radius remains user's2cm. Pure component cast/select on
ordinary paint path; four added nodes,490 existing authored pins retained,
only three data-pin link changes, execution wiring unchanged. Actual wound
Play127 accepted hits: skeletal3cm/static2cm; owned Play ended.
After repeated Live Coding memory exhaustion user authorized save/restart.
Saved dirty A_Sword and NS_bloodsplat2 with backups; A_DecalManager already
preserved/saved. Their hashes remain intact. Shutdown exposed duplicate blood
callback listener removal; existing atomic guard now unregisters once and skips
dead-object delegate cleanup. Normal builds54.93s/75.79s/64.29s passed, each one
compile unit; isolated startup/shutdown exited0. Normal DLLs current.
Editor14720 reopened explosionVFX, new BP control saved/opened, no dirty assets
or Play; reflection status3/native_properties0/pin_types0.
See Docs/BloodExperiments.md and Saved/Diagnostics/SkeletalBloodBrush.

**Limp blend floor correction — October20 19:34, verified running:**
Resumed latest79848_final, preserved locally and persistent readback verified,
as20261020_193455_uefn_limp_floor_512. Perturbed starts now receive minimum
upward root shift to clear every collider AFTER blending; joints/orientation/
XY/velocities unchanged. GPU batched FK/support only at reset, no physics-step
projection.42,020offline cases and18actual new replay starts clear floor.
Same L4new5546ihvxeax,trainer849/exitguard850;bridge12596/dashboard22876.
Verified79869advancing/79849backup; handoff watchdog released.
Early throughput10.69k transitions/s versus10.41k before: no observed slowdown
in this short comparison. All other curriculum/reward settings unchanged.
See MimicKitTraining opening and limp-floor verification receipts.

**Limp blend floor defect — October20, diagnosis preceding correction:**
Exact screenshot step79324 row11 reconstructed within1.42micrometres.
79.1% whole-pose blend to limp index31 places right hand44.5cm underground,
head25.8cm; saved limp endpoint only0.9cm penetration. Intermediate blended
pelvis height fails to clear the rotated/articulated body.16/18 replay starts
exceed5cm. Needs floor support recomputation after blending, at reset only.
Diagnostic turn did not modify or stop training; subsequently corrected above.

**Recovery limp curriculum — October20 19:09, verified running:**
User marks183047 stale; restart its initial79023_final, restore noise.075/
GAE.98/previous MSE leeway, retain50/50front/back.154normal/358perturbed,
normal77frame0/77random. Perturbed poses uniformly blend vanilla frame0 to
saved limp whole pose INCLUDING pelvis position/rotation; velocities unchanged.
Failure low-head check tick80 instead60. No AE or new physics changes.
Current20261020_190959_uefn_limp_blend_balanced_512 on same L4new5546ihvxeax,
trainer600/exitguard601,until stopped. Verified79044 advancing at~10.5k
transitions/s and79024 persistent backup. Handoff watchdog released.
Bridge11944/dashboard21884. See MimicKitTraining opening for details.

**Recovery settings restored — October20 18:30, verified running:**
Current20261020_183047_uefn_normal_balanced_no_leeway_512 resumes latest
79023_final preserved locally and in S3. Noise.05,GAE lambda.95,no position-MSE
leeway;front/back50/50,each128frame0+128random-frame. Fixed correlated motion/
start selectors by stratifying starts within each motion. No stiff/limp deployment.
Two startup-only errors on removed leeway compatibility/metadata fixed;
failure guards stopped billing, no checkpoint updates/loss in failed starts.
Old L4 unavailable after stop; replacement L4new5546ihvxeax at.59/hour,
trainer422/exitguard423,until stopped. Verified79034 advancing and79024 backup;
setup watchdog released. Bridge17828/dashboard15268. See topic opening.

**Recovery start split — October20 17:14, verified running:**
Current run20261020_171428_uefn_normal_back80_half_random_512 resumes latest
77390_final (1,267,974,144 samples), preserved locally and persistent readback
verified. User changed only start distribution:256normal frame0 +256normal
random-frame rows;410back/102front retained. No stiff/limp/perturbed rows.
Same L4rovwuwstkm0s7r,trainer729/exitguard730,until-stopped authorization.
Verified iteration77521 advancing; checkpoint77491 backup verified.
Bridge448/dashboard8920 publishing; handoff watchdog released after verification.
See MimicKitTraining opening; supersedes frame0-only setup below.

**Stiff / limp initialization datasets — October20, prepared only:**
User names the rotated/grounded1,000 poses "stiff inits". Derived "limp inits"
by simulating each independently for10policy frames (80physics steps,1/3second)
with all actuators disabled, gravity and training contacts active. Native
configured MuJoCo CPU, same model construction/profile as training.
Saved/MimicKitEquipment/limp-inits/corpus.npz includes actual final poses and
velocities, with source index mapping. No warnings. Soft contacts leave median
0.94cm / maximum3.14cm floor penetration; retained exact snapshots, no correction.
Preview http://127.0.0.1:8843/Saved/MimicKitEquipment/limp-inits/.
Training untouched. See MimicKitTraining opening.

**Grid3D fuse visibility — October20 config change, untested by request:**
DefaultEngine.ini [ConsoleVariables] now forces r.HeterogeneousVolumes=1 above
scalability priority, preserving other quality settings. Installed UE5.7 source
confirms this config section also loads in Shipping. Applies next startup/future
packages; no live command, build, restart or runtime test. See Docs/BombFuse.md.

**Random recovery poses — October20, whole-body rotations baked:**
The1,000 retained poses now also have a separate rotated/grounded dataset at
Saved/MimicKitEquipment/random-phat-poses-grounded/corpus.npz. Uniform SO(3)
root orientations, exact same local DOFs, zero velocities; minimal root height
against Z=0 using every collider. All1,000 nonpenetrating; lowering any pose
1micrometre causes penetration. Preview opened at
http://127.0.0.1:8843/Saved/MimicKitEquipment/random-phat-poses-grounded/.
Upright source preserved. Not deployed to training. See MimicKitTraining opening.

**Random recovery initialization corpus — October20, awaiting visual approval:**
Retained the exact first1,000 independent PHAT-admissible poses, pelvis fixed upright at
Z0.931191m, zero velocities. First10 shown in
http://127.0.0.1:8843/Saved/MimicKitEquipment/random-phat-poses/.
All14,000 retained joint cases accepted by the project Jolt limit probe; current saved
PHAT fingerprint verified. No floor/self-collision filtering (133 floor overlaps).
Poses1,001–1,500 archived into Windows Recycle Bin at user's request; preview
and generator now retain1,000, preserving the original sampled prefix.
Not deployed to training; current normal-back80 run left untouched. User must
vet before initialization changes. See MimicKitTraining opening.

**Automatic blood Niagara callback — October20 installed/verified:** placed and
spawned systems exposing User.decal_callback now bind the existing level's unique
callback manager automatically during Play. Valid explicit callbacks retained;
wrong Blueprint-asset references corrected. Creation/activation and level events,
cached manager lookup, no per-frame scan or timer. Ten owned-Play checks passed,
including attached effects and actual pool reuse. Normal incremental build365.77s
plus one-unit loading guard59.82s passed; normal DLLs include earlier sword and
decal-depth fixes. Editor26512 reopened explosionVFX, outside Play, no dirty
packages; reflection status3/native_properties0/pin_types0. User dirty map and
NS_bloodsplat saved with prior-byte backups before restart; all four saved
map/NS/manager/sword hashes preserved through testing. Floor-paint issue below
was subsequently repaired. See Docs/BloodExperiments.md automatic-callback
section and Saved/Diagnostics/BloodAutoCallbacks.

**MimicKit temporary normal/back focus — October20 15:50, verified running:** user
requested100% normal get-ups,100% frame0,80% back. Latest recovery74681_final
downloaded and S3 SHA verified. First154538 startup caught a body-name variable
shadowing error; guard stopped billing. Fixed/tested, runtime restored on same
L4. New155034_uefn_normal_back80_frame0_512,trainer483/guard484 until stopped. Fixed410back/
102front rows;0perturbed/random-frame. No reward change: suggested normal
completion bonus has not been authorized/applied. Prior recovery50/50 plan
saved normal-back80-previous-plan.json; no automatic switch-back scheduled.
Live batch verified512normal frame0,410back/102front,0perturbed/random/prior.
First74682 backup verified; replayer20normal rows and failure card working.
Mixed73832 checkpoint remains preserved for loco.

**Actual injury floor painting — October20 repaired/verified:** user fixed the
floor execution wire; remaining failures were tiled floor UV0 sending stamps
outside the RT and mapping MI_ProcGrid to generated parent M instead of preserving
MI. Asset-only repair uses an18KB project mesh copy with normalized UV0 and correct
generated material instance with original overrides. Same floor geometry,
transform, world-position grid appearance and1024RT; no native code/build/restart
or extra runtime work. Actual wound Play, foliage decals hidden: visible surface
stain,16 painted mask pixels vs0 before. Zero-intensity vs original material
capture pixel-identical; painted changes3,843pixels. User wiring preserved/saved.
Map, mesh, MI and generated parent saved (force-save parent needed as loaded
package had no file); editor26512 explosionVFX outside Play, no dirty packages.
See Docs/BloodExperiments.md opening and Saved/Diagnostics/FloorPaintFix.

**Separate decal rendering — October20 fixed/loaded, not the requested paint:** injury callback and
floor occupancy already worked; debug rectangles hid a rendering regression in
the rectangle adapter. Projectors barely overlapped the floor, reducing material
opacity to~13% through UE's depth fade. Centre now follows receiver+bounded surface
offset, keeping full opacity; no new recurring work/layout change. One-action
Live Coding134.49s passed/reloaded13:16:19UTC, rectangle regression passed
13:16:41UTC. Final actual injury capture visibly stains floor (19 decals).
No assets, materials, emitters, tuning or Blueprint wiring changed/saved.
At verification editor29912 was outside Play, sword graph identical.
**Build state superseded:** automatic-callback normal build above incorporates
this fix; editor26512 is open on explosionVFX outside Play.
See [blood rendering repair](Docs/BloodExperiments.md#injury-fountain-invisible-floor-stains--october20)
and compact evidence Saved/Diagnostics/InjuryBlood.

**MimicKit recovery/locomotion split — October20 15:14, verified running:** user now
wants separate policies. Latest mixed checkpoint73832_final downloaded locally
and verified against S3 SHA221ed14975999aab1846e53758113bb228418827acd4edbf8403ca1b05ba3699.
Preserve it for the user's locomotion fork; receipt
Saved/MimicKitEquipment/recovery-split-loco-fork-checkpoint.json. This chat owns
recovery-only run20261020_151434_uefn_recoveries_only_512 on existing L4
rovwuwstkm0s7r, trainer2478/guard2479. Requested512 rows:128 normal frame0,
128 normal random frames,256 perturbed with existing2:1 upper-half skew.
Live cohorts verified exactly; first73833 backup verified,73843 advancing at
~8ktransitions/s. Mixed starting checkpoint has1,209,679,872samples; preserve it.
Replayer20 get-up rows and both failure cards verified. **Locomotion fork must use separate run/control
state and must not stop or repurpose this recovery pod.** See topic opening.

**Sword/skeleton penetration — October20 repaired/loaded:** external constraints
now reuse passive skeletal props' existing Jolt bone handles. Scene collision
changes forward to the same rig, preserving QueryOnly trace bodies and native
simulation. No retained layout changes. Live Coding: three compile actions
188.76s, then one test-fixture correction121.44s; both loaded. PlacedMannequin
test passed12:59:04UTC, including joint reuse/no duplicate rig, channel-only and
response updates, restoration and teardown. Current explosionVFX owned Play
confirms nonzero native cut-joint forces and depth minimum0.606992 (~39% blade
penetration), then existing physics/Blueprint lets it come back out. No permanent
sticking claim. Sword graph identical; no wiring/tuning/assets changed or saved.
At verification editor29912 was outside Play. **Build state superseded: the
automatic-callback normal build above incorporates this fix.** First
reload logged RigVM access-detector ensures; subsequent Play/test passed.
See [skeletal props repair](Docs/JoltSkeletalProps.md#sword-penetration-repair--october20-installed).

**MimicKit settings adopted — October20 14:10:** user approved noise0.075 and
GAE lambda0.98 from the completed comparison. Active
20261020_141039_uefn_getup_success_value_512 resumes latest72108_final/
1,181,433,856 samples, preserved locally and verified in S3. Same L4, until
stopped; trainer2154/guard2155, bridge25552/dashboard21856. Actual post-restore
noise verified0.075 and GAE0.98. Normal get-up failure card now counts all
completed normal get-up episodes every10updates, same cadence as perturbed
cards. Normal/perturbed−100 failure costs and success fix retained. First72109
backup verified;72119 advancing at~7.9ktransitions/s. See topic opening.

**Focused comparison complete — October20 13:55:** noise.075/GAE.98 modestly
better than current.05/.95 with success fix: failures30vs36 at64updates,
23vs32 at128,928 identical get-up starts; training411vs408seconds. No normal
loco regression. One training seed, short horizon; both test configs predate
normal-get-up−100 change. No alternative applied. Queue1224 exited.
Main133905 continues with normal-get-up−100,71741/1.175B,~8.3ktransitions/s,
backup71641 verified. See MimicKitTraining opening.

**MimicKit normal-get-up penalty — October20 13:39:** user requested same−100
failure penalty for normal get-ups. Active133905_uefn_getup_success_value_512
resumes latest71440_final/1,170,489,344, locally/S3 verified. Trainer1587/guard1588,
same L4 and until-stopped budget. First71441 backup verified. Normal completion/
timeout unchanged, perturbed success fix retained. Focused comparison1224 was
paused during handoff and is resumed; both copies retain the frozen pre-change
objective for a fair comparison. Details in MimicKitTraining opening.

**MimicKit focused comparison requested — October20:** user now explicitly asks
to retry noise.075/GAE.98 against current.05/.95 with success fix. Bounded two-way
comparison queue1224,128updates each from70639, held-out evaluation at64/128.
No broader sweep or automatic live setting change. Main130053 continues unchanged.
See focused-success-launch.json and MimicKitTraining opening.

**MimicKit sweeps stopped — October20 13:15:** user objects to repeated sweeps.
Queue551 and its process group stopped, cancel.request set; do not restart
comparisons automatically. Main130053 remains training,70890/1.161B samples,
no failure. Earlier completed sweeps showed only modest improvement; no major
learning-speed gain established. Latest70639 baseline894/928 successes versus
current settings895/928 after64updates; other latest variants incomplete.
Keep live settings unchanged. See MimicKitTraining opening.

**MimicKit corrected resume — October20 13:01:** active
20261020_130053_uefn_getup_success_value_512, from70639/1,157,365,760 samples,
with known success value100. Same L4rovwuwstkm0s7r,.59/hour until stopped;
trainer444/exit guard445, bridge21024/dashboard29160. First70640 S3 readback
verified. Isolated corrected-success sweeps queue551 now starts from70639 too,
not the superseded67931. Results pending. See MimicKitTraining opening.

**MimicKit stopped by user — October20 12:55:** rollback67931 was too early.
Trainer saved68077; local download matches verified S3 SHA. Sweeps cancelled;
owned L4rovwuwstkm0s7r confirmed EXITED, billing stopped. User points to the
failure-curve trough immediately before its rise around1.159B. Selected retained
70639/1,157,365,760 samples (6.20% reported failure), last saved checkpoint before
the trough/rise; downloaded and ZIP checked. Do not reuse67931 or resume sweeps
from it. Training remains stopped. See latest MimicKitTraining opening.

**MimicKit resumed — October20 12:46:** active
20261020_124643_uefn_getup_success_value_512 on L4 rovwuwstkm0s7r,
.59/hour until stopped, trainer484/exit guard485. Rolled back to verified67931;
head success value100 enabled. First new67932 checkpoint S3 readback verified;
steps advanced to67952/1.11334B, ~8.1k transitions/s before sweep load.
Deleted69 old local replay JSONs,1.97GB; checkpoints/TB retained. No eligible
standalone old rollouts on persistent volume, no persistent deletion.
Storage API access recovered across datacenters without persistent cleanup;
underlying provider cause unknown. All temporary CPU helpers stopped, no relay.
Corrected-success learning sweeps resumed (queue577), results pending.
See opening of Docs/MimicKitTraining.md.

**MimicKit storage investigation — October20 12:31:** no trainer running;
latest L4 9r63p3vlvogqz5 and temporary CPU helper both confirmed stopped.
Full runtime SHA-verified locally with AWS downloader; pod S3 requests still
time out. Sudden underlying cause unproven. CPU direct mount listed files,
but full reads/relay not yet verified. Additional.06/hour relay approval pending;
user asks for root cause instead. See opening of Docs/MimicKitTraining.md.

**Directly placed mannequins — October20 installed/verified:** user requires
Jolt for skeletal mannequins dropped into scenes, including future placements.
Scene discovery now binds standalone SkeletalMeshActors with physical PHAT
collision to a passive shared-world Jolt articulation. Existing agents unchanged;
no NN/controller added. Visible pose and retained QueryOnly blood receivers follow
Jolt; standard velocity/force/impulse dispatch supports the new binding. Failed
admission freezes/reports instead of silently simulating Chaos. Six-action normal
build103.66s passed; PlacedMannequin test passed10:12:11UTC, zero errors/warnings
(floor contact, pose/query alignment, standard velocity, late spawn, scaled mesh,
cleanup). Saved dirty user Sword/map with backups before necessary restart.
Editor13868 reopened explosionVFX normally; owned live Play confirmed one Jolt
binding, dynamic pelvis and Chaos simulation=false across three frames. Ended
owned Play; no dirty packages. Original saved hashes verified. New native layouts
are in current normal DLLs. See [skeletal props](Docs/JoltSkeletalProps.md);
evidence Saved/Diagnostics/PlacedMannequin20261020.

**MimicKit rollback authorized — October20:** user now requests resume before
stalling, then continue sweeps.67931_final/1.113B selected with buffer before
known-good69138, local+fresh S3 verified. Explicit head-reset success value100
implemented/tested (99 bonus once, zero bootstrap, perturbed get-ups only).
Old L4 unavailable; replacement iiprikebnm51jl setup blocked by persistent-storage
timeouts, finally HTTP524. Replacement confirmed stopped12:09 before10minute
cutoff; both GPUs off. No trainer or new sweeps started. Code/checkpoint prepared
and tested, locally and S3 verified before allocation; no disk-full evidence or
deletion. Resume remains pending storage access. See
[MimicKitTraining](Docs/MimicKitTraining.md).

**MimicKit held — October20 11:38:** user asked to investigate head-reset avoidance
before restarting. Owned L4 ka68jrougesuit confirmed stopped. Latest70939/1.162B
checkpoint downloaded locally, SHA matched retained disk; S3 readback timeout
stopped previous trainer at71039 (not saved).70939 persistent verification pending.
Offline replay confirms get-ups hovering85–87% and timing out while earning~.85/tick.
Success has no explicit credit; TIME reset bootstraps poorly anchored final-state
critic estimates. Proposed known success value, no reward changes deployed.
All learning ablations/confirmation finished; candidate noise.075/lambda.98 offers
modest gain and better normal-get-up retention; not deployed. Details and resume
constraints in [MimicKitTraining](Docs/MimicKitTraining.md).

**MimicKit harder get-up sampling — October20 09:46:** resumed verified latest
69138_final with2/3 of perturbed get-up starts above50% strength,1/3 below.
Active094614_uefn_getup_skew_linear_512, trainer8547/guard8548 on existing L4,
until stopped; other training settings retained. Sequential disposable learning
ablations running; no candidate deployed. See [MimicKitTraining](Docs/MimicKitTraining.md).

**Special attacks / grab independence - October20 refined, isolated/verified:**
Managed checkout `C:/Users/singerie/.codex/worktrees/grab-special-attacks/Prophecy`.
Start Special Attack now has Release Grab0..1,default.8, relative to retained clip;
0 immediate,1 at completion. User-confirmed Cut Early convention changed:0 full,
positive value is clip endpoint (.8=80%,1=full). Pelvis frame-zero heading matched
once at entry; authored subsequent turns retained. Fresh editor clips finish their
pending compression before sampling (validity alone returned temporary ref poses).
Final4-action normal build46.55s passed.12 cases passed: four physical two-hand
projections, immediate/end/trimmed release, four world headings and Cut Early1.
Accepted entry-pose heading error<.000004deg; both regional and ordinary end events
once. Current video `Saved/SpecialAttacks/projection-refined.mp4` replays measured
UE/Jolt transforms. Main editor/source/assets untouched; **not installed live**.
Exact24-file baseline manifest/patch retained. See
[current work](Docs/SpecialAttacksAndGrabIndependence.md).

**MimicKit LR comparison — October20:** isolated10-full-update2x/4x/8x tests
finished. On928matched get-up starts: baseline794successes,2x792,4x792,fixed8x787.
8x hits guard8of10updates; no demonstrated gain over current2x. Live7410 unchanged.
Single training seed/short horizon; do not claim a long-run winner.
Details: [MimicKitTraining](Docs/MimicKitTraining.md).

**MimicKit continuation — October20 08:57:** user authorized double actual actor
LR and the verified observation optimization. Latest67931_final/1.113B samples
preserved locally and S3 before resume. Active085731_uefn_lr2_graphed_linear_512,
L4ka68jrougesuit, trainer7410/guard7411, until stopped. LR5.625e-7→1.125e-6;
Adam state/KLguard retained. Observation graph/device quaternion optimization and
replay fixes deployed; reward/physics/distribution unchanged. First new backup
verified; details in [MimicKitTraining](Docs/MimicKitTraining.md).

**MimicKit get-up learning audit — October20:** live run unchanged. Failure rate
still improves slowly (~18.3→17.8%); remaining failures concentrate in strongly
perturbed front starts. Actual restored actor LR is5.625e-7 (1/8 YAML), inherited
from earlier guard reductions, not a new slowdown. Isolated matched update favors
a2x LR trial;8x worsened getup surrogate. No tuning deployed. See
[MimicKitTraining](Docs/MimicKitTraining.md) for measured counts and limitations.

**MimicKit replayer repair — October20:** valid recordings from the new locomotion
failure-penalty run were rejected because the replay reward check omitted that
penalty. A second downloader retry bug then replaced the archive with its last
chunk. Both repaired locally; cloud trainer4368 unchanged and still advancing.
Failed downloads now restart from byte0 and preserve existing valid rollouts.
Details and verification: [MimicKitTraining](Docs/MimicKitTraining.md).

**Sword pre-impact first-collision follow-up — October20:** update-current-values
is correctly called inside ReceiveHit. Live log rejects placed A_Sword1 from Jolt
because MACD=true; Chaos events therefore return invalid/zeros. Switched only
that placed sword to supported ordinary CCD (MACD=false/CCD=true), verified after
component reconstruction. Map dirty/unsaved; no Play/build/restart. Class/child
defaults unchanged, still MACD=true. See Docs/HitImpactSpeed.md.

**Sword pre-impact node — October20 rewind installed/verified:** user rejects
per-sword tick storage and requests backward extrapolation from incoming motion.
Removed the proposed history map and both per-tick capture passes. Same node/pins
now rewind one full current physics-step duration from the contact sample using
constant incoming COM/angular velocity, including welded component lever arms.
Estimated earlier pose, not an exact previous-tick boundary; impact speed remains
measured contact-time. Current user Tip Distance=Blade+HiltHalfLength; don't restore
older double-hilt guidance. Dirty Sword preserved/saved before required shutdown,
sha5b33859a...; editor29952 exited cleanly. Superseded history build passed but was
not reopened. Replacement8-action normal build124.62s and focused hit test passed
11:17:24UTC with zero test errors/warnings (first hit, rotation, moving target,
kinematic, welded COM offsets/both orders, CCD substeps and changed velocity).
Editor9572 reopened explosionVFX normally; Sword saved SHA unchanged. Owned Play
first sword depth1.054566, versus earlier recorded0.911003, incomingZ-732.189798.
Ended owned Play. No promise every contact depth>=1; no depth clamp or BP edits.
See [HitImpactSpeed](Docs/HitImpactSpeed.md),
Saved/Diagnostics/SwordPreviousTick20261020 preservation and
Saved/Diagnostics/SwordRewind20261020 current evidence.

**Shared blood manager — October20:** user requested consolidation for sword
compatibility. Repaired original A_DecalManager floor/ordinary-mesh routes and
removed per-hit print, matching the experiment copy. explosionVFX now has one
BloodDecalManager of the original class; sword lookup verified one match.
Preserved nine variable values,22 floor-grid settings and paint/floor references.
No placed Niagara components remained; no callbacks to redirect. Original BP
compiled/saved; map was left dirty, then saved with the user's edits for the
subsequent pre-impact-node restart above. Old experimental BP preserved. No Play
started for consolidation. One-action Live Coding136.38s succeeded,
reload04:57:53UTC; normal DLLs stale. Existing WireExperiment command now repairs
the original BP. Subsequent normal build above covers this helper.
See Docs/BloodExperiments.md and
Saved/Diagnostics/BloodManagerConsolidation/receipt.json.

**Blood rectangle merger — October20 installed/verified:** user explicitly requested
production integration. Existing FoliageDecalGrid component/library now use the
lab's greedy rectangle kernel; Blueprint graphs and settings retained. Hit receiver/
instance and plane separate surfaces; sloped planar floors supported. Corrected
half-extents, actual width×height debug bounds. Dirty regions only, pooled hidden
preparation, max16 allocations/pass, no idle timer/tick. Existing interval/budget/
limits retained; 32×32 maximum region, smaller MaxMergeLevel respected. Capacity
retains pending occupancy instead of evicting old stains; Process/Start after cap
increase resumes. Source/build details and compatibility notes in
[BloodExperiments](Docs/BloodExperiments.md#rectangle-integration--october20).
Private retained layout required normal restart. Preserved dirty user A_Sword and
explosionVFX with backups/hashes. Six-action minimal normal build111.80s passed;
RectangleIntegration passed10:40:53UTC, zero errors/warnings (coverage, hole,
negative cells, reuse, receivers/heights/slope, capacity, allocation cap, cleanup).
Editor29952 reopened explosionVFX normally. Actual placed original manager in brief
owned Play:16cells→one102×25.5cm projector, including existing1.02padding. Owned Play
ended; map/sword/manager saved hashes preserved. No fountain recreated. Normal DLLs
current; no production GPU/FPS claim. Evidence Saved/Diagnostics/BloodRectangleInstall.
Independent lab/tests remain in Labs/BloodDecalLab. Historical isolated CPU results:
filled43→1,hole43→4,splash52→24,strip8→1; kernel7.17us/region, streamed p95.203ms,
cold capped max.749ms. These are lab NullRHI measurements, not production timings.

**Blood callback follow-up — October20:** new NS_bloodsplat pointed its callback
to the Blueprint asset. Replaced with placed BloodExperimentManager actor; both
Niagara override stores verified. Tuning unchanged; no Play/test/restart. Map left
unsaved in the user's editing session. See Docs/BloodExperiments.md.


**Blood experiment — October20 ready:** explosionVFX now has BloodFountain,
BloodExperimentManager, BloodPaintManager, BloodFluidRendering and three receiver
blocks in the Blood Experiment folder. Reuses NS_bloodarc with sustained 86400-game-
second emission and a 45deg/s rotation component. Current shared decal Blueprint
had disconnected ordinary-mesh painting and floor routing; corrected only a new
BP_BloodExperimentManager copy. Original blood assets/wiring preserved. One-action
editor-helper Live Coding passed213.59s/reloaded03:29:00UTC; copied BP status3.
Map and new BP saved. Final actual-Niagara check: rotating/emitting, two mesh paint
states, zero unsupported hits, floor cells created. Owned PIE ended/callback retired.
No performance claim: continuous spray can accumulate many floor-grid cells.
No restart; normal DLL predates new editor helper, minimal build before cold launch.
Temporary text dumps removed (~7.25MB); compact scripts/counters/map backup retained.
Full setup/controls and limitations: [BloodExperiments](Docs/BloodExperiments.md).


**VFX reopen — October20:** requested explosionVFX for blood work. Minimal normal
build succeeded (16 actions,312.35s); base DLLs now include preceding Live Coding
changes. Editor22852 launched normally on /Game/explosionVFX. Startup dialog dismissed;
map and remote connection verified before blood setup.
No assets changed or saved. Read-only probe: Saved/Diagnostics/VerifyVFXOpen20261020.py.


**Explosion lab checkout removed — October19:** user requested detachment/removal
to recover disk space. Temporarily unpinned this UE5 chat, used managed archive,
then restored its original pinned position. The isolated explosion-lab/Prophecy
folder is gone; only main Prophecy remains in git worktree list. Removed7,036 files,
3,566,537,400 logical bytes (~3.6GB). The app's Git source-recovery record adds
102,773 compressed bytes, with no full checkout/build archive. Existing compact
explosion recovery/media bundle remains at .codex/artifacts/prophecy-explosion-2026-10-18.
Main runtime/editor left untouched. Receipt Saved/Diagnostics/ExplosionWorktreeRemoval20261019.json.
Follow-up:96 redundant explosion/bomb diagnostic files (21,581,016bytes) moved
to Windows Recycle Bin, including retired fuse-physics folders, old asset backups,
graph dumps/logs and non-performance screenshots. Performance evidence, compact
verification records, scripts and final demo videos retained. Bin was not emptied.
Exact paths: Saved/Diagnostics/ExplosionClutterCleanup20261019.json.

**Motion AE size comparison — October 19 complete:** fresh 2x512/latent128 trial
on the identical corrected 64-motion features, splits, normalization, sampling and
12,000-update protocol. Best validation checkpoint: step 12,000. Train/validation/
test MSE .001244/.014059/.012319 versus 3x1024 .000997/.030460/.029142.
Smaller model improves validation 53.84%, test 57.73%; validation/train ratio drops
30.56x to 11.30x, so a gap remains. Single-seed comparison, not independent-motion
validation. Recommended smaller portable bundle: Saved/MotionRegularizer-2x512;
prior larger bundle remains Saved/MotionRegularizer. No controller changes.
Evidence: Saved/RoboticMotionAE/20261019_mse_fullbody/architecture-comparison.json
and run_2x512. Full topic: Labs/RoboticMotionAE/README.md.

**Motion AE correction — October 19 complete:** replaced the rejected 474-clip
model with a fresh AE on 64 motions: 12 existing trimmed retargets and the exact
full-body Physical Loco (2) MSE targets (48 omni, 2 idle, 2 front/back get-ups).
Drawn/unarmed variants included. All 52 MSE PKLs are byte-identical to the stopped
47039 deployment; no added projection, foot displacement or upper-body freezing.
Verified both arms articulate in every omni. Fresh 3x1024/latent128 trained 12,000
updates; selected step 12,000, train/validation/test MSE .000997/.030460/.029142.
The train/holdout gap remains a documented limitation. Portable export, standalone
loading, input gradients and heading invariance passed. Active bundle and neutral
integration instructions: Saved/MotionRegularizer. Rejected bundle archived under
Saved/RoboticMotionAE/20261019_loco/rejected-bundle. Viewer 8875 shows 64 motions.
Evidence: Saved/RoboticMotionAE/20261019_mse_fullbody. Policy remains stopped;
no Unreal/PHAT changes. Full topic: Labs/RoboticMotionAE/README.md.

**VDB node colors — October19 installed and verified:** Temperature Color and
Scattering Color added to Spawn VDB Effect/Light Bomb Fuse, matching existing
orange/white defaults. Set once before rendering; custom bomb colors stored in a
new non-ticking component, defaults allocate none. No new recurring update/pass.
Initial5-action build failed on validation API; corrected3-action retry113.50s
passed/reloaded12:00:22UTC, no restart or retained-layout changes. A_Bomb preserved,
compiled/saved;57 existing authored pins unchanged plus2 colors. Five isolated
integration cases passed12:03:48UTC including delayed/instant/default and cached
tail colors, invalid input rejection. Owned Play ended; callback retired. User
started a new Play before12:04:46UTC; left it and new dirty A_Bomb/NS/map untouched. Normal
DLLs stale: minimal normal build before cold launch. No user map/Niagara changes.
Evidence Saved/Diagnostics/VDBColors20261019; details Docs/ZibraExplosionFade.md.

**Optimised checkbox — October19 installed and verified:** user requested
an A/B checkbox. Added visible Optimised(defaultfalse) to Spawn VDB Effect and
Light Bomb Fuse; forwarding uses optional new non-ticking bomb marker. Optional new
VDB cache component/M_ProphecyVDBOptimisedTail reuse prepared final3D textures,
freeze lighting and disable projected shadows; off retains prior rendering.
Existing native layouts unchanged; minimal Live Coding6 compile actions passed
201.05s, reload09:54:56UTC. No restart. A_Bomb preserved/reconstructed/compiled/saved,
56 existing authored pins/defaults/links unchanged and one false bOptimised pin.
Generated ReceiveBeginPlay compiler graph excluded from authored-pin comparison.
Normal DLLs stale; build minimally before any cold launch. Timing test passed.
Zibra's internal1.5 density multiplier is preserved from the source MID; correcting
that required one body-only compile action66.03s/reload10:07:26UTC, no object changes.
Five owned runtime cases passed10:09:50UTC: off expires240; explosion/ring cache at
92/62 and expire240; overlapping fade stays live/expires120; early zero skips
cache/hides and expires60. Collision remains disabled, density/colour ratio and
lifetime checked, full/half-fade images inspected. Actual profiles: off held/fading
prep4.712/7.118ms plus translucency1.378/1.169; on no prep, translucency2.331/.820.
Pass costs only, no gameplay FPS promise; on also disables projected shadows.
Instant-bomb forwarding off/on passed10:12:10UTC, no fragments/emitter and one
short-lived effect at a time. Owned Play ended, editor26816 remains explosionVFX;
node is unchecked for the user's A/B test. `op`/`bf` done, callbacks retired.
Evidence Saved/Diagnostics/VDBOptimised20261019. Do not run the full bomb suite.

**VDB prototype findings — before checkbox:** user accepts a modest hitch only at effect startup, not
periodic refresh hitches. Do not implement a low-cadence refresh as the solution.
Cached final-volume/fade prototype succeeded, retaining real3D. At half/.0833/.01
density, current-style preparation7.5–8.2ms plus translucency1.2–1.3ms became no
preparation and translucency1.0–1.4ms. Native-setter repeat plus90degree camera move
confirmed3D/fade and eliminated preparation again. Fixed self/received lighting;
projected shadows disabled in ALL comparison cases. Tail only: animated phase,
startup/handoff spike, production ownership/cleanup and both assets not validated.
No full sequence cache or production change. Existing textures~19.97MiB for one
frame; extrapolated whole-clip memory is not a measured cache size.
Owned Play ended09:34:39UTC. Temporary duplicate material
`/Game/__ProphecyVDBPerfProbe/M_CachedTail_20261019` deleted/absence verified
09:36:04UTC. Original shader restored, user assets/BP untouched; editor26816 open
explosionVFX/outside Play, profile CVars/throttle restored. `vd` is done/no callback.
Native SetDensityScale avoids the lighting invalidation caused by editor property
notifications in the diagnostic; production uses direct property writes. Full
findings/control catalogue and prototype limitations in Docs/ZibraExplosionFade.md.

**VDB deeper investigation — October19, no new production change:** user requested
all performance knobs and explanation of costly near-invisible tails. Five owned
comparison runs completed (one VDB at a time); editor26816 left explosionVFX/outside
Play, profile CVars/throttle restored. Our fade handling disables lighting reuse at
tick180 after source ends at90; unchanged shape suddenly regains downsample/lighting
passes. At density.01, repeated GPU scopes: density downsample2.521ms, lighting1.193,
colour4.465 (prep8.181), translucency1.336. These are pass costs, not30ms effect cost.
Render downscaling still evaluates all source voxels; eighth not automatically faster.
Temporary eight-colour-sample shader trial cut quarter colour4.4–4.5→.9–1.0ms,
but added fire grain; motion/other views not validated. Original engine shader restored
byte-identical and recompiled before repeat; no experimental shader installed.
No native build/restart, user-asset or BP edits/saves. Prior adapter and stale normal DLL
status unchanged. Full native control catalogue, test receipts and prioritized next
work in Docs/ZibraExplosionFade.md. First proposed exact improvement: independently
cache unscaled density grid across held-frame density fades (no DensityScale input).
Final-volume caching tested as above; production caching and optional sampled
quality/cutoff remain proposals, not installed nodes. No recurring refresh cadence.
Evidence Saved/Diagnostics/VDBPerformance20261019.

**Sword death/drop repair — October19 installed, user accepted:** inspected current `die revive`.
Its `get sword` -> GetHeldSword returns null during D/S insertion, so the guard
skips material AND DropSword; shortened equipment remains attached to the dying
agent. Direct native drop restores full scale (1.311941 Z) from both reach and
attached slide. Static mesh receiver also lacked SetPhysMaterialOverride forwarding
to Jolt; now implemented without retained layout changes/polling. Five-action
Live Coding passed553.73s, reload07:42:37UTC; native MaterialOverrideDrop test passed
07:44:51UTC for independent/welded held, dropped and None reset material values.
Unreal26816 remains open explosionVFX. Normal base DLLs are now stale: minimal
normal build before any cold launch. Blueprint saved/preserved before reload.
First editor graph migration refused without edits because the existing cast
is pure. Corrected one-action helper build passed135.42s/reloaded07:49:24UTC.
Migration applied07:50:21UTC: drop first, use returned actor for guard and material
target, preserving material literal and other wiring. BP compiled status3. User
confirmed it works and pivoted to VDB performance. Agent's final graph-save/repeat
death probe was deferred during user Play; do not claim an agent post-migration save.
Evidence/scripts: Saved/Diagnostics/SwordDrop20261019. Current map/unrelated
assets unchanged; original auto-bomb scene baseline timed out at dead tick68;
subsequent owned D/S probes removed only PIE bombs before ignition and ended.

**VDB performance — October19 installed/verified, full 3D:** node-spawned effects
(including bombs) use quarter render-volume resolution, eighth lighting resolution
and main ray step4, configured before asset assignment to avoid full-resolution
startup allocations. Lighting is reused on unchanged source frames at stable
density, refreshed through fade/endpoints/snaps; zero-density tails disable plugin
visibility while preserving actor lifetime. No entire-clip cache or plugin edit.
Fine smoke detail is softer; moving-light/occluder lighting can stay frozen during
a constant-density held frame. Source animation timing and all node controls remain.
Controlled matching GPU captures: moving47.74→33.96ms, held41.41→22.25ms,
fading40.09→28.84ms. CSV means show smaller moving improvement; these are fixed
capture GPU costs, not gameplay FPS promises. Resident scene+effect GPU memory
3514.7→2939.9MiB. Invalid early pilots discarded. See Docs/ZibraExplosionFade.md.
Only ProphecyVDBLibrary.cpp changed. Two one-action layout-safe LC builds passed
61.15s/83.47s, final reload08:33:08UTC/no object changes. No restart or content save.
Timing automation passed08:33:59UTC; four actual-asset runtime cases and rendered
fade captures passed08:35:22UTC. Editor26816 open explosionVFX/outside owned Play.
Normal DLLs stale: minimal normal build required before any cold launch.
Evidence: Saved/Diagnostics/VDBPerformance20261019 and VDBCacheBenchmark.csv.

**Static fuse / upright Niagara — October19 installed and verified:** user rejected
and explicitly requested removal of the whole bomb fuse-physics experiment.
Static original-shape fuse replaces skeletal/AnimDynamics visual; remove stiffness
node/setup component and generated skeletal assets/tools. Shared holster unaffected.
Niagara follows the shrinking tip with world identity rotation/absolute scale,
keeping gridZ up. Current A_Bomb emitter pin uses NewNiagaraSystem1; null still
means none. Existing cap/hide/force/VDB/fragments controls preserved; offset pin removed.
Flame debug-box inspection11:03UTC: User.DrawBounds still true; automatic toggle
blocked by unavailable asset API/desktop helper. Asset export unchanged, dirty
A_Bomb preserved. Manual control/evidence recorded in Docs/BombFuse.md.
Retained layout changes: assets preserved, editor17636 closed cleanly. Initial
11-action normal build compiled runtime but failed on editor helper pointer type;
corrected4-action retry passed59.17s. Base DLLs current. Editor26816 reopened
explosionVFX; A_Bomb compiled/saved,63->56 pins with only requested changes.
Original470 fuse triangles and shading verified. Old skeletal fuse/skeleton and
six physics tools deleted. Isolated StaticFuse passed05:41:54UTC:180 moving/rotating
samples, world-up emitter, progressive clipping, material inheritance and hide.
No effects test in user editor. Niagara saved bytes unchanged; agent reflection
healthy. The two retired diagnostic directories (BombFuseFlexible and
BombFuseRigidity20261019) were moved to Recycle Bin in the user's October19 cleanup.
See Docs/BombFuse.md and Saved/Diagnostics/BombStaticFuse20261019.

**Recovery/test constraints:** previous full FuseAndDetonation test spawned eight
VDBs and crashed editor12676 with D3D12 E_OUTOFMEMORY. Never run it in the user's
interactive editor. Focused tests run isolated -nullrhi; disable Fab for that
process to avoid its restored browser tab asserting with -nocef. Niagara recovery
snapshot Saved/Diagnostics/NiagaraPulse.txt and compact recovery receipt remain;
recovered NewNiagaraSystem1 is saved. Never overwrite it with that old snapshot.

**Fuse Cap installed October19:** Light Bomb Fuse adds remaining-fuse fraction
0–1, default0;0 burns fully,.5 burns halfway,1 instant (zero speed allowed).
Burn/spark speed unchanged. New optional non-ticking cap component preserves all
existing retained layouts. Minimal Live Coding3 actions passed237.58s, reload
03:54:40UTC; no restart. Current A_Bomb preserved/refreshed/compiled/saved with
54 existing authored pins intact and one new cap pin0; stale library CDO repaired.
Native21-argument API and agent reflection healthy. FuseAndDetonation passes
03:56:48UTC including0/.25/.5/1 caps and VDB/force; EOS heartbeat warnings only.
This gameplay change is now incorporated into normal DLLs by the crash/reopen
build above. See Docs/BombFuse.md and
Saved/Diagnostics/BombFuseCap20261019 for preservation/verification evidence.

**Niagara clipping checked October19:** NewNiagaraSystem1 RenderScale0.2 and
LocalPivotZ0.12 make the red debug box misleading: its center differs from the
scaled simulation center. Flame reaches the real grid top. Temporary
WorldSpaceSizeZ300->600 recovered the missing tip; all diagnostic settings
restored, no content save/build/restart. See Docs/BombFuse.md Niagara clipping
section and Saved/Diagnostics/NiagaraClip20261019.txt. No permanent tuning change.

**A_Bomb shell material:** retain source-matched static shell and runtime material
inheritance. Former startup flexible fuse setup is superseded by the static-fuse
cleanup above; do not restore startup physics. See Docs/BombFuse.md.

**Fragment transparency fade — October18 installed/verified, no restart:** Light
Bomb Fuse adds Fragment Fade Duration (default1s,0off), over the final part of
Fragment Lifetime, clamped to that lifetime. Separate new non-ticking component
leaves existing layouts unchanged. Original material stays until fade, then20 pieces
share one translucent MID/opacity write. Current Bomb/PressureBomb uniform values
and nine matching static switches are preserved; alternative shaders need translucent
FragmentOpacity support or retain original material/expiry with a warning.
Live Coding5 actions passed452.06s; reload16:07:27UTC. User explicitly stopped their
Play before reload. Refreshed current /Game/_mygame/bomb/A_Bomb pins, compiled and
reopened; saved bytes match preservation. Native combined test passed16:07:51UTC,
including half/zero opacity and cleanup. Owned rendered Play passed239 samples:
solid through120, fading121–239, destroyed240 for lifetime4/fade2. Both solid/half
screenshots inspected. Editor6904 remains explosionVFX/outside Play; user dirty map
and NewNiagaraSystem untouched. Base DLLs require minimal normal build before next
cold launch, incorporating fade, fragment toggle and impact event. See
[BombFuse](Docs/BombFuse.md); Saved/Diagnostics/BombFragmentFade, Tools/BombFuse.

**Explosion impact event — October18 installed/verified:** six-file extension,
existing world/Agent/scheduler layouts unchanged. Minimal Live Coding8 compile
actions passed285.59s; ProphecyJolt patch_0/GameAnimationSample3 patch_1 loaded,
reload complete15:44:24UTC. No restart. Bind Explosion Impact(Self,event) gives
immediate first-hit notification and shared30-unpaused-tick cooldown per actor;
explosion impacts only. Three focused isolated tests pass after4-action build46.73s,
including real PHAT limbs, K2 pins, delayed delivery, cooldown and reentrant handlers.
Main owned Play smoke created receiver on actual agent and pushed26 bodies.
Python lacks wrappers for new types after LC, so main callback timing was not
retested through Python; native isolated tests cover it. Existing BP compile and
agent reflection healthy; sampled saved package hashes unchanged, no wiring
edits/saves. Editor6904 remains on explosionVFX/outside Play; map currently dirty,
left untouched. Base DLLs need minimal normal build before next cold launch,
including this event and prior fragment toggle. See [ExplosionImpact](Docs/ExplosionImpact.md).
This supersedes all older PAUSED references below.

**Fragment toggle — October18 installed, no restart:** Light Bomb Fuse
adds Spawn Fragments (defaulttrue). False skips fragment asset loads and debris
creation/cleanup but retains VDB and physical force. Existing Fragments array
represents the option; no retained native instance-layout changes. A_Bomb current
edits backed up/saved before function-reflection reload; user dirty map and
PressureBomb left intact. Live Coding3 actions passed286.30s; patch_0 and reflection
reload complete15:22:44UTC. Handled MTAccessDetector/RigVM reload ensures and .voltbl
linker diagnostics occurred; editor responsive afterward. Combined test passes
15:23:03UTC: default20 fragments, disabled timed/instant zero fragments while VDB
and actual physical force remain. Native19-argument reflection verified; Python's
cached wrapper still shows old signature, use call_method until cold launch.
Existing A_Bomb node initially had stale pins; reloaded only its freshly preserved,
clean package and compiled successfully15:25:12UTC. Same editor PID6904, no restart,
no manual wiring edits. Map/PressureBomb retain their pre-existing dirty state.
**Base DLL predates this checkbox: minimal normal build before next cold launch.**
Evidence/scripts: Saved/Diagnostics/BombFragmentsToggle.

**Light Bomb Fuse — October18, installed and verified:** node in Prophecy/VFX
accepts the original bomb mesh component, progressively clips its curved fuse,
then triggers VDB AND physical blast and launches20 prepared shell fragments.
All previous effect/blast controls plus fuse burn speed and fragment velocity.
User explicitly deferred Niagara: no glowing tip/emitter. UV1 stores burn distance;
white vertex colors preserve the imported glTF appearance. Original assets and
A_Bomb graph remain untouched; no automatic Blueprint wiring was added.
Material follow-up installed: all20 fragments inherit the bomb component's current
slot0 material at detonation, including dynamic instances replaced after ignition.
Burning visual still uses its prepared masked material. Single compile action
(198s), layout-safe patch_1 loaded14:36:40UTC; combined test with late dynamic
material replacement passes14:37:05UTC. No restart, assets or wiring changed.
User's dirty A_Bomb/explosionVFX were saved before the required native-layout restart.
Editor5800 hit a shutdown-window error after saves and exited; no force-kill.
Minimal normal build33 actions passed (538.92s), incorporating the VDB endpoint
fix and five-file base explosion port; impact-event extension stays PAUSED.
Final editor-only mesh-baker correction loaded by layout-safe Live Coding
patch_0 (1 compile action,208.32s), reload complete/no object changes. **Base DLL
predates the baker correction and fragment material inheritance: minimal normal
build before next cold launch.**
Combined native test passes, including actual Jolt impulse, delayed wave,20 radial
fragment velocities, VDB and cleanup. Final rendered Play captures verify original
appearance, progressive disappearance and fragmentation; owned Play ended.
Editor6804 open on `/Game/explosionVFX`, no Play/dirty packages. Original mesh,
material, preserved A_Bomb and map hashes unchanged. Agent reflection healthy.
See [BombFuse](Docs/BombFuse.md); evidence Saved/Diagnostics/BombFuse.

**Spawn VDB Effect node — October18, installed and verified:**
User requested the two downloaded effects with scale/framerate and density fade
start/target/duration; explicitly chose one-shot disappearance. New native node
and short-lived controller use authored60-tick timing, hold the final frame if
needed for the fade, then destroy the actor. Current explosionVFX was backed up,
saved and closed cleanly;7-action normal build passed (173.93s). Final endpoint
correction loaded through layout-safe Live Coding patch_0 (2 actions,125.32s).
The later normal bomb build above incorporates that correction into the base DLL.
Timing automation passes; both actual effects pass166 sampled Play frames,
including exact density/frame progression, transforms, final-frame hold and
destruction at ticks120/48. Final editor5800 is open on `/Game/explosionVFX`,
outside Play, with no dirty packages; existing agent BP reflection healthy,
wiring preserved. Failed headless Fab startup and handled RigVM reload ensures
are documented with successful subsequent verification in
[ZibraExplosionFade](Docs/ZibraExplosionFade.md). The separate explosion-impact
event task remains explicitly PAUSED; do not resume until requested. Its isolated
worktree journal records remaining verification/packaging. This requested map
supersedes the uncreated explosion_test proposal and older testNN reopen default.

**Crawl stopped at user request — October17:** user cancelled the additional
hour. Stop request reached run20261017_135639_uefn_crawl_velocity_512;
checkpoint1628 was saved and checksum-verified locally (SHAb2d38e957d29).
Owned pod o6qhah385ykhhx explicitly stopped; API confirms EXITED. Active run
marked stopped, latest verified pointer updated. No further training restart
authorized. Receipts: Saved/MimicKitCrawl/user-stop-confirmed.json and
local-backup-status.json. The previously planned14:58 finish is cancelled.

**Additional crawl hour startup (now stopped) — October17:** previous35-minute run
20261017_130908_uefn_crawl_velocity_512 finished cleanly and pod stopped.
Final checkpoint1612_final is locally checksum-verified (SHAaafec06143b4),
26,427,392 samples. User requested one additional hour; continuation startup
uses that final checkpoint and identical current PHAT/motions/configuration.
New run20261017_135639_uefn_crawl_velocity_512 started at13:58:10 Warsaw,
resuming at iteration1613 with optimizer/normalizers restored. First new
checkpoint1613 is checksum-verified locally. Training stops14:58:10; saving/hard shutdown by
15:00:55. Runtime deadline is updated locally/remotely and local checkpoint
helper reloads it. Startup connection timeout and integer-duration argument
bug were corrected before the successful learner launch. Receipt:
Saved/MimicKitCrawl/updated-training-20261017/added-hour-receipt.json.
No AE retraining in this extension; previous times below are historical.

**Updated-source AE completed /35-minute policy continuation running — October17:**
current AE run20261017_123736_updated_crawl_idle_2x512 uses edited native crawl
and current idle plus unchanged two LAFAN clips. Same2x512/latent128; best1500,
validation0.0612601, stopped3500/75.1seconds; scorer/export checks pass.
No AE policy reward. User authorized latest crawl checkpoint finetuning with
new PHAT for35minutes. Latest verified local archive1311 contains21,495,808
samples and saved actor/critic optimizers/normalizers. Updated planted crawl
reference installed (SHA02bcdbbf559e); idle unchanged. Full5% upper-body margin
passes103,456 Jolt checks; current-PHAT physics/PPO preflight and final saved
checkpoint rollout pass. Dynamic hand penetration still reaches2.69cm; no
perfect-contact claim. Run20261017_130908_uefn_crawl_velocity_512 is advancing
on owned L4 o6qhah385ykhhx with exact current PHAT/reference hashes. First new
checkpoint1312 is checksum-verified locally and in cloud; optimizer/normalizers
restored. Latest live verification reached1332 with no fatal failure.
Training runs35minutes from actual start13:10:51 Warsaw, stopping13:45:51;
saving and hard shutdown by13:48:36. Local/remote guards and backup helper use
the revised deadline, excluding startup retries (missing ephemeral runtime,
then upload timeout; fixed by restoring cache and reusing identical retained CP).
User-requested checkpoint cleanup kept1311 and the new run; removed9 local,
7 retained-pod and10 cloud archives, freeing300/237/312MB respectively.
Removed stale cloud pointers; current local verified receipt points to1312.
See current crawl topic and updated-training-20261017 receipts for evidence.

**Upper-body PHAT saved in place — October17, user authorized:** nine profiles
expanded in the single PA_UEFN_Mannequin for the latest authored crawl/idle,
their pure robot projections and existing contact-corrected idle, with the
documented1.05x angular-excursion rule and coupled swing ellipse. Existing wider
bounds retained; no obsolete cleaned crawl or LAFAN used. Changed spine_03,
spine_05, both clavicles/upperarms/hands, and head. Clavicle twists changed from
LOCKED to LIMITED to admit authored motion. All six leg profiles, including
both ankles, unchanged exactly; frames/geometry/mass/drives/damping unchanged.
Only PHAT saved; five pre-existing dirty animation/BP packages preserved; no
Play/restart/training. Saved asset SHA49994f0bb1257a1e9bdb5dd2aa229455544426a1b6a17d468cc6170df5e9640d.
Independent saved-value validation passes358,456 dense upper-body samples and
89,712 exact-Jolt reference/5%-margin cases. Canonical model/provenance and local
crawl package/source.zip synced; both model XMLs byte-identical. The subsequent
updated-source policy preparation above replaces the obsolete cleaned crawl
and refreshes the training preflight. Current viewer/report/limit overlay refreshed.
Plan, save receipt, verification and original PHAT/model/viewer backup are in
Saved/MimicKitCrawl/upperbody-limits-20261017. Exact values and method in
Docs/MimicKitUEFNBodyMatching.md. Scripts fit_upperbody_limits.py,
apply_upperbody_limits_unreal.py; use --verify-saved for read-only checks.

**Current-source shoulder-limit overlay — October17:** updated-source viewer now
has a checked-by-default "Show shoulder limits" checkbox. Green arms show both
nearest admissible shoulder rotations, for authored and robot views at all55
frames. Other local joints stay fixed; hands follow, with no planted-contact
solve or dynamic simulation. `add_source_limit_overlay.py` uses constrained
multistart quaternion-distance optimization; all220 resulting shoulder samples
accepted by exact project Jolt. overlay-verification.json records corrections.
Full-geometry handedness correction retained. Source/PHAT/training unchanged.

**Updated authored crawl and viewer handedness — October17:** freshly imported
recoveries/crawl.fbx saved12:07:07 Warsaw, SHA2e849ce9c90057c8a333ce506ded079b8987ccf00e5b46660ec267fd50fcbb84
(55 frames,30Hz). No contact IK, loop closure or LAFAN processing. Fresh read-only
Unreal PHAT export10:10:15UTC matches canonical source-rig exactly. Both shoulders
still exceed twist only; coupled swing fits. Peak twist R/L: authored skeleton
60.7453/60.5029deg; pure robot projection50.0714/46.0837deg; current limits
38.75/33.46deg. 1,732 project-Jolt samples agree with numerical classification.
`Labs/CrawlTraining/inspect_updated_source.py` keeps authored clavicle-relative
and rigid-torso robot measurements separate. Report/data and verified animated
viewer: http://127.0.0.1:8843/Saved/MimicKitCrawl/updated-source-2e849ce9c900/ .
Viewer defaults to authored frame38 (right peak); left peak is frame10. Source
and robot selector, playback and peak controls verified; comparison.png saved.
Complete posed geometry is reflected on world Y to match corrected replayer
handedness, without renaming limbs or modifying stored motions. Same display
correction applied to upperarm-pose-audit and constrained-ik HTML; their old
screenshots predate the correction. Existing policy/AE clips, PHAT, datasets
and training unchanged. Earlier candidate/audits below refer to the older FBX.

**Planted-hand arm IK candidate — October17:** user requested fixing excessive
upper-arm rotation while keeping hands planted and seeing the difference.
Review-only candidate in Saved/MimicKitCrawl/constrained-ik/crawl.pkl; existing
policy clip, AE, PHAT and training unchanged. Opened animated comparison at
http://127.0.0.1:8843/Saved/MimicKitCrawl/constrained-ik/ (before/IK, overlay,
source comparison, synchronized orbit, scrub/play, old worst frame280).
`constrained_contact.py` preserves both hand transforms exactly at240Hz keys,
pelvis/legs/travel, and loop closure; solves torso/shoulder/elbow IK with both
shoulders/elbows/wrists constrained to current PHAT,0.25deg interior margin.
Continuity weight20 removes a rejected first-candidate elbow jump. Verification
at1920Hz:20,742 arm poses accepted by project Jolt, zero arm violations;
right/left max twist88.55/64.59 ->38.50/33.21deg. Hand target interpolation
deviation<=0.091mm, planted floor error<=0.749mm, penetration<=0.176mm;
loop seam<0.0001mm, max adjacent world rotation4.924deg (authored hand motion).
Torso/head/left-ankle conflicts remain; head rejection samples increase from346
to675/3457 as absolute head orientation is preserved through changed torso.
Not a whole-body limit-valid training reference. Full-limit torso/head probe
did not converge with pelvis/legs and hand transforms fixed; not a proof of
infeasibility. `verify_constrained_contact.py`, verification.json and screenshot
record results. Candidate SHA a76798221b7d204a0a215f70c23ad77f0bc46871fccaac4656f31eeb3dd7fa1c.

**Worst upper-arm pose viewer — October17:** read-only comparison opened at
http://127.0.0.1:8843/Saved/MimicKitCrawl/upperarm-pose-audit/ . Magenta cleaned
target versus cyan nearest admissible selected shoulder rotation, synchronized
cameras, overlay, close-up and right/left selector. Worst means largest minimum
quaternion angular correction over433 cleaned crawl keys. Right frame280
(1.1667s):38.2449deg correction, elbow10.75cm/hand21.00cm displacement. Left
frame80(.3333s):26.0757deg, elbow6.68cm/hand16.31cm. Only selected shoulder
rotation changes; remaining local joints are fixed, not a fully limit-valid or
floor-corrected pose. Constrained multistart nearest-rotation optimization,
both resulting poses accepted by exact project Jolt. Script
Labs/CrawlTraining/upperarm_pose_audit.py; data.json and comparison.png under
Saved/MimicKitCrawl/upperarm-pose-audit. Browser rendering, close-up and selection
verified. No animation/PHAT/training changes.

**Crawl package corrected to the single current PHAT — October17:** removed
the historical-profile override from `prepare.py`. `current_phat.py` checks
current export/source asset hashes and copies the canonical model, limits and
physics metadata exactly. Local package and source.zip corrected/verified;
unchanged policy motion hashes, no asset save, cloud change or training restart.
Bundle/start now reject stale PHAT validation; start additionally verifies the
remote three asset hashes against the current local PHAT. Preflight no longer
expects two locked ankle rows. Four-world/three-tick physics check passes with
exact current runtime modes/angles and zero locked ball rows; this is not a
dynamic-contact or feasible-reference approval. Receipt current-phat-sync.json
and current-phat-analysis/package-verification.json under Saved/MimicKitCrawl.
Prior audit statement that package still has old limits is now superseded.
Shoulder trace uses only actual UEFN crawl/idle, not LAFAN: contact IK changed
upper-arm local orientations up to41.29/43.00degrees R/L. Crawl PHAT twist maxima
rose from55.93/46.09degrees in the reduced robot before cleanup to88.55/64.59
after; source full-skeleton shoulder connector maxima are65.38/60.33degrees.
These are PHAT connector-frame angles, not arm direction or authoring Euler
channels. Source, reduction and cleanup are separate measurements; do not blame
the authored motion alone for cleaned-target conflicts. Stage evidence:
current-phat-analysis/shoulder-stages.json. No animation changes this turn.

**Current PHAT crawl analysis — October17, read-only:** user clarified that
"restart" meant restart the analysis, not training. There is one authoritative
user PHAT; do not substitute historical pre-running profiles. Fresh Unreal
export at09:12:05UTC matches current `Saved/MimicKitUEFN/source-rig.json` in full.
Both ankle twists are LIMITED, not locked. The crawl package still contains
historical limits except its corrected wrists; its prior audit is not a current
PHAT audit. Against the current PHAT, cleaned crawl/idle torso exceeds limits
throughout; crawl shoulders/wrists and some head poses conflict; idle left wrist
conflicts throughout. Hips, knees, elbows and right ankle fit both clips; left
ankle swing conflicts in80.14% crawl and100% idle samples. Exact project Jolt and
numeric classification agree on11,340 samples at240Hz. Evidence and complete
per-joint percentages: `Saved/MimicKitCrawl/current-phat-analysis/report.json`.
No PHAT edits/saves, training mutations or restart performed. Current asset,
dirty packages and Play state preserved. Details in Labs/CrawlTraining/README.md.

**Crawl contact cleanup and one-hour resume — October17, authorized:** user
requested cleaning crawl hands then resuming for1h. `crawl_contact.py` restores
authored hand XY/orientation (with existing seam correction), raises intersecting
hand boxes to ground and retains positive authored box clearance. Fits torso/arms
at240Hz (433frames, same1.8s duration), preserving pelvis/legs/travel. Dense
interpolation check: planted hand gaps <=0.754/0.221mm, deepest reference
intersection0.142mm, loop seam<0.2micrometers. Idle unchanged; AE/originals unchanged.
New policy crawl hash `eca10a3b85d3d6dba9c11850c6cef5c4abc8b1788850aa55ea048891b1ac2190`.
Latest checkpoint701 verified (SHA168efb206c68ccb9dd683c2f709a9fd5b6be1e90fe8ccf0bacc482b51cda445e).
16-world local saved-policy checks:301 deterministic+160 noisy ticks, finite
and solver checks passed, optimizer/normalizers/11,501,568 samples restored.
Residual physical hand penetration up to4cm disclosed; reference cleanup does
not certify perfect dynamic contact. Original solver and current wrist limits
unchanged; joint-limit conflicts remain audited, no silent limit expansion.
Replay selector fixed to1idle/11crawl, auto-phase capture attached and verified.
Evidence contact-cleanup-validation.json, resume-validation.json, and local
replayer entry mimickit_crawl_cleaned_contacts_preview. Prior run assets/receipts
archived in stopped-run-20261017_065646. New3600s allocation pod
`o6qhah385ykhhx`, hard stop09:13:50 Warsaw (Unix1792221230.1971967), $0.59/h.
Run `20261017_081535_uefn_crawl_velocity_512` launched with resume701, trainer393,
exit guard394 and local deadline guard11832. Source71c0a2a02cc1a67d59cebf95395f7ba77cae8920c3bf505f2e1730b6dfb1477f
verified. Resume702 confirmed (optimizer/normalizer restored), training advancing;
first live replay702 verifies1idle/11crawl and phase metadata. No solver errors.
IMPORTANT: shared cloud store returned QuotaExceeded on checkpoint702 upload.
No deletion/volume-size change. Checkpoint702 independently checksum-verified
LOCAL backup at Saved/MimicKitCrawl/local-checkpoints/20261017_081535_uefn_crawl_velocity_512,
SHA b1e95b9ba4b5d2ea67cc0c20aa0a2f37269de4feecfde7ef5dfa8d0532a3c024.
Hidden local backup helper18260 (child28876) polls latest immutable checkpoint;
latest pointer local-backup-status.json. Use that local checkpoint for future
resume, NOT the previous run's S3 pointer. Source local_backup.py; exit watcher
replaced394 with572 to wait up to120s for local checksum acknowledgement before
stopping, bounded by original09:13:50 hard stop; remote deadline guard198 and
local11832 unchanged. Cloud backup error remains visible, not falsely cleared.
Training will hit its existing uploader error at shutdown; local copy and retained
pod volume preserve the completed checkpoint. No new training failure inferred
from that known backup exception. Other loco untouched.

**Crawl STOPPED at user request — October17, hovering crawl hands:** pod
`g525r7hbc356yo` confirmed EXITED at Unix1792216522. User correctly flagged
that only crawl_idle received hand-contact fitting; crawl received ONLY an
eight-frame loop-seam correction. Crawl stance contacts were not cleaned or
validated before training. Do not describe both references as contact-corrected.
Receipt `Saved/MimicKitCrawl/hovering-hands-user-stop.json`; active_run marked
stopped_by_user_hovering_hands. Local crawl observers/deadline guard retired;
other locomotion run untouched. No automatic resume. Existing assets/checkpoints
preserved. Separate replay-selection bug also remains: first-agent fill yields
11idle/1crawl previews despite actual20idle/492crawl training allocation.

**Crawl TensorBoard auto-phase display fixed — October17:** phase head/MSE were
already trained and logged. Local dashboard omitted `uefn_crawl_idle_mse` from
its tracking-loss/auto-phase mapping. Added that objective and backfilled all
three crawl histories from raw events; exact step/value equality verified.
Charts `auto_phase/mse`, `auto_phase/weighted_loss` and `loss/auto_phase` now
publish, along with body-loss components. Restarted ONLY current crawl dashboard
(PID17188), no trainer/optimizer/run changes. Receipt
`Saved/MimicKitCrawl/autophase-dashboard-fix.json`.

**Crawl continuation authorized — October17:** user requested resuming latest
for two hours after wrist correction. Latest verified checkpoint is iteration100
from `20261017_061639_uefn_crawl_velocity_512`, SHA256
`fb4890b3dac1217ad146e6bbfaa9e7c4d894f7e57b61f8d1bd054898f12d1457`.
Local16-world saved-policy test restored optimizer/normalizers and1,654,784
samples, without weight updates.160ticks each noiseless/noisy across both clips
passed finite/solver checks. Residual hand depth reaches26.74/30.74mm respectively;
0.51%/0.88% hand samples exceed20mm. Disclosed to user while proceeding with
requested continuation; do NOT label ground penetration fully resolved.
`resume-validation.json` preserves measurements; `resume-contact-acceptance.json`
records explicit continuation scope. Experimental ground recovery remains OUT.
Separate Secure L4 pod `g525r7hbc356yo` allocated at$0.59/hour, hard stop
08:53:55 Warsaw (Unix1792220035.647861). Continuation
`20261017_065646_uefn_crawl_velocity_512` launched with `--resume`, trainer412
and exit guard413; local deadline guard13676. Source bundle SHA256
`ba33e3ab14a075fbe43d4fdaf4dc81bd9c8b4e6c005d5433607e1e1a2f40ce04`
verified in storage and on the trainer. Resume and first completed update verified:
checkpoint101 independently read back/hash checked from storage (SHA256
`2b9ebac76b99b46cbb4358ecf81c22e81b3647f59c736b0b0c9d6707d4fc2c4b`).
Already advanced through five resumed updates; both wrists confirmed60/45/90
on trainer, no failure/solver-warning files. See resume-start-verification.json. Prior allocation
confirmed EXITED and launch records archived in stopped-run-20261017_061639.
No loco changes. Read active receipts for launch/verification state.

**Crawl wrist correction — October17, supersedes the diagnosis below:** user
flagged their newer PHAT wrist edits. Crawl preparation incorrectly restored
both wrists to30/20/50deg along with pre-running profiles, overriding the saved
user60/45/90deg (twist/swing2/swing1). Live Unreal PHAT was never changed.
`prepare.py` now preserves latest saved wrist profiles from source-rig.json;
local package corrected with only two wrist profiles changed, XML byte-identical.
Prior limits/audit preserved in hand-penetration/before-wrist-correction.
Controlled idle test with ORIGINAL solver and angular projection ON now reaches
only1.07mm/15.77mm hand penetration, versus50.70mm/59.08mm with old wrists.
This is within the existing20mm contact slop in this bounded test; do NOT
install experimental ground recovery based on the obsolete wrist experiment.
The all-motion/random-action dynamic check is still outstanding, deployment
remains blocked, and the paid crawl run stays stopped. Reference limit audit
refreshed: crawl wrist violations20/23 of55frames; idle0/48 of48frames.
Evidence: hand-penetration/corrected-wrists-ablation.json. No loco changes.

**Crawl stopped again — October17, confirmed hand penetration:** user observed
hands below floor. Measured exact physical hand boxes in the local preview
(4.6/5.8cm depth) and restarted run iteration100 (~5.0/5.6cm). This is dynamic
penetration, not target overlay; prior startup-contact/numerical checks missed it.
Pod `i2nng9pcr65ldu` confirmed EXITED at Unix1792211809; receipt
`Saved/MimicKitCrawl/penetration-stop-receipt.json`. No automatic restart.
Controlled local zero-command ablation confirms causality: angular position
projection ON -> hand depths5.07/5.91cm, OFF ->0.025/0.040cm. One projection
pushes hands down3.58/4.35cm after contacts. Earlier transfer notes explicitly
omitted floor position recovery because recorded loco stayed within2cm slop.
Experimental local GPU ground-position recovery tested: policy-tick hand
depths2.13/2.11cm with the existing Jolt2cm slop; first-substep worst2.64/2.95cm.
Generalized velocities unchanged. Prototype is NOT installed/deployed or ready
for training: coupled joint/contact residuals, random actions, all-body coverage
and captured throughput still need validation. See hand-penetration/diagnosis.json. `launch.py` now blocks paid deployment until dynamic penetration
validation passes. Evidence under `Saved/MimicKitCrawl/hand-penetration`.
No loco changes.

**Crawl restart — October17, approved after corrected replay review:** fresh
run `20261017_061639_uefn_crawl_velocity_512` launched on Secure L4 pod
`i2nng9pcr65ldu` ($0.59/hour), 512 worlds, only `crawl`/`crawl_idle`,
20 idle and492 crawl rows, no AE reward/injuries/adaptive sampling. Both clips
loop; original limits and27cm-only failure plus10s timeout preserved. Two-hour
allocation deadline08:14:56 Warsaw (Unix1792217696); local/remote stop guards
and trainer-exit watcher active. First PPO update complete; checkpoint0000000 backup independently verified
from object storage (SHA256 cb69204a0f6a44a61fc7a66737d2792dfb1de92df044f52648019d61d896ee8c).
Trainer, remote deadline guard and exit watcher confirmed alive; no reported
solver/failure/backup errors.
Current receipts `Saved/MimicKitCrawl/{active_run,pod,runtime_control}.json`.
Prior stopped run preserved under `stopped-run-20261017_054944`; loco unchanged.

**Crawl correction — October17, after user stopped the run:** policy dataset
must contain ONLY UEFN `crawl` and `crawl_idle`; LAFAN is only for the offline AE
used later for perturbations. Initial policy package incorrectly included LAFAN.
Screenshot idle terminated at clip end (flag2), 20 ticks from a58% start; max
collider error8.38cm, so the27cm failure was not responsible. Reduced rigid
torso/clavicles raised hands~6cm and left hand boxes~4cm above ground. Local
policy-only corrected idle fits hand contact with unchanged pelvis/legs and
hand orientation. Both policy clips now WRAP; crawl tail gets an8-frame small
seam correction (<=4.124deg and0.48mm Z, root XY unchanged). Original datasets
and four-clip AE are unchanged. Prior package archived under
`Saved/MimicKitCrawl/stopped-run-20261017_054944`; new package has2clips.
Corrected16-world CUDA/PPO/replay validation PASSED; runtime initial hand floor
gap<0.0041mm. Real done-path checks confirm no clip-end reset, failure at27.1cm,
and10-second timeout. Preview `mimickit_crawl_contact_fix_preview` in policy
replayer8021. Original limit conflicts remain audited. User approved the corrected
preview and requested a fresh two-hour run. Deployment in progress on separate
Secure L4 pod `i2nng9pcr65ldu`, hard stop Unix1792217696 (08:14:56 Warsaw).
Inspect current `Saved/MimicKitCrawl` receipts for launch/verification status.

**Crawl policy STOPPED at user request — October17:** user authorized a
separate crawl/idle run using the current loco MSE pipeline, original pre-running
angular limits, no angle or drawn/sheathed inputs, and 4% idle / 96% crawl.
Clarifications: NO limb disabling yet (four enabled placeholders for arms/legs),
NO AE reward (reserved for later perturbations), NO adaptive motion sampling,
and ONLY the existing 27cm collider-target deviation failure. Ordinary clip-end
and timeout resets remain. `crawl_idle.fbx` (48frames/30Hz) appended to both
saved crawl datasets; existing cut hashes unchanged. Four-clip AE complete at
`Saved/RoboticCrawlAE/runs/20261017_053724_crawl_idle_2x512`, best update1000,
validation0.063653. No existing AE checkpoints overwritten.

Isolated source `Labs/CrawlTraining`, package/state `Saved/MimicKitCrawl`; copied
the deployed loco source53e01c707017 without modifying it or the live PHAT.
153 policy inputs /34 motors, same actor/critic1024/1024/512, fresh learning state;
fixed20/512 idle rows and492 crawl rows. Original angular profiles restored only
inside this package from before-omni-limits/live-rig.json. Source motions exceed
some original bounds; retain audit, no clamp or silent expansion. Isolated runtime
adds bilateral locked ankle twist support and permits >4 same-shape contact points
using existing all-point manifold equations.129 locked-twist cases and1/2/4/5/8/16
point grouping checks pass.16-world actual CUDA/PPO/replay preflight passed42.3s.
Run `20261017_054944_uefn_crawl_velocity_512` launched and completed its first PPO
update with a hash-verified checkpoint backup. User then requested immediate stop
because of an issue. Owned pod `pfsx6089r481q1` is confirmed EXITED; receipt
`Saved/MimicKitCrawl/user-stop-receipt.json` (Unix1792209348). Do not restart
until the issue is identified and user authorizes continuation. Existing loco run untouched.
[Contract, checks and launch workflow](Labs/CrawlTraining/README.md).

**Smaller crawl AE1 — October17:** user requested **2 x 512 hidden neurons per
side, latent 128 unchanged**, after discussing overfitting. New local run
`Saved/RoboticCrawlAE/runs/20261017_045107_crawl_ae1_2x512` is COMPLETE;
`Saved/RoboticCrawlAE/current-run.json` now points here. It reuses the exact
prepared baseline data/normalization/splits, with 1,076,757 parameters versus
5,304,853. Early stopped at 3,750 updates (43 seconds), selected update 1,750:
validation MSE 0.062789 versus 0.099568 baseline (36.9% lower). Test MSE improved
on all three clips; jitter/body-jump checks passed, but timing-shuffle sensitivity
remains 2/5 for clip 2. Export parity/input gradients/hash verified. See
`completed.json`, `score-validation.json`, `baseline-comparison.json`. Same test
blocks were reused; this is not independent generalization evidence. Old run and source snapshot
preserved; no policy, locomotion, viewer or original dataset change.
[Contract and artifacts](Labs/RoboticCrawlAE/README.md).

**Initial crawl-only robotic AE1 baseline — October17:** user clarified a separate crawling agent,
with ONLY the three curated crawls and no locomotion/idle additions. Authorized
local AE training, now COMPLETE separately in
`Saved/RoboticCrawlAE/runs/20261017_044043_crawl_only_ae1`; `completed.json`
records 12,000 updates in 382 seconds, best checkpoint at update 1,000 (balanced
validation MSE 0.099568). Exported `scorer.pt` passed parity and input-gradient
checks. Root-jitter costs increased in all test windows; body-jump costs in
94.7–100%; heading/XY score drift <=9.27e-5. Timing-shuffle check increased cost
in only 2/5 windows of the second short clip. Overfitting and tiny within-source
holdouts remain limitations: first integration candidate, not a validated policy
reward. Full diagnostics in its `score-validation.json`. The current-run pointer
now selects the smaller run above. Initial source snapshot is under this run's
`source/`: fresh AE1 architecture1024x3 each side/latent128,405 inputs,
three actual15-body poses at30Hz in the fixed initial flat-pelvis frame; preserves
height/pitch/roll/displacement, removes global yaw/XY. Full12000-update local
recipe with equal clip sampling, separated temporal holdouts and best validation
checkpoint. Original two robot exports reused; third UEFN crawl converted only
inside the AE run. No viewer, original dataset, PHAT, locomotion policy/job or
cloud change. No crawling policy launch yet. [Contract and artifacts](Labs/RoboticCrawlAE/README.md).

**Lafan Cutter / crawls — October17:** native curator at `Labs/LafanCutter`,
desktop shortcut **Lafan Cutter**, user data in `Documents/Lafan Cutter`.
The user's saved `crawls` collection now has three clips: original two Re-solved
cuts (6084 and132 frames, unchanged hashes) plus full recovery `crawl.fbx`
(55 frames at30Hz). Original FBX archived, new BVH/revision and provenance saved;
source rig and timing retained, no robotic retarget or training. SDK/BVH round-trip
position error<.000037cm, orientation<9e-12rad. Read-only all-clips gallery at
`http://127.0.0.1:8874/`; source `Labs/LafanCutter/gallery.py`, generated buffers/logs
`Saved/LafanCrawlViewer`. Existing live Cutter draft/session was preserved; reopen
the updated dataset there before saving it again.

**October17 requested LAFAN retarget:** separate `crawls_uefn` collection now has
the two LAFAN cuts mapped to UEFN and projected through the current locomotion
15-body/34-DOF pipeline (wrists included); third FBX-derived cut byte-identical.
Original `crawls` unchanged. Gallery8874 now displays the retargeted collection
with a blue source-overlay toggle. `Saved/LafanCrawlRetarget` has robot PKLs,
BVHs, before/after NPZs and reports. Same existing locomotion export reproduced
with zero channel difference; FK round-trip<1e-6m/rad, all4536 foot lifts succeed.
Review candidates: hand displacement from reduction reaches26.82/19.43cm and
some poses exceed current locomotion limits. No contact fit, limit expansion,
training change or Unreal edit. [Workflow, mapping and limitations](Labs/LafanCutter/README.md).


**Explicit elbow posture / wrist twist — October16 current:** user reproduced a
full circle by setting Elbow down blend to0, then accepted the corrected lab and
explicitly requested its Unreal port. The earlier version7 case-specific fix was
insufficient: it inferred the bend from an admissible straight forearm (undefined
pole), ignored the blend in grab planning, then froze the inward result on grip.
Exact current-fixture replay reproduces224/363deg left/right total swivel and the
left inward pose. The replacement keeps three responsibilities separate: cached
forearm reach extent for body assistance; explicit outward/down elbow pole at the
actual wrist goal; axial wrist twist within PHAT. Blend updates approach AND held
posture. It never derives a bend from a straight forearm or changes it because
the hand happens to acquire grip. Transport and existing8deg swivel/4deg twist
caps remain. PHAT, contacts, fingers, speed settings and8/6deg gates unchanged.

Wrist twist solves feasible scalar intervals using polynomial boundary roots
(degree<=4), choosing the closest previous twist; already-feasible twists use a
fast path. No repeated elbow candidate search or stall/recovery strategy. The old
straight extent planner remains ONLY for body demand; using the bent posture for
that demand produced positive-feedback lean and was rejected. Cache version8;
Refresh migrates old poses/grips without resetting them. A formerly inward held
elbow can need a bounded near-half-turn to recover its outward posture.

Lab evidence `Saved/Diagnostics/ReachElbowDesign20261016/`: five blend values0..1,
live changes during approach/holding, current held resume,20/50cm dragging and
three prior recordings. Current blend0 grabs58/62, swivel44.49/69.97deg; final
left/right elbow outward, wrist error<.001deg and distance<.001cm. Increasing blend
lowers both elbows monotonically. Exact old circling recording now grabs142/145,
swivel8.01/25.89deg. Bone/PHAT errors at floating-point precision; max swivel8deg.
`Labs/ReachLab/test_elbow.cjs` and `test_wrist_twist.cjs` (720 known-feasible twist
cases including reversed frames, limited/free/locked axes) are current checks.
Do not overclaim all historical snapshots: frozen Stalled_250 retains its existing
left attachment but its requested left rotation remains27.28deg away; extreme
50cm sweeps still exceed reach and retain body-assistance residue. TestNN recorded
now acquires119/89 with final0/.64deg. These are separate from the accepted current
fixture. No user Refresh, reset, settings overwrite or lab service restart.

**Unreal port/build state — user-requested grab behavior restoration:** user rejected
the previous hold change because the balls stopped moving freely and appeared
fixed to the hands; explicitly requested "restore whatever was happening before".
Restore the exact pre-feedback behavior: GrabTarget reads the object's moving
surface/orientation on every tick, including after acquisition; coupled palm
anchor follows that surface; fixed joint captures the actual physical wrist.
The accepted explicit elbow/wrist solver remains unchanged. PHAT, gates, fingers,
body assistance, speeds, Blueprint wiring and ball settings remain unchanged.

Native implementation matches `ReachGripFeedback20261016/ProphecyReachLibrary-before.cpp`
exactly except one unused HoldTarget member retained to preserve loaded private
layout and permit Live Coding without an editor restart. Do not remove it through
Live Coding. Ordinary lab grips again capture the achieved wrist; the alternative
requested-frame attachment is retained only inside the historical feedback test.
No user lab Refresh, reset, persisted-state overwrite or service restart.

Live Coding rollback loaded successfully:269.17s,one C++ compile,patch0,
no object changes. Owned physical TestNN check through220 acquired grips
left120/right89 and retained both. Full commanded-pose trajectory matches
the pre-feedback recording exactly (0cm maximum difference); held targets
move11.88/51.88cm, confirming ball-following motion is restored.
Editor11912 remains TestNN/outside Play,
dirty[], full graph byte-identical and map/BP/PHAT hashes unchanged. No saves.
**Normal DLLs are stale: incremental normal build before the next cold launch.**

This intentionally restores the earlier feedback behavior too; physical elbow
circling is NOT considered fixed by the rejected hold change. Do not reintroduce
the agent-relative held target without a new user request. The previous lab
snapshots `UE_Grip_Feedback_Before`/`UE_Grip_Feedback` and physical receipts remain
historical comparison evidence: holding the authored command removed drift but
changed the requested behavior. Earlier native-final through720 and blend480
results describe that rejected version, not the current one. Evidence for the
rollback: `Saved/Diagnostics/ReachGripRestore20261016/`.

**Historical approach/held-elbow port to Unreal — October16 (superseded above):** explicitly requested by
the user. Native now follows the cached forearm plan immediately, transports it
for target changes, and carries the achieved elbow bend plane after grip. The
per-tick local candidate search is removed; at most two wrist projections/hand
plus one reverse projection when a target changes. Existing retained cache layout
is unchanged; only transient solve inputs gained hint/held fields. Live Coding
compiled one C++ unit in146.06s and loaded patch3 with no object changes. Editor
16368 stayed open. Normal DLLs remain stale: incremental build before cold launch.
600 approach/held/tracking/free/locked numerical cases pass, max arm position
error7.1e-14cm and wrist quaternion error3.4e-16. The initial planner's equivalent
axial-roll ties can differ (up to11.25deg); endpoint error<4e-6cm, reported separately.
Unmodified TestNN acquired physical grips left112/right87, both held through360.
Physical right-ball20cm vertical sweep through720 retained both joints, max
held-plane swivel8.7e-12deg, wrist limit error4.5e-16; lengths preserved.
Editor remains TestNN/outside Play/no dirty packages; Blueprint graph and all
three user asset hashes unchanged. Evidence `Saved/Diagnostics/ReachHeldPort20261016/`.
**Historical pre-lab-fix edge case:** the older separate kinematic auto-contact fixture
at sync=.82 still misses the right grip (1.949cm short). Exact terminal lab
one-step replay reproduces it within5.2e-14cm; do not call all target configurations
fixed. Early kinematic switching in the unmodified scene also failed admission.
Those receipts are retained; gates/tuning were not loosened. Current physical
TestNN is verified. The lab's old captured left-elbow0.0259cm metric is not a
new physical-scene measurement: new physical ball feedback gives max1.219cm
left-elbow movement at200-300. Plane continuity is verified separately.

**Held-ball elbow continuity - October16:** user reported the elbow jiggling while
moving the right ball up/down after grip. This was shared lab logic, not a live
Unreal connection; recorded TestNN inputs were already frozen past360. Captured
exact live setup at8960. A fast50cm vertical sweep reproduced a120.06-degree
one-tick elbow-plane flip near extension: projecting the old elbow against the
new axis reversed its bend direction. The solver now transports the established
plane with the changing reach axis, and held arms no longer swivel toward their
old approach hint. Elbow flexion, wrist twist/PHAT and palm coupling stay active.
No new state, delay, search or setting; still at most two wrist projections/hand.
Plane reversals8 to0; max swivel120.06deg to1.2e-11deg. Moderate20cm sweep retains
both grips with0 hand-angle error. Extreme fast sweeps still have extension
acceleration and rotation residuals: do not claim all unreachable motion is fixed.
Recorded grab timing unchanged left111/right86; max left-elbow step200-300 now
0.02590cm. Numeric regressions pass (`test_held.cjs`, owned stdin `test_kernel.py`,
no browser/live-service load). Evidence `Saved/Diagnostics/ReachHeld20261016/`.
User Refresh preserves current pose/grips and loads the JS. The lab correction
used no automatic refresh/reset or service restart. Native port is covered above.

**REACH planned approach and live-save stall fix - October16:** the user rejected
stall-then-change-route recovery. The lab now selects its existing admissible
forearm plan once at grab start and follows it immediately. Moving targets
transport/project that same route instead of rerunning the search. No stall timer
or fallback strategy; at most two wrist projections/hand/frame (previously18
candidate evaluations). Same speed caps, PHAT, contacts, fingers and8/6-degree gates.
Plan version5 persists target/rotation; legacy snapshots preserve body assistance.
TestNN recorded: right grips86 (previous delayed recovery150), left111, maximum
left-elbow step absolute200-300=0.05493cm. Both hold. Stalled250 grips296; frozen
initial31 grips left112/right85. One initial plan per hand in all three cases;
resume deterministic. Root-only difference0, common-translation error7.15e-14cm.
Paired isolated JS arithmetic mean0.19455 to0.04153ms/hand (~4.7x cheaper), not FPS.
837-frame ordinary grab/retarget/release regression passes. Current test:
`Labs/ReachLab/test_plan.cjs`; evidence `Saved/Diagnostics/ReachPlan20261016/`.
Earlier escape tests and exact-left-trajectory claims are historical/superseded.

**Live-save lag fixed:** entire330-frame recording was serialized twice in every
live packet plus again for session saving every1.2s. Measured formatting costs
were~1176ms live +447ms session. API3 retains motion once in
`Labs/ReachLab/motions/<sha256>.json`; recurring saves use
`motionRef:{id,startTick}`. Live file5.2MB to65KB, session2.5MB to19KB; cached
session saves5-9ms. `/session` expands motion for exact resume; fetch
`/motions/<id>.json` for a live reference. `desktop-view`/`current_view.json`
now have compact references: absent inline motion does NOT mean no recorded case.
Explicit snapshots/exports remain self-contained. Old desktop clients work; new
workspace uploads each recording once, removes redundant live redraws, and draws
recorded catch-up once per batch. Storage roundtrip/backward-compatibility tests
pass in `test_live_storage.py`. Only REACH background service restarted
(7688 to18084); visible window kept open, last readback paused at8201. User
Refresh loads final JS; no automatic Refresh. This storage fix is lab-only.

**Contact markers use occlusion:** gold point/normal arrow and cyan palm reference
now share scene depth, including snapshots. User Refresh loads renderer changes.

**No independent root-point bug:** moving/rotating only the floor root with body
and targets fixed does not affect the other bones. Actual body movement relative
to a stationary world ball changes reach geometry. Do not remove that relationship
or claim the root itself prevents grabbing. Native-captured scenarios remain
historical baselines in `Saved/Diagnostics/ReachScenario20261016/`; the accepted
native approach port now acquires both physical grips. Normal Unreal DLLs
remain stale for the Live Coding changes: normal incremental
build BEFORE any cold editor launch. Last editor receipt was TestNN outside Play,
no dirty packages. See `Docs/ReachGrasp20261012.md` for current and historical work.

**Left elbow hitch — October16 historical intermediate fix:** in the unmodified current
TestNN tick30 fixture, commanded left elbow made~0.9cm single-tick jumps at193,
218,256,275,307; the physical elbow followed. Wrist and shoulder stayed smooth.
Cause: fixed coarse half-step search near wrist alignment. Both lab `coupled.js`
and native `ProphecyReachArm.h` now scale elbow/roll search steps with remaining
quaternion error, retaining full steps above8deg and the same18-evaluation cap.
No new search/state or tolerance changes. Reconstructed one-step replay matches
the hitch within0.0004cm; full owned360-tick same-fixture capture verifies max
left-elbow step across absolute200–300: command0.90093→0.05366cm, physical
0.90080→0.05329cm, commanded angle2.252→0.131deg. Left physical grip acquires at111
(previous112) and holds through360. Right hand was ungripped before AND after;
do not repeat the earlier erroneous assumption that both current-fixture grips
were held. That fixture limitation is separate from this left-elbow repair.
34 active wrist samples pass PHAT (<9e-16); isolated837-frame lab regression passes
surface/manual grips, retargeting, release and inactive retirement. Recorded prior
performance summaries remain historical; rerun outputs copied into this evidence.
One-action Live Coding compile succeeded119.36s, reload with no object changes.
**Normal DLLs are now stale for this runtime fix: normal incremental build before
any cold launch.** No editor closure, user lab refresh, Blueprint/PHAT/tuning edits
or asset saves. Final editor remains TestNN/outside Play/no dirty packages.
Evidence: `Saved/Diagnostics/ReachElbowHitch20261016/verification.json` and
`lab-verification.json`. User's existing lab window picks up JS on their Refresh.

**Reach/grab Unreal port — October16 complete:** user explicitly authorized the
lab port and reopening after the editor stopped. Native reach/grab now includes
arm-first body compensation, bounded coupled elbow/forearm correction, upper-arm
automatic contact selection, lower-elbow preference and Set/Get Reach Motion Tuning
(Sync rotation0, Elbow down blend1 defaults, each0..1). Loaded PHAT remains live;
explicit surface points, Blueprint speeds/wiring and8/6-degree gates are preserved.
Use Surface Point=false selects the new automatic contact rule; the saved tick30
fixture still has its user-preserved explicit point wiring.
Normal incremental build succeeded135.19s/8 actions; new retained state cold-loaded.
Editor16368 reopened and finished on the previous robotics map
`/Game/_mygame/Tests/MimicKitTransfer/M_JoltTransferFailure`, outside Play, no dirty
packages. No crash cause established from the prior log. Blueprint graph and saved
BP/TestNN/PHAT bytes unchanged; reflection status3/native_properties0/pin_types0.
120 isolated lab/native cases pass: final poses match to numerical precision;
equivalent look-ahead roll varies but its forearm endpoint differs<0.000004cm.
Owned Kin-auto, Sim-auto and Sim-explicit grabs all acquire both balls (by absolute
tick150/150/180 after request90), hold through390, then return/retire by411. Four
contact fingers each;186 wrist samples within PHAT (<9e-16 domain violation).
Runtime code is in the normal DLL. A diagnostic-only Live Coding patch separated
look-ahead roll/direction metrics (no object changes); normal DLL diagnostic code
predates that refinement, so include it in the next normal build before cold launch.
No second closure, lab refresh, D/S/robotics edits or asset saves. Evidence and
backups: `Saved/Diagnostics/ReachPort20261016/verification.json`; details in
`Docs/ReachGrasp20261012.md`. No live many-agent performance claim.

**Latest user context:** user explicitly requested TestNN after the reach port.
Editor16368 is now open on `/Game/testNN`, verified remotely, outside Play.
The map switch preserved assets and required no build/restart or save. The prior
robotics map remains saved; do not switch away from TestNN without a new request.
**PHAT limits — October16:** at the user's request, saved seven angular-profile
expansions to contain the drawn/unarmed motion dataset plus5% room. Upper arms,
thighs, ankles and right knee changed; both user-edited wrists remain60/45/90deg.
Frames, geometry, mass/inertia, collisions and Blueprint wiring are unchanged.
Exact values and backup are in `Docs/MimicKitUEFNBodyMatching.md` (current section).
The REACH imported snapshot described below predates these seven expansions;
its lab files/session were not changed by this PHAT update.
**Lab refresh preference:** the user handles Refresh with the lab button. After
code edits, do not automatically reload, close or reopen their lab window. Leave
the running session alone and report that the change is ready to refresh.

**REACH elbow blend slider — October16:** **Elbow down blend** sits directly
below Sync rotation in the right panel. Range0..1, default1;0 exactly restores
original outward preference,1 exactly preserves the latest lower-elbow rule.
`settings.elbowDownBlend` persists in settings/snapshots and survives reset/restart;
old saves default1. One native multiplier, passed per request, no new search or
solver state. Coupled clamped grabs still prioritize wrist feasibility and may
override this preference (the default clamped fixture has identical elbows).
960 native endpoint-comparison frames passed; intermediate motion preserves arm
lengths, both clamped grips acquire at0/.5/1, UI placement/persistence pass.
Only the standalone DLL was built; REACH background service restarted to install.
Installed hash and live stateless HTTP blend verified. User window was not
refreshed, Unreal untouched. Ready for user's Refresh. Evidence:
`Saved/Diagnostics/ReachElbowBlend20261016/`; `test_elbow_blend.cjs` uses an isolated
service/store and headless browser. `build.py --output-dir` stages future builds.

**REACH rotation timing — October16:** shared right-panel **Sync rotation** slider
0..1, default0, stored in `settings.syncRotation`. Zero exactly preserves the old
rotation trajectory. One slows angular pursuit to the remaining wrist-distance /
reach-speed arrival estimate; intermediate values blend angular steps. Rotation
speed remains the cap; PHAT/body constraints or an insufficient angular cap can
delay alignment. Recomputed per tick with no timer/search/state; Follow arm bypasses.
Snapshots, reset/restart and persisted reloads preserve the value; old saves use0.
Isolated verification: full sync both hands finish position/rotation on the same
frames57/69 versus rotation12/13 at0. Both clamped grips acquire with unchanged
gates; retargeting, deterministic replay and UI persistence pass. Evidence:
`Saved/Diagnostics/ReachSyncRotation20261016/`. Only HTML/CSS/JS changed; no build,
service restart, Unreal changes or user-window refresh. Ready for manual Refresh.

**REACH PHAT snapshot — October16:** imported the user's newly edited loaded
PHAT wrists into `Labs/ReachLab/phat.json`: both hands60/45/90degrees in
twist/swing2/swing1 order, all LIMITED; frames unchanged. Lab HTTP export matches
the file. Ready for user's manual Refresh; no build/restart/Play or asset save.
Before/after evidence: `Saved/Diagnostics/ReachPHATImport20261016/`.

**REACH elbow preference — installed and verified:** only `PreferredBend` in
the lab's `solver.inl` changed: forward reaches now also favour a lower elbow
(70% relaxed preference), blending into the accepted side/back preference (100%).
The adjustment still fades near vertical. This supersedes preserving the old
outward-heavy forward rule. In snapshot0005 elbows lower6.47/7.54cm and move inward
5.54/6.17cm; wrist positions and body parameters are exactly unchanged. Both grips
hold with contact/fitting preserved.240-frame target sweeps and default clamped
grabs pass. No new search/iterations/state. DLL, installer and current evidence:
`Saved/Diagnostics/ReachForwardElbow20261016/`; previous side/back experiment:
`Saved/Diagnostics/ReachElbowPreference20261016/`.
Installation succeeded; only the REACH background service restarted.
Installed DLL hash matches the tested candidate, and stateless HTTP replay matches
the installed native solver exactly (`delivery.json`). Earlier approval blocks are
resolved. Window/session settings and Unreal untouched; user performs Refresh to
update the browser's kernel fingerprint and presses Play if the restart paused it.
See the lab README for evidence.

**Current REACH solver — arm first:** the old forearm-derived virtual endpoint
caused excessive body bending in snapshot0002. Replaced it with a bounded search
for wrist-admissible forearm directions, then body compensation driven only by
the remaining upper-arm reach shortfall beyond ordinary positional reach.
Ordinary pursuit catches up before adding compensation; excess is reduced again.
Compensation is continuous while dragging, limited to0.5cm per authored tick,
and the original body kernel still handles balance, legs and body motion.
The arm look-ahead uses at most14 projections per changed shoulder/target and is
cached within0.01cm; none ran during120 settled ticks in each regression case.
Existing per-tick arm correction remains bounded at18 evaluations/hand, settled1.
The original surface references, hand rotations, fitting and8/6-degree gates are
preserved; no relaxed wrist limits. Cache/feedback persist in `grabs[].armPlan`,
are validated on import, and resume deterministically from snapshots.
Snapshot0002 with identical contact: forward bend46.88->27.83deg, crouch21.15->9.14cm;
both grips acquire from idle and continue correctly. Fresh upper-arm contacts on
Restart give17.70deg/4.50cm. An arm-only feasible fixture grips with zero body motion.
This is bounded feedback through the existing body algorithm, not a proof of
minimum whole-body motion; demanding fixed upright palm orientations still bend.
Snapshot regression: overlay mean0.101ms/tick for both hands,p950.250ms; native
body mean0.120ms,p950.310ms. Broader837-frame regression: overlay0.178ms,p950.400ms;
native0.728ms,p952.939ms. No many-agent performance claim. Old performance records
remain in the [lab README](Labs/ReachLab/README.md); current evidence is
`Saved/Diagnostics/ReachArmFirst20261015/verification.json` and
`Saved/Diagnostics/ReachCoupled20261015/verification.json`.
**Ready for the user's manual Refresh.** Lab window/server and Unreal/robotics/D/S
were not restarted or changed. No build; only lab JS and handoff docs changed.

**REACH transport:** Restart now sits immediately left of Play/Pause. It resets
pose/grabs/tick and starts playback, preserving current targets, all tuning,
checkboxes, camera and playback speed. Browser-only change; no build.

**Current REACH contact selection:** Auto palm contact now selects the sphere
surface toward the same-side upper-arm bone origin (at the shoulder), replacing
the previous current-palm-centre reference. Uses full3D ball-to-upperarm direction
once per grab; the chosen normal stays ball-local afterward. Upright orientation,
manual rotation mode, tolerances and fitting are unchanged. A versioned automatic
contact key refits older grabs on the next tick after the user refreshes.
Lab left running; user performs refresh. No build or Unreal changes.

**Current REACH mode:** user requested Auto palm contact; both hands' persisted
orientation is now `surface`. It is exposed as one shared top-bar checkbox,
not an orientation-dropdown option; unchecking restores saved absolute rotations.
Toggling Clamp hand rotation releases the balls and immediately restarts grab
requests for enabled hands from their current displayed wrist/elbow transforms.
Body response, complete pose and tick are retained; contact/fitting are recomputed.
Disabled hands stay disabled. This supersedes the release-only/uncheck behavior. Existing target positions, radii, saved absolute
angles, speeds, clamp, tolerances and pose/camera checkpoint were preserved.
Active grab balls now display a gold surface-contact dot and outward-normal
arrow, transported by the held ball transform; shared rendering includes these
markers in live captures and snapshots. Reset pose & targets now resets only
pose/grab/tick and the captured target translations/rotations. It preserves every
checkbox (including mode, reach/grab and view toggles) plus radius, speeds,
tolerances, camera and playback settings.
Only the REACH app window was reopened; robotics/Unreal were not accessed.

**Reach lab ready — lab first, port later:** user requested the same rapid iteration
workflow as D/S. [REACH — Hand & Body Lab](Labs/ReachLab/README.md) runs at
**http://127.0.0.1:8873/reach**, with desktop shortcut **REACH - Hand & Body Lab**
(distinctive lime hand/purple target). Independent hand checkboxes, RMB target
drag, Shift+RMB depth, orbit/pan/zoom, fixed60Hz pause/step, target rotations,
PHAT wrist snapshot, angle/position readouts and saved JSON+PNG cases. Exact native
body/arm solver source extracted into lab-owned editable `solver.inl`; tiny
standalone DLL builds in seconds, without UBT or Unreal changes. Initial baseline
matches production source; future experiments stay in lab until explicitly ported.
720 kernel frames/2,430 wrist cases/browser interactions pass; actual app window
visible. Initial reach scope has since expanded to the sphere grab pipeline below.
No live complete-overlay physics parity claim. Evidence `Saved/Diagnostics/ReachLab20261015/`.
Unreal13040 remained open; only read-only PHAT export, no Play or asset edits.
Taskbar follow-up complete: launcher uses unique `/reach` path because Chromium's
app identity omits ports; root URLs grouped REACH under D/S. Native browser IDs now
differ, and the live window icon is the lime hand/purple target (ICO favicon).
Only lab server/window restarted through process APIs; saved settings hash unchanged,
D/S and Unreal preserved. No persistent taskbar helper. Read-only identity/icon
verification: `Saved/Diagnostics/ReachTaskbar20261015/`.
**Lab rotation follow-up:** user explicitly says stay in the lab until told
otherwise. Target rotation now uses absolute lab XYZ degrees (`qZ*qY*qX`), with
zero/zero/zero = identity; Follow arm remains available. Schema2 migrates old
idle-relative settings without changing their intended orientation or other
tuning. PHAT remains a snapshot and still clamps the wrist. Verified150 Euler
round trips (including singularities), migration/reload, both-hand identity,
180deg/s pursuit and orientation independence from target translation. Visible
REACH reopened through its launcher; no server/Unreal build or restart. Evidence:
`Saved/Diagnostics/ReachAbsoluteRotation20261015/`.
**Reach lab workspace follow-up:** four small per-hand translation/rotation reset
icons use the user's latest captured values: L13/60/125cm with rotation180/0/90°,
R−14/47/125cm with rotation0/0/−90° (October15 explicit default update).
Canonical `Labs/ReachLab/reset_defaults.json`; also exposed in `/reset-defaults`,
saved settings and live view. Defaults never change during ordinary tuning/restore.
D/S snapshot/refresh workflow adapted: numbered PNG+JSON, restore paused at exact
solver/pose/camera state, JSON import/export, P snapshot, Refresh lab preserving
pending edits/playback, persistent session resume. Worker capture and desktop
identity copied/adapted; `/desktop-view` plus sequence-matched `.png` provide the
actual user's view without computer use; ordinary tabs cannot overwrite it.
Snapshot pixels match the visible framebuffer. Workspace, existing UI and rotation
checks pass. Only REACH server/window restarted; latest user tuning, pose and camera
preserved, Unreal/D/S untouched. Evidence: `Saved/Diagnostics/ReachWorkspace20261015/`.
Reach header simplified at user request: branding removed, Snapshot/Refresh at
top left (the former title position), Reset pose & targets below them, and centered **Clamp hand rotation**
checkbox. This is the existing persisted `settings.phat` switch moved out of the
collapsed wrist section; unchecking bypasses both hands' rotation clamp. Lab only.

**Reach lab grab pipeline complete — October15:** both hands now have Grab ball
and one shared persistent **Ball radius** slider below the centered clamp checkbox
(0.5–15cm, initially3cm). It updates both balls together; per-hand radius inputs
are removed. Closure/grip angle inputs now stay visible in a fixed footer below
the scrolling hand panel; same persisted8/6-degree defaults and native position/
angle gates. Actual-vs-commanded tracking is identical in this kinematic lab,
whereas Unreal additionally checks its actual physical hand. XYZ is ball centre for
grab, wrist destination for reach-only. Actual30 finger joints from mannequin
reference plus authored closed_fist were exported read-only to `fingers.json`.
`grab.js` ports native palm offset, clearance, contact sampling, one-time curl
fitting, closure and distance/angle acquisition gates. Existing absolute hand
rotations remain; Auto palm contact offers the native surface-normal orientation.
Held balls follow a wrist-relative kinematic fixed attachment while RMB moves
their requested destination. Release opens fingers/returns the arm; resize or
orientation changes refit. Snapshot/refresh/live state include curls, contacts,
closure, ball transforms and attachments. This is the sphere pose/contact pipeline,
not Jolt collision response, gravity or physical tracking; native Kin only marks
grips, while the visual fixed attachment is a deliberate lab extension.
Both saved-default grips pass with PHAT enabled; actual user's latest desktop
also holds both balls, four contact fingers each. Preserved newer left target,
rotations, camera and user's clamp-off setting.14 fitted geometry cases, drag,
release, resize, blocked wrist/unreachable/oversize cases, snapshot continuation,
refresh and inactive retirement pass; workspace and reach-only rotation checks
also pass. Only REACH server/window restarted; Unreal13040 and D/S preserved,
no native build, asset writes or Play changes. See lab README and
`Saved/Diagnostics/ReachGrabLab20261015/`.

**Grab parity clarification:** matching acceptance thresholds does not make the
lab's default Absolute rotation mode the same experiment as Unreal Grab Object.
Absolute mode takes the user's orientation first and selects the sphere surface
normal to fit that palm; native Grab Object takes a surface point/normal first
and derives the hand orientation. A read-only lab comparison from neutral with
the latest saved4cm balls, PHAT on and8/6-degree tolerances acquired both absolute
grips (remaining angles0/5.066 degrees), but Auto palm contact acquired neither
(152.961/166.817 degrees, effectively zero position error after240ticks). This
isolates target-orientation selection as a sufficient blocker in the lab; it is
not a replay of the old map. The old PHAT capture also reached the positions
without acquiring grips. No user settings, Unreal map or robotics work changed.

**Complete — grab-angle Blueprint node:** user explicitly requested adjustable
closure/grip acceptance angles (8/6 degrees), not PHAT movement limits. Added
Set/Get Grab Angle Tolerances in the reach library; per-agent settings apply to
both hands, including active grabs. Normal build/restart required by new retained
settings storage. Preserved and saved dirty PoseAgent/TestNN, backed up prior disk
versions; PHAT was already clean. Editor19216 closed gracefully; normal incremental
build succeeded in492.43s,21 actions. Editor25832 reopened TestNN; normal DLLs are
current. Owned Sim check passed: strict0-degree grip blocked acquisition, then180
allowed both physical grips; defaults8/6 unchanged, invalid inputs rejected, agent
isolation and release persistence verified.268 wrist samples stay within PHAT.
Final outside Play/no dirty packages; saved assets unchanged after preservation,
graph wiring unchanged (input-key unused output-default serialization normalized).
Reflection status3/native_properties0/pin_types0. Node is available under
Prophecy → Grab; call Set Grab Angle Tolerances before Grab Object/Grab Bone.
No user Blueprint wiring or default tuning changed. Evidence:
`Saved/Diagnostics/GrabAngleTolerances20261015/`.

**D/S motion is TEMPORARY FINAL, accepted by the user.** Preserve the accepted lab/Unreal motion and tuning; change it only on a new user request. Latest reported Sim slowdown was not reproduced, and the user subsequently said it looked good. The explicit right-wrist limit follow-up is complete; no implementation task remains active.

- **Current review setup:** user removed the continuous D/S branch and requested the October12 two-ball grab experiment on their existing one-shot tick30 branch. PoseAgent and TestNN are now saved locally with two radius3cm spheres assigned to the player. Ball physics prepares at tick29; both Grab Object calls start at tick30,120cm/s and180deg/s. Player sword hides at the trigger; grabs stay held for user review. See [reach/grab review fixture](Docs/ReachGrasp20261012.md). No reach/grasp runtime solver or D/S tuning changes; no commit/push.
- **Wrist-limit follow-up complete:** D/S frees the hand_r–lowerarm_r joint's three angular motions through the full return, then restores the exact entry motions/angles through existing completion/interruption cleanup. Retained layouts unchanged. Four owned-PIE checks/498 sampled checks pass, including custom limits, repeated requests and hide during both returns. Full BP graph unchanged; no assets saved/restart. Current user graph starts S during initialization; diagnostic waits for it to finish before its controlled D/S pair. [Wrist-limit lifetime and evidence](Docs/SwordHolster.md#right-wrist-limits-during-ds-october15-follow-up).
- **Reach/grab PHAT follow-up complete:** user requested hand control follow the edited PHAT automatically; explicitly reach/grab only, D/S excluded. Native overlay reads loaded asset wrist frames/modes/angles each active update and constrains hand orientation, including release return. 4,860 math cases and804 live wrist samples pass across Kin reach, Sim reach and Sim ball grabs. Editing an isolated transient PHAT during an active Kin reach updates the clamp without restarting it. **Ball fixture limitation:** both target positions reached, but neither grip acquired by210 under current wrist limits; no success claim for grasp acquisition. User asset unchanged, no retained layout changes/save/restart. [Details and evidence](Docs/ReachGrasp20261012.md#phat-wrist-constraints--october-15).
- **Remote checkpoint:** commit `965b9cb4ac649f8f4ce7604e9a6b5c33588b1536` on `codex/standalone-sim`; annotated tag `ds-temporary-final-2026-10-15`. Branch and tag verified on GitHub. Previous broad D/S checkpoint `b34e1b31` is its parent. Recovery manifest verifies all 5976 recorded files; this is a curated backup, not the whole project/machine.
- **Finger rendering follow-up:** grab calculation was active but LOD1 removed finger bones (`r.SkeletalMeshLODBias=1`). Saved test player's Mesh/PhysicalMesh Forced LOD Model1 (=renderLOD0) in TestNN, matching the original experiment. Attack Fists already enabled; no graph/runtime/global-LOD changes. Kinematic LOD0 finger/model error<3e-7cm; physical native finger poses already present and LOD0 selected with the pre-Play override. Evidence `Saved/Diagnostics/ReachGrabFingers20261015/`; use next Play for the saved override.
- **Editor:** grab-angle implementation required one normal build/restart. Its first launch mistakenly used WindowStyle Hidden; user reported no visible editor. Clean hidden editor25832 was closed and reopened visibly as13040, without another build or asset changes. Use **Normal** for the requested interactive editor/browser; **Hidden** only for background helpers. Latest lab task preserved this running editor. User PoseAgent/TestNN edits saved with prior disk backups; PHAT unchanged. Reflection status3/native_properties0/pin_types0; wiring preserved. Remote checkpoint predates these local assets and does not contain this scene.
- **Build:** normal incremental editor build succeeded in492.43s for the grab-angle node and incorporated preceding Live Coding patches through20. **Normal DLLs are current.** Keep future builds minimal/incremental and prefer reload-safe implementations where appropriate. Do not restart just to tidy, save, inspect or tune; retained native storage/layout changes still require normal build/restart.
- **Last saved asset verification:** PoseAgent compiled status3 and saved with TestNN for the grab fixture. Against the user's live pre-edit full graph, only the existing tick30 Branch's unused Else and its terminal reroute's unused Output gained links;28 nodes added, no existing nodes removed or tuning changed. Both reaches active at absolute30, physical grips90/93, held through220. A_Sword untouched in this task. Native reflection health remains status3, native_properties0, pin_types0. Evidence `Saved/Diagnostics/ReachGrabWiring20261015/`.
- **Local-only work:** TestNN, generated defense pickers, separate MimicKitTraining/PhysicalRecovery work and unrelated PDF remain outside this D/S checkpoint. Do not stage, clean or overwrite another task's work. `ProphecyFKReturnFeedbackTests.inl` has appeared dirty without a semantic `git diff`; inspect before treating it as a new change.
- **Primary references:** [D/S runtime and integration](Docs/SwordHolster.md), [lab controls/recorded problems](Labs/SwordHolsterLab/README.md), [attached-arm physics audit](Docs/SwordHolsterPhysicsAudit20261014.md). Full old opening retained in the [October10–15 archive](Docs/Journal/ProjectJournal-history-through-2026-10-15.md); rejected trials are historical, not pending work.

## Accepted D/S behavior and settings

**October15 wrist PHAT follow-up:** user requested wrist articulation in the
separate training model and the same dataset+5% limit coverage. Only hand_r and
hand_l angular limit fields additionally changed: twist/swing2/swing1 degrees
30/23.71/50 and40.86/46.31/50 respectively. Saved PHAT; all other profile fields,
geometry, mass and drives unchanged; dirty PoseAgent preserved. Backup and
verification: [body-matching wrist correction](Docs/MimicKitUEFNBodyMatching.md).

**October15 PHAT limit update (explicit user request):** eight angular profiles in
PA_UEFN_Mannequin now contain the26 accepted retargeted locomotion clips with5%
angular leeway; both ankle twists are limited instead of locked. Shapes, masses,
joint frames, collision exclusions and drives are unchanged. Asset saved through
remote Python; preexisting dirty PoseAgent preserved. Values, backup and numerical
verification: [current PHAT limits](Docs/MimicKitUEFNBodyMatching.md#current-phat-limits--october-15-authorized-omni-expansion).
Existing physical rigs need recreation to import the saved bounds; no user Play
was active and no editor restart/build was needed. D/S code/tuning is unchanged.

D = draw/unsheathe; S = sheathe. The active standalone lab is `Labs/SwordHolsterLab`, normally at `http://127.0.0.1:8818`. Saved tuning is `Labs/SwordHolsterLab/state.json`; Unreal export is `Content/locomotion/SwordHolsterProfile.json`. Do not change the lab silently to make a native test pass. Motion experiments start in the lab; port only when requested. The original Attack Recovery Lab is a separate application (below).

The following are **last saved checkpoint values**, not permission to overwrite fresh user edits. Read the current Blueprint and saved lab before future imports.

| Setting | Drawing | Sheathing |
| --- | --- | --- |
| Max reach speed |260cm/s|230cm/s|
| Max reach angular speed |900deg/s|600deg/s|
| Sliding speed |330cm/s|230cm/s|
| Sliding curve |Linear|Latest saved four-point curve|
| Base FK return duration |.5s|.9s|
| Main return inertia |.5|.7|
| Early return start |90% of outward slide (10% insertion remaining)|70% insertion|
| FK→IK arm-return blend |Enabled, fractions.25→1|Disabled|
| Coordinated elbow IK correction |Enabled,15deg soft zone|Enabled,15deg soft zone|
| Independent hand rotation FK alpha |1|1|
| Big-node NN blend range |(1,1)|(0.7,1)|

Other saved values: axial shrink25% over.25s, unshrink.5s; attached hand speed150cm/s and angular speed200deg/s. Big-node grip holster rotation compensation80%, return duration.25s, S kinematic switch fraction.5. Leeway attachment phase disabled; tip tolerance2cm. D hand-local-X turn800deg/s, sigmoid exponent1.5, cutoff.4 of arm return. Negative angular speed reverses it; afterward existing hand return continues. Return durations can include angle-dependent extra time; base duration is not necessarily total duration.

For later user-requested imports, `node Tools/SwordHolster/SyncLabProfile.cjs` exports saved lab settings; inspect its semantic diff before applying. Existing big-node pins override imported values. `Prophecy.Editor.RefreshHolsterGripPins SetSlideSpeeds <draw> <sheathe>` updates only unlinked speed literals; preserve every other pin and compare the full graph before saving.

Latest import changed only S slide speed170→230 and its curve's first interior point to(.15053891961839325,.0988776276854313). Other S points: (.650179602563385,.7111385494636496), (.8849101307618773,.9562043029634382), (.9553293659722167,.9884497709488423). D remained330/linear. In the current saved geometry: S18ticks/.30s, D13ticks/.2167s. Duration depends on blade travel/shrink, not a fixed duration override.

### Ownership, timing and mode switches

- Authored seconds use60 unpaused game ticks. NN inference cadence is separate. Reach/slide curves affect only their procedural motion, not underlying idle/walk/run, head or FK return; each D/S return has its own timing curve.
- Reach uses FK, authored spine/clavicle targets and explicit elbow preference. The rejected direct-IK **reach** trial is removed. This is distinct from accepted FK→IK **return** and coordinated elbow IK correction. Old forearm-only bend limiter remains deleted; Main inertia scales strength without shortening duration.
- Geometry comes from authored sword/holster placement and blade marker; apply asset scale once and shrink only along blade axis. Capture references before moving the mount. Holster follows the actual component; compensation rotates about its origin without introducing pelvis-relative translation.
- S aims tip at entrance with angular tolerance. Optional leeway attachment phase first attaches, then aligns the tip within attached speed limits, then slides from the reached depth. It must not reset insertion to0. Holster-relative speed limits are intentional. Current saved leeway phase is off.
- During attached alignment/sliding in Sim, native upperarm_r/lowerarm_r/hand_r temporarily become kinematic and follow the completed actual pelvis/clavicle and holster-local sword path. Remaining body stays simulated. Sword stays attached to holster; no separate predicted sword path or attached hand–sword joint. Release restores simulation from current pose/COM/angular velocities and seeds return from actual current/previous arm poses. Ordinary kinematic characters do not receive this native ownership override.
- Holster simulation switches independently; a kinematic agent forces a kinematic holster while retaining its preference. Physical holster temporarily goes kinematic at the configured S reach fraction / during D sliding. Rotation compensation then applies; usual rest return and original joint restoration resume the prior preference. Interruption cleanup restores owned limits, collisions, joints and modes.
- Tab switches Sim/Kinematic without cancelling D/S, restarting clocks/shrink or losing attachment. Kin→Jolt queues the **entire** mode change at the existing safe admission boundary, avoiding an intermediate Chaos step. Rebind waits for native ownership. Completed attached-arm pose is republished at transfer; stale presentation blend is retired. **No added Sim→Kin whole-pose fade**: that trial delayed moving actions and was removed.
- A_Sword's consuming Tab→pause event was removed; character Tab works, Caps Lock backend selection is unchanged. RMB debug slowdown now uses `t.MaxFPS`, not fixed simulation delta. All agent/equipment overlap events are disabled in both modes at user request; blocking collision and queries remain.
- D/S suppresses right-arm collision for the action, restores it on completion/interruption, and applies head–clavicle suppression only during D/S. Neck/head and right-wrist angular limits are Free through the full return and restore their captured entry modes/angles afterward. See the physical-neck reference below for permanent neck pairs. Early NN return protects the gripping arm until release; arm return then uses its own clock/window.

### Verification and remaining limits

- Latest slide import:240 consecutive live ticks,3agents, six S/D slides; S18ticks and D13ticks for every agent. Recorded slide fractions match the lab evaluator within4.93e-10. Only the S speed pin changed in the graph. Evidence `Saved/Diagnostics/SlideLabSync20261015/`.
- Sim slowdown report: paired295tick current-scene runs; D release-to-finish38/39/40ticks per agent in **both** modes. Physical hand target error after the first two release ticks at most.11861cm. No slowdown fix was made; user accepted current motion. Evidence `Saved/Diagnostics/DrawReturnSlow20261015/`.
- Mode continuity: seven runs/4065ticks across3agents,111 requests including queued cancellations, actual Tab, moving agents and rapid reversals.16 immediate attached-arm transfers preserve position within6.36e-14cm and rotation<.01deg. Other bodies can still remove ordinary physical tracking error on entering Kin (measured up to1.1773cm/7.0571deg). Evidence `Saved/Diagnostics/ModeContinuity20261015/`.
- Attached-arm audit:123 completed slides/4705ticks, maximum S path error.00004615cm, native/query/display position discrepancy.00000417cm; ten lifecycle cases pass. Full legacy suite was **not** all green: outdated authored/short-return fixtures remain documented. See [audit and receipt](Docs/SwordHolsterPhysicsAudit20261014.md).
- Performance: latest measured attached-arm stage after overlap removal mean.184076ms/p95.2679ms for3agents, sequential editor runs. Earlier.257129ms baseline and scoped-movement-only result remain in [D/S topic](Docs/SwordHolster.md). This is neither total game time nor a100-agent benchmark or10x gain. No new performance work pending.
- Accepted does not mean universally flawless: prior no-switch fixture recorded a~148.53deg upper-arm roll at D release382; it was explicitly reported, not fixed by the Tab work. Historical obstructed running/unreachable-arm cases and variable-step neck test limitations are documented. Do not revive these as unsolicited fixes or widen tolerances to conceal them.

## Other systems to preserve

| Area | Current contract / caveat |
| --- | --- |
| Breathing | [Breathing](Docs/Breathing.md): default upper+pelvis, only at zero movement input; active through D/S. Successive cached idle deltas move actual accepted pelvis/upper pose; legs keep feet in place and NN history receives it. Independent pelvis/upper amplitudes; speed snaps.3→1 by.1 using shared pre-baked samples. No presentation-only overlay. |
| Physical neck | [PhysicalNeck20261013](Docs/PhysicalNeck20261013.md): original PHAT23bodies/22joints, neck_01→neck_02→head, approved capsule size and split neck mass; actual neck_02 feeds NN. Both necks exclude head/clavicles/each other permanently; head–clavicle exclusions only during D/S. Solver comparison option remains available. |
| Get-up | [GetUp](Docs/GetUp.md): remain simulated, restore magnetization; both-arm anti-jiggle until lower handoff then prior independent settings; magnetization0→1 at lower marker; slot1 includes PhysicalMesh material. Independent lower/upper handoff/tempering. Automatic floor-lift correction and its toggle were removed; explicit Ground Offset remains. Old tick30 hookup is historical—inspect current BP. |
| Native reach/grasp | [ReachGrasp20261012](Docs/ReachGrasp20261012.md): Reach Target/Double Reach/Grab Object/Grab Bone, durable local contact point and one joint per hand, fit fingers once. Ball and forehead prototypes tested; lower chin blocked; concurrent attack/get-up ownership not fully tested. Do not silently promote prototype to universally validated behavior. |
| Cosmetic holster strap | [HolsterStrap](Docs/HolsterStrap.md): separate asset/AnimDynamics work, editable ABP body definitions with linked constraints. Does not replace the existing agent holster or D/S. |
| Separate local tasks | MimicKitTraining and PhysicalRecovery files are local work from other tasks. Check their own docs/status before touching; this D/S cleanup neither validates nor stages them. |

## GOLDEN RULES — read before touching Unreal

1. **User tick numbers mean Blueprint `absolute tick debug`, never `tick debug`.** Auto-reset resets the latter. Record absolute tick, family, ownership and phase.
2. **Authored seconds =60 unpaused game ticks.** Holds/delays/fades/spreads do not use wall time, DeltaSeconds or30Hz inference steps. Explicit policy-frame controls (e.g. defense Frames After Hit) retain documented policy-frame units. [Timing contract](Docs/BlendTickTiming.md).
3. **Retained native layout changes require a normal build/restart.** Includes PRIVATE structs/classes in static TMap/TSet, heap allocations and nested profiles, not just reflected fields. Even empty containers retain allocations with the old stride. Live Coding cannot migrate them; isolated passing tests do not establish reload safety. Preserve assets, close cleanly, build, reopen TestNN, verify actual Play initialization.
4. **Keep small fixes fast.** No cosmetic/comment/tooltip edits to widely included headers, especially `ProphecyAgent.h`, even after compiling: they force the next task to rebuild dependents. Prefer implementation files and existing narrow libraries. New reflected libraries can also regroup generated/unity files. Do required API changes correctly; avoid unrelated rebuilds/full suites/toolchain edits.
5. **Build workers are automatically dynamic.** Installed UBA adapter recalculates free physical/commit RAM every500ms, default1.5GiB/job with CPU cap. Do not force fixed workers or restart a build to change concurrency. One worker can be correct with low RAM. `Tools/ConfigureBuildWorkers.ps1` reinstalls after engine restore/verification if needed. No custom launcher. [Build-worker contract](Docs/DynamicBuildWorkers.md).
6. **Preserve user work and active Play.** Owned diagnostic Play is authorized when needed for the requested investigation and no user Play exists; no repeated permission question. End only your own sessions. Do not silently stop user Play, restart, alter tuning/wiring, save unrelated assets or restore old backups. Explicit save/reopen requests authorize necessary steps. Preserve requested dirty assets before an authorized restart.
7. **Never cold-launch stale DLLs.** Successful Live Coding patches do not update normal DLLs. Build before reopening when needed; stop if it fails. Explicitly open `/Game/testNN`, not heavy default `/Game/mybasic`. Never remove expected pins/functions to accommodate old DLLs. User rejected a custom launcher; do not recreate it.
8. **User editor uses normal UI flags.** No `-unattended`, `-nullrhi` or automated test commands on interactive launch. Unattended bypassed normal per-monitor DPI setup and caused small fonts. Prefer isolated `UnrealEditor-Cmd -nullrhi -nocef -unattended` automation: interactive automation has previously crashed CEF. Don't change UI scale/render settings to mask it.
9. **Minimize editor closures; use Live Coding when layout-safe.** User explicitly reiterated this on October10. Do not restart for routine inspection/testing or safe implementation-only patches. Retained layout changes still require rule3's normal build/restart; batch necessary changes into one restart and wait for graceful exit before starting UBT. New native global registrations (for example CSV profiler categories) also need cold initialization; October14 Live Coding of a new CSV category crashed at its first captured scope. Avoid reflected WorldSubsystem/Agent reinstancing. Preserve unsaved BP before necessary reflected reloads; keep PIE stopped through patch application, not only dispatch. `LiveCoding.CompileSync` blocks the editor: explain first. Check compile AND reload completion before captures. Adaptive unity stays disabled; ordinary unity remains enabled.
10. **Check existing BP after reflection changes.** Use targeted stale-library-CDO/Agent repairs below, preserving all other defaults/links. Python wrappers may be stale despite valid native reflection. Verify the full graph; don't save a broken BP.
11. **Inactive/disabled/completed means no recurring feature work.** No extra inference/timer/skeleton copy/IK/query/history capture when unused; retire state/callbacks. A cheap guard is not literally zero CPU. Optimize supported behavior without sacrificing correctness.
12. **Measure before claiming a cause.** Distinguish raw NN, accepted future, displayed interpolation and physical mesh. NN Hit is not physical contact. Recurrent changes alter later states: preserve the prefix and intervene just before the symptom, or replay exact inputs. Keep geometry/checkpoints fixed unless changing them is the experiment.
13. **Lab first for motion experiments; port to Unreal only when explicitly requested.** User reiterated this after the mistaken October13 drawing IK implementation.
14. **Quick, concise collaboration.** User prefers their own motion tests unless investigation/testing is requested. Current FK elbow work uses numerical poses/poles, not images. Use remote APIs/scripts instead of taking over the desktop. No routine subagents/exhaustive suites/unsolicited changes. Don't re-ask already-authorized steps.
15. **Curated, bandwidth-limited backup.** Explicit staging only; never `git add .`, LFS transfers, bulk assets, caches or generated model uploads unless requested. Keep all FPS/performance references, especially100-agent benchmarks, during cleanup. No deletion outside authorized scope.
16. **Authored motion is at least root-local, per user.** Overall character turns carry the authored motion; pelvis/spine gait compensation is separate. World-space physics/query output does not justify a fixed-world authoring history. D/S head history and holster stabilization now follow this rule; do not claim every other system has been audited.

## Omni locomotion recording viewer — October15

User-requested gallery ready at **http://127.0.0.1:8841/**: 14 walk +16 run clips, each initialized from its matching actual omni animation, then120 NN-only game ticks settle and180 ticks recorded (181 samples,26 controlled bones). Actual current WalkJuly5/Run and Upper82500 contracts retained. Kinematic presented NN output; no physical noise or source-animation playback during capture. Per-frame checkpoint weights, finite poses, input speeds and continuity verified. RR-offset Run source350cm/s is capped at native345cm/s, explicitly retained/disclosed. Initial recorder heading-basis error and scene automatic-Run override were caught and corrected before accepting captures. Six-view synchronized gallery, single view, filter/pages, live scrub and per-tick stepping; existing D/S renderer reused read-only. No engine build/restart, saved asset/wiring/tuning changes or training changes. Editor19216 remains TestNN/outside Play,60FPS; pre-existing dirty PoseAgent preserved. [Procedure, source scripts and evidence](Docs/OmniLocomotionRecordings.md); receipt `Saved/Diagnostics/OmniRecord20261015/receipt.json`. This viewer does not replace D/S lab clips. October15 viewer-only correction: local-Y basis sign now matches the shared renderer; facial features no longer appear on the back of the head. Recorded transforms unchanged. User accepted the cuts; gallery now excludes Run LL/RR and Walk LL/RR (26 displayed:12walk/14run, offset variants retained). Original30 recordings retained. Best full-stride cuts selected for all30 motions; viewer defaults to unblended cut playback with an original-capture toggle. No cuts exceed the documented review thresholds; exact indices/metrics in loop-cuts.json.

## Tools and safe build/reopen sequence

| Item | Location |
| --- | --- |
| Workspace/project | `C:/Users/singerie/Documents/Unreal Projects/Prophecy/GameAnimationSample3.uproject` |
| Target/engine | `GameAnimationSample3Editor` / `C:/Program Files/Epic Games/UE_5.7` |
| Main BP/native class | `/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent` / `AProphecyAgent` |
| Map | `/Game/testNN` |
| Python | `C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe` |
| Remote runner | `Tools/RunUnrealRemote.py` (preferred tracked copy) |
| Current launch log | `Saved/Diagnostics/HolsterAttachmentAudit20261014/editor-after-profiler.log` |
| Default editor/build logs | `Saved/Logs/GameAnimationSample3.log` / `%LOCALAPPDATA%/UnrealBuildTool/Log.txt` |
| Git | `https://github.com/DTSwink/Prophecy.git`, `codex/standalone-sim` |

Read scripts before reuse: some start/end PIE, mutate actors/CVars, compile/save/repair or quit. Explicit UTF-8 file I/O. From project root:

```powershell
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/RunUnrealRemote.py Saved/Diagnostics/YourScript.py
```

Useful remote APIs/commands:

- `unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()` checks Play; `.get_editor_world()` checks map.
- `unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Editor.LiveAgentTypes Inspect')`; report `Saved/Diagnostics/LiveAgentTypes-Inspect.txt`. Healthy: status3, native_properties0, pin_types0.
- `Prophecy.Editor.RepairLibraryDefaults` repairs archived library CDOs; `Prophecy.Editor.LiveAgentTypes Repair` repairs exact stale Agent types. Targeted repairs, not routine edits.
- `Prophecy.Sword.AuditCollisionGraph` writes full BP graph to `Saved/Diagnostics/SwordThigh/BlueprintGraph.txt`. Compare before/after; normalize only known irrelevant reflection paths, never meaningful defaults/links.
- `unreal.BlueprintEditorLibrary.compile_blueprint(bp)` then `unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False)` saves only requested BP. Back up existing bytes; preserve unsaved user work first. Compiling is not saving.

For an authorized restart: preserve dirty assets, close cleanly (never force-kill unsaved editor), then:

```powershell
& 'C:/Program Files/Epic Games/UE_5.7/Engine/Build/BatchFiles/Build.bat' GameAnimationSample3Editor Win64 Development '-Project=C:/Users/singerie/Documents/Unreal Projects/Prophecy/GameAnimationSample3.uproject' -WaitMutex -FromMsBuild
```

Do not add `-NoLiveCoding`: it changes definitions and can rebuild broadly. After success, launch directly:

```powershell
Start-Process 'C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor.exe' -ArgumentList '"C:/Users/singerie/Documents/Unreal Projects/Prophecy/GameAnimationSample3.uproject" /Game/testNN -NoSplash'
```

Verify reflection/BP after launch; repaired Play crashes require actual Play verification. Startup restore/low-space dialogs can block remote discovery. Preserve autosaves/metadata; don't assume recovery happened or overwrite newer work with older backups. Diagnostic callbacks need timeout/error cleanup, CVar restoration, owned-session checks and data release. Physical rigs need actor ticking: tick-disabled fixtures must first switch all involved agents to Kinematic.

## Attack FK return and Attack Recovery Lab

- **Last recorded active Attack Recovery Lab:** `C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab`. `Labs/AttackRecoveryLab` is the portable backup, not necessarily the active server. Never overwrite live `state.json` from a stale backup.
- Server `http://127.0.0.1:8817`; `/desktop-view` has top-level `state`, `displayedPose`, `sequence`, identity/fingerprint, not nested `view`. Check freshness/client identity. Numbered snapshots are historical. [Capture/API instructions](Labs/AttackRecoveryLab/README.md).
- UE first slashLD =lab **variant21**, absolute61–101,21 unique30Hz policy frames from41 ticks,25 bones, excluding physical response/post-attack return. UE XYZcm -> lab XZYmetres; imported UE variants bypass harness forearm-roll repair. Original320 variants unchanged. Backup includes current saved lab profiles/view.
- Accepted original FK return with inertia, **not optional continuous spring**. Idle is real Unreal `M_Neutral_Stand_Idle_Loop` frame0, same across attacks, parent-local. Hand local inertia zero, parents still move hands. Spine01–05 share one weight, arms symmetric. Main inertia, bone weights, return/easing/timing are per attack. Spine angle adds flat seconds (.29s/90deg default), independent of base duration.
- **Remove upperarm twist inertia:** per attack, symmetric,0original/1full axial removal. Decomposes finite added inertia about actual shoulder-to-elbow axis, preserves swing. World mode carries correction into forearm/hand preserving local rotations. No angle clamp/forced downward elbow. Skipped after completion/zero inertia. Rejected90deg limiter/controls removed.
- Native **Set Attack FK Return Twist Inertia** changes only this field; Attack None means all families. Separate Values/Inertia Profile setters preserve it; legacy combined setter replaces the whole profile. Reset preserves captured configuration. [Return contract](Docs/AttackFKReturn.md), [separate controls](Docs/FKReturnSeparateControls.md).
- **Last verified attack slashLD tuning (October9; re-read current BP before changes):** return .39s, inertia .18, easing0, inertia hold .08, decay .8, world=true, angle addition .29s/90deg, twist removal .98. Weights spine .31 / clavicle1 / upperarm1 / lowerarm .36 / neck01 1 / neck02 1 / head1. Other15 profiles/idle unchanged. BP **NN AlphaHold .17 / Trim0** retained: different from inertia hold .08. Legacy/Values slashLD override nodes disconnected at verification; re-read if user changes BP.
- Parity:321 variants;2568 pure samples max .000207684cm/.000281378deg;6010 unchanged-winding runtime samples max .001155359cm/.000269452deg. Conditional slash winding separately redirects problematic inward arcs; don't promise identical curves under all UE modifiers.
- Files: `ProphecyFKReturn.h`, `ProphecyFKReturnMath.h`, `ProphecyFKReturnData.h`, `ProphecyFKReturnLibrary.cpp`; exporter `Tools/NN/ExportFKReturnLab.cjs`. **Don't overwrite all native profiles with a whole-lab export for one attack.** Check other rows/idle byte-identical. To recreate the ignored parity fixture safely on a fresh checkout, use `node Tools/NN/ExportFKReturnLab.cjs --reference-only`; it reads accepted native profiles without writing them and produces `Saved/FKReturn/lab-reference.json` needed by the parity test.

## Current combat contracts

Read current source/topic docs and actual BP pins for enabled settings. Defaults are not necessarily scene settings. Specials =full/half attacks and active Parry/Dodge; queued defense remains locomotion. Policy cadence30Hz differs from authored60-tick seconds.

| Area | Current reference and key caveat |
| --- | --- |
| Attack lifecycle/counters/bones/kicks | [AttackControls](Docs/AttackControls.md), [SlashBlueprintUsage](Docs/SlashBlueprintUsage.md). Active Trigger retargets without restarting. Kicks ignore half requests; experimental kick half regime removed. Previous Attack Name updates on end. |
| Half reach/ghost | [HalfAttackGTInitialization](Docs/HalfAttackGTInitialization.md), [GhostAttackLean](Docs/GhostAttackLean20261008.md). Upper AND lower ghost share compensated/clamped target. Older upper-only descriptions superseded; minimum reach defaults30cm horizontally about pelvis. |
| Ghost loco | [GhostLocoDrag](Docs/GhostLocoDrag.md). Independent undragged history stabilizes shared pelvis/upper; real feet keep drag and pelvis inertia. General/kick-specific inertia independent; kick run NN sees ghost kicking leg. |
| Attack motion/feedback | [AttackMotionInertia](Docs/AttackMotionInertia.md), [AttackNNFeedback](Docs/AttackNNFeedback.md). Preserve optional filters/legacy feedback defaults. No silent vanilla-fidelity rewrite; new specials cancel outgoing recovery. |
| Defense inputs/order/ghost | [NNDefense](Docs/NNDefense.md), [LiveDefenseControls](Docs/LiveDefenseControls.md), [DefenseInputGhost](Docs/DefenseInputGhost.md). Attacker accepted output before defender; visualize accepted defender body and actual pelvis/collider history, not physical-pose substitutions. |
| Defense start/end | [DefenseStartThresholds](Docs/DefenseStartThresholds.md). Current nodes use per-attack integer **Start Delays after Armed**, default0; raw Hit thresholds replaced. Post-Hit/max-duration/end/manual-stop settings retained. Movement input changes root window, not defense state. |
| Defense returns | [LiveDefenseControls](Docs/LiveDefenseControls.md). Legacy upper spring and separate lower tempering for Dodge; independent optional FK return for Parry. Don't mix attack/Parry profiles. |
| Defense collision | [DefenseCombatRules](Docs/DefenseCombatRules.md). Dodge excludes relevant attack bodies plus held sword for all families, only attacker/dodger pair. Parry protects BP trunk+both arms by zero contact inverse mass/inertia against attack bodies. Welded identity/sweeps respected; release on end/reset. |
| Sword phases/sweeps | [SwordAttackCollision](Docs/SwordAttackCollision.md), [JoltPHATSweeps](Docs/JoltPHATSweeps.md). Accepted sweeps initiate from sword on six slash families. Right punches exclude sword attack role and suppress its victim collision Armed->End. No universal penetration-free promise. |
| Arms anti-jiggle | [ArmsAntiJiggle](Docs/ArmsAntiJiggle.md). Opt-in each arm, defaultoff, solver motors. Suppressed **Armed->End for sword attacks only**, not Armed->NN Hit. Timed disable composes, retains asymmetric choices. |
| Sword no reaction | [SlashSwordNoReaction](Docs/SlashSwordNoReaction.md). Automatic slash Armed->End suspends during victim defense; Strength0..1. Manual override wins; defaultoff. Not blocked-sword stabilization. |
| Snapshots/magnetization | [PhysicalProfileSnapshots](Docs/PhysicalProfileSnapshots.md). Actual special entry restores slot1/cancels relevant pending blends; queued defense not active. Per-bone/below, hold-outs and delayed tolerance supported. Anti-wobble experiments reverted. |
| Reset/regional ends | [AgentReset](Docs/AgentReset.md), [RegionalSpecialRecovery](Docs/RegionalSpecialRecovery.md). Full->half emits lower end; upper return on upper end. Reset wins; arbitrary BP timers/variables aren't universally reset; reacquire recreated equipment. |
| Root/camera/trajectory | [RootSelfBalancing](Docs/RootSelfBalancing.md), [SlashFootContactsAndCamera](Docs/SlashFootContactsAndCamera.md), [ComputeCatchUp](Docs/ComputeCatchUp.md). Player-only camera/handoff; impulse/spread delays tick-based. Unreachable catch-up10000/false with naive pursuit velocity. |
| Diagnostics | [NNModifierDebug](Docs/NNModifierDebug.md). Paused one-tick report persists. Potential constraints aren't measured deltas. Raw Armed/Hit getter returns-1 inactive. |
| Checkpoints | [UpperCheckpointPicker](Docs/UpperCheckpointPicker.md), [AttackCheckpointComparison](Docs/AttackCheckpointComparison.md), [DefenseCheckpointPickers](Docs/DefenseCheckpointPickers.md). Dodge154546 Post-hit return5 / Free pelvis added to enum/path/staging and frozen export October11; was recorded as pending native compile/reload in that side task. Subsequent D/S builds are not evidence of explicit picker validation; check its topic and current reflection before relying on it.17 export parity batches passed (max1.55e-6); raw `Saved/Diagnostics/Dodge15454620261011/export/`. Read current selection; old defaults are not authoritative. No training watcher. |

**Keep performance references:** [DoubleReachPerformance20261008](Docs/DoubleReachPerformance20261008.txt), matching JSON and raw `Saved/Benchmarks/DoubleReach20261008/final/`. Direct native won and user chose direct. CPU reaching cost only, not total FPS. [Jolt performance](Docs/JoltAcceptedPerformance.md). Blood/native-Niagara migration and multiplayer aren't implemented by these tasks; historical proposals aren't accepted features.

## Push, restore and maintaining this handoff

- October18 scripts follow-up: scoped source/tools/docs for reach/grab, REACH lab,
  explosion/impact, VDB and bomb fuse/fragments/fade. No editor save/restart or
  current content assets, full captures, binaries or caches included. Separate
  robotics/training staging is preserved. Recovery inventory is regenerated for
  the selected tree; see Docs/Recovery.md for external dependencies and limits.

- Lightweight push: source/tests/scripts/docs, lab code/captured variant/saved profiles, freshly saved PoseAgent BP. Current TestNN map modification, generated defense pickers, unrelated PDF, binaries/caches/full captures remain local. Older tracked maps/models remain recoverable, not a promise of today's exact scene.
- `.gitattributes` stores curated assets as real Git blobs. No LFS uploads; explicit staging and size inspection. Set process-local `GIT_LFS_SKIP_PUSH=1` for the push (the legacy pre-push hook still invokes LFS); don't remove hooks or alter global settings. After staging, `Tools/Recovery/VerifySnapshot.py --write-index`, stage `Tools/Recovery/Snapshot20261003.json`, commit, verify `VerifySnapshot.py HEAD`, push `origin codex/standalone-sim`, compare remote HEAD. Manifest filename retains legacy date; inventory must match latest tree.
- [Recovery](Docs/Recovery.md) covers omitted external assets, dependencies, original checkpoints and standalone shortcuts. Repository isn't a full laptop backup. Milestone receipts: `Tools/Recovery/Receipts20261009FK/`.
- [Full pre-cleanup history through October9](Docs/Journal/ProjectJournal-history-through-2026-10-09.md) preserves earlier investigations/domain references. Historical prose is preserved; Markdown links were adjusted for the archive location. Older archives remain under `Docs/Journal/`. Historical pending builds/PIDs/scene settings aren't current instructions.
- [Full October10–15 handoff history](Docs/Journal/ProjectJournal-history-through-2026-10-15.md) preserves every superseded opening entry and previous build/save/test claim. Read current summaries first.
- **Update current sections instead of prepending endless logs.** Keep build coverage, saved assets, defaults versus actual BP, evidence and limits explicit. Detailed experiments belong in linked topic docs/receipts. Archive superseded behavior, preserve user corrections, and never revive an old investigation as unsolicited work.


