# Reach and grasp work — October 12

## Repeated D/S diagnosis — no D/S changes

Owned current-Blueprint captures, 1,200 absolute ticks each in Sim and Kinematic.
Four S/D cycles on left NPC `BP_ProphecyManualPoseAgent_C_2`; all three agents
recorded, including the possessed agent that remains stuck in reach. User
shrink20%, wiring, locomotion and settings preserved. Ended only owned PIE and
restored FPS. Evidence: `Saved/Diagnostics/ReachGrasp20261012/repeated-{sim,kin}.json`
and `*-boundaries.json`. `Tools/ReachGrasp/AnalyzeBoundaries.py` reproduces measures.

1. **Late S reach reverses in the commanded pose, not a physical tracking failure.**
   Second S, ticks363–366 moves +3.35,+3.18,+2.91,+2.73cm in pelvis-translation-relative
   X, then367–370 reverses -1.11,-1.23,-1.25,-1.37cm. Physical wrist rotation tracks
   command to .33→.11deg. Online ReachArm refits its destination every four slots,
   and every tick after its planned deadline; each destination is filtered across
   four ticks while the holster moves with gait. The lab plans against a known
   future recording. Refit/gait pursuit is implicated, but an exact matched-input
   replay has not yet separated each contribution. No damping fix justified.
2. **Additional S entry jump**, separate from the pre-slide complaint: first
   post-entry command steps4.41cm on first cycle,8.51/8.05/8.15cm later. Example380:
   (-6.09,-4.39,+4.01)cm versus previous(-.56,-.57,+.54)cm. Physical follows. Native
   switches from filtered reach destination to a new sliding guide/pole application.
   Kinematic later S entry peaks~3cm; physical arrival is later in Sim. This boundary
   needs exact captured-entry replay; it was not repaired.
3. **D release has a distinct physical kick.** At539 release, command1.41deg,
   physical8.29deg; at540 command4.11deg, physical28.88deg. Physical wrist already
   has ~11–14deg tracking error during sliding, grows18.05deg at539, then snaps
   toward command (6.74deg error540). Repeats25.63/28.88/31.07deg peaks on first
   three releases. Kinematic has no such excess; its command return still has
   ~6–9deg steps. The fixed grip's captured rest pose opposes authored wrist tracking
   during D sliding; removal exposes the error. Code captures D joint frames at
   grip and retains them while driving the sword. Strong timing/error evidence,
   not a joint-only A/B proof yet.
4. **Command-side D early return also differs from the restored lab.** Previously
   documented native60Hz versus lab240Hz held-arm return integration and release
   velocity sampling remain. This is distinct from the larger physical release
   kick and the later post-completion NN feedback fix.

No D/S solver, lab, profile, Blueprint or physics tuning edits in this diagnosis.
Do not describe either complaint as repaired. Existing evidence preserved.

## Research and chosen method

Primary references read:

