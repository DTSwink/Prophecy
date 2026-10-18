# Procedural sword holster

**Status: TEMPORARY FINAL, user accepted October15, 2026.** Lab and Unreal settings at Git milestone `ds-temporary-final-2026-10-15` are the accepted baseline. Do not revise D/S motion or tuning without a new user request. Existing verification limits below remain applicable.

Original implementation saved October10 through Live Coding; the current lab port below was subsequently rebuilt normally and verified in Play.
This supersedes the animation-driven proposal in SwordDrawingResearch.md.

## October15 saved slide tuning refresh

Imported current saved lab S sliding speed230cm/s (previous170) and first S slide-curve point(.15053891961839325,.0988776276854313); remaining curve points unchanged. D remains330cm/s with a linear slide curve. Updated existing unlinked Sheathe Sliding Speed literal on the big profile node, preserving every other graph field/link, then saved PoseAgent. Editor helper now supports `Prophecy.Editor.RefreshHolsterGripPins SetSlideSpeeds <draw> <sheathe>` for explicit existing-literal updates; wired values are rejected before mutation, normal missing-pin migration unchanged. Editor-only Live Coding130.94s, no restart or runtime/layout changes.240tick live capture across3agents verifies six slides: S18ticks/.30s, D13ticks/.2167s, all recorded curve fractions within4.93e-10 of the lab evaluator. Lab state and unrelated settings untouched. TestNN remains dirty/local; normal DLLs stale; included in the temporary final checkpoint. Evidence `Saved/Diagnostics/SlideLabSync20261015/`.

## October15 checkpoint and slowdown check

User accepted the current motion and requested a checkpoint. Diagnosis-only paired current-scene captures cover295 consecutive ticks per mode across3agents: D release-to-finish38/39/40ticks in both Sim and Kin; physical hand target error after the first two release ticks at most.11861cm. No extra Sim return delay reproduced; tick90 in this current setup is S, first D releases176–179. No source/tuning fix was made for that report. Evidence `Saved/Diagnostics/DrawReturnSlow20261015/`. PoseAgent/A_Sword freshly compiled and saved with byte-identical complete graph; TestNN remains unsaved/local. No restart; normal DLLs remain stale.

## October15 mode continuity correction

Tab now preserves the active D/S motion. The earlier cancellation removed the authored pose and restored sword scale; that was the reported reset, not an acceptable interruption policy. Pending entry samples, action clocks, previous/current poses, shrink, insertion and attachment survive. Before teardown, only old joints, temporary physical-arm ownership and scoped contacts/limits are released. Initial admission and rebind share the same holster binding/grip implementation. A holster already kinematic keeps its ongoing compensation.

Three additional transfer errors were found and corrected:

- Actual input could request Jolt after its admission window, leaving one intervening Chaos simulation frame. The entire Kin->Jolt switch now uses the existing admission queue; the character stays kinematic until native admission is safe. Existing admission identity/cancellation is reused, with no new retained fields, timer or polling layer. A later explicit Kin request cancels it.
- The intermediate ordinary sword refresh could send a holstered D sword back to the hand (51.24cm in a rapid-switch probe). Refresh now waits for selected Jolt ownership and rebinds the active holster state without changing scale or relative placement.
- Old presentation state could reappear: the Kin->Physical pose blend outlived Jolt takeover, and the attached arm's post-physics pose was newer than the published kinematic copy. Native admission now retires that completed mode blend; the switch republishes the already-computed current D/S pose. No resampling, new solver or action-time change is introduced.

A trial using the existing whole-pose fade on Sim->Kin was rejected during testing because it held the visible hand behind the advancing action and caused catch-up on return to Sim. It is absent from the final code. The corrected path preserves action continuity directly; it does not promise identical physical and kinematic tracking for every body.

Final evidence: `Saved/Diagnostics/ModeContinuity20261015/` (`verified*.json`, `repaired-smoke.json`, `verified.json`, `receipt.json`). Seven runs, 4065 consecutive world-tick samples across three agents, 111 mode/input requests including three cancelled pending requests. Coverage includes actual Tab idle/walk, S/D reach/sliding/return, fully holstered, rapid/same-tick reversals, pending entry and physical-holster preference. Both actions complete in every run. No action-clock reset, unexpected Chaos frame in key tests, duplicate sword adapter, missing attachment or binding error. The two immediate API suites contain16 attached-arm Sim->Kin transfers: max arm position change6.36e-14cm, rotation below.01deg; sword-local position remains within.001cm. Other bones still remove ordinary physical tracking error on Kin entry, measured up to1.1773cm/7.0571deg. Key-event before/after measurements span one or two moving ticks and must not be interpreted as instantaneous seam sizes.

The no-switch regression compares595ticks x3agents against the first continuity candidate, before the mode-only follow-ups: all physical/visible/future/authored/equipment transforms and native velocities match exactly. This is not a comparison to every historical version. A separate sharp upper-arm roll at D release382 (~148.53deg, then~60deg on following ticks) also occurs in the unchanged baseline. It is recorded as an existing motion issue and has not been altered in this Tab repair.

All six implementation/method-only Live Coding builds and reloads succeeded; Unreal was never closed, and no retained layout or Blueprint control changed. Reload-created archived library defaults were repaired using the existing helper, without saving assets. Final graph byte-identical to the pre-work capture; original dirty PoseAgent/TestNN preserved, A_Sword additionally unsaved after reference repair. Editor19216 outside Play/60FPS/status3, no stale native properties or pins. Normal DLLs still require building before a cold launch. No new steady-state calculation or performance claim; no push.

## October15 Tab input conflict

The character's Tab graph correctly toggles SetSimulationMode between Physical and Kinematic. A_Sword also had a consuming Tab event wired to SetGamePaused, intercepting the key before the character. Actual input reproduced a pause at tick71 with all three agents still Physical/Jolt. The earlier API-driven mode tests did not exercise this input path.

Removed only the sword Tab event and its outgoing execution link; the old pause function nodes remain unconnected, all other wiring/tuning retained. Character Tab and Caps Lock are unchanged. Eight key-driven round trips (first press20/45/70/105/140/155/168/190, second10ticks later) pass over2,040 consecutive captured ticks:16 real player-controller Tab events, expected Physical->Kinematic->Physical, no pause or physics binding errors. Saved A_Sword; repaired existing archived Live Coding library defaults and saved PoseAgent with identical gameplay graph. Key-pin empty/None serialization is equivalent. Existing A_Sword unconnected `get depth of location` compiler warning predates event removal and was left alone.

Editor helper uses the existing migration command's RemoveSwordTab option; InputCore is now an explicit editor-module dependency. Final Live Coding build119.81s/reload passed after one compile/two link errors; no runtime physics changes or restart. Evidence `Saved/Diagnostics/TabMode20261015/`. Owned tests ended; the user started a fresh Play session before final inspection, left untouched at60FPS with dirty TestNN unsaved. Normal DLLs require a build before cold launch.

## October15 sword binding across Sim / Kinematic

The mode-switch failure noted in the overlap audit below was reproduced and traced to equipment ownership, not overlap generation. At Sim -> Kinematic tick70, scene discovery treated a holstered sword as an ordinary loose prop because it checked `GetHeldSword()`. That getter deliberately returns null while the sword is in its holster. Scene discovery created a second Jolt adapter; the equipment controller only knew its original adapter and subsequently enabled Chaos on the same source. The shared Jolt world correctly stopped on that ownership violation at tick73. This preceded hide/re-equip100. Temporary tracing distinguished scene discovery from the generic force/admission path; both contained the same incorrect ownership predicate.

Both admission paths now check `UProphecySwordComponent::GetSword()`, which includes holstered equipment. Dropped swords remain ordinary props. The source guard now distinguishes a missing source from Chaos having been enabled on a live Jolt-owned component; no guard was weakened.

Fixing that exposed stale D/S state on the reverse switch: an action started kinematically could retain its old mode and write scale through the wrong backend after Sim resumed. The initial repair cancelled pending/active D/S before tearing down its bodies. That policy caused the user-reported pose reset and was rejected. The continuity correction above supersedes it; the original lifecycle evidence below does not establish pose continuity.

A fully sheathed sword is preserved instead: rebind updates its backend state and keeps its existing holster-relative transform rather than sending it through ordinary hand binding. Deferred rebinds wake the component and run before the holstered early return. Once settled, the component sleeps. A regression check caught the new sleep branch also disabling a queued draw; it now remains awake whenever a draw request is pending. The corrected no-switch capture matches the previous overlap-disabled version exactly for425ticks x3agents, including all previously captured poses, native velocities and D/S timing (zero differing fields).

Validation evidence and scripts: `Saved/Diagnostics/SwordModeSwitch20261015/`. The12-case matrix covers held, S/D reach/slide/return, fully holstered, one-agent switches, same-tick/rapid reversals and physical-holster preference. Additional cases repeat the original switch/hide/re-equip sequence and switching with a rigidly held sword. Tests require finite consecutive samples, successful switches, no duplicate adapters, consistent backend flags and preserved holstered parent. Original failing captures and the intermediate stale-state failures remain recorded; `comparison-before-pending-fix.json` records the caught timing regression. Final loaded-version verification is summarized in the current journal.

Final loaded-version results: all12 matrix cases plus original lifecycle and rigid-sword cases pass,136 individual mode-switch calls /6,125 consecutive finite captured ticks across3agents. No duplicate adapters, runtime physics errors, wrong holstered parents or stale mode flags. Through four fully holstered switches, maximum local position drift4.80e-14cm and quaternion-component difference2.22e-16. Final `unchanged-comparison.json` has zero differences over425ticks x3agents. These are numerical lifecycle/regression tests, not a new general performance or visual-perfection claim.

Four implementation-only Live Coding builds/reloads (130.07/144.16/341.29/129.71s), no retained layout or reflected pin changes, editor restart, Blueprint/asset/lab/tuning edits or push. Final editor19216 open TestNN, outside Play, clean,60FPS. Normal DLLs remain stale: normal build before a cold launch. No new per-tick ownership scan, extra solver, timer, interpolation or weakened physics checks.

## October15 agent overlap policy

User explicitly requested disabling all agent overlaps in both simulated and kinematic modes. `AProphecyAgent::BeginPlay` now enumerates primitive components, including Blueprint components and child actors, and sets GenerateOverlapEvents false. Sword Equip applies the same policy to its newly spawned equipment and children. Existing capsule/main-mesh initialization already disabled their overlaps. This is initialization/spawn work only: no new tick, retained state or policy manager. It does not change collision enabled modes, responses, physical hit events, Jolt contacts or traces. Arbitrary future gameplay code that creates new primitives or explicitly re-enables overlaps must respect this policy; there is deliberately no perpetual scanner. Viewport asset defaults are unchanged; runtime initialization applies the policy.

Layout-safe Live Coding build171.80s and reload succeeded without restarting or changing reflected layouts. Live checks inspect all33 current primitives every15ticks: zero enabled overlaps through425tick Sim and425tick Kin D/S runs. Sim capture matches the previous loaded version exactly for425ticks across3agents: all captured poses, native velocities and D/S fields/timing. Both modes traverse reach, slide, return and completed states.

Three650tick performance captures compared with the immediately preceding batching version,267 samples per group with all3arms attached:

| Attached-arm stage | Before | Overlaps disabled |
| --- | ---: | ---: |
| Mean | .257129ms | .184076ms |
| Median | .2349ms | .1747ms |
|95th percentile | .4073ms | .2679ms |
| Maximum | .5202ms | .4237ms |

These are sequential editor runs on the same machine, not an isolated or alternating-build benchmark. No whole-game/crowd speedup claim.

**Timeline correction from the detailed log:** the first shared-world failure occurs around tick73, just after Sim->Kin at70 and BEFORE hide/re-equip at100. The attempt to return to Sim at130 only reports that the shared world is already stopped. The earlier summary incorrectly associated the initial failure with re-equipping. The guard combines two cases (source component missing OR Chaos simulation enabled); the recorded generic message does not distinguish them or identify the writer. No repair has been attempted.

An additional compound lifecycle test failed: Sim->Kin at70, hide/re-equip(false) at100, return to Sim at130. The shared native world rejected enabling because an A_Sword binding had lost its source or Chaos simulation was enabled externally. Repeating with overlaps explicitly enabled reproduces the same error; all124 preceding actor samples are identical. Thus this failure persists independently of the overlap policy and is left reported, not marked passed or patched under this task. All inspected components stay overlap-disabled through the successful Kin/re-equip portion. The temporary comparison override is confined to the owned test, never production or assets. Initial Python getter/setter wrapper errors were corrected in the diagnostics.

Evidence `Saved/Diagnostics/AgentOverlaps20261015/`: source snapshots, capture/inspection scripts, Sim/Kin recordings, exact motion comparison, both failed lifecycle recordings, performance receipt and final status. Raw timing CSVs `Saved/Profiling/CSV/no-agent-overlaps-{0,1,2}.csv`. Editor19216 open TestNN, outside Play, no dirty packages,60FPS, native status3/no stale pins. Normal DLLs still require a build before cold launch. No lab/BP/tuning changes or Git push.

## October15 lossless attached-sword batching

User resumed the paused performance task after the RMB timestep fix. This pass produces a small optimization; it does **not** establish a large reduction in D/S cost.

The only production change is a standard `FScopedMovementUpdate` on the attached sword surrounding the holster's existing rotation update and the sword's existing local transform update. Previously the parent move published the child before the child's own move. Deferred child publication combines those updates, including the engine's ordinary overlap handling. The callback ownership checks remain. Kinematic-only agents do not enter this path. No motion calculation, physics write, collision setting, release history, asset, lab setting, recurring cache, scheduling policy or user control changed.

The first instrumented run attributed about.241ms to holster movement,.060ms to sword movement,.017ms to the arm solve and.015ms to native arm writes. Those absolute figures varied with machine load. Engine traces showed component transform propagation, query-collider updates, navigation updates and overlap work; repeated native sword writes were only a few microseconds, not the dominant cost. Traces are archived in the evidence directory to avoid leaving large temporary exports.

A trial scoped both parent and child. Its initial apparent32% improvement was **not accepted as an optimization result**, because unchanged math also ran faster. Six alternating650tick runs in one loaded build then compared the original path with that trial,351active frames per variant: median.2411→.2235ms, mean.253037→.244566ms. The redundant parent scope was removed for the final implementation. The temporary selector and all six additional timing subdivisions were removed; only the original `AttachedArm` scope/counter remains.

Final three650tick runs, compared with the original-path runs above:

| Frames where all three arms are attached | Original | Final |
| --- | ---: | ---: |
| Samples |267|267|
| Mean |.265363ms|.257129ms|
| Median |.2476ms|.2349ms|
|95th percentile |.3956ms|.4073ms|
| Maximum |.5273ms|.5202ms|

These are wall-time stage measurements on the user's editor/machine, not a hardware-isolated benchmark. Final versus original averages are not an alternating same-binary comparison: final has one scope and no temporary subdivisions. The small mean/median reduction is consistent with the controlled trial, but the tail did not improve. All-active-frame final average is.247386ms across351samples (some frames have fewer than3attached agents). Do not claim a major speedup,10×, or improved whole-game/crowd performance. The remaining engine component/query/overlap work was not removed by disabling functionality or weakening publication checks.

Verification:

- Original versus two-scope trial:425ticks ×3agents, all captured values exactly equal.
- Original versus final one-scope version:425ticks ×3agents, exactly equal again, including actual RMB press20/release150 (held cap5, fixed game step1/60), full poses, native linear/angular velocities, equipment and D/S report fields/timing.
- Both trial and final pass all10hide/drop/reset/Sim→Kinematic/direct-sword-destruction cases, each in alignment and sliding. Ownership, limits and holster return restore.
- Final layout-safe Live Coding build87.93s and reload succeeded; no object changes/restart. Four total implementation builds in this pass. Final editor19216 outside Play, clean,60FPS, native status3/no stale pins. Normal DLLs remain stale and must be built before a cold launch.
- No lab, Blueprint, tuning or asset edits; no Git push. Prior unrelated working-tree changes preserved.

