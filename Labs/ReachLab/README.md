# REACH — Hand & Body Lab

Dedicated local workspace for reach experiments before an explicitly requested
Unreal port. Open **REACH - Hand & Body Lab** on the desktop, or run `launch.ps1`.
Address: **http://127.0.0.1:8873/reach**. Lime hand / purple target icon; visible Edge
app window and a separate hidden localhost server. Works without Unreal running.
The dedicated `/reach` path keeps its taskbar group separate from D/S: Chromium's
URL-app identity uses host and path, ignoring the port. Keep this path in the
launcher. The root URL still works in an ordinary browser. The ICO favicon supplies
the running window's distinctive icon; no persistent Windows helper is needed.

## Controls


**Elbow posture:** the explicit outward/down bend now controls grabbing too,
including after grip. Blend0 uses the outward policy;1 favours a lower elbow.
Wrist twist fits the imported PHAT independently, so it cannot turn a straight
forearm's undefined bend into a full orbit. Body reach extent has its own cached
plan. Feasible twist intervals have a fast path when the current twist still fits.
Refresh preserves pose/grips/settings; Codex does not refresh the user window.
Old inward poses correct from their current position at the normal bounded speed.

Current checks: `test_elbow.cjs`, `test_wrist_twist.cjs`; evidence and limits in
`Saved/Diagnostics/ReachElbowDesign20261016/` and the current reach topic. The
reported blend0 fixture now has44/70deg total left/right swivel instead of224/363,
both outward and aligned. All five blend values0..1 and live changes are checked.
`UE_Elbow_Circling_Recorded` remains the exact earlier run91-260, with frozen inputs
after260; current grabs142/145. Accepted solver is now ported and loaded in Unreal;
600 native numerical cases pass. The subsequent physical-grip feedback experiment
is described below; lab settings were preserved.

**Current grab behavior:** at the user's request, ordinary grips again capture
the achieved wrist. Unreal follows the moving object's surface and orientation
after acquisition, as before the feedback correction. The agent-relative hold
was rejected because it changed ball movement. The explicit elbow/wrist solver
remains. Earlier physical feedback circling is therefore still an open issue.
No automatic Refresh, reset or service restart; current saved grips are preserved.

**Historical held-object feedback experiment:** after your Refresh, select
`UE_Grip_Feedback_Before` or `UE_Grip_Feedback` in the snapshot list. Both start
from the captured TestNN tick120 pose and contacts. The former feeds the attached
ball's response back into the reach goal; the corrected case keeps the authored
hold independent. This is a closed rigid-transform model of the feedback, not a
Jolt force/collision simulation. It reproduces excessive motion without Unreal.
Right swivel over480 steps:499.6deg before,1.28deg with the independent hold.
The late captured right target remains19deg away under PHAT; the experiment
verifies removal of drift, not fresh acquisition of that already-degraded goal.
Ordinary lab defaults still acquire both balls with four contact fingers and zero
terminal error. `test_grip_feedback.cjs` also checks drag/blend changes, stationary
settling and that output disturbances cannot rewrite the command.

The corrected experiment uses the same requested hand/object relationship as
the grasp goal. Its authored target is independent of ball motion. This attachment
is now limited to that historical experiment; ordinary grabs use the achieved
wrist again. Restart preserves user target offsets without treating
the old runaway ball motion as a new user offset. Snapshot/restore is deterministic.
`test_grip_attachment.cjs` and `test_feedback_workspace.cjs` cover the relationship
and workspace behavior. The rejected Unreal correction retained the hold in
agent coordinates so the character carried it. Its earlier physical TestNN
verification passed: both grips through720, right total swivel
57.84deg and only.004deg after300 (previously479.71deg through360). Held commands
have zero drift; runtime blend changes also settle and retain both joints.
That blend test retains1.19cm left requested-wrist error; it verifies stable
holding, not exact arrival for every held pose. These are historical results,
not current behavior. See the current reach topic and
`Saved/Diagnostics/ReachGripFeedback20261016/` for the experiment, and
`Saved/Diagnostics/ReachGripRestore20261016/` for its requested rollback.

