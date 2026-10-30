# Foot IK Lab

Independent kinematic terrain-placement prototype, created October 25, 2026
from the Bodyflip Lab renderer, cached NN gait banks and leg solver.

## Restore accepted slide movement/contact — October29

### October30 lossless solve optimization

The user approved the clearance-entry/contact-travel result below. The final
optimization preserves it exactly: `slide-entry.js` retains computed hip, knee
and foot chain values while their input coordinates are unchanged during the
corridor search. `slide-joints.js` avoids full hinge diagnostics when only the
hinge angle is needed, a duplicate quaternion product, and small polynomial
array callback allocations. Search order, iteration counts and arithmetic
order are unchanged. Shared surface/Foot IK solvers and arm motion were not
modified by this pass.

Strict deep equality passed for 20,121 complete frames: the accepted current
replay, 16 independently generated walk/run slide cases (all directions, yaw,
inclines and floor deletion), and 20 cached-input terrain/disabled cases.
An additional 10,400 randomized joint projection, diagnostic and blend
comparisons passed exactly. The 16 slide pairs took 121.80s before and 90.56s
after in sequential Node runs (1.345x overall; 1.08-1.63x per case). These are
solve timings, not a claim of improved render FPS or native Unreal speed.
Evidence and original source bytes: `Saved/FootIKLossless20261030/`.
No live settings, server or viewer state was changed. Native packaging and
cross-engine verification are separate work still in progress.

### October30 clearance entry and contact travel

F81.5 was the first elbow-clearance correction, with no earlier displayed-arm
history. F123-130 used an axis-selecting wall correction that suppressed the
hand's upward motion, then switched to the gradient method at .7rad and kicked
sideways at130.5. The wall solve now attempts the continuous shoulder gradient
at every correction size; individual axes remain only a numerical fallback.
History is retained while clear of the wall. Initial clearance acceleration is
bounded, then the entry limiter fades as contact weight rises from.85 to.95,
or retires after four settled ticks. This avoids carrying lag through a brace.
No frame/side cases, added torso guard, root changes, or new UI/tuning.

Checked user's current yaw-stop10m setup with recorded NN prefix (policy is
already paused in slide before either changed yaw horizon is reached). Over
80-83, left hand root-translation-relative peak acceleration266.31->26.67m/s2.
Over123-132, right peak211.78->11.99m/s2, upward relative velocity0.394-1.503m/s,
contact19/19 ticks. Root positions exact. All317 slide ticks pass joint/length/
wall checks; minimum collider clearance0.313mm, maximum arm step6.205degrees.
Yaw-stop12m regression also passes, retains contact144.5-150 and peak18.29m/s2.
Evidence Saved/FootIKArmSmooth20261029/continuous-wall-summary.json,
continuous-entry-fade.model.json.gz and continuous-regression12.model.json.gz.
Full viewer reload pending; user is doing visual review. Earlier self-crossing
limitations remain; these receipts do not claim every other hitch is resolved.

### October30 F145 root-turn boundary correction

The F144.5 hand kick coincides with the distance-based yaw command stopping:
measured turn speed drops from3.486rad/s to approximately0 while still braced.
The new release-only angular limiter did not cover it. Added a bounded world
hand-velocity transition for an already-contacting arm when heading acceleration
exceeds60rad/s2. It uses the existing constrained arm IK and wall-clearance pass;
normal bracing/free motion and root/yaw timing remain unchanged. Tracking exits
once velocity catches up for four solver ticks. No frame/side special cases.

Recorded replay through202: right world/root-translation-relative hand acceleration
peak over144.5-150 falls88.77 to19.37m/s2; contact retained throughout144-150.
All pose positions through144 and every root position are exact. Joint, length
and wall checks pass over317 slide ticks; minimum wall clearance0.300mm.
Saved/FootIKArmSmooth20261029/yaw-hand-summary.json and yaw-hand-ease.model.json.gz.
Earlier target-inertia/all-contact-filter experiments were not retained.
Full viewer reload pending; user is doing visual review. Torso crossing unresolved.

### October30 release velocity smoothing

Added angular acceleration limiting (45rad/s2) only while a brace releases,
after the wall solve. Wall safety repairs from that smoothed prediction toward
the safe pose, rather than discarding its velocity and restarting the blend.
No torso guard or extra target-pose filter. Current recorded replay passes wall,
joint and length checks over317 slide ticks; minimum wall gap0.300mm.
Left136-140 peak hand acceleration falls72.86 to44.02m/s2; hand path length
retains100.8% left/101.8% right. Right-hand F138 correction remains.
Evidence: Saved/FootIKArmSmooth20261029/release-final.model.json.gz and
release-final-targeted.json. Visual review deferred to user as requested;
full browser reload required to activate. Torso crossing remains unresolved.

### October30 torso guard removal

At user request, removed the finite-torso guard, front-route preference and
minimum-change cost. Its 1.2cm clearance margin caused the F105.5 velocity hitch.
The original left-arm torso crossing is therefore unresolved again.

Retained only the independent continuous shoulder-gradient wall correction for
the F138 right-hand kick. Replay through202 passes wall/joint checks over317
slide ticks, with minimum wall clearance0.300mm. Right-hand peak acceleration
over136-140 is11.73m/s2 versus312.69 before the fix. Evidence:
Saved/FootIKArmSmooth20261029/guard-removed.model.json.gz and
 guard-removed-targeted.json. No shared surface/NN/leg/settings changes.
Earlier final-optimized receipts describe the now-removed torso guard.

October30 activation correction: Copy-Item preserved backup LastWriteTime, so
the timestamp-only in-app Refresh incorrectly kept the rejected in-memory
scene. Previous live-revert claims were not reliable. Force a full browser
reload after restoring backups, and touch restored source timestamps so other
open tabs detect the rollback. Source hashes alone prove disk/HTTP contents,
not which simulation is already displayed.

User rejected the slide continuity change: it made the character spin with
little limb movement and the bracing hand stayed down. Restored the exact
accepted wall-clearance sources from before both inward-guard experiments:
slide-arms.js SHA256 E9725E63BB1C416205ACAC0CDA6E3E3F9DBEB43E44A3CCA84DCC3B8EB319C957,
surface.js FCE87DF5EA00A10041F150E992ED0BA78F81FD79006693CD7C7BEA90D8ACB283.
The mouse-scrubbing Play/Pause fix in app.js is retained.

