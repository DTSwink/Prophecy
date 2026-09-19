# Physical profile snapshots

At the end of delayed BeginPlay setup, call **Save Physical Profile Snapshot** with this agent. Leave `Snapshot Name` as `None` for one default snapshot, or use names for multiple presets. Names belong to each individual agent. Calling Save again with the same name replaces that snapshot. These are runtime snapshots, not disk saves; they are removed when the agent ends play.

After your existing per-bone setters temporarily change values, use:

- **Blend Body Magnetization To Snapshot** / **Below To Snapshot** / **Blend All Body Magnetization To Snapshot**.
- **Blend Physical Feedback Tolerance To Snapshot** / **Below To Snapshot** / **Blend All Physical Feedback Tolerances To Snapshot**.

Use the same snapshot name and an authored duration: 1 means60 unpaused game ticks regardless of actual FPS or time dilation. Zero or negative duration restores immediately. Single-bone nodes return success; Below/All return the number of matching saved entries. Below respects Include Parent. Missing names/bones do nothing and return false/zero. Saving and restoring magnetization/tolerance is independent: restoring one does not alter the other. Snapshots are reusable.

Each saved entry includes all four walk/run × drawn/sheathed profiles. Restores blend each cell independently with the existing smoothstep curve, so policy changes during restoration continue to select/blend the correct values. Saving an unfinished blend captures its current values, not its destination. Attack defaults remain in force; save/restore operates on the underlying locomotion profiles during attacks.

Magnetization captures enabled plus linear/angular scales. Restoring disabled magnetization fades toward zero, then restores the disabled flag and its remembered scales. Simulation membership, gravity cancellation, global drive settings and physics state are intentionally not part of these strength/tolerance profiles.

Saving adds no tick callback or per-frame snapshot lookup. Restores use the existing context/blend update. Completed identical profiles release that update state; different conditional profiles retain the existing context selection behavior. No snapshots or allocations exist for agents that never save.

## Hit-filter diagnosis (2026-09-18)

The live BP_ProphecyManualPoseAgent graph was inspected using the read-only collision graph audit. Its non-magic-cube Event Hit branch tests cast success, `OtherComp == Other.PhysicalMesh`, and `GetAgentState(Other) == Attacking`. It then changes **Self** magnetization/tolerance. There is no `Other != Self` test on this path. An older OtherComp filter elsewhere is bypassed by Event Hit's direct execution link.

Jolt deliberately emits generic hit events for self-collision as well as inter-agent collision. For self-collision, both component owners are the same actor: Other is Self. An attacking agent's own limb contact therefore satisfies every current condition. Add **Other != Self** to the AND before applying the hit reaction. For an actual A-attacks-B contact, B sees A (Attacking), and A sees B (e.g. Dodging), as expected. The state getter resolves the supplied agent's own manager handle; it is not shared state.

This is a graph/code diagnosis, not a captured runtime pair trace. No production Blueprint/map was modified or saved. Generic self-collision hit notifications are preserved.
