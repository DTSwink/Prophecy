# Physical profile snapshots

At the end of delayed BeginPlay setup, call **Save Physical Profile Snapshot** with this agent. Leave `Snapshot Name` as `None` for one default snapshot, or use names for multiple presets. Names belong to each individual agent. Calling Save again with the same name replaces that snapshot. These are runtime snapshots, not disk saves; they are removed when the agent ends play.

Saving also captures the **PhysicalMesh physical-material override**, including a
null override. Get Up immediately restores this value from slot `1` through the
existing Jolt-aware mesh setter. Material assets are retained while saved; replacing
or deleting the snapshot releases the old reference. Missing snapshots leave the
material alone. This addition does not change material on attack/defense entry or
ordinary strength/tolerance/mode snapshot returns. Re-save pre-patch snapshots to
capture their material.

To start returns at attack completion, add **Event On Attack Ended** in the pose-agent Blueprint. It is an inherited `AProphecyAgent` Blueprint event (`OnNNAttackEnded`), with the ended attack's name as an output. It fires once after native cleanup on natural completion, explicit stop/cancel, or replacement by another attack/defense. It does not fire merely when the NN outputs Hit, or when Stop is called while already inactive. Connect the desired blend nodes directly to this event. The event has no polling, timer or per-frame work. During Reset Initial Agents, the reset's baseline restore still takes precedence over blends started by the attack-ended event.

**Special entry (October 6):** an actual attack (full or half), Parry or Dodge immediately restores this agent's snapshot named **`1`**. This restores every saved magnetization, feedback-tolerance and joint-damping profile cell, plus all supported clamp modes, with exact enabled/override flags and remembered leeways. Pending returns for these saved values are cancelled; they cannot resume after the special. A queued defense waits until Armed/activation. Full/half mode changes are not new special entries. Slot `1` replaces the old hardcoded attack magnetization/tolerance/damping defaults for that special. Missing slot `1` leaves previous behavior unchanged. Other named/default snapshots and the private reset snapshot are not selected automatically. No new node, timer, inference or recurring snapshot scan is added; save slot `1` during setup. Global strength/gate controls, simulation membership and gravity remain outside this snapshot's scope.

Editor repair note (2026-09-20): adding the native event through Live Coding left some existing library parameters and graph pins referencing a temporary `LIVECODING_ProphecyAgent_0`. This produced Self/Agent incompatibility errors. The explicit editor command `Prophecy.Editor.LiveAgentTypes Inspect|Repair` detects and retargets those exact stale native-agent references and pose-agent pin types, compiles the Blueprint, and verifies its wiring/default values without saving. The current session was repaired and the Blueprint compiled successfully; this is not an attack/blending behavior change.

After your existing per-bone setters temporarily change values, use:

- **Blend Body Magnetization To Snapshot** / **Below To Snapshot** / **Blend All Body Magnetization To Snapshot**.
- **Blend Physical Feedback Tolerance To Snapshot** / **Below To Snapshot** / **Blend All Physical Feedback Tolerances To Snapshot**.
- **Blend Joint Angular Damping To Snapshot** / **Below To Snapshot** / **Blend All Joint Angular Damping To Snapshot**.
- **Blend Clamp To Snapshot** (Calf or Foot selector), **Blend All Clamps To Snapshot**.
- **Blend Magnetization Mode To Snapshot**.

Use the same snapshot name and an authored duration: 1 means60 unpaused game ticks regardless of actual FPS or time dilation. Every To Snapshot node has **Hold Out Time**, default0 seconds. It retains the current values before interpolation starts; duration counts only the interpolation after that hold. Zero or negative duration snaps at the end of the hold. Negative/nonfinite hold is rejected without changing the previous request. Single-bone nodes return success; Below/All return the number of matching saved entries. Below respects Include Parent. Missing names/bones do nothing and return false/zero. Saving captures magnetization, magnetization mode, tolerance, damping and clamps; restoring each kind is independent and does not alter the others. Snapshots are reusable. Damping requires a live Jolt rig when restoring; it covers anatomical inbound joints, not the sword grip. Re-save snapshots made before the new kind was supported.

