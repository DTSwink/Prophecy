# Foot IK parity checks

The reference is generated from the unbundled lab modules, independently of
the packaged runtime. It uses the real Run181751/Upper82500 source recordings
and recorded NN replies. Every native NN request is compared too: current
and history seeds, actual root history, future root positions, and future yaw.
Recorded replies therefore cannot conceal a changed controller forecast.

For a newly accepted scene, `parity-export.cjs --fixture=<recording.fixture.json.gz>
--out=<Saved directory>` accepts repeated fixtures and keeps the frozen matrix
intact. `record-arm-fit.cjs --corpus=<Saved directory>` records its native
kernel inputs from that same independent oracle. Unreal's
`-FootIKParityDirectory=<absolute Saved directory>` selects it for
`Prophecy.FootIK.EmbeddedRuntimeParity`. Start the isolated automation host with
`-DisablePython -DisablePlugins=Fab -nullrhi -nocef -unattended`; Python startup
otherwise recreates its deleted pip environment and can attempt downloads.

`parity-cases.cjs` covers 42 solver cases: walk/run on flat ground, stairs up/down,
uneven ground, toward/parallel inclines at 0/45/90 degrees, coupled wall
walk/run, front/back/left/right slides, both turn directions, 82/85-degree
transitions, parallel slides, floor removal, and the accepted current scenes.
The compact files under `parity-fixtures/` contain inputs and NN replies only.
Generated poses belong under `Saved/Diagnostics/FootIKPort20261030`.
Six additional `app-*` cases exercise the lab's complete `Handoff.prepare`
pipeline using actual canonical multi-frame NN continuation replies. Generate
their oracle separately with `parity-export.cjs --case=^app- --out=<Saved path>`;
the original 42 expected outputs remain an independent frozen regression.
The October30 native V8 sweep passed all48 cases/26,296 frames, with zero
position and other scalar error. `native-v8-complete.json` merges the disjoint
sequential runs and retains each case's evidence file. This certifies the
solver replay; game publication, NN feedback and performance remain separate.

Run sequentially with the pinned Node 24.19 runtime:

```text
node Tools/FootIK/parity-export.cjs
node Tools/FootIK/parity-jsrt.cjs --engine=node
node Tools/FootIK/parity-jsrt.cjs --probe=<native math-enabled probe.exe>
```

The comparison checks every 120 Hz pose, all retained contact/state/root
diagnostics, events, and NN input windows. Position tolerance is 1e-8 metres;
quaternion dot tolerance is 1e-10; other numbers use 1e-8. These thresholds
were not relaxed to make the native engine pass. Native compatibility math
instead reproduces the accepted V8 operation order. See `v8-math/README.md`.

The native automation tests are:

- `Prophecy.FootIK.EmbeddedRuntimeParity`: the same full matrix inside Unreal.
- `Prophecy.FootIK.BoundedExtension`: trim-bound generation, retained prefixes,
  no unused NN endpoint, no work on shrink, and closing the session.
- `Prophecy.FootIK.CoupledNativeNNDiagnostic`: six actual native NN feedback
  runs, using three cases with recorded source and then native initialization.
  It writes pose/root/rotation errors and foot state/contact/slide-contact/root
  mode disagreements to `native-nn-closed-loop-diagnostic.json`. Semantic
  disagreement fails the test. Full outputs and NN requests/responses are kept
  as bounded JSONL captures; `analyze-native-nn.cjs` identifies the first fork
  and separates carrier motion from body-relative errors. Completion is
  explicitly not a claim of continuous numerical parity; inspect that report
  separately rather than inferring a tolerance from the observed error.
- `Prophecy.FootIK.RootBridgeExact`:405 independent root contexts and force
  receipts,22 physical forecasts and21 actual NN virtual-root/heading windows.
  Every double must match bit-for-bit; root forecasts must not advance state.
- `Prophecy.FootIK.RootBridgeCoordinates`: fixed-course centimetre/metre mapping,
  root alignment without a skeletal bind offset, ten future rows, wall thrust,
  and complete root-heap teardown on disable.
- `Prophecy.FootIK.AsyncPreparation`: canceled jobs cannot publish; cold session
  creation must leave recurrence uninitialized; the first measured pair keeps
  its frozen NN result; a prepared V8 heap transfers to the game thread.
  This test and the real-agent lifecycle checks must pass after the async
  preparation change before it is treated as verified.
- `Prophecy.FootIK.Live.JoltTargetAndFeedback`: ordinary game controller and
  live terrain correction feed the production Jolt target packet. Explicit
  completed steps align feedback with that exact target endpoint. The test
  compares corrected pelvis/leg/foot commands, including the existing physical
  ankle allowance, and checks that disabling removes the terrain contribution.
  It measures physical tracking distance separately; it does not substitute a
  target-forwarding pass for a physical tracking quality result.

