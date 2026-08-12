# Chaos performance gains — 100 authored Physical agents

Reference: UE 5.7.4, 100 simultaneously simulated UEFN agents, pelvis + joint-torque drive, MACD on, foot roll 4, CPU NNE at 30 Hz, NullRHI. `+` means less Chaos CPU; `-` means slower. No setting below was saved.

## Repeatable results

| Change from reference | Chaos CPU gain | Decision |
|---|---:|---|
| `p.Chaos.SingleThreadPushData 1 -> 0` | **+3.4%** | Best low-risk candidate. Revalidate on target CPU. |
| Collision solver default -> Partial Jacobi (`SolverType 2`) | **+3.1%** | Real but changes contact solving; requires collision-behavior validation. |
| Both changes together | **+5.0%** | Best measured Chaos-knob result; not saved pending behavior validation. |
| Async physics off -> 30 Hz | **-0.9%** total solver CPU | Reject as a capacity optimization. End-physics waiting fell 70.4%, but work was rescheduled rather than removed. |
| `QueryAndPhysics -> PhysicsOnly` | **-3.7%** solver; **-45.8%** game-thread physics | Reject. It also removes limb raycast/overlap visibility. |

The first three rows used separate-process A-B-B-A replication, five-second warm-up, 160 captured frames per run, and high process priority. The reported number is the change in the average 10%-trimmed `PhysicsVerbose/AllWorkers/StepSolver` time. Runs completed without Chaos/Physics warnings, ensures, assertions, or fatal errors.

## Other plausible knobs screened on the same reference

| Change | Measured direction | Decision |
|---|---:|---|
| Enhanced determinism on -> off | **-2.6%** | Keep on; disabling it did not save CPU. |
| Joint ISPC off -> on | **-6.4%** | Keep current value. |
| Collision solver default -> SIMD (`SolverType 1`) | **-5.7%**, inconsistent | Reject. |
| Position iterations 8 -> 6 | **-1.6%**, inconsistent | Reject; no capacity gain. |
| Velocity iterations 2 -> 1 | **-6.0%** | Reject. |
| Projection iterations 1 -> 0 | Inconsistent | Do not trade stability for an unrepeatable result. |
| Iterations 8/2/1 -> 6/1/0 | **-5.7%** | Reject. |
| Inertia conditioning on -> off | **-5.9%** | Keep on. |
| Disable per-particle iteration calculation | Screened faster once, not repeatable | Unproven; do not adopt. |
| Collision cull distance -> 0 | **-17.7%** | Reject. |
| Position friction iterations -> 0 | **-6.4%** | Reject. |
| Manifold point cap -> 2 | **-26.4%** | Reject. |
| MACD on -> off | **-3.5%**, inconsistent | Keep MACD on. |
| Deferred narrow phase on | **-12.5%** | Reject. |
| Partial-island sleep on | **-1.8%** | Reject. |
| Island worker multiplier 1 -> 2 | Within noise | Keep current value. |
| Max island workers 0 -> 4 | Within noise | Keep current value. |
| Worker thresholds / batch sizes | Within noise | Keep current values. |

## Capacity conclusion

The Chaos settings offer about **5%** at best for this exact 100-agent workload. The large retained gain is structural: the selectable pelvis + joint-torque topology previously reduced non-NN residual cost by **58.4%** versus 22 independent world targets. For the next in-editor behavior test, try only the two-CVar combination above; keep it only if contacts, joint stability, and hit response remain correct.
