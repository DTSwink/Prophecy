# Independent audit of the 5/20/40 cm actual-NN runs

All three retained reports pass the bounded independent audit. `AuditPaddingReports.py` checks the complete report rows and writes the compact evidence/provenance file `PaddingRunsAudit.json`; it does not start Unreal or modify source/assets. The report SHA256 hashes are included below and in that JSON.

| Padding cm | World mean ms | World median ms | World p95 ms | Query scene update ms | Full query publication ms |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 12.826705 | 12.960501 | 15.697703 | 0.747637 | 1.737261 |
| 20 | 12.373281 | 12.623299 | 15.009899 | 0.671457 | 1.678266 |
| 40 | 12.230813 | 12.288999 | 15.060000 | 0.606553 | 1.602792 |

World summary mean/median/p95 and all reported character-phase means were recomputed from their complete source rows. Query scene update is a child of full query publication, and publication/NN/Jolt timers are nested in world/coordinator/manager scopes; do not add them all as separate costs. These are uncapped NullRHI world actor/physics timings, not rendered FPS. Head-query validation itself occurs outside the timed world interval.

The 40 cm run's world mean is approximately 0.596 ms below the 5 cm run; its measured scene-update phase is approximately 0.141 ms lower. Do not attribute the entire world difference to that subphase or claim a measured reinsertion count. There is one sequential run per treatment, so repeat-run significance, thermal/frequency effects and order effects remain unestablished. These reports do not satisfy the requested sub-10 ms total target.

## Settings and execution checked

All three are NNJoltCrowd, 100 characters, floor/gravity, 60 warmup frames, 360 measured frames and fixed 1/60 s. Substepping and async physics are off. Movement-only is on; full skeleton/query/body cadence remains present. Before, after and finish independently report the requested and effective padding value, unchanged at those boundaries. Every before/after native skeletal actor histogram contains exactly **2200 actors in bucket 0 / inner 1 (Dynamic)**. Other captured CVar settings agree across boundaries: Tree broadphase, dynamic tree and static/dynamic split enabled, query-only isolation disabled, dynamic leaf capacity8 and percentage enlargement approximately0.1.

All runs request/apply the explicit diagnostic GT affinity mask `0xff` (logical processors0–7, highest reported EfficiencyClass1), and restore the original GT mask `0xfff`. Process affinity remains `0xfff`; initial/final process priority is32 (Normal). Each report records360 BeginFrame samples,360 EndFrame samples and36,000 Refresh entry samples, all in the selected class, with no sample overflow. These sampled endpoints are not continuous residency or clock measurements. Process/thread power-throttling queries report unavailable/error87, so no successful power/QoS-state observation is claimed.

## Complete functional row checks

For **each** report:

- All360 frames and all36,000 character rows succeed, with unique agent indices0–99 each frame.
- Every frame contains2200 validated dynamic Jolt rig bodies and8800 validated skeletal bones; every character has22 bodies and88 bones. This totals792,000 native query-body checks and3,168,000 bone checks per report.
- Native simulation has2201 bodies including the floor and2100 joints, exactly one collision step per fixed Update, no fault/update-error bits, and no live Chaos dynamic bodies during measured frames.
- All actual automatic group fields are DuringPhysics (2); step/validation engine-frame identities agree and automatic step counts advance once per frame.
- Actual NN counters are monotonic with zero failed physical samples. Each report's measured deltas are180 NN steps and18,000 physical samples, with minimum managed-root travel at least1200 cm.
- Run, walk and upper runtimes remain `NNERuntimeORTCpu`; all three batches are100 and foot-roll integration remains4 steps.
- All36,000 head-query rows use the **normal unfiltered** path and hit the original `.PhysicalMesh` and `head`. **Capsule-filter fallback count is0 in all three reports.** The actual root is a capsule with one blocking native shape, and native/component capsule transforms agree within the declared tolerance.

## Callback/lifetime coverage and deliberate limits

Removal during bone finalization is exercised in every report. Removing one character rejects its22 handles and preserves2178 survivor handles; the remaining99 characters all validate after an explicit step. The two extra unmeasured lifecycle steps leave2179 bodies/2079 joints during survivor checks. Final disable leaves only the static floor, zero joints/active bodies/registered characters/Chaos dynamic bodies, rejects all2200 stale handles and reports a return to kinematic mode.

Immediate post-actor pending admission/cancellation succeeds: pending native world counts remain stable, cancellation returns Chaos dynamic count from22 to0 without completion callbacks,2178 survivor body states remain unchanged, repeated enable is idempotent, and pending token/delegate cleanup succeeds. The reports explicitly **do not** exercise next-frame admission/drain or deferred failure callbacks.

The same-frame authored-pose callback invalidation test is deliberately **not exercised** here because these are actual-NN cases; synthetic pose-store mutation is prohibited after manager adoption. Removal during finalization is covered, but must not be represented as that different authored-input regression.

Natural motion supplies **zero disjoint-previous-AABB edge rays** in all three reports. The reports explicitly require separate matching-source evidence for `Prophecy.Jolt.QueryPose.PostEndPhysicsPreservesNewerExternalPose`; these three JSON files do not execute or certify that external foundation test. No blood pixels/stains are validated in these NullRHI cases. Contacts remain the fixture's captured static-only policy; self/inter-character contacts are outside this benchmark.

## Immutable input identities

| Report under Saved/Benchmarks | SHA256 |
| --- | --- |
| `nn_jolt_padding5_A_100_20260909_1415.json` | `cdb4f2cda5dc89a33e6f712cc09f7186a759359cee766c4d3adb24e46526382f` |
| `nn_jolt_padding20_A_100_20260909_1416.json` | `3df5badc89b3c3d1256a872bbf4f6287eab379d462753e3896c7f76db6580684` |
| `nn_jolt_padding40_A_100_20260909_1417.json` | `5e08e847497f1cbd20cde396b600166998f94e00ddd867a3989cb574d6a6041a` |

The later padding40 CSV run is not among these three audited inputs. A pre-existing PowerShell report parse may have overlapped that later run's startup; its measured-window overlap is unconfirmed. It should remain an instrumented diagnostic rather than being relabelled a quiet baseline.