Evidence: `Saved/Diagnostics/AttachedArmOptimize20261015/`: original source snapshot, original/final captures, exact comparisons, lifecycle results, six A/B CSV summaries, final performance receipt and archived engine traces. Raw CSVs are in `Saved/Profiling/CSV/`. This pass leaves the larger component-publication cost explicitly unresolved rather than disguising it as a large gain.

## October15 right-click debug freeze

The actual RMB input was intercepted by A_Sword's debug binding. Its configured
slow-fps5 called SetFixedFrameRateRuntime, making each physics tick.2s instead
of1/60s. The character's separate RMB binding already used `t.maxfps10`, but
the sword consumed the key. Actual injected input reproduced the fault: after
tick36 all three physical agents froze through240. The first shared-world error
reported magic Cube publication differing by.000244140625cm; no D/S correction
or relaxed publication guard was added to hide that failure.

Only the sword RMB Pressed/Released execution links now point to its existing
FPS-cap nodes (slow-fps5 / release60). Fixed-clock initialization and all tuning
remain unchanged. The previous audit tested the cap directly and therefore
missed the sword's timestep-changing input binding.

Actual held-input test spans first S and D at4.996 measured FPS with fixed1/60
delta. Matched fresh control/repeat:235ticks across3agents, every recorded actor
value identical, including native velocities and motion timings. An earlier
post-reload capture differed slightly for one NPC from startup, before the key
press; retained separately rather than presented as exact parity. The repeat
comparison passes without tolerance or exclusions.

Saved A_Sword; complete graph comparison permits only six reciprocal pin-link
lists belonging to the two rewired connections. Editor-only repair helper
loaded without restart; no D/S/physics runtime or lab change. Editor clean,
outside Play,60FPS; normal DLLs remain stale from prior Live Coding. Performance
optimization remains paused. Evidence `Saved/Diagnostics/RightClickDS20261015/`.

## October14 slide speed inputs on the big node

Set Sword Holster Profile now exposes **Draw Sliding Speed** and **Sheathe
Sliding Speed**, in cm/s. The existing Blueprint node uses330/170, preserving
the accepted imported values. Call it after Set Sword Holster Lab Profile;
positive inputs override the next action and0 leaves the configured speed
unchanged. No change to curves, active actions or the lab. Existing per-action
fields hold the override; no retained-layout change or added tick work.

Live Coding built/loaded without restart. Only the two speed pins differ in
the full Blueprint graph after repairing archived library CDO references.
PoseAgent and restored A_Sword references saved; reflection healthy. Owned
Play verifies independent S24/D13 planned slide ticks across all three agents
at170/330cm/s. Editor19216 remains open, clean, outside Play at60FPS. Normal
DLLs still require a build before cold launch. Evidence:
`Saved/Diagnostics/SlideSpeedPins20261014/`. No push.

## October14 simulated attachment fix and full audit

The attached sword now follows the actual holster. During attached alignment
and sliding, only upperarm_r/lowerarm_r/hand_r are temporarily kinematic native
bodies; their anatomical joints and servo drives suspend. The completed physical
clavicle and holster determine their real poses before publication. Release
restores simulation at unchanged pose/velocity and initializes existing FK
return from actual current/previous arm poses. Fully kinematic mode bypasses this
ownership path. Pre-attachment reach, lab/tuning, authored curves and NN handoff
remain unchanged. Direct equipment destruction now retires this ownership before
ordinary cleanup rather than faulting the shared world.

11 live captures/4,705 ticks/123 completed slides; ten interruption cases pass.
Maximum S local path error .00004615cm, native/query/display .00000417cm.
415 matched ticks at actual10 versus24.7FPS are identical. New attached-arm
stage .262ms mean/.358ms p95 across the three-agent test; no100-agent total-game
claim. D's existing2cm/5deg admission tolerance remains. Legacy native fixture
failures are explicitly retained, not called green.

Read the [full audit](SwordHolsterPhysicsAudit20261014.md) for all implementation
decisions, rejected trials, tests, performance scope and remaining boundaries.
[Compact receipt](../Tools/SwordHolster/AttachmentPhysics20261014.json).
Editor19216 is open, clean/outside Play, original60FPS restored. Final cleanup
guard is Live Coded; normal build required before next cold launch. No lab,
Blueprint tuning/wiring change or Git push.

## October14 S sliding hitch — original diagnosis (superseded above)

User observes S sliding hitches, cleaner in kinematic. Four owned Play captures:
650ticks sim/kin, then350ticks sim/kin retaining attached sword plus native
pelvis velocities. All3 agents and repeated S examined; no runtime edits.

The slide progress is smooth, but simulated sword/hand movement relative to
the actual holster is not. First player S ticks77/78 move the physical hand
4.624 then1.831cm; authored movement4.622 then1.834cm, grip residual
.005834/.000307cm. Thus the constraint follows the commanded motion closely.
After rotation/tip correction finishes, the expected sword path is a pure local
translation along the blade with the saved insertion curve. Across six S:
- simulated maximum per-slide path errors .499502–1.407471cm;
  rotation errors .234376–.327186deg;
- kinematic <=.000028cm and effectively zero angle;
- simulated grip residual <=.012127cm over these post-correction samples.

`ProphecySwordHolsterPose.cpp:527` RefreshGeometry predicts the physical pelvis
one tick using native linear/angular velocity and derives a holster pose from
it. The sword native kinematic body receives that world target in
ProphecyJoltBodyComponent::PrepareJoltWorldStep. The displayed holster remains
mounted to the actual completed physical pelvis. PresentSword then correctly
shows the completed sword body, so prediction errors become real sword/hand
motion relative to the holster. The first S post-correction sword angular
error matches20% of the independently measured pelvis prediction angle error
(to .000146deg in magnitude), consistent with current80% compensation.
Physical acceleration makes that prediction imperfect; kinematic mode uses
known authored pelvis transforms instead. This is an existing prediction-based
attachment inconsistency, not elbow return IK or a grip joint slipping.
Git blame dates the mounted-pelvis predictor to63c6065d0 (October13).

No implementation/tuning/assets changed. Do not hide it by disconnecting the
rendered sword from its body or adding grip smoothing. Next fix must make
holster, sword and gripping hand use a consistent mount for the physics step.
Editor stays open; owned Play ended;60FPS unchanged; dirty TestNN preserved;
full BP graph identical. Evidence SheatheHitch20261014: sim/kin.json,
sim-native/kin-native.json, steps.txt, summary.json and analysis scripts.

## October14 Unreal elbow port and body-pose refresh

### Current request: restore IK correction in both implementations

The user explicitly requested restoring the coordinated shoulder/elbow IK
correction in the lab and porting it to Unreal. The independent D/S checkbox is
under FK return controls → Inertia options, default on, soft zone15deg. Off is
unrestricted return. The forearm-only limiter remains deleted. This is the prior
IK algorithm, preserving wrist direction/orientation and allowing a small radial
reach adjustment near straight/folded; it is not a new hand-path design.

Native uses fixed-size per-arm plane-angle state and restores it during
speculative body-return probes. Correction runs after optimized FK and before
the existing FK-to-IK blend and wrist-axis turn. No per-tick allocations.
Lab8-case geometry,3600 inertia samples and recorded sword-arc tests pass.
Normal build/restart completed.128 variants/4800 samples pass native parity:
max .000089462cm/.000274273deg, duration error3.45e-15s.
The comparison exposed an existing spring fallback changing the non-inertial
hand offset length; it now uses the prepared fixed-length offset, matching the
lab. New correction normalization and exact half-turn axis match the lab too.
Owned430tick Play completed425 finite samples and D/S return phases. Editor26208
is open on TestNN outside Play; BP graph byte-identical, health status3, no dirty
packages, original60FPS cap restored. Normal DLLs current. User-requested Git
checkpoint includes current lab tuning, Blueprint and dependencies. Refresh lab.
Evidence: `Saved/Diagnostics/ElbowIKRestore20261014/`.

Main inertia strength has also been ported: Drawing0.5/Sheathing0.7, preserving
duration/decay timing and existing BP overrides. Continuous spring unchanged.
The implementation-only patch successfully loaded before the IK request; its
standalone live audit was interrupted by that request. Current normal build
includes it. Original Attack Recovery lab remains unchanged. Earlier removal
and “awaiting port” statements below describe the preceding state.

### Main inertia zero discontinuity — diagnosed after removal

**Lab correction now implemented for Blend + inertia:** Main scales the carried
angular and offset motion, using the existing full-strength decay envelope.
Return duration, timing curve, hold and decay timing do not change with Main.
0 and1 preserve old poses; intermediate values now have meaningful strength.
At.001 the reported first bend is+2.397deg, close to zero's+2.444deg, with the
same .637869725s computed return (including existing spine-angle time).
3600 continuity samples and448 old endpoint comparisons pass. No elbow limits
or other solver changes. Optional Continuous spring remains unchanged.
Unreal and original Attack Recovery lab are untouched; await lab review/port.

Current problem_4 at UE1138 bends+2.444deg at inertia0 versus−39.261deg
at.001;1e−9 is still−39.162deg. Main inertia selects full incoming velocity
for any positive value and changes its decay rate, without scaling strength.
The decay denominator has a .025 floor, so the positive-value limit remains
finite instead of approaching the hard-disabled zero case. Same expression
exists in native D/S return/hand return, still awaiting this port; do not
reintroduce elbow limits to hide this. See InertiaZero20261014 evidence.

### User-requested removal — current behavior

Both the experimental coordinated elbow IK correction and forearm bend limiter
are removed from the lab. Native limiter code/profile/state are removed too.
The native trial was never ported. Their controls are gone; old saved lab keys
are discarded. No replacement correction, bend constraint or smoothing added.
The existing FK-to-IK return and its signed-angle continuity, hand-root return
and sword arc remain. Native profile cleanup removes only elbowSoftZone entries;
user lab state, body poses and other tuning remain untouched.

Verification:1200 old-unrestricted comparisons have identical positions,
12 D/S cases pass, and browser tests cover all6 problem selections, deleted
controls, ordinary controls, reload/playback and sword arc. Deleted solver tests
are retained only as local historical evidence. Necessary normal build passed
in200.10s; editor restarted because retained native layouts were removed.
Native return oracle:32 variants agree within .00000353cm/.00000452deg;
ReturnPoleContinuity passes. The broader legacy NativeParity test is NOT fully
green: its untouched head and reach-duration fixtures differ by43.75deg/.2349s.
The old full fixture exporter calls removed `B.optimize`; only its return
samples were regenerated. No head/reach change or relaxed test thresholds.
Editor13852 reopened TestNN and owned260tick Play check completed:255 finite
consecutive samples, D/S return reached, no crash. Owned Play ended. Full BP
graph byte-identical, reflection status3, no dirty packages; user BP/map edits
were saved before the necessary restart. Normal DLLs current. Refresh lab.

The following trial descriptions are historical and superseded by this removal.

### Lab-only coordinated elbow trial and exact return cases

Current user review rejects the enabled trial's hand route. For saved problem_4,
the trial deviates up to42.956cm from the recording while retaining the
unconstrained FK wrist route. Removing inertia does not remove its broad sweep.
Preserving an unconstrained endpoint and bone lengths did not establish a good
return path. Latest sword-arc fix itself leaves wrist positions unchanged;
trial-off reconstruction now independently matches the full recording's final
visible hand rotation within .00000684deg, in all3 cases. This is diagnosis,
not acceptance or a new solver change. User tuning and Unreal remain untouched.

Sword-arc replay correction: the exporter uses native `LastBody`/`bodyPose`,
which is saved before `HeadStep` and `HandAxisStep`, not the final pose.
The replay incorrectly copied that intermediate hand quaternion and skipped
the independent hand return and sword arc. It now calls the existing
`applyHandRotation` and `prepareSwordPoint` stages used by normal D; no new
rotation algorithm. Signed speed, exponent and cutoff work in all3 recordings,
including fractional scrubbing, and arc changes leave every bone position
unchanged. The captured torso/neck/head remain intermediate body inputs;
this fix does not establish final head or full visible/physical pose parity.
All3 recorded cases pass numerical arc checks and isolated browser checks
for positive/negative speed, disabling, reload persistence and real playback.
Normal sword-arc regression also passes. Saved tuning and Unreal untouched.

Reload follow-up: captured-return model omitted `bladeLength`. Startup source
information called `.toFixed` on it, so refreshing with a captured case selected
failed even though switching into that case after normal startup worked.
Added actual `setup.bladeLength`; no formatter fallback/error suppression.
Browser regression reproduced the reported crash before the fix, then passed
reloading all3 recorded selections, readiness, playback and controls afterward.
Recorded arm parity and normal saved tuning unchanged. No Unreal changes.

Display follow-up: initial exact captures incorrectly used the old100cm lab
cube with unit scale, despite captures coming from the newer baked-size holster.
Read-only export of `/Game/_mygame/fake_holster` now supplies per-recording mesh
geometry (including changed pivot), shared by viewport/snapshot rendering.
Normal lab geometry/settings remain untouched. Recorded fully-seated grip
provides the seated sword transform, avoiding the old pivot-dependent offset.
Geometry dimensions2.825×7.6445×89.2197cm verified; integer/fractional replay and
full isolated UI pass. Screenshots inspected after fix. Source export script:
`Saved/Diagnostics/Elbow43020261014/export-captured-holster.py`; stored geometry
`Labs/SwordHolsterLab/diagnostics/captured-holster-mesh.json`.

User authorized trying IK correction in the lab before any Unreal integration.
`elbowIKCorrection` defaults true and is independently saved in D/S return
profiles. FK return → Inertia options → **Trial: preserve hand path with IK**
selects coordinated shoulder/elbow correction; false retains the old limiter.
The original FK wrist position supplies the target. A C2 rounded magnitude
softens straight/folded reach; elbow pole approaches the valid bend plane in
the soft zone. Plane interpolates from release toward current base-animation
plane, with angle continuity; neither release nor moving endpoint is replaced.
Wrist orientation is counterrotated. No shared Recovery engine/native change.

Geometry tests: eight frozen inputs (including reported658/1137 releases),
13520 synthetic samples,24 reconstructed motions,48 hand-inertia cases pass.
All15 captured returns tested separately: radial wrist adjustment≤.05842cm,
no sideways adjustment, lengths preserved, wrist orientation error<.000004deg.
Old45deg early-forearm-step regression still fails at agent1 tick181:47.04deg.
This is a reviewable experiment, not a claim of universally smooth motion.

User interrupted to require the problem motions themselves in the lab.
The normal Problem selector now includes3 additional exact captured-return
entries: player UE660, player UE1135–1138, agent1 fast trial elbow UE181.
First two default to the old correction, third to the trial. They begin15ticks
before actual release, retain captured torso/head/holster and regenerate the
right-arm return from the exact captured current/previous poses and live NN
base samples. Hand-axis rotation is regenerated with the normal lab pipeline
(see correction above); it was not present in the selected capture field.
Visible description explains that return controls apply while body/reach
controls do not rewrite recordings. Existing3 fully editable NN clips remain.
Timeline shows absolute UE tick; normal play/scrub/step/panels remain available.
Old-correction positions match recorded native arms within.00000673cm.
`test_problem_motions_ui.cjs` passes all6 choices, real playback, comparison
toggles, persistence, worker and normal-state restore using isolated storage.
Export script: `Tools/SwordHolster/ExportReturnProblems.cjs`.
No live state overwrite, Unreal action or push. User must refresh existing lab;
CUA failed to initialize with kernel-assets OS error3, so live refresh is not
claimed. Await user vetting before Unreal integration or more solver changes.

### Subsequent visible failures — current unresolved status

