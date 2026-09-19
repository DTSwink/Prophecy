# Prophecy Project Journal

Current implementation and handoff — updated 2026-09-19.

Keep this journal about the finished current product: durable rules, accepted settings, authoritative paths, bounded validation and real remaining risks. Update the relevant section after each change; do not append turn-by-turn execution logs. Keep detailed evidence in topic documents. The [pre-tidy archive](Docs/Journal/ProjectJournal-history-through-2026-09-18.md) preserves all prior entries, including superseded behavior; it is not a current task queue.

## Working rules

- Follow the user's scope. Resolve routine implementation/build issues autonomously; ask about material behavior/design ambiguity. Do not begin unrelated optimization, benchmarks or extensive tests.
- Default to a successful compile and minimal meaningful checks. The user normally does extensive scene testing. Isolated tests do not establish scene quality or current packaged gameplay.
- **Blend/hold duration convention: 1 means60 unpaused game ticks, regardless of actual FPS or time dilation.** Do not substitute wall/game elapsed seconds or count30Hz NN evaluations as60Hz ticks. Inactive/finished features must not introduce recurring timer, interpolation, IK or extra-inference work. Scope: locomotion/recovery, tempering, physical-profile blends; [details](Docs/BlendTickTiming.md).
- Preserve user PIE, unsaved assets, scene transforms and Blueprint wiring. Do not save unrelated dirty assets or dismiss import/material dialogs on the user's behalf.
- **Use Live Coding for routine C++ changes. Never close/restart Unreal without user authorization.** Reflected changes alone do not justify a restart; new nodes can use separate Blueprint libraries.
- **Exception: do not Live-Code reflected changes to existing WorldSubsystem classes, especially ProphecyJoltWorldSubsystem.** This causes Ret->IsA during world creation. Add nodes in separate libraries.
- Reinstancing does not migrate retained non-UObject allocations. Preserve live layouts; adaptive-unity regrouping of nontrivial globals also needs care.
- Newly added cross-DLL symbols/classes may be unavailable through existing import libraries during Live Coding. Event-only reflected bridges are used where needed. Stale Python wrappers for new types are not grounds for a restart.
- Normal Editor builds: retain Live Coding support, use the normal target with -WaitMutex -NoHotReload, and omit -NoLiveCoding. Changing WITH_LIVE_CODING causes broad rebuilds.
- Include live patches/new libraries in the next planned normal build before relying on a fresh process. Do not restart merely to replace a working patch.
- When an authorized launch is needed, open **/Game/testNN** explicitly. Project-only startup opens heavy /Game/mybasic. Do not delete caches or change startup settings as a shortcut.
- Use apply_patch; preserve unrelated working-tree changes. Check local UE 5.7 source/supported APIs before inventing replacements for nontrivial engine behavior.
- If runtime evidence contradicts the model, investigate the exact symptom instead of stacking compensating patches.

## Project and Git

- Workspace: C:/Users/singerie/Documents/Unreal Projects/Prophecy. Project: GameAnimationSample3.uproject. UE: C:/Program Files/Epic Games/UE_5.7.
- Focused map: /Game/testNN; production map: /Game/mybasic; flat parity/audit map: /Game/locomotion.
- Main Blueprint: /Game/_mygame/locomotion/BP_ProphecyManualPoseAgent; native parent AProphecyAgent.
- Local simulation only; multiplayer and physics replication were explicitly excluded.
- Remote: https://github.com/DTSwink/Prophecy.git. Read actual branch/commit from Git; old recorded hashes are not current state.
- User has limited internet data: push only requested code/scripts/config and explicitly selected assets, not generated models, binaries or caches.
- **Do not re-enable Git LFS or trigger LFS transfers.** Preserve local pass-through overrides. ManualPoseAgent was requested as an ordinary Git file, not permission to push all assets.
- Preserve authored PHAT, accepted checkpoints, collider geometry and intentional per-agent drive differences. Do not change training/viewer behavior to hide a UE presentation issue.

## Accepted checkpoints and pose contract

**Accepted does not mean “best.”** Accepted Walk is July 5 fine-tune **_latest**: Use July 5 Walk Fine Tune = true; Use July 5 Walk Best Checkpoint = false.

