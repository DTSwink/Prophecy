# Intermediate Run checkpoint — September 28, 2026

Installed the newest completed save from `C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260927_220308_ik_run_turns_reface_mse0005_20260927_train/checkpoints`: `20260927_220308_ik_run_turns_reface_mse0005_20260927_train_last.pt`, modified 20:47:11 local, checkpoint `epoch`/training step **128231**. This is an intermediate snapshot; further fine-tuning is expected. Later training saves are not automatically installed.

Checkpoint SHA-256: `A5BF2DB23E74BC9C7FD6F76C6509E598D8DDCC24052B92485453E232F7F62906`.

Run ONNX SHA-256: `004D7A2D00E2EA2A8498DC7FCC6B2ADC28FD0014A612CB18550D85DDEE546415`.

Replaced only the existing Run model and matching contract:

- `Content/locomotion/NN/prophecy_lower_body_run_b100.onnx`
- `Content/locomotion/NN/prophecy_lower_body_runtime.json`

Walk, upper and attack models and Blueprint settings are unchanged. The [Run-movement / Walk-idle refactor](RunMovementWalkIdleRefactorPlan.md) remains deferred; this installation retains current selection and blending behavior.

The model keeps the existing fixed100 batch, 152 inputs, 43 outputs and 41-state layout. Root normalization/reference, skeleton, seed and geometry agree with the previous Run contract. Its exported foot-roll contract explicitly uses `continuous_sigmoid`; the near-floor minimum pin probability is **0**, previously1, matching this checkpoint's policy settings. This is part of the matching contract installation, not a manually added pinning adjustment.

Exported with `Tools/NN/ExportProphecyLowerBodyPolicy.py`. ONNX structural validation passed. Three100-row seed/perturbed-input comparisons against the PyTorch checkpoint passed through the ONNX reference evaluator, maximum absolute error **0.000001133**. The bundled Python has no onnxruntime package; actual ORT/DirectML execution is checked inside Unreal separately.

Normal Development Editor build succeeded in86.47seconds, incorporating prior Live Coding source changes before launch. Opened `/Game/testNN` explicitly. No runtime C++ or Blueprint wiring changes were made for this installation.

Live65-frame owned-PIE check passed:41 sampled frames reported `Run=NNERuntimeORTDml`, the installed Run path, Walk0/Run1 and finite NN poses. Temporary input changes were confined to diagnostic PIE, which was stopped afterward. Unreal remains open on `testNN`, ready to Play with the new model. No full suite or asset save.

Previous Run ONNX/contract backup: `Saved/CheckpointBackups/20260928-RunBefore128231/`. Frozen source, export, contract comparison, validation and build evidence: `Saved/Diagnostics/RunCheckpoint20260928/`.
