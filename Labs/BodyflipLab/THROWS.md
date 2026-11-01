# Throws in Bodyflip

## Point-targeted spear release - November 1 (accepted)

The accepted setup was pushed first as `5b2a2da6`; the remote branch and recovery
manifest were verified. The user confirmed the point-targeted change works and
requested its push. Live saved state and Unreal are unchanged.

Default spear aim now fits the forward shaft ray from its **actual held release
origin** to the target point. Previously it used the jump-frame-zero pelvis-to-
target direction, so a displaced release origin could leave a lateral miss.
Each candidate recomputes the held origin after spine articulation and COM
compensation. Like Throw Lab, it fits heading and elevation through spine01-05.
Ordinary playback retains its accepted rotation curve, including held-aim
transitions. Entry, Release, End and timed/distance-weighted return retain their
existing clocks. Relative arms, wrists and head remain authored.

For an actively spinning carrier, the two-angle fit evaluates the complete
physical trajectory, including its momentum response. This path uses Throw Lab's
continuous heading/elevation distribution to avoid the shortest-quaternion-log
seam while fitting large turns. The previous predictor
applied world rotations in the wrong order for this case. The fit starts from
the neutral carrier's release orientation; if that heading branch cannot converge,
it tries the opposite winding with the same two degrees of freedom. This may
require a larger spine turn. Nothing rotates the pelvis independently or redirects
the projectile. Fitting reads shaft geometry only; the actual spawn retains the
existing manifest velocity/spin transport and carrier translation.
Velocity prediction now accepts its own carrier pose sample, avoiding a recursive
read of the unfinished sequence in full-charge spinning throws. The actual spawn
continues to use the original carrier calculation.

Explicit `throwDirection` still requests a fixed authored world ray. Small throws
retain their frame-zero azimuth and source upward arc. Slashes/kicks are unchanged.
Preparation is cooperative and cached per attack/target; seeking/playback does not
re-fit. The four physical probes needed10/13/13/130 trajectory evaluations, so
this is a lab solution, not a measured60Hz native-game implementation. Native
integration/performance work has not been done. Unreachable points still report
the best residual; no universal reachability guarantee is implied.

Validation:396 moving/stationary target cases at2/4/12m, front/back/side and
elevated/lowered, with motion compensation on/off; maximum direction error
9.6e-9 and preserved arm/head local rotations within8.5e-16rad. Four complete
physical cases finish within2.4e-8 direction error and preserve seek results.
Actual app checks cover target inputs/drags, active spin with both momentum modes,
release packets, return controls and automatic playback resume (one Jolt world,
mock DOM/GL, no raster). Checkpoint comparison of slashL/jabR/KickL/small/explicit-
ray spear:15,860 bones, zero position difference and angular difference<2e-16rad.
Final source16,918 checks, shared return157 checks, authored direction762 checks
and existing four melee physical cases pass. Tests:verify-throw-target.mjs,
verify-throw-app.mjs, verify-throw-direction.mjs, verify-final-throws.mjs,
verify-duration-attack-return.mjs and verify-physical-aim.mjs.
The72-case throw-aim matrix also completes, including full-charge Small at
plus/minus360deg/s. Its pre-existing37% Small/-360 yaw-only limitation remains
(one case with0.00943 direction residual); it is not a spear point-fit failure.

## Upper-body pose audit - November 1 (current)

**Correction applied:** root is a coordinate frame; user authorized attacks to
exceed resting limits and return naturally. Normalize world pelvis rotation into
the initial root frame BEFORE source interpolation, then distribute to spine01-05.
Source arms/head remain authored. Shared attack projection and target tracking
carry attackFree through attack/return; normal projection resumes afterward.
Melee aim now preserves unchanged local rotations. Kicks share the final target
exemption. Contact clearance remains active. Native package/Unreal unchanged;
standalone Jolt structural constraints in dynamic simulation are not removed.

Current offline actual-app audit: final head/hand/chest relative errors<1e-6deg
through sampled Armed-to-End frames. F34 head/launch3.9796deg equals source;
F39 14.8101deg versus source14.7117deg (ongoing base pelvis moves), previously
60.9245deg. Arbitrary root rotations/translations leave articulation unchanged
at keys and subframes (<3e-14deg). Return exemption lifetime checked.16918 source/
shared-path checks,316 return checks,75 timeline checks, actual throw app and
4 physical aim cases pass. Original evidence: before.json; current: results.json.
No live state writes, GUI/raster verification, native build or asset changes.