- Run checkpoint: `C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260617_234645_ik_ik_full_RESUME_best47200_k32fixed_s05_rootaccelx01_i_e8b756b3\checkpoints\20260617_234645_ik_ik_full_RESUME_best47200_k32fixed_s05_rootaccelx01_i_e8b756b3_init.pt`, SHA-256 `CCC03FEE15E825EBCBCD24F9E71934D515B5133E760114ABE664445042D379C1`.
- Run ONNX: `Content/locomotion/NN/prophecy_lower_body_run_b100.onnx`, SHA-256 `75D9907B6FD62534CD4DC4FC7ED05C9E2DD32D1C173D4530044965887359C209`.
- Accepted Walk checkpoint: `C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260705_142401_ik_walk_finetune_legcap30_idlepin03_from_final\checkpoints\20260705_142401_ik_walk_finetune_legcap30_idlepin03_from_final_latest.pt`, SHA-256 `8BAE21C5B3159D69726CD98867C85000B51D566012708EED36374B2B5A9D4C79`.
- Accepted Walk ONNX: `Content/locomotion/NN/prophecy_lower_body_walk_july5_b100.onnx`, SHA-256 `549C1AC57971BE33AD72BB63EA5E9CA9D60E892027C3B5A8093479FB3A71949F`.
- Optional July 5 `_best` checkpoint: `C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260705_142401_ik_walk_finetune_legcap30_idlepin03_from_final\checkpoints\20260705_142401_ik_walk_finetune_legcap30_idlepin03_from_final_best.pt`, SHA-256 `860934962AD94894E5AF1262DD403D85DA46733E02A6BE4AFC09CF5E1197F64E`. Its ONNX is `Content/locomotion/NN/prophecy_lower_body_walk_july5_best_b100.onnx`, SHA-256 `F2122B104CA946F958C107BBF4967F0592AA94B7DC185AFA3807EEDF2981E30F`.
- Accepted Upper checkpoint (user-selected 2026-09-15): `C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260915_102838_ik_upper_cached_ae1ae4_bs64_allk32_ble_h66961999d3\checkpoints\20260915_102838_ik_upper_cached_ae1ae4_bs64_allk32_blend_noise50_initgaze50each_latest_download2.pt`, step `76,750`, SHA-256 `0597C163F93D447A40E970E0C757DB02E32CCD46C0154A3C037D01E9552B1C94`. Supersedes the August-16 checkpoint; this is the accepted selection, not a claim of best quality.
- Upper ONNX: `Content/locomotion/NN/prophecy_upper_body_b100.onnx`, SHA-256 `6FE1F1ED3D3633D2C9FB4FB6F466F916031FCCC66FFEBF78D2479741FA7B8D4F`; runtime contract: `Content/locomotion/NN/prophecy_upper_body_runtime.json`; exporter: `Tools/NN/ExportProphecyUpperBodyPolicy.py` (default updated to the selected September-15 checkpoint).
- Accepted Dodge upper: C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/dodge_step_205525.pt, SHA-256 256035eb190f0b2d683ea8089b3232936ee7cc93ec4d69aef6034b12a38aafb1. Installed prophecy_dodge_upper.onnx SHA-256 385dc27e5f847bc38c7bd695eae834b1544353d6f639f36e04873bb3606357ba. Frozen lower weights/contracts unchanged. Provenance: Content/locomotion/NN/defense/dodge_checkpoint.json; installer: Tools/NN/InstallDodgeCheckpoint.py. Old 198044 fixtures are original-port references, not current weights.
- Policy cadence is 30 Hz. Root, visible mesh and physical targets share completed-sample interpolation/accumulator phase, including slow frames. Explicit interpolation=false remains an exact-pose override.
- Default interpolation remains Current (Linear / Viewer Rotation); bounded Hermite positions / SLERP rotations is optional.
- Upper is the cached-lower 281-input/90-output policy. Lower owns pelvis/legs; upper predicts its delta; arms resolve through two-bone IK. Sword input comes from the actual held sword.
- Upper startup uses authored M_Neutral_Stand_Idle_Loop frame 0 transported through the lower pelvis.
- Parity requires identical primers, checkpoints, root windows, timing and geometry. The corrected Armed-aligned reference supersedes the early Hook L viewer diagnosis.
- Fixed whole-game 60 Hz configuration is separate from 30 Hz inference; lower rendered FPS can slow gameplay under that configuration. Do not silently change project timing.

