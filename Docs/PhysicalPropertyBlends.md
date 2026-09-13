# Timed magnetisation and physical feedback

Blueprint target: **Prophecy Agent**. These are native, non-latent commands: call once to start a transition; the output execution pin continues immediately. They work through the existing Jolt/Chaos property paths.

## Head recovery example

1. **Set Body Magnetization**: Bone Name `head`, Enabled **true**, Linear Strength Scale `0`, Angular Strength Scale `0`.
2. **Blend Body Magnetization**: Bone Name `head`, Linear Strength Scale `1`, Angular Strength Scale `1`, Duration Seconds `1`.

This starts immediately and restores the body's strength smoothly over one **game second**. Both scales are independently selectable. The curve is smoothstep: zero slope at the start and finish, no overshoot. A disabled body's effective starting strength is zero; the blend enables its per-body magnetisation. Global magnetisation enable/scales, gravity cancellation and simulation membership are preserved.

Use **Blend Body Magnetization Below** for an entire limb, with Parent Bone and Include Parent matching the existing setters. Each body starts from its own current strengths. `root` with Include Parent selects all PHAT bodies below it. Use **Cancel Body Magnetization Blend** to stop at the current value; Bone Name `None` cancels all magnetisation blends on that agent.

## Feedback

**Blend Physical Feedback Tolerance** and **Blend Physical Feedback Tolerance Below** interpolate the existing Linear Tolerance Cm and Angular Tolerance Degrees. For example: set head tolerances to `0 cm / 0°`, then blend to `3 cm / 5°` over `1` second.

These are deadband tolerances, **not a normalized feedback weight**. Zero tolerance allows full physical feedback; increasing the tolerance admits more deviation before feedback changes the recurrent pose. The supported NN feedback bones are unchanged: lowerarms are reconstructed, not direct feedback channels.

**Cancel Physical Feedback Tolerance Blend** holds the current values. Bone Name `None` cancels all feedback blends on the agent.

## Interruption and timing

- A new request replaces the same bone/channel's previous blend, starting from its currently applied values. It preserves value continuity; it starts a fresh ease curve, not a velocity-matched spline.
- Existing immediate Set nodes cancel the affected blends. Single-bone, Below and All variants follow their existing selection rules. Do not call a setter every Tick while expecting a blend to continue.
- Magnetisation and feedback transitions are independent and may run simultaneously, with different durations.
- Duration <= 0 applies the destination immediately. Finite negative destinations clamp to zero; invalid bone or nonfinite input returns failure without scheduling work.
- Time follows the world simulation clock, including the project's fixed-clock slow motion and world/agent time dilation. Pause freezes progression. Disabling the agent's actor Tick does not stop its transition.
- Ending play/destruction removes the agent's transitions. Runtime blends are not saved into assets or resumed across Play sessions.
- Use these APIs and the existing Set nodes to override transitions; direct edits to the exposed settings maps do not notify the scheduler.

## Cost

One world pre-actor callback updates only agents with active blends, before NN/physics consumers. The callback is unregistered when the last blend completes or is cancelled. No Timeline components, per-agent timers, additional actor ticks, or polling of idle agents are created.

PHAT/hierarchy selection and transition allocation happen when commands are issued. The steady update iterates compact active arrays, updates the selected settings, and uses a cached owning NN manager for feedback. Half Sim updates its existing body drive settings. Weak actor references and world teardown cleanup prevent transitions from retaining destroyed agents. `ProphecyPhysicalBlends` is the Unreal Insights CPU scope.

Validation (2026-09-12): normal Development Editor build installed after the user saved their Blueprint. `Prophecy.Agent.PhysicalBlends.RuntimeAndBatch` passed: timing/easing, independent channels, retriggering, immediate/below/all cancellation, PHAT/feedback selection, pause/dilation, destruction, teardown, and 100 agents with 200 active transitions. The isolated updater averaged **0.003525 ms** over 600 updates for 100 agents / 200 head channels. That microbenchmark excludes request-time setup, NN-manager propagation, NN inference, physics and Half Sim drive work; it is not a total frame-time claim.

The normal editor then ran the user's current `testNN` scene: all six nodes were reflected, and the active Jolt player `BP_ProphecyManualPoseAgent_C_1` smoothly restored head magnetisation from 0 to 1 and feedback tolerances from 0/0 to 3 cm/5 degrees in one game second. Every sampled value matched the smoothstep curve within floating-point tolerance, with exact final destinations. PIE ended afterward; scene/Blueprint assets were not edited by verification. Evidence: `Saved/Diagnostics/PhysicalBlends/Build.log`, `Tests.log`, `Live.json`, and `VerifyLive.py`.
