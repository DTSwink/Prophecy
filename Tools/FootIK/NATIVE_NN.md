# Native Foot IK NN

`FProphecyFootIKNN` owns a single retained inference stream. Its graphs use the
frozen lab **Run181751 / Upper82500** weights; Walk is a speed command using Run
(F2.0, B1.5, sides1.8m/s). Four directional contexts retain their original seed
geometry and course axes. No current game checkpoint is substituted.

- `Prepare(SettingsJson, Error)` retains the selected graph assets and settings.
  The private preparation worker owns the object exclusively during this call;
  gameplay never performs cold graph loading or inference on the game thread.
  It accepts settings directly or a `settings` object.
- `Initialize(OutSourceJson, Error)` runs on the planner worker. It reproduces
  the lab's 60-frame settling, round-to-even gait phase, command speed and future
  yaw warmup. Incline/custom surfaces get the five initial poses; plain terrain
  gets the full requested course for the canonical offline stair planner.
- `Generate(RequestJson, OutResponseJson, Error)` implements `surface_nn.Stream`
  for `__footikNN`. Ordinary calls retain lower/upper current and previous state;
  the first/reset call encodes both supplied history poses. Missing calls during
  slide do no work, and the canonical slide-exit reset resumes from its seed pair.
  Requests with `frames > 2` implement the separate canonical `/resume` course
  used by `Handoff.prepare` after stairs/down/uneven terrain: both corrected
  history poses seed inference, the first visible pose is preserved exactly,
  and the remaining frames use actual future root/yaw commands. This course
  uses normalized origin and the authored next root; it does not substitute the
  surface stream's capped next-root decoder or overwrite retained stream state.
- `Cancel()` is thread-safe. It prevents additional inference and is checked
  immediately before/after the ONNX run and every initialization row. A current
  run may finish. Private sessions contain no retained UObjects and can release
  on the retiring worker; no recurring inference worker/timer remains.

Inference uses the engine's bundled ONNX Runtime through its C API, with private
sessions configured for one intra/inter-op thread, sequential execution and no
worker spinning. This avoids changing NNE runtime/global settings used by other
agents. Model bytes are loaded in `Prepare`; the private session initializes on
its owning worker. Native test logs mark each fixture and session start/end so
initialization and inference stalls are distinguishable.

All vectors are lab metres/Y-up. Input axes are row matrices. Root yaw uses the
existing lab command convention relative to the selected direction context.
The callback consumes previous/current plus eight future roots and yaw values;
additional forecast rows are intentionally ignored, matching the Python stream.
Actual previous displacement and every upcoming heading enter the NN. The graph
also retains the canonical capped next-root decode, lower-policy thigh/FK decode,
upper heading transform and pin outputs.

ONNX tensor layouts (single float32 row):

| Graph | Input | Output |
|---|---:|---:|
| Seed | 641: two25-body points/axes,10roots,10yaws,normalize-origin flag | 373:370recurrent state+3native origin |
| Step | 413:370state,10roots,10yaws,3origin | 710:370state,3root,75points,225axes,2pins,35features |
| Resume | same413 layout; authored next root for canonical `/resume` | same710 layout |

The optional origin normalization is used for initial command warmup and
post-terrain continuation, matching `resume_in_course`; live surface stream
requests use zero origin.
The first live callback reencodes the actual displayed history rather than
inheriting the hidden warmup stream.

Build assets with `Tools/FootIK/export-nn.py` using the project's Python/torch
runtime. It validates 72recurrent steps per direction, including run/walk speed
and positive/negative upcoming yaw, against `surface_nn.Stream`. The four exported
pairs passed with maximum point/axis error1.01e-5; this is float32 ONNX parity,
not a claim of bit-identical Torch arithmetic. `Content/FootIKLab/NN/Receipt.json`
contains widths and per-asset hashes. No Python process is used by the game.

`Tools/FootIK/verify-nn.py` builds native fixtures in
`Saved/Diagnostics/FootIKPort20261030/NN`; `--full-course` also checks full5second
initialization. The Unreal test is
`Prophecy.FootIK.NN.FrozenRootWindowAndSource`. It checks initial phase/source,
retained history, root stops/reversal/turning, reset and cancellation through
the actual engine ORT on the same worker boundary. A successful Python reference check does
not replace the normal Unreal build and this native test.

