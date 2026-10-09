# Live control during parry and dodge

October8: [pair-specific combat rules](DefenseCombatRules.md) suppress attacker-body contacts against a dodger and give a parrier's Blueprint trunk list plus both arms zero direct contact reaction against its attacker. **Set Defense Half Attack Horizontal Velocity** optionally removes horizontal pelvis translation from half-attack perception (default off, synthetic spear excluded). Existing exit settings remain unchanged.

October5 stop-rule update: **Set Defense Frames After Hit** controls both modes per defender (default3 at30Hz,0 for immediate Hit exit). Attack end/cancellation always ends associated defenses immediately. Automatic collision stopping and its PHAT sweeps were removed for both modes. Explicit Stop/maximum duration still apply; old physical-contact ownership notes below are historical.

Both responses still wait for the incoming attack's learned Armed output. The defender keeps normal locomotion/attack ownership until then.

During active defense, the existing locomotion input, facing, mover, root impulses, window smoothing, balancing, root speed limits, and both sets of magic velocities remain live. Use the same control nodes. The continuous root-window getter also works during Dodge. Root placement and pelvis bounds rebase the private defense history coherently; capsule collision no longer cancels Dodge.

Parry retains the normal locomotion lower branch. Its upper defense conditioning now receives the newly resolved movement command every step instead of the episode's initial command.

Dodge retains its trained frozen lower networks and private recurrent state. Its lower inputs receive the full live eight-sample mover window, converted into the native heading/mesh-carrier frame and checkpoint normalization. Its upper conditioning receives the resolved next-root command. The trained root displacement and yaw correction are added once to that planned root. They do not rotate world-space magic velocity or become extra mover momentum. Only learned corrections consume Dodge's movement banks. The next recurrent pose is rebased into the combined root. Walk/run selection follows the live input; the Dodge lower branch retains its own checkpoint projection, rather than substituting the normal locomotion networks.

The original fixed-command reference path remains the default of the standalone native Prepare/CompleteDodge helpers for parity fixtures. The live manager explicitly supplies the planned root. New steering intentionally changes the original fixed-command rollout.

## Independent clamps

`ProphecyNNDefenseLibrary` exposes four leg nodes, each with Agent, Enabled and Leeway Cm:

- Set Parry Foot Clamp / Set Dodge Foot Clamp
- Set Parry Calf Clamp / Set Dodge Calf Clamp

Values are independent per agent and response. Zero leeway means an exact clamp; 1 means one centimetre. Negative/nonfinite values are rejected. Foot limits total leg reach; calf constrains segment length in both directions. Before an override, Parry uses locomotion leg settings and Dodge has no optional leg clamps. These controls do not disable Dodge's trained leg IK or foot-floor correction.

Both hands now remain attached at fixed anatomical forearm length in every mode. The former parry/dodge hand and forearm leeway nodes were removed September30, including their easing and profile entries. [Fixed arm attachment](FixedArmAttachments.md).

## Attack target and response readback

**Get NN Defense Relative Target** returns the incoming attack's aim point captured
in the defender's unscaled capsule-root space when Parry/Dodge actually activates.
`World Target` carries that point with the current root translation and rotation;
`Root Local Target` is the fixed local offset in centimetres. A point on the head
stays on the head if the head's transform relative to the root stays unchanged.
This is not bone tracking: head movement relative to the root, or later attacker
retargeting, does not change the captured point. The getter does not alter the
target used by the NN. Before Armed, after defense ends, or for an invalid agent,
it returns false and zero vectors. New defense activation captures a fresh point.
It performs one cached lookup and one transform per call, without ticking, bone
sampling, actor scans or additional inference. Stop/reset/EndPlay clear the cache.

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

## Optional upper-body returns (October 8, 2026)

Configure these before defense ends; each applies to the defender, independently of attack settings.

- **Set Dodge Upper Body Inertia** restores the old core/arm spring return only after Dodge. This is the existing `SetAttackUpperBodyInertia` native function with a corrected display name, preserving existing Blueprint references and pins. Response, hold, blend, momentum, arm reference space, core/arm alpha and arm timing overrides retain their meanings. It is off until configured. It never starts after attacks or Parry.
- **Set Parry FK Return** uses the same parent-local idle and curve implementation as the attack lab return, with independent Return Time, Inertia, Easing, Hold/Trim (X/Y), NN Takeover Coefficient, bone weights, inertia hold/decay, world-inertia flag and spine-angle time addition. It is off until configured. Enabling/disabling or changing Parry settings cannot change attack profiles or cancel an active attack return; disabling attack return cannot cancel a Parry return.

Both preserve the outgoing pose history, cache each accepted publication so repeated publishes cannot advance the spring/curve twice, and commit the resulting upper pose into the existing NN history. They do not change lower-body recovery, physical profiles, defense exit conditions or attack motion. A new special cancels either return immediately. Reset restores captured settings and clears active motion; disabling a node cancels its own active return. Timing uses the existing 60 Hz unpaused game-tick clock. No additional inference, tick registration or work on all bones when no return is active. The modifier debug report identifies Dodge inertia and Parry FK return separately.

## Separate Dodge lower-body tempering (October 8, 2026)

- **Set Dodge Locomotion Lower Body Tempering** stores a per-agent Dodge-exit profile: Enabled, feet XY/Z translation and rotation, pelvis XY/Z translation and rotation. Same follow semantics as the regular node; defaults are all 1 (no tempering). Configure before Dodge ends, or in **On NN Lower Special Ended**.
- **Blend Dodge Locomotion Lower Body Tempering To Normal** returns that selected profile to 1, with independent feet/pelvis duration and hold pins. Call after Set in the lower-special-ended event. Defaults: duration 1 second, hold 0. One second is 60 unpaused game ticks; this schedules the current return, not future exits.

The end dispatcher selects the profile before calling Blueprint. Regular/attack, kick and Dodge settings remain separate; other variants cannot overwrite a Dodge return, and Dodge nodes cannot overwrite an attack/kick return. Both sets of nodes may share the event without a Blueprint branch. Parry selects no tempering, even if the common event calls these nodes. The regular profile still applies in ordinary locomotion and after attacks, and existing kick fallback/independent-return behavior is retained. Previously both defenses inherited the regular profile; Dodge now needs its own configuration.

The existing pose calculation, blend curves, clocks and leg reconstruction are reused. Selection checks run only when configuring or dispatching an end event; there is no extra pose-tick lookup or inference. Reset clears selection and active clocks while retaining configured profiles, following the existing kick-profile lifecycle. This change does not alter separate policy blending or leg-reconstruction recovery nodes.