The previous checks were insufficient: reduced acceleration and nonzero speed
hid a79–83% loss of hand travel. Accepted settled wrist paths are2.292/2.535m
versus0.487/0.435m in the rejected version; actual full-slide hand contacts were
190 versus117. Full317-tick recorded replay now matches the accepted motion,
including wall clearance>=0.30mm and no joint/leg/root checks failing.

Both broad arm/leg filtering and the final inward-stop pass are removed. A
free-target-only guard retained contact but did not fix mixed-contact torso
crossing; a post-release guard snapped, so neither is active. The original
release-arm torso crossing and existing wall-correction hitches remain unresolved.
Do not claim those fixed or reinstall broad smoothing from numerical jerk metrics.
Rejected sources/receipts: `Saved/FootIKRestore20261029/`; full motion comparison
in `Saved/FootIKArmSmooth20261029/accepted-envelope.json` and
`accepted-restored.model.json.gz`.
Exact replay comparison:10,530 bone positions match the accepted clip with
zero difference;190 full-slide hand contacts restored. Live8890 refreshed,
wall brace visually checked at201, original paused22/camera/tuning retained.
Screenshot: `Saved/FootIKRestore20261029/restored-wall-brace.png`.

## Rejected slide limb continuity and playback scrubbing — October29

Historical description of the rejected implementation below. The previous
free-only inward stop missed bracing transitions and snapped the
shoulder at F44. It is superseded by a side-clearance term in the existing arm
wall solve, active throughout the contact blend. Incoming NN arm velocity carries
through entry; displayed arm pursuit retains angular velocity, including when
the arm is already clear. A brace that would fold through the chest releases
smoothly. Small impending overlaps receive a minimum local correction before
the existing wall safety fallback. The balancing trajectory/clock remains.

The hand clearance reserve is2mm, within the4mm contact tolerance. A candidate
using25mm was rejected: smoother motion alone hid the loss of wall contact.
Leg goals now retain angular velocity too, with3.5cm extra knee approach room
before the existing wall capsule limit. Root/pelvis paths and pre-slide NN poses
remain exact; no general self-collision module was restored.

Recorded current Run58/yaw200/Fall-2 through202 covers317 slide ticks. The F44
left shoulder step falls5.47->0.78deg; F81.5 wrist acceleration245->0.52m/s².
Whole-arm maximum step is2.15deg at120Hz, and forearms/hands stay outside the
torso across every contact weight. The attached proximal shoulder seam is
excluded from torso-intersection claims. Settled leg peak angular acceleration
falls678->305rad/s². Some wall safety acceleration remains; do not claim a
uniformly acceleration-capped motion. Audits and matching collider renders:
`Saved/FootIKArmSmooth20261029/` (`projected` is the final candidate), with leg
receipts under `Saved/FootIKLegSmooth20261029/`.

Mouse playback scrubbing now preserves Play/Pause and resets its elapsed-time
accumulator. It still displays the sought pose immediately; trim-bracket
preview/restore behavior is unchanged.

Live8890 regenerated through202 after a cold-load retry. Mouse rewind while
playing visibly continued advancing; paused scrubbing and exact frame82 were
checked. Original paused201,0-202 brackets,0.3x speed, camera and tuning restored.
Temporary test viewport restored; screenshot `viewer-verified.png` in the audit
folder. Shared isolation2722 checks and transition/reentry/split continuation
pass. Final right-hand contact117/136 requested samples; an existing unreachable
left brace interval remains. Residual F142 wrist correction is3.2mm/tick.

## Superseded dangling-arm inward limit — October29

The free arm now has a small, smooth shoulder-abduction stop. It eases elbow
and wrist outward when they approach the body's side, while preserving the
elbow bend, wrist-relative rotation, balancing clock and existing smoothing.
It fades out as wall bracing takes over. This is a single analytic rotation
after wall clearance, with Jolt shoulder limits; no collision search, pin,
accumulated correction or changes to legs/root. Current recorded turning clip:
worst free elbow goes from3.97cm inside the shoulder plane to2.81cm outside;
hand-box inner edge stays3.35cm outside. Root and non-arm positions are exact,
joint limits pass, and existing wall clearance remains at least0.30mm.
Receipts/backup: `Saved/FootIKFreeArm20261029/`. Live8890 regenerated through202;
90/102 visually checked, original paused0/camera/settings restored. First cold
generation timed out; retry succeeded, console clean. No server restart.

## Self-clearance experiment reverted — October29

User rejected the arm/body and opposing-leg clearance because the motion visibly
stuck. Restored the exact pre-experiment slide-arms.js and surface.js, preserving
the accepted arm-versus-wall fix. Removed self-clearance dependencies/tests from
the active lab; rejected sources and diagnostics remain in
`Saved/FootIKSelf20261029/`. Do not restore this approach based only on collision
metrics: those passed while the movement quality regressed.

## Slide arm wall clearance — October29 (local, activated)

The displayed upper arm, forearm and hand now receive a final wall-clearance
solve after entry/contact blending. Palm target fitting alone allowed elbows,
wrists and hand boxes through the wall during turns. The solve uses the actual
renderer capsule radii and oriented hand box, preserves lengths, and projects
candidate local rotations through the existing Jolt limits. A small elbow/wrist
reserve allows a shared temporal rate bound without interpolating into the wall;
corrections relax gradually back toward the existing arm motion. Contact receipts
now use the nearest hand-box surface, allowing honest tilted/edge contact.
This can release a palm when contact conflicts with arm clearance.

Captured Run58%, yaw200deg/s, Fall speed-2, throughF202:317 slide ticks; worst
whole-arm overlap30.6cm becomes minimum clearance0.30mm. No added joint-limit
violations; root positions are exact. Peak arm rotation step6.66degrees versus
5.96before at120Hz. Consecutive-frame side views cover63–67,94–98 and134–142.
`verify-slide-arm-clearance.cjs` also passes recorded forward and negative-turn
cases. Shared isolation2722 checks, slide transitions/split continuation and
signed Fall speed checks pass. Receipts and before/after poses are in
`Saved/FootIKArmWall20261029/`. No UI options or shared foot-placement changes.
Live8890 regenerated through202 and restored paused96, camera and tuning.
The first cold generation timed out; retry succeeded and the subsequent cached
reload initialized normally. Playback advancement and clean console verified.

## Signed Fall speed — October29

Fall speed m/s now accepts negative values. -1 means enter freefall while
upward root velocity slows to+1m/s; positive2 still waits for-2m/s and zero
still waits for downward movement. Initial upward inertia survives entry:
thrust stops and full gravity acts through the apex without cancelling Slide.
After the root has fallen, a new upward motion exits as before. Before the
apex, accelerating above the early-entry threshold also exits. Increasing
upward velocity cannot immediately retrigger early Slide. Current tuning is
preserved; no default change. `verify-slide-negative-threshold.cjs` covers
thresholds, gravity, saved-state continuation and reversal/re-entry.

