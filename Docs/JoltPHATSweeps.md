# Experimental per-agent PHAT sweeps

UPDATE: sweeps are automatically active during attacks AND active defense checkpoint
control (parry or dodge). Attacks include pre-Armed preparation. A defender waiting
for the attacker's Armed output stays in free motion and does not enable sweeps.
Defense enables them when its checkpoint takes control and releases them on
end/cancel/interruption/return to locomotion. With no override, both attack and defense
use Strength 1 / 64 iterations. Locomotion alone does not enable them.

`Set Jolt PHAT Sweeps`: Agent, Enabled (false), Strength (1), Max Iterations (64).
This configures permission/tuning for attacks and defense; Enabled=false explicitly opts out.
Enabled=true while idle saves settings but does not run sweeps. The same tuning is
retained across attacks and defenses. `Get Jolt PHAT Sweeps` returns EFFECTIVE Enabled plus saved
strength/iteration values, so Enabled is false outside those states. Valid strength is 0–1;
iterations 1–128. Invalid input returns false without changing the setting.
Disabled or strength zero removes the active request. Call on BeginPlay/state changes;
there is no need to repeat it on Tick. Settings can precede native rig creation.

The setter's white execution pin must be wired for it to change configuration; connecting
only Agent does not call it. Default automatic activation still works without the setter.

For a first comparison, use strength 1 and 64 iterations (automatic during attack/defense).
Leave global collision substeps at their ordinary setting to evaluate this separately.
Iterations bound conservative-advancement query work; they are NOT physics substeps.
No Blueprint wiring, global physics settings, or authored assets are changed.
Event-only hooks in NotifySwordAttackState and the shared committed DefenseChanged
lifecycle update independent attack/defense activation flags. Finishing one cannot
disable sweeps still owned by the other. The defense hook runs independently of whether
limb overrides exist. No state polling or physics work is performed for dormant configurations.

The selected bodies are the agent's registered PhysicalMesh PHAT rig. Queries use
the actual native shapes (including a welded sword), without enlarged colliders.
Potential contacts against other registered bodies are checked along both bodies'
predicted COM translation and world angular velocity. Object responses, PHAT groups,
pair exclusions and welded sword leaf filtering remain in effect. Pairs selected by
both agents are processed once, with the maximum strength/iteration setting.

After the velocity servo has updated ALL bodies, a converged future contact applies
an equal/opposite normal impulse weighted by dynamic mass and angular inertia. It
allows travel up to the predicted contact, rather than zeroing all motion. Bodies
are not teleported. Sleeping dynamic targets are activated before the impulse. The
actual applied impulse goes through the existing PhysicalMesh hit bridge if enabled;
its reported contact point is the predicted point within this substep. Ordinary
solver contacts can also report hits, as already happens for other multi-contact paths.

Already touching/overlapping pairs remain the normal solver's responsibility. An
unconverged sweep does nothing. This is an experimental predictive response, NOT a
replacement for the simultaneous contact/joint solver: later forces/joint solving can
change the prediction and penetration is still possible. No friction or restitution
is added by this supplementary pass. It does not turn on Jolt LinearCast CCD.

Disabled cost consists of empty-registry guards; no shape queries, body enumeration,
history capture or allocations. Enabled mode enumerates registered body IDs once per
frame and rejects body pairs with filters and relative-motion bounds before narrow
queries. Cost depends on enabled bodies and nearby candidates; no performance claim
or benchmark is made. Further broadphase optimization can be evaluated after visual
acceptance. It is not intended to be enabled globally by default.

Implementation lives in a separate Blueprint library and sparse native packets;
no existing world subsystem reflection or native allocation layouts were changed.
The sweep call is explicitly ordered after the velocity servo; a separate Jolt
step listener would allow a race because listeners may execute in parallel.

Focused test: `Prophecy.Jolt.ContactShapes.SelectiveSweeps` checks disabled behavior,
zero strength, collision rejection, fast translation, momentum transfer, and pure
rotation. Extensive scene testing is left to the user.
