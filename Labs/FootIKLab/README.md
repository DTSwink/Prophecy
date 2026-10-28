# Foot IK Lab

Independent kinematic terrain-placement prototype, created October 25, 2026
from the Bodyflip Lab renderer, cached NN gait banks and leg solver.

## Wall gait frame and anatomical knees corrected — October27

The previous "wall leg folding corrected" receipt failed visual acceptance.
Its nearest-feasible-knee rule could reverse the NN hinge and splay a knee.
Rotating the wall view into a floor view exposed the larger mistake: travel
used the surface frame, but pelvis height and legs used the tilted torso frame.
The resulting seated posture made IK compensate for a misplaced body.

The mesh root is now the capsule's ground reference along the surface normal.
NN pelvis translation and lower articulation use that same ground frame.
Upright changes upper posture around the pelvis; hip anchors follow it while
lower chains retain NN articulation. It cannot collapse standing height.
This host placement change is Foot IK-only, not Bodyflip's root controller.

Shared feet carry the source's stabilized signed hinge with the thigh. They do
not choose the opposite knee bend to clear an obstacle, infer its sign from the
tilted pelvis, or use a straight leg's undefined cross-product. Removed the
arbitrary world-up wall lift. Departure uses one position filter; constraint
projection is not swing momentum. Sole clearance, material heel/toe/yaw pivots,
relative ankle constraints and actual-root NN feedback remain.

Validation:15 frame/hinge checks over both601-tick live coupled rollouts;
17 native/root-coupling checks;697 checks across60 directional flat/incline/wall
cases;101 Upright-endpoint checks;1368 Bodyflip shared-adapter checks.
Saved Run143 ground-relative pelvis height87.0cm. Both full coupled clips retain
the NN hinge hemisphere (minimum dot0.984), without sideways flips. Native
recurrent parity3.61e-6, feature error2.39e-7, root replay error0. Visual sequences
20–300 inspected in wall and wall-as-floor views; final actual app load has no
errors and reports actual-root coupling. Its cold surface request took19.1s;
no instant-loading claim. Saved settings/frame/camera were not modified.

This is not a trained falling policy: late Walk cadence fades at extreme
physical descent speeds, and raw NN transitions can remain sharp. Root
speed/history/futures were not capped or replaced. No universal naturalness claim.

Evidence: verify-wall-frame.cjs, verify-wall-frame-browser.cjs,
data/wall-frame-{run,walk}-fixture.json.gz, snapshots/wall-frame-verification.json
and snapshots/wall-frame-{run,walk}-sequence-*.png. Older wall-contact fixtures
and geometry-only receipts describe the rejected version. The broad test now
uses actual release events, not historical pin times; cumulative roll/yaw
re-anchoring is bounded to0.5mm, with the active material pivot exact.
No UI additions, state writes, Unreal changes, server restart or push.
Refresh loads the update.

## Simulated root feeds the recurrent NN — October27

Surface scenes (inclines and edited platform layouts) now couple the120Hz root/
foot simulation to the actual lower/upper NN at30Hz. The initial phase/history
is retained. Every policy step receives measured previous/current root travel
and eight freshly predicted future roots, including upcoming yaw. The forecast
uses a copy of the same gravity/thrust/collision integrator, retaining observed
support only while reachable. It never mutates actual contacts or root history.
The next real tick replaces the prediction; the original constant-speed rollout
is no longer the articulation driving the surface sequence.

The planar NN coordinates follow the surface frame. Posture's Upright setting
does not reduce measured along-surface velocity. Normal motion remains physical;
the NN is not a three-dimensional flight policy. Current/previous recurrent
states are retained across all149 subsequent policy steps, without per-frame
resets, Walk-checkpoint injection, invented pins or swapping forward/back clips.
Walk still commands the Run checkpoint at its direction-specific walking speed.
The ghost shows this live policy before terrain foot correction, carried by the
same displayed root/body alignment. Existing yaw distance schedule is retained.

First-future-root decoding matches the game's native window contract: rebase
against the root encoded by the bounded future features, not an uncapped root
forecast that disagrees with those features. Physical velocity is never capped
by this rule, and measured history remains actual. This removed the severe
pose stretching caused by that mismatch at fast falling speeds.

`surface.js:simulate` exposes an optional generator for the standalone host;
legacy synchronous `prepare` and shared `createFeet` behavior remain unchanged.
`surface_driver.cjs` runs the same JS solver as a short-lived peer of the single
CPU policy worker. One `/resume` request prepares a sequence; the worker retains
policy tensors and uses a validated cached decoder graph. Browser replay uses
the returned policy samples and reproduces the root/foot simulation exactly.
Playback/scrubbing perform no inference. Cache keys include the actual shared
solver/bridge source contents. No additional resident server or GPU work.

Verification:17 coupling checks and41 existing surface/platform checks pass.
All149 root-history deltas equal the actual transported root displacements;
server/browser replay root error is zero in the recorded fixture. Native
recurrent parity error is6.44e-6 for Run and1.69e-6 for Walk; all root-feature
windows match the original training encoder within2.39e-7. At143 the actual
root falls7.234m/s; the following NN step sees7.252m/s down the surface, forward
relative to its final facing. Earlier approach, slowdown and reversal are all
present in the NN input. Current Run shoe penetration stays below4e-8m and
retained contact drift below2e-15m.7 owned-headless checks pass for real app
activation, a single coupled request, restored143/pause, playback, no redraw
inference and no errors; six collider/ghost frames reviewed.

The initial wall-IK failures and numerical metrics in this coupling receipt are
superseded by the correction above. Native feature bounds remain preserved;
unrestricted falls can still exceed the locomotion policy's useful range.

Measured coupled preparation with models loaded varied roughly3–7s under this
laptop's load. A cold production request took15.9s including worker/model
startup; an identical saved sequence uses the existing exact-input cache.
The current production request was prepared and cached. No claim of universally
instant refresh or new-phase preparation. User saved state unchanged; no user
tab/desktop control, server restart, Unreal/Bodyflip edits or push. Refresh.
Evidence: `data/surface-coupling-fixture.json.gz`, `verify-surface-coupling.cjs`,
`snapshots/coupling-{browser,warm}-verification.json`, `surface-coupling-verification.json`
and `coupling-final-*.png`.

## NN ghost investigation and root heading — October27

Reported setup: Run36%, Left, wall90°, yaw200°/s over1.2–6m, gravity70%,
floor removed55, unpin below1m/s; paused143. The ghost is the actual source
NN after root placement and body alignment, before foot IK. Across all601
samples it matches that rigidly transformed source exactly (rotation error
<2e-16rad). Ghost and main pelvis/upper placement coincide within1e-12m.
At143 both have39.289° body tilt; the ghost is not attached to a second,
independently tilted pelvis. Surface foot targets use the surface plane plus
contact/reach corrections, so those legs can differ substantially from the ghost.

The apparent backward gait exposes an existing surface-host limitation:
`prepare()` generates the NN once for constant forward course travel, then
simulates gravity independently. The generated turn ends at184.286° facing,
which commands backward locomotion relative to the body. At143 the actual root
is falling at8.141m/s while the mapped NN course still points upward/into the
wall. That reversal is not fed into the NN's current/history/future root window.
No ghost mirroring, time reversal, gait replacement or motion correction was
made here. A future coupled surface/NN change must supply the actual/predicted
root path and consistent pose history; this diagnostic does not claim that work
is implemented. The separate stair-exit NN handoff remains unchanged.

**Root** now includes a55cm yellow facing arrow. It uses the generated NN root
yaw samples and the command's initial facing, transformed by the same surface
body alignment. It does not use the animated pelvis, the identity synthetic
root axes or travel velocity. Heading holds after the yaw stop and works on
all terrain presets, with IK on or off. Existing checkbox/location marker and
UI arrangement remain. Ghost/Root tooltips clarify their meanings.

16 focused heading/source checks and41 existing surface/platform checks pass.
8 owned-headless checks confirm the rendered arrow, toggle, retained143 frame,
all authored terrains, no errors and byte-identical current motion. Five
current-motion collider frames reviewed with the arrow. User state unchanged;
no NN inference, server restart, user-tab control, Unreal/Bodyflip edit or push.
Refresh loads the overlay. Evidence: `verify-root-heading.cjs` and
`snapshots/ghost-heading-*.json` / `ghost-heading-after-*.png`.

## Low-speed unpin, root velocity and platform editing — October27

More options appends **Unpin below m/s**, default0.2;0 disables the rule.
When the actual root surface is steeper than Minimum gravity incline and the
root's total speed is below that value, both material foot pins release and
cannot reacquire until eligible again. Downhill and lateral velocity count;
this is not an uphill-speed test. Real geometric contact/collision and gravity
remain active. Minimum gravity incline remains editable with gravity off, since
the pin rule also uses it. The release keeps the existing smooth free-foot path.
Shared `createFeet.step` accepts optional `allowPins` (defaulttrue), so Bodyflip
does not inherit this root policy. API version1 and existing dependencies remain.

**Root v** is directly below the viewport status, in m/s. Surface scenes show
the simulated root velocity magnitude; authored scenes derive it from the root
trajectory. **+ Platform** is immediately below that. The editor reuses
Bodyflip's picking and gizmo implementation in an independent local adapter:
click selects;W/E/R move/rotate/scale;scale axes are local;Delete/Backspace remove;
Ctrl+Z undoes transforms;Escape deselects/cancels. Rotation/scaling use the slab
centre. Translation arrows and scale boxes differ. Ordinary dragging still
orbits;selection appears immediately, with only4px pointer jitter tolerance.
Text fields keep their editing keys. Transform preview does no NN request or
full motion preparation; release commits one replan at the retained playhead.

Layouts persist separately for each terrain preset. Edited scenes use the
surface root simulation with actual finite platform queries/collision. Untouched
stair segments retain ramp navigation while feet see treads;edited treads use
their edited plane. Preset geometry fields are disabled while the layout is
edited;gizmos own that geometry. Removing/reverting all edits restores the
procedural preset and its original solver. A distant platform leaves the current
wall sequence unchanged (<2e-14m pose difference). Added landing platforms receive
root impacts and foot pins. Removed surfaces cannot supply hidden support;
deleting everything permits free fall. No existing layout or state was rewritten.

Current Run36/Left/wall90/min80/full70 setup bottoms out at0.2703m/s, so the0.2
default does not trigger in that clip. At0.5, the right wall pin releases at46;
all suppressed frames have both contacts cleared.41 simulation checks pass,
including total-speed semantics, real releases, added-platform landing, five
terrain presets, empty scene and six byte-identical default Walk/Run surface
regressions with the rule disabled.18 owned-headless UI checks pass: placement,
readout, numeric commit/blur, add/select/W/E/R/delete/undo, pointer preview versus
commit, orbit over a platform, reload restoration, retained frame and no errors.
State writes were blocked at fetch and persistence levels; no user-tab control,
server restart, Unreal/Bodyflip edit, inference or push. Refresh loads the changes.
Evidence: `data/platforms-speed-fixture.json.gz`, `verify-platforms-speed.cjs`,
`verify-platform-ui.cjs`, `snapshots/platforms-*-verification.json` and `platforms-ui.png`.

## Turning upper NN uses the game's body-relative frame — October27

Reported scene: Run36%, Left3.5m/s, down16/35cm, yaw200deg/s over1.2–6m,
accent400%. After the stairs both arms straightened into an awkward running
pose. This was already present in the raw commanded NN, before terrain handoff.
An equivalent final heading/speed started from the backward source kept normal
arms, isolating a coordinate-frame error rather than a terrain or speed limit.

`nn_worker.py` reused the root-window world-to-heading matrix for upper pose
codecs that transpose their heading argument. This applied world yaw again
instead of removing it. The pelvis, foot and hand features changed with absolute
orientation. Upper pose headings now rotate with the root's pose frame, keeping
the lower-to-upper bridge constant, as Unreal's `LowerTransformToHeading` and
`BuildUpperBaseFromLower` do. The same frame is used for both seed/history poses,
every upper inference and the final decode. Root-window features retain their
existing convention and all upcoming turns. No checkpoint or terrain-solver edits.

`verify-upper-heading.py` checks434 policy steps against independently encoded
game equations (largest upper error1.08e-6), original lower inference (zero error),
and full-world123deg rotation of the roots plus both seed/history poses. That
rotation preserves poses within0.001mm/axes2.35e-5. The nonturning whole pose is
byte-identical. This scene's raw pelvis/legs/roots/pins are also byte-identical;
after preparing terrain and the real NN continuation, displayed lower joints
are unchanged at all601 samples. Handoff remains103 and raw resumed shoe
penetration6.063mm is unchanged. At212 the elbows change from158/162deg to
92/125deg. The corrected upper remains recurrent NN output throughout.

