# Packaged repeat-run timing comparison

Every timed row is retained. Failed gates remain failures; their timing is diagnostic only. Development and Shipping are separate controls. Median averages the two central samples; upper median and the exact p95 order index are also retained in JSON.

| Run | Configuration | Accepted gates | Frame class | N | Mean ms | Median ms | p95 ms | Max ms | >10 ms |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| Development-C100-20260909-183617-557 | Development | FAIL | total | 360 | 9.471366 | 9.955348 | 12.583900 | 18.379003 | 180 |
| Development-C100-20260909-183617-557 | Development | FAIL | nn_step | 180 | 11.537586 | 11.343550 | 13.015099 | 18.379003 | 180 |
| Development-C100-20260909-183617-557 | Development | FAIL | interstitial | 180 | 7.405145 | 7.299099 | 8.611400 | 9.558000 | 0 |

The JSON keeps disjoint manager/agent/coordinator/world-remainder partitions, a separate manager partition, all overlapping child phases, every counter delta/call, source hashes and repeat groups. Native wrapper, composition and RefreshBones are children of coordinator; query publication is inside RefreshBones. NN build includes physical resampling, and NN store includes pose publication.

Loaded Run/Walk/Upper batch-100 identities do not mean three inference calls: the walking fixture uses Walk plus Upper. Actual model work remains required.

Runner/package/report/validation hashes and current strict validation are checked. This tool does not independently rehash staged executables, DLLs, cooked packages or loaded memory; package provenance audits remain separate. No rendering, active blood-pixel or complete-migration claim follows from these NullRHI timings.

Failed gates for `C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\JoltMigration\NNCrowd-20260909-144331-647\Runs\Development-C100-20260909-183617-557\runner.json`:
```json
{
  "fresh_current_validator_pass": {
    "success": false,
    "error": "ValueError: Root capsule must export exactly 32 stored channel responses (WorldStatic Block, others Ignore); no transient/sentinel extras."
  },
  "exact_32_valid_collision_responses": {
    "entry_count_histogram": {
      "33": 100
    }
  },
  "callback_restore_evidence_present": null
}
```
