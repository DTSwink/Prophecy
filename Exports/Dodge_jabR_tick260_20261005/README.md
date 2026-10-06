# jabR into the dodger's face — Unreal capture, October 5

This package freezes the **recorded authored attacker** and provides the **exact two-frame initialization of the Dodge NN**. Replay the attacker from the recording; only the dodger needs inference. No Unreal installation or attack checkpoint is required for replay.

The source is the saved TestNN setup, player `BP_ProphecyManualPoseAgent`, defender `BP_ProphecyManualPoseAgent4`, Kinematic. The attack is jabR beginning at game tick241, with the face approach around256–260. This capture uses the accepted new defense rules: no collision stop,3 policy frames after Hit. It contains no collision-triggered Dodge reinitialization.

## Timing

| Event | Attack policy frame | Game tick |
|---|---:|---:|
| Initial attacker pose | 0 | 240 |
| First attack prediction | 1 | 241 |
| Dodge primer poses | 4,5 | before activation |
| Armed / first Dodge prediction | 6 | 250 |
| Face approach | 9 | 256 |
| Learned Hit latch | 10 | 258 |
| Continued Dodge | 11,12 | 260,262 |
| UE Hit+3 defense deadline / last attack pose | 13 | 264 |
| Attack no longer active | — | 265 |

Policy rate is **30Hz**. Game ticks are the Blueprint debug counter, not policy frames. Recorded poses are exact completed policy targets, not interpolated render samples. Frame0 is the previous authored endpoint accompanying attack frame1.

**Do not initialize Dodge at attack frame0.** Unreal waits for Armed. Its two exact primers correspond to attack frames4/5, and the first NN step consumes attacker frames5/6. The full attacker recording still starts at0 for display and analysis. `dodger_at_attack_start.json` separately supplies the dodger's earlier pose/history at tick240.

## Files

- `attack_recording.npz`: all14 attack poses (frames0–13), fixed target, pelvis/collider conditioning, Armed/Hit latches and original UE coordinates. Load with `allow_pickle=False`.
- `dodger_initial_state.json`: exact previous/current lower41, upper90 and root12 states, initial root command, all6 remaining movement banks, accumulated root shift/yaw and walk category. Captured immediately before the first Dodge prediction; completed steps=0.
- `load_case.py`: returns the original trainer's `agent, episode, metadata, validation_errors`. Uses only two defender primers and recorded attacker inputs. No future defender data, UE mover windows, balancing, inertia, clamps or physical feedback is injected. Checkpoint-native leg/forearm projection remains part of the unmodified network runtime.
- `assets/`: exact installed Dodge checkpoint322925 (including its embedded lower policies), skeleton geometry, bank/lower settings, collider catalogs and checkpoint provenance. `runtime_skeleton_seed.pt` plus `source_skeleton.npz` bootstrap the trainer skeleton; their template is not an episode or a future defender input. Captured UE geometry overwrites all runtime geometry tensors.
- `manifest.json`: timing, coordinate conventions, target, checkpoint and trainer-source hashes.
- `input_validation.json`, `loader_validation.json`: numerical validation receipts.
- `vanilla_dodge_smoke.npz`: a finite test rollout produced by the unmodified trainer. Reference output only, never an input.
- `reference_unreal/`: raw diagnostic capture, including subsequent UE defender poses and live NN inputs/outputs. These exist for comparison only. **Do not feed these future defender states or planned roots into vanilla inference.**

## Run in the Dodge trainer repository

```powershell
python load_case.py --training-dir "C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/ParryAndDodge" --run
```

After moving the package, change `--training-dir` to that repository's `ParryAndDodge` directory. Requires its normal Python dependencies. The checkpoint and skeleton bootstrap are included; no training pack needs to be fetched. `load_case()` is also importable for the trainer agent's analysis/replayer.

The vanilla runner continues through the recorded attack's last pose; it deliberately does not implement Unreal's contact/Hit/end lifecycle. Therefore its last prediction at attack frame13 extends one step beyond UE's final active Dodge prediction at12. It uses only the initial movement command for the dodger, as the vanilla trainer does. A later difference from UE can reflect UE's live movement/balancing inputs; it does not invalidate this seed.

## Array and coordinate contract

`attack_recording.npz` contains unbatched arrays: `positions[F,25,3]`, `rotations[F,25,3,3]`, `pelvis[F,9]`, `collider[F,9]`, `collider_axes[F,3,3]`, `attack_half[3]`, `target_world[3]`, `event[F,1]`, `armed[F]`, `source_frames[F]`, `times_seconds[F]`, `game_ticks[F]`, `joint_names[25]`, `world_origin[3]`, `ue_positions_cm[F,25,3]`, `ue_quaternions_xyzw[F,25,4]`. A9-vector is position plus the first two **rows** of the rotation basis.

Training coordinates are metres, Y-up, row-vector bases. UE world position `[x,y,z]` cm becomes `[x,z,y]/100 - world_origin`. Rotation rows are UE bone +X,-Y,+Z directions expressed with world Y/Z swapped. To display a training point back in UE: add `world_origin`, swap Y/Z, multiply by100. Quaternion arrays retain UE XYZW convention.

The fixed requested target is UE **(24.0488504,-224.2674235,147.2925369)cm**. Training-local target and origin are stored explicitly. Do not retarget to the newly predicted defender head.

The punch collider is attached to **lowerarm_r**, using the included attacker catalog's raw attachment and already-scaled half extents. Do not apply another1.5 multiplier or reconstruct its orientation from the defender's forearm. `attack_controls` contains the five captured attack flags; the loader appends regular-Dodge type0. This sixth value is not a held-sword flag.

The trainer `Episode` starts at attack frame4, with its first two entries reserved for primers. Its `times` use policy-frame units0…9, unlike the recording's `times_seconds`. Hit occurs at Episode index6. `authored_roots=None`: the defender's future root is never prescribed.

## Validation

All7 active UE Dodge input pairs match the exported attacker pelvis/collider vectors within **2.98023224e-7** maximum absolute component error. The target is constant. The stock trainer reconstructs the captured lower/upper histories, initial root command and bank state with **zero error**. The vanilla smoke rollout produces10 finite poses (two primers plus eight predictions).

`SHA256SUMS.json` covers the package files for transfer integrity. These checks verify recording and initialization fidelity; they do not claim vanilla Dodge will successfully avoid the punch.
