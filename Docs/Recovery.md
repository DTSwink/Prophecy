# Restoring Prophecy

## November 4 workspace and ProphecyAmbient checkpoint

User requested a Git backup before further cleanup. Includes the current on-disk
repository source, tools, tests, journals, SoundStudio and MetaSounds apps,
Bodyflip/FootIK lab work, training scripts, and ProphecyAmbient birds, bumblebees,
leaves and wind. All 74 authored Unreal asset files in the four module folders
under Content/Prophecy/Creatures/{Birds,Bumblebee} and Ambient/{Leaves,Wind} are
explicitly included, as are their source exports and existing edited foliage
materials. Saved/WindTest/overlay_revert.json preserves the wind rollback recipe.
The module registration and build targets are already tracked.

This is an on-disk recovery checkpoint, not a new full build/test certification
or a capture of unsaved editor state. Existing validation remains in topic docs.
No editor/lab/training processes are restarted or stopped by this backup.
Unreal's engine/plugins, other ignored marketplace Content, local environments,
training datasets/checkpoints outside tracked files, audio libraries in Documents,
and the separate Documents/Cursor/temp projects are NOT included. Do not delete
those on the assumption this Git backup replaces them. In particular the ambient
wind system references engine ProceduralVegetationEditor assets; keep required
engine plugins installed. The refreshed snapshot manifest verifies committed bytes.


## November 2 complete workspace checkpoint and Bodyflip port

The user requested all current repository work, including the accepted Bodyflip
lab and its new Unreal port. The explicit backup includes current source/tools,
lab profiles, authored exports and assets, the current PoseAgent Blueprint and
TestNN map, and the Bodyflip/FootIK runtime payloads, NN graphs and pinned V8 DLL
with its license. `Exports/Bodyflip/PikeFinal` preserves the exact pike_final FBX.
The snapshot manifest verifies the committed file list and bytes.

This is a repository checkpoint, not a full laptop or Unreal Content backup.
Ignored engine build caches, Saved diagnostics, external training runs and other
bulk Content remain local. Unrelated systems are backed up without claiming they
were behavior-tested by the Bodyflip port. A concurrent, unfinished Bumblebee
AddShot header edit remains local: this checkpoint keeps the preceding matching
two-argument declaration and definition instead of introducing a compile mismatch. The concurrent
working-copy changes are also backed up, unapplied, in
`Tools/Recovery/Receipts20261102Bodyflip/concurrent-work.patch`, with their base
commit and capture receipt alongside it. Bodyflip validation and remaining
floor-contact limits are in `Docs/BodyflipNative.md` and the compact receipts in
`Tools/Recovery/Receipts20261102Bodyflip`.


## November 1 accepted Bodyflip target-point aiming

User confirmed the target-point spear throw works and requested this checkpoint.
Includes the spine-only point fit, full momentum-response evaluation for spinning
throws, recursive prediction fix, focused regression tests and current handoff.
The earlier accepted setup is5b2a2da6. Live settings and Unreal are unchanged;
native integration/performance validation remains separate. See Bodyflip THROWS.md.

## November 1 accepted Bodyflip throw checkpoint

Pushed as `5b2a2da6` on `origin/codex/standalone-sim`; remote HEAD matched and
the recovery manifest verified. The accepted point-target follow-up is above.

Accepted standalone motion before target-point aiming experiments: FinalNoAim
throw sources, shared spine transfer/return, distance-weighted return duration,
attack joint-limit exemption and playback intent preservation. Includes current
saved-profile.json (snapshot of live state; live state itself is not changed),
final source exports/import tools and focused checks. 16,918 final-source,
157 return checks and the actual-app playback/retarget harness pass.
Unreal, native packaging and other tasks are outside this checkpoint.

## October 26 storage cleanup and historical diagnostic retrieval

The user requested a broad careful cleanup to Windows Recycle Bin.1,445 files
totaling11,607,151,778bytes were recycled and every bin payload SHA256-verified.
No permanent deletion or bin emptying. This is separate from the earlier1.94GB
obsolete Live Coding patch cleanup.