The following original diagnosis is superseded by that correction:

User reported the head facing far from the throw and explicitly rejected a gaze
hotfix. `audit-throw-pose.mjs` replays the captured live scene through the actual
app scripts and one real Jolt world, with an in-memory DOM/GL sink and mocked
state writes. Instrumentation exposes internal stages in memory only. The
captured playhead is0.683333s/sourceF39; Release is0.6s/sourceF34. The throwing
hand is **hand_l**. Both labs use the same head forward axis; renderer error0deg.
Embedded FinalNoAim clip data equals the approved export exactly.

Two structural differences are confirmed:

- `jump-attack.armTrack` projects the already-approved source arms against the
  lab's idle-based joint limits. AtF34, source wrist twist is-84.1527deg versus
  the generic-55deg limit. Upper arm changes2.4876deg, forearm3.4899deg and wrist
 30.1515deg; head/chest stays identical. Head/hand relative orientation changes
 34.4558deg. Release aim then calibrates against this modified weapon frame.
- Transfer preserves source world orientation while the source root is present,
  but `overlay` keeps only upper-body local rotations on the base pelvis and
  drops animated source-root rotation. The source root turns20.9222deg between
  F34 andF39. The measured source-to-overlay upper-body rotation changes
 20.8006deg (including base-pelvis movement). It exactly matches
  `basePelvis * inverse(sourceF0LocalPelvis) * inverse(sourceRoot(t))`.

Angles between head forward and each stage's initial release velocity:

| Stage | F34 | F39 |
| --- | ---: | ---: |
| Approved source / pelvis transfer | 3.9796deg | 14.7117deg |
| Arm preparation | 38.4194deg | 41.4996deg |
| Overlay on base | 38.4194deg | 61.1987deg |
| Final displayed pose | 38.4194deg | 60.9245deg |

AtF39 the joint projector also changes head local orientation by4.8429deg;
compensation and post-release hand support add smaller differences. Therefore
the wrist clamp is not the entire post-release discrepancy. Earlier tests
proved source equality before adaptation and preserved arms after preparation;
they did not prove source-to-final upper-body fidelity.

Evidence: `Saved/BodyflipLab/ThrowPoseAudit/{scene,inputs,results}.json`.
The original diagnostic changed no runtime behavior. inputs.json identifies
the pre-correction runtime. See the correction above for current state.

## Shared angular return controls - November 1 (latest)

Current return controls below Fall cap: **Attack return (seconds)** is an
always-enabled GLOBAL slider directly above **Return distance weight**. Removed
its binding to marker selection (the cause of the greyed-out control). Editing
sets attackReturnDuration for timeline throws/melee/kicks and manual attacks.
Until edited, null preserves saved per-event attackOut and the manual0.45s tail;
the UI displays the existing event/default duration. Readout updates during drag;
release rebuilds playback using the existing global-control handler. No live saved
state was overwritten. Actual-app no-selection slider, throw and manual duration
checks pass;157 focused return checks pass. Distance weight remains0..1/default0.
Inactive lerp/snap/exponent sliders remain beneath them.
At return start, measure the largest shortest-arc bone orientation difference
from the ongoing base pose (excluding root, including attack aim). Choose once:
duration = baseReturnSeconds * (1-weight + weight*angle/90deg), minimum1/60s. Weight0
returns the unchanged existing track; weight1 is linear distance scaling.
The existing C.transition runs over that fixed duration, retaining incoming
velocity and the moving base. Body and aim share the selected duration. Source
entry/strike/follow-through before End are unchanged. Without a global duration override, manual attacks use0.45s and scheduled
attacks retain saved Attack Out. Big/Small markers
remain16/34 source frames. Target/aim edits rebuild plans when weight>0.
Measurement is from the attack track's aimed End pose, before later physical
spin/contact processing; it is not a live physics feedback controller.
153 duration/continuity/seek/source checks,16918 FinalNoAim/shared checks,75
editor checks and actual-app weight1 playback/retarget checks pass. Tests use an
offline DOM/GL sink, no raster inspection. No live state writes or native build.
Reload lab. Details: Labs/BodyflipLab/THROWS.md.

