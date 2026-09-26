# Runtime NN interpolation

On a Prophecy Agent, use **Set NN Interpolation Mode**:

- **Current (Linear / Viewer Rotation)**: the existing implementation, and the default for every agent.
- **Hermite Positions / SLERP Rotations**: bounded cubic Hermite world positions with standard quaternion SLERP rotations.
- **Attack Viewer**: linear world positions with standard shortest-path quaternion SLERP rotations, matching the original attack viewer's interpolation. Despite the name, the selection applies to all of this agent's modes, including locomotion, attacks, dodge and parry.

**Get NN Interpolation Mode** returns the agent's requested mode. Changes apply when the next NN pose is published, so a running interval is not reinterpreted midway. The setting is per agent and survives simulation-mode changes. It is runtime-only; call the setter from Begin Play to opt in persistently through your Blueprint.

All modes use the existing 30 Hz inference and presentation clock. Neither optional mode adds a buffered frame or inference. The selection applies to the visible NN pose, pelvis presentation reads and physical-animation targets. Existing interpolation enable/disable controls and limb attachment corrections still apply.

Hermite tangents are estimated from already available world-space pose history. Each coordinate stays between its two endpoints; stationary coordinates remain stationary. Tangents restart with a straight segment when history is unavailable or discontinuous. A world-preserving root rebase retains the curve. Bounding can interrupt velocity continuity at abrupt stops or reversals; this is not a promise of continuous acceleration or a fix for discontinuous NN output. Rotations use SLERP, not a cubic rotation curve.

Implementation is isolated in `ProphecyNNInterpolation`. Hermite curve data is prepared once per published pose and stored with that snapshot. Current and Attack Viewer have no tangent storage; switching away from Hermite frees it. Attack Viewer bypasses Current's extra angle/atan2 rotation weighting. It performs less rotation math, but performance has not been benchmarked. Existing enum values and the default remain unchanged.

Correctness automation: `Prophecy.NN.Interpolation` (mode defaults/switching, endpoints, SLERP, history, stationary points, bounds, root rebases and cleanup).

2026-09-25 validation: all three tests pass with Attack Viewer, including switching from warm Hermite, zero tangent capacity, linear travel, shortest-path/antipodal rotations and pelvis presentation agreement. Live Coding loaded; native enum exposes Attack Viewer as value2 and the pose Blueprint compiles with wiring/defaults preserved. Full train replay with this mode was not completed because this editor session's Python enum wrapper retained its old member cache; this is not a new parity measurement or a performance benchmark.
