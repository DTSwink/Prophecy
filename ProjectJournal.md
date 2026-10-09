# Prophecy — current handoff

Updated **October 9, 2026**, after the FK twist-inertia port, Play-crash repair and dodge sword check. Read this first after a context reset. Current sections override dated history; history is evidence, not a to-do list.

## Resume here

- **Unreal is open on `/Game/testNN`, outside Play. Normal Editor/game/Jolt DLLs contain the current source.** Last normal build succeeded in 277.34 seconds (19 actions). This documentation/push needs no compilation. Recheck processes/logs before operating; PIDs and runtime tuning are not permanent facts.
- Latest request: push completed work and leave a tidy, complete handoff. Gameplay work is complete. Current PoseAgent BP compiled and saved for backup, status3 / native_properties0 / pin_types0, full graph unchanged. TestNN map was not edited/saved by this task; its existing local modification stays out of the lightweight push.
- **Crash resolved:** Live Coding added `FProfile::UpperArmTwistRemoval`, changing element size in retained static parry-return maps. Play crashed in `SetParryFKReturn` insertion. A closed-editor normal build and fresh process fixed it. Do not undo the accepted algorithm or strip Blueprint nodes to accommodate stale DLLs.
- **Verified:** 17 focused native tests; two actual180-absolute-tick Play runs through attacks/returns, one explicitly requesting Dodge. Finite poses, no crash, graph unchanged. Dodge audit:46 suppressed pairs =23 defender bodies including sword versus attacker hand_r+sword. Existing sword-backend refresh messages occur during PIE teardown, not the measured gameplay interval.
- **Latest behavior:** upperarm twist-inertia removal is in lab and UE. Latest slashLD settings imported; other15 profiles and idle unchanged. Dodge suppresses the attacker's held sword for every family; slashes/pike already included it, other families had a gap.
- Committed compact receipts: `Tools/Recovery/Receipts20261009FK/`. Full local evidence: `Saved/Diagnostics/FKUpperArmTwistPort20261009/`, `Saved/Diagnostics/FKCrashDodgeSword20261009/`. Full captures/build outputs are not uploaded.

## GOLDEN RULES — read before touching Unreal

