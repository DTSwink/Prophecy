# Accepted performance checkpoint — 9 September 2026

The user accepts this setup as sufficient optimization for now and explicitly requests resuming gameplay integration. Performance no longer blocks the body/sword work. Revisit tuning after functionality is integrated, rather than continuing microbenchmarks.

Best verified baseline: corrected R5 Shipping, 100 moving agents, **7.976 / 8.006 ms mean**, 8.238 / 8.349 ms median, 10.918 / 10.694 ms p95. Evidence: `Saved/JoltMigration/PackagedR5ComparisonDraft/BaselineR5AllBuilds.json/.md`. The median averages the two central samples of each 360-sample run; the native summaries' 9.039 / 9.095 ms values select the upper central sample.

- 60 Hz world, Jolt and full skeletal presentation; actual 30 Hz CPU NN, sequential Walk then Upper, batch 100.
- 22 bodies, 21 hard PHAT joints and 88 bones per agent, with all retained UE query bodies.
- Full `Physical` (Sim) mode with Jolt ownership. Each native manual agent has one active `PhysicalMesh`; its inherited `Mesh` has no mesh asset and ticking disabled. NN targets remain pose data, not a second animated skeleton. The retained UE bodies serve queries with Chaos dynamics off.
- SSE2; seven Jolt workers; exclusive-owner no-lock idle reads; DuringPhysics coordinator; 40 cm query-tree padding.
- Original physical feedback; Game ORT per-session pool, intra-op 1 / inter-op 1 / sequential execution.
- Movement-only crowd shells omit optional cameras/fist closing. Controlled P-class game-thread placement was explicit and restored by the benchmark.

These are NullRHI world-tick results on a separated moving grid with a static floor. They exclude rendering and active blood GPU work; this is not final production-scene acceptance or a promise that every frame is below 10 ms. The user accepts those recorded results as the checkpoint for proceeding.

The later ORT threading, prepared feedback and pose-build batching experiments did not establish a repeatable whole-tick improvement. Keep their original defaults; the pose-build candidate was rolled back and the main Editor rebuilt successfully. Do not repeat these experiments during the integration phase.

Workflow: iterate and test in standalone. Cook/package the final integrated candidate for verification, not each intermediate edit. No additional production-wide affinity or physics default changes are implied by this benchmark record.
