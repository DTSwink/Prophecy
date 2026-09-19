# Optional Jolt collision substeps

`Set Jolt Collision Substeps` takes **Enabled** and **Substeps** (default pin value2, accepted1–16). The feature is **off by default**. `Get Jolt Collision Substeps` reports the override.

- Enabled with2: at least two collision/integration steps per game frame, approximately120Hz at60FPS.
- Enabled with4: at least four, approximately240Hz at60FPS.
- Disabled, or Substeps1: restore ordinary project stepping.
- A higher count already required by the project timestep settings is preserved.

This controls the **shared Jolt world**, including all agents, swords and scene bodies. It is not per-agent; use one place to control the toggle, as conflicting calls use the last value. Call once or change it when needed—no need to call every Tick. It does not enable CCD, enlarge colliders, synthesize hits, alter the30Hz NN cadence or change project PhysicsSettings. The animation drive uses the same actual substep duration as the solver. Disabled adds no extra physics steps, NN evaluations or capture work. Enabled costs more physics work across the world; no performance benchmark was requested or run.

## Visible penetration reproduced

The earlier investigation focused too much on complete missed crossings and hit callbacks. The user's issue is **visible overlap during a contact that may still register a hit**. A fresh diagnostic measured the authored PHAT shapes at the displayed `PhysicalMesh` bone transforms, rather than body-origin distances or callback counts.

Three disposable PIE runs used the same five-hook schedule (L/R/L/R/L), face-to-face starting placement, head-target updates and Armed-gated Dodge. All used Discrete Jolt mode. Each sampled541 displayed frames from approximately1–10seconds; the measured pairs were each hand/forearm against the defender's head. Changing physics stepping changes the subsequent physical/NN-feedback trajectory, so these are comparable scenario runs, not identical recorded trajectories or a universal error bound.

| Minimum substeps/frame | Worst hand/head overlap | Frames with hand/head overlap | Frames above2cm |
|---|---:|---:|---:|
| Ordinary (1 at60FPS) | 3.520cm | 4 | 3 |
| 2 | 0.098cm | 1 | 0 |
| 4 | 0.313cm | 1 | 0 |

All positive measurements were `hand_l` against `head`; right hand and both forearms had no positive head overlap in these captures. The baseline peak occurred at9.433seconds. **Start with2**: it improved this scenario markedly, and4 was not better here. This does not prove that all visible skin intersections disappear or that greater substep counts monotonically improve every rollout. PHAT sweeps were not installed as a physical-response fix: detecting a swept crossing alone cannot prevent the displayed hand from penetrating the head.

## Implementation and validation

- Sparse per-world settings in `ProphecyJoltBlueprintLibrary.cpp`; lifecycle cleanup in the coordinator; shared `ProphecyJoltStepTiming` count/duration used by both coordinator and character target preparation.
- Non-shipping, explicitly invoked console diagnostic: `Prophecy.Debug.MeasureHandHead <attacker actor name> <defender actor name>`. Logs `PHAT_OVERLAP,time,attacker,defender,bone,depth_cm`. No automatic tick/observer or enabled-by-default capture. It queries PHAT geometry at displayed poses; it is not a GPU skin-vertex intersection test or a separate native-body depth measurement.
- `FProphecyJoltContactShape::PenetrationCm` shares the authored simple-shape builder used by the existing defense queries. Analytic capsule/sphere overlap test passed.
- `Prophecy.Jolt.Character.SubstepTiming` passed: default, enable/disable, matching drive duration, invalid-count rejection, preservation of a higher project count.
- Live Coding initially hit a new cross-module diagnostic-symbol link failure. Moving the diagnostic/test into the Jolt module resolved it; final patches installed without restarting Unreal. Failed-link test execution was not used as final validation.
- Evidence: `Saved/Diagnostics/HookPenetrationSummary.json`, `HookPenetrationDepth_{1,2,4}.json`, `HookPenetration_{1,2,4}.json`; scripts `capture_hook_penetration.py` and `summarize_hook_penetration.py`.
- Scene transforms restored, no Blueprint/map saves or production quality override left enabled. The user can wire the node to their preferred phase/control.
