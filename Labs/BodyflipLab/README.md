# Bodyflip Lab

Independent desktop lab, created October 24, 2026. Open **Bodyflip Lab** on the
Windows desktop, or run `launch.ps1`. The loopback service is
<http://127.0.0.1:8876/>. It uses its own Edge/Chrome app profile and saved settings.
Unreal is not required for playback. Jolt and the frozen network weights are local.

UI placement rule: preserve existing controls and their order. Append new options
at the bottom of the existing section; append horizontal controls on the right.
Do not reorganize controls by topic when adding a feature. Cone angle is last in
More options; Cone debug is after Bones in the viewport toggle row. At the user's
request, More options is now a collapsed dropdown under the view buttons at the
top right of the viewport. Its internal order is unchanged; expanded contents
scroll within the viewport. The same controls remain available in Idle, Walk and Run.
Refresh now matches Throw Lab: a green button centered below the top-right
scene action buttons, in a96px header. Existing controls retain their order.
Its existing save-and-restore playback behavior is unchanged.

Camera drag correction (October25): left-drag horizontal orbit now subtracts
dx from yaw; the previously requested inverted vertical mapping still subtracts
dy from pitch. Horizontal had retained its original sign, rather than being
changed by the earlier Y edit. Pan, target drag, presets and saved camera remain
unchanged. App syntax checked.

## F145 foot-release snap - October 31 (current)

The saved left-foot snap came from the release handoff. Contact history was
translated back into the internal trajectory's coordinates, then foot follow
projected it against the unchanged world floor. That invented penetration and
moved the captured foot forward. Projecting only its joints was insufficient:
the displayed knee includes floor clearance, so it must be captured as well.

Release samplers now accept the existing pose projector and execute it in world
space before rebasing. The physical flight integrator initializes its pose from
that captured release articulation; contact-side momentum, COM velocity and
Jump% impulse still supply its motion state. This prevents the pose correction
from being interpreted as an instantaneous limb movement requiring rigid recoil.
No new blend, gate, tuning control or solver iteration was introduced. The fixed
departure target, knee extension, one inertial return and separate hand timing
remain in place.

Frozen actual-app/Jolt/NN replay: F144->145 left-thigh change53.74->3.94deg;
the release boundary itself is0.121mm at the ankle and0.085deg at the knee.
Both markers still push at1.208333/2.4s; J2 releases at2.4079266s (4microseconds
different).364 origin-invariance/release checks,1126 earlier leg-continuity
checks,566 physical-flight checks,14 strength cases and five hand cases pass.
The approved flipless Space gym remains byte-exact across19attacks/684samples.
Native V8 parity passes48frames/10583numeric comparisons with zero difference.
Receipts: Saved/Diagnostics/BodyflipPort20261030/foot145-{input,before,final,
verification}.json; reproduction: probe-foot145.mjs. Live state and editor were
not changed. Refresh loads the fix.

Scope note: verify-foot-follow.mjs's old <3deg absolute world-aim assertion
already fails under final physical balance (39.91deg before this change,
40.91deg after). The subsequent rigid momentum correction turns that aimed
leg along with the body. This turn fixes the release discontinuity; it does
not claim that older absolute-aim contract passes. The current contact buildup
also retains its fast pre-release extension; it was not replaced by a new filter.

## Planted push landing ownership - October 31

SUPPORT means approach, before accepted contact. LOAD means planted buildup.
Saved axis-only J2 reached contact at2.3375s, but the other toe (ball_r) touched
at2.35833s and incorrectly handed control to locomotion before the2.4s push.
While PIN is active, additional hand/foot/toe contacts now join the existing
support-contact set. Collision response is retained; those contacts stop being
owned once lifted clear. Torso/head hits and contacts during approach/free fall
still cause normal landing. Current scene now pushes/releases at2.4/2.40792s.
RISE/FALL also uses the resolved COM velocity including collision carry, rather
than the source velocity before that carry.24 focused ownership/phase checks
and five paired-hand regressions pass. Actual app VM replay confirmed both
markers push, without desktop control or saved-state edits. Runtime repackaged.

## Jump strength - October 31

Jump % now commands COM takeoff energy directly for every successful foot/hand
push, whether spinning or not. The previous knee-extension trajectory only used
requested energy as a stopping threshold: a reaction/reach release could deliver
much less, independently of a larger percentage. The saved second200% push asked
for6.485m/s but delivered3.223m/s COM speed. The contact animation is no longer
the authority on jump strength.

One shared reference height (trimmed Run L,1.032640m) defines100%. At release the
surface supplies a gameplay impulse: outgoing COM velocity is retained tangent
velocity plus the skewed push direction times sqrt(2*g*referenceHeight*Jump%/100
+ 2*returnedReboundEnergy). Rebound remains its existing explicit option. With
Rebound0 on flat ground, height is exactly proportional to Jump %:70%=.722848m,
100%=1.032640m,200%=2.065280m,400%=4.130560m. Feet/hands, left/right animation
choice, pose recovery and spin do not silently reduce this command. Carrier
collision velocity is included once; actual later collisions can still alter
flight. Zero% and a support lost before pushing receive no new launch impulse.

This deliberately uses a contact impulse at release, not a claim that the visual
extension supplied that velocity through a finite physical force. Position is
continuous and the existing load/pin/follow animation remains in place. Only
translation is corrected for non-spinning surface jumps; no angular reaction is
introduced there. Active spins retain their momentum solve. Flipless Space gym
attacks keep their exact approved motion. RISE/FALL now follows actual flight
velocity, rather than the old extension trajectory's earlier apex.

Current saved scene (J1=150%, Rebound50%) compared with identical inputs except
J2 percentage:70% leaves at4.03647m/s (~.83m rise),200% at6.51348m/s (~2.16m).
14 strength cases cover0..400%, both hands/foot, no spin/spin, zero Load, reverse
seek, exact ballistic height and projected release continuity. Five paired-hand
release/miss cases and566 core flight checks pass. Receipts in the diagnostics
directory: `jump-percent-before.json`, `jump-percent-after.json`,
`jump-percent-after70.json`, `jump-strength.json`. Fresh native V8 parity passes
48frames/10583numeric comparisons exactly;19attack/684sample flipless Space gym
preservation remains exact. Saved state and editor untouched.

## Momentum balance during flips - October 31

Release-velocity correction: the initial balance implementation averaged COM
velocity over the final1/240s of contact. A short push was still accelerating
strongly during that interval, so this discarded the last part of the impulse.
In the saved first100% jump, upward release speed was3.074m/s instead of4.366m/s,
giving only.482m ballistic COM rise instead of.972m. Translation now uses a
second-order contact-side derivative at.1ms spacing, extrapolated to release.
The contact trajectory, Jump%, angular balance and saved settings are unchanged.
Two extra source samples are evaluated once per release, not per playback tick.
Analytic short/oblique push and falling-release regressions pass (562checks in
the flight suite); five hand-contact cases and19attack/684sample exact no-spin
preservation pass again. Current-scene launch receipts: `jump-height-before.json`
and `jump-height-after.json` in the diagnostics directory below. The original
scene timings/aim metrics below predate this correction; J2 contact timing changes
because J1 now stays airborne longer. Native runtime is repackaged with the fix.

Before the explicit launch contract above, the remaining height difference was:
the saved first jump's original source
COM rises about1.226m, versus.972m with ballistic COM (about21% less). The source
root leaves at4.629m/s while the actual COM leaves at4.366m/s, and the old pose's
COM rises another.138m relative to root by the old apex. Fixing the derivative
therefore did not restore the old height. Preserving that height with ballistic
COM would require a larger contact impulse. That root-versus-COM ambiguity is
now superseded by the explicit launch contract above, separate from angular
momentum balance.

Active bodyflips/twists now pass through one final rigid-body reaction solve.
It measures all25 bodies' spin and orbital momentum about COM after attack,
aim and released-limb articulation, then applies a COM-centred correction using
the shared physical inertia tensor. At most3 small3x3 solves per240Hz tick;
no per-limb optimizer was added. Existing attack joint poses, arming and soft
leg choreography remain the articulation source. Contact owns the motion until
the last support releases; the measured release momentum and explicit command
changes drive free flight. COM follows the release velocity plus gravity/cap.
Collision/landing runs after balancing and seeds the normal NN continuation.

User requirement: flipless microgravity attacks must remain EXACTLY unchanged.
When no spin has been activated, the original motion and external aim path run
without creating a physical track.19attacks/684samples match the preceding
global and aimed poses exactly in both checkbox modes, including reverse seek.
This preserves the approved animation; it does not claim that old no-spin
animation now conserves momentum. Preview attack generators were not rewritten.

New `3D momentum` checkbox is appended at the bottom of More options, default on.
On balances the full world momentum vector; off allows rigid reaction only
about the commanded axis and conserves that component. Transverse momentum
remains authored in the axis mode. Explicit spin-command changes are controlled
momentum inputs. Inertia100% preserves reference-command momentum;0% retains
constant commanded speed despite compaction while still reacting to articulation.
Stopped commands retain the previous axis in axis mode. Angular-velocity debug
metadata now measures the corrected carrier, with old velocity in commandedOmega.

Aiming predicts the balanced motion using a bounded endpoint solve: at most
two small Jacobians,60Hz prediction, final240Hz playback. Full3D uses spine bend
variables because a whole-body yaw would be canceled by the reaction. Fixed-axis
mode also has yaw freedom. This is approximate and does NOT guarantee all target
directions: saved scene residual is.08537 (~4.89deg) toward its partial-aim goal
in3D and.39614 (~22.85deg) in axis mode. It no longer searches wrapped multi-turn
solutions to force a hit. No-spin aiming is unchanged. Moving the target in a
spinning lab updates the marker during drag and regenerates on release; numeric
target/aim edits regenerate immediately, preserving playback time.

Saved-scene current checks: full-vector momentum error <.00043kg m^2/s during
the measured free-flight ticks, anatomical violations <3e-15rad. The earlier
F140->150 reversal is absent: J2 total momentum is approximately
(40.11,.21,-14.22)kg m^2/s across those frames. Axis-only error <4.2e-6 on J2's
selected component. Five paired-hand cases cover retention, single release,
lost supports/no phantom push, mirrored spin and seek order. Fixed the carrier
offset being counted twice at release; maximum positional seam1.64e-6m.

Performance: isolated full balance at240Hz costs roughly.7-1.0ms per60Hz frame
on this laptop, excluding source animation, collisions and rendering. Target
planning is cached, not performed per playback frame; warm standalone planning
~134ms. Saved whole-scene preparation measured8.77s including source/NN/contact
work. These are separate measurements; this is not a claim of8.77s realtime
execution or a measured render framerate. Immutable aim-cache optimization is
bit-identical. Core tests96+553 checks; exact no-spin preservation and actual
app/native adapter parity pass (6frames,0position error,5.96e-8rad max rotation).
Native V8 parity also passes48frames/10583numeric comparisons exactly across
slash, kick, both throws, foot and hands. Runtime package updated; no C++/
Blueprint/editor rebuild or saved-state edits.

Receipts under `Saved/Diagnostics/BodyflipPort20261030`:
`physical-scene-result.json`, `physical-scene-axis-result.json`,
`physical-contact.json`, `no-spin-preservation.json`, `physical-app-parity.json`.
Regression scripts: `verify-centroidal.mjs`, `verify-centroidal-flight.mjs`,
`verify-physical-contact.mjs`, `verify-no-spin-preservation.mjs`.

## Physical audit of the saved slash - October 31 (before the balance)

The earlier constraint-order fix is valid but does NOT make the complete motion
physically consistent. No production behavior or saved scene changed in this
audit. Actual app initialization and offline sampling of the current saved J2
slash use one Jolt world, real NN responses, no desktop control or state writes.
Sampled F134-194, with backward differences at240Hz and480Hz. Receipts and chart:
`Saved/Diagnostics/BodyflipPort20261030/physical-audit*`.

Measured all25 rigid bodies using the shared45kg mass model: sum each body's
spin angular momentum plus orbital momentum about the whole-body COM. At F140,
F150 and F160, final momentum along the fixed world flip axis is approximately
35.45,-2.00,35.00kg m^2/s (480Hz;240Hz gives35.50,-1.70,34.93). All physical
colliders are clear of the ground over F138-164, minimum8.78cm. The scalar
controller reports a constant23.798 axial budget, but this excludes the moving
limbs. These are not external-contact impulses or floating-point noise.

Findings, in pipeline order:
- The compensation target is the momentum of an authored opposite-angle pose,
  NOT conserved airborne angular momentum. Its low solver residual only means
  it follows that target. At F144 compensation drops pelvis rotation from the
  applied251deg/s flip component to about94deg/s before aiming.
- The result passes through independent pelvis/hip/knee/foot springs with60ms
  lookahead. Their final velocities are not fed back to the momentum solve.
- Spin preserves I_axis * omega for its input pose but omits articulated limb
  momentum. It deliberately retains a fixed commanded axis; it is not a full
  torque-free rigid-body/articulated dynamics solve.
- World-space support-leg follow is applied AFTER that inertia calculation.
  It preserves COM position but does not supply an equal-and-opposite angular
  response. At F150 it changes axial momentum from15.71 to0.71kg m^2/s (240Hz)
  while leaving pelvis speed unchanged. This is a major independent error.
- Aiming is later still and also changes momentum without compensating it.
  At F150 it changes that axial value from0.71 to-1.70kg m^2/s. It is not the
  principal cause of the early pelvis slowdown, which already exists upstream.
- Pelvis return starts at Hit (F164.463), overwriting its current evolution with
  the captured hit offset times a scalar fade. No velocity matching or momentum
  balance is enforced at this handoff. It cannot explain F138-150.
- COM itself follows pose-dependent motion: at F144 measured horizontal COM
  acceleration is approximately(6.4,-6.4)m/s^2 in world X/Z with no contact.
  The attack and compensation stages already contain it; later COM-preserving
  projection/rotation retain it. This is separate from rotational conservation.

The old attack-inertia capsule approximation differs from the shared physical
mass model by at most0.118kg m^2/s here; worth unifying, not the main fault.
The shared constraint/aim tests and native parity checks do not test whole-body
momentum conservation. Existing spin-momentum test explicitly tests controlled
axial inertia, not the articulated result. Simulation is also driven by direct
per-body velocity commands; merely selecting Sim does not establish conservation.

Recommended next implementation: one final whole-body momentum balance including
attack, aim, support follow, recovery and smoothing, plus a separately integrated
ballistic COM. Use compensation percentage as a posture preference, not a
physical conservation percentage. Re-check final displayed motion, not just the
intermediate controller. Retain the user's fixed-axis preference explicitly:
arbitrary prescribed joint paths, fixed rotation axis and exact vector momentum
cannot all be independently imposed; use remaining articulation freedom or
report the conflict rather than silently restoring the rejected free-tumble mode.
Physical reference: MIT Underactuated Robotics, centroidal dynamics,
https://underactuated.csail.mit.edu/humanoids.html .

## Constrained attack compensation - October 31

Compensation now evaluates the existing anatomical joint limits inside its
momentum solve. Source, baseline, opposite-angle target and each trial pose
are projected before their momentum is measured. The inertial response and
pelvis recovery also return legal poses; projection preserves whole-body COM.
Rigid compensation uses the same ordering. No new gates, tuning or UI changes.
The requested percentage still defines the opposite-angle target; limits can
restrict that target. This remains an authored response with inertial smoothing,
not an exact conservation law for the entire final aimed animation.

The saved J2 slash previously lost60.8deg of spine01 rotation during later
projection at F148-150 while retaining its pelvis response. That late rejection
is now numerical zero. Actual app replay F134-205: final pelvis rotation along
the flip axis at F144 rises from40 to93deg/s; F156 falls from406 to313deg/s.
The remaining speed variation includes the intended attack counterrotation.
Saved scene, compensation100%, arming times and fixed-world spin are unchanged.

Verification:56cases/2750samples across14 upper-body attacks, both rig profiles
and soft/rigid compensation; maximum late correction4.04e-15rad. A source change
entirely discarded by joint limits produces zero change in pelvis response.
COM preservation and reverse seeking pass;17attack/2571entry samples and60native
aim cases pass. Runtime-only package refreshed; no C++/editor rebuild.
Receipts: `constrained-compensation-verification.json`,
`all-armed-entry-verification.json` and saved slash traces under
`Saved/Diagnostics/BodyflipPort20261030`.

## Live Harness angular arming - October 31

Direct to Armed now uses the live Final Harness distance rule for all17 melee/
sword/kick clips and both throws. Sum shortest joint-local angular distances
from the current pose to Armed; divide by GT's accumulated frame-to-frame
angular travel from frame0 through Armed; multiply by GT's windup seconds.
Like the live implementation, compare clocks including/excluding forearms and
keep the shorter one. Default far-distance exponent and speed coefficient are1.
The fixed authored windup floor is removed. Existing Attack In remains the
explicit minimum, plus one60Hz frame for a nonzero interpolation interval.

The clock measures the active attack joints in the carrier frame: upper-body
attacks include the pelvis rotation transferred to spine01; kicks also include
pelvis and striking leg. Bodyflip/world travel is not counted as arming travel.
The separate aiming correction remains separate from this articulation clock.
Retain Bodyflip's existing C2 interpolation and Armed->Hit/Release->End source
speed. This ports the live angular-distance rule, not its ground stepping,
head/pelvis world-speed constraints or GT-LUT interpolation shape. Off retains
the original entry path. No controls were moved or added.

Throws now honor Direct to Armed too. They use the charge-specific Armed pose
and retain charged post-Armed timing, release impulse and existing recovery.
Kick viewer, timeline and manual attack paths share the same duration rule.

Current saved J2 slashL: arming.333333->.230350s (20->13.82frames at60Hz);
Armed2.4824531973, Hit2.7410531780, return end3.1657865306. Source Armed->Hit
stays.2585999807s. Actual app F130-205 replay completed without live writes.

Verification:1141 checks/19attacks, including executing the live harness's
actual angular-distance/LUT functions (maximum distance discrepancy6.37e-8rad),
shorter/longer/zero travel, cumulative GT reversal and0/10/100% throw charge.
17attacks/2571entry/manual samples;56arm cases/11221samples;2004kick samples
with COM, hinge, carry and viewer parity;60native aim cases;6native throw aim/
constraint cases. Throw app initialization/release uses one real Jolt world,
no rasterization or desktop control. Native JS package updated:48frames/
10595numeric values exact across kick/slash/throws/foot/hands V8 parity.
No C++/Blueprint/editor/state changes. Receipts: angular-arming-verification.json,
Saved/Diagnostics/BodyflipPort20261030/slash-trace-distance.json and v8-parity.

## Slash arm entry correction - October 31

Removed the rejected Modified rotations experiment, including its UI, settings
and solver branch. Old saved fields are discarded during sanitization; scene
files were not edited. Fixed combined world-axis spin remains the sole mode.

The saved slashL entry was blending an authored forearm twist into a hinge
elbow. Near F148/F155 its quaternion crossed the hinge projection singularity,
making the shoulder/elbow change abruptly. Arm animation keys are now fitted
to the existing joint rig before interpolation. The same arm track feeds
pose matching, Direct to Armed and normal authored playback. Spine/pelvis/leg
source rotations, attack clocks, joint limits and tracking speed caps are unchanged.

Actual app replay, F130-205, with saved J2 slashL:
- F148 left shoulder/elbow/wrist local steps:13.79/13.11/15.00 ->4.25/.60/3.46deg.
- F155:28.12/28.10/28.57 ->7.23/4.40/2.64deg.
- Armed2.5854366064s, Hit2.8440365871s and return end3.2687699397s unchanged.
- No live state writes, editor changes or desktop interaction.

Checks:17 attacks/2700 entry/manual/return samples;56 arm cases/11520 samples
across both rig profiles and entry modes;60 native-profile aim cases;4381
fixed-axis spin checks. The arm check verifies hinge-axis interpolation, not a
claim that every unconstrained polynomial stays within its angle interval:
raw blends can exceed that interval and final joint projection still applies.
No universal visual-cleanliness claim for every attack/pose follows from these tests.

Full native JS package regenerated; native-slash V8/Node parity8frames/1729
numeric values exact. No C++ build needed. Receipts in
Saved/Diagnostics/BodyflipPort20261030/slash-*.json and v8-parity/v8-receipt.json.
Older modified-*.json receipts describe the removed experiment.

## Commanded spin axis - October 30 (default mode)

User rejected the unwanted twist produced by unrestricted full-tensor momentum
conservation during a pure front flip. The spin controller now captures flip
and pelvis-up twist command vectors in world space at command onset. Their sum
defines one axis; the pose's moment of inertia changes speed along that axis.
Combined spin no longer reorients its twist axis every tick, and zero twist
cannot acquire a new axis from asymmetric limbs or off-diagonal inertia.
This is controlled rotation with axial inertia scaling, not conservation of
the articulated body's complete angular momentum vector. Authored pose movement,
contact correction and recoil remain separate from the global spin rotation.
Keep markers preserve the captured vectors/reference tensor; explicit changes
ramp them. Explicit zero stops the global rotation.

`verify-spin-momentum.mjs` now verifies this controlled-axis contract:4381 checks,
maximum measured rotation-axis error0.0000015deg, axial balance error0.000751%,
including moving poses/recoil/delayed launch/Keep/mixed axes/reversal/zero.
The saved260-frame replay retains the front-flip plane through jump1; at F93
the pelvis right vector is[-.9948,.0373,.0946], replacing the near90-degree turn.
Saved settings/markers are untouched. Native runtime is repackaged; see the
latest axis-native-parity receipt for parity results. The full-tensor experiment
and its historical conservation results below are superseded.
Current native kick/foot/hands parity:24frames, zero numeric differences.
Both saved jumps report Push at1.2354167s and2.2666667s without retiming markers.

## Superseded full-tensor spin experiment - October 30

Flip and twist commands now establish world angular momentum once at command
onset. Smooth commands ramp that momentum; blank markers retain it. Each tick
uses the full collider inertia tensor and subtracts the angular momentum of
articulating limbs to obtain the global rotation rate. The former sum of a
world-fixed flip velocity and a pelvis-following twist velocity steered combined
spin continuously. This correction supersedes scalar flip/twist multiplier tests.
At Inertia100% the experiment used the physical tensor; lower values blended toward the
reference-pose tensor and reduce articulation compensation. Secondary recoil
remains on and participates in the same balance. Angular velocity can precess;
angular momentum is the conserved quantity during free flight.

`verify-spin-momentum.mjs` passes4365 checks: fixed/moving poses, three axes,
flip/twist/combined spin, recoil, delay/ramp/reversal, Keep and explicit zero.
Independent collider-trajectory measurement gives maximum0.131deg direction
error and0.539% vector error. Keep-marker displacement is below2e-14m.
Native V8 parity passes24frames/5228values exactly; runtime is repackaged.
Historical verify-spin/verify-instant-spin assertions demanding scalar inertia
ratios and identical recoil/no-recoil angular speed are superseded, not passes.

The saved260-frame scene was replayed without modifying state. Jump1 still
pushes at1.2354167s; the new physical rotation changes jump2's approach: upperarm_l
contacts the floor at2.2791667s before its planned2.31875s push, so it reports
Miss. No contact rule or marker timing was relaxed to retain the old outcome.
Free-flight spin samples of both segments have measured momentum vector error
below0.179%; contacts and locomotion handoffs are external interventions.
Receipts/recording: Saved/Diagnostics/BodyflipPort20261030/momentum-*.

## Throws and rotating attack aim - October 30 (current)

Approved jump/landing/starting-yaw checkpoint67516390 is pushed; its exact saved
scene is under approved/2026-10-30. Subsequent integration remains local.
Big/Small throws now share the attack markers and the existing Jolt world, using
the approved Throw Lab evaluator. Charge and throw speed appear at the bottom of
the marker controls. See [throws](THROWS.md) for source fidelity and release data.

Attack aiming evaluates the complete future pose, including bodyflip, twist,
secondary motion, contact and anatomical projection. Direct attacks reach their
correction at Armed; circular attacks at Hit; throws aim total projectile COM
velocity at release. Spine joints absorb the bend first; pelvis tilt supplies
only the residual required when their limits are insufficient. A legal local
joint-coordinate path avoids the old quaternion branch snaps. Recoil now defaults
to60% for all spin changes; explicit saved zero remains zero. Idle/Space root
heading now uses a stable horizontal reference instead of roundoff in a vertical
axis. User scenes/settings were not rewritten.

Final audit:714 melee target cases and51 whole paths sampled at240Hz pass;
72 throw directions with stationary/spinning carriers pass. Actual collider
contact sheets inspected. Lossless hot-path changes pass878 exact comparisons;
192-pose projection median163.9ms ->148.1ms, full spin timing unchanged.
[Predictive aim evidence](../../Docs/BodyflipPredictiveAimAudit20261030.md),
[performance evidence](../../Docs/BodyflipPerformance20261030.md).
A slow throw cannot counter arbitrarily large incoming COM velocity without
changing its strength; no silent speed override is applied.

The contained live Unreal port is built and validated. It embeds the same solver
and frozen NN graphs, uses one background planner and the shared native Jolt
world, and reads the agent's actual PHAT constraints, masses and colliders.
All five final physical cases pass: kinematic/sim, both throws, one-hand and
two-hand pushes. Final Node/V8 parity is exact across24frames/5,216 values.
Use `StartBodyflip` explicitly; existing Blueprint wiring and the user's editor
session were preserved. Scene preparation can still be slow (62.737s for the
saved260-frame NN scene); this is not a gameplay frame-time measurement.
[Native API, evidence and limits](../../Docs/BodyflipNative.md).

Native Blueprint controls now have typed options: **Start Bodyflip** takes a
Settings struct; **Queue Bodyflip Jump** exposes At Time, Jump Percent, Push With
and Spin/Pose/Attack structs. Right-click an option pin and choose **Split Struct
Pin**, or connect its Make Struct node. Attacks and directions are enums; distances
are centimetres and durations are seconds. Legacy JSON nodes remain deprecated
for existing wiring; the typed nodes need no JSON input.

## Starting yaw - October 30 (approved checkpoint)

Start yaw, appended at the bottom of More options, controls frame-zero facing
only (-180 to180deg, default0). It does not rotate the root path, velocity,
platforms or target.180deg starts backward locomotion along the same world path.
For Walk/Run, the selected gait-phase history is rotated about each root and
feeds the existing NN in the new facing frame with unchanged world root commands.
This is a new seeded rollout, not a rotated forward-gait loop. Generation stops
at the trim and extends recurrently when untrimmed. Idle/Space use rotated poses.
Jump source orientation follows the starting yaw; rig rest geometry is unchanged.
The existing numeric apply/preserve-time/save behavior is reused.

