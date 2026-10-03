# Next checkpoint: fight-sim handoff

Latest requested work is complete: runtime self-collision on the active Jolt character. Six Prophecy Agent nodes cover master, exact body list, skeletal subtree, single pair, reset and pair readback. Runtime suppressions layer over captured PHAT/current-joint exclusions; enabling removes only that layer, and reset restores the authored filter. Selected bodies suppress against the whole same rig; other fighters/world/weapons remain eligible, UE blood-query receivers remain intact. No per-frame scan, recreated bodies/joints or asset edits. Normal Editor build and all 82 Jolt tests pass, including every actual-character pair, held sword/state preservation, real contact toggles, sleeping overlaps, invalid inputs and rebind. All six reflected nodes are loaded. Usage: `Docs/JoltFightSetup.md`; evidence: `RuntimeSelfCollision-20260910/{result.json,EditorBuild.log,reflection.json,Editor.log}`. Current editor PID is in `RuntimeSelfCollision-20260910/EditorPid.txt` (22876 at handoff); testNN outside PIE, no dirty packages. No further builds/tests pending for this request. No new package/performance result.

Tenfold-magnetization crash containment remains implemented and passes again in the 82-test suite. Native guards reject invalid velocity/transform writes, safely handle huge finite rotations and check full shape bounds. NumericalFailure bit 3 stops publication after worker completion; Stop Play/start resets. Gains and PHAT remain unchanged. Detailed native build/worker/30-and-60-Hz character evidence: `HighGainCrash-20260910/{Implementation.md,result.json}`.

Build workflow: `-NoLiveCoding` switches WITH_LIVE_CODING to0 and caused broad rebuilds when alternating with Live Coding. Current normal baseline is now1; normal builds omit that flag and subsequent Live Coding works (one-file safety-test patch passed). Keep the configuration consistent. Do not repeat the canceled105-action LC request or raise its limit. User explicitly authorized restart when needed, while unsaved work still must be preserved. The native build requires the exact checked-in safety patch/hash and stages matching DLLs in both Editor search locations.

Angular controls remain implemented and pass again in the 82-test run. The earlier question about direct Sim-to-HalfSim is unanswered: HalfSim still uses Chaos, and active Jolt currently refuses that direct switch. Do not silently choose a Chaos handoff or a Jolt HalfSim port while working on another request.

Open `/Game/testNN` and press Play. Its persisted Jolt Fight Setup actor starts the world/static floor and manual-NN Physical fighters; use the existing Equip Sword node when wanted. Current source passes the normal Editor build/reopen and skeletal-integrity regression. The earlier 12-frame startup checks verified ownership/counts but missed a frozen body/socket offset and are superseded.

- Fix: unwelded PHAT body origins map directly to bones and authored targets. Preserve native body states, captured shape/COM scales, PHAT limits and drives; no retuning. Baseline `PoseIntegrity-20260910/poses-055237.json` froze an 88.78345 cm strong-fighter body/socket error and stretched the right-hand link from 22.35 cm to 60.54 cm.
- `PoseIntegrity-20260910/poses-060805.json`: every frame through 120, 238 Jolt character frames, both explicit sword equips and all 22 body/display pairs aligned within 2.048e-12 cm / 2.415e-6 degrees. Its inspected PNG shows the connected strong fighter holding a sword. The optional native-summary command had a path-parsing error; full pose metrics/PNG remain valid. The setup actor does not equip swords.
- `PoseIntegrity-20260910/EditorBuild.log` and `EditorReopened.log`: normal build/reopen plus passing `Prophecy.Jolt.Character.DivergentBodyAndSocketAdmission`; deliberately displaced/rotated native bodies preserve their starting state, align rendered/query output and recover toward unchanged targets.
- Frozen-offset explosion is fixed. Armed quality is not fully accepted: unresolved transient left-hand parent-link error reaches 8.228 cm at frame 36 (4.9 cm in another run). Do not retune PHAT/drives or suppress the finding. Full motion/contact quality and deferred mechanics remain open; no new package/performance result.

Earlier Development and Shipping candidates **PASS** their functional fixture group; they predate the saved startup actor and initial-velocity admission fix:

- Development: `FinalFight/Packages/Development-Resume-20260910-020305-616/result.json`.
- Shipping: `FinalFight/Packages/Shipping-RuntimeResume-20260910-022749-979/result.json`.
- Both have exit code 0 and ensure-count delta 0, saved Static testNN floor, 28 actual sword lifecycle checks, 10 floor-contact checks, and both matched 12-step sword/fighter contact trials.
- These are NullRHI functional fixtures. They do not certify attack swings, cutting, rendered gameplay, a complete production map, or new NN/performance measurements.

Unreal is open on `/Game/testNN`, outside PIE with no dirty maps/content. `FightStartup-20260910/publication.json` confirms the map was already persisted through Unreal package recovery: exactly one enabled setup actor, unchanged other actor paths, disk SHA256 `80a3c2ff7ac6d0631e849b1de15735df36e803c4b848942abb2f8e0ff9b23c57`. No duplicate save was performed. Do not save unrelated assets or start another UE/build process.

## Current accepted implementation

