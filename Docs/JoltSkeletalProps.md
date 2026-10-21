# Directly placed skeletal mannequins

October20 user request: directly placed mannequins must use Jolt, including future
placements, without needing a Prophecy agent.

## Sword penetration repair — October20, installed

October21 follow-up: [Optimised sword cuts](OptimisedSwordCuts.md) is saved and
tested. It adds a separate three-row coupled slash plane/swing solve. The shared
explicitly enabled pike wrapper now also fully corrects its hard axial limit
inside existing position iterations; head-pike hilt error measured0.432mm.
Ordinary unmarked joints retain their solver. Final implementation patches are
loaded; normal DLLs require an incremental build before the next cold launch.

### October21 arm pike lateral motion — native opt-in node installed

Latest scene restore: user requested the original problematic arm-pike placement.
Restored A_Sword1 to (2007.955873660,172.688569383,171.148856237)cm in explosionVFX;
rotation/scale retained, mannequin already matched saved reference. Recovered exact
launch from15 matching precontact trajectory offsets and older saved map. Saved
map only; no Blueprint/tuning/correction toggle edits and no Play started. Reference
map was inspected without opening it, then temporary copy unloaded/deleted.
Receipt PikeSlide/restored-scene.json and Tools/SwordHolster/RestoreArmPikeScene.py.

**Current implementation — October21 coupled physical slider, verified:**
The unswept post-Step SetBodyPose projection is removed. The existing explicit
Set Pike Wound Correction node selects a native wrapper for that joint only.
Body A remains the simulated sword (UE component2); body B the wound. The two
transverse point-on-line rows and three angular rows share one 5x5 effective mass
matrix. Cholesky is computed at velocity setup and reused across normal velocity
iterations; normal position iterations recompute it and apply full hard-connector
correction. Jolt contacts solve afterward. Both bodies respond using their mass
and inertia. No post-step pose/velocity writer, mass conditioning, added global
iterations, extra physics steps, or collision-filter changes. Stock SixDOF still
handles Z travel limits/motor. Reaction forces include the custom row impulses,
so existing break thresholds remain connected. Drive-only updates preserve warm
starts; a frame/limit rebuild recreates the opted-in wrapper at reconciliation.
False restores the ordinary joint; broken/suspended joints retire normally.
Admission requires X/Y and all angular axes hard-locked, Z free/limited, a dynamic
sword, unrestricted dynamic body DOFs and solvable mass matrix. Unsupported native
admission retains the ordinary physical joint. Node return means opt-in accepted;
actual native admission happens at the shared-step boundary.

**Current user setting:** A_Sword's existing ProphecyPikeWoundCorrection.Enabled
checkbox is unlinked and FALSE. Preserve it; user has been told to tick it to try
the new solver. Existing temp-pike gate and entire Blueprint/map unchanged. The
two diagnostic runs only toggled transient Play joints. Post-restart graph audit
confirmed false, node wiring, absent Python preview and no dirty packages.

Actual restored arm scenario, identical15-frame precontact path, first cut
upperarm_l at0.26666665s,74 joint samples over the next1.2s:

| Mode | Peak sideways | RMS sideways | Peak orientation error |
|---|---:|---:|---:|
| Ordinary SixDOF | 52.2311mm | 23.3947mm | 44.3044deg |
| Coupled pike | 0.7513mm | 0.1194mm | 0.6846deg |

Both owned Play captures ended. This is the actual user geometry and launch,
not a different aim or higher-iteration test. Standalone Tools/Jolt/PikeJointLab
uses the installed pinned Jolt DLL and exact production block header. Comparisons
cover stock SixDOF, stock Slider, stock SixDOF with full positional correction and
coupled solver; masses2/10/50kg, offsets10/60cm, optional continuously pushed wall
and initial15rad/s spin. Stock Slider alone did not improve drift. Full positional
SixDOF helps but retains long-blade angular coupling error. Coupled wall trials
remain blocked; worst spin/wall transient is about3mm lateral error. Contacts
are allowed to leave residual joint error; no universal zero-error/collision
safety or production FPS claim. Tiny-fixture timings are not an Unreal benchmark.

Isolated native Prophecy.Jolt.Constraints.PikeWoundCorrection passed with no scene
Play: unchanged admission poses/velocities, actual solver alignment, static wound,
false/true, broken retirement and invalid-profile rejection. Existing Blueprint
reflection verified status3/native_properties0/pin_types0. User authorized restart
when memory constrained the Live build. No dirty packages at preservation; clean
Slate shutdown and normal build.30-action build had one PI namespace error;
5-action retry passed18.32s, normal DLLs current. Editor2612 reopened explosionVFX.
Saved map/A_Sword hashes identical. No asset saves, tuning or wiring changes.
Evidence Saved/Diagnostics/CoupledPike (~1.1MB): comparison.json, probe-off/coupled,
standalone case outputs, restart-preservation and verification receipt.
Tools/SwordHolster/TestCoupledPike.py, ProbeCoupledPike.py, AnalyzeCoupledPike.py.

