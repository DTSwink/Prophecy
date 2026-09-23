# Hand recovery and tempering

Three nodes, independent left/right hands, one profile shared by all attacks (including kicks):

- **Set Locomotion Hand Tempering**: Enabled plus Left Hand XY/Z/Rotation, then Right Hand XY/Z/Rotation. Defaults1. Zero carries the preceding accepted hand pose with `spine_05`; intermediate values follow the next prediction per NN step. XY, Z and rotation use that bone's local axes. Reach correction repairs shoulder/elbow/hand attachment while preserving the requested wrist rotation. Impossible endpoints are projected into reachable arm space.
- **Blend Locomotion Hand Tempering To Normal**: independent Left Hand Hold/Blend Duration Seconds and Right Hand Hold/Blend Duration Seconds. Hold defaults0, blend defaults1. Smoothstep returns all three values for each hand to1. Zero blend snaps after its hold. Repeating Blend starts from current values; Set cancels prior returns.
- **Set Attack To Locomotion Hand Blend**: Left Hand Source/Hold/Blend, then Right Hand Source/Hold/Blend. Source is Normal, Walk or Run. The node defaults to Run/0/1; before it is configured, no hand recovery is active. Normal or zero blend duration disables that hand, matching leg recovery. Positive configuration is selected at the next attack end; On Attack Ended can configure the current handoff before its first locomotion prediction.

Configure Set nodes in BeginPlay, and call Blend To Normal in On Attack Ended to return tempering. End-of-attack selection restores the configured hand tempering profile each time. There are no kick variants. All durations use60 unpaused game ticks per authored second and do not accelerate with agent time dilatation. Active full/half attacks, parries and dodges bypass hand tempering and cancel hand source recovery.

## Source meaning and integration

There is one upper-body NN checkpoint. Walk/Run here means evaluating that same upper NN with the corresponding lower policy's next pelvis and foot prediction. The two source branches share the accepted current/previous history, root trajectory, equipment and gaze. They do not secretly advance separate recurrent histories. Each source lower prediction uses the ordinary pin/floor correction and the same root rebase as actual locomotion.

Only the selected arm's15 upper-state values are mixed back into the ordinary upper output (position, wrist rotation, shoulder frame); torso/core rotations and the other hand remain unchanged. Arm reconstruction resolves the mixed endpoint. Tempering follows that mix, then existing hand inertia runs if enabled. The accepted arm state feeds recurrence and publication together. Actual lower-body selection, pelvis, root movement and physical drive profiles are unchanged by the source selector. Normal means the normal upper prediction conditioned on the actual lower body, including existing regional leg recovery.

Only requested sources run, shared between both hands when they request the same source: at most two additional fixed-batch upper evaluations per active prediction, and a missing lower-policy evaluation if necessary. This is a real active cost. Once recovery expires, its source state is removed; no source buffer copies or extra inference remain. All-one/disabled tempering skips pose decoding/reconstruction; return clocks stop at their endpoint. No new actor tick or persistent callback is introduced; timing uses the existing blend clock.

Reset captures hand configuration and current values after delayed initialization, restores them, and cancels active hand blends/source state. Teardown clears all hand state. Existing Blueprint graphs are not rewired.

## Spine reference for hand tempering

Hand tempering now uses the previous/current decoded `spine_05` world transforms
instead of the root. At zero, the prior hand transform relative to the prior
spine is carried by the new spine, including translation, yaw, pitch and roll.
Intermediate XY/Z/rotation values interpolate in that same local frame; at1 the
original target is returned directly. References come from policy poses, not the
interpolated/rendered mesh. The existing arm solver carries its source chain in
that same spine frame. Publication also carries the retained forearm twist with
spine rotation before following the new decoded twist.

Only tempered hands use this reference; source-only Walk/Run recovery and the
separate hand-inertia feature retain their existing behavior. Existing node pins,
profile/reset storage, holds,60-tick blend timing and special-mode bypasses are
unchanged. No extra processing runs once tempering is normal/inactive. The
supported25-bone skeleton contains `spine_05`; unexpected skeletons missing it
fall back to the existing root frame.