Reviewed18 actual collider frames across the full turn, handoff and final run.
Owned headless browser reported no errors; persistence disabled and all state
POSTs blocked. Live8890 responses match the verified corrected worker output.
No server restart or user-tab operation; Refresh reloads while retaining state.
No Unreal/Bodyflip changes, added UI or push. Evidence: `data/upper-heading-fixture.json.gz`,
`snapshots/upper-heading-verification.json`, `upperpose-activation.json`,
`upperpose-browser-verification.json` and `upperpose-final-sheet.jpg`.

## Descending release follows travel instead of dragging — October27

Reported scene: Run61%, down16/35cm, yaw200deg/s over1.2–6m, accent400%,51.
The left contact lasted until48.5, by which time its upper tread was almost at
hip height. The free swing then retained a backwards offset from that contact;
recovery was restricted to rising endpoints. Height fitting ran before recovery,
so even an advanced shoe could retain the old tread's clearance requirement.
This path already existed before the previous pelvis fix (51 ankle positions
differed by only2.5mm), but that fix lowered the pelvis another3.4cm in this turn
and made the posture worse. The previous straight-descent checks missed it.

Descending support now reserves reach for the NN's downward hip-to-foot posture,
with the existing2cm allowance, rather than spending almost the whole leg length
horizontally. It releases the upper tread when both cannot be retained. Recovery
also handles falling endpoints. It carries incoming contact velocity for60ms
(bounded by swing duration), then gains travel relative to the pelvis. The fit
cannot introduce a later wait behind the original path merely to follow a slower
reference; real shoe obstacles still take precedence. Descent shoe height is
fitted after that horizontal recovery. Retained heel/toe pivots remain exact.
No new control, time/side-specific production branch or NN weight/runtime change.

Current51 left ankle is32.10cm farther forward and16.08cm lower; with the pelvis
also6cm higher, the foot is22.45cm below its hip rather than0.52cm. The contact
ends at43.5, and the free foot keeps positive travel relative to the hip through
48–57. Current whole-course ankle steps10.99→10.66deg; maximum foot velocity
change remains3.648m/s. Knee step21.043→21.053deg (0.01deg difference); the
earlier source-NN peaks are not claimed removed. Whole-course swing lag is not
increased. Peak pelvis correction18.41→12.42cm. Walk61/2m/s turn also passes:
velocity/angle maxima do not increase and retained contacts satisfy posture reach.

`verify-descent-drag.cjs` passes26 checks. The existing pelvis and earlier turn
suites pass28+21 checks; six ascent/flat/uneven clips remain byte-identical.
The earlier stance-duration fraction assertion is superseded by downward-posture
feasibility and exact retained contact checks. Actual corrected NN continuations
were recaptured for changed seeds. Current Run handoff stays73, post-NN shoe
penetration7.23mm. Walk61 already had no handoff candidate in its5s clip; this
change preserves that and its pure-NN flat fade. Earlier straight Run20/Walk20
handoffs remain73/189; raw post-handoff penetration23.60/4.95mm is not corrected
by terrain IK. Prior turn82 handoff73 stays at7.19mm. No zero-penetration claim
for resumed NN output. Terrain itself stays within1e-5m clearance/reach tolerance.

Evidence: `snapshots/descent-drag-verification.json`, `dragdown-browser-verification.json`,
`dragdown-final-*-sheet.jpg`, and `data/descent-drag-fixture.json.gz`. Reviewed28
actual collider frames spanning both turning descents, with no browser errors.
Owned headless browser only; persistence stubbed and state POST blocked before
page code. User settings, camera and playback remain untouched. Existing server
serves client JS; user Refresh activates it. No server restart, Unreal/Bodyflip
edit or push. Shared exports/API and `surface.js` remain unchanged.

## Descending pelvis: reachable support and balanced transfer — October27

The later descending-release correction above supersedes stance lifetime and
the continuation measurements below; the pelvis/contact-acquisition fix remains.

Reported scene: Run20%, forward5m/s, down16/35cm over12 steps, no yaw,
step accent400%, paused42. An intended lower-tread contact was accepted at32.5
while still unreachable; the pelvis solver pulled the body down26.87cm to
manufacture support. Its recovery envelope retained20.53cm of that lowering
at42 even though the instantaneous reach goal was already zero. The accent
then added another drop. This was a terrain-planning error, not the NN gait.

Lower-tread acquisition now remains swing until the rolling shoe can reach its
contact with the existing2cm pelvis allowance. Established heel/toe material
pins remain exact. Descent pelvis approach/recovery is fitted inside the actual
leg-reach interval to round velocity corners. The descent accent can use soft
extension headroom for its positive half (hold over support, then lower), rather
than retaining only the crouching half. Root navigation and NN body bob remain.
The swing reach limit approaches the landing reach before contact, avoiding a
straightening kick when PIN begins. A lower landing also retires the preceding
toe-off pitch cap during approach, so the shoe does not snap to its new angle.
No frame/leg-specific branch, new control, setting reset or runtime inference added.

Run42 pelvis correction: −23.58→−1.98cm; worst downward correction over the
course26.87→7.14cm. Actual Run-policy Walk at2m/s (same phase/settings),105:
−23.24→−9.60cm; course maximum drop30→11.33cm at the user's400% accent.
With accent0, both remain below5cm reach correction. Peak120Hz pelvis velocity
change1.9→0.186/0.106m/s for Run/Walk. Whole-course ankle angle steps improve
10.51→8.71deg /7.27→6.71deg; knees do not worsen. Terrain shoe penetration
<0.0004mm, material pivot error<1e-8m. The movement remains kinematic.

`verify-descent-pelvis.cjs` passes28 checks using captured real Run-policy sources
and corrected NN continuations. `verify-descent.cjs` passes21 checks including
the prior turning descent and six byte-identical ascent/flat/uneven bank clips.
The prior assertion retaining every premature lower-tread contact is superseded;
reachable retained portions preserve their original world positions/rotations.
Prior turning53 shoe clearance is now4.98cm (old43.92cm), with ankle29.25cm lower;
its peak foot velocity change improves3.707→3.460m/s. Updated continuation fixture
uses the new current/history poses. NN handoffs remain73 Run /189 Walk /73 turn.
Post-handoff raw NN is not terrain-corrected: measured maximum shoe penetration
17.48/5.11/7.22mm respectively, not claimed zero. All continuation poses finite.
Evidence: `snapshots/descent-pelvis-verification.json`, `descent-verification.json`,
`pelvisdown-*` captures and `data/descent-pelvis-fixture.json.gz`.

Owned headless collider views cover both descents. Page-close keepalive escaped
the test's request interception and saved its final198 frame; restored original42
with a playback-only patch after verifying that exact QA value. Settings/camera
matched the original throughout. The offline visual harness now stubs persistence
itself to prevent unload writes. Existing user tabs were never controlled. User Refresh
loads the existing server's current client JS; no restart, Unreal/Bodyflip edit,
NN-weight change or push. Shared API unchanged; `surface.js` behavior unaffected.

## RunB comparison: command mismatch, not retained terrain rotation — October27

Saved current scene is Run20%, Direction Forward, down16/35cm, yaw200deg/s
over1.2–6m, paused162. That command retains5m/s and finishes at192deg; native
RunB uses3m/s. The running Model Viewer launch checkpoint
Saved/Diagnostics/RunCheckpoint20260930-135852/source_checkpoint.pt has exactly
the same SHA256 as the lab Run weights. Its saved collider dimensions also
match. The Model Viewer's live UI selection was not changed or inspected.

Current terrain handoff is76. At162 displayed feet are entirely the resumed
NN (foot rotation difference from that raw NN <0.000003deg). Removing terrain
IK from the complete5m/s turn still produces the toe-biased gait. Over120–300,
minimum sole tilt is17.46/14.47deg with stair history versus17.44/14.47 without
terrain; native RunB3m/s gets10.61/8.41deg. This is a cycle-range comparison,
not a claim that independent frame162 poses share gait phase. Changing to
Backward/zero yaw/Flat is the lab's native3m/s comparison. No motion, terrain,
speed setting or rotation compensation was retuned. Evidence:
snapshots/runb-comparison.json and its captured source/handoff/reference files.

Generating the previously uncached Backward graph exposed a loading-optimization
bug: disabling JIT execution optimization during trace/freeze could leave calls
to removed submodule forward methods, and the invalid graph had been saved
before validation. nn_worker.compiled_step now explicitly enables optimization
only while constructing/freezing, validates before atomic save, and rebuilds an
invalid disposable cache. Normal frozen execution still skips repeated profiling.
The repaired Backward graph was generated and used; worker source reloads through
normal service retirement. verify-graph-build.py exercises fresh build, cached
load and interrupted-cache recovery with a bounded Backward rollout, original
controller parity at every policy step, and exact poses/roots/pins across all
three paths (reference error0). No server restart, user-state writes, app control,
Unreal/model changes or push.

## Descending turn: remove stale tread height — October27

The later descending-pelvis correction above supersedes contact-acquisition and
measurement details in this earlier entry; the surplus-height fix remains active.

Current saved setup: Run82%, down16/35cm over12 steps, yaw200deg/s from1.2–6m,
step accent400, paused frame53. The left material pin ends at42; the next NN
plant is106. The planner interpolated the old tread's absolute height across
that whole unpinned interval while the root descended its ramp. At53 this added
51.75cm relative to the NN ankle, with43.92cm of actual shoe clearance. This was
already in the terrain target before final smoothing; NN inference was unchanged.

The existing constrained shoe-height fit previously handled rising swings only.
It now also handles falling ramp carriers, fitting surplus height back toward
the NN on that carrier while preserving full-shoe terrain constraints, horizontal
travel and material contact endpoints. It only removes excess; an already lower
valid path is not raised merely to match the NN. No frame/side-specific branch,
new setting or phase/timing change. At53 the ankle is29.25cm lower and actual
shoe clearance is3.47cm. All contact choices, release times, world pin points
and planted rotations are retained. The unnecessary height also amplified ankle
rotation: peak pre-handoff half-frame change98.39→18.20deg; peak foot velocity
change is essentially unchanged (difference0.00013m/s).

verify-descent.cjs passes21 checks with the exact captured NN and corrected
continuation, no live inference. Whole601-sample course, material contacts,
reach/collision, backward seeking and actual handoff at73 checked. New corrected
current/history poses feed the same Run policy. Existing post-handoff NN shoe
penetration is7.22mm versus7.23mm before; it is not claimed zero. Ascent, flat
and uneven Walk/Run bank clips remain byte-identical (six full clips); descent
bank cases also retain clearance/reach. Captured current-frame and43/63/73
collider views reviewed in one owned headless browser with state writes blocked.
Evidence: snapshots/descent-verification.json, down-regression.json and
down-before/after-*.png; reproducible fixture data/descent-turn-fixture.json.gz.

Shared API unchanged; surface.js/Bodyflip incline behavior is unaffected. Existing
user tabs/settings/camera/frame were not modified; user Refresh loads this
client-side change. No server restart, NN/model edits, Unreal work or push.

## New-phase preparation, not just Refresh — October27

The unchanged-Refresh improvement below did not address changing phase. Profiled
the actual phase workflow and removed repeated initialization work: the same
two settled starting poses are now retained as initialization data, with source,
weight, geometry, stride, codec and Torch-version invalidation. New commanded
motion still runs the complete recurrent policy and terrain-seeded continuation.
Frozen policy execution also skips redundant JIT profiling; graph validation
against the original eager implementation remains.

Two complete phase rollouts (.20/.31) match the original poses, roots and pin
values exactly. Real app phase changes to .47/.73 measured3212/4515ms, including
both newly inferred requests, terrain and draw; no completed-response cache hits.
The test intercepts all state writes and checks frame/renderer preservation.
Evidence: snapshots/phase-preparation-verification.json. This is an isolated
headless viewer measurement on the laptop, not a guarantee under other load.

