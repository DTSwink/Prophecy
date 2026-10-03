# Previous Run model: checkpoint 138684

This is the exact installed Run ONNX and its matching runtime JSON, copied and SHA-256 verified before the September30 refresh to181751. The other networks were not replaced.

To revert, close Unreal and run `RestoreRun.ps1` in this directory with PowerShell, then reopen the project. The script verifies both backup files before restoring them and refuses to run while UnrealEditor is open. No rebuild is needed for this model-only revert.

The frozen original138684 training checkpoint also remains in `Saved/Diagnostics/RunCheckpoint20260929Refresh/source_checkpoint.pt`.
