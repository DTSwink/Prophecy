# Packaged R4: the 30 Hz NN frames explain the two timing groups

All 360 measured rows are retained and classified from successive `actual_nn.completed_nn_steps` counters, starting with `before.actual_nn_initial`. Each NN frame increments exactly one NN step and 100 physical samples; intermediate frames increment neither. Cumulative build/inference/output/store timers are differenced per row, rather than treating their running totals as frame costs. Sampling, raw-encoder and publication calls independently match that classification.

| R4 world time, ms | Intermediate frames | Actual NN frames |
|---|---:|---:|
| Count | 180 | 180 |
| Mean | 7.405145 | 11.537586 |
| Conventional median | 7.299099 | 11.343550 |
| p95, each group's sorted index 171 | 8.611400 | 13.015099 |
| Minimum | 6.541200 | 10.352697 |
| Maximum | 9.558000 | 18.379003 |
| Frames above 10 ms | 0 | 180 |

The overall 9.471366-ms mean lies between two disjoint groups. The report's upper-middle sample, sorted index 180, is therefore the **fastest NN frame**, 10.352697 ms. Its conventional median averages that sample and the slowest intermediate frame, yielding 9.955348 ms. Neither median definition means NN frames already meet 10 ms. NN-step presence versus world time has point-biserial/Pearson correlation 0.93777; this is an association within the recorded run.

## Where the 4.132441-ms gap occurs

These four top-level rows are disjoint. The last is an arithmetic remainder of the measured world interval, not a named Engine phase.

| World partition, mean ms | Intermediate | NN | NN minus intermediate |
|---|---:|---:|---:|
| NN manager tick | 0.470976 | 4.525213 | +4.054237 |
| All agent ticks | 0.981100 | 1.001532 | +0.020431 |
| Jolt coordinator | 4.896336 | 4.901752 | +0.005415 |
| Remaining world interval | 1.056732 | 1.109089 | +0.052357 |
| Total world | 7.405145 | 11.537586 | +4.132441 |

**98.1% of the group mean gap is inside the NN manager.** Its NN-frame work partitions as follows. Build excludes the nested resample scope; store includes pose expansion and pose-store writes. These rows sum to the manager's NN-frame mean within timer precision.

| Manager partition, ms per actual NN frame | R4 packaged | Earlier proxy Editor | Earlier Original-feedback Editor |
|---|---:|---:|---:|
| Actual model inference | 2.057982 | 1.429679 | 0.819083 |
| Physical resampling | 0.923903 | 1.154638 | 1.089819 |
| Other lower/upper input construction | 0.140474 | 0.199866 | 0.182413 |
| Output application and layers | 0.331190 | 0.464877 | 0.438711 |
| Pose expansion and store publication | 0.577435 | 0.758379 | 0.738545 |
| Visual-root movement | 0.479013 | 0.729856 | 0.733827 |
| Manager remainder | 0.015216 | 0.026863 | 0.026278 |
| Manager total | 4.525213 | 4.764158 | 4.028677 |

The three source timers have equivalent boundaries, but these are separate sessions and binaries. They are not a controlled performance comparison. The packaged inference interval is higher even while the other manager work is lower; this warrants checking the runtime execution policy before changing model work.

For comparison, the nested bridge phases show essentially no NN-frame penalty: native step wrapper 1.714523 → 1.724484 ms; batch composition 0.512433 → 0.523009; RefreshBones 1.862807 → 1.854635; query publication 1.075105 → 1.069639. They overlap coordinator/refresh parents and must not be added to the world partition.

## Next factor to measure

The highest-value supported experiment is **ORT intra-operator thread count in the same packaged executable**, retaining all models, input/output shapes, actual steps, update rates and gameplay work. Installed UE source has a concrete target difference: `NNERuntimeORTSettings.h:60` defaults Editor threading to a global pool with intra/inter counts 0/0, while line 64 defaults Game threading to separate sessions with counts 1/1. `NNERuntimeORTModule.cpp:48–52` selects these by `WITH_EDITOR`, and `NNERuntimeORTUtils.cpp:461–468` applies the selected pool/counts to ORT sessions. The setting's own documentation states that intra count 1 uses only the invoking thread. Project, snapshot and Engine Config searches found no override; **the R4 report does not capture the resolved ORT settings**, so those defaults remain a source-supported explanation to verify, not a proven runtime attribution.

Suggested first control: Game intra count **1 versus 2**, keeping global pool false, inter count 1 and sequential graph execution identical. Apply it before ORT environment/session creation, capture the effective setting and process invocation, and compare full-run world/group timings plus retained correctness gates. The ORT source-audit agent owns the exact supported override and output-equivalence controls. A faster inference micro-interval alone is insufficient if worker activity increases later world work. No gain is claimed before that experiment.

The next measured NN-specific costs are the 0.924-ms resample and 0.577-ms publication intervals. Prepared feedback already has a separate exact-math control and a measured local saving without an established total gain; this analysis does not reclassify it as an accepted optimization. Removing all remaining input-construction overhead would save only 0.140 ms per NN frame. The coordinator's 5-µs difference between NN/intermediate frames cannot explain the 1.538-ms NN-frame mean shortfall.

The longest sample is frame 0 at 18.379003 ms. Its manager is an ordinary 4.449598 ms and its unassigned world remainder is 7.777490 ms; that spike is not an inference spike. It remains in every statistic. Within NN frames, world time correlates with coordinator (0.7803), remainder (0.6839), manager (0.6105) and inference (0.5073), so the tail still needs full-world validation after any average NN improvement. The record does not isolate the cause of the first-frame remainder or establish clock/thermal/worker residency.

## Scope and reproducibility

`ProphecyNNLocomotionManager.cpp:2777–2801` places resampling inside BuildSeconds and sums lower and upper model calls in InferenceSeconds; `:1919–1930` measures all PublishAgentPose calls inside StoreSeconds, followed by UpdateVisualRoots. `ProphecyPhysicsBenchmark.cpp:521–524,558–563` starts the world timer before ordinary world work and stops it **before** per-row correctness validation. Those post-timer head rays/body/bone audits are preserved validation evidence, not extra costs to subtract from world time. Normal in-frame query-body publication remains measured.

The input is R4 `Runs/Development-C100-20260909-183617-557/benchmark.json`; its prior independent workload/provenance audit remains `PackagedR4AuditDraft/PackagedR4Comparison.md`. Its invalid 33rd diagnostic collision response and incomplete callback animation restoration remain historical defects. This document does not turn that report into a clean R5 result, omit any workload, or claim the overall goal complete.

`AnalyzeNNFrameGroups.py` writes source report hashes, all reconstructed per-frame timers, group statistics, conditional correlations and complete phase tables to `NNFrameGroups.json`. Only these draft artifacts were written; no source, Engine settings, build, UE session or benchmark process was changed.