Source: ProphecyJoltPikeJoint.h and native SetJointPikeWoundCorrection; runtime
Prepare configures the opted-in native joint, replacing the old post-step callback.
References: [Jolt slider docs](https://jrouwe.github.io/JoltPhysicsDocs/5.6.0/class_slider_constraint.html)
and [Chappuis constraint equations, section2.3](https://danielchappuis.ch/download/ConstraintsDerivationRigidBody3D.pdf).

The following prototype entries are historical and superseded by the native
coupled solver above. In particular, do not reinstall the Python teleport preview.

**Superseding user request: leave correction enabled.** Installed
ShowPikeWoundProjection.py --keep-enabled into current editor, including existing
Play without stopping it. It survives Stop/Play, clears/rebinds world references,
and has no expiry/no auto Play. Error still unregisters and writes receipt.
Same Python post-solve translation only; not yet native/packaged or editor-startup
installed. No BP/asset saves/build. User does not want one-shot rearming behavior.

Latest: user stopped the visual demo and requested watching the motion from its
beginning. `ShowPikeWoundProjection.py --arm` is armed for their next Play press;
does not auto-start Play. Wait expires after10min; runtime clock starts on Play.
Stop Play retires this one-session correction. Dirty A_Sword left untouched.

**User visual demo now running:** ShowPikeWoundProjection.py applies the same
lateral-only post-solve translation and leaves Play open for the user. First
cut0.266667,74 corrections/1.2s,max0.807332cm, normal iterations. No persistent
change/build/save. Callback retires when Play ends/world changes, on error, or
after10minutes; does not stop Play. Initial owned attempt failed before any
correction on nonexistent unreal.is_valid; ended that owned session and reran
successfully with SystemLibrary.is_valid. Current Play belongs to user inspection.
Receipt: Saved/Diagnostics/PikeSlide/show-wound-anchor.json.

**Later user wound-pivot steering:** iteration experiment rejected; removal found
no active Play, so overrides were already discarded. User's insight is valid:
angular error should not be allowed to pull the wound sideways off the blade.
Actual arm-side anchor equals stored localimpact, and native SixDOF's
GetPositionConstraintProperties uses p2 minus sword COM as its lever arm. There
is no explicit hilt hinge to relocate; finite solving leaves attachment error.
Also distinguish total orientation error from blade tilt: baseline44.304deg total
contains substantial rotation about blade Z; maximum blade-axis tilt14.850deg.
Higher-iteration capture maximum tilt4.980deg (total14.006deg).

Temporary `ProbePikeSlide.py --project-wound` trial projects only the sword's
translation perpendicular to current blade axis after each completed step. Uses
live arm anchor and sword frame, preserving sword orientation, axial coordinate
and native velocities. No angular snapping, iteration boost, target movement,
saved tuning or native production changes. Current standalone sword transform
adapter forwards the correction into Jolt. Same prefix through first cut as
baseline.74joint samples: maximum post-correction lateral residual3.915e-6cm,
RMS4.551e-7cm (zero by construction, not solver convergence); largest per-frame
translation0.8073cm. Max total rotation error21.768deg/RMS6.732deg. Owned Play
ended. This demonstrates the wound-line correction candidate, not a production
implementation, visual user acceptance, energy-conservation or cost guarantee.
Native version, if requested, should run before pose publication, be scoped to
the cut slider, preserve axial limits and retire with the cut. Evidence:
probe-wound-anchor.json and analysis.json; no build/restart or asset saves.

User subsequently requested a visual trial. `Tools/SwordHolster/ShowPikeIterations.py`
starts Play, applies the same10/32 override at first cut, then unregisters its
callback and leaves Play running for user inspection. Verified t0.266667 and
native10/32 log. No asset/camera/speed changes; stopping Play discards the override.
Do not stop this session on behalf of the user.

Current user's moved sword hits upperarm_l; two read-only owned Play captures
reproduce the symptom. EventGraph sets X/Y Locked, Z Limited, all angular axes
Locked, joint orientation from sword world rotation. Current runtime cut has
Z limit126.65139cm; local Pos2=(2.366886,3.693745,142.501398)cm. Both attachment
frames remain unchanged over74 joint samples (89 total game ticks,1.483s).
Initialization aligns to under a micrometre. Therefore this capture is not an
incorrect slide axis or repeated depth-function rebinding.

Measured locked-axis error grows to5.2231cm laterally and44.3044degrees angular.
Native GetCurrentTwist/Swing and ConstraintAudit confirm the same rotation error,
live Jolt ownership and force; this is actual native constraint drift, not just
render lag. First Hit creates a temporary Chaos component; next shared-step
admission retires Chaos and uses Jolt, as expected by the adapter.

Controlled comparison: after identical first-contact prefix, existing transient
ContactExperiment command sets victim rig constraints to10velocity/32position
iterations. Confirmed in native log; affects the connected island, not merely the
new cut joint. Peak lateral0.5496cm, RMS0.17225cm versus2.33947cm baseline;
peak angular14.0058deg, RMS3.69918deg versus23.59898deg baseline. This establishes
solver-convergence sensitivity, not an accepted fix or a performance measurement.
Transient settings disappeared when owned Play ended; no persistent tuning change.

Additional source gap: runtime profile has bEnableProjection=True,
ProjectionLinearAlpha=1, LinearTolerance=5cm, AngularAlpha=0,
AngularTolerance=180deg. ConstraintRuntime::Reconcile forwards limits/drives but
does not implement those Chaos projection settings (or mass conditioning).
Thus Blueprint projection currently provides no final sideways correction under
Jolt. Extra iterations alone remain imperfect and can affect the entire connected
island. A next fix should investigate scoped cut/slider correction at normal
budgets rather than silently increasing world iterations. No fix implemented here.

Tools: InspectPikeSlide.py, ProbePikeSlide.py [--iterations32], AnalyzePikeSlide.py
in Tools/SwordHolster (argument syntax is `--iterations 32`). Compact evidence in
Saved/Diagnostics/PikeSlide. No build, restart, graph edit, tuning save or asset
save. NS_bloodwound and explosionVFX were dirty on entry and were not edited or
saved by these scripts. Final remote check: owned Play ended, no dirty packages.

### October21 clean pike entry — installed and verified

Later same-day naming change: **Accept Pike Hit** now displays **Cancel Hit
Reaction**. Internal function remains AcceptPikeHit to preserve existing links.
Applied live via UFunction metadata, no restart/build, and updated the narrow
header DisplayName for future builds. Graph audit confirms the title; complete
live A_Sword exports hash-identical before/after, user's dirty BP left unsaved.
Normal DLL metadata still has the old label until the next normal build;
`Tools/SwordHolster/RenameHitReaction.py --apply` can reapply live if needed.
No behavior, pin, acceptance or joint changes.

User kept acceptance conditions in Blueprint and explicitly excluded joint changes.
The earlier pre-solver shared-predicate proposal below is superseded by a narrow
same-frame continuation. Arbitrary Blueprint conditions still execute synchronously
inside Jolt Event Hit on the game thread, after solving.

`Enable Clean Hit Continuation(Component, Enabled)` captures one start-of-step
body pose for each opted-in standalone component; wired once at A_Sword BeginPlay.
`Accept Pike Hit(Hit Receiver)` goes after the existing pike acceptance branch,
before creating its cut joint. It reconstructs this frame's collision-free end
pose from the captured start and incoming COM/angular velocity, then replaces
native pose, velocity and visible/query component transform together. Gravity and
damping already in the incoming sample are retained. CCD is covered explicitly:
Jolt rotates before sweeping, so advancing the rewound contact pose would rotate
twice. This implementation integrates from the actual captured start instead.

It leaves the struck body's solved response and all joint settings alone; this
is not a physics replay or a persistent no-reaction mode. Subsequent joint forces
remain normal. No extra physics step, trace, or per-frame world/body scan for
already-resolved enabled components. Disabled feature has only empty-map guards.

Supported scope: standalone dynamic receiver, one collision substep, no existing
joint/weld, one solved body pair this step. Refuses ambiguous multiple-body hits
instead of erasing unrelated collision response. `Accepted=false` and advanced
`Reason` explain refusal; the installed false branch does not create a pike cut.
Call synchronously within the matching Hit, before a Delay or joint creation.
Repeated accepted calls in that Hit are idempotent. Held/previously joined swords
are deliberately not supported by this narrow entry correction.

A_Sword preserves all24graphs/3,937 original pins and authored defaults. Four
added nodes, ten original link changes only. Accepted pikes bypass the old
SetWorldLocationAndRotation and later linear/angular velocity setters; the old
linear setter added incoming velocity to the bounced velocity, and the angular
setter interpreted radians as degrees. Slash path, thresholds, joint pins and
collision policy remain authored. Installer:
`Prophecy.Editor.RefreshHolsterGripPins CleanPike`,
`Tools/SwordHolster/InstallCleanPike.py`; native continuation is in
`Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltHitContinuation.inl`.

Validation: minimal normal build11actions/200.87s, UBA dynamic workers, passed.
`Prophecy.Jolt.HitEvents.CleanPike` and `SolvedImpulseAndLifetime` passed in
isolated NullRHI editor October21 06:53UTC. New coverage includes ordinary and
CCD free-flight pose/rotation/velocity equivalence, synchronous component update,
disabled/unaccepted paths, ambiguous collision and substep refusal, wrong receiver,
outside-Hit and duplicate calls. Actual unchanged explosionVFX launch accepted
pike at game time0.266667s. Incoming and final native velocities both exactly
(997.336864,0,-260.963416)cm/s; position continued forward at acceptance and on
following captured frames. Later joint reaction remains, as requested.

User map saved before required retained-state restart; its hash preserved through
installation. A_Sword compiled status3, graph-preservation check passed and saved.
Editor15456 reopened normally on explosionVFX, A_Sword editor opened, owned Play
ended, no dirty packages. Reflection native_properties0/pin_types0/status3.
Normal DLLs current. Compact receipts and prior-byte backup in
`Saved/Diagnostics/CleanPike`; owned Play probe is `Tools/SwordHolster/ProbeCleanPike.py`.

### Earlier October21 pike recoil audit — superseded proposal

Live A_Sword graph and native dispatch inspected read-only; no Play started or
physics/Blueprint changes made. Hit dispatch in CharacterWorldSubsystem follows
native Step and all client ConsumeCompletedJoltWorldStep calls. Event Hit then
reads Get Hit Pre Impact State, evaluates pike gates, teleports to extrapolated
pose, creates the cut joint and restores velocities. Thus acceptance currently
occurs after the blocking impulse and native pose publication. This establishes
late correction, not a measured attribution of each visible recoil frame.
Two concrete correction defects in the live graph: node105 Set Physics Linear
Velocity has bAddToCurrent=true; node103 Set Physics Angular Velocity in Degrees
receives current ang vel directly from the pre-impact getter's radians output.
Pike gates include normalized blade depth>.99, tip axial speed above the existing
impulse cut threshold (despite the name this is velocity), angle<80 degrees,
active/receiver filters and relative component speed>10.
Proposed: shared native acceptance predicate using current BP settings before
contact solving, per-contact sword-side response suppression only on accepted
pikes, deferred accepted-hit notification independent of solver impulse, and
existing cut lifecycle cleanup. Existing ScopedContacts already supports pair-
specific zero inverse mass/inertia. Must also account for the cut joint's later
reaction if the whole penetration should leave sword motion unaffected. A global
sword-no-reaction toggle would exceed requested scope. The implemented design
above instead preserves arbitrary Blueprint conditions and excludes joint changes.

### October20 skeletal penetration repair evidence

Read-only source/Blueprint audit and a four-second owned Play reproduced the
current explosionVFX sword/skeleton failure. No tuning, wiring or assets changed;
owned Play ended.

- The sword accepts the spine_03 contact: printed depth1.084014, pike accepted,
  type matter2. Its cuts array grows to one and creates
  NODE_AddPhysicsConstraintComponent-0. Roughly0.5s later it removes the cut.
- The native log explicitly rejects that constraint: `Body pelvis: Body has no
  native simulation-enabled primitive from which to capture its fixture collision
  policy.` ConstraintRuntime::BodyFor routes ordinary skeletal endpoints into
  ConstrainedSkeleton::BodyFor/Admit instead of checking the existing
  UProphecyJoltSkeletalPropComponent. That path attempts to recapture the already
  QueryOnly/non-Chaos mannequin, so no native cut joint is created.
- The Blueprint correctly changes the receiver to SLIDED_SKEL after accepting
  the cut. Source audit finds no live collision-policy forwarding in the passive
  prop binding: SceneCollision's skeletal branch admits/finds the binding then
  continues; Prop::Prepare updates kinematic targets only. Thus the existing
  rig retains its captured physical channel/responses, while Unreal's trace
  component displays the new ones.

Implemented in ConstraintRuntime, SkeletalPropComponent and SceneCollision:

- External constraints resolve an existing skeletal-prop binding before legacy
  ConstrainedSkeleton admission. Pending/failed bindings cannot fall through and
  create a second owner. Named endpoints use the original native bone handles.
- Collision-dirty updates forward object channel and combined body/component
  response filters to each existing native body. The response combination matches
  Unreal's minimum container rule. QueryOnly trace copies do not disable native
  simulation. No geometry, masses, joint tuning or agent behavior changes.
- Deferred admission refreshes the latest collision policy on completion.
  Existing scene change tracking is reused; no new recurring bone/world scan
  when policy is unchanged, and no retained native state/layout additions.

Validation: expanded `Prophecy.Jolt.SceneCollision.PlacedMannequin` passed
October20 12:59:04UTC with no warnings/errors: original floor/pose/late-spawn
coverage plus a blade joint to the original spine_03 handle, unchanged native
body count, channel-only updates, response updates on spine and pelvis,
restoration, QueryOnly preservation and joint teardown. Initial test-fixture run
incorrectly left the automatic blade adapter enabled in an explicit-step world;
fixed only the fixture before the passing rerun.

Final four-second owned explosionVFX Play: no native constraint-admission error,
nonzero joint force/torque, cut depth falls from near1 (tip) to0.6069916 (~39.3%
blade penetration), then returns past1 and the existing cut cleanup removes it.
This verifies penetration, not permanent sticking. The pre-existing Blueprint
cuts[0] access warning during removal remains; no user cleanup wiring changed.
Sword graph matches the pre-repair export after newline normalization. No assets
saved or tuning changed; owned Play ended, no dirty packages.

Build/load: safe Live Coding, three compile actions188.76s plus one fixture-only
action121.44s. First reload completed12:53:45UTC and logged RigVM MTAccessDetector
ensures during reference replacement (no crash); fixture reload12:58:45UTC
reported no object changes. Native reflection check: native_properties0,
pin_types0, status3, wiring_preserved1. Editor29912 remains open on explosionVFX.
**Normal DLLs remain stale: minimal normal build required before next cold launch.**
No restart needed or performed for this repair.

Evidence: `Saved/Diagnostics/SwordSkeletonPenetration` (pre-repair graph/state,
probe.json/probe-log.txt, probe-after.json/probe-after-log.txt, verification.json,
build.txt/build-test.txt); reproducible scripts in Tools/SwordHolster.

## Passive skeletal-prop binding

The existing default Jolt scene discovery now recognizes standalone
`ASkeletalMeshActor` components with a PHAT and physical collision enabled.
It attaches a transient `UProphecyJoltSkeletalPropComponent` at runtime. Actor,
mesh, material slots and saved map identity are preserved. Existing agents retain
their own character binding; no NN lane or physical-animation drive is added.

The binding captures the live PHAT geometry, joints, disabled pairs, materials,
mass, velocities and per-body simulation state. Chaos MACD is omitted, as with
agent swords; ordinary CCD remains captured. The native articulation participates
in the same per-world Jolt step as agents, weapons, props and the floor.
Unreal bodies become QueryOnly/non-simulating receivers for traces and blood
painting. Completed Jolt poses update both visible bones and query bodies.
Admission failure freezes the mannequin and reports an error rather than silently
continuing Chaos simulation.

Initial placement, later spawning and streamed-level discovery share the scene
queue. There is no added world-wide per-frame mannequin search. Native bindings
are retired on actor/component/world or scene-owner teardown.

This is a passive skeletal-prop binding: unmapped bones retain the captured pose,
and nonsimulating PHAT bodies follow the component transform. It does not run an
animation Blueprint alongside the ragdoll. QueryOnly/NoCollision decorations are
not made physical. Agents are unaffected.

The standard Blueprint physics dispatch now recognizes these bindings for
velocities, simulation state, forces, impulses and whole-component simulation
switches. Trace-only Chaos bodies are never used as a force fallback for an
existing skeletal-prop binding.

Build/test and editor state are recorded in the current ProjectJournal entry.
Compact preservation and test evidence:
`Saved/Diagnostics/PlacedMannequin20261020`.

Validation: six-action normal build succeeded in103.66s. Native test
`Prophecy.Jolt.SceneCollision.PlacedMannequin` passed October20 10:12:11UTC,
zero warnings/errors: real mannequin/floor contact, render/query pelvis alignment,
standard velocity dispatch, late discovery, .75 scale, destruction and zero leaked
bodies. Actual explosionVFX Play then showed one binding, native dynamic pelvis,
Chaos simulation=false and QueryOnly receivers across three consecutive frames.
The first live probe used a Python wrapper excluded by BlueprintInternalUseOnly;
rerun used reflected calls on the library CDO. No product repair/build was needed.
Owned Play ended; editor reopened with no dirty packages and saved Sword/map
hashes preserved.