- Local simulation only. Hard PHAT limits, no rig retuning or numeric Chaos parity.
- Physical animation, native rigid bodies/joints, retained UE query receivers and existing static/character/ISM blood evidence are implemented. See `Docs/JoltIntegrationStatus.md` and `Docs/JoltFightSetup.md` for exact support and startup nodes.
- Training sword has one saved 127-vertex convex, strict 256-cap/zero-tolerance preparation, preserved bounds/render/material/complex-query geometry; max inward difference 1.911 mm, volume -0.922%. Original Sword_GL01 and A_Sword are unchanged. Backup/evidence: `SwordHull-20260910/`.
- User-authorized sword MACD omission is active; existing CCD=true is retained. Equip, fixed grip, attached/physical switch, both drops, momentum, owner exclusions, queries and cleanup pass.
- Imported testNN Floor is saved Static at its unchanged transform. `TestNNFloor-20260910/` contains backup/publication evidence.
- Blueprint initializer scratch is 256 MiB at default capacity. The focused scene checks passed 120 active steps; peak scratch 128,064,928 bytes.
- Held-sword/fighter contact is verified by equal 45-body initial states with only sword/victim Block/Ignore changed. It tests deliberate blade/head contact and depenetration, not a swing.
- Tiny standalone presentation follows UE's supported location/rotation thresholds while native query transforms still update exactly. Two focused tests pass, including real callback-pose replacement rejection.
- Preserve intentional upper-torso drive strengths: ManualPoseAgent2 0.02, ManualPoseAgent default 1.0. Keeper rendered still: `Saved/Screenshots/WindowsEditor/HighresScreenshot00019.png`. The existing walking test eventually leaves the floor.
- The approved ManualPoseAgent Blueprint save is backed up in `ApprovedBlueprintSave-20260910-020615/`. NewFunctionLibrary's 34 unlinked duplicate reserved context definitions are repaired/saved; remaining graph pins/defaults/wiring unchanged, compilation zero warnings/errors. Evidence: `AngSpringRepair-20260910/`.

## Package evidence and storage

Development used the clean saved repair. UAT built/cooked/staged successfully; a trailing-dot bug in the external-asset verifier was corrected without exemptions. Recovery reused the existing stage. Its audit explicitly records that Editor pre-cook hashes were not persisted, and full cook/stage hashes were first persisted at recovery; do not invent stronger historical provenance.

Shipping reused that exact shared cook. Its completed compiled binary was staged successfully with `-skipbuild -skipcook`. The final runtime uses a fresh external saved `Engine.ini`, selected by UE's supported `-EngineINI=` argument, setting only `GameDefaultMap=/Engine/Maps/Entry.Entry`. This is necessary because client Shipping ignores command-line map overrides. Stage, binary, cook and project defaults are byte-unchanged; all original attempts/reports remain preserved. Helpers and source support are in `ShippingStageRecovery-20260910/` and `ShippingRuntimeRecovery-20260910/`; final recipe documentation is `FinalFight/README.md`.

After both configurations passed, the duplicate Development stage and three obsolete NN stages were removed. Their reports, the shared successful cook, current Shipping stage and runtime reports remain. Cleanup reports: `RemovedVerifiedDevelopmentStage-20260910.json`, `RemovedObsoleteNNStages-20260910.json`, and the other `Removed*20260910.json`. Free space was 6.13 GB before reopening.

Automatic approval review previously denied these cleanup targets with “blocked by policy”; never retry them through another tool, alias, ancestor or compression workaround:
- `FinalFight-Development-20260910-000815-663/Cook` under the short .codex/tmp/ProphecyJolt root.
- The 84 Live Coding files in `ObsoleteLivePatchesAfterFinalBuild-20260910.json`.
- `NNCrowd-20260909-144331-647/Project/Saved/Cooked` under Saved/JoltMigration.
- `NNPkg-Development-20260909-183030-780/Cook` under the short root.

## Next work and user decisions

The user can build the fight sim now. In another fight map, place one Jolt Fight Setup actor; set `Enable Jolt` false before Play for normal Chaos. Admission waits for BeginPlay and latent startup, handles manual-NN Physical fighters only, skips Kinematic/HalfSim and does not force later explicit modes. Spawned fighters need existing NN registration and a published pose. Use the existing Equip Sword node when wanted. Visual/motion testing is deferred until the user is asleep; the short startup checks do not certify rendered motion or a complete fight.

Cutting, rope, noose and boat are deferred. Leave A_Sword Tick/cutting chains disconnected. Do not add force/velocity/joint wrapper work or a custom soft constraint until that work resumes. The broader migration plan, capability ledger and asset findings retain the deferred cutting consumers, motors and world support gaps. Character backend selection is supported; whole-fight live transfer, dropped-weapon transfer and Jolt HalfSim are not claimed.

Performance work is closed at the user-accepted R5 Shipping setup: 100 moving full-physical agents, 7.976/8.006 ms mean, standard medians 8.238/8.349 ms, p95 10.918/10.694 ms. One active PhysicalMesh, 22 bodies/21 hard joints/88 bones per agent; no second animated skeleton. 60 Hz world/output, 30 Hz actual NN, original feedback, retained queries, optional crowd cameras/fist closing omitted. See `Docs/JoltAcceptedPerformance.md`; no new benchmark.
