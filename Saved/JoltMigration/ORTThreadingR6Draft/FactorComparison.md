# Packaged repeat-run timing comparison

Every timed row is retained. Failed gates remain failures; their timing is diagnostic only. Development and Shipping are separate controls. Median averages the two central samples; upper median and the exact p95 order index are also retained in JSON.

| Run | Configuration | Accepted gates | Frame class | N | Mean ms | Median ms | p95 ms | Max ms | >10 ms |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| Development-C100-20260909-194320-293 | Development | PASS | total | 360 | 9.276337 | 10.019699 | 12.119800 | 18.353902 | 180 |
| Development-C100-20260909-194320-293 | Development | PASS | nn_step | 180 | 11.293415 | 11.041600 | 12.568101 | 18.353902 | 180 |
| Development-C100-20260909-194320-293 | Development | PASS | interstitial | 180 | 7.259258 | 7.136250 | 8.332402 | 9.725701 | 0 |
| Development-C100-20260909-194334-480 | Development | PASS | total | 360 | 9.373505 | 10.055600 | 12.317501 | 18.408101 | 182 |
| Development-C100-20260909-194334-480 | Development | PASS | nn_step | 180 | 11.126740 | 10.916300 | 12.828499 | 18.408101 | 180 |
| Development-C100-20260909-194334-480 | Development | PASS | interstitial | 180 | 7.620270 | 7.475799 | 8.931998 | 10.182802 | 2 |
| Development-C100-20260909-194348-687 | Development | PASS | total | 360 | 9.338433 | 9.647850 | 12.150299 | 21.308802 | 179 |
| Development-C100-20260909-194348-687 | Development | PASS | nn_step | 180 | 11.097964 | 10.877049 | 12.596101 | 21.308802 | 179 |
| Development-C100-20260909-194348-687 | Development | PASS | interstitial | 180 | 7.578901 | 7.490452 | 8.602001 | 9.399600 | 0 |
| Development-C100-20260909-194402-714 | Development | PASS | total | 360 | 9.417955 | 9.763500 | 12.034602 | 18.103302 | 180 |
| Development-C100-20260909-194402-714 | Development | PASS | nn_step | 180 | 11.478534 | 11.393899 | 12.534998 | 18.103302 | 180 |
| Development-C100-20260909-194402-714 | Development | PASS | interstitial | 180 | 7.357376 | 7.289451 | 8.261200 | 9.019602 | 0 |

The JSON keeps disjoint manager/agent/coordinator/world-remainder partitions, a separate manager partition, all overlapping child phases, every counter delta/call, source hashes and repeat groups. Native wrapper, composition and RefreshBones are children of coordinator; query publication is inside RefreshBones. NN build includes physical resampling, and NN store includes pose publication.

Loaded Run/Walk/Upper batch-100 identities do not mean three inference calls: the walking fixture uses Walk plus Upper. Actual model work remains required.

Runner/package/report/validation hashes and current strict validation are checked. This tool does not independently rehash staged executables, DLLs, cooked packages or loaded memory; package provenance audits remain separate. No rendering, active blood-pixel or complete-migration claim follows from these NullRHI timings.
