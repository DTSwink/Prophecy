# Procedural sword holster

Implemented and saved October10 through Live Coding; no editor restart.
This supersedes the animation-driven proposal in SwordDrawingResearch.md.

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
