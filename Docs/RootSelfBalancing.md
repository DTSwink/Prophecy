# Root self balancing

Call **Set Root Self Balancing** with your agent (`Self`), once to enable or whenever you want to retune it. It is disabled until you enable it. You do not need to call it on Tick.

| Input | Meaning | Default |
|---|---|---|
| Enabled | Enable automatic balancing for this agent. False removes its balance state. | Explicit choice |
| Speed Threshold Cm Per Second | Balance only when current horizontal root speed is at or below this value. | 60 |
| Move Input Threshold | Maximum requested movement amplitude, from 0 to 1, before Speed Scale. Input above this restores ordinary movement at the next 30 Hz policy update, even when the root is stationary. Set 0 to disengage on any nonzero move input. | 0.05 |
| Spring Frequency Hz | Higher values pull toward the feet faster. Must be positive. | 2 |
| Damping Ratio | 1 is critical damping in the spring equation; below 1 permits oscillation, above 1 gives a slower return. Implicit integration adds numerical damping. | 1 |
| Max Balance Speed Cm Per Second | Maximum corrective speed. Also capped by Speed Threshold so balancing cannot repeatedly disengage itself by accelerating past its own gate. | 30 |
| Tolerance Cm | Horizontal radius around the midpoint in which no spring, spring damping, or balance speed-cap correction acts. Outside, pull toward the nearest edge of this zone. Zero preserves the original point spring. | 0 |

Tolerance is radial: `5` means a 5 cm circle around the feet midpoint, not 5 cm independently on each axis. Inside it, a stationary root stays still; existing velocity is not forcibly stopped and can carry the root through the zone. The speed/input eligibility gates, yaw, collision and root-window smoothing still apply. Negative or nonfinite tolerance is rejected without changing the previous settings.

The target is the arithmetic midpoint of `foot_l` and `foot_r`, projected onto the current root's horizontal plane. It reads actual body origins for simulated feet (Jolt or Chaos), and the visible mesh's foot positions for kinematic feet. Both feet count equally regardless of pinning. It does not shift root height or rotate the root.

## Kick recovery exception

**Set Kick Self Balancing Exception Durations** takes Agent, **Hold Duration Seconds**
(node default0) and **Fade Duration Seconds** (node default1). Call it before the
kick, for example during BeginPlay. It is opt-in per agent; without the node the
existing rule remains. Both0 disables the setting and cancels any active return.
Negative/nonfinite inputs are rejected. Positive edits configure future kicks.

When `kickL` or `kickR` finishes/cancels back to locomotion, its root-return target
is directly below the current pelvis. The balancing target then follows the live
pelvis during Hold, before smoothstep blending toward the live feet midpoint
during Fade. The pelvis uses the simulated physical body when applicable, otherwise
the displayed mesh bone. Both targets stay on the root's current Z plane. This
includes full/half kicks; replacing an attack without returning to locomotion does
not start a kick recovery. The existing explicit pelvis-return mode still places
the root below the pelvis as before.

**1 duration second =60 unpaused game-world ticks**, independent of FPS or time
dilation. Hold0/Fade1 starts below the pelvis then returns over60 ticks.
Hold1/Fade0 holds for60 ticks and then immediately restores the normal target.
Time starts at the kick handoff and keeps progressing even if balancing is gated
off; completion stops the clock even before the next eligible policy sample.

The spring enable/input/speed/magic gates are unchanged. The exception also chooses
the kick handoff point when the spring itself is disabled. A new valid attack,
active parry/dodge or reset cancels the active exception; configuration remains for
future kicks. Root movement/window/cube handoff and camera inverse-snap compensation
continue through their existing paths. No extra inference, body movement or height
correction is introduced.

Only active recovery uses a bounded clock. After completion there are no continuing
fade ticks or pelvis reads. During a full pelvis hold there is no need to read feet;
during fading, the selected target is sampled once per eligible policy step and
shared by the actual root and future window. `Get Root Self Balancing State` reports
this effective target in its existing **Flat Feet Midpoint** output while the
exception is active; its pin name is retained for Blueprint compatibility.

Loaded through Live Coding2026-09-21 at13:11:42UTC. Reflected defaults verified;
`Prophecy.Root.KickSelfBalancingException` and `Prophecy.Blends.SixtyTickClock`
passed13:12:17UTC, covering kick activation, lifecycle, schedule boundaries and
60-tick timing with30/60/120FPS deltas/time dilation. No gameplay rollout or asset
rewiring/save; include the live patch in the next normal build before fresh launch.

While eligible, the spring replaces the planar locomotion motor, so ordinary stopping friction does not cancel small balancing corrections. It starts from current root velocity. Disabling it, exceeding the speed gate, or requesting movement restores the ordinary motor without teleporting or zeroing velocity. Foot positions refresh once per real policy step; the same target and spring are used by all eight predicted roots and the actual step. The underlying equation is `acceleration = omega² × (target − root) − 2 × dampingRatio × omega × velocity`, with `omega = 2π × frequency`. The implicit solve remains stable for stiff settings without extra physics substeps.

Full attacks retain their authored root movement, so balancing pauses during them. Half attacks allow it. Existing capsule collision and root-window smoothing still apply; setting all root-window smoothing factors to zero can intentionally prevent movement. No obstacle or support-polygon solver is added: blocked roots cannot necessarily reach the midpoint.

**Get Root Self Balancing State** exposes Enabled, Active, and Flat Feet Midpoint from the latest policy step. It does not sample meshes. Active means the spring is selected, including when already balanced with zero correction; it does not guarantee that collision/smoothing permits movement.

Disabled agents have no balance-state allocation, bone reads, extra inference, timers, or components. Only enabled, eligible agents sample their two feet. Invalid settings return false and preserve the previous configuration. Runtime settings are local to the agent and removed at world teardown.

The spring runs at each of the **eight future root samples**, not just root1. Root-window smoothing is applied afterward, so a low/zero smoothing factor can reduce/freeze the displayed spring trajectory. The present sample remains the prediction anchor and the past sample remains history; actual movement advances to encoded root1. This is a predicted trajectory over time, not an equal translation of every root sample.

When speed/input/attack eligibility rejects balancing, no foot reads or spring solve run. Input is checked first and speed uses a squared comparison (no square root). Preparation returns the selected spring directly, avoiding a second state lookup before prediction. Small enable/state/gate checks remain necessary to detect activation; this is not a claim of literally zero added CPU instructions.

Native regression: `Tools/NN/TestProphecyRootBalance.cpp` checks convergence at 30/60/120 Hz, speed/input gates, high-stiffness bounds, predicted/actual agreement, and yaw preservation. `TestProphecyRootMomentum.cpp` also retains its existing normal-movement/impulse checks.