1. **User tick numbers mean Blueprint `absolute tick debug`, never `tick debug`.** Auto-reset resets the latter. Record absolute tick, family, ownership and phase.
2. **Authored seconds =60 unpaused game ticks.** Holds/delays/fades/spreads do not use wall time, DeltaSeconds or30Hz inference steps. Explicit policy-frame controls (e.g. defense Frames After Hit) retain documented policy-frame units. [Timing contract](Docs/BlendTickTiming.md).
3. **Retained native layout changes require a normal build/restart.** Includes PRIVATE structs/classes in static TMap/TSet, heap allocations and nested profiles, not just reflected fields. Even empty containers retain allocations with the old stride. Live Coding cannot migrate them; isolated passing tests do not establish reload safety. Preserve assets, close cleanly, build, reopen TestNN, verify actual Play initialization.
4. **Keep small fixes fast.** No cosmetic/comment/tooltip edits to widely included headers, especially `ProphecyAgent.h`, even after compiling: they force the next task to rebuild dependents. Prefer implementation files and existing narrow libraries. New reflected libraries can also regroup generated/unity files. Do required API changes correctly; avoid unrelated rebuilds/full suites/toolchain edits.
5. **Build workers are automatically dynamic.** Installed UBA adapter recalculates free physical/commit RAM every500ms, default1.5GiB/job with CPU cap. Do not force fixed workers or restart a build to change concurrency. One worker can be correct with low RAM. `Tools/ConfigureBuildWorkers.ps1` reinstalls after engine restore/verification if needed. No custom launcher. [Build-worker contract](Docs/DynamicBuildWorkers.md).
6. **Preserve user work and active Play.** Owned diagnostic Play is authorized when needed for the requested investigation and no user Play exists; no repeated permission question. End only your own sessions. Do not silently stop user Play, restart, alter tuning/wiring, save unrelated assets or restore old backups. Explicit save/reopen requests authorize necessary steps. Preserve requested dirty assets before an authorized restart.
7. **Never cold-launch stale DLLs.** Successful Live Coding patches do not update normal DLLs. Build before reopening when needed; stop if it fails. Explicitly open `/Game/testNN`, not heavy default `/Game/mybasic`. Never remove expected pins/functions to accommodate old DLLs. User rejected a custom launcher; do not recreate it.
8. **User editor uses normal UI flags.** No `-unattended`, `-nullrhi` or automated test commands on interactive launch. Unattended bypassed normal per-monitor DPI setup and caused small fonts. Prefer isolated `UnrealEditor-Cmd -nullrhi -nocef -unattended` automation: interactive automation has previously crashed CEF. Don't change UI scale/render settings to mask it.
9. **Live Coding only when layout-safe.** Avoid reflected WorldSubsystem/Agent reinstancing. Preserve unsaved BP before necessary reflected reloads; keep PIE stopped through patch application, not only dispatch. `LiveCoding.CompileSync` blocks the editor: explain first. Check compile AND reload completion before captures. Adaptive unity stays disabled; ordinary unity remains enabled.
10. **Check existing BP after reflection changes.** Use targeted stale-library-CDO/Agent repairs below, preserving all other defaults/links. Python wrappers may be stale despite valid native reflection. Verify the full graph; don't save a broken BP.
11. **Inactive/disabled/completed means no recurring feature work.** No extra inference/timer/skeleton copy/IK/query/history capture when unused; retire state/callbacks. A cheap guard is not literally zero CPU. Optimize supported behavior without sacrificing correctness.
12. **Measure before claiming a cause.** Distinguish raw NN, accepted future, displayed interpolation and physical mesh. NN Hit is not physical contact. Recurrent changes alter later states: preserve the prefix and intervene just before the symptom, or replay exact inputs. Keep geometry/checkpoints fixed unless changing them is the experiment.
13. **Quick, concise collaboration.** User prefers their own motion tests unless investigation/testing is requested. Current FK elbow work uses numerical poses/poles, not images. Use remote APIs/scripts instead of taking over the desktop. No routine subagents/exhaustive suites/unsolicited changes. Don't re-ask already-authorized steps.
14. **Curated, bandwidth-limited backup.** Explicit staging only; never `git add .`, LFS transfers, bulk assets, caches or generated model uploads unless requested. Keep all FPS/performance references, especially100-agent benchmarks, during cleanup. No deletion outside authorized scope.

## Tools and safe build/reopen sequence

| Item | Location |
| --- | --- |
| Workspace/project | `C:/Users/singerie/Documents/Unreal Projects/Prophecy/GameAnimationSample3.uproject` |
| Target/engine | `GameAnimationSample3Editor` / `C:/Program Files/Epic Games/UE_5.7` |
| Main BP/native class | `/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent` / `AProphecyAgent` |
| Map | `/Game/testNN` |
| Python | `C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe` |
| Remote runner | `Tools/RunUnrealRemote.py` (preferred tracked copy) |
| Current launch log | `Saved/Diagnostics/FKCrashDodgeSword20261009/editor.log` |
| Default editor/build logs | `Saved/Logs/GameAnimationSample3.log` / `%LOCALAPPDATA%/UnrealBuildTool/Log.txt` |
| Git | `https://github.com/DTSwink/Prophecy.git`, `codex/standalone-sim` |

Read scripts before reuse: some start/end PIE, mutate actors/CVars, compile/save/repair or quit. Explicit UTF-8 file I/O. From project root:

```powershell
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/RunUnrealRemote.py Saved/Diagnostics/YourScript.py
```

Useful remote APIs/commands:

