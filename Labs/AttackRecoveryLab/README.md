# Attack Recovery Lab

Open **Attack Recovery Lab** on the Windows desktop. It launches its own window
and local service at `http://127.0.0.1:8817`. No Unreal session is required.

The app contains **320 freshly generated Easy variants**, 20 for each of the
16 Final Harness attack types. Every type except headbutt has 19 volume targets
and one floor target (the harness's rounded 7% quota). Headbutt has 20 volume
targets. Variant 20 is the floor target where applicable. Use the attack and
variant selectors, or **Go to floor target**.

## Accepted Unreal port baseline, October 4

The saved state contains the accepted per-attack Blend + inertia profiles. Main
inertia, bone weights, duration, easing, inertia hold/decay, world mode and additive
spine-angle time are all per attack. Angle time adds seconds per 90 degrees
(default .29), independently of base duration. Continuous spring remains a lab
experiment and is not part of the requested Unreal port. This snapshot preserves
the running lab before that port. The October 4 accepted milestone subsequently
updates saved tuning and adds snapshots 11/12. Lab slashRU angle time .20 is
preserved here independently of Unreal's deliberately unchanged .29 profile.

## Controls

The October 8 recovery milestone refreshes this snapshot's saved lab state,
including hookR main inertia .10, return time .28 seconds and easing 0.
The runtime algorithm and portable launcher are unchanged.

The attack/variant picker, top yaw slider, Snapshot and Refresh stay visible.
**Motion** contains return tuning, method/space selectors, bone weights/profile
copy and the per-attack Main inertia. **View** contains display/gizmos and
camera reset. **Library** contains floor targets, saved snapshots and variant
management. The selected tab and open side panel persist through refresh. Scripts and styles
use content-versioned URLs so restoring an older file cannot reuse newer cached
code through an old modification timestamp.
Control explanations are under **Control guide**. Playback remains at the bottom.


Sliders preview values while dragging and apply to playback only on release.
Playback and saved snapshots keep the last committed settings during a drag.

- **Return time · current attack** controls the duration after the complete
  authored tail for the selected attack type (0.1–3 seconds), shared by variants.
  Changing attack loads its saved duration; existing settings initialize every
  attack to the previous return time. **Easing · current attack**, beside Return time in the left panel, blends between a constant-speed
  return (0) and the original quintic ease-in/out (1). It is independent of
  inertia; zero bone inertia still follows the selected easing. Durations and
  easing persist per attack in settings and snapshots.
- **Main inertia** saves per attack type, shared across that attack’s variants.
  All attacks initialize to 100% when migrating from the old global control.
  It is included in profile copies and snapshots. Zero removes momentum carry;
  increasing it carries the outgoing world angular motion farther into the
  return. Both hands have no local rotation or offset inertia; they still
  inherit forearm/ancestor motion and follow the ordinary local idle blend.
  The end of the return is exact at every setting.
- **Inertia hold · current attack** delays momentum decay for 0–80% of return
  time; its label also shows seconds. The local momentum offset grows at its
  initial rate during the hold, while the ordinary idle-return blend continues.
  The envelope joins its fade smoothly after the hold.
- **Inertia decay · current attack** scales the exponential decay: lower means
  slower, higher means faster. Zero removes exponential damping, but the end
  fade still brings the offset to zero at the return deadline. Hold 0% and decay
  1× preserve the previous curve. Both values save per attack, share across its
  variants, and are included in snapshots and profile copies. Long holds can
  require a faster final return; increase Return time for a longer total window.
- **Inertia space → World** carries each active joint's angular
  correction about a fixed world axis instead of an axis carried by its parent.
  Each joint uses the world orientation of the ordinary FK idle blend as its
  baseline; parent inertia is not reapplied to its rotation. It still inherits
  parent position, keeping every joint attached and segment lengths fixed.
  Hands and zero-weight joints follow their parents normally. This controls
  rotational inertia, not free world-space translation or rigid-body physics.
  The selector saves per attack and copies with its profile. Parent local retains the
  existing parent-local mode; old settings/snapshots retain their saved space.
- **Method → Continuous spring** replaces the rejected hold-then-return experiment.
  Active joints keep angular velocity and receive a spring torque toward their
  parent-local idle target throughout the return. The spring grows continuously;
  there is no hold phase or active-joint pose crossfade. **Pull ramp** controls
  how gently attraction starts (higher = gentler early / stronger late).
  **Spring damping** controls braking/overshoot; damping converges toward critical
  damping near the deadline to settle. Per-bone inertia changes spring response;
  lower nonzero values make the spring stiffer while retaining outgoing motion.
  Zero-weight joints and hands retain their ordinary local idle return.
  World space integrates angular velocity in world coordinates while pulling
  toward each current parent's idle target. Local space integrates FK local
  rotations. Both keep segment lengths fixed. This is an angular spring model
  with FK constraints, not a mass-coupled rigid-body or collision simulation.
  The trajectory is cached on a deterministic integration grid and sampled
  through FK, so playback rate and seeking do not alter the simulation. Short
  Return time still requires a fast finish. Old profiles default this mode off.
- **Copy profile to attacks…** opens a source selector and destination checklist.
  Select one source and any number of targets (or Select all), then Copy. It
  copies per-bone inertia multipliers, inertia space/hold/decay, return time and easing as independent
  profiles, shared across each target's variants. Selected settings are replaced
  and saved automatically; the main inertia multiplier is copied too.
- **Attack spine rotation** applies −179° to +179° yaw to authored playback.
  Like Unreal half-attack distribution, each of spine_01 through spine_05 adds
  20% of the turn, with the pelvis and lower body fixed. Recovery captures the
  twisted tail and its outgoing velocity, then returns to the shared neutral frame-0
  idle. This is an input to recovery, not a persistent display rotation.
- **Per-bone inertia…** opens a separate panel of 0–1 multipliers saved independently
  for each attack type and shared across its variants. **Spine** controls all
  five spine joints together; neck bones, head, clavicles, upperarms and lowerarms
  have their own controls. Paired bones share one multiplier. Effective inertia = main inertia × bone alpha; all default
  to 1. Zero removes that bone's local momentum while retaining parent motion.
  These settings are saved and included in snapshots. Existing global settings
  initialize each attack, averaging the former five spine values into Spine.
  Hands remain excluded.
- **Return to idle** switches the new processing on/off. Off holds the authored
  last frame after the attack so it can be compared directly.
- **Upper body only · lock spine_01** hides everything below spine_01 and locks
  that joint's position to its first-frame location. Its own rotation remains
  visible. The target receives the same display translation; a floor target can
  therefore appear above the grid in this inspection mode. Motion data is untouched.
- **Show idle reference** draws the destination as a blue skeleton.
- **Green authored · orange return** shows green through the authored tail,
  then orange when recovery begins. Disable it to leave the agent orange.
- **Hand rotation guizmos**, **Lowerarm rotation guizmos**, and
  **Upperarm rotation guizmos** independently show
  the side selected by **Arm guizmo side** (Right or Left), using the displayed bone basis: X red, Y green, Z blue, yellow
  pivot, and the same depth-tested arrows as Final Harness.
- **Remove this variant permanently** excludes that generated variant from
  the app library across refresh, relaunch and regeneration. The identity is
  retained in `removed_variants.json`; original binaries and snapshots stay
  available for diagnostics. No variants are automatically removed.
- Space always plays/pauses and arrows always step one source frame, even with
  a widget focused. Frame stepping wraps at either end. Drag orbits; right-drag pans;
  the wheel zooms. Playback automatically loops, with a 0.35-second inspection pause at the loop end.
- **Snapshot (N)** shows the saved snapshot count and increments after a
  successful save. Snapshot / P saves a numbered PNG and JSON under `snapshots/`, including
  the actual displayed pose, target, source motion hash, frame, tuning and camera.
  The snapshot selector in Library restores that state. **Refresh harness** preserves it.

## Playback fidelity

Playback samples the existing motion at requestAnimationFrame timestamps, with
no new smoothing, frame quantization, time clamping, or recovery changes.
The renderer reuses vertex storage and cached capsule topology while retaining
exact float32 vertex positions, normals, colors, triangle order and resolution.
PNG capture uses asynchronous encoding and reuses an unchanged shared view;
pixels and pose are frozen together before playback advances. Snapshots remain
full-resolution PNGs. Slider labels avoid repeated identical DOM writes.

`profile_playback.cjs` measures rendering and frame intervals in an isolated
inspection browser. `verify_playback_fidelity.cjs` compares rendered geometry
against the saved prior renderer and verifies asynchronous capture preserves
the exact pixels even while the displayed frame advances. The reference files
are in `playback-performance-before`; measured results are in
`playback-performance-baseline.json`, `playback-performance-after.json`, and
`playback-fidelity-verification.json`.

## Motion contract

`recovery.js` processes spine_01 and its descendants through parent-local FK.
Authored positions and hand/sword rotations are preserved. Forearm rotations
carry their frame-0 parent-local orientation with the upperarm and use the
shortest swing to face the wrist, removing unstable decoder roll. This is
applied at authored subframes too. At tail end, recovery captures
the terminal authored world angular velocity and parent-local offsets. The
velocity is measured from the actual displayed path, including forearm fitting
and distributed spine yaw. Each bone subtracts the velocity it will inherit from
its parent, then converts the residual into its terminal bone frame. The initial
idle-easing velocity is subtracted too. These seeds are cached per profile and
applied as parent-local FK offsets throughout recovery, so active joints keep
their outgoing world angular velocity without counting parent motion twice.
The frozen pelvis has zero return velocity; spine_01 therefore carries the
pelvis contribution that would otherwise disappear. The local orientation
returns along a quaternion shortest arc to the shared neutral animation's
frame-0 idle. Local offset directions return on the sphere, at fixed segment
length, which keeps shoulders/elbows/wrists attached throughout the return.

Every attack uses frame 0 of `M_Neutral_Stand_Idle_Loop` as one common
parent-local idle, including the entire spine/neck/head chain. The authored
neutral NPZ was checked against the actual Unreal animation local rotations;
its frozen copy and digest are recorded in `manifest.sharedIdle`. Per-attack
frame-0 poses are kept only as authored forearm references, not return targets. Pelvis/root/legs hold their
authored last-frame transforms during recovery; they are never corrected here.

The return uses quintic smooth interpolation plus an analytic angular momentum
offset. Except on hand_l and hand_r, the momentum preserves outgoing
world angular velocity at the transition and fades
to exactly zero at the chosen end time. Hold and decay tune its envelope;
all attacks use the same algorithm, including
slashLU. This is an initial FK return prototype; it does not contain a body
collision avoidance solver.

This is a kinematic momentum handoff, not rigid-body dynamics. Fixed bone lengths,
local offset interpolation and the exclusion of hand inertia still constrain
point velocities. The existing momentum envelope still brakes the motion after
the transition. A zero inertia weight retains the ordinary idle interpolation
for that joint; descendants account for the motion they actually inherit.

Authored subframes use Final Harness's global position lerp and global quaternion
slerp, followed by the forearm correction described above. FK applies to the new recovery. The original viewer interpolated authored
parent/child local rotations separately; inconsistent arcs during a forearm roll
could flip the hand between otherwise correct frames. Snapshot 0002 exposed it
at slashLU variant 20, frame 23.503: stored motion matched the frozen harness
byte-for-byte but the old viewer added 179.537 degrees of hand rotation. The
corrected display matches the harness, so these motions need no regeneration.
`audit-snapshot-0002.json` preserves the before-fix evidence.

Sampling is stateless and shared by playback, stepping, snapshots and tests.
Preparation happens once per loaded variant. Active evaluation is linear in
skeleton size. Disabled processing returns the existing source endpoint;
completed processing returns a cached idle pose with no spring work.

## Source and generation

This app is independent of the Final Harness UI/settings and its production
datasets. `frozen/receipt.json` pins the standard Final Harness HTML, shared
settings and renderer used for generation. The sampler is the harness's
`sampleDatasetCloudForActive('easy', 20)` with seed 1234 and normal authored
starts. The exporter calls `visibleTrajectoryCapture()`, the same displayed
solver used by the harness. Each packed little-endian float32 motion stores
all frame positions, then all frame bases, with SHA-256 in its JSON receipt.

`generate.mjs` uses an isolated browser with intercepted settings/publishing
requests. It never writes to the real Final Harness, starts production
generation, or contacts a remote service. It resumes only matching, checksum-
verified motions. To regenerate, use the local Python/Node runtimes, run
`freeze_source.py`, start `server.py`, run `generate.mjs`, then
`prepare_assets.py` and `build_renderer.py`. Changed frozen inputs stop rather
than silently replacing completed data.

The renderer is derived reproducibly from the frozen Final Harness WebGL
renderer: depth-tested body volumes, hand/foot shapes, sword geometry, orbit
camera and grid. The app adds the upper-body mask, optional skeleton, target,
idle reference and recovery controls. It uses no CDN or network asset.

## Focused verification

`test_recovery.cjs` checks all 320 motions, floor quotas and finite values,
unchanged integer attack frames, fixed recovery lengths, untouched lower body,
seam continuity, outgoing angular velocity, exact local idle, disabled/completed
behavior and spine anchoring. `verification-core.json` stores the result.

`check_ui.mjs` exercises attack/variant selection, floor/headbutt behavior,
playback, snapshot creation/restoration and refresh persistence in Chromium.
Its screenshots and `verification-ui.json` record the check.

`check_v2.mjs` uses a separate server/state directory to check colors, guizmos,
snapshot/refresh persistence, three loops and a second attack, desktop identity,
matching PNG/state hashes, read-only capture, and permanent removal across server
restart. It never removes real user variants. Results: `verification-v2-ui.json`.

## Inspecting the exact desktop view

The launcher registers a fresh desktop session token. Only that window may save
settings/snapshots, remove variants or publish the current view. Other browser
tabs are inspection-only. The backend is `backend.py`; `server.py` launches it.

Read `GET /desktop-view` on port 8817 first. Require `ok`, a recent `receivedAt`,
the expected client ID, loaded build revision, attack/variant, frame, controls,
target and fingerprint. Read `/desktop-view.png?sequence=<sequence>` for the
matching viewport; a 409 means the frame changed, so reread both. Verify its
`imageSha256`. A test tab must never substitute for the actual desktop view.

For numerical inspection, POST `/app-control` with the desktop `clientId` and
`command: "capture_visible_trajectory"`; poll `/capture?id=<returned-id>`.
The desktop evaluates the retained immutable model/settings for that published
fingerprint without changing selection, frame, camera, playback or focus.
Verify the returned fingerprint; expired views fail explicitly.
`current_view.json` and `current_view.png` mirror the latest published view.
Numbered snapshots remain stable historical evidence for specific complaints.

## Upperarm twist inertia removal (October 9)

**Remove upperarm twist inertia** replaces the removed angle limit entirely.
The 0–100% slider is saved per attack and shared by both arms. Zero preserves
the original sampler. At 100%, swing/twist decomposition removes the axial
part of the finite inertia rotation while preserving its swing exactly.
The axis is the actual shoulder-to-elbow segment, expressed in the upperarm
frame. Partial values remove the corresponding fraction of that twist.

World inertia carries the removed shoulder rotation through the forearm and
hand so their parent-local rotations remain unchanged; independent world
forearm inertia must not undo the shoulder correction. Shoulder and elbow
positions match the original path, wrist position follows the corrected bend.
No pose clamp, forced elbow-down target or normal-idle-return change.
The optional continuous spring remains unchanged and hides this control.
The filter is skipped after return ends, at zero inertia or zero removal.

Numeric verification across 321 variants preserves swing and forearm/hand
local rotations within floating-point precision; zero removal is bit-identical.
For slashLD21 at 0.125 seconds into recovery, world pole elevation changes
from +55.0 degrees to -25.1 degrees at full removal. Some upward pole motion
remains later; this is not a guarantee that the elbow always points downward.
Slider changes commit on release; refresh, snapshots and profile copy retain it.
Legacy twist-limit settings are ignored. Ported to Unreal on October 9 as
**Set Attack FK Return Twist Inertia**. The accepted slashLD profile was imported;
other native attack profiles were preserved. See `Docs/AttackFKReturn.md` in the
repository root for the native contract and numerical parity limits.