## Slide hand continuity — October 29 (local, activated)

Fixed hard lateral hand chatter in the heading-aware arm solver. Reach fitting
previously accepted a palm anywhere on the wall, even when it missed its intended
contact point sideways. It now measures the full palm-to-target error, uses a
damped constrained solve and finer reach search. The accepted elbow bend is
transported to the next reach axis; trial fits do not alter that history.
All three arm joints share one response and rate bound; independent angular
caps had distorted the chain and produced alternating wrist/elbow motion.
Response increases continuously with commanded heading speed and arm reach,
using2mm intended contact lag. A fixed local low-pass was rejected because it
made turning hands trail behind the wall. Friction, balancing and continuous
front/side/back contact weights remain active.

`verify-slide-hand-continuity.cjs` replays the recorded current Run58% scene
without inference. Over F134–202, peak lateral wrist acceleration falls from
423.75 to3.31m/s², palm rotation step from6.07 to0.36degrees at120Hz, and rapid
sideways reversals from23 to0. Both palms retain274/274 contact samples with
maximum gap1.77mm; anatomical limits pass and root positions are bit-identical.
The inner fitting loop now rebuilds only the three arm joints; comparison with
full-skeleton FK differs by less than3.2e-12m. Receipts:
`Saved/FootIKSlideAudit20261029/hand-continuity-check.json` and
`hand-arm-fk-parity.json`. No new settings or shared foot-solver changes.
Final fitting uses0.3mm convergence and nine reach subdivisions, avoiding
unnecessary precision. Recorded native solve is about3.5–3.8s for the current
scene; this is preparation cost, not playback cost.
Close-up collider strips cover F137–141 and175–180 before/after the fix.
Slide exit/re-entry and exact split generation pass; shared Bodyflip isolation
passes2722 checks. Live8890 Refresh generated through202 and retained paused173,
camera and tuning; browser console is clean.
Final seven-case native audit covers the current scene, four directions and
full positive/negative turns. All pass with zero rapid lateral reversals.
Full-turn maximum arm steps are4.89/5.27degrees; contact samples improve to
376/442 and293/452 from the original252/442 and283/452. Contacts can still
release during arm repositioning. Root paths remain exact and leg differences
are below0.16mm from hand-contact feedback. A slower30deg/s captured-input
replay retains93.9% contact samples without illegal joints. The six-second
full-turn preparations remain heavier at25–26s; this change does not solve that
remaining cost. Final receipts: `hand-final-regression/report.json` and
`visuals/hand-final-front.png` in the same audit directory.

## Heading-aware wall slide — October 29 (local, activated)

Slide now retains the controller's facing direction. Forward faces the wall,
sideways remains sideways, and backward retains the outward-facing pose.
The target follows live root yaw continuously, including complete turns in
either direction; it no longer rotates every approach into one reference pose.
Pelvis position retains the existing Slide closer offset and independent
Pelvis blend clock. Its orientation uses a decaying local entry residual so
crossing 180 degrees during entry cannot switch the interpolation branch.

Leg targets and anatomical knee poles follow facing continuously. The entry
corridor forecasts the same future heading and independent pelvis schedule.
Ankles retain their relaxed calf-relative rotation; contact may use a shoe's
heel, toe or edge rather than forcing a flush sole by twisting the ankle.

Contact targets now account for knee capsule clearance as well as the sole,
joint limits and the previous knee-pole branch. The nearest feasible tangent
target is selected, preferring a lower target for wall clearance but allowing
an upward fallback at a floor corner. Speed/friction shifts use the same
feasibility checks. A retained offset and bounded tangent travel prevent sudden
target changes when a higher position becomes reachable. Settled clearance
starts from the previous legal joint pose; it no longer accumulates a correction
in normalized coordinates while the body turns underneath it. Both clear and
planned entry paths check knees before a shoe collision forces a late correction.

`slide-arms.js` owns the host-only arm posing. Forward-facing poses use both
hands when reachable; side/back poses blend toward the near hand and leave
the other arm balancing. Each arm has its own continuous contact weight and
anatomical elbow/wrist constraints. Unreachable hand contacts release rather
than forcing an invalid shoulder. The reported primary hand is only a label;
it does not select which arm receives friction or controls the other arm.

The accepted irregular torso motion, free-arm balance circle and speed-based
downward gaze remain active in every heading. Gaze still reaches 70% toward
absolute down at Head max at m/s (default30), with the same entry ease and
neck/head joint limits. A four-heading transform audit verifies this directly.
No extra UI settings, altered root forces, gait-policy changes or shared-foot
API changes are part of this update.

Verification: `verify-slide-heading.cjs` covers16 Walk/Run configurations,
cardinal approaches,82/85/90-degree inclines, retained/deleted floors and three
extended yaw sweeps(+535,-523,+679 degrees). All joint/geometry/heading checks
pass; maximum settled heading error0.923degrees and joint increment7.59degrees
at120Hz. Actual gaps are reported for every foot, not only contacts claimed by
the solver. In the current Run58%, forward90-degree scene both feet touch for
all286 settled samples; maximum gap0.0122mm, no motion-review flags. Some fast
turns briefly release a contact during repositioning. In82/85-degree floor
interaction cases the root takes hips beyond leg reach; contact releases
without changing root inertia or inventing a pelvis pull.

Exact native pre-Slide pose/root parity, four-heading gaze checks,2722 shared
Bodyflip isolation checks and Slide exit/re-entry with exact split generation
also pass. Full-motion collider sheets, complete turns and focused fast-entry
intervals were inspected from multiple views. The latest matrix supersedes the
earlier fixed-heading20-case audit below. Receipts and source hashes:
`Saved/FootIKSlideAudit20261029/heading/final-report.json`, `live.json`,
`acceleration-context.json`, reach analyses and `visuals-final/`.
Live8890 Refresh generated through202 and kept paused140, camera, trim and
tuning. Console clean. The unavailable8890 service was restored with its existing
overnight-state.json. Validation uses bounded sequential recorded-policy replays,
without per-case inference workers. No push.

