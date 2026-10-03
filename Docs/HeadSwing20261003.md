# Head swing investigation — October 3, 2026

The upper NN generates the observed head correction for the current TestNN turn and incoming pose. The correction survives removal of FK return, lower recovery effects, physical feedback, and physics. It also reproduces through free recurrence in the original PyTorch checkpoint outside Unreal. No new root-feature frame/scaling error or core publication overwrite was found in the symptom window.

This is more specific than “the NN is bad.” The runtime transition differs from the Stepper Run Reface180 examples, and the comparison does not prove that the checkpoint alone is defective or that all Reface180 examples should exhibit the same swing. No gameplay fix or tuning change was made during this investigation.

## Current replay and measured motion

Current first Pike starts157, changes to half180, and ends198. The root finishes its large turn around224–228 (next-root prediction, current root and velocity feature refer to different samples). The presented head peaks at231–232, **3.7613 degrees/game tick relative to neck_02**. Head displacement relative to pelvis peaks235, **2.6597cm/game tick**. From224 to240 the head changes40.34 degrees relative to neck_02, neck_02 changes21.21 degrees relative to neck_01, and the head's net orientation changes57.25 degrees relative to pelvis. These rotations compose; they should not be added as scalar angles.

The original245 diagnosis used an older replay whose first Pike ended212. Its frame numbers should not be substituted into this capture. All rates here use the project's60 game ticks/second; policy inference occurs every2 ticks.

## Controlled Unreal experiments

Eight owned310-tick captures were made. Seven are valid comparison conditions; the initial `kinematic` attempt is explicitly discarded below. Every late intervention listed below has an exactly identical recorded bone-position prefix through its switch. Gaze0 was tested from the start and is not a matched-prefix experiment.

| Condition | Head peak218–250, degrees/game tick | Peak tick | Result |
| --- | ---: | ---: | --- |
| Normal replay | 3.7613 | 232 | Baseline |
| FK return disabled at195, before attack ends | 3.6603 | 231 | Swing remains |
| Lower tempering/reconstruction recovery disabled from180 | 3.6843 | 229 | Swing remains |
| Gaze held0 from start, verified in actual tensors | 3.0233 | 231 | Reduces local rotation, does not remove swing; position peak2.7873cm/tick |
| Kinematic from210, verified through entire later window | 3.8886 | 230 | Swing remains |
| Physical feedback disabled from210, physics still running | 3.8886 | 230 | Same head response as verified kinematic |
| Facing target extended45 degrees at210 | 2.5901 | 246 | Response moves later with turn end |

At the original peak232, extending the turn changes head speed **3.7613 → 1.1335 degrees/tick**. A later response follows at246. This establishes sensitivity to the turn-to-straight transition; it does not isolate the last yaw clamp as the sole cause, because the intervention also changes subsequent pelvis/feet/history.

The first diagnostic named `kinematic` switched at tick2, but Blueprint logic restored Physical before the relevant window. Its “physics off” interpretation is invalid. This was caught by checking recorded modes and replaced by `kinematic_late` plus the independent `no_feedback` experiment. Do not reuse the initial file as kinematic evidence.

Physical head tracking error in224–240 stays below0.713cm and1.190 degrees relative to the presented pose. There is no separate physical head snap. The immediate head parent has no physical body, so the angular tracking error is world-space head-body versus presented-head orientation, not a physical neck-local comparison.

![Controlled replay curves](../Saved/Diagnostics/HeadSwingAudit20261003/causal-comparison.png)

## Original model, feature and recurrence checks

