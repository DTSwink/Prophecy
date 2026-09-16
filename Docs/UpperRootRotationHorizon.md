# Upper root rotation horizon

`Set Upper Root Rotation Horizon(Agent, Horizon=1)` changes the future root orientations supplied to that agent's upper locomotion NN. `Get Upper Root Rotation Horizon` reads its current setting. Values must be finite and between 0 and 1; invalid calls return false without changing the setting.

- **1:** original inputs, bit for bit.
- **0.5:** the first half of the orientation window is resampled across all eight future samples.
- **0:** all future orientations equal the present root orientation.

This matches the temporary UpperRootHorizonPreview viewer: prepend the present relative yaw (zero), unwrap the eight future yaw angles, sample at `(sample index + 1) * Horizon`, then write cosine/sine back. It shortens the preview horizon; it does not multiply each angle by the factor or freeze the last half of the window.

Only the upper input's 16 future orientation values change. Future root positions, current root velocity, pelvis/lower features, gaze, the lower policy's input and the shared root window stay unchanged. Separate attack-policy inputs are unaffected. In a coupled physical/feedback setup, changed upper motion can naturally influence subsequent physical motion; this is not a promise to isolate those downstream interactions.

Each manager lane caches one scalar. At 1, an inline comparison returns before any resampling, trigonometry, allocation or configuration lookup. Other values use a fixed nine-angle stack buffer; zero writes identity orientations directly. There is no extra NN evaluation, component, timer or tick. The setter alone updates weak per-agent configuration and the manager cache, including support for setup before agent registration. Settings are removed on world cleanup.

Focused regression: `Prophecy.NN.UpperRootHorizon.Resampling` checks exact default bypass, zero, half and fractional horizons across wrapped yaw, and preservation of every other root feature. Runtime smoke script: `Tools/NN/TestProphecyUpperRootHorizon.py`.

Validated 2026-09-15: compilation and Live Coding patches succeeded without restarting. The focused automation passed with zero warnings/errors; short current-scene PIE passed independent settings on two of three agents, unchanged third-agent default, invalid argument rejection, restoring 1, and world cleanup. No asset edits/saves or performance benchmark. Live reload emitted handled RigVM/ControlRig reference-replacement access-detector ensures; the subsequent Play session completed successfully. Evidence: `Saved/Diagnostics/UpperRootHorizonPIE.json`, `UpperRootHorizonAutomation.log`, `BuildUpperRootHorizon.log`. The base DLL should incorporate these changes at the next planned normal build.
