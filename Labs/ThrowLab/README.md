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

## Approved throw checkpoint - October27

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
needs Python and Chromium as specified in `launch.ps1`. The included spear cache
is the version used by the approved throw, independent of ongoing asset work.

### Current editing behavior

Hold **Left Ctrl** while dragging any rotation ring (hand, forearm, weapon grip
or velocity) for30% angular movement. Pressing/releasing it during a drag changes
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

`prepare_spear.py` reads the requested FBX with the existing FBX SDK, preserving
all21,112 triangles, the grip pivot and2.2m scale. The nine authored convex UCX
hulls form one Jolt compound body; decorative tassel geometry is excluded from
collision. Render colors sample the BaseColor atlas per triangle under existing
lab lighting; this renderer does not reproduce the full PBR material. Mass is
1.2kg, matching the placeholder. No source asset is modified. Refresh loads the
cache; importing is explicit, with no watcher or extra background process:

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
the service when needed; it does not restart other labs or Unreal. No push.
