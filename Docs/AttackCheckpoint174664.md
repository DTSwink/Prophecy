# Attack checkpoint 174664

Requested viewer: http://127.0.0.1:8795/best_total_172k175k_20260924/seed_2026092211/complete/variant_viewer.html

Exact source: `C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260922_latest_chained_variants/best_total_172k175k_20260924/checkpoint_step174664_3c68cbeec601.pt`.
SHA256: `3c68cbeec601b814d569c53c577812402b17cb4f94a931d657bcf3f8f9b5a61f`.

The training receipt and viewer manifest both identify step174664, the lowest saved training total loss in the requested172k–175k interval. This is the requested checkpoint, not latest184064.

Relative to123793, inference retains the same architecture, geometry/clamps, actual-Armed-before-Hit behavior, recurrent inputs and GT tails. The executable pin-strength contract changes to `clamp(clamp(2*sigmoid(command)-1,0,1)/0.99,0,1)`, applied once before foot projection. The export records `pin_full_strength_at`; native runtime defaults absent fields to1 for old exports and only accepts1 or0.99. Remaining recipe differences are training loss coefficients and provenance paths. No Blueprint recovery/clamp/tempering settings are changed.

Staging: `Saved/Slash174664`. Export validates cone/lower/upper at batches1/3/100; maximum neural-output error2.146e-6. `ValidateCurrentSlashChain.py --staging Saved/Slash174664` generates the same30-request seed2026092211 and native audit fixture. Installation is gated on the native chain audit, with prior exported files backed up under `Saved/CheckpointBackups`.

Installed September24. Python replay exactly matches all448 stored viewer frames: zero position, rotation or target differences and identical30 segment records. Unreal autoregressive replay passed446 transitions with maximum joint-position error0.015556mm, one-step error0.001352mm and matrix-entry error0.000132. All Armed/Hit latches match. Reports: `Saved/Slash174664/viewer_reference_comparison.json` and `unreal_chain_audit.json`.

Live Coding build passed248.58s and loaded10:09:32UTC. Installed-model startup/parity check passed; all five Content export files have verified hashes. Previous exports backed up to `Saved/CheckpointBackups/20260924-101457-before-174664`; installation receipt retained in staging. Idle editor model cache cleared before the private model layout update and after installation; next Play prepares the new checkpoint. No active user Play, Blueprint/map changes, restart or push. Verification was numerical, not a simulated gameplay rollout.

The new runtime pin mapping and checkpoint allowlist are currently loaded through Live Coding. Include these changes in the normal editor DLL before the next fresh launch, following the existing journal restart/build rule.
