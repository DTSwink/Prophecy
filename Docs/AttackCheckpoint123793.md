# Intermediate attack checkpoint — step 123793

Source: `C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260923_pin_x12_latest_fetch_005607/checkpoint_step123793_d467d60bd11e.pt`.
SHA256: `d467d60bd11e4c07408297047249161309b2bee3e7b0f086fae22c929821e7ad`.

This is a new inference contract, not a weights-only replacement of the September6 good.pt export. Lower input is51/current-state only, with no frozen Walk proposal or inference. Upper remains217 inputs/92 outputs. Both held histories, root-space conversion, recurrent carry and the existing independent agent batching remain.

Training's actual-Armed-before-Hit latch replaces the old early-Hit-to-Armed rule. The lower stage applies learned pinning, then the checkpoint's257-sample pelvis/leveled-foot cone, then its floor-safe calf-distance band of rest length±5cm. Upper inference includes the checkpoint's forearm-distance band and left-wrist55degree swing limit. These corrections feed recurrent state and FK, rather than changing only presentation.

The Blueprint-controlled extension-only NN correction has been removed at the user's request. It previously projected the foot onto the calf axis and clamped extension to[0,Leeway], rejecting compression permitted by training and potentially lowering a planted foot. It no longer rewrites foot/toe targets at publication or animation interpolation, captures outgoing extension, or adds it to locomotion reconstruction. Physical joint allowance and its60-tick-per-authored-second return remain. While that allowance is positive, the physical foot target follows the published NN foot instead of being independently projected back to the calf end. Explicit mode-specific clamps and physical joint constraints remain separate user controls; this does not promise identical simulated and kinematic positions.

Export tool: `Tools/NN/ExportCurrentSlashCheckpoint.py`; staging and numerical evidence: `Saved/Slash123793`. The exporter writes no training files or live Content assets. Existing optional headbutt GT preparation, half attacks, pelvis inertia, recovery controls and Blueprint graph wiring remain available.

The user-linked viewer uses step120943, not123793. `Tools/NN/ValidateCurrentSlashChain.py` reproduces its seed2026092211 and30 complete requests using123793, with original GT post-Hit tails and continuous recurrent history. It writes461 transition inputs/outputs for an isolated native audit. The audit can load staged models without replacing gameplay files.

Validation: all three ONNX exports passed batch1/3/100 comparisons; maximum neural-output error2.87e-6. Unreal's461-step/30-attack autoregressive replay matches Python within0.012884mm in joint position and0.000108 in rotation-matrix entries. All Armed/Hit latches match; teacher-forced one-step positional difference stays below0.001416mm. The initial mismatch came from using the absolute box minimum in the calf band rather than training's rounded contact calculation; corrected before installation. Evidence: `Saved/Slash123793/unreal_chain_audit.json` and `chain/complete/manifest.json`.

Installed September23 after native validation. Prior models are preserved in `Saved/CheckpointBackups/20260922-234039-before-123793`; installation receipt is in the staging folder. Final normal editor build passed36.98s. Installed-model startup max absolute error1.818e-6, Blueprint status3 with preserved wiring, KickFootLeeway and AttackLegClamps tests passed. Unreal reopened on testNN. These are numerical/model and focused regression checks, not a gameplay simulation rollout.
