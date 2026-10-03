# Manual upper-body Armed pose

Three Blueprint nodes in `Prophecy | Agent | Armed Pose`:

- **Set Upper Body Armed Pose**: Agent, Enabled, Attack, Max Joint Speed Degrees Per Second (default 180), **Blend In Time** (default 0), and the joint alphas below (default 1). Returns success and an error message. Call once during locomotion. The target is the selected attack's ground-truth Armed frame from `prophecy_slash_half_gt.json`; all 16 attack families are supported, including kicks (upper body only). Repeating the same attack retunes settings without restarting the manual track or entry timer. Changing the attack captures the currently presented pose as the new start.
- **Get Upper Body Armed Pose Distance**: Agent, Attack; returns success and Average Degrees. This is the mean shortest rotation difference across the 16 controlled upper-body joints, each in its parent's local frame. Zero means matching rotations. It measures the presented NN target, not the simulated physical body, and does not measure position error.
- **Stop Upper Body Armed Pose**: Agent; releases either a moving or held pose and resumes the normal upper checkpoint using the last authored recurrent pose. Repeated stops are harmless. Setting Enabled=false also stops.

The controlled joints are spine_01 through spine_05, both clavicles, upper arms, lower arms and hands, neck_01, neck_02 and head. Joint offsets/scales are preserved; pelvis and legs retain locomotion ownership. SLERP uses the shortest quaternion arc. The initial largest angular distance divided by maximum speed defines one duration shared by every joint on the manual track: the farthest joint moves at the limit and all others reach their target together. During partial influence, live locomotion also contributes motion, so this speed limit governs the manual track rather than the final mixed velocity. Speeds and blend seconds follow the project's convention of 60 unpaused world ticks per second. The finished manual track remains held until stopped or superseded.

## Joint influence and entry blend (September30)

**Blend In Time** smoothly increases manual influence from zero to each joint's requested alpha. Zero time applies that influence immediately. Each local rotation is SLERPed from the live upper locomotion rotation to the current manual-track rotation with `smoothstep(entry progress) * joint alpha`. Alpha 0 leaves the joint's local rotation to locomotion; alpha 1 gives full manual influence after the entry blend; 0.5 mixes equally. Parent rotation still carries descendants: a hand alpha of 1 is exact relative to its forearm, rather than a world-space hand-position lock.

There are individual **Spine 01–05**, **Neck 01–02**, and **Head Alpha** pins. Arms have four **Hitting** and four **Non Hitting** alphas: clavicle, upperarm, lowerarm and hand. Both arms share the same blend time and speed, as clarified by the user. Roles are resolved when selecting the attack:

| Attack | Hitting profile | Non-hitting profile |
| --- | --- | --- |
| jabL, hookL, overL | Left arm | Right arm |
| jabR, hookR, overR | Right arm | Left arm |
| All six slash directions and pike | Right arm | Left arm |
| headbutt, kickL, kickR | Both arms | Neither |

For example, set spine alphas to 0.5 and Hitting Hand Alpha to 1 for a partly locomotion-driven torso and fully posed striking wrist. All effective alphas zero release the feature. Alphas outside 0–1, nonfinite values, and negative blend time are rejected. Existing calls default to time 0/all alphas 1 and retain the original behavior. Changing influence during an already running pose retunes it directly; it does not restart the entry blend.

An accepted attack, defense or animation layer cancels manual posing. Manual posing itself does not trigger attack events or load/evaluate an attack checkpoint. Its published pose is fed back into upper recurrence, including the pose used to seed a real attack. Reset and agent/world cleanup release its state.

Upper locomotion input/output and inference continue while the entry blend is incomplete or any effective joint alpha is below 1. This blends against a live prediction, not a frozen entry pose. The accepted composite feeds upper recurrence and both presentation endpoints are cached to prevent duplicate publication from applying influence twice. Once every joint has full influence, ordinary upper processing is skipped. Upper model dispatch is skipped when no active agent needs it; a mixed batch still pays the existing shared model cost for agents that need normal upper inference. Lower locomotion continues. The Armed pose bank loads lazily on an explicit Set/Get call. Disabled agents retain no manual state or clock and perform no manual pose sampling/blending. The clock retires once the manual track and entry blend have both finished, including while partial joints keep using locomotion. Holding still requires upper forward kinematics and recurrence feedback. The distance getter only samples when called and still measures distance to the complete GT pose, so partial alphas need not reach zero distance.

Implementation uses sparse sidecars and does not change retained manager or agent layouts.