3132 facing/path/settings/trim-extension checks pass for all four modes at
-180/-90/45/90/180deg. Actual backward Run NN checked F0-60: facing stays backward,
root continues +Z at5m/s.809 backward-landing checks still pass. Scene unchanged,
no GUI/server restart; Refresh loads. Evidence: Saved/BodyflipLab/StartYaw/.

## Landing heading and continuity - October 30 (approved checkpoint)

Landing root yaw now follows the pelvis horizontal facing. Both history poses
and the full root command path are transformed into that heading for the
unchanged locomotion NN; predictions are transformed back to world space.
The same yaw reference is used on both sides of the body blend, avoiding a
new reference-frame orbit. World root trajectory/momentum are unchanged.
No forced RunF facing after backward landings; no policy/server restart needed.
Current saved twist300 case lands facing179deg and stays facing backwards
through F228.808 original-scene and809 backward-scene checks pass, including
physical landing continuity, fixed heading, seeking and no thigh loop. Current
backward recovery minimum forward COM speed4.05m/s, maximum right thigh
1.20deg per240Hz tick.1126 earlier jump checks still pass. Fixtures contain the
actual seeded NN responses; source scene state untouched. Evidence in
Saved/BodyflipLab/LandingHeading/. Included in checkpoint67516390.

The following describes the preceding continuity fix:

Fixed the saved F195 locomotion handoff in capsule.js. Airborne spin rotates
its virtual root; NN decoding uses an identity root. Landing now changes that
reference frame while preserving every physical bone in world space, before
blending. Previously the two reference frames blended and orbited the pelvis:
root forward speed stayed5m/s but displayed COM briefly moved backwards.
The body now transitions into the actual seeded NN rollout, rather than
back-extrapolating its future endpoint over the full Body blend. That extrapolated
pose caused the right thigh loop. Existing Body timing and NN weights remain.
No frame gates, scene changes, new controls or root-speed tuning.

Frozen current scene lands atF185.25. F194->195 right thigh135.3deg becomes3.1deg;
F185.25-220 dense240Hz recovery has max right hip2.26deg/tick and minimum forward
COM speed4.51m/s.667 current-scene/physical-seed/continuity/seek checks pass using
the captured actual NN rollout; the previous code fails the new orbit detector.
1126 earlier jump checks still pass. Collider sheets inspected throughF217.
The older body-landing suite still fails its historical F131 scene expectation;
the identical failure was reproduced with the pre-change capsule.js. The old
trim-generation suite also fails its incremental-NN-request assertion both
before and after this change; no regression fix is claimed for that test.
Evidence: Saved/BodyflipLab/LandingContinuity/. Live scene/playback not written,
no GUI takeover or Unreal changes. Refresh loads; not pushed.

## Leg continuity / Follow cam - October 29 (current jump behavior, local)

The existing viewport camera checkbox now reads **Follow cam**: checked follows
the agent; unchecked enters free camera from the current view. Rechecking centres
the agent while retaining viewing angle and distance. No duplicate camera widget.

The saved F61/F80 and second-push defects had several distinct sources:

- The root-first push compressed its requested velocity change into about8ms
  when loading left little reach. Hard ankle pinning then drove the knee nearly
  straight, and the extra two-frame follow entry overshot/rebounded.
- Per-frame shortest-arc interpolation during leg return changed branches,
  creating a123deg thigh turn atF80.
- An airborne foot marker could still inherit the preceding jump's future
  locomotion landing, unlike an owned hand marker.

Foot pushes now use a finite-speed knee-extension curve seeded with incoming
bend/velocity. The root moves along the requested change of velocity while
retaining the remaining incoming motion. Loading ends at the latest feasible
candidate; actuation ends when the requested launch speed is reached, contact
reaction becomes tensile, or existing contact geometry runs out. Actual outgoing
velocity continues into flight. The driver does not compress time to manufacture
the requested impulse, and retains the intended removal of incoming normal
velocity on skewed surfaces. Existing Load/rebound/Jump% controls remain; no new
eligibility gates or UI options. Hand pushes retain their existing driver.

Contact planning predicts the continuing inherited turn about COM for its hip,
anchor and posed collision geometry. New airborne markers own both articulation
and a position/velocity-matched root continuation; the old carrier's hypothetical
future landing cannot replace them. This is a planning prediction of inherited
rotation; the main spin solver still integrates the current pose's inertia.

Released feet now have one world-space continuation and one inertial return.
The fixed departure point and projected pose seed extension; the two-frame entry
has been removed. The return captures its rotational offset once, so it cannot
switch shortest-arc branches halfway through. Joint limits apply to the continued
reach before it seeds recovery. Leg follow remains0.20s by default and Leg still
sets the return duration. Zero follow keeps immediate animation recovery.

The carrier completes the contact side of release before constructing free-flight
ticks; the departure seed uses that actual collision result. Contact boundaries
replace the nearest regular240Hz tick, avoiding microscopic collision intervals.
Subframes retain the exact source root curve. Final foot-clearance IK now restores
the intended COM between passes instead of adding a small display-only COM shift.

Frozen current-scene results: F60/F61 support knee41.84/36.17deg (previously
41.68/2.60); F79->80 thigh9.39deg (previously122.9). Both markers push, atF56.625
andF117.75; releasesF57.487/F118.101. Requested markers stayF56/F116; push/release
timing follows the new extension.1126 checks cover both full leg chains at240Hz,
release continuity, lengths, seeking, momentum and nearly aligned collision
boundaries.300 world-follow and120 zero-follow regression checks pass;96 original
paired-bounce checks retain hand behavior.693 additional flat/inclined/wall-skew
checks cover continuous root velocity, launch budget, forward momentum and reach.
Nine hand-recovery cases and six
25/50/100%/positive/negative/zero-spin cases were also checked. Zero-spin edge
cases retain a sub-degree (~0.22deg) projected hip difference at release; there is
no visible lock/rebound in the sampled collider views. No claim of exact physical
contact-force simulation is made by this kinematic target authoring model.

Evidence and actual-collider sheets: Saved/BodyflipLab/LegContinuity/. Current
scene generation plus369 projected samples takes about3-5s on this machine;
playback samples cached motion. No live scene/settings edits, desktop operation,
Unreal launch, server restart or push. Refresh loads the changes.

## Initial world-space leg follow-through - October 29 (superseded above)

Foot pushes now retain their last world-space ankle/contact orientation after
release, like hand follow-through. **Leg follow s** is appended at the bottom of
More options, default0.20s, range0-1s. Zero restores immediate animation recovery.
The existing **Leg** slider controls return duration after this follow interval.
There is no new ground pin or push force: the hip can leave the point and the
leg cannot stretch. Whole-body rotation continues while the leg aims back toward
the fixed point, within the normal joint limits.

The shared spin-contact follow solver now supports legs as well as arms. Feet
retain the actual departure pose from the carrier; later root collisions cannot
rewrite it. Knee extension carries its release speed into a critically damped
approach to the reach limit, with response duration based on Leg follow. This
avoids an abrupt maximum-reach lock while the pelvis moves away. COM correction
remains shared; returning blends use the untouched moving animation. Hand
behavior/settings remain independent. Follow also works when spin is disabled.

Saved second jump at F120 stays aimed within about3deg through the entry and
below0.03deg after entry in whole-frame samples, then returns over the existing
Leg time. Both pushes retain timing.300 focused checks cover world aim, subframe
extension, fixed bone lengths, COM, pin release, seek stability, zero-spin use,
settings and control placement;122 zero-follow knee-release checks pass.
Evidence: Saved/BodyflipLab/FootFollow/. Live state unchanged; no desktop,
Unreal, server restart or push. Refresh loads the new control and behavior.

## Airborne foot release knee pop - October 29 (local)

The saved second jump at F116 exposed two errors. Its carrier still used the
standing capsule during SUPPORT/LOAD/PUSH, despite the bounce planner already
using posed-body collision. This lifted the airborne root15.25cm. After release,
a further collision offset was also applied to the *past* planted pose when
rebuilding the leg recovery, changing the departure knee angle. Displayed right
knee went46.8deg to6.8deg bent from F119 to F120.

Airborne foot support now uses body colliders through the carrier as well.
Recovery seeds once from the departing contact, with its actual root offset
and velocity estimated from the last two completed240Hz carrier ticks. Later
collision displacement cannot rewrite that earlier joint pose. This avoids
recursive sampling of a collision tick still being integrated. The existing
Leg blend duration, target animation, spin, contact and anatomical limits remain.
Current frozen scene now goes89.1deg to81.5deg bent at F119/F120; both pushes keep
their timing.122 focused checks cover subframe extension, fixed leg lengths,
root displacement independence and seek stability;67 early-crouch checks pass.
Evidence: Saved/BodyflipLab/Knee120/. No live-state, UI, desktop or Unreal edits;
no push. Refresh loads the fix.

## Earlier foot-jump crouch - October 29 (local)

Larger foot jumps now lower the pelvis during preparation, instead of starting
the entire crouch only after contact. For grounded jumps, the extra time over
the X tier starts before the marker: defaults give Y100ms and full200ms of
anticipation. The marker still starts foot capture. The same smooth depth curve
continues through approach/contact; elapsed preparation counts toward the chosen
buildup duration. Airborne foot jumps start lowering at their marker. Small
jumps, hand buildup, existing controls and saved tuning retain their behavior.
Preparation cannot start before scene0, the previous support releases, or the
latest landing. Zero depth disables the new preparation.

The root keeps its existing trajectory and momentum. Grounded knees bend under
the lowered pelvis while the gait feet keep their world trajectories; the upper
body keeps its source rotations. On contact, the chosen foot uses the existing
world pin and heel-to-toe roll. Reach can still end loading early. Crouch depth
stops growing on push and returns through the existing body blend after release.
A failed foot approach blends the crouched body back as well as the support leg.

Frozen current run: preparation F44, contact F56, push F60, release F60.48.
Displayed pelvis is9.65cm below the original gait at contact; authored depth
reaches12.10cm on push (formerly about1mm). Forward root speed remains5m/s.
Second marker still pushes at1.95208s.67 early-crouch checks and335 momentum/
continuing-animation checks pass, including tier controls, unchanged gait foot
paths, trim extension equivalence and sub-mm push/release boundaries. Airborne
capsule regression now explicitly lowers only the nonphysical root reference,
keeping body/contact geometry fixed; its ballistic first step and push pass.
The older aggregate jump-build test still fails its handBoth25 pin assertion
with both the pre-change source and this source; it is not a new regression.
Evidence: Saved/BodyflipLab/EarlyCrouch/. No UI changes, live state writes,
desktop control, Unreal work or push. Refresh loads the update.

## Instant spin and limb recoil - October 29 (local)

**Instant spin** is per jump, appended at the bottom of the jump marker popup
(user placement/scope correction). **Spin lag %** remains in More options.
Instant spin overrides marker Accel/Brake without overwriting them: the new
flip/twist command takes effect at actual release plus Delay. Keep still carries
the previous command; explicit zero stops it. Orientation stays continuous.
Integration splits at command boundaries, including fractional240Hz ticks, so
there is no motion before the delay expires. Inertia scaling remains active.
Instant spin persists on each marker; new markers default off. Legacy global
values migrate once onto existing markers, respecting explicit marker values;
the global key is removed. Spin lag remains per scene, default0. For the
experiment, enable Instant spin on the chosen jump and set Spin lag to60%.
Editor checks cover independent toggles, marker switching and saved roundtrips;
mixed instant/smooth command checks pass. No live-state edits.

spin-response.js adds damped limb recoil driven by changes in the spin command.
Each shoulder/hip has three rotational coordinates and its elbow/knee one hinge.
The lab's collider masses, centres and rotational inertia determine the joint
velocity impulse. Critical damping returns the offsets to the moving animation;
smooth bounded offsets and existing Jolt limits prevent overextension. No
oscillatory noise or extra COM force. The response preserves COM and bone lengths;
spin's inertia multiplier includes the resulting pose. Contact/follow-through
solves run afterward. Keep markers carry the existing response without replaying
its impulse. Zero strength bypasses the response. This is a small animation
response to a prescribed turn, not a complete muscle/free-flight dynamics model.

