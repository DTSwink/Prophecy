# Run checkpoint refresh — September 29, 2026

Installed step **134440** from the latest completed save in the existing training run: `C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260927_220308_ik_run_turns_reface_mse0005_20260927_train/checkpoints/20260927_220308_ik_run_turns_reface_mse0005_20260927_train_latest.pt`, modified10:59:18 local. Source hashes before/after copying and the frozen copy agreed.

Checkpoint SHA256: `E83A7C844BCEE4BB7AECBF832B772F98219559CD192CD49E761F2116C8CC2D81`.
ONNX SHA256: `87E02B61DF7E907034E307EA7680C4E279E0CC1A8301D5DD29ED2FED49CB78E8`.

Replaced `Content/locomotion/NN/prophecy_lower_body_run_b100.onnx` and its matching `prophecy_lower_body_runtime.json`. No substantive contract changes versus128231: existing dimensions, geometry, seed reference, foot-roll settings and selection/blending retained. Other checkpoints and Blueprint settings unchanged. Deferred Run/Walk refactoring remains unimplemented.

Exported with `Tools/NN/ExportProphecyLowerBodyPolicy.py`; structural validation and three100-row seed/perturbed comparisons against PyTorch passed, maximum absolute error0.0000013113. A fresh65-frame owned PIE session on the already-open `testNN` loaded Run through ORT DirectML, with41 finite-pose samples at Walk0/Run1. Owned PIE ended. No editor restart, build, full suite or asset save.

Previous model/contract: `Saved/CheckpointBackups/20260929-RunBefore134440/`. Frozen checkpoint, source metadata, staged export, parity/contract results and live capture: `Saved/Diagnostics/RunCheckpoint20260929/`.