The initial completion/parity checks did not establish acceptable return motion.
The user's tick430 failure was reproduced in commanded poses and in an exact
lab replay of native release inputs: player tick424 forearm step65.39deg. The
limiter derived its bend plane from a nearly straight non-inertial baseline;
that plane changed57.62deg in one tick. A release-plane reference and minimal
3D direction correction replaced it in lab/native, followed by matching
projected baseline measurement. Both implementation-only Live Coding builds
succeeded without restart. Normal DLLs remain stale. Added six frozen release
regressions and13520 mirrored/spring/boundary checks pass; these are limited
checks, not evidence of universally acceptable motion.

User then reported the hand shooting sideways immediately after draw sliding
around660 and1135. Fresh1250tick capture reproduces this: player releases658
and1137. At660 the soft constraint displaces the wrist15.121946cm from the
same return with only the soft constraint disabled. At1138, first return tick,
it displaces the wrist16.936601cm and commands an11.937841cm hand step (physical
11.957066cm). This is not physics drift. Raw forearm inertia crosses backward
(-12.76deg at659, -38.69deg at660; -44.55deg at1138). Correcting that forearm
alone while retaining the upper-arm rotation breaks their combined wrist path.
It is a coupled-arm constraint problem; do not hide it with another hand blend.

Exact15-release replay of captured inputs matches native wrist positions within
0.00001cm. Comparison uses identical duration0.6s/current live NN poses with
only elbowSoftZone disabled offline; user settings/Blueprint are untouched.
Evidence: `Saved/Diagnostics/Elbow43020261014/release6601135.json`,
`release-analysis.json`, `release-fixtures.json`, `analyze-release.cjs`,
`inspect-soft.cjs`; earlier axis diagnosis in `baseline.json`/`replay.json`.
Owned Play ended, capture arrays released and original t.MaxFPS0 restored.
No runtime changes/push/restart for this latest diagnosis. A coordinated
shoulder/elbow correction to preserve wrist path would be a two-bone solve;
that design change needs to be explained, not silently introduced as FK.

The lab soft elbow barrier now runs in native D/S return, with independent
`elbowSoftZone` profile values (15deg default; 0 off). Both spring/world and
ordinary returns use it. Wrist counterrotation preserves authored orientation.
Fixed-size per-arm angle state replaces lab playback keys; held-grip reachability
trials restore that state before testing another candidate time. No extra
pose-history bank, timer or inactive work. Native already retained both FK/IK
angle branches; shoulder-coincident target handling was also brought across.
The previous elbow plane is transported into the current NN reference before
being used as the exactly-straight fallback, as in the lab.

Latest normal lab body values exported: clear right clavicle X=-17 for D/S;
seated right X=-37.3 D/-37 S; seated S spine X=-40 and pole34.1. Full independent
body settings are in the JSON. Blueprint overrides preserved: D duration0.6s,
holster compensation80%, S kinematic fraction0.5, NN ranges D1/1 S0.7/1.
Lab code/settings were not edited. No push.

Verification: normal build145.39s succeeded; four isolated tests passed,
including64 full lab/native comparisons across idle/walk/run and the three
problem inputs, D/S, entry inertia on/off, both skeleton layouts and return
variants. Reach/slide/finish ticks exact; max0.000088771cm/0.000219392deg.
The added raw problem-input tests initially failed because the historical
fixture captured the mount with identity root before applying the recording's
initial heading. `export_accepted.cjs --problems` expresses each clip in its
entry-root frame on BOTH sides; relative transforms and subsequent root motion
are preserved. Raw recordings/lab remain unchanged. Production Begin already
sets the root before capturing authored state. Root-frame regression also passes.

Live checks: simulated430ticks/9 completed actions; kinematic310ticks/4 completed
actions,425/305 consecutive samples and finite poses. Third kinematic agent
remains in its FIRST S reach (hand-target error7–9cm), never entering return;
that separate reach issue was left untouched. An interim progress update said
six kinematic completions incorrectly and was explicitly corrected. Simulated
grip tracking max1.509854cm/3.247759deg. Authored parity does not mean exact
physical tracking or universal visual perfection.

The isolated suite preceded the final straight-elbow fallback normalization.
That implementation-only adjustment compiled/reloaded via Live Coding170.64s,
no object changes, no second restart. **Normal DLLs are now stale: build before
cold launch.** Editor12548 remains open TestNN. User dirty PoseAgent/TestNN were
saved before the one required retained-layout restart; full Blueprint graph
byte-identical afterward, status3, no dirty packages. Final post-patch simulated240tick check completed6 actions with235 consecutive
finite samples. Capture arrays released; pre-test t.MaxFPS0 restored. Editor
remains outside Play, graph byte-identical/status3/clean. Full evidence in
`Saved/Diagnostics/ElbowPort20261014/`.

## October14 lab elbow correction and soft bend limit

User authorized fixing both angle-wrap paths and adding a smooth elbow limit.
`fkreturn.js` continues both the moving target angle and the FK→IK blend angle
against chronological keys. Fractional/backward sampling uses the surrounding
keys, not the latest queried pose. A target exactly at the shoulder uses the
current arm direction for the existing minimum reach constraint, avoiding a
world-axis fallback. No new timing/easing/speed cap is added.

FK return → Inertia options → **Elbow soft limit zone** defaults to15degrees,
independent D/S;0 disables it. It softens both extension through0 and folding
through180degrees. The reference bend plane comes from non-inertial FK in the
upper-arm frame; straight-reference fallback uses captured/previous local bone
geometry. Bend angles are continued across turns before constraining them.
Below a knee k, with x=(k-angle)/k, the mapped bend is k/(1+x+x²): positive,
monotone, matching position/velocity/acceleration where it joins identity.
The knee is bounded by the baseline bend, preserving release and final poses.
Only the forearm bend is corrected; the hand's local rotation counters that
correction to keep its existing authored world orientation. Both arms share
this mechanism; lengths, torso and shared Recovery.js remain unchanged.

Validation:
-13520 synthetic samples: mirrored arms,0.1..179.9deg starting bends,±300 and
 ±2800deg/s, both inertia methods, reverse sampling, exact release/endpoints,
 finite poses and lengths (worst error<1e-12cm).
-24 captured-input reconstructions:3cases×D/S×both planners×soft on/off, finite
 complete motions, deterministic reverse/fractional samples, exact final arm
 positions. Reported problem2 seam elbow10.793→3.348cm and forearm43.375→10.142deg.
-48 hand-inertia regressions retain original wrist-step results after adding
 wrist counterrotation. Test contract now permits forearm rotation correction
 when hand-offset inertia changes its direction; unrelated bones/elbow position
 remain exact.
-16 hand-root,8return-curve+2sequence,8hand-axis and pole-reference tests pass.
 UI test uses isolated verified storage: real advancing playback, panels,
 editable inertia, per-case persistence/reload, worker rebuild, normal restore.
-Old test_fkreturn entry equality and test_early_return source-frame identity
 also fail unchanged code. The old12case IK test's30deg all-motion cap remains
 failing: old61.38deg max, new46.63deg in a continuous fast walking arc. Its
 hand path/length/root/reverse-sampling assertions pass. No universal visual
 perfection claim; these failures are not hidden by changing their thresholds.
-20 local full problem2 preparations: median21.2ms versus22.0ms prior; same
 cached playback architecture. This is not an Unreal crowd benchmark.

Evidence/backup: `Saved/Diagnostics/ElbowSmooth20261014/`. No Unreal changes,
restart, asset edits, user tuning overwrite or push. Problem motion UI is now
an editable reconstruction in the main lab, not the earlier diagnostic clip.

## October14 lab problem_2 tick71–72 diagnosis

Current Problem checkbox case Agent2 (problem_2), Draw with inertia.5 and
FK→IK .25..1 reproduces the user's live tick72 pose within1.2e-12cm.
This is a distinct snap during FK→IK interpolation, not the initial extension
through straight. The elbow is54.177deg bent at71 and59.723deg at72.
`fkreturn.js:applyArmIK` takes a freshly wrapped signed angle from the current
FK elbow direction to the desired IK elbow direction, then multiplies by the
partial blend weight. That signed angle changes−148.394→+178.688deg; the
continuous value would be−181.312deg. Multiplying equivalent angles by a
fraction makes them inequivalent: at tick72's.205559 weight the bend plane
changes by74deg solely from the representation wrap. Spine step1.44deg and
hand step5.80cm remain smooth; elbow step10.793cm and forearm step43.375deg spike.
An isolated in-memory module experiment continuing only this angle, with all
inertia/settings/timing retained, yields4.309cm elbow and6.408deg forearm steps;
hand position and elbow bend stay identical. No production fix applied, no
Unreal edits/builds, and no tuning changes. Evidence and instrumentation:
`Saved/Diagnostics/ElbowSnap7172/{state,desktop-view,analysis}.json`, `analyze.cjs`.

The former read-only Problems tab is superseded by the user's requested Problem
checkbox beside the normal motion selector. Captured NN clips now feed the
normal planner with normal editing controls; reconstruction is not exact physics
replay. UI work was interrupted by the request to diagnose this snap first.

## October14 first-draw elbow diagnosis and lab captures

Current user scene: compensation80%, S kinematic fraction.5, D NN blend1/1,
Blueprint Set Sword FK Return Duration overrides D to.6seconds. Preserve those
values; prior78%/.8/.5–1 descriptions are earlier measurements.

Three first draws reproduce a commanded bend-side reversal immediately after
release: player two-tick turn~135deg at178–179, NPC single-tick~172deg at178
and~174deg at180. Physical tracking closely follows the command. FK-to-IK has
not started at this first reversal. A separate later swing occurs during its
blend; do not claim that later motion diagnosed/fixed by this investigation.

Imported actual release/current+previous authored poses and underlying NN poses
into the unchanged lab FK return adapter. Including the BP .6second override,
all three early elbow trajectories match Unreal within.0000023cm. Retained compact
fixtures in `Labs/SwordHolsterLab/diagnostics/elbow-cases.json`.
The main lab now has **Problems → Problematic motions**, also accessible at
`http://127.0.0.1:8818/#problems`. Three selectable first-nine-tick cases use
the existing viewport, timeline, playback speed and keyboard controls. Original
versus forearm-angular-inertia-off is a diagnostic comparison, not a solver fix.
The torso is recorded; the right arm is evaluated through the unchanged lab
return adapter. Equipment and physics are not replayed in these short clips.
Leaving restores normal motion/time/camera/speed/panels. Normal saved settings
are frozen while inspecting captures; snapshot and remote motion capture are
unavailable there to avoid mislabelling a diagnostic clip as normal D/S.
The rejected separate HTML/controller have been removed. Regression
`Labs/SwordHolsterLab/test_problem_motions_ui.cjs` passes all3cases×2variants,
captured elbow parity, standard transport, settings/disk preservation and normal
motion restoration. No production solver or profile edit.

All three share excessive extension momentum through straightness. Initial
forearm angular correction magnitudes~1496/2709/2829deg/s, with two release
elbows already within6.52/3.67deg of straight. Isolating only forearm angular
inertia reduces first-nine-tick bend-direction max steps86/172/174 to3/18/41deg.
Removing translation inertia or upper-arm twist does not remove the reversal.
An elbow-aware extension-inertia treatment is the proposed general correction;
no anatomical constraint, speed cap, damping change or finished fix was added.

The earlier temporary UE all-inertia-off control also reset D duration to the
file's.5; it is not a clean single-variable proof. The subsequent offline lab
component-isolation tests retain the correct.6 and establish the cause.
No further Unreal build/restart after the user redirected to the lab. Both
owned captures completed/ended. UI all3cases×2variants passes without errors;
geometry screenshot verifies display only, not subjective motion acceptance.
Evidence/scripts: `Saved/Diagnostics/ElbowDraw20261014/`.

## October14 D return pop

Current idle draws reproduced an elbow/upper-arm target discontinuity around
absolute ticks196–198, also in kinematic mode. Two signed-angle branches in
FK-to-IK return crossed ±180 degrees. Blending their wrapped values made the
elbow jump; the simulated torso/neck reacted on the following tick.

Keep the goal and blend angle continuous against their own preceding value,
reset at return entry. No velocity cap, pose smoothing, tuning change or extra
solve. Removed the unused previous base pole. The lab remains untouched.

Three isolated native tests pass, including both seam directions, repeated
turns, moving root frames, the recorded branch and reset behavior. Live9draws
simulated and6kinematic complete with unchanged initial completion ticks.
Worst seam elbow step drops roughly18→10–11cm and upper-arm step37→17deg;
physical head angular-step change drops6.4→1.38deg. The residual fast continuous
arm swing was reported. User reviewed and accepted the current motion before
requesting breathing speed controls.

One required native-layout restart; normal build100.22s succeeds. User BP/map
saved beforehand; graph unchanged except unused InputKey output None values
serialized as blank. Editor24960 open TestNN, Play off, clean/status3. Normal
DLLs current at this checkpoint. No push. Evidence:
`Saved/Diagnostics/DrawPop20261014/`.

## October14 Draw Sword speed-pin cleanup

**Draw Sword** now takes only **Agent** and **Sheathe**. Removed the misleading
Max Reach Speed, Max Reach Rotation Speed and Sliding Speed pins: the configured
lab profile already supplies separate D/S speeds. The existing no-profile native
defaults100cm/s,180deg/s,60cm/s remain internally; current lab-profile behavior
and tuning are unchanged. The old editor import no longer writes those pins.

Applied with Live Coding, no restart or retained-layout changes. Corrected two
editor-helper compilation errors before the successful72.41s build/reload.
Refreshed the existing node, repaired library defaults and verified the complete
Blueprint graph differs only by those three removed pins. Existing Agent,
Sheathe, execution and result connections are preserved. Reflection status3,
native_properties0/pin_types0; two-argument reflected call verified. Saved the
user's PoseAgent edits before reload and the refreshed Blueprint afterward;
their dirty TestNN map remains unsaved. No motion-suite rerun for this signature
cleanup. Editor18792 remains open outside Play; normal DLLs are stale again and
must be rebuilt before a cold launch. No lab/tuning edits or push.

Evidence: `Saved/Diagnostics/SwordSpeedPins20261014/`.

## October14 early sheathing kinematic fraction

**Set Sword Holster Profile** now exposes **Sheathe Kinematic Fraction**,
default0.8, accepted range0..1. It uses the existing curve-modulated S reach
progress, on authored ticks. Zero takes ownership as reaching begins; one waits
until reaching completes. Attachment takes ownership earlier if its existing
admission gate passes first. Drawing still takes ownership at grip.

This calls the existing mount takeover without starting rotation compensation:
the holster keeps its current world pose and follows the pelvis from that pose.
Compensation still begins at attachment/tip alignment. Release and cancellation,
including interruption between the early switch and attachment, use the same
return-to-class-rest duration and restore the selected physics mode/joint.
The value is copied with the action profile; changing it affects the next action.
No extra per-agent clock, callback, solver or pose history. Lab unchanged.

One required retained-profile-layout restart; normal build187.69s succeeds.
Existing Blueprint automatically reconstructs the new pin at0.8; saved it after
verifying every old pin/default/link unchanged. Live345ticks/three agents:
six S reaches switch on the first sample crossing0.8, three D grips retain their
existing timing, all nine releases restore physics after15ticks. Compensation
stays off throughout early S ownership. Separate145tick run covers fractions
0/0.8/1 and three cancellations (two before attachment), including selecting
kinematic or physical while temporarily held; all return to the selected mode,
no accumulated joints and finite consecutive poses. These are mode/lifecycle
checks, not a claim that every visible jitter is eliminated.

Editor26036 open TestNN, Play off, normal DLLs current, BP healthy/status3,
no dirty packages. No lab changes or push. Evidence:
`Saved/Diagnostics/HolsterEarly20261014/` (capture/analyze scripts and receipts).

### Fractional compensation checked in live slides