The last distinction matters: bit-identical solver replay does not prove
that native float NN inference is bit-identical to the reference provider.
Small NN differences can affect contact branches and accumulate through
feedback. The closed-loop diagnostic measures this instead of hiding it.

`parity-live-stairs.cjs` is an architecture diagnostic. The causal surface
solver alone does not reproduce the lab's planned stair trajectories.
The planned-course worker must use the canonical `FootIK.prepare` path;
the live causal prototype is not a substitute for that parity requirement.

The standalone CMake probes output only below `Saved/`. `footik_v8_probe`
loads the pinned native ClearScript DLL through `FOOTIK_V8_DLL`; no CLR,
browser or Node process is involved. Optional complete native brace and entry
searches retain the canonical JS fallback; these are batched solver calls,
not individual native arithmetic callbacks.
The older `footik_math_probe` preserves the slow but exact Chakra diagnostic.
Use `--engine=v8 --probe=<footik_v8_probe.exe>` for the native V8 comparison.
`FOOTIK_DIAG_NORMAL_PRIORITY=1` permits a single normal-priority diagnostic
process when unrelated high-priority work starves background tasks. Reports
record process CPU, wall time, and peak memory separately; a wall-time timeout
under scheduling starvation is not a numerical mismatch.
The probes never start Unreal, inference servers, or viewer sessions.
`profile-live-surface.cjs` instruments a Saved-only package copy and verifies
the complete accepted405-frame motion. Its timers exclude initialization,
JSON transfer and assertions. The native thread CPU clock avoids confusing
scheduling contention with solver work. The original settled slide cost37.83ms CPU per120Hz tick on this laptop.
Exact native brace, entry and leg-contact batches, followed by ordered-comparison
and provable entry-search early-outs, reduce that to5.55–6.66ms in the retained
paired CPU measurements. Six standalone entry corridors take125ms CPU in total;
their1,162 output doubles remain bit-identical. Whole-scene405-frame solver cost
was2.375s CPU in the last measurement. These replay timings exclude NN cold
session preparation and do not establish gameplay frame rate. Use
`--label=<name>` to retain separate measurements.
`--duplicates` separately measures bounded exact-input reuse; its instrumentation
cost must not be used as a production timing. It found no duplicate arm solves
among86,299 calls,20.8% reuse among exposed leg swivels, and3.26% among entry
geometry evaluations (512 entries per owner and tick, signed zero preserved).
`parity-math.cjs` tests arithmetic compatibility before expensive solver runs.
`parity-trace.cjs` instruments a copied bundle under `Saved/` for first-fork
diagnosis; it never patches the canonical lab or the packaged runtime.

`v8-trig.js` contains a 7,907-byte Wasm module compiled from the pinned V8
13.6 fdlibm sin/cos kernels. It corrects the native distribution's libm
trigonometry while keeping all arithmetic inside V8. Its 103,806-angle
expanded test is bit-identical to the canonical Node runtime. The tiny
`scalbn` import multiplies by an exact power of two during large-argument
reduction. `build-trig-wasm.cjs` reproduces it using the pinned, contained
Zig 0.15.2 compiler and the installed wasm linker; it does not modify PATH.
The DLL, compiler and Wasm digests are in `Content/FootIKLab/V8/Receipt.json`.

`native-batch-final-complete.json` repeats all48 cases after the final exact
entry early-outs:26,296 full120Hz frames and1,024 NN windows, with zero differing
pose quaternion components as well as zero positional and diagnostic error.
This additional component check avoids confusing quaternion normalization
roundoff with a rotation difference. Earlier proof reports remain retained.

`record-arm-fit.cjs` captures original unbundled searches as binary float64
fixtures below Saved, preserving signed zero. `--kernel=entry` captures
entire immutable corridors, including normal/quality and alternate seeds;
`--finite-slabs` is a separately labeled branch experiment, not the accepted
frame oracle. `footik_arm_probe` and `footik_entry_probe` compare every
output bit. Initial proofs:634 brace fits /21,556 doubles, and6 corridors
(4 normal +2 quality) /1,162 doubles, with zero differing bits.

`--kernel=leg` records full contact selection and retained history. The initial
634-selection proof covers20,922 exact doubles. The leg kernel explicitly
assumes the canonical two-box shoe; custom profiles retain the JS path.
`verify-native-batches.cjs` checks offset typed-array views, exact output
bits and20,000 rejected calls with no partial output or out-of-view writes.

Native batching is guarded by `native-kernel-contract.json`, which pins each
canonical algorithm dependency using normalized-LF SHA-256. Packaging fails
if a dependency changes, even when broad splice markers still match. Update
the contract only after independent kernel revalidation; a receipt hash by
itself is not sufficient protection against executing stale native logic.