Reference basis: [Haering et al.,2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5396868/)
separate release momentum, changing inertia and segmental momentum transfer in
acrobatic rotation. [Willett et al.,2017](https://gfx.cs.princeton.edu/pubs/Willett_2017_SMF/index.php)
use physically inspired rigs to propagate primary motion into secondary response.
These motivate the design; the damping and response strength are artistic tuning,
not measured human constants or a reproduction of either paper's solver.

The instant turn also exposed an existing simulated-substep interpolation defect:
the nonphysical root reference changed basis at release, and interpolation of
root-local pelvis position pulled an intermediate target down26cm. Physics now
uses one root basis for both endpoints, preserving the pelvis world path and
local limb interpolation. Collision remains enabled; no solver limits relaxed.
The failing foot fixture's2.29cm anchor separation becomes0.0344cm.

Verification:3164 focused checks (timing, axes, reversal/stop, bounds, COM, inertia,
Keep and deterministic seeking);161 prior spin checks; six paired-hand/release
cases;1296 real Jolt ticks over foot, one-hand and two-hand jumps. Simulated
maximum joint separation1.09mm, maximum bone-position tracking error1.54cm.
Actual saved Run scene retains both successful pushes with the experiment on.
Inspected collider frames57-80, covering the impulse and recovery. Cached motion
sampling p95~3.3ms, excluding rendering; warm preparation~2.4s. Served browser
module/controls checks pass. No desktop control, live-state write, Unreal work
or push. Evidence: Saved/BodyflipLab/InstantSpin/. Refresh loads it.

Current LOAD observation (October29, unchanged): saved first marker F56,
Run5m/s,100% jump,300ms buildup,15% depth. Actual loading ends after29.17ms
at the reach reserve (2.5cm left for extension), while root advances14.58cm.
The300ms quintic depth curve has reached only0.097cm of its12.24cm target;
displayed pelvis drops0.105cm. This is the mismatch between available stance
time and the authored lowering clock, not the Instant spin option. A deeper
buildup needs earlier preparation/available stance travel; compressing the full
depth into29ms would introduce a snap. No loading or support tuning changed.
Frozen scene and per-tick evidence: Saved/BodyflipLab/LoadDepth/.

## Airborne foot rejump - October 29 (local)

Saved Run scene,350deg/s first flip and second foot marker atF115: contact
was valid at1.94167s, hip-foot distance73.51cm within80.75cm reach. The longer
buildup resolver still used a standing capsule for airborne foot support; with
root at-19.14cm, its first tick lifted root20.18cm and produced91.18cm reach,
rejecting the push. Airborne foot loading now resolves the posed body, excluding
the pinned foot/ball, matching hand loading. Grounded locomotion retains the
standing capsule. No reach-limit relaxation or fabricated impulse. Actual saved
replay now pushes; first jump timing unchanged. Zero push duration no longer
misreports spin release unless the spin contact planner actually released early.

verify-airborne-foot-rejump.mjs uses a committed small settings fixture and
frozen Run phase bank, checking real upward release, absence of root lift, finite
replay and unchanged first jump.335 buildup/momentum checks pass. The broader
body-landing test has an existing F136 hand assertion failure, reproduced using
the pre-fix flight.js with the same current dependencies; not introduced here.
Evidence/backups: Saved/BodyflipLab/SecondPushMiss/. No live-state edits or push.

## Independent hand return - October 29 (local)

Hand return slider is directly below Body and Leg in the left panel (user
placement correction),0-1s, default0.4s.
Hand animation entry/abort, continued-reach recovery and pose cache duration use
this clock; foot recovery retains legBlend (renamed Leg in the left panel).
Hand follow remains the delay before returning. Existing scenes lacking the new
field receive0.4s, without changing saved leg timing or writing live scene state.

## Hand return at F146 - October 29 (local)

Saved scene used Hand follow0.1s and Limb0.2s. Carrier correction blended the
already blended arm again, and final aim projection pulled it back toward the
contact during recovery. This delayed visible return into F146-150. Each
contact/COM correction now uses the untouched animation as its target; final
projection follows the blended arm direction during recovery. Full world-point
aim remains during follow. User timings, root, commands and scene state retained.
Saved F140-160 trace: shoulder peak15.98 to13.31 degrees/frame, with motion spread
earlier through the existing12-frame return. Limb remains the return duration;
Hand follow delays its start. Evidence: Saved/BodyflipLab/HandReturn146/.

## Separate hand cone angle - October 29 (local)

Hand cone degrees is appended at the bottom of More options, range0-85.
The existing Cone degrees now applies to feet only. Hand surface ranking and
approach planning both use handCone. Existing scenes inherit their previous
shared angle once; saved hand/foot angles then remain independent. Direct
15/60 and60/15 degree candidate checks, migration, bounds and syntax pass.
The 45-degree ramps toggle includes/excludes the original left/right platforms
from scene geometry and collision; their saved transforms remain. No state edits.

## Hand cone debug - October 29 (local)

Hand cones appended to the viewport toggles; existing Cone remains for foot
support. Shows both prepared hand query cones, retained after capture so the
actual decision can be inspected. Hand target circles are the pre-cone ideals;
yellow crosses now mark the chosen surface contacts, connected to their ideals.
Released hands are red even if originally planned as a pair. Saved F132 verifies
left contact about22cm from its ideal; right was released at the marker by the
spin/contact compatibility check. This is a debug-only change, not a contact
solver change. Both cones/contacts, active/released labels, preference and syntax
checked. Evidence: Saved/BodyflipLab/HandCones/.

## Support target visibility - October 29 (local)

Foot targets and Hand targets are appended to the right of the viewport
toggles. Both default on, preserving the previous display; each independently
controls the active support type's ideal circles and contact guide. The circles
were already shared by foot and hand support, not permanently foot markers.
Paired hand plans now mark both selected hand candidates green. Preferences
use normal scene saving; toggling redraws without regenerating motion. Syntax,
default/persistence, placement and rendering-gate checks pass. No live state edits.

## Hand follow-through and playback cost - October 29 (local, unpushed)

Hand follow s is appended at the bottom of More options (default 0.25 s).
A hand that actually pushed keeps reaching toward its captured world-space
release point, then returns over Limb seconds. The aim is recomputed from the
moving shoulder; it is not a frozen spine-relative rotation. The common target
projector reapplies that world aim after anatomical projection, within the same
Jolt shoulder limits. Wrist limits, COM trajectory and support release times
remain; a hand released before the push does not gain a new contact. A two-frame
velocity-preserving entry prevents a release seam. The body continues its motion.

Playback reuses prepared source/contact poses for foot as well as hand segments.
Timestamp keys merge numerical clock drift; caches stay bounded and trim-limited
generation remains. Kinematic playback samples at 60 Hz; simulated mode retains
240 Hz. Saved-scene offline motion cost fell from 25.9 ms p95 to 1.92 ms p95
per displayed frame (rendering excluded). Preparation measured 2.32 s in the
final saved-scene replay. These are workload timings, not measured browser FPS.

Left/right frame stepping and Step wrap between the trim brackets, including
when Loop is off. Text editing retains its arrow keys. Seven boundary/pending
preview cases pass; six rotating/paired/single-release contact cases pass,
maximum release seam 0.077 mm. Browser-global load and served-file checks pass;
the user resumed editing during verification, so the older frozen state is no
longer expected to match live state. No live-state write, desktop control, Unreal
change or push. Evidence: Saved/BodyflipLab/HandFollowThrough/.

## Continuous COM spin and simulated playback - October 29 (local, unpushed)

Flip and twist now command **degrees/second**, rather than a finite angle. A
marker's blank value (**Keep**) inherits the preceding command and its unfinished
ramp; explicit **0** brakes to rest. Delay starts after that marker's physical
release (at the marker in Space gym / a 0% action). Accel and Brake in More
options control rate changes. There is no automatic rotation deadline in flight.
Foot/hand support retains the incoming orientation and rate command. A genuine
landing hands control to the seeded locomotion recovery. Global Air flip also
works when walking off the edge without a marker.

`mass.js` shares the actual lab Jolt masses, shape centres and inertia with the
planner: 25 bodies, 45 kg, including the five torso boxes. Rotations preserve
this weighted COM while leaving the root reference separate. **Inertia %**, at
the bottom of More options, defaults to100: each commanded axis is multiplied
by `I_reference / I_current`. At0 it is a plain angular-velocity command; between
these values the multiplier interpolates. A tested tucked pose spins1.60x faster.
This is an axis-based authored speed multiplier, not a claim of a fully passive
Euler rigid-body simulation. Existing attack compensation tuning is retained.

Legacy nonzero angle totals migrate in memory to their former mean speed
(angle / old duration); legacy zero means Keep. Version2 stores explicit rates.
The duration/absolute-angle widgets are hidden; controls retain their locations.
Saved scene files were not edited. Refresh loads the implementation and preserves
normal app save/playback behavior.

Under a continuing turn, paired hand support checks reach and shoulder/elbow
limits. It releases the conflicting hand with the existing Limb blend; if both
contacts are lost, it ends the drive and falls instead of inventing a push. The
release blend uses the actual collision-corrected pose. Contact fitting preserves
COM, and hand approach/release still carries incoming momentum and gravity.
Zero-strength markers now use body collision too. Their collision clearance can
move the body slightly without applying any launch impulse.

Kinematic and simulated playback now use one legal joint target. Knees/elbows
use the same hinge frames as Jolt; other joints use its swing/twist limits. The
conversion retains authored socket twist near straight limbs and limits local
joint changes to30rad/s, preventing a joint-limit branch change from teleporting
the sweep-kick leg. Ground clearance includes both physical shapes and visible
shoe/body geometry. The preexisting non-spine Jolt capsules have not been
replaced with display boxes; this does not claim a new PHAT/Unreal asset match.

Sim remains25 actual dynamic Jolt bodies with only pelvis absolute positioning.
Parent/child attachment velocities are now compatible with the angular servo,
instead of making constraints fight the commanded turn. Fast turns subdivide
only when needed (over0.06rad in a240Hz step); ordinary motion retains its normal
cost. Landing recovery uses the existing Body blend to meet the seeded NN with
continuous pose/velocity, avoiding the first unstable inverted-pose predictions.

Verification: all12 axes/signs, mixed twist, delayed/inherited/zero commands,
reverse seeks, trim extension, four poses,17 attacks, paired contact retention,
one-hand release, loss of both hands, slopes and a wall. Real Jolt sweep:
33 cases /12,490 steps, plus updated nine contact cases /3,024 steps. The largest
attack/contact deviation is8.2cm transient during self contact; it is not a
constraint explosion.3600deg/s plus twist stays within1.3cm of the target. In the
unchanged saved scene through3.4s, final maximum target error is1.53cm at foot
release, pelvis5.3mm, joint attachment7.8mm; the former baseline exceeded1m.
Visible target volumes stay above the floor.310 hand-COM checks retain ballistic
motion; released support is still not counted as a fresh landing.

Full collider frame sheets reviewed for the saved motion in both modes, paired
release/failure and the sweep kick. Evidence, source backups, exact NN replay,
regression logs and the completed plan are in `Saved/BodyflipLab/AngularMotion/`
and `ANGULAR_MOTION_PLAN.md`. Offline saved-motion audit took7.3s total, including
2.1s for3.4s of Jolt playback. Worst-case32 overlapping actions took5.5s isolated
and10.8s after the full attack corpus; it remains a costly stress case, not a
per-frame workload. All work was single-thread/bounded, without desktop control,
Unreal edits, live-scene writes, a service restart or a push. The older finite-angle
scene timings below are historical and are superseded by this section.


## Full hand-push and landing replay - October 29 (local, unpushed)

The previous contact-only correction was incomplete. Replaying the entire
current F128 hand-push sequence through the actual landing NN showed loading
used nearly all available arm compression. The drive then hit its travel limit
after only 3.26 ms, releasing with COM vertical velocity -2.22 m/s. A real elbow
contact at F139.75 started locomotion; the NN rapidly raised the body afterwards.

For a longer authored buildup whose drive is cut short while still moving into
the surface, `bounce.js` now tries at most eight earlier loading endpoints.
It retains the longest complete feasible drive, keeping the latest buildup on
ties. Each candidate uses only compression/energy accumulated by that endpoint.
The root keeps its incoming momentum and gravity during loading; limb lengths,
contact rules and successful existing drives are unchanged. This is shared by
foot and hand pushes, not a special timing gate for this scene.

Unchanged current scene: contact F134, loading 4.17 ms, complete drive 33.75 ms,
release 2.27125 s with COM vertical velocity +2.36 m/s. It remains airborne
through the saved 2.55 s trim. Extending offline to 3.4 s shows real pelvis
landing at F172 (2.86667 s), followed by the seeded walking NN. During this
recovery the NN could place a knee about 9.5 cm through the floor despite its
supported root capsule. `capsule.js` now resolves the posed body against the
platform during that recovery, preserving the root reference, joint rotations
and limb lengths. The exact initial landing pose remains continuous.

Validation includes actual NN continuation (17 output frames) and offline
rendering using the lab's collider geometry through F204. The saved state,
camera, markers and settings were not modified. Numeric suites pass: 106 body
landing checks; 127 travel checks across 36 single/paired, impact/launch/slope
cases; 96 paired/legacy checks (legacy outputs identical); 335 buildup momentum;
310 hand COM; 9 recovery; 30 trim; 18 release-contact, plus strength-tier cases.
Dense current push sampling has sub-nanometre pin/reach error and no penetration.
Extending the trim retains the already-generated prefix. One bounded, existing
single-thread CPU NN worker was used; no desktop control or Unreal work.

Evidence/backups: `Saved/BodyflipLab/FullHandMotion/`, including before/after
whole-motion collider renders and `after-full.json`. No restart or push.
Refresh loads these scripts. This supersedes the F136/F139.75 outcome reported
below; the released-support contact identity rule itself remains in place.

## Released support contact is not a new landing - October 29 (local, unpushed)

Follow-up saved setup moved the hand marker to F128 (2.13333 s). The right-hand
fallback releases at2.25534 s, but its continuing palm contact was counted as a
new landing at2.25833 s, about3 ms later. That incorrectly showed WALK atF136.

The carrier now remembers the contacting body-part/surface pair when that part
leaves the support solver. Its continuing contact still resolves collision and
normal velocity, but cannot itself start locomotion. Once the shape separates
beyond the existing collision tolerance (4 micrometres), a subsequent contact
can land normally. Other body parts and other surfaces remain eligible. This
has no timer and does not change push/plant/release timing. The same rule covers
hands and feet. Extra contact queries run at release and while contact persists,
not throughout support preparation.

Read-only replay of the unchanged current scene: F136 now remains FALL, with
1.75 cm minimum body clearance. Later actual upper-arm contact lands at2.32917 s.
18 release-contact tests cover both hands/a foot, collision retention, lift and
recontact, other-body landing and reverse seeking. The expanded body-landing
suite passes100 checks;310 COM,9 recovery and30 trim-generation checks also pass.
No live NN/desktop/Unreal work, saved-state edit, restart or push. Refresh loads.
Evidence and source backups: `Saved/BodyflipLab/HandLanding/`.

## Airborne body contact and landing - October 29 (local, unpushed)

The standing capsule previously touched down while a folded/rotated body was
still well above the platform. Jump flight and hand support now query the posed
body volumes in `body-contact.js`: renderer-matched pelvis/spine/hand/foot boxes
and limb/head capsules. The five spine boxes share the physical torso definitions.
This is the kinematic lab's swept collision geometry, not a new Unreal mover or
an assertion that all legacy Jolt limb shapes match these display dimensions.
Finite platforms, slopes, sides and thin-platform sweeps use the same shapes.
Locomotion retains the 30 cm / 86 cm standing capsule.

Descending contact with an upward supporting surface starts locomotion. Wall
contacts remove inward velocity without counting as a landing. The intended
supporting hand(s), or planted feet during their contact phase, retain their
existing support solver rather than triggering an ordinary landing themselves.
Other body parts can land and interrupt a pending push. Hand COM fitting and
loading also use posed geometry, so an invisible standing capsule cannot hold
them up before body contact. Existing foot buildup remains unchanged.

At landing, restoring the standing root reference does not move the visible
body. Both current and previous NN seed poses retain their world coordinates;
only the root reference/history is rebased. Interpolation approaches the contact
root, not the restored standing root. Hand takeover also stops inheriting the
previous jump's hypothetical future landing, which otherwise caused a 6.5 mm
right-foot discontinuity. Pending pushes interrupted by body contact report Miss
with the contacting body part and do not draw a push arrow.

Read-only saved-scene replay: at F131, body clearance is 57.55 cm and the body
remains airborne. The unchanged F136 hand marker starts before landing, but the
right upper arm contacts the floor at 2.29583 s before the palms finish planting.
That is the new real landing, not an early capsule landing. An offline variant
with the marker at 1.95 s completes a paired-hand release at 2.23926 s. User
markers, playback, scene files and tuning were not written.

Validation: 95 geometry/sweep/landing checks, including renderer parity, rotated
saved-scene handoff, slopes, side contact, finite gaps, thin platforms and reverse
seeking. The saved-scene join has 1.24 micrometre maximum joint displacement over
0.1 microseconds; its deterministic policy stand-in receives the exact visible
contact pose. Also pass: 310 hand COM checks, nine independent Body/Limb recovery
cases, 335 buildup momentum checks, six tier/contact cases and 30 trim-generation
checks. Hand regression fixtures now explicitly use L for the first support and
a feasible 1.95 s hand marker, avoiding dependency on changing Auto scores or the
removed invisible capsule support; COM/recovery assertions remain intact.
No live NN inference or visual desktop QA this turn. Existing service serves the
new scripts; Refresh loads them. Evidence/backups: `Saved/BodyflipLab/PoseLanding/`.
No Unreal work, service restart or push.

## Supporting-foot composite score - October 29 (local, unpushed)

Auto foot selection still runs after each foot's cone/finite-surface query.
It now compares actual lowest-shoe-point travel to that contact, minus a bounded
preference for being ahead of the pelvis in the surface-tangent travel direction.
Previously it ranked ankle travel into the final Plant orientation, even though
capture can use the current shoe orientation. In the reported saved pose both
soles are about 1.8 mm from the floor, but that old metric said 20.8/12.6 cm.

Score units are metres: contactDistance - forwardBonus. Each 10 cm of lead is
worth 2.5 cm of contact travel, bounded to half a limb's reach on either side.
The preference is multiplied by speed^2/(speed^2 + 0.25^2), using tangent speed
in m/s. It vanishes for rest/normal-only motion; a raised leading foot can lose
to a ready rear foot. Scores within 1 mm tie deterministically L-first. Selection
has no playback history. Manual L/R, existing eligibility, penetration handling,
cone geometry, target carry, approach speed and hand selection are unchanged.
The phase tooltip now shows actual contact distance and composite score; no
controls were added or moved. Existing distance remains ankle travel for the
planner; diagnostics also expose contactDistance, forwardLead, forwardBonus, cost.

`verify-support-score.mjs` passes 338 offline checks: reversed/sideways motion,
rest/noise, height sweeps, rotated slopes/walls/ceiling, platform edges, manual
choices, far surfaces, the earlier inclined-cone fixture, and 96 real walk/run
poses (24 grounded front/rear comparisons). Momentum335 and the tier/contact/
trim suite also pass. Dense replay of the saved scene selects L, loads 210.4 ms
instead of R's 22.9 ms, and keeps 2.00002 m/s tangent speed with sub-nanometre
pin error and no reach excess. Push/release joins are continuous; initial capture
has the existing ~5 mm maximum joint adjustment from resolving sole contact.
The later hand event still pushes, now with the existing R-hand fallback because
its arrival pose changed. Marker times and user state were not edited.
Evidence: `Saved/BodyflipLab/SupportScore/`. No desktop control, live NN,
Unreal/service restart or push. Refresh loads the correction.

## Jump strength buildup - October 29 (local, unpushed)

Jump % selects three loading tiers for foot, single-hand and two-hand pushes:
through X (default 35%) uses the existing Load ms response unchanged; above X
through Y (70%) uses Y ms (200 ms); above Y uses 100% ms (300 ms), including
strengths above 100%. X is kept below Y. Medium/full times cannot be shorter
than the preceding tier. Old scenes with a tuned Load value initialize the new
times at twice/three times that value, capped at 1500 ms. Settings live at the
bottom of More options: X %, Y %, Y ms, 100% ms and Bend %. Existing controls
stay in place. Setting all times equal restores the original loading path.

Corrected after the user's momentum report: longer buildup authors pelvis
translation toward the surface, not a spring pulling the root toward the plant.
Bend % (15% default, 0-25%) is lowering relative to limb reach. Root velocity
continues with gravity; only actual capsule collision removes inward normal
velocity. No reach correction brakes or pulls the root backwards during loading.
The captured pelvis height lowers smoothly while the supporting limb bends
against its contact. All other local joint rotations keep following the current
NN or already-running jump animation at its continuing clock. The rejected
free-leg clearance IK and separate crouching-root carrier were removed.

Available reach/compression can end loading before the requested tier time;
we do not slow the character to keep a trailing limb planted. The existing push
duration and Jump % strength rules remain. The lowered pelvis returns using
Body blending after release. Hand wrist fitting uses the lowered body for both
palms, with cached targets invalidated when the loading depth is committed.
Hand COM correction remains. Space gym/0% actions stay contact-free.

`verify-build-momentum.mjs` passes 335 checks: ballistic airborne root motion,
grounded tangent momentum and real frozen NN/fall-animation sources. Their
pelvis drops are about 12 cm; unaffected local rotations agree with the advancing
source within 8e-16 radians. `verify-jump-build.mjs` checks thresholds/settings,
six foot/two-hand tiers, contact/reach, hand COM, release continuity, finite
floor/slope/wall constraints, deterministic seeking, save/reload, trim extension
and appended UI fields. The 96 legacy bounce checks, 310 COM checks, nine
arm-recovery cases and 12 wrist cases also pass. Historical fixtures use equal
tier times to retain their previous timing.

Before the composite foot selection above, offline replay kept the first root at 2.00002 m/s
through loading and the push. Its trailing foot reaches the extension margin
at 22.9 ms rather than holding the requested 300 ms by braking. The later paired
hand push completes its 200 ms buildup and retains its incoming tangent speed.
The composite-selection section above records the newer arrival pose and hand fallback.
Evidence and rejected-implementation backup: `Saved/BodyflipLab/BuildMomentum/`;
initial tier-work backups: `Saved/BodyflipLab/JumpBuild/`. No desktop control, live NN, Unreal,
live state write, service restart or push. Refresh loads the correction.

## Hand recovery clocks - October 29 (local, unpushed)

Fixed the saved scene's F142 arm snap with Body 0.4 s / Limb 0.2 s.
At release + 0.2 s (F141.225), the arm override ended and exposed the arm
rotations still recovering inside the 0.4 s body blend. The hands jumped
45-51 cm at that boundary. Hand recovery now excludes the supporting clavicle,
upper arm, forearm and hand from the Body blend; those joints use only their
Limb recovery and then follow the target animation. The torso and free arm
retain Body timing. Both blends still start from the displayed release pose.
Foot-jump blending, contact timing, wrist limits and COM correction are unchanged.

`node Labs/BodyflipLab/verify-hand-recovery.mjs` checks nine saved-scene variants:
Body shorter/longer/equal to Limb, either duration zero, and single/both hands.
It checks joint continuity at nonzero blend endpoints and repeat/seek consistency.
The saved scene's former discontinuity is below 1 micrometre across the sampled
boundary. Existing 310 COM checks and 12 wrist cases also pass. Before/after
F139-144 traces: `Saved/BodyflipLab/HandPerformance/frame142-*.json`.
Saved tuning/playhead and UI remain untouched; Refresh loads the fix.

## Hand playback performance - October 29 (local, unpushed)

The saved Both hands scene exposed repeated contact/COM solves during playback.
Each displayed frame requests four 240 Hz samples; the raw pose override and
capsule source could evaluate the same hand motion three times per tick. Tiny
differences between accumulated playback time and the fixed capsule grid also
missed the source cache. Its 128 entries did not retain the hand interval across
loops. Slow frames could then request three catch-up steps before rendering.

Hand segments now share their solved raw poses across capsule integration,
playback, preceding-segment articulation and debug reads. Only timestamps within
1e-10 seconds of a 240 Hz tick are canonicalized; arbitrary subframe queries and
different flip/twist/axis values remain separate. The expensive approach/push/
blend interval is retained across loops, capped at 2400 poses per segment;
free-fall/scrub and angle-override caches each retain at most 256 entries.
Caches belong to one generated sequence, so settings edits rebuild them.
Preparation still ends at the trim bracket and extends the existing prefix.

The hand capsule also reuses its contact-corrected pose for the same source
frame and exact resolved root. It still performs the original solve on the first
query, including zero-offset cases. Public pose arrays are copied so a caller
cannot modify a stored result. Landing/velocity metadata remains fresh; foot,
locomotion, wrist limits, COM fitting and the 240 Hz simulation rate are unchanged.

The same cached scene's four ticks plus enabled debug reads averaged about
18.9 ms per displayed hand-approach frame before the fix, 0.56 ms afterwards.
Playback no longer performs the COM fitting iterations already done during
preparation. These are offline motion costs, excluding Jolt and rendering;
no claim of measured browser FPS. Evidence and the pre-change source snapshot:
`Saved/BodyflipLab/HandPerformance/`. The strict before/after audit passes
32 checks and 818 frame comparisons, including altered settings/angles, off-grid
seeks, caller mutation and trim extension. Maximum numerical difference is
1.57e-10 (4.27e-13 in the saved scene). Existing 310 COM checks, 9 paired-hand
cases, 12 wrist cases and 30 trim checks pass; 13 focused capsule-cache checks
also pass. No UI/state edits, live NN, Unreal or service
restart. Refresh loads the changes.

## Two-hand push and hand COM - October 28 (local, unpushed)

The existing marker's **Push with** selector now ends with **Both hands**.
It tries two contacts on the selected platform, with one shared torso fold and
one push. The first palm stays planted while the second approaches. Both actual
arm reaches, legal wrist rotations, finite contact bounds and the root capsule
must remain compatible. Otherwise the request falls back to ordinary Hand
(auto); the status reports the hand actually used. No controls were moved or
new timing sliders added. Existing scenes retain their selected support mode.

The shared drive uses the mean shoulder and wrist positions, with separate
reach constraints for both arms. It does not double Jump %. The first arm to
exhaust its usable travel ends the common push. Loading resolves both reach
constraints with the capsule, including tangent corrections when the floor
blocks a radial correction. Velocity constraints are solved together so two
parallel arms cannot remove the same velocity twice. The debug push arrow starts
between the two contacts. Body and Limb recovery still use their existing times.

Palm aiming also accounts for the displayed forearm's rounded wrist end. When
flattening the hand would put that capsule through the platform, backward wrist
pitch stops earlier. Twist, sideways deviation and the Jolt bounds are unchanged;
the palm remains inclined with actual surface contact.

The COM audit reproduced the saved 90-degree flip followed by the 50% left-hand
push, using the physical rig's 45 kg mass distribution and collider centres.
Previously, unfolding after release added about 2.17 m/s upward COM velocity;
by 2.547 s the COM was 28.6 cm above the gravity-only prediction. The airborne
reach also introduced up to 11.28 m/s² of extra COM acceleration. These were
articulation moving mass around a ballistic root.

Airborne hand preparation now fits root translation and wrist targets together
against the incoming COM trajectory. It carries the solved root between planner
ticks and preserves the existing reach pacing, cone and retreat checks. Both
approaching hands are fitted together. Real capsule support or the first palm
contact permits external forces; a standing floor-to-wall reach is not treated
as free fall. The floor state comes from the actual carrier/capsule, not from the
normal of the platform being reached for.

After release, COM position and velocity are taken from the actual pinned pose.
The completed body/limb/flip/attack pose and its root are translated together so
internal animation cannot move the COM away from its ballistic path. The capsule
receives that same corrected root. Its source curve is retained between collision
ticks to avoid a pin-release interpolation hitch. Hand RISE/FALL timing uses COM
vertical velocity; paused/reloaded flight readouts use COM velocity too. The
existing fall cap remains, without an impulse if inherited release speed already
exceeds it. Contact loading remains the lab's authored spring/push model.

Validation: 310 inertia checks, 57 saved-scene regressions, 12 strict wrist cases,
96 paired-drive checks, 9 paired-contact cases, 62 UI/persistence checks and
30 trim-generation checks. Free approach
COM error is below 2 nm for the saved single and paired setups; post-release error
is below 4e-15 m. Exact single-support bounce traces and the preceding foot-jump
prefix remain unchanged. A cached current-scene preparation measured about
0.5 s, with 60 support samples taking about 0.11 s total on this laptop. These are
bounded offline measurements, not a general frame-rate guarantee.

The audit separately found existing COM drift during the preceding foot flip;
this hand change preserves the accepted foot path. Its true incoming COM velocity
is retained at the hand marker. Actual capsule-floor collision before palm contact
also changes momentum and is retained. No claim of a full rigid-body force or
angular-momentum solve is made for this kinematic lab.

Offline actual-collider sheets: `Saved/BodyflipLab/HandReview/both-*.png`.
No saved scene edits, desktop/browser control, Unreal/NN launch, service restart
or push. Refresh loads the changes.

## Trim-limited preparation - October 28 (local, unpushed)

Edits prepare playback only through the end bracket. Later markers wait until
that part of the timeline is exposed. Dragging the bracket outward or explicitly
seeking farther calls `flight.extend(end)` and retains the existing sequence,
segments, capsule history and Foot IK caches. It does not shorten the timeline.
Releasing a bracket still restores the original playhead. A subsequent settings
edit clamps a playhead outside the new generated range to the end bracket.

Landing NN requests cover only the required output, with at most one 30 Hz
interpolation frame. Extension resumes the exact recurrent lower/upper/pelvis
state and origin instead of re-encoding an already decoded pose. Root-command
lookahead (eight policy frames), the small precomputed gait source, and source
curves needed to plan a visible action are still available; they are not extra
generated playback. Zero-percent actions pass preparation and root-state queries
to their underlying carrier. Previously prepared poses remain readable while an
extension is pending. Refresh cancels obsolete client preparation after capturing
its playback snapshot. An already submitted inference request finishes normally
and its obsolete client result is discarded.

`verify-trim-generation.mjs`: 30 offline checks, including incremental/full
equivalence, unchanged prefix, deferred markers, landing continuation, rapid
bracket release, overlapping seeks/edits, cancelled stale seeks/bracket previews,
and zero-percent-action handovers.
The policy is mocked in this test; Python state shape/finite checks and syntax
were checked without loading the trained network or restarting the service.

## Wrist contact limits - October 28 (local, unpushed)

Hand support now authors a forearm-relative wrist bend. It no longer points the
palm at the surface with an unconstrained world rotation. `wrist.js` shares the
unchanged Jolt wrist limits with `physics.mjs`: normal swing 45 degrees, plane
swing 40 degrees, axial twist plus/minus 55 degrees. The reference is the shared
rig pose, not the pose at the jump marker. This matters in Kinematic mode, where
Jolt itself does not enforce constraints on the displayed pose.

The palm attempt changes only backward flexion/extension. Existing allowed
axial twist and sideways deviation are retained; the support target adds neither.
A fully flat palm is not forced when the allowed pitch cannot reach it. The hand
stays inclined. The quaternion swing ellipse and rest frames match the shipped
Jolt implementation, including the mirrored hand convention. Illegal input is
projected into the existing bounds; no joint limit was widened.

Approach reconstructs the wrist from the actually solved forearm at subframes.
Capture couples arm IK, allowed pitch and the real rendered hand-box offset.
During contact the same solve receives the bounce/capsule root, so final capsule
interpolation cannot reintroduce hand twist or move the wrist off its contact.
The captured material pivot is retained tangentially and lifted when a different
box corner becomes lower. This is continuous contact, not a no-slip rolling model.
The retreat check uses one wrist-clearance offset for both compared frames while
retaining their actual cone/finite-edge contacts: rotating the hand alone cannot
cause a false miss, and moving past the platform can still fail.

`verify-wrist.mjs` has 3,408 checks, including comparison with the actual Jolt WASM
constraint clamp (maximum angular difference below 5e-7 rad). Twelve strict
integration cases sample ordinary and half-ticks of the saved inverted push,
both hands from Idle/Walk/Run, slopes, walls and a missed finite edge. No added
wrist twist exceeds 4.2e-7 rad; pin error stays below 1.8e-15 m and the wall capture
seams below 2.6 micrometres. Grounded geometry and the 57-check exact-scene regression
also pass. These are bounded fixtures; they do not assert that every contact is
reachable under the newly enforced wrist limits. The updated legacy hand suite
passes 405 checks across 6,193 samples, including zero-load contact and 18 unchanged
foot-path comparisons (maximum error1.57e-16). Its slope fixtures now start outside
the surface; unreachable rotated-floor cases verify legal wrists and no active
impulse instead of requiring the old unrestricted palm to succeed.
Actual-collider sheets: `Saved/BodyflipLab/HandReview/wrist-*.png`.
No controls moved, saved scenes edited, browser/desktop control or service restart.
Refresh loads the change.

## Hand jumps - October 28 (local, unpushed)

The existing marker popup ends with **Push with**: Foot (default), Hand (auto),
Left hand, Right hand or Both hands. **Hand bend s**, default 0.35, remains last in More
options. `Limb s` controls support-limb recovery; `Speed cm/s` retains the stored
`supportSpeed` value. Reach, Gate, Speed, Lead, Cone, Load, Rebound, Up skew and
Jump % also apply to hands. Foot heel/toe roll and Match foot stay foot-specific.
Old scenes still use feet. No controls have moved in this correction.

The hand adapter reuses finite-platform cone selection, root-local ideals,
reach-aware travel, proximity capture and distance-growing misses. It preserves
world bone transforms while separating the carrier root frame from an earlier
body flip. Torso bending uses the actual incoming orientation; an inverted
handstand remains inverted. Once the hand marker takes over, its articulation
comes from the previous raw motion, not that previous jump's hypothetical future
landing and locomotion NN. The displayed pose and velocity seed the handover.

Loading and push planning now include the root capsule. The wrist pin, shoulder
reach calculation, rendered body and release blend use the same constrained
trajectory. Capsule and taut-arm constraints are resolved together; a ground
correction cannot silently put the arm out of reach. Shoulder surface clearance
is measured from the actual plane, independently of the rolling wrist offset.
A contact with no usable extension releases without an active jump impulse.

Grounded preparation uses a forward hip hinge with the hips moving back and
feet trailing them. It blends captured joint rotations into one prepared stance;
recomputing that stance from each gait frame had caused a sudden thigh twist.
The supporting elbow turns outward around the shoulder-to-wrist axis, keeping
the wrist pinned and the forearm clear of the knee. Incoming joint velocity is
carried into the fold instead of being discarded on the first frame.

After release, Body and Limb independently recover the procedural torso and arm
changes. Airborne launches continue their incoming articulation. Grounded launches
enter the existing fall loop, aligned to the incoming pelvis, instead of walking
in midair. The ordinary foot-jump animation is no longer substituted beneath an
inverted pelvis. Elbow recovery uses the
same bounded hinge-momentum treatment as knees, enabled only for this hand path.
The wrist-limited contact above supersedes the earlier forced palm flattening
and fixed heel-lift target. Free-hand surface correction does not switch off at a
blend deadline while the hand is still below the plane.

The original 423 checks did not exercise the user's two-marker setup (180-degree
foot flip followed by a left-hand push) or the full capsule correction at release.
That setup exposed a 5.75 cm wrist teleport and a thigh passing through the torso.
`verify-hand-current.mjs` now reads the committed phase bank and recreates that
scene without live inference. It checks full-sequence pinning, release continuity,
actual torso/limb geometry, return to incoming articulation, both hands and turns,
ordinary walking, deterministic seeking, and absence of obsolete NN requests.
The saved case has pin error below 4e-15 m and positive torso/limb terrain clearance
through the inspected interval. Its preceding foot motion remains unchanged.

Final offline verification: 57 exact-scene checks; 423 isolated hand/foot checks
covering 6,350 poses; 30 trim checks; and 56 marker checks. The six Idle/Walk/Run
left/right cases in `verify-hand-grounded.mjs` sample at 240 Hz, including release
into the fall loop. Wrist pin error stays below 8e-16 m; worst joint-position
seam is 0.83 mm. There is no gross torso/leg/arm intersection: the measured shell
overlaps and plane discrepancy stay below 1 mm. Maximum hip-relative knee speed
is 5.50 m/s. These are bounded fixture results, not universal self-collision.
Actual-collider Walk/Run sheets were inspected after the final recovery change.
The saved 2.55-second scene prepares in about 0.7 s using decoded cached gait data,
with no obsolete landing-NN call; this is an offline preparation measurement,
not a browser load-time measurement.

`verify-hand-jump.mjs` covers isolated floor/slopes/wall contacts, timing and speed
options, misses, cached gaits, mixed markers and numerical comparison with the
retained pre-hand foot implementation. Running contacts with no extension room
now verify a clean miss rather than requiring the old below-floor success.
`verify-jump-track.mjs` covers marker controls and persistence. Actual-collider
sheets and diagnostics are in `Saved/BodyflipLab/HandReview/`; older HandJump
previews are historical, not verification of this correction.

The lab still authors kinematic support motion with the root capsule; it is not
an articulated torque controller or a finger-grip/self-collision simulator.
It uses existing platform top faces (rotate one to provide a wall).
No live scene writes, desktop/browser control, Unreal build or service restart.
Refresh the existing lab to load the changes. No push was requested this turn.

## Sweep kick - October 28 (local, unpushed)

`Sweep kick` (`sweepKick`) is appended to the main Attack selector, marker attack
selector and kick comparison viewer. Source is the user's
`C:/Users/singerie/Documents/Cursor/stepper/ue5/slashes/recoveries/sweepKick.fbx`:
36 original frames (0-35),30 Hz, Armed8 and Hit17. It strikes with the right foot
and uses the shared full-body kick path and native post-Armed motion.
It is circular: aim finishes at **Hit**, unlike Kick L/R at Armed.

`export_sweepkick.py` reads the FBX without modifying it, normalizes through the
existing FBX converter and writes one44,928-byte clip plus manifest entries.
The main selector has one authored variant. All16 original dataset families and
binary clips remain unchanged. The general vanilla exporter retains supplements.
No target annotation exists in this FBX; the ideal hit point is derived from the
existing foot contact offset on foot_r at frame17, with that provenance in metadata.

Direct to Armed exposed a backward-knee overshoot during entry. The shared kick
entry uses a bounded scalar hinge coordinate for entry curves that leave the
0-to-180-degree interval, preserving endpoint velocity/acceleration. Valid old
entries and every recorded key after Armed remain unchanged; no sweep-specific
blend branch or new setting.232 original Kick L/R entry samples match the previous
implementation below1.3e-16.2,118 direct/2,316 normal kick-integration samples pass,
including viewer/manual/timeline parity, moving baseline, COM, sockets and knees.
All17 attack-entry checks pass (2,700 samples). Circular Hit deadline and source
FBX hash verified. No UI control, saved-state writes, Unreal/NN/server restart.
Refresh loads the new attack.

### Full-turn correction - October 28

The first import was broken despite passing app/viewer parity checks: both paths
shared the same error. The zero-spin balance solver opposed the authored body
turn, then the absolute pelvis return from Hit erased the rest of that turn.
This left the pelvis facing one way while the legs and torso continued another.

All full-body kicks now separate the recorded, continuously unwrapped pelvis
heading from articulation. Balance runs in that turning frame; the complete
heading trajectory is restored afterwards about COM. The root remains the
locomotion anchor throughout, including the main app's local-pose composition.
The recovery now removes only **added balance rotations**, preserving the
ongoing source pelvis tilt and all authored follow-through. It starts at Hit
and finishes at max(native End, Hit + existing Out), inside the original end
time. Short clips therefore retain a smooth correction interval. No duration
was added, no sweep-name exception or new UI option was introduced, and the
upper-body attack compensation path is unchanged.

This is a kinematic, motion-preserving turn: the authored heading is prescribed.
The balance solve is relative to it, not a claim of zero total world angular
momentum during a 360-degree attack. Its correction is deliberately released
during recovery. Source turn/strike fidelity takes priority over forcing an
authored spinning action into a zero-spin initial condition.

`verify-body-turn.mjs` checks 1,858 samples across all three kicks/both entry
modes. Sweep pelvis finishes at -359.25 degrees (direct mode), matching its
source. Every striking-leg orientation and hip-relative segment position is
preserved through native End (<2.1e-15 error), with fixed COM, root axes,
deterministic seeks, exact final pose and continuous entry/Hit/recovery velocity
(join discrepancy <0.0044 rad/s at a 1-microsecond finite difference).
Existing integration:2,118 direct/2,316 normal samples; all-attack entry:2,700;
aiming:9,500 samples/all17 attacks and34 Undo rotation cases, all pass.