Earlier angular-return descriptions below are superseded.

User explicitly replaced duration-based Attack out with angular error decay.
`core.attackReturn` is shared by timeline upper-body attacks, throws, kicks and
manual attacks (Direct to Armed on/off). Each joint's local rotational offset
from the moving base animation decays by(1-alpha)^(60*elapsed). Below the snap
angle it is removed exactly. The additive aim rotation uses the same policy.
Sampling is stateless, so backward seeking/render frequency does not change the
trajectory. Manual animation attackRate is compensated in the return clock.

Original sliders (placement superseded above): Return lerp %/tick (1..100, default10) and Return snap
degrees (0.1..10, default0.5).1% means99% of the error remains per60Hz tick.
Removed the old per-event Attack out control/binding; saved legacy attackOut
values no longer drive active attack returns. Support hand/leg returns are
separate controls and remain unchanged. Internal returnEnd is a maximum bound
derived from180deg, alpha and snap, not a fixed-duration interpolation. Each
smaller joint offset snaps as soon as it reaches the threshold.

More options has Big/Small +frames after Release, stored globally per throw
type. Defaults16/34 retain Big sourceF50 and Small sourceF68 at100%. Converted
through each track's playback fps and bounded to its available source clip.
The full baked reference clips and manifest launch values remain unchanged.

Verification: verify-angular-attack-return.mjs passes316 checks over10 attack/
entry cases, plus moving slash/kick bases, frame-rate equivalence, snap, seek,
settings and UI location. Actual app-script harness tests slider edits, return
marker regeneration and both manual entry modes at2x rate.16,918 final-source/
shared-path,75 timeline,33 scene and4 physical-aim cases pass. Preserved throw
scene app replay: unchanged Release/launch, return starts0.8667s, reaches exact
base by1.8s at defaults. Legacy verify-attack-return.mjs asserts the superseded
fixed attackOut contract and is not the acceptance test for this feature.
No GUI/raster verification, live scene writes or native/Unreal build. Reload.

## Big throw source end F50 - November 1 (latest)

User identified the long baked comeback as the source of the delayed return.
Big throw now marks source frame50 as attack End. The complete FinalNoAim clip
is retained for source/reference inspection and transition derivatives; only
the runtime attack endpoint is shortened. Small throw remains unchanged.

The shared jump-attack path consumes optional phases.end (otherwise the last
frame). Its existing fast Armed entry is unchanged. Release is still computed
from Armed plus (releaseFrame-armedFrame)/playbackFPS; End is then Release plus
(endFrame-releaseFrame)/playbackFPS. At default speed that is F34 ->F50,16/60s.
Neither event is hardcoded to a scene time/frame. Normal shared Attack out then
returns the body and aim; no separate throw return rule was added.

Actual captured-scene app replay: Release0.60s, End0.866667s, returnEnd1.116667s;
aim weight0 and residual aim angle1.1e-16rad at returnEnd. Release velocity and
shaft remain unchanged.16,918 checks include exact baked source, shared return,
variable entry durations/delay and0.5/1/2x throw speed; actual-app retarget and
reference checks plus76 jump-track checks pass. No live state/trim edits, GUI
or native rebuild. Reload source. Earlier2.45s return diagnosis is superseded
by this explicit source endpoint. Evidence: Saved/BodyflipLab/ThrowSceneAudit.

## Shared attack return - November 1 (latest)

User rejected the separate throw fade added in the previous update. Removed
the `initialLaunch` timing branch: throws and slashes now use the same aim
envelope, held through clip End then blended out over Attack out to returnEnd.
The underlying body, compensation and recovery already use jump-attack.js.
FinalNoAim source data,60fps timing and manifest launch remain unchanged.
The prior Release-to-End throw-only fade described below is superseded.

`verify-final-throws.mjs` now checks16,882 values, including61 samples per throw
against the shared slash body path (same clip/inputs), identical pose positions/
quaternions and identical slash/throw aim envelopes.27 shared pelvis-return
checks and actual-app retarget/reference tests pass. Actual app replay of the
preserved failing throw scene gives aim weights1 at2.20s,0.5 at2.325s,0 at2.45s;
remaining aim pose difference at returnEnd is1.1e-16rad. Released spear values
remain unchanged (shaft0deg error; travel2.13deg, including source2.08deg).