References: [interpolation](Docs/NNInterpolationModes.md), [idle initialization](Docs/UpperIdleInitialization.md), [Dodge mismatch evidence](Docs/DodgeHookLViewerMismatch.md).

## Attacks and defense

- Attack-to-locomotion checkpoint recovery starts at100% Run, optionally holds it, then smoothstep blends to Walk over1second by default. `Set Attack To Locomotion Blend(Agent, Duration Seconds, Hold Duration Seconds)` configures the next handoff per agent; Hold defaults0 so existing calls are unchanged. Duration0 disables the entire recovery including hold, preserving ordinary selection without extra inference; it also cancels an active mixture on the next policy step. Positive timing overrides ordinary walk/run intent and speed selection until the walk endpoint. Hold uses only Run inference; only the blend requires both checkpoints. Uses the complete lower-body mixture including pelvis, pinning, published weights and upper conditioning. Full/half attack finish or cancellation into locomotion starts recovery; direct replacements do not. New attacks/active defenses/reset cancel it. Movement input/root speed unchanged. See [AttackControls](Docs/AttackControls.md).
- BP_ProphecyManualPoseAgent class defaults contain three populated Name arrays (saved 2026-09-18): attack list = all 16 supported families; melee list = jabL/R, hookL/R, overL/R, headbutt, kickL/R (9); slash list = slashL/R, slashLD/RD, slashLU/RU, plus pike (7). Verified against the runtime family catalog and after Blueprint compilation; no graph wiring or map save. Backup/result: Saved/Diagnostics/AttackLists/20260918-111537.
- Before attacker Armed, queued parry/dodge leaves the defender free to locomote or attack. Current history capture permits the first defense output **on Armed**; the old one-step-later implementation is superseded.
- Both defenses retain locomotion input/facing, mover, magic velocities and root controls. Dodge composes its learned root correction once with the planned window.
- Parry ends on first latched attacker Hit. Dodge ends X policy frames after Hit, default X = 1, adjustable in BP. Explicit stop/replacement/duration/failure cleanup remain.
- Automatic contact-based defense stopping is for **Kinematic defenders only**. Sim/HalfSim stop-on-hit is user Blueprint gameplay.
- Termination queries use actual PHAT/sword shapes, never enlarged training boxes. NN conditioning geometry retains the training contract. Parry Blocker/selected-arm input and its downstream classification were removed.
- Set NN Attack Target changes aim without resetting frame/history/latches. Trigger NN Attack has optional Victim; unplugged means no targeted agent. Defense-state queries include accepted pre-Armed waiting responses.
- **Set Attack Return To Root Balancing(Agent, Use Root Balancing Target=true)** chooses attack-to-locomotion root placement per agent. Default/no call uses the flat feet midpoint; false preserves placement directly below the pelvis. Simulated body positions take priority over visible kinematic bones; root height stays unchanged. Selection and target sampling run only at handoff, without Tick/timer overhead and independently of balancing enable/thresholds. Parry/dodge keep their feet midpoint. Both choices preserve world pose, shift the whole root window and reset the registered magic cube to the root. Direct replacements and unactivated cancellations retain their continuity rules. See [AttackControls](Docs/AttackControls.md).
- Sword collision is suppressed at attack start. Slash/pike restore it on first Armed; melee (punch/kick/headbutt) restores it on first learned Hit (>0.5), including recovery animation. Restoration is latched for the episode. End/cancel/interruption also restores saved responses. Owner exclusions remain separate; this is NN Hit, not a physics Event Hit. Installed via Live Coding 2026-09-19; AttackCollisionPhases passed (UE/native filters, simulated/attached/kinematic swords, lifecycle and stable bodies/joints). No restart or Blueprint/map edits.
- Get NN Attack Colliders returns attack name and striking PHAT bones: punch hand/lowerarm; kick calf/foot plus ball only if separate; headbutt head; slash/pike sword component only. Available before Armed.
- Attack Initialization Mode: Dynamic is default. Static duplicates current lower/upper frames into previous once at attack start, including chains. Subsequent inference is normal; half attacks retain GT ghost placement.
- Independent parry/dodge calf/foot/forearm/hand clamps coexist with attack/locomotion controls.
- KinematicAttackDefenseDemo retains role reversal, interval and parry/dodge selection. Preserve current scene wiring and input debugging; do not reinstall it without a request.