Offline review used the actual `renderer.js` collider mesh builder, with50 sweep
frames including the recovery, recorded/before/after/aimed comparisons, and both
existing kicks. The distorted backward-folding recovery is gone. Artifacts:
`Saved/BodyflipLab/SweepTurn/comparison.png`, `frames-2.png`, `frames-3.png` and
`sweep-comparison.gif` (half-speed). `audit-sweep-turn.mjs` uses the before-source
snapshots retained in that folder; `render-sweep-audit.py` produces the sheets.
No browser/desktop control, saved-scene writes, Unreal/NN/server restart or push.
Refresh in the existing app/viewer loads the shared fix; live feel awaits user review.

## Static target aiming - October 27 (local, unpushed)

Aim now adds **yaw only to the pelvis**, preserving its existing world-up tilt.
The remaining bend is distributed in equal increments along the five spine
joints for hand, sword and head contacts. Foot contacts use their hip because
spine articulation cannot move the foot. Other local joint rotations (including
elbows and knees), bone sockets and the root trajectory are preserved. A common
translation maintains physical COM after articulation. Authored motion and
attack compensation remain active; their existing pelvis tilt is not removed.

Original `attack_target_world_m` metadata is attached to the vanilla Hit effector,
including the authored blade contact. A cached three-parameter solve (pelvis
yaw, contact-chain bend about world X/Z) fits the processed Hit direction after
articulation. This accounts for the changed contact position and COM. It runs
only when the target changes, not per frame, with no NN work. There is no target
rejection or added pelvis pitch/roll fallback. Alignment controls direction;
changing the spine shape changes radial reach, so distance is not forced.

Kicks/jabs/pike reach the aim correction at Armed; others at Hit. Quintic timing,
manual/timeline application and immediate target updates remain. Aim amount
scales yaw and chain bend (100% full alignment); it is no longer a fraction of
one rigid-body shortest rotation. `Undo rotation`, at the right of the viewport
checkbox row, defaults on. Off retains the complete correction after End/Out;
later timeline attacks interpolate from that retained yaw and chain deformation,
including when the contact changes from a hand to a foot. The toggle controls
aiming return only, not the existing pelvis compensation recovery. Scene save
and paused toggling are unchanged. Static aiming only; no bodyflip coordination.

Verification: 8,580 samples across all16 attacks with both entry modes; target
directions, native contact calibration, Armed/Hit deadlines, 32 Undo rotation
cases, manual/timeline routes, COM/root, fixed sockets, unchanged non-chain
rotations and uniform chain increments. Added pelvis pitch/roll was below
6e-16 radians; direction error below9e-9. Saved Slash L target at full alignment:
156.71 degrees pelvis yaw,6.08 degrees total spine bend,zero added pelvis tilt.
At the saved80%, residual direction error is29.74 degrees. At100%, the contact
is17.52cm past the target center: direction aligns, reach is not warped.
No browser/desktop control, scene writes, Unreal changes or server restart.
User Refresh loads the source changes; visual feel awaits user review.

Camera orbit now permits almost vertical downward/upward views (89.94 degrees).
It rotates at constant viewing distance, retains both drag signs, saved cameras,
free-camera behavior and unlimited zoom out; zoom in also works near the poles.

## Approved attack checkpoint - October 27

User approved the integrated kicks, pelvis-only return and Direct to Armed for
all16 attacks. This checkpoint includes scoped lab source, both viewers, tests,
verification receipts and documentation on `codex/standalone-sim`. Live scenes,
preview images, NN caches and parallel Unreal/Foot IK changes remain local.
The recovery inventory covers the selected committed tree. The following
local/unpushed notes describe development before this approved checkpoint.

## Direct-to-Armed entry for every attack - October 27

`Direct to Armed` now controls all16 attacks, from both timeline markers and the
manual Attack button. The main checkbox remains immediately after Raw leg in the
viewport row; its kick-only label is removed. The soft-leg comparison viewer now
also has this checkbox on the right, alongside the kick viewer's existing one.
Default off; the legacy saved key `kickToArmed` is retained so enabled scenes
keep their choice. Toggling retains the playhead and existing control positions.

Upper-body attacks interpolate their affected local joints directly from the
current pose to the transferred Armed pose (authored pelvis rotation included
at spine_01). The interpolator carries initial local velocity/acceleration and
meets the forward Armed derivatives, then resumes the complete native recording.
The upper14 keep their existing compensation, leg response and pelvis-only
return. Kicks retain their approved full-body solver. Manual aiming, variants,
rate and original off-mode entry behavior remain supported. Manual direct entry
uses the same planner as timeline entry, with its existing0.15/0.45 In/Out.

2596 direct-mode samples cover all16 timeline/manual attacks, variants, moving
gait, rates, exact Armed timing, native upper follow-through, entry/endpoints,
manual parity and reverse seek. Mutating pre-Armed keys does not alter entry.
Upper source error<1.1e-14, manual parity<1.6e-16, Armed angular-velocity join
error<2e-5rad/s.84 off-mode cases/5100 samples still preserve original strikes
and follow-through. Aimed jab/slash manual paths, viewer syntax, current checkbox
label and HTTP byte/no-store checks pass. Receipt:
`all-armed-entry-verification.json`. No browser control or saved-scene writes.

On: skip the recorded frame-zero/pre-Armed path and interpolate the current
pose directly to Armed. Off: retain the previously approved complete recording.
Historical static-harness timing (superseded by live angular arming above):
entry = max(Attack In, authored Armed/fps), then Armed->Hit->End at native speed.
For both current kicks Armed is at0.30s; Hit L0.4333s/R0.40s. Out timing remains
unchanged. Manual loop duration follows the shorter entry instead of adding an
idle gap. Hierarchy-local quaternion interpolation retains sockets/knee hinges;
endpoint velocity/acceleration match the recorded motion so Armed is not a stop.
The existing full-body balance and pelvis-only recovery still operate afterward.
No pre-Armed recording frames are sampled as part of the direct entry path.

Source inspected: final_harness_standalone/index.html, standaloneBlendPoseLocalAxes,
standaloneIndependentStartPoseAt, standalonePlannedEasyEntry, and the Armed/Hit
clock around lines24018-24094. Ground-foot travel anchors do not apply to the
airborne entry. The lab uses fixed-length FK and velocity-matched quintic local
rotation interpolation rather than importing the harness's world-point blend.

1182 direct-mode samples pass for both kicks, selected manual variants/rates,
current moving gait, carried rotation/translation, COM, hinges, exact Armed
endpoint, native post-Armed source, endpoint velocity, recovery and seek. Viewer/
app parity <5.2e-14; knees3.23-146.46deg. The off-mode1314 samples retain prior
results. Longer In timing, cache separation, checkbox persistence/placement,
manual loop duration, embedded script syntax and HTTP no-store/byte parity pass.
Receipts: `kick-armed-verification.json`, `kick-integration-verification.json`.
No scene writes, browser control, inference or restart. Local/unpushed; Refresh
loads the checkbox, then the user enables it for comparison.

## Current kick integration - October 27

The full-body kick viewer is now connected to the app. Previously timeline and
manual attacks selected only spine_01 descendants, silently dropping both kick
legs. `kick-attack.js` now shares the exact `airborne-motion.js` recording,
balanced solve and pelvis-only recovery between the viewer, timeline markers
and Attack button. Other 14 attacks retain the existing upper-body path.

With direct-to-Armed off, kicks play from frame zero, preserving the chamber,
strike and follow-through. Timeline In/Out set entry/recovery durations; manual
retains 0.15/0.45 s and its selected variant/rate. They do not match/skip to an
upper-body Armed frame. Kicks use the approved full-body balance independently
of the upper-body Amount/Soft legs controls; tooltips now state that scope.
The direct-entry checkbox above is the only added control. The active kick is not
redirected by the manual upper-body Aim overlay.

The ongoing pose fades out/in at entry/recovery; root/pelvis facing carries the
kick with the character. COM follows the underlying scene motion. Full-body
plan caches are shared per clip/reference/timing, bounded to eight timings per
clip; repeated markers do not repeat the numerical solve. Browser dependencies
are loaded in the main app and both viewers. The user refreshes; no UI control,
scene writes, inference, workers or server/Unreal restart were performed.

Validation: 1314 kick samples cover both legs, timeline, actual manual functions,
selected variants, rates 0.5/1/2, moving/rotating baseline, run entry/exit, COM,
sockets, hinged knees and reverse seek. Viewer parity error <5.4e-15; knees
3.04-146.46 degrees, COM error <8.9e-15. 32 cached kicks sampled in 5.7 ms.
84 upper-attack cases / 5100 samples retain original strike/follow-through;
2121 manual integration samples pass. 90 sequence checks pass (32 overlapping
upper attacks: 2764 ms). Read-only replay of the current saved Space gym Kick L
reaches source Hit frame13 at1.5667 s with the full leg motion. HTTP serves exact
current files with no-store; embedded viewer script syntax passes.
Receipts: `kick-integration-verification.json`,
`all-attack-hit-return-verification.json`, `leg-response-integration-verification.json`,
`space-attacks-verification.json`. Local/unpushed.

## Current attack recovery - October 27

The post-Hit upright correction now applies only to the pelvis. The user rejected
the full-body Hit-to-base blend because it removed Slash R's follow-through.
That full-body return is removed. `Recovery.pelvisReturn` continuously samples
the original source motion, while the pelvis's Hit-relative rotation decays to
the ongoing baseline over the same existing time window.

Each direct pelvis child (spine and hips) is counter-rotated so all non-pelvis
bones keep their live source world orientations. The arms, torso, legs, knees
and weapon therefore continue their authored follow-through; no Hit-pose freeze
or direct blend is imposed on them. Sockets and pelvis position are retained;
child anchor positions naturally follow the rotated pelvis. This is orientation
preservation, not a claim that every world-space point is identical.

The shared helper serves all 16 timeline and manual attacks, rigid/soft/zero
compensation modes, the soft-leg viewer and both full-body kick previews. In the
kick preview the normal source/compensation recovery is retained for the other
segments, and the COM is recentered after the pelvis correction. Its left side
remains the original recording. No attack-name exception or new UI controls.

Every strike through Hit and original finish time remain unchanged. Timeline
return ends at source end + attackOut; manual at clip.duration + 0.6. The kicks
still finish at 1.1633 s. Gait, root facing, jumps and flips continue. Timeline
attack phase/source-frame metadata again follows the full source animation,
including post-Hit follow-through. Amount retains its opposite-angle meaning.
Pelvis recovery is authored, not torque-free angular-momentum conservation.

Validation: 96 cases / 5784 samples compare all 16 manual/timeline attacks in
soft, rigid and zero-compensation modes with saved pre-change source samplers.
Every non-pelvis world orientation matches through the entire follow-through
(maximum error 1.57e-15), including Slash R. Strike error is below 1.4e-15;
pelvis return is monotone; original end times, baseline endpoints, reverse seek,
sockets, knee hinges and ranges pass. Manual rates 0.5/1/2x and moving gait are
covered. The hit boundary remains pose-continuous; incoming pelvis velocity is
not asserted continuous across the authored turnaround.

Other checks pass: 1390 return samples (including unchanged kick non-pelvis
orientations), 2379 integration samples, 1676 compensation samples, 7192 soft-leg
samples, and all 94 sequence checks. 32 overlapping markers took 2202 ms on this
run. Sequence checks again require the complete authored post-Hit source motion.

Receipts: `all-attack-hit-return-verification.json`, `attack-return-verification.json`,
`leg-response-integration-verification.json`, `attack-compensation-verification.json`,
`soft-legs-verification.json`, `space-attacks-verification.json`. Twelve actual
collider/weapon frames comparing original Slash R with pelvis-only recovery were
reviewed offline in `Saved/BodyflipLab/PelvisOnlyReturn/slashR-follow-through.png`.
Local/unpushed; no desktop/browser control, scene writes, inference or restart.
Read-only HTTP confirms current scripts; user refreshes the lab/viewers.

## Full-body kick solver - October 27

The approved three-axis lab was pushed and remote-verified as
`6a3c2f7c513c3313c9b0ad7e8e7ca7b7c17a403a` on `codex/standalone-sim` before
starting this work. Recovery inventory: 8943 files, 1,073,585,378 bytes, no LFS
pointers. The main lab retains that approved strike behavior and percentage
meaning, with the shared pose return above added afterward. The full-body kick
solver is now integrated as documented above, local/unpushed.

`kick-preview.html` on the existing 8876 service compares the complete recorded
Kick L/R articulation with an airborne conversion. Existing Left/Right selector,
one playback bar, frame stepping and 0.25/0.5/1x speed are retained. It uses the
main renderer's actual collider meshes. No app/scene writes, browser control,
workers, NN requests or server restart. User refreshes the existing viewer.

The former main attack layer selected only spine_01 descendants and discarded
the kicks' leg animation; that mask is now bypassed for full-body kicks. These 17-frame, 30 Hz clips contain knee
chamber then extension: Armed 9; Hit 13 for L and 12 for R. The preview retains
the native keys and strike timing instead of reusing the throw/heading leg curves.
The R source includes shin twist: the retargeter reconstructs the recorded leg
plane at the hip, retains a hinged knee and preserves ankle orientation. Fixed
lab lengths move knee/foot positions by at most 3.35 mm relative to the source.

Latest correction addresses the knee snap, excessive pelvis turn and sideways
free-leg response. Source local rotations and knee angles now use C2 splines:
velocity and acceleration are continuous across source keys. Entry and return
match both source velocity and acceleration. The return decays smoothly rather
than carrying the source's sideways leg velocity into a wide recovery pose.
Dense checks found no knee inversion or overflexion from the interpolation.

`airborne-motion.js:createBalanced` distributes the response over common body
rotation, spine_01, both shoulders and the non-striking hip/knee. Pelvis turn
and sideways free-hip motion are penalized more strongly than torso, arm and
forward/backward leg motion. The free knee remains a hinge with a smooth
0-150 degree range. As the kick releases, the relative joints return toward
their resting pose while common body rotation carries the remaining response;
the free leg is no longer held out to counter the recovery turn.

The striking thigh, shin and foot retain their recorded world orientations
through chamber, strike and retraction, using an inverse correction at the hip.
Their hip-to-foot vector, knee bend, ankle motion and native timing are retained
after hinge retargeting. This protection releases smoothly during return.
It preserves direction relative to the moving hip, not an absolute world foot
position: COM recentering and pelvis motion can translate that hip.

The articulated planner solves three-axis angular momentum at 120 Hz using the
shared segment mass/inertia model. A critically damped response with 60 ms
lookahead smooths the balancing joints; it does not filter the striking leg.
A second momentum solve adjusts common body rotation after that smoothing.
The final displayed body-turn curve is C2, with bounded deterministic caches.
The skeleton is recentered on the requested COM path. Incoming spin and a
ballistic COM path are supported; this viewer starts at zero spin with fixed
COM. Remaining body orientation after recovery is retained, not reset by an
external torque. The solver has no Kick L/R-specific response branch.

This is momentum-constrained kinematic retargeting with approximate segment
inertias, not measured muscle dynamics or a contact simulation. Balancing joints
are deliberately changed; the striking chain's direction/timing is protected.
The upper-body attacks' opposite-angle percentage is not reused with a new meaning.