**Delayed tolerance writes during a snapshot hold (October 7):** a tolerance
snapshot return keeps its requested interpolation duration even when its current
value already matches the snapshot. If a delayed tolerance setter expires during
that hold (including the positive-duration blend's first tick), it changes the
starting tolerance without cancelling the scheduled return or restarting its
hold. This applies to single/Below/All returns and setter scopes, preserving the
four walk/run/equipment cells. Example: schedule a delayed tolerance change and
an All Tolerances To Snapshot return with Hold1/Duration1; the delayed value stays
until the original hold ends, then returns over the following60 ticks. A new
snapshot blend still replaces the old request. Ordinary immediate setters and
explicit cancellations retain their cancellation behavior; a delayed setter
after interpolation has begun is also a new overriding write.

Magnetization/tolerance/damping entries include all four walk/run × drawn/sheathed profiles. Restores blend each cell independently with the existing smoothstep curve, so policy changes during restoration continue to select/blend the correct values. Saving an unfinished blend captures its current values, not its destination. Without a slot `1` restore, legacy attack defaults remain in force and save/restore operates on underlying locomotion profiles. With slot `1`, restored profiles remain effective during the attack and normal context selection still applies.

Clamps retain shared left/right Foot and Calf settings in Locomotion, Attack, Parry and Dodge: eight saved entries. Save includes enabled state, remembered leeway and override/inheritance flags. Inherited settings return to inheritance at the endpoint. Mode defaults to All and can restrict the return to one mode. Hand/Forearm clamp entries mentioned in the historical validation below are no longer supported.

**Set Magnetization Mode** configures the current Jolt drive for this agent:0 follows the actual physical parent,1 keeps the existing world target, intermediate values blend those targets. Default1 preserves existing setups. The pelvis remains world-driven. Bones without their own simulated parent use the nearest physical ancestor. Each body uses one servo; local and intermediate modes share the same parent sampling path. Parent links are cached at rig admission. The servo evaluates parents before children and carries each local target with its parent's commanded endpoint for the current physics step. This allows the connected chain to straighten without its position drives resisting its angular drives. Gravity cancellation is not inherited a second time; the previous solved parent velocity is not added on top of the correction. A parent without a drive retains the existing physical-frame fallback. Global mode bypasses the local hierarchy. Topology is cached, endpoint scratch is reused, and no allocation occurs in the physics step. This mode is distinct from magnetization strength.

**Get Magnetization Mode** reads the current value. Save Physical Profile Snapshot captures it, and **Blend Magnetization Mode To Snapshot** restores it using the same hold and smoothstep timing. The existing per-bone/Below/All magnetization-strength returns remain independent; they do not change the agent-wide mode. Special entry restores the mode saved in slot1 immediately and cancels its pending hold/blend, like the other saved values. Set the desired mode before saving slot1 if you want that mode during specials. Reset restores its captured baseline. No new inference, additional solver, continuous idle blend timer or saved-asset format is introduced.

**Per-body modes (October 6):** **Set Body Magnetization Mode** changes one physical
bone, and **Set Body Magnetization Mode Below** changes physical bones in a skeletal
subtree, with Include Parent. **Set Magnetization Mode** replaces every override
and cancels all mode returns. **Get Body Magnetization Mode** reads the selected
bone's configured value; the older getter reads the shared baseline. The pelvis
always uses world targets regardless of its configured mode.

Snapshots capture every body's mode. **Blend Body Magnetization Mode To Snapshot**
and **Blend Magnetization Mode Below To Snapshot** restore only their selection;
the original mode-return node restores the whole saved mode profile. All have
Hold Out Time. A single-body setter cancels only that body's return, including
when it is assigned the current value during a whole-body return. Slot1 and reset
also restore mixed profiles. Uniform profiles and uniform-to-uniform returns use
one scalar, with no per-body mode lookup in the drive loop. Mixed profiles cache
their values in physical-body order when edited; unchanged frames use indexed
reads. Completed identical profiles collapse back to uniform.

`Print Physical Bone Profiles` shows fixed attachment for hands and locomotion Foot/Calf clamps on foot rows, without units, for example ` / Clamp=Foot:3.00 Calf:4.00`. Other rows and the magnetization/tolerance/damping fields keep their format.

**Magnetization strength (October7 rollback):** original momentum-preserving
velocity blend: `v += strength * (error / duration - v)`.0 disables that channel;
1 uses the original full-strength command. All anti-wobble experiments were
removed at the user's request: direct fractional landing, predictive crossing
brakes and the experimental small-angle calculation. The earlier accepted local
parent prediction fix remains. Overshoot can occur with the original response.

Magnetization captures enabled plus linear/angular scales. Restoring disabled magnetization fades toward zero, then restores the disabled flag and its remembered scales. Simulation membership, gravity cancellation, global strength/gate settings and physics state are intentionally not part of these strength/tolerance profiles.

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
