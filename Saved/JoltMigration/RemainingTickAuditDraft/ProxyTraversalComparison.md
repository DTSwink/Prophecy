# Native proxy traversal: runtime audit

The duplicate native animation update is removed while the full pose/query pipeline remains intact. Both the historical control and current candidate pass **50 independent report checks** across all 720 measured rows. This comparison does **not** establish a whole-world speedup.

| Control | World mean ms | Reported median ms | p95 ms | RefreshBones ms | Actual NN inference ms/world frame |
|---|---:|---:|---:|---:|---:|
| Historical Original, 16:41 | 11.521021 | 11.542801 | 14.564000 | 2.823204 | 0.409541 |
| Native proxy traversal, 20:19 | 11.878346 | 11.552498 | 16.108699 | 2.629975 | 0.714839 |

The native proxy now executes **36,000 PreUpdates**, one for each completed pose publication, versus 72,000 in the historical control. Both runs retain exactly 36,000 PreEvaluate, Evaluate, PostEvaluate, query-publication and finalization scopes, plus 216,000 publication identity validations. Per-frame checks establish those counts on every frame rather than relying only on totals. The required explicit animation tick remains present.

Each run retains 100 agents, 60 warmup/360 measured frames, 60 Hz world/Jolt/presentation, 30 Hz actual lower/walk/upper ORTCpu inference at batch 100, four foot-roll iterations, 2,200 active Jolt bodies, 2,100 joints, all 88 bones per character and zero Chaos dynamic bodies. The full-row audit checks 36,000 agent records, 792,000 dynamic-body checks, 3,168,000 bone checks, 792,000 retained query-body pose checks and 36,000 ordinary unfiltered head rays per run. There are no own-capsule validation fallbacks. All 180 NN steps and 18,000 physical-feedback samples complete. Original feedback remains selected. Minimum managed-root travel is 1,200.010681 cm in both runs.

Removal during finalization, surviving 99 rigs, two extra unmeasured lifecycle steps, late admission/cancellation, stale handle rejection, disable and final floor-only teardown all retain their original gates. Camera subtrees remain detached with their components retained. The explicit P-class game-thread policy is applied and restored. Worker count seven, NoLock idle reads, DuringPhysics, 40 cm query-tree padding, no Chaos pause and 60 Hz endpoint expansion remain unchanged.

All **five current query tests** pass with no warnings/errors in `Foundation-20260909-201658-412/index.json`. The strengthened immediate query test logs five finalizations, including public animation reinitialization, reuse of source revision 1 and changed root/head transforms. It checks actual graph traversal progression, one update/evaluation cycle, all 88 current bones and immediate query/socket agreement. This is the current five-test result; the audit does not relabel older full-foundation runs as fresh tests of this binary.

RefreshBones decreases **0.193228 ms**, while its disjoint world remainder increases **0.550553 ms**; total mean increases 0.357325 ms. Measured NN inference increases 0.305298 ms. Original interpolation-only frames average 9.759633 ms versus 9.708209 ms now; inference frames average 13.282408 versus 14.048483 ms. These are historical/current associations; clock changes, contention or other causes are not established. Detailed phase timers overlap their parents and must not be added twice.

Seven before/after binary hashes match within each run group. Across builds, the six external binaries are identical and the game module changes, as expected. Known source changes include the native proxy traversal fix, the strengthened query regression and the two runtime Blueprint-class-flag compile fixes. The runs occur hours apart and are neither a same-binary nor time-matched A/B. Boundary hashes do not prove continuous loaded-memory identity.

The goal remains unmet. These are separated-grid/static-floor NullRHI controls, excluding rendering, active blood GPU work and dense crowd contacts. They are not packaged Shipping results.

Evidence: [standalone auditor](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/RemainingTickAuditDraft/AuditProxyTraversal.py>), [machine audit](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/RemainingTickAuditDraft/ProxyTraversalComparison.json>), [historical report](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_feedback_original_100_20260909_1641.json>), [current report](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_proxy_traversal_100_20260909_2019.json>).