- The installed upper is step82500, SHA256 `02e73800b8e63dc1b79e3e9c67c0a5f269eb830d3a330fe81c2d11480ac6f5b4`. Evaluating captured tensors using the original PyTorch weights matches Unreal's NN deltas within5.2e-7 across all captures; baseline error3.95e-7.
- Decoding those deltas independently as ten normalized parent-local rotations verifies the eight spine/neck/head bones. Their future-pose error during218–250 stays below0.000047 degrees across captures. Thus neither an active return/Armed layer nor the publication conversion creates the observed core turn after inference.
- Reconstructed current root features match within4.2e-7. Across216–240, the eight predicted future headings match subsequently realized headings within3.5e-7 in sine/cosine components; future-position features differ by at most5.90e-5 normalized units. The earlier world-direction forecast defect is not still present here. This hindsight comparison excludes the later258 facing-command change, which the earlier forecast could not know.
- Pelvis and foot features were reconstructed independently from lower states, the seed-to-heading bridge, and the actual next-root transform. Pelvis/current-foot discrepancies are below6e-7. Next-foot discrepancies stay below0.000386 across compared cases (small post-publication/float differences), not a large axis, sign, or one-root-frame mismatch. The upper's35 root channels equal the lower's copied channels exactly.
- Normal Physical recurrence can replace wrist positions; raw NN output is therefore not the entire next90-value input. No core-rotation overwrite occurs in the checked window. Removing feedback at210 eliminates that confound.
- Starting at216 or224 in the feedback-off capture, a Python implementation then freely recurs **all90 upper-state values**, using the captured external lower/root conditions and Stepper's base/cleaning functions. Every predicted90-value output through252 matches Unreal within6e-7 (measured maxima3.65e-7 and5.36e-7 respectively). This is a multi-step reproduction of the swing, not just a one-step ONNX/PyTorch parity check.
- On that validated free recurrence, replacing only the root-input channels with the extended-turn run lowers the peak3.8881→2.9395 degrees/tick (start216). Replacing root+pelvis+feet gives2.5811. These are diagnostic mixed-condition rollouts, not proposed gameplay settings.
- Stepper clamps forearm length before recurrence; Unreal ordinarily clamps the displayed geometry. This known separate discrepancy was tested using Stepper's exact clamp in the feedback-off recurrent replay: head peak3.8881→3.8871. It does not explain this head correction.

The original free-recurrence trial against the normal Physical run does **not** match all90 channels, because it deliberately lacks the physical wrist feedback. Use `recurrence-audit-no_feedback.json` for validated complete-state parity; do not quote `recurrence-audit-baseline.json` as such.

## Stepper Run Reface180 comparison

Ran the actual `rollout_upper_cached_lower_checkpoint` function used by the viewer with the same original82500 upper weights: F_R, F_L, B_R, B_L × sword/no sword × gaze0/-1 = **16 rollouts**. Each uses the matching source, verified immutable lower cache and normal authored three-frame initialization. Generated and authored poses were measured separately. The viewer's currently selected GUI checkpoint/gaze could not be read reliably, so these are explicitly controlled comparisons, not a claim about its live selection.

This viewer route uses cached lower checkpoint SHA `d01d632f…`, whereas Unreal uses Run SHA `0f2565ac…`. The viewer also has authored root trajectories, different gait/initial pose, no preceding Pike/FK-return history, and usually a different gaze. They are not the same input sequence.

For sword/gaze0, excluding the first three authored seed rows:

| Run Reface180 | Generated head peak, degrees per equivalent60Hz tick | Head's net local change in first8 policy steps after turn | Authored net change over same interval |
| --- | ---: | ---: | ---: |
| F_R | 3.700 | 21.70° | 11.81° |
| F_L | 3.742 | 28.45° | 8.34° |
| B_R | 1.951 | 17.15° | 16.10° |
| B_L | 1.859 | 10.27° | 21.70° |

The generated front variants do exhibit a delayed neck-local correction, but its timing and distribution differ from Unreal's concentrated40.34-degree head-local correction over16 ticks. The back variants are markedly quieter. Similar whole-clip maximum speeds alone do not establish identical visible motion: authored running itself contains sizeable periodic head rotations. This explains why the user need not see the same abrupt correction in the viewer, without dismissing that observation.

![Authored and generated curves](../Saved/Diagnostics/HeadSwingAudit20261003/head-curves.png)

## Conclusion and state left for the user

The immediate cause is the upper controller's recurrent response as this particular root/lower-body turn settles, with gaze and incoming pose affecting its shape. Output export, core decoding/publication, post-attack return and physics do not create the swing in this capture. The upstream trajectory is valid but differs from the authored viewer examples. This establishes the source of this observed motion; it is not a proof of universal model correctness or a claim that no other integration issue exists.

A correction should be evaluated against this exact transition, either by changing the learned response/coverage or deliberately shaping its input/output behavior. No cosmetic damping or checkpoint replacement was silently applied.

All owned Play sessions ended. Editor remains onTestNN. Diagnostic controls restored `SlashTraceAgent=-1`, `SlashTraceFrames=0`, `NNInputTraceFrames=0`. Every captured Blueprint graph is byte-identical. No gameplay source, Blueprint asset, model, viewer setting, or persistent tuning was edited or saved. Current editor/Live Coding state is preserved; normal DLL still needs the previously documented rebuild before any cold launch.

Reproducible scripts, JSON traces,16 NPZ rollouts, summaries and plots: `Saved/Diagnostics/HeadSwingAudit20261003/`. Primary indices: `summary.json`, `model-audit.json`, `feature-audit.json`, `recurrence-audit-no_feedback.json`, `restored.json`.