The following scenario notes describe their historical introduction; current
measurements and remaining limitations are in the current reach topic.

The TestNN right-hand failure is available in **Snapshots & settings** after
Refresh. Select **TestNN_Right_Recorded**, then **Play**. Both hands, actual targets,
7.5cm right ball, fitted fingers, wrist limits and native solver history are imported.
The native neural base and root-relative goal motion advance from absolute31–360;
the reach/body algorithm solves them live. Inputs freeze afterward. The original
lab replay reproduced the native non-grab at1.19cm/10.20deg within1e-6cm. The current
lab correction now grips right at tick86 and left111, with smooth left-elbow tracking.
Targets remain draggable; Restart preserves edits as offsets to the recorded path,
plus checkbox/tuning settings. Snapshot/Refresh resume the captured sequence.
**TestNN_Right_Stalled_250** freezes the stalled checkpoint for local experiments;
the corrected solver follows its planned approach and grips after46 further ticks without resetting.
**TestNN_Right_Frozen_Start_31** is the comparison that grabs: the missing root-relative
target motion explains its success. Restoring an ordinary snapshot returns to the
normal idle base. Each grab selects its forearm approach once and follows it
immediately. Moving targets transport the same approach, with no stall timer or
fallback strategy. PHAT, contacts and user angle gates still apply. At most two
wrist projections/hand/frame; initial planning is cached. Moving only the floor root point has no
effect; coordinate translation also preserves the solve. This correction is lab
only and has not been ported to Unreal. These cases do not add live physics; recorded held-ball paths are
inputs, and the lab's own grab attachment remains kinematic. Detailed evidence and
controlled comparisons: `Saved/Diagnostics/ReachScenario20261016/` and reach topic doc.
Current correction tests: `test_plan.cjs`, with evidence in
`Saved/Diagnostics/ReachPlan20261016/`. Older escape receipts are historical.

Live recording data is stored once in `motions/<sha256>.json`, referenced by
`motionRef:{id,startTick}` in compact live/session files. Read it through
`/motions/<id>.json`; `/session` expands it for exact resume. Explicit snapshots
and exports still include the entire motion. This avoids formatting megabytes of
unchanged recording data every1.2s during playback. User Refresh loads JavaScript
changes; Codex does not automatically refresh the visible lab.

- Left/right **Reaching** checkboxes independently enable the hands.
- **Grab ball** enables palm targeting, fitted fingers and acquisition for that
  hand. With it checked, XYZ describes the **ball centre**; unchecked, XYZ is
  the wrist reach destination. **Ball radius**, a shared slider directly below the top-bar clamp checkbox,
  resizes both balls together from0.5 to15cm. Resizing releases/refits the grip on the next simulation tick.
  Both new grab switches initially default on, with3cm balls.
- A **gold dot** marks the selected surface contact reference on each active
  grab ball. Its short gold arrow shows the outward surface normal. The reference
  follows the held ball's translation and rotation, and appears in snapshots.
  A cyan point shows the achieved effective palm reference (including the fitted
  clearance and contact padding), with a line to the gold surface target.
  These diagnostic markers use scene depth; nearer body/ball geometry occludes them.
- **Right-drag a coloured ball** to move that hand target in the camera plane.
- **Shift + right-drag** moves it toward/away from the camera.
- Left-drag orbits; middle-drag pans; wheel zooms. Front/Side/Top/Perspective views.
- XYZ positions in centimetres and per-hand reach/rotation speeds. **Absolute
  rotation** sets hand orientation in the fixed lab coordinate system using XYZ
  degrees (`qZ * qY * qX`). Zero/zero/zero aligns the hand bone axes with the lab
  axes; it is independent of idle pose, target position, arm movement and camera.
  PHAT still constrains the actual wrist. Follow arm uses the body solver's natural
  hand orientation for reach-only. The shared **Auto palm contact** checkbox in
  the top bar switches both hands together; unchecking restores their saved
  absolute rotations. Automatic mode hides the per-hand manual orientation
  controls. It now chooses the sphere surface toward the same-side upper-arm
  bone origin (`upperarm_l` / `upperarm_r`, at the shoulder), using the full3D
  direction from the ball centre. That normal and the upright palm orientation
  are captured once when starting a grab; they do not track later bone motion.
  This lab experiment replaces the native palm-centre reference. After refresh,
  existing automatic grabs refit on the next tick through a versioned contact key.
  **Absolute rotation** preserves the existing world-angle controls and selects
  the sphere contact on the facing side of that palm. Changing orientation refits
  the grasp; translating a ball preserves its contact and fitted curls.
  Settings schema2 converts earlier idle-relative angles once,
  preserving their intended orientation and every other setting.