User questioned whether the holster was completely frozen or the return blend
was overriding compensation. Read-only capture of the current scene (three
agents, six S/D slides) confirms weight0.779999971 throughout every slide;
mount return is inactive and the NN blend is0 in these windows. Measured
root-relative holster excursion / pelvis excursion is0.220000029 in all six.
Example player S ticks64–87: pelvis7.210487deg, holster1.586307deg. Physical
swing is absent while kinematic, but the remaining22% of pelvis rotation is
applied. No runtime/Blueprint/tuning change or restart. Evidence:
`Saved/Diagnostics/HolsterCompensation20261014/`.

## October14 physical holster slide override

Physical holsters temporarily become kinematic at S attachment/tip alignment
or D grip. The current world pose is preserved; the original pelvis joint is
suspended before the next native physics step. Grip rotation compensation uses
the existing setting (current78%). Release or cancellation starts the existing
return-to-class-rest motion (current.25seconds/15ticks); physics and the original
joint resume afterward if still selected. A selection made during grip wins
after release. Repeating the same mode call cannot cancel the automatic return.
Originally kinematic holsters retain their prior compensation fade.

The first live test exposed incorrect relative rotation on return: changing
`SetUsingAbsoluteRotation` alone left the transform cache unchanged, allowing
the subsequent world-pose setter to early-out with a world quaternion still
stored as relative. Next tick produced a170degree deflection. Use the engine's
`SetAbsolute` cache update before restoring the world/relative pose, at both
compensation entry and release. No cap, corrective blend or motion retiming.

Validation:

- Physical12 slides and kinematic12 slides on three moving agents: finite,
  consecutive captures, correct mode/compensation, no accumulated joints;
  all12 physical resumes occur15ticks after release. Max physical hand-grip
  error1.662cm; this is not a claim of perfect hand tracking.
- Leeway enabled only in temporary PIE instances: three S attachment/alignment
  phases and slides pass, including compensation during alignment.
- Six cancellations (S/D): ordinary cancellation, selecting kinematic during
  grip, and selecting kinematic then physical. All return to rest and the selected
  mode; immediate holster change<.000001cm/.000004deg. Same-mode calls every tick
  tested in normal runs. Registry handles can still be reported on the admission
  tick; existing constraint preparation retires them before the next native step.
- Three existing native regressions pass: StandardComponents constraint frames,
  ReturnBlend and ReturnPoleContinuity. No new per-agent idle callback; the shared
  return callback retires when no return/backend transition remains.

**Unresolved separate case:** changing the whole character to Kinematic during
active D/S causes the sword body to fault the shared Jolt step with “Collision
synchronization lost its source or Chaos simulation was enabled externally.”
Physical re-enable then fails because stopped clients remain. It also reproduces
with an already-kinematic holster (no physical-holster takeover); the holster
itself is forced kinematic and reaches rest correctly. The sword mode-refresh
path is unchanged. Do not treat this as verified whole-character mode switching,
or silently cancel/restart D/S to hide it; get direction before changing that
behavior. Failed S/D and kinematic-holster control recordings are retained.

Saved user PoseAgent/TestNN before one required retained-layout restart.
Normal build135.72s, then implementation-only Live Coding160.72s and113.28s,
both successful reloads without object changes. Editor23968 open TestNN, Play
off; full graph byte-identical, status3/no stale types/no dirty packages.
**Normal DLLs stale: build before cold launch.** No lab/tuning changes or push.
Evidence: `Saved/Diagnostics/HolsterSlideMode20261014/` (build/native, before-cache
failure, five passing live captures/summary, failed-character-switch S/D,
control-character-kinematic, and final graph check).

## October14 independent holster physics

**Set Holster Simulate Physics** takes Agent and Simulate. The class holster's
simulation setting is the initial selection. Character Kinematic forces the
holster kinematic but retains the selection; returning to Physical restores it.
Call this node for mode changes rather than toggling the component directly.

Physical to kinematic preserves the current world pose, suspends the authored
pelvis joint, attaches to PhysicalMesh/pelvis and returns to the class viewport
placement over the existing **Holster Return Duration**. Current .25 means15
unpaused world ticks. Physical resumes from the current pose with the original
constraint frames/drives; it does not recapture rest anchors from a deflection.
Changing back during a return cancels that return. Physical activation requires
Jolt and an authored holster/pelvis joint; failure returns false.

D/S follows the actual physical holster during reach. At S attachment/tip
alignment or D grip, it temporarily switches the holster to kinematic, preserves
its current world pose and suspends the authored pelvis joint. Existing rotation
compensation then runs throughout the grip/slide. The selected simulation mode
remains remembered; even compensation0 still gets the temporary kinematic hold.

At release, a previously physical holster stays kinematic while returning to
the class viewport placement over **Holster Return Duration**, then resumes
the original joint frames/drives if simulation is still selected. Cancellation
uses the same return. A mode selection during grip applies after release;
repeated calls requesting the same mode cannot cut the return short. Character
Kinematic still forces holster kinematic. Originally kinematic holsters retain
their existing compensation fade and stay kinematic. The temporary override
adds no ordinary-idle tick work or extra joint.

The mesh pivot and user class placement are unchanged. Startup restoration: a detached
simulated holster must receive the pelvis-relative rest transformed to world,
not that local transform interpreted as a world position.

One shared tick callback exists only while a return or backend transition is
pending; it is removed when idle. World/actor teardown clears retained state.
No lab, tuning or graph changes. Saved user PoseAgent/TestNN before the required
retained-state restart. Normal build250.83s passed; after a stalled startup and
user-authorized restart, editor9036 is open on TestNN outside Play. Low-space
dialog was dismissed by the user. Normal DLLs are current.

Validation in `Saved/Diagnostics/HolsterModes20261014/`:

- Native StandardComponents constraint test passes suspend/resume with exactly
  preserved anchor frames.
- Three agents,33 mode calls: all succeed; immediate pose changes below
  .000001cm/.000005deg. Includes interrupted returns, forced kinematic, retained
  physical selection, and retained kinematic selection. Return completes in15
  ticks; joint count0 in kinematic and1 after physical resumes.
- Current physical-holster setup:383 samples through tick400,9 completed D/S
  actions; maximum constrained hand error .08047cm/.34390deg.
- Actual character/holster kinematic control:223 samples through240,6 completed
  actions. Another223-sample run switches the holster at60/65 during S sliding
  and158/161 during D sliding:6 actions complete, release ticks166/166/167
  unchanged; maximum grip error .08084cm/.34420deg.
- Final full Blueprint graph byte-identical, status3/no stale native types,
  no dirty packages. These tests establish mode/constraint lifecycle and the
  current D/S cases, not universal visual or velocity continuity. Startup logs
  still contain existing unsupported-MACD admission warnings; current agents
  nevertheless enter Jolt and live grip joints are verified.

## October14 D release: failed Jolt startup and false kinematic classification

The new level `fake_holster` mesh has query geometry but no effective solid shapes,
even though its component requests QueryAndPhysics. The scene importer rejected it
and aborted Jolt FightSetup. D/S then misclassified Chaos Physical as kinematic
because it only checked whether Jolt was enabled. No grip joint was created;
at D0% the sword snapped to the lagging physical hand (up to13.20cm blade-tip
step and10.23deg rotation).

Scene admission now checks the actual native shapes: purely non-simulation
geometry retains its UE queries and observation, without importing a fabricated
solid or aborting other actors. Physics rebuild can admit newly added solids.
Unsupported/probe/invalid geometry still follows strict capture. This check runs
on admission, not every physics tick. D/S checks the actual simulation mode and
rejects simulated admission without active Jolt instead of taking a kinematic path.
No mesh, collision setting, Blueprint, lab, tuning or release blending was changed.

Live Coding159.27s, no restart/layout changes. Two native scene tests pass,
including preserved query hits and subsequent solid admission. Current unchanged
scene400ticks completes9actions with automatic Jolt startup; three D releases at
166/166/167 have real joints and sword step<=.06429deg, hand tracking<=.04032cm
and.065deg. Actual kinematic control240ticks completes6actions on the same release
ticks; blade-tip steps5.1546–5.1558cm versus simulated5.1802–5.1820cm
(baseline13.135–13.2021cm). These are final slide displacements, not zero-motion
requirements. No universal visual-perfect claim. Earlier pivot captures below
were Chaos Physical incorrectly labelled kinematic; their geometry result remains.

Evidence `Saved/Diagnostics/SwordRelease20261014/`: current, modes, startup,
jolt-control, fixed, kinematic, summary, final and native-test receipts.
User's unsaved PoseAgent/fake_holster/TestNN and exact graph preserved. Editor25668
remains open, Play off; normal DLLs need rebuilding before any cold launch.

## October14 holster pivot/scale capture correction

The user replaced the holster mesh, baked its dimensions into the mesh at scale1,
and changed its pivot/viewport placement. Placed agents retained the former mount.
Capture restored the class mount before measuring SwordRef. Its simulated blade
stayed in the old world pose, producing a false entrance43.871269cm from the
authored one on all3agents. Independently expressing the old blade-base point in
the new mount reproduces the erroneous local coordinates to.000004cm.

Capture now measures seated transform, marker and blade length before restoring
the class mount. No pivot offsets, scale multiplier, layout changes or motion
retuning. The real mesh origin remains the stabilization pivot. Live Coding
134.84s succeeded without restart; normal DLLs still need building before cold
launch. User's unsaved PoseAgent/fake_holster/TestNN and complete graph preserved.

Correction: these captures were Chaos Physical, incorrectly labelled kinematic by D/S.
Original243ticks left all3agents reaching. Corrected
463tick replay completes8actions, including S and D for every agent; entrance
error stays below9e-14cm. Blade length89.3492cm and normal sword scale unchanged.
This verifies the geometry defect, not universal motion quality: one first D
takes174ticks to reach, and two later D reaches remain active at capture480.
No change to FK pursuit/arrival rules or lab tuning was made to conceal that.
Evidence `Saved/Diagnostics/HolsterPivot20261014/` (inspection, mount-check,
before/after/after-repeat, analysis, final).

## Blueprint FK return duration

**Set Sword FK Return Duration** overrides the selected action's base return time:
`Sheathe=false` changes D, `true` changes S. `Duration` accepts 0.1..5 authored
seconds (60 unpaused game ticks per second); invalid values return false.
Call it after **Set Sword Holster Lab Profile** and before **Draw Sword**.
It changes only that agent/action's configured duration; active actions keep
their captured profile, and loading a lab profile again replaces the override.
The lab's angle-dependent extra time, inertia amount/decay, curves and NN blend
fractions stay unchanged. This is the base FK duration, not inertia decay time.
There are no new retained fields or recurring work.

## October14 accepted lab return port

**Root omission corrected and live-verified:** the earlier oracle included `root`, while the live
25-bone NN/PHAT pose omits it. Bone-name guards silently disabled hand-axis,
FK/IK and independent hand rotation in live use. Completion/position checks
missed this. The controller now uses explicit current/previous character mesh
frames. Four native tests pass:40 recorded cases (20 using the exact live order),
signed hand-axis/root-motion covariance, head-root invariance and NN blend.
Live sim and kin each completed6actions/243ticks; all3agents activate IK and39
angular samples per mode match the saved sigmoid profile within.000002415deg.
The requested turn is111.5967deg; simulated wrist angular tracking error stays
below.66543deg during the hand-axis lifetime. Earlier recorded-input results
remain valid but did not prove live activation. Lab and tuning are unchanged.
One necessary retained-layout restart; normal build77.44s. Editor25668 open
TestNN outside Play, clean/status3, graph values/wiring preserved. Evidence:
`Saved/Diagnostics/SwordRootReturn20261014/` (`angular-summary.json`, native,
motion-result, sim/kin, final-check). No universal physics/visual-perfect claim.

The approved lab revision `a42b66717cfd98cdefcfd247fa31de215b237857a6c064591ccef1b664795eb4`
is now implemented in the native controller. No lab motion/tuning files were changed.
`Set Sword Holster Lab Profile` loads independent D/S `armIKEnabled`,
`armIKStart`, `armIKEnd`, plus drawing `swordPointSpeed`, `swordPointExponent`,
`swordPointCutoff` from the existing JSON export. No extra Blueprint nodes.

The released-arm return captures its actual outgoing root-local FK pose at
blend Start, using bracketing ticks for fractional starts. Its wrist path then
reaches current locomotion at full return; the Start/End window blends ownership.
Bend directions and their angle branch exactly follow the accepted lab, including
its documented limitations in other configurations. Fingers/twist children keep
local transforms. The left arm and held grip retain existing behavior.

The drawing hand-axis turn postmultiplies hand-local X rotation after release.
Signed speed, sigmoid integral and cutoff match the lab. At cutoff its reached
rotation and preceding velocity seed the existing one-joint return over the
remaining interval, toward the original moving wrist path. This is applied after
saving the controller's unmodified pose history, and before the existing NN blend.
There is no future-pose lookup, Control Rig pass or idle history recording.

Latest exported drawing return: base duration .5s, easing .5, inertia .5,
decay .1, FK/IK .25→1 enabled; hand-axis 800deg/s, exponent1.5, cutoff .4.
Sheathing stays independent (duration .9s, early start .7, IK disabled).
The user's current native NN windows D(.8,1)/S(.8,1) are preserved; they blend
onto live NN and therefore intentionally differ from the lab near completion.
Unreal continues to use the actual holster/mesh pivot and live NN inputs.

Normal native build succeeded. Recorded-input AcceptedMotion (20 cases: idle,
walk/run, D/S, entry inertia, root-hand alpha, spring/world/full/early return)
and ReturnBlend tests pass. Reach, slide and completion ticks match exactly;
maximum bone error .000036141cm/.000096140deg. This establishes authored
controller parity for those inputs, not perfect physical response or every
possible tuning. The accepted lab's known other-case large arm steps are not
silently modified. Evidence: `Saved/Diagnostics/AcceptedReturnPort20261014/`.

Live verification after saving: 9 simulated actions over403ticks and6 kinematic
actions over303ticks completed on the current scene, with no missing ticks or
nonfinite poses. Maximum right-hand target/mesh discrepancy was .31424cm in sim
and .000000304cm in kinematic. No visual-perfection claim. Existing basic profile
pin changes were numeric formatting only; new return tuning lives in the JSON.
Both current NN blend ranges (.8,1), higher solver checkbox and all graph links
were preserved. User BP/map edits saved before the one necessary restart;
editor21432 remains open on TestNN outside Play, clean/status3, graph unchanged
after tests. Startup low-space dialog was dismissed; no further restart.

## October14 NN blend ranges — current implementation

**Set Sword Holster Profile** replaces the two scalar cutoffs with **Draw NN Blend
Range** and **Sheathe NN Blend Range**. X starts the linear blend; Y finishes it.
For example, (.5,.8) leaves FK unchanged through 50% of the elapsed torso-return
interval, then increases the NN weight from zero to one by 80%. It uses the
existing 60-tick clock, independently for D/S. Valid values are .5 <= X <= Y <= 1;
(1,1) retains the full lab return. Each action captures its configured range.
The user confirmed that blending will not begin while grip still needs a separate
return, so there is no second delayed arm-blend mechanism.

The NN continues running beneath D/S. During the window, parent-local transforms
blend the authored pose onto that live NN pose, preserving segment lengths and
normal root motion. The whole upper body, including the head, participates.
Grip protection remains until slide completion. At Y, the published pose is
already the current NN pose and the authored override retires. This replaces the
hard-transfer history/reseeding/one-tick repeated presentation implementation;
there is no extra inference or history collection. The lab is unchanged.

Current BP saved **D(.5,.9), S(.5,.8)**, preserving the user's last scalar
endpoints. Every other graph default/link matches; healthy status3, no stale
native properties/pin types, no dirty packages after tests. Normal build277.60s
passed; one required layout/reflection restart, editor23068 open TestNN outside
Play. No lab changes or push.

