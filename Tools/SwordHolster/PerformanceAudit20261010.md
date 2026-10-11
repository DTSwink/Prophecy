# D/S performance audit — October 10, 2026

The regular heavy reach tick is real. The spine/clavicle search consumed about80% of it: median3.68–4.02ms of4.60–5.01ms for100 synchronized agents. This search runs every fourth reach tick. Reach ticks without that search took0.74–0.80ms. These are measurements of the existing implementation, with no optimization applied.

## Average cost, descending

Final batch: idle/walk × draw/sheath,100 synchronized agents,7 measured repetitions per case after warmup,3,514 instrumented active ticks. Average over the entire action, including sliding and return; values are for all100 agents together. The percentages include one pose-cache publication and one full-pose read per agent per tick, measured separately from the original procedural-only timer.

| Work | ms/tick | Share |
| --- | ---: | ---: |
| Head/neck look update |0.253|22.4%|
| Spine/clavicle target search |0.237|21.0%|
| FK return update |0.236|20.9%|
| Applying body rotations through the skeleton |0.139|12.3%|
| Publishing and reading the pose cache |0.092|8.2%|
| Remaining arm interpolation, curves, copies and bookkeeping |0.083|7.4%|
| Generating arm destination/slide-guide poses |0.080|7.1%|
| Starting FK return, amortized over the action |0.007|0.7%|
| **Total with the specified cache transfer** |**1.128**|**100%**|

The second and third rows are effectively tied; their order changes between draw and sheath. The head does up to eight neck/head corrections per look-in tick. The search tests successive spine/clavicle angles, evaluating shoulder position repeatedly; its low update frequency conceals its much larger individual-tick cost in the action average. The body transform pass still runs during return, before the return pose replaces it; this is a source-inspection optimization candidate, not a measured saving. No proposed optimization has been applied or validated here.

## Setup and irregular peaks

- **Initial pose-planning math for100 simultaneous starts:** median11.07–12.30ms depending on case. Initial body search6.45–7.30ms, reach-duration calculation4.40–4.75ms, arm destination0.18–0.23ms. Initial search starts from zero correction. Skeleton discovery, live NN reads, runtime ownership and component setup are additional and excluded. These costs were excluded from the earlier per-tick benchmark and are not in the table above.
- **Normal FK-return entry for100 agents:** median0.86–0.92ms. Fine probes measured buffer allocation/initialization0.14–0.18ms, initial pose/velocity calculations0.60–0.63ms, and rate calculations0.10–0.11ms. Those component medians need not sum exactly to the median total.
- **Irregular return-entry stalls:** the first batch included5.5–11.4ms inside return setup. They did not recur in the second batch or under the finer probes; the fine-probe maximum was1.44ms. Their cause remains unproven. The data does not establish that allocation caused them; no OS scheduler/page-fault trace was collected. They must not be described as ordinary repeatable algorithm cost, or quietly omitted from the tail-latency record.

## Measurement limits and evidence

Same recorded-pose fixtures and saved profile as the earlier benchmark. The idle/walk names identify fixture poses; this does not replay live NN inference or a walking crowd. All agents start together and run serially. Three batches were run: coarse probes, a repeat, then finer return-entry probes and a fresh initial-search measurement. Final paired controls had probes disabled: mean1.018ms procedural-only versus1.042ms with probes, approximately2.3% overhead plus run-to-run timing variation. Small rankings are not significant at sub-percent precision. The active editor and machine load also differ from the earlier isolated headless benchmark; this audit is not evidence of a gameplay regression.

Excluded: NN pose reads/inference, physics, rendering, sword runtime/component operations, concurrent cache-reader contention, and full start-up admission. Pose transfer here is exactly one publication and one read, not a measurement of all actual scene consumers. This audit explains the earlier procedural benchmark; it does not measure full100-agent scene cost.

Full local evidence: `Saved/Diagnostics/SwordPerformanceAudit20261010/` contains all three frame CSVs, setup CSVs, native temporary probe source, instrumentation scripts and analysis. The compact tracked receipt is `PerformanceAudit20261010.json`. The finer-probe CSV's final six column labels were emitted as null because Live Coding retained the original diagnostic label array; analysis maps those six columns to their explicit enum order (return_buffers, return_poses, return_rates). Numeric timer values and call counts remain in the raw CSV. The retained gameplay controller layout was not changed.

Only the narrow implementation file was temporarily instrumented. No Blueprint, tuning, asset, PHAT, simulation setting or animation behavior was changed. The editor was kept open throughout.

Cleanup: source restored byte-for-byte to the pre-audit file; restoration Live Coding compile succeeded in77.36s and reload completed with no object changes. Editor remains on TestNN outside Play with no dirty packages. Normal gameplay DLLs remain the baseline implementation; no normal rebuild/restart was needed. No optimization or motion changes were made.
