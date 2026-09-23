# Upper-body attack-exit inertia

`Set Attack Upper Body Inertia` configures an agent's recovery. Call it once
before attacks, or in **Attack Ended** before the next locomotion evaluation.
It is available in the base agent's Blueprint library and usable by the pose
agent. **It has not been wired into the user's Blueprint.** The experiments
enabled it explicitly on transient PIE agents; no scene or graph settings were
saved.

| Pin | Default | Meaning |
|---|---:|---|
| Enabled | true | Enable this opt-in recovery configuration. |
| Response Time Seconds | 0.25 | Spring softness/time scale. Larger carries the outgoing motion farther and settles more gently. This is a response coefficient, not the lifetime of the recovery. |
| Hold Duration Seconds | 0 | How long inertia has full ownership before the blend begins. |
| Blend To Normal Duration Seconds | 0.5 | Smoothly fade inertia back to the ordinary NN/tempering controls. |
| Momentum Scale | 1 | Multiply the outgoing angular velocity; 1 preserves it, 0 starts with no inherited angular velocity. |

Hold/blend durations count **60 unpaused game ticks per authored second**,
unaffected by FPS or agent time dilation. The angular spring integrates each
complete NN pose sample interval, rather than mistaking the first ownership
tick for an entire future pose. Response0 or Hold+Blend0 bypasses/cancels the
feature. Momentum0 still leaves a spring response; use Enabled=false to bypass.

The core is spine_01 through head plus both clavicles. It retains outgoing
world-space angular velocity, applies critically damped rotation following,
keeps FK attachments and carries the arms with their clavicles. Corrected local
rotations are written into accepted upper state for recurrence and publication;
root, pelvis and legs are not authored by this feature. Existing hand controls
still run after the core. No attack-family gates or checkpoint changes.

The first interpolation retains the actual outgoing world-space upper endpoint,
including across root recentering. Reconstructing it from rotation-only NN state
would lose the attack's slightly different spine offsets and move the head before
interpolation starts. Its cache survives repeated publication of the same sample
and retires on the following accepted sample.

New attack/parry/dodge and reset cancel the motion. Reset restores captured
configuration, not an old running spring. Dodge also now cancels hand recovery
and slash-neutral return, matching parry. An attack-end callback that immediately
starts another special cannot accidentally begin a recovery over it.

No separate tick or extra model inference is introduced. Once the finite return
finishes, its motion, clock and handoff cache are removed and the manager skips
its pose work. Configured values remain for later attacks. Normal paths retain
only inactive checks; see [the wider audit](BlendIdleAudit.md).

## Diagnosis and evidence

The unchanged current scene repeatedly exits full slashR with FK-core follow0.1
and a0.5-second return to normal. That first-order pose following preserves pose
continuity but does not retain outgoing velocity. The head slowed from about
155–176 to27–31 cm per authored second within two frames. A separate re-decoded
spine-offset handoff caused another approximately37.85cm/s velocity change.

Six-exit600-frame captures were collected; the table uses the five exits with
40 following frames available. Values are changes between consecutive displayed
head velocity vectors, using60Hz authored units. Actual PhysicalMesh readback
matches these measurements in this scene.

| Measurement (cm/authored second) | Original | Default response0.25 | Softer response0.4 |
|---|---:|---:|---:|
| Initial velocity-vector change |181.12–203.24|59.27–64.01|51.03–53.70|
| Separate next-frame change |37.84–37.87|0.001–0.003|0.001–0.003|
| Maximum near return retirement |8.69–10.24|15.06–15.45|18.93–19.01|

The default is a conservative response;0.4 is softer at the handoff but carries
more motion into the later recovery. The endpoint is bounded and much smaller
than the original cusp, not mathematically zero acceleration. These are current
scene measurements, not a guarantee for every possible pose or momentum value.

Evidence under `Saved/Diagnostics`:
- `CalfRoll-20260923-150214.json`: unchanged all-bone baseline.
- `UpperInertiaEnabled-20260923-152516.json`: final default-enabled scene.
- `UpperInertiaEnabled-20260923-152548.json`: final response0.4 comparison.
- `UpperInertiaComparison.json`, `MeasureHeadHandoff.py`, `SummarizeUpperInertia.py`.
- `VerifyUpperBodyInertia.py`:32 focused tests, all passed13:24:53UTC.

Live Coding patch15 compiled successfully (150.76s). Blueprint compiled status3,
zero stale native/pin types, wiring preserved. Earlier patch13 validation repaired
46 archived library defaults without changing user pins or connections; final
validation needed no repairs. No editor restart or explicit asset save; owned
PIE captures were stopped. Include live patches in the next authorized normal
editor build before reopening.

Subsequent all-special integration: the same opt-in configuration now also begins
from the two actual outgoing parry/dodge endpoints. Defense root recentering is
captured before callbacks, and a new special cancels the old inertia. The node's
existing name/pins remain for compatibility. See [SpecialRecovery](SpecialRecovery.md)
for event wiring and defense validation; it remains unwired unless configured.
