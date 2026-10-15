# Physical recovery lab

Contained robotics work: original UEFN PHAT -> MuJoCo Warp get-up training -> isolated Jolt validation. This does not replace gameplay locomotion or sword motion.

## Acceptance gates

1. Regenerate geometry, mass/inertia, skeletal hierarchy, constraint frames, original angular limits and disabled collision pairs from the original PHAT. Record asset hashes and tool versions. Reject unsupported geometry/constraints rather than silently approximate them.
2. Verify coordinate conversion numerically and with rendered reference/fallen poses. Calibrate simple drops, sliding, angular response and joints between MuJoCo and Jolt before humanoid training.
3. Benchmark CUDA-graph batched simulation and PPO locally. Begin with one settled fallen pose, then a bank of static fallen poses. Report actual held-out recovery and standing stability, not just reward.
4. Run the exported checkpoint through an isolated Jolt rig with the same observation/action/material contracts, without locomotion magnetization. Diagnose transfer failures before changing training.
5. Add a physical-checkpoint mode to Stepper Model Viewer, heavy-cube launches on Space, and live training replays using the existing replayer.

The decision log is [PhysicalRecovery.md](../../Docs/PhysicalRecovery.md). Generated environments, upstream checkouts, exports, caches and checkpoints live in ignored `Saved/Robotics/`. Source and compact manifests belong here. Preserve user assets and existing viewer modes.

## Current state

Export and all23 collider checks pass. Explicit PD experiments exposed numerical instabilities and remain blocked. Native implicit-damped motors pass force, settling, random and recorded-failure tests. Current learning uses Jolt's no-gyro convention, summed action-change penalty and upstream timestep-scaled rewards. The original Jolt body-speed cap and saturated motor integration remain measured transfer differences. No successful recovery or cross-engine parity claim. See the decision log.

Use a new experiment name, for example `Saved/Robotics/env/Scripts/python.exe Labs/PhysicalRecoveryLab/train.py --worlds 1024 --iterations 100 --run my_fixed_trial --native-motors --relative-targets --standing-fraction 0.4 --live-replay --diagnose`. Existing runs require explicit `--resume`; old-controller runs cannot resume under new gains. A `stop.request` file in the run directory saves/stops at the next completed PPO update. Standing practice is excluded from floor-recovery metrics. Regenerate `rig.json` using the native `Prophecy.Robotics.ExportRig` fixture, then `convert_rig.py` and validation scripts whenever the original PHAT changes. Rig hashes prevent reusing a fallen bank from a different export. Unsupported shapes/limits fail instead of silently approximating them.

For current experimental settings add `--action-rate-sum --reward-dt --raw-action-cost --ccd-iterations 100 --no-gyroscopic-forces`. The requested-action cost fixes a clipping loophole and changes previous-action observation semantics, so start fresh when enabling it on an old policy. Source speed-cap exceedances stop diagnostics by default. `--allow-speed-cap-mismatch` explicitly permits exploratory learning with recorded exceedances and unchanged motion; it does not certify transfer. Changes to physics/reward settings require a new run name. Reward-unit changes alone convert the loaded critic while preserving the actor.

`generate_fallen_bank.py` creates a separately named bank from physically settled random falls, requiring a full second of low speeds. Use `--initial bank --pose-bank <filename>.npz` for training; bank hashes are recorded. `evaluate.py --all-bank-poses --initial bank --pose-bank <filename>.npz --worlds <bank-size>` tests every admitted pose rather than a random subset. Old banks remain intact.

`--posture-profile joint_scaled` selects the separately tested posture experiment: upstream-style angle tolerances applied to reference-relative PHAT rotation vectors. It preserves the existing term weight/upright gate and all physics. Run `test_posture_reward.py` first and use a new experiment name. The default `legacy` profile reproduces historical uniform-quaternion shaping. Both profiles are stored in checkpoints; neither is evidence of a working get-up.

`build_rig_fixture.ps1` generates/builds a separate CPU Jolt fixture from the source export. `test_native_rig.py` verifies reconstructed geometry, inertia, policy-coordinate mapping and solved ground impulses. `evaluate_native.py --checkpoint <path>` tests a current relative-action/no-gyro actor against the exact project DLL without opening Unreal. Success additionally requires measured foot support and low root speed for a full second; standing-start retention is distinguished from recovery. Native motor calibration and unresolved saturation/cap differences are recorded separately.

`export_policy.py --checkpoint <path>` writes a dynamic-batch float32 ONNX actor and checks CPU Runtime against PyTorch. New requested-action checkpoints export raw commands: retain them for the next observation and clamp to the controller's bound only before physical actuation. Historical checkpoints retain bounded outputs. This certifies inference conversion only, not recovery or physical transfer.
