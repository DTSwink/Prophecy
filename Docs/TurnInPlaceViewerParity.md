# Turn-in-place: Unreal versus standalone viewer — 2026-09-15

The head overshoot is reproduced numerically. For the current setup, replaying the accepted lower and upper checkpoints through the Python training implementation reproduces Unreal's unwanted motion. No Unreal-only inference, history, gaze, or head/spine decoding fault was found. No gameplay correction or smoothing was installed for this investigation.

## Captured setup and measurement

- Unchanged live `testNN` / `BP_ProphecyManualPoseAgent` setup. The turning actor was `BP_ProphecyManualPoseAgent_C_1`; the two other agents were idle.
- Captured 40 simulation seconds: 2,401 samples per agent at 60 Hz, with separate future targets, interpolated targets and physical-mesh transforms. Also captured lower/upper inputs, upper deltas, published lower state and root frames at 30 Hz.
- After its initial startup frame, the turning actor was **kinematic**, and gaze remained **(0, 0)** throughout. The defect is already in its future NN target, independently of Jolt contact/drive behavior.
- Repeated turns occur every two seconds. The main comparison uses the settled repetition beginning near 8.0167 s, after three preceding turns.
- Head overshoot is measured as peak horizontal facing minus its settled facing after the same turn. It is approximately **42 degrees**. This is not the earlier exploratory yaw measurement relative to the first startup pose, whose tilted reference gives a different number.

## Matched-input checks

All comparisons below use the captured inputs, not visual estimates:

| Check | Maximum discrepancy |
| --- | ---: |
| Captured Unreal upper delta versus accepted PyTorch checkpoint | 8.35e-7 |
| Python upper autoregression using captured lower conditioning versus Unreal | 5.61e-6 state units |
| Python lower correction using the same four foot-roll steps versus Unreal published lower state | 3.58e-7 state units |
| Autonomous lower + upper Python replay, 360 steps / 12 seconds: lower state | 1.02e-5 state units |
| Same autonomous replay: upper state | 6.55e-6 state units |
| Python decoded pelvis, spine_05 and head versus captured Unreal world targets | < 0.0003 degrees |
| Encoded future yaw versus subsequently reached roots during unchanged turn intent | < 0.000025 degrees |

The autonomous replay starts from Unreal's captured initial pose pair, then builds its own lower history, lower correction, root rebasing, upper base/prior, pelvis/feet features and upper recurrence using the training code. It retains only the recorded root commands and mode/gaze. It reproduces the overshoot without Unreal running the simulation. The pose comparison converts the training world/bone bases to Unreal; it does not hide errors with per-frame alignment.

## Why the standalone example is different

The official viewer routine was replayed offline with the accepted upper checkpoint and `walk_transitions/M_Neutral_Stand_Turn_180_R.npz`, for both holding-sword and sheathed datasets. It reproduces the clean behavior described by the user.

1. **Different root trajectory.** The authored clip starts turning immediately, peaking at approximately **663 degrees/second**, then decelerates and finishes around 0.5 s. Unreal starts from idle, accelerates, sustains **320 degrees/second**, then stops over approximately 0.8 s. Its future window is consistent with that movement, but is a different conditioning sequence.
2. **Different initialization.** The cached-upper viewer defaults to `start_frame=2`: it displays authored upper states for frames 0, 1 and 2 and begins predicting frame 3. On this clip the head has already turned **44.26 degrees** at frame 2. The comparison therefore skips prediction of the initial idle-to-turn response. Unreal's later loops carry their actual recurrent idle history into each new turn.
3. **Different lower history.** The viewer consumes its immutable authored-trajectory lower cache. Unreal's lower checkpoint runs autoregressively against the live mover trajectory. Thus the upper policy receives different pelvis and feet conditioning too. The previously reported frame-0/frame-1 difference between the direct lower viewer and cached lower is an additional, separate initialization distinction.

The same network receiving different histories and trajectory features is not a matched parity test, even when both pictures are described as a “180-degree turn with gaze zero.”

## Isolated experiments

These were offline diagnostics only; no project settings were changed.

