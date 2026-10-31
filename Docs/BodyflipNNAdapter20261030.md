# Native Bodyflip NN adapter

October 30, 2026. `ProphecyBodyflipNN.cpp` implements the standalone lab's
resume-service boundary with independent CPU NNE instances. No gameplay Python,
Node process, shared locomotion-manager buffers, or agent mutation is involved.

The exporter (`Tools/Bodyflip/export-nn.py`) packages the frozen lower/upper
policies and their original encode/decode operations into fixed ONNX graphs.
There are four profiles: run/walk, each drawn/unarmed. A profile contains a seed
encoder, recurrent step with full-body decode, and two-pose phase seeds.

| Graph | Input | Output |
| --- | --- | --- |
| Seed | 606 floats: two poses' points, then axes, then two roots | 370 floats: previous/current lower, previous/current upper, previous/current pelvis, upper base |
| Step | 402 floats: recurrent state without current pelvis, current/next root, 35 root commands | 530 floats: next lower, upper, pelvis, base, 25 positions, 25 axis matrices |

All matrices and positions stay in the lab's Y-up metre convention at this
boundary. The Unreal pose adapter converts them later. Large world coordinates
are shifted together before inference, preserving the body relative to its root.

`GenerateNN` accepts either the full lab resume request (two poses including the
virtual root, complete bone names, a root command window and frame count), or an
initial `{gait, drawn, phase, duration}` request. The latter selects the same
nearest phase slot with Python's round-to-even rule, then runs fresh recurrence.
The first output pose is the exact supplied current pose. No landing blend or
unrelated gait restart is inserted.

The continuation object contains `origin`, `previous`, `current`, `prev_upper`,
`cur_upper`, `prev_pelvis`, `cur_pelvis`, and `base`, using the original nested
single-batch arrays. Extension restores this internal state instead of deriving
it from the displayed skeleton. The encoder still supplies the seed diagnostics.

`PrepareNN(gait, drawn, error)` loads the selected graph bytes and creates retained
model-data objects on the game thread. Module startup also creates the rooted
ORT runtime and its settings CDO. Heavy CPU model optimization, instance creation
and tensor setup happen lazily during the first worker `GenerateNN` call. The
registry lock is separate from the work lock, so another game-thread preparation
cannot wait behind inference. No worker creates a UObject or dispatches a
synchronous game-thread task. Calling a cold, unprepared profile from a worker
fails explicitly. Recurrent history belongs to each request, not the registry;
the Agent argument is deliberately unused.

This split follows the installed UE 5.7 CPU implementation in
`NNERuntimeORT.cpp` and `NNERuntimeORTModel.cpp`: CPU model-data conversion mutates
only the privately retained model-data cache; CPU instance creation and tensor
setup have no game-thread operation. The dedicated work mutex protects these
objects. The DML backend's different thread requirements are irrelevant here.

## Verification status

The coordinated native build and `Prophecy.Bodyflip.NN.InitialAndContinuation`
automation passed. The initial models were created on a worker for every profile.
Game-thread preparation took 0.108-0.162 seconds; first worker initialization plus
its eight-frame rollout took 7.342-8.009 seconds. Uninterrupted and continued
native rollouts matched exactly (maximum difference zero).

The independent original-PyTorch comparison then passed all four 16-frame native
rollouts. Maximum errors across profiles: positions 9.537e-7 m, rotation-matrix
elements 9.641e-6, full recurrent continuation 1.073e-6, seed upper state
1.193e-7. Root commands and seed lower state matched exactly. Receipts are
`Saved/Diagnostics/BodyflipPort20261030/NN/python-parity.json` and
`nn-native-parity.log` in its parent folder. These results verify the NN boundary;
they do not imply the separate native agent/full-solver tests passed.

Automation `Prophecy.Bodyflip.NN.InitialAndContinuation` checks all four profiles:
worker-side cold initialization, exact initial seed, phase midpoint rounding,
16-frame uninterrupted output versus
an 8-frame prefix and 9-frame continuation, plus rejection of incomplete history.
It writes native request/actual JSON pairs to
`Saved/Diagnostics/BodyflipPort20261030/NN/` for independent Python-reference
comparison after the build. The export tool separately validates its graphs
against the original PyTorch functions.

The Windows TorchScript ONNX exporter initially crashed on a zero-width
core-joint tensor in the lower-only codec. A literal reshape dimension of zero
was emitted with ONNX's copy-input-dimension meaning. The exporter now folds
known empty reshapes to exact empty constants, within this export process only.
No installed library, frozen policy, or live lab service is changed. Normal
ONNX shape inference, model checks and CPU execution remain enabled. All four
profiles passed 45 recurrent reference comparisons each. Maximum absolute float
differences were 1.29305e-5 (run unarmed), 2.18898e-5 (run drawn), 2.43634e-6
(walk unarmed) and 2.11596e-6 (walk drawn). The checked graphs and banks have
SHA-256 hashes in `Content/BodyflipLab/NN/Receipt.json`.

`Tools/Bodyflip/verify-nn-native.py` emits original-policy request/result fixtures
from the phase banks, or consumes the native automation receipts and compares
positions, axes, roots, encoded seeds and complete continuation state. Native
comparison is explicitly required with `--require-native`; generated fixtures
alone are not evidence that the C++ adapter passed.

The heading fix in `spin.js` is related native parity work: the authored idle
root's local Z is vertical, unlike an NN root's local Z. Heading now uses local
minus Y when Z has no horizontal component. This removes an atan2 result based
on floating-point noise. The 96 heading and 161 analytic spin checks pass.