- `unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()` checks Play; `.get_editor_world()` checks map.
- `unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Editor.LiveAgentTypes Inspect')`; report `Saved/Diagnostics/LiveAgentTypes-Inspect.txt`. Healthy: status3, native_properties0, pin_types0.
- `Prophecy.Editor.RepairLibraryDefaults` repairs archived library CDOs; `Prophecy.Editor.LiveAgentTypes Repair` repairs exact stale Agent types. Targeted repairs, not routine edits.
- `Prophecy.Sword.AuditCollisionGraph` writes full BP graph to `Saved/Diagnostics/SwordThigh/BlueprintGraph.txt`. Compare before/after; normalize only known irrelevant reflection paths, never meaningful defaults/links.
- `unreal.BlueprintEditorLibrary.compile_blueprint(bp)` then `unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False)` saves only requested BP. Back up existing bytes; preserve unsaved user work first. Compiling is not saving.

For an authorized restart: preserve dirty assets, close cleanly (never force-kill unsaved editor), then:

```powershell
& 'C:/Program Files/Epic Games/UE_5.7/Engine/Build/BatchFiles/Build.bat' GameAnimationSample3Editor Win64 Development '-Project=C:/Users/singerie/Documents/Unreal Projects/Prophecy/GameAnimationSample3.uproject' -WaitMutex -FromMsBuild
```

Do not add `-NoLiveCoding`: it changes definitions and can rebuild broadly. After success, launch directly:

```powershell
Start-Process 'C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor.exe' -ArgumentList '"C:/Users/singerie/Documents/Unreal Projects/Prophecy/GameAnimationSample3.uproject" /Game/testNN -NoSplash'
```

Verify reflection/BP after launch; repaired Play crashes require actual Play verification. Startup restore/low-space dialogs can block remote discovery. Preserve autosaves/metadata; don't assume recovery happened or overwrite newer work with older backups. Diagnostic callbacks need timeout/error cleanup, CVar restoration, owned-session checks and data release. Physical rigs need actor ticking: tick-disabled fixtures must first switch all involved agents to Kinematic.

## Current FK return and live lab

- **Running lab:** `C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab`. `Labs/AttackRecoveryLab` is the portable backup, not necessarily the active server. Never overwrite live `state.json` from a stale backup.
- Server `http://127.0.0.1:8817`; `/desktop-view` has top-level `state`, `displayedPose`, `sequence`, identity/fingerprint, not nested `view`. Check freshness/client identity. Numbered snapshots are historical. [Capture/API instructions](Labs/AttackRecoveryLab/README.md).
- UE first slashLD =lab **variant21**, absolute61–101,21 unique30Hz policy frames from41 ticks,25 bones, excluding physical response/post-attack return. UE XYZcm -> lab XZYmetres; imported UE variants bypass harness forearm-roll repair. Original320 variants unchanged. Backup includes current saved lab profiles/view.
- Accepted original FK return with inertia, **not optional continuous spring**. Idle is real Unreal `M_Neutral_Stand_Idle_Loop` frame0, same across attacks, parent-local. Hand local inertia zero, parents still move hands. Spine01–05 share one weight, arms symmetric. Main inertia, bone weights, return/easing/timing are per attack. Spine angle adds flat seconds (.29s/90deg default), independent of base duration.
- **Remove upperarm twist inertia:** per attack, symmetric,0original/1full axial removal. Decomposes finite added inertia about actual shoulder-to-elbow axis, preserves swing. World mode carries correction into forearm/hand preserving local rotations. No angle clamp/forced downward elbow. Skipped after completion/zero inertia. Rejected90deg limiter/controls removed.
- Native **Set Attack FK Return Twist Inertia** changes only this field; Attack None means all families. Separate Values/Inertia Profile setters preserve it; legacy combined setter replaces the whole profile. Reset preserves captured configuration. [Return contract](Docs/AttackFKReturn.md), [separate controls](Docs/FKReturnSeparateControls.md).
- **Latest slashLD:** return .39s, inertia .18, easing0, inertia hold .08, decay .8, world=true, angle addition .29s/90deg, twist removal .98. Weights spine .31 / clavicle1 / upperarm1 / lowerarm .36 / neck01 1 / neck02 1 / head1. Other15 profiles/idle unchanged. BP **NN AlphaHold .17 / Trim0** retained: different from inertia hold .08. Legacy/Values slashLD override nodes disconnected at verification; re-read if user changes BP.
- Parity:321 variants;2568 pure samples max .000207684cm/.000281378deg;6010 unchanged-winding runtime samples max .001155359cm/.000269452deg. Conditional slash winding separately redirects problematic inward arcs; don't promise identical curves under all UE modifiers.
- Files: `ProphecyFKReturn.h`, `ProphecyFKReturnMath.h`, `ProphecyFKReturnData.h`, `ProphecyFKReturnLibrary.cpp`; exporter `Tools/NN/ExportFKReturnLab.cjs`. **Don't overwrite all native profiles with a whole-lab export for one attack.** Check other rows/idle byte-identical. To recreate the ignored parity fixture safely on a fresh checkout, use `node Tools/NN/ExportFKReturnLab.cjs --reference-only`; it reads accepted native profiles without writing them and produces `Saved/FKReturn/lab-reference.json` needed by the parity test.

