# Robotic crawl AE1

October17 updated-source retrain completed locally:
`Saved/RoboticCrawlAE/runs/20261017_123736_updated_crawl_idle_2x512` is current.
Latest native crawl SHA2e849ce9c900 and idle SHAc2c11c9bd05e replace the archived
native inputs; the two LAFAN robot clips remain unchanged. Same2x512/latent128,
features, equal-clip weighting and split rules. Stopped at3500, best1500,
validation MSE0.0612601,75.1seconds. Export/gradient/basic-corruption checks pass;
scorer SHA8a745d44b428c5752d3e832be0f11c9a6979154e94dc490b31b10575175d5e5c.
`--native-sources` accepts checksummed run-specific replacements without editing
the user's saved Cutter dataset. Existing LAFAN dependencies may pass a known
limit-only revision only when original backup hashes and geometry/frame fields
match exactly. Heading/fixed three-pose-frame contract unchanged. Offline only;
no AE reward in the crawl policy. Tiny within-clip holdouts retain prior limits.

October17 update: user added `crawl_idle.fbx` to the collection. Current pointer
now selects `Saved/RoboticCrawlAE/runs/20261017_053724_crawl_idle_2x512`:
four clips, same 2x512/latent128 architecture, equal offline clip weights;
early stopped at3,000 updates, best at1,000, validation MSE0.063653,39.2seconds.
Export/gradient and basic corruption checks passed. New idle is48frames/30Hz,
with31/2/3 train/validation/test windows. This small split is not independent
generalization evidence. Old three-clip runs below remain immutable baselines.
The user explicitly reserved this AE for later perturbations; the current crawl
policy uses the loco MSE objective with no AE scoring. See `Labs/CrawlTraining`.

User-authorized **local crawl-only AE**, separate from locomotion. Exactly the
three selected motions from `Documents/Lafan Cutter/datasets/crawls_uefn` are
used. No idle/walk/run additions, policy training, cloud job, PHAT change, or
viewer change. This is a motion prior for a separate future crawling agent.

## Current run

`Saved/RoboticCrawlAE/current-run.json` points to the run and launch logs.
Current requested architecture: **two 512-wide hidden layers per side, latent 128**,
1,076,757 parameters (previously 5,304,853). Run
`Saved/RoboticCrawlAE/runs/20261017_045107_crawl_ae1_2x512` completed locally using
`--reuse-data` from the first run: identical feature arrays, normalization and splits.
It uses a maximum of 12,000 updates and early stopping after eight validation
checks without improvement (2,000 updates); always exports the best checkpoint.
The original run and its source snapshot/checkpoints remain available.

The smaller run stopped at update 3,750 after 43 seconds, selecting update 1,750.
Best validation MSE **0.062789**, down 36.9% from the baseline's 0.099568.
Clean test means improved on all three clips: **0.194766 / 0.146387 / 0.062002**.
Root jitter raised costs in 100% of windows; body jump in 98.2% / 100% / 100%.
Timing shuffle still raised cost in only 2/5 windows on the second clip, and
body-jump margins remain small. Maximum tested yaw/XY score drift was 7.78e-5.
Exported scorer parity, input gradients and artifact hash checks passed.
`baseline-comparison.json` confirms identical prepared-feature hashes and
records the comparison. These reused within-source holdouts support choosing
the smaller candidate, but are not independent generalization evidence.

Initial baseline run: `Saved/RoboticCrawlAE/runs/20261017_044043_crawl_only_ae1`.
Its `status.json` records preparation/training/completion/failure; `metrics.jsonl`
and `tensorboard/` record training. `completed.json` is written only after all
updates, scoring diagnostics and exported-scorer checks succeed. No scheduler
or automatic agent-training integration is installed.

Baseline completed October 17, 2026: 12,000 updates in 382 seconds on the local RTX 4060.
Export uses the best validation checkpoint at update 1,000, with equal-clip
validation MSE 0.099568. Later training overfit: final training MSE 0.0000275,
final validation MSE 0.213484. `scorer.pt` passed exported-score parity and finite
input-gradient checks; its SHA-256 is recorded in `completed.json`.

Baseline held-out diagnostic results:

| Clip | Test windows | Clean mean MSE | Root jitter: cost increased | Body jump: cost increased | Timing shuffle: cost increased |
| --- | ---: | ---: | ---: | ---: | ---: |
| ground1_subject5 | 452 | 0.290566 | 100% | 94.7% | 100% |
| ground2_subject3 | 5 | 0.238665 | 100% | 100% | 40% |
| crawl | 4 | 0.074514 | 100% | 100% | 100% |