`export-nn.py --resume-only` adds four `/resume` graphs without changing the
validated surface graphs. `verify-handoff-nn.py` produces the six whole-app
continuation replies and native fixtures from canonical `Handoff.requestFor`
requests. These check both gait commands over stairs/down/uneven terrain,
including the exact first corrected pose, complete roots, headings and pins.
The six recorded browser continuations passed over 516 poses: maximum point
error 5.73e-6 metres, axis component error 1.10e-4 and pin error 1.12e-5.
All four additional resume graphs also passed their directional checks.

## Lossless transport and tensor-shape optimization — October30

Forecast consumes `GenerateResult` directly, avoiding a JSON serialization and
parse of the same result. Public `Generate` retains its JSON schema and uses
compact whitespace with the same numeric writer. Native `NN.JsonTransport`
checks recursive values, signed zero, escaped text and actual reference payloads.

The exported graphs now retain static tensor-shape metadata. No operator,
initializer, weight, arithmetic order, precision, time step or forecast horizon
was changed. `annotate-nn-shapes.py --apply` verifies the computational graph
fingerprint and every float bit before replacing an asset; repeat runs recognize
the retained receipt. All twelve graphs passed1,824 outputs across four direction
contexts, walk/run speeds, stop/reversal, yaw and vertical-root commands.
Paired one-thread inference CPU fell by roughly12–25% for the step/resume graphs
in this busy-laptop run; seed inference is too short for a useful CPU comparison.
`Saved/Diagnostics/FootIKPort20261030/nn-shapes-proof.json` retains hashes, exact
counts and measurements. Native gameplay timing remains a separate gate.

## Current coupled oracle

The 48 recorded-input solver cases remain unchanged. Their replies are fixed
inputs, so they prove solver equivalence but cannot prove that a historical
reply still answers a root window generated by the current complete system.
The old wall fixtures exposed precisely this distinction: at run call 44 the
saved reply's first pin was 0.884741485, while the same current request produced
0.903051615 in canonical Torch and 0.903051257 in Unreal. Through call 43 the
fresh Torch responses matched the old replies exactly. Same-input Torch/ORT
and recurrent-state probes stayed within 2.3e-6; the apparent 0.0183 NN error was
an outdated request/reply pairing, not a native model or encoding defect.

`re-record-coupled.py` now runs the unchanged canonical JS driver and Torch
Stream together, sequentially on one CPU thread. It saves three independent
oracles under `Saved/Diagnostics/FootIKPort20261030/coupled-current`, hashes
every actual request/reply pair, and verifies the JS peer retained those exact
replies. It never overwrites the 48 fixed-input proofs. The native coupled test
requires these files and records their directory; the analyzer follows that
metadata (or accepts `--oracle-dir=coupled-current`).

Read-only comparison of the six retained actual Unreal captures against these
fresh oracles found no contact, foot-state, slide-contact or root-mode changes
over 3,214 frames. Recorded-source wall motion differs by at most 22 micrometres
relative to the root. Native-generated source can accumulate about 5mm of root
drift; the accepted slide has up to 5.16mm arm-position drift and4.181 degrees
of joint-orientation difference. These continuous float32 differences remain
explicit and are **not** bit-identical NN parity. The actual Unreal rerun passed
as `Reports/final-native-2/CoupledNativeNNDiagnostic` with no semantic changes;
its warning explicitly separates those continuous differences. Evidence:
`coupled-current/*.receipt.json`, `coupled-wall-run-state-drift.json`, and
`native-nn-analysis-current.json` in the same diagnostics directory.

The native integration tests `Prophecy.FootIK.AgentKinematicLifecycle` and
`Prophecy.FootIK.AgentJoltTracking` create a transient world and one agent. They
generate courses through the public API and compare all 25 published body
targets and the carrier against the canonical diagnostic frames. The first
checks rotated world frames, directional commands, future yaw, stairs, a wall,
post-terrain handoff, a course longer than five seconds, cancellation, pause,
disable/ordinary-NN resume and removal of feature callbacks. The second records
Jolt tracking on a short flat course. These tests do not load a recorded pose
course or edit user assets. Build/execution status belongs in the project
journal; their presence alone is not evidence that they passed.