## Current combat contracts

Read current source/topic docs and actual BP pins for enabled settings. Defaults are not necessarily scene settings. Specials =full/half attacks and active Parry/Dodge; queued defense remains locomotion. Policy cadence30Hz differs from authored60-tick seconds.

| Area | Current reference and key caveat |
| --- | --- |
| Attack lifecycle/counters/bones/kicks | [AttackControls](Docs/AttackControls.md), [SlashBlueprintUsage](Docs/SlashBlueprintUsage.md). Active Trigger retargets without restarting. Kicks ignore half requests; experimental kick half regime removed. Previous Attack Name updates on end. |
| Half reach/ghost | [HalfAttackGTInitialization](Docs/HalfAttackGTInitialization.md), [GhostAttackLean](Docs/GhostAttackLean20261008.md). Upper AND lower ghost share compensated/clamped target. Older upper-only descriptions superseded; minimum reach defaults30cm horizontally about pelvis. |
| Ghost loco | [GhostLocoDrag](Docs/GhostLocoDrag.md). Independent undragged history stabilizes shared pelvis/upper; real feet keep drag and pelvis inertia. General/kick-specific inertia independent; kick run NN sees ghost kicking leg. |
| Attack motion/feedback | [AttackMotionInertia](Docs/AttackMotionInertia.md), [AttackNNFeedback](Docs/AttackNNFeedback.md). Preserve optional filters/legacy feedback defaults. No silent vanilla-fidelity rewrite; new specials cancel outgoing recovery. |
| Defense inputs/order/ghost | [NNDefense](Docs/NNDefense.md), [LiveDefenseControls](Docs/LiveDefenseControls.md), [DefenseInputGhost](Docs/DefenseInputGhost.md). Attacker accepted output before defender; visualize accepted defender body and actual pelvis/collider history, not physical-pose substitutions. |
| Defense start/end | [DefenseStartThresholds](Docs/DefenseStartThresholds.md). Current nodes use per-attack integer **Start Delays after Armed**, default0; raw Hit thresholds replaced. Post-Hit/max-duration/end/manual-stop settings retained. Movement input changes root window, not defense state. |
| Defense returns | [LiveDefenseControls](Docs/LiveDefenseControls.md). Legacy upper spring and separate lower tempering for Dodge; independent optional FK return for Parry. Don't mix attack/Parry profiles. |
| Defense collision | [DefenseCombatRules](Docs/DefenseCombatRules.md). Dodge excludes relevant attack bodies plus held sword for all families, only attacker/dodger pair. Parry protects BP trunk+both arms by zero contact inverse mass/inertia against attack bodies. Welded identity/sweeps respected; release on end/reset. |
| Sword phases/sweeps | [SwordAttackCollision](Docs/SwordAttackCollision.md), [JoltPHATSweeps](Docs/JoltPHATSweeps.md). Accepted sweeps initiate from sword on six slash families. Right punches exclude sword attack role and suppress its victim collision Armed->End. No universal penetration-free promise. |
| Arms anti-jiggle | [ArmsAntiJiggle](Docs/ArmsAntiJiggle.md). Opt-in each arm, defaultoff, solver motors. Suppressed **Armed->End for sword attacks only**, not Armed->NN Hit. Timed disable composes, retains asymmetric choices. |
| Sword no reaction | [SlashSwordNoReaction](Docs/SlashSwordNoReaction.md). Automatic slash Armed->End suspends during victim defense; Strength0..1. Manual override wins; defaultoff. Not blocked-sword stabilization. |
| Snapshots/magnetization | [PhysicalProfileSnapshots](Docs/PhysicalProfileSnapshots.md). Actual special entry restores slot1/cancels relevant pending blends; queued defense not active. Per-bone/below, hold-outs and delayed tolerance supported. Anti-wobble experiments reverted. |
| Reset/regional ends | [AgentReset](Docs/AgentReset.md), [RegionalSpecialRecovery](Docs/RegionalSpecialRecovery.md). Full->half emits lower end; upper return on upper end. Reset wins; arbitrary BP timers/variables aren't universally reset; reacquire recreated equipment. |
| Root/camera/trajectory | [RootSelfBalancing](Docs/RootSelfBalancing.md), [SlashFootContactsAndCamera](Docs/SlashFootContactsAndCamera.md), [ComputeCatchUp](Docs/ComputeCatchUp.md). Player-only camera/handoff; impulse/spread delays tick-based. Unreachable catch-up10000/false with naive pursuit velocity. |
| Diagnostics | [NNModifierDebug](Docs/NNModifierDebug.md). Paused one-tick report persists. Potential constraints aren't measured deltas. Raw Armed/Hit getter returns-1 inactive. |
| Checkpoints | [UpperCheckpointPicker](Docs/UpperCheckpointPicker.md), [AttackCheckpointComparison](Docs/AttackCheckpointComparison.md), source/receipts for Parry/Dodge pickers. Read current selection; old journal defaults aren't authoritative. No training watcher. |