- **Sync rotation**, shared0..1 slider at the top of the right panel:0 preserves
  the existing angular pursuit;1 slows it to finish with the estimated reach
  arrival. It blends between normal angular step and the smaller step derived
  from remaining wrist distance / reach speed. Each hand uses its own distance
  and speeds. Rotation speed remains the maximum; PHAT/body constraints or a cap
  too slow for the reach can delay final alignment. Recomputed from current pose
  every tick, so dragged targets and resumed snapshots need no timer/history.
  Follow arm in reach-only bypasses synchronization. `settings.syncRotation`
  persists through saves/reloads/snapshots/reset/restart; older settings default0.
- **Elbow down blend**, directly below Sync rotation, scales the native elbow
  preference from0 (original outward rule) to1 (current lower-elbow rule).
  Default1 preserves existing behavior; `settings.elbowDownBlend` persists in
  settings and snapshots, including reset/restart. It is passed per request,
  updating the explicit grab elbow pole as well as ordinary reach. Wrist twist
  is fitted separately within PHAT; impossible orientations remain constrained.
- **Reset pose & targets** resets the body pose, grab state/tick and saved target
  translations/rotations only. Every checkbox is preserved, including Reaching,
  Grab ball, Auto palm contact, Clamp hand rotation, Skeleton and Wrist axes.
  Radius, speeds, tolerances, camera and playback settings are also retained.
- Small reset icons on the right of each translation/rotation group restore only
  that hand's group. User-captured defaults: left translation **13,60,125cm**,
  rotation **180,0,90°**; right translation **−14,47,125cm**, rotation **0,0,−90°**. `reset_defaults.json` is the
  durable baseline; ordinary edits, snapshots and imports never recapture it.
  `/reset-defaults`, `/state` (`resetDefaults`) and the live view expose it.
- **Restart**, immediately left of Play/Pause, resets the pose, grabs and tick
  to the beginning and starts playback using the current targets and tuning.
  Checkboxes, camera and playback speed are preserved.
- Pause/Space, Step/Right Arrow, ¼×/½×/1× playback. Fixed60Hz authored steps;
  renderer FPS does not alter the solver's delta. The tab suspends when hidden.
- **Clamp hand rotation**, centered in the top bar, enables/disables the imported
  PHAT wrist clamp for both hands. Checking or unchecking it releases both balls
  and restarts grabbing for enabled hands from their **current wrist positions
  and rotations**, preserving body response and elbow state. Contact and finger
  fitting are recomputed; disabled hands stay disabled. There is no idle-pose
  reset or tick reset. If paused, motion continues when played or stepped. Its setting persists through saves, snapshots
  and refresh. Snapshot/Refresh sit at the top left, in the former title position, with Reset pose & targets
  beneath; the header has no branding. The panel shows wrist target error,
  closure progress, rotation blocking and **Held** status, plus fitted finger
  contact count and open-hand clearance. **Closure angle** and **Grip angle**
  sit in a fixed section below the scrolling sidebar, always visible. They apply
  to both hands and persist; defaults8°/6° match Unreal. Closure needs<3cm;
  acquisition needs full closure,<1.25cm and the grip angle. Unreal additionally
  checks its actual hand (<2cm and the same grip angle); here actual and commanded
  hands coincide because the lab is kinematic.
