# Lower-body feedback tolerance investigation — 2026-09-16

Investigation only. No production source, Blueprint, map, live editor state or settings changed. No build, restart, Live Coding or remote editor execution. Experiments used a separate CPU Python process, one Torch thread, below-normal process priority.

## Finding

There is a reference-frame and presentation-time mismatch at the feedback boundary. A physical body can perfectly follow its presented target and still be treated as having a large error relative to the NN recurrent state. At low tolerances, feeding that mismatched sample back repeatedly is sufficient to collapse stepping.

The existing tolerance arithmetic itself is consistent: inside the tolerance retain the NN state; outside it inject only the excess error; zero selects the physical sample. It does not change magnetization strength.

## Source trace

Paths are relative to the project:

- `Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp:517,553`: reads the NN published pose and uses **Interpolated** world transforms as physical targets.
- `Source/GameAnimationSample3/Private/ProphecyNNPresentation.h:9`: explicitly retains one NN interval of presentation delay.
- `Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp:3365,3413,3473`: publishes the transition in the old root, rebases recurrence into the next root and advances/swaps the NN state.
- `Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp:4224`: the visible actor root interpolates between published roots.
- `Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp:1323`: completed physical world transforms are converted relative to the current inherited AgentMesh transform (the displayed root).
- `Source/GameAnimationSample3/Private/ProphecyNNPhysicalFeedbackBatch.inl:14`: the resulting sample is compared directly to `CurStateBuffer`, without converting from that displayed reference to the NN reference or accounting for sample/presentation time. Both serial and prepared paths do this.
- Same file around line 195: a differing lower sample replaces current recurrent state and feeds the sampled history as previous state. Manager input construction around line 3102 uses these states to compute NN motion features.

Even with interpolation disabled and perfect tracking of the latest published target, published foot coordinates and recurrent coordinates differ by one root advance. In the forward clips tested that is 6.67 cm at walk speed and 16.67 cm at run speed. Repeated feedback can effectively undo the root rebase for the feet. Interpolation adds a phase difference affecting rotations too.

## Isolated experiment

`experiment.py` loads the checkpoints named in the installed walk/run runtime JSON contracts. Walk is the accepted July-5 **latest**, never the best checkpoint. Checkpoint hashes are retained in the JSON results.

For each checkpoint: 11 cases batched together; 240 steps at the policy's 30 Hz; statistics over the final 180 steps. Uses the original training input builder, network, residual output, cleanup, foot pin/roll projection and root rebase; foot-roll integration set to the installed 4. Root windows come from the forward seed animation. Root rotation is constant (verified), so interpolating the published positions locally gives the same relative positions as world interpolation followed by removal of the interpolated root.

The synthetic physical follower has **zero error against its own displayed target**, no inertia, no contacts and no servo lag. The displayed-pose surrogate is the midpoint of successive published poses, representing the 60 Hz midpoint between 30 Hz policy updates. Pelvis feedback is excluded; foot positions, thigh/foot rotations and toe angles get the selected tolerances. This is an isolated reproduction of the feedback mechanism, **not a replay or measurement of the user's current Jolt scene**. Physical constraints, optional clamps, rigid-calf presentation and engine scheduling variation are omitted. Therefore the numbers below demonstrate sufficiency of the mismatch, not exact live-scene values.

| Case | Walk left/right foot vertical excursion | Run left/right foot vertical excursion |
|---|---:|---:|
| No effective feedback | 17.45 / 17.76 cm | 46.87 / 45.60 cm |
| Zero linear and angular tolerance, displayed sample | 0.036 / 0.044 cm | 0.101 / 0.517 cm |
| Zero linear tolerance only; angular feedback ignored | 0.003 / 0.012 cm | 0.273 / 1.025 cm |
| Zero angular tolerance only; linear feedback ignored | 18.14 / 16.43 cm | 37.91 / 40.27 cm |
| Displayed sample rebased to NN root; delay retained | 14.20 / 14.33 cm | 25.76 / 30.66 cm |
| Exactly matching recurrent reference/time, zero tolerance | Identical to no-feedback baseline | Identical to no-feedback baseline |

In the no-feedback baseline, comparing the perfect displayed follower to recurrence nevertheless reports:

| Apparent error | Walk | Run |
|---|---:|---:|
| Mean foot position error | 6.82 cm | 16.98 cm |
| 95th percentile foot position error | 9.99 cm | 24.75 cm |
| Mean thigh/foot rotation error | 3.36 degrees | 5.97 degrees |

Other useful controls:

- Latest published pose without interpolation, but still unrebased: also collapses stepping. So interpolation lag alone is not the main explanation; the root reference mismatch is independently sufficient.
- Correcting only the displayed sample's root reference restores substantial motion but not baseline. Presentation time still matters.
- 10 cm / 30 degrees completely masks the mismatch in this walk clip; it does not in the faster run clip.
- Angular-only feedback changes gait timing/motion but does not collapse foot lift in these tests.
- Walk collapse occurred without both feet being hard-pinned simultaneously (both-pinned fraction zero). It is not dependent on a two-foot pin lock.
- A latest-pose/rebased control has zero ongoing feedback error; walk retains a small initialization difference (0.24 cm mean foot difference), so it is not claimed to be bit-identical. The explicit aligned-state control is identical.

“Thigh and below” does not supply an independent linear state for every leg segment. The lower NN receives foot position, thigh and foot rotation, and toe angle. Calves are derived. Foot linear feedback by itself was enough to reproduce the reported symptom.

## Recommended correction, not implemented

Establish an explicit feedback sample reference and timestamp. Compare actual physical motion to its corresponding authored target in the same world frame and at the same time, then transport only the resulting physical deviation into the recurrent NN state. Maintain a consistent previous/current history. Do not substitute an older, displayed-root-relative absolute pose directly into newer recurrence.

The key regression criterion is: a perfect physical follower must leave the NN recurrence unchanged at tolerance zero, regardless of forward speed, turn rate or presentation alpha. Real contact errors must still be fed back. This also needs live-physics validation before considering a fix complete; it is not enough to increase tolerances or just subtract one frame of root translation.

## Artifacts

- `walk/results.json`, `run/results.json`: complete cases, metrics, contract/checkpoint identity.
- `walk/rollouts.npz`, `run/rollouts.npz`: recurrent states, apparent errors, rotations, pin probabilities and feedback activity.
- `experiment.py`: reproducible isolated harness. Run with the project's Python environment; add `--run` for the run checkpoint.
- Top-level `results.json` / `rollouts.npz` retain the initial 10-case walk experiment; the `walk/` and `run/` folders are the final 11-case results.