- Meta [Hand Grab Interactions](https://developers.meta.com/vr/documentation/unity/unity-isdk-hand-grab-interaction/): palm grip offset and per-finger pose ownership.
- Meta [Custom Hand Grab Poses](https://developers.meta.com/vr/documentation/unreal/unreal-isdk-hand-grab-poses/): authored finger poses and pose debugging.
- Ultraleap [Physical Hands](https://docs.ultraleap.com/xr-and-tabletop/xr/unity/plugin/features/physical-hands.html): collider-based hand contact and multiple-joint considerations.
- Unity [dynamic attachment](https://docs.unity.cn/Packages/com.unity.xr.interaction.toolkit%403.0/api/UnityEngine.XR.Interaction.Toolkit.XRGrabInteractable.useDynamicAttach.html): preserve the actual acquisition pose.

Chosen prototype: original native DoubleReach body/arm math, contact-limited
open-to-closed finger rotation, and one fixed grip per hand. No Control Rig or
15-body finger simulation. Our engineering choice is informed by those systems;
it does not claim to reproduce their proprietary implementations.

## Implemented Blueprint nodes

`UProphecyReachLibrary`, categories **Prophecy → Reach / Grab**:

- **Reach Target:** Agent, Left/Right, world target transform, Max Reach Speed
  (cm/s); advanced Max Rotation Speed (deg/s). Persistent until changed/released.
  Calling the other hand enables both; repeated updates do not restart reaching.
- **Double Reach:** Off/Left/Right/Both, two world transforms and speed. Calls the
  original native body/arm solver directly, without a copied solver or Control Rig.
- **Grab Object:** primitive component, hand and speed; advanced optional world
  surface point and rotation speed. Without a point, chooses the closest simple
  collider point to the approaching palm.
- **Grab Bone:** skeletal mesh, bone name, world collider-surface point, hand and
  speeds. Stores point, normal and grip orientation in that bone's frame.
- **Release Grab:** one hand; **Stop Reaching:** both. Advanced Return Seconds=.25.
- **Get Grab Status:** active, gripped, physical grip, live surface point, commanded
  wrist distance and fitted contact-finger count. Distance is commanded wrist to
  target, not physical tracking error.
- **Set Reach Visualization:** toggles markers for an existing active reach;
  does not create or restart an action.

One update consumes 1/60 authored second, independent of wall-clock FPS. The
original solver supplies shared pelvis/spine/arm geometry and elbow filtering.
Each hand has speed-limited target pursuit. This is not a strict speed cap on
every physical joint after gait, body adjustment and contact response.

## Implementation decisions and corrections

1. Direct NN world/component pose consumers receive the native reach overlay.
   Upper feedback is retained while reach owns the pose. Inactive state exits
   before pose copies/solves; completion removes state. D/S has priority: admission
   during D/S fails and starting D/S cancels reach. No D/S behavior edits.
2. Fingers reuse the existing closed-fist retargeting convention, reference open
   pose and15 phalanges/hand. Simple collider probes stop each joint's curl, using
   12 bracket samples and6 refinements. This fits a pose rather than simulating
   individual fingers. Finger trials recompute only that finger and test only
   segments affected by the changing joint.
3. Fit once per grab, then close over .2 authored seconds once the wrist is close.
   Holding reuses fitted local rotations without recurring collision fitting.
4. Numerical checks caught the open thumb intersecting the sphere before curling.
   Admission now finds minimum outward clearance (bounded4cm,8 refinements)
   before fitting. Requested surface point stays unchanged. Failure to clear the
   open hand rejects admission rather than pretending it has a clean grasp.
5. Physical acquisition requires actual wrist within2cm/6deg of target, commanded
   wrist within1.25cm and finished closure. One fixed native joint captures the
   actual acquisition frames. Repeated requests reuse state and joint. Kinematic
   mode previews pose/grip state without a physical joint or parenting the object.
6. Coarse hand/forearm colliders initially knocked the balls away. Scoped contact
   rules now ignore only the selected target body against that hand and forearm.
   Other collisions remain. Release, invalid target, reset, mode changes, D/S
   interruption and EndPlay remove the owned joint and filter; no overwrite of
   existing collision preferences.
7. Releasing one hand gives that arm/fingers a parent-local FK return while the
   other holds. Full release returns the shared body too. Re-enabling seeds target,
   elbow and rotation from current physical pose, including mid-return. Retained
   body parameters follow full return progress. No restart on duplicate calls.
8. Reject invalid hand values, non-finite inputs, unsupported simple collision,
   missing bones and unavailable physical target bodies. Physical grabs require
   Jolt; Kinematic previews supported. Double Reach validates before mode changes.
9. Ordinary skeletal socket reads for non-physical finger bones were stale in this
   Jolt setup. Numerical inspector uses `SampleActualComponentPose`, reading the
   completed full skeleton used by the renderer. Python `fingers` socket arrays
   are not valid contact evidence; native CSVs are. Wrist/body queries agree.
10. All fixtures are temporary owned PIE actors and instance overrides. Swords and
    extra NN renderer hidden only during experiments. No fixture/wiring saved into
    TestNN. Editor remains open outside Play.

## Verification

Two native automation tests pass: `Prophecy.Reach.NativeKernel` and
`Prophecy.Reach.GrabGeometry`. Cover left/right/both, finite normalized output,
target pursuit speed, arm lengths, real reference/fist conversion, bounded curl,
component-local point transport and invalid admission. Receipt predates the later
implementation-only clearance/fitting patches; final live checks cover those.

Final evidence in `Saved/Diagnostics/ReachGrasp20261012/`:

| Capture | Result |
| --- | --- |
| `small-balls`, radius3cm Sim | Physical grips148/158, held to release350. Steady wrist error max .0184cm/.064deg. |
| `small-balls-kin` | Same148/158 grip ticks; wrist error <3e-7cm; no physical joints. |
| `balls-clearance60` / `balls-clearance20`, radius6cm | All331 captured ticks90–420 have identical commanded/physical hands and grip/release flags. |
| `head-clearance` | Another walking agent approaches; forehead surface grip186, holds to350. Steady wrist error max .0603cm/.056deg. |
| `lifecycle-final` | Duplicates, release-left/retain-right, reacquisition, full-return interruption, target destruction, mode change and reset clean up. |

Head point stayed bone-local across227 samples: max drift3.86e-14cm. Completed
finger poses track the fitted model: small balls max .016cm; head sample .092cm
during settling. Small-ball phalanx centres clear the collider by at least .717cm
at checked hold sample, versus .65cm probe radius. End segments also use intermediate
contact samples; this is not a proof of skin-mesh nonintersection for every asset.

World baseline8 generic joints/8 suppressed pairs; both grips10/12; left release9/10;
reacquisition never exceeds10 joints; target destruction clears its grip; mode/reset/
completion restore8/8. Counts include pre-existing world joints. Receipts:
`latest-validation.json`, `fps-parity.json`, `bone-local-point.json`, each `*-native/`.
`Tools/ReachGrasp/AnalyzeGrasp.py` reproduces summaries. Visuals: `small-balls.png`,
`balls-clearance60.png`, `head-clearance.png`.

An earlier surface below the chin **did not acquire**: actual wrist remained
~2.7cm/11deg from the authored target. The gate correctly refused a joint. Forehead
point succeeds without loosening acceptance or disabling other body collisions.
Failed captures remain, including bad test fixtures with changing facing and a
root-window move that did not durably relocate the target; not counted as passes.

## Performance and limits

Explicit live benchmark,1000 repetitions on the active fixture, warm assets:

- Pose read + native solve + publication: **.0135–.0185ms/agent** for two ball grips;
  .0111ms for the single head reach.
- One-hand reference conversion: **.065–.077ms**.
- One-time fitting: **.093–.119ms/sphere hand**, **.353ms/head collider**.
- Separate100-agent native solver-only test: initial .427–.438ms mean; later run
  during editor startup .855–.859ms. Easy reachable fixture, not whole-game cost.

Live benchmark excludes NN inference, physics, rendering, admission clearance,
first asset load and some controller bookkeeping. Not a measured100-agent live
grasp crowd; simultaneous admissions can accumulate a setup spike. No recurring
contact fit, Control Rig or individual finger rigidbodies were introduced.

Prototype limits:

- Sphere/capsule/box/convex simple collision. Triangle-mesh-only objects rejected.
  No force-closure analysis, grasp taxonomy or obstacle avoidance claimed.
- Reach-and-hold surface grasp; no separate carry/throw trajectory or Kinematic
  parenting. It follows the component/bone; Release destroys the physical grip.
- An obstructed/unreachable admitted target stays active until released/retargeted;
  Gripped remains false. No timeout teleports the hand into place.
- Requires the tested humanoid/fist references. Different skeletons, scaling held
  objects and arbitrary compound shapes require further fit checks.
- Concurrent attack/get-up/defense authoring has not been accepted. Only D/S
  priority and reset/mode/destruction cleanup explicitly handled. This is not a
  complete gameplay ownership system.
- No human motion-quality approval or universally natural grasping claim. Numerical
  traces and screenshots support these ball/head fixtures.

## Build/save state and replay

New-API normal build212s; test-enabled incremental37s. Later retained-return-state
normal build37s/final correction31s, within one additional restart. **Two necessary
editor restarts total.** Subsequent safe implementation patches use Live Coding,
successful reload/no object changes. **Editor25964 has latest code; normal DLLs
are stale and require a normal build before cold reopen.** Log `editor2.log` here.

Final postflight: PoseAgent, TestNN, A_Sword, SwordHolsterProfile and lab state
byte-identical to task preservation checkpoint; full BP graph identical, no dirty
packages. User pre-existing edits remain. No Git commit/push this task.

With normal editor open and no existing Play, run sequentially from project root:

```powershell
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/RunUnrealRemote.py Tools/ReachGrasp/Probe.py --name review-balls --kind balls --radius 3
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/RunUnrealRemote.py Tools/ReachGrasp/Probe.py --name review-head --kind head
```

Wait for each owned capture to finish before the next. Probe restores FPS, ends
only its own Play and never saves assets. Inspector/benchmark commands are explicit
development diagnostics, with no polling in normal gameplay.