Old large diagnostic JSON/JSONL/text/log/T3D files dated before October19, excluding
tracked files, current/recent work, code-referenced fixtures and named performance
material, were losslessly archived before recycling. The1,126 files retain their
project-relative paths in
`Saved/DiagnosticArchives/HistoricalBulkBefore20261019.zip` (2,653,710,038bytes).
All archive members were independently read back and SHA256-verified. To recover
an old journal reference, extract only its exact member into the project root;
do not overwrite a newer existing file or bulk-restore the archive. Scripts,
small summaries and current fixtures remain in their original locations.

Other recycled files: byte-identical old asset backups (one verified copy kept),
the unused `unreal_collision.next.json`, redundant `runtime-cache-local.tar.gz`
(required startup-diagnosis copy retained), pre-October19 crash dumps/rotated logs,
old pip download/unpack caches, and the optional old generated project DDC pack.
Current assets, autosaves, model weights/handoffs, training data/environments,
normal binaries, current camera patches, C++ incremental caches, local Zen cache,
all benchmark folders and Jolt migration evidence remain.39,735 protected files
matched their original sizes/mtimes after cleanup, with none missing/changed.

Deleting `DerivedDataCache/Compressed.ddp` does not remove source assets; missing
derived data can regenerate on use, so the next launch may perform cache work.
The separate outstanding camera normal-build requirement still applies before
any cold editor launch. No editor, lab or training process was stopped/restarted.

Exact paths, SHA256, duplicate `kept_copy` replacements, bin metadata/payload paths
and verification are in `Saved/Diagnostics/StorageCleanup20261026/`:
`recycle-manifest.json`, `receipt.json`, and `summary.json`.
The archive is an external local recovery artifact, not a pushed Git backup.
Net space reclaimable after emptying the bin, accounting for the retained archive,
is8,953,441,740bytes (about8.95GB). Loose Diagnostics shrank14.43→6.21GB.

## October 25 Bodyflip motion checkpoint

The approved lab includes Idle with shared jump controls, fresh flat scenes,
capsule collision and actual NN landing continuation, free camera, whole-body
matched jumps, opaque leg overlays and smooth knee-safe transitions. The idle
recording and focused verification scripts/receipts are included;265 automated
checks pass. Live `state.json`, previews, inference caches and other sessions'
changes are excluded. The existing `saved-profile.json` is the earlier curated
setup, not the latest live scene library.

The October24 no-inference playback note below is historical: landing preparation
now needs the existing Stepper/Torch runtime, original encoder/decoder modules
and four NPZ seeds listed in `Labs/BodyflipLab/models/provenance.json`. These
runtime/seed dependencies remain external. The three frozen policy weights are
already tracked in `Tools/Recovery/Checkpoints/`; restore them by matching the
provenance hashes into `models/run.pt`, `walk.pt` and `upper.pt`. Initial locomotion
still uses included phase banks. See the [lab restore notes](../Labs/BodyflipLab/README.md).

## October 24 Bodyflip Lab checkpoint

`Labs/BodyflipLab` includes the standalone app, Jolt runtime/license, desktop
shortcut scripts, recorded attacks/jumps, exact Run/Walk phase banks, focused
verification scripts/receipts and `saved-profile.json` with current tuning and
camera. Copy that profile to live `state.json` only on a fresh restore. Playback
needs Python 3 and Edge/Chrome, without Unreal or neural-network inference.
The current shortcut launcher names a laptop-specific Python path; the lab
README gives the portable server command and documents regeneration-only
external models/seeds. Temporary exports, logs, browser profiles and full
captures are omitted. Parallel Unreal, training and other lab changes are
outside this checkpoint; only Bodyflip handoff sections are staged from the
shared journal.

## October 22 grab and tools checkpoint

Includes per-arm live grab joint independence, closest-agent/physical-mesh helpers,
grab defaults and surface-point controls, the root-relative pelvis floor, sword
FPS-reset removal, and the saved PoseAgent and A_Sword Blueprints. Normal Editor
build and focused grab verification passed; see the current reach/grab journal.
Also captures current MimicKit training scripts and the Sound Studio/idle viewer
source. Their local environments, audio, frozen viewer checkpoint and source
bundle under Saved are external; the viewer source alone is not a complete
runtime backup. TestNN's current local modification, generated defense exports,
full captures, diagnostics and unrelated PDF remain excluded under the curated
backup rule. This checkpoint does not save or change the running editor.

## October 18 source-only follow-up

