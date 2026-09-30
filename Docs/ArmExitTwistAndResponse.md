# Arm exit snap: twist versus response

September 30 follow-up to the elbow rebound correction. The user reports the first wrist snapping at attack end and the third forearm recovering as though it moves independently. The earlier wrist-goal clamp fix remains; this investigation does not claim that positional rebound measurements established satisfactory rotational motion.

Three owned 620-tick replays of the unchanged current Blueprint compare normal settings, removed outgoing axial angular momentum, and a response override. Upper exits remain 197, 365 and 543. The Blueprint selects kinematic mode each tick. Measurements below use presented NN poses, expressed relative to spine_05; angular increments are split into shaft-parallel twist and perpendicular swing. These finite-step components are diagnostic approximations, not anatomical joint angles.

The upper-end **Set Attack Upper Body Inertia**, `EventGraph/K2Node_CallFunction_251`, sets Response **0.025**, Hold **0**, Blend **0.5**, Momentum **1**, Spine Local, Alpha **1**. It supersedes the earlier 0.82 response setting. The spring coefficient is `2/Response`; at a 1/30-second NN interval, a stationary step target receives `1-(1+w*dt)*exp(-w*dt)` of the correction: about **74.5%** for 0.025, versus **3.0%** for 0.25. Blend controls ownership; it does not stretch the response over half a second.

| Measurement | Current 0.025 | Axial outgoing momentum removed | Response 0.25, original momentum |
|---|---:|---:|---:|
| Third exit, forearm swing at543 | 12.313 degrees/tick | 12.313 | 2.427 |
| Third exit, wrist rotation at543 | 5.253 degrees/tick | 5.243 | 1.350 |
| First exit, forearm swing at197 | 8.177 degrees/tick | 8.179 | 1.905 |
| First12 recovery ticks, peak upper-arm twist, third attack | 2.761 degrees/tick | approximately2.7 | 1.050 |

At the first exit, wrist velocity in spine space changes from approximately `(-18.14,-59.74,-17.83)` cm/s before exit to `(-91.60,-98.49,-9.27)` at197 with the current response. The 0.25 replay instead gives `(-19.30,-46.41,-18.76)` at197. The slower response materially preserves outgoing motion. It does not make the arm unconstrained or remove subsequent checkpoint recovery: later first-attack rotational speeds still reach about5.3 degrees/tick near223–224.

The outgoing-momentum experiment removes shaft-parallel velocity from the upper arm and forearm and local-X roll velocity from the wrist, only when beginning exit inertia. It does **not** disable all authored twist or rotational spring attraction. It therefore rules out carried axial momentum as the main cause of this snap; it is not proof that every later twist in the checkpoint is desirable. Upper-arm twist is also reconstructed by the hinge solver as the bend plane changes, so its presence alone does not establish that upper-arm twist drives the elbow.

Recommended current-setting adjustment: **Response 0.25 seconds** on the upper-end node; keep Hold0/Blend0.5 initially. The comparison used an editor-only runtime override. Blueprint values were not changed or saved, and both overrides were reset to zero. No speculative gameplay twist suppression was retained.

Editor diagnostic controls (zero/default preserves normal behavior): `Prophecy.UpperInertia.DebugResponse` and `Prophecy.UpperInertia.DebugNoTwist`. They are read only at an enabled inertia Begin, not per tick; absent in non-editor builds, with no additional inference or disabled pose work. Live Coding loaded September29 23:39:34UTC. Three short rollout captures, no full suite or restart; owned PIE ended.

Evidence: `Saved/Diagnostics/Knee202/arm_twist_before.json`, `arm_twist_removed.json`, `arm_response_slower.json`, their `_rotation.json` measurements, and `AnalyzeArmTwist.py` / `CompareArmTwist.py` in `Saved/Diagnostics`.
