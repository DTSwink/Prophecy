# Collision launch diagnosis — 2026-09-16

Production source, Blueprint, map and tuning unchanged. Three short disposable PIE captures of the user's current scene; each ended normally. The second and third runs change only transient PIE values for isolation. No reset node invoked. Reports: collision_launch_baseline.json, collision_launch_zero_spin.json, collision_launch_no_feedback.json. CollisionBlueprintGraph.txt records current in-memory Blueprint wiring.

## Result

The root stays at ground height. The NN's published pelvis target rises; the physical pelvis closely follows it. The triggering path is the Event Hit graph accumulating a persistent Magic Angular Velocity 2, reaching -6443.267797 degrees/second (17.898 revolutions/second, 214.776 degrees per 30 Hz NN interval).

For BP_ProphecyManualPoseAgent_C_1:

| Run | Maximum physical pelvis Z | Maximum presented target pelvis Z |
|---|---:|---:|
| Current Blueprint | 1725.74145 cm | 1727.638943 cm |
| Clear only magic angular velocity 2 after each frame | 93.00242 cm | 93.760903 cm |
| Force every feedback tolerance to 100000000 cm / 1000 degrees after each frame | 1725.23980 cm | 1727.638943 cm |

Baseline root Z remained approximately -0.49997 cm. Magic linear velocity Z stayed below 0.000008 cm/s. This is not upward root motion. At 2.0167 s the presented pelvis target was already173.16 cm, at5.0167 s785.51 cm, at10.0167 s1727.64 cm. Baseline and feedback-disabled presented pelvis maximum are identical; physics follows within a few cm.

Disabling feedback through the existing tolerance mechanism leaves the target failure intact, while removing the accumulated yaw term prevents it. This is an isolation result on the installed build, not a pre-patch binary comparison: it does not establish whether the old feedback masked the instability. The earlier chat conclusion excluding a connection to the change was premature.

## Exact source of vertical displacement

An additional fresh five-second PIE capture used the existing opt-in NN input trace. `replay_collision_raw.py` replays the 150 captured player inputs through the installed run and walk checkpoint weights outside Unreal. The run checkpoint's raw pelvis-Z residual accounts for every published pelvis-Z change, within 0.0000278 cm (float inference roundoff). At 1.55 seconds the raw NN adds 11.311446 cm. After two seconds it averages 6.820346 cm per 30 Hz step upward. Every next input pelvis Z equals the preceding published pelvis Z exactly: neither physical feedback nor root rebasing adds height between steps. This is recurrent NN target drift, followed by the physical pelvis. It does not by itself explain why the user did not see the behavior before the alignment change. Evidence: `collision_launch_nn_raw.json`, `collision_raw_replay.json`, `Saved/Diagnostics/SlashContacts/nn_inputs.jsonl`.

## Blueprint path

## Requested temporary revert comparison

Installed a development-only switch with Live Coding (371.49 s build, no restart), then ran two fresh ten-second PIE sessions: legacy absolute sample followed by corrected aligned deviation. The user's current runtime lower tolerances are now **20 cm / 30 degrees**, unlike the earlier 1000/1000 captures. Neither run changed Blueprint/map/tuning. Both compared runs used the same current settings. `collision_launch_legacy_feedback.json` and `collision_launch_aligned_feedback.json` record the actual runtime values.

Player maxima: legacy physical pelvis153.778615 cm, published target157.561349 cm; aligned physical pelvis1667.728520 cm, target1669.635863 cm. Peak magic yaw speeds were6832.672146 and6832.337110 deg/s respectively. Other agents' maxima match between the runs. This confirms the legacy calculation strongly suppresses the runaway under the current20/30 configuration. It supports the user's masking hypothesis, without proving what an older build with1000/1000 did.

Restored `Prophecy.NNLowerFeedbackAlignment=1` and verified PIE is off after both runs. Fixed implementation remains the default; the comparison switch is compiled out in Shipping. No authored assets saved or modified. The flying-target failure is still unresolved; do not describe the diagnostic revert as a fix.

## Blueprint path details

Event Hit -> MyComp == magic Cube -> Double Printtt -> Set Root Magic Velocity 2 (Add to Current=true) -> Set Root Magic Ang Velocity 2 (Add to Current=true).

Angular input is cross(normalized(cube location - hit location), NormalImpulse) * -10 * 0.016667. No decay or maximum is wired. The native node intentionally stores a constant additional velocity until overwritten/cleared; unlike root impulse momentum it has no automatic damping.

The graph's 1000/1000 Below(pelvis) call applies, but conditional upper-arm/hand configuration resolves the right hand to0cm/10degrees afterward. This is a separate finding: forcing all those upper tolerances large did not remove the launch. Lower pelvis/thigh/foot/toe tolerances are1000/1000 throughout the failing interval.

At this spin rate the root turns more than180degrees between NN steps; shortest-angle root-delta encoding cannot describe that physical revolution unambiguously. The motion is far more extreme than the reference rollout. A stable collision response should scale and bound the angular-velocity contribution and explicitly decay it, or use the existing damped root angular impulse path with appropriate units. No silent cap/decay was added to the constant-magic API, whose requested semantics are persistent velocities.
