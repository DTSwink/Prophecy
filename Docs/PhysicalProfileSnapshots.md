# Physical profile snapshots

At the end of delayed BeginPlay setup, call **Save Physical Profile Snapshot** with this agent. Leave `Snapshot Name` as `None` for one default snapshot, or use names for multiple presets. Names belong to each individual agent. Calling Save again with the same name replaces that snapshot. These are runtime snapshots, not disk saves; they are removed when the agent ends play.

To start returns at attack completion, add **Event On Attack Ended** in the pose-agent Blueprint. It is an inherited `AProphecyAgent` Blueprint event (`OnNNAttackEnded`), with the ended attack's name as an output. It fires once after native cleanup on natural completion, explicit stop/cancel, or replacement by another attack/defense. It does not fire merely when the NN outputs Hit, or when Stop is called while already inactive. Connect the desired blend nodes directly to this event. The event has no polling, timer or per-frame work. During Reset Initial Agents, the reset's baseline restore still takes precedence over blends started by the attack-ended event.

Editor repair note (2026-09-20): adding the native event through Live Coding left some existing library parameters and graph pins referencing a temporary `LIVECODING_ProphecyAgent_0`. This produced Self/Agent incompatibility errors. The explicit editor command `Prophecy.Editor.LiveAgentTypes Inspect|Repair` detects and retargets those exact stale native-agent references and pose-agent pin types, compiles the Blueprint, and verifies its wiring/default values without saving. The current session was repaired and the Blueprint compiled successfully; this is not an attack/blending behavior change.

After your existing per-bone setters temporarily change values, use:

- **Blend Body Magnetization To Snapshot** / **Below To Snapshot** / **Blend All Body Magnetization To Snapshot**.
- **Blend Physical Feedback Tolerance To Snapshot** / **Below To Snapshot** / **Blend All Physical Feedback Tolerances To Snapshot**.
- **Blend Joint Angular Damping To Snapshot** / **Below To Snapshot** / **Blend All Joint Angular Damping To Snapshot**.
- **Blend Clamp To Snapshot** (Calf, Forearm, Hand or Foot selector), **Blend All Clamps To Snapshot**.

Use the same snapshot name and an authored duration: 1 means60 unpaused game ticks regardless of actual FPS or time dilation. Zero or negative duration restores immediately. Single-bone nodes return success; Below/All return the number of matching saved entries. Below respects Include Parent. Missing names/bones do nothing and return false/zero. Saving captures magnetization, tolerance, damping and clamps; restoring each kind is independent and does not alter the others. Snapshots are reusable. Damping requires a live Jolt rig when restoring; it covers anatomical inbound joints, not the sword grip. Re-save snapshots made before the new kind was supported.

Magnetization/tolerance/damping entries include all four walk/run × drawn/sheathed profiles. Restores blend each cell independently with the existing smoothstep curve, so policy changes during restoration continue to select/blend the correct values. Saving an unfinished blend captures its current values, not its destination. Their attack defaults remain in force; save/restore operates on the underlying locomotion profiles during attacks.

Clamps retain their existing shared left/right settings and separate Locomotion, Attack, Parry and Dodge modes. Save captures enabled state, remembered leeway and override/inheritance flags for all existing clamps (4 locomotion, 3 attack, 4 parry, 4 dodge). It does not add an attack forearm clamp or capture manager-wide defaults; inherited settings return to inheritance at the end. `Mode` on the new restore nodes defaults to **All** and can restrict restoration to one mode.

Clamp selection is by existing clamp type, not by skeleton bone or subtree: choose **Calf**, **Forearm**, **Hand** or **Foot**. Each restores independently and remains shared left/right. There is no Below clamp node. All restores the existing 15 mode/type settings, not 30; Attack + Forearm returns false because that setting does not exist. Replace any previously placed experimental bone/Below restore nodes with the clamp selector node.

Clamp leeway uses smoothstep over the specified number of ticks. A disabled endpoint is represented during a transition by allowance1000 (raised if either remembered leeway exceeds1000), then its exact saved enabled/override flags and remembered leeway are restored. Both disabled endpoints restore immediately since there is no visible clamp to blend. Existing clamp setters cancel only that mode/type's pending return. Reset cancels active clamp returns and restores its privately captured clamp snapshot too. Active returns have a callback only until completion; saving or finished blends add no per-frame callback or polling.

`Print Physical Bone Profiles` appends only locomotion clamps, only on physical hand and foot rows, without units: ` / Clamp=Hand:5.00 Forearm:off` or ` / Clamp=Foot:3.00 Calf:4.00`. These are configured effective locomotion settings; e.g. a configured Forearm clamp can take precedence over Hand in the existing decoder. Other rows and the magnetization/tolerance/damping fields keep their format.

Magnetization captures enabled plus linear/angular scales. Restoring disabled magnetization fades toward zero, then restores the disabled flag and its remembered scales. Simulation membership, gravity cancellation, global drive settings and physics state are intentionally not part of these strength/tolerance profiles.

Saving adds no tick callback or per-frame snapshot lookup. Restores use the existing context/blend update. Completed identical profiles release that update state; different conditional profiles retain the existing context selection behavior. No snapshots or allocations exist for agents that never save.

`Set All Body Magnetization` immediately replaces all active magnetization profiles
and cancels pending magnetization blends, including snapshot returns. Enabled=false
therefore wins even during an attack and stays disabled when the old restore would
have finished or that attack ends. Tolerance/damping restores continue, and the
saved snapshot remains reusable. A later explicit magnetization/restore call is a
new request; the setter is not a permanent death-state lock.

## Clamp snapshot validation (2026-09-20)

The simplified clamp-type selector compiled and loaded via Live Coding; `Prophecy.PhysicalProfiles.ClampSnapshots` passed at 09:37 UTC. The focused test covers save/restore, independent Calf/Forearm/Hand/Foot selection, mixed-FPS 60-tick timing, mid-blend capture, direct-set cancellation, exact disabled/inherited flags, debug suffixes and removal of finished ticking work. Scene behavior remains for user testing.

## Hit-filter diagnosis (2026-09-18)

The live BP_ProphecyManualPoseAgent graph was inspected using the read-only collision graph audit. Its non-magic-cube Event Hit branch tests cast success, `OtherComp == Other.PhysicalMesh`, and `GetAgentState(Other) == Attacking`. It then changes **Self** magnetization/tolerance. There is no `Other != Self` test on this path. An older OtherComp filter elsewhere is bypassed by Event Hit's direct execution link.

Jolt deliberately emits generic hit events for self-collision as well as inter-agent collision. For self-collision, both component owners are the same actor: Other is Self. An attacking agent's own limb contact therefore satisfies every current condition. Add **Other != Self** to the AND before applying the hit reaction. For an actual A-attacks-B contact, B sees A (Attacking), and A sees B (e.g. Dodging), as expected. The state getter resolves the supplied agent's own manager handle; it is not shared state.

This is a graph/code diagnosis, not a captured runtime pair trace. No production Blueprint/map was modified or saved. Generic self-collision hit notifications are preserved.