September30 validation: build/Live Coding succeeded; all three focused `Prophecy.NN.ArmedPose` tests passed, covering legacy synchronized speed, all16 attack roles, moving locomotion with0/0.5/1 local alphas, entry ramp, attached offsets, accepted previous endpoints, duplicate publication, inference ownership and clock retirement. The existing Blueprint call was refreshed with its original values/links preserved and compiled successfully, left unsaved.

A155-tick owned Kinematic preview on testNN passed partial posing, retuning to full influence without restart, and Stop. With spine alphas0.5, hitting-arm1 and non-hitting0, the left jab wrist reached its local GT rotation within0.000003degrees. The complete all-one pose reached mean error below0.000001degrees. Captured network calls: partial window31frames had16 upper/16 lower; full window21frames had0 upper/11 lower; after Stop16frames had8 upper/8 lower. No attack network was called. Evidence: `Saved/Diagnostics/ArmedPoseBlend20260930/live.json`, `analysis.json`, and `Saved/Diagnostics/AttackPerformance/armed_pose_blend20260930.json`. Preview settings affected PIE only; owned PIE ended. No full suite.

Validation (September 29 local): Live Coding loaded the three nodes; final mapping fix loaded at September 28 22:14:28 UTC. The focused native `Prophecy.NN.ArmedPose.SynchronizedJoints` test passed: common arrival, maximum angular speed, quaternion sign equivalence, moving pelvis, preserved offsets/legs, duplicate publication, clock retirement and repeated Stop across simulated 30/60/120 FPS. A bounded 276-tick owned PIE check passed on `testNN`, including turning while posing, Stop from hold, Stop during a blend, restarting and triggering a real half attack. Initial mean error was 45.9021 degrees; held maximum was 0.000000107 degrees. Profiling showed 40 lower and zero upper network calls during the 81-frame manual window, then 10 lower and 10 upper calls during the 21-frame window after Stop. The second manual window again had zero upper calls. Physical tracking was not tested; this check used Kinematic mode. Owned PIE ended and the profiler stopped; no Blueprint save, editor restart or full suite.

Evidence: `Saved/Diagnostics/ArmedPose/live.json`, `analysis.json`, `Saved/Diagnostics/AttackPerformance/manual_armed_pose.json`. Scripts: `TestArmedPoseNative.py`, `TestArmedPose.py`, `AnalyzeArmedPose.py` under `Saved/Diagnostics`. The live check caught and fixed a physical-target versus NN bone-order mismatch; binding now uses snapshot NN indices and samples presented transforms by name.


October 2 entry-history correction (loaded and verified): a current TestNN capture
shows the first Armed-pose application at tick 140 replacing the previous
interpolation endpoint with the sampled displayed local pose. At zero entry weight
this changed spine_05 by 7.026882 degrees and head by 4.702679 degrees / 2.576814 cm;
pelvis history was unchanged. The entry now seeds its cached previous locals from
the incoming previous policy endpoint; the sampled visible pose still starts the
manual rotation track. Subsequent updates continue using the last accepted composite.
Existing .1 blend, 350-degree speed, .1 core influence and Blueprint wiring are preserved.
No added smoothing, duration or inference. Evidence: Saved/Diagnostics/ArmedSpineHitch
and Saved/Diagnostics/Knee202/armed_spine_before.json. Live Coding loaded 18:13:53 UTC; all four ArmedPose checks passed 18:14:14 UTC. The owned 230-tick replay reduced the tick-140 spine/head history jump to numerical zero (head displacement below 1e-12 cm). Owned Play ended; Blueprint tuning and assets were unchanged.


October 2 forearm convention follow-up (loaded and checked): Armed targets were
still loading source-controller forearm rotations directly, unlike locomotion,
full/half attacks and defense. jabR's right forearm differed from the canonical
upper-arm/idle convention by 169.546 degrees. This also changed the corresponding
hand's parent-local rotation, allowing the two local interpolation paths to twist
unnecessarily. Both target forearms now use the common reconstruction before
parent-local goals are derived. The original authored hand/sword component rotation
is preserved. The conversion runs once per cached target bank, for all 16 families;
the distance getter uses the same corrected bank. Raw GT data stays unchanged.

The user confirmed the full turn is gone in the Play session started after the 18:23:39 UTC Live Coding load. That session was left running.

All eight Armed/forearm checks passed at 18:25:49 UTC. Both arms across all 16 source families match the common convention; original hand rotations and corrected wrist composition are covered. The existing entry-history fix also passed again. Normal editor DLL rebuild is required before cold launch.
