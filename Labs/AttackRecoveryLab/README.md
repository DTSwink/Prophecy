# Attack Recovery Lab

Open **Attack Recovery Lab** on the Windows desktop. It launches its own window
and local service at `http://127.0.0.1:8817`. No Unreal session is required.

The app contains **320 freshly generated Easy variants**, 20 for each of the
16 Final Harness attack types. Every type except headbutt has 19 volume targets
and one floor target (the harness's rounded 7% quota). Headbutt has 20 volume
targets. Variant 20 is the floor target where applicable. Use the attack and
variant selectors, or **Go to floor target**.

## Controls

Sliders preview values while dragging and apply to playback only on release.
Playback and saved snapshots keep the last committed settings during a drag.

- **Return time · current attack** controls the duration after the complete
  authored tail for the selected attack type (0.1–3 seconds), shared by variants.
  Changing attack loads its saved duration; existing settings initialize every
  attack to the previous return time. **Easing · current attack**, beside Return time in the left panel, blends between a constant-speed
  return (0) and the original quintic ease-in/out (1). It is independent of
  inertia; zero bone inertia still follows the selected easing. Durations and
  easing persist per attack in settings and snapshots.
- **Inertia** is the only momentum control. Zero removes momentum carry;
  increasing it carries the outgoing local angular motion farther into the
  return. Both hands have no local rotation or offset inertia; they still
  inherit forearm/ancestor motion and follow the ordinary local idle blend.
  The end of the return is exact at every setting.
- **Copy profile to attacks…** opens a source selector and destination checklist.
  Select one source and any number of targets (or Select all), then Copy. It
  copies per-bone inertia multipliers, return time and easing as independent
  profiles, shared across each target's variants. Selected settings are replaced
  and saved automatically; the main inertia multiplier remains shared.
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
  The snapshot selector restores that state. **Refresh harness** preserves it.

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
the final two parent-local orientations and offsets. The local orientation
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
parent-local angular velocity and fades
to exactly zero at the chosen end time, without a separate hold, alpha, core/arm
setting or per-attack exception. All attacks use the same algorithm, including
slashLU. This is an initial FK return prototype; it does not contain a body
collision avoidance solver.

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
