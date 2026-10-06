# Feet-threshold events

**Set Realistic Mode** enables a threshold monitor on one agent. It defaults to
disabled, with **Foot Threshold Cm = 10**. It only reports state changes; it never
changes magnetization, forces, gravity, damping, snapshots or NN inputs.

The measured height is the lower of `foot_l` and `foot_r` bone origins, minus the
capsule's lowest point in world Z. Physical body positions are used when
available; otherwise the displayed skeletal pose is used. The capsule bottom
calculation includes capsule scale and tilt. This is not a floor trace or a
measurement of the bottom of the foot collider.

- **Event Start Realistic** fires once when the measured height is strictly above
  the threshold: both feet must be above it.
- **Event End Realistic** fires once when height reaches or goes below it, when
  the monitor is disabled, when feet become unavailable, or when the agent resets.
- **Is Realistic Mode Active** reads the current crossing state.

Enabling or changing the threshold evaluates immediately; subsequent evaluations
run in the agent's existing Tick before native target publication. There is no
extra timer, component or inference. Disabled agents skip all foot reads. The
state is committed before the Blueprint event runs, so a handler can disable or
reconfigure the monitor. Negative/nonfinite thresholds are rejected unchanged.
Reset ends the active crossing but retains enable/threshold settings. There is no
hidden hysteresis or delay; use your Blueprint handlers to choose transitions.
As with the other actor Tick updates, explicitly disabling the agent's Tick also
stops this monitor; normal physical agents and the existing gameplay Blueprint tick.

For per-body hit responses, use **Set Body Magnetization Mode**, **Set Magnetization
Mode Below**, or their snapshot-return variants. Those controls are independent
of this monitor. Saving slot1 also saves mixed modes; special entry continues to
restore slot1 as before.

## Validation, October 6

Normal Development Editor DLL rebuilt successfully; TestNN reopened with no
stale Blueprint pins (status3, native_properties0, pin_types0). All26 focused
native tests passed, covering bone-mode selection, snapshot timing/cancellation,
uniform compaction, slot1/reset, threshold geometry, existing servos and multi-rig
isolation. No performance benchmark or whole-project test-suite claim.

A900-tick owned PIE run sampled540 actor records across3 physical agents, all
finite with maximum tracked pelvis-to-limb span100.479cm. Mixed values remained
on the player. The current NPC Blueprint repeatedly sets the global mode to.25,
so that deliberately overwrites per-body changes on those NPCs. An isolated,
ticking native probe verified the uninterrupted.5s hold/.5s return: hand.7 at
tick30,.35 at45,0 at60, with the other hand unchanged. Python event overrides
received exactly Start/End/Start/End, without duplicate events on unchanged state.
Physical-foot threshold checks did not change mode or linear strength.

The diagnostic probe required correcting its Python spawning API, using the
skeletal fallback on its nonphysical fixture, and enabling that fixture's Tick;
those were test-fixture issues, not production-code changes. The existing scene
also logs an empty GetAttackBones array access from Blueprint, outside this change.
All owned Play sessions ended. TestNN remains open with no dirty packages, no
asset edits and original scene settings. Receipts:
`Saved/Diagnostics/RealisticMag20261006/{validation,reflection,live,probe,final-state}.json`.
