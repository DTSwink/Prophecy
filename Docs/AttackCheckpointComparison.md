# Per-agent attack checkpoint comparison

`Set Attack Checkpoint` takes Agent and Checkpoint, and returns success plus Out Error.

- **Current (174664)** is the unchanged default.
- **Predictive Pin x5 (160664)** is the requested viewer's checkpoint.
- **Predictive Pin x5 Refresh 2 (184064)** is the later refresh2 viewer checkpoint, added without changing either existing enum value or the default.

Call after agent initialization, preferably delayed BeginPlay. Selection belongs to that agent, including full and half attacks. A running attack keeps the checkpoint selected when it started: changing this node, updating its target or retriggering it does not reset history, Armed, Hit or frame count. The next new attack uses the new selection. Stop + Trigger still explicitly starts a new attack. Reset stops the active attack and keeps the selected comparison setting. EndPlay removes comparison state.

`Get Attack Checkpoint` returns Selected (next attack), Effective (ongoing attack, otherwise Selected), and Attacking. First selection of each alternative loads and startup-validates that model for the owning manager; later selections reuse it. Current-only sessions never load the extra models. Simultaneous attackers are batched separately per checkpoint, with independent per-agent recurrent states and phase latches. All batches use the existing locomotion/defense/physics/recovery workflows. Loaded alternatives are retained until that manager ends; this is a temporary comparison feature, not an additional permanent policy stage.

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
