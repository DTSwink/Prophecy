# Optional arm repellant cone

Wrist recoil is removed: no pointing/roll springs, idle-reference captures, wrist settings maps, per-attack wrist-strength node, wrist debug drawing or wrist pins remain in runtime code. The exact pre-removal source is archived under `Saved/FKReturn/wrist-removal/before/`; historical behavior is in [the archive](Journal/ArmRepellantCone-history-through-2026-10-02.md).

The upper-arm cone remains available as an opt-in feature. `Set Arm Repellant Cone` defaults Enabled=false; `Set Attack Arm Repellant Cone Enabled` defaults every attack to false. Zero radius or strength also disables it. Disabling retires its recovery, spring, publication cache and blend clock immediately.

The current PoseAgent Blueprint's cone setup, selection and visualizer nodes are retained disconnected, with their execution paths bypassed. The master Enabled literal is false. This avoids repeating setup and drawing calls from Tick while keeping the old tuning available. Wrist pins are removed and execution flow through the rest of the graph is preserved.

With no active cone anywhere, the attack publication path reads one global boolean and skips the per-agent lookup, pose copies, geometry, springs and history. Disabled visualization returns before reading the NN pose. No feature timer or extra inference runs. Lifecycle/setup calls are event work; this is not a claim of literally zero CPU instructions.

Explicitly reconnecting and enabling the master plus selecting attacks restores cone correction during selected full/half attacks. Automatic upper-body return cancels the legacy cone so the FK return owns the handoff. The retained native hold/blend code is available for explicit use, with the existing 60-game-tick timing contract. Lower-body behavior is unchanged.

Validation: Live Coding compiled and loaded October 2 at approximately 17:30:46 UTC. The Blueprint cleanup removed five wrist pins, disabled the master and bypassed three cone calls; Blueprint compile status 3, execution connections valid. The before/after graph comparison contains only the intended cone/pin changes and execution bypass. `DisabledByDefault`, `RegionalLifecycle` and `FeedbackOnlyCorrectedArms` all passed at 17:31:10 UTC. Evidence: `Saved/FKReturn/wrist-removal/`. No explicit asset save or editor restart; user Play was preserved. This is Live Coding coverage only: normal DLL rebuild remains required before a cold launch.
