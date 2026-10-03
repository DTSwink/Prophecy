# Shared upper checkpoint picker

`Set Upper Checkpoint` takes Agent, Checkpoint, and Out Error, returning success.
It selects the upper locomotion network for **every agent in that agent's manager**.
Call after registration, for example delayed BeginPlay. `Get Upper Checkpoint`
reads that shared selection (false for uninitialized agents or custom model paths).

Choices:

- **Project Default**: the standard `Content/locomotion/NN/prophecy_upper_body_*` files,
  restored to step82500 on October1. Future explicit refreshes may replace these.
- **October 1 - Previous (82500)**: frozen original upper checkpoint.
- **October 1 - Hand Velocity Bound (85750)**: frozen earlier hand-velocity-bound checkpoint.
- **October 1 - Hand Velocity Bound (86750)**: frozen checkpoint from the October 1
  20:37:52 training run, added on explicit request. Existing enum values are preserved;
  this choice uses value 3. Project Default and the node's default selection remain 82500.
- **October 1 - Hand Velocity Bound (83750)**: frozen checkpoint from the October 1
  22:31:23 training run, added October 2 on explicit request. Uses enum value 4;
  all earlier enum identities and the default selection are preserved.

Named pairs live in `Content/locomotion/NN/Upper82500`, `Upper85750`, `Upper86750` and `Upper83750`.
Each installed pair's ONNX hash was checked against its runtime JSON.
82500 comes from `Saved/CheckpointBackups/20261001-174707-UpperBeforeRefresh`;
85750 is the supplied s8 handvelbound model installed immediately before this picker.

86750 source:
`C:/Users/singerie/Documents/Cursor/stepper/training/runs/20261001_203752_ik_upper_cached_ae1ae4_bs64_allk32_blend_noise50_initgaze50each_handvelbound/checkpoints/checkpoint_step_086750.pt`.
Its source was frozen with matching before/copy/after hashes and exported with the
existing upper exporter. ONNX format validation and the full nonmetadata runtime
contract comparison passed. ONNX ReferenceEvaluator matched the PyTorch startup
audit over the fixed 100-row batch with maximum absolute error **1.9371509552e-7**.
This validates export parity, not gameplay motion quality. The six existing default/
82500/85750 files were verified unchanged.

- Source SHA-256: `CAD549A41D20A075087B7E8DF3DD47EE377EB82C270EB041FA21532CB8BD8F40`.
- ONNX SHA-256: `238E9C9B7F046C2DC714BD16998C41D27226D9DE5E175639CCB532DAA8FD2A14`.
- Frozen source/export/receipt: `Saved/Diagnostics/UpperCheckpoint86750-20261001-230751/`.
- Addition receipt: `Saved/Diagnostics/upper_picker_86750_install.json`.

83750 source:
`C:/Users/singerie/Documents/Cursor/stepper/training/runs/20261001_223123_ik_upper_cached_ae1ae4_bs64_allk32_blend_noise50_initgaze50each_handvelbound/checkpoints/checkpoint_step_083750.pt`.
The source was frozen with matching before/copy/after hashes. Existing exporter,
ONNX validation and full nonmetadata contract comparison passed. ONNX
ReferenceEvaluator matched the PyTorch startup audit over the fixed 100-row batch
with maximum absolute error **1.6391277313e-7**. All eight existing default/named
model and contract files were verified unchanged. This validates export parity,
not gameplay motion quality.

- Source SHA-256: `3156BD02241D4516AF3A02B749BDA7DD31687F009D406A2C87F7F410D37BB680`.
- ONNX SHA-256: `BD650E6F8FED7D33A6F0551E9E774E522534C4046D4DCBE215286F146D2CDD20`.
- Frozen source/export/receipt: `Saved/Diagnostics/UpperCheckpoint83750-20261002-013908/`.
- Addition receipt: `Saved/Diagnostics/upper_picker_83750_install.json`.
- Live Coding loaded October 1 **23:44:22 UTC** (October 2 local). Native enum
  reflection verified all five choices, including value 4/name/display label, via
  `KismetNodeHelperLibrary` (Python's cached enum wrapper is stale after reload).
  User Play was preserved; Blueprint references were checked after Play ended.

Selection changes synchronously load the model and check contract compatibility and
the existing startup parity audit. Failure restores the previous model and paths.
Repeated selection of the active choice does not reload. Selection preserves all
agents' pose/history and applies to the next upper update, including existing hand
recovery sources. A live weight change is not a pose crossfade; select at startup
for repeatable comparisons. The choice lasts for this manager's lifetime; wire the
node at startup to choose a named model each Play session.

There is no additional per-tick branch, model, or inference pass. No attack/run/walk
model, Blueprint wiring, or tuning was changed. Only one upper model remains active;
switching to another model loads it on demand rather than retaining two copies.