Native ReturnBlend validates independent weights, unchanged pre-window/lower
poses, segment lengths, rigid-root invariance and exact NN endpoint/retirement.
AcceptedMotion's20 recorded lab cases still match exact event ticks and prior
pose tolerances. Live current setup: simulated15actions/583ticks and kinematic
9actions/363ticks, no missing ticks,421 interior blend samples with zero weight
error, all24 actions complete, none overlap grip. Drawing player seam now slows
right-hand speed4.92→1.19→.34cm/s rather than the former12.8→0→31.7cm/s kick.
**Linear pose weighting does not guarantee endpoint velocity continuity:** the
player's later S window ends with right-hand speed117.86→66.59→.03cm/s. This is
recorded rather than hidden behind unrequested easing. No full crowd benchmark
or universal simulated tracking/smoothness claim. Evidence:
`Saved/Diagnostics/SwordReturnRange20261014/` (native, verified.json,
current-verification.json, kinematic-verification.json, final-check.json).

## October14 former hard-handoff velocity seam — historical diagnosis

User rejected the handoff's velocity seam. Current D.9/S.8 capture reproduces
both hands moving outward after drawing. At player absolute206, left hand speed
is1.9→0→20.8cm/s and right12.8→0→31.7cm/s. There is a duplicated presentation tick,
then the NN prediction changes direction/speed. Previous/current core input
features match recorded outgoing transforms within1.22e-7; this drawing example's
hand-history errors are below.000106cm. Removing the NN delta in offline decoding
leaves only.00056cm wrist displacement. Applying the actual delta reproduces the
outward motion; reconstructed predictions match all15 handoff future endpoints
within.000026cm. Correct history alone does not enforce velocity continuity.

No runtime, lab, tuning or asset changes this diagnosis; no build or restart.
Current editor left open outside Play. Evidence:
`Saved/Diagnostics/SwordHandoffVelocity20261014/`. The prior checks below establish
pose continuity, not a fully smooth handoff. Do not silently add a correction blend.

## October14 early handoff repair and separate D/S cutoffs — superseded

**Set Sword Holster Profile** exposes **Draw FK Return Cutoff** and
**Sheathe FK Return Cutoff**, defaults1. Both existing Blueprint literals were
copied from the user's latest0.8, preserving all other defaults and wiring.
The old internal `FKReturnCutoff` pin remains Draw for link compatibility;
`SheatheFKReturnCutoff` is independent. Each action snapshots its own value.

For cutoff below1, the torso return fraction requests one whole-upper transfer
at the next normal NN update; FK continues until consumed. Current and previous
actual authored poses span one policy interval in root-local space. Both NN
history samples, pelvis heading/base and presentation starting endpoint are
seeded together. A still-held arm follows the sword through slide completion;
its release transfers only right-arm history without reseeding the torso.
No extra inference, time compression or blend. Cutoff1 and lab unchanged.

Three native groups pass: independent D/S cutoff selection, pose/motion history
including fractional intervals and grip-only transfer, plus20 recorded lab cases
with unchanged exact event timing.18 live actions complete with no missing ticks:
kinematic idle.5; simulated run Draw.25/Sheathe.75; simulated idle0.23 measured
handoff boundaries preserve parent-local transforms within3.4e-13cm/.000002415deg.
All20 captured NN-owned pre-release held frames retain the grip joint.

Limits: this establishes pose continuity and correct input history, not exact
velocity continuity of subsequent NN predictions. The boundary presents the
last authored pose once before interpolation advances; following speed comes
from the model response. Simulated running return hand tracking reaches2.4922cm.
No new full performance benchmark or exhaustive interruption matrix this pass.

Final normal binaries current; editor10492 open TestNN, Play off, healthy saved
BP/status3, clean packages, graph unchanged after tests. The required initial
native-layout restart was followed by an avoidable helper-migration restart:
a changed console-command delegate remained registered with its old signature
through Live Coding. User explicitly reiterated not to close Unreal needlessly;
acknowledged and recorded. Final helper build76.43s. Lab untouched, no push.
Evidence: `Saved/Diagnostics/SwordNNHandoff20261014/`, `split/verified.json`,
`split/native/automation/index.json`, `live/` and the three transfer reports.

## October14 early cutoff: teleport confirmed, unresolved

User reports upper-body teleport with cutoff.5. The current implementation forces
return progress to1 at the selected fraction, replacing the unfinished authored
pose with the independently running NN pose. The .5 test verified this switch,
not continuity; its passing result is not evidence of a smooth handoff. The saved
half-cutoff capture contains spine steps up to18.75deg. D/S isolates its authored
upper pose from recurrent NN input. A true early handoff needs to transfer the
current pose/motion into NN recurrence and presentation history while retaining
the still-gripping arm. No fix or new blend has been applied. Full-return recorded
parity below remains valid; early-cutoff smoothness is explicitly not verified.

## October14 return controls port and cutoff — prior verification

Native D/S loads the lab's independent return timing curves and drawing
`handRotationFKAlpha`. Drawing's root-local hand rotation starts after release,
follows the current NN hand destination, and leaves wrist position on the FK arm.
The one-joint return uses the same curve, duration, inertia and spring method;
alpha1 skips its work. The rejected exponent is removed and is not ported.
Latest saved D/S poses, speeds, return values and curves are exported by
`Tools/SwordHolster/SyncLabProfile.cjs`; curve bypass also includes return curves.

**Set Sword Holster Profile → FK Return Cutoff** is an Unreal-only override,
default1. It switches each FK return to the current NN pose when that fraction
of its original elapsed duration is reached; it does not accelerate or reshape
the preceding motion. Body return and the separately released arm each use their
own return interval. The gripping arm remains on the sword through sliding.
Head look, sword unshrink and holster rotation restoration retain their own
completion clocks. Lowering the cutoff deliberately truncates the pose and may
produce a discontinuity; no extra blending is inserted. Applies on the next D/S.

Normal build242.04s passed; interactive editor23480 is open on TestNN, outside
Play, no dirty packages, status3/native_properties0/pin_types0. The existing node
was reconstructed and saved with cutoff1, Higher Solver Accuracy stilltrue,
and current profile literals (including78% holster stabilization). User's dirty
Blueprint/map were saved before the required restart; original bytes backed up.
All other graph defaults/wiring are preserved. Post-PIE audit differs only by10
empty lines in one dumped string field; nonblank graph content is identical.

**Verification:**20 recorded-input cases (idle/walk/run D/S, entry inertia off/on,
plus early/full drawing return ×local/world inertia ×blend/spring with alpha.35)
match exact reach, slide admission, slide duration and completion ticks. Maximum
pose error.000036141cm/.000096140deg. Two additional pre-existing implementation
differences surfaced and were fixed: whole-body return must disable FK wrist
inertia, and world-inertia grip return must sample its ancestor frames internally
before publishing only the grip branch. No lab motion change beyond removing the
requested exponent. Cutoff automation verifies unchanged first-half motion and
exact current-NN destination at.5/0. Lab16 hand cases,8 return-curve cases/two
sequences and isolated UI/persistence checks pass.

Six live idle/walk/run ×kinematic/sim cases completed72 D/S actions on three
agents, with no missing captured ticks or nonfinite poses. A separate simulated
run cutoff.5 completed6 actions. Testing temporarily disabled only the known
Cube obstacle in owned PIE; saved scene/collision is unchanged. **This is not
perfect physical parity:** simulated hand tracking reached2.3584cm and neck
tracking5.9458deg. One kinematic running reach also contains a67.53deg parent-local
upper-arm twist (NPC_C_3 absolute49); wrist rotation step there is2.93deg. This
occurs before slide/return and was not changed or concealed by this return port.
A new reach-motion experiment would still need to start in the lab.

Evidence and compact receipt: `Saved/Diagnostics/FinalReturnPort20261014/`.
`Saved/Diagnostics/SwordHolsterParity/` is the reusable oracle output; earlier
 dated evidence remains unchanged. No fresh performance benchmark or push.

## October14 parity port — controller matched; physical neck residual remains

### Solver comparison checkbox (October14)

**Set Sword Holster Profile → Higher Solver Accuracy** defaults off. On requests
the existing attack/defense policy (10 velocity / 32 position iterations) from
successful D/S admission through the full return. Off leaves configured ordinary
counts in effect (normally 0/0 overrides, meaning world defaults 10/2). Changing
the profile applies to the next action. Cleanup restores configured counts on
completion, cancellation, hide/drop and mode changes; another active attack or
defense keeps its own override. No polling or new per-tick work is added.

Controlled run tests changed only solver counts at tick480, with identical pose
history beforehand. Across three agents in return ticks499–550, 10/32 reduces
worst neck_01 angle error25.8205→6.3432deg and worst head position error
1.5075→.2621cm. Self-collision suppression is identical to baseline; damping
removal does not resolve it; more position passes help substantially whereas
more velocity passes alone do not. This demonstrates insufficient positional
convergence as a contributor, not exact physical parity or zero residual.
Evidence: `Saved/Diagnostics/NeckTracking20261014/special-result.json` and
the corresponding damping/contact/velocity/position controls. This checkbox is
an Unreal physics comparison; lab motion and tuning are unchanged.

Normal build243.82s and `Prophecy.Jolt.SpecialSolver.Lifecycle` pass, including
D/S overlap with attack/defense, repeated notifications and custom-count restore.
Existing Blueprint checkbox saved unchecked; every previous graph line is unchanged.
Three-agent run S/D cycles pass checked and unchecked, with effective counts verified
each tick and restored on both completions; three-agent hide interruption restores
counts too. Test fixture reapplies its temporary checkbox for D because the saved
Blueprint reconfigures the unchecked profile between actions. Editor11260 remains
open outside Play, no dirty packages, status3/native_properties0/pin_types0.
Map/sword/PHAT/lab settings/runtime JSON hashes preserved. No new performance
claim or push. Evidence/build log:
`Saved/Diagnostics/HolsterSolverCheckbox20261014/`.

Native FK wrist interpolation now uses the lab's neutral-joint reference, including
reach duration and entry inertia. The runtime JSON/exporter carries `wristReference`;
profiles without it retain the earlier selection. No new Blueprint pin or IK path.

Identical recorded-input tests exposed another difference: native held early FK
return overwrote arm roll after the pole solve, unlike the lab. Removing that
extra step restores matching return and release inertia. Alignment's existing
roll transport remains. This supersedes the held-return part of the October13
roll fix below; live simulated releases must be rechecked for its original symptom.

All12 idle/walk/run ×D/S ×entry-inertia cases pass. Reach, slide, slide duration
and completion ticks match exactly; upper-body max error.000036141cm/.000096261deg.
Normal DLLs rebuilt successfully. Interactive TestNN is open, outside Play.
Idle/walk/run in kinematic mode each completed two S/D cycles on three agents.
Simulation did the same with an unobstructed path: 72 completed actions across
these six configurations. Saved-scene walk/run obstruct the third NPC at Cube;
disabling only that collider in owned PIE removes both stalls. The saved scene
and collision settings were not changed.

For unobstructed simulated releases, hand tracking error is at most .076cm/.313deg.
The earlier large release spikes were not reproduced. Maximum grip residuals
are .372cm idle, 1.244cm walk and 1.658cm run; rendered/native sword position
separation stays below .000005cm. These are physical residuals, not exact parity.

**Remaining physical neck deviation:** run neck_01 reaches 3.385cm/25.821deg
from the commanded pose, while head orientation remains within 1.5deg (position
within1.634cm). Idle also has a brief10.631deg head tracking error at entry181.
Owned-PIE neck/head collision suppression gives identical run results; freeing
all three neck/head joints leaves neck error25.833deg. Neither intervention
explains/removes the residual. Target neck parent-local offsets change by less
than .016cm, excluding a large changing target bone length. No physics tuning,
PHAT change or pose correction was applied to hide this. The subsequent solver comparison above demonstrates insufficient positional
convergence as a substantial contributor; do not claim complete simulated1:1 parity.

Saved BP/map/sword/PHAT/lab settings hashes are unchanged; no dirty packages.
Normal DLLs are current, Blueprint status3/native_properties0/pin_types0.
No new performance claim or push. Live captures, tracking summaries and the two
neck controls are in the evidence folder below.
Evidence: `Saved/Diagnostics/SwordParity20261013/`.

## Saved body/inertia tuning sync (October13; editor closed)

The runtime JSON now contains the current lab's independent D/S body poses,
entry inertia and both return profiles. Drawing return is inertia1, easing0,
decay.1. These fields load through the existing Set Sword Holster Lab Profile
node; no Blueprint rewrite or build is needed. Other runtime tuning is preserved.
JSON values and loader support verified offline; live execution deferred during
robotics training. The lab FK wrist-arc code correction is not part of this sync.
Evidence: `Saved/Diagnostics/SwordProfile20261013/verification.json`.

## Drawing IK trial removed (October13)

User chose FK. The lab trial and checkbox are removed. Unreal's trial was already
reverted and `ProphecySwordHolsterPose.cpp` still matches its pre-trial backup,
retaining the earlier head/holster root-frame and arm-roll fixes. Trial-only
native tests are absent; rollback normal build70.63s passed previously.

The subsequent wrist-arc correction is **lab only**: see the
[lab contract](../Labs/SwordHolsterLab/README.md). No Unreal launch/build or native
motion edit in this turn; another session owns the closed-editor robotics work.

## Physical neck correction (October13; current)

Subsequent current-scene D/S loops and release spikes were separate authoring
errors: world-fixed head/holster history opposed root turns, and a nearly straight
held-arm solve injected axial roll into return inertia. Both are now corrected;
head/holster history follows the root and the held solve preserves segment roll.
Sim and kinematic captures cover591 consecutive ticks each with unchanged user
inputs. The reported missed drawing grip remains deferred by the user. Lab,
Blueprint tuning and PHAT were not changed by these fixes. See the linked report
for exact measurements, test status and build state.

The original PHAT now contains neck_01→neck_02→head. Both necks permanently
exclude head/clavicles; head–clavicle exclusions apply only during D/S and restore
on completion/interruption. Player head error at289 is .055cm; physical feedback
uses both real neck bodies. Lab and Blueprint motion settings are unchanged.
See [decisions, saved/build state and validation](PhysicalNeck20261013.md).

## Original stationary head/neck diagnosis (historical; before correction)

Two independent problems are now isolated in the unchanged stationary second S:

**PHAT provenance clarified:** this is NOT a Jolt import omission. The original clean
`/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin` asset itself defines bodies
neck_01/head and the direct head↔neck_01 constraint; no neck_02 body. The importer
copies every Physics Asset body and each live constraint's endpoints. This topology
is independently documented in committed `Tools/SwordHolster/NeckLimits20261011.json`
(commit822cf423, October11). The asset file's last-write timestamp is July10,2026;
that is supporting metadata, not a versioned proof of topology since July. The
asset was Git-ignored until the pre-change checkpoint `3c8d11b6` force-added it;
its original author/date/reason cannot be established from earlier history. No unsaved changes on this PHAT at inspection; unrelated dirty
agent BP/map preserved. Do not describe this as the physics backend removing neck_02.

1. **Head/right-clavicle self-contact causes the extra bobble.** Actual hit events
   name only `head` and `clavicle_r`, player284–292 and NPCs283–293. Holster arm
   collision suppression starts at `upperarm_r` (`ProphecyLimbCollisionLibrary.cpp`),
   so the clavicle is omitted. Disabling ONLY that pair gives an identical physical
   trajectory to disabling every neck/head contact through325. Head travel283–293
   falls2.456159→.693067cm (command.701616cm), position error289 falls1.303158→.346655cm.
   These are owned-PIE diagnostic overrides, not saved changes.
2. **The requested neck chain is incompatible with the physical joint.** Both lab
   and native head authoring distribute rotation across neck_01/neck_02/head. The
   current PA_UEFN_Mannequin has neck_01/head bodies but no neck_02 body, with a direct
   neck_01→head joint. Asset head anchor is zero; neck_01 anchor is
   (9.926639,-.543086,0)cm. Requested world transforms place those anchors1.340642cm
   apart at289. Without the contact, physics closes them to.004718cm while the neck
   turns6.796841deg away from its command. Turning off only the head's linear drive
   in that contact-free test reduces neck error to3.656910deg, but increases head
   position error to1.033735cm. That is evidence of conflicting targets, not a fix
   or a proposal to remove head magnetisation. Free angular limits still retain the
   positional joint connection. A three-bone authored chain cannot be assumed to
   match a two-body articulation automatically.

