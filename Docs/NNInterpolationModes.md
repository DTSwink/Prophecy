# Runtime NN interpolation

On a Prophecy Agent, use **Set NN Interpolation Mode**:

- **Current (Linear / Viewer Rotation)**: the existing implementation, and the default for every agent.
- **Hermite Positions / SLERP Rotations**: bounded cubic Hermite world positions with standard quaternion SLERP rotations.

**Get NN Interpolation Mode** returns the agent's requested mode. Changes apply when the next NN pose is published, so a running interval is not reinterpreted midway. The setting is per agent and survives simulation-mode changes. It is runtime-only; call the setter from Begin Play to opt in persistently through your Blueprint.

Both modes use the existing 30 Hz inference and presentation clock. The new mode adds no additional buffered frame or inference. It applies to the visible NN pose and its physical-animation targets, including locomotion and attacks. Existing interpolation enable/disable controls and limb attachment corrections still apply.

Hermite tangents are estimated from already available world-space pose history. Each coordinate stays between its two endpoints; stationary coordinates remain stationary. Tangents restart with a straight segment when history is unavailable or discontinuous. A world-preserving root rebase retains the curve. Bounding can interrupt velocity continuity at abrupt stops or reversals; this is not a promise of continuous acceleration or a fix for discontinuous NN output. Rotations use SLERP, not a cubic rotation curve.

Implementation is isolated in `ProphecyNNInterpolation`. Curve data is prepared once per published pose and stored with that snapshot. Default agents have no tangent storage. Performance has intentionally not been benchmarked.

Correctness automation: `Prophecy.NN.Interpolation` (mode defaults/switching, endpoints, SLERP, history, stationary points, bounds, root rebases and cleanup).
