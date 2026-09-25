# Per-agent attack checkpoint comparison

`Set Attack Checkpoint` takes Agent and Checkpoint, and returns success plus Out Error.

Dropdown order is oldest first. Stored enum values are explicit, so reordering the menu does not change saved selections:

1. **September 20 - good.pt (265458)** — historical frozen-walk checkpoint (value3).
2. **Predictive Pin x5 (160664)** — first predictive viewer checkpoint (value1).
3. **Current (174664)** — unchanged default (value0).
4. **Predictive Pin x5 Refresh 2 (184064)** — later refresh2 checkpoint (value2).

Call after agent initialization, preferably delayed BeginPlay. Selection belongs to that agent for full and half **non-kick** attacks. **kickL and kickR always use September20 good.pt265458**, regardless of this selection. Changing the selection alone leaves an ongoing attack's checkpoint/history/Armed/Hit/frame count unchanged. Updating a target or retargeting between non-kick families retains that active model. Retargeting from a non-kick to a kick switches to good.pt; retargeting back switches to the agent's currently selected non-kick model, preserving recurrent state and phase/frame latches. Half kicks remain unsupported. Stop + Trigger explicitly starts a new attack. Reset stops the active attack and keeps the selected setting. EndPlay removes comparison state.

`Get Attack Checkpoint` returns Selected (non-kick choice), Effective (ongoing model, always good.pt for kicks; otherwise Selected when idle), and Attacking. First selection/use of each alternative loads and startup-validates it for the owning manager; later selections reuse it. A session using kicks necessarily loads the historical model even when its selected non-kick model is Current. Simultaneous attackers remain batched separately per effective checkpoint, with independent recurrent states and phase latches. No additional inference stage or per-tick selection lookup was introduced. Loaded alternatives remain until manager shutdown.

Forced-kick routing compiled and loaded via Live Coding2026-09-25 13:21:08UTC (23.82s incremental build). The model loader was separated from selection so forcing a kick never overwrites the user's saved choice. Failure to load/validate historical files refuses the kick rather than silently using the selected model. The new isolated switch/retarget test is `Saved/Diagnostics/TestForcedGoodKicks.py`; it was not run because the user asked to leave their active Play running and test themselves. Earlier selector checks below predate this routing exception. No asset edits/save/restart.

## September20 historical checkpoint265458

The September19 `f314e8d` and September21 `8919c05` exporter revisions both identify `training/runs/done slash 2 2/checkpoints/good.pt`, step265458, SHA256 `6a76321d6e1525c9e6bcfcedcd0ce46676b03dd15dd277c2bd87f6c834239072`. The pre-replacement export in `Saved/CheckpointBackups/20260922-234039-before-123793` agrees; source checkpoint and all three exported network hashes were verified.

The five original files are installed separately under `Content/locomotion/NN/AttackSeptember20` (about4.56MB). The existing native legacy branch preserves this checkpoint's frozen-walk model,92-wide lower input and original pin mapping. It is not decoded through the new no-frozen/cone contract. Its external dimensions, root geometry, labels, gate threshold and post-hit tails match the current agent interface. Current recovery, physical and Blueprint controls still apply; this is checkpoint selection, not a rollback of the whole September20 game code.

Loaded on explicit selection or first kick, retained by that manager, separate inference batch, cleared on manager shutdown. Current files are unchanged. Provenance/install receipt: `Saved/Diagnostics/AttackSeptember20-installation.json`. `MAX` is hidden; newly placed Set nodes retain Current174664 as their explicit non-kick default despite the historical choice appearing first.

Normal21-action editor build passed91.78s after authorized save/restart (pose Blueprint and dirty testNN backed up and saved). Live Coding's enum replacement had left the old menu and an unused duplicate Checkpoint pin; clean loading restores the canonical four-choice enum, and explicit editor repair removes only an unlinked orphan when its valid replacement exists, preserving the live selection and all links.

Owned short PIE passed2026-09-25: historical/current/predictive concurrent models, pending selection vs latched active model, target/type retrigger preserving phase/frame, full and half attacks, historical batch1→3, and return to current. Native historical startup max error0.000003919. All sampled poses finite. The first harness incorrectly required every short attack still to be active at a later sample; it now allows natural completion after separately asserting successful entry. Final result: `Saved/Diagnostics/AttackSeptember20Selection.json`. This is switching/inference validation, not a recreation of the entire September20 gameplay rollout. Test settings exist only in the owned PIE, which was ended.