Remaining visual limitation: Run-left's folded entry around80–92 still makes
a broad high leg sweep. The incoming foot is23.3cm above the pelvis; the corridor
raises it to61cm. This is a planner-authored detour, not a demonstrated NN
necessity. It stays continuous and within joint/scene constraints. Moderate,
hip-first and projected lower-path experiments either failed clearance or
introduced correction snaps, so none were applied. Receipts: `entry-*.json`
in the audit folder. The naturalness of this one entry remains below the
current forward scene and the settled/full-turn poses.

## Slide entry and wall-motion audit — October 29 (local, activated)

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

Follow-up: **Slide closer cm** is appended at the bottom of More options.
The base slide previously inherited the pelvis-to-plane distance at entry.
This explicit extra inward offset blends in over Blend s and remains throughout
Slide; root freefall/inertia is unchanged. Legacy default0 retains the prior
pose; current scene is set to10cm closer, about39–41cm from the wall after
entry. Range0–15cm, with a minimum15cm pelvis clearance. Larger experimental
offsets cramped the legs and were not exposed. Current0/10/15cm replays verify
joint/contact limits, exact root parity and the requested settled displacement.
The earlier no-pelvis-detour assertion now subtracts this intentional offset.

The previous clearance envelope below is superseded: it moved the displayed
pelvis away from the wall and then back. The current transition keeps the
configured pelvis distance and plans the leg path in hip/knee/ankle joint
coordinates. `slide-entry.js` is a Foot IK host helper; it is not a shared
Bodyflip foot-placement dependency. The old hidden inward hand-reach pull is
also removed. Physical root inertia can still legitimately change wall distance.

Slide starts from the preceding displayed pose carried with the root, avoiding
an unpinned-foot jump on its first frame. The bracing arm uses soft reach near
full extension and releases smoothly if inertia takes its palm out of reach.
Dangerous-incline pelvis closeness eases its withdrawal when the supporting
surface changes, instead of dropping its full correction in one tick.

The corridor uses bounded hip swing/twist, a knee hinge and calf-relative ankle
coordinates. A shorter body-turn schedule is considered only when the ordinary
route is obstructed. Cubic path offsets and an angular-distance clock avoid
compressing a large joint turn into a few ticks. Actual geometry is checked
against the current surface set, including floor deletion during entry and
finite-platform undersides. Incoming NN joint residuals may fade; they cannot
grow during that fade. No pelvis-clearance fallback remains.

Twenty configurations pass: Run/Walk forward, backward and sideways approaches,
both turn directions, 82/85/90-degree surfaces, travel parallel to the wall and
retained/deleted floors (including deletion during entry). Exact recorded policy
replays were supplemented with fresh NN output for affected feedback cases.
Across the19 cases reaching Slide: no added hip-limit error, all settled joints
legal, fixed limb lengths, max shoe penetration0.00235mm, max joint increment
6.93degrees/120Hz and no solver-added pelvis displacement. Retained-floor Walk
Backward correctly does not enter Slide: the floor catches the root before its
descending speed reaches the2m/s trigger. Remaining fast folded-leg motion
follows the NN's foot velocity and collision constraints; no extra knee lag is
applied. Whole-motion/focused collider sheets were inspected from several views.

Current scene F85–115 stays48.4–49.2cm from the wall; that0.8cm change is root
inertia. The previous path reached~70cm then ended at31.2cm. The accepted0.5s
blend remains. Ordinary active-leg planning is~0.4s here; difficult folded
sideways routes can still need several seconds for additional planning.

`verify-slide-directions.cjs` with the audit's `validated-cases.json` passes all20.
Joint math16,311, shared Bodyflip isolation2,722, coupling17 and bounded-session
2,906 checks pass. Slide exit/re-entry and exact split-generation checks also
pass after the final source freeze. Receipts and before/after collider sheets:
`Saved/FootIKSlideAudit20261029/`. Live8890 Refresh generated through F202 and
retained paused F108; persisted state is byte-equivalent as parsed JSON. No
Unreal, Bodyflip, UI layout or tuning changes; no push.

## Earlier slide entry hip correction — October 29 (superseded clearance)

Current saved scene uses **Blend s = 0.5**, doubled from 0.25 at the user's
request for a slower whole-body slide transition. Changed through the existing
option; target poses and root behavior are unchanged. Frame147 retained.

The reported Run/phase36%/Full gravity70% setup enters Slide at85. The old
wall-avoidance ankle arc deliberately took the long way around the hip while
hip limits were disabled until blend completion. At92, right hip twist reached
-165.48 degrees against its65-degree limit; it crossed the excluded cone.

Entry now interpolates hip swing inside Jolt's quaternion-space ellipse and
twist inside its bounded interval. Knees use their hinge coordinate; foot/toe
rotation stays relative to the calf and segment lengths stay fixed. Existing
incoming NN joint residuals fade away rather than snapping on the entry frame.
Wall contact cannot override this free-leg path during the blend.

The earlier version assumed the body needed room for that legal path: a one-time31-sample shoe sweep planned
a smooth outward clearance envelope, zero at both ends of the existing Blend
time. In this folded entry it briefly moves the displayed body about30cm away
from the wall. It changes neither the ballistic root nor the settled pelvis
distance. This replaces the long arc, not a new permanent pelvis offset.

`verify-slide-entry.cjs` replays the reported setup plus full-gravity and later
fall recordings. Both hips stay legal throughout the reported blend, max thigh
increment6.52 degrees/120Hz, shoe penetration below0.002mm, fixed bone lengths.
The pre-slide serialized frames and physical root are identical to before.
All three settled leg-limit checks pass; native incoming violations in other
cases are not silently claimed absent. Slide exit/re-entry and split-generation
tests also pass. No new worker, inference, UI option, Unreal or Bodyflip change.
Receipts/source backups: Saved/FootIKSlideHip20261029/. Viewer93/97/101 inspected,
frame93 restored; saved camera, trim and tuning retained.

## Slide head gaze and irregular upper-body motion — October 29 (local)

The head gradually turns70% toward absolute down as root speed rises from its
slide-entry speed to Head max at m/s (default30), independently of the feet shift speed. The angle was
reduced from100% at the user's request. A0.65s entry ease
prevents snapping if that limit is already reached. The turn is distributed
across both neck joints and the head, with the existing Jolt angular limits.
Head max at m/s is appended at the bottom of More options, saved independently,
and accepts0.1–100m/s. The head speed endpoint no longer follows Feet max at m/s.

The five spine joints now share small irregular bend/twist targets, driven by
smooth deterministic noise and a damped spring. This is procedural articulation,
not added root forces. The bracing hand keeps its pre-gesture wall target and its
arm is solved again from the moved shoulder; the accepted free-arm circle and
speed bursts remain. Current601-frame root, pelvis and legs are exactly unchanged.
This intentionally supersedes the earlier free-arm-only scope described below.

