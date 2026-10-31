# Bodyflip integration - October 30, 2026

User goal: approved checkpoint, throws, predictive aim during bodyflip, all-spin secondary motion, lossless optimization, full contained Unreal port.

- [x] Push approved checkpoint67516390; remote verified, saved scene snapshot included.
- [x] Secondary motion default60% for all spin changes; explicit saved zero retained.
- [x] Reuse approved Throw evaluator, Big/Small selectors, charge and release data; same Jolt world.
- [x] Aim from complete future composed pose; direct attacks reach correction at Armed, circular at Hit; throw release velocity aimed at target.
- [x] Visual/numerical rotation/target/attack/throw tests, deterministic seeking and handoff.
- [x] Lossless hot-path parity and bounded CPU benchmarks.
- [x] Native live runtime/control/root/contact/spin/attack port, independent of FootIK work.
- [x] Feed the actual native PHAT mass, constraints and contact shapes into the native solver; retain the lab's existing profile and all saved Unreal tuning.
- [x] Normal build, native parity and isolated Unreal verification; preserve existing editor/Play/BP.

Earlier ownership: parent app/aim integration, throws agent dedicated throw + physics/renderer + dispatch, spin agent spin/contact optimization, native agent new Bodyflip native files. Final fixes and validation completed in the parent, without new workers or desktop takeover. New integration remains local; only the approved checkpoint67516390 was pushed.

Native completion evidence:

1. Normal dynamic-UBA/NoPCH build succeeded in155.23s (`build-entry-return.log`). Reused one isolated DLL-copy host with shared asset junctions and no PDB copies. The user's editor, Play session, Blueprint wiring, PHAT and saved tuning were not changed.
2. Embedded parity, trim extension, V8 interrupt/recreation, heap-budget/recreation, native NN continuation, failed-generation error retention, queued execution budget and overlay ownership pass. Four native NN profiles/64poses match PyTorch within9.65e-6. Approved260-frame scene completes with real NN in62.737s; this remains a material preparation cost.
3. Finite parent, anchor carry and integrated finite-parent diagnostics pass, with the coarse-step constraint response documented in `Docs/BodyflipNative.md`. Native heading, entry and general blend regressions pass. Three obsolete F59 expectations fail identically before/after the transition correction; the other76 historical knee-test checks/metrics remain identical.
4. Final actual physical run:5/5 Success, no errors (`Reports/release-final/index.json`): kinematic/sim, Big Throw, Small Throw, one-hand and two-hand pushes. The base case has the deliberate unrecorded-projectile-seek warning; the other four report attack self-collision owner lifetime ending at world teardown. Both palms register solved floor impulses during the paired push. Position/rotation/segment thresholds were not relaxed. One-hand segment discrepancy2.954cm is a narrow pass against3cm.
5. All five final collider sheets and dense hand contact/release frames inspected. Native hinge solver passes7,224 checks; spinning hand history passes248 checks/73frames including both unequal release boundaries and reverse seeking. Ordinary lab profile retains20 byte-identical complete outputs.
6. Final Runtime SHA256 `caf24be9d5809cdba6fc0161e7439c46ba52f1b127e4b185a2e023a8e46e90a5`. Node/V8 native-profile parity:24frames/5,216 numeric values, zero difference across kick, foot and paired-hand cases. Historical receipts and failed attempts remain distinguishable from the accepted final package. No aggregate speedup claim from paging-affected timings.

Runtime use is opt-in through `StartBodyflip`; see `Docs/BodyflipNative.md` for control API, units, ownership and limits. This validates the contained runtime and transient native test worlds, not a new user-authored Blueprint workflow.

Storage: about12.5GiB free at handoff. Reused the host, reports and image paths. Automatic approval review rejected cache cleanup, so that attempt deleted nothing; no equivalent deletion was retried. No owned headless Unreal process remains running.

Later user-authorized Recycle Bin cleanup succeeded:8 disposable cache/obsolete
engine/archive paths,181,474,003bytes (173MiB), no permanent deletion. Working
host binaries, packaging tools and evidence retained. See `recycled-files.json`.
Recycled files still occupy disk space until the bin is emptied.
