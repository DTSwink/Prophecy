# Procedural sword holster

Original implementation saved October10 through Live Coding; the current lab port below was subsequently rebuilt normally and verified in Play.
This supersedes the animation-driven proposal in SwordDrawingResearch.md.

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