- **Snapshot** or **P** writes numbered JSON+PNG files under `snapshots/`.
  **Snapshots & settings** restores snapshots and imports/exports JSON. Restore
  pauses at the exact saved pose, including all26 bones, solver/hand/return state,
  both grab states, fitted curls, closure, held-ball transforms and attachments,
  target settings, camera, view controls and PHAT/source provenance. Resume uses
  that saved solver state. Legacy timestamp-named cases remain listed/restorable.
- **Refresh lab** saves pending edits and the exact pose, camera and playback
  state before reloading the code. The desktop session also persists periodically
  to `session.json`, so reopening restores the most recently shared pose/view.
- Settings save to the lab's `state.json`; no Blueprint or Unreal tuning is written.

## Live inspection and capture

The D/S snapshot/list/restore/refresh workflow and desktop identity were adapted;
its `capture.js` and `capture-worker.js` were copied and adapted for REACH's shared
`reach-renderer.js`. PNG capture runs in a worker (640px preview while playing,
full viewport when paused or taking snapshots). Source hashes: `reuse-receipt.json`.
No D/S files are changed.

Open through the desktop shortcut to register the writable desktop session. Other
browser tabs are inspection views: they cannot save or replace the desktop feed.
`GET /desktop-view` returns the exact pose, settings, reset defaults, camera,
client/sequence, runtime errors, fingerprint and PNG hash. Fetch
`/desktop-view.png?sequence=<sequence>` for matching pixels;409 means reread the
view. These are also persisted as `current_view.json` / `current_view.png`.
`/current-view` remains the JSON compatibility endpoint. `/snapshots` lists durable
names; `/snapshots/<name>.json` and `.png` read each pair. No computer-use tool is
needed for these diagnostics. This online solver has no precomputed future
trajectory; its snapshots contain exact current state for deterministic continuation.

Both hands off returns the body to idle over15 authored ticks, then stops solver
requests entirely. Disabling one hand performs a parent-local arm return while
the other continues reaching. The lab return wrapper is independent from the
native reach overlay; the native body/arm kernel is shared by source extraction.

## Unreal port status

The user authorized the reach/grab port on October16. The native editor pipeline
now includes the accepted elbow preference/blend, rotation sync, shoulder-selected
automatic contact, coupled wrist/arm correction and arm-first body compensation.
See `Docs/ReachGrasp20261012.md` and `Saved/Diagnostics/ReachPort20261016/` for the
120 numerical cases and owned Kin/Sim grasp checks. Existing editor explicit points,
speeds, physical admission and loaded PHAT remain authoritative. Lab controls and
saved tuning are independent; subsequent lab changes still need explicit porting.

**October16 elbow hitch follow-up:** coupled elbow/roll search steps now shrink
with remaining quaternion error near alignment. Full step sizes remain above8deg;
the18-evaluation cap is unchanged. This fixes the native settled-grip coarse-step
hitch; mirrored lab837-frame regression passes. Evidence:
`Saved/Diagnostics/ReachElbowHitch20261016/`. User refreshes the lab manually.

## Solver and scope

**October16 elbow preference (installed and verified):** only
`PreferredBend` changed. Forward directions with Y>=0.65 now use70% relaxed elbow
preference, smoothly increasing to100% for side/back reaches at Y<=0. The relaxed
direction is projected down with a small outward bias. This supersedes retaining
the old outward-heavy forward rule. The blend fades to zero near vertical. It stays on
the same feasible elbow circle and adds no search, iterations or solver state.
The Elbow down blend slider now scales this addition, with1 matching this rule
and0 matching the original outward preference exactly. Evidence for the slider:
`Saved/Diagnostics/ReachElbowBlend20261016/` (960 endpoint-comparison frames,
intermediate blends, clamped grips, request wiring and persisted UI checks).
This is a small direction-dependent heuristic inspired by VRArmIK's posture
selection, not a port of that solver or an anatomical-limit guarantee.
Unreal source, grip logic, PHAT clamp and body algorithm are unchanged.

