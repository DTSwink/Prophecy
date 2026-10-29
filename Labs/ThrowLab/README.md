# Throw Lab

Independent standalone lab created October 26, 2026. Launch **Throw Lab** from
the Windows desktop, or run `launch.ps1`. Address: http://127.0.0.1:8893/throw-lab.html.
The launcher checks service identity and uses its own `ThrowLab/browser-profile`.
The local server runs below normal priority; no Unreal, NN or training process
is required. One small Jolt WASM world runs inside the browser, with no workers.
Paused playback schedules no animation loop; hiding the window pauses playback.
Rendering caps pixel ratio at 1.5.

Desktop/taskbar correction October26: a unique teal target / orange spear icon
replaces the copied Bodyflip icon. `create_icon.py` builds the multi-resolution
ICO; desktop shortcut and app favicon both use `assets/throw-target.ico`.
`throw-lab.html` is now the canonical HTML entry; `index.html` redirects there.
The launcher must use this distinct path: Chromium's URL-app identity uses
host plus path, omitting port ([Chromium implementation](https://chromium.googlesource.com/chromium/src/+/main/chrome/browser/web_applications/web_app_helpers.cc)).
Thus root URLs on different local ports can collide; keep the unique path.
Existing windows need closing/reopening from the updated desktop shortcut to
receive the new launch identity. Shortcut/icon HTTP checks and the isolated
browser smoke pass; the actual Windows taskbar was not inspected or controlled.
No service restart or extra resident helper was needed.

## Current scope and workflow

## Approved throw checkpoint - October29

User approved the current lab and requested an Unreal port with throw-control
nodes; nonphysical animation/pose/grip settings mirror this checkpoint.
`approved/2026-10-29/saved-profile.json` preserves the exact current scene library
and presets; its manifest records hashes. It supersedes October27 for current
behavior. Use the same deliberate backup/restore procedure below.

## Approved throw checkpoint - October27

Approved lab commit `a0ce0db2af8c84208dc2b8fe54e2eae15baa822f`, followed by
exact-byte recovery fix `6c5f94dddd88e185617f70568d4e089f711ab814`, on
`codex/standalone-sim`. Recovery inventory verifies9004 files/1,083,829,824bytes,
with no unresolved LFS pointers. Approved snapshots disable text normalization;
all three files' hashes match their exact Git blobs. This checkpoint precedes
the local aero study below.

`approved/2026-10-27/saved-profile.json` is the exact user-approved saved scene
library, including both throws' settings, hand/forearm keys, weapon grip/scale,
release tuning, camera, playback and undo history. Its manifest records SHA256
and capture time. Matching original big/small throw FBXs are beside it; their
hashes match the included animation cache. Render/collision caches and bundled
Jolt runtime are included, so ordinary lab playback needs no Unreal or FBX SDK.

To restore intentionally: close Throw Lab, back up any newer `state.json`, copy
this saved profile to `Labs/ThrowLab/state.json`, then launch the lab. The live
state remains ignored and is not overwritten automatically. Source re-export
tools still depend on the documented external FBX SDK/Stepper paths; launching
needs Python and Chromium as specified in `launch.ps1`. That Git checkpoint's
spear cache is the approved throw version; the current lab cache was explicitly
refreshed from the supplied FBX on October28 as documented below.

### Current editing behavior

**Hand continuity and whole-timeline detector (October29):** Partial Throw no
longer drops throwing-arm velocity at trigger entry or at the shortened stroke
end. Cached FK angular/offset velocity corrections carry through both joins.
The entry correction ends at the existing entry-blend endpoint; the return
correction fades over at most8frames and then exactly rejoins the existing FK
return. Corrections have zero value/velocity/acceleration at their endpoint.
This adds finite follow-through: current37%/.06 peak arc after release is about
36.28 degrees versus32.37 before. The charge endpoint and physical release stay
unchanged, as do launch velocity/twist, whole-frame user keys, head/body motion,
clavicle behavior,100% and Big Throw. No global smoothing/filter or worker.

`motion-audit.js` scans every bone over the full timeline at quarter frames,
adaptively refines velocity/angular-velocity discontinuities and distinguishes
smooth acceleration from jumps using shrinking probes. Source and retimed source
key changes remain reported separately. `verify-strength.mjs` runs18 charge/speed
cases and fails on unexplained procedural jumps; negative controls require the
old entry/return failures to be detected. Incoming hand velocity is also checked
at both joins. Original30fps source interpolation still has velocity changes;
the detector is a kinematic regression check, not a guarantee of visual quality.

Run `node Labs/ThrowLab/verify-motion-current.cjs` with the8893 service available
to scan a copy of the latest saved scene in an isolated headless viewer. It writes
Saved/ThrowLab/motion-audit-current.json and reports baseline/current/source
motion. It never writes live scene state or runs continuously during playback.
At37% it identified added jumps aroundF6.66 andF24.8796 (about2.27 and0.98m/s
respectively); both disappear after the fix. Full-cycle before/after captures:
Saved/ThrowLab/hand37-before/, hand37-after/, hand-return-comparison.png.
992 prefix/992 pose/12 launch,18 detector cases and isolated UI/Aim/Half/undo/
Refresh/velocity checks pass. Live presets preserved; Refresh loads the change.

**Clavicle correction (October29, clarified by user):** The user meant the
clavicles in the screenshot, not the spine. The preceding whole-torso early
unwind was reverted. Only clavicle_l and clavicle_r now release their retained
wind-up offset smoothly from trigger to the authored full-release marker.
The rest of the quadratic body layer, head and pelvis retain their preceding
behavior. Shoulder world-orientation compensation preserves the throwing
arm/elbow/wrist source motion while the clavicles relax underneath it.
Current37%,F20 left/right clavicle deviations from neutral:20.93/8.76 to
12.39/5.00 degrees;F26:19.13/8.20 to4.31/1.80. Full-cycle comparison to the
pre-misread version confirms head/spine/pelvis/legs restored within5.6e-16.
992 prefix/992 pose/12 launch and isolated UI/Aim/Half/undo/Refresh/velocity
checks pass. Head still has one forward/return. Receipt:
Saved/ThrowLab/clavicle-correction.json. Live presets untouched; Refresh loads.

**Quadratic body effort (October29):** Small Throw now scales remaining body
motion by charge squared:25% ->6.25%,50% ->25%,75% ->56.25%,100% ->100%.
This uses the existing coherent root/pelvis/spine/head/support-arm layer.
The causal wind-up, reached pose and incoming velocity remain preserved; their
residual uses1-charge-squared so the change does not pull the head backward.
Throwing-arm arc, release timing and launch-velocity multiplier are unchanged.
Numeric and isolated browser regressions pass, including the full43% head path,
100% identity, Aim/Half, native palm, physics, undo and Refresh. At43%, peak
head travel falls13.904 ->11.278cm and chest5.779 ->4.154cm;5% head0.841cm,
chest0.296cm. The earlier linear-body metrics below are historical. Live scene
state preserved; Refresh loads it.

**Small Throw velocity slider (October29):** Left panel Throw velocity slider
under Remove slowdown multiplies launch velocity at every Small Throw charge,
including100%. Range0-5x, step0.05, default1x. It shares the existing per-throw
speedScale/Amplitude value, so presets, copy, undo/redo, reset and Refresh use
one value. Numeric amplitudes above5 remain supported and expand the slider.
Only velocity magnitude changes; arm/body motion, release timing, direction
and twist remain.0% still drops at zero velocity. Big Throw is independent.
Isolated browser verifies slider input, single-gesture undo, redo/Refresh,
exact3x velocity at0/5/43/100%, unchanged pose/release/twist and changed Jolt
flight/replay. UI inspected in Saved/ThrowLab/small-throw-velocity-slider.png.
Live state preserved; Refresh loads the slider.

**Remove slowdown (October29):** Small Throw adds a0–1 slider directly under
Throw %. Default0 preserves the current slow stroke;1 plays the same shortened
source segment at1x source-animation speed. Intermediate values linearly blend
the rate: rate = baseRate + (1−baseRate)×slowdownBlend. The current resulting
rate is displayed. `slowdownBlend` is clamped0–1, defaults0 on old scenes, and
persists per throw/scene through copy, grouped undo/redo and Refresh. The control
is hidden with the Small Throw section when Big Throw is selected.

The forward stroke, arm-entry blend and physical release are synchronized with
the new rate. Trigger time and normal-speed wind-up remain unchanged. The source
segment, throw arc, body motion and configured launch speed/twist are
unchanged; this is an animation-speed control, not a global playback multiplier
or a launch-power slider. Actual release/Go to throw follows the earlier event;
authored full-strength markers and current-frame hand/forearm keys are retained.
No extra slowdown applies at100% throw. Zero-charge/degenerate strokes avoid a
division by zero and retain the existing drop behavior.

For33% with A18/R34, slider0/0.5/1 gives source rates0.19208/0.59604/1.0 and
release frames21.94/11.0961/9.0133. Numeric tests cover25 charge/blend rate cases,
source-speed and release-phase equality, unchanged prefixes and12 Jolt release/
replay cases. Isolated browser verifies actual slider input, linear midpoint,
unchanged strength, undo/redo/Refresh, held-to-release handoff and fast Aim/Half
with bomb/spear. Default behavior regressions pass. UI screenshot:
Saved/ThrowLab/slowdown-blend.png. No live-state edits or push; Refresh loads it.

**Small Throw charge (October29, source-pose rebuild):** Throw % controls the
forward arc, upper-body effort and launch speed.0–100/default100, saved per
throw/scene, undoable and retained on Refresh. Wind-up runs at normal speed,
exactly matching100% until trigger T=percentage×Armed, including Aim/Half.
No weaker pose is anticipated before trigger release.

**Armed-stall correction:** Partial throws select a start and end frame on the
original forward animation, then advance continuously through that segment.
The start matches the pose angle reached at trigger release; the end is Throw %
of the full forward arc measured from the actual frame0 shoulder-to-hand neutral
pose. The former per-frame angular remapping squeezed early movement into an
almost stationary pose near neutral. It has been removed. The angular lookup
now selects the segment endpoints only; source time progresses uniformly across
the stroke. Actual source elbow, wrist and palm roll remain together, with the
existing short FK entry blend. No synthetic arm-direction or wrist correction.

The saved33% setup (A18/R34) was reproduced in an isolated viewer from a copy of
state.json. Full-cycle images every two frames and quarter-frame traces were
captured before and after. Between playback F10–16, the old source advanced only
0.182 frames / arm angle1.945°; the corrected path advances1.152 frames /11.773°.
The forward clock now covers45.45% of its selected segment in the first10 of22
forward frames instead of lingering at armed. Regression checks cover the full
stroke at5/18/25/33/50/76/99%, not just boundary continuity. The neutral reference
is the actual held-arm pose;50% is about42.91° beyond neutral (approximately45°).

**Head/body reversal correction (October29):** The old time-based amplitude
fade is removed. In the user's saved43% throw, slowdownBlend0.06, A18/R34,
it pulled the already-reached head/body lean backward around F10.75-14.25,
then forward again. Zero derivatives at the blend endpoints did not prevent
this interior reversal; checking the joins alone was insufficient.

The normal-speed wind-up stays exactly original through trigger T=percentage
x Armed. After trigger, body rotations/translations retain the reached pose
and scale only the remaining authored movement by charge squared. A cached local-space residual
also preserves the incoming velocity, settling that residual velocity over
four frames. The body offset remains through the authored full-release marker, then fades
during recovery. Only the clavicle offsets unwind earlier as described above.
Body pose sampling stays on one original timeline. The same operation applies
to root, pelvis, spines, head, legs and supporting arm; there is no head-only
filter or per-render history. Low-charge body effort is reduced without pulling
completed wind-up movement backward. Consequently the total excursion is not
exactly Throw % of the full excursion: the causal prefix has already happened.

The throwing arm retains its existing cropped native source sequence and world
orientation compensation; source elbow/wrist/palm stay together. Its recovery
uses the body pose at the arm peak as its anchor. User hand/forearm keys still
apply afterwards at the current whole frame.0% holds neutral;100% and Big Throw
bypass the partial path exactly. Half retains its fixed lower body. The slowdown
slider still changes the arm clock/release together, not the body's clock.

At the default slowdown blend0, release is T+(Throw−Armed), with full-reference launch speed
multiplied once by charge. The source lookup slows the smaller swing while the
wind-up stays normal speed. At the reduced arm peak, that arm blends directly to the
ending while the body continues its original timeline. A18/R34.25 at50%: trigger F9, release F25.25, peak F31, about42.91° from
neutral.25/75% peaks are about21.46°/64.37°. The lookup is cached, quarter-frame
sampled and interpolated; no per-render search, extra loop or worker.0% holds
the reached upper pose and drops at zero speed.100% and Big Throw use the exact
original pipeline. Aim uses the existing partial-release solve after trigger;
manual twist, speed/direction tuning and editor workflow remain.

Verification checks992 causal-prefix and992 FK poses across Half/Aim and
0/5/18/25/50/75/99/100%, native whole-arm quaternions, neutral-to-full arc,
source progression,25 slowdown-rate cases and12 Jolt release/replay cases.
The43% regression traces the entire head path on both world-Z and the original
F8-to24 travel direction: no backward step during F8-24 and exactly one forward
to return transition over the whole cycle. Old world-Z reversals were at
F10.75/14.25/24; the corrected path has only its forward peak atF26.

Independent world head/chest/pelvis excursion and pelvis-rotation peaks increase
with5/25/43/50/75/100% charge and stay within the full throw's peaks.5% head
travel is1.679cm, chest0.705cm, pelvis0.207cm and pelvis rotation0.575 degrees.
The residual can briefly carry an individual supporting-arm joint beyond its
source angle (75% right forearm about0.72 degrees); no per-joint clamp is used,
and world body movement remains smaller. Original30fps key slope changes are
retained. New joins preserve velocity; this is not a blanket source smoother.

The exact saved43%/.06 setup was copied into an isolated headless viewer for
before/after full-cycle captures every2frames and quarter-frame head position,
head rotation and pelvis traces. Evidence: Saved/ThrowLab/head43-before/,
head43-after/, head43-before-after.gif and head43-comparison.png. Current
strength-verification.json and attack-browser-verification.json pass, including
Aim/Half, native palm, low-charge bounds, source clock, slider, undo/Refresh and
held-to-physical handoff. Existing818-pose/84-launch checks also pass. Isolated
sampling measured about0.24ms per pose. No extra worker or animation loop,
no live-state/Unreal edits and no push. Refresh loads the correction.

**Small Throw bomb default / current spear (October28):** Object choice is now
stored independently for Big Throw and Small Throw in `throwObjects`. Small
Throw defaults to Bomb, including migration from the old global selector;
Big Throw defaults to the sword/spear slot and retains an active legacy choice.
Explicit choices made after this update survive clip switches, scenes, copy,
undo and Refresh. Existing motion, launch, grip and scale settings are retained.
The existing bomb cache already is the exact UE5 bomb-feature mesh:
`/Game/Fab/CC0_-_Bomb/cc0_bomb/StaticMeshes/cc0_bomb.cc0_bomb`, from
`Tools/BombFuse/Geometry.json`. All1,799 vertices/2,622 triangles, including the
static curved fuse, match after coordinate conversion (rounding error<5.1nm).
Follow-up size correction: the saved UE5 `A_Bomb` mesh component has explicit
`RelativeScale3D=(2,2,2)`. The initial lab cache omitted this and showed an11.2cm
body instead of22.4cm. `prepare_objects.py --bomb-only` now bakes the component
scale around the shell centre into render and collision vertices, keeping the
hand offset and user's additional per-throw scale unchanged. The fuse scales
with it. `inspect_bomb_scale.py` reads and validates the saved UE5.7 tagged
component export without launching Unreal; unsupported layouts fail explicitly.
Source Blueprint hash/scale/provenance are stored with the bomb cache.
Backup: `Saved/ThrowLab/BombScale-20261028-223534/`. Geometry/size, projectile
attachment/release/collision/replay, attack and isolated browser checks pass.
Other weapons, live state and UE5 asset bytes remain unchanged.
Lab triangle colors remain simplified; this does not add the UE5 fuse/explosion
effects. The sword placeholder remains available with Imperial Spear unchecked.

Imperial Spear now loads the optimized supplied FBX, SHA256
`e1dbb2b1414c32d180d75d5c3214f0c667abe695647f250c1bf0962449ef6814`:
22,559 vertices/43,494 triangles,2.25223124m,17 authored UCX hulls. Importer supports
both direct and indexed per-corner UVs. Same atlas, bind and collision hulls;
sword/bomb caches and live saved state are byte-for-byte preserved. Backup:
`Saved/ThrowLab/WeaponRefresh-20261028-222819/`. `verify-weapons.cjs`, grip/contact
and818-pose/84-launch checks pass. Isolated browser on existing8893 verifies
Small Throw default, override/undo/Refresh, independent throws and current asset
hashes; all state writes intercepted. No Unreal/source asset edits or extra service.

**Attack mode (October28):** Half attack and Aim at target appear on the left
below the animation selector. Both default off, are independent per throw and
save with scenes/Refresh/copy. Each toggle is one undo step. With both off,
the previous pose and launch are restored exactly; existing presets are retained.

Half attack freezes root/pelvis/legs at the clip's frame0 pose. Spine_01
counter-rotates against the fixed pelvis so the upper body retains the normal
attack's world orientations, including the head and held weapon. Native upper
motion and current whole-frame hand/forearm keys remain active. Half mode alone
keeps the original configured launch vector/speed and axial twist, despite the
changed hand translation. Weapon grip/scale and release timing are unchanged.

Aim at target now uses the held sword/spear's forward shaft axis and actual
weapon origin at the exact Throw frame, including the current grip and
hand/forearm keys. The agent turns until the forward shaft ray passes through
the target; launch velocity no longer determines that orientation. Bombs retain
the original configured velocity compared with spine_05-to-target. Full mode
adds world-up yaw to the whole body around its starting root, with pitch spread
equally across spine_01 through spine_05; pelvis gets no added pitch/roll. Half
mode spreads the combined yaw/pitch across all five spines and keeps the lower
body fixed. A bounded cached two-angle fit accounts for the weapon origin moving
during articulation. No target solve while off and no new worker or animation loop.

With aiming on, frame0-to-Armed uses direct local-joint quaternion FK
interpolation into the aimed Armed pose, with a smooth quintic blend. Full mode
interpolates the full body; half mode retains the fixed lower body. After Armed,
authored motion continues with the full aiming correction. Armed0 applies it
immediately. Hand/forearm keys apply after this layer so they remain editable at
every whole frame. The release uses the actual corrected held pose and rotates
the original launch vector by the same complete chest correction, preserving
speed/twist and all stored edits. The preset angle between velocity and shaft is
retained; use Align velocity to spear to make them parallel. It does not add
ballistic elevation or home toward the target after release; gravity and existing
Jolt aerodynamics apply. Spear aiming works even at zero speed. A target coincident
with the held weapon leaves it inactive; bombs still require nonzero speed and
a target away from the chest.

`attack.js` owns FK/compensation/aiming; projectile reference measurement is
cached separately from the displayed pose. Snap-to-spear operates back in the
original preset frame and remains compatible with both modes. Numeric checks
cover818 poses/84 launch cases, both clips/all weapons, lower-body invariance,
world head/hand orientation, five-spine distribution, no added pelvis tilt,
fractional release/Armed continuity and cached Jolt replay. Actual isolated
browser clicks verify target updates, presets, snap, independent throws,
undo/Refresh and exact off restore. Tests: `verify-attack.mjs`,
`verify-attack-ui.cjs`; regression presets: `fixtures/attack-presets.json`.
Evidence is under `Saved/ThrowLab/attack-*`; live state and desktop untouched.
October28 shaft-reference update passes all818 pose/84 launch cases, including
forward ray intersection, zero/reversed-speed independence, fractional release,
preserved speed/twist and both full/half modes. Browser harness now asserts the
shaft direction and accepts an isolated test URL. The initial browser attempt
was blocked while8893 was down; the subsequent weapon refresh verified all of
these checks in an isolated browser against the available existing8893 service.

**Room brightness** is at the top of the left sidebar. The0-100% slider changes
the background/fog, floor and ambient light immediately; default40% gives a
lighter room, while0% restores the previous dark lighting. Saved per scene,
included in copy/Refresh and undo; one pointer drag is one undo step. It changes
rendering only and adds no loop or physics work. Isolated WebGL pixel/uniform,
undo/redo and Refresh checks pass without writing the live state file.

**Align velocity to spear** sits below the Launch velocity controls. It uses the
held weapon orientation at the exact Throw frame (including hand/forearm keys,
grip rotation and fractional release sampling), regardless of the current
playhead. It applies a shortest-arc correction to the existing root-relative
velocity angles, preserving speed/amplitude, twist, weapon pose, keys, timing,
camera and playhead. One Ctrl+Z step; pressing it again while aligned is a no-op.
This is a one-shot snap, not a persistent direction lock. It also works for the
sword placeholder, and is disabled for Bomb or zero animation-derived speed.

**Launch spin** is a separate section below Launch velocity. **Twist velocity**
sets signed degrees per60fps frame around the sword/spear's long axis at release.
Typing immediately switches off Use animation twist and updates the launch,
without needing Enter or blur. Zero gives no launch spin; negative reverses it.
Empty/incomplete input leaves the previous value intact. One focused editing
session is one undo step; per-throw values survive Refresh. Existing saved rates
and automatic mode are preserved until edited. Tests cover actual typed input,
grouped undo and ten signed/zero Jolt release cases across both weapons.

**Spear aerodynamics** is on by default for both throws and has a visible On
checkbox plus collapsed Tuning controls below Launch velocity. Air strength0-10x
(default1), pressure point0-50% of weapon length behind COM (default27%), and
additional sideways rotation damping0-10x (default1) are independent per throw,
undoable and saved through Refresh/copy. Turning off exactly restores the prior
flight. Bomb ignores these controls; held objects receive no aerodynamic load.
The pushed approved checkpoint and its saved profile remain untouched; these
implementation changes are local until another requested push.

`aerodynamics.js` supplies relative-airflow drag at an aft pressure point and
additional pitch/yaw damping. `projectile.js` applies force/torque before each
existing120Hz Jolt step, with no orientation overwrite or target seeking.
Point velocity includes `omega cross r`; longitudinal spin receives no direct
aerodynamic torque. Jolt retains gyro coupling, all rotational axes, CCD and
normal collision response. Air continues through active impacts and stops with
sleep, rather than forcing the spear to face its post-impact velocity.

Defaults use rho1.225kg/m3, effective lateral coefficient-area0.96m2 and axial CdA0.001m2;
areas and pressure distance scale with the current weapon geometry/XYZ scale.
These remain a reduced, uncalibrated model, not measured Imperial Spear data.
The initial lateral model was too weak: it used transverse speed squared,
giving only0.74degrees nose-down at F54 in the user's saved scene. Lateral
force now uses full point airflow speed times its transverse velocity, giving
a linear near-alignment response, with a coefficient tuned for short throws.
The first correction reached10.80degrees nose-down at F54. The user still found
alignment too weak on the subsequent saved throw, so the lateral response was
increased another4x (0.24 to0.96m2). With unchanged1x strength/27% pressure/1x
damping, the latest F62 case improves velocity-axis error11.54 to4.73degrees,
with14.29degrees nose-down. The original F54 regression now reaches16.96degrees
nose-down and4.59degrees error. Both saved cases are retained as test fixtures.
Air-off remains0.26degrees nose-up. No direct orientation lock or launch edit.
This is deliberate game tuning, not a claim of measured real-spear aerodynamics.
Effective mass/inertia bound drag impulses with an implicit response for small
weapons, high speeds and stronger tuning. All forces dissipate instantaneous
mechanical power; pure shaft spin is left free. Two reused WASM vectors and a
cached inverse-inertia matrix avoid per-step WASM allocations for these loads.
No worker, new animation loop or collision-hull rebuild. Cached seeks do not
apply forces again; changing aero parameters invalidates the flight cache.

Validation:16 rotated-root/antiparallel velocity alignment cases,81 dissipative
force/torque cases, both throws with spear/sword/bomb, exact aero-off and cached
replay, release continuity, maximum-control/small-scale finite contact cases,
and the existing grip/XYZ-scale/floor/target suite pass. Actual isolated browser
clicks verify snap scope, no-op, all tuning controls, bomb disabling, per-throw
settings, undo/redo and Refresh. Screenshot:
`Saved/ThrowLab/spear-aerodynamics-controls.png`. Tests:
`verify-aerodynamics.mjs` and `verify-aero-ui.cjs`; live state is not overwritten.
`fixtures/flat-spear-flight.json` and `verify-flat-flight.cjs` retain the actual
reported F54 regression and verify corrected rendered pose, exact settings,
camera,40 air substeps and Refresh replay. All force/contact/scale checks pass.
`fixtures/stronger-spear-flight.json` adds the subsequent F62 regression;
maximum-strength, small-scale and floor/target contact checks still pass.

Hold **Left Ctrl** while rotating the camera (orbit or free mode) or dragging any
rotation ring (hand, forearm, weapon grip or velocity) for30% angular movement.
Pressing/releasing it during a drag changes
only subsequent deltas, without a jump. Right Ctrl retains normal sensitivity;
translation and scale are unchanged. Physical-key tracking runs before the
active-drag shortcut guard and clears on blur/hidden window. No saved setting
or additional undo step. Focused checks cover all four rotation tools, mid-drag
transitions, side distinction, blur and edge-on tangent dragging.

Playback speed is limited to0.1-1.0x. The slider, input handler and saved-setting
normalization enforce the cap, including scene loads and undo/redo. Slower
speeds stay unchanged. Press Refresh to load this limit.

October27 whole-frame correction: the saved problem case contained25 forearm
keys across14 frames, including four conflicting subframe targets within F26.
These made playback repeatedly detour through different rotations and the
unedited integer defaults. Hand/forearm keys now migrate to nearest whole frames;
collisions retain the sample closest to that frame, preferring an existing whole
frame (equal distances use the last entry). Conversion is idempotent and also
applies to undo/redo and scene loads. Quaternion interpolation avoids Euler-wrap
spins. No independent subframe rotation targets remain. Numeric edits, Key here,
gizmo grabs, scrubbing and A/D all use whole frames; Armed also rounds. Throw
keeps exact fractional timing, including the sampled release pose and velocity.

Original state backup: `Saved/ThrowLab/BeforeWholeFrameRotations-20261027-150239/`.
The live state file was not overwritten; Refresh loads and normalizes the latest
saved edits. Weapon grip/scale, camera, target and throw timing are retained.
`verify-vanilla.mjs` covers the25-key regression fixture, integer-pose preservation,
1500+ interpolated samples, shortest-arc wraps and fractional Jolt release.
`verify-whole-frames.cjs` checks actual hand/forearm drags snapping before axis
capture, all displayed axes, numeric/Key here, Armed/A-D, Refresh and undo in an
isolated headless tab. It intercepts all state writes into session storage.

Refresh is green and centered on a second header row below New / Copy / Rename /
Snapshot. The original save-and-reload handler is retained. Header spacing keeps
it above the viewport camera buttons; isolated1280px/1000px layout checks pass.

Authored **big throw** and **small throw**, a flat floor, and a target fixed in
absolute world space unless explicitly edited. The first throw's root moves
about59cm; the initial camera AND floor followed that root, making the already
world-fixed target appear to move. Both camera anchor and grid are now fixed.

The **Vanilla throws** tab selects **big throw** or **small throw**, with separate
tuning for each. The left-hand selector offers **Spear (sword)** and **Bomb**;
the **Imperial Spear** checkbox replaces the sword placeholder with the supplied spear. **More options**
stays beneath the view buttons on the right for the frame summary/help.

The five gizmo checkboxes (forearm, hand, velocity, weapon grip and scale) are
mutually exclusive: enabling one unchecks the other four. Clicking the active checkbox
turns all gizmos off. Selection is one undo step and persists through Refresh.
Older saved states with multiple gizmos enabled keep one, prioritizing scale,
then weapon grip, velocity, forearm and hand. This normalization also applies on undo.
Other viewport checkboxes remain independent. No fields appear when selecting
a gizmo; all checkbox positions stay fixed at a given window size.

**S** hides/shows all gizmo overlays, including their readout and contextual
Reset button, while retaining the selected tool checkbox. Selecting a gizmo
explicitly shows it again. Visibility is saved per scene, survives Refresh and
is undoable. Typing, modified shortcuts, key repeats and active drags are
protected. Plain S takes priority over free-camera movement; **Shift+S** moves
backward. Focused shortcut and saved-state roundtrip checks pass.

Hovering or dragging a hand/forearm rotation ring appends the signed offset to
its existing right-side label, e.g. **FOREARM - LOCAL | Y +25.0 degrees** (the
UI uses a separator dot and degree symbol). No cursor-following box or native
rotation-axis tooltip remains. The axis-colored text updates live, follows the
displayed axis in forearm local or hand world/local space, and hides off-ring.
It measures the signed twist component of the offset about that axis, wrapped
to [-180,180); an undefined perpendicular half-turn is labeled undefined.
Hand default includes current forearm edits, avoiding double counting. No saved
state or layout change. Isolated hover/drag checks confirm label placement and
absence of native titles; screenshot `Saved/ThrowLab/rotation-label-readout.png`.

A single contextual **Reset hand/forearm/weapon/velocity rotation** button sits
inside the viewport below the playback status. It appears only for the active
rotation gizmo, so the checkbox row stays fixed; scale mode/all-off hide it.
Hand and forearm resets clear all of that joint's rotation keys across the
whole selected throw. Reset works even when the
current frame is unedited; it restores the joint's authored timeline. Weapon reset zeros only the current
weapon's grip rotation for this throw, retaining grip position and XYZ scale.
Velocity reset restores animation-derived direction only, retaining amplitude
and twist. The button label identifies the target; its tooltip states the scope.
Reset stays enabled even at default; clicking it then is a no-op and adds no
undo entry. Armed is only a pose marker: it never gates rotation editing or reset.
Hand/forearm editing works at frame0, before/at Armed and after Throw within
the animation. Reset pauses playback when changing a rotation, preserves camera/playhead,
and creates one undo step. Other throws/weapons/tuning stay unchanged; saved
state and history survive Refresh. No rotation resets occur until clicked.
Isolated mouse tests cover all four reset targets, exact unaffected settings,
no-op/visibility/layout, undo/redo and Refresh. Screenshot:
`Saved/ThrowLab/contextual-rotation-reset.png`.

**Show forearm gizmo** rotates the left forearm at the elbow using the
forearm's own current local orthonormal XYZ axes. This corrects the initial
upper-arm-relative display. The axes follow the edited forearm; each drag uses
the displayed axis captured at grab. It is on the usual viewport checkbox row,
with no additional fields. L only changes hand-gizmo space. Dragging pauses playback
and snaps to the nearest whole60fps frame BEFORE capturing the axis/base pose,
then keys `forearmKeys` there, independently per throw. Every unedited integer
frame uses zero offset (the original animation). Playback interpolates adjacent
integer-frame offsets with shortest-arc quaternion slerp. No additional subframe
targets, Euler-channel interpolation, gap bridging or last-key hold. This applies
to both hand and forearm. Only the
forearm and its descendants move; upper arm/body remain unchanged. Forearm
keys retain their parent-space storage for compatibility, preserving the
rotation at each explicitly edited frame. Mouse rotations about the forearm-local axes
convert back into that storage. Existing hand offsets apply afterward. The weapon follows the edited hand with its saved grip/scale;
release pose and animation-derived velocity incorporate forearm edits. One drag
is one Ctrl+Z step, and scene/Refresh persistence is retained.

User-requested hand reset: cleared the two saved big-throw hand rotation keys
at F26 and F27. No small-throw keys existed. Weapon position, rotation, scale,
launch/target settings, camera and playhead were verified unchanged. Backup and
receipt: `Saved/ThrowLab/HandReset-1793092569480/`. Exact-key-list guarded,
one-time repair prevents an older open app from restoring those keys on Refresh;
new different edits are protected. Reset itself is undoable. Source FBXs unchanged.
Browser checks verify all three forearm ring axes, fixed elbow/upper arm,
whole-frame keys, untouched other joints/hand keys/weapon settings/camera,
launch updates, Refresh and undo. Numerical checks cover both clips. Screenshot:
`Saved/ThrowLab/forearm-gizmo.png`.

**Edit scale** follows Edit weapon grip in the bottom viewport row. It shows
three colored local X/Y/Z handles with square tips. Scale is edited only by
the gizmo; the percentage inputs are removed so toggling does not move checkboxes. Drag a handle toward the grip to shrink only that axis, or outward to
enlarge it. Axes follow the weapon's current orientation; Z runs along its length.
Each axis allows10-200%, with100% the source size. Scaling uses the grip pivot
and leaves attachment position/rotation, camera and hand keys unchanged. Size is
constant across frames, independent for each throw and sword/spear, and saved
with scenes/Refresh. Turning off the checkbox hides controls without resetting
size. Ctrl+Z groups one handle drag. Previous scalar scales migrate to equal XYZ
values, including when restoring old undo history. This replaces the original
uniform handle/slider. L continues to affect only the hand rotation gizmo.
The collision shape, COM offset and inertia scale with the mesh; configured mass
stays1.2kg. Normals use inverse scale for correct shading. One Jolt scaled-shape
wrapper is owned by the current released body; no hull recooking or watchers.
Physics tests cover uniform and unequal XYZ sizes, release/replay/floor alignment.
Isolated browser tests exercise every local scale handle, confirm the other axes
are unchanged, and verify rotated weapon axes, mesh transforms,
undo/redo, independent sizes and Refresh. Screenshot:
`Saved/ThrowLab/imperial-spear-scale.png`.

**Imperial Spear** is the leftmost checkbox in the bottom viewport row.
**Edit weapon grip** remains after the hand/velocity toggles. Both are only
shown in Vanilla mode. They apply
to the sword/spear slot and are disabled while Bomb is selected. The grip toggle
shows both local translation arrows and rotation rings. Drag an arrow to move
along that weapon axis; drag a ring to rotate about its displayed local axis.
Both use the weapon's grip pivot and an orthonormal basis, with Z along the blade.
The axis is captured at grab, and playback pauses. L only changes hand-gizmo
space; weapon editing stays local. The attachment gizmo remains at the hand's
held-weapon pose after release; seek before Throw to inspect the held mesh.

Grip position and rotation are constant attachment offsets, independent of
per-frame hand keys. **Each throw has separate sword and spear offsets.**
Switching weapon/clip restores its offsets. Grip edits do not alter the hand,
its keys, camera or playhead; one drag is one Ctrl+Z step. Toggles/offsets are
saved with scenes and survive Refresh. Release simulation includes the complete
grip transform in its pose and COM finite-difference velocity. Twist remains
along the weapon's length; collisions can subsequently rotate it freely.

October28 spear refresh and grip correction: `prepare_spear.py` reads the
requested FBX with the existing FBX SDK, preserving all59,460 triangles/30,542
vertices, the grip pivot and2.252231m source length. The17 authored convex UCX
hulls form one Jolt compound body; decorative tassel geometry is excluded from
collision. Render colors sample the BaseColor atlas per triangle under existing
lab lighting; this renderer does not reproduce the full PBR material. Mass is
1.2kg, matching the placeholder. No source asset is modified. Refresh loads the
cache; importing is explicit, with no watcher or extra background process.
Current source SHA256:
`adebec94c106705a6db9b6628a54e8403734f145b507cfc521b12dc25e533668`.
The first import correctly matched the supplied FBX, but that file predated the
saved Blender grip movement and blade transform. A read-only source audit found
the leather/two keepers moved17.637cm away from the blade. Main FBX now reflects
those saved transforms, centred at the new grip; shaft/grip/blade hulls, sockets
and blade normals follow. UVs/colors/topology and protected geometry stay intact.
The lab matches the saved source to0.0001404mm, with saved settings/bind unchanged.
Audit/backups: `Saved/ThrowLab/SpearGripSync20261028/`; targeted preparation tool:
`Tools/SpearAsset/sync_grip_translation.py`. GLB/LODs remain outside this update.
Importer now measures length/counts instead of requiring the old nine-hull
geometry, preserves the existing spear bind, checks source/atlas stability and
replaces the cache atomically. Atlas stays uint8 during sampling to reduce peak
memory. Sword/bomb data, spear mass/axis/bind and saved state are unchanged.
Grip/scale/contact tests, aero regressions and both attack-mode suites pass.
New geometry exposed a near180-degree half-aim quaternion-log discontinuity;
spine yaw/pitch now distribute continuously, preserving equal angular shares.
Backup and receipts: `Saved/ThrowLab/SpearRefresh20261028/`. This refresh does
not certify or modify the separate Unreal/LOD export package.

To refresh from a later source:

```powershell
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Labs/ThrowLab/prepare_spear.py
```

`prepare_objects.py` now preserves the spear cache when rebuilding sword/bomb.
The sword cache is rigidly reframed into grip-centered weapon coordinates;
its default visible vertices agree with the original attachment within8.16e-9m.
`verify-grip.mjs` covers this preservation, both throws/weapons, constant offsets,
release continuity/COM velocity, cache invalidation, replay, shaft-only twist and
compound spear contacts. Tested final spear hull penetration reaches5.21mm.
Browser verification covers all three local movement and rotation axes, unchanged
hand keys/camera, grouped undo/redo, independent settings, visibility and Refresh.
Screenshot: `Saved/ThrowLab/imperial-spear-grip.png`. All tests use isolated state.

**Ctrl+Z** undoes edits; **Ctrl+Shift+Z** redoes them. Undo/Redo buttons sit below
the Vanilla throws tab. Shortcuts use the typed letter (`event.key`), so AZERTY
Z works even when its physical code is KeyW; physical KeyZ producing W is not
treated as undo. History covers clip/object selection, armed/throw frames,
hand keys and deletion, velocity direction/amplitude/twist, Animation reset,
gizmo visibility and local/world mode, target/radius, trim/loop, playback speed
and display toggles. One gizmo or trim/slider drag is one step; numeric edits
group while focused. The shortcuts also work from numeric fields, committing
and undoing the current edit. They are inactive during a live gizmo drag.
Undo pauses playback and retains the camera/playhead (clamped only if the
restored clip is shorter). Scrubbing, camera navigation, play/pause, snapshots
and scene naming/selection are not tuning edits and do not fill history.

Each scene retains its own undo/redo stacks through Refresh. Copy copies that
history independently; New starts empty. A new edit clears the redo branch.
Keep at most100 steps per stack and1MiB total history per scene, evicting oldest
entries as needed. Older edits made before this feature cannot be reconstructed.
No extra worker, timer or observer; history uses the existing save cycle.

User-requested October27 recovery: the saved big-throw F33 hand key was
`[0,0,31.113577207342754]`. Removed this single key to restore the authored hand
pose; all unrelated settings, camera, playback and scene data were compared and
preserved. Backup and verification receipt:
`Saved/ThrowLab/UndoRecovery20261027-1793081807665306700/`.
Ignored local `state-repairs.json` carries a scene/frame/exact-value-guarded repair
so an older open window cannot reintroduce it by saving during Refresh. Receipts
are kept outside undo stacks and preserved by scene saves. The repair consumes
once, does not remove different/new rotations, and does not create fake history.

Follow-up recovery: rolled back the next two saved hand edits using the actual
undo stack, restoring the pre-edit settings exactly and retaining both steps
in redo. Camera/playhead preserved; backup/receipt:
`Saved/ThrowLab/UndoAxesRecovery20261027-1793082518162/`. An exact-settings-guarded
history rollback in the local repair list also handles an old window's Refresh.

- **Armed frame** is a ready-to-throw pose marker, as clarified by the user.
  It does not spawn/hide the object or freeze playback. **Throw frame** releases
  the object. Only Throw accepts fractional values. Armed here rounds the
  playhead; Throw here captures it exactly. Go to armed / Go to throw seek
  exactly to their markers.
  Armed is bounded between0 and the throw frame; throw is within the animation.
- **Throwing hand rotation** edits local X/Y/Z degree offsets at Edit frame.
  Entering an angle creates/updates a key; Key here also records an unchanged
  pose. The key picker jumps between keys; Delete key removes the current key.
  Every unedited integer frame has zero offset. Playback smoothly interpolates
  neighboring whole-frame offsets using the shortest quaternion arc. No
  offset carries through unedited gaps or holds after the last edit. Rotation order is local
  X then Y then Z (`qx*qy*qz`). Only the hand and descendants rotate, about the
  wrist; other joints and source FBX/cache remain unchanged. Focusing an angle
  pauses playback and snaps to the nearest whole frame for editing.
- **Launch velocity** X/Y/Z rotate the animation-derived COM velocity in the
  character's root axes at release. Amplitude multiplies its magnitude, default1.
  The grip offset and edited hand motion contribute to that COM velocity.
  Zero offsets and multiplier1 retain the animation-derived launch vector.
- **Show hand gizmo** / **Show velocity gizmo** select mouse
  rotation rings from the bottom viewport row, after Two-tone, Bones and Free
  camera. These two controls and their overlays appear only while Vanilla throws
  is selected (off initially; visibility is saved per scene). **L** toggles the
  hand gizmo between **WORLD** (absolute X/Y/Z, the default) and **LOCAL** (the
  current hand's three orthonormal axes). The label and ring tooltips show the active mode;
  the choice persists per scene through Refresh. Switching preserves poses/keys.
  Typing in fields, modified shortcuts, held-key repeats and active drags do not
  toggle it. World rings stay independent of forearm/hand rotation; in either
  mode the center stays at the wrist. Left-drag a hand ring to apply that rotation
  and create/update a key at the nearest whole animation frame. The result
  converts back to the existing local offset keys, keeping prior keys compatible
  and choosing nearby Euler angles across wraps. Numeric fields remain local
  offsets; the velocity gizmo retains its existing root-relative axes.
  Local hand mode now applies a quaternion rotation around the displayed hand
  axis captured at grab, rather than incrementing an Euler channel. The previous
  Euler/gimbal axes were not an orthogonal local hand basis after edits.
  Ring selection uses closest projected geometry instead of SVG paint order;
  hovering highlights the ring that will be picked, including overlaps.
  Playback pauses on grab; hand/forearm editing snaps to a whole frame before
  capturing the drag basis. Camera stays fixed. The velocity
  widget sits at the object's release COM, with a yellow launch-direction arrow;
  its rings change the per-clip direction without changing amplitude or twist.
  Its origin remains at the throw frame even when inspecting another frame.
  The widgets remain visible over geometry and use different ring sizes so both
  can be enabled. Ring grabs capture the pointer until release/cancel, avoiding
  accidental camera orbit. Elsewhere, camera/target controls are unchanged.
  No overlay render loop or physics stepping is added; hidden widgets skip
  projection work. Gizmos are editing overlays, excluded from PNG snapshots.
- **Twist** is signed degrees per60fps timeline frame around the object's long
  principal axis (computed from the collision hull's inertia). All other launch
  angular components are zero. Use animation twist starts enabled and projects
  the animation-derived angular velocity onto this axis. Entering a value turns
  that checkbox off; zero stops launch spin. **Animation** resets direction,
  amplitude and twist defaults, retaining timing and hand keys. This controls
  the release seed only: subsequent collisions can produce tumbling on any axis.

All timing controls/readouts use the same zero-based60fps timeline. Scrubbing
lands on whole frames; stepping rounds the current frame then adds/subtracts
one. Continuous playback still blends smoothly. Release samples the
interpolated pose exactly at the requested frame, and starts the physics cache
there without snapping to the solver grid. Each scene retains both clips' keys,
armed markers, launch tuning and fractional releases through Refresh/copy.
Existing stored release/trim/playback timing is retained; legacy setups acquire
zero hand offsets, an armed marker at F0 and the new twist-only launch default.
Default release is the middle of each clip; no automatic aim or release solving.
Both objects follow the edited left-hand transform until release.

After release, one dynamic Jolt body uses the configured COM and twist velocities.
Gravity, rotation,
friction, restitution and collision with the floor/static target are simulated.
Mass defaults are1.2kg for the sword and0.6kg for the bomb. Convex hulls use the
rendered geometry; the bomb's fuse is decorative, not a separate physics body.
The agent remains authored animation without a collision body; no IK, aiming,
explosion, fuse ignition or fragments are implemented in this lab.

October26 sword-impact rotation correction (before the October27 launch controls): enable `mApplyGyroscopicForce` on
released bodies. Previously it inherited Jolt's disabled default, so free-flight
angular velocity retained a fixed direction after an impact (apart from damping).
All six degrees of freedom were already enabled; no rotational constraint or
rendering lock was present. The thin sword hull has about232:1 principal inertia
ratio, making the missing coupling especially visible. Shape, mass, damping and
release velocities remain unchanged. See the [Jolt setting](https://jrouwe.github.io/JoltPhysicsDocs/5.5.0/_body_creation_settings_8h_source.html).

The user's saved big throw at release F33 hit the target at F41 in the old
configuration. A controlled comparison retained identical states through F41,
then enabled gyroscopic motion: the rotation-axis direction changed about100
degrees between F42 and F54, versus effectively zero before. With the setting
enabled from release, impact occurs near F40 and that axis changes about92
degrees. Flight/contact outcomes can therefore change. Background numerical
evidence is in `Saved/ThrowLab/rotation-audit.json`; no user state was written.

180 extra timeline frames after the source animation allow flight/landing inspection;
the agent holds its final pose. Existing explicit trim bounds remain intact.
Simulation runs at120Hz with continuous linear collision detection and0.5mm
penetration slop, then caches results for deterministic backward seeking/loops.
New object/release/target settings invalidate the replay and rebuild it at the
existing playhead. Held/paused/sleeping objects do no physics stepping. One
dynamic body plus two static bodies; no character rig or inference is started.

Preserve the Bodyflip philosophy: incremental lab-first edits, user motion
review, root-local authoring when introduced, and keep existing controls in
place. Append new controls to the bottom of a section or right of a row.

The renderer, camera, recovery/FK math, styling, scene library and launch pattern
come from Bodyflip Lab as independent copies (`reuse.json`). Only the pure
`footFrame` geometry helper was extracted from its support solver. No shared
settings, server or live Bodyflip files are modified.

- Left drag orbits with Bodyflip's inverted X/Y mapping; middle drag pans;
  wheel zooms; double-click or View resets. Front/Side/Top presets retained.
  Orbit tilt now reaches nearly straight down/up (89.94 degrees), replacing the
  old roughly42-degree downward stop. Vertical dragging preserves eye-to-target
  distance; a tiny pole margin prevents inversion. Existing saved camera poses
  retain their representation and restore unchanged. Zoom remains usable at
  steep angles. Focused background checks cover both limits, distance, finite
  camera bases, restore, zoom, free-mode transition and reversible dragging.
  Free camera uses Q/Z/Shift+S/Shift+D; plain S toggles gizmos and D advances the timeline. The default view uses a fixed world anchor to frame
  both the character and the target, independent of animation root translation.
- Right drag moves the target in the view plane; Shift moves it in depth.
  XYZ fields use metres, Y up, matching the Bodyflip lab convention.
- **Whole frame**, beside the footer frame counter, pauses and snaps the current
  playhead to the nearest integer60fps frame (halves round upward). A one-shot
  navigation action: fractional throw timing remains available, existing rotation
  keys/settings stay unchanged and no undo entry is added. Refresh saves the
  snapped playhead normally.
- Space plays/pauses; A/D or Left/Right arrows step one60fps frame; R resets to trim start.
  Scrubbing is immediate. Drag timeline brackets to trim and enable looping.
  Playback speed changes playback only. Authored samples remain at 30 Hz.
- Changing controls retains the playhead where the selected clip's frame range permits.
  Each clip retains its own trim bounds. Two-tone and Bones displays retained.
- Refresh saves the complete setup, camera, exact playhead and playing state before
  reloading uncached code. Pending saves cannot overwrite the refresh snapshot.
  New/Copy/Rename scenes are independent from every other lab.
- Snapshot saves a PNG and setup/source identity under `snapshots/`.
  Settings are local in ignored `state.json` and never overwritten by tests.

## Animation sources

Both FBXs are read from:
`C:/Users/singerie/Documents/Cursor/stepper/ue5/slashes/recoveries/`.

| Clip | Original samples | Rate | Timeline frames (60 fps) |
| --- | ---: | ---: | ---: |
| big throw.fbx | 66 | 30 Hz | 0–130 |
| small throw.fbx | 35 | 30 Hz | 0–68 |

The user replaced the mistaken nine-frame **big throw 2** and deleted its FBX.
The fresh **small throw** is now the second clip; saved selections of the retired
clip map to small throw, while its old trim/release values are not carried over.
Keep the two current sources exactly as exported; do not substitute the earlier
Mixamo originals or stretch the authored clips to fill the flight tail.
`export_clips.py` reads via the existing Autodesk FBX SDK; original FBXs are
unchanged. The cached `data/clips.json` contains source paths/hashes and the
Bodyflip display bones' global poses in Y-up metres. Playback uses parent-local
quaternion interpolation. Only each clip's initial horizontal root offset is
subtracted to place it at the lab origin; all subsequent authored displacement,
timing and joint motion are retained. No retargeting or motion correction.

`prepare_objects.py` builds `data/objects.json` from the cached Bodyflip sword
and `Tools/BombFuse/Geometry.json` (the original `/Game/Fab/CC0_-_Bomb` mesh).
The existing right-hand sword grip is transferred to the left using a proper
180-degree local-Z rotation, without mirroring the geometry. The original bomb
is converted from UE centimetres to lab metres and placed in the left palm.
Source hashes are embedded; materials are simple lab colors. No Unreal export,
asset save or source geometry edit. `vendor/jolt.js` is the unchanged Bodyflip
Jolt1.1.1 module with a `.js` suffix so the existing server serves correct MIME;
license/provenance are included. No service restart needed.

To incorporate a later edited FBX, run the exporter with the existing runtime,
then press Refresh. This explicit import avoids watchers and repeated FBX work:

```powershell
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Labs/ThrowLab/export_clips.py
```

## Verification and current service

`node Labs/ThrowLab/verify.cjs` uses a temporary headless browser with all state
writes intercepted into session storage. It closes the owned browser afterward.
It checks both current clips, source-keyframe fidelity, fixed camera/target,
left-hand objects, frame-only controls and bounds,
scrubbing, release at playhead, reverse replay, frame steps,
paused/playing Refresh, looping, scene copy/new, camera modes, and smaller layout.
It also checks whole armed/fractional throw values, hand key creation/deletion,
launch edits, exact Refresh restoration and independent per-clip tuning.
Mouse tests drag every hand axis and the velocity direction ring using native
headless-browser pointer events; verify whole-frame keys, camera, amplitude,
twist, hiding both overlays and Refresh persistence.
World-axis follow-up additionally verifies that each hand drag changes the world
pose around only the selected axis and leaves the rings fixed, plus numerical
round-trips through rotated arm bases, full turns and Euler singularities.
Keyboard checks cover L in both directions, unchanged poses, local ring editing,
typing/modifier/repeat guards and persisting the local mode through Refresh.
Follow-up mouse checks verify all three local normals are orthogonal and each
hand's world rotation delta aligns with the selected displayed normal. An overlap
case deliberately places another SVG hit path above the intended visible ring;
the nearest ring still wins. Keyboard checks exercise both QWERTY and AZERTY
Z/Shift+Z and confirm physical KeyZ with typed W does not undo.
Undo checks cover grouped drag edits, field/selector/toggle/reset/delete changes,
Ctrl+Z/Shift+Z, focused inputs, unchanged camera/playhead and Refresh persistence.
`node Labs/ThrowLab/verify-history.cjs` checks grouped history, redo branching,
storage bounds, scene-copy persistence and the guarded one-time state repair.
Screenshot: `Saved/ThrowLab/rotation-gizmos.png`. Tests intercept saved state and close their
owned browser. Refresh testing exposed intermittent `ERR_CONNECTION_REFUSED`
on parallel script requests; `boot.js` now loads dependencies sequentially to
avoid that burst against the existing small server. No server/app restart needed.
101 source samples reproduce their stored positions with maximum numerical error
6.8e-16 m. Screenshot checks cover both throws and 1000x700/1280x900 layouts.
`node Labs/ThrowLab/verify-vanilla.mjs` checks all four clip/object combinations:
fractional release continuity, rotation-key interpolation, untouched other bones,
root-relative velocity rotation, amplitude, twist-only/zero-spin seeds, cache
invalidation, reverse replay and scene persistence. These run in one short-lived
Node/WASM world; launch preview is cached and never steps physics.
`node Labs/ThrowLab/verify-projectiles.mjs` retains the original unfiltered-launch
physics regression for all four clip/object cases:
left-hand attachment, continuous release, inherited COM/angular velocity,
reverse seeks, finite results, ground contact, gravity against a reference,
sleep retirement and target collision versus an unobstructed launch. The F33
sword-impact regression checks changing rotation axis, free degrees of freedom,
landing and exact reverse replay. Largest final tested hull penetration0.71mm;
authored release/target configurations
outside these cases are not exhaustively validated. Receipts/screenshots under
`Saved/ThrowLab/`. No user desktop takeover or live-state overwrite. Refresh
loads the current changes; no Unreal interaction was needed.

Initial service PID21604 on8893; desktop shortcut installed. Treat the PID as
historical and check `/health` for current service identity. The launcher starts
the service when needed; it does not restart other labs or Unreal. The initial
service setup was local; the approved October27 checkpoint above is now pushed.

## Spear aerodynamic investigation - October27 (pre-implementation evidence)

The approved checkpoint's Jolt integration has gravity, collision/friction/restitution, inertia,
gyroscopic coupling and angular damping, but no aerodynamic force. Damping
cannot steer the nose toward velocity by itself. The approved Imperial Spear
releases at F34, at0.1692m/frame, with17.10degrees between its nose and travel
direction. COM-to-target distance is2.61m; scaled length1.676m, mass1.2kg,
longitudinal spin7.528degrees/frame. Geometry and release were read from the
approved profile/cache, not the independently evolving Unreal spear asset.

Recommended mechanism: forces from relative airflow at one or several pressure
points aft of COM. At each existing120Hz Jolt step, use local point velocity
`u = vCOM - wind + omega cross r`, split into axial and lateral components, and
apply opposing drag. An aft application point gives `torque = r cross force`;
using point velocity also damps sideways rotation. Keep roll/twist free, preserve
gyroscopic coupling and contacts, and stop work when sleeping. No target seeking
or orientation overwrite. Reuse WASM vectors; no worker or mesh recook needed.
Both `Body.AddForce` and `Body.AddTorque` exist in the actual bundled module.

This is a reduced aerodynamic model needing asset-specific area, drag and
pressure-point calibration. NASA describes the restoring effect of pressure
behind the center of gravity in [Rocket Stability](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/rocket-stability/),
and the distributed pressure basis in [Center of Pressure](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/generalized-center-of-pressure/).
Real javelin moments are more nuanced: the [2023 magnetic-balance study](https://www.nature.com/articles/s41598-023-27534-2)
reports nose-up moments below12degrees for its tested design. Thus a decorative
spear cannot be assumed to align perfectly from geometry alone. The [Jolt API](https://jrouwe.github.io/JoltPhysicsDocs/5.1.0/class_body_interface.html)
provides the required force/torque integration.

An isolated, workerless feasibility probe used the approved launch with target
moved away and floor lowered, so results describe free flight, not impact accuracy.
Assumed rho1.225kg/m3, lateral CdA0.04m2, axial CdA0.001m2, pressure point0.45m
behind COM. Lateral force used `-0.5*rho*CdA*|uSide|*uSide`. These parameters are
uncalibrated assumptions, not measurements of this spear. At12 flight frames,
axis/velocity error was24.15degrees with no air versus23.32degrees with aft air;
at30frames35.72 versus29.91; at60frames50.38 versus20.84. Moving the point forward
instead destabilized it (101.55degrees at60frames). Multiplying lateral CdA by6
improved alignment sooner, but is stronger gameplay tuning, not validated realism.
Natural alignment takes time and can lag a curved trajectory; this short throw
may show only a small correction. Added air also changes trajectory, so replay
both approved throws and check contacts before enabling it in the app.

Evidence: `Saved/ThrowLab/approved-launch-analysis.json` and
`Saved/ThrowLab/AerodynamicsStudy/{run.mjs,probe-projectile.mjs,results.json}`.
Study files remain local. The subsequent authorized implementation is described
under Current editing behavior above; approved checkpoint physics remains intact.
