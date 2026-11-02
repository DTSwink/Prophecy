# Prophecy â€” current handoff

**Accepted lab port, November 3 (built and verified; source-only checkpoint):**
Current normal-kick solver and live saved scene/settings are ported. Four jab/hook
cutoffs now match typed C++ defaults. Native settings use the validated
bodyflip-lab-settings-v1 wrapper. Arrow-step hit and Big Throw renderer fixes
remain in the browser. Previous lab-only notes below are historical.

Normal Editor build succeeded. Complete-project cold host passed saved defaults,
Small Throw and Blueprint compatibility; 10,552 pins/links retained. Normal
TestNN editor passed reflection and 60 owned Play ticks, then returned to edit.
No gameplay assets or live settings changed. Two intermediate startup GC crashes
stopped recurring after refreshing the diagnostic host from the independently
rebuilt Ambient binaries; no Ambient code was changed in this task.

34 app/package cases /945 frames pass; pinned V8 checks 268,801 values exactly;
actual Unreal VM checks 210,779 values exactly. Kick22, pose/attack5, sweep6,
sweep-cut8 and package101 checks pass. Broad lab suite:26 pass after harness
repairs;9 older checks still fail on previous committed source too (8 same first
failure). These are recorded, not called green. Saved-scene tests have a stale
attackFree=false assertion: persistent Ball pose correctly retains authored
joint freedom. Clear-air tracking meets existing gates; floor contact still
reaches57.15deg against45deg. Earlier hand/contact limitations remain.

Evidence: Saved/Diagnostics/BodyflipAccepted20261102. Compact receipt:
Tools/Recovery/Receipts20261102Bodyflip/accepted-lab-final.json. Only Bodyflip
source/settings/tests/receipt are in this checkpoint; no heavy assets/binaries.

**Big Throw playback performance, November 2 (LAB ONLY):** Current live setup
profiled read-only. The 43,494-triangle spear renderer rebuilt temporary vectors
and spread arguments every frame; drawing dominated CPU time, not trajectory
sampling or projectile physics. `renderer.js` now reuses typed vertex/normal/
color buffers and scalar transforms, preserving the full mesh and draw order.
Actual-app Node replay with a GL sink: repeated-pass mean 60.65 -> 8.75 ms,
p95 94.78 -> 10.55 ms; first-pass mean 56.94 -> 11.74 ms (first-use spikes remain).
These are CPU replay timings, not measured browser FPS. Nine mesh checks match
uploaded Float32 values exactly; 115 before/after character/projectile frames
also match exactly. Settings unchanged; served renderer verified. Regression:
`node Labs/BodyflipLab/verify-projectile-renderer.mjs`. Evidence and profile:
`Saved/Diagnostics/ThrowPlayback20261102/`. No Unreal port or Git push.

**Arrow-step hit indicator, November 2 (LAB ONLY):** Forward arrow steps now run
the same ticks/contact checks as Play, including intermediate frames when held.
Previously the seek path cleared the hit and never tested contact. Rewinding,
scrubbing or wrapping clears later hits and checks the selected pose without a
stale swept segment. Attack motion, collision thresholds and live settings are
unchanged. `node Labs/BodyflipLab/verify-frame-step.mjs`: 13 behavioral checks
pass; source syntax and served app.js verified. No Unreal port or Git push.

**Normal kick pose correction, November 2 (LAB ONLY; awaiting user review):**
User clarified that the deformed kick poses matter, not only the Hit direction.
Normal Kick L/R now use the existing common-body airborne reaction, retaining
recorded joint arrangement instead of the16-variable spine/free-hip rebalance.
Aim also rotates the complete compensated pose; it reaches its correction by
Armed and retains the existing normal-kick return policy. The motion-compensation
checkbox now also works for normal kicks. Entry/return use the projected base.
Normal kicks carry the existing authored-pose exemption through return so spin
recoil cannot re-clamp them into resting joint cones. Recoil itself is retained.

Measured old distortions: compensation added up to49.15deg at spine01 and33.66deg
at the free hip; aim added65-103deg at the striking hip; spin-recoil's resting
clamp independently changed Kick R by35.83deg. These corrections no longer
reshape the normal kick. The accepted sweep branch is unchanged.

Steering is an explicit commanded body turn, not passive conserved motion.
Its finite-step momentum is the difference between the moving aim frame and
that same interval with the aim frame held fixed. The original neutral solver's
residual is retained (transport disagreement<5.2e-10), not reset to zero.
Fractional seeks use the actual underlying integration interval. Sweep's earlier
bookkeeping is retained to avoid changing the accepted movement in this task.

22 actual-app motion cases at960Hz cover both legs, flip+/-400, twist+/-200,
front/rear targets, zero spin, compensation off and full3D. Maximum Hit direction
error9.2e-16; added aim joint rotation<2.8e-13deg; recorded-stroke shape difference
<0.000735deg /4.4micrometres from retained recoil. Reverse seeks agree<9e-15.
Boundary pose differences across+/-1e-7s are below0.000717deg; strike/return
velocity joins below1.7deg/s at6.25e-7s. The original falling loop has a velocity
corner at this setup's entry time (about263deg/s at left hand); projected kick
entry matches that baseline to about1e-6deg/s. That pre-existing loop corner is
not claimed fixed. No still image or video was used to approve dynamic quality.
Sweep/Slash L/Pike:363 before/after poses match exactly. Live settings unchanged;
served source bytes verified. No Unreal package/build changes and no Git push.
Portable regression: `node Labs/BodyflipLab/verify-kick-shape.mjs` (four reported
cases), `--full` selects22. Captured fixture: `fixtures/kick-spin.json`.
Evidence: `Saved/Diagnostics/KickPose20261102/`; preceding diagnosis below remains
historical. User must refresh the lab to review the changed movement.

**Earlier normal-kick investigation, November 2 (superseded by lab correction above):**
Captured the live Kick L / flip-400 / twist200 Space Gym setup read-only at
`Saved/Diagnostics/KickSpin20261102/live-state.json`. Actual app replay checks
Kick L/R at zero spin and flip+/-400 with twist200, plus sweep controls.
Kick L/-400 misses the target DIRECTION by38.261deg; its bounded solve returns
error0.655446 after52 trajectory evaluations, and production applies that failed
result without a failure indication. Other three spinning normal-kick endpoints
fit, but aiming changes the kicking hip by65.44-103.39deg during the motion.
Normal kicks use Hit-derived joint-coordinate offsets, unlike sweep's rigid
whole-compensated-pose aim. Do not equate an exact Hit endpoint with good motion.

Offline in-memory experiment retains normal `createBalanced` compensation and
changes only aim to a rigid whole-pose turn. Direction errors fall below1.3e-6deg
without changing any joint-local articulation (below5.2e-14deg). Normal kick
entry/return also switches raw falling poses against the projected display,
causing about8deg entry and5-6deg exit jumps, including at zero spin. Applying
the existing sweep projected-base rule removes those jumps: differences halve
with each halved time interval. Eight combined prototype cases cover both legs,
flip+/-400, twist+200/current rear target and twist-200/reflected front target.
The accepted sweep generator, live settings, lab runtime and Unreal are unchanged.

Proposed implementation: keep normal kick animation/balance; predict its balanced
Hit pose; use one explicit rigid aiming command, fully introduced by Armed;
retain existing return policy; use the same projected baseline on both sides.
Do not copy sweep's momentum bookkeeping blindly: the prototype reports roughly
0.26-1.71 angular-momentum residual versus below0.001 in the current normal path;
current sweep controls themselves report about1.45-1.47. Its finite-step
`I*omega` steering accounting must be resolved/verified before adoption. The
pre-existing arm-speed peaks also remain; prototype endpoint/continuity checks are not
visual approval of the full motion. No videos or still-based motion claims.
Evidence/scripts: `Saved/Diagnostics/KickSpin20261102/` (current-audit,
rigid-audit, rigid-projected-audit). No production fix, build or push this turn.

**Pike steering replacement, November 2 (accepted; ported to Unreal):** removed the rejected
06 world-chest lock and its winding history. The same optional saved checkbox
is now labelled **Pike: steer through thrust**. It plans a continuous heading /
five-spine elevation curve at Armed, mid-stroke and Hit in the moving carrier
frame, evaluating the actual momentum response. Arm locals, source timing,
ordinary aim/return and released-contact articulation are retained. Preparation
is cooperative; no solver is added to the playback pose after momentum balance.
Entry heading uses the shortest branch; an unconverged fit retains standard aim
and explicitly reports that in the lab's sequence status instead of applying it.

Current flip400/twist200 numerical motion checks at960Hz pass, including fresh
reverse seeks and velocity boundaries at Armed, mid-stroke, cut and return-end.
Added spine rotation peaks at22.82degrees per joint versus44.68 in rejected06;
aim direction error4.25e-7, arm-local difference<2e-13degrees, momentum residual
<3.4e-6. Front/rear, opposite/fast/inherited spin and Undo-off cases inspected
numerically. Off, zero-spin and Slash L poses match the previous paths exactly.
Production default, fresh reverse, front, original rear and fast-spin checks pass.
Permanent check: `node Labs/BodyflipLab/verify-pike-steering.mjs` (optional fixture
and `reverse` argument). Evidence: Saved/Diagnostics/PikeStroke20261102/.

**Limits:** the current stroke still drifts about6.2degrees between fitted points
(previous standard aim about69degrees); COM-relative contact path still has about
15.5cm curvature. This is not an exact straight-line constraint or a claim that
all dynamic movement looks correct. The full3D momentum test failed the bounded
fit: it now reports unavailability and keeps standard aim. Do not conceal this
fallback or call full3D Pike steering solved. User specifically clarified that
stills cannot validate dynamic mistakes; rely on time-dependent checks and never
claim that still images establish acceptable motion. No new videos were made.
User accepted the replacement and requested the complete Unreal port and Git
backup. Current captured setup has steering ON, Pike cut at source frame16,
flip400/twist200 and a1s attack delay. The live state was read without writes.
Native build, exact Unreal solver parity and clear-air physical replay pass.
TestNN is open; the owned Play startup check passed. See Docs/BodyflipNative.md.
Other earlier elbow-return concerns remain separate.

**Earlier Pike06 visual rejection, November 2 (replaced above):** user reports the unwrapped
motion tears/corkscrews the upper body. The wrap discontinuity was removed, but
that did NOT validate the movement. Offline inspection of the reported scene
with06 enabled measures223.41degrees of extra distributed torso rotation near
Armed (44.68degrees per spine, on top of authored pose). At Hit it is116.90degrees.
The full chest-orientation constraint cancels the carrier flip through the spine;
continuous unwrapping retains the large rotation instead of making it plausible.
Prior checks for continuity, arm-local preservation, momentum residual and endpoint
aim missed total torso deformation. Do not claim06 is a satisfactory Pike solution.
A replacement is not yet validated; do not add another clamp/counter-correction
or assume the earlier rejected direction-only prototypes are solved.
Current captured saved scene has06 off. No animation/settings changes during this
review. Evidence: Saved/Diagnostics/Pike06TorsoReview20261102/torso-correction.json.
User explicitly said to STOP MAKING VIDEOS; do not generate any unless asked again.

**Earlier Pike06 numerical wrap fix, November 2 (visual result rejected above):** the reported180degree
branch snap is fixed in the optional **Pike: spine absorbs rotation** path.
The spine correction retains the equivalent rotation nearest the previous
completed physical step before applying entry weight / five-spine distribution.
Only completed fixed steps select winding; momentum trial poses and fractional
or reverse seeks cannot change it. The physical articulation context now exposes
its start/timestep; a continued segment starts with its own identity correction.
The existing return carries the continuous correction and its outgoing velocity.

Exact reported flip400/twist200 case: maximum spine step at960Hz falls from
141.23degrees to1.94degrees. Forward/rear targets, opposite spin, flip800, and a
Pike beginning during inherited spin pass through entry, strike and full return.
Authored arm-local rotations and target direction pass; reported-case momentum
residual<1e-7. Reverse-order poses match forward exactly. Original reviewed06
forward/rear poses and checkbox-OFF poses remain position-exact (rotation roundoff
<1e-13deg). Released-foot-follow regression passes. Permanent regression:
`node Labs/BodyflipLab/verify-pike-spine-wrap.mjs` (with its regression fixture).
Evidence: Saved/Diagnostics/Pike06Wrap20261102/verification.json, parity.json,
per-case traces and 06-wrap-current.mp4 /06-wrap-front.mp4 (1080p60 before/after,
two normal passes then quarter speed). Rendered frame comparison inspected.
Only06 rotation-branch handling and physical-context metadata changed; elbow
files verified untouched. Checkbox remains default OFF; Refresh then enable it
to inspect. No live scene writes, UI control, Unreal changes or push.

**Earlier scope clarification, November 2:** user meant the06 wrap snap,
not the elbow-return body reaction. Keep this investigation focused on06.
The verified cause is `physical-aim.js` taking a fresh shortest quaternion log
before multiplying by entry weight and distributing it across the five spines.
At1.80833s the correction is178.00degrees; at1.8125s its axis reverses with
179.42degrees on the opposite branch. Partial entry weight / spine fractions
make those equivalent full rotations different partial poses: measured137.75deg
upper-body jump in4.17ms. A correction needs a continuous rotation path before
weighting/distribution, including deterministic seeks and return; no additional
elbow redesign is implied by this request. No animation code changed.

**Earlier Pike rotation-snap investigation, November 2 (06 now fixed above):**
user reports whole-body rotation snapping after the elbow fixes. Exact captured
scene still has06 OFF: Pike, flip400/twist200, delay1, F16 cut. The shoulder-transfer
workaround preserves forearm/hand orientation but moves the arm masses along a
different path. Momentum compensation responds with a sharp carrier counter-turn.
Offline controls: peak pelvis rotation839.12deg/s without either elbow protection,
1154.01 with right-only protection,1220.10 with both. Removing just the shoulder
transfer in an offline control removes that return burst (817.18deg/s overall
peak occurs during entry); that diagnostic redirects the hand, so it was NOT
installed as a fix. Previous elbow/hand/continuity checks were insufficient to
validate the whole-body response. Do not describe the shoulder-transfer workaround
as preserving whole-body motion/momentum without this qualification. The return
needs a coherent legal arm trajectory, not another whole-body counter-correction.

Separate06 failure reproduced in the same scene when enabled offline: at1.8125s
the shortest rotation log flips across180degrees (178.00deg -> opposite179.42deg).
Its weighted/distributed spine correction jumps137.75degrees in4.17ms. This is a
true discontinuity;06 remains default OFF and is not the cause in the saved state.
Evidence: Saved/Diagnostics/RotationSnap20261102/{fixture,audit,findings}.json/mjs
and per-variant traces. All production animation hashes verified unchanged during
this investigation; live scene preserved, no UI/Unreal work or push.

**Earlier Pike other-elbow return fix, November 2 (body reaction now under review):** the earlier protection
covered only the right/sword arm. In the new captured Pike setup (flip400,
twist200, attackDelay1, F16 cut,06 off), the left elbow reached79.42degrees
backwards during return (51.80degrees at the user's paused2.25s frame).
Both Pike elbows now use the existing extension-braking/shoulder-transfer rule.
No new clamp or return envelope: the blocked elbow turn passes into its shoulder,
preserving the combined forearm/hand orientation and outgoing velocity.
The actual-app960Hz return check now stays above3.55degrees flexion left and
3.91degrees right. Both-arm audit checks transition orientation preservation,
other local joints, rigid sockets, aim direction and boundaries. Original F16,
F17 and four coupled slash return regressions pass; reverse seek is deterministic.
Rendered before/after return frames inspected. Evidence:
Saved/Diagnostics/OtherElbow20261102/ (fixture, before/after, verified-current,
original-cut16/cut17 reports, coupled-returns.txt and comparison.png).
Production changes are limited to accepting both protected elbow indices and
passing both for Pike; other attacks retain their previous protection selection.
Pike06 remains optional/default off. Refresh the lab to load this fix. No live
settings writes, UI control, Unreal work or push.

**Pike 06 rollback option, November 2:** More options now ends with
**Pike: spine absorbs rotation** (`pikeSpineAbsorb`), default OFF. Off restores
pre-06 Pike behavior; on enables the experimental06 articulation. Saved per
scene, with the existing playback/time-preserving rebuild. Actual-app checks
pass: exact pre-06 poses off (103 Pike frames), on activates06, off restores the
baseline, saved on/off values and playback intent retained. The current captured
scene uses Slash L, flip400/twist200: all176 checked frames are identical with
the option on/off and pre-06 code. This option only affects Pike.
Evidence: Saved/Diagnostics/Pike06Toggle20261102/{current-result,pike-result}.txt.
Refresh to load the checkbox. No live scene writes, UI control, Unreal work or
push. This supplies the requested rollback; it does not fix the new motion case.

**Earlier Pike 06 installation, November 2 (now opt-in above):** user selected "Spine absorbs
rotation" and explicitly requested installation. `physical-aim.js` now uses that
orientation-only spine articulation for Pike with spin. It preserves authored
arm locals and the accepted return, and composes the existing released-foot
follow after the spine turn inside momentum balance. Other attacks retain their
previous articulation. Production matches every archived06 forward/rear displayed
pose through return within1.3e-13degrees /1.9e-15metres.480Hz continuity, reverse
seeks,19 attack cuts,19 zero-spin attacks, four coupled weapon returns and physical
slash aim pass. A focused Pike/contact composition check passes1,780 assertions
(foot direction error<0.000002degrees, momentum residual<0.000015).
Evidence: Saved/Diagnostics/Pike06Applied20261102/.
Residual positional curve and the known faster-spin quaternion-branch limitation
remain; this is the selected06 behavior, not a general straight-line constraint.
The user stopped computer control with Escape before the green Refresh button
could be clicked. Disk code is updated; the existing lab still needs Refresh.
No live settings were changed by this work; no Unreal work or push.

**Earlier Pike visual review correction, November 2 (before installation):** user reports severe twitching /
snapping in the attempts except06 (spine absorbs rotation). Retain06 as the only
candidate; reject01-05/07/08. Previous straightness/momentum/encoded-frame checks
were insufficient to accept motion. Saved120Hz poses confirm individual bone
jumps of up to174.45degrees per8.33ms in rejected variants. New06 forward/rear
480Hz audits show converging pose continuity at Armed/Hit/return-end, identical
reverse seeks, and authored sword-arm local rotations preserved within1.2e-13deg.
These checks do not establish a general finished fix: residual curve, faster-spin
quaternion branches and ground-contact-follow composition remain. No prototype
installed; no Unreal work. Evidence and decision: Saved/Diagnostics/PikeFlip20261102/
Videos/review-decision.json and continuity-06-orientation-{forward,back}.json.

**Pike review playback fix, November 2:** the comparison is now served at
http://127.0.0.1:8877/ by a read-only, allowlisted loopback server with byte-range
support. This avoids broken relative media paths in the app's local-file preview.
The page uses that media base and shows loading/playback errors instead of silently
ignoring them. Open Review.cmd beside the videos restarts the service when needed.
All nine video range requests pass; actual in-app browser baseline/variant06
playback reached4.628/4.631s with readyState4. No animation changes.

**Pike flip video review, November 2 (experiments only):** user requested videos
of all attempts, with both forward and rear targets, to choose visually. Eight
exact prototype sources plus unchanged baseline are archived under
Saved/Diagnostics/PikeFlip20261102/Videos/. Nine numbered 1080p60 MP4s each
show both targets through entry, strike and return; two 1x passes then 0.25x.
A 4K60 nine-way overview and local review page include known failures.
[Open video review](Saved/Diagnostics/PikeFlip20261102/Videos/index.html).
No experimental aiming code was applied to the live lab; baseline hash verified.
The original flip/Pike correction remains unresolved. Orientation-only variant06
passes current forward/rear momentum checks but retains curvature. Direction
variant08 straightens the captured rear stroke, but forward and other spin
cases fail. Earlier line-lock variants also have momentum spikes / sampling-order
sensitivity; video appearance alone is not a regression pass. Retain the accepted
Pike source, elbow/wrist return and settings below. Unreal remains deferred.

**Pike restart, November 2 (lab only):** previous path fix rejected after the
user's rear target made the torso fold over. Its endpoint fit had selected a
119-degree bend. Restarted from pre-fix code: Pike now uses heading/elevation
only, with no arbitrary sideways-bend/roll fallback; the reported target needs
20.2 degrees. Previous wrist IK and frozen-shoulder translation removed.
Authored pelvis travel follows the stroke; source hand rotations, compensation,
return inertia and other attacks retained. F16-trimmed Pike return now prevents
elbow hyperextension while passing its blocked turn through the shoulder: the
elbow-only brake redirected the sword and is superseded. Sword/forearm return
orientation and local wrist motion are preserved; safe Pike/other returns stay
unchanged. Elbow, combined-arm, cut/duration and spin checks pass. Exact rear/front,
24-direction grids, 19 cuts and four coupled returns pass. Whole rear movement
rendered and inspected. Residual path curvature is documented, not called zero.
`pike_final.fbx` remains Armed 9 / Hit 16 / End 17 at 30 Hz.
**The user has now accepted the lab and requested the complete native port below.**
[Lab details and verification](Labs/BodyflipLab/README.md).

**Bodyflip Unreal port, November 2 — accepted update built and loaded:**
Current package includes all five changed lab modules, pike_final and the latest
saved target/flip400/twist200/delay1/cut16/steering-ON settings. Normal builds pass.
Start Bodyflip Saved Lab Setup retains the exact scene without rewiring Blueprint.
18 app/adapter cases (513 frames) pass; package/source/settings audit100 checks
passes. Existing Blueprint compiles with all10,552 original pins/links preserved.
Clear-air native saved-setup replay passes through198 frames: maximum physical
error6.76cm /12.96deg, RMS0.466cm /0.492deg, leg-length error0.1094cm. Lowering only
the test floor preserves every canonical packet and removes all floor contacts.
The original floor-level Space Gym fixture reaches89.2deg right-foot rotation
error; a combined-run left-hand push also exceeded the3cm leg gate (4.125cm).
Do not describe the entire contact suite as green. Pinned V8:21 cases /607 frames exact. Actual Unreal:513 frames /117,179 numbers
exact. TestNN is open; healthy reflection and owned60-tick Play startup verified.
No assets or live lab state were saved. The requested broad repository checkpoint
includes current work and native runtime dependencies; see the recovery manifest.
[Bodyflip native current handoff](Docs/BodyflipNative.md).

Handoff updated **November 2, 2026**. This file and the current sections of linked topics take precedence over dated archives. Each topic has its own verification/build state.

## Resume here

**November 2 isolated crawl trial — NOT RUNNING; awaiting authorized replacement capacity.**
Capacity automation ACTIVE: launch-isolated-crawl-experiment-on-rtx-4000-ada,
every60seconds, explicitly authorized after replacement unavailability. Follow
this current section, not historical instructions below. Reconcile provider and
local receipts before allocating; exactly ONE replacement at <=$0.28/h, check
Community and Secure. Stay quiet while unavailable/unchanged. Notify verified
launch, meaningful failure or required user action only. Pause this schedule
once launch is fully verified, on unresolved setup failure or user cancellation.
Keep setup bounded20minutes with BOTH local/remote controls identical. If setup
cannot complete, stop only owned replacement and confirm provider EXITED.
Never allocate another pod over an existing replacement. Existing original
5xs589fdlcb7nr and stopped vpv6saq7zyooak/disk must be left untouched.
Working directory C:/Users/singerie/Documents/Unreal Projects/Prophecy; Python
Saved/Robotics/env/Scripts/python.exe. Upload main20414 with replacement helper;
use deploy_crawl_only_experiment.py for this trial, NOT old disabled-curriculum
launch helpers. After setup preflight/stage/launch/audit/verify, check local
TB8035 reward cards and8021 replay, then report verified launch and pause.

Main final20414 is safe locally and persistent; exact original main source/configs
are archived for rollback. Main checkpoint SHA
cd4e1569da103b8ab07e2cbd265e0b21415e41e138e0402b984a74837320f99f.
Trial2048 rows all moving crawl/code12/both legs passive, existing random starts,
50% target speed and signed displacement bonus passed full GPU preflight:
three finite PPO updates from20414,36864 termination boundaries,8 independent
replay reconstructions. Reward zero at rest,5 at target,negative backward/large
lateral error; no positive credit for zero-net rocking. Existing physics,
500failure penalty,0.8m pelvis sphere/130tick windows preserved.
Production launch20-56-23 FAILED before training: train.py resume guard lacked
explicit allowance for slow_loco_crawl_only_experiment. Agent also armed only
remote setup watchdog, leaving local guard in until-stopped mode. Local fallback
stopped podvpv6saq7zyooak on failure. Provider confirms EXITED; same-host restart
refused for no free GPU. No experiment checkpoint was promoted.
Config exception is now implemented and exact YAML delta checked. Launch helper
now requires identical local/remote bounded setup guards, matching pod and price.
Corrected source790d41c8f061b26d496738d2e924394b8e85dcf1f80f2a5ac721d817207acd1a
is locally and persistently verified, NOT installed on running hardware.
User AUTHORIZED ONE replacement RTX4000Ada <=$0.28/h. Initial Community and Secure
attempts both unavailable; no replacement allocated. Preserve both stopped pods
and their disks; never restart them alongside a replacement or touch other pods.
Helpers: replace_crawl_experiment_pod.py allocate/upload_resume;
deploy_slow_policy.py setup; deploy_crawl_only_experiment.py preflight/stage/
launch/audit/verify. Allocation helper reconciles named replacements first.
Before launch require actual-checkpoint2048world preflight on new GPU, both setup
guards armed and same deadline, two advancing finite statuses,160obs/flags,
8 independent live replays, persistent readback and telemetry, then release
setup deadline. Main resumes later from MAIN20414 plus main-source.zip, never
experimental weights. Receipts/rollback.json: Saved/MimicKitSlowLoco/
crawl-only-experiment-20261102/. Do not claim launch until deployment-verified.json.


**Slow-loco forward-bonus follow-up, November 2 — analysis only, stall persists.**
Checkpoint20240 full2048-world128tick no-update probe confirms bonus reaches PPO.
Two-passive crawl after first second:2.16cm/s, pelvis22.3cm, upper commands about
half the working one-leg cases. Only77/2048worlds target this task. Current bonus
dominates pose reward but not the scale of failure-related learning signals.
Zero-clipped bonus has a rocking loophole: +/-10cm/s equal-time motion can earn
positive reward with no net displacement. This is not proof of exploitation.
Recommend isolated signed-net-progress/focused stable-start crawl test; no new
reward/curriculum change deployed. Main20310,412 production hashes unchanged,
probe complete. See current SlowLocoPolicy.md and crawl-forward-followup-20261102.

**Slow-loco separate crawl-speed reward, November 2 — VERIFIED RUNNING.**
User approved dominant movement reward only for perturbed moving crawl with
both legs disabled. Add0..5 speed-matching bonus outside exp(-pose/tracking loss),
target cycle-average23.376cm/s; zero at rest, lower for lateral/overspeed. Existing
0..1 imitation reward and500 failure penalty retained. Other rows unchanged.
Full2048 preflight:36,864 boundaries, three finite resumed PPO updates and33
independent replay reconstructions pass. Latest20039_final preserved locally
and persistent, then SAME retained RTX4000Ada podvpv6saq7zyooak resumed run
20261102_192728_uefn_slowloco_disabled_curriculum_crawl_forward5_2048.
Live20040->20050 verified, optimizer/normalizer restored, persistent readback
passed; until-stopped released. TB19-27-28 now has reward/crawl_forward,
crawl_pose and actual/target speed cards; replayer includes separate bonus.
Details and receipts: Labs/RoboticMotionAE/SlowLocoPolicy.md and
Saved/MimicKitSlowLoco/crawl-forward-deploy-20261102/. Previous stall/capacity
audits below are historical evidence; reward change is now active.

**Slow-loco two-passive-leg stall audit, November 2 — analysis only.**
Checkpoint19886,96 isolated worlds/256 ticks, training noise/reset path, no
learning updates. One-leg-disabled crawl moves28.5–30.5cm/s; both-disabled3.84
against23.38cm/s target. Position+rotation is97.6% of both-disabled mean loss;
exp(-loss) median reward2.09e-6,81.3% of transitions below0.001. Forward-speed
correction barely improves reward. COM permits2.45cm/s;80cm/130tick sphere
can admit ~4.4–6cm/s. Penalty500/zero bootstrap is applied; critic predicts
large failure cost. Arms enabled/commanded, passive legs zero torque and
excluded loss/termination, reference clock correct. No production changes.
Recommend testing separate dense progress reward outside pose exponential,
scoped to both-passive moving crawl; not deployed or proven learning fix.
Main advanced19986/1309868032samples;412 production hashes unchanged; probes
finished. Detailed evidence/limitations in Labs/RoboticMotionAE/SlowLocoPolicy.md
and Saved/MimicKitSlowLoco/crawl-stall-audit-20261102/analysis.json.

**Slow-loco upper-body capacity audit, November 2 — analysis only.**
Current upper-body caps can support and perform an arm-driven pull with both
legs at zero torque: one isolated matched-start test moved COM17.15cm/pelvis24.61cm
without torso/head/pelvis floor contact. Doubling shoulders gave17.73cm COM;
doubling all upper-body caps destabilized that controller. This does NOT prove
sustained target-speed legless crawl or arbitrary passive-leg initialization.
Rear-biased loading/contact coordination is a stronger current suspect than
a blanket torque shortage. Source/settings unchanged (412 remote hashes), no
GPU allocated; all scratch probes exited, main2048 run verified advancing19816.
Details, limitations and full trial evidence in the current
[SlowLocoPolicy](Labs/RoboticMotionAE/SlowLocoPolicy.md) capacity-audit section.

**Slow-loco moving-crawl legs-only, November 2 — VERIFIED RUNNING.**
Latest18485_final locally/persistently preserved. Same retained RTX4000Ada now
runs20261102_140858_uefn_slowloco_disabled_curriculum_crawl_legs_only_2048;
18486->18496 verified, optimizer/normalizer restored, persistent backup read back.
Moving crawl always keeps both arms enabled: perturbed one leg at90% speed or
both legs at50%; vanilla unchanged. Crawl-idle/other motion masks unchanged.
Global10/30/30/30 quotas retained; crawl's cohort3 redistributed to other7motions.
33live replay cases verified.130tick crawl spheres and500/100 penalties retained.
Until-stopped released. TB14-08-58. See current
[SlowLocoPolicy](Labs/RoboticMotionAE/SlowLocoPolicy.md) and crawl-legs-only receipts.

**Pike pre-impact interpolation correction, November 2 (current, local):**
Captured saved Pike setup (Direct to Armed) at Saved/BodyflipLab/pike-input.json.
Violent pre-impact swings originated in source subframe interpolation, before
compensation/aim: separate local forearm/wrist slerps added15.08deg/10.38deg hand
detours between sourceF14-15/F15-16, where recorded hand keys differ7.14/4.33deg.
Pike now samples root-normalized component rotations together, then reconstructs
local joints for retargeting and pelvis transfer. Original integer poses retained;
source sword direction matches component slerp at subframes within1.2e-13deg,
with pelvis transfer on/off. Rigid local socket positions retained. Scope is Pike;
slash/throw/kick interpolation and all return inertia/decay logic stay unchanged.
Armed0.935847158s and Hit1.169180491s unchanged. Pre-impact authored peak hand
rotation1432deg/s ->215deg/s; displayed aim peak1650deg/s ->430deg/s during strike.
Actual rendered Armed-to-Hit contact sheet reviewed at Saved/BodyflipLab/Pike/
return.png. Current captured-app assertions pass in audit-pike-entry.mjs; all four
coupled sword-return regressions pass unchanged. No live state writes, native
work or push. Refresh existing lab to review.

**Coupled forearm/wrist return, November 2 (current, local):**
User required continuing the trimmed Slash LU fix while retaining existing inertia.
Return seeding now removes equal opposing axial forearm/wrist rates as a pair,
relative to the upper arm. Net hand angular velocity, swing rates, starting pose,
return polynomial/decay and duration policy are retained. Same-sign roll is
untouched. This applies to the sword arm only for slashes/pike, in original and
distance-weighted returns. The hand remains forearm-local throughout recovery.
No independent world-hand override, added damping, speed cap, source interpolation
change, or after-the-fact wrist clamp. Resting limits may still be exceeded briefly,
as authorized for attacks. No guarantee of passive articulated momentum conservation.
Original LU cutoff20: accumulated displayed hand travel about462deg ->260deg.
Peak wrist limit excess127.7deg ->6.62deg; the small remaining transient is NOT
claimed strictly within resting limits. LU cutoff21 and Slash L full end23 have
valid wrists throughout sampled return. Conservative entire-sword mesh/head
clearance bounds: LU20 >=5.66cm, LU21 >=0.30cm, L23 >=14.15cm (sampled at240Hz).
Four actual-app cases pass weapon path, continuous pose/hand velocity, and seek
checks, including zero distance weight. A synthetic counter-roll pair preserves
net hand inertia to5.5e-16rad; non-cancelling motion remains exactly unchanged.
All19 attack cutoff tests pass. Actual body/sword contact sheet reviewed. Live
playback not controlled. Reload lab; no live state writes, native work or push.
Regression: verify-coupled-weapon-return.mjs with saved original fixture
../../Saved/BodyflipLab/trimmed-sword-input.json. Separate current Slash L audit:
audit-sword-wrist.mjs ../../Saved/BodyflipLab/slashL-wrist-input.json final-L.

**Slash L wrist/head regression rollback, November 2 (preceding correction):**
User reported broken wrist and sword/head penetration in active Slash L (full
source end23), screenshot at1.55s. The independent world-hand return introduced
by the last attempt was the cause. It preserved arm motion but broke the wrist's
relationship to that arm: at1.55s wrist exceeded limits by95.32deg; peak148.2deg.
Its sword centerline passed9.1cm inside the head capsule during return.
Removed that complete attempt from core.js/jump-attack.js, restoring both files
byte-for-byte to pre-sword-fix snapshots (all earlier trim controls retained).
The established forearm-local wrist return and full original inertia are restored.
No new braking, clamping, world-hand override or source-interpolation change.
Actual-app replay of the saved current setup now passes wrist limits throughout
return (max error2.8e-14deg). A conservative capsule enclosing the entire actual
sword mesh stays at least14.15cm from the rendered head capsule at240Hz samples.
Audit: Labs/BodyflipLab/audit-sword-wrist.mjs with fixture
../../Saved/BodyflipLab/slashL-wrist-input.json; before/after in Saved/BodyflipLab.
Earlier independent-hand verification is retained as rejected history under
Saved/BodyflipLab/rejected-independent-hand-verification.mjs, not a passing test.
The original trimmed Slash LU complaint was not solved by that rollback; the
coupled correction above supersedes this pending status. Future diagnosis must check
wrist/forearm coherence and weapon clearance, not merely accumulated sword travel.
No live state edits or native work; refresh the existing lab.

**Sword return correction, November 2 (REVERTED: wrist/head regression):**
The rejected braking/return-target projection was fully reverted first. Source
interpolation was investigated but is unchanged. Existing return curves, decay,
duration selection, compensation and joint-limit handoff remain unchanged.
For sword attacks (slashes/pike), only hand_r return orientation now uses the
actual hand/world quaternion and velocity in the same existing transition curve.
Forearm-relative counter-twist was previously carried as independent rotational
inertia, creating excess sword spin. The hand calculation is applied after the
original compensation/return plan so it does not change body or arm trajectories.
Throws, kicks and unarmed attacks retain their old path. No velocity clamp or
new damping policy. No live state edits or native work; refresh lab for review.
Before/after actual-app comparison on the captured Slash LU cutoff20: attack
before cut and every non-hand return orientation match within1.25e-16rad;
all joint positions match, incoming hand velocity and return deadlines retained.
Checked distance weight0 and0.4, hand pose/velocity joins and deterministic seek.
At weight0.4 displayed hand accumulated travel462.47deg ->258.21deg; this measures
total travel, not a shortest-path guarantee. All19 cutoff checks pass. Actual
renderer body/sword contact sheet reviewed; live user playback not controlled.
Test: Labs/BodyflipLab/verify-sword-return-inertia.mjs, run with captured fixture
../../Saved/BodyflipLab/trimmed-sword-input.json; baseline mode uses the pre-attempt
core/jump-attack snapshots in Saved/BodyflipLab/trimmed-sword-before-*.js.

**Trimmed sword return attempt REVERTED, November 2:**
User rejected changing the established inertia. Restored core.js and jump-attack.js
exactly to their pre-attempt state: no added rotation braking or return-target
projection. Keep existing return inertia, duration, compensation and tuning.
Earlier reduced-travel test/render are evidence of the rejected attempt only.
Superseded by the scoped hand-coordinate correction immediately above.

Jump window pin (November 2, local): Pin button appended beside Delete.
Pinned window stays open on outside clicks, More options and Escape; unpinning
restores normal dismissal. Other jump markers still select normally; deleting
the selected jump hides its editor. Pin is session UI state and does not rebuild
motion or change saved jump tuning. Existing editor checks pass (89 total,
including pin/dismissal behavior); browser layout not verified. Refresh lab.

**November 2 agonising exemption / perturbed radii — VERIFIED RUNNING.**
User requested no failure termination for agonising and agonising_idle (all cohorts)
and double all sphere radii for perturbed rows. Normal10s TIME reset retained;
no failure penalty on exempt rows, other failures still-100. All enabled spheres
including head and pelvis doubled once forcohorts1/2/3; vanilla unchanged except
agonising exemption. Passive limbs remain excluded. Pelvis40->80cm, recenter70
unchanged; limb27->54cm, limp54->108cm, limp-idle hands20->40cm. Row metadata
removes exempt spheres and carries actual radii/readiness into replayer.
Full2048 GPU preflight passed36864 boundaries,3 resumed finite updates,40 replay
rows and independent MSE/rewards; no loss/strength/motion/settings changes.
Latest15026_final locally/persistently verified. Same retained podvpv6saq7zyooak;
new20261102_033522_uefn_slowloco_disabled_curriculum_agonising_free_2048,
trainer1688/guard1689,bridge49672/dashboard50748. Live15027->15037 verified,
985530368samples; optimizer/normalizer restored.40 live replay rows checked,
agonising variants never FAIL and have no sphere points; all other per-row radii
match requested multiplier. Independent MSE/reward and persistent backup readback
passed. Until-stopped released.8021 local replay and8035 new run verified. Source9934febb95bc62346c63a9d832df9cf5c16980effe9a4aea03e3014884f15e49.
Helper Labs/RoboticMotionAE/deploy_agonising_radii.py; receipts under
Saved/MimicKitSlowLoco/agonising-radii-deploy-20261102. Previous curriculum section
is historical run state; current source/settings above take precedence.

**November 2 disabled-limb curriculum — VERIFIED RUNNING.**
Replacement vpv6saq7zyooak, Secure RTX4000Ada at$0.28/h. Original5xs589fdlcb7nr
remains EXITED with disk preserved. No duplicate GPU. Resumed14765_final into
20261102_024758_uefn_slowloco_disabled_curriculum_2048, trainer775/guard776.
Full2048 resumed preflight passed3 finite PPO updates,30720 termination boundary
cases, dead torque0, vanilla equivalence and independent40-row replay reconstruction.
Live14766->14776 /968425472 samples verified; optimizer restored, arm flag scales1,
critic grad_clip100. Live independent raw MSE/reward reconstruction passed all40rows;
persistent checkpoint readback SHA verified. Setup deadline released to until-stopped.
Source87706a8ef5d045c4a3dee85dc000e8534bce1bc54dfbd89cdbe8ac1132c8f8dc.
Bridge61248/dashboard59276;8021 and8035 HTTP200; TensorBoard includes02-47-58;
local replay40rows has vanilla/1/2/3 labels, disabled limbs and speed percentages.
Mixed crawl speeds60%/50% confirmed. Availability heartbeat completed and removed.
Latest pre-change14765_final remains local+persistently SHA verified
(6a958d83df400cdce0c06a7d8df9f1a6b922424e2b2f23e829aba871aa76a957).

First attempt20261102_015009 failed on update14766 with nonfinite parameters;
existing failure_stop guard stopped the original pod. No corrupted checkpoint
promoted. Old fresh-agent200-world preflight missed restored optimization.
CPU restored-critic stress test on new initial poses reproduced overflow with
unclipped SGD; gradient norm clipping100 kept32 updates finite. Prepared repair:
critic grad_clip100, all optimizer state/LR retained; only previously constant
arm-enabled observation channels154/155 std raised to1 (mean1 unchanged), keeping
all vanilla inputs bit-identical. This repair is now validated by resumed preflight and advancing live updates.
New preflight requires actual14765, full2048 worlds,3 finite resumed PPO updates,
physics/masks/termination checks and independent40-row replay reconstruction.
Setup failure guards defer stopping only inside the bounded20-minute setup
window; deadline guard remains active. Four actual exit-guard branch tests passed.

Approved curriculum:10% vanilla and30% each total1/2/3 disabled limbs (limp's
original passive leg counts). Preserve active limp leg and >=1 crawl arm. Random
joint-limit-valid disabled-chain initial poses; no torque, four-MSE loss or limb
sphere termination on dead chains. Preserve mass/collisions. Failure-100 applies
to all perturbed failures. Crawl speed uses slower factor: oneleg.9, onearm.6,
bothlegs.5; arm+leg.6 and arm+bothlegs.5. Scale clocks/reference velocities/phase
and COM bands together.160 observations with actual four enabled flags. Replayer
40 rows =10motions x vanilla/1/2/3, labels include disabled limbs and playback rate.
Other losses/strength/motion assets retained. Initializer bank6016 states passed
joint/floor/collision checks; original fresh-agent masks/replay checks passed.

Helpers: Labs/RoboticMotionAE/replace_disabled_pod.py allocate (reconciles original,
Community then Secure, no duplicates, immediate20min watchdog); deploy_slow_policy.py
setup; replace_disabled_pod.py upload_resume; deploy_disabled_curriculum.py
preflight,stage,launch,audit,verify. Deployment receipts and CPU audits under
Saved/MimicKitSlowLoco/disabled-curriculum-deploy-20261102. Full resumed GPU
preflight must pass before production launch. Verify2 advancing statuses, correct
model/normalizer/replay, independent persistent backup before until-stopped release.
Do not use failed launch or old200-world report as verification. No desktop control.



**Attack end-frame dropdown, November 2 (current, local):**
More options now contains a collapsible Attack end frames section with separate
source-frame controls for all 19 attacks, including both throws. This replaces
the single Sweep end frame field. Blank uses existing ending timing; explicit
cuts are clamped between Hit/Release and the full clip end. Saved attackEndFrames
map applies to manual and timeline attacks. Existing sweep cutoff migrates;
throw +frames settings remain the defaults when no per-attack override is set.
Source playback rate and release timing are unchanged. The selected frame starts
the existing return, seeded from that pose and velocity. Play intent is preserved.
Actual-app tests pass for all 19 cutoff/save/return cases and independent reset;
eight sweep entry/cut continuity cases also pass. Tests intercept state writes;
no live state edits, native changes or push. Refresh the lab to load the controls.
Tests: verify-attack-cuts.mjs and verify-sweep-cut.mjs in Labs/BodyflipLab.
UI follow-up: each attack now occupies its own row with a right-aligned input;
explicit grid/flex styles fix the inline labels wrapping into neighbouring fields.
Number inputs now contain the effective default instead of an empty value with
a placeholder, so native arrow steps start there (Slash RU 24 to 23, not 18).
Clearing restores the default without storing an override.

**Sweep end-frame option, November 2 (superseded UI; behavior retained):**
User explicitly accepted the sweep including its whole-body aim after the inversion
explanation. Preserve that behavior. Added Sweep end frame at the bottom of More
options, using source-animation frames17 (Hit) through35 (original End), default35.
Global saved sweepKickEndFrame applies to timeline and manual sweep kicks; other
kicks retain full clips. Entry and native playback rate stay unchanged. Recording
ends at the selected frame and derives return pose/velocity from that frame,
using existing Attack return/distance weight. Preview cache includes the cut.
Early cuts allow aim recovery through the return so cutting at Hit cannot snap
steering to zero; it always completes by the actual return deadline. Timeline
source-frame diagnostics stop at the selected frame. Playback intent retained.
Eight actual-app checks pass across full/direct entry and cuts35/24/18/17:
aim at Hit, continuous cut/return, save/sanitize and Play/pause preservation.
Existing full-turn continuity and404 normal-kick comparisons pass. No live state
writes, native work or push. Refresh existing lab; default35 preserves full clip.
Test: Labs/BodyflipLab/verify-sweep-cut.mjs.

**Sweep inversion diagnosed, November 1 (subsequently accepted November 2):**
User reports upside-down head with forward target after last correction.
Actual saved frame1.116667s: source pelvis tilt52.77deg, compensated57.46deg,
aimed126.26deg. At Hit, compensated foot ray points59.06deg below horizontal;
target ray is20.52deg above. Rigid aim pitches the complete body79.58deg
(and yaws48.50deg), producing inversion. The whole-body aiming rule preserves
limb spacing but has no posture preference and allows an upside-down result.
User subsequently explicitly accepted this behavior on November 2; preserve it.
No production changes made in this diagnosis. Read-only captured setup:
Saved/BodyflipLab/SweepFollowup/inverted-input.json; audit-sweep-inversion.mjs.

**Bodyflip sweep follow-up, November 1 (current, local):**
User reported compensation making the leg traverse the arms and a whole-body
hitch at timelineF100-105. Previous strike-only world protection caused the
first issue: the body/arms counter-rotated into the fixed leg. Sweep balance
now rotates the complete authored pose together, preserving all local joint
rotations and arm-to-leg spacing; final aim uses the compensated foot direction.
This supersedes the prior world-fixed-strike contract for sweeps only. Normal
KickL/R retain their accepted protection/balance path.
The hitch originated in recording interpolation, before balance or aim. F0-relative
unwrapped rotation vectors become singular near the completed360deg turn; at
sourceF32.5 the interpolator took a13.75deg detour between nearby recorded poses.
Circular clips now use neighbouring quaternion SQUAD with continuous angular
velocity; recorded integer-frame orientations are preserved (<2.4e-15rad).
Current displayed pelvis increments F100-105:1.598,1.251,.955,.731,.571,.460deg,
progressively slowing. Source hitch before was13.75/13.42deg atF102/103.
Six actual-app saved-target/aim-off/comp-off/twist+/twist-/flip cases pass;
arm-leg spacing error<8e-16m, authored local articulation error<9e-16rad,
final direction error<7e-16.404 normal-kick comparisons match previous code
within1.6e-16. Current collider sheet reviewed; user live playback not controlled.
Regression: verify-sweep-continuity.mjs uses the before-source snapshots under
Saved/BodyflipLab/SweepFollowup; input.json is a read-only live-state capture.
verify-sweep-current.mjs now checks local strike and arm-leg spacing, rather
than requiring the rejected world-fixed striking leg. Source FBX unchanged.
No live writes, native work or push. Refresh the lab for review.

**Bodyflip sweep correction, November 1 (current, local):**
User approved fixing sweep while keeping compensation off the striking motion
and preserving normal kicks. Circular kicks now use the existing common-body
momentum solver with the strike chain protected, instead of independently
folding spine/shoulders/free leg. Authored full body turn retained; only added
balance fades over Hit-to-End. Motion compensation checkbox works for sweep.
Sweep aiming rotates the complete compensated pose about COM using heading /
elevation, preserving all local joints. Steering fades over native follow-through
(Hit-to-End), so it no longer holds a hip offset until the final short return.
Spinning sweep aims the predicted compensated result as an explicit rigid command;
no iterative counter-rotation cancels that turn. It updates carrier/velocity and
momentum metadata; this prescribed aim is external angular drive, not passive
conservation. Normal kick/slash/throw steering stays on its accepted path.
Sweep entry/return uses the projected base that actually takes over afterward,
removing the reported2.494/1.462deg knee jumps at the final handoff.
Six offline actual-app cases pass: saved scene, aim off, compensation off, both
200deg/s twist signs and120deg/s flip. Strike orientation error<4.1e-16rad;
free joint and aim articulation errors<1e-15rad; hit direction error<5e-16.
End-handoff difference across +/-1e-7s is~1.07e-6rad (moving fall animation),
not the previous2.5deg discontinuity.414 normal KickL/R direct/full-entry
samples match checkpoint b445835d within1.6e-16. Five existing pose+slash /
kick/throw app regressions pass; playback/save checks pass. Offline actual-mesh
source/compensated/aimed sheet reviewed; live playback still needs user review.
Evidence: verify-sweep-current.mjs and Saved/BodyflipLab/SweepCurrent/
{verification.json,comparison-current.png,audit.json}. No live state writes,
Unreal/native edits or new push. Refresh existing lab to load the correction.

**Bodyflip sweep-kick audit, November 1 (analysis only):**
Accepted checkpoint pushed as b445835d8157aa8b21b913b2c75dc73c5be6d193 to
origin/codex/standalone-sim; remote HEAD matched;9591-file recovery manifest
verified. Commit includes only Bodyflip work/current saved-profile and scoped
journal handoff, excluding other tasks. Current live setup copied read-only.
Sweep: Space, Direct to Armed on, no active spin or pose; Hit1.183333s,
native End1.783333s, shared return End2.000159s. Older kick balance changes
local free hip49.70deg, shoulder33.77deg and spine01 23.51deg at Hit. Static
aiming changes only strike hip substantially:43.26deg at Hit,47.70deg at
sourceF32,48.10deg at End; steering holds until End then releases in0.217s.
At returnEnd, raw kick stays continuous but final projected knees jump
2.494deg left/1.462deg right as attackFree drops and resting projection resumes.
No sweep motion code changed. Smaller jitter not yet isolated to a unique cause.
Plan: preserve authored whole sweep/body turn, replace competing joint balance
with shared carrier compensation, steer a coherent sweep plane, and use one
continuous return to the same projected base used after handoff. Recheck target
at Hit plus full limb/velocity trajectory, including no-aim/source comparisons.
Offline harness: Labs/BodyflipLab/audit-sweep-current.mjs; stage samples and
measurements: Saved/BodyflipLab/SweepCurrent/audit.json. No live writes/GUI/native
work; audit was local after checkpoint. User subsequently approved correction above.

**Bodyflip accepted checkpoint, November 1:** User requested push before the sweep-kick audit. Includes current authored poses/shared transition controls, Keep/enable/variant options, twist aiming, Space fall option and saved-profile snapshot. Focused pose/app/attack checks passed. Unrelated native/assets/tasks excluded.

**Bodyflip authored poses, November 1 (current, local):**
Added shared Ease in / Exponent / Ease out sliders directly below Blend distance
weight. Defaults0.15 /2 /0.5 give a quicker start and softer finish. Independent
start/end easing shapes time; Exponent1 keeps common joint progress and higher
values accelerate joints with farther target rotations relative to nearer ones.
Distances are measured per local joint once at entry (including requested spin
variant); the analytic curve slows into the target and finishes at the existing
distance-weighted duration. Applies to entering/changing/clearing poses, including
the variant deformation; Keep retains the ongoing curve. Pelvis uses only the
shared time envelope. No attack-return or spin-response damping changes.
Entry/clear checks cover45/135deg joints, exponents1/2/3, monotonic motion,
exact arrival, smooth finish, seeking; authored-pose/timing/spin checks pass.
Actual-app slider/save/playback and five pose+attack cases pass, as do Keep
continuity checks. No live state writes, native work or push; refresh the lab.

Pose in, Blend distance weight, Full response and Spin response are now shared
across all poses. Only Wobble speed/amplitude remain per pose; the Wobble pose
selector sits below the shared sliders. Legacy scenes migrate the previously
selected pose's displayed values to shared settings once; subsequent selector
changes only edit wobble. Entry uses shared Pose in; No pose Out stays per marker.
Source/timing/spin and actual-app controls/save/mode/playback checks pass.
No live state writes or push; refresh the lab.

Added Invert pose variants at the bottom of More options, default off. Swaps
the positive/negative extra frames for every pose (including timing measurement
and Keep), without reversing spin commands. Serialized global setting; rebuild
retains Play/pause intent. Neutral frame and wobble tuning retained.

Added Keep pose to jump markers. It continues the active pose/wobble/filter
without restarting and follows changed spin commands; no active pose stays
unposed. Contact re-entry retains incoming pose choice and wobble clock.
Small checked-by-default enable checkbox sits below each jump marker. Off skips
all of that jump's push/spin/pose/attack planning but preserves its settings;
re-enable restores them. Editor82 and Keep/disabled-sequence checks pass;
actual-app checkbox/playback and pose+attack regression checks pass. No live
state writes, native work or push. Refresh lab to load both controls.

Zero-wobble pelvis drift corrected after user report: Snatch had zero spin,
no active physical balance, but inherited2.107deg of idle pelvis sway. A held
pose now retains its incoming pelvis basis, blending out idle sway during entry.
Source FBX pelvis remains excluded; commanded flip/twist and physical carrier
rotation remain. No pose restores the underlying animated pelvis via a relative
offset, including after body turns. Four-pose regression: held rotation drift
<2e-16rad, clear/flip/twist/seek checks pass. User saved settings unchanged.

Replaced placeholders with user recovery FBXs: Lara, Snatch, Ball and Ninja,
three frames each, keeping pose1..pose4 saved IDs. Frame0 neutral; positive /
negative spin uses Lara1/2 and others2/1, chosen by authored limb trailing.
Source SHA256 recorded; FBXs unchanged. **Corrected after user review:** all
three frames now affect only joints below the current pelvis. Source pelvis/root
orientation is excluded; the pose follows the pelvis through flips. Earlier
implementation incorrectly copied the authored pelvis rotation.

Pose entry/clear now uses the attack-return angular-distance duration rule,
with shared **Blend distance weight** on the left (default1, range0..1).
Duration = In/Out * (1-weight + weight*angle/90deg), minimum1/60s, measured
once at the start from the largest below-pelvis orientation difference. Entry
includes the requested spin variant at incoming measured velocity and initial
wobble. No pose uses the shared weight; attack tuning is independent.
24 distance/entry/exit checks and whole-body-frame invariance checks pass.
Full response tooltip now explains the speed threshold and halfway example.
Pose in is now an always-enabled left slider directly above Blend distance
weight, editing the shared base entry time across all poses and markers. Removed the old In
field from More options; No pose Out stays there. Playback intent retained.
Pose in slider maximum is now0.6s for finer dragging; existing saved tuning
and angular-distance scaling are retained.

Shared Full response speed and Spin response damping time, plus per-pose
Wobble speed and Wobble amplitude sit directly below left return sliders, above Foot/Air flip,
per the user's explicit placement. Defaults360deg/s,0.15s,1x,10%. Wobble adds
mean-relative falling-loop motion only to limbs. Spin frames use measured world
angular velocity projected on current pelvis up, with a damped response coupled
to existing momentum balance. Preserve authored joint ranges through recoil;
mask pose response off attack joints and restore it during the shared return.
Poses now hold indefinitely until a later jump selects another pose or No pose.
No pose blends to the ongoing unposed animation using that marker's Out time,
keeping the current pelvis frame. Removed obsolete Hold input; saved poseHold
is ignored. In applies to pose entry; Out is enabled for No pose. Wobble tuning
remains independent per pose; slider rebuild retains playback intent.

Source/math/sign/wobble/slider-extreme/grounded-jump checks pass. Pose layer
retains the incoming pelvis frame upright, sideways and upside-down, holds through
100s, and changing/clearing markers remain continuous while flipping. Clearing
restores the moving projected base within3e-15rad. Jump editor76 checks pass.
Five actual-app pose+attack cases cover slash, kick, Big throw and weighted
return, checking target direction, authored arms/head and phase continuity. Existing
Space-fall, throw/playback and157 duration-return checks pass. Source collider
sheet reviewed offline; live playback not reviewed. Legacy jump-motion test
fails its delay assertion on both HEAD and current code, before pose checks.
Legacy landing harness also fails exact contact/NN-seed matching on current
and HEAD; landing/NN code was not changed in this correction.
No live-state/Unreal/native edits or push. Refresh lab. Details and options:
[Labs/BodyflipLab/README.md](Labs/BodyflipLab/README.md#authored-airborne-poses---november-1-current-local).

**Bodyflip Space falling animation, November 1 (current, local):**
User accepted twist + attack after switching OFF 3D momentum; that resolves the
reported residual tilt for the selected axis-controlled behavior. No physics
code or saved setting was changed during the tilt audit. Its seven offline
comparisons distinguish full-3D residual body rotation from the ordinary attack
return; the earlier joint-only return check did not establish global uprightness.

Added **Falling animation in Space** at the bottom of More options, default off
and disabled in other modes. Space previously used only the idle loop as its
base. On blends into the existing Loop_Fall at the first marker (time zero if
there are none), using Jump blend. Attacks return to that ongoing animation.
Only local limb/spine rotations change; root/pelvis base, gravity and push rules
remain. Actual-app checkbox/rebuild/playback test passes: final aimed direction
error2.85e-10, return articulation error<4e-15rad, no added root drift, off
restores the original pose exactly. No live state writes, native/Unreal work or
push. Reload the lab, then enable the checkbox. Details: Bodyflip README.

**Bodyflip twist + melee aim, November 1 (local; accepted with 3D momentum off):**
The saved SlashL /200deg/s twist now aligns the final contact direction at Hit:
147deg error before,0.000034deg after. User scope is direction only. Predict
body orientation at Hit, reuse air-attack heading/elevation, then fit those two
angles against the actual compensated trajectory. No separate arm correction.
The old predictor fitted a different rotation order and balance cancelled its
whole-body heading. Deliberate aim heading is now an explicit angular command,
like existing flip/twist; internal articulation still receives compensation.
This changes total world angular momentum during the aiming turn; it is NOT
passive torque-free conservation. Heading stays continuous across180deg.
12 actual-app cases pass (both twist signs, flips, combined motion, slashL/R,
jab, pike, kick, zero-spin); arms/head and shared return retained. Accepted
zero-spin pose matches exactly; throw/playback and focused return checks pass.
Offline collider contact sheet reviewed; user subsequently accepted axis-only playback.
Preparation is cached,7-16 trajectory evaluations; no native runtime performance
claim. Live settings, Unreal and native files unchanged. No commit/push yet.
See [current implementation and verification](Labs/BodyflipLab/README.md#twist-and-melee-aim---november-1-local).

**Bodyflip target-point spear aim, November 1 (accepted for push):**
User confirmed the targeting works and requested a push.
Accepted state was pushed first as5b2a2da6 on origin/codex/standalone-sim;
remote HEAD matched and recovery manifest verified. Current spear default now
fits the actual release shaft/origin to the target, fitting heading/elevation
through spine01-05. Explicit throwDirection and small
throw azimuth keep their earlier behavior. For spinning bodies, fit against the
complete momentum-compensated trajectory; no projectile velocity redirect.
Full-charge spin prediction also avoids recursive carrier-velocity reads.
396 target cases,4 physical cases and actual-app spin/retarget/playback pass.
Matched checkpoint poses for slash/jab/kick/small/explicit-ray throws:15,860 bone
comparisons, zero position difference. FinalNoAim16,918 checks and157 return
checks pass. Agent validation was offline CLI/DOM; user acceptance followed.
No live state writes, Unreal changes or native port. See Labs/BodyflipLab/THROWS.md.

## November 1 accepted Bodyflip throw checkpoint

Accepted standalone motion before target-point aiming experiments: FinalNoAim
throw sources, shared spine transfer/return, distance-weighted return duration,
attack joint-limit exemption and playback intent preservation. Includes current
saved-profile.json (snapshot of live state; live state itself is not changed),
final source exports/import tools and focused checks. 16,918 final-source,
157 return checks and the actual-app playback/retarget harness pass.
Unreal, native packaging and other tasks are outside this checkpoint.

**Bodyflip current status, November 1:** option edits now retain playback intent.
Temporary slider/loading pauses no longer cancel Play. The latest successful
rebuild resumes if it was running; paused stays paused; explicit Pause, seek,
failure or hiding the lab cancels resume. Rapid/same-key edits, motion/loop/attack
selection and mode restoration are covered. Actual app race checks, generation
invalidation,16 refresh checks and30 trim/seek checks pass. No GUI or live writes.
Details: Labs/BodyflipLab/README.md.

Current throw behavior: corrected throw coordinate conversion
and removed resting-limit projection during authored attacks/return. User clarified
that root is only a coordinate frame and attacks may exceed limits. Normalize
source pelvis into the initial root frame BEFORE interpolation, then distribute
through spine01-05. Preserve authored arms/head; shared target tracker does not
re-clamp or speed-limit attack poses. Duration-based return restores
the base pose before normal projection resumes. Saved Big throw finalF34 head/
launch3.98deg (source3.98), F39 14.81deg (source14.71), previously60.92deg.
Matched-frame final head/hand and head/chest errors below1e-6deg; arbitrary root
reframing including subframes changes articulation by<3e-14deg. Source clips,
live state, Unreal and native package unchanged. Reload lab. Offline actual-app
checks only; no GUI/raster verification. See Labs/BodyflipLab/THROWS.md.

Current return controls below Fall cap: **Attack return (seconds)** is an
always-enabled GLOBAL slider directly above **Return distance weight**. Removed
its binding to marker selection (the cause of the greyed-out control). Editing
sets attackReturnDuration for timeline throws/melee/kicks and manual attacks.
Until edited, null preserves saved per-event attackOut and the manual0.45s tail;
the UI displays the existing event/default duration. Readout updates during drag;
release rebuilds playback using the existing global-control handler. No live saved
state was overwritten. Actual-app no-selection slider, throw and manual duration
checks pass;157 focused return checks pass. Distance weight remains0..1/default0.
Inactive lerp/snap/exponent sliders remain beneath them.
At return start, measure the largest shortest-arc bone orientation difference
from the ongoing base pose (excluding root, including attack aim). Choose once:
duration = baseReturnSeconds * (1-weight + weight*angle/90deg), minimum1/60s. Weight0
returns the unchanged existing track; weight1 is linear distance scaling.
The existing C.transition runs over that fixed duration, retaining incoming
velocity and the moving base. Body and aim share the selected duration. Source
entry/strike/follow-through before End are unchanged. Without a global duration override, manual attacks use0.45s and scheduled
attacks retain saved Attack Out. Big/Small markers
remain16/34 source frames. Target/aim edits rebuild plans when weight>0.
Measurement is from the attack track's aimed End pose, before later physical
spin/contact processing; it is not a live physics feedback controller.
153 duration/continuity/seek/source checks,16918 FinalNoAim/shared checks,75
editor checks and actual-app weight1 playback/retarget checks pass. Tests use an
offline DOM/GL sink, no raster inspection. No live state writes or native build.
Reload lab. Details: Labs/BodyflipLab/THROWS.md.

**Bodyflip Big throw source end F50, November 1 (latest):** user identified the
long comeback in the base clip. Big throw now supplies source phases.end50 to
the shared jump-attack path, retaining its fast direct-to-Armed entry. Shared
end time is hit/release time + (sourceEnd-sourceHit)/playbackFPS, not sceneF50.
At default60fps, F34 Release ->F50 End is16/60s, followed by normal Attack out.
Small and slash endpoints are unchanged; original full FinalNoAim/reference
clips remain intact. Captured throw app replay: Release0.60s, End0.8667s,
returnEnd1.1167s with zero residual aim twist; release packet unchanged.
16,918 final-source/shared-return/timing checks include varying entry duration,
delay and0.5/1/2x speeds; actual-app checks and76 jump-track checks pass. No
live settings/loop edits, GUI or native build. Reload. Details THROWS.md.

**Bodyflip shared slash/throw return restored, November 1 (latest):** user
rejected throw-specific recovery. Removed the initialLaunch return timing branch
from attack-aim.js; both now hold aim through clip End and fade over the existing
Attack out to returnEnd. Throw body/compensation already delegates to jump-attack;
no second body-return implementation added. FinalNoAim source/timing/launch kept.
16,882 checks include both throws versus the shared slash path over61 samples,
pose/quaternion equality and identical aim envelope;27 shared pelvis-return
checks and actual-app retarget/reference checks pass. Captured throw-scene app
replay: aim1 at2.20s,0.5 at2.325s,0 at2.45s; residual pose angle1.1e-16rad.
Loop cut is important: current trimOut2.0833s is before that return starts.
Do not claim playback inside that loop shows the return. User currently switched
live saved attack to slashL; replay used the preserved throw input snapshot.
No live state/trim edits, GUI or native build. Reload source. THROWS.md has details.

**Bodyflip FinalNoAim import and return, November 1 (latest):** user explicitly
identified Exports/Throws/FinalNoAim/HANDOFF.md. Previous Bodyflip source was NOT
that bake. Full-charge Big/Small now sample its clips.json directly, no repeated
hand/forearm/source shaping or source aim. Original60fps preserved; removed1.8x
animation retiming. Manifest launch velocity/spin transported by held orientation
with carrier translation; explicit handoff supersedes previous hand-derivative
launch contract. Geometry/binds match ThrowLab objects.json. Partial Small retains
legacy procedural source (the supplied bake is100% only). New importer records
SHA256 for clips/manifest;10,416 exact-frame/timing/launch/return checks pass.
Aim turn now fades from Release to authored clip End, instead of staying full
through source recovery. Actual app replay has zero remaining aim pose rotation
at End (<5e-16rad), shaft error0deg and travel2.13deg off goal (source manifest
already2.08deg shaft/travel difference). App retarget/reference checks pass.
No GUI/live state edits/native rebuild. Reload lab. Details Labs/BodyflipLab/THROWS.md.

**Final unaimed throws baked, November 1:** user requested both final animations
for another lab, explicitly selected100% Small. Outputs:
Exports/Throws/FinalNoAim/{BigThrow_Final_NoAim,SmallThrow_Final_NoAim}.fbx,
plus clips.json for26 lab bones. Both Aim off; current saved pose edits baked,
full89-bone source hierarchy retained. Big131/Small69 samples at60fps; releaseF34.
FBX reimport all-bone/frame checks pass, max position error2.97e-7m. Small100%
has no saved keys, so matches source motion; partial-charge shaping remains
procedural. Grip/scale/launch physics in manifest, not reapplied pose edits or
animation retiming. Source/live-state/Unreal assets unchanged; no editor/build.
[Short receiving-agent handoff](Exports/Throws/FinalNoAim/HANDOFF.md).

**Bodyflip rearward heading correction, November 1 (latest, partial):** user
authorized fixing backward-facing/downward launch, explicitly forbids declaring
success on unrelated fixtures. Replaced shortest-arc throw steering with world
heading then elevation. Additive throw spine aim is no longer clipped by the
standalone rest22deg spine cones; source projection and other joints remain,
native profiles retain limits. Actual saved-scene app replay now yields shaft
error0deg and vertical release+2.549m/s (before44.15deg/-16.969m/s). Heading
turn-176.79deg, elevation-5.95deg. Offline before/after pose plot inspected.
NOT fully fixed: velocity is still42.94deg from requested direction; unaimed
adapted motion already has47.64deg hand-velocity/shaft mismatch. No redirected
projectile velocity was added.951 direction checks, six motion cases/2,000
transfer checks, actual app checks and four shared physical cases pass. No GUI,
live state edits or native build. Details Labs/BodyflipLab/THROWS.md;
Saved/BodyflipLab/ThrowSceneAudit/{scene,results}.json and release-comparison.png.

**Bodyflip actual saved throw failure, November 1 (latest investigation):** user
rejected the displayed result again. Read-only actual-app replay of state.json
(Space, big throw, target[-.83778,2.43491,-3.27299], compensation1, transfer on)
reproduces release shaft44.15deg and velocity81.51deg off the fixed world goal.
Aim solution residual0.75163; correction quaternion[.80441,.57225,-.15955,.00254]
is nearly180deg around a tilted axis. The newly introduced shortest-arc rule
can fold the torso for a rearward target; final22deg spine limits also constrain
the correction. Earlier app tests exercised different targets and do not validate
this scene. No further production change in this investigation. Do not claim
the throw fixed. Offline replay: Labs/BodyflipLab/audit-throw-scene.mjs;
Saved/BodyflipLab/ThrowSceneAudit/before.json. No GUI/live scene writes.

**Bodyflip continuous throw spine steering, November 1 (latest, local):** user
reiterated original-to-authored-direction rotation through the spine, preserving
relative arms. Throw aim no longer converts its endpoint into projected joint
coordinate offsets and replays them on every pose. It retains one quaternion,
smoothly blends it over entry/release/return, and applies cumulative20/40/60/80/100%
world rotations over spine_01-05. Spear uses shortest-arc direction rotation,
avoiding an additional heading/elevation roll; Small remains yaw-only. Existing
pelvis-transfer option and motion compensation remain. Final legal projection
and endpoint calibration remain; no arm offsets are added by aim.951 direction/
intermediate-arm checks, six motion cases/2,000 transfer checks, actual app
release/retarget/reference toggle and four shared physical melee cases pass.
No raster verification or claim that the separate hand/shaft velocity mismatch
is eliminated. Source-only; reload. Details: Labs/BodyflipLab/THROWS.md.

**Bodyflip spear launch/reference repair, November 1 (current, local):** same
Throw Lab `big throw.fbx`, with its approved grip/key edits. Previous correction
dropped the profile's 1.8x speed and axial spin, introducing transverse hand
angular velocity. Restored configured shaft-axis spin; apply speedScale to
animation timing, keeping linear release velocity derived from the final hand
trajectory. Current-settings fixed-base audit: 9.83 -> 17.66m/s (Throw Lab18.34),
initial transverse spin13.18 -> 0rad/s; first25ms shaft turn16.30 -> 1.73deg.
Remaining aerodynamic turning is real: hand travel is still24.75deg from shaft;
this does not prove full alignment or eliminate all in-flight turning.
Vanilla checkbox now shows **THROW LAB REFERENCE** for both throws: full-body
approved100% source plus held/released weapon and original target/floor. Cached
reference flight adds no runtime physics world.49,864 source/reference checks,
app render/toggle/retarget test, six motion cases,60 drift and130 direction checks
pass. No GUI/raster, live state writes, Unreal/native build or tuning edits.
Reload lab. Details: Labs/BodyflipLab/THROWS.md; ThrowLaunchAudit evidence.

**Bodyflip authored throw direction, November 1 (current, local):** user
clarified spine-only steering with unchanged relative arms, then replaced the
moving-point aim objective with an authored absolute world direction. Optional
per-event `throwDirection: [x,y,z]` is normalized and persisted. Without it,
the lab uses target minus pelvis position at `segment.jumpStart` (jump frame 0).
The frozen origin is captured from world poses, before physical aim prediction;
spine corrections and subsequent body drift/spin cannot change the goal. Spear
uses the vector; Small throw its horizontal bearing, preserving the arc.
Target edits reauthor the default ray from that same frame-zero origin; explicit
vectors ignore target edits. Viewport guide displays the frozen world ray.
130 direction/relative-arm checks, six motion cases, app target-edit/release
checks, 33 scene checks and four shared physical cases pass. Source-only change;
reload lab. No GUI, saved-state overwrite, Unreal/native package or arm edits.
Earlier pending wrist/forearm question is superseded, not an outstanding choice.
Details: Labs/BodyflipLab/THROWS.md; Saved/BodyflipLab/ThrowDirection/results.json.

**Bodyflip throw motion, November 1 (historical; question superseded below):**
User rejected the saved-impulse approach. Throws now use the shared upper-body
attack path: optional equal transfer over spine_01-05, legal arm entry, motion
compensation, soft legs/amount and recovery. Imported Throw Lab target aiming
is disabled. Bodyflip throw aim uses upper-chain heading/elevation only (bomb
heading only), with no free roll or pelvis/whole-body tilt fallback. Release
linear/angular velocity comes from the final held object's pre-release motion;
no saved impulse/spin is added. Throw speed changes animation rate; zero disables
that throw. No live state edits, GUI use, Unreal work or native repackaging.
Checks: six compensation/aim cases, 2,000 spine shares, 60 drift/rate checks,
app release-velocity checks, source parity and shared melee physics pass.
Remaining: adapted spear shaft is ~48deg off hand-driven travel; original source
is already ~17deg, increased by retargeting/arm projection. Asked whether to
adjust forearm/wrist motion or preserve source pose; superseded by the newer
spine-only, authored-direction instruction above.
Do not restore the saved impulse or claim complete throw acceptance. Evidence:
Saved/BodyflipLab/ThrowMotion/results.json; Labs/BodyflipLab/THROWS.md.

**Bodyflip throw release aiming, October 31 (rejected/superseded):** Big throw now
aims the spear shaft from its geometry origin at Release. Small throw solves
world yaw only so launch stays in the target's vertical plane and retains its
upward arc; target height cannot flatten it. Replaced attached-hand/source
derivative subtraction (false lateral impulse from retargeting/projection) with
body COM translation plus pelvis angular transport. Imported throw impulse,
charge/speed, gravity and aero unchanged. 20 release cases + 12 prescribed
carrier cases, 72 direction/spin cases, 54 drift checks, app retarget checks,
49,314 source parity checks and 4 shared physical melee cases pass. Reproduced
stationary spear has 1.34cm lateral deviation at nominal target flight time;
shaft unit-vector error below 9e-9. This is not an exact ballistic-hit guarantee.
Reload lab; no live state edits, GUI, Unreal build or native repackaging.
Details/evidence: Labs/BodyflipLab/THROWS.md, Saved/BodyflipLab/ThrowAim/.

**Bodyflip target-move crash, October 31 (current, local):** fixed projectile
shape lifetime in `projectile-world.mjs`. Retargeting destroyed the released
spear's body and its scaled collider, leaving a dangling cache entry; the next
spawn failed inside WASM (reported function signature mismatch; offline replay
produced table index out of bounds). Cache now owns an explicit reference until
disposal. 36 projectile rebuilds, 6 target inputs + 6 drag-path edits in the actual
app-script harness, and 10 existing projectile checks pass. No live scene writes,
GUI use, Unreal or native package changes. Reload lab to load fix and clear the
crashed instance. Details: Labs/BodyflipLab/THROWS.md.

**Bodyflip full-strength aim, latest October31:** removed Aim percentage slider;
Aim on/off remains. Enabled timeline/manual/held/physical aiming always uses100%.
Legacy saved aimWeight is forced to1 on load/sanitize, covering older80% scenes.
Frozen KickL replay now hits3.2304cm from centre inside12cm target. Legacy migration,
33scene checks and syntax pass. Refresh loads; no saved-state overwrite, GUI use,
Unreal or native package changes. Details in Bodyflip README/full-aim.json receipt.

**Bodyflip KickL aim audit, latest October31:** user accepted distributed transfer.
Current saved Space kick misses because Aim is80%. Reproduced reported26.7526cm
surface miss; identical inputs at100% place contact3.2304cm from centre, inside
12cm target. Kick path is separate from spine transfer. No settings/source edits.
Evidence Saved/Diagnostics/BodyflipKickAim/; details in Bodyflip README.

**Bodyflip optional distributed pelvis transfer, latest October31:** unconditional
spine_01 transfer removed; default scheduled/manual attacks retain authored pelvis
and spine rotations. New More options checkbox **Spread pelvis turn across spine**
(defaultoff, last) keeps the base pelvis and distributes the attack pelvis delta
20% each over spine_01–05. Full chain recovers original upper orientation before
limits/aim. Motion compensation remains separate; user's conservation complaint
is not resolved/validated by this option. Post-Hit recovery now removes compensation
relative to authored motion, preserving its follow-through.1046 distribution and
1068 authored samples +24manual checks pass; arm-entry/arming/torso/scene checks
pass. Saved settings untouched; no GUI/native package/build/push. Refresh loads.
Details: Labs/BodyflipLab/README.md, Saved/Diagnostics/BodyflipAuthoredPelvis/.

**Bodyflip Motion compensation checkbox, October31:** appended at the end of
More options after Vanilla attack only; default on preserves previous behavior.
Off bypasses existing upper-body attack pelvis compensation (soft and rigid) for
scheduled/manual paths, retaining Amount % and Soft legs. Rechecking restores
them. Uses preserve-time regeneration and scene persistence; does not disable
aim, pelvis transfer, joint limits or separate flip balance.608 pose comparisons,
33 scene checks and syntax pass. Saved scene/native/editor unchanged. Refresh
loads the checkbox; details in Labs/BodyflipLab/README.md.

**Bodyflip vanilla inspection, latest October31:** appended More options checkbox
Vanilla attack only (default off). Displays original full-body source directly,
including pelvis/root motion, bypassing all motion corrections in the display.
Armed-aligned source clock makes current F100 slashL source F13.9364; original
pre-Armed frames and held endpoints. Display-only, persists per scene, no generation
on toggle; hides scene/debug overlays.267 focused checks +33 scene checks pass,
syntax checked, no GUI use. Saved settings/native/editor unchanged. See latest
Labs/BodyflipLab/README.md section. Refresh loads the new control.

**Bodyflip F95–F100 investigation, latest October31:** vanilla comparison and
stage audit confirm an introduced motion shape. Original pelvis turn is moved
into spine_01 (vanilla local twist~0deg); first +/-22deg clamp suppresses lead-in
until F96.2657. Active opposite-pelvis/soft-leg compensation counter-rotates that
spine to preserve upper world orientation, but a second clamp breaks preservation
from F98.9361. F100 same-input chest speed941->384deg/s; bypassing only that last
spine clamp restores941 (diagnostic, not a fix). Flip balance inactive, separate
attack-inertia solver still active. Current target changed; first audit aim-speed
numbers describe the previous target. No production/tuning/editor changes. Detailed
intent/stages/evidence in Labs/BodyflipLab/README.md and
Saved/Diagnostics/BodyflipUpper95Followup. User withdrew under1s requirement.

**Bodyflip context refresh — October 31, latest handoff.** Read the
[current lab status](Labs/BodyflipLab/README.md#context-refresh-handoff---october-31)
before resuming. Per-mode timelines are implemented and verified (33 checks):
Run retains the two jumps; Space is empty. First app reload must be Ctrl+R,
because the old Refresh button saves its stale state first. No desktop control.
The earlier slash/performance work is **unfinished, uncommitted lab-only work**:
warm generation measured2.74–3.01s, cold5.99s including3.20s landing NN; user
requires below1s. Latest aim preserves authored arm motion and fits direction,
not exact contact; earlier near-zero-contact and native-parity claims below do
not validate this version. Bounce test has an unresolved loading-velocity failure.
Native package is still the earlier891446-byte version; do not assume lab/native
parity. Detailed changes, tests, limitations, saved-scene migration and resume
steps are in the linked README. Preserve accepted flipless motion, existing
settings and other agents' dirty files. No broad cleanup, GUI use, Unreal build
or push was performed for this handoff. Latest request was documentation only.

**November 2 limp-idle hand spheres20cm — VERIFIED RUNNING.**
User requested both hand termination radii20cm only forlimpL_idle/limpR_idle.
Runtime per-row squared radii and per-motion replay metadata updated. Other
spheres, all losses/reward, targets, physics, observations, sampling and passive-leg
exclusion unchanged. Movinglimps retain54cm hands, other motions27cm. Existing
heading alignment applies; either hand beyond20cm triggers failure with existing
-100 penalty. Actual _update_done boundary test passed40cases (both hands/all10
motions at radius+/-1mm), row isolation and reset observations. Only packaged
pipeline/slow_loco_env.py changed; no motion/config/train changes.
Resumed latest final13964, locally/persistently preserved and SHA verified, into
20261102_001108_uefn_slowloco_unperturbed_2048 on SAME retained RTX4000Ada
pod5xs589fdlcb7nr. Optimizer/normalizer restored;13965→13975,915931136 samples
verified. All10 live replay rows, radii/passive masks, reconstructed MSE/rewards,
checkpoint source/controller hashes and independent persistent readback verified.
Setup deadline released to until-stopped. Trainer17691/guard17692;
bridge58812/dashboard14952. Replayer8021 serves both20cm hand spheres on the two
limp idles; TB8035 shows00-11-08 alongside previous runs. Source SHA
 ee27e07fb85701e9e193aafc08872725e1c524ca961a49c2040d162ba39e3e65.
Helper Labs/RoboticMotionAE/deploy_idle_hand20.py; receipts
Saved/MimicKitSlowLoco/idle-hand20-deploy-20261102. No desktop interaction or newGPU.

**November 1 limp idle asymmetry audit — READ ONLY, training unchanged.**
Pinned latest-at-start checkpoint13788 (persistent SHA verified) of230938.
Deterministic replay: L idle hands~4-6cm error, R~27cm; R arms account for87% of
pose loss. R pelvis~6.1cm height error/15.1deg orientation error versusL~2.4cm/
2.9deg. Eight matched starting breathing phases reproduce this: hand errorL~5.5cm,
R~26.6cm; both survive10s. Correct passive masks/205rows each/full head-strength;
zero passive torque and no sampled enabled motor saturation. Authored targets both
COM-centred with5.75cm minimum active-sole support margin and no sampled limits
violations. Instantaneously restoring arms leaves R geometric COM support margin
positive (~3.6cm), BUT dynamic arm-only target servo starting2s caused R8/8 failures
(ticks135-292), L0/8. Thus current R learned controller relies on its arm strategy;
static COM projection alone was insufficient. This does NOT prove R target is
infeasible: intervention changes momentum/proprioception and learned leg response.
A full-enabled-joint target servo from reset failed BOTH (L40-47ticks,R64-100), so
that controller cannot establish target feasibility either. Optimistic static
contact-force LP found passive-joint residuals for both targets, slightly smaller
onR, omitting joint-limit reactions; no R-specific strength shortfall established.
Confirmed learning concern: exp(-sumloss) settled reward averages0.3776 L versus
2.85e-5 R, with mean loss~1 vs11. R's arm pose error dominates this saturation.
Interpretation: coupled learned balance compensation plus very weak imitation
reward contrast; target-specific instability remains unproven. Avoid merely
raising arm MSE. Next test should address dynamically settled passive-leg/stance
reference and/or reward contrast, isolated before changing training. No source,
settings, targets, optimizer, trainer, pod or desktop changes. CPU geometry/LP
and three bounded80-world evaluation probes on SAME retained GPU only.
Artifacts/checkpoint/probe arrays/reports/plot: Saved/MimicKitSlowLoco/
idle-asymmetry-audit-20261101. Scripts audit_limp_idle_balance.py,
audit_limp_idle_statics.py,plot_limp_idle_audit.py in Labs/RoboticMotionAE.

**November 1 approved limp idles — VERIFIED RUNNING.**
User approved v2 pelvis/COM/arms preview and authorized heading-invariant idles in
training. limpL_idle/limpR_idle appended after the original eight motion IDs.
160 inputs preserved: original eight command slots remain; limpL/limpR slot +1
is hopping, -1 is corresponding idle, all other command slots zero. Limb flags
still identify the passive leg. Matching motor mask, all-four-MSE exclusion and
disabled-foot sphere exemption carry over. Active-leg velocity5x, head velocity3x,
head-height strength, failure-100 and zero pose leeways retained. New idles use
world-Z-yaw-invariant pose/articulation losses and aligned limb spheres; no
reference XY travel velocity or flat-COM loss. Their pelvis40cm world sphere
keeps XY anchor fixed between70tick recenters; authored absolute Z retained.
Ten looping motions approximately equally sampled (204/205 rows per motion,
2048 total; idle_row_fraction0.6). Original eight motion files unchanged.
80-world remote preflight passed physics, passive torque0, signed commands,
subset resets, seven yaw rotations (max loss discrepancy2.98e-7), height/tilt
sensitivity, one PPO update, failure penalty and ten replay conversions.
Resumed latest final13487 from220301, safely preserved locally and persistent,
into20261101_230938_uefn_slowloco_unperturbed_2048 on SAME retained RTX4000Ada
pod5xs589fdlcb7nr ($0.20/h). Actor/critic optimizer and normalizer restored;
prior samples883949568; advancing13488→13498 /884670464 samples verified.
Live ten-row masks, spheres, sampling, commands and all four MSEs independently
checked against actual replay values; terminal rewards reconstructed. Checkpoint
source/controller hashes and independent persistent readback SHA passed. Setup
deadline released: runs until stopped. No new GPU, user desktop or AE changes.
Trainer16310/guard16311; bridge9464/dashboard60224. Local replayer8021 serves all
10 rows and TensorBoard8035 lists23-09-38 alongside previous runs. Source SHA
3d10b0c9aa5808a87b2488a14c251489b25d719ecdea808b7a0bc617045abafc.
Helper Labs/RoboticMotionAE/deploy_limp_idles.py; complete receipts including
preflight, latest-checkpoint, live-loss/metadata, deployment and telemetry checks:
Saved/MimicKitSlowLoco/limp-idles-deploy-20261101. Approved v2 motion provenance
remains in limp-idles-preview-20261101/report.json. Older NOT DEPLOYED preview
entries below describe their historical state and are superseded by this entry.

**November 1 limp idle preview v2 — pelvis motion, centred COM, relaxed arms; NOT DEPLOYED.**
User rejected fixed pelvis/subtle movement and requested pelvis sway, centre-of-mass
alignment over active foot, and arms down like normal idle. Same frame26 limp base.
Arms now use normal unarmed idle mean joint rotations, plus its full slow movement.
Transfer normal idle's slow0.1-0.6Hz components at original amplitude, including
pelvis orientation/height, torso, head and arms. Ten-second120Hz seamless loop.
Analytic two-bone IK preserves BOTH complete foot world transforms while pelvis
moves. Solve pelvisXY each frame so physical mass-weighted COM projection is at
active sole centre. Base pelvis shifts ~4.15cm sideways forlimpL and4.24cm opposite
forlimpR, with only0.34/0.10cm forward adjustment; no lowering was needed.
Pelvis range ~1cm XY,0.36cm height, up to3.55deg angular excursion from source idle.
Active-foot centre error<1e-6mm numerically; foot FK position/rotation errors~1e-15.
No floor penetration or sampled collider overlap; joint limits checked every frame.
Largest joint step0.0477deg at120Hz, loop adjacent-velocity mismatch0.00051deg/step.
Headless software-browser Play/Space/pause/loop checks passed; front/side/3-4
screenshots visually inspected. Viewer uses proper UTF8 and versioned script URL.
Same preview URL /Saved/MimicKitSlowLoco/limp-idles-preview-20261101/; refresh toload.
v1 files preserved under v1-before-pelvis. New draft PKLs/report/continuity-check/
viewer-check and screenshots are in main preview directory. No dynamic balance
claim: this remains a kinematic authoring preview. Existing training/source/motion
package and GPU untouched; await user's approval before adding these motions.

**November 1 limpL_idle / limpR_idle — DRAFT PREVIEW, NOT DEPLOYED.**
User requested quiet one-foot idle targets derived from limp frames with breathing,
and explicitly wants to see them first. Offline drafts select frame26 (zero-based)
from each currently deployed limp: lowest COM-to-active-foot offset among quiet
support frames. Active right foot forlimpL, left forlimpR. Flatten only active
ankle (~1deg), ground full sole at1.5mm; preserve authored body/leg pose. Passive
ankle corrected minimally into real limits/floor clearance (2.61deg L,0.43deg R).
Disabled foot is not counted in support-area checks, even though its toe rests
near the floor. Pelvis and both legs remain exactly fixed across the new clips.
Breathing extracted from M_Neutral_Stand_Idle_Loop_Unarmed.pkl in final-phase-source:
dominant0.3Hz torso motion plus its second harmonic, quaternion-local upper-body
deltas,75% torso/50% head+arms, excluding root/leg sway. Seamless3.333s/120Hz loops.
Minimum COM margins inside active sole2.014cm L/1.957cm R over breathing cycle;
minimum collider floor clearance>=1mm, no collision or joint-limit violations
at sampled checks. Upper-joint frame steps<0.019deg; exact loop closure. These
are kinematic checks, not a dynamic balance/policy test.
Preview http://127.0.0.1:8863/Saved/MimicKitSlowLoco/limp-idles-preview-20261101/
shows both idles side by side, active/disabled-leg colors, support polygon and
COM marker, breathing toggle, synchronized orbit and front/side views. Play,
Space pause/resume and loop wrapping tested in a separate headless software-rendered
browser; no user's desktop/browser interaction. Paused views render on changes.
Builder Labs/RoboticMotionAE/build_limp_idles.py; viewer Labs/RoboticMotionAE/limp_idle_viewer;
QA Labs/RoboticMotionAE/check_limp_idle_preview.py. Draft PKLs, report.json,
viewer-check.json and screenshots in Saved/MimicKitSlowLoco/limp-idles-preview-20261101.
No live package, dataset, AE, one-hot, masks, run or GPU changes; existing eight-
motion run remains the current configuration. Await user review before deployment.

**November 1 remove limp pose leeways, rollback12968 — VERIFIED RUNNING.**
User reported limpR regression and requested removal of leeways plus rollback to
13000. Exact13000 unavailable; user explicitly chose nearest preserved earlier
12968 over13368. Both10cm active-leg position and15deg rotation dead zones are
removed: ordinary position and rotation-matrix MSE restored. Active thigh/shin/
foot linear and angular velocity MSE remain5x throughout both limp episodes.
Passive leg remains excluded, head velocity3x and all other motion/motor/
termination settings preserved. Precomputed powered-leg mask is now used only
for velocity weighting; obsolete rotation-leeway helper removed. Metadata records
position/rotation leeways disabled, radius0m/angle0deg.
Selected12968 validated ZIP/resume state and SHA matched local/persistent/remote.
Outgoing13662 final separately preserved locally and persistently as fallback.
Remote64-world physics/PPO/eight-replay preflight passed, including independent
position/rotation/velocity cost checks and passive masks. New run
20261101_220301_uefn_slowloco_unperturbed_2048 resumes12968 (optimizer and normalizer
restored), trainer15231/guard15232, bridge2304/dashboard14188. Verified12969->12979,
850,657,280samples,2048worlds/160inputs/eight motions256rows each. All eight live
raw replay MSE components independently reconstructed with zero allowances and
active-leg5x. Checkpoint source and live metadata verified; fresh persistent
checkpoint independently read/hash verified; until-stopped deadline restored.
Same RTX4000Ada pod5xs589fdlcb7nr retained; no allocation, desktop control or
local GPU workload. Checkpoint SCP initially timed out while old trainer ran;
resolved using matching retained pod copy, independently hash verified.
Source SHA e54a0da5bdd96fd41b9e9818dc8d6503ec549f013db8813b707b0dce9a45753f.
Helper Labs/RoboticMotionAE/deploy_activeleg_no_leeway.py; receipts
Saved/MimicKitSlowLoco/activeleg-no-leeway-deploy-20261101.

**November 1 limp active-leg velocity MSE x5 — VERIFIED RUNNING.**
User chose constant whole-active-leg weighting instead of the proposed stance-only
foot rule. Both limps: linear and angular velocity MSE x5 on active thigh, shin
and foot, at every frame (right leg onlimpL, left onlimpR). Four extra copies
of those errors plus original, preserving the15-body/component denominator.
Precomputed row/body mask; no contact/phase gating. Passive leg remains excluded;
10cm position and15deg rotation allowances, head velocity3x, all other motions,
strength and termination settings unchanged.
Remote64-world physics/PPO/eight-replay preflight passed, with independent
per-body velocity weighting, passive exclusion, static yaw and existing leeway
checks. Latest13461 final checkpoint preserved locally and on persistent storage
with SHA verification. Same retained RTX4000Ada pod5xs589fdlcb7nr; no allocation,
desktop control or local GPU workload. Resumed optimizer/normalizer into
20261101_213102_uefn_slowloco_unperturbed_2048, trainer14010/guard14011;
bridge60336/dashboard53008. Verified13462->13472,882,966,528samples,
2048worlds/160inputs/eight motions256rows each. Live raw replay position,
rotation, linear and angular losses independently reconstructed for all eight
motions; live multiplier metadata and checkpoint source hashes verified.
Persistent checkpoint independently read/hash verified; deadline released to
until-stopped. Source SHA
e1c632a1806a62803bdf703ea119ca0f691c568eba19b44ff448c68c64b922ea.
Helper Labs/RoboticMotionAE/deploy_activeleg_velocity5.py; receipts
Saved/MimicKitSlowLoco/activeleg-velocity5-deploy-20261101.
Mini-hop improvement remains to be evaluated after training; launch verification
is not evidence of learned behavioral improvement.

**November 1 limpR post-landing mini-hop audit — read-only; training unchanged.**
User requested detection from latest foot speeds. Latest complete capture13268
shows active left foot inlimpR stops at133-134 after touchdown132, then reaches
0.517m/s at135 and0.301m/s at137 before pinning at138. Reference135 is0.0174m/s.
Seven settled-cycle peak speeds: median0.505m/s forlimpR versus0.041m/s forlimpL;
limpR moves roughly4.4-5.8cm horizontally after landing versus<0.06cm in most
limpL cycles. Measured collider-centre velocity from recorded body-origin velocity
plus angular cross offset. Lowest box corner remains near floor: rocking/sliding
readjustment, not a second clearly airborne hop at30Hz. Same asymmetric grounded
centre-bounce pattern in12968/13068/13168; different reset phases, not a matched-seed
learning comparison. Active/passive sides and equal leeway masks are correct.
Current foot velocity/angular MSE is active: frame135 contributes0.1208 out of
1.2649 total loss. Foot position cost0.0020 (11.05cm error with10cm allowance),
rotation cost0 (9.20deg within15deg). No claim that new leeway caused its onset.
Reward-only held-foot counterfactual already favors pinning for that foot alone;
it is not a physically feasible rollout or proof of whole-body causal incentives.
Suggested next experiment, NOT implemented: stance-only active-foot linear/angular
velocity MSE multiplier (start5x), using a precomputed reference planted/slow-foot
mask with smooth landing/toe-off fades. Keep10cm/15deg leeway and ordinary hop
phase unchanged. Track post-landing speed bursts, slip and hop success together.
Evidence/script: Saved/MimicKitSlowLoco/minihop-audit-20261101; speed-audit.json,
latest-replay.npz, settling-speed.png; Labs/RoboticMotionAE/audit_limp_minihop.py.
No GPU workload, desktop control, trainer restart, or training-source edit.

**November 1 limp active-leg rotation allowance — VERIFIED RUNNING.**
User requests15deg rotation leeway in addition to10cm position leeway. Same
active thigh/shin/foot: right onlimpL, left onlimpR. Remove15deg from the
shortest3D orientation mismatch, retain its relative axis, then evaluate the
original rotation-matrix MSE with the existing body/component denominator and
weight. At20deg, penalize5deg; within15deg zero. Quaternion-sign invariant,
not a separate15deg allowance on each Euler axis. Passive legs still excluded;
velocity/angular MSE, other bodies/motions, termination and motors unchanged.
Remote64-world physics/PPO/eight-replay preflight passed, including6912 known
shortest-angle/sign cases and2304 position cases. Static yaw invariance retained.
Helper Labs/RoboticMotionAE/deploy_activeleg_rotation15.py; receipts
Saved/MimicKitSlowLoco/activeleg-rotation15-deploy-20261101. Same retained GPU,
no desktop interaction/localGPU workload. Resumed12967 final, independently
preserved locally and on persistent storage with SHA verification. New run
20261101_202450_uefn_slowloco_unperturbed_2048, trainer13157/guard13158;
bridge31648/dashboard37932. Source SHA
72a60dedfc8ec1fb456613b9978dd3e62fa92b676d002575e459efcbfccbcf6b.
Verified12968->12978,850,591,744samples; optimizer/normalizer restored,
2048worlds/160inputs/eight motions256rows each. Live metadata and checkpoint
source hashes verified. Independently reconstructed position and shortest-angle
rotation MSE agree with recorded losses on all eight replays, including both
active-leg allowances and passive masks. Fresh persistent checkpoint independently
SHA verified; setup deadline released to until-stopped on retained GPU5xs589fdlcb7nr.

**November 1 limp active-leg position allowance — VERIFIED RUNNING.**
User requests10cm position-MSE leeway on the active leg in limps. Precomputed
row/body mask selects right thigh/shin/foot forlimpL and left thigh/shin/foot
forlimpR. Each selected body contributes max(norm(position-target)-0.10m,0)^2,
retaining the original15-body/3-coordinate denominator and calibrated weight.
This is radial XYZ distance, not10cm independently per axis. Disabled-leg MSE
exclusions remain. Velocity/angular/rotation losses, other bodies/motions,
termination spheres,70tick/40cm pelvis rule and static yaw alignment unchanged.
Helper Labs/RoboticMotionAE/deploy_activeleg_position10.py; receipts
Saved/MimicKitSlowLoco/activeleg-position10-deploy-20261101. Retain GPU5xs589fdlcb7nr;
64-world remote physics/PPO/eight-replay preflight passed, including2304 known
position-distance cases, diagonal boundaries, passive exclusions and unchanged
velocity/rotation terms. Source SHA
1d4e7249f8ba41607490c2ebab48869b9bc10220adeb73e3fe3cffa225996900.
Resumed12838 final, local+persistent SHA verified. New run
20261101_200631_uefn_slowloco_unperturbed_2048, trainer12266/guard12267;
bridge53720/dashboard15584. Verified12839->12859,842,792,960samples;
optimizer/normalizer restored,2048worlds/160inputs, all eight motions256rows each.
Live metadata/source hashes and independently reconstructed position MSE passed
for all eight captures, including the active-leg dead zone and passive masks.
All initial captures had no failure; verification accepts that rather than
requiring an incidental failure (-100fail behavior tested in remote preflight).
Fresh persistent checkpoint independently SHA verified; until-stopped restored.
No desktop/localGPU use.

**November 1 static yaw invariance + pelvis40cm/70ticks — VERIFIED RUNNING.**
User changed the fixed pelvis world sphere to40cm and XY recenter interval70ticks.
Reference absolute height, other limb/head spheres, passive-foot exemptions,
head velocity MSE3x and head-height strength remain unchanged. All eight motions.
64-world remote physics/PPO/eight-replay preflight passed;210tick sphere-kernel
checks cover three recenters, inside/outside boundary and isolated partial reset.
Recorded limpL12429 counterfactual: max gap19.31cm over125frames; this does not
prove indefinite survival. Viewer reads recorded reset interval (old captures150,
new70); syntax checked without desktop interaction. Source SHA
a1981c89cec0c213c1d49dc98070b06df01eed703b35e953848e8fcc76b68955.
Retained pod5xs589fdlcb7nr; resumed12629 final, preserved locally and persistent
with SHA verification. New run20261101_194151_uefn_slowloco_unperturbed_2048,
trainer11436/guard11437; bridge56300/dashboard15752. Verified12630->12640,
828,440,576samples,2048worlds/160inputs and optimizer/normalizer restoration.
All eight live replays and checkpoint source hashes verified; static flat-COM
term exactly zero on all five affected motions. Fresh persistent checkpoint
independently SHA verified; setup deadline released until stopped. No desktop
control or local GPU use. Helper
Labs/RoboticMotionAE/deploy_pelvis70_radius40.py and Saved/MimicKitSlowLoco/pelvis70-radius40-deploy-20261101.
User clarified affected motions are static. Static crawl_idle,agonising,agonising_idle,
lying,sitting now align reference pelvis heading by a world-Z-only quaternion;
position/rotation and articulation velocity targets, plus limb spheres, follow
that yaw. Tilt, height and joint errors remain. Remove static flat-COM axis-band
loss and reference pelvis XY travel velocity; retain body velocity/angular MSE
(including head3x) against aligned articulation targets. Moving crawl/limpL/limpR
remain numerically unchanged. Seven heading tests on64-world production loss:
max difference3.58e-7; collider-centre errors invariant; height/tilt retained.
512 arbitrary-tilt pairs x5 yaw angles: max rotation-matrix error2.36e-14.
Remote physics/PPO/eight-replay preflight passed for the combined patch.

**November 1 head velocity MSE x3 — VERIFIED RUNNING.**
Verified12229->12239 /802,160,640samples; all eight live replays report
head linear/angular MSE3x, position/rotation1x. Head-height controller unchanged
and present in checkpoint; exact environment/controller source hashes checked.
Latest checkpoint independently persistent-hash verified; setup deadline released
until stopped. Same GPU, no desktop/local GPU interaction.
Run20261101_185254_uefn_slowloco_unperturbed_2048,trainer10095/guard10096;bridge33916/dashboard17512.
Resumed12228 final, independently preserved/downloaded/hash-verified; retained
pod5xs589fdlcb7nr,$0.20h. Source SHA 733756c1d3da0947feffff2b7d7cb3a05daa9fc06a5a2e5a4e23819a0df2b03e.
User requests stronger head linear/angular velocity tracking against wobble.
Add2x original head-only squared error to the existing linear/angular MSE,
using original15-body/component denominator and original calibrated scales:
head contribution3x, all other bodies1x. Head position/rotation, COM, passive
leg masking, head-height strength controller and150tick pelvis rule unchanged.
All eight motions,256rows each/2048;160inputs. Remote-only production-loss and
physics/PPO/replay validation PASSED: exacthead3x, all other contributions
unchanged, zero passive torque, finite PPO and eight replay rows. Source staged;
graceful latest-checkpoint handover, advancement and persistent backup verified. No desktop/local GPU interaction.
Helper Labs/RoboticMotionAE/deploy_head_vel3.py; receipts
Saved/MimicKitSlowLoco/head-vel3-deploy-20261101. Resume latest on retained GPU.

**November 1 physical head-height strength — VERIFIED RUNNING.**
Live12143->12153,796,524,544samples; eight motions256rows each,160inputs,
optimizer/normalizer restored. Actual replay masks, strengths,150tick pelvis
rule and -100failure charge checked. Checkpoint actuation_controller.json and
embedded controller/environment sources verified against deployed hashes.
Independent persistent backup hash verified; setup deadline released until
stopped. Same RTX4000Ada/$0.20h retained; desktop untouched.
Run20261101_184222_uefn_slowloco_unperturbed_2048, trainer9218/guard9219 on retained5xs589fdlcb7nr.
Resumed12142 final, downloaded/hash-verified from persistent storage; bridge9648,
dashboard35156. Source SHA bfbbad98231e214706573ff04be672d8e94a30d884a8af3c8de65d6291a3622a.
User requests strength by actual head height, all eight native motions restored.
Calibrated collider-centre head height from both limps and crawl/crawl_idle:
vanilla at0.4194127769m (highest crawl family), max at1.1672050694m
(0.9 times lowest limp1.2968945216m). Linear alpha clamped0..1.
Both enabled legs, every motion: hip200->400Nm/axis, knee150->500Nm,
ankle90->180Nm/axis. Passive leg stays0; other body caps and motor velocity
gains unchanged. Update before every30Hz action and after resets; no new
observations (160 preserved), no motion identity in strength rule.
Precomputed DOF ratios and offsets; head collision centre matches reference
and physical-state measurement. Runtime dense FK corroborates bounds within
0.07mm. New checkpoint ZIP carries actuation_controller.json plus
head_strength.py and slow_loco_env.py; raw NN weights alone do not change
Unreal motor limits. Runtime must read this contract and apply the same ramp.
Same retained GPU; remote-only64-world physics/PPO preflight PASSED in isolated
head-strength-preflight directory. No desktop or local GPU interaction.
Helper Labs/RoboticMotionAE/deploy_head_strength.py; receipts
Saved/MimicKitSlowLoco/head-strength-deploy-20261101. Other losses and150tick
pelvis sphere re-anchor unchanged. Restored256 rows per motion,2048 total. Full eight-row replay conversion,
controller endpoints/midpoints, actual solver bounds, zero passive torque and
finite PPO update verified; no local GPU used.

**November 1 pelvis sphere reset150 — VERIFIED RUNNING.**
Advancement11607->11617,761,397,248samples. Actual replay verifies30cm sphere,
150tick metadata, passive exclusions and -100terminal penalty. Independent
persistent checkpoint download/hash verified; setup deadline released until
stopped. User requested no desktop interaction while using PC; UI verification
was stopped on Escape and all remaining checks used remote CLI only. Viewer
code updated/syntax-checked, but final visible desktop state not verified.
Run 20261101_174831_uefn_slowloco_unperturbed_2048 resumed checkpoint11606 final, independently preserved locally
and on persistent storage. Same retained5xs589fdlcb7nr, trainer8409/guard8410;
bridge10968/dashboard2120. Source SHA cbd6402cb7ac2559773d73aa343262387e989cf9e6a766c38902802cb48cacca.
Latest user instruction supersedes the rolling/percentage rules below. Keep a
constant30cm XYZ sphere, following original reference displacement in world
space between horizontal re-anchors to actual pelvis at ticks150,300,... .
Absolute reference height is retained on re-anchor; sphere active from first
control tick, including reset ticks. No10% allowance and no rolling window.
Other head/hand/enabled-foot54cm limp spheres and passive-foot exemption remain.
2048 limp-only agents,160inputs, motor strengths/losses/-100FAIL unchanged.
Production-kernel450-tick tests and real64-world termination tests passed;
full64-world PPO/replay preflight passed. Live backup/advancement verification passed. Viewer new rows show sphere and next recenter
countdown; old recorded rules retain their historical visualization.
Helper Labs/RoboticMotionAE/deploy_pelvis_reset150.py; receipts
Saved/MimicKitSlowLoco/pelvis-reset150-deploy-20261101. Retain same GPU.

**November 1 pelvis radius correction — SUPERSEDED, never deployed.**
User rejected removing the spatial radius, approved base radius plus10% travel,
then specified30cm. New pelvis rule is a true XYZ sphere with effective radius
0.30m + 0.10 * norm(reference XY displacement over the rolling two-cycle window).
Centre remains actual(t-W) XY + reference displacement XY, with absolute reference
Z. Limp window70ticks; full XYZ sphere applies after warmup, height-only against
the same effective radius during warmup. This intentionally adds30cm leeway on
top of the10% allowance; it is not a strict90%-speed floor. Other spheres54cm on
limp rows and passive-foot exclusions unchanged. Viewer preserves historical
cylinders but draws the new sphere and recorded radius for new rollouts.
Helper Labs/RoboticMotionAE/deploy_pelvis_radius30.py; receipts
Saved/MimicKitSlowLoco/pelvis-radius30-deploy-20261101. No GPU release/allocation.

**November 1 rolling pelvis displacement — VERIFIED RUNNING.** Verified advancing to iteration 11461 / 751,173,632 samples; persistent checkpoint independently verified and setup deadline released to run until stopped. Desktop visual verification was interrupted by the user pressing Escape; no further computer control attempted.
Resumed11430 final local+persistent hash-verified on retained5xs589fdlcb7nr.
Run20261101_173113_uefn_slowloco_unperturbed_2048,trainer7918/guard7919,
bridge49668/dashboard58496. Source SHA
 ddcb1058b844e86f8e36bef89950e4936e7bb0a955de3c0fe6f119069601d42f.
Full64-world PPO/replay preflight passed, including passive torque zero,
160inputs and reset subsets. Live checks passed and setup deadline was released.
User clarified require90% target progress (allow10% less), accepted rolling two
hop-cycle check and resume latest. Replaces permanent pelvis trajectory error
with horizontal vector displacement error over two authored cycles: rolling
centre=actual(t-W)+reference(t)-reference(t-W). Radius=max5cm,10% norm(reference
XY displacement). Limp W=70ticks/2.333s. Full-window warmup gates horizontal
check only; absolute reference height remains immediate54cm on limp rows.
Direction remains in vector error; overspeed beyond tolerance is also an error.
Histories reset per row and use a bounded preallocated GPU ring. Other spheres,
passive-leg exclusions,-100FAIL charge,2048 limp-only worlds and160inputs unchanged.
Synthetic95%/90% pass,85%/stationary/sideways fail; old drift expires,partial reset
isolated. Real64-world done/other spheres/height/timeout tests passed. Full PPO
preflight caught stripped slow-loco replay metadata; restored exact deployed
recorder specializations before continuing; corrected preflight passed before deployment.
Helper Labs/RoboticMotionAE/deploy_pelvis_rolling.py; receipts
Saved/MimicKitSlowLoco/pelvis-rolling-deploy-20261101.

**November 1 pelvis replayer reset audit (display only).**
User reported stationary sphere/reset despite limbs inside. Audited actual replay
10809: limpL frame62 pelvis error54.693092cm>54cm; head9.02cm,hands8.98/2.20cm,
enabled foot12.76cm all inside. limpR frame52 pelvis54.254018cm>54cm; other active
points inside. Raw world target advances; converter uses identical XYZ->[X,Z,-Y]
for target and actual. No numeric training/display position mismatch found for
these captures; user-specific rollout identification was requested.
Viewer now shows fixed floor trajectory/start, target travel and gap, red outside
sphere, exact world target/actual XYZ, and RESET: pelvis at terminal frame.
Browser10809 frame62 agrees54.69cm with raw physics audit. Earlier static screenshot
alone did not establish playback correctness; no claim that this resolves a
different capture. Trainer unchanged/running. Evidence under
Saved/MimicKitSlowLoco/pelvis-world-deploy-20261101, terminal-world-pelvis.png.

**November 1 world-space pelvis termination — RUNNING and verified.**
Verified10709->10719,702,545,920samples; optimizer/normalizer restored,160inputs,
1024rows per limp. Live replay validates world target starts at actual pelvis,
finite per-frame XYZ trajectory,54cm threshold and exact -100 terminal charge.
Independent persistent backup verified; setup deadline released until stopped.
Browser8021 verified cyan Pelvis target sphere with target skeleton hidden at
frame25 of10709. Screenshot: pelvis-world-deploy-20261101/replayer-world-pelvis.png.
User requested a pelvis radius against the world trajectory to prevent staying
in place. Added pelvis body-origin point with raw `_ref_body_pos` target,
including animation loop displacement; full XYZ distance, 54cm on limp rows
(27cm on other motions if restored). Other spheres retain their prior alignment.
The existing -100 FAIL charge applies; timeout remains free. No MSE, motor,
passive-leg exclusion, sampling or observation changes. Real64-world threshold
and PPO/replay preflight passed, including raw-target/aligned-target independence.
Recorder exports `frame_world_pelvis_target`; replayer draws the cyan world
sphere, connector and Pelvis target label. Target spheres work independently
of the target-skeleton toggle; label now shows the actual radii.
Resumed checkpoint10708 final, independently downloaded/hash-verified from
persistent storage, on retained pod5xs589fdlcb7nr ($0.20/h RTX4000Ada).
Run20261101_162157_uefn_slowloco_unperturbed_2048, trainer7474/guard7475,
bridge30628/dashboard3760. Source SHA
80e9b5ad99cb1bded17318bb4c4c9975539abb193c1c8cb0b477c1275cca3fae.
Helper Labs/RoboticMotionAE/deploy_pelvis_world.py; receipts
Saved/MimicKitSlowLoco/pelvis-world-deploy-20261101.

**November 1 slow-loco failure penalty100 — RUNNING and verified.**
Verified10427->10437 (684,064,768samples), optimizer/normalizer restored,160inputs,
1024rows per limp, strength/masks/54cm targets preserved. Actual live replay
shows exactly one failure charge on each limp; reward accounting agrees within
2.81e-6 (exclude supervised auto_phase from environment reward). Both recorded
terminal rewards round to-100. Independent persistent backup hash verified;
setup deadline released to until-stopped. TB8035 lists15-51-41 run.
User requested the same termination penalty as locomotion. Consulted October20
loco_failure_penalty journal: fixed100 reward subtraction once on FAIL, no TIME
charge, zero FAIL critic continuation. Implemented slow_loco_failure_penalty100
in prepared config, subtracted in SlowLocoEnv._update_done after reward rebuild
and failure classification, before PPO records it. Applies to slow-loco failures;
currently only limpL/limpR are sampled. It would also apply to the other slow-loco
motions if sampling restored. No charge on TIME/SUCC and no loss-exponent change.
Replay uses existing loco_failure_penalty metadata/accounting; new config's
resume allowance changes only that key. Tests exercise all target thresholds,
normal/timeout zero cost, passive exemption and real PPO buffer/terminal targets:
failed rewards<=-99 and terminal critic target equals terminal reward exactly.
Full64-world PPO/replay conversion passed.54cm active limp spheres, disabled-leg
MSE/motor exclusions,1024/1024 rows and hip400/knee500/ankle180Nm retained.
Run20261101_155141_uefn_slowloco_unperturbed_2048 on retainedGPU5xs589fdlcb7nr,
trainer6800/guard6801, resumed10426 final local+persistent hash-verified.
Source SHA4ec75c24c4fd0a6172ed3471841d06a11ad400e864106544978dcb4a0c763ad5.
Bridge47876/dashboard60172. Helper Labs/RoboticMotionAE/deploy_failure100.py;
receipts Saved/MimicKitSlowLoco/failure100-deploy-20261101.
Reward curves across this boundary are not comparable without adding back the
terminal cost. Use survival/failure outcomes and unchanged tracking losses.

**November 1 all limp termination targets54cm including head — RUNNING and verified.**
Verified10111->10121 (663,355,392samples), optimizer/normalizer restored,160inputs,
1024rows per limp and both live replay rules:head/hands/enabled foot54cm, passive
foot excluded. Independent persistent backup hash verified; until-stopped released.
TB8035 lists2026-11-01_15-21-50_slow_loco_unperturbed_2048.
User clarified head must also receive doubled radius. All active head/hand/foot
termination spheres now54cm for limpL/limpR; disabled foot remains excluded.
Other six motion thresholds remain27cm if restored. This supersedes previous
head27cm exception. Only package slow_loco_env.py changed. Actual done-path test
across all eight motions passes26/28/53/55cm and5m checks, passive exemption,
combined failure, wrap and timeout.64-world PPO/replay preflight passes.
Continue1024rows each limp,160inputs, hip400/knee500/ankle180Nm, existing losses.
Run20261101_152150_uefn_slowloco_unperturbed_2048 on retained GPU5xs589fdlcb7nr,
trainer6357/guard6358, resumed10110 final preserved local+persistent/hash checked.
Source SHA9b6026343e7d642be9052efcc28e8bca90698948b27f13e238d7d2613295ae0c.
Bridge60016/dashboard49460. Helper Labs/RoboticMotionAE/deploy_all_radius.py;
receipts Saved/MimicKitSlowLoco/all-radius-deploy-20261101.

**November 1 doubled limp limb radii — verified; head correction requested.**
Verified10055->10065, live model/replays and independent persistent backup;
setup deadline released. User clarified the head must also use54cm. Preparing
all-target correction below; earlier head27cm behavior is superseded.
User extended doubled termination radii from feet to all limbs. On limpL/limpR,
both hands and enabled foot now54cm; disabled foot excluded; head remains27cm.
Foot radius is not doubled again. Other six motions retain27cm if restored.
Only slow_loco_env.py changed in package; replay metadata mirrors actual thresholds.
All-eight motion/target tests pass at26/28/53/55cm and5m, including passive-foot
exclusion, another target's failure, cycle wrap and timeout.64-world PPO/replay
preflight passes. Continue1024 limpL+1024 limpR with160inputs and hip400/knee500/
ankle180Nm; losses and disabled-body MSE exclusions unchanged.
New run20261101_151537_uefn_slowloco_unperturbed_2048 on retained RTX4000Ada
5xs589fdlcb7nr, trainer6005/guard6006, resumed latest10054 final saved locally and
persistent with matching hash. Bridge15136/dashboard48008.
Source SHA1a35dfc137000f5e8f4012d4cc1a44b2c8007b56e63c69f5dcee6cd5568d91a6.
Helper Labs/RoboticMotionAE/deploy_limb_radius.py; receipts
Saved/MimicKitSlowLoco/limb-radius-deploy-20261101.

**November 1 temporary limp-only training — RUNNING and verified.**
Verified advancing9989->9999 (655,360,000samples), restored optimizer/normalizer,
160-input actor/critic, live1024/1024 allocation and two limp replays. Persistent
checkpoint independently downloaded/hash verified; setup deadline released to
until-stopped. TB8035 lists2026-11-01_15-08-42_slow_loco_unperturbed_2048.
User requested removing other six motions temporarily to focus training on limps.
2048 fixed rows now1024 limpL +1024 limpR, with identical selection after every
reset. Eight-motion one-hot order and160 inputs retained; all eight assets and
reference caches preserved. Other six motions receive zero training rows.
Restore full equal-eight sampling by removing slow_loco_motion_subset from BOTH
Saved/MimicKitSlowLoco/prepared/env_config.yaml and package/prepared/env_config.yaml,
then perform normal verified continuation. The narrow resume allowance accepts
only null or [limpL,limpR], with every other saved setting still matched.
Motor caps hip400/knee500/ankle180Nm, passive-leg MSE/motor exclusions and limp
foot termination radius remain unchanged. Recorder emits only two active clips.
64-world PPO/replay preflight passed:32/32 rows, fixed IDs across resets,160inputs,
passive torque0, two actual-physics replays and working conversion.
Run20261101_150842_uefn_slowloco_unperturbed_2048 launched on retained
RTX4000Ada5xs589fdlcb7nr, trainer5603/guard5604, from final9988 checkpoint,
preserved locally and persistent with matching hash. Bridge55812/dashboard59400.
Source SHA220f583ba93cee94caa5526f2cf1d3f0ed4f601ea07c508b5e0f401ce7b9a1e0.
Helper Labs/RoboticMotionAE/deploy_limps_only.py and receipts
Saved/MimicKitSlowLoco/limps-only-deploy-20261101.

**November 1 enabled limp thighs doubled — verified, superseded by pending limp-only curriculum.**
Training advanced9948->9958 (652,673,024samples), all8 live replay rows and
160-input model verified; independent persistent backup hash matched and setup
deadline released. User then requested temporarily training only limpL/limpR.
Preparing that sampling-only continuation; keep400Nm hips,500Nm knees,180Nm ankles.
User requested double thighs after knee500. Enabled support hip torque limits are
now400Nm per axis (was200) on limpL/right and limpR/left only. Knees500Nm and
ankles180Nm retained; passive legs remain unpowered and all four passive-leg MSE
terms excluded. Other motions unchanged. Actual96tick/64world test verifies all
hip caps400 and reaches400 on both support hips; passive torque roundoff<1e-7Nm.
Full PPO/replay preflight passes. Same retained RTX4000Ada5xs589fdlcb7nr;
run20261101_145743_uefn_slowloco_unperturbed_2048, trainer5058/guard5059,
2048worlds/160inputs, resumed latest9947 final (local+persistent hash verified).
Source SHA0a41c0d93290ca03039a1b32516f2c501b893181cf4bc786ae28f219f8e285cd.
Helper Labs/RoboticMotionAE/deploy_hip400.py; receipts
Saved/MimicKitSlowLoco/hip400-deploy-20261101. Bridge14412/dashboard47956.

**November 1 enabled limp knee500 — RUNNING and verified.**
Verified advancing training9898->9908 (649,396,224 samples), restored optimizer and
normalizer, actor/critic160 inputs and all8 actual replay rows with knee500 metadata
and preserved disabled-leg MSE masks. Fresh persistent checkpoint independently
downloaded/hash verified; setup deadline released to until-stopped. TB8035 lists
2026-11-01_14-47-34_slow_loco_unperturbed_2048. Same GPU retained throughout.
User explicitly requested500Nm. Sole package change is limp_support_strength
knee_nm300->500 in slow_loco_env.py; right support knee on limpL and left support
knee on limpR only. Hip200Nm/axis, ankle180Nm/axis, passive motor masks and all
four disabled-leg MSE exclusions preserved. Normal motions unchanged.64-world
96tick actual-torque test reaches500Nm with passive numerical residual6.24e-16Nm;
zero assertion uses existing PPO preflight1e-7Nm tolerance. Full PPO/replay
preflight passes. Bundle978bb924096a5ef25e0f0e89cdb025273a62b4e4d87948b769c5370ef00f536b.
Run20261101_144734_uefn_slowloco_unperturbed_2048 launched on same retained
RTX4000Ada5xs589fdlcb7nr,trainer4675/guard4676,2048worlds/160inputs, from latest9897
(648,675,328samples), local+persistent SHA
434727d9b1c12b4b97b0faa3c59e01fea3de62ade7f2a7bf451e2d7d051882d0.
Helper Labs/RoboticMotionAE/deploy_knee500.py; receipts
Saved/MimicKitSlowLoco/knee500-deploy-20261101. Bridge59444/dashboard60048 launched.

**November 1 passive-leg MSE exclusion — RUNNING and verified.**
Verified training9840->9850 (645,595,136samples), optimizer+normalizer restored,
2048worlds/160inputs, all8 actual-physics replay rows carry the expected exclusion.
Fresh persistent checkpoint independently downloaded/hash verified; bounded setup
deadline released to until-stopped. Same GPU retained. TB8035/data/runs confirms
2026-11-01_14-36-35_slow_loco_unperturbed_2048; bridge20576/dashboard57176 publishing.
User authorized removing disabled-leg MSE. New run20261101_143635_uefn_slowloco_unperturbed_2048
launched on retained RTX4000Ada pod5xs589fdlcb7nr, trainer4170/exitguard4171,
from latest9839 final (644,874,240samples), local+persistent SHA
27be823d0ea5e3ca4a5c6929c17823d82869b19ced716b7547ab042680350af3.
Precomputed per-row body mask zeros position,linear-velocity,rotation,angular-
velocity MSE for left thigh/shin/foot on limpL and right thigh/shin/foot on limpR.
Original15-body denominator retained: other body contributions unchanged; flat
COM objective, motor masks/caps, motions, observation160,2048worlds and termination
unchanged. Metadata disabled_leg_mse exposed in actual replay. Canonical and
package slow_loco_env.py synchronized; sole package change. Targeted64-world
mask/real-step tests and full disposable PPO/replay preflight passed. Bundle SHA
e3b3ff75f46dc88c651e6b46f405943567db637656d8e18042a87c87306aa840.
Knee-specific policy-free test: current300Nm knee supplies42-54% of support-leg
positive work in first200ms (~175-177J), hits cap83-96ms. Same direct controller:
150Nm peak COM up0.846/1.021m/s;300Nm1.485/1.626;450Nm1.530/1.705;
600Nm1.537/1.703. Original150 restrictive;450 improves only3-5% for this controller.
Not reoptimized per cap, not a maximum-capacity bound. Keep current300Nm knee,
200Nm/axis hip and180Nm/axis ankle for this reward-only continuation.
Receipts Saved/MimicKitSlowLoco/passive-leg-mse-deploy-20261101; helper
Labs/RoboticMotionAE/deploy_passive_leg_mse.py. Knee evidence
Saved/MimicKitSlowLoco/knee-capacity-20261101/comparison.json.

**November 1 limp tracking deep audit — target/actuation conflict, live unchanged.**
User rejected generic hop proof as insufficient for the observed training failure.
Downloaded/hash verified checkpoint9597 (ea12501deb36775ecb6dd7dd6d1148bb25cb88813807778abc324558c5c52791).
Compared9189 vs9597 under identical current physics on32 seeded random starts per
limp motion; initial observations bit-identical. Added26,738,688 training samples
but requested good-foot swing frames (>2cm target, <1cm actual) remain missed
97.95% L /97.55% R (previous97.97%/97.84%). Mean first-failure duration combined
1.142->1.144s; no starts survive90ticks. Average reward rises, so reward progress
is not hop progress. Disabled leg still contributes20-25% of measured tracking
loss; only its foot termination is masked. Latest saved live replay limp episodes
0.367/0.500s. Current run advancing9757/639,500,288samples, no failure/backup errors.
Critical reference issue: good foot swings while disabled foot stays at~1.5mm;
COM trajectory is supported, not ballistic. Smoothed Newton COM estimate needs
~0.827/0.825 bodyweights ground support at sourceframes3-5, when only disabled
foot can supply it. Reference thus expects load-bearing controlled behavior from
fully passive hip/knee/ankle. Optimistic inverse dynamics using actual exported
MJ model, zero armature, generous all-eight-corner friction force choices:
critical swing remains inconsistent even with huge enabled torque and freely
allowed passive ankle moments; those frames have no joint-limit violations.
Finite-difference demand/omitted drag mean this is strong diagnostic evidence,
not an exact trajectory-feasibility theorem. Many small double-support residuals
can disappear with ankle constraint moments; do not overclaim all frames impossible.
Six local-only matched cases also include direct reference servos15/40, hip3x,
and powered-disabled-leg diagnostic. Triple good-hip caps barely changes servo
failure timing; powering disabled leg improves servo reward3-4x, still not stable.
No deployment, reward/target/actuator changes or provider allocation/stop. Next
recommended direction for user's fully passive leg: physically feasible hop/support
reference and tracking terms that allow passive motion, validated on a full cycle
before long training. Generic takeoff proof below remains valid but does not prove
this reference is achievable. Evidence Saved/MimicKitSlowLoco/limp-deep-audit-20261101/
{diagnosis,tracking-summary,reference-dynamics}.json and target-support-and-policy.png;
traces, checkpoint, actual-model.mjb retained. Scripts fetch_limp_deep_audit.py,
probe_limp_tracking.py,audit_limp_reference_dynamics.py,summarize_limp_tracking.py.
Initial phase metadata corrected from recorded input phase; starts were random,
not uniform phase grid, and all measured traces remain unchanged.

**November 1 mechanical hop-capacity proof — independent of neural policy.**
User correctly rejected frozen-policy cap ablations as an answer to physical
capability. Local-only direct bounded-velocity servo search (1,024 limp candidates)
found takeoff witnesses at CURRENT support caps: hip200Nm/axis, knee300Nm,
ankle180Nm/axis. Independently reran at240Hz with zero initial velocity, two
repetitions/condition, authored starts and stricter single-foot starts. For strict
starts, passive knee flexed+0.9rad and passive ankle neutral at initialization;
these poses are collision-free, within every joint limit, and passive foot starts
clear of floor. No motor enabled in passive leg, no external impulses. limpL/right
support: peak COM upward speed1.485m/s, both feet>1cm continuously0.0958s, max
simultaneous clearance3.50cm. limpR/left support:1.626m/s,0.2458s,10.38cm.
Passive foot ground impulse over first200ms exactly0; support impulse214.85/226.44Ns.
Momentum balance discrepancy0.37%/0.13%; all actuator caps respected; motors-off
controls never ascend or become airborne. Thus current thigh/leg strength permits
physical takeoff; no additional hip power is necessary merely to make a hop
possible. This does NOT establish stable repeated hopping, exact reference
tracking, or minimum sufficient caps. COM rise22.4/25.1cm is measured from crouch,
not ballistic jump height. Authored starts also hopped, with<1% push-off impulse
from passive foot; original passive ankle has an initial limit violation, which
is absent in strict tests. No live training/source/settings/GPU changes.
Evidence: Saved/MimicKitSlowLoco/limp-mechanical-capacity-20261101/
{conclusion,verification,report}.json, verification-trajectories.npz,capacity-proof.png.
Repro: Labs/RoboticMotionAE/{probe,verify,summarize}_limp_hop_capacity.py.

**November 1 hip/thigh strength follow-up — live settings unchanged.**
User asked whether more thigh power is needed. Downloaded/hash verified latest
checkpoint9397 (only100updates after stronger-knee/ankle continuation) into
Saved/MimicKitSlowLoco/limp-hip-audit-20261101. Four local frozen-policy cases,
256worlds/64 matched limp starts each,120tick horizon; all initial obs bit-identical.
Existing knee300/ankle180 support-only preserved; passive motors stay0. Hip200Nm:
35.859 mean first-failure ticks;400Nm33.813;600Nm34.531;200Nm with doubled hip
velocity gain35.266. Mean per-start peak pelvis up speed0.3872/0.3765/0.3831/0.4003m/s.
Baseline hip saturation only third axis0.80% L,2.75% R; other axes0. Hip velocity
commands near bounds<2.1%; existing bounds~6.28-9.05rad/s,gain50Nm/(rad/s).
600Nm trial actually produced up to409.3Nm; capacity was available. No demonstrated
benefit of higher hip torque or gain, so no live source/config/GPU changes made.
This tests the current frozen policy, not physical feasibility of every possible
learned hop. No airborne-success metric: upward pelvis speed is only a proxy.
Scripts sweep_limp_hips.py; raw reports/initial_obs and comparison.json in above
folder. Current live hip200,knee300,ankle180 per axis as previously verified.

**November 1 limp support strength RUNNING and verified (latest).**
Run20261101_131243_uefn_slowloco_unperturbed_2048 resumed latest checkpoint9296
from prior00-35-44, optimizer+normalizer restored,2048worlds/160inputs. Same retained
RTX4000Ada pod5xs589fdlcb7nr,$0.20/h; advancing9297->9307 /610,009,088samples,
fresh independent persistent backup verified, until-stopped restored. Local final
9296 SHA4e065eba2b49e55e363e6ecc88a1e3dfa94579e945866365f0e4a450d153023b.
Support knee300Nm and ankle180Nm/axis ONLY on enabled leg of limpL/right,limpR/left.
Implemented once at init with existing per-world motor torque-bound multiplier;
disabled leg remains0Nm, binary limb flags unchanged. Hips,other motions,gains,
losses,termination and motion files unchanged. Existing limp enabled-foot radius
54cm and disabled-foot exemption preserved. Metadata records actual intended scope.
Analysis: six frozen-policy cases,checkpoint9189,256worlds/64 matched limp starts,
120ticks; starting observations bit-identical. Mean first-failure ticks baseline
27.906,knee-only30.109,ankle-only29.859,both1.5x33.125,both2x33.781,both3x33.469.
Selected2x gives+21.05%,near-cap knee/ankle~0-2%;3x no observed added survival benefit.
All still fail in short frozen-policy test; NOT a claim of learned hopping success.
Actual64-world96tick bounds/reset/solver test passes; knee reaches300Nm,disabled0;
full disposable PPO/preflight and converted replay pass. Live eight-row strength
and termination metadata verified. Source SHA
40bc5bac0619fb843ee7a86b31226692ee2fc7882d88141001dd4f9494e4e2c7;
only package diff pipeline/slow_loco_env.py; config files/motions unchanged.
Evidence in Saved/MimicKitSlowLoco/limp-strength-update-20261101/{comparison,selection}.json
and limp-strength-deploy-20261101/{deployment-verified,strength-test,
live-strength-metadata,live-termination-metadata,resume-checkpoint}.json.
Canonical Labs/RoboticMotionAE/slow_loco_env.py updated; helper deploy_limp_strength.py.
TB8035 and replay8021 new run bridge/dashboard launched. Never release/reallocate GPU
for an ordinary continuation. Previous source snapshots retained for rollback.

**November 1 limp strength audit (read-only live run; local experiment only):**
Latest persistent checkpoint9189 downloaded/hash verified into limp-strength-20261101.
Actual64-world local physics,300 ticks,8 limpL+8 limpR rows, noiseless policy, fixed
seed20261101. Live mass78.255kg; hip caps200Nm/axis,knee150Nm,ankle90Nm/axis.
Disabled leg torque stays0. Baseline any enabled leg motor >=95% cap on51.75% L /
71.375% R sampled control ticks (last physics substep); knee31%/27.875%, dominant
ankle22.5%/41.375%. Disposable knee300/ankle180Nm, same policy/seed, reduces leg
saturation to3.25%/3.29%. Matched first-episode duration means28.75->33.5 ticks L,
26->36.375 R; combined+27.6% (16 starts), still failures. All-reset episode means
30.12->35.12 and26.93->32.94 ticks; later resets are not paired. This supports a
knee/ankle strength bottleneck, not proof that stronger motors solve hopping.
Reference enabled foot lifts~5.1cm; passive foot remains~1.5mm above floor throughout
(dragging support, not fully airborne one-legged hop). Conditional Newton-Euler
single-support inverse demand suggests knee~206Nm peak, but passive foot can bear
load and drag/contact impulses are omitted, so do NOT present that as exact required
torque or use large ankle estimates as tuning prescriptions. No live strength,
source, training or GPU changes. Scripts probe_limp_strength.py/audit_limp_demand.py;
reports/probes in Saved/MimicKitSlowLoco/limp-strength-20261101. Small single-seed
experiment; longer learned-policy comparison needed before claiming a fix.

**November 1 slow-loco correction RUNNING and verified on retained RTX4000 Ada.**
Run `20261101_003544_uefn_slowloco_unperturbed_2048` resumed latest checkpoint3988
(261,423,104 samples, final SHA85a19ef040d73c37bd1902516d224f8c5ac96808b98e9d2754120f5cd59e4d83)
with optimizer+normalizer restored,2048worlds/160inputs/eight looped motions.
Same pod5xs589fdlcb7nr,$0.20/h retained throughout; until-stopped deadline restored
after advancing statuses3989->3999 and independent persistent checkpoint readback.
Live replay verifies enabled foot radius54cm on limpL/limpR ONLY; disabled foot
excluded; all other spheres remain27cm. User explicitly clarified 'limp', not limb.
`crawl_reference_upper.py` restores original world hand rotations (dense error
<0.024deg) and head orientation. Torso compensation reduces visible head height
range11.89->1.54cm while preserving compensated leg world paths and14.8776deg
pelvis lean. Head stabilized near a reachable lower height, not exact original
absolute height; source retarget floated palms. Swing wrist height independent
of hand rotation. Stance palm centre XY drift<0.034mm; minimum elbow bend28.54deg;
no arm-leg intersection at480Hz, floor min0.5mm. Right/left elbow acceleration
peaks27.39/48.49m/s^2; left higher than rejected flattened-palm pass but below
original popping78.7. Existing left-foot limit and0.792mm foot/thigh overlap unchanged.
All8 dense contact/loop checks,64-start reset physics (zero tick1/3 failures),
disposable PPO,160-input contract and termination boundary/replay tests passed.
These are target/deployment checks, not proof the trained policy has learned them.
Source6a22e122043ce22440539605d8b06d4567265418c347e2778115f8c914972bda.
Only deployed changes: crawl.pkl,manifest,slow_loco_env.py,observe.py. Viewer8021
and TB8035 respond; bridge/dashboard new run active. Contact review8863 rebuilt,
Space/loop checked, shows verified deployment. Before reference remains immutable.
Latest new checkpoint3989 downloaded/hash+ZIP verified locally before cleanup;
14 older intermediate archives removed from persistent and owned pod,418,554,107
bytes freed in each. Final/latest/local-preserved archives and all histories kept.
Evidence: Saved/MimicKitSlowLoco/reference-upper-deploy-20261101/{deployment-verified,
live-termination-metadata,resume-checkpoint}.json; checkpoint-cleanup-20261101/complete.json;
contact-cleanup-20261031/reference-upper.json. Screenshot viewer-deployed.png in
reference-upper-deploy-20261101. Do not rerun older correction passes or release GPU.

**October31 crawl pelvis lean / both elbow jiggle repair — preview only.**
User requested forward pelvis rotation with thigh compensation to preserve legs.
`crawl_lean_arms.py` supersedes separate hand passes: 14.8776deg pelvis lean about
hip axis/pivot plus2.4026deg torso lean. Thigh local rotations compensate; all
leg world origins/orientations preserved (dense max0.0000203cm /1.25e-13deg).
Coupled smooth arm solve keeps constant stance palm transforms, allows small
reference-like tilt (~13deg each), smooth swing wrist adjustment, and20mm reach
reserve. Minimum geometric elbow bends42.1deg right /57.8deg left. Actual elbow
acceleration cost and smooth periodic elbow-plane guide replace hand-only checks.
Peak elbow acceleration right104.1->30.4m/s^2 (-71%), left78.7->36.5 (-54%).
Upper-arm angular acceleration22463->7191 and14850->7299deg/s^2. Hand rotation
peaks588->49deg/s right,484->64 left. Dense plant position range<0.021mm,
rotation<0.0027deg. Head world orientation matches reference; its height changes
with the user's requested forward lean (not the old hard head-height constraint).
No arm-leg intersections at480Hz; floor min1.449mm; no new joint-limit violations
beyond numerical1e-6 tolerance. Existing left-foot limit and0.792mm foot/thigh
overlap unchanged. All8 dense floor/seam checks pass; crawl seam0.64cm. Backup
before-pelvis-arm-repair, report pelvis-arms.json, parameters pelvis-arms-probe.npz.
Preview rebuilt/reloaded. Live run22-13-06, package, GPU untouched. Do not rerun
older arm/head passes over this candidate. Current changes are NOT deployed.

**October 31 pink crawl hand sliding repair — preview only.**
User identified sliding from source frame35, then clarified the PINK hand in
new colored markers (anatomical right). Rendered box corners moved11.20cm over
35..43 before this repair; the cyan/left plant was stationary over that range.
`crawl_right_hand_plant.py` now anchors right palm world pose on0..12 and36..54,
with a periodic lifted swing, independent swing wrist adjustment, and explicit
hand/thigh separation. Contact tilt capped35deg; lifting2frames earlier allows
reach without changing the head/torso/root/legs or the accepted left-arm fix.
Swing lift26.20cm is a deliberate reach/clearance tradeoff, not exact source motion.
No arm-leg intersections at480Hz; right-arm limits pass within1e-6 tolerance.
All8 dense floor/seam checks pass (crawl min1.418mm; seam0.64cm). Hand angular
peak1754.9 ->588.4deg/s (original reference1186.3); angular acceleration269552
->5294deg/s^2. Fixed hand markers at source35 and cyan/pink coloring now expose
sliding in the viewer, with world-fixed camera by default. Space/play still loops.
Candidate and preview updated; package/live22-13-06 run/GPU untouched. No deploy
or restart performed. Backup before-right-hand-plant; right-hand-plant.json/probe
and pink-hand-plant-fixed.jpg. This pass runs AFTER the left-hand/head passes.
Earlier rejected solve variants were not staged; final --stage-probe reruns
constraints, floor, intersections, temporal checks and unchanged-DOF assertion.

**October 31 left crawl hand plant/snap repair — preview only.**
User reported left-hand snap/sliding after head-height correction. Measured old
left-hand peak797.6deg/s near source9; planted11..43 XY path14.12cm. New
`crawl_hand_plant.py` fixes left palm world position/orientation during stance,
uses quintic XY swing between translated cycle anchors, smooth lift, and filtered
reference-relative swing rotation faded to zero at contact. Anatomical arm IK
with periodic pole curve and actual joint limits; only left-arm DOFs modified.
Dense stance drift ranges max0.0418mm, rotation0.00347deg. Hand angular peak
484.0deg/s; angular acceleration86,316 ->5,038deg/s^2. Head/root/rightarm/legs
unchanged. Dense floor min1.449mm, no arm-leg intersections at480Hz, no new joint
limit violations (left upper numerical margin~-1e-6). Existing tinyfoot/thigh
0.792mm overlap and leftfootlimit issues unchanged. All8 dense floor/seam checks
pass; moving-crawl seam position0.75cm. Candidate and viewer updated, live run
22-13-06 and package untouched/running. Backup before-left-hand-plant; report
left-hand-plant.json. This pass comes LAST after crawl_head_height.py; do not
rerun earlier upperbody passes over it. GUI Space/play loop available.

**October 31 crawl head-height correction — preview only.**
User reported head still dropping. Measured prior candidate head origin8.419cm
below original at source frame34 despite exact reference orientation. New
`crawl_head_height.py` solves periodic torso correction, hand XY placement and
arm poles together, holding head world rotation to reference and head height
within[-1mm,+15mm] of reference. Dense32x validation: rotation error0.000727deg,
floor minimum1.435mm, torso/head/arm limits pass. Head angular peak84.8deg/s equals
reference, torso115.2 vs111.8ref. Arms adapt to maintain contact; right lowerarm
peak531.1deg/s vs445.1previous/402.8ref, smooth periodic IK, no branch flipping.
Added right-hand/thigh separation after first solve revealed5.6mm overlap; final
has zero arm-leg overlap at keys. Root/legs bitwise unchanged. Existing tiny
foot/thigh overlap0.792mm and pre-existing left-foot limit findings unchanged.
All8 dense floor/seam checks pass. Candidates/crawl.pkl and viewer updated;
package and live22-13-06 trainer remain unchanged/running. Previous candidate
backed up under before-head-height-fix. Report crawl-head-height.json. This coupled
pass supersedes older head-only/torso passes; do not rerun them over this candidate.

**October 31 head amplitude revision — preview only, live trainer unchanged.**
User rejected the deployed head motion as exaggerated. Peak-speed-only validation
missed up to18.21deg orientation error vs reference. New final pass
`preserve_crawl_head_orientation.py` counter-rotates only neck DOFs9:12 to preserve
reference world head orientation: key error<1e-12deg, dense error0.000483deg,
head joint margin0.18997. All other DOFs and all body-origin positions unchanged;
hand/leg contacts and floor1.437mm preserved. Head positional excursion remains
larger because torso contact correction remains; do not claim identical trajectory.
Candidate crawl and preview updated, NOT package/live run22-13-06. Training/GPU
left running. Viewer deployed badge now depends on candidate hashes matching
actual deployed hashes. Backup before-head-reference-fix, report
head-reference-orientation.json. Constant-torso experiment crawl_head_reference.py
failed arm-limit validation and was NOT staged. This neck-only pass must come LAST
if building the preview again; it supersedes the earlier unchanged-head-joint claim.

**October 31 crawl head repair deployed; training resumed and verified.**
The contact IK's per-frame torso twists caused the head jerk; the head joint
animation itself matched the reference. `crawl_upper_cycle.py` now solves a smooth,
periodic torso/hand-placement trajectory and stable arm IK within actual limits.
Head peak rotation 365.7 -> 95.4 deg/s (reference 84.8); angular acceleration
24,436 -> 3,520 deg/s^2 (reference 3,153). Root and approved leg trajectories are
bitwise unchanged. Hand contact heights/orientations retained; XY changes <=1.99cm.
Dense crawl floor minimum 1.437mm, no new self-overlaps above1mm, all torso/arm
joint margins pass; pre-existing left-foot joint-limit finding remains.
All eight dense floor/seam/hash checks pass. Actual 64-start physics reset check:
reset minimum+0.073cm, first tick-0.297cm, zero failures on ticks1/3 (zero commands;
not a policy-quality test). Viewer regenerated with final head correction.
Old trainer20-07-23 gracefully finished; latest2652_final /173,867,008samples is
preserved locally and persistent (SHA7a060729474b6716ee3faa18def7eb12eb9a9eec8353c28f662f811248198a42).
Run `20261031_221306_uefn_slowloco_unperturbed_2048` is running on retained
RTX4000 Ada pod5xs589fdlcb7nr at$0.20/h,2048worlds, until stopped. Resumed2652_final
with both optimizers and normalizer restored; source/settings changes limited to
all8 corrected motion PKLs and prepared manifest. Corrected crawl SHA11acfe044497d98bab3312e94fbbf5b8a0490df395a79a391f529b919adc8c9f.
Source ZIP002b130e1c943536c8ef481edb9c4a01b70f020a09e158b705bafa69f16ae622
verified locally, remote and persistent. Disposable actual physics/PPO preflight
passed with160inputs, exact one-hot/limb flags and disabled torque0.
Live model actor/critic[1024,160]; replay all8 motions with WRAP and correct limp
flags; observed iterations2653 ->2663 ->2673 (175,243,264samples). First new
checkpoint2653 independently read back from persistent and SHA verified. New
bridge/dashboard running; TB8035 lists22-13-06 and earlier runs; replayer8021 up
and local replay2653 published. Both persistent backup and advancing-training
verification recorded in contact-cleanup-deploy-20261031/deployment-verified.json.
GPU never released/reallocated. Runtime remains until-stopped after verification.
Keep `crawl_upper_cycle.py --stage-only` LAST after the coupled leg correction.
Receipts/reports: contact-cleanup-20261031/crawl-upper-cycle.json and
contact-cleanup-deploy-20261031/{head-repair-hold,resume-checkpoint}.json.

**October31 crawl knee continuity repair — REVIEW candidates only.**
The foot-only repair left the per-frame solver's knee/pole flips in place. Measured
right/left shin peaks were2072.9/2250.5deg/s and knee speed9.60/9.96m/s. Replaced
that leg trajectory with `crawl_cycle_ik.py`: both legs solved jointly over the
entire cycle, eight periodic cubic control points per leg for footXY/bend pole,
reference bend directions and HARD original world foot rotations. Exact capsule
floor and inter-leg clearance, foot-box separation and temporal regression checks.
New moving-crawl shin peaks125.87/141.15deg/s; thighs223.70/161.98deg/s (reference
224.17/163.39), knee speeds~1.93/1.55m/s, foot rotations unchanged. FootXY adjustment
at most~2.3cm; upper body/root keys bitwise unchanged. Crawl idle also rebuilt on a
continuous collision-free branch. No detected self-overlap over0.1cm in either
crawl candidate. Existing arm/left-ankle joint-limit findings remain in reports.
All8 dense floor/seam/source-hash checks pass; crawl min1.443mm, idle1.500mm,
crawl seam1.93cm.64-phase local reset check rerun: reset min+0.073cm, firsttick
min-0.223cm, zero first/thirdtick failures (zero commands, not policy evaluation).
`before-knee-continuity-fix` preserves input candidates; `crawl-cycle-ik.json` and
`crawl_idle-cycle-ik.json` contain before/after/reference temporal metrics.
Viewer rebuilt, loaded at former snap frames4.7/26.5; Space/playback verified.
This whole-cycle pass SUPERSEDES earlier independent/cyclic/polish/foot-only
passes as the FINAL crawl step; do not rerun those over the staged crawls.
Reproduce: `crawl_cycle_ik.py --stage`, `validate_slow_contacts.py`,
`check_contact_resets.py`, `contact_review.py`. Live PKLs/source hashes unchanged;
no trainer/pod/limits/settings changes or GPU stop/release in this turn.

**October31 crawl foot rotation snaps corrected in REVIEW candidates only.**
User identified violent foot snaps introduced by contact cleanup. Confirmed moving
crawl peaks1309/1837deg/s vs reference~64/88deg/s; the per-frame floor solver had
used ankle rotation as a free variable. New preserve_crawl_foot_rotations.py makes
both world foot orientations hard reference targets and solves hip/knee placement
for clearance, with ankle counterrotation. Fixed peaks64.546/88.615deg/s exactly
match reference resampled at120fps; crawl_idle also matches its reference. Keyframe
orientation error <5e-14deg. All8 dense floor/seam checks rerun successfully; crawl
minimum clearance0.5mm. Backup before-foot-rotation-fix retains previous candidates.
Viewer data rebuilt/reloaded, playing corrected crawl. Existing joint-limit and
self-overlap findings remain reported separately; no live package/trainer/pod edit.
This orientation-preservation pass must remain LAST in the candidate pipeline;
rerunning older free-rotation IK/polish afterward would reintroduce the defect.

**October31 contact-viewer playback freeze fixed.**
First RAF timestamp could precede performance.now() recorded by the Play handler,
producing a negative time/frame index and aborting draw. Clock now initializes
from the first RAF callback, elapsed time and sample indices are nonnegative,
and looping uses positive modulo. Clip changes/scrubbing reset the clock. Space
is captured once (no key-repeat toggling); button and Space verified in browser,
including pause/resume with button focus and last-frame wrap to frame0.6.
Source contact_viewer and served contact-cleanup-20261031 assets synchronized;
view.js?v=playback2 invalidates the old script cache. No motion/training changes.

**October31 motion-aware contact cleanup READY FOR REVIEW; NOT DEPLOYED.**
User requested intelligent support cleanup and before/after for all eight motions.
Viewer: http://127.0.0.1:8863/Saved/MimicKitSlowLoco/contact-cleanup-20261031/.
Exact opaque PHAT geometry, synchronized cameras/time, contact heights, eight-motion
selector/table, Space play/pause and looping; paused view is event-driven.
Crawl idle palms corrected from ~4cm floating to1.5mm clearance; knees/toes also
cleared. A modest spine inclination makes palm reach feasible without a wide-knee
pose. Moving crawl keeps alternating hand lifts; 120fps corrected keys preserve
its1.8s duration, and cyclic knee solve avoids a new loop discontinuity. Limps
retain passive-leg roles, active stance/swing clearance and unchanged upper body.
Supine motions use back/pelvis, arm and foot supports as appropriate; agonising
hands remain over abdomen. Sitting keeps user torso lean/crossed-leg arrangement,
with2.27cm pelvis lift, feet grounded and hands following the same leg contacts.
Small coupled-leg polish avoids increasing leg overlap after independent IK.
All8 full cycles pass exact FK floor checks at32subsamples/key interval; minimum
clearance0.5mm. Sources/live PKLs unchanged, originals saved under before/.
64 local physics resets (8 phases/motion): lowest +0.073cm vs original -9.548cm;
firsttick min -0.162cm, no first/thirdtick terminations with zero velocity commands.
This is NOT a learned-policy survival comparison or a guarantee of full physical
feasibility: authored self-overlaps and joint-limit violations remain documented;
original limpL loop seam (~10.61cm/~25.9deg) also remains. No asset limit changes.
Validated candidate hashes match physics input receipts. Run20-07-23 remains on
pod5xs589fdlcb7nr; last verified2296/150,536,192samples, alive/no failure/backup error.
No pod/trainer/source/settings switch or GPU release in this turn. Candidate PKLs,
report.json, validation.json, physics-reset-check-before/after.json and before/ are
in Saved/MimicKitSlowLoco/contact-cleanup-20261031. Repro helpers: clean_slow_contacts,
close_crawl_contact_cycle, polish_contact_overlaps, validate_slow_contacts,
check_contact_resets, contact_review in Labs/RoboticMotionAE. Base cleaner alone
is not the final accepted candidate: cyclic solve and coupled polish are required.

**October31 all-motion foot-floor audit: source penetration confirmed, NOT fixed yet.**
User's limpL1876 replay initializes supporting right foot -5.044cm, disabled left
foot -1.411cm. Supporting foot stays about -5cm across ticks0..3; its collider-target
error rises0->2.98->18.07->36.83cm, causing27cm reset at tick3. Disabled left foot
error only1.30cm and remains exempt. Reference and actual tick0 FK match, so this
is baked into target data rather than introduced by reset placement. Do not claim
foot cleaning made these targets floor feasible. RetargetFootLift.lift_feet only
removes additional reduction penetration: max(0,min(original_bottom,0)-before).
It deliberately preserves original source penetration. Native limpL conversion
reports41 corrections, max.206cm, while actual feet still penetrate5.17cm.
Across actual8training PKLs: agonising worst2.65cm, agonising_idle.593cm,
crawl4.07cm, crawl_idle3.78cm, limpL5.17cm, limpR5.17cm, lying none,
sitting .091cm (under1mm, user-approved pose intact). Many other joint-limit
violations also remain; fixing floor alone is not proof of full physical feasibility.
Needs absolute collider-floor cleanup of references, interpolated phases and
reset states, minimal leg-only IK, no whole-body pose replacement. Must verify
same-policy/same-init behavior before claiming this explains all early resets.
No source/package/pod/trainer changes in this audit-only turn. Evidence:
Saved/MimicKitSlowLoco/floor-audit-20261031/source-audit.json and limpL-replay.json.

**October31 hip limits corrected; RUNNING and verified:**
Run20261031_200723_uefn_slowloco_unperturbed_2048 on retained RTX4000Ada
pod5xs589fdlcb7nr ($0.20/h),2048worlds. Latest1875_final restored with optimizer/
normalizer; verified1876->1886,123,666,432samples, no failure/backup errors.
New checkpoint1876 independently SHA readback verified; until-stopped restored.
Training-only right hip twist +/-117.88deg, left swing1 101.89deg (5% pose margin);
all other bodies/axes retained. Eight target PKLs byte-identical, saved pose intact.
Existing floor-aware projection guard enabled. Unreal assets not edited; carry
these ranges into Unreal before deploying this policy there. Editor server14164
now serves the same expanded ranges (reload page to refresh cached metadata).
Actual first live sitting replay: tick1 foot bottoms +.026cm/right,-.011cm/left,
maximum target error.619cm; no first-tick reset. Lasted15ticks, then left-hand
error28.98cm caused ordinary27cm target reset. Both feet remained at floor level.
Thus floor plunge is fixed; policy still needs to learn the corrected pose.
First10-update mean8.18s; no speedup claim. TB8035 contains20-07-23 with earlier
runs;8-row replay synced/replayer8021. Source/first-tick/PPO/live evidence and
checkpoint receipts in Saved/MimicKitSlowLoco/hip-limits-20261031.

**October31 corrected hip-limit run launched, verification underway:**
20261031_200723_uefn_slowloco_unperturbed_2048, same pod5xs589fdlcb7nr,
trainer2176/guard2177. Latest1875_final preserved locally/persistent, SHA
9c2a01b6ad29f1d49a7a65b532e3e37bbb073f24b545d2140c68d9c670ecf371.
Restored122,945,536samples, actor/critic optimizer and normalizer; first1876
123,011,072samples. Source8ec4b97c254f50e4340ebadeefda13b1a07403f0abb1567dfd45ee4d6a684efd
backed up/readback verified.64-world first-tick test: all8sitting worlds survive,
max zero-command target error.345cm, feet within.084cm of floor;30ticks zero-command
survive. Motors-disabled firsttick also passes; later passive fall is expected.
Disposable PPO update finite, solver validated, one-hot/flags/reset checks pass.
Bridge25828/dashboard56668. Need two advancing statuses + new backup readback +
actual sitting replay before deploy_slow_policy.verify releases1200s setup deadline.
Editor server14164 reloads corrected hip ranges; saved pose unchanged.

**October31 hip-range correction authorized, preparing continuation:** User
explicitly asked to give legs sufficient limits and resume. Saved pose unchanged;
training right hip twist38.78->117.88deg, left hip swing1 80->101.89deg,5% pose
margin and coupled-ellipse fit. Other axes/bodies unchanged. Enable existing
floor-aware split-projection guard; config migration scoped to slow_loco_task.
Local64-world first-tick and PPO preflight underway; old run still running.
Deploy helper Labs/RoboticMotionAE/deploy_hip_limits.py preserves latest FINAL
checkpoint locally/persistent, switches trainer on same pod without releasing GPU.
Training limits are an isolated override; Unreal PHAT asset not edited. Future
Unreal deployment must apply these matching ranges. Receipts hip-limits-20261031.

**October31 hip-twist wording clarified:** Identify legs by pose, not screen side.
The raised-knee leg is internally left_thigh: saved twist6.89deg, knee height40.3cm.
The folded-flat leg is internally right_thigh: saved twist-112.27deg, knee height7.3cm.
Its twist axis is aligned with hip-to-knee within0.000005deg, so this is longitudinal
hip roll relative to the parent constraint frame, not an arbitrary transverse axis
and not visible torsion along a rigid capsule. Original sitting already had
-102.39deg on that folded-flat leg; arm-only draft identical. User editing did not
originate this large value. Raised-knee leg has a swing-limit issue, not112deg twist.
No live changes; pending choice about pose/limits remains unresolved.

**October31 sitting first-tick failure diagnosed, live run unchanged:** User
reported sitting reset after1tick. Replay1537 confirms right foot (character side)
lowest collider -26.91cm and collider-target error29.219cm >27cm, triggeringFAIL.
Saved pose starts with right foot -0.09cm, left foot0cm, pelvis -2.12cm; root/reference
FK matches at tick0. Exact isolated64-world ablations reproduce with zero commands
and with all motors disabled (-27.02cm,29.31cm error). Disabling split joint-limit
position projection removes the plunge; enabling existing FloorProjectionGuard
also removes it while retaining contact/limit solver (first-tick foot -.08cm,
.01cm target error; no reset through3ticks). Current slow-loco engine has no
transfer_floor_aware_projection flag, unlike later normal-loco profiles.
Separate feasibility issue: chosen right-hip twist -112.27deg vs +/-38.78deg;
left hip and torso also exceed PHAT bounds. Floor guard alone does not make target
joint-limit feasible. Asked user whether preserve pose and expand necessary
physical limits or keep limits and adjust editor pose. Do not silently change
saved pose/PHAT/training. GPU and trainer retained while awaiting this choice.
Evidence: Labs/RoboticMotionAE/diagnose_saved_sitting.py and
Saved/MimicKitSlowLoco/user-pose-20261031/first-tick-diagnosis.json/log.
Previous finite preflight did not establish first-tick target stability; corrected
claim here. Proposed guard is only locally tested, NOT deployed yet.

**October31 saved sitting pose APPLIED, continuation verified:** Run
20261031_185810_uefn_slowloco_unperturbed_2048 on retained pod5xs589fdlcb7nr,
trainer1831/exit guard1832. No GPU stop or allocation. Resumed safe1436_final
(94,175,232samples), actor/critic optimizers and normalizers restored. Verified
1437 ->1447 (94,896,128samples), no failures or backup errors. Checkpoint1437
SHA ad554e21dfcfab3ac84a726fef761fc13daa97f2cfd8d149c0fc3e81aef2efc3
independently readback verified in persistent storage; until-stopped restored.
User's17:53:22UTC saved40-coordinate sitting pose repeated exactly over50frames,
WRAP/30fps. All seven other motions byte-identical to original before/motions.
No re-optimization/automatic pose edits: saved floor/overlap/joint-limit findings
are retained in application.json; finite actual64-world physics/PPO test passed.
Source SHA b6ebbb3d4392158624428d0e0d3b998be23d6ad60595e3ab55e6e647202cb192,
persistently verified. Bridge6376/dashboard43064;8-row replay synced, TB8035
lists18-58-10 alongside previous runs; replayer8021 available. Details/receipts:
Saved/MimicKitSlowLoco/user-pose-20261031. Rejected17-59-34 trainer ended normally
and its exit guard was removed only for the handover; do not resume those targets.

**October31 user-approved sitting pose deployment in progress:** User saved the
chosen pose at17:53:22UTC and explicitly requested updating training now.
Apply exact saved40 coordinates as a static50-frame WRAP sitting target; restore
all seven other motions byte-for-byte from before/motions. Resume preserved
1436_final before rejected full-body targets, on the same allocated4000Ada pod.
Receipt Saved/MimicKitSlowLoco/user-pose-20261031/application.json.
Pelvis editor rotation now compensates both legs and preserves foot transforms;
108rotation cases,61drag samples and6unreachable cases pass. Current user save
supersedes earlier unchanged verification save; do not reset or re-optimize it.

**October31 manual sitting pose editor ready:** User accepts the arm-only draft
appearance, wants more forward torso lean, and now requests direct manual pose
editing before the training update. This supersedes the pending question about
which hand-contact alternative to choose. Editor: http://127.0.0.1:8871/.
Local server31456, Labs/RoboticMotionAE/pose_editor_server.py (loopback only).
Starts from arm-only sitting frame20; click/select any body, rotate with gizmo,
move hands/feet with exact two-bone IK, elbows/knees control bend direction.
Torso forward/back2deg buttons optionally keep hands planted. Undo/redo/reset,
local draft restoration, PHAT checks and optional limits, saved pose + PNG.
Edits remain local: no automatic training/package writes. Save path
Saved/MimicKitSlowLoco/pose-editor/current.json; versioned saves retained.
Current saved file is the unchanged starting pose saved during verification,
NOT a user-authored final choice. Wait for user's edited pose / go before updating.
FK agrees with actual model within2.3e-16m; four-chain IK and6deg torso lean
with pinned hands pass, legs exact. UI gizmo drag/lean/undo/save readback pass.
The misleading Matplotlib renderer is retired for pose/overlap decisions; old
review URL redirects to an opaque WebGL view. The full-body trial still runs
per explicit user instruction to retain training/GPU during preparation:
17-59-34 on5xs589fdlcb7nr, verified1737 /113,901,568samples, no failure.
No provider/trainer stop, allocation, model change or training update this turn.
When applying the chosen pose, restore seven other motions from before/motions,
exclude rejected full-body targets, and use the preserved pre-replacement1436_final
checkpoint unless user explicitly chooses otherwise. Keep the GPU allocated.

**October31 retarget correction in progress:** The full-body target replacement was
rejected by the user because it changed the authored pose. It was already deployed
as run `20261031_175934_uefn_slowloco_unperturbed_2048`, trainer1513/guard1514,
on retained pod5xs589fdlcb7nr at$0.20/h. User explicitly requires keeping this GPU
and training running while preparing the arm-only correction. Do not stop or
allocate pods. Restore original targets except arm IK for sitting: preserve root,
trunk/head and both legs exactly; map hands to source-relative leg contact points.
Safe pre-replacement checkpoint1436_final from17-19-41 is preserved locally and
persistent (SHA e0a48a00df0be0a18b4e53a5fb4795c25eebdd6fcff0e8f1908cc6176c635e24).
The old retarget-repair/accepted.json is explicitly rejected, not user-approved.
Do not automatically reuse its full-body candidates. Arm-only work is isolated in
Saved/MimicKitSlowLoco/arm-ik-20261031; no live changes made yet for that correction.

**Locomotion October31 - previous-run storage cleanup complete:** Removed63
persistent intermediate checkpoints from19-05-37, freeing3,223,710,635bytes
(3.22GB). Kept first323238 and latest329638. Latest independently SHA/ZIP
verified locally and SHA readback verified in persistent storage before deletion.
Other runs, telemetry and active slow-loco training untouched. Receipt:
Saved/MimicKitLocomotion/checkpoint-cleanup-20261031-previous-run/complete.json.

**Slow loco policy October31 - RUNNING, verified:** Eight native clips,
fresh2048worlds, equal256/clip;160inputs with8motion one-hot and4limb flags.
limpL/limpR have respective hip/knee/ankle motors disabled in actual solver;
physical leg state/contact retained. Unperturbed original crawl MSE/flat-COM
objective, no AE.64-world CUDA/PPO/replay checks pass; all8rows captured,
disabled torque zero in final stress test. Source backed up/readback verified.
Current run `20261031_171941_uefn_slowloco_unperturbed_2048` on Community RTX4000Ada
`5xs589fdlcb7nr` at $0.20/hour. Trainer1066, exit guard1067. Resumed latest1197_final,
preserved/hash/CRC verified locally/persistent. All eight training clips nowWRAP
like loco, with original frames/fps and stock horizontal cycle displacement.
No clip-end resets;10s limit/27cm checks retained. limpL left foot and limpR right
foot remain exempt.64-world threshold, multi-cycle wrap and timeout tests pass.
Live1198/78,577,664samples; checkpoint1198 independently verified. Until-stopped
control restored; TB17-19-41/8-row replay confirm wrapping and10s timeouts.
Source/settings and current continuation details in linked handoff.
TB8035/replayer8021 restored and new run visible. Capacity heartbeat deleted
after successful launch. Old locomotion pods remain stopped.
[Launch handoff](Labs/RoboticMotionAE/SlowLocoPolicy.md).

**Slow loco AE October31 - complete, offline only:** Added six selected FBXs
(agonising, agonising_idle, limpL, limpR, lying, sitting) to the user's slowloco
Cutter dataset; original four cuts byte-identical, ten clips total. Separate
2x512/latent128 AE trained12,000updates locally in49.2s; selected best3000,
validation.032804/test.036992. Export/CPU/input-gradient/invariance checks pass.
Bundle Saved/RoboticMotionAE/20261031_slowloco/bundle; current policy and normal
AE untouched. Reopen saved dataset in Cutter to see additions; active draft
preserved. [AE preparation and limitations](Labs/RoboticMotionAE/README.md).

**Locomotion October31 - latest backed-up checkpoint downloaded:** Owned pod
jvf465ue7ydr0a already EXITED; SSH refused, no stop/restart performed this turn.
Latest available persistent checkpoint329638 from19-05-37 saved locally under
Saved/MimicKitLocomotion/preserved-latest; full SHA readback and ZIP CRC verified.
Training is stopped; cause not investigated in this download-only request.
[Checkpoint receipt/status](Docs/MimicKitTraining.md).

**Locomotion October30 - idle stepping and leg reversal restored:** All idle
(normal/P/P+/P-minus) retain original four MSEs plus COM2 and now restore only
excessive stepping and thigh/shin translation/angular reversal at prior fixed
weights (historical15%/7% calibration). Both active all episode; no prior fade.
Other idle losses/boosts/multiplier/phase supervision remain off. Normal idle
noise.025 and41/2048 rows, P-minus62, other idle100, locomotion1845 unchanged.
Locomotion, termination/penalties and original position allowances unchanged.
128-world150-tick checks pass, including restored costs, MSE/COM2, zero forbidden
extras, graph parity and bit-exact non-idle reward. Latest323237 safe locally/cloud.
Run19-05-37 launched on same RTX4000Ada jvf465ue7ydr0a,$0.20/hour,2048 until stopped.
Verified323248 /14,142,341,120samples,~20.8ktransitions/s; checkpoint323238
persistent readback,20 finite replay rows/config/source checks pass. Setup guard
released. TB cards publishing; prior/wobble and separate foot-jiggle stay off.
[Current training handoff](Docs/MimicKitTraining.md).

**Spear October30 — pike-only actor complete and saved:**
`/Game/_mygame/spear/A_Spear` uses Big Throw's saved mesh scale
(.862342759,.883492713,.761916187), no slash admission or hilt/deferred depth cap.
Forward release waits for the entire spear/pommel plus assumed15cm target;
withdrawal and authored resistance remain. Four native regressions and five
actual Blueprint Play cases pass, including flesh/full blade stain/collision
restore and original sword hilt stop. Saved status3,43,494tris,17Jolt-valid hulls;
derived collision-only FBX preserves all render/shading/socket data. CCD on,
MACD off; inherited test launch and two tick prints disabled only in the copy.
Disk reload/default checks and3,991-pin audit pass; original sword, PoseAgent,
two maps and both Throw Lab state/profile files remain byte-identical.
Successful normal `build-ccd.log` DLL snapshot tested; no Live Coding. Later
whole-checkout retries cancelled under paging pressure, no claim on unrelated
agents' later builds. Owned host45696 has completed editor shutdown; Main Menu
and user Play untouched. Big Throw controller attachment/release/flight wiring
remains the separate pending port. Storage follow-up: about625MiB of owned test
host/build data remains; automatic approval review blocked full-host and narrower
cache-only cleanup. Nothing deleted. [Evidence/usage](Docs/SpearPike.md).

**Foot IK October30 - lossless optimization after user approval:** Host-only
slide-entry dependency caching and slide-joints redundant-work removal preserve
20,121 complete frames and 10,400 joint comparisons exactly. Sixteen sequential
slide cases total121.80->90.56s (1.345x); no motion tuning, shared solver, arms,
settings, viewer or server changes. Original source and parity receipts retained
in Saved/FootIKLossless20261030. Native port/packaging verification is separate
and still in progress. [Details](Labs/FootIKLab/README.md).

**Foot IK October30 - native integration built; final checks pass:**
Accepted lab/setup remains remote76614437. Build35 succeeds with normal dynamic
UBA/NoPCH. Set Foot IK Enabled / Configure Live Foot IK / Get Live Foot IK State
are available; default off, no Blueprint wiring/tuning/assets changed. Held-input
forecast invalidation now survives its normal turning speed-cap changes; real
input/facing/tuning changes still cancel. Actual moving/turning/reverse/stop/
re-enable checks pass twice. Real ramp, surface lifecycle, Jolt target/feedback
and elevated/sliding Bodyflip handoff pass. Terrain exit now preserves its full
accepted pose for the first NN predecessor, beside ordinary current/history
feature encoding: final-native-23 gives zero endpoint error, ten new policy
publications and return retirement. Canonical exit may have zero remaining
correction; test requires a real corrected episode, not artificial exit influence.
Cold Build35 BP compile/Play passes status3/properties0/pins0,60ticks/25targets,
public disable call, unchanged BP/map hashes. Owned test editor closed.
Exact packaged solver48cases/26,296frames, including the shoe-corner optimization;
no position/quaternion-component/scalar differences. Private lower-only forecast
222frames/26,466values exact (4,571->2,028ms); discarded initial work4,923frames/
43checkpoints exact (1,141->797ms). Engine NN26fixtures/1,876poses within0.0003;
coupled3,214frame semantic parity retains backend drift up to5.2mm/4.19degrees.
**Limit:** this is not unconditional realtime1:1 parity. Under CPU/memory pressure,
stair forecasts can miss their deadline and expose current raw NN; a retained
trace shows a correction interruption. Slide entry also remains costly. Exact
finite box/box-convex collision and explicit incline mode are the supported scope.
No late stale pose, shortened horizon or relaxed contact gate hides those limits.
Reuse NativeHost; no new host/model copies. Automatic approval review still
blocks about845MiB of owned temporary-cache removal; preserve cleanup receipt.
[Usage, evidence and limitations](Docs/FootIKNative.md).
**Foot IK October30 - F82 clearance entry / F123-131 hand stall:** Replaced the
hard .7rad/contact switch between wall-search methods with continuous shoulder
gradient correction throughout. Seed arm history before clearance starts and
briefly limit entry acceleration, fading as contact settles. Current yaw-stop10m
replay: left80-83 peak266.31->26.67m/s2; right123-132 peak211.78->11.99m/s2,
upward relative travel stays positive and19/19 contact ticks retained. Roots
exact; full joint/wall checks pass. Stop12m regression retains F145 fix/contact.
Host slide-arms.js only. Reload pending; visual review remains with user.
[Details](Labs/FootIKLab/README.md).

**Foot IK October30 - F145 right-hand yaw-stop correction:** Root yaw ends at12m
(F144.5); contacting hand now eases its world velocity through abrupt heading
changes using existing constrained arm IK. Root/timing and all poses through144
unchanged. Replay spike88.77 to19.37m/s2, contact144-150 retained, wall/joint checks
pass. Host-only; full viewer reload pending, user doing visual review.
[Details](Labs/FootIKLab/README.md).

**Foot IK October30 - release smoothing implemented:** Releasing arms now bound
angular acceleration; wall-safe repair starts from that prediction. Recorded
left136-140 peak acceleration72.86 to44.02m/s2; wall/joint checks pass. Right138
fix retained; torso guard stays removed. User requested quick implementation
and will visually review; full viewer reload pending. [Details](Labs/FootIKLab/README.md).

**Locomotion October30 - whole-body velocity/angular-velocity MSE x5 live:**
Replaces leg-only x5 on all rows, including custom MSE alongside prior; no leg
stacking. Position/rotation unchanged; existing pelvis relative emphasis retained.
Latest302476 preserved locally/cloud, resumed same$0.28/hour RTX4000Ada2048,
run01-09-28 until stopped. Verified302487,~23.7ktransitions/s,20 replay rows and
new persistent backup. Immutable source1c2d2b9; no rejected idle objective.
[Current training handoff](Docs/MimicKitTraining.md).

**Foot IK October30 - torso guard removed at user request:** The finite-torso
avoidance/front route caused a velocity hitch at F105.5 and has been removed.
The independent continuous shoulder-gradient fix for the F138 right-hand kick
remains. Recorded replay: right136-140 peak acceleration11.73m/s2 (original312.69),
wall/joint checks pass over317 slide ticks. Left-arm torso crossing is unresolved
again; do not claim self-clearance. Host slide-arms.js only; surface/NN/legs/tuning
unchanged. [Details](Labs/FootIKLab/README.md).

**Throw Lab October29 - checkpoint pushed; first native control/motion port built:**
Approved lab plus exact saved setup pushed as a193d263; remote hash verified.
Snapshot/hash manifest: Labs/ThrowLab/approved/2026-10-29/. Native Begin/Play,
Release/Cancel/State nodes and pose evaluator added; physical velocity/twist
controls only, with nonphysical settings mirrored from that snapshot. Runtime
profile: Content/ThrowLab/Profile.json. Normal Editor DLLs current;4/4 native
checks pass,1392 poses, max position1.92e-11m and launch error2.10e-14. Every
game frame publishes authored motion (including odd-frame keys); accepted pose
feeds NN recurrence. Reflection status3/properties0/pins0/wiring preserved;
PoseAgent/TestNN hashes unchanged. No interactive main editor or user Play.
Headless Fab startup crashed before tests; retry with process-only DisablePlugins=Fab
passed. Evidence Saved/Diagnostics/ThrowPort20261029/. Projectile attachment/Jolt
flight/aerodynamics and actual Play verification remain pending; this is not a
completed physical throw pipeline. [Native scope and procedure](Docs/ThrowControls.md),
[lab details](Labs/ThrowLab/README.md).

**Locomotion October29 evening - leg velocity MSE x5 extended to all rows:**
User clarified velocity/angular velocity only, legs only, including custom MSE
alongside prior. Replaces idle-only x5 without stacking; position/rotation and all
other settings unchanged. Resumed latest294801 on same$0.28/hour RTX4000Ada,
2048worlds,run18-54-46. Advancing294812 at~24ktransitions/s; backup/replay verified.
Immutable source4b3d171. [Current training handoff](Docs/MimicKitTraining.md).

**Locomotion October29 - idle leg velocity MSE x5 live:** all idle cohorts now
weight both thighs/shins/feet linear and angular velocity MSE x5, with existing
handoff and other losses unchanged. Resumed latest291954 on same$0.28/hour
RTX4000Ada,2048worlds,run16-34-13. Advancing291965 at~23.9ktransitions/s;
new backup/configs/replay verified. Immutable sourceba917fd; bounded idle reward
remains rejected. [Current training handoff](Docs/MimicKitTraining.md).

**Locomotion October29 afternoon - cheaper GPU migration live:** resumed latest
checkpoint288354 unchanged on Secure RTX4000Ada7rpazo6vljk1yp at$0.28/hour,
2048worlds, run13-37-26, until stopped. Advancing288365 at~23ktransitions/s;
new persistent checkpoint, configs and20 replay rows verified. Old L4 remains
stopped. One-minute booking schedule completed; rejected idle reward stays excluded.
[Training handoff](Docs/MimicKitTraining.md).

**Locomotion October29 - rejected idle reward experiment rolled back:** user
requested restoration of the previous setup. Resumed preserved pre-change final
checkpoint274953 (10.977B samples) with exact leg7/idle3 sourcea757d51, original
reciprocal reward and all previous settings. Same L4dt94w83iq0waci,2048worlds,
run00-41-10 until stopped. Advancing274974 at~24k transitions/s; new checkpoint
backup/configs/20 replay rows verified. Idle-comparison plan cancelled; rejected
idle-recovery checkpoints must not be used for future resumes.
[Current training handoff](Docs/MimicKitTraining.md).

**Throw Lab October29 - hand hard stops fixed; motion detector added:**
Current37%/.06 had added hand velocity jumps at charge cutoffF6.66 and return
F24.8796. Cached finite FK velocity carry now joins both smoothly, with up to8F
follow-through (current peak~36.28deg vs32.37 before). Release/launch controls,
body/head/clavicle motion and user keys preserved;100%/Big bypass retained.
Whole-timeline all-bone detector scans/refines speed/angular-velocity jumps;
18 charge/speed cases pass and old code is a required negative control.
Source/retimed-key changes reported separately. Current-scene command:
node Labs/ThrowLab/verify-motion-current.cjs. No live state or desktop takeover.
992 prefix/992 pose/12 launch and isolated UI checks pass. Captures hand37-
before/after and audit receipts in Saved/ThrowLab. Refresh loads.
[Details and limits](Labs/ThrowLab/README.md).

**Throw Lab October29 - clarified clavicle correction:**
User meant clavicles, not spine. Reverted whole-torso early unwind; only the
two clavicle wind-up residuals now relax through the throw. Pre-misread
head/spine/pelvis/legs restored within5.6e-16; quadratic effort retained.
Current37% atF26 clavicle neutral deviations left19.13 ->4.31deg,
right8.20 ->1.80deg. Native throwing arm/palm retained by shoulder compensation.
992 prefix/992 pose/12 launch and isolated browser checks pass. Receipt:
Saved/ThrowLab/clavicle-correction.json. Presets untouched; Refresh loads.
[Details](Labs/ThrowLab/README.md).

**Throw Lab October29 - quadratic Small Throw body effort:**
Remaining body motion now uses charge squared (50% ->25%,100% unchanged).
Reached wind-up/velocity retained to avoid the prior head reversal. Arm arc,
release timing and velocity multiplier remain.43% peak head13.904 ->11.278cm,
chest5.779 ->4.154cm;5% head0.841cm.992 prefix/992 pose/12 launch and isolated
UI/head-path/Aim/Half/undo/Refresh/velocity tests pass. Presets untouched.
Refresh loads it. [Current behavior](Labs/ThrowLab/README.md).

**Throw Lab October29 - Small Throw velocity slider added:**
Left Throw velocity0-5x slider multiplies all Small Throw charge velocities.
Shares saved speedScale with existing Amplitude; preserves presets and supports
undo/redo/Refresh. Motion, release, twist and Big Throw retain their behavior.
Isolated actual UI/3x launch/Jolt replay checks at0/5/43/100% pass; UI inspected.
No live-state edits. Refresh loads it. [Details](Labs/ThrowLab/README.md).

**Throw Lab October29 - current43% head/body reversal corrected:**
Saved43%/.06 slowdown A18/R34 reproduced in an isolated viewer. Prior amplitude
fade pulled the reached lean backward atF10.75-14.25, then forward again despite
continuous endpoints. Removed that fade: retain reached pose/incoming velocity,
scale remaining body motion, settle residual velocity over4frames and release
its offset during original recovery. Root/pelvis/spines/head/support arm share
one source clock; native throwing-arm/palm path and slowdown control retained.
Quarter-frame full-cycle traces now show one forward/return head peak (Z F26),
with no intermediate reversal. Current saved presets unchanged.5% head travel
1.679cm and chest0.705cm; world motion stays bounded by full throw and grows
with charge.992 prefix/992 pose/12 launch, isolated UI/undo/Refresh/Aim/Half and
818-pose/84-launch checks pass. Captures/head rotations: Saved/ThrowLab/head43-
before/ and head43-after/, comparison GIF beside them. No live-state/Unreal
edits or push; Refresh loads it. [Current behavior](Labs/ThrowLab/README.md).

**Throw Lab October29 - Small Throw slowdown blend added:**
Remove slowdown slider under Throw % blends source-animation speed from current
slowdown at0 to1x at1; default0 preserves behavior. Stored per throw/scene with
one undo group per drag and Refresh retention. Forward stroke, entry and actual
release shorten together; wind-up/trigger, cut arc, launch strength/twist and
body motion retain existing behavior.33% A18/R34 rates0.19208/0.59604/1 at slider
0/0.5/1, release F21.94/11.0961/9.0133. Numeric25-rate/12-Jolt-case checks and
isolated UI slider/undo/Refresh/fast Aim/Half/release checks pass. UI inspected.
Prior armed-plateau fix retained: shortened source segment advances continuously;
source arm/palm poses preserved,50% arc≈42.91° from actual neutral. The body amplitude fade was superseded by the head/body correction above. Current
keys/presets,100% and Big Throw retained. No live-state/Unreal edits or push.
Refresh loads the option. [Details and verification](Labs/ThrowLab/README.md).

**Throw Lab October28 - bomb UE5 scale omission corrected:**
Saved A_Bomb bomb_GEN_VARIABLE mesh component uses RelativeScale3D=(2,2,2).
Previous lab matched raw geometry but omitted this Blueprint scale:11.2cm body
diameter versus UE5's22.4cm. Bomb render and collision now bake the2x component
scale around the shell centre; hand offset and user's per-throw scale remain.
Read-only guarded UE5.7 package/tag inspection in inspect_bomb_scale.py avoids
opening Unreal (no main editor remote node). Blueprint/source hashes retained
in cache metadata; prepare_objects.py --bomb-only reproduces only this update.
Backup: Saved/ThrowLab/BombScale-20261028-223534/. Source-size/topology,
attachment/release/contact/replay,818-pose/84-launch and isolated browser checks
pass. Live lab state, sword/spear and UE5 assets unchanged. Refresh loads it.
[Lab details](Labs/ThrowLab/README.md).

**Throw Lab October28 - Small Throw bomb default / optimized spear refreshed:**
Object selection is independent per throw, persisted as throwObjects. Small
Throw defaults to Bomb on legacy-state migration; later explicit choices survive
switching, scenes/copy, undo and Refresh. UE5 bomb-feature mesh already matches
the lab: CC0_-_Bomb/cc0_bomb,1,799 vertices/2,622 triangles including curved fuse;
exact topology and<5.1nm rounded vertex error verified against BombFuse geometry.
Refreshed Imperial Spear from supplied mainFBX:22,559 vertices/43,494 triangles,
2.25223124m,17 UCX hulls; SHA256
e1dbb2b1414c32d180d75d5c3214f0c667abe695647f250c1bf0962449ef6814.
Importer accepts direct/indexed corner UVs. Existing atlas/bind/hulls, sword/bomb
cache and live scene bytes preserved. Backup: Saved/ThrowLab/WeaponRefresh-20261028-222819/.
Focused object migration/source checks, Jolt grip/contact,818-pose/84-launch and
isolated browser checks pass. Existing8893 service now available; browser tests
also verify previous spear-axis aiming change, independent objects, override,
undo and Refresh. All test state writes isolated. No desktop/Unreal/source edits,
service restart or push. Refresh loads new defaults/cache.
[Lab handoff](Labs/ThrowLab/README.md).

**Imperial spear October28 — selective topology reduction complete:**
New editable `Exports/ImperialSpear/ImperialSpear_Optimized.blend` and refreshed
mainFBX preserve final user grip/blade transforms.59,460→43,494triangles(-26.85%);
guard/crown/scrolls/pommel selectively reduced, sampled deviation<0.04mm.
Matched PBR close-ups, source UV/normal/topology checks and actualFBX readback pass.
Original atlas/shared material,17 corrected UCX hulls and4 sockets preserved.
Original Working.blend/open user Blender and all lab/Unreal state untouched.
Older GLB/LODs/Source/Game blends/reports remain historical. Current details and
recovery: [Imperial spear handoff](Docs/ImperialSpear.md).

**Throw Lab October28 - aim by spear orientation at release (local):**
Aim at target now turns the agent so the actual held sword/spear shaft points
directly at the target at the fractional Throw frame. Cached two-angle solve
includes weapon origin movement, grip offsets and hand/forearm keys. Full keeps
whole-body yaw plus distributed spine pitch; half distributes yaw/pitch across
five spines with fixed lower body. Armed FK entry unchanged. Original speed,
twist and velocity-to-shaft angle remain; Align velocity to spear still makes
them parallel. Bomb aiming retains spine_05/velocity reference. Spear aiming
works at zero speed; no ballistic compensation or post-release homing.
818 pose/84 launch cases pass, including forward shaft ray/target intersection,
fractional release, zero/reversed-speed independence, fixed half legs and no
added pelvis tilt. Initial browser run could not complete while8893 was down;
the subsequent weapon refresh above verified the shaft-reference change against
the available existing service in an isolated browser, including undo/Refresh.
No live state edits, desktop takeover, Unreal work or push. Refresh loads it.
[Current lab handoff](Labs/ThrowLab/README.md).

**Main-menu scene October30 — native menu implemented / tuning ready:**
Reference menu now lives in isolated Unreal lab: vector triple borders/corner arcs/
diamonds, translucent crimson glass, Cormorant SC small caps, selected-row glow
and hover crossfades. Exact1280-reference frame112/66/400/544; cached licensedfont
and explicit tracking.18 numeric+slider Menu controls, menu-only reset and Show
menu use Save/Revert/recovery. Tab opens right-hand studio on Menu; clean menu
opens by default. Mouse/keyboard/D-pad actions work in scene-preview scope;
Continue hides menu/Escape returns, New Game confirms mannequin/water reset,
Load Game has no saves/backend, Settings opens tuning, Quit confirms Save/exit.
Normal build and native input/hit-target/keyboard/modal/save-revert checks pass;
1280/960/1920 renders and extreme panel/font bounds inspected. No scene material
or background tuning changes; prior44168 saved/closed, clean review55888 opened.
Evidence Saved/MenuUI20261030, menu-*.png, Validation/menu-controls.json. No desktop
input, main-project wiring changes or push. Read current UI/lab docs before edits.
[UI handoff](Docs/WeaponWheelUI.md), [controls](Labs/MainMenuSceneLab/README.md).

**Main-menu scene October30 — approved finite-card reflection checkpoint:**
User rejected wavy/flat/wavy distance bands. Removed that extra wave layer and
ring-normal broadening. The original seeded impacts now cover their full support.
Seven cards are reflected by ray intersection with their actual common X plane,
finite bounds and original emission profile, replacing the native planar 200cm
sphere approximation for those sources. Native planar mannequin remains; cards
are excluded from its capture. Fixed2x2 subpixel radiance integration, same rain
field at every depth; no distance amplitude, fade or source blur. Original source
radiance and tuning retained. User approved the result and requested a push;
SaveLive captured the latest rain0.58208954 (14.55%), ripple size2/depth80/width1.
Ground has depth(-200…200m) and width(.1…4x) entries/sliders; live shader uniforms,
seven transforms, save/revert and weather checks pass. Normal build and focused
water/softbox prepare current;32 moving/paused captures reviewed. Flat-water
source mean .65226 vs old .65219. Far highlight shimmer remains at maximum rain;
not a finished reference match or a full scene ray tracer. No card-occlusion trace
or full GGX source convolution. No extra history CVars retained. Evidence:
Saved/RainFilter20261029, rain-filter-quad-* captures. Current look saved through live44168, which remains open on Ground. Scene-only
checkpoint pushed as d195d6d0 to origin/codex/standalone-sim; remote hash
verified. Live review retained; no desktop input or engine edits.
[Current UI handoff](Docs/WeaponWheelUI.md), [lab details](Labs/MainMenuSceneLab/README.md).

**Main-menu scene October29 — both lighting attempts reverted:**
User rejected the overhead-strip change and then the distance fade. Original
seven upright reflection cards, original source material profile and constant
water specular.255 restored. Native scene source now matches pushed HEAD.
SaveLive preserved current tuning before closing38648; normal build and focused
water/softbox preparation pass. Visible review19976 on Ground responds, scene
and smoke ready05:17:33 Warsaw. Settings hash matches this turn's backup in
Saved/ReflectionRevert20261029. No desktop input, engine edits or push.
User requested a separate rotatable explanatory schematic; current geometry is
recorded in the UI handoff. Older lighting experiment receipts are rejected
history. [Current UI handoff](Docs/WeaponWheelUI.md).

**Main-menu scene October29 — real horizontal smoke width and checkpoint:**
Pushed checkpoint `b1ed59f0` to `origin/codex/standalone-sim`; only the scene,
its curated dependencies and handoff were committed. Other work remains local.
Air Horizontal width replaces the ineffective Spread slider with0.25–8x actual
source scaling on world Y. Native Grid3D_Gas_SphereSource Non Uniform Scale is
linked to User.SmokeSourceScale=(1,width,1); vertical/depth radius and source
velocity stay unchanged. New smoke_horizontal_width defaults1, preserving saved
source shape; legacy haze_spread remains as compatibility baseline. Grid grows
only to fit the widened source plus450cm each end; resolution tracks previous
cell size with512-axis cap. Resizes debounce300ms; source-only changes keep the
field, domain changes reset gas once and need seconds to reform.
Normal build and Niagara CPU/GPU preparation pass. Native source/grid bounds,
unchanged vertical/depth dimensions, save/reload and existing controls pass.
1x/4x/8x captures visually verify widening; at8x source radius227.87cm unchanged,
grid Y4545.916cm versus2884.702cm at1x. Curated receipts in the lab's Verification/.
SaveLive preserved user rain_amount4, smoke shift7.4628cm and current water tuning
before closing28136. Resources/scene.json matches Saved/SmokeWidth20261029/live-saved.json.
Review20344 reopened on Air and was later saved/closed for the lighting update. User requested
push: curate this isolated scene, its required content, settings and handoff only;
exclude all other workstreams and generated caches/recovery files.
[Current UI handoff](Docs/WeaponWheelUI.md).

**Main-menu scene October29 — collision tuning and resting-contact gate:**
Water tab adds Push strength0–3x, Motion threshold0–20cm/s, Contact softness
0.5–20cm, Damping0–100%, Wave relief0–3x, Allow resting contact (legacy),
Try calmer contact and Clear existing waves.34 sliders total. All use existing
Save/Revert/recovery; SaveLive preserved latest native tuning before closing26304.
Measured frozen mannequin has zero bone motion but old always-present colliders
leave normal XY energy0.000397816. A native keep-depth branch made it worse and
was rejected. Final engine depth mode remains original. New default gate measures
actual PHAT transforms only for shapes reaching the3.5cm surface, including
rotation via seven local bounds samples; above-threshold horizontal speed admits
the original whole mannequin provider, with80ms release hold. No hand-authored
waves. Resting contact checkbox bypasses this gate to reproduce old behavior.
Frozen gate: exact0 GPU normal energy. Default1cm/s animated idle retains small
waves; calmer preset (.6x push,5cm/s,4cm softness,30% damping) produces exact0
for sampled idle and a real wake for90cm translation (energy0.000135745).
Inactive shapes are absent from the fluid boundary; purely vertical forcing
retains Epic's horizontal-velocity limitation. Background/rain remain independent.
Clear waves preserves position/tuning and clears displayed RT even when paused.
Normal build and lab-only Niagara CPU/GPU preparation pass. Native controls,
persistence and GPU readback receipts: Saved/Validation/collision-controls.json,
collision-response.json, weather-controls.json. Water panel capture inspected:
Saved/Captures/contact-gated-studio.png. User scene.json byte-identical to
Saved/CollisionControls20261029/live-saved.json; no main-project/engine assets,
desktop input or push at that revision. Previous PID28136 reopened on Water, responding with
scene/smoke ready03:38:01 Warsaw; rain0/background30.597%/wave relief0.8 retained.
[Current UI handoff](Docs/WeaponWheelUI.md).

**Main-menu scene October29 — click-to-move mannequin gizmo:**
Click actual mannequin/PHAT to select; world X/Y/Z translation handles, blueZ
lifts it out of water. Native query-only collision, mesh and water colliders
translate together. Pause supported. Esc cancels drag/deselects; empty click
deselects; Tab hides gizmo with panel. Reset position above Save/Revert on every
tab restores starting location/heading; R retains additional water reset.
body_offset_x/y/z persist via Save/Revert/recovery; WASD retains height. Limits
450cm horizontal, Z-30…400cm. Continuous deprojection avoids engine integer-pixel
rounding causing depth steps; native40cm XYZ drags now exact at log precision.
Normal build and shared native pick/drag/scaled-geometry/paused/cancel/persistence/
reset checks pass; existing weather/recovery validation passes. Native capture
mannequin-gizmo.png inspected; receipt Saved/Validation/mannequin-gizmo.json.
SaveLive preserved latest rain0/background30.597% before closing30320. User file
unchanged versus Saved/MannequinGizmo20261029/live-saved.json. No desktop input,
main-project/asset edits, shader preparation or push. Reopened visible review
PID26304 was on Ground with rain0/background30.597%; saved/closed for the collision controls above.

**Main-menu scene October29 — retained rain, smoke and ambient ripple:**
Latest: Ground Background ripple exposes wind_strength0–1 (current30.597%); zero
removes only ambient water normals, leaving rain/mannequin response.29 controls.
User says stop asking them to Save. Use Labs/MainMenuSceneLab/SaveLive.ps1 before
authorized rebuild: native request saves exact live settings, checks ack/disk.
Live edits also debounce250ms to .recovery, restored on launch only when the
stored baseline exactly matches saved JSON; explicit Revert resets recovery.
Implementation-only Live Coding patch added save IPC safely with no layout
changes and recovered rain-off tuning from PID12136. Then closed for normal
build of new retained storage. Backup Saved/AmbientRipple20261029/live-saved.json.
Never ask the user to Save for routine rebuilds; preserve via this mechanism.
No desktop input or source asset changes. Current review status in UI handoff.
Normal build and native controls pass, including ambient0/.37, recovery.81 and
Revert. Ground-tab capture background-ripple-control.png inspected. Previous
review PID30320 opened on Ground; scene/smoke ready01:56:41 Warsaw. SaveLive.ps1
verified on that session; later saved/closed for the gizmo update above.
Density is now0–100% across four times the old capacity: old80%=new20%, old100%
=new25%.98,532 physical streak seeds in four independently jittered layers;
all impacts use the same seed/phase/position as their drops. Original layer0
and stored rain_amount units preserved (now0–4); saved looks need no migration.
Inactive quads collapse before rasterization; water visits only occupied layers.
Fine-storm button/preset uses new95%. Native20%/100% captures verify19,718/98,532
active seeds,4.997x rate with unchanged speed/width/length/impact strength. Native
save/reload at raw3.27 and both material bindings pass. Tools/verify_dense_rain.py.
Smoke no longer has sideways wind. Centered source emits downward; negative
density buoyancy against explicit gravity-980Z creates upward return, with
vorticity curling it. No temperature/thermal buoyancy. At saved12% drift:
velocity(0,0,-64)cm/s, coefficient-.016. Drift scales speed/return acceleration;
zero pauses. Rolling motion stays independent. Source20cm above bank center,
radius180*sqrt(spread), capped240cm (~228cm saved). An initial120cm source offset
put too much smoke above frame; final20cm offset visually checked. User height,
crop, shift and other settings untouched. Only lab assets/overrides modified.
User saved before rebuild; Resources/scene.json remains byte-identical to
Saved/DenseRain20261029/prior-saved.json (saved rain90.3%, now displays23%).
Normal build-final succeeds; preparation0 errors/0 warnings and CPU/GPU smoke
compile passes. Offscreen dense-rain-20/100, down-roll-8/18 and dense-roll-studio
captures inspected. Typed flow readbacks and evolving upper bank verified;
no claim of direct GPU velocity-field measurement. Receipts:
Saved/Validation/dense-rain.json, downward-smoke.json, weather-controls.json.
No desktop input; only CLI build/render/launch. Review29744 closed for this
authorized rebuild. Current Air-tab review PID12136 reopened with saved look;
SCENE_READY/SMOKE_GAS_READY and responding window verified01:17:13 Warsaw.
This review was later saved/closed for the update above. [Current UI handoff](Docs/WeaponWheelUI.md).

**Main-menu scene October28 — retained flowing bed and calm puddle:**
`Labs/MainMenuSceneLab` ground now uses one warped phase field with long curves
and finer following strands; the rejected multi-direction interference patches
are superseded. Saved scale0.75 and dark-area option retained. Water's authored
background normals are reduced50 times so rain/contact dominate the calm surface.
Rain rings last1.05s, expand28cm/s and use directional antialiasing plus shallow
bed refraction. They remain analytical material events paired to the3D drops.
Actual mannequin collision still uses Epic WaterAdvanced/NiagaraFluids. Lab-only
soft collision falloff30→4cm fixes weak coupling in the3.5cm puddle; friction
0.00025/dissipation0.0003 reduce wake loss. Engine assets/solver unchanged.
Native GPU readback at3.2167s: collision-on XY energy0.000369499, off exactly0.
After motion stops, outer250–350cm energy rises3.25x by4.5s, showing propagation.
Stock horizontal-speed collision gate remains: purely vertical contact is limited.
28 sliders across Ground/Rain/Air/Body. New Air Left / right moves cold smoke and
source together ±1000cm without resetting the grid; default/current shift200cm.
Epic Grid3D_Gas_Smoke/native volume renderer, upper-edge mask, optional middle
mist, physical rain widths and UV wet-body coating retained. No VDB/cache bake.
All43 current live settings, including unsaved rain/smoke edits, were captured by
native F12 report and preserved exactly; only shift200 was added to scene.json.
Backups: Saved/PuddleRevision/prior-live.json and prior-saved.json. Actual saved
smoke height394.03cm/spread1.6026/roll27.985%/lower-edge30.075%; do not restore the
older cold-smoke preset over the user's tuning. Normal build-puddle-3 succeeds;
latest material/Niagara preparation has0 errors/0 warnings. Control live binding,
cloud location and save/reload checks pass. Native offscreen captures inspected:
Saved/Captures/puddle-studio-final.png, puddle-rain-final/after.png and
puddle-contact-final/disabled/after.png; JSON settings/raw GPU fields retained.
Receipts: Saved/Validation/puddle-collision.json, puddle-rain-motion.json and
weather-controls.json. Render matching remains an art-review checkpoint.
User standing authorization "dont ask just rebuild everytime" covers this lab;
latest instruction "without using my computer, resume" forbids desktop input.
Computer Use stopped; all subsequent changes/builds/captures were file/CLI/offscreen.
October29: user explicitly requested reopening; Open.ps1 -Visible -Air launched
review PID29744 with current saved settings. SCENE_READY/SMOKE_GAS_READY and
responding studio window verified at00:38:56 Warsaw. No desktop input or tuning
changes. That review was later closed for the October29 update above. Other apps, main project, Blueprints, other
labs and engine assets untouched; no push or storage cleanup.
[UI handoff](Docs/WeaponWheelUI.md), [lab instructions](Labs/MainMenuSceneLab/README.md).

**Locomotion October28 — resumed after funds interruption:** user selected latest
2048-agent foot-loss experiment. Preserved/verified checkpoint266159 at10.401B
samples; resumed unchanged on same L4 f0454mznhwpt34 ($0.59/hour), run13-01-24,
until stopped. Verified advancing266170, ~23.5k transitions/s, exact configs/source,
20 replay rows and new persistent checkpoint readback. Bridges restored; recovery
untouched. [Training handoff](Docs/MimicKitTraining.md).

**Throw Lab / spear October28 - Blender-to-FBX grip mismatch corrected:**
User screenshots exposed a genuinely stale FBX relative to saved Working.blend.
Read-only Blender bridge audit found leather/two keepers translated-0.17637485m
and a blade scale/translation absent from the FBX. Lab cache matched that old FBX
within5nm; reimporting it alone could not reflect these newer saved source edits.
Main FBX now matches current saved source geometry; grip pivot1.05862513m source
Z, blade tip2.221231m, total2.252231m. Same30,542 vertices/59,460 triangles/17 hulls.
Updated affected grip/shaft/blade hulls and sockets, blade normals; topology,
UVs/colors and other geometry preserved. New FBX hash
adebec94c106705a6db9b6628a54e8403734f145b507cfc521b12dc25e533668.
Lab cache rebuilt; full source-to-cache nearest-point error0.0001404mm. Jolt
grip/contact and818-pose/84-launch checks pass; isolated viewer loads new hash.
Blender source, live scene bytes, lab bind/scale/presets and other weapons unchanged.
Backups/audit/candidate: Saved/ThrowLab/SpearGripSync20261028/. Main FBX and lab
only; older GLB/LODs/export reports are not refreshed by this targeted sync.
Full export_spear.py still contains historical grip/blade/collision constants;
reconcile those with current source before another complete export. User Refresh
loads the corrected spear. [Asset handoff](Docs/ImperialSpear.md).

**Throw Lab October28 - requested spear FBX refreshed (local):**
Imported `Exports/ImperialSpear/SM_ImperialSpear.fbx` into the lab render/physics
cache:30,542 vertices/59,460 triangles,17 authored UCX hulls,2.231m source length.
Source SHA256 a1aca4b1821830485940b07dcd8a187863da982cdaed88cb8eb59734030cf211.
Existing spear attachment/mass/axis, sword/bomb and live scene bytes preserved;
grip/scale/presets unchanged. Geometry/COM now follow the new source. Importer
accepts revision-specific counts, keeps atlas uint8, verifies stable source/atlas
hashes and writes atomically. Grip/contact, aero and818-pose/84-launch attack
checks pass; actual isolated viewer/undo/Refresh pass. Fixed a near180-degree
half-aim bend discontinuity exposed by the new COM using continuous distributed
yaw/pitch. Backup/receipts: Saved/ThrowLab/SpearRefresh20261028/. User Refresh
loads it. No desktop/Unreal use, export-package repair or resident process.
[Lab details](Labs/ThrowLab/README.md).

**Throw Lab October28 - half attacks and target aim (local, unpushed):**
Left Attack mode section adds Half attack and Aim at target, both default off,
per throw, saved and undoable. Half fixes root/pelvis/legs at frame0; spine_01
compensates to preserve normal upper-body world rotations, head and held weapon.
Initial aim used preset launch velocity/spine_05; spear/sword now use the shaft
and held weapon origin as described above. Bombs retain the initial reference.
Full uses whole-body yaw only plus pitch shared equally across all five spines;
half shares combined yaw/pitch through the five spines with fixed lower body.
Cached two-angle solve accounts for the changed reference position. Direct local FK
entry reaches aimed Armed, then authored motion continues with the correction.
Current hand/forearm keys apply afterwards and remain editable at whole frames.
Launch pose follows the corrected hand; original speed/twist and all stored
presets stay intact. Aim off restores original launch direction; both off restore
exact old pose/launch. No ballistic elevation or post-release target steering.
818 pose/84 launch numeric cases pass across both clips/all weapons, including
world orientations, frozen legs, no added pelvis tilt, five-spine distribution,
fractional release, direct FK entry/Armed continuity and Jolt replay. Existing
vanilla and aero regression suites pass. Isolated browser toggles, target updates,
undo/Refresh, independent throws and snap checked; no live state/desktop takeover,
Unreal/server restart or additional worker. User Refresh loads it.
[Current implementation and checks](Labs/ThrowLab/README.md).

**Foot IK October29 - accepted slide movement/contact restored:** user rejected
October30 activation correction: backup copies retained old timestamps; in-app
Refresh therefore kept the rejected in-memory motion. Full browser reload is
required; restored source mtimes now renewed for other open tabs. Prior claim
that the viewer had reverted was premature despite correct disk/HTTP hashes.

User rejected
the continuity change: hands lost79–83% of travel and bracing stayed down.
Restored exact accepted pre-guard slide-arms.js(E9725E63) and surface.js(FCE87DF5).
No broad arm/leg filtering or inward stop remains; mouse scrub Play/Pause fix
retained.317-tick replay matches accepted contact/motion, min wall gap0.30mm,
joint/root/leg checks pass. Accepted full-slide hand contacts190 vs rejected117;
settled wrist paths2.292/2.535m vs0.487/0.435m. Original release-arm torso crossing
and wall-correction hitches remain unresolved. Do not equate reduced jerk with
motion quality/contact preservation. Receipts Saved/FootIKRestore20261029 and
ArmSmooth20261029/accepted-envelope.json. [Current handoff](Labs/FootIKLab/README.md).
Live8890 refreshed and wall brace at201 inspected; original paused22/camera/
tuning retained.10,530 replay bone positions match accepted clip exactly.

**Foot IK October29 - REJECTED slide arm/leg continuity and scrub playback:**
Supersedes the free-only inward stop: F44 entry and contact transitions exposed
its discontinuity and torso crossing. Existing host wall solve now keeps a side
clearance through all contact weights, carries incoming arm velocity, retains
joint velocity and smoothly releases unreachable braces. Hand reserve2mm retains
contact; rejected25mm smoothing candidate made the hand hover. Host leg-goal
inertia reduces settled acceleration678->305rad/s²; root/pelvis/pre-slide NN
remain exact. Current317-tick audit: F44 shoulder5.47->0.78deg, F81.5 wrist
acceleration245->0.52m/s²; max whole-arm step2.15deg, forearm/hand torso clear.
Residual wall safety accelerations remain; no general self-collision pass.
Mouse scrubbing preserves Play/Pause and resets frame clock; brackets unchanged.
Live8890 through202, mouse rewind while playing verified. Original paused201,
camera/tuning/0-202 trim/0.3x restored. Shared isolation/transition checks pass.
Receipts Saved/FootIKArmSmooth20261029/projected.*. [Details](Labs/FootIKLab/README.md).

**Foot IK October29 - superseded simple dangling-arm inward stop:** only the free
arm receives one smooth outward shoulder rotation after wall clearance, fading
out as bracing takes over. Elbow bend, wrist-relative rotation, circle clock and
existing smoothing retained; Jolt shoulder limits applied. No collision search,
pin/history, legs/root/shared API changes. Current317-slide-tick replay: worst
free elbow-3.97cm to+2.81cm outside shoulder plane, inner hand-box edge+3.35cm;
root and non-arm positions exact, limits pass, wall clearance>=0.30mm. Rejected
general self-clearance remains removed. Saved/FootIKFreeArm20261029 receipts.
Live8890 loaded through202;90/102 inspected, paused0/camera/tuning restored.
[Lab handoff](Labs/FootIKLab/README.md).

**Foot IK October29 - self-clearance rejected and reverted:** user reported
visible sticking. Restored exact pre-experiment arms/surface sources, preserving
the accepted wall-clipping correction. Removed self-clearance helper dependencies
and its test from active lab; rejected code/metrics archived in
Saved/FootIKSelf20261029. Collision checks had passed but motion quality did not;
do not treat those checks as proof this approach is acceptable. [Details](Labs/FootIKLab/README.md).

**Foot IK October29 - slide arm wall clearance (local, activated):** final displayed arm
capsules/hand boxes now avoid the wall after entry/contact blending, using the
existing Jolt limits and a clearance-aware temporal bound. The palm-only check
missed forearm/elbow overlap. Current Run58/yaw200/Fall-2 through202 passes all317
slide ticks: minimum gap0.30mm versus30.6cm penetration before, no added joint
violations, exact root path. Forward and negative-turn replay, shared isolation,
transition/split and signed Fall checks pass. Hand contact can release when arm
clearance conflicts. Live8890 loaded through202, paused96 retained; playback and
console verified after a cold-generation timeout/retry. No shared foot-placement/UI changes. [Details](Labs/FootIKLab/README.md).

**Foot IK October29 - signed Fall speed (local):**
Fall speed accepts negative values: -1 enters Slide as upward Vy slows to+1m/s.
Initial upward inertia survives with no thrust and full gravity through apex;
it does not immediately exit just because Vy is positive. After descending,
new upward motion exits; before apex, accelerating above entry speed exits.
Early entry requires slowing ascent, preventing immediate re-entry on upward
reversal. Positive/zero behavior retained; no saved tuning changes. Root
snapshots retain prior Vy/descending state. Focused negative-threshold checks
cover gravity, restore and reversal; existing full transition/re-entry and
exact split-generation regression also passes. Shared createFeet/Unreal unchanged.
[Details](Labs/FootIKLab/README.md).

**Foot IK October29 - slide hand chatter corrected (local, activated):**
The heading-aware arm fitter accepted sideways palm misses because it checked
only distance to the wall; independent joint speed caps then broke the solved
chain. Full palm-target residual, accepted elbow-pole continuation, damped
fitting and a shared three-joint response/rate bound remove alternating motion.
Heading speed continuously raises response to avoid turning-contact lag;
a fixed local low-pass was rejected after full-turn checks.
Current Run58% F134–202: lateral wrist acceleration423.75→3.31m/s², palm step
6.07→0.36deg/120Hz, rapid reversals23→0; both palms contact274/274 samples,
max gap1.77mm, legal joints and exact root trajectory. Arm-only inner FK matches
full FK within3.2e-12m, avoiding whole-skeleton work per fitting iteration.
Bounded fitting precision keeps recorded native preparation around3.5–3.8s.
Friction/balance and heading-aware contacts retained. Before/after upper-body
strips checked; shared isolation2722 and exit/re-entry/split checks pass.
Final native7-case current/cardinal/full±turn audit passes, all zero rapid
lateral reversals. Turn arm steps4.89/5.27deg; contacts376/442 and293/452 improve
on original252/442 and283/452. Root exact, leg differences<0.16mm.30deg/s
captured-input check retains93.9% contact with legal joints. Full six-second
turn preparations take25–26s; that remaining cost is not fixed by this work.
Live8890 Refresh loaded202 and retained paused173/camera/tuning, console clean.
Shared feet, NN and Unreal unchanged. Receipts:
Saved/FootIKSlideAudit20261029/hand-continuity-*
hand-final-regression/report.json and hand-arm-fk-parity.json.
[Details](Labs/FootIKLab/README.md).

**Foot IK October29 - heading-aware Slide (local, activated):**
Slide retains commanded facing: front stays toward the wall, side stays side,
back remains outward. Root yaw continuously changes the pose and hand contacts;
the entry corridor forecasts the heading at the end of the leg blend. Pelvis
orientation uses a decaying local entry residual to avoid a180-degree wrap snap.
Independent pelvis/leg clocks, pelvis distance, ballistic root and native NN
approach are retained. New host-only slide-arms.js gives both front hands or a
near side/back hand continuous reach weights and anatomical elbow/wrist limits.
The accepted torso/free-arm motion and70% speed-based absolute-down gaze remain
active in every heading; Head max at m/s still controls its endpoint(default30).
Goal contact now considers sole contact, all-surface knee clearance, joint
limits and knee-pole continuity together. It selects a nearby feasible tangent
target instead of asking a knee to enter the wall and then pulling the shoe
away. Settled clearance carries the previous legal joint pose, preventing
stale correction offsets from folding the leg. A delayed knee-clearance check
on otherwise clear entry paths and a slide-exit scope error were also fixed.
Sixteen Walk/Run direction/incline/floor cases pass, including +535/-523/+679
degree yaw sweeps. Max settled heading error0.923deg, max joint step7.59deg at
120Hz; native pre-Slide poses and ballistic root remain exact. Current Run58%,
forward90deg scene has286/286 settled foot-contact samples, max gap0.0122mm,
no motion-review flags. Four-heading gaze check, shared isolation2722 checks,
exit/re-entry and exact split-generation checks pass. Full-motion/multi-view
collider sheets and focused fast-entry frames were inspected. The82/85deg
floor-interaction tests correctly release wall contact once hips exceed leg
reach; they do not secretly pull the pelvis back. Earlier20-case receipts below
describe the previous fixed-heading behavior. Live8890 refreshed through202,
paused140 retained with camera/tuning/trim; console clean. No shared-foot API,
Bodyflip or Unreal changes; no push. Receipts:
Saved/FootIKSlideAudit20261029/heading/. [Details](Labs/FootIKLab/README.md).
Remaining visual limitation: the folded Run-left entry around80–92 still takes
a broad high leg sweep. The corridor raises the foot23.3→61cm above pelvis;
this extra rise is planner-authored, not required by the NN. It is continuous
and joint/geometry-valid, but not an optimal natural route. Bounded lower-route
experiments caused penetration or correction snaps and were rejected; stable
production code/timing retained. See entry-*.json in the audit folder.

**Foot IK October29 - slide transition audit (previous fixed-heading version):**
Pelvis timing follow-up: Pelvis blend s is appended below Leg blend s. It controls
pelvis position/orientation independently (legacy default twice body Blend s,
current1s). Slide closer uses this pelvis clock too. The leg corridor forecasts
the independent pelvis schedule. Current saved replay passes joint/contact and
pelvis-path checks; entry62.5 to pelvis-ready122.5, max joint step3.94deg/120Hz.
Receipt: Saved/FootIKSlideAudit20261029/pelvis-blend-check.json. Root/NN unchanged.

Slide follow-up: entry cancels only outward wall-normal rebound from locomotion;
tangential inertia/gravity remain with no ongoing attraction/thrust. Current
replay drift54.3cm becomes zero; exit/re-entry and exact split continuation pass.
Added Leg blend s at the bottom of More options, separate from body Blend s.
Legacy default is twice Blend s (current1s vs body0.5s). The leg corridor predicts
the longer duration with the independent body schedule. Contact takeover waits
for leg completion. Current entry62.5, body ready92.5, legs ready122.5; joint,
contact and pelvis checks pass, max joint increment4.21deg/120Hz. Host-only;
no Unreal/Bodyflip changes or push. Receipt: leg-blend-check.json in the audit folder.

Follow-up: base Slide inherits entry pelvis distance. Added Slide closer cm at
the bottom of More options: default0, current scene10, range0–15cm. Blends the
explicit inward pose offset over Blend s and retains it during Slide without
altering root inertia/gravity. Current0/10/15cm checks pass joint/contact limits,
exact root parity and settled offset. Larger cramped offsets are not exposed.
Saved scene retains Blend s0.5. The prior large body-clearance envelope and
hidden inward hand-reach pull are superseded: the transition now plans a legal
hip/knee/ankle route while preserving configured pelvis placement. New host-only
slide-entry.js is included in browser/worker fingerprints, not Bodyflip bundles.
Entry carries the last displayed pose; soft arm reach and smooth contact release
avoid snapping when root inertia takes the wall out of reach. Dangerous-incline
pelvis withdrawal fades its world vector, so a wall pull cannot become a sudden
downward crouch when support changes to the floor.
Twenty direction/turn/incline/floor configurations pass;19 reach Slide and one
retained-floor backward walk correctly lands before the descending trigger.
Fresh NN verifies affected feedback cases; numerical checks cover every120Hz
tick and multi-view collider sheets cover whole motion and difficult intervals.
No added hip-limit error or pelvis detour; settled limits/fixed lengths pass,
max shoe penetration0.00235mm, max joint increment6.93deg/120Hz. Current F85–115
pelvis stays48.4–49.2cm (root inertia), replacing~70cm peak and31.2cm endpoint.
Joint/shared/coupling/exit/re-entry/bounded-session checks pass; saved Blend0.5
retained. Live8890 Refresh loaded through202 at paused108, persisted state
unchanged. Hard folded routes still need more preparation than the ordinary
~0.4s active-leg plan. No Unreal/Bodyflip/UI/tuning changes or push.
Saved/FootIKSlideAudit20261029/; [details](Labs/FootIKLab/README.md).

**Foot IK October29 - slide head gaze and upper-body motion (local):**
Head gaze ramps from slide-entry root speed to Head max at m/s (default30),
now appended at the bottom of More options and saved independently of feet shift,
reaching70% toward absolute down at that limit (user reduced the original100%). A0.65s entry ease
and three limited neck/head joints avoid a snap. Small irregular damped
bends/twists are distributed across the five spine
joints. Bracing arm is re-solved to its original wall target after chest motion;
free-arm orbit/speed bursts remain. No added root forces, NN calls or workers.
Two full recorded clips plus current601frames pass: max head step0.41°/120Hz,
chest step0.18°, chest range5.8–7.4°; all settled joint limits and wall contacts
pass. Current root/pelvis/legs are exactly unchanged. This deliberately expands
the earlier free-arm-only scope; balance regression now preserves lower body,
root and pre-slide prefix. Full slide-motion tests also pass. Live8890 Refresh
retained F203/camera and loaded through F300 with no console errors. Receipts:
Saved/FootIKHeadTorso20261029/. No Unreal/other-lab changes or push.
[Current details](Labs/FootIKLab/README.md).

**Foot IK October29 - descending Slide and upward NN return (local):**
Fall speed m/s replaces Trigger |Vy|:2 means world Vy<=-2m/s, never ascent.
Above Minimum gravity incline, Slide is ballistic with zero thrust; it exits
when Vy becomes positive and may enter again on a later fall. Exit clears stale
pins, restarts native inference from preserved gait current/history rebased to
the actual root/heading, and blends the displayed slide back after leg IK using
existing Blend time. Procedural Slide pose is not fed into the gait network.
Current live scene: Full gravity10% continues climbing through F300; diagnostic
100% peaks at F43 and enters Slide at F56, Vy=-2.048m/s. User tuning preserved.
Controlled upward impulse test exits F138/re-enters F168, exit angular step
0.000436deg/120Hz; split generation exactly equal. Native recurrent reset equals
a fresh Stream seeded with the same current/history. No inference while sliding,
extra workers, Unreal/other-lab changes or push. Receipts:
Saved/FootIKSlideTransitions20261029/. Supersedes the ascent/latch diagnosis and
trigger semantics in the historical October28 receipts below.
Live8890 Refresh loaded through F300, retained the user's F171/camera/settings,
and shows upward Vy=+0.59m/s outside Slide. Fall speed label verified in More
options; existing server remained running, no restart required.
[Current details](Labs/FootIKLab/README.md).

**Foot IK October29 - free-arm neutral orientation and balancing (local):**
Current follow-up: user rejected added corrective gestures; those offsets are
removed. Original circle/reach now follow an integrated clock with irregular
2.2–3.4× bursts (0.10–0.17s rise,0.40–0.64s return), then exactly1× gaps.
Accumulated phase is retained: no rewinds or path changes. Contact-driven sway
and initial amplitude blend keep real timing.20s clock checks and three full
pose clips pass: neutral/joint limits, identical root and other bones; new peaks
0.92m/s,12.61m/s²,1.11°/120Hz supersede the slow-orbit figures below.
Saved/FootIKOrbitSpeed20261029/ is current; FootIKCorrections20261029 is rejected.
The slide's free elbow pole now follows the idle reference in its clavicle frame,
transported to the hand target. The old wall-relative pole twisted it102.9° from
neutral at the user'sF184 despite satisfying broad shoulder limits. Wrist stays
neutral-relative; true hinge elbow retained. A smooth7×10cm,~0.55Hz balancing
circle supplements inherited inertial sway, with gradual entry/extension instead
of a hard reach cap. No added UI, root force, NN calls or worker. Three recorded
clips check both arms: limits pass, settled free-arm steps<0.63°/120Hz and hand
acceleration<3.42m/s². Current417frames keep root and every other bone exactly
unchanged. Full slide-motion contact/length/entry checks pass. Captures/receipts:
Saved/FootIKBalance20261029 and snapshots/slide-balance-verification.json.
No Unreal/other-lab changes or push. [Details](Labs/FootIKLab/README.md).

**Foot IK October29 - slide preparation optimized (local):**
Current8890 scene previously spent23.70s in browser solve /24.22s to ready,
despite19ms cached backend. Worker now sends lossless gzip-JSON solved-pose
batches; browser appends them instead of repeating120Hz simulation. Same trim
and resumable prefix; no extra processes. Idle same-version Node peers reset
and reuse compiled code within the existing two-session limit. Slide-only
chain FK, shoe geometry reuse, lean joint projection and allocation reduction
give3.56× paired median raw-solver gain. All417 current frames retain exact
roots; max difference13.4micrometres /0.0018°. Full joint/contact clips,5800
session checks,30 restore/reset checks,18 shift and25 UI checks pass.
Refresh0.44–0.46s; final uncached setting edits8.97/6.83/5.84s and cold-worker
request22.21s. Requested10× fresh solves NOT achieved; do not call cached
Refresh the fresh-solve benchmark. Existing below-normal workers/startup remain.
Also separated16 surface-result /16 seed cache budgets: the old mixed budget
evicted active gait seeds and added2.93s on an otherwise cached reload.17-edit
cache isolation/migration test passes. Only8890 server restarted as PID37324;
saved scene bytes identical. No Unreal/other-lab restart, retained tuning change
or push. Final browser ready in1.43s, frame43/camera/trim0–208/tuning retained.
Receipts/pre-change sources in Saved/FootIKPerf20261029.
[Details](Labs/FootIKLab/README.md).

**Foot IK October28 - independent feet/hand slide shift (local):**
More options now has Feet shift cm / Feet max at m/s, followed by Hand shift cm
/ Hand max at m/s. Both inherit the old shared tuning; missing hand values are
explicitly persisted once so future feet changes cannot alter them on Refresh.
Separate damped offsets/carrier velocities retain the existing reach/contact
solver. Independent amounts, thresholds, zero-disable and delta-save/reload
checks pass; all601 recorded frames exactly match prior motion at equal tuning.
25 UI/trim checks pass. Live8890 Refresh retained frame126, camera and trim0–208,
saved hand20cm/10m/s and displayed all four rows. No server restart or Unreal
changes. [Details and receipt](Labs/FootIKLab/README.md).

**Foot IK October28 - speed-based upward slide targets (local):**
Appended Max shift cm (default20,0–50) and Max shift at m/s (default10,.1–100)
after Recovery speed. Feet and bracing hand request maxShift times clamped
totalRootSpeed/maxSpeed, along projected world up on the slide plane. A damped
neutral-target response handles velocity reversals; friction sees its velocity.
Per-limb reachable-target search retains the neutral knee/elbow bend planes,
joint limits and wall contact; offset can be smaller than requested. No root
forces/shared createFeet changes. Zero shift restores the previous target path.
18 focused checks pass, root/pre-slide equality exact. Both default recorded
clips pass full bone/joint/contact checks (max successive pose rotation7.6/12.2°
at120Hz). Extreme50cm/.1m/s remains legal/contacting but has a32.2° calf step;
that stress case is NOT evidence of uniformly smooth motion at extreme tuning.
25 app/trim and15 friction/recovery checks pass. Live Refresh retained frame103,
camera and0–208 trim;15cm edit/Enter/blur/persistence verified, then restored20cm.
No server restart/Unreal work,
other-lab edits or push. [Controls and limits](Labs/FootIKLab/README.md).

**Foot IK October28 - exposed slide friction/recovery (local):**
Two controls appended below Blend s in More options: Friction strength %
(0–300) and Recovery speed % (10–200), both default100/persisted with scene.
The distance-dependent restoring pull is retained (farther pulls harder,
progressive stretch guard); Recovery adjusts damping inversely so lower values
do not merely create larger catches followed by faster snaps. Zero friction
removes catches; high Recovery allows more rebound. Low-speed damping uses
small stable substeps.15 focused checks pass:100/100 exact prior particle
motion, zero friction, stronger pull with distance, force scaling, monotonic
recovery and finite full range.15cm80%return:25%=1.408s,100%=.300s,200%=.167s.
25 app/trim checks also pass. UI edits keep playhead and end-trim generation.
Live 25% Recovery edit/Enter/save verified; restored100% and savedframe149.
No server restart, UI rearrangement, other-lab/Unreal change or push.
[Controls and evidence](Labs/FootIKLab/README.md).

**Foot IK October28 - slower slide recovery, relaxed feet (local):**
After user review, contact spring now9rad/s with1.05 damping scaled to nonlinear
stiffness, replacing12/.52. Same rough-patch forcing; matched15cm release takes
0.300s for80% return versus0.117s, peak speed1.256→0.616m/s. Both recorded clips
show26–44% lower average recovery speeds, retained6.8–8.2cm half-second motion.
Slide feet prefer calf-neutral rotation with20% wall bias before ankle/toe
projection; clearance correction only along wall normal. Heel/toe/edge contact
replaces flat-sole preference: median wall tilt26–35°, ankle deviation23–24°
versus40–46°. Hip safeguard still swivels knees only to honor the hip cone;
not disabled as an ankle workaround. Root/pre-slide motion and NN calls exact;
contacts, joints and bone lengths pass.15 new compliance checks,26 existing
friction checks, full joint-motion and5,796 continuation checks pass. Activated
by Refresh, saved201/camera/0–208trim preserved. No server restart/UI additions,
other-lab/Unreal changes or push. [Current behavior](Labs/FootIKLab/README.md).

**Foot IK October28 - Refresh restored; surface generation follows end trim (local):**
Saved trim was0–208 and playback195; collapsed brackets were the blank page's
uninitialized HTML. Replaced unbounded browser requests with bounded waits,
including response bodies; preparation serializes/coalesces edits. API7 /
generation protocol1 activated on8890 alone, hidden/below-normal PID27988,
same overnight-state.json. Surface/wall and edited-platform scenes use a0.1s
seed then generate only through trimOut. Extension retains120Hz physics,
contact/slide state and30Hz NN tensors; shrink does no work. Two retained CPU
sessions, disk checkpoint restoration, future root commands still supplied.
Legacy stair planner remains unchanged: its noncausal anticipation cannot be
truncated without changing earlier motion. Warmup mean height replaces the
unused5s mean: +5.005mm in current fixture, root difference<5.950mm through208.
5,796 generator /25 UI /5 timeout /17 backend /7 genuine-NN checks pass;
split/restore prefixes and root windows equal uninterrupted runs exactly.
Actual user tab loads frame195 through208. Refresh127.6ms without rebuilding;
first cold load18.8s (policy startup plus two coupled simulation passes remains
costly). UI208→244 appends the same session (0.868s backend, zero new NN calls
after slide), shrunk to208, playback verified and paused195 restored. No other
lab/Unreal restart, motion tuning changes, UI additions or push.
[Current loading contract and evidence](Labs/FootIKLab/README.md).

**Foot IK October28 - dangerous-incline slide prototype (historical receipts):**
Trigger/latch semantics below are superseded by the October29 descending entry
and upward NN return above. Pose/contact work remains current.
Bottom of More options now has opt-in Slide, Trigger |Vy| m/s (default2) and
Blend s (default0.25). Above Minimum gravity incline, absolute world vertical
speed crossing the threshold latches slide for the replay, ascending or falling.
Preserves actual velocity; disables drive, support spring, pins/grace and energy
redirection immediately. Full gravity, no speed cap; unilateral capsule collision
still removes inward normal velocity. Root-to-mesh frame freezes at entry.
Subsequent user-rejected arm/ankle/static pose corrected: free arm hangs near
neutral/down with damped entry inertia. The tiny-sway version still read static;
October28 contact motion replaces fixed limb offsets with three damped tangent
particles, independent irregular friction patches and release intervals. Drag
opposes slip; elastic recovery returns each limb, and uneven tension rocks the
torso. No forces enter the root. Stable ankle/palm measurements (excluding
lowest-corner switching): median half-second excursions10.3–12.1 cm versus
0.07–0.43 cm before, minimum window7.1 cm in both fixtures. Knees vary16–23deg.
Hip swivel accommodates drag while retaining ankle target and signed hinge;
transition transports the legal goal pole without projecting the folded
incoming NN hip. Bracing arm uses the actual Jolt elbow hinge plus a feasible shoulder
swivel, preserving the palm contact. Ankles/toes/wrists use sharedIdle Jolt
swing/twist frames/limits in host-only slide-joints.js; knees use calibrated
hinges. Feet may touch by heel/toe rather than being forced flat. Blend retires
incoming NN joint residuals smoothly; exterior ankle arcs avoid the wall and
calf-relative foot rotation avoids opposite-limit snaps. No added root forces.
NN inference stops at slide; ghost carries the last policy pose. Shared feet/API
and Bodyflip unchanged.32 root/contact checks, full joint-motion checks and37
Slide-off pelvis-speed checks pass. Ascent/descent fixtures22/109 use10/54 NN
calls; root/replay error zero. Both settled wall fixtures pass all joint limits,
sole gap≤0.011mm, palm<0.00001mm. Post-entry maximum joint increments7.1/12.5deg
per120Hz tick. Isolated real8890 browser route, current130, entry/later frames and
other views checked; user state unchanged. This remains kinematic procedural
motion, not a ragdoll. Strongly folded entry hip transitions and an85deg cached
gait thigh probe are not universally joint-constrained; no blanket full-body
Jolt-compliance claim. Existing pre-entry sharpness is not claimed fixed.
8890 was stopped again when the user reported an unloaded viewer. Restored only
Foot IK using its existing overnight-state.json, hidden/below-normal PID448
(superseded by the bounded-generation activation above).
Health checked after launch. Latest friction motion activated in the user's
in-app tab; inspected195/207/219, restored195 and camera. New26-check comparison
retains exact root and pre-slide pose hashes, deterministic replay, stable-point
derivatives and <3deg settled joint-step guards. Plots/120Hz series:
verify-slide-friction.cjs, render-slide-friction.cjs and snapshots/slide-friction-*.
No evidence
identifies why the prior host exited. No Unreal/other-lab changes or push.
[Details and evidence](Labs/FootIKLab/README.md).

**Foot IK October28 - accepted checkpoint pushed; velocity-based pelvis closeness local:**
Approved wall-frame/pelvis-height/signed-knee motion pushed and remote-verified
as16d1fe0a93b469f4ab3fd0a87d337cee8e229f88 on codex/standalone-sim. Includes
prior terrain/yaw/root gravity/platform/persistence/live-NN work and
approved/2026-10-28/profile.json. Recovery9136 files/1,096,116,002bytes verified.
Other sessions and live scene files excluded; external runtime dependencies
remain documented. Subsequent user request is implemented locally:
Pelvis min cm keeps the previous amount at the bottom of More options. A compact
Min/Max Speed m/s pair and Pelvis max cm follow it. Blend the two amounts using
actual total root speed, clamped outside the range (default 0 / 3.5 m/s).
Maximum amount inherits minimum for old saves, preserving current 10 cm tuning.
Both amounts allow 0–50 cm and either can be larger. Dangerous inclines are above
Minimum gravity incline; the speed-selected amount ramps linearly from zero
there to full at 90°. Existing smoothed ground frame carries the inward shift.
Root and NN foot targets remain unchanged by the posture translation; signed
hinge IK reaches original targets/material pins. Zero/below-minimum exactly
match the accepted baseline (set both amounts to zero). Ghost stays before correction. Optional shared
pelvisShift is not enabled by Bodyflip.81 focused geometry/zero tests,13 baseline
and17 coupling checks pass. Saved76 visually compared0/20; live601-tick rollout
has no hinge inversion, replay error0 and pins exact. Browser verifies bottom
placement, Enter commit/blur, frame/value retention across reload. User state
unchanged. Speed extension adds 37 checks including exact pre-change Walk/Run
frame hashes, speed/angle blend, pins and knees. Isolated browser verified the
pair fits without widening the panel, Enter commit/blur and retained frame/value
on reload. Live 10→30 cm rollout: replay error zero, pin drift <2e-15 m, no hinge
inversion or sole penetration above 4e-8 m; reviewed 76/95/137/143/180. Real saved
state unchanged. No Unreal/server restart or extra worker. Refresh for controls.
[Current lab handoff](Labs/FootIKLab/README.md).


**Imperial spear October28 — selected pommel preview, export refresh pending:**
User accepted the latest shown shape and asked to stop refining and show views.
Exact source saved to `Saved/Diagnostics/ImperialSpear/PommelLotus/Selected_Pommel_Preview.blend`
and `Working.blend`. Body65 rows/3.2mm crest, fuller budV5, darker carved channels.
Corrected cavity gate preserves the prior head render pixel-for-pixel. Original70
components and four atlas PNGs remain unchanged. Later crown proposal not applied.
Export attempt stopped on LOD1 color interpolation outside the authored range;
mixed current outputs need a completed refresh/readback before Unreal use.
This selected-source checkpoint supersedes the older exported-build entry below.
[Current selection and resume details](Docs/ImperialSpear.md).

**Bodyflip October31 - separate mode timelines, local:** Run/Walk/Idle/Space
now persist independent markers, trim/loop, speed, playhead and gait start controls
per scene. New modes start empty; scene copy and refresh retain every mode.
Rapid mode switching preserves pending playheads and rejects stale restoration.
33 scene/mode checks and the no-op generation guard pass. Current Space's two
markers matched the saved Run capture exactly: retained under Run, cleared from
Space. Other scenes/world tuning preserved; backup mode-playbacks-before.json in
Saved/Diagnostics/BodyflipPort20261030. First reload should be Ctrl+R, because the
old Refresh button saves old state first. No motion solver/native changes or push
in this step. Earlier performance/airborne-slash work remains unfinished.
See Labs/BodyflipLab/README.md for scope.

**Bodyflip October31 - earlier no-op freezes / post-hit pelvis aim return:**
Historical package evidence; latest lab experiments are summarized at Resume here.
Marker-click jitter and rounded time-field commits rebuilt the full motion.
Canonical event equality,4px marker drag threshold, release-only commit and
motion-input equality now prevent this; identical pending prepares are shared.
76editor checks plus invalidation checks pass. Real motion preparation remains
expensive/synchronous; no general speedup claim. J2 zero-twist command stays on
world X; pelvis aim bank turns that flip into torso-axis rotation. Remove its
post-hit hold: pelvis aim now returns over Attack out starting at Hit, while
spine/shoulder follow-through remains. Current HitF174.4405 unchanged; pelvis
aim endsF189.4405 vsF199.9245. Transient aiming rotation still exists.27return
checks,4physical aim cases,19flipless attacks/684samples exact; native slash
V8 parity8frames/1723numbers exact. Runtime891446bytes, SHA256
5ed93ac7db5248d4c727e244e6304bbcfc0c34d874984c20ddf51b6d840c402f.
Saved Aim0.8/other state retained. No desktop/editor/build/push. Refresh to load.
Landing-to-NN discontinuity remains separate; see Bodyflip README and
Saved/Diagnostics/BodyflipPort20261030/twist-return-corrected.json.

**Bodyflip October31 - pelvis inspection view added, local:** `Pelvis view`
appended after Hand cones. Camera follows actual displayed pelvis translation
and full rotation; hides scene/debug overlays, keeps character colliders/weapon.
Starts from current view; orbit/pan/zoom/playback remain, off restores prior
camera. Scene-saved camera option; no rollout regeneration or motion/tuning edits.
36camera checks pass including arbitrary rigid-frame invariance below9e-15m.
Use Refresh to load. User is inspecting slash quality; attack solver unchanged
in this step. No desktop control, native changes or push. See Bodyflip README.

**Bodyflip October31 - earlier airborne slash contact solve (superseded in lab):** J2
full-aim miss56.86cm -> original hit marker0.0077mm; actual blade3.26cm from centre
of12cm sphere,4.998cm atF174. Fits contact position, independent shoulder/spine,
pelvis-local yaw and weighted preference against pelvis tilt. Coarse solve then
240Hz playback-accurate refinement; no per-playback solve. Elbow/wrist source
motion retained; flipless19attacks/684samples exact. Four physical position cases
pass; native V8 six cases48frames/10577numbers exact. Runtime890981bytes, SHA256
f15a76259e321254c5fabd66752eae0d417add02b944fdb05e4a3d4e219c44d3.
Active Aim restored100%, user's Leg follow0.10 and other state retained; useF5.
No desktop/editor/build/Blueprint changes/push. See lab README and
Saved/Diagnostics/BodyflipPort20261030/slash-weighted.json.
**Separate unresolved landing issue:** hand_l landingF194 leads to~110.7deg
right-wrist stepF198.76 in NN return. Endpoint/keyframe projection trials did not
fix it and were removed. Do not report complete landing continuity as passed.
Evidence slash-landing-audit.json; airborne interval is separately verified.

**Bodyflip October31 - foot push/follow corrected, local:** Foot contact now
releases at the accepted gameplay push impulse; the old ~8ms reach-to-99% stroke
was overextending the constrained hip/ankle and pulling the foot forward atF145.
The existing finite-speed extension follows the last world point inside final
momentum balance, then performs one inertial Leg return. Knee plane follows the
hip while endpoint aim remains world-directed. Released toes extend toward the
shin at existing Roll speed within ankle limits, rather than freezing at35deg
above the surface. Leg follow option remains in place; default/active scene
0.20 ->0.08s, all other saved state verified identical; F5 loads it. Zero follow
retains direct inertial return. Jump% impulse/carry, misses and hand timing kept.
Focused5564, earlier leg1126/release364/physical566, strength14 and hand5 checks
pass. Historical long inverted-follow exact-aim test remains joint-limit-bound;
see topic scope. No desktop/editor/build/restart or push.
[Behavior, tests and receipts](Labs/BodyflipLab/README.md).

**Bodyflip October31 - physical aim fixed for current slash, local:**
Follow-up: user requests100% Aim by default. Updated core/UI/native settings source
and active saved scene only, preserving other tuning/camera/playback/scenes.80% was
the original hard-coded lab default, not user-selected necessity. F5 reloads the
saved edit; old page Refresh would first save its stale in-memory settings. Runtime
repackaged; native default header remains pending build, no editor operation.
Source checkpoint09476308 pushed and remote verified before this change; it
excludes pending shared native C++ integration/generated packages/model exports.
Current aim omitted carrier displacement/drift (3.27m vertical at hit), seeded
from static motion and quit after two iterations. Prediction now uses resolved
world motion; bounded cached solve starts neutral and allows the attacking
shoulder to contribute within limits. Full Aim hits within10.046cm of the12cm
target centre; the saved80% setting intentionally leaves30.754cm/17.04deg and
was preserved. No new controls/gates or jump-strength changes. Four physical-aim
invariance cases pass;19attack/684sample flipless preservation exact. Runtime
repackaged; no editor or live state changes. Fix remains local after checkpoint.
[Current behavior, performance and limits](Labs/BodyflipLab/README.md).

**Bodyflip October31 - F145 foot-release snap fixed:**
Release history was rebased before floor projection, causing a false penetration
correction and capturing the wrong departing leg. Projection now runs in world
coordinates before rebasing; physical flight starts with that captured constrained
articulation while retaining contact momentum/COM velocity and the Jump% impulse.
No new blend/gate/control. Saved F144->145 thigh change53.74->3.94deg; release
seam0.121mm ankle/0.085deg knee. Both current markers still push at the same times.
364 focused,1126 prior leg-continuity,566 physical checks,14 strength/five hand
cases pass;19attack/684sample flipless Space gym remains exact. Runtime refreshed;
no editor/live state edits or push. Older absolute world-follow assertion remains
a documented pre-existing failure under the final rigid momentum correction.
[Details and receipts](Labs/BodyflipLab/README.md).

**Bodyflip October31 - predictable Jump % restored:**
Follow-up: fixed axis-only saved J2 canceling during LOAD when the other toe
touched ground atF141.5. Additional extremity contacts during an accepted PIN
now remain support contacts, with collision response intact, until lifted clear.
Head/torso and approach/free-fall landings unchanged. J2 now pushes2.4s and
releases2.40792s. RISE/FALL uses resolved COM velocity including carrier bias.
24 ownership/phase checks plus five hand cases pass; app replay confirmed.
No saved-state/editor changes; runtime repackaged. See current lab README.
Successful surface pushes now set COM takeoff energy directly from Jump%, plus
the existing Rebound option. Previously percentage was only a stopping threshold
for knee extension; early reaction release silently under-delivered regardless
of requested strength. Shared100% height1.032640m; with rebound0,200%=2.065280m.
Contact impulse at release, same load/pin/recovery and tangent carry; no new
impulse on zero% or a miss before pushing. Applies to feet/hands with/without
spin. Angular solve unchanged; non-spinning surface jumps correct translation
only, approved flipless Space gym unchanged. Saved J2 comparison70%~.83m versus
200%~2.16m with existing rebound.14 strength cases, five hand cases,566 flight
checks pass. No live scene/Blueprint/editor mutation. Lab/runtime updated.
[Current behavior and receipts](Labs/BodyflipLab/README.md).

**Bodyflip October31 - active-spin physical balance, no-spin art preserved:**
Follow-up: fixed lost jump height from averaging the last4.17ms of an accelerating
push. The release seed now uses a second-order instantaneous COM derivative from
contact-side samples. Saved J1 upward speed3.074->4.366m/s, ballistic rise.482->.972m;
contact drive/Jump% unchanged.562 flight checks, five hand cases and exact19attack
no-spin preservation pass. Lab/runtime updated; no live scene or editor changes.
Before the explicit Jump% contract above: old J1 COM rise1.226m versus ballistic.972m
(~21% lower). Old root speed4.629m/s exceeds COM4.366m/s, and animated recovery
adds.138m relative COM lift after release. Derivative fix alone does not restore
old height. The subsequent launch contract above supersedes this ambiguity.
The scene timings and aim measurements below predate this velocity correction.
One shared-mass3x3 COM reaction solve now balances final attack/aim/released-limb
motion, with ballistic COM before collision/landing. `3D momentum` appended at
bottom of More options (on=fullvector, off=commandedaxis component). No-spin
microgravity art deliberately remains exact:19attacks/684samples pass globally
and after aiming, both modes. No physicaltrack is created for inactive spin.
Saved J2 fullmomentum error<.00043kg m^2/s; prior F140-150 reversal removed.
Five hand/contact cases pass; double carrieroffset atrelease fixed (seam1.64um).
Core≈.7-1ms per60Hzframe at240Hz; separate cached targetplanning≈134ms and full
saved-scene preparation8.77s. Aim is bounded/approximate: saved3D residual≈4.9deg
toward partialaim goal, axis≈22.9deg; no promise of arbitraryphysical hitdirections.
Actualapp/nativeadapter6frames agree; nativeJS package updated. No C++/Blueprint/
editor rebuild, scene mutation or preview-art rewrite. Detailed receipts/scope:
[Current Bodyflip handoff](Labs/BodyflipLab/README.md).

**Bodyflip October31 - physical audit before balance:**
Current saved slash sampled F134-194 through all stages,240/480Hz differences.
All25body momentum about COM along flip axis35.45 atF140 ->-2.00 atF150 ->35.00
atF160 kg m^2/s, despite no contact (minimum collider clearance8.78cm F138-164).
Opposite-angle compensation is an authored momentum target, not a conservation
target; smoothing changes it afterward. Fixed-axis spin ignores moving-limb
momentum, then support-leg follow and aim change it again without reaction.
Post-Hit pelvis return overwrites angular evolution; COM is also not ballistic.
Last joint-order fix removed a real bug but did not resolve these wider issues.
No production/state/editor changes in audit. Detailed findings, recommendation
and physical-audit receipts/chart are linked in the current lab README.
[Physical audit](Labs/BodyflipLab/README.md).

**Bodyflip October31 - compensation now includes joint limits:**
Fixed saved slash's pelvis slowdown caused by computing compensation from torso
rotation that was later discarded. Source, target and solver trials now obey
the existing joints; smoothed output and recovery do too, preserving COM.
F148-150 late spine01 rejection60.8deg -> numerical zero. Saved F144 pelvis
speed along flip axis40->93deg/s; F156406->313deg/s. Intended counterrotation
still changes visible pelvis speed. No percentage, timing, spin or scene edits.
56cases/2750samples across14attacks and both rig profiles pass, including zero
pelvis response to discarded motion, COM and deterministic seeking;17attack
entry and60aim cases pass. Native JS package refreshed; no C++/editor changes.
[Current details and receipts](Labs/BodyflipLab/README.md).

**Bodyflip October31 - live angular-distance arming, all19attacks:**
Direct to Armed now scales GT windup seconds by current->Armed joint angular
distance / accumulated GT windup angular distance. Includes the live harness's
with/without-forearms clock comparison. Removes fixed GT duration floor; keeps
the explicit Attack In minimum and existing smooth interpolation. Kicks share
the clock with viewer/manual paths; both throws now honor Direct to Armed,
retaining charge-specific post-Armed motion and release. Carrier spin and the
separate aiming correction are not part of articulation timing.
Current J2 slash arms in.230350s vs.333333s, hits at2.741053178vs2.844036587.
1141checks across19attacks, actual live-harness distance oracle,2571entry samples,
11221hinge-axis samples,2004kick samples,60aim and6native throw cases pass.
Runtime-only native package updated;48frames/10595values exact V8 parity.
No saved-state/desktop/editor/C++ changes. Lab README records scope and receipts.

**Bodyflip October31 - slash arm snaps fixed; Modified rotations removed:**
Removed the rejected experimental checkbox, setting and solver branch; fixed
combined world-axis spin remains. No saved scene/tuning/playback edits.
Saved slashL had an off-hinge forearm blend, then abrupt joint projection at
F148/F155. Arm keys now fit the existing rig before matching/interpolation;
source spine/legs and attack timings remain. Actual app F130-205 replay:
F148 shoulder/elbow/wrist13.79/13.11/15.00 ->4.25/.60/3.46deg per frame;
F155 28.12/28.10/28.57 ->7.23/4.40/2.64deg.17attacks/2700entry samples,
56arm cases/11520samples (lab/native, both entry modes),60native aim cases and
4381fixed-axis spin checks pass. Tests establish hinge-axis continuity; raw
polynomial angle overshoot still uses existing final joint projection.
Full native JS package rebuilt, native-slash V8 parity8frames/1729values exact.
No editor/desktop use or C++ change. Saved slash receipts under
Saved/Diagnostics/BodyflipPort20261030; current lab README has scope/details.

**Bodyflip October30 - commanded spin axis restored (default mode):**
User rejected the full-tensor experiment's unwanted twist on jump1. Spin now
captures flip/twist vectors in world space and applies inertia scaling along
their combined axis, so a front flip cannot gain an unrequested global twist.
Mixed-spin direction remains fixed between commands rather than following pelvis.
This supersedes full articulated momentum conservation; it is axis-controlled
animation with axial inertia scaling. Recoil/contacts/authored poses remain.
4381 regressions pass including delayed launch, moving poses, all tested axes,
Keep/reversal/zero; measured axis error below0.0000015deg, axial error0.000751%.
Saved260-frame rollout re-recorded, first flip stays in plane, no saved tuning
or markers changed. Runtime-only packaging updated; native parity receipt is
Saved/Diagnostics/BodyflipPort20261030/axis-native-parity.json. No editor use.
Both saved jumps now report Push (1.2354167s /2.2666667s). Native kick/foot/hands
parity passes all24frames with zero numeric differences. Served lab source verified.
[Current lab handoff](Labs/BodyflipLab/README.md).

**Bodyflip October30 - full-tensor conservation experiment (superseded above):**
spin.js now transports world angular momentum between authored commands and
solves full collider inertia plus orbital/intrinsic articulation momentum.
It no longer adds world-fixed flip velocity to a pelvis-following twist velocity.
4365 focused checks pass, including recoil/moving poses/Keep/delay/ramp/zero;
independent collider trajectories give max0.131deg direction error /0.539%
vector error, versus the old frozen-pose combined-spin ~80deg drift.
Runtime-only package rebuilt; native V8 parity24frames/5228values exact. No C++
build/editor or saved setup change. Old scalar-speed spin assertions are
superseded, not reported as passing. Current260-frame replay completes, but its
corrected rotation makes upperarm_l contact at2.2791667s before jump2's planned
push2.31875s, so jump2 now reports Miss. No timing/contact rules were changed.
Jump1's push remains1.2354167s. Free-flight segment vector error below0.179%.
Updated in-chat recording; receipts Saved/Diagnostics/BodyflipPort20261030/
momentum-*. See [lab handoff](Labs/BodyflipLab/README.md).
User accepted the changed pure-flip trajectory and will retime jumps themselves;
keep the full momentum correction and do not adjust their saved markers.

**Bodyflip October30 - typed Blueprint options built and verified:**
User requested normal Blueprint pins instead of JSON. Added typed Settings and
Spin/Pose/Attack structs, attack/push/pose/axis/sequence enums, and normal
Start Bodyflip / Queue Bodyflip Jump nodes. Jump %, Push With and At Time are
direct pins; option structs split into writable pins or Make Struct nodes.
All20 attack choices include None, Sweep Kick and Big/Small Throw. Native pins
use centimetres/seconds/degrees; inheritance distinguishes unchanged spin from
explicit zero. No motion solver changes. Legacy JSON nodes remain deprecated
to preserve prior wiring. UHT and normal build-blueprint-options-retry.log passed.
Unity regrouping exposed a missing UObject/Package.h include in BombBake; only
that include was added, no bomb behavior changed. Source-to-lab mapping checks48
settings/20 attacks. Native Controls.BlueprintOptions passes with zero errors or
warnings: callable reflection, writable/splittable option fields, all attack IDs,
inheritance versus explicit zero, defaults and cm/seconds conversions. Report:
Saved/Diagnostics/BodyflipPort20261030/Reports/blueprint-options. Reused host exited;
no user editor or Play restarted. Updated DLLs load on the next project launch.

**Bodyflip October30 - throws/predictive aim and native port validated:**
Approved jump/landing/starting-yaw checkpoint67516390 pushed and remote verified;
exact saved scene in Labs/BodyflipLab/approved/2026-10-30. New local integration:
Big/Small approved throws share marker UI and Jolt world; actual projectile COM
exit velocity includes body translation/spin. Future complete-body aim honors
Armed/Hit/Release deadlines, joint limits, spine-first bend and necessary residual
pelvis tilt. Legal local-coordinate path removes intermediate rotation snaps.
714 melee target cases,51 dense240Hz paths,72throw cases pass; actual collider
sheets inspected. Default Spin lag60% now covers every spin change; saved0 retained.
878 exact parity checks for lossless optimization; projection median~9.7% faster,
full spin unchanged. Current scenes untouched. Native solver/NN/Jolt port passes
all five final actual physical cases: kinematic/sim, Big Throw, Small Throw,
one-hand push and two-hand push (Reports/release-final). Native entry plans from
the held current pose; hand follow/return continues through landing. Base errors
are5.45cm maximum/.231cm RMS,19.35deg maximum rotation. Both palms register solved
floor impulses inside the push interval. The one-hand segment discrepancy is
2.954cm against the unchanged3cm limit: a narrow pass, not zero physical error.
Actual PHAT hinge/connector IK passes7,224 checks. The physical hinge supplies
the bend plane at near-straight elbows; separate hand departure boundaries avoid
recursive spin-history reads.248 checks/73frames cover release and reverse seek.
All five actual collider sheets and dense hand contact/release frames inspected.
Native profile supplies23 bodies/78.25kg, actual inertia, constraints and shapes;
saved PHAT/tuning and ordinary lab defaults remain unchanged. No motor or test
threshold was relaxed. Normal build-entry-return.log succeeded; the isolated
DLL-copy host is reused, sharing assets and excluding PDB copies.
Private single-thread ORT continuation matches64poses/4profiles within9.65e-6;
V8/ownership/trim/cancellation/budget/finite-parent checks pass. Saved260frame
scene prepares with real NN in62.737s. These are preparation costs, not gameplay
FPS. Earlier lossless wrist/contact replay matched8complete frames/1,740values.
Release cache now matches52 commands against current uncached code, reducing
launch computations54 to10; the latest paging-affected timing shows no speedup.
Final packagecaf24be9 matches Node/V8 exactly on24frames/5,216 numeric values;
the ordinary lab profile retains20 byte-identical complete outputs.
Native CarrierHeading passes. The entry test has105 checks and common blend
checks39; three obsolete F59 knee expectations fail identically with and without
the transition fix, with all other76 checks/metrics unchanged.
Storage follow-up: after explicit user authorization to use the Recycle Bin,
eight disposable cache/obsolete-engine/archive paths (181,474,003bytes,173MiB)
were recycled, with no permanent deletion. Earlier rejected cleanup did nothing.
Receipt: Saved/Diagnostics/BodyflipPort20261030/recycled-files.json. Working host
binaries, packaging dependencies and verification evidence retained. Bin contents
still occupy disk space until emptied. User editor/Play, wiring/tuning, scenes and parallel
Foot IK work remain untouched. Native use is opt-in through StartBodyflip; the
new integration is local, not part of the previously pushed checkpoint67516390.
[Native rig contract](Docs/BodyflipNativeRig20261030.md), [Lab](Labs/BodyflipLab/README.md),
[aim audit](Docs/BodyflipPredictiveAimAudit20261030.md),
[native status](Docs/BodyflipNative.md).

**Bodyflip October30 - starting yaw (approved checkpoint67516390):**
Start yaw appended to bottom of More options, default0deg. Facing only; world
root velocity/path unchanged.180deg uses rotated gait-phase history and the
existing seeded NN for backward locomotion, with trim-bounded recurrence.
Idle/Space rotate pose only; jump sources follow initial heading.3132 checks and
actual F0-60 backward NN pass;809 landing checks retained. Scene untouched,
Checkpoint pushed; Refresh loads. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October30 - landing pelvis heading / continuity (approved checkpoint67516390):**
Landing root yaw follows pelvis facing; both history poses and root commands
enter the unchanged NN in that frame, then predictions return to world space.
Root momentum/path unchanged. Current twist300 landing179deg stays backward
through F228;808 previous-scene +809 backward-scene checks pass,1126 earlier
jump checks pass. No scene writes or server restart; included in checkpoint67516390.
[Current details](Labs/BodyflipLab/README.md).

Preceding continuity fix:
F195 traced to two landing blend errors: rotating virtual-root reference back
to NN identity orbited the physical pelvis, and backward extrapolation of a
future NN endpoint invented the right thigh loop. Rebase only the virtual root,
retain physical world pose, then transition to the actual seeded rollout.
Current F194->195 thigh135.3deg ->3.1deg; dense recovery COM forward>=4.51m/s,
root remains5m/s.667 landing checks and1126 prior jump checks pass; old code
fails new detector. Historical body-landing F131 assertion fails identically
before/after; old trim-generation incremental-request assertion also fails on
both versions. Offline collider frames inspected; scene untouched, Refresh loads,
not pushed. [Details/evidence](Labs/BodyflipLab/README.md).

**Bodyflip October29 late - leg continuity / Follow cam (current jump behavior, local):**
Existing camera checkbox now Follow cam (checked follows, unchecked free from
current view; rechecking centres agent). Fixed current F61 knee lock, F80 thigh
branch switch and second-push stop/start. Foot push is now driven by seeded
finite-speed knee extension, with outgoing velocity carried into flight and
requested launch speed as the actuation budget; no8ms root-first impulse squeeze.
World contact planning includes inherited COM rotation. Airborne foot markers,
like hand markers, own their incoming body/root continuation instead of inheriting
the previous carrier's future locomotion landing. Released foot uses one world
reach then one inertial return; removed the two-frame entry and per-frame slerp
branch change. Carrier completes a contact-side release boundary before free
ticks, and final foot-clearance IK preserves intended COM. Hand driver retained.
F60/F61 knee41.84/36.17deg versus41.68/2.60; F79->80 thigh9.39deg versus122.9.
Both markers push; procedural push/release timing changes, marker times retained.
1126 current-scene checks,300 follow,120 zero-follow,96 paired-bounce and693
flat/inclined/wall-skew driver checks pass;
9 hand-recovery and6 strength/spin cases checked; actual collider sheets inspected.
Small~0.22deg zero-spin projected hip boundary difference remains in edge cases.
Current generation plus369 projected samples~3-5s. EvidenceSaved/BodyflipLab/
LegContinuity/. Live state/Unreal/desktop unchanged; no server restart or push.
Refresh loads it. [Current details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - initial world-space leg follow-through (superseded above):** Released foot
keeps aiming at its last push point through whole-body rotation, then returns
to the moving animation. Leg follow s appended at bottom of More options,
default0.20; existing Leg controls return. Zero disables follow. Damped extension
carries release knee speed without snapping to maximum reach; no renewed pin,
extra force or limb stretch. Actual departing pose and COM retained. Hands keep
independent follow/return. Saved two jumps still push.300 world-aim/subframe/
length/COM/seek/UI checks and122 zero-follow release checks pass. Evidence:
Saved/BodyflipLab/FootFollow/. Live state/desktop/Unreal unchanged; no push.
[Details](Labs/BodyflipLab/README.md). Refresh loads it.

**Bodyflip October29 - F120 knee pop corrected (local):** Airborne foot SUPPORT/
LOAD/PUSH now uses posed-body collision in the carrier too; the standing capsule
had incorrectly lifted the root15.25cm. Release recovery also applied later root
offsets to its past planted pose, rewriting the knee angle. It now seeds once
from the actual departing contact/root offset/velocity, using completed carrier
ticks. Current F119->F120 right-knee bend46.8->6.8deg becomes89.1->81.5deg. Both
pushes retain timing.122 subframe/length/offset/seek checks and67 crouch checks
pass. Existing blend controls/contact/limits retained. No live-state, UI,
desktop, Unreal changes or push. Saved/BodyflipLab/Knee120/; Refresh loads.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - foot buildup begins before contact (local):** Larger
grounded jumps start the extra tier time before their marker (Y100/full200ms by
default), then continue the same crouch through approach and load. Airborne
foot buildup starts at the marker. Root momentum and upper-body source motion
continue; grounded knees bend while gait feet retain their world trajectories.
Existing tier duration/depth controls apply; no new UI. Failed approach also
blends the crouched body back. Current run: prepF44/contactF56/pushF60,9.65cm
displayed lowering at contact and12.10cm authored depth on push;5m/s root retained.
Both saved jumps push.67 focused and335 momentum checks plus isolated airborne
root/capsule regression pass; trim extension retains prefix. Older aggregate
handBoth25 pin assertion also fails before this change, recorded in README.
No live-state/desktop/Unreal changes or push. Evidence: Saved/BodyflipLab/EarlyCrouch/.
[Current behavior](Labs/BodyflipLab/README.md). Refresh loads it.

**Bodyflip October29 - prior first-jump LOAD diagnosis:** F56 Run
at5m/s,100% jump,300ms buildup/15% bend. Reach reserve ends loading after29.17ms
with14.58cm root advance;300ms lowering curve reaches only0.097cm of12.24cm
depth. Displayed pelvis drops0.105cm. Earlier preparation/stance travel is needed
for a deeper crouch; squeezing full depth into29ms would snap. No load/support
tuning changed. Evidence: Saved/BodyflipLab/LoadDepth/. No live state edits.

**Bodyflip October29 - reachable airborne foot rejump fixed (local):**
Second foot jump was rejected because its buildup used the standing capsule:
root was below the floor reference, so capsule correction lifted it20cm and
forced a reachable73.5cm leg to91.2cm (>80.8cm limit). Airborne foot loading now
uses posed-body collision, excluding pinned foot/ball; grounded capsule behavior
unchanged. Saved second push succeeds with upward release; first jump unchanged.
Miss reason corrected to distinguish actual spin release from no push travel.
New frozen-bank regression and335 momentum checks pass. Existing F136 hand
landing assertion also fails against pre-fix source; recorded separately.
No live state/Unreal edits or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - separate hand return slider (local):** Hand return
directly below Body/Leg in the left panel (user placement correction),
default0.4s, independent of existing legBlend.
Hand entry/abort/follow recovery and caches use the new clock; left Limb label
now Leg. Hand follow remains hold duration. Live state untouched.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - hand recovery double blending fixed (local):** Saved
F146-150 rush came from re-blending an already blended pose plus continued
contact aiming during return. Corrections now use untouched animation; final
projection preserves blended direction during return. Hand follow0.1s and
Limb0.2s unchanged; saved F140-160 trace spreads return earlier, peak shoulder
step15.98 to13.31 degrees. No live state edits.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - independent hand cone angle (local):** Hand cone degrees
appended at bottom of More options; existing Cone degrees now feet only.
Hand candidate ranking and approach both use independent handCone. Legacy scenes
inherit prior shared angle; later saves retain both values. Independent15/60 and
60/15 queries, migration, bounds and syntax checked. No live-state edits.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - hand cone diagnostics (local):** Added Hand cones at
the end of the viewport toggles. Both prepared cones visible; yellow crosses
distinguish chosen contacts from large pre-cone ideal circles. Released hand
circles turn red. Saved F132: L contact~22cm from ideal; R already released by
spin/contact limits. Diagnostic-only; motion/state untouched.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - support target toggles (local):** Foot targets and
Hand targets appended to the viewport checkbox row. Both default on; hide/show
active support circles and contact guide independently, without recomputation.
Paired hand candidates both green. Normal scene persistence; live state untouched.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - world-space hand follow-through / playback cost (local):**
Added Hand follow s at the bottom of More options, default0.25s, followed by
existing Limb recovery. Released pushing arms aim back at captured world points
from their moving shoulders; final anatomical projection preserves that aim as
far as joint limits allow. Two-frame continuous entry; actual push/COM/release
timing unchanged. Prepared foot/hand pose reuse and60Hz kinematic sampling reduce
saved-scene offline motion p95 from25.9ms to1.92ms (excludes rendering); simulated
mode stays240Hz. Arrow steps and Step wrap inside trim brackets regardless of Loop.
Seven trim cases and six hand/spin release cases pass (max seam0.077mm). Browser
global/served-source checks pass. User now testing live; no state/desktop/Unreal
changes or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October29 - continuous COM spin and simulated tracking (local):**
Flip/twist now specify target deg/s; blank Keep inherits through foot/hand pushes,
explicit0 brakes, and rotation continues until real landing. Delay is after
release; Accel/Brake remain in More options. Inertia % appended there defaults100,
scaling by reference/current axis inertia. Shared25-body/45kg model matches actual
Jolt mass properties; all rigid turns preserve COM. Legacy nonzero angles migrate
in memory to old mean speeds, duration/absolute-angle controls hidden. Paired pins
release the incompatible hand; loss of both ends the push. Release blending uses
collision-corrected sockets, keeping COM and gravity.0% actions now collide too.
Both modes use shared legal joints and physical/visible-body clearance. Sim uses
real dynamic bodies, pelvis-only absolute position and compatible attachment
velocities. Fast turns substep adaptively. Seeded landing NN blends from actual
contact using Body time.33 Jolt cases/12,490steps plus9 contact cases/3,024steps;
all17 attacks, all12 axes, poses, inheritance, hand release and3600deg/s tested.
Saved3.4s motion:1.53cm peak joint-target difference versus old>1m; full collider
frame sheets reviewed. Attack self contact can still transiently deviate8.2cm.
310 COM checks pass. Live scene/settings/playback unchanged, no desktop/Unreal,
restart or push. Refresh loads. New behavior supersedes finite-angle timings below.
[Current details, limitations and evidence](Labs/BodyflipLab/README.md).

**Bodyflip October29 - full hand-push/NN landing replay corrected (local):**
The earlier contact-only fix missed the cause: authored loading consumed nearly
all arm compression, leaving a3.26ms partial push and downward COM release.
The elbow then genuinely landed atF139.75; actual NN recovery raised the body.
Longer authored buildup now reserves usable push travel by testing at most eight
earlier integrated endpoints when the drive is truncated before reversing its
incoming velocity. Chooses the longest complete drive, with energy from that
endpoint only; no root braking, limb stretching or changed landing eligibility.
Same current scene/contactF134 now loads4.17ms, pushes33.75ms, releases2.27125s
with COM vy+2.36m/s. Airborne through trim2.55; offline extension lands pelvis
atF172. Actual seeded NN recovery also resolves posed-body clearance, preventing
its knee from penetrating the floor while retaining root/joint rotations.
Whole sequence rendered with actual collider geometry throughF204; real17-frame
NN continuation used one bounded single-thread CPU worker.106 body-landing,
127 travel/36cases,96 legacy/paired,335 momentum,310 COM,9 recovery,30 trim and18
release checks pass, plus tier cases. Existing successful/legacy output unchanged.
Scene/markers/playback untouched; no desktop/Unreal, restart or push. Refresh.
Evidence: Saved/BodyflipLab/FullHandMotion/. Supersedes prior F136/F139.75 outcome.
[Current behavior and verification](Labs/BodyflipLab/README.md).

**Bodyflip October29 - hand release contact no longer ends flight (local):**
Current F128 hand marker released at2.25534s; the same lingering right-palm
contact incorrectly became a new landing3ms later. Released support now retains
its body-part/surface contact identity until geometric separation. Collision and
normal response remain; later recontact or another body part can still land.
No timer or change to push/plant/release. F136 now FALL with1.75cm body clearance;
actual later upper-arm landing2.32917s.18 release checks,100 body-landing,310 COM,
9 recovery and30 trim checks pass. Current state/timing preserved; no live NN,
desktop/Unreal, restart or push. Refresh loads.
[Current behavior and verification](Labs/BodyflipLab/README.md).

**Bodyflip October29 - actual airborne body landing (local, unpushed):**
Jump flight/hand support now collide using posed renderer-matched body volumes,
replacing the standing capsule that landed above the floor. Locomotion keeps the
native standing capsule. Real descending body contact on an upward surface seeds
locomotion from the exact visible pose; root/history rebase does not lift the body.
Intended support palms keep their push solver; other body contact can interrupt.
Hand preparation no longer inherits an earlier jump's hypothetical landing root.
Saved F131 remains airborne with57.55cm body clearance. Unchanged F136 hand marker
then meets real right-upper-arm contact at2.29583s before both palms plant; Miss
reports the contact. Offline1.95s marker completes paired release at2.23926s.
95 geometry/handoff checks,310 COM,9 recovery,335 momentum, tier/contact and30
trim checks pass. Landing test uses a deterministic policy stand-in; no live NN
or desktop visual QA. User scene/playback/markers untouched, no Unreal/restart
or push. Refresh loads. Supersedes earlier capsule-based landing/outcome timings.
[Current behavior and verification](Labs/BodyflipLab/README.md).

**Bodyflip October29 - composite supporting-foot choice (local, unpushed):**
Auto selection now scores actual sole-to-contact distance after the cone, minus
bounded forward placement along surface-tangent velocity. The previous ankle
travel metric included reorienting into Plant even for grounded feet: reported
soles were both~1.8mm away but ranked20.8/12.6cm. Lead preference fades at rest;
high front feet can lose, invalid cones stay unavailable, manual choices and
penetration handling remain. Stable1mm score tie; no scrub history. Existing
phase tooltip shows contact/score, no added/rearranged UI. Hand choice unchanged.
338 selection checks cover noise/rest, reversed/sideways travel, height, finite
edges, slopes/walls, old inclined regression and96 real gait poses. Momentum335
and tier/contact/trim checks pass. Saved first jump now selects L, loads210.4ms
at2.00002m/s; later hand still pushes using existing R-hand fallback. This
supersedes the previous trailing-foot22.9ms/paired-hand outcome below. No state
write, desktop control, live NN/Unreal/restart or push. Refresh loads.
[Score, current replay and verification](Labs/BodyflipLab/README.md).

**Bodyflip October29 - jump buildup momentum corrected (local, unpushed):**
X/Y/full Jump % tiers remain, default35/70% thresholds and100/200/300ms.
Options stay at the bottom of More options. Longer buildup now lowers the
pelvis relative to the root and bends the planted limb; other joints keep the
current NN or jump-animation motion. Removed the rejected spring pulling the
root toward the plant, free-leg IK and separate crouching-root workaround.
Root keeps incoming momentum plus gravity; only capsule contact removes inward
normal velocity. Reach/compression can end buildup early instead of braking.
Base push duration/strength and small-tier behavior retained; equal times use
the original path. Body blending recovers pelvis height after release. Both
palms fit against the lowered body; wrist caches reset when loading commits.
335 momentum/source-motion checks, tier/geometry/trim/save/UI suite,96 legacy
bounce,310 COM,9 arm-recovery and12 wrist checks pass. Current first jump stays
at2.00002m/s; its trailing foot ends loading at22.9ms on reach. The later paired
hand push completes200ms and succeeds (supersedes previous miss report).
No scene/playback write, desktop control, live NN/Unreal/restart or push.
Refresh loads. [Details and verification](Labs/BodyflipLab/README.md).

**Bodyflip October29 - F142 hand recovery snap fixed (local, unpushed):**
Saved Body0.4s/Limb0.2s setup exposed a45-51cm hand discontinuity atF141.225:
arms finished Limb recovery then re-entered the unfinished Body blend. Hand
Body recovery now excludes the supporting arm chains; Limb alone owns their
return, followed by the target animation. Free arm/torso retain Body timing.
Nine timing/single/both-hand regression cases,310COM checks and12wrist cases
pass. No tuning, UI, saved playback, foot blending or contact changes. Refresh
loads the fix; no service restart, live NN, Unreal or push.
[Details and verification](Labs/BodyflipLab/README.md).

**Bodyflip October29 - hand playback performance (local, unpushed):**
Saved Both hands setup reproduced repeated raw/contact/COM solves: four240Hz
ticks could evaluate the hand source12times per displayed frame, with catch-up
amplifying stalls. Shared per-segment hand pose caching now retains the expensive
support/blend interval, merges only floating-point drift at fixed ticks, and
bounds arbitrary-time/angle caches. Capsule contact corrections reuse only the
same source frame and exact root; returned pose arrays remain private copies.
Same offline scene's hand approach drops from18.9ms to0.56ms mean per displayed
frame of motion work, excluding physics/rendering.32 checks/818 before-after
frame comparisons pass (saved scene difference4.27e-13), plus310COM checks,
9paired-hand/12wrist cases and30trim checks.240Hz contact checks, motion,
COM/wrist constraints, trim-only preparation and incremental extension retained.
No UI/state edits, live NN, Unreal, service restart or push. Refresh loads.
[Details and verification](Labs/BodyflipLab/README.md).

**Bodyflip October28 - two-hand pushes and hand COM (local, unpushed):**
Push with appends Both hands. Shared torso, real two-palm capture/wait, one drive;
individual arm/capsule constraints, ordinary Auto fallback when pairing cannot
work. No UI rearrangement or extra timing options. Legal wrist pitch stops short
of flattening when needed to clear the displayed forearm capsule; twist and Jolt
bounds unchanged. Current saved90-degree/50% scene can pair: right palm first,
left95.8ms later. Saved scene itself remains left-hand mode.
COM audit confirmed artificial acceleration from airborne torso/arm motion and
recovery (previous release blend added~2.17m/s upward). Airborne approach now fits
whole-body translation and wrist targets together; actual floor/capsule/palm
contact permits external forces. After release, completed animation/flip/attack
poses and root share one COM trajectory seeded from actual release position and
velocity. Capsule subframe interpolation, paired velocity projection and grounded
wall classification corrected. Hand ascent timing/paused flight velocity use COM.
310 inertia,57 current-scene,12 strict wrist and96 paired-drive checks pass;
focused paired/UI/trim checks also cover fallback and finite-edge misses.
Saved single/pair free-approach COM residual<2nm; released residual<4e-15m.
Foot prefix and original single-support drive preserved. Earlier foot-flip COM
drift remains outside this hand change; its actual incoming velocity is inherited.
Cached offline checks/collider sheets only; no saved-state/UI/Unreal/NN/service
restart or push. Refresh loads it. [Current behavior](Labs/BodyflipLab/README.md).

**Bodyflip October28 - wrist-limited hand support (local, unpushed):**
Palm contact now bends backward relative to the solved forearm, retaining allowed
incoming twist/deviation instead of adding a world-space hand twist. A palm that
cannot flatten within its wrist pitch range stays inclined. Shared wrist.js and
physics.mjs retain the existing Jolt45/40/55-degree limits and reference frames;
3,408 tests include agreement with the actual WASM clamp below5e-7 rad.
Arm/contact/capsule composition and subframe samples use the same constrained
hand orientation. Retreat comparison removes changing palm-clearance offset,
while preserving finite-edge failures. Both hands in Idle/Walk/Run pass the
existing grounded geometry checks. Twelve strict wrist/contact cases include
half-ticks, inclined/wall contacts and finite-edge failure; added twist<4.2e-7rad,
pin error<1.8e-15m. Exact57-check saved motion regression and collider sheets pass;
source handoffs below retain their earlier numerical receipts. Updated legacy
suite:405 checks/6,193 poses, zero-load pinning, legal misses and18 unchanged foot
comparisons. No UI/state takeover, Unreal/NN work or service restart. Refresh loads it.
[Wrist behavior and tests](Labs/BodyflipLab/README.md).

**Bodyflip October28 - trimmed generation and hand-push correction (local, unpushed):**
Edits prepare only through trimOut. Extending the end bracket retains the sequence,
segments, capsule/IK caches and recurrent landing-NN state; later markers wait.
Generated NN output has at most one interpolation frame past the boundary; source
clips and required root-command lookahead remain available. Bracket release still
restores the cursor. Recompute clamps a cursor outside the new prepared range.
Refresh captures playback before cancelling obsolete preparation. 30 offline trim
checks cover extension/prefix equivalence, seeks/edits, 0% actions and pending NN.
Cancelled seeks/bracket previews cannot extend a newly edited trimmed sequence.

The saved Scene 2 hand push follows a 180-degree flip. Earlier hand checks missed
its capsule correction: root/pin mismatch produced a 5.75 cm release teleport,
then an unrelated foot-jump pose drove a thigh through the torso. Hand loading now
resolves capsule and arm reach together. Torso/arm recovery follows the incoming
raw articulation with bounded elbow momentum, avoiding the old jump's obsolete
future landing NN. Hand planning separates carrier root axes from body flips;
shoulder clearance uses the surface plane, and the palm heel clears its actual
forearm end cap. No usable push travel means no active impulse.
Grounded hands now use a forward hip hinge, prepared leg rotations and an
outward elbow plane; no per-frame thigh-frame switch or arm/knee crossing.
Release enters the pelvis-aligned fall loop instead of walking in midair.
57 exact-scene, 423 isolated/6,350-pose and six grounded L/R cases pass; measured
grounded shell/plane discrepancies stay below 1 mm. Foot numerical paths match.

Existing Push with and Hand bend controls stay in place; saved foot defaults,
contact-selection rules and the foot path remain. The exact-scene regression
uses the committed gait bank, full capsule composition and collider measurements;
legacy isolated contacts and marker/persistence tests remain separate. Actual
collider sheets: Saved/BodyflipLab/HandReview/. This is kinematic support with a
root capsule, not a torque/finger-grip controller. No UI takeover, live-scene
writes, Unreal work, service restart or push. Refresh loads the change.
[Current behavior and verification](Labs/BodyflipLab/README.md).

**Bodyflip October28 - Sweep kick full turn corrected (local, unpushed):**
The initial import passed parity tests but both app/viewer shared broken motion:
zero-spin balancing opposed the source turn, and absolute pelvis return from Hit
erased its continuation. Full-body kicks now carry continuously unwrapped authored
heading around COM, balance articulation relative to that frame, and recover only
added balance while native pelvis tilt/follow-through continue. Root axes remain
the locomotion anchor. Same shared path for all three kicks; upper attacks unchanged.
No added duration or UI. Sweep completes-359.25deg like source; entire striking-leg
motion retained to<2.1e-15 through End.1,858 focused winding/continuity checks,
2,118 direct/2,316 normal integration,2,700 entry and9,500 aim samples pass.
Actual collider meshes reviewed offline across50 sweep frames including recovery,
with source/before/after/aimed comparisons and both existing kicks. See
Saved/BodyflipLab/SweepTurn/. Authored heading is prescribed: relative balance is
not a zero-world-angular-momentum claim. No desktop/browser control, live-state
writes, Unreal/NN/server restart or push. User Refresh loads both app and viewer.

Authored import:
Imported recoveries/sweepKick.fbx read-only:36 frames at30Hz, Armed8/Hit17,
right-foot full-body strike. Circular aiming reaches correction at Hit. App,
marker and kick-viewer selectors append Sweep kick; one authored variant.
Original16 datasets/binaries untouched. Ideal target derives from the existing
right-foot contact at17 because this FBX has no target annotation. Reproducible
exporter and source hash recorded. Direct-to-Armed knee-entry overshoot fixed
with bounded hinge interpolation only for invalid entry curves; native sweep
and valid old entries retained.232 old-entry samples unchanged;2,118 direct and
2,316 normal integration samples and2,700 all-attack entry samples pass.
No saved-state mutation, desktop/browser control or Unreal/NN/server restart.
User Refresh loads it. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October27 - spine-distributed static aim (local, unpushed):**
Aim adds pelvis yaw only. Pitch/roll correction is distributed across five
spines for hand/head/sword contacts, or the hip for foot contacts. Existing
pelvis animation/compensation is preserved. Non-chain local rotations, knees,
sockets and root stay unchanged; a common translation preserves physical COM.
Cached three-parameter solve fits the calibrated vanilla Hit contact direction
after articulation. Kicks/jabs/pike arrive at Armed; others at Hit. 100% fully
aligns direction; lower amounts scale yaw and bend. Radial reach is not forced.
Undo rotation remains at the right of the viewport row, default on; off retains
yaw and deformation after End/Out, including transitions between contact chains.
8,580 samples/all16 attacks/both entry modes and32 release-toggle cases pass.
Added pelvis tilt below6e-16 radians, direction error below9e-9. Saved Slash L:
156.71 degrees yaw,6.08 degrees total spine bend at100%,zero added pelvis tilt.
Saved80% retained. Camera nearly vertical orbit remains. No bodyflip logic,
UI control, scene writes or Unreal/NN/server restart. User Refresh loads it.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October27 - approved kick and attack-entry checkpoint:**
Pushed and remote-verified as `2e512bc1c005630c694ecb1a1a9e6b00dc2e30d1`
on codex/standalone-sim. Recovery:8958 files,1,073,713,440bytes, no LFS pointers.

User approved full-body airborne kicks, pelvis-only post-Hit recovery and
Direct to Armed for all16 attacks. Viewer, timeline and manual paths share the
same motion. The existing viewport checkbox (after Raw leg) skips pre-Armed
motion, reaches Armed no earlier than authored timing, then retains the native
strike/follow-through. Upper14 retain opposite-angle compensation and inertial
legs; kicks retain recorded striking-leg dynamics and articulated balance.
2596 all-attack direct-entry samples,1182 direct-kick samples,1314 original-kick
samples and84 off-mode cases/5100 samples pass. Manual variants/rates/aim,
moving baseline, COM/hinges, native upper motion, Armed continuity and seek
checked.90 sequence checks pass;32 overlaps2764ms. Scoped source/tests/receipts,
viewers and docs only; live scenes, screenshots, unrelated work remain local.
No desktop/browser control or Unreal/NN/server restart. User Refresh loads it.
Recovery inventory regenerated for the approved checkpoint on codex/standalone-sim.
[Current details](Labs/BodyflipLab/README.md),
[prior notes](Docs/Journal/Bodyflip-2026-10-27-pre-checkpoint.md).

**Imperial spear October28 — concept04 Lotus bud rebuild:**
Previous flattened-leaf model rejected. User selected Lotus bud and requested
a planned rebuild, then clarified a four-peaked FLOWER cross-section for the
MAIN BODY. Four radial ribs surround broad Bezier concave scoops; comparable
width/depth, axis diameter49.00mm and4.351mm scoop below peak chord.
The scoops now contain integral closed leaf insets (0.55mm recess,
0.10mm raised flat lip) with tapered tips. Circular necks meet stepped collars;
the lower seat has a straight land and separator. BudV3 has six recessed arched
petals, flat lip lands/inner bevel steps, seated root and beveled button throat.
70 other components and original4K atlas bytes
preserved. User explicitly requested the same existing head gold; the pommel
uses M_ImperialSpear_PBR and the plain gold atlas region. One material slot.
Bud extends31mm below prior cap; total2.231m. Shaft/head/grip fixed; grip
is1.266m from new tip. Source/game/FBX/GLB/LODs and previews refreshed.
End-on body and diagonal previews document the radial cross-section.
Triangles46,836/25,758/13,114;17 convex hulls, max60vertices,4 sockets.
Current source/UV/normal/material preservation, actual collision containment,
wood join and main/LOD FBX readback checks pass. Current audit:
`Pommel_Lotus_Verification.json`; previous leaf audits are rejected-stage history.
Unreal import/cooking/physics remain untested; appearance awaits user review.
Owned hidden Blender closed after bounded3-thread CPU work. No Unreal/Play/BP/lab
state changed. [Current handoff](Docs/ImperialSpear.md).

**Broad storage cleanup October26 —11.61GB recycled, about8.95GB net reclaimable:**
User authorized careful project-wide cleanup plus related disposable caches.
Recycled1,445 files (11,607,151,778bytes), with every bin payload SHA256-verified.
Loose Diagnostics reduced14.43→6.21GB:1,126 old bulk text captures/logs are retained
losslessly in `Saved/DiagnosticArchives/HistoricalBulkBefore20261019.zip`
(2,653,710,038bytes), independently read back/hash-verified before binning originals.
Current scripts/summaries/recent captures and code-referenced fixtures stay in place.
Also recycled exact duplicate old BP backups/generated copies, old crash dumps/
rotated logs, Python download/unpack caches, and the optional old project
`DerivedDataCache/Compressed.ddp`. Unreal may regenerate derived data on next use;
current Zen cache and incremental C++ caches retained.39,735 protected files across
assets/source/plugins/binaries/build caches/robot handoffs/benchmark directories
checked against pre-audit sizes/mtimes: none missing or changed. All FPS/100-agent
references and Jolt migration benchmark material retained. No editor/build/process
restart, user assets, training data/environment or Git history changes. Bin was not
emptied; net saving after keeping the archive is8,953,441,740bytes once emptied.
Manifest/duplicate replacement paths/verified receipt:
`Saved/Diagnostics/StorageCleanup20261026/`. Old diagnostic links may now require
extracting the exact archive member; see [restore notes](Docs/Recovery.md).

**Robotics cleanup October26 — recycled1.94GB of obsolete build patches:**
Audited the robot port, camera checks, transfer fixtures and handoffs. Recent
robot/camera diagnostic folders total about29.4MiB; no multi-GB port dump found.
Moved94 obsolete Live Coding patch files (1,943,291,063bytes) from Binaries/Win64
to Windows Recycle Bin. Each entire patch group predates its normal module build;
current October26 camera patches and normal binaries retained. All94 recycled
payloads verified by SHA256. Weights, assets, source, training/environments,
transfer/100-case/performance evidence and incremental caches untouched. No
editor/build process was running; none started/stopped. Bin was not emptied, so
disk space is reclaimed only when the user empties it. Exact manifest/receipt:
`Saved/Diagnostics/RoboticsCleanup20261026/`. Camera cold-launch build requirement
below still applies. [Cleanup details](Docs/RobotLocomotion.md).

**Throw Lab October27 - approved throw checkpoint and aero investigation:** standalone lab and exact
user-approved scene library saved in `Labs/ThrowLab/approved/2026-10-27/`.
Includes both source FBXs (cache hashes verified), runtime animation/object
caches, Jolt, tools, desktop launcher and complete saved tuning/undo history.
Checkpoint `a0ce0db2` plus exact-byte recovery fix `6c5f94dd` on
`codex/standalone-sim`;9004 recovery files/1,083,829,824bytes verified, no LFS
pointers. All three approved files match their manifest hashes in Git.
Current big throw uses Imperial Spear with Throw F34. Whole-frame rotation
editing, quaternion interpolation, Ctrl precision, inline axis readout, fixed
world target, free/orbit camera and1x playback cap included. Source and focused
mouse/physics checks pass. Snapshot inventory verifies the selected commit.
User subsequently authorized velocity-to-spear snap and aerodynamics: now
implemented locally, not pushed. Button below Launch velocity aligns direction
to the held spear at exact Throw frame; amplitude/twist/keys/camera/playhead
preserved, one undo step, repeated aligned click is a no-op. Air enabled by
default for spear/sword, with per-throw On/strength/pressure-position/damping
controls below Launch velocity. Applies dissipative relative-airflow forces
and torque through Jolt120Hz, preserving roll/gyro/contacts; none while held,
for Bomb, asleep or during cached replay. Off restores exact prior flight.
Implicit force response bounds high-speed/small-inertia impulses. Reused WASM
vectors, no new worker/loop/hull cooking.16 snap/81 force cases, both-throw
physics/replay/extreme-control contacts, grip/scale/floor/target suite, actual
browser controls/undo/Refresh pass. Model remains uncalibrated; user Refresh
loads it. Approved checkpoint/profile and live state file untouched.
Follow-up: user reported spear still flat. Reproduced actual saved F54 scene:
air active for40 substeps, but only0.74degrees nose-down. Replaced transverse-
speed-squared normal drag with full-airflow-speed times transverse velocity;
effective normal coefficient-area increased0.04 to0.24m2 for visible short-flight
response. First correction gave10.80degrees nose-down at F54. User still found
the later saved throw weak: normal response now increased another4x to0.96m2.
Latest F62 error improves11.54 to4.73degrees, pitch-14.29degrees, with saved
settings untouched. Original F54 fixture now has4.59degrees error. This is game
tuning, not measured realism. Launch spin now has its own sidebar section;
signed Twist velocity updates on input and switches to manual immediately,
zero stops spin, negative reverses it, blank input is ignored. Existing auto
mode/rates preserved; grouped undo and ten signed/zero Jolt launch cases pass.
Actual-scene numeric
and isolated browser/Refresh regression, passivity/extreme controls and scaled
contact tests pass. No saved settings/launch edits or desktop takeover.
Study assumptions/sources and implementation details are in the lab README;
evidence under Saved/ThrowLab/, including the separate AerodynamicsStudy/.
See [lab handoff and restore steps](Labs/ThrowLab/README.md).

**Throw Lab October27 - rotation readout moved into label:** removed native
rotation-axis title tooltips and the pointer-following value box. Hand/forearm
offset now appends to the existing right-side WORLD/LOCAL label, axis-colored,
while hovering/dragging. No new overlay over the joint. Existing offset math,
precision controls and state unchanged. Isolated mouse checks verify label
placement, live values and absent native titles; screenshot at
`Saved/ThrowLab/rotation-label-readout.png`. Press Refresh.

**Throw Lab October27 - precision rotation:** holding physical Left Ctrl scales
rotation-ring mouse deltas to30% for hand, forearm, weapon and velocity. Can
press/release mid-drag without jumping; Right Ctrl, translation and scale retain
normal behavior. Modifier tracking precedes the active-drag shortcut guard and
clears on blur/hide. Focused four-tool/transition/tangent checks pass; no state
writes or desktop control. Press Refresh.
Extended to camera rotation in both orbit and free modes using the same physical
Left Ctrl tracker and incremental30% deltas. Mid-drag changes remain continuous;
pan/zoom unchanged. Lightweight pointer-handler checks pass for both modes,
modifier transitions and normal Right Ctrl behavior. User Refresh loads it.

**Throw Lab October27 - room brightness:** slider at the top of the left sidebar
adjusts background/fog, floor and ambient lighting immediately. Range0-100%,
default40%;0% matches the old dark room. Saved per scene, undoable in one drag,
retained through copy/Refresh. Isolated WebGL pixels/uniforms, undo/redo and
Refresh verified; launch/camera preserved. No live state writes or desktop
takeover. Local source only; user Refresh loads it.

**Throw Lab October27 - playback speed cap:** slider and input handler now stop
at1x; saved settings, scenes and undo/redo normalize higher speeds to1x.
Slow motion0.1-1x retained. Focused boundary checks pass; user Refresh loads it.

**Throw Lab October27 - whole-frame rotation correction (supersedes subframe
authoring below):** diagnosed saved forearm motion:25 keys across14 frames,
including four subframe targets within F26; playback detoured through those
and default integer poses. Hand/forearm edits now snap BEFORE capturing the
drag axis/base. One key per whole60fps frame; nearest-frame migration prefers
the closest sample, preserving existing integer poses on collisions. Applied
on scene/settings loads and undo/redo, so old histories cannot restore subframe
targets. Adjacent frame offsets use shortest-arc quaternion interpolation,
avoiding Euler-wrap spins. Unedited integer frames still use original animation.
Armed, key fields, scrub and A/D now use whole frames. Throw alone retains
fractional authoring and exact release-pose/velocity sampling. Whole-timeline
Reset scope retained. Original saved state backed up in
`Saved/ThrowLab/BeforeWholeFrameRotations-20261027-150239/`; live file unchanged.
Refresh normalizes the latest saved edits; weapon transforms, camera and throw
timing preserved. Numeric regression fixture/1500+ samples/Jolt release, isolated
actual mouse snapping/axis/Refresh/undo checks and updated main browser suite
pass. No desktop takeover or Unreal work. [Current details](Labs/ThrowLab/README.md).

**Throw Lab October27 - S toggles gizmos:** plain S hides/shows all gizmo
overlays, their readout and contextual Reset, retaining the selected tool.
Selecting a gizmo explicitly unhides it. Per-scene flag survives Refresh and
uses normal undo. Typing/modifiers/repeat/active drags are protected. Free-camera
backward movement is now Shift+S; plain S has priority. Focused shortcut and
save-roundtrip checks pass. No live state edits; user Refresh loads the change.

**Throw Lab October27 - downward camera range:** orbit tilt now reaches nearly
straight down/up (89.94 degrees) instead of stopping around42 degrees downward.
Vertical orbit preserves viewing distance; tiny pole margin avoids inversion.
Saved poses remain compatible; steep-angle zoom remains usable. Focused camera
math/restore/zoom/free-transition checks pass. Background-only change, no live
state writes or desktop control. User Refresh loads it.

**Throw Lab October27 - rotation axis readout:** hand/forearm rings now show
a signed degree offset from the authored default beside the pointer on hover
and during dragging. Uses the displayed axis, including hand world/local and
forearm local, rather than stored Euler channels; hand excludes upstream forearm
edits. Hidden off-ring/for other tools, no layout or saved-state changes. Numeric
quaternion and isolated mouse hover/drag checks pass; screenshot at
`Saved/ThrowLab/rotation-axis-readout.png`. Press Refresh; live app untouched.

**Throw Lab October27 - Reset scope corrected to whole timeline:** hand and
forearm Reset now remove all keys for the selected joint across the selected
throw, even when invoked from an unedited frame. Editing itself remains per
frame. Other joint keys, weapon transforms/scale, other throws and tuning stay
intact. Button stays enabled, with scope in its tooltip; one Ctrl+Z restores all
removed keys. Isolated whole-timeline/scope/undo/Refresh checks pass. No live
reset was performed; press Refresh to load the button behavior.

**Throw Lab October27 - Reset availability:** greyed Reset meant the selected
rotation was already at default, not an Armed-frame lock. Reset now stays enabled
for an active rotation gizmo; default clicks are harmless no-ops with no undo
entry. Armed remains a marker only. Isolated mouse checks verify hand/forearm
rotation and reset at F0, before/at Armed and after Throw in the animation.
No live state writes or desktop takeover. Press Refresh.

**Throw Lab October27 - whole-frame navigation:** added **Whole frame** directly
beside the footer frame counter. Pauses and rounds the playhead to the nearest
integer60fps frame; .5 rounds up. One-shot navigation, no key/settings mutation
or undo entry; fractional authoring and normal Refresh persistence retained.
Press Refresh to load. No live state or user desktop changes.

**Throw Lab October27 - hand/forearm edits are frame-local:** removed sparse-key
carry-over and the last-key hold. Every unedited60fps integer frame uses its
original authored rotation; fractional samples interpolate only within their
neighboring integer frames (and any explicit fractional keys). Hand and forearm
share this behavior. Explicit saved edits retained; weapon grip/scale stay
constant. Contextual hand/forearm Reset clears that joint across the selected timeline
(as clarified in the latest Reset-scope correction). Numeric checks cover unedited neighbors/gaps/tails,
fractional interpolation and release continuity. Isolated browser mouse/key/
reset/undo/Refresh checks pass; a forearm edit no longer alters a later unedited
release frame. No live state overwrite, Unreal or desktop takeover. Press Refresh.

**Throw Lab October27 - contextual rotation reset:** one compact viewport
button appears for the active hand/forearm/weapon/velocity gizmo, with a matching
label and scope tooltip. Hidden for scale/all-off; enabled at default (a no-op). Hand and
forearm reset the whole selected timeline (latest scope correction above). Weapon resets rotation
only, keeping position/scale; velocity restores direction while retaining
amplitude/twist. Other tuning/throws/weapons and camera/playhead stay unchanged.
Reset pauses, is one Ctrl+Z step, and saves through Refresh. Checkbox layout
remains fixed. Isolated mouse/scope/undo/redo/Refresh checks pass; screenshot
`Saved/ThrowLab/contextual-rotation-reset.png`. No live state edits or app takeover.
Press Refresh. [Lab handoff](Labs/ThrowLab/README.md).

**Throw Lab October27 - left forearm gizmo and hand-key reset:** user clarified
"calf" means left forearm. Follow-up correction: Show forearm gizmo at the elbow
now uses the forearm's OWN current local XYZ axes, following its edited rotation.
All three mouse axes verified against current forearm orientation; elbow/upper
arm stay fixed. Existing keys/interpolation and weapon edits are preserved by
retaining parent-space key storage and converting local gizmo deltas into it.
Per-frame fractional keys per throw; then hand keys. Only forearm
subtree moves. Weapon local grip/scale retained; release velocity follows edits.
Mutually exclusive with other gizmos, one drag per undo step, scene/Refresh saved.
Removed the user's two saved big-throw hand keys at F26/F27; no small-throw keys
existed. All other settings, camera/playhead and weapon transforms compared and
preserved. Undoable reset with exact-list guarded one-time stale-window repair.
Backup/receipt: `Saved/ThrowLab/HandReset-1793092569480/`.
Both-clip numerical checks, all three mouse axes, subtree isolation, fixed elbow,
weapon preservation, launch updates, undo and Refresh pass. Screenshot:
`Saved/ThrowLab/forearm-gizmo.png`. No Unreal or user desktop interaction.
Press Refresh. [Lab handoff](Labs/ThrowLab/README.md).

**Throw Lab October27 - local XYZ weapon scale editor (corrected):**
Gizmo selection follow-up: hand/velocity/grip/scale checkboxes are mutually
exclusive; selecting one unchecks the rest, and the active one can be turned off.
One undo step restores the previous tool. Saved multi-tool states normalize to
one. Removed scale percentage inputs entirely: local-axis gizmo editing only,
with stable checkbox positions. Browser selection/layout/undo/Refresh checks pass.
Refresh layout follow-up: green Refresh is centered below New/Copy/Rename/
Snapshot in the header, with space above the camera buttons. Same save/reload
handler; isolated1280px/1000px layout checks pass. Press Refresh to load.
Viewport order follow-up: **Imperial Spear** is now the far-left checkbox,
before Two-tone. HTML order verified; Refresh loads it.
**Edit scale** now shows three colored local-axis handles with square tips and
gizmo-only independent X/Y/Z editing. Replaces the uniform handle/slider. Handles
follow the rotated weapon basis; each changes only its own axis about the grip,
with10-200% bounds. Prior scalar sizes migrate to equal XYZ values. Scale remains
constant per throw/weapon, saved in scenes/Refresh and covered by grouped undo.
Grip pose, hand keys and camera remain unchanged; L only affects hand rotation.
Render positions/normals and Jolt shape/COM/inertia use the same local XYZ scale;
configured mass unchanged. Isolated mouse/local-axis/mesh/undo/Refresh checks and
Node/WASM unequal-scale release/replay/floor checks pass. No user desktop/state
writes, Unreal or resident process. Press Refresh. Screenshot/receipts under
`Saved/ThrowLab/`; [lab handoff](Labs/ThrowLab/README.md).

**Throw Lab October27 - Imperial Spear and constant local grip editor:**
Added bottom-viewport Vanilla checkboxes **Imperial Spear** (replaces the sword)
and **Edit weapon grip** (local movement arrows plus rotation rings). Separate
position/rotation offsets for each throw AND weapon; constant while held,
independent of hand animation keys. Gizmos use an orthonormal weapon basis and
pivot at the grip; sword default geometry is preserved within8.16e-9m after
reframing its old hand-space cache. L still affects only the hand gizmo.
One drag is one undo step; both toggles and offsets survive scenes/Refresh.
Imported the specified `Exports/ImperialSpear/SM_ImperialSpear.fbx` directly with
FBX SDK: full21,112-triangle/2.2m render mesh, grip pivot, nine authored UCX hulls
in one Jolt compound body. Cosmetic tassel excluded from collision. Atlas colors
sampled per triangle for the existing lightweight lab renderer (not full PBR).
Grip-aware COM velocity/release continuity, shaft twist, all local mouse axes,
per-throw/per-weapon independence, undo/redo and Refresh verified. Compound
spear target/floor tests pass; tested final hull penetration up to5.21mm.
Receipts/screenshots in `Saved/ThrowLab/`, notably `grip-verification.json` and
`imperial-spear-grip.png`. No user state overwrite, desktop takeover, Unreal,
server restart or new resident process. Press Refresh. [Lab handoff](Labs/ThrowLab/README.md).

**Throw Lab October27 — Vanilla throws authoring ready:** new tab selects big/small
throw. A/D now step backward/forward one60fps frame using typed letters (AZERTY
compatible), retaining fractional offsets. Both pause playback; typing/modifiers
and gizmo drags are protected. Plain D takes priority over free-camera movement;
Shift+D retains camera-right. Frame navigation creates no undo entries. Browser
shortcut/fractional/free-camera checks pass. Press Refresh.
The tab selects either
throw. Latest correction: Ctrl+Z/Shift+Z now use typed Z, fixing the physical-KeyZ
binding on AZERTY. Local hand gizmo now uses current hand orthonormal axes and
quaternion rotation about the picked normal; world mode retained. Closest-ring
geometry picking replaces SVG paint-order picking at overlaps, with hover feedback.
Browser checks cover all local/world axis deltas, overlap selection, QWERTY/AZERTY
undo/redo, Refresh and preserved camera/playhead. Undid the user's next two hand
edits from the real saved history; both are retained in redo. Exact-settings
guarded repair also handles stale-window Refresh. Backup/receipt:
`Saved/ThrowLab/UndoAxesRecovery20261027-1793082518162/`. Press Refresh.
The tab selects either
throw. Ctrl+Z undo / Ctrl+Shift+Z redo now cover tuning edits, key changes, gizmo
drags, resets, selectors, target/trim/view settings. One drag or focused numeric
edit per step; scene-local history survives Refresh (100-step/1MiB bounds).
Undo pauses and retains camera/playhead; navigation does not fill history.
Restored user's sole big-throw F33 hand offset [0,0,31.113577207342754] to authored
pose by removing that key. Backup/receipt in
`Saved/ThrowLab/UndoRecovery20261027-1793081807665306700/`; unrelated live state
verified unchanged. Exact-match, one-time local repair guards against an older
window saving that key again on Refresh. Undo/redo browser checks and history/
repair unit checks pass; no desktop takeover or server restart. Press Refresh.
The tab selects either
throw with independent tuning. Fractional armed/throw frames; armed means ready-pose
marker only (user clarified), with exact seek/capture buttons. Key local left-hand
XYZ rotation on any animation frame; interpolate degree offsets, retain other joints.
Root-relative launch direction offsets and amplitude default to animation-derived
COM velocity. Angular launch is now twist-only about the hull's long principal
axis; animation projection by default, editable signed degrees/frame or zero.
Jolt gyroscopic motion/collisions stay free after launch. Keys, fractional timings
and tuning persist through Refresh/scenes; prior stored timing retained.
Follow-up: separate Show hand gizmo / Show
velocity gizmo checkboxes (off initially, scene-persistent), now on the bottom
viewport row after Two-tone/Bones/Free camera, visible only for Vanilla throws.
L now toggles hand rings between absolute world XYZ (default) and current local hand
axes. Label/tooltips show mode; scene/Refresh retains it. Switching preserves poses;
typing/modifiers/repeats/active drags do not toggle. Both mode drags and keyboard
guards/Refresh pass. World edits convert back to existing local offset keys; prior
keys/numeric controls preserved. All three mouse axes and rotation conversion
across full turns/Euler singularities pass. RGB rings key
the current fractional hand frame or rotate launch direction; velocity arrow/rings
anchor at release COM. Drag pauses playback and preserves camera, frame, amplitude
and twist. Both widgets can coexist; no extra render loop or hidden projection.
All hand axes/velocity drag, hiding and Refresh persistence pass in the isolated
browser. Script-load bursts reproduced ERR_CONNECTION_REFUSED; sequential boot
loads fix the tested Refresh workflow without a server restart. One cached preview
plus existing small world; no workers/watchers/Unreal/UI takeover or live-state
write. Four clip/object numerical cases and source poses passed; browser checks
cover editing, Refresh and clip independence. Press Refresh.
[Current controls and validation](Labs/ThrowLab/README.md).

**Throw Lab October26 — hand release and object physics ready:** desktop **Throw Lab**
launches `Labs/ThrowLab` on8893 with its own settings/browser profile. Authored
`recoveries/big throw.fbx` (66 frames) and new `small throw.fbx` (35 frames), both30Hz.
User deleted/replaced the mistaken nine-frame big throw2; importer/reference and
picker updated, retired saved selections migrate. Left-hand selector now offers
the existing sword as spear placeholder and original CC0 bomb. Right-side More
options sets per-clip release frame/At playhead; inherited COM/angular velocity
then single-body Jolt gravity and floor/fixed-target collision.180-frame
flight tail; authored agent holds last pose. All timing UI now uses zero-based
60fps frames (release, scrubber, trim markers and clip ranges); saved timing
preserved. Frame conversion/scrubbing/Refresh checks pass in the isolated browser.
No aiming, explosion or agent collider.
Sword-impact follow-up: Jolt gyroscopic force was disabled by default; all axes
were already free. Reproduced user's release F33 / target hit F41. Identical
prefix through impact, then enabling gyroscopic motion changes the rotation-axis
direction by about100 degrees from F42 to F54 versus effectively zero before.
Enabled for released objects; mass/geometry/release velocities retained. Both
clips/objects and the added F33 sword hit/landing/replay checks pass in background
Node/WASM. No user UI or saved settings changed; press Refresh to load.
World target was already fixed, but root-follow camera/grid made it look moving;
both are now world-anchored. Bodyflip-style controls/Refresh/settings retained.
All101 source poses match; four clip/object physics cases and browser workflow
checks pass, including reverse replay, release timing, gravity/contact/sleep and
fixed target/camera. No user desktop takeover, Unreal, other-lab edits or inference.
Small below-normal loopback server; workerless cached browser physics only;
owned test browser closed. Desktop/taskbar follow-up: distinct teal target/orange
spear icon; launcher uses `/throw-lab.html` for a separate Chromium URL-app
identity (port alone does not distinguish root URLs). Reopen existing Throw Lab
from its updated shortcut. Shortcut/favicon and headless smoke verified; no
taskbar UI takeover or other-app restart. [Workflow and source details](Labs/ThrowLab/README.md).

**Player robot camera October26 — loaded without restart, verified:**
NN↔robot camera switches now have separate Blend In0.4 / Blend Out1 controls
through Set Locomotion Camera Blend (Agent defaults Self). Robot target is actual
15-body mass-weighted COM X/Y on floor Z0; spring height/settings and independent
BP offsets retained. Uses existing player camera follower, new sidecar storage,
60-tick authored timing; no retained layout changes or NPC COM sampling. Successful
switches activate it automatically; Get Up↔Clanker keeps the same follow. Repeated
settings do not restart blends. Four camera/real-rig handoff tests pass. Minimal
Live Coding16 affected units882.69s, then1-unit safeguard145.19s; final reload
13:45:04UTC. Saved dirty PoseAgent before reflection, prior bytes backed up.
Full BP graph and saved BP/TestNN hashes preserved; LiveAgentTypes status3/native0/
pins0. New node defaults Self,0.4,1.0 verified. Editor27348 remains TestNN/outside
Play; no user session or scene tuning changed. **Normal DLLs predate this camera
addition: minimal normal build before any cold launch.**
[Implementation and current checks](Docs/RobotLocomotion.md).

**Robot locomotion October26 — contact correction installed and verified:** both
Get Up and Clanker now opt out of speculative response per contact point, using
the shared spherical32 rig and unchanged weights. Also fixed missing callback
installation for robot-only worlds and its bypass in the scoped-protection
listener. Robot admission installs the callback; removal retires it unless
another feature needs it. Ordinary contacts retain the native default.
Actual production UE rig + NNE check now passes100/100 saved Get Ups and16/16
five-second walks, including all15 native MuJoCo walking successes. AgentSwitch,
ordinary contact settings, scoped defense and sword-reaction checks pass:6/6.
The intermediate99/100 Get Up,10/15 walking transfer failure remains recorded;
it exposed the missing listener ownership, not a reason to weaken assertions.
Native Development dependency and minimal normal UE builds passed. Saved dirty
PoseAgent BP and TestNN before closing PID22068; preserved hashes still match.
Interactive TestNN PID27348 is open and verified: five nodes/three enum values,
LiveAgentTypes status3/native0/pins0/wiring preserved. Owned12-frame Play smoke
initialized all three user BP agents and ended cleanly; editor remains outside
Play. Loaded native DLL matches the build manifest. No assets saved by checks.
No Blueprint wiring, tuning, weights or PHAT assets changed. Exact spherical
limits remain in one packaged rig because stock PHAT cannot represent them.
Run and long fixed Get Up holds remain unvalidated; native MuJoCo also fails the
old run controls. Do not generalize the passing walk/Get Up suite to those cases.
[Current integration and evidence](Docs/RobotLocomotion.md).

**Bodyflip October27 - whole-leg inertia experiment stays in the viewer:**
Left hip-to-foot direction stopped sharply around frames51-52 at Slash L/100%.
Peak acceleration275.45rad/s^2 barely changed without yaw correction (271.83):
reference hip/knee motion was still imposed directly. New viewer-leg-response.js
tracks root-relative thigh/foot orientations and hinge knee bends with continuous
angular position/velocity (legs24rad/s, pelvis32). Upper orientations and rigid
sockets retained; no knee-position IK. Left peak vector acceleration falls75%,
retaining92% of swing; right falls62%, retaining84%. Focused0/50/100%, hinge,
socket, reverse-seek, analytic-rate and bounded-cache checks pass. This is an
angular posture response, NOT exact physical momentum conservation. Existing
viewer compares prior yaw-only response with whole-leg response. Refreshed tab4,
inspected52/58, restored paused25/100% and camera. No lab motion/default/state,
Unreal, NN or server changes. [Details and receipt](Labs/BodyflipLab/README.md).

**Bodyflip October27 - compensation editable in the existing comparison:**
User wants to work on this motion in the viewer before returning to the lab.
Added0-100% Compensation slider/number at header right; live updates preserve
frame/camera/play state. One plan shared by both canvases. Preview motion/event,
amount, time, camera and play state persist per tab across refresh, independently
of lab saves. Existing IAB tab4 refreshed in place; no duplicate opened. Verified
0/100, blur commit and refresh/frame retention; restored80 and resumed playback.
No lab motion/default/state, Unreal, NN or server changes. Future experiments
stay in the viewer until user asks to carry them back. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October27 - inertial yaw response fixes lower-body jitter:**
User accepted reference poses but rejected jitter. Measured tickwise pelvis-rate
reversals from exact momentum matching plus hard hip-lag projection. Planner now
drives a critically damped angular response (32rad/s); yaw position/velocity carry
between ticks, analytic sampling keeps acceleration continuous, no displayed
hard clamp. Reference hip/knee poses and upper motion retained. About63ms yaw lag;
instantaneous old momentum budget is intentionally relaxed, NOT exact conservation.
After cache end, analytic settling preserves final turn without snapping velocity.
At80%, peak pelvis acceleration falls94% Slash L/80% Slash RU; peak turn retained
85%/82%.6424 pose checks, focused rate/acceleration/tail/reverse/cache checks,
94 sequence regressions and owned UI/manual checks pass. Comparison now shows
previous immediate vs new inertial yaw on the same reference poses; fractional
playback clock removes rounding steps, still30Hz render cap/hidden pause.
Saved/BodyflipLab/soft-legs-inertial.gif. No live state, Unreal, server, training
or push changes. Refresh. [Details and momentum limits](Labs/BodyflipLab/README.md).

**Bodyflip October27 - human-reference leg motion replaces speed-driven knees:**
User rejected the shared turn-speed bend as arbitrary/uncanny. Soft legs now
adapts rounded Wagner2011 jump-throw hip/knee curves: different leg roles,
Armed/Hit timing, continuous phase clock, smooth entry/return, shorter gestures
for shorter strikes. Hip flexion follows pelvis forward; canonical hinge permits
knee extension as well as flexion. Real phase metadata used for scheduled/manual
attacks. Existing Amount and Soft legs controls retained. Hip yaw lag18 degrees.
Upper world orientations/sockets preserved; yaw solver still matches the old
rigid correction's momentum budget, NOT full3D conservation. This is reference
adaptation, not sword mocap.6424 pose/hinge/tilt/reverse checks,94 sequence checks,
rigid comparison and owned UI/refresh/manual checks pass; reviewed Slash L/RU
frames. Very fast source clips can still require rapid hip yaw at100%.
Current comparison: soft-legs-preview.html; half-speed recording:
Saved/BodyflipLab/soft-legs-reference.gif. Earlier Soft legs versions/recordings
are superseded. No live-state write, Unreal/server restart, training or push.
Refresh lab/comparison. [Behavior, source and limits](Labs/BodyflipLab/README.md).

**Bodyflip October26 - pelvis attack compensation:** appended0-100% at the
bottom of More options, default50%. Opposes attack-added spine_01 yaw on the
pelvis, then corrects spine_01 to keep upper-body world orientations unchanged.
Pelvis position/socket geometry retained; legs follow the counter-turn. Applies
after attack blending (scheduled/manual), excluding whole-body flip yaw.1676
compensation samples,580 transfer samples,94 sequence/30 Jolt checks and owned
browser option/frame/refresh/manual tests pass. No live-state overwrite, push,
Unreal/server restart. Refresh. [Behavior](Labs/BodyflipLab/README.md).

**Bodyflip October26 - attack pelvis rotation transferred to spine_01:**
Upper-only attacks now carry the source pelvis rotation relative to clip start
into the first spine, including twist and lean. Actual pelvis/root/legs stay
with underlying motion. Corrected pose drives matching, entry, native playback
and return; manual Strike uses the same transfer.580 source-pose comparisons,
94 sequence checks,30 actual Jolt checks and owned browser scheduled/manual
checks pass. No UI changes, live-state overwrite, Unreal/server restart or push.
Refresh existing window. [Transfer details](Labs/BodyflipLab/README.md).

**Bodyflip October26 - five spine boxes matched to Jolt:** user chose retained
box appearance with matching physical shapes. Replaced three grouped torso
proxies with one bone-local box per spine_01..05, using shared dimensions/offset/
rotation for rendering and Jolt. Scheduled attacks already start at spine_01;
manual Strike/aim now uses that same upper-only mask. Pelvis stays excluded.
Five spine constraints/masses/COM offsets retained; torso geometry/inertia now
matches display.30 focused actual-Jolt checks,94 motion regressions and owned
browser frame/manual-attack checks pass. No UI rearrangement, Unreal/server
restart, live-state overwrite or push. Refresh existing window.
[Details and remaining display scope](Labs/BodyflipLab/README.md).

**Bodyflip October26 - Space gym and scheduled vanilla attacks ready:**
Sequence appends zero-gravity Space gym using existing markers. Jump % defaults100;
0 gives no push, higher values increase jump energy. Popup appends Jump %, Attack
(None +16 vanilla melee/sword clips) and delay; Attack In/Out append at bottom of
More options. Closest pre-Armed upper-pose match, adapted Final Harness entry,
then native Armed->End playback; root/pelvis/legs preserved. Actual attacked pose
feeds NN landing. Space has no contact/NN requirement, constant impulse drift,
and retains ground scene platforms for mode switching.97 focused checks,52 editor,
84 motion and38 blend checks pass. Isolated browser verified two layouts, editing,
playback, refresh and ground restoration; writes intercepted/browser closed.
No Unreal/server restart, live-state overwrite or push. Refresh existing window.
[Behavior and source provenance](Labs/BodyflipLab/README.md).

**Bodyflip October26 - shared Foot IK integration, desktop restart pending:**
FootIKLab `surface.js:createFeet()` is the canonical contact solver used by both
labs. Bodyflip API6 serves current source modules on Refresh with isolated
globals; no copying, watcher or shared UI/state. Grounded incline locomotion uses
Foot IK contact/roll/reach/knee rules plus capsule-to-mesh pelvis compensation.
Jump support/push/flight retain their authored control. Corrected pose history
feeds falls/NN landings; crest transitions do not double-apply old tilt. Foot IK
checkbox appended at bottom of More options.1529 integration checks +84 motion,
78 knee and24 capsule checks pass. Six full Foot IK clips remain byte-identical
through API extraction. Browser verified live-source loading, six frames,
comparison/playhead and graceful old-server fallback; saves intercepted.
**Main8876/PID27312 remains API5**: automatic approval rejected the verified
Bodyflip-only restart ("blocked by policy"). No alternate restart attempted.
Foot IK stays disabled with a restart-needed label there. Isolated API6 preview
8891/PID12412 and owned browser closed. No Unreal/FootIK server changes or push.
[Shared contract](Labs/FootIKLab/SHARED_API.md), [Bodyflip details](Labs/BodyflipLab/README.md).

**Recovery October26 â€” accepted checkpoint handoff exported:** latest accepted
13-11-28 pelvismax final161960, 3.669B samples, packaged in
`Exports/MimicKitEquipment/Recovery_Pelvismax161960_Unreal_20261026/` with
`HANDOFF.md`, original verified checkpoint, ONNX actor, frozen rig/Jolt32Hz
references and SHA256 manifest. CPU inference parity verified on516 recorded
observations; ONNX Unreal integration remains to be checked. Previous100/100
actual Unreal/Jolt test used Python inference. No training or gameplay changes.
[Details](Docs/MimicKitTransfer.md).

**Foot IK October27 - wall gait frame and anatomical knees corrected:**
Prior "wall leg folding corrected" receipt failed visual acceptance. Its
nearest-feasible-knee rule could reverse the NN hinge; mismatched surface
travel and torso-relative pelvis height produced the seated/crab posture.
Mesh origin now follows the capsule ground reference along the surface normal.
NN pelvis translation/lower chains share the ground frame; Upright changes
posture about the pelvis, not standing height. Source-stabilized signed knee
hinges follow their thighs, including straight-leg samples. Removed arbitrary
world-up wall lift and opposite-side obstacle-clearing knee selection. Departure
keeps one position filter without collision momentum. Material heel/toe/yaw
pins, relative ankle limits and actual recurrent root windows remain.
15 frame/hinge +17 coupling +697 directional surface +101 Upright-endpoint
checks pass.1368 shared Bodyflip adapter checks pass; its host is untouched.
Saved Run143 pelvis height87cm in ground frame; minimum knee-hinge dot0.984
across both601-tick live Run/Walk clips. Native parity3.61e-6, features2.39e-7,
root replay error0. Visual review includes wall and wall-as-floor sequences20–300.
Late unbounded-speed descent can exceed the NN's useful gait range (Walk cadence
fades); no universal motion-quality claim or speed/input cap. Final actual app
load error-free, actual-root coupling; cold surface request19.1s, not instant.
Older wall-contact fixtures/receipts are rejected-history evidence. Current:
verify-wall-frame.cjs and wall-frame-{run,walk} fixtures. No UI/state write,
Unreal/server restart or push. User Refresh. [Details](Labs/FootIKLab/README.md).

**Foot IK October27 - simulated root now drives the actual NN (initial receipt):**
Inclines/edited surfaces now couple120Hz root/feet to a retained30Hz lower/upper
NN stream. Actual root history and8 fresh physics-predicted future positions/yaws
replace the old constant-speed gait command. Surface frame transports velocity;
Upright is posture only. Phase, native pins, Walk-at-Run-policy speeds and yaw
schedule retained. Shared createFeet/API1 unchanged;41 legacy tests still pass.
One bounded CPU request uses a short-lived shared-JS physics peer and validated
cached NN decoder; playback does no inference. Actual physical speed uncapped.
First-next-root decoding now matches native encoded-window bounds, preventing
the prior fast-fall rebase mismatch.17 coupling checks pass; all149 measured
history deltas and replay roots match. Native Run/Walk parity<6.5e-6; original
root-window features<2.4e-7. At143 root falls7.234m/s and NN sees the same reversed
travel, now forward relative to facing.7 protected headless app checks and six
collider frames reviewed; current production request cached, saved state intact.
The subsequent wall correction above supersedes this receipt's IK metrics and
fixes the prolonged Walk reach/collision failure. Late high-speed NN motion
remains sharp; current raw/corrected measurements are in the newer entry.
Loaded preparation measured3–7s; cold production request15.9s. No universal
instant-load claim. No user-tab control, server restart, Unreal/Bodyflip edit or
push. Refresh. [Architecture, exact limits and receipts](Labs/FootIKLab/README.md).

**Foot IK October27 - ghost investigated; root heading arrow:**
Current Run36/Left/wall90/yaw200 over1.2–6m/gravity70/unpin1 at143: ghost exactly
matches the rigidly placed source NN at all601 samples; pelvis/upper coincide
with main body. Both tilt39.289°. Actual root falls8.141m/s while the precomputed
NN still follows its forward course with184.286° final facing. Surface gravity
is not fed back into the NN root window; this is an existing host/input mismatch,
not a reversed ghost renderer. No motion fix or recoupling claimed here.
Root checkbox now also draws a yellow facing arrow from actual root position,
using generated root yaw/initial heading plus surface alignment, not pelvis or
velocity.16 focused and41 surface checks pass;8 owned-headless checks and five
frames reviewed. Current full motion byte-identical; saved state unchanged.
No inference, user-tab control, restart, Unreal/Bodyflip edits or push. Refresh.
[Finding, remaining limitation and evidence](Labs/FootIKLab/README.md).

**Foot IK October27 - root-speed pin release and editable platforms:**
More options appends Unpin below m/s (0.2 default;0 off). On actual surfaces
steeper than Minimum gravity incline, total root speed below the threshold
cancels both pins and prevents acquisition; geometric contact/gravity continue.
Root v is below viewport status; + Platform below it. Bodyflip-style W/E/R,
local scale, centre pivot, Delete/Backspace, transform Ctrl+Z and orbit-safe
selection work in Foot IK's own adapter. Layouts persist per terrain; previews
do not replan or infer until release, and retain frame. Edited scenes use surface
root simulation; untouched stairs retain root ramps/foot treads. Reverting all
edits restores the original preset solver. Added platforms catch the root and
receive pins; a far platform leaves the existing wall motion within2e-14m.
Current wall clip minimum speed0.2703m/s, so0.2 does not trigger;0.5 releases the
right pin at46.41 simulation +18 protected headless UI checks pass, including
six unchanged default surface clips, persistence and camera/key interactions.
Shared API1 adds optional allowPins=true; Bodyflip's pin policy is unaffected.
No user-state/tab operation, server restart, Unreal/Bodyflip/NN edits or push.
User Refresh loads changes. [Details and evidence](Labs/FootIKLab/README.md).

**Foot IK October27 - turning upper NN frame corrected:**
Run36/Left3.5m/s/down/yaw200 after stairs exposed a lab conversion bug: the
root-window inverse heading was reused in upper pose codecs that transpose it,
so world yaw was applied twice to upper pelvis/feet/hands. Upper pose frames now
rotate with the root, matching the game's constant lower-to-upper bridge in
LowerTransformToHeading/BuildUpperBaseFromLower. Both history seeds, inference
and decoding use it; root-window features/upcoming turns remain unchanged.
434 steps match independent game equations (upper error1.08e-6); original lower
inference error0. World-rotation equivariance and byte-identical nonturning pose
verified. Current scene's displayed lower joints are unchanged across601 samples,
including real NN handoff103. Resumed shoe penetration remains6.063mm. At212
elbows now92/125deg versus158/162deg.18 collider frames reviewed, no browser errors.
Live8890 returns verified fixed output; user Refresh activates it with state kept.
No restart, user-tab/state operation, Unreal/Bodyflip/terrain/weights/UI edit or
push. [Cause and regression evidence](Labs/FootIKLab/README.md).

**Foot IK October27 - descending released feet no longer trail the old tread:**
Run61/down/yaw200/accent400 at51 exposed a separate support/recovery defect that
the prior straight-descent check missed. Upper-tread pin remained until the leg
was almost horizontal; recovery only accepted rising endpoints and clearance
ran before forward recovery. Descent support now reserves the NN downward leg
posture within reach, then recovers over falling endpoints with incoming velocity
and no later artificial wait. Height fitting sees the recovered path. Current51
foot moves32.10cm forward/16.08cm lower, now22.45cm below its hip; retained material
pins stay exact. Peak pelvis correction18.41→12.42cm. Both current Run and real
Run-policy Walk2m/s tested, plus previous straight/turning descent regressions.
26+28+21 checks pass; six ascent/flat/uneven bank clips byte-identical.28 collider
frames reviewed in owned headless browser, persistence disabled, no browser errors.
Current Run NN handoff73 checked; native post-handoff shoe penetration7.23mm.
Straight Run20 resumed NN has23.60mm penetration; terrain IK is not claimed to
correct resumed raw NN. Walk61 had/has no handoff candidate in5s and retains its
pure-NN flat fade. User scene/camera/playback untouched; user Refresh loads JS.
No restart, Unreal/Bodyflip/NN-weight edits or push. Shared API unchanged.
[Behavior, limits and evidence](Labs/FootIKLab/README.md).

**Foot IK October27 - descending pelvis no longer forces unreachable support:**
Current Run20%, down16/35cm, no yaw, accent400%,42 crouched because an early
lower-tread pin demanded26.87cm body lowering and its recovery envelope retained
the drop. New lower contacts wait for reach with the existing2cm allowance;
supported material pivots stay exact. Descent pelvis curves smooth within reach
bounds, and accent can hold the body above support before lowering, instead of
only adding crouch. Swing reach and toe-off rotation now approach their actual
landing constraints before contact. Run42 correction−23.58→−1.98cm; worst drop
26.87→7.14cm. Actual Run-policy Walk2m/s maximum drop30→11.33cm at400% accent.
28 new checks and21 prior descent checks pass; six ascent/flat/uneven clips remain
byte-identical. Knee steps do not worsen; ankle steps improve for both gaits.
Actual current/history NN handoffs checked; raw post-handoff NN retains small
shoe penetration (17.48mm Run /5.11mm Walk), not claimed corrected by terrain IK.
Prior turning descent remains clear with29.25cm excess foot lift removed.
Owned headless visual checks only; no user-tab control. QA unload accidentally
saved198; original42 restored with a playback-only patch. Settings/camera retained;
test harness now disables persistence itself to prevent further unload writes.
User Refresh loads client JS, no restart needed. No Unreal/Bodyflip/NN weights
changed or push. [Behavior and verification](Labs/FootIKLab/README.md).

**Foot IK October27 - RunB toe-angle comparison:** Saved Run20%, Forward,
downstairs, yaw200 over1.2–6m retains5m/s and finishes192deg; native RunB is3m/s.
Model Viewer launch checkpoint hashes exactly to lab Run weights. Saved frame162
is pure resumed NN after handoff76; displayed/raw foot rotation differs by
<0.000003deg. Same5m/s turn without terrain retains toe-biased gait: minimum
sole tilts17.44/14.47deg versus nativeRunB10.61/8.41 over120–300. No gait/IK,
speed settings or rotations retuned. New Backward reference exposed first-build
JIT issue from prior optimization: trace/freeze now explicitly enables graph
optimization, validates before atomic save and rebuilds invalid disposable
caches. Frozen execution still skips profiling. Fresh/load/corrupt-rebuild
Backward outputs exact, original-controller reference error0. Repaired graph
active; worker source naturally reloads after idle. No restart, user state/app
control, Unreal/model changes or push. [Details](Labs/FootIKLab/README.md).

**Foot IK October27 - descending left-leg height fixed:** Current Run82%, down
16/35cm, yaw200deg/s over1.2–6m, accent400, frame53. Old tread height was carried
from release42 toward next NN plant106 while the ramp root descended, adding
51.75cm to the ankle. Extended existing constrained height fit to descending
carriers, removing surplus toward NN height with full-shoe clearance. No new
settings, side/frame branch, timing or NN change. Ankle29.25cm lower at53; actual
shoe gap43.92→3.47cm. Material pins/rotations/release times retained; peak
pre-handoff ankle step98.39→18.20deg, velocity continuity retained.21 focused
checks pass across full current clip, actual NN handoff73, seek, collision/reach
and bank descents; six ascent/flat/uneven clips byte-identical. NN after handoff
retains~7.22mm existing shoe penetration (7.23mm before). Owned headless views
reviewed with writes blocked; user tabs/state untouched. **User Refresh loads
the fix**. Shared surface API/Bodyflip incline unchanged; no server restart,
Unreal, model/checkpoint changes or push. [Details](Labs/FootIKLab/README.md).

**Foot IK October27 - actual new-phase preparation reduced:** Unchanged Refresh
below did not solve phase edits. Reuse only invariant NN initialization poses,
invalidated by source/weights/geometry/stride/native codecs/Torch; every new
command and terrain handoff still runs the original recurrent NN. Skip redundant
JIT profiling of frozen graphs, retaining eager parity validation. Two full
.20/.31 rollouts preserve every pose, root and pin value exactly. Real app edits
to .47/.73 measured3212/4515ms with both requests newly inferred (no response-cache
hits); frame/renderer retained, writes intercepted. Cold page load still22.24s,
first request17.71s versus1.91s actual inference:30s worker retirement causes
repeated import/model load. Service source now keeps one sleeping worker5min,
then releases it; **lifetime change pending restart** because prior automatic
approval rejected restart as "blocked by policy". No bypass/restart performed.
Worker-side optimizations verified through existing8890 service. No GPU,
background inference, saved-state writes, Unreal/Bodyflip/shared-solver changes
or push. Cache/lifetime tests pass without Torch; ONNX trial rejected for
recurrent motion divergence and removed from active dependencies. See
[current details and timing receipts](Labs/FootIKLab/README.md).

**Foot IK October27 - actual Refresh overhead fixed:** API-only129ms earlier
was not Refresh. Actual IAB full reload5087ms (NN217ms, renderer727ms,
terrain+handoff1983ms). Refresh now checks runtime-file modification dates with
at most4 HEAD requests in flight; unchanged sources retain the ready NN,
terrain frames and WebGL renderer. Adopts other-tab saved edits, re-solves only
motion changes; changed/missing/ambiguous source dates still reload. Server
Date/navigation baseline avoids client clock skew. No polling or solver change.
Activated on8890: unchanged Refresh54.3ms with playback continuing; full script
activation1866ms. Actual app/state/camera/frame/model reuse and code-change
reload verified with intercepted writes in one headless browser; date guards
and9 persistence checks pass. Initial server restart attempt was policy-blocked;
final client-only implementation needs no restart, existing process retained.
No Unreal/Bodyflip, shared API, checkpoint, UI layout or push changes.
[Current details](Labs/FootIKLab/README.md).

**Foot IK October27 - Walk handoff experiment removed; loading audited:** User
rejected the entire arc. Removed extra Walk model, contact-wait detector,
checkpoint swap, lower-inertia exception, checkbox/policy labels and experiment
test; deleted its compiled graph. Archived original checkpoints retained.
Run-only handoff/UI restored exactly to pre-experiment; stale walkHandoff prefs
are discarded. Current initial NN and all continuation poses match the old
Run-only captures exactly. Policy graph cache now hashes graph/native dependencies,
model provenance and Torch version rather than the whole worker, preventing
unnecessary retracing after orchestration edits. Five cache checks pass.
Repeat source+handoff HTTP requests129ms total/no inference; fully uncached pair
including graph compilation13.86s. Current scene results are cached for Refresh.
Single CPU thread/no GPU/30s idle retirement retained. No server restart,
browser control, user-state writes, Unreal/Bodyflip edits or push.
[Current behavior and verification](Labs/FootIKLab/README.md).

**Foot IK October27 - Run turning hover61–94 investigated:** Current setup
is Run38%, stairs16/35cm, yaw300deg/s from1.2–6m, accent400. The right stair
pin releases at59.5 because it needs83.55cm reach versus81.67cm available;
no procedural contact61–72 while the authored ramp root continues. Actual
terrain-seeded NN handoff occurs at73. Its pin strengths are only0–1.60%
on policy frames75–93 (~2.09% at94); floor contact nevertheless returns
around82/91. NN labels mean solver ownership, not absence of neural pins.
The initial NN also slides with weak pinning under this turning command.
Original-controller parity is exact for both sequences, future-window error
<=1.2e-7. Added existing continuous `pins` output for diagnosis, including
phase slicing;152 source and115 continuation poses/roots remain identical.
No gait/IK/tuning/UI change, server restart or push. Distinguish this stair
planner from the incline `surface.js` knee fixes below. The source response
and stair clearance planning both contribute; no forced pins added.
[Details and local evidence](Labs/FootIKLab/README.md).

**Foot IK October27 - exported WalkF comparison fixes vanilla knee fidelity:**
User supplied `Exports/WalkF_Rollout_20261027` (read-only). Two lab errors:
the upper/pelvis decoder re-solved lower knees even with unchanged pelvis,
and Incline/wall at0deg still repinned/re-solved the NN legs. The first moved
knees up to3.95cm relative to the supplied rollout while feet/hips matched;
the second added a12.88deg knee step at60 against the source's0.71deg.
`directional_nn.decode_policy_rows` now composes the upper policy but decodes
lower joints through original lower FK/geometry, preserving predicted thigh
rotations. Both direction generation and nn_worker continuation use it. Frozen
weights, inference, future root window and original NN pin projection unchanged.
With matching source/history, all120 compared frames match the independent
Model Viewer export within0.049mm; rotation-matrix maxerror0.000148. Live lab
uses Run source geometry/settled history, so arbitrary frame numbers are not
the same phase as this fresh WalkF export (geometry alone differs by~0.93mm).
Earlier claims that a pop in the lab's raw NN proved a policy pop were incomplete:
that output still passed through the extra pelvis-decoder knee solve.
**Follow-up: terrain IK repaired and retained on flat ground.** No level-ground
bypass. `surface.js` now filters the terrain residual relative to the NN ankle,
respects natural NN leg extension instead of forcing94% reach, and captures the
incoming shoe orientation without a forced flat/shortened-leg snap. Capture
radius grows continuously from5mm with the requested terrain delta, up to35mm.
Physical shoe support is independent of the hard-pin latch. A deleted platform
can transfer a pin to a finite coplanar replacement containing the same material
contact; actual unsupported deletion still falls normally. Heel/toe roll,
pin yaw, leg length, shoe collision and gravity/thrust rules remain active.
Supplied60 knee step12.88→0.711deg (NN0.711); current left106:9.02→1.99
(NN1.89), left225:7.32→0.59 (NN0.44). Full240/300-frame clips have maximum
extra knee step3.82/3.68deg, with450/547 active pin ticks; corrected poses are
not forced equal to the NN. verify-flat-rollout:24 cases/12,984 frames;
verify-surface:697 checks/60 cases; floor deletion8 cases, root thrust0/45/100%,
and shared Bodyflip adapter1,529 checks pass. Gravity regression compares
unsupported motion; stable supported traction can balance gravity exactly.
createFeet API1 remains compatible. Viewer8890 refreshed, settings/camera and
paused user frame179 retained after visual checks. No server, Unreal or other
lab restarted. NN decoder comparison above remains valid. No push requested.
[Details](Labs/FootIKLab/README.md).

**Foot IK October27 - root marker and optional incline gravity:**
**Viewer / persistence:**8890 API6/save protocol2/PID996 uses
snapshots/overnight-state.json, also explicit in launcher and /health. Reopening
loaded the old45deg preview file; restored last observed90deg wall/Walk69%/
yaw300 from1.2-6m/accent400/ghost on/trim0-299/frame202. Current camera retained;
prior camera unavailable, exact historical missed-save cause unproven. Saves
now merge only edited fields, before motion preparation; startup/idle tabs do
not resave the scene. Close flush/Refresh, atomic durable writes and ordered
client saves prevent stale tab/request overwrites. Old save clients rejected.
Client/server persistence checks and real immediate reload/app Refresh pass.
Only Foot IK restarted; no other server/editor or motion-solver changes.
 Root checkbox
appended after Bones. New mode and Minimum gravity incline / Full gravity % /
Energy conservation % appended at bottom of More options for Incline / wall.
Defaults off/45deg/100%/100%; old scenes retain motion until enabled.
**Revised gravity semantics:** at/above minimum, full gravity acts with no
automatic compensation; no angle ramp toward90. Full gravity % removes
world-vertical root thrust from both velocity drive and the commanded height
spring.100% gives exactly-9.81m/s2 before collision responses;0% retains thrust,
not gravity cancellation. Horizontal thrust and solid collisions remain.
Energy conservation still projects at0% / transports at100%, once per surface
transition.173 checks/18 clips plus3 actual current Run-policy Walk cases pass;
100% has359 active frames at exactly-g and344 impulse-free intervals with exact
velocity integration. Off and below-threshold motion unchanged. Root and
controls remain in place, saved settings/frame retained. Enter commits and
blurs numeric entries; arrows then step playback. More options header stays pinned while scrolling; clicking outside closes it. **Delete floor F** appended
last in More options for Incline / wall only; default-1 keeps it. Selected60Hz
frame removes geometry, collisions and foot pins with no leftover floor force.
Reverse playback restores the floor. Incline extends in both plane directions,
sized for the whole clip's travel/fall, including below the floor. Eight deletion
clips and173 gravity checks pass; browser verified Enter, deletion100 at101,
floor restored at99, and return to-1/frame101. Settings/camera retained. No NN/Unreal/Bodyflip,
shared createFeet API, or server changes for this revision. Receipts in
snapshots/incline-gravity-verification.json and root-thrust-verification.json.


**Foot IK October26 - planted yaw and accepted ankle correction:**
**Wall cutoff removed:** standalone surface root no longer expires after0.55s
Walk/0.85s Run, disables future pins or latches drive to zero. Valid contacts,
reach/ankle/collision limits, bounded traction and gravity now determine motion;
mode reflects current support/vertical velocity. Current Walk69/yaw300/90deg
continues upward at2m/s at206 instead of standing still after timed fall.
17 full clips pass contact-driven checks including both gaits/approaches and
0/45/75/90deg. Existing broad suite stops on its lateral0deg material-pin-slip
assertion; that clip's poses/metrics are byte-identical to pre-change, so this
is not a new regression and is not claimed as a full-suite pass. Shared
createFeet API/host controls unchanged. No NN, Bodyflip, Unreal or restart.
Receipt: snapshots/contact-driven-wall-verification.json.

**Pelvis accent follow-up:** appended Step accent % at the bottom of More
options, range0-400 (expanded on request).100 preserves the previous pelvis rhythm exactly;0 disables
only this accent. Current Walk36/yaw300 UI set to200: extra loading2.107->4.214cm.
Existing80ms smoothing,10cm accent ceiling, pelvis cap and both-leg extension
bounds retained. Root/ankle paths, material pin orientations and contact timing
unchanged; free ankle articulation still follows the corrected calf.211 main
and11 departure regressions pass; six accent levels checked on current actual
NN source plus Walk/Run ascent/descent clearance/reach spot checks. Original
NN checkpoint/runtime unchanged; terrain-exit continuation uses adjusted poses
as before. No server restart, Unreal/Bodyflip changes or push. See
verify-step-accent.cjs and snapshots/step-accent-verification.json.

**Reported225 audit, no motion change:** phase60/stairs/yaw300 current setup
hands off at180; at224 the right knee reaches0deg bend,226 reaches20.79deg.
Displayed225 is exactly resumed NN output; the100ms handoff blend ended186.
Replayed the same seeds/root commands through original controller functions:
referenceError0, root-window error2.98e-8. Pop is already in30Hz decoded poses,
not created by render interpolation or stair IK at225. This continuation uses
terrain-seeded history, so this does NOT prove ordinary untouched flat rollouts
always pop. Earlier35.5 explanation does not explain225. Trace:
verify-knee-225.mjs --reference / snapshots/knee-225-audit.json. UI restored225.
**Flat-approach audit, not yet fixed:** current UI phase60/stairs/yaw300 has
terrain influence from35.5, before the first tread. At that first tick the raw
right sole is2.591mm below flat ground; full floor projection raises it despite
IK weight0.000207, displacing the knee11.51mm. This is a lab entry correction,
not changed NN weights. Flat terrain preset matches raw NN in all601 samples.
Diagnostic: verify-flat-knee-audit.mjs / snapshots/flat-knee-audit.json.
No production code or UI settings changed during this audit.
**Departure follow-up:** the yaw-only arc skip also skipped horizontal swing
travel, causing the reported right82 foot to rise in place. Restored forward
progress independently of the bounded height envelope. Planted turns now reserve
4cm beside risers; blocked turns release with lift room, preserving grounded
toe-off instead of forcing a sharp lift. Current right lastpin65.5, toe-down16deg,
yaw43.42deg.72-82 advance9.96->35.36cm; early vertical peak3.65->1.85m/s.
211 base+6 ankle+262 yaw+11 travel checks pass. Browser reviewed full0-299,
close-up64-90; restored82/camera. No new UI, NN, server or Bodyflip changes.
Earlier frame67/contact-margin receipts are superseded by this follow-up.
Old ankle comparison removed, signed shoe-plane pitch fix retained. Foot yaw
option appended at bottom of More options(default45deg). Planted heading now
turns about heel/toe material support, transferring toward projected sole centre
nearflat; shared surface.createFeet uses the same helper. Original NN allows
rotation with integrated support-point ankle compensation; it has no yaw cap.
Knee poles remain NN/anatomical. Current Walk91/yaw300/start1.2m right67 body yaw
75->41.24deg, knee54.81 vsNN54.27. FullIK pole step1.858deg/120Hz, accel.240;
shoe step8.001deg. Riser-clearance limit can release a trapped contact; turned
swings avoid global endpoint-arc inflation. Final smoothing fades with influence,
fixing the initial straight-knee jump.211 motion+6 ankle+101 surface endpoint
checks pass,12 shared zero-yaw goldens unchanged;262 focused checks pass across
14 actualNN clips and16 synthetic pivot cases. Independent knee audit retained.
Browser refreshed/checked67,70 and option; frame/camera retained. No NN, Unreal,
server restart, Bodyflip file changes or push. See FootIK README/shared contract.

**Foot IK October26 - actual NN yaw window, Run-policy Walk, distance controls:**
Active8890 now supplies previous/current/eight future turning root carriers to
Run181751 + Upper82500, including per-frame pose encoding/rebasing and the
original continuous learned pin projection. Removed post-inference spin and
handoff counter-spin. Walk uses Run at F2/B1.5/sides1.8m/s; Run retains native
F5/B3/sides3.5m/s. Current+previous corrected world poses seed terrain exits.
Root yaw is available on all terrains. Start m / Stop m appended below its
speed in More options; blank Stop is unlimited, stopped yaw holds its heading.
Distances use the horizontal commanded root course, shared with a new metre
counter directly below the frame counter in the existing76px width. Actual
incline gravity mass-point travel can differ from that commanded course.
Future NN windows anticipate both distance boundaries; no elapsed-time gate.
Original training encoder/controller parity checked on five5s directional/yaw
rollouts and Walk/Run boundary cases.211 procedural regressions and12 exact
shared-surface baselines pass; material pins remain anchored. Shared Bodyflip
createFeet API unchanged. One CPU thread, lazy worker, cached replay; no server
restart, Unreal, Bodyflip changes or push. Existing desktop uses8890 and
snapshots/overnight-state.json. Earlier post-spin verification is superseded;
see FootIK README, nn-root-window and yaw-distance receipts.

**Bodyflip October26 - flip/pose blending in More options:** appended Turn,
Flip In/Out and Pose In/Hold/Out after Rebound in the existing viewport panel.
Angles/axis/delay/pose stay in the marker popup. Selection persists when it closes;
the panel identifies J1/J2 and edits that jump without moving playback. New turn
ease periods support constant-speed middle motion, zero ramps and proportional
fitting within Turn. Missing fields migrate to half-duration each, preserving
all existing quintic turns exactly.47 editor +84 motion checks pass; isolated
browser verified both layouts, selection and native numeric edits/playhead.
Saved settings intercepted during verification, browser closed. Refresh needed;
no Unreal, server restart, live-state overwrite or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - per-jump flips and pose slots:** existing marker popup
now appends signed Flip/Twist totals, axis, delay0 and smooth turn duration0.8s;
No pose plus four temporary slots, with collapsed In/Hold/Out timing. Motion
starts after support release; root-heading flip axis, pelvis-vertical twist,
smooth pose entry/exit. Root trajectory and pinned frames unchanged. Both render
and landing NN use the same authored pose; landing interrupts remaining motion
and continues from the current pose. Settings persist per jump/scene; edits keep
playhead time, click-away applies, Escape closes before platform shortcuts.
331 checks pass including12 actual NN landing checks; isolated actual-app browser
render verified two popup sizes and ten motion samples. Test saves were blocked;
owned browser closed. Automatic review blocked temporary browser-profile cleanup
("blocked by policy"); those two Saved/BodyflipLab folders remain. Four
placeholders await the user's poses tomorrow; source
mapping in `jump-motion.js`. Desktop Refresh required, no server restart, Unreal,
other-lab work, live-state overwrite or push. [Details](Labs/BodyflipLab/README.md).

**Foot IK October25-26 - directions and gravity-surface prototype verified:**
isolated apiVersion6 preview8890/PID16304 uses its own overnight-state.json.
Main8878/desktop and earlier8879 remain older processes: automatic approval
review blocked FootIK-only restart ("blocked by policy") despite user approval.
No alternative termination, Unreal, other-lab mutation or push. Main saved
Run/phase21/frame73/camera/settings remain unchanged. Genuine matching backward
and lateral lower/upper NN contexts, native speeds, both-pose continuation
history; flat output exact NN. Travel-basis, bidirectional heel/toe reach roll,
landing continuity and lateral early-clearance corridor corrected.703 grouped
direction checks over48 full5s clips plus focused releases; accepted forward
phase21 Walk/Run byte-identical after final corridor fix,20 targeted checks pass.
Incline/wall adds angle, approach and upright bias at bottom of More options.
Gravity mass-point/capsule root plus kinematic NN limbs, bounded support then
fall; NOT full Jolt/live Unreal. Initial wall clearance and folded free-leg
knee stability fixed without moving pins.696 checks/60 cases +101 endpoint
checks/16 cases and independent32-case shoe-face review pass; worst reviewed
shoe penetration0.07671mm.71 actual HTTP checks +6 mock service guards pass.
Browser checked backward/lateral trouble intervals,45/90deg toward/parallel and
upright endpoints; no console errors. Preview paused120,Walk,45deg Toward,
Upright55%. Source safeguards newer than running8890; desktop8878 NOT activated.
No idle NN worker retained. See FootIK README, current receipts and preview PNG.

**Foot IK October25 - actual NN continuation, preview active:** `handoff.js`
now seeds the original lower/upper policies from corrected current and previous
30Hz poses when the root is past the course, both feet have released contact,
and both rendered shoes clear the exit plane. Current Run/phase21 hands off
at73 using71/73, Walk/phase21 at190. Exact incoming pose retained;100ms local
velocity carry then full newly inferred NN pose, no cached-gait catch-up. Root
speed retained, earlier terrain frames untouched. One CPU thread in a FootIK-only
lazy worker, frozen Bodyflip loader/models read-only, local bounded seed cache,
30s idle retirement verified. No training/GPU/Unreal/other-lab changes or push.
28 new inference/integration checks +346 existing procedural regressions pass;
original-controller reference error0, no riser penetration. NN's existing sole
box ground error remains (Run9.37mm,Walk4.82mm, within raw NN baseline).
**Activation blocked:** user explicitly approved restarting ONLY FootIK8878,
but automatic approval review rejected the scoped restart again with only
"blocked by policy". No alternate kill attempted.8878 remains apiVersion4/PID996;
do NOT claim it activated. Verified apiVersion5 preview8879/PID15472 is retained
for the user; inspected73/80/90 and restored paused73/settings/camera. Main8878
needs manual server restart to load `/resume`; desktop Refresh alone is not enough.
See FootIK README, `handoff-verification.json`, `handoff-suite-status.json`.

**Foot IK October25 - running recovery advances after departure:** Run/phase21
left66-80 followed the NN's backward fold; the recovery bridge was skipped
because its terrain-exit endpoint was still behind the departure in pelvis
space. Find a compatible forward-moving endpoint within the same source swing
and retain correction for that leg until it joins (current94), independently
of terrain influence. Final smoothing respects the available forward clearance
corridor rather than buying premature riser crossing with extra lift.70-80
pelvis-local travel -21.73 ->+20.48cm; forward progress from about70 after initial
toe/riser clearance. Grounded roll/contact timing, right leg and pelvis retained.
346 checks pass plus8 phase/course spot checks. Prior ankle regression's airborne
path/state invariants were updated for this deliberately changed path; rotation,
contact, clearance and reach thresholds retained. IAB refreshed/inspected66/70/78,
restored78/camera/settings. Desktop Refresh needed; no server/Unreal/NN/UI/push
changes. See FootIK README and run-travel verification receipts.

**Foot IK October25 - running ankle exit:** Run/phase21 frame81 held the old
toe-off world pitch while the calf folded, producing104.49deg NN-relative ankle
error and a33.85deg rotation in one120Hz sample at83. Final swings without a
next retained contact now retire the cap over20-40% of the source gait cycle;
the calf-relative rotation no longer fades back toward the held pose at the
terrain exit. Whole-shoe clearance still bounds rotation.81 error0.21deg,
75-85 peak11.12deg/sample. Foot trajectories, material pins, support timing and
pelvis unchanged.288 targeted checks pass; no assertions relaxed. Browser
refreshed/checked81 and83, restored81/camera/settings. No server restart, NN,
Unreal or UI edits/push. Desktop Refresh needed. See FootIK README and
`run-ankle-verification.json` / `run-ankle-suite-status.json`.

**Bodyflip October25 - approved motion checkpoint pushed:** verified remote
`codex/standalone-sim` at `eb74a1a6e5e89e52a703f1f02bca9941f0b0724a`;
recovery inventory verified (8883 files). Includes Idle/shared jump controls,
flat new scenes, capsule
collision with actual NN landing continuation, free camera, matched whole-body
jumps, opaque animation-leg overlays, motion-preserving blends and knee braking.
Walk frame59 now bends28.67deg normally instead of71.66deg backwards; no straight
hold or repeated recoil, original blend deadlines/contact/root retained.265
automated checks pass. User accepted the result; agent visual tools were blocked.
Source, idle recording and verification files are included; live scenes/settings,
previews, inference caches and unrelated sessions stay local. Landing requires the
existing frozen models/seeds and Stepper/Torch runtime; see restore notes.
[Bodyflip details](Labs/BodyflipLab/README.md), [recovery](Docs/Recovery.md).

**Foot IK October25 - final-level toe-off rotation:** left191 was stuck at41deg
despite NN79deg and sufficient clearance. Final same-height departure now releases
the stair anti-roll cap and carries the release offset onto moving calf-relative
NN rotation over120ms; whole-shoe clearance retained. Earlier transfers/landing,
ankle paths, pelvis rhythm and pin timing unchanged.191 pitch79.78 vs NN79.35,
quaternion error38.55 ->4.55deg, sole gap2.65cm.248 targeted checks pass; no
assertions relaxed. IAB refreshed/current191/camera/ghost/settings retained.
Desktop Refresh needed; no server/Unreal/NN/UI work or push. See FootIK README
and `level-exit-verification.json` / `level-exit-suite-status.json`.

**Foot IK October25 - approved checkpoint pushed, pelvis rhythm local:** remote
`codex/standalone-sim` verified at `3bc2cde7304da2bf67491283e6ba9efbce0592e0`;
recovery manifest verified. Only FootIK source/runtime banks/tests and scoped
journal entry included; unrelated work/live state excluded. Subsequent local
pelvis change times smooth loading/pull-up to actual plants, bounded by BOTH
legs' existing extension. Root ramp, ankle trajectories and pin/release timing
retained; calf-relative free ankle and exact material heel/toe pins retained.
Current phase21/Clearance1 added loading max3.37cm, speed0.240m/s, acceleration
3.55m/s2;318 checks pass, no assertions relaxed. Browser checked106/114 then
restored latest paused6/settings/camera. Desktop Refresh needed; no new UI,
server restart, Unreal changes or push of this pelvis experiment. See
[Foot IK details](Labs/FootIKLab/README.md) and pelvis-transfer verification receipts.

**Foot IK October25 - approved checkpoint:** standalone Foot IK Lab preserved
with frozen Walk/Run NN phase banks, terrain placement, grounded heel/toe pins,
smooth swing recovery, full-body/ghost rendering, desktop launcher and regression
fixtures. Includes gentler right155 toe-off (35deg on NN-return departures,
45deg on retained-contact transfers);307 checks passed. Live playback state,
screenshots and unrelated session work excluded. Pelvis stair-transfer work
starts AFTER this checkpoint; see Labs/FootIKLab/README.md for current behavior.

**Foot IK October25 - gentler right155 toe-off:** higher-step departures returning
to NN gait use35deg grounded toe roll instead of45deg; transfers into a retained
contact keep45deg. Early departure timing/material heel-toe pin are unchanged.
Current phase21/Clearance1cm right155-161 peak upward speed4.030 ->3.332m/s
(17% lower), peak120Hz velocity change1.629 ->1.446. Continuous forward/up motion,
release still155, right89-102 identical. All299 existing +8 focused checks pass;
receipt `Labs/FootIKLab/exit-toeoff-verification.json`. See lab README for detail.
IAB refreshed/inspected154 and157, restored155/settings/camera. No Unreal,
server restart, new UI, other-lab edits or push. Desktop app needs Refresh.

**Bodyflip October25 - carry motion across blends:** shared stateless pose/velocity
offset transition replaces captured-pose easing for Body, support release, fall
loop, ledge falls and missed-support recovery. Shoe alignment carries incoming
rotation; contact fitting/heel-toe controls retained. Attack entry/return preserve
authored velocities and hit-window timing; landing still seeds the actual NN.
Body/Leg sliders and procedural pelvis/contact ownership retained; no new controls.
187 checks pass:38 motion,53 matched-body,48 contact,24 pacing,24 capsule/NN landing.
Source slope changes accounted for; release angular-rate error0.00850rad/s at1us.
Contact fixture later-event expectation updated for changed incoming poses; its
geometry/continuity checks retained. Syntax passes; no visual QA. Refresh needed,
with possible landing recomputation. Only existing single-thread CPU worker used;
no server restart, live-state overwrite or Unreal changes. [Details](Labs/BodyflipLab/README.md).

**Foot IK October25 - early departure WITH grounded roll:** higher steps again
prepare up to50ms early; author heel/toe pivot roll before release, up to45deg
toe-down, with smooth outgoing velocity. Material contact/whole-shoe checks and
airborne downward-rotation limit retained. Height-ceiling entry eased to200ms to
avoid post-riser braking;161 default gap18.92cm vs previous14.02 (old23.22).
Current phase21/clearance1 right89 finishes grounded roll,89.5 lifts;88-102 peak
up speed5.54 ->2.93m/s, velocity kick3.11 ->0.84m/s.299 checks pass; previous84-92
failure resolved. Timing/ankle-handoff/height tests updated for requested behavior;
collision/reach/knee/velocity/flat-NN checks retained. Browser checked89/92 and
restored92/settings/camera/ghost; desktop Refresh needed. No UI additions,
Unreal/server/NN/other-lab work or push. [Details](Labs/FootIKLab/README.md).

**Bodyflip October25 - other leg red / frame59-60 diagnosis:** Anim other leg
changed from orange to red; support stays green, Raw leg red. Syntax checked.
Saved Scene 2 left leg near-stop comes from Body0.2s blending out of a captured
launch pose with zero-slope smoothstep: weights3.638%/10.201% at59/60; forward
ankle advance8.47mm versus48.09mm at56-57. Incoming gait velocity is not carried
through this blend. Diagnosed only, motion unchanged. Refresh loads color.

**Foot IK October25 - bound smoothing surplus:** final trajectory height fit
now aims for NN/pre-fit height plus existing clearance, with collision/reach
priority and gradual application after toe-off. Initial release velocity and
material pins retained. Phase21 right161 gap23.22 ->14.02cm, extra NN ankle lift
20.41 ->11.28cm;159-167 keeps advancing/upward.87 focused checks pass; broader
210/211 with the same known84-92 lift-acceleration failure. Existing release
kick6.80m/s unchanged, not fixed. Prep~335ms/cached playback, no UI additions.
Browser checked161/restored latest157/settings/camera/ghost; desktop Refresh
needed. No Unreal/server/NN/other-lab changes or push. [Details](Labs/FootIKLab/README.md).

**Bodyflip October25 - opaque overlay depth correction:** animation leg shapes
were already shared with the agent, but the old X-ray pass disabled depth testing
and writes. Opaque rear triangles consequently drew over front triangles. Moved
all three leg overlays into the normal opaque scene pass, before translucent
platform sides; normal self/scene occlusion now applies. Colors retained. Syntax
checked; no visual QA, motion/physics changes or server restart. Refresh needed.

**Foot IK October25 - retain toe roll / stop airborne over-rotation:** removed
the50ms early-release rule. Phase21 left68-71.5 keeps its material toe pin,
22.39 ->52.29deg down; releases72. Planned/calf-relative swing rotation cannot
continue downward past the actual release angle (previously nearly90deg).
Browser checked71/77, restored69/settings/camera/ghost.79 focused checks pass;
broader suite210/211: default fixture84-92 lift-acceleration bound now fails
without early release. Known regression retained explicitly, assertion unchanged;
NOT all-green. Collision/reach/pins/knees/flat NN checks pass;72 backward snap
still absent. Prep~0.35s/cached playback. Desktop Refresh needed; no Unreal,
server, NN-bank or other-lab changes. [Details](Labs/FootIKLab/README.md).

**Bodyflip October25 - animation leg volumes:** Anim other leg added immediately
right of Anim leg, independently showing the opposite leg on the matched clock.
All three animation overlays now use agent-sized capsules and foot/toe boxes,
sharing geometry definitions; now fully opaque, green for supporting Anim leg,
orange for Anim other leg and red for Raw leg. Tooltip colors updated; syntax passes.
No extra physics bodies or motion preparation. Scene-persisted, default off.
53 focused checks and syntax pass; no visual QA. Refresh needed. No server/Unreal
changes or live-state overwrite. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - whole-body match at normal speed:** Match foot now starts
all animated joints at the matched source frame on PUSH, at1x; removed the
support-only slowdown. Procedural pelvis/root, pinning, loading locomotion and
separate Body/Leg entry blends retained. Fall-loop animation advances with the
shared clock; red Raw leg stays on original timing, purple previews matched timing.
47 focused checks pass (both feet, standing, zero loading, blends, source poses,
root/pins and reverse seek); root/pin differences zero. Syntax checked, no visual
QA. Refresh needed; landing NN will prepare from the changed pose. No live-state
overwrite, server restart or Unreal work. [Details](Labs/BodyflipLab/README.md).

**Foot IK October25 - swing continuity + sole support:** ankle-ray selection
misclassified left68 as flat/NN stance and selected the preceding last tread.
Use main sole centre for support;68 now rolls on a material pin with96.5% reach.
Higher steps get up to50ms lift preparation. Root arrival no longer dissolves a
trailing pin;175-177 retains last-tread support, then departs continuously. Final
bounded XYZ trajectory smoothing follows all positional edits; smooth landing
pitch cap retained.72 backward -4.84 ->forward1.92m/s; peak left-foot velocity kick
6.63 ->0.94m/s in phase21.282 checks pass, prep~0.37s/cached playback. Timing tests
updated for actual contact/foot handoff; full geometry/reach/pin checks retained.
Browser checked68/72/176 and restored latest72/settings/camera/ghost. Desktop
Refresh needed. No NN bank/Unreal/server/other-lab work. [Details](Labs/FootIKLab/README.md).

**Bodyflip October25 - Refresh placement:** moved the existing Refresh button
beside the brand, above the viewport left edge, per the marked screenshot.
HTML/CSS only; existing refresh/save/playback handler retained. Refresh to load.

**Bodyflip October25 - original jump leg overlay:** Raw leg checkbox appended
after Free camera. Red supporting leg follows normal jump timing, bypassing Match
foot retiming/IK/release blend; purple Anim leg remains the retimed target. Both
are aligned to the displayed pelvis. Default off, scene-persisted, redraw only.
Current Scene 2 numerical comparison agrees with source animation to 1.15e-16m;
JS syntax passes. No visual QA. Refresh needed; no server restart, live-state
overwrite, NN inference or Unreal changes. [Controls](Labs/BodyflipLab/README.md).

**Foot IK October25 - first-riser shoe clip:** current phase21 left41 had ~7cm
edge/face intrusion missed by corner-only checks. Full box-face/tread-footprint
clearance now shared by the planner/reach/orientation checks; boundary-only
clipping, cached playback retained. Existing smoothing also covers NN-exit swings,
removing the late175.5 lift snap in this phase.270 checks pass; independent dense
face sampling confirms41 clear, actual material pins retained. Preparation~0.37s.
Browser checked41 then restored188/settings/camera/ghost; desktop Refresh needed.
No NN bank/Unreal/server/other-lab edits. [Details](Labs/FootIKLab/README.md).

**Foot IK October25 - pelvis-local release progress:** replaces world-forward
recovery with a curve, source-release check, collision-bound fit and gait rejoin
measured in the moving/rotating pelvis frame. Saved phase49 right137-147 local
advance4.99 ->15.21cm; every139-150 sample advances,143-147 no relative-speed dip.
Initial137-138 still retreats1.27mm for toe/riser clearance; no zero-drift claim.
261 checks pass, no added vertical lift/UI/playback work. Browser compared147,
restored current150/settings/camera/options. Desktop Refresh needed. NN banks,
root/current pins, Unreal and other labs untouched. [Details](Labs/FootIKLab/README.md).

**Bodyflip October25 - free camera:** checkbox appended after Show jump. QZDS
camera-relative movement; left-drag looks from current eye, inverted Y retained;
existing wheel zoom/unlimited dezoom, middle-pan and target drag retained. Enabling
preserves the current view; disabling now snaps COM to screen center, clears pan/
offset and retains viewing direction/distance. Per-scene camera persistence,
explicit presets return to follow.
No idle camera RAF, inference or motion preparation; keyboard movement also works
paused and stops on focus loss. Writing/Ctrl+Z/WER keep their input ownership.
16 camera checks pass;21 scenes and14 refresh passed on initial free-camera work; visual QA
unavailable. Refresh needed. No server restart, state overwrite or Unreal work.
[Controls](Labs/BodyflipLab/README.md).

**Foot IK October25 - forward recovery after early release:** reach-released
trailing feet no longer wait for the NN's remaining stance while lifting. Cached
forward recovery meets the moving gait, with shoe collision bounds and smooth
anticipation; rejoin early enough to avoid a later waiting stall. Current pins,
root, NN banks/recurrence retained (no live reseed). Saved phase49 right134.5-140
forward2.29 ->11.75cm; left167.5-171 4.55 ->8.91cm, unchanged vertical lift.
257 checks pass; no added UI/playback work/process, prep230ms. Browser checked
140/171 and restored135/settings/camera/options. Desktop Refresh needed. No
Unreal or other-lab changes. [Details](Labs/FootIKLab/README.md).

**Foot IK October25 - remove pre-landing toe-up rebound:** calf-relative swing
was handing back to an airborne NN toe-up peak. Terrain landing now has a shallow
5deg heel lead and late swing aims directly at contact orientation; material
heel/toe pins and negative-pitch push-off retained. Contact geometry now adjusts
ankle trajectories (supersedes preceding identical-path claim). Isolated riser
floor clamps smoothed with a constrained upper envelope; existing knee bounds pass.
Saved phase49 approach77-88 peak29.4 ->5deg;135-141 <7.3deg.245 checks pass.
Browser refreshed/current135 restored; Desktop Refresh needed. No new UI/process,
Unreal, training or other-lab changes. [Details](Labs/FootIKLab/README.md).

**Foot IK October25 - calf-relative swing ankle:** swing rotation now preserves
NN ankle articulation relative to the IK-adjusted calf, smoothly handing back to
world-space contact orientation near pins.120ms anticipation and full shoe-corner
clearance limit; exact heel/toe material pins and hip/knee/ankle paths retained.
Saved phase49 mean SWING ankle error23.45 ->8.05deg;79:63.8 ->39.5deg (near83
contact).211 +18 velocity +7 clearance +6 ankle checks pass; default prep254ms,
no added playback work/UI. Supersedes swing WORLD-rotation test; Flat stays exact.
Browser refreshed/restored79 and settings; Desktop Refresh needed. No Unreal,
server, training or other-lab changes. [Details](Labs/FootIKLab/README.md).

**Bodyflip October25 - capsule landing seeds the actual NN:** corrected the
cached-gait snap. Capture landing + preceding30Hz pose; encode lower41/upper90
history with original frozen Run/Walk/Upper policies and codecs. First output is
exactly the landing, then recurrent predictions follow capsule-resolved movement.
Idle returns to zero-speed Walk NN; its starting idle loop remains authored.
Later jumps use the new continuation; air rotation edits rebuild its seed.
No display crossfade. Kinematic planned-pose feedback; not live Jolt/attack feedback.
Capsule remains native-default30cm radius/86cm half-height, static-slab sweep/slide;
no editor/Blueprint query. 24 capsule +11 NN/codec +20 idle +21 scenes +14 refresh
+24 pacing checks pass. Entry gap0.000268mm over0.1us; compiled step equals original
functions through30 recovery steps, current/prior-pose perturbations affect output.
Single-thread CPU inference only during preparation, serial worker expires30s idle;
compiled steps and bounded result caches. Cached requests14ms; new1s rollout0.245s;
first uncached setup can take seconds (7.4s measured with compiled weights).
Only own server8876 restarted to API5. Saved state hash unchanged; no UI movement,
Unreal/other-session work or push. Refresh needed; visual QA unavailable.
[Current behavior, limits and verification](Labs/BodyflipLab/README.md).

**Foot IK October25 - reduce leading-foot overclearance:** fitted retained-contact
swing heights to actual shoe clearance/NN height, lowering the global arc's surplus
as the foot passes the hip. Keep trailing toe-off, forward timing, pins and root.
Saved phase49 frame163 sole gap20.17 ->5.42cm;132 forward swing samples mean
14.07 ->8.07cm (43% reduction).211 +18 velocity +7 clearance checks pass without
loosening prior motion/knee/collision bounds. Cached preparation164ms; no extra
playback work. Refreshed browser at163, original camera/settings retained.
Desktop Refresh needed. Contained FootIK only; no Unreal/server/training work.
[Details and measurements](Labs/FootIKLab/README.md).

**Foot IK October25 - entry clearance / exit velocity:** measured saved Walk
phase49: late spatial fade caused7.14m/s upward kick near43; entry preparation
now spans toe-off to higher landing, with constrained smooth shoe clearance.
Peak40-48 upward speed0.492m/s, peak ankle height44.14 ->43.07cm. Exit arc's
artificial forward lead caused177-179.5 to stall while NN kept advancing.
Unpinned landings now preserve NN forward progress plus contact offsets, retaining
clearance. Velocity detector passes phases0/.25/.49/.75; root remains2m/s.
211 existing +18 velocity checks pass. Supersedes stairs F41 raw-NN assertion:
first higher landing is now anticipated; Flat remains exact across all50 slots.
No live NN/history reseed, per-frame solver, server/Unreal/Bodyflip changes.
Ghost translucency appended below existing More options; live redraw, persisted,
0solid/100invisible/default70. Browser43/178 checked, no console errors; restored
paused172/phase49/camera/ghost16/terrain10. Desktop Refresh required.
[Current behavior and evidence](Labs/FootIKLab/README.md).

**Bodyflip October25 - shared controls and jumps in Idle:** corrected the prior
Idle-only bypass. Idle is a stationary motion source for the SAME sequence planner
as Run/Walk. Jump markers, + Jump, trim/loop, all options and debug views visible;
standing/repeated jumps, load/push/fall, attacks and air flip/twist use shared paths.
Idle source loops with Phase offset; no markers means stationary idle. Fixed
zero-speed edge handling (original flat platform extends5m, no spontaneous fall).
20 idle checks pass including repeated/delayed pushes, phase, reverse seeks and
air rotation; scenes21, refresh14 and run-pacing24 pass. No new controls, UI moves,
NN request for idle, state overwrite, process restart, Unreal work or push.
Refresh required; visual QA unverified. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - Idle replaces Space:** removed Space sequence option;
legacy saves migrate to Idle. Reuses frozen neutral idle animation (301frames,
30Hz,10s) with original provenance; upright, stationary root and grounded shoes.
No flip/twist rotation. Existing platforms remain visible/editable; transport
samples idle clock, switching cancels old flight/pending run response. Jump tuning
and markers retained.11 idle,21 scenes,14 refresh checks pass; visual QA unavailable.
Refresh required. Small local animation export only; no Unreal, inference/server
process, state overwrite or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - fresh flat scene button:** New scene appended at the far
right of the header, after existing scene tools. Saves outgoing scene, creates
named independent setup with original flat platform only, default tuning/camera,
one default jump and paused frame0. Carries current platform migration version
so reload does not respawn inclines. Copy remains duplication. Scenes21 and
refresh14 checks pass; syntax checked. Refresh to load. No live state overwrite,
server restart, Unreal/training work or new push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - named scenes and curated checkpoint:** added scene picker,
Copy and Rename after existing header controls. Legacy current setup becomes
Inclines. Copies retain tuning/platforms/jumps/target/camera/playback/brackets and
start paused; switching saves outgoing work then reloads the selected scene.
Library stored locally in state.json, current state kept top-level for compatibility.
Save writes serialize; failure leaves current scene open. Reload isolates undo.
Current user setup also preserved in tracked saved-profile.json. Scenes16,
refresh14, pacing24 checks pass; visual QA unavailable (kernel-assets error).
Refresh required. Bodyflip source, focused tests/receipts, fixture, saved profile
and Bodyflip-only journal updates prepared for requested push; unrelated Unreal,
FootIK, training and audio work excluded. No new process, server restart or
Unreal activity. [Controls and restore](Labs/BodyflipLab/README.md).

**Foot IK Lab October25 - full-body shadows:** replaced rejected foot-only
footprints with real character depth-map shadows on terrain/body. One1024Â² map
(about4MiB), four-metre COM window, one extra draw reusing the existing mesh upload;
cached for unchanged poses/camera-only redraws. Character casts, terrain receives.
32-sample GPU check: extra depth pass median0.088ms/p950.145ms, excluding main
scene shading; cache/error checks pass. Syntax and visual F25/F150 checked, no
browser warnings/errors. Restored F25/camera/settings; no motion/UI/tuning changes,
server restart, Unreal or training work. Desktop app needs Refresh.
[Details and measurements](Labs/FootIKLab/README.md).

**Foot IK Lab October25 - knee poles / retained toe-off / trailing rotation:**
The previous soft-reach fix addressed extension but missed knee-plane jitter.
Filter IK poles in pelvis space, transporting neighbouring planes to the current
leg axis before a small Gaussian average; fade with terrain influence, exact NN
flat/approach/exit unchanged. Default stair-course max pole-increment change
4.56 ->0.423deg at120Hz; reversal around80 about4.40 ->0.423deg.
Removed the premature35deg extra-roll cap: contact can now use70deg toe-down,
extra correction slew540deg/s. Material sole pivots and heel/toe transfers remain
fixed in world space, ankle follows the arc. Trailing foot stays pinned101-102;
101 pitch -57.4deg. Replaced fixed0.1s release with swing-position-driven rotation:
retain toe-down behind pelvis, blend into NN as foot advances or approaches its
next landing;107 remains -67.1deg. Reserve bounded toe-off room before rising
risers and delay colliding forward travel while the pointed shoe lifts.
Rising swing now coordinates forward/upward progress between actual contacts,
with a smooth clearance arc fitted to the shoe corners. Supersedes height-only
Hermite lift, which left the trailing foot rising vertically around108.106-110
now travels15.1cm forward /15.1cm up, previously2.3cm/13.0cm.84-92 remains a
continuous ascent at1.61-2.47cm per120Hz sample. Fixed a missed exit case: requiring
a retained landing pin skipped the168-198 swing and restored per-riser lifts.
Exit swings now plan to the NN endpoint too.171-176 rises1.58-2.01cm per120Hz
sample with >=2.39cm forward travel;169-181 lift-acceleration check covers178.
Ascending exit recovery now fades over12 samples and ends when the root has
left the ramp and both NN shoe footprints lie over the final level plane.
Walk is exact NN from181.5 (formerly205.5); Run from74.5. Flat preset/source banks
were already exact and remain unchanged. Toe pins retained through164-168;
no new UI or per-frame work.
212 checks pass: whole-course pole continuity,101 pin,107 trailing rotation,
material anchors,50 cached flat phase slots,8 gait/terrain presets and existing
strict motion bounds, continuous84-92 ascent/early clearance and diagonal106-120
travel.104 knee flexes faster with forward swing (max8.72deg/displayed frame,
limit10); acceleration bound1.5deg and global motion limits unchanged. Source NN gait,
full collider ghost, shadows, UI layout/options retained. Cached preparation
~170ms default Node check, no live per-frame IK/inference or Unreal/Bodyflip work.
Browser170/174/182 checked with no console errors, refreshed and restored to
paused178 with user's camera/settings. Desktop needs Refresh. Details in
[Labs/FootIKLab/README.md](Labs/FootIKLab/README.md).
Initial prototype distorted
the real NN gait: generic flat swing lift plus endpoint division raised the left
foot84.3cm at F41; copied straight-knee fallback pointed backwards. Rewrote the
terrain planner/solver. Flat approach/exit and Flat preset now return exact NN
poses; bounded terrain clearance, anatomical knee hinge, preserved shoe rotation,
rate-limited reach-only pelvis correction and early unplant. Walk bank/checkpoint
provenance verified (July5 8bae21c5b315,2m/s); no source/stride substitution.
Checks include all50 cached phase slots unchanged on flat, exact F22/F41,
per-frame flips/teleports, contacts/reach/clearance and source immutability.
Flat Walk max rotation step8.71deg equals source maximum; no IK loops.
Seconds/bracket tooltips replaced by frames. Desktop app shortcut/icon retained.
Visual F22/F41 NN overlay and F150 ascent/descent checked, no console errors;
standalone Edge app opened and its dedicated profile/port verified.
Contained FootIKLab only; no Unreal/training or Bodyflip edits. Earlier84-check
validation was insufficient and is superseded. [Details](Labs/FootIKLab/README.md).

**Foot IK Lab October25 - separate terrain prototype:** created
`Labs/FootIKLab` and desktop **Foot IK Lab** shortcut, own port8878/state/profile.
Copied NN Walk/Run banks and renderer/leg helpers; no live Bodyflip dependencies.
Root follows a smooth stair ramp; foot IK queries discrete treads, estimates
stance from original gait height/speed, pins finite contacts, anticipates swing
clearance and adjusts pelvis against both legs. Cached banks omit NN pin outputs;
corrections stay outside recurrent NN state. Stripped UI retains single timeline,
brackets, speed/frame stepping, COM camera and Refresh state. Stairs up/down,
uneven/flat presets; compact More options under views.84 checks pass; maximum
default run-down target error1.01cm, sole clearance passes. Browser visual/input/
Refresh QA passed, no console errors. Server running8878; shortcut installed.
No Unreal/training operations or existing lab edits by this task; no commit/push.
[Controls, limits and verification](Labs/FootIKLab/README.md).

**Bodyflip October25 - anticipate pelvis reach during foot approach:** user
requested slowing the foot before it spends available extension, retaining
root-local motion. Foot cm/s is now a maximum. Each prepared step measures
remaining travel inside the selected reach sphere and estimates time until the
plant target is reachable using one frame of existing incoming body motion.
Travel is paced over that interval; no new option, gate or root/pelvis path edit.
Saved Phase.30/Load50/Foot400/Reach.99 markers F53/F95/F125 all now push; third
captures F137.25, versus previous Distance-growing abort F136.75. Approach max
hip-ankle79.01cm <80.63cm limit; no sampled sole penetration or bone-length error.
Pacing24, selection37, alignment36, bounce140 checks and syntax pass. Cached
three-jump preparation about120ms, no added playback integration/inference.
Tooltip and diagnostics explain/report pacing; control layout/settings retained.
Refresh required; visual QA unverified. No Unreal/training/server work or push.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - compare feet after cone constraint:** selection retains
ankle-to-planted-ankle metric, now against each foot's cone-constrained contact,
not its theoretical ideal. Original ideal distance retained for approach rotation
timing; no new gate, fallback or exception. Phase tooltip labels post-cone scores.
Frozen reported F146/Load50 pose picks R3.53cm versus L31.53cm (old ideal metric
picked L47.47cm versus R55.07cm). New rule also changes FIRST jump to grounded L,
capturing at F53 instead of later. Therefore saved F115/F146 now MISS after the
different first launch; markers/tuning deliberately unchanged. Do not claim all
three saved jumps still succeed or silently add an exception to keep old motion.
Selection37, alignment36, bounce140 and syntax pass. Small frozen incoming-pose
fixture preserves the reported regression independent of upstream flight changes.
Refresh required; visual QA unverified. No UI moves, saved-state changes, Unreal,
training or server work, commit or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - remove unrequested penetration rejection:** removed the
hardcoded signed-height cutoff from cone validity; no replacement depth threshold.
At saved F115 the right foot is34.3cm from its ideal versus left56.5cm, but its
lowest shoe corner is9.5mm inside the incline. The old5mm cutoff wrongly excluded
it. Jump2 now selects R/left incline and captures immediately at F115, followed
by LOAD/PUSH. Existing distance trigger, finite surfaces and reach retained.
All original three markers succeed. Selection34, bounce148, alignment47 and
contact40 checks pass; syntax checked. Prior tests that required R rejection
were validating the bug and have been corrected. Refresh required; no saved
state/tuning/marker/platform changes, UI additions, Unreal work or push.
Standing user instruction: implement requested behavior without inventing gates,
fallbacks or exceptions; ask about ambiguity and explain proposed changes first.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - centered gizmo / continuous contact alignment:** platform
gizmo and transform pivot now use slab center; orbit clears selection, including
an older selected slab. Scale axes remain local. Captured shoe bank continues
leveling through LOAD/PUSH, with moving sole pivots and the same ankle trajectory
in loading physics and IK. Retains captured pitch; existing heel/toe speed starts
at PUSH. Both ideal rings now shown (green selected/red other), smaller green
contact ring; phase tooltip gives selection-time distances/eligibility. Saved
jump3 selection was correct before edits (L50.1cm/R60.4cm), so selection rule kept.
Original three markers still push floor/left/right; jump3 bank dot normal goes
from0.731 to0 before release, no sole gap or bone-length error in sampled contact.
Alignment47, bounce148, selection23, platform101, contact40, skew105, arrow18
checks pass. Cached preparation about50-70ms; no new options/processes/inference.
Visual tools fail with kernel-assets os error3; refresh lab to load. Saved state,
markers/platforms/tuning untouched; no Unreal/training activity or push.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - jump2 surface/foot mismatch:** surface availability used
either foot's cone, then planner could choose the invalid other foot. Shared
candidates now choose an eligible foot by own-ideal distance per surface, then
rank surfaces by that foot's actual contact gap. Unreachable valid-cone slabs
excluded; explicit overrides retained. Saved F115 picks L/left incline23.0cm,
versus R/right29.4cm; all three ORIGINAL markers succeed. Earlier F114 retiming
advice is superseded. Selection23, bounce148, contact40 pass; syntax checked,
visual QA unavailable. Refresh required. No saved settings/platform/marker edits,
Unreal/training work, new process or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - loading/rebound prototype:** implemented kinematic pelvis
spring loading with incoming momentum+gravity, pinned foot, then finite-duration
drive and ballistic release. LOAD precedes PUSH; jump blend, roll and arrow wait
for extension. Two options appended after Translucency: Load ms100 (0 restores
old launch), Rebound50%. Geometry/energy/stiffness bounded; root path replaces
clip height, no double launch.148 focused checks; Load0 platform93/skew105/arrow18
and refresh14 pass. Cached three-jump preparation about42ms; visual QA unavailable.
Saved second marker F115 now misses; read-only F114 trial makes all three succeed.
Markers/settings/layout not overwritten. Refresh required. No Unreal/training,
new process, server restart or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - forward foot on inclines:** plant heading now comes from
anatomical pelvis forward, flattened then projected onto the surface; imported
jump root +Z was lateral. Pitch/roll retained with corrected roll axis. Saved
frame151/jump3 capture heading error2.28deg; heading58, target71, contact39,
schedule136, cone88, skew105 pass. Visual QA unavailable. Refresh required;
no tuning/marker/platform reset or Unreal/training work. Bounce remains a proposal:
spring/damper pelvis loading under incoming momentum+gravity, then extension,
bounded compression/rebound; no bounce implementation yet.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - inclined alpha / knee / frame diagnostics:** alpha uses
incoming root velocity projected onto the selected surface, scaled by1/200;
root-local carry and finite bounds retained. Red circle shows the other foot's
ideal; green remains actual selected contact. Knee bend pole follows pelvis/aim,
thigh and calf share a hinge plane. F counter beside seconds is zero-based60Hz,
updated before HUD throttling. Saved frame149 reproduced; corrected jump3 selects
R60.7cm versus L63.9cm (previous L73.8/R77.6). No marker/tuning reset. Target71,
contact39, schedule136, skew105, cone88, platform93, arrow18, refresh14 pass.
Cached data only; live browser visual QA unavailable. Refresh required. No Unreal,
training or server activity. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - platform side translucency:** More options ends with
Translucency %, default80; sides/undersides blend, local walkable tops stay
opaque from the front. Top backs/grid omitted when viewed from underneath.
Sorted transparent pass retains depth testing, disables depth writes, restores
render state. Appearance-only edit, persists without replan/pause.25 focused
checks plus platform93 and syntax pass; live GPU visual QA unavailable.
Refresh to load. No physics/layout/tuning reset or Unreal/training changes.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - Refresh playback / alpha step:** app Refresh saves time,
playing state, attack time, runtime angles and hit readout before pausing; boot
restores after flight setup. Authored angles stay separate to prevent double air
rotation. Queued previews/delayed saves cancelled before reload; trim/speed/camera
preserved. Alpha native numeric step now1 (fractions still typeable). 14 focused
checks and syntax pass; visual QA unavailable. First reload loads this feature;
older running code cannot snapshot its unsaved playhead. No live-state overwrite,
Unreal/training/server action or push. [Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - sole orientation / second-push momentum:** foot and toe
frames use anatomical rig signs, replacing world-Y flips. Query geometry and
rendered boxes agree; inverted nearby capture aligns sole-first. Saved third
contact foot-only regression changes from inverted up dot normal=-0.959 to
+0.861. Incoming velocity now retains only motion tangent to BOTH physical
surface and skewed push axis, superseding the earlier push-axis-only rule.
Jump2's carried surface-normal component is zero. Corrected trajectory makes
the existing third marker miss (Distance growing); timings preserved. Contact37,
motion105, schedule136, platform93 and arrow18 checks pass. Cached NN data only,
visual QA unavailable. Refresh required; no saved-state reset or Unreal/training.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - trim preview return:** bracket drags retain their live
boundary preview, then restore the pre-drag playhead on release/cancel/lost
capture. New trim bounds remain; pending preview callbacks cannot override the
return. Seven handler checks and syntax pass. Refresh lab; no saved-state reset.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - Up skew COM trajectory fix:** retained incoming velocity
now uses the effective skewed push axis, not the physical surface normal. Old
slope projection converted downward arrival into sideways drift even at100%.
100% now matches flat-ground root/pelvis motion for identical incoming velocity
and clip, retaining horizontal momentum;0% is unchanged. Physical contacts/IK
still use the actual surface. Measured45-degree-slope drift0.20m over0.1s removed.
102 trajectory checks, arrow18 and platform93 pass; live visual QA unavailable.
Refresh required. No tuning/layout reset, inference, Unreal/training or push.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - Show jump:** checkbox appended after Cone, persisted and
off by default. Large yellow1.4m arrow starts at support contact and follows
actual authored push direction including Up skew. Visible for3 frames at60Hz
from push onset, determined by playback time for pause/seek/loop consistency.
Misses draw nothing. Reused overlay mesh, no timers or replans. 18 focused checks
and syntax pass; browser visual QA unavailable. Refresh and enable Show jump.
No Unreal/training/server activity or saved layout reset.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - immediate platform gizmo:** user clarified the complaint
was elapsed click-to-gizmo time, not drag distance. Gizmo now previews on mouse
press without waiting for release or pausing playback. A completed click pauses;
orbit/cancel/lost capture restores the previous selection. Original4 CSS-pixel
jitter threshold restored, undoing the mistaken4-to1 change. No Alt required;
gizmo transforms unchanged. 93 focused checks plus syntax pass; live visual QA
unavailable. Refresh lab. No saved layout/tuning reset, Unreal or training activity.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - distinguish gizmos:** W Move now has large arrowheads
and a round center; R Scale has outlined square endpoints and a square center.
Colors/orientation/interaction unchanged. Syntax and82 checks pass; visual QA
still unavailable. Refresh lab for appearance update. Lab-only, no state reset.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - W gizmo keyboard fix:** platform W/E/R and Ctrl+Z now
use printed letters, fixing physical W/Z mapping on AZERTY. Viewport/gizmo
pointerdown transfers focus to canvas, leaving dropdowns and committing numeric
edits. Writable controls retain editing shortcuts. R gizmo remains local;
W/E remain world. 82 focused checks pass, including visible Move handle output
and focus routing; browser visual QA unavailable. Refresh required; no saved
layout/tuning change, Unreal/training work or push.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - platform reset / Ctrl+Z:** user-requested saved layout
reset to original floor and both45-degree ramps; all other state preserved by
/state readback. Backup: Saved/BodyflipLab/platforms-before-reset-20261025.json.
Startup reset version prevents an older tab's Refresh save from restoring the
old layout; subsequent edits persist. Ctrl+Z undoes one completed transform,
up to100 in-session operations; cancels active drag, ignores no-op drags, retains
text-field undo and playhead. Add/delete are outside transform history. 72 focused
checks and syntax pass; browser visual QA still unavailable. Refresh lab once.
Contained lab-only changes; no Unreal/training/server restart or push.
[Details](Labs/BodyflipLab/README.md).

**Bodyflip October25 - platform editor / upward push skew:** + Platform below
phase at viewport top left; click a slab for gizmo. W move, E rotate, R scale;
Delete/Backspace remove, Escape cancels/deselects. Text editing retains its keys.
Gizmo pivots at clicked point to stay accessible on long ramps. Alt-left-drag
orbits over geometry. Preview during drag, single replan/save at release with
playhead retained. Layouts persist, including empty scenes. Wheel dezoom cap
removed and clipping expands with distance. More options ends with Up skew %,
default50: authored wall push45 degrees toward up; incoming tangent retained.
50 focused platform/wall/zoom checks plus136 legacy-skew schedule and19 marker
checks pass. UI runtime still fails initialization, so visual QA unverified.
No live-state overwrite or Unreal/training activity. [Details](Labs/BodyflipLab/README.md).


**Bodyflip camera October25:** horizontal left-drag orbit now uses yaw -= dx;
inverted vertical remains pitch -= dy. Horizontal previously retained its
original sign. Only the lab orbit mapping changed; saved camera/pan/target drag
untouched. Syntax checked.

**Bodyflip October25 - ramps and manual jump markers:** two finite45-degree
ramps form a V beyond the ledge. Support cones, sole clearance/roll, rendering
and Jolt share oriented surfaces. Repeated scheduled pushes continue incoming
motion; missed contacts add no lift. User confirmed markers start SUPPORT,
then contact starts PUSH. UI correction: markers are on the EXISTING playback
bar, with + Jump beside Loop at the START of the timeline (same-sized mouse
target as transport buttons). User rejected the far-right placement: keep
related actions near their working area. Select a marker for time/Delete;
no second timeline, After or Gap controls. Preserve this minimal UI.
136 geometry/motion and19 control checks pass, including three successive
pushes; previous cone88/blend33/abort36 checks pass. Browser layout remains
unverified because both UI runtimes failed at initialization. Tuning/camera
preserved, no Unreal/training/server action or push. Details/receipts:
[Labs/BodyflipLab/README.md](Labs/BodyflipLab/README.md).


**Standing UI placement rule (October25):** preserve existing control positions
and order. New options go at the bottom; in horizontal rows they go on the right.
Do not shuffle existing controls to group new features. Bodyflip Cone angle was
moved to the end of More options, and Cone debug after Bones; source order checked.
User then requested moving the entire More options panel under the view buttons
at viewport top right. Done as a collapsed dropdown, with internal order retained,
bounded scrolling and Space-mode hiding; source structure/syntax checked.

## October 25 - intermediate backup cleanup and latest resume

User explicitly authorized deleting intermediates and resuming (supersedes
conditional storage-only cleanup). Latest checkpoint0203311 /6,282,149,888 samples
was SHA/ZIP checked locally and independently read back from S3. Updated the
run's latest_verified.json to this verified newest checkpoint BEFORE deleting49
older numbered checkpoints from that exact run prefix; freed2,397,767,986bytes.
Latest checkpoint, source, previous-run final/initialization and unrelated runs
remain. Old pod-volume copies cannot be reached; do not claim those were removed.

Original L4 w754z82j94t55a restart again rejected for host GPU availability;
retained pod remains EXITED, state archived under storage-resume-20261025/retained-pod.
Replacement L4 ghd13y3edq7ruw at$0.59/hour uses a fresh20GB volume and restored
verified runtime/source. New run20261025_165654_uefn_locomotion_idle_prior_2048,
trainer465/failure guard466,2048worlds, until stopped. Same sourcef83f9855bce3,
settings/30+30 repeated-push prior/COM2/no-extra-early-MSE unchanged.
Verified iteration203322 /6,282,870,784samples, recent2.707s/update. Both optimizer
and normalization restored. New checkpoint0203312 persistently verified;
all production dispatch counts8/8/16/16 retained. TensorBoard8035 serves fresh
16-56-54 points, replayer8021 serves20rows at203312. Setup guard released after
verification; trainer failure/billing guard remains active. Receipts: Saved/MimicKitLocomotion/storage-resume-20261025.

## October 25 - stop-cause investigation blocked by retained-host capacity

Read-only provider check: pod still EXITED; balance about$7.49, so account is
not currently empty. Generic provider stop reason does not identify the original
cause. No locally received failure/backup-error or uploaded exit-evidence archive.
Latest203311 checkpoint revalidated locally (SHA/ZIP) and persistent readback
was already verified. User authorizes removing intermediate checkpoints IF storage
caused the stop. Do not infer that condition from the gap in telemetry alone.
Bounded diagnostic start of the same pod was rejected for no free host GPU;
explicit GraphQL gpuCount0 also rejected with the same capacity error. Diagnostic
guards cancelled; no new pod or training launch, no checkpoint deletion.
Remote disk/log inspection remains unavailable. Evidence directory:
Saved/MimicKitLocomotion/storage-audit-20261025.

## October 25 - viewers recovered; GPU already stopped

Provider confirms locomotion pod w754z82j94t55a EXITED at14:33:44UTC /15:33:44
Warsaw. Provider reason is generic "Exited by user"; precise cause not established.
Do not mistake the last local status.json (training) for live status. No GPU
restart performed for the viewer-only request. Stopped the disconnected local
bridge and removed its stale training.active marker; other observers preserved.
TensorBoard8035 already served the last real training points through6,282,149,888
samples at15:33:22Warsaw. Actual replayer8021 is healthy. Recovered the newer
203311 capture (20rows) from S3 checkpoint0203311 and verified through its HTTP API.
The separate impulse viewer8850 is unrelated and remains stopped.
Checkpoint0203311 downloaded locally, full ZIP CRC and independent S3 readback
verified SHA8e993cd93b44629919e1be62a06aadf8045c3752206bcec4558b55ef8c568d91;
it was uploaded just before pod exit, newer than the remote latest_verified
manifest203211. No invented scalar history. Receipt and preserved-checkpoint path:
Saved/MimicKitLocomotion/viewer-recovery-20261025.json.

## October 25 - pushed-idle prior handoff resumed

User approved restarting the 30-tick full-prior + 30-tick linear MSE fade
on EVERY P-minus idle push. Before its first push P-minus remains full MSE.
P/P+ retain their episode-start 30/30 handoff. All handoffs now have
`ae_mse_weight=0`: remove only the additional calibrated early tracking MSE;
ordinary MSE returns through the fade. COM2 remains active throughout at
56.41750205477203. Cohorts, termination, optimizer, physics and other losses
are unchanged; the source retains every production dispatch optimization.

Cleanly stopped 20261025_020410_uefn_locomotion_dispatch_2048 at5,960,957,952
samples. Latest checkpoint0198410_final.zip is verified locally and by S3
readback, SHA bd3a0af93206b6ffbb9d21438938b52d5a6218dc2cabfe54df1ea021467526fd.
Local: Saved/MimicKitLocomotion/preserved-latest/
20261025_020410_uefn_locomotion_dispatch_2048/checkpoint_0198410_final.zip.
New run20261025_113940_uefn_locomotion_idle_prior_2048, trainer10777/guard10778,
same L4 w754z82j94t55a,2048 worlds,$0.59/hour until stopped. Verified advancing
at iteration198431 /5,962,334,208 samples; recent updates about2.7s. Both optimizers
and observation normalization restored. New checkpoint0198411 is persistently
verified (SHA32fa5edd4cb0cac1e621802bd89b8ebe2dd8cd5de39042671d5db286ad89e692).
Replay P-minus rows advertise the repeated-push prior timing; TensorBoard8035
has fresh motion_prior and com2_velocity points under11-39-40. Handoff guard
released after verification; normal failure/billing guard remains active.

Candidate source f83f9855bce340e4ce33a8c71103c3d61491316fce5f71ac017069a889b67d72
and receipts: Saved/MimicKitLocomotion/idle-prior-handoff-20261025.
Actual reward-method CPU checks18cases passed; GPU repeated-push checks10cases
match eager/captured rewards exactly after lazy engine state is materialized.
Shared recovery environment files were deliberately preserved; edited production
files live in the pinned source/candidate. Reproduce via
Labs/MimicKitTraining/resume_idle_prior_20261025.py and prior_handoff.py.

## October 25 - local TensorBoard writer restored after disk full

The download bridge stayed alive, but the dashboard event writer exited with
ENOSPC and the COM2 chart stalled for about 12 minutes. Freed 3,154,976,492 bytes
by removing 97 old local rollout_step JSON snapshots only from the October23
000133 locomotion run; kept its newest three, all checkpoints and scalar files.
Restarted the current 020410 dashboard writer. Bridge re-downloaded the event
file, and TensorBoard8035 now has 959 COM2 points through 5,717,753,856 samples,
including the missing 25 points (latest about40s old at verification). Remote
training continued unchanged, no errors. Receipt:
Saved/MimicKitLocomotion/tb-writer-recovered-20261025.json.


## October 25 - proposed hardware comparison cancelled by user

User said "forget about it" after the overnight recap. The proposed RTX4090
comparison is cancelled; do not allocate it or treat the older pending approval
question as active. Main training remains unchanged and running on L4
w754z82j94t55a at $0.59/hour, 2048 worlds. Verified iteration194529 /
5,706,612,736 samples; 2.5781s recent update mean, no errors. Persistent
checkpoint0194519 verified SHA
aa65de60a7537d7b22957628d302b14f6d9b24814b9e0909c6e21d19221830d5.
No clean cumulative speedup or net dollar-savings measurement exists; do not
present individual probe improvements as a measured total.


## October 25 - isolated hardware comparison prepared; budget approval pending

Production remains 20261025_020410_uefn_locomotion_dispatch_2048, L4 w754z82j94t55a,
trainer8043/guard8044. Verified iteration186059 /
5,151,522,816 samples after the baseline; both processes alive,
no error or remaining benchmark process. COM2 stays56.41750205477203.
Persistent checkpoint0186019 SHA
e528b5c738de86b111740f8db32bea85253c7bbe22161199951acf0a13737cf2 verified.

One same-checkpoint L4 hardware baseline completed:8 warm complete PPO updates,
mean2.533971850s, median2.537114984s.
All current8/8/16/16 dispatches, Newton convergence, highestFP32/TF32off,2048
worlds and optimizer/normalizer state retained. Isolated timing pause20.697s
resumed normally under an independent60s guard. Includes simulation/resets/
rewards/actor/critic; periodic evaluation and backup excluded. This is a hardware
comparison baseline, not a cumulative improvement or learning-quality claim.
Frozen checkpoint185919 SHA3902ddf8094b1a61259e0eadeb0e9673fa8eb52cccd21c3c87affc0990eb2a5d
is preserved/readback-verified under the hardware-trial S3 prefix. Source remains
450a177a000a6ed5d8a4523cfac3fcd3a422e57e861e5d55f6c205bb272221a5.

Prepared one RTX4090 comparison, <=$0.89/hour and20minutes including setup
(<= $0.30 GPU charge), keeping main training running. Actual account price
verified0.89 withHighstock; availability is not an allocation guarantee.
Existing0.59/hour ceiling requires explicit approval. Async question sent;
NO approval, allocation, migration or paid trial yet. Never interpret silence
or the older COM2 "go" as this approval. Controller requires human-approval.json;
do not create it until the user explicitly agrees to this specific test.

Helpers hardware_trial_20261025.py and benchmark_hardware_20261025.py; artifacts
Saved/MimicKitLocomotion/perf-lossless-20261024/hardware-options/rtx4090-trial.
Review.txt contains concrete plan/price/spec sources; plan.json pins checkpoint,
source, seed and settings. Local ownership/approval/budget checks passed.
Separate trial state forbids main/recovery IDs; absolute local billing guard,
remote guard and completion/failure evidence-upload+stop are prepared. Trial
collects from persistent storage after billing stops. No automatic migration.
At current rates throughput must exceed1.5085x to improve GPU cost/sample.
Optimization goal marked BLOCKED after the same missing budget approval
persisted across three consecutive goal turns.10x remains unproven.
The main run is NOT blocked or stopped: providerRUNNING at0.59/hour,
trainer8043/guard8044 alive, iteration186199 /5,160,697,856 samples,
COM2=56.41750205477203, no error or probe. Latest persistent backup0186119
SHA5d1bacf5d543e30baa59f1ddbf4112dcde6aadb8b1da49af9d1e28601a195167.
4090 price rechecked0.89/hour. No approval receipt, allocation attempt or
trial pod exists. Await the existing explicit20-minute/0.30GPU-cost request.
Receipt: hardware-options/rtx4090-trial/blocked-audit.json.


Periodic-work audit completed without pausing/restarting training or allocating
compute. Recent clean10-update log windows average2.671065s/update. Latest
evaluation16.558959s and local checkpoint creation0.616106s occur every100
updates; estimated periodic fraction6.04%. Even eliminating these entirely
would yield only1.0643x throughput, not a large gain. Upload/readback runs in
an existing background worker. Preserve evaluation/replay and verified backups.
Evidence: perf-lossless-20261024/periodic-overhead/{cycle-evidence,analysis}.json.
The upstream Samples_Per_Second metric divides lifetime resumed samples by
this run's elapsed time and is invalid after resume (currently~1.60million/s).
Use delta samples/delta wall time: clean windows24.3-24.7k/s, including ordinary
per-update logging/health overhead. Hardware benchmark2.534s excludes periodic
work and is not itself full-production throughput. Do not claim a cumulative
speedup from different checkpoints or this erroneous upstream metric.
The RTX4090 approval remains pending; no allocation or code deployment.



## October 25 - COM2 x10 confirmed active; zero-product probe rejected

The requested COM2 multiplication is already deployed: 5.641750205477203 ->
56.41750205477203. Do not multiply it again. Current run remains
20261025_020410_uefn_locomotion_dispatch_2048 on L4 w754z82j94t55a,
trainer 8043 / guard 8044, 2048 agents, until stopped at <=$0.59/hour.
Live check: iteration 185899, 5,141,037,056 samples; both processes alive,
no failure/backup error and no probe running. Verified persistent checkpoint
0185819 SHA 9b599a6e1651d5c7b7ddedf2dd2520b503973a099c8f81e34edbd15bd1ed7847.
TensorBoard8035 serves loss/com2_velocity for 02-04-10, through 5,140,381,696
samples at verification. No restart or additional coefficient multiplication
was needed for the latest confirmation. Receipt: com2-x10/current-status-confirmation.json.

The all-zero quadratic-product fast path is now ruled out: ten edge cases pass,
2,472,397,056 live values match exactly, and 36.55% of tiles skip the product,
but complete updates average 2.588874s versus 2.570774s current (0.7% slower).
Rejected; no production change. All 8/8/16/16 graph dispatch counts retained;
the guarded timing pause resumed successfully. Receipt: perf-lossless-20261024/
zero-quadratic-tiles/complete.json. Supersedes the earlier suggestion to test it.
No hardware trial allocated or approved; read-only price inventory is evidence only.


## October 25 - further solver-cache and compiler audit; training unchanged

Production remains20261025_020410_uefn_locomotion_dispatch_2048, trainer8043 /
guard8044, L4w754z82j94t55a,2048 worlds, COM2=56.41750205477203, until stopped.
Verified185609 /5,122,031,616 samples. Latest persistent checkpoint0185519 SHA
2ac6c40f82bb309b953437dfe503169cd1178949e5dedfa0737c720ce85f4238.
Both production processes are alive; no failure/backup error or probe remains.
Source450a177a remains deployed; no production or physics/learning change this round.

A within-solve quadratic-Hessian cache reused47% of active matrices and matched
4,934,361,600 values exactly. Complete-update ABBA2.569626s current versus2.855392s
cache:11.1% slower, rejected. Fused tile reuse with coalesced state checks matched
2,457,234,432 values exactly across eight distinct solver contexts, but was also
slower:2.566487s current versus2.645301s (3.1%). Rejected, not deployed.
An earlier fused probe retained only3 contexts because temporary output memory
could be recycled. Its timings/parity are INVALID; v2 retains every H buffer and
asserts8 distinct contexts before measuring. Retain this regression guard.
All valid graph variants preserved existing velocity8/derivative8/factor16/cached48=16.
Timing pauses had independent60s resume guards; production resumed successfully.
Receipts: perf-lossless-20261024/cached-base-hessian, cached-tiled-hessian (invalid),
cached-tiled-hessian-v2; live check cache-compiler-live-after.json.

Generic torch.compile/Inductor at highest FP32 (TF32 disabled, no autotune/padding)
changed checkpoint feature-network results on synthetic inputs. Actor-gradient
relative L2 deviations reached6.87e-4; critic features relative L2=2.89e-7. This is
not proof of a learning-quality regression, but does not establish lossless updates;
no full-PPO speed/quality claim or deployment. The bounded probe did not pause
production. Evidence: perf-lossless-20261024/compiled-network. Compiler behavior
reference: https://pytorch.org/blog/training-production-ai-models/ (section3.1).

Goal remains ACTIVE;10x is unproven. Do not repeat the rejected cache variants or
promote compiled arithmetic as lossless without stronger evidence. A distinct
remaining idea is a native all-zero quadratic-tile fast path, with unchanged
FP32/finite/nonfinite semantics and equations; inspect its value before any probe.

## October 25 02:04 Warsaw - cached Cholesky optimization RUNNING

Run20261025_020410_uefn_locomotion_dispatch_2048 is verified on the same L4
w754z82j94t55a, trainer8043/failure guard8044. Handoff watchdog7921 has exited
after verification.2048 agents, until stopped, <=$0.59/hour; COM2 coefficient
stays56.41750205477203. Verified185149 /5,091,885,056 samples, recent mean
2.56160s/update (~25,584 transitions/s). This live rate is observational; the
controlled comparison below is the speed evidence. No probe remains.

New checkpoint0185119 has verified persistent backup, SHA
d32a449ee0c4a908902284f2f2cc8ce213583f790e2239b5b2e175f06ad04fe0.
Local replay parses with20 rows; TensorBoard8035 serves loss/com2_velocity
under the02-04-10 run. Old bridge finished sync; old dashboard26844 was stopped.

Old run20261025_005749_uefn_locomotion_dispatch_2048 stopped cleanly at
5,089,853,440 samples, iteration185119. Final checkpoint0185118_final is safe
locally and in verified persistent storage, SHA
b6b5aa90986430781e3050b87338510dc7675dfe477494b4761a2573d506889b.
Local: Saved/MimicKitLocomotion/preserved-latest/
20261025_005749_uefn_locomotion_dispatch_2048/checkpoint_0185118_final.zip.

Change retains all native48 padded rows and16-column block arithmetic, keeping
tiles resident between uses.77,112,816 live output values matched exactly.
Controlled complete updates2.630825 ->2.572510s, about2.27% throughput gain;
all three ABBA blocks improved. No cumulative percentage or10x claim.
Source450a177a000a6ed5d8a4523cfac3fcd3a422e57e861e5d55f6c205bb272221a5
is locally/persistently verified. Only lossless_runtime.py changed; added
cholesky_cached48_runtime.py. All configurations/assets remain byte-identical.
Packaged preflight passed27 reward comparisons,2 optimizer/weight comparisons,
9 nonfinite motor checks,3 training updates and160 evaluation ticks.
Existing dispatches remain velocity8/derivative8/factor16; cached Cholesky16.

Edge40 was about30% faster in isolation but failed full-solve force/acceleration
fidelity; excluded. Full reference caching changed quaternion rounding by
5.96e-8 and failed exact target parity; excluded. All evidence and source are
under perf-lossless-20261024/cached48-deployment, cached48-full, edge-full and
reference-cache. Do not deploy discarded candidates.

The corrected contact-launch geometry screen is now complete. All five variants
retained velocity8/derivative8/factor16/cached48=16/contact16. Current complete
updates averaged2.584663s; best (grid24/block256)2.566270s, only about0.7% faster
in this short screen, below the1.5% progression gate. No candidate deployed;
no repeat timing or extra GPU. Probe8270 exited; its one31.35s timing pause
resumed normally under an independent60s resume guard. Evidence:
perf-lossless-20261024/contact-launch-corrected. Older invalid timings superseded.

After this screen trainer8043/guard8044 are alive and training advanced to185289 /
5,101,060,096 samples. Latest verified backup0185219 SHA
752861035cf2d5da6ab4353817ed22ee8f7cdbe9adcd6f33400faad09bb228c5.
COM2 remains56.41750205477203; local TB8035 has its current02-04-10 card.
No failure or backup error. Recent rolling speed includes probe contention/pause
and is not an uncontended performance result. No probe remains.

Future graph probes must retain every installed context. Use
 dispatch_probe_common.build_variant_graph and its8/8/16/16 checks. Do not repeat
tested candidates without new evidence. Goal remains ACTIVE;10x not achieved.

## October 25 - corrected comparison complete; production unchanged

Current run20261025_005749_uefn_locomotion_dispatch_2048 remains RUNNING on
L4 w754z82j94t55a, trainer4265/guard4266. COM2 coefficient56.41750205477203
is the requested x10; it was not multiplied again. Verified184717 /
5,063,573,504 samples. Latest checkpoint0184717 persistent readback verified,
SHA54df171f58c724253092e5e4fbaffa9a518764a95f6c4fbc3038532df7993b5b.
Local TensorBoard8035 serves the current run's loss/com2_velocity card.

The corrected shared-environment comparison retained velocity8/derivative8/
factor16 dispatches in every candidate, with explicit source-identity checks.
Complete-update screen: current2.59709s, deferred FK2.59212s, cached cone2.60551s,
static cone2.48681s. Deferred FK and cached cone show no material gain. Static
cone is about4.44% faster in this small screen, but fails full-solve fidelity:
qacc max relative0.01015 vs0.000208 native repeat; constraint-force0.01524 vs
0.000827; iteration mismatches166 vs18 across49,152 world states. Rejected.
No candidate deployed; original physics, precision and training math remain.

Probe6549 ended normally. The one31.19s timing pause resumed via finally with
an independent60s resume guard. No probe remains; no new GPU. Rolling live speed
immediately afterward includes probe contention/pause and is not steady throughput.
First corrected attempt6250 exited at the capture-count gate before timing,
because an old pipeline probe shadowed the uploaded file; isolated imports fixed
this. Receipts: perf-lossless-20261024/composition-corrected-v2.
The Cholesky-edge prototype is still unvalidated and is not in production.
Speed goal remains active; no10x gain has been established.

## October 25 00:57 Warsaw - dispatch optimization RUNNING

Post-deployment audit: current run advanced to184187 /5,028,839,424 samples;
trainer4265 and guard4266 alive, no probe or failure remains. Latest verified
persistent checkpoint0184117 SHA9f385122696904ec921ec659b0aaea281484f0ee5aad01de7f5a1125e4ffd1bc.
COM2 remains56.41750205477203 and its local TB card is present.
Fresh profile: physics57.2%, actor+critic27.8%, resets7.0%; nested timings are
attribution, not a promise of attainable speedup. Isolated normal updates2.53-2.62s.
A candidate omitting six unread intermediate FK passes matched31,948,800 body
transform/velocity values, including TRAIN/TEST transitions, but full-update ABBA
was2.60604s current versus2.61291s candidate. Rejected; production unchanged.
Two timing windows used independent60s resume guards; both resumed normally.
The live rolling throughput immediately after probes includes contention/pause
and must not be compared with uncontended speed. Evidence: perf-lossless-20261024/
dispatch-baseline and deferred-fk. Speed goal remains active; no10x claim.

Run20261025_005749_uefn_locomotion_dispatch_2048 is verified on the same L4
w754z82j94t55a, trainer4265, failure/billing guard4266. Handoff watchdog4129
was released after advancing updates, persistent backup and replay/TB verification.
2048 worlds, until stopped, <=$0.59/hour. COM2 stays56.41750205477203 (x10).

Verified183957 /5,013,766,144 samples. New checkpoint0183917 SHA
368d00adb6a565ae474de07cfed69c3ed45058571b51c53649fb587fc81ae0fc
has verified persistent backup. Local replay parses with20 rows and correct run;
local TensorBoard8035 serves loss/com2_velocity under the00-57-49 run. No probe
process remains. Uncontended recent30-update mean2.61191s,25091 transitions/s.
This live number is observational; the controlled Newton comparison is below.

Previous run20261024_235427_uefn_locomotion_dispatch_2048 stopped cleanly at
5,011,079,168 samples, iteration183917. Final checkpoint0183916_final is
preserved locally and through verified persistent S3 readback, SHA
bc3b9e9eead781f0847e879b106c773cd54ac4e7732d8206fbc29980a290ea94.
Local: Saved/MimicKitLocomotion/preserved-latest/
20261024_235427_uefn_locomotion_dispatch_2048/checkpoint_0183916_final.zip.

Source96e22df97e00225bb35c553f813640329dc621e528ed19973b5a734a70befa94
is locally and persistently verified. Plan: Saved/MimicKitLocomotion/
perf-lossless-20261024/converged-deployment/prepared.json.
Only lossless_runtime.py changed; three runtime modules were added. All prepared
configuration bytes, training/physics settings, losses, sampling, Adam/KL and
FP32 precision are unchanged. Source is assembled from the pinned production
archive; unrelated shared-tree modifications were not deployed.

Newton now performs the original cost/gradient convergence test before building
a search direction that would never be used for a converged world. No tolerance,
iteration cap or contact setting changed. Across65,536 live world states, errors
matched native repeat variation; active constraint states matched. Controlled
full updates2.73958 ->2.63245s (about4.1% throughput gain). TRAIN reference/done
CUDA graphs were also included after exact parity at boundary ticks; separately
their combined timing2.72499 ->2.70089s was a small0.9% difference. Do not add
these percentages; a precise combined A/B percentage has not been measured.

Packaged preflight passed27 reward checks, exact actor/critic weights+Adam
checks, nine nonfinite motor checks, three training updates and160 evaluation
ticks including TRAIN/TEST transitions. New deployment retains existing sparse
motor/factor/reward/kick optimizations. New GPUs: none.

Rejected this round: cached cone coefficients (exact2.57billion contributions,
but0.7% slower); actor/critic overlap (exact losses, weights, Adam, RNG and sample
order, but no speed gain). Earlier rejected direct solves, blocked64 and selective
minibatches remain excluded. GPU is at its default/max72W limit without thermal
throttling; clocks unchanged. The speed audit goal is ACTIVE; no10x result.
Receipts are under perf-lossless-20261024: early-done-full-complete.json,
next-runtime-preflight-complete.json, next-package-diff.json, progress.json.

## October 24 - dispatch restart configuration gate fix

The first dispatch launch (20261024_234318_uefn_locomotion_dispatch_2048)
exited before training because the checkpoint compatibility gate rejected the new
lossless_dispatch config flag. The failure guard stopped pod w754z82j94t55a at
21:44:52 UTC; API confirmed EXITED. Latest checkpoint 0182844_final remains safe
locally and in verified persistent storage; no trained state was lost.

The isolated candidate train.py now permits that explicit dispatch flag while
keeping the existing objective/physics config checks. The actual resume-check
AST passes with this checkpoint and still rejects a changed episode length.
Updated source upload/readback and guarded restart on the same L4 are in progress.
Do not treat the earlier launch receipt as proof that training is running.


## October 24 - lossless dispatch handoff IN PROGRESS

Old locomotion run 20261024_214841_uefn_locomotion_com2x10_2048 stopped cleanly.
Latest checkpoint0182844_final, 4,940,824,576 samples, is locally preserved under
Saved/MimicKitLocomotion/preserved-latest/20261024_214841_uefn_locomotion_com2x10_2048.
SHA94f16e52aa35158875b15c4d1d7a64714c130ecdfdecac9e8a0e6375d270583b,
ZIP checked and persistent S3 readback verified. Existing L4 w754z82j94t55a only.
Remote handoff watchdog6070 stops billing if launch is not verified within10min.

Candidate source SHA813432a21c3e8864b082bfb3e065b2c2874552d47b4b4549039c57f4563ad5a4.
Saved/MimicKitLocomotion/perf-lossless-20261024/prepared.json is the prepared plan;
source-stored.zip is isolated from unrelated shared runtime changes. Source and
persistent readback verified. Helpers prepare_lossless_dispatch_20261024.py and
resume_lossless_dispatch_20261024.py; the latter reuses the existing guarded handoff.

Sparse motor work matched exactly on307,200 live-policy physics states. Fused LDL
uses identical sparse update schedule/FP32 math; atomic reduction ordering retains
native numerical nondeterminism. Matrix differences match native repeat variation;
full trajectories are NOT bitwise deterministic. Graph reward buffers matched
exactly at nine timeline points through TRAIN/TEST/TRAIN. Nonfinite motor velocity
classification verified. Staged training and evaluation smoke checks passed.

Controlled combined timing2.86168 ->2.70603sec/update (~1.0575x), not10x.
PPO graph experiment had exact loss/weights/Adam but <1% overall gain; lazy capture
had a stream-order failure in isolated preflight. PPO graphs were excluded from
this deployment and preflight rerun successfully. Adam/KL remain unchanged.
CuBLASLt FP32 alternatives were slower for training and were excluded. Candidate
contains sparse motor kernels, fused sparse factor dispatch, device-only alignment,
empty get-up no-ops removed, train-only reward graph, kick Jacobian/backsolve graph.
Physics240Hz, policy30Hz, solver convergence, FP32 precision, all losses/sampling,
2048 worlds and COM2 coefficient56.41750205477203 remain unchanged.

User optimization goal remains active. Verify new launch, advancing updates,
checkpoint backups, replay and TensorBoard before releasing handoff guard. Do not
claim measured live improvement until verified. No other GPU or experiment active.


## October 24 - lossless locomotion performance audit IN PROGRESS

Production remains 20261024_214841_uefn_locomotion_com2x10_2048 on L4
w754z82j94t55a, trainer2180, 2048 worlds, COM2 coefficient56.41750205477203.
No optimization or physics/learning change deployed. User's speed-optimization
goal remains active. Current source is still com2-x10/source-stored.zip.
Latest post-probe verification182183 /4,897,505,280samples; backup182163 verified,
SHA472d0b938e9a6553ca28e47ea78a3688feccf575bf76f79979f0191245a25c51.

Isolated probes shared the same GPU sequentially; no GPU allocation. They are
all finished. One controlled comparison paused only trainer2180 for22.73seconds,
with an independent60second SIGCONT guard; trainer resumed and advanced. Recent
smoothed throughput includes probe contention/pause, so is not steady speed.

Profile: physics roughly half update; PPO and reset/reward work make up the rest.
CPU copy timings include waiting for asynchronous physics, not pure copy cost.
Device-only alignment matched bitwise but noisy overall A/B gain inconclusive.
Reward graph + removing empty get-up work passed bitwise checks on every loss,
reward/target, diagnostic and AE-history buffer at ticks1,29,30,31,45,60,80,130,150.
Reward-only mean3.105ms ->1.578ms. Kick Jacobian/ten-backsolve graph mean3.615ms
->2.133ms; Jacobian exact, inverse deviations <=3.10e-6 (same unmodified-call
atomic variation), resulting requested-body velocity difference <=2.49e-6m/s.
Mass preparation stays outside this graph to preserve the original path.

Controlled full-update ABBA (four samples each): original2.82050s, both candidates
2.77458s, apparent1.01655x throughput. Small preliminary difference, not a robust
large speedup; graphs remain experimental. No claim of2x or10x overall speed.
205 enabled collision pairs; conservative all-pair bound exceeds current contact
and constraint capacity. Buffer reduction not justified without stronger proof.
Prior precision/dense-layout experiments are in dated journal: altered gradients
or no speed/learning benefit, so do not repeat or promote as lossless casually.

Evidence Saved/MimicKitLocomotion/perf-lossless-20261024; progress.json,
controlled-dispatch-complete.json, live-after-probes.json, reward-graph-complete.json,
kick-graph-complete.json, profile_0.json and python_calls.txt. Scripts
Labs/MimicKitTraining/probe_{reward_graph,kick_graph,dispatch_pair}_20261024.py.
Remaining: investigate larger structural costs and validate any meaningful gain
before guarded latest-checkpoint deployment. No background probe is pending.


## October 24 - Bodyflip curated Git checkpoint

User requested pushing the lab. Checkpoint includes Bodyflip code, Jolt runtime,
attack/jump recordings, exact phase banks, verification scripts/receipts and
saved-profile.json (tuning/camera snapshot). Live state, local model copies,
temporary exports and full captures remain local. Only Bodyflip journal sections
are staged; concurrent Unreal/training/other-lab work stays outside this commit.
Restore instructions: [Bodyflip README](Labs/BodyflipLab/README.md) and
[Recovery](Docs/Recovery.md). Existing split-blend33 +browser6 checks passed;
no new build, inference, editor action or process restart for the checkpoint.

## October 24 21:48 Warsaw - COM2 loss x10 RUNNING

User requested multiplying the existing COM2 loss by10 and resume from latest.
Only config coefficient changed: 5.64175020548 -> 56.4175020548.
Same constant per-motion COM2 targets, forward/sideways leeway, all-row/all-tick
scope, termination, sampling, optimizer and physics. No recalibration.
Run 20261024_214841_uefn_locomotion_com2x10_2048 on existing L4 w754z82j94t55a,
2048 worlds at <=$0.59/hour until stopped. Latest source checkpoint
checkpoint_0180862_final.zip, 4,810,932,224 samples,
downloaded locally to C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\MimicKitLocomotion\preserved-latest\20261024_130124_uefn_locomotion_com2_2048\checkpoint_0180862_final.zip
and SHA256/ZIP plus persistent-readback verified. SHA 2fa2a4737498b7ea81bfc8c805d71177f245dc8cf58f6e222408ad578b17e86e.
Advancing iteration180873, 4,811,653,120 samples;
first new backup verified, handoff guard released. loss/com2_velocity recorded
with new weight in actual replay and TB. Source diff is env_config.yaml only.
Helper Labs/MimicKitTraining/resume_com2_x10.py;
receipts Saved/MimicKitLocomotion/com2-x10. Current prepared plan updated.


## October 24 - Bodyflip separate Body / Leg blend durations

Sequence now exposes Body (existing jumpBlend) and Leg (new legBlend), seconds
0-1. Body starts at PUSH; Leg starts at contact release. Pelvis stays procedural,
pin timing unchanged. Body blend excludes support chain with Match foot on/off.
Old saved Leg inherits Body (.2s currently); zero supported. Edits retain time.
33 numerical +6 browser checks pass; settings/camera preserved. Lab only, no
NN inference, Unreal changes or server restart. [Details](Labs/BodyflipLab/README.md).

## October 24 - Bodyflip SUPPORT upper-body freeze investigation

Current saved Phase.67/Foot500/Lead6/Roll400: SUPPORT .900-.945833s.
Compared 21 samples against unmodified NN locomotion: all joints outside the
support leg match within numerical precision (position <5e-16m, angle <7e-14deg).
Arms move4.41/5.46deg during approach. No SUPPORT freeze in this setup; no motion
change warranted. PUSH starts the existing .2s smoothstep blend from a held
takeoff pose, so upper-body angular motion eases in there (left upper-arm local
change .00276deg at1ms, .272deg at10ms). This can read as a pause at PUSH.
Verification is specific to this saved setup, not a claim about every tuning.
Receipt: Labs/BodyflipLab/support-locomotion-verification.json. State untouched;
no NN inference, Unreal work, or process restart.

## October 25 - Bodyflip sole cone / immediate proximity launch / heel roll

Failed-fall pelvis fixed: current Phase30%/Cone60 aborts.904167s; root never
launches, but old fall-animation pelvis caused7.24cm upward rebound at1.10-1.15s.
Abort path now captures the displayed pelvis at the ledge and keeps it on capped
gravity while limbs blend. No extra gates or plant/timing changes. 36 focused
Run/Walk/Body0,.2,.8 checks pass for no bounce, continuity and active limbs.
Saved state untouched; receipts/details in Bodyflip README.

Ideal contact now clips to the cone from the lowest sole point and valid ground.
More options Cone defaults30deg half-angle (0-85); viewport Cone debug checkbox.
No cone/platform intersection aborts. Root-local ideal, foot selection, locomotion
and reach retained; miss history now measures sole-to-contact distance. Gate5cm
tests sole proximity, including at support entry, and starts PUSH immediately.
Nearby contact is captured by IK within gate/cone tolerance: no wait for ideal
ankle or Plant rotation. Gate0 waits for exact contact. Heel roll uses actual
captured pitch, preserving Roll speed, Toe-off and reach-limited release.
Run Phase54% now jumps.900s instead of.950s with no forward replant; Phase67%
approaches until.925s. 88 cone +33 blend numerical checks pass. Browser visual
check remains pending: CUA initialization twice failed with missing runtime path;
UI wiring inspected, fixture verify-cone.html ready. State/camera unchanged.
No NN/Unreal/server restart. [Current details](Labs/BodyflipLab/README.md).


## October 24 - Bodyflip phase stalls / planted sole contact

Phase was applying correctly but uncached requests took 4.55s because /run
started fresh NN inference. Phase/duration playback now reads exact precomputed
binary NN rollouts (all Run/Walk phases, both equipment states, through5s).
Server API4 removes runtime worker launches; export is one-shot single-thread CPU.
Original phase seeds/warmups preserved; three recorded Run phases match exactly.
Support no longer freezes at the distance gate while hovering: also requires
actual sole contact, retaining approach speed/reach/root advance/abort. Current
phase.67, Foot500: 4.84cm gap fixed, jump12.5ms later. Nine renderer-contact cases,
80 matching and162 support checks pass. Browser edits11-30ms; API10-63ms.
All100 cached rollouts validated; ten browser checks pass. Export exited; only
Bodyflip server restarted toAPI4. Current user tuning/camera retained. [Details](Labs/BodyflipLab/README.md).


## October 24 - Bodyflip gait phase clarification / verification

Phase selects the gait starting pose; user confirms the rest is working.
Verified 0 versus .44 through the UI handlers at time zero: displayed poses
differ by up to .67964m root-local, four checks pass. Also verified at .5s.
No runtime changes warranted. Phase applies on slider release and preserves
current playback time; it does not scrub the jump animation. Saved state restored.
Receipt: Labs/BodyflipLab/phase-verification.json.


## October 24 - Bodyflip playback timeline focus fix

Removed the focus guard that froze the timeline thumb after scrubbing and
resuming with Space. Timeline now follows displayed time even while focused,
including paused frame stepping. All 21 timeline browser checks pass. Motion
and saved tuning unchanged.
[Lab details](Labs/BodyflipLab/README.md).


## October 24 - Bodyflip closest-foot frame matching replaces endpoint blend

Removed fixed End pose experiment. More options now has Match foot (defaulton):
at release search trimmed jump frames for closest support ankle in pelvis-local
space, using actual hip socket. Play that leg from matched frame at rate
(end-match)/(end-release), synchronizing at existing fall transition. Other joints
and procedural pelvis retain clocks. Existing short Blend prevents snap from
imperfect match; off restores previous ordinary timing. Ghost shows retimed pose.
Current saved RunR matches .100s vsrelease.034095s, rate.965601x, gap12.76cm.
UI displays matched time/rate and tooltip gap. Standing cutoff remains. Old endLeg
setting removed; user tuning/camera retained. 80 numerical/7 browser checks pass,
plus28 legacy live-aim checks. Cached lab only, no NN/Unreal/server restart.
[Details](Labs/BodyflipLab/README.md); match-leg-preview.png.


## October 24 - Bodyflip velocity jump choice / endpoint support-leg experiment

More options (collapsed) now contains Stand / Walk ratio default.5 (WalkF2m/s,
cutoff1m/s) and End pose (enabled). Standing clip selected from measured horizontal
root velocity at support contact; existing Walk2/Run5 remain Run-start at default.
Exported actual Stand L/R read-only via one headless nullRHI commandlet, exited
successfully; no interactive editor running, no asset saves/builds. Separate
jumps-standing.json preserves old exports. Both retain automatic source trim.
End pose moves released support joints directly to last jump-only pose at the
fall-loop transition, arriving with other joints (~1.95/2.05s after jump starts).
Not extra pin time. Purple Anim leg shows that fixed destination. Off restores
live-target Blend behavior. User trimOut1.8 ends before arrival: extend bracket
for full experiment. Other tuning/camera preserved; option edits keep time.
69 numerical/7 browser checks pass, plus184 pelvis/28 aim legacy-mode checks.
[Details](Labs/BodyflipLab/README.md); jump-options-preview.png. No NN/server restart.


## October 24 - Bodyflip animation-target support-leg ghost

Added **Anim leg** viewport checkbox: purple x-ray hip/knee/ankle/toe for the
jump animation's supporting leg, anchored to current pelvis. User clarified this
means animation target, not procedural reach. No initial/support blends or IK;
includes later fall-loop transition. Default off, saved; no reset/replan on toggle
and no sampling while off. Hidden before jump/abort/Space. Existing Ghost unchanged.
16 numerical and3 browser checks pass. User tuning preserved, contained lab only.
[Details](Labs/BodyflipLab/README.md); anim-leg-preview.png.


## October 24 - Bodyflip released leg keeps aiming at ground

Fixed RISE/BLEND using a frozen release-local pose that translated with pelvis.
Blend source now recomputes IK from current hip toward planted ankle every sample,
within Reach, after air rotation. Existing release time and blend duration remain;
FREE returns to animation. No leg stretch or false contact after reach is exceeded.
28 live-aim checks pass across Run/Walk/L/R/flip plus184 pelvis and162 support
checks. User settings preserved, contained lab/cached motion only.
[Details](Labs/BodyflipLab/README.md); release-aim-verification.json.


## October 24 - Bodyflip procedural pelvis / masked jump blend

Pelvis now retains its takeoff root-local position/orientation throughout jump
and prolonged fall; root supplies height/forward trajectory. Animation cannot
lower it. Initial pose blend excludes pelvis and planted support leg. Support
hip socket remains fixed; existing IK pin/reach determines release, then Blend
hands the leg back to local animation. Other joints blend normally; air flip
still works around the procedural pelvis. Locomotion and abort paths unchanged.
184 pelvis checks (both gaits/equipment/feet, Blend0/.08/.2/1) show zero hip drop;
162 support and15 walk checks pass. Current user Blend.08/tuning/camera preserved.
Contained lab, cached files only; no NN/Unreal processes or server restart.
[Current behavior](Labs/BodyflipLab/README.md); pelvis-verification.json.


## October 24 - Bodyflip Walk + jump / measured push timing

Added Walk + jump to the existing selector. Frozen Walk July5 latest lower NN
plus Upper82500 at2m/s, equipment variants and cached defaults; Run stays5m/s.
Duration/phase, support, trim, arrows and COM follow shared. Server API3; only
Bodyflip server restarted. Transient single-thread CPU inference, no GPU/Unreal.
Saved tuning/camera preserved. Walk Auto with saved Foot300 misses and aborts;
FootR succeeds at300, Auto succeeds at800. No silent contact-rule changes.
Run investigation: saved blend.2/playback.3 gives approach.0125s, pin.10886s,
then leg blend.2s (~1.03s wall-time pin+blend). Jump root rises immediately, but
pose blending lowers support hip ~18cm in first.1s, so pinned leg flexes then
extends. Source lead-in.333s already trimmed. Explained without changing timing.
15 motion/7 browser checks and duration/phase API checks pass. Details and
jump-timing.json in [Bodyflip Lab](Labs/BodyflipLab/README.md).


## October 24 - Bodyflip alpha sensitivity / keep intended target behavior

User clarified that alpha was working: 0.1 and 0.5 both requested points beyond
available ground and therefore shared the same edge-clamped contact. Do not
redesign working behavior to agree with a reported bug; explain the constraint.
Only sensitivity changes: local forward lead = root speed * alpha / 200.
At 5 m/s: alpha 0.1 = 2.5 mm, 0.5 = 1.25 cm, 1 = 2.5 cm. Saved numbers preserved.
Reverted interrupted current-pelvis anchor and extra ideal-marker work; retain
prepared root-local targets, half-hip spacing, moving gait, clamp and abort.
162 cached-run support checks pass. Tooltip/docs updated. Contained lab only;
no Unreal/NN processes launched. This supersedes the unscaled formula below.


## October 24 â€” Bodyflip root-speed alpha / global frame arrows

Lead is now root-local forward speed times alpha (seconds), with no COM velocity,
foot lateral-distance factor or division by approach speed. Alpha.02 at5m/s
requests10cm for either foot. Root heading carries the offset; actual contact
still projects to valid ground. Saved alpha/tuning preserved; numeric step.01.
Left/Right now pause and scrub exactly one authored1/60s frame globally, even
with sliders, selectors, buttons or trim brackets focused. Capture keydown AND
keyup; Up/Down are reserved rather than changing those controls. Focused writable
text/number/contenteditable fields keep normal arrows; readonly fields do not.
Manual frame scrubbing can inspect outside trim; Play/Step retain bracket bounds.
Repeated keys accumulate without lost frames; backward scrub clamps at zero.
152 motion/lead,6 grounding,43 browser key/lead and17 timeline checks pass.
Real keyboard verified on focused speed slider and foot selector: timeline moves,
speed.3 and FootAuto unchanged. Saved alpha2 retained.
Contained lab only, cached runs; no NN or Unreal processes launched.
[Current lab details](Labs/BodyflipLab/README.md); keys-verification.json.

## October 24 â€” Bodyflip run levitation fixed

Removed the lab's extra +5.5cm world-Y translation from the NN run in flight.js.
The cached NN gait is already ground-referenced; the extra lift raised stance
feet roughly5cm. Run bone heights now match the source exactly, retaining its
normal airborne gait phases. No per-frame root snapping or animation edits.
Measured actual renderer foot/toe boxes across both cached runs: stance gaps
within3.1mm; existing interpolation dips up to9.4mm below ground are unchanged.
Six grounding checks plus144 support/abort checks pass. Visual stance verified.
Current Foot300/alpha1/Early.10 now launches at.9125s after6.25cm forward approach.
Only contained lab/docs; settings preserved, no NN/Unreal processes started.
[Details](Labs/BodyflipLab/README.md); ground-verification.json in the lab.

## October 24 â€” Bodyflip root-local support / no freeze / missed-edge abort

Ideal support contact is stored root-local before finite-ground projection;
every authored240Hz step transforms it with the root and queries valid ground.
Foot approach is root-relative at Foot cm/s, carrying root momentum. Lead is
fixed from the preparation pose instead of feeding moving-foot displacement back
into the target. Removed the body hold; cached gait continues while approaching.
After the cached endpoint, carry its last pose forward without another NN call.
Actual foot-to-valid-target distance recorded every substep; first increase
over0.01mm aborts. Gate/reach still required for takeoff. Failed attempts release
IK with Blend, run to the ledge if still on ground, then fall with the speed cap;
HUD ABORT - RUN/FALL, no jump ascent and no frozen WAIT SUPPORT state.
History: BodyflipLab.state.flight.supportHistory. Replay/seek is deterministic.
Current user Foot300 / alpha1 / Early.10 retained: jump.9167s, root advances8.33cm
during approach. Foot10 miss abort1.0083s as gap grows8.28â†’8.73cm.
144 numerical and27 browser checks pass. Contained lab only; no NN/Unreal processes.
[Current lab behavior](Labs/BodyflipLab/README.md).

## October24 â€” accepted oil liquid / glass base line correction

User approved the liquid shown in Transmission/front-plain.png; preserve it.
M_OilBottleLiquid now saves transmission(.72,.32,.018), roughness.035, specular.45,
opacity0, refraction1.003 and cheap refracted-cylinder chord absorption. No new
CPU work, collision or scene capture; this is approximate volume optics. The
native constructor default binding remains current in normal DLLs. No new build.
The1.035 trial narrowed the oil visually and was rejected; mesh thickness never
changed. Glass-only A/B isolated broken black base strokes to screen refraction.
M_OilBottleGlass RefractionStrength .01â†’.001 removes the doubled rim; all other
settings retained. Saved glass only for this final fix; protected liquid/cork and
all bottle/debris mesh SHA256 hashes unchanged. No map/scalability/physics edits.
Current1200Â² front/oblique previews and receipt: Saved/Diagnostics/Oil/Bottle/
GlassBase/glass-base-fixed.png, glass-base-oblique.png, receipt.json.
Previous golden-oil-1080p.mp4 remains8-check impact/debris evidence, not current
appearance. Accepted airborne splash/puddle unchanged. See Docs/OilStains.md.
Owned editor18340 hit Unreal !IsRooted while deleting old liquid expressions,
before saving. Recovered in owned20236; recipe now reconnects rooted expressions
safely and version2 preserves the approved liquid on subsequent installs. Exact
approved shader saved, then glass-only fix verified. Owned20236 closed cleanly;
no test/encoder remains and no user editor was involved.
Prior cleanup rejection remains in effect for old diagnostic files; no retry.

## October 24 â€” Bodyflip pelvis / cm/s / inverted vertical orbit

Pelvis render box now centers on the two thigh sockets, removing the hard-coded
7 cm downward bone offset. Skeleton, IK and physics bodies unchanged.
**Foot cm/s** uses the intended 800 cm/s = 8 m/s. Both approach and COM lead
prediction convert to metres per second. Current Foot set to 800; other tuning
and camera retained. Earlier claims that 800 m/s was intentional were wrong.
Default approach spans several 240 Hz steps, at most 3.33 cm each; root ascent
still waits for the gate. Saved alpha20.1 at Early.10 now requests an unreachable
target: WAIT SUPPORT is expected; user informed, alpha preserved. Alpha1/default
configuration verified to jump. Left-drag vertical orbit inverted; horizontal
orbit, middle pan and right-target drag unchanged.
122 numerical, 22 browser support/orbit and 20 editing checks passed, cached runs only.
No NN/Unreal processes. Preview: Labs/BodyflipLab/pelvis-units-preview.jpg.
[Current lab details](Labs/BodyflipLab/README.md).

## October24 â€” bottle edge/tint/cork refinement and native1080p

User's enlarged screenshots exposed remaining aliasing/dark rim and uneven tint.
Material A/B at1920Â² isolated refraction patches from the960Ã—720 preview upscale.
Glass now neutral transmission, specular.25, refraction strength.01 (IOR1.0052),
SSR off on that material; EdgeCoverage.2 softens overlapping grazing interfaces.
Oil uses pow(Tint,NoV), cancelling UE's sheet1/NoV absorption instead of the prior
NoVÂ² term that faded yellow out at the sides. Tint(.99,.88,.38), specular.15;
background/light reflections still vary. Cork is brown(.10,.048,.018), roughness.82,
with derivative-filtered pores. Recipe: Tools/Oil/BottleMaterials.py.
At that stage only three bottle materials saved; the later default-material
correction above supersedes its no-native-build state and pale preview.
Accepted splash/puddle untouched. Capture AA6 is process-local, not saved user
scalability. Native1920Ã—1080/CRF16 video (no upscale), plus1920Â² hero:
Saved/Diagnostics/Oil/Bottle/Studio/studio-bottle-1080p.mp4. All7 real-impact,
20-fragment, fade/cleanup/spill checks pass, impact tick199. Current details and
shader approximation limits: Docs/OilStains.md. One owned BelowNormal editor,
one single-thread encoder; close/cleanup at end of this turn.

## October 24 â€” Bodyflip earlier jump option / alpha ledge workaround reverted

User correctly noted alpha was functioning; reverted the automatic platform-edge
expansion introduced last turn. Edge is again speed Ã— Run âˆ’ .12 m, independent
of alpha. Existing alpha formula, uncapped values and lead readout remain.
Added **Early s** beside Run, default **.10 s**; 0 restores old timing. Support
preparation uses the cached gait at Run âˆ’ Early, then still waits for the foot
gate. Default cached takeoff .904 s instead of 1.004 s, same fixed ledge.
Early leaves at least one authored frame of running; unreachable support still
waits. Click-away/Enter commits and edit-in-place playback fixes are retained.
120 numerical and 20 browser editing checks pass. Direct keyboard edits at
0.95 s show RUN with Early 0 and PUSH with Early .10, preserving playback time.
Only contained lab/docs; no NN or Unreal processes.
[Current behavior](Labs/BodyflipLab/README.md).

## October 24 â€” Bodyflip commit edits / retain playback time / alpha feedback

Number fields now blur/commit on outside pointer-down, including canvas clicks
whose default focus change is prevented. Enter also commits/unfocuses. Sequence
parameter edits rebuild at the current time; paused remains paused and playing
support edits resume there. Reset remains explicit. Cached support edits use no NN.
Measured alpha 1â†’20: previous final contact shifted only 8 mm and hit the old
ledge; at Foot 800 m/s the requested lead itself is only ~1 cm. The finite ledge
now allows a 12 cm margin after predicted contacts, capped by leg forward reach.
Lead readout reports actual cm and marks edge limiting; formula is unchanged.
Verified 104 support checks plus 17 editing checks (`editing-verification.json`),
and real canvas-click / Enter commits at 1.05 s without a time reset. Alpha 1â†’20
moves the planted foot forward 0.912 cm at that same time. Original alpha 20.1
and other saved tuning restored. No NN/Unreal processes launched.
Details: [Bodyflip README](Labs/BodyflipLab/README.md). Contained lab only.

## October 24 â€” Bodyflip support alpha uncapped

Removed the upper bound of 10 from **Lead alpha**, both UI and settings sanitizer.
Any finite nonnegative value, including values above 1 and 10, is accepted/saved.
Default remains 1. At Foot 800 m/s, alpha 10 yields only about 5 mm of forward
lead for the cached gait. Actual contact remains clamped to the finite platform;
its edge is unchanged. Only contained lab controls/docs changed; refresh the lab.

## October 24 â€” Bodyflip playback speed

Shortened the timeline on the right for a compact **Speed 0.1Ã—â€“2.0Ã—** slider,
default 1.0Ã— and saved. Changes playback speed live without restarting; authored
timeline/trim/Step and fixed simulation step sizes remain unchanged. Bounded
frame work is retained. Only Bodyflip lab UI/clock and current docs changed.
Refresh the desktop lab. [Details](Labs/BodyflipLab/README.md).

## October 24 â€” Bodyflip procedural support plant

Replaced authored support preparation / jump-pose distance selection with a
procedural ground contact in **Kinematic**. Pelvis projects to the finite platform;
ideal L/R contacts sit half a hip width along its tangent. Auto selects the nearer
corresponding foot; L/R overrides remain. Prediction is COM tangent velocity Ã—
alpha Ã— lateral foot distance **divided by foot speed**, as clarified by user.
Controls: **Reach .99**, **Gate 5 cm**, **Lead alpha 1**, **Foot 800 m/s**.
Speed-limited approach gates root ascent; plant the reached position without a
final snap, hold in world space with fixed-length two-bone IK, release at reach
limit, then blend that leg into its matching jump clip using Blend. Other limbs
blend at takeoff; Air flip starts after foot release. Green ring shows contact.
Unreachable contact waits; slow-foot approach can hold the body at the ledge.
Read [Bodyflip README](Labs/BodyflipLab/README.md) for contact-gap and geometry
details. **104 numerical / 20 browser / 17 bracket checks passed** using cached
runs only. Preview: `Labs/BodyflipLab/support-preview.jpg`.
No NN worker, Unreal, native build, shared assets or other sessions changed.
Existing bracket settings preserved; refresh the desktop lab to load this change.

## October 24 â€” Bodyflip playback stays inside brackets

Fixed replay ignoring the visible range when Loop was off. In/Out now always
bound Run + jump playback: Loop repeats; without Loop playback pauses at Out.
Moving either bracket enables Loop automatically; Step also respects Out.
Kinematic remains active. `timeline-verification.json` passes **17 checks**,
including actual animation-frame playback, repeat wrapping, Loop-off stopping,
Step bounds and live drag previews. Only the contained lab and this handoff
changed; no NN or Unreal processes started. Refresh the desktop lab to load it.

## October 24 â€” Bodyflip inline trim brackets / live scrubbing

User rejected the extra trim row. Replaced it with draggable **[ / ] brackets on
the playback timeline**, highlighted range and compact Loop beside transport.
Footer restored to **56 px**; separate sliders/numeric fields removed. Hover/focus
shows endpoint time; arrows move one frame (Shift ten); saved ranges preserved.
Kinematic playhead and bracket dragging now update the scene **before release**,
coalescing pointer inputs once per animation frame without NN/replay work.
Current details: [Bodyflip README](Labs/BodyflipLab/README.md).
`verify-timeline.html` checks input-only live preview, latest-position wins, bracket
adjustments, compact layout, loop wrapping and kinematic membership; receipt
`timeline-verification.json`. Old loop test routes to the replacement fixture.
Only contained lab files changed. Refresh the existing desktop app.

## October 24 â€” Bodyflip playback In/Out loop

Run + jump playback bar now has **In / Out** sliders plus seconds fields and a
separate **Loop** checkbox. Edit boundaries, enable Loop, Play/Space to repeat.
Edits pause/preview that endpoint; bounds snap to 60 Hz frames and cannot cross.
Defaults 0â€“3 s, Loop off; values persist. Numeric fields extend range up to 600 s.
Kinematic remains selected. Seeking/wrapping directly samples the prepared sequence
and flip/twist phase without NN work or simulation replay; transient attack/hit
state clears per pass. Sim uses the existing yielding reconstruction if selected.
Attack Loop remains independent. [Bodyflip README](Labs/BodyflipLab/README.md).
`loop-verification.json`: 11 checks passed, including three wraps, exact restart,
boundary guards, pause and Loop-off behavior. Only lab files changed; no heavy
processes started. Refresh the existing desktop app.

## October24 â€” oil bottle studio lighting / smooth edges

Supersedes the earlier ghost-glass preview. Retains the exact Fab bottle; fixed
reversed UE render winding in the bottle +20 fragments (cork top was incorrectly
culled), without changing their collision shapes. PrepareBottle.py now exports
correct UE winding after manifold processing. New BottleMaterials.py recipe:
Thin Translucent glass with restrained screen-space refraction, warm dither-fading
cork, separate bulk-liquid material. Accepted airborne splash/puddle untouched.
Liquid edge uses48 sides/11 rounded rings and smooth side normals, correct render
winding; no additional physics or idle polling. Fixed mesh capacity3168triangles.
Normal incremental build passed:4 actions, one module compilation,56.22seconds.
DLLs current. Only the owned offscreen editor was closed/reopened for that build.

StudioSetup.py saves contained M_OilTest lighting/HDR/materials. Dedicated
background has no collision geometry and actor collision disabled; an earlier
background interfered with the test drop and was corrected. Saved map still has
both original bottle demonstrations. Explicit capture AA removes jagged edges;
global user scalability/config unchanged. Actual Jolt release breaks at tick199
into20 fragments;7 checks pass including fade/cleanup and spill. Current video:
Saved/Diagnostics/Oil/Bottle/Studio/studio-bottle-preview.mp4 (normal sequence +
labelled0.4x impact replay), hero.png and compact receipts. Reproduce via
StudioReview.py / ComposeStudioVideo.py. Historical ClearBottleReview.py disabled
so it cannot overwrite the new material. Details: Docs/OilStains.md.
Final capture measured0.397ms median /0.569ms p95 CPU liquid updates for one moving
bottle, no idle tick; not a many-bottle/GPU benchmark. Final video fully decodes.
Owned preview editor/encoder closed;15.5MB of discarded captures/raw video removed.

## October 24 â€” Bodyflip kinematic takeoff trimmed / support-foot Auto

Current work remains **Kinematic**, now also the fresh-settings default. Both
authored Lfoot/Rfoot jump variants already existed. Each now skips **20 frames /
0.333 s** before meaningful root ascent; root height is rebased at the cut. Run
ends directly in ascent, with no preparation delay or root-position discontinuity.
Blend still interpolates the body without delaying the root. Apex is 0.467 s (L)
or 0.533 s (R) after Run; edge/fall-loop/air-flip timing use the trimmed timeline.
**Foot Auto** chooses the smaller root-relative 3D supporting-ankle distance:
final-run left foot versus trimmed L support, right foot versus trimmed R support.
Removed the old whole-leg score at the untrimmed first frame. L/R remain explicit
overrides; status shows the chosen support. These are two authored opposite-foot
variants, not a claim of exact mathematical mirror symmetry.
Read [Bodyflip Lab](Labs/BodyflipLab/README.md). Focused sampling checks cover
immediate ascent, continuity, source pose fidelity, both overrides, exact support
matches and both choices across gait positions: `takeoff-verification.json`.
Browser results: `takeoff-browser-verification.json` (**20/20**). Also fixed timeline
pointer input losing its requested value during the pause redraw; real clicking
now seeks to 1.17 s and visibly shows RISE. No NN worker, Unreal process,
asset edits or physics tuning. Refresh the existing desktop lab.

## October 24 â€” Bodyflip tracking correction / kinematic comparison / hitching

User found button-focus Space conflicts, hitching and poor simulated gait. Changes
remain in `Labs/BodyflipLab`; [current details](Labs/BodyflipLab/README.md).
**Motion â†’ Sim / Kinematic** compares identical decoded NN targets and restarts the
sequence. Kinematic has no solve/contact response; Sim has 25 dynamic bodies.
Space now captures keydown/keyup and suppresses repeats, including with a
button/slider/checkbox/selector focused. Text editing keeps normal keys.

Diagnosis confirmed: initial Run + jump used spring joint motors, NOT the native
velocity tracking functions. Corrected to `ProphecyJoltVelocityServo.cpp`'s angular
error/substep command and parent-first predicted endpoints, with world position
tracking on pelvis only, gravity compensation and origin-to-COM velocity correction.
Joint motors are off in this mode; real constraints/contact remain. Original Space
motors remain. One-second frozen NN comparison: upper-spine mean angular error
28.10Â°â†’1.60Â°, left-hand 54.20Â°â†’6.17Â°. Hinge/contact errors remain; lab rig/tuning is
not native-rig parity. Source NN is unchanged. Kinematic exposes its exact poses.

Optimization: cached sword geometry/normals, unique vertex transforms, reused GPU
buffers, cached local pose sampling, scalar root-height derivatives, 10 Hz HUD,
bounded catch-up. Decoded NN cache makes reset/blend/foot/cap edits reuse a segment;
timeline reconstructs on release in short yielding batches. Measured same local
1000Ã—700 fixture: mean frame work 22.40â†’9.38 ms; p95 25.30â†’12.80 ms. Cached Reset
3.5 ms. These include test diagnostics/render submission, not GPU-present FPS.

Validation: **27/27** focused comparison checks, real focused-button Space toggle,
tracking regression, and 12 simulated seconds. Max anchor 4.111 mm, pelvis position
1.172 cm, pelvis angle 19.05Â°; fall cap respected. Receipts in lab:
`comparison-verification.json`, `tracking-before/after.json`,
`performance-before/after.json`, updated `flight-verification.json`.
Prior 16/39 UI receipts below are historical; sequence fixture adapted to async seek.
Only the small existing server remains resident; no NN/Unreal/build/training process
started for these fixes. Existing desktop icon; refresh the lab to load changes.

## October24 13:01 Warsaw - continuous COM2 loss RUNNING

User approved the discussed continuous COM2 loss and latest-checkpoint resume.
Run 20261024_130124_uefn_locomotion_com2_2048 on existing L4 w754z82j94t55a,
2048 worlds, <=$0.59/hour until stopped. Latest checkpoint171151_final,
4,174,512,128 samples preserved locally at C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\MimicKitLocomotion\preserved-latest\20261024_122025_uefn_locomotion_idle_speed40_2048\checkpoint_0171151_final.zip
and verified by SHA256/ZIP plus persistent readback. SHA 81ca9a7f441c99170e67bb2f2ef14521ba907964877acf848eb7ed14f68ad67f.
Advancing iteration171162 at ~22,506 transitions/s;
first new checkpoint171152 persistent readback verified; handoff guard released.

New loss/com2_velocity: mass-weighted pelvis/torso/head body-COM world XY velocity,
constant target equal to existing per-motion time average. Separate forward/sideways
symmetric leeway encloses reference deviations, sampled at240Hz midpoints AND grid
endpoints; all50 animations have exactly zero sampled authored loss. Idle target0,
world XY basis. Cost is mean squared excess beyond these two allowances.
Applied all rows, every tick, independently of AE/MSE fade or termination grace.
Fixed coefficient 5.64175020548, calibrated to10% of combined body loss
on120 recorded episodes across6 current-run evaluations, stratified by actual cohort
proportions. Calibration mean base 137.864, rawCOM2 2.71516.
This is a fixed offline calibration, NOT dynamically10% at every tick. Auto-phase
and discrete terminal penalties excluded. Termination rules, all existing loss
terms including legacy flat_com_velocity, optimizer, observations, and sampling unchanged.

Only pinned perturbed_omni.py, env_config.yaml and new com2_loss_reference.json
changed. Shared runtime received scoped optional patch, preserving unrelated recovery
work. Exact-method CPU checks: envelope zero, vertical ignored, idle zero target,
existing terms preserved, no timing/cohort gate. New loss reaches physical reward
through ordinary summed-loss path, full-batch statistics, and recorded replay terms.
TB card loss/com2_velocity verified remotely; local dashboard allowlist extended
and only this run's local dashboard restarted. TB filter13-01-24.
Helper Labs/MimicKitTraining/resume_com2_loss.py;
receipts/calibration/precomputed references: Saved/MimicKitLocomotion/com2-loss.


## October 24 â€” Bodyflip Lab simulated run â†’ jump â†’ void complete

Contained in `Labs/BodyflipLab`; desktop **Bodyflip Lab**, loopback **8876**.
Current details: [Bodyflip Lab README](Labs/BodyflipLab/README.md).
Default **Run + jump** uses frozen installed Run **181751** + Upper **82500** NN
weights through the original Stepper encoder/decoder (CPU, read-only dependency).
Run duration defaults to **1 s**, gait phase and jump blend have sliders. Real
GASP L/R running jump starts supply the root rise; the prolonged fall uses
`M_Relaxed_Jump_Loop_Fall`. Platform ends at lift-off; below it is an infinite void.
Downward speed defaults to **20 m/s**, with a configurable cap on actual body COM.
Camera follows mass-weighted simulated COM. All **25 bodies are dynamic**;
mode **0** principle means parent-relative limb angular motors and world-space
pelvis attraction only. This is the lab's Jolt implementation/tuning, not exact
native Unreal adapter parity. NN recurrence prepares a segment without physics
feedback. Original Space mode, attacks, draggable target, flip/twist remain.
Air flip is off by default and, when enabled, starts at lift-off.

Laptop containment: single-CPU inference workers exit after preparation; default
unarmed/drawn segments and four recent requests are cached. Idle server measured
**18.5 MB**, no resident Torch/NN; cached repeat **12 ms** (uncached **16.9 s** under
current load). Paused/hidden lab does no continuous rendering or simulation.
Export-only headless processes have exited and their Content junction was removed.
No gameplay C++ build, asset saves, training/model-pointer changes, or changes to
other labs/sessions. Export had unrelated dependency/config diagnostics; all three
source asset hashes and exported transforms independently verified.

Validation: final **16/16** sequence browser checks, original **39/39** UI checks,
320 attack clips and 12 axes verified. Twelve simulated seconds: maximum joint
anchor error **4.147 mm**, pelvis target error **8.779 cm**, pelvis angle error
**12.6Â°**; terminal COM speed respects the 12 m/s test cap to float precision.
Receipts: `flight-verification.json`, `sequence-browser-verification.json`,
`nn-verification.json`, `jump-export-verification.json` in the lab. No NN worker
is intentionally kept running after verification. Existing desktop shortcut remains.

## October24 12:20 Warsaw - perturbed idle speed-only termination RUNNING

User requested idle perturbed/perturbed+ horizontal trunk COM2 speed cutoff above40%
of matching WalkF mean COM2 speed; no direction/minimum-speed check. Limits0.813071m/s
Unarmed,0.800485m/s Drawn, precomputed once. Existing velocity gates retained: regular
perturbed ticks9-79 and130onward; perturbed+ first foot below1cm plus50ticks. Same
100 one-time failure cost, zero FAIL bootstrap; no penalty at timeout. Idle perturbed-
unchanged: non-foot ground contact failure100, no pose/spheres. No timing inputs added.
Run20261024_122025_uefn_locomotion_idle_speed40_2048 on existing L4w754z82j94t55a,
$0.59/hour until stopped. Resumed latest170458_final /4,129,095,680samples, saved
locally under preserved-latest/20261024_105104_uefn_locomotion_paired_2048 and
persistent-readback verified; SHA17f180d99533ecdd9f1efbd03dd4787a46073cbbe2c1f1302e486e6d7ec16ad9.
Advancing170509 /4,132,438,016samples,~22,155transitions/s; firstbackup170459 verified.
Handoff watchdog released. TBfilter12-20-25. Initial replay selected ordinary idle
and idle perturbed-; new perturbed-idle example pending normal evaluation rotation.
Changed only pinned perturbed_omni.py,replay.py,env_config idle_speed_walk_f_ratio=.4.
CPU exact-method tests cover timing boundaries,strict threshold,amplitude-only,
vertical ignored,minus/normal/loco unchanged,penalty once,and timeout; replay cost test passes.
No loss weight or sampling change. Helper:Labs/MimicKitTraining/resume_idle_speed_gate.py;
evidence and prepared plan:Saved/MimicKitLocomotion/idle-speed-gate.
Clarified COM2 is termination-only,not a continuous loss. Legacy flat_com_velocity
uses trunk+legs excluding arms; weight0.677104,original one-point10%calibration,not
a constant percentage. It is zeroed for all perturbed rows at all ticks, active on
normal/idle-minus only outside reference XYbands. Pelvis linear MSE multiplier10
is separate: perturbed MSE weight0.010628 through30,linear ramp to1at60; full weight
normal/idle-minus throughout. No direct COM2 shaping enabled by this request.
User rejects timing context; objective is correct velocity regardless of time. Explained
omitting context does not enforce that preference; rewards would need to encode it.


## October 24 - Fab Oil Bottle, impact breaking and prepared debris complete

`/Game/_mygame/OilBottle/BP_OilBottle` replaces both placeholders in the isolated
`/Game/_mygame/Tests/Oil/M_OilTest`. Feature assets live together under OilBottle
(Meshes, Materials, Debris, VFX); old paths have small redirectors. Fab Milk Bottle
by mokbulsd downloaded after explicit EULA approval;88KB source/attribution in
Tools/Oil/Source.27.735cm total height, seated cork,19 closed Voronoi glass pieces
plus cork, baked offline. Visible geometry unchanged by separate128/64vertex
collision LODs (max inset1.313mm bottle/.857mm pieces; required by Jolt hull limit).

Class defaults: Break On Hit=true, Break Impact Speed=250cm/s incoming relative
normal contact speed, Spawn Fragments=true, radial Fragment Velocity120cm/s,
Fragment Lifetime4 / Fade Duration1 authored seconds. Current effective material
slots/MID values copied at break; supplied shaders support FragmentOpacity.
No intact-bottle actor tick. New cosmetic OilInside component updates only during
motion/settling, then retires; shares the airborne oil material. Fill.65, slosh1,
damping.4; volume-preserving inscribed cavity, ordinary-tilt shortcut, no fluid
simulation/collision/queries. See Docs/OilStains.md. One debris fade clock,
actual Jolt bodies, complete cleanup.
Liquid final normal build/BP save passed;9 controlled-motion checks pass incl
inversion, volume, idle retirement/wake and empty opt-out.8second two-view video:
Saved/Diagnostics/Oil/Bottle/Liquid/oil-inside-preview.mp4. CPU update/enqueue
median136.6us/p95 194.7us in busy editor (not GPU/many-bottle benchmark).
Owned editor/encoders exited; temporary captures cleaned. User Oct24 reminder:
keep laptop work lightweight alongside their other sessions; one isolated editor
at a time, below-normal priority, bounded single-thread encoders, close after checks.
New placements Launch On Play=false; two demo bottles retain true. Manual Break
Bottle remains. No bomb/fuse/VDB or gameplay-map changes.

Oil rays now optionally ignore tagged OilBottleFragment actors before intersection,
preventing oil masks on tiny temporary shards; physical contacts/ordinary rays
unchanged. Controlled comparison reduced44 coating groups to4 in the four-spill
test. Final two-bottle video has3 groups/109 patches, then zero at tick660.
Normal DLL build succeeded.10 gameplay checks pass, including soft/hard impacts,
fragment opt-out, live MID override inheritance, fade/cleanup. Existing7 query
tests and new filtered-query assertions pass. Final actual UE video passes6
checks; same push moves wet cube216.915cm vs dry15.134cm. These are controlled
scene results, not a large-scale performance benchmark. Preview:
Saved/Diagnostics/Oil/Bottle/oil-bottle-preview.mp4 (24s,1280x720,30fps).
Receipts: test.json, defaults.json, bake.json, FilteredQuery/index.json,
Video/recording.json. See Docs/OilStains.md and Tools/Oil/{PrepareBottle,
InstallBottle,TestBottle,ComposeBottleVideo}. All owned test editors closed;
user/UI-lab processes were untouched. No push requested. Disposable capture
frames/intermediate videos/geometry and the owned null-RHI test crash are cleaned;
small regeneration source, receipts and final preview retained.

**October24 Mixamo throws â€” corrected animation-only exports for Cascadeur:**
User reported distorted mesh with initial mesh-inclusive exports. Replacement
`UEFN_Throwing_AnimationOnly.fbx` and `UEFN_Throw_Object_AnimationOnly.fbx` are in
`C:/Users/singerie/Documents/UEFN_Throws_Cascadeur_20261024`; old files preserved
in audit/SupersededMeshExports.88-bone rig/rest transforms exactly match user's
working Sitting_Idle_Anim1.FBX; no mesh/bind-pose objects. All315 joint frames
exactly preserve the retarget,168/147samples at30fps. No trim/speed changes.
Single lightweight background Unreal export; no assets saved, owned process exited.
User explicitly prohibits desktop control and requests lightweight processes.
Correction was checked offline, NOT imported in Cascadeur; user import pending.
Saved animations remain `/Game/_mygame/animations/MixamoThrows20261024`.
Details and reproduction: [Mixamo throws](Docs/MixamoThrowsCascadeur.md).

## October24 - read-only pushed-idle / perturbed+ failure investigation

Main2048 left training unchanged. Audit pinned checkpoint169460 /4,063,690,752samples
and its matching deterministic replay, locally downloaded to Saved/MimicKitLocomotion/failure-investigation.
All20 reward formulas match recorded data; terminal penalty100 is present for pushed idle
and perturbed loco. Pinned PPO zeroes FAIL bootstrap and records reward before reset.
CPU critic reconstruction validated against recorded phase output (max error0.000546).
Idle-minus row0: kick60, contact FAIL108, reward-99.994; critic already-20.68 at70
and-46.27 at90. Only22/2048worlds are pushed idle (7%idle *30%normal *50%pushed).
Perturbed+ examples: row2 FAIL51 at46.84degrees/74.29%speed; row5 FAIL57 at69.82%speed
and20.35degrees, critic+54.09 one tick before-99.535. Both improved velocity but missed
sharp thresholds. Another drawn run remains132.52degrees off, so not all are near misses.
Confirmed missing critic/actor context: cohort, elapsed/grace/push countdown and reward blend.
Exact pinned done+gate CPU test: same physical state/command/phase,49vs50ticks since foot
contact => reward+0.465vs-99.535. Hidden schedule is real; causal learning-speed gain
from context still requires an ablation. Early pelvis MSE shares0.010628weight through30,
full weight only60; plus grace may end51. Perturbed+ IDLE has no failure/100 penalty,
only150tick timeout. These are existing semantics, not changed during investigation.
KL guard not blocking:40accepted/0rejected,KL0.00747 at capture. No GPU allocated.
Evidence: findings.json,offline-analysis.json,hidden-clock-test.json,training-log-context.json
and reproducible audit.py/test_hidden_clock.py in failure-investigation.
Interpret deterministic rollout values as diagnostics, not actual noisy training advantages.
Candidate next tests: critic-only schedule context; explicit COM2 shaping during grace;
more pushed-idle exposure. No reward,termination,proportion,optimizer change authorized here.


**October24 Bodyflip Lab â€” isolated and ready:** new `Labs/BodyflipLab`, desktop
**Bodyflip Lab** shortcut/icon, loopback8876 and its own browser profile. Reuses
copied D/S renderer/math and all320 existing full-body attack clips across16
families. Original D/S sources verified unchanged.12 horizontal flip directions
at30deg intervals; separate pelvis-local twist angle/speed; right-drag target,
Shift-right depth, optional bounded aim, play/step/scrub, saved settings/snapshots.
Actual local Jolt WASM:25bodies/24joints, hinge knees/elbows, remaining limited
swing/twist joints; constant-speed kinematic pelvis, dynamic limbs, zero gravity,
240Hz physics/60Hz authored ticks. Dedicated lab profile, not current PHAT/DLL
parity; target is a non-blocking marker and sword hits use geometric checks.
All320source hashes,12axes and16attack families pass; max anchor error1.536mm,
hinge excess0.053deg, neutral tracking error4.364deg at120flip/60twist.39/39browser
checks pass, including synthetic right-drag/depth events, full-body playback,
scrub and cancel. App opened paused/neutral for user review. No Unreal build,
remote call, asset/BP edit, training change or modification of existing labs.
Read [Bodyflip Lab](Labs/BodyflipLab/README.md) before changes; receipts and preview
are contained there. Keep future iterations contained until an explicit port request.

## October24 - 4096 trial cancelled by user; main2048 continues

User requested removing the4096 trial and leaving2048 running. Clean stop completed;
owned trial pod24u69pod1xot9c confirmed EXITED (GPU billing stopped). Final checkpoint
checkpoint_0169227_final.zip preserved locally in Saved/MimicKitLocomotionSweeps/20261024_batch4096,
with SHA256/ZIP verification against persistent latest_verified metadata.
Final trial:4,065,984,512samples, completed iteration169227; receipt169228.
Trial ended early after1662.97seconds; planned35-minute comparison cancelled.
Comparison heartbeat compare-2048-agent-trial PAUSED. No automatic restart.
Main20261024_105104_uefn_locomotion_paired_2048 on w754z82j94t55a remains unchanged,
verified training at iteration169500,4,066,312,192samples,2048worlds.
TB main-only filter:10-51-04.*2048. Trial records retained; no checkpoint deletion.


## October24 10:58 Warsaw - main2048 and synchronized4096 trial RUNNING

Latest1024 run cleanly stopped; final checkpoint168959 preserved locally and S3
readback verified:4,030,857,216samples, SHA7ef78e39def67087d161edf317f0e26fbfdf58076b0ae941c1a00a8f94353634.
Local:C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\MimicKitLocomotion\preserved-latest\20261024_094745_uefn_locomotion_idle_contact_only_1024\checkpoint_0168959_final.zip
Main now20261024_105104_uefn_locomotion_paired_2048 on L4w754z82j94t55a,
$0.59/hour until stopped. Separate4096 trial20261024_105104_uefn_locomotion_paired_4096
reuses L4 24u69pod1xot9c at$0.59/hour. Both loaded identical latest1024 checkpoint.
Both training loops released10:56:11.319 Warsaw; recorded start difference
0.000559seconds. Trial35minutes ends11:31:11; hard billing
stop11:33:56 includes final evaluation/save/upload reserve. Main continues.
Verified main iteration168990 at22129transitions/s;
trial iteration168970 at23717transitions/s.
Each first checkpoint verified in persistent storage; handoff/setup guards released.
Trial remote deadline guard, exit watcher and local fallback guard remain active.
TB8035 both curves:regex10-51-04. Observers isolated by pod/state directory.

Source SHA7ccff24f0591b5b05ad96ce134690e64ca4bbca1b9054707892c9a2b85eaa57f. All config files byte-identical to prior1024 run.
Only train.py changes: allow2048/4096 in launcher assertion, optional one-time
--paired-start-file barrier before the training-loop clock. No physics/loss changes.
Current main authority: Saved/MimicKitLocomotion/getup-success-prepared.json and
final-phase-prepared.json. Trial/evidence: Saved/MimicKitLocomotionSweeps/20261024_batch4096.
Helper Labs/MimicKitTraining/loco_paired4096.py takes ROLE(main|trial) then ACTION.
At trial completion: trial collect_finished confirms EXITED, downloads/hash-checks
final checkpoint and complete persistent exit-evidence/events; main fetch retrieves
continuing baseline events without stopping it; trial analyze compares2100seconds.
Timing source timing-armed.json overrides scheduled assumptions; obey extensions.
Report wall-clock throughput and full-batch episode failure rates, not tiny replays;
single-run results are provisional. Pause comparison heartbeat after reporting.
No new GPU allocation required. Recovery/Unreal untouched. Old automation superseded.

Previous35minute2048 trial ended cleanly, final167846 at4,015,390,720samples retained
under Saved/MimicKitLocomotionSweeps/20261024_batch2048. Its throughput20161/s vs
1024baseline15602/s (+29.2%), but final3minute failure64.03% vs62.81% (not a learning
win). User nevertheless requested2048 main and next4096 test; followed explicitly.


## October24 10:22 Warsaw - separate2048 locomotion trial extended to35minutes

Main1024 run20261024_094745_uefn_locomotion_idle_contact_only_1024 remains running
unchanged on L4w754z82j94t55a. Trial2048 run20261024_100809_uefn_locomotion_batch2048_trial
on separate L4 24u69pod1xot9c ($0.59/hour), from same verified167205 checkpoint.
User added20minutes: training ends10:44:27 Warsaw; hard billing stop10:47:12,
including165seconds reserve for final evaluation/save/upload. Runtime controls and
remote/local guards updated. Trial source differs only by allowing2048 in train.py
world-count assertion; configs/learning settings unchanged. Trial source SHA
b5e68679482f8d1a25473356d0e387eb3c6499e8acb688880b8ce178146d8ae5.
TB8035 has both09-47-45 and10-08-09 curves. Trial data/backups isolated in
Saved/MimicKitLocomotionSweeps/20261024_batch2048. Main stays until stopped.
At completion use Labs/MimicKitTraining/loco_batch2048_trial.py collect_finished
(after pod EXITED) to fetch verified final checkpoint and complete event history
from persistent exit evidence; fetch_baseline collects main history without stopping it.
Then run analyze_batch2048_trial.py, which reads2100seconds from comparison.json.
Compare equal35minute windows; initial15minute baseline remains within full history.
Full-batch episode counters are primary; tiny replay samples and repeated stale
Test_Return scalars are not independent evaluations. One run is provisional evidence.
Setup attempts: qyurz46dryi7xk stalled and was stopped; trial initially hit old world
assertion, then setup watchdog during uncached warmup. Those attempts had no learning.
Complete runtime cache restored (remove only stale known venv symlink before restore).
First trial backup167206 and advancing167216 verified; setup guard released.


## October 24 09:47 Warsaw - locomotion resumed, isolated batch trial requested

Main run20261024_094745_uefn_locomotion_idle_contact_only_1024 is running on L4
w754z82j94t55a at $0.59/hour until stopped, from verified checkpoint167205
(3,973,382,144 samples). Source/settings unchanged. Advancing167216 at17277
transitions/s and persistent backup167206 verified; setup watchdog released.
Latest source checkpoint is safe locally under Saved/MimicKitLocomotion/preserved-latest.
User-authorized persistent cleanup removed690 old locomotion checkpoint archives,
freeing33,431,109,720 bytes;24 latest/verified archives retained. Old podtt2565dylarg7p
remains EXITED with retained disk; restart unavailable. Original stop cause unconfirmed.
TB8035 restarted; missing historical events on old disk are not yet recovered.
Evidence: Saved/MimicKitLocomotion/checkpoint-cleanup-complete.json and
storage-resume-live-verification.json. Recovery/Unreal untouched.
User requested separate15minute L4 trial2048 worlds versus continuing1024 main,
same checkpoint/settings. State: Saved/MimicKitLocomotionSweeps/20261024_batch2048.
Older RUNNING entries below are historical.

## October 24 00:50 Warsaw - pushed idle pose-distance termination removed RUNNING

User clarified that disabling sphere termination also means disabling the older
1m body-origin pose-distance check for `idle perturbed-`. Both are now disabled
for that cohort only. Added a cached per-row pose mask (~final.minus), passed to
stock compute_done via optional argument; other callers default to original rules.
Floor/contact failures,300tick timeout and pushed-idle failure penalty100 retained.
Other cohorts, velocity gate timings, optimizer, physics, proportions and losses
unchanged. Replay explicitly reports stock_pose_termination=false and empty target
termination body list for pushed idle, with contact_termination=true.

Run 20261024_005020_uefn_locomotion_idle_contact_only_1024 on existing L4tt2565dylarg7p,
$0.59/hour until stopped. Latest162004_final at3,802,955,776samples retained locally
and persistent-readback verified, SHA d31142e0377c270a93e577572323155877750be571adff60d266e15e24b554ae.
Local checkpoint: Saved/MimicKitLocomotion/preserved-latest/20261024_001155_uefn_locomotion_pre_push_velocity_1024/checkpoint_0162004_final.zip.
Verified advancing 162015 / 3803316224samples at
15995 transitions/s; first backup162005 verified.
Live replay confirms both pose checks off, contacts and penalty100 on. Handoff
watchdog released after verification. Recovery/Unreal untouched. TB run00-50-20.

Pinned source changes limited to deepmimic_env.py optional pose mask and
final_locomotion.py mask initialization/replay metadata; unrelated shared edits
not imported. Source SHA 80ac6342f95ff595682ed77e9f11581cd8a6b1d815b574b0aa46d1d5d801da77.
Authority Saved/MimicKitLocomotion/final-phase-prepared.json and getup-success-prepared.json.
Evidence under Saved/MimicKitLocomotion/idle-contact-only/verification.json and
live-verification.json. CPU TorchScript tests cover masked/unmasked pose failure,
non-foot contact, allowed foot contact, timeout, completion, first tick; recorded
step161378 frames129/130 reproduce old [NULL,FAIL], now [NULL,NULL] for pose-only
termination with zero contact forces. Helper Labs/MimicKitTraining/resume_idle_contact_only.py.
Older RUNNING entries below are historical.


## October 24 00:11 Warsaw - regular perturbed velocity checks before push RUNNING

User clarified that regular perturbed rows preserve initial target COM velocity,
so the check must also run before the push. Now active ticks9-79 and130 onward;
initial8-tick grace and push recovery ticks80-129 excluded. Perturbed+ retains
its50-tick first-foot-contact grace. No new fall/sphere checks, no reward changes;
all existing failure penalties (including pushed-idle100), proportions and losses
remain intact. Only final_locomotion.py gate and replay description changed in
pinned source; shared unrelated recovery work was not imported.

Run 20261024_001155_uefn_locomotion_pre_push_velocity_1024 on existing L4tt2565dylarg7p,
$0.59/hour until stopped. Resumed latest161077_final at3,772,579,840samples,
retained locally and in persistent storage with SHA 08927b603ac751091c2bf18736b86279d6c228696429d51401fcd9082d2b7624.
Local checkpoint: Saved/MimicKitLocomotion/preserved-latest/20261023_225715_uefn_locomotion_idle_failure100_1024/checkpoint_0161077_final.zip.
Verified advancing 161088 / 3772940288samples at
15554 transitions/s; first backup161078 readback verified.
First live evaluation includes a regular perturbed failure at tick9, confirming
the restored early check. Replay metadata identifies both active windows.
Handoff guard released after checks. Recovery/Unreal untouched. TB run00-11-55.

Authority Saved/MimicKitLocomotion/final-phase-prepared.json and getup-success-prepared.json;
source SHA 01569d443ef33c17b4c5ded91a53f4ef9afaeac69f944d6c112c3f1af724600f. Evidence under
Saved/MimicKitLocomotion/pre-push-velocity/verification.json and live-verification.json.
Boundary tests cover0,8,9,79,80,129,130,149; perturbed+ expression unchanged across151ticks.
Helper Labs/MimicKitTraining/resume_pre_push_velocity.py. Older RUNNING entries
below are historical.


## October 23 22:57 Warsaw - pushed-idle failure penalty100 RUNNING

User approved -100 once on actual `idle perturbed-` failure. Previous masks excluded
these normal pushed-idle rows. Added `_final.minus & done==FAIL`; success/timeouts,
other rows, proportions, physics, optimizer and other losses remain unchanged.
Critic production-return test verifies the negative reward reaches value targets;
failure future value remains zero. Replay metadata/validation include the new cost.

Run 20261023_225715_uefn_locomotion_idle_failure100_1024 on L4tt2565dylarg7p,
$0.59/hour until stopped. Resumed latest159187_final at3,710,648,320samples,
verified locally and in persistent storage (SHA 3d6eb7fedc4c2805d839f030b961dfd9f9106feab283531002571d6fa17ee416).
Local checkpoint: Saved/MimicKitLocomotion/preserved-latest/20261023_205457_uefn_locomotion_idlepush60_pelvis10_1024/checkpoint_0159187_final.zip.
Verified advancing 159198 / 3711008768samples,
16186 transitions/s; first backup159188 verified.
Live pushed-idle replay has FAIL and penalty100. Handoff guard released after checks.
Recovery/Unreal untouched. TensorBoard run22-57-15.

Authority Saved/MimicKitLocomotion/final-phase-prepared.json and getup-success-prepared.json;
source SHA 5a9806de9c0f57cab419e950792e8157e3f846a40cf4ae609cb361cc6f5a5864. Built from pinned old locomotion source,
only3 runtime/replay edits and1config field; unrelated recovery edits not imported.
Evidence Saved/MimicKitLocomotion/pushed-idle-penalty/verification.json,
critic-verification.json and live-verification.json. Helpers in Labs/MimicKitTraining:
prepare_pushed_idle_penalty.py and resume_pushed_idle_penalty.py.
Older RUNNING entries below are historical.



## October 23 20:54 Warsaw â€” idle pushes60 and pelvis velocity MSE10 RUNNING

User asked to RESUME LATEST, superseding the prior restart-from-init instruction
for this change. Latest checkpoint156086_final from19:54run retained locally and
in persistent storage, SHA9ec2cc720a52dd3529c4a6338025e101f469e5ee0a2649a50bb8ea0c92b206f7,
3,609,034,752samples. New run20261023_205457_uefn_locomotion_idlepush60_pelvis10_1024
on same L4tt2565dylarg7p, $0.59/hour until stopped. Verified advancing156097 /
3,609,395,200samples at16.1k transitions/s, first new backup readback verified.
Handoff watchdog released only after that verification. Recovery untouched.

Only two configuration changes: normal pushed-idle kicks every60frames (2s),
previously30; all-rows pelvis LINEAR velocity MSE multiplier5->10 (double current
pelvis contribution). The multiplier applies before early/handoff MSE weighting,
so both stages and normal rows are covered. Other body velocity terms, angular
velocity MSE, trunk COM loss/termination and perturbation settings unchanged.
Runtime kick timing and precomputed kick-plan indexing now use configured interval.
Timing test: idle60/120/180/240/300; perturbed locomotion kick80 unchanged.
Uniform perturbed+ pose/joint-velocity blends and50frame foot-contact grace retained.

Authority Saved/MimicKitLocomotion/final-phase-prepared.json; source SHA
76eb59ffa9385f5e8d6b1ba07e516d42f79c015ec5f5c485e12d9660c2b15519.
Local and remote archive checksums match; persistent source readback verified.
Evidence idle-push60-pelvis10/change-verification.json and live-verification.json;
timing test idle-push60/timing-test.json under Saved/MimicKitLocomotion.
The idle60-only package was superseded before deployment. TensorBoard run20-54-57.
Older RUNNING entries below are historical.

## October 23 19:54 Warsaw â€” locomotion uniform-blend RESTART

User supersedes19:31run as stale: restart from its INITIAL checkpoint154586_final
(3,559,882,752samples), NOT stale final155049.155049 is separately retained in
persistent storage; stop receipt Saved/MimicKitLocomotion/final-phase-blended/stale-run-stop.json.
New run20261023_195413_uefn_locomotion_final_blend50_1024 on existing L4tt2565dylarg7p,
$0.59/hour until stopped. Verified RUNNING at154597 /3,560,243,200samples,15.8k training transitions/s.
First new backup154587 verified in persistent storage; handoff watchdog released
only after advancing updates. TensorBoard publishing. Evidence live-verification.json
in the blended state directory. No recovery/Unreal edits.

Perturbed+ now blends full authored start pose (root position/orientation and
child joint orientations) toward the prior full random perturbed+ pose, using
one uniform alpha[0,1] per initialization. SAME alpha blends authored joint
velocities toward random joint velocities. Root linear/angular velocities keep
the previous random-dataset rule. Original authored frame is sampled uniformly
within the assigned motion; phase/reference offset matches it. Quaternion
interpolation follows shortest arcs; any intermediate floor penetration gets
only its minimum upward clearance correction, baked offline.

51,200 precomputed starts (1024 per motion), all1000limp source poses represented;
alpha mean0.499936,50.15% below0.5. First-foot contact grace is50frames (was40),
then existing COM2 termination activates. Other cohorts, pushes,150frame horizon,
losses/penalties/proportions/optimizer remain unchanged. No per-reset grounding.
Frozen1024-world160-tick GPU check passed;22.97k rollout transitions/s.
Builder Labs/MimicKitTraining/prepare_final_loco_blend.py; authoritative plan
Saved/MimicKitLocomotion/final-phase-prepared.json, source SHA
c17b263f77387e1cb1841b2ddf0ae55a850e957c57199c3fb2d8227b50ecbfb3.
Evidence Saved/MimicKitLocomotion/final-phase-blended/verification.json and preflight.json.
Use this builder for this variant; original prepare_final_locomotion.py builds
unblended starts. Prior19:31status below is superseded.

## October 23 19:31 Warsaw â€” final locomotion perturbations RUNNING

Run `20261023_193108_uefn_locomotion_final_push_plus_1024`, replacement L4
`tt2565dylarg7p` at $0.59/hour, until stopped (standing user authorization).
Old locomotion L4 `leuh8va7hfcevy` could not restart; retained disk untouched.
Recovery training/Unreal work untouched. Resume checkpoint154586_final,
3,559,882,752 samples, SHA e31bd4bf87600a4daa8cf638972b01a146df0e6deaee57cc7e7a5f0f8e9e98f8,
remains verified locally and in persistent storage.

1024 worlds retain7% idle/93% locomotion,30% normal/70% perturbed,
walk/run50/50. Integer allocation:307 normal (including10 pushed idle),
215 perturbed,502 perturbed+. Perturbed episodes150 ticks.
- Perturbed: random locomotion limb poses/velocities, old yawÂ±180deg,
  original target trunk COM velocity preserved. Independent horizontal0â€“3m/s
  kicks to both hands, both feet and pelvis at tick80. COM2 termination only
  ticks130 onward; all other existing perturbed objectives retained.
- Perturbed+: all1000 recovery limp poses retained,16 baked upright-cone
  variants each (pelvis tiltâ‰¤45deg). IMPORTANT latest user correction:
  height = lowest non-clipping pelvis height + uniform0â€“60cm, NOT absolute60cm.
  Random dataset root linear/angular velocity; independently sampled dataset
  joint velocities. First foot bottom<1cm latches timer; COM2 termination
  enables40 ticks later. No new termination before this gate.
- Half of normal idle rows receive independent five-body kicks every30ticks;
  only their sphere termination is disabled. Normal idle objective/phase remain.

Offline banks:25,600 pushed starts,16,000 plus starts,8192 kick sequences.
Bank SHA3745ab99104021e2a63481482bfa24fbb7e3d79ccf3ca0bcd6e531b2dc52dbb5.
No online pose search/IK/grounding. Event-only GPU articulated impulse solve
produces mass-independent requested horizontal COM speed increments. Frozen
1024-world test verified baked states, kick/frame boundaries and160 rollout
steps; actual kick errorâ‰¤0.00112m/s,22.4k rollout transitions/s. Production
154597 reached3,560,243,200 samples at15.4k training transitions/s; backup154587
verified by persistent readback. Setup guard released only after that verification.
Existing AE/MSE handoff, penalties, loss weights, optimizer/noise and native
240Hz physics/30Hz control unchanged. Large airborne loss at floating starts
is expected under the retained walking airborne penalty; no silent rescaling.
Replayer keeps two idle examples and covers all three locomotion cohorts,
including idle perturbed- and perturbed+ labels.

Prepared/source authority: Saved/MimicKitLocomotion/final-phase-prepared.json,
source SHA 2371185f4ddb945614c215c9c10ddea8194e4e7ce4fd53c2696869a6ff4711c1. The source archive is based on the
stopped locomotion package, not concurrent recovery files. Runtime opt-in patches
are applied by Labs/MimicKitTraining/prepare_final_locomotion.py; do not rebuild
from the unrelated working-tree recovery trainer. Evidence: final-phase-preflight.json,
final-phase-live-verification.json, final-phase-inits/feasibility.json in that state dir.
Builder: precompute_loco_final_inits.py; runtime: final_locomotion.py;
deploy: deploy_final_locomotion.py. Current setup/status files under locomotion only.

## October 23 â€” Why the Jolt get-up viewer sometimes looks faster

Read-only investigation; accepted weights, physics profile and gameplay untouched.
Across99paired successful fresh starts, native mean25.49ticks (0.850s), Jolt26.90
(0.897s); medians22vs23. Jolt faster16, equal18, slower65. Common-time-window mean
per-case angular RMS ratio0.944 and linear RMS ratio0.967. No global speedup;
viewer advances both recordings on one30Hz timeline, simulations240Hz/30Hz.

Default viewer case0 is a real outlier: Jolt32ticks vs native62. Native head first
passes its height threshold at43, then fails feet-height gate through61; Jolt
passes all gates at32. Head-origin peak vertical speed3.174vs2.489m/s, so its
push is also sharper in this case. Case94 native72/Jolt24 follows different
recovery attempts; it is not a rescaled copy of the same movement.

Frozen-policy mechanism probes on12stratified cases used the existing isolated
candidate executable. Baseline state arrays matched saved Unreal exactly.
No drag:12/12, mean23.83ticks vs baseline23.83; case0 remains32. Gyro enabled:
12/12,25.17; case0 remains32. Limit16Hz:12/12,24.08; case0=34. Limit8Hz:
11/12,46.92 (includes failure tick), case0=71. Half motor gain:12/12,41.08;
case0=46. Alternative motor clamp ordering:12/12,25.50; case0=32.
These are diagnostics, not adopted settings or a new tuned profile.

Loaded native model confirms no passive DOF damping, no fluid viscosity/density,
no armature and no extra drag hook; velocity-motor gains/caps match Jolt.
Jolt adds small compound drag and zero native per-body damping. Native ball limits
use solref[0.02,1], while Jolt uses32Hz critical spring limits; contact/integration
also differ. Limit response demonstrably influences the sharper recovery; this
does not isolate all contact/motor contributions or establish trajectory parity.
Success transfer remains100/100, but that never established equal trajectories.
No reason from these measurements to globally slow Jolt or add arbitrary damping.

Evidence: Saved/MimicKitTransfer/getup-transfer-20261023/speed-investigation/
(trajectory-stats.json,case-details.json,ablations.json,native-model.json).
Reproducer: Labs/MimicKitTransfer/investigate_getup_speed.py.
References: MuJoCo modeling solver parameters; Jolt5.6 MotorSettings and architecture
damping documentation. Training stays stopped, no cloud GPU allocation.

## October 23 â€” Broader frozen-checkpoint transfer test: Unreal/Jolt 100/100

Viewer follow-up: fixed a first-animation-frame negative time delta that could
index frame -1 and kill playback. Clock starts on the first animation callback
and resets on resume; Play at the endpoint restarts. Both viewers and the shared
template updated; fresh-100 generator now reads/writes HTML explicitly as UTF-8,
also correcting its stale18-test header. Browser Play/Pause verified after reload.

User requested 100 fresh get-ups before accepting transfer. Fixed-seed2026102301
test used the actual saved training reset code:50front/50back, each with25ordinary
perturbed and25perturbed+ starts; uniform whole-pose limp blending, original
floor correction, separate locomotion root/joint velocity frames and0â€“700deg/s
spin.94distinct limp poses; no filtering, retries or tuning against the results.
The prior32Hz spherical-limit profile and accepted pelvismax161960_final weights
were frozen before sampling. Deterministic policy, flat floor,240Hz/30Hz unchanged.

Results: native MuJoCo99/100; actual installed Jolt inside Unreal100/100.
All99native successes transfer, and native failure case27 also succeeds in Jolt.
All four25-case cohorts pass in Unreal. Five owned headless Unreal automation
processes completed successfully. Initial observations were checked against the
production environment. Full initial states, metadata and trajectories retained.

Evidence: Saved/MimicKitTransfer/getup-transfer-20261023/fresh-100/summary.json.
Viewer: http://127.0.0.1:8843/Saved/MimicKitTransfer/getup-transfer-20261023/fresh-100/.
Harness: Labs/MimicKitTransfer/check_getup_100.py. No training or cloud allocation.
This supports using the accepted weights without fine-tuning for this reset
distribution. Same installed Jolt library as gameplay, but the new spherical
constraints remain opt-in on the isolated test rig; gameplay defaults are NOT
updated. No RunLR changes. Uneven-floor/live gameplay integration not covered.

## October 23 â€” Native pelvismax works in opt-in Jolt recovery tests; training STOPPED

The accepted native pelvismax run13-11-28 checkpoint161960_final stays unchanged.
Local ZIP SHA256 reverified:0dc58150f87f1cb25816235f9e565638e9972d262b9203c5da0d14c0ea736a2b.
User requested adapting Jolt to these weights to avoid long retraining. No training,
GPU allocation, checkpoint deletion, PHAT edit or gameplay-default change this turn.
Recovery poduks8hn8yeqnpxf remains stopped by the prior explicit user request;
stop receipt Saved/MimicKitEquipment/user-stop-transfer-doubt-20261023.json.
Earlier RUNNING entries below are historical, not current authorization/status.

Actual Unreal/Jolt frozen-policy tests now pass18/18 recorded perturbed starts,
versus1/18 with the prior angular limits; both recorded normal clips also complete.
The fix is an opt-in Jolt spherical angular-limit constraint matching the native
training bound (PHAT-centered total angle, radius=max of the three limits), with
32Hz critically damped softness. Motors/caps,240Hz physics/30Hz policy and success
criteria are unchanged. Native Jolt library unchanged; only isolated recovery rig
construction adds this constraint. This is not the rejected custom MJWarp solver.

Evidence/profile: Saved/MimicKitTransfer/getup-transfer-20261023/jolt-native-profile/.
Comparison: http://127.0.0.1:8843/Saved/MimicKitTransfer/getup-transfer-20261023/comparison/.
Unreal and standalone full state traces match exactly for all18. Four starts used
for tuning, fourteen additional starts; deterministic flat-floor evaluation only.
Normal front test starts0.933s into its clip (18ticks remaining), back starts0s
(42ticks). This does not establish arbitrary-state or full gameplay integration.
Details, activation and limitations: Docs/MimicKitTransfer.md. Training stays stopped.

## October 23 16:24 Warsaw â€” corrected recovery restart RUNNING

Resumed directly from accepted native pelvismax13-11-28 checkpoint161960_final,
SHA0dc58150f87f1cb25816235f9e565638e9972d262b9203c5da0d14c0ea736a2b.
Run20261023_162429_uefn_getup_bounded_jolt40_native161960_1024, Secure L4
uks8hn8yeqnpxf,$0.59/hour, until stopped. Tested warning-fixed custom source
753129e55c65 and bounded_jolt_40_20,1024agents,240Hz/30Hz; learning settings unchanged.
This supersedes the capacity-blocked status below. No stale custom continuation.

Verified advancing161981 /3,669,671,936samples,2.42s/update (~13.2k transitions/s).
New backup SHA/persistent readback verified; resume.zip exact native SHA checked
on pod. TB curve live; local replay downloaded. Setup guard released only after
successful verification. Audit native-restart-20261023/live-verified.json.
Trainer452/exit guard453; bridge20768/dashboard780. No locomotion changes.
Unrelated TensorBoard history restored; only four stale custom attempts hidden.

## October 23 â€” corrected restart pending GPU; TensorBoard cleaned

User explicitly rejected all custom-solver continuations as stale. Resume ONLY
native pelvismax run20261022_131128_uefn_getup_pelvismax7_1024, checkpoint161960_final,
SHA0dc58150f87f1cb25816235f9e565638e9972d262b9203c5da0d14c0ea736a2b.
Local ZIP and persistent readback verified again. Main getup-success-prepared.json
and unexpected-stop-20261023/prepared.json now pin that original checkpoint with
warning-fixed source753129e55c65, bounded_jolt_40_20,1024 worlds, same settings.
Do not use prepare() in resume_contact_warnings.py: the stale162261 route is disabled.
Its stage/launch/verify now support the corrected native restart. Evidence and
superseded plan: Saved/MimicKitTransfer/getup-transfer-20261023/native-restart-20261023/.

Run155033 stopped15:56:48 Warsaw: checkpoint upload QuotaExceeded at162364,
not a solver error. Podl4fcl20i2n04u9 EXITED; restart GPU unavailable. Replacement
Secure L4/RTX4000Ada and Community4090/5000Ada/A6000 unavailable at<=0.59/hour.
No new pod allocated or billing. Until-stopped restart remains authorized, pending
capacity. Earlier RUNNING entries below are historical and superseded.

Freed7,392,990,078bytes by deleting170 redundant intermediate backups from the
original pelvismax run under the standing intermediate-cleanup authorization;
first and final161960 preserved. Old replay archives were already absent.
Other branch checkpoints untouched. Cleanup inventory/receipt in audit directory.

TensorBoard cleanup corrected after user objected to overreach: unrelated historical
runs restored to normal newest-ten selection. Only four October23 custom-solver
attempts (09-00-57,11-35-22,11-50-10,15-50-33) remain hidden. No event logs deleted.
The earlier storage deletion of170 intermediate pelvismax checkpoints was outside
this TensorBoard cleanup request; first/final retained. Do not infer authorization
for future checkpoint deletion from a request to hide TensorBoard runs.


**October23 recovery â€” warning fix RUNNING on equivalent GPU:**
User authorized retry, then equivalent GPU. L4 still unavailable;4090/5000Ada
also unavailable. Resumed162261 as20261023_155033_uefn_getup_bounded_jolt40_warnings_1024
on Secure RTX4000Ada podl4fcl20i2n04u9,$0.28/hour, until stopped. At162292,
last30 updates2.604s /12,583 transitions/s vs L4's2.315s:12.5% more time/update
at less than half the hourly price. New162262 backup SHA/readback verified;
TB32tags and20-row replay live. Setup guard released after verification.
The previous run stopped on an obsolete four-point assertion. Larger patches
now retain every point with an informative warning; differing normals have
separate friction patches. Actual failed equations give identical velocities;
NaN/capacity failures remain fatal. Source753129e55c65 unchanged from tested fix.
Initial162261 is locally safe; stale162044 and native161960 remain preserved.
Helper Labs/MimicKitTraining/resume_contact_warnings.py; evidence in
Saved/MimicKitTransfer/getup-transfer-20261023/unexpected-stop-20261023/.
No locomotion, Blueprint, physics tuning or unrelated Play changes.

**October23 oil bottles â€” Niagara droplets and flared sheet installed:**
Supersedes the native instanced bead renderer below. Test bottle and both map
instances now reference `/Game/_mygame/Tests/Oil/NS_OilDroplets`:360 small
velocity-facing, velocity-stretched sphere particles per burst. Reduced sphere
mesh12.5% triangle target; separate droplet material; no Niagara collision,
readback, shadows or additional native traces. Existing56 native samples retain
all landing/stain authority. The procedural sheet now has a low center and curved,
raised five-lobed rim; same193vertices/320triangles and actual contact handover.
Niagara advances once per authored60Hz tick and expires; pending first-use asset
preparation catches up to the current age. Normal incremental4action81.72s build
passed; normal DLLs current. No user editor/Play interrupted, no push.

Video `Saved/Diagnostics/Oil/NiagaraFlower/Angles/oil-splash-three-angles.mp4`:
18s,1280x720,60fps,1,634,918bytes; overhead,22cm low view, angled; each normal
speed then labelled1/3speed replay. Droplets and raised rim visually inspected.
6/6 checks pass. Native slider samples, landing ticks48/54/60/66/72, last sheet60,
coverage/lifetime counters exactly match prior accepted recording (max delta0).
Wet/dry travel224.782719/15.133747cm. Full video decode passed. This is authored
playback, not a new aggregate GPU/FPS benchmark. Small receipts in NiagaraFlower;
raw captures/intermediate streams cleaned. Owned test processes exited.
Builder `Tools/Oil/CreateNiagaraSplash.py` uses the installed converter's editor
authoring API only; plugin not enabled in project/runtime. Rebuilding its generated
NS requires explicit `-ProphecyOilRebuild`; preserve future user edits. Wiring
helper copies the oil struct before assignment and explicitly dirties/saves the
two isolated actors: mutating a borrowed struct had silently failed to save its
new reference. See [OilStains](Docs/OilStains.md).

**October23 oil bottles â€” previous sheet landing handover and native beads:**
Airborne-only follow-up: visible beads restored using existing instance slots,
with bounded cosmetic height/size variation and velocity stretch. No landing,
coverage or friction changes. Straight trial strands were rejected and removed;
normal incremental4action47.08s build passed. Overhead, near-floor22cm and angled
video ready: `Saved/Diagnostics/Oil/Airborne/Angles/oil-splash-three-angles.mp4`,
18s/60fps/1280x720/1,206,983bytes. Each view includes normal speed then a labelled
1/3speed replay.6/6 capture checks pass; landing ticks, coverage/lifetime counters
and all sampled native cube positions/velocities EXACTLY match the accepted
Landing recording (maximum delta0). Same56 instance slots and query budget;
default38 sheet beads +7 free drops visible. No new Niagara or physics work.
Full video decode and camera-frame review passed. Raw captures cleaned, compact
receipts retained in Airborne. Owned processes exited; user UI labs untouched.
User rejected the nested sheet/puddle silhouette in the first landing video.
The old center-to-rim110/140/170/200 launch speeds staggered sheet contact too
far apart. Sheet points now share an180cm/s arc with a small ripple. Their full
area transfers to the coating on contact and stops drawing the airborne layer;
free fringe droplets alone retain six-tick splat expansion. Contact frames on
mesh and Landscape inspected; revised video is ready for user review.
The sheet now survives until actual surface contact. Default56 samples comprise
49 traced sheet points (center +3 rings) and7 free fringe drops. Each landed point
transfers into full-size wet coverage; denser interior coverage makes a mostly
connected puddle. Display interpolation uses at most193vertices/320triangles,
one sheet draw and no extra collision rays. Landed spans interpolate linearly to
avoid curve overshoot. Counts below13 retain separate drops only. This remains
a bounded ballistic approximation, not fluid simulation.
Shared body-local union masks retain the previous overlap/tint fix: one sheen +
optional3.5% tint per compatible connected group, shared visual/friction fade,
512x5128-bit masks, no settled raster/upload. Materials sample OilCoverage UV.yx;
run UnionAppearance.py last after historical appearance-recreation tools.
Final normal incremental build4actions51.46s passed; normal DLLs current. Final
cold1800tick regression12/12 passes, including moving receivers, limbs, cleanup
and64 Landscape comparisons. Actual Unreal660tick recording passes6/6 checks;
sheet persists through landing and retires, all effects disappear. Two identical
cubes receive one150cm/s push: oil224.78cm versus dry15.13cm after2.5seconds.
No continuous force/teleport or artificial puddle under the character.109 patches
form3groups/6decal components;28 mask rebuilds remain unchanged120â†’360ticks.
These counts are not a whole-frame FPS benchmark; old physics-only timing remains
in [Oil stains](Docs/OilStains.md), alongside controls, limits and replay steps.
Physics review `Saved/Diagnostics/Oil/Landing/Video/oil-sheet-landing-and-physics.mp4`:
22s,1280x720,30fps,1,826,770bytes; full decode and sampled-frame review passed.
Final video and compact receipts retained; own raw captures cleaned. Owned test
processes exited. WeaponWheelLab4296 and PauseMenuLab10504 left untouched. No
asset/BP/map edits, user editor restart or push this revision. Cross-body/material/
strongly curved surface charts remain separate; large areas reduce mask detail.

**October23 recovery transfer/speed investigation â€” corrected fine-tune RUNNING:**
Native161960/custom162044 preserved. Four difficult native-MJ successes fail in
headless Unreal/Jolt feedback tests; one custom perturbed get-up succeeds at18
ticks in custom and19 in Unreal. Other custom successes do not all transfer.
Old RunLR acceptance used a separate patched DLL, never installed in gameplay;
its map was a recorded preview. Fixed custom reset body-velocity cache refresh.
User authorized fine-tuning from native161960, explicitly rejecting
custom162044 as the restart point. Fixed-budget40-pass custom profile passes
all16 old RunLR starts and six selected custom get-ups; packaged reset refresh
passes. Resumed native161960 as20261023_115010_uefn_getup_bounded_jolt40_1024
on replacement L4 grxkeijwtwvrkp at$0.59/hour, until stopped. At162011, last30
updates average2.407s /13,614 transitions/s versus previous custom25.72s:
10.69x faster, about14% more time per update than nativeMJ2.118s.
New checkpoint161961 persistent SHA/readback verified; TB and20-row replay live.
Setup guard released after verification; failure/billing guards remain. Original
and failed-attempt pods are stopped with disks retained. Current evidence:
Docs/MimicKitTransfer.md and Saved/MimicKitTransfer/getup-transfer-20261023.
No asset, Blueprint or WeaponWheelLab changes; separate locomotion stays stopped.

**October23 recovery â€” STOPPED, final custom-solver checkpoint downloaded:** user ended this experiment. Saved162044_final locally in `Saved/MimicKitEquipment/preserved-latest/20261023_090057_uefn_getup_custom_final_1024/`, verified SHA256 and ZIP against persistent backup. Recovery pod0to3wg3r3n926h confirmed EXITED; GPU billing stopped. Final replay available, prior native161960_final retained. Restart handoff points to custom162044 but no restart authorized. Receipts under `Saved/MimicKitEquipment/custom-solver-final-pass/`. The earlier RUNNING entry below is superseded.

**October23 recovery â€” custom solver final pass RUNNING:** saved native161960_final locally and verified persistent SHA256/ZIP, then resumed as `20261023_090057_uefn_getup_custom_final_1024` on recovery L4. Earlier Jolt-style contact/motor/limit solver plus floor guard restored;1,024 agents,240Hz physics/30Hz policy, learning settings unchanged. Advanced161971; new checkpoint161961 backup verified; TB/replayer live. First11 updates average~25.72s (~1.27k transitions/s) versus native~2.12s (~15.47k/s), about12x slower. Existing until-stopped duration retained. Audit `Saved/MimicKitEquipment/custom-solver-final-pass/verified.json`; see MimicKitTraining. Independent locomotion state below is owned by its other chat.

**October23 locomotion â€” STOPPED for final phase:** user requested latest download
and stop. Final154586 (3,559,882,752samples) preserved locally under
Saved/MimicKitLocomotion/preserved-latest/20261023_000133_uefn_locomotion_translation_speed_head_1024/.
Persistent readback, local SHA256 and ZIP verified. Loco pod leuh8va7hfcevy
confirmed EXITED; GPU billing stopped. Final TB/replayer sync finished.
Recovery untouched. Latest checkpoint/restart handoff updated; no new run started.

**October23 locomotion speed loss â€” RUNNING:** resumed latest140173_final as
20261023_000133_uefn_locomotion_translation_speed_head_1024. Extremity speed
subtracts only pelvis translation; rigid body rotation now counts. Added head;
all five reference limits recomputed at150% peak, idle uses backward walk.
Same soft-loss weight, perturbed idle/loco only. Other settings unchanged.
Latest CP preserved locally/S3; new backup and actual replay rewards verified.
Advanced140184 at~15.3k transitions/s. Recovery untouched. See MimicKitTraining.

**October 22 checkpoint cleanup:** downloaded and SHA256/ZIP-verified recovery145097 and locomotion137705 into each branch's `preserved-latest/<run>/`. Removed178 intermediate checkpoints from today's two active runs in persistent storage (7.92GB), plus corresponding pod copies; first/latest/newer checkpoints preserved. Both trainers remain running. Audit: `Saved/MimicKitEquipment/checkpoint-cleanup-20261022/completed.json`; details in `Docs/MimicKitTraining.md`. No retention-policy change.

**October22 locomotion checkpoint downloaded:** latest verified137705 saved in
Saved/MimicKitLocomotion/preserved-latest/20261022_203036_uefn_locomotion_walk_height2_1024/.
SHA256 and ZIP integrity checked; training left running. Receipt latest-local-checkpoint.json.

**October27 UI - twenty larger ruby-and-gold refinements ready:** User supplied
the selected ruby/gold menu and requested greater sophistication, height and
width. All 20 retain its enclosed rectangle, translucent interior, bright text,
vertical five-action order and selected Continue. Current gallery:
`Labs/MainMenuConcepts/2026-10-27-ruby-refinements/index.html`.
01-05 frame, 06-10 typography, 11-15 material, 16-20 detail. Exact new attachment
copied/hash verified. All 20 made with built-in imagegen and individually
reviewed: 20 unique decoded 1672 x 941 PNGs, 33,481,486 bytes (31.93 MiB).
Each panel visibly taller/wider; prompt dimensions are targets, not runtime
measurements. Prompts/source paths/validation saved; links/script syntax checked.
Arrows browse, B compares reference, D enables scrolling 2x details; selected
concept gets a #concept-NN URL. No live browser control. Await selection;
native implementation deferred. Scene preservation is visual, not pixel-identical.
Previous enclosed, broad UI, lighting and ground galleries preserved.
No game title or Unreal/preset/build/push changes.
[UI topic](Docs/WeaponWheelUI.md).

**October23 UI â€” approved optical font option loaded in pause lab:**
Latest October24: user approved and saved pause UI; requested UI-only push.
Include both isolated UI labs, runtime artwork/fonts, saved presets, font study
and pause concepts. Unselected opacity saved0.8032181263, whiteness0, right
extension200. User cancelled disaster-recovery audit; do not conduct it here.
Chronological tuning order remains mandatory: append new controls at bottom.
Final build12.31s;351/351 input checks passed. No main-game integration.
User approved the font-only study. **R â†’ Menu hairline strength** now selects
Bodoni Moda's authored optical size24â†’6 (19 steps, weight400); starts at B Medium
(size10). Removed the rejected translucent outline. Only five menu labels
change; PAUSED/footer/decorations untouched. Save persists
`menu_hairline_strength`. All13 previous user settings preserved.
Four-action incremental build21.67s;21/21 input checks passed. Native comparison
verified6304/7184 changed menu pixels and zero change elsewhere. Review25084
left open; only owned pause lab restarted, wheel4296 and main project preserved.
See Docs/WeaponWheelUI.md, pause README and VerifyOptical.py. No gameplay hookup.

User chose Fine Underline (variation02). Independent native UE5.7 project
`Labs/PauseMenuLab` now implements its visual composition, mouse/keyboard
selection, pause/resume preview and persistent tuning. R tunes, P hides hints,
F5 reloads, F12 snapshots.4-action build passed16.62s;21/21 handler checks and
final1672Ã—941 capture verified. Review instance11072 left open; wheel4296
preserved. Separate typography/gradient/blur/underline/star/glow; no gameplay
hookup or other menu pages yet. About43MiB including binaries; no shared PCH.
Read [Pause lab README](Labs/PauseMenuLab/README.md). Stop for user rating.

20 distinct pause concepts saved in `Labs/PauseMenuConcepts/2026-10-23/`;
`index.html` gallery, `manifest.json` exact prompts/provenance. Built-in imagegen,
English, forest backdrop, translucent celestial styling. Requested Blueprint
push checked: saved Blueprints already match remote
16d490e0; fetch/push returned up to date. No unrelated staging. Wheel remains isolated:
UE5.7 `Labs/WeaponWheelLab`; open with its `Open.ps1`. Eight varied orbit profiles
replace uniform dashed rings; stars/pearls sit on their carrying curves. New
local crescent/star glow, smooth Gaussian name backing and whole-wheel size
slider. Native live color picker controls the selection and halo (R â†’ Settings).
New independent Center/Circle line/Connecting line brightness controls (0â€“1)
replace the shared Ornament brightness slider. Center1; circles/connectors inherit
the previous saved brightness when new keys are absent; later user tuning wins.
Independent Center font size(12â€“36,default22) and Center decoration size(0â€“1.5,
default1) now available. Font changes do not move/scale surrounding decorations;
decoration size scales stars/diamonds/lateral lines and their positions together.
Latest saved preset preserved; small pre-font backup retained. Save settings
persists all controls. Darkness controls remain.
All new UI, labels, docs and conversation must remain **English**.
Prior45/45 input checks at three sizes; four rendered layer comparisons and color
callback comparison passed; native picker opened/rendered. Native1024Ã—949
capture retained. Size controls4-action build passed14.14s; own review window4296
left open. No main game/editor/assets/wiring changes. Shared PCH remains disabled;
lab~48MiB including outputs. Production GPU cost not measured. See
[WeaponWheelUI](Docs/WeaponWheelUI.md). Stop for the next visual rating before
gameplay hookup or further scope.

**October22 evening TensorBoard revived:** restarted missing local8035 server
and both bridge/dashboard pairs. Current recovery13-11-28/loco20-30-36 graphs
caught up; trainers untouched. Receipt Saved/MimicKit/tb-revive-20261022.json.

**October22 recovery checkpoint downloaded:** latest verified142097 saved locally
in MimicKitEquipment/preserved-latest; SHA256/ZIP checked. Both training runs
left unchanged. Receipt latest-local-checkpoint.json; see training journal.

**October22 walking height envelope â€” RUNNING:** locomotion resumed latest134504
as20261022_203036_uefn_locomotion_walk_height2_1024 on existing L4,1,024agents.
Walking rows also penalize the higher foot bottom exceeding the assigned walk's
reference maximum (24walks,1.88--6.26cm). Fixed weight calibrated2% of existing
loss using57,344noisy samples; existing8% airborne penalty unchanged. Reuses
foot detector; added math~0.047ms/batch. Actual replay losses/rewards, backup,
advancing134515 (~15.9k transitions/s) and newTBcard verified. Latest resume CP
preserved locally and S3. Recovery/idle viewer unchanged; see MimicKitTraining.

**October22 walking jump penalty â€” RUNNING:** locomotion resumed latest133578
on existing L4 leuh8va7hfcevy,1,024agents until stopped. New run
20261022_194959_uefn_locomotion_walk_ground8_1024. Only walking inputs, normal and
perturbed: squared excess when BOTH exact foot-box bottoms exceed1cm. Fixed
weight calibrated8% of existing live training loss; percentage varies afterward.
Analytic two-box detector~0.29ms/1,024worlds. Actual reward/masks, backup, advancing
133589 (~15.1k transitions/s), replay and loss/walking_airborne TB card verified.
Pre-change/latest saves preserved locally and S3. Recovery/idle viewer unchanged.
See MimicKitTraining opening and walking-airborne receipts.


**October23 isolated free experiments -- investigation active:**
STOPPED by explicit user request on October23,2026. Investigation closed as
unsuccessful overall: no verified faster learned policy. Do not resume, retry,
launch experiments or schedules unless the user explicitly requests new work.
Kaggle teacher-consistency v2 completed naturally during shutdown; API COMPLETE
and browser Active Events=none verified. No experiment compute remains active.
All14 local schedules are PAUSED, including check-kaggle-comparison-results.
Production locomotion/recovery/Unreal are outside this stop request and untouched.

Cleanup inventory:311 disposable files /625,497,379bytes under ONLY
Saved/MimicKitSuperMimic. Original96009/119475 checkpoints and source archive
outside this directory verified by SHA256 before proposing duplicate removal.
Preserve code, research source/provenance, reports, receipts and production data.
User subsequently explicitly requested the Recycle Bin. All311 inventoried files
(625,497,379bytes) successfully moved to Windows Recycle Bin; source absence
verified, zero errors. Production checkpoints/code/reports preserved.
Space is NOT reclaimed until the bin is emptied; no permanent deletion performed.
Exact inventory cleanup-manifest-20261023.json and successful receipt
recycle-receipt-20261023.json retained in Saved/MimicKitSuperMimic.
Earlier blocked deletion receipt cleanup-receipt-20261023.json is historical.

Historical pre-stop state follows; it must not trigger more work:

Previously active Kaggle madmad74100/prophecy-teacher-consistency v2. v1 ERROR after
repeat-zero-score assertion at42s planning, bothworkers stopped; exactv1logs
archived prophecy-teacher-consistency-v1-failed. Initialobs identical, but
zero32tick score changed~.02â€“.04 cohortmean, oneFAILoutcome. New assertion was
too strict for nondeterministic GPUphysics; do not claim production bug.
Official MJWarp FAQ confirms nondeterministic GPU atomics. V2 explicitly records
three identical zero repeats with per-tick observation/action drift and score
variation before repeated CEM searches. Initialobs2e-4 assertion unchanged.
No activev1job/duplicate. V2 sourceSHA
4b00ff56304b5eaceffb56049a26b245a00128829e7378521383f864f3d6c628;
workerSHA e1745fb80ed20f1b922ead27257b6368b9733ce83e18f9aca083e3d9d37c996e.
Exactv2receipt/source archived. Parent500s/Kaggle750s; all v1/v2 costs count.
V1 procedure below retained for method context; monitor VERSION2 only.

Teacher consistency procedure:  Submitted, verifying
startup now. Bootstrap verifiedoriginalcheckpoint at41.57s and both workers
started41.57s. Two workers984220/984221, each repeats native16candidate CEM twice
from identical initial states with independent candidate RNGs. Compare zero,
winnerA/winnerB and their mean in unchanged real MuJoCo120ticks, deterministic
and sigma.075. All weights frozen; no production changes. Parent500s bound,
Kaggle900s. Retain candidate choice scores and residuals this time.
Receipt/source teacher-consistency-v1-* underSaved/MimicKitSuperMimic.
SourceSHA f6f95147f26604af9111f2cee2810212f1fa98da4c82a8f686e068a28bb48e7f.
Gate before more distillation: mean improves noisy real return with paired95%CI
above0 and >=1pp fewer failures on BOTH cohorts. No speedup claim; both searches,
all setup/evaluation and prior209.731s teacher collection accounted.

CPU retained-teacher audit COMPLETE in0.782s, localteacher-data SHA verified
7451c44bbff5ee8dc608218a33eee8ecdd5ae3b72fb714adaa9a6edd812e1b40.
19040teacher rows=2380distinct starts x8taperedframes; validation2272=284x8.
Taper verifiedexact. Initialheldout nearest-state residual MSE is2.082x zero;
32neighbor mean1.033x zero; meanlabel energy.0455%, topSVDdirection3.66%.
This indicates poor local label predictability, NOT proof no nonlinear policy
can fit it. No candidate scores retained in prior dataset, so cannot audit
benefit-weighted imitation there. Audit teacher-audit/teacher-audit.json.
Primary references POPLIN arxiv1906.08649 sections4.4/5.2 actiondistillation
collapse; PMLR32/levine14 trajectory/policy compatibility. New probe diagnoses
independent search target variability and physical effect of averaging.

Native-fidelity-probe v1 COMPLETE, fetched/analyzed and
archived in prophecy-native-fidelity-probe-v1-reports/verified-native-fidelity.json.
Workers original176.97s/cap4 161.08s; notebook289.57s. No actorupdates;
policy exactzerochanges. First measured result rejects candidate: warmed
original98.363s/cap4 83.806s=1.174x, below1.5x gate. Noisy normal loco
18/572 original versus474/572 cap4; perturbed323/1332 versus537/1332.
Original240Hz/30Hz unchanged; only solver caps differ. No production promotion.
Exactreceipt/source archived native-fidelity-v1-* underSaved/MimicKitSuperMimic.
Next: inspect why native planner corrections fail policy transfer using retained
teacher data and heldout states before spending another GPU run. Check teacher
coverage/action residual ambiguity and phase/observation conditioning; do not
repeat already failed fullstudent/frozenfeature fit/LR variants unchanged.
Free Kaggle only. No verified faster learner. Preserve active production.

Conditional multi-fidelity probe v1 COMPLETE/analyzed.
Both workers finished in91s (225s notebook including bootstrap/cleanup). Original
policy/world unchanged exactly; real reward maxerror.000225 and0FAILmismatches.
Heldout32tick projected-gradient variance ratios by branch0/24/56/80:
1.0031,1.0132,.9942,1.0015; all95%world-bootstrap intervals include1.
Measured diagnostic variance-times-cost1.40â€“1.46; no followup-training gate passes.
8tick best observed ratio.9498 also hasCI[.737,1.076]. Coefficient calibration
849200 and heldout984200 are separate;64motor-head projections, not fullactor.
Reject this learned-model CV, not all MFPG. No actortraining or speedup claim.
Exactv1 source/receipt and verified-multifidelity.json archived in v1 reports.
Next discrepancy: published MFPG uses reduced-accuracy native physics rather
than an inaccurate neural world. Check solver iteration caps at unchanged
240Hz/30Hz, original geometry/friction/motors, then compare fidelity and actual
cost before any training. Original solver100iterations/50line-search,1e-8tol;
these are caps, not proof that100iterations are actually executed. Production
settings remain unchanged. Free only; bounded screening before any learner.

Transfer-head-race v1 COMPLETE, analyzed and archived.
Full79/head-only83updates used148.58/147.20s actual learning; both ended
328/1332 noisy failures (24.625%), above starting22.973/23.048%.
Head-only return29.905 versus full28.016; paired difference CI[-1.054,4.525],
not reliable; head-only also regressed its own baseline31.992. Prospective gate
FALSE. Hidden features stayed exactly unchanged, motor heads genuinely updated;
median KL .00000279 versus .000507 full. Frozen transfer preserved ordinary
locomotion better but did not improve perturbed locomotion. No promotion.
Exact v1 source/receipt and verified-transfer.json archived; normalized source
SHA2a1aa4e3908b8b35d56b6195bd55f0c6526a3d204ccbc07b7bfd7d0a4e4147ed.
Original96009/task/noise retained; prior326.301s model preparation remains charged.

Next: bounded multi-fidelity control-variate feasibility screen, then training
only if measured gradient-variance reduction justifies its extra compute.
Primary source arxiv2610.02505 (MFPG-PPO, Oct1 2026) uses real trajectories,
noise-coupled low-fidelity twins and an independent low-fidelity mean; warns
about resynchronization bias and monitors empirical variance. Q-Prop's claimed
unbiased gains require caution: arxiv1802.10031 identifies asymmetric advantage
normalization in its public implementation. Do not repeat that mistake.
Our proposed screen keeps all weights frozen, uses original sigma.075 and exact
reward/FAIL checks, and estimates heldout motor-head gradient variance at8/32
steps. Independent model trajectories start from the same real state to avoid
an uncontrolled distribution difference. This is a conditional control-variate
screen, not a faithful MFPG-PPO reproduction or a learning-speed result.
Free Kaggle only; production, checkpoints and Unreal unchanged.

Uncertainty planner v1 COMPLETE/analyzed/archived-v1, rejected.1332newstarts:
noisy control307failures23.048%,raw334/25.075%,penalized333/25.000%.
Penalized return29.239 versuscontrol32.110,paired95%CI[-5.328,-.440].
Det control19.895%,penalized20.796%. Model ranking21.35/21.39s versus
native16candidate pool40.83s, but worse real outcomes; no teacher/learning gain.
Fitted lambda1.55678; uncertainty/relative-score-optimism correlation train.015,
heldout-.148. Penalized heldout optimismMAE14.000 versusraw13.923; state-error
correlation did not translate into useful reward-error calibration. This is a
measured failure of this shared-trunk ensemble metric, not proof all uncertainty
methods fail. Scorer maxerror.00006032,0FAILmismatches; recurrentmean parity and
policy/world exactzerochanges verified. Workers213.35/213.62s plus~165s
bootstrap; calibration65.47s, prior531.200s model preparation remains charged.
Reports prophecy-uncertain-planner-v1-reports/verified-uncertainty.json;
receipt/source uncertain-planner-v1-launch.json and uncertain-planner-v1-source.py.
Do not repeat this ranking/penalty unchanged.

Latest result: feature head fits in0.940s, alpha.1 chosen on heldout worlds,
original base/phase/critic exactly unchanged. Teacher energy explained only3.02%
versus rawstudent9.90%. Existing cohort noisy24.249% versusPPO24.850%; fresh
cohort22.748% versusPPO22.222%. Pooled2664episodes626candidate/627control
failures (23.498/23.536%), return31.251/31.206, difference95%CI[-1.279,1.443].
Prospective gateFALSE; no physical improvement established. Charged collection
plus fit210.671s; previous complete data-producing worker586.822s plus new
workers265.46/275.68s and setup must not be omitted from total investigation cost.
Reports prophecy-frozen-feature-student-v1-reports/verified-features.json;
receipt feature-student-v1-launch.json and exact source feature-student-v1-source.py.
Kaggle title-derived slug was pinned before monitoring; no duplicate launch.

Planning-student fit v1 also COMPLETE/analyzed/archived-v1. Student28325fits
in300.000s (209.731collection/90.269other), selected5000 byheldoutloss;
PPO79updates301.679s. Noisy25.000% vsPPO25.150%, return28.606/28.890,
differenceCI[-2.540,1.826]; studentstart25.000%. Gatefalse. Energy explained
train/heldout12.5/5.7% at1000,27.7/9.9% at5000,36.8/7.7% at10000,
46.0/1.9% at20000. More fitting initially helps then overfits; neither extra
fit nor a frozen-feature linear student demonstrates generalization of the
native planner's gains. Do not repeat these fit/LR variations unchanged.
Exact65,027,219-byte teacher dataset is retained remotely, SHA
7451c44bbff5ee8dc608218a33eee8ecdd5ae3b72fb714adaa9a6edd812e1b40.

Previous discrepancy tested/rejected above: model uncertainty had not been
used when selecting actions. Review MOPO/PETS primary code before a bounded uncertainty-aware
model-planning screen. First establish whether uncertainty predicts reward/
FAIL optimism for candidate actions, not merely physical state error. Then
compare unpenalized and uncertainty-adjusted candidate rankings in real MuJoCo
with original exploration, fresh heldout reset seeds, and zero-residual control.
No actor/world refitting in that screen. If it yields useful real corrections
much faster than the native planner (~43s per1024starts), use that to collect
more training examples within the same student budget and compare learned
policies. This is a route to a learning-speed test, not a planning-only win.
The completed uncertainty screen above tested this discrepancy; production PPO
is unchanged. Retain free-only and short bounded regression screens.

Available reusable model: madmad74100/prophecy-rwm-history-calibration v1,
recurrent/world_model.pt SHA
0f0c6ca2bc1b53b410350db0b2f8cdd468ae52f3e3bc98fedb9e4c14ee2e0bb9.
Its temporary shared data was removed by the original launcher after completion;
do not rely on it being retained. Published RWM GRU256x2/5heads with31past
steps+current, episode-boundary padding. Read supermimic_rwm_history.py and
supermimic_rollout_calibration.py. State-error/uncertainty correlation .475 at8
and.624 at32 is evidence ONLY about state error, not return-error calibration.
Prior326.301s warm fitting +24.322s collection +180.577s recurrent fitting
(extra diagnostics/setup separate) must be charged if this model is reused.

MOPO official source re-read/pinned e5efe3eaa548850af109c920bfc2c1ec96bf2285,
research/mopo/fake_env.py and MITlicense. Default penalty is maximum ensemble
next-state distance from ensemble mean, subtracted from imagined reward;
alternative learned variance is optional. Our RWM diagnostic's mean increment
spread is NOT the same quantity. Any adapted penalty requires units/calibration
checks and heldout evaluation; no faithful MOPO reproduction or gain claimed.
Sources https://arxiv.org/abs/2005.13239 and
https://github.com/tianheyu927/mopo and PETS https://arxiv.org/abs/1805.12114.
Heartbeat remainsACTIVE3minutes. Preserve production/checkpoints/Unreal.

CN-PPO longer confirmation v1 COMPLETE16:12UTC, analyzed/archived-v1.
Both900s seed pairs complete, actual noise/update checks pass; no regression
stop. Seed849150 white236/colored238updates,901.877/901.051s; noisy23.048/
22.673%. Seed849151 both237updates,902.793/903.589s; noisy24.399/24.700%.
Pooled2664episodes:632whitefailures versus631colored (23.724/23.686%);
difference-.0375pp, motion-cluster95%CI[-1.158,1.016]. Return31.542/31.700,
differenceCI[-1.406,1.776]. Candidate better firstseed, worse second; prospective
gateFALSE. Slightly lower curve area is insufficient to claim faster learning.
Worker elapsed includes setup/checks/saving, mean interpolated gap-.337pp;
common notebook bootstrap reported separately, secondseedcache reuse explicit.
Reports prophecy-colored-ppo-confirmation-v1-reports/verified-confirmation.json
and learning-comparison.png. Original900s gate not changed after results.
Two trainingseeds limit precision; this does not reject every noise setting.
Source/receipt archived with both normalized-text and Windows-file hashes;
launcher hashes normalized UTF-8 text, explaining CRLF bytehash difference.

SHAC target-critic v1 COMPLETE/analyzed/archived-v1; no gain. Online/target89/107
actorupdates over191.930/193.616s actual learning (310.584/309.662inclchecks).
Noisy failures27.102/27.778%, return24.039/22.801; diffreturnCI[-3.122,.564].
Det21.471/23.048%, targetworse+1.577pp CI[.303,2.849]. Both regressed initial
~24.0%noisy. TargetEMA actually updated107times, L2delta15.463/gap.580; finite,
no KL rejection. Initial warmup gate differed before intervention; no causal
precision claimed. Original code/target-critic tests passed, not a wiring failure.
Workers456.22/454.41s plus bootstrap; prior326.30s model preparation additional.
Online stopped at thirdcheck for normal noisy regression; target reached cap.
Reports prophecy-target-critic-race-v1-reports/verified-comparison.json.
Not promotion; model accuracy remains an unresolved limitation.

CN-PPO v1 COMPLETE/analyzed/archived-v1, no perturbed learning-speed advantage.
White/colored78/80actual outerupdates;303.628/302.447s learning,
323.453/321.907s with check; worker588.73/584.93s,parent705s+finalization.
Noisy failures23.423/23.649%, delta+.225pp CI[-1.205,1.432]; return31.505/31.661,
deltaCI[-1.595,2.171]. Det18.393/19.069%. Both improved slightly over initial
24.474/24.550%noisy. Normal noisy5.944/3.147% favors correlation, but this is one
short training seed and is not a perturbed-speed result. Noise audit passes:
RMS~1, lag1white.00012 versus correlated0.36035,2496/2560sampler calls;
actor deltas0.1276/0.1558. Gatefalse, not proof all correlated-noise settings fail.
Reports prophecy-colored-ppo-race-v1-reports/verified-student.json; source/receipt
archived. Original checkpoints, production and Unreal untouched.

Planning student v1 COMPLETE/analyzed/archived-v1. Genuine1000residual updates,
deltaL2=10.1207; original actor/phase/critic exactly unchanged. Four fresh planning
batches, each16candidates,19,040training teacher samples plus59,042anchors;
2,272heldout teacher samples, whole worlds. Selected1000 by heldout BC MSE.001698.
All planning/collection/fit215.576s (235.363including check); PPO76updates in
302.357s (322.614including check), actor delta.1241. Noisy failure24.024% student
versus23.123%PPO; return30.977/32.494, candidate-minusPPO CI[-3.458,.437].
Det failure19.369/19.820%; no convincing benefit. Starting student failure23.048%
noisy, so no learned speedup demonstrated. Normal300tick outcomes checked.
Workers518.20/610.10s plus bootstrap,parent729.51s. No model fitting reused.
Student reject; native planning itself succeeded on individual starts, but this
small residual BC adaptation did not generalize its gains. That distinction is
measured; multimodality/limited dataset are hypotheses, not diagnosed causes.
Reports prophecy-planning-student-race-v1-reports/verified-student.json.
Planning probe v1 COMPLETE/analyzed/archived-v1. Original policy exactly frozen,
reset errors0. Two seeds/1332perturbed episodes: noisy failure23.498->21.321%,
paired delta-2.177pp CI[-3.684,-.676]; return31.599->35.593, deltaCI[1.825,6.346].
Deterministic19.520->11.787% failures; return46.669->61.427. Both seedsnonworse.
Post32noisy failures73/73; post32meanreturn29.161->30.634, so gain does persist
beyond planning horizon. Selected residualRMS.0674;43s planning/seed, total
workers159.17/157.94s plus bootstrap,parent230s. No reused fitting.
Passes teacher-feasibility gate. This is per-state planning, NOT learned-policy
speedup; it justifies the new generalization/time comparison above.
Primary source RAI Judo CEM/SMPC-to-RL arxiv2608.12063 (read again October23).
Pinned96d6f451f482d68c903e17b223577b752319b4d1/license under research/judo.
Reports prophecy-native-planning-probe-v1-reports/verified-planning.json.
Smooth-actor v1 COMPLETE/analyzed/archived-v1. ReLU/smooth90/90actual updates
in159.97/160.59s learning (240.15/240.61with checks). Parameter deltas.0691/.0679.
Noisy failures28.153/28.228%;det23.649/23.273%. Noisy return difference95%CI
[-1.355,2.323],det[-.608,2.611]; no convincing advantage, neither improved
starting checkpoint. Reject this near-ReLU smoothing; no nativePPO promotion.
Workers434.83/434.73s,parent508s, prior326.30s preparation extra. Beta256 was
needed to preserve starting behavior; not a test of retrained fullSiLU networks.
Existing3min heartbeat ACTIVE. Fetch only COMPLETE/exact version; do not duplicate.

Failure-replay v1 COMPLETE/analyzed/archived-v1.
Frozen policies exactly unchanged;515/511 real model steps in180.49/180.50s.
Eight-tick noisy return MAE1.486->1.061;det1.133->.850. Missed imminent
failures fell46%->17% noisy, but32tick return MAE worsened6.808->8.060 noisy
and6.398->7.872det. State8NSE.03116->.03457. Fails its prospective gate;
no actor promotion. Worker355.13/357.47s,parent423s; prior326.30s fit extra.
Next: smooth actor activation ablation. Public reproductions use SiLU/ELU;
our trained actor uses ReLU. Test beta-SiLU calibrated for checkpoint output
closeness, retaining all parameters, normalizers, exploration and critic.
This adaptation is not exact public architecture reproduction. Three local
checks pass: true smooth derivative, parameter/critic preservation, beta
selection with heldout rejection. No production/checkpoint changes.

COM2 v2 COMPLETE/analyzed/archived-v2. Frozen actor delta0; shared-data/hash and
exact native reward/termination checks pass.482/273fit steps in180.63/180.42s.
8tick return MAE1.759->1.412 noisy(-19.8%),1.029->.804det(-21.9%);
32tick7.309->6.942 noisy,5.855->5.829det. State8NSE.06164->.06281.
Failed predeclared25%short-horizon improvement threshold; no actor promotion.
Aux gradient calibration worked (.5x state); full workers376.51/378.35s plus
bootstrap,parent~507s. COM2 loss computation also reduces fitting throughput.
Minor floating divergence remains (up to2real failures between frozen arms).
A rare-boundary sampling test now targets missed failures without extra FK loss.

Research update: official SuperDyno link on theknight-z.github.io points to
https://dynamics-humanoid.github.io/dynamics-humanoid/, still404. OpenReview
requires human verification; no bypass. Search-indexed paper reports harder
recovery/stepping discovery than model-free RL, but full paper remains unread.
Public SuperMimic reproductions use smooth policy activations (SiLU orELU);
our actor is ReLU. This is an untested discrepancy, not a diagnosed cause.

V1 COMPLETE/analyzed/archived under *-v1-reports and com2-model-v1-launch.json.
Same frozen policy and shared-data hashes; actual fit490/300steps in180.34/180.55s.
COM2 calculation agrees with simulator within1.08e-5m/s. Extra COM2 loss cut
8tick closed-loop return MAE1.724->.815 noisy,1.586->.930 deterministic. However
32tick error rose7.320->7.614 and5.915->6.465; state8NSE.03239->.03699 (14%worse).
V1 fails its original gate; no actor test or policy improvement claimed.
Initial auxiliary gradient was4.495x state despite scalar loss being only0.5x.

V2 changes only coefficient calibration: auxiliary gradient norm initially0.5x
state, fixed afterward, on training-only data. Same warm model/data/Adam2e-4,
8tick fitting,180s/arm; two new evaluation seeds984103/984104, det/noisy.
Prospective gate for a SHORT8tick actor trial:8tick return MAE>=25% lower in both
modes,32tick MAE<=105% of control,8tick stateNSE<=110%. This new test does not
retroactively pass v1. Five CPU checks pass; original/production untouched.
Primary rationale: GradNorm, https://proceedings.mlr.press/v80/chen18a.html,
shows gradient magnitude matters for multi-loss balance. Our fixed initial
calibration is NOT the adaptive GradNorm algorithm. Prior326.30s fitting extra.
Two free T4s,950s parent/1200s Kaggle cap. Verify actual startup after submission.

Audit exclusions: public CuboiLeo state_spec.py integrates velocities AND free
pose residuals, as our earlier IntegratedWorld did; strict integration is not a
missed fidelity discrepancy. Pinned task has no detected domain randomization
or action delay; equipment command does not alter the inspected fixed physics.
Windows download naming corrected: remote com2/* maps to local com2_model/*
because COM2 and COM2.log are reserved device names. Existing3min heartbeat active.

Termination calibration v1 COMPLETE/analyzed/archived: frozen policy/world deltas0.
Learned versus analytic32tick failure Brier score ratio.815noisy/.734det, but
expected-return MAE ratio.974/.939: fails the predeclared15%both-metrics gate.
Sampled learned failures do not improve; no actor test/promotion. Actual worlds
have minor floating reset divergence (1/3failure difference).149.75/149.31s
workers,230.66s parent; hashes verified, prior fitting extra.
Next preparation: task-aware dynamics fit targeting actual trunk COM2 velocity,
whose direction/speed defines perturbed termination. Same shared fresh replay
and warm model; compare state-only fit with additional COM2-vector prediction
loss. Weight calibrated once on training worlds; policy reward/termination and
production stay unchanged. Previous critic-gradient VaGraM ablation failed;
this uses measured physical targets, not an estimated value gradient.
The COM2 comparison above is now submitted; existing3min heartbeat ACTIVE.

RWM history v1 COMPLETE/analyzed/archived. Same shared-data hashes and frozen
policy delta0;494/442model steps over180.31/180.58s,control/recurrent. Heldout8tick
NSE.04327/.05146;32tick.02366/.02314. Recurrent uncertainty/error correlation.62
at32ticks, but real-outcome calibration worse: pooled noisy32tick return MAE
6.487/6.733,det5.163/5.579; missed failures36.4/39.4%noisy,30.9/37.1%det.
No actor promotion. Small floating-point divergence causes up to4different real
failures between frozen arms; report comparison is descriptive, not an exact
paired CI. Totalworkers325.8/328.6s; parent454.5s; prior326.30s fit extra.
Source rsl_rl_rwm pinned18eebcdd7145284c8d5eed5d8ed1a4b96c649693;32history
GRU256x2 and5bootstrapped residual heads, physicalFK retained. This adaptation's
mean prediction did not solve optimism; not a rejection of full published RWM.

Short-world v2 COMPLETE/analyzed/archived-v2: PPO/candidate49/49actual actor
updates in185.98/185.16s learning; noisy failures23.649/25.300%,det19.745/19.444%.
Noisy returns31.340/28.407; paired return difference95%CI[-5.181,-.619]. No gain,
no promotion. Setup107/108s,checks116/117s,final39s; prior326.30s fitting extra.
Matching the gate increased actor updates but did not improve real outcomes.
Fetch now requires current COMPLETE and requests its exact version; Kaggle can
otherwise return older completed outputs during a newer RUNNING version.
Subsequent RWM history/ensemble calibration is complete; outcomes are above.
Official rsl_rl_rwm pinned18eebcdd7145284c8d5eed5d8ed1a4b96c649693,
read-only sources/license/provenance under research/rsl-rl-rwm. Production intact.
v1 COMPLETE/analyzed/archived: noisy24.174/24.474%real/short,det20.345/19.970%,
45/36actualupdates,178/181s learning; intervals span0, no gain. Its32tick model
gate paused44outeriterations; v2 tests that separate limitation. No promotion.
Calibration COMPLETE: exact frozen weights; final-policy first32noisyticks
real20.12%fail versusmodel12.84%,143missed/268actual failures. Across branch
cohorts8tick return MAE1.18 versus32tick7.07. Concrete model optimism supports
short-rollout test; no speed gain claimed. Primary MBPO source reread.
Completed prophecy-model-rollout-calibration v1: frozen initial96009/finalPPO-WM
policies, same completed fitted world, real versus predicted1/4/8/16/32tick
failure/return calibration. Two new seeds, matched noise, no learning/refitting.
600s parent bound; receipt rollout-calibration-launch.json. Verify startup.
PPO-WM v1 COMPLETE/analyzed/archived: matched183/184s actual learning,
PPO/model noisy23.724/23.574%,det19.970/19.970%, returns slightly worse for model;
intervals include0, no gain. Both actor updates/deltas verified. Prior326.30s
model preparation extra. Next action depends on measured rollout calibration.
PPO-WM control prophecy-ppo-world-race v1 submitted11:59UTC; bootstrap/source
and checkpoint hashes/both actual GPU workers verified54.22s.
Both actual actor update paths verified; candidate first204.71s, native40
minibatch steps, L2delta.011207, KL.006186. Completed outcomes above.
Native PPO on real versus learned32tick rollouts, two free T4s,300s/arm with75s
real checks; parent1000s bound. Same96009/task/Adam/noise/phase/KLguard. All
imagined transitions detached; no dynamics derivative reaches actor. Three CPU
boundary checks pass; original files/production preserved. No paid compute.
Policy-direction v1 COMPLETE/archived: actual signed updates restored exactly;
model KL.05 positive noisy22.072->22.297%,det18.769->18.318%, intervals include0.
No reversed-gradient conclusion or verified gain. Earlier-policy comparison also
failed: PPO/model noisy23.574/24.099%; model returns worse after~237--241s learning.
Existing3min heartbeat ACTIVE. See topic for authoritative job and accounting.
Completed frozen audit proves earlier headroom: noisy first-episode23.12%
versus6.46% mature; continuous26.19/7.20%. Both model deltas0. No catastrophic
hidden reset effect. Normal120tick screens truncate300tick episodes; full noisy
normal failure~4.1--4.4%, versus1.57% short. See topic for exact accounting.
AWRv2 complete/archived, no gain (equal241s PPO/AWR noisy6.156/6.682%).
v4 C51+TD3BC COMPLETE/rejected, archived/analyzed:115actorsteps after51.46s
warmup, noisy failures6.306->66.366% by71.54s; PPO6.306% at62.39s.
Normal rows collapsed too; phase-only explanation insufficient. No promotion.
Existing3min heartbeat active. v3 COMPLETE/rejected,
archived: matched180s noisy failures99.399%C51 versus6.306%PPO, det98.423/4.054%.
Actual793actorsteps verified; no promotion. Qfit quality did not imply policygain.
Sources audited; original checkpoints/production untouched. No paid compute.
Direct tracking-gradient test COMPLETE/rejected:53/55updates,197.4/192.8s
actual learning; PPO/candidate noisy failures6.231/7.658%, det4.204/4.805%,
returns also worse. Capacity/full-phase/stochastic-full also rejected.
Existing3min monitor active. Free only, production/originals preserved.
See Labs/MimicKitTraining/SuperMimicExperiment.md for authoritative job,
recipe deviations, timing accounting and next action.

Previous completed confirmation:
Final phase confirmation v1 COMPLETE about01:28UTC; four workers and downloaded
reports verified. At~486--488seconds actual learning per arm, fixed phase/PPO
noisy failures6.68/7.66% for seed92719 but6.23/6.23% for38147; deterministic
3.75/4.05% then4.35/3.98%. Initial promising result did not replicate reliably.
All actors actually updated128--132times; no failure-rate interval excludes zero.
Tested model-based refinements and advantage-cap change also gave no repeatable
policy-learning advantage. Retain production PPO; no experimental promotion.
Source/CP119475 preserved; production trainers untouched. No paid compute.
No active experiment or new job queued; monitoring heartbeat PAUSED via app.
See Labs/MimicKitTraining/SuperMimicExperiment.md for outcomes, timing and limits.

Previous comparisons:
Free Kaggle H4/H16 accepted70/41updates in184/181seconds including checks.
Matched noisy failures6.53->8.48/7.06%; both seeded initial observations match.
Real forward error0 and actor deltas verified. Exact-reward audit v2 now passed:
local action directions improved actual reward85â€“100% of matched test rows.
H32 exact pilots complete: small step noisy failures6.456->6.306% (not significant),
large step13.063% (rejected). Short-exact H1/H4 at large LR also regressed and
stopped at first check. Small-LR learned/analytic failure variants also regressed
to7.43/6.91% noisy failures; refitted/frozen dynamics8.26/10.36%, no win.
Phase derivative ablation also failed; it was not a sufficient cause. Completed
free exact-critic-race v1,21:57UTC: unchanged PPO versus H16 exact-score method
with real-transition/EMA critic,300s incl90s checks. Startup and both actor
update paths VERIFIED; critic is fitting real transitions. Actual reward and
termination unchanged. No learning
improvement established in that earlier comparison. Heartbeat is now paused;
production untouched. See SuperMimicExperiment current.

Previous noisy PPO/model race: free Kaggle
prophecy-supermimic-noisy-race v1,20:23UTC, startup and both workers verified.
180seconds each, native PPO versus stochastic H1/real-critic model training;
matched real-MuJoCo checks with and without exploration. Prior one-step v2
finished160updates each but4.58/4.95% failures versus original4.20%, no win.
User authorized continued overnight free testing and primary-source research;
heartbeat active, no production changes. See SuperMimicExperiment current section.

Previous one-step pilots v2: retry20:01UTC
returned BOOTSTRAP_STARTED at0.8s. Stalled v1 canceled after authenticated browser
inspection; v2 session361242531 uses compact verified warm-model input. Same
short tests; monitor actual logs, never treat RUNNING alone as startup proof.
Cautious3minute tests still regressed. Direct simulator audit found H1 action directions more
accurate than H4, but improvements mainly raise critic estimates, not immediate
reward. Free Kaggle prophecy-supermimic-one-step-pilots v1 compares imagined
critic fitting versus real-transition fitting plus slow target critic,180s each.
Original119475 policy and saved world model; early regression stops/live logs.
Follow-up heartbeat active every10min; production untouched. See experiment
topic for current job, audit limitations and source receipts.
See Labs/MimicKitTraining/SuperMimicExperiment.md current section.

**October22 first SuperMimic comparison â€” COMPLETE, adaptation failed:** isolated
free Kaggle two-T4 comparison from locomotion init119475,30min per worker.
Real-MuJoCo final perturbed-loco failures4.17% PPO versus62.99% adaptation;
normal-loco0.087% versus80.16%. Both finished with finite metrics, identical
checkpoint/reset observations and real experimental actor updates. Large
pre-clip gradients accompanied regression. This is our adaptation, not official
SuperMimic code. Do not promote experimental weights. Production untouched;
no further run launched. Reports/curve retained under Saved/MimicKitSuperMimic/.
See MimicKitTraining and Labs/MimicKitTraining/SuperMimicExperiment.md.

**October22 curated checkpoint prepared:** user requested pushing current work
before switching to UI. Includes current source/tests/tools/docs, saved PoseAgent
and A_Sword, required physical-mesh Python label helper, and current lightweight
MimicKit/Sound Studio source. TestNN's local modification, generated models,
environments, full captures/diagnostics and unrelated PDF remain local. No editor
mutation or new build for this checkpoint. Recovery inventory regenerated from
the staged tree; Git history/remote identify the final checkpoint. See Recovery
opening for external dependencies and scope.

**October24 Sound Studio â€” UPDATED/VERIFIED:** independent native Windows WAV
editor at `Labs/SoundStudio`, desktop **Prophecy Sound Studio**. Default source
`Documents/Sounds`, target `Documents/Sounds Mixed`; editable export name, unique
numbered files, source/target lists, double-click remix with all controls reset.
Large frequency-coloured spectrum/waveform with always-visible EQ sliders and
draggable frequency/gain points. Outer L/H now hold their gain to the spectrum
edges (no bell recovery), with bottom CUT=zero and exact0dB snapping. Shared
padded zero-phase response drives sound/curve. All five sliders, numeric controls
and graph handles now reach CUT; middle bands no longer clamp atâˆ’12dB. Middle CUT
zeros the selected centre frequency while retaining the deepest bell's poles for
a smooth final step. Graph samples exact centres and shares audio coefficients.
Playback measures a local FFT at the audible
DAC-clock position and scrolls a two-second waveform. EQ curves follow sliders
immediately;25ms scheduling starts previews during dragging, with completed
intermediate audio while latest settings catch up (curve/controls never roll back).
In-process float64 RBJ EQ/low-cut,128MiB bounded intermediate cache, batched visual
analysis and low-latency device mode replace repeated subprocess/pitch work.
Cached/fresh renders match samples; pitch remains offline R3 quality. Fireplace
EQ with existing pitch:1.3â€“1.4s processingâ†’76â€“80ms; measured audible updates~.19â€“.29s.
Audio publishes before whole-clip visual analysis; no playback stop/reset. Paused edits preserve pause and position. Loop defaults on; Space
pause/resume and Left/Right250ms seek override focused sliders/text/lists/dialogs.
One Play/Pause button plus Play original checkbox now replaces dual transport
buttons. Bypass auditions the full untouched source, keeps edits/export settings,
and swaps buffers without stopping; paused state/time retained. Bypass defaults
off on new sounds and survives app refresh. Hover popups removed. View fixed64Ã—
and listening100%, both controls removed.
Bottom-left Refresh app loads newest local code in a fresh process, retaining the
current WAV/edit/name/folders/layout; playback stops. User operates Refresh app;
do not click it or restart their running app to install routine edits. Pending work drains before
lock release/relaunch. One-use snapshot consumed; actual newPID restart verified.
Defaults now neutral: zero fades, effects/normalization/protection off, source
rate/PCM-float format and decoded samples preserved without added dither. Explicit
48kHz/16-bit dithered export and optional estimated true-peak protection remain.
Independent offline R3 pitch/speed, trim, EQ, reverb tails, local polish/denoise.
Compression slider beside Polish/Gain defaults Off and resets with each sound.
0â€“100% drives a linked-stereo downward compressor (peak-relative threshold0â€“30dB,
ratio1â€“8, attack10ms/release120ms, no makeup gain). Runs after cached wet effects;
dragging reuses pitch/EQ/reverb, updates audio/waveform during playback and preserves
pause/time. Refresh/recipe/export include amount; Play original bypasses it.
Measured fireplace slider-to-device updates~.21â€“.28s with pitch/reverb, no underruns;
1280/1520 layouts inspected. Receipts Saved/Diagnostics/SoundStudio20261024/compression-*.
Dedicated `Saved/SoundStudio/env`; matching shortcut/process AppUserModelID and
native icons.51 signal/UI checks passed, including compression dynamics/stereo/off,
cache/export/drag/reset/refresh/bypass, middle deep-cut audio/graph
agreement, actual slider/graph drags to CUT and neutral reset, filter-reference precision,
cache sample equality/invalidation/bounds, updates during dragging, single-button/original bypass
with retained edits/stream/pause, refresh edit restoration,
outer-cut signal/graph parity,
mouse CUT/neutral access, actual muted Windows playback,
focus priority, pause/seek/loop, continuous stream during EQ/rate/channel changes,
neutral sample-exact exports, live FFT/envelopes, filter parity and safe exports.
Actual fireplace WAV hash unchanged; live/paused screenshots and measurements in
`Saved/Diagnostics/SoundStudio20261022/transport-*`. No Unreal/assets/training changes.
[Workflow, research and limits](Labs/SoundStudio/README.md).

**October22 shared pelvis speed threshold corrected â€” RUNNING:** user requires
max of both get-up peaks for all perturbed rows, since front can roll into back.
Shared149.516cm/s replaces per-motion limits. Resumed latest130296 as
20261022_131128_uefn_getup_pelvismax7_1024, same L4/1,024agents until stopped.
Fixed loss weight recalibrated7%; all18perturbed replay rows share threshold.
New backup/reward/progress verified130307,~15.15k transitions/s. See training
journal opening and getup-pelvis-max receipts. Other settings/loco unchanged.

**October22 local idle push viewer â€” ready/paused:** http://127.0.0.1:8850/ .
Frozen latest-at-capture locomotion checkpoint0122776, one local CPU agent with
real idle inputs, native240Hz physics/30Hz policy. Limb selection, directional
mass-independent velocity kicks, strength control, reset and pause. Pause/hide
stops simulation and continuous drawing. Verified30.18updates/s and equal1m/s
kicks across hand/foot/pelvis. No cloud/training/Unreal changes. Restart with
Labs/MimicKitIdleLive/start.ps1; see its README and MimicKitTraining opening.


**October22 per-arm grab independence â€” INSTALLED/VERIFIED:** Joint
Independance0..1 on Grab Object/Bone plus per-hand live Set/Get nodes. Reuses only
the isolated projection experiment's constraint solver; other special-attack
features remain isolated. Live Coding new cross-module imports failed; authorized
normal incremental build30actions269.60s passed, all normal DLLs current. Isolated
headless TestNN:174native checks pass; held clavicle alpha0/.25/.5/1/0 preserves
physical joint identity, right setting.75 unchanged. Three existing grab nodes
refreshed/saved, other wires/tuning identical; reflection/status healthy. Editor8096
closed cleanly, current M_JoltTransferFailure already saved. Test process exited;
interactive6904 verified on that map, Play off/dirty[], all4API signatures loaded.
See ReachGrasp opening and GrabIndependence
receipts; Tools/ReachGrasp/GrabIndependence.py / TestGrabIndependence.py.

**October22 recovery horizontal pelvis speed cost â€” RUNNING:** resumed latest
129835 on same L4,1,024agents until stopped. Run20261022_124925_uefn_getup_pelvis7_1024.
Perturbed/perturbed+ only: squared excess above front0.473/back1.495m/s reference
peaks, fixed weight calibrated7%. Verified XY horizontal/Z vertical and pelvis
origin vs COM; pure vertical speed contributes zero. New backup/replay/TB and
129846progress verified (~15.1k transitions/s). Existing foot/AE weights and
normal/loco/physics unchanged. See MimicKitTraining opening and pelvis receipts.

**October22 recovery foot penalties â€” RUNNING:** resumed latest129347 on existing
L4 0to3wg3r3n926h,1,024 agents until stopped. New run
20261022_122519_uefn_getup_feet7_1024 adds ankle target-velocity and idle-relative
foot rotation costs to perturbed/perturbed+ only, fixed weights calibrated to
7% EACH. Normal/loco/physics unchanged. Latest checkpoint locally/S3 preserved;
new backup, advancing129358 and replay/TB terms verified (~15.2k transitions/s).
See MimicKitTraining opening and getup-foot calibration/verification receipts.

**October22 clavicle grab fixed â€” loaded/verified:** correct Self/closest-agent
wiring was rejected by StartGrab's fixed4cm open-finger clearance cap. Replaced
that cap with a collider/hand geometry bound, one-time admission work only.
Live Coding1action161.75s, reload10:46:44UTC. Exact current TestNN owned PIE:
BP starts at absolute30, reaches by60, grips by90 and holds through180. No tuning,
wiring, save or restart; dirty agent BP/TestNN preserved, owned Play ended.
Slow startup is existing sword Start Slow FPS=true/Slow FPS=5; removal of its
EndPlay reset now preserves that cap. Startup values unchanged. Normal DLLs
remain stale. See ReachGrasp opening and GrabDefaultsSelf diagnostic receipts.

**October22 all grab nodes default Self â€” loaded/saved:** added DefaultToSelf Agent
to Grab Object/Bone, Release Grab, Get Grab Status, Set/Get Grab Angle Tolerances.
Explicit overrides remain supported. Runtime/editor Live Coding4actions314.31s,
reload10:25:37UTC. All6metadata entries verified;4existing nodes refreshed and
agent BP saved. User had already removed GrabBone304's incorrect Agent link;
it now defaults Self, target Mesh and automatic surface selection preserved.
Graph unchanged except object/Object FName casing; BP types/status healthy.
No Play/restart or retained layout changes. Tools/ReachGrasp/GrabDefaultsToSelf.py
and GrabDefaultsSelf receipts. Normal DLLs remain stale; see ReachGrasp opening.

**October22 sword End Play FPS reset removed/saved:** deleted fixed60 and
t.MaxFPS60 reset nodes from A_Sword End Play, so HideSword/destruction no longer
changes global clock. Exact graph comparison confirms only those two nodes and
their exec links removed. Existing startup/RMB debug controls unchanged. Saved
A_Sword only; TestNN remains dirty, no Play/restart. Editor helper1action80.60s,
reload09:50:55UTC. Normal DLLs remain stale. Tools/SwordHolster/RemoveEndPlayFPS.py,
Saved/Diagnostics/SwordEndPlayFPS/verification.json; see SwordHolster opening.

**October22 Grab Bone optional surface point â€” loaded:** new visible Use
Surface Point bool, default true for compatibility. False ignores supplied point
and uses Grab Object's automatic collider selection toward the upper arm.
No retained layout change. Runtime3actions162.05s; editor refresh helper1action
119.54s (after compile correction), reload09:39:31UTC. Current node refreshed,
all existing graph wiring/defaults verified unchanged, agent BP saved. No Play
or restart. Tools/ReachGrasp/UpgradeGrabBone.py and GrabBoneSurface receipts.
Normal DLLs remain stale. No FPS behavior changes: diagnosed HideSword destroys sword and
A_Sword EndPlay unconditionally restores60FPS; current Grab Bone also had the
victim wired as grabber (self-grab rejection). See ReachGrasp topic opening.

**October22 physical mesh getter renamed:** Blueprint display name is now Get
Physical Mesh for all instances of native GetPoseReferenceMesh. Serialized
identity/wiring unchanged. Existing editor Python startup reapplies the label;
Tools/ReachGrasp/RenamePhysicalMesh.py reapplies after any future Agent reflection
replacement. Verified all3TestNN agents return PhysicalMesh. No build/restart,
graph edits or saves; user dirty agent BP/TestNN preserved. Normal DLLs remain
stale from preceding tasks. See ReachGrasp topic opening.

**October22 closest-agent node â€” loaded:** added pure Get Closest Agent
in existing Reach library, Prophecy|Agent category. Same-world3D actor-position
distance, excludes self/destroying agents, returns None when unavailable. No
retained state or background work. Dirty BP_ProphecyManualPoseAgent preserved to
disk before reload; previous saved bytes in Saved/Diagnostics/ClosestAgent.
Live Coding3actions178.65s, reload09:18:36UTC. Verified correct nearest-other
references for all3TestNN agents and None input; Blueprint types healthy after
compiling the dirty agent BP. TestNN consequently dirty, left unsaved. No Play,
restart or wiring edits. Tools/ReachGrasp/VerifyClosestAgent.py and diagnostic
verification.json retain the check. Normal DLLs remain stale. See ReachGrasp topic.

**October22 recovery resumed after funds outage:** latest127054 locally verified;
replacement L4 0to3wg3r3n926h, $0.59/hour until stopped, exact existing1024-agent
settings. Run20261022_104951_uefn_getup_perturbed_plus_1024 advanced127055->127065,
15.49k transitions/s; new persistent backup/replay/TB verified. Old retained pod
upszb03gy35fzj remains stopped. Locomotion independently resumed by its own chat;
both current TB streams verified. See MimicKitTraining opening and recovery
funds-resume-verification.json. Supersedes prior recovery running-pod status.

**October22 locomotion resumed after funds shutdown â€” RUNNING:** latest119475
(2,409,365,504samples) locally/persistently verified, optimizer/normalizer restored.
Old L4q764mqd40pabiq unavailable after Runpod shutdown; retained disk preserved.
Replacement L4leuh8va7hfcevy,$0.59/hour,1,024agents until stopped, exact previous
settings/source. Run20261022_104557_uefn_locomotion_pelvis_velocity5_1024,
verified119476->119486 and first backup. TB10-45-57, bridge/dashboard publishing.
Recovery unchanged. See MimicKitTraining opening and funds-resume-* receipts.
Supersedes locomotion status below.

**October22 reach/grab pelvis floor â€” loaded:** minimum commanded pelvis height
is now40cm vertically above the root, replacing the animation-relative72cm drop
cap. New Set/Get Reach Minimum Pelvis Height Blueprint nodes allow per-agent
live overrides for both hands. Candidate body solve applies the floor before
arms/legs; no extra solver iterations or retained-state layout changes.
Isolated kernel21cases/2520frames passed. Live Coding4compile actions338.41s;
reload08:11:45UTC, nodes/default and Blueprint types verified. Editor8096 remains
TestNN/outside Play, dirty[], no asset/wiring edits. **Normal DLLs stale: normal
incremental build before next cold launch.** Lab untouched. See ReachGrasp topic
opening and Saved/Diagnostics/ReachPelvisHeight/ receipts.

**October22 TestNN reopened:** editor8096 verified on /Game/testNN.testNN,
outside Play, no dirty packages. Existing normal DLLs current; no build or
asset edits. Startup rebuilt missing engine-material shaders before opening.

**October22 locomotion TB refreshed:** local observers restarted; missing event
history restored through2.324B samples, live cards verified17seconds old. Current
run23-17-29 selected. L4 training remained uninterrupted at~19.25ktransitions/s.
Dashboard skips unnecessary replay scans when full-batch counters are available;
bridge polling30seconds,TB cap10unchanged. See MimicKitTraining opening and
Saved/MimicKitLocomotion/tb-refresh-20261022.json.

**October22 scheduled perturbed+ switch â€” RUNNING:** resumed latest recovery
113353_final (2,076,229,632 samples), locally SHA256-verified and persistent,
as 20261022_013025_uefn_getup_perturbed_plus_1024 on same L4 upszb03gy35fzj,
$0.59/hour until stopped. 307 normal /359 ordinary perturbed /358 perturbed+;
plus179 front and179 back. Root linear and local joint velocities use two
different random locomotion frames; independent isotropic spin magnitude uniform
0â€“700deg/s. Plus head50% failure begins tick100; ordinary stays80. Other settings
unchanged. GPU reset checks passed, advancing113354->113364 at early14.96k
transitions/s; first backup readback verified. Replayer20rows includes9 correctly
labelled perturbed+; TB/bridge publishing. Schedule paused after completion.
See Docs/MimicKitTraining.md and getup-plus-verification.json. Supersedes scheduled
entry below. Locomotion branch untouched.

**October21 pelvis velocity MSE x5 â€” RUNNING:** pelvis-only 3D linear velocity
contribution multiplied by5 on every locomotion-branch row (normal/perturbed,
idle/loco), retaining body mean and AE/MSE handoff. Latest99574_final
(1,757,249,536samples) locally/persistently verified and resumed as
20261021_231729_uefn_locomotion_pelvis_velocity5_1024, sameL4q764mqd40pabiq,
1,024agents,$0.59/hour until stopped. Verified99575->99585 at18.56ktransitions/s,
first backup verified, actual20row replay confirms new weighting. Other losses
and recovery branch unchanged. TB23-17-29; see MimicKitTraining opening and
Saved/MimicKitLocomotion/pelvis5-* receipts. Supersedes loco status below.

**October21 recovery perturbed+ switch scheduled:** in two hours, approximately
October22 01:16 Europe/Warsaw, resume latest with half the perturbed rows assigned
new initial velocities. Root linear velocity and local joint velocities come
from two different random locomotion frames; independent random 3D spin has
uniform magnitude 0â€“700 deg/s. Only these rows delay the 50% head-height failure
check from tick80 to100. Other settings unchanged. Implementation is scheduled,
not yet deployed. Plan Saved/MimicKitEquipment/perturbed-plus-switch.json;
heartbeat switch-half-of-perturbed-get-ups-to-perturbed. Preserve loco branch.

**October21 speed-loss TB card fixed:** dashboard whitelist omitted the already
logged loss/extremity_speed_excess. Added mapping, backfilled31points exactly,
restarted local dashboard only(PID2912), ongoing updates enabled. Trainer/GPU
uninterrupted. TB22-48-04 filtered to new card; see MimicKitTraining opening.

**October21 locomotion soft speed loss â€” RUNNING:** both hard speed-limit tries
stale. Restored pre-change98733_final(1,729,691,648samples), optimizer/normalizer
included. Keep150%foot/hand thresholds; idle uses walk backward. Speed no longer
terminates: squared excess cost with fixed3.20399479weight, calibrated to15%of
existing loss on violating frames. COM2 conditions unchanged. New run
20261021_224804_uefn_locomotion_speed_loss_1024 on sameL4q764mqd40pabiq,
1,024agents,$0.59/hour until stopped. Verified98734->98754,18.53ktransitions/s,
new backup verified; replay15overspeed frames continue and reward matches cost.
TB22-48-04. Recovery untouched. See MimicKitTraining opening and speed-loss receipts.
Supersedes hard speed termination entries below.

**October21 locomotion speed limits both150% â€” RUNNING:** feet raised135->150%,
hands unchanged150%, idle still uses matching walk backward. Latest99151_final
(1.743B) locally/persistently preserved, resumed20261021_221827_uefn_locomotion_extremity150_1024
on same L4q764mqd40pabiq,1,024agents,$0.59/hour until stopped. Verified99152->99172
at18.47ktransitions/s, first backup verified. TB22-18-27. Only speed-reference
artifact changed; recovery unchanged. See MimicKitTraining opening and speed150 receipts.
Supersedes earlier locomotion135%foot limit below.

**October21 persistent replay/checkpoint cleanup completed:** user approved deleting
the 468 intermediate physical UEFN checkpoint archives containing old replays.
Deleted exactly that list: 21,375,033,969 bytes (21.38 GB). Verified every deleted
key absent and all 14 protected latest/final saves present, including newer saves
found during execution. Training was not interrupted; local files, datasets,
source packages and TensorBoard logs untouched. Receipt:
Saved/MimicKitEquipment/replay-cleanup-20261021/completed.json.
This was a one-time cleanup, not a change to automatic retention.

**October21 locomotion extremity-speed limits â€” RUNNING:** perturbed rows fail
above135%foot/150%hand reference maximum in moving pelvis frame; idle uses
matching walk backward. Latest98733_final locally/persistently preserved;
resumed20261021_220225_uefn_locomotion_extremity_speed_1024 on replacement
L4q764mqd40pabiq,$0.59/hour,1,024agents until stopped. Verified98734->98754,
18.44k transitions/s, first backup readback verified. Replay5speed crossings
all terminate at first eligible tick. TB22-02-25. Initial startup table-shadowing
bug fixed/tested; old A40 stopped and unavailable. Recovery unchanged.
See MimicKitTraining opening. Supersedes loco status below.

**October21 locomotion perturbed idle pose MSE x5 â€” RUNNING:** position and
rotation only, perturbed ordinary idle only, across early MSE/handoff/full MSE.
Existing early coefficient0.01062843 retained; AE/velocities/normals/loco and
recovery untouched. Resumed preserved97272_final (1.682B samples) as
20261021_205453_uefn_locomotion_perturbed_idle_pose5_1024, same A40,$0.59/hour,
1,024agents until stopped. Advancing97273->97283,early14.0k transitions/s;
new backup persistent-verified. TB20-54-53. Scope tests and receipt details in
MimicKitTraining opening; Saved/MimicKitLocomotion/idle-pose5-*.
Supersedes earlier locomotion status below.

**October21 perturbed get-up jump termination â€” running:** pelvis worldZ
>=93.457782cm fails from tick6; first5ticks exempt, normals untouched. Existing
100failure cost/no success bonus. Latest104663_final locally/persistently
preserved, resumed20261021_200623_uefn_getup_pelvis_ceiling_1024 on sameL4,
1,024agents/until stopped. Verified104674 at~15.31ktransitions/s,backup and
11actual replay jumps terminated on first eligible crossing with penalty.
Previous success gates/all other settings retained; locomotion untouched.
See MimicKitTraining opening and pelvis-ceiling-verification.json.


**October21 locomotion early MSE+AE RUNNING:** user-requested added MSE
shares the AE fade: (1-mix)*AE + [mix+0.01062843*(1-mix)]*bodyMSE,
30ticks early/30ticks handoff. Calibration matches mean early costs~0.299 each;
late MSE, normals, physics/optimizers unchanged. Resumed preserved96009_final
(1.640B samples) on same A40wjxv6qigq3dy9o,$0.59/hour until stopped,1,024agents.
Run20261021_200213_uefn_locomotion_ae_earlymse_yaw180_1024, TB20-02-13.
Advancing96010->96020,early14.3k transitions/s,new backup persistent-verified.
Recovery untouched. See MimicKitTraining opening and early-mse verification
receipts in Saved/MimicKitLocomotion. Supersedes earlier locomotion status.

**October21 optimisation cleanup / TestNN reopen:** recycled disposable
Intermediate/PikeJointLab (3,985,596bytes); source and benchmark receipts kept.
Optimised diagnostics only11.318MiB, no large dumps from this arc. Map switch
hit Unreal's old-world GC fatal: Python retained /Game/explosionVFX Package.
All assets saved/no Play before switch. Inspection scripts now use function
scope; cut capture releases world references on finish. Never keep editor
actors/packages in remote Python globals across map loads. Incremental normal
build succeeded (10actions,251.60s); normal DLLs now current. Recycled today's
27 obsolete Live Coding patch files (479.34MiB) after build/before launch.
Editor27876 verified on /Game/testNN.testNN, outside Play, no dirty packages.
Total recycled483.14MiB; retained small diagnostics, benchmarks and source.

**October21 perturbed recovery success tightened / running:** exact screenshot
rollout103985 gives feet threshold13.034895cm and |head vertical speed|<2.103453m/s,
in addition to head>90%idle height. Both feet must pass; body-origin worldZ.
Latest104197_final saved locally/persistently before same-L4 restart as
20261021_194738_uefn_getup_success_gates_1024,1,024agents,until stopped.
Verified104208 at~15.85ktransitions/s, new persistent backup, all6recorded
successes satisfy new gates. Other settings unchanged; locomotion untouched.
See MimicKitTraining opening and success-gates-verification.json.


**October21 current head-pike entry fixed before requested backup:** Optimised
was recentering the accepted contact6.221cm onto the blade centreline, causing
an upward solver kick. It now retains the pike's transverse contact offset at
the hilt plane. Ten exact-prefix samples; first post-contact deviation from
legacy4.751deg ->0.019deg. Stain reaches1; withdrawal removes joint/cut/NS at
0.35s. Current fixture transient hilt overshoot4.945mm (earlier0.432mm belonged
to a different approach). No BP/scene tuning edits. One implementation compile
119.98s, Live Coding loaded17:09:35UTC, no restart; normal DLLs remain stale.
Owned Play ended; latest user A_Sword/map edits saved for the requested backup.
Curated snapshot targets codex/standalone-sim: scripts/source/docs/config plus
all346 Blueprint/Niagara/ControlRig assets and lightweight supporting assets.
No new LFS pointers or files over25MiB; bulk meshes/textures/animation libraries,
VDB volumes, training checkpoints and generated diagnostics excluded. Remote
push receipt lives in Saved/Diagnostics/Backup20261021 after verification. See
[current correction and evidence](Docs/OptimisedSwordCuts.md).

**October21 Optimised sword cuts â€” saved, loaded and tested:** A_Sword has
instance-editable Optimised=true (select before Play); false retains old BP path.
User-confirmed velocity cut dampings, easier withdrawal, matter0-only frame5
depth cap, and one-time accepted-slash width overshoot correction implemented.
Native travel releases cuts/NS; flesh pikes publish progressive blade stain.
Slash plane/swing3x3 solve leaves twist free; hard blade limits solved in existing
iterations. Wall width2.779678cm held; cube cap frame5/natural ejection0.68333s;
head pike NS/stain1.0/withdrawal cleanup pass, hilt residual0.432mm.3976 original
pins compared/nine expected changes. Only A_Sword saved, map hash unchanged.
Editor21708 explosionVFX stopped/no dirty packages. Normal layout build/restart
completed earlier; final implementation-only plugin patch33.21s loaded16:52:35UTC.
Normal DLLs stale: incremental build before next cold launch. Standalone100-cut
world~0.45â€“0.73ms physics CPU, not an Unreal FPS comparison. Shared opted-in pike
hard-stop correction also tightened; ordinary joints unchanged. See
[implementation, measurements and exclusions](Docs/OptimisedSwordCuts.md).

**October21 locomotion RUNNING with1,024 agents:** user-selected resume from
preserved production91895_final (1.506B samples), not sweep weights. New A40
wjxv6qigq3dy9o at$0.59/hour until stopped; L4 unavailable. Run
20261021_171453_uefn_locomotion_ae30_mse30_yaw180_1024. Settings unchanged except
agent count; pinned512-only startup gate corrected. First attempt failed before
training and stopped billing automatically; corrected run advances91896->91906,
early13.6k transitions/s. First checkpoint persistent-readback verified. Both
optimizer states/normalization restored. Recovery stays stopped. TB17-14-53;
Saved/MimicKitLocomotion/worlds1024-live-verification.json; topic opening has
source/backup/setup details. Supersedes stopped-production statements below.

**October21 recovery resumed with1,024 agents:** latest99984_final retained;
new20261021_171139_uefn_getup_ae10_1024 on L4upszb03gy35fzj/$0.59hour,
until stopped. Optimizer/normalizer restored; other training settings unchanged.
Verified99985â†’99995 (~15.15k transitions/s early), persistent backup and replay.
Removed obsolete equipment512-agent launch restriction after first attempt
stopped automatically before training. Original/replacement retained pods
unavailable; both stopped. Locomotion untouched. See MimicKitTraining opening
and Saved/MimicKitEquipment/getup1024-verification.json.


**October 21 isolated locomotion sweeps â€” finished; GPU stopped:** ten
configurations screened from protected checkpoint91895_final. No verified
learning-speed winner: rollout64+LRx2 gave27.40% failures versus baseline27.67%,
within evaluation uncertainty. 1,024 worlds processed transitions1.68x faster,
but evaluation velocity/observation hashes differed; learning result excluded.
User requested wrapping up; longer confirmation cancelled without a completed
comparison. Separate A40a9y7igarhig19j confirmed EXITED, estimated GPU cost$1.14.
All seven production checkpoint/source/control files rehashed unchanged. Both
production branches stay stopped; no settings promoted. Evidence and stop/
backup receipts: Saved/MimicKitLocomotionSweeps/20261021. Final research/report:
Saved/MimicKitLocomotion/research-20261021/results.md. See topic opening.

**October21 first wound ray â€” fixed, saved and tested in current head-pike scene:**
NS_bloodwound Fountain001 now uses wound-only synchronous CPU collision copies;
trace multiplier1 instead of5. Local space, speed, lifetime and other emitters
unchanged. Stock asynchronous hits were stale by the paint callback: original
1cm retrace missed100/100 sampled first-emitter exports; fixed100/100 hit head.
First stamp at0.283333s, three game ticks after head pike at0.233333s; first-only
normal callback and full two-emitter test agree. Visible head stain verified
against same-view BloodIntensity0 capture. Temporary wider retrace removed;
A_DecalManager keeps +/-1cm, scalar pin repaired/compiled/saved. Only wound NS,
two companion modules and manager saved; A_Sword user edits remain dirty.
Owned tests ended, explosionVFX open, no restart. Editor helper Live Coding
loaded (API/link repair retries; final installer guard build109.16s); normal editor DLL stale before
future cold launch. Runtime uses saved Niagara assets, no native tick hook.
See Docs/BloodExperiments opening and compact Saved/Diagnostics/WoundRay evidence.

**October21 recovery stopped / latest preserved:** user requested download then
stop. Final99984 at1,638,154,240samples verified locally and in persistent storage;
L4w9aq90rzkg1d0g confirmed EXITED. Prepared recovery resume pointer updated.
Final TB/replay synced; recovery bridge stopped. Locomotion untouched (its pod
independently reported EXITED). See Docs/MimicKitTraining opening and
Saved/MimicKitEquipment/stopped-latest-20261021.json. Supersedes running entry.


**October21 locomotion STOPPED by user:** final91895 checkpoint downloaded
and SHA/ZIP verified locally, preserved in persistent storage. L4rjsan0uitu03qd
confirmed EXITED; GPU billing stopped, local observers/active marker cleared.
Saved/MimicKitLocomotion/preserved-latest/20261021_091005_uefn_locomotion_ae30_mse30_yaw180_512/checkpoint_0091895_final.zip.
Recovery branch untouched. See MimicKitTraining opening and user-stop receipts.

**October21 original arm-pike scene placement restored/saved:** user requested
the problematic arm-hit setup again. Only A_Sword1 actor placement restored in
explosionVFX: position(2007.955873660,172.688569383,171.148856237)cm, original
rotation/actor scale retained. Mannequin already matches CleanPike saved-map
reference exactly. Reconstructed launch using old map start plus constant offset
between CleanPike and PikeSlide recordings; all15 precontact samples agree within
2.274e-13cm. Saved map only; current BPs, correction toggle and tuning untouched.
No Play started. Small reference-map copy loaded without opening/replacing current
scene, then unloaded/deleted. Receipt Saved/Diagnostics/PikeSlide/restored-scene.json;
Tools/SwordHolster/RestoreArmPikeScene.py. Historical arm hit was upperarm_l,t0.266667.

**October21 coupled pike solver â€” built, loaded, measured:** replaces unswept
post-Step sword teleport with a per-joint five-row physical solve of transverse
motion and rotation, inside Jolt's normal iterations before contacts. Existing
Set Pike Wound Correction node/tag retained; only marked hard X/Y+angular locks
with Z free/limited qualify. Stock axial motor/limit and reaction/break reporting
retained. No iteration override, new scans, mass overwrite or collision-filter
change. Native case rejects unsupported constrained body axes/singular mass matrix
while retaining original joint. Old broad Python preview absent after restart.
**Saved A_Sword node Enabled is FALSE (user setting), preserved.** User must tick
it to try the new solve; no BP/map/tuning saves or wiring edits in this task.
Exact restored arm comparison: same15-frame precontact prefix/upperarm_l hit at
0.266667s;74 joint samples. Off peak lateral5.223108cm/RMS2.339469cm/rotation44.3044deg;
on peak.0751295cm (0.7513mm)/RMS.0119437cm/rotation.684620deg. Both owned captures
ended; no user Play stopped. Independent blade/wall and spin fixtures retain wall
blocking; strongest tested contact leaves~3mm transient joint error, so no claim
of universally exact alignment or collision-proof arbitrary configurations.
Isolated UE automation Prophecy.Jolt.Constraints.PikeWoundCorrection passed;
node/Blueprint reflection status3/native_properties0/pin_types0 verified. Saved
map/sword hashes match pre-restart; editor2612 open /Game/explosionVFX, stopped,
no dirty packages at final check. User authorized restart for RAM. Clean Slate
shutdown; cancelled own in-flight LC UBT to release shutdown wait. Normal build
30actions found one PI namespace error;5-action retry passed18.32s. Normal DLLs
current. Source + small standalone fixture Tools/Jolt/PikeJointLab; procedures,
measurements and caveats in Docs/JoltSkeletalProps and Saved/Diagnostics/CoupledPike
(~1.1MB). No video/user Play demo started beyond the two diagnostic captures.

**October21 Play-camera ZQSD â€” loaded and bindings verified:** user requested
ZQSD instead of WASD. DefaultInput FlyCam mappings changed; native DefaultPawn
requires the existing editor helper's new3-key remap (Q descent moved to A).
Only ProphecyDebugCameraInput.inl/config/tools changed; no maps/BPs/Play touched.
After the shared Live Coding build succeeded, Tools/SetPlayCameraZQSD.py installed
the helper at09:06UTC. Log verified changed=3 ZQSD=1 QDescends=0; loaded FlyCam
axes verified Z/S and Q/D. No Play started/stopped, no asset saves or restart.
Normal DLLs remain stale: normal build needed before future cold launch.
See Docs/DebugCameraInput.md. User retains motion testing.

**October21 wound correction left enabled â€” supersedes one-shot demo:** user
explicitly requested keeping it in. ShowPikeWoundProjection.py --keep-enabled
now stays registered across Stop/Play in this editor, with no demo timeout or
automatic Play control. Attached to existing user Play without stopping it.
Same lateral-only Python prototype, no native build/BP edits/saves; normal
iteration budget. Clears world references between Play sessions, rebinds next
Play. Editor restart still needs reinstalling this helper; not packaged runtime
code. Dirty A_Sword preserved. Do not revert to one-shot behavior unless asked.

**October21 wound demo rearmed â€” user controls start:** previous demo was stopped
by user; callback retired. User missed the motion while assistant launched it.
ShowPikeWoundProjection.py --arm now waits for their next Play press (up to10min),
then applies the same temporary correction through that Play only. Do not launch
Play for them. No save/build/wiring changes; dirty A_Sword preserved. Stop Play
retires the callback. Receipt show-wound-anchor.json records armed/active/retired.

**October21 wound-line visual demo â€” Play left running for user:** user asked to
judge the temporary post-solve sword translation. ShowPikeWoundProjection.py now
runs it in the current scene; first cut t0.266667, 74 corrections over1.2s,
maximum shift0.807332cm, same as prior prototype. Normal iteration budget;
no rotation/velocity edits, native build, asset save or BP changes. Callback
retires on Stop Play/world replacement/error or10minute safety timeout. Do not
stop this user inspection session. Initial owned attempt hit a Python validity
API error before any correction; ended only that failed owned Play and reran
with SystemLibrary.is_valid. Receipt Saved/Diagnostics/PikeSlide/show-wound-anchor.json.

**October21 wound-pivot follow-up â€” transient prototype only:** user rejected
higher iterations and suggested rotation should preserve wound contact. No Play
was active when removal checked, so overrides were already discarded. Current
joint stores arm wound anchor, not an explicit hilt hinge; native SixDOF linear
Jacobian uses wound lever arm, but finite solver leaves lateral residual. Tested
post-step lateral-only wound-to-blade-line projection at normal budgets, same
first-contact prefix. Maximum residual0.000003915cm (by construction), maximum
per-frame correction0.8073cm; max rotation error21.768deg vs44.304deg baseline.
Keeps orientation, axial travel and velocities from native solve. Existing physical
adapter forwards the translated sword pose. Owned Play ended; no production
code/wiring/asset change or build. This is a Python prototype, not a deployed fix
or a conservation/performance claim. See JoltSkeletalProps/PikeSlide receipts.

**October21 user visual iteration trial â€” Play left running:** user asked to see
the higher-iteration effect. ShowPikeIterations.py started Play and applied
transient10velocity/32position to victim mannequin at first cut,t0.266667;
native log verified10/32. Callback unregistered after application. This Play is
now for user inspection: do not stop it. No saved tuning, BP or camera changes;
dirty A_Sword present before starting. Stopping Play discards iteration overrides.
Receipt Saved/Diagnostics/PikeSlide/show-iterations.json.

**October21 sword depth stain â€” additive, installed/saved:** A_Sword
**Stain Blade(Depth, Seed)** keeps Max(previous,Clamp(input,0,1));0 adds nothing,
.5tip-to-half,1tip-to-hilt. Seed(int0 default) chooses a repeatableÂ±20deg/slightly
wavy edge, locked on first positive stain; shape translates unchanged with depth.
Blade-local Y and scaleY/Z compensate nonuniform scale. Seed upgrade compiled
status3/saved,1editor compile173.52s/no restart; existing caller Depth links intact.
Existing paint MID/RT retained; generated sword blood
material unions painted mask with depth using shared blood shading. Later paint
recognizes/reuses depth MID. No tick/traces or event rewiring;24other graphs
verbatim, BP status3/saved. Original M_Sword untouched; first companion superseded.
Live Coding runtime/editor2actions and editor repair1action passed/no restart.
NORMAL DLLS STALE: next normal build must include paint-manager resolver/reset
changes before cold launch. No visual Play test. See BloodExperiments opening
and Saved/Diagnostics/SwordBloodDepth; user scene unchanged.

**October21 arm pike lateral drift â€” investigated, no production change:** current
upperarm_l cut starts aligned; X/Y and all rotation axes Locked, blade Z Limited.
Both frames stay fixed but native/visible error reaches5.223cm/44.304deg.
Same-prefix transient10velocity/32position comparison reduces to0.550cm/14.006deg;
confirms convergence sensitivity, not an approved high-cost fix. Unreal projection
is enabled in profile but not implemented by Jolt adapter (linear alpha1;
angular alpha0). No build/restart/assets saved; owned Play ended, transient solver
settings retired. Dirty NS_bloodwound/map preserved. See JoltSkeletalProps opening
and Saved/Diagnostics/PikeSlide. Next fix should be scoped to cut/slider behavior.

**October21 recovery AE regularizer running:** user restores frozen AE on
perturbed get-ups only, additive to full position MSE. Fixed weight.2752568
calibrated for10% combined pose+AE cost on latest88363_final's evaluation.
Latest saved locally/S3 before resume; normal rows/settings unchanged. Live
20261021_091317_uefn_getup_ae10_512 on L4w9aq90rzkg1d0g until stopped, $.59/hr;
trainer696/guard697,bridge13512/dashboard1724. Verified88384 at~9.29ktransitions/s,
new checkpoint readback and actual18perturbed AE/2normal zero-AE replay rows.
See MimicKitTraining opening and getup-ae calibration/verification receipts.

**October21 locomotion AE30/MSE30 â€” running/verified:** latest78988_final
(1.294B) preserved locally/persistently, resumed sameL4rjsan0uitu03qd until-stopped.
Perturbed only:AE through30ticks,linear blend toMSE at60;originalAEweight6.94265826.
Normal rows/settings unchanged. Live20261021_091005_uefn_locomotion_ae30_mse30_yaw180_512,
trainer701/guard702;78989â†’79009 verified,~11.65k transitions/s,newbackup verified.
Replay confirms0/.5/1tracking weights at30/45/60. Recovery branch untouched.
See MimicKitTraining opening and Saved/MimicKitLocomotion/ae30-verification.json.

**October21 node rename â€” live, no restart/build:** Accept Pike Hit now displays
**Cancel Hit Reaction**. Updated native UFunction DisplayName metadata through
remote Python and the narrow header's DisplayName for future builds; underlying
AcceptPikeHit function, pins and behavior unchanged. Native graph audit confirms
new title; full live A_Sword exports SHA-identical before/after. User's dirty
A_Sword preserved unsaved. No Play/compile/save/restart. Metadata-only source
change is not yet in normal DLLs: next normal build incorporates it; until then
`Tools/SwordHolster/RenameHitReaction.py --apply` reapplies after a cold launch.
Receipt Saved/Diagnostics/CleanPike/rename.json.

**October21 clean pike entry â€” installed/verified:** Blueprint acceptance stays
editable; joint settings untouched. New Enable Clean Hit Continuation at sword
BeginPlay and Accept Pike Hit after existing pike gates replace pose/velocity
together before rendering. Accepted pikes bypass old teleport/additive velocity
correction; slash path preserved.24graphs/3,937 original pins/defaults retained,
four added nodes/ten link changes. Scope: free dynamic sword, one collision
substep, no existing joint/weld or second solved pair; refusal exposes Reason.
Normal build11actions/200.87s passed; CleanPike and existing HitEvents tests pass.
Actual unchanged scene accepted at0.266667s: velocity exactly incoming
(997.336864,0,-260.963416)cm/s, forward continuation. A_Sword saved; map hash
preserved. Editor15456 open explosionVFX/A_Sword, owned Play ended/no dirty assets,
reflection status3/native_properties0/pin_types0. Normal DLLs current.
See Docs/JoltSkeletalProps.md and Saved/Diagnostics/CleanPike.

**October21 blood mesh shadows â€” user verified:** active Fountain001 mesh renderer
in NS_bloodsplat2 uses new M_Blood_ShadowOnly, masked ShadowPassSwitch(0 visible,
1 shadow); original sprites/material and mesh geometry/scale retained. Only
material and NS saved; user confirmed shadows work. See Docs/BloodExperiments.md.

**October21 recovery resumed:** verified85149(1.395B) after storage cleanup,
same settings, replacement L4w9aq90rzkg1d0g at$0.59/hour until-stopped.
Old recovery GPU unavailable; retained disk preserved. Locomotion managed in
separate chat. Run20261021_074429_uefn_limp_floor_512,trainer479/exitguard480;
verified85150â†’85170 at~10.63k transitions/s and new85150 persistent readback.
Bridge18464/dashboard7392; TB and20-row replay available. Exact saved recovery
source retained via SHA-pinned launcher verification. See MimicKitTraining.

**October21 locomotion resumed:** latest75533 (1.238B samples), unchanged
settings and until-stopped authorization. Old L4 could not restart; replacement
L4rjsan0uitu03qd at$0.59/hour, live20261021_074500_uefn_locomotion_mse_yaw180_512.
Trainer481/exitguard482,bridge4900/dashboard22724. First75534 checkpoint
backup verified after fresh checkpoint-sized storage write/readback. Recovery
branch untouched. See MimicKitTraining opening and locomotion resume receipt.

**October21 authorized checkpoint cleanup:** latest recovery85149(1.395B) and
locomotion75533(1.238B) downloaded, SHA256/ZIP verified, preserved locally in
each branch's preserved-latest folder and in persistent storage. User-authorized
older physical loco/get-up checkpoints/replays removed:46.58GB persistent,
5.26GB local. Datasets, code, TB history, crawl/other Unreal models untouched.
No training restart. See MimicKitTraining opening and cleanup-20261021 receipts.

**October21 training status correction:** both Runpod pods are now EXITED.
Follow-up confirms shared persistent storage quota exhausted: even18-byte
PutObject fails QuotaExceeded. Failed-backup shutdown is the strong common
explanation; exact exit logs still unavailable. Free safe storage and verify
checkpoint-sized backup before any paid restart; no user files deleted here.
Locomotion stopped October20 22:01:00 Warsaw; recovery stopped22:01:37.
Runpod labels both `Exited by user`, but the caller/cause remains unidentified;
do not infer a user instruction or a training crash from that label. Recovery
control still says until-stopped. No restart performed. Recovery replay and
saved evaluation metrics recovered through85149 (1.395B samples); missing raw
training events remain unavailable. See MimicKitTraining opening for evidence.

**Independent locomotion branch â€” October20, running and verified:**
User resumes preserved pre-split73832_final(1.210B samples) on a NEW L4,
cb2i8leh2qpjdf at.59/hour until user stops it ("ad vitam" supersedes8hours).
All controls in Saved/MimicKitLocomotion, separate from recovery
Saved/MimicKitEquipment/new5546ihvxeax; recovery training untouched.
7%idle/93%loco, each30%normal/70%perturbed; no get-ups or AE.
Pure tracking MSE fromtick0; perturbation yaw[-180,+180],initialCOM2 velocity
preserved;120tick perturbed horizon,300normal. Existing termination rules/
penalties,50/50walk/run and split-checkpoint optimizer settings retained.
Live run 20261020_211208_uefn_locomotion_mse_yaw180_512, trainer435/exitguard436.
Verified advancing73833â†’73913, persistent checkpoint73833 readback, actual AE
not loaded, correct row allocation and120tick replay horizon; ~11.4â€“11.6k
training transitions/s. Bridge25868/dashboard27124; setup watchdog released
only after progress/backup verification. Recovery pod/control hashes unchanged.
See MimicKitTraining opening and deploy_locomotion_branch.py.

**Sword Slow Start clock â€” October20 fixed/verified:** user's true/5 startup
still called SetFixedFrameRateRuntime(5), yielding0.2s physics steps while
authored clocks spent1/60. Startup now retains fixed60 and uses t.MaxFPS with
existing slow value; normal startup and End Play restore cap60. Four added BP
nodes, six existing pin changes only;24graphs/3911live original pins preserved.
Actual Play true/5: all deltas1/60, cap5, measured4.636FPS;0.2simulation seconds
over2.588wall seconds. End Play cap60 verified. A_Sword saved; no map/tuning
or runtime-physics changes. Helper's first application crashed on obsolete
BuildString_Float lookup before save; corrected to Double with safe preflight,
normal one-unit build65.34s passed, isolated graph/compile validation completed,
then live edit/test/save passed. Prior saved sword hash preserved through crash.
Normal DLLs current. Editor29136 reopened explosionVFX, outside Play, cap60,
no dirty assets; reflection status3/native_properties0/pin_types0.
See Docs/SwordHolster.md October20 and Saved/Diagnostics/SceneClock.

**Separate skeletal blood brush â€” October20 installed/verified:** placed
**the decal manager** now exposes Blood Paint > Skeletal Brush Radius (3cm).
Ordinary/floor brush radius remains user's2cm. Pure component cast/select on
ordinary paint path; four added nodes,490 existing authored pins retained,
only three data-pin link changes, execution wiring unchanged. Actual wound
Play127 accepted hits: skeletal3cm/static2cm; owned Play ended.
After repeated Live Coding memory exhaustion user authorized save/restart.
Saved dirty A_Sword and NS_bloodsplat2 with backups; A_DecalManager already
preserved/saved. Their hashes remain intact. Shutdown exposed duplicate blood
callback listener removal; existing atomic guard now unregisters once and skips
dead-object delegate cleanup. Normal builds54.93s/75.79s/64.29s passed, each one
compile unit; isolated startup/shutdown exited0. Normal DLLs current.
Editor14720 reopened explosionVFX, new BP control saved/opened, no dirty assets
or Play; reflection status3/native_properties0/pin_types0.
See Docs/BloodExperiments.md and Saved/Diagnostics/SkeletalBloodBrush.

**Limp blend floor correction â€” October20 19:34, verified running:**
Resumed latest79848_final, preserved locally and persistent readback verified,
as20261020_193455_uefn_limp_floor_512. Perturbed starts now receive minimum
upward root shift to clear every collider AFTER blending; joints/orientation/
XY/velocities unchanged. GPU batched FK/support only at reset, no physics-step
projection.42,020offline cases and18actual new replay starts clear floor.
Same L4new5546ihvxeax,trainer849/exitguard850;bridge12596/dashboard22876.
Verified79869advancing/79849backup; handoff watchdog released.
Early throughput10.69k transitions/s versus10.41k before: no observed slowdown
in this short comparison. All other curriculum/reward settings unchanged.
See MimicKitTraining opening and limp-floor verification receipts.

**Limp blend floor defect â€” October20, diagnosis preceding correction:**
Exact screenshot step79324 row11 reconstructed within1.42micrometres.
79.1% whole-pose blend to limp index31 places right hand44.5cm underground,
head25.8cm; saved limp endpoint only0.9cm penetration. Intermediate blended
pelvis height fails to clear the rotated/articulated body.16/18 replay starts
exceed5cm. Needs floor support recomputation after blending, at reset only.
Diagnostic turn did not modify or stop training; subsequently corrected above.

**Recovery limp curriculum â€” October20 19:09, verified running:**
User marks183047 stale; restart its initial79023_final, restore noise.075/
GAE.98/previous MSE leeway, retain50/50front/back.154normal/358perturbed,
normal77frame0/77random. Perturbed poses uniformly blend vanilla frame0 to
saved limp whole pose INCLUDING pelvis position/rotation; velocities unchanged.
Failure low-head check tick80 instead60. No AE or new physics changes.
Current20261020_190959_uefn_limp_blend_balanced_512 on same L4new5546ihvxeax,
trainer600/exitguard601,until stopped. Verified79044 advancing at~10.5k
transitions/s and79024 persistent backup. Handoff watchdog released.
Bridge11944/dashboard21884. See MimicKitTraining opening for details.

**Recovery settings restored â€” October20 18:30, verified running:**
Current20261020_183047_uefn_normal_balanced_no_leeway_512 resumes latest
79023_final preserved locally and in S3. Noise.05,GAE lambda.95,no position-MSE
leeway;front/back50/50,each128frame0+128random-frame. Fixed correlated motion/
start selectors by stratifying starts within each motion. No stiff/limp deployment.
Two startup-only errors on removed leeway compatibility/metadata fixed;
failure guards stopped billing, no checkpoint updates/loss in failed starts.
Old L4 unavailable after stop; replacement L4new5546ihvxeax at.59/hour,
trainer422/exitguard423,until stopped. Verified79034 advancing and79024 backup;
setup watchdog released. Bridge17828/dashboard15268. See topic opening.

**Recovery start split â€” October20 17:14, verified running:**
Current run20261020_171428_uefn_normal_back80_half_random_512 resumes latest
77390_final (1,267,974,144 samples), preserved locally and persistent readback
verified. User changed only start distribution:256normal frame0 +256normal
random-frame rows;410back/102front retained. No stiff/limp/perturbed rows.
Same L4rovwuwstkm0s7r,trainer729/exitguard730,until-stopped authorization.
Verified iteration77521 advancing; checkpoint77491 backup verified.
Bridge448/dashboard8920 publishing; handoff watchdog released after verification.
See MimicKitTraining opening; supersedes frame0-only setup below.

**Stiff / limp initialization datasets â€” October20, prepared only:**
User names the rotated/grounded1,000 poses "stiff inits". Derived "limp inits"
by simulating each independently for10policy frames (80physics steps,1/3second)
with all actuators disabled, gravity and training contacts active. Native
configured MuJoCo CPU, same model construction/profile as training.
Saved/MimicKitEquipment/limp-inits/corpus.npz includes actual final poses and
velocities, with source index mapping. No warnings. Soft contacts leave median
0.94cm / maximum3.14cm floor penetration; retained exact snapshots, no correction.
Preview http://127.0.0.1:8843/Saved/MimicKitEquipment/limp-inits/.
Training untouched. See MimicKitTraining opening.

**Grid3D fuse visibility â€” October20 config change, untested by request:**
DefaultEngine.ini [ConsoleVariables] now forces r.HeterogeneousVolumes=1 above
scalability priority, preserving other quality settings. Installed UE5.7 source
confirms this config section also loads in Shipping. Applies next startup/future
packages; no live command, build, restart or runtime test. See Docs/BombFuse.md.

**Random recovery poses â€” October20, whole-body rotations baked:**
The1,000 retained poses now also have a separate rotated/grounded dataset at
Saved/MimicKitEquipment/random-phat-poses-grounded/corpus.npz. Uniform SO(3)
root orientations, exact same local DOFs, zero velocities; minimal root height
against Z=0 using every collider. All1,000 nonpenetrating; lowering any pose
1micrometre causes penetration. Preview opened at
http://127.0.0.1:8843/Saved/MimicKitEquipment/random-phat-poses-grounded/.
Upright source preserved. Not deployed to training. See MimicKitTraining opening.

**Random recovery initialization corpus â€” October20, awaiting visual approval:**
Retained the exact first1,000 independent PHAT-admissible poses, pelvis fixed upright at
Z0.931191m, zero velocities. First10 shown in
http://127.0.0.1:8843/Saved/MimicKitEquipment/random-phat-poses/.
All14,000 retained joint cases accepted by the project Jolt limit probe; current saved
PHAT fingerprint verified. No floor/self-collision filtering (133 floor overlaps).
Poses1,001â€“1,500 archived into Windows Recycle Bin at user's request; preview
and generator now retain1,000, preserving the original sampled prefix.
Not deployed to training; current normal-back80 run left untouched. User must
vet before initialization changes. See MimicKitTraining opening.

**Automatic blood Niagara callback â€” October20 installed/verified:** placed and
spawned systems exposing User.decal_callback now bind the existing level's unique
callback manager automatically during Play. Valid explicit callbacks retained;
wrong Blueprint-asset references corrected. Creation/activation and level events,
cached manager lookup, no per-frame scan or timer. Ten owned-Play checks passed,
including attached effects and actual pool reuse. Normal incremental build365.77s
plus one-unit loading guard59.82s passed; normal DLLs include earlier sword and
decal-depth fixes. Editor26512 reopened explosionVFX, outside Play, no dirty
packages; reflection status3/native_properties0/pin_types0. User dirty map and
NS_bloodsplat saved with prior-byte backups before restart; all four saved
map/NS/manager/sword hashes preserved through testing. Floor-paint issue below
was subsequently repaired. See Docs/BloodExperiments.md automatic-callback
section and Saved/Diagnostics/BloodAutoCallbacks.

**MimicKit temporary normal/back focus â€” October20 15:50, verified running:** user
requested100% normal get-ups,100% frame0,80% back. Latest recovery74681_final
downloaded and S3 SHA verified. First154538 startup caught a body-name variable
shadowing error; guard stopped billing. Fixed/tested, runtime restored on same
L4. New155034_uefn_normal_back80_frame0_512,trainer483/guard484 until stopped. Fixed410back/
102front rows;0perturbed/random-frame. No reward change: suggested normal
completion bonus has not been authorized/applied. Prior recovery50/50 plan
saved normal-back80-previous-plan.json; no automatic switch-back scheduled.
Live batch verified512normal frame0,410back/102front,0perturbed/random/prior.
First74682 backup verified; replayer20normal rows and failure card working.
Mixed73832 checkpoint remains preserved for loco.

**Actual injury floor painting â€” October20 repaired/verified:** user fixed the
floor execution wire; remaining failures were tiled floor UV0 sending stamps
outside the RT and mapping MI_ProcGrid to generated parent M instead of preserving
MI. Asset-only repair uses an18KB project mesh copy with normalized UV0 and correct
generated material instance with original overrides. Same floor geometry,
transform, world-position grid appearance and1024RT; no native code/build/restart
or extra runtime work. Actual wound Play, foliage decals hidden: visible surface
stain,16 painted mask pixels vs0 before. Zero-intensity vs original material
capture pixel-identical; painted changes3,843pixels. User wiring preserved/saved.
Map, mesh, MI and generated parent saved (force-save parent needed as loaded
package had no file); editor26512 explosionVFX outside Play, no dirty packages.
See Docs/BloodExperiments.md opening and Saved/Diagnostics/FloorPaintFix.

**Separate decal rendering â€” October20 fixed/loaded, not the requested paint:** injury callback and
floor occupancy already worked; debug rectangles hid a rendering regression in
the rectangle adapter. Projectors barely overlapped the floor, reducing material
opacity to~13% through UE's depth fade. Centre now follows receiver+bounded surface
offset, keeping full opacity; no new recurring work/layout change. One-action
Live Coding134.49s passed/reloaded13:16:19UTC, rectangle regression passed
13:16:41UTC. Final actual injury capture visibly stains floor (19 decals).
No assets, materials, emitters, tuning or Blueprint wiring changed/saved.
At verification editor29912 was outside Play, sword graph identical.
**Build state superseded:** automatic-callback normal build above incorporates
this fix; editor26512 is open on explosionVFX outside Play.
See [blood rendering repair](Docs/BloodExperiments.md#injury-fountain-invisible-floor-stains--october20)
and compact evidence Saved/Diagnostics/InjuryBlood.

**MimicKit recovery/locomotion split â€” October20 15:14, verified running:** user now
wants separate policies. Latest mixed checkpoint73832_final downloaded locally
and verified against S3 SHA221ed14975999aab1846e53758113bb228418827acd4edbf8403ca1b05ba3699.
Preserve it for the user's locomotion fork; receipt
Saved/MimicKitEquipment/recovery-split-loco-fork-checkpoint.json. This chat owns
recovery-only run20261020_151434_uefn_recoveries_only_512 on existing L4
rovwuwstkm0s7r, trainer2478/guard2479. Requested512 rows:128 normal frame0,
128 normal random frames,256 perturbed with existing2:1 upper-half skew.
Live cohorts verified exactly; first73833 backup verified,73843 advancing at
~8ktransitions/s. Mixed starting checkpoint has1,209,679,872samples; preserve it.
Replayer20 get-up rows and both failure cards verified. **Locomotion fork must use separate run/control
state and must not stop or repurpose this recovery pod.** See topic opening.

**Sword/skeleton penetration â€” October20 repaired/loaded:** external constraints
now reuse passive skeletal props' existing Jolt bone handles. Scene collision
changes forward to the same rig, preserving QueryOnly trace bodies and native
simulation. No retained layout changes. Live Coding: three compile actions
188.76s, then one test-fixture correction121.44s; both loaded. PlacedMannequin
test passed12:59:04UTC, including joint reuse/no duplicate rig, channel-only and
response updates, restoration and teardown. Current explosionVFX owned Play
confirms nonzero native cut-joint forces and depth minimum0.606992 (~39% blade
penetration), then existing physics/Blueprint lets it come back out. No permanent
sticking claim. Sword graph identical; no wiring/tuning/assets changed or saved.
At verification editor29912 was outside Play. **Build state superseded: the
automatic-callback normal build above incorporates this fix.** First
reload logged RigVM access-detector ensures; subsequent Play/test passed.
See [skeletal props repair](Docs/JoltSkeletalProps.md#sword-penetration-repair--october20-installed).

**MimicKit settings adopted â€” October20 14:10:** user approved noise0.075 and
GAE lambda0.98 from the completed comparison. Active
20261020_141039_uefn_getup_success_value_512 resumes latest72108_final/
1,181,433,856 samples, preserved locally and verified in S3. Same L4, until
stopped; trainer2154/guard2155, bridge25552/dashboard21856. Actual post-restore
noise verified0.075 and GAE0.98. Normal get-up failure card now counts all
completed normal get-up episodes every10updates, same cadence as perturbed
cards. Normal/perturbedâˆ’100 failure costs and success fix retained. First72109
backup verified;72119 advancing at~7.9ktransitions/s. See topic opening.

**Focused comparison complete â€” October20 13:55:** noise.075/GAE.98 modestly
better than current.05/.95 with success fix: failures30vs36 at64updates,
23vs32 at128,928 identical get-up starts; training411vs408seconds. No normal
loco regression. One training seed, short horizon; both test configs predate
normal-get-upâˆ’100 change. No alternative applied. Queue1224 exited.
Main133905 continues with normal-get-upâˆ’100,71741/1.175B,~8.3ktransitions/s,
backup71641 verified. See MimicKitTraining opening.

**MimicKit normal-get-up penalty â€” October20 13:39:** user requested sameâˆ’100
failure penalty for normal get-ups. Active133905_uefn_getup_success_value_512
resumes latest71440_final/1,170,489,344, locally/S3 verified. Trainer1587/guard1588,
same L4 and until-stopped budget. First71441 backup verified. Normal completion/
timeout unchanged, perturbed success fix retained. Focused comparison1224 was
paused during handoff and is resumed; both copies retain the frozen pre-change
objective for a fair comparison. Details in MimicKitTraining opening.

**MimicKit focused comparison requested â€” October20:** user now explicitly asks
to retry noise.075/GAE.98 against current.05/.95 with success fix. Bounded two-way
comparison queue1224,128updates each from70639, held-out evaluation at64/128.
No broader sweep or automatic live setting change. Main130053 continues unchanged.
See focused-success-launch.json and MimicKitTraining opening.

**MimicKit sweeps stopped â€” October20 13:15:** user objects to repeated sweeps.
Queue551 and its process group stopped, cancel.request set; do not restart
comparisons automatically. Main130053 remains training,70890/1.161B samples,
no failure. Earlier completed sweeps showed only modest improvement; no major
learning-speed gain established. Latest70639 baseline894/928 successes versus
current settings895/928 after64updates; other latest variants incomplete.
Keep live settings unchanged. See MimicKitTraining opening.

**MimicKit corrected resume â€” October20 13:01:** active
20261020_130053_uefn_getup_success_value_512, from70639/1,157,365,760 samples,
with known success value100. Same L4rovwuwstkm0s7r,.59/hour until stopped;
trainer444/exit guard445, bridge21024/dashboard29160. First70640 S3 readback
verified. Isolated corrected-success sweeps queue551 now starts from70639 too,
not the superseded67931. Results pending. See MimicKitTraining opening.

**MimicKit stopped by user â€” October20 12:55:** rollback67931 was too early.
Trainer saved68077; local download matches verified S3 SHA. Sweeps cancelled;
owned L4rovwuwstkm0s7r confirmed EXITED, billing stopped. User points to the
failure-curve trough immediately before its rise around1.159B. Selected retained
70639/1,157,365,760 samples (6.20% reported failure), last saved checkpoint before
the trough/rise; downloaded and ZIP checked. Do not reuse67931 or resume sweeps
from it. Training remains stopped. See latest MimicKitTraining opening.

**MimicKit resumed â€” October20 12:46:** active
20261020_124643_uefn_getup_success_value_512 on L4 rovwuwstkm0s7r,
.59/hour until stopped, trainer484/exit guard485. Rolled back to verified67931;
head success value100 enabled. First new67932 checkpoint S3 readback verified;
steps advanced to67952/1.11334B, ~8.1k transitions/s before sweep load.
Deleted69 old local replay JSONs,1.97GB; checkpoints/TB retained. No eligible
standalone old rollouts on persistent volume, no persistent deletion.
Storage API access recovered across datacenters without persistent cleanup;
underlying provider cause unknown. All temporary CPU helpers stopped, no relay.
Corrected-success learning sweeps resumed (queue577), results pending.
See opening of Docs/MimicKitTraining.md.

**MimicKit storage investigation â€” October20 12:31:** no trainer running;
latest L4 9r63p3vlvogqz5 and temporary CPU helper both confirmed stopped.
Full runtime SHA-verified locally with AWS downloader; pod S3 requests still
time out. Sudden underlying cause unproven. CPU direct mount listed files,
but full reads/relay not yet verified. Additional.06/hour relay approval pending;
user asks for root cause instead. See opening of Docs/MimicKitTraining.md.

**Directly placed mannequins â€” October20 installed/verified:** user requires
Jolt for skeletal mannequins dropped into scenes, including future placements.
Scene discovery now binds standalone SkeletalMeshActors with physical PHAT
collision to a passive shared-world Jolt articulation. Existing agents unchanged;
no NN/controller added. Visible pose and retained QueryOnly blood receivers follow
Jolt; standard velocity/force/impulse dispatch supports the new binding. Failed
admission freezes/reports instead of silently simulating Chaos. Six-action normal
build103.66s passed; PlacedMannequin test passed10:12:11UTC, zero errors/warnings
(floor contact, pose/query alignment, standard velocity, late spawn, scaled mesh,
cleanup). Saved dirty user Sword/map with backups before necessary restart.
Editor13868 reopened explosionVFX normally; owned live Play confirmed one Jolt
binding, dynamic pelvis and Chaos simulation=false across three frames. Ended
owned Play; no dirty packages. Original saved hashes verified. New native layouts
are in current normal DLLs. See [skeletal props](Docs/JoltSkeletalProps.md);
evidence Saved/Diagnostics/PlacedMannequin20261020.

**MimicKit rollback authorized â€” October20:** user now requests resume before
stalling, then continue sweeps.67931_final/1.113B selected with buffer before
known-good69138, local+fresh S3 verified. Explicit head-reset success value100
implemented/tested (99 bonus once, zero bootstrap, perturbed get-ups only).
Old L4 unavailable; replacement iiprikebnm51jl setup blocked by persistent-storage
timeouts, finally HTTP524. Replacement confirmed stopped12:09 before10minute
cutoff; both GPUs off. No trainer or new sweeps started. Code/checkpoint prepared
and tested, locally and S3 verified before allocation; no disk-full evidence or
deletion. Resume remains pending storage access. See
[MimicKitTraining](Docs/MimicKitTraining.md).

**MimicKit held â€” October20 11:38:** user asked to investigate head-reset avoidance
before restarting. Owned L4 ka68jrougesuit confirmed stopped. Latest70939/1.162B
checkpoint downloaded locally, SHA matched retained disk; S3 readback timeout
stopped previous trainer at71039 (not saved).70939 persistent verification pending.
Offline replay confirms get-ups hovering85â€“87% and timing out while earning~.85/tick.
Success has no explicit credit; TIME reset bootstraps poorly anchored final-state
critic estimates. Proposed known success value, no reward changes deployed.
All learning ablations/confirmation finished; candidate noise.075/lambda.98 offers
modest gain and better normal-get-up retention; not deployed. Details and resume
constraints in [MimicKitTraining](Docs/MimicKitTraining.md).

**MimicKit harder get-up sampling â€” October20 09:46:** resumed verified latest
69138_final with2/3 of perturbed get-up starts above50% strength,1/3 below.
Active094614_uefn_getup_skew_linear_512, trainer8547/guard8548 on existing L4,
until stopped; other training settings retained. Sequential disposable learning
ablations running; no candidate deployed. See [MimicKitTraining](Docs/MimicKitTraining.md).

**Special attacks / grab independence - October20 refined, isolated/verified:**
Managed checkout `C:/Users/singerie/.codex/worktrees/grab-special-attacks/Prophecy`.
Start Special Attack now has Release Grab0..1,default.8, relative to retained clip;
0 immediate,1 at completion. User-confirmed Cut Early convention changed:0 full,
positive value is clip endpoint (.8=80%,1=full). Pelvis frame-zero heading matched
once at entry; authored subsequent turns retained. Fresh editor clips finish their
pending compression before sampling (validity alone returned temporary ref poses).
Final4-action normal build46.55s passed.12 cases passed: four physical two-hand
projections, immediate/end/trimmed release, four world headings and Cut Early1.
Accepted entry-pose heading error<.000004deg; both regional and ordinary end events
once. Current video `Saved/SpecialAttacks/projection-refined.mp4` replays measured
UE/Jolt transforms. Main editor/source/assets untouched; **not installed live**.
Exact24-file baseline manifest/patch retained. See
[current work](Docs/SpecialAttacksAndGrabIndependence.md).

**MimicKit LR comparison â€” October20:** isolated10-full-update2x/4x/8x tests
finished. On928matched get-up starts: baseline794successes,2x792,4x792,fixed8x787.
8x hits guard8of10updates; no demonstrated gain over current2x. Live7410 unchanged.
Single training seed/short horizon; do not claim a long-run winner.
Details: [MimicKitTraining](Docs/MimicKitTraining.md).

**MimicKit continuation â€” October20 08:57:** user authorized double actual actor
LR and the verified observation optimization. Latest67931_final/1.113B samples
preserved locally and S3 before resume. Active085731_uefn_lr2_graphed_linear_512,
L4ka68jrougesuit, trainer7410/guard7411, until stopped. LR5.625e-7â†’1.125e-6;
Adam state/KLguard retained. Observation graph/device quaternion optimization and
replay fixes deployed; reward/physics/distribution unchanged. First new backup
verified; details in [MimicKitTraining](Docs/MimicKitTraining.md).

**MimicKit get-up learning audit â€” October20:** live run unchanged. Failure rate
still improves slowly (~18.3â†’17.8%); remaining failures concentrate in strongly
perturbed front starts. Actual restored actor LR is5.625e-7 (1/8 YAML), inherited
from earlier guard reductions, not a new slowdown. Isolated matched update favors
a2x LR trial;8x worsened getup surrogate. No tuning deployed. See
[MimicKitTraining](Docs/MimicKitTraining.md) for measured counts and limitations.

**MimicKit replayer repair â€” October20:** valid recordings from the new locomotion
failure-penalty run were rejected because the replay reward check omitted that
penalty. A second downloader retry bug then replaced the archive with its last
chunk. Both repaired locally; cloud trainer4368 unchanged and still advancing.
Failed downloads now restart from byte0 and preserve existing valid rollouts.
Details and verification: [MimicKitTraining](Docs/MimicKitTraining.md).

**Sword pre-impact first-collision follow-up â€” October20:** update-current-values
is correctly called inside ReceiveHit. Live log rejects placed A_Sword1 from Jolt
because MACD=true; Chaos events therefore return invalid/zeros. Switched only
that placed sword to supported ordinary CCD (MACD=false/CCD=true), verified after
component reconstruction. Map dirty/unsaved; no Play/build/restart. Class/child
defaults unchanged, still MACD=true. See Docs/HitImpactSpeed.md.

**Sword pre-impact node â€” October20 rewind installed/verified:** user rejects
per-sword tick storage and requests backward extrapolation from incoming motion.
Removed the proposed history map and both per-tick capture passes. Same node/pins
now rewind one full current physics-step duration from the contact sample using
constant incoming COM/angular velocity, including welded component lever arms.
Estimated earlier pose, not an exact previous-tick boundary; impact speed remains
measured contact-time. Current user Tip Distance=Blade+HiltHalfLength; don't restore
older double-hilt guidance. Dirty Sword preserved/saved before required shutdown,
sha5b33859a...; editor29952 exited cleanly. Superseded history build passed but was
not reopened. Replacement8-action normal build124.62s and focused hit test passed
11:17:24UTC with zero test errors/warnings (first hit, rotation, moving target,
kinematic, welded COM offsets/both orders, CCD substeps and changed velocity).
Editor9572 reopened explosionVFX normally; Sword saved SHA unchanged. Owned Play
first sword depth1.054566, versus earlier recorded0.911003, incomingZ-732.189798.
Ended owned Play. No promise every contact depth>=1; no depth clamp or BP edits.
See [HitImpactSpeed](Docs/HitImpactSpeed.md),
Saved/Diagnostics/SwordPreviousTick20261020 preservation and
Saved/Diagnostics/SwordRewind20261020 current evidence.

**Shared blood manager â€” October20:** user requested consolidation for sword
compatibility. Repaired original A_DecalManager floor/ordinary-mesh routes and
removed per-hit print, matching the experiment copy. explosionVFX now has one
BloodDecalManager of the original class; sword lookup verified one match.
Preserved nine variable values,22 floor-grid settings and paint/floor references.
No placed Niagara components remained; no callbacks to redirect. Original BP
compiled/saved; map was left dirty, then saved with the user's edits for the
subsequent pre-impact-node restart above. Old experimental BP preserved. No Play
started for consolidation. One-action Live Coding136.38s succeeded,
reload04:57:53UTC; normal DLLs stale. Existing WireExperiment command now repairs
the original BP. Subsequent normal build above covers this helper.
See Docs/BloodExperiments.md and
Saved/Diagnostics/BloodManagerConsolidation/receipt.json.

**Blood rectangle merger â€” October20 installed/verified:** user explicitly requested
production integration. Existing FoliageDecalGrid component/library now use the
lab's greedy rectangle kernel; Blueprint graphs and settings retained. Hit receiver/
instance and plane separate surfaces; sloped planar floors supported. Corrected
half-extents, actual widthÃ—height debug bounds. Dirty regions only, pooled hidden
preparation, max16 allocations/pass, no idle timer/tick. Existing interval/budget/
limits retained; 32Ã—32 maximum region, smaller MaxMergeLevel respected. Capacity
retains pending occupancy instead of evicting old stains; Process/Start after cap
increase resumes. Source/build details and compatibility notes in
[BloodExperiments](Docs/BloodExperiments.md#rectangle-integration--october20).
Private retained layout required normal restart. Preserved dirty user A_Sword and
explosionVFX with backups/hashes. Six-action minimal normal build111.80s passed;
RectangleIntegration passed10:40:53UTC, zero errors/warnings (coverage, hole,
negative cells, reuse, receivers/heights/slope, capacity, allocation cap, cleanup).
Editor29952 reopened explosionVFX normally. Actual placed original manager in brief
owned Play:16cellsâ†’one102Ã—25.5cm projector, including existing1.02padding. Owned Play
ended; map/sword/manager saved hashes preserved. No fountain recreated. Normal DLLs
current; no production GPU/FPS claim. Evidence Saved/Diagnostics/BloodRectangleInstall.
Independent lab/tests remain in Labs/BloodDecalLab. Historical isolated CPU results:
filled43â†’1,hole43â†’4,splash52â†’24,strip8â†’1; kernel7.17us/region, streamed p95.203ms,
cold capped max.749ms. These are lab NullRHI measurements, not production timings.

**Blood callback follow-up â€” October20:** new NS_bloodsplat pointed its callback
to the Blueprint asset. Replaced with placed BloodExperimentManager actor; both
Niagara override stores verified. Tuning unchanged; no Play/test/restart. Map left
unsaved in the user's editing session. See Docs/BloodExperiments.md.


**Blood experiment â€” October20 ready:** explosionVFX now has BloodFountain,
BloodExperimentManager, BloodPaintManager, BloodFluidRendering and three receiver
blocks in the Blood Experiment folder. Reuses NS_bloodarc with sustained 86400-game-
second emission and a 45deg/s rotation component. Current shared decal Blueprint
had disconnected ordinary-mesh painting and floor routing; corrected only a new
BP_BloodExperimentManager copy. Original blood assets/wiring preserved. One-action
editor-helper Live Coding passed213.59s/reloaded03:29:00UTC; copied BP status3.
Map and new BP saved. Final actual-Niagara check: rotating/emitting, two mesh paint
states, zero unsupported hits, floor cells created. Owned PIE ended/callback retired.
No performance claim: continuous spray can accumulate many floor-grid cells.
No restart; normal DLL predates new editor helper, minimal build before cold launch.
Temporary text dumps removed (~7.25MB); compact scripts/counters/map backup retained.
Full setup/controls and limitations: [BloodExperiments](Docs/BloodExperiments.md).


**VFX reopen â€” October20:** requested explosionVFX for blood work. Minimal normal
build succeeded (16 actions,312.35s); base DLLs now include preceding Live Coding
changes. Editor22852 launched normally on /Game/explosionVFX. Startup dialog dismissed;
map and remote connection verified before blood setup.
No assets changed or saved. Read-only probe: Saved/Diagnostics/VerifyVFXOpen20261020.py.


**Explosion lab checkout removed â€” October19:** user requested detachment/removal
to recover disk space. Temporarily unpinned this UE5 chat, used managed archive,
then restored its original pinned position. The isolated explosion-lab/Prophecy
folder is gone; only main Prophecy remains in git worktree list. Removed7,036 files,
3,566,537,400 logical bytes (~3.6GB). The app's Git source-recovery record adds
102,773 compressed bytes, with no full checkout/build archive. Existing compact
explosion recovery/media bundle remains at .codex/artifacts/prophecy-explosion-2026-10-18.
Main runtime/editor left untouched. Receipt Saved/Diagnostics/ExplosionWorktreeRemoval20261019.json.
Follow-up:96 redundant explosion/bomb diagnostic files (21,581,016bytes) moved
to Windows Recycle Bin, including retired fuse-physics folders, old asset backups,
graph dumps/logs and non-performance screenshots. Performance evidence, compact
verification records, scripts and final demo videos retained. Bin was not emptied.
Exact paths: Saved/Diagnostics/ExplosionClutterCleanup20261019.json.

**Motion AE size comparison â€” October 19 complete:** fresh 2x512/latent128 trial
on the identical corrected 64-motion features, splits, normalization, sampling and
12,000-update protocol. Best validation checkpoint: step 12,000. Train/validation/
test MSE .001244/.014059/.012319 versus 3x1024 .000997/.030460/.029142.
Smaller model improves validation 53.84%, test 57.73%; validation/train ratio drops
30.56x to 11.30x, so a gap remains. Single-seed comparison, not independent-motion
validation. Recommended smaller portable bundle: Saved/MotionRegularizer-2x512;
prior larger bundle remains Saved/MotionRegularizer. No controller changes.
Evidence: Saved/RoboticMotionAE/20261019_mse_fullbody/architecture-comparison.json
and run_2x512. Full topic: Labs/RoboticMotionAE/README.md.

**Motion AE correction â€” October 19 complete:** replaced the rejected 474-clip
model with a fresh AE on 64 motions: 12 existing trimmed retargets and the exact
full-body Physical Loco (2) MSE targets (48 omni, 2 idle, 2 front/back get-ups).
Drawn/unarmed variants included. All 52 MSE PKLs are byte-identical to the stopped
47039 deployment; no added projection, foot displacement or upper-body freezing.
Verified both arms articulate in every omni. Fresh 3x1024/latent128 trained 12,000
updates; selected step 12,000, train/validation/test MSE .000997/.030460/.029142.
The train/holdout gap remains a documented limitation. Portable export, standalone
loading, input gradients and heading invariance passed. Active bundle and neutral
integration instructions: Saved/MotionRegularizer. Rejected bundle archived under
Saved/RoboticMotionAE/20261019_loco/rejected-bundle. Viewer 8875 shows 64 motions.
Evidence: Saved/RoboticMotionAE/20261019_mse_fullbody. Policy remains stopped;
no Unreal/PHAT changes. Full topic: Labs/RoboticMotionAE/README.md.

**VDB node colors â€” October19 installed and verified:** Temperature Color and
Scattering Color added to Spawn VDB Effect/Light Bomb Fuse, matching existing
orange/white defaults. Set once before rendering; custom bomb colors stored in a
new non-ticking component, defaults allocate none. No new recurring update/pass.
Initial5-action build failed on validation API; corrected3-action retry113.50s
passed/reloaded12:00:22UTC, no restart or retained-layout changes. A_Bomb preserved,
compiled/saved;57 existing authored pins unchanged plus2 colors. Five isolated
integration cases passed12:03:48UTC including delayed/instant/default and cached
tail colors, invalid input rejection. Owned Play ended; callback retired. User
started a new Play before12:04:46UTC; left it and new dirty A_Bomb/NS/map untouched. Normal
DLLs stale: minimal normal build before cold launch. No user map/Niagara changes.
Evidence Saved/Diagnostics/VDBColors20261019; details Docs/ZibraExplosionFade.md.

**Optimised checkbox â€” October19 installed and verified:** user requested
an A/B checkbox. Added visible Optimised(defaultfalse) to Spawn VDB Effect and
Light Bomb Fuse; forwarding uses optional new non-ticking bomb marker. Optional new
VDB cache component/M_ProphecyVDBOptimisedTail reuse prepared final3D textures,
freeze lighting and disable projected shadows; off retains prior rendering.
Existing native layouts unchanged; minimal Live Coding6 compile actions passed
201.05s, reload09:54:56UTC. No restart. A_Bomb preserved/reconstructed/compiled/saved,
56 existing authored pins/defaults/links unchanged and one false bOptimised pin.
Generated ReceiveBeginPlay compiler graph excluded from authored-pin comparison.
Normal DLLs stale; build minimally before any cold launch. Timing test passed.
Zibra's internal1.5 density multiplier is preserved from the source MID; correcting
that required one body-only compile action66.03s/reload10:07:26UTC, no object changes.
Five owned runtime cases passed10:09:50UTC: off expires240; explosion/ring cache at
92/62 and expire240; overlapping fade stays live/expires120; early zero skips
cache/hides and expires60. Collision remains disabled, density/colour ratio and
lifetime checked, full/half-fade images inspected. Actual profiles: off held/fading
prep4.712/7.118ms plus translucency1.378/1.169; on no prep, translucency2.331/.820.
Pass costs only, no gameplay FPS promise; on also disables projected shadows.
Instant-bomb forwarding off/on passed10:12:10UTC, no fragments/emitter and one
short-lived effect at a time. Owned Play ended, editor26816 remains explosionVFX;
node is unchecked for the user's A/B test. `op`/`bf` done, callbacks retired.
Evidence Saved/Diagnostics/VDBOptimised20261019. Do not run the full bomb suite.

**VDB prototype findings â€” before checkbox:** user accepts a modest hitch only at effect startup, not
periodic refresh hitches. Do not implement a low-cadence refresh as the solution.
Cached final-volume/fade prototype succeeded, retaining real3D. At half/.0833/.01
density, current-style preparation7.5â€“8.2ms plus translucency1.2â€“1.3ms became no
preparation and translucency1.0â€“1.4ms. Native-setter repeat plus90degree camera move
confirmed3D/fade and eliminated preparation again. Fixed self/received lighting;
projected shadows disabled in ALL comparison cases. Tail only: animated phase,
startup/handoff spike, production ownership/cleanup and both assets not validated.
No full sequence cache or production change. Existing textures~19.97MiB for one
frame; extrapolated whole-clip memory is not a measured cache size.
Owned Play ended09:34:39UTC. Temporary duplicate material
`/Game/__ProphecyVDBPerfProbe/M_CachedTail_20261019` deleted/absence verified
09:36:04UTC. Original shader restored, user assets/BP untouched; editor26816 open
explosionVFX/outside Play, profile CVars/throttle restored. `vd` is done/no callback.
Native SetDensityScale avoids the lighting invalidation caused by editor property
notifications in the diagnostic; production uses direct property writes. Full
findings/control catalogue and prototype limitations in Docs/ZibraExplosionFade.md.

**VDB deeper investigation â€” October19, no new production change:** user requested
all performance knobs and explanation of costly near-invisible tails. Five owned
comparison runs completed (one VDB at a time); editor26816 left explosionVFX/outside
Play, profile CVars/throttle restored. Our fade handling disables lighting reuse at
tick180 after source ends at90; unchanged shape suddenly regains downsample/lighting
passes. At density.01, repeated GPU scopes: density downsample2.521ms, lighting1.193,
colour4.465 (prep8.181), translucency1.336. These are pass costs, not30ms effect cost.
Render downscaling still evaluates all source voxels; eighth not automatically faster.
Temporary eight-colour-sample shader trial cut quarter colour4.4â€“4.5â†’.9â€“1.0ms,
but added fire grain; motion/other views not validated. Original engine shader restored
byte-identical and recompiled before repeat; no experimental shader installed.
No native build/restart, user-asset or BP edits/saves. Prior adapter and stale normal DLL
status unchanged. Full native control catalogue, test receipts and prioritized next
work in Docs/ZibraExplosionFade.md. First proposed exact improvement: independently
cache unscaled density grid across held-frame density fades (no DensityScale input).
Final-volume caching tested as above; production caching and optional sampled
quality/cutoff remain proposals, not installed nodes. No recurring refresh cadence.
Evidence Saved/Diagnostics/VDBPerformance20261019.

**Sword death/drop repair â€” October19 installed, user accepted:** inspected current `die revive`.
Its `get sword` -> GetHeldSword returns null during D/S insertion, so the guard
skips material AND DropSword; shortened equipment remains attached to the dying
agent. Direct native drop restores full scale (1.311941 Z) from both reach and
attached slide. Static mesh receiver also lacked SetPhysMaterialOverride forwarding
to Jolt; now implemented without retained layout changes/polling. Five-action
Live Coding passed553.73s, reload07:42:37UTC; native MaterialOverrideDrop test passed
07:44:51UTC for independent/welded held, dropped and None reset material values.
Unreal26816 remains open explosionVFX. Normal base DLLs are now stale: minimal
normal build before any cold launch. Blueprint saved/preserved before reload.
First editor graph migration refused without edits because the existing cast
is pure. Corrected one-action helper build passed135.42s/reloaded07:49:24UTC.
Migration applied07:50:21UTC: drop first, use returned actor for guard and material
target, preserving material literal and other wiring. BP compiled status3. User
confirmed it works and pivoted to VDB performance. Agent's final graph-save/repeat
death probe was deferred during user Play; do not claim an agent post-migration save.
Evidence/scripts: Saved/Diagnostics/SwordDrop20261019. Current map/unrelated
assets unchanged; original auto-bomb scene baseline timed out at dead tick68;
subsequent owned D/S probes removed only PIE bombs before ignition and ended.

**VDB performance â€” October19 installed/verified, full 3D:** node-spawned effects
(including bombs) use quarter render-volume resolution, eighth lighting resolution
and main ray step4, configured before asset assignment to avoid full-resolution
startup allocations. Lighting is reused on unchanged source frames at stable
density, refreshed through fade/endpoints/snaps; zero-density tails disable plugin
visibility while preserving actor lifetime. No entire-clip cache or plugin edit.
Fine smoke detail is softer; moving-light/occluder lighting can stay frozen during
a constant-density held frame. Source animation timing and all node controls remain.
Controlled matching GPU captures: moving47.74â†’33.96ms, held41.41â†’22.25ms,
fading40.09â†’28.84ms. CSV means show smaller moving improvement; these are fixed
capture GPU costs, not gameplay FPS promises. Resident scene+effect GPU memory
3514.7â†’2939.9MiB. Invalid early pilots discarded. See Docs/ZibraExplosionFade.md.
Only ProphecyVDBLibrary.cpp changed. Two one-action layout-safe LC builds passed
61.15s/83.47s, final reload08:33:08UTC/no object changes. No restart or content save.
Timing automation passed08:33:59UTC; four actual-asset runtime cases and rendered
fade captures passed08:35:22UTC. Editor26816 open explosionVFX/outside owned Play.
Normal DLLs stale: minimal normal build required before any cold launch.
Evidence: Saved/Diagnostics/VDBPerformance20261019 and VDBCacheBenchmark.csv.

**Static fuse / upright Niagara â€” October19 installed and verified:** user rejected
and explicitly requested removal of the whole bomb fuse-physics experiment.
Static original-shape fuse replaces skeletal/AnimDynamics visual; remove stiffness
node/setup component and generated skeletal assets/tools. Shared holster unaffected.
Niagara follows the shrinking tip with world identity rotation/absolute scale,
keeping gridZ up. Current A_Bomb emitter pin uses NewNiagaraSystem1; null still
means none. Existing cap/hide/force/VDB/fragments controls preserved; offset pin removed.
Flame debug-box inspection11:03UTC: User.DrawBounds still true; automatic toggle
blocked by unavailable asset API/desktop helper. Asset export unchanged, dirty
A_Bomb preserved. Manual control/evidence recorded in Docs/BombFuse.md.
Retained layout changes: assets preserved, editor17636 closed cleanly. Initial
11-action normal build compiled runtime but failed on editor helper pointer type;
corrected4-action retry passed59.17s. Base DLLs current. Editor26816 reopened
explosionVFX; A_Bomb compiled/saved,63->56 pins with only requested changes.
Original470 fuse triangles and shading verified. Old skeletal fuse/skeleton and
six physics tools deleted. Isolated StaticFuse passed05:41:54UTC:180 moving/rotating
samples, world-up emitter, progressive clipping, material inheritance and hide.
No effects test in user editor. Niagara saved bytes unchanged; agent reflection
healthy. The two retired diagnostic directories (BombFuseFlexible and
BombFuseRigidity20261019) were moved to Recycle Bin in the user's October19 cleanup.
See Docs/BombFuse.md and Saved/Diagnostics/BombStaticFuse20261019.

**Recovery/test constraints:** previous full FuseAndDetonation test spawned eight
VDBs and crashed editor12676 with D3D12 E_OUTOFMEMORY. Never run it in the user's
interactive editor. Focused tests run isolated -nullrhi; disable Fab for that
process to avoid its restored browser tab asserting with -nocef. Niagara recovery
snapshot Saved/Diagnostics/NiagaraPulse.txt and compact recovery receipt remain;
recovered NewNiagaraSystem1 is saved. Never overwrite it with that old snapshot.

**Fuse Cap installed October19:** Light Bomb Fuse adds remaining-fuse fraction
0â€“1, default0;0 burns fully,.5 burns halfway,1 instant (zero speed allowed).
Burn/spark speed unchanged. New optional non-ticking cap component preserves all
existing retained layouts. Minimal Live Coding3 actions passed237.58s, reload
03:54:40UTC; no restart. Current A_Bomb preserved/refreshed/compiled/saved with
54 existing authored pins intact and one new cap pin0; stale library CDO repaired.
Native21-argument API and agent reflection healthy. FuseAndDetonation passes
03:56:48UTC including0/.25/.5/1 caps and VDB/force; EOS heartbeat warnings only.
This gameplay change is now incorporated into normal DLLs by the crash/reopen
build above. See Docs/BombFuse.md and
Saved/Diagnostics/BombFuseCap20261019 for preservation/verification evidence.

**Niagara clipping checked October19:** NewNiagaraSystem1 RenderScale0.2 and
LocalPivotZ0.12 make the red debug box misleading: its center differs from the
scaled simulation center. Flame reaches the real grid top. Temporary
WorldSpaceSizeZ300->600 recovered the missing tip; all diagnostic settings
restored, no content save/build/restart. See Docs/BombFuse.md Niagara clipping
section and Saved/Diagnostics/NiagaraClip20261019.txt. No permanent tuning change.

**A_Bomb shell material:** retain source-matched static shell and runtime material
inheritance. Former startup flexible fuse setup is superseded by the static-fuse
cleanup above; do not restore startup physics. See Docs/BombFuse.md.

**Fragment transparency fade â€” October18 installed/verified, no restart:** Light
Bomb Fuse adds Fragment Fade Duration (default1s,0off), over the final part of
Fragment Lifetime, clamped to that lifetime. Separate new non-ticking component
leaves existing layouts unchanged. Original material stays until fade, then20 pieces
share one translucent MID/opacity write. Current Bomb/PressureBomb uniform values
and nine matching static switches are preserved; alternative shaders need translucent
FragmentOpacity support or retain original material/expiry with a warning.
Live Coding5 actions passed452.06s; reload16:07:27UTC. User explicitly stopped their
Play before reload. Refreshed current /Game/_mygame/bomb/A_Bomb pins, compiled and
reopened; saved bytes match preservation. Native combined test passed16:07:51UTC,
including half/zero opacity and cleanup. Owned rendered Play passed239 samples:
solid through120, fading121â€“239, destroyed240 for lifetime4/fade2. Both solid/half
screenshots inspected. Editor6904 remains explosionVFX/outside Play; user dirty map
and NewNiagaraSystem untouched. Base DLLs require minimal normal build before next
cold launch, incorporating fade, fragment toggle and impact event. See
[BombFuse](Docs/BombFuse.md); Saved/Diagnostics/BombFragmentFade, Tools/BombFuse.

**Explosion impact event â€” October18 installed/verified:** six-file extension,
existing world/Agent/scheduler layouts unchanged. Minimal Live Coding8 compile
actions passed285.59s; ProphecyJolt patch_0/GameAnimationSample3 patch_1 loaded,
reload complete15:44:24UTC. No restart. Bind Explosion Impact(Self,event) gives
immediate first-hit notification and shared30-unpaused-tick cooldown per actor;
explosion impacts only. Three focused isolated tests pass after4-action build46.73s,
including real PHAT limbs, K2 pins, delayed delivery, cooldown and reentrant handlers.
Main owned Play smoke created receiver on actual agent and pushed26 bodies.
Python lacks wrappers for new types after LC, so main callback timing was not
retested through Python; native isolated tests cover it. Existing BP compile and
agent reflection healthy; sampled saved package hashes unchanged, no wiring
edits/saves. Editor6904 remains on explosionVFX/outside Play; map currently dirty,
left untouched. Base DLLs need minimal normal build before next cold launch,
including this event and prior fragment toggle. See [ExplosionImpact](Docs/ExplosionImpact.md).
This supersedes all older PAUSED references below.

**Fragment toggle â€” October18 installed, no restart:** Light Bomb Fuse
adds Spawn Fragments (defaulttrue). False skips fragment asset loads and debris
creation/cleanup but retains VDB and physical force. Existing Fragments array
represents the option; no retained native instance-layout changes. A_Bomb current
edits backed up/saved before function-reflection reload; user dirty map and
PressureBomb left intact. Live Coding3 actions passed286.30s; patch_0 and reflection
reload complete15:22:44UTC. Handled MTAccessDetector/RigVM reload ensures and .voltbl
linker diagnostics occurred; editor responsive afterward. Combined test passes
15:23:03UTC: default20 fragments, disabled timed/instant zero fragments while VDB
and actual physical force remain. Native19-argument reflection verified; Python's
cached wrapper still shows old signature, use call_method until cold launch.
Existing A_Bomb node initially had stale pins; reloaded only its freshly preserved,
clean package and compiled successfully15:25:12UTC. Same editor PID6904, no restart,
no manual wiring edits. Map/PressureBomb retain their pre-existing dirty state.
**Base DLL predates this checkbox: minimal normal build before next cold launch.**
Evidence/scripts: Saved/Diagnostics/BombFragmentsToggle.

**Light Bomb Fuse â€” October18, installed and verified:** node in Prophecy/VFX
accepts the original bomb mesh component, progressively clips its curved fuse,
then triggers VDB AND physical blast and launches20 prepared shell fragments.
All previous effect/blast controls plus fuse burn speed and fragment velocity.
User explicitly deferred Niagara: no glowing tip/emitter. UV1 stores burn distance;
white vertex colors preserve the imported glTF appearance. Original assets and
A_Bomb graph remain untouched; no automatic Blueprint wiring was added.
Material follow-up installed: all20 fragments inherit the bomb component's current
slot0 material at detonation, including dynamic instances replaced after ignition.
Burning visual still uses its prepared masked material. Single compile action
(198s), layout-safe patch_1 loaded14:36:40UTC; combined test with late dynamic
material replacement passes14:37:05UTC. No restart, assets or wiring changed.
User's dirty A_Bomb/explosionVFX were saved before the required native-layout restart.
Editor5800 hit a shutdown-window error after saves and exited; no force-kill.
Minimal normal build33 actions passed (538.92s), incorporating the VDB endpoint
fix and five-file base explosion port; impact-event extension stays PAUSED.
Final editor-only mesh-baker correction loaded by layout-safe Live Coding
patch_0 (1 compile action,208.32s), reload complete/no object changes. **Base DLL
predates the baker correction and fragment material inheritance: minimal normal
build before next cold launch.**
Combined native test passes, including actual Jolt impulse, delayed wave,20 radial
fragment velocities, VDB and cleanup. Final rendered Play captures verify original
appearance, progressive disappearance and fragmentation; owned Play ended.
Editor6804 open on `/Game/explosionVFX`, no Play/dirty packages. Original mesh,
material, preserved A_Bomb and map hashes unchanged. Agent reflection healthy.
See [BombFuse](Docs/BombFuse.md); evidence Saved/Diagnostics/BombFuse.

**Spawn VDB Effect node â€” October18, installed and verified:**
User requested the two downloaded effects with scale/framerate and density fade
start/target/duration; explicitly chose one-shot disappearance. New native node
and short-lived controller use authored60-tick timing, hold the final frame if
needed for the fade, then destroy the actor. Current explosionVFX was backed up,
saved and closed cleanly;7-action normal build passed (173.93s). Final endpoint
correction loaded through layout-safe Live Coding patch_0 (2 actions,125.32s).
The later normal bomb build above incorporates that correction into the base DLL.
Timing automation passes; both actual effects pass166 sampled Play frames,
including exact density/frame progression, transforms, final-frame hold and
destruction at ticks120/48. Final editor5800 is open on `/Game/explosionVFX`,
outside Play, with no dirty packages; existing agent BP reflection healthy,
wiring preserved. Failed headless Fab startup and handled RigVM reload ensures
are documented with successful subsequent verification in
[ZibraExplosionFade](Docs/ZibraExplosionFade.md). The separate explosion-impact
event task remains explicitly PAUSED; do not resume until requested. Its isolated
worktree journal records remaining verification/packaging. This requested map
supersedes the uncreated explosion_test proposal and older testNN reopen default.

**Crawl stopped at user request â€” October17:** user cancelled the additional
hour. Stop request reached run20261017_135639_uefn_crawl_velocity_512;
checkpoint1628 was saved and checksum-verified locally (SHAb2d38e957d29).
Owned pod o6qhah385ykhhx explicitly stopped; API confirms EXITED. Active run
marked stopped, latest verified pointer updated. No further training restart
authorized. Receipts: Saved/MimicKitCrawl/user-stop-confirmed.json and
local-backup-status.json. The previously planned14:58 finish is cancelled.

**Additional crawl hour startup (now stopped) â€” October17:** previous35-minute run
20261017_130908_uefn_crawl_velocity_512 finished cleanly and pod stopped.
Final checkpoint1612_final is locally checksum-verified (SHAaafec06143b4),
26,427,392 samples. User requested one additional hour; continuation startup
uses that final checkpoint and identical current PHAT/motions/configuration.
New run20261017_135639_uefn_crawl_velocity_512 started at13:58:10 Warsaw,
resuming at iteration1613 with optimizer/normalizers restored. First new
checkpoint1613 is checksum-verified locally. Training stops14:58:10; saving/hard shutdown by
15:00:55. Runtime deadline is updated locally/remotely and local checkpoint
helper reloads it. Startup connection timeout and integer-duration argument
bug were corrected before the successful learner launch. Receipt:
Saved/MimicKitCrawl/updated-training-20261017/added-hour-receipt.json.
No AE retraining in this extension; previous times below are historical.

**Updated-source AE completed /35-minute policy continuation running â€” October17:**
current AE run20261017_123736_updated_crawl_idle_2x512 uses edited native crawl
and current idle plus unchanged two LAFAN clips. Same2x512/latent128; best1500,
validation0.0612601, stopped3500/75.1seconds; scorer/export checks pass.
No AE policy reward. User authorized latest crawl checkpoint finetuning with
new PHAT for35minutes. Latest verified local archive1311 contains21,495,808
samples and saved actor/critic optimizers/normalizers. Updated planted crawl
reference installed (SHA02bcdbbf559e); idle unchanged. Full5% upper-body margin
passes103,456 Jolt checks; current-PHAT physics/PPO preflight and final saved
checkpoint rollout pass. Dynamic hand penetration still reaches2.69cm; no
perfect-contact claim. Run20261017_130908_uefn_crawl_velocity_512 is advancing
on owned L4 o6qhah385ykhhx with exact current PHAT/reference hashes. First new
checkpoint1312 is checksum-verified locally and in cloud; optimizer/normalizers
restored. Latest live verification reached1332 with no fatal failure.
Training runs35minutes from actual start13:10:51 Warsaw, stopping13:45:51;
saving and hard shutdown by13:48:36. Local/remote guards and backup helper use
the revised deadline, excluding startup retries (missing ephemeral runtime,
then upload timeout; fixed by restoring cache and reusing identical retained CP).
User-requested checkpoint cleanup kept1311 and the new run; removed9 local,
7 retained-pod and10 cloud archives, freeing300/237/312MB respectively.
Removed stale cloud pointers; current local verified receipt points to1312.
See current crawl topic and updated-training-20261017 receipts for evidence.

**Upper-body PHAT saved in place â€” October17, user authorized:** nine profiles
expanded in the single PA_UEFN_Mannequin for the latest authored crawl/idle,
their pure robot projections and existing contact-corrected idle, with the
documented1.05x angular-excursion rule and coupled swing ellipse. Existing wider
bounds retained; no obsolete cleaned crawl or LAFAN used. Changed spine_03,
spine_05, both clavicles/upperarms/hands, and head. Clavicle twists changed from
LOCKED to LIMITED to admit authored motion. All six leg profiles, including
both ankles, unchanged exactly; frames/geometry/mass/drives/damping unchanged.
Only PHAT saved; five pre-existing dirty animation/BP packages preserved; no
Play/restart/training. Saved asset SHA49994f0bb1257a1e9bdb5dd2aa229455544426a1b6a17d468cc6170df5e9640d.
Independent saved-value validation passes358,456 dense upper-body samples and
89,712 exact-Jolt reference/5%-margin cases. Canonical model/provenance and local
crawl package/source.zip synced; both model XMLs byte-identical. The subsequent
updated-source policy preparation above replaces the obsolete cleaned crawl
and refreshes the training preflight. Current viewer/report/limit overlay refreshed.
Plan, save receipt, verification and original PHAT/model/viewer backup are in
Saved/MimicKitCrawl/upperbody-limits-20261017. Exact values and method in
Docs/MimicKitUEFNBodyMatching.md. Scripts fit_upperbody_limits.py,
apply_upperbody_limits_unreal.py; use --verify-saved for read-only checks.

**Current-source shoulder-limit overlay â€” October17:** updated-source viewer now
has a checked-by-default "Show shoulder limits" checkbox. Green arms show both
nearest admissible shoulder rotations, for authored and robot views at all55
frames. Other local joints stay fixed; hands follow, with no planted-contact
solve or dynamic simulation. `add_source_limit_overlay.py` uses constrained
multistart quaternion-distance optimization; all220 resulting shoulder samples
accepted by exact project Jolt. overlay-verification.json records corrections.
Full-geometry handedness correction retained. Source/PHAT/training unchanged.

**Updated authored crawl and viewer handedness â€” October17:** freshly imported
recoveries/crawl.fbx saved12:07:07 Warsaw, SHA2e849ce9c90057c8a333ce506ded079b8987ccf00e5b46660ec267fd50fcbb84
(55 frames,30Hz). No contact IK, loop closure or LAFAN processing. Fresh read-only
Unreal PHAT export10:10:15UTC matches canonical source-rig exactly. Both shoulders
still exceed twist only; coupled swing fits. Peak twist R/L: authored skeleton
60.7453/60.5029deg; pure robot projection50.0714/46.0837deg; current limits
38.75/33.46deg. 1,732 project-Jolt samples agree with numerical classification.
`Labs/CrawlTraining/inspect_updated_source.py` keeps authored clavicle-relative
and rigid-torso robot measurements separate. Report/data and verified animated
viewer: http://127.0.0.1:8843/Saved/MimicKitCrawl/updated-source-2e849ce9c900/ .
Viewer defaults to authored frame38 (right peak); left peak is frame10. Source
and robot selector, playback and peak controls verified; comparison.png saved.
Complete posed geometry is reflected on world Y to match corrected replayer
handedness, without renaming limbs or modifying stored motions. Same display
correction applied to upperarm-pose-audit and constrained-ik HTML; their old
screenshots predate the correction. Existing policy/AE clips, PHAT, datasets
and training unchanged. Earlier candidate/audits below refer to the older FBX.

**Planted-hand arm IK candidate â€” October17:** user requested fixing excessive
upper-arm rotation while keeping hands planted and seeing the difference.
Review-only candidate in Saved/MimicKitCrawl/constrained-ik/crawl.pkl; existing
policy clip, AE, PHAT and training unchanged. Opened animated comparison at
http://127.0.0.1:8843/Saved/MimicKitCrawl/constrained-ik/ (before/IK, overlay,
source comparison, synchronized orbit, scrub/play, old worst frame280).
`constrained_contact.py` preserves both hand transforms exactly at240Hz keys,
pelvis/legs/travel, and loop closure; solves torso/shoulder/elbow IK with both
shoulders/elbows/wrists constrained to current PHAT,0.25deg interior margin.
Continuity weight20 removes a rejected first-candidate elbow jump. Verification
at1920Hz:20,742 arm poses accepted by project Jolt, zero arm violations;
right/left max twist88.55/64.59 ->38.50/33.21deg. Hand target interpolation
deviation<=0.091mm, planted floor error<=0.749mm, penetration<=0.176mm;
loop seam<0.0001mm, max adjacent world rotation4.924deg (authored hand motion).
Torso/head/left-ankle conflicts remain; head rejection samples increase from346
to675/3457 as absolute head orientation is preserved through changed torso.
Not a whole-body limit-valid training reference. Full-limit torso/head probe
did not converge with pelvis/legs and hand transforms fixed; not a proof of
infeasibility. `verify_constrained_contact.py`, verification.json and screenshot
record results. Candidate SHA a76798221b7d204a0a215f70c23ad77f0bc46871fccaac4656f31eeb3dd7fa1c.

**Worst upper-arm pose viewer â€” October17:** read-only comparison opened at
http://127.0.0.1:8843/Saved/MimicKitCrawl/upperarm-pose-audit/ . Magenta cleaned
target versus cyan nearest admissible selected shoulder rotation, synchronized
cameras, overlay, close-up and right/left selector. Worst means largest minimum
quaternion angular correction over433 cleaned crawl keys. Right frame280
(1.1667s):38.2449deg correction, elbow10.75cm/hand21.00cm displacement. Left
frame80(.3333s):26.0757deg, elbow6.68cm/hand16.31cm. Only selected shoulder
rotation changes; remaining local joints are fixed, not a fully limit-valid or
floor-corrected pose. Constrained multistart nearest-rotation optimization,
both resulting poses accepted by exact project Jolt. Script
Labs/CrawlTraining/upperarm_pose_audit.py; data.json and comparison.png under
Saved/MimicKitCrawl/upperarm-pose-audit. Browser rendering, close-up and selection
verified. No animation/PHAT/training changes.

**Crawl package corrected to the single current PHAT â€” October17:** removed
the historical-profile override from `prepare.py`. `current_phat.py` checks
current export/source asset hashes and copies the canonical model, limits and
physics metadata exactly. Local package and source.zip corrected/verified;
unchanged policy motion hashes, no asset save, cloud change or training restart.
Bundle/start now reject stale PHAT validation; start additionally verifies the
remote three asset hashes against the current local PHAT. Preflight no longer
expects two locked ankle rows. Four-world/three-tick physics check passes with
exact current runtime modes/angles and zero locked ball rows; this is not a
dynamic-contact or feasible-reference approval. Receipt current-phat-sync.json
and current-phat-analysis/package-verification.json under Saved/MimicKitCrawl.
Prior audit statement that package still has old limits is now superseded.
Shoulder trace uses only actual UEFN crawl/idle, not LAFAN: contact IK changed
upper-arm local orientations up to41.29/43.00degrees R/L. Crawl PHAT twist maxima
rose from55.93/46.09degrees in the reduced robot before cleanup to88.55/64.59
after; source full-skeleton shoulder connector maxima are65.38/60.33degrees.
These are PHAT connector-frame angles, not arm direction or authoring Euler
channels. Source, reduction and cleanup are separate measurements; do not blame
the authored motion alone for cleaned-target conflicts. Stage evidence:
current-phat-analysis/shoulder-stages.json. No animation changes this turn.

**Current PHAT crawl analysis â€” October17, read-only:** user clarified that
"restart" meant restart the analysis, not training. There is one authoritative
user PHAT; do not substitute historical pre-running profiles. Fresh Unreal
export at09:12:05UTC matches current `Saved/MimicKitUEFN/source-rig.json` in full.
Both ankle twists are LIMITED, not locked. The crawl package still contains
historical limits except its corrected wrists; its prior audit is not a current
PHAT audit. Against the current PHAT, cleaned crawl/idle torso exceeds limits
throughout; crawl shoulders/wrists and some head poses conflict; idle left wrist
conflicts throughout. Hips, knees, elbows and right ankle fit both clips; left
ankle swing conflicts in80.14% crawl and100% idle samples. Exact project Jolt and
numeric classification agree on11,340 samples at240Hz. Evidence and complete
per-joint percentages: `Saved/MimicKitCrawl/current-phat-analysis/report.json`.
No PHAT edits/saves, training mutations or restart performed. Current asset,
dirty packages and Play state preserved. Details in Labs/CrawlTraining/README.md.

**Crawl contact cleanup and one-hour resume â€” October17, authorized:** user
requested cleaning crawl hands then resuming for1h. `crawl_contact.py` restores
authored hand XY/orientation (with existing seam correction), raises intersecting
hand boxes to ground and retains positive authored box clearance. Fits torso/arms
at240Hz (433frames, same1.8s duration), preserving pelvis/legs/travel. Dense
interpolation check: planted hand gaps <=0.754/0.221mm, deepest reference
intersection0.142mm, loop seam<0.2micrometers. Idle unchanged; AE/originals unchanged.
New policy crawl hash `eca10a3b85d3d6dba9c11850c6cef5c4abc8b1788850aa55ea048891b1ac2190`.
Latest checkpoint701 verified (SHA168efb206c68ccb9dd683c2f709a9fd5b6be1e90fe8ccf0bacc482b51cda445e).
16-world local saved-policy checks:301 deterministic+160 noisy ticks, finite
and solver checks passed, optimizer/normalizers/11,501,568 samples restored.
Residual physical hand penetration up to4cm disclosed; reference cleanup does
not certify perfect dynamic contact. Original solver and current wrist limits
unchanged; joint-limit conflicts remain audited, no silent limit expansion.
Replay selector fixed to1idle/11crawl, auto-phase capture attached and verified.
Evidence contact-cleanup-validation.json, resume-validation.json, and local
replayer entry mimickit_crawl_cleaned_contacts_preview. Prior run assets/receipts
archived in stopped-run-20261017_065646. New3600s allocation pod
`o6qhah385ykhhx`, hard stop09:13:50 Warsaw (Unix1792221230.1971967), $0.59/h.
Run `20261017_081535_uefn_crawl_velocity_512` launched with resume701, trainer393,
exit guard394 and local deadline guard11832. Source71c0a2a02cc1a67d59cebf95395f7ba77cae8920c3bf505f2e1730b6dfb1477f
verified. Resume702 confirmed (optimizer/normalizer restored), training advancing;
first live replay702 verifies1idle/11crawl and phase metadata. No solver errors.
IMPORTANT: shared cloud store returned QuotaExceeded on checkpoint702 upload.
No deletion/volume-size change. Checkpoint702 independently checksum-verified
LOCAL backup at Saved/MimicKitCrawl/local-checkpoints/20261017_081535_uefn_crawl_velocity_512,
SHA b1e95b9ba4b5d2ea67cc0c20aa0a2f37269de4feecfde7ef5dfa8d0532a3c024.
Hidden local backup helper18260 (child28876) polls latest immutable checkpoint;
latest pointer local-backup-status.json. Use that local checkpoint for future
resume, NOT the previous run's S3 pointer. Source local_backup.py; exit watcher
replaced394 with572 to wait up to120s for local checksum acknowledgement before
stopping, bounded by original09:13:50 hard stop; remote deadline guard198 and
local11832 unchanged. Cloud backup error remains visible, not falsely cleared.
Training will hit its existing uploader error at shutdown; local copy and retained
pod volume preserve the completed checkpoint. No new training failure inferred
from that known backup exception. Other loco untouched.

**Crawl STOPPED at user request â€” October17, hovering crawl hands:** pod
`g525r7hbc356yo` confirmed EXITED at Unix1792216522. User correctly flagged
that only crawl_idle received hand-contact fitting; crawl received ONLY an
eight-frame loop-seam correction. Crawl stance contacts were not cleaned or
validated before training. Do not describe both references as contact-corrected.
Receipt `Saved/MimicKitCrawl/hovering-hands-user-stop.json`; active_run marked
stopped_by_user_hovering_hands. Local crawl observers/deadline guard retired;
other locomotion run untouched. No automatic resume. Existing assets/checkpoints
preserved. Separate replay-selection bug also remains: first-agent fill yields
11idle/1crawl previews despite actual20idle/492crawl training allocation.

**Crawl TensorBoard auto-phase display fixed â€” October17:** phase head/MSE were
already trained and logged. Local dashboard omitted `uefn_crawl_idle_mse` from
its tracking-loss/auto-phase mapping. Added that objective and backfilled all
three crawl histories from raw events; exact step/value equality verified.
Charts `auto_phase/mse`, `auto_phase/weighted_loss` and `loss/auto_phase` now
publish, along with body-loss components. Restarted ONLY current crawl dashboard
(PID17188), no trainer/optimizer/run changes. Receipt
`Saved/MimicKitCrawl/autophase-dashboard-fix.json`.

**Crawl continuation authorized â€” October17:** user requested resuming latest
for two hours after wrist correction. Latest verified checkpoint is iteration100
from `20261017_061639_uefn_crawl_velocity_512`, SHA256
`fb4890b3dac1217ad146e6bbfaa9e7c4d894f7e57b61f8d1bd054898f12d1457`.
Local16-world saved-policy test restored optimizer/normalizers and1,654,784
samples, without weight updates.160ticks each noiseless/noisy across both clips
passed finite/solver checks. Residual hand depth reaches26.74/30.74mm respectively;
0.51%/0.88% hand samples exceed20mm. Disclosed to user while proceeding with
requested continuation; do NOT label ground penetration fully resolved.
`resume-validation.json` preserves measurements; `resume-contact-acceptance.json`
records explicit continuation scope. Experimental ground recovery remains OUT.
Separate Secure L4 pod `g525r7hbc356yo` allocated at$0.59/hour, hard stop
08:53:55 Warsaw (Unix1792220035.647861). Continuation
`20261017_065646_uefn_crawl_velocity_512` launched with `--resume`, trainer412
and exit guard413; local deadline guard13676. Source bundle SHA256
`ba33e3ab14a075fbe43d4fdaf4dc81bd9c8b4e6c005d5433607e1e1a2f40ce04`
verified in storage and on the trainer. Resume and first completed update verified:
checkpoint101 independently read back/hash checked from storage (SHA256
`2b9ebac76b99b46cbb4358ecf81c22e81b3647f59c736b0b0c9d6707d4fc2c4b`).
Already advanced through five resumed updates; both wrists confirmed60/45/90
on trainer, no failure/solver-warning files. See resume-start-verification.json. Prior allocation
confirmed EXITED and launch records archived in stopped-run-20261017_061639.
No loco changes. Read active receipts for launch/verification state.

**Crawl wrist correction â€” October17, supersedes the diagnosis below:** user
flagged their newer PHAT wrist edits. Crawl preparation incorrectly restored
both wrists to30/20/50deg along with pre-running profiles, overriding the saved
user60/45/90deg (twist/swing2/swing1). Live Unreal PHAT was never changed.
`prepare.py` now preserves latest saved wrist profiles from source-rig.json;
local package corrected with only two wrist profiles changed, XML byte-identical.
Prior limits/audit preserved in hand-penetration/before-wrist-correction.
Controlled idle test with ORIGINAL solver and angular projection ON now reaches
only1.07mm/15.77mm hand penetration, versus50.70mm/59.08mm with old wrists.
This is within the existing20mm contact slop in this bounded test; do NOT
install experimental ground recovery based on the obsolete wrist experiment.
The all-motion/random-action dynamic check is still outstanding, deployment
remains blocked, and the paid crawl run stays stopped. Reference limit audit
refreshed: crawl wrist violations20/23 of55frames; idle0/48 of48frames.
Evidence: hand-penetration/corrected-wrists-ablation.json. No loco changes.

**Crawl stopped again â€” October17, confirmed hand penetration:** user observed
hands below floor. Measured exact physical hand boxes in the local preview
(4.6/5.8cm depth) and restarted run iteration100 (~5.0/5.6cm). This is dynamic
penetration, not target overlay; prior startup-contact/numerical checks missed it.
Pod `i2nng9pcr65ldu` confirmed EXITED at Unix1792211809; receipt
`Saved/MimicKitCrawl/penetration-stop-receipt.json`. No automatic restart.
Controlled local zero-command ablation confirms causality: angular position
projection ON -> hand depths5.07/5.91cm, OFF ->0.025/0.040cm. One projection
pushes hands down3.58/4.35cm after contacts. Earlier transfer notes explicitly
omitted floor position recovery because recorded loco stayed within2cm slop.
Experimental local GPU ground-position recovery tested: policy-tick hand
depths2.13/2.11cm with the existing Jolt2cm slop; first-substep worst2.64/2.95cm.
Generalized velocities unchanged. Prototype is NOT installed/deployed or ready
for training: coupled joint/contact residuals, random actions, all-body coverage
and captured throughput still need validation. See hand-penetration/diagnosis.json. `launch.py` now blocks paid deployment until dynamic penetration
validation passes. Evidence under `Saved/MimicKitCrawl/hand-penetration`.
No loco changes.

**Crawl restart â€” October17, approved after corrected replay review:** fresh
run `20261017_061639_uefn_crawl_velocity_512` launched on Secure L4 pod
`i2nng9pcr65ldu` ($0.59/hour), 512 worlds, only `crawl`/`crawl_idle`,
20 idle and492 crawl rows, no AE reward/injuries/adaptive sampling. Both clips
loop; original limits and27cm-only failure plus10s timeout preserved. Two-hour
allocation deadline08:14:56 Warsaw (Unix1792217696); local/remote stop guards
and trainer-exit watcher active. First PPO update complete; checkpoint0000000 backup independently verified
from object storage (SHA256 cb69204a0f6a44a61fc7a66737d2792dfb1de92df044f52648019d61d896ee8c).
Trainer, remote deadline guard and exit watcher confirmed alive; no reported
solver/failure/backup errors.
Current receipts `Saved/MimicKitCrawl/{active_run,pod,runtime_control}.json`.
Prior stopped run preserved under `stopped-run-20261017_054944`; loco unchanged.

**Crawl correction â€” October17, after user stopped the run:** policy dataset
must contain ONLY UEFN `crawl` and `crawl_idle`; LAFAN is only for the offline AE
used later for perturbations. Initial policy package incorrectly included LAFAN.
Screenshot idle terminated at clip end (flag2), 20 ticks from a58% start; max
collider error8.38cm, so the27cm failure was not responsible. Reduced rigid
torso/clavicles raised hands~6cm and left hand boxes~4cm above ground. Local
policy-only corrected idle fits hand contact with unchanged pelvis/legs and
hand orientation. Both policy clips now WRAP; crawl tail gets an8-frame small
seam correction (<=4.124deg and0.48mm Z, root XY unchanged). Original datasets
and four-clip AE are unchanged. Prior package archived under
`Saved/MimicKitCrawl/stopped-run-20261017_054944`; new package has2clips.
Corrected16-world CUDA/PPO/replay validation PASSED; runtime initial hand floor
gap<0.0041mm. Real done-path checks confirm no clip-end reset, failure at27.1cm,
and10-second timeout. Preview `mimickit_crawl_contact_fix_preview` in policy
replayer8021. Original limit conflicts remain audited. User approved the corrected
preview and requested a fresh two-hour run. Deployment in progress on separate
Secure L4 pod `i2nng9pcr65ldu`, hard stop Unix1792217696 (08:14:56 Warsaw).
Inspect current `Saved/MimicKitCrawl` receipts for launch/verification status.

**Crawl policy STOPPED at user request â€” October17:** user authorized a
separate crawl/idle run using the current loco MSE pipeline, original pre-running
angular limits, no angle or drawn/sheathed inputs, and 4% idle / 96% crawl.
Clarifications: NO limb disabling yet (four enabled placeholders for arms/legs),
NO AE reward (reserved for later perturbations), NO adaptive motion sampling,
and ONLY the existing 27cm collider-target deviation failure. Ordinary clip-end
and timeout resets remain. `crawl_idle.fbx` (48frames/30Hz) appended to both
saved crawl datasets; existing cut hashes unchanged. Four-clip AE complete at
`Saved/RoboticCrawlAE/runs/20261017_053724_crawl_idle_2x512`, best update1000,
validation0.063653. No existing AE checkpoints overwritten.

Isolated source `Labs/CrawlTraining`, package/state `Saved/MimicKitCrawl`; copied
the deployed loco source53e01c707017 without modifying it or the live PHAT.
153 policy inputs /34 motors, same actor/critic1024/1024/512, fresh learning state;
fixed20/512 idle rows and492 crawl rows. Original angular profiles restored only
inside this package from before-omni-limits/live-rig.json. Source motions exceed
some original bounds; retain audit, no clamp or silent expansion. Isolated runtime
adds bilateral locked ankle twist support and permits >4 same-shape contact points
using existing all-point manifold equations.129 locked-twist cases and1/2/4/5/8/16
point grouping checks pass.16-world actual CUDA/PPO/replay preflight passed42.3s.
Run `20261017_054944_uefn_crawl_velocity_512` launched and completed its first PPO
update with a hash-verified checkpoint backup. User then requested immediate stop
because of an issue. Owned pod `pfsx6089r481q1` is confirmed EXITED; receipt
`Saved/MimicKitCrawl/user-stop-receipt.json` (Unix1792209348). Do not restart
until the issue is identified and user authorizes continuation. Existing loco run untouched.
[Contract, checks and launch workflow](Labs/CrawlTraining/README.md).

**Smaller crawl AE1 â€” October17:** user requested **2 x 512 hidden neurons per
side, latent 128 unchanged**, after discussing overfitting. New local run
`Saved/RoboticCrawlAE/runs/20261017_045107_crawl_ae1_2x512` is COMPLETE;
`Saved/RoboticCrawlAE/current-run.json` now points here. It reuses the exact
prepared baseline data/normalization/splits, with 1,076,757 parameters versus
5,304,853. Early stopped at 3,750 updates (43 seconds), selected update 1,750:
validation MSE 0.062789 versus 0.099568 baseline (36.9% lower). Test MSE improved
on all three clips; jitter/body-jump checks passed, but timing-shuffle sensitivity
remains 2/5 for clip 2. Export parity/input gradients/hash verified. See
`completed.json`, `score-validation.json`, `baseline-comparison.json`. Same test
blocks were reused; this is not independent generalization evidence. Old run and source snapshot
preserved; no policy, locomotion, viewer or original dataset change.
[Contract and artifacts](Labs/RoboticCrawlAE/README.md).

**Initial crawl-only robotic AE1 baseline â€” October17:** user clarified a separate crawling agent,
with ONLY the three curated crawls and no locomotion/idle additions. Authorized
local AE training, now COMPLETE separately in
`Saved/RoboticCrawlAE/runs/20261017_044043_crawl_only_ae1`; `completed.json`
records 12,000 updates in 382 seconds, best checkpoint at update 1,000 (balanced
validation MSE 0.099568). Exported `scorer.pt` passed parity and input-gradient
checks. Root-jitter costs increased in all test windows; body-jump costs in
94.7â€“100%; heading/XY score drift <=9.27e-5. Timing-shuffle check increased cost
in only 2/5 windows of the second short clip. Overfitting and tiny within-source
holdouts remain limitations: first integration candidate, not a validated policy
reward. Full diagnostics in its `score-validation.json`. The current-run pointer
now selects the smaller run above. Initial source snapshot is under this run's
`source/`: fresh AE1 architecture1024x3 each side/latent128,405 inputs,
three actual15-body poses at30Hz in the fixed initial flat-pelvis frame; preserves
height/pitch/roll/displacement, removes global yaw/XY. Full12000-update local
recipe with equal clip sampling, separated temporal holdouts and best validation
checkpoint. Original two robot exports reused; third UEFN crawl converted only
inside the AE run. No viewer, original dataset, PHAT, locomotion policy/job or
cloud change. No crawling policy launch yet. [Contract and artifacts](Labs/RoboticCrawlAE/README.md).

**Lafan Cutter / crawls â€” October17:** native curator at `Labs/LafanCutter`,
desktop shortcut **Lafan Cutter**, user data in `Documents/Lafan Cutter`.
The user's saved `crawls` collection now has three clips: original two Re-solved
cuts (6084 and132 frames, unchanged hashes) plus full recovery `crawl.fbx`
(55 frames at30Hz). Original FBX archived, new BVH/revision and provenance saved;
source rig and timing retained, no robotic retarget or training. SDK/BVH round-trip
position error<.000037cm, orientation<9e-12rad. Read-only all-clips gallery at
`http://127.0.0.1:8874/`; source `Labs/LafanCutter/gallery.py`, generated buffers/logs
`Saved/LafanCrawlViewer`. Existing live Cutter draft/session was preserved; reopen
the updated dataset there before saving it again.

**October17 requested LAFAN retarget:** separate `crawls_uefn` collection now has
the two LAFAN cuts mapped to UEFN and projected through the current locomotion
15-body/34-DOF pipeline (wrists included); third FBX-derived cut byte-identical.
Original `crawls` unchanged. Gallery8874 now displays the retargeted collection
with a blue source-overlay toggle. `Saved/LafanCrawlRetarget` has robot PKLs,
BVHs, before/after NPZs and reports. Same existing locomotion export reproduced
with zero channel difference; FK round-trip<1e-6m/rad, all4536 foot lifts succeed.
Review candidates: hand displacement from reduction reaches26.82/19.43cm and
some poses exceed current locomotion limits. No contact fit, limit expansion,
training change or Unreal edit. [Workflow, mapping and limitations](Labs/LafanCutter/README.md).


**Explicit elbow posture / wrist twist â€” October16 current:** user reproduced a
full circle by setting Elbow down blend to0, then accepted the corrected lab and
explicitly requested its Unreal port. The earlier version7 case-specific fix was
insufficient: it inferred the bend from an admissible straight forearm (undefined
pole), ignored the blend in grab planning, then froze the inward result on grip.
Exact current-fixture replay reproduces224/363deg left/right total swivel and the
left inward pose. The replacement keeps three responsibilities separate: cached
forearm reach extent for body assistance; explicit outward/down elbow pole at the
actual wrist goal; axial wrist twist within PHAT. Blend updates approach AND held
posture. It never derives a bend from a straight forearm or changes it because
the hand happens to acquire grip. Transport and existing8deg swivel/4deg twist
caps remain. PHAT, contacts, fingers, speed settings and8/6deg gates unchanged.

Wrist twist solves feasible scalar intervals using polynomial boundary roots
(degree<=4), choosing the closest previous twist; already-feasible twists use a
fast path. No repeated elbow candidate search or stall/recovery strategy. The old
straight extent planner remains ONLY for body demand; using the bent posture for
that demand produced positive-feedback lean and was rejected. Cache version8;
Refresh migrates old poses/grips without resetting them. A formerly inward held
elbow can need a bounded near-half-turn to recover its outward posture.

Lab evidence `Saved/Diagnostics/ReachElbowDesign20261016/`: five blend values0..1,
live changes during approach/holding, current held resume,20/50cm dragging and
three prior recordings. Current blend0 grabs58/62, swivel44.49/69.97deg; final
left/right elbow outward, wrist error<.001deg and distance<.001cm. Increasing blend
lowers both elbows monotonically. Exact old circling recording now grabs142/145,
swivel8.01/25.89deg. Bone/PHAT errors at floating-point precision; max swivel8deg.
`Labs/ReachLab/test_elbow.cjs` and `test_wrist_twist.cjs` (720 known-feasible twist
cases including reversed frames, limited/free/locked axes) are current checks.
Do not overclaim all historical snapshots: frozen Stalled_250 retains its existing
left attachment but its requested left rotation remains27.28deg away; extreme
50cm sweeps still exceed reach and retain body-assistance residue. TestNN recorded
now acquires119/89 with final0/.64deg. These are separate from the accepted current
fixture. No user Refresh, reset, settings overwrite or lab service restart.

**Unreal port/build state â€” user-requested grab behavior restoration:** user rejected
the previous hold change because the balls stopped moving freely and appeared
fixed to the hands; explicitly requested "restore whatever was happening before".
Restore the exact pre-feedback behavior: GrabTarget reads the object's moving
surface/orientation on every tick, including after acquisition; coupled palm
anchor follows that surface; fixed joint captures the actual physical wrist.
The accepted explicit elbow/wrist solver remains unchanged. PHAT, gates, fingers,
body assistance, speeds, Blueprint wiring and ball settings remain unchanged.

Native implementation matches `ReachGripFeedback20261016/ProphecyReachLibrary-before.cpp`
exactly except one unused HoldTarget member retained to preserve loaded private
layout and permit Live Coding without an editor restart. Do not remove it through
Live Coding. Ordinary lab grips again capture the achieved wrist; the alternative
requested-frame attachment is retained only inside the historical feedback test.
No user lab Refresh, reset, persisted-state overwrite or service restart.

Live Coding rollback loaded successfully:269.17s,one C++ compile,patch0,
no object changes. Owned physical TestNN check through220 acquired grips
left120/right89 and retained both. Full commanded-pose trajectory matches
the pre-feedback recording exactly (0cm maximum difference); held targets
move11.88/51.88cm, confirming ball-following motion is restored.
Editor11912 remains TestNN/outside Play,
dirty[], full graph byte-identical and map/BP/PHAT hashes unchanged. No saves.
**Normal DLLs are stale: incremental normal build before the next cold launch.**

This intentionally restores the earlier feedback behavior too; physical elbow
circling is NOT considered fixed by the rejected hold change. Do not reintroduce
the agent-relative held target without a new user request. The previous lab
snapshots `UE_Grip_Feedback_Before`/`UE_Grip_Feedback` and physical receipts remain
historical comparison evidence: holding the authored command removed drift but
changed the requested behavior. Earlier native-final through720 and blend480
results describe that rejected version, not the current one. Evidence for the
rollback: `Saved/Diagnostics/ReachGripRestore20261016/`.

**Historical approach/held-elbow port to Unreal â€” October16 (superseded above):** explicitly requested by
the user. Native now follows the cached forearm plan immediately, transports it
for target changes, and carries the achieved elbow bend plane after grip. The
per-tick local candidate search is removed; at most two wrist projections/hand
plus one reverse projection when a target changes. Existing retained cache layout
is unchanged; only transient solve inputs gained hint/held fields. Live Coding
compiled one C++ unit in146.06s and loaded patch3 with no object changes. Editor
16368 stayed open. Normal DLLs remain stale: incremental build before cold launch.
600 approach/held/tracking/free/locked numerical cases pass, max arm position
error7.1e-14cm and wrist quaternion error3.4e-16. The initial planner's equivalent
axial-roll ties can differ (up to11.25deg); endpoint error<4e-6cm, reported separately.
Unmodified TestNN acquired physical grips left112/right87, both held through360.
Physical right-ball20cm vertical sweep through720 retained both joints, max
held-plane swivel8.7e-12deg, wrist limit error4.5e-16; lengths preserved.
Editor remains TestNN/outside Play/no dirty packages; Blueprint graph and all
three user asset hashes unchanged. Evidence `Saved/Diagnostics/ReachHeldPort20261016/`.
**Historical pre-lab-fix edge case:** the older separate kinematic auto-contact fixture
at sync=.82 still misses the right grip (1.949cm short). Exact terminal lab
one-step replay reproduces it within5.2e-14cm; do not call all target configurations
fixed. Early kinematic switching in the unmodified scene also failed admission.
Those receipts are retained; gates/tuning were not loosened. Current physical
TestNN is verified. The lab's old captured left-elbow0.0259cm metric is not a
new physical-scene measurement: new physical ball feedback gives max1.219cm
left-elbow movement at200-300. Plane continuity is verified separately.

**Held-ball elbow continuity - October16:** user reported the elbow jiggling while
moving the right ball up/down after grip. This was shared lab logic, not a live
Unreal connection; recorded TestNN inputs were already frozen past360. Captured
exact live setup at8960. A fast50cm vertical sweep reproduced a120.06-degree
one-tick elbow-plane flip near extension: projecting the old elbow against the
new axis reversed its bend direction. The solver now transports the established
plane with the changing reach axis, and held arms no longer swivel toward their
old approach hint. Elbow flexion, wrist twist/PHAT and palm coupling stay active.
No new state, delay, search or setting; still at most two wrist projections/hand.
Plane reversals8 to0; max swivel120.06deg to1.2e-11deg. Moderate20cm sweep retains
both grips with0 hand-angle error. Extreme fast sweeps still have extension
acceleration and rotation residuals: do not claim all unreachable motion is fixed.
Recorded grab timing unchanged left111/right86; max left-elbow step200-300 now
0.02590cm. Numeric regressions pass (`test_held.cjs`, owned stdin `test_kernel.py`,
no browser/live-service load). Evidence `Saved/Diagnostics/ReachHeld20261016/`.
User Refresh preserves current pose/grips and loads the JS. The lab correction
used no automatic refresh/reset or service restart. Native port is covered above.

**REACH planned approach and live-save stall fix - October16:** the user rejected
stall-then-change-route recovery. The lab now selects its existing admissible
forearm plan once at grab start and follows it immediately. Moving targets
transport/project that same route instead of rerunning the search. No stall timer
or fallback strategy; at most two wrist projections/hand/frame (previously18
candidate evaluations). Same speed caps, PHAT, contacts, fingers and8/6-degree gates.
Plan version5 persists target/rotation; legacy snapshots preserve body assistance.
TestNN recorded: right grips86 (previous delayed recovery150), left111, maximum
left-elbow step absolute200-300=0.05493cm. Both hold. Stalled250 grips296; frozen
initial31 grips left112/right85. One initial plan per hand in all three cases;
resume deterministic. Root-only difference0, common-translation error7.15e-14cm.
Paired isolated JS arithmetic mean0.19455 to0.04153ms/hand (~4.7x cheaper), not FPS.
837-frame ordinary grab/retarget/release regression passes. Current test:
`Labs/ReachLab/test_plan.cjs`; evidence `Saved/Diagnostics/ReachPlan20261016/`.
Earlier escape tests and exact-left-trajectory claims are historical/superseded.

**Live-save lag fixed:** entire330-frame recording was serialized twice in every
live packet plus again for session saving every1.2s. Measured formatting costs
were~1176ms live +447ms session. API3 retains motion once in
`Labs/ReachLab/motions/<sha256>.json`; recurring saves use
`motionRef:{id,startTick}`. Live file5.2MB to65KB, session2.5MB to19KB; cached
session saves5-9ms. `/session` expands motion for exact resume; fetch
`/motions/<id>.json` for a live reference. `desktop-view`/`current_view.json`
now have compact references: absent inline motion does NOT mean no recorded case.
Explicit snapshots/exports remain self-contained. Old desktop clients work; new
workspace uploads each recording once, removes redundant live redraws, and draws
recorded catch-up once per batch. Storage roundtrip/backward-compatibility tests
pass in `test_live_storage.py`. Only REACH background service restarted
(7688 to18084); visible window kept open, last readback paused at8201. User
Refresh loads final JS; no automatic Refresh. This storage fix is lab-only.

**Contact markers use occlusion:** gold point/normal arrow and cyan palm reference
now share scene depth, including snapshots. User Refresh loads renderer changes.

**No independent root-point bug:** moving/rotating only the floor root with body
and targets fixed does not affect the other bones. Actual body movement relative
to a stationary world ball changes reach geometry. Do not remove that relationship
or claim the root itself prevents grabbing. Native-captured scenarios remain
historical baselines in `Saved/Diagnostics/ReachScenario20261016/`; the accepted
native approach port now acquires both physical grips. Normal Unreal DLLs
remain stale for the Live Coding changes: normal incremental
build BEFORE any cold editor launch. Last editor receipt was TestNN outside Play,
no dirty packages. See `Docs/ReachGrasp20261012.md` for current and historical work.

**Left elbow hitch â€” October16 historical intermediate fix:** in the unmodified current
TestNN tick30 fixture, commanded left elbow made~0.9cm single-tick jumps at193,
218,256,275,307; the physical elbow followed. Wrist and shoulder stayed smooth.
Cause: fixed coarse half-step search near wrist alignment. Both lab `coupled.js`
and native `ProphecyReachArm.h` now scale elbow/roll search steps with remaining
quaternion error, retaining full steps above8deg and the same18-evaluation cap.
No new search/state or tolerance changes. Reconstructed one-step replay matches
the hitch within0.0004cm; full owned360-tick same-fixture capture verifies max
left-elbow step across absolute200â€“300: command0.90093â†’0.05366cm, physical
0.90080â†’0.05329cm, commanded angle2.252â†’0.131deg. Left physical grip acquires at111
(previous112) and holds through360. Right hand was ungripped before AND after;
do not repeat the earlier erroneous assumption that both current-fixture grips
were held. That fixture limitation is separate from this left-elbow repair.
34 active wrist samples pass PHAT (<9e-16); isolated837-frame lab regression passes
surface/manual grips, retargeting, release and inactive retirement. Recorded prior
performance summaries remain historical; rerun outputs copied into this evidence.
One-action Live Coding compile succeeded119.36s, reload with no object changes.
**Normal DLLs are now stale for this runtime fix: normal incremental build before
any cold launch.** No editor closure, user lab refresh, Blueprint/PHAT/tuning edits
or asset saves. Final editor remains TestNN/outside Play/no dirty packages.
Evidence: `Saved/Diagnostics/ReachElbowHitch20261016/verification.json` and
`lab-verification.json`. User's existing lab window picks up JS on their Refresh.

**Reach/grab Unreal port â€” October16 complete:** user explicitly authorized the
lab port and reopening after the editor stopped. Native reach/grab now includes
arm-first body compensation, bounded coupled elbow/forearm correction, upper-arm
automatic contact selection, lower-elbow preference and Set/Get Reach Motion Tuning
(Sync rotation0, Elbow down blend1 defaults, each0..1). Loaded PHAT remains live;
explicit surface points, Blueprint speeds/wiring and8/6-degree gates are preserved.
Use Surface Point=false selects the new automatic contact rule; the saved tick30
fixture still has its user-preserved explicit point wiring.
Normal incremental build succeeded135.19s/8 actions; new retained state cold-loaded.
Editor16368 reopened and finished on the previous robotics map
`/Game/_mygame/Tests/MimicKitTransfer/M_JoltTransferFailure`, outside Play, no dirty
packages. No crash cause established from the prior log. Blueprint graph and saved
BP/TestNN/PHAT bytes unchanged; reflection status3/native_properties0/pin_types0.
120 isolated lab/native cases pass: final poses match to numerical precision;
equivalent look-ahead roll varies but its forearm endpoint differs<0.000004cm.
Owned Kin-auto, Sim-auto and Sim-explicit grabs all acquire both balls (by absolute
tick150/150/180 after request90), hold through390, then return/retire by411. Four
contact fingers each;186 wrist samples within PHAT (<9e-16 domain violation).
Runtime code is in the normal DLL. A diagnostic-only Live Coding patch separated
look-ahead roll/direction metrics (no object changes); normal DLL diagnostic code
predates that refinement, so include it in the next normal build before cold launch.
No second closure, lab refresh, D/S/robotics edits or asset saves. Evidence and
backups: `Saved/Diagnostics/ReachPort20261016/verification.json`; details in
`Docs/ReachGrasp20261012.md`. No live many-agent performance claim.

**Latest user context:** user explicitly requested TestNN after the reach port.
Editor16368 is now open on `/Game/testNN`, verified remotely, outside Play.
The map switch preserved assets and required no build/restart or save. The prior
robotics map remains saved; do not switch away from TestNN without a new request.
**PHAT limits â€” October16:** at the user's request, saved seven angular-profile
expansions to contain the drawn/unarmed motion dataset plus5% room. Upper arms,
thighs, ankles and right knee changed; both user-edited wrists remain60/45/90deg.
Frames, geometry, mass/inertia, collisions and Blueprint wiring are unchanged.
Exact values and backup are in `Docs/MimicKitUEFNBodyMatching.md` (current section).
The REACH imported snapshot described below predates these seven expansions;
its lab files/session were not changed by this PHAT update.
**Lab refresh preference:** the user handles Refresh with the lab button. After
code edits, do not automatically reload, close or reopen their lab window. Leave
the running session alone and report that the change is ready to refresh.

**REACH elbow blend slider â€” October16:** **Elbow down blend** sits directly
below Sync rotation in the right panel. Range0..1, default1;0 exactly restores
original outward preference,1 exactly preserves the latest lower-elbow rule.
`settings.elbowDownBlend` persists in settings/snapshots and survives reset/restart;
old saves default1. One native multiplier, passed per request, no new search or
solver state. Coupled clamped grabs still prioritize wrist feasibility and may
override this preference (the default clamped fixture has identical elbows).
960 native endpoint-comparison frames passed; intermediate motion preserves arm
lengths, both clamped grips acquire at0/.5/1, UI placement/persistence pass.
Only the standalone DLL was built; REACH background service restarted to install.
Installed hash and live stateless HTTP blend verified. User window was not
refreshed, Unreal untouched. Ready for user's Refresh. Evidence:
`Saved/Diagnostics/ReachElbowBlend20261016/`; `test_elbow_blend.cjs` uses an isolated
service/store and headless browser. `build.py --output-dir` stages future builds.

**REACH rotation timing â€” October16:** shared right-panel **Sync rotation** slider
0..1, default0, stored in `settings.syncRotation`. Zero exactly preserves the old
rotation trajectory. One slows angular pursuit to the remaining wrist-distance /
reach-speed arrival estimate; intermediate values blend angular steps. Rotation
speed remains the cap; PHAT/body constraints or an insufficient angular cap can
delay alignment. Recomputed per tick with no timer/search/state; Follow arm bypasses.
Snapshots, reset/restart and persisted reloads preserve the value; old saves use0.
Isolated verification: full sync both hands finish position/rotation on the same
frames57/69 versus rotation12/13 at0. Both clamped grips acquire with unchanged
gates; retargeting, deterministic replay and UI persistence pass. Evidence:
`Saved/Diagnostics/ReachSyncRotation20261016/`. Only HTML/CSS/JS changed; no build,
service restart, Unreal changes or user-window refresh. Ready for manual Refresh.

**REACH PHAT snapshot â€” October16:** imported the user's newly edited loaded
PHAT wrists into `Labs/ReachLab/phat.json`: both hands60/45/90degrees in
twist/swing2/swing1 order, all LIMITED; frames unchanged. Lab HTTP export matches
the file. Ready for user's manual Refresh; no build/restart/Play or asset save.
Before/after evidence: `Saved/Diagnostics/ReachPHATImport20261016/`.

**REACH elbow preference â€” installed and verified:** only `PreferredBend` in
the lab's `solver.inl` changed: forward reaches now also favour a lower elbow
(70% relaxed preference), blending into the accepted side/back preference (100%).
The adjustment still fades near vertical. This supersedes preserving the old
outward-heavy forward rule. In snapshot0005 elbows lower6.47/7.54cm and move inward
5.54/6.17cm; wrist positions and body parameters are exactly unchanged. Both grips
hold with contact/fitting preserved.240-frame target sweeps and default clamped
grabs pass. No new search/iterations/state. DLL, installer and current evidence:
`Saved/Diagnostics/ReachForwardElbow20261016/`; previous side/back experiment:
`Saved/Diagnostics/ReachElbowPreference20261016/`.
Installation succeeded; only the REACH background service restarted.
Installed DLL hash matches the tested candidate, and stateless HTTP replay matches
the installed native solver exactly (`delivery.json`). Earlier approval blocks are
resolved. Window/session settings and Unreal untouched; user performs Refresh to
update the browser's kernel fingerprint and presses Play if the restart paused it.
See the lab README for evidence.

**Current REACH solver â€” arm first:** the old forearm-derived virtual endpoint
caused excessive body bending in snapshot0002. Replaced it with a bounded search
for wrist-admissible forearm directions, then body compensation driven only by
the remaining upper-arm reach shortfall beyond ordinary positional reach.
Ordinary pursuit catches up before adding compensation; excess is reduced again.
Compensation is continuous while dragging, limited to0.5cm per authored tick,
and the original body kernel still handles balance, legs and body motion.
The arm look-ahead uses at most14 projections per changed shoulder/target and is
cached within0.01cm; none ran during120 settled ticks in each regression case.
Existing per-tick arm correction remains bounded at18 evaluations/hand, settled1.
The original surface references, hand rotations, fitting and8/6-degree gates are
preserved; no relaxed wrist limits. Cache/feedback persist in `grabs[].armPlan`,
are validated on import, and resume deterministically from snapshots.
Snapshot0002 with identical contact: forward bend46.88->27.83deg, crouch21.15->9.14cm;
both grips acquire from idle and continue correctly. Fresh upper-arm contacts on
Restart give17.70deg/4.50cm. An arm-only feasible fixture grips with zero body motion.
This is bounded feedback through the existing body algorithm, not a proof of
minimum whole-body motion; demanding fixed upright palm orientations still bend.
Snapshot regression: overlay mean0.101ms/tick for both hands,p950.250ms; native
body mean0.120ms,p950.310ms. Broader837-frame regression: overlay0.178ms,p950.400ms;
native0.728ms,p952.939ms. No many-agent performance claim. Old performance records
remain in the [lab README](Labs/ReachLab/README.md); current evidence is
`Saved/Diagnostics/ReachArmFirst20261015/verification.json` and
`Saved/Diagnostics/ReachCoupled20261015/verification.json`.
**Ready for the user's manual Refresh.** Lab window/server and Unreal/robotics/D/S
were not restarted or changed. No build; only lab JS and handoff docs changed.

**REACH transport:** Restart now sits immediately left of Play/Pause. It resets
pose/grabs/tick and starts playback, preserving current targets, all tuning,
checkboxes, camera and playback speed. Browser-only change; no build.

**Current REACH contact selection:** Auto palm contact now selects the sphere
surface toward the same-side upper-arm bone origin (at the shoulder), replacing
the previous current-palm-centre reference. Uses full3D ball-to-upperarm direction
once per grab; the chosen normal stays ball-local afterward. Upright orientation,
manual rotation mode, tolerances and fitting are unchanged. A versioned automatic
contact key refits older grabs on the next tick after the user refreshes.
Lab left running; user performs refresh. No build or Unreal changes.

**Current REACH mode:** user requested Auto palm contact; both hands' persisted
orientation is now `surface`. It is exposed as one shared top-bar checkbox,
not an orientation-dropdown option; unchecking restores saved absolute rotations.
Toggling Clamp hand rotation releases the balls and immediately restarts grab
requests for enabled hands from their current displayed wrist/elbow transforms.
Body response, complete pose and tick are retained; contact/fitting are recomputed.
Disabled hands stay disabled. This supersedes the release-only/uncheck behavior. Existing target positions, radii, saved absolute
angles, speeds, clamp, tolerances and pose/camera checkpoint were preserved.
Active grab balls now display a gold surface-contact dot and outward-normal
arrow, transported by the held ball transform; shared rendering includes these
markers in live captures and snapshots. Reset pose & targets now resets only
pose/grab/tick and the captured target translations/rotations. It preserves every
checkbox (including mode, reach/grab and view toggles) plus radius, speeds,
tolerances, camera and playback settings.
Only the REACH app window was reopened; robotics/Unreal were not accessed.

**Reach lab ready â€” lab first, port later:** user requested the same rapid iteration
workflow as D/S. [REACH â€” Hand & Body Lab](Labs/ReachLab/README.md) runs at
**http://127.0.0.1:8873/reach**, with desktop shortcut **REACH - Hand & Body Lab**
(distinctive lime hand/purple target). Independent hand checkboxes, RMB target
drag, Shift+RMB depth, orbit/pan/zoom, fixed60Hz pause/step, target rotations,
PHAT wrist snapshot, angle/position readouts and saved JSON+PNG cases. Exact native
body/arm solver source extracted into lab-owned editable `solver.inl`; tiny
standalone DLL builds in seconds, without UBT or Unreal changes. Initial baseline
matches production source; future experiments stay in lab until explicitly ported.
720 kernel frames/2,430 wrist cases/browser interactions pass; actual app window
visible. Initial reach scope has since expanded to the sphere grab pipeline below.
No live complete-overlay physics parity claim. Evidence `Saved/Diagnostics/ReachLab20261015/`.
Unreal13040 remained open; only read-only PHAT export, no Play or asset edits.
Taskbar follow-up complete: launcher uses unique `/reach` path because Chromium's
app identity omits ports; root URLs grouped REACH under D/S. Native browser IDs now
differ, and the live window icon is the lime hand/purple target (ICO favicon).
Only lab server/window restarted through process APIs; saved settings hash unchanged,
D/S and Unreal preserved. No persistent taskbar helper. Read-only identity/icon
verification: `Saved/Diagnostics/ReachTaskbar20261015/`.
**Lab rotation follow-up:** user explicitly says stay in the lab until told
otherwise. Target rotation now uses absolute lab XYZ degrees (`qZ*qY*qX`), with
zero/zero/zero = identity; Follow arm remains available. Schema2 migrates old
idle-relative settings without changing their intended orientation or other
tuning. PHAT remains a snapshot and still clamps the wrist. Verified150 Euler
round trips (including singularities), migration/reload, both-hand identity,
180deg/s pursuit and orientation independence from target translation. Visible
REACH reopened through its launcher; no server/Unreal build or restart. Evidence:
`Saved/Diagnostics/ReachAbsoluteRotation20261015/`.
**Reach lab workspace follow-up:** four small per-hand translation/rotation reset
icons use the user's latest captured values: L13/60/125cm with rotation180/0/90Â°,
Râˆ’14/47/125cm with rotation0/0/âˆ’90Â° (October15 explicit default update).
Canonical `Labs/ReachLab/reset_defaults.json`; also exposed in `/reset-defaults`,
saved settings and live view. Defaults never change during ordinary tuning/restore.
D/S snapshot/refresh workflow adapted: numbered PNG+JSON, restore paused at exact
solver/pose/camera state, JSON import/export, P snapshot, Refresh lab preserving
pending edits/playback, persistent session resume. Worker capture and desktop
identity copied/adapted; `/desktop-view` plus sequence-matched `.png` provide the
actual user's view without computer use; ordinary tabs cannot overwrite it.
Snapshot pixels match the visible framebuffer. Workspace, existing UI and rotation
checks pass. Only REACH server/window restarted; latest user tuning, pose and camera
preserved, Unreal/D/S untouched. Evidence: `Saved/Diagnostics/ReachWorkspace20261015/`.
Reach header simplified at user request: branding removed, Snapshot/Refresh at
top left (the former title position), Reset pose & targets below them, and centered **Clamp hand rotation**
checkbox. This is the existing persisted `settings.phat` switch moved out of the
collapsed wrist section; unchecking bypasses both hands' rotation clamp. Lab only.

**Reach lab grab pipeline complete â€” October15:** both hands now have Grab ball
and one shared persistent **Ball radius** slider below the centered clamp checkbox
(0.5â€“15cm, initially3cm). It updates both balls together; per-hand radius inputs
are removed. Closure/grip angle inputs now stay visible in a fixed footer below
the scrolling hand panel; same persisted8/6-degree defaults and native position/
angle gates. Actual-vs-commanded tracking is identical in this kinematic lab,
whereas Unreal additionally checks its actual physical hand. XYZ is ball centre for
grab, wrist destination for reach-only. Actual30 finger joints from mannequin
reference plus authored closed_fist were exported read-only to `fingers.json`.
`grab.js` ports native palm offset, clearance, contact sampling, one-time curl
fitting, closure and distance/angle acquisition gates. Existing absolute hand
rotations remain; Auto palm contact offers the native surface-normal orientation.
Held balls follow a wrist-relative kinematic fixed attachment while RMB moves
their requested destination. Release opens fingers/returns the arm; resize or
orientation changes refit. Snapshot/refresh/live state include curls, contacts,
closure, ball transforms and attachments. This is the sphere pose/contact pipeline,
not Jolt collision response, gravity or physical tracking; native Kin only marks
grips, while the visual fixed attachment is a deliberate lab extension.
Both saved-default grips pass with PHAT enabled; actual user's latest desktop
also holds both balls, four contact fingers each. Preserved newer left target,
rotations, camera and user's clamp-off setting.14 fitted geometry cases, drag,
release, resize, blocked wrist/unreachable/oversize cases, snapshot continuation,
refresh and inactive retirement pass; workspace and reach-only rotation checks
also pass. Only REACH server/window restarted; Unreal13040 and D/S preserved,
no native build, asset writes or Play changes. See lab README and
`Saved/Diagnostics/ReachGrabLab20261015/`.

**Grab parity clarification:** matching acceptance thresholds does not make the
lab's default Absolute rotation mode the same experiment as Unreal Grab Object.
Absolute mode takes the user's orientation first and selects the sphere surface
normal to fit that palm; native Grab Object takes a surface point/normal first
and derives the hand orientation. A read-only lab comparison from neutral with
the latest saved4cm balls, PHAT on and8/6-degree tolerances acquired both absolute
grips (remaining angles0/5.066 degrees), but Auto palm contact acquired neither
(152.961/166.817 degrees, effectively zero position error after240ticks). This
isolates target-orientation selection as a sufficient blocker in the lab; it is
not a replay of the old map. The old PHAT capture also reached the positions
without acquiring grips. No user settings, Unreal map or robotics work changed.

**Complete â€” grab-angle Blueprint node:** user explicitly requested adjustable
closure/grip acceptance angles (8/6 degrees), not PHAT movement limits. Added
Set/Get Grab Angle Tolerances in the reach library; per-agent settings apply to
both hands, including active grabs. Normal build/restart required by new retained
settings storage. Preserved and saved dirty PoseAgent/TestNN, backed up prior disk
versions; PHAT was already clean. Editor19216 closed gracefully; normal incremental
build succeeded in492.43s,21 actions. Editor25832 reopened TestNN; normal DLLs are
current. Owned Sim check passed: strict0-degree grip blocked acquisition, then180
allowed both physical grips; defaults8/6 unchanged, invalid inputs rejected, agent
isolation and release persistence verified.268 wrist samples stay within PHAT.
Final outside Play/no dirty packages; saved assets unchanged after preservation,
graph wiring unchanged (input-key unused output-default serialization normalized).
Reflection status3/native_properties0/pin_types0. Node is available under
Prophecy â†’ Grab; call Set Grab Angle Tolerances before Grab Object/Grab Bone.
No user Blueprint wiring or default tuning changed. Evidence:
`Saved/Diagnostics/GrabAngleTolerances20261015/`.

**D/S motion is TEMPORARY FINAL, accepted by the user.** Preserve the accepted lab/Unreal motion and tuning; change it only on a new user request. Latest reported Sim slowdown was not reproduced, and the user subsequently said it looked good. The explicit right-wrist limit follow-up is complete; no implementation task remains active.

- **Current review setup:** user removed the continuous D/S branch and requested the October12 two-ball grab experiment on their existing one-shot tick30 branch. PoseAgent and TestNN are now saved locally with two radius3cm spheres assigned to the player. Ball physics prepares at tick29; both Grab Object calls start at tick30,120cm/s and180deg/s. Player sword hides at the trigger; grabs stay held for user review. See [reach/grab review fixture](Docs/ReachGrasp20261012.md). No reach/grasp runtime solver or D/S tuning changes; no commit/push.
- **Wrist-limit follow-up complete:** D/S frees the hand_râ€“lowerarm_r joint's three angular motions through the full return, then restores the exact entry motions/angles through existing completion/interruption cleanup. Retained layouts unchanged. Four owned-PIE checks/498 sampled checks pass, including custom limits, repeated requests and hide during both returns. Full BP graph unchanged; no assets saved/restart. Current user graph starts S during initialization; diagnostic waits for it to finish before its controlled D/S pair. [Wrist-limit lifetime and evidence](Docs/SwordHolster.md#right-wrist-limits-during-ds-october15-follow-up).
- **Reach/grab PHAT follow-up complete:** user requested hand control follow the edited PHAT automatically; explicitly reach/grab only, D/S excluded. Native overlay reads loaded asset wrist frames/modes/angles each active update and constrains hand orientation, including release return. 4,860 math cases and804 live wrist samples pass across Kin reach, Sim reach and Sim ball grabs. Editing an isolated transient PHAT during an active Kin reach updates the clamp without restarting it. **Ball fixture limitation:** both target positions reached, but neither grip acquired by210 under current wrist limits; no success claim for grasp acquisition. User asset unchanged, no retained layout changes/save/restart. [Details and evidence](Docs/ReachGrasp20261012.md#phat-wrist-constraints--october-15).
- **Remote checkpoint:** commit `965b9cb4ac649f8f4ce7604e9a6b5c33588b1536` on `codex/standalone-sim`; annotated tag `ds-temporary-final-2026-10-15`. Branch and tag verified on GitHub. Previous broad D/S checkpoint `b34e1b31` is its parent. Recovery manifest verifies all 5976 recorded files; this is a curated backup, not the whole project/machine.
- **Finger rendering follow-up:** grab calculation was active but LOD1 removed finger bones (`r.SkeletalMeshLODBias=1`). Saved test player's Mesh/PhysicalMesh Forced LOD Model1 (=renderLOD0) in TestNN, matching the original experiment. Attack Fists already enabled; no graph/runtime/global-LOD changes. Kinematic LOD0 finger/model error<3e-7cm; physical native finger poses already present and LOD0 selected with the pre-Play override. Evidence `Saved/Diagnostics/ReachGrabFingers20261015/`; use next Play for the saved override.
- **Editor:** grab-angle implementation required one normal build/restart. Its first launch mistakenly used WindowStyle Hidden; user reported no visible editor. Clean hidden editor25832 was closed and reopened visibly as13040, without another build or asset changes. Use **Normal** for the requested interactive editor/browser; **Hidden** only for background helpers. Latest lab task preserved this running editor. User PoseAgent/TestNN edits saved with prior disk backups; PHAT unchanged. Reflection status3/native_properties0/pin_types0; wiring preserved. Remote checkpoint predates these local assets and does not contain this scene.
- **Build:** normal incremental editor build succeeded in492.43s for the grab-angle node and incorporated preceding Live Coding patches through20. **Normal DLLs are current.** Keep future builds minimal/incremental and prefer reload-safe implementations where appropriate. Do not restart just to tidy, save, inspect or tune; retained native storage/layout changes still require normal build/restart.
- **Last saved asset verification:** PoseAgent compiled status3 and saved with TestNN for the grab fixture. Against the user's live pre-edit full graph, only the existing tick30 Branch's unused Else and its terminal reroute's unused Output gained links;28 nodes added, no existing nodes removed or tuning changed. Both reaches active at absolute30, physical grips90/93, held through220. A_Sword untouched in this task. Native reflection health remains status3, native_properties0, pin_types0. Evidence `Saved/Diagnostics/ReachGrabWiring20261015/`.
- **Local-only work:** TestNN, generated defense pickers, separate MimicKitTraining/PhysicalRecovery work and unrelated PDF remain outside this D/S checkpoint. Do not stage, clean or overwrite another task's work. `ProphecyFKReturnFeedbackTests.inl` has appeared dirty without a semantic `git diff`; inspect before treating it as a new change.
- **Primary references:** [D/S runtime and integration](Docs/SwordHolster.md), [lab controls/recorded problems](Labs/SwordHolsterLab/README.md), [attached-arm physics audit](Docs/SwordHolsterPhysicsAudit20261014.md). Full old opening retained in the [October10â€“15 archive](Docs/Journal/ProjectJournal-history-through-2026-10-15.md); rejected trials are historical, not pending work.

## Accepted D/S behavior and settings

**October15 wrist PHAT follow-up:** user requested wrist articulation in the
separate training model and the same dataset+5% limit coverage. Only hand_r and
hand_l angular limit fields additionally changed: twist/swing2/swing1 degrees
30/23.71/50 and40.86/46.31/50 respectively. Saved PHAT; all other profile fields,
geometry, mass and drives unchanged; dirty PoseAgent preserved. Backup and
verification: [body-matching wrist correction](Docs/MimicKitUEFNBodyMatching.md).

**October15 PHAT limit update (explicit user request):** eight angular profiles in
PA_UEFN_Mannequin now contain the26 accepted retargeted locomotion clips with5%
angular leeway; both ankle twists are limited instead of locked. Shapes, masses,
joint frames, collision exclusions and drives are unchanged. Asset saved through
remote Python; preexisting dirty PoseAgent preserved. Values, backup and numerical
verification: [current PHAT limits](Docs/MimicKitUEFNBodyMatching.md#current-phat-limits--october-15-authorized-omni-expansion).
Existing physical rigs need recreation to import the saved bounds; no user Play
was active and no editor restart/build was needed. D/S code/tuning is unchanged.

D = draw/unsheathe; S = sheathe. The active standalone lab is `Labs/SwordHolsterLab`, normally at `http://127.0.0.1:8818`. Saved tuning is `Labs/SwordHolsterLab/state.json`; Unreal export is `Content/locomotion/SwordHolsterProfile.json`. Do not change the lab silently to make a native test pass. Motion experiments start in the lab; port only when requested. The original Attack Recovery Lab is a separate application (below).

The following are **last saved checkpoint values**, not permission to overwrite fresh user edits. Read the current Blueprint and saved lab before future imports.

| Setting | Drawing | Sheathing |
| --- | --- | --- |
| Max reach speed |260cm/s|230cm/s|
| Max reach angular speed |900deg/s|600deg/s|
| Sliding speed |330cm/s|230cm/s|
| Sliding curve |Linear|Latest saved four-point curve|
| Base FK return duration |.5s|.9s|
| Main return inertia |.5|.7|
| Early return start |90% of outward slide (10% insertion remaining)|70% insertion|
| FKâ†’IK arm-return blend |Enabled, fractions.25â†’1|Disabled|
| Coordinated elbow IK correction |Enabled,15deg soft zone|Enabled,15deg soft zone|
| Independent hand rotation FK alpha |1|1|
| Big-node NN blend range |(1,1)|(0.7,1)|

Other saved values: axial shrink25% over.25s, unshrink.5s; attached hand speed150cm/s and angular speed200deg/s. Big-node grip holster rotation compensation80%, return duration.25s, S kinematic switch fraction.5. Leeway attachment phase disabled; tip tolerance2cm. D hand-local-X turn800deg/s, sigmoid exponent1.5, cutoff.4 of arm return. Negative angular speed reverses it; afterward existing hand return continues. Return durations can include angle-dependent extra time; base duration is not necessarily total duration.

For later user-requested imports, `node Tools/SwordHolster/SyncLabProfile.cjs` exports saved lab settings; inspect its semantic diff before applying. Existing big-node pins override imported values. `Prophecy.Editor.RefreshHolsterGripPins SetSlideSpeeds <draw> <sheathe>` updates only unlinked speed literals; preserve every other pin and compare the full graph before saving.

Latest import changed only S slide speed170â†’230 and its curve's first interior point to(.15053891961839325,.0988776276854313). Other S points: (.650179602563385,.7111385494636496), (.8849101307618773,.9562043029634382), (.9553293659722167,.9884497709488423). D remained330/linear. In the current saved geometry: S18ticks/.30s, D13ticks/.2167s. Duration depends on blade travel/shrink, not a fixed duration override.

### Ownership, timing and mode switches

- Authored seconds use60 unpaused game ticks. NN inference cadence is separate. Reach/slide curves affect only their procedural motion, not underlying idle/walk/run, head or FK return; each D/S return has its own timing curve.
- Reach uses FK, authored spine/clavicle targets and explicit elbow preference. The rejected direct-IK **reach** trial is removed. This is distinct from accepted FKâ†’IK **return** and coordinated elbow IK correction. Old forearm-only bend limiter remains deleted; Main inertia scales strength without shortening duration.
- Geometry comes from authored sword/holster placement and blade marker; apply asset scale once and shrink only along blade axis. Capture references before moving the mount. Holster follows the actual component; compensation rotates about its origin without introducing pelvis-relative translation.
- S aims tip at entrance with angular tolerance. Optional leeway attachment phase first attaches, then aligns the tip within attached speed limits, then slides from the reached depth. It must not reset insertion to0. Holster-relative speed limits are intentional. Current saved leeway phase is off.
- During attached alignment/sliding in Sim, native upperarm_r/lowerarm_r/hand_r temporarily become kinematic and follow the completed actual pelvis/clavicle and holster-local sword path. Remaining body stays simulated. Sword stays attached to holster; no separate predicted sword path or attached handâ€“sword joint. Release restores simulation from current pose/COM/angular velocities and seeds return from actual current/previous arm poses. Ordinary kinematic characters do not receive this native ownership override.
- Holster simulation switches independently; a kinematic agent forces a kinematic holster while retaining its preference. Physical holster temporarily goes kinematic at the configured S reach fraction / during D sliding. Rotation compensation then applies; usual rest return and original joint restoration resume the prior preference. Interruption cleanup restores owned limits, collisions, joints and modes.
- Tab switches Sim/Kinematic without cancelling D/S, restarting clocks/shrink or losing attachment. Kinâ†’Jolt queues the **entire** mode change at the existing safe admission boundary, avoiding an intermediate Chaos step. Rebind waits for native ownership. Completed attached-arm pose is republished at transfer; stale presentation blend is retired. **No added Simâ†’Kin whole-pose fade**: that trial delayed moving actions and was removed.
- A_Sword's consuming Tabâ†’pause event was removed; character Tab works, Caps Lock backend selection is unchanged. RMB debug slowdown now uses `t.MaxFPS`, not fixed simulation delta. All agent/equipment overlap events are disabled in both modes at user request; blocking collision and queries remain.
- D/S suppresses right-arm collision for the action, restores it on completion/interruption, and applies headâ€“clavicle suppression only during D/S. Neck/head and right-wrist angular limits are Free through the full return and restore their captured entry modes/angles afterward. See the physical-neck reference below for permanent neck pairs. Early NN return protects the gripping arm until release; arm return then uses its own clock/window.

### Verification and remaining limits

- Latest slide import:240 consecutive live ticks,3agents, six S/D slides; S18ticks and D13ticks for every agent. Recorded slide fractions match the lab evaluator within4.93e-10. Only the S speed pin changed in the graph. Evidence `Saved/Diagnostics/SlideLabSync20261015/`.
- Sim slowdown report: paired295tick current-scene runs; D release-to-finish38/39/40ticks per agent in **both** modes. Physical hand target error after the first two release ticks at most.11861cm. No slowdown fix was made; user accepted current motion. Evidence `Saved/Diagnostics/DrawReturnSlow20261015/`.
- Mode continuity: seven runs/4065ticks across3agents,111 requests including queued cancellations, actual Tab, moving agents and rapid reversals.16 immediate attached-arm transfers preserve position within6.36e-14cm and rotation<.01deg. Other bodies can still remove ordinary physical tracking error on entering Kin (measured up to1.1773cm/7.0571deg). Evidence `Saved/Diagnostics/ModeContinuity20261015/`.
- Attached-arm audit:123 completed slides/4705ticks, maximum S path error.00004615cm, native/query/display position discrepancy.00000417cm; ten lifecycle cases pass. Full legacy suite was **not** all green: outdated authored/short-return fixtures remain documented. See [audit and receipt](Docs/SwordHolsterPhysicsAudit20261014.md).
- Performance: latest measured attached-arm stage after overlap removal mean.184076ms/p95.2679ms for3agents, sequential editor runs. Earlier.257129ms baseline and scoped-movement-only result remain in [D/S topic](Docs/SwordHolster.md). This is neither total game time nor a100-agent benchmark or10x gain. No new performance work pending.
- Accepted does not mean universally flawless: prior no-switch fixture recorded a~148.53deg upper-arm roll at D release382; it was explicitly reported, not fixed by the Tab work. Historical obstructed running/unreachable-arm cases and variable-step neck test limitations are documented. Do not revive these as unsolicited fixes or widen tolerances to conceal them.

## Other systems to preserve

| Area | Current contract / caveat |
| --- | --- |
| Breathing | [Breathing](Docs/Breathing.md): default upper+pelvis, only at zero movement input; active through D/S. Successive cached idle deltas move actual accepted pelvis/upper pose; legs keep feet in place and NN history receives it. Independent pelvis/upper amplitudes; speed snaps.3â†’1 by.1 using shared pre-baked samples. No presentation-only overlay. |
| Physical neck | [PhysicalNeck20261013](Docs/PhysicalNeck20261013.md): original PHAT23bodies/22joints, neck_01â†’neck_02â†’head, approved capsule size and split neck mass; actual neck_02 feeds NN. Both necks exclude head/clavicles/each other permanently; headâ€“clavicle exclusions only during D/S. Solver comparison option remains available. |
| Get-up | [GetUp](Docs/GetUp.md): remain simulated, restore magnetization; both-arm anti-jiggle until lower handoff then prior independent settings; magnetization0â†’1 at lower marker; slot1 includes PhysicalMesh material. Independent lower/upper handoff/tempering. Automatic floor-lift correction and its toggle were removed; explicit Ground Offset remains. Old tick30 hookup is historicalâ€”inspect current BP. |
| Native reach/grasp | [ReachGrasp20261012](Docs/ReachGrasp20261012.md): Reach Target/Double Reach/Grab Object/Grab Bone, durable local contact point and one joint per hand, fit fingers once. Ball and forehead prototypes tested; lower chin blocked; concurrent attack/get-up ownership not fully tested. Do not silently promote prototype to universally validated behavior. |
| Cosmetic holster strap | [HolsterStrap](Docs/HolsterStrap.md): separate asset/AnimDynamics work, editable ABP body definitions with linked constraints. Does not replace the existing agent holster or D/S. |
| Separate local tasks | MimicKitTraining and PhysicalRecovery files are local work from other tasks. Check their own docs/status before touching; this D/S cleanup neither validates nor stages them. |

## GOLDEN RULES â€” read before touching Unreal

1. **User tick numbers mean Blueprint `absolute tick debug`, never `tick debug`.** Auto-reset resets the latter. Record absolute tick, family, ownership and phase.
2. **Authored seconds =60 unpaused game ticks.** Holds/delays/fades/spreads do not use wall time, DeltaSeconds or30Hz inference steps. Explicit policy-frame controls (e.g. defense Frames After Hit) retain documented policy-frame units. [Timing contract](Docs/BlendTickTiming.md).
3. **Retained native layout changes require a normal build/restart.** Includes PRIVATE structs/classes in static TMap/TSet, heap allocations and nested profiles, not just reflected fields. Even empty containers retain allocations with the old stride. Live Coding cannot migrate them; isolated passing tests do not establish reload safety. Preserve assets, close cleanly, build, reopen TestNN, verify actual Play initialization.
4. **Keep small fixes fast.** No cosmetic/comment/tooltip edits to widely included headers, especially `ProphecyAgent.h`, even after compiling: they force the next task to rebuild dependents. Prefer implementation files and existing narrow libraries. New reflected libraries can also regroup generated/unity files. Do required API changes correctly; avoid unrelated rebuilds/full suites/toolchain edits.
5. **Build workers are automatically dynamic.** Installed UBA adapter recalculates free physical/commit RAM every500ms, default1.5GiB/job with CPU cap. Do not force fixed workers or restart a build to change concurrency. One worker can be correct with low RAM. `Tools/ConfigureBuildWorkers.ps1` reinstalls after engine restore/verification if needed. No custom launcher. [Build-worker contract](Docs/DynamicBuildWorkers.md).
6. **Preserve user work and active Play.** Owned diagnostic Play is authorized when needed for the requested investigation and no user Play exists; no repeated permission question. End only your own sessions. Do not silently stop user Play, restart, alter tuning/wiring, save unrelated assets or restore old backups. Explicit save/reopen requests authorize necessary steps. Preserve requested dirty assets before an authorized restart.
7. **Never cold-launch stale DLLs.** Successful Live Coding patches do not update normal DLLs. Build before reopening when needed; stop if it fails. Explicitly open `/Game/testNN`, not heavy default `/Game/mybasic`. Never remove expected pins/functions to accommodate old DLLs. User rejected a custom launcher; do not recreate it.
8. **User editor uses normal UI flags.** No `-unattended`, `-nullrhi` or automated test commands on interactive launch. Unattended bypassed normal per-monitor DPI setup and caused small fonts. Prefer isolated `UnrealEditor-Cmd -nullrhi -nocef -unattended` automation: interactive automation has previously crashed CEF. Don't change UI scale/render settings to mask it.
9. **Minimize editor closures; use Live Coding when layout-safe.** User explicitly reiterated this on October10. Do not restart for routine inspection/testing or safe implementation-only patches. Retained layout changes still require rule3's normal build/restart; batch necessary changes into one restart and wait for graceful exit before starting UBT. New native global registrations (for example CSV profiler categories) also need cold initialization; October14 Live Coding of a new CSV category crashed at its first captured scope. Avoid reflected WorldSubsystem/Agent reinstancing. Preserve unsaved BP before necessary reflected reloads; keep PIE stopped through patch application, not only dispatch. `LiveCoding.CompileSync` blocks the editor: explain first. Check compile AND reload completion before captures. Adaptive unity stays disabled; ordinary unity remains enabled.
10. **Check existing BP after reflection changes.** Use targeted stale-library-CDO/Agent repairs below, preserving all other defaults/links. Python wrappers may be stale despite valid native reflection. Verify the full graph; don't save a broken BP.
11. **Inactive/disabled/completed means no recurring feature work.** No extra inference/timer/skeleton copy/IK/query/history capture when unused; retire state/callbacks. A cheap guard is not literally zero CPU. Optimize supported behavior without sacrificing correctness.
12. **Measure before claiming a cause.** Distinguish raw NN, accepted future, displayed interpolation and physical mesh. NN Hit is not physical contact. Recurrent changes alter later states: preserve the prefix and intervene just before the symptom, or replay exact inputs. Keep geometry/checkpoints fixed unless changing them is the experiment.
13. **Lab first for motion experiments; port to Unreal only when explicitly requested.** User reiterated this after the mistaken October13 drawing IK implementation.
14. **Quick, concise collaboration.** User prefers their own motion tests unless investigation/testing is requested. Current FK elbow work uses numerical poses/poles, not images. Use remote APIs/scripts instead of taking over the desktop. No routine subagents/exhaustive suites/unsolicited changes. Don't re-ask already-authorized steps.
15. **Curated, bandwidth-limited backup.** Explicit staging only; never `git add .`, LFS transfers, bulk assets, caches or generated model uploads unless requested. Keep all FPS/performance references, especially100-agent benchmarks, during cleanup. No deletion outside authorized scope.
16. **Authored motion is at least root-local, per user.** Overall character turns carry the authored motion; pelvis/spine gait compensation is separate. World-space physics/query output does not justify a fixed-world authoring history. D/S head history and holster stabilization now follow this rule; do not claim every other system has been audited.

## Omni locomotion recording viewer â€” October15

User-requested gallery ready at **http://127.0.0.1:8841/**: 14 walk +16 run clips, each initialized from its matching actual omni animation, then120 NN-only game ticks settle and180 ticks recorded (181 samples,26 controlled bones). Actual current WalkJuly5/Run and Upper82500 contracts retained. Kinematic presented NN output; no physical noise or source-animation playback during capture. Per-frame checkpoint weights, finite poses, input speeds and continuity verified. RR-offset Run source350cm/s is capped at native345cm/s, explicitly retained/disclosed. Initial recorder heading-basis error and scene automatic-Run override were caught and corrected before accepting captures. Six-view synchronized gallery, single view, filter/pages, live scrub and per-tick stepping; existing D/S renderer reused read-only. No engine build/restart, saved asset/wiring/tuning changes or training changes. Editor19216 remains TestNN/outside Play,60FPS; pre-existing dirty PoseAgent preserved. [Procedure, source scripts and evidence](Docs/OmniLocomotionRecordings.md); receipt `Saved/Diagnostics/OmniRecord20261015/receipt.json`. This viewer does not replace D/S lab clips. October15 viewer-only correction: local-Y basis sign now matches the shared renderer; facial features no longer appear on the back of the head. Recorded transforms unchanged. User accepted the cuts; gallery now excludes Run LL/RR and Walk LL/RR (26 displayed:12walk/14run, offset variants retained). Original30 recordings retained. Best full-stride cuts selected for all30 motions; viewer defaults to unblended cut playback with an original-capture toggle. No cuts exceed the documented review thresholds; exact indices/metrics in loop-cuts.json.

## Tools and safe build/reopen sequence

| Item | Location |
| --- | --- |
| Workspace/project | `C:/Users/singerie/Documents/Unreal Projects/Prophecy/GameAnimationSample3.uproject` |
| Target/engine | `GameAnimationSample3Editor` / `C:/Program Files/Epic Games/UE_5.7` |
| Main BP/native class | `/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent` / `AProphecyAgent` |
| Map | `/Game/testNN` |
| Python | `C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe` |
| Remote runner | `Tools/RunUnrealRemote.py` (preferred tracked copy) |
| Current launch log | `Saved/Diagnostics/HolsterAttachmentAudit20261014/editor-after-profiler.log` |
| Default editor/build logs | `Saved/Logs/GameAnimationSample3.log` / `%LOCALAPPDATA%/UnrealBuildTool/Log.txt` |
| Git | `https://github.com/DTSwink/Prophecy.git`, `codex/standalone-sim` |

Read scripts before reuse: some start/end PIE, mutate actors/CVars, compile/save/repair or quit. Explicit UTF-8 file I/O. From project root:

```powershell
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/RunUnrealRemote.py Saved/Diagnostics/YourScript.py
```

Useful remote APIs/commands:

- `unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()` checks Play; `.get_editor_world()` checks map.
- `unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Editor.LiveAgentTypes Inspect')`; report `Saved/Diagnostics/LiveAgentTypes-Inspect.txt`. Healthy: status3, native_properties0, pin_types0.
- `Prophecy.Editor.RepairLibraryDefaults` repairs archived library CDOs; `Prophecy.Editor.LiveAgentTypes Repair` repairs exact stale Agent types. Targeted repairs, not routine edits.
- `Prophecy.Sword.AuditCollisionGraph` writes full BP graph to `Saved/Diagnostics/SwordThigh/BlueprintGraph.txt`. Compare before/after; normalize only known irrelevant reflection paths, never meaningful defaults/links.
- `unreal.BlueprintEditorLibrary.compile_blueprint(bp)` then `unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False)` saves only requested BP. Back up existing bytes; preserve unsaved user work first. Compiling is not saving.

For an authorized restart: preserve dirty assets, close cleanly (never force-kill unsaved editor), then:

```powershell
& 'C:/Program Files/Epic Games/UE_5.7/Engine/Build/BatchFiles/Build.bat' GameAnimationSample3Editor Win64 Development '-Project=C:/Users/singerie/Documents/Unreal Projects/Prophecy/GameAnimationSample3.uproject' -WaitMutex -FromMsBuild
```

Do not add `-NoLiveCoding`: it changes definitions and can rebuild broadly. After success, launch directly:

```powershell
Start-Process 'C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor.exe' -ArgumentList '"C:/Users/singerie/Documents/Unreal Projects/Prophecy/GameAnimationSample3.uproject" /Game/testNN -NoSplash'
```

Verify reflection/BP after launch; repaired Play crashes require actual Play verification. Startup restore/low-space dialogs can block remote discovery. Preserve autosaves/metadata; don't assume recovery happened or overwrite newer work with older backups. Diagnostic callbacks need timeout/error cleanup, CVar restoration, owned-session checks and data release. Physical rigs need actor ticking: tick-disabled fixtures must first switch all involved agents to Kinematic.

## Attack FK return and Attack Recovery Lab

- **Last recorded active Attack Recovery Lab:** `C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab`. `Labs/AttackRecoveryLab` is the portable backup, not necessarily the active server. Never overwrite live `state.json` from a stale backup.
- Server `http://127.0.0.1:8817`; `/desktop-view` has top-level `state`, `displayedPose`, `sequence`, identity/fingerprint, not nested `view`. Check freshness/client identity. Numbered snapshots are historical. [Capture/API instructions](Labs/AttackRecoveryLab/README.md).
- UE first slashLD =lab **variant21**, absolute61â€“101,21 unique30Hz policy frames from41 ticks,25 bones, excluding physical response/post-attack return. UE XYZcm -> lab XZYmetres; imported UE variants bypass harness forearm-roll repair. Original320 variants unchanged. Backup includes current saved lab profiles/view.
- Accepted original FK return with inertia, **not optional continuous spring**. Idle is real Unreal `M_Neutral_Stand_Idle_Loop` frame0, same across attacks, parent-local. Hand local inertia zero, parents still move hands. Spine01â€“05 share one weight, arms symmetric. Main inertia, bone weights, return/easing/timing are per attack. Spine angle adds flat seconds (.29s/90deg default), independent of base duration.
- **Remove upperarm twist inertia:** per attack, symmetric,0original/1full axial removal. Decomposes finite added inertia about actual shoulder-to-elbow axis, preserves swing. World mode carries correction into forearm/hand preserving local rotations. No angle clamp/forced downward elbow. Skipped after completion/zero inertia. Rejected90deg limiter/controls removed.
- Native **Set Attack FK Return Twist Inertia** changes only this field; Attack None means all families. Separate Values/Inertia Profile setters preserve it; legacy combined setter replaces the whole profile. Reset preserves captured configuration. [Return contract](Docs/AttackFKReturn.md), [separate controls](Docs/FKReturnSeparateControls.md).
- **Last verified attack slashLD tuning (October9; re-read current BP before changes):** return .39s, inertia .18, easing0, inertia hold .08, decay .8, world=true, angle addition .29s/90deg, twist removal .98. Weights spine .31 / clavicle1 / upperarm1 / lowerarm .36 / neck01 1 / neck02 1 / head1. Other15 profiles/idle unchanged. BP **NN AlphaHold .17 / Trim0** retained: different from inertia hold .08. Legacy/Values slashLD override nodes disconnected at verification; re-read if user changes BP.
- Parity:321 variants;2568 pure samples max .000207684cm/.000281378deg;6010 unchanged-winding runtime samples max .001155359cm/.000269452deg. Conditional slash winding separately redirects problematic inward arcs; don't promise identical curves under all UE modifiers.
- Files: `ProphecyFKReturn.h`, `ProphecyFKReturnMath.h`, `ProphecyFKReturnData.h`, `ProphecyFKReturnLibrary.cpp`; exporter `Tools/NN/ExportFKReturnLab.cjs`. **Don't overwrite all native profiles with a whole-lab export for one attack.** Check other rows/idle byte-identical. To recreate the ignored parity fixture safely on a fresh checkout, use `node Tools/NN/ExportFKReturnLab.cjs --reference-only`; it reads accepted native profiles without writing them and produces `Saved/FKReturn/lab-reference.json` needed by the parity test.

## Current combat contracts

Read current source/topic docs and actual BP pins for enabled settings. Defaults are not necessarily scene settings. Specials =full/half attacks and active Parry/Dodge; queued defense remains locomotion. Policy cadence30Hz differs from authored60-tick seconds.

| Area | Current reference and key caveat |
| --- | --- |
| Attack lifecycle/counters/bones/kicks | [AttackControls](Docs/AttackControls.md), [SlashBlueprintUsage](Docs/SlashBlueprintUsage.md). Active Trigger retargets without restarting. Kicks ignore half requests; experimental kick half regime removed. Previous Attack Name updates on end. |
| Half reach/ghost | [HalfAttackGTInitialization](Docs/HalfAttackGTInitialization.md), [GhostAttackLean](Docs/GhostAttackLean20261008.md). Upper AND lower ghost share compensated/clamped target. Older upper-only descriptions superseded; minimum reach defaults30cm horizontally about pelvis. |
| Ghost loco | [GhostLocoDrag](Docs/GhostLocoDrag.md). Independent undragged history stabilizes shared pelvis/upper; real feet keep drag and pelvis inertia. General/kick-specific inertia independent; kick run NN sees ghost kicking leg. |
| Attack motion/feedback | [AttackMotionInertia](Docs/AttackMotionInertia.md), [AttackNNFeedback](Docs/AttackNNFeedback.md). Preserve optional filters/legacy feedback defaults. No silent vanilla-fidelity rewrite; new specials cancel outgoing recovery. |
| Defense inputs/order/ghost | [NNDefense](Docs/NNDefense.md), [LiveDefenseControls](Docs/LiveDefenseControls.md), [DefenseInputGhost](Docs/DefenseInputGhost.md). Attacker accepted output before defender; visualize accepted defender body and actual pelvis/collider history, not physical-pose substitutions. |
| Defense start/end | [DefenseStartThresholds](Docs/DefenseStartThresholds.md). Current nodes use per-attack integer **Start Delays after Armed**, default0; raw Hit thresholds replaced. Post-Hit/max-duration/end/manual-stop settings retained. Movement input changes root window, not defense state. |
| Defense returns | [LiveDefenseControls](Docs/LiveDefenseControls.md). Legacy upper spring and separate lower tempering for Dodge; independent optional FK return for Parry. Don't mix attack/Parry profiles. |
| Defense collision | [DefenseCombatRules](Docs/DefenseCombatRules.md). Dodge excludes relevant attack bodies plus held sword for all families, only attacker/dodger pair. Parry protects BP trunk+both arms by zero contact inverse mass/inertia against attack bodies. Welded identity/sweeps respected; release on end/reset. |
| Sword phases/sweeps | [SwordAttackCollision](Docs/SwordAttackCollision.md), [JoltPHATSweeps](Docs/JoltPHATSweeps.md). Accepted sweeps initiate from sword on six slash families. Right punches exclude sword attack role and suppress its victim collision Armed->End. No universal penetration-free promise. |
| Arms anti-jiggle | [ArmsAntiJiggle](Docs/ArmsAntiJiggle.md). Opt-in each arm, defaultoff, solver motors. Suppressed **Armed->End for sword attacks only**, not Armed->NN Hit. Timed disable composes, retains asymmetric choices. |
| Sword no reaction | [SlashSwordNoReaction](Docs/SlashSwordNoReaction.md). Automatic slash Armed->End suspends during victim defense; Strength0..1. Manual override wins; defaultoff. Not blocked-sword stabilization. |
| Snapshots/magnetization | [PhysicalProfileSnapshots](Docs/PhysicalProfileSnapshots.md). Actual special entry restores slot1/cancels relevant pending blends; queued defense not active. Per-bone/below, hold-outs and delayed tolerance supported. Anti-wobble experiments reverted. |
| Reset/regional ends | [AgentReset](Docs/AgentReset.md), [RegionalSpecialRecovery](Docs/RegionalSpecialRecovery.md). Full->half emits lower end; upper return on upper end. Reset wins; arbitrary BP timers/variables aren't universally reset; reacquire recreated equipment. |
| Root/camera/trajectory | [RootSelfBalancing](Docs/RootSelfBalancing.md), [SlashFootContactsAndCamera](Docs/SlashFootContactsAndCamera.md), [ComputeCatchUp](Docs/ComputeCatchUp.md). Player-only camera/handoff; impulse/spread delays tick-based. Unreachable catch-up10000/false with naive pursuit velocity. |
| Diagnostics | [NNModifierDebug](Docs/NNModifierDebug.md). Paused one-tick report persists. Potential constraints aren't measured deltas. Raw Armed/Hit getter returns-1 inactive. |
| Checkpoints | [UpperCheckpointPicker](Docs/UpperCheckpointPicker.md), [AttackCheckpointComparison](Docs/AttackCheckpointComparison.md), [DefenseCheckpointPickers](Docs/DefenseCheckpointPickers.md). Dodge154546 Post-hit return5 / Free pelvis added to enum/path/staging and frozen export October11; was recorded as pending native compile/reload in that side task. Subsequent D/S builds are not evidence of explicit picker validation; check its topic and current reflection before relying on it.17 export parity batches passed (max1.55e-6); raw `Saved/Diagnostics/Dodge15454620261011/export/`. Read current selection; old defaults are not authoritative. No training watcher. |

**Keep performance references:** [DoubleReachPerformance20261008](Docs/DoubleReachPerformance20261008.txt), matching JSON and raw `Saved/Benchmarks/DoubleReach20261008/final/`. Direct native won and user chose direct. CPU reaching cost only, not total FPS. [Jolt performance](Docs/JoltAcceptedPerformance.md). Blood/native-Niagara migration and multiplayer aren't implemented by these tasks; historical proposals aren't accepted features.

## Push, restore and maintaining this handoff

- October18 scripts follow-up: scoped source/tools/docs for reach/grab, REACH lab,
  explosion/impact, VDB and bomb fuse/fragments/fade. No editor save/restart or
  current content assets, full captures, binaries or caches included. Separate
  robotics/training staging is preserved. Recovery inventory is regenerated for
  the selected tree; see Docs/Recovery.md for external dependencies and limits.

- Lightweight push: source/tests/scripts/docs, lab code/captured variant/saved profiles, freshly saved PoseAgent BP. Current TestNN map modification, generated defense pickers, unrelated PDF, binaries/caches/full captures remain local. Older tracked maps/models remain recoverable, not a promise of today's exact scene.
- `.gitattributes` stores curated assets as real Git blobs. No LFS uploads; explicit staging and size inspection. Set process-local `GIT_LFS_SKIP_PUSH=1` for the push (the legacy pre-push hook still invokes LFS); don't remove hooks or alter global settings. After staging, `Tools/Recovery/VerifySnapshot.py --write-index`, stage `Tools/Recovery/Snapshot20261003.json`, commit, verify `VerifySnapshot.py HEAD`, push `origin codex/standalone-sim`, compare remote HEAD. Manifest filename retains legacy date; inventory must match latest tree.
- [Recovery](Docs/Recovery.md) covers omitted external assets, dependencies, original checkpoints and standalone shortcuts. Repository isn't a full laptop backup. Milestone receipts: `Tools/Recovery/Receipts20261009FK/`.
- [Full pre-cleanup history through October9](Docs/Journal/ProjectJournal-history-through-2026-10-09.md) preserves earlier investigations/domain references. Historical prose is preserved; Markdown links were adjusted for the archive location. Older archives remain under `Docs/Journal/`. Historical pending builds/PIDs/scene settings aren't current instructions.
- [Full October10â€“15 handoff history](Docs/Journal/ProjectJournal-history-through-2026-10-15.md) preserves every superseded opening entry and previous build/save/test claim. Read current summaries first.
- **Update current sections instead of prepending endless logs.** Keep build coverage, saved assets, defaults versus actual BP, evidence and limits explicit. Detailed experiments belong in linked topic docs/receipts. Archive superseded behavior, preserve user corrections, and never revive an old investigation as unsolicited work.