Both actual neck/head angular modes are Free at289; configured global/body drive
strengths are1 and mode1. Enlarging head/neck recurrent-feedback tolerances produces
zero physical trajectory difference. Hit-event logging also preserves the baseline
trajectory. Earlier attribution of the entire visible difference to neck rotation
was incomplete: removing contact improves head position while neck angle error grows.

No runtime source, lab, tuning, Blueprint or asset edits; all temporary tests ended,
editor left open outside Play. Fix choice remains for user discussion. Do not silently
change lab authoring or PHAT. Evidence and rerunnable analysis:
`Saved/Diagnostics/HeadParent29020261013/root-cause.json`, `analyze-root.py`,
`baseline-detail.json`, `no-head-clavicle-detail.json`, `no-contacts-detail.json`,
`head-angular-only-detail.json`, `no-feedback-detail.json`, `hits-bones2-detail.json`,
`physics-asset.t3d`. Asset export was read-only. Earlier reflection-only frame reads
were unsupported/protected; final anchor analysis uses the successful standard T3D
export, checked against the physical joint's measured closure.

Prior comparison: same setup kinematic head path.705621cm versus current lab.589126cm;
kinematic positional tracking<9e-14cm. Live lab stabilization.78 differs from native.48;
preserved; activation is later than the divergence. World-head rotation excursion in
the selected window is not greater than lab, so do not claim all rotational motion is worse.

## Accepted-lab port integrated (October13)

The accepted lab is frozen and remains unchanged. Native source now shares its
linear FK reach progress, independent attached translation/rotation limits,
shrink duration, optional leeway alignment, configurable direct-entry tip
threshold, and slide from the reached depth. The saved lab profile supplies
these values. Earlier descriptions below are historical where they conflict.

Unreal deliberately uses the mesh/component origin as its stabilization pivot,
per the user's clarification. The lab axial-pivot percentage is neither exported
nor exposed on the Unreal node. The class viewport placement remains authoritative.

User-approved timing: capture the preceding NN pose after a request, admit the
player on the next unpaused tick, and spread NPC admissions over ticks1..4.
Pending requests retain only their last pose; skipped ticks require a fresh
consecutive pair. Active target refits run at action-relative4,8,12…; the former
independent world-slot refit scheduler is removed. Entry inertia uses measured
preceding-tick movement rather than an interpolation-derivative estimate.

Twelve recorded idle/walk/run D/S comparisons with saved entry inertia on/off match every
reach/slide/completion tick, with maximum pose difference.000036cm/.000078deg.
This comparison exposed and corrected missing torso ancestor rates when seeding
arm-return inertia. Tip alignment and stagger lifecycle tests pass.

The existing BP profile is saved with25% shrink/.25s shrink/.5s unshrink,
48% stabilization/.25s return, attached150cm/s/200deg/s, leeway off/tip2cm.
All other defaults and links are preserved; per-action profiles load from JSON.
Six live idle/walk/run × kinematic/sim cases complete two cycles on three agents
each. Eight alignment/slide × hide/drop/mode/reset cases verify removed grip
joints, restored angular limits and original holster placement. Mode/reset apply
at tick boundaries; the user's looping BP may start another action afterwards.
Tests distinguish a fresh action from incomplete cleanup.

Remaining physical limitation: with saved Cube collision enabled, the third
running agent stops at X≈−876cm and its second sheathing attempt stalls. The
same owned-PIE test completes on all agents with only that obstacle disabled.
Saved map/collision untouched. Completed sim grip error maxima:.70cm idle,
1.47cm walking,2.16cm unobstructed running; rendered/native sword gap<.000005cm.
This does not establish universal physical parity or artistic motion perfection.
No fresh full-runtime crowd FPS benchmark was run; old references are preserved.

Normal runtime build-entry.log is current. A later editor-only value-refresh
helper compiled/reloaded via Live Coding (85.02s), with no runtime layout change
or restart. Rebuild that editor helper normally before the next cold launch.
Final TestNN: open, no Play, no dirty packages/maps, saved healthy agent BP.
Lab code and motion tuning are unchanged; user camera/playback changes preserved.
Logs still contain unsupported-MACD scene-admission messages and sword rebind
failures during world teardown; no physics fallback was added to hide them.
Evidence: `Saved/Diagnostics/SwordAcceptedPort20261013/` completion.json,
live-final-verification.json, lifecycle-verification.json and editor-final.json.

## Earlier port (October13)

Sheathing now captures the sword at the full rotation-tolerance gate, attaches
without a world-transform jump, aligns the tip in the holster frame, then slides.
Alignment freezes shrink and uses the existing reach speed limits on the normal
60-tick clock. Body motion continues under its angular bound; slide entry uses
the body pose actually reached. After capture, the sword path is authoritative:
an unreachable wrist cannot drag the sword away from the holster-local path or
block tip arrival. The hand follows through the existing joint, whose frames are
updated at capture to preserve the actual grip; the authored arm uses that same
grip. The lab now also gives the holster-local sword path authority during
alignment/sliding, with arm tracking error exposed rather than stalling the
sword. See [lab ownership correction](LabSwordOwnership20261013.md). Full
lab/Unreal pose parity has not been established.

**Mesh/native synchronization:** during constrained alignment/sliding the mesh
presents the completed Jolt sword pose. Sim predicts the holster from its real
physical parent, not the NN pelvis. Passive holster/hand attachments synchronize
both mesh and native collider, including axial resize and handoff. Repeated
moving cycles measured position mismatch below.000006cm and reported rotation
below.05deg. Native hand-grip constraint error is separate and remains nonzero;
see [verification and limitations](SwordPhysicsPresentation20261013.md). This
supersedes the old unconditional attached-kinematic publication rule below.

**Set Sword Holster Profile** has two additional pins:

- **Grip Holster Stabilization Percent**, default0:0 follows the pelvis;
  100 holds the captured world rotation throughout grip, including S tip
  alignment. Intermediate values mix those rotations. Translation follows pelvis.
- **Holster Return Duration**, default.25 authored seconds: after sliding ends,
  restore the class-authored local rotation over this duration. Interruption
  restores the mount and rotation inheritance immediately and preserves a
  released sword's world transform.

The existing class viewport placement is authoritative at game reference capture;
old placed-instance overrides cannot replace it. Runtime stabilization never
writes the class template. The lab's separate always-on stabilization is still
not imported. **Visualize Sheathing Leeway** now turns the cone green at rotation
admission and continues through tip alignment; the tip distance is a separate
alignment readout, not the former2cm pre-attachment gate.

[Implementation decisions, verification and limits](HolsterTipAlignPort20261013.md).

## Previous port (October12)

**Drawing grip conflict corrected:** both temporary grip actions now derive
the sword-side joint frame from the authored grip and native body origin.
Drawing previously captured transient acquisition/physics-publication error,
opposing the authored wrist through sliding. Matched-prefix before/after test:
first release physical step14.93→2.99deg with unchanged2.96deg command;
9 repeated D releases end within.504deg wrist error. No damping, speed changes
or extra per-tick work. S pursuit/slide-entry issues remain. The lab now has
an optional **No cheat** causal mode; off preserves the original reference.
[Implementation, tests and remaining differences](NoCheatGrip20261012.md).

**Sheathing entry visualization (October12):** `Visualize Sheathing Leeway`
is an optional Blueprint Tick call (Agent defaults to self). It reads the live
S profile, currently15deg, and only draws during S reach. Cyan cone/axis shows
the maximum blade tilt and perfect alignment; the green/red ray shows actual
blade direction but its color uses the **full quaternion rotation** gate,
including roll. The adjacent roll dial's cyan arc is the remaining allowance at
the current tilt, not an independent15deg roll limit. The2cm mouth sphere,
actual tip dot/connector, distance text and authored-body ready/waiting label
show the other entry conditions. Display Length40cm only scales the illustration;
advanced Duration0 is one frame. No planner mutation, persistent controller,
tuning/acceptance changes or unused per-tick work. Uses the same actual component
transforms/scales as `TrySheathe`, not its next-tick predicted pose.

**Latest incremental pass:** the holster is now a non-physical pelvis-socket child
in the PoseAgent Blueprint; the user subsequently deleted its former motor
constraint. Runtime D/S does not require it. The user's
new placement is copied into the lab. Unreal's arm-plane/pole-budget changes are
reverted to the restored lab rules; rigid mount prediction and slide-entry pole
capture are aligned. Early-return arm parity is still incomplete. See
[current fix, measurements and pending question](HolsterRigid20261012.md).

**Later October12 rollback:** at the user's request, the lab motion code is back
to pushed checkpoint `e0da908c`, with current user settings preserved. Unreal
retains the port changes. The shared-solver descriptions and parity evidence
below describe the pre-rollback verification, not agreement with today's lab.
Tell the user before changing reference-lab behavior.

The lab/saved tuning and PoseAgent Blueprint checkpoint is pushed as `e0da908`.
The new native port uses independent Drawing/Sheathing body, elbow, speed and
return profiles, authored spine/clavicle endpoints, captured FK entry inertia,
and drawing hand rotation/translation return inertia. Native compensation follows
character heading while cancelling pelvis gait. The left arm keeps its live
local locomotion. Saved tuning is D260/900/250, S230/600/150, compensation .96,
entry inertia1/.5s, axial shrink15%, unshrink .5s. Blueprint wiring is preserved.

`Tools/SwordHolster/SyncLabProfile.cjs` exports current saved tuning and neutral
body references to `Content/locomotion/SwordHolsterProfile.json`. A configured
lab profile supplies action-specific speeds through the existing Draw Sword
function. Head/FK clocks, gaze, curves, early return and physical cleanup retain
the established native implementation. Unreal follows its actual holster;
**lab holster rotation stabilization is intentionally not ported**. Lab sequence
order is preview composition; Unreal callers invoke the same D/S actions.

Both implementations now transport the arm's existing bend plane before solving
a guide. This prevents a nearly straight arm from acquiring a large axial twist
when the target moves across its previous elbow direction. There are no new
knobs or changes to saved tuning. Numerical/live verification is recorded; see
[the implementation and test annex](SwordHolsterPort20261012.md) for current
results, remaining limits and build state. The following dated sections describe
the prior implementation and are superseded where they disagree.

## Previous lab port (October11)

**Overnight follow-up:** the current profile uses230cm/s reach and600deg/s
rotation (the two corresponding Blueprint literals were saved); head vertical-axis
tilt45deg, factory70. All other saved wiring/tuning is preserved. The tilt bound
compares head localX with spine_05 localX, preserving vertical twist/yaw;90 disables
it. See [overnight decisions, evidence and remaining limits](SwordHolsterOvernight20261011.md).
The dated measurements below predate this follow-up.

Moving Sim holsters are sampled from native COM/angular velocity one60Hz tick
ahead for planning, preserving actual pelvis lag. Kinematic planning carries the
completed holster through previous/current NN pelvis frames. Acceptance still
uses actual physical geometry. Sliding sword and hand address the same upcoming
physics step. Sheathing retains the ordinary nominal grip; drawing still captures
the current placement. Reach refits keep the preceding elbow solution, and sliding
guides rejoin the integer sampling grid after a fractional correction cutoff.

Head authoring and current-NN head coordinates share a signed world reference.
Their separate weighted factors cancel exactly through the whole neck at handoff;
spine-parent cancellation is distributed independently. This avoids the old
combined-log full turn that could leave each neck bone120deg wrong while the head
itself matched. Current gaze, speed/exponents, independent timing, segment lengths
and fractional lab playback are preserved. No new public controls or motor tuning.

The current lab profile is loaded in Unreal through the existing `Set Sword Holster Lab Profile` call and `Content/locomotion/SwordHolsterProfile.json`. Blueprint links and literals are unchanged. Current tuning:15% axial shrink, .5s unshrink,250cm/s reach,2500deg/s reach rotation,150cm/s slide;15° sheath acceptance tolerance, .45 rotation-correction time fraction,1000deg/s spine/clavicle speed, early return S=.7 and D=.9. The exported lab gaze170 is metadata: Unreal uses each agent's current live gaze.

The port includes tip-at-mouth acceptance while aiming perfect, continuous captured entry position/orientation/scale, unrestricted signed spine twist, coordinated speed-bounded clavicle/spine, and elapsed-time slide rotation correction independent of the sliding curve. Head movement has its own60-tick clock, continuous signed world-space rotation, inherited-spine cancellation, neck detail, gaze-dependent in/out speeds, shared exponents, look-in arrival timing alpha, sheathing tip-to-mouth target alpha and current-gaze look-out. There is no artificial head-angle clamp.

Body FK return begins on the first authored tick crossing its action's actual curved insertion threshold. The gripping clavicle/right arm stays on the sword until the slide endpoint, then returns from that exact pose using the same return engine. A torso return that would exceed the held arm's reach waits until it can continue. Head and FK return are not sped up by reach/slide curves. The live NN keeps its normal clock and receives no procedural upper-body feedback.

The optimized shoulder-only search, prepared quaternion arcs, output cache and four-slot crowd scheduler remain. Native live sliding uses two rolling FK destination guides, including the independent rotation cutoff; early-return overlap solves against the current returning shoulder. It does not retain a full animation bank per agent. Completed controllers retire their pose work. New per-agent return scratch reuses the existing return evaluator instead of duplicating a second implementation.

### Sim sword drive correction

The first crowd run exposed a stalled NPC: the hand reached its authored target, but the sword drifted about76° from its grip orientation and its tip stayed57cm from the entrance. Replacing the ordinary hand grip had removed its existing sword drive follower. The temporary joint alone did not preserve tracking under the current physics setup. During dynamic sheathing reach, the temporary grip now registers that same drive follower; its offset updates only when shrinking changes joint geometry. The follower is removed when the holster takes ownership or when the action is canceled. Joint handles are reused, and no PHAT, motor, magnetization, shrink or tolerance values were increased.

After the correction all three agents complete S and D at saved tuning. Kinematic and Sim both slide for31ticks. Sim sheath entry is at50/51/52 across agents versus51/52/52 in the matching kinematic capture; drawing completion is identical469/470. Body return begins20ticks into S at insertion.705333965 and28ticks into D at.903225806; the hand joint remains until slide end. Maximum authored grip error after slide entry in this setup is.142cm kinematic/.282cm Sim. The same sword actor, axial scale, holster parenting, collision restoration and joint cleanup remain.

### Right wrist limits during D/S (October15 follow-up)

At the user's request, the existing scoped neck/head snapshot now also selects
the `hand_r`–`lowerarm_r` joint (either connectivity order). All three angular
motions become Free on physical D/S admission and remain Free through the full
arm/head return. Completion and the existing interruption cleanup restore the
exact entry swing/twist motions and angles, including custom or already-Free
settings. Repeated requests retain the original snapshot. Other joints, linear
anchors, drives and the saved PHAT are unchanged. Mode transfer restores before
backend teardown and re-applies on physical rebind while the action is active.

The retained snapshot type/map/inline capacity are unchanged; the fourth joint
uses the existing array's heap overflow. This is an implementation-only Live
Coding change. `Tools/SwordHolster/VerifyWristLimits.py` checks full S/D returns,
repeat requests and hide during either return using owned PIE instances, with
optional custom wrist settings. It temporarily skips the two-ball fixture only
on the PIE player; it does not edit/save the user's Blueprint or map.