`verify-slide-head-torso.cjs` checks two full recorded clips and the current
five-second scene, including a custom20m/s endpoint and the default30m/s endpoint.
Gaze reaches70% toward world down at the selected speed; at the default, maximum
adjacent head rotation is0.41° at120Hz, chest rotation0.18°, with5.8–7.4° chest
variation across each clip. All settled joint limits pass, hand contact error
is below0.000001mm and sole error below0.30mm. `verify-slide-motion.cjs` and the
updated `verify-slide-balance.cjs` also pass; the latter now preserves the exact
lower body/root and pre-slide prefix rather than requiring an unchanged chest.
Sources, poses and receipts: `Saved/FootIKHeadTorso20261029/`. Live8890 Refresh
loaded all300 display frames, retained paused frame203 and the saved camera,
and reported no browser errors. No extra NN calls/processes or Unreal changes.

## Free slide arm: neutral roll and balance circles — October 29 (local)

Current timing: the extra corrective reach offsets were removed at the user's
request. The original ellipse and elbow flexion use an integrated orbit clock
with irregular2.2–3.4× peaks, accelerating over0.10–0.17s and returning to1×
over0.40–0.64s. Quiet gaps run at exactly1×. Extra phase accumulates permanently,
so slowing down cannot rewind or jump the hand. The initial0.7s amplitude entry
keeps its original timing; contact-driven sway remains on the real physics clock.
Only traversal speed changes, not the authored circle or reach trajectory.
`verify-slide-orbit-speed.cjs` checks continuous monotonic time, repeatability,
quiet1× gaps and speed bounds over20s. Three full pose clips retain neutral roll,
legal arm joints and identical root/non-free-arm bones; peaks0.92m/s,12.61m/s²,
1.11°/120Hz supersede the original slow-orbit figures below.
Current receipt: Saved/FootIKOrbitSpeed20261029/; the old corrective-gesture
receipts in Saved/FootIKCorrections20261029/ are historical and rejected.

The dangling arm now carries the idle reference elbow plane with its clavicle,
then transports that plane to the hand target by shortest swing. The old fixed
wall-relative elbow pole was legal within the broad shoulder cone but twisted
the free arm102.9° from its transported neutral plane at the user's frame184.
The wrist retains its neutral forearm-relative orientation and true hinge elbow.

The downward-biased neutral arm makes a gentle7×10cm elliptical balance circle,
roughly0.55Hz with slow phase variation. It fades in with zero initial velocity
and acceleration; existing contact-driven inertial sway remains. A smooth reach
envelope replaces the hard extension cap, avoiding a radial-velocity hitch.
No extra controls, root forces, NN calls or processes. This is authored balancing
motion with inertial sway, not a dynamically simulated shoulder.

`verify-slide-balance.cjs` checks both free-arm sides through full recorded clips
plus the user's417-frame scene. Neutral elbow-plane deviation stays below0.000004°,
settled free-arm rotation steps below0.63° at120Hz, shoulder-relative hand speed
below0.47m/s and acceleration below3.42m/s². Shoulder/elbow/wrist limits pass;
the current root and every non-free-arm bone remain exactly unchanged.
`verify-slide-motion.cjs` also passes the full joint/contact/length/entry checks.
Current-scene before/after poses and viewer captures: `Saved/FootIKBalance20261029/`.
Shared API1 and other labs are unchanged. Refresh activates the source update.

## Slide solve performance — October 29 (local)

Surface preparation now publishes the poses already solved by its existing CPU
peer, in lossless `gzip-json-v1` batches. The viewer decodes/appends them instead
of repeating the entire root/contact simulation on the UI thread. This is still
120 Hz, stops at the end trim, and retains completed frame objects when extending.
Only appended poses cross the Node/Python pipe; cumulative batches accompany the
existing HTTP prefix response. No extra worker is started. The two-session limit
remains; evicting a same-version session resets and reuses its idle Node process,
preserving compiled code but clearing all simulation state. Source-version changes
still retire the old peer. Old offline responses without batches retain replay.

Within slide contact fitting, IK updates only the affected four-bone chain,
shoe corners/plane projections are reused while rotation is fixed, unused joint
diagnostics are skipped, and polynomial bisection stops when doubles cannot
subdivide further. Vector arithmetic avoids callback allocations. Other terrains
retain the existing leg solve; shared API1 is unchanged. Numerical comparison of
all417 current-scene frames gives identical roots, max13.4 micrometres positional
change and0.0018° rotation difference. Default full clips retain legal joints,
wall contacts and bone lengths; the prior extreme-tuning caveat below still applies.

Verification:5800 session/batch/trim checks,30 Python checkpoint/peer-reset checks,
18 shift checks,25 UI checks and both full slide-motion clips pass. The paired
standalone benchmark measured3.56× median raw-solver improvement under varying
laptop load. Browser before:23.70s terrain solve /24.22s ready, despite a cached
19ms server response. After pose delivery:0.30s preparation /0.44–0.46s ready
on Refresh. An initial fresh setting edit took6.30s before peer reuse. Final
uncached edits measured8.97/6.83/5.84s; the first cold-worker request was22.21s
(including NN import/model startup). These are distinct from cached Refresh;
10× fresh-solve performance has NOT been achieved. No priority boost, extra
workers, lower solve rate or looser contact/joint limits were used to chase it.
Receipts and pre-change sources: `Saved/FootIKPerf20261029/` from project root;
`verify-slide-performance.cjs` replays that local captured prefix. The app logs
`[Foot IK solve]` for actual edits, including backend duration/cache status.

A final reload also exposed seed eviction in the old mixed16-response cache:
it regenerated the gait seed for2.93s despite an unchanged scene. Surface pose
responses now have a separate16-item budget; small seed responses keep their
own16-item budget, cache hits refresh recency, and old surface filenames migrate
on use. Bounded-pose cache compression uses level1. `verify_response_cache.py`
confirms17 surface edits retain the seed, bounds/migration and compiled-graph
preservation. Only Foot IK's8890 service was restarted to activate this change;
saved scene bytes were identical. Unreal and other lab services were untouched.
Final post-restart browser check:1.43s to ready (seed57ms, pose response188ms),
frame43, trim0–208, hand40cm/20m/s and camera retained. Earlier cached loads were
0.44–0.46s; timing varies with the laptop's concurrent load.

## Speed-based slide target shift — October 28 (local)

