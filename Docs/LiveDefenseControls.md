# Live control during parry and dodge

Both responses still wait for the incoming attack's learned Armed output. The defender keeps normal locomotion/attack ownership until then.

During active defense, the existing locomotion input, facing, mover, root impulses, window smoothing, balancing, root speed limits, and both sets of magic velocities remain live. Use the same control nodes. The continuous root-window getter also works during Dodge. Root placement and pelvis bounds rebase the private defense history coherently; capsule collision no longer cancels Dodge.

Parry retains the normal locomotion lower branch. Its upper defense conditioning now receives the newly resolved movement command every step instead of the episode's initial command.

Dodge retains its trained frozen lower networks and private recurrent state. Its lower inputs receive the full live eight-sample mover window, converted into the native heading/mesh-carrier frame and checkpoint normalization. Its upper conditioning receives the resolved next-root command. The trained root displacement and yaw correction are added once to that planned root. They do not rotate world-space magic velocity or become extra mover momentum. Only learned corrections consume Dodge's movement banks. The next recurrent pose is rebased into the combined root. Walk/run selection follows the live input; the Dodge lower branch retains its own checkpoint projection, rather than substituting the normal locomotion networks.

The original fixed-command reference path remains the default of the standalone native Prepare/CompleteDodge helpers for parity fixtures. The live manager explicitly supplies the planned root. New steering intentionally changes the original fixed-command rollout.

## Independent clamps

`ProphecyNNDefenseLibrary` now exposes eight nodes, each with Agent, Enabled and Leeway Cm:

- Set Parry Foot Clamp / Set Dodge Foot Clamp
- Set Parry Calf Clamp / Set Dodge Calf Clamp
- Set Parry Hand Clamp / Set Dodge Hand Clamp
- Set Parry Forearm Clamp / Set Dodge Forearm Clamp

Values are independent per agent and response. Zero leeway means an exact clamp; 1 means one centimetre. Negative/nonfinite values are rejected. Foot limits total leg reach; calf/forearm constrain segment length in both directions; hand constrains wrist attachment displacement. Forearm takes precedence over hand if both are enabled, matching the locomotion arm controls. Clamps affect presentation, not the retained raw defense recurrence. They do not disable Dodge's trained leg IK/bone-length reconstruction or final foot-floor correction.

Before an override, Parry keeps its existing locomotion foot/calf settings, Dodge has no optional foot/calf clamps, forearm is off, and the existing hand interpolation attachment correction remains on at zero leeway. Defense hand settings now have their own defaults rather than inheriting stale settings from the agent's last attack.

## Attack target and response readback

**Trigger NN Attack** has an optional **Victim** agent pin. Unconnected means no designated victim; it does not implicitly select Self. The pin is gameplay association, not automatic head tracking or automatic defense activation. The existing demonstration connects it to CombatDemoOpponent.

**Set NN Attack Target** updates the world-space target of the current attack without resetting the attack frame, recurrent history, Armed/Hit flags or defense history. Call it as the desired aim point moves. Both Parry and Dodge read the updated attack target in their conditioning on subsequent policy steps. Changing targets after Hit does not start a new attack or clear Hit.

**Get NN Attack Victim** returns the designated victim, or None for an untargeted/ended attack. **Get NN Attack Defense State** exposes Being Parried and Being Dodged. Readback includes accepted waiting requests before Armed and active responses afterwards; cancellation/end clears it. With a designated victim, only that agent's response is reported. For an untargeted attack, explicitly requested responses from other agents can still be reported; both flags can be true if different agents respond in different ways. No inference or pose sampling is performed by these getters.

Configurations use optional sidecar storage and are cleared at EndPlay. Outside defense, there is no defense window conversion, history rebase, clamp scan, or additional network evaluation.

## Return to locomotion

Ending a full/half attack into locomotion uses **Set Attack Return To Root Balancing**: true(default) selects the flat midpoint of foot_l and foot_r; false places root XY directly below the pelvis. Simulated body positions take priority over visible kinematic bones. Parry and Dodge continue using the feet midpoint. Root height and existing heading behavior are retained. These handoffs do not require the spring to be enabled and do not depend on its thresholds. Both recurrent frames and the full root window are rebased while preserving the skeleton's world pose; the registered magic cube resets to the repositioned root. Direct replacements do not trigger the locomotion recenter. A cancelled request that never activated does not move the root. Sampling runs only at handoff; the locomotion spring itself is unchanged.

## Validation (2026-09-17)

The 2026-09-19 attack-only pelvis target change compiled and loaded through Live Coding (final build 12.94 s, no warnings). The scene was not replayed; the older feet-midpoint measurements below do not validate the new attack target. No Blueprint/map edits or restart.

Normal Editor build succeeded. Six native Dodge tests passed, including planned-root/residual composition, and all 1046 original fixed-command trace tensors passed the reference comparator. Focused disposable PIE passed live Parry/Dodge steering, retargeting without reset, pre-Armed response flags, all eight clamp setters, and feet-midpoint handoffs for full attack, Parry and Dodge (zero measured root-target/world-bone shift). Half-attack uses the same handoff helper but was not separately exercised. These checks do not constitute extensive physical contact/visual acceptance. Evidence: Saved/Diagnostics/LiveDefenseControls. Unreal remains open, PIE stopped; no dirty map/content packages.

## Physical contact ownership and agent state (2026-09-17)

Predicted attack/defense collider sweeps can finish defense only when the defender is Kinematic. In Sim and Half Sim those sweeps are skipped; ContactCollider is None, and ContactTimeSeconds is -1. The native system does not substitute Jolt hits or automatically bind a Hit handler: gameplay can call Stop NN Defense from its physical Hit event. Kinematic stopping uses authored PHAT and held-sword collision shapes, separately from enlarged training NN inputs; pose endpoint history remains current for switching back to Kinematic. Attack end/replacement, duration, explicit Stop and error/lifecycle exits still apply.

Get Agent State is a pure Blueprint getter returning the Prophecy Agent State enum: Locomotion, Parrying, Dodging, Attacking. Full and half attacks both report Attacking. Waiting for Armed leaves the actual current Locomotion/Attacking state unchanged. Reads existing manager state on demand; no per-frame state mirroring. This enum is also available as a Blueprint variable type.