| Replay | Head overshoot beyond settled facing |
| --- | ---: |
| Unreal trajectory/history, four foot-roll steps | 42.08 degrees |
| Same trajectory/history, training's sixty foot-roll steps | 42.49 degrees |
| Authored root profile inserted into repeated turns from an idle recurrent state, four steps | 28.09 degrees |
| Same authored-profile experiment, sixty steps | 28.79 degrees |
| Original viewer rollout, drawn | 0.31 degrees |
| Original viewer rollout, sheathed | 0.18 degrees |

The authored-profile experiment retains the idle recurrent history; it deliberately does not copy the viewer's three authored upper initialization poses. Changing the profile alone reduces the problem but does not recreate the viewer's clean result. This rules out “just make the root turn faster” as a complete fix.

An additional oracle-future experiment replaced the live predicted root windows with the subsequently reached roots, including knowledge of future input changes. Overshoot remained (approximately 48 degrees); missing advance knowledge of the next input is not sufficient to explain or fix the defect.

**Foot-roll iteration difference:** Unreal intentionally uses four iterations; the frozen training configuration uses sixty. On identical inputs this accounts for at most 3.24 mm of single-step foot-position discrepancy in this capture. At four iterations, the Python correction matches Unreal to float precision. Sixty iterations change subsequent lower recurrence, but do not fix the head or eliminate the additional lower movement. Preserve the user's accepted four-iteration setting rather than silently increasing work.

For scale, the repeated Unreal turn has about 99 cm left / 69 cm right accumulated horizontal ankle travel during the comparison interval; the viewer clip has about 66 / 70 cm over its full 66 frames. These are different trajectories/durations, not an apples-to-apples footstep-count metric. The matched Python replay reproduces Unreal's actual extra movement.

## Recommended next work

Create a checkpoint evaluation/training case using the **live mover's root windows and continuous lower-policy rollout**, with a settled idle prefix and repeated turns. Do not initialize the upper history from already-turning authored poses when assessing idle-to-turn behavior. Keep the existing authored-clip test as a separate baseline.

If the requested behavior must be learned, fine-tune against these live conditions with coherent gaze/head targets and corresponding lower-body contact/motion targets. This investigation establishes the reproducible failure case; it does not claim that a particular loss or retraining recipe has already been validated. No head clamp, damping, output blend, pin override, checkpoint replacement or training job was applied.

## Sources and evidence

- Accepted upper: step 70750, `20260816_051748_ik_upper_cached_ae1ae4_bs64_allk32_blend_noise50_initgaze50each_latest.pt`; SHA256 `48F79FA29A869EB07FA5AAF42C34F05C02A30C893739C929F15F98E657D596D6`.
- UE export contract: `Content/locomotion/NN/prophecy_upper_body_runtime.json`. Accepted lower selection remains July 5 `_latest`, not `_best`.
- Training reference: `C:/Users/singerie/Documents/Cursor/stepper/training/ik/train_upper_pose_controller_pelvis.py`, `rollout_upper_cached_lower_checkpoint` and `decode_rows`; `train_upper_pose_controller.py` heading/base helpers; `train_simple_ae_controller.py` lower correction; `upper_cached_lower.py` immutable cache generation.
- UE reference: `Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp`, `BuildInputBatch`, `ApplyOutputBatch`, `BuildUpperInputBatch`, `ApplyUpperOutputBatch`, `DecodeLocomotionPose`.
- Local evidence: `Saved/Diagnostics/TurnParity/current.json`, `current_inputs.jsonl`, `viewer_*.npz`, `ue_upper_replay.npz`, `ue_training_decoded.npz`, `coupled_*.npz`, `experiment_summary.json`.
- Capture/replay scripts: `Saved/CaptureTurnParity.py`, `AnalyzeTurnParity.py`, `CompareTurnModels.py`, `CompareTurnLower.py`, `ReplayTurnPipeline.py`, `SummarizeTurnExperiments.py`. Diagnostic files are local; nothing was uploaded.

Unreal was left open with PIE stopped. Existing unsaved Blueprint/map edits were preserved. No saved gameplay assets or runtime code were changed for the turn investigation.