References: [live defense](Docs/LiveDefenseControls.md), [NN defense](Docs/NNDefense.md), [attack controls](Docs/AttackControls.md), [sword phases](Docs/SwordAttackCollision.md), [demo](Docs/KinematicCombatDemo.md), [half attacks](Docs/HalfAttackGTInitialization.md).

## Jolt sweeps, collision and hits

- **Automatic PHAT sweeps equal Enabled = true, Strength = 1, Max Iterations = 64**, unless overridden per agent.
- Active during attacks (including preparation) and actual parry/dodge checkpoint control. Queued defense waiting for Armed and locomotion alone do not activate them.
- Independent attack/defense flags OR together; ending one cannot disable the other. Defense release/stop and world cleanup remove activation.
- Set Jolt PHAT Sweeps configures permission/tuning for both. Enabled=false or Strength=0 opts out. Enabled=true while idle stores configuration without running sweeps.
- The setter needs its white execution input wired. Self alone does not call it. No setter is needed for automatic defaults.
- Get Jolt PHAT Sweeps reports effective activation and retained tuning. Strength 0–1; iterations 1–128. The setter's Enabled pin default false is distinct from automatic defaults when no override exists.
- Registered PhysicalMesh PHAT bodies, including welded sword, predict translation/rotation after servo writes. Filters remain; response uses normal impulses weighted by mass/inertia. Pairs selected by both agents are processed once.
- This does not enable CCD or alter global substeps. Existing overlaps and subsequent joint solving can still permit penetration; no perfect-contact guarantee.
- Dormant path has empty-registry guards, no shape queries/body scans/history capture. Enabled cost has not been benchmarked.
- Focused activation/contact tests passed 2026-09-18 08:02:52 UTC: defense defaults, disable/zero, overlapping ownership, cleanup, fast crossing, rotation-only contact and momentum. Latest defense change was not a new current-scene contact capture.
- Set/Get Jolt Collision Substeps is a **world-wide minimum**, last writer wins; optional default off, Substeps pin 2, range 1–16. It preserves higher project-required counts.
- Set/Get Jolt Penetration Slop is shared-world; default 2 cm, nonnegative. Temporary 0.1 cm reduced measured blade penetration but was not made the production default.
- Generic Jolt PhysicalMesh hit notifications include self-collisions. **Inspected BP diagnosis:** OtherComp == Other.PhysicalMesh and Other.State == Attacking also pass for an attacker's self-contact. Add **Other != Self** to the AND. This was graph/code analysis, not a runtime pair trace; no BP wiring was changed.
- Standard PhysicalMesh Add Force / Add Torque in Radians with Bone Name route to individual Jolt bodies.
- Per-limb channel/response overrides remember original filters, restore them during attacks/parry/dodge, and reapply locomotion overrides afterward.
- Plain scene/runtime mesh integration has its documented admission rules; do not assume every unrelated Chaos component automatically participates.

References: [sweeps](Docs/JoltPHATSweeps.md), [substeps](Docs/JoltCollisionSubsteps.md), [slop](Docs/JoltPenetrationSlop.md), [hit events](Docs/JoltPhysicalHitEvents.md), [default meshes](Docs/JoltDefaultMeshes.md), [runtime meshes](Docs/JoltRuntimeStaticMeshes.md), [channels](Docs/JoltRuntimeCollisionChannels.md), [integration status](Docs/JoltIntegrationStatus.md).

## Magnetization, feedback and snapshots

- `Print Physical Bone Profiles` is an on-demand Blueprint debug node. It prints each unique PHAT bone as `bone : L=mag A=mag / L=tolerance cm A=tolerance deg`, in stable reference-pose height order (head at top, feet at bottom). Reads currently applied blend/context values; magnetization includes global scales and becomes0 when disabled. Unsupported feedback bones show `n/a`. One keyed block per agent refreshes on Tick; Duration0 is one-frame display, increase for one-shot calls. No automatic tick, profile mutation or work when disconnected; omitted in Shipping/Test builds.
- Print-node validation: Live Coding succeeded2026-09-19; reflected call on the current editor agent returned22 unique PHAT rows, head first/foot_r last; null-agent call returned empty. No PIE, restart, Blueprint rewiring or scene edits.

