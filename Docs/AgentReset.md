# Initial agent reset

Call **Initialize Agent Reset** once after the NN manager has initialized its agents, before starting movement. `Agent Count` reports captured agents. Check `Return Value` / `Out Error`: calling before NN initialization is rejected and can be retried. Calling again after success keeps the original checkpoint.

Connect a key's **Pressed** execution pin to **Reset Initial Agents**. The request is queued once at the next timer boundary, so an input or hit callback cannot tear down a physics rig during its publication. Repeated requests before that boundary coalesce. Success means accepted; a later per-agent failure is reported in the Output Log.

Reset restores captured root location/yaw and the published lower/upper pose. It resets both previous/current NN pose histories, physical feedback history, interpolation tangents and all future roots. The window starts collapsed at the restored root. Linear/angular root momentum, movement input, both magic velocity sets, foot-pinning debug samples, hand/pelvis inertia history and the prepared balancing target are cleared. Attacks, defense and NN animation layers are stopped.

Current tuning remains in place: feedback tolerances, magnetization, root smoothing factors, inertia follow factors, interpolation mode and simulation mode are not reset. Physical rigs are recreated at the restored pose, clearing their velocities and cached contacts/constraint impulses. Captured auxiliary primitive components on each agent (including the magic cube) return to their captured transforms with zero velocity through the Jolt-aware standard component API.

Only captured, still-existing registered agents are reset. Later spawns are excluded; destroyed agents/components are skipped. This is a motion/pose reset, not a save-game restore: it does not reset arbitrary Blueprint variables, restart BeginPlay, respawn dropped weapons, undo Blueprint graph edits, or rewind custom timers. For example, reset `tick debug` yourself if your test logic uses it. A Tick graph that keeps issuing movement/impulses will naturally resume after reset.

Capture must occur outside an attack/defense/animation layer. The external standalone Sim Bridge is unsupported and rejected; this reset operates on native UE NN agents.

No ongoing per-frame scan, tick component or timer. Capture allocates session-only snapshots; reset temporarily schedules a single callback. Snapshots are released on manager EndPlay/world cleanup. New native storage is separate from existing retained Live Coding allocations.

Implementation: `ProphecyAgentResetLibrary.*`, `ProphecyNNAgentReset.inl`. Focused pure-state automation: `Prophecy.NN.AgentReset.MotionAndWindow`. Gameplay testing is left to the user.

Installed 2026-09-16 through the shared feedback/reset Live Coding build (452.75 seconds), without restarting Unreal. Both reflected nodes loaded and rejected an invalid world; the native motion/window reset test passed. Live scene reset was not exercised. Evidence: `Saved/Diagnostics/AgentResetNodes.json` and editor log test completion at 10:30:53 UTC.