The current loop Out is2.0833s, before this throw's shared return starts. A loop
ending there cannot display the return. Saved attack is now slashL; the replay
explicitly uses Saved/BodyflipLab/ThrowSceneAudit/scene.json, not a substituted
claim about the live scene. User trim/settings were not changed. Reproduce:
`node Labs/BodyflipLab/audit-throw-scene.mjs Saved/BodyflipLab/ThrowSceneAudit/scene.json`.
No GUI or native build; reload source. Full live visual acceptance is not claimed.

## FinalNoAim source and authored recovery - November 1 (latest)

User specifically selected Exports/Throws/FinalNoAim/HANDOFF.md. The prior
runtime did not use it. `import-final-throws.mjs` now embeds its clips.json and
manifest.json with SHA256 provenance in data/throws.json. Full-charge Big/Small
sample the final bake directly: no old hand/forearm keys, Half shaping or source
target aiming reapplied. Existing geometry/binds are checked against current
ThrowLab/data/objects.json. Supplied clips are100%; partial Small still uses the
legacy procedural path, not duplicated edits on the baked clip.

Animation remains60fps at throwSpeed1, with Armed25/18 and Release34. Physical
speedScale is no longer applied to animation timing. As explicitly required by
the handoff, runtime launch uses manifest velocity/spin, rotated by the held
frame's change from the baked release, plus carrier translation once. This
supersedes earlier final-hand-derivative launch claims for full-charge throws.
The manifest's inherent shaft/travel difference is retained, not target-snapped.
Reference view also uses this bake and a regenerated offline Jolt flight with
the manifest packet; floor collisions, no reference target-sphere collision.

The added aim turn now fades smoothly from Release through the authored clip
End, rather than staying fully turned throughout the source recovery and only
unwinding afterward. Existing Undo rotation off behavior remains intentional.
Actual saved-app replay verifies half weight midway, zero at End/returnEnd, and
<5e-16rad pose difference from the un-aimed recovery at End. Source motion and
shared compensation still play during the fade.

`verify-final-throws.mjs`:10,416 checks including every final frame/bone, exact
file hashes, source timing, manifest speed and recovery weights. App script
retarget/reference tests pass. `audit-throw-scene.mjs` saves actual scene inputs
and verifies return poses; current shaft error0deg, travel error2.13deg versus
source manifest2.08deg. Previous hand-derived-speed/source-model tests describe
superseded contracts, not acceptance of this import. No GUI/raster, live scene
write or native rebuild. Reload to load. Evidence: Saved/BodyflipLab/ThrowSceneAudit.

## Rearward heading correction - November 1 (latest, partial)

User authorized correcting rearward facing/downward release, and requires the
actual failing scene as evidence. Replaced the shortest-arc spear-axis rotation
with heading about world up, followed by elevation about the turned horizontal
axis. The existing smooth five-spine distribution remains. `attackSpineAim`
marks this additive steering so standalone joint projection does not clip it
back to the resting22deg spine cones. Base/source poses and other joints retain
their projection. Native rig profiles still enforce their configured limits;
this is not native/dynamic acceptance or an Unreal change.

Actual state.json app replay: heading-176.79deg, elevation-5.95deg, shaft error
0deg; vertical launch velocity changes-16.969 ->+2.549m/s. The before/after
offline pose reconstruction was rendered and inspected. It is not a browser
screenshot. Actual-scene assertions check shaft alignment, no large torso pitch
and upward velocity. Same input snapshot is saved beside the result.

Full throw remains unresolved: actual travel is42.94deg off the requested ray.
The unaimed adapted motion already has47.64deg between shaft and hand velocity.
No velocity snapping/redirect was added. Do not conflate shaft alignment with
trajectory alignment.951 direction checks, six motion cases/2,000 transfer
checks, actual app retarget/reference checks and four shared physical cases pass.
Evidence: Saved/BodyflipLab/ThrowSceneAudit/{before,results,scene}.json and
release-comparison.png. Replay: `node Labs/BodyflipLab/audit-throw-scene.mjs`.
No live state writes, GUI control or native package changes; reload loads source.

## Actual saved-scene failure - November 1 (latest investigation, unresolved)