Live Coding loaded2026-09-23 10:21:53UTC (287.93s build); four
`Prophecy.NN.HandRecovery` tests passed10:22:40UTC, including the new
`SpineReference` test for translated/tilted references, independent XY/Z/rotation,
all-one bypass and blend samples. The pose Blueprint compiled successfully with
zero stale types and preserved wiring. An owned360-frame PIE capture forced zero
hand tempering at runtime: across three agents' consecutive locomotion samples,
maximum wrist orientation change relative to spine was0.000022degrees while the
spine itself changed up to12.86degrees per sample. Reach projection can still
adjust hand position for arm attachment; this does not freeze an unreachable wrist.
Evidence: `Saved/Diagnostics/HandChain-20260923-122250.json` and its
`.spine-validation.json`. Diagnostic PIE ended; no scene/graph edits, asset saves
or restart. Include this live patch in the next authorized normal build.

## Arm continuity refinement — September23

### Follow-up: attack forearm roll diagnosis

User subsequently reported independent left forearm roll DURING the attack.
Fresh capture `Saved/Diagnostics/HandChain-20260923-115309.json` confirms it:
118 active-attack samples have left wrist-derived roll mismatch up to104.51deg
(median63.18deg). At that maximum the actual forearm agrees with the upper-arm
pole reconstruction within0.000046deg and aims at the hand within0.000046deg.
The right arm also has the mismatch (maximum172.23deg). Attack-start samples
can still carry the initial locomotion pose, so the pole rule is not exact for
every sample marked Attacking.

Cause: `FSlashNative::SolveLimb` chooses the forearm frame from the elbow-to-hand
axis and the upper arm's transformed pole, independently of the predicted wrist
rotation. `ForearmRotationFromHand` in locomotion instead carries wrist roll and
removes wrist swing to aim at the hand. The90-value upper state has no independent
forearm rotation. The training `training/ik/ik_core.py` decoder uses the same
upper-arm pole rule as the native attack path, so this is a contract difference,
not a newly introduced UE parity error. The recovery continuity patch smooths
the switch but does not change attack reconstruction.

### Shared forearm roll for all specials — implemented

User authorized wrist-driven roll for every special: attack (full and half),
parry and dodge. All now use the same `ForearmRotationFromHand` calculation as
locomotion, through the shared `SetForearmRollFromHand` UE-boundary helper.
It aims the forearm at the wrist while carrying wrist roll, removing only wrist
swing. Only the forearm quaternion changes: positions, scales, upper-arm and
wrist rotations remain untouched by this correction.

Attack applies it once per new accepted pose before caching VisibleWorldPose.
Rendering, Jolt targets and attacker-collider samples consumed by defense use
that cache, including half-attack mounting. Existing optional hand inertia still
uses the same wrist-derived convention after its endpoint correction. Parry and
dodge apply it to the decoded output before PHAT stopping checks and component
publication; dodge origin offsets do not affect orientation. Native policy
decoders, weights and reduced state encoding are unchanged. Forearm collider
orientation intentionally changes, which can affect contacts and subsequent
defense responses; this is not an entirely cosmetic or training-identical rollout.

No new node, persistent state, tick, blend clock or inference pass. Work occurs
only for newly accepted special poses; ordinary locomotion stays on its existing
path. Intermediate presentation retains the existing interpolation method.

Live Coding patch5 loaded2026-09-23 10:05:46UTC,92.25s build, no object changes.
All nine `Prophecy.NN.PhysicalTargets` tests passed10:06:18UTC, including new UE
boundary and defense coordinate/mapping checks, wrist-roll/aim, untouched other
transforms, idempotence, existing hand/leg clamps and rigid interpolation.
Pose BP compiled status3, zero stale native properties/pins, wiring preserved.

