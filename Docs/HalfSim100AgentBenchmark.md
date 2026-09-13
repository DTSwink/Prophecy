# 100-agent Half Sim / Sim test — 2026-09-08

## Result

Exploratory PIE comparison on the current machine, not a packaged-build or isolated Chaos benchmark:

| Configuration | Mean FPS | Mean frame time | Mean World Tick CPU |
| --- | ---: | ---: | ---: |
| Half Sim on inherited `Mesh`, extra mesh disabled | 2.62 | 381.68 ms | 262.81 ms |
| Sim on `PhysicalMesh`, existing Blueprint follower | 1.92 | 520.96 ms | 340.43 ms |

Half Sim reduced measured frame time by 26.7% (36.5% higher FPS). Neither configuration is usable at 100 agents in this test. This does **not** establish that Chaos Half Sim itself is 26.7% cheaper: controller paths differ and the heavily overloaded Sim crowd drifted substantially during each pass.

## Method and audit

- Fresh PIE per pass: Half Sim, Sim, Sim, Half Sim; 5-second warm-up and 8-second wall-time sample per pass.
- 100 individually registered NN agents, 10 × 10 grid with 300 cm spacing, shared camera, forced LOD0, shadows disabled on active meshes, stationary locomotion intent.
- Half Sim uses `Mesh` for animation and physics. Extra `PhysicalMesh` is renamed only on PIE copies, emptied, hidden, non-colliding, non-simulating and non-ticking. Actor tick is disabled to remove the obsolete Blueprint follower; the NN manager and active mesh still tick.
- Sim retains the current Blueprint follower on `PhysicalMesh`; inherited `Mesh` is empty and disabled by the normal manager setup.
- Every before/after audit passed: 100 registered agents, exactly 100 asset-bearing meshes, 100 pelvis-simulating meshes, and 100 disabled extra skeletal-mesh components.
- Half Sim pass FPS: 2.41 / 2.84. Sim pass FPS: 1.85 / 1.99. Only 43 Half Sim and 31 Sim frames were collected, so precision is limited.
- Pelvis positions are included in the raw report. Half Sim stayed close to its initial grid; Sim drifted around 20 metres along one axis. Treat this as a configuration stress test, not equal-motion physics profiling.
- Startup emitted transient collision/simulation warnings. After the first measured pass, PIE teardown produced a handled `ConstraintInstance.IsTerminated()` ensure in constraint destruction; it was outside the measurement window. The runtime-template duplication harness should be hardened before reuse for authoritative profiling.
- No map or Blueprint assets were saved; PIE ended and the editor stayed open. This does not permanently migrate production agents to one mesh.

## Files and reproduction

- Editor-only console harness: `Source/ProphecyEditor/Private/ProphecyHalfSimBenchmark.cpp`, command `Prophecy.HalfSimBench.Prepare HalfSim` or `Physical`, PIE only.
- Runner: `Tools/NN/Benchmark100AgentModes.py` (execute inside Unreal Python while PIE is stopped).
- Raw measurements and component/position audits: `Saved/Benchmarks/100_agent_modes.json`.
- Initial setup smoke check: `Saved/Benchmarks/100_smoke.json`.

Live Coding initially exposed unity-build helper-name collisions after the earlier Git commit changed adaptive-unity membership. Only private helper identifiers were renamed in `ProphecyModeTransitions.cpp`, `ProphecyRetractableSkeletalMeshComponent.cpp`, and `ProphecyPotenceRopeVisualComponent.cpp`; their behavior is unchanged. Compilation and Live Coding then succeeded. No additional Git push was performed.