Maximum score drift under the tested global yaw/XY change was 9.27e-5.
The basic jitter/body-jump check passed, but body-jump margins were small
(median cost increases 0.0010–0.00235), and timing-shuffle discrimination was
inconsistent in the second clip. Only 5 and 4 test windows exist for the short
clips. Treat this as a first crawl-prior integration candidate, not a validated
controller reward or a general motion-quality classifier. No policy was started.

Run with `Saved/Robotics/env/Scripts/python.exe train.py --run <new-directory>`.
Existing runs are never overwritten. The process is launched hidden with below
normal CPU priority; it shares the local RTX 4060 with existing applications.
Default maximum 12,000 updates, batch 512, seed 1234, AdamW 1e-3/weight decay 1e-5.
Early stopping defaults to eight checks without improvement (`--patience 0` disables).
Learning rate drops to 3e-4 at 70% and 1e-4 at 90% of the configured maximum.
Architecture is the user's smaller variant of Run AE1:
two 512-wide Linear/LayerNorm/GELU layers each side, latent 128 with GELU,
linear reconstruction output. Fresh weights, no input noise, normalized MSE.
`Autoencoder(1024, 3)` can reconstruct the old architecture for checkpoint loading;
old standalone TorchScript scorers remain independent of this default change.

## Motion and feature contract

15 physical bodies in the saved `data/dataset.json` order, 34 articulated DOFs
including wrists. The two LAFAN robot exports are reused unchanged. The third
UEFN FBX-derived BVH is projected through the same current robot hierarchy and
independent foot correction into a **run-local** motion file. It skips LAFAN
axis/proportion mapping. Its 58 foot corrections peak at 0.288 cm. The source
dataset and viewer remain untouched.

Generalized coordinates are resampled at 30 Hz: root translation linearly, root
and ball rotations using quaternion SLERP, hinges using unwrapped angles.
FK after resampling preserves rigid target lengths. Resampled counts: 3042, 66, 55.
No interpolation across clips or artificial cyclic boundary.

Input consists of three consecutive poses, 135 values per pose, 405 total.
Per body: position in metres, then the first two rotation-matrix columns
(column-major, six values). Shared `features.encode` defines preprocessing:

- Origin is the first pelvis XY at the ground-plane height.
- Rotation removes only first-pelvis heading. Pelvis local -X is projected onto
  the horizontal plane; near vertical (horizontal norm<0.25), projected +Y gives
  the corresponding heading instead. Both branches are global-yaw equivariant.
- The frame remains fixed across all three poses. Height above ground, root
  displacement, pitch, roll and turning within the window remain encoded.
- Runtime must use actual physical body origins/orientations in the same model
  convention. Reset history between episodes; no score until three poses exist.

Each clip has chronological 70/15/15 training/validation/test blocks with three
excluded frames between blocks. Windows share no pose frames across splits.
Training windows: 2127/44/36; validation: 451/5/3; test: 452/5/4. This is a small
within-source holdout, not an independent-motion generalization claim.
Equal per-clip sampling prevents the 101-second selection from dominating.
Normalizer uses only training blocks, with equal clip weights; standard-deviation
floors of 0.02 m for positions and 0.05 for rotation components avoid unstable scaling
of constant features. Validation checkpoint selection also weights clips equally.

## Validation and use

Preparation verifies global yaw/XY-translation invariance, near-vertical heading
fallback, retained height/movement/tilt, finite gradients, sources and existing
retarget dependencies. Receipts: `data/preflight.json`, `data/dataset.json`.

Every 250 updates save `checkpoints/latest.pt` and, if validation improves,
`checkpoints/best.pt`, including optimizer and torch RNG state. After training,
the best checkpoint is evaluated against untouched test blocks and diagnostic
root jitter, body displacement, and mismatched final poses. These corruptions
are **evaluation only**, not extra training animation. Results and raw cost
calibration are in `score-validation.json`. Failed discrimination is reported
as requiring review; it does not silently change the recipe or deploy a reward.

`scorer.pt` is a frozen TorchScript scorer accepting `[batch,405]` unnormalized
features and returning normalized reconstruction MSE per sample, lower being
more familiar. `features.py` must be used for both offline and runtime input.
Weights are frozen but input gradients remain available. No reward coefficient,
confidence interpretation, or physical-controller wiring is chosen here.

Retarget hand-contact deviations and existing locomotion-limit violations are
retained as approved reference data. This AE does not correct them, establish
balance, or guarantee long-horizon crawling. The window spans 2/30 seconds.
