# Shared defense checkpoint pickers

**Set Parry Checkpoint** / **Get Parry Checkpoint**:

- Project Default: installed Parry1149700.
- Frozen Parry1149700,1178405,1216457.

**Set Dodge Checkpoint** / **Get Dodge Checkpoint**:

- Project Default: installed Dodge322925.
- Frozen Dodge322925 and Dodge151341 (October7 inertia x3 run).

Connect any initialized agent as `Agent` (Self works). Selection affects **all
agents using that agent's locomotion manager**, like Set Upper Checkpoint.
Parry and Dodge selections are independent. Setters return success and Out Error;
getters return false for an uninitialized/invalid agent. Call after registration,
for example from delayed BeginPlay. Nothing selects a new model automatically.

Selections last for the manager's lifetime; new Play starts on Project Default
unless your Blueprint selects another. Named choices are frozen exports under
`Content/locomotion/NN/defense/pickers/`; defaults remain the normal installed files.
Current1149700 exactly matches the supplied parry_step_1149700.pt source hash.

Changing selection loads and validates a candidate model before replacing the
existing model. Failure keeps the previous selection and network. Repeating the
same choice returns immediately without reloading. Before the first defense,
the validated candidate is retained and moved into the lazy runtime once.
During defense, a change takes effect on the next existing policy inference:
pose history, attack target, bank usage and timers are preserved. There is no
crossfade, so switching during an action can visibly change its next prediction.

The existing single batched Parry inference and existing Dodge batching remain
unchanged. There is no picker lookup, new scan, timer or extra inference per tick.
Model binding/selection work happens only at initialization/selection/destruction.

Dodge151341 has exactly the same frozen walk/run model bytes, lower settings and
bank capacities as322925, verified by the exporter. Both therefore reuse those
unchanged lower assets; only Dodge upper policy weights switch. The checks reject
a future checkpoint with different lower behavior instead of silently mixing it.
All supported choices retain their required exact-forearm projection contract.

`Tools/NN/BuildDefensePickers.py` stages through the established defense exporter,
checks saved/random PyTorch-to-ONNX batches, freezes named choices and verifies
that all installed defaults remain unchanged. Native picker tests use its oracles
at `Saved/Diagnostics/DefensePickers20261008/export/validation.json`.
The game build stages the frozen ONNX/metadata files and both default checkpoint
metadata files. The original trainer checkpoints are not read by Unreal at runtime.