**Verified:** four owned-PIE checks pass (498 sampled action/completion checks):
complete D/S with existing and custom entry wrist limits, plus hide during each
return with custom limits. Complete cycles sample38 D-return ticks and50 S-return
ticks each; every active wrist is Free and all six entry fields restore exactly.
Custom entry is Limited17 / Locked11 / Free8, proving restoration does not replace
the snapshot with PHAT defaults. Repeated requests during return preserve the
snapshot; every unrelated joint remains unchanged. Existing native batched apply
mirrors UE profiles only after a successful Jolt update.

The current user graph starts S during initialization, so the probe waits for that
scene action to finish, then captures the baseline and runs its controlled D/S
pair. Earlier probe setup/timing failures were corrected without changing runtime
code or the user graph. Evidence: `Saved/Diagnostics/SwordWristLimits20261015/`.
Live Coding succeeded in268.36s after memory-related retries; patch18 reload
reported no object changes. No restart or asset save. Final TestNN/outside Play,
no dirty packages, full Blueprint graph byte-identical, reflection status3 with
native_properties0/pin_types0. Normal DLLs remain stale; build before cold launch.

### Neck/head limits during D/S (October11 follow-up)

EventGraph `SetUseAuthoredAngularLimits(false)` disables all angular limits after `begin_f2`, but the connected `tick debugging` chain later calls `ResetPhysicalJointAngularLimits` on `neck_01`, `neck_02`, and `head` (nodes94,96,82). Reset means restore PHAT defaults; the active neck/head joints are Limited30/20/20 while the right-arm joints are Free. This is not a failure of the global disable node.

The authored head/neck path is continuous, but those physical bounds oppose it. At current saved gaze the player's physical head has an18.315° return step and up to53.858° tracking error; the corresponding large step is not present in the commanded pose. A diagnostic freeing only neck_01/head during D/S reduces these to3.423° and4.669°, restores the limits at completion, and has maximum.131° head step over the next10ticks. Other agents also complete. Disabling the optional predictive joint-limit correction alone leaves the18.32° jump, so that feature is not its cause. Extreme normalized gaze-1 produces roughly53° physical steps with the existing limits despite commanded steps below5°.

The user subsequently authorized freeing these joints only during D/S and restoring them even on interruption. The native controller now captures the active angular modes and angles of the actual neck/head joints at admission, sets only their angular modes to Free, and restores the captured values when the complete D/S action (including head/FK return) ends. Queued requests and kinematic actions do not change limits. The existing Blueprint reset calls and PHAT assets remain unchanged.

A small new per-action snapshot avoids changing retained controller layouts. It stores only joint identities and six angular fields, with no per-tick scan or profile application. Begin/end use one batched native update each. The shared cleanup path restores limits on hide, drop, invalid/destroyed sword, failure, cancellation and actor teardown. Mode transitions restore before backend teardown captures source profiles. Repeated requests do not recapture the temporary Free state. Restoration touches only matching neck/head joints, preserving unrelated live joint values. Custom entry settings are restored exactly rather than blindly replacing them with PHAT defaults.

Nine owned-PIE checks pass: complete S/D with default and custom limits; hide during S reach/slide/return; drop during S slide; mode switch during return; sword-actor destruction during reach; and hide during D slide with custom limits. Every sampled active neck is Free, unrelated joints stay unchanged, and prior angular modes/angles are restored on cleanup. The final three-agent Sim replay completes both actions; player physical head return peak is3.424° and tracking error4.680°, versus18.315°/53.858° before the override. Live Coding succeeded with no reflected object changes and no restart. Full graph/asset preservation and final motion capture are recorded in `Tools/SwordHolster/NeckLimits20261011.json`.

### Verification, performance and save/build state

Twelve isolated native tests pass, including3600 independent lab head samples and500 slide-geometry samples: max head/neck rotation error0.0000073°, neck position0.00000054cm, zero head-completion tick differences; slide position below2e-13cm and rotation0.000003°. The480-case bone-order matrix covers63,540ticks with no timing/position/length/inertia mismatches. Existing curve, FK kernel, return, reach-continuity, stagger, physical-feedback and60-tick-clock checks pass.

Owned Play tests pass: three-agent kinematic and Sim cycles, repeated S/D with pause and duplicate calls, cancellations during reach/slide/return, walking in both modes, and restoration from kinematic to Sim. The cap60/cap20 Sim replays (observed39.23/19.99FPS) have exactly identical target, future, physical and equipment transforms and phase ticks. This verifies frame-pacing independence in the fixed1/60 setup; it is not sustained60FPS coverage. High-gaze actions complete; those captures predate the authorized neck-limit override described above.

Current100-agent procedural benchmark, six scenarios/seven repeats: median mean.638–.772ms/tick, peak1.273–1.502ms, admission peak1.251–1.347ms. This includes procedural admission/math, excludes NN/physics/rendering/equipment/publication costs, and is not a whole-game FPS claim. Historical benchmark files are preserved under the raw evidence's `prior-metrics` directory.

One required restart handled retained controller/profile/return layout changes. The user's dirty TestNN was backed up and saved before closing. Normal build succeeded; TestNN reopened. The implementation-only sword drive fix subsequently compiled/reloaded through Live Coding with no object changes, avoiding another restart. **October11 visible-window recovery: normal build succeeded (65.86s), including the later sword-drive and neck-limit fixes.** The prior editor was responding but hidden. With the window-control helper unavailable, it was closed normally with no dirty packages/Play and relaunched using explicit `-WindowStyle Normal`, normal UI flags and `/Game/testNN`; PID17644 has a main window titled GameAnimationSample3 - Unreal Editor. Reflection status3/native_properties0/pin_types0 and unchanged saved assets verified. Evidence: `Saved/Diagnostics/VisibleEditor20261011/`. The complete BP graph and saved map/agent/sword bytes match the preserved baseline, with no dirty packages after verification. Owned Play ended. Live lab settings/camera/snapshots were untouched.

The lab uses recorded idle/walk with a pelvis rest mount; Unreal uses live NN movement and a simulated holster. Exact absolute reach ticks for different input poses are not promised. Online head arrival timing uses the planned perfect-reach deadline; the offline lab can know its earlier acceptance tick in advance. Numerical verification does not claim human motion acceptance. Receipt: [LabSync20261011.json](../Tools/SwordHolster/LabSync20261011.json). Full evidence: `Saved/Diagnostics/SwordLabSync20261011/`. Recreate the independent lab oracle with `node Tools/SwordHolster/export_channels.cjs`; run the existing `RunParity.ps1` in an isolated process against current normal DLLs.

## Historical blade-direction hitch diagnosis (October11)

The earlier capture identified a separate entry-placement correction after the old hard hand gate. The new tip/angle acceptance and captured residual slide path above supersede that placement logic. Original evidence remains in `Saved/Diagnostics/SwordBladeHitch20261011/`; the user had clarified that their reported hitch was before sliding, so the earlier transfer correction was a separate finding.

## Reach continuity fix (October11)

Two baseline replays reproduced target discontinuities before sliding. Sheathing replaced its FK destination abruptly on each four-tick refit: the player's late upperarm steps were3.386/3.159deg and wrist4.106/3.037deg. During drawing, a destination crossing180deg relative to the original wrist made shortest-path interpolation reverse its chosen arc, producing a27.541deg local wrist step at absolute205. The physical hand followed these authored changes; the draw joint was not created until215.

`ReachArm` keeps each destination quaternion in the hemisphere of its previous destination, then samples the original-source interpolation with that continuous arc. Existing slide-guide scratch is reused to spread destination corrections over at most four authored ticks during reach; the interval shortens at the arrival deadline, and the current endpoint is sampled exactly at that deadline. Slide entry resets the scratch key. There is no retained layout change, additional body search/endpoint solve, new per-agent allocation or user control. Scheduling, reach/slide curves, head/return clocks and physical ownership are unchanged. This is interpolation between refits, not distance-triggered easing.

The slide arrival gate still requires the reach clock to finish, authored hand position within2cm, physical hand position within2cm and orientation within5deg. Drawing also waits until the body turn is within0.25deg. A genuinely unreachable pose still waits; no larger tolerances or hidden shrink were introduced.

Native pure checks cover16 signed/directional180deg-crossing cases (192 destination calls, exactly the existing cadence),48 paired legacy/optimized-kernel lifecycles and the480-case/61,290-tick bone-order regression. The wrist counterexample falls from38.55deg to2.8deg maximum step, exact endpoint error<0.000003deg; lengths and lifecycle event ticks agree. `Prophecy.Sword.VerifyReachContinuity` invokes pure routines without editor Automation. The legacy test lifecycle now shares the new reach staging while retaining independent pre-optimization kernels; historical performance receipts remain historical.

Three complete owned Sim captures (caps60/20/60, actual19.95–36.41FPS) each tested three agents through S and D:9 cycles/18 returns. All target/future/physical samples and action ticks match exactly across replays. Player S66/97/159 and D215/246/308; NPCs complete S155,D308/309, unchanged from baseline. At the two late S refits the player's upperarm steps fall to0.910/1.573deg and wrist1.426/1.527deg. Drawing wrist204–206 is now7.641→5.571→3.899deg rather than7.515→27.541→4.284deg. Physical hand-target position error at205 falls0.309→0.031cm. Head/neck return maxima remain1.83334/1.32140deg per tick. Fixed world delta1/60 throughout. These are numerical continuity checks, not human playback acceptance or sustained60FPS coverage; remaining normal motion and physical tracking error are not claimed eliminated.

Final Live Coding compile80.49s/reload succeeded without warnings or reflected object changes. Editor stayed open; user's already-dirty BP/TestNN remain unsaved, graph and map/agent/sword/profile hashes identical, owned Play ended, cap restored60. Normal DLLs remain stale and require a normal build before the next cold launch. No kinematic rerun or fresh CPU benchmark for this patch; the added work is bounded three-joint interpolation, with unchanged search/solve counts.

[Receipt](../Tools/SwordHolster/ReachContinuity20261011.json); raw evidence `Saved/Diagnostics/SwordReachJitter20261011/`. Reproduce with `ProbeHeadFps.py --arm --name <name> --fps 60 --ticks 340 --draw-at 185 --output Saved/Diagnostics/SwordReachJitter20261011`, then `SummarizeReachJitter.py`. Native wrapper `Prophecy.SwordHolster.ReachContinuity` is available for the next isolated normal-build suite.

## Head/neck bone-order fix (October11)

The correction is loaded in editor PID12024 through a layout-safe Live Coding patch (compile45.35s; reload succeeded, no reflected object changes). **Normal DLLs remain the older staggering build: build before the next cold editor launch.** No restart, asset save, physics/tuning change or Blueprint edit was needed. Full graph and map/agent/sword/profile disk hashes match the pre-fix baseline; the user's already-dirty Blueprint and TestNN remain unsaved. Owned Play sessions ended and FPS cap returned to60.

`ProphecySwordHolsterPose.cpp` now builds parent-first traversal indices from the actual parents, leaving all pose indices and physics mappings intact. The upper traversal is prepared once at admission and reused by body propagation, return-rate propagation, ordinary local/world return, spring integration, twist correction and final mounting. Return entry also traverses the complete hierarchy in parent order before reading parent quaternions. Invalid/cyclic parents reject admission. Stack-inline scratch covers the current25 bones; no retained layout change, per-tick sorting or new scheduling work.

The native pure-math regression covers480 cases and61,290 ticks: real25-body PHAT order (head15,neck_02=22), reversed order and eight seeded shuffles; idle/walk, D/S, local/world, ordinary/spring, inertial/zero-inertia and twist-removal paths, moving base and different head exponents. Compared with canonical order: zero timing differences, zero invalid rotations, identical positions/lengths/seed angular rates, max rotation difference0.00000540deg. Reusable return buffers are deliberately dirtied before initialization. The counterfactual old body traversal produces34.377deg error, so the fixture catches the defect without relying on random uninitialized memory. `Prophecy.Sword.VerifyBoneOrder` runs the pure check directly without starting editor Automation; the same routine is registered as `Prophecy.SwordHolster.BoneOrder` for the next isolated normal-build suite. No interactive Automation was run.

Six owned Play captures at caps20(two),60(three),120(one) each tested three Sim agents through S and D:18 complete cycles/36 returns. The current Blueprint starts S at25; the diagnostic requests D at185. All target, future and physical pose samples are exactly identical across the six captures; action ticks are identical. Player S reaches66/returns97/completes159; D reaches215/returns246/completes308. NPC S returns93/completes155; D completes308/309. Maximum commanded return neck_01 step0.98434deg, neck_02 step1.32139deg, head1.83334deg; physical head3.43456deg/tick. The old114.90–117.27deg commanded neck flips did not recur. Current PHAT constraints still cause up to10.74deg head-target tracking difference on the player; this fix does not claim perfect physical tracking. Actual captured FPS19.87–32.20, world delta fixed1/60 throughout; caps60/120 are not evidence of sustained60/120FPS coverage.

A separate owned kinematic crowd fixture with temporary25% shrink passed S, D, pause, duplicates, queued cancellation and final joint/slot cleanup (completion275). It uses the established reachable test fixture, not a saved tuning change. Saved15% reach limitations remain. Motion claims above are numerical captures, not human playback acceptance.

**Audit beyond D/S:** get-up, Dodge/upper inertia, attack-start FK and attack-motion inertia receive the manager's canonical model arrays, not the unordered PHAT target list. All nine lower/walk/upper/slash/defense source contracts checked are parent-first. Attack/Parry FK return binds by name into its own validated canonical bone order. Armed-pose binding explicitly uses snapshot order and rejects a later parent. Jolt pose composition validates reference-skeleton parent order; physical target expansion and debug mesh reconstruction traverse that reference skeleton, mapping arbitrary input names. Jolt body targets read already-completed transforms, and hand/foot inertia/arm-cone corrections use explicit named chains or independent world transforms. Sword and both saved/live Attack Recovery lab datasets are parent-first. No second active occurrence was found in these paths. The pre-optimization test kernels remain historical and are only exercised with canonical-order fixtures; their lifecycle now shares the later reach-continuity staging described above.

[Fix receipt](../Tools/SwordHolster/HeadOrderFix20261011.json), regression `Private/Tests/ProphecySwordHolsterOrderTests.inl`, capture `Tools/SwordHolster/ProbeHeadFps.py`, analysis `Tools/SwordHolster/SummarizeHeadFix.py`; full evidence `Saved/Diagnostics/SwordHeadFix20261011/`. Previous diagnostic evidence below is retained.

### Original investigation

The old return implementation had a confirmed bone-order defect. The live physical-target array puts `head` at15 and its parent `neck_02` at22. `BeginReturn` reconstructed world rotations in array order, reading `ReturnWorld[22]` and `PreviousWorld[22]` before writing them. `FQuat` default construction does not initialize these values. Other hierarchical passes also used the unsorted upper list and could consume a parent's previous/base result. Invalid head return inertia then entered the independent head correction, which distributed that correction through the neck. The pre-optimization implementation contained the same defect.

Owned current-setup captures show commanded neck_01 jumps of114.90–117.27degrees during the arm return, while the commanded head stays within1.83334degrees/tick. The physical head jumps up to24.64degrees/tick. A control freeing only the head/neck angular limits at90 still produced a117.11degree commanded neck jump; changing PHAT limits cannot repair this upstream pose error. Native head/body and displayed socket agree within0.000003degrees in the captures containing both. No claim that every remaining physical discrepancy is explained or fixed.

All captured world deltas were exactly the float1/60 value. This project currently enables a fixed60Hz engine clock; the lower debug FPS cap changes pacing without changing that delta. Cap20 reproduced the defect too; repeated cap60 runs varied between actors. Those cap60 captures attained about28–32FPS on average, so they are not evidence of sustained60FPS coverage. Uninitialized memory explains run-dependent behavior; FPS alone has not been established as the trigger. The general Jolt step accepts world delta, so fixed stepping is a property of this setup, not a universal guarantee for arbitrary engine settings.

The correction above covers every hierarchical D/S pass with real/reordered physical-target regressions. Simply clearing the buffers or changing damping would leave the ordering error. Existing lab/native fixtures were parent-first and therefore missed this fault. No gameplay/native correction was applied during the original investigation; previous parity/performance results did not establish correctness for the live ordering.

