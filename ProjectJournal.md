# Prophecy â€” current handoff

**November4 — accepted Foot IK pushed and ported to Unreal:** lab-only commit
8fe5a2c5 pushed; no models/captures/unrelated uploads. Current user setup phase0.9,
Leg blend0.8s, floor deletionF50 retained. Canonical wall-approach/ankle/slide-entry
changes now embedded; native hand-contact math matches the corrected collider
extent. Normal build passed. Four slide cases/1120 frames/81 NN windows exact
inside Unreal and native V8;14 terrain cases/8414 frames exact; root-coordinate
and disable check passes. Existing Foot IK enable node and Blueprint tuning
preserved. Native port local only. Interrupted cold lifecycle attempt is NOT a
pass; realtime limits remain. Owned test processes closed. Auto-review blocked
removing ~174MB of generated test caches; paths and evidence in
[Foot IK native handoff](Docs/FootIKNative.md). Earlier lab-only status below is
superseded by this port.

**November 3 - Foot IK F16-19 thigh continuity follow-up (lab):** The prior
clearance/impact response still produced a sharp thigh arrival/reversal. Shared
feet now accommodate a damped thigh-direction pursuit with a bounded pelvis
translation, re-solving both legs to the existing ankle targets. Material pins
and held shoe rotations stay fixed; free shoes retain joint/sole constraints.
The contact planner keeps a separate reference for hip forecasting; final shoe
geometry owns support reporting. No frame gates, contact delay, new UI or NN
change. Reset/disable/empty terrain clear the response; flat output unchanged.

Fresh saved scene: thigh step5.62->3.83deg/120Hz, velocity change597->231deg/s;
first pin remains F18.5 for4ticks, calf axial<0.93deg, ankle error<0.000004deg.
237 targeted,757 surface/60cases,2723 shared-adapter checks pass; split replay
exact, renderer comparisons inspected. Small arrival-* evidence and prior-source
backup retained under Saved/Diagnostics/FootIKWall20261103; discarded trials
removed. Root transport investigation not shipped. See FootIKLab README and
SHARED_API. Scene/camera/playhead/native/Blueprints untouched; no push. Refresh.

**November 3 - Foot IK thigh arrival smoothing (lab):** F18-19 was a fast
thigh turn followed by a contact reversal, not another hinge flip. Shared feet
spread new-plane clearance over the last 0.12s of swing and absorb part of the
capture velocity change with a small damped pelvis translation before leg IK.
No landing planner, acquisition delay, relaxed ankle limit or NN alteration.
The response is absent on unchanged ground and clears on reset/disable.

Saved scene: thigh step 7.61 to 5.62 deg/120Hz; angular-velocity change 1110 to
597 deg/s. First wall pin stays F18.5, duration 3 to 4 ticks; load response peaks
at 3.35cm. Prior calf/ankle fixes remain. 237 targeted checks on a fresh 217-frame
causal rollout, 757 checks/60 surface cases and 2,723 shared-adapter checks pass.
Torso articulation is checked relative to the pelvis, with this new translation
separately bounded. Actual contact changes slightly change the later root
trajectory; whole-clip equality is not claimed. Slide still starts F44.5.
Rendered approach/slide comparisons inspected. See FootIKLab README/SHARED_API;
small thigh-* evidence in Saved/Diagnostics/FootIKWall20261103, discarded trials
removed. No live-state/native/Blueprint/build/push changes; Refresh to load.

**November 3 — Foot IK wall-entry rotation follow-up (lab):** F18–28's left
calf twist came from the derived FK frame, not the predicted knee position.
Surface-only decoding now uses the existing signed-hinge-normal contract on a
copied lower clip. Same-input checks preserve all positions, predicted axes
and recurrent tensors exactly; shared checkpoint/runtime untouched. Free shoe
rotation carries NN motion and limits only terrain correction. An approaching
new plane cues orientation in the existing landing window; heading and heel/toe
axes are transported onto it. Explicit surface heading prevents the pin yaw
limiter reading floor-to-wall approach as backwards. No incoming knee pre-bend,
acquisition gate or changes to accepted slide-arm motion.

82 targeted checks: left calf axial step 17.68→0.90° at F18–28; right sole angle
to wall normal at F16 83.70→28.23°. Material pins and actual ankle limits hold,
split generation is exact, eight ordinary terrain/disabled cases unchanged.
697 surface checks/60 cases and 2,723 shared-adapter checks pass. The surface
yaw test now measures heading from the lateral shoe axis, avoiding singular
forward projection when the toe aims into a wall. See FootIKLab README and
SHARED_API; small entry-* evidence under Saved/Diagnostics/FootIKWall20261103.
Rendered comparisons inspected; live tuning/playhead retained, Refresh needed.
No native/Blueprint/build/push. Earlier slide-floor overlap limitation remains.

**November 3 — Foot IK wall-run contact corrections (lab):** F19 captured the
previous tick's ankle and changed reach allowance on release. Shared feet now
capture the current predicted ankle, keep one source-preserving soft reach
allowance, and roll an existing heel/toe contact before full extension. No
pre-bent arrival or delayed acquisition gate. Actual ankle constraints reuse
the pure Jolt-frame slide-joints.js helper; source NN residuals are retained.
Slide hands now fit their actual collider extent to the wall before the final
clearance pass, avoiding the sideways shoulder repair at F67/F85. Existing
friction, free-arm travel and easing remain. Calf step around F19: 7.90→4.72°;
right hand acceleration peaks: 353.68→7.32 / 134.44→12.78 m/s².

817 targeted/parity checks, 697 surface checks (60 cases), and 2,723 Bodyflip
shared-adapter checks pass. Ordinary flat/stair/down/disabled output is exact.
See Labs/FootIKLab/README.md and SHARED_API.md for behavior/dependency details;
evidence/original sources are in Saved/Diagnostics/FootIKWall20261103. A longer
turning NN request timed out; its shorter window passed with fresh replies.
The existing slide/floor foot overlap late in this clip remains (3.8cm before,
4.4cm with the changed contact trajectory). Visual checks used the lab renderer
in an isolated closed browser; live browser control unavailable, Refresh needed.
No native/Blueprint/build/push or live-tuning edits; user camera/playhead retained.

**November 3 — wall-run comparison opened in Foot IK:** Bodyflip Scene 2's
current footIKSettings/run phase imported into a separate small persistent
`Labs/FootIKLab/bodyflip-wall-scene.json`. Foot IK on port8890 now runs with
`--state-file` pointing there: Run58%,90-degree wall,toward approach; loop0–2.2s
at0.5x,paused0.6s. Original Foot IK state.json and Bodyflip settings unchanged.
This isolates the run-up in Foot IK; Bodyflip jump/flip events are not imported.

**November 3 CURRENT: vanilla shared Foot IK runtime restored.** The user asked
whether the rollback was really to the original Foot IK lab. It was not: the
first rollback still retained the older captureSustainable acquisition guard.
That guard is now removed. All11 shared runtime files match committed HEAD,
including the accepted later port corrections from dbc4401e; surface.js itself
also matches76614437. The HTTP shared-foot-ik.js bundle was checked to contain
that original surface solver with no guard. Bodyflip integration, jump/backflip
and user tuning remain; no wall-step workaround remains in canonical FootIK.
The existing Bodyflip target projection is still part of the host integration;
matching solver source is not a claim of identical final rendered poses between
the two labs. Jiggle is unresolved. Do not restore pre-bent wall arrival or
change the incoming pose to hide it: contact should stay stable, with the knee
bending on the wall when necessary. No native port or push.


**Earlier November 3 rollback (superseded by vanilla restoration above):**
The user wants the leg to bend as needed AFTER contacting the wall, and chiefly
wants a stable contact without jiggle. They did not request a pre-bent landing
or an anticipated wall pose. Do not restore that approach.

Restored the runtime immediately before the latest attempt: surface.js from
Saved/Diagnostics/surface-before-wall-lock.js; removed the added wall roll/yaw,
swing-carrier and early-stance changes; removed terrainTarget projection bypass
and preparation handoff; removed the terrain-mode-only NN forearm return fit.
The Bodyflip + Foot IK mode, scene, settings and previous integration remain.
This restores the earlier reach-ahead acquisition guard as part of the exact
rollback; that guard was also rejected as a fix and the jiggle is UNRESOLVED.
The contact regression therefore remains expected to fail on the missing first
right material pin. Test thresholds restored, including2mm at jump contact.
Previous passing verification and first-wall recordings describe the reverted
attempt, not current success. No new replacement fix, Unreal port or Git push.

**Bodyflip + Foot IK mode, November 3 (initial integration, LAB ONLY):** Added a separate mode and
wallrun/backflip preset. It uses the canonical FootIKLab surface/coupled NN
implementation, served from the Bodyflip server, then passes actual world pose
and movement to existing support/push/spin. Other modes do not run terrain IK.
Mode timelines retain their own platforms and spin settings; prior setup is
preserved. Wall controls sit on the left between return and pose controls.

Default: 90-degree wall, run phase .58, support marker .65 s, backflip command
320 deg/s, 0-2.2 s loop at half speed. With saved tuning: push/release .70625 s,
before original slide entry .73333 s; right toe landing 1.65 s. Wall loading
uses posed-body collision rather than an upright capsule. On landing only the
invisible root is rebased onto the support plane; physical bones stay in world
space. These two corrections are restricted to the new terrain adapter.

verify-terrain-mode.mjs (--saved also passes): 529 frames at240Hz, finite poses,
reverse seeks, successful wall push/foot landing, no terrain IK during flight,
mode restoration, displayed handoff position gaps below2mm (contact1.44mm;
release/landing below.02mm). 363 ordinary Run/Walk/Space poses exactly match HEAD.
Scene33, playback16 and arrow13 checks pass. The old capsule standing-jump test
still fails, reproduced on HEAD; not counted as a new regression or fixed.
Browser loads the shared compressed frames and plays the selected new mode.
Numerical/UI checks are not user acceptance of dynamic appearance.

Scope: shared wall locomotion into Bodyflip, then its existing grounded NN
return; repeated re-entry from a landing into a new wallrun is not yet a new
causal surface session. Initial terrain generation retains FootIKLab's five-
second limit (explicit error for longer locomotion-only timelines). Unreal,
Blueprints/assets and native packages were not changed or rebuilt; no Git push.
Evidence: Saved/Diagnostics/BodyflipFootIK/verification.json; original live
settings backup: Saved/Diagnostics/bodyflip-before-footik-mode.json.

**Expanded motion review, November 3:** The same native-review.html now offers
14 recordings / 1,709 frames: original floor/friction comparisons, native left-
and two-hand pushes, plus lab throw/sword returns, stopping spin and landings.
The left-hand capture exposes the earlier calf-to-foot stretch (+4.12 cm at
0.4 s), with desired-pose overlay. Native physics and lab algorithm comparisons
are explicitly distinguished. Four lab recordings have no independent expected
pose; overlay is disabled rather than inventing a target. Landing continuation
uses fresh local NN output: the old cached-input test failed before generating
motion, so this is not labelled a reproduced movement bug.
Tools/Bodyflip/capture-review-lab.mjs and prepare-native-review.py generate the
local-only replay under Saved/Diagnostics/BodyflipFloorReview20261103. All frames
checked finite; displayed position errors agree with recorded reference errors.
Selector, flagged-frame seek and overlay availability checked in the browser.
No gameplay, Unreal settings, original tests or live lab settings changed.

**Foot-friction controlled comparison, November 3:** Test-only native runs
baseline / zero foot friction / foot-foot pair disabled completed146 frames each.
Actual baseline feet use friction0.7, restitution0.3; zero-friction test verifies
friction0, Minimum combine, retaining restitution and all requested poses/rig.
Zero friction does NOT eliminate foot jitter. Disabling only foot-foot collision
removes its late contacts (37 ->0) but also does NOT eliminate jitter. Therefore
prior explanation attributing jitter to that pair alone is not established.
Fresh baseline right-foot peak19.79deg differs from original57.15deg despite
identical requested poses/rig; do not claim deterministic reproduction of that
peak. Precise remaining physical cause is unresolved. No gameplay tuning changed.
Compact result: Tools/Recovery/Receipts20261102Bodyflip/foot-friction-comparison.json.
Raw evidence: Saved/Diagnostics/BodyflipFootFriction20261103. Replay selector now
also offers all three controlled runs. Normal build passed; TestNN reopened.
No push requested/performed for these diagnostic additions.

**Journal scope (November 3):** This is the Unreal/game integration journal.
Standalone policy/AE training, cloud runs, sweeps, losses, checkpoints and training
viewers belong in [TrainingJournal.md](TrainingJournal.md). Keep only actual
Unreal integration, asset/runtime contracts and relevant game-lab work here;
do not copy training status logs back into this file.


**Recorded native motion review, November 3:** User requested a replay of the
saved-scene simulated mismatch with a selectable requested-pose overlay.
Tools/Bodyflip/prepare-native-review.py exports the two existing native traces
without rerunning physics; Tools/Bodyflip/native-review.html provides play,
frame stepping, speed, floor-present/lowered selection, overlay/off/target-only,
body selection, orbit/pan/follow and worst-error seek. Local viewer:
http://127.0.0.1:8878/Tools/Bodyflip/native-review.html . Generated replay remains
under Saved/Diagnostics/BodyflipFloorReview20261103 (not added to Git).
All292 recorded frames retain native world coordinates. Recomputed rendered
pose errors agree with native errors within1.75e-8rad /1.8e-15cm. Worst floor-run
error is right foot57.15deg at2.2s, AFTER the character has left the floor;
floor contact at that exact instant is not established and must not be claimed.
The lowered-floor run peaks33.36deg at the right thigh,1.567s. User reviews the
movement; this viewer is not a solver fix or visual approval. No Unreal/live
lab settings changed and no build required.

**Normal kick pose correction, November 2 (LAB ONLY; awaiting user review):**
User clarified that the deformed kick poses matter, not only the Hit direction.
Normal Kick L/R now use the existing common-body airborne reaction, retaining
recorded joint arrangement instead of the16-variable spine/free-hip rebalance.
Aim also rotates the complete compensated pose; it reaches its correction by
Armed and retains the existing normal-kick return policy. The motion-compensation
checkbox now also works for normal kicks. Entry/return use the projected base.
Normal kicks carry the existing authored-pose exemption through return so spin
recoil cannot re-clamp them into resting joint cones. Recoil itself is retained.

Measured old distortions: compensation added up to49.15deg at spine01 and33.66deg
at the free hip; aim added65-103deg at the striking hip; spin-recoil's resting
clamp independently changed Kick R by35.83deg. These corrections no longer
reshape the normal kick. The accepted sweep branch is unchanged.

Steering is an explicit commanded body turn, not passive conserved motion.
Its finite-step momentum is the difference between the moving aim frame and
that same interval with the aim frame held fixed. The original neutral solver's
residual is retained (transport disagreement<5.2e-10), not reset to zero.
Fractional seeks use the actual underlying integration interval. Sweep's earlier
bookkeeping is retained to avoid changing the accepted movement in this task.

22 actual-app motion cases at960Hz cover both legs, flip+/-400, twist+/-200,
front/rear targets, zero spin, compensation off and full3D. Maximum Hit direction
error9.2e-16; added aim joint rotation<2.8e-13deg; recorded-stroke shape difference
<0.000735deg /4.4micrometres from retained recoil. Reverse seeks agree<9e-15.
Boundary pose differences across+/-1e-7s are below0.000717deg; strike/return
velocity joins below1.7deg/s at6.25e-7s. The original falling loop has a velocity
corner at this setup's entry time (about263deg/s at left hand); projected kick
entry matches that baseline to about1e-6deg/s. That pre-existing loop corner is
not claimed fixed. No still image or video was used to approve dynamic quality.
Sweep/Slash L/Pike:363 before/after poses match exactly. Live settings unchanged;
served source bytes verified. No Unreal package/build changes and no Git push.
Portable regression: `node Labs/BodyflipLab/verify-kick-shape.mjs` (four reported
cases), `--full` selects22. Captured fixture: `fixtures/kick-spin.json`.
Evidence: `Saved/Diagnostics/KickPose20261102/`; preceding diagnosis below remains
historical. User must refresh the lab to review the changed movement.

**Earlier normal-kick investigation, November 2 (superseded by lab correction above):**
Captured the live Kick L / flip-400 / twist200 Space Gym setup read-only at
`Saved/Diagnostics/KickSpin20261102/live-state.json`. Actual app replay checks
Kick L/R at zero spin and flip+/-400 with twist200, plus sweep controls.
Kick L/-400 misses the target DIRECTION by38.261deg; its bounded solve returns
error0.655446 after52 trajectory evaluations, and production applies that failed
result without a failure indication. Other three spinning normal-kick endpoints
fit, but aiming changes the kicking hip by65.44-103.39deg during the motion.
Normal kicks use Hit-derived joint-coordinate offsets, unlike sweep's rigid
whole-compensated-pose aim. Do not equate an exact Hit endpoint with good motion.

Offline in-memory experiment retains normal `createBalanced` compensation and
changes only aim to a rigid whole-pose turn. Direction errors fall below1.3e-6deg
without changing any joint-local articulation (below5.2e-14deg). Normal kick
entry/return also switches raw falling poses against the projected display,
causing about8deg entry and5-6deg exit jumps, including at zero spin. Applying
the existing sweep projected-base rule removes those jumps: differences halve
with each halved time interval. Eight combined prototype cases cover both legs,
flip+/-400, twist+200/current rear target and twist-200/reflected front target.
The accepted sweep generator, live settings, lab runtime and Unreal are unchanged.

Proposed implementation: keep normal kick animation/balance; predict its balanced
Hit pose; use one explicit rigid aiming command, fully introduced by Armed;
retain existing return policy; use the same projected baseline on both sides.
Do not copy sweep's momentum bookkeeping blindly: the prototype reports roughly
0.26-1.71 angular-momentum residual versus below0.001 in the current normal path;
current sweep controls themselves report about1.45-1.47. Its finite-step
`I*omega` steering accounting must be resolved/verified before adoption. The
pre-existing arm-speed peaks also remain; prototype endpoint/continuity checks are not
visual approval of the full motion. No videos or still-based motion claims.
Evidence/scripts: `Saved/Diagnostics/KickSpin20261102/` (current-audit,
rigid-audit, rigid-projected-audit). No production fix, build or push this turn.

**Bumblebees ambient system, November 2-3 (separate task, Claude):** isolated runtime module
`ProphecyAmbient` (listed in the .uproject and both Target.cs ExtraModuleNames; no other module, BP, map or tuning
touched). `Bumblebee Zone` preference boxes (BeeCount, Preference, BeeSizeMultiplier, WingBeatHz 150, WalkSpeed 2.5 cm/s,
AirTime 0.5, bAvoidIndoors; yellow box + label visualiser, Show In Game) auto-create one `Bumblebee Swarm`: 8 instanced
meshes (fly/landed x 4 forced LODs), GPU WPO wings (per-instance Hz, blur fade) and legs (tripod gait driven by distance
walked), sweep-validated flight legs with circular-arc corners, persistent sway, banking and a 360 deg/s body turn cap (no
mid-air stops), constant time-to-contact landings on any surface, walking on pre-checked footholds (no walking off rims or
into flower centres, no hitching), threat take-off, indoor escape, tiered cost. BP category `Bumblebees` (Spawn Bumblebee
Zone with all settings, Set Bumblebee Size, threats, enable, show zones, stats). Bee Scale 0.75 = 1.9 cm vs 167.8 cm UEFN
mannequin. Materials v2 applied in-editor via `Saved/ClaudeJobs/beetools/bee_wpo_v2.py` (only the 3 bee materials saved).
Measured with `-BeeTest=traj` (every bee near the patch at 60 Hz) and the deterministic `-BeeTest=swarm` profiler:
worst close view (~300 near, ~280 flying) swarm tick 0.36 -> 0.26 ms after the optimisation pass; ~15.5 MB memory.
Test shots can be data-driven (`-BeeShots=<json>`, no rebuild). mybasic map test still not run (RAM).
**User standing instruction (Nov 2): when a build needs the main editor closed, Claude closes it itself (check no Play +
no dirty packages via remote Python `beetools/close_editor_safe.py`, graceful quit_editor, never force-kill unsaved work),
never builds while any editor on the project is open (Nov 3 C1076 incident), relies on the dynamic UBA worker adapter
(no fixed MaxParallelActions) and relaunches `/Game/testNN -NoSplash` afterwards.** A whole headless video in one process
runs the laptop out of RAM: record in parts (`-BeeVideoPart=1|2|3`). Job runner `Saved/ClaudeJobs`. No push.
[Bumblebees](Docs/Bumblebees.md).

**Ambient birds (gulls + kingfishers), November 3 (separate task, Claude):** same `ProphecyAmbient` module (no other
module, BP, map or tuning touched). `Bird Zone` (species, count, Primary/Secondary colour = kingfisher brown/white, gulls
fixed, size, air time, ambient cries; blue box visualiser) + `Spawn Bird Zone` node; one `Bird Flock` manager per world.
`ABird` = skeletal mesh + native `UBirdAnimInstance` blending Perch/Walk/Glide/Flap/Hover clips with procedural jaw (beak)
and head look; bank-limited coordinated flight, flap/glide bouts, reserved landing spots with glide-cone final approach and
damped touchdown, gull walks, threats (player, `BirdThreat`/`BeeThreat` tags). Bird-bird no-overlap rule (predictive
avoidance + hard pass; spot/walk spacing = take-off clearance). SFX hook: `OnBirdCry`/`OnZoneBirdCry`, `Bird Cry`,
`Set Beak Open`. Death: damage >= 10, spear (`/Game/_mygame/spear/A_Spear`, `Spear`/`BodyflipProjectile` tags, name) through
the bird faster than 7.5 m/s (swept test: Bodyflip projectiles are Jolt-only, no Chaos hits), heavy physics hit (> 3 m/s,
250 kg cm/s), `Kill Bird` -> runtime physics-asset ragdoll (14 bodies, real mass) + instanced feather burst (drag to
terminal velocity, falling-leaf flutter, settles). Models are PLACEHOLDERS (procedural Blender, `Exports/Birds/`,
`/Game/Prophecy/Creatures/Birds/`); user will replace them (Tripo) keeping the bone names, then re-run
`Exports/Birds/setup_birds.py`. Measured: flock 0.2-0.45 ms, no overlaps, 0 orientation snaps. Tests `-BirdTest=birds|video`
(`Saved/BirdTest`). Gotchas: Python SkeletalMaterial entries are copies; FBX anim import needs
`automated_import_should_detect_type=False` + armature-only FBX; UHT rejects UFUNCTION params named `Instigator`; `PI` is a
macro; a Chaos body created at rest is asleep (SetPhysicsLinearVelocity does not wake it). [Birds](Docs/Birds.md).

**Pike steering replacement, November 2 (accepted; ported to Unreal):** removed the rejected
06 world-chest lock and its winding history. The same optional saved checkbox
is now labelled **Pike: steer through thrust**. It plans a continuous heading /
five-spine elevation curve at Armed, mid-stroke and Hit in the moving carrier
frame, evaluating the actual momentum response. Arm locals, source timing,
ordinary aim/return and released-contact articulation are retained. Preparation
is cooperative; no solver is added to the playback pose after momentum balance.
Entry heading uses the shortest branch; an unconverged fit retains standard aim
and explicitly reports that in the lab's sequence status instead of applying it.

Current flip400/twist200 numerical motion checks at960Hz pass, including fresh
reverse seeks and velocity boundaries at Armed, mid-stroke, cut and return-end.
Added spine rotation peaks at22.82degrees per joint versus44.68 in rejected06;
aim direction error4.25e-7, arm-local difference<2e-13degrees, momentum residual
<3.4e-6. Front/rear, opposite/fast/inherited spin and Undo-off cases inspected
numerically. Off, zero-spin and Slash L poses match the previous paths exactly.
Production default, fresh reverse, front, original rear and fast-spin checks pass.
Permanent check: `node Labs/BodyflipLab/verify-pike-steering.mjs` (optional fixture
and `reverse` argument). Evidence: Saved/Diagnostics/PikeStroke20261102/.

**Limits:** the current stroke still drifts about6.2degrees between fitted points
(previous standard aim about69degrees); COM-relative contact path still has about
15.5cm curvature. This is not an exact straight-line constraint or a claim that
all dynamic movement looks correct. The full3D momentum test failed the bounded
fit: it now reports unavailability and keeps standard aim. Do not conceal this
fallback or call full3D Pike steering solved. User specifically clarified that
stills cannot validate dynamic mistakes; rely on time-dependent checks and never
claim that still images establish acceptable motion. No new videos were made.
User accepted the replacement and requested the complete Unreal port and Git
backup. Current captured setup has steering ON, Pike cut at source frame16,
flip400/twist200 and a1s attack delay. The live state was read without writes.
Native build, exact Unreal solver parity and clear-air physical replay pass.
TestNN is open; the owned Play startup check passed. See Docs/BodyflipNative.md.
Other earlier elbow-return concerns remain separate.

**Earlier Pike06 visual rejection, November 2 (replaced above):** user reports the unwrapped
motion tears/corkscrews the upper body. The wrap discontinuity was removed, but
that did NOT validate the movement. Offline inspection of the reported scene
with06 enabled measures223.41degrees of extra distributed torso rotation near
Armed (44.68degrees per spine, on top of authored pose). At Hit it is116.90degrees.
The full chest-orientation constraint cancels the carrier flip through the spine;
continuous unwrapping retains the large rotation instead of making it plausible.
Prior checks for continuity, arm-local preservation, momentum residual and endpoint
aim missed total torso deformation. Do not claim06 is a satisfactory Pike solution.
A replacement is not yet validated; do not add another clamp/counter-correction
or assume the earlier rejected direction-only prototypes are solved.
Current captured saved scene has06 off. No animation/settings changes during this
review. Evidence: Saved/Diagnostics/Pike06TorsoReview20261102/torso-correction.json.
User explicitly said to STOP MAKING VIDEOS; do not generate any unless asked again.

**Earlier Pike06 numerical wrap fix, November 2 (visual result rejected above):** the reported180degree
branch snap is fixed in the optional **Pike: spine absorbs rotation** path.
The spine correction retains the equivalent rotation nearest the previous
completed physical step before applying entry weight / five-spine distribution.
Only completed fixed steps select winding; momentum trial poses and fractional
or reverse seeks cannot change it. The physical articulation context now exposes
its start/timestep; a continued segment starts with its own identity correction.
The existing return carries the continuous correction and its outgoing velocity.

Exact reported flip400/twist200 case: maximum spine step at960Hz falls from
141.23degrees to1.94degrees. Forward/rear targets, opposite spin, flip800, and a
Pike beginning during inherited spin pass through entry, strike and full return.
Authored arm-local rotations and target direction pass; reported-case momentum
residual<1e-7. Reverse-order poses match forward exactly. Original reviewed06
forward/rear poses and checkbox-OFF poses remain position-exact (rotation roundoff
<1e-13deg). Released-foot-follow regression passes. Permanent regression:
`node Labs/BodyflipLab/verify-pike-spine-wrap.mjs` (with its regression fixture).
Evidence: Saved/Diagnostics/Pike06Wrap20261102/verification.json, parity.json,
per-case traces and 06-wrap-current.mp4 /06-wrap-front.mp4 (1080p60 before/after,
two normal passes then quarter speed). Rendered frame comparison inspected.
Only06 rotation-branch handling and physical-context metadata changed; elbow
files verified untouched. Checkbox remains default OFF; Refresh then enable it
to inspect. No live scene writes, UI control, Unreal changes or push.

**Earlier scope clarification, November 2:** user meant the06 wrap snap,
not the elbow-return body reaction. Keep this investigation focused on06.
The verified cause is `physical-aim.js` taking a fresh shortest quaternion log
before multiplying by entry weight and distributing it across the five spines.
At1.80833s the correction is178.00degrees; at1.8125s its axis reverses with
179.42degrees on the opposite branch. Partial entry weight / spine fractions
make those equivalent full rotations different partial poses: measured137.75deg
upper-body jump in4.17ms. A correction needs a continuous rotation path before
weighting/distribution, including deterministic seeks and return; no additional
elbow redesign is implied by this request. No animation code changed.

**Earlier Pike rotation-snap investigation, November 2 (06 now fixed above):**
user reports whole-body rotation snapping after the elbow fixes. Exact captured
scene still has06 OFF: Pike, flip400/twist200, delay1, F16 cut. The shoulder-transfer
workaround preserves forearm/hand orientation but moves the arm masses along a
different path. Momentum compensation responds with a sharp carrier counter-turn.
Offline controls: peak pelvis rotation839.12deg/s without either elbow protection,
1154.01 with right-only protection,1220.10 with both. Removing just the shoulder
transfer in an offline control removes that return burst (817.18deg/s overall
peak occurs during entry); that diagnostic redirects the hand, so it was NOT
installed as a fix. Previous elbow/hand/continuity checks were insufficient to
validate the whole-body response. Do not describe the shoulder-transfer workaround
as preserving whole-body motion/momentum without this qualification. The return
needs a coherent legal arm trajectory, not another whole-body counter-correction.

Separate06 failure reproduced in the same scene when enabled offline: at1.8125s
the shortest rotation log flips across180degrees (178.00deg -> opposite179.42deg).
Its weighted/distributed spine correction jumps137.75degrees in4.17ms. This is a
true discontinuity;06 remains default OFF and is not the cause in the saved state.
Evidence: Saved/Diagnostics/RotationSnap20261102/{fixture,audit,findings}.json/mjs
and per-variant traces. All production animation hashes verified unchanged during
this investigation; live scene preserved, no UI/Unreal work or push.

**Earlier Pike other-elbow return fix, November 2 (body reaction now under review):** the earlier protection
covered only the right/sword arm. In the new captured Pike setup (flip400,
twist200, attackDelay1, F16 cut,06 off), the left elbow reached79.42degrees
backwards during return (51.80degrees at the user's paused2.25s frame).
Both Pike elbows now use the existing extension-braking/shoulder-transfer rule.
No new clamp or return envelope: the blocked elbow turn passes into its shoulder,
preserving the combined forearm/hand orientation and outgoing velocity.
The actual-app960Hz return check now stays above3.55degrees flexion left and
3.91degrees right. Both-arm audit checks transition orientation preservation,
other local joints, rigid sockets, aim direction and boundaries. Original F16,
F17 and four coupled slash return regressions pass; reverse seek is deterministic.
Rendered before/after return frames inspected. Evidence:
Saved/Diagnostics/OtherElbow20261102/ (fixture, before/after, verified-current,
original-cut16/cut17 reports, coupled-returns.txt and comparison.png).
Production changes are limited to accepting both protected elbow indices and
passing both for Pike; other attacks retain their previous protection selection.
Pike06 remains optional/default off. Refresh the lab to load this fix. No live
settings writes, UI control, Unreal work or push.

**Pike 06 rollback option, November 2:** More options now ends with
**Pike: spine absorbs rotation** (`pikeSpineAbsorb`), default OFF. Off restores
pre-06 Pike behavior; on enables the experimental06 articulation. Saved per
scene, with the existing playback/time-preserving rebuild. Actual-app checks
pass: exact pre-06 poses off (103 Pike frames), on activates06, off restores the
baseline, saved on/off values and playback intent retained. The current captured
scene uses Slash L, flip400/twist200: all176 checked frames are identical with
the option on/off and pre-06 code. This option only affects Pike.
Evidence: Saved/Diagnostics/Pike06Toggle20261102/{current-result,pike-result}.txt.
Refresh to load the checkbox. No live scene writes, UI control, Unreal work or
push. This supplies the requested rollback; it does not fix the new motion case.

**Earlier Pike 06 installation, November 2 (now opt-in above):** user selected "Spine absorbs
rotation" and explicitly requested installation. `physical-aim.js` now uses that
orientation-only spine articulation for Pike with spin. It preserves authored
arm locals and the accepted return, and composes the existing released-foot
follow after the spine turn inside momentum balance. Other attacks retain their
previous articulation. Production matches every archived06 forward/rear displayed
pose through return within1.3e-13degrees /1.9e-15metres.480Hz continuity, reverse
seeks,19 attack cuts,19 zero-spin attacks, four coupled weapon returns and physical
slash aim pass. A focused Pike/contact composition check passes1,780 assertions
(foot direction error<0.000002degrees, momentum residual<0.000015).
Evidence: Saved/Diagnostics/Pike06Applied20261102/.
Residual positional curve and the known faster-spin quaternion-branch limitation
remain; this is the selected06 behavior, not a general straight-line constraint.
The user stopped computer control with Escape before the green Refresh button
could be clicked. Disk code is updated; the existing lab still needs Refresh.
No live settings were changed by this work; no Unreal work or push.

**Earlier Pike visual review correction, November 2 (before installation):** user reports severe twitching /
snapping in the attempts except06 (spine absorbs rotation). Retain06 as the only
candidate; reject01-05/07/08. Previous straightness/momentum/encoded-frame checks
were insufficient to accept motion. Saved120Hz poses confirm individual bone
jumps of up to174.45degrees per8.33ms in rejected variants. New06 forward/rear
480Hz audits show converging pose continuity at Armed/Hit/return-end, identical
reverse seeks, and authored sword-arm local rotations preserved within1.2e-13deg.
These checks do not establish a general finished fix: residual curve, faster-spin
quaternion branches and ground-contact-follow composition remain. No prototype
installed; no Unreal work. Evidence and decision: Saved/Diagnostics/PikeFlip20261102/
Videos/review-decision.json and continuity-06-orientation-{forward,back}.json.

**Pike review playback fix, November 2:** the comparison is now served at
http://127.0.0.1:8877/ by a read-only, allowlisted loopback server with byte-range
support. This avoids broken relative media paths in the app's local-file preview.
The page uses that media base and shows loading/playback errors instead of silently
ignoring them. Open Review.cmd beside the videos restarts the service when needed.
All nine video range requests pass; actual in-app browser baseline/variant06
playback reached4.628/4.631s with readyState4. No animation changes.

**Pike flip video review, November 2 (experiments only):** user requested videos
of all attempts, with both forward and rear targets, to choose visually. Eight
exact prototype sources plus unchanged baseline are archived under
Saved/Diagnostics/PikeFlip20261102/Videos/. Nine numbered 1080p60 MP4s each
show both targets through entry, strike and return; two 1x passes then 0.25x.
A 4K60 nine-way overview and local review page include known failures.
[Open video review](Saved/Diagnostics/PikeFlip20261102/Videos/index.html).
No experimental aiming code was applied to the live lab; baseline hash verified.
The original flip/Pike correction remains unresolved. Orientation-only variant06
passes current forward/rear momentum checks but retains curvature. Direction
variant08 straightens the captured rear stroke, but forward and other spin
cases fail. Earlier line-lock variants also have momentum spikes / sampling-order
sensitivity; video appearance alone is not a regression pass. Retain the accepted
Pike source, elbow/wrist return and settings below. Unreal remains deferred.

**Pike restart, November 2 (lab only):** previous path fix rejected after the
user's rear target made the torso fold over. Its endpoint fit had selected a
119-degree bend. Restarted from pre-fix code: Pike now uses heading/elevation
only, with no arbitrary sideways-bend/roll fallback; the reported target needs
20.2 degrees. Previous wrist IK and frozen-shoulder translation removed.
Authored pelvis travel follows the stroke; source hand rotations, compensation,
return inertia and other attacks retained. F16-trimmed Pike return now prevents
elbow hyperextension while passing its blocked turn through the shoulder: the
elbow-only brake redirected the sword and is superseded. Sword/forearm return
orientation and local wrist motion are preserved; safe Pike/other returns stay
unchanged. Elbow, combined-arm, cut/duration and spin checks pass. Exact rear/front,
24-direction grids, 19 cuts and four coupled returns pass. Whole rear movement
rendered and inspected. Residual path curvature is documented, not called zero.
`pike_final.fbx` remains Armed 9 / Hit 16 / End 17 at 30 Hz.
**The user has now accepted the lab and requested the complete native port below.**
[Lab details and verification](Labs/BodyflipLab/README.md).

**Bodyflip Unreal port, November 2 — accepted update built and loaded:**
Current package includes all five changed lab modules, pike_final and the latest
saved target/flip400/twist200/delay1/cut16/steering-ON settings. Normal builds pass.
Start Bodyflip Saved Lab Setup retains the exact scene without rewiring Blueprint.
18 app/adapter cases (513 frames) pass; package/source/settings audit100 checks
passes. Existing Blueprint compiles with all10,552 original pins/links preserved.
Clear-air native saved-setup replay passes through198 frames: maximum physical
error6.76cm /12.96deg, RMS0.466cm /0.492deg, leg-length error0.1094cm. Lowering only
the test floor preserves every canonical packet and removes all floor contacts.
The original floor-level Space Gym fixture reaches89.2deg right-foot rotation
error; a combined-run left-hand push also exceeded the3cm leg gate (4.125cm).
Do not describe the entire contact suite as green. Pinned V8:21 cases /607 frames exact. Actual Unreal:513 frames /117,179 numbers
exact. TestNN is open; healthy reflection and owned60-tick Play startup verified.
No assets or live lab state were saved. The requested broad repository checkpoint
includes current work and native runtime dependencies; see the recovery manifest.
[Bodyflip native current handoff](Docs/BodyflipNative.md).

Handoff updated **November 2, 2026**. This file and the current sections of linked topics take precedence over dated archives. Each topic has its own verification/build state.

## Resume here

**Slow-loco Unreal integration prerequisites:** Training changes do not update
Unreal automatically. The checkpoint's `actuation_controller.json` defines the
head-height leg-strength ramp; NN weights alone do not set native motor limits.
The training-only hip-range expansions were not applied to the Unreal PHAT.
Before an authorized port, match the checkpoint's controller and joint-limit
contract. [Controller details](TrainingJournal.md#training-entry-0079),
[hip-limit details](TrainingJournal.md#training-entry-0109).

**Pike pre-impact interpolation correction, November 2 (current, local):**
Captured saved Pike setup (Direct to Armed) at Saved/BodyflipLab/pike-input.json.
Violent pre-impact swings originated in source subframe interpolation, before
compensation/aim: separate local forearm/wrist slerps added15.08deg/10.38deg hand
detours between sourceF14-15/F15-16, where recorded hand keys differ7.14/4.33deg.
Pike now samples root-normalized component rotations together, then reconstructs
local joints for retargeting and pelvis transfer. Original integer poses retained;
source sword direction matches component slerp at subframes within1.2e-13deg,
with pelvis transfer on/off. Rigid local socket positions retained. Scope is Pike;
slash/throw/kick interpolation and all return inertia/decay logic stay unchanged.
Armed0.935847158s and Hit1.169180491s unchanged. Pre-impact authored peak hand
rotation1432deg/s ->215deg/s; displayed aim peak1650deg/s ->430deg/s during strike.
Actual rendered Armed-to-Hit contact sheet reviewed at Saved/BodyflipLab/Pike/
return.png. Current captured-app assertions pass in audit-pike-entry.mjs; all four
coupled sword-return regressions pass unchanged. No live state writes, native
work or push. Refresh existing lab to review.

**Coupled forearm/wrist return, November 2 (current, local):**
User required continuing the trimmed Slash LU fix while retaining existing inertia.
Return seeding now removes equal opposing axial forearm/wrist rates as a pair,
relative to the upper arm. Net hand angular velocity, swing rates, starting pose,
return polynomial/decay and duration policy are retained. Same-sign roll is
untouched. This applies to the sword arm only for slashes/pike, in original and
distance-weighted returns. The hand remains forearm-local throughout recovery.
No independent world-hand override, added damping, speed cap, source interpolation
change, or after-the-fact wrist clamp. Resting limits may still be exceeded briefly,
as authorized for attacks. No guarantee of passive articulated momentum conservation.
Original LU cutoff20: accumulated displayed hand travel about462deg ->260deg.
Peak wrist limit excess127.7deg ->6.62deg; the small remaining transient is NOT
claimed strictly within resting limits. LU cutoff21 and Slash L full end23 have
valid wrists throughout sampled return. Conservative entire-sword mesh/head
clearance bounds: LU20 >=5.66cm, LU21 >=0.30cm, L23 >=14.15cm (sampled at240Hz).
Four actual-app cases pass weapon path, continuous pose/hand velocity, and seek
checks, including zero distance weight. A synthetic counter-roll pair preserves
net hand inertia to5.5e-16rad; non-cancelling motion remains exactly unchanged.
All19 attack cutoff tests pass. Actual body/sword contact sheet reviewed. Live
playback not controlled. Reload lab; no live state writes, native work or push.
Regression: verify-coupled-weapon-return.mjs with saved original fixture
../../Saved/BodyflipLab/trimmed-sword-input.json. Separate current Slash L audit:
audit-sword-wrist.mjs ../../Saved/BodyflipLab/slashL-wrist-input.json final-L.

**Slash L wrist/head regression rollback, November 2 (preceding correction):**
User reported broken wrist and sword/head penetration in active Slash L (full
source end23), screenshot at1.55s. The independent world-hand return introduced
by the last attempt was the cause. It preserved arm motion but broke the wrist's
relationship to that arm: at1.55s wrist exceeded limits by95.32deg; peak148.2deg.
Its sword centerline passed9.1cm inside the head capsule during return.
Removed that complete attempt from core.js/jump-attack.js, restoring both files
byte-for-byte to pre-sword-fix snapshots (all earlier trim controls retained).
The established forearm-local wrist return and full original inertia are restored.
No new braking, clamping, world-hand override or source-interpolation change.
Actual-app replay of the saved current setup now passes wrist limits throughout
return (max error2.8e-14deg). A conservative capsule enclosing the entire actual
sword mesh stays at least14.15cm from the rendered head capsule at240Hz samples.
Audit: Labs/BodyflipLab/audit-sword-wrist.mjs with fixture
../../Saved/BodyflipLab/slashL-wrist-input.json; before/after in Saved/BodyflipLab.
Earlier independent-hand verification is retained as rejected history under
Saved/BodyflipLab/rejected-independent-hand-verification.mjs, not a passing test.
The original trimmed Slash LU complaint was not solved by that rollback; the
coupled correction above supersedes this pending status. Future diagnosis must check
wrist/forearm coherence and weapon clearance, not merely accumulated sword travel.
No live state edits or native work; refresh the existing lab.

**Sword return correction, November 2 (REVERTED: wrist/head regression):**
The rejected braking/return-target projection was fully reverted first. Source
interpolation was investigated but is unchanged. Existing return curves, decay,
duration selection, compensation and joint-limit handoff remain unchanged.
For sword attacks (slashes/pike), only hand_r return orientation now uses the
actual hand/world quaternion and velocity in the same existing transition curve.
Forearm-relative counter-twist was previously carried as independent rotational
inertia, creating excess sword spin. The hand calculation is applied after the
original compensation/return plan so it does not change body or arm trajectories.
Throws, kicks and unarmed attacks retain their old path. No velocity clamp or
new damping policy. No live state edits or native work; refresh lab for review.
Before/after actual-app comparison on the captured Slash LU cutoff20: attack
before cut and every non-hand return orientation match within1.25e-16rad;
all joint positions match, incoming hand velocity and return deadlines retained.
Checked distance weight0 and0.4, hand pose/velocity joins and deterministic seek.
At weight0.4 displayed hand accumulated travel462.47deg ->258.21deg; this measures
total travel, not a shortest-path guarantee. All19 cutoff checks pass. Actual
renderer body/sword contact sheet reviewed; live user playback not controlled.
Test: Labs/BodyflipLab/verify-sword-return-inertia.mjs, run with captured fixture
../../Saved/BodyflipLab/trimmed-sword-input.json; baseline mode uses the pre-attempt
core/jump-attack snapshots in Saved/BodyflipLab/trimmed-sword-before-*.js.

**Trimmed sword return attempt REVERTED, November 2:**
User rejected changing the established inertia. Restored core.js and jump-attack.js
exactly to their pre-attempt state: no added rotation braking or return-target
projection. Keep existing return inertia, duration, compensation and tuning.
Earlier reduced-travel test/render are evidence of the rejected attempt only.
Superseded by the scoped hand-coordinate correction immediately above.

Jump window pin (November 2, local): Pin button appended beside Delete.
Pinned window stays open on outside clicks, More options and Escape; unpinning
restores normal dismissal. Other jump markers still select normally; deleting
the selected jump hides its editor. Pin is session UI state and does not rebuild
motion or change saved jump tuning. Existing editor checks pass (89 total,
including pin/dismissal behavior); browser layout not verified. Refresh lab.

**Attack end-frame dropdown, November 2 (current, local):**
More options now contains a collapsible Attack end frames section with separate
source-frame controls for all 19 attacks, including both throws. This replaces
the single Sweep end frame field. Blank uses existing ending timing; explicit
cuts are clamped between Hit/Release and the full clip end. Saved attackEndFrames
map applies to manual and timeline attacks. Existing sweep cutoff migrates;
throw +frames settings remain the defaults when no per-attack override is set.
Source playback rate and release timing are unchanged. The selected frame starts
the existing return, seeded from that pose and velocity. Play intent is preserved.
Actual-app tests pass for all 19 cutoff/save/return cases and independent reset;
eight sweep entry/cut continuity cases also pass. Tests intercept state writes;
no live state edits, native changes or push. Refresh the lab to load the controls.
Tests: verify-attack-cuts.mjs and verify-sweep-cut.mjs in Labs/BodyflipLab.
UI follow-up: each attack now occupies its own row with a right-aligned input;
explicit grid/flex styles fix the inline labels wrapping into neighbouring fields.
Number inputs now contain the effective default instead of an empty value with
a placeholder, so native arrow steps start there (Slash RU 24 to 23, not 18).
Clearing restores the default without storing an override.

**Sweep end-frame option, November 2 (superseded UI; behavior retained):**
User explicitly accepted the sweep including its whole-body aim after the inversion
explanation. Preserve that behavior. Added Sweep end frame at the bottom of More
options, using source-animation frames17 (Hit) through35 (original End), default35.
Global saved sweepKickEndFrame applies to timeline and manual sweep kicks; other
kicks retain full clips. Entry and native playback rate stay unchanged. Recording
ends at the selected frame and derives return pose/velocity from that frame,
using existing Attack return/distance weight. Preview cache includes the cut.
Early cuts allow aim recovery through the return so cutting at Hit cannot snap
steering to zero; it always completes by the actual return deadline. Timeline
source-frame diagnostics stop at the selected frame. Playback intent retained.
Eight actual-app checks pass across full/direct entry and cuts35/24/18/17:
aim at Hit, continuous cut/return, save/sanitize and Play/pause preservation.
Existing full-turn continuity and404 normal-kick comparisons pass. No live state
writes, native work or push. Refresh existing lab; default35 preserves full clip.
Test: Labs/BodyflipLab/verify-sweep-cut.mjs.

**Sweep inversion diagnosed, November 1 (subsequently accepted November 2):**
User reports upside-down head with forward target after last correction.
Actual saved frame1.116667s: source pelvis tilt52.77deg, compensated57.46deg,
aimed126.26deg. At Hit, compensated foot ray points59.06deg below horizontal;
target ray is20.52deg above. Rigid aim pitches the complete body79.58deg
(and yaws48.50deg), producing inversion. The whole-body aiming rule preserves
limb spacing but has no posture preference and allows an upside-down result.
User subsequently explicitly accepted this behavior on November 2; preserve it.
No production changes made in this diagnosis. Read-only captured setup:
Saved/BodyflipLab/SweepFollowup/inverted-input.json; audit-sweep-inversion.mjs.

**Bodyflip sweep follow-up, November 1 (current, local):**
User reported compensation making the leg traverse the arms and a whole-body
hitch at timelineF100-105. Previous strike-only world protection caused the
first issue: the body/arms counter-rotated into the fixed leg. Sweep balance
now rotates the complete authored pose together, preserving all local joint
rotations and arm-to-leg spacing; final aim uses the compensated foot direction.
This supersedes the prior world-fixed-strike contract for sweeps only. Normal
KickL/R retain their accepted protection/balance path.
The hitch originated in recording interpolation, before balance or aim. F0-relative
unwrapped rotation vectors become singular near the completed360deg turn; at
sourceF32.5 the interpolator took a13.75deg detour between nearby recorded poses.
Circular clips now use neighbouring quaternion SQUAD with continuous angular
velocity; recorded integer-frame orientations are preserved (<2.4e-15rad).
Current displayed pelvis increments F100-105:1.598,1.251,.955,.731,.571,.460deg,
progressively slowing. Source hitch before was13.75/13.42deg atF102/103.
Six actual-app saved-target/aim-off/comp-off/twist+/twist-/flip cases pass;
arm-leg spacing error<8e-16m, authored local articulation error<9e-16rad,
final direction error<7e-16.404 normal-kick comparisons match previous code
within1.6e-16. Current collider sheet reviewed; user live playback not controlled.
Regression: verify-sweep-continuity.mjs uses the before-source snapshots under
Saved/BodyflipLab/SweepFollowup; input.json is a read-only live-state capture.
verify-sweep-current.mjs now checks local strike and arm-leg spacing, rather
than requiring the rejected world-fixed striking leg. Source FBX unchanged.
No live writes, native work or push. Refresh the lab for review.

**Bodyflip sweep correction, November 1 (current, local):**
User approved fixing sweep while keeping compensation off the striking motion
and preserving normal kicks. Circular kicks now use the existing common-body
momentum solver with the strike chain protected, instead of independently
folding spine/shoulders/free leg. Authored full body turn retained; only added
balance fades over Hit-to-End. Motion compensation checkbox works for sweep.
Sweep aiming rotates the complete compensated pose about COM using heading /
elevation, preserving all local joints. Steering fades over native follow-through
(Hit-to-End), so it no longer holds a hip offset until the final short return.
Spinning sweep aims the predicted compensated result as an explicit rigid command;
no iterative counter-rotation cancels that turn. It updates carrier/velocity and
momentum metadata; this prescribed aim is external angular drive, not passive
conservation. Normal kick/slash/throw steering stays on its accepted path.
Sweep entry/return uses the projected base that actually takes over afterward,
removing the reported2.494/1.462deg knee jumps at the final handoff.
Six offline actual-app cases pass: saved scene, aim off, compensation off, both
200deg/s twist signs and120deg/s flip. Strike orientation error<4.1e-16rad;
free joint and aim articulation errors<1e-15rad; hit direction error<5e-16.
End-handoff difference across +/-1e-7s is~1.07e-6rad (moving fall animation),
not the previous2.5deg discontinuity.414 normal KickL/R direct/full-entry
samples match checkpoint b445835d within1.6e-16. Five existing pose+slash /
kick/throw app regressions pass; playback/save checks pass. Offline actual-mesh
source/compensated/aimed sheet reviewed; live playback still needs user review.
Evidence: verify-sweep-current.mjs and Saved/BodyflipLab/SweepCurrent/
{verification.json,comparison-current.png,audit.json}. No live state writes,
Unreal/native edits or new push. Refresh existing lab to load the correction.

**Bodyflip sweep-kick audit, November 1 (analysis only):**
Accepted checkpoint pushed as b445835d8157aa8b21b913b2c75dc73c5be6d193 to
origin/codex/standalone-sim; remote HEAD matched;9591-file recovery manifest
verified. Commit includes only Bodyflip work/current saved-profile and scoped
journal handoff, excluding other tasks. Current live setup copied read-only.
Sweep: Space, Direct to Armed on, no active spin or pose; Hit1.183333s,
native End1.783333s, shared return End2.000159s. Older kick balance changes
local free hip49.70deg, shoulder33.77deg and spine01 23.51deg at Hit. Static
aiming changes only strike hip substantially:43.26deg at Hit,47.70deg at
sourceF32,48.10deg at End; steering holds until End then releases in0.217s.
At returnEnd, raw kick stays continuous but final projected knees jump
2.494deg left/1.462deg right as attackFree drops and resting projection resumes.
No sweep motion code changed. Smaller jitter not yet isolated to a unique cause.
Plan: preserve authored whole sweep/body turn, replace competing joint balance
with shared carrier compensation, steer a coherent sweep plane, and use one
continuous return to the same projected base used after handoff. Recheck target
at Hit plus full limb/velocity trajectory, including no-aim/source comparisons.
Offline harness: Labs/BodyflipLab/audit-sweep-current.mjs; stage samples and
measurements: Saved/BodyflipLab/SweepCurrent/audit.json. No live writes/GUI/native
work; audit was local after checkpoint. User subsequently approved correction above.

**Bodyflip accepted checkpoint, November 1:** User requested push before the sweep-kick audit. Includes current authored poses/shared transition controls, Keep/enable/variant options, twist aiming, Space fall option and saved-profile snapshot. Focused pose/app/attack checks passed. Unrelated native/assets/tasks excluded.

**Bodyflip authored poses, November 1 (current, local):**
Added shared Ease in / Exponent / Ease out sliders directly below Blend distance
weight. Defaults0.15 /2 /0.5 give a quicker start and softer finish. Independent
start/end easing shapes time; Exponent1 keeps common joint progress and higher
values accelerate joints with farther target rotations relative to nearer ones.
Distances are measured per local joint once at entry (including requested spin
variant); the analytic curve slows into the target and finishes at the existing
distance-weighted duration. Applies to entering/changing/clearing poses, including
the variant deformation; Keep retains the ongoing curve. Pelvis uses only the
shared time envelope. No attack-return or spin-response damping changes.
Entry/clear checks cover45/135deg joints, exponents1/2/3, monotonic motion,
exact arrival, smooth finish, seeking; authored-pose/timing/spin checks pass.
Actual-app slider/save/playback and five pose+attack cases pass, as do Keep
continuity checks. No live state writes, native work or push; refresh the lab.

Pose in, Blend distance weight, Full response and Spin response are now shared
across all poses. Only Wobble speed/amplitude remain per pose; the Wobble pose
selector sits below the shared sliders. Legacy scenes migrate the previously
selected pose's displayed values to shared settings once; subsequent selector
changes only edit wobble. Entry uses shared Pose in; No pose Out stays per marker.
Source/timing/spin and actual-app controls/save/mode/playback checks pass.
No live state writes or push; refresh the lab.

Added Invert pose variants at the bottom of More options, default off. Swaps
the positive/negative extra frames for every pose (including timing measurement
and Keep), without reversing spin commands. Serialized global setting; rebuild
retains Play/pause intent. Neutral frame and wobble tuning retained.

Added Keep pose to jump markers. It continues the active pose/wobble/filter
without restarting and follows changed spin commands; no active pose stays
unposed. Contact re-entry retains incoming pose choice and wobble clock.
Small checked-by-default enable checkbox sits below each jump marker. Off skips
all of that jump's push/spin/pose/attack planning but preserves its settings;
re-enable restores them. Editor82 and Keep/disabled-sequence checks pass;
actual-app checkbox/playback and pose+attack regression checks pass. No live
state writes, native work or push. Refresh lab to load both controls.

Zero-wobble pelvis drift corrected after user report: Snatch had zero spin,
no active physical balance, but inherited2.107deg of idle pelvis sway. A held
pose now retains its incoming pelvis basis, blending out idle sway during entry.
Source FBX pelvis remains excluded; commanded flip/twist and physical carrier
rotation remain. No pose restores the underlying animated pelvis via a relative
offset, including after body turns. Four-pose regression: held rotation drift
<2e-16rad, clear/flip/twist/seek checks pass. User saved settings unchanged.

Replaced placeholders with user recovery FBXs: Lara, Snatch, Ball and Ninja,
three frames each, keeping pose1..pose4 saved IDs. Frame0 neutral; positive /
negative spin uses Lara1/2 and others2/1, chosen by authored limb trailing.
Source SHA256 recorded; FBXs unchanged. **Corrected after user review:** all
three frames now affect only joints below the current pelvis. Source pelvis/root
orientation is excluded; the pose follows the pelvis through flips. Earlier
implementation incorrectly copied the authored pelvis rotation.

Pose entry/clear now uses the attack-return angular-distance duration rule,
with shared **Blend distance weight** on the left (default1, range0..1).
Duration = In/Out * (1-weight + weight*angle/90deg), minimum1/60s, measured
once at the start from the largest below-pelvis orientation difference. Entry
includes the requested spin variant at incoming measured velocity and initial
wobble. No pose uses the shared weight; attack tuning is independent.
24 distance/entry/exit checks and whole-body-frame invariance checks pass.
Full response tooltip now explains the speed threshold and halfway example.
Pose in is now an always-enabled left slider directly above Blend distance
weight, editing the shared base entry time across all poses and markers. Removed the old In
field from More options; No pose Out stays there. Playback intent retained.
Pose in slider maximum is now0.6s for finer dragging; existing saved tuning
and angular-distance scaling are retained.

Shared Full response speed and Spin response damping time, plus per-pose
Wobble speed and Wobble amplitude sit directly below left return sliders, above Foot/Air flip,
per the user's explicit placement. Defaults360deg/s,0.15s,1x,10%. Wobble adds
mean-relative falling-loop motion only to limbs. Spin frames use measured world
angular velocity projected on current pelvis up, with a damped response coupled
to existing momentum balance. Preserve authored joint ranges through recoil;
mask pose response off attack joints and restore it during the shared return.
Poses now hold indefinitely until a later jump selects another pose or No pose.
No pose blends to the ongoing unposed animation using that marker's Out time,
keeping the current pelvis frame. Removed obsolete Hold input; saved poseHold
is ignored. In applies to pose entry; Out is enabled for No pose. Wobble tuning
remains independent per pose; slider rebuild retains playback intent.

Source/math/sign/wobble/slider-extreme/grounded-jump checks pass. Pose layer
retains the incoming pelvis frame upright, sideways and upside-down, holds through
100s, and changing/clearing markers remain continuous while flipping. Clearing
restores the moving projected base within3e-15rad. Jump editor76 checks pass.
Five actual-app pose+attack cases cover slash, kick, Big throw and weighted
return, checking target direction, authored arms/head and phase continuity. Existing
Space-fall, throw/playback and157 duration-return checks pass. Source collider
sheet reviewed offline; live playback not reviewed. Legacy jump-motion test
fails its delay assertion on both HEAD and current code, before pose checks.
Legacy landing harness also fails exact contact/NN-seed matching on current
and HEAD; landing/NN code was not changed in this correction.
No live-state/Unreal/native edits or push. Refresh lab. Details and options:
[Labs/BodyflipLab/README.md](Labs/BodyflipLab/README.md#authored-airborne-poses---november-1-current-local).

**Bodyflip Space falling animation, November 1 (current, local):**
User accepted twist + attack after switching OFF 3D momentum; that resolves the
reported residual tilt for the selected axis-controlled behavior. No physics
code or saved setting was changed during the tilt audit. Its seven offline
comparisons distinguish full-3D residual body rotation from the ordinary attack
return; the earlier joint-only return check did not establish global uprightness.

Added **Falling animation in Space** at the bottom of More options, default off
and disabled in other modes. Space previously used only the idle loop as its
base. On blends into the existing Loop_Fall at the first marker (time zero if
there are none), using Jump blend. Attacks return to that ongoing animation.
Only local limb/spine rotations change; root/pelvis base, gravity and push rules
remain. Actual-app checkbox/rebuild/playback test passes: final aimed direction
error2.85e-10, return articulation error<4e-15rad, no added root drift, off
restores the original pose exactly. No live state writes, native/Unreal work or
push. Reload the lab, then enable the checkbox. Details: Bodyflip README.

**Bodyflip twist + melee aim, November 1 (local; accepted with 3D momentum off):**
The saved SlashL /200deg/s twist now aligns the final contact direction at Hit:
147deg error before,0.000034deg after. User scope is direction only. Predict
body orientation at Hit, reuse air-attack heading/elevation, then fit those two
angles against the actual compensated trajectory. No separate arm correction.
The old predictor fitted a different rotation order and balance cancelled its
whole-body heading. Deliberate aim heading is now an explicit angular command,
like existing flip/twist; internal articulation still receives compensation.
This changes total world angular momentum during the aiming turn; it is NOT
passive torque-free conservation. Heading stays continuous across180deg.
12 actual-app cases pass (both twist signs, flips, combined motion, slashL/R,
jab, pike, kick, zero-spin); arms/head and shared return retained. Accepted
zero-spin pose matches exactly; throw/playback and focused return checks pass.
Offline collider contact sheet reviewed; user subsequently accepted axis-only playback.
Preparation is cached,7-16 trajectory evaluations; no native runtime performance
claim. Live settings, Unreal and native files unchanged. No commit/push yet.
See [current implementation and verification](Labs/BodyflipLab/README.md#twist-and-melee-aim---november-1-local).

**Bodyflip target-point spear aim, November 1 (accepted for push):**
User confirmed the targeting works and requested a push.
Accepted state was pushed first as5b2a2da6 on origin/codex/standalone-sim;
remote HEAD matched and recovery manifest verified. Current spear default now
fits the actual release shaft/origin to the target, fitting heading/elevation
through spine01-05. Explicit throwDirection and small
throw azimuth keep their earlier behavior. For spinning bodies, fit against the
complete momentum-compensated trajectory; no projectile velocity redirect.
Full-charge spin prediction also avoids recursive carrier-velocity reads.
396 target cases,4 physical cases and actual-app spin/retarget/playback pass.
Matched checkpoint poses for slash/jab/kick/small/explicit-ray throws:15,860 bone
comparisons, zero position difference. FinalNoAim16,918 checks and157 return
checks pass. Agent validation was offline CLI/DOM; user acceptance followed.
No live state writes, Unreal changes or native port. See Labs/BodyflipLab/THROWS.md.

## November 1 accepted Bodyflip throw checkpoint

Accepted standalone motion before target-point aiming experiments: FinalNoAim
throw sources, shared spine transfer/return, distance-weighted return duration,
attack joint-limit exemption and playback intent preservation. Includes current
saved-profile.json (snapshot of live state; live state itself is not changed),
final source exports/import tools and focused checks. 16,918 final-source,
157 return checks and the actual-app playback/retarget harness pass.
Unreal, native packaging and other tasks are outside this checkpoint.

**Bodyflip current status, November 1:** option edits now retain playback intent.
Temporary slider/loading pauses no longer cancel Play. The latest successful
rebuild resumes if it was running; paused stays paused; explicit Pause, seek,
failure or hiding the lab cancels resume. Rapid/same-key edits, motion/loop/attack
selection and mode restoration are covered. Actual app race checks, generation
invalidation,16 refresh checks and30 trim/seek checks pass. No GUI or live writes.
Details: Labs/BodyflipLab/README.md.

Current throw behavior: corrected throw coordinate conversion
and removed resting-limit projection during authored attacks/return. User clarified
that root is only a coordinate frame and attacks may exceed limits. Normalize
source pelvis into the initial root frame BEFORE interpolation, then distribute
through spine01-05. Preserve authored arms/head; shared target tracker does not
re-clamp or speed-limit attack poses. Duration-based return restores
the base pose before normal projection resumes. Saved Big throw finalF34 head/
launch3.98deg (source3.98), F39 14.81deg (source14.71), previously60.92deg.
Matched-frame final head/hand and head/chest errors below1e-6deg; arbitrary root
reframing including subframes changes articulation by<3e-14deg. Source clips,
live state, Unreal and native package unchanged. Reload lab. Offline actual-app
checks only; no GUI/raster verification. See Labs/BodyflipLab/THROWS.md.

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

**Bodyflip Big throw source end F50, November 1 (latest):** user identified the
long comeback in the base clip. Big throw now supplies source phases.end50 to
the shared jump-attack path, retaining its fast direct-to-Armed entry. Shared
end time is hit/release time + (sourceEnd-sourceHit)/playbackFPS, not sceneF50.
At default60fps, F34 Release ->F50 End is16/60s, followed by normal Attack out.
Small and slash endpoints are unchanged; original full FinalNoAim/reference
clips remain intact. Captured throw app replay: Release0.60s, End0.8667s,
returnEnd1.1167s with zero residual aim twist; release packet unchanged.
16,918 final-source/shared-return/timing checks include varying entry duration,
delay and0.5/1/2x speeds; actual-app checks and76 jump-track checks pass. No
live settings/loop edits, GUI or native build. Reload. Details THROWS.md.

**Bodyflip shared slash/throw return restored, November 1 (latest):** user
rejected throw-specific recovery. Removed the initialLaunch return timing branch
from attack-aim.js; both now hold aim through clip End and fade over the existing
Attack out to returnEnd. Throw body/compensation already delegates to jump-attack;
no second body-return implementation added. FinalNoAim source/timing/launch kept.
16,882 checks include both throws versus the shared slash path over61 samples,
pose/quaternion equality and identical aim envelope;27 shared pelvis-return
checks and actual-app retarget/reference checks pass. Captured throw-scene app
replay: aim1 at2.20s,0.5 at2.325s,0 at2.45s; residual pose angle1.1e-16rad.
Loop cut is important: current trimOut2.0833s is before that return starts.
Do not claim playback inside that loop shows the return. User currently switched
live saved attack to slashL; replay used the preserved throw input snapshot.
No live state/trim edits, GUI or native build. Reload source. THROWS.md has details.

**Bodyflip FinalNoAim import and return, November 1 (latest):** user explicitly
identified Exports/Throws/FinalNoAim/HANDOFF.md. Previous Bodyflip source was NOT
that bake. Full-charge Big/Small now sample its clips.json directly, no repeated
hand/forearm/source shaping or source aim. Original60fps preserved; removed1.8x
animation retiming. Manifest launch velocity/spin transported by held orientation
with carrier translation; explicit handoff supersedes previous hand-derivative
launch contract. Geometry/binds match ThrowLab objects.json. Partial Small retains
legacy procedural source (the supplied bake is100% only). New importer records
SHA256 for clips/manifest;10,416 exact-frame/timing/launch/return checks pass.
Aim turn now fades from Release to authored clip End, instead of staying full
through source recovery. Actual app replay has zero remaining aim pose rotation
at End (<5e-16rad), shaft error0deg and travel2.13deg off goal (source manifest
already2.08deg shaft/travel difference). App retarget/reference checks pass.
No GUI/live state edits/native rebuild. Reload lab. Details Labs/BodyflipLab/THROWS.md.

**Final unaimed throws baked, November 1:** user requested both final animations
for another lab, explicitly selected100% Small. Outputs:
Exports/Throws/FinalNoAim/{BigThrow_Final_NoAim,SmallThrow_Final_NoAim}.fbx,
plus clips.json for26 lab bones. Both Aim off; current saved pose edits baked,
full89-bone source hierarchy retained. Big131/Small69 samples at60fps; releaseF34.
FBX reimport all-bone/frame checks pass, max position error2.97e-7m. Small100%
has no saved keys, so matches source motion; partial-charge shaping remains
procedural. Grip/scale/launch physics in manifest, not reapplied pose edits or
animation retiming. Source/live-state/Unreal assets unchanged; no editor/build.
[Short receiving-agent handoff](Exports/Throws/FinalNoAim/HANDOFF.md).

**Bodyflip rearward heading correction, November 1 (latest, partial):** user
authorized fixing backward-facing/downward launch, explicitly forbids declaring
success on unrelated fixtures. Replaced shortest-arc throw steering with world
heading then elevation. Additive throw spine aim is no longer clipped by the
standalone rest22deg spine cones; source projection and other joints remain,
native profiles retain limits. Actual saved-scene app replay now yields shaft
error0deg and vertical release+2.549m/s (before44.15deg/-16.969m/s). Heading
turn-176.79deg, elevation-5.95deg. Offline before/after pose plot inspected.
NOT fully fixed: velocity is still42.94deg from requested direction; unaimed
adapted motion already has47.64deg hand-velocity/shaft mismatch. No redirected
projectile velocity was added.951 direction checks, six motion cases/2,000
transfer checks, actual app checks and four shared physical cases pass. No GUI,
live state edits or native build. Details Labs/BodyflipLab/THROWS.md;
Saved/BodyflipLab/ThrowSceneAudit/{scene,results}.json and release-comparison.png.

**Bodyflip actual saved throw failure, November 1 (latest investigation):** user
rejected the displayed result again. Read-only actual-app replay of state.json
(Space, big throw, target[-.83778,2.43491,-3.27299], compensation1, transfer on)
reproduces release shaft44.15deg and velocity81.51deg off the fixed world goal.
Aim solution residual0.75163; correction quaternion[.80441,.57225,-.15955,.00254]
is nearly180deg around a tilted axis. The newly introduced shortest-arc rule
can fold the torso for a rearward target; final22deg spine limits also constrain
the correction. Earlier app tests exercised different targets and do not validate
this scene. No further production change in this investigation. Do not claim
the throw fixed. Offline replay: Labs/BodyflipLab/audit-throw-scene.mjs;
Saved/BodyflipLab/ThrowSceneAudit/before.json. No GUI/live scene writes.

**Bodyflip continuous throw spine steering, November 1 (latest, local):** user
reiterated original-to-authored-direction rotation through the spine, preserving
relative arms. Throw aim no longer converts its endpoint into projected joint
coordinate offsets and replays them on every pose. It retains one quaternion,
smoothly blends it over entry/release/return, and applies cumulative20/40/60/80/100%
world rotations over spine_01-05. Spear uses shortest-arc direction rotation,
avoiding an additional heading/elevation roll; Small remains yaw-only. Existing
pelvis-transfer option and motion compensation remain. Final legal projection
and endpoint calibration remain; no arm offsets are added by aim.951 direction/
intermediate-arm checks, six motion cases/2,000 transfer checks, actual app
release/retarget/reference toggle and four shared physical melee cases pass.
No raster verification or claim that the separate hand/shaft velocity mismatch
is eliminated. Source-only; reload. Details: Labs/BodyflipLab/THROWS.md.

**Bodyflip spear launch/reference repair, November 1 (current, local):** same
Throw Lab `big throw.fbx`, with its approved grip/key edits. Previous correction
dropped the profile's 1.8x speed and axial spin, introducing transverse hand
angular velocity. Restored configured shaft-axis spin; apply speedScale to
animation timing, keeping linear release velocity derived from the final hand
trajectory. Current-settings fixed-base audit: 9.83 -> 17.66m/s (Throw Lab18.34),
initial transverse spin13.18 -> 0rad/s; first25ms shaft turn16.30 -> 1.73deg.
Remaining aerodynamic turning is real: hand travel is still24.75deg from shaft;
this does not prove full alignment or eliminate all in-flight turning.
Vanilla checkbox now shows **THROW LAB REFERENCE** for both throws: full-body
approved100% source plus held/released weapon and original target/floor. Cached
reference flight adds no runtime physics world.49,864 source/reference checks,
app render/toggle/retarget test, six motion cases,60 drift and130 direction checks
pass. No GUI/raster, live state writes, Unreal/native build or tuning edits.
Reload lab. Details: Labs/BodyflipLab/THROWS.md; ThrowLaunchAudit evidence.

**Bodyflip authored throw direction, November 1 (current, local):** user
clarified spine-only steering with unchanged relative arms, then replaced the
moving-point aim objective with an authored absolute world direction. Optional
per-event `throwDirection: [x,y,z]` is normalized and persisted. Without it,
the lab uses target minus pelvis position at `segment.jumpStart` (jump frame 0).
The frozen origin is captured from world poses, before physical aim prediction;
spine corrections and subsequent body drift/spin cannot change the goal. Spear
uses the vector; Small throw its horizontal bearing, preserving the arc.
Target edits reauthor the default ray from that same frame-zero origin; explicit
vectors ignore target edits. Viewport guide displays the frozen world ray.
130 direction/relative-arm checks, six motion cases, app target-edit/release
checks, 33 scene checks and four shared physical cases pass. Source-only change;
reload lab. No GUI, saved-state overwrite, Unreal/native package or arm edits.
Earlier pending wrist/forearm question is superseded, not an outstanding choice.
Details: Labs/BodyflipLab/THROWS.md; Saved/BodyflipLab/ThrowDirection/results.json.

**Bodyflip throw motion, November 1 (historical; question superseded below):**
User rejected the saved-impulse approach. Throws now use the shared upper-body
attack path: optional equal transfer over spine_01-05, legal arm entry, motion
compensation, soft legs/amount and recovery. Imported Throw Lab target aiming
is disabled. Bodyflip throw aim uses upper-chain heading/elevation only (bomb
heading only), with no free roll or pelvis/whole-body tilt fallback. Release
linear/angular velocity comes from the final held object's pre-release motion;
no saved impulse/spin is added. Throw speed changes animation rate; zero disables
that throw. No live state edits, GUI use, Unreal work or native repackaging.
Checks: six compensation/aim cases, 2,000 spine shares, 60 drift/rate checks,
app release-velocity checks, source parity and shared melee physics pass.
Remaining: adapted spear shaft is ~48deg off hand-driven travel; original source
is already ~17deg, increased by retargeting/arm projection. Asked whether to
adjust forearm/wrist motion or preserve source pose; superseded by the newer
spine-only, authored-direction instruction above.
Do not restore the saved impulse or claim complete throw acceptance. Evidence:
Saved/BodyflipLab/ThrowMotion/results.json; Labs/BodyflipLab/THROWS.md.

**Bodyflip throw release aiming, October 31 (rejected/superseded):** Big throw now
aims the spear shaft from its geometry origin at Release. Small throw solves
world yaw only so launch stays in the target's vertical plane and retains its
upward arc; target height cannot flatten it. Replaced attached-hand/source
derivative subtraction (false lateral impulse from retargeting/projection) with
body COM translation plus pelvis angular transport. Imported throw impulse,
charge/speed, gravity and aero unchanged. 20 release cases + 12 prescribed
carrier cases, 72 direction/spin cases, 54 drift checks, app retarget checks,
49,314 source parity checks and 4 shared physical melee cases pass. Reproduced
stationary spear has 1.34cm lateral deviation at nominal target flight time;
shaft unit-vector error below 9e-9. This is not an exact ballistic-hit guarantee.
Reload lab; no live state edits, GUI, Unreal build or native repackaging.
Details/evidence: Labs/BodyflipLab/THROWS.md, Saved/BodyflipLab/ThrowAim/.

**Bodyflip target-move crash, October 31 (current, local):** fixed projectile
shape lifetime in `projectile-world.mjs`. Retargeting destroyed the released
spear's body and its scaled collider, leaving a dangling cache entry; the next
spawn failed inside WASM (reported function signature mismatch; offline replay
produced table index out of bounds). Cache now owns an explicit reference until
disposal. 36 projectile rebuilds, 6 target inputs + 6 drag-path edits in the actual
app-script harness, and 10 existing projectile checks pass. No live scene writes,
GUI use, Unreal or native package changes. Reload lab to load fix and clear the
crashed instance. Details: Labs/BodyflipLab/THROWS.md.

**Bodyflip full-strength aim, latest October31:** removed Aim percentage slider;
Aim on/off remains. Enabled timeline/manual/held/physical aiming always uses100%.
Legacy saved aimWeight is forced to1 on load/sanitize, covering older80% scenes.
Frozen KickL replay now hits3.2304cm from centre inside12cm target. Legacy migration,
33scene checks and syntax pass. Refresh loads; no saved-state overwrite, GUI use,
Unreal or native package changes. Details in Bodyflip README/full-aim.json receipt.

**Bodyflip KickL aim audit, latest October31:** user accepted distributed transfer.
Current saved Space kick misses because Aim is80%. Reproduced reported26.7526cm
surface miss; identical inputs at100% place contact3.2304cm from centre, inside
12cm target. Kick path is separate from spine transfer. No settings/source edits.
Evidence Saved/Diagnostics/BodyflipKickAim/; details in Bodyflip README.

**Bodyflip optional distributed pelvis transfer, latest October31:** unconditional
spine_01 transfer removed; default scheduled/manual attacks retain authored pelvis
and spine rotations. New More options checkbox **Spread pelvis turn across spine**
(defaultoff, last) keeps the base pelvis and distributes the attack pelvis delta
20% each over spine_01–05. Full chain recovers original upper orientation before
limits/aim. Motion compensation remains separate; user's conservation complaint
is not resolved/validated by this option. Post-Hit recovery now removes compensation
relative to authored motion, preserving its follow-through.1046 distribution and
1068 authored samples +24manual checks pass; arm-entry/arming/torso/scene checks
pass. Saved settings untouched; no GUI/native package/build/push. Refresh loads.
Details: Labs/BodyflipLab/README.md, Saved/Diagnostics/BodyflipAuthoredPelvis/.

**Bodyflip Motion compensation checkbox, October31:** appended at the end of
More options after Vanilla attack only; default on preserves previous behavior.
Off bypasses existing upper-body attack pelvis compensation (soft and rigid) for
scheduled/manual paths, retaining Amount % and Soft legs. Rechecking restores
them. Uses preserve-time regeneration and scene persistence; does not disable
aim, pelvis transfer, joint limits or separate flip balance.608 pose comparisons,
33 scene checks and syntax pass. Saved scene/native/editor unchanged. Refresh
loads the checkbox; details in Labs/BodyflipLab/README.md.

**Bodyflip vanilla inspection, latest October31:** appended More options checkbox
Vanilla attack only (default off). Displays original full-body source directly,
including pelvis/root motion, bypassing all motion corrections in the display.
Armed-aligned source clock makes current F100 slashL source F13.9364; original
pre-Armed frames and held endpoints. Display-only, persists per scene, no generation
on toggle; hides scene/debug overlays.267 focused checks +33 scene checks pass,
syntax checked, no GUI use. Saved settings/native/editor unchanged. See latest
Labs/BodyflipLab/README.md section. Refresh loads the new control.

**Bodyflip F95–F100 investigation, latest October31:** vanilla comparison and
stage audit confirm an introduced motion shape. Original pelvis turn is moved
into spine_01 (vanilla local twist~0deg); first +/-22deg clamp suppresses lead-in
until F96.2657. Active opposite-pelvis/soft-leg compensation counter-rotates that
spine to preserve upper world orientation, but a second clamp breaks preservation
from F98.9361. F100 same-input chest speed941->384deg/s; bypassing only that last
spine clamp restores941 (diagnostic, not a fix). Flip balance inactive, separate
attack-inertia solver still active. Current target changed; first audit aim-speed
numbers describe the previous target. No production/tuning/editor changes. Detailed
intent/stages/evidence in Labs/BodyflipLab/README.md and
Saved/Diagnostics/BodyflipUpper95Followup. User withdrew under1s requirement.

**Bodyflip context refresh — October 31, latest handoff.** Read the
[current lab status](Labs/BodyflipLab/README.md#context-refresh-handoff---october-31)
before resuming. Per-mode timelines are implemented and verified (33 checks):
Run retains the two jumps; Space is empty. First app reload must be Ctrl+R,
because the old Refresh button saves its stale state first. No desktop control.
The earlier slash/performance work is **unfinished, uncommitted lab-only work**:
warm generation measured2.74–3.01s, cold5.99s including3.20s landing NN; user
requires below1s. Latest aim preserves authored arm motion and fits direction,
not exact contact; earlier near-zero-contact and native-parity claims below do
not validate this version. Bounce test has an unresolved loading-velocity failure.
Native package is still the earlier891446-byte version; do not assume lab/native
parity. Detailed changes, tests, limitations, saved-scene migration and resume
steps are in the linked README. Preserve accepted flipless motion, existing
settings and other agents' dirty files. No broad cleanup, GUI use, Unreal build
or push was performed for this handoff. Latest request was documentation only.

**Spear October30 — pike-only actor complete and saved:**
`/Game/_mygame/spear/A_Spear` uses Big Throw's saved mesh scale
(.862342759,.883492713,.761916187), no slash admission or hilt/deferred depth cap.
Forward release waits for the entire spear/pommel plus assumed15cm target;
withdrawal and authored resistance remain. Four native regressions and five
actual Blueprint Play cases pass, including flesh/full blade stain/collision
restore and original sword hilt stop. Saved status3,43,494tris,17Jolt-valid hulls;
derived collision-only FBX preserves all render/shading/socket data. CCD on,
MACD off; inherited test launch and two tick prints disabled only in the copy.
Disk reload/default checks and3,991-pin audit pass; original sword, PoseAgent,
two maps and both Throw Lab state/profile files remain byte-identical.
Successful normal `build-ccd.log` DLL snapshot tested; no Live Coding. Later
whole-checkout retries cancelled under paging pressure, no claim on unrelated
agents' later builds. Owned host45696 has completed editor shutdown; Main Menu
and user Play untouched. Big Throw controller attachment/release/flight wiring
remains the separate pending port. Storage follow-up: about625MiB of owned test
host/build data remains; automatic approval review blocked full-host and narrower
cache-only cleanup. Nothing deleted. [Evidence/usage](Docs/SpearPike.md).

**Foot IK October30 - lossless optimization after user approval:** Host-only
slide-entry dependency caching and slide-joints redundant-work removal preserve
20,121 complete frames and 10,400 joint comparisons exactly. Sixteen sequential
slide cases total121.80->90.56s (1.345x); no motion tuning, shared solver, arms,
settings, viewer or server changes. Original source and parity receipts retained
in Saved/FootIKLossless20261030. Native port/packaging verification is separate
and still in progress. [Details](Labs/FootIKLab/README.md).

**Foot IK October30 - native integration built; final checks pass:**
Accepted lab/setup remains remote76614437. Build35 succeeds with normal dynamic
UBA/NoPCH. Set Foot IK Enabled / Configure Live Foot IK / Get Live Foot IK State
are available; default off, no Blueprint wiring/tuning/assets changed. Held-input
forecast invalidation now survives its normal turning speed-cap changes; real
input/facing/tuning changes still cancel. Actual moving/turning/reverse/stop/
re-enable checks pass twice. Real ramp, surface lifecycle, Jolt target/feedback
and elevated/sliding Bodyflip handoff pass. Terrain exit now preserves its full
accepted pose for the first NN predecessor, beside ordinary current/history
feature encoding: final-native-23 gives zero endpoint error, ten new policy
publications and return retirement. Canonical exit may have zero remaining
correction; test requires a real corrected episode, not artificial exit influence.
Cold Build35 BP compile/Play passes status3/properties0/pins0,60ticks/25targets,
public disable call, unchanged BP/map hashes. Owned test editor closed.
Exact packaged solver48cases/26,296frames, including the shoe-corner optimization;
no position/quaternion-component/scalar differences. Private lower-only forecast
222frames/26,466values exact (4,571->2,028ms); discarded initial work4,923frames/
43checkpoints exact (1,141->797ms). Engine NN26fixtures/1,876poses within0.0003;
coupled3,214frame semantic parity retains backend drift up to5.2mm/4.19degrees.
**Limit:** this is not unconditional realtime1:1 parity. Under CPU/memory pressure,
stair forecasts can miss their deadline and expose current raw NN; a retained
trace shows a correction interruption. Slide entry also remains costly. Exact
finite box/box-convex collision and explicit incline mode are the supported scope.
No late stale pose, shortened horizon or relaxed contact gate hides those limits.
Reuse NativeHost; no new host/model copies. Automatic approval review still
blocks about845MiB of owned temporary-cache removal; preserve cleanup receipt.
[Usage, evidence and limitations](Docs/FootIKNative.md).
**Foot IK October30 - F82 clearance entry / F123-131 hand stall:** Replaced the
hard .7rad/contact switch between wall-search methods with continuous shoulder
gradient correction throughout. Seed arm history before clearance starts and
briefly limit entry acceleration, fading as contact settles. Current yaw-stop10m
replay: left80-83 peak266.31->26.67m/s2; right123-132 peak211.78->11.99m/s2,
upward relative travel stays positive and19/19 contact ticks retained. Roots
exact; full joint/wall checks pass. Stop12m regression retains F145 fix/contact.
Host slide-arms.js only. Reload pending; visual review remains with user.
[Details](Labs/FootIKLab/README.md).

**Foot IK October30 - F145 right-hand yaw-stop correction:** Root yaw ends at12m
(F144.5); contacting hand now eases its world velocity through abrupt heading
changes using existing constrained arm IK. Root/timing and all poses through144
unchanged. Replay spike88.77 to19.37m/s2, contact144-150 retained, wall/joint checks
pass. Host-only; full viewer reload pending, user doing visual review.
[Details](Labs/FootIKLab/README.md).

**Foot IK October30 - release smoothing implemented:** Releasing arms now bound
angular acceleration; wall-safe repair starts from that prediction. Recorded
left136-140 peak acceleration72.86 to44.02m/s2; wall/joint checks pass. Right138
fix retained; torso guard stays removed. User requested quick implementation
and will visually review; full viewer reload pending. [Details](Labs/FootIKLab/README.md).

**Foot IK October30 - torso guard removed at user request:** The finite-torso
avoidance/front route caused a velocity hitch at F105.5 and has been removed.
The independent continuous shoulder-gradient fix for the F138 right-hand kick
remains. Recorded replay: right136-140 peak acceleration11.73m/s2 (original312.69),
wall/joint checks pass over317 slide ticks. Left-arm torso crossing is unresolved
again; do not claim self-clearance. Host slide-arms.js only; surface/NN/legs/tuning
unchanged. [Details](Labs/FootIKLab/README.md).

**Throw Lab October29 - checkpoint pushed; first native control/motion port built:**
Approved lab plus exact saved setup pushed as a193d263; remote hash verified.
Snapshot/hash manifest: Labs/ThrowLab/approved/2026-10-29/. Native Begin/Play,
Release/Cancel/State nodes and pose evaluator added; physical velocity/twist
controls only, with nonphysical settings mirrored from that snapshot. Runtime
profile: Content/ThrowLab/Profile.json. Normal Editor DLLs current;4/4 native
checks pass,1392 poses, max position1.92e-11m and launch error2.10e-14. Every
game frame publishes authored motion (including odd-frame keys); accepted pose
feeds NN recurrence. Reflection status3/properties0/pins0/wiring preserved;
PoseAgent/TestNN hashes unchanged. No interactive main editor or user Play.
Headless Fab startup crashed before tests; retry with process-only DisablePlugins=Fab
passed. Evidence Saved/Diagnostics/ThrowPort20261029/. Projectile attachment/Jolt
flight/aerodynamics and actual Play verification remain pending; this is not a
completed physical throw pipeline. [Native scope and procedure](Docs/ThrowControls.md),
[lab details](Labs/ThrowLab/README.md).

**Throw Lab October29 - hand hard stops fixed; motion detector added:**
Current37%/.06 had added hand velocity jumps at charge cutoffF6.66 and return
F24.8796. Cached finite FK velocity carry now joins both smoothly, with up to8F
follow-through (current peak~36.28deg vs32.37 before). Release/launch controls,
body/head/clavicle motion and user keys preserved;100%/Big bypass retained.
Whole-timeline all-bone detector scans/refines speed/angular-velocity jumps;
18 charge/speed cases pass and old code is a required negative control.
Source/retimed-key changes reported separately. Current-scene command:
node Labs/ThrowLab/verify-motion-current.cjs. No live state or desktop takeover.
992 prefix/992 pose/12 launch and isolated UI checks pass. Captures hand37-
before/after and audit receipts in Saved/ThrowLab. Refresh loads.
[Details and limits](Labs/ThrowLab/README.md).

**Throw Lab October29 - clarified clavicle correction:**
User meant clavicles, not spine. Reverted whole-torso early unwind; only the
two clavicle wind-up residuals now relax through the throw. Pre-misread
head/spine/pelvis/legs restored within5.6e-16; quadratic effort retained.
Current37% atF26 clavicle neutral deviations left19.13 ->4.31deg,
right8.20 ->1.80deg. Native throwing arm/palm retained by shoulder compensation.
992 prefix/992 pose/12 launch and isolated browser checks pass. Receipt:
Saved/ThrowLab/clavicle-correction.json. Presets untouched; Refresh loads.
[Details](Labs/ThrowLab/README.md).

**Throw Lab October29 - quadratic Small Throw body effort:**
Remaining body motion now uses charge squared (50% ->25%,100% unchanged).
Reached wind-up/velocity retained to avoid the prior head reversal. Arm arc,
release timing and velocity multiplier remain.43% peak head13.904 ->11.278cm,
chest5.779 ->4.154cm;5% head0.841cm.992 prefix/992 pose/12 launch and isolated
UI/head-path/Aim/Half/undo/Refresh/velocity tests pass. Presets untouched.
Refresh loads it. [Current behavior](Labs/ThrowLab/README.md).

**Throw Lab October29 - Small Throw velocity slider added:**
Left Throw velocity0-5x slider multiplies all Small Throw charge velocities.
Shares saved speedScale with existing Amplitude; preserves presets and supports
undo/redo/Refresh. Motion, release, twist and Big Throw retain their behavior.
Isolated actual UI/3x launch/Jolt replay checks at0/5/43/100% pass; UI inspected.
No live-state edits. Refresh loads it. [Details](Labs/ThrowLab/README.md).

**Throw Lab October29 - current43% head/body reversal corrected:**
Saved43%/.06 slowdown A18/R34 reproduced in an isolated viewer. Prior amplitude
fade pulled the reached lean backward atF10.75-14.25, then forward again despite
continuous endpoints. Removed that fade: retain reached pose/incoming velocity,
scale remaining body motion, settle residual velocity over4frames and release
its offset during original recovery. Root/pelvis/spines/head/support arm share
one source clock; native throwing-arm/palm path and slowdown control retained.
Quarter-frame full-cycle traces now show one forward/return head peak (Z F26),
with no intermediate reversal. Current saved presets unchanged.5% head travel
1.679cm and chest0.705cm; world motion stays bounded by full throw and grows
with charge.992 prefix/992 pose/12 launch, isolated UI/undo/Refresh/Aim/Half and
818-pose/84-launch checks pass. Captures/head rotations: Saved/ThrowLab/head43-
before/ and head43-after/, comparison GIF beside them. No live-state/Unreal
edits or push; Refresh loads it. [Current behavior](Labs/ThrowLab/README.md).

**Throw Lab October29 - Small Throw slowdown blend added:**
Remove slowdown slider under Throw % blends source-animation speed from current
slowdown at0 to1x at1; default0 preserves behavior. Stored per throw/scene with
one undo group per drag and Refresh retention. Forward stroke, entry and actual
release shorten together; wind-up/trigger, cut arc, launch strength/twist and
body motion retain existing behavior.33% A18/R34 rates0.19208/0.59604/1 at slider
0/0.5/1, release F21.94/11.0961/9.0133. Numeric25-rate/12-Jolt-case checks and
isolated UI slider/undo/Refresh/fast Aim/Half/release checks pass. UI inspected.
Prior armed-plateau fix retained: shortened source segment advances continuously;
source arm/palm poses preserved,50% arc≈42.91° from actual neutral. The body amplitude fade was superseded by the head/body correction above. Current
keys/presets,100% and Big Throw retained. No live-state/Unreal edits or push.
Refresh loads the option. [Details and verification](Labs/ThrowLab/README.md).

**Throw Lab October28 - bomb UE5 scale omission corrected:**
Saved A_Bomb bomb_GEN_VARIABLE mesh component uses RelativeScale3D=(2,2,2).
Previous lab matched raw geometry but omitted this Blueprint scale:11.2cm body
diameter versus UE5's22.4cm. Bomb render and collision now bake the2x component
scale around the shell centre; hand offset and user's per-throw scale remain.
Read-only guarded UE5.7 package/tag inspection in inspect_bomb_scale.py avoids
opening Unreal (no main editor remote node). Blueprint/source hashes retained
in cache metadata; prepare_objects.py --bomb-only reproduces only this update.
Backup: Saved/ThrowLab/BombScale-20261028-223534/. Source-size/topology,
attachment/release/contact/replay,818-pose/84-launch and isolated browser checks
pass. Live lab state, sword/spear and UE5 assets unchanged. Refresh loads it.
[Lab details](Labs/ThrowLab/README.md).

**Throw Lab October28 - Small Throw bomb default / optimized spear refreshed:**
Object selection is independent per throw, persisted as throwObjects. Small
Throw defaults to Bomb on legacy-state migration; later explicit choices survive
switching, scenes/copy, undo and Refresh. UE5 bomb-feature mesh already matches
the lab: CC0_-_Bomb/cc0_bomb,1,799 vertices/2,622 triangles including curved fuse;
exact topology and<5.1nm rounded vertex error verified against BombFuse geometry.
Refreshed Imperial Spear from supplied mainFBX:22,559 vertices/43,494 triangles,
2.25223124m,17 UCX hulls; SHA256
e1dbb2b1414c32d180d75d5c3214f0c667abe695647f250c1bf0962449ef6814.
Importer accepts direct/indexed corner UVs. Existing atlas/bind/hulls, sword/bomb
cache and live scene bytes preserved. Backup: Saved/ThrowLab/WeaponRefresh-20261028-222819/.
Focused object migration/source checks, Jolt grip/contact,818-pose/84-launch and
isolated browser checks pass. Existing8893 service now available; browser tests
also verify previous spear-axis aiming change, independent objects, override,
undo and Refresh. All test state writes isolated. No desktop/Unreal/source edits,
service restart or push. Refresh loads new defaults/cache.
[Lab handoff](Labs/ThrowLab/README.md).

**Imperial spear October28 — selective topology reduction complete:**
New editable `Exports/ImperialSpear/ImperialSpear_Optimized.blend` and refreshed
mainFBX preserve final user grip/blade transforms.59,460→43,494triangles(-26.85%);
guard/crown/scrolls/pommel selectively reduced, sampled deviation<0.04mm.
Matched PBR close-ups, source UV/normal/topology checks and actualFBX readback pass.
Original atlas/shared material,17 corrected UCX hulls and4 sockets preserved.
Original Working.blend/open user Blender and all lab/Unreal state untouched.
Older GLB/LODs/Source/Game blends/reports remain historical. Current details and
recovery: [Imperial spear handoff](Docs/ImperialSpear.md).

**Throw Lab October28 - aim by spear orientation at release (local):**
Aim at target now turns the agent so the actual held sword/spear shaft points
directly at the target at the fractional Throw frame. Cached two-angle solve
includes weapon origin movement, grip offsets and hand/forearm keys. Full keeps
whole-body yaw plus distributed spine pitch; half distributes yaw/pitch across
five spines with fixed lower body. Armed FK entry unchanged. Original speed,
twist and velocity-to-shaft angle remain; Align velocity to spear still makes
them parallel. Bomb aiming retains spine_05/velocity reference. Spear aiming
works at zero speed; no ballistic compensation or post-release homing.
818 pose/84 launch cases pass, including forward shaft ray/target intersection,
fractional release, zero/reversed-speed independence, fixed half legs and no
added pelvis tilt. Initial browser run could not complete while8893 was down;
the subsequent weapon refresh above verified the shaft-reference change against
the available existing service in an isolated browser, including undo/Refresh.
No live state edits, desktop takeover, Unreal work or push. Refresh loads it.
[Current lab handoff](Labs/ThrowLab/README.md).

**Main-menu scene October30 — native menu implemented / tuning ready:**
Reference menu now lives in isolated Unreal lab: vector triple borders/corner arcs/
diamonds, translucent crimson glass, Cormorant SC small caps, selected-row glow
and hover crossfades. Exact1280-reference frame112/66/400/544; cached licensedfont
and explicit tracking.18 numeric+slider Menu controls, menu-only reset and Show
menu use Save/Revert/recovery. Tab opens right-hand studio on Menu; clean menu
opens by default. Mouse/keyboard/D-pad actions work in scene-preview scope;
Continue hides menu/Escape returns, New Game confirms mannequin/water reset,
Load Game has no saves/backend, Settings opens tuning, Quit confirms Save/exit.
Normal build and native input/hit-target/keyboard/modal/save-revert checks pass;
1280/960/1920 renders and extreme panel/font bounds inspected. No scene material
or background tuning changes; prior44168 saved/closed, clean review55888 opened.
Evidence Saved/MenuUI20261030, menu-*.png, Validation/menu-controls.json. No desktop
input, main-project wiring changes or push. Read current UI/lab docs before edits.
[UI handoff](Docs/WeaponWheelUI.md), [controls](Labs/MainMenuSceneLab/README.md).

**Main-menu scene October30 — approved finite-card reflection checkpoint:**
User rejected wavy/flat/wavy distance bands. Removed that extra wave layer and
ring-normal broadening. The original seeded impacts now cover their full support.
Seven cards are reflected by ray intersection with their actual common X plane,
finite bounds and original emission profile, replacing the native planar 200cm
sphere approximation for those sources. Native planar mannequin remains; cards
are excluded from its capture. Fixed2x2 subpixel radiance integration, same rain
field at every depth; no distance amplitude, fade or source blur. Original source
radiance and tuning retained. User approved the result and requested a push;
SaveLive captured the latest rain0.58208954 (14.55%), ripple size2/depth80/width1.
Ground has depth(-200…200m) and width(.1…4x) entries/sliders; live shader uniforms,
seven transforms, save/revert and weather checks pass. Normal build and focused
water/softbox prepare current;32 moving/paused captures reviewed. Flat-water
source mean .65226 vs old .65219. Far highlight shimmer remains at maximum rain;
not a finished reference match or a full scene ray tracer. No card-occlusion trace
or full GGX source convolution. No extra history CVars retained. Evidence:
Saved/RainFilter20261029, rain-filter-quad-* captures. Current look saved through live44168, which remains open on Ground. Scene-only
checkpoint pushed as d195d6d0 to origin/codex/standalone-sim; remote hash
verified. Live review retained; no desktop input or engine edits.
[Current UI handoff](Docs/WeaponWheelUI.md), [lab details](Labs/MainMenuSceneLab/README.md).

**Main-menu scene October29 — both lighting attempts reverted:**
User rejected the overhead-strip change and then the distance fade. Original
seven upright reflection cards, original source material profile and constant
water specular.255 restored. Native scene source now matches pushed HEAD.
SaveLive preserved current tuning before closing38648; normal build and focused
water/softbox preparation pass. Visible review19976 on Ground responds, scene
and smoke ready05:17:33 Warsaw. Settings hash matches this turn's backup in
Saved/ReflectionRevert20261029. No desktop input, engine edits or push.
User requested a separate rotatable explanatory schematic; current geometry is
recorded in the UI handoff. Older lighting experiment receipts are rejected
history. [Current UI handoff](Docs/WeaponWheelUI.md).

**Main-menu scene October29 — real horizontal smoke width and checkpoint:**
Pushed checkpoint `b1ed59f0` to `origin/codex/standalone-sim`; only the scene,
its curated dependencies and handoff were committed. Other work remains local.
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
Review20344 reopened on Air and was later saved/closed for the lighting update. User requested
push: curate this isolated scene, its required content, settings and handoff only;
exclude all other workstreams and generated caches/recovery files.
[Current UI handoff](Docs/WeaponWheelUI.md).

**Main-menu scene October29 — collision tuning and resting-contact gate:**
Water tab adds Push strength0–3x, Motion threshold0–20cm/s, Contact softness
0.5–20cm, Damping0–100%, Wave relief0–3x, Allow resting contact (legacy),
Try calmer contact and Clear existing waves.34 sliders total. All use existing
Save/Revert/recovery; SaveLive preserved latest native tuning before closing26304.
Measured frozen mannequin has zero bone motion but old always-present colliders
leave normal XY energy0.000397816. A native keep-depth branch made it worse and
was rejected. Final engine depth mode remains original. New default gate measures
actual PHAT transforms only for shapes reaching the3.5cm surface, including
rotation via seven local bounds samples; above-threshold horizontal speed admits
the original whole mannequin provider, with80ms release hold. No hand-authored
waves. Resting contact checkbox bypasses this gate to reproduce old behavior.
Frozen gate: exact0 GPU normal energy. Default1cm/s animated idle retains small
waves; calmer preset (.6x push,5cm/s,4cm softness,30% damping) produces exact0
for sampled idle and a real wake for90cm translation (energy0.000135745).
Inactive shapes are absent from the fluid boundary; purely vertical forcing
retains Epic's horizontal-velocity limitation. Background/rain remain independent.
Clear waves preserves position/tuning and clears displayed RT even when paused.
Normal build and lab-only Niagara CPU/GPU preparation pass. Native controls,
persistence and GPU readback receipts: Saved/Validation/collision-controls.json,
collision-response.json, weather-controls.json. Water panel capture inspected:
Saved/Captures/contact-gated-studio.png. User scene.json byte-identical to
Saved/CollisionControls20261029/live-saved.json; no main-project/engine assets,
desktop input or push at that revision. Previous PID28136 reopened on Water, responding with
scene/smoke ready03:38:01 Warsaw; rain0/background30.597%/wave relief0.8 retained.
[Current UI handoff](Docs/WeaponWheelUI.md).

**Main-menu scene October29 — click-to-move mannequin gizmo:**
Click actual mannequin/PHAT to select; world X/Y/Z translation handles, blueZ
lifts it out of water. Native query-only collision, mesh and water colliders
translate together. Pause supported. Esc cancels drag/deselects; empty click
deselects; Tab hides gizmo with panel. Reset position above Save/Revert on every
tab restores starting location/heading; R retains additional water reset.
body_offset_x/y/z persist via Save/Revert/recovery; WASD retains height. Limits
450cm horizontal, Z-30…400cm. Continuous deprojection avoids engine integer-pixel
rounding causing depth steps; native40cm XYZ drags now exact at log precision.
Normal build and shared native pick/drag/scaled-geometry/paused/cancel/persistence/
reset checks pass; existing weather/recovery validation passes. Native capture
mannequin-gizmo.png inspected; receipt Saved/Validation/mannequin-gizmo.json.
SaveLive preserved latest rain0/background30.597% before closing30320. User file
unchanged versus Saved/MannequinGizmo20261029/live-saved.json. No desktop input,
main-project/asset edits, shader preparation or push. Reopened visible review
PID26304 was on Ground with rain0/background30.597%; saved/closed for the collision controls above.

**Main-menu scene October29 — retained rain, smoke and ambient ripple:**
Latest: Ground Background ripple exposes wind_strength0–1 (current30.597%); zero
removes only ambient water normals, leaving rain/mannequin response.29 controls.
User says stop asking them to Save. Use Labs/MainMenuSceneLab/SaveLive.ps1 before
authorized rebuild: native request saves exact live settings, checks ack/disk.
Live edits also debounce250ms to .recovery, restored on launch only when the
stored baseline exactly matches saved JSON; explicit Revert resets recovery.
Implementation-only Live Coding patch added save IPC safely with no layout
changes and recovered rain-off tuning from PID12136. Then closed for normal
build of new retained storage. Backup Saved/AmbientRipple20261029/live-saved.json.
Never ask the user to Save for routine rebuilds; preserve via this mechanism.
No desktop input or source asset changes. Current review status in UI handoff.
Normal build and native controls pass, including ambient0/.37, recovery.81 and
Revert. Ground-tab capture background-ripple-control.png inspected. Previous
review PID30320 opened on Ground; scene/smoke ready01:56:41 Warsaw. SaveLive.ps1
verified on that session; later saved/closed for the gizmo update above.
Density is now0–100% across four times the old capacity: old80%=new20%, old100%
=new25%.98,532 physical streak seeds in four independently jittered layers;
all impacts use the same seed/phase/position as their drops. Original layer0
and stored rain_amount units preserved (now0–4); saved looks need no migration.
Inactive quads collapse before rasterization; water visits only occupied layers.
Fine-storm button/preset uses new95%. Native20%/100% captures verify19,718/98,532
active seeds,4.997x rate with unchanged speed/width/length/impact strength. Native
save/reload at raw3.27 and both material bindings pass. Tools/verify_dense_rain.py.
Smoke no longer has sideways wind. Centered source emits downward; negative
density buoyancy against explicit gravity-980Z creates upward return, with
vorticity curling it. No temperature/thermal buoyancy. At saved12% drift:
velocity(0,0,-64)cm/s, coefficient-.016. Drift scales speed/return acceleration;
zero pauses. Rolling motion stays independent. Source20cm above bank center,
radius180*sqrt(spread), capped240cm (~228cm saved). An initial120cm source offset
put too much smoke above frame; final20cm offset visually checked. User height,
crop, shift and other settings untouched. Only lab assets/overrides modified.
User saved before rebuild; Resources/scene.json remains byte-identical to
Saved/DenseRain20261029/prior-saved.json (saved rain90.3%, now displays23%).
Normal build-final succeeds; preparation0 errors/0 warnings and CPU/GPU smoke
compile passes. Offscreen dense-rain-20/100, down-roll-8/18 and dense-roll-studio
captures inspected. Typed flow readbacks and evolving upper bank verified;
no claim of direct GPU velocity-field measurement. Receipts:
Saved/Validation/dense-rain.json, downward-smoke.json, weather-controls.json.
No desktop input; only CLI build/render/launch. Review29744 closed for this
authorized rebuild. Current Air-tab review PID12136 reopened with saved look;
SCENE_READY/SMOKE_GAS_READY and responding window verified01:17:13 Warsaw.
This review was later saved/closed for the update above. [Current UI handoff](Docs/WeaponWheelUI.md).

**Main-menu scene October28 — retained flowing bed and calm puddle:**
`Labs/MainMenuSceneLab` ground now uses one warped phase field with long curves
and finer following strands; the rejected multi-direction interference patches
are superseded. Saved scale0.75 and dark-area option retained. Water's authored
background normals are reduced50 times so rain/contact dominate the calm surface.
Rain rings last1.05s, expand28cm/s and use directional antialiasing plus shallow
bed refraction. They remain analytical material events paired to the3D drops.
Actual mannequin collision still uses Epic WaterAdvanced/NiagaraFluids. Lab-only
soft collision falloff30→4cm fixes weak coupling in the3.5cm puddle; friction
0.00025/dissipation0.0003 reduce wake loss. Engine assets/solver unchanged.
Native GPU readback at3.2167s: collision-on XY energy0.000369499, off exactly0.
After motion stops, outer250–350cm energy rises3.25x by4.5s, showing propagation.
Stock horizontal-speed collision gate remains: purely vertical contact is limited.
28 sliders across Ground/Rain/Air/Body. New Air Left / right moves cold smoke and
source together ±1000cm without resetting the grid; default/current shift200cm.
Epic Grid3D_Gas_Smoke/native volume renderer, upper-edge mask, optional middle
mist, physical rain widths and UV wet-body coating retained. No VDB/cache bake.
All43 current live settings, including unsaved rain/smoke edits, were captured by
native F12 report and preserved exactly; only shift200 was added to scene.json.
Backups: Saved/PuddleRevision/prior-live.json and prior-saved.json. Actual saved
smoke height394.03cm/spread1.6026/roll27.985%/lower-edge30.075%; do not restore the
older cold-smoke preset over the user's tuning. Normal build-puddle-3 succeeds;
latest material/Niagara preparation has0 errors/0 warnings. Control live binding,
cloud location and save/reload checks pass. Native offscreen captures inspected:
Saved/Captures/puddle-studio-final.png, puddle-rain-final/after.png and
puddle-contact-final/disabled/after.png; JSON settings/raw GPU fields retained.
Receipts: Saved/Validation/puddle-collision.json, puddle-rain-motion.json and
weather-controls.json. Render matching remains an art-review checkpoint.
User standing authorization "dont ask just rebuild everytime" covers this lab;
latest instruction "without using my computer, resume" forbids desktop input.
Computer Use stopped; all subsequent changes/builds/captures were file/CLI/offscreen.
October29: user explicitly requested reopening; Open.ps1 -Visible -Air launched
review PID29744 with current saved settings. SCENE_READY/SMOKE_GAS_READY and
responding studio window verified at00:38:56 Warsaw. No desktop input or tuning
changes. That review was later closed for the October29 update above. Other apps, main project, Blueprints, other
labs and engine assets untouched; no push or storage cleanup.
[UI handoff](Docs/WeaponWheelUI.md), [lab instructions](Labs/MainMenuSceneLab/README.md).

**Throw Lab / spear October28 - Blender-to-FBX grip mismatch corrected:**
User screenshots exposed a genuinely stale FBX relative to saved Working.blend.
Read-only Blender bridge audit found leather/two keepers translated-0.17637485m
and a blade scale/translation absent from the FBX. Lab cache matched that old FBX
within5nm; reimporting it alone could not reflect these newer saved source edits.
Main FBX now matches current saved source geometry; grip pivot1.05862513m source
Z, blade tip2.221231m, total2.252231m. Same30,542 vertices/59,460 triangles/17 hulls.
Updated affected grip/shaft/blade hulls and sockets, blade normals; topology,
UVs/colors and other geometry preserved. New FBX hash
adebec94c106705a6db9b6628a54e8403734f145b507cfc521b12dc25e533668.
Lab cache rebuilt; full source-to-cache nearest-point error0.0001404mm. Jolt
grip/contact and818-pose/84-launch checks pass; isolated viewer loads new hash.
Blender source, live scene bytes, lab bind/scale/presets and other weapons unchanged.
Backups/audit/candidate: Saved/ThrowLab/SpearGripSync20261028/. Main FBX and lab
only; older GLB/LODs/export reports are not refreshed by this targeted sync.
Full export_spear.py still contains historical grip/blade/collision constants;
reconcile those with current source before another complete export. User Refresh
loads the corrected spear. [Asset handoff](Docs/ImperialSpear.md).

**Throw Lab October28 - requested spear FBX refreshed (local):**
Imported `Exports/ImperialSpear/SM_ImperialSpear.fbx` into the lab render/physics
cache:30,542 vertices/59,460 triangles,17 authored UCX hulls,2.231m source length.
Source SHA256 a1aca4b1821830485940b07dcd8a187863da982cdaed88cb8eb59734030cf211.
Existing spear attachment/mass/axis, sword/bomb and live scene bytes preserved;
grip/scale/presets unchanged. Geometry/COM now follow the new source. Importer
accepts revision-specific counts, keeps atlas uint8, verifies stable source/atlas
hashes and writes atomically. Grip/contact, aero and818-pose/84-launch attack
checks pass; actual isolated viewer/undo/Refresh pass. Fixed a near180-degree
half-aim bend discontinuity exposed by the new COM using continuous distributed
yaw/pitch. Backup/receipts: Saved/ThrowLab/SpearRefresh20261028/. User Refresh
loads it. No desktop/Unreal use, export-package repair or resident process.
[Lab details](Labs/ThrowLab/README.md).

**Throw Lab October28 - half attacks and target aim (local, unpushed):**
Left Attack mode section adds Half attack and Aim at target, both default off,
per throw, saved and undoable. Half fixes root/pelvis/legs at frame0; spine_01
compensates to preserve normal upper-body world rotations, head and held weapon.
Initial aim used preset launch velocity/spine_05; spear/sword now use the shaft
and held weapon origin as described above. Bombs retain the initial reference.
Full uses whole-body yaw only plus pitch shared equally across all five spines;
half shares combined yaw/pitch through the five spines with fixed lower body.
Cached two-angle solve accounts for the changed reference position. Direct local FK
entry reaches aimed Armed, then authored motion continues with the correction.
Current hand/forearm keys apply afterwards and remain editable at whole frames.
Launch pose follows the corrected hand; original speed/twist and all stored
presets stay intact. Aim off restores original launch direction; both off restore
exact old pose/launch. No ballistic elevation or post-release target steering.
818 pose/84 launch numeric cases pass across both clips/all weapons, including
world orientations, frozen legs, no added pelvis tilt, five-spine distribution,
fractional release, direct FK entry/Armed continuity and Jolt replay. Existing
vanilla and aero regression suites pass. Isolated browser toggles, target updates,
undo/Refresh, independent throws and snap checked; no live state/desktop takeover,
Unreal/server restart or additional worker. User Refresh loads it.
[Current implementation and checks](Labs/ThrowLab/README.md).

**Foot IK October29 - accepted slide movement/contact restored:** user rejected
October30 activation correction: backup copies retained old timestamps; in-app
Refresh therefore kept the rejected in-memory motion. Full browser reload is
required; restored source mtimes now renewed for other open tabs. Prior claim
that the viewer had reverted was premature despite correct disk/HTTP hashes.

User rejected
the continuity change: hands lost79–83% of travel and bracing stayed down.
Restored exact accepted pre-guard slide-arms.js(E9725E63) and surface.js(FCE87DF5).
No broad arm/leg filtering or inward stop remains; mouse scrub Play/Pause fix
retained.317-tick replay matches accepted contact/motion, min wall gap0.30mm,
joint/root/leg checks pass. Accepted full-slide hand contacts190 vs rejected117;
settled wrist paths2.292/2.535m vs0.487/0.435m. Original release-arm torso crossing
and wall-correction hitches remain unresolved. Do not equate reduced jerk with
motion quality/contact preservation. Receipts Saved/FootIKRestore20261029 and
ArmSmooth20261029/accepted-envelope.json. [Current handoff](Labs/FootIKLab/README.md).
Live8890 refreshed and wall brace at201 inspected; original paused22/camera/
tuning retained.10,530 replay bone positions match accepted clip exactly.

**Foot IK October29 - REJECTED slide arm/leg continuity and scrub playback:**
Supersedes the free-only inward stop: F44 entry and contact transitions exposed
its discontinuity and torso crossing. Existing host wall solve now keeps a side
clearance through all contact weights, carries incoming arm velocity, retains
joint velocity and smoothly releases unreachable braces. Hand reserve2mm retains
contact; rejected25mm smoothing candidate made the hand hover. Host leg-goal
inertia reduces settled acceleration678->305rad/s²; root/pelvis/pre-slide NN
remain exact. Current317-tick audit: F44 shoulder5.47->0.78deg, F81.5 wrist
acceleration245->0.52m/s²; max whole-arm step2.15deg, forearm/hand torso clear.
Residual wall safety accelerations remain; no general self-collision pass.
Mouse scrubbing preserves Play/Pause and resets frame clock; brackets unchanged.
Live8890 through202, mouse rewind while playing verified. Original paused201,
camera/tuning/0-202 trim/0.3x restored. Shared isolation/transition checks pass.
Receipts Saved/FootIKArmSmooth20261029/projected.*. [Details](Labs/FootIKLab/README.md).

**Foot IK October29 - superseded simple dangling-arm inward stop:** only the free
arm receives one smooth outward shoulder rotation after wall clearance, fading
out as bracing takes over. Elbow bend, wrist-relative rotation, circle clock and
existing smoothing retained; Jolt shoulder limits applied. No collision search,
pin/history, legs/root/shared API changes. Current317-slide-tick replay: worst
free elbow-3.97cm to+2.81cm outside shoulder plane, inner hand-box edge+3.35cm;
root and non-arm positions exact, limits pass, wall clearance>=0.30mm. Rejected
general self-clearance remains removed. Saved/FootIKFreeArm20261029 receipts.
Live8890 loaded through202;90/102 inspected, paused0/camera/tuning restored.
[Lab handoff](Labs/FootIKLab/README.md).

**Foot IK October29 - self-clearance rejected and reverted:** user reported
visible sticking. Restored exact pre-experiment arms/surface sources, preserving
the accepted wall-clipping correction. Removed self-clearance helper dependencies
and its test from active lab; rejected code/metrics archived in
Saved/FootIKSelf20261029. Collision checks had passed but motion quality did not;
do not treat those checks as proof this approach is acceptable. [Details](Labs/FootIKLab/README.md).

**Foot IK October29 - slide arm wall clearance (local, activated):** final displayed arm
capsules/hand boxes now avoid the wall after entry/contact blending, using the
existing Jolt limits and a clearance-aware temporal bound. The palm-only check
missed forearm/elbow overlap. Current Run58/yaw200/Fall-2 through202 passes all317
slide ticks: minimum gap0.30mm versus30.6cm penetration before, no added joint
violations, exact root path. Forward and negative-turn replay, shared isolation,
transition/split and signed Fall checks pass. Hand contact can release when arm
clearance conflicts. Live8890 loaded through202, paused96 retained; playback and
console verified after a cold-generation timeout/retry. No shared foot-placement/UI changes. [Details](Labs/FootIKLab/README.md).

**Foot IK October29 - signed Fall speed (local):**
Fall speed accepts negative values: -1 enters Slide as upward Vy slows to+1m/s.
Initial upward inertia survives with no thrust and full gravity through apex;
it does not immediately exit just because Vy is positive. After descending,
new upward motion exits; before apex, accelerating above entry speed exits.
Early entry requires slowing ascent, preventing immediate re-entry on upward
reversal. Positive/zero behavior retained; no saved tuning changes. Root
snapshots retain prior Vy/descending state. Focused negative-threshold checks
cover gravity, restore and reversal; existing full transition/re-entry and
exact split-generation regression also passes. Shared createFeet/Unreal unchanged.
[Details](Labs/FootIKLab/README.md).

**Foot IK October29 - slide hand chatter corrected (local, activated):**
The heading-aware arm fitter accepted sideways palm misses because it checked
only distance to the wall; independent joint speed caps then broke the solved
chain. Full palm-target residual, accepted elbow-pole continuation, damped
fitting and a shared three-joint response/rate bound remove alternating motion.
Heading speed continuously raises response to avoid turning-contact lag;
a fixed local low-pass was rejected after full-turn checks.
Current Run58% F134–202: lateral wrist acceleration423.75→3.31m/s², palm step
6.07→0.36deg/120Hz, rapid reversals23→0; both palms contact274/274 samples,
max gap1.77mm, legal joints and exact root trajectory. Arm-only inner FK matches
full FK within3.2e-12m, avoiding whole-skeleton work per fitting iteration.
Bounded fitting precision keeps recorded native preparation around3.5–3.8s.
Friction/balance and heading-aware contacts retained. Before/after upper-body
strips checked; shared isolation2722 and exit/re-entry/split checks pass.
Final native7-case current/cardinal/full±turn audit passes, all zero rapid
lateral reversals. Turn arm steps4.89/5.27deg; contacts376/442 and293/452 improve
on original252/442 and283/452. Root exact, leg differences<0.16mm.30deg/s
captured-input check retains93.9% contact with legal joints. Full six-second
turn preparations take25–26s; that remaining cost is not fixed by this work.
Live8890 Refresh loaded202 and retained paused173/camera/tuning, console clean.
Shared feet, NN and Unreal unchanged. Receipts:
Saved/FootIKSlideAudit20261029/hand-continuity-*
hand-final-regression/report.json and hand-arm-fk-parity.json.
[Details](Labs/FootIKLab/README.md).

**Foot IK October29 - heading-aware Slide (local, activated):**
Slide retains commanded facing: front stays toward the wall, side stays side,
back remains outward. Root yaw continuously changes the pose and hand contacts;
the entry corridor forecasts the heading at the end of the leg blend. Pelvis
orientation uses a decaying local entry residual to avoid a180-degree wrap snap.
Independent pelvis/leg clocks, pelvis distance, ballistic root and native NN
approach are retained. New host-only slide-arms.js gives both front hands or a
near side/back hand continuous reach weights and anatomical elbow/wrist limits.
The accepted torso/free-arm motion and70% speed-based absolute-down gaze remain
active in every heading; Head max at m/s still controls its endpoint(default30).
Goal contact now considers sole contact, all-surface knee clearance, joint
limits and knee-pole continuity together. It selects a nearby feasible tangent
target instead of asking a knee to enter the wall and then pulling the shoe
away. Settled clearance carries the previous legal joint pose, preventing
stale correction offsets from folding the leg. A delayed knee-clearance check
on otherwise clear entry paths and a slide-exit scope error were also fixed.
Sixteen Walk/Run direction/incline/floor cases pass, including +535/-523/+679
degree yaw sweeps. Max settled heading error0.923deg, max joint step7.59deg at
120Hz; native pre-Slide poses and ballistic root remain exact. Current Run58%,
forward90deg scene has286/286 settled foot-contact samples, max gap0.0122mm,
no motion-review flags. Four-heading gaze check, shared isolation2722 checks,
exit/re-entry and exact split-generation checks pass. Full-motion/multi-view
collider sheets and focused fast-entry frames were inspected. The82/85deg
floor-interaction tests correctly release wall contact once hips exceed leg
reach; they do not secretly pull the pelvis back. Earlier20-case receipts below
describe the previous fixed-heading behavior. Live8890 refreshed through202,
paused140 retained with camera/tuning/trim; console clean. No shared-foot API,
Bodyflip or Unreal changes; no push. Receipts:
Saved/FootIKSlideAudit20261029/heading/. [Details](Labs/FootIKLab/README.md).
Remaining visual limitation: the folded Run-left entry around80–92 still takes
a broad high leg sweep. The corridor raises the foot23.3→61cm above pelvis;
this extra rise is planner-authored, not required by the NN. It is continuous
and joint/geometry-valid, but not an optimal natural route. Bounded lower-route
experiments caused penetration or correction snaps and were rejected; stable
production code/timing retained. See entry-*.json in the audit folder.

**Foot IK October29 - slide transition audit (previous fixed-heading version):**
Pelvis timing follow-up: Pelvis blend s is appended below Leg blend s. It controls
pelvis position/orientation independently (legacy default twice body Blend s,
current1s). Slide closer uses this pelvis clock too. The leg corridor forecasts
the independent pelvis schedule. Current saved replay passes joint/contact and
pelvis-path checks; entry62.5 to pelvis-ready122.5, max joint step3.94deg/120Hz.
Receipt: Saved/FootIKSlideAudit20261029/pelvis-blend-check.json. Root/NN unchanged.

Slide follow-up: entry cancels only outward wall-normal rebound from locomotion;
tangential inertia/gravity remain with no ongoing attraction/thrust. Current
replay drift54.3cm becomes zero; exit/re-entry and exact split continuation pass.
Added Leg blend s at the bottom of More options, separate from body Blend s.
Legacy default is twice Blend s (current1s vs body0.5s). The leg corridor predicts
the longer duration with the independent body schedule. Contact takeover waits
for leg completion. Current entry62.5, body ready92.5, legs ready122.5; joint,
contact and pelvis checks pass, max joint increment4.21deg/120Hz. Host-only;
no Unreal/Bodyflip changes or push. Receipt: leg-blend-check.json in the audit folder.

Follow-up: base Slide inherits entry pelvis distance. Added Slide closer cm at
the bottom of More options: default0, current scene10, range0–15cm. Blends the
explicit inward pose offset over Blend s and retains it during Slide without
altering root inertia/gravity. Current0/10/15cm checks pass joint/contact limits,
exact root parity and settled offset. Larger cramped offsets are not exposed.
Saved scene retains Blend s0.5. The prior large body-clearance envelope and
hidden inward hand-reach pull are superseded: the transition now plans a legal
hip/knee/ankle route while preserving configured pelvis placement. New host-only
slide-entry.js is included in browser/worker fingerprints, not Bodyflip bundles.
Entry carries the last displayed pose; soft arm reach and smooth contact release
avoid snapping when root inertia takes the wall out of reach. Dangerous-incline
pelvis withdrawal fades its world vector, so a wall pull cannot become a sudden
downward crouch when support changes to the floor.
Twenty direction/turn/incline/floor configurations pass;19 reach Slide and one
retained-floor backward walk correctly lands before the descending trigger.
Fresh NN verifies affected feedback cases; numerical checks cover every120Hz
tick and multi-view collider sheets cover whole motion and difficult intervals.
No added hip-limit error or pelvis detour; settled limits/fixed lengths pass,
max shoe penetration0.00235mm, max joint increment6.93deg/120Hz. Current F85–115
pelvis stays48.4–49.2cm (root inertia), replacing~70cm peak and31.2cm endpoint.
Joint/shared/coupling/exit/re-entry/bounded-session checks pass; saved Blend0.5
retained. Live8890 Refresh loaded through202 at paused108, persisted state
unchanged. Hard folded routes still need more preparation than the ordinary
~0.4s active-leg plan. No Unreal/Bodyflip/UI/tuning changes or push.
Saved/FootIKSlideAudit20261029/; [details](Labs/FootIKLab/README.md).

**Foot IK October29 - slide head gaze and upper-body motion (local):**
Head gaze ramps from slide-entry root speed to Head max at m/s (default30),
now appended at the bottom of More options and saved independently of feet shift,
reaching70% toward absolute down at that limit (user reduced the original100%). A0.65s entry ease
and three limited neck/head joints avoid a snap. Small irregular damped
bends/twists are distributed across the five spine
joints. Bracing arm is re-solved to its original wall target after chest motion;
free-arm orbit/speed bursts remain. No added root forces, NN calls or workers.
Two full recorded clips plus current601frames pass: max head step0.41°/120Hz,
chest step0.18°, chest range5.8–7.4°; all settled joint limits and wall contacts
pass. Current root/pelvis/legs are exactly unchanged. This deliberately expands
the earlier free-arm-only scope; balance regression now preserves lower body,
root and pre-slide prefix. Full slide-motion tests also pass. Live8890 Refresh
retained F203/camera and loaded through F300 with no console errors. Receipts:
Saved/FootIKHeadTorso20261029/. No Unreal/other-lab changes or push.
[Current details](Labs/FootIKLab/README.md).

**Foot IK October29 - descending Slide and upward NN return (local):**
Fall speed m/s replaces Trigger |Vy|:2 means world Vy<=-2m/s, never ascent.
Above Minimum gravity incline, Slide is ballistic with zero thrust; it exits
when Vy becomes positive and may enter again on a later fall. Exit clears stale
pins, restarts native inference from preserved gait current/history rebased to
the actual root/heading, and blends the displayed slide back after leg IK using
existing Blend time. Procedural Slide pose is not fed into the gait network.
Current live scene: Full gravity10% continues climbing through F300; diagnostic
100% peaks at F43 and enters Slide at F56, Vy=-2.048m/s. User tuning preserved.
Controlled upward impulse test exits F138/re-enters F168, exit angular step
0.000436deg/120Hz; split generation exactly equal. Native recurrent reset equals
a fresh Stream seeded with the same current/history. No inference while sliding,
extra workers, Unreal/other-lab changes or push. Receipts:
Saved/FootIKSlideTransitions20261029/. Supersedes the ascent/latch diagnosis and
trigger semantics in the historical October28 receipts below.
Live8890 Refresh loaded through F300, retained the user's F171/camera/settings,
and shows upward Vy=+0.59m/s outside Slide. Fall speed label verified in More
options; existing server remained running, no restart required.
[Current details](Labs/FootIKLab/README.md).

**Foot IK October29 - free-arm neutral orientation and balancing (local):**
Current follow-up: user rejected added corrective gestures; those offsets are
removed. Original circle/reach now follow an integrated clock with irregular
2.2–3.4× bursts (0.10–0.17s rise,0.40–0.64s return), then exactly1× gaps.
Accumulated phase is retained: no rewinds or path changes. Contact-driven sway
and initial amplitude blend keep real timing.20s clock checks and three full
pose clips pass: neutral/joint limits, identical root and other bones; new peaks
0.92m/s,12.61m/s²,1.11°/120Hz supersede the slow-orbit figures below.
Saved/FootIKOrbitSpeed20261029/ is current; FootIKCorrections20261029 is rejected.
The slide's free elbow pole now follows the idle reference in its clavicle frame,
transported to the hand target. The old wall-relative pole twisted it102.9° from
neutral at the user'sF184 despite satisfying broad shoulder limits. Wrist stays
neutral-relative; true hinge elbow retained. A smooth7×10cm,~0.55Hz balancing
circle supplements inherited inertial sway, with gradual entry/extension instead
of a hard reach cap. No added UI, root force, NN calls or worker. Three recorded
clips check both arms: limits pass, settled free-arm steps<0.63°/120Hz and hand
acceleration<3.42m/s². Current417frames keep root and every other bone exactly
unchanged. Full slide-motion contact/length/entry checks pass. Captures/receipts:
Saved/FootIKBalance20261029 and snapshots/slide-balance-verification.json.
No Unreal/other-lab changes or push. [Details](Labs/FootIKLab/README.md).

**Foot IK October29 - slide preparation optimized (local):**
Current8890 scene previously spent23.70s in browser solve /24.22s to ready,
despite19ms cached backend. Worker now sends lossless gzip-JSON solved-pose
batches; browser appends them instead of repeating120Hz simulation. Same trim
and resumable prefix; no extra processes. Idle same-version Node peers reset
and reuse compiled code within the existing two-session limit. Slide-only
chain FK, shoe geometry reuse, lean joint projection and allocation reduction
give3.56× paired median raw-solver gain. All417 current frames retain exact
roots; max difference13.4micrometres /0.0018°. Full joint/contact clips,5800
session checks,30 restore/reset checks,18 shift and25 UI checks pass.
Refresh0.44–0.46s; final uncached setting edits8.97/6.83/5.84s and cold-worker
request22.21s. Requested10× fresh solves NOT achieved; do not call cached
Refresh the fresh-solve benchmark. Existing below-normal workers/startup remain.
Also separated16 surface-result /16 seed cache budgets: the old mixed budget
evicted active gait seeds and added2.93s on an otherwise cached reload.17-edit
cache isolation/migration test passes. Only8890 server restarted as PID37324;
saved scene bytes identical. No Unreal/other-lab restart, retained tuning change
or push. Final browser ready in1.43s, frame43/camera/trim0–208/tuning retained.
Receipts/pre-change sources in Saved/FootIKPerf20261029.
[Details](Labs/FootIKLab/README.md).

**Foot IK October28 - independent feet/hand slide shift (local):**
More options now has Feet shift cm / Feet max at m/s, followed by Hand shift cm
/ Hand max at m/s. Both inherit the old shared tuning; missing hand values are
explicitly persisted once so future feet changes cannot alter them on Refresh.
Separate damped offsets/carrier velocities retain the existing reach/contact
solver. Independent amounts, thresholds, zero-disable and delta-save/reload
checks pass; all601 recorded frames exactly match prior motion at equal tuning.
25 UI/trim checks pass. Live8890 Refresh retained frame126, camera and trim0–208,
saved hand20cm/10m/s and displayed all four rows. No server restart or Unreal
changes. [Details and receipt](Labs/FootIKLab/README.md).

**Foot IK October28 - speed-based upward slide targets (local):**
Appended Max shift cm (default20,0–50) and Max shift at m/s (default10,.1–100)
after Recovery speed. Feet and bracing hand request maxShift times clamped
totalRootSpeed/maxSpeed, along projected world up on the slide plane. A damped
neutral-target response handles velocity reversals; friction sees its velocity.
Per-limb reachable-target search retains the neutral knee/elbow bend planes,
joint limits and wall contact; offset can be smaller than requested. No root
forces/shared createFeet changes. Zero shift restores the previous target path.
18 focused checks pass, root/pre-slide equality exact. Both default recorded
clips pass full bone/joint/contact checks (max successive pose rotation7.6/12.2°
at120Hz). Extreme50cm/.1m/s remains legal/contacting but has a32.2° calf step;
that stress case is NOT evidence of uniformly smooth motion at extreme tuning.
25 app/trim and15 friction/recovery checks pass. Live Refresh retained frame103,
camera and0–208 trim;15cm edit/Enter/blur/persistence verified, then restored20cm.
No server restart/Unreal work,
other-lab edits or push. [Controls and limits](Labs/FootIKLab/README.md).

**Foot IK October28 - exposed slide friction/recovery (local):**
Two controls appended below Blend s in More options: Friction strength %
(0–300) and Recovery speed % (10–200), both default100/persisted with scene.
The distance-dependent restoring pull is retained (farther pulls harder,
progressive stretch guard); Recovery adjusts damping inversely so lower values
do not merely create larger catches followed by faster snaps. Zero friction
removes catches; high Recovery allows more rebound. Low-speed damping uses
small stable substeps.15 focused checks pass:100/100 exact prior particle
motion, zero friction, stronger pull with distance, force scaling, monotonic
recovery and finite full range.15cm80%return:25%=1.408s,100%=.300s,200%=.167s.
25 app/trim checks also pass. UI edits keep playhead and end-trim generation.
Live 25% Recovery edit/Enter/save verified; restored100% and savedframe149.
No server restart, UI rearrangement, other-lab/Unreal change or push.
[Controls and evidence](Labs/FootIKLab/README.md).

**Foot IK October28 - slower slide recovery, relaxed feet (local):**
After user review, contact spring now9rad/s with1.05 damping scaled to nonlinear
stiffness, replacing12/.52. Same rough-patch forcing; matched15cm release takes
0.300s for80% return versus0.117s, peak speed1.256→0.616m/s. Both recorded clips
show26–44% lower average recovery speeds, retained6.8–8.2cm half-second motion.
Slide feet prefer calf-neutral rotation with20% wall bias before ankle/toe
projection; clearance correction only along wall normal. Heel/toe/edge contact
replaces flat-sole preference: median wall tilt26–35°, ankle deviation23–24°
versus40–46°. Hip safeguard still swivels knees only to honor the hip cone;
not disabled as an ankle workaround. Root/pre-slide motion and NN calls exact;
contacts, joints and bone lengths pass.15 new compliance checks,26 existing
friction checks, full joint-motion and5,796 continuation checks pass. Activated
by Refresh, saved201/camera/0–208trim preserved. No server restart/UI additions,
other-lab/Unreal changes or push. [Current behavior](Labs/FootIKLab/README.md).

**Foot IK October28 - Refresh restored; surface generation follows end trim (local):**
Saved trim was0–208 and playback195; collapsed brackets were the blank page's
uninitialized HTML. Replaced unbounded browser requests with bounded waits,
including response bodies; preparation serializes/coalesces edits. API7 /
generation protocol1 activated on8890 alone, hidden/below-normal PID27988,
same overnight-state.json. Surface/wall and edited-platform scenes use a0.1s
seed then generate only through trimOut. Extension retains120Hz physics,
contact/slide state and30Hz NN tensors; shrink does no work. Two retained CPU
sessions, disk checkpoint restoration, future root commands still supplied.
Legacy stair planner remains unchanged: its noncausal anticipation cannot be
truncated without changing earlier motion. Warmup mean height replaces the
unused5s mean: +5.005mm in current fixture, root difference<5.950mm through208.
5,796 generator /25 UI /5 timeout /17 backend /7 genuine-NN checks pass;
split/restore prefixes and root windows equal uninterrupted runs exactly.
Actual user tab loads frame195 through208. Refresh127.6ms without rebuilding;
first cold load18.8s (policy startup plus two coupled simulation passes remains
costly). UI208→244 appends the same session (0.868s backend, zero new NN calls
after slide), shrunk to208, playback verified and paused195 restored. No other
lab/Unreal restart, motion tuning changes, UI additions or push.
[Current loading contract and evidence](Labs/FootIKLab/README.md).

**Foot IK October28 - dangerous-incline slide prototype (historical receipts):**
Trigger/latch semantics below are superseded by the October29 descending entry
and upward NN return above. Pose/contact work remains current.
Bottom of More options now has opt-in Slide, Trigger |Vy| m/s (default2) and
Blend s (default0.25). Above Minimum gravity incline, absolute world vertical
speed crossing the threshold latches slide for the replay, ascending or falling.
Preserves actual velocity; disables drive, support spring, pins/grace and energy
redirection immediately. Full gravity, no speed cap; unilateral capsule collision
still removes inward normal velocity. Root-to-mesh frame freezes at entry.
Subsequent user-rejected arm/ankle/static pose corrected: free arm hangs near
neutral/down with damped entry inertia. The tiny-sway version still read static;
October28 contact motion replaces fixed limb offsets with three damped tangent
particles, independent irregular friction patches and release intervals. Drag
opposes slip; elastic recovery returns each limb, and uneven tension rocks the
torso. No forces enter the root. Stable ankle/palm measurements (excluding
lowest-corner switching): median half-second excursions10.3–12.1 cm versus
0.07–0.43 cm before, minimum window7.1 cm in both fixtures. Knees vary16–23deg.
Hip swivel accommodates drag while retaining ankle target and signed hinge;
transition transports the legal goal pole without projecting the folded
incoming NN hip. Bracing arm uses the actual Jolt elbow hinge plus a feasible shoulder
swivel, preserving the palm contact. Ankles/toes/wrists use sharedIdle Jolt
swing/twist frames/limits in host-only slide-joints.js; knees use calibrated
hinges. Feet may touch by heel/toe rather than being forced flat. Blend retires
incoming NN joint residuals smoothly; exterior ankle arcs avoid the wall and
calf-relative foot rotation avoids opposite-limit snaps. No added root forces.
NN inference stops at slide; ghost carries the last policy pose. Shared feet/API
and Bodyflip unchanged.32 root/contact checks, full joint-motion checks and37
Slide-off pelvis-speed checks pass. Ascent/descent fixtures22/109 use10/54 NN
calls; root/replay error zero. Both settled wall fixtures pass all joint limits,
sole gap≤0.011mm, palm<0.00001mm. Post-entry maximum joint increments7.1/12.5deg
per120Hz tick. Isolated real8890 browser route, current130, entry/later frames and
other views checked; user state unchanged. This remains kinematic procedural
motion, not a ragdoll. Strongly folded entry hip transitions and an85deg cached
gait thigh probe are not universally joint-constrained; no blanket full-body
Jolt-compliance claim. Existing pre-entry sharpness is not claimed fixed.
8890 was stopped again when the user reported an unloaded viewer. Restored only
Foot IK using its existing overnight-state.json, hidden/below-normal PID448
(superseded by the bounded-generation activation above).
Health checked after launch. Latest friction motion activated in the user's
in-app tab; inspected195/207/219, restored195 and camera. New26-check comparison
retains exact root and pre-slide pose hashes, deterministic replay, stable-point
derivatives and <3deg settled joint-step guards. Plots/120Hz series:
verify-slide-friction.cjs, render-slide-friction.cjs and snapshots/slide-friction-*.
No evidence
identifies why the prior host exited. No Unreal/other-lab changes or push.
[Details and evidence](Labs/FootIKLab/README.md).

**Foot IK October28 - accepted checkpoint pushed; velocity-based pelvis closeness local:**
Approved wall-frame/pelvis-height/signed-knee motion pushed and remote-verified
as16d1fe0a93b469f4ab3fd0a87d337cee8e229f88 on codex/standalone-sim. Includes
prior terrain/yaw/root gravity/platform/persistence/live-NN work and
approved/2026-10-28/profile.json. Recovery9136 files/1,096,116,002bytes verified.
Other sessions and live scene files excluded; external runtime dependencies
remain documented. Subsequent user request is implemented locally:
Pelvis min cm keeps the previous amount at the bottom of More options. A compact
Min/Max Speed m/s pair and Pelvis max cm follow it. Blend the two amounts using
actual total root speed, clamped outside the range (default 0 / 3.5 m/s).
Maximum amount inherits minimum for old saves, preserving current 10 cm tuning.
Both amounts allow 0–50 cm and either can be larger. Dangerous inclines are above
Minimum gravity incline; the speed-selected amount ramps linearly from zero
there to full at 90°. Existing smoothed ground frame carries the inward shift.
Root and NN foot targets remain unchanged by the posture translation; signed
hinge IK reaches original targets/material pins. Zero/below-minimum exactly
match the accepted baseline (set both amounts to zero). Ghost stays before correction. Optional shared
pelvisShift is not enabled by Bodyflip.81 focused geometry/zero tests,13 baseline
and17 coupling checks pass. Saved76 visually compared0/20; live601-tick rollout
has no hinge inversion, replay error0 and pins exact. Browser verifies bottom
placement, Enter commit/blur, frame/value retention across reload. User state
unchanged. Speed extension adds 37 checks including exact pre-change Walk/Run
frame hashes, speed/angle blend, pins and knees. Isolated browser verified the
pair fits without widening the panel, Enter commit/blur and retained frame/value
on reload. Live 10→30 cm rollout: replay error zero, pin drift <2e-15 m, no hinge
inversion or sole penetration above 4e-8 m; reviewed 76/95/137/143/180. Real saved
state unchanged. No Unreal/server restart or extra worker. Refresh for controls.
[Current lab handoff](Labs/FootIKLab/README.md).


**Imperial spear October28 — selected pommel preview, export refresh pending:**
User accepted the latest shown shape and asked to stop refining and show views.
Exact source saved to `Saved/Diagnostics/ImperialSpear/PommelLotus/Selected_Pommel_Preview.blend`
and `Working.blend`. Body65 rows/3.2mm crest, fuller budV5, darker carved channels.
Corrected cavity gate preserves the prior head render pixel-for-pixel. Original70
components and four atlas PNGs remain unchanged. Later crown proposal not applied.
Export attempt stopped on LOD1 color interpolation outside the authored range;
mixed current outputs need a completed refresh/readback before Unreal use.
This selected-source checkpoint supersedes the older exported-build entry below.
[Current selection and resume details](Docs/ImperialSpear.md).

**Bodyflip October31 - separate mode timelines, local:** Run/Walk/Idle/Space
now persist independent markers, trim/loop, speed, playhead and gait start controls
per scene. New modes start empty; scene copy and refresh retain every mode.
Rapid mode switching preserves pending playheads and rejects stale restoration.
33 scene/mode checks and the no-op generation guard pass. Current Space's two
markers matched the saved Run capture exactly: retained under Run, cleared from
Space. Other scenes/world tuning preserved; backup mode-playbacks-before.json in
Saved/Diagnostics/BodyflipPort20261030. First reload should be Ctrl+R, because the
old Refresh button saves old state first. No motion solver/native changes or push
in this step. Earlier performance/airborne-slash work remains unfinished.
See Labs/BodyflipLab/README.md for scope.

**Bodyflip October31 - earlier no-op freezes / post-hit pelvis aim return:**
Historical package evidence; latest lab experiments are summarized at Resume here.
Marker-click jitter and rounded time-field commits rebuilt the full motion.
Canonical event equality,4px marker drag threshold, release-only commit and
motion-input equality now prevent this; identical pending prepares are shared.
76editor checks plus invalidation checks pass. Real motion preparation remains
expensive/synchronous; no general speedup claim. J2 zero-twist command stays on
world X; pelvis aim bank turns that flip into torso-axis rotation. Remove its
post-hit hold: pelvis aim now returns over Attack out starting at Hit, while
spine/shoulder follow-through remains. Current HitF174.4405 unchanged; pelvis
aim endsF189.4405 vsF199.9245. Transient aiming rotation still exists.27return
checks,4physical aim cases,19flipless attacks/684samples exact; native slash
V8 parity8frames/1723numbers exact. Runtime891446bytes, SHA256
5ed93ac7db5248d4c727e244e6304bbcfc0c34d874984c20ddf51b6d840c402f.
Saved Aim0.8/other state retained. No desktop/editor/build/push. Refresh to load.
Landing-to-NN discontinuity remains separate; see Bodyflip README and
Saved/Diagnostics/BodyflipPort20261030/twist-return-corrected.json.

**Bodyflip October31 - pelvis inspection view added, local:** `Pelvis view`
appended after Hand cones. Camera follows actual displayed pelvis translation
and full rotation; hides scene/debug overlays, keeps character colliders/weapon.
Starts from current view; orbit/pan/zoom/playback remain, off restores prior
camera. Scene-saved camera option; no rollout regeneration or motion/tuning edits.
36camera checks pass including arbitrary rigid-frame invariance below9e-15m.
Use Refresh to load. User is inspecting slash quality; attack solver unchanged
in this step. No desktop control, native changes or push. See Bodyflip README.

**Bodyflip October31 - earlier airborne slash contact solve (superseded in lab):** J2
full-aim miss56.86cm -> original hit marker0.0077mm; actual blade3.26cm from centre
of12cm sphere,4.998cm atF174. Fits contact position, independent shoulder/spine,
pelvis-local yaw and weighted preference against pelvis tilt. Coarse solve then
240Hz playback-accurate refinement; no per-playback solve. Elbow/wrist source
motion retained; flipless19attacks/684samples exact. Four physical position cases
pass; native V8 six cases48frames/10577numbers exact. Runtime890981bytes, SHA256
f15a76259e321254c5fabd66752eae0d417add02b944fdb05e4a3d4e219c44d3.
Active Aim restored100%, user's Leg follow0.10 and other state retained; useF5.
No desktop/editor/build/Blueprint changes/push. See lab README and
Saved/Diagnostics/BodyflipPort20261030/slash-weighted.json.
**Separate unresolved landing issue:** hand_l landingF194 leads to~110.7deg
right-wrist stepF198.76 in NN return. Endpoint/keyframe projection trials did not
fix it and were removed. Do not report complete landing continuity as passed.
Evidence slash-landing-audit.json; airborne interval is separately verified.

**Bodyflip October31 - foot push/follow corrected, local:** Foot contact now
releases at the accepted gameplay push impulse; the old ~8ms reach-to-99% stroke
was overextending the constrained hip/ankle and pulling the foot forward atF145.
The existing finite-speed extension follows the last world point inside final
momentum balance, then performs one inertial Leg return. Knee plane follows the
hip while endpoint aim remains world-directed. Released toes extend toward the
shin at existing Roll speed within ankle limits, rather than freezing at35deg
above the surface. Leg follow option remains in place; default/active scene
0.20 ->0.08s, all other saved state verified identical; F5 loads it. Zero follow
retains direct inertial return. Jump% impulse/carry, misses and hand timing kept.
Focused5564, earlier leg1126/release364/physical566, strength14 and hand5 checks
pass. Historical long inverted-follow exact-aim test remains joint-limit-bound;
see topic scope. No desktop/editor/build/restart or push.
[Behavior, tests and receipts](Labs/BodyflipLab/README.md).

**Bodyflip October31 - physical aim fixed for current slash, local:**
Follow-up: user requests100% Aim by default. Updated core/UI/native settings source
and active saved scene only, preserving other tuning/camera/playback/scenes.80% was
the original hard-coded lab default, not user-selected necessity. F5 reloads the
saved edit; old page Refresh would first save its stale in-memory settings. Runtime
repackaged; native default header remains pending build, no editor operation.
Source checkpoint09476308 pushed and remote verified before this change; it
excludes pending shared native C++ integration/generated packages/model exports.
Current aim omitted carrier displacement/drift (3.27m vertical at hit), seeded
from static motion and quit after two iterations. Prediction now uses resolved
world motion; bounded cached solve starts neutral and allows the attacking
shoulder to contribute within limits. Full Aim hits within10.046cm of the12cm
target centre; the saved80% setting intentionally leaves30.754cm/17.04deg and
was preserved. No new controls/gates or jump-strength changes. Four physical-aim
invariance cases pass;19attack/684sample flipless preservation exact. Runtime
repackaged; no editor or live state changes. Fix remains local after checkpoint.
[Current behavior, performance and limits](Labs/BodyflipLab/README.md).

**Bodyflip October31 - F145 foot-release snap fixed:**
Release history was rebased before floor projection, causing a false penetration
correction and capturing the wrong departing leg. Projection now runs in world
coordinates before rebasing; physical flight starts with that captured constrained
articulation while retaining contact momentum/COM velocity and the Jump% impulse.
No new blend/gate/control. Saved F144->145 thigh change53.74->3.94deg; release
seam0.121mm ankle/0.085deg knee. Both current markers still push at the same times.
364 focused,1126 prior leg-continuity,566 physical checks,14 strength/five hand
cases pass;19attack/684sample flipless Space gym remains exact. Runtime refreshed;
no editor/live state edits or push. Older absolute world-follow assertion remains
a documented pre-existing failure under the final rigid momentum correction.
[Details and receipts](Labs/BodyflipLab/README.md).

**Bodyflip October31 - predictable Jump % restored:**
Follow-up: fixed axis-only saved J2 canceling during LOAD when the other toe
touched ground atF141.5. Additional extremity contacts during an accepted PIN
now remain support contacts, with collision response intact, until lifted clear.
Head/torso and approach/free-fall landings unchanged. J2 now pushes2.4s and
releases2.40792s. RISE/FALL uses resolved COM velocity including carrier bias.
24 ownership/phase checks plus five hand cases pass; app replay confirmed.
No saved-state/editor changes; runtime repackaged. See current lab README.
Successful surface pushes now set COM takeoff energy directly from Jump%, plus
the existing Rebound option. Previously percentage was only a stopping threshold
for knee extension; early reaction release silently under-delivered regardless
of requested strength. Shared100% height1.032640m; with rebound0,200%=2.065280m.
Contact impulse at release, same load/pin/recovery and tangent carry; no new
impulse on zero% or a miss before pushing. Applies to feet/hands with/without
spin. Angular solve unchanged; non-spinning surface jumps correct translation
only, approved flipless Space gym unchanged. Saved J2 comparison70%~.83m versus
200%~2.16m with existing rebound.14 strength cases, five hand cases,566 flight
checks pass. No live scene/Blueprint/editor mutation. Lab/runtime updated.
[Current behavior and receipts](Labs/BodyflipLab/README.md).

**Bodyflip October31 - active-spin physical balance, no-spin art preserved:**
Follow-up: fixed lost jump height from averaging the last4.17ms of an accelerating
push. The release seed now uses a second-order instantaneous COM derivative from
contact-side samples. Saved J1 upward speed3.074->4.366m/s, ballistic rise.482->.972m;
contact drive/Jump% unchanged.562 flight checks, five hand cases and exact19attack
no-spin preservation pass. Lab/runtime updated; no live scene or editor changes.
Before the explicit Jump% contract above: old J1 COM rise1.226m versus ballistic.972m
(~21% lower). Old root speed4.629m/s exceeds COM4.366m/s, and animated recovery
adds.138m relative COM lift after release. Derivative fix alone does not restore
old height. The subsequent launch contract above supersedes this ambiguity.
The scene timings and aim measurements below predate this velocity correction.
One shared-mass3x3 COM reaction solve now balances final attack/aim/released-limb
motion, with ballistic COM before collision/landing. `3D momentum` appended at
bottom of More options (on=fullvector, off=commandedaxis component). No-spin
microgravity art deliberately remains exact:19attacks/684samples pass globally
and after aiming, both modes. No physicaltrack is created for inactive spin.
Saved J2 fullmomentum error<.00043kg m^2/s; prior F140-150 reversal removed.
Five hand/contact cases pass; double carrieroffset atrelease fixed (seam1.64um).
Core≈.7-1ms per60Hzframe at240Hz; separate cached targetplanning≈134ms and full
saved-scene preparation8.77s. Aim is bounded/approximate: saved3D residual≈4.9deg
toward partialaim goal, axis≈22.9deg; no promise of arbitraryphysical hitdirections.
Actualapp/nativeadapter6frames agree; nativeJS package updated. No C++/Blueprint/
editor rebuild, scene mutation or preview-art rewrite. Detailed receipts/scope:
[Current Bodyflip handoff](Labs/BodyflipLab/README.md).

**Bodyflip October31 - physical audit before balance:**
Current saved slash sampled F134-194 through all stages,240/480Hz differences.
All25body momentum about COM along flip axis35.45 atF140 ->-2.00 atF150 ->35.00
atF160 kg m^2/s, despite no contact (minimum collider clearance8.78cm F138-164).
Opposite-angle compensation is an authored momentum target, not a conservation
target; smoothing changes it afterward. Fixed-axis spin ignores moving-limb
momentum, then support-leg follow and aim change it again without reaction.
Post-Hit pelvis return overwrites angular evolution; COM is also not ballistic.
Last joint-order fix removed a real bug but did not resolve these wider issues.
No production/state/editor changes in audit. Detailed findings, recommendation
and physical-audit receipts/chart are linked in the current lab README.
[Physical audit](Labs/BodyflipLab/README.md).

**Bodyflip October31 - compensation now includes joint limits:**
Fixed saved slash's pelvis slowdown caused by computing compensation from torso
rotation that was later discarded. Source, target and solver trials now obey
the existing joints; smoothed output and recovery do too, preserving COM.
F148-150 late spine01 rejection60.8deg -> numerical zero. Saved F144 pelvis
speed along flip axis40->93deg/s; F156406->313deg/s. Intended counterrotation
still changes visible pelvis speed. No percentage, timing, spin or scene edits.
56cases/2750samples across14attacks and both rig profiles pass, including zero
pelvis response to discarded motion, COM and deterministic seeking;17attack
entry and60aim cases pass. Native JS package refreshed; no C++/editor changes.
[Current details and receipts](Labs/BodyflipLab/README.md).

**Bodyflip October31 - live angular-distance arming, all19attacks:**
Direct to Armed now scales GT windup seconds by current->Armed joint angular
distance / accumulated GT windup angular distance. Includes the live harness's
with/without-forearms clock comparison. Removes fixed GT duration floor; keeps
the explicit Attack In minimum and existing smooth interpolation. Kicks share
the clock with viewer/manual paths; both throws now honor Direct to Armed,
retaining charge-specific post-Armed motion and release. Carrier spin and the
separate aiming correction are not part of articulation timing.
Current J2 slash arms in.230350s vs.333333s, hits at2.741053178vs2.844036587.
1141checks across19attacks, actual live-harness distance oracle,2571entry samples,
11221hinge-axis samples,2004kick samples,60aim and6native throw cases pass.
Runtime-only native package updated;48frames/10595values exact V8 parity.
No saved-state/desktop/editor/C++ changes. Lab README records scope and receipts.

**Bodyflip October31 - slash arm snaps fixed; Modified rotations removed:**
Removed the rejected experimental checkbox, setting and solver branch; fixed
combined world-axis spin remains. No saved scene/tuning/playback edits.
Saved slashL had an off-hinge forearm blend, then abrupt joint projection at
F148/F155. Arm keys now fit the existing rig before matching/interpolation;
source spine/legs and attack timings remain. Actual app F130-205 replay:
F148 shoulder/elbow/wrist13.79/13.11/15.00 ->4.25/.60/3.46deg per frame;
F155 28.12/28.10/28.57 ->7.23/4.40/2.64deg.17attacks/2700entry samples,
56arm cases/11520samples (lab/native, both entry modes),60native aim cases and
4381fixed-axis spin checks pass. Tests establish hinge-axis continuity; raw
polynomial angle overshoot still uses existing final joint projection.
Full native JS package rebuilt, native-slash V8 parity8frames/1729values exact.
No editor/desktop use or C++ change. Saved slash receipts under
Saved/Diagnostics/BodyflipPort20261030; current lab README has scope/details.

**Bodyflip October30 - commanded spin axis restored (default mode):**
User rejected the full-tensor experiment's unwanted twist on jump1. Spin now
captures flip/twist vectors in world space and applies inertia scaling along
their combined axis, so a front flip cannot gain an unrequested global twist.
Mixed-spin direction remains fixed between commands rather than following pelvis.
This supersedes full articulated momentum conservation; it is axis-controlled
animation with axial inertia scaling. Recoil/contacts/authored poses remain.
4381 regressions pass including delayed launch, moving poses, all tested axes,
Keep/reversal/zero; measured axis error below0.0000015deg, axial error0.000751%.
Saved260-frame rollout re-recorded, first flip stays in plane, no saved tuning
or markers changed. Runtime-only packaging updated; native parity receipt is
Saved/Diagnostics/BodyflipPort20261030/axis-native-parity.json. No editor use.
Both saved jumps now report Push (1.2354167s /2.2666667s). Native kick/foot/hands
parity passes all24frames with zero numeric differences. Served lab source verified.
[Current lab handoff](Labs/BodyflipLab/README.md).

**Bodyflip October30 - full-tensor conservation experiment (superseded above):**
spin.js now transports world angular momentum between authored commands and
solves full collider inertia plus orbital/intrinsic articulation momentum.
It no longer adds world-fixed flip velocity to a pelvis-following twist velocity.
4365 focused checks pass, including recoil/moving poses/Keep/delay/ramp/zero;
independent collider trajectories give max0.131deg direction error /0.539%
vector error, versus the old frozen-pose combined-spin ~80deg drift.
Runtime-only package rebuilt; native V8 parity24frames/5228values exact. No C++
build/editor or saved setup change. Old scalar-speed spin assertions are
superseded, not reported as passing. Current260-frame replay completes, but its
corrected rotation makes upperarm_l contact at2.2791667s before jump2's planned
push2.31875s, so jump2 now reports Miss. No timing/contact rules were changed.
Jump1's push remains1.2354167s. Free-flight segment vector error below0.179%.
Updated in-chat recording; receipts Saved/Diagnostics/BodyflipPort20261030/
momentum-*. See [lab handoff](Labs/BodyflipLab/README.md).
User accepted the changed pure-flip trajectory and will retime jumps themselves;
keep the full momentum correction and do not adjust their saved markers.

**Bodyflip October30 - typed Blueprint options built and verified:**
User requested normal Blueprint pins instead of JSON. Added typed Settings and
Spin/Pose/Attack structs, attack/push/pose/axis/sequence enums, and normal
Start Bodyflip / Queue Bodyflip Jump nodes. Jump %, Push With and At Time are
direct pins; option structs split into writable pins or Make Struct nodes.
All20 attack choices include None, Sweep Kick and Big/Small Throw. Native pins
use centimetres/seconds/degrees; inheritance distinguishes unchanged spin from
explicit zero. No motion solver changes. Legacy JSON nodes remain deprecated
to preserve prior wiring. UHT and normal build-blueprint-options-retry.log passed.
Unity regrouping exposed a missing UObject/Package.h include in BombBake; only
that include was added, no bomb behavior changed. Source-to-lab mapping checks48
settings/20 attacks. Native Controls.BlueprintOptions passes with zero errors or
warnings: callable reflection, writable/splittable option fields, all attack IDs,
inheritance versus explicit zero, defaults and cm/seconds conversions. Report:
Saved/Diagnostics/BodyflipPort20261030/Reports/blueprint-options. Reused host exited;
no user editor or Play restarted. Updated DLLs load on the next project launch.

**Bodyflip October30 - throws/predictive aim and native port validated:**
Approved jump/landing/starting-yaw checkpoint67516390 pushed and remote verified;
exact saved scene in Labs/BodyflipLab/approved/2026-10-30. New local integration:
Big/Small approved throws share marker UI and Jolt world; actual projectile COM
exit velocity includes body translation/spin. Future complete-body aim honors
Armed/Hit/Release deadlines, joint limits, spine-first bend and necessary residual
pelvis tilt. Legal local-coordinate path removes intermediate rotation snaps.
714 melee target cases,51 dense240Hz paths,72throw cases pass; actual collider
sheets inspected. Default Spin lag60% now covers every spin change; saved0 retained.
878 exact parity checks for lossless optimization; projection median~9.7% faster,
full spin unchanged. Current scenes untouched. Native solver/NN/Jolt port passes
all five final actual physical cases: kinematic/sim, Big Throw, Small Throw,
one-hand push and two-hand push (Reports/release-final). Native entry plans from
the held current pose; hand follow/return continues through landing. Base errors
are5.45cm maximum/.231cm RMS,19.35deg maximum rotation. Both palms register solved
floor impulses inside the push interval. The one-hand segment discrepancy is
2.954cm against the unchanged3cm limit: a narrow pass, not zero physical error.
Actual PHAT hinge/connector IK passes7,224 checks. The physical hinge supplies
the bend plane at near-straight elbows; separate hand departure boundaries avoid
recursive spin-history reads.248 checks/73frames cover release and reverse seek.
All five actual collider sheets and dense hand contact/release frames inspected.
Native profile supplies23 bodies/78.25kg, actual inertia, constraints and shapes;
saved PHAT/tuning and ordinary lab defaults remain unchanged. No motor or test
threshold was relaxed. Normal build-entry-return.log succeeded; the isolated
DLL-copy host is reused, sharing assets and excluding PDB copies.
Private single-thread ORT continuation matches64poses/4profiles within9.65e-6;
V8/ownership/trim/cancellation/budget/finite-parent checks pass. Saved260frame
scene prepares with real NN in62.737s. These are preparation costs, not gameplay
FPS. Earlier lossless wrist/contact replay matched8complete frames/1,740values.
Release cache now matches52 commands against current uncached code, reducing
launch computations54 to10; the latest paging-affected timing shows no speedup.
Final packagecaf24be9 matches Node/V8 exactly on24frames/5,216 numeric values;
the ordinary lab profile retains20 byte-identical complete outputs.
Native CarrierHeading passes. The entry test has105 checks and common blend
checks39; three obsolete F59 knee expectations fail identically with and without
the transition fix, with all other76 checks/metrics unchanged.
Storage follow-up: after explicit user authorization to use the Recycle Bin,
eight disposable cache/obsolete-engine/archive paths (181,474,003bytes,173MiB)
were recycled, with no permanent deletion. Earlier rejected cleanup did nothing.
Receipt: Saved/Diagnostics/BodyflipPort20261030/recycled-files.json. Working host
binaries, packaging dependencies and verification evidence retained. Bin contents
still occupy disk space until emptied. User editor/Play, wiring/tuning, scenes and parallel
Foot IK work remain untouched. Native use is opt-in through StartBodyflip; the
new integration is local, not part of the previously pushed checkpoint67516390.
[Native rig contract](Docs/BodyflipNativeRig20261030.md), [Lab](Labs/BodyflipLab/README.md),
[aim audit](Docs/BodyflipPredictiveAimAudit20261030.md),
[native status](Docs/BodyflipNative.md).

**Bodyflip October30 - starting yaw (approved checkpoint67516390):**
Start yaw appended to bottom of More options, default0deg. Facing only; world
root velocity/path unchanged.180deg uses rotated gait-phase history and the
existing seeded NN for backward locomotion, with trim-bounded recurrence.
Idle/Space rotate pose only; jump sources follow initial heading.3132 checks and
actual F0-60 backward NN pass;809 landing checks retained. Scene untouched,
Checkpoint pushed; Refresh loads. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October30 - landing pelvis heading / continuity (approved checkpoint67516390):**
Landing root yaw follows pelvis facing; both history poses and root commands
enter the unchanged NN in that frame, then predictions return to world space.
Root momentum/path unchanged. Current twist300 landing179deg stays backward
through F228;808 previous-scene +809 backward-scene checks pass,1126 earlier
jump checks pass. No scene writes or server restart; included in checkpoint67516390.
[Current details](Labs/BodyflipLab/README.md).

Preceding continuity fix:
F195 traced to two landing blend errors: rotating virtual-root reference back
to NN identity orbited the physical pelvis, and backward extrapolation of a
future NN endpoint invented the right thigh loop. Rebase only the virtual root,
retain physical world pose, then transition to the actual seeded rollout.
Current F194->195 thigh135.3deg ->3.1deg; dense recovery COM forward>=4.51m/s,
root remains5m/s.667 landing checks and1126 prior jump checks pass; old code
fails new detector. Historical body-landing F131 assertion fails identically
before/after; old trim-generation incremental-request assertion also fails on
both versions. Offline collider frames inspected; scene untouched, Refresh loads,
not pushed. [Details/evidence](Labs/BodyflipLab/README.md).

**Bodyflip October29 late - leg continuity / Follow cam (current jump behavior, local):**
Existing camera checkbox now Follow cam (checked follows, unchecked free from
current view; rechecking centres agent). Fixed current F61 knee lock, F80 thigh
branch switch and second-push stop/start. Foot push is now driven by seeded
finite-speed knee extension, with outgoing velocity carried into flight and
requested launch speed as the actuation budget; no8ms root-first impulse squeeze.
World contact planning includes inherited COM rotation. Airborne foot markers,
like hand markers, own their incoming body/root continuation instead of inheriting
the previous carrier's future locomotion landing. Released foot uses one world
reach then one inertial return; removed the two-frame entry and per-frame slerp
branch change. Carrier completes a contact-side release boundary before free
ticks, and final foot-clearance IK preserves intended COM. Hand driver retained.
F60/F61 knee41.84/36.17deg versus41.68/2.60; F79->80 thigh9.39deg versus122.9.
Both markers push; procedural push/release timing changes, marker times retained.
1126 current-scene checks,300 follow,120 zero-follow,96 paired-bounce and693
flat/inclined/wall-skew driver checks pass;
9 hand-recovery and6 strength/spin cases checked; actual collider sheets inspected.
Small~0.22deg zero-spin projected hip boundary difference remains in edge cases.
Current generation plus369 projected samples~3-5s. EvidenceSaved/BodyflipLab/
LegContinuity/. Live state/Unreal/desktop unchanged; no server restart or push.
Refresh loads it. [Current details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - initial world-space leg follow-through (superseded above):** Released foot
keeps aiming at its last push point through whole-body rotation, then returns
to the moving animation. Leg follow s appended at bottom of More options,
default0.20; existing Leg controls return. Zero disables follow. Damped extension
carries release knee speed without snapping to maximum reach; no renewed pin,
extra force or limb stretch. Actual departing pose and COM retained. Hands keep
independent follow/return. Saved two jumps still push.300 world-aim/subframe/
length/COM/seek/UI checks and122 zero-follow release checks pass. Evidence:
Saved/BodyflipLab/FootFollow/. Live state/desktop/Unreal unchanged; no push.
[Details](Labs/BodyflipLab/README.md). Refresh loads it.

**Bodyflip October29 - F120 knee pop corrected (local):** Airborne foot SUPPORT/
LOAD/PUSH now uses posed-body collision in the carrier too; the standing capsule
had incorrectly lifted the root15.25cm. Release recovery also applied later root
offsets to its past planted pose, rewriting the knee angle. It now seeds once
from the actual departing contact/root offset/velocity, using completed carrier
ticks. Current F119->F120 right-knee bend46.8->6.8deg becomes89.1->81.5deg. Both
pushes retain timing.122 subframe/length/offset/seek checks and67 crouch checks
pass. Existing blend controls/contact/limits retained. No live-state, UI,
desktop, Unreal changes or push. Saved/BodyflipLab/Knee120/; Refresh loads.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - foot buildup begins before contact (local):** Larger
grounded jumps start the extra tier time before their marker (Y100/full200ms by
default), then continue the same crouch through approach and load. Airborne
foot buildup starts at the marker. Root momentum and upper-body source motion
continue; grounded knees bend while gait feet retain their world trajectories.
Existing tier duration/depth controls apply; no new UI. Failed approach also
blends the crouched body back. Current run: prepF44/contactF56/pushF60,9.65cm
displayed lowering at contact and12.10cm authored depth on push;5m/s root retained.
Both saved jumps push.67 focused and335 momentum checks plus isolated airborne
root/capsule regression pass; trim extension retains prefix. Older aggregate
handBoth25 pin assertion also fails before this change, recorded in README.
No live-state/desktop/Unreal changes or push. Evidence: Saved/BodyflipLab/EarlyCrouch/.
[Current behavior](Labs/BodyflipLab/README.md). Refresh loads it.

**Bodyflip October29 - prior first-jump LOAD diagnosis:** F56 Run
at5m/s,100% jump,300ms buildup/15% bend. Reach reserve ends loading after29.17ms
with14.58cm root advance;300ms lowering curve reaches only0.097cm of12.24cm
depth. Displayed pelvis drops0.105cm. Earlier preparation/stance travel is needed
for a deeper crouch; squeezing full depth into29ms would snap. No load/support
tuning changed. Evidence: Saved/BodyflipLab/LoadDepth/. No live state edits.

**Bodyflip October29 - reachable airborne foot rejump fixed (local):**
Second foot jump was rejected because its buildup used the standing capsule:
root was below the floor reference, so capsule correction lifted it20cm and
forced a reachable73.5cm leg to91.2cm (>80.8cm limit). Airborne foot loading now
uses posed-body collision, excluding pinned foot/ball; grounded capsule behavior
unchanged. Saved second push succeeds with upward release; first jump unchanged.
Miss reason corrected to distinguish actual spin release from no push travel.
New frozen-bank regression and335 momentum checks pass. Existing F136 hand
landing assertion also fails against pre-fix source; recorded separately.
No live state/Unreal edits or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - separate hand return slider (local):** Hand return
directly below Body/Leg in the left panel (user placement correction),
default0.4s, independent of existing legBlend.
Hand entry/abort/follow recovery and caches use the new clock; left Limb label
now Leg. Hand follow remains hold duration. Live state untouched.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - hand recovery double blending fixed (local):** Saved
F146-150 rush came from re-blending an already blended pose plus continued
contact aiming during return. Corrections now use untouched animation; final
projection preserves blended direction during return. Hand follow0.1s and
Limb0.2s unchanged; saved F140-160 trace spreads return earlier, peak shoulder
step15.98 to13.31 degrees. No live state edits.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - independent hand cone angle (local):** Hand cone degrees
appended at bottom of More options; existing Cone degrees now feet only.
Hand candidate ranking and approach both use independent handCone. Legacy scenes
inherit prior shared angle; later saves retain both values. Independent15/60 and
60/15 queries, migration, bounds and syntax checked. No live-state edits.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - hand cone diagnostics (local):** Added Hand cones at
the end of the viewport toggles. Both prepared cones visible; yellow crosses
distinguish chosen contacts from large pre-cone ideal circles. Released hand
circles turn red. Saved F132: L contact~22cm from ideal; R already released by
spin/contact limits. Diagnostic-only; motion/state untouched.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - support target toggles (local):** Foot targets and
Hand targets appended to the viewport checkbox row. Both default on; hide/show
active support circles and contact guide independently, without recomputation.
Paired hand candidates both green. Normal scene persistence; live state untouched.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - world-space hand follow-through / playback cost (local):**
Added Hand follow s at the bottom of More options, default0.25s, followed by
existing Limb recovery. Released pushing arms aim back at captured world points
from their moving shoulders; final anatomical projection preserves that aim as
far as joint limits allow. Two-frame continuous entry; actual push/COM/release
timing unchanged. Prepared foot/hand pose reuse and60Hz kinematic sampling reduce
saved-scene offline motion p95 from25.9ms to1.92ms (excludes rendering); simulated
mode stays240Hz. Arrow steps and Step wrap inside trim brackets regardless of Loop.
Seven trim cases and six hand/spin release cases pass (max seam0.077mm). Browser
global/served-source checks pass. User now testing live; no state/desktop/Unreal
changes or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - continuous COM spin and simulated tracking (local):**
Flip/twist now specify target deg/s; blank Keep inherits through foot/hand pushes,
explicit0 brakes, and rotation continues until real landing. Delay is after
release; Accel/Brake remain in More options. Inertia % appended there defaults100,
scaling by reference/current axis inertia. Shared25-body/45kg model matches actual
Jolt mass properties; all rigid turns preserve COM. Legacy nonzero angles migrate
in memory to old mean speeds, duration/absolute-angle controls hidden. Paired pins
release the incompatible hand; loss of both ends the push. Release blending uses
collision-corrected sockets, keeping COM and gravity.0% actions now collide too.
Both modes use shared legal joints and physical/visible-body clearance. Sim uses
real dynamic bodies, pelvis-only absolute position and compatible attachment
velocities. Fast turns substep adaptively. Seeded landing NN blends from actual
contact using Body time.33 Jolt cases/12,490steps plus9 contact cases/3,024steps;
all17 attacks, all12 axes, poses, inheritance, hand release and3600deg/s tested.
Saved3.4s motion:1.53cm peak joint-target difference versus old>1m; full collider
frame sheets reviewed. Attack self contact can still transiently deviate8.2cm.
310 COM checks pass. Live scene/settings/playback unchanged, no desktop/Unreal,
restart or push. Refresh loads. New behavior supersedes finite-angle timings below.
[Current details, limitations and evidence](Labs/BodyflipLab/README.md).

**Bodyflip October29 - full hand-push/NN landing replay corrected (local):**
The earlier contact-only fix missed the cause: authored loading consumed nearly
all arm compression, leaving a3.26ms partial push and downward COM release.
The elbow then genuinely landed atF139.75; actual NN recovery raised the body.
Longer authored buildup now reserves usable push travel by testing at most eight
earlier integrated endpoints when the drive is truncated before reversing its
incoming velocity. Chooses the longest complete drive, with energy from that
endpoint only; no root braking, limb stretching or changed landing eligibility.
Same current scene/contactF134 now loads4.17ms, pushes33.75ms, releases2.27125s
with COM vy+2.36m/s. Airborne through trim2.55; offline extension lands pelvis
atF172. Actual seeded NN recovery also resolves posed-body clearance, preventing
its knee from penetrating the floor while retaining root/joint rotations.
Whole sequence rendered with actual collider geometry throughF204; real17-frame
NN continuation used one bounded single-thread CPU worker.106 body-landing,
127 travel/36cases,96 legacy/paired,335 momentum,310 COM,9 recovery,30 trim and18
release checks pass, plus tier cases. Existing successful/legacy output unchanged.
Scene/markers/playback untouched; no desktop/Unreal, restart or push. Refresh.
Evidence: Saved/BodyflipLab/FullHandMotion/. Supersedes prior F136/F139.75 outcome.
[Current behavior and verification](Labs/BodyflipLab/README.md).

**Bodyflip October29 - hand release contact no longer ends flight (local):**
Current F128 hand marker released at2.25534s; the same lingering right-palm
contact incorrectly became a new landing3ms later. Released support now retains
its body-part/surface contact identity until geometric separation. Collision and
normal response remain; later recontact or another body part can still land.
No timer or change to push/plant/release. F136 now FALL with1.75cm body clearance;
actual later upper-arm landing2.32917s.18 release checks,100 body-landing,310 COM,
9 recovery and30 trim checks pass. Current state/timing preserved; no live NN,
desktop/Unreal, restart or push. Refresh loads.
[Current behavior and verification](Labs/BodyflipLab/README.md).

**Bodyflip October29 - actual airborne body landing (local, unpushed):**
Jump flight/hand support now collide using posed renderer-matched body volumes,
replacing the standing capsule that landed above the floor. Locomotion keeps the
native standing capsule. Real descending body contact on an upward surface seeds
locomotion from the exact visible pose; root/history rebase does not lift the body.
Intended support palms keep their push solver; other body contact can interrupt.
Hand preparation no longer inherits an earlier jump's hypothetical landing root.
Saved F131 remains airborne with57.55cm body clearance. Unchanged F136 hand marker
then meets real right-upper-arm contact at2.29583s before both palms plant; Miss
reports the contact. Offline1.95s marker completes paired release at2.23926s.
95 geometry/handoff checks,310 COM,9 recovery,335 momentum, tier/contact and30
trim checks pass. Landing test uses a deterministic policy stand-in; no live NN
or desktop visual QA. User scene/playback/markers untouched, no Unreal/restart
or push. Refresh loads. Supersedes earlier capsule-based landing/outcome timings.
[Current behavior and verification](Labs/BodyflipLab/README.md).

**Bodyflip October29 - composite supporting-foot choice (local, unpushed):**
Auto selection now scores actual sole-to-contact distance after the cone, minus
bounded forward placement along surface-tangent velocity. The previous ankle
travel metric included reorienting into Plant even for grounded feet: reported
soles were both~1.8mm away but ranked20.8/12.6cm. Lead preference fades at rest;
high front feet can lose, invalid cones stay unavailable, manual choices and
penetration handling remain. Stable1mm score tie; no scrub history. Existing
phase tooltip shows contact/score, no added/rearranged UI. Hand choice unchanged.
338 selection checks cover noise/rest, reversed/sideways travel, height, finite
edges, slopes/walls, old inclined regression and96 real gait poses. Momentum335
and tier/contact/trim checks pass. Saved first jump now selects L, loads210.4ms
at2.00002m/s; later hand still pushes using existing R-hand fallback. This
supersedes the previous trailing-foot22.9ms/paired-hand outcome below. No state
write, desktop control, live NN/Unreal/restart or push. Refresh loads.
[Score, current replay and verification](Labs/BodyflipLab/README.md).

**Bodyflip October29 - jump buildup momentum corrected (local, unpushed):**
X/Y/full Jump % tiers remain, default35/70% thresholds and100/200/300ms.
Options stay at the bottom of More options. Longer buildup now lowers the
pelvis relative to the root and bends the planted limb; other joints keep the
current NN or jump-animation motion. Removed the rejected spring pulling the
root toward the plant, free-leg IK and separate crouching-root workaround.
Root keeps incoming momentum plus gravity; only capsule contact removes inward
normal velocity. Reach/compression can end buildup early instead of braking.
Base push duration/strength and small-tier behavior retained; equal times use
the original path. Body blending recovers pelvis height after release. Both
palms fit against the lowered body; wrist caches reset when loading commits.
335 momentum/source-motion checks, tier/geometry/trim/save/UI suite,96 legacy
bounce,310 COM,9 arm-recovery and12 wrist checks pass. Current first jump stays
at2.00002m/s; its trailing foot ends loading at22.9ms on reach. The later paired
hand push completes200ms and succeeds (supersedes previous miss report).
No scene/playback write, desktop control, live NN/Unreal/restart or push.
Refresh loads. [Details and verification](Labs/BodyflipLab/README.md).

**Bodyflip October29 - F142 hand recovery snap fixed (local, unpushed):**
Saved Body0.4s/Limb0.2s setup exposed a45-51cm hand discontinuity atF141.225:
arms finished Limb recovery then re-entered the unfinished Body blend. Hand
Body recovery now excludes the supporting arm chains; Limb alone owns their
return, followed by the target animation. Free arm/torso retain Body timing.
Nine timing/single/both-hand regression cases,310COM checks and12wrist cases
pass. No tuning, UI, saved playback, foot blending or contact changes. Refresh
loads the fix; no service restart, live NN, Unreal or push.
[Details and verification](Labs/BodyflipLab/README.md).

**Bodyflip October29 - hand playback performance (local, unpushed):**
Saved Both hands setup reproduced repeated raw/contact/COM solves: four240Hz
ticks could evaluate the hand source12times per displayed frame, with catch-up
amplifying stalls. Shared per-segment hand pose caching now retains the expensive
support/blend interval, merges only floating-point drift at fixed ticks, and
bounds arbitrary-time/angle caches. Capsule contact corrections reuse only the
same source frame and exact root; returned pose arrays remain private copies.
Same offline scene's hand approach drops from18.9ms to0.56ms mean per displayed
frame of motion work, excluding physics/rendering.32 checks/818 before-after
frame comparisons pass (saved scene difference4.27e-13), plus310COM checks,
9paired-hand/12wrist cases and30trim checks.240Hz contact checks, motion,
COM/wrist constraints, trim-only preparation and incremental extension retained.
No UI/state edits, live NN, Unreal, service restart or push. Refresh loads.
[Details and verification](Labs/BodyflipLab/README.md).

**Bodyflip October28 - two-hand pushes and hand COM (local, unpushed):**
Push with appends Both hands. Shared torso, real two-palm capture/wait, one drive;
individual arm/capsule constraints, ordinary Auto fallback when pairing cannot
work. No UI rearrangement or extra timing options. Legal wrist pitch stops short
of flattening when needed to clear the displayed forearm capsule; twist and Jolt
bounds unchanged. Current saved90-degree/50% scene can pair: right palm first,
left95.8ms later. Saved scene itself remains left-hand mode.
COM audit confirmed artificial acceleration from airborne torso/arm motion and
recovery (previous release blend added~2.17m/s upward). Airborne approach now fits
whole-body translation and wrist targets together; actual floor/capsule/palm
contact permits external forces. After release, completed animation/flip/attack
poses and root share one COM trajectory seeded from actual release position and
velocity. Capsule subframe interpolation, paired velocity projection and grounded
wall classification corrected. Hand ascent timing/paused flight velocity use COM.
310 inertia,57 current-scene,12 strict wrist and96 paired-drive checks pass;
focused paired/UI/trim checks also cover fallback and finite-edge misses.
Saved single/pair free-approach COM residual<2nm; released residual<4e-15m.
Foot prefix and original single-support drive preserved. Earlier foot-flip COM
drift remains outside this hand change; its actual incoming velocity is inherited.
Cached offline checks/collider sheets only; no saved-state/UI/Unreal/NN/service
restart or push. Refresh loads it. [Current behavior](Labs/BodyflipLab/README.md).

**Bodyflip October28 - wrist-limited hand support (local, unpushed):**
Palm contact now bends backward relative to the solved forearm, retaining allowed
incoming twist/deviation instead of adding a world-space hand twist. A palm that
cannot flatten within its wrist pitch range stays inclined. Shared wrist.js and
physics.mjs retain the existing Jolt45/40/55-degree limits and reference frames;
3,408 tests include agreement with the actual WASM clamp below5e-7 rad.
Arm/contact/capsule composition and subframe samples use the same constrained
hand orientation. Retreat comparison removes changing palm-clearance offset,
while preserving finite-edge failures. Both hands in Idle/Walk/Run pass the
existing grounded geometry checks. Twelve strict wrist/contact cases include
half-ticks, inclined/wall contacts and finite-edge failure; added twist<4.2e-7rad,
pin error<1.8e-15m. Exact57-check saved motion regression and collider sheets pass;
source handoffs below retain their earlier numerical receipts. Updated legacy
suite:405 checks/6,193 poses, zero-load pinning, legal misses and18 unchanged foot
comparisons. No UI/state takeover, Unreal/NN work or service restart. Refresh loads it.
[Wrist behavior and tests](Labs/BodyflipLab/README.md).

**Bodyflip October28 - trimmed generation and hand-push correction (local, unpushed):**
Edits prepare only through trimOut. Extending the end bracket retains the sequence,
segments, capsule/IK caches and recurrent landing-NN state; later markers wait.
Generated NN output has at most one interpolation frame past the boundary; source
clips and required root-command lookahead remain available. Bracket release still
restores the cursor. Recompute clamps a cursor outside the new prepared range.
Refresh captures playback before cancelling obsolete preparation. 30 offline trim
checks cover extension/prefix equivalence, seeks/edits, 0% actions and pending NN.
Cancelled seeks/bracket previews cannot extend a newly edited trimmed sequence.

The saved Scene 2 hand push follows a 180-degree flip. Earlier hand checks missed
its capsule correction: root/pin mismatch produced a 5.75 cm release teleport,
then an unrelated foot-jump pose drove a thigh through the torso. Hand loading now
resolves capsule and arm reach together. Torso/arm recovery follows the incoming
raw articulation with bounded elbow momentum, avoiding the old jump's obsolete
future landing NN. Hand planning separates carrier root axes from body flips;
shoulder clearance uses the surface plane, and the palm heel clears its actual
forearm end cap. No usable push travel means no active impulse.
Grounded hands now use a forward hip hinge, prepared leg rotations and an
outward elbow plane; no per-frame thigh-frame switch or arm/knee crossing.
Release enters the pelvis-aligned fall loop instead of walking in midair.
57 exact-scene, 423 isolated/6,350-pose and six grounded L/R cases pass; measured
grounded shell/plane discrepancies stay below 1 mm. Foot numerical paths match.

Existing Push with and Hand bend controls stay in place; saved foot defaults,
contact-selection rules and the foot path remain. The exact-scene regression
uses the committed gait bank, full capsule composition and collider measurements;
legacy isolated contacts and marker/persistence tests remain separate. Actual
collider sheets: Saved/BodyflipLab/HandReview/. This is kinematic support with a
root capsule, not a torque/finger-grip controller. No UI takeover, live-scene
writes, Unreal work, service restart or push. Refresh loads the change.
[Current behavior and verification](Labs/BodyflipLab/README.md).

**Bodyflip October28 - Sweep kick full turn corrected (local, unpushed):**
The initial import passed parity tests but both app/viewer shared broken motion:
zero-spin balancing opposed the source turn, and absolute pelvis return from Hit
erased its continuation. Full-body kicks now carry continuously unwrapped authored
heading around COM, balance articulation relative to that frame, and recover only
added balance while native pelvis tilt/follow-through continue. Root axes remain
the locomotion anchor. Same shared path for all three kicks; upper attacks unchanged.
No added duration or UI. Sweep completes-359.25deg like source; entire striking-leg
motion retained to<2.1e-15 through End.1,858 focused winding/continuity checks,
2,118 direct/2,316 normal integration,2,700 entry and9,500 aim samples pass.
Actual collider meshes reviewed offline across50 sweep frames including recovery,
with source/before/after/aimed comparisons and both existing kicks. See
Saved/BodyflipLab/SweepTurn/. Authored heading is prescribed: relative balance is
not a zero-world-angular-momentum claim. No desktop/browser control, live-state
writes, Unreal/NN/server restart or push. User Refresh loads both app and viewer.

Authored import:
Imported recoveries/sweepKick.fbx read-only:36 frames at30Hz, Armed8/Hit17,
right-foot full-body strike. Circular aiming reaches correction at Hit. App,
marker and kick-viewer selectors append Sweep kick; one authored variant.
Original16 datasets/binaries untouched. Ideal target derives from the existing
right-foot contact at17 because this FBX has no target annotation. Reproducible
exporter and source hash recorded. Direct-to-Armed knee-entry overshoot fixed
with bounded hinge interpolation only for invalid entry curves; native sweep
and valid old entries retained.232 old-entry samples unchanged;2,118 direct and
2,316 normal integration samples and2,700 all-attack entry samples pass.
No saved-state mutation, desktop/browser control or Unreal/NN/server restart.
User Refresh loads it. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October27 - spine-distributed static aim (local, unpushed):**
Aim adds pelvis yaw only. Pitch/roll correction is distributed across five
spines for hand/head/sword contacts, or the hip for foot contacts. Existing
pelvis animation/compensation is preserved. Non-chain local rotations, knees,
sockets and root stay unchanged; a common translation preserves physical COM.
Cached three-parameter solve fits the calibrated vanilla Hit contact direction
after articulation. Kicks/jabs/pike arrive at Armed; others at Hit. 100% fully
aligns direction; lower amounts scale yaw and bend. Radial reach is not forced.
Undo rotation remains at the right of the viewport row, default on; off retains
yaw and deformation after End/Out, including transitions between contact chains.
8,580 samples/all16 attacks/both entry modes and32 release-toggle cases pass.
Added pelvis tilt below6e-16 radians, direction error below9e-9. Saved Slash L:
156.71 degrees yaw,6.08 degrees total spine bend at100%,zero added pelvis tilt.
Saved80% retained. Camera nearly vertical orbit remains. No bodyflip logic,
UI control, scene writes or Unreal/NN/server restart. User Refresh loads it.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October27 - approved kick and attack-entry checkpoint:**
Pushed and remote-verified as `2e512bc1c005630c694ecb1a1a9e6b00dc2e30d1`
on codex/standalone-sim. Recovery:8958 files,1,073,713,440bytes, no LFS pointers.

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

**Imperial spear October28 — concept04 Lotus bud rebuild:**
Previous flattened-leaf model rejected. User selected Lotus bud and requested
a planned rebuild, then clarified a four-peaked FLOWER cross-section for the
MAIN BODY. Four radial ribs surround broad Bezier concave scoops; comparable
width/depth, axis diameter49.00mm and4.351mm scoop below peak chord.
The scoops now contain integral closed leaf insets (0.55mm recess,
0.10mm raised flat lip) with tapered tips. Circular necks meet stepped collars;
the lower seat has a straight land and separator. BudV3 has six recessed arched
petals, flat lip lands/inner bevel steps, seated root and beveled button throat.
70 other components and original4K atlas bytes
preserved. User explicitly requested the same existing head gold; the pommel
uses M_ImperialSpear_PBR and the plain gold atlas region. One material slot.
Bud extends31mm below prior cap; total2.231m. Shaft/head/grip fixed; grip
is1.266m from new tip. Source/game/FBX/GLB/LODs and previews refreshed.
End-on body and diagonal previews document the radial cross-section.
Triangles46,836/25,758/13,114;17 convex hulls, max60vertices,4 sockets.
Current source/UV/normal/material preservation, actual collision containment,
wood join and main/LOD FBX readback checks pass. Current audit:
`Pommel_Lotus_Verification.json`; previous leaf audits are rejected-stage history.
Unreal import/cooking/physics remain untested; appearance awaits user review.
Owned hidden Blender closed after bounded3-thread CPU work. No Unreal/Play/BP/lab
state changed. [Current handoff](Docs/ImperialSpear.md).

**Broad storage cleanup October26 —11.61GB recycled, about8.95GB net reclaimable:**
User authorized careful project-wide cleanup plus related disposable caches.
Recycled1,445 files (11,607,151,778bytes), with every bin payload SHA256-verified.
Loose Diagnostics reduced14.43→6.21GB:1,126 old bulk text captures/logs are retained
losslessly in `Saved/DiagnosticArchives/HistoricalBulkBefore20261019.zip`
(2,653,710,038bytes), independently read back/hash-verified before binning originals.
Current scripts/summaries/recent captures and code-referenced fixtures stay in place.
Also recycled exact duplicate old BP backups/generated copies, old crash dumps/
rotated logs, Python download/unpack caches, and the optional old project
`DerivedDataCache/Compressed.ddp`. Unreal may regenerate derived data on next use;
current Zen cache and incremental C++ caches retained.39,735 protected files across
assets/source/plugins/binaries/build caches/robot handoffs/benchmark directories
checked against pre-audit sizes/mtimes: none missing or changed. All FPS/100-agent
references and Jolt migration benchmark material retained. No editor/build/process
restart, user assets, training data/environment or Git history changes. Bin was not
emptied; net saving after keeping the archive is8,953,441,740bytes once emptied.
Manifest/duplicate replacement paths/verified receipt:
`Saved/Diagnostics/StorageCleanup20261026/`. Old diagnostic links may now require
extracting the exact archive member; see [restore notes](Docs/Recovery.md).

**Robotics cleanup October26 — recycled1.94GB of obsolete build patches:**
Audited the robot port, camera checks, transfer fixtures and handoffs. Recent
robot/camera diagnostic folders total about29.4MiB; no multi-GB port dump found.
Moved94 obsolete Live Coding patch files (1,943,291,063bytes) from Binaries/Win64
to Windows Recycle Bin. Each entire patch group predates its normal module build;
current October26 camera patches and normal binaries retained. All94 recycled
payloads verified by SHA256. Weights, assets, source, training/environments,
transfer/100-case/performance evidence and incremental caches untouched. No
editor/build process was running; none started/stopped. Bin was not emptied, so
disk space is reclaimed only when the user empties it. Exact manifest/receipt:
`Saved/Diagnostics/RoboticsCleanup20261026/`. Camera cold-launch build requirement
below still applies. [Cleanup details](Docs/RobotLocomotion.md).

**Throw Lab October27 - approved throw checkpoint and aero investigation:** standalone lab and exact
user-approved scene library saved in `Labs/ThrowLab/approved/2026-10-27/`.
Includes both source FBXs (cache hashes verified), runtime animation/object
caches, Jolt, tools, desktop launcher and complete saved tuning/undo history.
Checkpoint `a0ce0db2` plus exact-byte recovery fix `6c5f94dd` on
`codex/standalone-sim`;9004 recovery files/1,083,829,824bytes verified, no LFS
pointers. All three approved files match their manifest hashes in Git.
Current big throw uses Imperial Spear with Throw F34. Whole-frame rotation
editing, quaternion interpolation, Ctrl precision, inline axis readout, fixed
world target, free/orbit camera and1x playback cap included. Source and focused
mouse/physics checks pass. Snapshot inventory verifies the selected commit.
User subsequently authorized velocity-to-spear snap and aerodynamics: now
implemented locally, not pushed. Button below Launch velocity aligns direction
to the held spear at exact Throw frame; amplitude/twist/keys/camera/playhead
preserved, one undo step, repeated aligned click is a no-op. Air enabled by
default for spear/sword, with per-throw On/strength/pressure-position/damping
controls below Launch velocity. Applies dissipative relative-airflow forces
and torque through Jolt120Hz, preserving roll/gyro/contacts; none while held,
for Bomb, asleep or during cached replay. Off restores exact prior flight.
Implicit force response bounds high-speed/small-inertia impulses. Reused WASM
vectors, no new worker/loop/hull cooking.16 snap/81 force cases, both-throw
physics/replay/extreme-control contacts, grip/scale/floor/target suite, actual
browser controls/undo/Refresh pass. Model remains uncalibrated; user Refresh
loads it. Approved checkpoint/profile and live state file untouched.
Follow-up: user reported spear still flat. Reproduced actual saved F54 scene:
air active for40 substeps, but only0.74degrees nose-down. Replaced transverse-
speed-squared normal drag with full-airflow-speed times transverse velocity;
effective normal coefficient-area increased0.04 to0.24m2 for visible short-flight
response. First correction gave10.80degrees nose-down at F54. User still found
the later saved throw weak: normal response now increased another4x to0.96m2.
Latest F62 error improves11.54 to4.73degrees, pitch-14.29degrees, with saved
settings untouched. Original F54 fixture now has4.59degrees error. This is game
tuning, not measured realism. Launch spin now has its own sidebar section;
signed Twist velocity updates on input and switches to manual immediately,
zero stops spin, negative reverses it, blank input is ignored. Existing auto
mode/rates preserved; grouped undo and ten signed/zero Jolt launch cases pass.
Actual-scene numeric
and isolated browser/Refresh regression, passivity/extreme controls and scaled
contact tests pass. No saved settings/launch edits or desktop takeover.
Study assumptions/sources and implementation details are in the lab README;
evidence under Saved/ThrowLab/, including the separate AerodynamicsStudy/.
See [lab handoff and restore steps](Labs/ThrowLab/README.md).

**Throw Lab October27 - rotation readout moved into label:** removed native
rotation-axis title tooltips and the pointer-following value box. Hand/forearm
offset now appends to the existing right-side WORLD/LOCAL label, axis-colored,
while hovering/dragging. No new overlay over the joint. Existing offset math,
precision controls and state unchanged. Isolated mouse checks verify label
placement, live values and absent native titles; screenshot at
`Saved/ThrowLab/rotation-label-readout.png`. Press Refresh.

**Throw Lab October27 - precision rotation:** holding physical Left Ctrl scales
rotation-ring mouse deltas to30% for hand, forearm, weapon and velocity. Can
press/release mid-drag without jumping; Right Ctrl, translation and scale retain
normal behavior. Modifier tracking precedes the active-drag shortcut guard and
clears on blur/hide. Focused four-tool/transition/tangent checks pass; no state
writes or desktop control. Press Refresh.
Extended to camera rotation in both orbit and free modes using the same physical
Left Ctrl tracker and incremental30% deltas. Mid-drag changes remain continuous;
pan/zoom unchanged. Lightweight pointer-handler checks pass for both modes,
modifier transitions and normal Right Ctrl behavior. User Refresh loads it.

**Throw Lab October27 - room brightness:** slider at the top of the left sidebar
adjusts background/fog, floor and ambient lighting immediately. Range0-100%,
default40%;0% matches the old dark room. Saved per scene, undoable in one drag,
retained through copy/Refresh. Isolated WebGL pixels/uniforms, undo/redo and
Refresh verified; launch/camera preserved. No live state writes or desktop
takeover. Local source only; user Refresh loads it.

**Throw Lab October27 - playback speed cap:** slider and input handler now stop
at1x; saved settings, scenes and undo/redo normalize higher speeds to1x.
Slow motion0.1-1x retained. Focused boundary checks pass; user Refresh loads it.

**Throw Lab October27 - whole-frame rotation correction (supersedes subframe
authoring below):** diagnosed saved forearm motion:25 keys across14 frames,
including four subframe targets within F26; playback detoured through those
and default integer poses. Hand/forearm edits now snap BEFORE capturing the
drag axis/base. One key per whole60fps frame; nearest-frame migration prefers
the closest sample, preserving existing integer poses on collisions. Applied
on scene/settings loads and undo/redo, so old histories cannot restore subframe
targets. Adjacent frame offsets use shortest-arc quaternion interpolation,
avoiding Euler-wrap spins. Unedited integer frames still use original animation.
Armed, key fields, scrub and A/D now use whole frames. Throw alone retains
fractional authoring and exact release-pose/velocity sampling. Whole-timeline
Reset scope retained. Original saved state backed up in
`Saved/ThrowLab/BeforeWholeFrameRotations-20261027-150239/`; live file unchanged.
Refresh normalizes the latest saved edits; weapon transforms, camera and throw
timing preserved. Numeric regression fixture/1500+ samples/Jolt release, isolated
actual mouse snapping/axis/Refresh/undo checks and updated main browser suite
pass. No desktop takeover or Unreal work. [Current details](Labs/ThrowLab/README.md).

**Throw Lab October27 - S toggles gizmos:** plain S hides/shows all gizmo
overlays, their readout and contextual Reset, retaining the selected tool.
Selecting a gizmo explicitly unhides it. Per-scene flag survives Refresh and
uses normal undo. Typing/modifiers/repeat/active drags are protected. Free-camera
backward movement is now Shift+S; plain S has priority. Focused shortcut and
save-roundtrip checks pass. No live state edits; user Refresh loads the change.

**Throw Lab October27 - downward camera range:** orbit tilt now reaches nearly
straight down/up (89.94 degrees) instead of stopping around42 degrees downward.
Vertical orbit preserves viewing distance; tiny pole margin avoids inversion.
Saved poses remain compatible; steep-angle zoom remains usable. Focused camera
math/restore/zoom/free-transition checks pass. Background-only change, no live
state writes or desktop control. User Refresh loads it.

**Throw Lab October27 - rotation axis readout:** hand/forearm rings now show
a signed degree offset from the authored default beside the pointer on hover
and during dragging. Uses the displayed axis, including hand world/local and
forearm local, rather than stored Euler channels; hand excludes upstream forearm
edits. Hidden off-ring/for other tools, no layout or saved-state changes. Numeric
quaternion and isolated mouse hover/drag checks pass; screenshot at
`Saved/ThrowLab/rotation-axis-readout.png`. Press Refresh; live app untouched.

**Throw Lab October27 - Reset scope corrected to whole timeline:** hand and
forearm Reset now remove all keys for the selected joint across the selected
throw, even when invoked from an unedited frame. Editing itself remains per
frame. Other joint keys, weapon transforms/scale, other throws and tuning stay
intact. Button stays enabled, with scope in its tooltip; one Ctrl+Z restores all
removed keys. Isolated whole-timeline/scope/undo/Refresh checks pass. No live
reset was performed; press Refresh to load the button behavior.

**Throw Lab October27 - Reset availability:** greyed Reset meant the selected
rotation was already at default, not an Armed-frame lock. Reset now stays enabled
for an active rotation gizmo; default clicks are harmless no-ops with no undo
entry. Armed remains a marker only. Isolated mouse checks verify hand/forearm
rotation and reset at F0, before/at Armed and after Throw in the animation.
No live state writes or desktop takeover. Press Refresh.

**Throw Lab October27 - whole-frame navigation:** added **Whole frame** directly
beside the footer frame counter. Pauses and rounds the playhead to the nearest
integer60fps frame; .5 rounds up. One-shot navigation, no key/settings mutation
or undo entry; fractional authoring and normal Refresh persistence retained.
Press Refresh to load. No live state or user desktop changes.

**Throw Lab October27 - hand/forearm edits are frame-local:** removed sparse-key
carry-over and the last-key hold. Every unedited60fps integer frame uses its
original authored rotation; fractional samples interpolate only within their
neighboring integer frames (and any explicit fractional keys). Hand and forearm
share this behavior. Explicit saved edits retained; weapon grip/scale stay
constant. Contextual hand/forearm Reset clears that joint across the selected timeline
(as clarified in the latest Reset-scope correction). Numeric checks cover unedited neighbors/gaps/tails,
fractional interpolation and release continuity. Isolated browser mouse/key/
reset/undo/Refresh checks pass; a forearm edit no longer alters a later unedited
release frame. No live state overwrite, Unreal or desktop takeover. Press Refresh.

**Throw Lab October27 - contextual rotation reset:** one compact viewport
button appears for the active hand/forearm/weapon/velocity gizmo, with a matching
label and scope tooltip. Hidden for scale/all-off; enabled at default (a no-op). Hand and
forearm reset the whole selected timeline (latest scope correction above). Weapon resets rotation
only, keeping position/scale; velocity restores direction while retaining
amplitude/twist. Other tuning/throws/weapons and camera/playhead stay unchanged.
Reset pauses, is one Ctrl+Z step, and saves through Refresh. Checkbox layout
remains fixed. Isolated mouse/scope/undo/redo/Refresh checks pass; screenshot
`Saved/ThrowLab/contextual-rotation-reset.png`. No live state edits or app takeover.
Press Refresh. [Lab handoff](Labs/ThrowLab/README.md).

**Throw Lab October27 - left forearm gizmo and hand-key reset:** user clarified
"calf" means left forearm. Follow-up correction: Show forearm gizmo at the elbow
now uses the forearm's OWN current local XYZ axes, following its edited rotation.
All three mouse axes verified against current forearm orientation; elbow/upper
arm stay fixed. Existing keys/interpolation and weapon edits are preserved by
retaining parent-space key storage and converting local gizmo deltas into it.
Per-frame fractional keys per throw; then hand keys. Only forearm
subtree moves. Weapon local grip/scale retained; release velocity follows edits.
Mutually exclusive with other gizmos, one drag per undo step, scene/Refresh saved.
Removed the user's two saved big-throw hand keys at F26/F27; no small-throw keys
existed. All other settings, camera/playhead and weapon transforms compared and
preserved. Undoable reset with exact-list guarded one-time stale-window repair.
Backup/receipt: `Saved/ThrowLab/HandReset-1793092569480/`.
Both-clip numerical checks, all three mouse axes, subtree isolation, fixed elbow,
weapon preservation, launch updates, undo and Refresh pass. Screenshot:
`Saved/ThrowLab/forearm-gizmo.png`. No Unreal or user desktop interaction.
Press Refresh. [Lab handoff](Labs/ThrowLab/README.md).

**Throw Lab October27 - local XYZ weapon scale editor (corrected):**
Gizmo selection follow-up: hand/velocity/grip/scale checkboxes are mutually
exclusive; selecting one unchecks the rest, and the active one can be turned off.
One undo step restores the previous tool. Saved multi-tool states normalize to
one. Removed scale percentage inputs entirely: local-axis gizmo editing only,
with stable checkbox positions. Browser selection/layout/undo/Refresh checks pass.
Refresh layout follow-up: green Refresh is centered below New/Copy/Rename/
Snapshot in the header, with space above the camera buttons. Same save/reload
handler; isolated1280px/1000px layout checks pass. Press Refresh to load.
Viewport order follow-up: **Imperial Spear** is now the far-left checkbox,
before Two-tone. HTML order verified; Refresh loads it.
**Edit scale** now shows three colored local-axis handles with square tips and
gizmo-only independent X/Y/Z editing. Replaces the uniform handle/slider. Handles
follow the rotated weapon basis; each changes only its own axis about the grip,
with10-200% bounds. Prior scalar sizes migrate to equal XYZ values. Scale remains
constant per throw/weapon, saved in scenes/Refresh and covered by grouped undo.
Grip pose, hand keys and camera remain unchanged; L only affects hand rotation.
Render positions/normals and Jolt shape/COM/inertia use the same local XYZ scale;
configured mass unchanged. Isolated mouse/local-axis/mesh/undo/Refresh checks and
Node/WASM unequal-scale release/replay/floor checks pass. No user desktop/state
writes, Unreal or resident process. Press Refresh. Screenshot/receipts under
`Saved/ThrowLab/`; [lab handoff](Labs/ThrowLab/README.md).

**Throw Lab October27 - Imperial Spear and constant local grip editor:**
Added bottom-viewport Vanilla checkboxes **Imperial Spear** (replaces the sword)
and **Edit weapon grip** (local movement arrows plus rotation rings). Separate
position/rotation offsets for each throw AND weapon; constant while held,
independent of hand animation keys. Gizmos use an orthonormal weapon basis and
pivot at the grip; sword default geometry is preserved within8.16e-9m after
reframing its old hand-space cache. L still affects only the hand gizmo.
One drag is one undo step; both toggles and offsets survive scenes/Refresh.
Imported the specified `Exports/ImperialSpear/SM_ImperialSpear.fbx` directly with
FBX SDK: full21,112-triangle/2.2m render mesh, grip pivot, nine authored UCX hulls
in one Jolt compound body. Cosmetic tassel excluded from collision. Atlas colors
sampled per triangle for the existing lightweight lab renderer (not full PBR).
Grip-aware COM velocity/release continuity, shaft twist, all local mouse axes,
per-throw/per-weapon independence, undo/redo and Refresh verified. Compound
spear target/floor tests pass; tested final hull penetration up to5.21mm.
Receipts/screenshots in `Saved/ThrowLab/`, notably `grip-verification.json` and
`imperial-spear-grip.png`. No user state overwrite, desktop takeover, Unreal,
server restart or new resident process. Press Refresh. [Lab handoff](Labs/ThrowLab/README.md).

**Throw Lab October27 — Vanilla throws authoring ready:** new tab selects big/small
throw. A/D now step backward/forward one60fps frame using typed letters (AZERTY
compatible), retaining fractional offsets. Both pause playback; typing/modifiers
and gizmo drags are protected. Plain D takes priority over free-camera movement;
Shift+D retains camera-right. Frame navigation creates no undo entries. Browser
shortcut/fractional/free-camera checks pass. Press Refresh.
The tab selects either
throw. Latest correction: Ctrl+Z/Shift+Z now use typed Z, fixing the physical-KeyZ
binding on AZERTY. Local hand gizmo now uses current hand orthonormal axes and
quaternion rotation about the picked normal; world mode retained. Closest-ring
geometry picking replaces SVG paint-order picking at overlaps, with hover feedback.
Browser checks cover all local/world axis deltas, overlap selection, QWERTY/AZERTY
undo/redo, Refresh and preserved camera/playhead. Undid the user's next two hand
edits from the real saved history; both are retained in redo. Exact-settings
guarded repair also handles stale-window Refresh. Backup/receipt:
`Saved/ThrowLab/UndoAxesRecovery20261027-1793082518162/`. Press Refresh.
The tab selects either
throw. Ctrl+Z undo / Ctrl+Shift+Z redo now cover tuning edits, key changes, gizmo
drags, resets, selectors, target/trim/view settings. One drag or focused numeric
edit per step; scene-local history survives Refresh (100-step/1MiB bounds).
Undo pauses and retains camera/playhead; navigation does not fill history.
Restored user's sole big-throw F33 hand offset [0,0,31.113577207342754] to authored
pose by removing that key. Backup/receipt in
`Saved/ThrowLab/UndoRecovery20261027-1793081807665306700/`; unrelated live state
verified unchanged. Exact-match, one-time local repair guards against an older
window saving that key again on Refresh. Undo/redo browser checks and history/
repair unit checks pass; no desktop takeover or server restart. Press Refresh.
The tab selects either
throw with independent tuning. Fractional armed/throw frames; armed means ready-pose
marker only (user clarified), with exact seek/capture buttons. Key local left-hand
XYZ rotation on any animation frame; interpolate degree offsets, retain other joints.
Root-relative launch direction offsets and amplitude default to animation-derived
COM velocity. Angular launch is now twist-only about the hull's long principal
axis; animation projection by default, editable signed degrees/frame or zero.
Jolt gyroscopic motion/collisions stay free after launch. Keys, fractional timings
and tuning persist through Refresh/scenes; prior stored timing retained.
Follow-up: separate Show hand gizmo / Show
velocity gizmo checkboxes (off initially, scene-persistent), now on the bottom
viewport row after Two-tone/Bones/Free camera, visible only for Vanilla throws.
L now toggles hand rings between absolute world XYZ (default) and current local hand
axes. Label/tooltips show mode; scene/Refresh retains it. Switching preserves poses;
typing/modifiers/repeats/active drags do not toggle. Both mode drags and keyboard
guards/Refresh pass. World edits convert back to existing local offset keys; prior
keys/numeric controls preserved. All three mouse axes and rotation conversion
across full turns/Euler singularities pass. RGB rings key
the current fractional hand frame or rotate launch direction; velocity arrow/rings
anchor at release COM. Drag pauses playback and preserves camera, frame, amplitude
and twist. Both widgets can coexist; no extra render loop or hidden projection.
All hand axes/velocity drag, hiding and Refresh persistence pass in the isolated
browser. Script-load bursts reproduced ERR_CONNECTION_REFUSED; sequential boot
loads fix the tested Refresh workflow without a server restart. One cached preview
plus existing small world; no workers/watchers/Unreal/UI takeover or live-state
write. Four clip/object numerical cases and source poses passed; browser checks
cover editing, Refresh and clip independence. Press Refresh.
[Current controls and validation](Labs/ThrowLab/README.md).

**Throw Lab October26 — hand release and object physics ready:** desktop **Throw Lab**
launches `Labs/ThrowLab` on8893 with its own settings/browser profile. Authored
`recoveries/big throw.fbx` (66 frames) and new `small throw.fbx` (35 frames), both30Hz.
User deleted/replaced the mistaken nine-frame big throw2; importer/reference and
picker updated, retired saved selections migrate. Left-hand selector now offers
the existing sword as spear placeholder and original CC0 bomb. Right-side More
options sets per-clip release frame/At playhead; inherited COM/angular velocity
then single-body Jolt gravity and floor/fixed-target collision.180-frame
flight tail; authored agent holds last pose. All timing UI now uses zero-based
60fps frames (release, scrubber, trim markers and clip ranges); saved timing
preserved. Frame conversion/scrubbing/Refresh checks pass in the isolated browser.
No aiming, explosion or agent collider.
Sword-impact follow-up: Jolt gyroscopic force was disabled by default; all axes
were already free. Reproduced user's release F33 / target hit F41. Identical
prefix through impact, then enabling gyroscopic motion changes the rotation-axis
direction by about100 degrees from F42 to F54 versus effectively zero before.
Enabled for released objects; mass/geometry/release velocities retained. Both
clips/objects and the added F33 sword hit/landing/replay checks pass in background
Node/WASM. No user UI or saved settings changed; press Refresh to load.
World target was already fixed, but root-follow camera/grid made it look moving;
both are now world-anchored. Bodyflip-style controls/Refresh/settings retained.
All101 source poses match; four clip/object physics cases and browser workflow
checks pass, including reverse replay, release timing, gravity/contact/sleep and
fixed target/camera. No user desktop takeover, Unreal, other-lab edits or inference.
Small below-normal loopback server; workerless cached browser physics only;
owned test browser closed. Desktop/taskbar follow-up: distinct teal target/orange
spear icon; launcher uses `/throw-lab.html` for a separate Chromium URL-app
identity (port alone does not distinguish root URLs). Reopen existing Throw Lab
from its updated shortcut. Shortcut/favicon and headless smoke verified; no
taskbar UI takeover or other-app restart. [Workflow and source details](Labs/ThrowLab/README.md).

**Player robot camera October26 — loaded without restart, verified:**
NN↔robot camera switches now have separate Blend In0.4 / Blend Out1 controls
through Set Locomotion Camera Blend (Agent defaults Self). Robot target is actual
15-body mass-weighted COM X/Y on floor Z0; spring height/settings and independent
BP offsets retained. Uses existing player camera follower, new sidecar storage,
60-tick authored timing; no retained layout changes or NPC COM sampling. Successful
switches activate it automatically; Get Up↔Clanker keeps the same follow. Repeated
settings do not restart blends. Four camera/real-rig handoff tests pass. Minimal
Live Coding16 affected units882.69s, then1-unit safeguard145.19s; final reload
13:45:04UTC. Saved dirty PoseAgent before reflection, prior bytes backed up.
Full BP graph and saved BP/TestNN hashes preserved; LiveAgentTypes status3/native0/
pins0. New node defaults Self,0.4,1.0 verified. Editor27348 remains TestNN/outside
Play; no user session or scene tuning changed. **Normal DLLs predate this camera
addition: minimal normal build before any cold launch.**
[Implementation and current checks](Docs/RobotLocomotion.md).

**Robot locomotion October26 — contact correction installed and verified:** both
Get Up and Clanker now opt out of speculative response per contact point, using
the shared spherical32 rig and unchanged weights. Also fixed missing callback
installation for robot-only worlds and its bypass in the scoped-protection
listener. Robot admission installs the callback; removal retires it unless
another feature needs it. Ordinary contacts retain the native default.
Actual production UE rig + NNE check now passes100/100 saved Get Ups and16/16
five-second walks, including all15 native MuJoCo walking successes. AgentSwitch,
ordinary contact settings, scoped defense and sword-reaction checks pass:6/6.
The intermediate99/100 Get Up,10/15 walking transfer failure remains recorded;
it exposed the missing listener ownership, not a reason to weaken assertions.
Native Development dependency and minimal normal UE builds passed. Saved dirty
PoseAgent BP and TestNN before closing PID22068; preserved hashes still match.
Interactive TestNN PID27348 is open and verified: five nodes/three enum values,
LiveAgentTypes status3/native0/pins0/wiring preserved. Owned12-frame Play smoke
initialized all three user BP agents and ended cleanly; editor remains outside
Play. Loaded native DLL matches the build manifest. No assets saved by checks.
No Blueprint wiring, tuning, weights or PHAT assets changed. Exact spherical
limits remain in one packaged rig because stock PHAT cannot represent them.
Run and long fixed Get Up holds remain unvalidated; native MuJoCo also fails the
old run controls. Do not generalize the passing walk/Get Up suite to those cases.
[Current integration and evidence](Docs/RobotLocomotion.md).

**Bodyflip October27 - whole-leg inertia experiment stays in the viewer:**
Left hip-to-foot direction stopped sharply around frames51-52 at Slash L/100%.
Peak acceleration275.45rad/s^2 barely changed without yaw correction (271.83):
reference hip/knee motion was still imposed directly. New viewer-leg-response.js
tracks root-relative thigh/foot orientations and hinge knee bends with continuous
angular position/velocity (legs24rad/s, pelvis32). Upper orientations and rigid
sockets retained; no knee-position IK. Left peak vector acceleration falls75%,
retaining92% of swing; right falls62%, retaining84%. Focused0/50/100%, hinge,
socket, reverse-seek, analytic-rate and bounded-cache checks pass. This is an
angular posture response, NOT exact physical momentum conservation. Existing
viewer compares prior yaw-only response with whole-leg response. Refreshed tab4,
inspected52/58, restored paused25/100% and camera. No lab motion/default/state,
Unreal, NN or server changes. [Details and receipt](Labs/BodyflipLab/README.md).

**Bodyflip October27 - compensation editable in the existing comparison:**
User wants to work on this motion in the viewer before returning to the lab.
Added0-100% Compensation slider/number at header right; live updates preserve
frame/camera/play state. One plan shared by both canvases. Preview motion/event,
amount, time, camera and play state persist per tab across refresh, independently
of lab saves. Existing IAB tab4 refreshed in place; no duplicate opened. Verified
0/100, blur commit and refresh/frame retention; restored80 and resumed playback.
No lab motion/default/state, Unreal, NN or server changes. Future experiments
stay in the viewer until user asks to carry them back. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October27 - inertial yaw response fixes lower-body jitter:**
User accepted reference poses but rejected jitter. Measured tickwise pelvis-rate
reversals from exact momentum matching plus hard hip-lag projection. Planner now
drives a critically damped angular response (32rad/s); yaw position/velocity carry
between ticks, analytic sampling keeps acceleration continuous, no displayed
hard clamp. Reference hip/knee poses and upper motion retained. About63ms yaw lag;
instantaneous old momentum budget is intentionally relaxed, NOT exact conservation.
After cache end, analytic settling preserves final turn without snapping velocity.
At80%, peak pelvis acceleration falls94% Slash L/80% Slash RU; peak turn retained
85%/82%.6424 pose checks, focused rate/acceleration/tail/reverse/cache checks,
94 sequence regressions and owned UI/manual checks pass. Comparison now shows
previous immediate vs new inertial yaw on the same reference poses; fractional
playback clock removes rounding steps, still30Hz render cap/hidden pause.
Saved/BodyflipLab/soft-legs-inertial.gif. No live state, Unreal, server, training
or push changes. Refresh. [Details and momentum limits](Labs/BodyflipLab/README.md).

**Bodyflip October27 - human-reference leg motion replaces speed-driven knees:**
User rejected the shared turn-speed bend as arbitrary/uncanny. Soft legs now
adapts rounded Wagner2011 jump-throw hip/knee curves: different leg roles,
Armed/Hit timing, continuous phase clock, smooth entry/return, shorter gestures
for shorter strikes. Hip flexion follows pelvis forward; canonical hinge permits
knee extension as well as flexion. Real phase metadata used for scheduled/manual
attacks. Existing Amount and Soft legs controls retained. Hip yaw lag18 degrees.
Upper world orientations/sockets preserved; yaw solver still matches the old
rigid correction's momentum budget, NOT full3D conservation. This is reference
adaptation, not sword mocap.6424 pose/hinge/tilt/reverse checks,94 sequence checks,
rigid comparison and owned UI/refresh/manual checks pass; reviewed Slash L/RU
frames. Very fast source clips can still require rapid hip yaw at100%.
Current comparison: soft-legs-preview.html; half-speed recording:
Saved/BodyflipLab/soft-legs-reference.gif. Earlier Soft legs versions/recordings
are superseded. No live-state write, Unreal/server restart, training or push.
Refresh lab/comparison. [Behavior, source and limits](Labs/BodyflipLab/README.md).

**Bodyflip October26 - pelvis attack compensation:** appended0-100% at the
bottom of More options, default50%. Opposes attack-added spine_01 yaw on the
pelvis, then corrects spine_01 to keep upper-body world orientations unchanged.
Pelvis position/socket geometry retained; legs follow the counter-turn. Applies
after attack blending (scheduled/manual), excluding whole-body flip yaw.1676
compensation samples,580 transfer samples,94 sequence/30 Jolt checks and owned
browser option/frame/refresh/manual tests pass. No live-state overwrite, push,
Unreal/server restart. Refresh. [Behavior](Labs/BodyflipLab/README.md).

**Bodyflip October26 - attack pelvis rotation transferred to spine_01:**
Upper-only attacks now carry the source pelvis rotation relative to clip start
into the first spine, including twist and lean. Actual pelvis/root/legs stay
with underlying motion. Corrected pose drives matching, entry, native playback
and return; manual Strike uses the same transfer.580 source-pose comparisons,
94 sequence checks,30 actual Jolt checks and owned browser scheduled/manual
checks pass. No UI changes, live-state overwrite, Unreal/server restart or push.
Refresh existing window. [Transfer details](Labs/BodyflipLab/README.md).

**Bodyflip October26 - five spine boxes matched to Jolt:** user chose retained
box appearance with matching physical shapes. Replaced three grouped torso
proxies with one bone-local box per spine_01..05, using shared dimensions/offset/
rotation for rendering and Jolt. Scheduled attacks already start at spine_01;
manual Strike/aim now uses that same upper-only mask. Pelvis stays excluded.
Five spine constraints/masses/COM offsets retained; torso geometry/inertia now
matches display.30 focused actual-Jolt checks,94 motion regressions and owned
browser frame/manual-attack checks pass. No UI rearrangement, Unreal/server
restart, live-state overwrite or push. Refresh existing window.
[Details and remaining display scope](Labs/BodyflipLab/README.md).

**Bodyflip October26 - Space gym and scheduled vanilla attacks ready:**
Sequence appends zero-gravity Space gym using existing markers. Jump % defaults100;
0 gives no push, higher values increase jump energy. Popup appends Jump %, Attack
(None +16 vanilla melee/sword clips) and delay; Attack In/Out append at bottom of
More options. Closest pre-Armed upper-pose match, adapted Final Harness entry,
then native Armed->End playback; root/pelvis/legs preserved. Actual attacked pose
feeds NN landing. Space has no contact/NN requirement, constant impulse drift,
and retains ground scene platforms for mode switching.97 focused checks,52 editor,
84 motion and38 blend checks pass. Isolated browser verified two layouts, editing,
playback, refresh and ground restoration; writes intercepted/browser closed.
No Unreal/server restart, live-state overwrite or push. Refresh existing window.
[Behavior and source provenance](Labs/BodyflipLab/README.md).

**Bodyflip October26 - shared Foot IK integration, desktop restart pending:**
FootIKLab `surface.js:createFeet()` is the canonical contact solver used by both
labs. Bodyflip API6 serves current source modules on Refresh with isolated
globals; no copying, watcher or shared UI/state. Grounded incline locomotion uses
Foot IK contact/roll/reach/knee rules plus capsule-to-mesh pelvis compensation.
Jump support/push/flight retain their authored control. Corrected pose history
feeds falls/NN landings; crest transitions do not double-apply old tilt. Foot IK
checkbox appended at bottom of More options.1529 integration checks +84 motion,
78 knee and24 capsule checks pass. Six full Foot IK clips remain byte-identical
through API extraction. Browser verified live-source loading, six frames,
comparison/playhead and graceful old-server fallback; saves intercepted.
**Main8876/PID27312 remains API5**: automatic approval rejected the verified
Bodyflip-only restart ("blocked by policy"). No alternate restart attempted.
Foot IK stays disabled with a restart-needed label there. Isolated API6 preview
8891/PID12412 and owned browser closed. No Unreal/FootIK server changes or push.
[Shared contract](Labs/FootIKLab/SHARED_API.md), [Bodyflip details](Labs/BodyflipLab/README.md).

**Recovery October26 â€” accepted checkpoint handoff exported:** latest accepted
13-11-28 pelvismax final161960, 3.669B samples, packaged in
`Exports/MimicKitEquipment/Recovery_Pelvismax161960_Unreal_20261026/` with
`HANDOFF.md`, original verified checkpoint, ONNX actor, frozen rig/Jolt32Hz
references and SHA256 manifest. CPU inference parity verified on516 recorded
observations; ONNX Unreal integration remains to be checked. Previous100/100
actual Unreal/Jolt test used Python inference. No training or gameplay changes.
[Details](Docs/MimicKitTransfer.md).

**Foot IK October27 - wall gait frame and anatomical knees corrected:**
Prior "wall leg folding corrected" receipt failed visual acceptance. Its
nearest-feasible-knee rule could reverse the NN hinge; mismatched surface
travel and torso-relative pelvis height produced the seated/crab posture.
Mesh origin now follows the capsule ground reference along the surface normal.
NN pelvis translation/lower chains share the ground frame; Upright changes
posture about the pelvis, not standing height. Source-stabilized signed knee
hinges follow their thighs, including straight-leg samples. Removed arbitrary
world-up wall lift and opposite-side obstacle-clearing knee selection. Departure
keeps one position filter without collision momentum. Material heel/toe/yaw
pins, relative ankle limits and actual recurrent root windows remain.
15 frame/hinge +17 coupling +697 directional surface +101 Upright-endpoint
checks pass.1368 shared Bodyflip adapter checks pass; its host is untouched.
Saved Run143 pelvis height87cm in ground frame; minimum knee-hinge dot0.984
across both601-tick live Run/Walk clips. Native parity3.61e-6, features2.39e-7,
root replay error0. Visual review includes wall and wall-as-floor sequences20–300.
Late unbounded-speed descent can exceed the NN's useful gait range (Walk cadence
fades); no universal motion-quality claim or speed/input cap. Final actual app
load error-free, actual-root coupling; cold surface request19.1s, not instant.
Older wall-contact fixtures/receipts are rejected-history evidence. Current:
verify-wall-frame.cjs and wall-frame-{run,walk} fixtures. No UI/state write,
Unreal/server restart or push. User Refresh. [Details](Labs/FootIKLab/README.md).

**Foot IK October27 - simulated root now drives the actual NN (initial receipt):**
Inclines/edited surfaces now couple120Hz root/feet to a retained30Hz lower/upper
NN stream. Actual root history and8 fresh physics-predicted future positions/yaws
replace the old constant-speed gait command. Surface frame transports velocity;
Upright is posture only. Phase, native pins, Walk-at-Run-policy speeds and yaw
schedule retained. Shared createFeet/API1 unchanged;41 legacy tests still pass.
One bounded CPU request uses a short-lived shared-JS physics peer and validated
cached NN decoder; playback does no inference. Actual physical speed uncapped.
First-next-root decoding now matches native encoded-window bounds, preventing
the prior fast-fall rebase mismatch.17 coupling checks pass; all149 measured
history deltas and replay roots match. Native Run/Walk parity<6.5e-6; original
root-window features<2.4e-7. At143 root falls7.234m/s and NN sees the same reversed
travel, now forward relative to facing.7 protected headless app checks and six
collider frames reviewed; current production request cached, saved state intact.
The subsequent wall correction above supersedes this receipt's IK metrics and
fixes the prolonged Walk reach/collision failure. Late high-speed NN motion
remains sharp; current raw/corrected measurements are in the newer entry.
Loaded preparation measured3–7s; cold production request15.9s. No universal
instant-load claim. No user-tab control, server restart, Unreal/Bodyflip edit or
push. Refresh. [Architecture, exact limits and receipts](Labs/FootIKLab/README.md).

**Foot IK October27 - ghost investigated; root heading arrow:**
Current Run36/Left/wall90/yaw200 over1.2–6m/gravity70/unpin1 at143: ghost exactly
matches the rigidly placed source NN at all601 samples; pelvis/upper coincide
with main body. Both tilt39.289°. Actual root falls8.141m/s while the precomputed
NN still follows its forward course with184.286° final facing. Surface gravity
is not fed back into the NN root window; this is an existing host/input mismatch,
not a reversed ghost renderer. No motion fix or recoupling claimed here.
Root checkbox now also draws a yellow facing arrow from actual root position,
using generated root yaw/initial heading plus surface alignment, not pelvis or
velocity.16 focused and41 surface checks pass;8 owned-headless checks and five
frames reviewed. Current full motion byte-identical; saved state unchanged.
No inference, user-tab control, restart, Unreal/Bodyflip edits or push. Refresh.
[Finding, remaining limitation and evidence](Labs/FootIKLab/README.md).

**Foot IK October27 - root-speed pin release and editable platforms:**
More options appends Unpin below m/s (0.2 default;0 off). On actual surfaces
steeper than Minimum gravity incline, total root speed below the threshold
cancels both pins and prevents acquisition; geometric contact/gravity continue.
Root v is below viewport status; + Platform below it. Bodyflip-style W/E/R,
local scale, centre pivot, Delete/Backspace, transform Ctrl+Z and orbit-safe
selection work in Foot IK's own adapter. Layouts persist per terrain; previews
do not replan or infer until release, and retain frame. Edited scenes use surface
root simulation; untouched stairs retain root ramps/foot treads. Reverting all
edits restores the original preset solver. Added platforms catch the root and
receive pins; a far platform leaves the existing wall motion within2e-14m.
Current wall clip minimum speed0.2703m/s, so0.2 does not trigger;0.5 releases the
right pin at46.41 simulation +18 protected headless UI checks pass, including
six unchanged default surface clips, persistence and camera/key interactions.
Shared API1 adds optional allowPins=true; Bodyflip's pin policy is unaffected.
No user-state/tab operation, server restart, Unreal/Bodyflip/NN edits or push.
User Refresh loads changes. [Details and evidence](Labs/FootIKLab/README.md).

**Foot IK October27 - turning upper NN frame corrected:**
Run36/Left3.5m/s/down/yaw200 after stairs exposed a lab conversion bug: the
root-window inverse heading was reused in upper pose codecs that transpose it,
so world yaw was applied twice to upper pelvis/feet/hands. Upper pose frames now
rotate with the root, matching the game's constant lower-to-upper bridge in
LowerTransformToHeading/BuildUpperBaseFromLower. Both history seeds, inference
and decoding use it; root-window features/upcoming turns remain unchanged.
434 steps match independent game equations (upper error1.08e-6); original lower
inference error0. World-rotation equivariance and byte-identical nonturning pose
verified. Current scene's displayed lower joints are unchanged across601 samples,
including real NN handoff103. Resumed shoe penetration remains6.063mm. At212
elbows now92/125deg versus158/162deg.18 collider frames reviewed, no browser errors.
Live8890 returns verified fixed output; user Refresh activates it with state kept.
No restart, user-tab/state operation, Unreal/Bodyflip/terrain/weights/UI edit or
push. [Cause and regression evidence](Labs/FootIKLab/README.md).

**Foot IK October27 - descending released feet no longer trail the old tread:**
Run61/down/yaw200/accent400 at51 exposed a separate support/recovery defect that
the prior straight-descent check missed. Upper-tread pin remained until the leg
was almost horizontal; recovery only accepted rising endpoints and clearance
ran before forward recovery. Descent support now reserves the NN downward leg
posture within reach, then recovers over falling endpoints with incoming velocity
and no later artificial wait. Height fitting sees the recovered path. Current51
foot moves32.10cm forward/16.08cm lower, now22.45cm below its hip; retained material
pins stay exact. Peak pelvis correction18.41→12.42cm. Both current Run and real
Run-policy Walk2m/s tested, plus previous straight/turning descent regressions.
26+28+21 checks pass; six ascent/flat/uneven bank clips byte-identical.28 collider
frames reviewed in owned headless browser, persistence disabled, no browser errors.
Current Run NN handoff73 checked; native post-handoff shoe penetration7.23mm.
Straight Run20 resumed NN has23.60mm penetration; terrain IK is not claimed to
correct resumed raw NN. Walk61 had/has no handoff candidate in5s and retains its
pure-NN flat fade. User scene/camera/playback untouched; user Refresh loads JS.
No restart, Unreal/Bodyflip/NN-weight edits or push. Shared API unchanged.
[Behavior, limits and evidence](Labs/FootIKLab/README.md).

**Foot IK October27 - descending pelvis no longer forces unreachable support:**
Current Run20%, down16/35cm, no yaw, accent400%,42 crouched because an early
lower-tread pin demanded26.87cm body lowering and its recovery envelope retained
the drop. New lower contacts wait for reach with the existing2cm allowance;
supported material pivots stay exact. Descent pelvis curves smooth within reach
bounds, and accent can hold the body above support before lowering, instead of
only adding crouch. Swing reach and toe-off rotation now approach their actual
landing constraints before contact. Run42 correction−23.58→−1.98cm; worst drop
26.87→7.14cm. Actual Run-policy Walk2m/s maximum drop30→11.33cm at400% accent.
28 new checks and21 prior descent checks pass; six ascent/flat/uneven clips remain
byte-identical. Knee steps do not worsen; ankle steps improve for both gaits.
Actual current/history NN handoffs checked; raw post-handoff NN retains small
shoe penetration (17.48mm Run /5.11mm Walk), not claimed corrected by terrain IK.
Prior turning descent remains clear with29.25cm excess foot lift removed.
Owned headless visual checks only; no user-tab control. QA unload accidentally
saved198; original42 restored with a playback-only patch. Settings/camera retained;
test harness now disables persistence itself to prevent further unload writes.
User Refresh loads client JS, no restart needed. No Unreal/Bodyflip/NN weights
changed or push. [Behavior and verification](Labs/FootIKLab/README.md).

**Foot IK October27 - RunB toe-angle comparison:** Saved Run20%, Forward,
downstairs, yaw200 over1.2–6m retains5m/s and finishes192deg; native RunB is3m/s.
Model Viewer launch checkpoint hashes exactly to lab Run weights. Saved frame162
is pure resumed NN after handoff76; displayed/raw foot rotation differs by
<0.000003deg. Same5m/s turn without terrain retains toe-biased gait: minimum
sole tilts17.44/14.47deg versus nativeRunB10.61/8.41 over120–300. No gait/IK,
speed settings or rotations retuned. New Backward reference exposed first-build
JIT issue from prior optimization: trace/freeze now explicitly enables graph
optimization, validates before atomic save and rebuilds invalid disposable
caches. Frozen execution still skips profiling. Fresh/load/corrupt-rebuild
Backward outputs exact, original-controller reference error0. Repaired graph
active; worker source naturally reloads after idle. No restart, user state/app
control, Unreal/model changes or push. [Details](Labs/FootIKLab/README.md).

**Foot IK October27 - descending left-leg height fixed:** Current Run82%, down
16/35cm, yaw200deg/s over1.2–6m, accent400, frame53. Old tread height was carried
from release42 toward next NN plant106 while the ramp root descended, adding
51.75cm to the ankle. Extended existing constrained height fit to descending
carriers, removing surplus toward NN height with full-shoe clearance. No new
settings, side/frame branch, timing or NN change. Ankle29.25cm lower at53; actual
shoe gap43.92→3.47cm. Material pins/rotations/release times retained; peak
pre-handoff ankle step98.39→18.20deg, velocity continuity retained.21 focused
checks pass across full current clip, actual NN handoff73, seek, collision/reach
and bank descents; six ascent/flat/uneven clips byte-identical. NN after handoff
retains~7.22mm existing shoe penetration (7.23mm before). Owned headless views
reviewed with writes blocked; user tabs/state untouched. **User Refresh loads
the fix**. Shared surface API/Bodyflip incline unchanged; no server restart,
Unreal, model/checkpoint changes or push. [Details](Labs/FootIKLab/README.md).

**Foot IK October27 - actual new-phase preparation reduced:** Unchanged Refresh
below did not solve phase edits. Reuse only invariant NN initialization poses,
invalidated by source/weights/geometry/stride/native codecs/Torch; every new
command and terrain handoff still runs the original recurrent NN. Skip redundant
JIT profiling of frozen graphs, retaining eager parity validation. Two full
.20/.31 rollouts preserve every pose, root and pin value exactly. Real app edits
to .47/.73 measured3212/4515ms with both requests newly inferred (no response-cache
hits); frame/renderer retained, writes intercepted. Cold page load still22.24s,
first request17.71s versus1.91s actual inference:30s worker retirement causes
repeated import/model load. Service source now keeps one sleeping worker5min,
then releases it; **lifetime change pending restart** because prior automatic
approval rejected restart as "blocked by policy". No bypass/restart performed.
Worker-side optimizations verified through existing8890 service. No GPU,
background inference, saved-state writes, Unreal/Bodyflip/shared-solver changes
or push. Cache/lifetime tests pass without Torch; ONNX trial rejected for
recurrent motion divergence and removed from active dependencies. See
[current details and timing receipts](Labs/FootIKLab/README.md).

**Foot IK October27 - actual Refresh overhead fixed:** API-only129ms earlier
was not Refresh. Actual IAB full reload5087ms (NN217ms, renderer727ms,
terrain+handoff1983ms). Refresh now checks runtime-file modification dates with
at most4 HEAD requests in flight; unchanged sources retain the ready NN,
terrain frames and WebGL renderer. Adopts other-tab saved edits, re-solves only
motion changes; changed/missing/ambiguous source dates still reload. Server
Date/navigation baseline avoids client clock skew. No polling or solver change.
Activated on8890: unchanged Refresh54.3ms with playback continuing; full script
activation1866ms. Actual app/state/camera/frame/model reuse and code-change
reload verified with intercepted writes in one headless browser; date guards
and9 persistence checks pass. Initial server restart attempt was policy-blocked;
final client-only implementation needs no restart, existing process retained.
No Unreal/Bodyflip, shared API, checkpoint, UI layout or push changes.
[Current details](Labs/FootIKLab/README.md).

**Foot IK October27 - Walk handoff experiment removed; loading audited:** User
rejected the entire arc. Removed extra Walk model, contact-wait detector,
checkpoint swap, lower-inertia exception, checkbox/policy labels and experiment
test; deleted its compiled graph. Archived original checkpoints retained.
Run-only handoff/UI restored exactly to pre-experiment; stale walkHandoff prefs
are discarded. Current initial NN and all continuation poses match the old
Run-only captures exactly. Policy graph cache now hashes graph/native dependencies,
model provenance and Torch version rather than the whole worker, preventing
unnecessary retracing after orchestration edits. Five cache checks pass.
Repeat source+handoff HTTP requests129ms total/no inference; fully uncached pair
including graph compilation13.86s. Current scene results are cached for Refresh.
Single CPU thread/no GPU/30s idle retirement retained. No server restart,
browser control, user-state writes, Unreal/Bodyflip edits or push.
[Current behavior and verification](Labs/FootIKLab/README.md).

**Foot IK October27 - Run turning hover61–94 investigated:** Current setup
is Run38%, stairs16/35cm, yaw300deg/s from1.2–6m, accent400. The right stair
pin releases at59.5 because it needs83.55cm reach versus81.67cm available;
no procedural contact61–72 while the authored ramp root continues. Actual
terrain-seeded NN handoff occurs at73. Its pin strengths are only0–1.60%
on policy frames75–93 (~2.09% at94); floor contact nevertheless returns
around82/91. NN labels mean solver ownership, not absence of neural pins.
The initial NN also slides with weak pinning under this turning command.
Original-controller parity is exact for both sequences, future-window error
<=1.2e-7. Added existing continuous `pins` output for diagnosis, including
phase slicing;152 source and115 continuation poses/roots remain identical.
No gait/IK/tuning/UI change, server restart or push. Distinguish this stair
planner from the incline `surface.js` knee fixes below. The source response
and stair clearance planning both contribute; no forced pins added.
[Details and local evidence](Labs/FootIKLab/README.md).

**Foot IK October27 - exported WalkF comparison fixes vanilla knee fidelity:**
User supplied `Exports/WalkF_Rollout_20261027` (read-only). Two lab errors:
the upper/pelvis decoder re-solved lower knees even with unchanged pelvis,
and Incline/wall at0deg still repinned/re-solved the NN legs. The first moved
knees up to3.95cm relative to the supplied rollout while feet/hips matched;
the second added a12.88deg knee step at60 against the source's0.71deg.
`directional_nn.decode_policy_rows` now composes the upper policy but decodes
lower joints through original lower FK/geometry, preserving predicted thigh
rotations. Both direction generation and nn_worker continuation use it. Frozen
weights, inference, future root window and original NN pin projection unchanged.
With matching source/history, all120 compared frames match the independent
Model Viewer export within0.049mm; rotation-matrix maxerror0.000148. Live lab
uses Run source geometry/settled history, so arbitrary frame numbers are not
the same phase as this fresh WalkF export (geometry alone differs by~0.93mm).
Earlier claims that a pop in the lab's raw NN proved a policy pop were incomplete:
that output still passed through the extra pelvis-decoder knee solve.
**Follow-up: terrain IK repaired and retained on flat ground.** No level-ground
bypass. `surface.js` now filters the terrain residual relative to the NN ankle,
respects natural NN leg extension instead of forcing94% reach, and captures the
incoming shoe orientation without a forced flat/shortened-leg snap. Capture
radius grows continuously from5mm with the requested terrain delta, up to35mm.
Physical shoe support is independent of the hard-pin latch. A deleted platform
can transfer a pin to a finite coplanar replacement containing the same material
contact; actual unsupported deletion still falls normally. Heel/toe roll,
pin yaw, leg length, shoe collision and gravity/thrust rules remain active.
Supplied60 knee step12.88→0.711deg (NN0.711); current left106:9.02→1.99
(NN1.89), left225:7.32→0.59 (NN0.44). Full240/300-frame clips have maximum
extra knee step3.82/3.68deg, with450/547 active pin ticks; corrected poses are
not forced equal to the NN. verify-flat-rollout:24 cases/12,984 frames;
verify-surface:697 checks/60 cases; floor deletion8 cases, root thrust0/45/100%,
and shared Bodyflip adapter1,529 checks pass. Gravity regression compares
unsupported motion; stable supported traction can balance gravity exactly.
createFeet API1 remains compatible. Viewer8890 refreshed, settings/camera and
paused user frame179 retained after visual checks. No server, Unreal or other
lab restarted. NN decoder comparison above remains valid. No push requested.
[Details](Labs/FootIKLab/README.md).

**Foot IK October27 - root marker and optional incline gravity:**
**Viewer / persistence:**8890 API6/save protocol2/PID996 uses
snapshots/overnight-state.json, also explicit in launcher and /health. Reopening
loaded the old45deg preview file; restored last observed90deg wall/Walk69%/
yaw300 from1.2-6m/accent400/ghost on/trim0-299/frame202. Current camera retained;
prior camera unavailable, exact historical missed-save cause unproven. Saves
now merge only edited fields, before motion preparation; startup/idle tabs do
not resave the scene. Close flush/Refresh, atomic durable writes and ordered
client saves prevent stale tab/request overwrites. Old save clients rejected.
Client/server persistence checks and real immediate reload/app Refresh pass.
Only Foot IK restarted; no other server/editor or motion-solver changes.
 Root checkbox
appended after Bones. New mode and Minimum gravity incline / Full gravity % /
Energy conservation % appended at bottom of More options for Incline / wall.
Defaults off/45deg/100%/100%; old scenes retain motion until enabled.
**Revised gravity semantics:** at/above minimum, full gravity acts with no
automatic compensation; no angle ramp toward90. Full gravity % removes
world-vertical root thrust from both velocity drive and the commanded height
spring.100% gives exactly-9.81m/s2 before collision responses;0% retains thrust,
not gravity cancellation. Horizontal thrust and solid collisions remain.
Energy conservation still projects at0% / transports at100%, once per surface
transition.173 checks/18 clips plus3 actual current Run-policy Walk cases pass;
100% has359 active frames at exactly-g and344 impulse-free intervals with exact
velocity integration. Off and below-threshold motion unchanged. Root and
controls remain in place, saved settings/frame retained. Enter commits and
blurs numeric entries; arrows then step playback. More options header stays pinned while scrolling; clicking outside closes it. **Delete floor F** appended
last in More options for Incline / wall only; default-1 keeps it. Selected60Hz
frame removes geometry, collisions and foot pins with no leftover floor force.
Reverse playback restores the floor. Incline extends in both plane directions,
sized for the whole clip's travel/fall, including below the floor. Eight deletion
clips and173 gravity checks pass; browser verified Enter, deletion100 at101,
floor restored at99, and return to-1/frame101. Settings/camera retained. No NN/Unreal/Bodyflip,
shared createFeet API, or server changes for this revision. Receipts in
snapshots/incline-gravity-verification.json and root-thrust-verification.json.


**Foot IK October26 - planted yaw and accepted ankle correction:**
**Wall cutoff removed:** standalone surface root no longer expires after0.55s
Walk/0.85s Run, disables future pins or latches drive to zero. Valid contacts,
reach/ankle/collision limits, bounded traction and gravity now determine motion;
mode reflects current support/vertical velocity. Current Walk69/yaw300/90deg
continues upward at2m/s at206 instead of standing still after timed fall.
17 full clips pass contact-driven checks including both gaits/approaches and
0/45/75/90deg. Existing broad suite stops on its lateral0deg material-pin-slip
assertion; that clip's poses/metrics are byte-identical to pre-change, so this
is not a new regression and is not claimed as a full-suite pass. Shared
createFeet API/host controls unchanged. No NN, Bodyflip, Unreal or restart.
Receipt: snapshots/contact-driven-wall-verification.json.

**Pelvis accent follow-up:** appended Step accent % at the bottom of More
options, range0-400 (expanded on request).100 preserves the previous pelvis rhythm exactly;0 disables
only this accent. Current Walk36/yaw300 UI set to200: extra loading2.107->4.214cm.
Existing80ms smoothing,10cm accent ceiling, pelvis cap and both-leg extension
bounds retained. Root/ankle paths, material pin orientations and contact timing
unchanged; free ankle articulation still follows the corrected calf.211 main
and11 departure regressions pass; six accent levels checked on current actual
NN source plus Walk/Run ascent/descent clearance/reach spot checks. Original
NN checkpoint/runtime unchanged; terrain-exit continuation uses adjusted poses
as before. No server restart, Unreal/Bodyflip changes or push. See
verify-step-accent.cjs and snapshots/step-accent-verification.json.

**Reported225 audit, no motion change:** phase60/stairs/yaw300 current setup
hands off at180; at224 the right knee reaches0deg bend,226 reaches20.79deg.
Displayed225 is exactly resumed NN output; the100ms handoff blend ended186.
Replayed the same seeds/root commands through original controller functions:
referenceError0, root-window error2.98e-8. Pop is already in30Hz decoded poses,
not created by render interpolation or stair IK at225. This continuation uses
terrain-seeded history, so this does NOT prove ordinary untouched flat rollouts
always pop. Earlier35.5 explanation does not explain225. Trace:
verify-knee-225.mjs --reference / snapshots/knee-225-audit.json. UI restored225.
**Flat-approach audit, not yet fixed:** current UI phase60/stairs/yaw300 has
terrain influence from35.5, before the first tread. At that first tick the raw
right sole is2.591mm below flat ground; full floor projection raises it despite
IK weight0.000207, displacing the knee11.51mm. This is a lab entry correction,
not changed NN weights. Flat terrain preset matches raw NN in all601 samples.
Diagnostic: verify-flat-knee-audit.mjs / snapshots/flat-knee-audit.json.
No production code or UI settings changed during this audit.
**Departure follow-up:** the yaw-only arc skip also skipped horizontal swing
travel, causing the reported right82 foot to rise in place. Restored forward
progress independently of the bounded height envelope. Planted turns now reserve
4cm beside risers; blocked turns release with lift room, preserving grounded
toe-off instead of forcing a sharp lift. Current right lastpin65.5, toe-down16deg,
yaw43.42deg.72-82 advance9.96->35.36cm; early vertical peak3.65->1.85m/s.
211 base+6 ankle+262 yaw+11 travel checks pass. Browser reviewed full0-299,
close-up64-90; restored82/camera. No new UI, NN, server or Bodyflip changes.
Earlier frame67/contact-margin receipts are superseded by this follow-up.
Old ankle comparison removed, signed shoe-plane pitch fix retained. Foot yaw
option appended at bottom of More options(default45deg). Planted heading now
turns about heel/toe material support, transferring toward projected sole centre
nearflat; shared surface.createFeet uses the same helper. Original NN allows
rotation with integrated support-point ankle compensation; it has no yaw cap.
Knee poles remain NN/anatomical. Current Walk91/yaw300/start1.2m right67 body yaw
75->41.24deg, knee54.81 vsNN54.27. FullIK pole step1.858deg/120Hz, accel.240;
shoe step8.001deg. Riser-clearance limit can release a trapped contact; turned
swings avoid global endpoint-arc inflation. Final smoothing fades with influence,
fixing the initial straight-knee jump.211 motion+6 ankle+101 surface endpoint
checks pass,12 shared zero-yaw goldens unchanged;262 focused checks pass across
14 actualNN clips and16 synthetic pivot cases. Independent knee audit retained.
Browser refreshed/checked67,70 and option; frame/camera retained. No NN, Unreal,
server restart, Bodyflip file changes or push. See FootIK README/shared contract.

**Foot IK October26 - actual NN yaw window, Run-policy Walk, distance controls:**
Active8890 now supplies previous/current/eight future turning root carriers to
Run181751 + Upper82500, including per-frame pose encoding/rebasing and the
original continuous learned pin projection. Removed post-inference spin and
handoff counter-spin. Walk uses Run at F2/B1.5/sides1.8m/s; Run retains native
F5/B3/sides3.5m/s. Current+previous corrected world poses seed terrain exits.
Root yaw is available on all terrains. Start m / Stop m appended below its
speed in More options; blank Stop is unlimited, stopped yaw holds its heading.
Distances use the horizontal commanded root course, shared with a new metre
counter directly below the frame counter in the existing76px width. Actual
incline gravity mass-point travel can differ from that commanded course.
Future NN windows anticipate both distance boundaries; no elapsed-time gate.
Original training encoder/controller parity checked on five5s directional/yaw
rollouts and Walk/Run boundary cases.211 procedural regressions and12 exact
shared-surface baselines pass; material pins remain anchored. Shared Bodyflip
createFeet API unchanged. One CPU thread, lazy worker, cached replay; no server
restart, Unreal, Bodyflip changes or push. Existing desktop uses8890 and
snapshots/overnight-state.json. Earlier post-spin verification is superseded;
see FootIK README, nn-root-window and yaw-distance receipts.

**Bodyflip October26 - flip/pose blending in More options:** appended Turn,
Flip In/Out and Pose In/Hold/Out after Rebound in the existing viewport panel.
Angles/axis/delay/pose stay in the marker popup. Selection persists when it closes;
the panel identifies J1/J2 and edits that jump without moving playback. New turn
ease periods support constant-speed middle motion, zero ramps and proportional
fitting within Turn. Missing fields migrate to half-duration each, preserving
all existing quintic turns exactly.47 editor +84 motion checks pass; isolated
browser verified both layouts, selection and native numeric edits/playhead.
Saved settings intercepted during verification, browser closed. Refresh needed;
no Unreal, server restart, live-state overwrite or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - per-jump flips and pose slots:** existing marker popup
now appends signed Flip/Twist totals, axis, delay0 and smooth turn duration0.8s;
No pose plus four temporary slots, with collapsed In/Hold/Out timing. Motion
starts after support release; root-heading flip axis, pelvis-vertical twist,
smooth pose entry/exit. Root trajectory and pinned frames unchanged. Both render
and landing NN use the same authored pose; landing interrupts remaining motion
and continues from the current pose. Settings persist per jump/scene; edits keep
playhead time, click-away applies, Escape closes before platform shortcuts.
331 checks pass including12 actual NN landing checks; isolated actual-app browser
render verified two popup sizes and ten motion samples. Test saves were blocked;
owned browser closed. Automatic review blocked temporary browser-profile cleanup
("blocked by policy"); those two Saved/BodyflipLab folders remain. Four
placeholders await the user's poses tomorrow; source
mapping in `jump-motion.js`. Desktop Refresh required, no server restart, Unreal,
other-lab work, live-state overwrite or push. [Details](Labs/BodyflipLab/README.md).

**Foot IK October25-26 - directions and gravity-surface prototype verified:**
isolated apiVersion6 preview8890/PID16304 uses its own overnight-state.json.
Main8878/desktop and earlier8879 remain older processes: automatic approval
review blocked FootIK-only restart ("blocked by policy") despite user approval.
No alternative termination, Unreal, other-lab mutation or push. Main saved
Run/phase21/frame73/camera/settings remain unchanged. Genuine matching backward
and lateral lower/upper NN contexts, native speeds, both-pose continuation
history; flat output exact NN. Travel-basis, bidirectional heel/toe reach roll,
landing continuity and lateral early-clearance corridor corrected.703 grouped
direction checks over48 full5s clips plus focused releases; accepted forward
phase21 Walk/Run byte-identical after final corridor fix,20 targeted checks pass.
Incline/wall adds angle, approach and upright bias at bottom of More options.
Gravity mass-point/capsule root plus kinematic NN limbs, bounded support then
fall; NOT full Jolt/live Unreal. Initial wall clearance and folded free-leg
knee stability fixed without moving pins.696 checks/60 cases +101 endpoint
checks/16 cases and independent32-case shoe-face review pass; worst reviewed
shoe penetration0.07671mm.71 actual HTTP checks +6 mock service guards pass.
Browser checked backward/lateral trouble intervals,45/90deg toward/parallel and
upright endpoints; no console errors. Preview paused120,Walk,45deg Toward,
Upright55%. Source safeguards newer than running8890; desktop8878 NOT activated.
No idle NN worker retained. See FootIK README, current receipts and preview PNG.

**Foot IK October25 - actual NN continuation, preview active:** `handoff.js`
now seeds the original lower/upper policies from corrected current and previous
30Hz poses when the root is past the course, both feet have released contact,
and both rendered shoes clear the exit plane. Current Run/phase21 hands off
at73 using71/73, Walk/phase21 at190. Exact incoming pose retained;100ms local
velocity carry then full newly inferred NN pose, no cached-gait catch-up. Root
speed retained, earlier terrain frames untouched. One CPU thread in a FootIK-only
lazy worker, frozen Bodyflip loader/models read-only, local bounded seed cache,
30s idle retirement verified. No training/GPU/Unreal/other-lab changes or push.
28 new inference/integration checks +346 existing procedural regressions pass;
original-controller reference error0, no riser penetration. NN's existing sole
box ground error remains (Run9.37mm,Walk4.82mm, within raw NN baseline).
**Activation blocked:** user explicitly approved restarting ONLY FootIK8878,
but automatic approval review rejected the scoped restart again with only
"blocked by policy". No alternate kill attempted.8878 remains apiVersion4/PID996;
do NOT claim it activated. Verified apiVersion5 preview8879/PID15472 is retained
for the user; inspected73/80/90 and restored paused73/settings/camera. Main8878
needs manual server restart to load `/resume`; desktop Refresh alone is not enough.
See FootIK README, `handoff-verification.json`, `handoff-suite-status.json`.

**Foot IK October25 - running recovery advances after departure:** Run/phase21
left66-80 followed the NN's backward fold; the recovery bridge was skipped
because its terrain-exit endpoint was still behind the departure in pelvis
space. Find a compatible forward-moving endpoint within the same source swing
and retain correction for that leg until it joins (current94), independently
of terrain influence. Final smoothing respects the available forward clearance
corridor rather than buying premature riser crossing with extra lift.70-80
pelvis-local travel -21.73 ->+20.48cm; forward progress from about70 after initial
toe/riser clearance. Grounded roll/contact timing, right leg and pelvis retained.
346 checks pass plus8 phase/course spot checks. Prior ankle regression's airborne
path/state invariants were updated for this deliberately changed path; rotation,
contact, clearance and reach thresholds retained. IAB refreshed/inspected66/70/78,
restored78/camera/settings. Desktop Refresh needed; no server/Unreal/NN/UI/push
changes. See FootIK README and run-travel verification receipts.

**Foot IK October25 - running ankle exit:** Run/phase21 frame81 held the old
toe-off world pitch while the calf folded, producing104.49deg NN-relative ankle
error and a33.85deg rotation in one120Hz sample at83. Final swings without a
next retained contact now retire the cap over20-40% of the source gait cycle;
the calf-relative rotation no longer fades back toward the held pose at the
terrain exit. Whole-shoe clearance still bounds rotation.81 error0.21deg,
75-85 peak11.12deg/sample. Foot trajectories, material pins, support timing and
pelvis unchanged.288 targeted checks pass; no assertions relaxed. Browser
refreshed/checked81 and83, restored81/camera/settings. No server restart, NN,
Unreal or UI edits/push. Desktop Refresh needed. See FootIK README and
`run-ankle-verification.json` / `run-ankle-suite-status.json`.

**Bodyflip October25 - approved motion checkpoint pushed:** verified remote
`codex/standalone-sim` at `eb74a1a6e5e89e52a703f1f02bca9941f0b0724a`;
recovery inventory verified (8883 files). Includes Idle/shared jump controls,
flat new scenes, capsule
collision with actual NN landing continuation, free camera, matched whole-body
jumps, opaque animation-leg overlays, motion-preserving blends and knee braking.
Walk frame59 now bends28.67deg normally instead of71.66deg backwards; no straight
hold or repeated recoil, original blend deadlines/contact/root retained.265
automated checks pass. User accepted the result; agent visual tools were blocked.
Source, idle recording and verification files are included; live scenes/settings,
previews, inference caches and unrelated sessions stay local. Landing requires the
existing frozen models/seeds and Stepper/Torch runtime; see restore notes.
[Bodyflip details](Labs/BodyflipLab/README.md), [recovery](Docs/Recovery.md).

**Foot IK October25 - final-level toe-off rotation:** left191 was stuck at41deg
despite NN79deg and sufficient clearance. Final same-height departure now releases
the stair anti-roll cap and carries the release offset onto moving calf-relative
NN rotation over120ms; whole-shoe clearance retained. Earlier transfers/landing,
ankle paths, pelvis rhythm and pin timing unchanged.191 pitch79.78 vs NN79.35,
quaternion error38.55 ->4.55deg, sole gap2.65cm.248 targeted checks pass; no
assertions relaxed. IAB refreshed/current191/camera/ghost/settings retained.
Desktop Refresh needed; no server/Unreal/NN/UI work or push. See FootIK README
and `level-exit-verification.json` / `level-exit-suite-status.json`.

**Foot IK October25 - approved checkpoint pushed, pelvis rhythm local:** remote
`codex/standalone-sim` verified at `3bc2cde7304da2bf67491283e6ba9efbce0592e0`;
recovery manifest verified. Only FootIK source/runtime banks/tests and scoped
journal entry included; unrelated work/live state excluded. Subsequent local
pelvis change times smooth loading/pull-up to actual plants, bounded by BOTH
legs' existing extension. Root ramp, ankle trajectories and pin/release timing
retained; calf-relative free ankle and exact material heel/toe pins retained.
Current phase21/Clearance1 added loading max3.37cm, speed0.240m/s, acceleration
3.55m/s2;318 checks pass, no assertions relaxed. Browser checked106/114 then
restored latest paused6/settings/camera. Desktop Refresh needed; no new UI,
server restart, Unreal changes or push of this pelvis experiment. See
[Foot IK details](Labs/FootIKLab/README.md) and pelvis-transfer verification receipts.

**Foot IK October25 - approved checkpoint:** standalone Foot IK Lab preserved
with frozen Walk/Run NN phase banks, terrain placement, grounded heel/toe pins,
smooth swing recovery, full-body/ghost rendering, desktop launcher and regression
fixtures. Includes gentler right155 toe-off (35deg on NN-return departures,
45deg on retained-contact transfers);307 checks passed. Live playback state,
screenshots and unrelated session work excluded. Pelvis stair-transfer work
starts AFTER this checkpoint; see Labs/FootIKLab/README.md for current behavior.

**Foot IK October25 - gentler right155 toe-off:** higher-step departures returning
to NN gait use35deg grounded toe roll instead of45deg; transfers into a retained
contact keep45deg. Early departure timing/material heel-toe pin are unchanged.
Current phase21/Clearance1cm right155-161 peak upward speed4.030 ->3.332m/s
(17% lower), peak120Hz velocity change1.629 ->1.446. Continuous forward/up motion,
release still155, right89-102 identical. All299 existing +8 focused checks pass;
receipt `Labs/FootIKLab/exit-toeoff-verification.json`. See lab README for detail.
IAB refreshed/inspected154 and157, restored155/settings/camera. No Unreal,
server restart, new UI, other-lab edits or push. Desktop app needs Refresh.

**Bodyflip October25 - carry motion across blends:** shared stateless pose/velocity
offset transition replaces captured-pose easing for Body, support release, fall
loop, ledge falls and missed-support recovery. Shoe alignment carries incoming
rotation; contact fitting/heel-toe controls retained. Attack entry/return preserve
authored velocities and hit-window timing; landing still seeds the actual NN.
Body/Leg sliders and procedural pelvis/contact ownership retained; no new controls.
187 checks pass:38 motion,53 matched-body,48 contact,24 pacing,24 capsule/NN landing.
Source slope changes accounted for; release angular-rate error0.00850rad/s at1us.
Contact fixture later-event expectation updated for changed incoming poses; its
geometry/continuity checks retained. Syntax passes; no visual QA. Refresh needed,
with possible landing recomputation. Only existing single-thread CPU worker used;
no server restart, live-state overwrite or Unreal changes. [Details](Labs/BodyflipLab/README.md).

**Foot IK October25 - early departure WITH grounded roll:** higher steps again
prepare up to50ms early; author heel/toe pivot roll before release, up to45deg
toe-down, with smooth outgoing velocity. Material contact/whole-shoe checks and
airborne downward-rotation limit retained. Height-ceiling entry eased to200ms to
avoid post-riser braking;161 default gap18.92cm vs previous14.02 (old23.22).
Current phase21/clearance1 right89 finishes grounded roll,89.5 lifts;88-102 peak
up speed5.54 ->2.93m/s, velocity kick3.11 ->0.84m/s.299 checks pass; previous84-92
failure resolved. Timing/ankle-handoff/height tests updated for requested behavior;
collision/reach/knee/velocity/flat-NN checks retained. Browser checked89/92 and
restored92/settings/camera/ghost; desktop Refresh needed. No UI additions,
Unreal/server/NN/other-lab work or push. [Details](Labs/FootIKLab/README.md).

**Bodyflip October25 - other leg red / frame59-60 diagnosis:** Anim other leg
changed from orange to red; support stays green, Raw leg red. Syntax checked.
Saved Scene 2 left leg near-stop comes from Body0.2s blending out of a captured
launch pose with zero-slope smoothstep: weights3.638%/10.201% at59/60; forward
ankle advance8.47mm versus48.09mm at56-57. Incoming gait velocity is not carried
through this blend. Diagnosed only, motion unchanged. Refresh loads color.

**Foot IK October25 - bound smoothing surplus:** final trajectory height fit
now aims for NN/pre-fit height plus existing clearance, with collision/reach
priority and gradual application after toe-off. Initial release velocity and
material pins retained. Phase21 right161 gap23.22 ->14.02cm, extra NN ankle lift
20.41 ->11.28cm;159-167 keeps advancing/upward.87 focused checks pass; broader
210/211 with the same known84-92 lift-acceleration failure. Existing release
kick6.80m/s unchanged, not fixed. Prep~335ms/cached playback, no UI additions.
Browser checked161/restored latest157/settings/camera/ghost; desktop Refresh
needed. No Unreal/server/NN/other-lab changes or push. [Details](Labs/FootIKLab/README.md).

**Bodyflip October25 - opaque overlay depth correction:** animation leg shapes
were already shared with the agent, but the old X-ray pass disabled depth testing
and writes. Opaque rear triangles consequently drew over front triangles. Moved
all three leg overlays into the normal opaque scene pass, before translucent
platform sides; normal self/scene occlusion now applies. Colors retained. Syntax
checked; no visual QA, motion/physics changes or server restart. Refresh needed.

**Foot IK October25 - retain toe roll / stop airborne over-rotation:** removed
the50ms early-release rule. Phase21 left68-71.5 keeps its material toe pin,
22.39 ->52.29deg down; releases72. Planned/calf-relative swing rotation cannot
continue downward past the actual release angle (previously nearly90deg).
Browser checked71/77, restored69/settings/camera/ghost.79 focused checks pass;
broader suite210/211: default fixture84-92 lift-acceleration bound now fails
without early release. Known regression retained explicitly, assertion unchanged;
NOT all-green. Collision/reach/pins/knees/flat NN checks pass;72 backward snap
still absent. Prep~0.35s/cached playback. Desktop Refresh needed; no Unreal,
server, NN-bank or other-lab changes. [Details](Labs/FootIKLab/README.md).

**Bodyflip October25 - animation leg volumes:** Anim other leg added immediately
right of Anim leg, independently showing the opposite leg on the matched clock.
All three animation overlays now use agent-sized capsules and foot/toe boxes,
sharing geometry definitions; now fully opaque, green for supporting Anim leg,
orange for Anim other leg and red for Raw leg. Tooltip colors updated; syntax passes.
No extra physics bodies or motion preparation. Scene-persisted, default off.
53 focused checks and syntax pass; no visual QA. Refresh needed. No server/Unreal
changes or live-state overwrite. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - whole-body match at normal speed:** Match foot now starts
all animated joints at the matched source frame on PUSH, at1x; removed the
support-only slowdown. Procedural pelvis/root, pinning, loading locomotion and
separate Body/Leg entry blends retained. Fall-loop animation advances with the
shared clock; red Raw leg stays on original timing, purple previews matched timing.
47 focused checks pass (both feet, standing, zero loading, blends, source poses,
root/pins and reverse seek); root/pin differences zero. Syntax checked, no visual
QA. Refresh needed; landing NN will prepare from the changed pose. No live-state
overwrite, server restart or Unreal work. [Details](Labs/BodyflipLab/README.md).

**Foot IK October25 - swing continuity + sole support:** ankle-ray selection
misclassified left68 as flat/NN stance and selected the preceding last tread.
Use main sole centre for support;68 now rolls on a material pin with96.5% reach.
Higher steps get up to50ms lift preparation. Root arrival no longer dissolves a
trailing pin;175-177 retains last-tread support, then departs continuously. Final
bounded XYZ trajectory smoothing follows all positional edits; smooth landing
pitch cap retained.72 backward -4.84 ->forward1.92m/s; peak left-foot velocity kick
6.63 ->0.94m/s in phase21.282 checks pass, prep~0.37s/cached playback. Timing tests
updated for actual contact/foot handoff; full geometry/reach/pin checks retained.
Browser checked68/72/176 and restored latest72/settings/camera/ghost. Desktop
Refresh needed. No NN bank/Unreal/server/other-lab work. [Details](Labs/FootIKLab/README.md).

**Bodyflip October25 - Refresh placement:** moved the existing Refresh button
beside the brand, above the viewport left edge, per the marked screenshot.
HTML/CSS only; existing refresh/save/playback handler retained. Refresh to load.

**Bodyflip October25 - original jump leg overlay:** Raw leg checkbox appended
after Free camera. Red supporting leg follows normal jump timing, bypassing Match
foot retiming/IK/release blend; purple Anim leg remains the retimed target. Both
are aligned to the displayed pelvis. Default off, scene-persisted, redraw only.
Current Scene 2 numerical comparison agrees with source animation to 1.15e-16m;
JS syntax passes. No visual QA. Refresh needed; no server restart, live-state
overwrite, NN inference or Unreal changes. [Controls](Labs/BodyflipLab/README.md).

**Foot IK October25 - first-riser shoe clip:** current phase21 left41 had ~7cm
edge/face intrusion missed by corner-only checks. Full box-face/tread-footprint
clearance now shared by the planner/reach/orientation checks; boundary-only
clipping, cached playback retained. Existing smoothing also covers NN-exit swings,
removing the late175.5 lift snap in this phase.270 checks pass; independent dense
face sampling confirms41 clear, actual material pins retained. Preparation~0.37s.
Browser checked41 then restored188/settings/camera/ghost; desktop Refresh needed.
No NN bank/Unreal/server/other-lab edits. [Details](Labs/FootIKLab/README.md).

**Foot IK October25 - pelvis-local release progress:** replaces world-forward
recovery with a curve, source-release check, collision-bound fit and gait rejoin
measured in the moving/rotating pelvis frame. Saved phase49 right137-147 local
advance4.99 ->15.21cm; every139-150 sample advances,143-147 no relative-speed dip.
Initial137-138 still retreats1.27mm for toe/riser clearance; no zero-drift claim.
261 checks pass, no added vertical lift/UI/playback work. Browser compared147,
restored current150/settings/camera/options. Desktop Refresh needed. NN banks,
root/current pins, Unreal and other labs untouched. [Details](Labs/FootIKLab/README.md).

**Bodyflip October25 - free camera:** checkbox appended after Show jump. QZDS
camera-relative movement; left-drag looks from current eye, inverted Y retained;
existing wheel zoom/unlimited dezoom, middle-pan and target drag retained. Enabling
preserves the current view; disabling now snaps COM to screen center, clears pan/
offset and retains viewing direction/distance. Per-scene camera persistence,
explicit presets return to follow.
No idle camera RAF, inference or motion preparation; keyboard movement also works
paused and stops on focus loss. Writing/Ctrl+Z/WER keep their input ownership.
16 camera checks pass;21 scenes and14 refresh passed on initial free-camera work; visual QA
unavailable. Refresh needed. No server restart, state overwrite or Unreal work.
[Controls](Labs/BodyflipLab/README.md).

**Foot IK October25 - forward recovery after early release:** reach-released
trailing feet no longer wait for the NN's remaining stance while lifting. Cached
forward recovery meets the moving gait, with shoe collision bounds and smooth
anticipation; rejoin early enough to avoid a later waiting stall. Current pins,
root, NN banks/recurrence retained (no live reseed). Saved phase49 right134.5-140
forward2.29 ->11.75cm; left167.5-171 4.55 ->8.91cm, unchanged vertical lift.
257 checks pass; no added UI/playback work/process, prep230ms. Browser checked
140/171 and restored135/settings/camera/options. Desktop Refresh needed. No
Unreal or other-lab changes. [Details](Labs/FootIKLab/README.md).

**Foot IK October25 - remove pre-landing toe-up rebound:** calf-relative swing
was handing back to an airborne NN toe-up peak. Terrain landing now has a shallow
5deg heel lead and late swing aims directly at contact orientation; material
heel/toe pins and negative-pitch push-off retained. Contact geometry now adjusts
ankle trajectories (supersedes preceding identical-path claim). Isolated riser
floor clamps smoothed with a constrained upper envelope; existing knee bounds pass.
Saved phase49 approach77-88 peak29.4 ->5deg;135-141 <7.3deg.245 checks pass.
Browser refreshed/current135 restored; Desktop Refresh needed. No new UI/process,
Unreal, training or other-lab changes. [Details](Labs/FootIKLab/README.md).

**Foot IK October25 - calf-relative swing ankle:** swing rotation now preserves
NN ankle articulation relative to the IK-adjusted calf, smoothly handing back to
world-space contact orientation near pins.120ms anticipation and full shoe-corner
clearance limit; exact heel/toe material pins and hip/knee/ankle paths retained.
Saved phase49 mean SWING ankle error23.45 ->8.05deg;79:63.8 ->39.5deg (near83
contact).211 +18 velocity +7 clearance +6 ankle checks pass; default prep254ms,
no added playback work/UI. Supersedes swing WORLD-rotation test; Flat stays exact.
Browser refreshed/restored79 and settings; Desktop Refresh needed. No Unreal,
server, training or other-lab changes. [Details](Labs/FootIKLab/README.md).

**Bodyflip October25 - capsule landing seeds the actual NN:** corrected the
cached-gait snap. Capture landing + preceding30Hz pose; encode lower41/upper90
history with original frozen Run/Walk/Upper policies and codecs. First output is
exactly the landing, then recurrent predictions follow capsule-resolved movement.
Idle returns to zero-speed Walk NN; its starting idle loop remains authored.
Later jumps use the new continuation; air rotation edits rebuild its seed.
No display crossfade. Kinematic planned-pose feedback; not live Jolt/attack feedback.
Capsule remains native-default30cm radius/86cm half-height, static-slab sweep/slide;
no editor/Blueprint query. 24 capsule +11 NN/codec +20 idle +21 scenes +14 refresh
+24 pacing checks pass. Entry gap0.000268mm over0.1us; compiled step equals original
functions through30 recovery steps, current/prior-pose perturbations affect output.
Single-thread CPU inference only during preparation, serial worker expires30s idle;
compiled steps and bounded result caches. Cached requests14ms; new1s rollout0.245s;
first uncached setup can take seconds (7.4s measured with compiled weights).
Only own server8876 restarted to API5. Saved state hash unchanged; no UI movement,
Unreal/other-session work or push. Refresh needed; visual QA unavailable.
[Current behavior, limits and verification](Labs/BodyflipLab/README.md).

**Foot IK October25 - reduce leading-foot overclearance:** fitted retained-contact
swing heights to actual shoe clearance/NN height, lowering the global arc's surplus
as the foot passes the hip. Keep trailing toe-off, forward timing, pins and root.
Saved phase49 frame163 sole gap20.17 ->5.42cm;132 forward swing samples mean
14.07 ->8.07cm (43% reduction).211 +18 velocity +7 clearance checks pass without
loosening prior motion/knee/collision bounds. Cached preparation164ms; no extra
playback work. Refreshed browser at163, original camera/settings retained.
Desktop Refresh needed. Contained FootIK only; no Unreal/server/training work.
[Details and measurements](Labs/FootIKLab/README.md).

**Foot IK October25 - entry clearance / exit velocity:** measured saved Walk
phase49: late spatial fade caused7.14m/s upward kick near43; entry preparation
now spans toe-off to higher landing, with constrained smooth shoe clearance.
Peak40-48 upward speed0.492m/s, peak ankle height44.14 ->43.07cm. Exit arc's
artificial forward lead caused177-179.5 to stall while NN kept advancing.
Unpinned landings now preserve NN forward progress plus contact offsets, retaining
clearance. Velocity detector passes phases0/.25/.49/.75; root remains2m/s.
211 existing +18 velocity checks pass. Supersedes stairs F41 raw-NN assertion:
first higher landing is now anticipated; Flat remains exact across all50 slots.
No live NN/history reseed, per-frame solver, server/Unreal/Bodyflip changes.
Ghost translucency appended below existing More options; live redraw, persisted,
0solid/100invisible/default70. Browser43/178 checked, no console errors; restored
paused172/phase49/camera/ghost16/terrain10. Desktop Refresh required.
[Current behavior and evidence](Labs/FootIKLab/README.md).

**Bodyflip October25 - shared controls and jumps in Idle:** corrected the prior
Idle-only bypass. Idle is a stationary motion source for the SAME sequence planner
as Run/Walk. Jump markers, + Jump, trim/loop, all options and debug views visible;
standing/repeated jumps, load/push/fall, attacks and air flip/twist use shared paths.
Idle source loops with Phase offset; no markers means stationary idle. Fixed
zero-speed edge handling (original flat platform extends5m, no spontaneous fall).
20 idle checks pass including repeated/delayed pushes, phase, reverse seeks and
air rotation; scenes21, refresh14 and run-pacing24 pass. No new controls, UI moves,
NN request for idle, state overwrite, process restart, Unreal work or push.
Refresh required; visual QA unverified. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - Idle replaces Space:** removed Space sequence option;
legacy saves migrate to Idle. Reuses frozen neutral idle animation (301frames,
30Hz,10s) with original provenance; upright, stationary root and grounded shoes.
No flip/twist rotation. Existing platforms remain visible/editable; transport
samples idle clock, switching cancels old flight/pending run response. Jump tuning
and markers retained.11 idle,21 scenes,14 refresh checks pass; visual QA unavailable.
Refresh required. Small local animation export only; no Unreal, inference/server
process, state overwrite or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - fresh flat scene button:** New scene appended at the far
right of the header, after existing scene tools. Saves outgoing scene, creates
named independent setup with original flat platform only, default tuning/camera,
one default jump and paused frame0. Carries current platform migration version
so reload does not respawn inclines. Copy remains duplication. Scenes21 and
refresh14 checks pass; syntax checked. Refresh to load. No live state overwrite,
server restart, Unreal/training work or new push. [Details](Labs/BodyflipLab/README.md).

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

**Foot IK Lab October25 - full-body shadows:** replaced rejected foot-only
footprints with real character depth-map shadows on terrain/body. One1024Â² map
(about4MiB), four-metre COM window, one extra draw reusing the existing mesh upload;
cached for unchanged poses/camera-only redraws. Character casts, terrain receives.
32-sample GPU check: extra depth pass median0.088ms/p950.145ms, excluding main
scene shading; cache/error checks pass. Syntax and visual F25/F150 checked, no
browser warnings/errors. Restored F25/camera/settings; no motion/UI/tuning changes,
server restart, Unreal or training work. Desktop app needs Refresh.
[Details and measurements](Labs/FootIKLab/README.md).

**Foot IK Lab October25 - knee poles / retained toe-off / trailing rotation:**
The previous soft-reach fix addressed extension but missed knee-plane jitter.
Filter IK poles in pelvis space, transporting neighbouring planes to the current
leg axis before a small Gaussian average; fade with terrain influence, exact NN
flat/approach/exit unchanged. Default stair-course max pole-increment change
4.56 ->0.423deg at120Hz; reversal around80 about4.40 ->0.423deg.
Removed the premature35deg extra-roll cap: contact can now use70deg toe-down,
extra correction slew540deg/s. Material sole pivots and heel/toe transfers remain
fixed in world space, ankle follows the arc. Trailing foot stays pinned101-102;
101 pitch -57.4deg. Replaced fixed0.1s release with swing-position-driven rotation:
retain toe-down behind pelvis, blend into NN as foot advances or approaches its
next landing;107 remains -67.1deg. Reserve bounded toe-off room before rising
risers and delay colliding forward travel while the pointed shoe lifts.
Rising swing now coordinates forward/upward progress between actual contacts,
with a smooth clearance arc fitted to the shoe corners. Supersedes height-only
Hermite lift, which left the trailing foot rising vertically around108.106-110
now travels15.1cm forward /15.1cm up, previously2.3cm/13.0cm.84-92 remains a
continuous ascent at1.61-2.47cm per120Hz sample. Fixed a missed exit case: requiring
a retained landing pin skipped the168-198 swing and restored per-riser lifts.
Exit swings now plan to the NN endpoint too.171-176 rises1.58-2.01cm per120Hz
sample with >=2.39cm forward travel;169-181 lift-acceleration check covers178.
Ascending exit recovery now fades over12 samples and ends when the root has
left the ramp and both NN shoe footprints lie over the final level plane.
Walk is exact NN from181.5 (formerly205.5); Run from74.5. Flat preset/source banks
were already exact and remain unchanged. Toe pins retained through164-168;
no new UI or per-frame work.
212 checks pass: whole-course pole continuity,101 pin,107 trailing rotation,
material anchors,50 cached flat phase slots,8 gait/terrain presets and existing
strict motion bounds, continuous84-92 ascent/early clearance and diagonal106-120
travel.104 knee flexes faster with forward swing (max8.72deg/displayed frame,
limit10); acceleration bound1.5deg and global motion limits unchanged. Source NN gait,
full collider ghost, shadows, UI layout/options retained. Cached preparation
~170ms default Node check, no live per-frame IK/inference or Unreal/Bodyflip work.
Browser170/174/182 checked with no console errors, refreshed and restored to
paused178 with user's camera/settings. Desktop needs Refresh. Details in
[Labs/FootIKLab/README.md](Labs/FootIKLab/README.md).
Initial prototype distorted
the real NN gait: generic flat swing lift plus endpoint division raised the left
foot84.3cm at F41; copied straight-knee fallback pointed backwards. Rewrote the
terrain planner/solver. Flat approach/exit and Flat preset now return exact NN
poses; bounded terrain clearance, anatomical knee hinge, preserved shoe rotation,
rate-limited reach-only pelvis correction and early unplant. Walk bank/checkpoint
provenance verified (July5 8bae21c5b315,2m/s); no source/stride substitution.
Checks include all50 cached phase slots unchanged on flat, exact F22/F41,
per-frame flips/teleports, contacts/reach/clearance and source immutability.
Flat Walk max rotation step8.71deg equals source maximum; no IK loops.
Seconds/bracket tooltips replaced by frames. Desktop app shortcut/icon retained.
Visual F22/F41 NN overlay and F150 ascent/descent checked, no console errors;
standalone Edge app opened and its dedicated profile/port verified.
Contained FootIKLab only; no Unreal/training or Bodyflip edits. Earlier84-check
validation was insufficient and is superseded. [Details](Labs/FootIKLab/README.md).

**Foot IK Lab October25 - separate terrain prototype:** created
`Labs/FootIKLab` and desktop **Foot IK Lab** shortcut, own port8878/state/profile.
Copied NN Walk/Run banks and renderer/leg helpers; no live Bodyflip dependencies.
Root follows a smooth stair ramp; foot IK queries discrete treads, estimates
stance from original gait height/speed, pins finite contacts, anticipates swing
clearance and adjusts pelvis against both legs. Cached banks omit NN pin outputs;
corrections stay outside recurrent NN state. Stripped UI retains single timeline,
brackets, speed/frame stepping, COM camera and Refresh state. Stairs up/down,
uneven/flat presets; compact More options under views.84 checks pass; maximum
default run-down target error1.01cm, sole clearance passes. Browser visual/input/
Refresh QA passed, no console errors. Server running8878; shortcut installed.
No Unreal/training operations or existing lab edits by this task; no commit/push.
[Controls, limits and verification](Labs/FootIKLab/README.md).

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


**Bodyflip camera October25:** horizontal left-drag orbit now uses yaw -= dx;
inverted vertical remains pitch -= dy. Horizontal previously retained its
original sign. Only the lab orbit mapping changed; saved camera/pan/target drag
untouched. Syntax checked.

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


**Standing UI placement rule (October25):** preserve existing control positions
and order. New options go at the bottom; in horizontal rows they go on the right.
Do not shuffle existing controls to group new features. Bodyflip Cone angle was
moved to the end of More options, and Cone debug after Bones; source order checked.
User then requested moving the entire More options panel under the view buttons
at viewport top right. Done as a collapsed dropdown, with internal order retained,
bounded scrolling and Space-mode hiding; source structure/syntax checked.

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

## October 25 - Bodyflip sole cone / immediate proximity launch / heel roll

Failed-fall pelvis fixed: current Phase30%/Cone60 aborts.904167s; root never
launches, but old fall-animation pelvis caused7.24cm upward rebound at1.10-1.15s.
Abort path now captures the displayed pelvis at the ledge and keeps it on capped
gravity while limbs blend. No extra gates or plant/timing changes. 36 focused
Run/Walk/Body0,.2,.8 checks pass for no bounce, continuity and active limbs.
Saved state untouched; receipts/details in Bodyflip README.

Ideal contact now clips to the cone from the lowest sole point and valid ground.
More options Cone defaults30deg half-angle (0-85); viewport Cone debug checkbox.
No cone/platform intersection aborts. Root-local ideal, foot selection, locomotion
and reach retained; miss history now measures sole-to-contact distance. Gate5cm
tests sole proximity, including at support entry, and starts PUSH immediately.
Nearby contact is captured by IK within gate/cone tolerance: no wait for ideal
ankle or Plant rotation. Gate0 waits for exact contact. Heel roll uses actual
captured pitch, preserving Roll speed, Toe-off and reach-limited release.
Run Phase54% now jumps.900s instead of.950s with no forward replant; Phase67%
approaches until.925s. 88 cone +33 blend numerical checks pass. Browser visual
check remains pending: CUA initialization twice failed with missing runtime path;
UI wiring inspected, fixture verify-cone.html ready. State/camera unchanged.
No NN/Unreal/server restart. [Current details](Labs/BodyflipLab/README.md).


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


## October 24 â€” Bodyflip root-speed alpha / global frame arrows

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

## October 24 â€” Bodyflip run levitation fixed

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

## October 24 â€” Bodyflip root-local support / no freeze / missed-edge abort

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
during approach. Foot10 miss abort1.0083s as gap grows8.28â†’8.73cm.
144 numerical and27 browser checks pass. Contained lab only; no NN/Unreal processes.
[Current lab behavior](Labs/BodyflipLab/README.md).

## October24 â€” accepted oil liquid / glass base line correction

User approved the liquid shown in Transmission/front-plain.png; preserve it.
M_OilBottleLiquid now saves transmission(.72,.32,.018), roughness.035, specular.45,
opacity0, refraction1.003 and cheap refracted-cylinder chord absorption. No new
CPU work, collision or scene capture; this is approximate volume optics. The
native constructor default binding remains current in normal DLLs. No new build.
The1.035 trial narrowed the oil visually and was rejected; mesh thickness never
changed. Glass-only A/B isolated broken black base strokes to screen refraction.
M_OilBottleGlass RefractionStrength .01â†’.001 removes the doubled rim; all other
settings retained. Saved glass only for this final fix; protected liquid/cork and
all bottle/debris mesh SHA256 hashes unchanged. No map/scalability/physics edits.
Current1200Â² front/oblique previews and receipt: Saved/Diagnostics/Oil/Bottle/
GlassBase/glass-base-fixed.png, glass-base-oblique.png, receipt.json.
Previous golden-oil-1080p.mp4 remains8-check impact/debris evidence, not current
appearance. Accepted airborne splash/puddle unchanged. See Docs/OilStains.md.
Owned editor18340 hit Unreal !IsRooted while deleting old liquid expressions,
before saving. Recovered in owned20236; recipe now reconnects rooted expressions
safely and version2 preserves the approved liquid on subsequent installs. Exact
approved shader saved, then glass-only fix verified. Owned20236 closed cleanly;
no test/encoder remains and no user editor was involved.
Prior cleanup rejection remains in effect for old diagnostic files; no retry.

## October 24 â€” Bodyflip pelvis / cm/s / inverted vertical orbit

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

## October24 â€” bottle edge/tint/cork refinement and native1080p

User's enlarged screenshots exposed remaining aliasing/dark rim and uneven tint.
Material A/B at1920Â² isolated refraction patches from the960Ã—720 preview upscale.
Glass now neutral transmission, specular.25, refraction strength.01 (IOR1.0052),
SSR off on that material; EdgeCoverage.2 softens overlapping grazing interfaces.
Oil uses pow(Tint,NoV), cancelling UE's sheet1/NoV absorption instead of the prior
NoVÂ² term that faded yellow out at the sides. Tint(.99,.88,.38), specular.15;
background/light reflections still vary. Cork is brown(.10,.048,.018), roughness.82,
with derivative-filtered pores. Recipe: Tools/Oil/BottleMaterials.py.
At that stage only three bottle materials saved; the later default-material
correction above supersedes its no-native-build state and pale preview.
Accepted splash/puddle untouched. Capture AA6 is process-local, not saved user
scalability. Native1920Ã—1080/CRF16 video (no upscale), plus1920Â² hero:
Saved/Diagnostics/Oil/Bottle/Studio/studio-bottle-1080p.mp4. All7 real-impact,
20-fragment, fade/cleanup/spill checks pass, impact tick199. Current details and
shader approximation limits: Docs/OilStains.md. One owned BelowNormal editor,
one single-thread encoder; close/cleanup at end of this turn.

## October 24 â€” Bodyflip earlier jump option / alpha ledge workaround reverted

User correctly noted alpha was functioning; reverted the automatic platform-edge
expansion introduced last turn. Edge is again speed Ã— Run âˆ’ .12 m, independent
of alpha. Existing alpha formula, uncapped values and lead readout remain.
Added **Early s** beside Run, default **.10 s**; 0 restores old timing. Support
preparation uses the cached gait at Run âˆ’ Early, then still waits for the foot
gate. Default cached takeoff .904 s instead of 1.004 s, same fixed ledge.
Early leaves at least one authored frame of running; unreachable support still
waits. Click-away/Enter commits and edit-in-place playback fixes are retained.
120 numerical and 20 browser editing checks pass. Direct keyboard edits at
0.95 s show RUN with Early 0 and PUSH with Early .10, preserving playback time.
Only contained lab/docs; no NN or Unreal processes.
[Current behavior](Labs/BodyflipLab/README.md).

## October 24 â€” Bodyflip commit edits / retain playback time / alpha feedback

Number fields now blur/commit on outside pointer-down, including canvas clicks
whose default focus change is prevented. Enter also commits/unfocuses. Sequence
parameter edits rebuild at the current time; paused remains paused and playing
support edits resume there. Reset remains explicit. Cached support edits use no NN.
Measured alpha 1â†’20: previous final contact shifted only 8 mm and hit the old
ledge; at Foot 800 m/s the requested lead itself is only ~1 cm. The finite ledge
now allows a 12 cm margin after predicted contacts, capped by leg forward reach.
Lead readout reports actual cm and marks edge limiting; formula is unchanged.
Verified 104 support checks plus 17 editing checks (`editing-verification.json`),
and real canvas-click / Enter commits at 1.05 s without a time reset. Alpha 1â†’20
moves the planted foot forward 0.912 cm at that same time. Original alpha 20.1
and other saved tuning restored. No NN/Unreal processes launched.
Details: [Bodyflip README](Labs/BodyflipLab/README.md). Contained lab only.

## October 24 â€” Bodyflip support alpha uncapped

Removed the upper bound of 10 from **Lead alpha**, both UI and settings sanitizer.
Any finite nonnegative value, including values above 1 and 10, is accepted/saved.
Default remains 1. At Foot 800 m/s, alpha 10 yields only about 5 mm of forward
lead for the cached gait. Actual contact remains clamped to the finite platform;
its edge is unchanged. Only contained lab controls/docs changed; refresh the lab.

## October 24 â€” Bodyflip playback speed

Shortened the timeline on the right for a compact **Speed 0.1Ã—â€“2.0Ã—** slider,
default 1.0Ã— and saved. Changes playback speed live without restarting; authored
timeline/trim/Step and fixed simulation step sizes remain unchanged. Bounded
frame work is retained. Only Bodyflip lab UI/clock and current docs changed.
Refresh the desktop lab. [Details](Labs/BodyflipLab/README.md).

## October 24 â€” Bodyflip procedural support plant

Replaced authored support preparation / jump-pose distance selection with a
procedural ground contact in **Kinematic**. Pelvis projects to the finite platform;
ideal L/R contacts sit half a hip width along its tangent. Auto selects the nearer
corresponding foot; L/R overrides remain. Prediction is COM tangent velocity Ã—
alpha Ã— lateral foot distance **divided by foot speed**, as clarified by user.
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

## October 24 â€” Bodyflip playback stays inside brackets

Fixed replay ignoring the visible range when Loop was off. In/Out now always
bound Run + jump playback: Loop repeats; without Loop playback pauses at Out.
Moving either bracket enables Loop automatically; Step also respects Out.
Kinematic remains active. `timeline-verification.json` passes **17 checks**,
including actual animation-frame playback, repeat wrapping, Loop-off stopping,
Step bounds and live drag previews. Only the contained lab and this handoff
changed; no NN or Unreal processes started. Refresh the desktop lab to load it.

## October 24 â€” Bodyflip inline trim brackets / live scrubbing

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

## October 24 â€” Bodyflip playback In/Out loop

Run + jump playback bar now has **In / Out** sliders plus seconds fields and a
separate **Loop** checkbox. Edit boundaries, enable Loop, Play/Space to repeat.
Edits pause/preview that endpoint; bounds snap to 60 Hz frames and cannot cross.
Defaults 0â€“3 s, Loop off; values persist. Numeric fields extend range up to 600 s.
Kinematic remains selected. Seeking/wrapping directly samples the prepared sequence
and flip/twist phase without NN work or simulation replay; transient attack/hit
state clears per pass. Sim uses the existing yielding reconstruction if selected.
Attack Loop remains independent. [Bodyflip README](Labs/BodyflipLab/README.md).
`loop-verification.json`: 11 checks passed, including three wraps, exact restart,
boundary guards, pause and Loop-off behavior. Only lab files changed; no heavy
processes started. Refresh the existing desktop app.

## October24 â€” oil bottle studio lighting / smooth edges

Supersedes the earlier ghost-glass preview. Retains the exact Fab bottle; fixed
reversed UE render winding in the bottle +20 fragments (cork top was incorrectly
culled), without changing their collision shapes. PrepareBottle.py now exports
correct UE winding after manifold processing. New BottleMaterials.py recipe:
Thin Translucent glass with restrained screen-space refraction, warm dither-fading
cork, separate bulk-liquid material. Accepted airborne splash/puddle untouched.
Liquid edge uses48 sides/11 rounded rings and smooth side normals, correct render
winding; no additional physics or idle polling. Fixed mesh capacity3168triangles.
Normal incremental build passed:4 actions, one module compilation,56.22seconds.
DLLs current. Only the owned offscreen editor was closed/reopened for that build.

StudioSetup.py saves contained M_OilTest lighting/HDR/materials. Dedicated
background has no collision geometry and actor collision disabled; an earlier
background interfered with the test drop and was corrected. Saved map still has
both original bottle demonstrations. Explicit capture AA removes jagged edges;
global user scalability/config unchanged. Actual Jolt release breaks at tick199
into20 fragments;7 checks pass including fade/cleanup and spill. Current video:
Saved/Diagnostics/Oil/Bottle/Studio/studio-bottle-preview.mp4 (normal sequence +
labelled0.4x impact replay), hero.png and compact receipts. Reproduce via
StudioReview.py / ComposeStudioVideo.py. Historical ClearBottleReview.py disabled
so it cannot overwrite the new material. Details: Docs/OilStains.md.
Final capture measured0.397ms median /0.569ms p95 CPU liquid updates for one moving
bottle, no idle tick; not a many-bottle/GPU benchmark. Final video fully decodes.
Owned preview editor/encoder closed;15.5MB of discarded captures/raw video removed.

## October 24 â€” Bodyflip kinematic takeoff trimmed / support-foot Auto

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

## October 24 â€” Bodyflip tracking correction / kinematic comparison / hitching

User found button-focus Space conflicts, hitching and poor simulated gait. Changes
remain in `Labs/BodyflipLab`; [current details](Labs/BodyflipLab/README.md).
**Motion â†’ Sim / Kinematic** compares identical decoded NN targets and restarts the
sequence. Kinematic has no solve/contact response; Sim has 25 dynamic bodies.
Space now captures keydown/keyup and suppresses repeats, including with a
button/slider/checkbox/selector focused. Text editing keeps normal keys.

Diagnosis confirmed: initial Run + jump used spring joint motors, NOT the native
velocity tracking functions. Corrected to `ProphecyJoltVelocityServo.cpp`'s angular
error/substep command and parent-first predicted endpoints, with world position
tracking on pelvis only, gravity compensation and origin-to-COM velocity correction.
Joint motors are off in this mode; real constraints/contact remain. Original Space
motors remain. One-second frozen NN comparison: upper-spine mean angular error
28.10Â°â†’1.60Â°, left-hand 54.20Â°â†’6.17Â°. Hinge/contact errors remain; lab rig/tuning is
not native-rig parity. Source NN is unchanged. Kinematic exposes its exact poses.

Optimization: cached sword geometry/normals, unique vertex transforms, reused GPU
buffers, cached local pose sampling, scalar root-height derivatives, 10 Hz HUD,
bounded catch-up. Decoded NN cache makes reset/blend/foot/cap edits reuse a segment;
timeline reconstructs on release in short yielding batches. Measured same local
1000Ã—700 fixture: mean frame work 22.40â†’9.38 ms; p95 25.30â†’12.80 ms. Cached Reset
3.5 ms. These include test diagnostics/render submission, not GPU-present FPS.

Validation: **27/27** focused comparison checks, real focused-button Space toggle,
tracking regression, and 12 simulated seconds. Max anchor 4.111 mm, pelvis position
1.172 cm, pelvis angle 19.05Â°; fall cap respected. Receipts in lab:
`comparison-verification.json`, `tracking-before/after.json`,
`performance-before/after.json`, updated `flight-verification.json`.
Prior 16/39 UI receipts below are historical; sequence fixture adapted to async seek.
Only the small existing server remains resident; no NN/Unreal/build/training process
started for these fixes. Existing desktop icon; refresh the lab to load changes.

## October 24 â€” Bodyflip Lab simulated run â†’ jump â†’ void complete

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
**12.6Â°**; terminal COM speed respects the 12 m/s test cap to float precision.
Receipts: `flight-verification.json`, `sequence-browser-verification.json`,
`nn-verification.json`, `jump-export-verification.json` in the lab. No NN worker
is intentionally kept running after verification. Existing desktop shortcut remains.

## October 24 - Fab Oil Bottle, impact breaking and prepared debris complete

`/Game/_mygame/OilBottle/BP_OilBottle` replaces both placeholders in the isolated
`/Game/_mygame/Tests/Oil/M_OilTest`. Feature assets live together under OilBottle
(Meshes, Materials, Debris, VFX); old paths have small redirectors. Fab Milk Bottle
by mokbulsd downloaded after explicit EULA approval;88KB source/attribution in
Tools/Oil/Source.27.735cm total height, seated cork,19 closed Voronoi glass pieces
plus cork, baked offline. Visible geometry unchanged by separate128/64vertex
collision LODs (max inset1.313mm bottle/.857mm pieces; required by Jolt hull limit).

Class defaults: Break On Hit=true, Break Impact Speed=250cm/s incoming relative
normal contact speed, Spawn Fragments=true, radial Fragment Velocity120cm/s,
Fragment Lifetime4 / Fade Duration1 authored seconds. Current effective material
slots/MID values copied at break; supplied shaders support FragmentOpacity.
No intact-bottle actor tick. New cosmetic OilInside component updates only during
motion/settling, then retires; shares the airborne oil material. Fill.65, slosh1,
damping.4; volume-preserving inscribed cavity, ordinary-tilt shortcut, no fluid
simulation/collision/queries. See Docs/OilStains.md. One debris fade clock,
actual Jolt bodies, complete cleanup.
Liquid final normal build/BP save passed;9 controlled-motion checks pass incl
inversion, volume, idle retirement/wake and empty opt-out.8second two-view video:
Saved/Diagnostics/Oil/Bottle/Liquid/oil-inside-preview.mp4. CPU update/enqueue
median136.6us/p95 194.7us in busy editor (not GPU/many-bottle benchmark).
Owned editor/encoders exited; temporary captures cleaned. User Oct24 reminder:
keep laptop work lightweight alongside their other sessions; one isolated editor
at a time, below-normal priority, bounded single-thread encoders, close after checks.
New placements Launch On Play=false; two demo bottles retain true. Manual Break
Bottle remains. No bomb/fuse/VDB or gameplay-map changes.

Oil rays now optionally ignore tagged OilBottleFragment actors before intersection,
preventing oil masks on tiny temporary shards; physical contacts/ordinary rays
unchanged. Controlled comparison reduced44 coating groups to4 in the four-spill
test. Final two-bottle video has3 groups/109 patches, then zero at tick660.
Normal DLL build succeeded.10 gameplay checks pass, including soft/hard impacts,
fragment opt-out, live MID override inheritance, fade/cleanup. Existing7 query
tests and new filtered-query assertions pass. Final actual UE video passes6
checks; same push moves wet cube216.915cm vs dry15.134cm. These are controlled
scene results, not a large-scale performance benchmark. Preview:
Saved/Diagnostics/Oil/Bottle/oil-bottle-preview.mp4 (24s,1280x720,30fps).
Receipts: test.json, defaults.json, bake.json, FilteredQuery/index.json,
Video/recording.json. See Docs/OilStains.md and Tools/Oil/{PrepareBottle,
InstallBottle,TestBottle,ComposeBottleVideo}. All owned test editors closed;
user/UI-lab processes were untouched. No push requested. Disposable capture
frames/intermediate videos/geometry and the owned null-RHI test crash are cleaned;
small regeneration source, receipts and final preview retained.

**October24 Mixamo throws â€” corrected animation-only exports for Cascadeur:**
User reported distorted mesh with initial mesh-inclusive exports. Replacement
`UEFN_Throwing_AnimationOnly.fbx` and `UEFN_Throw_Object_AnimationOnly.fbx` are in
`C:/Users/singerie/Documents/UEFN_Throws_Cascadeur_20261024`; old files preserved
in audit/SupersededMeshExports.88-bone rig/rest transforms exactly match user's
working Sitting_Idle_Anim1.FBX; no mesh/bind-pose objects. All315 joint frames
exactly preserve the retarget,168/147samples at30fps. No trim/speed changes.
Single lightweight background Unreal export; no assets saved, owned process exited.
User explicitly prohibits desktop control and requests lightweight processes.
Correction was checked offline, NOT imported in Cascadeur; user import pending.
Saved animations remain `/Game/_mygame/animations/MixamoThrows20261024`.
Details and reproduction: [Mixamo throws](Docs/MixamoThrowsCascadeur.md).

**October24 Bodyflip Lab â€” isolated and ready:** new `Labs/BodyflipLab`, desktop
**Bodyflip Lab** shortcut/icon, loopback8876 and its own browser profile. Reuses
copied D/S renderer/math and all320 existing full-body attack clips across16
families. Original D/S sources verified unchanged.12 horizontal flip directions
at30deg intervals; separate pelvis-local twist angle/speed; right-drag target,
Shift-right depth, optional bounded aim, play/step/scrub, saved settings/snapshots.
Actual local Jolt WASM:25bodies/24joints, hinge knees/elbows, remaining limited
swing/twist joints; constant-speed kinematic pelvis, dynamic limbs, zero gravity,
240Hz physics/60Hz authored ticks. Dedicated lab profile, not current PHAT/DLL
parity; target is a non-blocking marker and sword hits use geometric checks.
All320source hashes,12axes and16attack families pass; max anchor error1.536mm,
hinge excess0.053deg, neutral tracking error4.364deg at120flip/60twist.39/39browser
checks pass, including synthetic right-drag/depth events, full-body playback,
scrub and cancel. App opened paused/neutral for user review. No Unreal build,
remote call, asset/BP edit, training change or modification of existing labs.
Read [Bodyflip Lab](Labs/BodyflipLab/README.md) before changes; receipts and preview
are contained there. Keep future iterations contained until an explicit port request.

## October 23 â€” Why the Jolt get-up viewer sometimes looks faster

Read-only investigation; accepted weights, physics profile and gameplay untouched.
Across99paired successful fresh starts, native mean25.49ticks (0.850s), Jolt26.90
(0.897s); medians22vs23. Jolt faster16, equal18, slower65. Common-time-window mean
per-case angular RMS ratio0.944 and linear RMS ratio0.967. No global speedup;
viewer advances both recordings on one30Hz timeline, simulations240Hz/30Hz.

Default viewer case0 is a real outlier: Jolt32ticks vs native62. Native head first
passes its height threshold at43, then fails feet-height gate through61; Jolt
passes all gates at32. Head-origin peak vertical speed3.174vs2.489m/s, so its
push is also sharper in this case. Case94 native72/Jolt24 follows different
recovery attempts; it is not a rescaled copy of the same movement.

Frozen-policy mechanism probes on12stratified cases used the existing isolated
candidate executable. Baseline state arrays matched saved Unreal exactly.
No drag:12/12, mean23.83ticks vs baseline23.83; case0 remains32. Gyro enabled:
12/12,25.17; case0 remains32. Limit16Hz:12/12,24.08; case0=34. Limit8Hz:
11/12,46.92 (includes failure tick), case0=71. Half motor gain:12/12,41.08;
case0=46. Alternative motor clamp ordering:12/12,25.50; case0=32.
These are diagnostics, not adopted settings or a new tuned profile.

Loaded native model confirms no passive DOF damping, no fluid viscosity/density,
no armature and no extra drag hook; velocity-motor gains/caps match Jolt.
Jolt adds small compound drag and zero native per-body damping. Native ball limits
use solref[0.02,1], while Jolt uses32Hz critical spring limits; contact/integration
also differ. Limit response demonstrably influences the sharper recovery; this
does not isolate all contact/motor contributions or establish trajectory parity.
Success transfer remains100/100, but that never established equal trajectories.
No reason from these measurements to globally slow Jolt or add arbitrary damping.

Evidence: Saved/MimicKitTransfer/getup-transfer-20261023/speed-investigation/
(trajectory-stats.json,case-details.json,ablations.json,native-model.json).
Reproducer: Labs/MimicKitTransfer/investigate_getup_speed.py.
References: MuJoCo modeling solver parameters; Jolt5.6 MotorSettings and architecture
damping documentation. Training stays stopped, no cloud GPU allocation.

## October 23 â€” Broader frozen-checkpoint transfer test: Unreal/Jolt 100/100

Viewer follow-up: fixed a first-animation-frame negative time delta that could
index frame -1 and kill playback. Clock starts on the first animation callback
and resets on resume; Play at the endpoint restarts. Both viewers and the shared
template updated; fresh-100 generator now reads/writes HTML explicitly as UTF-8,
also correcting its stale18-test header. Browser Play/Pause verified after reload.

User requested 100 fresh get-ups before accepting transfer. Fixed-seed2026102301
test used the actual saved training reset code:50front/50back, each with25ordinary
perturbed and25perturbed+ starts; uniform whole-pose limp blending, original
floor correction, separate locomotion root/joint velocity frames and0â€“700deg/s
spin.94distinct limp poses; no filtering, retries or tuning against the results.
The prior32Hz spherical-limit profile and accepted pelvismax161960_final weights
were frozen before sampling. Deterministic policy, flat floor,240Hz/30Hz unchanged.

Results: native MuJoCo99/100; actual installed Jolt inside Unreal100/100.
All99native successes transfer, and native failure case27 also succeeds in Jolt.
All four25-case cohorts pass in Unreal. Five owned headless Unreal automation
processes completed successfully. Initial observations were checked against the
production environment. Full initial states, metadata and trajectories retained.

Evidence: Saved/MimicKitTransfer/getup-transfer-20261023/fresh-100/summary.json.
Viewer: http://127.0.0.1:8843/Saved/MimicKitTransfer/getup-transfer-20261023/fresh-100/.
Harness: Labs/MimicKitTransfer/check_getup_100.py. No training or cloud allocation.
This supports using the accepted weights without fine-tuning for this reset
distribution. Same installed Jolt library as gameplay, but the new spherical
constraints remain opt-in on the isolated test rig; gameplay defaults are NOT
updated. No RunLR changes. Uneven-floor/live gameplay integration not covered.

## October 23 â€” Native pelvismax works in opt-in Jolt recovery tests; training STOPPED

The accepted native pelvismax run13-11-28 checkpoint161960_final stays unchanged.
Local ZIP SHA256 reverified:0dc58150f87f1cb25816235f9e565638e9972d262b9203c5da0d14c0ea736a2b.
User requested adapting Jolt to these weights to avoid long retraining. No training,
GPU allocation, checkpoint deletion, PHAT edit or gameplay-default change this turn.
Recovery poduks8hn8yeqnpxf remains stopped by the prior explicit user request;
stop receipt Saved/MimicKitEquipment/user-stop-transfer-doubt-20261023.json.
Earlier RUNNING entries below are historical, not current authorization/status.

Actual Unreal/Jolt frozen-policy tests now pass18/18 recorded perturbed starts,
versus1/18 with the prior angular limits; both recorded normal clips also complete.
The fix is an opt-in Jolt spherical angular-limit constraint matching the native
training bound (PHAT-centered total angle, radius=max of the three limits), with
32Hz critically damped softness. Motors/caps,240Hz physics/30Hz policy and success
criteria are unchanged. Native Jolt library unchanged; only isolated recovery rig
construction adds this constraint. This is not the rejected custom MJWarp solver.

Evidence/profile: Saved/MimicKitTransfer/getup-transfer-20261023/jolt-native-profile/.
Comparison: http://127.0.0.1:8843/Saved/MimicKitTransfer/getup-transfer-20261023/comparison/.
Unreal and standalone full state traces match exactly for all18. Four starts used
for tuning, fourteen additional starts; deterministic flat-floor evaluation only.
Normal front test starts0.933s into its clip (18ticks remaining), back starts0s
(42ticks). This does not establish arbitrary-state or full gameplay integration.
Details, activation and limitations: Docs/MimicKitTransfer.md. Training stays stopped.

**October23 oil bottles â€” Niagara droplets and flared sheet installed:**
Supersedes the native instanced bead renderer below. Test bottle and both map
instances now reference `/Game/_mygame/Tests/Oil/NS_OilDroplets`:360 small
velocity-facing, velocity-stretched sphere particles per burst. Reduced sphere
mesh12.5% triangle target; separate droplet material; no Niagara collision,
readback, shadows or additional native traces. Existing56 native samples retain
all landing/stain authority. The procedural sheet now has a low center and curved,
raised five-lobed rim; same193vertices/320triangles and actual contact handover.
Niagara advances once per authored60Hz tick and expires; pending first-use asset
preparation catches up to the current age. Normal incremental4action81.72s build
passed; normal DLLs current. No user editor/Play interrupted, no push.

Video `Saved/Diagnostics/Oil/NiagaraFlower/Angles/oil-splash-three-angles.mp4`:
18s,1280x720,60fps,1,634,918bytes; overhead,22cm low view, angled; each normal
speed then labelled1/3speed replay. Droplets and raised rim visually inspected.
6/6 checks pass. Native slider samples, landing ticks48/54/60/66/72, last sheet60,
coverage/lifetime counters exactly match prior accepted recording (max delta0).
Wet/dry travel224.782719/15.133747cm. Full video decode passed. This is authored
playback, not a new aggregate GPU/FPS benchmark. Small receipts in NiagaraFlower;
raw captures/intermediate streams cleaned. Owned test processes exited.
Builder `Tools/Oil/CreateNiagaraSplash.py` uses the installed converter's editor
authoring API only; plugin not enabled in project/runtime. Rebuilding its generated
NS requires explicit `-ProphecyOilRebuild`; preserve future user edits. Wiring
helper copies the oil struct before assignment and explicitly dirties/saves the
two isolated actors: mutating a borrowed struct had silently failed to save its
new reference. See [OilStains](Docs/OilStains.md).

**October23 oil bottles â€” previous sheet landing handover and native beads:**
Airborne-only follow-up: visible beads restored using existing instance slots,
with bounded cosmetic height/size variation and velocity stretch. No landing,
coverage or friction changes. Straight trial strands were rejected and removed;
normal incremental4action47.08s build passed. Overhead, near-floor22cm and angled
video ready: `Saved/Diagnostics/Oil/Airborne/Angles/oil-splash-three-angles.mp4`,
18s/60fps/1280x720/1,206,983bytes. Each view includes normal speed then a labelled
1/3speed replay.6/6 capture checks pass; landing ticks, coverage/lifetime counters
and all sampled native cube positions/velocities EXACTLY match the accepted
Landing recording (maximum delta0). Same56 instance slots and query budget;
default38 sheet beads +7 free drops visible. No new Niagara or physics work.
Full video decode and camera-frame review passed. Raw captures cleaned, compact
receipts retained in Airborne. Owned processes exited; user UI labs untouched.
User rejected the nested sheet/puddle silhouette in the first landing video.
The old center-to-rim110/140/170/200 launch speeds staggered sheet contact too
far apart. Sheet points now share an180cm/s arc with a small ripple. Their full
area transfers to the coating on contact and stops drawing the airborne layer;
free fringe droplets alone retain six-tick splat expansion. Contact frames on
mesh and Landscape inspected; revised video is ready for user review.
The sheet now survives until actual surface contact. Default56 samples comprise
49 traced sheet points (center +3 rings) and7 free fringe drops. Each landed point
transfers into full-size wet coverage; denser interior coverage makes a mostly
connected puddle. Display interpolation uses at most193vertices/320triangles,
one sheet draw and no extra collision rays. Landed spans interpolate linearly to
avoid curve overshoot. Counts below13 retain separate drops only. This remains
a bounded ballistic approximation, not fluid simulation.
Shared body-local union masks retain the previous overlap/tint fix: one sheen +
optional3.5% tint per compatible connected group, shared visual/friction fade,
512x5128-bit masks, no settled raster/upload. Materials sample OilCoverage UV.yx;
run UnionAppearance.py last after historical appearance-recreation tools.
Final normal incremental build4actions51.46s passed; normal DLLs current. Final
cold1800tick regression12/12 passes, including moving receivers, limbs, cleanup
and64 Landscape comparisons. Actual Unreal660tick recording passes6/6 checks;
sheet persists through landing and retires, all effects disappear. Two identical
cubes receive one150cm/s push: oil224.78cm versus dry15.13cm after2.5seconds.
No continuous force/teleport or artificial puddle under the character.109 patches
form3groups/6decal components;28 mask rebuilds remain unchanged120â†’360ticks.
These counts are not a whole-frame FPS benchmark; old physics-only timing remains
in [Oil stains](Docs/OilStains.md), alongside controls, limits and replay steps.
Physics review `Saved/Diagnostics/Oil/Landing/Video/oil-sheet-landing-and-physics.mp4`:
22s,1280x720,30fps,1,826,770bytes; full decode and sampled-frame review passed.
Final video and compact receipts retained; own raw captures cleaned. Owned test
processes exited. WeaponWheelLab4296 and PauseMenuLab10504 left untouched. No
asset/BP/map edits, user editor restart or push this revision. Cross-body/material/
strongly curved surface charts remain separate; large areas reduce mask detail.

**October23 recovery transfer/speed investigation — historical Unreal findings:**
Four difficult native-MJ successes failed in headless Unreal/Jolt feedback tests;
one custom perturbed get-up succeeded at18ticks in custom and19 in Unreal.
Other custom successes did not all transfer. Old RunLR acceptance used a separate
patched DLL, never installed in gameplay; its map was a recorded preview.
These are historical results, superseded by the later native transfer checks above.
[Full evidence and training continuation](TrainingJournal.md#training-entry-0408).

**October27 UI - twenty larger ruby-and-gold refinements ready:** User supplied
the selected ruby/gold menu and requested greater sophistication, height and
width. All 20 retain its enclosed rectangle, translucent interior, bright text,
vertical five-action order and selected Continue. Current gallery:
`Labs/MainMenuConcepts/2026-10-27-ruby-refinements/index.html`.
01-05 frame, 06-10 typography, 11-15 material, 16-20 detail. Exact new attachment
copied/hash verified. All 20 made with built-in imagegen and individually
reviewed: 20 unique decoded 1672 x 941 PNGs, 33,481,486 bytes (31.93 MiB).
Each panel visibly taller/wider; prompt dimensions are targets, not runtime
measurements. Prompts/source paths/validation saved; links/script syntax checked.
Arrows browse, B compares reference, D enables scrolling 2x details; selected
concept gets a #concept-NN URL. No live browser control. Await selection;
native implementation deferred. Scene preservation is visual, not pixel-identical.
Previous enclosed, broad UI, lighting and ground galleries preserved.
No game title or Unreal/preset/build/push changes.
[UI topic](Docs/WeaponWheelUI.md).

**October23 UI â€” approved optical font option loaded in pause lab:**
Latest October24: user approved and saved pause UI; requested UI-only push.
Include both isolated UI labs, runtime artwork/fonts, saved presets, font study
and pause concepts. Unselected opacity saved0.8032181263, whiteness0, right
extension200. User cancelled disaster-recovery audit; do not conduct it here.
Chronological tuning order remains mandatory: append new controls at bottom.
Final build12.31s;351/351 input checks passed. No main-game integration.
User approved the font-only study. **R â†’ Menu hairline strength** now selects
Bodoni Moda's authored optical size24â†’6 (19 steps, weight400); starts at B Medium
(size10). Removed the rejected translucent outline. Only five menu labels
change; PAUSED/footer/decorations untouched. Save persists
`menu_hairline_strength`. All13 previous user settings preserved.
Four-action incremental build21.67s;21/21 input checks passed. Native comparison
verified6304/7184 changed menu pixels and zero change elsewhere. Review25084
left open; only owned pause lab restarted, wheel4296 and main project preserved.
See Docs/WeaponWheelUI.md, pause README and VerifyOptical.py. No gameplay hookup.

User chose Fine Underline (variation02). Independent native UE5.7 project
`Labs/PauseMenuLab` now implements its visual composition, mouse/keyboard
selection, pause/resume preview and persistent tuning. R tunes, P hides hints,
F5 reloads, F12 snapshots.4-action build passed16.62s;21/21 handler checks and
final1672Ã—941 capture verified. Review instance11072 left open; wheel4296
preserved. Separate typography/gradient/blur/underline/star/glow; no gameplay
hookup or other menu pages yet. About43MiB including binaries; no shared PCH.
Read [Pause lab README](Labs/PauseMenuLab/README.md). Stop for user rating.

20 distinct pause concepts saved in `Labs/PauseMenuConcepts/2026-10-23/`;
`index.html` gallery, `manifest.json` exact prompts/provenance. Built-in imagegen,
English, forest backdrop, translucent celestial styling. Requested Blueprint
push checked: saved Blueprints already match remote
16d490e0; fetch/push returned up to date. No unrelated staging. Wheel remains isolated:
UE5.7 `Labs/WeaponWheelLab`; open with its `Open.ps1`. Eight varied orbit profiles
replace uniform dashed rings; stars/pearls sit on their carrying curves. New
local crescent/star glow, smooth Gaussian name backing and whole-wheel size
slider. Native live color picker controls the selection and halo (R â†’ Settings).
New independent Center/Circle line/Connecting line brightness controls (0â€“1)
replace the shared Ornament brightness slider. Center1; circles/connectors inherit
the previous saved brightness when new keys are absent; later user tuning wins.
Independent Center font size(12â€“36,default22) and Center decoration size(0â€“1.5,
default1) now available. Font changes do not move/scale surrounding decorations;
decoration size scales stars/diamonds/lateral lines and their positions together.
Latest saved preset preserved; small pre-font backup retained. Save settings
persists all controls. Darkness controls remain.
All new UI, labels, docs and conversation must remain **English**.
Prior45/45 input checks at three sizes; four rendered layer comparisons and color
callback comparison passed; native picker opened/rendered. Native1024Ã—949
capture retained. Size controls4-action build passed14.14s; own review window4296
left open. No main game/editor/assets/wiring changes. Shared PCH remains disabled;
lab~48MiB including outputs. Production GPU cost not measured. See
[WeaponWheelUI](Docs/WeaponWheelUI.md). Stop for the next visual rating before
gameplay hookup or further scope.

**October22 curated checkpoint prepared:** user requested pushing current work
before switching to UI. Includes current source/tests/tools/docs, saved PoseAgent
and A_Sword, required physical-mesh Python label helper, and current lightweight
MimicKit/Sound Studio source. TestNN's local modification, generated models,
environments, full captures/diagnostics and unrelated PDF remain local. No editor
mutation or new build for this checkpoint. Recovery inventory regenerated from
the staged tree; Git history/remote identify the final checkpoint. See Recovery
opening for external dependencies and scope.

**November3 Sound Studio - CLEAN PRESET / SIMPLIFIED / VERIFIED:** independent native Windows WAV
editor at `Labs/SoundStudio`, desktop **Prophecy Sound Studio**. Source defaults to
`Documents/Sounds`, target `Documents/Sounds Mixed`. Large frequency-coloured
spectrum/waveform, source/mix browsers, unique named exports and double-click
remix with fresh defaults. Three viewport buttons EQ / Volume / Pitch, default
EQ: each has exactly five sliders and five draggable points. Switching preserves
curves; each slider now has a visible reset arrow, Reset view resets that curve.
Red top-right Reset all clears effects, curves/time points, grains/pattern, trim,
output name, loop/bypass and stored sequence/joins; returns to the loaded source.
EQ reset arrows restore frequency/gain/Q. Folder locations and files remain intact.
Volume 0-200% (neutral100), pitch +/-24st (neutral0), movable internal
time points with smooth interpolation. Volume and pitch automation cover the
finished output including reverb. Neutral curves bypass exactly. Pitch automation
uses the official Rubber Band4.0 Finer R3 CLI with sample maps, stereo linked,
padding and duration compensation. Installed privately via pinned-checksum
`install_audio_tools.py` under `Saved/SoundStudio/tools`; normal operation offline.

IN/OUT trim handles can cross: IN -> source end -> source start -> OUT. Zero is
selectable; equal handles mean a full revolution starting at IN. Optional top-bar
Granular button reveals size, density, position, scatter, pitch spread, reverse chance, output length,
Freeze and New pattern. Seeded Hann overlap-add, bounded overlap normalization,
polyphase/sinc antialias sampling; default Off. Lean panels move to the right
sidebar on shorter windows. Grains/sequence share expansion space for the canvas.
Top-bar Crossfade button opens the separate mode; it adds source/mix WAVs or an edited snapshot, reorders
clips and sets incoming equal-gain/equal-power crossfades. Overlap capped at half
both neighbours. Mixed rates/channels handled; float assembly retains all source
hashes and clip recipes. Edit/sequence switching preserves both workspaces.
Multiple takes/variation UI removed. Each Generate click saves one unique WAV,
retaining loaded source/edit and continuing playback. Change settings or New
pattern and generate again. Rename
selected in either browser changes WAV/recipe names without changing samples,
refuses collisions and updates loaded/sequence references.

Five EQ bands still reach CUT, including middle notch zeros and outer shelf cuts
held to the spectrum edges; exact0dB reset. Immediate curve feedback,25ms preview
scheduling, in-process EQ,128MiB bounded stage cache and audio publication before
visual analysis remain. Volume/compression reuse cached pitch automation. Playback
continues on the previous buffer while expensive pitch/grain edits render; no
stop/reset. Source changes cancel obsolete work. Actual waveform/local FFT follow
the audible position. Fixed64x amplitude/100% listening, no hover popups. One Play/Pause
plus purple Play original toggle button; loop default on. Space and arrows+/-250ms
override focused controls. Zero fades and neutral/off effects remain defaults.
Compression Off-100% stays linked/downward with no makeup gain.

**November3 source-anchored trim display:** waveform and trim bar use full source
time; moving IN/OUT does not rebase, resize or pan the view. Actual processed
min/max samples map back to retained source positions; excluded source remains
visible but greyed out on both views. Wrapped IN>OUT greys the middle gap; equal
endpoints retain a complete revolution. A red trim-bar playhead maps original
and processed playback through trim, wrap, speed and reverse. Reverb tail holds
at the endpoint; granular display explicitly represents selection progress, not
individual grain provenance. Live buffer maps retain each audible render's
settings, including delayed device buffers. Trim edits preserve source position
when retained, otherwise snap playback to the nearest boundary without panning.
40 targeted timeline/navigation/transport/reset/export checks pass, including
muted live-device trim changes and pixel checks. Rendered normal/wrapped/equal
views inspected in Saved/Diagnostics/SoundStudio20261103/trim. Source samples and
DSP/export algorithms unchanged. User Refresh required; production not restarted.

**November3 waveform navigation:** click-drag scrubs continuously; holding near
either waveform edge pans the time window in both directions. Mouse wheel
stretches/compresses time around the pointer (20ms to whole clip), without
changing audio or64x amplitude. Works in EQ/Volume/Pitch, original/processed,
paused/live. Normal playback follows at the right edge; new-source/Reset all
restores2s. Seeks coalesce in the existing device callback, no stream reopening.
17 targeted navigation/transport/reset/export checks pass, including muted real
device scrubs and paused edits. See test_wave_navigation.py and SoundStudio README.
User clicks Refresh app to load; production app was not restarted.

Centred Clean button in the sound title bar uses the user's chosen Clear strong
preset from `Clean latest Bandicam audio` (01a1942d-495c-7842-9427-adc5faf0ee25):
installed Antinode Clear VST3, ambience-24dB, voice reverb-12dB, voice0dB, Eco off.
Reveals0-100% blend slider, initially100%, with reset arrow; default Off and
new-source/Reset all turn it Off. Refresh retains enabled/amount. Full-source
cleanup runs in a cancellable hidden child before wrapped trim/other DSP; cached
result supports later slider, trim and EQ edits. Playback continues. Source-level
RMS matching reproduces the old cleanup without its extra listening boost.
If Clear is still unactivated its periodic trial noise remains; licensing is
unchanged. Real12.77s reference comparison: correlation0.999999982, zero measured
sample lag, RMS error1.08e-6 after undoing reference boost. First UI pass32.8s,
cached amount update1.06s. Muted device test preserved stream identity; preview
and mono48k export matched exactly, reset complete, source/reference hashes
unchanged. Both1520x970/1280x800 layouts inspected, button centred exactly.
Receipts: `Saved/Diagnostics/SoundStudio20261103/clean/`.

Latest UI supersedes earlier layout: footer/under-wave status row removed;
messages/errors/warnings use the header centre without modal warning popups.
Refresh app is inside the source panel at bottom left. Live Preview/Folders/Guide,
format selectors and redundant Grain controls button removed. Direct top mode
buttons reopen their panels when covered; clicking an open mode turns it off.
**Fixed output:48kHz, mono, dithered16-bit PCM**, following Epic's recommendation
for direct Unreal import (24-bit conversion lacks dither; source linked in README).
No universal AAA format claimed. Float processing/high-quality SoX/R3 retained.
Automatic overload protection acts only at estimated full scale, lowering the
whole clip to about-1dBTP and reporting reduction in the header. Preview/export
share protected samples. This fixes the integer-clipping popup that also blocked
playback. Optional Protect peaks keeps the stricter-1dBTP ceiling below full scale.
Engine API retains neutral source-format/stereo support; the UI always uses the
fixed output/safety policy. Stereo spread control removed with fixed mono.

Bottom-left Refresh app loads new local code, retaining the WAV/edit, envelope
view, grain seed, sequence, folders/name/layout; playback stops. Old snapshots
migrate to the fixed output policy; removed batch/format options stay removed.
**User operates Refresh app; do not click it or restart their running app to
install routine edits.** Pending work drains before lock release/relaunch.
Matching shortcut/process AppUserModelID and native icons are unchanged.
84 signal/UI tests passed (200.63s), including Clean blend/cache/reset/refresh,
cancel/missing-plugin handling, playback/export equality, overload protection,
all knob/global resets, repeated saves with stream continuity, direct header buttons,
removed controls and old transport/EQ/compression behavior,
wrapped sample order, five-knob views/reset, measured pitch automation incl short
clips, grain reproducibility/alias suppression, crossfade laws, all-source hash
checks, rename integrity, distinct/repeated exports, continuous playback and
refresh restoration. Separate muted device-path tests; no subjective audition
claim. Source fireplace SHA-256 unchanged. Visual checks at1520x970 and1280x800:
`Saved/Diagnostics/SoundStudio20261103/simplified/`. Normal canvas grew519->572px
high after row removal.
Additional visual regression passed:64x source-strip peaks now clip to their own
rectangle instead of painting across the spectrum on loud material. Pixel test
accounts for Windows display scaling. Updated overload screenshot inspected.
Earlier wrapped4.08s grain render improved~6.1s to~0.8-1.3s; pitch envelope~3.2s
inclUI under load, not guaranteed
real-time. Research links, installation and workflow: [SoundStudio README](Labs/SoundStudio/README.md).
No Unreal/assets/training changes; the user's running app was left untouched.

November3 appearance update: user rejected bright silver panels and unchanged-
looking viewport. Current theme is dark silver/gunmetal across the whole app:
charcoal chrome, neutral-grey spectrum/wave/envelope canvas, silver controls and
selected states; no navy canvas. Frequency colours, purple bypass and red reset
remain. Shared `studio_theme.py`; paint colours updated in both canvas modules.
Eleven existing UI/integration checks passed. EQ/volume/pitch, Clean controls,
granular/crossfade and details inspected at1520x970/1280x800; no clipped canvas.
Source hash unchanged, no audio/transport changes or production-app restart.
Screenshots/receipt: `Saved/Diagnostics/SoundStudio20261103/silver/`.
November3 folder ordering: source and saved-mix lists sort by Windows creation
date, oldest first; equal times use relative filename. Verified both panes,
filtering/subfolders, modification-date independence, rename and kept selection.

**October22 per-arm grab independence â€” INSTALLED/VERIFIED:** Joint
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

**October22 clavicle grab fixed â€” loaded/verified:** correct Self/closest-agent
wiring was rejected by StartGrab's fixed4cm open-finger clearance cap. Replaced
that cap with a collider/hand geometry bound, one-time admission work only.
Live Coding1action161.75s, reload10:46:44UTC. Exact current TestNN owned PIE:
BP starts at absolute30, reaches by60, grips by90 and holds through180. No tuning,
wiring, save or restart; dirty agent BP/TestNN preserved, owned Play ended.
Slow startup is existing sword Start Slow FPS=true/Slow FPS=5; removal of its
EndPlay reset now preserves that cap. Startup values unchanged. Normal DLLs
remain stale. See ReachGrasp opening and GrabDefaultsSelf diagnostic receipts.

**October22 all grab nodes default Self â€” loaded/saved:** added DefaultToSelf Agent
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

**October22 Grab Bone optional surface point â€” loaded:** new visible Use
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

**October22 closest-agent node â€” loaded:** added pure Get Closest Agent
in existing Reach library, Prophecy|Agent category. Same-world3D actor-position
distance, excludes self/destroying agents, returns None when unavailable. No
retained state or background work. Dirty BP_ProphecyManualPoseAgent preserved to
disk before reload; previous saved bytes in Saved/Diagnostics/ClosestAgent.
Live Coding3actions178.65s, reload09:18:36UTC. Verified correct nearest-other
references for all3TestNN agents and None input; Blueprint types healthy after
compiling the dirty agent BP. TestNN consequently dirty, left unsaved. No Play,
restart or wiring edits. Tools/ReachGrasp/VerifyClosestAgent.py and diagnostic
verification.json retain the check. Normal DLLs remain stale. See ReachGrasp topic.

**October22 reach/grab pelvis floor â€” loaded:** minimum commanded pelvis height
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

**October21 Optimised sword cuts â€” saved, loaded and tested:** A_Sword has
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
world~0.45â€“0.73ms physics CPU, not an Unreal FPS comparison. Shared opted-in pike
hard-stop correction also tightened; ordinary joints unchanged. See
[implementation, measurements and exclusions](Docs/OptimisedSwordCuts.md).

**October21 first wound ray â€” fixed, saved and tested in current head-pike scene:**
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

**October21 coupled pike solver â€” built, loaded, measured:** replaces unswept
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

**October21 Play-camera ZQSD â€” loaded and bindings verified:** user requested
ZQSD instead of WASD. DefaultInput FlyCam mappings changed; native DefaultPawn
requires the existing editor helper's new3-key remap (Q descent moved to A).
Only ProphecyDebugCameraInput.inl/config/tools changed; no maps/BPs/Play touched.
After the shared Live Coding build succeeded, Tools/SetPlayCameraZQSD.py installed
the helper at09:06UTC. Log verified changed=3 ZQSD=1 QDescends=0; loaded FlyCam
axes verified Z/S and Q/D. No Play started/stopped, no asset saves or restart.
Normal DLLs remain stale: normal build needed before future cold launch.
See Docs/DebugCameraInput.md. User retains motion testing.

**October21 wound correction left enabled â€” supersedes one-shot demo:** user
explicitly requested keeping it in. ShowPikeWoundProjection.py --keep-enabled
now stays registered across Stop/Play in this editor, with no demo timeout or
automatic Play control. Attached to existing user Play without stopping it.
Same lateral-only Python prototype, no native build/BP edits/saves; normal
iteration budget. Clears world references between Play sessions, rebinds next
Play. Editor restart still needs reinstalling this helper; not packaged runtime
code. Dirty A_Sword preserved. Do not revert to one-shot behavior unless asked.

**October21 wound demo rearmed â€” user controls start:** previous demo was stopped
by user; callback retired. User missed the motion while assistant launched it.
ShowPikeWoundProjection.py --arm now waits for their next Play press (up to10min),
then applies the same temporary correction through that Play only. Do not launch
Play for them. No save/build/wiring changes; dirty A_Sword preserved. Stop Play
retires the callback. Receipt show-wound-anchor.json records armed/active/retired.

**October21 wound-line visual demo â€” Play left running for user:** user asked to
judge the temporary post-solve sword translation. ShowPikeWoundProjection.py now
runs it in the current scene; first cut t0.266667, 74 corrections over1.2s,
maximum shift0.807332cm, same as prior prototype. Normal iteration budget;
no rotation/velocity edits, native build, asset save or BP changes. Callback
retires on Stop Play/world replacement/error or10minute safety timeout. Do not
stop this user inspection session. Initial owned attempt hit a Python validity
API error before any correction; ended only that failed owned Play and reran
with SystemLibrary.is_valid. Receipt Saved/Diagnostics/PikeSlide/show-wound-anchor.json.

**October21 wound-pivot follow-up â€” transient prototype only:** user rejected
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

**October21 user visual iteration trial â€” Play left running:** user asked to see
the higher-iteration effect. ShowPikeIterations.py started Play and applied
transient10velocity/32position to victim mannequin at first cut,t0.266667;
native log verified10/32. Callback unregistered after application. This Play is
now for user inspection: do not stop it. No saved tuning, BP or camera changes;
dirty A_Sword present before starting. Stopping Play discards iteration overrides.
Receipt Saved/Diagnostics/PikeSlide/show-iterations.json.

**October21 sword depth stain â€” additive, installed/saved:** A_Sword
**Stain Blade(Depth, Seed)** keeps Max(previous,Clamp(input,0,1));0 adds nothing,
.5tip-to-half,1tip-to-hilt. Seed(int0 default) chooses a repeatableÂ±20deg/slightly
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

**October21 arm pike lateral drift â€” investigated, no production change:** current
upperarm_l cut starts aligned; X/Y and all rotation axes Locked, blade Z Limited.
Both frames stay fixed but native/visible error reaches5.223cm/44.304deg.
Same-prefix transient10velocity/32position comparison reduces to0.550cm/14.006deg;
confirms convergence sensitivity, not an approved high-cost fix. Unreal projection
is enabled in profile but not implemented by Jolt adapter (linear alpha1;
angular alpha0). No build/restart/assets saved; owned Play ended, transient solver
settings retired. Dirty NS_bloodwound/map preserved. See JoltSkeletalProps opening
and Saved/Diagnostics/PikeSlide. Next fix should be scoped to cut/slider behavior.

**October21 node rename â€” live, no restart/build:** Accept Pike Hit now displays
**Cancel Hit Reaction**. Updated native UFunction DisplayName metadata through
remote Python and the narrow header's DisplayName for future builds; underlying
AcceptPikeHit function, pins and behavior unchanged. Native graph audit confirms
new title; full live A_Sword exports SHA-identical before/after. User's dirty
A_Sword preserved unsaved. No Play/compile/save/restart. Metadata-only source
change is not yet in normal DLLs: next normal build incorporates it; until then
`Tools/SwordHolster/RenameHitReaction.py --apply` reapplies after a cold launch.
Receipt Saved/Diagnostics/CleanPike/rename.json.

**October21 clean pike entry â€” installed/verified:** Blueprint acceptance stays
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

**October21 blood mesh shadows â€” user verified:** active Fountain001 mesh renderer
in NS_bloodsplat2 uses new M_Blood_ShadowOnly, masked ShadowPassSwitch(0 visible,
1 shadow); original sprites/material and mesh geometry/scale retained. Only
material and NS saved; user confirmed shadows work. See Docs/BloodExperiments.md.

**Sword Slow Start clock â€” October20 fixed/verified:** user's true/5 startup
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

**Separate skeletal blood brush â€” October20 installed/verified:** placed
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

**Grid3D fuse visibility â€” October20 config change, untested by request:**
DefaultEngine.ini [ConsoleVariables] now forces r.HeterogeneousVolumes=1 above
scalability priority, preserving other quality settings. Installed UE5.7 source
confirms this config section also loads in Shipping. Applies next startup/future
packages; no live command, build, restart or runtime test. See Docs/BombFuse.md.

**Automatic blood Niagara callback â€” October20 installed/verified:** placed and
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

**Actual injury floor painting â€” October20 repaired/verified:** user fixed the
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

**Separate decal rendering â€” October20 fixed/loaded, not the requested paint:** injury callback and
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

**Sword/skeleton penetration â€” October20 repaired/loaded:** external constraints
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

**Directly placed mannequins â€” October20 installed/verified:** user requires
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

**Sword pre-impact first-collision follow-up â€” October20:** update-current-values
is correctly called inside ReceiveHit. Live log rejects placed A_Sword1 from Jolt
because MACD=true; Chaos events therefore return invalid/zeros. Switched only
that placed sword to supported ordinary CCD (MACD=false/CCD=true), verified after
component reconstruction. Map dirty/unsaved; no Play/build/restart. Class/child
defaults unchanged, still MACD=true. See Docs/HitImpactSpeed.md.

**Sword pre-impact node â€” October20 rewind installed/verified:** user rejects
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

**Shared blood manager â€” October20:** user requested consolidation for sword
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

**Blood rectangle merger â€” October20 installed/verified:** user explicitly requested
production integration. Existing FoliageDecalGrid component/library now use the
lab's greedy rectangle kernel; Blueprint graphs and settings retained. Hit receiver/
instance and plane separate surfaces; sloped planar floors supported. Corrected
half-extents, actual widthÃ—height debug bounds. Dirty regions only, pooled hidden
preparation, max16 allocations/pass, no idle timer/tick. Existing interval/budget/
limits retained; 32Ã—32 maximum region, smaller MaxMergeLevel respected. Capacity
retains pending occupancy instead of evicting old stains; Process/Start after cap
increase resumes. Source/build details and compatibility notes in
[BloodExperiments](Docs/BloodExperiments.md#rectangle-integration--october20).
Private retained layout required normal restart. Preserved dirty user A_Sword and
explosionVFX with backups/hashes. Six-action minimal normal build111.80s passed;
RectangleIntegration passed10:40:53UTC, zero errors/warnings (coverage, hole,
negative cells, reuse, receivers/heights/slope, capacity, allocation cap, cleanup).
Editor29952 reopened explosionVFX normally. Actual placed original manager in brief
owned Play:16cellsâ†’one102Ã—25.5cm projector, including existing1.02padding. Owned Play
ended; map/sword/manager saved hashes preserved. No fountain recreated. Normal DLLs
current; no production GPU/FPS claim. Evidence Saved/Diagnostics/BloodRectangleInstall.
Independent lab/tests remain in Labs/BloodDecalLab. Historical isolated CPU results:
filled43â†’1,hole43â†’4,splash52â†’24,strip8â†’1; kernel7.17us/region, streamed p95.203ms,
cold capped max.749ms. These are lab NullRHI measurements, not production timings.

**Blood callback follow-up â€” October20:** new NS_bloodsplat pointed its callback
to the Blueprint asset. Replaced with placed BloodExperimentManager actor; both
Niagara override stores verified. Tuning unchanged; no Play/test/restart. Map left
unsaved in the user's editing session. See Docs/BloodExperiments.md.


**Blood experiment â€” October20 ready:** explosionVFX now has BloodFountain,
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


**VFX reopen â€” October20:** requested explosionVFX for blood work. Minimal normal
build succeeded (16 actions,312.35s); base DLLs now include preceding Live Coding
changes. Editor22852 launched normally on /Game/explosionVFX. Startup dialog dismissed;
map and remote connection verified before blood setup.
No assets changed or saved. Read-only probe: Saved/Diagnostics/VerifyVFXOpen20261020.py.


**Explosion lab checkout removed â€” October19:** user requested detachment/removal
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

**VDB node colors â€” October19 installed and verified:** Temperature Color and
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

**Optimised checkbox â€” October19 installed and verified:** user requested
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

**VDB prototype findings â€” before checkbox:** user accepts a modest hitch only at effect startup, not
periodic refresh hitches. Do not implement a low-cadence refresh as the solution.
Cached final-volume/fade prototype succeeded, retaining real3D. At half/.0833/.01
density, current-style preparation7.5â€“8.2ms plus translucency1.2â€“1.3ms became no
preparation and translucency1.0â€“1.4ms. Native-setter repeat plus90degree camera move
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

**VDB deeper investigation â€” October19, no new production change:** user requested
all performance knobs and explanation of costly near-invisible tails. Five owned
comparison runs completed (one VDB at a time); editor26816 left explosionVFX/outside
Play, profile CVars/throttle restored. Our fade handling disables lighting reuse at
tick180 after source ends at90; unchanged shape suddenly regains downsample/lighting
passes. At density.01, repeated GPU scopes: density downsample2.521ms, lighting1.193,
colour4.465 (prep8.181), translucency1.336. These are pass costs, not30ms effect cost.
Render downscaling still evaluates all source voxels; eighth not automatically faster.
Temporary eight-colour-sample shader trial cut quarter colour4.4â€“4.5â†’.9â€“1.0ms,
but added fire grain; motion/other views not validated. Original engine shader restored
byte-identical and recompiled before repeat; no experimental shader installed.
No native build/restart, user-asset or BP edits/saves. Prior adapter and stale normal DLL
status unchanged. Full native control catalogue, test receipts and prioritized next
work in Docs/ZibraExplosionFade.md. First proposed exact improvement: independently
cache unscaled density grid across held-frame density fades (no DensityScale input).
Final-volume caching tested as above; production caching and optional sampled
quality/cutoff remain proposals, not installed nodes. No recurring refresh cadence.
Evidence Saved/Diagnostics/VDBPerformance20261019.

**Sword death/drop repair â€” October19 installed, user accepted:** inspected current `die revive`.
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

**VDB performance â€” October19 installed/verified, full 3D:** node-spawned effects
(including bombs) use quarter render-volume resolution, eighth lighting resolution
and main ray step4, configured before asset assignment to avoid full-resolution
startup allocations. Lighting is reused on unchanged source frames at stable
density, refreshed through fade/endpoints/snaps; zero-density tails disable plugin
visibility while preserving actor lifetime. No entire-clip cache or plugin edit.
Fine smoke detail is softer; moving-light/occluder lighting can stay frozen during
a constant-density held frame. Source animation timing and all node controls remain.
Controlled matching GPU captures: moving47.74â†’33.96ms, held41.41â†’22.25ms,
fading40.09â†’28.84ms. CSV means show smaller moving improvement; these are fixed
capture GPU costs, not gameplay FPS promises. Resident scene+effect GPU memory
3514.7â†’2939.9MiB. Invalid early pilots discarded. See Docs/ZibraExplosionFade.md.
Only ProphecyVDBLibrary.cpp changed. Two one-action layout-safe LC builds passed
61.15s/83.47s, final reload08:33:08UTC/no object changes. No restart or content save.
Timing automation passed08:33:59UTC; four actual-asset runtime cases and rendered
fade captures passed08:35:22UTC. Editor26816 open explosionVFX/outside owned Play.
Normal DLLs stale: minimal normal build required before any cold launch.
Evidence: Saved/Diagnostics/VDBPerformance20261019 and VDBCacheBenchmark.csv.

**Static fuse / upright Niagara â€” October19 installed and verified:** user rejected
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
0â€“1, default0;0 burns fully,.5 burns halfway,1 instant (zero speed allowed).
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

**Fragment transparency fade â€” October18 installed/verified, no restart:** Light
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
solid through120, fading121â€“239, destroyed240 for lifetime4/fade2. Both solid/half
screenshots inspected. Editor6904 remains explosionVFX/outside Play; user dirty map
and NewNiagaraSystem untouched. Base DLLs require minimal normal build before next
cold launch, incorporating fade, fragment toggle and impact event. See
[BombFuse](Docs/BombFuse.md); Saved/Diagnostics/BombFragmentFade, Tools/BombFuse.

**Explosion impact event â€” October18 installed/verified:** six-file extension,
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

**Fragment toggle â€” October18 installed, no restart:** Light Bomb Fuse
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

**Light Bomb Fuse â€” October18, installed and verified:** node in Prophecy/VFX
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

**Spawn VDB Effect node â€” October18, installed and verified:**
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

**Upper-body PHAT saved in place â€” October17, user authorized:** nine profiles
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

**Current-source shoulder-limit overlay â€” October17:** updated-source viewer now
has a checked-by-default "Show shoulder limits" checkbox. Green arms show both
nearest admissible shoulder rotations, for authored and robot views at all55
frames. Other local joints stay fixed; hands follow, with no planted-contact
solve or dynamic simulation. `add_source_limit_overlay.py` uses constrained
multistart quaternion-distance optimization; all220 resulting shoulder samples
accepted by exact project Jolt. overlay-verification.json records corrections.
Full-geometry handedness correction retained. Source/PHAT/training unchanged.

**Updated authored crawl and viewer handedness â€” October17:** freshly imported
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

**Crawl package corrected to the single current PHAT â€” October17:** removed
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

**Current PHAT crawl analysis â€” October17, read-only:** user clarified that
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

**Explicit elbow posture / wrist twist â€” October16 current:** user reproduced a
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

**Unreal port/build state â€” user-requested grab behavior restoration:** user rejected
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

**Historical approach/held-elbow port to Unreal â€” October16 (superseded above):** explicitly requested by
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

**Left elbow hitch â€” October16 historical intermediate fix:** in the unmodified current
TestNN tick30 fixture, commanded left elbow made~0.9cm single-tick jumps at193,
218,256,275,307; the physical elbow followed. Wrist and shoulder stayed smooth.
Cause: fixed coarse half-step search near wrist alignment. Both lab `coupled.js`
and native `ProphecyReachArm.h` now scale elbow/roll search steps with remaining
quaternion error, retaining full steps above8deg and the same18-evaluation cap.
No new search/state or tolerance changes. Reconstructed one-step replay matches
the hitch within0.0004cm; full owned360-tick same-fixture capture verifies max
left-elbow step across absolute200â€“300: command0.90093â†’0.05366cm, physical
0.90080â†’0.05329cm, commanded angle2.252â†’0.131deg. Left physical grip acquires at111
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

**Reach/grab Unreal port â€” October16 complete:** user explicitly authorized the
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
**PHAT limits â€” October16:** at the user's request, saved seven angular-profile
expansions to contain the drawn/unarmed motion dataset plus5% room. Upper arms,
thighs, ankles and right knee changed; both user-edited wrists remain60/45/90deg.
Frames, geometry, mass/inertia, collisions and Blueprint wiring are unchanged.
Exact values and backup are in `Docs/MimicKitUEFNBodyMatching.md` (current section).
The REACH imported snapshot described below predates these seven expansions;
its lab files/session were not changed by this PHAT update.
**Lab refresh preference:** the user handles Refresh with the lab button. After
code edits, do not automatically reload, close or reopen their lab window. Leave
the running session alone and report that the change is ready to refresh.

**REACH elbow blend slider â€” October16:** **Elbow down blend** sits directly
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

**REACH rotation timing â€” October16:** shared right-panel **Sync rotation** slider
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

**REACH PHAT snapshot â€” October16:** imported the user's newly edited loaded
PHAT wrists into `Labs/ReachLab/phat.json`: both hands60/45/90degrees in
twist/swing2/swing1 order, all LIMITED; frames unchanged. Lab HTTP export matches
the file. Ready for user's manual Refresh; no build/restart/Play or asset save.
Before/after evidence: `Saved/Diagnostics/ReachPHATImport20261016/`.

**REACH elbow preference â€” installed and verified:** only `PreferredBend` in
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

**Current REACH solver â€” arm first:** the old forearm-derived virtual endpoint
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

**Reach lab ready â€” lab first, port later:** user requested the same rapid iteration
workflow as D/S. [REACH â€” Hand & Body Lab](Labs/ReachLab/README.md) runs at
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
icons use the user's latest captured values: L13/60/125cm with rotation180/0/90Â°,
Râˆ’14/47/125cm with rotation0/0/âˆ’90Â° (October15 explicit default update).
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

**Reach lab grab pipeline complete â€” October15:** both hands now have Grab ball
and one shared persistent **Ball radius** slider below the centered clamp checkbox
(0.5â€“15cm, initially3cm). It updates both balls together; per-hand radius inputs
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

**Complete â€” grab-angle Blueprint node:** user explicitly requested adjustable
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
Prophecy â†’ Grab; call Set Grab Angle Tolerances before Grab Object/Grab Bone.
No user Blueprint wiring or default tuning changed. Evidence:
`Saved/Diagnostics/GrabAngleTolerances20261015/`.

**D/S motion is TEMPORARY FINAL, accepted by the user.** Preserve the accepted lab/Unreal motion and tuning; change it only on a new user request. Latest reported Sim slowdown was not reproduced, and the user subsequently said it looked good. The explicit right-wrist limit follow-up is complete; no implementation task remains active.

- **Current review setup:** user removed the continuous D/S branch and requested the October12 two-ball grab experiment on their existing one-shot tick30 branch. PoseAgent and TestNN are now saved locally with two radius3cm spheres assigned to the player. Ball physics prepares at tick29; both Grab Object calls start at tick30,120cm/s and180deg/s. Player sword hides at the trigger; grabs stay held for user review. See [reach/grab review fixture](Docs/ReachGrasp20261012.md). No reach/grasp runtime solver or D/S tuning changes; no commit/push.
- **Wrist-limit follow-up complete:** D/S frees the hand_râ€“lowerarm_r joint's three angular motions through the full return, then restores the exact entry motions/angles through existing completion/interruption cleanup. Retained layouts unchanged. Four owned-PIE checks/498 sampled checks pass, including custom limits, repeated requests and hide during both returns. Full BP graph unchanged; no assets saved/restart. Current user graph starts S during initialization; diagnostic waits for it to finish before its controlled D/S pair. [Wrist-limit lifetime and evidence](Docs/SwordHolster.md#right-wrist-limits-during-ds-october15-follow-up).
- **Reach/grab PHAT follow-up complete:** user requested hand control follow the edited PHAT automatically; explicitly reach/grab only, D/S excluded. Native overlay reads loaded asset wrist frames/modes/angles each active update and constrains hand orientation, including release return. 4,860 math cases and804 live wrist samples pass across Kin reach, Sim reach and Sim ball grabs. Editing an isolated transient PHAT during an active Kin reach updates the clamp without restarting it. **Ball fixture limitation:** both target positions reached, but neither grip acquired by210 under current wrist limits; no success claim for grasp acquisition. User asset unchanged, no retained layout changes/save/restart. [Details and evidence](Docs/ReachGrasp20261012.md#phat-wrist-constraints--october-15).
- **Remote checkpoint:** commit `965b9cb4ac649f8f4ce7604e9a6b5c33588b1536` on `codex/standalone-sim`; annotated tag `ds-temporary-final-2026-10-15`. Branch and tag verified on GitHub. Previous broad D/S checkpoint `b34e1b31` is its parent. Recovery manifest verifies all 5976 recorded files; this is a curated backup, not the whole project/machine.
- **Finger rendering follow-up:** grab calculation was active but LOD1 removed finger bones (`r.SkeletalMeshLODBias=1`). Saved test player's Mesh/PhysicalMesh Forced LOD Model1 (=renderLOD0) in TestNN, matching the original experiment. Attack Fists already enabled; no graph/runtime/global-LOD changes. Kinematic LOD0 finger/model error<3e-7cm; physical native finger poses already present and LOD0 selected with the pre-Play override. Evidence `Saved/Diagnostics/ReachGrabFingers20261015/`; use next Play for the saved override.
- **Editor:** grab-angle implementation required one normal build/restart. Its first launch mistakenly used WindowStyle Hidden; user reported no visible editor. Clean hidden editor25832 was closed and reopened visibly as13040, without another build or asset changes. Use **Normal** for the requested interactive editor/browser; **Hidden** only for background helpers. Latest lab task preserved this running editor. User PoseAgent/TestNN edits saved with prior disk backups; PHAT unchanged. Reflection status3/native_properties0/pin_types0; wiring preserved. Remote checkpoint predates these local assets and does not contain this scene.
- **Build:** normal incremental editor build succeeded in492.43s for the grab-angle node and incorporated preceding Live Coding patches through20. **Normal DLLs are current.** Keep future builds minimal/incremental and prefer reload-safe implementations where appropriate. Do not restart just to tidy, save, inspect or tune; retained native storage/layout changes still require normal build/restart.
- **Last saved asset verification:** PoseAgent compiled status3 and saved with TestNN for the grab fixture. Against the user's live pre-edit full graph, only the existing tick30 Branch's unused Else and its terminal reroute's unused Output gained links;28 nodes added, no existing nodes removed or tuning changed. Both reaches active at absolute30, physical grips90/93, held through220. A_Sword untouched in this task. Native reflection health remains status3, native_properties0, pin_types0. Evidence `Saved/Diagnostics/ReachGrabWiring20261015/`.
- **Local-only work:** TestNN, generated defense pickers, separate MimicKitTraining/PhysicalRecovery work and unrelated PDF remain outside this D/S checkpoint. Do not stage, clean or overwrite another task's work. `ProphecyFKReturnFeedbackTests.inl` has appeared dirty without a semantic `git diff`; inspect before treating it as a new change.
- **Primary references:** [D/S runtime and integration](Docs/SwordHolster.md), [lab controls/recorded problems](Labs/SwordHolsterLab/README.md), [attached-arm physics audit](Docs/SwordHolsterPhysicsAudit20261014.md). Full old opening retained in the [October10â€“15 archive](Docs/Journal/ProjectJournal-history-through-2026-10-15.md); rejected trials are historical, not pending work.

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
| FKâ†’IK arm-return blend |Enabled, fractions.25â†’1|Disabled|
| Coordinated elbow IK correction |Enabled,15deg soft zone|Enabled,15deg soft zone|
| Independent hand rotation FK alpha |1|1|
| Big-node NN blend range |(1,1)|(0.7,1)|

Other saved values: axial shrink25% over.25s, unshrink.5s; attached hand speed150cm/s and angular speed200deg/s. Big-node grip holster rotation compensation80%, return duration.25s, S kinematic switch fraction.5. Leeway attachment phase disabled; tip tolerance2cm. D hand-local-X turn800deg/s, sigmoid exponent1.5, cutoff.4 of arm return. Negative angular speed reverses it; afterward existing hand return continues. Return durations can include angle-dependent extra time; base duration is not necessarily total duration.

For later user-requested imports, `node Tools/SwordHolster/SyncLabProfile.cjs` exports saved lab settings; inspect its semantic diff before applying. Existing big-node pins override imported values. `Prophecy.Editor.RefreshHolsterGripPins SetSlideSpeeds <draw> <sheathe>` updates only unlinked speed literals; preserve every other pin and compare the full graph before saving.

Latest import changed only S slide speed170â†’230 and its curve's first interior point to(.15053891961839325,.0988776276854313). Other S points: (.650179602563385,.7111385494636496), (.8849101307618773,.9562043029634382), (.9553293659722167,.9884497709488423). D remained330/linear. In the current saved geometry: S18ticks/.30s, D13ticks/.2167s. Duration depends on blade travel/shrink, not a fixed duration override.

### Ownership, timing and mode switches

- Authored seconds use60 unpaused game ticks. NN inference cadence is separate. Reach/slide curves affect only their procedural motion, not underlying idle/walk/run, head or FK return; each D/S return has its own timing curve.
- Reach uses FK, authored spine/clavicle targets and explicit elbow preference. The rejected direct-IK **reach** trial is removed. This is distinct from accepted FKâ†’IK **return** and coordinated elbow IK correction. Old forearm-only bend limiter remains deleted; Main inertia scales strength without shortening duration.
- Geometry comes from authored sword/holster placement and blade marker; apply asset scale once and shrink only along blade axis. Capture references before moving the mount. Holster follows the actual component; compensation rotates about its origin without introducing pelvis-relative translation.
- S aims tip at entrance with angular tolerance. Optional leeway attachment phase first attaches, then aligns the tip within attached speed limits, then slides from the reached depth. It must not reset insertion to0. Holster-relative speed limits are intentional. Current saved leeway phase is off.
- During attached alignment/sliding in Sim, native upperarm_r/lowerarm_r/hand_r temporarily become kinematic and follow the completed actual pelvis/clavicle and holster-local sword path. Remaining body stays simulated. Sword stays attached to holster; no separate predicted sword path or attached handâ€“sword joint. Release restores simulation from current pose/COM/angular velocities and seeds return from actual current/previous arm poses. Ordinary kinematic characters do not receive this native ownership override.
- Holster simulation switches independently; a kinematic agent forces a kinematic holster while retaining its preference. Physical holster temporarily goes kinematic at the configured S reach fraction / during D sliding. Rotation compensation then applies; usual rest return and original joint restoration resume the prior preference. Interruption cleanup restores owned limits, collisions, joints and modes.
- Tab switches Sim/Kinematic without cancelling D/S, restarting clocks/shrink or losing attachment. Kinâ†’Jolt queues the **entire** mode change at the existing safe admission boundary, avoiding an intermediate Chaos step. Rebind waits for native ownership. Completed attached-arm pose is republished at transfer; stale presentation blend is retired. **No added Simâ†’Kin whole-pose fade**: that trial delayed moving actions and was removed.
- A_Sword's consuming Tabâ†’pause event was removed; character Tab works, Caps Lock backend selection is unchanged. RMB debug slowdown now uses `t.MaxFPS`, not fixed simulation delta. All agent/equipment overlap events are disabled in both modes at user request; blocking collision and queries remain.
- D/S suppresses right-arm collision for the action, restores it on completion/interruption, and applies headâ€“clavicle suppression only during D/S. Neck/head and right-wrist angular limits are Free through the full return and restore their captured entry modes/angles afterward. See the physical-neck reference below for permanent neck pairs. Early NN return protects the gripping arm until release; arm return then uses its own clock/window.

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
| Breathing | [Breathing](Docs/Breathing.md): default upper+pelvis, only at zero movement input; active through D/S. Successive cached idle deltas move actual accepted pelvis/upper pose; legs keep feet in place and NN history receives it. Independent pelvis/upper amplitudes; speed snaps.3â†’1 by.1 using shared pre-baked samples. No presentation-only overlay. |
| Physical neck | [PhysicalNeck20261013](Docs/PhysicalNeck20261013.md): original PHAT23bodies/22joints, neck_01â†’neck_02â†’head, approved capsule size and split neck mass; actual neck_02 feeds NN. Both necks exclude head/clavicles/each other permanently; headâ€“clavicle exclusions only during D/S. Solver comparison option remains available. |
| Get-up | [GetUp](Docs/GetUp.md): remain simulated, restore magnetization; both-arm anti-jiggle until lower handoff then prior independent settings; magnetization0â†’1 at lower marker; slot1 includes PhysicalMesh material. Independent lower/upper handoff/tempering. Automatic floor-lift correction and its toggle were removed; explicit Ground Offset remains. Old tick30 hookup is historicalâ€”inspect current BP. |
| Native reach/grasp | [ReachGrasp20261012](Docs/ReachGrasp20261012.md): Reach Target/Double Reach/Grab Object/Grab Bone, durable local contact point and one joint per hand, fit fingers once. Ball and forehead prototypes tested; lower chin blocked; concurrent attack/get-up ownership not fully tested. Do not silently promote prototype to universally validated behavior. |
| Cosmetic holster strap | [HolsterStrap](Docs/HolsterStrap.md): separate asset/AnimDynamics work, editable ABP body definitions with linked constraints. Does not replace the existing agent holster or D/S. |
| Separate local tasks | [Standalone training journal](TrainingJournal.md) owns MimicKit/AE runs and experiments. Native integration remains in the relevant Unreal topic; training-only updates stay out of this journal. |

## GOLDEN RULES â€” read before touching Unreal

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

## Omni locomotion recording viewer â€” October15

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
- UE first slashLD =lab **variant21**, absolute61â€“101,21 unique30Hz policy frames from41 ticks,25 bones, excluding physical response/post-attack return. UE XYZcm -> lab XZYmetres; imported UE variants bypass harness forearm-roll repair. Original320 variants unchanged. Backup includes current saved lab profiles/view.
- Accepted original FK return with inertia, **not optional continuous spring**. Idle is real Unreal `M_Neutral_Stand_Idle_Loop` frame0, same across attacks, parent-local. Hand local inertia zero, parents still move hands. Spine01â€“05 share one weight, arms symmetric. Main inertia, bone weights, return/easing/timing are per attack. Spine angle adds flat seconds (.29s/90deg default), independent of base duration.
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
- [Full October10â€“15 handoff history](Docs/Journal/ProjectJournal-history-through-2026-10-15.md) preserves every superseded opening entry and previous build/save/test claim. Read current summaries first.
- **Update current sections instead of prepending endless logs.** Keep build coverage, saved assets, defaults versus actual BP, evidence and limits explicit. Detailed experiments belong in linked topic docs/receipts. Archive superseded behavior, preserve user corrections, and never revive an old investigation as unsolicited work.