Separate pairs follow Recovery speed in More options: **Feet shift cm** /
**Feet max at m/s**, then **Hand shift cm** / **Hand max at m/s**.
Shift defaults to 20 cm (range 0–50); speed defaults to 10 m/s (range 0.1–100).
Old shared values initialize both pairs and are explicitly persisted, so later
feet edits do not silently alter the hand after Refresh. Either pair can be
disabled with zero shift. Both feet share the feet pair; only the bracing hand
uses the hand pair. Each has its own damped offset and carrier velocity.
The feet and bracing hand request an upward shift along their slide surface:
`maxShift × clamp(totalRootSpeed / maxShiftSpeed, 0, 1)`. World up is projected
onto the plane and normalized; a horizontal plane has no uphill direction.
Zero shift restores the prior target path. The root/free arm are not shifted.
The neutral offset follows that request with a critically damped response
(10 rad/s), preventing a low speed threshold from creating a one-frame reversal
at the ballistic apex. Thus the requested offset is linear in speed; the
displayed limb motion has a short response time and can be reach-limited.

Joint reach can reduce the requested shift per limb. The solver follows the
connected feasible interval from the original target, eases near its boundary,
and transports the neutral knee/elbow bend planes to their shifted targets.
A small arm-extension margin keeps the elbow plane defined. Friction includes
the shifting neutral target's velocity; the first offset uses the existing
entry blend instead of generating an impulse. No new force reaches the root.
Settings save with the scene, retain playback/camera, and generate through trim.

Verification: `verify-slide-shift.cjs` passes 18 mapping/root/contact checks.
Both full default clips pass `verify-slide-motion.cjs`: legal settled joints,
fixed bone lengths, wall contacts, and maximum successive rotation 7.6°/12.2°
at 120 Hz. The deliberately extreme 50 cm / 0.1 m/s test remains legal and in
contact but still has a 32.2° calf step near the apex. Its relaxed no-inversion
criterion is a stress bound, not a claim of good motion quality at that tuning.
25 UI/trim and 15 friction/recovery tests also pass. Receipts are in snapshots.
Live Refresh and a 15→20 cm control edit preserve frame103, camera and trim0–208;
Enter commits and blurs. The later independent-pair split passes migration,
delta-save/reload, independent threshold/amount and zero-shift checks. All601
recorded frames exactly match the previous shared-setting motion when both
pairs match. Live Refresh retained frame126/camera/trim0–208 and saved the new
hand values. Receipt: `snapshots/slide-separate-shifts-verification.json`;
controls: `snapshots/slide-separate-shifts-controls.jpg`.25 UI/trim checks pass.

## Slide tuning controls — October 28 (local)

Appended beneath Blend s at the bottom of More options:
**Friction strength %** (0–300, default 100) and **Recovery speed %**
(10–200, default 100). Both save with the scene, regenerate only through the
end trim, and preserve the playhead/camera. Zero friction removes the feet/palm
catches. Lower Recovery adds damping; higher is quicker with more rebound.
The restoring pull already grows with distance, including the existing
progressive stretch guard. It is not a constant-speed return or a strictly
linear Hooke spring over its entire range.

Recovery changes damping inversely, leaving the distance-dependent spring and
friction force independent. Softening the spring instead was rejected because
it allowed larger catches and could paradoxically increase return speed.
Small adaptive integration substeps stabilize the low-speed/high-damping range.
At 100/100 the prior particle motion is bit-identical in the tested sequences.
15 focused checks cover defaults/bounds, distance response, zero friction,
independent force scaling, monotonic recovery and the full strength/speed grid.
Matched 15 cm release to 80%: 25% takes 1.408 s, 100% 0.300 s, 200% 0.167 s.
Actual rough-patch inward peaks at strength 100: 0.150/0.423/0.817 m/s for those
three speeds. Tests: `verify-slide-tuning.cjs`; receipt:
`snapshots/slide-tuning-verification.json`. No new server process or root forces.
Live UI: changed Recovery to 25%, Enter applied/deselected, motion regenerated
through frame 208 while retaining frame 149, then restored 100% from the ready
scene cache. Both controls remain visible at the bottom of the options panel.

## Slide recovery and relaxed feet — October 28 (local)

Contact catches now recover with a 9 rad/s spring and damping ratio 1.05,
scaled by the square root of the progressive stiffness. The previous 12 rad/s,
0.52-damped spring became increasingly underdamped on larger catches. Rough
patches and friction forcing are unchanged. Matched 15 cm release: 80% return
0.117→0.300 seconds, peak 1.256→0.616 m/s. Across both recorded slide clips,
actual recovery average speeds fall 26–44%, rendered peak speeds 26–42%, with
6.8–8.2 cm median half-second contact excursions remaining.

The preferred foot orientation is now calf-relative neutral, biased only 20%
toward the wall-aligned request, then projected into the existing ankle/toe
limits. The contact fit adjusts normal clearance only; it does not pull the
ankle sideways to flatten the shoe. Heel/toe/edge contact is permitted. Median
sole tilt is 26–35° versus 0–8° before; ankle deviation from neutral falls from
40–46° to 23–24°. The independent hip-cone knee swivel remains: that correction
enforces the hip, not the ankle. Knee hinge, arm constraints and bone lengths
remain valid. Contact fitting can still move the ankle along the surface normal
to avoid penetration; this is not an invariant-leg-position guarantee.

`verify-slide-compliance.cjs` compares the immutable
`snapshots/slide-compliance-before-surface.js` to current code, using recorded
NN responses and instrumenting contact particles only inside the test process.
15 checks pass, including matched release, actual recovery speeds, retained
motion, contacts/joints and exact root/pre-slide equality. Existing 26 friction
checks, full joint-motion checks and 5,796 resumable-session checks also pass.
No new settings, root forces, shared `createFeet` changes or server restart.
Viewer refreshed at the saved frame 201; original trim/camera retained.

## Bounded surface generation and Refresh — October 28 (local)

Incline/wall and edited-platform scenes generate only through the end trim.
Moving it forward extends the retained 120 Hz physics/contact/slide state and
30 Hz recurrent NN state. Moving it back retains the existing prefix and does
no new work. Required future root commands remain available to the NN; an
interpolated interval may require its next 30 Hz endpoint, but no unused future
limb simulation is run. Trim preview still returns to the prior playhead on
release; the frame display cannot advance beyond prepared motion.

