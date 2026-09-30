# Run checkpoint refresh — September30,2026

Latest completed save: **181751** (`epoch` in the checkpoint), from the established September27 run's `20260927_220308_ik_run_turns_reface_mse0005_20260927_train_last.pt`, modified September30 13:57:24 local. Frozen source copy and source hashes before/after copying agree.

Installed Run ONNX SHA-256: `914FE944EDA9D7D65A807581A64620D821BD1B570447246AE258CFFC2C16E46C`.

Source checkpoint SHA-256: `0F2565AC72C5209153CBD910135209487F9EF8A0E234ED0C6D99DF2FF30A299E`.

The previous installed Run138684 model and matching runtime JSON were backed up **before replacement**, with hash verification and a `RestoreRun.ps1` script:

`Saved/CheckpointBackups/20260930-135852-RunBeforeRefresh/`

To revert, close Unreal, run that restore script in PowerShell, then reopen. It verifies both backed-up files and refuses to restore while UnrealEditor runs. The previous frozen training checkpoint also remains at `Saved/Diagnostics/RunCheckpoint20260929Refresh/source_checkpoint.pt`.

Export used `Tools/NN/ExportProphecyLowerBodyPolicy.py`; ONNX validation and three100-row seed/perturbed PyTorch comparisons passed, maximum absolute error0.0000015497. No substantive runtime contract changes. Only Run ONNX and its matching `prophecy_lower_body_runtime.json` replaced; other networks, Blueprint tuning and the deferred Walk/Run refactor unchanged.

Frozen source, metadata, staged export and validation: `Saved/Diagnostics/RunCheckpoint20260930-135852/`. Editor was already closed at the request. Normal Development Editor build succeeded in200.11seconds, incorporating the prior Live Coding changes. Unreal reopened on `/Game/testNN`; a65-frame owned PIE check passed41 finite-pose samples with Run100% through ORT DirectML. Verification PIE ended at12:03:43UTC; editor remains open ready to Play. No full suite, Blueprint tuning, asset save or push.