The earlier fixed-preference candidate and installation evidence are at
`Saved/Diagnostics/ReachForwardElbow20261016/`; the adjustable version supersedes it.
After the user's explicit "run it", `install.ps1` restarted only the Python REACH
service, preserving the registered browser session and settings. A transient DLL
lock required a bounded100ms copy retry. The installed DLL hash matches the tested
candidate, and stateless HTTP replay matches the local native solver exactly;
`delivery.json` records the verification. Earlier approval blocks are resolved.
The browser was not launched/refreshed. The user should Refresh to pick up the new
dataset fingerprint and press Play if the service interruption paused playback.

`solver.inl` is an editable, lab-owned snapshot of the complete numerical
`ProphecyDoubleReach` core and `ProphecyNativeReach::Step` extracted from
`Source/GameAnimationSample3/Private/ProphecyDoubleReachAnimInstance.cpp`.
Initial source SHA256:
`a67eef345dd062a62205b22361d18018c2b107d4e49176f35509f17079610183`.
Pelvis drop/shifts, distributed spine rotations, shoulder girdle reach, balance
feasibility, bilateral refinement, target pursuit, elbow projection and foot
anchoring execute that C++ code. `math_compat.h` supplies standalone double
precision vectors/quaternions/arrays; it is not linked to Unreal.

Input is the actual neutral idle frame0 already exported for the D/S lab, reordered
to the native26-bone layout. Unreal numerical XYZ cm are converted only for display.
Existing D/S renderer and quaternion helpers are served read-only. D/S files and
accepted settings are untouched.

`wrist.js` ports the current PHAT quaternion projection. `phat.json` contains the
loaded PHAT wrist frames, endpoint order, angular modes and bounds exported on
October16 after the user's manual PHAT edits: both wrists60/45/90degrees in
twist/swing2/swing1 order, all LIMITED, with unchanged constraint frames.
The server's exported JSON was verified; the user performs Refresh to load it
into the existing browser. No asset save or build was performed by the importer.
Before/after: `Saved/Diagnostics/ReachPHATImport20261016/`.
This is a snapshot, not a live editor connection. To refresh it while
Unreal is open (read-only, no build/save/Play changes), run from the project root:

```powershell
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/RunUnrealRemote.py Labs/ReachLab/export_phat.py
```

Then refresh the lab. The exporter uses a transient isolated fixture and the
existing `Prophecy.Robotics.ExportRig reach-lab.json` command.

`coupled.js` couples arm solving to the wrist clamp for active grabs. A bounded
forearm-roll search projects candidates through the wrist constraint with the
hand fixed, choosing the allowed direction closest to a straight reach. This
look-ahead asks whether the elbow can fit within upper-arm length before requesting
body help. `app.js` lets ordinary positional pursuit catch up, subtracts the
shortfall already handled by positional reach, and feeds back only the additional
orientation shortfall. Excess compensation decreases again; it does not persist
just because a grip succeeded. The existing native body algorithm receives an
adjusted radial wrist request and still controls balance, legs and body motion.
The former full-forearm virtual extension beyond the elbow is removed.

Look-ahead is capped at14 projections, with a one-projection exit when straight
reach is admissible or the wrist is fully locked. It is cached until the goal,
PHAT parameters, or shoulder position changes (0.01cm shoulder tolerance). Body
compensation changes at most0.5cm per authored tick, with a0.01cm residual deadband
and0.35cm orientation feasibility reserve. Translating a target preserves the
feedback value while recomputing its direction, preventing a body reset on drag.
`grabs[].armPlan` stores the feedback/cache for deterministic snapshot continuation;
imports validate it. Old snapshots without this state start with zero added request.

The arm correction still preserves both bone lengths and adjusts elbow swivel
and forearm roll from the previous displayed pose, with at most two passes and18
quaternion-cost evaluations per hand/tick (one when settled). It recomputes wrist
position from the achievable rotation and fixed palm/contact offset. There is no
correction or look-ahead for inactive hands, reach-only, or clamp-off. The native
body kernel executes once per authored tick; no new solver calls or native build.
Elbow swivel remains limited to8degrees/tick (also speed-scaled), forearm roll to
4degrees/tick. Existing angular hand pursuit precedes the final wrist projection.
The selected surface, hand rotation, finger fit and acquisition tolerances are
unchanged. Clamp/grab transitions seed pursuit from the displayed wrist/elbow.

