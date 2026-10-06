# First punch in TestNN — hookL / Parry, October 5

This package contains the **recorded authored attack**, fixed target, and **exact Parry initialization** from the current open TestNN setup. Replay the attacker from the recording; no Unreal or attack NN is required. `load_case.py` runs the original `FrozenUpperParry` trainer with the included installed checkpoint **1037725**.

The first punch is **hookL**, starting at game tick31. The player attacks `BP_ProphecyManualPoseAgent4`; the defender is using Parry and has a sword (`defender_drawn=1`). This captures the current in-memory setup, including the user's unsaved Blueprint/map edits, without saving or changing those assets. The capture used an owned PIE session, which was stopped afterwards.

## Timing

| Event | Attack policy frame | Game tick |
|---|---:|---:|
| Initial attacker pose | 0 | 30 |
| First attack prediction | 1 | 31 |
| Parry primer poses | 5,6 | 38,40 |
| Armed / first Parry prediction | 7 | 42 |
| Learned attacker Hit | 11 | 50 |
| Last active Parry prediction | 13 | 54 |
| Hit+3 Parry deadline | 14 | 56 |
| Last authored attack prediction | 15 | 58 |
| Attack inactive | — | 60 |

Policy rate is **30Hz**. Game ticks are the Blueprint debug counter, not policy frames. The attacker recording has all16 poses, frames0–15, from the completed authored targets; it excludes post-attack FK return and render interpolation. Frame0 is the previous endpoint accompanying the first attack prediction.

**Initialize Parry at Armed, not at attack frame0.** Its two exact recurrent primers correspond to frames5/6; the first prediction consumes attacker frames6/7. The separate attack-start pose is included for inspection.

## Files

- `attack_recording.npz`: full authored hookL, target, pelvis/collider conditioning, Armed and Hit latches, training and original UE coordinates. Load with `allow_pickle=False`.
- `parrier_initial_state.json`: exact two lower41 / upper90 / root12 history frames, baseline upper state, initial root command, attack controls and defender sword bit.
- `parrier_at_attack_start.json`: earlier defender pose/history at tick30, for display/analysis rather than the Armed-time NN seed.
- `lower_motion.npz`: the independent lower locomotion Parry received, covering attack frames5–13. Contains pelvis/legs, roots, lower states and lower-derived baseline upper states. **It does not contain predicted defensive arm/core motion.** The full25-joint arrays are lower-FK baselines required by the stock decoder.
- `load_case.py`: importable `load_case(training_dir, device='cpu')`, returning `agent, episode, metadata, initialization_errors`, plus a command-line vanilla replay.
- `assets/`: exact Parry checkpoint, geometry, colliders, provenance and skeleton bootstrap. No training pack needs to be fetched. The bootstrap prototype only constructs the skeleton; its episode/motion is not replayed.
- `vanilla_parry_smoke.npz`: stock trainer result, nine poses (two primers plus seven predictions); reference output only.
- `input_validation.json`, `loader_validation.json`, `native_boundary_validation.json`: numerical checks.
- `reference_unreal/`: diagnostic native inputs/outputs and actual subsequent UE defender poses. **The vanilla loader never reads this directory.**
- `manifest.json`: timing, target, coordinate contract and source/checkpoint hashes. `SHA256SUMS.json` covers transfer integrity.

## Run in the trainer repository

```powershell
python load_case.py --training-dir "C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/ParryAndDodge" --run
```

Change `--training-dir` after moving to another machine; use the trainer's normal Python dependencies. Only the upper Parry network runs. Parry is an upper-only architecture, so its recorded lower locomotion is a required external input. The replay covers the seven actual Parry predictions; the attacker file includes its remaining frames14/15 too. To run defense farther, supply additional lower locomotion to the stock trainer.

The stock replay retains the initial root command computed from the two primers. It does **not** inject UE's later planned-root command overrides, balancing feedback, upper inertia, or later defended upper poses. It uses the checkpoint's own exact-forearm projection. The recorded lower input can embody UE locomotion choices; replace it with independently generated vanilla locomotion if you want a different lower-body experiment.

## Coordinates and arrays

Training coordinates are metres, Y-up, with row-vector rotation bases. UE `[x,y,z]`cm becomes `[x,z,y]/100`. **Parry uses no episode-origin subtraction here** (`world_origin=[0,0,0]`). Rotation rows are UE bone +X,-Y,+Z directions expressed with world Y/Z swapped. UE quaternion arrays remain XYZW.

The fixed requested target is UE **(16.7699283,-244.4925881,147.7794830)cm**, stored explicitly in both conventions. Keep it fixed; do not retarget to the predicted defender head. The punch collider is attached to **lowerarm_l** using the raw attacker-catalog attachment and already-scaled half extents. Do not apply another1.5 scale or reconstruct the attacker's collider from the defender.

`attack_recording.npz`: `positions[F,25,3]`, `rotations[F,25,3,3]`, `pelvis[F,9]`, `collider[F,9]`, `collider_axes[F,3,3]`, `attack_half[3]`, `target_world[3]`, `hit[F,1]`, `armed[F]`, `source_frames[F]`, `times_seconds[F]`, `game_ticks[F]`, `joint_names[25]`, `world_origin[3]`, `ue_positions_cm[F,25,3]`, `ue_quaternions_xyzw[F,25,4]`. A9-vector is position plus the first two rotation rows.

`lower_motion.npz`: `source_frames[T]`, `lower[T,41]`, `roots[T,12]`, `baseline_upper[T,90]`, `positions[T,25,3]`, `rotations[T,25,3,3]`. Its Episode starts at source frame5 and uses frame units0–8. Parry's Episode event is **activation**: zero for both primers, then one. It is not the attacker Hit latch. The six attack-type values are the five native attack controls plus regular-defense type0; defender sword status is a separate policy tail bit1.

## Validation and limits

- Initialization recreates all captured recurrent histories, roots and initial root command with **zero error**.
- All seven recorded attacker pelvis/collider input pairs match UE within **2.38418579e-7** maximum absolute component error.
- Independent one-step native-boundary checks reproduce all258 policy input channels within **2.38418579e-7**, and the90 NN outputs within **9.83476639e-7**.
- The unmodified vanilla replay produces nine finite poses.

The one-step comparison uses each native recurrent state and command for verification only; those future states are never replay inputs. UE replaces the root command each step, while the stock trainer keeps its initial command. This yields a first-input difference of0.000172689 and a maximum full-run input difference of0.00649146 in mixed policy channels. These are documented runtime differences, not missing initialization or a claim of identical future motion. The package verifies faithful capture and vanilla replay; it does not claim the punch will be successfully parried.
