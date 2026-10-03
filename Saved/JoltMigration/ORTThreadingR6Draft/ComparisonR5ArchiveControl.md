# Packaged repeat-run timing comparison

Every timed row is retained. Failed gates remain failures; their timing is diagnostic only. Development and Shipping are separate controls. Median averages the two central samples; upper median and the exact p95 order index are also retained in JSON.

| Run | Configuration | Accepted gates | Frame class | N | Mean ms | Median ms | p95 ms | Max ms | >10 ms |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| Development-C100-20260909-192656-176 | Development | PASS | total | 360 | 9.145706 | 9.918651 | 11.617500 | 17.998103 | 180 |
| Development-C100-20260909-192656-176 | Development | PASS | nn_step | 180 | 11.109899 | 11.030599 | 11.918399 | 17.998103 | 180 |
| Development-C100-20260909-192656-176 | Development | PASS | interstitial | 180 | 7.181512 | 7.128650 | 7.950302 | 9.629000 | 0 |

The JSON keeps disjoint manager/agent/coordinator/world-remainder partitions, a separate manager partition, all overlapping child phases, every counter delta/call, source hashes and repeat groups. Native wrapper, composition and RefreshBones are children of coordinator; query publication is inside RefreshBones. NN build includes physical resampling, and NN store includes pose publication.

Loaded Run/Walk/Upper batch-100 identities do not mean three inference calls: the walking fixture uses Walk plus Upper. Actual model work remains required.

Runner/package/report/validation hashes and current strict validation are checked. This tool does not independently rehash staged executables, DLLs, cooked packages or loaded memory; package provenance audits remain separate. No rendering, active blood-pixel or complete-migration claim follows from these NullRHI timings.
