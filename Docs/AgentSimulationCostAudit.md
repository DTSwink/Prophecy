# Agent simulation cost audit

Current production configuration: 100 authored agents, 30 Hz batched CPU NNE, four-step foot roll, pelvis + joint-torque Physical drive, MACD on for Physical agents, and the production capsule/limb collision matrix. The audit used NullRHI so rendering cost is excluded.

`Physical` below means full Chaos limb simulation. Every condition still runs intent, the 100-agent NN batch, pose construction, and kinematic capsule collision for non-Physical agents.

| Physical agents | Total wall ms/frame, median (range) | Input + physical resample | Quiet NNE inference | Four-step output + IK | Pose publish | Chaos solver, median (range) | Collision detection | Constraint solve |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 (0%) | **5.021** (3.061–6.597) | 0.1166 | 0.3847 | 0.4680 | 0.1488 | **0.238** (0.233–0.299) | 0.011 | 0.000 |
| 50 (50%) | **14.552** (9.651–19.819) | 0.1812 | 0.4398 | 0.4432 | 0.1415 | **4.983** (4.003–6.279) | 0.904 | 2.675 |
| 100 (100%) | **29.894** (18.185–36.222) | 0.2608 | 0.4889 | 0.4666 | 0.1462 | **12.663** (9.610–15.836) | 2.224 | 6.779 |

Times are milliseconds per 30 Hz step/frame. Four interleaved runs were recorded per condition over 450 warmed frames each. Total wall and Chaos solver values are medians; ranges expose the concurrent CPU load present during the audit. NNE inference performs the identical `[100,152]` batch in every row, so its quiet sample is listed instead of the load-contaminated median; observed external-contention spikes reached 7.743 ms. Chaos collision and constraint scopes are nested/parallel diagnostic scopes and must not be added to the solver total.

## What costs scale

- Physical-state resampling is negligible: all 100 agents add about **0.144 ms** over the kinematic input build, roughly **0.00144 ms per Physical agent**.
- Four-step foot roll plus output cleanup and IK stays around **0.44–0.47 ms for all 100 agents**. It does not scale with Physical count.
- Pose publication stays around **0.14–0.15 ms for all 100 agents**.
- Chaos dominates the scalable cost: median solver time rises from **0.238 ms** at 0% to **4.983 ms** at 50% and **12.663 ms** at 100%.
- The 100%-Physical median is inside the 33.333 ms budget by about **3.44 ms**, but the slowest loaded run exceeded it. This is a CPU/headless capacity result, not rendered `mybasic` performance.

No Chaos optimization CVar from the earlier audit is enabled. The benchmark used the existing `/Game/locomotion` test map transiently; `mybasic` and the bridge were not modified.