This is a lab-only overlay above the native body kernel (including the October16
elbow preference change). The feedback
reduces unnecessary bending but does not prove a global minimum of body movement.
Fixed upright palm orientations and wrist limits can still require compensation.
It enforces wrist PHAT and arm lengths, not shoulder/elbow PHAT, collision or
physical stability. Unreal still uses its earlier overlay until explicitly ported.

`grab.js` ports the native palm offset, open-thumb clearance (up to4cm with8
binary refinements), sphere contact query, five fingers/three joints each,
12-step curl search plus6 binary refinements, and.65cm contact sample radius.
Each segment uses the same five sample points and2cm terminal tip as Unreal.
Fingers fit once per grab/size/orientation, then close over.2 authored seconds
once wrist error is<3cm and the closure angle passes. Acquisition requires full
closure,<1.25cm and the grip angle. The native actual-hand<2cm/angle gates are
identical here because commanded and actual hands coincide. Contact count is
reported but, like the native prototype, is not an additional acquisition gate.
Large spheres that cannot clear the open fingers within4cm are rejected visibly.

`fingers.json` contains the actual mannequin reference and authored `closed_fist`
frame0 transforms. Reference-basis conversion and folded metacarpals match native
`BuildFingers`. Thirty finger joints drive visible capsules; the palm is shortened
to meet the finger roots. Refresh that read-only export via `export_fingers.py`
using the same remote Python command as the PHAT exporter. No asset writes, Play
or build are needed. Snapshots fingerprint the exported finger poses and reject
incompatible saved finger states after an export changes.

The lab's held sphere has a **kinematic fixed attachment** captured relative to
the actual wrist at acquisition. Right-drag moves its requested destination;
the hand reaches there and the held sphere follows the wrist. Disabling Reaching
releases the ball at its current pose, opens the fingers and returns the arm over
15ticks. Unchecking Grab ball switches to reach-only and opens the fingers.
Ball positions are authored; released balls stay placed, without gravity.

This covers the sphere grab pose/contact pipeline, not NN locomotion, Jolt rigid
bodies, collision response or physical tracking. Native Kinematic mode itself
only marks a grip; the visible fixed attachment is an explicit lab extension.
The physical fixed joint still requires Unreal validation when porting. Box,
capsule and skeletal-bone grab targets are not yet lab controls. Future fixes
belong here first; port only after user approval.

## Fast development

The user performs refresh manually with **Refresh lab**. Do not automatically
reload, close or reopen the lab window after edits; leave the active session
alone and report that the change is ready for their refresh.

Edit `solver.inl` for body/arm math or `app.js`/`wrist.js`/`coupled.js` for the lab overlay.
`build.py` compiles only one tiny standalone DLL, normally a few seconds; no UBT,
Unreal restart, project-header changes or editor assets. Stop only this lab's
server before rebuilding its loaded DLL, then run `launch.ps1` again. Browser-only
changes need refresh. Build preserves lab edits; **`--import-unreal` explicitly
replaces the lab solver snapshot**, so do not use that flag over experiments.
`origin.json` and `bin/build.json` distinguish original source and lab revision.
The launcher builds locally if the DLL is missing and verifies server identity;
an occupied port belonging to another app is never stopped/reused.

## Verification — October15

October16 Sync rotation: `node test_sync_rotation.cjs` runs an isolated server
and browser, never the user's desktop session. Sync0 reproduces the complete old
pose/grab/solver trajectory exactly. At sync1, position and rotation finish on
the same authored frames57/69; at0 rotation finishes12/13 and at0.5 finishes36/38.
Both PHAT-clamped grips still acquire with the original gates; constraint error
<4.5e-16. Mid-reach retargeting, deterministic snapshot replay, reset preservation,
legacy default0, numeric clamping, slider UI and persistent reload all pass.
Receipt and screenshot: `Saved/Diagnostics/ReachSyncRotation20261016/`.
No build/service restart/Unreal changes; user performs Refresh.