The user rejected the result after continuous steering. The actual app scripts
replayed with the saved scene now reproduce44.15deg shaft error and81.51deg
velocity error at release. Target[-.83778,2.43491,-3.27299], Space kinematic,
distributed transfer and full soft compensation. Solution residual0.75163;
its quaternion[.80441,.57225,-.15955,.00254] is nearly180deg around a tilted
axis. Shortest-arc direction alignment does not preserve an upright torso
for rearward targets; the final22deg spine constraints also clip the turn.
Previous passing app tests used other targets. They do not validate this case.
No further production edits were made during this investigation. Reproduce:
`node Labs/BodyflipLab/audit-throw-scene.mjs`; receipt:
Saved/BodyflipLab/ThrowSceneAudit/before.json. All state saves are mocked;
no GUI or live scene changes. This remains unresolved.

## Continuous spine steering - November 1 (latest)

Throw steering now retains one direction-to-direction quaternion. Previously
the solver converted the corrected release pose into legal joint coordinates,
then applied those coordinate differences to every animated pose. That is not
the same operation as continuously rotating the original upper-body motion.

The correction now blends from identity over entry to full rotation at release,
then out over recovery. Each spine receives one fifth of the world correction
(cumulative20/40/60/80/100%); descendants above spine_05 share its entire rotation,
preserving relative clavicle/arm/forearm/hand motion. Spear uses the shortest arc
between directions, rather than an extra yaw/pitch roll. Small retains yaw only.
The existing pelvis-transfer setting and compensation remain. Source arm legality,
final projection and endpoint calibration still apply. No projectile velocity
redirection, new speed/spin tuning or arm edits were made in this change.

951 checks now include nonzero target turns through41 frames per throw, shared
hand/chest correction, unchanged relative arms/pelvis and no added roll around
the source ray. Six motion/compensation cases,2,000 transfer checks, actual app
release/retarget/reference-toggle checks and four shared physical melee cases
pass. No GUI/raster or live-state writes. Reload lab; native package unchanged.
This does not by itself resolve the separate hand/shaft velocity-angle mismatch
documented below; the earlier numeric audit describes the preceding version.

## Spear speed, initial spin and reference view - November 1 (current)

The source is still Throw Lab's approved `big throw.fbx` at30fps, with saved
hand/forearm keys and grip edits. Release is virtual60Hz frame34 (FBX frame17).
Its approved profile has speedScale1.8 and axial twist14deg per60Hz frame.
The previous hand-derived release correction removed both profile settings,
and inherited transverse hand angular motion as projectile tumbling.

The runtime now uses `60 * throwSpeed * controls.speedScale` animation fps;
linear launch velocity remains the derivative of the final held COM trajectory.
No saved velocity direction/impulse is injected. Configured spear spin is restored
along its release shaft (`14 * PI/3`rad/s at throwSpeed1), with no transverse
hand angular component. This is an authored Throw Lab launch policy, not an
assertion that full hand angular velocity is preserved. Bomb angular velocity
still follows the hand. Shared spine transfer, fixed world aim, arm rotations
and motion compensation remain intact.

In the current-settings fixed-base audit (not a full live-scene replay), speed
changes9.8304 ->17.6621m/s; original Throw Lab's tuned launch is18.3398m/s.
Transverse initial spin changes13.1793 ->0rad/s. An isolated real Jolt replay
turns the shaft1.73deg in its first25ms, down from16.30deg. Remaining aero
turning is not fixed: the actual hand velocity is24.75deg from the shaft,
giving13.48deg shaft turn after100ms. Do not claim complete alignment or zero
in-flight turning. Evidence: Saved/BodyflipLab/ThrowLaunchAudit/{before,results}.json.

The existing Vanilla attack only checkbox now supports both throws, labelled
**THROW LAB REFERENCE**. It uses the same full-body approved source model at
100% charge, including Throw Lab grip/key/aim edits; it is not raw unedited FBX.
The source clock runs at original timing, Armed-aligned, independently of the
Bodyflip speed setting. `export-throw-reference.mjs` records the original lab's
actual Jolt flight at120Hz into data/throw-reference.json (80,798bytes). The
display uses this cache with its original target/floor and held weapon before
release. It adds no live simulation or world and cannot alter Bodyflip tuning.

