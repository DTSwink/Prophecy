# Editor shutdown crash, 2026-09-11

The fatal report `Saved/Crashes/UECC-Windows-61FD154D423D4AC01087E49F00D1A6BC_0002` records an access violation reading `0x58` while exiting (07:16 local). The stack reaches `FSimpleAssetEditor::~FSimpleAssetEditor`, line 46: removal from `GEditor->GetEditorSubsystem<UImportSubsystem>()->OnAssetPostImport`. The simple asset editor is being destroyed by Slate during `FEngineLoop::Exit`, too late for the import subsystem.

The restart script called `unreal.SystemLibrary.quit_editor()`. Installed UE 5.7.4 source establishes the lifecycle error:

- `KismetSystemLibrary.cpp:650` sends `QUIT_EDITOR` directly.
- `EditorServer.cpp:5772` explicitly warns against directly calling that command with Slate. It invokes `CloseEditor`, which requests engine exit without the main-frame shutdown sequence.
- `MainFrameHandler.cpp:93` performs normal shutdown, broadcasting editor close at line 111. `UAssetEditorSubsystem::OnEditorClose` closes asset editors while subsystems still exist. Only afterward does the main frame defer `QUIT_EDITOR`.
- `CLOSE_SLATE_MAINFRAME` routes through `IMainFrameModule::RequestCloseEditor`, preserving that sequence and close/save checks.

Use `Tools/CloseUnrealClean.py` through the existing remote runner for authorized restarts. It rejects PIE and dirty packages, then requests the normal Slate close. Do not use direct `quit_editor()` for an interactive editor with asset windows open. No engine binary, simulation code, or user asset is changed for this correction.

The same session had a partial Live Coding failure: plugin patch linked but the game patch had unresolved new cross-module exports. RigVM/ControlRig parallel reference replacement also emitted handled access-detector ensures. These are separate from the fatal shutdown stack; there is no evidence proving they caused it. A normal Editor build is required to load the complete material implementation consistently. The earlier DXGI swap-chain creation crashes remain a separate unresolved issue.

Validation: normal Editor build succeeded. Opened the engine DefaultPhysicalMaterial in its asset editor, verified no dirty packages/PIE, and closed through `Tools/CloseUnrealClean.py`. The editor completed shutdown normally at 07:37:04 with `LogExit: Exiting` and the log file closed; no new crash report appeared. Evidence: `Saved/Diagnostics/RuntimeBoneMaterials/shutdown_probe.json` and `CleanShutdown.log`. This verifies this restart path, not a guarantee against unrelated future editor crashes.