The reach/grab lab and native pipeline, explosion wave/impact event, VDB playback,
and bomb fuse/fragment/fade source and preparation tools are included in this
follow-up. It does not capture the current editor's unsaved assets, Niagara tuning,
maps, PHAT edits, or generated bomb/VDB content. Restore the external ZibraVDB
plugin and source content before using the documented preparation scripts in
Tools/BombFuse; inspect Docs/BombFuse.md and Docs/ZibraExplosionFade.md first.
Build normal Editor DLLs before loading the newer Blueprint APIs; Live Coding
patches are not a replacement-machine backup. Reach lab code, defaults, exported
hand data and test-required recorded fixtures are included; other historical
captures and preview screenshots remain local. Other robotics/training work in progress
is outside this follow-up. Earlier recovery milestones below describe their own
saved assets and validation, not the current editor state.

This snapshot, updated through the October 9, 2026 FK-return and collision recovery
milestone, is a source and authored-setup backup on
`DTSwink/Prophecy`, branch `codex/standalone-sim`. It does not contain the entire
Unreal content library or the Stepper training workspace.

Latest named recovery point: `milestone/2026-10-08-combat-recovery`.
See [milestone contents and validation](Milestone20261008CombatRecovery.md).
Latest branch work includes upperarm twist-inertia removal, the tuned slashLD
profile, imported lab variant21, current lab settings, dodge held-sword coverage,
and the freshly saved PoseAgent Blueprint. See [current handoff](../ProjectJournal.md)
and `Tools/Recovery/Receipts20261009FK` for validation. The normal DLL rebuild and
two Play checks passed on October9; the current laptop editor is up to date.
On a replacement machine, build normal Editor DLLs before opening saved BPs.
The current local TestNN modification and generated defense picker exports were
excluded from this lightweight push; previously committed copies are older.

## Included

- Current game/editor C++, the Jolt plugin and its pinned build recipe, scripts,
  tests, project journals and diagnostic summary receipts.
- Forearm leeway follow-up: attack wrist freedom, per-arm captured stretch return,
  physical wrist constraints, and GT slash support in Sim/Half Sim. The saved
  PoseAgent Blueprint enables the return with a 0.3-second duration. Implementation,
  tests and diagnostic scripts/summary receipts are included; see
  `Docs/AttackForearmStretchReturn.md` for behavior and measured solver lag.
- All project `Config/Default*.ini` files and the Visual Studio workload manifest.
- PoseAgent, sword and other Blueprint graphs; control rigs, input definitions,
  structs and enums; selected small material/physics/PCG/tuning assets; TestNN
  and project maps. Authored assets are stored as real Git blobs, not LFS pointers.
- All 67 installed NN export/contract files under `Content/locomotion/NN`, including
  upper checkpoint choices, attack checkpoints and defense networks. Original
  training checkpoints are not necessary for running these exports.
- Follow-up checkpoint backup: **17 original `.pt` files (115,337,720 bytes)** in
  `Tools/Recovery/Checkpoints`, covering installed Run/Walk/Upper/Attack models,
  every current picker option, latest Parry and current/reference Dodge. They are real
  Git blobs, including training state present in the originals. The manifest
  `Tools/Recovery/NNCheckpoints20261003.json` records SHA-256, original paths,
  restore locations and referring runtime contracts. This is not every historical
  training-run save. Verify with `python Tools/Recovery/RestoreNNCheckpoints.py`;
  use `--restore --stepper-root C:/path/to/stepper` to recreate the referenced
  project/Stepper checkpoint paths on another machine. Existing different files
  are refused rather than overwritten.
- Standalone simulation source/data and a snapshot of its camera, combat options
  and opening layout under `Tools/Recovery/StandaloneSimSettings`.
- `Labs/AttackRecoveryLab`: an independent copy of the working app, accepted
  profiles, 320 generated variants plus captured Unreal slashLD variant21,
  frozen harness/idle inputs, icon and snapshots.
  The only portability adjustment is its Python launcher lookup. The original
  live lab under the Stepper workspace is unchanged.
- Previously ignored project Python/PowerShell/JavaScript scripts under `Saved`.
  These retain their original paths for journal links and imports. Historical
  repair/migration scripts are evidence, not a restore sequence: do not bulk-run them.

`Tools/Recovery/Snapshot20261003.json` lists the Git blob identity, SHA-256 and
size of every file in this snapshot, excluding the manifest itself. Verify it
against the committed tree with `python Tools/Recovery/VerifySnapshot.py HEAD`.
This verifies stored files, not the availability of external Unreal assets.

