# Restoring Prophecy

This October 3, 2026 snapshot is a source and authored-setup backup on
`DTSwink/Prophecy`, branch `codex/standalone-sim`. It does not contain the entire
Unreal content library or the Stepper training workspace.

## Included

- Current game/editor C++, the Jolt plugin and its pinned build recipe, scripts,
  tests, project journals and diagnostic summary receipts.
- All project `Config/Default*.ini` files and the Visual Studio workload manifest.
- PoseAgent, sword and other Blueprint graphs; control rigs, input definitions,
  structs and enums; selected small material/physics/PCG/tuning assets; TestNN
  and project maps. Authored assets are stored as real Git blobs, not LFS pointers.
- All 66 installed NN export/contract files under `Content/locomotion/NN`, including
  upper checkpoint choices, attack checkpoints and defense networks. Original
  training checkpoints are not necessary for running these exports.
- Follow-up checkpoint backup: **15 original `.pt` files (100,610,789 bytes)** in
  `Tools/Recovery/Checkpoints`, covering installed Run/Walk/Upper/Attack models,
  every current picker option, Parry and current/reference Dodge. They are real
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
  profiles, 320 generated variants, frozen harness/idle inputs, icon and snapshots.
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

5. Build the normal Editor DLL **before opening the saved Blueprints**:

   ```powershell
   & 'C:/Program Files/Epic Games/UE_5.7/Engine/Build/BatchFiles/Build.bat' GameAnimationSample3Editor Win64 Development "-Project=$PWD/GameAnimationSample3.uproject" -WaitMutex -FromMsBuild
   ```

   Stop if compilation fails. Old editor DLLs cannot load new Blueprint functions
   reliably. Live Coding patches, Binaries and Intermediate are intentionally not
   restored. No custom Unreal launch wrapper is required or provided.
6. Open `GameAnimationSample3.uproject` on `/Game/testNN`, then verify the PoseAgent
   Blueprint compiles and the three agents appear in Play. The last normal DLL
   build and six focused ghost/foot/pelvis tests passed on October3; the user
   subsequently accepted Ghost Loco Drag and the existing FK return.

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