- Single/Below Set and Blend nodes support Locomotion = Both/Walk/Run and Equipment = Both/Drawn/Sheathed. Existing defaults are Both/Both.
- Four context cells preserve combinations. Actual checkpoint weights blend walk/run; held sword selects equipment. Last writer changes selected cells.
- Attacks temporarily use enabled magnetization 1/1 and controlled tolerance 1000 cm / 1000 degrees, restoring locomotion profiles afterward. Global drive settings, gravity and simulation membership are separate.
- Tolerance is a deadband: 0 feeds realized physics back; within tolerance the NN value stays unchanged; beyond it only residual error is fed back. Lower feedback uses the authored target paired with the completed physics step, transported to the current recurrent frame.
- Controlled channels: pelvis, spine/neck/head, clavicles, upper arms, hands, thighs, feet, balls. Calves/lowerarms are IK results, not independent recurrent feedback channels.
- Timed blends use smoothstep over60 game ticks per authored second; setters cancel affected timelines, replacements start at current values. Conditional cells and snapshot returns use the same convention. All timing callbacks retire when their active work ends. Legacy Tick velocity overwrites can bypass magnetization.
- **Save Physical Profile Snapshot** after delayed BeginPlay captures body magnetization enabled/scales and supported tolerances across all four contexts.
- Snapshots are per-agent runtime data, not disk saves. Name None is a default slot; same name overwrites.
- **Blend Body Magnetization To Snapshot** and **Blend Physical Feedback Tolerance To Snapshot** have Below and All variants. Same name + duration; <=0 is immediate. Missing name/bone returns false/0 without changes.
- Saves capture current blend values, not unfinished destinations. Attack overrides remain; save/restore addresses underlying locomotion profiles.
- Disabled magnetization fades to zero then restores disabled flag/remembered scales. Simulation membership, gravity, global settings and physical state are excluded.
- Saving adds no tick or per-frame snapshot lookup. Restores use existing updates; identical completed profiles release context state, conditional profiles retain normal selection.
- Focused snapshot/context and existing blend tests passed 2026-09-18 07:36:13 UTC. Scene wiring/testing remains with user.

References: [snapshots](Docs/PhysicalProfileSnapshots.md), [conditional settings](Docs/ConditionalPhysicalSettings.md), [blends](Docs/PhysicalPropertyBlends.md), [feedback alignment](Docs/LowerPhysicalFeedbackAlignment.md), [joint damping](Docs/JointAngularDamping.md).

## Root, locomotion and inertia

