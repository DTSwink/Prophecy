# Foot IK Lab

Independent kinematic terrain-placement prototype, created October 25, 2026
from the Bodyflip Lab renderer, cached NN gait banks and leg solver.

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

## Collider ghost and contact roll — October 25

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
shoe now stays pinned at **101�102** (57.4 degrees toe-down at 101), then remains
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

## Full-body shadows — October 25

Replaced the rejected analytic foot footprints with actual depth-mapped shadows
from the displayed head, torso, arms, hands, legs and shoes. They fall across the
real stair treads and sides, and the body can shadow itself. Ghost/target overlays
do not cast. Motion, tuning and UI layout are unchanged.

One 1024² depth texture (about 4 MiB in WebGL2) covers a stable four-metre window
around COM. The existing body vertex buffer is uploaded once and reused for one
extra depth draw; there is no second CPU mesh build. Only the character casts;
the terrain receives, avoiding a second draw of the course. The framebuffer and
texture are allocated once. Camera/debug-only redraws reuse the map while the
pose and displayed geometry are unchanged. A small 3×3 filter smooths edges;
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

## October 25 correction — preserve the NN gait

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

Five-second preparation takes approximately **50–145 ms** in the local Node
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