Cold startup remains significant: the same run's initial document took22.24s;
the first NN request took17.71s although inference itself took1.91s. The existing
service retires its worker after30s, causing imports/model load on the next edit.
nn_service.py now retains its single sleeping worker for five minutes after use,
including cache-hit activity, then releases it. No polling, background inference,
GPU or extra workers. **This lifetime change is pending server restart**: the
earlier restart was rejected by automatic approval review with "blocked by policy".
No retry/bypass or restart was performed. Worker-side initialization/JIT changes
are already usable through the existing service after normal idle retirement.

verify-phase-startup.py covers initialization reuse, dependency invalidation,
interrupted-cache recovery, bounded retirement and stale-timer protection without
Torch/inference. An isolated ONNX experiment was rejected because full recurrent
motion diverged; it is not used or imported. Its dependencies are archived under
the ignored .nn-cache/rejected-runtime-trial. A terrain micro-optimization gave
no reliable improvement and was reverted. No motion solver, NN weights, shared
API, user scene, Unreal/Bodyflip code or layout changed. No push.

## Refresh avoids rebuilding an unchanged scene — October27

The earlier129ms figure measured only repeated NN HTTP requests, not Refresh.
The actual in-app browser full reload measured5087ms: cached NN requests217ms,
renderer727ms, terrain+handoff1983ms, drawing24ms, plus document/startup time.

Refresh now flushes edited state and checks the served runtime files with HEAD
requests (at most four connections). Their Last-Modified dates must precede
navigation. The baseline uses the server Date minus navigation elapsed time,
so a browser/server clock offset cannot silently retain old code. Missing or
ambiguous timestamps conservatively reload. There is no background polling.
Runtime scripts, HTML/CSS/icon/rig and lab NN/service sources are covered.
On unchanged sources, retain the actual model, NN data and WebGL renderer;
adopt saved edits from other tabs, solving again only for motion settings.
Changed sources still reload normally. This is reuse of a ready scene, not a
new gait approximation or a terrain/NN bypass.

Activated in the existing8890 tab. Measured unchanged Refresh54.3ms, with
playback continuing; activating the changed scripts took1866ms. Unseen NN
commands and real code reloads can still need preparation. No motion solver,
checkpoint, shared API or UI layout changes. A proposed server restart was
rejected by automatic review; the final implementation is client-only and
uses the existing server, which was not restarted. No Unreal/Bodyflip changes.

verify-refresh.cjs tests the actual app in one isolated headless browser with
all state writes intercepted: unchanged model/renderer identity, no NN calls,
frame/camera preservation, other-tab view edits without solving, motion edits
with solving, and code-change reload. verify-refresh-guards.cjs covers changed,
missing/ambiguous dates, failures and bounded concurrency. Persistence checks
also cover adopting a refreshed snapshot without publishing stale fields.
Evidence: snapshots/refresh-verification.json and refresh-live-verification.json.

## Run-only handoff restored — October27

User discarded the complete Walk-handoff experiment. Removed its temporary
Walk model, contact-wait detector, checkpoint switch, lower-inertia exception,
checkbox, NN WALK/RUN phase labels and dedicated test. Its compiled Walk graph
is deleted; archived checkpoints and prior diagnostic snapshots remain read-only.
Stale walkHandoff preferences are discarded by sanitize. The usual Run-policy
Walk and Run gait commands remain, with the original Run-only terrain handoff.
The restored motion requests/handoff match the pre-experiment behavior; the
subsequent Refresh-only changes are documented above. Current source and every
continuation pose match the captured pre-experiment Run output.

Loading audit: the removed experiment loaded an extra model and graph. The
policy graph cache also unnecessarily hashed the entire worker, so edits to
resume orchestration or diagnostics retraced the unchanged NN. It now hashes
PolicyStep, its native implementation dependencies, model provenance and Torch
version; eager-vs-traced output validation remains. The response cache still
invalidates whenever worker behavior changes. verify-graph-cache.py checks
five invalidation cases without inference or filesystem mutations.

The earlier API-only benchmark measured repeat source+handoff HTTP requests
at129ms total with no inference (74ms+54ms); this was not browser Refresh. A fully uncached request pair including initial graph
compilation took13.86s; cold imports/model loading and actual recurrent inference
are still required for unseen results. The exact NN responses are cached, but full reload also rebuilt graphics and
terrain motion; the subsequent correction above addresses that overhead. Preparation remains one CPU thread, no GPU,
with the existing30s idle worker retirement. No server restart, browser control,
Unreal/Bodyflip change, saved-state overwrite or push. Evidence:
snapshots/run-only-load-verification.json. Earlier hover investigation below
remains a diagnosis; the discarded Walk experiment did not resolve it.

## Run / turning hover investigation — October27

Current report61–94 uses Run phase38%, stairs16/35cm, yaw300deg/s over
1.2–6m, and step accent400. This is the `footik.js` stair path, not the
`surface.js` incline/flat setup in the knee investigation below.

At59.5 the right rolling pin releases on reach: hip-to-ankle83.55cm exceeds
leg reach81.67cm. Both procedural feet are SWING at61–72. Source shoe speed
prevents the stance heuristic from finding another plant; the clearance path
then bridges to the exit while the root continues up its authored ramp.
At73, `handoff.js` seeds the actual recurrent NN with the corrected history.
Its NN labels denote ownership, not pin state. Geometric contact returns
(left around82, right around91), so this is not continuous airborne motion
through94; it includes weak/sliding support.

For this exact command, initial source pin strengths are already weak and
material shoe points slide before terrain correction. In sampled62–94,
mean stronger-foot pin strength is1.22% at300deg/s versus24.54% at0deg/s.
The actual terrain-seeded continuation has maximum pin strength1.60% on
policy frames75–93 (about2.09% interpolated at94). These are continuous
projection strengths, not binary contact classifications. Both initial and
resumed inference match the original controller exactly; future-window
encoding differs by at most1.2e-7. This verifies the controller execution,
not a claim that every commanded motion is within the training distribution.

`nn_worker.py` now returns the existing `pins` channel for diagnosis, aligned
with output poses; a supplied seed has null strength because it was not
inferred. `directional_nn.py` trims this channel with the settled poses.
Initial152 and resumed115 poses/roots remain byte-identical after adding it.
No solver, model, tuning or user playback change was made for this report.
Do not force impossible pins or relax the speed threshold indiscriminately:
the stair planner amplifies a source-contact problem, and the NN after exit
needs to be evaluated separately. Evidence: snapshots/run38-hover-investigation.json
and its source/continuation pin captures.

## Vanilla gait fidelity — October27

The user's independent `Exports/WalkF_Rollout_20261027` exposed two errors.
The upper/pelvis decoder always ran a two-bone knee solve, even though this
lab leaves the NN pelvis unchanged. That moved knees by up to3.95cm while
the predicted hips and feet matched. `directional_nn.decode_policy_rows`
now composes the upper output without that solve, and uses the original
lower FK and lower-source geometry for the pelvis and both legs. Direction
generation and terrain-seeded continuation share this decoder. Policy weights,
recurrent inference, future root commands and NN pin projection are unchanged.

With the export's exact source, two history poses and root commands, all120
compared policy frames match within0.049mm; maximum rotation-matrix component
error0.000148. This is float32 recurrence/rebasing tolerance, not bit identity.
The live lab retains its Run source geometry and settled history; the fresh
WalkF export has different source geometry (~0.93mm at the knee) and phase.
Earlier raw-NN pop diagnoses did not exclude the extra knee solve and should
not be treated as proof of a network problem.

Terrain IK remains active at0 degrees; there is no flat-ground bypass. The
October27 follow-up fixes the causes in `surface.js`:

- Free-foot inertia follows the NN ankle carrier and smooths only the terrain
  residual. It no longer low-passes the gait using root velocity.
- The old94% reach target forced roughly40 degrees of knee bend. Roll/reach
  protection now respects the NN's legitimate extension; a free leg also keeps
  its natural reach allowance. Shoe collision and actual leg-length limits stay.
- Capture keeps the incoming shoe rotation rather than forcing a flat shoe and
  a shortened leg. The capture envelope is5mm plus the requested terrain delta,
  capped at the existing35mm: no large acquisition displacement is requested
  when the source pose already matches the ground. Heel/toe roll and yaw pivots
  remain active after capture.
- Physical shoe support is separate from the animation's hard-pin latch. A
  contact does not stop supporting the root merely because its lock is changing.
  Removing a platform preserves an existing material pin if another finite,
  coplanar surface contains that contact. Otherwise deletion still releases it.

On the supplied rollout, the unwanted knee change at60 falls from12.88 degrees
to0.711 (source0.711). In the current phase69 setup, left106 is9.02→1.99
(source1.89), and left225 is7.32→0.59 (source0.44). Across both full clips,
maximum60Hz knee-flex steps are8.32/8.82 versus input maxima7.91/7.91;
maximum extra step over the same input frame is3.82/3.68 degrees. Corrections
are not zero while a foot is pinned; this is not an exact-pose bypass.

Verification: `audit_model_viewer_rollout.py --matched-source` checks the decoder
independently. `verify-flat-rollout.cjs` checks active IK/root integration across
24 cases (12,984 solver frames), the full source-vs-corrected motion, contact
slip, reach and penetration. `verify-surface.mjs` passes697 checks across60
Walk/Run/direction/angle cases. Its gravity comparison now uses unsupported
motion: stable traction can correctly balance gravity in a supported case.
Backward checks cover the stance/release window rather than requiring a pin on
an old capture tick. Floor deletion (8 cases), root thrust (0/45/100%) and the
Bodyflip adapter (1,529 checks) pass. The solver API remains1.

Viewer8890 refreshed with the user's settings/camera retained. No server or
Unreal restart, model change or push. Prior exact-flat-pose receipts describe
the rejected bypass, not the current solver. Numerical reports are in snapshots.

## Shared with Bodyflip - October 26

`surface.js` now exports `createFeet`, `gaitIntent`, `bodyRotation`, `stableLeg`
and `apiVersion:1`. Foot IK's `prepare` uses that same routine. Six full pre/post
Walk/Run incline/wall clips remain byte-identical, including metrics/events.
Bodyflip imports these canonical source files through its own server on Refresh;
there is no copied solver or Foot IK UI/state/service dependency. Keep solver
changes here; coordinate API/dependency changes using [SHARED_API.md](SHARED_API.md).
Bodyflip retains its own capsule and authored jump feet. This extraction changes
no Foot IK scene, saved tuning or running server. Bodyflip desktop activation is
pending a server restart: automatic approval rejected it ("blocked by policy").
The isolated integration server/browser were verified and closed.


## Planted yaw and accepted ankle fix - October26

The accepted toe-off pitch correction remains: measure signed pitch in the
shoe forward/up plane and correct about its own lateral axis. Old ankle and
its comparison branch are removed; saved oldAnkle fields are discarded.

The new **Foot yaw degrees** option is appended at the bottom of More options,
default45. Terrain contacts retain their heading inside a soft limit, then
rotate around the support normal through the actual heel/toe material pivot.
Within2-8degrees of flat, the yaw pivot transfers smoothly toward the ground-
projected sole centre (a contact-patch pivot, exact sole centre when flat).
The rigid yaw transform carries subsequent roll/pivot transfers; it never rotates
about the ankle or rotates the knee pole with the shoe. Actual NN thigh/pole
continues guiding the leg. PureNN approach/exit/flat frames remain unmodified.

This mirrors the original NN's contact compensation, not a supposed NN yaw cap:
train_simple_ae_controller.py:5646 integrates rotation about lowest foot/toe OBB
supports, while:6670 preserves predicted rotation and adjusts ankle position.
The original pinning path has no body-relative yaw limit. Native equivalent:
ProphecyNNLocomotionManager.cpp:1195/4112; see Docs/FootPinningDebug.md.

Finite stair yaw retains4cm riser room for departure. The initial6mm numerical
margin was insufficient: a shoe corner crossed the next riser just after release
and forced a sharp lift. The larger reserve lets blocked turns release in time.
If further turning is blocked past the limit, the contact releases into the
existing clearance swing rather than twisting through a riser. Turned departures
keep their forward swing path while using bounded shoe-aware height clearance,
instead of amplifying an endpoint obstacle into a whole-swing arc. The first
version accidentally skipped forward travel with that arc, leaving the foot
following the NN's remaining stance timing. Initial airborne rotation waits for
actual clearance. The
last trajectory smoothing now fades with IK influence, eliminating the small
straight-knee bend jump at the start of IK without changing material pins.