- `Set Locomotion Lower Body Tempering` has Enabled and four per-agent values: Feet Translation, Feet Rotation, Pelvis Translation, Pelvis Rotation (all default 1). One preserves normal prediction; zero holds the previous published pose in root-local coordinates, so it travels/turns with the root. Intermediate values follow the new prediction per policy step. Feet rotation includes toe/knee-frame motion. Tempering happens before existing world-space foot pinning; fixed-length leg resolution follows pinning and checkpoint blending, before recurrence/upper conditioning. Uses the pelvis-inertia reach/floor/hinge solver. **Locomotion only: all active specials, including half attacks, full attacks, parries and dodges, bypass tempering and its additional history copies/leg solve.** Pending defense requests remain free to locomote. Settings and return schedules are retained for locomotion; clocks continue rather than restarting on special entry. Disabled/all-one entries are removed, skipping tempering/history copies/extra solves and inference. No retained pose cache. See [LowerBodyTempering](Docs/LowerBodyTempering.md).
- `Blend Locomotion Lower Body Tempering To Normal` captures current controls and independently holds/restores feet and pelvis to1. Each pair has Duration(default1) and Hold(default0): duration1=60 game ticks; hold0.5=30 game ticks. Active-only shared clock; sampled on the existing eligible policy path. The ticking clock retires at its deadline even during full attacks/defense; the final result is consumed on return. Completion removes settings/timeline and bypasses tempering work. New Set cancels; new Blend retargets from current values. Duration0 snaps after hold;0/0 immediate. Already-normal allocates nothing.
- Hold/return controls loaded via Live Coding2026-09-19; reflected node signatures verified, LowerTempering.ReturnTimeline and PolicyBlend.AttackRecovery passed (12:33UTC): holds, four-value interpolation, timeline retirement, setter cancellation, run-only hold, blend-boundary residual time and legacy zero-duration recovery bypass. No restart or user asset edits; scene testing remains with user.
- Blend clocks subsequently changed to the requested60-game-tick convention (2026-09-19, loaded via Live Coding). Six focused tests passed, including30/60/120FPS clock inputs, exact hold/return boundaries, callback retirement, physical/profile/snapshot behavior and attack transfer; final profile test passed12:59UTC. [Scope and evidence](Docs/BlendTickTiming.md). Physics/NN scheduling and Blueprint wiring unchanged.
- Tempering exposes exactly **two menu nodes: Set and Blend Locomotion Lower Body Tempering To Normal**. Blend has Feet Duration/Hold and Pelvis Duration/Hold pins, independently restoring each translation/rotation pair. Completed parts retire independently; both normal bypass all tempering. New Set/Blend replace both schedules. Feet/Pelvis-only compatibility functions are hidden from the menu. Existing Duration/Hold connections now control feet; new pelvis pins default1/0. Same60-tick convention and zero-duration behavior. [Details](Docs/LowerBodyTempering.md).
- **Repeated full-attack diagnosis:** zero tempering holds the first attack's finishing stance between attacks. In the current two-`overL` scene, disabling tempering immediately after the second Trigger produced exactly identical18-step attack inputs/outputs; the weak lower motion is already in the attack prediction. Allowing locomotion recovery in the gap restored a ready stance and much larger second-attack movement. Full attack bypass is working; it does not reset the starting pose. No forced recovery/reset added. Three bounded360-frame captures, no Blueprint/map changes or restart; evidence and scope in [LowerBodyTempering](Docs/LowerBodyTempering.md).
- Two-node interface loaded via Live Coding without restart; SeparateReturns, ReturnTimeline and SixtyTickClock passed2026-09-19 at13:19UTC, including exactly two menu-exposed functions and separate timing through one Blend node. No Blueprint/scene edits.
- Blueprint owns locomotion inputs; do not restore native keyboard polling.
- Continuous root readback follows estimated present root. Future sample spacing is still the policy spacing, not 1/60 s; use returned Time Offsets Seconds.
- Explicit root placement shifts root/window together. Automatic pelvis bounds instead rebase root/window/cube while preserving NN world targets. Do not revive the root/cube runaway.
- Root impulses and forces/torques act through the mover. World linear momentum must not rotate with yaw. Units/scope are documented.
- Two independent magic linear/angular velocity sets have separate setters, additive/overwrite selection and getters; they compose separately from mover motion.
- Root limits, optional pelvis bounds/cube registration and balancing remain per-agent. Balancing includes speed, move-input, tolerance and magic-velocity conditions. Preserve user tuning.
- Future-root smoothing independently controls distance, direction change and orientation. Zero preserves previous root-to-root local relationships; present root is not smoothed.
- Pelvis inertia runs after lower inference with leg-chain correction, before upper conditioning. Hand inertia resolves arms via IK with root-local axes and per-checkpoint values. Defaults preserve existing behavior; disabled paths avoid correction work.
- Lower tempering and zero attack-recovery bypass compiled in the normal Editor target on 2026-09-19 (Unreal was already closed). Four focused headless tests passed: root-local tempering/pin/chain, existing pelvis leg-chain regression and both policy-blend tests. Temporary process exited successfully; no scene/BP edits or extensive rollout testing.
- Walk pin tolerance/fallback, raw/effective diagnostics and near-ground threshold are separate controls. Debug capture is opt-in.
- Automatic run selection above root speed defaults to 100000, distinct from the low-speed walk-checkpoint override.

References: [continuous window](Docs/ContinuousRootWindow.md), [smoothing](Docs/LocomotionRootWindowSmoothing.md), [magic](Docs/RootMagicVelocities.md), [bounds](Docs/RootPelvisBounds.md), [limits](Docs/RootVelocityLimits.md), [balancing](Docs/RootSelfBalancing.md), [impulses](Docs/RootAngularImpulse.md), [pelvis](Docs/PelvisInertia.md), [hand](Docs/HandInertia.md), [pin diagnostics](Docs/FootPinningDebug.md), [walk tolerance](Docs/WalkPinningTolerance.md).

## Other retained systems and remaining risks