References: [Kim et al. 2011](https://www.jssm.org/researchjssm-10-31.xml.xml)
measured different hip/knee coordination across kick types, supporting retention
of each recording's coordination. [Preuschl et al. 2016](https://jssm.org/jssm-15-92.xml-Fulltext)
studied 22 athletes' airborne axe kicks and did not find a universal
proximal-to-distal sequence. These support preserving source timing, not copying
an axe-kick pose onto these clips. The response here is a mechanics-based
adaptation, not a measured airborne version of the source animation.

Validation: `node Labs/BodyflipLab/verify-airborne-kicks.mjs` passes 1136 dense
pose samples across both complete motions, including entry and recovery.
Checks cover native keys/timing, active-chain orientations and hip-to-foot
direction, hinges, sockets, COM, joint/body velocity continuity, knee acceleration
continuity, reverse seeking, bounded caches, incoming spin and ballistic COM.
Displayed momentum residual at solve ticks is below 1e-8 kg m^2/s; inter-tick
240 Hz momentum RMS is 0.15-0.18% of raw motion (peak residual below 0.09).
Interpolation is not claimed to conserve exactly between solve ticks.

Maximum pelvis correction over the full motion is 20.79 degrees L / 62.46 R,
versus 50.41 / 98.32 with the previous rigid solver on the same source curves.
The R maximum occurs during recovery; remaining whole-body reorientation is
intentional. Added sideways free-hip response is at most 4.24 degrees. Peak
added knee acceleration during the source clip is 25.73 / 34.30 m/s^2, down
from 55.67 / 79.14 in the user-rejected snapshot. Source kick acceleration itself
is retained. Preparation takes approximately 0.6-0.7 s once per clip; subsequent
playback and seeking sample the bounded cache.

Receipt: `airborne-kicks-verification.json`. Offline actual-collider sheets for
source / previous / current motion were reviewed through recovery:
`Saved/BodyflipLab/AirborneKicks/MotionReview/KickL-review.png` and
`KickR-review.png`. No browser/desktop interaction was performed. Preview and
module serving were checked with read-only HTTP; the user must refresh.

## Approved lab: opposite-angle percentage on all three axes - October 27

Amount has its original meaning again: it scales the attack-added spine
rotation in the opposite direction.50% targets half the opposite rotation;
100% targets the complete opposite rotation. This uses a quaternion rotation
vector in the underlying pelvis frame, covering yaw, pitch and roll with the
same rule. It excludes baseline gait/facing/flip rotation. The upper body is
counter-corrected at spine_01 to retain its authored world orientations.

Both manual attacks and timeline attacks pass the same rigid angle target to
the shared soft-leg planner. As in the original yaw planner, the solver uses
the momentum of that target pose to distribute the response across pelvis and
hips. It no longer treats Amount as a fraction of angular momentum to cancel.
A missing target now fails explicitly instead of silently selecting another
meaning. The existing leg reference, damped response,60 ms lookahead,60 Hz
cache, knee hinges and smoothly bounded18-degree hip corrections are retained.
There is no attack-name branch or separate headbutt calibration.

The percentage specifies the target pose. Leg articulation and smoothing mean
the displayed pelvis need not rotate by that exact fraction at every frame, nor
reproduce the previous yaw-only solver exactly. Controlled Slash L at95% now
peaks at22.82 degrees pelvis yaw, versus124.85 in the superseded momentum-fraction
version (and40.62 before the three-axis upgrade). Headbutt uses this same rule.
Default50%, saved scene tuning, UI order and refresh/save behavior are unchanged.

Leg coordination still blends continuously by the actual upper-body
Armed-to-Hit rotation. Twist-heavy motion uses the jump-throw reference;
forward/backward and lateral rotation use the bilateral opposing swing.
Sources remain [Kristensen2002](https://ojs.ub.uni-konstanz.de/cpa/article/view/726/648),
[Kristensen et al.2004](https://www.tandfonline.com/doi/abs/10.1080/14763140408522840)
and [Zordan et al.2014](https://www2.cs.sfu.ca/~kkyin/papers/rotation.pdf).
The additional leg-angle curves are authored qualitative coordination, not
measured mocap. This is a smooth kinematic response, not exact physical angular
momentum conservation. The earlier44.9% cancellation result is superseded.

Validation:21 signed-axis/mixed-axis cases at0/50/100%; exact opposite-angle
targets; independent planner-to-target momentum checks; target contract cannot
be overridden by changing amount metadata; attack-selector/clip renaming
leaves both Slash L and headbutt motion identical.7192 scheduled samples across
all16 attacks at50/100%,2379 manual/continuing-gait samples and1676 rigid-angle
samples pass. Upper orientations, rigid sockets, knee range/hinges, global
rotation invariance and deterministic seeking pass. The93 sequence behavior
checks pass, but the32-overlap stress timing is3598-3790 ms against its3000 ms
limit on the current laptop run; that performance check remains unresolved.
No further motion changes were made to chase this stress case.

Receipts: `spatial-compensation-verification.json`,
`soft-legs-verification.json`, `leg-response-integration-verification.json`,
`attack-compensation-verification.json`, `angle-calibration-verification.json`.
The prior `space-attacks-verification.json` passing timing is historical.
Both main app and comparison viewer use this current system. No browser/desktop
control, scene/state writes, NN requests or restart; user Refresh loads it.
Pushed and verified as `6a3c2f7c` before the isolated kick experiment above.
Earlier dated compensation sections below are history.

## Previous integration checkpoint - October 27

The user approved bringing the viewer motion into the complete app. The shared
`leg-response.js` now runs through `attack-inertia.js` for all sixteen scheduled
attacks and the manual Attack button. No separate copy or new UI controls:
existing Soft legs enables it; compensation controls its amount. Off retains
the rigid comparison. Upper-body attack orientations and rigid sockets remain
unchanged. Both the app and the right-hand viewer now use this same response;
the viewer's left side explicitly requests the older yaw-only response.

The moving-gait check found that filtering a knee angle offset could preserve
extension after the baseline knee had already straightened, bending it backward.
Knee response now filters separate fractions of available extension and flexion.
The critically damped fractions remain between0 and1, so the output respects
the current knee's range without clipping the rendered pose or its velocity.
The approved Slash L /100% idle comparison changes at most0.099degrees/0.735mm;
left hip-to-foot peak acceleration reduction remains75%. This is still an
angular posture response, not full physical angular-momentum conservation.

Verified7192 scheduled samples across16 attacks at50/100%,2379 samples through
the actual manual functions and continuing Run gait, root-rotation equivariance,
hinges, sockets, exact shared-viewer parity and deterministic seeking.94 sequence
checks including32 overlapping markers pass. Moving-gait/manual knees remain
9.79-120.52degrees. Receipts: `leg-response-integration-verification.json`,
`approved-response-parity.json`, `soft-legs-verification.json` and the existing
viewer/sequence receipts. No workers, inference or server restart added.

**Refresh required:** the user stopped Computer Use and explicitly forbids
desktop/browser control. Complete background code/checks only; leave Refresh
to the user. The live app was not refreshed and live scenes/settings were not
written. This integration is local, after pushed checkpoint681c75b5.

## Soft legs: human reference revision - October 27

Soft legs now uses separate hip/knee trajectories adapted from the airborne
jump-throw curves in Wagner et al. (2011), Figure 2 A-D. The old symmetric
turn-speed knee bend and fixed hip/knee ratio were rejected by the user and
removed. These are approximate, rounded readings of published mean curves;
this is an adaptation to the lab attacks, NOT original mocap or a sword capture.

The follow leg extends through the strike while the lead thigh moves forward.
Attack-added spine turn determines which side follows and scales the gesture;
small yaw attacks receive proportionally little motion. Existing compensation
Amount also scales it. Armed maps to late cocking (-160ms), Hit to release.
A monotone cubic clock and shape-preserving joint curves preserve velocity at
phase boundaries. Quintic entry/return weights blend with the continuing base
pose. Strikes with less than160ms from Armed to Hit reduce the excursion in
proportion to time, rather than rushing through a full throwing gesture.

Hip flexion uses the pelvis sagittal plane, so splayed legs still travel forward.
Knees flex AND extend about the canonical rig hinge; no knee-position IK,
new pole, changed segment lengths or coupled45% hip rule. Starting folded legs
can unfold. The target stays between5 and150 degrees of knee flexion; the
blend retains the starting pose and its joint velocities. Foot/toe local
orientations remain authored. Whole-character flips carry the motion correctly.
Scheduled/manual paths use the real source Armed/Hit metadata; manual sampling
includes its existing150ms entry. No new controls or saved-state migration.

### Inertial response follow-up

The reference poses were accepted but the lower-body rotation was jittery.
Measured Slash L at80% reversed pelvis velocity within a tick, with peak
acceleration2152rad/s^2. The momentum planner imposed a fresh angle each tick;
its hard18-degree hip-lag projection also introduced abrupt rate changes.

The planner remains a target generator. Displayed pelvis/leg yaw now follows
it through a critically damped angular spring at32rad/s, integrated exactly
against the moving target. Position AND angular velocity persist between ticks.
Sampling uses the same analytic integration between120Hz cache points, so angular
velocity and acceleration remain continuous. The output is not hard-clamped.
Identical responses for pelvis and leg yaw retain the relative-lag bound without
an instantaneous projection. Reference hip/knee curves, knee hinge, upper-body
world orientations, root and rigid sockets are unchanged. Soft legs off still
restores the original rigid lower-body turn.

This introduces about63ms low-frequency rotational lag and intentionally relaxes
instantaneous agreement with the old yaw-momentum budget. The planner's residual
is now named maxPlannedResidual; it must NOT be reported as a conservation error
for the displayed body. At80%, the output's peak yaw-momentum difference from
the old target is3.12 kg m^2/s for Slash L and7.26 for Slash RU in this approximate
model. Full3D conservation and sword inertia are still outside scope. The final
planned turn is preserved: after the finite cache the response continues settling
analytically, without growing history or freezing a nonzero velocity.

Verification:6424 poses across16 attacks at50/100% retain exact upper orientations,
hinge-only knee rotation, unchanged foot-local orientation/sockets, deterministic
reverse seeks and tilted-character equivariance. At80%, peak pelvis acceleration
falls94% for Slash L and80% for Slash RU, retaining85%/82% of peak turn amplitude.
Maximum total hip step over the16-attack sweep falls16.2->6.9 degrees/120Hz tick;
the reference knee trajectory is unchanged. Independent finite differences of the
actual sampler agree with its velocity within3e-9rad/s; acceleration boundary
discrepancy is<0.017rad/s^2 at1us spacing. Tail continuity, final angle and bounded
cache pass.94 sequence regressions (including32 overlaps) plus owned browser
manual/scheduled orientation, UI/refresh checks pass. Browser saves intercepted
and browser closed. No user-state write, Unreal/server restart, training or push.

Read-only comparison: `soft-legs-preview.html` initially compared immediate
correction with inertial yaw; the whole-leg experiment below supersedes that
comparison. It initially loads saved attack/amount; optional
`?attack=slashRU` selects another vanilla clip without saving. Play now keeps
fractional time between draws instead of repeatedly rounding the clock to frames.
Rendering remains capped at30Hz and stops when hidden/paused. Scrubbing still
selects exact60Hz frames. Current half-speed recording:
`Saved/BodyflipLab/soft-legs-inertial.gif`. Earlier recordings are historical.
Receipts: `inertial-response-verification.json`, `soft-legs-verification.json`.

Viewer tuning (October27): Compensation0-100% slider and editable number are
appended on the right of the existing header. Both views update at the current
frame; edits keep the camera and play state. Numeric edits apply on blur/Enter.
A single motion plan drives both canvases to keep dragging lightweight. The
Before view uses the existing yaw response; After uses the viewer-only whole-leg
response described below. Amount0 keeps the same timeline length.

This tab keeps its selected motion/event, amount, frame, play state and camera
in sessionStorage across refreshes. It never POSTs lab settings or requests NN.
The user initially requested tuning here before returning to the lab; the
deployment section above records their subsequent authorization to integrate it.
Refreshed existing IAB tab4 rather than opening another. Verified slider0,
numeric100 on blur, frame52 retained, refresh retaining100/frame52; restored80
and resumed playback. Screenshot: Saved/BodyflipLab/preview-compensation.jpg.

### Viewer-only whole-leg response - October 27

The user then identified abrupt stopping/jitter in the left hip-to-foot vector.
At the viewer's current Slash L /100%, peak vector angular acceleration was
275.45rad/s^2 around frames51-52; removing yaw correction still gave271.83.
The remaining stop therefore mostly came from the reference hip/knee curves,
which the earlier yaw-only response did not filter.

The response module (now `leg-response.js`) gives pelvis, both thighs, both feet and both knee
bends persistent angular position/velocity. Thigh/foot orientation corrections
are root-relative, so a pelvis turn cannot drag them around instantaneously.
Knees remain on their anatomical hinge; there is no positional leg IK or moving
pole. The pelvis uses32rad/s and legs24rad/s critically damped responses, with
exact integration against linearly changing targets and continuous sampling.
Base idle motion continues. The cache is bounded and the tail settles analytically.
Upper-body world orientations and rigid sockets are preserved. This is a posture
response experiment, not a full physical angular-momentum conservation solve.

The existing viewer now compares Yaw inertia only (left) with Whole-leg inertia
(right). No additional controls; compensation remains editable. At100%, left
hip-to-foot peak acceleration falls275.45->67.91rad/s^2 (75%), retaining92% of
directional excursion. Right falls110.05->41.55 (62%), retaining84%. Tests at
0/50/100% also check hinge-only knees, rigid sockets, upper orientations, reverse
seek determinism, analytic velocity and bounded cache. Zero compensation is
unchanged. Current knee flexion remains14.5-78.7degrees.

At that checkpoint only the preview imported the new module; lab motion,
defaults, saved state and Unreal were untouched. Existing IAB tab4 refreshed, frames52/58 inspected, then
restored to the user's paused frame25 at100% with its camera retained. Receipt:
`viewer-leg-response-verification.json`; run `node verify-viewer-leg-response.mjs`.
Screenshot: `Saved/BodyflipLab/whole-leg-inertia.jpg`. The main-app integration
above supersedes this earlier viewer-only scope.


Sources:
- Wagner et al.,2011, [Performance and Kinematics of Various Throwing Techniques in Team-Handball](https://pmc.ncbi.nlm.nih.gov/articles/PMC3737895/), [Figure 2](https://www.jssm.org/mobile/ShowFigure.php?FigureId=fig002&jid=jssm-10-73.xml). The numeric hip/knee curve reference used here.
- Liu et al.,2025, [Volleyball jump-serve aerial kinetics](https://pmc.ncbi.nlm.nih.gov/articles/PMC12751981/). Supports phase-dependent flexion/extension; its curves are NOT implemented as a separate overhead profile yet.
- Zordan et al.,2014, [Control of Rotational Dynamics for Ground and Aerial Behavior](https://pubmed.ncbi.nlm.nih.gov/26357383/). Background for the reduced inertia model, not a reproduction.

## Pelvis attack compensation - October 26

Appended Pelvis attack compensation at the bottom of More options:0-100%,
default50%. Measures attack-added spine_01 forward-heading change around the
underlying pelvis's local up axis, after entry/return blending. Rotates the
pelvis by the negative of that yaw times the amount, then inversely corrects
spine_01 so every upper-body world orientation stays unchanged.50% is half,
100% equal/opposite;0 preserves the previous fixed-pelvis behavior. This is an
artistic angular counter-motion, not an inertia-weighted conservation solver.

The pelvis retains its position; legs inherit its turn with their local joint
rotations intact. Joint socket offsets stay rigid, so the first spine socket
moves with the pelvis. Whole-body flips are not counted as attack yaw. Scheduled
and manual attacks both use the correction; manual aiming runs before it.
Edits preserve playback position; settings save/restore per scene. No extra
controls, data migration, Unreal changes or server restart.

1676 sampled poses across16 attacks verify0/50/100%, exact proportional counter
yaw, upper orientation preservation, unchanged local leg rotations/sockets and
continuous entry/Armed/return. An explicit60-degree source yaw gives-30/-60 on
a tilted pelvis.580 source-transfer checks,94 sequence and30 torso/Jolt checks
pass. Owned browser verifies control placement/default/edit, frame66 retention,
refresh persistence, and manual slash/kick upper orientation; no app errors.
Browser closed; saves intercepted, live scene untouched. Refresh to activate.

## Attack pelvis rotation carried by spine_01 - October 26

Upper-only attacks now transfer the source pelvis rotation relative to its first
frame into spine_01. In quaternion order: inverse(initial pelvis local rotation)
* current pelvis local rotation * current spine_01 local rotation. This carries
all three rotation axes, not just yaw, and preserves the authored upper-body
orientation relative to the initial pelvis. Root facing/translation is not added;
the actual pelvis and legs remain controlled by the underlying motion.

Scheduled closest-frame matching, entry and authored playback all use this
corrected target. Existing return blending removes it smoothly. Manual Strike
uses the same transfer before its upper-body blend; aim does not add it twice.
Raw clips and joint offsets are unchanged. No extra UI or settings migration.

Verification:580 source/interpolated poses across all16 attacks match the
independent world-orientation reference within1.7e-15rad, including tilted and
moving destination pelvises. Root/pelvis/legs unchanged within1.5e-15;
entry/Armed/return boundaries continuous.94 sequence regressions and30 actual
Jolt/torso checks pass. Owned headless browser checked frames48/60/66 and manual
slash/kick lower-body invariance with no app errors; fixture intercepted saves
and closed. No Unreal/server restart, live-state overwrite or push. Refresh.

## Five faithful spine boxes - October 26

User chose to retain the box-shaped torso and match five physical colliders.
The old display merged pelvis->spine_02 and spine_02->spine_04 into larger
blocks, omitted a separate spine_05 volume, and reconstructed each block from
joint endpoints. This concealed individual spine rotations, especially the first.
The scheduled attack already included spine_01 and all its descendants.

`torso.js` now defines one rigid box for each spine_01..05 in that bone's local
frame. Rendering and Jolt consume the same dimensions, offset and orientation.
The renderer uses the bone transform directly; dimensions do not stretch and
neighbouring joints cannot supply its rotation. Jolt's former five spine capsules
are now matching zero-bevel boxes. Five spine constraints, masses and COM offsets
retain their previous ownership. Only torso collider geometry/inertia changes;
other lab bodies/contact planning and Unreal are unchanged. This is torso parity,
not a claim that the remaining stylized limb/hand/head display equals Jolt shapes.
Kinematic mode still displays exact target poses without running a Jolt solve.

Manual Strike now uses the same spine_01 upper-body mask as scheduled attacks,
including its optional aim result; neither can overwrite pelvis or leg motion.
No UI changes. Refresh retains scene/playback state.

30 focused checks verify all five actual Jolt box types, dimensions (<1.3e-8m),
offsets (<1.4e-9m), orientations (<6.2e-8rad), bone-local rotation ownership,
spine_01 authored attack motion, fixed pelvis, exact kinematic poses and a small
simulated attack (maximum joint-anchor error0.594mm). Owned headless browser
reviewed front frames36/48/60/66, five visible articulated boxes, manual slash
and kick upper-only behavior (lower-body position error<1.2e-15m), and no app
errors.94 scheduled-motion regressions pass. Preview saves intercepted/browser
closed. No server/Unreal restart, user-state overwrite or push.

## Space gym, jump strength and scheduled attacks - October 26

Sequence now appends **Space gym**: zero gravity, no contact requirement, and the
same jump markers, flips, poses and playback. Root starts stationary in free
space. Positive jump values add world-up impulse and retain constant drift;
0% adds no impulse but still plays choreography. Platforms remain saved in the
scene and reappear when returning to Idle/Walk/Run. No locomotion or landing NN
requests are made in Space gym. Sim mode also disables Jolt gravity and its
pelvis gravity compensation. The existing continuous Air flip remains available.

The marker popup appends **Jump %**, **Attack**, and its **Delay s**, in that order.
Jump defaults to100;0 disables push,400 is the current upper bound. Percentage
scales active jump energy (sqrt scaling for launch speed), so on level ground
without loading25% gives one-quarter height. Existing loading/rebound still adds
returned impact energy.100 preserves the previous root trajectory. Ground0%
keeps the current motion instead of planting a foot for an artificial jump.

Attack defaults toNone. All16 original melee/sword clips are available, with
only the spine, neck/head, clavicles, arms and hands overridden. Kicks therefore
play their upper-body portion only. Root, pelvis, leg transforms and lengths
stay with the underlying motion. These are vanilla clips, without target aiming.
Delay is measured from foot release, or the marker itself in Space/0% actions.
Two per-marker **Attack blend In/Out** fields append at the bottom of More options.
In is a minimum entry duration; a longer remaining authored wind-up keeps its
normal duration. Out returns to the continuing underlying pose.

`export_vanilla_attacks.py` extracts original basePayload positions/basis from
Final Harness, before any target solver, and source Armed/Hit metadata.16 clips,
306 frames,381888 bytes; provenance/hash receipt in `data/vanilla.json`. Source
harness and NPZs remain unchanged. `jump-attack.js` adapts the harness functions
`standaloneIndependentStartPoseAt`, `standalonePlannedEasyEntry` and
`standaloneBlendPoseLocalAxes`: continuing outgoing motion joins moving pre-Armed
animation through hierarchy-local rotations, then Armed->End uses native fps.
The added closest-frame search compares upper local rotations from frame0 through
Armed at attack onset, ignoring pelvis/world orientation. A smooth blend weight
preserves motion at entry; existing velocity-aware transition handles return.
This is a contained adaptation, not a live dependency on the Final Harness UI.

Scheduled attacks are inside the flight sampler, before capsule landing seeds.
The NN therefore resumes from the actual attacked pose; landing ends choreography.
Space attack overlaps use the displayed outgoing pose and a bounded tiny cache.
Clips load lazily; completed layers do no attack pose calculations.

Validation:97 focused checks pass, including all16 vanilla clips, upper-only
invariance, native Armed playback, delays, overlap, reverse seeking,0/25/100/200%
height,32 overlapping markers and an actual seeded NN landing during attack.
52 marker edits,84 existing motion and38 blend checks pass. Owned headless app
verified1280x900/1000x700 layouts, edits retaining frame48, playback advancement,
refresh restoring time/settings, and return to the preserved ground scene.
All preview saves intercepted; browser closed. No Unreal or server restart,
no live scene overwrite and no push. Refresh the existing Bodyflip window.

## Shared Foot IK on inclined platforms - October 26

Bodyflip now consumes Foot IK's canonical surface/contact solver directly.
`FootIKLab/surface.js` exposes `createFeet()` and its own `prepare()` calls the
same routine. `shared_foot_ik.py` serves the current five Foot IK modules at
`/shared-foot-ik.js` on every Refresh, isolated from Bodyflip's globals. No copy,
watcher, second Foot IK server or shared saved settings is required. Source
changes propagate on Refresh; changing sliders in Foot IK does not copy tuning.
See [the shared API contract](../FootIKLab/SHARED_API.md) before changing exports.

`foot-ik.js` adapts Bodyflip's edited finite platforms and NN poses. The upright
capsule still owns collision/root motion. Mesh pelvis clearance compensation and
Foot IK's body alignment let both feet reach inclined surfaces; contact,
heel/toe roll, reach, ankle and knee rules come from the shared solver. Grounded
Idle/Walk/Run use it; authored support/push/flight retain the existing jump solver.
Corrected pose history feeds ledge falls and actual seeded NN landings. A brief
crest landing resets the correction history so the old tilt is not applied twice.
Corrections are prepared at120Hz, cached for playback/reverse seeking, and ease
out when returning to flat ground. Foot IK is a single checkbox appended at the
bottom of More options. Its edits preserve the playhead.

**Desktop activation pending:** current8876/PID27312 is still API5. Automatic
approval review rejected the verified Bodyflip-only restart with "blocked by
policy". No alternate restart was attempted. The old server remains usable;
Foot IK is disabled with "server restart needed" until the server is restarted
normally. Current source is API6. The isolated API6 test server8891/PID12412 and
owned test browser were closed after verification. No Unreal or Foot IK service
restart, live-state writes or push.

Validation:1529 integration checks covering Walk/Run toward/across45deg surfaces,
material contacts, shoe clearance, lengths, knee steps, a real inclined jump and
NN landing, reverse seeking, slope/flat transitions and an edge fall. Largest
steady shoe penetration0.00030mm. Support/landing boundary changes at1e-7s are
0.00056/0.00090mm.84 authored-motion,78 knee-blend and24 capsule checks pass.
Six full Foot IK reference clips (Walk/Run,45deg toward/parallel,90deg parallel)
retain byte-identical poses/metrics/events after the extraction. Isolated browser
verified six rendered frames, source hash, comparison toggle/time preservation,
and the old-server fallback; all state writes were intercepted. Receipts:
`foot-ik-verification.json`, `Saved/BodyflipLab/shared-foot-ik-browser-verification.json`.
Tests use8876 by default; `BODYFLIP_TEST_URL` can select an isolated API6 server.


## Flip and pose timing in More options - October 26

Detailed jump timing now appends after Rebound at the bottom of the existing
viewport **More options** panel. The marker popup retains angles, axis, delay
and pose selection. Select a marker to edit its **J1/J2... Flip / pose** controls:
Turn seconds, Flip blend In/Out seconds, and Pose blend In/Hold/Out seconds.
The selected marker stays selected when its popup closes, so clicking More
options does not lose the editing target. No selected marker means disabled
timing fields and a selection hint. Escape only claims the popup while it is open.

Flip In/Out now control the acceleration/deceleration periods for both angles.
Short blends leave constant angular speed in between; zero disables that ramp.
If In+Out exceeds Turn, both fit proportionally within Turn. Existing settings
without these fields migrate to half-duration each, exactly preserving the prior
quintic curve at every turn duration. No pose blend or takeoff rule changed.

47 editor checks and84 motion checks pass, including independent jump editing,
legacy curve identity, zero/asymmetric/overlong ramps and smooth speed joins.
The isolated browser fixture verifies both popup sizes, the bottom-of-panel
layout, retained selection, native number editing and unchanged playback time.
Actual screenshots checked at1000x700; all new fields fit. Test writes intercepted;
browser closed. No live-state overwrite, Unreal/server changes or push. Refresh.

## Per-jump flips and poses - October 25

Click an existing timeline marker. Its time/Delete/status row stays in place;
the following controls are appended underneath:

- **Flip / Twist degrees:** total signed rotation, including multiple revolutions
  (up to ten each). Both default to zero. Nonzero per-jump angles replace the
  old continuous Air flip for that jump; no Air flip checkbox is required.
- **Axis:** one of the twelve existing directions, or **Lab axis** (default)
  to follow the sidebar grid. The axis follows root heading at release, without
  pelvis gait sway; twist remains around the pelvis vertical axis.
- **Delay seconds:** defaults to zero, measured from foot release. Turn duration
  (default0.8s) and its ease-in/out are now in **More options**, as described above.
  Signed scalar angles stay unwrapped through full turns. Readouts and the axis
  guide show the active jump's rotation.
- **Pose:** No pose by default, plus Pose1-4 marked **temp**. **More options** now
  contains In/Hold/Out (defaults0.2/0.3/0.25s). Pose entry starts at foot release,
  independently of rotation delay, and exit blends back to the moving animation.

The four placeholders are snapshots from existing standing/run/fall clips,
not final authored poses. Their stable IDs and temporary source mapping live in
`jump-motion.js::placeholders`; replace those four local-rotation targets when
the user provides poses. Pose blending changes local rotations only: root,
pelvis position, bone lengths and hip sockets retain their existing ownership.
Do not move the pose slots or timing into a new timeline or rearrange other UI.

`core.sanitizeJump` preserves and validates the new per-marker fields through
save, refresh, scene copy and selection. Existing markers with no choreography
keep their previous motion; inactive/missed jumps do not allocate a motion layer.
The shared sampler feeds both rendering and capsule/landing preparation, so the
NN receives the actual rotated/posed current and preceding frames. A landing
ends any unfinished turn/pose and continues from that pose through the existing
NN handoff. This is kinematic choreography, not an angular-momentum simulation.
Root collision, contact timing, support selection and pin/release rules are unchanged.

Edits retain playback time. Click-away commits a typed value. Escape now closes
the jump popup before the platform editor can consume the key. Popup placement
uses its actual width, with bounded height/scrolling on smaller windows.

Verification:75 motion checks,40 marker/edit/persistence checks and12 actual
NN landing checks pass. Existing78 knee,38 blend,53 matched-body,21 scene and14
refresh checks also pass (331 total). Across Run and Idle, all four placeholders
stay within0-150deg knees; maximum tested angle130.593deg. Root/pinned-frame error
is zero, and landing position discontinuity is below0.000001m. Reverse sampling,
independent jump settings, full turns, delay and blend boundary velocities checked.
`verify-jump-motion-browser.cjs` renders the actual app in an isolated headless
browser with live-state writes blocked:1280x900/1000x700 popup layouts, ten samples
through a flip/twist, Escape, click-away and unchanged playhead verified. The
original browser/native tools failed to initialize; the isolated render succeeded.
Receipts: `jump-motion-verification.json`, `jump-motion-landing-verification.json`,
`jump-track-verification.json`; browser receipt/screenshots under
`Saved/BodyflipLab/jump-motion-*`. No Unreal/other-lab edits, server restart,
live-state overwrite, persistent test process or push. **Refresh the desktop lab**.

## Prevent backwards knees during blends - October 25

Approved checkpoint: the user accepted this result and requested a push. This
also preserves the Idle/new-scene controls, capsule/NN landing, free camera,
matched whole-body jump and opaque leg overlays added since the previous push.
Live scenes/settings remain in ignored `state.json`; restore dependencies below
now distinguish cached locomotion from actual NN landing continuation.

The Walk fixture at frame59 exposed an invalid inertial transition: the supporting
right knee kept its roughly67rad/s extension speed for too long and bent71.66deg
backwards. `core.transition` now checks both knees against the existing0-150deg
hinge range while preparing its trajectory. If carried velocity would exceed it,
that velocity decays sooner with a smooth exponential brake. The thigh, calf,
foot and toe share the decay; the remaining displacement fades over the original
Body/Leg duration. There is no rendered-angle clamp, straight-leg hold, new control
or per-playback-frame constraint search. The original animation deadline and
incoming velocity are retained. The same helper covers jump/body/leg, fall, miss
and attack transitions. Rig registration uses the existing skeleton/reference.

Frame59 now bends28.67deg normally; the dense Walk trajectory reaches a minimum
3.85deg, turns once and continues toward the moving target. Push/release times,
authored root path and the reported pinned contact are unchanged. Also removed
the redundant1um shortening in the IK solve (below full extension): it caused a
tiny pre-release knee lock in the zero-loading case that disagreed with the
velocity used to seed the blend. Full-extension singularity protection remains.

78 new checks cover the reproduced failure, both support legs, Walk/Run, phase,
short/long independent blends, zero loading, joint range, source bone-length
ranges, release/end velocities, no straight hold/repeated recoil, deadlines,
reverse seeks and all16 attack families. Existing38 motion,53 matched-body,
48 contact,24 pacing and24 capsule/NN-landing checks also pass (265 total).
Three-jump preparation measured1.38s versus1.36s without knee braking in the same
process; playback remains cached/stateless. JS syntax passes. Visual inspection
was attempted but both browser and desktop tools failed to initialize (kernel
assets path error). Refresh needed. No live-state overwrite, UI changes, server
restart, Unreal edits or push.

## Preserve movement through transitions - October 25

Body, supporting-leg release, jump-to-fall, ledge-fall and missed-support recovery
now carry the outgoing local position/angular velocity into the moving animation.
The shared `core.transition` samples the source just before the handoff, seeds a
pose/velocity offset against the incoming motion, and removes that offset over
the existing blend duration. Both offset and offset velocity reach zero at the
end. FK keeps the skeleton connected; offset directions preserve bone lengths.
Sampling is deterministic with seeds cached during preparation, so paused scrubs
and reverse playback need no per-frame history or extra inference.

Body still starts at PUSH; Leg still starts at pin release. Contact and procedural
root/pelvis constraints retain ownership. Contact alignment also carries the
incoming shoe rotation rather than restarting at zero angular speed; existing
heel/toe speed and contact fitting remain. This can change reach-release timing
and the closest source frame chosen by Match foot. No new eligibility gates.
Attack entry meets the first clip frame with its authored velocity, return keeps
the terminal velocity, and the moving locomotion/attack layer has smooth entry
and exit weights. Original attack lead/tail durations and hit windows remain.
Actual NN landing feedback is retained without adding a cached-gait crossfade.

Validation:38 motion-transition checks (all16 melee/sword families),53 whole-body
match checks,48 contact alignment,24 support pacing and24 capsule/NN-landing checks
pass. Boundary angular-velocity errors: PUSH0.000273, release0.00850rad/s at a1us
measurement interval; source-keyframe slope changes are accounted for separately.
Frame59-60 left ankle advances9.32cm in the flat Run fixture, with forward progress
through the entry. The contact fixture's expected later events were updated to two
pushes then one miss because the incoming poses changed; geometric/continuity
assertions remain. JS syntax checked. No visual QA. Refresh needed; landing NN
preparation may recompute from the new poses using the existing single-thread CPU
worker. No server restart, live-state overwrite, Unreal edit or new UI controls.

## Whole-body matched jump - October 25

Visualization update: Anim other leg is immediately right of Anim leg, as
requested, and independently shows the opposite leg on the same matched clock.
Anim leg, Anim other leg and Raw leg now draw the agent's full-size thigh/calf
capsules and foot/toe boxes rather than bones. Capsule definitions and foot-box
construction are shared with the agent renderer. Supporting Anim leg is green,
Anim other leg is now red, and Raw leg stays red. All are fully opaque and now
render in the normal scene depth pass, so front surfaces correctly hide back
surfaces and the agent/platforms occlude them normally. Removed the old X-ray
pass, which drew rear triangles over front triangles after opacity was removed. No extra
physics bodies are created. The new toggle defaults off, persists per scene and
only redraws/saves. 53 focused checks pass, including opposite-side selection and
clock agreement for left/right support. JS syntax checked; visual QA not performed.

Match foot now chooses the closest supporting-ankle frame as before, then starts
all animated joints at that frame on PUSH and plays at 1x. The old support-only
slowdown is removed. The pelvis/root path and foot pinning remain procedural.
Body now carries movement from the push pose over Body seconds; the supporting leg keeps
its independent Leg blend starting at release. Loading continues locomotion.
The whole body reaches the falling loop earlier by the matched source offset;
this changes animation timing, not jump height, velocity, contact or release.
Turning Match foot off starts the jump clip normally. Its existing UI position
and saved setting are retained; the readout now says Body and reports 1.000x.

Green Anim leg previews the shared matched animation before IK/blending. Red
Raw leg remains on the original elapsed-since-push clock, so the overlays can
differ from the first push frame. Both follow their own fall-loop transition.
47 focused checks cover both support sides, standing jumps, zero loading,
independent blend durations, source rotations, pins, root path and reverse seek.
Measured root/pin change is zero; local quaternion error is below 4.5e-16.
No visual QA. Refresh to load; landing NN preparation uses the new landing pose.

Resolved frame59-60 diagnosis (before the transition correction above): supporting side R; left leg uses Body0.2s.
At PUSH0.9604167s, body blending starts from the captured launch pose with
smoothstep weight (zero initial slope), losing the incoming gait velocity.
Weights at59/60 are3.638%/10.201%; left ankle advances only8.47mm relative to the
pelvis between those frames, after48.09mm/frame at56-57. This created a visible
near-stop; the movement-preserving transitions above replace that implementation.

## Raw leg overlay - October 25

Raw leg is appended after Free camera, off by default and saved with scene settings.
It shows the supporting leg in red at the original jump timing (elapsed since
push, retaining the existing takeoff trim), attached to the displayed pelvis.
It bypasses the matched-frame offset, support IK and release blending. Anim leg
is green and shows the matched target; both can be enabled for comparison.
Both follow their animation clock's fall transition and hide after capsule landing. Toggling
only redraws/saves; it does not recompute motion. Current Scene 2 samples match
normal animation to 1.15e-16m and differ from the retimed leg by up to 0.786m.
JS syntax checked; no visual verification. Refresh to load.

## Free camera - October 25

Free camera is appended after Show jump in the existing viewport checkbox row.
Enabling captures the rendered eye, direction and viewing distance, including pan;
it stops following COM without changing the view. Q/Z/D/S are left/forward/right/
back, using the typed keys (AZERTY supported). Movement is camera-relative at3m/s,
with normalized diagonals. Left-drag looks around from the eye and retains the
requested inverted vertical direction. Wheel keeps exponential zoom with unlimited
dezoom; middle-pan and right-drag target editing remain available. A click still
selects a platform; dragging cancels selection as before.

Disabling snaps the agent's COM to screen center, retaining the current viewing
direction and distance and clearing pan/offset, then follows COM movement.
Camera state is saved per scene, including
free position; explicit view presets/reset return to follow mode. Text entry,
Ctrl+Z and platform W/E/R controls retain their keys. Held movement works when
paused, releases on key-up/focus loss/hide, and schedules no camera frames at rest.
No motion preparation or NN inference is triggered by camera controls.

16 focused camera checks pass, including unchanged entry and recentered exit for
panned/top/distant views, in-place rotation, movement, wheel, restore and input
ownership. Scenes21 and refresh14 passed with the original free-camera change.
Visual QA unavailable; Refresh loads
this change. No server restart, saved-state overwrite or Unreal work.

## Capsule root collision and landing - October 25

Historical implementation: the October 29 airborne-body-contact section above
supersedes standing-capsule landing during jump flight and hand support.
The later trimmed-generation section supersedes the original 12-second horizon.

The upright carrier uses native AProphecyAgent dimensions: 30cm radius, 86cm
half-height. Root is its lowest point, matching GetRootLowPoint and
SetManagedRootLowPoint. Native source was inspected; no editor was launched or
modified, and Blueprint-instance overrides were not queried.

`capsule.js` sweeps finite oriented platform boxes, including sides/undersides,
slides and resolves initial overlap. The capsule stays upright while the body
flips. Pinned feet retain their world contact when the resolved root moves.
Descending supporting contact resumes locomotion; wall/ceiling hits do not land.
Gaps and edges still fall with the selected speed cap, and later markers can jump.

**Landing handoff correction:** the earlier immediate replacement with a cached
gait pose was a snap. Now capture the resolved landing pose and the preceding
1/30-second pose. `resume_locomotion.py` encodes both into the actual lower41 and
upper90 recurrent states: pelvis, ankle positions/orientations, thigh directions,
toe hinges, upper local rotations and wrists. It uses the original frozen Run or
Walk and Upper checkpoints/codecs, matching the channels in Unreal's
EncodeComponentPoseToNNStates. Capsule-resolved root positions supply the movement
history and future commands, and decoded predictions stay attached to that root.
Idle uses Walk with zero root movement after landing; its pre-jump authored idle
loop remains unchanged. The first output preserves the supplied landing exactly;
following frames are NN predictions, interpolated at the usual 30Hz policy rate.
There is no extra fade into a cached gait. Subsequent jumps start from this new
continuation. Air-flip/twist/axis changes rebuild the landing seed on commit.

`flight.prepare` prepares dependent landings in chronological order; old or
cancelled preparations cannot overwrite newer controls. `sequence` alone is a
collision/planning helper: without a resume provider it holds the captured pose.
The app always uses `prepare`. Initial locomotion still uses the existing phase
banks. The seeded continuation covers the prepared timeline (at least 12seconds,
all markers plus5seconds, and Trim Out); seeks/replays reuse it deterministically.
This is kinematic authored-pose feedback, not live Jolt-body/attack-overlay feedback
or a complete port of Unreal's mover. Static-slab collision remains lab code.

`/resume` uses one serial CPU worker, one Torch/BLAS thread, no GPU/training. It
traces the original policy step to avoid repeated Python dispatch and checks the
compiled output against the eager functions. Decoding is batched. Playback does
no inference. The worker exits after30 idle seconds; eight client continuations,
16 compressed disk results and four compiled gait/mode steps bound ordinary cache
retention in ignored `.resume-cache`. The first uncached setup can take several
seconds (measured7.4s with compiled weights available); repeated disk requests
were14ms. One second of new policy motion took0.245s in the focused check. Own
loopback server8876 restarted for API5; state.json hash unchanged. No new UI,
Unreal change, other-session restart or push.

Validation: 24 capsule checks, 11 landing-codec/NN checks,20 idle,21 scenes,
14 refresh and24 support-pacing checks. The compiled step matched the original
lower step/eager upper through30 recovery predictions with zero measured error.
Perturbing the current foot or previous wrist changes the next prediction, proving
both current pose and motion history are consumed. Across landing, maximum joint
position difference at times separated by0.1microseconds was0.000268mm (continuous
motion, no cached-pose jump). Flat Idle lands at1.85417s; capsule clearance is1um.
Run/Walk, repeat jumps, capsule motion and reverse seeking also pass.
Browser verification is unavailable (CUA kernel-assets error); Refresh is needed.

## Idle sequence - October 25

Idle replaces Space as the stationary starting motion, not a separate feature
mode. All jump controls, markers, trim brackets, More options, attacks and debug
views are available in Idle, Walk and Run. The same support/load/push/fall planner
uses the neutral idle loop before the first marker; with no markers it idles
indefinitely. Phase sets its initial animation phase. The existing speed threshold
selects the standing jump automatically, and airborne flip/twist work as usual.
Default marker timing still comes from duration minus Early, until edited manually.

The frozen M_Neutral_Stand_Idle_Loop has301frames at30Hz (10seconds), stationary
horizontal root and grounded shoes. The original flat platform remains beneath
it (five-metre forward edge); zero locomotion speed never triggers an automatic
ledge fall. Scheduled jumps retain the same finite-surface/contact/failure rules.
Local animation comes from the matching frozen neutral_idle.npz SHA256;
`export_idle.py` reproduces it. After a landing, the seeded zero-speed NN described
above takes over; this supersedes the original no-inference return behavior.

The earlier Idle-only bypass incorrectly hid controls and ignored markers; removed.
Tests cover standing/repeated/delayed jumps, indefinite idle without markers,
phase, airborne rotation, reverse seeking and shared control visibility, plus
original loop/grounding checks. Scene/refresh/run-pacing regressions also checked.
Visual verification remains unavailable.

## Named scenes and checkpoint - October 25

The header has a scene picker, **Copy**, and **Rename** after Refresh, with
**New scene** at the far top right. New scene creates a named, paused setup at
frame zero with just the original flat platform, default tuning/camera and one
default jump. It saves the outgoing scene first; it does not copy its layout or
jump schedule. The platform reset migration preserves this flat-only setup.
Existing single-scene saves become **Inclines** on first load. Copy asks for a
name and creates an independent paused copy of the current setup. Edit its
platforms and jump markers freely, then use the picker to return to the original.
Each scene keeps all tuning, platforms, jump markers, target, camera, playback
position and loop brackets. The existing Save/autosave now saves the library.
Switching saves outgoing work before loading the selected scene; the lightweight
page reload clears transform undo and pending animation work between scenes.
A failed save leaves the current scene open. No new server or inference process.

The library is local in ignored `state.json`, with active scene settings still
at the top level for compatibility. Back up that file to preserve all scenes.
`saved-profile.json` is the curated checkpoint of the user's current setup before
adding scenes; it is independent of subsequent edits to live state. To restore it,
close the lab page, copy it to `state.json`, then reopen the lab. This replaces the
live library, so retain a copy of `state.json` first if it contains other scenes.

21 scene checks cover fresh flat scenes, migration, independent edits, camera/playback round trips,
actual app copy/switch handlers, queued writes, cancellation and save failure.
Refresh14 and support-pacing24 also pass. Browser verification remains unavailable
(kernel-assets initialization error); existing controls retain their order.

## Pace the approaching foot for the moving pelvis - October 25

Foot cm/s now sets the maximum root-relative approach speed. If the planting
target is beyond the selected reach, the planner estimates its closing rate from
one frame of the existing incoming body motion. It spreads the available foot
travel inside the reach sphere over that predicted wait. The foot slows before
exhausting leg extension and can return to full speed as the target comes within
reach. Each planned advance also fits within remaining reach along its path.
Root-local carry, target construction, foot selection, capture distance and abort
rules remain as authored. There is no new option or pelvis/root movement rule.

The reported failure used Phase.30, Load50ms, Foot400cm/s, Reach.99 and markers
F53/F95/F125. Previously jump3 approached too quickly, reached full extension,
was carried through the incline and aborted at F136.75. With pacing all three
jumps succeed; jump3 captures at F137.25. Its maximum approach hip-to-ankle
distance is79.01cm against the80.63cm limit. This is a different setup from the
older Phase.61/F115/F146 sequence, whose misses remain valid.

24 pacing checks verify actual root-local travel <= configured speed, slowdown
before the reach limit, full-speed recovery, no sole penetration, fixed bone
lengths, reverse-seek determinism, immediate contact without delay and no launch
from a receding unreachable surface. Selection37, alignment36 and bounce140 also
pass. Three-jump preparation about120ms using cached NN data; no inference,
process or per-frame integration added. Existing Foot tooltip explains maximum
speed; supportHistory diagnostics include approachSpeedCmS, reachWait and
hipDistance. No control moved, tuning/marker/state changed, or Unreal work.
Refresh to load; visual QA remains unverified.

## Compare supporting feet after the cone pass - October 25

Per user clarification, both feet first constrain their ideal contact through
their own cone. Selection then compares current ankle to the planted ankle
position for that constrained contact, including the same shoe offset as before.
The metric is unchanged; only its target is corrected. Scores expose distance
(after cone), idealDistance, constrainedSurface and constrainedTarget. The phase
tooltip labels the post-cone distances. Ideal debug rings remain ideal rings.
The original ideal distance still drives approach rotation timing, so this change
does not independently retime that blend. No new eligibility rule or exception.

The reported F146/Load50 incoming pose is frozen in data/cone-choice-case.json
(5.5KB): L31.53cm versus R3.53cm after cone, selecting R. Before cone, the same
pose measured L47.47cm/R55.07cm. The frozen pose also verifies planner/query
agreement, immediate right-foot contact, bone lengths and continuous rotation.

Applying the rule to the whole saved sequence also chooses L on the FIRST jump:
post-cone L9.33cm/R37.87cm. It captures at F53 and changes the flight trajectory.
Consequently existing F115/F146 markers now miss with no ground in their cones.
The older all-three-success claims below describe the previous selection rule.
No markers, launch settings or saved state were changed to conceal this effect.

Selection37, contact alignment36 and bounce140 checks pass; JS syntax checked.
Unavailable equal-distance surfaces may tie as diagnostic miss labels; tests
verify such ordering cannot create a launch or alter root motion. Visual QA
unverified; refresh to load. No UI layout/new options, Unreal/training/server work.

## Penetration does not reject a support foot - October 25

Removed the unrequested5mm penetration cutoff from cone validity. There is no
replacement depth rejection. A foot below the plane uses its projected point;
finite platform bounds still apply. The existing sole-to-contact distance trigger
controls capture, independently of eligibility. Reach and closest-own-ideal
selection are unchanged.

Saved jump2/F115: R34.3cm versus L56.5cm from their ideals. R's lowest shoe corner
is9.5mm inside the nearby left incline; the old cutoff wrongly rejected it. R now
wins and captures immediately at F115, then loads/pushes. All three original
markers succeed. This supersedes the older assertion that L was correct on
jump2. The previous selection test enforced the bug; corrected tests check the
closer penetrated foot and absence of any depth cutoff, including beyond5cm.

Selection34, bounce148, alignment47 and contact40 checks pass; syntax checked.
The corner-contact rotation test now uses an explicitly banked fixture so later
arrival changes cannot silently remove its coverage. Refresh to load. No saved
settings/platforms/markers changed, no UI additions or Unreal/training activity.
User instruction: do not invent gates, fallbacks or exceptions; ask if ambiguous
and explain any proposed behavior change before implementing it.

## Centered gizmo and continuous contact alignment - October 25

Selecting a platform places the gizmo at the slab center, which is also the
rotation/scale pivot. Scale handles remain aligned with the rotated local axes.
A left drag that becomes an orbit clears selection, including a previously
selected platform. Actual pointer cancellation still restores the prior selection.
No timer or extra click is added; the existing four-pixel drag threshold remains.

Contact no longer freezes an unfinished shoe bank. A prepared contact trajectory
continues leveling the shoe's lateral axis to the surface through LOAD and PUSH,
preserving the pitch reached during approach. Heel-to-toe roll starts at PUSH at
the existing Foot roll speed. The solver rolls the displayed shoe boxes over their
supporting vertices, keeps the lowest geometry on the plane, and checks finite
surface contact. Loading uses that same moving ankle and its relative velocity;
the displayed IK is not a separate cosmetic adjustment. Rotation, ankle position,
root motion and leg lengths stay continuous across loading/push/release.
Alignment is automatic; no new option or UI rearrangement.

Both ideal targets now have equal-size rings: green selected, red other. A smaller
green ring/line marks actual contact. Hover the phase label for the two original
selection distances and eligibility. The old display compared green actual contact
with red ideal, which could look like the wrong choice. Before this edit, saved
jump3 correctly picked L50.1cm versus R60.4cm at selection time, both eligible.
The closest-eligible-own-ideal rule is retained; targets move during approach,
and the chosen foot is not repeatedly switched during that approach.

Verification:47 contact-alignment checks cover the original three markers,
surface clearance, both bone lengths, IK/physics agreement, phase continuity,
reverse seeks and existing roll speed including zero. Saved jump3 begins with
side dot normal0.731 and reaches0 before release. All original markers still
push floor/left/right. Bounce148, selection23, platform101, contact40, skew105,
arrow18 checks pass; JS syntax checked. Cached planning about50-70ms, no inference
or per-frame integration. Browser and desktop visual tools both fail with
kernel-assets os error3, so visual QA is unverified. Refresh to load; saved
settings/markers/platforms untouched. No Unreal/training changes or push.

## Joint surface and foot selection - October 25

Auto selection now evaluates the same foot/contact pair for both surface ranking
and support planning. Previously a platform was considered available when either
foot had a valid cone, but planning could then choose the other, invalid foot.
The saved jump2 picked the opposite/right incline on pelvis distance, then picked
L despite its cone being below that plane. This was a selection bug, not a need
to retime the marker.

Each finite surface builds both planted-foot ideal candidates with the actual
incoming velocity. Eligible candidates need a valid foot cone and a surface
within leg reach plus shoe clearance. Auto keeps the nearest-own-ideal foot among
eligible feet on that surface; surfaces rank by that foot's actual surface gap.
Pelvis distance breaks ties and provides the diagnostic fallback if none are
eligible. Explicit foot/surface choices remain honored. Distant slabs cannot
steal selection solely because a wide cone intersects them. Selection diagnostics
are exposed as surfaceChoices; no new UI or option.

Saved F115 now chooses L on the nearby left incline, gap23.0cm versus R/right
29.4cm. All three original markers succeed; the prior F114 workaround is no
longer required.23 focused selection checks, bounce148 and contact40 pass;
syntax checked, live browser visual QA unavailable. Refresh to load. No saved
marker/tuning/platform edits, new processes, Unreal/training work or push.

## Loading and rebound prototype - October 25

Implemented the proposed kinematic pelvis model in bounce.js. Two inputs are
appended after Translucency in More options: Load ms (default100, range0-300)
and Rebound % (default50, range0-100). Load0 preserves the previous authored
launch for comparison. Other values set spring response, not a mandatory delay:
little impact means little loading, and remaining leg reach can shorten it.
Edits use the existing preserve-playhead path; settings persist on refresh.

Contact starts LOAD with the incoming world velocity and gravity. A damped leg
spring compresses while the shoe stays pinned; the other limbs continue their
incoming animation. Extension starts PUSH, jump blending, heel-to-toe roll and
the three-frame direction arrow. Root/pelvis motion uses the loading/drive path
instead of adding it to the clip's root height. The active jump's energy comes
from the clip's ascent height; returned impact energy is added once, capped at
the active jump energy. Rebound0 absorbs impact but retains the active jump.

Preparation integrates loading at480Hz, then stores samples with continuous
position/velocity interpolation. The drive fits remaining leg travel and releases
at reach, finite contact loss or drive end; gravity and capped fall continue from
that exact position/velocity. Compression is bounded by leg geometry and surface
clearance, stiffness is bounded for numerical stability, and a lost contact cannot
manufacture a push. No new inference, worker, process or per-frame integration.
Animation matching/blend, busy marker intervals and air rotation use the delayed
push/release times. A no-drive release is reported as Miss, with no push arrow.

148 focused checks pass, including momentum continuity, compression/energy bounds,
flat/slope/wall plants, controls, reverse seeks, release/arrow timing, misses and
three successive bounces. Platform93, skew105 and arrow18 cover Load0 behavior;
refresh14 passes. Cached three-jump preparation measured about42ms. Live browser
visual verification remains unavailable; refresh to load.

Historical before the pair-selection fix above: original jump2 marker F115 missed.
Read-only trial at F114 (1.900s) makes all three markers succeed, with loading about
21/38/46ms. The pair-selection fix now makes original F115 work too. User marker
times, platforms and tuning were NOT overwritten. No
Unreal/training activity, server restart or push.

## Forward-facing plant on inclines - October 25

Plant orientation now uses the character's anatomical pelvis forward (-Y),
flattened to heading and then projected onto the contact surface. The former
root +Z assumption was valid for cached locomotion but became lateral after
jump sampling put the pelvis basis on the root. Pelvis lean no longer introduces
sideways yaw through slope projection. Plant pitch and heel-to-toe roll remain;
the roll axis is built from the corrected forward direction. This is separate
from alpha, which still follows incoming root velocity along the surface.

Saved frame151 / jump3 reproduced with alpha6, Foot400. Captured shoe heading
is now within2.28 degrees of intended forward (previously almost sideways).
58 heading/pitch/root-basis/roll checks pass, plus target71, contact39,
schedule136, cone88 and skew105. Browser visual QA unavailable. Refresh required;
saved tuning, platforms and marker times untouched. Actual contact time changes
as the correctly oriented shoe reaches the surface.

Historical proposal, now implemented above: capture previously removed incoming normal
velocity and immediately starts authored jump height. Proposed next step is a
deterministic pelvis spring/damper loading phase under momentum and gravity,
with the foot pinned, bounded leg compression and recoverable impact energy.
Jump animation and heel-to-toe push begin on extension, not first contact;
spring-driven root motion must replace, not add to, the existing launch trajectory.
Proposed compact controls: loading response time and rebound energy fraction,
appended at the bottom of More options.

## Inclined lead, alternative target and knee hinge - October 25

Lead alpha now multiplies the incoming world root velocity projected onto the
selected surface, divided by200. It no longer reconstructs velocity from root
facing and horizontal speed. Descent onto slopes contributes along the slope;
the prepared ideal remains root-local during approach and finite-ground clamped.
This supersedes the root-forward direction described in older entries below.
Alpha0 removes the lead; there is no foot-distance or foot-speed multiplier.

A red circle shows the other foot's ideal candidate on the active platform.
The green circle remains the selected foot's actual contact. The red candidate
uses the same root-local target as selection, follows approach, and freezes at
capture/abort. Auto still chooses the smaller ankle-to-own-ideal distance at
support start. Saved jump3 previously chose L:73.8cm versus R:77.6cm. Corrected
target/IK sequence chooses R:60.7cm versus L:63.9cm; marker timing is unchanged.

The knee uses its actual perpendicular bend direction carried with the pelvis
and transported with hip-to-target aim, replacing projection of a frozen world
hip-to-knee vector. Thigh and calf rotations share one hinge plane, preserving
segment lengths and removing independent twist. A compact F counter beside
playback seconds is zero-based at60Hz; time/rail/frame update before HUD throttling,
including immediate scrub previews, frame steps and refresh restoration.

Reproduced the saved frame149.71 focused target/hinge/readout checks, contact39,
schedule136, skew105, cone88, platform93, arrow18 and refresh14 pass. Test fixtures
use cached phase-bank data only. Live browser/GPU visual verification remains
unavailable. Refresh to load; no saved tuning/layout reset or Unreal/training work.

## Platform side translucency - October 25

Translucency % is appended at the bottom of More options, default80. It controls
platform side and underside faces only:0 is opaque,100 invisible. Walkable top
faces stay opaque from their front; their back faces and back-facing grid lines
are omitted so they do not obscure the agent through the underside. The local
top follows rotated platforms. Picking, collisions, support planning and saved
platform geometry are unchanged. Changing translucency redraws/saves without
replanning or moving/pausing playback.

Visible non-top faces render after opaque geometry, sorted far-to-near, with
alpha blending and depth testing but no depth writes. Opacity/blend/depth-write
state is restored before overlays. The small face queue and vertex buffer are
reused.25 focused render-routing/settings checks and93 platform checks pass;
syntax checked. Browser/GPU visual verification remains unavailable. Refresh
lab to load, preserving playback through the updated Refresh button.

## Refresh playback state and alpha step - October 25

The app Refresh button snapshots the playhead, playing/paused state, attack time,
current flip/twist and hit readout before pausing/saving/reloading. Startup restores
that snapshot after clips and flight are ready. Paused positions outside trim
remain outside trim; active playback resumes under normal trim rules. Pending
seek previews and delayed saves are cancelled before refresh. Settings/camera,
trim and speed persist as before. Runtime angles are saved separately from
starting angles to avoid adding the air rotation twice. Old saves without a
playback snapshot still load normally. Hidden tabs do not resume rendering.
This becomes active after the first reload of the new code; an already-open older
version cannot save a playhead it did not previously record.

Lead alpha's native numeric step is1, so Up/Down and spinner clicks change it by1;
fractional values remain directly editable. 14 focused refresh/restore checks and
syntax pass. Live visual QA unavailable. No live-state overwrite, server restart,
Unreal/training work or push.

## Anatomical foot plant and incoming velocity - October 25

Foot/toe up directions now use the rig's anatomical left/right axis signs.
The old world-Y sign choice flipped the foot frame after it crossed vertical,
so the saved third jump planted on the top (anatomical up dot normal=-0.959).
Plant alignment, surface queries and rendered boxes now share the same foot
frame; no world-up sign switch. Queries use all box corners to handle an airborne
inverted shoe. An inverted nearby contact is aligned sole-first before capture.
The isolated third-contact regression now has positive up dot normal=0.861.

Incoming velocity is projected onto the directions tangent to BOTH the actual
platform and the skewed push axis. This removes the normal component requested
by the user without reintroducing downward-to-sideways carry at100% Up skew.
This supersedes the earlier push-axis-only projection: tangential sliding within
the plane containing both normals is removed too; motion along their common
tangent survives. On flat ground /0% skew the normals coincide and ordinary
surface-tangent carry survives. Up skew controls the new authored push, while
physical contact and IK continue using the real platform.

Verified against saved setup: jump2 carries[0,0,5]m/s with zero surface-normal
component. Its changed flight makes the existing third marker miss (Distance
growing); marker times were preserved. 37 contact/render/orientation checks,
105 motion checks,136 schedule checks,93 platform and18 arrow checks pass.
The contact fixture uses cached phase banks only, no NN inference. Live browser
visual QA remains unavailable. Refresh required; no saved-state reset,
Unreal/training activity, server restart or push.

## Trim preview returns to playhead - October 25

Dragging either bracket still previews its boundary immediately. Release restores
the playhead saved at pointerdown while keeping the new trim range, even if that
playhead is outside it. Cancel/lost capture also restore the position; pending
preview frames are cancelled so they cannot overwrite the restored scene.
Playback remains paused as before. Seven focused handler checks and syntax pass.
Refresh the lab to load; no state reset or Unreal/training activity.

## Up skew affects takeoff momentum - October 25

Historical intermediate fix; superseded by the dual-normal cancellation above.

Fixed a mismatch: the jump impulse used the skewed direction, but retained
velocity was still projected onto the physical surface. Downward motion against
a45-degree slope could therefore add sideways motion even at100% Up skew.
Incoming velocity is now projected perpendicular to the effective push direction.
At100%, takeoff root/pelvis displacement matches flat ground for identical incoming
velocity and jump clip: horizontal momentum remains, vertical arrival velocity
is replaced by the authored jump. At0%, physical-normal behavior is unchanged.
Contact selection, foot placement and pinning still use the actual platform.

Reproduction before: incoming[0,-4,3]m/s on45-degree slope at100% yielded
[0.20,0.0661,0.30]m displacement after0.1s, versus flat[0,0.2661,0.30]m.
After the fix the slope matches the flat result (numerical noise below1e-8).
102 focused trajectory checks pass across left/right slopes, wall, rising/falling/
stationary approaches, retained horizontal momentum and three skew settings.
Arrow18 and platform93 checks also pass. Browser visual QA remains unavailable.
No saved settings/layout reset, inference, server restart or Unreal/training work.
Refresh the lab to use the corrected trajectory.

## Show jump direction - October 25

Show jump is appended after Cone in the viewport checkbox row, defaults off,
and persists with settings. Each successful push displays a large yellow1.4m
arrow from the supporting contact along the authored push direction (including
Up skew, excluding existing tangential motion). It lasts3 simulation frames at
60Hz /0.05s of playback time. Pause, speed changes, stepping, reverse seek and
looping therefore retain the same window; missed jumps show nothing. The arrow
is drawn through the body for readability, using a reused mesh only while visible.
No timers, extra playback loops, inference or replans are introduced by the toggle.
18 focused timing/direction/render checks and syntax pass; browser visual QA
remains unavailable. Refresh the lab and enable Show jump.

## Immediate click feedback without blocking camera drag - October 25

The user clarified that the delay meant elapsed click-to-gizmo time, not drag
distance. The gizmo now renders on pointer press, without waiting for release,
a timer, or a full scene redraw. This preview does not pause playback. Release
commits the click and pauses; dragging, cancellation or lost capture restores
the previous selection. A drag returning to its starting point is not a click.
The original4 CSS-pixel jitter allowance is restored; the earlier4-to1 reduction
addressed the wrong issue. Left-drag orbits over platforms without Alt. Gizmo
transforms, middle-pan and right-target drag retain their behavior.
93 focused checks and syntax pass, including immediate SVG output, no pause on
press, and actual camera handlers. Live visual QA remains unavailable; refresh
the lab to load. Saved tuning and platform layouts are unchanged.

## Distinct transform gizmos - October 25

Move (W) now uses large pointed arrowheads and a round center handle. Scale (R)
uses outlined square endpoints and a square center. Axis colors, orientation,
click targets and transform behavior are retained. This replaces the nearly
identical small circles/squares. Syntax and82 existing checks pass (Move render
assertions updated for arrowheads). Live visual QA remains unavailable due to
UI runtime initialization failure. Refresh the lab to load the new appearance.

## Platform keyboard focus and layout - October 25

W/E/R and Ctrl+Z now use the printed letter (KeyboardEvent.key), not physical
QWERTY positions. This fixes W being missed on AZERTY (physical KeyZ) and its
Ctrl+Z equivalent. Clicking the viewport or gizmo explicitly transfers focus to
the canvas, committing numeric edits and leaving dropdowns so their retained
focus cannot block transform shortcuts. Active text editing still keeps its keys.
The R scale gizmo remains local; W move and E rotate remain world-oriented.
82 focused checks pass, including rendered Move handles for QWERTY/AZERTY W and
actual focus-handler execution. Browser visual QA remains unavailable. Refresh
the lab to load this update; no layout reset or saved tuning changes this turn.

## Platform reset and transform undo - October 25

Requested reset restored the saved default floor and two 45-degree ramps. Other
settings, jump markers and camera were preserved and verified through /state
readback. The previous state is backed up in
Saved/BodyflipLab/platforms-before-reset-20261025.json (project-relative).
A one-time platformResetVersion migration also applies on startup so an old open
tab saving before Refresh cannot undo this requested reset. Subsequent layout
edits persist normally. Refresh the lab once to load the reset and new controls.

Ctrl+Z undoes one completed platform move, rotation or scale; up to100 operations
are kept in memory until reload. No-op/cancelled drags add no history. During a
drag, Ctrl+Z cancels that drag. Undo restores its gizmo anchor, previews immediately
and replans/saves once while retaining the playhead. It preserves later additions
and skips transforms of deleted platforms; add/delete themselves are not undo
operations. Writable fields and selects retain native editing shortcuts. No new
UI controls or rearrangement. 72 focused checks pass, including undo, reset
idempotence and input routing. Syntax checks pass. Browser visual verification
remains unavailable due to the UI runtime initialization error; no Unreal,
training, inference or server restart was needed.

## Platform editing, zoom and upward skew - October 25

+ Platform is below the phase label at viewport top left. It creates a 2m square
slab near the character and selects it. Click any existing platform to select it:
W is world-axis translation, E world-axis rotation, R local-axis scale.
Delete/Backspace removes the selection; text/number/select widgets retain their
editing keys. R no longer resets playback in Run/Walk mode. Escape cancels a
current drag, otherwise deselects. Gizmos anchor at the clicked point so even a
long ramp with its center behind the camera remains editable. Rotation and scale
use that point as pivot. The white center moves in the camera plane / scales
uniformly. Shift during rotation snaps to15 degrees. Left-drag orbits even over
geometry; the gizmo appears on press and the click commits on release.
Alt-left-drag also orbits. Existing inverted X/Y mapping is retained.

Dragging previews geometry immediately and pauses playback. Release rebuilds
support plans/collision slabs once, retaining the playhead, and saves the layout.
Existing floor and ramps become editable records on the first edit. Their
position, quaternion and dimensions persist with settings, including deletions
and an entirely empty scene. Initial locomotion remains on its authored path;
platform edits do not relocate the character. Scene queries and Jolt use the
same edited geometry. No platform queries or gizmo geometry run while unselected.

Wheel zoom-out no longer has the0.35 floor. The perspective far plane expands
with distance (near plane adapts for precision), so distant viewing is not cut
at60m. The existing close-zoom limit remains. Numerical underflow is rejected.

More options ends with Up skew %, default50. It rotates the authored push
vector from the surface normal toward world up by this fraction of the angle:
0 reproduces the previous normal push,50 gives45 degrees upward from a vertical
wall,100 gives a vertical push. Incoming velocity tangent to both the physical
platform and skewed push direction is retained (see the current correction above). Contact cones/heel roll use the
actual surface normal. Vertical-wall planting now handles root-forward being
parallel to the surface normal without a degenerate foot basis.

50 geometry/editor-event checks pass, including a real authored wall push at
45 degrees from rest, transform persistence, picking, drag/cancel/delete,
uncapped wheel zoom and retained camera axis signs. Existing136 schedule checks
pass with Up skew explicitly0 to retain their original reference trajectories;
19 marker-editor checks also pass. Receipt: platform-verification.json.
Browser visual verification remains blocked by the UI runtime's missing
kernel-assets path error. No live state overwrite, inference, Unreal work,
server restart or push. Refresh the lab to load these changes.

## Inclined surfaces and timed jumps - October 25

Two finite 45-degree ramps form a V beyond the runway edge. Each ramp is 6m
along its incline and 18m forward. More options ends with the 45-degree ramps
checkbox. Rendering, support queries and Jolt use the same oriented rectangles.
Cone clipping, foot clearance, plant rotation, contact markers and heel roll use
the selected surface normal. A small 5mm back-face tolerance retains existing
sub-millimetre gait sole penetration; deeper back-face contacts fail.

Jump markers now sit ON THE EXISTING playback rail. The only permanent new
control is + Jump, beside Loop at the start of the existing timeline. Its mouse
target matches the transport buttons. The far-right placement was rejected as
inconvenient: keep related mouse actions beside their working area. It adds support
preparation at the current playhead. Drag a numbered marker to move it; click it
for a small popover with exact seconds and Delete. Click away or Escape closes
that popover. No second playback bar, After, Gap, or permanent timing form.
Markers and trim brackets share the same time scale. Edits retain the playhead;
marker times snap to 1/60s. Up to 32 markers can be saved, including an empty
schedule. Existing Run/Early seeds the first marker until the schedule is edited;
Run duration still locates the runway edge.

Each marker begins support preparation along the incoming trajectory. Additional
jumps choose the nearest finite surface to the pelvis, preferring surfaces with
a valid foot cone; existing foot selection then applies. Contact still needs the
sole gate and leg reach. A successful slope push uses the animation ascent along
the surface normal, preserving incoming tangential velocity; gravity remains
world-vertical and capped. The character remains upright. A miss blends the leg
back onto the previous trajectory without adding root/pelvis lift. Overlapping
support/push markers report Busy and do not restart that push. No automatic
kinematic landing is added: pushes occur only from scheduled, valid contacts.

One cached 5s NN bank request supplies the gait; no live inference. Plans are
built on edits, with drag replanning debounced. Numerical checks cover both
slopes, exact sole contact throughout heel roll, three successful scheduled
pushes, misses, overlap, empty schedules, deterministic seeks and Jolt slab
recreation. UI event checks cover add/edit/drag/delete and popover dismissal.
136 motion/geometry checks and 19 control checks pass; existing cone88,
independent-blend33 and abort-pelvis36 checks also pass. Two-jump preparation
measured about19-31ms in Node (not a browser FPS claim). Receipts:
schedule-verification.json and jump-track-verification.json. Live visual
verification remains unavailable: both UI runtimes failed with the missing
kernel-assets path error. User's screenshot informed the simplification.
Saved tuning/camera were not overwritten; refresh the lab to load the changes.
No Unreal activity, training changes, server restart or Git push.

## October 27 approved checkpoint

The user approved the whole-leg viewer response and requested a push. This
checkpoint includes the Bodyflip work since October25: marker flip/pose timing,
Space gym and vanilla attacks, five matching spine colliders, attack pelvis
transfer/compensation, reference leg motion and the isolated whole-leg viewer.
The shared Foot IK surface/contact source and contract are included as runtime
dependencies. Other Foot IK UI/NN work, Unreal, training, live scenes, browser
state, screenshots and inference/model caches stay outside the checkpoint.

The whole-leg response remains viewer-only; the main lab retains the earlier
yaw response. Open `/soft-legs-preview.html` on the Bodyflip service to review
it. All sixteen small vanilla recordings and the idle recording are included;
the comparison needs no NN inference. The existing `saved-profile.json` is an
older curated scene, not a copy of today's live scene library. The current
desktop server remains API5; the source's API6/shared Foot IK activation still
needs a normal restart as documented above. No process was restarted for push.

## Git checkpoint and restore - October 24

The curated checkpoint includes app/server source, desktop shortcut scripts,
Jolt JS/WASM runtime and license, attack/jump recordings, all four locomotion
phase banks, verification scripts/receipts, and `saved-profile.json` containing
the saved tuning and camera at push time. Live `state.json` stays ignored.
On a fresh restore, copy `saved-profile.json` to `state.json` before opening the
lab; do not overwrite an existing profile unless you want that saved snapshot.

Playback requires Python 3 and Edge/Chrome; Unreal is not required. Initial
locomotion uses the included phase banks. Since the capsule-landing update,
preparing a landing also requires the existing Stepper/Torch runtime and frozen
models/seeds for actual NN continuation; Python alone is no longer sufficient
for the complete current sequence.
The desktop launcher currently expects the recorded Stepper Python path. If that
path is unavailable, run `python Labs/BodyflipLab/server.py --port 8876` from the
project root and open http://127.0.0.1:8876/ in a browser. Recreate the desktop
icon with `install_shortcut.ps1` after configuring that launcher path.

Original model copies and NPZ seeds, temporary Unreal export project, logs,
browser profile, snapshots and historical preview images are excluded. Model
provenance records their source paths/hashes; these external inputs and the
Stepper runtime are required for landing continuation and phase-bank regeneration.
The three policy checkpoints are already backed up under
`Tools/Recovery/Checkpoints/`; copy the matching hashes listed in
`models/provenance.json` into `models/run.pt`, `walk.pt` and `upper.pt` on restore.
The four NPZ seeds and original Stepper Python modules remain external dependencies.
Latest split-blend and foot-roll previews are retained as small review images.

## Cone-constrained sole target - October 25

Abort pelvis correction: saved Run Phase30%, Cone60 aborts at .904167s for
increasing sole/contact distance; it never receives jump root height. The previous
abort-to-fall blend nevertheless borrowed the fall clip's pelvis translation,
causing a7.24cm upward rebound around1.10-1.15s while the root was descending.
The failed-fall path now captures the displayed root-local pelvis at the ledge
(including any unfinished abort blend) and carries it along capped gravity.
Other joints still animate. This changes neither plant acceptance nor fall timing.
36 checks across Run/Walk failures and Body blend0/.2/.8 verify no upward pelvis
motion, edge continuity, limb animation and deterministic seeks. Saved settings
remain untouched. Receipts: miss-investigation.json (before),
abort-pelvis-verification.json (after).

The selected support foot now projects a cone from its lowest rendered sole
point toward the ground (opposite the outward surface normal). Where several
sole vertices share the minimum height, their contact-edge center is used.
More options / Cone is the half-angle, default30 degrees, range0-85. The contact
is the closest point to the existing ideal contact inside BOTH the cone and the
finite platform. No valid intersection means abort, rather than reaching outside
the cone to manufacture a contact. Foot selection, root-local ideal/Lead and
continued locomotion retain their existing rules. The cone follows the approaching
foot and shrinks as it nears the surface. Increasing sole-to-contact distance
still aborts; this now measures the sole instead of the ankle-to-Plant offset.

Gate now means lowest-sole-to-valid-ground distance, default5cm. It is evaluated
at support entry and every approach step; entering the gate starts PUSH directly
without waiting for the ideal ankle position or completed Plant rotation. The
remaining small gap is captured to the cone contact with IK, so the push is
grounded rather than pinning in midair. This deliberately permits a contact
correction within the gate (up to gap/cos(Cone) when the ideal is cone-clipped);
Foot speed bounds the approach before capture. Gate0 requests exact contact.
Existing leg reach remains required. Heel roll starts from the actual captured
foot angle and preserves the configured Roll speed and Toe-off limit.

Viewport Cone checkbox draws the live cone/footprint, pink ideal and green
chosen point (red for no intersection). It works before/during support and push,
and disappears after release/abort. Toggle only redraws/saves, without replanning;
debug queries/geometry are not evaluated when off. The later inclined-surface extension above adds oriented finite rectangles;
this section records the initial horizontal-platform version.

Reported Run Phase54% now jumps at .900s with no forward replant, versus .950s
previously. Phase67% remains airborne approach and jumps at .925s. 88 numerical
checks cover geometry, nearest-point selection, valid ground, zero Gate,
immediate launch, heel contact, seek determinism and debug origin; the33 independent
blend checks also pass. Browser fixture verify-cone.html is provided but NOT yet
executed: CUA failed to initialize twice (missing runtime path). Checkbox/angle
wiring was inspected statically; visual appearance remains unverified. Saved
state/camera untouched; no inference, Unreal activity or server restart.
Receipt: cone-verification.json. Earlier exact-contact/Plant-completion rules
below describe the previous version and are superseded by this sole gate.

## Independent body and support-leg blends - October 24

Sequence now has Body and Leg sliders (seconds, 0-1). Body starts at PUSH and
blends the other animated joints into the jump; pelvis remains procedural. Leg
starts when ground contact releases and blends live ground reach into the
supporting leg's animation, including Match foot timing when enabled. Neither
control changes the pin duration. Zero selects an immediate handoff.

Existing jumpBlend is retained as Body; missing legBlend inherits the saved
jumpBlend on load. Both therefore start at the user's prior value. Edits preserve
the playhead and save independently. Body blending is masked out of the support
chain even with Match foot disabled. The existing abort/fall blend is unchanged.
33 numerical checks verify independent joint motion, zero, migration and contact
timing; six browser checks verify editing, persistence and retained playhead.
Receipts: split-blend-verification.json, split-blend-browser-verification.json.

## Forward foot placement and adjustable roll - October 24

Support ankle/toe rotations now turn toward root-forward while the foot travels
to the target. More options contains Plant degrees (default10: heel up, negative
values lift toes), Toe-off degrees (default35 heel up), and Roll degrees/second
(default720, range0-3600). Zero speed holds the landing angle. The approach turns
with travel progress; Roll speed applies only during the grounded push.

Landing clearance uses the rotated foot and toe boxes. The actual sole contact,
including its offset from the ankle, must be on available ground; near an edge
this can move the ankle target back. Ground-sweeping rotation is adjusted during
approach without increasing ankle speed. Takeoff requires the final landing
orientation and real sole contact. Foot/toe local geometry is preserved.

The push rolls the rigid foot around the active sole contact instead of pinning
the ankle. Contact vertices transfer continuously across the sole outline; the
marker shows that contact. Angle advances at Roll speed up to Toe-off. The first
leg-reach or invalid-surface boundary releases the foot, even if the requested
angle is not reached. Release blend and frame matching use the final rolled
ankle/orientation. Existing pelvis trajectory, jump selection and cached NN stay.

Saved Phase67%, Foot500, Lead6: initial heel lift33.29 degrees, arrival10 degrees,
toe-off35 degrees; takeoff .945833s and pin .053026s at speed720. Speed360 reaches
27.19 degrees before reach release; speed180 reaches17.15 degrees. Some forced
late RunL plants now abort because the actual toe contact cannot fit before the
edge; do not weaken reach/abort to manufacture a push. Forced-foot comparison
fixtures use Early.3 to leave runway; user's Early.1 is retained.

Ten browser checks pass: speed edits change the displayed pose in21ms, keep
playback time, accept zero, and remain in collapsed More options. Saved settings
and camera restored after verification. `foot-roll-browser-verification.json`.

294 numerical checks cover both gaits/feet, signed landing angles, exact angular
rates including0, actual rendered sole contact, finite ground, pose continuity,
and seeking. Matching80 checks pass. The former fixed-ankle drift requirement is
superseded by rolling contact. No inference, Unreal work, or server restart.
Receipts: `foot-roll-verification.json`, `contact-verification.json`.

## Cached phase changes and real support contact - October 24

A previously unseen Phase/duration combination launched a fresh Python/PyTorch
worker, rebuilt the lower rollout, and reran upper inference. Measured Run43%
request: 4.553 s (2.545 s inference), versus .034 s when already cached. Multiple
edits could queue behind the server inference lock. This was a preparation stall,
not a phase control that did nothing.

`export_phase_bank.py` now prepares every discrete phase once, with the original
phase-specific warmup/seed, for Run/Walk and both equipment states. Single-thread
CPU export; no persistent inference process. Binary float32 banks cover the full
.1-5 s duration range and preserve Python's phase rounding and 100%=0 wrapping.
`run_bank.py` slices these files; server API4 never imports torch or launches a
worker for /run. Existing bounded four-entry caches remain. Re-export only when
the frozen source models/runtime change. The lower export horizon was extended
to cover the largest phase plus five seconds. Phase0/.44/.67 Run points and axes
match the old generated output exactly, including their original upper warmup.

The support gate is now necessary but not sufficient for takeoff: the rendered
sole must reach the floor too. Previously the ankle froze as soon as it came
within Gate, leaving up to that distance of air under the foot. Approach continues
at the requested speed with the root advancing; no final snap. Reach limits and
increasing-distance abort still apply. Current Phase67% / Foot500 had 4.837cm of
hover; contact now occurs at .925s rather than .9125s (12.5ms later), with under
.002mm sole error throughout PIN. After release the leg may lift normally.

End-to-end browser phase edits now take 11-30 ms (four phases), retaining the
playhead. API requests measured10-33ms for1s clips and63ms for5s Walk. All100
rollouts pass full-duration/finite/speed checks, all four default outputs match
exactly, and 100% wraps to0. Ten browser checks pass, including current saved
PIN. Receipts: `phase-bank-verification.json`, `phase-latency-verification.json`,
`fast-phase-browser-verification.json`, `contact-verification.json`. Four bank
files total18.4MB. Export worker exited; only Bodyflip server restarted (API4).

Nine contact cases cover both gaits, both feet/equipment and current saved setup,
using actual renderer boxes independently of the solver. Continuous takeoff,
fixed pin and approach speed checks pass, along with 80 matching and 162 support
checks. Saved tuning and camera are preserved. No Unreal/training changes.

## Playback timeline focus fix - October 24

The playback thumb no longer stops updating when the timeline retains focus
after scrubbing. Display synchronization follows simulation time regardless of
focus; live scrubbing still pauses and previews, and arrows still step frames.
Regression coverage added to `verify-timeline.html` for focused Space resume,
advancement, pause synchronization and arrow stepping. All 21 timeline checks
pass; receipt `timeline-focus-verification.json`. Saved state restored after
the check. No motion changes.

## Closest-foot frame and synchronized leg playback - October 24

Historical support-only timing below is superseded by Whole-body matched jump
at the top of this document.

Replaced the fixed-endpoint experiment with **Match foot** in More options,
enabled by default. Old endLeg settings are discarded; standing speed selection
and other tuning remain. At release, search the selected trimmed jump's 60 Hz
frames up to the fall transition for the closest support ankle in pelvis-local
space, using the actual hip socket. Equal matches prefer the nearest source time
to release. Search runs once during preparation, never each playback frame.

Support leg then plays actual source frames on its own clock:
`rate = (fallTransition - matchedTime) / (fallTransition - releaseTime)`.
An advanced match slows playback; a behind match speeds it up. Both clocks meet
at the same fall transition, then share the normal loop crossfade. The pelvis,
root and other joints keep their original timing. Existing Blend fades from live
reach into this retimed animation to avoid snapping when the nearest foot pose
is not an exact match. Zero Blend still requests an immediate handoff.

**Anim leg** shows the retimed target, not a fixed endpoint. More options displays
matched source time and rate; hover for remaining ankle mismatch. Current saved
Run R / Foot300 / alpha.03 matches .100 s versus release .034095 s, rate .965601x,
closest ankle gap12.76cm. This is a modest advance/slowdown, not a perfect match.
The long jump itself is not shortened; the leg now follows its motion instead of
interpolating slowly to one end pose. Unchecking Match foot restores normal timing.

80 numerical checks cover nearest-frame optimality, rate/deadline, sampled leg
rotations, unchanged other joints, ghost alignment, release/fall continuity and
seek determinism for Run/Walk, both feet and Run/Stand clips. Seven browser checks
pass for toggle, velocity selection and retained playback time. Legacy live-aim28
checks pass with matching off. Receipts: `match-leg-verification.json`,
`match-leg-browser-verification.json`. No NN/Unreal work or server restart.

## Earlier endpoint experiment (replaced above) / standing selection - October 24

Collapsed **More options** in Sequence contains two saved controls:
- **Stand / Walk**: standing-start cutoff as a fraction of Walk F speed (2 m/s).
  Default .5 selects Stand below 1 m/s; zero disables it. Compare horizontal
  root velocity around support contact, not mode name. Current Walk2 and Run5
  both remain Run-start at default; raising the ratio enables comparison.
- **End pose**: enabled for this experiment. After the ordinary reach-limited
  pin, interpolate support-leg local rotations directly from the released pose
  to a fixed endpoint. The endpoint is the last jump-only pose at loopStart,
  immediately before the fall-loop crossfade. Remaining angular distance over
  remaining time gives slower motion when already close. All four support joints
  reach that pose at the same authored time the rest of the jump reaches it.
  Existing initial body Blend still applies to other joints. Unchecking restores
  the live-IK-to-moving-animation blend over Blend seconds.

End-pose mode uses linear quaternion interpolation with a shared deadline,
not a chase of intermediate leg frames. Arrival is ~1.95 s (Run R) /2.05 s (Run L)
after jump starts. It does not increase ground pin time. Endpoint interpolation
follows pelvis/root heading and air rotation; only the initial pin is world-fixed.
The purple **Anim leg** ghost shows the fixed destination until arrival, then
resumes the current fall animation target. At the boundary the normal .25 s
fall-loop blend continues without a positional snap. Existing trim Out1.8 ends
before this endpoint in the default run, so extend the bracket to see arrival.

Standing L/R assets were sampled read-only to `data/jumps-standing.json`, with
source hashes. These are actual Relaxed Stand clips, trimmed by the same first
root-ascent rule: L .6667 s / R .6167 s. No synthetic symmetry was introduced.
No interactive editor was running; one headless null-RHI commandlet exported
both clips and exited successfully (0 errors/warnings). No asset saves or builds.
Reproduction: `export_standing_jump.py` (also usable via RunUnrealRemote).

69 focused endpoint/selection checks pass across both gaits, both support feet,
Run/Stand targets, synthetic low velocities, monotonic angular progress, exact
arrival, both boundary continuities and capped fall. Seven browser checks verify
collapsed controls, real Stand/Run selection, toggle and preserved time. Legacy
pelvis184 and live-aim28 checks pass with End pose disabled. Receipts:
`end-leg-verification.json`, `jump-options-browser-verification.json`.
Other saved settings/camera retained. No NN inference or server restart.

## Animation support-leg ghost - October 24

Viewport checkbox **Anim leg** shows a purple x-ray skeleton of the chosen
support leg's jump-animation target (hip/knee/ankle/toe), attached to the current
displayed pelvis. It excludes locomotion crossfade, support IK and release blend.
It follows the jump clip and later the transition to the prolonged-fall clip.
This is the animation destination, not the procedural reach or ground target.
Visible from jump start onward; absent before jumping, on abort and in Space.
Default off, saved independently of the existing whole-body Ghost. Toggle only
redraws/saves, without replanning or resetting playback. No target sampling while
off; lightweight leg overlay stays visible through the body.
16 numerical checks cover both feet/gaits, raw local target alignment, unchanged
input poses and differing IK-vs-animation feet; 3 browser checks confirm toggle,
unchanged time/pose and no runtime errors. Preview: `anim-leg-preview.png`.

## Live support aim through release - October 24

During RISE/BLEND the leg previously blended from a frozen root-local release
pose, so pelvis movement carried the leg away from its ground target. The blend
source is now a fresh two-bone IK solve from the current hip toward the original
planted ankle each sample, clamped to Reach. Solve after any air flip/twist so
the ground target remains world-fixed. Blend fades this live reach into the
animation over the existing duration; FREE remains fully animated.
The pin still releases at the reach boundary: out-of-reach feet aim toward the
target instead of stretching or claiming continued ground contact.

28 focused checks cover live target alignment, rejection of the frozen-pose
regression, leg lengths, Run/Walk, both feet and air rotation. At 50 ms into a
1 s diagnostic blend, unrotated aim errors are .07-.18 degrees versus 3.8-12.5
degrees for the old frozen direction. 184 pelvis and 162 support checks pass.
`release-aim-verification.json` records results. Settings unchanged; cached
motion only, no server/Unreal/NN restart.

## Procedural pelvis during jump - October 24

The pelvis is excluded from both the jump-start and prolonged-fall pose blends.
It keeps its takeoff root-local position and orientation while the root follows
jump height, forward travel and capped fall. Air flip/twist still rotate around
that procedural pelvis. The jump animation can no longer introduce a hip drop.

The supporting thigh/calf/foot/toe are excluded from the initial animation blend
while planted. The hip socket stays fixed relative to the pelvis; two-bone IK
owns the leg until the existing Reach boundary. At release the existing Blend
hands that leg back to local animation rotations. Other joints blend as before.
Locomotion, support approach and failure paths are unchanged. Current saved
Blend .08 and all other controls/camera are preserved. No new slider required.

Verification: 184 checks across Run/Walk, unarmed/drawn, L/R support and Blend
0/.08/.2/1; zero hip drop throughout the push, stable pelvis through ascent and
prolonged fall, pinned ankle/reach, continuous nonzero-blend release, and local
animation recovery. Existing 162 support and 15 walk checks also pass.
Receipts: `pelvis-verification.json`, `support-verification.json`.
Cached files only, no NN/Unreal processes or server restart.

## Walk + jump and run push timing - October 24

Sequence now offers Run + jump, Walk + jump and Space. Walk uses the frozen
Walk July5 latest lower checkpoint (8bae21c5b315), the existing Upper 82500,
and matching unarmed/drawn walking seeds. Actual NN forward speed is 2 m/s;
Run stays 5 m/s. Duration and Phase work for either gait; walking phase covers
29 policy samples (about .967 s, based on the accepted 57-game-tick stride).
Trim, frame keys, attacks, support pin/abort, fall and COM follow are shared.
No changes to jump timing or saved tuning. Internal mode `walk` persists.

Default one-second walk variants are cached on disk. Other durations/phases use
one transient, single-thread CPU worker, serialized by the existing lock; gait
is included in both caches. No GPU/training/editor work. Server API version 3.
Only the Bodyflip loopback server was restarted to load the route change.

Earlier measurement, before the procedural pelvis correction above: saved Foot300, alpha.03, Blend.2, Early.1, Phase0:
preparation starts at .900 s, root ascent at .9125 s, support releases at
1.02136 s. Approach .0125 s, pin .10886 s, then support-leg blend .2 s.
While root rises, blending into the authored jump pose lowers the support hip
from .861 m to .676 m over the first .1 s, causing knee flexion then extension
against the pinned foot. This is pose blending plus IK, not a physics delay.
The original .333 s source lead-in remains trimmed. At saved playback .3x,
pin plus leg blend occupies about 1.03 real seconds. `jump-timing.json` records
hip/root heights, knee flexion and timestamps. Behavior was explained, not retimed.

At saved Foot300, walk Auto/L misses contact and aborts as designed; R succeeds.
Walk Auto succeeds at the default Foot800. Tests preserve saved settings.
15 motion checks and 7 browser checks pass (`walk-verification.json`,
`walk-browser-verification.json`); API checks also covered Walk1.2/Phase.5 and
switching back to cached Run. Models/exports are contained in this lab.

## Alpha sensitivity corrected - October 24

Lead now uses `root forward speed * alpha / 200`, keeping the original
root-local support targets and finite-ground clamp. At 5 m/s, alpha 0.1 gives
2.5 mm, 0.5 gives 1.25 cm, and 1 gives 2.5 cm. Numeric settings are preserved.
The interrupted pelvis-anchor/extra-blue-marker changes were reverted: both
larger offsets had correctly saturated at the ledge; no target redesign was needed.
162 cached-run support checks pass, including alpha 0, 0.1, 0.5, 1 and 20.

## Root-speed lead and global frame keys â€” October 24

**Lead Î±** controls scaled root-speed lead: `local forward offset = root
speed Ã— alpha / 200`. At 5 m/s, alpha **4** gives **10 cm**. COM velocity, foot
distance and approach speed no longer influence the offset. Both feet get the
same forward shift; root heading carries it, and valid-ground projection still
limits the final target. Saved alpha values are preserved; input step is .01.

**Left / Right** pause and scrub backward / forward by exactly **1/60 s**,
including when a slider, selector, button, checkbox or trim bracket has focus.
Those widgets cannot consume any arrow key; Up/Down are reserved. A focused
writable text/number field, textarea or contenteditable area retains its arrows.
Held/repeated keys accumulate frames; rewind clamps at zero. Manual scrubbing
can inspect outside the trim range; Play and the Step button retain trim bounds.
Brackets remain draggable; arrows now scrub playback rather than moving them.

Verification: 152 motion/lead checks, six grounding checks and 43 browser checks
for controls, editable exceptions, repeats, exact frame times and lead invariance.
The 17 timeline checks also pass with bracket dragging, loop bounds and live scrub.
Receipts: `support-verification.json`, `ground-verification.json`,
`keys-verification.json`.

## Run height correction â€” October 24

Removed the erroneous **+5.5 cm root lift** applied to the entire run. The NN
gait is already ground-referenced. Run bone heights now match the source exactly;
normal airborne running phases remain. This is a constant-offset correction,
without per-frame ground snapping or changes to animation/IK settings.
`verify-ground.mjs` measures the actual renderer foot/toe boxes: six checks pass
for source heights, stance contact and retained airborne phases across both
cached runs. Stance gaps are within 3.1 mm; pre-existing interpolation dips up to
9.4 mm remain. The 144 support/abort checks also pass.

## Root-relative support approach and missed-edge abort â€” October 24

The ideal contact is now stored in the root frame at support preparation, before
the finite-ground clamp. Each authored substep carries it with the current root
and finds the closest valid ground point. The foot approaches in that same root
frame at **Foot cm/s**; its world velocity also includes root movement. Lead is
computed once from the preparation pose, avoiding feedback from the moving foot.
Only after contact is reached does the planted foot become fixed in world space.

Locomotion continues during approach: the old reachability-based body hold is
removed. Other limbs use the remaining cached run; after its endpoint, the last
pose continues forward at run speed. No additional NN inference is requested.

Every 240 Hz substep records the actual ankle-to-valid-target distance. The first
increase greater than 0.01 mm cancels the attempt (tiny tolerance for numerical
noise). Contact must still meet Gate and Reach before jumping. On failure, the
HUD shows **ABORT - RUN** until the ledge, then **ABORT - FALL**. IK blends out,
forward momentum continues, and gravity uses the existing fall-speed cap. No
jump-height animation runs on failure. Hover the phase for the failure reason
or current approach gap. Distance history is available in
`BodyflipLab.state.flight.supportHistory` with authored timestamps.

With zero lead, Foot300 / Early.10 launches at .9125 s after 6.25 cm of approach
travel. A zero-lead 10 cm/s case aborts at 1.0125 s as its gap grows. Other alpha
values use the new root-speed formula above. The fixed ledge and plant rules remain.
144 numerical and 27 browser support checks pass, including no hold, target projection,
per-tick distance history, first-increase abort, continuity and deterministic replay.

## Pelvis placement, foot speed units and orbit â€” October 24

The rendered pelvis box is centered between the two thigh sockets instead of
using the erroneous 7 cm downward offset from the pelvis bone. Its orientation
still follows the pelvis; skeleton, IK and physics bodies are unchanged.

**Foot cm/s** now uses centimetres per second: **800 means 8 m/s**. Approach
movement and lead prediction both convert to metres per second. The default
remains the displayed number 800. Earlier claims that 800 m/s was intentional
were wrong. The former unreachable-target wait is superseded by the moving-root
approach and explicit abort above. Current user tuning is preserved.
Alpha remains uncapped; contacts still clamp to the fixed ledge.

Left-button orbit now inverts vertical dragging. Horizontal orbit, middle-button
pan and right-button target dragging retain their controls. Verification:
122 numerical support, 22 browser support/orbit and 20 editing checks passed.

## Earlier jump, fixed ledge restored â€” October 24

The automatic ledge movement introduced during alpha troubleshooting is reverted.
The original edge is again `run speed Ã— Run seconds âˆ’ 0.12 m`, independent of alpha.
Alpha's agreed formula, acceptance of values above 1, and lead readout remain.
The previous tiny response came from the erroneous m/s interpretation, now corrected.

**Early s**, beside Run, starts support preparation earlier by that many authored
seconds. Default **0.10 s**; **0** restores the original timing. Run 1.00 / Early
0.10 samples the cached gait at 0.90 s, chooses support there, and waits for the
existing distance gate before root ascent. The default cached run now launches
after the foot approaches at 8 m/s. The ledge stays put, so preparation is farther back.
Early is limited to leave at least one 60 Hz frame of running. It does not bypass
reach or contact requirements; infeasible gait poses still wait for support.
Changing Early retains the playback time and reuses the prepared run without NN
inference. Click-away and Enter commits remain fixed.

## Editing at the current playback time â€” October 24

Clicking outside a number field, including on the 3D canvas, commits the edit and
removes its focus. Enter does the same. The canvas previously prevented the
browser's normal focus change, so pending values could remain unapplied.
Support controls, Early, Foot, Blend, Fall cap, Run and Phase rebuild at the current
timeline time instead of frame zero. Paused edits stay paused; support-number
edits made during playback resume from the same time. Cached support edits do
not request NN inference. Reset still explicitly returns to frame zero.

Alpha comparisons now show **Lead â€¦ cm** beside the selected support foot, with
requested/applied distances on hover and an **edge** suffix if limited. Actual contact clamps
to the restored fixed ledge. The agreed formula and leg-length limits are unchanged.

`editing-verification.json` covers commits, focus and retained playback time.
`support-verification.json` now has 144 checks including early timing, unchanged
ledge, root ascent, foot gate and the earlier support-motion checks.

## Procedural support foot â€” October 24

Kinematic remains selected. At Run minus Early, project the pelvis onto the
closest point of the finite platform. Project the left/right hip direction onto
that surface and place two ideal contacts at half the hip-to-hip distance on
either side. Auto picks the foot closest to its corresponding target; Foot L/R
overrides the choice and selects the matching trimmed jump clip.

Each target receives a root-local forward offset: `root speed Ã— Lead Î± / 200`.
Alpha / 200 is the lead time in seconds; foot distance, COM velocity and foot approach
speed do not enter that calculation. Targets are clamped back onto the actual
platform, including its edge. The ground query exposes a surface normal for a
later wall extension; this version supports the horizontal platform only.

| Control | Default | Meaning |
| --- | --- | --- |
| Reach | 0.99 | Maximum pinned hip-to-ankle distance as a fraction of thigh + calf length. |
| Gate cm | 5 | Maximum remaining foot-to-target distance before jump and plant. |
| Lead Î± | 1 | Scaled lead time (alpha / 200 seconds); no upper cap. At 5 m/s, 4 gives 10 cm. |
| Foot cm/s | 800 | Procedural approach speed, in centimetres per second (8 m/s). |

The former alpha cap of 10 is removed in both the number field and settings
validation. Larger values can be typed directly. The finite ground edge still
limits the actual contact, regardless of alpha.

The chosen foot approaches at the configured speed while the body advances.
The root-local ideal is reprojected onto valid ground during approach. The body
keeps moving even if contact becomes unreachable; an increasing gap aborts the
jump attempt and continues into a fall at the ledge. The ankle target accounts
for the displayed foot/toe sole clearance; the green ring marks the surface.

At the distance gate, plant **the reached foot position** without a last-frame
snap: the gate also permits up to that much contact gap. At the default speed
the foot approaches at most 3.33 cm per 240 Hz step relative to the root. Root ascent begins only when
the distance gate is met. The foot stays fixed in world space during **PUSH**, with a two-bone
knee solve preserving both segment lengths. At Reach, release it and blend its
local leg rotations back to the jump animation using the existing Blend duration.
Other limbs blend at the jump trigger. Optional Air flip begins after release.

Planning uses the cached run once on control changes; playback and random seeks
sample the same deterministic plan. No inference for support-control edits,
no background IK while paused, and no Unreal or training changes. Saved trim
brackets are preserved. `support-verification.json`: **144 checks**;
`support-browser-verification.json`: **27 checks** including both feet, Auto,
slow approach, abort/fall, distance history, exact kinematic poses and live scrubbing.
Run `node Labs/BodyflipLab/verify-support.mjs`, or open `verify-support.html`.
The old takeoff check entry points route to these replacement checks.

## Playback trim loop â€” October 24

The timeline leaves room on its right for **Speed**, a 0.1Ã—â€“2.0Ã— slider (default
1.0Ã—, saved). It changes the whole playback clock immediately without restarting
the sequence or preparing another NN run. Scrub times, trim brackets and Step
remain in authored seconds/frames. Fixed simulation steps and bounded frame work
remain; changing speed clears accumulated wall time to avoid a catch-up hitch.

The playback bar has draggable **[ / ] brackets directly on the timeline**, with
a highlighted range and a compact Loop checkbox next to transport. The separate
In/Out row and seconds fields were removed; the footer is back to 56 px. Hover or
focus a bracket to see its time. Drag the bracket to adjust its endpoint.
Home/End move a focused bracket to its allowed boundary; arrows scrub playback.
Bounds cannot cross. Existing saved ranges
are retained. This control applies to Run + jump; attack Loop remains independent.

**Dragging the playhead updates the Kinematic scene continuously before release.**
Bracket dragging also previews its endpoint. Input is coalesced to the newest
position once per animation frame; it does not queue NN requests or full replay.
Kinematic seeking directly samples the prepared sequence and flip/twist phase.
**Brackets always constrain playback**, even with Loop off: Play starts at In
when outside the range; reaching Out repeats with Loop on, or pauses with Loop
off. Moving a bracket automatically enables Loop. Step also respects Out. Each pass clears
transient attacks/hit state. Sim retains yielding reconstruction when selected.
Paused/hidden windows stop playback and hidden windows cancel pending preview.

`verify-timeline.html` / `timeline-verification.json` cover compact layout, live
input without a change/release event, newest-position wins, bracket adjustment,
range looping and kinematic membership. The old `verify-loop.html` entry redirects
to this replacement fixture; its old receipt is historical.

## Trimmed takeoff â€” earlier October 24 behavior

Kinematic remains selected and is now the fresh-settings default. Both authored
opposite-foot jump assets were already exported: **Lfoot** and **Rfoot**. They are
separate authored variants, not a newly synthesized mathematical mirror.

Both starts now skip **20 samples / 0.333 s** of preparation. Sampling begins at
the frame immediately before the first meaningful root ascent (5 mm threshold to
ignore export noise). Root height is rebased to that frame, so ascent starts as
soon as Run ends, without a vertical position jump. Apex is now **0.467 s (L)** or
**0.533 s (R)** after the run ends. The platform edge, fall-loop timing and optional
air-flip clock use this trimmed timeline. Blend still controls the run-to-jump pose
interpolation and does not delay the root ascent.

The earlier **Foot Auto** compared the final run pose's left ankle with the trimmed L start's
support ankle, and its right ankle with the trimmed R start's support ankle. It
chooses the smaller 3D distance in a common root-relative frame. Swing-leg/whole-leg
scores and the untrimmed first frames no longer affect selection. **L/R** remain
manual overrides. The status line shows the selected **L support / R support**.

`verify-takeoff.mjs` checks source trimming, immediate rise, blend continuity,
exact source rotations, both overrides, synthetic exact support matches and both
choices across real gait positions. Browser receipt: `takeoff-browser-verification.json`.
No NN inference, Unreal process, asset changes or simulation tuning needed.

## Tracking, kinematic comparison and responsiveness â€” October 24 correction

**Motion â†’ Sim / Kinematic** restarts the same sequence with the same decoded NN
segment. Kinematic presents the exact target transforms, without a physics solve
or collision response, and follows that pose's mass-weighted COM. Sim retains
physical joints/contact. Both work in Run + jump and Space. Ghost can also expose
the target during simulated playback. Space captures keydown **and** keyup before
buttons, checkboxes, sliders or selectors; holding it does not retrigger. Text
editing retains its normal keys.

The original Run + jump tracking was incorrect for the requested native contract:
it used spring constraint motors, which accumulated angular lag along the chain.
Sim now follows `ProphecyJoltVelocityServo.cpp`'s `CalculateRewrite` and
`PredictCommandFrame`: parent-first predicted angular endpoints, shortest-arc
rotation error divided by the substep, strength 1, and no extra stale target
feed-forward. Only the pelvis gets a positional velocity correction, gravity
compensation and body-origin â†’ COM velocity conversion. Dynamic-mode joint motors
are off; the constraints still enforce hinge/other limits and attachment. Original
Space-mode motors remain. Lab shapes/limits still differ from the native rig.

The same frozen one-second unarmed NN run, before â†’ after mean angular errors:
upper spine **28.10Â° â†’ 1.60Â°**, left hand **54.20Â° â†’ 6.17Â°**. Hinge/contact-limited
errors remain (left forearm mean **17.47Â°**); this is not perfect pose matching.
`inspect-tracking.mjs` and `tracking-before/after.json` retain the evidence.

The sword now caches its fixed geometry/normals and transforms each unique vertex
once per draw; GPU buffers reuse capacity. Source local transforms are cached for
sampling; jump-height derivatives no longer evaluate the whole skeleton. HUD text
updates at 10 Hz during play. Physics remains 240 Hz. Catch-up is bounded to three
60 Hz ticks per render callback. Decoded NN segments are cached in the browser,
so blend/foot/cap/reset changes reuse the existing segment. Equipment changes
prepare the matching unarmed/drawn segment. Timeline dragging previews the time;
release reconstructs simulation in short yielding batches so the UI stays usable.

Measured with `profile.html`, 60 frames after 10 warm-up frames at the same 1000Ã—700
viewport and sword selection: mean **22.40 â†’ 9.38 ms**, p95 **25.30 â†’ 12.80 ms**,
maximum **42.50 â†’ 14.90 ms**. This includes physics, rendering submission and test
diagnostics; it is a local measurement, not a GPU-present FPS guarantee. Cached
Reset measured **3.5 ms**. Paused/hidden behavior and transient NN workers remain.

`verify-comparison.html`: **27/27** focused checks (exact kinematic poses, COM,
Space ownership/repeat/release, dynamic membership, cached reset, yielding seek,
fall, Space mode and runtime errors). Real browser Space presses from a focused
Step button also toggled Play/Pause correctly. Updated twelve-second physics test:
max anchor **4.111 mm**, pelvis position **1.172 cm**, pelvis angle **19.05Â°**;
12 m/s cap respected. Previous 16/39 check receipts below describe the earlier
version; the sequence fixture now awaits asynchronous scrubbing.

## Run / jump / void â€” base October 24 implementation

The default **Run + jump** mode runs forward for **1 s**, blends into an actual
GASP running-jump start, follows its root's upward arc, and falls indefinitely
past a physical platform edge. The camera follows the **mass-weighted simulated
body COM**, including vertical motion. No ground exists below the platform.

| Control | Behavior |
| --- | --- |
| Run | 0.1â€“5 authored seconds; default 1. Releasing a sequence slider rebuilds the run at the current playback time. |
| Phase | 0â€“100% of a full forward-running stride (38 game ticks / 19 policy frames); 100% wraps to 0. |
| Blend | Run-to-jump pose interpolation, 0â€“1 s; default 0.2 s. Root rise remains authored. |
| Fall cap | Downward speed limit, 2â€“50 m/s; default 20. Also clamps actual mass-weighted body COM downward velocity. |
| Foot | Auto chooses the nearest procedural ground contact; L/R overrides. See support controls above. |
| Air flip | Off by default for reviewing the jump. When enabled, existing flip/twist clocks begin at physical lift-off. |
| Space | Select the original stationary, zero-gravity experiment. |
| Timeline | In Run + jump, pause and deterministically replay physics from the start to the requested time. |
| Target Reset | In Run + jump, bring the draggable target near the current pelvis. XYZ accepts positions beyond the original Â±5 m area. |

**Networks:** immutable copies of installed **Run 181751** and **Upper 82500**
PyTorch checkpoints, verified against their installation hashes. `locomotion.py`
uses the original Stepper encoder/decoder and real CPU network evaluation at
30 Hz. The lower network generates one continuous run; upper inference is
conditioned on that lower output, neutral gaze, and the selected attack's sword
equipment state at preparation. The lower has two seconds of settling; upper
has one stride of warm-up. Forward speed is the seed's **5 m/s**. Settings changes
request a finite NN segment, which the browser then feeds to Jolt at 240 Hz.
This is **not a recorded gallery loop**, and no network is retrained. It is also
not an online policy receiving physical feedback: recurrence uses accepted NN
poses. An uncached request starts a single-CPU worker which exits after preparing
the segment; the server retains at most four segments, not Torch or NN models.
Default 1 s / phase 0 unarmed and sword runs are already prepared. An uncached
request took 16.9 s under current laptop load; its cached repeat took 12 ms.
The idle server measured 18.5 MB. No inference runs while paused, and hiding the
window pauses playback. One worker at a time keeps preparation contained.

`models/provenance.json` records original checkpoint/seed paths and hashes.
The small frozen models and seeds are stored under `models/` (ignored by Git).
The existing local Stepper Python 3.10/Torch runtime and encoder/decoder sources
remain a read-only dependency; Python bytecode writes are disabled for that import.
The loopback server adds only `/run`, serialized in its own inference lock.
No training process, remote GPU, model pointer or installed Unreal model changes.

**Sim mode 0:** the journal's magnetization mode **0** is parent-relative;
mode 1 is world-relative. This lab implements that requested arrangement using
**25 dynamic Jolt bodies**, parent-relative angular velocity tracking, 24 physical joints, and one
world-space pelvis velocity servo. It reuses the native mode-0 control principle;
it does not load or claim exact tuning parity with the native Unreal adapter.
There are no independent limb position magnets. Gravity is 9.81 m/sÂ²; joint
limits, mass profile and motor strengths are the existing lab profile. Only reset
or explicit scrub reconstruction teleports the body. Ordinary play stays dynamic.
The descent cap applies a uniform linear velocity correction to all bodies,
preserving their relative velocities and angular motion.

**Jump sources:** `data/jumps.json` contains 60 Hz component-space samples and
source `.uasset` hashes for:

- `/Game/Characters/UEFN_Mannequin/Animations/Jump/M_Relaxed_Jump_F_Start_Run_Lfoot`
- `/Game/Characters/UEFN_Mannequin/Animations/Jump/M_Relaxed_Jump_F_Start_Run_Rfoot`
- `/Game/Characters/UEFN_Mannequin/Animations/Jump/M_Relaxed_Jump_Loop_Fall`

The original starts rise approximately **1.033 m** in root space. The current
trim removes their first 0.333 s; apex times are 0.467 s and 0.533 s after Run
ends. The platform edge and lift-off use the run boundary.
After the apex, a continuous ballistic trajectory takes over and reaches the
chosen terminal speed. The start pose crossfades into the fall loop over 0.25 s
near the end of the start clip. Both animations' root translation is removed
from the posed body before applying that one trajectory, so the fall loop's
authored downward translation is never added a second time.

Epic describes GASP as using motion matching and character state to choose
locomotion/jump/fall animation. This lab explicitly selects the three assets;
it does not recreate the whole GASP chooser/motion-matching graph.
[Official GASP documentation](https://dev.epicgames.com/documentation/unreal-engine/game-animation-sample-project-in-unreal-engine).

The Unreal editor was closed. Remote discovery was attempted without a live
node; `export_jump.py` sampled assets in a separate, content-only headless project,
with no gameplay C++ modules, PIE, build, or asset saves. Exported transforms and
source hashes are independently checked. The temporary project's dependency
loading also reported unrelated content/config diagnostics; those are not
gameplay-project build failures or claims that the entire content project validates.

`verify-flight.mjs`: 12 simulated seconds, root rise, indefinite descent, terminal
cap, finite poses, joints, and switching back to Space. Latest maximum anchor
error **4.111 mm**, pelvis target error **1.172 cm**, pelvis angular error **19.05Â°**,
12 m/s test cap respected to
float precision. `verify-sequence.html`: **16/16** browser integration checks,
including phase, duration, blend/scrub, COM camera, low cap, flips and airborne
attacks. `nn-verification.json` covers 0.1 and 5 s generation at endpoint phases.
Original 320-clip physics verification and **39/39** browser regressions also pass.
Test fixtures restore saved settings and must not run while the user edits the lab.

## Controls

| Control | Action |
| --- | --- |
| Flip grid | 12 directed horizontal axes, at 30-degree intervals. Back, Front, Left, Right and eight intermediate directions. Selection starts that flip at zero angle. |
| Flip Speed / Angle | Signed degrees per second; direct angle adjustment. Zero speed holds the flip. |
| Pelvis twist | Separate angle and signed speed around the pelvis's own vertical axis. This axis follows the flip. Zero clears only twist. |
| Attack / 01â€“20 | All 16 existing melee/sword families, with 20 variants each. |
| Attack / A | Start the selected attack and playback. Does not restart the flip. |
| Cancel / Loop / Rate | Return to idle, repeat attacks, or change attack playback rate independently of rotation. |
| Aim | Optional bounded joint aim correction toward the target. Slider controls its strength. |
| Right-drag | Move the target in the camera plane. Works anywhere in the viewport. |
| Shift + right-drag | Move the target along camera depth. XYZ and radius are also editable. |
| Left-drag / middle-drag / wheel | Orbit / pan / zoom. Double-click or View resets the camera. |
| Play / Space | Start or pause; ordinary playback flips the idle body until Attack is pressed. |
| Step / right arrow | Advance one 60 Hz authored tick, including four physics steps. |
| Reset / R | Stop, return to neutral angles/idle and retain speeds, target and selected attack. |
| Timeline | Pause and inspect an attack pose at the current flip/twist angles. |
| Ghost / Two-tone / Bones | Desired pose, the D/S limb orientation colors, or skeleton display. |
| Save / Refresh / Snapshot | Save settings, reload local code, or save the viewport PNG plus exact pose/settings JSON. |

The pale gold endpoint marks the active strike point. The target turns green on
a detected hit; **Miss** reports the closest surface separation for the current
attack. These are lab geometric measurements, not Unreal's Armed/Hit signals.

## Reuse and isolation

- `renderer.js` and `recovery.js` were copied from `Labs/SwordHolsterLab`.
  The renderer retains the D/S body, face, limb shading, camera math and WebGL
  geometry. Its camera pivot and camera basis export are the two base-renderer
  changes. `reuse.json` records original hashes.
- All 320 existing full-body attack recordings and the sword mesh were copied
  from `Labs/AttackRecoveryLab/data`; recorded clip hashes are checked unchanged.
  This lab samples and returns **every body joint**, including both legs.
- New UI, target handling, animation controller and physics live only here.
  There is no import of another lab's mutable state, shared server endpoint,
  native build, gameplay asset edit or training request. Jump assets were sampled
  read-only as described above.
- `state.json` and `snapshots/` belong only to this lab. Launching checks port
  ownership before opening. Browser profile: `%LOCALAPPDATA%/BodyflipLab`.
- Refresh is user-operated. Pausing/hidden tabs stop animation and physics;
  there is no polling, timer-driven skeleton work or cloud compute. NN inference
  occurs only when preparing an explicitly requested run segment.

## Physics and aiming

Jolt Physics JS **1.1.1**, single-thread WebAssembly, is vendored in `vendor/`.
The official npm tarball SHA-512 was verified. License and package/module hashes
are retained. Upstream: [JoltPhysics.js](https://github.com/jrouwe/JoltPhysics.js),
[constraint examples](https://github.com/jrouwe/JoltPhysics.js/blob/main/Examples/constraints.html).

In **Space** mode there are **25 rigid bodies and 24 real Jolt constraints**. The pelvis is
kinematic and rotates analytically at the requested speeds; the other 24 bodies
are dynamic. Knees and elbows use four limited Hinge constraints; the remaining
20 joints use limited SwingTwist constraints and position motors. Motors use
50 Hz critical damping and 2000 Nm caps. The neutral posture tracks the rotating
pelvis; it is not a rigid visual overlay of an unconstrained skeleton.

In **Space** mode gravity is zero, physics is 240 Hz, and pelvis position stays at `[0, 1.5, 0]` m.
The floor is a visual reference. Lab coordinates are X/Z horizontal and Y up.
Flip axes are fixed relative to the initial facing direction; positive Back
tips the torso backward. Twist is about the current pelvis local X bone axis
(its vertical axis), not a fixed world-up spin. Attack rate never retimes either
rotation controller. Physics updates and motor changes happen only when playing,
stepping, or explicitly reconstructing a paused pose.

The capsule geometry, masses, motor strengths, collision exclusions and angular
bounds form a **dedicated lab profile** around the shared idle pose. This is not
an exact import of the current game PHAT or its native Jolt DLL. Overlapping torso,
shoulder and adjacent-chain shapes are filtered; separate limbs still collide.
Knee bounds represent approximately 0â€“150 degrees of anatomical bend, relative
to the slightly bent idle reference. Elbows similarly allow 0â€“155 degrees.

Source clips drive local motor targets across the whole body, with the authored
pelvis rotation removed so it cannot change the chosen flip clock. Aim uses three
bounded CCD passes on the selected strike chain, with small distributed spine
correction for hand/head attacks and hip correction for kicks. The hinge axes are
never replaced by unconstrained knee/elbow rotations. The Jolt solver enforces
the physical joint limits. Aim is experimental steering, not a promise that an
arbitrary target is reachable during every flip phase. No NN was retrained.

The sword remains the existing hand-attached visual mesh; hit checking uses its
blade segment and swept endpoint. Melee uses the selected hand, foot or head
endpoint. The target is a movable non-blocking aiming marker, not an impact prop.
Hits include a 2.5 cm strike-point tolerance. Scrubbing reconstructs and settles
the requested constrained pose; it does not replay a recorded physics history.

## Verification

Run `node Labs/BodyflipLab/verify.mjs` from the project root. It checks all 320
source hashes and decodes, all 12 flip axes with independent twist, every attack
family through real Jolt, full-body return, aim response, finite poses, joint
anchors, knee/elbow limits and neutral tracking. The latest receipt is
`verification.json`. Initial final-profile run: maximum anchor separation
1.536 mm, hinge-bound excess 0.053 degrees; all checks passed.

Open `verify.html` and press Run checks for the separate browser fixture. It
exercises the production controls, 60-tick clock increments, grid switches,
right-drag/depth/orbit pointer handlers, all 16 attack selections, scrub and
cancel. It uses synthetic pointer events for deterministic dragging and restores
the saved settings afterward. Do not run it while another user edits this lab.
This fixture is separate from the normal application UI.

`install_shortcut.ps1` reinstalls the desktop shortcut with the local purple/orange
bodyflip icon. The launcher uses the existing Python 3.10 runtime and Edge or
Chrome. It does not start, close, build or save an Unreal project.
