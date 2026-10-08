# Independent root magic velocities

## Third channel: delay and spread

**Set Root Magic Velocity 3** and **Set Root Magic Ang Velocity 3** add a third
independent channel. Their getters report channel 3's current stored value.

- **Delay** defaults to 0 seconds, counted at 60 unpaused game ticks per second.
- **Spread Ticks** defaults to 1. With no delay, the first fraction is immediate;
  with delay, it is delivered when that delay expires. Remaining fractions arrive
  on consecutive ticks. A positive fractional delay rounds up to a tick.
- **Add to Current** defaults to false: ramp to the requested channel-3 velocity.
  When true, add that total velocity to channel 3's value at delay expiry.
- **Braking Deceleration** on the linear node defaults to **1800 cm/s²**, the idle
  locomotion braking rate. Each unpaused game tick removes30cm/s from the velocity's
  magnitude, preserving direction and clamping to zero. This brakes only channel3,
  independent of move input, channels1/2 and angular velocity. It is a constant
  magnitude reduction, not exponential damping. Actual root motion still has its
  existing smoothing/collision pipeline; identical trajectories are not promised.
- A new call replaces the pending request for that component of channel 3. Linear
  and angular schedules are independent. Invalid arguments leave pending work intact.
- **0 braking** preserves the original constant-velocity behavior. It creates no
  braking state or callback; completed delay/spread work retires exactly as before.
  Positive braking starts at first delivery and continues after the spread until
  zero; its state/callback then retire automatically. New calls replace that linear
  channel's braking settings too. During a new delay, the stored velocity is held.
- Set zero with Delay0/Spread1/Add=false to stop immediately and cancel the linear
  request/braking. Angular channel3 retains the original behavior without braking.
- Reset, removal and full-attack entry clear all three channels and cancel channel-3
  queued work. World cleanup drops remaining queued work. Full attacks/defense retain
  the existing application rules; a spread's timer itself uses unpaused world ticks.

Example from zero: `(400,0,0)`, Spread3, Delay.03, Braking1800 gives no change on
tick1, then approximately103.33,206.67,310cm/s on ticks2,3,4; tick5 is280cm/s and
braking continues to zero. Each spread installment adds only its fraction, so it
cannot restore velocity removed on previous ticks. With Braking0 the values are
133.33,266.67,400 instead, and400 persists. With zero delay, the immediate setter
delivery is not braked retroactively; braking begins on the following game tick.

All three channels feed the existing cached sum. Prediction/integration still use
the same single lookup. Extra source storage exists only for agents using channel3;
the timer callback exists only while a delay/spread or positive braking is active. The original paired
storage layout is retained for safe Live Coding. Existing channel1/2 writes cannot
overwrite channel3.

## Original two channels

The original nodes control set 1. The second independent set uses:

- **Set Root Magic Velocity 2**
- **Set Root Magic Ang Velocity 2**
- **Get Root Magic Velocity 2**
- **Get Root Magic Ang Velocity 2**

Both setters retain **Add to Current** (default false). It adds to the selected set only. Each getter reports its own stored set, even while attacks pause application. Setting zero clears only that component of that set; it does not clear the other set or its angular/linear counterpart. Defaults are zero.

Linear velocity is world XYZ in cm/s. Angular velocity is world degrees/s, Z yaw only, as before. The effective additional velocity is set 1 + set 2. Both affect the actual root and full future window through the same existing integration. Full attacks/NN defense pause both; half attacks retain locomotion behavior. Existing self-balancing magic thresholds evaluate the combined additional velocity.

The sum is cached when a setter runs. Root prediction, actual integration, root velocity readback and balancing still consume one existing lookup, with no per-step second lookup or summation. Extra source storage exists only while set 2 is nonzero. Opposing sets can cancel effective motion while retaining their separately readable/editable values. Nonfinite components or sums are rejected without changing either set.

Implementation preserves the existing native velocity-map element layout and uses a separate new map for paired sources, avoiding retained-allocation resizing during Live Coding.