- Preserve Kinematic/HalfSim/Sim continuity and distinct backend/controller contracts. Experimental classes/controllers are not production defaults. HalfSim and Sim are not interchangeable.
- Sword grip uses accepted Training sword geometry. Cutting behavior and owner exclusions are separate from attack-phase filtering; old global sword-ignore descriptions are historical.
- Simulated Jolt swords inherit the gripping hand's accepted magnetisation packet (default hand_r): effective linear/angular strengths, gravity compensation, enable state and target trajectory. The grip/socket/body-origin offset is applied after hand-target interpolation on each native substep, so the independent sword drive follows the authored target, not the deflected physical hand. `Break Sword Grip Constraint` removes only the fixed joint, retaining held ownership, drive and collision exclusions for testing; switch simulation off/on or drop/re-equip to restore it. Drop/mode change/body or hand destruction removes the drive. Attached/kinematic swords register no extra drive. Live Coding loaded 2026-09-19; IndependentHandMagnetization and AttackCollisionPhases passed through the shared step path (11:34 UTC). No restart or user asset edits; contact jitter remains for user scene testing. See [SwordMagnetization](Docs/SwordMagnetization.md).
- Repeated overL left-arm separation measured on2026-09-19: actual native elbow anchors reached6.71cm apart at default10 velocity/2 position iterations. 40/2 barely helped;10/8 reached2.77cm;two substeps reached2.75cm;10/32 reached0.55cm (91.75% reduction). Attacker-only10/32 reproduced this result, with other agents retaining default overrides. Existing `Set Jolt Solver Iterations` exposes the tested settings;0/0 restores defaults. No gameplay defaults/assets changed, no restart, no performance claim. Position convergence is implicated, not a demonstrated missing constraint/upstream bug. See [OverL arm investigation](Docs/OverLArmConstraintInvestigation.md).
- **Accepted specials solver policy:** attacks and committed parry/dodge automatically use10 velocity/32 position iterations; exit/cancel/interruption restores that agent's configured locomotion counts (normally0/0 overrides =10/2). Pending pre-Armed defenses do not activate it. Attack/defense flags compose; re-created rigs use effective counts. Solver setter during a special changes the later locomotion values while getter reports effective10/32. Event-only state, no new Tick/poll; teardown removes it. Live Coding loaded2026-09-19, SpecialSolver.Lifecycle passed;180-frame current overL capture confirmed73 attacking samples/native joints at10/32 and107 locomotion samples at0/0, with no mismatched effective samples. Blueprint/map unchanged; no restart.
- Numerical containment preserves requested gains, rejects invalid native state and safely stops the affected shared simulation. Do not suppress assertions or retune PHAT to hide failures.
- Blood, reach, Boss/MetaHuman, rope/noose and boat keeper decisions remain in topic docs and the [archived domain sections](Docs/Journal/ProjectJournal-history-through-2026-09-18.md#other-accepted-project-systems). Do not resume deferred work from historical next-task lists.
- Consult Boss material/asset provenance before reimporting; historical FBX exports are not automatically equivalent to the accepted fitted keeper.
- Performance figures are workload-specific. Headless fixtures and historical packages do not prove current rendered performance or current packaged gameplay.
- User owns extensive visual/contact tuning. Exact frame-90 sword pop was not reproduced in the recorded comparison; startup overlap caused a separate large spike.
- Sword cold-load guard is installed, finishing compilation of the selected mesh before editor physics admission. Specific first-Play failure still needs fresh-process confirmation at the next planned launch; do not restart solely for this.
- Include live changes/new libraries in the next planned normal build before fresh launch. Latest results are live-editor tests, not new packaging acceptance.
- Reinspect current BP before assuming the user has added Other != Self or removed legacy velocity overwrites. The investigation did not edit either.
- No historical pending task becomes active automatically; follow the user's next request.

References: [fight setup](Docs/JoltFightSetup.md), [capability ledger](Docs/JoltCapabilityLedger.md), [accepted performance](Docs/JoltAcceptedPerformance.md), [Boss](Docs/BossUEFNImport.md), [blood bridge](Docs/JoltBloodBridge.md), [blood visual evidence](Docs/JoltBloodVisualValidation.md).

Journal tidy on 2026-09-18 changed documentation only. All previous entries/evidence were preserved in the archive; current sweep defaults and attack/defense gating above supersede old default-off and attack-only records.