October16 forward follow-up: snapshot0005 elbows lower6.47/7.54cm and move inward
5.54/6.17cm, with exactly unchanged wrists/body and both grabs held. Contact,
rotation and finger fitting are preserved; snapshot replay is deterministic.
Eight directional fixtures and240 moving horizontal/vertical-circle frames pass,
max elbow step2.62cm, bone-length error<3.2e-14cm. Default PHAT-clamped grabs still
acquire under the existing8/6-degree gates. Native mean0.109ms before/0.119ms after
in this mixed test (load-dependent, not a performance regression claim). One
standalone translation unit built; only REACH service restarted. Installed hash
and stateless HTTP/native replay verified. Current evidence:
`Saved/Diagnostics/ReachForwardElbow20261016/`.

Earlier October16 side/back candidate: isolated baseline/candidate replay of snapshot0003
lowers the left elbow4.72cm, with exactly identical wrist positions and body
parameters. Both grips remain acquired, contact/rotation/palm/finger fitting stay
unchanged, snapshot continuation is deterministic, and a forward-reach fixture
matches the old complete pose exactly. Eight directional fixtures plus240 moving
target frames (horizontal circle and vertical circle through overhead) pass.
Maximum sweep elbow displacement2.62cm/frame at120cm/s wrist pursuit; arm-length
error<3.2e-14cm, quaternion norm error<9e-16, fixed feet unchanged. Both default
PHAT-clamped grabs acquire with the original8/6-degree gates. Measured native
mean across the mixed comparison was0.118ms before/0.102ms after; noise/load mean
this is not a speedup claim. Verification JSON and before/after PNGs are under
`Saved/Diagnostics/ReachElbowPreference20261016/`. No Unreal build. One standalone
translation unit compiled into the candidate; installed lab DLL now matches it.

-720 native-kernel frames, Off/Left/Right/Both, high/low/asymmetric distant goals:
  finite normalized poses, target pursuit bound, anchored feet, exact idle when
  Off, body response, arm length error at most5.69e-14cm.
-2,430 wrist-projection cases over all27 motion-mode combinations: normalization,
  all-free identity, all-locked alignment, projection idempotence≤2.13e-15.
-Browser: real right-drag and Shift-right-drag input, hand isolation, full return
  and inactive retirement, settings reload, screenshot/JSON case saving, no JS
  errors; rendered viewport visually inspected at1440×960.
-Actual visible desktop app verified by window title and current-view heartbeat.
-Taskbar follow-up: live IDs `MSEdge.127.0.0.1_/reach.browserprole.Default`
  (REACH) versus `MSEdge.127.0.0.1_/.browserprole.Default` (D/S). Live40px icon
  extracted read-only and visually verified as the lime hand/purple target.
  Browser resampling differs from Windows LoadImage pixel-for-pixel. Settings
  hash unchanged across the lab-only restart; Unreal and D/S remained open.
  Evidence: `Saved/Diagnostics/ReachTaskbar20261015/`.

Commands: `test_kernel.py`, `node test_wrist.cjs`, `node test_ui.cjs`. UI checks use
an isolated state directory and server port, never the user's current lab state.
`node test_rotation.cjs` checks absolute rotation,150 Euler round trips including
singularities, legacy-state migration/reload, identity for both hands, angular
speed, position-independent orientation and persistence. Its isolated browser
receipt is in `Saved/Diagnostics/ReachAbsoluteRotation20261015/`.
`node test_workspace.cjs` checks four independent resets, immutable defaults,
numbered snapshot restore, deterministic continuation, JSON import/export,
pending-edit refresh, server-restart persistence, read-only inspection, matched
live PNG hashes and P snapshots. Worker PNG matched the visible framebuffer
pixel-for-pixel. Evidence: `Saved/Diagnostics/ReachWorkspace20261015/`.
Receipts: `Saved/Diagnostics/ReachLab20261015/`. The source extraction is exact;
these are standalone invariants/UI checks, not an end-to-end live Unreal pose
comparison. No Unreal build/restart/gameplay edits were performed for this lab.

