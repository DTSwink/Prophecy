# Walk pinning smoothing

`Set Walk Pinning Smoothing` takes Agent, Enabled, Pin In Frames (default3), and Pin Out Frames (default3). Off until explicitly called with Enabled. Both frame counts zero also bypasses the feature.

Each foot independently ramps its applied Walk pin strength: a full0→1 change takes Pin In Frames unpaused game ticks, and1→0 takes Pin Out Frames.60ticks means one authored second at every framerate; wall delta and agent speed do not scale it. Linear constant-rate ramps begin from the current weight, so a half-strength release takes half the full release duration. Reversing direction does not jump or restart from an endpoint. Zero makes that direction immediate. Repeated calls with unchanged settings do not restart ramps. Enabling starts with zero pin strength.

The existing Walk winner/tolerance decision supplies the target. Smoothed weights feed actual foot-roll/pinning before checkpoint mixing and final pose clamps. They are sampled when the existing NN evaluation runs; this adds no inference or publication rate. Raw pin debug remains the requested decision, effective pin debug reflects smoothing and subsequent vetoes. Hidden hand-recovery policy evaluations do not change the smoothing history.

Raw-value limit and full-extension reach guard retain immediate priority, clearing any residual weight for the affected foot. No pin is transferred to the other foot by a veto. Normal direction changes can temporarily leave both feet partially pinned. Run and active attack/parry/dodge outputs are unchanged. Special entry, reset and pure Run clear history while preserving configuration; returning to Walk starts fresh.

Disabled has no stored per-agent smoothing state, timer, interpolation or extra inference; the existing policy path only checks the empty configuration guard. Enabled but stable retains its configuration/history without a tick callback. World cleanup removes it. Integration lives in ProphecyWalkPinningLibrary and the shared locomotion correction path; no Blueprint wiring is added automatically.

Validation: Live Coding build passed149.42s and loaded10:31:25UTC. `Prophecy.NN.WalkPinning.Smoothing` passed10:31:55UTC. The focused native test covers independent rise/fall rates, reversal, exact60-tick endpoints at30/60/120FPS, repeated reads/setters, pause, zero durations, hard vetoes, reset and disabled cleanup.

Canonical reflected node invocation verified. The existing Python wrapper retained its pre-reload method list, so validation used the canonical reflected class/CDO. Pose Blueprint compiled status3 after repairing47 archived library default-object references; other values/wiring preserved, zero stale native agent properties/pins. No asset save, node wiring, Play session or restart. Include live changes in the normal editor DLL before a fresh launch.