49,864 source/reference checks pass, including reference hold/release continuity,
pose/flight mapping and axial launch policy. The actual app-script harness tests
reference mesh rendering/toggle isolation, twelve retarget paths, final hand
velocity and shaft aim, and exactly one real Jolt world. Six motion cases,2,000
spine-share checks,60 drift/rate and130 world-direction checks pass. No browser
raster or live-state writes; no native/Unreal rebuild. Reload the lab to load.

## Authored world direction - November 1 (current)

Per the latest user instruction, throw aim is a world direction, not a ray
recomputed from each candidate release point. `throwDirection: [x,y,z]` on the
jump event is an optional normalized world-space override; it persists through
settings/scene sanitization. It is not a pelvis-local vector. No arm, forearm
or wrist adjustment was introduced.

With no explicit vector, the lab captures the pelvis world position at
`segment.jumpStart` (frame zero of the jump, distinct from attack/release time)
and uses `normalize(target - capturedPelvis)`. Every candidate and playback
sample uses the same direction. Physical prediction gets the same unpredicted
world-space anchor, rather than a pelvis position from its current trial.
Spear shaft aims along this vector; Small throw uses its horizontal bearing.
Explicit vectors ignore target-position edits. Editing the lab target reauthors
the default ray from the same jump-frame-zero origin. Viewport guide now draws
that frozen ray, not a line from the moving hand to the target.

The earlier wrist/forearm choice is superseded. The previous invariant-angle
claim applied only to a constant rigid rotation: a time-varying spine can also
change hand velocity. No arm edits or release-rate experiments were applied;
this update implements the user's replacement direction-authoring contract.
Hand-derived release velocities and existing compensation remain in place.

`verify-throw-direction.mjs`: 130 checks covering frame-zero timing, translated/
rotating bodies, changed future trajectories, explicit normalized/copied vectors,
scene serialization, physical world transforms and unchanged relative arm
rotations. Six motion/compensation cases and app target-edit/release-velocity
checks pass, along with 33 scene checks and four shared physical melee cases.
Evidence: Saved/BodyflipLab/ThrowDirection/results.json. No GUI or live state
writes; reload lab to load. Native runtime has not been repackaged.

## Motion correction - November 1 (retained, earlier context)

User rejected the previous saved-impulse construction and sideways body tilt.
`throw-attack.js` now delegates to `jump-attack.js` with an adapted clip, sharing
legal arm entry, optional pelvis transfer over spine_01-05, compensation,
soft legs/amount and recovery. Source target aiming is disabled for the adapter;
charge curves and grip edits remain. No separate compensation solver was added.

Throw aiming has only upper-chain heading/elevation (bomb heading only), with
no free roll, global pelvis aim or whole-body tilt fallback. Limited targets
retain a measured residual. Physical aim evaluates neighboring candidate poses
so the bomb's velocity comes from the same aimed motion.

`releaseVelocity` and `releaseAngularVelocity` measure left derivatives of the
held object's COM/orientation, using three final poses spaced by1ms / motion rate. The final
projected, aimed, compensated trajectory is the authority. `launchAt` accepts
complete velocities; it adds no seed linear impulse or detached speed multiplier.
The spear's angular launch now uses `projectileAngularVelocity` as described above.
Translation, body rotation and articulation enter once through that attachment.
Old transport method aliases remain for the source native adapter; no native
package was rebuilt. The reference `model()` still exposes imported launch data
for source parity; that saved packet is not the runtime release authority.

Throw speed changes animation fps so the hand and projectile speed change
together; zero disables that throw. Gravity/aero and collider ownership remain.

The earlier pose-only audit found a ~48deg shaft/travel angle after adaptation.
That was not proof that spine-only motion cannot solve it. The follow-up user
instruction chooses the fixed world direction described above and removes the
pending wrist/forearm question. The old 1.34cm ballistic miss receipt remains
historical; it used the rejected saved-impulse construction.

`verify-throw-motion.mjs`: six cases (two throws, compensation off/soft/rigid),
2,000 equal-spine-share checks, continuous entry/release/return boundaries
(max 3.58e-6 radians), independent held-object velocity agreement within
0.005m/s, zero measured derivatives for a frozen hand, and no roll/pelvis aim parameter.
Both compensation paths visibly change the pelvis numerically. Nearby shaft/
plane targets fit below 1e-8. `verify-throw-drift.mjs`: 60 translation, rotation,
analytic COM tangent, angular velocity, playback-rate and zero-rate checks.
App harness checks final displayed release velocity and shaft after 12 target
edits. Source-model parity (49,314 values), 36 projectile rebuilds, and four
shared physical melee cases pass. No GUI/raster or live saved-state writes.
Evidence: Saved/BodyflipLab/ThrowMotion/results.json.

