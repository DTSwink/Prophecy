# Defense checkpoint update — October 5, 2026

Requested files:

- Dodge: `20261004_150744_dodge_bs256_unchanged_resume_8h_step322925.pt`
- Parry: `parry_step_1037725.pt`

Both source files are under
`C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/`.
Source hashes, installed model hashes and rollback provenance are recorded in
`Content/locomotion/NN/defense/dodge_checkpoint.json` and `parry_checkpoint.json`.

This is a complete checkpoint update. Dodge includes its embedded walk/run
networks (both identity `0f2565ac…`), continuous learned pin probabilities without
the old forced minimum, and six movement budgets: 0.6m pelvis/each foot/root,
10 degrees pelvis rotation and 30 degrees root yaw. All 17 trained attack labels
use those same budgets. The changed pelvis-drop weight is loss bookkeeping only,
not an inference limit.

Both trainers now project wrist positions to exact forearm rest lengths before
FK decoding and recurrent feedback. The runtime performs that same projection,
using only the seven shoulder ancestors and two elbows. All rotation channels
are retained. This is distinct from the existing UE presentation correction.
The contract is latched from metadata when each upper model loads; old loaded
models and original regression fixtures retain their original behavior. No
retained runtime structure, Blueprint pin, locomotion model or attack model was
changed for this update.

`Tools/NN/InstallDefenseCheckpoints.py` reproduces export, compatibility checks,
PyTorch/ONNX comparisons, trainer forearm fixtures, backup and installation.
The staging/rollback folder is
`Saved/DefenseIntegration/CheckpointUpdates/Defense20261005/`; `backup/` contains
the previous installed files. Restore those model/settings/metadata files
together and remove the newly added parry metadata when rolling back. A new Play
session loads changed files; an existing manager retains its loaded models.

All four exports passed saved-input and random-batch comparisons (batches 1/4/17):
17 cases each for dodge upper/walk/run, 15 for parry. Maximum absolute network
error was 2.02656e-6. `validation.json` contains additional native-runtime checks
and 24 trainer forearm projection cases, including collapsed-wrist fallback.

The normal Development Editor build succeeded. An isolated hidden Unreal
process on the Entry map passed all three requested tests at 00:56 Warsaw on
October 5: `CheckpointUpdate20261005`, `GeometryReference`, `NeuralReference`.
The installed four models passed native NNE batches 1/4 (maximum absolute error
2.02656e-6). All 24 forearm cases matched the trainer within 5.96046e-8m, retaining
every non-position channel exactly. Original geometry/neural fixtures still
pass with their old contract. Automation report:
`Saved/DefenseIntegration/CheckpointUpdates/Defense20261005/Automation/index.json`.

No authored Blueprint/map was edited or saved by this update, and no existing
Play session was stopped. The hidden test process exited. No new live fight
rollout or visual defense-quality result is claimed. Changes are local; no push
was requested. Start a new Play session to load the installed checkpoints.