Grab follow-up: `node test_grab.cjs` verifies both default grips with PHAT enabled,
30 rendered finger joints,14 fitted size/side cases with no contact-sample
penetration, held RMB dragging and rigid attachment, release/return, resize/refit,
oversize rejection, automatic contact, blocked PHAT and unreachable targets,
exact snapshot continuation, refresh and inactive retirement. Workspace and
reach-only rotation regressions also pass. Evidence:
`Saved/Diagnostics/ReachGrabLab20261015/`. Actual desktop feed confirms both balls
held with four fitted contact fingers each; latest user positions/rotations,
camera and disabled clamp setting preserved. Only REACH server/window restarted.

Coupled clamp follow-up: `node test_coupled.cjs` verifies837 frames across automatic
and absolute contact, moving held targets, an unreachable target, current-pose
exit to reach-only, clamp-off/inactive bypass, and exact snapshot continuation.
Both default pairs acquire with8/6-degree tolerances and their originally selected
contact/rotation/curls unchanged. Max bone-length error2.49e-14cm; wrist reprojection
error3.33e-16 (quaternion-dot measure); no added foot displacement. Max wrist step
2cm at120cm/s; settled contact errors below1.5e-14cm. Observed evaluation bound18,
settled1. The older zero-rotation test is now achievable through arm compensation;
it checks the resulting PHAT constraint and grip gate instead of expecting failure.

Historical measurement before the arm-first correction: browser correction including virtual endpoint generation
averaged0.127ms/tick for the two hands, p950.300ms, max0.750ms over the mixed test.
The existing native body kernel averaged2.700ms, p9518.887ms in those cases; it
remains the dominant cost and this is not a many-agent performance claim.
A separate Node arithmetic-only benchmark (100 batches of100 single-hand solves,
mixed approach poses,5.08 evaluations on average) measured0.236ms/hand on average;
its batch p95 was0.698ms/hand. Runtime/load differences mean this is not a browser
frame-time or Unreal estimate. Rendering/network/physical simulation are excluded.
The current verification receipt in that folder is regenerated by later tests;
these earlier numbers are retained here for comparison. No native/Unreal build was needed; only the lab overlay and static-file route changed.

Delivery check: the live REACH desktop resumed its saved tick/pose with settings,
camera and playback preserved, and acquired both existing balls without changing
their captured surface normals, rotations, palm offsets or curls. Lab server and
app alone reopened. Both `test_coupled.cjs` and updated `test_grab.cjs` pass; the
latter explicitly checks acceptance gates on new acquisition rather than on
already-held grips (which remain attached when subsequent motion exceeds a gate).
`delivery.json` and `after-live.json` record the live check.

Arm-first regression: `node test_arm_first.cjs` reads snapshot0002 (or a supplied
JSON path) in a read-only inspection browser; it never writes the desktop session.
Identical saved contacts: forward bend46.88->27.83degrees, crouch21.15->9.14cm;
both hands acquire from idle and remain held on continuation. A real Restart,
which selects fresh upper-arm contact references, gives17.70degrees/4.50cm.
The reachable arm-only fixture has0degrees bend and0cm crouch, both grips held.
Contacts/rotations/fitting unchanged during each run; zero invalid acquisitions,
exact snapshot continuation, maintained body feedback during target translation,
and clamp-off bypass pass. No look-ahead calls in the final120 settled ticks.
Overlay mean0.101ms/tick for both hands,p950.250ms; native body mean0.120ms,
p950.310ms in this snapshot regression. Broader837-frame `test_coupled.cjs` also
passes: max length error2.14e-14cm, wrist reprojection error3.33e-16, max hand step
2cm at120cm/s, overlay mean0.178ms,p950.400ms, native0.728ms,p952.939ms. These exclude
rendering/network and are not many-agent estimates. Evidence and comparison PNG:
`Saved/Diagnostics/ReachArmFirst20261015/`. No app/server refresh or restart;
changes await the user's Refresh button. No native build or Unreal changes.