The updated 72-case heading/spin probe passes continuity/COM, parameter-count,
unturned-direction and honest-residual checks. Four offset targets remain
limited (maximum unit-vector residual 0.07998, about 4.58deg); these are not
counted as exact hits. The previous all-directions fit contract relied on the
now-removed pelvis/roll freedom and is no longer an appropriate acceptance test.

`bodyflip-throws.js` owns held meshes and immutable release plans.
`projectile-world.mjs` creates released bodies in the existing Bodyflip Jolt
world. It uses the approved convex/compound geometry, physical scale, mass,
gyro, CCD and dissipative spear aerodynamics. The app advances its one world;
kinematic seeking caches projectile states and does not step while paused or
scrubbing through an already cached interval. Fractional release boundaries
split a step. Released objects participate in existing actor/platform
collisions; there is no added temporary collision gate.

October 31 target-move crash fix (local): cached raw `ScaledShape` objects now
hold an explicit `AddRef`, balanced by `Release` after bodies are destroyed at
world disposal. Previously the body held the only reference; rebuilding release
plans after a target move freed the collider but left its wrapper in the cache.
The next spawn accessed freed WASM memory (UI: function signature mismatch;
offline reproduction: table index out of bounds). Unscaled/compound shapes
already retain their creation results and settings.

`verify-projectile-retarget.mjs` failed before the fix and passes 36 successive
rebuilds afterward, covering the exported spear scale, unscaled bomb and a
nonuniformly scaled bomb, cached playback, body counts and disposal.
`verify-throw-app.mjs` now exercises 6 coordinate-input changes plus 6 target
drag-preview/end paths after spear release in the actual app scripts with a
mock DOM/GL sink and one real Jolt world. Its DOM/timer mocks were updated for
current toggleAttribute/cooperative preparation. These and the existing 10
projectile checks pass. No actual GUI/raster verification or live saved-state
writes; native runtime remains un-repackaged. Reload the lab after a crash.

Validation commands (offline; no desktop or saved-scene writes):

```text
node Labs/BodyflipLab/verify-throws.mjs
node Labs/BodyflipLab/verify-projectiles.mjs
node Labs/BodyflipLab/verify-projectile-retarget.mjs
node Labs/BodyflipLab/verify-throw-hulls.mjs
node Labs/BodyflipLab/verify-throw-aim.mjs
node Labs/BodyflipLab/verify-throw-motion.mjs
node Labs/BodyflipLab/verify-throw-direction.mjs
node Labs/BodyflipLab/verify-throw-release-aim.mjs
node Labs/BodyflipLab/verify-throw-drift.mjs
node Labs/BodyflipLab/verify-throw-app.mjs
node Labs/BodyflipLab/verify-jump-track.mjs
node Tools/Bodyflip/verify-throw-embedded.mjs
node Tools/Bodyflip/verify-app-parity.mjs
node Labs/BodyflipLab/verify-native-profile-throws.mjs
node Tools/Bodyflip/verify-release-cache.mjs
```

Historical checks before the November 1 correction (superseded contracts):

Reference parity checks 49,314 pose/launch values, maximum difference
1.55e-14. The aiming check covers both throws, Small charge 10/37/100%,
stationary and +/-360 degrees/s bodyflip plus twist, and six target directions:
72 cases, maximum shaft/planar direction-vector error 7.87e-9. Bomb cases use
targets with a horizontal bearing; directly overhead has no unique yaw.
The drift check adds 54 assertions across eight known-reachable mixed-spin cases
(including 11 m/s upward drift), two deliberately unreachable weak bombs,
and scene-translation/source-rotation invariance. Reachable error is at most
2.75e-9; impossible cases remain finite misses, without changing source impulse,
and beat an independent 24-yaw sweep. Older full-velocity aiming descriptions
and native parity results below predate this release-direction contract.

