# Run checkpoint refresh — September 29, 2026

Installed step **138684** from the existing September27 training run's `20260927_220308_ik_run_turns_reface_mse0005_20260927_train_last.pt`, saved September29 12:50:36 local. Source directory: `C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260927_220308_ik_run_turns_reface_mse0005_20260927_train/checkpoints`. Source hashes before/after copying and the frozen copy agreed.

Checkpoint SHA256: `0DEB3E4ACB4A5FB873C5483B790C09E69AFEBA7E16CFE2F98DEEBF6C755D71DD`.
ONNX SHA256: `134F72C1A659A27A7A2C60D15388090BD844F3A76F1D2EC7FFD16638CB737DF8`.

Replaced the Run ONNX and matching `Content/locomotion/NN/prophecy_lower_body_runtime.json`. No substantive contract changes versus134440. Existing Run/Walk selection and blending remain; the deferred refactor is not implemented.

Exported using `Tools/NN/ExportProphecyLowerBodyPolicy.py`. Structural validation and three100-row seed/perturbed PyTorch comparisons passed, maximum absolute error0.0000010729. Previous model/contract backed up to `Saved/CheckpointBackups/20260929-RunBefore138684/`; frozen checkpoint, staged export and parity evidence in `Saved/Diagnostics/RunCheckpoint20260929Refresh/`.

Normal Development Editor build succeeded in165.57seconds, incorporating recent Live Coding changes before reopening Unreal on `/Game/testNN`. Final65-frame owned PIE check passed41 finite-pose samples at Walk0/Run1 through ORT DirectML, with the actor's publishing tick enabled. The first diagnostic used the older script's disabled actor tick and produced Jolt ordering errors; corrected the diagnostic and repeated successfully. Diagnostic PIE ended; Unreal remains open ready to Play. No full suite, asset edits/save or push.