**Keep performance references:** [DoubleReachPerformance20261008](Docs/DoubleReachPerformance20261008.txt), matching JSON and raw `Saved/Benchmarks/DoubleReach20261008/final/`. Direct native won and user chose direct. CPU reaching cost only, not total FPS. [Jolt performance](Docs/JoltAcceptedPerformance.md). Blood/native-Niagara migration and multiplayer aren't implemented by these tasks; historical proposals aren't accepted features.

## Push, restore and maintaining this handoff

- Lightweight push: source/tests/scripts/docs, lab code/captured variant/saved profiles, freshly saved PoseAgent BP. Current TestNN map modification, generated defense pickers, unrelated PDF, binaries/caches/full captures remain local. Older tracked maps/models remain recoverable, not a promise of today's exact scene.
- `.gitattributes` stores curated assets as real Git blobs. No LFS uploads; explicit staging and size inspection. Set process-local `GIT_LFS_SKIP_PUSH=1` for the push (the legacy pre-push hook still invokes LFS); don't remove hooks or alter global settings. After staging, `Tools/Recovery/VerifySnapshot.py --write-index`, stage `Tools/Recovery/Snapshot20261003.json`, commit, verify `VerifySnapshot.py HEAD`, push `origin codex/standalone-sim`, compare remote HEAD. Manifest filename retains legacy date; inventory must match latest tree.
- [Recovery](Docs/Recovery.md) covers omitted external assets, dependencies, original checkpoints and standalone shortcuts. Repository isn't a full laptop backup. Milestone receipts: `Tools/Recovery/Receipts20261009FK/`.
- [Full pre-cleanup history through October9](Docs/Journal/ProjectJournal-history-through-2026-10-09.md) preserves earlier investigations/domain references. Historical prose is preserved; Markdown links were adjusted for the archive location. Older archives remain under `Docs/Journal/`. Historical pending builds/PIDs/scene settings aren't current instructions.
- **Update current sections instead of prepending endless logs.** Keep build coverage, saved assets, defaults versus actual BP, evidence and limits explicit. Detailed experiments belong in linked topic docs/receipts. Archive superseded behavior, preserve user corrections, and never revive an old investigation as unsolicited work.