The initial surface source now contains 0.1 seconds plus course metadata,
instead of an unused five-second rollout before the real root-coupled rollout.
Reference pelvis height comes from the already-evaluated warmup gait period.
For the saved Run/Left/36% fixture this differs from the former five-second mean
by 5.005 mm; root difference stays below 5.950 mm through frame 208. First source
poses match within 6.6e-16 m. The legacy stair planner still uses its full course:
its anticipation is noncausal, and truncating it changed earlier foot placements.
That planner was not changed by this surface-loading fix.

API 7 / generation protocol 1 owns at most two retained surface sessions in one
single-thread CPU policy worker. Checkpoints persist the recurrent tensors and
recorded prefix; restoration replays physics without repeating prefix inference.
Idle workers retire after five minutes. UI preparation serializes edits and
coalesces intermediate requests. HTTP deadlines cover response bodies as well
as headers; queue waits are bounded to 12 seconds, worker work to 45 seconds.
Failures show a retryable error rather than leaving a permanent loading screen.

Verification: 5,796 split/full generator checks, 25 app/trim checks, five network
timeout checks, 17 backend protocol checks and seven genuine-NN restore checks.
Split, restored and uninterrupted runs have identical prefix poses/root windows.
The user's saved trim was valid (0–208); the apparently collapsed brackets were
the blank page's initial HTML. Server 8890 was restarted alone with the existing
`snapshots/overnight-state.json`, hidden/below-normal PID 27988. No Unreal or
other-lab restart, new UI controls, or push.

Live viewer verified: saved frame 195 loaded through 208; Refresh took 127.6 ms
without rebuilding. Dragging 208→244 appended the same session (0.868 s backend,
zero extra NN calls because slide was already active); shrinking back to 208
did no generation. Playback advanced and looped, then frame 195 was restored.
The first cold load was still 18.8 seconds: policy startup and mirrored
server/browser physics remain real costs, not claimed eliminated here.

## Dangerous-incline slide prototype — October28 (local)

Appended at the bottom of More options: **Slide** (opt-in), **Fall speed m/s**
(default 2), **Blend s** (default 0.25, range 0.05–1). A nearby active surface
must be steeper than Minimum gravity incline. October29 correction: entry is
world Vy <= -Fall speed (2 means -2 m/s). Negative thresholds now allow early
entry during slowing ascent; see Signed Fall speed above. A zero threshold
still requires downward movement. Slide exits as soon as world Vy becomes
positive after descending, and can enter again on a later fall. Zero velocity alone holds Slide.

Exit resumes normal root control and NN inference. The last native gait pose
and its30Hz history are retained during Slide, rebased to the new root/heading,
and supplied once to reset the recurrent NN with its actual future root window.
The procedural slide pose is not fed into the gait network. The displayed pose
blends back after leg IK using the existing Blend time; old pins are cleared and
new pins acquire after that transition. Re-entry creates fresh slide contacts.

The current run scene with Full gravity10% keeps climbing through F300; the
same live inference request at100% peaks at F43 and enters Slide at F56 with
Vy=-2.048m/s. This supersedes the old ascent-trigger diagnosis below. Tests
verify an injected upward reversal, fresh NN history/current roots, later slide
re-entry, exact split-generation replay and native NN reset parity. Receipts:
Saved/FootIKSlideTransitions20261029/. Tests: verify-slide-transitions.cjs and
verify_slide_resume.py. The reversal impulse exists only in the test harness.

At entry retain actual root velocity, stop both mover drive and the support
spring immediately, and integrate full gravity without a speed cap. Full gravity
%, energy-conservation redirects, material pins, and contact grace cannot add
thrust during slide. Capsule collisions remain unilateral and frictionless:
they remove inward normal velocity, but never convert it into uphill velocity.
Thus freeflight is ballistic; an obstacle can still interrupt it. Freeze the
root-to-mesh frame on entry so changing incline alignment cannot move the drawn
root independently of the physical trajectory. Forecast copies carry the mode.

The procedural reference is mirrored for the nearer hand, chosen once from the
entry pose. Body faces partly out from the wall, feet are staggered, the near
palm braces and the free arm hangs below its shoulder with a relaxed elbow and
neutral wrist. The first tiny-sway version was rejected as too static. Each
sole and the palm now has its own compliant particle in the wall tangent plane:
Coulomb drag opposes absolute sliding velocity, while a damped elastic tether
returns it toward the nominal pose. Independent deterministic rough patches
have smooth leading edges and release intervals; spatial sampling is bounded
at high fall speeds to avoid jitter. State advances once per120Hz tick, outside
geometric contact iterations. Friction cannot reverse slip on its own. If a
contact is lost, drag stops and the tether recovers. Uneven contact tension
rocks the torso and drives secondary free-arm swing. No root force is added.
This is pose-only friction/compliance, not a simulated ragdoll. Contacts slide
along the plane and provide no root support or permanent tangential pin.

`slide-joints.js` uses Bodyflip Jolt's exact sharedIdle joint frames and limits:
ankles40/28 degrees with twist±25, toes35/8/±8, wrists45/40/±55, elbow hinge0–155.
It projects swing onto Jolt's quaternion-space ellipse. Both arm segments share
the hinge frame; shoulder feasibility swivels the elbow around the hand target
instead of twisting the elbow or moving the palm off the wall. Knees use the
neutral hinge reference with actual incoming bone lengths. The same feasible
swivel calculation now accommodates the hip cone around the hip-to-ankle axis,
retaining the ankle target and signed knee hinge during catches. Entry now uses
the constrained joint path described above. Foot contact fitting
alternates leg reach and ankle projection, allowing heel/toe contact instead of
forcing every sole flat. The embedded neutral reference has a provenance/hash
check against data/rig.json. This helper is loaded only by the Foot IK slide host;
Bodyflip's shared foot-placement bundle gains no dependency.

Blend uses the actual entry pose. Incoming NN joints can already be outside the
strict reference limits; ankle/wrist/elbow residuals decay over the existing
Blend time rather than snapping on the first frame. The old exterior ankle arc
is replaced by the constrained joint path and temporary body clearance above.
Feet follow calf-relative rotation during this free swing, avoiding an opposite
twist-limit snap. Knee bend planes are transported continuously. Locomotion
inference stops while Slide is active; the NN ghost carries the last policy pose.
Root debug arrow follows slide heading; Targets includes the sliding palm.

