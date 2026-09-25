# Recovery knee steering in the foot frame

Initial implementation and evidence, 2026-09-25. The geometric limiter below is retained; its former tempering-only lifetime and fixed speed are superseded by [independent recovery timing and the pelvis360 fix](LegRecoveryTimingAndPelvis360.md). The accepted September20 reconstruction and height-based guidance remain.

## Diagnosis

The current scene repeats `overR`. The authored targets already contain the exit snap, independent of physical simulation. At tick321 the right knee's bend direction changes25.51 degrees relative to its foot, followed by25.49 degrees at322. The left changes14.21/13.57 degrees. Measure the radial knee bend perpendicular to hip→ankle, rather than the heading of hip→knee (which becomes misleading when the knee is almost directly below the hip).

The existing geometric reconstruction applies its chosen pole immediately. Frozen policy inputs confirm a51.01996-degree right-knee steering request at the third exit, not just an artefact of the displayed interpolation or a changing rollout.

## Implementation

`SmoothTemperedKneePole` in `ProphecyLowerTempering.inl` runs after the unchanged `ResolveTemperedLeg` geometry at the existing manager call site.

1. Recover the previous published hip/ankle axis and knee bend. Near a straight leg, use the existing authored hinge-axis fallback.
2. Carry this complete frame through the change in foot rotation. This is equivalent to keeping the direction in the foot's local frame.
3. Minimally transport the carried frame to the newly accepted hip→ankle axis, so endpoint changes do not detach the chain or create a projection sign flip.
4. Measure the signed turn around that axis toward the existing reconstruction's final pole. Limit only this remaining steering to12 degrees per30Hz policy step. Smaller requests return the original result bit for bit; there is no permanent low-pass lag.
5. Rotate the already solved thigh around hip→ankle by the required correction. Pelvis, ankle position, foot rotation, toe and the other leg stay bitwise unchanged. Thigh/calf lengths stay unchanged.

The previous published state supplies history. There is no added timer, agent layout, inference, persistent map, Blueprint node or saved tuning change. This is a per-policy-step angular budget, not a wall-clock duration. The existing presentation interpolates policy poses at60Hz.

Only active tempered leg reconstruction with nonzero rotation follow calls it. Fully frozen rotation retains the prior path. Normal locomotion, disabled reconstruction, finished tempering and active attacks/parries/dodges bypass it. Recovery after any special uses the same rule; there is no attack-name gate. Existing pinning, height guidance,15cm inner exclusion, length recovery and calf twist handling are unchanged.

## Validation

Live Coding21.09s, loaded13:46:25UTC. Five focused tests passed13:47:04UTC:

- `Prophecy.NN.LowerTempering.FootFramePoleSmoothing`: angular budget in both directions, exact bypass, finite convergence, invariant endpoints/lengths and361 common foot-frame rotations spanning a full turn.
- `Prophecy.NN.LowerTempering.HeightDirection`.
- `Prophecy.NN.LowerTempering.SupportSourceContracts`.
- `Prophecy.NN.PelvisInertia.LegChain`.
- `Prophecy.NN.PhysicalTargets.RecoveryCalfLength`, including the previously updated frozen geometric oracle.

Six owned420-frame captures: original scene, instrumented baseline, enable only after320, enabled throughout, alternating kickL/kickR baseline, alternating kicks enabled. Captures ended their own Play sessions; no user Play session, graph or asset was modified/saved.

The switch comparison has exactly identical authored positions through320. At321–322 the right foot-relative pole turns25.51/25.49→6.00/6.02 degrees. The left turns14.21/13.57→6.16/5.89. Steering reaches the requested direction over the following samples instead of making the one-policy-step correction. Same-input frozen comparisons verify12-degree maximum steering and bitwise endpoint/rotation preservation, so changed recurrent motion cannot account for that improvement.

On52 frozen kick-recovery leg inputs,48 results remain exactly unchanged. Four excess turns are limited; largest requested steering19.42 degrees. Both alternating kick directions were captured (three complete18-frame exit windows plus the beginning of the fourth). First supporting-knee peak7.51→6.03 degrees; second support9.94→6.72; kicking-foot behavior remains close to baseline. These comparisons do not certify every possible subsequent NN rollout: the changed thigh is intentionally fed back, and later outputs can differ. Ordinary locomotion's separate near-extension transients are outside this correction.

Evidence under `Saved/Diagnostics`:

- `PunchKneeBaseline-live.json`.
- `PunchPole-{baseline,switch,enabled,kick-baseline,kick-enabled}-live.json`.
- Corresponding `-frozen.jsonl` and `-frozen-analysis.json` files.
- `PunchPole-live-summary.json`, `ComparePunchPole.py`, `AnalyzeFootFramePole.py`, `TestFootFramePole.py`.

Editor-only comparison `Prophecy.Tempering.PoleSmoothing`:1=current/default,0=unsmoothed. `Prophecy.Tempering.PoleTrace` is an opt-in bounded same-input capture, default0. Final values verified1/0, no diagnostic callback remaining and PIE stopped. No shipping trace/check overhead. Include the live patch in the next authorized normal build.