## Refresh2 checkpoint184064

Viewer: http://127.0.0.1:8795/latest_predictive_pin_x5_20260924_refresh2/seed_2026092211/complete/variant_viewer.html . Its manifest and checkpoint receipt both identify step184064.

Source: `C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260922_latest_chained_variants/latest_predictive_pin_x5_20260924_refresh2/checkpoint_step184064_e0759ba5039d.pt`.

SHA256: `e0759ba5039db0db26f5dd17d58e74b72f1dc092f9f7bf6f54e4a622677f7d7b`.

Staging: `Saved/Slash184064`. Installed separately under `Content/locomotion/NN/Attack184064`. Exported using `Tools/NN/ExportCurrentSlashCheckpoint.py`;120 source transitions finite, ONNX comparisons at batch1/3/100 pass (cone exact, lower max1.669e-6, upper max2.981e-7). Native geometry/contract fields match current export exactly except network weights/hashes and expected startup output. Runtime encoding, labels and finishing rules match. Installation receipt verifies both previous sets of five files unchanged. Selection validates the exact checkpoint hash and native startup parity before committing a per-agent choice.

Normal editor build completed2026-09-24 after authorized pose-BP save/restart. Final editor-helper build26.29s after a corrected pointer declaration; game module had already linked in the preceding80.13s build. testNN reopened; all three enum choices reflected and pose BP status3/zero stale agent types. Existing node wiring/values preserved. Live Coding had temporarily retained an obsolete enum pointer; clean loading repaired it automatically. Explicit editor-only `Prophecy.Editor.RepairAttackCheckpointEnum` remains available for saved stale/null checkpoint pins, changes no defaults/links and never runs automatically.

Owned short PIE switching test passed16:15:22UTC: three concurrent models, selected/effective separation during attacks, retrigger preserving frame/Armed/Hit, stop/start applying pending choice, half attacks,184064 batch1→3, full/half headbutts, then all agents returning to current. Native startup maximum absolute error5.245e-6 for184064 and2.623e-6 for160664. Evidence `Saved/Diagnostics/Attack184064Selection.json`. Test stopped its own Play session; no gameplay checkpoint choice or graph wiring was changed in saved assets. This is a bounded switching/inference test, not a full viewer-chain or visual-quality certification.

## Original160664 installation

Requested viewer: http://127.0.0.1:8795/latest_predictive_pin_x5_20260924_refresh1/seed_2026092211/complete/variant_viewer.html

Source: `C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260922_latest_chained_variants/latest_predictive_pin_x5_20260924_refresh1/checkpoint_step160664_73a549008e88.pt`.

SHA256: `73a549008e883e3b945ce5ebdc1597c75a1a79a816e59c67e131a7af8a04a143`.

Staged exports: `Saved/Slash160664`. Alternate-only installation: `Content/locomotion/NN/Attack160664` (five files, about3.46MB). Current174664 exports were hash-verified unchanged. Export contracts have identical geometry, root frame, labels, tails, clamps and0.99 pin mapping; only network weights/startup outputs/provenance differ. Setter validates compatible runtime metadata and rejects the wrong alternative hash or failed startup parity without changing selection.

Export network checks passed at batch1/3/100: cone exact, lower max4.292e-6, upper max2.981e-7. User requested node delivery before further tests; the30-attack Python chain was stopped after19 segments, native chain/gameplay switching tests were not run. `Saved/Diagnostics/TestAttackCheckpointSelection.py` is prepared but has not been executed. Installation receipt records this limitation. No Blueprint wiring/settings changes or automatic checkpoint switch.

Build: normal GameAnimationSample3Editor Win64 Development succeeded in93.79s. User-authorized pose Blueprint save and clean editor restart completed; testNN reopened and Set/Get Attack Checkpoint plus both enum choices verified by reflection. No gameplay tests were run after the request to hand over the node. Current checkpoint remains174664 until the per-agent setter selects160664.