Owned360-frame PIE capture `Saved/Diagnostics/HandChain-20260923-120633.json`
exercised full attacks, half attack, parry and dodge by temporary runtime calls.
122 attack,32 parry and20 dodge samples show both forearms agreeing with the
wrist-derived target within0.000064degrees; assertions require below0.001degrees.
Evidence is alongside it in `.events.json` and `.roll-validation.json`.
Owned PIE stopped afterward; no Blueprint/map edits, asset saves or restart.
Include the live patch in the next authorized normal editor build.

The first implementation resolved a tempered wrist using the new predicted
shoulder as its entire source frame, and transported that frame through wrist
rotation. It also forced the forearm to its reference length during recovery.
These choices discarded the accepted elbow bend and could move the elbow when
only wrist roll changed. The reduced upper state also omits forearm twist;
re-decoding an outgoing attack as locomotion discarded that rotation.

Baseline capture `Saved/Diagnostics/HandChain-20260923-113007.json` records360
frames and three attack returns in the current setup. Left forearm orientation
steps at the exits were103.75/103.53/103.31degrees; right steps were73.00/73.98/
73.85degrees. These are displayed target rotations, not physical wobble.

The recovery solve now uses the rebased accepted arm state carried into
the next root frame. It blends that source toward the candidate, then transports
the complete elbow hinge to the requested wrist, without carrying it through
wrist roll. The least-following XY/Z/rotation control governs hinge following;
an active Walk/Run return additionally uses its recovery alpha. Source forearm
length follows continuously instead of switching to reference length and back;
authored presentation/physical clamps still own their respective limits. Wrist
orientation remains exactly the requested tempered orientation.

During active hand recovery/rotation tempering, publication retains the preceding
real forearm rotation, swings it onto the new forearm axis, then follows the
decoder's twist. Repeated publication at the same policy time uses the same
preceding sample, matching calf continuity. No new timeline, retained state,
attack-family gate or inference pass is introduced. Fully normal/inactive hands
bypass this work; specials continue to use their original arm path.

Final Live Coding patch4 loaded09:40:33UTC (99.22s final build, no reflected
object changes). Capture `Saved/Diagnostics/HandChain-20260923-114041.json`
repeats360frames/three returns with no scene/Blueprint edits. Across the captured
recovery intervals, maximum displayed forearm steps fell from103.75/73.98degrees
(left/right) to7.49/13.48. Shoulder-relative elbow steps fell from1.78/3.89cm to
0.91/2.44cm. Left upper-arm maximum fell5.86→1.95degrees; right maximum changed
8.80→9.08degrees later in recovery, rather than a new entry snap. Motion is not
bit-identical: the accepted arm feeds subsequent NN history. These captures
demonstrate improvement in this setup, not proof against every possible pose.

The intermediate patch's stale-carrier source increased initial elbow steps;
that version is superseded. Positions/shoulders now come from rebased accepted
state, while missing forearm twist alone comes from real publication. Existing
hand-inertia, lower-body, checkpoint and root-snap implementations are unchanged.

All three `Prophecy.NN.HandRecovery` tests pass, including new ChainContinuity
coverage for coherent-pose identity, wrist-roll/elbow isolation, reach and wrist
rotation, continuous source-length return to normal, finite transforms, forearm
aim preservation and root-frame equivariance. Pose Blueprint compiles status3,
zero stale native properties/pins and preserved wiring. Only owned diagnostic
Play sessions were stopped; Unreal remains open. No asset save or restart.

Live Coding build succeeded1088.04s and loaded2026-09-23 02:11:57UTC (one new library,62 existing classes unchanged). All three reflected nodes were called successfully; existing pose Blueprint compiled status3 with zero stale native properties/pin types and preserved wiring. Both `Prophecy.NN.HandRecovery` tests passed02:12:20UTC:60-tick timing at30/60/120 supplied FPS, independent hands and leg/hand lifecycle, reset/cancellation/retirement, root-local XY/Z/rotation and reach, source tensor fields and isolation of unselected arm/core output. No gameplay rollout, asset save, graph rewiring or restart. These source/input tests do not establish visual quality of a live attack sequence. Include live changes in the next normal editor build before reopening. Evidence: `Saved/Diagnostics/HandRecoveryValidation.json` and editor log.