Current Walk phase91/yaw300/start1.2m: last right contact65.5 keeps16.04degrees
toe-down and43.42degrees body-relative yaw. Forward travel72-82 is35.36cm
(regressed version9.96cm); speed82 is2.575m/s against root2m/s. Early vertical
peak1.852m/s replaces3.649m/s. FullIK pole step1.397degrees/120Hz,
pole acceleration0.243degrees/tick squared, maximum shoe step8.001degrees.
Max penetration0.000113mm, material pin error below1e-7m.211 existing motion,
6 prior ankle and101 surface endpoint checks pass. Twelve zero-yaw shared
surface golden clips remain byte-identical. verify-planted-yaw.mjs adds262
passing checks across14 actualNN clips and16 synthetic pivot cases, with
independent diagnostics in verify-planted-yaw-audit.mjs. The11 checks in
verify-planted-yaw-travel.mjs cover forward speed, early lift, grounded toe-off,
whole-clip joints, reach and clearance; contact invariants alone missed the stall.

Shared surface.createFeet uses the same K.createPinYaw helper; API version1 and
host adapter inputs are unchanged. Bodyflip receives it on Refresh once its
existing shared integration is active. Neither server nor Unreal was restarted.
Browser reviewed the entire0-299 sequence and the64-90 release closely;
reported82 and the camera restored. No additional control was added.

## Root yaw and active desktop route - October 26

The desktop shortcut and browser use http://127.0.0.1:8890/ (API6, save
protocol2). The active save is `snapshots/overnight-state.json`; launch.ps1
passes that same path, and /health reports it. October27 startup succeeded with
normal hidden pythonw. Only Foot IK was restarted; other labs/editor untouched.