[Compact diagnostic receipt](../Tools/SwordHolster/HeadFpsDiagnosis20261011.json), capture script `Tools/SwordHolster/ProbeHeadFps.py`, analysis `SummarizeHeadFps.py`; raw captures and graph/hash checks in `Saved/Diagnostics/SwordHeadFps20261011/`. The mid-action kinematic control canceled D/S at91 and is explicitly excluded from return-parity evidence. Owned sessions ended; FPS cap restored60; editor stayed open. The user's already-dirty PoseAgent Blueprint and TestNN remain unsaved, with graph and disk hashes unchanged.

## Historical lab port (October10)

The October10 [performance optimization](../Tools/SwordHolster/Optimization20261010.md) preserves the pose/timing contract below. Body refits are about11× faster, head look-in6.3×, ordinary FK return4×, and initial planning7.3–7.7× in paired100-agent tests. Those baseline measurements preceded the crowd scheduling below. The retained controller caches fixed return interpolation data and head speed-cap coefficients; layout changes still require a normal build/restart. Those normal-build checks predate the head-order patch above; its current build/save state takes precedence.

The native lab port supersedes the original hand-path IK sequence below. `Set Sword Holster Lab Profile` imports the saved JSON curves, body/head controls and independent D/S FK-return profiles. The existing tick25 Blueprint chain now loads `Content/locomotion/SwordHolsterProfile.json` before its existing profile and Draw Sword calls. Current saved values are15% axial shrink,250cm/s maximum reach,2500deg/s maximum reach rotation,150cm/s slide and.5 authored seconds unshrink. Node defaults are unchanged.

- The live NN keeps its own normal locomotion clock. The procedural overlay reads that base and is shared by visual and physical targets; it never writes its authored upper pose into NN recurrence. Lower physical feedback remains enabled. This prevents a post-release feedback loop that caused rapidly rotating wrist targets and stretched physical joints.
- Reaching uses parent-local FK interpolation and generated destination poses, with a duration bounded by wrist displacement and joint/wrist rotation. Four independent monotone curves remap D/S reach and slide. Sparse FK slide guides follow the moving holster; there is no per-sample Cartesian hand-path IK.
- Spine twist and two-axis clavicle swing minimize shoulder-to-clear-target distance within the saved limits. The lower spines receive20/40/60/80/100% net correction; pelvis remains the NN pose. Body targets update against live geometry with angular-rate bounds. Drawing waits for its turn; sheathing releases clavicle correction from its actual slide-entry value as insertion advances.
- Head/neck gaze uses the actual holster mouth, independent look-in/out speeds and sigmoid exponents, independent D/S look-out thresholds and look-at alpha. Neck sharing is1/3,2/3,full head. Head time is never curve-remapped.
- Independent D/S FK return starts at authored slide completion, on its own60-tick clock. Both local/world inertia, ordinary/spring return, timing/easing/hold/decay, bone weights and upperarm twist removal match the lab math. The spring evaluator keeps two rolling integration samples rather than an entire per-agent pose bank.
- The sword uses the same actor throughout, with one reusable temporary joint. Ownership/joint release uses the authored slide endpoint. S leaves the sword attached to the holster; D reparents it to the hand and unshrinks independently. Completion waits for FK/head/unshrink, but completed pose ownership retires immediately so a long unshrink cannot freeze NN motion.
- Right-arm contact suppression lasts through the return and restores the underlying user settings. Native PHAT limits, magnetization values and motors were not retuned to mask the release problem.
- In kinematic mode the holster follows the pelvis; its previous simulation/attachment state is restored when returning to Sim. A moving physical holster can still change reachability relative to a rigid mount. The saved shrink/angle limits are not silently increased to accommodate an unreachable target; the arrival gate continues to require a real reachable grip.
- Explicit JSON configuration caches parsing across agents and reloads when the file timestamp changes. Inactive/completed controllers have no recurring fit, pose-copy, head or return work. Shared output reads use the existing pose IDs and a reader/writer lock; worker feedback receives immutable per-agent isolation flags.

Verification and remaining limits are recorded in `Tools/SwordHolster/Verification20261010.md` and the current ProjectJournal status. Regenerate math fixtures with `node Tools/SwordHolster/export_parity.cjs`, then run `Tools/SwordHolster/RunParity.ps1` against current normal DLLs in a separate headless process. Do not run Automation in the user's interactive editor.

Pre-optimization timing audit: [descending measured costs](../Tools/SwordHolster/PerformanceAudit20261010.md). The regular fourth-tick search caused about80% of the synchronized heavy reach tick. Head, search and FK return each accounted for about21–22% of total action cost when averaged over their different update frequencies. Initial pose planning and irregular return-entry stalls are documented separately. These baseline measurements precede the optimization linked above.

## Crowd scheduling (October11)

`Draw Sword` accepts an NPC request into one of four upcoming unpaused world ticks. The player starts immediately. Pending S keeps the ordinary held sword and NN pose; pending D keeps the sword holstered. Admission reads the current pose, holster, profile and physical mode when its slot becomes due. The delay is at most three ticks while the component is ticking, not three wall-clock frames during pause or suspension. A delayed consumer starts when it next runs; there is no missed-modulo deadlock or accelerated catch-up of the pending animation.

Four rolling start counters balance new planning bursts independently from the four counters for current reach work. This prevents an emptied reach slot from attracting an entire burst of new initial plans. Reach slots choose the least current load, release their load at sliding, and use the shared world clock instead of each action's local clock. A missed pose update performs at most one fresh body refit and schedules the next refit back in its assigned slot. It does not repeat searches for historical ticks against the same current geometry.

Head, FK movement/return, sword transforms and physical targets still update every authored tick. Reach arrival still refreshes its arm destination immediately; grip, parent/joint release, slide completion and FK-return entry are not delayed by a budget. Slide guides remain due-driven: the saved speed/spacing already requires nearly one per tick, so speculative precomputation would add invalidation work. Each action's clocks begin at admission. On moving input, shifted refit samples can produce small pose differences; the test matrix measured at most0.785cm/1.914degrees and no completion-tick difference across all16 start/slot combinations.

Repeated pending requests in the same direction are idempotent; opposite-direction calls are rejected. Hide/drop, failed admission, actor teardown and world cleanup release pending reservations. No general job queue, worker task, per-agent scheduling callback or per-tick scan of all reservations was added. One callback advances the clock for each active world; it unregisters when no reservations remain. There are no new Blueprint nodes or tuning controls. The on-demand holster report exposes `queued` and `refresh_slot`.

Nine isolated native tests and four owned-PIE checks passed: unchanged player Sim ticks, player kinematic/Sim restoration, NPC Sim and NPC kinematic admission/pause/duplicates/cancellation. Temporary25% reachable fixtures were not saved; saved15% reach limits remain as documented. Full BP graph and map/agent/sword/profile hashes are unchanged. [Paired100-agent timings and verification](../Tools/SwordHolster/Stagger20261011.md), [receipt](../Tools/SwordHolster/Stagger20261011.json); raw evidence `Saved/Diagnostics/SwordStagger20261011/`.

## Historical original implementation

The sections below document the original implementation and old tuning, not the current lab port.

## User-facing controls

- **Draw Sword**: `Sheathe` (default false), `Max Reach Speed` (100 cm/authored second), `Max Reach Rotation Speed` (180 degrees/authored second), `Sliding Speed` (60 cm/authored second).
- **Set Sword Holster Profile**: `Shrink Percent` (10), `Unshrink Duration` (.25 authored seconds). **10 means ten percent smaller, retaining90% of normal blade-axis length, with unchanged width and thickness.** Valid shrink range is0 inclusive to100 exclusive. Duration may be0; speeds must be finite and positive.
- One authored second is60 unpaused game ticks. Reach position and quaternion rotation advance with one fraction, capped by both speed limits. There are no animation clips or pose handoff fades.

`Capture Sword Holster Reference` is a supporting construction/initialization node. It reads the `SwordRef (deleted in begin play)` child actor under `holster`. Its sword mesh supplies the seated transform relative to the holster; `base blade` supplies the beginning of the blade, measured to the mesh's positive-Z tip. Extraction is negative blade-Z. If the marker has already been deleted by child BeginPlay, its construction template supplies its local position under `sword`.

The user moved normal sword scale into A_Sword's mesh component. Equip now spawns the actor at unit scale and retains the authored component scale exactly once. The historical SwordGripTransform scale is no longer multiplied into it; grip location/rotation and the existing Training mesh remain in use. Captured normal blade length in the inspected asset is about89.35cm.

## Sequence

Sheathe reaches the holster mouth while progressively shrinking the sword about the hand grip. The NN presentation authors shoulder/elbow/hand with a two-bone solve and feeds that accepted upper pose into recurrence, letting normal physical magnetization follow the arm target. On arrival the same sword actor's mesh root attaches to the holster, becomes a managed native kinematic body, and slides0->100%. The fixed hand joint makes the physical hand follow; the NN target follows the same grip. At completion the temporary joint is removed and arm ownership returns immediately to locomotion.

Draw reaches the seated grip, creates one temporary joint at the current physical pose, then slides100->0%. At the clear endpoint it removes the joint and attaches the sword root to the hand. Scale returns to1 over Unshrink Duration; ordinary held simulation/attachment resumes using the previous hold preference.

During either action, the native collision responses of `upperarm_r` and its descendant PHAT bodies (forearm and hand) temporarily ignore every channel. This includes body, holster and world contacts. Simulation, joints and magnetization stay active. The override starts on accepted entry, remains through reach/slide/unshrink, and releases at sheath/draw completion or cancellation/drop/hide. It composes with the existing limb settings: configuration/reset calls during the action cannot re-enable contacts, and their latest settings become effective on release. The left arm and torso are unaffected. No additional Blueprint control is required.

Repeated calls in the current direction are idempotent; opposite-direction calls during a transfer are rejected. Native joint handles are reused when changing the shrinking grip frames. Drop, despawn and completion clear owned temporary joints and contact exclusions. The sword remains the same actor throughout. `Get Held Sword` returns no held sword while the holster owns it, so existing NN/combat consumers see an unarmed agent.

Shrinking changes only local Z (the blade axis) in both the native Jolt shape and UE receiver scale. Grip translation and the reused joint anchor resize on the same axis, keeping the hand contact pivot fixed. Attached kinematic receivers retain their parent-relative transform during physics publication; the native body follows that authored target through the shared physics step. Writing the previous native world pose back onto this attachment would cancel parent motion. Native mass/inertia are retained during this visual fitting operation. Holster motor and pelvis constraint settings remain user-owned. This first implementation requires the agent's Jolt physical mode.

## Right-arm collision verification

Live Coding build290.15s and reload succeeded without a restart or reflection repairs. Actual Play through absolute150 verified125 suppression checks across19 exposed collision channels: sheath completion99, draw completion142, hide interruption150. Left-arm/torso responses matched their baseline, duplicate calls were harmless, and limb configure/reset changes made during suppression survived release. A transient70% profile made the diagnostic cycle reachable; user35/.5 remained unchanged. Full Blueprint graph and agent/sword/map disk hashes are identical to the pre-build baseline; only the already-dirty TestNN remains unsaved. Evidence `Saved/Diagnostics/SwordHolsterArm20261010/`, receipt `Tools/Recovery/SwordHolsterArm20261010.json`. Normal DLLs remain stale. The initial test script used the wrong Python collision enum and was corrected before the passing run. Other agents still in holster actions emit empty restore warnings only during PIE teardown after their rig is gone; their character EndPlay removes the temporary state.

## Latest correction verification / recovery

October10 correction passed an actual sheath/draw cycle through absolute tick289 with a transient70% profile. Width/thickness ratio error was below3e-16; retained blade length was0.300000012. During60 holstered ticks, the parent moved139.68cm: local position drift was0 and rotation drift0.00000342 degrees. The managed native kinematic collider followed with at most3.88cm gap during movement; there is shared-step lag rather than accumulated attachment drift. Drawing restored the original asset scale and kept the same actor. The old implementation reproduced70% width/thickness loss and severe relative attachment drift in the same exercise.

Build354.90s and Live Coding reload succeeded, no restart. Eighteen archived library-CDO references were repaired; the entire agent/A_Sword graph then matched the current user baseline exactly. Both assets saved, agent status3, A_Sword retains its pre-existing warning. TestNN disk bytes unchanged and dirty map left unsaved. Current user node values are **35% shrink / .5s unshrink**, preserved; native node defaults remain10/.25. Normal DLLs remain stale. Evidence `Saved/Diagnostics/SwordHolsterFix20261010/`, receipt `Tools/Recovery/SwordHolsterAxisParent20261010.json`.

## Original implementation verification (historical)

The full cycle passed in actual Play at70% shrink (30% retained size), including two consecutive sheath/draw cycles through absolute tick324. Five duplicate Sheathe calls left the native joint handle, state and total joint count unchanged. Native generic joint count returned to14 at both completed draws; temporary joint was absent at both endpoints. Sword component scale returned exactly to `(0.837727, 0.766194, 1.311941)` and the actor instance remained the same within each cycle. No motion-quality claim is made; user inspection remains appropriate.

**The original trial used10%; the user has since changed the saved node to35%.** At the original trial geometry,10% could not reach the mouth-clear target. Actual arm reach was about49cm versus a target about79cm from the shoulder, leaving approximately30cm error. Physical and NN arm positions agreed to well under0.1cm in the captured pose; this was geometric reach saturation, not a failure to magnetize. A50% transient shrink trial remained about6cm short.70% was used only in the diagnostic instance, not saved into the node. Adjust the profile or holster placement for a reachable target; there is no silent automatic increase of the user's shrink value.

The user’s unused True branch of `is tick i=25` in `tick debugging` was initially wired to call Set Sword Holster Profile (10/.25; now user35/.5) then Draw Sword (Sheathe=true,100/180/60). Construction and begin_f each capture the reference before the existing deletion. Four nodes added; full graph audit confirmed only four expected existing execution-pin changes. No other tuning or connections changed. A_Sword's six archived library-CDO self references were repaired after reload, preserving its entire authored graph. Its pre-existing disconnected `get depth of location` warning remains; agent BP compiles cleanly.

Agent BP and A_Sword are saved. TestNN disk bytes are unchanged; its current dirty state is left unsaved. Editor PID22876 remains outside Play. Normal DLLs are stale: perform a normal build before any cold launch. Original implementation compile succeeded in191.68s and reload finished; earlier initial build fixed two pointer-deduction errors. No native Automation suite was run in the interactive editor.

Evidence and scripts: `Saved/Diagnostics/SwordDraw20261010/`. `Prophecy.Sword.HolsterReport` writes on-demand state to `state.txt` without a permanent diagnostic sampler. The setup command `Prophecy.Editor.WireSwordHolster` verifies the unused tick25 True branch and refuses an existing Draw Sword call; it compiles without saving. Full graph comparison is required before saving.

Runtime state is a new sidecar in `ProphecySwordHolsterRuntime.inl`; no existing retained controller/native-state layout was resized. Once loaded, changing this sidecar's struct layout also requires a normal build/restart under the journal's retained-layout rule.

## Current35% stall diagnosis

Unmodified current setup measured through absolute221: shoulder-to-goal63.14cm, NN arm length49.00cm, physical hand error14.09cm, physical-to-NN hand error0.058cm. Right-arm collision is Ignore. Target progress is1, insertion0, phase remains Reach. The two-bone solve keeps the shoulder position fixed and clamps hand reach to the arm length; arrival requires the real hand within2cm (rotation was already within0.633deg versus5deg tolerance). No reachability fallback or timeout exists, so this target stalls indefinitely. Earlier70% diagnostic cycles were reachable and do not establish reachability of the saved35% setup. No settings/code were changed during diagnosis. Evidence `Saved/Diagnostics/SwordStall20261010/probe.json`.