## Restore on a replacement Windows machine

1. Clone `https://github.com/DTSwink/Prophecy.git` and check out
   `codex/standalone-sim` (or the dated recovery tag recorded with the push).
   Current curated files use ordinary Git; no laptop-local LFS configuration is
   required. Older commits can still contain historical LFS pointers.
2. Install Unreal Engine **5.7**, Visual Studio 2022 C++/Windows SDK tools,
   Git, CMake and Python 3.10+. The verified Jolt baseline used VS toolset14.44
   and Windows SDK10.0.22621.0. `.vsconfig` and the build scripts record details.
3. Restore the omitted content library from its external source, preserving
   package paths. `Tools/Recovery/ExternalAssets20261003.json` lists asset names,
   classes and sizes excluded from this snapshot. It is an inventory, not proof
   that another copy exists. Restore bulk assets first, then restore this Git
   snapshot's tracked files so older bundles cannot overwrite the saved Blueprints.
4. In the project root, prepare the reproducible Jolt dependency:

   ```powershell
   powershell -File Tools/Jolt/BuildJolt.ps1 -Configuration Development
   ```

5. Install the automatic RAM-aware compiler scheduler with
   `Tools/ConfigureBuildWorkers.ps1` after restoring/verifying the engine; see
   [build-worker recovery](DynamicBuildWorkers.md). Then build the normal Editor
   DLL **before opening the saved Blueprints**:

   ```powershell
   & 'C:/Program Files/Epic Games/UE_5.7/Engine/Build/BatchFiles/Build.bat' GameAnimationSample3Editor Win64 Development "-Project=$PWD/GameAnimationSample3.uproject" -WaitMutex -FromMsBuild
   ```

   Stop if compilation fails. Old editor DLLs cannot load new Blueprint functions
   reliably. Live Coding patches, Binaries and Intermediate are intentionally not
   restored. No custom Unreal launch wrapper is required or provided.
6. Open `GameAnimationSample3.uproject` on `/Game/testNN`, then verify the PoseAgent
   Blueprint compiles and the three agents appear in Play. The forearm follow-up
   passed a normal DLL build, six focused tests and five replay checks. The latest
   October 3 reopening confirmed the build is current and the saved Blueprint
   compiles without stale native properties or pin types. Ghost Loco Drag and
   the existing FK return were previously accepted by the user.

## Standalone apps

For Prophecy Simulation, run `StandaloneSim/scripts/build.ps1 -Configuration Release`
then `StandaloneSim/scripts/install_desktop_shortcut.ps1`. Before its first launch,
copy the two saved settings JSON files into `%LOCALAPPDATA%/ProphecyStandaloneSim/`.
The persistent Combat Lab mode can run without the omitted world collision export.
The world view needs `StandaloneSim/data/unreal_collision.json`, restored externally
or regenerated using the export/baking procedure in `StandaloneSim/README.md`.
Render cache and executable outputs are rebuilt locally.

For Attack Recovery Lab, run `Labs/AttackRecoveryLab/install_shortcut.ps1`, then use
the desktop icon. Install Python 3.10+ and Edge/Chrome. If Python is not discoverable,
set `PROPHECY_LAB_PYTHON` to its executable. The server uses only the Python standard
library. NumPy and Node/Playwright are needed only for the optional extraction or
regeneration tools; existing variants are included. Tests can be run with Node:
`node Labs/AttackRecoveryLab/test_recovery.cjs` and `test_spine_turn.cjs` in that folder.
The original Stepper folder layout and live browser session are not required.

## Deliberately external

Large meshes, textures, grooms, MetaHuman identities/source meshes, marketplace
packs, most animation libraries, `SourceArt`, duplicate `Content - Copy` trees,
training runs/datasets beyond the 15 checkpoint files above and the rest of the Stepper repository are
not backed up here. Custom fitted MetaHuman meshes are also in that external set;
their existence on another device has not been verified. Recover those authored
assets from your external copy, not merely the stock marketplace download.

Unreal/IDE/shader caches, compiled third-party libraries, browser profiles,
credentials, full per-frame diagnostic captures, large ONNX export reports,
unrelated reports in `tmp`/`output`, and executables are omitted. Scripts for many
diagnostics survive, but some historical input captures must be regenerated.
This snapshot protects the listed project work, not every file on the laptop.