On reopening October27, that file still held the original45-degree preview
configuration. The last observed user setup was recovered:90-degree wall,
Walk phase69%, yaw300 degrees/s from1.2 to6m, Step accent400%, ghost on,
trim0-299 and paused202. Current camera retained; the previous camera was not
recoverable. The exact historical overwrite/missed save could not be established.
Pre-recovery and recovered copies are in snapshots/*wall-state*-20261027.json.

Autosave now sends only changed settings/camera/playback fields, before waiting
for motion preparation. Opening an idle tab does not save. Hidden/closing tabs
flush pending edits with keepalive; Refresh awaits the save. Server merges under
its lock, atomically writes and flushes the file, and ignores out-of-order client
requests. A stale tab changing its camera cannot restore old terrain settings.
Old full-scene save requests are rejected with a Refresh message. New UI and
launcher check protocol compatibility to avoid writing to an older server.
verify-persistence.cjs and verify_persistence.py cover untouched tabs, concurrent
fields, delayed replies/requests, retries, close flush and durable reload.
Browser verified an edited slope through immediate reload and restoration90
through app Refresh, retaining phase/yaw/frame. No motion solver changes.

Root yaw is now in More options on **every terrain**. The earlier output-spin
implementation and its geometric-only validation are superseded. The lab sends
actual previous/current/eight future root orientations into Run181751 and
Upper82500, encodes each history pose in its own carrier, and rebases every
prediction into the next carrier. The original Run continuous-sigmoid pin
projection remains active. Terrain exit feeds the corrected world-space history
and future turns directly into the same policy, without de-yaw/re-yaw.

**Walk uses the Run checkpoint** at the recorded walking command speeds:
forward2, backward1.5, lateral1.8m/s. Run retains5/3/3.5m/s. Phase selects the
starting recurrent gait state after settling at command speed. The lab requests
this through the existing /resume route, requiring no server restart. The old
Walk banks remain historical fixtures and shared consumer inputs; the Foot IK
UI no longer selects that checkpoint.

**Start m / Stop m** sit directly below Root yaw. Start defaults0; blank Stop
means unlimited. They gate angular velocity by horizontal root-course distance
from the visible start, independent of gait phase/playback speed. After Stop,
the attained heading is retained. The eight future root samples anticipate both
boundaries. Angular velocity stays degrees/second, so a faster traversal spends
less time turning inside the same distance span. The root metre counter below
F n /300 uses that same command path, with deterministic seeking and looping.
It occupies the existing76px readout width. On the gravity incline prototype,
this is commanded course distance, not the gravity mass-point's 3D arc length.

Validation: verify_nn_root_window.py compares actual recurrent inference with
the original controller, plus all root features with the original training
encoder, and verifies active learned pin projection and future anticipation.
verify-nn-root-window.mjs covers unchanged shared baselines, exact NN on flat,
material pins, shoe clearance/reach, all terrain modes and actual turning
handoffs. The older verify-root-yaw entry points now invoke this replacement.
verify_yaw_distance.py checks Walk/Run gates at3m and8m through actual inference;
yaw-distance-integration.json records matching counter and handoff-window checks.
The original211 procedural regressions and12 shared-surface zero-yaw clips pass.
The Bodyflip shared API is unchanged. No Unreal or other lab/server mutations.

## Directional gait and gravity surfaces - October 25-26

Verified isolated preview: http://127.0.0.1:8890/ (apiVersion6), using
`snapshots/overnight-state.json`. Main8878 and earlier8879 remain running older
server code. Automatic approval review blocked the scoped restart despite the
user's explicit FootIK-only approval ("blocked by policy"); no alternative
termination was attempted. The desktop launcher still points to8878 and is NOT
upgraded. Main saved Run/phase21/frame73/settings/camera remain unchanged.

Direction is appended below the existing controls. Backward/Left/Right use their
own original omni NN seeds and drawn-context files, validated by SHA256 in
`directional-sources.json`; they are not rotated forward-walk recordings.
`directional_nn.py` runs the existing lower/upper autoregressive policies with a
matching warmup and transforms their travel onto the course. Facing remains
backward or lateral. Native speeds: backward Walk1.5/Run3.0m/s; lateral
Walk1.8/Run3.5m/s. Phase changes only the starting gait pose. No retraining,
model edits, Unreal interaction or other-lab worker changes.

Terrain recovery uses travel direction while retaining anatomical facing. Reach
relief searches heel- and toe-side roll and takes the smallest sufficient change.
Backward/lateral early departure uses the roll needed at actual release.
Old toe-off limits fade into the next contact or NN return; landing follows its
support orientation. Complete-shoe clearance bounds final quaternion blending.
Alternate-phase review also caught a lateral uneven-terrain lift: final smoothing
had allowed lateral drift into a higher neighbour, forcing a sudden vertical
correction. Both horizontal axes now remain inside the clear corridor, and
departure anticipates intervening obstacles while retaining grounded heel/toe
roll. RunLeft/phase49 sample50.5 rise10.16->0.91cm; speed12.59->3.49m/s.
The accepted forward Walk/Run phase21 sequences remain byte-identical to before
this final release/corridor fix.

After terrain exit, directional handoff transforms BOTH corrected history poses
and root commands into policy coordinates, runs the original NN, and transforms
its result back. Exact first pose; no cached-phase catch-up. One serialized CPU
worker, one Torch thread, bounded5s requests/cache and30s idle retirement.
The newest service source also checks immutable source files before cached
responses and protects retirement from obsolete timers. Those two safeguards
have mock verification; running8890 predates them and needs restart to load them.
No inference worker remained running at final read-only process inspection.

The separate `surface.js` prototype is selected with Terrain: Incline / wall.
Only three controls are appended at the bottom of More options: Incline0-90deg,
Toward/Parallel approach and Upright bias. Toward starts on flat entry; Parallel
starts on the incline and travels along its contour. Stair controls are disabled
here while retaining values. Header: Gravity root; viewport: SUPPORT/FLIGHT/FALL.
This is a simulated mass-point/capsule root with kinematic NN limbs/IK, NOT a
full Jolt ragdoll or a trained wall-running policy.

Root motion integrates gravity plus bounded spring/traction at120Hz. Collision
removes inward velocity and prevents root tunnelling; initial clearance also
holds at the full-upright wall endpoint. Material foot pins permit heel/toe roll
in either direction with a shared300deg/s budget. Reach/ankle limits release
impossible pins. Free-leg minimum hip distance avoids folded singularities while
allowing deeper native NN folds; transported knee poles recover toward the NN
without moving pinned targets. Wall support has no elapsed-time cutoff: valid
contacts, reach/ankle/collision limits, bounded traction and gravity determine
whether it climbs or falls. Ground contact can drive again without a reset.
Upright bias controls body orientation independently of surface alignment.
Preparation is cached; playback and scrubbing perform no inference. This remains
a lab prototype, not live Unreal integration or a full-body landing controller.

Final verification:
- 703 grouped directional checks:24 default-phase clips,24 alternate-phase clips
  and10 focused release checks. Complete5s sequences sampled at120Hz, including
  flat, stairs up/down and uneven ground. Flat output matches source NN exactly.
- 20 targeted forward checks pass after the final fix; prior263 baseline checks
  and full-sequence identity evidence are recorded separately to avoid double
  counting. Backward boundary rotations reduced from27-44 to5-12deg/sample.
- 696 surface checks/60 cases,101 endpoint checks/16 cases and an independent
  32-case shoe-FACE clipping review pass against final surface source.
  Worst reviewed shoe penetration0.07671mm, material pin drift at floating-point
  precision; gravity, collision and root integration checked.
- 71 actual HTTP inference/history/phase checks plus6 mocked service guards.
  Original-controller reference error0; both history poses affect continuation.
- Actual-app review covered backward87-90 and230-231, lateral contacts, the
  RunLeft/phase49 uneven50-56 regression,45deg toward/parallel,90deg contacts/fall,
  and full-upright wall71-73. No browser warnings/errors in final preview.

Receipts: `direction-suite-status.json`, `surface-verification.json`,
`surface-endpoint-verification.json`, `surface-independent-review.json`,
`directional-http-verification.json`, `directional-service-guards-verification.json`.
CoreSHA88abc20955df97a52dd2db492e3cd8e1dbc7f69e46c18e6d86ee3dd4339d32e2;
surfaceSHA209c1782ecb1b21934b59263f23cf935826b917b72da73c07cb127f6f18869e2.
Visual review does not establish that every configuration is natural.

`motion-audit.js` measures source-relative joints, shoe clearance, material pins
and root/pelvis motion. `motion-audit.mjs` creates interactive SVG reports with
two views and foot trails; orange corrected, purple NN. Six current reports:
`snapshots/direction-audit-{walk|run}-{backward|left|right}.html`.
These audit the procedural core; actual NN handoff has separate checks.

Reproduction uses existing Stepper Python/Torch and frozen models:
`verify-directional-nn.py` generates the six default fixtures with one CPU thread.
`generate-direction-phases.py --url http://127.0.0.1:8890` generates missing
alternate fixtures serially; `--check-only` validates offline (six retained,
zero regenerated at handoff). Run Node scripts `verify-directions.mjs`,
`verify-direction-phases.mjs`, `verify-direction-release.mjs`,
`verify-surface.mjs` and `verify-surface-endpoints.mjs` serially.
Caches are ignored. No GPU, training or permanent inference worker.

Preview is left paused120, Walk/Forward/phase21,45deg Toward,Upright55%,Side view.
Proof: `snapshots/directional-surface-preview.png`; lateral before/after:
`snapshots/lateral-lift-before-51.png`, `snapshots/lateral-lift-after-51.png`.

References: [Rapier character controller](https://rapier.rs/docs/user_guides/javascript/character_controller/),
[Box2D character movement](https://box2d.org/documentation3d/md_character.html).
The bounded spring/traction is this lab's implementation, not either engine.
[Backward versus forward walking study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10223441/)
informed contact review; backward gait is not forced through forward heel-off.
Native poses were compared with accepted Unreal omni recordings in
`directional-baseline-verification.json`.

No push requested. An early export mistakenly created12 duplicate reports under
`Documents/Unreal%20Projects/Prophecy/Labs/FootIKLab/snapshots`; path fixed and
intended reports current. Automatic review blocked scoped duplicate cleanup;
no alternative deletion attempted.

## Actual terrain-to-NN continuation - October 25

This supersedes the cached-gait exit described below. The terrain approach and
foot placement remain the accepted procedural prototype. After the course, the
lab can now run the original frozen lower AND upper NN from the actual corrected
state, instead of waiting for an unrelated cached gait to catch up.

`handoff.js` checks the current root, retained contacts and all rendered shoe
corners at 60Hz. When the root has passed the course, both contacts have released
and both shoes clear the final plane by 5mm, it sends the corrected current pose
and the pose exactly 1/30s earlier to `/resume`. Current Run/phase21:73, seeded
from71/73. Walk/phase21:190. All preceding frames and the exact handoff pose are
unchanged. Constant commanded root speed continues on the final level.

`nn_worker.py` reuses Bodyflip's frozen model loader/codecs READ-ONLY, with the
original autoregressive lower/upper controller at30Hz. No phase lookup or old
bank target participates after this handoff. Local pose-velocity differences
fade over100ms into the new NN output, preserving the inferred bone lengths.
Both foot labels become NN; the ghost shows this newly inferred source. Inference
is causal, but its bounded continuation is computed during preparation for cheap,
deterministic playback/scrubbing. This remains a kinematic lab, not an Unreal
runtime integration or a live terrain-collision controller. The initial approach
still comes from the frozen NN phase bank and existing offline terrain planner.

`nn_service.py` owns one serialized, one-thread CPU worker; no CUDA or training.
It starts only for a new seed, retires after30s idle, and caches at most16 exact
seed/history responses in ignored `.nn-cache/`. Compiled policy graphs are also
FootIK-local. Dependencies remain the Stepper Python/Torch runtime, Bodyflip's
`locomotion.py`, frozen models/provenance and their existing codec dependencies.
No files, workers or settings in Bodyflip or Unreal were changed.

Verification:28 new checks in `verify-handoff.mjs` plus346 unchanged procedural
regression checks. Traced inference matches original controller with reference
error0. Perturbing only previous-pose history changes the first NN prediction;
repeat requests reproduce exactly. Prefix/seed preservation, constant root,
transition continuity, riser clearance, reverse seek, cache, cancellation and
failure reporting pass. Run/Walk max orientation step7.72/8.46deg per120Hz.
Inferred bone geometry is preserved to floating-point precision: the raw walk
NN itself varies calf length by2.67mm, so the test compares against each inferred
frame rather than falsely assuming the source decoder has a rigid length.
NN sole-box penetration Run9.37mm/Walk4.82mm is within the uncorrected flat NN
baseline9.38mm/5.55mm; the handoff does not impose a new flat-ground pin.
Receipts: `handoff-verification.json`, `handoff-suite-status.json`.

Activation: preview http://127.0.0.1:8879/ has apiVersion5 and was visually checked
at73/80/90, then restored paused73 with saved camera/settings. The worker retired
and only the small preview server remains. Main8878 is still the OLD apiVersion4
server (PID996 at this writing). The user explicitly approved a FootIK-only
restart, but automatic approval review again rejected the scoped command with
only "blocked by policy". No alternate process termination was attempted.
Main8878 needs a manual server restart before refreshing the app; the desktop
launcher reuses a running server, so simply reopening its icon will not upgrade
that existing process. Preview8879 is retained as the working deliverable.
No push was requested for this change.

## Forward recovery through the running exit - October 25

Run/phase21 left66-80 inherited the source's backward-folding airborne path.
The pelvis-local recovery pass could not bridge to the old spatial exit: that
endpoint was still behind the release point, so its positive-progress check
skipped the correction entirely.

For that case, search later in the SAME source swing for a forward-moving pose
with a monotone Hermite bridge and compatible endpoint velocity. Retain the
recovery per foot until it rejoins the NN, independent of the spatial terrain
fade. Preserve the other leg's exact NN exit. Final XYZ smoothing and whole-shoe
clearance/reach remain active; the forward smoothing corridor cannot cross a
riser by demanding an unnecessary height increase. This is cached procedural
foot recovery, not NN inference or a recurrent-state refresh.

Current case retains toe roll through66, moves forward in pelvis space from
about70 after the initial toe/riser clearance, and rejoins the NN at94.70-80
pelvis-local progress -21.73 ->+20.48cm. Incoming/outgoing join velocity difference
0.361m/s; maximum foot rotation step8.35deg/120Hz. All earlier grounded motion,
actual contacts/releases, the right leg and pelvis rhythm are unchanged.

346 regression checks pass plus8 Walk/Run phase/course spot checks. The prior
run-ankle test's exact airborne path and SWING/NN labels were intentionally
replaced with unchanged right-leg/pelvis and actual support/release assertions;
its ankle/collision/reach limits are unchanged. New12-check run-travel regression
covers pelvis-local progress, pins, NN join velocity, full-shoe clearance, reach
and reverse seek. Baseline: data/run-travel-before.json. Receipts:
run-travel-verification.json / run-travel-suite-status.json.
Browser refreshed/checked66,70,78 and restored78/settings/camera. Desktop Refresh
needed. No server restart, Unreal, source NN, UI or push changes.

## Running ankle handoff - October 25

Run/phase21 frame81 retained the old toe-off world pitch while the calf folded,
putting the ankle104.49deg from its NN-relative articulation. The spatial exit
fade then released it at83 with33.85deg rotation in one120Hz sample.

Final swings with no next retained terrain contact now retire that cap over
20-40% of the source gait cycle, and keep the resulting calf-relative NN target
through the terrain exit. Whole-shoe clearance still bounds the rotation. Source
periodSeconds is carried through decode; no gait, root or history modifications.
Material heel/toe pins, accepted ankle paths, pelvis rhythm and support timing
are identical. No controls or per-playback work added.

81 ankle error104.49 ->0.21deg;75-85 peak foot step33.85 ->11.12deg at120Hz.
288 targeted checks pass (211 main +77 focused), without relaxed assertions.
Receipts: run-ankle-verification.json / run-ankle-suite-status.json; baseline:
data/run-ankle-before.json. Browser refreshed and checked81/83, restored81 with
camera/settings intact. Desktop Refresh needed; no server restart, Unreal or push.

## Final level-ground toe-off follows NN - October 25

At current191 the left shoe was held near41deg toe-down although the NN reached
79deg and its full shoe cleared the surface. The anti-airborne-roll limiter was
being retained across the final same-height departure, and the natural-ankle
blend also faded back toward that held orientation at the exit.

Keep the limiter on earlier terrain transfers; clear it after support on the
final stair level. Carry the actual release rotation offset onto the moving
calf-relative NN articulation, easing the offset out over120ms. Clearance still
bounds the whole foot/toe geometry. Only the tail of that last stance opts out
of the redundant rotation fade, so its preceding landing is unchanged.

191 pitch79.78deg vs NN79.35; full quaternion error38.55 ->4.55deg; sole gap2.65cm.
187.5 and all earlier left orientations are unchanged, as are ankle paths,
pelvis motion, and contact timing.188-200 peak foot step6.31deg at120Hz.
248 checks passed in the final targeted run:211 main,9 ankle,9 grounded toe-off,
11 pelvis transfer,8 level-exit. No assertions relaxed. Receipts:
level-exit-verification.json / level-exit-suite-status.json. Current-case baseline:
data/level-exit-before.json. Browser refreshed and left at191 with camera,
settings and ghost preserved. Desktop Refresh needed; no server restart,
Unreal, source NN, UI or push changes.

## Adjustable pelvis accent - October 26

Step accent % (0-400) is appended at the bottom of More options.100 is the exact
previous rhythm;0 removes only the stair weight-transfer accent;200 doubles
its target before the existing smoothing and leg-reach limits. It affects
stairs up/down, not flat/uneven or the shared incline solver. The control is
disabled for Incline/wall. Current Walk36/yaw300 setting is200, increasing extra
loading from2.107 to4.214cm. Root trajectory, accepted ankle positions, material
pin rotations and contact timing are unchanged. Free-foot articulation follows
the newly bent calf, and terrain-exit NN continuation is still seeded normally.

Verified original100 output equality and0/100/150/200/300/400 range, exact foot paths,
contact timing, pin rotations, clearance/reach and bounded pelvis speed and
acceleration in verify-step-accent.cjs.211 main and11 departure regressions pass.
Walk/Run ascent/descent geometry spot checks also pass. No NN weight/runtime,
shared surface API, server or other-lab changes.

## Pelvis weight-transfer rhythm - October 25

Approved foot-motion checkpoint pushed as3bc2cde7304da2bf67491283e6ba9efbce0592e0
on codex/standalone-sim; remote SHA and recovery manifest verified. The pelvis
experiment below is subsequent local work, not part of that approved checkpoint.

Root still follows the same ramp. Actual accepted foot plants define successive
body-height transfers, with smooth loading/pull-up/continuation rather than
constant diagonal ascent. Quintic height goals are fitted with80ms curvature
smoothing, bounded by both legs' CURRENT extension and the existing Pelvis cm
limit. Loading may bend the knees; the body rise cannot straighten them farther
than the accepted gait. This naturally limits the accent where reach is tight.
NN body bob is retained. Flat/uneven terrain behavior and source banks unchanged.

The correction runs after completed ankle trajectories and before final ankle
rotation/leg IK. World ankle paths and all plant/release timings are identical;
material heel/toe rotations remain fixed. Free feet still follow their corrected
calf articulation, with the existing whole-shoe clearance/landing limits. No new
controls, per-playback solve or NN feedback. Current phase21/Clearance1 peaks at
3.37cm extra loading, maximum added vertical speed0.240m/s and acceleration
3.55m/s2. This is a restrained pelvis accent, not a replacement stair gait.

318 checks pass without relaxing existing assertions:211 main,96 prior focused,
and11 pelvis-transfer checks. These verify unchanged root/ankle paths/pin timing,
no extra leg extension, smooth body speed, exact flat NN, clearance and reverse
seeking. Receipts: pelvis-transfer-verification.json and
pelvis-transfer-suite-status.json. Current baseline: data/pelvis-transfer-before.json.
Browser refreshed, inspected106/114 and restored the user's paused6/camera/settings.
Desktop app needs Refresh. No server restart, Unreal changes or new push.

Reference for the weight-acceptance/pull-up/forward-continuation phases:
[Stair-ascent kinematics study](https://pmc.ncbi.nlm.nih.gov/articles/PMC7859378/).
The curve is our constrained procedural approximation, not captured reference data.

## Gentler last-stair toe-off - October 25

For a higher-step departure that returns to the NN gait rather than another
retained contact, cap the grounded toe roll at35deg instead of45deg. This avoids
an excessive toe-down shoe demanding a sharp vertical clearance correction.
Retained-contact transfers keep45deg; early release timing is unchanged.

Current phase21/Clearance1cm right155-161 peak upward speed4.030 ->3.332m/s
(17% lower), peak120Hz velocity change1.629 ->1.446m/s. Grounded material toe
pivot stays fixed, release remains155, forward/up travel stays continuous, and
right89-102 is identical. Existing299 checks plus8 focused checks pass.
Receipt: exit-toeoff-verification.json; baseline: data/exit-toeoff-before.json.
Browser refreshed and inspected154/157, restored155 with settings/camera intact.
No new controls, server restart, Unreal changes or push.

## Earlier departure with grounded heel-to-toe - October 25

Supersedes the retained late toe-off timing and short height-ceiling handoff.
Higher-tread swings again prepare up to50ms early (minimum120ms stance).
Before removing the final stance frames, author the late ground roll over up to
200ms using the existing material heel/toe pivot solver. The monotone cubic
starts gently and carries nonzero rolling velocity into release. Aim for up to
45deg toe-down, rather than copying a nearly vertical late reach-compensation
pose into the earlier stance. Reject retiming if full shoe/surface validity fails.
Recompute foot/toe orientation, actual sole offsets and reach limits at each
retimed sample. Root and source NN timing are unchanged. Airborne rotation still
cannot add missing downward push-off after contact is gone.

The smoothing-height ceiling now enters over200ms rather than80ms after toe-off;
the hard earlier entry had produced abrupt braking immediately after clearance.
Tradeoff: phase21/default4cm clearance frame161 gap18.92cm instead of14.02cm,
still below the older23.22cm. This deliberately retains more room for smooth
recovery. No new UI controls, runtime filters or per-playback work.

Current phase21/Clearance1cm right toe finishes45deg roll on ground at89 and
releases89.5. Reported88-102 peak upward velocity5.54 ->2.93m/s (47% lower);
peak120Hz velocity change3.11 ->0.84m/s (73% lower), continuous forward/up90-100.
299 checks pass, including unchanged211 main checks: prior84-92 acceleration
failure is now resolved. verify-toe-release now tests the explicitly requested
EARLY grounded roll rather than retaining contact to71.5. Ankle NN-error metric
is evaluated after200ms authored toe-off handoff (6.91deg; whole-swing mean10.75),
with full-contact/angle/collision checks retained. Height tests reflect the stated
smoothness/height tradeoff, not the old15cm pose bound. No collision, reach,
knee/velocity or flat-NN assertions weakened. Receipt:
grounded-departure-suite-status.json; current-case baseline: data/departure-before.json.

Browser inspected89/92 and restored92/settings/camera/ghost. Desktop Refresh
needed. No server restart, Unreal, training, other-lab edits or push.

## Limit smoothing surplus - October 25

The final minimum-curvature fit had no useful upper height limit besides leg
reach. At saved phase21 right161 it added15.1cm over an already raised arc.
Add a height ceiling based on the greater of the pre-fit trajectory and NN
height, plus the existing Clearance margin, respecting shoe collision and reach.
Apply it gradually after toe-off (80ms) and as excess NN-relative lift develops;
retain the unconstrained first airborne sample to preserve outgoing velocity.
This is an internal fit constraint, not a new control or a hard sole-gap cap.
It leaves raw NN lift intact and avoids abruptly braking a foot immediately
behind a riser. No output low-pass layer, pin/root change or playback overhead.

Phase21 right161 sole gap23.22 ->14.02cm; extra ankle height over NN20.41 ->11.28cm.
Forward/upward motion159-167 remains continuous. The existing release-window
velocity kick6.80m/s is unchanged, NOT fixed by this height correction. Earlier
84-92 lift-acceleration regression also remains.87 focused checks pass; broader
suite210/211, same single existing failure and no assertion relaxation. New
verify-height-budget.mjs covers surplus, forward/up motion, release velocity,
collision, reach and exact flat NN. Preparation~335ms, cached playback retained.
Receipts: height-budget-verification.json, height-budget-suite-status.json;
baseline: data/height-budget-before.json. Older all-green receipts are historical.

Browser refreshed and inspected161, then restored latest157/settings/camera/ghost.
Desktop Refresh needed. No UI changes, Unreal/server work, NN changes or push.

## Retained toe roll and airborne rotation - October 25

Removed the 50ms higher-step early-release rule. Saved phase21 left toe now
retains its exact material pin through71.5 (22.39deg down at68,52.29deg down at
71.5), then releases at72. The old rule released at69 with only25.55deg roll.
Calf-relative airborne articulation could subsequently add another downward
rotation to nearly90deg. Both planned swing orientation and the calf-relative
candidate now respect the actual release pitch, rotating foot/toe together.
Natural articulation above that limit, landing preparation and shoe collision
checks remain active. Flat NN gait, root, UI and servers are unchanged.

Eight new retained-contact/air-rotation regressions pass. Existing focused suites
pass79 checks total including these8. The broader suite has210/211 passing:
its 84-92 left swing lift-acceleration bound fails in the default walk fixture.
Removing the premature release restores that known sharp liftoff acceleration;
this is NOT an all-green or fully smooth release claim. The assertion was not
weakened. Full collision/reach/material-pin/knee/flat-NN checks still pass across
the eight gait/terrain cases. Current phase21 backward72 snap remains absent;
whole-course peak left velocity increment2.24m/s versus old6.63m/s, but higher
than the early-release version's0.94m/s. Preparation~0.35s, cached playback.
Receipts: toe-release-verification.json and toe-release-suite-status.json;
prior verification.json is historical, not a passing receipt for this revision.

Browser refreshed, inspected71 and77, restored69, phase21, camera and NN ghost.
Desktop Refresh needed. No Unreal, training, other-lab changes or push.

## Swing continuity and actual sole support - October 25

Supersedes the ankle-ray support choice and the early root-based exit handoff.
Phase21 left68 had no pin at all: its ankle was behind the first riser, so the
entry surface was selected and treated as uncorrected NN stance even though the
shoe was on the stair. Terrain landing now selects support from the main sole
box centre. The same correction puts the final stance on step11 rather than
step10.68 now has actual toe rolling (-22.39deg) and96.53% leg reach, versus the
old unpinned98.79%; exact material contact remains fixed.

Higher-tread swings reserve up to50ms at the end of stance for lift preparation
(minimum120ms retained stance). This avoids trying to gain a riser's clearance
only after flat-ground NN toe-off. Level/down transitions retain source timing.
Remove the six-frame return to NN triggered by root arrival on the exit: finish
through the existing complete-shoe spatial fade instead.175-177 now retains its
valid last-tread toe contact; the subsequent188-193 swing advances continuously.

A final constrained trajectory fit follows every positional planning pass. It
smooths all three axes over each unpinned terrain interval, with exact pinned/NN
boundary samples, a2.5cm horizontal corridor, whole-shoe floor constraints and
analytic leg-reach bounds. The existing banded solver now supports upper bounds.
This is cached trajectory smoothing, not a playback low-pass or live physics.
A smooth toe-up limit during landing preparation also prevents calf-relative
articulation from reintroducing the pre-landing dorsiflexion rebound.

Reported72 forward speed -4.84 ->+1.92m/s. Whole-course phase21 left-foot peak
120Hz velocity increment6.63 ->0.94m/s (86% reduction).175-177 vertical velocity
stays below0.5m/s on the retained pin, instead of the old6.89m/s forced lift.
Preparation~0.37s, no new playback work/UI/processes.282 checks pass, including12
in verify-inertia.mjs. Baseline: data/swing-inertia-before.json; receipt:
inertia-verification.json. Eight walk/run terrain cases, all stored flat phases,
full-shoe clearance, reach, material pins, knee poles, ankle rotation and the
reported windows are covered. Old exact-frame assertions now distinguish rolling
contact from flight, allow at most50ms earlier upward toe-off, and test NN handoff
after actual foot recovery. Support may change by one tread; lift budget accounts
for its height, while independent collision/clearance checks remain enforced.

Browser visually inspected68/72/176, restored latest paused72 with phase21,
camera/ghost/options unchanged. Desktop Refresh needed. Journal updated; source
NN banks/recurrence, root ramp, Unreal, Bodyflip and servers untouched. No push.

## Whole-shoe riser clearance - October 25

Current phase21 left41 intersected the first riser by about7cm despite the old
corner-only collision metric reporting zero. A shoe edge crossed the stair face
below its top while the two endpoints lay on different treads. floorFor now
clips each rendered foot/toe box face against overlapping tread footprints and
uses the lowest intersecting point. Interior boxes use a bounds/min-height fast
path; only boundary overlaps need clipping. Shared by planning, reach projection,
rotation acceptance and diagnostics. No extra playback work or new controls.

The same verification exposed a pre-existing late lift snap around175.5 in this
phase. Extend the existing clearance smoothing to swings ending at the exact NN
exit as well as a planted endpoint. Current whole-course peak limb displacement
per120Hz sample is7.92cm (before9.36cm), peak angle10.56deg. Pins/root/source banks
remain unchanged; exact NN on the level approach/exit. No recurrent inference.

270 checks pass, including9 new checks in verify-riser.mjs. Independent dense
sampling of the six shoe faces detects6.89cm in the retained before fixture and
zero at41 after correction; whole-course corrected maximum intrusion is numerical
noise (<0.001mm). Existing release fixture allows <1cm lift difference for the
new edge clearance, instead of requiring identical old corner-only heights.
The crossing-gap test now checks a3mm actual edge margin, not5mm at an endpoint.
Current preparation about0.37s in Node; all trajectory work remains cached.

Browser refreshed/visually checked41, then restored188, phase21, ghost/camera and
collapsed options. Desktop Refresh needed. No server/Unreal/other-lab changes.
Receipt: riser-verification.json; baseline: data/first-riser-before.json.

## Pelvis-relative release recovery - October 25

Supersedes the world-forward criterion below. Foot speed can be positive in world
space while it still drags backwards relative to the advancing/rotating pelvis.
Release detection, the Hermite recovery and the constrained smooth fit now use
pelvis-local forward (rig local -Y), including pelvis orientation and correction.
The shoe's world collision limits are converted into that same local coordinate;
convert the result back to world for reach/IK. Joining the gait also uses local
position/velocity. Desired initial relative speed is a quarter of root speed,
limited by the relative travel available in the remaining swing.

Saved phase49 right137-147 pelvis-local forward travel4.99 ->15.21cm. Through
139-150 every120Hz sample advances locally (>0.44m/s), with no143-147 speed dip
(all >1m/s). There is still1.27mm retreat137-138 while the shoe clears the riser;
this is not a claim of zero backward motion throughout the initial toe extraction.
Clearance, current pins/root and source NN banks are retained; no extra vertical
lift or live NN recurrence/history changes. All261 checks pass: previous257 plus
four true pelvis-local regressions in `verify-pelvis-release.mjs`. Baseline and
receipt: `data/pelvis-release-before.json`, `pelvis-release-verification.json`.
Default preparation253ms in Node; unchanged cached playback cost and UI.
Browser visually compared147 before/after, then restored current150 with original
camera/settings/options. Desktop needs Refresh. No Unreal/other-lab/server changes.

## Forward recovery after early pin release - October 25

At phase49 right134.5 and left167.5, reach released the foot before the NN left
stance. Vertical clearance continued, but the unpinned-landing path retained the
NN's near-zero forward speed. Recovery now detects that mismatch and authors a
forward Hermite path from release. It selects the earliest gait rejoin that can
absorb the recovery without dropping below95% of root speed in the unconstrained
curve, rather than spreading the correction until the end and slowing to wait.
The full rendered shoe sets forward collision limits at the existing heights;
a constrained smooth fit anticipates risers instead of clamping, stopping and
catching up. Keep current pins, root, source banks and recurrence untouched.
This remains cached procedural IK, not live NN reseeding/history feedback.

Saved phase49: right134.5-140 forward2.29 ->11.75cm for unchanged28.07cm lift;
left167.5-171 forward4.55 ->8.91cm for unchanged17.84cm lift. Full recovery has
positive forward movement, no added catch-up kick beyond0.20m/s per120Hz sample
above source speed changes, reachable targets and no rendered shoe penetration
above1e-5m. NN handoff positions remain exact; measured speed differences<0.32m/s.

257 checks pass:211 core,18 velocity,7 clearance,9 ankle and12 release. Exit
velocity must match the gait at the handoff; the old throughout-exit NN-speed
similarity assertion is superseded because it required the reported waiting.
Existing stall detector passes phases0/.25/.49/.75. Knee, landing orientation,
clearance and all50 exact Flat NN slots retain their checks. Default preparation
230ms in Node; no new playback work or UI/processes. No Unreal/other-lab changes.
Browser refreshed and visually checked140/171, then restored135 and options,
settings/camera retained. Desktop needs Refresh. Evidence: `release-verification.json`,
`verify-release.mjs` and `data/release-before.json`.

## Shallow landing without toe-up rebound - October 25

The calf-relative pass was still handing back to the NN's airborne toe-up peak:
phase49 left pitch went flat near78, rose to29.4deg at82, then flattened after
contact. Terrain contacts now use at most5deg positive heel lead, retaining the
existing negative-pitch heel/toe push-off and material-pivot solver. Late swing
slerps directly toward that actual landing orientation over up to220ms (half a
swing), instead of applying a contact delta to the changing airborne NN rotation.
Calf-relative swing and clearance-limited smooth contact handoff remain active.

New shoe geometry changes ankle paths around heel pivots, so the preceding
section's identical-path claim no longer applies. Reach projection can move a
corner across a riser after arc planning; isolated floor-clamp bumps now use a
small constrained upper-envelope fit with fixed contacts. This avoids a newly
exposed knee/riser kick without loosening the existing angular/velocity bounds.

Saved phase49 approach77-88 peaks5deg, down from29.4;135-141 stays below7.3deg.
Mean swing ankle error6.52deg.245 checks pass (211 core,18 velocity,7 clearance,
9 ankle); all previous knee, pin drift, collision, exact Flat NN and exit-stall
checks pass. The old exact ankle-path equality test is replaced by an added-lift
budget check because contact rotation now changes ankle height physically.
Largest sampled added ankle height2.50cm, within the4cm clearance budget;
mean forward sole gap5.33cm, frame163 gap3.81cm. Default preparation270ms in Node.
No new UI, processes, NN or per-playback work. Browser refreshed at current135,
visually checked135/141 and restored135/settings/camera/options. Desktop Refresh
needed. Evidence: `ankle-verification.json`, `clearance-verification.json`.

## Calf-relative swing ankles - October 25

Swing foot orientation now follows the solved calf while retaining the NN's
local ankle articulation. Blend back to the existing world-space contact plan
before touchdown and away from it after release, over a120ms neighbourhood.
Limit the blend against complete rendered-shoe clearance, anticipating nearby
limits so a stair corner cannot abruptly twist the ankle. Pinned heel/toe material
pivots and their rolling arcs are untouched. This final cached orientation pass
does not change hip/knee/ankle positions, pelvis/root motion or NN recurrence.

Saved Walk/phase49: frame79 ankle-relative error63.8 ->39.5deg (already preparing
touchdown at83); free swing60/65/70 matches NN articulation. Across420 SWING
samples, mean ankle error23.45 ->8.05deg. Baseline comparison found zero change
to hip/knee/ankle positions and unchanged pinned rotations to numerical precision.
Whole-course max foot rotation8.03deg per120Hz sample; max material-pin error
1.2e-15m. Mean leading-foot sole gap now6.43cm, frame163 gap3.81cm.

211 core +18 velocity +7 clearance +6 ankle checks pass. The former assertion
that a swinging foot must retain NN WORLD rotation is superseded by the ankle-
relative requirement. The clearance fixture also records pre-change ankle heights:
rotating a shoe changes its footprint and which finite tread is below it, so the
no-added-lift regression compares ankle height instead of the former shoe gap.
Default Walk stairs preparation254ms in Node; no new playback work or UI.
Browser refreshed and checked79/83, then restored79, camera/settings/options.
Evidence: `ankle-verification.json` and `verify-ankle.mjs`. Desktop needs Refresh.
Contained FootIK changes only; no server restart, Unreal, training or push.

## Forward swing clearance - October 25

The global retained-contact arc carried its hardest clearance requirement through
most of the swing, over-lifting the leading foot. The existing constrained height
solver now also fits these swings to the actual shoe-corner floor constraints and
NN height, lowering surplus only. Preserve the initial toe-off path while the
shoe trails the hip; smoothly apply the reduction as it moves from15cm behind to
15cm ahead. This avoids reintroducing the early-release knee jerk. Forward timing,
material pins, source rotations, pelvis/root and UI settings are retained.

Saved Walk/phase49 frame163 sole gap:20.17 ->5.42cm;165:19.68 ->4.71cm.
Across132 leading-foot swing samples, mean sole gap14.07 ->8.07cm (43% less).
Clearance is not a hard height cap: upcoming risers, shoe orientation and smooth
motion can require more room than the4cm setting.

211 existing +18 velocity +7 clearance checks pass. Existing84/108/exit, knee,
contact, collision and motion limits were not loosened. Phase49 maximum joint
step11.87deg and displacement4.87cm per120Hz sample; no measured sole penetration
above1e-5m. Default preparation164ms in Node, no added playback work.
Evidence: `clearance-verification.json`, `data/forward-clearance-before.json`.
Refreshed browser and visually checked163; preserved frame, camera and settings.
Desktop needs Refresh. No other lab, Unreal, training or server changes.

## Entry clearance and exit velocity - October 25

Measured the reported saved Walk/phase49 setup, rather than assuming the default
phase. The first-riser correction was prepared but multiplied by a late spatial
influence fade: upward velocity reached 7.14 m/s near frame43. Higher entry
landings now start clearance preparation at toe-off. A small banded constrained
minimum-curvature solve spreads the lift across that swing, checking rendered
shoe corners and retaining the endpoint samples. Peak upward speed over40-48 is
now0.492 m/s; peak ankle height over28-56 decreases44.14 ->43.07 cm.

The exit arc also manufactured a forward phase lead, then removed it during the
handoff. A world-velocity detector identifies the old unplanted slowdown177-179.5:
NN forward speed exceeds1.2 m/s while corrected total foot speed drops below60%
of NN total speed. Swings ending without a retained landing now retain NN forward
progress plus the smoothly changing contact offset. They keep their clearance
arc without accelerating ahead and waiting for the source to catch up. The
reported exit no longer triggers that detector; phases0/.25/.49/.75 pass too.
Root speed stays2 m/s and retained material contacts are unchanged.

This fixes the planner, not the network state: the lab still uses cached genuine
NN rollouts, with no live policy or history reseeding. A real reseed would require
the lower recurrent pose and previous sample in the correct root frames plus a
new rollout; changing cached phase is not equivalent. It was not necessary to
remove the measured planner-induced stall. No added playback-time work.

211 existing checks plus18 velocity regressions pass. The former assertion that
stairs/frame41 is entirely raw NN is superseded: anticipating a higher landing
requires correction before crossing its riser. The independent Flat preset still
matches every cached phase exactly. The old exit forward-speed minimum was also
replaced by comparison to actual NN progress, so the test cannot reward rushing
ahead. Prior knee, pin,84-92/106-120 clearance, reach and motion bounds remain.
Default preparation measured160 ms in Node. Results: `verification.json` and
`velocity-verification.json`; baseline sample trace: `data/velocity-phase49-before.json`.
Browser43/178 visually checked, no console errors, restored paused172 with original
phase49, camera, ghost16% and terrain translucency10%. Desktop needs Refresh.

Ghost translucency is appended at the bottom of More options:0% solid,100%
invisible, default70%. It redraws immediately and persists with setup without
rebuilding motion. Refresh now also restores its percentage readout.

## Collider ghost and contact roll â€” October 25

NN ghost now draws translucent purple versions of the same full-body capsules
and boxes as the main character, including feet/toes, visible through the terrain.
Its geometry/upload is cached for unchanged raw poses. It does no work when
unchecked, casts no shadow, and uses a depth prepass to prevent stacked transparent
back faces. The existing checkbox stays in place.

The previous ankle-centred contact rotation was incorrect: it recovered a floor
intersection while letting the material point on the sole slide. It is replaced
by a rigid heel-to-toe roll. The planner captures the shoe/toe geometry and uses
`support.js`'s piecewise pivot arcs: a fixed material point stays at its world
anchor until the sole reaches the next supporting edge. The ankle follows that
arc. Foot/toe articulation stays fixed during a plant. After toe-off, the captured
rotation remains while the ankle trails the pelvis; it blends back to the NN as
the foot advances from 15 cm behind to 12 cm ahead, or approaches the next landing.
This replaces the old fixed 0.1-second release. The source pitch drives the roll. Extension can use the remaining range down to
70 degrees toe-down; the old 35-degree extra-roll cap prematurely released contact.
Extra rotation slews at up to 540 deg/s. A rising next tread reserves up to 6 cm
of toe-off room while keeping the initial material contact on its finite tread.
The swept shoe volume reserves tread room, including top corners near risers.
Release is checked against the rolled ankle's reach, not the old ankle target.
`ROLL` now denotes a real retained material contact, not a new ray intersection.

Knee popping came from a hard 99.5% extension clamp and abrupt contact/reach
transitions. A C1 exponential soft reach begins over the final 6% of extension.
A short precomputed pelvis envelope anticipates stance reach and recovers more
slowly after release; swing clearance is resolved using the same reach limit.
Dropping past a finite tread edge approaches the landing instead of snapping
down and immediately declaring a plant. Descending swing corrections settle
earlier to avoid excessive folding while the root descends its ramp.

Knee-plane jitter is handled separately from knee extension. The IK pole is
filtered in pelvis space with a small Gaussian window (sigma 5 samples at 120 Hz,
12 samples on either side), transporting neighbouring poles onto the current leg
axis before averaging. Source orientations are retained; this is a pole target
filter, not a post-solve knee-position filter. It fades with terrain influence,
and flat/approach/exit continue to use exact NN poses.

Across the default stair sequence, the maximum change in transported pole-angle
increment falls from **4.56 to 0.423 degrees per 120 Hz sample**. The sharp right
pole reversal around 80 falls from about **4.40 to 0.423 degrees**. The trailing
shoe now stays pinned at **101–102** (57.4 degrees toe-down at 101), then remains
67.1 degrees toe-down at 107 instead of resetting horizontally behind the body.
The rig labels that trailing cyan leg R in this view. Finite riser clearance is
checked during toe-off; forward travel can wait while the pointed shoe lifts.

Rising swing now coordinates forward travel and elevation between actual planted
contacts. The previous height-only Hermite correction improved 84 but made the
trailing foot climb almost vertically around 108. Forward progress now eases
between takeoff and landing; elevation follows the same incline progression with
a smooth clearance arc fitted to all rendered shoe corners. The arc's shoulders
flatten through mid-swing to avoid an unnecessarily tall dome. Original lateral
motion, sole rotation, planted contact timing and NN body motion are retained.
The path starts at a retained contact and can end at either a plant or the NN
exit pose. Requiring a retained landing pin was a bug: it skipped the 168-198
exit swing, reverting to per-riser corrections. Exit swings now use the same
continuous path, with the correction fading into the NN endpoint.

Default right-foot travel over 106-110 is now 15.1 cm forward / 15.1 cm upward,
versus 2.3 / 13.0 cm with height-only lift. The left-foot ascent through 84-92
remains continuous (1.61-2.47 cm per 120 Hz sample). The first crossed riser is
located from the swept sole during verification, rather than assumed to occur
at the old 85.5 timing.

The ascending exit handoff is based on the root leaving the ramp and both NN
shoe footprints lying over the common final-tread/exit plane. A 12-sample fade
ends at that point; thereafter the exact raw pose object is returned, including
all knee positions and orientations. Default Walk switches at 181.5 (formerly
205.5); Run at 74.5. The independent Flat preset and its cached NN banks were
already unchanged. No source NN motion is filtered or rewritten.

The reported right foot stays pinned through 164-168, then clears the last
risers continuously: 171-176 rises 1.58-2.01 cm per 120 Hz sample, advancing at
least 2.39 cm/sample. Tests also cover lift acceleration through 181 so the
later 178 kick cannot escape a short-window regression.

**212 checks pass**: all 50 cached phase slots unchanged on flat, walking/running
on four presets, fixed material anchors, heel/toe transfers, bone lengths, finite
contacts, clearance, motion bounds, reported knee extension and the new whole
course pole-continuity / 101 retained pin / 107 trailing orientation regressions.
Default Walk/stairs has 195 consecutive same-pivot pairs with drift below
0.000001 mm and eight pivot transfers. Existing 15/20-degree and 9/14-cm Walk/Run
per-sample motion bounds remain unchanged. The knee at 104 now intentionally
flexes during ascent; its regression checks angular-velocity continuity across
102-106 (under 1.5 degrees change per displayed frame) and speed under 10 degrees.
The shared forward swing flexes the knee faster (maximum 8.72 degrees per
displayed frame in this window), while retaining the former acceleration bound
and all global motion limits. New checks cover continuous 84-92 ascent, lift
acceleration, early riser clearance and diagonal progress throughout 106-120. This is not a claim
that every terrain/tuning combination is pop-free. Results: `verification.json`.

The solver still prepares 601 cached poses only on setup changes (about 170 ms
for the default Walk/stairs in the Node check). No extra inference, physics or
per-frame solver was added. UI layout and options are unchanged. Browser
170/174/182 inspected with the full collider ghost; no console warnings/errors.
Restored the user's paused 178, camera and settings. Preview: `snapshots/exact-nn-exit-182.jpg`.
The in-app tab is refreshed; an already-open desktop lab still needs Refresh.

## Full-body shadows â€” October 25

Replaced the rejected analytic foot footprints with actual depth-mapped shadows
from the displayed head, torso, arms, hands, legs and shoes. They fall across the
real stair treads and sides, and the body can shadow itself. Ghost/target overlays
do not cast. Motion, tuning and UI layout are unchanged.

One 1024Â² depth texture (about 4 MiB in WebGL2) covers a stable four-metre window
around COM. The existing body vertex buffer is uploaded once and reused for one
extra depth draw; there is no second CPU mesh build. Only the character casts;
the terrain receives, avoiding a second draw of the course. The framebuffer and
texture are allocated once. Camera/debug-only redraws reuse the map while the
pose and displayed geometry are unchanged. A small 3Ã—3 filter smooths edges;
normal/depth bias removes self-shadow acne without the old footprint approximation.
No GPU readbacks or timing queries run in the app.

Implementation references: [WebGL shadow mapping](https://webglfundamentals.org/webgl/lessons/webgl-shadows.html)
and [MDN performance guidance](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_best_practices).
The optional `verify-shadows.html` check uses cached poses without accessing saved
state, renders only 32 measured samples and releases its WebGL context afterward.
It verified one depth draw per pose, cache reuse on camera changes, and no GL errors.
On this laptop/browser the extra depth pass (7,948 triangles) measured **0.088 ms
median / 0.145 ms p95 GPU**; CPU submission p95 was 0.1 ms. These figures exclude
the main scene's shadow sampling cost and are not total frame times. Results:
`shadow-verification.json`.

Syntax and live shader checks pass. F25 on the approach and F150 on the stairs
were visually inspected; no browser warnings/errors. Restored the user's F25,
camera and settings. Preview: `full-body-shadows.jpg`. Refresh an already-open
desktop app to load the change. No server restart, Unreal or training work.

## October 25 correction â€” preserve the NN gait

The first prototype was wrong: it applied a generic swing lift on flat ground,
then divided stair clearance by a nearly zero endpoint blend weight. At the
reported F41 (0.683 s), this moved the left foot **84.3 cm above the NN pose**.
The copied support solver also used pelvis +Y (backwards in this rig) as the
fallback knee pole when the source leg straightened. Reach/penetration checks
alone did not catch either motion defect; the earlier validation was inadequate.

`footik.js` has been rewritten. Flat terrain, level approach and level exit
return the exact NN pose, with no pelvis adjustment, foot alignment or IK solve.
Terrain corrections begin near the first riser. A bounded clearance envelope
replaces the amplified arc, and the anatomical hinge defines the bend direction
near extension. The material-pivot roll described above now supplements the NN shoe motion on
terrain; source articulation returns during swing.
Pelvis motion is driven only by contact reach, is rate-limited, and does not jump
to a new constraint bound. Resolved swing paths also anticipate risers after reach
projection. A stance releases before the trailing leg is dragged out of reach.

The source was verified rather than swapped: the copied Walk bank is byte-identical
to Bodyflip's recorded bank, and its recorded Walk July5 checkpoint SHA256 matches
the installed `lower_body_walk_july5-8bae21c5b315.pt`. Forward speed remains the NN's
2 m/s (Run 5 m/s). No stride scale, retiming or authored animation substitute.

The seconds readout and bracket tooltips now use frames. The existing desktop
shortcut launches its own Edge/Chrome app window, profile and icon on port 8878.

## Run

Open **Foot IK Lab** on the desktop, or run `launch.ps1`. The launcher checks
ownership of port **8878**, starts a hidden local Python server when needed,
and opens an app window with its own browser profile.

- Local URL: <http://127.0.0.1:8878/>
- Separate state: `state.json` (ignored by Git).
- Separate browser profile: `%LOCALAPPDATA%/FootIKLab/browser-profile`.
- Reinstall the shortcut: `install_shortcut.ps1`.
- No Unreal connection, training process, Jolt simulation or live NN inference.
- All runtime files and gait data are local copies; there are no live imports
  from Bodyflip Lab. `reuse.json` records the copied source hashes.

## Controls

Walk/Run and Phase choose the cached NN gait and starting pose. Terrain offers
stairs up, stairs down, uneven blocks and flat ground. Rise and Tread are in
centimetres. **The root follows a continuous ramp; foot placement queries the
discrete stair treads.** Uneven blocks leave the root on its flat reference path.

Enable IK switches immediately between the corrected pose and the NN pose on
the same root path. Clearance adds swing clearance over upcoming risers. More
options, below the view buttons, contains Steps, maximum Pelvis correction in
centimetres, and side/underside Translucency. Defaults: 12 steps, 16 cm rise,
35 cm tread, 4 cm clearance and 30 cm maximum pelvis correction.

The existing single playback bar retains loop brackets, immediate scrubbing,
speed, a zero-based 60 Hz frame counter and keyboard control. Space toggles
playback; Left/Right step one frame unless a writable field has focus. Dragging
a bracket previews that boundary, then restores the previous playhead when
released. Refresh restores settings, camera, playhead and playback state.

Left drag orbits, middle/right drag pans, wheel zooms without an outward cap.
The camera follows body COM. Diagnostics at the bottom: NN ghost, Targets,
Root ramp, Two-tone and Bones. Target colours are green for PIN/ROLL, purple for
SWING and orange for an unresolved REACH limit.

## Pipeline and research

`cached NN gait -> ramp root -> terrain targets + pelvis correction -> leg IK`

This is an independent, GASP-inspired prototype, not a port of Epic's node or
Control Rig. The [GASP documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/game-animation-sample-project-in-unreal-engine)
describes Leg IK following IK-foot targets. Epic's
[UE 5.7 update](https://www.unrealengine.com/tech-blog/explore-the-updates-to-the-game-animation-sample-project-in-ue-5-7)
introduces the Footplacement Control Rig. The installed
`UE_5.7/Engine/Plugins/Animation/AnimationWarping/Source/Runtime/Private/BoneControllers/AnimNode_FootPlacement.cpp`
was inspected for the separation between contact intent, alignment, planting,
pelvis solving and leg reach. No Epic implementation code was copied.

The first version:

1. Estimates stance intent from uncorrected NN sole height and horizontal foot
   speed, with hysteresis. The copied pose banks do **not** contain the NN pin
   outputs; this estimate is not advertised as those outputs.
2. Chooses a finite tread contact that fits the swept shoe. A stance retains a
   material sole pivot and its surface identity/local position. Reach releases
   it without immediately replanting during the same source stance.
3. Rolls around that pivot using source pitch plus bounded extra toe-down at
   extension. Heel/toe transfers keep contact continuous. Clearance checks include
   actual rotated foot and toe corners, including the top of the shoe near risers.
4. Previews the upcoming swing and adds only necessary terrain clearance. The
   bounded envelope also checks the path after reach projection; no division by
   a small blending weight and no added flat-ground swing arc.
5. Solves a bounded, rate-limited pelvis offset for contacts, then uses a two-bone
   solver with a stable anatomical bend plane through straight-knee poses.

Corrections stay outside NN recurrent state. A future simulated integration
must compare physical error against the corrected commanded target, following
[Lower Physical Feedback Alignment](../../Docs/LowerPhysicalFeedbackAlignment.md),
rather than treating the deliberate stair correction as an NN disturbance.

## Limits and validation

This version uses five-second forward Walk/Run samples and static rectangular
terrain. It has no jump controller, platform editor, physical tracking or moving
platform transport. Contact local coordinates are retained for future transport;
moving-platform behavior is not implemented. Very steep/narrow settings can
exhaust pelvis or leg reach; this is not a complete production stair controller.

`node Labs/FootIKLab/verify.mjs` passes **201 checks**. They now require exact NN
identity for all 50 stored Walk/Run starting phases on flat ground, exact source
policy samples, and exact identity at reported F22/F41 in the default stair scene.
The default eight gait/terrain cases additionally check every frame for orientation
flips/teleports, finite poses, bone lengths, actual planted contacts, sole clearance,
root-ramp separation, bounded pelvis motion and deterministic reverse seeking.
Terrain-corrected reach error is below 0.0001 mm in those fixtures. Original small
flat-ground NN sole/interpolation offsets are deliberately retained, not cleaned up.
Default Walk terrain motion has maximum per-sample angular change of 12.59 degrees;
the worst Run terrain case is 13.79 degrees at 120 Hz. Uncorrected flat Walk
retains the NN source's 8.71-degree maximum. Contact-roll checks also verify
fixed material pivots, a moving ankle, rigid stance articulation, bounded extra
roll and the knee changes at F75/F96/F104.
These are regression checks, not a claim of perfect gait quality at all tunings.

Five-second preparation takes approximately **50â€“145 ms** in the local Node
check. Browser playback reads the precomputed 120 Hz frames; it does not run the
solver or NN on every render. Rendering pauses when the tab is hidden, and pixel
ratio is capped at 1.25 to keep laptop load modest.

Browser QA verified F22/F41 against the NN ghost, the frame-only readout,
keyboard stepping and Refresh restoring F41. Earlier UI checks also covered
Walk/Run changes, scrubbing and Space after a button click. Regression screenshots
are `frame-22.jpg` and `frame-41.jpg`. Ascending and descending contact were also
visually checked at F150; no browser errors were recorded. The desktop shortcut
was exercised and opened a separate Edge app window; its process arguments were
verified to use port 8878 and the dedicated FootIKLab browser profile.
The desktop shortcut target, arguments and icon were inspected. The server was
started on port 8878; no existing lab server or Unreal session was restarted.

## Files

- `terrain.js`: separate root surface and foot collision surfaces.
- `footik.js`: deterministic contact/swing/pelvis/leg planning.
- `app.js`, `index.html`, `style.css`: stripped lab UI and rendering integration.
- `support.js`, `recovery.js`, `renderer.js`: independent reused helpers.
- `run_bank.py`, `data/*-phases.*`: frozen cached NN samples.
- `verify.mjs`, `verification.json`: focused regression checks and last results.
- `server.py`, `launch.ps1`, `install_shortcut.ps1`: local app lifecycle.

### Wall timer removal - October26
Removed standalone wall expiry and permanent zero-speed latch. Current
Walk69/yaw300/90deg climbs at2m/s at206.17 focused full-clip checks pass.
The broader surface suite has an existing lateral0deg pin-slip assertion failure;
that case is pose/metric-identical before and after this change. No solver or
NN changes to conceal that failure. Shared createFeet host API unchanged.

## Incline gravity and root marker - October27

Root is appended after Bones and shows the actual root bone as a yellow
three-axis marker on all terrains. Incline gravity is an optional mode at the
bottom of More options for Incline / wall. Defaults: mode off to retain existing
scenes, minimum45deg, full gravity100%, energy conservation100%. Controls persist
and edits retain playback time/camera. No reordered controls. Enter (including keypad Enter) commits numeric entries and removes focus, so playback shortcuts work immediately afterward.

The More options header stays visible while its panel scrolls, so it can always be closed. Clicking outside closes it; clicks inside retain it.

**Delete floor F** is appended after Energy conservation, only for Incline /
wall. Default-1 keeps the flat entry; otherwise remove it at that exact60Hz
playback frame. Geometry, terrain queries, root collision and existing foot
pins all lose the surface together. No residual support grace or deletion
impulse. Rewinding/looping uses the active surfaces for the sampled time.
The incline extends both uphill and downhill; its extent covers the recorded
root travel plus full ballistic fall, so a wall continues below the entry floor.
Parallel approach already has no flat entry. Other terrain modes ignore this
option. No new API requirement for shared createFeet; a removed surface ID
releases its pin immediately.

Eight45/90-degree deletion clips cover frames0/20/120/300, exact unchanged
prefixes, no deletion impulse, pins/clearance/reach and downward wall coverage.
Further checks cover exact pinned-surface release, reverse seek and unchanged
stairs. All173 gravity checks still pass. Browser verified Enter commits/blurs,
arrow rewind101→99 restores the floor for deletion100, and forward101 removes
it. Restored-1 and the user's frame101/settings/camera afterward. Receipt:
snapshots/floor-delete-verification.json.

October27 clarification: at/above Minimum gravity incline, gravity is fully
active with no automatic gravity compensation. There is no angle ramp toward90.
Full gravity % removes that fraction of **world-vertical root thrust**, including
both velocity drive and the commanded height-support spring. Horizontal thrust
remains.0% retains thrust (gravity still acts);100% removes all vertical thrust,
so vertical acceleration is exactly-9.81m/s2 before collision responses, on any
active incline. Solid-surface collisions and the separate entry energy transfer
still change velocity; gravity does not let the root penetrate the terrain.
Below the minimum and with the mode off, existing controller behavior remains.

On a course-plane transition, redirect incoming velocity before smoothed body
alignment and normal damping consume it.0% projects velocity onto the new plane;
100% transports its heading to the new plane preserving speed. Intermediate
values retain that fraction of kinetic energy that projection would lose.
A normal change is processed once; persistent collision with the same plane does
not repeatedly transfer energy. Landing can transfer back onto the floor.
Incoming2m/s flat-to-wall checks:0% gives near-zero upward speed;100% gives2m/s up,
then gravity slows and reverses it. No timed support cutoff or permanent stop.

173 focused checks over18 full clips pass: gravity/vertical-thrust endpoints,
no hidden compensation at0%, exact integration, energy transfer, clearance,
reach/material pins, below-threshold pose equality and old-mode frame equality.
Three additional clips use the current actual Run-policy Walk command (phase69,
yaw300 from1.2-6m) at0/45/100%. At100%, all359 active frames have exactly-9.81m/s2
vertical acceleration;344 intervals with no vertical collision impulse also
show that exact velocity change. Receipts: snapshots/incline-gravity-verification.json
and snapshots/root-thrust-verification.json. Shared createFeet API remains1;
Bodyflip's root simulation does not inherit these lab-only controls. No server
restart, NN change or other-lab/Unreal edits required. Refresh retains settings.