Native and app aim use the same initial centered physical reference; a globally
transformed equivalent reference had introduced roundoff that selected visibly
different weak-throw solutions. The solve now scales its LM regularizer with
Jacobian sensitivity and reuses each projected candidate. Fourteen Node/Chakra
frames at Small 0.37% and 37%, mixed spin and a rear target, agree within
1.62e-8 m and 5.38e-9 in launch direction. This includes the fractional release
frame. The planner retains its 120 s whole-job watchdog and memory guard;
the VM Command MaxSeconds argument currently does not enforce a separate
per-command deadline. Probe timings cover whole cases.

The app smoke loads all browser scripts and actual assets against an in-memory DOM/GL sink and the
real single Jolt world; it verifies release/UI integration but does not
rasterize a browser image. Existing simulated foot/one-hand/two-hand replay
also passed 1,296 frames with maximum pose tracking error 1.54 cm and no hinge
limit excess.

Final app/adapter boundary checks pass 24 samples across four fixtures: sweep
with mixed spin aimed behind, Small throws at 37% and 0.37% in that setup, and
an idle foot push with surface correction. Positions match exactly; the
quaternion-angle comparator reports at most 5.97e-8 radians. This is Node
running the actual app scripts and packaged native adapter; the separate
Chakra comparison above covers cross-engine arithmetic. The idle landing uses
the same deterministic NN stub on both sides, so this check does not establish
trained native NN or native physics parity. All ten recorded source/package
hashes remained unchanged during the run. Receipts:
Saved/Diagnostics/BodyflipPort20261030/app-parity-final-summary.json and
app-parity-hashes-before.json / app-parity-hashes-after.json.

The explicit native rig profile (23 bodies, 78.25452959537506 kg) also passes
six mixed-spin throw endpoints, including COM drift and rear/diagonal targets.
Maximum launch-direction error is 5.37e-10. Across 36 intermediate samples,
joint-limit error stays below 4.85e-16 rad, connector error below 4.58e-16 m,
and COM displacement from the aiming correction below 1.81e-15 m. Source
hashes remained fixed during this run. This verifies the profile-aware source
planner; it does not replace native Jolt flight or servo validation.

The native adapter caches each completed throw's release packet until its
target, sequence, preparation horizon or scene changes. Sample time still
updates the release remainder; callers receive a fresh copy of cached data.
With BODYFLIP_RELEASE_PROFILE=Labs/BodyflipLab/fixtures/native-rig.json, the
cache test compares 52 commands against an uncached copy of the same source
adapter. Repeated samples, backward seeks, target edits, preparation extensions,
scene changes and caller mutation all produce exactly equal output. Release
calculations fall from 54 to 10; wall-time measurements were noisy and do not
establish a native performance gain. The profile run uses source modules in
memory and a deterministic NN stub for its ground continuation. Receipts are
native-profile-throws.json and release-cache-native-profile.json under
Saved/Diagnostics/BodyflipPort20261030/; both record unchanged source hashes.

Native integration uses the same packaged evaluator and a scoped
FProphecyBodyflipProjectiles owner. It shares the existing Jolt coordinator;
an optional per-call schedule splits only active projectile steps at release
fractions and preserves unrelated forces for the full requested interval.
Its opt-in authored-convex preparation keeps the approved 1 mm bevel before
physical scaling; ordinary imported convex geometry uses its existing path.
Authored preparation bypasses the preliminary zero-tolerance Chaos hull pass,
which rejected two approved spear hulls. It uses the measured WASM settings
(hull tolerance 0.001 m, convex-radius error 0.05 m, bevel 0.001 m), retaining
the exported mass/COM/inertia. All 18 hulls pass the coordinate/scale check;
maximum bounds difference from approved WASM construction is 9.33e-8 m.
The native tests are Prophecy.Jolt.Bodyflip.FractionalRelease and
Prophecy.Bodyflip.ProjectileGeometry. Native seeks restore recorded owned
projectile position, orientation, linear/angular velocity and activation without
stepping the shared world. Released objects require an exact recorded frame and
matching launch settings; an uncomputed/evicted frame returns an explicit error
before changing the playback state. Pre-release frames remain freely seekable.
History retains at most 32,768 body states; scene edits invalidate old collision
history. Resuming a recorded state simulates against the current shared world;
other actors and old contact solver history are not rewound. Pause clears only
the owned body's queued forces, preserves its release velocity, and excludes it
from fractional-step force callbacks.
The isolated material bake is Tools/Bodyflip/create_projectile_material.py.