Historical October28 receipts (the ascent trigger/latch are superseded above):
32 focused checks cover the dangerous-angle gate, ascent/descent triggers,
latched state, zero thrust, exact velocity/position integration including collision
receipts, no energy redirect, limb lengths, sliding contact and recurrent replay.
Live fixtures: threshold2 enters at22 with +3.51m/s; threshold5 enters at109 with
-5.01m/s. NN calls remain10/54, with physical/recurrent replay error zero. Every
settled joint passes the reference limits in these two wall fixtures; heel/toe
gap≤0.011mm, palm gap<0.00001mm, fixed bone lengths. Maximum post-entry joint
increment7.1/12.5deg per120Hz tick; knees4.6/10.9deg. Incoming NN sharpness is not
claimed fixed. The free hand stays>43cm below its shoulder and continues moving
after the pose blend. 37 prior pelvis-speed checks retain exact Slide-off
Walk/Run motion. Tests: verify-slide-joints.cjs (projection/hinge/shoulder),
verify-slide-motion.cjs (full sequences), verify-slide.cjs (root/contact).
Owned browser checked the real8890 inference route and captured both entries,
current130, later motion and other viewpoints; playback advances and real saved
state remains unchanged. Evidence: snapshots/slide-joints-*.

Contact-motion comparison: `node verify-slide-friction.cjs --compare` replays
both recorded policy streams, compares immutable before-v2 to the current
solver and writes120Hz series. It tracks fixed ankle/palm material points;
lowest shoe-corner switches are excluded from motion/derivative measurements.
26 checks pass: exact root and pre-slide poses, deterministic replay, bone/joint
and contact constraints, settled joint steps<3deg, and at least2 cm median/p10
travel in half-second windows. Actual median ranges10.3–12.1 cm (before0.07–0.43
cm); minimum window7.1 cm. Knee ranges16–23deg, torso rotation6.6–8.7deg. This
detects static limbs; it is not a numerical certificate of perceived realism.
The free elbow remains at a relaxed bend, and spine articulation relative to
pelvis remains fixed; their motion comes from the torso/shoulder response.
`node render-slide-friction.cjs` regenerates snapshots/slide-friction-stable-points.svg.
Updated live viewer inspected at195/207/219 and restored to195 with camera/tuning.
No new UI, background process, server restart, Unreal change or push.

Limits: this is not a whole-body Jolt simulation. The transition can temporarily
exceed hip limits when recovering a strongly folded incoming pose; the85-degree
cached-gait probe also found a thigh limit exceedance. Ankle/wrist/elbow limits
and actual contact are the enforced slide requirements. Do not claim universal
full-body constraint compliance from the two settled wall fixtures.

Port8890 was found stopped again on the user's unloaded-viewer report. Started
only Foot IK with snapshots/overnight-state.json, hidden/below-normal (PID448).
Health checked after launch; the in-app viewer visibly loaded the saved wall
slide at frame130 and remains open, with scene/camera preserved. The source has
no HTTP-host idle shutdown; the300s timeout retires only the NN child. The prior
host's exit cause is unknown. No Unreal/other-lab changes or push.

## Dangerous-incline pelvis closeness and speed blend — October28 (local)

Accepted prior state pushed and remote-verified as16d1fe0a93b469f4ab3fd0a87d337cee8e229f88
on codex/standalone-sim. Scoped Foot IK sources/tests/fixtures, approved profile
and recovery inventory included:9136 files,1,096,116,002bytes, no LFS pointers.
The new option below is subsequent local work, ready for user Refresh.

The controls remain after Unpin below at the bottom of More options. The previous
Pelvis closer amount is now Pelvis min cm (`pelvisCloser`). A compact Min / Max
Speed m/s pair (`pelvisSpeedMin`, `pelvisSpeedMax`) and Pelvis max cm
(`pelvisCloserMax`) follow it. Both amounts allow 0–50 cm. Use the magnitude of
the actual simulated root velocity, including vertical/lateral motion, rather
than the requested gait speed or playback multiplier. Linearly blend the two
amounts between the speed thresholds, clamping outside them. Either endpoint
can be larger. Max speed is clamped to at least Min; equal thresholds select the
low amount at/below that speed and the high amount above it.

New speed defaults are 0 / 3.5 m/s. An old save's maximum amount inherits its
existing minimum amount, preserving the tuned motion exactly until edited.
The user's current 10 cm setting is retained. A dangerous incline is steeper
than Minimum gravity incline, independently of the Incline gravity checkbox.
Multiply the speed-selected amount by a linear angle ramp from 0 at the minimum
to 1 at 90°. For minimum 80° and selected 20 cm: 80°→0, 85°→10 cm, 90°→20 cm.
Minimum 90° disables the ramp.
The existing smoothed surface frame carries the displacement toward the surface,
so entering a wall does not apply an instantaneous20cm translation.

The mesh root/controller and NN foot targets remain separate from this posture
shift. Translate hip anchors/torso before leg IK, then solve to the original
foot targets and material pins with the accepted signed NN hinge. The NN ghost
remains the uncorrected reference. Pelvis readout reports the inward offset.
Bodyflip has no change unless its host supplies the new optional pelvisShift.
Both amounts zero and all surfaces at/below the minimum reproduce the approved
motion exactly.

Speed extension: 37 checks cover speed/angle endpoints, reverse/falling speed,
both blend directions, migration, exact pre-change Walk/Run frame hashes,
bone lengths, signed knees, material pins and sole clearance. The owned browser
verified the compact pair has no horizontal overflow, Enter commits/blurs,
playhead and values survive reload, and real server state remains unchanged.
One live 10→30 cm recurrent rollout took 4.04 s; replay error was zero, material
pin drift below 2e-15 m and shoe penetration below 4e-8 m. Reviewed saved frame
137 plus 76/95/143/180. Evidence: verify-pelvis-speed.cjs,
verify-pelvis-speed-browser.cjs and snapshots/pelvis-speed-*.

81 focused checks cover Walk/Run,0/80/85/90°,zero/default/max offsets, bone lengths,
normal displacement, upper rotations, signed hinges, sole clearance and pins.
13 accepted-frame and17 causal-coupling checks pass with closer explicitly0.
Actual saved scene20cm full recurrent rollout: minimum hinge dot0.884, root replay
error0, pin drift<2e-15m and shoe penetration<4e-8m. Saved76 shows19.55cm inward
because the ground frame is still settling. Visual comparisons at0/20 and76,
95,143,180 checked. Owned browser verifies bottom placement, Enter blur/commit,
frame retention and persisted refresh. Real user state was byte-equivalent
before/after; one CPU inference request took3.24s. No restart or new background
worker. Tests/evidence: verify-pelvis-closer.cjs,
verify-pelvis-closer-browser.cjs and snapshots/pelvis-closer-*.

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
