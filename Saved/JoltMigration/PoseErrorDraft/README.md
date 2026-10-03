Draft only. No active source, engine, build or asset changes.

`Proposed.patch` changes four existing files; `Baseline.json` records exact active and proposed SHA-256 hashes. Full proposed files are under `proposed/`.

The character retains each captured body mass before Chaos becomes QueryOnly. A private helper, accessible only to the Agent friend, returns the captured mass, completed native dynamic body-origin transform and binding-local body index. The Agent deduplicates that index and feeds its existing accumulation math. The Chaos path, Presented target selection, sign, units, shortest angular arc, unnormalized sums and output types remain unchanged. No COM/bone-frame conversion or public API is added. Stopped/stale Jolt bindings do not fall back to Chaos.

The existing LiveJolt fixture now checks the API immediately after handoff and after every measured step. Its independent reference uses `ManualInitialRig` pre-handoff masses, direct world `ReadBody`, original Presented targets and unique native slots. JSON records returned/reference linear and angular sums, mass, body counts and differences under `mass_weighted_pose_error`; mismatches fail the existing fixture. This closes the QueryOnly early-return regression and exercises current moving native bodies; it does not inject duplicate target names or alter gameplay poses.

After promotion/build, use the existing correctness run:

```powershell
./Tools/NN/RunSterilePhysicsBenchmark.ps1 -Methods JoltLive -Count 1 -Warmup 30 -Samples 60 -Repeats 1 -Label jolt_pose_error
```

No runtime result is claimed by this draft. Cutting remains deferred, including the mismatch between disconnected exported sword execution chains and historical runtime cut-constraint evidence.
