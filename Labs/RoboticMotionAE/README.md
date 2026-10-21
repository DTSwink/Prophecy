# Robotic Motion AE — corrected full-body selection

## Current architecture comparison — October 19

User requested a smaller AE trial. Trained fresh 2x512 hidden layers per side,
latent 128, 1,076,757 parameters. Used the exact existing features file, train-only
normalization, splits, sampling, AdamW settings, seed and 12,000-update budget.
Selected the lowest validation checkpoint, step 12,000, before test evaluation.

| Model | Train MSE | Validation MSE | Test MSE | Validation/train |
| --- | ---: | ---: | ---: | ---: |
| 3x1024 | .00099659 | .03046036 | .02914211 | 30.56x |
| 2x512 | .00124428 | .01405949 | .01231863 | 11.30x |

Smaller improves validation 53.84% and test 57.73%; recommended of these two.
Training took 133 seconds. Synthetic corruption fractions above clean remain
100% root jitter, 99.32% body jump, 100% mismatched final pose among eligible clips.
There is still a holdout gap. One seed and within-motion splits do not establish
unseen-motion or noisy-policy quality. Test is now a comparison set, not untouched.

Portable smaller bundle: Saved/MotionRegularizer-2x512. The previous 3x1024 bundle
remains Saved/MotionRegularizer; no controller loss or running policy was changed.
Evidence: Saved/RoboticMotionAE/20261019_mse_fullbody/architecture-comparison.json
and run_2x512. Bundle verification.json records standalone loading/gradient/yaw
checks; checksums.json covers payloads.

Reproduce using train.py with --data-root Saved/RoboticMotionAE/20261019_mse_fullbody
--run-dir <new-directory> --hidden-dim 512 --hidden-layers 2. Existing run directories
are refused. package.py accepts --run-dir and records the actual architecture.
compare.py --data-root Saved/RoboticMotionAE/20261019_mse_fullbody checks shared
protocol and compares the two completed runs. No duplicate prepared dataset.

## Dataset and larger-model baseline

Current dataset contains64 motions,2457.9146seconds (40.965minutes):
-12 approved retargeted clips, unchanged from their previous seven-second trim.
-48 exact omni targets:24 unarmed and24 drawn,24 run and24 walk overall.
-2 exact idle targets: unarmed and drawn.
-2 exact physical get-up tracking targets: front and back.

User rejected the previous474-clip dataset and AE. Do not use its weights or
raw Stepper NPZ imports. That collection used the wrong native sources; its
upper-body/transition projection problems are not part of the corrected model.
Prior evidence remains under Saved/RoboticMotionAE/20261019_loco, marked rejected.

Authoritative MSE source is the exact deployed archive linked by Physical Loco (2):
Exports/MimicKitEquipment/20261019_stopped_47039/training_source.zip,
SHA73618ec950279eb97dd4cc1c9c6835d07da86f69d57449f396c3c81cfd00fe62.
Use prepared/manifest.json (50omni/idle rows) and prepared/recovery_motions.yaml
(2get-up target rows). Reset-pose IK variants are not extra motion references.
Workspace XML/limits/physics files are byte-identical to deployed model assets.
The52 extracted PKLs are byte-identical, including all40 generalized coordinates.
No new retargeting, projection, IK, limit clamp, foot correction or upper-body
freezing. Added displacement from their MSE targets is exactly zero. Existing
MSE approximation/contact characteristics are retained; do not claim perfect
source skeleton/contact matching merely because the target files are unchanged.

Saved/RoboticMotionAE/20261019_mse_fullbody holds collection/source receipts,
upper-body verification, independent-verification.json, prepared data and fresh run.
Every upper body has pelvis-relative articulation. All48 omni left upper arms
excursion28.82–90.59degrees; idles1.61–6.54; get-ups74.63–144.57. Both upper arms
exceed1degree for each omni. Viewer BVHs reconstruct those same physical anchors;
max full-skeleton float32 roundtrip error5.972e-6m. BVH exporter accepts a caller
precision tolerance2e-5m here, preserving default5e-6m elsewhere, plus world ULPs.

Fresh3x1024 hidden layers per side,latent128,5,304,853parameters. No checkpoint
loaded. AdamW1e-3/weight-decay1e-5,batch512,12000steps with original LR stages.
Three poses at30Hz; fixed oldest-pelvis XY/heading frame; height/pitch/roll and
within-window motion retained. Same405feature schema as the prior robotic AE.
Sampling50% diverse retargets,50% exact MSE targets; uniform clips then windows
within each family. Same weights define train-only normalization and validation
checkpoint selection. This prevents40minutes of long captures swamping52 short
MSE references.43,922train/14,612validation/14,612test windows. Chronological
roughly60/20/20 with two excluded pose frames between intervals; shortest18pose
loops reserve3poses per holdout (one window). Their shuffle test is untested,
not counted as a timing failure or success. No independent-motion generalization
claim. Local policy training remains stopped; no Unreal/PHAT changes.

Current viewer8875 is rebuilt with exactly64 clips. Original12 preview buffers
are reused by verified hash;52 MSE previews generated from the exact PKLs.
The verified portable neutral-worded bundle is Saved/MotionRegularizer. The rejected
bundle is archived under Saved/RoboticMotionAE/20261019_loco/rejected-bundle.
The active scorer SHA256 is e9cfe1806715214ddb25f533c10cc6d810fd98eaa6056e60a405fed2f969e1c2.

Commands using Saved/Robotics/env/Scripts/python.exe:
- Labs/RoboticMotionAE/prepare_mse.py (refuses a completed preparation)
- Labs/RoboticMotionAE/train.py --data-root Saved/RoboticMotionAE/20261019_mse_fullbody
- Labs/RoboticMotionAE/package.py --data-root Saved/RoboticMotionAE/20261019_mse_fullbody --output Saved/MotionRegularizer-candidate64

Training completed: 12,000 updates in 306 seconds; selected step 12,000.
Normalized reconstruction MSE: training .00099659, validation .03046036,
test .02914211. The substantial train/holdout gap remains a limitation.
Mean per-clip fraction above clean cost: root jitter 100%, body jump 98.99%,
mismatched last pose 100% among tested clips (one-window clips excluded).
These are synthetic short-window checks, not real policy perturbation results.
Portable export parity, standalone CPU loading, finite nonzero input gradients,
and heading/horizontal translation invariance passed. Bundle verification.json
and checksums.json record the promoted payload. No controller integration occurred.
Full training/export metrics: run/completed.json. Viewer proof: viewer-verified.png.
