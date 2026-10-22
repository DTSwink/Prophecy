# MimicKit humanoid trial

## October22 13:11 - shared maximum pelvis speed correction

User correction: front can roll into back. ALL perturbed and perturbed+ get-ups
now use the maximum of both reference peaks:1.4951565265655518m/s (149.516cm/s).
This supersedes the preceding per-motion thresholds. Runtime validates both
reference peaks then broadcasts their maximum to both motion IDs. World XY
horizontal/Z vertical and pelvis-origin velocity unchanged. Future package
preparation corrected too; config limit_mode=shared_maximum_over_both_getups.

RUNNING20261022_131128_uefn_getup_pelvismax7_1024 on existing L4
0to3wg3r3n926h,$0.59/hour,1,024agents until stopped. Resumed latest130296_final
(2,631,417,856samples), locally preserved under
Saved/MimicKitEquipment/preserved-latest/20261022_124925_uefn_getup_pelvis7_1024/.
Local/S3 checkpoint SHA2203f55ee65f3fc8edba811d792485abd7a4de2cf29a5fadba872efd3d5aa05d
verified before restart. Optimizer/normalizer restored; all other settings,
including existing foot/AE weights, unchanged. Locomotion branch untouched.

Fixed weight recalibrated to0.30317221303099545 for7% of combined physical loss
at calibration, excluding terminal rewards. Same256world/192tick frozen-policy
procedure: existing loss mean1.820573091507,raw excess mean0.451995193958.
Verified shared threshold for both motions in calibration and all18perturbed
replay rows; normal masks/actual rewards correct. New130297persistent backup
SHA12fea0921cbd5b397de0e261fdb91234706947e02daef6c64d56d1edf861c679 verified;
training advanced130297->130307 at15,152transitions/s. Watchdog released after
verification. Bridge19052/dashboard22240; old recovery observers8240/5428 stopped.
Replayer and TB retain pelvis_horizontal_speed_excess label.

Receipts getup-pelvis-max-{preserved,calibration,verification}.json; source
getup-pelvis-max-source.zip SHA 703b2f574be6198e0cc6cd0d505cec0a3a28af9b01515b0c6f77085249cd5bc1. Helpers restart_getup_pelvis_max.py
and calibrate_getup_pelvis_max.py; getup-success-prepared.json updated.

## October22 - local live idle impulse viewer

Ready, initially PAUSED: http://127.0.0.1:8850/ . Implementation and restart
command are in Labs/MimicKitIdleLive/README.md and start.ps1. Frozen locomotion
checkpoint0122776 from20261022_104557_uefn_locomotion_pelvis_velocity5_1024,
SHA256 4d1c2ae0a2cb7dde540fd2859c43de2c164f997a99cf83dce786c8155f23d591,
preserved under Saved/MimicKitIdleLive with pinned source, config and assets.
No training, cloud pod, recovery branch or Unreal state was changed.

Single local CPU native MuJoCo agent, configured240Hz physics/30Hz policy,
saved normalization/action scaling/torque caps. Real idle command with selectable
unarmed/drawn stance, deterministic actor and autoregressive phase feedback.
No AE, reward or learning work, and no automatic failure reset or pose pinning.
CPU trajectories need not be bit-identical to GPU training.

Choose/click any body, select world direction and strength0.1-10m/s, apply
impulse. Strength means directional body-COM velocity change; effective mass
from the articulated mass matrix/Jacobian makes it independent of limb mass.
Verified1m/s for hand0.812kg, foot2.161kg and pelvis16.454kg; UI2m/s kick and
both idle stances checked. Subsequent contacts/motors react normally.
Pause cancels stepping and continuous rendering; hiding/leaving tab pauses too.
Backend is request-driven without a physics worker; model remains resident.
Verified unchanged tick count while paused and live30.18policy ticks/s over a
3second wall-clock sample. Receipts: Saved/MimicKitIdleLive/verification.json.

## October22 12:49 - recovery pelvis horizontal excess-speed loss

RUNNING `20261022_124925_uefn_getup_pelvis7_1024` on L4
`0to3wg3r3n926h`, $0.59/hour until stopped,1,024agents. Resumed latest129835_final
(2,616,311,808 samples), optimizer/normalizer restored. Prior final checkpoint
saved locally under preserved-latest/20261022_122519_uefn_getup_feet7_1024/ and
S3-readback/ZIP/SHA verified before restart. SHA256
2b4198a7259278d4da8a9d7a5b9e137147789cc1fa7dd26abdf66f390cea506b.

User requested a loss above reference peak pelvis horizontal velocity, calibrated
to7% of total loss, and explicitly requested axis verification. Scope continues
the previous regularizers: ordinary perturbed and perturbed+ get-ups only.
Normal get-ups and the separate locomotion run unchanged.

Verified physical axes: world X/Y horizontal, Z vertical; live gravity
[0,0,-9.81]. Replayer WORLD_TO_VIEW converts physics Z-up into display Y-up.
Use pelvis BODY ORIGIN velocity from absolute_walk, already corrected from
engine world COM velocity by subtracting omega cross rotated COM offset. Do
not substitute raw engine get_root_vel/get_body_vel without this correction.
Reference uses root-position forward difference times30FPS, exactly MotionLib;
final velocity duplicated. Whole-clip yaw alignment preserves horizontal norm.
Front peak0.47284913063049316m/s at sourceframe24; back peak1.4951565265655518m/s
at frame17. Reference asset checksums saved in getup-pelvis-reference.json and
config. Startup validates peaks against the actual recovery motion library and
gravity; recompute the reference table if either authored motion changes.

New `pelvis_horizontal_speed_excess` =
0.11446152133224635 * max(sqrt(vx^2+vy^2)-assigned_motion_peak,0)^2.
No velocity cost below threshold, no vertical component, no new termination.
Fixed weight calibrated with latest frozen policy/current exploration,256worlds,
192ticks,34,368perturbed samples. Existing loss mean1.79974889755 (including AE
and both foot costs), raw excess mean1.18349790573; weight=(.07/.93)*base/raw.
New term contributes7% of combined physical loss at calibration, excluding
terminal bonuses/penalties. Existing foot/AE weights unchanged; fractions may
change during learning. Both current perturbed cohorts included, no new grace.

Verified pure-Z and changed-Z invariance, X/Y equivalence, zero at/below limit,
correct body-origin calculation, masks, actual reward including all new/old
costs and terminal adjustments. New training advanced129836->129846 at
15,091transitions/s. New checkpoint129836 passed persistent SHA256 readback.
All18perturbed replay rows contain the new active loss and correct per-motion
limit; normal rows zero. Replayer label Pelvis horizontal speed excess and live
TensorBoard loss/pelvis_horizontal_speed_excess verified. New local bridge21084,
dashboard8240; old recovery observers23984/3092 stopped. Setup watchdog released
only after training progress, new verified backup, and replay reward checks.

Receipts getup-pelvis-{reference,preserved,calibration,verification}.json in
Saved/MimicKitEquipment. Source getup-pelvis-source.zip SHA256 7d431be36ae057395887d3bd6a4a6b9aac0bd27f95bcd6d1720c04d369cfebbc.
Helpers Labs/MimicKitTraining/{getup_pelvis_speed,calibrate_getup_pelvis,restart_getup_pelvis}.py.
Runtime package changes only prepared/env_config.yaml and pipeline/perturbed_omni.py,
plus calibration receipt. Foot reward indexing now uses names so appending the
new term cannot double-count/drop existing costs. Physics, proportions, LR,
noise, GAE, success/failure and other loss settings unchanged.

## October22 12:25 - recovery foot regularizers, resumed and verified

RUNNING `20261022_122519_uefn_getup_feet7_1024` on existing L4
`0to3wg3r3n926h`, $0.59/hour until stopped, 1,024 agents. Latest prior
checkpoint129347_final (2,600,321,024 samples) preserved locally and persistent
S3 SHA256 verified before restart. Optimizer and observation normalizer restored.
Local checkpoint: Saved/MimicKitEquipment/preserved-latest/20261022_104951_uefn_getup_perturbed_plus_1024/checkpoint_0129347_final.zip.
SHA256 33e97b6d5480fc58b3e6c5cf2477d70ce6b2d769108b146502de4f30366795e3.

User-confirmed 7% EACH: two new losses apply only to ordinary perturbed and
perturbed+ get-ups. `feet_target_velocity` is the mean squared actual clamped
ankle motor target angular velocity across six DOFs, rad^2/s^2. Its weight is
0.006859699331106141. `feet_idle_local_rotation` is the mean squared shortest
rotation angle of each foot relative to its calf, compared with assigned idle
frame0, rad^2. Its weight is 0.11904574395704297. Quaternions are sign-invariant;
whole-body rotation does not affect the local rotation term. Both costs subtract
from the actual perturbed reward, including the linear-reward override.

Weights are FIXED, calibrated on the latest frozen policy with existing noise:
256 worlds,192 ticks,34,368 perturbed samples, both perturbed cohorts. Existing
pose+AE mean1.56536317, raw velocity18.57417870, raw rotation1.07028842. Each weight
is (0.07/0.86)*existing_mean/raw_mean, giving 7% each of combined physical loss
at calibration, excluding terminal bonuses/penalties. Fractions may change as
learning improves; there is no dynamic renormalization that cancels improvement.
Normal rows receive exactly zero new costs. Locomotion branch untouched.
Physics, AE weight, success/failure rules, distributions, LR/noise/GAE unchanged.

Verified geometry/sign invariance, physical command indexing/clamping, normal
masking, and exact recorded reward including new terms and terminal adjustments.
New training advanced129348->129358,15,184 transitions/s; new checkpoint129348
passed persistent SHA256 readback. First20-row replay and live TB contain both
new terms. Replayer labels: Foot target velocity / Foot local rotation. Also
corrected stale AE-disabled label when the active loss list includes motion_prior.
Local observers bridge24408/dashboard23984; superseded recovery dashboard stopped.
Ten-minute handoff watchdog extended by a bounded three-minute startup grace;
released only after advancing training, verified new backup, and replay checks.

Receipts: getup-foot-{preserved,calibration,verification}.json in
Saved/MimicKitEquipment. Source archive getup-foot-source.zip, SHA256 a06ce8482714e6265bbb2444525d2e684afb2252e27c90b3f5961ba69cd5e3dc.
Helpers Labs/MimicKitTraining/{getup_foot_regularizers,calibrate_getup_feet,restart_getup_feet,test_getup_foot_regularizers}.py.
Only pipeline/perturbed_omni.py, pipeline/observe.py and prepared/env_config.yaml
changed from the exact previous recovery source, plus the calibration receipt.
Current plan getup-success-prepared.json points at this source and checkpoint.

## October22 10:53 - recovery resumed after funds outage

Latest recovery checkpoint127054 (2,525,184,000 prior samples) downloaded from
persistent storage and locally ZIP/SHA256 verified before restart. Preserved at
Saved/MimicKitEquipment/preserved-latest/20261022_013025_uefn_getup_perturbed_plus_1024/.
SHA32557599472f4477445da687dbc1b09a00f5e248eb09ba40bbc0b73cca90dea0.
Old L4upszb03gy35fzj could not restart because its GPU was reassigned; retained
pod/disk left intact. Replacement L4 0to3wg3r3n926h at $0.59/hour, until stopped.
New run20261022_104951_uefn_getup_perturbed_plus_1024 resumes exact source
0428e568eaff and checkpoint, optimizer/normalizer, 1024 agents and all existing
settings. No learning-setting changes. Ten-minute setup watchdog released only
after training advanced127055->127065 and first checkpoint127055 passed persistent
SHA256 readback. Throughput15,489 transitions/s. First replay127055 and live TB
cards verified. New bridge21960/dashboard18340; stopped superseded recovery
observers only. Locomotion was concurrently restarted by its own chat on
leuh8va7hfcevy as20261022_104557_uefn_locomotion_pelvis_velocity5_1024; its live TB
points verified, no changes to that restart. Both prior latest checkpoints also
preserved locally. Receipts funds-resume-prepared/launch/verification.json in
Saved/MimicKitEquipment. Helper resume_after_funds.py preserves exact prior args.

## October22 - locomotion resumed after account funds shutdown

Runpod stopped q764mqd40pabiq at08:00UTC when funds ran out. User requested
resume unchanged. Latest persistent119475 checkpoint (07:58UTC),
2,409,365,504samples, downloaded locally and ZIP/SHA256 verified:
b08240a5064bedea9be4af53f8903adfb47c4d8714551a39ff70145216df5665.
Saved under Saved/MimicKitLocomotion/preserved-latest/20261021_231729_uefn_locomotion_pelvis_velocity5_1024/.
Old host refused restart for insufficient GPUs; retained pod/disk preserved.
Replacement L4leuh8va7hfcevy at$0.59/hour, SSH157.157.221.29:29875.

RUNNING20261022_104557_uefn_locomotion_pelvis_velocity5_1024,1,024agents until
stopped. Exact previous source archive534659c4cd91e3ed7de4d7b8707ba711f34725e5aaec2c05e611d41e02b3f846
restored; no loss,physics,sampling or optimizer-setting changes. Pelvis velocity
MSE x5 and soft extremity-speed loss retained. Optimizer/normalizer restored.
Verified119476->119486, early15,822transitions/s after startup. New119476backup
readback verified SHA dc647d3975d28d122c0bdc78bb00ed915469d6f02ef8bc62e7a434ed0d528b0f.
Setup guard released after advancing/backup; trainer498/exitguard499,
bridge18400/dashboard13308. Old local observers stopped; recovery untouched.
TB10-45-57, events publishing. Receipts Saved/MimicKitLocomotion/funds-resume-*;
helper resume_loco_after_funds.py. Old pod state archived in retained-pods/q764mqd40pabiq.

## October22 09:20 - both current TensorBoard experiments refreshed

Both telemetry SSH streams had stalled for roughly half an hour. Restarted only
local bridges (recovery18196,locomotion13148), preserving30second polling, and
locomotion dashboard6520. TensorBoard8035 cap10 unchanged. Verified visible
get-up failure points through2,489,794,560samples and locomotion failure points
through2,369,716,224samples,51/57seconds old. Both remote runs remained training;
no trainer/GPU restart or settings changes. Receipts tb-refresh-both-20261022.json
in each branch's Saved directory. Opened filter for both current experiments.

## October22 morning - locomotion TensorBoard caught up

Locomotion bridge/dashboard had stopped locally while the L4 kept training.
Restarted only those observers and backfilled original event history. Verified
live TensorBoard8035 speed-excess and locomotion-failure cards through
2,324,168,704samples,17seconds old. Opened current23-17-29 run; previous browser
filter22-48-04 referred to the superseded run. Training and recovery untouched.
Restored usual30second bridge polling after catch-up; latest10run TB cap retained.
Dashboard now skips replay-history scans for training_outcomes runs, whose cards
already use full-batch event counters. This avoids needless startup parsing and
does not change card values. Observer PIDs/receipt:
Saved/MimicKitLocomotion/tb-refresh-20261022.json.

## October22 morning - TensorBoard refresh after local observers stopped

Restarted recovery telemetry bridge/dashboard and capped TensorBoard8035 server
(latest10runs). Backfilled missing event history and verified both normal and
perturbed get-up failure cards through2,445,230,080samples, about25seconds old.
Remote training remained running, no restart or configuration change. Returned
bridge to its usual30second polling after catch-up. Current observer PIDs and
verification receipt: Saved/MimicKitEquipment/tb-refresh-20261022.json.

## October22 - scheduled perturbed+ recovery switch completed and verified

Resumed current recovery from checkpoint0113353_final, 2,076,229,632 samples.
Saved under Saved/MimicKitEquipment/preserved-latest/20261021_200623_uefn_getup_pelvis_ceiling_1024/;
local ZIP/checksum verified against persistent backup SHA
21f08946ee8f0c7a3b20ae45f3ad63b988c110b958e214df30c882a18610981d.
New run20261022_013025_uefn_getup_perturbed_plus_1024 uses same L4upszb03gy35fzj,
$0.59/hour,1,024agents until stopped. Locomotion branch untouched.

Fixed cohorts:307 normal,359 ordinary perturbed,358 perturbed+ (179 front/179
back). Normal front154/back153; ordinary front179/back180. All prior pose/reset
settings retained. Every plus reset samples pelvis-origin world linear velocity
from locomotion frame A and local joint DOF velocities from a separately sampled
different frame B. Whole-body angular velocity uses an independent uniform sphere
axis and magnitude uniform0–700deg/s, converted to radians/s. Root linear engine
velocity includes omega cross rotated pelvis COM offset, so the body-origin speed
matches the dataset even with the independently sampled spin. Actual Newton FK
and native engine reset validated this conversion, all sampled joint velocities,
different frame indices and spin bounds on the L4 before launching training.
Only plus rows delay the existing head<=50% failure from tick80 to100. Pelvis
ceiling still starts after tick5; success gates,180tick maximum,AE,losses,penalties,
optimizer,normalizer and normal get-ups unchanged. No added physics pass; random
sampling and velocity assignment run only at reset. Source archive differs only
in perturbed_omni.py and three env-config keys; other config compared identical.

20,000 sample CPU check and actual reset/done methods passed, including80/100
boundary flags and terminal100penalty. Full1,024world GPU preflight passed.
Training advanced113354->113364 at early14,959transitions/s versus preceding
15,532; this is an early measurement with harder starting states, not an isolated
overhead benchmark. First113354checkpoint persistent readback verified SHA
d95d2cc16914318cae2453028a688e68c9c00ff84f8f8e15566f9a4420fb3106.
Recorded first20rows include9plus starts whose actual velocities match metadata
and sampled source frames. All plus/ordinary head-check metadata verified100/80.
Replayer labels now distinguish perturbed+. TB and replay bridges publish.
Trainer1556/exitguard1557,bridge19832/dashboard30744. Handoff watchdog released
only after advancing training and verified backup. Initial SSH source upload
timed out; direct persistent download succeeded and source checksum was verified.
Source SHA0428e568eaffb26baf24800d9361ca8288cfb4a57068c96474e39b1b7dec8793.

One-time heartbeat switch-half-of-perturbed-get-ups-to-perturbed is PAUSED after
completion. Plan perturbed-plus-switch.json marked complete. Receipts:
plus-preserved.json,getup-plus-method-tests.json,getup-plus-verification.json;
helpers getup_perturbed_plus.py,restart_getup_plus.py,preflight_getup_plus.py,
test_getup_plus.py,verify_getup_plus.py. Restart helper is scoped to this handoff.

## October21 - pelvis velocity MSE x5 on every locomotion-branch row

User explicitly selected the existing 3D pelvis linear-velocity MSE, not a new
direction-only loss. Multiply body0's contribution by5 while retaining the
15-body/3-component mean, original linear weight3.2992958902731857 and existing
early-MSE/handoff coefficient. Normal/perturbed idle/loco all receive it; other
bodies and losses unchanged. Config all_rows_pelvis_velocity_mse_multiplier=5
under perturbed_motion; default1 preserves other branches. Recorded in the
existing linear_velocity_mse term and replay metadata. No additional physics or
AE pass. Actual-method tests pass54 axis/body/tick combinations across all four
row cohorts. Exact prior source archive patched; unrelated shared recovery
changes were not deployed.

Latest99574_final /1,757,249,536samples preserved locally and verified by
persistent SHA256 readback: a312af658a9c4e6f5713c203f0785a552b1b4f44509d7d380cfa3fced89a6440.
Launched20261021_231729_uefn_locomotion_pelvis_velocity5_1024 on same
L4q764mqd40pabiq,1,024agents,$0.59/hour until stopped. Verified99575->99585
at18,565transitions/s; optimizer/normalizer restored. New99575backup verified
SHA1dfe640df3e49953510ed2fe23e42a90451f4565e3f1e640c61faf9794bad23d.
All20replay rows reconstruct the weighted linear MSE within6.18e-7, including
normal/perturbed idle/loco and early/handoff/full-MSE frames. Handoff watchdog
released after progress and backup verification. TB23-17-29.
Trainer1252/exitguard1253,bridge7452/dashboard24816. Source SHA
534659c4cd91e3ed7de4d7b8707ba711f34725e5aaec2c05e611d41e02b3f846.
Receipts Saved/MimicKitLocomotion/pelvis5-*. Helpers restart_loco_pelvis5.py
and verify_loco_pelvis5.py. Recovery unchanged.

## October21 - recovery perturbed+ change scheduled, not yet deployed

User requested a switch in two hours: half of perturbed recovery rows become
perturbed+, preserving 30% normal and dividing the remaining70% equally between
ordinary perturbed and perturbed+. Root linear velocity uses random loco frame A;
joint velocities use a different independently sampled loco frame B (explicit
user correction). Whole-body angular velocity uses an independent uniform random
3D axis and uniform magnitude0–700deg/s. Resample at episode resets; keep existing
limp pose blend and floor correction. Only perturbed+ delays the low-head failure
check from tick80 to100; existing head threshold50%, success gates, pelvis ceiling,
AE, rewards, penalties, episode duration and other settings remain unchanged.
Scheduled for October22 ~01:16 Europe/Warsaw, latest checkpoint at switch time.
Read Saved/MimicKitEquipment/perturbed-plus-switch.json for execution/verification;
automation switch-half-of-perturbed-get-ups-to-perturbed. Current run untouched.

## October21 - speed-loss TensorBoard card repaired without trainer restart

The trainer already logged loss/extremity_speed_excess, but dashboard.py's
explicit metric mapping omitted it. Added that single mapping; restarted only
the current locomotion local dashboard (PID2912). Backfilled31existing points,
steps1,729,724,416..1,739,554,816, exactly matching original event values. Future
points publish at the same cadence as other losses. The card shows weighted
speed loss averaged over the training batch, including zero-cost frames/normal
rows; it is not a violation percentage or the conditional15% calibration ratio.
No GPU/trainer restart, settings or original events changed. Receipt:
Saved/MimicKitLocomotion/speed-loss-tb-card-fix.json. Opened TB22-48-04 filtered
to loss/extremity_speed_excess. Shared dashboard mapping also covers future runs.

## October21 - hard speed-limit tries stale; soft loss from pre-change checkpoint

User rejected both hard extremity-speed termination runs (220225 and221827).
Both marked stale; no continuation from their policy/optimizer states. Restored
protected98733_final from205453:1,729,691,648samples, SHA
777a1b823d593a63498e9f377feede526144c47185f905f4cf1d1387eae9f5cb.
Local SHA and persistent readback reverified before restart. Stale99982_final
was cleanly saved for evidence but is not the resumed state.

Keep150% limits for both feet/hands, per motion/limb; ordinary idle uses matching
walk backward. New cost =3.2039947906657353 * mean_over_four_limbs(max(speed-limit,0)^2).
Same body-origin velocity relative to translating AND rotating pelvis; reuses
existing reward velocities. Perturbed ordinary idle/loco only, across all ticks,
no AE/handoff fade. Normal/recovery rows unchanged. No speed termination or
terminal speed penalty; existing COM2 conditions and loco100failure penalty remain.
Adds named extremity_speed_excess term before the existing reciprocal reward,
so critic/PPO receive its effect. No new physics/AE pass or per-tick CPU sync.

Fixed weight calibrated on the protected checkpoint's recorded replay98733:
1,483perturbed frames excluding reset frames;44exceeded limits. On these44frames,
existing loss mean2.16874146, raw speed cost0.10153301, weighted cost0.32531124
=15% of existing loss. Calibration is conditional on violations, not diluted by
zero-cost frames; communicated to user. Across all calibration frames mean cost
0.00965185 versus existing3.06182051. Future frames need not maintain exact15%.

Only deployed perturbed_omni.py and two perturbed config keys changed:
extremity_speed_termination=false; extremity_speed_loss_weight=3.2039947906657353.
Threshold table unchanged. Default-off shared code preserves other branch work.
Actual-method CPU tests cover squared excess, zero below threshold, rigid pelvis
motion removal, unchanged other terms, normal/recovery exclusion and disabled
speed-failure call. Real replay98734 reconstructs cost and scalar reward within
6.01e-7:15overspeed frames continue without reset; one coincides with existing
COM2 failure. This confirms speed no longer forces termination.

RUNNING20261021_224804_uefn_locomotion_speed_loss_1024, sameL4q764mqd40pabiq,
$0.59/hour,1,024agents until stopped. Optimizer/normalizer restored from98733.
Advancing98734->98754 at18,535transitions/s; first98734backup persistent verified
SHA98e256716527fa3661df2a1c4172bb473d8b6817c7ff82384bf97694ec35266c.
Trainer956/exitguard957,bridge27688/dashboard3360; TB22-48-04. Old observers
stopped; handoff watchdog released after progression and backup. Recovery untouched.
Helpers loco_speed_loss.py, restart_loco_speed_loss.py, verify_loco_speed_loss.py.
Receipts Saved/MimicKitLocomotion/speed-loss-* and stale-speed-termination-runs.json.
Source SHAfc50a217442cf2f134b6cc2ec5e0de62fc1bfe3b51392960b24101d6d69cf425.

## October21 - locomotion feet and hands both150%, resumed latest

User changed feet from135% to150%; hands remain150%. Only the deployed
prepared/extremity_speed_reference.json changed: foot limits recomputed from
stored per-motion maxima, all hand values and idle walk-backward mappings
preserved exactly. No physics, code, reward, optimizer or sampling changes.
50motion tables verified, including the deployed copy. Same moving-pelvis
measurement, perturbed-only scope and tick1 activation.

Latest99151_final /1,743,388,672samples locally saved and persistent readback
verified SHA1112d5179325a3d9824adf043d25a31b418b94ab8e8337253332bce82f4d7839.
Resumed20261021_221827_uefn_locomotion_extremity150_1024 on same
L4q764mqd40pabiq,$0.59/hour,1,024agents until stopped. Optimizers/normalizer
restored. Advancing99152->99172 at18,471transitions/s. First99152 backup verified
SHAe982a003a4342929cbbde9c8790a832621285f5eaf8549553d3ea3544bc13c64.
Handoff watchdog released after progression/backup; normal failure guards active.
Trainer735/exitguard736,bridge10584/dashboard24684; TB22-18-27. Previous
observers stopped. Recovery unchanged. Receipts Saved/MimicKitLocomotion/speed150-*;
source locomotion-extremity-speed150-source.zip, SHA861724e04dd31f261385735927d6769c17df90ba4ee2581a77504e0960a31152.

## October21 - approved persistent replay/checkpoint cleanup completed

No standalone recent replay objects were found: these replays were embedded in
checkpoint ZIPs. User approved the proposed 468 intermediate physical UEFN
checkpoint deletions while retaining each run's latest and final saves. Executed
only those exact approved keys, after refreshing inventory and latest_verified
manifests and checking original size/modified time. Individual S3 deletes with
8 workers completed without errors. Re-list verified all 468 absent and all 14
protected latest/final saves still present. Freed 21,375,033,969 bytes (21.38 GB).
Newly written archives outside the approved list were not deleted. Neither
training branch was interrupted; no local files, datasets, source packages,
TensorBoard logs or unrelated Unreal checkpoints were touched. No automatic
retention policy changed. Plan, per-key receipts and verification are saved in
Saved/MimicKitEquipment/replay-cleanup-20261021/; completed.json is the result.

## October21 - perturbed extremity-speed failure, resumed and verified

Requested feet >135% and hands >150% of reference maximum speed. Each
individual limb uses its own animation maximum; user explicitly selected
matching Drawn/Unarmed Walk_Loop_B as the reference for ordinary idle.
50 exact deployed motion files sampled offline at480Hz. Body-origin speed
in translating AND rotating pelvis frame is norm(v-v_p-omega_p cross(p-p_p)).
Live engine COM velocities are converted to origins before comparison.
Perturbed ordinary idle/loco only; strict exceeds, active from first simulated
tick, no added grace. Failure overrides timeout, resets the row and zeroes
bootstrap; existing loco100 failure cost applies once, no new idle penalty.
Normals/recovery unchanged; no extra physics/AE pass or per-tick CPU readback.

Latest98733_final /1,729,691,648samples saved locally and persistent verified,
SHA777a1b823d593a63498e9f377feede526144c47185f905f4cf1d1387eae9f5cb.
Initial restart215646 failed before training: new initializer shadowed the
existing COM table variable, causing KeyError masses_kg. Corrected to a separate
speed_table; actual initializer and terminal-path CPU tests now pass, including
COM-table preservation. Failure evidence retained; guard stopped A40wjxv6qigq3dy9o.
Runpod then could not restart it (GPU reassigned). Replacement L4q764mqd40pabiq
allocated at$0.59/hour with10minute setup guard. Corrected run
20261021_220225_uefn_locomotion_extremity_speed_1024 is advancing98734->98754,
1,024agents until stopped; measured18.44k transitions/s after warmup. This is a
hardware change from A40, so not an isolated overhead comparison. Optimizers
and normalizer restored. First98734 backup persistent readback verified,
SHA08310a85498b8d5b6cdc460741ed90735002a9ec941f6ef89c36be39e9241337.
Setup guard released only after progression and verified backup. Trainer467,
exitguard468, localbridge17272/dashboard12104. TB22-02-25. Replay98734 checked
all11perturbed captured rows:5speed crossings, all fail on the first crossing
(including one at tick1),6never cross. Idle uses matching walk-backward limits
and lasts120ticks in this capture. No new grace; no lost checkpoint progress.
Recovery pod untouched. Old failed-run observers stopped. Detailed evidence
extremity-speed-terminal-tests, remote-replay-verification, live-verification.
Corrected source SHAe0c91ebe0b1c4aae9371ecf700ab1ef777860ef5bcbce8e85543507911772051. Helpers loco_extremity_speed.py, restart_loco_extremity_speed.py,
verify_loco_extremity_speed.py. Receipts Saved/MimicKitLocomotion/extremity-speed-*.

## October21 - perturbed idle position/rotation MSE x5, resumed latest

User requested x5 position and rotation MSE for perturbed ordinary idle rows,
including early MSE and handoff. Applies across all ticks, after the existing
mix+k*(1-mix) coefficient. k remains0.010628431805636024; no recalibration that
would cancel the requested increase. Linear/angular velocity, AE, COM terms,
normal idle, locomotion and all recoveries unchanged. Scope explicitly excludes
recovery rows and requires perturbed plus idle gait. Default multiplier1 keeps
other branches unchanged; shared recovery edits preserved. No new model/physics
passes, only batched selection and scaling of two existing loss columns.

Source package changes only pipeline/perturbed_omni.py and one env config key:
perturbed_motion.idle_pose_mse_multiplier=5. Actual patched-method tests compare
before/after at ticks0,2,29,30,45,59,60,120, including default1, normal idle,
locomotion and perturbed/normal get-ups; only intended two columns differ.
Helper Labs/MimicKitTraining/loco_idle_pose_scale.py.

Latest97272_final /1,681,817,600samples preserved locally and persistent,
SHA699bae31434db8fcb25a1b882ce9b5e1d1d7c39c50523287efbcb7e99ca8b45e.
Resumed20261021_205453_uefn_locomotion_perturbed_idle_pose5_1024 on same A40
wjxv6qigq3dy9o,$0.59/hour,1,024agents until stopped. Optimizer states and
normalizer restored. Advancing97273->97283,early13,976transitions/s. New97273
backup persistent-readback verified SHA
7a7045d4effdfb586b675e26821b23536aac401b173283cdc1130cf8bbf928ef.
Trainer1088/failureguard1089,bridge15836/dashboard700; TBfilter20-54-53.
Replay97273 verified20rows/4,020frames: affected perturbed idle spans120ticks;
position/rotation match x5 through early/handoff/late stages, all other terms
retain previous coefficients. Max reconstruction error2.65e-6, accepted within
normal numerical tolerance. Converted replayer rollout exists locally.
Handoff watchdog released after progression and verified backup. Recovery
pod/run untouched. Receipts under Saved/MimicKitLocomotion/idle-pose5-:
source-verification, preserved-checkpoint, live-verification, replay-verification,
before-plan, switch. Source locomotion-perturbed-idle-pose5-source.zip.

## October21 - perturbed get-up pelvis ceiling, first five ticks exempt

User requested a failure at the pelvis height shown in rollout104398,row17/
world18,tick30 of20261021_194738_uefn_getup_success_gates_1024, then clarified
it must activate after the fifth frame for high initial poses. Screenshot HUD
root[-.750,.935,.575] matches stored frame30 exactly (slider30.4; do not use
interpolated30.4 height). Ceiling is pelvis body-origin worldZ0.9345778227m.
Perturbed get-ups fail when ticks>5 AND pelvisZ>=ceiling, starting at tick6.
Ticks0..5 exempt. Normal recoveries untouched. Existing FAIL path wins over
simultaneous success, blocks success bonus, charges existing100 penalty once
and zero-bootstraps. Success feet/head-speed gates remain unchanged. No extra
simulation, CPU sync or new reward term; one vector height comparison.

Checkpoint104663_final /1,791,475,712samples downloaded and persistent verified:
SHAd0ab18f748661bb89fa21b43c4178958a2a64ea183d596a16b5eb97833dc1c26.
Resumed20261021_200623_uefn_getup_pelvis_ceiling_1024 on same L4upszb03gy35fzj,
$0.59/hour until stopped,1,024agents. Trainer1051/exitguard1052;
bridge23596/dashboard15408. Verified104664→104674 at~15.31k transitions/s.
New104664 backup readback SHAd16f3962325ce2348fd280a8ac94469804d34233d94d627681a6cb21ca7dade6.
All18perturbed replay rows checked:11 high-pelvis crossings terminate at first
eligible crossing with FAIL and terminal reward<=-99 (base reward minus100).
Boundary tests cover ticks0/5/6,exact ceiling,below ceiling and normal exclusion;
actual production terminal tail confirms failure overrides success and penalty.
No trainer/backup errors. Restart watchdog released after advancing save/replay.
Source50586a1f9a9a,only perturbed_omni.py and two env config keys changed.
Calibration getup-pelvis-ceiling-calibration.json,checkpoint receipt
pelvis-ceiling-preserved.json,live receipt pelvis-ceiling-verification.json.
Helpers getup_pelvis_ceiling.py/restart_getup_pelvis_ceiling.py. Locomotion untouched.


## October21 - early MSE added alongside locomotion AE, resumed latest

User requested MSE alongside the early prior, fading that extra MSE with AE,
scaled to roughly equal its cost. Perturbed idle/loco body cost now:
(1-mix)*weighted_AE + (mix + k*(1-mix))*weighted_body_MSE.
mix=0 through tick30, linear30..60, then1. k=0.010628431805636024.
Four existing position/linear-velocity/rotation/angular-velocity MSE terms retain
current leeways and autoregressive targets. Existing full-strength late MSE,
AE weight, COM2 conditions/penalty, normals and all other settings unchanged.
No extra AE/physics pass: reuse already-computed MSE with a batched multiplier.

Fixed calibration from actual previous-run replay95896:13perturbed rows,
353valid early frames(ticks2..29), excluding reset/invalid AE-history ticks.
Mean existing weighted AE0.2992596011; unblended weighted MSE28.1565151430.
Weight makes their means equal on this sample, not a guarantee on future states.
Offline reconstruction matched3,558recorded frame losses with max error9.65e-7.
CPU tests execute actual patched loss method at ticks0,2,29,30,45,59,60,120;
normal rows, get-up override, defaultzero and full late MSE remain unchanged.
Shared perturbed_omni.py change is default-off; recovery edits preserved.
Pinned source differs only perturbed_omni.py, new env_config key ae_mse_weight,
and calibration metadata. Source/source SHA recorded in prepared plan.

Saved latest96009_final locally/persistently,1,640,431,616samples,
SHA837b98a83ec5e86219bfbb2a1fd100054f6889c865f4f2e61b8dcddae4042542.
Resumed20261021_200213_uefn_locomotion_ae_earlymse_yaw180_1024 on same A40
wjxv6qigq3dy9o,$0.59/hour,1,024agents,until stopped. Optimizers and normalizer
restored. Advancing96010->96020, early14,288transitions/s. First96010 backup
persistent-readback verified SHA9f79fffe7ba2b3636c4e52dc98e1d520e0b82d5a6dbd4a590df38a2c30db65b8.
Trainer895/failureguard896; bridge6884/dashboard1080; TBfilter20-02-13.
Live replay96010 verified20rows/3,727frames: new MSE multiplier matches
recorded terms (max reconstruction error2.76e-7); AE schedule unchanged.
Early perturbed mean costs0.277MSE and0.348AE on the new replay, roughly matched.
Converted replayer rollout and new TB event stream are present locally.
Ten-minute handoff watchdog released after verified progress and backup.
Receipt prefix Saved/MimicKitLocomotion/early-mse-: calibration, preserved-checkpoint,
live-verification, replay-verification, switch, before-plan. Implementation helper
Labs/MimicKitTraining/loco_early_mse.py. Recovery pod/run untouched.

## October21 - stricter perturbed get-up success, resumed latest

User calibrated gates from displayed rollout103985,row9/world4,tick19 in
20261021_171139_uefn_getup_ae10_1024. Exact saved physics: left-foot body-origin
worldZ0.260697901m, head-origin vertical velocity+4.206905365m/s. Screenshot
pelvis matches exactly. Use half values: BOTH feet worldZ<0.1303489506m and
absolute head-origin vertical speed<2.1034526825m/s, in addition to prior
head>90%idle-frame0 rule. Absolute speed excludes fast descent too, as stated
to user. Engine COM velocity converted to head-origin velocity with omega x
rotated local COM offset, matching recorder; physical verticalZ, viewerY.
Scope perturbed recoveries only. Rejected success stays in the episode under
existing failure/timeout rules; success bonus and all other rewards unchanged.
No extra simulation/CPU synchronization; small batched checks in existing done
calculation. Replay metadata records thresholds and reset code2 is labelled
standing success reset (head height,feet height,head speed).

Latest104197_final (1,776,205,824samples) preserved locally and persistent:
SHA0a8ea0b14fcea8bfeffe093f9d5729dd8e5765d149911f00cc2a09d35f586f68.
Resume20261021_194738_uefn_getup_success_gates_1024 on sameupszb03gy35fzj L4,
$0.59/hour until stopped,1,024agents;trainer808/guard809,bridge10932/dashboard28696.
New104198 backup persistent-readback verified SHA
892308b70a0f4ff45041d6f2d0f4d79fdc406704c2fb159644d59b68588c8e01.
Advancing104198→104208 at~15.85k transitions/s; no trainer/backup errors.
18perturbed replay rows checked; all6successful rows meet both new bounds.
Threshold tests reject screenshot, either high foot, fast ascent/descent and
boundary equality; low feet/slow head passes and normal eligibility unaffected.
Source package differs only perturbed_omni.py,observe.py and two env config
keys; source349842cd0600. All other config unchanged, including AE/proportions.
Ten-minute restart watchdog released after advancement/backup/replay checks.
Receipts getup-success-gates-calibration.json,success-gates-preserved.json,
success-gates-verification.json in Saved/MimicKitEquipment. Helpers
getup_success_gates.py,restart_getup_success_gates.py. Locomotion untouched.


## October21 - recovery resumed with 1,024 agents

User requested latest get-up resume with batch1,024 (parallel environments).
Resumed verified99984_final /1,638,154,240samples; original local/persistent
checkpoint retained. Run20261021_171139_uefn_getup_ae10_1024, L4upszb03gy35fzj at$0.59/hour,
until stopped; trainer468/exitguard469, bridge25964/dashboard13884.
Confirmed99985→99995,1,638,514,688samples,early throughput15.15k transitions/s.
New99985 checkpoint verified by persistent readback:
SHA49dd1ae752a7bc2b39b22599c1eb93e16df20af362443faa405e5d3b95b406ac.
Actor/critic optimizer and normalizer restored. Same30/70normal/perturbed,
50/50front/back, normal half frame0/half random; uniform whole-pose limp blend,
floor clearance,AE weight.2752568,noise.075,GAE.98,LR1.125e-6,losses/physics
and termination settings unchanged. Recorder has first new replay; dashboard
published27 points. Explicit world count is now read from the prepared plan.

Original L4w9aq90rzkg1d0g unavailable. First replacement90v1fafvq5uudn exited
before any training because the legacy RunLR assertion forced512 even for
prepared equipment runs; guard confirmed GPU stop. Removed that restriction
for equipment runs while retaining the512-world standalone RunLR fixture.
Corrected source changes only pipeline/train.py versus the pinned AE package;
512/1024 argument checks passed; source archive hashcf6d3b06e3f3b707dc6463291bacdd1b3f3dd6e0d1ff430f1fe151b10e65e35a.
That replacement then could not restart, so current L4 was allocated. No old
pod/disk deleted and locomotion untouched. Setup watchdog released only after
advancement and verified backup. Receipt getup1024-verification.json; failed
launch evidence getup1024-initial-exit-evidence.zip. Supersedes stopped status.


## October21 - locomotion resumed with 1,024 agents (verified)

User selected1,024 agents; resumed latest production91895_final at
1,505,624,064samples, not a sweep checkpoint. Run
20261021_171453_uefn_locomotion_ae30_mse30_yaw180_1024 on replacement A40
wjxv6qigq3dy9o at$0.59/hour, until stopped (existing indefinite authorization).
Original L4, sweep A40 and replacement L4 had no capacity. Recovery untouched.

All task/physics/optimizer settings retained:7%idle/93%loco, each30%normal/
70%perturbed, no recovery rows, yaw180,120tick perturbed episodes,AE30 then
30tick blend to MSE, same priors/losses/termination/penalties. Actor LR1.125e-6,
critic1e-4, noise.075, GAE.98,32tick rollout. Batch now32,768 transitions;
actor minibatch4,096, critic2,048 via unchanged batch factors4/2.
Both optimizer states and normalization restored; normalization changed0channels.
Verified advancing91896->91906,1,505,984,512samples, early13,626transitions/s.
This is startup throughput, not a guaranteed long-run average.

Pinned archive had an obsolete512-only startup assertion. First attempted run
20261021_170742 exited before training; automatic failure guard stopped billing.
Only pipeline/train.py gate changed in copied source to permit1024 equipment
worlds; original source/checkpoint remain preserved. Gate CPU checks passed,
all other archive entries byte-identical. Shared train.py already has a broader
world-count check; it was left untouched. deploy_locomotion_branch.launch now
reads plan.worlds (defaults512). Fresh-host runtime restore encountered a retained
venv symlink after pod restart; verified archive/extraction reused and restore
completed without changing packages. Cold physics kernels compiled normally.

First new checkpoint91896, SHA
cde4a94842006472082c7a6176103eb1088d733d1b3416a3694d928a129164f1,
verified by persistent readback. Live receipt worlds1024-live-verification.json;
source-change receipt worlds1024-source-change.json; first failed launch evidence
worlds1024-first-start-evidence.zip. Prepared plan points to91895 and corrected
locomotion-ae30-mse30-1024-source.zip. No rollback or sweep weights promoted.
Trainer575, failure guard576; local bridge9524/dashboard15612.
Setup watchdog released after advancing steps and verified backup. Training/backup
failure stop remains active. Runtime control until_stopped=true. TB filter17-14-53.

## October21 - isolated locomotion learning-speed sweeps finished

User requested wrapping up, superseding the earlier unlimited-time exploration.
Separate A40pod a9y7igarhig19j at$0.59/hour confirmed EXITED. Estimated allocation
GPU cost$1.14; storage/provider rounding excluded. Main locomotion and recovery
remain stopped. All seven protected production checkpoint/source/control files
were rehashed unchanged, including91895_final at1,505,624,064samples. No candidate
has been applied to production. Resume must use the preserved91895_final, not
the older78988 reference in getup-success-prepared.json.

Ten configurations including baseline completed4.194M transitions each:
actorLRx2/x4, criticLRx3, actorbatch8+LRx2, rollout64+LRx2, adaptiveKL,
critic reward context, TF32, and1,024worlds. Eight fixed held-out seeds give
2,664perturbed locomotion first episodes per candidate. Training used one seed;
normal full300tick screening used two seeds for candidates, eight for baseline.
Censored normal rows were excluded. Differences are exploratory and evaluation
confidence intervals do not measure variation across training seeds.

Baseline27.665% failures in473.24training seconds; best valid screen rollout64+
LRx2 reached27.402% in460.6seconds. Difference-0.263percentage points, paired
95%evaluation interval[-1.69,+1.01]: no reliable improvement. Larger actor batch
was14% quicker but worse at28.94%. TF32 was4% slower and28.08%. No benefit from
higher actor/critic LR or reward context. Baseline guard rejected no steps.
Baseline profiling~68%rollout/27%actor/5%critic. Heading/50motion input audit passed.

1,024worlds took281.84seconds:1.68x transition throughput. Its separate512world
evaluator matched poses/targets/yaw/assignments but failed byte-equality checks
on velocities/observations. Physical magnitude not measured; derivative
preprocessing is only a hypothesis. Exclude its failure score from learning
comparisons. Investigation stopped at user's wrap-up request; do not claim a
validated learning speedup. Fresh-seed longer baseline/rollout64 confirmation
was cancelled before a completed comparison; no confirmation result exists.
FastSAC/FastTD3 researched but not implemented or experimentally ruled out.

State/evidence Saved/MimicKitLocomotionSweeps/20261021: result_*.json,
sweep_comparison.json, final-billing-stop.json, final-main-integrity.json,
preserved-screen-states.json, loco-screen2/artifact_backups.json, and
loco-confirm-a/user-wrap-cancellation.json. Baseline/rollout64 and both runtime
full training states have S3 SHA256 readback-verified backups; results local.
Final report Saved/MimicKitLocomotion/research-20261021/results.md; literature.md,
audit.md, audit-followup.md retain sources and hypotheses. Isolated helper code
and path/controller tests retained; no main trainer configuration changed.

## October21 - recovery stopped at user request; latest downloaded

Recovery run20261021_091317_uefn_getup_ae10_512 stopped cleanly using its
stop.request; existing exit guard stopped L4w9aq90rzkg1d0g, API EXITED confirmed.
Latest99984_final,1,638,154,240samples,47,879,209bytes is retained in persistent
storage and downloaded to Saved/MimicKitEquipment/preserved-latest/
20261021_091317_uefn_getup_ae10_512/checkpoint_0099984_final.zip.
SHA256 cd51ee57a63cd8926ce08ec383d3ca7a1aecb43454bbbef53bc11dd941214674
matches the persistent verified manifest; local ZIP integrity passed.
Receipt stopped-latest-20261021.json; prepared recovery plan points to this save.
Final event log/replay restored locally from the checkpoint; recovery bridge
stopped and active replay marker cleared. No training settings changed.
Locomotion was not modified; its pod also reported EXITED independently.
This supersedes recovery-running status below; do not restart without request.


## October21 - locomotion stopped at user request; latest downloaded

User requests latest checkpoint download and stop. Graceful stop produced
91895_final, retained in persistent storage and downloaded locally:
Saved/MimicKitLocomotion/preserved-latest/20261021_091005_uefn_locomotion_ae30_mse30_yaw180_512/checkpoint_0091895_final.zip.
53,780,635bytes; SHA256
fb259aa89e2c42306ef7d98dee7471fdf7be04b1b21ec9e979f92896f0df37d1.
Local SHA matches persistent verified receipt, ZIP CRC/model.pt/resume_state.pt
verified. Owned locomotion pod rjsan0uitu03qd confirmed EXITED; GPU billing
stopped. Retained pod disk and persistent/local checkpoint preserved. Local
locomotion bridge/dashboard stopped, active marker cleared; local until-stopped
control superseded by explicit user stop. Recovery branch untouched.
Receipts Saved/MimicKitLocomotion/user-stop-checkpoint.json,user-stop-billing.json.
Latest training setup remains AE30→MSE30 on perturbed rows for any future resume;
no restart authorized by this stop request.

## October21 - additive AE regularizer restored on perturbed get-ups only

User explicitly chooses perturbed get-ups only; normal recoveries unchanged.
Stopped cleanly and preserved latest88363_final,1,447,755,776samples locally
and in persistent storage, SHA886c29496275c07286c94711dfecb7c7816061989acb5ac1dfd58aab5bc1ff73.
Added getup_ae_regularizer=true to the pinned recovery package; only
perturbed_omni.py and prepared configuration/calibration changed. The shared
workspace has the same opt-in logic; default false preserves other branches.
The frozen existing AE sees generated physical body origins/world rotations,
three consecutive30Hz poses, with reset-isolated history and no score until valid.
Position MSE stays full strength; additive weighted AE is included in both
displayed total and actual linear RL reward:1-position_cost-weighted_AE.
Success bonus99, failure penalty100, initialization, phase and termination unchanged.

Fixed weight0.2752567992958057 calibrated on the final checkpoint's actual
deterministic perturbed get-up replay windows: mean position cost1.966992551,
mean AE raw0.794003013; weighted AE0.218554728 is10% of combined pose+AE cost.
Terminal bonuses/penalties excluded from this loss calibration. This is a fixed
weight from recorded evaluation, not a guarantee of10% at every tick or later
in training. Scorer/encoder extracted from the deployed source archive itself.
Receipt getup-ae-calibration.json; preserved save getup-ae-preserved.json.

Resumed20261021_091317_uefn_getup_ae10_512 on same L4w9aq90rzkg1d0g at$.59/hour,
until stopped. Trainer696/exitguard697; bridge13512/dashboard1724. Verified
88364→88384 (~9.29k transitions/s), new88364 checkpoint persistent readback
SHAb5a11c90d9132559e7ee1c06a67ff072afe1e8cc984dd22d42f49675f431b348.
No trainer/backup errors. Actual20-row replay:18perturbed rows have AE cost,
2normal rows zero; first two stored frames zero, then valid three-pose costs.
Verified weighted AE equals recorded raw times configured weight. Production
reward-method checks prove AE affects reward and normals/default behavior remain
unchanged; real scorer test confirms history clears only the reset agent.
Ten-minute handoff watchdog released only after progress/backup verification.
Helpers restart_getup_ae.py,getup_ae_regularizer.py,test_getup_ae_regularizer.py;
getup-ae-live-verification.json and getup-ae-replay-verification.json record results.

## October21 - locomotion AE to MSE restored, 30/30 (verified running)

User requests latest resume with full AE first30 policy ticks, linear handoff
through next30, full MSE from60 onward on PERTURBED idle/loco rows only.
Normal MSE unchanged. Restore exact prior assets and previous weight
6.942658260262293 from pre-split noise-gae source. No extra division/scaling.
Three consecutive real poses required by existing AE history contract; the first
transition has no valid three-pose window. Existing autoregressive phase retained.
120tick perturbed horizon,yaw±180,7/93idle/loco,30/70normal/perturbed,
50/50walk/run,noise.075,GAE.98,Adam/KL and all termination/penalties unchanged.
Only existing package file changed is prepared/env_config.yaml; prior assets
restored. No new physics/AE architecture/normal-row changes. Recovery untouched.

Stopped prior run cleanly;78988_final at1,294,155,776samples saved locally and
persistent-readback verified, SHA27708b597263b9240e9eb3f7ddf31e63830732728400b2eb39a9d59221336168.
Preserved under Saved/MimicKitLocomotion/preserved-latest/20261021_074500_uefn_locomotion_mse_yaw180_512/.
New run20261021_091005_uefn_locomotion_ae30_mse30_yaw180_512, same L4
rjsan0uitu03qd/$0.59hour/until-stopped. Trainer701/exitguard702;
bridge11512/dashboard8380. Actual advancement78989→79009,~11.65k transitions/s.
First new checkpoint78989 persistent readback verified,
SHA6b1736294d8f6ab8e59b59127745ece708aa8957acc7a220110fc25791979ee3.
Live replay MSE mix0 at ticks0/29/30,.5at45,1at60/120;AE loaded=true.
Ten-minute handoff billing watchdog605 released after progress/backup verified.
Helper restart_locomotion_ae.py; ae30-switch/launch/verification receipts in
Saved/MimicKitLocomotion. Current source55dee57664d7; prepared plan updated.
Generic locomotion launcher now accepts either AE asset state from its pinned
source, and validates exact source-package hash before restart.

## October21 - recovery resumed after storage cleanup (verified running)

Resumed RECOVERY only in this chat; locomotion is managed separately.
Old recovery new5546ihvxeax could not start (GPU reassigned). Replacement SECURE
L4w9aq90rzkg1d0g at$0.59/hour; old retained disk preserved. Until-stopped
authorization retained. Source e72cfe88cf75 and checkpoint85149 (1,395,097,600
samples) restored with SHA verification. Optimizer, normalizer and settings kept.
512 recoveries:30%normal/70%perturbed,front/back50/50,normal starts half frame0/
half random; uniform whole-pose limp blends and reset-only floor correction.
Noise.075,GAE.98,actorLR1.125e-6; same MSE leeway, objectives and physics.

Live20261021_074429_uefn_limp_floor_512,trainer479/exitguard480. Verified
85150→85170,1,395,441,664samples,~10.63k transitions/s. No failure/backup errors.
New checkpoint85150 persistent upload/readback verified, SHA
804329267a307c4293e505fc9e78f04824164055fe21b9a8b1002ac5097020ad.
Bridge18464/dashboard7392 running; TB8035 new run present and20-row replay85150
published locally. Receipt Saved/MimicKitEquipment/resume-after-storage-verification.json.

Launcher optionally checks remote runtime against an explicitly SHA-pinned source
archive, retaining current-workspace checks by default. Used here to preserve
the exact tested recovery source: shared workspace code has since changed for
the separate locomotion branch. No training code changes deployed to recovery.

## October21 - locomotion resumed after storage cleanup

User requested resume from latest. Verified local ZIP/SHA and persistent readback
of75533 (1,237,549,056 samples), SHA
a07d385731dec8a3ca2aa80e4790848ca5293770d0cad1ed63bd0848d9f6f450.
Fresh checkpoint-sized S3 upload/readback succeeded; diagnostic probe removed.
Existing L4cb2i8leh2qpjdf could not restart (machine lacks resources); retained
stopped disk untouched. Replacement SECURE L4rjsan0uitu03qd at$0.59/hour.
Live run20261021_074500_uefn_locomotion_mse_yaw180_512, trainer481/exitguard482,
remote deadline guard314; until-stopped authorization retained. No training
settings changed:7%idle/93%loco,each30/70normal/perturbed,no get-ups/AE,
yaw180,120perturbed ticks, existing losses/termination/optimizer settings.
Resume reports75534offset, actor/critic optimizer and normalizer restored.
First new checkpoint75534 persistent readback verified, SHA
35197d2fef48fea413aa52d7531fbc2c29958d5f63ff0b19dc11b0f88ca0b686.
Verified advancement75534→75564, ~12.8k training transitions/s. Setup watchdog
released after progress and backup verification. TensorBoard new run visible.
Bridge4900/dashboard22724; stale old locomotion observers stopped. Recovery
branch not operated. Receipt Saved/MimicKitLocomotion/resume-20261021.json.

## October21 - authorized physical locomotion/recovery history cleanup

User explicitly requests downloading latest BOTH branches, then deleting older
physical locomotion/get-up checkpoints and replay recordings except those saves.
Downloaded full archives, verified SHA256 against persistent latest_verified,
ZIP CRC integrity, model.pt and resume_state.pt BEFORE deleting anything.
Preserve locally AND in S3:
- Recovery85149,1,395,097,600samples, SHA
  033c917f44f57bd3a0eb755ebe12ecd0a5dd3921af33998db1a0e1e360bf3f17.
  Saved/MimicKitEquipment/preserved-latest/20261020_193455_uefn_limp_floor_512/checkpoint_0085149.zip.
- Locomotion75533,1,237,549,056samples, SHA
  a07d385731dec8a3ca2aa80e4790848ca5293770d0cad1ed63bd0848d9f6f450.
  Saved/MimicKitLocomotion/preserved-latest/20261020_211208_uefn_locomotion_mse_yaw180_512/checkpoint_0075533.zip.

Deleted1135 historical checkpoint/replay objects under physical UEFN non-crawl
runs and equipment preserved-checkpoint copies:46,578,114,944bytes. Relisting
confirmed all selected objects absent and both protected archives present.
Deleted302 corresponding local checkpoint/replay files (4,716,801,953bytes),
plus68 obsolete last_batch_rollout.json/replay.part files (541,138,980bytes).
Historical latest_verified pointers/source receipts may now reference explicitly
deleted archives; use only the two preserved saves above for these branches.
Datasets, source packages, TensorBoard history, crawl and other Unreal model
families untouched. No pod start/resume. This is a one-time authorized cleanup,
not a new automatic retention policy. Full manifests/receipts live under
Saved/MimicKitEquipment/cleanup-20261021. Final46,135,077-byte upload and
SHA256 readback SUCCEEDED after cleanup; temporary probe removed.
completed.json records success; checkpoint backups have usable capacity again.

## October21 - both pods found stopped; recovery display caught up

Follow-up storage check: a fresh18-byte S3 PutObject to a unique diagnostic
key fails with Runpod QuotaExceeded / storage quota exceeded. Shared persistent
volume aj7d2jzwuq is200GB; MimicKit run archives alone total45,978,576,317bytes
across1285objects. Local C: still has about10GB free. Persistent backup quota
is therefore CONFIRMED exhausted now. train.py raises on backups.errors and
the exit watcher stops the owned GPU, making failed backups the strong common
explanation for both stops. Exact terminal logs remain inaccessible, so the
historical trigger is not directly verified. No user files/checkpoints deleted;
diagnostic key cleanup only. Do not restart paid training until backup capacity
is restored and a checkpoint-sized write/readback succeeds.

Read-only Runpod checks show locomotion cb2i8leh2qpjdf stopped October20
20:01:00 UTC and recovery new5546ihvxeax stopped 20:01:37 UTC (22:01 Warsaw).
Both report `Exited by user`; this label does not identify whether the request
came from a human or an API guard. The initiating actor/reason is UNRESOLVED.
Recovery runtime_control still says until_stopped with no practical deadline.
No matching local stop receipt, final checkpoint, or persistent exit-evidence
archive was found. The account currently has $14.82 and underBalance=false;
this is not a historical balance record. Neither pod was restarted by this audit.

Recovered eight missing recovery replay captures (84449 through85149) and their
saved evaluation aggregates from persistent checkpoint archives. TensorBoard HTTP
verification confirms episode/test_seconds and reward/test through1,395,097,600
samples; replay latest85149. Training curves still end at1,382,973,440 samples:
ordinary checkpoint archives do not contain the missing training event files.
No synthetic training/failure-rate data was inserted. Stopped the stale recovery
local bridge/dashboard and removed its training.active marker; TB remains up.
Helper refresh_stopped_recovery.py; receipt
Saved/MimicKitEquipment/refresh-stopped-recovery-report.json.

## October20 - independent locomotion MSE branch (running, verified)

User forked locomotion from the checkpoint immediately before recovery-only
training. Immutable73832_final from mixed141039,1,209,679,872samples,
SHA221ed14975999aab1846e53758113bb228418827acd4edbf8403ca1b05ba3699.
Original receipt recovery-split-loco-fork-checkpoint.json preserved.
New state/control directory Saved/MimicKitLocomotion; NEVER use
Saved/MimicKitEquipment pod/control files to operate this branch.
New dedicated SECURE L4cb2i8leh2qpjdf,0.59/hour. User superseded the initial
8-hour answer with "ad vitam": run until explicitly stopped, no8-hour cutoff.
Recovery L4new5546ihvxeax and its live source/control remain untouched.

512agents:7%ordinary idle/93%locomotion; within each30%normal/70%perturbed.
Verified36idle(11normal/25perturbed),476locomotion(143normal/333perturbed);
existing50/50walk/run and equipment distribution retained. Zero recovery rows.
Retain split-checkpoint noise.075,GAE.98,Adam/KL,actorLR1.125e-6,normalization,
physics/torque/command bounds and MSE leeways. No AE weights in source package;
mse_only skips model loading, contract loading, history/scoring and blend ramp.
Full tracking MSE starts at tick0. Predicted phase controls perturbed input and
reference; normal uses authored clock. Existing normal flat-COM band remains;
perturbed flat-COM loss remains excluded, matching previous branch semantics.

Perturbed idle/loco timeout120policy ticks(4s), normal300ticks(10s).
Yaw uniform[-180,+180]deg around worldZ, keeping initial trunkCOM2 world
velocity intact. Existing perturbed locomotion termination: after8-tick grace,
direction>45deg from target, speed<70% or>170% target; failure penalty-100.
Perturbed idle has timeout only. Normal existing27cm tracking spheres and
other checks retained. Existing ordinary auto-phase supervision retained.

Production loss/done regression verifies full MSE at ticks0/79/80/119,
AE never called,120vs300horizons,8-tick grace and unchanged failure penalty.
Zero-recovery reference/velocity paths now return before empty ambiguous
reshapes. These changes are gated/default-preserving for the recovery branch.
Actual production resume compatibility checks passed against73832 before
allocating. Checkpoint/source persistent readbacks verified.
Helper deploy_locomotion_branch.py; local setup watchdog13408 and remote
deadline guard300 protect setup, in addition to training failure guard.

Verified live20261020_211208_uefn_locomotion_mse_yaw180_512, trainer435/exitguard436.
Startup reports zero recovery rows,238walk/238run, AE model not loaded,
mse_only=true,120perturbed ticks,yaw180. Resume restores actor/critic Adam
states and normalizer from73832_final. Progress73833→73913 observed; warm
training throughput11.4–11.6k transitions/s (~1.42s/update). Initial checkpoint
73833 backed up with persistent readback SHA
6b13225bf645f671b8d2be0f99f3096ff33cc434c585373ee974b6469568ac91.
Receipt Saved/MimicKitLocomotion/launch-verification.json. Local setup marker
written only after verified progress/backup; live deadline remains until-stopped.
Bridge25868/dashboard27124 populate local replay and TensorBoard;20rows
verified, no get-ups, AE disabled, perturbed horizons<=120,normal<=300.
Recovery pod/control file hashes match the prelaunch snapshot.


## October20 - limp blended starts floor clearance correction

User authorizes correction and resume from LATEST, not initial79023.
For perturbed limp starts only, after blending root/joints, run batched FK and
compute exact Z=0 support of all model colliders: eight corners per box,
two endpoints plus radius per capsule, centre plus radius per sphere.
Translate pelvis upward by penetration depth plus2micrometres float32 allowance
only if penetrating. Never lower already clear poses. Joint angles, root
orientation/XY and all authored starting velocities remain unchanged.
No per-step projection, contact/solver setting changes or corpus rewrite.
Support points load once from the packaged model, reset math stays on GPU.
Replay records reset_floor_lift_m and reset_floor_clearance_corrected.

test_limp_floor_clearance.py checks1,000limp endpoints x21strengths x2vanilla
starts plus20recorded starts against independent double-precision collider
support (42,020cases). Minimum resulting clearance0.825micrometres, all clear;
reported screenshot receives44.5368cm vertical shift. Endpoint blending/
partial-reset/velocity-preservation tests also pass. Deployment helper
deploy_limp_floor.py performs guarded latest-final save, local and persistent
checkpoint verification, then resume on same pod.

Verified launch20261020_193455_uefn_limp_floor_512 on sameL4new5546ihvxeax,
trainer849/exitguard850;bridge12596/dashboard22876,existing until-stopped budget.
Prior run gracefully saved79848_final (1,308,246,016samples), downloaded locally
and verified against persistent S3 readback, SHA256
e9b8574175e1e6f9a00792f28f3c73b974581e2f2992f27396006f727172ead5.
Resumed latest weights/optimizer/counters; all settings except floor placement
unchanged. Live77normal frame0/77normal random/358perturbed, prior_rows0.
First new79849 checkpoint persistently verified SHA256
93746b519f496dc2f9c95178cc5916a597caddb01277002bce871d6eb3e80955.
At79869/1,308,590,080samples progressing, recent mean1.533s/update,
10,685transitions/s versus prior recent1.573s/10,413transitions/s.
Short live comparison shows no slowdown, not a controlled isolated benchmark.
Guard completion marker released after verified progress and backup.
First actual replay79849: all18perturbed frame0 collider supports above floor,
minimum1.985micrometres, correction metadata present. Independent computation
from recorded world poses; not merely testing helper output. Receipts
limp-floor-preserved/verified/live-replay-verified.json.

## October20 - confirmed floor penetration introduced by whole-pose blending

User screenshot step79324 frame0 traced to replay row11, drawn front get-up,
limp corpus index31, alpha0.7908768058. Corpus SHA matches deployed artifact.
Read-only audit_limp_blend_clipping.py reconstructs the exact production blend
from vanilla frame0 (adjusting unarmed/drawn idle heading) and limp endpoint:
maximum body-position discrepancy1.42micrometres.
Limp endpoint deepest collider is0.897cm below floor; vanilla front pelvis3.600cm.
Blended start right hand44.537cm below floor and head25.793cm below floor.
16/18 perturbed starts in this replay exceed5cm floor penetration.
This is a reset placement defect, not replay display or a physics-tick effect:
interpolating root height while rotating/articulating does not preserve support.
Prior endpoint/interpolation tests missed floor clearance of intermediate poses.
Proposed correction: recompute minimum floor-clearing pelvis Z after blending,
at reset only, preserving blended joint pose and orientation. Not implemented
or deployed in this diagnostic turn; running training unchanged.
Evidence Saved/MimicKitEquipment/limp-blend-clipping-audit.json.

## October20 19:09 - limp whole-pose curriculum restart (verified running)

User marks183047 stale and explicitly restarts from its initial79023_final,
not its later checkpoints. Restore action noise.075, GAE lambda.98 and original
position-MSE leeway from79023 (normal recovery legs10cmXY/5cmZ, upper5cm).
100% recovery rows, front/back50/50;154normal/358perturbed among512.
Normal starts77frame0/77random; perturbations always vanilla frame0 blended
uniformly with one of1,000 saved limp poses, no strength skew.
User explicitly chose whole-pose blending: linear local DOFs and pelvis position,
shortest-arc quaternion interpolation for pelvis rotation. Keep authored
starting velocities, do not substitute stored limp velocities. Corpus SHA256
683193642d2350eedaef7cade16811f4f5161055b0296955bc5f539f18aca163.
No floor repositioning, new projection or physics change.
Low-head failure moves from tick60 to80, still below/equal50% idle head height.
Other reward/reset rules unchanged: perturbed get-ups use only idle-frame0
body-position linear cost, no leeway/AE, failure-100,90%head success value99;
normal recovery tracking,65cmhead/hands35cmfeet, failure-100 retained.

Code: perturbed_omni loads and validates corpus once into GPU tensors; all
blend operations occur only at reset. Cohorts stratified within each motion,
largest-remainder rounding preserves total77random normal starts.
test_limp_blend.py exercises production reset endpoints/midpoint, quaternion
signs, untouched rows, unchanged velocities and empty reset batches.
deploy_limp_blend.py validates production resume compatibility and persistent
readbacks before guarded handoff; preserves stale final separately and stages
only the initial79023 checkpoint.

Stale183047 saved80379_final to persistent storage but was NOT used to resume.
New20261020_190959_uefn_limp_blend_balanced_512 launched on same
L4new5546ihvxeax at.59/hour under existing until-stopped authorization,
trainer600/exitguard601. Loaded checkpoint SHA4f8a2a...70baa (79023),
optimizer and normalization restored, first update79024.
Live cohorts77normal frame0/77normal random/358perturbed frame0; prior_rows0.
Front normal38frame0/39random; back39frame0/38random;179perturbed each.
Config verified noise.075,lambda.98,restored leeway, uniform strength, tick80.
79024 backup verified SHA7e4821fef80a5fcd94adf36bd34d70b9242d3e137d138c363d85cca1fa688c58.
At final verification79044/1,295,073,280samples advancing, recent throughput
10,505transitions/s. Bounded handoff watchdog released only after progress and
backup verification. Bridge11944/dashboard21884 started; dashboard publishing.
Receipts limp-blend-prepared/staged/live/verification/verified.json in Saved.

## October20 18:21 - original noise/GAE, balanced recoveries, no position leeway

User requested resume latest with action noise.05, GAE lambda.95,
no position-MSE leeway and front/back50/50. Half frame0/half random starts
remain. Removed position_mse_leeway config entirely (raw position objective);
flat-COM velocity band, pelvis velocity multiplier, termination radii,
rewards, Adam learning rate and physics unchanged.

Fixed correlated cohort selectors exposed by equal fractions: both motion
assignment and random-start assignment previously chose the same evenly spaced
rows at.5. Random starts are now stratified within each fixed motion in both
RecoveryOmniEnv and the PerturbedOmniEnv normal-row override. Setup-only work,
no per-tick overhead. Regression tests exercise source-frame reset/phase,
partial resets, fraction extremes and128rows in each front/back x frame0/random
group. New recovery_start_by_motion.json records the live cross-tab.

Previous77391+ run stopped gracefully; latest79023_final downloaded locally
and verified against persistent S3 readback and ZIP CRC. SHA256
4f8a2a285cdc74de1a1f499960924a5eaf9c56561cc646290439856b58a70baa.
Receipt normal-balanced-no-leeway-preserved.json; config/source helper
Labs/MimicKitTraining/deploy_normal_balanced.py. Exact source diff is only
two configuration files and train/recovery_omni/perturbed_omni.py for the
cohort correction/reporting. No initialization-corpus deployment.
First182101 launch rejected removal of position_mse_leeway in the checkpoint
compatibility check; no updates ran. Exit guard stopped old pod billing.
Extended explicit --resume-position-leeway to permit key removal, and passed
the actual production compatibility-check AST against79023 locally before retry.
Resume helper now passes this flag through the prepared plan. Checkpoint unchanged.
Old L4 could not restart (GPU reassigned); EU-RO-1 mounted replacement unavailable.
Allocated replacement SECURE L4new5546ihvxeax at.59/hour, retained old pod/disk,
restored hash-verified source/checkpoint and cached runtime on container disk.
Second182635 launch passed compatibility but hit a KeyError in resume metadata
serialization, which also assumed the leeway field existed. No updates; billing
stopped. Changed that metadata to null for disabled leeway; executed actual
production branch for both enabled/removed cases locally. All occurrences audited.
Same replacement L4 restarted successfully; source/checkpoint/runtime restoring
under600-second setup watchdog. Latest79023 remains the preserved restart source.

Verified final launch20261020_183047_uefn_normal_balanced_no_leeway_512 on
L4new5546ihvxeax (.59/hour until stopped),trainer422/exitguard423,
bridge17828/dashboard15268. Live front/back each128frame0+128random-frame.
Noiseactual.05,GAE.95,position_leeway absent/null;Adam/normalizer restored.
At verification79034/1,294,909,440samples advancing; first79024 backup verified
SHAa4954e44b6321eb07eac00dcb58ba10289b1ac733dbd8308831f01f21cd77a45.
Local setup completion marker written only after those checks. Receipt
normal-balanced-no-leeway-verified.json. Old failed run outputs are diagnostic
only; current-run and active_run point at183047.

## October20 17:14 - normal get-ups half frame0, half random frames

User requests half the current run from frame0 and half in medias res.
Only prepared/env_config.yaml changed in the exact existing source package:
idle_recovery.start_at_frame_zero=false,random_start_fraction=.5;
perturbed_motion.normal_getup_random_start_fraction=.5. All runtime files and
other configuration preserved; no stiff/limp init dataset deployed.
Idle/recovery fractions1,perturbed fraction0,back_row_fraction.8 unchanged.
Random cohort uses existing uniform source-frame sampling on reset, excluding
the final frame. Live counters verify256normal frame0/256normal random,
0perturbed/prior,410back/102front.

Stopped prior155034 trainer gracefully under600-second handoff billing guard.
Final77390 saved locally and verified by persistent S3 readback/ZIP integrity:
1,267,974,144samples,SHA2da774988faf9f0c74a12ab8bc708b3f68b7a612d274bf31ada16faa12eb6b15.
Receipt normal-back80-half-random-preserved.json. Helper
Labs/MimicKitTraining/deploy_normal_half_random.py, new source
Saved/MimicKitEquipment/normal-back80-half-random-source.zip.
Resumed20261020_171428_uefn_normal_back80_half_random_512 on same
L4rovwuwstkm0s7r at.59/hour until stopped;trainer729/exitguard730.
Actor/critic Adam and normalization restored. Noise.075,GAE.98,
actorLR1.125e-6 and all losses/rewards unchanged.
Verified77521/1,270,120,448samples advancing;77491 checkpoint SHA
126f9ac9920dc86a2b6e4d8746f6a587242642f909d758b4970b2951771fbfd5 backed up.
Handoff complete marker written only after cohort, progression, backup and
guard checks. Bridge448/dashboard8920 publishing new run.
Live verification receipt normal-back80-half-random-verified.json.

## October20 - stiff and limp initialization datasets

User names the1,000 rotated/grounded poses "stiff inits"; existing corpus path
random-phat-poses-grounded/corpus.npz and bytes unchanged, preview/report named.
Limp inits generated from each stiff pose independently, zero starting velocity,
10policy frames at30Hz =80physics steps at240Hz =1/3second.
Script: Labs/MimicKitTraining/limp_random_phat_poses.py.
Dataset: Saved/MimicKitEquipment/limp-inits/corpus.npz.
SHA256:683193642d2350eedaef7cade16811f4f5161055b0296955bc5f539f18aca163.

Uses local CPU MuJoCo through existing CpuEngine model construction and
configure_native_model; current PHAT fingerprints verified, live normal-back80
engine configuration read. Same native spherical joint-limit approximation,
contact/friction/gravity/self-collision settings as training; no custom solver.
All actuators disabled via mjDSBL_ACTUATION, confirmed zero actuator force.
No passive stiffness/damping; zero velocity command alone was NOT used.
No policy inference, resets, projection or post-simulation floor lift.

1,000 final states finite, exact elapsed time verified, no MuJoCo warnings.
Initial body placement discrepancy <0.85micrometre; saved DOFs reconstruct
final positions within0.94micrometre and rotations within1e-6rad.
Native soft contacts leave floor penetration: median0.942cm,p95=1.963cm,
maximum3.136cm;958poses exceed1mm. This is explicitly retained, not hidden
or cosmetically corrected. Frame10 is a snapshot, not guaranteed settled rest.
NPZ stores local DOFs/root/world-body poses, actual final joint/root/body
velocities, native qpos/qvel, source_pose_index (zero based) and floor clearance.
Native settling-model.mjb saved for reproducibility. Prior14,000PHAT joint
checks describe stiff source only; no claim of exact PHAT-cone compliance
after native spherical-limit dynamics. Training unchanged; not deployed.
Preview http://127.0.0.1:8843/Saved/MimicKitEquipment/limp-inits/.

## October20 - random whole-body orientations and minimal floor height

User requested whole-body rotation for the retained1,000 poses, then the lowest
pelvis height at which no collider intersects the floor. Baked separately with
Labs/MimicKitTraining/ground_random_phat_poses.py into
Saved/MimicKitEquipment/random-phat-poses-grounded/corpus.npz.
Uniform SO(3) orientations, seed20261021; same local DOFs and zero velocities.
Root XY stays zero. Entire articulated body follows root through production FK.
Upright source and its14,000 passing Jolt joint-limit cases remain unchanged;
no joint limit changes or additional pose filtering.

Floor is world Z=0. Exact box/capsule/sphere support determines root height,
then baked float32 FK is rechecked and raised only enough for numerical roundoff.
Independent box-corner/capsule-endpoint verification:0/1,000 floor penetrations;
all1,000 would penetrate if lowered1micrometre. Maximum final gap0.139micrometres.
Pelvis heights0.130680–1.051713m. Maximum rigid transform/FK discrepancy
0.690micrometres. Self-overlap unchanged. Source current-PHAT fingerprints checked.
Corpus SHA256:6e313f73933fb7e53e1fdf003f756d7b1f6d1a403d84061b58c950eb7411b2b6.
Dataset includes root quaternion/position,34local DOFs,15world body transforms,
zero velocities, clearance per pose; report/data.json and browseable preview.
Preview: http://127.0.0.1:8843/Saved/MimicKitEquipment/random-phat-poses-grounded/.
Prepared only; training process/configuration and Unreal assets untouched.

## October20 - random PHAT pose corpus, preview before use

User now requests1,000 totally random local poses within PHAT, pelvis upright;
show first10 for approval before using them. Generated locally with
Labs/MimicKitTraining/random_phat_poses.py, seed20261020. No training process,
configuration, GPU allocation, Unreal asset or Play state touched.
Original1,500 corpus trimmed to its exact first1,000 without resampling.
Last500 poses and their validation evidence archived into Windows Recycle Bin.
Generator preserves the original1,500-sample RNG stream, retaining only its
first1,000 poses so regeneration does not change the reviewed samples.
Canonical current_source verification passes saved PHAT and mesh hashes;
PHAT asset SHA49994f0bb1257a1e9bdb5dd2aa229455544426a1b6a17d468cc6170df5e9640d.

Each retained joint sampled independently: uniform allowed twist/hinge angle,
uniform area within coupled swing ellipse. Existing reference quaternion
convention applied, actual float32 DOFs validated. Hinge connector locked-axis
export residue is normalized exactly as existing test_model.test_jolt does
(sub0.001degree), not an additional articulated freedom. No blending against
known poses, rejection/curation, floor cleanup or self-overlap filtering.
Pelvis quaternion XYZW[0,0,0,1], position[0,0,0.93119133]metres for every pose.
All root/joint velocities zero. Body positions follow FK; no independent limb
translation.14joints*1,000poses=14,000retained cases pass the project Jolt --limits probe.

Saved/MimicKitEquipment/random-phat-poses/corpus.npz contains34DOFs, roots,
15body poses, zero velocities and floor clearance; SHA
f4ad69d9ec140cf64e38a2724abf56c0f2954ca865c8f4ca19e99b3be840cd6c.
report.json records hashes/method/checks.133poses intersect the floor at the
fixed pelvis height; intentionally retained as raw joint-admissible poses.
HTML/data.json show first10 uncurated samples, orbit/zoom each, browse later
groups of10. All10 visually verified; first-ten.png saved.
Preview http://127.0.0.1:8843/Saved/MimicKitEquipment/random-phat-poses/.
Corpus not yet used for training; await user review. Whole-body rotation deferred.

## October20 15:45 - temporary normal get-up fine-tune, 80% back, frame0 only

User asks for100% normal get-ups,100% frame0 and80% back. Preserved latest
74681_final from151434 recovery run locally and verified S3 readback/ZIP CRC:
SHA39aab53d359374a0ee0b7f112433eff56bdeb11dbbfe9a4577aecd404a96f2f0.
Receipt normal-back80-preserved.json; previous recovery50/50 preparation saved
normal-back80-previous-plan.json. Shared mixed73832 locomotion fork checkpoint
and receipt remain untouched.

New config:idle/recovery fractions1,perturbed fraction0,normal random fraction0,
idle_recovery.random_start_fraction0,start_at_frame_zero true,back_row_fraction.8.
Back clip identified by its filename, not assumed index. Fixed stratified
assignment yields410back/102front rows (80.078%/19.922% nearest whole rows).
Rows keep this assignment at reset, avoiding episode-length-induced allocation
drift. Production allocation CPU test verifies410/102,allframe0; all-normal
replay path preserves array width when no perturbed replacement rows exist.
No losses/bonus/physics/optimizer changes. Normal failure−100 remains; proposed
normal-success bonus was only discussed and is NOT implemented.

First154538 startup failed before training: new assignment code shadowed the
existing sphere body-name list with clip names. Failure guard stopped billing.
Renamed clip_names and extended the allocation test to verify body names remain
unchanged. Same L4 restarted; cached runtime/kernel archives restored and CUDA
imports verified. Retained dangling venv symlink required finishing runtime
restore after extraction; no checkpoint/data loss.

Restarting20261020_155034_uefn_normal_back80_frame0_512 on L4rovwuwstkm0s7r,
.59/hour until stopped, trainer483/exitguard484,bridge29460/dashboard30576.
Noise.075,GAE.98,Adam actorLR1.125e-6 retained. No automatic duration or switch-back
invented; this temporarily supersedes50/50normal/perturbed recovery training.
Live setup verified512normal frame0,0random/perturbed/prior rows,410back/102front.
Resumed1,223,589,888samples; first74682 backup readback verified
SHAa6e9c97933539138d190049399ba402d28df11e4272e6f0ca849bd9513020b3f.
Setup guard released only after this verification. Local replayer20normal rows
converted without error; normal failure card plotting in15-50-34 view.
Helper deploy_normal_back80.py and normal-back80-* receipts.

## October20 15:14 - split policies; recovery-only launch

User decided to split locomotion/recovery checkpoints. Stopped mixed141039 run
at73832_final and downloaded the final ZIP to
Saved/MimicKitEquipment/preserved-checkpoints/20261020_141039_uefn_getup_success_value_512/checkpoint_0073832_final.zip.
SHA221ed14975999aab1846e53758113bb228418827acd4edbf8403ca1b05ba3699,
matching verified persistent readback; ZIP integrity checked. Do not delete this
shared starting point. Fork handoff receipt recovery-split-loco-fork-checkpoint.json
contains exact local path/S3 key; recovery-split-parent-run.json retains mixed
run source/control provenance. Locomotion fork requires its own state directory
and run controls, not this recovery pod/state.

Prepared source sets idle_row_fraction=1, idle_recovery.fraction=1,
perturbed_motion.fraction=.5, normal_getup_random_start_fraction=.5.
Normal random-frame mask is assigned *after* normal/perturbed membership so
evenly spaced masks cannot alias and make all normal rows random-frame.
512-row CPU allocation check:128 normal frame0,128 normal random,256 perturbed
frame0,0 perturbed random. Recovery source clips remain front/back; locomotion
clips remain loaded solely as the established perturbation pose pool.
Perturbation blend skew unchanged:probability2/3 above50% strength,1/3 below.
No normal idle or locomotion training rows. No loss/physics changes; noise.075,
GAE.98, Adam state/LR,−100 failures and head-success credit retained.

Starting20261020_151434_uefn_recoveries_only_512, trainer2478/exitguard2479,
bridge8240/dashboard1688, existing L4rovwuwstkm0s7r at.59/hour until stopped.
Live recovery_cohorts.json verifies128/128/256,0 perturbed random-frame rows,
0 prior-scored rows. recovery_setup.json verifies512 recoveries,0 ordinary idle,
0 walking,0 running. Restored sample count1,209,679,872. First73833 checkpoint
readback verified SHA261522f943bbb44623c8f80ec1b2a5c29968cb367e11a3f7a0b75c217771ed3f.
At73843,1,209,860,096 samples,~7,982transitions/s; no failure. Handoff guard
completed. Local replayer20rows all get-ups (2 normal,18 perturbed, retaining
the requested display policy); both normal/perturbed get-up cards plotting.
TensorBoard view switched to15-14-34 with Get-up failure filter.
Helper deploy_recovery_split.py, receipts recovery-split-*.json.

## October20 14:10 - adopted noise0.075/GAE0.98; full normal-get-up card

User approved adopting the completed comparison's alternative and adding a
proper normal-get-up failure card. Active run
20261020_141039_uefn_getup_success_value_512 on existing L4rovwuwstkm0s7r,
$0.59/hour until stopped. Trainer2154/exit guard2155, bridge25552/dashboard21856.
Resumed latest72108_final/1,181,433,856 samples. Local ZIP CRC and SHA match
persistent readback: f8048f15a97ba26dc70dda9c8d4f658c4fcdcd79225e97e82cb91ff94abf93f8.
First new72109 backup verified;72119/1,181,614,080 samples~7,889transitions/s,
no failure, bounded handoff watchdog completed.

Actor action noise0.075 and td_lambda0.98 persisted in prepared agent config.
Explicit CLI overrides apply after checkpoint restoration as well: checkpoint
load otherwise restores the saved fixed logstd tensor. resume.json confirms all
34 noise values0.075000003 and GAE0.98. Learned weights/Adam state, actorLR1.125e-6,
KL guard, native MJ physics, motion data, distribution and reward fixes retained.
Normal get-up, perturbed get-up and perturbed loco failure penalties remain100;
perturbed head-success value100/discount0.99 remains active. No additional sweep.

Reused per-world outcome buffers now count all training row completions; masks
preserve the existing perturbed summaries and add normal recovery rows excluding
perturbed rows. New normal_termination/Get-up failure percent equals100*FAIL/
completed episodes, including frame-0 and random starts. SUCC/TIME count in the
denominator only. Empty windows skipped; no fabricated historical zeros.
Same10update cadence and existing batched CPU reduction as perturbed cards;
no extra evaluation or replay simulation. Dashboard accepts upstream's
space-to-underscore tag sanitization and displays one normal-get-up card.
Visible filter now ^(perturbed|normal)_termination/ for14-10-39.
First full10update window:65.0122% normal failures, published locally.
Final UI check:7 card points all match raw failure/episode counters; latest
1397/2155=64.826%. Replayer converted20 rows successfully. Trainer72169/
1,182,433,280 samples~8,472transitions/s. noise-gae-ui-verified.json.

Production-method CPU test covers normal FAIL/SUCC/TIME, normal locomotion,
perturbed groups, counter clear and evaluation exclusion; actual noise override
test passes. Receipts noise-gae-{source,handoff,preserved,live}.json. Source and
handoff helper deploy_noise_gae.py; launch overrides stored in
getup-success-prepared.json. Earlier opening's “no alternative applied” is
superseded by this deployment.

## October20 13:55 - focused comparison complete, modest earlier improvement

Both branches trained128updates/2,097,152transitions from70639 with known-success
value100, actorLR1.125e-6 and identical restored Adam state/training seed13579.
Only noise/GAE differ: current.05/.95 versus alternative.075/.98.
Held-out928 perturbed get-ups at64updates: current892success/36failure,
alternative898/30. At128: current896/32,alternative905/23. All0timeouts.
Baseline894/34. Corresponding failure percentages: at64,3.879%vs3.233%;
at128,3.448%vs2.478%. Training408.39vs410.72seconds, excluding setup/evaluation
and paused wall time. This supports modest earlier/better learning in this window,
not a claimed2x long-run speedup. Single training seed.

Every checkpoint/seed's initial positions, velocities, alpha, side, and cohort
matched exactly. Final paired outcomes: alternative succeeds where current fails
10times, reverse1time (paired binomial p.0117, conditional on this training seed).
Hardestalpha>.75 cohort:215/245vs223/245successes. Final perturbed-loco failures
182vs180/432; normal-loco0vs0/184; normal-get-up293vs286/432.
No candidate applied; no further sweep queued. Results focused-success-results.json,
focused-success-summary.json, focused-success-analysis.json.

Scope: both comparisons use frozen130053 objective, including perturbed-success
fix and excluding newly added normal-get-up penalty. The live133905 run includes
normal-get-up−100 and keeps originalnoise.05/GAE.95. At final check71741/
1,175,420,928samples,~8,329transitions/s after comparison exited, backup71641,
no failure. Comparison process1224 gone; focused-success-final-health.json.

## October20 13:39 - normal get-up failures now cost100; live resumed

User asked to briefly pause comparison and add termination penalty to normal
get-ups too. Added optional normal_getup_failure_penalty=100 to current config.
Production done logic subtracts100 once for recovery_rows AND NOT perturbed_rows
AND final DoneFlags.FAIL. Uses existing parent normal-get-up failure conditions;
no new termination condition, no penalty on normal SUCC/TIME, no normal-loco
penalty. Perturbed get-up/loco costs and known head-reset success value unchanged.
Reward subtraction happens before PPO buffer capture; critic receives the cost.
Per-row replay metadata and reward verification include the new penalty.
Production-method CPU test covers normal failure/completion/timeout/loco plus
perturbed failure/success and confirms no double penalty; existing PPO test passes.

Brief guarded handoff saved71440_final/1,170,489,344 samples; downloaded locally
and matched S3-verified SHAdae6462634e22e0a6918a590ff3dc5c2176136d4bbe26c2f03d5cdeacff21278.
Source normal-getup-penalty-source.zip SHA
bf855d7a009a0d963800446072f87d4a9cecf6220c34422f069657430c1e95ac
uploaded/readback verified before stopping main. Active
20261020_133905_uefn_getup_success_value_512, trainer1587/exitguard1588,
bridge20904/dashboard12316 on same L4rovwuwstkm0s7r, until stopped.
New71441 S3 readback verified SHA231fe6a1c12e2bc3f34b879a791971ce6731ac6b26877f163709e2119e206f35;
handoff guard completed. ActorLR/optimizer/settings retained.
Receipts normal-getup-penalty-{source,preserved,handoff,live,resumed}.json.

Comparison1224 SIGSTOPped during changes and SIGCONT after new backup verified.
Both comparison copies continue to use old130053 config (normal penalty0,
perturbed success value100), not new live133905 config; this scope was stated to
user. No mixed-reward comparison or discarded/restarted sweep. Controller uses
its frozen launch directory even though live run changed. Pending results.

## October20 - newly requested focused learning-curve comparison

User explicitly authorizes retrying the specific earlier alternative on the
current corrected-reward run, to see whether failure falls earlier. This
supersedes the stop on comparisons only for this bounded two-way test.
focused_success_comparison.py launched queue1224, directory
/workspace/mimickit_trial/focused-success-20261020_130053_uefn_getup_success_value_512.
Both start70639; currentnoise.05/GAE.95 vs alternative.075/.98,128updates each,
same seed13579, actorLR1.125e-6, existing trained Adam moments. Success value100
and discount.99 are checked explicitly. Model/normalizer state captured at64/128
without interrupting training trajectories; evaluation afterward on identical
four seeds (928perturbed get-up starts per checkpoint). Training outcomes retained
per update. Maximum1200seconds per variant; no automatic expansion/deployment.
Main130053 unchanged and continues while this one helper shares the L4.
Results pending; do not mistake old incomplete sweep results for this test.

## October20 13:15 - stop repeated sweeps; main continues

User challenged the repeated comparisons and time spent. Stopped isolated queue551
and its process group, cancel.request written. Confirmed process gone; main
130053 still training at70890/1,161,478,144 samples without failure. No candidate
applied; no further automatic sweeps. Receipt success-sweeps-user-stop.json.
Main shared-GPU speed last measured~5.1k before sweep removal; earlier main-only
speed~8.1k. Do not present shared-GPU slowdown as a learning algorithm cost.

Latest completed70639 comparison: baseline894/928 get-up successes,0timeouts,
182 perturbed-loco failures; current settings after64updates/1,048,576transitions:
895/928,0timeouts,177 perturbed-loco failures,203.63training seconds,0 KL rejects.
Normal loco failures0; normal get-up failures290 baseline vs294 aftertraining.
All four seeds' starting positions/velocities/perturbations matched exactly.
Higher GAE.98 completed training but only1/4 evaluation seeds before cancellation;
not a completed comparison. Earlier full old-reward sweeps found noise.075/GAE.98
modestly better (confirmation835vs828 successes), not a substantial speedup.
Evidence does not establish a dramatically faster setup; further repeated short
sweeps are not justified without a specific new hypothesis/user request.

## October20 13:01 - corrected resume from70639; sweeps restarted

User explicitly approved resume from the selected checkpoint with success fix,
and continuing sweeps. Same L4rovwuwstkm0s7r successfully restarted at.59/hour,
until-stopped authorization retained. Runtime/source/kernel archives verified.
Active20261020_130053_uefn_getup_success_value_512; trainer444/exit guard445,
bridge21024/dashboard29160. Resumed70639/1,157,365,760 samples, source success
value100 (99 once on successful head reset, zero bootstrap) unchanged.
Fresh persistent readback of70639 matched70347318ed7b9bb6dca2f35f0f3a5414d1eb59f23a2ba8474870c65bc1d400af.
First new70640 checkpoint S3 readback verified, SHA
bb86fe2f22c4c2ee2bd9093ed4464d9177aa5ed585ace050eaef5a3c65df01b6.
Setup guard marked complete only after this verified backup.

Isolated sweep queue551 at
/workspace/mimickit_trial/success-sweeps-20261020_130053_uefn_getup_success_value_512.
Baseline and noise.05/.075 ×lambda.95/.98,64updates each, all frozen70639 and
current actor LR1.125e-6. No candidate autoapplied. Evaluation records normal
versus perturbed/recovery/gait labels to check collateral changes. Previous
67931 sweep cancelled/superseded; do not mix its results. Results pending.

## October20 12:55 - user stops overly early rollback

User explicitly stopped the67931 rollback and identified the circled low failure
region just before the rise. Training stop.request saved68077/1,115,389,952
samples; verified S3 SHA0928645c376eef81af256d326fb23e095897a9f218f78382eabf9094e4c6e313
matches downloaded local checkpoint. Sweep queue577 process group terminated,
cancel.request written. L4rovwuwstkm0s7r confirmed EXITED; receipt
user-correct-rollback-stop.json. Training and sweeps remain stopped.

Original094614 TensorBoard exact scalar minimum is5.619% at1,158,512,640,
followed by7.914% at1,158,676,480 and later rise. Available checkpoints are every
100updates.70639/1,157,365,760 (6.200% at its step) is the final saved checkpoint
before this trough/rise;70739/1,159,004,160 is already after it.70639 downloaded
from persistent storage and full ZIP CRC checked, SHA
70347318ed7b9bb6dca2f35f0f3a5414d1eb59f23a2ba8474870c65bc1d400af.
Both local paths/keys/hashes in corrected-rollback-preserved.json.
This supersedes the earlier67931 choice. Do not treat its incomplete corrected
success sweeps as the requested comparison from the user's intended checkpoint.

## October20 12:46 - resumed after access recovery

Active20261020_124643_uefn_getup_success_value_512 on owned L4rovwuwstkm0s7r,
.59/hour, until-stopped authorization retained. Trainer484/exit guard485;
local bridge26148/dashboard28928. Restored source/checkpoint/runtime/kernel
archives all SHA verified. Resume67931_final/1,112,997,888samples; success
value100 correction enabled, actor LR1.125e-6 and all other prepared settings kept.
First new67932/1,113,014,272 checkpoint47MB S3 upload+readback verified,
SHAb96749543fea989700e53df54b97c3096f0a892f831934525038d3eb00fd5d56.
Status subsequently67952/1,113,341,952samples;~8,124transitions/s before sweep
load. No failure/backup error seen. Evidence getup-success-launch.json,
current-run.txt and local mirrored run telemetry.
Follow-up success_learning_sweeps queuePID577 started after verified backup,
baseline plus noise.05/.075 ×lambda.95/.98,64updates each from frozen67931,
current actor LR, matched928get-up starts. No candidate deployed; pending results.
All temporary CPU helpers stopped. No extra.06/hour relay needed or deployed;
earlier relay approval question is obsolete. Cleanup and access evidence below.

## October20 12:46 - replay cleanup and storage access recovered

Deleted69 obsolete local rollout_step JSONs (1,965,414,157bytes) from Stepper's
mimickit run debug directories, keeping latest per run and latest3 in094614.
Checkpoints/TB untouched; exact manifest obsolete-local-rollouts-plan.json and
receipt obsolete-local-rollouts-deleted.json. Persistent mimickit tree1307files
and stepper/training/runs476files contain no standalone replay data eligible for
this cleanup; matching names there are source code. No persistent objects deleted.
Persistent MimicKit usage39.48GB; total volume scan incomplete, do not claim total.
New1MB mounted write/fsync/read succeeded; S3 readback SHA matched in1.15seconds;
temporary probe deleted. EU-RO CPU S3 request4.42seconds; independent US-MO-2 CPU
(same DC as failed L4) request1.14seconds. Both CPU helpers confirmed stopped.
Current evidence supports transient access failure, not full-volume failure;
local deletion did not free persistent space and cannot explain remote recovery.
Exact provider-side cause remains unknown; no permanent CPU relay deployed.
Latest replacement L4 rovwuwstkm0s7r at.59/hour, bounded10minute setup guard.
AWS managed downloader has verified source/resume/runtime/kernel archives; restore
finishing. Not yet trainer launch at this entry. Prior pod states retained.

## October20 12:31 - storage investigation, cause still unproven

No trainer running. Latest owned L4 9r63p3vlvogqz5 confirmed EXITED
(sdk-storage-block-stop.json); temporary CPU helper t9qpwmxvnezq55 also EXITED
(storage-cpu-stop.json). Prior owned GPUs remain stopped.
AWS managed multipart download retrieved and SHA-verified the full409,880,235-byte
runtime locally in107.42seconds. The same SDK on the replacement L4 still timed
out reading source; tiny metadata GET also timed out. Disabling optional SDK
checksums and forcing path addressing did not fix the short metadata probe.
This local-versus-pod difference narrows the fault but does not establish why
it began, nor prove a regional outage. Runpod status reports fleet maintenance;
the EU-RO storage incident shown in history is October10, not current.
Direct EU-RO L4 allocation rejected for no capacity despite catalog Low stock.
CPU direct mount could list the runtime archive and manifest. Full mounted-file
read/hash and a working relay have NOT been tested; do not call the relay proven.
Proposed CPU relay adds.06/hour to L4.59/hour. Approval question pending;
user instead asked whether the cause is understood. Do not launch that paid relay
without resolving approval. Current pod.json is9r63p3vlvogqz5; older state retained.
Helpers sdk_success_restore.py and mounted_success_resume.py are prepared,
not a verified successful resume. Local runtime cache is retained for fallback.

## October20 - approved rollback and success credit; replacement setup

**Current outcome12:09:** restart is blocked by Runpod storage, NOT running.
Replacement iiprikebnm51jl confirmed EXITED at Unix1792490950.61 (~9.2minutes
setup, within10minute guard). Receipt getup-success-storage-block-stop.json.
Runtime-cache download ultimately returned HTTP524 (origin timeout); source/
checkpoint GETs also repeatedly timed out from the replacement. Local metadata
and checkpoint/source reads had succeeded slowly before allocation. This is not
evidence of disk-full; do not delete unrelated data as a timeout workaround.
No new checkpoint/trainer/learning sweeps started. Both old and replacement GPUs
are stopped, retained disks untouched. Current canonical pod.json refers to
iiprikebnm51jl; old state retained under retained-pods/ka68jrougesuit.
Next action: restore verified runtime/source/resume on an available owned L4 once
storage responds, launch via resume_getup_success.py, verify advancing steps and
first backup/replayer before success_learning_sweeps.py start. The start/replace
helpers originally target ka68jrougesuit; reconcile current stopped replacement
before using them, never allocate duplicates. Do not invoke stale curriculum
heartbeat or older rollback scripts.
Follow-up sweeps prepared: frozen67931, corrected success accounting, current
LR1.125e-6; noise.05/.075 ×lambda.95/.98,32tick rollouts,1,048,576transitions each,
plus unchanged baseline and928 matched get-up evaluation starts. No candidates
automatically applied. Previous completed sweeps used old reward, so this rerun
is necessary before treating their winner as applicable.

Latest user supersedes the hold: resume from before stalling with a safety buffer,
then continue isolated sweeps. Selected67931_final/1,112,997,888 samples, earlier
than69138 which had0timeouts among928 held-out get-ups.67931's seven recorded
perturbed get-ups all hit the head reset. This is evidence of absence in sampled
rollouts, not proof every possible starting pose is unpolluted.
Selected SHA5e79866e8a4704214b7d43ce964ff83902c56107a412cc53dae4418809037436.
Local integrity and fresh S3 readback verified; source getup-success-source.zip
SHA4c06482b094ff6af80f6b7bda7d51604117d694a061ee0935d0cb08298ebc41c
also uploaded/readback verified. Receipts getup-success-prepared.json and
success-checkpoint-manual-readback.json.

Implemented optional perturbed-get-up success value100 at gamma.99 by paying99
once on the head-reset transition and using SUCC with zero continuation. This
is exactly r+.99*100, without double counting. Ordinary clip completions retain
zero continuation and receive no bonus. TIME timeouts and−100 failures unchanged.
Config/agent startup checks gamma and zero ordinary-success continuation.
Replayer includes the per-row bonus in reward validation. CPU production-method
test confirms success target99.8, normal completion.8, failure−99.2 and timeout
−28.9 with deliberately bad critic−30. Critic gradient correct. Seven archived
success rollouts also pass updated replay conversion. Tests receipt success-value-tests.json.
Backup readback now retries interrupted streams from byte0 up to3times, closes
every stream and still rejects permanent errors/checksum mismatches; CPU tested.

Old ka68jrougesuit cannot restart (GPU reassigned), remains EXITED. Replacement
L4 iiprikebnm51jl allocated at.59/hour under existing replacement/rate authorization.
Setup guard19168 stops at Unix1792490997.93 unless launch changes authorized clock.
No trainer yet at this entry. Source SSH upload timed out at~9MB; continuing via
cloud downloads with existing runtime-cache User-Agent (default urllib UA got403).
Storage is slow: even tiny metadata reads take~39seconds;47MB checkpoint readback
took54seconds. No disk-full error; network volume allocation200GB, local C:~9GB
free, old pod workspace~8GB of20GB. No unrelated files/checkpoints deleted.
Current LR1.125e-6 and harder sampling2/3 retained, other settings unchanged.

## October20 11:38 - training held; head-reset incentive audit

User requested holding restart to investigate perturbed front get-ups settling
below the90% head reset. Owned L4 `ka68jrougesuit` confirmed EXITED, billing stop
receipt `Saved/MimicKitEquipment/head-reset-investigation-stop.json`.
Do not automatically resume while this investigation/change is pending.

Latest retained checkpoint70939 (1,162,280,960samples) is downloaded locally:
`Saved/MimicKitEquipment/preserved-checkpoints/20261020_094614_uefn_getup_skew_linear_512/checkpoint_0070939.zip`,
SHA256 `b9f910c28ac9ad37457b4b43ce3b6a6cf6cda3422a90b0650a8487d8be99fb1a`,
matched to retained disk. The run failed at71039 waiting for70939 S3 readback
(ReadTimeoutError);71039 was NOT saved. Last verified S3 receipt70839;70939 upload
exists but persistent readback still needs verification before resuming.
GPU briefly restarted for recovery, then stopped on user's hold. Runtime restore
may need repeating. No new allocation. Local readback-stream retry change in
backup.py is NOT deployed or yet tested; do not claim it protects production.
No disk-full evidence: pod workspace used8GB, local C: had~10GB free.
User authorizes removing redundant old replayer data if storage is full, preserving
required checkpoints/UE assets. No deletion performed during this audit.

Offline evidence from70939's saved deterministic replay:
- Front row2 settles at85.9% head height, moves within85.89–86.00% over its last
  60ticks, earns0.8449/tick out of maximum1, and times out at180ticks.
- Four recorded back rows also time out at85.6–87.4%. Three other front rows
  successfully cross90% at21,21,36ticks. This is not universal inability to rise.
- Current reward is1−10*mean(body-origin XYZ error²). Low-head penalty−100 only
  applies from tick60 at<=50%. Between50% and90%, no deadline failure applies.
- Both90% head resets and180tick timeouts are TIME. PPO retains V(final_obs)
  and breaks the trajectory recursion; it does NOT use the next spawned pose.
  Thus no success payout exists. Final states are bootstrap targets but are not
  stepped from after reset, so their values rely on generalization.
- CPU reconstruction of recorded154inputs reproduces phase outputs within
  0.000378, allowing approximate critic inspection: stalled front final value
  ~84.89; three successful front final values~4.70,11.48,−30.39. Corresponding
  last-transition training targets~84.89 versus5.44,12.12,−29.38.
  These are different trajectories, not matched action counterfactuals; the
  evidence supports a strong incentive defect, not a proven sole causal factor.
- Stable0.845 rewards with gamma.99 imply continuing value~84.5, matching the
  stalled critic. Successful final estimates are poorly anchored. Current
  accounting therefore makes hovering attractive and fails to reliably credit
  completion. Earlier69138 held-out baseline had no timeout get-ups among928;
  latest replay establishes that stalling appeared subsequently (samples differ).

Script `Labs/MimicKitTraining/audit_head_reset_offline.py`, receipt
`Saved/MimicKitEquipment/head-reset-offline-audit.json`. CPU only; no billed
physics experiments. Actual saved rewards/poses/outcomes are exact; reconstructed
critic values are approximate, cross-checked against recorded phase outputs.
Proposed correction, NOT applied: preserve immediate90% reset but explicitly
credit successful completion with known absorbing-success value100
(maximum per-tick reward1/(1−.99)), instead of guessed continuation. Scope only
perturbed get-up success; ordinary animation SUCC semantics must remain unchanged.
Do not merely change TIME to zero-value SUCC: that would remove remaining value
and can increase the incentive to delay success. No reward/termination edits made.

## October20 - learning ablation screening and confirmation complete

All twelve combinations completed, plus the old-sampling control and a frozen
baseline. Each trained configuration used 1,048,576 transitions from the same
verified checkpoint, seed13579. All accepted2,560 actor steps; no KL rejects or
LR reductions. Training took202.8–206.0seconds per candidate on the shared L4.
The main trainer8547 continued throughout.

Noiseless success counts on the same928 get-up starts:

| Noise | Rollout ticks | GAE lambda | Get-up successes | Loco failures /432 | Other failures /688 |
|---|---:|---:|---:|---:|---:|
| .05 | 32 | .95 | 824 | 181 | 165 |
| .05 | 32 | .98 | 825 | 185 | 156 |
| .05 | 64 | .95 | 818 | 183 | 157 |
| .05 | 64 | .98 | 824 | 182 | 149 |
| .075 | 32 | .95 | 828 | 187 | 154 |
| .075 | 32 | .98 | 828 | 181 | 152 |
| .075 | 64 | .95 | 824 | 186 | 157 |
| .075 | 64 | .98 | 826 | 183 | 150 |
| .10 | 32 | .95 | 822 | 180 | 151 |
| .10 | 32 | .98 | 826 | 180 | 149 |
| .10 | 64 | .95 | 820 | 186 | 150 |
| .10 | 64 | .98 | 823 | 184 | 150 |

Frozen baseline819/928; old uniform-sampling control824/928. Sampling alone did
not improve the overall count in this short trial. Candidate.075/32/.98 recovered
11 baseline failures and lost2 baseline successes; net9 hard-front recoveries.
Its apparent advantage over current settings is only4 cases, not evidence for
a large learning-speed multiplier. No alternative hyperparameters deployed.

Confirmation queue15026 completed current.05/32/.95 against.075/32/.98 from the SAME
frozen checkpoint, new training seed24680, 2,097,152transitions each (128updates).
Four identical held-out evaluation seeds retained. Current:828/928 get-up successes,
182/432 perturbed locomotion failures,215/432 normal get-up failures.
Candidate:835/928,181/432,158/432 respectively. Normal walking/running and plain
idle had zero failures in both. Training402.37 versus403.06seconds; no KL rejects.
Modest repeated improvement plus better normal-get-up retention, not evidence of
2x learning speed. All helpers exited; no candidate hyperparameters deployed.
Results in learning-ablations-{results,summary,comparison}.json.

Cross-check with prior LR audit: all four get-up observation and velocity hashes
match exactly. The frozen checkpoint's819 successes versus earlier794 represent
real progress between checkpoints, not different evaluation starts.

## October20 09:46 - harder get-up sampling deployed; learning ablations running

User requested twice as many perturbed get-up starts above50% strength as below.
New config `perturbed_motion.getup_upper_half_probability=2/3`; inverse-CDF
sampling remains uniform inside each half. Default.5 preserves the old RNG/output
exactly. Applies only to perturbed get-up local-pose blend, not normal get-ups,
locomotion yaw, cohort proportions, rewards, physics or termination.
Deterministic300,000-point sampling check:100,000lower/200,000upper,
conditional means.25/.75; receipt getup-skew-sampling-test.json.

Resumed from69138_final/1,132,773,376samples, local and S3 readback verified SHA
c70de5b48ccd80dfe26dec926b0a7664facdb993f340e3f6954236f88d7e4875.
Active20261020_094614_uefn_getup_skew_linear_512, existing L4ka68jrougesuit,
trainer8547/guard8548, until-stopped authorization retained. Adam state and
actual actorLR1.125e-6 retained. Bridge28848/dashboard10416.
Source getup-skew-source.zip SHA
ce20b72ec1f308bd7381f7813295d56106eb795241371c579e3b8b4c2e4b08a7.
Receipts getup-skew-{launch,preserved-checkpoint,source-verified}.json.

Bounded sequential diagnostic queue8626 uses the same preserved checkpoint,
never live weights: noise.05/.075/.10 × rollout32/64 × GAE lambda.95/.98;
plus old uniform sampling control and unchanged-policy baseline.
Each trained variant gets1,048,576transitions (64×32 or32×64×512), full PPO
including critic. Explicit noise override AFTER checkpoint restore. Existing
KL guard and inherited LR remain active; guard reductions are measured.
Four held-out evaluation seeds, uniform0..1 strength for EVERY variant, noiseless
actions and first episode per row. Also measures locomotion/other-row failures.
Same existing GPU, one helper at a time,700s timeout each. No new allocation.
Scripts audit_learning_ablations.py/run_learning_ablations.py and receipts
learning-ablations-{plan,results,summary}.json. Results pending; no candidate
settings selected for production.

Evaluation audit: an initial whole-batch bitwise hash check was too strict.
Repeated reset before/after32frozen steps gives EXACT get-up inputs/velocities;
other rows differ by at most1.1921e-7 in observations and4.7684e-7m/s in body
velocity. Numerical variation, not a changed sampled pose. Diagnostic
learning-ablations-reset-audit.txt. Evaluation now checks get-up hashes exactly,
positions/assignments/blends exactly, other observation/velocity arrays with
1e-6 absolute/relative tolerance. Baseline includes untrained warmup for compiled
math. Queue restarted as9381; obsolete partial candidate excluded. Uniform-control
first result predates array recording and is explicitly a preliminary control.

## October20 - 10-update LR comparison completed; production remains2x

User requested2x(current),4x,8x for10updates. audit_lr_ten_updates.py runs disposable
learners with deployed code/settings on existing L4; live7410 never paused or
modified. Frozen verified checkpoint68632 SHA
0a6011133040b2a63988756f7d9f826176bf884b49930a94073761f1f86f76b8.
Each candidate starts with identical checkpoint/Adam state and reset RNG, runs
10 FULL PPO iterations (32ticks*512worlds each;163,840fresh transitions, actor AND
critic learning), then deterministic evaluation on4held-out seeds/928getup starts.
Initial training observation hashes and every evaluation position/velocity/
observation hash, blend, side and row ID match exactly across candidates.
Baseline is the unchanged checkpoint, evaluated on those same starts.

Baseline794/928success(85.56%). Fixed2x1.125e-6:792/928(85.34%);
fixed4x2.25e-6:792/928(85.34%); fixed8x4.5e-6:787/928(84.81%).
2x/4x accept400actor minibatch steps each with zero rejects; maxKL.027/.066.
Fixed8x hits guard8of10iterations, accepts177steps total, maxKL.171,
no full-rollout rollback. Relative baseline2x gains1/loses3 cases,4x gains2/loses4,
fixed8x gains2/loses9. Training time33.25/32.72/30.82s respectively on shared GPU;
~68-70s per complete candidate including construction/evaluation.
No evidence from this short single-training-seed test to raise production above2x.
Small success differences are not a reliable long-run ranking.

Initial8x production-style trial automatically reduced LR to4x at iteration3
after a full rollback; it ended795/928, but is NOT a pure8x result. Retained as
additional evidence. Corrected fixed8x comparison reasserts requested LR before
each disposable iteration while retaining all KL rejection/weight rollback.
This fixed-rate option is test-only, never enabled in production.
Raw results lr-ten-update-results.json, lr-ten-update-fixed8.json; comparison
lr-ten-update-summary.json; receipt lr-ten-update-launch.json. Remote diagnostic
folder lr-ten-update-20261020; all probe processes exit after completion.

## October20 08:57 - doubled actual actor LR and observation optimization deployed

User authorized both changes and resume from latest. Helper resume_lr2_graphed.py
cleanly stopped080052, preserving checkpoint67931_final at1,112,997,888samples:
SHA5e79866e8a4704214b7d43ce964ff83902c56107a412cc53dae4418809037436.
Verified local archive/CRC and persistent S3 readback before launch. Extracted
actual saved Adam LR5.625e-7 and passed explicit post-restore override1.125e-6;
Adam moments/counters, critic and KLguard.18 preserved. No implicit YAML-rate use.

Run20261020_085731_uefn_lr2_graphed_linear_512 on existing L4ka68jrougesuit,
trainer7410, exit guard7411, until-stopped control retained. Local bridge13968,
dashboard18236. Source lr2-graphed-source.zip SHA
b15a77a15d608891b82733d6173ff6f44be88d3d5adb10b3299d553ee88a5687.
Deploys previously validated device quaternion and graphed physical observations,
plus the replay penalty-validation/download-retry fixes. Actual new env/engine
configs match previous run. No solver/contact/physics-frequency changes.
New TB run has its own training outcomes; no historical curves spliced in.

Resume receipt confirms prior samples1,112,997,888, both optimizers restored,
LRoverride5.625e-7→1.125e-6. First update67932 advances to1,113,014,272samples.
First checkpoint67932 S3verified SHA
63bced7ce8495b2f07fd29c5f083f0c3b6c0f802eaa637d864cd47829668b84c.
Startup actor updates accepted40, rejected0, KL.0152. First-step timing includes
warmup; use subsequent live timings for speed. Receipts lr2-graphed-{launch,
preserved-checkpoint,source-verified,live-verification}.json.
Live follow-through:67982/1,113,833,472samples, recent update2.0129s /
8,139transitions/s (about7% above prior~7,585/s; early live observation, not
the isolated14% benchmark claim). LR1.125e-6 and zero rejected actor steps
confirmed in synced events. Replayer HTTP serves67932 with20rows; both training
failure cards published in the new own-run dashboard.

## October20 - perturbed get-up progress/calibration audit; live run unchanged

User reported slower learning. Read the actual trainer events, using episode-count
weighted rates rather than the small noiseless replay sample. Previous072057 run's
four equal sample windows: getup failure24.93,22.46,20.42,19.83%. Current080052:
18.34,18.63,18.00,17.78% (through~1.106B samples). No180-tick timeouts in those
logged getup outcomes; other endings were successful90%-head resets. Throughput
~7.6ktransitions/s before probe. Critic loss rose from~9-12 to~19-25 after the
new loco failure cost; this is an observed adjustment, not proof of a learning bug.

Actual restored Adam actor LR is5.625e-7, not YAML4.5e-6. It was already at that
value before today's00:52 run: no recent LR reduction explains the new slowdown.
kl_guard.py halves LR on first-step rejection/full rollback and never restores it;
resume preserves optimizer param groups. Current logged updates accept40/40,
zero rejects/rollbacks, KL~.010 versus limit.18. It is conservative but not frozen.

Isolated audit_getup_calibration.py used deployed modules and verified checkpoint
67483 SHA e6658c52b791fbf7fdb92a8aef0c447e62ec8884e41036ba5df660ce401c9100;
512worlds including232perturbed getups,108perturbed loco. Six frozen-policy32-tick
buffers, then matched actor-only updates from identical weights, Adam moments,
batch order and RNG. Total39.77s; helper exited; no live checkpoint/config change.
Completed episodes by blend strength (known pose0/random local pose1):
front0-.5:254/254 successes; .5-.75:80/117; .75-1:3/129.
Back0-.5:224/226; .5-.75:112/117; .75-1:99/107.
These are sampled completed episodes, not an exhaustive validation suite.
Failed hard-front heads averaged~14% of standing height, far below the50% cutoff;
this is not simply narrowly missing that threshold. Remaining difficulty is
concentrated in heavily perturbed front starts.

Matched single-rollout actor test: current/2x/4x/8x LR give getup clipped-PPO
surrogate improvement .03962/.04687/.04857/-.01319. KL .00969/.01803/.03222/.15712.
First three accept40steps;8x accepts10 then rejects1. Thus2x is a reasonable next
trial, not a claim of18% faster real learning;4x adds little on this batch and8x
worsens it. Recommendation only, no LR/reward/proportion/termination change made.
No justification found to increase getup penalty or loosen head threshold.
Counterfactual removing loco penalty with unchanged critic was diagnostic only;
its advantage variance is not a causal estimate of long-run cross-task dilution.
Receipts: getup-progress-calibration-audit.json, getup-calibration-sidecar.json.

## October20 - empty replayer: penalty validation and retry repair

Current080052 trainer4368 remains running unchanged. The original replay
conversion failure was a missing `loco_failure_penalty` subtraction in replay.py's
reward validation: valid reciprocal rewards with the new terminal -100 cost
were rejected. That exposed a second bug in bridge.py: it promoted the completed
download before conversion, then retried only its last chunk after conversion
failed. The resulting local replay was missing exactly the first2,097,152bytes.
Remote replay passed ZIP CRC validation; training was not corrupted.

Replay validation now includes the recorded loco penalty only on FAIL. Bridge
validates partial-file offsets, converts before promotion, resets failed file
transfer state to byte0, and continues syncing other telemetry after a per-file
failure. Existing valid rollout/archive remains available while retrying.
Regression tests cover failed conversion, whole-file retry, missing/duplicated
chunks, changed file versions, terminal penalty and timeout without penalty.
Only local bridge restarted; no trainer/physics/reward changes and no deployment
of the pending performance package. Receipt: replay-sync-repair-verification.json.
Verified step67383 with20rows through the actual replayer HTTP endpoints;
local archive SHA604bfd12ee94 matches remote, ZIP CRC passes, bridge error cleared.
Six regression tests pass. New local bridge parent2140; trainer still4368,
step67433 at1,104,838,656samples and~7,575transitions/s during repair.

## October20 - further rollout optimization prepared; live run uninterrupted

User requested continued performance work aiming at2-3x. Existing live trainer4368
on ka68jrougesuit remains untouched. Isolated bounded probes share its GPU, so
reported A/B measurements are relative, NOT a claim of new live throughput.
Found hidden cudaStreamSynchronize/CPU-to-GPU temporary in upstream TorchScript
exp_map_to_quat and calc_heading; this also prohibits CUDA graph capture. Replaced
only the observation/joint-conversion formulas with device_quaternion.py using
the same operation order, thresholds, normalization and handedness. Full512-body
physical observations now replay one PyTorch CUDA graph; current engine arrays
are copied each call, commands/phase assembled through the original methods,
output storage cloned to protect terminal/reset observations. Empty subset uses
upstream shape behavior. CPU/other observation layouts preserve their prior path.

Alternating original/optimized/optimized/original whole PPO updates:3.3804,
2.9637,2.9547,3.3581 seconds:1.139x throughput /12.2% less time. Observation50-call
measurements .1524/.1943 original vs .02386/.02523 optimized (~7.06x). Actual reset
poses, arbitrary subsets,changed joint state,old-output lifetime checks passed;
observations exactly equal on those states. Random quaternion/observation probes
showed <=9.54e-7 rounding difference; forward/inverse tests0/1/7/512 rows passed.
No contact/motor/frequency/optimizer/reward/configuration changes. Helpers default
on in LOCAL source for subsequent PerturbedOmni runs, NOT retroactively in live PID.
Prepared graphed-observations-source.zip SHA
b759748782a747942b13b28fb9a35a2b8e16bf1b37072bb3dda49337835e7d80,
verified runtime inventory. Receipts perf-observations-{result,profile_1}.json,
graphed-observations-prepared.json; earlier current profile perf-current-*.
Physics now largest measured phase:~1.21s of instrumented2.94s (concurrent GPU),
actor/critic~.53s, reset~.60s. Instrumented nested ranges overlap. No2-3x claim.

Read official MJWarp performance guidance before matrix-layout experiment:
https://mujoco.readthedocs.io/en/stable/mjwarp/index.html#performance-tuning .
No contact capacity reduction or solver-iteration/tolerance/frequency change.
Native dense-vs-existing Jacobian layout probe completed; NOT selected.
After full mjw.reset_data plus qacc/state restoration,32 physics substeps on512
worlds: existing .1105/.1150s vs dense .1066/.1102s (~4%, within shared-GPU
variability). Original-repeat itself varies up to1.70mm at one body; dense
1.69mm, rms26.7micrometres, qvel maximum .082 vs original-repeat .043. Initial
partial-reset comparison invalidated and retained only for audit, not a speed
claim. No solver layout/settings/capacity changes promoted. Receipts
perf-layout-reset-result.json and device-quaternion-verification.json.
All isolated helpers completed; only validated observation/conversion change
prepared for next authorized restart. Existing trainer never paused/restarted.

## October20 - perturbed locomotion failure penalty handoff

User requested the same get-up termination cost for perturbed locomotion and
resume from latest. Added explicit perturbed_motion.loco_failure_penalty=100;
subtract once on COM2 FAIL after the existing 8-tick grace, before PPO copies
the transition reward. Normal locomotion, ordinary idle, timeouts, successful
head resets and get-up rewards unchanged. Two package changes only: env_config
and perturbed_omni.py. CPU test verifies cohort/grace/timeout masks and no reward
carryover. Existing critic FAIL semantics already zero bootstrap and preserve
full terminal cost. Optimizations and full-training outcome cards retained.
Guarded helper resume_loco_failure_penalty.py preserved latest66582_final,
1,090,895,872 samples, locally and S3 readback verified SHA
21cd0cb0c49b474527079d35d279f04d84e1d983b1691118bf1098187de37ed3.
Launched 20261020_080052_uefn_loco_failure_penalty_linear_512 on existing
L4 ka68jrougesuit, trainer4368, until-stopped limit and failure guards retained.
Live verified step66593 /1,091,076,096 samples; first checkpoint66583 S3 readback verified. Six perturbed loco replay rows:3 FAILs each exactlyone -100 cost (max float error2.81e-6),3 TIME endings no cost. Example terminal reward .558182->-99.441818. Steady startup throughput~7,009 transitions/s. Receipt loco-failure-penalty-live-verification.json.

## October20 07:20 - optimized continuation and training outcome cards launched

User authorized resume from latest with speed fixes and full-training outcomes;
then asked to skip further investigation of the noisy sampled graph and launch.
Run20261020_072057_uefn_fast_training_outcomes_linear_512, existing L4ka68jrougesuit,
trainer4112, until stopped, latest65624_final at1,075,200,000 samples. Checkpoint
SHA80ee9ea2947a10aaa4e0b6945621ecbe409997690d0e69e2f293ebf6d5dfa2e3
verified locally/S3. Env/agent configs byte-identical to previous package.
Batched joint conversion and prior exclusion now deployed. New GPU per-world
failure/end/head-reset counters accumulate TRAIN only, exclude evaluation and
reset only when logged every10updates. Two failure cards count all completed
perturbed loco/getup episodes in each interval; no temporal smoothing, no false0
when denominator0. Raw denominator/headreset counts retained in trainer events
for audits, not extra dashboard cards. Dashboard training_outcomes=True disables
sample-derived outcomes for this run. History NOT stitched. Old sampled records
remain in their own old runs, excluded from new-run view.

Graph investigation: step65394 zero failures had7starts alpha.07-.698, all head
resets. Step65494 3/7failures were alpha.813,.854,.943; four easier starts succeeded.
Different difficulty, not matched-policy comparison; cannot infer regression.
Receipt failure-jump-sampling-audit.json. Counter unit test checks fail/reset
separation, no evaluation contribution, clearing between intervals, separate
cohorts. Launch/backup receipts fast-training-outcomes-*; helper
resume_fast_training_outcomes.py. Live verification: step65655,1,075,707,904 samples; first new checkpoint65625 S3 verified. Recent update2.175s /7,532 transitions per second (~25% higher throughput than previous ~6,046/s). Every10updates:1953 getup episodes,518 failures=26.5233%;199 loco episodes,93 failures=46.7337%. Successful head resets counted only in denominator. Two own-run cards published; source writer sanitizes spaces to underscores, dashboard accepts that form and keeps readable display labels. Local publisher restarted21716; trainer uninterrupted. Receipt fast-training-outcomes-live-verification.json.

## October20 - performance audit and optimizations READY, not live

User requested profiling/AE removal WITHOUT stopping live trainer3279.
Live ptrace sampling rejected by container SYS_PTRACE policy; no intrusive
workaround. Two isolated CPU/GPU profiling helpers, each bounded180s, shared
L4 briefly; trainer kept running. Helpers completed. Source fixes are NOT in
live process; apply on next authorized checkpoint resume, do not claim live speedup.

Profile: rollout/collection3.54s out of instrumented4.13s; actor.477s,
critic.096s. Nested times overlap; current host shared, not production throughput.
Joint conversions alone were major CPU-dispatch cost:101 forward calls expanded
into1,414 individual joint calls. Repeated observations and resets dominate.
New batched_joint_conversion.py groups hinge/spherical joints using SAME torch
quaternion functions. Tested empty/1/7/512 rows, large random angles/zero angles:
forward and inverse output differences exactly0. Alternating isolated benchmark:
100 conversions .802/.781s original vs .116/.135s batched (~6.3x faster).
Full PPO alternating updates4.062/4.063s original vs2.924/2.982s batched (~27%
less time). Concurrent GPU workload means no claim of actual live speed yet.

perturbed_omni now excludes232 idle-position getups from prior buffer/scorer;
358->126 AE rows. Retained score equivalence passed; getup rewards/losses exact.
AE-only timing ~.025s/30calls both sizes, so exclusion is correctness/efficiency
cleanup, not major measured speedup. _prior_raw excluded rows remain0; AE raw
diagnostics now concern only scored rows. Ordinary perturbed idle/loco retained.
Batched conversions installed for PerturbedOmniEnv and included in source inventory.
Prepared package fast-perturbed-source.zip; receipt fast-perturbed-prepared.json.
Evidence perf-audit-{profile_0.json,python_calls.txt,ae_compare.json},
perf-batched-result.json. Test/profile scripts profile_perturbed_sidecar.py,
verify_batched_sidecar.py. No physics, optimizer, learning objective or proportions
changed. Cannot quantitatively attribute all historical slowdown to host vs code
without matched old-workload test; current conversion bottleneck is directly tested.

## October20 - TensorBoard experiment boundaries corrected

User rejected previous-run history repeated under new experiment names. Outcome
publisher now reads only each run's own private cache, ignoring historical-source
lists. Removed derived outcome summaries and rebuilt under original run names;
no cross-run stitching, averaging or step renumbering. Raw training curves and
private outcome caches preserved. Prior event files recoverable under
Saved/MimicKitEquipment/retired-cross-run-events. Local publishers/TB restarted;
remote training untouched. Only current publisher needs to remain live, earlier
experiments are static. Receipt outcome-run-boundaries-fixed.json. This supersedes
all earlier instructions describing combined continuation history in one run.

## October20 06:52 - replay selection resumed from latest

User authorized brief resume. Run20261020_065209_uefn_replay_getup_selection_linear_512
resumes65093_final at1,066,500,096 samples, preserved locally/S3 with SHA
4516efe97a3506a65fe24058053eabb5630db2025078654479f4b585bae00bc6.
Package comparison proves only pipeline/observe_many.py changed; training config
byte-identical. One normal get-up per motion, extra slots perturbed get-ups;
20 total replay rows. Existing until-stopped L4 and guards retained.
Proportion audit:358idle/getup (340getups+18idle),154loco(78walk+76run),
70/30 as requested; adaptive sampling off. Outcome graph is selected evaluation
episodes, not512-world statistics: preceding point2/3failures=66.7%; changing
pose difficulty and tiny sample make it jagged. Historical zeros predate low-head
failure rule, not evidence of successful recovery. Receipts replay-getup-selection-*.

## October20 - replay selection change prepared, NOT live

User requests one normal front/back get-up, replacing extra normal get-ups with
perturbed ones without stopping training. observe_many.py now prepares that
selection, preserving existing non-get-up rows and recording count. Synthetic
selection checked across12 rotations: one normal per motion, replacements
perturbed, no duplicate world IDs. This is NOT deployed to the live trainer:
MultiRecorder.start has no live reload/config hook. User's no-stop constraint
preserved. Apply on next authorized restart; do not claim live row changes.

## October20 - perturbed get-up terminal reward penalty

Live run20261020_064321_uefn_getup_failure_cost_linear_512 resumed from
64965_final at1,064,402,944 samples. First64966 checkpoint S3 verified.
Live NPZ confirms failures receive exactly100 subtraction on one tick each
(-1.223922 -> -101.223923); successful head reset receives zero subtraction.
Receipts getup-failure-cost-live{,-reward-test}.json.

User approved subtracting100 reward once for perturbed get-up FAIL, and asked
for critic-path verification. Config getup_failure_penalty=100. Reward applied
in _update_done AFTER SimEnv _update_reward, before collection. Normal rows,
head-height TIME resets and timeout TIME resets receive no penalty. Existing
linear pose reward remains; failure continuation value remains0 (DeepMimic
get_reward_fail), NOT -100/(1-gamma). PPO _build_train_data reads this reward,
computes TD-lambda returns and stores tar_val; critic MSE fits unclipped tar_val.
Actual deployed method CPU test: terminal reward1 becomes-99, terminal target
drops exactly100, preceding tick target drops94.05 with gamma.99/lambda.95;
next episode and reset column unchanged. Critic gradient points toward lower
value. Test script test_getup_failure_cost.py; receipt getup-failure-cost-critic-test.json.
No critic architecture/LR/normalization modifications. Replay metadata and
reward validation include the terminal subtraction. Guarded resume helper:
resume_getup_failure_cost.py; latest verified checkpoint retained locally/S3.
References checked: Gymnasium handling_time_limits (terminal targets retain
reward, no bootstrap), OpenAI Spinning Up PPOBuffer.finish_path (terminal reward
included in returns; critic fits targets). Sources:
https://gymnasium.farama.org/tutorials/gymnasium_basics/handling_time_limits/
https://spinningup.openai.com/en/latest/_modules/spinup/algos/tf1/ppo/ppo.html
Magnitude100 is user-approved tuning, not a literature-guaranteed optimum.

## October 20 - noisy get-up graph now shows failures

User requested replacing head-reset percentage with termination percentage.
Two cards: Locomotion failure percent and Get-up failure percent, perturbed
recorded evaluation rows only. Get-up numerator is terminal flag1; head-height
and timeout resets are not failures. Historical caches derive failure percentage
as100-head_reset-timeout from known outcomes. Removed139 obsolete head-reset
summary values (recoverable retired-head-reset-events). Local dashboard/TB
restarted only; GPU training uninterrupted. Publisher16504, TB supervisor17856.
No averaging or extra cards.

## October 20, 06:01 Warsaw - low-head termination

User clarified termination only, no added reward penalty. Resumed latest
64158_final (1,051,181,056 samples) as 20261020_060120_uefn_getup_low_head_linear_512
on existing L4 ka68jrougesuit, until stopped. From policy tick60 onward,
perturbed get-ups fail (flag1, reason1) if head world Z <= 50% of assigned
idle-frame0 head Z. Existing90% head bootstrap reset and180-tick timeout remain.
Normal rows unchanged. Reward remains1-10*positionMSE with no failure subtraction.
Actual done-method checks passed: tick59/60, equality, normal rows,90% reset.
Latest checkpoint verified locally and by persistent S3 readback; receipts
getup-low-head-*.json. Guarded handoff: resume_getup_low_head.py. Two-card raw
outcome history preserved; head-reset percentage counts failures in denominator.
Optimizers, normalizer, physics, other losses and sampling unchanged.

## October 20 — final requested two-card outcome view

User clarified get-ups must show HEAD-HEIGHT RESET percentage, not failure
termination. Final visible tags are perturbed_termination/Locomotion failure
percent and perturbed_termination/Get-up head reset percent. Two raw unsmoothed
curves, perturbed evaluation rows only, previous/current history sample-sorted.
Removed all seven perturbed_eval_sample cards and the obsolete Get-up failure
card from dashboard event files (11 files,574 summary values); original affected
files are recoverably archived under Saved/MimicKitEquipment/retired-outcome-card-events.
Unrelated summary values verified identical. Raw trainer event files untouched.

Historical diagnostic values now live outside TensorBoard in
Saved/MimicKit/PerturbedOutcomeCache; dashboard stores new replay outcomes there
and publishes only the two requested cards. Do not rerun the old
backfill_perturbed_outcomes.py event-writing path, which would reintroduce old
cards; backfill the private cache instead. Local publisher PID29720; local TB
supervisor PID7132. GPU training never stopped. TensorBoard briefly restarted to
clear obsolete tag caches, then browser reloaded/verified. Both curves retain
65+ points; get-up head reset is no longer flat0. Evidence
outcome-cards-final-verification.json and retired-outcome-cards.json. First filter
attempt encountered Windows path-length limit before replacing any event file;
retry used a short staging path and completed. Existing latest10 run cap retained.

## October 20 — simplified termination view; no smoothing

User rejected averaging and overlapping/multiple outcome graphs. Active
TensorBoard tab now filters only `perturbed_termination/`: exactly two raw
curves, Locomotion failure percent and Get-up failure percent, perturbed rows
only. One trace each combines the explicitly selected previous/current run
history, sorted by sample counter with no duplicates (65 points verified at
setup). Published in current dashboard run as derived continuation history;
its historical section precedes that run's launch. No averaging or smoothing.
All failures counted separately from bootstrap resets. Get-up failures are0%
because current perturbed get-up rules only reset on head height or timeout;
that flat line does NOT mean every get-up succeeded. Earlier success/reset
metrics remain available in raw tags but hidden in this focused view.
Local dashboard publisher PID4848; training and GPU untouched. Captured
perturbed-termination-clean-view.png and verified exactly two tags via HTTP.
Current manifest's perturbed_termination_history_sources defines the two source
runs; raw sampled evaluation limitations still apply. Other UI groups collapsed.

## October 20 — historical perturbed outcome graphs recovered

Backfilled52 captures for previous run20261020_005208, plus the missing first
capture of current20261020_044014. Read only replay metadata from61 existing
remote checkpoint archives; one duplicate capture removed. No model download,
GPU simulation, training interruption or new allocation. Also restored the
single surviving local replay endpoint for each of seven October19 perturbed
runs (150048,151703,153401,161437,170826,182229,184549). Each point retains its
original sample counter, capture time and TensorBoard run. No interpolated or
invented points; these remain selected noiseless evaluation-row outcomes.
Kept existing TensorBoard run cap. Current publisher owns new captures;
backfill only adds missing older samples. HTTP confirms52 previous-run points
and no duplicate sample steps. Sources and receipts: perturbed-outcomes-
historical-{remote,local}.json, perturbed-outcomes-backfill.json and
perturbed-outcomes-backfill-http.json under Saved/MimicKitEquipment.

## October 20 — perturbed outcome graphs added without interrupting training

Local dashboard now derives `perturbed_eval_sample/*` from existing archived
noiseless replayer captures, backfilled for the current run and updated as new
captures arrive. No trainer restart, GPU simulation, remote logging changes or
additional download. Only local dashboard publisher restarted (PID2144).
Each captured episode counts once, regardless of duration. Flag1=failure;
flag3=reset, never a failure. Separate locomotion_no_failure_percent and
all_no_failure_percent; getup_head_reset_percent uses final reason2 and
getup_timeout_percent uses reason3. Sample counts are published beside rates.
Incomplete, nonperturbed and unknown-terminal rows excluded; missing get-up
reset reasons do not become successes. These are SELECTED EVALUATION ROWS,
not full-batch training statistics; rotating motion selection can change rates.
Get-ups/ordinary idle have no failure termination, so use the locomotion graph
for failure avoidance and head-reset graph for get-up achievement, not the
combined rate alone. Head-height reset does not prove stable standing.

Verified six historical capture points via TensorBoard HTTP. Latest sampled
capture63118: locomotion3/5 nonfailure(60%), get-ups4/5 head-height resets(80%)
and1/5 timeouts(20%); combined10/12 nonfailure(83.33%). Unit checks distinguish
failures/resets and exclude incomplete/normal/missing-reason records. Receipts
Saved/MimicKitEquipment/perturbed-outcomes-{dashboard,verification}.json.

## October 20, 04:40 Warsaw — idle-heavy blend continuation running

User requested idle/locomotion70/30, stronger punishment for perturbed get-ups,
and uniform0–100% interpolation from the known get-up pose toward a sampled
locomotion pose, matching the earlier local-DOF experiment. Prepared config:
358 idle rows (340 get-ups,18 ordinary idle),154 locomotion; normal/perturbed
allocation rule stays30/70 and walk/run stays50/50. Perturbed get-ups remain
frame0, pelvis/root and initial velocities unchanged. A single alpha~U[0,1] is
sampled per episode and shared across its child DOFs. No floor IK, root shifting,
PHAT edits or motor changes added; stronger blends can still intersect the floor.

Perturbed get-up reward now1 -10*raw body-position MSE, replacing1/(1+MSE).
Target remains assigned idleframe0, follows pelvisXY, standingworldZ andheading.
Only this cohort changes reward; position loss recorded is weightedMSE x10;
all other terms remain0 includingAE. Example rawMSE .22 now reward-1.2 versus
previous .8197; matching target gives1. Linear reward has no large-error
saturation. 90% head-height bootstrap reset and180-tick timeout unchanged;
no termination penalty. Both optimizers, LR, normalizer and counters preserved.

Isolated512-world validation from checkpoint62415: sampledalpha .00121–.98928,
mean .4829; interpolation matches the known-pose DOF cache exactly.32 simulation
ticks independently verify target/loss/reward, other rewards unchanged, get-up
nonposition terms0 and head reset flag3. One PPO update accepted40/rejected0,
KL .0307, finite weights. No diagnostic optimizer updates enter resumed model.
Replayer supports per-row linear reward and validates recorded rewards; four
historical captures converted with synthetic new reward successfully.
Evidence Saved/MimicKitEquipment/getup-blend-validation.json.

Resumed run **20261020_044014_uefn_getup_blend_linear_512** on existing L4
ka68jrougesuit ($0.59/hour), until user stops it. Latest checkpoint62517_final
at1,024,294,912 samples preserved locally and persistent-S3-readback verified,
SHA4fe9cb1fac809e3dff7a68075c5062c708cc48291dabec8ed857d4e9121bd2c0.
Both Adam states and normalizer restored. Verified live1,024,475,136 samples,
iteration62528, recent throughput~5.95k transitions/s during startup. First
live updates accept40/reject0. First new checkpoint62518 persistent verified,
SHA01979394cf2e863a361b8aa501940f01788aac625f577448525dd69b2b7cfa5e.
TensorBoard has the new dated run; replayer has20 rows. Its four perturbed
get-up records have blends .5913/.9128/.5274/.0388, weight10, linear reward
matching recorded terms exactly, all other terms0. Journal and paused old
curriculum plan updated to prevent a stale relaunch. Exit/backup guards active.
Receipts: getup-blend-{launch,launch-verification,preserved-checkpoint,
replay-verification}.json under Saved/MimicKitEquipment.

## October 20 — perturbed get-up failure investigated; live settings unchanged

Read-only history audit:185 recorded perturbed get-ups,0 above90% idle head height;
170 normal recovery recordings all reached it. First/last five captures: perturbed
mean position loss .2480 -> .2217 while mean peak head .340 -> .261m. Reciprocal
reward rose .8016 -> .8186 despite remaining down. Independent target/MSE/reward
recomputation matched within1.2e-7. AE/other loss terms remain0 for this cohort.

Isolated frozen-policy probes on verified checkpoint62015 (1,016,070,144samples),
128 worlds, two reset seeds9211/9212,50 perturbed starts (27front/23back):
full random locomotion local pose0/50 head-height resets; training sigma.05 also
0/50; authored clock instead of feedback0/50. Restore original local get-up pose,
keeping perturbed objective/phase/reset/motors:50/50 (original poses are repeated
controls, not50 distinct authored animations). Interpolate local DOFs from authored
pose toward each sampled locomotion pose:10% gives50/50,25% gives13/50 (front13/27,
back0/23),50% gives0/50,100% gives0/50. This is immediate recoverability, NOT proof
that a future curriculum will learn the full distribution. Production unmodified.

Reset validity issue: random local pose overwrites the floor-cleaned get-up DOFs
without a floor check. Four captured perturbed starts had collider bottoms17–45cm
underground; raw body origins alone reached8–33cm belowfloor. Native collider/FK
pool check over2334 locomotion frames per start side also shows pervasive additional
penetration. Keep pelvis fixed in any future remedy. Smaller perturbations improve
both pose familiarity and penetration; the two causes were not isolated, so do not
claim penetration alone explains all failures or that pose repair guarantees learning.

Optimizer is active: all logged actor updates accept40 minibatches, reject0;
effective LR5.625e-7 and KL .0046–.0169. Current perturbed physical inputs clipped
at most2.13e-5 of measured values in probes; transient extremes remain, unlike the
old persistent height clipping. Frozen PPO rollout probe confirms nonzero get-up
advantages/gradients; no loss disconnect. No torque insufficiency established by
these probes. Original pose and10% perturbations succeed with unchanged motors.

Primary next proposal: gradual, floor-valid local-pose perturbations from known
recoverable starts, preserving pelvis. Reward scale is also weak: typical failed
floor pose receives~.81 of maximum1; plain MSE is a PPO score, not a direct joint
gradient. Change neither objective nor initialization without user direction.
Evidence Saved/MimicKitEquipment/getup-idle-audit-20261020/{history,probe,followup,
summary}.json and getup-idle-current-contact-audit.json. Isolated successful probes
took177.5s+78.8s; an earlier follow-up stopped on a prefixed collider-name mismatch,
then was corrected. No diagnostic optimizer steps, extra pod or persistent model
copies. Main run continued and returned to~6.5k transitions/s.

## October 20 — clarify unused AE diagnostic in replayer

Checked deployed perturbed_omni.py hash against local source and live recorded
get-up rows: objective idle_frame0_body_positions; motion_prior loss is exactly0
on every recorded tick. AE still evaluates these rows in its shared batch and
records frame_ae_raw (observed peaks1.12–1.32), but tracking mix1 multiplies its
reward contribution by0. Raw diagnostic must not be described as an active loss.
Viewer now explicitly displays `AE disabled` for position-only get-ups; other
perturbed rows label the diagnostic `AE raw (unweighted)`. Asset version6-ae-status
served at8021; checked formatter against four actual get-up rows. Reload page to
replace already loaded JS. No training/physics changes or restart.

## October 20 — internet-gap data recovered

Current perturbed run continues uninterrupted on ka68jrougesuit. Recovered13
missing replay captures60415 through61615 from existing remote checkpoint ZIP
members,20 rows each, preserving original capture times and the bridge's latest
pointer. No model weights downloaded; temporary NPZ files removed. Local history
has no missing saved captures through61815. Live bridge remains active.
TensorBoard caught up automatically: all434 checked episode/train_seconds,
episode/test_seconds and loss/total points match raw events through1,013,284,864
samples; scalar HTTP endpoint confirms them. Local raw event file1071531 bytes
SHA matches the full remote file at verification. No interpolated points.
Receipt Saved/MimicKitEquipment/live-gap-recovery-20261020.json.

## October 20, 00:55 Warsaw — perturbed training restored on replacement L4

Replacement Secure L4 **ka68jrougesuit**, $0.59/hour, is running
**20261020_005208_uefn_curriculum_perturbed_512** until the user stops it.
The allocation succeeded on the 00:49 scheduled retry. Old pod/disk retained.
Verified checkpoint57514 resumed at942,325,760 samples; both Adam states and
normalizer restored, physical normalization migration changed0 channels.
Live verification:943,161,344 samples, iteration57565, about6.6k transitions/s.
No fresh weights, counter reset, checkpoint rewind or new physics changes.

Restored prepared30% normal/70% perturbed and30% idle/70% locomotion setup.
512 worlds:146 get-ups (21 normal random starts,21 normal frame0,104 perturbed
frame0),8 ordinary idle,180 walk,178 run. Perturbed get-ups use body-position
MSE to idle frame0 and head-above90% bootstrap reset, as already prepared.
Configured native MJ and existing motor/optimizer settings remain unchanged.

First new checkpoint57515 is persistent-readback verified, SHA
31412e59844415d109f44c0fca79920ee44218234b621b22183175b38adf1f7a.
Original selected942.3M checkpoint remains preserved locally and in S3.
TensorBoard lists the new dated run; local replayer has20 rows at57515,
including11 perturbed rows. Canonical local/remote controls both until_stopped;
trainer exit/backup guards active. Setup-only600-second deadline superseded.
Evidence: curriculum-replacement-ready.json, getup-curriculum-launch.json,
getup-curriculum-launch-verification.json, and guard-control-sync.json under
Saved/MimicKitEquipment. Availability heartbeat is PAUSED after this verified launch; curriculum is
finished, do not start another replacement.

## October 19, 21:49 Warsaw — immediate perturbed switch awaiting replacement L4

User explicitly waived the rest of settling: switch NOW from latest, then run
perturbed indefinitely. During handoff, SSH was refused: old L4 f44oylb1xk3y5o
had stopped at21:42:40. **Cause confirmed:** local guard created during L4
migration read Saved/MimicKitEquipment/l4-migration/runtime_control.json,
which still had Unix1792438960.398735. Canonical and remote controls were
until_stopped, but this second local copy was not updated. Exact stop receipt:
l4-migration/local_guard_stopped.json, reason bounded trial deadline, confirmed
EXITED at1792438960.4226. Earlier claims that all guards shared the new deadline
were incorrect. Trainer telemetry still showed the year9999 deadline at exit.

Fix: extend_runtime.sync_guard_controls now atomically updates all existing
runtime_control.json copies for the SAME pod beneath the canonical state dir;
unrelated pod controls are preserved. Isolated test confirms canonical/migration
copies both update and other pod does not. Replacement provisioning uses only
canonical Saved/MimicKitEquipment for its local guard, with a600-second setup
deadline and remote guard, then until_stopped at launch. No physics changes.

Old host restart rejected: GPU reassigned. User explicitly approved replacement
L4 <=$0.59/hour. Default Secure, eight alternate Secure regions and Community
allocation requests returned no available instances; subsequent default retry
also rejected. No replacement allocated, no GPU billing. Old disk retained.
Current source is prepared; TRAINING IS NOT RUNNING. Do not claim switched yet.

Latest persistent checkpoint57514 safely recovered locally and SHA verified:
5e36f63f83e6e293d2a6573215a439080be2d264de51fec364ed8d6625cb86cd,
47,764,520 bytes. Path preserved-checkpoints/
20261019_202430_uefn_curriculum_mixed_512/checkpoint_0057514.zip.
Receipt getup-curriculum-preserved-checkpoint.json. This is the latest verified
save before the abrupt stop; uncheckpointed final minute was not recovered.
Perturbed source SHA2b01cb4aaf5733f4743fad957315b4d19d87b74f8a39f0253f6594508a9c5c25.

Plan stage **awaiting_l4**, pending/next perturbed. Existing half-hour heartbeat
advance-get-up-curriculum now retries authorized replacement using
replace_curriculum_pod.py; after success run getup_curriculum.py launch directly.
Do NOT run capture (old trainer inaccessible) or rewind to earlier checkpoint.
Helpers read replacement pod from plan and update dashboard pod identity.
Preserve pending allocation receipts and inspect before retry to avoid duplicate
GPUs. Report actual launch/failure; stay quiet on unchanged capacity. Pause the
heartbeat only after verified perturbed launch or user cancellation.

## October 19, 20:52 Warsaw — mixed stage passed; one-hour settling

Scheduled check advanced plan from mixed to **settle**, without restarting or
changing training. Same active run20261019_202430_uefn_curriculum_mixed_512.
Noiseless frame0 front46/back42 ticks both complete (terminal2), drawn/unarmed,
evaluation55914 at916,111,360 samples. Live training at916,930,560 samples,
about9.6k transitions/s. Evidence getup-curriculum-last-check.json and checks.jsonl.
Keep146 frame0/146 random get-up worlds and all other settings unchanged.
The extra hour ends about **21:52:48 Warsaw**, Unix1792439567.8127; plan's
settle_until_unix is authoritative. Keep half-hour heartbeat active. At/after
that time capture/verify the latest checkpoint, restore the prepared perturbed
configuration, verify launch/backup/observers, then pause the heartbeat and leave
training running until stopped. No snapshot rewind and no early switch now.

## October 19, 20:24 Warsaw — curriculum advanced to mixed get-up starts

The20:22 scheduled check passed the frame0 stage: noiseless front completed46
ticks and back42 ticks, both drawn/unarmed, terminal2. Evidence iteration54991,
900,988,928 samples in getup-curriculum-checks.jsonl. Previous19:52 check had
front failure24/back completion42 and correctly left training unchanged.

Saved the actual latest final55113 at **902,987,776 samples**, SHA
09597c9ee2b447f1f99dc7a0ab563bbfb84bf6c6616d6dd5f3c55be463039174,
verified local archive and persistent S3 readback. New active run
**20261019_202430_uefn_curriculum_mixed_512**, same owned L4 f44oylb1xk3y5o,
trainer3374/exit guard3375. Source diff against stage1 is ONLY
idle_recovery.random_start_fraction:0 -> .5. No perturbation, rewind, optimizer
reset or reward change. Expected292 get-up worlds split146 frame0/146 random.
Source SHA f8170ec0c432cf86a034a1bca9608b4e39fbdce6db93107e61e6eb1ee7375e9e.

Keep `advance-get-up-curriculum` active. Next check approximately20:52 Warsaw;
the fixed half-hour cadence now remains eligible across short checkpoint handoffs.
Do not skip directly to settling based on stage1's successful rollouts: require
both motions/equipment variants to complete from frame0 in the mixed-stage
checks first, then leave this setup another hour, then restore perturbed training.
Until-stopped authorization and all failure/backup guards remain unchanged.

Live mixed-stage verification confirms146 frame0/146 random get-up worlds,
15 ordinary idle/103 walk/102 run. Both Adam states and normalizer restored from
902,987,776 samples; counter advanced to903,331,840 at about9.4k transitions/s.
First new checkpoint55114 persistent readback verified, SHA
23f77ba63435d4ef58e0769cee4e9aacb45a3f84937357176ed086627fead10a.
20-row evaluation captured and new datetime run listed by TensorBoard.

## October 19, 19:22 Warsaw — staged return to get-up-heavy training

User superseded the 90-minute restoration with performance-gated stages. New
run **20261019_192214_uefn_curriculum_frame0_512**, same owned Secure L4
f44oylb1xk3y5o ($0.59/hour), resumes the CURRENT final53190 checkpoint at
**871,481,344 samples**. SHA
2ea58c9eb617e91ebdf29aae980e7c43e49950101d8257a3c593b94e2f06d855.
Local preserved-checkpoints/20261019_184549_uefn_getup_normal_512 and persistent
equipment/getup-curriculum copy verified before launch. No weight/counter reset
and no rewind. Saved normalization and both Adam states are retained.

**Training setup:** reuse mixed-position-leeway-source.zip from the earlier
get-up-heavy main run: idle/loco60/40, ordinary/recovery idle5/95,
walk/run50/50. 512 worlds allocate 292 get-ups, 15 ordinary idle, 205 locomotion.
No perturbed environment or AE in these stages. First stage sets recovery
random_start_fraction=0; second sets .5. Everything else in the original env,
agent and engine configs matches exactly. Dataset/assets and original recovery,
reward, motor/physics code compared byte-identical. Current wrappers retain
backup/replay fixes and allow explicit --resume-recovery-curriculum to remove
perturbed configuration while restoring all learned tensors. No normalization
reset or additional migration is applied in ordinary RecoveryOmniEnv.
Native configured MJ, reciprocal reward, head/hands65cm and feet35cm spheres,
pelvis velocity x2, authored targets, get-up phase feedback, no idle tail and no
termination penalty remain as in that older main run.

**Automatic progression:** heartbeat `advance-get-up-curriculum` every30 minutes;
plan Saved/MimicKitEquipment/getup-curriculum-switch.json is authoritative.
Use getup_curriculum.py check. It reads existing noiseless evaluation captures,
not aggregate train_seconds and not random-start completions. Require frame-0
front/back coverage in both equipment states. A failure tick does not count as
a survived tick. Frame0 -> mixed when every covered example survives25 ticks.
Mixed -> settle when every example completes its authored clip (terminal2).
Keep the mixed setup running one additional hour, then restore the latest
perturbed setup from getup-idle-position-source.zip: idle/loco30/70, normal/
perturbed30/70, perturbed get-ups at frame0 with random local locomotion pose,
idle-frame0 body-position-only loss and90% head-height bootstrapped reset.
Always capture and verify the LATEST checkpoint at each transition, never rewind.
Existing recorder prioritizes frame0 and random examples for both front/back
and equipment states; no extra evaluation workload is added by this monitor.

User explicitly authorizes ongoing training through these stages and the final
perturbed run **until stopped**. Prior21:42 deadline is superseded; live control
and both deadline guards now carry until_stopped=true (finite year9999 sentinel).
Failure/backup safeguards and a600-second handoff billing watchdog remain.
Do not allocate another pod. Pause heartbeat on superseding user request,
training failure/end, or after verified final perturbed launch; leave final
training running. Report stage changes/failures, stay quiet on unchanged checks.
Old `restore-perturbed-get-ups` schedule is PAUSED and its plan marked superseded.

Source SHA7a526e5216c960960992416d60a7c9df3ad561bb9fc7b00172927b4e4bae65f2,
persistent readback verified. Helpers getup_curriculum.py and
getup_curriculum_metrics.py; receipts getup-curriculum-*.json. Synthetic stage
gate checks cover missing motions, random starts, failure ticks and completion.

Live verification: recovery_setup confirms292 frame0/0 random,15 ordinary idle,
103 walk/102 run. Both optimizers and normalizer restored; samples advance from
871,481,344 to871,661,568, recent throughput9.9k transitions/s. Actor40 accepted/
0 rejected, saved effective LR5.63e-7 retained. First checkpoint53191 persistent
SHA25ca88bf6e96ef7c7529b94c0e476ec465151d21962e48ac4473947ef35502e7.
TB new datetime run and20-row replay published locally. Baseline frame0 front/
back, drawn/unarmed all fail at tick3 (2 survived); no advancement claimed.
First scheduled progression check approximately19:52 Warsaw; checks.jsonl keeps
the evidence and last-check.json gives the latest decision.

## October 19, 18:45 Warsaw — rewind and normal get-up rehearsal

Current run **20261019_184549_uefn_getup_normal_512**, owned L4
f44oylb1xk3y5o. User rejected the prior continuation as stale: this run rewinds
to its original checkpoint **52179_final, 854,917,120 samples**, SHA
e508a49aae43a61fb33e5e5d69ca711bba504d7799fd7a3709c453cccca0fa3e.
This is not fresh weights or a resume of the stale run's latest checkpoint.
The stale final52778 (864,731,136 samples) remains preserved locally and in S3.

Temporarily all **146 get-up worlds are normal**, with authored tracking:
73 frame-0 starts and 73 random-frame starts. Other cohorts are unchanged.
The new `perturbed_motion.getup_normal_only` flag changes only recovery rows.
CPU allocation validation confirmed this split and identical other-cohort masks.
Configured native MJ, physical normalization migration and existing KL guard remain.
At 855,670,784 samples, recent updates accepted 40 actor steps and rejected 0;
effective actor LR was 5.63e-7 after guard adaptation. Throughput about 9.7k
transitions/s. First checkpoint52180 persistent backup verified, SHA
0b97c4592510a539ff02183df34c0c493f51ceee02c21b205d39fa00be30ae15.
TB8035 lists the new datetime run; replayer8021 has its 20-row noiseless capture.

**Scheduled restoration at 20:16 Warsaw today:** heartbeat
`restore-perturbed-get-ups` follows
`Saved/MimicKitEquipment/getup-rehearsal-switch.json`. Resume from the latest
rehearsal checkpoint then, not the rewind checkpoint again. Restore the original
nominal 30/70 normal/perturbed allocation (42/104 among these get-up worlds),
perturbed frame-0 starts and the idle-frame-0 position-only objective below.
Use `Labs/MimicKitTraining/getup_rehearsal.py` prepare --phase mixed, stop,
capture, launch; capture verifies local SHA and persistent S3 readback first.
Respect superseding user instructions and require the expected active run.
Pause the heartbeat after completion, cancellation or training ending.
**Hard deadline remains 21:42:40 Warsaw, Unix1792438960.398735; no extension.**

## October19 18:22 Warsaw — idle-frame0 position get-ups and physical normalization

Current continuation **20261019_182229_uefn_getup_idlepos_512**, same Secure L4
f44oylb1xk3y5o, hard deadline21:42:40 Warsaw (1792438960.398735), unchanged.
User explicitly selected BODY POSITIONS ONLY for perturbed get-ups; ordinary
get-ups retain authored tracking. Latest old run final52179 at854,917,120samples
was downloaded locally and persistent S3 readback verified BEFORE resuming:
SHA e508a49aae43a61fb33e5e5d69ca711bba504d7799fd7a3709c453cccca0fa3e.
Local Saved/MimicKitEquipment/preserved-checkpoints/20261019_170826_uefn_perturbed_headadd_512/checkpoint_0052179_final.zip.

**Perturbed get-up objective:** from tick1, plain mean squared XYZ body-origin
position error over all15 bodies against the assigned D/S idle motion frame0.
Target follows live pelvis XY only; original standing Z and heading remain fixed.
Pelvis therefore contributes height only. Weight1 (not old position calibration
814.227, which remains unchanged on other rows). No position deadbands on these
rows. No AE, rotation, velocity, COM-band, extra pelvis velocity, auto-phase
supervision or head-height contribution. Reward remains1/(1+MSE). Existing
frame0 recovery pelvis/random local locomotion pose initialization, autoregressive
phase input,180-tick maximum, proportions and other cohorts remain unchanged.
Head ABOVE90% assigned idle-frame0 head height yields DoneFlags.TIME=3,
bootstrapping the observed final state; no failure, success terminal or penalty.
No new duration/budget was granted or inferred.

**Normalization migration physical_scales_v1:** keep saved means/command scales;
raise physical standard deviations to at least pelvisheight.25m, root/joint
orientation components.25, root linear velocity1m/s, root/DOF angular velocity
2rad/s, key-body positions.25m. +/-10 normalized safety clipping remains; this
widens the physical range, rather than removing all numerical safeguards.
136 channels changed in the actual resumed checkpoint. Actor/critic first-layer
columns multiply by new_std/old_std; their Adam first/second gradient moments divide
by ratio/ratio squared. Biases, other layers, optimizer counters and saved LR
initially retained. Normalizer second moments adjusted consistently; learned count
remains >100M, so statistics stay frozen. Migration is idempotent on subsequent
resumes and saved model/optimizer tensors contain it. Phase uses the shared actor
trunk; command channels146..153 unchanged. Previously UNCLIPPED affine responses
preserved within floating-point tolerance; previously clipped responses necessarily
change. This is distinct from the earlier soft-tail A/B, not a proven learning cure.

**Validation:** isolated128-world test on latest available verified checkpoint:
206 clipped perturbed-getup physical inputs before migration,0 afterward (largest
normalized absolute value5.661). Pelvis heights.20/.50m encode-2.7148/-1.5148,
instead of the same-10. Synthetic old-unclipped actor/critic hidden max errors
1.8e-7/7.6e-6; second migration changes0channels.64 physical ticks finite, position
loss and target exactly match independent recomputation; other get-up terms zero.
Forced head crossing returns3. Two consecutive accepted PPO updates after initial
KL rejections; final real deployment verified separately below.

**Actual live optimizer behavior:** migration initially triggered KL rejections.
Existing guard reduced actual actor LR2.25e-6 to1e-7 (its existing minimum),
not a manual LR override. At update52240 (855,916,544samples), last four logged
updates each accepted40 actor steps and rejected0. Throughput~8.9..10k transitions/s.
Do not report unchanged effective LR or claim long-term get-up success yet.
First new checkpoint52180 verified persistent SHA
9b935736c30a39a8518b5874a2c055861678380949c1d448163f2bcd6b2290f0.

**Replayer/TB:**20 noiseless rows published; both position and orientation of the
shown target now come from the actual reward target (orientation for display only
on position-only rows). Four recorded perturbed get-ups independently checked:
standing target Z constant, position MSE recomputation max error5.96e-8, all other
weighted terms zero, reward matches reciprocal. These captures timed out at180;
that is NOT evidence of success. UI honors row active_loss_terms and hides unused
AE/blend diagnostics on static-idle-position get-ups. Other rows keep full terms.
Global historical position scale814.227 remains in shared metadata; these get-up
rows explicitly override it with getup_position_mse_weight=1 and their objective.

Source Saved/MimicKitEquipment/getup-idle-position-source.zip, SHA
faf017745f17b7a7c3b97824603b1a2089b5f28203fda0a97c1bdd603d77a42a.
Runtime changes limited to perturbed_omni, resume, train, observe, observe_many;
configuration changes confined to perturbed_motion. Helper resume_getup_idle_position.py;
test verify_getup_idle_position.py. Evidence Saved/MimicKitEquipment/
getup-idle-position-{launch,preserved-checkpoint,preflight,replay-validation,live-validation}.json.
Unreal/PHAT/assets/ProjectJournal untouched.

## October19 — clipping A/B test completed; no live change

User asked to test whether observation clipping causes perturbed get-ups to stay down.
Isolated checkpoint51279 (840,171,520 samples), SHA
6b91dc9a08f9fc6bada0be13f0af43b2291d42705ec67f4822c3add0a2c4fc85,
was copied after matching the verified persistent receipt. Both arms restored the
same weights, Adam state and frozen normalization. Control hard-clipped normalized
observations at +/-10. Intervention kept the same means/std and values inside that
range, but gave values outside it a slope of0.1 instead of discarding their variation.
This changes actor, critic and phase-head inputs; it is not a retrained normalizer.

Two training seeds6411/6412,128 worlds,80 PPO updates each arm (327,680 transitions
per copy), actual restored actor LR2.25e-6. Reward, reset, physics and action noise
unchanged. Total probe881.6s on existing L4; no new GPU or deadline extension.
Training initial raw observations match byte-for-byte within each paired seed.
Post-training evaluations also match initial raw observations byte-for-byte across
all four copies: reset seeds9851/9852,50 perturbed starts (27front/23back) and22
ordinary get-up starts,12 of those frame0. Evaluation actions deterministic.
First ever pre-training evaluation had a different full-observation hash from later
resets; all reported final comparisons use matching hashes.

Results after80updates, seed6411 / seed6412:
- Hard clip: perturbed successes0/50 and0/50; mean peak head front0.18465/0.18955m,
  back0.43617/0.45026m.
- Compressed tail: perturbed successes0/50 and0/50; front0.18222/0.18280m,
  back0.36671/0.34664m.
- Ordinary get-ups22/22 succeeded in every copy, including12/12 frame0 starts.
- Before training the changed inputs already reduced back peak from~0.436m to
  ~0.353m. Seed6411 recovered slightly; seed6412 did not. Do not present this as
  proof that clipping is harmless: short learning budget and changed input
  distribution limit inference. It does reject this intervention as a demonstrated
  immediate fix. Clipping removes information, but causal responsibility for the
  get-up failure remains unproven. No normalization change recommended as a proven fix.

Evidence Saved/MimicKitEquipment/clipping-ab/result.json and cleanup.json;
script Labs/MimicKitTraining/test_getup_clipping_ab.py. Disposable48,529,661-byte
remote checkpoint removed after completion; original checkpoint untouched.
Probe and its replacement timeout guard stopped. Live run remained unchanged and
advancing: iteration51679,846,725,120samples; throughput temporarily~5.4k during
concurrent work versus~9.4k before, latest post-probe status~7.4k transitions/s
(still includes overlap). Main deadline unchanged21:42:40 Warsaw.

## October19 — deeper frozen-checkpoint get-up audit; live run unchanged

User asked to investigate why additive-reward perturbed get-ups remain down.
Two isolated probes on the existing L4 used verified checkpoint50979,
835,256,320 samples (SHA9082fe1cbe5aba28e3a0d91460efb30fc970fb6053b0b08a36d8dca714014403).
They did not update weights, write trainer state, alter live settings, stop the
trainer or extend billing. 128 probe worlds, same reset seed, 25 perturbed get-up
starts (11 front/14 back); four180-tick trials plus192 frozen on-policy ticks.
First probe74.2s; second observation probe23.5s; bounded240s/90s processes ended.
Disposable remote48MB checkpoint copy removed after collecting compact evidence.

**Confirmed observation clipping:** restored normalization is frozen after100M
samples and reflects upright motion. Normalizer clips normalized inputs at+-10.
Pelvis height mean0.878708/std0.030915 => EVERY height below0.569554m maps to-10.
Head Z relative to pelvis mean0.489887/std0.003723 => EVERY value below0.452661m
maps to-10. Pelvis orientation component6 lower unclipped bound0.913776, so most
non-upright orientations saturate that component too. These are input-information
losses for BOTH actor and critic, not an absent reward gradient. Other joint and
velocity inputs still distinguish some poses; policy is not wholly blind.
5.30% of perturbed get-up features clipped initially,4.88% after96ticks versus
0.61% of other rows; max raw normalized magnitude160. No normalization change made.

**Confirmed hidden time:** keeping physical state and feedback phase fixed and
changing elapsed time30->90 ticks yields EXACTLY identical raw actor/critic
observations and critic values, but height bonus changes0->mean0.225. No elapsed
time/cohort flag is supplied; feedback phase is not the authored clock. This
prevents the critic from representing those two reward regimes independently.

**Reset/reward interaction:** the authored front/back trajectories cross90% idle
head height at ticks29/28, respectively. Under perturbed rules those successful
fast trajectories reset BEFORE head reward begins at61. Actual trajectories do
not receive a success bonus; TIME bootstraps critic value, so this does NOT prove
every early success is disfavored (continuation estimate matters). It does prove
no head bonus is collected on such fast successful paths. Do not equate finite
recorded return with the bootstrapped PPO objective.

**Exploration:** deterministic mean peak head front/back0.173/0.412m; normal
sigma0.05 (physical per-axis command std0.314rad/s)0.176/0.451m; sigma0.2 gives
0.208/0.527m, highest individual0.608m. Holding sigma0.2 noise8ticks gives
0.208/0.433m. Zero successes in each25-start trial. Larger noise is not a verified
solution. Different stochastic paths alter later RNG/reset events; starting
seed/initial poses are matched, not entire trajectories.

**AE and PPO:** back-start late prior cost~0.27 and total reward~1.10 while head
~0.44m: a low resting pose already earns substantial reward. Clean authored get-up
AE costs are0.002..0.300 weighted, so AE does not categorically reject standing
or the authored get-up. PPO gradients are nonzero. One batch actor-trunk get-up
gradient norm9.83 vs20.45 for other rows, cosine-0.049 (little directional conflict
in that batch); get-up fraction19.53%. Across192 frozen stochastic ticks, late
head movement >2mm/tick occurs5.2% of samples. Mean normalized advantage on those
rising transitions-0.042 vs+0.063 on falling transitions. This is descriptive,
not causal proof that upward movement itself is penalized; values/AE/action/state
also differ. Live ordinary front frame0 get-up at replay51079 completed46ticks,
head1.403m: rules out a blanket inability of this rig/policy to get up, not all
possible physical obstacles from randomized child poses.

Evidence `Saved/MimicKitEquipment/head-learning-audit/{probe-result,
observation-audit,normalization-bounds}.json`; executable isolated scripts
`Labs/MimicKitTraining/audit_getup_learning.py` and `audit_getup_observations.py`.
Earlier proposed next change was a deliberate normalizer migration covering recovery
poses; the subsequent A/B above did not validate it as a fix. Such a migration would
need to preserve old affine responses where previously unclipped, with explicit
validation; previously clipped states cannot have both identical old responses
and restored information. Also resolve delayed-height-reward versus early-success
reset and hidden elapsed time. No objective/input/normalizer changes authorized
or applied by this investigation.

## October19 17:08 Warsaw — additive get-up height reward; two ordinary idle replays

User approved replacing the x20 squared head penalty with a separate additive
height reward. Current continuation `20261019_170826_uefn_perturbed_headadd_512`
uses same L4 f44oylb1xk3y5o, deadline21:42:40 Warsaw unchanged. Latest final50178
at822,132,736 samples was saved locally and S3 readback verified before resume,
SHA256 `b82bd66d58bceabe41210feaae9adf7f3fe4f0dddcc67f302ba31d82da89df7a`.
Weights, Adam state, normalizers, counters, physics, motor limits, motion data,
cohort proportions, phase behavior and all reset conditions remain unchanged.

Perturbed get-up reward now equals `1/(1+AE_cost) + clamp(headZ/idle_headZ,0,1)`
with the second term active ONLY after tick60. First active tick61; head origin
world Z in metres, assigned idle frame0 target. No squared head term remains
inside loss total or reciprocal denominator. Height reset at90% remains; the
height reward's mathematical upper bound1 is normally preempted by that reset.
Normal/other perturbed rows retain their existing rewards. No extra physics pass.
TB `reward/getup_head_height` averages over perturbed get-up transitions including
inactive first60 ticks; `reward/total` averages actual rewards over all worlds.
Per-frame replayer shows Head height reward and Total reward separately from
losses. Training loss totals exclude this positive reward by design.

Replay selection retains at most2 ordinary idle rows, preserves get-up coverage,
and replaces excess ordinary-idle slots with diverse perturbed locomotion worlds.
Still20 noiseless recordings; does not change training allocation or reset sampling.
CPU tests cover tick60/61 boundary, clipping, cohort mask, actual reward override
without loss mixing, unique selection and idle replacements. Live first update
50179 reached822,149,120 samples and checkpoint50179 S3 readback verified SHA256
`fd92f0d091f37e4c0758c9e82bc32ac76aa53e6c1f93be2b238116c53868da27`.
Live replay confirms20 rows, exactly2 ordinary idle examples, extra perturbed
locomotion, and no old head penalty column. All20 recorded reward sequences
match reciprocal tracking cost plus the independent head contribution within
1.2e-7. Head contribution is positive only for perturbed get-ups after60 ticks.
Receipt `Saved/MimicKitEquipment/head-height-additive-replay-validation.json`.
Live update50189 reached822,312,960 samples at8,964 transitions/s. Both new reward
charts are visible in local TensorBoard. Local replay converter was extended to
validate the additive reward form (it initially rejected the unfamiliar formula);
all20 rows converted and published successfully, bridge restarted with that fix.
This was a local display delay, not a training failure or interruption.

Current package `Saved/MimicKitEquipment/head-height-additive-source.zip`, SHA256
`d04cc15a4e0d78153f75c63f35c0a957ea777de0ea2d57da689ef56f6f13be3d`.
Only changed runtime entries: perturbed_motion, perturbed_omni, observe,
observe_many, train; only config changes are inside perturbed_motion. Local TB
mapping and stepper replayer loss overlay updated. Resume helper
`Labs/MimicKitTraining/resume_additive_head_reward.py`; receipts
`Saved/MimicKitEquipment/head-height-additive-*.json`. Older x20 package is historical.

## October19 17:02 Warsaw — head-loss investigation, no training changes

User reports perturbed get-ups remaining on ground. Read-only live/source/replay
audit confirms this behavior, not an omitted head term. In 13 archived evaluation
captures48633..49833, all displayed perturbed recoveries reached180 ticks without
the head-height reset; highest head origin was about0.35m versus idle target1.40m.
These are varying random initial poses, not matched-seed comparisons or exhaustive
training-world statistics. Latest four recorded rows ended at0.155..0.222m.

Recorded head loss agrees with20*max(idle_headZ-current_headZ,0)^2 to5.1e-6;
zero through tick60, active from61, correct world vertical and idle target.
Remote replay49933 actual reward matches1/(1+sum(weighted losses)) exactly.
Example tick60 reward0.4311 drops to0.03119 at61 as head cost29.742 activates.
No failure or success reset caused the stalled replays; all ended at time limit.

Confirmed objective sensitivity issue: on replay49833 back row0, holding AE
cost fixed and algebraically raising head10cm improves reward only0.00568 at
weight20, versus0.01179 at weight1. This is a reward-form counterfactual, NOT a
physically simulated improvement. Head loss27.25 and prior2.12 dominate its late
cost. Large loss inside reciprocal compresses improvements far from standing;
it does not mean raising head is intrinsically punished. First60 ticks offer no
head-height incentive. AE reconstructs three poses, with no authored get-up
progress target on these rows. Elapsed time/head-loss-active flag is absent from
actor AND critic inputs (phase is autoregressive, not an elapsed clock), so the
tick61 change is not explicitly observable; causal importance remains unmeasured.
No claim that motor strength, exploration or shared-policy interference is ruled out.

PPO continues updating: recent logs40 accepted actor minibatches/update, no
rejections in sampled log entries, KL about0.014..0.018 versus0.18 guard.
Actual restored optimizer LR2.25e-6 (prepared config says4.5e-6); do not confuse
the configuration default with checkpoint optimizer state. No LR change made.
Evidence Saved/MimicKitEquipment/head-loss-audit/latest-replay-summary.json.
Training and deadline remain unchanged. Recommendation is to give height a
separate reward contribution outside reciprocal AE cost rather than increasing
its coefficient inside the denominator; requires user choice before objective change.

## October19 16:16 Warsaw — perturbed get-up head loss multiplied by20

Current run is `20261019_161437_uefn_perturbed_headx20_512` on owned Secure L4
`f44oylb1xk3y5o` ($0.59/hour). User requested head loss x20. The ONLY package
change is `perturbed_motion.getup_head_height_weight: 1.0 -> 20.0`.
Squared head-height shortfall remains restricted to perturbed get-ups after
tick60 (first active tick61); existing90% head-height reset and all other
settings remain unchanged. Hard stop remains October19 21:42:40 Warsaw.

Resumed latest final48632 at796,803,072 samples, retaining weights, Adam,
normalizers and counters. Checkpoint SHA256
`9a1cbba377792ae77fea175c9c6022bb6fcf00a9228716df27e8162b3fe7c227`
is locally preserved and S3 readback verified. Receipt:
`Saved/MimicKitEquipment/head-height-x20-preserved-checkpoint.json`.
Current source is `Saved/MimicKitEquipment/head-height-x20-source.zip`, SHA256
`cc205aef3ebe70f4e7d40928364e74b51f924427afd54d6e1d7555fa6c027088`;
do not reuse the older weight1 package for subsequent continuations.
Handoff helper: `Labs/MimicKitTraining/raise_perturbed_head_weight.py`.
Launch receipt: `Saved/MimicKitEquipment/head-height-x20-launch.json`.

Verified advancing iteration48653 /797,147,136 samples at9,050 transitions/s.
Weighted head-height loss is live (3.575 in this batch). First continuation
checkpoint48633 is persistently readback verified, SHA256
`7619ec1f0017a9c6bd6d95926db30e5296675da43126ee391b4812c172ed3940`.
Local bridge and dated TensorBoard observers started for this continuation.
A40 remains stopped; L4 availability heartbeat remains paused.

## October19 15:37 Warsaw — L4 running; A40 confirmed stopped

User explicitly authorized booking L4 and then said DO NOT stop A40 until L4 is
running. Community allocation returned no instances despite advertised$0.44.
Secure L4 f44oylb1xk3y5o booked at$0.59/hour, isolated control state in
Saved/MimicKitEquipment/l4-migration. Boot/SSH/GPU and runtime cache restore passed.
First signed source request returned403; small verified source transferred viaSSH;
runtime and checkpoint read directly from persistent S3 successfully. Two brief
setup stops/restarts occurred; final SSH port changed to17271. A40 stayed training.
L4 trainer20261019_153401_uefn_perturbed_ae_L4_512 launched15:34:04 from latest
verified A40 checkpoint47507, SHA81236a5769ac09de9ad34b30931c4749aafb029e4840e0a9b3f4f70362014e4a.
Same corrected source/settings; hard deadline21:42:40 remains. Both local and
remote L4 guards updated to that deadline. Verify advancing L4 updates and first
readback-verified checkpoint BEFORE gracefully stopping A40 y2l8exly57bqu0.
Do not allocate another pod while this migration is active. Pause L4 heartbeat
after successful migration; its revised prompt is19 words.

L4 live update47528 reached778,715,136 samples at9,229 transitions/s versus
A40 ~6.4k. First checkpoint47508 readback verified SHA256
c4d5af0af5e0c3562dc7dff75ca2819aa3785221e3a52e7f5f1ea1200773bc5f;
manifest independently checked from PC. Only AFTER these confirmations, requested
A40 graceful stop. Main pod/control/active-run now point to L4; old identities
preserved under retained-pods/y2l8exly57bqu0/l4-migration-*.json. Local bridge and
dated TensorBoard for L4 started. L4 heartbeat PAUSED after success. Migration
receipts Saved/MimicKitEquipment/l4-migration/{migration-proof,promoted}.json.
The A40 continued independently during L4 preparation as explicitly requested;
its additional overlap updates will be preserved in its final checkpoint, not
merged into the L4 policy resumed from47507. Both use unchanged corrected settings.
A40 confirmed EXITED after its final47610 checkpoint was persistently verified,
SHAe4d827bd962a5dffead314eea1f2891dc2e6290bfd7425ae6d57130388ba4fa0.
Receipt l4-migration/a40-final-state.json. Only the L4 remains running for this task.

## October19 — explicit objective corrections and frame-zero perturbed getups

User rejected nominal-speed auto-phase supervision on autoregressive rows.
It is removed on ALL phase-feedback rows, including normal recovery rows:
rollout buffer records a phase-supervision mask, both actor-loss paths apply it,
and replay reports zero weighted phase loss/weight there. Remaining clock rows
retain the original batch denominator and weight. No output/input dimensions,
optimizer, physics, motor, or dataset changes. Phase feedback still operates.
Important limitation disclosed to user: phase outputs are not PPO actions, so
AE reward does not directly train the phase head; no new algorithm was added.

Audit found an unrequested flat-COM-band loss on perturbed rows. Removed it;
normal rows keep their original COM loss. User additionally requested motion
prior divided by10: coefficient69.42658260262293 ->6.942658260262293.
Every perturbed getup now starts from recovery frame0 (pelvis and local velocity
from that frame), retaining the requested random locomotion child-joint pose.
Normal getup start mix is unchanged. User approved head-height squared shortfall
with weight1: max(assigned idle frame0 headZ - actual headZ,0)^2, only on perturbed
getups strictly after tick60. Tick60 itself is zero. New loss/getup_head_height
chart and generic per-tick replayer term. Existing90% head-height reset remains.

Latest original run stopped gracefully for this correction: final47206,
773,439,488 samples; local and S3 readback verified SHA256
b0d594b796e770f150a2d14b845d6dec928ec3d01c1cf66c7da8cea589487274.
Saved/MimicKitEquipment/perturbed-correction-preserved-checkpoint.json records it.
Correction resumed15:17:10 Warsaw as20261019_151703_uefn_perturbed_ae_corrected_512
on same A40; deadline unchanged21:42:40 Warsaw. CPU gradient-mask and head
tick-boundary tests pass. GPU one discarded PPO update passed frame0/phase-mask/
COM-zero/AE-weight contracts, restoring773,439,488 samples with Adam and normalizers.
Source e58d426c81f3e7b0fb47a8e8b73a6b5f892026108082f431a2146de722edcf7c;
current package Saved/MimicKitEquipment/perturbed-correction-source.zip and
launch/validation receipts `perturbed-correction-*.json`. Earlier perturbation
preparation source is historical and must not replace this corrected package.
First live update47207 advanced773,455,872 samples; initial checkpoint0047207
passed persistent readback, SHA256c19b981a4861f6518e693e4db6edc0c27b66cd47b971259a8089aaf6b60969bc.
Aggregate auto_phase stays nonzero because clock-input normal locomotion/idle
rows remain supervised; feedback rows contribute exactly zero. Initial head
loss is zero because the first batch has not reached tick61.
Engine/agent YAML match original47039 exactly; only idle fraction/perturbation
configuration differs in environment YAML. New source changes scoped by package
comparison. No new spending window or second GPU authorized by this correction.

## October19 14:58 Warsaw — A40 launch explicitly authorized

User now accepts the slower A40 at $0.59/hour and requests L4 availability checks
every three minutes. Heartbeat `check-l4-availability` created with a 17-word prompt;
checks must leave A40 training uninterrupted, notify on availability, and stop when
training ends. Do not rent a second training GPU merely to check availability.
Original hard stop remains October19 21:42:40 Warsaw (1792438960.398735).
Latest checkpoint remains final47039, 770,703,360 samples, verified locally and S3.

A40 preflight passed 512 worlds/180 ticks/five discarded PPO updates. New workload
measured 5.8k–6.55k transitions/s; exact old-workload baseline 5.50k versus recorded
L4 ~9.5k. User explicitly accepts this difference; launcher flag
`--accept-slower-a40` skips the repeated old-workload speed gate. It does not change
training, physics, or checkpoint state. Direct persistent S3 works on CA-MTL-1
hosts; Swedish-host S3 timeout is not a general provider outage. No PC relay used.
Replacement owned pod y2l8exly57bqu0 booted with SSH/GPU healthy in ~29 seconds.
Production launched at 15:00:56 Warsaw: `20261019_150048_uefn_perturbed_ae_512`,
512 worlds, restored weights/Adam/normalizers/counters. First live update47040
advanced to770,719,744 samples. Preflight on this host measured6,661 transitions/s.
Local bridge/dashboard started; receipt Saved/MimicKitEquipment/perturbed-launch.json.
Independent local/remote deadline and trainer-exit guards remain installed.
Live update47060 reached771,047,424 samples at6,273 transitions/s (recent PPO
mean). First persistent checkpoint0047040 is readback-verified, SHA256
ee2f63467721ca8686ae189634b52dafce153ae900ba2f622a81c637d9e2749a;
S3 latest_verified.json independently retrieved locally. Remote evaluation and
20-row replay are present. Replayer API confirms the new run is running with one
local capture containing20 rows; TensorBoard8035 exposes the dated15-00-48 run.

## October19 14:37 Warsaw — prolonged setup stopped; no training launched

User questioned prolonged startup. Owned A40 h1cq7jhsxtsv4q confirmed EXITED
at Unix1792413435; no train.py or preflight process was running. No further
allocation/restart dispatched. Its retained disk now has the complete409880235-byte
verified-runtime archive and49157256-byte final47039 checkpoint (checkpoint remote
SHA verified). Local runtime cache and original local/S3 checkpoint remain safe.
The A40 full-PPO throughput comparison is STILL UNMEASURED; do not claim parity
or start production merely because CUDA boots.

Confirmed failures were distinct: unavailable/non-booting L4 allocations;
first A40 preflight omitted initial observations before PPO (fixed locally);
subsequent A40 hosts time out reading EU-RO S3 with BOTH urllib and actual boto3,
while the identical signed request works from the PC. Alternative resolved IPv4
also timed out; virtual-hosted S3 addressing was not usable. No provider-internal
cause/global outage has been proven. A temporary loopback SSH relay through the
PC passed a small S3 write/readback/delete test in4seconds, but was only a test:
it was closed after stopping the pod. Production must not silently depend on
the user's PC connection. The slow ~410MB SSH upload was a poor fallback for
paid setup and contributed most of the delay. Do not repeat it blindly.

Failed new allocations93oue2ikkiudr1, kskfq6e0140qqi and vunesen56iilua were
stopped/deleted after preserving diagnostics; none held new training checkpoints.
Original retained L4/checkpoints untouched. Original authorized hard deadline
remains21:42:40 Warsaw if work is resumed, not a fresh eight hours.

## October19 - A40 fallback validation after L4 capacity failures

14:10 Warsaw: L4 start requests on three retained hosts explicitly report no
free GPU; fresh L4 requests now report no instances available. The identical
container image started on A40 kskfq6e0140qqi at $0.59/h in29seconds, with SSH
and CUDA healthy. This isolates the practical blockage to L4 availability/startup;
the earlier accepted-but-never-started L4 allocations have no host events, so
their internal provider failure is not proven. No general Runpod outage claimed.
Evidence: Saved/MimicKitEquipment/startup-diagnosis.

User permits A40 production only if throughput is comparable. Its first
512-row physical validation passed180ticks, but the standalone PPO benchmark
omitted the initial observation reset. Fixed preflight to call _reset_envs()
before _train_iter(); no training checkpoint changed. Failure guard stopped
the A40 immediately. Retrying the same pod with a full-PPO speed gate of
8192transitions/s (2s/update versus recent L4 ~1.72s/update), including AE.
Original21:42:40 Warsaw deadline remains; no production launch claimed yet.
Updated prepared source SHA fbf44f57de160714efebfa2e629dd44a6c5cafcb344cbaf9e079232c687ba817.

### Earlier L4 startup attempts

13:55 Warsaw: no trainer launched. Original retained pod n5esp2rc3dvxc4
could not resume. Replacement93adwv87jcwf3z never exposed a container/SSH
after bounded45/180-second attempts; other seven selected regions reported
no L4 capacity. Replacementj6g4aultpym8qj on a different RO host also failed
to start within300seconds. Both had zero container uptime and no Docker ID,
were confirmed EXITED, then deleted because no files were ever uploaded to
either disk. Original n5 retained disk/checkpoint remains intact and EXITED.
At that point no GPU was left running and no GPU preflight/PPO success was claimed.

Source dd1f287d2dfd7e8cfe9fe2d824f2294a4700454a1ca5090616b364b21e5288e5
is persistently readback-verified under equipment/perturbed-motion in the
existing mimickit/pipeline_20261014 prefix; final47039 readback also passed.
Local launch helper `launch_perturbed.py`, status `perturbed-launch-status.json`,
cleanup `perturbed-empty-pods-cleanup.json` in Saved/MimicKitEquipment.
Original attempted8h window ends21:42:40 Warsaw October19; --continue-window
preserves it on another attempt. Setup has a separate ten-minute cutoff;
production extends only to the original hard deadline after GPU preflight.

User authorizes continuation from final47039 for eight hours on the existing
L4 rate ceiling, with 30% normal / 70% perturbed rows, each 30% idle / 70%
locomotion. Keep 50/50 walk/run and 5/95 ordinary/recovery idle ratios.
Perturbed locomotion and ordinary idle receive world-Z yaw in [-90,+90], keeping
local joint velocities and original world XY trunk-COM velocity. This needs
a uniform translation-velocity correction after yaw, not simply retaining
pelvis linear velocity. User explicitly selected eight initial grace ticks,
removal of old failure conditions for perturbed rows, and COM2 direction/speed
termination only for perturbed locomotion: strict speed below70% or above170%
of the mean target, or direction more than45degrees away, after eight ticks.
The user's latest correction explicitly selects70%, not30%, as the lower cutoff.
Normal rows retain prior behavior.
COM2 is mass-weighted pelvis/torso/head only, excluding all limbs.

Implemented `perturbed_motion.py` and opt-in `perturbed_omni.py`: velocity-preserving yaw, strict
COM2 gates, 80-tick AE / 60-tick linear transition helper, frozen portable
three-pose AE scorer with isolated reset history. Wired through `train.py` and
explicit `--resume-perturbed-motion` migration. CPU numerical checks pass COM2 preservation, local relative
velocity preservation, speed/direction boundaries, blend endpoints and exact
AE score parity/history resets. The AE is an RL reward input; no pathwise
simulator gradients are claimed. Bundle: Saved/MotionRegularizer-2x512.

`prepare_perturbed_com2.py` precomputed all50 loaded motion averages from the
exact stopped deployment. Saved/MimicKitEquipment/perturbed-preparation/
com2_targets.json records source and motion hashes, masses and world XY target
vectors. Trunk masses16.4535866/23.9462585/4.0400376kg;48 locomotion target speeds
range1.46290-5.04159m/s. Sampling uses full-clip midpoint quadrature at240Hz;
idle entries are computed but never used for speed termination.

Perturbed get-ups receive NO yaw. Preserve original pelvis pose and sample
child-joint positions from a uniform random frame across all48 locomotion clips.
Existing local velocities remain unchanged. AE-only tracking cost, maximum180
ticks, with a reset when head worldZ exceeds90% of assigned idle frame0 headZ.
Both head reset and horizon use TIME3 (bootstrap final state, no failure penalty),
not FAIL1 or SUCC2. Old failure checks are disabled for every perturbed row.
Normal get-ups retain the old mixed frame0/random-frame starts and sphere checks.

Perturbed phase input feeds back the previous prediction; for locomotion and
ordinary idle it also chooses the current MSE reference. AE weight remains full
through tick80, then blends linearly to full MSE at140. Get-ups stay AE-only.
Keep the old flat-COM band term on non-getup rows; normal losses are unchanged.
Supervised auto-phase remains a separate optimizer loss. Frozen AE coefficient
69.4265826 matches prior body tracking cost on3574 saved three-pose windows:
raw AE mean5.90005e-3, weighted body mean4.09621e-1. No weight/physics tuning.
Each reset clears AE history; scoring begins after three valid physical poses.
512-row allocation:154normal/358perturbed,154idle/358loco,108perturbed idle.

Latest checkpoint47039/770703360 restored in CPU smoke; phase feedback, AE history,
get-up zero tracking cost and TIME reset passed24 physical ticks. All50 COM2
targets are prepared; locomotion reference instantaneous speeds fall within
0.846-1.263 of their full-motion means. GPU validation checks all512 rows and
five discarded PPO updates before production reloads the untouched checkpoint.
Replay records per-tick AE cost/blend/reset reason and labels normal/perturbed;
old termination spheres are hidden on perturbed rows. No Unreal/PHAT changes.
Preparation/evidence: Saved/MimicKitEquipment/perturbed-preparation.

## October19 - stopped at user request; final checkpoint preserved

Owned L4 `n5esp2rc3dvxc4` gracefully saved its final evaluated checkpoint and
is confirmed **EXITED**; GPU billing stopped. Run
`20261019_101601_uefn_main_mixed_position_leeway_512` ended at update **47039**,
**770,703,360 samples**. No new training is authorized by this stop/backup task.

Final `checkpoint_0047039_final.zip` is verified in persistent S3 and downloaded
to `Exports/MimicKitEquipment/20261019_stopped_47039/`. SHA256:
`8313a3118a1553fe8df97ebbb008f15bfa43c28d9d1daefd8cc102706dbbe742`.
That directory also preserves the exact deployed source package, a manifest
and recovery notes for the requested Git backup. Optimizers, normalizers,
counters, RNG, final replay/evaluation/configs and TensorBoard events are in
the checkpoint; live simulator episode state is not. Retained pod disk remains
intact. Subsequent sections describe the now-stopped experiment and history.

## Current temporary workflow — configured native MJ is the default

October18 user instruction: all subsequent training uses **configured native
MJWarp** (`uefn_native_profile: native_runlr_soft_contact_20261018`) unless the
user explicitly changes it. Do not require the user to repeat this. Disable
custom bounded motors, custom Jolt contacts and floor-aware projection in
training configs; retain240Hz physics/30Hz policy and existing gains/torque
caps. Keep the custom solver available for an explicitly requested later
transfer/fine-tune experiment; do not silently mix solvers. Native limits are
still the documented spherical approximation, not exact Jolt parity.

## October19 — left-foot bounce diagnosis (read-only; training unchanged)

Follow-up clarification: user specifically asks passive rebound versus active
lifting AFTER collision. Earlier motor-off-from-frame11 test changed approach
and could not isolate that. Additional `--post-impact` forks preserve the
recorded collision approach and exact qpos/qvel at12.0/12.375/12.5/13/13.25.
At back-get-up12.5 (just after vertical velocity turns positive), normal foot
rises4.59cm over next0.1s; disable left-leg motors ONLY then:0.138cm; all motors
off:0.280cm. Removing just left-foot contact at12.375 prevents reversal despite
normal motors. Thus the upward kick is a motor-driven push against ground,
not a purely passive floor rebound or a free-space motor lift. By13.0 the kick
has already happened: normal rise3.70cm versus3.62cm with left leg disabled,
so subsequent airborne rise is mostly existing upward momentum. Front frame12
small hop also requires actuation/contact; separate later front frame17 impact
does rebound with motors off, so do not generalize to every collision.
Evidence `post-impact.json` and `post-impact-traces.json`; no training changes.

User noticed get-up left-foot bounce near frame12. Captured replay/checkpoint
43833 /718,176,256 samples from current mixed-allowance run. Downloaded only
that checkpoint for isolated CPU native-MuJoCo probes; no second cloud workload,
no live trainer/physics/config changes. Local directory
`Saved/MimicKitEquipment/left-foot-bounce`; helper `diagnose_left_foot_bounce.py`.
Checkpoint SHA `c5e6439f54e346ee81c41e6ac586f43b5cc8231bee90269d8a51255b5417749f`.

Reconstructed exact recorded world poses/velocities and policy inputs, including
recorded feedback phase. CPU phase predictions match within1.8e-7; body mapping
error below6e-7m. Independent one-tick native CPU predictions reproduce GPU
left-foot height within4.74e-7m across frames9-20 for front/back.

Forked recorded frame11 with identical recorded policy command sequence through
frame19,240Hz/30Hz unchanged. Back get-up foot-origin rebound from local minimum:
normal4.611cm; LEFT LEG motor gains/bias disabled0.420cm; all motors disabled
0.560cm; contact damping doubled at fixed stiffness3.070cm. Damping probe uses
solref(.00875,4) versus original(.0175,2), above2dt clamp. Therefore large rebound
is predominantly driven by left-leg actuation interacting with contact, not
simple passive restitution. Floor still contributes: normal sole penetration
about1.2cm during impact and peak foot normal force684N. Left knee commanded
about7.22rad/s near impact, with about123Nm while contact slows the joint;
foot leaves floor around frame13.25. This does NOT establish an unstable motor
implementation or justify changing gains: it is a diagnosed policy/contact
interaction. No tuning performed. Raw substep traces and variant reports saved.

## October19 — idle allowances plus 3cm locomotion allowance (current)

Latest correction: locomotion also gets leeway, **0.03m isotropic on every
body**. Idle/get-up keeps leg XY radius0.10m / Z half-height0.05m and all
other bodies radius0.05m. Use squared excess distance only, original averaging
and weights. Pelvis XY is still aligned away; only height contributes there.
Current gait -1 chooses idle allowance; gait0/1 chooses locomotion sphere.
Start again from preserved final43232 /708,329,472 samples, not either short
allowance experiment. All other settings remain unchanged, including motion
assets, configured native MJ, Adam moments/LR/KL, sampling and termination.

Scripted `spherical_position_mse` implements locomotion. CPU tests passed
axis and diagonal boundaries plus unchanged idle branch. Recorder metadata
includes `scope: idle`, `locomotion_radius_m: 0.03`, original idle allowances
and per-row idle membership. Audit recomputes the correct branch per row.
Helper `restart_mixed_position_leeway.py`; source SHA
`73618ec950279eb97dd4cc1c9c6835d07da86f69d57449f396c3c81cfd00fe62`
verified in persistent storage. Brief idle-only run saved/stopped at final43260;
new run deliberately loads the original final43232 instead (local and S3 SHA
reverified). Active run `20261019_101601_uefn_main_mixed_position_leeway_512`,
same owned L4 n5esp2rc3dvxc4, trainer3298/exit guard3299,
bridge30316/dashboard16300. Fresh4h hard deadline **14:16:05 Warsaw October19**
(1792412165.9907017),165s save reserve; both billing guards updated.
New-window GPU ceiling$2.36. Receipts `mixed-position-leeway-*` in
Saved/MimicKitEquipment. Source diff confirms only allowance code/config changed.
Live check: restored both Adam states/normalizer and original708,329,472 count.
First new checkpoint43233 persistently verified, SHA
`e6d12c5f76d9b20c982ad1447e50d71b4bd2e740e290be7931468471f58917ec`.
All20 replay rows independently recomputed from actual captured targets:
10 idle/get-up rows use the larger allowances (max discrepancy2.98e-7);
10 locomotion rows use the3cm sphere (max discrepancy2.24e-8).
Evidence `mixed-position-leeway-live-verification.txt`. Intermediate experiments'
final saves remain backed up, but neither contributes learned state to this run.

## October19 — idle-only position allowances (superseded during handoff)

Latest user correction rejects the all-row allowance run. Restart from the SAME
preserved final43232 /708,329,472-sample checkpoint (SHA
`efa5f216b18e2f0edadda0d0a9a102913ae67b39aae5aba31e523ae0b67ddaba`), not
its newer descendants. Apply the allowances below only to idle command rows
(gait -1), which includes normal idle and noisy-idle/get-up rows. Walk/run
(gait 0/1) retain the exact original raw position MSE. Axes, allowances,
weights, targets, optimizer, sampling and termination remain unchanged.

Prepared config adds `position_mse_leeway.scope: idle`. OmniWalkEnv supplies
the mask from the current motion's gait; recovery retains its idle motion
assignment while tracking the separate get-up target. CPU checks cover
reordered assignments and exact raw-MSE retention for locomotion. Recorder
metadata includes scope plus per-row idle membership; audit recomputes both
branches from recorded actual/target coordinates. Handoff helper
`restart_idle_position_leeway.py`. Persistent source SHA
`720a940c46508995ba94c63f0f5534ebd103bd94019b1f5f8f43f0a7545e5de9`.
This intermediate correction launched `20261019_101243_uefn_main_idle_position_leeway_512`
from the requested checkpoint, then was superseded by the 3cm locomotion
correction above. Its brief learned continuation is not the new starting point.

## October19 — position MSE allowances (all-row scope superseded)

User requested position leeway and resume from latest. Training coordinates are
world XY horizontal and Z vertical. Both thighs, shins and feet use distance
outside a cylinder: horizontal radius 0.10m, vertical half-height 0.05m.
Every other body, including pelvis, uses distance outside a 0.05m sphere.
Only excess distance is squared, so loss is zero within the allowance and
continuous at its boundary. Preserve mean over bodies / 3 components and all
existing weights; no recalibration. Pelvis XY anchoring remains unchanged.
Rotation, linear/angular velocity, COM, auto-phase, termination radii, sampling,
Adam/LR/KL guard and configured native MJ remain unchanged. Applies to all rows.

Implementation: scripted GPU helper `position_leeway_mse` in `absolute_walk.py`;
explicit `--resume-position-leeway` config migration in `train.py`. Recorder
receives actual adjusted per-tick losses and includes allowance/body metadata.
CPU numerical checks passed for vertical axis, horizontal radial allowance,
upper-body isotropy, boundary continuity, sign/XY-swap invariance and exact old
MSE with zero allowance. No new physics passes or CPU transfers in training.
Handoff helper `resume_position_leeway.py`; verified persistent source receipt
`Saved/MimicKitEquipment/position-leeway-source-verified.json` (SHA
`c88f629925d912d7bacfede280c6a78b696baa9470a2969d080f0210099fea13`).
Only absolute_walk.py, train.py and the new env-config allowance differ from
the prior source package; all other settings and motion assets match exactly.

Resumed latest final43232 / 708,329,472 samples, preserved locally under
`Saved/MimicKitEquipment/preserved-checkpoints/20261019_093131_uefn_main_front_foot_velocity_restored_512/`
and S3 volume aj7d2jzwuq key
`mimickit/pipeline_20261014/equipment/position-leeway/preserved_checkpoint_0043232_final.zip`.
SHA `efa5f216b18e2f0edadda0d0a9a102913ae67b39aae5aba31e523ae0b67ddaba`;
full persistent readback/local SHA and ZIP CRC verified. Both Adam states,
normalizers and counters restored; new physical episodes as usual.

Active run `20261019_095239_uefn_main_position_leeway_512`, owned L4
n5esp2rc3dvxc4, trainer2854/exit guard2855, bridge15928/dashboard19600.
Fresh4h hard deadline **13:52:43 Warsaw October19** (1792410763.2287066),
165s final-save reserve, maximum GPU cost $2.36. Both billing guards updated.
Training advanced to43243 /708,509,696 samples; last update1.689s (recent
startup-inclusive mean1.778s). First new checkpoint43233 persistently verified,
SHA `ccdd819aee4f0255f91714739b7f2811becdd6198aed9eee9ab2f5333d99a733`.
Independent recomputation of all20 recorded rollout position losses from actual
target/body world coordinates passed (maximum absolute discrepancy3.58e-7).
Evidence `position-leeway-live-verification.txt`; dated TensorBoard run visible.

## October19 — edited front get-up loaded; global velocity x2 reverted

User edited getUp_front_quick.fbx right-foot ending and then requested also
reverting the global x2 linear/angular velocity weights, resuming LATEST.
This supersedes the weighting section below; keep the higher actor LR and
KL allowance. Rebuilt front with the SAME deployed preparation scripts:
anchor projection/conditional foot lift, then fixed-pole hand and foot IK
for reset poses only. No abandoned arc cleanup or global pelvis shift.
Staging `Saved/MimicKitEquipment/front-foot-update-20261019` includes source,
conversion, target/reset banks and verification. Front remains47 frames/30Hz,
1.533s; first generalized pose exactly unchanged. Final right-foot orientation
differs19.7202degrees from the former target. Source FBX SHA
`4d64945bd11df40b7b8b8f6bbce44b519567c48832cee96ca12b2d08ac2fd7f1`.
Unchanged back rebuilt as a control: all three frame arrays exactly match the
deployed back banks; package retains their original bytes. All other motion,
physics, optimizer and curriculum files remain byte-identical. Original source
FBX is untouched and included in the verified persistent update package.

Linear weight restored6.598591780546371 ->3.2992958902731857; angular restored
0.5427070962620917 ->0.27135354813104584 for every row. Whole environment config
matches the pre-x2 config exactly. Existing get-up-only pelvis emphasis2x is
retained; this instruction reverted only the later global velocity doubling.

Latest final42633 /698,515,456 samples preserved locally at
`Saved/MimicKitEquipment/preserved-checkpoints/20261019_090626_uefn_main_velocity_mse_x2_512/checkpoint_0042633_final.zip`
and persistent volume aj7d2jzwuq key
`mimickit/pipeline_20261014/equipment/front-foot-velocity-restored/preserved_checkpoint_0042633_final.zip`.
48,151,554bytes; SHA `1f44979d464d918e12b7bd2fcff9faadd962db6c1387c6a3ba33ac1c986e5b8b`.
Local hash/ZIP CRC and persistent readback verified. Resume uses this latest
save, NOT the older pre-x2 policy; both Adam states and counters are retained.

Run `20261019_093131_uefn_main_front_foot_velocity_restored_512`, same owned L4
n5esp2rc3dvxc4, trainer2675/exit guard2676, bridge2812/dashboard28208.
Fresh4h hard stop **13:31:39 Warsaw October19**, Unix1792409499.3864002;
165s final-save reserve; both deadline guards updated. New-window ceiling$2.36.
Source SHA `5157ab4c1164a54032f07cec14264d0bb2d7691a38bb64a34e0ab9eca4f72500`,
persisted/readback-verified. Receipts `front-foot-velocity-restored-*`; helpers
`refresh_front_getup.py` and `resume_front_foot.py` in Labs/MimicKitTraining.

Live verification: advanced to iteration 42714 / 699,842,560 samples; recent
mean 1.722s per update (~9.52e3 transitions/s). Both Adam states restored;
actor LR 4.5e-6 retained. First new checkpoint 42634 verified in persistent
storage (SHA `0e180a3f23ed513647c6fe3a0122722f1410382f283494df1830372ca1ce52f0`).
Local replayer received all 20 rows at step 42634; TensorBoard exposes the new
09-31-31 dated run and individual loss charts. Deployed front target hash
matches the rebuilt target. No further restart needed.

## October19 — linear/angular velocity MSE doubled for every row (superseded)

User requested doubling both velocity MSE terms and resuming the latest save.
Shared calibrated weights changed: linear_velocity_mse3.2992958902731857 ->
6.598591780546371; angular_velocity_mse0.27135354813104584 ->0.5427070962620917.
Applies to all512 rows: walking, running, ordinary idle and both get-up start
cohorts. Recovery pelvis linear-velocity emphasis remains2x relative to other
bodies; its extra contribution automatically doubles with the base linear
weight. Position/rotation, flat COM band and auto-phase weights unchanged.
Reciprocal reward remains1/(1+total); no recalibration or renormalization.
Weighted loss graphs therefore have a new baseline and are not directly
comparable to the previous total without accounting for this weight change.

Prior run stopped gracefully; final41923 /686,882,816 samples preserved locally
at `Saved/MimicKitEquipment/preserved-checkpoints/20261019_082046_uefn_main_adam_lr45_512/checkpoint_0041923_final.zip`
and volume aj7d2jzwuq key
`mimickit/pipeline_20261014/equipment/velocity-mse-x2/preserved_checkpoint_0041923_final.zip`.
48,255,710bytes; SHA256
`5865adf193fc86b0055ab3d0af9b84efb1a83cab0c990f7c590b60f82f1875a5`.
Persistent readback, local hash and ZIP CRC verified. Earlier preserved saves
retained. Resumed weights, Adam moments/counters, normalizers and sample count;
no actor-LR override, so saved effective LR is retained. KL limit0.18 unchanged.

Run `20261019_090626_uefn_main_velocity_mse_x2_512`, same L4 n5esp2rc3dvxc4,
trainer2435/exit guard2436, bridge13468/dashboard30500. Fresh4h window ends
**13:06:31 Warsaw October19**, Unix1792407991.6500585;165s save/upload reserve.
Both deadline guards updated; new-window GPU ceiling$2.36. Source
SHA `a64b70c1cbf95dd0713ddda072f9196b9cea4a2ccfe9dd27a56b939041c30d20`
persisted/readback-verified. Package comparison finds only the two weight edits
and train.py's explicit resume compatibility option: --resume-velocity-mse-scale2
permits exactly that ratio for the two velocity weights; unrelated configuration
still must match. No physics, dataset, row mix, radii, noise or optimizer changes.
Receipts `velocity-mse-x2-{launch,preserved-checkpoint,source-verified,weights}.json`;
helper `Labs/MimicKitTraining/double_velocity_mse.py`.
Live verification: both Adam states restored, effective actor LR4.5e-6 retained,
counter advanced past687,063,040 samples. Last update1.692s; startup-inclusive
recent mean1.773s. First checkpoint41924 persisted/readback-verified, SHA
`a857ed59226e991ddd3fb2544f61c110bfb9fb4058e34cfe5ac77de08a61228a`.
Recomputed linear/angular errors from actual recorded world velocities across
all20 replay rows and checked weighted terms against new coefficients, including
recovery pelvis extras. Maximum discrepancy1.43e-6 (float32 reduction rounding).
Replay metadata carries the new weights; per-tick values are the actual weighted
training objective. Evidence `velocity-mse-x2-live.json`.

## October19 — actor LR tripled; wider KL allowance

User requested the same latest-checkpoint preservation/resume procedure, actor
LR x3, and a guard that does not throttle the intended larger updates. Previous
30 logged points accepted all40 steps at1.5e-6, no rejections/rollback; mean
KL0.01096, max0.01749. New actor LR4.5e-6; KL limit0.02->0.18. For fixed
Gaussian noise, KL scales quadratically with policy-mean displacement; this
allows roughly3x displacement with similar relative headroom, not a guarantee
of learning stability. Guard rollback, finite checks and automatic backoff on
first-step rejection/full rollback remain active. Critic LR1e-4 unchanged.

Preserved final checkpoint40560 /664,551,424 samples,47,966,949bytes, SHA
`c90e5bf25c6e43d87f7b172c67a94d4a611d4fe63f2f0b402c4d2150c242ebd6`.
Local: `Saved/MimicKitEquipment/preserved-checkpoints/20261019_080138_uefn_main_adam_lr15_512/checkpoint_0040560_final.zip`.
Persistent volume aj7d2jzwuq:
`mimickit/pipeline_20261014/equipment/adam-lr45-4p5e-6/preserved_checkpoint_0040560_final.zip`.
Readback hash and local hash/ZIP CRC verified; original archive and all earlier
explicitly preserved checkpoints retained. Adam moments/counters, learned
weights, normalizers and sample counter continue from this save.

Run `20261019_082046_uefn_main_adam_lr45_512`, same owned L4
n5esp2rc3dvxc4, trainer2242/exit guard2243; bridge6800/dashboard27396.
Fresh4h hard stop **12:20:51 Warsaw October19**, Unix1792405251.146087,
165s save/upload reserve, maximum$2.36 GPU charge for the new window.
Local/remote reloadable deadlines updated together. Package comparison confirms
ONLY actor LR and KL limit changed; runtime, physics, animations, rewards,
sampling, noise, termination and evaluation settings are identical.
Source SHA `4bf7fa582307c6805d2b1cee82cf1a19bafb93b1557ad92f769202d39c068c2b`,
persisted/readback-verified. Receipts `adam-lr45-{launch,preserved-checkpoint,source-verified}.json`;
helper `Labs/MimicKitTraining/raise_actor_lr45.py`.
Live check: first21 complete PPO updates each accepted all40 actor steps,
zero rejections/full rollbacks, LR remained4.5e-6. Reported KL0.0142–0.0371
(mean0.02644), so the old0.02 threshold would have constrained some updates;
the new0.18 threshold did not. Both Adam states restored, only actor LR
overridden; counters advanced to664,895,488 samples. Recent update mean1.768s
(~9,269 transitions/s), last1.705s. First new checkpoint40561 persisted and
readback-verified, SHA `a0e82205ea18f0244ffcdd839094fae86403309b6205838aba9b6225b6d5f5b7`.
No failure files. This verifies startup and lack of immediate guard throttling,
not future learning stability. `adam-lr45-live.json` contains compact evidence.

## October19 — latest checkpoint preserved; actor LR increased by20%

User authorized preserving the latest checkpoint and resuming for a fresh4h
at actor LR1.5e-6 (previous1.25e-6). Critic LR1e-4 and KL limit0.02 unchanged.
Prior run stopped gracefully at655,998,976 samples; final checkpoint40038 is
48,281,369bytes, SHA256
`c4da6def203cbba16d8edac70403f49dc71c2393860cf1792cf14044f619cef7`.
Preserved locally at
`Saved/MimicKitEquipment/preserved-checkpoints/20261019_071932_uefn_main_adam_velocity_512/checkpoint_0040038_final.zip`
and in volume aj7d2jzwuq at
`mimickit/pipeline_20261014/equipment/adam-lr-1p5e-6/preserved_checkpoint_0040038_final.zip`.
Both hashes verified; local archive CRC checked. Original run final and
latest_verified remain intact. Do not remove this explicitly preserved save.

Run `20261019_080138_uefn_main_adam_lr15_512`, same owned L4
n5esp2rc3dvxc4 ($0.59/h), trainer2021/exit guard2022. New hard stop
**12:01:43 Warsaw October19**, Unix1792404103.2930884, with165s reserved for
final evaluation/upload. Local and remote deadline controls updated together.
New four-hour GPU ceiling$2.36. Bridge22508/dashboard7376; existing20 replay
rows and datetime TensorBoard naming retained.

`--actor-lr` now applies after loading optimizer state as well as to the saved
equipment config. Thus both Adam moments, optimizer step counters, learned
weights, normalizers and global counters survive; only actor LR changes.
CPU check confirms exact moment/counter/weight preservation. Ordinary resumes
without an explicit LR flag still restore the checkpoint LR. No changes to
physics, rewards, noise, row proportions, termination radii or KL behavior.
Source persisted/readback-verified, SHA
`b43196c3fd49cb7c2adc8f65e175955d0b532f3fc5d1032a7a315294aee8e889`.
Receipts `adam-lr-{launch,preserved-checkpoint,source-verified}.json` and helper
`Labs/MimicKitTraining/raise_actor_lr.py` record the handoff.
Live resume receipt confirms actor and critic optimizer states restored and
only LR overridden1.25e-6->1.5e-6. New checkpoint40039 uploaded/readback-verified,
SHA `a55757ffe08d10e43af95af34e6824c4940fe551a3495fee11f436e08db23e78`.
Training advanced past656.3M at1.75s/update (~9,361 transitions/s); observed
updates accept40 actor steps with no rejection and LR remains1.5e-6.
TensorBoard HTTP API confirms new dated run and optimizer charts. Evidence
`adam-lr-{live,progress,observers}.json`; this startup check does not establish
long-term learning improvement.

## October19 — velocity reporting fixed; Adam with transactional KL guard

User authorized fixing the native velocity bug, switching to Adam with a KL
guard, and resuming the last saved good checkpoint before the collapse.
Selected38799 /635,699,200 samples; full archive is locally saved as
`Saved/MimicKitEquipment/pre-collapse-38799.zip`, CRC verified and model/optimizer
bytes matched to the independently audited pre-collapse copy. SHA
`0ef2174013df98c44dc7fb094c68ecea4fcb11d5ecb0866c333038f00baee716`.
Old run stopped gracefully with final40066 /656,457,728 samples persisted and
readback-verified, SHA
`e9dcf4049ad32670a5561fc2ba3a37b1591d010fcce36ab666d7282648a14b2b`.
We deliberately resume38799, not this later damaged policy.

NativeUefnEngine now reconstructs body COM linear/world angular velocities
using the existing child-frame BodyVelocity adapter, once at the end of each
policy tick inside the CUDA graph. Omni reset also refreshes reported body
velocities after assigning poses/joint velocities, including partial resets.
No solver iterations, contacts, torque/gains, qpos/qvel integration or physics
frequency changed. This correction is the native engine default from now on.

Actor and critic use the upstream `Adam` option (implemented as AdamW with
explicit weight_decay0, equivalent to Adam). Actor initial LR1.25e-6, critic
LR1e-4, critic cap10 retained; no extra actor gradient cap. Actor and critic
weights, normalizers, RNG and global counters come from38799; incompatible SGD
momentum is intentionally discarded and Adam starts with fresh moments. Later
Adam-to-Adam resumes restore those moments and any saved LR adjustment.

`kl_guard.py` measures analytic KL(old||proposed) across34 motor outputs,
averaged over states. Limit0.02 per rollout's actor update. Each proposed step
is checked on2048 sampled rollout states; rejected steps restore actor weights,
Adam moments and step counters exactly, then finish this batch's actor updates.
A final complete16384-state check catches probe misses and restores the whole
actor update if necessary. Critic updates are separate. A rejected first step
or full rollback halves actor LR down to1e-7; ordinary later-step stopping does
not reduce LR. Training continues, with accepted/rejected step counts, KL,
full-rollbacks and LR visible in TensorBoard `optimizer/` charts. Nonfinite
proposals print a warning and are undone; these do not kill the run. Guard
bounds mean motor-policy change on collected states, not every possible state
or auto-phase output. Watch accepted steps/LR for persistent under-updating.

CPU regression verifies successful updates, exact Adam-state rollback, empty
Adam-state rollback and a full-rollout check catching a probe miss. Real L4
512-world preflight checks initial/partial reset and stepped velocities against
CPU MuJoCo Jacobians. Post-step maximum linear error4.09e-6m/s, angular2.78e-5
rad/s. Reset FK approximations produce up to0.134mm position,1.96e-4m/s linear,
7.68e-4rad/s angular discrepancies; logged, not treated as production failures.
Noisy get-up cohort remains146 random +146 frame0,65cm head/hands and35cm feet.

Twelve discarded PPO updates validate guarded Adam. Starting LR1e-5 was too
large for this checkpoint; guard backoff selected1.25e-6. Accepted updates
continue at that LR; all parameters finite. Steady mean1.632s/update across
mixed accepted counts; full40-step updates about1.70s vs prior live1.728s.
This is a short speed/safety check, not proof of long-term learning stability.
Production reloads38799 again, discarding preflight learning.

Run `20261019_071932_uefn_main_adam_velocity_512` launched on existing owned
L4 n5esp2rc3dvxc4, trainer1786/exit guard1787. Original09:11:52 Warsaw hard stop
and09:09:07 save cutoff retained; no new GPU or extra budget. Bridge16480 and
dashboard9932. Source persisted/readback-verified, SHA
`57be32b78827c35d32461285587c777a0f8ac7aa56fa7b934c3badbecf3a598a`.
Receipts `adam-velocity-launch.json`, `adam-velocity-preflight.json`,
`adam-velocity-handoff-final.json` in Saved/MimicKitEquipment.
Live verification:38850 /636,534,784 samples,1.704s/update (~9,613 transitions/s),
CUDA graph active. TensorBoard HTTP API shows policy KL0.01174; recent updates
accept40 steps at1.25e-6. First checkpoint38800 persisted/readback-verified,
SHA `b2f9f1e30b2983c8105c9764b908a052f070cf32d3319d33784ccb0c23fb7181`;
independent S3 latest_verified and object size confirmed. Local replay has20
rows, frame0 and random-start cohorts; first front-frame0 capture reaches all46
ticks. Both8021 and8035 respond; all loss terms and new optimizer guard charts
are present. Saved compact live evidence in `adam-velocity-live.json`.

## October19 — mixed-start collapse investigation (historical; fixes above)

User reported the sharp regression near637M, including walk/run. Read-only
cloud inspection and local CPU diagnostics confirm a real policy change,
not just the episode-average mix. No production settings, physics, weights,
deadline or GPU allocation changed during this investigation.

**Sequence from per-update stdout, finer than TensorBoard's10-update logs:**
at636,682,240 samples critic loss0.123, actor loss-0.0388,
action-bound loss6.13e-6. At636,698,624 samples (local iteration1361), critic
is still0.105 and advantages have ordinary spread0.340, but actor loss rises
to0.342, mean PPO probability ratio falls to0.590,74.3% are outside the PPO
clip interval, and action-bound loss rises to0.0195. At the NEXT update,
636,715,008 samples, critic loss spikes to161 and advantage spread12.6.
Therefore the actor change precedes the critic failure; the critic spike must
not be described as the initiating cause. The first damaging minibatch and its
gradients were not saved, so PPO/bound/auto-phase contributions to the initial
step cannot be causally separated from these logs.

Actor uses SGD1e-4 with0.9 momentum,40 minibatch updates per rollout,
sigma0.05, no actor gradient cap or KL stop/rollback. PPO objective clipping
does not impose a hard limit on the policy change. Critic alone has cap10.
This is an exposed path for an excessive actor update to persist and damage
all motions sharing the actor. Do not silently change optimizer settings
based solely on this observation; an oversized-update safeguard should also
save diagnostic evidence, including optimizer/batch state, instead of killing
the paid run on a minor numerical tolerance.

**Paired checkpoint check:**38799 vs38899,3504 identical reconstructed
pre-collapse replay observations. Environment/agent/engine/command-bound
configs and all normalizer tensors are identical. Recomputed next-phase
outputs match recorded post-reset outputs within7.76e-4; initial reset frames
are excluded because their velocity conversion takes a different path.
Front-from-frame0 mean action change is3.32rad/s RMS across joints/states.
Walking/running commands also change on identical inputs. This spans100
updates, NOT an exact measurement of the one bad update. The front noiseless
episode goes from46ticks/full completion to14ticks/failure. Locomotion replay
clip selection rotates, so aggregate before/after durations are not paired
same-clip measurements.

**Separate confirmed native velocity bug — NOT FIXED in live training:**
NativeUefnEngine directly inherits NewtonEngine and omits the BodyVelocity
correction installed by custom UefnNewtonEngine. Newton's MJ conversion copies
ball-joint qvel in child axes, but its articulation FK rotates these using the
parent joint frame. Its body linear-velocity output also disagrees with the
COM convention consumed by the loss. AbsoluteWalkEnv then compares these
incorrect velocities with correctly constructed reference-body velocities.
This affects linear/angular tracking and the flat-COM term; it is not a change
to MuJoCo's integrated dynamics. Current live/local native engine and Newton
kernel hashes match exactly; kernel SHA
`1eb7aab6d194fdbd1513da748cd6d21fdf8a481d1abbceb987ad90d684328a72`.

Independent CPU MuJoCo Jacobians evaluated at recorded states establish this:
pose reconstruction error <=5.01e-6m; sampled pre-collapse front-from-frame0
body-velocity discrepancies2.08rad/s angular RMS and0.690m/s linear RMS.
Across20 rows, maximum row RMS3.37rad/s and1.32m/s. Correct child-frame/body
origin recursion agrees with MuJoCo within2.46e-6; quaternion finite-difference
check agrees within1.25e-4. No simulation step, GPU or extra live workload was
needed. Fix velocity conversion before interpreting further velocity-loss
tuning. It is an ongoing corrupted learning signal, not proof of the cause
of the abrupt actor jump. A production fix needs reset/step consistency and
a bounded performance check; do not add more contact solver iterations.

Evidence: `Saved/MimicKitEquipment/mixed-collapse-audit/` contains
`per-update.json`, `scalars.json`, `rows.json`, `paired-policy.json`,
`velocity-coordinates.json`, `reconstructed-observations.pt` and57.4MB
`models.zip` (38799/38899 model+optimizer/config/replay).
Reproducers: `Labs/MimicKitTraining/audit_mixed_policy.py` and
`audit_recorded_velocities.py`. Last live check39619 /649,134,080 samples,
~1.728s/update,9490 transitions/s; checkpoint39599 S3 readback-verified.
Original09:11:52 Warsaw stop remains. No optimizer or velocity fix deployed.

## October19 — half of get-up rows use random-frame starts

User requested resuming latest with half of get-ups starting at a random frame.
`idle_recovery.random_start_fraction: 0.5` assigns146 of292 get-up worlds to a
fixed random-start cohort, evenly distributed through the existing equipment
groups. Each reset samples a fresh uniform source frame for these worlds;
the other146 always start at frame0. Final source frame is excluded so at least
one authored interval remains. Front/back selection is unchanged. Reset pose,
velocity, target clock and initial phase correspond to the chosen source frame;
auto-phase feedback then proceeds as before. No idle tail is appended.
Ordinary idle15 and205 locomotion worlds (50/50 allocation,103 walk/102 run at
this restart) and all rewards,65/35cm recovery spheres,
completion fix, optimizer, configured MJ and09:11:52 Warsaw deadline unchanged.
Replay prioritizes both start cohorts for front/back and drawn/unarmed, within
the existing20-row capture. Per-row metadata includes start mode and time.
CPU production reset regression passes, including phase and partial resets.
Source `mixed-getup-starts-source.zip`, SHA
`bb47541dede77a9324531ab7ecaa654b8769ec6a4d647aa304868329e9f8023b`.
Graceful handoff saved and verified latest37498_final from the65cm run, SHA
`f2384372e7f06da1b88488e4650bec15628646651052cdfcfdea5d483b4de2f1`.
Resumed `20261019_055242_uefn_main_mixed_getup_starts_512` on the same L4;
trainer862/exit guard863, bridge18988/dashboard3256. Source is persisted and
readback-verified. Receipt `mixed-getup-starts-launch.json`; original billing
deadline retained. Restored614,383,616 samples with optimizer/normalizer;
advanced to37509 /614,563,840 samples, ~1.70s/update. Live setup reports exactly
146 random +146 frame0. First replay confirms both front/back and equipment
states for each start cohort: fixed rows start0s; random examples start0.433,
0.600,0.900,1.367s. First new checkpoint37499 readback-verified in persistent
storage. Evidence `mixed-getup-starts-live.json` and
`mixed-getup-starts-replay-verification.txt`. The explicit random_start_fraction
overrides the legacy start_at_frame_zero fallback; that fallback is retained
for old configurations.

## October19 — terminal fix,65cm head/hands, best saved checkpoint

User authorized fixing the diagnosed completion bug, get-up head/hand spheres
65cm (feet stay35cm), faithful per-row replayer spheres, and four hours from
the saved checkpoint with highest train_seconds. Selected36286 at594,526,208
samples, train_seconds1.57266159. Absolute scalar peak1.69828377 occurs at36296
between100-update checkpoints and was never saved. Persistent36286 archive
downloaded locally, ZIP CRC verified, evaluation identity checked; SHA
`a34ae9b6e99a7a785941120875072bbf8be70e3281c83fa8657b65f3b2448697`.
Receipt `best-train-seconds-checkpoint.json`; local `best-train-seconds.zip`.

Both recovery done paths now emit SUCC=2 on authored clip completion, TIME=3
only on time truncation, preserving failure precedence. This zeroes the PPO
continuation value without adding a reward or penalty. CPU production-method
regression passes, including ordinary TIME bootstrapping. Sphere tests confirm
head/hands fail beyond65cm, feet beyond35cm; ordinary rows stay27cm.
Recorder emits only enabled termination points, each with its actual radius.
Viewer reads the selected row's settings and never substitutes row0's rule for
missing metadata. Historic captures retain their original radii. Live browser
row switching confirmed ordinary idle27cm vs historical get-up30/35cm.

Source `getup-best-native-source.zip` persisted/readback-verified, SHA
`6ebbe225df6223014f69bdcd4ec039da9f36b4eebbfd452c7878ba9b7594ea5c`.
Old pod9jhktpikw2jr41 could not restart; retained disk preserved. Replacement
Secure L4 `n5esp2rc3dvxc4` at$0.59/h allocated within authorized4h/$2.36 ceiling.
Setup started05:11:52 Warsaw; hard stop09:11:52 October19,
Unix1792393912.192196. Local guard28360 and remote billing guard protect setup.
Native MJ, original optimizer settings, reciprocal reward, cohort allocation,
motion data and physics frequency unchanged. Paid preflight runs one discarded
PPO update; production restores selected checkpoint again. Production launched
`20261019_051422_uefn_main_getup65_best_512` and advanced to36347 /595,525,632
samples. Initial steady updates average1.626s (~10,078 transitions/s), native
GPU graph active. First new checkpoint36287 is persisted and readback-verified
on S3; independent latest_verified read confirms SHA
`6ffb8fae20fdcd1bdff86b6f8e4e1b425bc46341b723ed666b8561df47691265`.
All20 local replay rows checked: four get-up rows record65cm head/hands and
35cm feet; other16 record27cm. Browser row switching and rendered spheres
verified against those values. First back captures complete42 ticks. This is
launch validation, not evidence that long-term regression is fully resolved.
TensorBoard has new dated run `2026-10-19_05-14-22_UEFN_Main_getup65_best_512`,
with advancing episode/train_seconds and loss/total. Bridge21292/dashboard26400.
Receipts: `getup-best-launch.json`, `getup-best-live-verification.json`.
Training save cutoff09:09:07; billing hard stop09:11:52 Warsaw October19.

## October19 — repeated get-up regression audit (no training changes)

User reports repeated learning/loss around frame23. Inspected complete837M
TensorBoard scalars,87 local captured checkpoints (27986–36486, plus43186;
internet outage leaves gaps), and final persistent replay51086.508 recovery
rows across those87 captures include repeated identical starting conditions,
not508 independent random trials. Front reaches3–28 ticks (median24), no
completed46-tick clips in this recorded subset; back5–42 ticks (median20),
four complete rows all at checkpoint36286. Final replay: front24, back15.

Real policy regression confirmed: checkpoint28686 front24/back19 ticks;
28786 front3/back5. Sampled ordinary/locomotion rows simultaneously fall from
10s mean to1.376s (coverage may differ; aggregate is not a paired all-motion
benchmark). At36286 both equipment back starts complete42 ticks, then36386
both fail at19. Front remained around24–28. Aggregate episode/train_seconds
mixes all cohorts and is episode-weighted, not a get-up completion metric.

Optimizer evidence: at471.32M critic loss155.53 (vs0.057 two logged windows
earlier), advantage std11.76, PPO clip fraction0.727, coinciding with collapse.
Further critic spikes71.23 at627.79M,58.14 at736.90M,82.17 at819.31M precede
or coincide with major drops. Not all drops have such huge spikes. Actor has
40 SGD steps/update at1e-4 with0.9 momentum, fixed sigma0.05, no gradient cap
or KL-based step rejection; PPO clipping is an objective, not an enforced
limit on the parameter update. Auto-phase shares its trunk. Evidence supports
unstable policy/value updates; original PPO batches/gradients/KL were not saved,
so no claim to have isolated the initial cause of every collapse. Observation
normalizer mean/std exactly constant throughout; no ongoing normalization drift.

Definite finite-episode semantic defect: RecoveryOmniEnv._update_done marks
authored clip completion as TIME=3; vanilla DeepMimic marks motion end SUCC=2.
PPO zeroes continuation value for SUCC/FAIL but bootstraps TIME. CPU test of
actual production methods proves a hypothetical final reward0.2 with critic
next-value10 produces target10.1 instead of0.2. End-reset recovery episodes
have no continuation/idle tail. This is a real defect to fix before further
training, but its contribution to the recorded collapses is not yet isolated.
No production behavior modified in this investigation.

Final front frame23→24: left-hand error0.2286→0.3258m crosses0.30m;
right-foot0.1826→0.3119m remains below0.35m. Reward0.0767→0.0444;
reciprocal reward works and is not numerically zero. Always-frame0 starts and
early sphere resets limit practice beyond the failing stage. This does not
prove torque sufficiency for the full front motion. Phase error is small in
many failed captures; not a universal clock-wrap failure at frame23.

Recommended sequence: correct finite clip completion flag; then bounded
comparison from a preserved good checkpoint with measured policy-change guard
and critic diagnostics, before another long run. Do not blindly widen all
spheres, change physics/gains, or declare the sole cause proven. Pod remains
stopped; no cloud spend. Evidence: Saved/MimicKitEquipment/getup-loop-audit/
{scalars.json,rows.json,final-replay.npz,terminal-test.json}; CPU reproduction
Labs/MimicKitTraining/audit_recovery_terminal.py.

## October18 — get-up feet35cm continuation

**October19 final TensorBoard recovery:** user internet outage left local events
incomplete. Pod confirmed EXITED (03:52:25 Warsaw); no restart or GPU billing.
Recovered final events from persistent `exit_evidence_cc2c1300ff18.zip`, verified
archive SHA prefix and exact match of existing local event prefix. Event file
grew2,994,487 to4,518,045 bytes; republished14,024 missing chart points with
deduplication. TensorBoard8035 HTTP scalar API confirms final837,009,408 samples.
Final checkpoint51086_final persistent SHA
`f555ba00901daafa3d80d00dad7632235fe8057d28a8febc890019fbfb80ec60`.
Receipt `Saved/MimicKitEquipment/tb-outage-sync-20261019.json`.

**Deadline updated October18 at19:54 Warsaw:** user requested finish eight
hours from now. Same run continues uninterrupted; new hard stop is
**October19 03:54:39 Warsaw**, Unix1792374879.565009, superseding00:11 below.
Local/remote billing controls updated; live trainer confirmed iteration35366
with new training cutoff1792374714.565009 (165s final-save reserve).

User requested latest-checkpoint continuation for a fresh eight hours, changing
only get-up FOOT termination spheres to35cm. Head/hands remain30cm;
ordinary idle/locomotion retain27cm. Added `idle_recovery.target_radii_m`
per-body overrides, precomputed squared-radius tensor on device; the existing
batched comparison handles it without extra simulation passes. Replayer stores
and draws individual radii and labels feet separately.

CPU test executes production radius construction and termination:32cm
head/hands fail,32cm feet survive,36cm feet fail, clip end resets;
legacy uniform radii preserved. Package comparison confirms the radius override
is the only configuration change. Reciprocal reward, configured native MJ,
gains/caps, motions,512 rows, proportions and learned state unchanged.

Run `20261018_161058_uefn_main_getup_feet35_512` launched16:11 Warsaw
on owned L4 `9jhktpikw2jr41`, latest final27985 persistently readback-verified:
SHA `06f8ba16c5b7148b97829f3d660d937056174226fdf5c4190ae72438de239c11`.
Fresh eight-hour hard cutoff **October19 00:11:05 Warsaw**, Unix1792361465.9210265;
final-save reserve165s. GPU$0.59/h, eight-hour ceiling$4.72. Local/remote deadline
controls updated; local guard22404, remote guard214 and exit guard1315 confirmed.
Trainer1314. Receipt `Saved/MimicKitEquipment/feet35-launch.json`; source SHA
`f3a878df4379beaf7d80655fa98f9a93d546fcf9ced8e3627b20af6d4c82f73b`.
Verified advancing update28016 /459,030,528 samples at10,074 transitions/s.
First new checkpoint27986 uploaded with full readback verification; independent
S3 `latest_verified.json` matches SHA
`c3206363957c976cce5cd190a4f6dbfabb865f48d1556ac0ddd546d9f39fa008`.
All20 recorded replay rows checked: get-up feet35cm/head-hands30cm,
ordinary rows27cm; reciprocal reward confirmed. Dated TensorBoard run visible;
bridge8992/dashboard24384 active. Local replayer published step27986,20 rows;
converted per-point radii confirmed35/30/27cm as applicable.

## October18 — front get-up thigh-limit inspection (read-only)

Current configured native MJ uses80-degree spherical limits on both hips.
Updated front target peaks left78.239deg /right75.347deg, inside that active
limit over737 interpolated samples. The stricter original PHAT/Jolt shape is
violated by the LEFT target from0.5333–0.66875s (66/737 samples; twist peak
56.174deg vs55.490deg; coupled swing ellipse peak1.436 where boundary is1).
Right target stays within original PHAT. These are different admissibility
rules: PHAT violation is not a violation of the current spherical MJ limit.

Latest inspected noiseless replay26371 has three front rows. Left simulated
hip peaks74.88–76.05deg; RIGHT reaches88.83–89.42deg, crossing the80deg boundary
from approximately0.533s to0.733–0.767s. Reconstruction uses recorded world
quaternions, inverse pelvis orientation, XML local rest and the native PHAT
reference offset; recorded target angles independently match the source.
Replay is30Hz: no claim about unsaved240Hz intermediate states or measured
limit impulses. No training or PHAT changes. Evidence:
`Saved/MimicKitEquipment/front-thigh-limits-20261018.json`.

## October18 — reauthored get-up endings, same preparation

User requested replacing the two get-up motions with the latest source FBXs,
keeping the live trainer running during preparation and resuming its latest
checkpoint when ready. Prepared separately under
`Saved/MimicKitEquipment/recovery-update-20261018`; the old previews are intact.
The deployed six target/reset PKLs matched `recovery-preview` byte-for-byte
before preparation. Current rig/XML/limits and the three preparation scripts
also matched the live package. Reused `prepare_recovery_starts.py` anchor
projection/conditional foot lift, then `prepare_recovery_hand_ik.py` and
`prepare_recovery_foot_resets.py` for reset-only fixed-pole IK. No abandoned
cleaned/pinned/arc preview, global pelvis shift or new smoothing.

Front remains47 frames at30Hz (1.533s), back43 frames (1.4s). Starting generalized
coordinates differ by at most2.68e-7 /1.07e-6 from the old targets. Reset IK
checks preserve root transform, unaffected chains and end-effector orientation.
The existing preparation still does not enforce joint limits after reset IK;
this update does not claim to resolve that known limitation. Only authored
motion updates and their identical-method resets are being promoted.

Full package comparison keeps all physics, policy/reward configs, ordinary
idle and locomotion assets unchanged. New source SHA256
`4186034f6d5adff1e09d3b473c12dbebd3c4531bf3e928886a4bf34f0d8a26f4`.
Receipts: `updated-recovery-source.json`; preparation reports beside the new
motions. Handoff helper `resume_updated_recovery.py` stages first, then obtains
a final verified checkpoint, checks its persistent pointer and SHA readback,
and starts the continuation with unchanged19:24:34 Warsaw hard cutoff.
A separate five-minute handoff watchdog covers the gap between trainer exit
guards. No second GPU workload. Continuation launched12:53:22 Warsaw on the same L4, run
`20261018_125315_uefn_main_updated_getups_512`. Old trainer saved final21670,
355,057,664 samples; persistent pointer and full SHA readback verified
`04ab37e6f472db4c0cdc8c1c0ffcdc7a62d690ce77d38ab3340c9573a679116b`.
Restored policy/optimizers/normalizers/counters, first update21671 advancing.
Both deployed target hashes match the new prepared clips; the new trainer has
its normal exit guard, and the temporary handoff watchdog is cancelled.
First new checkpoint21671 is persistently readback-verified (SHA
`c2d59d5eb198fe6bf492d46feef282d13a299d29cdf3d4db3aad24de70ead27a`).
Verified update21691 /355,401,728 samples at9.16k transitions/s, no error
files; new dated TensorBoard and20-row replay21671 published.
Receipt `updated-recovery-launch.json`. Deadline and all training settings
unchanged. Local preparation was slow loading Python dependencies; paid
training continued throughout that stage.

## TensorBoard visibility — October18

User hid the last get-up penalty experiment from the latest-ten comparison.
Its dated directory `2026-10-18_10-30-31_UEFN_Getup_penalty_MJ_512` now lives
in `Saved/MimicKit/TensorBoardHidden`, outside the served run directory.
Logs and checkpoints retained; the earlier run fills the freed slot.

## October18 — main337 resume with approved critic stabilization

**LIVE, verified at 12:20 Warsaw:** run
`20261018_121738_uefn_main337_native_mj_512`, owned Secure L4
`9jhktpikw2jr41` at $0.59/hour. Resumed untouched checkpoint20613_final
(337,739,776 samples) with policy, optimizer momentum, normalizers and counters.
The only optimizer change is the user-approved stock critic gradient norm
cap10; actor remains uncapped and both learning rates stay1e-4. Five discarded
512-world PPO preflight updates passed (9.47s total), then production restored
the original checkpoint again. No assertion or diagnostic wrapper from the
preflight is installed in production. Latest observed update20664:
338,575,360 samples,1.782s/update,9,192 transitions/s; no failure/backup-error
files. This confirms startup stability, not learned get-up success.

First new checkpoint20614 is uploaded and SHA256 readback-verified:
`3ed2a640777d7aa3fff5eca9f7d132f891fa8ae8c553f22a827b87bdd9799e7f`.
Persistent run `latest_verified.json` independently read and matches. Source
package `ae69b79d9957b8af2635afe9713ae91d1e6a392ec43a395e4a4b2cd3dc0008e4`
is also persisted/verified. TensorBoard8035 has the dated new run and all loss
terms including `pelvis_velocity_extra`; replayer8021 has20 noiseless rows,
30cm spheres on recovery and27cm on ordinary rows. No penalty term.

**Hard cutoff stays19:24:34 Warsaw October18**, preserving the original8h
window; training/final-save reserve starts19:21:49. No fresh8h timer after
setup retries. Local/remote deadline and trainer-exit guards active. Prior
setup source upload timeout and storage user-agent403 were resolved by a
verified cloud-to-cloud source fetch using the existing runtime-cache request
headers; affected pod was stopped each time, retained disks preserved.
Receipts: `main337-launch.json`, `main337-preflight.json`,
`main337-source-verified.json`, `main337-start.json` under
`Saved/MimicKitEquipment`. Earlier uncapped critic failure evidence retained
as `uncapped512-main337-diagnostic.json` / `uncapped512-main337-preflight.log`.

The following paragraphs record preparation and the earlier failed preflights;
the live state above supersedes their pending/blocked status.

User approved eight hours on the existing L4 rate ceiling$0.59/hour ($4.72
maximum GPU cost), replacing the stopped get-up-only experiment. Exact rollback:
`20613_final`,337,739,776samples, from
`20261017_192404_uefn_equipment_solver_speed_512`. Local archive
`idle18-resume-latest.zip`, SHA256
`3b008cfdf37b7550cc6936c5f4513008b6028a7385edc9a7f9bcd3d2be8f3e5e`.
Restore policy, optimizers, normalizers and counters; reset physical episodes.
Do not substitute get-up-only checkpoints or the later383.6M main checkpoint.

512 fixed rows: idle/loco60/40 ->307idle/205locomotion. Within idle, ordinary/
noisy5/95 ->15ordinary/292recovery. Within locomotion, walk/run50/50 ->102walk/
103run. Equipment remains balanced by existing motion weights. Adaptive
sampling remains disabled. Get-up starts are frame0, front/back randomly
split equally in expectation; reset at authored clip end with NO idle tail.
Noisy idle has all five head/hand/foot spheres at30cm, other failure checks
disabled. Ordinary idle and locomotion retain their existing27cm sphere,
contact/pose checks and10s horizon. Target positions for ALL rows follow
pelvisXY only, preserving authored world height/heading/orientation and
world velocity targets. No pelvis-rotation alignment or local-joint loss.

Keep reciprocal reward `1/(1+total weighted tracking error)` from the recent
get-up run. Remove the failed termination-penalty experiment from production;
no penalty column, no subtraction on failure. Historical captures remain
readable. Double ONLY the pelvis linear-velocity MSE contribution on recovery
rows; retain the original all-body normalization and all other body/angular
weights. A separate `pelvis_velocity_extra` component exposes the added copy
in per-tick replay/TensorBoard and total. No extra physics solves/readbacks.
CPU tests verify actual allocation and isolated pelvis weighting; real L4
preflight checks restored337.74M state, mixed-cohort rewards and five
discarded PPO updates. Assets/motions remain byte-identical. Agent config
differs from the checkpoint ONLY by the approved critic gradient cap10.
Previous host rejected restart for unavailable GPU capacity; retained pod
`ennp2v39ymd04t` remains stopped. Replacement Secure L4 `6dxhk255i53o9f`
is allocated at$0.59/hour. Hard stop **19:24:34 Warsaw October18**;
final save reserve starts19:21:49. Local/remote guards installed before setup.
Source archive6,614,775bytes SHA18430f5256f0 is S3 readback-verified before
allocation; rollback checkpoint is also rechecked in persistent storage.
The replayer sphere display now reads the selected row's own radius, so it
shows30cm for recovery and27cm for ordinary rows. Launch remains pending. The64-world preflight passed24 physical ticks,
reward/radius/extra-loss checks, then produced nonfinite parameters in its
single PPO update. Guard stopped6dxhk255i53o9f immediately. Original checkpoint
and saved optimizer tensors are all finite. Diagnostic64-world result is
preserved in `main337-preflight-64world-failure.log`; no production policy was
saved from it. Next bounded preflight uses the actual512 worlds and identifies
the first failed optimization stage. Five updates, if finite, are discarded
before production restores the untouched337.74M checkpoint. Original19:24:34
hard deadline/budget retained. No gain or learning-rate changes. The later
approved critic cap is described below.
Host GPU availability changed after stop; subsequent replacement may use a
new owned pod recorded in `main337-start.json`.
Unreal, PHAT, user Blueprints and unrelated work remain untouched.


**Before the approved cap:** full512-world preflight also failed. Physical/reward checks
pass; during the FIRST PPO update, critic optimization diverges BEFORE any
actor update: recent critic loss1.7e3 ->3.3e4 ->1.5e6 ->1.2e19 ->nonfinite.
Normalized observation peak is10 (existing clipping), and original model/
optimizer checkpoint tensors are finite. This identifies critic instability;
it does not establish whether reward change, state distribution or both are
the underlying trigger. No production run or contaminated checkpoint saved.
Latest owned replacement `3x24h0qjtz49iz` is API-confirmed EXITED by guard.
Original337.74M archive remains intact, both locally and persistently. Evidence:
`main337-diagnostic.json`, `main337-preflight.log`,
`main337-setup-failed-stop.json`. Asked user to authorize a **critic-only gradient
cap10**, test it, then launch with actor/learning rates unchanged. User approved
this change ("ok"). Use the repository critic_optimizer.grad_clip=10 only;
restore optimizer momentum/counters and keep actor uncapped, both LR1e-4. Existing
19:24:34 Warsaw budget deadline remains; do not extend it silently.

## October 18 — get-up termination-penalty experiment stopped by user

User requested immediate stop at approximately10:52 Warsaw. Trainer stopped
cleanly at **645_final**, saved and S3-readback-verified. Its unsolicited local
download was removed at the user's request; the previously requested3839_final
local download remains. Persistent645_final SHA256:
`548da59857f4f410fdb941191ce40fb7baad3e5fd47d4c6fcccd726124fdc6bd`.
Owned pod `ennp2v39ymd04t` is API-confirmed **EXITED**; GPU billing stopped.
Final telemetry/replay/events recovered from the verified exit archive.
No restart authorized. Receipts: `getup-penalty-stop.json`,
`getup-penalty-billing-stopped.json`. Launch details below are historical.

User requested stopping the configured native MJ run, downloading its latest
checkpoint, then one final experiment from fresh weights/counters. Approved
penalty: subtract remaining animation ticks × maximum per-tick reward (1).
Approved budget: one hour on L4 at <=$0.59/hour.

Previous run stopped cleanly at `3839_final`; owned pod was API-confirmed
EXITED before restart. Latest save is locally checksum-verified at
`Saved/MimicKitEquipment/getup-native-stopped-latest.zip` (30,846,630 bytes),
SHA256 `4b075eeb7db321978662a6396c65642b84565f342a80ab6feeb865b7106a00f0`.
Persistent S3 readback matches. Receipt: `getup-native-stop.json`.
This checkpoint is preserved for study, NOT used to initialize the new run.

New opt-in `idle_recovery.termination_penalty_per_tick: 1.0` subtracts the
remaining-tick cost AFTER `1/(1+tracking_error)`, on FAIL only. Excludes the
current tick; clips remaining duration against the episode horizon. Normal
clip completion costs zero. Example: failure on tick10 of46 subtracts36.
No action/observation/network/optimizer/controller/physics/motion changes.
512 worlds, frame0 front/back starts, 30cm head/hand/foot spheres, pelvis-XY
relative targets, no idle tail; reset at clip completion. Fresh weights,
optimizers, normalizers and counters. Native configured MJ only, 240/30Hz.

Penalty is a separate `termination_remaining` component in per-tick replay
and TensorBoard. Displayed total includes weighted tracking, penalty and
supervised auto-phase; PPO reward uses reciprocal tracking minus penalty,
while auto-phase remains a separate supervised actor loss. `body_total`
excludes the termination penalty. Production accounting adds the penalty
once after done detection; no extra physical solves or CPU synchronization.
CPU tests pass remaining-tick arithmetic, endpoint rounding, normal-end and
nonrecovery exclusion, preserved tracking values and loss-accounting totals.
Source archive is S3 readback-verified; receipt `penalty-source-verified.json`.

Same retained L4 `ennp2v39ymd04t` restarted. Hard billing deadline
**11:27:28 Warsaw October18**; one hour includes setup/final-save time.
Local/remote billing guards and trainer-exit stop guard are installed. Final
save/evaluation reserve begins 11:24:43. Real L4 preflight passed 24 ticks
in32 worlds, including101 early failures and one finite discarded PPO update.
Production initialized fresh, not from that update or the preserved checkpoint.
Run `20261018_103031_uefn_getup_penalty_mj_512` is verified advancing:
update150 /2,473,984 samples; recent30-update mean1.9714s,8,311 transitions/s
(excludes periodic capture/save overhead). Initial replay and S3 backup are
verified; checkpoint0 SHA `3fb955eb6325f2acd1eec06695033958ba3d16819c8d895945a6d3023cf89f9c`
matches persistent latest_verified. Twenty noiseless replay rows at update100
are published; per-tick termination penalties and all eight displayed totals/
components are present. TensorBoard8035 exposes the dated run and
`loss/termination_remaining` alongside tracking/auto-phase/total.

The local replay converter initially rejected the new reward form. Added its
explicit reciprocal-minus-penalty verification and restarted only the owned
bridge (PID26752); GPU training was uninterrupted. Conversion validates all20
rows, including actual failure ticks costing36/37. Corrected observer source
is separately S3 readback-verified. Launch/live evidence:
`penalty-launch.json`, `penalty-preflight.json`, `penalty-live-verification.json`.
New source/runtime and latest old checkpoint were preserved before renting.

The preceding upper-body CPU diagnostic was interrupted by this new task.
In one back-get-up pose, raising left-wrist torque cap reduced alternating
joint velocity; this is not proof of general insufficient lifting strength
or a validated GPU fix. No gains/torque changes were applied. Evidence stays
in `Saved/MimicKitEquipment/upperbody-audit`; do not promote its counterfactual
settings into this experiment. Unreal, PHAT and source motions are untouched.

## October 18 — configured native MJ get-up continuation launched

Latest user instruction replaces mixed native/custom scheduling with **native
configured MJWarp only**, resuming the latest get-up checkpoint for two hours.
Run `20261018_084204_uefn_getup_native_mj_512`, owned L4 `ennp2v39ymd04t`,
$0.59/hour. Launched 08:42:09 Warsaw; hard billing stop **10:34:09 Warsaw**
October 18 (the two-hour allowance includes setup; final save reserves 165 s).
Local and remote deadline guards and trainer-exit stop guard are installed.
The old unavailable pod `v05mjf1bj17lwa` remains stopped with its disk retained.
One local timestamp error stopped the replacement during setup; corrected to
the Windows local timezone and restarted within the original deadline.

Resume source is verified `656_final`, 10,764,288 samples, next global update
657; optimizer and normalizers restored, physical episodes reset. SHA256:
`d4496271001dd5cfa443ee95ea01ee2305c9b5499ec47d8b762fe46d112dc105`.
512 worlds, original gains/torque envelope, 240 Hz physics / 30 Hz policy,
reciprocal reward, frame-0 front/back starts, pelvis-XY-relative targets,
30 cm termination spheres and reset at clip end without idle tail are retained.
The exact checkpoint task/agent configs, assets and motions were preserved.

Production adapter `native_uefn_engine.py` selects the native profile below,
with **no custom motor/contact/limit/projection solver** and no solver mixing.
Policy/reset/observation joint coordinates stay unchanged; two small GPU
coordinate-conversion kernels bridge the centered native ball coordinates.
CPU tests covered 128 randomized poses, inverse/in-place conversion and FK
(maximum position error 1.2e-7 m). Real L4 smoke covered 24 policy ticks,
resets, reciprocal reward and one discarded PPO update; maximum native/Newton
body-position discrepancy 5.6e-7 m, finite states/gradients. Production resumed
the original checkpoint, not the smoke-test update.

Source archive 6,611,746 bytes is S3 readback-verified at
`mimickit/pipeline_20261014/equipment/native-getup/source_4c08e356110e.zip`.
Receipts: `Saved/MimicKitEquipment/native-launch.json`, `native-preflight.json`,
`native-source-verified.json`, `native-getup-source.json`. Replayer and
chronological TensorBoard bridge are launched under this run name.
Live verification reached update **687 / 11,272,192 samples** with finite
training metrics. Recent 30-update mean **1.726 s/update**, **9,492 transitions/s**
on the L4, excluding periodic evaluation/checkpoint overhead. The earlier
custom get-up measurement was 3.920 s/update: this observation is about 2.27x
faster, not a new paired benchmark or evidence of improved learning.
Checkpoint657 is S3 readback-verified (29,010,282 bytes, SHA256
`d295a90116e534ade2a96bb929606d3d52da374b1783129f963364ac466d03a4`);
the persistent latest_verified pointer matches the local bridge receipt.
Replayer8021 has its first 20-row deterministic capture at657, and TensorBoard
8035 exposes the new dated run and all six losses plus total. Initial noiseless
mean episode length is 15.03 ticks (0.501 s); recovery success is not claimed.
Receipt: `Saved/MimicKitEquipment/native-live-verification.json`.
The native limits remain a spherical PHAT approximation; this does not claim
exact Jolt contact parity or eliminate the penetration measured in the audit.
Unreal, PHAT, source animations and unrelated processes were not changed.

## October 18 — native MuJoCo audit completed; paid GPU stopped

User authorized a replacement L4 for at most 10 minutes / $0.10 to verify
native settings. Audit pod `u7yyhwcg8xt179` ran for 236.2 seconds including
setup, then API-confirmed EXITED. Estimated GPU cost is $0.0387 at $0.59/h,
not a provider invoice. The previous retained pod `v05mjf1bj17lwa` and its
checkpoint remain untouched. No training was launched by this audit.
After local evidence and persistent-S3 SHA256 readback verification, only the
disposable audit pod was deleted; absence from the pod list was confirmed.
Archive: `mimickit/diagnostics/native-audit-20261018-65f2607c0753.tar.gz`,
17,445,619 bytes; receipt `vanilla-calibration/persistent-audit.json`.

Same frozen old Run LR checkpoint 4013, archived rig, 16 distinct starting
phases, 10-second horizon, original 27 cm tracking criterion, 240 Hz physics
and 30 Hz policy. All candidates use native MJWarp 3.5.0.2, without the custom
contact/motor/projection solver. GPU results:

| Native settings | Completed starts | Mean duration | Physics / policy tick, 512 worlds |
| --- | ---: | ---: | ---: |
| Original Newton-converted model | 0/16 | 0.990 s | 12.09 ms |
| PHAT-centered spherical ball bounds + contact profile | 12/16 | 7.600 s | 16.99 ms |
| Above, motor gains ×0.9 | 13/16 | 8.202 s | 17.51 ms |
| Above, original gains, contact solref [0.0175, 2] | 13/16 | 8.233 s | 16.81 ms |

Provisional native candidate: the last row, preserving motor gains and torque
caps. Largest improvement came from restoring native ball-joint bounds:
Newton's original conversion had left those joints unlimited. Each native
ball bound is centered on the PHAT reference and uses its largest axis limit.
This is a spherical approximation, NOT the exact PHAT swing ellipse/twist.
The reference motion fits these bounds. Coordinate rebasing preserves actual
body poses, geometry, mass/inertia, reset states and motor axes. Armature is
zero. The production Newton state/observation adapter now preserves the
original joint-coordinate convention (see current launch above); do not simply
edit body_quat and leave resets/observations unchanged.

Other selected native settings: implicitfast integration, Newton solver,
elliptic friction cone, impratio 10, tolerance 1e-8, max 100 solver iterations
and 50 line-search iterations, floor priority 1 / condim 3 / friction 1,
frictionless self contacts (condim 1). No physics-frequency change.
CPU solver actually averaged about 3.19 iterations on the selected trial;
100 is a ceiling, not an executed fixed pass count. GPU iteration counts
were not instrumented in this audit.

Limitations: three starts still fail early. Exact collider geometry measured
from the saved GPU frames reaches 5.06 cm floor penetration in the selected
candidate (4.21 cm with reduced gains); substep peaks were not measured.
This is not exact Jolt contact parity or a fully solved transfer. The benchmark
measures eight captured physics steps plus a GPU reset, with paired identical
initial states/commands: selected settings cost 39.1% more than unconfigured
native physics. It does NOT measure full PPO or establish the speed ratio to
the earlier custom-solver get-up run, which used different motions/current rig.
No current-PHAT/get-up validation or training success is claimed.

Evidence: `Saved/MimicKitTransfer/vanilla-calibration/audit-summary.json`,
`selected-profile.json`, `gpu-results.json`, `gpu-evidence.tar.gz`,
`replacement-session.json`, CPU `confirm.json` / `finalists.json`.
Reproducers: `Labs/MimicKitTransfer/calibrate_vanilla.py`,
`package_vanilla_validation.py`, `validate_vanilla_gpu.py`,
`run_replacement_vanilla_audit.py`, `summarize_vanilla_audit.py`.
The prior custom training checkpoint remains verified 656_final, SHA below.
Unreal, current PHAT, source animations and other work were not changed.

## October18 — custom training stopped; native MuJoCo calibration underway

User replaced the custom-solver approach with native MuJoCo settings calibrated
against the successful old Run LR Unreal/Jolt test. Run
20261018_062758_uefn_getup_frame0_reciprocal_512 stopped gracefully at656_final.
Owned pod v05mjf1bj17lwa is EXITED; no new paid window/allocation.
Checkpoint29173079bytes, SHAd4496271001dd5cfa443ee95ea01ee2305c9b5499ec47d8b762fe46d112dc105,
verified locally in Saved/MimicKitEquipment/getup-reciprocal-stopped-latest.zip
and persistent storage. Receipt: getup-reciprocal-stop.json in that directory.

Read the version-matched MuJoCo3.5.0 modeling, computation, XML and MJWarp
documentation BEFORE parameter trials; checked installed MJWarp3.5.0.2 source.
Calibration is CPU-only, isolated archived4013 checkpoint/body; Unreal, current
PHAT and other GPU work untouched. Do not promote a candidate from reward alone.
Use recorded successful Jolt states/commands for one-tick response, followed by
feedback-policy rollouts with identical phases and27cm tracking checks.

Parameter coverage: timestep/integrator; solver/cone/Jacobian/iterations/tolerances;
contact impedance/reference, friction dimensions/mixing, margins; joint limits,
passive damping/armature; actuator gains, control bounds, force caps and frames;
gravity/drag, collision filtering and GPU capacity/graph settings. Keep body
geometry/mass/inertia and torque caps unchanged during the first comparison.
No-slip, PGS, full implicit integration and contact override are unavailable in
installed MJWarp; sparse Jacobians ARE supported despite older documentation.
Native ball limits cannot exactly express PHAT swing/twist: report that gap.
Native velocity force-clamp integration also differs from the custom coupled
solve; smaller timestep is a documented candidate, not assumed equivalent.

Sources: [modeling](https://mujoco.readthedocs.io/en/3.5.0/modeling.html),
[computation](https://mujoco.readthedocs.io/en/3.5.0/computation/index.html),
[XML reference](https://mujoco.readthedocs.io/en/3.5.0/XMLreference.html),
[MJWarp](https://mujoco.readthedocs.io/en/3.5.0/mjwarp/index.html).
Latest user constraint: keep physics240Hz and policy30Hz. Earlier isolated
480/960Hz candidates are historical evidence only and EXCLUDED from selection.
Production frequency was never changed; harness now rejects other frequencies.
Harness: Labs/MimicKitTransfer/calibrate_vanilla.py. Evidence directory:
Saved/MimicKitTransfer/vanilla-calibration. No native candidate accepted yet.

## October18 — matched L4 get-up speed audit versus vanilla MJWarp

User asked why the current run is slower and requested a vanilla comparison.
Measured on the same owned L4 using disposable copies of checkpoint500,
512 worlds,32 policy ticks/update, same body,240Hz physics, network/PPO,
command bounds and seed. Production PID388 was suspended for210.4s while
three diagnostics ran sequentially, then resumed in finally; independent
resume watchdog also installed. No production weights/configuration/deadline
changed and no second allocation. Each diagnostic had a180s timeout.

Uninstrumented median of the last3 of5 updates: current frame0 setup3.9198s;
only changing resets to random source frames3.5900s; vanilla Newton/MJWarp
backend1.3168s. Current is2.98x vanilla update time. Vanilla retains this
UEFN asset, zero armature, torque-cap envelope and exact current action bounds,
but uses upstream motors/contact/limits and omits our Jolt adapters, drag/gyro
correction and position guard. It is a performance baseline, not physically
equivalent or a proposed drop-in training replacement. Trajectories differ.

Separate synchronized attribution (nested ranges overlap; instrumentation
adds overhead): current physics3.2607s vs vanilla0.5645s (5.78x), reset work
0.3576 vs0.3554s, observation/reward/done0.2347 vs0.2090s, actor+critic updates
0.1610 vs0.1749s. Dominant cost is the custom coupled contact/limit/motor
solver, not PPO or replay. Four captured physics ticks attribute88.96ms/tick
to two block-solve kernels plus a scalar seed/retry kernel; angular position
projection3.62ms and floor guard1.26ms/tick are much smaller. These are measured
GPU kernel times, not claimed pass counts. Scalar3000-pass fallback counters
were ZERO over those4ticks; no evidence that that fallback caused this sample.
Current sampled contact count8.69/world vs2.63 with random starts. Randomizing
starts reduced whole-update time8.4%, so frame0 alone does NOT explain the full
historical1.85s-to-current3.92s difference. Historical timings used different
policies/termination/reference distributions; do not claim a matched regression
or blame the reciprocal reward from those before/after numbers.

Evidence: Labs/MimicKitTraining/audit_getup_speed.py;
Saved/MimicKitEquipment/getup-speed-audit.json (includes raw timing samples,
per-stage attribution, top kernels, fallback counters and suspend/resume receipt).
Remote speed-audit-20261018 retains individual results/logs. No checkpoint
copies or optimizer results saved by the audit. Afterward production reached
610/10,010,624samples,3.9409s/update; checkpoint600 backup verified, no failure
files. The08:25:18 Warsaw billing deadline remains unchanged.

## October18 — durable replay history and true capture timestamps

User correctly reported100/200 apparently one minute apart and200 disappearing
after refresh. Actual pod capture timestamps:100 at06:36:11.494,200 at06:41:29.034,
300 at06:46:50.570 Warsaw. Gaps317.54s and321.54s. Dropdown used local file mtime;
100 was converted late during the previous repair, making its displayed time
misleading. The history bug was real, not merely a missing manual refresh:
bridge replaced last_batch_rollout.json while viewer archived only every7min.
A capture could be displayed then overwritten before archival.

bridge.publish_rollout now archives each received step BEFORE publishing latest,
deduplicates by step, and stamps archive mtime with actual computed_at capture
time. Conversion failures are not acknowledged in the telemetry cursor and can
retry. Successful sync clears stale bridge-error.txt. Restored0 and200 by
extracting only their NPZ members from existing remote checkpoints (~764KB
combined; no full checkpoint downloads).100/300 also have corrected timestamps.
Only local bridge restarted (20992); GPU trainer/deadline unchanged. New400
arrived and was archived automatically during verification. Browser selected200
successfully with all other captures retained; refresh loads newest from the
same complete list. test_bridge_history.py passes preservation/dedup/timestamp
checks. Applies to future local MimicKit captures without extra GPU evaluations.

## October18 — reciprocal rollout display repaired without trainer restart

User reported no rollout in replayer. NPZ capture and telemetry were working,
but replay.py only recognized exp_negative_sum; reciprocal_sum fell through to
the legacy negative-loss assertion and prevented last_batch_rollout.json from
being published. Earlier launch verification checked NPZ metadata and missed
this conversion failure. Require end-to-end conversion/viewer verification
when changing reward transforms, not just successful recording.

Converter now validates1/(1+sum physical terms) for reciprocal_sum, preserving
the auxiliary auto-phase exclusion and existing exponential/negative paths.
Reconverted current update100 (1,654,784samples),20 rows, and visibly verified
the selected live run, motion and per-tick losses in the browser. Only local
bridge23008 restarted as27392; trainer388 and deadline are unchanged. Proof:
Saved/MimicKitEquipment/reciprocal-replay-fixed.png. Regression test added for
reciprocal conversion, auxiliary phase exclusion and rejection of bad rewards.
All3 targeted replay tests passed. Broader pipeline suite had10 passes and an
unrelated existing resume-fixture error (fake Agent lacks _env); no training
resume code changed. Current capture was also checked through the actual
20-row converter and browser, with playback visibly advancing.

## October18 — fresh frame-zero get-up run with reciprocal reward

Latest user direction cancels further animation cleanup. The pinned preview
was rejected: although its root was restored, torso IK and leg changes inherited
from the first cleaner still moved the head/feet. Checking only root equality
was insufficient, and the prior response overstated what was preserved. No
preview edits are promoted into training. Preserve existing packaged target
and reset motions exactly; their known incompatibilities remain unresolved.

User explicitly approved fresh weights/counters,512 worlds, all get-up starts
at authored frame0, and reward=1/(1+total weighted error), for two hours on L4
at <=$0.59/hour ($1.18 GPU ceiling). Keep pelvis-XY following, existing weights,
auto-phase input,50/50 front/back sampling,34 velocity controls,30cm all-five
termination spheres, and reset at clip end with NO idle tail. No new animation,
PHAT, motor, solver or PPO changes. The reciprocal transform is opt-in through
tracking_reward_form=reciprocal_sum; default exponential behavior is preserved.
idle_recovery.start_at_frame_zero=true applies on every reset, not just startup.

Local64-world physics smoke passed3 full resets and8 ticks each: all starts0,
both clips sampled (98/94), exact reciprocal reward checked on every step and
finite observations/rewards. Source archive comparison found only train.py
provenance text, recovery_omni.py, absolute_walk.py and env_config.yaml changed.
Persistent source readback SHA256:
9f4967710ef741a09bd4e7758652cfbd483835dbac05e0295aae3305d7589c94.
Evidence: reciprocal-smoke.json; reciprocal-source.json; launcher
Saved/MimicKitEquipment/fresh_reciprocal_two_hours.py. Owned v05mjf1bj17lwa
restarted with local/remote billing guards. Startup time is included in7200s
cap; launch uses --keep-deadline and no --resume.

Live:20261018_062758_uefn_getup_frame0_reciprocal_512, trainer388/exit guard389,
local billing guard9180, bridge23008/dashboard19348. Hard stop08:25:18 Warsaw
(1792304718.265493), with save/upload reserve before it. Verified update10 /
180,224samples advancing at4.40e3transitions/s; resume.json reports zero prior
samples and iteration offset. First save checkpoint0000000 (16,384samples)
persistently readback-verified, SHA256
9c3a603a2ee8603235164f2f39003006e54837bcbe9cf05d47f72561cd5227bd,
28,715,083bytes. S3 latest_verified independently checked locally. All20 replay
rows start at0.0s and record reward_from_loss=reciprocal_sum. TensorBoard has
reward, episode duration, optimizer and every weighted loss card under the
2026-10-18_06-28-04_UEFN_Getup_frame0_reciprocal_512. Evidence: reciprocal-live-check.json and per-run
dashboard/bridge receipts. No preview cleanup was deployed.

## October18 — hand contact correction supersedes the first cleanup preview

User rejected the independently corrected frames because hands jiggle/slide;
the earlier pelvis lift was also not authorized. Training remains stopped and
the verified final2222 checkpoint below remains safe. No cloud operations here.

New candidate: Saved/MimicKitEquipment/recovery-pinned-preview/.
Original pelvis XYZ and orientation are restored exactly at every authored
frame; intermediate samples follow the original MotionLib root interpolation.
PHAT and packaged training motions remain untouched. During selected support
intervals, both hands have fixed world-position anchors, with smooth approach
and release targets and preferred stable orientation. Torso plus arm IK solves
those constraints together with the exact PHAT joint limits and hand collider
floor clearance. Root motion is never an IK variable. Support intervals at
original30Hz: front right6–18 /left6–12; back right10–16 /left10–12.

30Hz joint interpolation initially caused up to3.27mm hand drift between pinned
frames. Offline120Hz constrained samples reduce this to0.201mm maximum, measured
through actual MotionLib interpolation at960Hz (2,818 samples). Both clips have
zero joint-limit violations and finite velocities. Minimum hand floor clearance
is1.207mm front /1.304mm back. Hand rotation excursion during support is at most
1.094 degrees; positions are pinned, orientations are softly preserved rather
than locked exactly. All authored root samples compare bit-exact to the source.
Duration unchanged:1.533s front /1.400s back. No runtime IK is added to training.

IMPORTANT: this is a hand-contact preview, not a fully floor-clean training
dataset. Restoring the original pelvis removes the prior whole-body lift;
torso/pelvis/lower-body penetration remains, up to44.55mm front /13.13mm back.
Do not represent the old all-body clearance validation as applying to this
candidate, or deploy it silently. Do not lift the pelvis to hide other collider
penetration without explicit user authorization. Keep temporal contact checks
alongside floor/limit tests: per-frame floor clearance alone is insufficient.

Scripts under Labs/MimicKitTraining: pin_recovery_hands.py,
refine_pinned_recovery.py, publish_pinned_recovery.py,
validate_pinned_recovery.py. report.json and validation.json retain numeric
evidence; original30Hz candidate files remain for comparison.
Preview: http://127.0.0.1:8843/Saved/MimicKitEquipment/recovery-pinned-preview/

## October18 — user stop and constrained get-up cleanup for visual review

User requested stopping training, cleaning the animations and showing them,
specifically hand IK AFTER enforcing joint limits. No restart authorized here.
Owned L4 v05mjf1bj17lwa stopped; Runpod API confirmed EXITED. Final2222 archive
was read back from persistent storage and downloaded locally with SHA256
452417cfaafd46f12e50d25f8cf35f22f3a5126059e34e0727aaee705c700dd9.
Local checkpoint: Saved/MimicKitEquipment/getup-cleaning-latest.zip;
receipt: getup-cleaning-stop.json. Original animations, package and PHAT remain
unchanged. Preview candidates are in recovery-cleaned-preview, not deployed.

Cleaner first projects joint rotations into the exact retained twist/swing
ellipse or hinge interval. Then constrained IK clears the actual PHAT collider
shapes while retaining those joint constraints throughout the solve. Hand and
foot targets keep horizontal position and prefer their limit-projected
orientation; elbow/knee/body deviations are minimized. Root XY, root rotation,
clip timing and frame counts stay authored. Pelvis Z is raised only where its
own collider needs clearance (and minimally if the remaining floor constraints
require it); hand clearance is solved separately through arm IK. This also
clears other body colliders rather than hiding penetration outside hands/feet.
No self-collision constraint added. Initial2mm clearance provides interpolation
margin; local refinements address any remaining dips between authored frames.

Both reset and target will use the same cleaned trajectory on a future approved
launch. MotionLib derives fresh root/joint velocities from these new frames;
old reset-only IK files must NOT be paired with the cleaned targets. Current
reward and training configuration are unchanged. Cleanup scripts:
clean_recovery_preview.py, refine_clean_recovery.py, validate_clean_recovery.py
under Labs/MimicKitTraining. Validation uses actual MotionLib interpolation at
960Hz, checking all colliders, exact joint limits and finite velocities.
Final verification passed2,818samples: no joint-limit violations, minimum
collider clearance0.327mm front /0.540mm back. Maximum pelvis-height change
from the original is4.625cm front /1.513cm back; horizontal root path and
orientation unchanged. Original duration1.533s/1.400s and47/43frames retained.
An initial check caught between-frame dips up to7.24mm and a left-ankle
interpolation violation; local constrained refinements fixed these before
delivery. This is geometric/interpolation validation, not a guarantee of
dynamic tracking with the existing checkpoint.
Browser preview opened and visually checked at hand-support frames, with both
animations playing and optional original-target overlay:
http://127.0.0.1:8843/Saved/MimicKitEquipment/recovery-cleaned-preview/
Preview screenshot, validation.json and refinement.json are in that folder.

## October18 05:30 — why early get-up starts fail: frozen-policy audit

Read-only investigation; live sphere30 run was left unchanged and advancing
(iteration2132 /34,947,072samples observed). No new cloud allocation or extension.
Frozen checkpoint1822 /29,868,032samples downloaded and SHA256 verified locally:
252811ac2a2cd2b3958f174e9560f65d97b63a4c84e553ea38fd4ac7a4faafe4.
Local package limits and both target motions were SHA-matched to the live pod.

64 deterministic starts: two get-ups,16 evenly spaced source-frame phases,
both equipment groups. First-quarter starts completed0/16; last-quarter16/16.
The first-quarter failures occurred after0.133–0.200s. Front first-frame start
failed on left-foot distance at tick5; back first-frame on head distance at
tick5. Replacing autoregressive phase input with perfect authored phase in
the paired local experiment left completions40/64 and early completions0/16.
This does not support phase prediction as the principal cause here.

Confirmed target/reset incompatibilities with the ACTUAL packaged PHAT:
- Original targets violate joint limits in18/47 front and27/43 back source
  frames. No violations in either final quarter. Back right-shoulder twist
  exceeds its bound by up to38.41degrees; torso/hip/knee/ankle limits also fail.
- Reward targets still contain floor penetration: back right hand12.58cm,
  front right hand6.71cm; feet about4.5cm. Earlier IK corrected reset files
  ONLY, leaving tracking positions/rotations/velocities on the original clips.
- Reset IK clears hands/feet but not the rest of the body: front torso/pelvis
  penetrate up to4.48/4.42cm; back torso3.23cm. Corrected resets still violate
  joint limits in18/47 and27/43 frames. Therefore these are not wholly feasible
  reset states, and exact reference tracking is physically contradictory.

Reward starvation compounds this: exp(-sum of all weighted errors), with
scales inherited from RunLR. Front frame0 reward falls from0.0501 at tick1
to1.585e-8 at tick5. First-quarter mean reward0.0310 vs final-quarter0.951;
51% of pre-failure first-quarter ticks have reward below1e-4. This is evidence
of a weak learning signal after early divergence, not proof of zero gradient
or that reward changes alone would solve it. 30cm termination then prevents
these attempts from reaching the successfully learned later portion.

Every physics substep in the first0.20s was instrumented locally. For unarmed
first-frame starts, maximum motor torque/cap was0.678 front,0.403 back, with
no saturated axis/substep; commanded velocities also stayed inside bounds.
This rejects torque saturation as the immediate reason THESE policies fail;
it does not prove the caps can reproduce the full authored trajectory.
Extra split-position limit projection moved bodies by less than3e-8m on
these early starts (the floor guard blocks it), so do not blame the newly
added position-projection correction for their observed30cm divergence.
Contact and velocity-limit constraints remain active. Zero-velocity-command
controls still diverge from the moving reference; they are not limp controls.

Recommended next work: make a single feasible recovery trajectory consistent
with floor and joint limits and use it for both resets and tracking, including
recomputed velocities. Review any PHAT/animation change before deploying.
Then reconsider the all-terms exponential scaling and early-start curriculum;
do not blindly increase torque or assert that these changes guarantee recovery.
No physics, PHAT, reward, dataset or live-run change made by this audit.
Evidence: Saved/MimicKitEquipment/getup-start-audit/{report,targets,corrections}.json;
paired policy_phase/clock_phase traces and substep NPZs. Reproduction helpers:
Labs/MimicKitTraining/diagnose_getup_starts.py (also --corrections),
diagnose_getup_corrections.py, audit_getup_targets.py.

## October18 04:27 — resume get-up with all five30cm spheres

User requested latest-checkpoint continuation for two hours with full sphere
termination at30cm. Prior clip-end-only run stopped gracefully at921_final,
15,106,048samples; locally downloaded and SHA3e704d44bd14 verified against
persistent archive (sphere30-resume.json /sphere30-resume-latest.zip).
New20261018_042646_uefn_getup_sphere30_512 uses --resume, preserving weights,
optimizer/normalizers/counters;512recovery rows, pelvisXY target and clip-end
reset/no idle tail remain. Fail when any head/right-hand/left-hand/right-foot
collider-centre target deviation is strictly greater than0.30m after time0.
Other failure conditions stay disabled; sphere_only is distinct from the older
path that also re-enabled pose termination. Clip-end/horizon resets remain;
sphere failure takes precedence when both happen on the same tick.

CPU boundary tests cover all five points (exactly30cm accepted,30.1cm fails),
and512-world/eight-tick physics smoke checks actual flags; passed sphere30-smoke.
Source7936f559e5e2 fully verified persistently. Same L4 v05mjf1bj17lwa,
trainer880/exit guard881; two-hour hard deadline1792297612.081509 =06:26:52
Warsaw, <=$1.18 additional GPU ceiling. Bridge27884/dashboard7896 started.
Replayer sphere geometry already reads radius_m; its formerly hardcoded27cm
label now also reads recorded radius, preserving accurate historical labels.
Resume verified: prior_samples15,106,048,iteration_offset922, optimizer and
normalizers restored. New checkpoint922 (15,122,432samples) persistently
verified, SHA81f448163591. TensorBoard and20-row replay checked: sphere_only=true,
radius_m=.3, all five body names, reset_at_getup_end=true. Receipt
sphere30-live-check.json; helper resume_sphere30_two_hours.py.

## October18 — correction: get-up completion resets; no idle tail

User corrected the fresh-only experiment: do NOT append idle after get-up.
Disabling failure termination must never implicitly disable authored clip-end
reset. These are independent controls. reset_at_getup_end=true now remains
effective with timeout_only=true: no pose/contact/distance failure checks, but
clip completion (or10s safety horizon) resets immediately. Reference remains
the get-up clip through the final tick, never switching to idle. Random starts
exclude the final source frame so every episode has at least one interval.
PelvisXY following,512recovery rows, remaining settings unchanged. Restart from
fresh weights/optimizer/normalizers and zero counters; new two-hour window.

The incorrect20261018_032329 run stopped gracefully; final194 /3,194,880samples
verified persistently, SHA02df9039ebc1, receipt clip-reset-prior-final.json.
Regression checks distinguish ordinary-row failures, recovery no-failure,
authored clip-end completion and horizon timeout.512-world/eight-tick physical
smoke passes with reset_at_getup_end=true and no idle-reference tick
(fresh-clip-end-smoke.json). Source8ac3411327c6 verified in persistent storage,
helper fresh_clip_end_two_hours.py. Corrected run
20261018_033547_uefn_fresh_getup_clip_end_512 launched on the same L4, trainer663,
exit guard664; fresh two-hour hard deadline1792294551.9579153 =05:35:51 Warsaw.
No checkpoint loaded; resume.json reports prior_samples=0/iteration_offset=0.
First checkpoint0 (16,384samples), SHA8cb97e2bd949, is persistently verified.
TensorBoard and20-row replay verified: every row reset_at_getup_end=true,
failure checks disabled, phase mode 'get-up authored clock; reset at clip end'.
Recorded durations0.067–1.167s reflect different random start frames; no idle
tail. Receipt fresh-clip-end-live-check.json. Pending mixed-motion resume helper
also preserves clip-end resets; rebuild its source before any future launch.

## October18 — fresh noisy-idle-only side experiment, two hours authorized

User superseded immediate mixed-motion resume with a temporary fresh experiment:
512worlds,100%idle and100%recovery membership, random front/back get-up source
frames, pelvisXY-relative target positions, existing world heading/height and
velocity/angular tracking, existing calibrated weights and auto-phase. Fresh
weights/optimizer/normalizers and zero counters; no --resume argument. Keep
the337.74M mixed-motion continuation pending and its checkpoint intact.
No early termination on these rows;10s horizon remains. Authored get-up target
clock transitions to the existing autoregressive idle target after clip end.
Two-hour GPU authorization at <=$0.59/hour (ceiling$1.18), replacing the initial
one-hour answer. Dedicated helper fresh_idle_two_hours.py/source archive leaves
the pending mixed-motion config intact. Row allocation now admits exactly100%
idle, explicitly skips the empty locomotion cohort; previous fractions unchanged.
Local512-world/eight-tick fresh-policy smoke, cohort assertion and horizon check
passed (fresh-idle-smoke.json). Source619b45150390 fully verified in persistent
storage. Original host rejected start for insufficient GPU capacity; its stopped
disk remains retained (retained-t7kby2z4440esp-pod.json). Replacement Secure L4
v05mjf1bj17lwa allocated at$0.59/hour; hard stop1792293667.513482 =05:21:07
Warsaw, including setup time within the$1.18 ceiling. Runtime cache restored and
verified in37.3s. Launched20261018_032329_uefn_fresh_noisy_idle_512 at03:23:35,
trainer432 /exit guard433; local billing guard2004, remote billing guard active.
Fresh command has no checkpoint argument. Bridge14124/dashboard18676 started
with a separate datetime experiment and20 noiseless replay rows. First checkpoint0
(16,384samples) is fully uploaded/readback verified, SHA27c3cec0dadf1; S3
latest_verified independently checked. Learner advanced through update4/81,920
samples. Initial update3.01s /5,438transitions/s; this is startup timing, not a
steady-state benchmark. Runtime recovery_setup confirms512recovery/0ordinary
idle/0walk/0run, absolute_target=false and timeout_only=true. Test return1.17
is initial evaluation, not proof of learned recovery. TensorBoard experiment is
visible; first20-row replay loaded and checked: all rows timeout_only=true,
target_position_mode='pelvis XY following'. At03:28, update50/835,584samples,
recent mean1.846s/update (8,874transitions/s), no failure receipt. Receipts:
fresh-idle-live-check.json and fresh-idle-source.json. The source/PHAT and all
existing checkpoint archives remain preserved; no earlier run resumed.

## October18 03:05 — prepared rollback to337.74M; launch blocked by balance

Latest user request: resume checkpoint20613_final (337,739,776 samples) for
three hours, remove all early termination from noisy idle/recovery rows, and
restore pelvis-relative get-up tracking. Use idle18-resume-latest.zip and its
idle18-resume.json checksum3b008cfdf37b; local and persistent full readback verified.
Do not substitute the later383.6M checkpoint.

Prepared config keeps18%idle (92rows:74recovery/18ordinary),168walk/252run.
Recovery timeout_only overrides pose/contact/27cm/clip-end resets; only the
existing10s horizon resets these rows. After authored get-up ends, they follow
idle using autoregressive phase as previously implemented. Other rows retain
all their existing termination checks. Numerical safety checks remain active.
absolute_target=false makes get-up target positions follow current pelvisXY;
authored world heading/height and world velocity/angular targets remain intact.
No local-joint loss or full pelvis-rotation alignment was introduced.

Termination override passed512-world/eight-tick physical smoke and horizon
check; a dtype mismatch found in that smoke was fixed before cloud startup.
Subsequent pelvisXY change passed full/subset target translation tests with
height preserved. The full physical smoke preceded that final config switch.
Canonical shared-actor optimization from the completed audit is in the prepared
package (including corrected auto-phase metric reporting). Source is stored at
equipment/timeout-pelvis-xy-20261018/source.zip under the existing S3 pipeline.
Helpers: resume_timeout_three_hours.py, timeout-source.json,
test_recovery_timeout_only.py and timeout-only-smoke.json.

Runpod POST start rejected the existing L4 t7kby2z4440esp for insufficient
account balance. Stop call completed; readback confirms EXITED. No new trainer
or observer started. Three-hour authorization remains for the eventual launch;
regenerate deadline at successful startup, not from the failed attempt.

## October18 — replay / TensorBoard recovery after local internet outage

Owned pod t7kby2z4440esp is confirmed EXITED; no restart or new GPU was used.
Recovered 11 missing checkpoint replay captures using S3 ZIP byte-range reads
(66,952,038 bytes transferred, CRC-checked members, no model downloads).
Local replayer now contains all 29 persistently saved captures, 20 rows each,
through update23414 /383,631,360 samples; latest points to that capture.
Original capture timestamps retained and dropdown steps deduplicated.
Restored 18 genuine TensorBoard points from checkpoint metadata: six test
episode durations, six test returns and six training total losses. Original
event files preserved; no curves interpolated. Latest-ten experiment cap stays.

Limitation: persistent storage has no final archive or exit-evidence bundle for
this run. Full training event log after local update22894 was not uploaded in
the intermediate checkpoints, so detailed training curves cannot currently be
recovered from S3. They may remain on the stopped pod's retained disk. Do not
claim final completion, a clean shutdown or a precise stop time from this data.
The local billing guard only confirmed EXITED after connectivity returned at
02:22 Warsaw; this is confirmation time, not evidence of when billing stopped.
Recovery scripts and receipts: Saved/MimicKitEquipment/offline-telemetry-recovery,
recover_offline_telemetry.py and restore_recovered_scalars.py.

## October17 20:05 — 18% idle continuation, fresh three-hour authorization

User interrupted the optimization audit to triple idle allocation and remove
head/hand 27cm termination only from noisy idle/get-up rows. Run
20261017_200515_uefn_equipment_idle18_512 resumes latest20613_final, SHA3b008cfdf37b,
verified locally in idle18-resume-latest.zip and by full persistent S3 readback.
Same owned L4 t7kby2z4440esp, $0.59/hour. Fresh three-hour hard deadline
1792271122.0458524 =23:05:22 Warsaw;165s reserved for final save/evaluation.
All deadline readers updated; new trainer-exit guard678 and independent local/
remote billing guards retained. No GPU release/reallocation during handoff.

512 rows now:92 idle (74 recovery,18 ordinary),168 walk,252 run. Recovery rows
retain pose-MSE, both feet's27cm deviation, clip-end reset and timeout checks;
head/hand deviations remain tracked/rewarded but do not independently terminate
these rows. Ordinary idle/locomotion termination unchanged. Same learned model,
optimizer, normalizers/counters; new physical episodes and fixed assignments.
Unit termination checks and512-world/eight-tick physical smoke passed. Source
0911d5acbdf9 is persistently verified; idle18-source.json, idle18-smoke.json and
idle18-resume.json record evidence. At20:10 learner reached20684/338,903,040
samples; all four actual cohort counts match, full optimizer/normalizer resume
confirmed. First new20614 checkpoint has persistent full readback verification
(SHAb98d8bd44c6d);20-row replay and TensorBoard update correctly. No fatal error.
Last30 updates average2.623s /6,246 transitions/s with the larger recovery share;
this changed workload is not a matched speed comparison against6% idle.

At20:31 live training reached21094/345,620,480 samples. Latest checked persistent
save21014 SHAe0e59dbbde0b is verified; replay21014/TB respond; no fatal error.
Last30 updates2.831s /5,787 transitions/s. Learning metrics have fluctuated after
the new mixture: this confirms advancing training, not improved recovery quality.
Live run is left uninterrupted until the23:05:22 deadline.

## October17 20:32 — full follow-up optimization audit completed

All five researched directions were tried locally, with no second cloud GPU,
Unreal interaction, PHAT edit or change to the live learner's physics.

Accepted in canonical code/future source packages: PPO and auto-phase now share
one actor hidden-layer pass when exploration probability is1. Mixed exploration
keeps the reference path. Inputs, outputs, rewards, SGD/momentum, minibatch
sampling, noise and physics remain unchanged. In the paired512-world full-PPO
benchmark, warmed complete update10.5488 ->10.0946s (**4.31% less time**); the
non-rollout portion2.2573 ->1.4736s (**34.7% less time**). These are LOCAL4060
measurements with trajectory/timing variation, not an L4 gain or a large physics
speedup. Both paired blocks improved; physics still dominates. Evidence:
optimization-followup/full-shared.json and ppo-v4.json.

Numerical scope: the loss is algebraically unchanged, but combining backward
paths changes float32 summation. Single-batch gradient checks pass (about1e-7
with all stochastic actions); repeated clipped/ReLU PPO updates amplify tiny
rounding changes. A strict2e-6 parameter-equivalence check failed, retained in
ppo-v3/ppo-v4; do NOT call this bit-identical. ppo-trace.json records the growth.
The old Unreal Run LR4013 checkpoint and its exact archived body were tested:
16 distinct phase starts repeated across512 worlds,10s each. Original, one
reference PPO update and one shared-actor PPO update all passed every start,
zero solver warnings; peak target distances18.05/18.83/18.45cm respectively,
below27cm. No new learned checkpoint saved. This is MJ behavioral validation;
unchanged Jolt native evidence remains historical, not claimed rerun. Report:
optimization-followup/ppo-shared-runlr.json. Production512-world32-tick PPO
smoke and phase-metric check pass in production-actor-smoke.json.

Also fixed a reporting bug: phase_prediction and auto_phase metric aliases
shared storage while upstream accumulated/scaled each key in place, producing
roughly20x underreporting with40 actor minibatches. Independent metric tensors
now report the true mean. Actual supervised phase weight/loss was always used
in backprop and is unchanged. Expect larger displayed phase loss after deploying
the new source; this alone is not a learning regression.

Rejected (diagnostic only): scratch reuse6.226 ->6.394ms; three-axis batched RHS
6.561 ->6.473ms and active-row clearing6.400 ->6.383ms were within timing
variation, not dependable gains. Matched contact impulse reuse preserved the
short Run LR motion but averaged129.83 ->138.89ms per tick, slower. CUDA capture
worked after removing retained autograd graphs but added no clear improvement
over the shared actor calculation at this batch size. No iteration caps,
convergence tolerances, precision, contacts or constraints were weakened.

Release edeeaf57ed7f is packaged as source.zip/recovery-source.zip and fully
readback-verified in persistent storage at equipment/shared-actor-20261017.
audit-complete.json is saved locally and persistently. The ACTIVE L4 still uses
0911d5acbdf9: no optimization hot patch/restart was imposed on this requested
three-hour run. Deploy the new canonical package at the next authorized resume.
All experiments/logs and failed checks are retained under
Saved/MimicKitEquipment/optimization-followup and followup-*.log.

## October17 19:24 — authorized L4 continuation launched; measuring actual speed

User authorized three hours and explicitly said to leave training running and
report actual L4 speed. New owned Secure L4 t7kby2z4440esp costs $0.59/hour.
Run 20261017_192404_uefn_equipment_solver_speed_512 resumes verified19683_final
at322,502,656 samples, including weights, optimizers, normalizers and counters.
Source release d61275b88cbc is verified on the pod. Settings/body/data unchanged.
Hard billing stop1792267893.7239227 =22:11:33 Europe/Warsaw, October17;
training reserves165s for final evaluation/upload. Budget ceiling$1.77 includes
setup time. Local guard, remote deadline guard and trainer-exit guard are active.
Speed alone must NOT stop this run: user explicitly asked to let it run.

The old klyceawn5edw3l host could not resume. Replacement5a5ezh60g5hrwp hit
a PC-upload timeout, then a bootstrap dependency/authentication issue; setup
failures stopped its billing. Its GPU was then unavailable. Both earlier pods
remain EXITED with retained disks. Final replacement uses a SHA256-verified
direct S3 source download and cached runtime. All attempts share the initial
22:11 deadline; retries did not extend the budget. Evidence and helper receipts
are in Saved/MimicKitEquipment.

Actual L4 verification at19:28: last30 complete PPO updates average2.1941s,
7,467 transitions/s (earlier warmed window2.1658s /7,565 transitions/s).
Previous L4 full-PPO measurement3.065s /5,345 transitions/s: now28.4% less
time per update,39.7% more throughput. This is actual resumed training, not a
physics-only benchmark; it is a before/after run comparison, not a simultaneous
paired benchmark. Separate periodic evaluation/checkpoint overhead is outside
that update timer. Latest observed iteration19734,323,338,240 samples; advancing.
No solver warnings, numerical failure or backup errors at the check.
First new checkpoint19684 has verified S3 full readback, manifest independently
confirmed locally. Replay has20 rows atstep19684; TensorBoard serves this dated
run within its newest10 limit; both local viewers respond. Training remains
running as requested. Evidence: solver-speed-l4-live-verification.json and
floor-recovery-optimized-verification.json in Saved/MimicKitEquipment.

## October17 — faster contact solver implementation and local validation

### Further optimization research, October17 — ideas only, live run unchanged

User requested internet research while the current L4 trains. No runtime edit,
cloud profiling, dependency upgrade, benchmark or second GPU workload was made.
Cross-checked current code against primary documentation. Priorities:

1. Persistent velocity-contact impulse warm starts. block_contact_gpu.py clears
   contact/limit/manifold impulses on entry; its existing warm_state/warm_status
   caches motor branches, not previous-tick contact impulses. Match persistent
   contacts/manifolds across substeps, transform friction into the new basis,
   discard invalid matches and episode-reset entries, and solve with unchanged
   residual criteria. Box2D describes temporal impulse reuse as reducing repeated
   convergence work, especially resting contacts. This is a candidate, not a
   proven speedup or bit-identical trajectory: friction/nonunique solutions and
   finite iteration budgets require validation. Do not warm-start position
   projection corrections. Source: https://box2d.org/posts/2024/02/solver2d/
2. Batch small groups of RHS vectors against the same Cholesky factor. Current
   block solver calls tile_cholesky_solve separately for each contact axis,
   limit and spin row. Multiple-RHS solves could share factor reads/instructions;
   modest groups limit extra scratch memory. This differs from rejected reuse
   of factors across changing motor active sets. Verify support/performance in
   pinned Warp1.12.1; current docs may describe newer APIs.
   https://github.com/NVIDIA/warp/blob/main/warp/examples/tile/example_tile_block_cholesky.py
3. Audit compiled shared-memory footprint/temporary tiles, then explicit scratch
   reuse or splitting factor preparation from register-only contact iterations.
   Warp documentation says owning tile allocations accumulate without live-range
   reuse. We already reuse the main factor tile; remaining temporaries may still
   restrict concurrent worlds. Splitting adds launches/memory traffic and is only
   worthwhile if measured whole PPO improves. One-warp blocks also have a50%
   theoretical warp-occupancy ceiling on Ada (24blocks vs48warps), before memory
   limits; this is not proof of the bottleneck. Earlier64-thread-per-world trial
   failed to help; packing independent worlds is a distinct, more invasive idea.
   https://nvidia.github.io/warp/latest/user_guide/programming_model/tiles.html
   https://docs.nvidia.com/cuda/ada-tuning-guide/index.html
4. Avoid work over unused contact capacity. Adapter allocates4*ngeom contact
   slots and3*njnt limit slots, clears full Jacobian buffers and launches several
   preparation kernels over capacity. Prefer active-entry work/fusion or proven
   capacity sizing; never silently drop contacts. MJWarp explicitly documents
   both memory and computation scaling with contact/constraint capacities.
   https://mujoco.readthedocs.io/en/stable/mjwarp/index.html#performance-tuning
5. Lower priority: capture/compile fixed-shape PPO minibatch computations. Physics
   already uses CUDA graphs; upstream actor/critic updates remain Python loops.
   Actor boolean selection gives dynamic batch shape, so full capture is not a
   drop-in toggle. Preserve sampled actions, mask reductions, optimizer steps,
   normalizer timing and RNG semantics. Local candidate PPO has~2.3s outside
   rollout of10.6s total, so this cannot eliminate the dominant rollout cost;
   no corresponding L4 component split has been measured.
   https://pytorch.org/blog/accelerating-pytorch-with-cuda-graphs/

Do not present estimated gains as measurements. Do not blindly lower iteration
caps, increase timestep, enable lower-precision physics, remove floor protection,
or repeat rejected factor/shared-cache experiments under another name. The
highest-value first candidate is contact warm starting, with bounded validation
against the existing captured contacts and current recovery/locomotion states.

The runtime now keeps generalized velocities in GPU registers during contact
iterations, uses full contact corrections, and preconditions friction using the
current articulated response. Both tangent denominators receive the SAME
positive scale: their ratio and the original disk-projection fixed points are
preserved. Spin uses the corresponding scalar response. Motor branch estimates
retain their required 0.5 damping. Gains, torque caps, mass, PHAT, friction law,
constraint order, floor protection, rewards, episode resets and checkpoint are
unchanged. Converged sweeps stop only after BOTH small velocity change and checks
of the original contact/limit/friction equations. Float32 precision allowance is
2e-6 plus eight epsilons of scale, capped at 1e-4. The 100-pass ceiling remains for
hard cases; it was NOT blindly reduced. Larger (>64-DOF) rigs retain the previous
tiled kernel. All stepping remains GPU-only inside existing CUDA graphs.

Measured on this local RTX4060, paired baseline/candidate/candidate/baseline,
512 worlds, latest19683 checkpoint restored between blocks, 12 disposable PPO
updates /196,608 transitions: mean full update13.6211 ->10.6027s, **22.16% less
time /1.285x throughput**. Rollout11.5236 ->8.3033s. Both candidate blocks were
faster than both reference blocks, with finite parameters/buffers and no solver
warnings. This includes fused FK and cached recovery starts as well as the new
solver; it is NOT an L4 result or a guaranteed zero-overhead claim. Candidate
contact passes averaged21.15–21.17 per motor branch solve; max100 still occurs.
The earlier ~77-pass measurement used a frozen-policy diagnostic, so it is not
an exactly matched PPO pass-count comparison.

Validation: 24 identical recorded impacts across512 worlds, qpos difference
<=1.79e-7 and generalized velocity difference<=8.02e-5 versus the old solver.
Final production kernels match independent float64 difficult-case solutions
within1.40e-5; CUDA graphs, bad cached motor branches, finite-budget warnings and
nonfinite rejection pass. The older test incorrectly expected finite-budget
failure to kill training; its expectation now matches the user's existing
warning-only policy. No runtime failure policy was weakened. Actual packaged
floor cases retain peak penetration4.378mm with the guard. Forced-time diagnostic
resets bypass the spawn cache so the test actually uses its requested poses.

Fused FK preserves hierarchy/quaternion algebra (max tested position1.07e-6m,
quaternion component5.96e-7); CPU/autograd retain upstream behavior. Recovery
spawn cache is exact for all90 authored sampled frames. These changes alone
previously delivered only3.5% with strong drift; they were insufficient.
Rejected factor-reuse/shared-cache/exact-cycle candidates remain diagnostic-only.
The additional solver changes above are the implemented improvement.

Evidence: Saved/MimicKitEquipment/floor-recovery/preconditioned-speed-ppo.json,
preconditioned-vs-current.json, production-register-reference/,
production-register-floor.json. Final packaged production smoke passes two PPO
updates (32,768 disposable transitions), finite weights/buffers, no warnings;
its measured second update is9.906s, which is a smoke result, not a new paired
speed claim. Only seven intended Python runtime files were updated in the
frozen package; body/motions/configuration and every other archive entry are
preserved byte-for-byte. Full runtime inventory verification passes.
Source ZIP d61275b88cbc (6,605,955bytes) is published to persistent S3 and its
entire contents independently read back and SHA256 verified. Receipt:
Saved/MimicKitEquipment/floor-recovery/solver-speed-release.json. The local
source.zip and recovery-source.zip match this release. No additional checkpoint
was created. API reconfirms owned pod EXITED at publication.

At optimization completion, pod klyceawn5edw3l was stopped; speed heartbeat remains paused.
Latest19683_final is still locally/S3 verified (SHA3cb1100da832), with322,502,656
samples. No cloud training/allocation, Unreal change or extra checkpoint was
made during that optimization. See the newer live-run handoff above for L4 verification.

## October17 — paid run stopped; isolate and fix the speed regression locally

User rejected continued spending and instructed solving the slowdown. This
supersedes the three-hour continuation below. Owned pod klyceawn5edw3l is
confirmed EXITED. Final19683 archive is checksum-verified both locally and in
persistent storage, SHA3cb1100da832; local file
Saved/MimicKitEquipment/parallel-floor-stopped-latest.zip. Unique exit evidence
also downloaded. Receipt parallel-floor-user-stop.json. The speed heartbeat
is PAUSED. Do not allocate/resume paid training while this investigation runs.
The earlier variable local ABBA timing did not establish acceptable L4 speed;
do not use it as launch evidence. New investigation separates same-state floor
guard time, split-limit projection time, and complete physics/PPO workloads.

Local causal isolation now identifies the reset change, not the floor guard,
as the dominant workload increase. Same frozen checkpoint,512 worlds,90 policy
ticks, fixed seeds: reset-at-getup-end OFF took17.50s without guard /16.94s
with guard; reset ON took32.63s without guard /31.67s with guard. Recovery-row
cold retries rise223->1897 (guard OFF); locomotion work stays essentially equal.
GPU graph trace: floor guard2.27ms of111.20ms physics; motor/contact block solves
dominate. Uncaptured Warp event timings include launch gaps and incorrectly
inflate CRB cost; use captured CUDA profiler results, not those timings.
Existing cache survives teleports; invalidating only reset rows reduces recovery
retries roughly1440->1200 but total time remains32s: insufficient by itself.
Investigating exact redundant contact-iteration cycles; no tolerance relaxation,
controller/PHAT changes or paid work launched. Evidence contact-work.json,
contact-work-invalidate.json, kernel-profile.json. Earlier wording attributing
the full71% slowdown to the parallel guard was not causally justified.

## October17 — three-hour parallel-floor continuation authorized

User authorized resuming the latest checkpoint for three hours and requested
notification if actual training slowdown becomes substantial. This supersedes
the earlier stop/no-restart instructions below. Latest checkpoint19510_final
contains319,668,224 samples, SHA0b5774d06420; local and persistent copies verified.
Old L4 b97r8nr7eo4mc1 could not restart because its GPU was unavailable; retained
disk preserved. Replacement owned L4 klyceawn5edw3l costs$0.59/hour. Its hard
deadline is Unix1792258567.605572 (19:36:07 Warsaw), including setup time;
maximum GPU budget$1.77. No further extension authorized. Source3eb712705f4d
selects the tested parallel guard, keeping existing training settings and
get-up-end resets. Local/remote billing guards remain mandatory.
Setup briefly stopped the pod on a helper KeyError reading hard_stop_unix from
pod metadata; corrected to read runtime_control.json. Same pod restarted with
the original deadline. No training or checkpoint was lost by this setup error.
Trainer launched16:41:19 Warsaw as20261017_164113_uefn_equipment_parallel_floor_512
from the checksum-verified latest archive; restore/progress and L4 speed are
verified below. TB/replay observers launched, existing
servers respond on8035/8021. Quiet five-minute heartbeat
equipment-training-speed-watch alerts sustained update time>2.24s (25% over
original), new failures or completion, and pauses when done. Compare steady
full PPO update time with original1.79s and rejected serial guard3.17s;
the local4060 result below is not evidence of L4 throughput.

Live check16:44 Warsaw: restore confirmed319,668,224 samples, optimizer and
normalizer restored, iteration19521 advancing. First new19511 checkpoint
SHA685b6eeacc63 is independently visible via persistent latest_verified;
no failure file. Crucially, initial post-warmup update2.874s versus original
1.79s (+60.5%). User notified immediately; longer30-update window pending.
Do not describe this as no-overhead or assume the laptop benchmark transfers.
Training remains running under the latest explicit resume-and-report instruction.

Confirmed16:45 Warsaw at19541 /320,176,128 samples: last30 full PPO updates
average3.065s (5,345 transitions/s), excluding initial update. That is71.2%
longer per update /41.6% fewer transitions/s than original1.79s. Only3.3%
faster than rejected serial guard3.17s. Therefore the parallel implementation
has NOT recovered the original L4 throughput. Different replacement host
and different checkpoint trajectories prevent attributing the whole difference
to one kernel without a matched L4 comparison. Do not hide this behind local
benchmark results. User informed; no unrequested tuning or restart.
First verified persistent save19511, SHA685b6eeacc63; no failure file.
20-row local replay and TensorBoard updates confirmed. Recovery-end resets
visible in replay; both unarmed/drawn locomotion included. Evidence:
Saved/MimicKitEquipment/floor-recovery-optimized-verification.json.
Speed watcher should not repeat this already reported3.07s finding unchanged;
report a meaningful worsening, failure, or completion.

## October17 — parallel floor guard tested locally; cloud remains stopped

User asked to continue fixing the overhead after stopping the paid run. No cloud
restart/allocation authorized by this investigation. Two local candidates:
1. Existing-contact mass projection: rejected. The same bad start still reaches
5.58cm penetration vs5.68cm baseline; active contacts miss newly introduced
floor intersections. Evidence contact-metric-candidate.json. Diagnostic code
contact_projection_candidate.py is NOT packaged/selected by training.
2. Parallel geometric guard: one warp per world and one lane per collider,
computing each collider's ancestor transforms independently. Same floor bounds,
search and correction semantics as guarded version; floating-point operation
order differs.1024 randomized geometry cases pass, new penetration<2e-7m,
clear states bit-identical, CUDA replay exact. Worst generalized-coordinate
difference from scalar guard5.1e-5; do not claim bit-identical blocked states.
Matched saved-policy cases keep peak penetration at4.38mm instead of5.68cm.
No controller, mass, geometry, gains, limit values or self-collision changes.
Full512-world paired PPO benchmark now passes:24 disposable updates /393,216
transitions, original saved weights/optimizer and fixed random seed restored
between baseline/parallel/parallel/baseline blocks. First2 updates per block
excluded from timing. Median full rollout+GAE+PPO update15.234s baseline vs
12.001s parallel (ratio0.788). All recorded tensors/parameters finite and solver
validation passes. This is on the local4060 laptop, not an L4 measurement or
a literal zero-additional-instructions claim. No measurable whole-training
slowdown in this bounded workload; do not extrapolate a guaranteed21% speedup.
ContactTransferEngine now selects the parallel implementation when the existing
floor-aware flag is enabled. Scalar guard remains a diagnostic reference.
Tests/evidence: floor-recovery/guard-parallel-unit.json, parallel-policy.json,
parallel-ppo-benchmark.json. Tested source package3eb712705f4d (6,601,954bytes)
is persisted in S3 and independently readback verified. Production constructor
path and direct ancestor FK tests pass (<6.7e-7m error versus CPU geometry);
recovery reset/termination regressions pass. Pod b97r8nr7eo4mc1 confirmed EXITED
after publishing code. Cloud restart remains prohibited pending new instruction.
Original and final local checkpoint ZIPs remain preserved.

## October17 — user STOP: overhead rejected

User explicitly rejected the floor guard's training overhead and ordered the run
stopped. Stop requested for20261017_154335_uefn_equipment_floor_recovery_opt_512;
normal final-checkpoint save and owned exit billing watcher remain active.
DO NOT resume or allocate GPU without a new user instruction. The measured
3.1–3.3s/update versus1.8s was unacceptable; resuming despite this measurement
was a mistake. Any replacement must demonstrate acceptable end-to-end overhead
before a paid training launch; isolated kernel timings are insufficient.
The guard remains opt-in in the prepared configuration, so DO NOT launch that
package accidentally. Keep the locally downloaded study checkpoint intact.

Confirmed stopped15:49:16 Warsaw: pod b97r8nr7eo4mc1 desiredStatus=EXITED,
GPU compute released, retained disk preserved. Final19510 /319,668,224 samples,
SHA0b5774d06420, persistent S3 readback verified and downloaded locally as
Saved/MimicKitEquipment/floor-recovery-stopped-latest.zip. No failure file.
Receipt floor-recovery-user-stop.json. Original317.7M study zip also retained.

## October17 — floor-aware limit corrections and get-up-end resets

User requested cheap floor clipping repair, reset recovery rows at get-up end,
and local download of the latest checkpoint before continuation. Gracefully
stopped run20261017_145946 at19389_final /317,685,760 samples. Persistent S3
readback and local SHA6289ef4c1d51 verified. Study checkpoint:
Saved/MimicKitEquipment/floor-recovery-study-checkpoint.zip. Keep this file.
Old exit watcher suspended only during supervised handoff; billing guards remain.

Opt-in engine flag transfer_floor_aware_projection adds a GPU-only geometric
check around the existing split angular-limit position correction, which runs
after the contact velocity solve. If that correction pushes any sphere/capsule/
box through the horizontal floor, backtrack its generalized-position displacement
to the last floor-feasible fraction. No root lift, velocity change, new gains,
torque caps, angular-limit values or self-collision changes. Clear proposals are
bit-identical. Blocked corrections are deferred: this is a unilateral step guard,
not a new simultaneous contact/limit position solver and not proof of Jolt parity.
Only this equipment engine config opts in; unrelated training/Unreal unchanged.

Matched frozen-policy back-get-up start at16/30s: peak foot penetration5.681cm
before ->0.439cm with guard. Separate initial foot penetrations existed before
physics (front example2.749cm). Precomputed reset-only leg IK now lifts clipped
feet while preserving foot XY/orientation, hips, pole, root and upper body/hands.
Front92/back62 foot-frame corrections, max4.475/4.535cm. Targets remain unchanged.
Both already-hand-cleaned source banks preserved; new *_reset_floor_ik.pkl used.
Final matched32-world off/on tests show all four starts clear at reset to3um;
guarded peak during motion <=4.38mm. This residual contact/integration penetration
is NOT fixed by the angular correction guard. Early pose failures still occur;
no recovery-success claim. Exact cases/results: floor-recovery/*.json.

Guard tests:1024 randomized cases across actual compound hinge/free rig and
ball/free fixture; FK error<3.5e-7m; new floor violation<1.9e-7m; clear poses
bit-identical; CUDA capture/replay exact.512-world physics/PPO smoke and20-row
evaluation pass. Matched projection microbenchmark on laptop adds about0.84ms
per512-world physics substep; not a measured whole-L4-training percentage.
No CPU copies or allocations on the live substep path. Offline IK has zero
per-step cost. Full source/evidence package is persisted before continuation.

reset_at_getup_end=true: recovery rows retain the final authored get-up target
on their last tick and then TIME/reset (or existing FAIL if tracking failed).
They no longer transition to idle. Ordinary idle rows unchanged. Sampling excludes
the final source frame to avoid empty episodes;1us endpoint tolerance prevents a
float32-extra tick. Auto-phase feedback input and authored get-up clock unchanged.
Consequently aggregate episode seconds will shorten by design; not comparable
to the previous get-up-plus10s-idle-tail curve. Tests retain old opt-in transition
behavior and verify new end-reset/termination priority.

Initial continuation run20261017_153656_uefn_equipment_floor_recovery_512
restored317,685,760 samples, optimizer and normalizer. First new checkpoint19390
SHAe71abb43c9ce was stream-readback verified in persistent S3.20-row local replay
and TB8035/replayer8021 verified; three captured recovery rows reach clip-end
TIME/reset with no idle tail (another still fails tracking early). Backup/live
verification receipts are floor-recovery-first-backup.json and
floor-recovery-live-verification.json. Hard billing stop17:37:00 Warsaw;
165s final-save reserve. New exit watcher replaced the suspended old watcher.

Measured L4 update cost initially3.16s versus prior1.79s: substantial overhead,
not negligible. Local block-size sweep preserves all geometry/capture checks;
64-thread launch reduces the randomized actual-rig guard from about2.3ms to1.2ms.
Only launch block size changes, no altered correction/physics algorithm. A
supervised latest-checkpoint handoff applies this optimization while retaining
the17:37 deadline. Explicit64-vs256 launch test produces bit-identical accepted
qpos on all1024 randomized cases. Subsequent isolated timings vary with laptop
load (1.2–1.8ms); do not treat these as exact L4 throughput predictions.

Optimized continuation20261017_154335_uefn_equipment_floor_recovery_opt_512
resumed19455_final /318,767,104 samples (SHA0a5afa0178b0). That intermediate
handoff is also locally verified as floor-recovery-optimization-checkpoint.zip;
the originally requested317.7M study checkpoint remains untouched. Source
591f4a02c831 persisted/readback verified. PID1121, exit watcher1122, bridge6904,
dashboard15528. Hard stop17:37:05 Warsaw (same minute; five seconds handoff
overhead), training deadline17:34:20 with final-save reserve. Optimizer and
normalizer restored; first update succeeds. Final verification receipt:
floor-recovery-optimized-verification.json.

First optimized checkpoint19456 SHA c0ff47cd08af verified by persistent stream
readback; confirmed advancing through19466 /318,947,328 samples without failure.
Early full L4 measurement remains3.26s/update versus prior1.79s (~82% longer,
~45% fewer transitions/s). The isolated kernel scheduling improvement has NOT
demonstrated an end-to-end training speed improvement. Floor clipping mitigation
is verified but the requested cheapness is not achieved; retain this limitation
prominently rather than describe the guard as negligible overhead.

## October17 — absolute get-up targets and idle-heading alignment

User requested latest-checkpoint continuation for two hours. During the authored
get-up only, all body targets retain fixed world positions instead of following
the simulated pelvis. At the exact switch to idle, pelvis-XY target following
resumes; target height and heading remain authored. Each whole get-up is rotated
once about world Z to match its final pelvis heading to the first frame of the
row's assigned idle (drawn/unarmed have slightly different headings). Root
translation, orientation, linear/angular velocities rotate together; local joint
coordinates, height, hand-only reset IK, phase rules, losses and termination
settings remain unchanged. COM velocity bands are computed in the rotated world
axes too. Replay records the same target tensors used by the loss/27cm check.
Local tests passed: 512 worlds, 32 physics ticks, one disposable PPO update,
20-row replay, both idle headings/front-back combinations, fixed get-up targets
and exact-boundary return to pelvis-XY following. Runtime116.7s. Floor/pose/
27cm/timeout regression test passed. Test report: recovery-preflight/report.json.
No change to main ProjectJournal, Unreal assets or other cloud pods.

Latest checkpoint18889_final /309,493,760 samples SHA4fb2d5092cb1 verified
by persistent readback and downloaded locally as absolute-recovery-resume-latest.zip.
Previous trainer completed gracefully. Same pod b97r8nr7eo4mc1, source
2b5c5038a836, new run20261017_145946_uefn_equipment_absolute_recovery_512
launched14:59:54 Warsaw, PID736, exit watcher737; old watcher retired.
Fresh two-hour hard stop16:59:52 Warsaw (Unix1792249192.067905), including
165s final-save reserve. Existing local/remote deadline guards updated.
Bridge23088 and dashboard2764 verified live; 20-row replay and TB published.
First new checkpoint18890 SHA884a13363095 verified by S3 readback, then
independently downloaded/hash-checked locally (absolute-recovery-first-verified.zip).
Advancement confirmed through local update68 /310,624,256 samples; no failure
or backup-error files at verification. Actual replay checks confirm absolute
rotated get-up root targets within1e-5m and exact pelvis-XY following after idle
transition in all four captured front/back/equipment combinations. Receipts:
absolute-recovery-first-backup.json and absolute-recovery-replay-verification.json.
Detailed receipt: Saved/MimicKitEquipment/absolute-recovery-handoff.json.


## October17 — user-requested persistent-storage cleanup

Deleted seven explicitly verified disposable cache files,2,163,975,624 bytes
(2.16GB decimal). Four historical processed-animation caches have their format
markers verified from bounded object reads; three superseded Warp compilation
archives are excluded from current runtime manifests. All model checkpoints,
UE5 exports, source animations, latest equipment/crawl backups and current
runtime/kernel caches retained. Eighteen distinct checkpoints referenced by
current installed UE5 contracts/pickers hash-verified locally before cleanup.
No pods stopped/deleted or training modified. Each deletion confirmed404.
Exact inventory/plan/receipt and protected-model manifest:
Saved/MimicKitEquipment/storage-audit-20261017/. Cloud receipt:
mimickit/storage-cleanup/20261017-safe-cache-cleanup.json (readback verified).
Inspection was scoped; unclassified older environments/assets were retained.

## October17 — user authorizes verified 284M backup; resume recovery for two hours

Latest user explicitly abandoned waiting for inaccessible latest and authorized
resuming verified checkpoint17362 /284,475,392 samples on available L4, within
the existing two-hour <=$0.59/hour budget. Old-host recovery heartbeat PAUSED.
Preserve stopped old pod/disk; do not automatically retry it. Prepared recovery
curriculum and hand-only IK unchanged. Verify first new checkpoint in persistent
storage before further updates; failed backups stop trainer and billing. Each
save also waits for prior upload, preventing unverified checkpoint accumulation.
This supersedes all no-fallback/no-new-pod instructions below.

Replacement L4 b97r8nr7eo4mc1 allocated at $0.59/hour; two-hour hard billing
stop Unix1792245706.0179138 (16:01:46 Warsaw), training reserves165 seconds
for final evaluation/save. Old o095ir9r3mkpda remains stopped and retained;
its local control files are preserved in Saved/MimicKitEquipment/retained-old-host.
Source7d552c52835a5a7452f944138b5bfa8eedc5772ccc1640b2364c855edcf46c6d
verified in persistent storage. Runtime restored from cache, no reinstall.
Fallback17362 SHA d4969070cf38a0e8fe5f594836136e69ab8671142e07688b08719332b05f89df
verified locally, S3 readback and on new host. Launched
20261017_140400_uefn_equipment_recovery_512 at14:04:41 Warsaw, PID501,
failure-exit watcher502, local billing guard25624 and remote deadline guard.
Bridge1404 and dashboard5956 started. Verified advancement through local update34
(global17397),285,048,832 samples, no failure/backup-error files. Resume receipt
confirms optimizer and normalizer restored with fresh physical episodes.
Actual row assignment193 walk/288 run,25 recovery/6 ordinary idle; weighted
40/60 sampling rounds by motion allocation, adaptive allocation disabled.
First new checkpoint17363 independently read back from S3 and saved locally as
recovery-first-verified-checkpoint.zip; SHA
f7478af3c0ac6f0c393dc1ee449e8b7a736dd6652332a6a2bac56832483f8b5c.
Receipt recovery-first-verified-receipt.json; training proceeded only after its
background uploader readback completed. First20-row replay6.14MB transferring
through existing2MiB/30s telemetry chunks. Transfer and local replay conversion
now complete (last_batch_rollout.json present); TB comparison publishing.
Injected upload failure test confirms error recording/propagation; scoped billing
stop tests pass. Checkpoint cadence/retention unchanged; first upload verified
synchronously, subsequent uploads background with no queue accumulation past next save.

### Previous latest-only request (superseded)

Latest user correction explicitly says resume training. Recover latest >=19846,
verify locally and in persistent storage, then launch prepared recovery setup
for the approved two-hour window at <=$0.59/hour. No older fallback. One-minute
heartbeat retries host availability and continues through successful launch.
This supersedes the recovery-only/stay-stopped instructions below. Preserve
retained disk; no new pod allocation. Use existing scoped runtime guards and
backup-failure stop handling. Do not leave an accessible paid pod idle on failure.

### Earlier recovery-only instruction (superseded by correction above)

User now explicitly requests retrieving latest and one-minute scheduled retries
if unavailable. This supersedes the earlier prohibition on retrying host access,
but does not authorize restarting training or renting a replacement GPU.
CPU-only podResume retried and rejected for insufficient host memory; exact pod
o095ir9r3mkpda independently remains EXITED. Retained disk is preserved.
Heartbeat recover-latest-equipment-checkpoint is ACTIVE every minute in this chat.
Bounded retrieval/verification/stop instructions are saved in
Saved/MimicKitEquipment/checkpoint-recovery-instructions.txt. On access, download
latest >=19846, verify locally and by S3 readback, stop pod, then pause heartbeat.
No new GPU, no training, no deletion of fallback or retained disk.

### Previous handoff — hand IK passes; latest still on retained disk

User explicitly chose "Keep latest; leave training stopped" after the host
restart failed. Do not substitute older checkpoint17362, rent a replacement,
retry launches or create a monitor without a new instruction (now supplied above). Preserve stopped
pod o095ir9r3mkpda and its retained disk holding the believed latest19846
(~325M samples). Latest is NOT yet downloaded or verified. The accessible
backup17362 has284,475,392 samples; retained locally and in persistent storage.

Recovery hand-only reset correction PASSED the512-world physical preflight,
32-tick rollout, disposable PPO update, phase/reset contract checks and20-row
noiseless capture. No solver error or invalid tensors. Evidence report.json in
Saved/MimicKitEquipment/recovery-preflight (88.57s; fallback17362 used only for
local tests). Test episode average250.014 ticks is aggregate, NOT a claim of
successful get-up learning. Geometric checks confirm exact unchanged root/
lower body and preserved hand orientation; IK is precomputed, reset-only.
Preview refreshed with a checked "Hand IK starting poses" toggle.

Code/config/IK reset libraries persisted and SHA-readback verified:
mimickit/pipeline_20261014/uefn-equipment/source_33221d7e1da4.zip,
SHA33221d7e1da4c3ec8c74656f3342dda14c219280679501f8aaaa05f5e28574a6.
REST start rejected (host GPU unavailable). GraphQL gpuCount0 also rejected;
explicit computeType CPU rejected for insufficient host memory. Owned pod
independently confirmed EXITED, retained volume unchanged. No paid replacement
allocated, no new timer/guard started, no GPU spending this turn.

### Preparation and earlier failed preflight (resolved by hand IK)

User approved the preview, edited front once more, and authorized resuming for
two hours. Latest front SHA64db68a4ca4d289472f60516dfa8bfbb60a91729b9aefe8304917e2543cbdf17
is retargeted with the same native projection and independent foot correction.
Both clips now pass that foot solve; front max added-penetration correction
0.103cm, back0.909cm. Original authored floor penetration and recorded PHAT
excursions remain disclosed, not silently clamped. Preview folder is refreshed.

Requested allocation implemented in opt-in recovery_omni.py:31 idle rows,
25 recovery/6 ordinary;192 walk/289 run; adaptive allocation removed. Recovery
starts use equal front/back selection and uniform authored-frame sampling.
Auto-phase feeds the next tick's input; get-up target retains authored clock;
after get-up, idle reference follows the previous tick's prediction. Recovery
rows retain pose-error/27cm failure and10s timeout, allowing floor contact.
No network/input-size, learned-weight, optimizer, noise or loss-weight change.
Current PHAT assets included in candidate package, not yet deployed.

Local512-world checks passed154 inputs/34 motors, exact row counts, fixed
membership, phase queue timing, clock independence during get-up and idle
handoff. Rollout buffers and disposable PPO update remained finite, but the
physics validator rejected recovery worlds3/8/16 with error7: more than four
contacts in one shape-pair manifold. Paid launch is HELD pending diagnosis;
this is not a successful physical preflight. No check suppressed, PHAT or
physics rule modified. Focused64-world capture reproduced failure on the first
tick: world35, back clip at0.1s. Saved GPU equation has a five-point manifold;
state/solved velocities remain finite. CPU collision query at that captured
pose measures right-hand collider penetration9.184cm, forearm2.692cm and
right foot2.644cm. Do not mislabel this as nonfinite PPO or merely roundoff.
Evidence: recovery-preflight/first-contact-failure.{json,npz}; CPU contact
count is not asserted identical to GPU contact count. Recovery-only termination
unit test passes: floor contact allowed, pose/27cm/timeout preserved, ordinary
rows unchanged. Physical preflight remains FAILED, not waived.

User rejected whole-body lifting and explicitly requested hand IK when a hand
clips. Implemented reset-only arm IK using the existing exact two-bone hinge
solver: fixed shoulder, preserved elbow pole, hand XY/orientation retained;
hand collider bottom lifted to floor plus1micrometre for float32 FK tolerance.
Root and lower-body generalized coordinates are byte-identical. Target PKLs
remain unchanged. Front34 hand/frame corrections(max6.710cm), back23(max12.578cm).
Prepared reset libraries are loaded once; no IK solve in training steps.
Preview now has "Hand IK starting poses" checkbox; unchecked shows actual target.
All geometric reach/orientation and physical512-world tests pass. See hand-ik-report.json,
prepare_recovery_hand_ik.py and recovery-preflight/hand-ik-test.log.
Owned pod o095ir9r3mkpda independently confirmed EXITED; no new GPU spending.

User explicitly authorized deleting all older MimicKit checkpoints except the
resume source. Deleted1654 cloud checkpoint ZIPs/30,168,827,431 bytes; preserved
other chat's crawl runs and all code/log/replay data. Receipt and exact inventory:
Saved/MimicKitEquipment/checkpoint-cleanup-{receipt,inventory}.json. Verified
cloud fallback17362 is retained locally and remotely. Latest actual19846 is
believed retained on the stopped owned pod, but NOT yet downloaded/verified;
old run's volume-full errors prevented uploads after17362. Recover19846 before
resuming; never silently substitute fallback17362. Prepared resume_recovery.py
starts only this pod with immediate two-hour guard and preserves latest before
removing fallback. No start/publish stage has run. Candidate train.py now stops
on a failed durable backup at the next PPO boundary so the existing exit watcher
can end billing; checkpoint cadence/retention for the new run is unchanged.

## Earlier October17 — initial get-up preview (superseded above)

Latest user instruction supersedes immediate two-hour resume: retarget and show
the newly edited getUp_front_quick.fbx / getUp_back_quick.fbx first, then train.
Owned equipment pod o095ir9r3mkpda confirmed EXITED. No restart/rental or policy,
training config, normalizer, checkpoint, sampling or observer changes made.

Requested next experiment (NOT implemented/launched): keep6% idle rows;80% of
those start at a random frame anywhere in either get-up, front/back equally.
For these rows disable failure termination. During recovery, the target/MSE
follows the get-up's authored clock; predicted next-tick phase feeds input only.
At the end switch target to idle, with the predicted phase controlling its
next-tick reference/MSE as well as input. Preserve the one-tick timing of the
phase output. Keep episode timeout as stated to user; remaining ordinary idle
and locomotion rows keep normal behavior. User authorized two hours but now
requires preview before launch. Do not substitute an idle target during get-up.

Fresh FBX imports: front SHA b441efef21cc1d45d60a97f04981b1d9a57ec2a3ed2583fb2cbd5b852f014f3f,
47frames/30Hz/1.533s; back SHA96b892aba2b1e98a1b3a6564ec304864bc9c31415717e6db28030f3846b3f8c2,
43frames/30Hz/1.4s. Autodesk SDK round-trip maximum position error<3e-5cm,
orientation<7e-12rad. Existing native UEFN anchor projection and handedness
conversion to current15-body/34-DOF rig. No PHAT edits, limit clamps or scaling.
Back uses existing independent pole-preserving foot correction (54 foot frames,
maximum lift0.909cm). Front's frame7 left leg cannot reach the requested lift
without changing the existing solve; whole front preview is explicitly pure
projection, no foot correction. Maximum added front penetration1.031mm right,
0.779mm left. Authored PHAT foot geometry already intersects floor up to4.535cm
across these clips; this was not erased by the retarget.

Limit audit at16 subdivisions finds excursions: front torso/right upper arm/
left lower arm/left thigh; back torso/right upper arm/right thigh/right knee/
both ankles. These are reported, not silently fitted or certified for training.
Need resolve admissibility and preview review before paid training.

Preview: http://127.0.0.1:8843/Saved/MimicKitEquipment/recovery-preview/
Orange retarget; optional blue authored PHAT overlay, independent playback and
scrubbing. Browser render verified. Evidence, imported FBXs/BVHs and candidate
PKLs in that folder; report.json records caveats/source hashes. Reproducible
helper Labs/MimicKitTraining/prepare_recovery_starts.py: convert with Stepper
SDK Python310, prepare with Saved/Robotics/env/Scripts/python.exe.

## October17 — locomotion retarget verified against latest upper-body PHAT

User requested reretargeting while preserving the lower body. Reran all54
equipment references with the existing sources/cuts/foot-lift method and the
current exported model. Fresh Unreal export exactly matches canonical source;
editor state preserved. All54 files are byte-identical to the previous motions,
including pelvis, legs, upper body and phase metadata. The retarget does not
clamp to joint limits, so the expansion changes allowed physics motion rather
than reference poses. Dense current-limit audit passes6,512,884 samples with
the existing5% margin. Current canonical model/limits already contain the new
PHAT. No training restart, cloud deployment, sampling or exclusion changes.
Evidence: Saved/MimicKitUEFN/upperbody-retarget-20261017/verification.json.
See Docs/MimicKitUEFNBodyMatching.md for exact PHAT provenance and method.

## October 17 — user shortened current run to one hour remaining

At 08:35:30 Warsaw, user requested stopping the current run in one hour.
Applied reloadable hard deadline Unix1792222530.6748135, **09:35:30 Warsaw**,
to owned pod o095ir9r3mkpda on both remote and local controls; this supersedes
the earlier 14:56 deadline. Trainer stops 165 s earlier for final evaluation,
checkpoint save/upload. Trainer446, remote guard120, exit watcher447 and local
guard9776 confirmed alive. No restart or training-setting changes.

## October 17 — second regression: forward running lost, walks retained

User flagged another test spike/drop. Saved evaluation 16,562 -> 16,662:
5.938 -> 0.798 s, but tracking loss only 2.344 -> 2.372. No failure or
numerical/solver-warning file. Engine/env/agent configs and normalizer tensors
are byte/value identical across those checkpoints. Do not call this run stable
just because tensors remain finite or its average loss improves.

Repeated local frozen comparison on the SAME 50 motions × four phases, current
caps/physics, zero noise/adaptation/updates: 16,562 mean 9.003 s, 163/200 finish
10 seconds; 16,662 mean 7.889 s, 150/200 finish. Running mean 8.231 -> 5.807 s,
walking 9.693 -> 9.794 s, idle 10 s throughout. Run F unarmed 9.250 -> 0.342 s;
Run F drawn 7.425 -> 0.333 s. Forward variants regress most; most other motions
retain their behavior. The episode-count weighted chart greatly amplifies this
specific failure because failed forward rows repeatedly restart.

Prospective one-update audit from peak 16,562: same 512-world rollout, saved
motion assignments and actor/critic momentum, fixed normalizer, identical
minibatches, standard 32 rollout ticks and 40 actor optimizer steps. Only actor
LR varied in disposable local copies. At 1e-4: mean old/new Gaussian KL 0.1285,
p95 0.2587, final minibatch clipping fraction 69.1%, physical action shift RMS
0.02731 rad/s. At 3e-5: mean KL 0.02571, p95 0.04688, clipping fraction 40.3%,
RMS 0.01222 rad/s. This measures substantially more conservative updates; it
does NOT replay the historical collapse or establish long-run retention.
No actor-LR, checkpoint, sampling, physics, deadline or observer changes were
made to the paid run. A controlled continuation from 16,562 at smaller actor
LR is a candidate next test, not an already-proven fix.

Evidence: Saved/MimicKitEquipment/torque-regression/new_16562_16662.json,
second-remote-summary.json, ppo-update.json; standalone audit helper
Labs/MimicKitTraining/diagnose_ppo_update.py. Only two additional model snapshots
and the peak's optimizer state downloaded (~38.7 MB compressed); no second
cloud workload or local training continuation. Local diagnostic jobs finished.

## October 17 — torque-run regression investigated without changing training

User reported the test-duration drop. The current run's saved tests are
15,662: 1.17 s; 15,762: 2.76 s; 15,862: 0.45 s; 15,962: 0.53 s;
16,062: 0.67 s. Actual training tracking losses jump between updates 15,802
and 15,812, before the large adaptive reallocation at 15,818. No numerical
failure was recorded. Engine/environment/agent configs and all normalization
tensors are identical between 15,762 and 15,862; learned weights changed.

Local frozen-policy comparison: 50 admitted motions × four identical phases,
no noise, learning or adaptive sampling, current physics/caps, 10-second horizon.
Checkpoint 15,661: mean 6.762 s, 111/200 finish; 15,762: 7.966 s, 147/200;
15,862: 4.252 s, 69/200. Running-only means fall 5.866 -> 1.494 s;
walking 9.897 -> 6.531 s; idles remain 10 s. All 131 later failures exceed
the 27 cm deviation allowance; the furthest point is a foot in 116 cases.
On identical initial observations, action change RMS is 1.137 rad/s, largest
at knees and ankle axes. This establishes genuine learned-policy regression.

Torque-only counterfactual keeps current velocity-command bounds and changes
only caps back to their original values. At two seconds, the good policy has
144/200 survivors with old caps versus 174 with new; the later policy has
65 versus 97. Reverting motor caps does not recover the lost capability.
The current caps improve both policies in this bounded comparison.

Chart caveat: upstream ReturnTracker averages every completed episode, so
short-failing rows contribute repeatedly while long episodes finish once.
Adaptive row counts also vary. The raw chart exaggerates this drop relative
to equal-start testing, and repeats each test value until the next 100-update
evaluation. No dashboard metric was silently redefined.

Exact intervening gradient/update causality is NOT established: there is no
per-update model or gradient history. High PPO clip fractions (~50–67%) already
existed before this restart, so they alone do not prove the cause. Smaller
updates from 15,762 are a possible next controlled test, not a proven fix.
No live weights, LR, caps, sampling, deadline, or training processes changed.
Tests and compact reports: Labs/MimicKitTraining/diagnose_torque_regression.py,
Saved/MimicKitEquipment/torque-regression/{summary,new_15661_15762_15862,
old_15762_15862}.json. Only two model snapshots were downloaded (25.8 MB).
Initial diagnostic setup typo (joint conversion called on the character model
instead of the motion library) was corrected before any measured rollout.
The run and its backups remain active; prior stronger checkpoint is preserved.

## October17 — validated leg torque caps; eight-hour resume launched

Current run20261017_065748_uefn_equipment_velocity_512, same Secure L4 pod
o095ir9r3mkpda at$0.59/hour. Fresh eight-hour allocation window started
Unix1792212963.3014052; hard stop1792241763.3014052 (14:56:03 Warsaw), with
165s reserved for final evaluation/backup. Trainer446, exit watcher447,
remote deadline guard120 and reused local guard9776. Source backup
mimickit/pipeline_20261014/uefn-equipment/source_ed4eba2a16c7.zip verified
SHAed4eba2a16c7e53ad4d74606eacc28056a17bac42848c3e4e5e2e38d382637b5,
6,507,537bytes, including measurement/verification evidence. Restored cached
runtime; only this owned GPU was restarted. Observers14980/14816 publish the
chronological06-57-48 TensorBoard run and20-row deterministic replay.
Verified live at update 15,672 / 256,786,432 samples, about 6,231 transitions/s.
Trainer and guards are alive; no failure/numerical-failure report. Live gains match
the original exactly and all torque caps match the validated envelope. First
checkpoint 15,662 is uploaded and readback-verified: 35,871,116 bytes,
SHA256 32d117f7b0c6c3bb704bfecc19d3322b3a385ed2d6d94f84a73cb1bd3ea91285.
TensorBoard has the chronological 06-57-48 run. First converted replay received
at 07:01 Warsaw: 20 deterministic rows, actual training targets included.

Latest steering: user ended further demand scanning and requested implementation
plus verification against the latest Unreal wrist PHAT. Preserved1,576 completed
reference starts spanning all50 clips (the unfinished tail was drawn idle).
No further command search. Raising only axes whose measured demand exceeds
their old cap, to measured peak*1.05; adequate caps remain unchanged. This affects
the14 leg axes only. These are measured demands of found tracking commands,
not a mathematical minimum or a promise of sustained policy success.

Read-only fresh Unreal export Saved/MimicKitEquipment/current-live-rig.json
matches the complete current source-rig.json exactly, including saved asset hashes.
Both wrists already have60/45/90degree twist/swing2/swing1 limits. Training archive,
local physics files and audit snapshot agree byte-for-byte. No PHAT edit, save,
rebuild or retarget is needed; user dirty assets and editor session preserved.
Receipt:current-phat-receipt.json. The initially empty wrist receipt was a report
filter using numeric child indices as names; corrected using body-name mapping.

Finite-cap check passes15 distinct saved starts including each raised axis's
peak-demand case and forward/backward controls. Maximum position difference
versus uncapped commands0.097mm, no numerical errors and no cap saturation.
Restoring each individual old cap worsens tracking at its supporting case.
The first right-knee peak331.15Nm was NOT justified by this comparison: clipping
that particular command improved its error. Sixteen existing high-demand knee
cases were replayed without another search. Highest supported demand305.862Nm
gives321.155Nm with5% room, not the initial347.708Nm proposal. Full evidence in
calibration_all/{axis_probe,envelope,verification}.json. Adequate upper-body caps
stay unchanged (a margin alone crossing an adequate cap does not raise it).
The CPU-model validation initially read only actuator caps; hinges instead store
their cap on the scalar joint. Fixed the independent check to honor both storage
forms; actual motor and Newton-model caps already agreed. No physics workaround.

512-world checkpoint restore and three disposable PPO updates pass with the new
caps: every checkpoint tensor equal before updates, optimizer/normalizer/counters
restored from15661/256,606,208 samples, finite rollout/parameters and solver check.
Gains unchanged; physical exploration remains0.314159rad/s (normalized sigma.05).
The existing command-bound formula automatically reserves the new torque/gain
headroom; action normalization and learned outputs are not rescaled. Local check
49.96s, updates10.10/6.20/6.37s including first-use setup, not an L4 benchmark.
The cap overrides are applied once before solver construction, with no new
physics-step computation. Reports:torque-limit-check/report.json and
one_tick/calibration_all/envelope.json. These checks preceded the live resume above.

User authorized finishing the torque investigation, increasing only supported
per-axis caps with 5% margin, then resuming the latest checkpoint for a new
eight-hour window at the existing $0.59/hour ceiling. Gains stay unchanged.
Stopped prior locomotion run20261017_060504_uefn_equipment_velocity_512 using
stop.request. Exit guard completed saving and pod o095ir9r3mkpda was EXITED
before the new eight-hour allocation above.
Final15661 verified from persistent storage and downloaded to
Saved/MimicKitEquipment/torque-resume-checkpoint.zip:36,043,295bytes,
SHA3943adb561767b8de8c89edc222db20987db49278ba75c224a833d6e6192a6bf.
S3 key ends runs/20261017_060504_uefn_equipment_velocity_512/checkpoint_0015661_final.zip.

The local reference-state torque scan was stopped at the user's request after
1,576 starts; its completed measurements are preserved. Named torque-cap support
and the validated caps are now deployed, as recorded above.
This work does not touch the other chat's separate crawl pod or its assets.

## October17 — unchanged-motor resume requested; torque calibration deferred

User reports longer running episodes and asks to resume with the CURRENT limits.
Stop further torque calibration. The interrupted local audit is no longer running;
partial calibration_all/progress.json is incomplete evidence, not an approved
motor envelope. Experimental torque helper files remain standalone. Reverted the
unpublished hooks in train.py/uefn_engine.py and verified their exact bytes and
all packaged runtime files against the existing source53e01c707017. No torque
override was put in prepared configs, deployed or trained.

Prior run ended normally at checkpoint15265 final, verified S3 key
mimickit/pipeline_20261014/runs/20261017_045927_uefn_equipment_velocity_512/checkpoint_0015265_final.zip,
37,324,662bytes,SHA d599637e5c6276fb9427e5a56cd48fcfeb3bb6ed37dfaaba420f0defca9fad29.
Pod o095ir9r3mkpda confirmed EXITED. User's resume continues the last eight-hour
limit; this interpretation and$0.59/hour ceiling were stated in commentary.
Same pod restart accepted, hard stop1792238602.9531512 (includes setup), local
guard9776, remote guard108. Cached runtime restored and verified; no second GPU.
Run20261017_060504_uefn_equipment_velocity_512 launched with keep-deadline,
trainer366/exit guard367. Resumed15265 final with250,118,144 prior samples;
optimizer and normalizer restored, no new inputs. First update15266 completed,
250,134,528 samples; live torque/gain arrays match the original values exactly
(hips200Nm,knees150Nm,ankles90Nm; gains50/50/40). Physical noise remains
.3141593rad/s and the previously expanded command bounds remain active.
No failure or numerical-failure file. Observers29236/10424 publish the06-05-04
chronological TensorBoard run and20-row deterministic replay. First TB data
arrived; initial replay still pending at this check. Both UI servers respond.
Hard stop14:03:22 Warsaw; trainer reserves165s for final evaluation/backup.
Compiled-kernel cache saving to persistent storage to avoid repeated startup
compilation on another restart; no additional GPU workload.
Follow-up: advancing15276/250,298,368 samples,~5431 transitions/s; first resumed
checkpoint15266 readback-verified,35,982,220bytes,SHA
95a04b7f0ebe077d72445ddd38775d7f82c3b9b4810fd6562a8539a175c0d982.
Kernel cache43,293,523bytes saved and readback-verified at
mimickit/runtime/warp_0c107a856e57c7b0.tar.gz. Remote20-row replay is6,558,751bytes;
the unchanged bounded2MiB telemetry bridge is delivering it incrementally.
Final local check:15316/250,953,728 samples advancing, no failure file,
20-row replay fully converted and available in the8021 replayer; TB events live.

## October17 — per-axis torque envelope calibration (deferred)

User now authorizes increasing ONLY insufficient torque limits to measured need
plus5%, preserving existing higher limits. Gains remain unchanged. Local
one_tick_motor_audit.py --torque-calibration lifts caps temporarily in the
isolated diagnostic, optimizes next-frame commands, and measures actual substep
torque. Saved/MimicKitMotorAudit/one_tick/calibration retains its evidence.
These peaks are demands of found commands, not a proven global minimum or a
certificate of exact reference feasibility. Broader motion coverage and replay
with the proposed finite envelope are required before promoting any caps.
No production changes or additional cloud rental/time authorized so far.

## October17 — Run F next-tick motor diagnosis (local only)

User requested reference pose/velocity starts and next-tick feasibility tests,
without interrupting the improved live run. Added
Labs/MimicKitTraining/one_tick_motor_audit.py. Evidence is in
Saved/MimicKitMotorAudit/one_tick/{report,summary,solutions,rollout}.json.
Downloaded one verified checkpoint,14895/244,056,064 samples,36,235,027 bytes,
SHA cb41b91c50f503ece0dae96f567834eb91cd06301e97f9d22aaf23b63b169134.
The immutable original source snapshot supplies identical physics/assets/motions;
current pipeline code supplies the widened command limits. No cloud diagnostic
job, learning update, production gain/cap change, PHAT or Unreal edit.

48 distinct reference starts:16 phases each Run F Unarmed/Drawn,8 each Run B/LR
Unarmed. Initialize pose AND velocity; free pelvis, gravity, contacts and joint
limits remain active. Optimize a constant34-axis velocity command over one
1/30s policy tick/eight1/240s physics steps. Four comparisons keep exactly the
same command limits:current motors,2x gains,2x torque caps,both2x. Twelve bounded
finite-difference/local-search iterations per case. The objective equals the
current four tracking errors plus flat COM band; auto-phase excluded because
it does not affect motor feasibility. Residual reconstruction checked against
actual env loss terms. Delivered torque/cap saturation measured every substep.
All192 final cases finite with no physics-error flag;215s local runtime.

Across32 forward starts, optimized mean tracking cost:
current2.463e-1;gain2x2.484e-1;torque2x2.022e-1;both2x2.084e-1.
Thus gain alone provides no useful improvement;2x torque reduces this cost17.9%.
This mostly improves velocity tracking, not a dramatic pose correction:current
mean maximum-body position error is about2.25cm after a single tick. Some hip
axes reach200Nm and ankle axes90Nm throughout the tick even after optimizing
commands. These caps restrict near-reference tracking. This is NOT a proof
that exact reference tracking is physically possible or that twice the caps
is the minimum necessary/sufficient setting. Search failures are not an
impossibility certificate. Repeated equal starts have finite solver variation:
largest initial across-copy cost spread1.51e-2 in a gain2x case; preserve this
evidence rather than claiming exact deterministic optimization.

Separate frozen-policy check:4 initial phases per motion, same checkpoint,
no automatic resets; observe until first task failure or3s.64 trajectories.
Across8 Run F starts, mean time to failure is0.404s current,0.271s gain2x,
0.517s torque2x,0.317s both2x. Current maximum0.600s versus0.933s torque2x.
All8 still fail with doubled torque. Both backward and LR controls finish3s
from all4 starts with current or torque2x motors;gain2x breaks those controls
(backward0.867–1.200s,LR0.767–1.033s). No numerical error in captured trajectories.
The frozen-policy comparison measures immediate effects, not potential learning
after retraining. It does NOT prove torque is the sole cause or that current
gains are globally optimal. Conclusion:raising gains is unsupported;torque
headroom helps but does not by itself repair this policy. Exact required caps
and sustained Run F feasibility remain unproven. No production tuning applied.

Live training checked advancing at15085/247,169,024 samples,~5742 transitions/s,
unchanged existing06:00:22 Warsaw billing deadline and05:57:37 trainer stop.
No extension or new rental authorized by this diagnostic request.

## October17 — wider velocity commands; latest-checkpoint training resumed

User requested command limits at the required values plus5%, then resume.
Each motor now permits max(previous bound,1.05*(reference peak speed+torque cap/gain)).
The extra cap/gain permits full motor torque at the animation's peak speed;
gains, torque caps, PHAT and motions are unchanged. Right/left knee command bounds
20.5919/19.7145rad/s, previously6.2832. Existing bounds are never reduced.
Opt-in env_config velocity_command_margin=.05; calculated once from all loaded
motion frames and actual motors, before constructing the agent. No physics-step work.

Checkpoint action normalization, network and optimizer are preserved. Output1 still
means6.2832rad/s; Gaussian sigma.05 still means.314159rad/s. This linear Gaussian
output CAN exceed1. The Omni PPO action-bound penalty now obtains the legal interval
from physical bounds through the loaded normalizer instead of assuming[-1,1].
Its coefficient10 and every other learning setting remain unchanged. No output-layer
rescaling, altered exploration or optimizer migration. New checkpoints include the
computed velocity_command_bounds.json. Historical checkpoints remain immutable.

Local verification: old limits reproduce the old penalty exactly; legal new commands
have zero penalty and illegal commands have gradients pointing inward. Full512-world
restore is tensor-for-tensor equal to checkpoint14194 before updates. Three disposable
PPO updates passed finite-state/solver checks, without saving a new policy. Evidence
Saved/MimicKitEquipment/command-limit-check/report.json. These are wiring checks,
not evidence of newly learned forward running. Paid pod o095ir9r3mkpda restart
accepted at$0.59/h; retain existing October17 06:00:22 Warsaw deadline
(Unix1792209622.2040958), guards and durable backups. Run
20261017_045927_uefn_equipment_velocity_512 launched from14194/232,570,880 samples;
first completed update14195/232,587,264. Live report confirms the preserved action
scale6.2831855, physical noise.3141593, right-knee normalized bound3.27730155.
No failure/numerical-warning files in that initial check. Deadline guard108,
exit guard388, trainer387; existing local deadline guard remains active.
Bridge20580/dashboard3620; TensorBoard sees the chronological04-59-27 run.

Source53e01c707017a9f79942113ab38da91253242d4723ff5de6f6e2ba464492f02a
is readback-verified on persistent storage (command-limit-source-receipt.json).
Current Saved/MimicKitEquipment/source.zip and packaged env config updated;
original source moved to Saved/MimicKitMotorAudit/source.zip, whose existing
snapshot retains the old motions/config for reproducible diagnostics.
The stopped pod retained its checkpoint and data but lost /opt runtime. Cached
runtime restored; its existing dangling venv symlink caused the generic restore
to stop after successful extraction. Verified archive/existing target, reused
the link, restored kernel cache and verified CUDA imports; no reinstall, source
physics change or new GPU rental. Initial custom-kernel compilation completed.
Verified advancing through14215/232,914,944 samples (~3.013s/update), no failure
or solver-warning files. First new checkpoint0014195.zip readback-verified in
persistent storage,35,906,505bytes,SHA36ce554e6a6d833801bda8d46ffb0f71bb9da7e5fcbc5ed963b7dc085451355b.
The local bridge delivered TensorBoard events and the first complete replay;
debug/last_batch_rollout.json exists for the new run at05:04 Warsaw. Existing
bounded2MiB telemetry chunks retained;~8.90MB total telemetry downloaded at that check.
Receipt command-limit-live-verification.json retains exact live values. This
confirms a healthy resume, not that forward-running capability is solved.

## October17 — local motor authority evidence; paid training remains stopped

Isolated diagnostics in Labs/MimicKitTraining/motor_audit.py,
motor_dynamics_audit.py and motor_search.py. Inputs are the hash-checked stopped
run source.zip plus latest-stopped.zip and its exact packaged motions. Snapshot
Saved/MimicKitMotorAudit/source is immutable. RTX4060 local diagnostics only;
no pod restart, optimizer update, production gain/cap/config or Unreal change.

The simple joint-velocity-plus-pose follower passed only4/200 six-second
clip/phase cases (all unarmed idle). It also failed backward running, so its
failures MUST NOT be called evidence of weak motors. A floating-root inverse-
dynamics screen includes unilateral foot forces/friction and minimizes required
motor-cap multiplier. Exact forward AND backward reference acceleration failed
root-support feasibility in the initial sample; exact kinematic replay is a
stricter requirement than this task's tracking tolerance. The screen also does
not enforce contact complementarity/acceleration or limit reactions and is not
a dynamic proof. A bounded whole-body feedback controller likewise failed the
backward positive control; not promoted as a strength test.

Actual frozen-policy positive control, original motors and +/-2pi commands:
all4 phases each of backward and LR run survive6s (8/8); forward phases fail
at .233/.233/.200/.267s. Widening only the command clamp, preserving actor weights
and saved action normalizer, gives the same survival results. No claim that
changing the clamp alone repairs the already-trained actor.

Independent bounded command search (frozen policy + optimized torso/leg velocity
offsets, real240Hz engine,30Hz commands, free root) finds a forward phase-zero
ONE-SECOND witness with original gains/caps and expanded command range. Physical
pelvis travels4.16m over the recorded .967s, height .822..932m. Repeating the
candidate across256 worlds gives peak target-distance .201..258m, below .27m.
There is finite solver/history variation between identical starts, recorded
rather than hidden. This is NOT an all-phase, long-duration, learned-policy or
Jolt-transfer success. Evidence: policy_stock.json, policy_reference.json,
search_forward.json/.npz, reference_k15.json under Saved/MimicKitMotorAudit.

Full frozen-policy check,50 clips x4 phases x6 seconds:157/200 pass.37 clips pass
all4 phases;3 more pass3/4 (Walk F Unarmed, Run LR_offset Drawn, Walk FR Drawn).
All40 cases belonging to the10 forward-run variants fail. No numerical solver
errors during any measured first episode. One FR Unarmed world reports an error
at tick106, long AFTER its first failure at tick6; this excluded post-termination
tail is explicitly recorded. The first all-world script had rejected the whole
batch due to such tails; policy_all_checked.json now records first-error timing
and never counts an affected measured episode as a pass. Production is untouched.

Matched bounded command search (same method, seed,256 candidates,8 iterations
per .2s extension): original +/-2pi commands fail around.533s,0/256 identical
candidate repeats survive the attempted.6s. With per-axis range
max(reference speed)+torque_cap/gain, original gains/caps complete1s in256/256
repeats, peak collider-target distance .167..210m. Delivered torque never exceeds
the existing caps (maximum cap ratio1.0 at physics-substep samples). Source files
search_forward_stock and search_forward_matched. The earlier unconstrained-prefix
extension did NOT demonstrate2s (0/256 repeats, first failure~1.77s). The separate
prefix-preserving search_forward_windowed also failed: stopped expanding at1.8s,
final repeat first fails at1.60s;0/256 pass; recorded row0 has zero solver warnings
and zero motor/contact residual metrics. All local jobs exited normally. Do not
imply long-run success from the one-second witness. No stronger motor settings
were selected, and no all-motion capability certification has been established.

Inverse-screen validation: static gravity force767.677N for78.2545kg; mass matrix
positive definite; synthesized support/torque equilibrium reconstructs; negative
ground-normal support rejected. FK mapping maximum spatial error.134mm from the
deployed float32 hinge conversion. Exact reference support failure is not proof
of motor weakness: learned backward running passes with tracking deviations.

Proposed command-envelope.json is READ-ONLY evidence, not an applied setting.
Knee bounds with full torque headroom:19.611/18.776rad/s versus current6.283.
Before any resumed wider-range training, reconcile the saved action normalizer,
environment action space and PPO action-bound penalty. Upstream base_agent.py
hard-codes normalized bounds[-1,1], active weight10. Merely widening the physical
clamp while retaining old normalization would still penalize useful faster
commands. Any migration must explicitly preserve/check physical means and noise;
no such production migration or paid restart has been performed.

Local comparison viewer: http://127.0.0.1:8843/Saved/MimicKitMotorAudit/ (existing
local server, no added service), generated by motor_audit_viewer.py. Real collider
geometry and captured actual training targets; orange physical, magenta target.
No animation or transform is substituted for physics. Raw results and compact
summary.json retain failed evidence. Current pod o095ir9r3mkpda rechecked EXITED.

## October17 — user stopped training before motor feasibility audit

User requested stopping current training to establish whether torque/gain and
velocity control can achieve the animations. Root stop.request saved/stopped at
iteration14194,232,570,880 samples. Final evaluated checkpoint readback-verified
in persistent volume aj7d2jzwuq and downloaded to Saved/MimicKitEquipment/
latest-stopped.zip (single reusable latest artifact, not an extra checkpoint set).
Key mimickit/pipeline_20261014/runs/20261017_025027_uefn_equipment_velocity_512/
checkpoint_0014194_final.zip;36,861,235 bytes;
SHA a62bbefc3f4aca001518d0bd73b52769e8f8046aeff70cd5d720a5a65dee6b7f.
Matches persistent latest_verified.json, local archive CRC passes. Unique exit
telemetry preserved by exit watcher as exit_evidence_7dba4a09143c.zip. Runpod API
confirms owned pod o095ir9r3mkpda EXITED: GPU billing stopped. Pod volume retained;
no delete, rental, restart or spending extension. Local active_run.json marked
stopped with final samples/key. Receipts motor-audit-stop-request.json and
motor-audit-stopped.json; latest-stopped.json updated. Training MUST NOT restart
until the requested control-feasibility issue is resolved and user directs it.

Proposed next diagnostic, not yet implemented/run: an independent reference
follower using the exact deployed body/contacts/limits/motors, policy commands
held at30Hz with240Hz physics. Initialize from motion poses/velocities, then
leave root and joints physical: no root forces, teleporting, contact pinning or
kinematic enforcement. Test all50 clips/multiple initial phases over full cycles.
Record per-joint demanded/delivered torque, command clipping, angular-speed error,
position/orientation drift and contacts. Separate command-range inadequacy from
insufficient gain and actual torque-cap saturation. A contact-aware inverse-
dynamics calculation can screen torque feasibility, but must enforce floating-
root balance, unilateral support and friction; motor-only or unconstrained inverse
results are not proof of a physically realizable gait. Verify any candidate by
forward simulation in the actual engine. A failed tracker alone does not prove
insufficient strength; inspect controller/contact/reference failures separately.
For the present velocity law, required command at desired end speed is roughly
qdot_target + torque_required/gain. Thus just covering reference peak speed is
insufficient: controller torque headroom is also needed. Preserve all actual
gains/caps/PHAT until a specific supported change is chosen; do not silently
retune production training to make a diagnostic pass.


## October17 — forward-run stall: velocity command range mismatch confirmed

User requested diagnosis without stopping the active run. Read-only live report
history through60/iteration13970: ten forward run clips still100% early-failure
(227,323/227,323 completed episodes in reports51..60). Approximate lifetime from
allocated-world exposure .2311s early, .2374s previous window, .2412s latest;
these are estimates, with evaluation/assignment caveats above. Exact noiseless
checkpoint14085 captures: F Unarmed .233s, F Drawn .267s, FR Unarmed .200s,
FL Unarmed .267s. No meaningful forward recovery. The earlier replay's terminal
collider-centre errors reconstruct >.27m at a foot, with pelvis falling from
~.89m to~.73-.75m; initial body pose matches the recorded reference.

Confirmed control limitation inherited from vanilla CharEnv: every velocity
action is bounded +/-2*pi rad/s, and _apply_action hard-clamps to this range.
Frozen checkpoint action normalizer also has std=2*pi for all34 motors. This
was not adapted to the UEFN motion velocities. Forward references have knee
peaks15.2..16.6rad/s (Unarmed F family), versus command6.283rad/s; ankles also
reach12..14rad/s. Each forward knee exceeds the command bound for~48..66% of
sampled cycle states. Motor rule tau=clip(gain*(command-end_speed),+/-cap),
knee gain50/torque150Nm, means that at reference speed the motor unavoidably
brakes at full cap for~32..41% of those knee samples, even with the best allowed
command. This is a COMMAND cap, not a hard physical angular-speed cap: inertia,
contacts or coupled motion may carry the limb faster, against motor braking.
Backward/lateral references are also not wholly within range but less demanding:
backward knees exceed cap~13..18% of cycle, full-brake~0..5%; lateral full-brake0%.
Forward translation ~5.0m/s, backward~3.0m/s, lateral~3.5m/s, so success on the
other directions is not proof that forward control authority is sufficient.

CPU-only audit on the pod (CUDA_VISIBLE_DEVICES empty, one Torch thread) checked
all50 deployed motion clips and frozen actor on256 evenly spaced reference
states each. Reference world linear/angular velocities match finite-difference
interpolation derivatives: maximum3.43e-3m/s and2.43e-3rad/s. No normalized input
clipping in these fixtures. Commands are correct per previous full input audit.
Reference-state actor knee means sit near the bound for32..43% of forward phases.
Separate checkpoint14085 archive audit reconstructs actual replay observations
from saved rigid transforms/velocities and evaluates the matching frozen actor:
F Unarmed right knee exceeds command cap2/6 interior ticks; F Drawn1/7. Other
failed samples FR/FL have no knee command clipping. Thus the range restriction
is a real mismatch/strong contributor candidate, NOT proven sole cause of every
failure. No widened-range physical A/B or fine-tuning was performed, so do not
promise that raising it alone fixes forward running. Reconstructed rotations
agree within1.21e-6 matrix components; phase within1.29e-6. Commands are recomputed
from matching checkpoint, not directly saved action tensors.

Evidence under Saved/MimicKitEquipment: forward-latest-reports.json,
forward_reference_audit.py, forward-reference-audit.json,
forward_recorded_actions.py, forward-recorded-actions.json (checkpoint14085,
model SHA inside). Small CPU diagnostics copied to owned pod root; no new GPU
process, training/config/data/model mutation, restart, extra rental or extension.
Recommended next controlled experiment: expand available joint velocity command
range to cover motion requirements with controller headroom, keep physical gains,
torque caps, PHAT and targets unchanged. Treat action normalization/checkpoint
mapping deliberately: changing scale silently multiplies existing outputs/noise;
a resume must preserve physical commands and clearly define exploration changes.
User has not yet authorized this training/control change in this diagnostic turn.


## October17 — falling episode chart investigated; no training changes

Read-only inspection of adaptive reports1..40 (12794..13571), local raw TB,
ReturnTracker and saved deterministic replay captures. Run still healthy at13605,
222,920,704 samples,2.852s/update; backup13585 readback verified, no failure files.
Evidence: Saved/MimicKitEquipment/adaptive-inspection.json and
adaptive-replay-comparison.json. No restart, tuning or extra GPU evaluation.

The chart is a completed-episode mean, not an equal-motion performance score.
Ten forward Run variants (F,F_L_20,F_R_20,FL,FR, both equipment states) received
150/512 worlds in the original stratified allocation; adaptive reports increase
these to210 first report,230 at10,250 at20,255 at40. Report40 has97.12% of its
completed episodes from these ten clips. They remain100% early failures.
TB previous final train length19.97194ticks=.666s (preceding20.65ticks=.688s);
current13.55ticks=.452s. More agents on fast-failing clips explains the dominant
aggregate decrease. Other clips improving also loses their failure multiplier,
so the share assigned to the persistently failing clips rises further.

Approximate exposure/completion estimate for those ten clips is.231s over
reports3..12 versus.237s over31..40: no worsening of their short lifetime.
This uses previous desired row counts and PPO iteration deltas; delayed
assignment and forced evaluation resets make it an estimate, not measured
per-clip episode durations. Do not treat reconstructed fixed-mixture values
as exact metrics. In the same windows, non-forward-run completed-episode failure
fraction drops67.9% to20.8%; walk failures3.05% to2.25%, idle0%.
These group rates still have changing internal mixtures.

Saved noiseless clips at12174..12574 versus13185..13385 agree qualitatively:
walks/backward runs mostly retain10s, forward runs remain~.17-.35s. Several
lateral captures improve (Drawn LR1.33s mean to10s, Drawn LR_offset1.93s to10s),
but Unarmed LR has one worse capture (3.08s prior mean to.23s). Samples are sparse
and start phases differ; not a controlled same-start policy comparison and not
proof every motion improves. There is no evidence of a broad collapse from this
chart. The unresolved training issue is the stalled forward-run family despite
extra allocation. Recommendation: fixed-mixture or per-motion episode reporting
for progress comparison; retain actual training-mixture chart separately.


## October17 — adaptive fixed-row allocation active

User authorized any early-failed motion to receive up to3x sampling weight,
keeping fixed motion assignments and rebalancing from one-minute reports.
New adaptive_rows.py counts completed TRAIN episodes before reset clears flags,
with per-world training provenance to exclude evaluation and forced resets.
Every60 wall-clock seconds, at the next PPO update boundary, multiplier is
1+2*(failed/completed) per clip. No observations keeps its preceding multiplier.
This is capped1..3 and recalculated, never compounded. Existing run3:walk1 base
weights stay;31/512 dedicated idle rows stay. Each admitted clip retains at
least one row. Largest-remainder quotas minimize reassignment; the desired
assignment only takes effect on the next reset, never midway through a rollout.
No new physics passes, evaluation passes or per-step GPU readback. Two GPU
scatter-add counters per nonempty training reset; one tiny CPU report/minute.

Checkpoint state saves allocation, counters, multipliers and remaining report
interval; evaluation does not affect these. adaptive_rows.json is latest report,
jsonl retains compact reports; archives preserve both and code. Telemetry syncs
latest report only. CPU tests cover failures/timeouts, mode transitions, no
repeated multiplier escalation, no mid-episode mutation, minimum coverage,
minimal churn, state restore and100 distributions for the actual50-clip pool.
Resume targets20261017_025027_uefn_equipment_velocity_512 from latest final
checkpoint. Owned pod and06:00:22 Warsaw deadline unchanged. Source
ce212b22640f5caa7456279e6239657f61f2a522e5a68497019f716cfe454640
readback-verified in persistent storage; adaptive-rows-* receipts under
Saved/MimicKitEquipment. GPU preflight runs only after old trainer exits.
Preflight passed on L4:512 worlds,31 idle, genuine OmniWalkEnv reset override
with parent reset mocked verifies counts before done-clear, no double counts,
evaluation exclusion and no active-motion mutation. Bookkeeping benchmark
279.66us/full512-row reset,8.95ms/32-step PPO update worst case (~0.3% of
previous~3s update); not literally zero overhead. Old final12784 verified
SHA40d4ce8e8db1e12a60bc6a25ebe7fe17920eaa492c6b8a8c92a9f52c4a9e41f8.
New trainer2030/exit watcher2031; bridge22380/dashboard7032.
Live verification: first report6937 completed/failures,109 desired row changes;
second report21495 completed/21112 failures,27 further changes; target allocation
31 idle/70 walk/411 run. All50 clips retained. State12825 /210,141,184 samples,
no failure markers, recent update2.8907s. First new checkpoint12785 readback
verified SHAa09946a30fdcc2537ed72b0c626fa57c6b17a031b4de3e9c514362277c1dc507.
Replayer12785 fully synced and selected in browser:20 rows,10 Unarmed/10
Drawn by recorded equipment metadata and clip names; sorted idle/walk/run.
TensorBoard new dated run publishing; old bridge finished and old dashboard
processes19332/4088 retired. Evidence adaptive-rows-live*.json. First report may
cover fewer active training seconds because initialization/evaluation also take
wall-clock time; only completed training episodes enter the report. Report
elapsed_seconds records actual wall time; no-data clips retain their multiplier.



## October17 — replay row menu order

MimicKit row picker sorts idle, walk, then run; within each gait, matching
motion names are paired Unarmed then Drawn. Recorded row IDs and payload arrays
remain untouched. Previous/next row buttons follow the visible menu order and
wrap around. This is local viewer-only; no training or capture selection changes.

## October17 01:56 — transient loss increase inspected, training left running

User noticed loss jump. Read live pod status and local raw TensorBoard events:
iteration11624 total2.90275,11634 total3.02824 with critic loss7.72496,
11644 total3.47759; falls to3.07681 by11744. Position/linear/angular/rotation
terms rose together. Latest noiseless evaluation11674 episode mean17.17916
policy ticks versus18.62611 previously, so not only a chart artifact.
This is a real temporary performance regression; critic error spike is correlated,
not established root cause. No new solver warnings since11158 (four total), no
failure file, process1363 still advancing, latest11674 backup verified. Observation
normalizer metrics unchanged. Viewer handedness fix is local rendering only,
no deployed training mutations. No stop, restart or tuning made for this check.

## October17 — viewer handedness corrected (display only)

Replayer viewer.html now uses a left-handed camera projection for UEFN omni
captures (task uefn_omni_absolute_walk), shared by solid geometry, magenta
targets, guides and spheres. Orbit horizontal drag follows the same convention;
pan uses the corrected camera right vector. Stock MimicKit projection unchanged.
This converts handedness at projection without changing recorded body transforms,
collider axes, loss values or live training. Existing saved captures are corrected
on page reload. Input-comparison/viewer.js reflects each complete posed geometry
group on Y, retaining regular/Strafe panel placement. No runtime/source bundle,
training process, physics or dataset mutations. Verified actual served replayer
loads capture11174 Run BR Drawn at frame83 with original losses and targets.

## October17 — drawn hand appearance: handedness conversion diagnosed

User spotted apparently left-handed sword posture in Run BR Drawn, replay11174
row11 frame83. Named right hand is correctly the quieter hand at every stage:
raw UE torso-relative span8.03cm right /35.58cm left; packaged FK7.07/36.89cm;
exact replay median20-frame spans target7.04/36.75cm, agent9.89/42.10cm.
Mappings right_hand->hand_r and left_hand->hand_l are intact; no sword input swap.

The spatial layout is mirrored in the right-handed display: exported rest pose
right-minus-left shoulder is -X, actual foot-to-toe forward is +Y, up +Z.
Normalized cross(right,forward).up=-1. Asset+90Z, motion-90Z and replay(x,z,-y)
are all proper rotations and preserve that handedness. Earlier build.py/topic
statements identifying the source's forward as -Y are inconsistent with the
actual rest toe geometry. This is a coordinate-convention/display diagnosis,
NOT evidence that the policy chose the wrong named arm. Do not swap arm labels
or silently rebuild the dataset/physics to hide it. No training, renderer,
PHAT or motion changes made during diagnosis. Evidence handedness-audit.json
in Saved/MimicKitEquipment. A display conversion must handle positions AND
orientation/geometry consistently; training/UE round-trip implications need to
remain explicit if changing anything deeper than rendering.

## October17 — final deployed input audit passed

Read-only CPU check on the owned pod, using its actual deployed modules, current
checkpoint and reference FK physical-state fixtures. No training pause, optimizer
steps, physics rollout or injection into the live trainer. All512 fixed assignments
pass FULL DeepMimic->Omni observation assembly (not a stub physical observation),
including a reordered subset.154 inputs:146 physical, then gait at146,
direction XY147:149, sword-drawn149, arms150:152, phase cosine/sine152:154.
50 active clips have50 distinct gait/direction/equipment combinations. Manifest
equipment/gait agree with filenames; current allocation31 idle/120 walk/361 run,
255 unarmed/257 drawn. Both arms intentionally enabled; injury behavior untrained.

Actual checkpoint normalizer maps sword0/1 to approximately-0.99586/+1.00416;
all command values within2.539 standard deviations, below clipping at10. Current
1024->1024->512 actor responds when only one command is changed while keeping
the same physical-state fixture: mean absolute normalized motor-output differences
gait3.514e-2, direction3.334e-2, sword2.402e-2, phase4.897e-2. This establishes
connected/non-ignored conditioning, NOT successful physical behavior.
Checked3,756 actual recorded phase frames: next-tick labels agree with current
phase plus1/30s /each clip's duration, max component discrepancy1.088e-5.
Deployed omni_walk.py, omni_policy.py, train.py, manifest and weights hashes all
match saved source.zip. Evidence/script: Saved/MimicKitEquipment/
final-input-check.json and final_input_check.py. This is reconstruction from
deployed code/checkpoint plus replay validation, not direct live-process tracing.

## October17 — replay equipment selection corrected

User observed almost exclusively unarmed rows. Confirmed replay10901 had18
unarmed locomotion rows plus one idle in EACH equipment state; row0 also had a
misleading generic walk label. Training allocation itself was255 unarmed /
257 drawn. The recorder walked world indices and took first distinct clips.
After fixed assignments, worlds were ordered by manifest, unarmed first;
rotating the starting WORLD by one per capture barely changed that bias.

observe_many.select_replay_worlds now balances equipment explicitly:20 rows
means10 unarmed/10 drawn, each with one idle and9 distinct locomotion examples.
Select evenly across each state's clip list and rotate by CLIP each capture;
rotate the representative world within each clip too. No RNG, environment
reset, training assignment, loss or extra physics steps. The same20-world
capture buffers and evaluation steps remain. CPU contracts verify the actual
ordered512-world fixture, both states,20 distinct clips, two idles, all50 clips
covered over24 captures, odd row counts, shortages and no duplicate worlds.
replay.py now gives row0 its actual motion_file name like the remaining rows.

Scoped save/resume targets20261017_011121_uefn_equipment_velocity_512. Current
source8d5e7ff5eda5ac3bbde05786ebec73cd768d2b0210150d3b882ce878d1478346
uploaded/readback-verified. Only runtime differences observe_many.py/replay.py.
The run3:walk1 allocation,50 active clips and06:00:22 Warsaw deadline are
unchanged. Receipts: Saved/MimicKitEquipment/replay-balance-*.
Checkpoint10973_final saved/readback-verified SHA
5d7cfecdb5c37d99a9346d03467050b1fe404b5c758bdacf6db4b2752d02d51c;
resumed with trainer1363/exit watcher1364 on the same owned pod. Local
bridge5144/dashboard19332 follow the new dated run. Handoff retains independent
deadline guards; old exit watcher retired only after replacement launched.
Live capture10974 verified20 rows:10 Unarmed/10 Drawn, one idle per state,
with both walks/runs and paired motion names represented. Training advanced
to10984 /179,978,240 samples without failure markers. First new checkpoint
readback-verified SHAe5f8939d25cfae01e7091c3b5a5eab2cf73311253ebd335ecd19bfff9b171e27.
Evidence: Saved/MimicKitEquipment/replay-balance-resume-verified.json.
Local replayer sync completed: converted10974 capture has exactly10 named
Unarmed/10 named Drawn rows; row0 correctly names the unarmed idle.

## October17 — temporary run:walk weight3:1

User requested running clips be three times as likely as walking clips, until
they ask to remove this bias. Set each run clip's motions.yaml weight to3 and
each walk/idle clip to1. Dedicated6% idle allocation remains unchanged. Actual
CPU check of row_motion_weights/fixed_motion_rows gives512 worlds:361 run,
120 walk,31 idle. Resets retain each world's assigned motion; no per-reset
resampling introduced. Both equipment states receive the same gait weighting.
All50 clips and reference values retained; Strafe BR/FL stay excluded. This is
a sampling/allocation change, NOT a loss multiplier. Local prepare_equipment.py
has temporary RUN_MOTION_WEIGHT=3; restore it to1 plus active motions.yaml when
the user asks to remove the bias. Do not alter other training settings then.

Prepared source c53a8536de4b3ec209ebd073c6b06076a0f515295b59470a1a025eee0a8833af
is readback-verified in persistent storage. Runtime diff is only
prepared/motions.yaml. Scoped latest-checkpoint handoff targets new dated run
20261017_003615_uefn_equipment_velocity_512, same owned pod and unchanged
October17 06:00:22 Warsaw deadline. Receipts/allocation evidence:
Saved/MimicKitEquipment/run-weight-{request,source-receipt,allocation}.json.
No new GPU allocation, budget or deadline extension.
Handoff complete: checkpoint10400_final uploaded/readback-verified SHA
33cb3f02203999bcdeda3deb6d9a20a032bcd42a9c68deeb285b59a19f817801.
New trainer1215 and exit watcher1216; local bridge17816/dashboard26140.
Weights, optimizer, normalizer and counters resumed; only fresh physical
episodes and the user-requested weighted assignments are initialized anew.
Full receipt: Saved/MimicKitEquipment/run-weight-handoff.json.
Resume confirmed170,409,984 prior samples and iteration offset10401 with optimizer
and normalizer restored. First update10401 reached170,426,368 samples, no failure
markers. Live motions.yaml verified weights idle1/walk1/run3. Old observer bridge
completed final sync before its dashboard was retired; new observers retained.
Verified advancing10411 /170,590,208 samples, no failure markers; checkpoint10401
readback-verified SHA730142f918a7bd62eb156413372c8abf69451242d8a8702302c9fa37c5f120f3.
All20 local replay rows arrived and TB lists the00-36-15 dated run. Receipt:
Saved/MimicKitEquipment/run-weight-resume-verified.json.

## October17 00:05 — regular BR/FL only, resumed latest checkpoint

User selected the regular Run BR/FL motions. Removed Strafe BR and Strafe FL
from active training membership in BOTH equipment states (four clips). Active
prepared manifest and motions.yaml now contain50 clips:2 idles,48 locomotion.
All50 gait/direction/equipment command combinations are distinct. Retained
motion files and phase offsets are unchanged. Local prepare_equipment.py applies
the same explicit exclusion on future preparations; source recordings retained.
512 worlds retain fixed per-motion assignments and6% idle allocation (31 worlds);
remaining481 worlds are apportioned over48 locomotion clips. No architecture,
input layout, reward, normalizer, controller or physics changes.

Scoped handoff saved checkpoint9854_final and verified its persistent upload:
SHA75b3a03b33640a0d6cf71decdad2f584e8aedf31e51fd1932e817f459a380364.
Run20261017_000451_uefn_equipment_velocity_512 resumes that latest checkpoint,
including optimizer/normalizer/counters. Trainer966, exit watcher967 on the same
owned pod o095ir9r3mkpda. Existing October17 06:00:22 Warsaw deadline unchanged.
Only old exit watcher was paused during the bounded handoff then retired;
independent deadline guards stayed active. Source bundle e19ab7eecd9780c5a1d0abf8fc5e6d4a75acbcfb2d7c0a4881b8bcb4f7ad93d6
was uploaded/readback-verified before handoff. Active dataset changes are only
the two membership files (excluded PKLs omitted from new archive, retained in
historical archives). Historical motions/manifest.json is an inactive earlier
26-clip provenance file, NOT the active prepared manifest.
Receipts: Saved/MimicKitEquipment/regular-only-{request,source-receipt,handoff}.json.
Local bridge26440/dashboard22012 use the new dated run; TB latest10 cap retained.
Verified resume reports161,464,320 prior samples, iteration offset9855, optimizer
and normalizer restored, no appended inputs. First resumed checkpoint9855 /
161,480,704 samples uploaded/readback-verified SHA
73aef20fbc0756ffc4fe7777bb28189b66a8bd10dbef2fb01d39e573666ea6dc.
No failure/numerical-failure/backup-error markers. Fresh replay is3.63MB.
TensorBoard lists the new00-04-51 run within its10-run cap. Old bridge finished
its final sync before old dashboard was retired. Verification receipt:
Saved/MimicKitEquipment/regular-only-resume-verified.json.
Subsequent telemetry confirms9865 /161,644,544 samples advancing. Local replayer
received and converted all20 rows; new dashboard scalar updates are publishing.

## October16 — live animation-input audit

Read-only audit of run20261016_223354: the actor receives154 floats, comprising
146 physical-state values and8 commands: gait(-1 idle/0 walk/1 run), fixed-world
direction XY, sword-drawn0/1, right/left arm-enabled1/1, phase cosine/sine.
No future target poses or clip identity. Global physical observations and command
directions use matching world axes. All54 motion files, manifest and omni_walk.py
hash-match the live deployment. Actual observation assembly passes every manifest
row and reordered subset indexing; existing phase wrap/next-tick contracts pass.
The live normalizer preserves varying gait/direction/equipment/phase signals
(none reaches its10-sigma clip); both arm flags normalize to0 because all arms
are intentionally enabled. This run has not learned injury conditioning.
Largest difference between commanded direction and recorded net horizontal
travel is1.46deg. Phase zero is the preparation heuristic of minimum left-foot
velocity along travel relative to pelvis; next-tick labels include each clip's
duration/offset and do not feed back into the clock.

Found four command-colliding pairs: regular versus Strafe Run BR and Run FL,
each unarmed/drawn. At the same normalized phase, with only pelvis XY aligned,
120-point CPU FK comparison gives mean/max body-position differences:
BR unarmed16.06/42.22cm; FL unarmed10.29/33.78cm; BR drawn15.40/42.24cm;
FL drawn0.10/0.47cm (this last pair is effectively redundant positionally).
Thus three pairs have materially different targets without an explicit command
selecting them. Physical observations differ and may identify an ongoing style;
the complete observation is NOT necessarily identical. This audit establishes
ambiguous target selection, not that it causes the observed learning failures.
No clips removed, input dimensions changed, or training interrupted pending user
choice about retaining these variants. Evidence: Saved/MimicKitEquipment/
input_audit.py, input-audit.json and input-audit-live.json. CPU checks only;
live checkpoint read on CPU, no extra training workload.

User-facing comparison: http://127.0.0.1:8843/Saved/MimicKitEquipment/input-comparison/
shows regular BR versus Strafe BR, with FL and equipment selectors, overlay,
pause/scrub/speed. Exported directly from packaged training PKLs through the
same MotionLib/FK and packaged XML collider geometry; both cycles synchronized
by the supplied phase offsets, pelvis XY removed only for in-place display.
No target/training data changed. Build/source/data/server PID receipt live in
Saved/MimicKitEquipment/input-comparison/. Verified visible in browser.

**TensorBoard display rule (restored October16):** port8035 must load only the
10 newest dated experiment directories, not the entire TensorBoardRuns root.
Launch Labs/MimicKitTraining/serve_tensorboard.py; it supplies an exact logdir_spec
and refreshes the server's selection when a new dated run appears. Older event
files remain intact. Current supervisor receipt is
Saved/MimicKitEquipment/tensorboard-process.json (limit10). This local display
change does not restart training, alter checkpoints or change dashboard writers.

## October16 22:33 — fixed motion assignments deployed and resumed

User explicitly requested agents reset on the same motion, with the existing
proportions. Equipment worlds now receive a fixed, weighted allocation at
construction: 31 idle rows and 481 locomotion rows for 512 agents. Existing
equal clip weights give 15/16 rows to the two idles and 9/10 to each of 52
locomotion clips. Assignment is deterministic for a fixed manifest/weights/world
count, including checkpoint resumes. Random phase sampling remains on each
reset. Failed agents, timed-out agents, full evaluation resets and asynchronous
subset resets all retain their clip. Arms, controller, physics, rewards, network,
normalization and optimizer are unchanged. No motion-switch curriculum added.

Only production runtime change: pipeline/omni_walk.py. Source bundle
7e3d148e1b3c22aa23375e13423f5ca19d6fc98d69c55033104b37a3d86cecac is uploaded
and SHA readback-verified on existing S3 storage. CPU contracts exercise actual
reset code with reordered/subset/repeated resets, immutable motion assignments,
random phases and disabled phase randomization. Isolated 512-world frozen-policy
physics smoke: 51,200 transitions, 3,908 reset events, fixed assignments after
every tick, unchanged policy/normalizer and valid physics. Evidence:
Saved/MimicKitEquipment/evaluation_audit/noise0.05_seed6741_fixed.json and
fixed-motion-allocation.json. Repeated short failures explain the large reset
count: hard clips can no longer be exchanged for easier clips. Completed-episode
mean can drop under this new sampling mix without a weight reset.

Same owned L4 o095ir9r3mkpda and unchanged October17 06:00:22 Warsaw hard stop.
Scoped handoff saved and verified checkpoint8319 final /136,314,880 samples,
SHA0941d2a5db2d50b2f7a1981be22d3fa39d3d700339d3517929bf66ee5d9489ee.
Run20261016_223354_uefn_equipment_velocity_512 launched with trainer596 and new
exit watcher597. Optimizer/normalizer restored; fresh physical episodes only.
Old exit watcher421 was paused for the transaction then retired; independent
deadline guards remained active. New checkpoint8320/136,331,264 samples is
readback-verified on S3, SHA
ff731c51debb77600a79c90ca75a6bc57509cbad95075c77ec4cce5d2e38c05c.
No failure/backup-error files; 20 replay rows exported (2.60MB). Local bridge27220
and dashboard22112 watch the new chronological run. Previous bridge completed its
final sync, and its dashboard was flushed before stopping, avoiding a historical
chart gap. Current-run/active-run receipts updated. Source and checkpoint receipt:
Saved/MimicKitEquipment/fixed-motion-handoff.json; live verification:
fixed-motion-resume-verified.json. No new GPU allocation or deadline extension.
Subsequent local telemetry confirms8330/136,495,104 samples advancing; the first
20-row replay has arrived and converted for the replayer, and TensorBoard is
publishing the new run. The initial post-startup rate was about4,844 transitions/s;
this short warmup sample is not a controlled performance comparison.

### Noiseless-versus-training investigation

The apparently worse evaluation mean was substantially a measurement effect.
Frozen checkpoint7714, exact archived physics, 512 identical initial physical
states/motions/phases: one completed attempt per world averaged 4.4460s without
noise versus 4.3847s with sigma0.05; 219 versus216 reached the10s timeout.
Stock short-window counting, which includes extra attempts from fast-failing
worlds, reported2.5607s/937episodes versus2.5582s/931episodes respectively.
With the same noiseless weights, extending observation from10s to30s increased
the all-completed mean to3.6114s; no learning or normalizer change occurred.
Thus the earlier4.27s training/2.61s evaluation figures were not an equal-window,
equal-attempt noise comparison. This test does not prove noise never matters.
Training previously also spent disproportionate frames on easy clips because
failed rows sampled new clips; the user-requested fixed assignments correct that
sampling issue. Evaluation metric definitions were NOT changed in this request.
Local audit used RTX4060/Torch2.11/Warp1.12.1, no cloud GPU competition or gameplay
changes. Both audited initial state arrays are byte-identical. The noisy report's
source hash was corrected to the validated archived source10ac15f04305: its final
report originally rehashed source.zip after the fixed-motion package was built,
but the process used the unchanged, separately extracted original runtime.

## October16 22:02 — user-authorized eight-hour continuation verified running

User requested resuming the same run for8h. Prior run ended with verified
checkpoint **7714 final**, SHA
707138897f23a91e7c4a1c98f7ae498bed2bbce3f5d0d1005a3cb1136b2897c0,
35,915,088bytes; downloaded and SHA-checked as latest-stopped.zip. Local observer
had stale6643 telemetry, but persistent latest_verified correctly held7714 final.
Prior pod nsvb0bg53dnc32 is EXITED; restart rejected because GPU was reassigned.
Replacement owned pod **o095ir9r3mkpda**, Secure L4 **$0.59/h**, allocated
22:00:22 Warsaw. Hard stop **October17 06:00:22 Warsaw**,
Unix1792209622.2040958. Eight-hour GPU ceiling$4.72 includes setup; do not extend
the deadline at launch. No new goal or scheduled automation. Existing independent
deadline/failure guards are required. Equipment deploy bound now admits the
explicitly approved28800s; other task deployment bounds unchanged.
Source10ac15f04305 matches current runtime exactly; no settings/physics/reward/
architecture change. Restoring the verified environment and compiled kernel cache.
Run **20261016_220202_uefn_equipment_velocity_512**, trainer420/exit guard421,
launched22:02 from7714 with --keep-deadline (no budget extension for setup).
Local deadline guard17020; observers bridge24508/dashboard10604. Replayer8021
responds. TensorBoard8035 was not running; restarted its local server, retaining
all chronological historical runs. Confirmed7725/126,582,784 samples advancing,
recent2.717s/update (~6,031 transitions/s). Optimizer/normalizer and126,402,560 prior
samples restored. First7715 checkpoint is readback-verified on persistent S3,
SHA17f190a12f4d7dcd657d10575dad2645c9f1b5293344e6d909a65331653058d2.
No failure, numerical-failure or backup-error file at verification. TB comparison
points are publishing;20-row7715 replay is present locally. Subsequent status7745/
126,910,464 samples confirms continued progress (~6,543 transitions/s).
Verified runtime/kernel cache restored; common GPU kernels load from
cache, but several custom solver modules are regenerated on this host. TensorBoard
HTTP200 confirmed after restart (server11392).

TensorBoard episode-length investigation after resume: the initial 0.2422s
point includes only the 554 episodes already completed during the first 32-tick
rollout (1.0667s); longer survivors are not counted until they finish. Fresh
physical episodes and a cleared ReturnTracker explain this startup sampling
bias, not reset weights. Subsequent points rise to 4.2236s. Upstream also clears
the tracker and resets environments after each 100-update output/evaluation,
which explains the repeated dips in the previous curve. No metric or training
semantics changed.

The historical x-axis gap was stale local telemetry: previous source events
ended at 108,855,296 samples although its verified final checkpoint reached
126,402,560. Restored the exact archived event file from SHA-verified
latest-stopped.zip after checking the local bytes were an identical prefix
(803,464 to 1,002,280 bytes). Historical dashboard deduplication appended 1,819
missing scalar points; its final episode point is now 126,386,176 samples,
4.2271s, immediately preceding the resumed run's 126,418,944 first point at the
normal logging cadence. Receipt:
Saved/MimicKitEquipment/restored-145703-tensorboard-history.json.
Live trainer and observers were left running unchanged.

## October16 14:57 — corrected solver continuation verified running

Owned Secure L4 **nsvb0bg53dnc32**, $0.59/hour, run
**20261016_145703_uefn_equipment_velocity_512**. Trainer447, exit guard448;
local deadline guard2532 plus remote deadline guard. Hard stop
**18:57:08 Warsaw**, Unix1792169828.1608927, fresh authorized4h. Live deadline
reserves165s for final evaluation/upload/shutdown. No scheduler created.
Observers bridge11628/dashboard24228;20 rows, existing8021 replayer/8035 TB.

Resume from **2322 final**, SHA
d59ad0cc917fbf895749bc722918d8c7f81af51081e2caddb6c1987139e909b3,
31,785,956bytes. Verified on persistent S3, downloaded to latest-stopped.zip and
independently verified on the replacement pod. Old fnl4fg2hm3tgsq is EXITED;
its restart failed because Runpod reassigned the GPU, so replacement was required.
No other paid workload started. Source **10ac15f04305** is SHA readback-verified
on S3 and exact runtime inventory verified before launch. Package differs only
in sequential_contact_adapter.py, new coupled_contact_gpu.py and uefn_package.py.
Network, optimizer, rewards, data, PHAT, targets and observer settings unchanged.
Verified advancing through **2363 /38,731,776 samples**, recent2.426s/update
(~6,753 transitions/s), finite losses and CUDA graph active. This is an observed
L4 rate, not a controlled speedup claim. Initial2323 checkpoint is readback-verified
on S3, SHA c78eb45828a7a132b7cfe52c52ef7ed31000e274747473102e06f6f358e4a6f9.
Resume receipt confirms optimizer/normalizer restored,38,060,032 prior samples;
only physical episodes restart. No failure/numerical-failure or solver-warning
file at verification.20 deterministic replay rows arrive locally;8021/8035 both
respond. New Warp cache3e20d7669df00954 (41.8MB) uploaded/readback-verified directly
from pod to persistent storage for subsequent restarts; no laptop payload.
Validation evidence bundle402951a7fa66 is also persisted. All required goal work
is now handled: hard captured solver cases fixed/tested without the rejected
cycle detector, tiny idle drift left as explicitly allowed, Unreal recordings
preserved, and corrected latest-checkpoint continuation actually advancing.
The remaining scalar safeguard is retained for unseen cases; no global
convergence guarantee is claimed. Billing/backup/failure guards remain active.

## October16 14:08 — user-requested resume; target-following unchanged

**Solver correction, verified locally; checkpoint handoff requested:** the 512-world noisy test
completed262,144 transitions/15,145 resets.31 hard solves used206 Newton steps
and656 scalar seed sweeps in total, with zero legacy fallback/warning. Captured
equation tests now pass all51 states, CUDA graph replay, preservation of unrelated
error codes and explicit NaN rejection. The NaN test caught a projection masking
invalid input; this was fixed before deployment. Production source is prepared
locally; stop.request now requests the unchanged trainer's final verified
checkpoint before the authorized fresh4h continuation.

Rejected the optional branch-cycle detector: it doubled physics time in the
paired PPO benchmark (2.320->4.699s/update). Removing it retained ordinary block
behavior and resolved all13 hard calls with zero scalar fallbacks; reference had
11 scalar fallbacks. Physics medians2.334->2.325s/update, whole update4.751->4.631s
are effectively neutral within laptop/Unreal variation, not a claimed speedup.
Final consolidated source also passes six disposable PPO updates per variant:
reference15 legacy fallbacks; corrected15 coupled solves/170 Newton steps/448
seed sweeps, zero legacy fallback. Median whole update4.931->4.871s, physics
2.319->2.365s; mixed paired round results and16–19% timing ranges show ordinary
variation, not evidence of a material speedup or regression. Package/default
engine/stale-source/invalid-PPO guards pass. Source10ac15f04305 is uploaded and
SHA readback-verified on persistent storage. Only the rare
failed block solves receive the new simultaneous solve; ordinary100-iteration
contact approximation is unchanged. No claim that every ordinary contact is
converged to an exact root, nor evidence linking its tiny residual to idle drift.
The original finite-warning scalar fallback remains a final safeguard; current
tests do not need it. Physics equations, PHAT, dataset and live-pelvis XY targets
are unchanged. No cycle-detection code is retained in the runtime.

User stopped training to inspect target foot sliding, then explicitly cancelled
further dataset/PHAT checks and requested immediate resume plus the ongoing solver
goal. Exact screenshot replay1301/row6/tick19->20 matches the training target to
7.15e-5cm: source right-foot motion0.171cm plus live-pelvis XY target shift2.116cm.
That large visible shift follows the previously requested live-pelvis target
anchoring. No reference-anchoring, dataset, PHAT, contact or reward change was made.

Previous run stopped safely at1456. Final archive SHA
4ae06ddf3338a40c913cd3eda2643426f5d14c1a356176add1bb393a989293d8,
29,795,319bytes, verified in S3 and Saved/MimicKitEquipment/latest-stopped.zip.
Old pod8dazc6h0elfeww is EXITED; its GPU was reassigned, confirmed by restart error.
Replacement **fnl4fg2hm3tgsq**, Secure L4 at$0.59/hour, runs
**20261016_140757_uefn_equipment_velocity_512**, trainer474/exitguard475, from1456.
Current deadline remains **17:40:30 Warsaw** (Unix1792165230.319209); the goal's
fresh four-hour continuation begins only after verified solver correction.
Runtime cache and unchanged sourceab70891e0b03 restored; remote source and resume
archive SHA verified. Local/remote billing guards installed. Initial deployment's
redundant source-backup request hit a transient connection reset AFTER setup;
existing identical S3 source was independently verified before launch.
Observers bridge28532/dashboard7348,20rows, same architecture/settings/counters.
Actual PPO confirmed beyond1847/30,277,632samples at~6.1k transitions/s; no second
cloud workload. Resume metadata restores optimizer/normalizer and prior23,871,488
samples, offset1457. This confirms progress, not just a launched process.

Independent solver experiments remain diagnostic-only in solver_idle_audit/.
Simultaneous Newton solves captured1274 from50 seed sweeps in5 iterations, matching
the long float64 reference within5.17e-6 velocity, but perturbation tests exposed
a stalled case; it has NOT been deployed. Branch cycling and incomplete contact
convergence checking remain the production issues under investigation. Idle
foot-origin net drift was roughly0.1–2mm over10s; user explicitly allows ignoring
that absent a clear bug. Original Unreal comparison assets remain present; current
user TestNN map and Play/work state were not changed.

**14:35 isolated solver progress (not deployed):** a safeguarded simultaneous
Newton solve retains the unchanged capped-motor, contact, friction and limit
equations. Failed Newton attempts are discarded; its independent scalar seed
continues advancing rather than accepting a stalled residual.206 CPU cases pass
(six saved failures plus200 perturbations); at most64 seed sweeps/36 Newton steps.
201 batched GPU perturbations match CPU impulses within1.16e-12; CUDA graph passes.
All51 physical states present in six saved captures pass fully device-side
assembly/solve, including active limits and repeated graph execution. Captured
1274 takes16 seed sweeps+9 Newton steps, final motor residual7.63e-6Nm and velocity
difference5.11e-6 from the long scalar reference. Isolated wall timings are noisy
with Unreal open; warm full candidate roughly11–49ms versus original290ms fallback.
Do not call the earlier4–6ms kernel-only measurement full cost or whole-PPO speedup.

Real64-world noisy rollout:8192 transitions/473 resets,13.29s measured simulation,
two candidate calls/eight Newton steps/32 seed sweeps, zero legacy fallback or
warning, no PPO or checkpoint writes.512-world longer test is in progress.
All code remains under ignored solver_idle_audit/, loaded only by its local test
process. Production, Jolt, user physics assets and cloud source unchanged.

Further acceptance audit: current block path tests motor branches, not complete
contact convergence.27/50 saved states accepted by that rule still change by
>2e-6 in an independent contact sweep. Four checked examples differ from the full
root by2.08e-4..1.29e-3 generalized velocity; supported-foot normal residuals about
1e-6..1.1e-5m/s. This is an incomplete convergence check, NOT proof that it causes
the user's tiny idle drift or a claim of large physical errors. Its handling and
performance must be assessed before promoting any solver correction.

## October16 13:40 — checkpoint1200 continuation and solver/idle audit

Current owned L4 **8dazc6h0elfeww**, $0.59/hour, is running
**20261016_134023_uefn_equipment_velocity_512** from verified checkpoint1200
(SHA bcdc88ccb7c80c379fbd63436ea59a65e0c7f4130197d4c32595f0c109bca07f).
User explicitly authorized this continuation for four hours while the slow
solver and apparent idle foot drift are diagnosed separately, then a corrected
continuation from the latest checkpoint for another four hours once verified.
Current deadline Unix1792165230.319209, **17:40:30 Warsaw**. Trainer465 and exit
guard466 are alive; actual PPO updates have advanced beyond the resumed checkpoint.
Original failed run and its red failure evidence remain intact. Source archive
ab70891e0b03, original 3,000 fallback budget with visible nonfatal finite-convergence
warnings; no physics/reward/optimizer change in this initial continuation.
Observers bridge24968/dashboard21996; requested20 rows. No extra GPU rented.

Audit evidence lives in `Saved/MimicKitEquipment/solver_idle_audit/`. Initial CPU
replay shows the main motor-branch solve cycles at the captured update1274 case,
even with400 inner contact sweeps; three ankle motor branches recur. Separately,
acceptance checks only motor-branch stability, which is not proof that contacts
have converged. These are diagnoses in progress, not fixes or a parity claim.
Production is left unchanged while independent equation/contact tests are built.
Unreal comparison recordings must be preserved; user work is not to be disturbed.

## October16 requested larger-network restart — failed; GPU stopped

**Current status:** stopped at12:23:46 Warsaw, update1274, before PPO: solver
error6 in world267. Runpod API independently confirms owned pod y2jz4d7bnx16w9
EXITED; GPU billing stopped. Latest verified checkpoint1200, SHA
bcdc88ccb7c80c379fbd63436ea59a65e0c7f4130197d4c32595f0c109bca07f.
Automatic exit guard preserved S3 exit_evidence_667ed618e37d.zip; downloaded and
SHA-checked in Saved/MimicKitEquipment/failure1274/. Exact equations retained.
Cause diagnosed below: insufficient iteration budget. Same residual thresholds
retained. Resume attempts failed for GPU capacity; no running allocation. Earlier rounding warning
at629/world276 was accepted and training continued as intended.

**User correction — finite convergence flags are nonfatal:** the user explicitly
rejected aborting the entire run on these numeric flags. Prior rounding-only
exception was too narrow. The proposed10,000 cap is REVERTED before deployment;
original3,000 cap and strict early-exit checks remain. If the budget expires with
finite velocities, impulses and residuals, retain that computed approximation,
count/report a convergence warning and continue. No agent reset, sample removal,
reward/optimizer change or claim that an unconverged solution is exact. NaN/Inf,
unsupported constraints, contact-buffer overflow and invalid PPO batches remain
fatal and trigger the existing GPU-stop guards. New GPU counters retain warning
counts and maximum iteration/motor/contact-limit residuals; logs, TensorBoard
health charts and an amber replayer line expose them. No per-step CPU copies.
Saved failure now warns with unchanged finite output within1e-6 absolute
comparison; tests at1/16/512/3000 sweeps all report their actual residuals without
abort. CUDA graph warning path passes; injected NaN and unsupported-contact9
remain errors. CPU validator emits each new warning count once; fatal flags still
raise. All four historical equation regressions also pass, max float64 difference8.02e-6.
Compile checks pass. Updated sourceab70891e0b03 is SHA-verified on S3; another
bounded L4 capacity request is in progress, still original14:01 deadline.

Measured original fallback on the local RTX4060 laptop, isolated saved problem:
100-pass cap median8.56ms;512 cap52.17ms;3,000 cap290.30ms;3,152 actual convergence
295.82ms. Five synchronized wall-clock measurements, excluding compile; variable
laptop/Unreal load, NOT L4 timing or whole-training overhead. This is expensive for
one difficult physics step. Ordinary block solve unchanged; this cost is not paid
by every agent or every step. Evidence failure1274/fallback-cost.json.

**Update1274 diagnosis/fix:** six active contacts, no joint-limit rows. The
captured problem remains slowly convergent even in float64; this is NOT the prior
rounding-floor case. At3000 sweeps, motor residual2.533e-3Nm exceeds existing2e-3.
The unchanged GPU solver exits normally at3152 sweeps with1.887e-3Nm. Increasing
its allowed cap to3200/4000/10000 produces exactly the same3152-sweep result.
Superseded candidate: rare fallback maximum3000→10000 only. Normal block path, early
exit, all error thresholds, physics and PPO unchanged. No residual is suppressed.
This removes the demonstrated insufficient iteration budget; it is not a guarantee
that arbitrary contact problems always converge. Saved-case/CUDA-graph and all four historical regressions pass. Continuation
being prepared from verified1200, preserving current1024→1024→512 architecture
and original14:01 deadline. Old stopped L4 capacity was reassigned; restart failed
with explicit insufficient-GPU error. Replacement within original budget rejected: no instances available. Earlier
stopped pod kdoqhqti1z2n0i also rejects restart for unavailable GPU. API reconciliation
confirms both owned pods EXITED and no replacement allocated. NO paid workload
running. Fix is ready to resume verified1200 when authorized capacity is available;
original14:01 deadline remains, no automatic restart/retry schedule installed.
Evidence: failure1274/{diagnosis,iteration-budget,reference-converged}.json.

User changed the continuation request to a fresh restart: **actor and critic
1024 → 1024 → 512**, fresh weights/optimizers/normalizers and zero counters.
Equipment conditioning, all six losses/scales, 512 worlds, 31 idle rows, live arms,
clock-driven phase, noise, physics and existing14:01:11 Warsaw deadline unchanged.
Historical1024→512→512 checkpoints remain loadable; no weight migration is attempted.

Old pod kdoqhqti1z2n0i is EXITED. After the verified shutdown test its GPU was
reassigned and restart explicitly failed for capacity. Replacement owned pod
**y2jz4d7bnx16w9**, Secure L4 at$0.59/hour, is inside the original four-hour budget
and original Unix1792152071.7139745 stop deadline. Runtime restored from cache;
confirmed-stop deadline guards deployed. Launch source97c9e917f29b is SHA-verified
in S3; current code/telemetry/journal backup key is in source-receipt.json.
Fresh production **20261016_112012_uefn_equipment_velocity_512**, trainer547,
exit guard548, launched11:20:21 Warsaw with NO resume argument. Observers bridge17268,
dashboard6536; datetime TB convention retained. Verified update50/835584samples,
~5986transitions/s, no failure/warning file at that check. Initial checkpoint0000000
SHAf05c298b4098c15e5dfb36ae8fc6fe5ac463a62044093aa5076848a9b673727f
verified on persistent volume. resume.json confirms prior_samples=0/iteration_offset=0.
Actual saved actor_net/critic_net both fc_1024_1024_512. Local replayer has20rows,
20actual target skeletons and all six per-tick losses. TB datetime11-20-12 exposes
all losses, episode durations, optimizer and throughput charts.
The20-row metadata made status repeat~455KB of per-frame/target details. Telemetry
now sends compact evaluation summaries, retaining full details once in replay.npz;
only the named SSH telemetry child was reconnected, trainer547 uninterrupted.
Verified live status size fell455240→1300bytes; iteration60 arrived correctly.
Chunk/replacement and unchanged-summary transfer tests pass.
Actual512-world/20-row preflight PASSED, including a disposable PPO update;
154inputs/34motors/2auto-phase outputs. Evaluation2.391s including capture,
20-row archive346969bytes, serialization0.0671s. These are total times, not an
isolated baseline overhead comparison. The recordings use the same batched test
rollout, no20extra simulations. This fresh preflight is not proof of long-run learning.
Latest final-sweep warning classification regression passed the captured failure
and all three historical fixtures; max difference from independent float64=8.02e-6.
Graph replay passes; unsupported-contact error9 still rejected.
Injected failure-receipt write error also verified to reach the billing-stop
finally block; early startup failures cannot bypass stopping due to missing run folder.

## October16 new equipment experiment — stopped; solver and billing guard correction

**Current override:** production failed on update132/world225 before PPO. Exact
first equations now preserved at `Saved/MimicKitEquipment/failure132/solver_failure.npz`
and S3 `failure_evidence_7dffcbdd376d.zip`. Checkpoint100 remains the latest verified.
The remote exit guard uploaded evidence but did NOT stop billing: its urllib
request is rejected with HTTP403/code1010, reproduced safely against the already
stopped pod. Local manual requests-based stop confirmed EXITED at10:37:57 Warsaw.
This describes the failed run; the replacement/restart authorization and current
status are above. Original14:01 deadline unchanged.
User explicitly requires no relaunch on an unexplained failure, confirmed stop on
failure, and warnings rather than whole-run aborts for harmless numerical misses.
Shared requests-based stop helper now retries until GET confirms the owned pod
EXITED; real idempotent API verification passes. Remote deadline/exit guards use
it, and local deadline guard also watches mirrored failures with30s evidence-save
grace. Future launch automatically installs an exit guard. Updates are now deployed on the replacement pod. The bounded rounding-warning
classification is documented below; physical parameters are unchanged.

Captured world225 is finite, two contacts, no active limits, motor residual1.07e-4
Nm. Independent float64 solve differs by4.35e-6 in generalized velocity. Local GPU
replay reproduces a3.09944e-6 iteration-change floor at512/3000/10000 sweeps;
strict2e-6 caused the abort. Contact normal speed error is below5.69e-7m/s.

New policy: keep strict convergence and the3000-sweep cap. If exhausted, accept
ONLY finite results whose final sweep change and contact/limit velocity residuals
fit `min(1e-4,max(2e-6,8*float32_epsilon*max(1,max_abs_velocity)))`, with original
motor residual<.002Nm still required. Count/report these as rounding warnings,
never silently clear them. Other failures remain fatal; manifold normal mismatch
now has separate error9 (previously ambiguously6). No motor/contact parameters,
NN optimizer/loss weights or Jolt code changed. Captured failure and three earlier
equation fixtures match independent float64 within8.02e-6; CUDA graph replay passes.
Insufficient1/16 sweeps and unsupported-contact error9 remain rejected.
Evidence: failure132/{gpu-diagnosis,gpu-warning-validation,warning-regressions}.json.

Real shutdown test also passed: intentionally failed owned subprocess automatically
caused RUNNING→EXITED, confirmed through independent API at11:04:51 Warsaw. Runtime
venv symlink needs cache restore after stopping (its /opt target is ephemeral).
Both requests-based deadline/exit guards now retry and verify; API403, still-running
responses and wrong identities tested. Archive/dependency/receipt-write failures
cannot bypass stop. A local failure fallback is installed too.

20-row batched evaluation recorder prepared (2 idle,18 diverse locomotion examples;
display selection only). No additional simulation rollouts or training RNG calls.
Each row retains its own terminal, target skeleton and six per-tick loss terms.
Synthetic20-row export/target validation passes; 3MiB replay chunking/replacement
test passes. Actual GPU overhead measurement and production continuation pending.

Authorized one L4 up to$0.59/hour for4hours (GPU ceiling$2.36). After the
collision-only diagnosis, user explicitly deferred the native Jolt bug and
authorized MJ training. Allocated owned Secure L4 **kdoqhqti1z2n0i**, rate$0.59/h,
Unix1792137671.7139745; hard stop1792152071.7139745 (**14:01:11 Warsaw October16**).
Local and remote deadline guards active. State is `Saved/MimicKitEquipment`;
never operate other pods. Runtime restored from verified cache; source is
checksum-verified on persistent volume aj7d2jzwuq; current archive/hash is recorded
in `Saved/MimicKitEquipment/source-receipt.json`.
Full512 remote preflight passed, including a disposable PPO update. Production
`20261016_100610_uefn_equipment_velocity_512` completed update0/16,384 samples,
then rejected world147 during update1 before PPO optimization. Process exited;
the last status.json saying training is stale. Initial checkpoint0000000 is
SHA-verified on persistent storage (86c25ba83f23f6e5453b8c4f1a317c2fd172dcc88b2dfae2245b9552330b9468).
This is an MJ-side transfer-solver rejection, separate from the deferred native
floor collision bug. No tolerance or physical parameter changed. Same-seed
diagnostics completed3 and20 updates without rejection; GPU trajectories are not
bit-identical across runs. The initial failure is NOT explained or declared fixed.
Training now saves the already-enabled first failed GPU equation on exception;
the former wrapper lost that in-memory capture on exit. Failure status is also
explicitly written; synthetic checks verify capture failures preserve the original
exception. Preserve all failed evidence.

Historical failed production: **20261016_101733_uefn_equipment_velocity_512**, PID982,
same original14:01:11 deadline. Last launch verification: iteration110/1,818,624
samples, ~5,129 transitions/s, no rejection. Checkpoint0000100 verified on
persistent storage, SHA748658f04a1e45bf1e94564788c0ac935a07709a73d64918a1fb85d38c7106b8.
`failure_stop.py` PID1074 watches ONLY this trainer: after a failed process exits,
it archives small unique diagnostic evidence with SHA readback and stops this pod.
It neither changes physics nor restarts training; stop preserves the pod volume
even if diagnostic upload fails. Existing local/remote deadline guards remain.
Viewer8021/TensorBoard8035 are live; observer identities in
`Saved/MimicKitEquipment/observers.json`, current name in current-run.txt.
TB datetime label2026-10-16_10-17-33_UEFN_Equipment_velocity_512 includes all six
loss terms. Replayer conversion fixed: supervised auto-phase is displayed but
excluded from the environment-reward consistency assertion. Recorded physics
reward agrees within5.96e-8; deliberately corrupt reward still rejected. Only the
local bridge restarted; production training was uninterrupted.

**Added horizontal COM velocity band loss (October16):** each clip has
independent fixed-world X/Y minimum/maximum reference COM velocities, sampled once
at240Hz using the same interpolation/velocity rules as tracking. Mass-weighted
pelvis/torso/head/thighs/shins/feet only; both whole arms including hands excluded.
Reference origin velocities are converted to COM velocities with angular velocity
and COM offsets; actual physics already reports COM velocities. Bounds expand by
10% of that axis's range at EACH end (20% wider overall), including signed/backward
speeds. Constant axes remain constant. Loss is zero inside; outside it is the mean
squared X/Y excess, multiplied by0.6771039952. Initial scale:0.5m/s excess on both
axes costs10% of4013's measured four-term tracking loss. This is a tunable modest
reference scale, not a claim about the new run's realized loss share. Existing
auto-phase coefficient remains calibrated against the original four tracking terms.
Enabled only for this prepared experiment; no new inputs or physics changes.
Bounds/mass weights are precomputed at startup; per-tick math stays on GPU.
TB `loss/flat_com_velocity` and weighted per-tick replay term included in totals.
CPU tests cover signed bounds, exact zero, gradients, mass weighting and excluded
arms/Z.16-world GPU preflight passes63.86s including disposable PPO update and
noiseless six-term replay; new term averaged0.04670 versus original terms6.51699
in this short fresh-policy smoke, not a learning result. Evidence:
`Saved/MimicKitEquipment/flat-com-preflight.log` and prepared/preflight/replay.npz.

Prepared54 motions, fresh weights/counters, unchanged1024→512→512 trunks,
154 observations (previous151 plus sword_drawn/right-arm-enabled/left-arm-enabled).
Sword0=unarmed/sheathed,1=drawn; both arm flags stay1. User deferred all injuries;
future disabled arms should use uniform gain sampling, exclude disabled-arm
tracking losses and corresponding hand termination, but none is active now.
31 of512 permanent rows are idle-only (nearest6%),481 locomotion-only; resets
retain row membership. Gait−1/0/1=idle/walk/run; equipment sampled within each pool.

Use the name **auto-phase** going forward (formerly Phase E). Two outputs predict
next inference cos/sin; reference clock still supplies training input, no feedback.
New experiment normalizes the prediction onto the circle; legacy checkpoint heads
remain unchanged. Maximum component-mean squared circular error2. Calibration from
4013's latest4,800 recorded samples: four-term mean1.6927599881, auto-phase weight
0.1493611754 makes its maximum0.2987223508 exactly15% of combined1.9914823389.
It remains a supervised actor auxiliary loss, not a guarantee of gradient share.
Prepared files/calibration/source.zip are in `Saved/MimicKitEquipment/`.
CPU contracts pass;16-world GPU smoke with asynchronous resets, disposable PPO
update and noiseless replay passes (61.04s, no saved learner). Remote512 preflight
passed165.5s including initial compilation. Full deployment/observers completed as
above. TB/replay code includes auto-phase; local edits remain uncommitted.

Updated-PHAT native fixture: `Saved/MimicKitEquipment/native/fixture.exe`, generated
header from current canonical exports, linked to the same isolated comparison DLL.
16/16 Run LR starts complete300ticks, but phase0.25 has a genuine right-ankle
anchor separation0.2023299m at tick87/substep4 (zero-based), recovering to5.66mm by
the policy boundary. Saved-body recomputation and repeated single-substep replay
confirm it; not just the scalar diagnostic. Prior native receipt did not show it.
Original reports preserved; new report is
`causal_transfer/solver_warm4013_self0_native_v40p8_point.json`.
`native/anchor-audit.json` and the identical-prefix interventions contain evidence.
Follow-up: freeing all angular limits still jumps21.04cm. At the identical
pre-fault state, disabling only contact positional correction via diagnostic
max-penetration-distance0 reduces separation to0.03627cm; disabling all position
correction gives0.14418cm. The culprit floor/right-foot manifold reports a
downward normal(z≈−1) and points19–29cm above the floor. This identifies contact
generation/correction as the next investigation, not a motor/limit workaround.
Diagnostic-only controls are confined to the isolated executable; no production
settings changed. Evidence: native/anchor-contact-position.json.
Narrowphase-only reproduction now matches the bad normal/depth exactly, without
advancing physics: dynamic foot first against floor half-width100m returns
normal z=−1/depth0.0011059679091m. Same foot pose at half-width25/50/75/125/200m
returns z=+1; reversing query order also returns +1. Instrumented local copy of
the existing convex collision code reproduces the sign reversal inside EPA after
GJK returns Indeterminate. It does not require motors, joint limits, contact-cache
reuse, or position solving. The wrong normal then selects the top foot face and
position correction pushes it downward. No floor-size workaround, collision
algorithm patch or gameplay change retained. Numerical internals/fix remain open;
do not conflate this narrowed collision-detection fault with a resolved transfer.
Receipts: native/anchor-query-dynamic-first.json, anchor-query-floor-first.json,
anchor-query-instrumented.json and stderr.log under Saved/MimicKitEquipment.
User subsequently authorized MJ training with this bug deferred. Do not issue a
new native transfer acceptance; this authorization does not make Jolt parity pass.

## October16 equipment dataset preflight — no launch

User requested checking the new PHAT and drawn/sheathed dataset before training.
Re-ran `verify_motion_limits.py --equipment --backup-name before-equipment-limits`:
54 clips,6,512,884 dense joint samples,103,264 exact-Jolt reference/margin tests,
zero violations including5% margin. Saved PHAT/mesh hashes match current exports.
Additional file audit confirms54 unique readable finite40-coordinate motions
(root xyz/rotation vector plus34 joints),60Hz, correct durations, normalized
directions and circular phase offsets, YAML order, and byte-identical unarmed
copies of the accepted originals. No loop-screening warnings. Receipt:
`Saved/MimicKitUEFN/equipment/current-dataset-audit.json`.

Each equipment set has14run/12walk/1idle. Both idles last10s. Unarmed idle is
the authored `/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop`;
drawn idle is the NN continuation captured with sword drawn. Drawn viewer's clip
selector includes Idle; the default unarmed preview currently contains only26
gaits, although its idle exists in the training files. No viewer change made.

Not ready to launch both sets: `prepare_local_omni.py` still selects the old27
clips, and `OmniWalkEnv` does not consume `sword_drawn`. Explicit equipment input
is needed before mixing the variants. Updated-limit native dynamic transfer
validation is also outstanding as described below; static limit admissibility
does not replace it. No training, Unreal or dataset modifications in this audit.

## Future UEFN training motor contract — October15

**Latest October16 solver pass verified; production still stopped.**
Current runtime reuses previous motor torque-limit branches only after solving
and checking them against current inputs; failed guesses run the unchanged full
seed/solve. Prepared manifold responses are reused. No physical rules, tolerances,
motor law or iteration ceilings changed. Cache70KiB/512 worlds, net one added GPU
launch, no extra CPU readbacks. Exact-stop seed experiment rejected as unhelpful.
Repeated-input physics5.680->3.853ms (32.2% less), but real training physics saves
only5–8%. Two full-PPO comparisons give2.6% median saving over10 matched rounds,
9/10 faster; no large whole-training speedup claim. Final4 crash controls, wrong
cache recovery,131,072 transitions/10,801 resets and4013's16x10s walking checks
pass; max16.940cm, zero walking fallbacks. Saved weights/body exports untouched.
Details and all rejected experiments: `MimicKitTransfer.md`,
`Saved/MimicKitLocal/solver_followup/result.json`.

**Current transfer receipt is stale:** the separate06:57 PHAT expansion predates
this optimization; native evidence uses the archived older body. Current MJ
walking tests pass, but native transfer must be revalidated with those new limits
before fresh all-motion training. The verifier now rejects differing native/MJ
body exports instead of certifying new assets using old reports. The earlier
receipt was restored; its freshness check fails as intended. Preserve the user's
new limits. See `MimicKitTransfer.md` for the audit and rejected receipt.

**Earlier coefficient/matrix optimization baseline:** cache motor coefficients during the50 seed sweeps; reuse/factor the effective
matrix in place and solve only needed constraint RHS vectors. No changed physical
settings, sweep counts, tolerances, failure checks or added CPU transfers/kernels.
Paired512-world physics8.588->5.640ms (34.3% less), contact/motor solve
7.463->4.439ms (40.5% less). Full disposable PPO medians6.389->5.251s/update
(17.8% less); all five measured pairs improve. Vanilla control3.231s. Unreal was
active, so these are paired observed timings, not guaranteed idle-GPU rates.
All saved crashes/manifold controls,131,072 noisy transitions and4013's16x10s
walking starts pass (max16.945cm,27cm bound unchanged).19 rare checked fallbacks
in the noisy test, none in the walking evaluation. Saved checkpoints are unchanged;
old native evidence remains historical. Future packages use these current
sources; old packages still fail the source freshness check. No production resume.
Full decisions/rejected experiments: `MimicKitTransfer.md` and
`Saved/MimicKitLocal/solver_optimization/`.

**Earlier October16 projection optimization:** matching-profile physics substep reduced
12.599->7.526ms on the controlled512-world fixture (40.3% less time,1.67x throughput).
Joint projection4.878->0.437ms; cached/reused calculations and a smaller GPU kernel,
with unchanged physical settings, iteration counts and tolerances. Four historical
failure regressions,131,072 noisy transitions, source/guard checks and4013's16x10s
tracking test pass (max17.890cm, original27cm threshold). Future packaging selects
these current sources; transfer receipt refreshed with the new MJ check and
unchanged native evidence. Production training remains stopped; checkpoints intact.

That earlier pass's full PPO speedup was **not established**: Unreal reopened during that measurement;
even alternating reference/current runs had large unrelated timing fluctuations.
Do not compare those wall times to the older idle-editor benchmark or claim the
old2.80x PPO penalty is eliminated. Evidence and accepted/rejected choices are in
`MimicKitTransfer.md`, `Saved/MimicKitLocal/optimization/`.

**Pre-optimization October16 speed audit:** the Jolt-matching profile cost7.68x vanilla MJ
physics time on identical recorded512-world inputs (12.599ms vs1.641ms/substep).
Complete disposable512-world PPO updates:6.581s vs2.350s,2.80x slower. Main costs
are the replacement contact/motor solver and split angular position projection;
zero rare fallback solves in the paired physics benchmark. The prior implementation
was not adequately benchmarked against vanilla before being made the default.
Details/caveats/evidence in `MimicKitTransfer.md`. Training remains stopped;
benchmark weights were discarded, original checkpoints preserved.

**October16 current state:** local fine-tuning from3913 to4013 completed100updates.
Both MJ and native Jolt40/8 pass16/16 true animation starts for10s, max target
errors16.93/16.86cm under the original27cm threshold. All sixteen60s native controls
also pass; two60s ONNX feedback controls pass. Initial29s failures were running off the old finite100m test
floor; a separate1000m-floor fixture proves this without changing the rig/DLL.
Details and remaining limits: `MimicKitTransfer.md`.
Fresh local all-omni+idle training stopped at03:49 October16 after753updates:
float32 accumulation made the rare contact-solver fallback fail convergence in
world218. Exact capture reproduced; compensated summation now fixes it without
changing physics, training settings or tolerances. Saved-case/CUDA-graph tests and
131,072 noisy transitions pass. Status corrected to failed; checkpoint700 remains
safe. Training has NOT been resumed. Full diagnosis: `MimicKitTransfer.md`.
The stopped run used512worlds, fresh weights and
counters: `2026-10-16_02-07-18_omni_idle_fresh_512`, bounded1000updates, no cloud.
27clips, idle−1/[1,0], walk0/run1, original network/observations/Phase E/losses/PPO.
TensorBoard8035 and noiseless replay8021 are connected; one rolling verified local
checkpoint. Future omni training selects the same verified contact engine by
default and requires zero added armature. Source package inventories include its
eight modules and launch checks reject stale bundles before spending. Shared PPO
guard rejects latched physics errors once per rollout before optimizing. CPU
inventory/factory/guard tests pass; no cloud upload/allocation or current-run
restart. Below describes the preceding shared motor fix.

Added idle fits every current PHAT limit including5% margin across1,075,214 dense
joint samples. The target motion and original PHAT were not changed by this audit.

Full-set update300 still has short noiseless episodes (mean5.488ticks); lower
loss alone is not successful locomotion. Two directional commands each occur in
two different approved styles; retained unchanged pending per-clip evaluation.
The future local runner now records failure status before attempting CUDA failure
capture, preserving the original error/checkpoint if that capture also fails.
Reporting-only controls pass; active training was not restarted. See transfer
journal for prepared successful4013 skin recordings and pending UE import.

Current UEFN source also reconstructs actual body COM velocities from the Newton
joint state before drag/gyro forces and after each policy step. This fixes the
MJ-child-frame versus Newton-parent-frame ball-velocity reporting mismatch,
including partial reset synchronization. Four captured-GPU10s trials and CPU
substep/Jacobian checks pass. Physics timestep, gains, torque caps, body properties,
observations and reward definition are unchanged; their body-velocity inputs are
now correct. Package builders include `assets/uefn/body_velocity.py` and launch
checks reject missing/stale adapters. This fix alone did not establish transfer;
the additional contact/limit work and current acceptance are recorded above.

All subsequent UEFN velocity training, fresh or resumed, defaults to the bounded
end-step motor/contact solve. Gains, torque caps and body inertia are unchanged.
Current source must be repackaged/deployed; cached older source is rejected before
GPU allocation or restart. Original checkpoint archives remain untouched. CPU
and CUDA equation tests and the integrated engine test pass. No new training or
cloud spend. Jolt already uses this motor law; full transfer still fails and has
separate limit/contact differences. Implementation, tests and limitations are
recorded in `Docs/MimicKitTransfer.md`.

## Reduced-rig skin preview — October15, separate transfer fork

User authorized trying the15-body articulation on the original weighted mesh.
Two separate Unreal animation previews now show recorded Newton and Jolt physics
on all88 original bones, without editing weights, mesh, original PHAT, Blueprint
or map. Newton preview is open; Jolt remains a failed-transfer diagnostic, not
working live integration. All imported frames verified numerically. Details,
current3913 transfer results and limitations: `Docs/MimicKitTransfer.md`.
GPU remains stopped; no training was launched for this work.

## Latest checkpoint downloaded; GPU stopped — October15 15:59 Warsaw

User requested download, stop and continuing Unreal integration. Latest verified
`checkpoint_0003913_final.zip` downloaded to
`Saved/MimicKitNoArmature/checkpoints/20261015_153406_no_armature_uefn_runLR_velocity_512/`.
15,910,118 bytes; SHA256
`176473b5f1128e7dfd951db9ae5c5da5d99ad267add14842e01f804bb5bf3837`.
Local hash, ZIP integrity and required entries verified. Persistent copy retained.
Owned pod `bpzuyhk04huodw` confirmed EXITED after explicit stop; no new GPU started.
Final sample count64,126,976; evaluated checkpoint3913, loop exit reports3914.
Final deterministic evaluation:512 episodes, mean297.15/300 ticks (9.91s),
return37.59384, weighted four-term mean2.79609. This is MuJoCo performance only.
Receipt: `Saved/MimicKitNoArmature/download-latest-receipt.json`.
Continuing isolated Jolt/inference verification in
`Saved/MimicKitTransfer/no-armature-3913/`; see `Docs/MimicKitTransfer.md`.

## Zero-armature fine-tune — October15, separate transfer fork

User authorized 30 minutes to fine-tune the latest Run LR checkpoint after
removing added joint armature. Launched at15:34:08 Warsaw as
`20261015_153406_no_armature_uefn_runLR_velocity_512` (remote PID476).
Only owned new pod
`bpzuyhk04huodw`, Secure L4 $0.59/h, allocation Unix1792071050.1840756,
hard stop Unix1792072850.1840756 (**16:00:50 Warsaw**). GPU ceiling $0.295;
setup and final save are included. Independent local and remote guards; no new
recurring schedules. Previous stopped pod and unrelated work remain untouched.

Resume input: verified `checkpoint_0003042_final.zip` from
`20261015_124835_uefn_runLR_velocity_512`, SHA256
`f14dbe34eb5ce33989b760447b1822923d4e4d58443c818b27c3f3fa9f5e0092`.
Preserve weights, optimizer/normalizer state, Phase E and counters; fresh physical
episodes. No reward, gain, torque, noise, calibration, PPO or termination changes.
Body mass, COM and physical inertia remain unchanged. This is a Newton/MuJoCo
fine-tune, not proof of Jolt transfer. Do not alter the velocity-reporting issue
identified in the separate transfer assessment during this experiment.

Implementation: opt-in `uefn_zero_joint_armature` clears Newton's generalized
joint armature before solver creation; checks both MuJoCo and MuJoCo Warp arrays
are zero. No per-step work. `--zero-joint-armature` requires Run LR resume; strict
configuration comparison permits only that one explicit change. Source ZIP is
the frozen previous source with only `train.py` and `uefn_engine.py` replaced.
CPU preflight: 32 finite ticks using actual saved actor, 151 inputs/34 actions,
15 bodies; original mass/COM/inertia assertions pass. Evidence and package
receipts in `Saved/MimicKitNoArmature/`, preflight in
`Saved/MimicKitTransfer/production_zero_armature_preflight.json`.

Source persisted and readback SHA256 verified at
`mimickit/pipeline_20261014/uefn-runLR/source_a8db9ca5cecd.zip`.
Runtime restored from the existing verified cache. Initial PC-to-pod checkpoint
upload timed out; switched to direct S3-to-pod download and verified the complete
original SHA256 before launch. No training used the incomplete upload.
Bridge29724/dashboard25468 use their own scoped state and dated `no_armature`
label; existing TensorBoard8035 and replayer8021 remain in place.

Live verification: resumed49,856,512 samples with optimizer/normalizer restored;
saved env and agent configs match exactly, engine config differs only by
`uefn_zero_joint_armature=true`. Advanced to update3073/50,364,416 samples,
~8,995 training transitions/s at this early check. No numerical failure reported.
First deterministic evaluation after the change:149.23/300 ticks (4.97s),
return6.2884; original final evaluation was274.31ticks/26.0808. The initial drop
is real; fine-tuning has not yet demonstrated recovery. First new checkpoint3043
uploaded and readback-hashed by uploader; independently retrieved S3 verified
manifest and confirmed stored size. Receipt `first-checkpoint-verified.json`.
Local replay contains the new deterministic rollout; TensorBoard has the four
loss terms, total, episode lengths and Phase E charts with advancing samples.
Final evaluation/upload reserve is165s; optimization stops by15:58:05 Warsaw,
billing guard stops the pod at16:00:50. Original checkpoint and Unreal untouched.

## Isolated transfer assessment — October15, separate fork

Latest Run LR checkpoint tested on CPU without contacting Unreal or changing
training. Four starts complete10s in the frozen training simulator; a15-body
Jolt transfer candidate exceeds27cm after0.20–0.70s. Direct deployment is not
validated. Armature sensitivity,15-versus23-body articulation and a backend
body-velocity reporting discrepancy are documented in
[MimicKitTransfer.md](MimicKitTransfer.md), with corrected adapter tests and
explicit limitations. No live rig, saved asset, lab tuning or cloud run changed.

## Stopped; final checkpoint downloaded — October15

User requested downloading the latest checkpoint and stopping the run. Runpod
API confirms owned pod **mrle36uk2xfjxs is EXITED**: the existing one-hour guard
already stopped it at13:46:10 Warsaw. No restart or new allocation. GPU training
is stopped; pod retained, not deleted. Persistent storage copy remains intact.

Downloaded latest verified **checkpoint_0003042_final.zip** for
`20261015_124835_uefn_runLR_velocity_512` to
`Saved/MimicKitOmniRun/checkpoints/20261015_124835_uefn_runLR_velocity_512/`.
16,131,949bytes; local SHA256 matches S3's readback-verified receipt:
`f14dbe34eb5ce33989b760447b1822923d4e4d58443c818b27c3f3fa9f5e0092`.
ZIP integrity and required model/optimizer/config entries passed. Bundle includes
final evaluation, replay and TensorBoard events. Receipt:
`Saved/MimicKitOmniRun/download-latest-receipt.json`.
Final deterministic evaluation: mean episode274.31ticks (~9.14s of10s maximum),
mean return26.0808. These are measured evaluation metrics, not a universal success
claim. No further run authorized by the download/stop request.

## Replayer COM camera and playback continuity — October15

Added persistent **Follow COM** checkbox beside Reset Camera. It follows the
selected agent's mass-weighted whole-body COM, including each body's rotated
local inertial offset, in the recorded world/view frame. Orbit/zoom remain
available; panning becomes an offset from COM; disabling freezes the camera
anchor. Reset Camera clears that offset. Recordings lacking mass properties
disable this option rather than substituting a joint average or pelvis.

MimicKit geometry export now includes mass/local COM per body. Current and prior
UEFN Run LR captures were backfilled against their matching XML/collider data
(15bodies, total78.254529595kg). Current local bridge restarted asPID19544 to
pick up the converter/geometry; GPU trainer and settings remain untouched.
Refresh, sidebar Reload and checkpoint selection retain current play/pause state,
including user changes while loading. Browser reload restores selected run,
speed and play/pause within the tab; COM preference persists across visits.

Verification: JavaScript syntax; unequal-mass/rotated-offset numerical COM case;
live COM following over a moving300tick recording; Refresh, sidebar Reload and
browser reload preserve playing. Paused Refresh remains paused. Existing simple
name/value loss display retained. Changes are in the Stepper replayer HTML and
checkbox_preferences.js, plus Labs/MimicKitTraining/replay.py; no main journal edit.

## Completed Run LR continuation — October15 12:48 Warsaw

User requested another one-hour **resume**, with unchanged settings. Run
`20261015_124835_uefn_runLR_velocity_512` resumes the verified final update1121
checkpoint (18,382,848 samples) from the preceding Run LR trial. Weights,
actor/critic optimizer momentum and steps, normalizers, RNG and counters are
restored, including the Phase E head; physical episodes start anew at random
reference phases as before. No reward, termination, controller or tuning changes.

Owned pod **mrle36uk2xfjxs**, Secure L4 at $0.59/hour, allocated1792061169.0668986.
Hard billing stop **1792064769.0668986 =13:46:09 Warsaw**, with165s reserved for
final evaluation/checkpoint/upload (stop new updates at13:43:24). One-hour GPU
cost ceiling $0.59, not a quoted exact bill. Local and remote guards installed;
no scheduled automation. State remains **Saved/MimicKitOmniRun**. TrainerPID629,
remote guard161, bridge26712/dashboard5104; local guard PID is in guards.json.
Old pod7e1ivwq6huv55h had stopped correctly but could not restart because its host
GPU was taken. Its verified final checkpoint/code/logs were preserved before
deleting it and replacing it within this newly authorized budget. Other pods
and Unreal work remain untouched.

Resume bundle SHAea1b4a001937c621b1fe2fea55705019e29d90e0ff5b5a560dfa2b2ac54c60ad,
15,542,976bytes, verified again on the new pod, from
`mimickit/pipeline_20261014/runs/20261015_115918_uefn_runLR_velocity_512/checkpoint_0001121_final.zip`.
Asset hash, saved calibration, finite model,151inputs and Phase E shape verified.
train.py now permits same-contract omni continuation and requires exact saved
engine/env/agent configuration equality before restoring; it bypasses none of
the strict checks and allows no migration of this run's calibration/objective.
Actor optimizer44,880steps/critic35,904steps in source checkpoint. Source backup
readback verified at `mimickit/pipeline_20261014/uefn-runLR/source_be1a4ceb5b90.zip`,
SHAbe1a4ceb5b90f5de3ee05b19d764e1b1a4a4c4d5a8f8dc2bc4e28613a5c74a00.
Cached runtime restored instead of reinstalling packages; this host rebuilt its
physics kernels. Live update1142 verified at18,726,912samples,~8.96e3transitions/s,
finite metrics and no failure alert. Resume receipt confirms optimizer and
normalizer restoration, global offset1122, no added/migrated observations.
First continuation checkpoint1122 is readback-verified on persistent storage:
SHA54a33436ca1ee9b102e17290d0a0367c01e56ce45a33d836c9e06404dd5e691f,
15,311,547bytes. Replayer8021 has the new deterministic rollout; TensorBoard8035
serves the dated12-48-35 run with all four losses/total, Phase E, episode duration
and throughput. Mean episode7.02ticks (~.234s) is still short; resuming does not
constitute successful locomotion. Guards and both local observers verified alive.

## Previous Run LR trial — October15 11:59 Warsaw

Fresh run `20261015_115918_uefn_runLR_velocity_512`, trainerPID498,512worlds,
151inputs/34motor outputs/2Phase E outputs on Secure L4 **7e1ivwq6huv55h** at
$0.59/hour. User explicitly approved replacing the stopped pod within the same
total budget and original deadline after its host refused restart for capacity.
Old x58la7cho673hu remained EXITED, then was deleted (no production training or
checkpoint there); only its obsolete local guard23744 was stopped. Active state
is **Saved/MimicKitOmniRun**, not Saved/MimicKitOmni. Never touch other fork pods.

Hard stop1792060477.4002864 = **12:34:37 Warsaw** unchanged.165s reserve means
training stops starting new updates at12:31:52 for final evaluation/checkpoint
and verified upload. This is remaining time in the original one-hour spending
window, NOT a newly authorized full hour. New local guard9752 plus remote guard;
no scheduled automation. Bridge3040/dashboard15260 follow the same deadline.
Existing TensorBoard8035, replayer8021, dated dashboard
`2026-10-15_11-59-18_UEFN_RunLR_velocity_512`. Do not renew automatically.

CUDA preflight:512worlds,151observations,34motors, finite rollout/disposable PPO
update and Phase E gradients, complete deterministic replay.82.998s including
new kernels; production uses the same resulting cache but starts fresh weights,
optimizers, normalizers and zero counters. First production samples16384/update0.
No future reference inputs; hidden widths1024->512->512. Wrist motor settings
verified after Newton import: velocity gain10, effort50Nm, position gain0.

Four-loss calibration comes from the fresh seeded noisy32tick batch BEFORE any
optimizer update; preserve summed mean8.7413016 and give each term2.1853254.
Fixed weights: position8.14227102e2,linear velocity3.29929589,rotation9.57144943e1,
angular velocity2.71353548e-1. No dynamic reweighting, controller/physics tuning,
reward changes or previous checkpoint transfer. Phase auxiliary coefficient0.1
is explicitly recorded in config, with phase/prediction_mse and weighted_loss
charts. Auxiliary prediction never advances the clock.

At update100:1,654,784samples,~9.63e3transitions/s, mean episode4.53ticks(~.151s),
weighted total8.055; no failure/backup alerts. These short early episodes are
NOT successful locomotion. First and update100 checkpoints uploaded and SHA
readback verified on volumeaj7d2jzwuq; independent latest_verified confirms
checkpoint_0000100.zip,15,297,461bytes,
SHAeed545c84fe665e4923aaf5c539f8136e8c7d810e0f6fafbf4ce3a184f83cd9b.
Immutable deployed source
`mimickit/pipeline_20261014/uefn-runLR/source_fb52f4310abe.zip`,561864bytes,
SHAfb52f4310abec80a6ba27539769f25dc2d4969da820c76f18dd6aa9b18e9fca3.
Calibration embedded in saved env config; no checkpoints downloaded locally.

UI verified: noiseless rollout, solid magenta23-collider target using RECORDED
reward positions/orientations, optional27cm target spheres, per-tick four losses
and total, phase/current/predicted-next/target-next. Checkbox works, no browser
errors. Independent NumPy/SciPy reconstruction at update100 agrees with recorded
weighted losses within2.16e-7; rendered sphere centres exactly match transformed
training centres; phase-next labels match next recorded tick. Episode ends with
right foot33.14cm from target. Evidence: replay-numerical-verification.json and
replay-verification.png under current state. Keep original actor and reference
motion distinction; reference is kinematic, actor is actual physics.

Supplemental preparation/UI backup readback verified:
`mimickit/pipeline_20261014/uefn-runLR/review_f902be40dc43.zip`,394866bytes,
SHAf902be40dc432683ecdc02be4c78fe0f0def947cc7c3adc2fd045cf9f344e958.
Includes wrist builder/tests/retarget scripts, all26 regenerated motion files,
saved PHAT/source export, dedicated notes, calibration, numerical verification
and local observer/replayer code. This does not replace the deployed source or
checkpoint archives. No unrelated process, Blueprint wiring or D/S tuning changed.

## Run LR preparation — October15 wrist correction, no trainer launched yet

Owned Secure L4 x58la7cho673hu was allocated at1792056877.4002864,
$0.59/hour ceiling, hard stop1792060477.4002864 =12:34:37 Warsaw.
An earlier user-facing message mistakenly said13:54; correct deadline is12:34.
Stopped/confirmed EXITED while correcting wrists, before any production launch.
Original source backup verified at
`mimickit/pipeline_20261014/uefn-runLR/source_95945325dda8.zip`.
State/guards/receipts are isolated in Saved/MimicKitOmni. Do not touch other pods.

User explicitly requested restoring wrists; approved reusing stock neck motor
settings (velocity gain10/effort50Nm per axis). Current model34motor outputs,
151observations=146physical+walk/run1+direction2+phase2, separate next-tick Phase E
2outputs, actor/critic1024->512->512. No future poses, no phase-clock feedback.
Phase auxiliary MSE coefficient0.1 is explicit in omni_config.py; it is an actor
auxiliary objective, not a fifth locomotion reward. Fresh weights/counters remain
required; no prior28-action checkpoint is compatible. Full wrist/source/retarget
checks are documented in MimicKitUEFNBodyMatching.md.

27cm termination implemented in omni_walk.py: strict Euclidean collider-centre
distance for head/both hands/both feet versus the EXACT reward target (including
target rotation/centre offsets). Stock contact/pose failure retained; upstream
has no separate pelvis-height threshold. Boundary test caught Python-vs-float32
squaring at exactly27cm; threshold now squared in matching tensor precision.
Strict-boundary, each-limb, head-offset and reset checks pass. Exact target body
orientations are recorded/conveyed to the viewer, allowing solid magenta colliders
and optional27cm target spheres. Phase E per-tick capture added. Fresh-weight
four-loss calibration will be regenerated for34actions; previous calibration
and disposable preflight are invalid for the revised body. CUDA preflight must
pass before launching; no recovery/learning claim from these setup tests.

## Pending UEFN omni setup - October15; Run LR test authorized, not launched

User now authorizes a fresh Run LR-only test with512agents on oneL4 for up to1hour/$0.59 GPU cost. This supersedes the preparation-only/no-launch restriction below. No allocation yet: complete integrated preflight and new27cm head/hand/foot target-deviation termination plus exact solid-target replayer/optional spheres first. Other pods/experiments remain outside this authorization.

Preflight found corrected RunLR ankle poses outside original limits in36/36frames and head twist outside in8/36. User explicitly chose to modify PHAT to admit the dataset with5% leeway. Completed for all26cuts: eight retained joint profiles widened, both ankle twists unlocked to LIMITED; all other constraint/profile/geometry/mass/drive/damping settings preserved. Saved original PHAT and regenerated matching model metadata; motion files bit-identical. Details/current values and receipts in Docs/MimicKitUEFNBodyMatching.md. New source export Saved/MimicKitUEFN/source-rig.json; historical Robotics/rig.json untouched. Dense1,871,160joint-sample+5% checks and29,856 exact-Jolt reference/margin checks pass; independent3600random Jolt comparisons and480CPUsteps pass. Current eight coupled profiles have ZERO locked ankle rows, superseding earlier two-row statements below. Preexisting dirty PoseAgent untouched, editor outside Play, no rebuild/restart.

Fit development caught exported hinge quaternion rounding (~2.3e-6rad) in the diagnostic's strict locked-axis check. Corrected diagnostic to the established exact single-axis hinge convention used by test_model.test_jolt; no runtime/asset change or relaxation of physical hinge axes. Initial failed fit made no changes; only the verified plan was applied. Current GPU integration/calibration/launcher/27cm/replayer work remains pending; no training-success or CUDA validation claim.

Review UI addition: omni.html now has optional wireframe spheres around both hands, head and both feet on each displayed character. Shared radius defaults to30cm; checkbox defaults on. Centres follow the actual named collider centres (head_shape0, hand_l/r_shape0, foot_l/r_shape0), not the reduced neck anchor. Radius/visibility update immediately without stopping playback and persist in localStorage under omni-review-spheres. Geometry allocated once and shared; update only position/scale. Verified30cm default,15cm edit,off/on,restored30cm, no console errors; screenshot Saved/MimicKitUEFN/omni-spheres-review.png. Visualization only, no collision/target/training changes.

User requests preparing a replacement for this chat's balanced walking experiment using the separate UEFN compound body/physics brief and the accepted26 omni cuts. Explicitly NO training launch until user says so. No cloud allocation, restart or deadline extension authorized by preparation. Confirmed fresh weights/optimizers/normalizers/counters; actor/critic hidden widths1024->512->512; walk/run scalar0/1, direction cos/sin; phase retained/implemented correctly for source cycles. Phase E uses two circular outputs for the next30Hz policy tick, prediction only; animation clock stays authoritative. Do not drive clocks with predicted phase. User informed that phase input makes prediction capable of learning clock advancement rather than physical gait phase.

Read body integration brief/README, rechecked both current saved UE asset hashes against rig.json (match), rebuilt existing asset and reran test_model:15bodies/28actions/23colliders,total78.254529595kg, FK5.582e-7m;3600Jolt classifications0mismatches;480CPU limit steps pass. Local setup dependencies now isolated under Saved/MimicKitUEFN/dependencies (Newton1.0.0, MuJoCo3.5.0, MJWarp3.5.0.2; existing Warp1.12.1). No installed-library edits. Reran test_newton on CPU:23colliders,8coupled profiles,2locked rows, geometry error6.209e-7m. No GPU integration validation or training launch yet.

User explicitly resolved observations: REMOVE future poses. Prior balanced baseline had enable_phase_obs=False, enable_tar_obs=True, tar_obs_steps=[1,2,3]; preserve that baseline. New opt-in omni_walk.py disables both upstream additions and appends exactly gait1+direction2+circular phase2 to physical state. Integrated CPU observation count145=140physical+5. Reference data remains for reward/reset only. omni_policy.py supplies actor/critic1024->512->512 and separate2-output next-tick phase head, never extra motor actions or noisy predictions/clock feedback. Phase auxiliary weight must be explicit in eventual config; not selected/launched yet. Labels recorded before stepping/reset. Contract tests pass widths,28motor/2phase outputs, gradient flow, wrap continuity, subset worlds and unchanged physical input; no optimizer steps.

Opt-in uefn_engine.py installs the existing PHAT adapter before stepping/capture, validates LOADED mass/COM/inertia, and adds compound member drag plus gyro cancellation per physics substep. prepare_physics.py produces physics.json from the verified export. Independent brute-force member drag/torque comparison passed max7.475e-8; includes preexisting external forces. Integrated CPU smoke:2worlds,4policy ticks,finite observations/losses,partial reset,8ball profiles, unchanged velocity controller/240Hz physics/30Hz policy. Evidence Saved/MimicKitUEFN/omni-contract-tests.json and integrated-engine-cpu.json. This is a bounded wiring check, NOT recovery, locomotion stability, CUDA capture, controller parity or a throughput benchmark.

Motion review: user was told initial reduction differs up to11cm at a hand and62.91deg at a fixed wrist; explicitly chose KEEP15BODIES and SHOWRETARGETEDMOTIONS. Tools/Locomotion/PrepareMimicKitOmni.py prepares all26 accepted cuts separately in Saved/MimicKitUEFN/omni. Greedy orientation projection preserves spherical rotations, projects hinges onto their axis, fixes wrists, uses reduced FK; NO pose fitting, stretching, limit clamping, seam blending or original recording edits. These errors are measured for this conversion, not proven irreducible. Phase offsets currently use left-foot minimum travel-relative velocity as a stance-centre proxy; alignment remains candidate pending review. Motion basis is proper-90degZ because recorded forward is+Y; asset basis stays+90degZ, bridged by anchor offsets. This180deg global difference is explicit, not a reflection or changed asset. Direction uses this same motion basis.

Review page http://127.0.0.1:8842/omni.html:cyan original23PHATcolliders following recorded bones;orange reduced15body/23collider FK. Same time/root translation/height; side-by-side or overlay,26clip selector,60Hz scrub/play/speed. Neither is a physical rollout. Both geometry sets use independently computed local collider transforms. RunF and WalkLR inspected; overlay/scrub/selector work, no browser console errors. Evidence Saved/MimicKitUEFN/omni-review.png. Original8841gallery/raw recordings untouched. First preview export failed because PHAT display metadata groups body labels; fixed source lookup using collider's original bone name, then regenerated successfully.

Remaining BEFORE readiness: user motion review; numerical reference-limit/clearance audit and any approved retarget correction; final phase alignment; integrated CUDA/multiworld/reset/force checks and benchmark; new-body fixed four-loss calibration; phase auxiliary coefficient, recorder/TB wiring and launch packaging. Do not claim launch-ready. No paid allocation, optimizer steps, upload, schedules, training or deadline extension in this preparation. No old checkpoint/normalizer transfer. Keep this branch out of ProjectJournal.md and preserve other fork changes. Full stride cuts remain intentionally not seamless.

Foot-clearance review: user likes the retarget appearance but noticed extra floor penetration. Confirmed numerically using exact collider-box support height, independently checked against all eight world corners (Tools/Locomotion/AuditOmniFootClearance.py; Saved/MimicKitUEFN/omni-foot-clearance.json). All26cuts have at least0.1cm additional penetration somewhere. Worst added depth:WalkLR/rightfoot/cut tick16, original bottom-1.647cm versus retarget-5.063cm, added3.415cm. Foot orientation differs less than4.55e-5degrees; the difference is foot POSITION, not collider size/rotation. WalkLR right shin orientation differs up to4.888degrees after single-axis knee projection, its anchor position only0.300cm, downstream foot position up to4.129cm. The rotation-only retarget does not constrain foot contact. Original recordings also intersect PHAT foot boxes with floor; do not attribute all penetration to conversion. No motion correction or floor lift applied during diagnosis. Candidate remains unapproved for training.

Subsequent authorized correction: user rejected restoring full original foot XYZ; asked to lift the foot and recompute its chain with the same pole. Implemented RetargetFootLift.py as an offline preparation step. For each foot independently, lift=max(0,min(original collider bottom,0)-retarget collider bottom). Thus remove extra penetration only, preserve existing XY and world foot orientation, leave original penetration intact. Hip anchor/pelvis fixed; retain knee pole projected onto the new hip-to-foot plane. Solve exact hinge-chain length equation including asset rest-frame/anchor offsets; choose nearest knee-angle branch, reconstruct hip/knee/ankle rotations. No bone stretch, pelvis move, smoothing, physical asset change or limit clamp. Unreachable/degenerate cases raise instead of silently substituting a solution; none occurred in26cuts. This preview correction does not claim joint-limit admissibility; that remains in the readiness audit above.

All26cuts regenerated and verified: pelvis/upper body bit-identical, uncorrected leg frames bit-identical, corrected foot XYZ and knee match analytic targets, foot orientation preserved. Initial fixed4e-7m comparison failed on4.195e-7m float32 rounding at roughly10m world travel; comparison now accounts for float32 magnitude (5e-7 absolute+2e-7 relative), not changed geometry/solver. Exact corner audit now finds maximum extra penetration3.740e-5cm (<0.001mm), versus3.415cm before. WalkLR/right/tick16 corrected depth1.64736cm versus original1.64733cm. Baseline evidence preserved as omni-foot-clearance-before-lift.json; updated report omni-foot-clearance.json, build log omni-foot-lift-build.log. Viewer reloaded and inspected at that frame. No training launched; original captures untouched.


## Separate UEFN body-matching asset - October 15

Dedicated specification/results: [match existing training bodies to UEFN PHAT](MimicKitUEFNBodyMatching.md). User subsequently requested implementation and explicitly approved multiple colliders on existing bodies. Separate asset/viewer in `Labs/MimicKitUEFN`: 15 bodies/28 action dimensions, all23 source colliders in the exact rest pose; no added bones/joints. Original model and active training untouched. Coupled PHAT limits require the explicit adapter shipped with the new asset; XML alone does not enforce Newton ball limits. Viewer localhost8842. Read its README and dedicated note before adoption. User withdrew the constant termination-penalty proposal after observing learning; do not implement it or restart/extend training for this asset work.

## Standing rule - restart versus resume

User clarified explicitly October15: **restart means return to the initialization checkpoint/state of the run being restarted**, apply requested changes and renew its runtime. **Resume means continue from its latest checkpoint. Restart from scratch means fresh weights, optimizer, normalizers and counters.** Do not equate restart with either resume or fresh weights. Preserve initialization provenance in launch receipts; an incorrectly resumed replacement must not become the baseline when correcting the mistake.

## Standing rule - loss visibility in the replayer

Every added, removed or reweighted loss must appear in the visible replayer in the same change. User explicitly requires the original plain monospace overlay: name and value, no panel/card/table/window. Show every recorded weighted PER-TICK loss term and total at the current playback/scrub tick in scientific notation; retain training total, run, noise, iteration, samples, agents, playback frame/time/speed, current root and capture timestamp. Keep coefficients and per-term train comparisons in metadata/TensorBoard rather than cluttering the overlay. Discover terms from capture metadata automatically; preserve each historical capture's objective and do not substitute current settings. Missing values mean "not recorded", never zero. Read exact recorded per-step loss arrays, using the current integer tick without smoothing/interpolating spikes. Never substitute frozen episode totals. Missing per-tick data must be labeled not recorded. Keep any aggregate training total explicitly labeled. Current early bonus is applied at45 only, tail penalties at46..50; zero outside the application windows is correct. Omit unrelated combat, foot-pin, sword and empty n/a diagnostics; preserve other viewers. Verify the visible current run. UI-only changes must not stop training or extend billing. Verify TensorBoard through read-only events/API, never by instantiating a writer.

## Current walking restart - balanced world-body losses, October 15

User requested RESTART with all four losses scaled to start equally because velocity terms dominated. Restart from ORIGINAL absolute run initialization: velocity checkpoint_0003209.zip,52,592,640samples/offset3210, SHAcd73bb7dacc3d98f6467fe6e1ed392130a0f1e48efce33da8661819b290b93dd. Do not use latest absolute run's learned checkpoint. Old absolute run stopped safely at65,716,224samples/final4010;16,526,366bytes SHA7c6fea7754de05f1a2de8ff25aa88875b444180f8c4f3d4204e9fe2bae555382 verified via S3manifest; preserve comparison.

Calibration uses ORIGINAL first actual TRAINING batch, same initial policy/512worlds/32ticks/action noise.05, before its first optimizer update. Read exact loss/* event points at52,609,024samples from20261015_065527_deepmimic_walk_absolute_velocity_512. Raw means:position3.570241679e-4,linearvelocity1.334306449e-1,rotation4.129034467e-3,angularvelocity1.743754625. Preserve their summed mean1.881671329 and assign one quarter4.704178322e-1 to each. Fixed multipliers:position1.317607811e3,linearvelocity3.525560659,rotation1.139292578e2,angularvelocity2.697729516e-1. No dynamic normalization/rebalancing; later curves should change with learning. Exact equal contribution is on calibration batch; repeated GPU physics and sampling need not be bit-identical.

absolute_walk.py multiplies raw four-term errors once BEFORE reward/log/recording; metadata carries exact weights. Replayer and TB show WEIGHTED errors plus total, and exact aligned target remains unchanged. Native velocity control, policy inputs, PPO/network/noise, motion/termination and exp(-sum error) reward mapping unchanged. Optional --absolute-loss-calibration file is embedded in env_config/checkpoint. First adoption requires resume checkpoint hash match; subsequent continuation must retain identical calibration. Calibration provenance is Saved/MimicKitTorque/absolute-balanced-calibration.json and immutable source archive. Other fork/source/pod unaffected.

Initially considered the existing deterministic305tick diagnostic as calibration; switched BEFORE launching training to actual noisy first training batch above. A diagnostic assertion demanding repeated physical averages match to2e-5 failed (~2% position variation), despite all functional target/loss/finite checks passing. Removed that unjustified determinism assertion: verify exact scaling on the recorded calibration means and independently reconstruct weighted replay errors. No physics or training tuning workaround. Final scaled preflight PASS:512worlds x305ticks, no optimizer steps, exact weighted replay loss/reward reconstruction,10s noiseless capture, finite policy states;7.35s rollout/34.21s total. Recomputed calibration contributions all4.704178322e-1. Noiseless diagnostic means differ from noisy training calibration by design (position.2975,linear.4398,rotation.2604,angular.3379); do not falsely claim those test means are equal. Evidenceabsolute-balanced-smoke.json.

Launched20261015_071323_deepmimic_walk_balanced_velocity_512 PID2188 on same ownedp4q79u5vt1jo1a. Renewed1h deadline1792044804.52837=08:13:24Warsaw,165s save reserve, existing guards/no schedule. Correct initialization3209 is explicit in launch receipt. Observersbridge14664/dashboard30212; separate datedTB2026-10-15_07-13-23_DeepMimic_walk_balanced_velocity_512, previous unbalanced curves preserved. Source+calibration archived/readbackverified underabsolute-balanced/source.zip; receiptbalanced-source-receipt.json. Only this fork's remote train.py patched from preserved deployed snapshot. Live verification passed: first training batch at52,609,024samples has weighted losses position.470664948,linearvelocity.470458388,rotation.470754117,angularvelocity.470372707 (all within0.08% of calibration target); total1.882250190. At55,394,304samples total1.300685763; no success claim from loss alone. S3latest independently confirmscheckpoint3310,16,517,655bytes SHA0d6d6c15c8d272af1d54810299c02f820a27fb51472b890d87af2c955e58bd4d. TensorBoard read-only API and visible five cards verified scaled values. Replayer selected newrun3310 with actual magenta targets enabled; tick120 weighted values.06794/.3244/.04559/.1575,total.5954. Screenshotbalanced-replay.png; balanced-output-verification.json. Initial noisy train equality does not imply every replay tick has equal terms. No further training restart for UI.

## Previous walking comparison - unbalanced absolute world-body motion loss, October 15

User requests continuing latest velocity walking policy with FOUR world-body errors: position, linear velocity, rotation, angular velocity. Position targets follow actual pelvis XY only; retain reference animation world height and heading, never rotate with actual pelvis. Pelvis XY position error therefore zero; its Z position and all three other errors remain. Original motion/world body-origin velocities are targets (not the derivative of the live XY re-anchoring). No local joint errors. Policy inputs, stock reference/reset distribution, termination, PPO/network/noise and native velocity controller remain unchanged. Four equally weighted body/component MSEs; rotation uses rotation-matrix MSE (quaternion-sign invariant). Reward exp(-sum of four errors), preserving positive imitation reward with stock zero-on-failure continuation; NOT negative loss with an escape incentive. This reward mapping was explicitly explained to user before launch. No added failure cost or controller changes.

Old velocity run stopped normally at52,592,640samples/final3209. checkpoint_0003209.zip verified on persistent S3 and manifest independently checked:16,354,082bytes SHAcd73bb7dacc3d98f6467fe6e1ed392130a0f1e48efce33da8661819b290b93dd. New20261015_065527_deepmimic_walk_absolute_velocity_512 PID1735 resumes EXACT checkpoint/optimizer/normalizers/counters,512worlds. Same owned podp4q79u5vt1jo1a at$0.59/h; other fork/pod untouched. Requested resume renews1h authorization. Both existing deadline readers renewed BEFORE old deadline to1792043247.678524 =07:47:27Warsaw, includes wiring/testing time; launch uses --keep-deadline to avoid extending again. Existing165s save reserve/guards, no schedules/new pod.

Implementation absolute_walk.py subclasses DeepMimicEnv, leaving upstream files untouched. Reference world velocities are propagated analytically through the existing FK hierarchy. Newton body_qd linear entries are WORLD COM velocities: convert to body-origin velocities using v_origin=v_COM-omega cross R*COM before matching skeleton origins. Numerical derivative test exposed upstream slerp's constant midpoint branch at sin(half-angle)<.001 and constant-q0 branch at dot>=1. Its stored DOF/root angular velocities ignore those branches. Precomputed per-segment moving masks match those EXACT existing sampler branches; no custom threshold, smoothing, altered animation or gain. Initial unmasked check failed (maxlinear discrepancy.1758m/s); corrected derivative check passes max5.739e-4m/s and8.340e-4rad/s. Source motion and sampler remain unchanged.

Preflight512worlds x305ticks, restored latest checkpoint, NO optimizer steps: finite states/losses, all four losses independently reconstructed from recorded poses, original and target body-origin linear/angular velocities; recorded target pelvisXY exactly equals recorded actual pelvisXY. XY translation invariance, height/heading error, pelvis forward velocity error and quaternion-sign invariance pass. Recorded full10s deterministic episode; rollout7.44s. Evidence Saved/MimicKitTorque/absolute-smoke.json, test_absolute_walk.py; remote absolute-smoke-replay.npz. Diagnostic loss means:position2.213e-4,linearvelocity1.247e-1,rotation2.265e-3,angularvelocity1.252,total1.379. These characterize unchanged prior policy under NEW objective; not a learning claim.

User specifically requires replayer to show EXACT training target, not original unshifted animation. Recorder copies reward_target_pos/refworldrot each captured tick and four weighted MSEs; converter verifies exp(-sum loss)==recorded reward. Reference skeleton stays magenta via existing checkbox. Recorded velocities allow independent recomputation. No reconstructed/guessed target for these captures. Existing historical stock references retained unchanged. Plain per-tick name/value overlay automatically showsfour+total; TensorBoard gets explicit loss/position_mse,linear_velocity_mse,rotation_mse,angular_velocity_mse,total alongside existing reward/episode/optimizer/performance charts. Separate datedTB label2026-10-15_06-55-27_DeepMimic_walk_absolute_velocity_512; originals preserved. Observers bridge14540/dashboard5136 under isolated Saved/MimicKitTorque; no other observer stopped.

Exact deployed source archived/readbackverified at mimickit/pipeline_20261014/absolute-walk/source.zip (receipt absolute-source-receipt.json). Deploy train.py patched narrowly from this pod's frozen snapshot, preserving other fork's independent local trainer changes. Local trainer receives opt-in --absolute-walk; no default behavior changes. Main ProjectJournal/UE/PHAT/BP/D/S untouched. Live verification: restored52,592,640samples/offset3210 with optimizer/normalizer and zero appended inputs. At3300/54,083,584samples training advances~1.914e4transitions/s; no numerical/backup errors. Initial new-objective evaluation512episodes mean9.968s/return91.898, per-tick totalMSE1.363; these are new reward units, not comparable to the stock reward. First checkpoint3210 verified16,518,407bytes SHAb5e32b0d3e8f3557301697662036979ce649861fd56df1587ae5f2eb87b24b9f; subsequent manifest continues advancing (absolute-checkpoint-verified.json). Replayer visibly selected correct run, tick120 shows position7.216e-5,linearvelocity1.307e-1,rotation1.445e-3,angularvelocity6.613e-1,total7.936e-1; exact target checkbox ON. Recorded target pelvisXY alignment error<=1.49e-8m. All5TB cards have actual scalar samples, filtered in existing own TB tab; old comparisonruns preserved. Screenshotabsolute-replay.png; numerical/UI evidenceabsolute-output-verification.json. No trainer restart for UI.

## Previous walking comparison - fresh velocity control, October 15

User requested restart FROM SCRATCH in velocity mode. Gracefully stopped torque continuation at70,402,048samples/final4296; checkpoint16,356,906bytes SHAf5041d1dc2d7f81c8f188ff961c2a8e2eb2b39abfa8cbf08863598a995ec879a verified on persistent S3. Preserve it for comparison, do not resume these weights into velocity training. Same owned L4p4q79u5vt1jo1a at$0.59/hour; other pod/training untouched. Fresh1h renewal per standing user instruction: hardstop1792039724.235264 =06:48:44Warsaw, existing local6376/remote196guards and165s final-save reserve. No new pod/schedule.

Velocity run20261015_054840_deepmimic_walk_velocity_512 PID1070,512worlds, stock DeepMimic humanoid walking reference/rewards/PPO/network/noise/reset/termination, native control_mode=vel. Fresh weights/optimizers/normalizers/counters, no --resume. Only physical control mode changes versus original torque trial. Position stiffness0; stock asset damping acts as velocity feedback; velocity action-space bounds +/-2pi rad/s. Zero requested velocity is braking, not limp. Stock torque limits remain50..200Nm. Local launcher permits vel for walking only, preserves parent fork's independently added torque/world_pose support. Remote launcher modified narrowly from its existing snapshot to add vel choice, avoiding unrelated source deployment.

512world preflight PASS: stiffness0, dampingpositive, action bounds+/-2pi, exact requested target_vel sent to backend,1rad/s target causes0.921283rad/s measured response difference versus zero-control airborne pair;90finite policyticks,2373endedepisodes,16frame replay, no optimizersteps. Test test_velocity_walk.py / Saved/MimicKitTorque/velocity-smoke.json. Exact deployed source backed up/readbackverified atvelocity-walk/source.zip,690183bytes SHAf5b74f9b9708059d3e13b9a492796185f8839988a0c2bb7becca5e0a60071ec9. Full reference skeleton recorder remains enabled for evaluations. Bridge16660/dashboard9380, unique datedTB label2026-10-15_05-48-47_DeepMimic_walk_velocity_512, original torque curves retained. Verified fresh prior_samples0/iteration_offset0, advancing100updates/1,654,784samples at1.362e4transitions/s; no failure. Checkpoint100 verified16,204,271bytes SHA79bd3822f71c710b3c0ccfc35efbe51467a1fbc6b7ed0a5a4d3dfc5274547ae4, independently confirmed S3latest_verified. Deterministic evaluation100 mean1.00443s/return20.7444 versus initial0.57927s/11.1337; early improvement only, not walking success. Actual reference_pose finite in replay, new run selected and dated TB charts verified read-only. Other experiment and main journal untouched.

## Parallel experiment - stock DeepMimic walking with torque, October 15

User requested +1h after scheduled stop. Original trainer ended normally at the165s save cutoff, no failure; final2391 at39,190,528samples saved/readbackverified16,292,468bytes SHAd5069b3e3d1641a96fc6a5e67cde46ba623898324e43d6782d4a24f823c5a01e. Same pod still running; extended BOTH deadline readers before billing stop to1792037407.9830446 =06:10:07Warsaw, exactly one hour added to prior allocation deadline (additional GPU ceiling$0.59). Local6376/remote196 guards preserved. No new pod, schedule or changes to the other experiment. Continuation20261015_051013_deepmimic_walk_torque_512_resume PID735 uses that exact checkpoint, same512/torque/walk/stock PPO/config, --keep-deadline. Existing remote train.py preserved; uploaded only already-requested recorder update to save exact reference poses during evaluation. TB appends continuation to the SAME dated run/chart, counters retained. Bridge22240/dashboard27396 replace only this experiment observers. Verified restored39,190,528samples/offset2392 plus optimizer and normalizer; advancing2412/39,534,592samples at1.60e4transitions/s, no error. First2392 checkpoint16,355,001bytes SHA404f4064f0c97a7b782546c6578a34ae890953d13c52d9f1b2fe60e140389c04 verified; S3latest_verified independently confirms uploads advancing beyond it. Deterministic evaluation512episodes mean300ticks/10seconds and return232.109. Actual301frame reference_pose recorded, finite and visible via target checkbox; resumed run selected in replayer. Same datedTB curve has points beyond prior final sample count, independently checked through scalar API.

Target skeleton overlay added on user request October15: existing checkbox reads "Target skeleton" for DeepMimic references, draws magenta skeleton above shaded physics, remains toggleable/persistent and shares playback/scrubbing time. No simulated target actor, training change, restart or deadline extension. Current legacy walking captures omit reference; CPU-only replay_reference.py reconstructs the unique initial clip time from the reset root segment and verifies ALL body positions/quaternions before using upstream MotionLib/FK for each recorded episode time, including loop translation. Reference remains in original authored world coordinates, never follows the simulated root. Reject ambiguous/mismatched initial poses (>0.1mm or1e-4 quaternion distance); do not guess. Current1900 capture reset maximum discrepancy0.01917mm, quaternion4.65e-5 due to float32 reset DOF round-trip. Synthetic phases/loop boundaries agree <=9.54e-7;1cm wrong-head pose rejected. Source/clip bytes verified identical to deployed snapshot.16 existing local walking captures backfilled,1 unmatched left unavailable. Historical capture timestamps retained. Future recorder source copies exact _ref_body_pos/_ref_body_rot only during recorded DeepMimic evaluation, and converter prefers these over reconstruction; active trainer keeps its existing recorder. Source change is not hot-loaded into training. Only torque local bridge restarted11656; other observers untouched. Verified checkbox on/off and magenta reference visibly beside simulated body at tick15. Local PyYAML dependency158kB installed for upstream CPU motion reader; no GPU/training or network-payload overhead. Evidence reference-test.json/reference-backfill.json and test_replay_reference.py. Main journal/UE/D/S unchanged.

User authorized a SECOND Secure L4, one hour total allocation at at most $0.59 GPU cost. Separate pod p4q79u5vt1jo1a at $0.59/hour; allocation1792030207.9830446, immutable hard stop1792033807.9830446 (05:10:07 Warsaw). Existing pod a34l6y5ngp6s6a and its run/deadline are untouched. All local pod/control/guard/observer state isolated under Saved/MimicKitTorque via optional MIMICKIT_STATE_DIR; default cloud.py behavior unchanged. Local guard6376 and remote guard196 independently stop this pod. No new schedule. Preserve 165s for final evaluation/checkpoint upload; setup time counts toward the authorized hour.

Run20261015_041442_deepmimic_walk_torque_512, trainer538, launched with --keep-deadline, no resume (fresh weights/counters). Stock DeepMimic humanoid walking reference, 512 parallel worlds, native torque mode; stock rewards, reset distribution, termination, PPO and network remain unchanged. Stock deterministic32-episode evaluation retained for noiseless replay. Only logging/checkpoint cadence differs from upstream defaults. No custom pose/height/impact objectives, AMP, floor-only starts, gradient caps or noise overrides. Direct torque uses stock per-joint bounds50..200Nm, no positional or velocity motor servo; passive mechanics and contacts still apply. Selected engine config is saved separately, original engine YAML unchanged.

Preflight512world test PASS: both motor stiffness and damping zero; zero action yields exactly zero commanded motor torque; controlled airborne25%-torque experiment changes joint velocity9.74673rad/s versus zero command;90 finite policy ticks,3704 completed episodes, valid14-frame replay, no optimization. This verifies plumbing, NOT learned walking. Evidence Labs/MimicKitTraining/test_torque_walk.py and Saved/MimicKitTorque/torque-smoke.json. Runtime restored from existing verified cache; no reinstall. Source backed up at mimickit/pipeline_20261014/torque-walk/source.zip (687917bytes, SHA902c3fbde1b5d1ad12cc5c763743d3ae5fed430b30d4cc29cc66127f28423542). Independent bridge16756/dashboard19140 share existing replay/TensorBoard services under a unique dated run. Live110updates/1,818,624samples at1.358e4transitions/s, fresh zero counters verified. Config diff against stock: only engine control_mode=torque, reference=humanoid_walk, iters_per_log=10; 512worlds supplied at launch. Evaluation0 mean0.36719s/return3.6351; evaluation100 mean0.54693s/return7.2168. This is initial improvement, NOT learned walking. Checkpoint100 readback verified on S3,16,187,178bytes SHA0fa1bee7dc6ccd356229f9c36d2b975beb3381254188386740d8ddc25759011e. Source checkpoint0 also safe. Exact configs/code remain in the source snapshot and checkpoint archives. No numerical or backup failure observed.

Local-only display correction: stock walking captures had fallen through to legacy MSE/combat diagnostics. replay.py now exposes their exact recorded per-tick reward and episode return; viewer uses the existing compact plain overlay for those captures. Numerical comparison to replay.npz reward array passes exactly. Existing custom loss displays unchanged. Only this new local bridge restarted; trainer and other observers stayed running. Visible torque replay100 verified with per-tick imitation reward, episode return, noise, iteration/samples, frame and root. DatedTB run2026-10-15_04-14-42_DeepMimic_walk_torque_512 has reward train/test, episode seconds, actor/critic and throughput; tags verified via read-only API and run shown in separate browser tabs. All final-save/deadline guards retain original allocation deadline. No changes to ProjectJournal/Unreal/assets/D/S.

## CURRENT - pose/height restart with native velocity control, October 15

Live20261015_055108_pose_height_velocity_512 PID6909 on existinga34l6y5ngp6s6a. Fresh resume.json prior_samples0/iteration_offset0 verified; engine modevel,30/240Hz and noimpactflags confirmed. Renewed existing local/remote deadline readers to1792047070.4196568 =08:51:10Warsaw,165second save reserve; no new schedules/pod. Bridge22164/dashboard18480, previous failed torque dashboard30000 stopped by exact identity. Source archive/readback receipt pose-velocity-source-receipt.json. At170updates/2801664samples,1.669e4transitions/s, no numerical/backup failure; first100checkpoint19445155bytes SHA85b190e705a6fca1b96e859085cd4901ac44ae1b31b1007ecd2339278a864832 independently verified via S3latest_verified. Not a learned-recovery claim.

DatedTB2026-10-15_05-51-08_Pose_height_DeepMimic_velocity_512_1024x1024 has live loss/train (sample2637824,1.75373), all fourloss components/total and episode cards. Replayer selected new velocity run; iteration100 noiseless28tick capture visibly shows all four weighted per-tick losses+total, no force-termination readout, training noise.05. Tick28 total.8617 contains remaining-frame charge.8356; this is real foot-distance termination. Evidence pose-velocity-{test,live,checkpoint-verified,tb-verification,observers}.json and pose-velocity-replay.png. Original floors/target/calibrations/controller configuration retained apart from requested control mode. Main journal and other walking torque experiment untouched.

User paused torque investigation and requested restarting in velocity mode. Return to current run's fresh seeded initialization (20261014), reset weights/optimizers/normalizers/counters, do not resume learned torque checkpoint. Same custom pose/height PPO task,512worlds,1024x1024,.05fixed noise,2second episodes,50/50noisy floor starts,1.75x Euclidean foot-distance failure with remaining cost, existing fixed loss calibrations; floor-impact termination remains OFF. Stock30Hz control/240Hz physics/implicitfast retained. No speed clamp, RK4, damping tuning or new loss. Existing vel mode uses target speed bounds +/-2pi rad/s, zero position gains and original velocity-servo gains10..100 with stock torque bounds. This is a requested velocity target bound, not a hard physical speed limit. Actor-normalization rebuilt for velocity actions. Minimal trainer change permits world_pose with vel using existing native backend.

Preflight test_pose_velocity.py passes512worlds x240stochastic ticks with no optimization, fresh sample count0. Native servo command/positive response verified (1.9058rad/s contrast versus zero target), all original losses and remaining charges numerically identical,44.8225cm foot-distance threshold retained, no AMP/impact buffer. Maximum actual DOF speed19.9773rad/s, finite;2456completed episodes; rollout7.29s,total22.88s. No learning/success claim. Renew same owned L4's3h window on launch per standing restart rule; separate walking torque pod untouched. Source/test/checkpoint/observer receipts will record launch. Torque/RK4 approval question is superseded by this request.

## Previous - fresh DeepMimic PPO pose/height with direct torque, October 15 (failed; preserved)

Live run20261015_052650_pose_height_torque_fresh_512 launched from fresh state (prior_samples0/iteration_offset0), same owned pod, deadline1792045613.3786612 /08:26:53Warsaw. Failed at update2: invalid next observation/reward, rollout rejected BEFORE PPO optimization. Checkpoint0/16384samples verified19436375bytes SHA428b13adde511527aea80632505a264c606e221a6b2302db01a2cdf31b936e1d. No healthy running trainer now; stale status.json says training, failure.json takes precedence. Do not restart blindly. Source archive734309bytes SHA15aa7baeb0f2430af96bafe05edb82d47a1cf0680d11be1bfb256fbc69be8009 verified under deepmimic-pose-torque/source.zip.

Diagnosis: fresh seeded TRAIN-mode policy reproduces failure with NO optimizer updates, world371 at controltick12, first episode/no resets. Commands finite/in bounds; left ankle DOF27 exceeds1.1e3rad/s before NaNs. Zero-command240tick test passes. Cutting torque after6ticks passes. 480Hz and RK4-at240Hz each pass512worlds x240ticks, but these are bounded diagnostics, not training validation. User explicitly rejected480Hz and requested further240Hz investigation. RK4 approval remains PENDING; no production integrator/physics changes. Rough3x RK4 timing was from unlike rollout/reset counts (15.01s RK4 stochastic vs5-6s zero/cutoff baseline), NOT a matched training throughput benchmark.

Stock importer converts3hinges to balls; solver exports ball joints limited=False. Only elbows/knees retain limits. Torque mode has zero motor gains and zero passive damping; armature values correctly present(.01/.02). Not a new limit removal in this port. Captured identical state/actions replay in CPU MuJoCo follows GPU divergence (first subsequent pose discrepancy5.65e-6, velocity1.77e-3), then CPU reports unstable QACC and auto-resets where GPU becomes nonfinite. Controlled CPU diagnostic with ALL commands, gravity and constraints disabled: implicitfast at240Hz raises kinetic energy505.45->1523.82J in.2s, RK4 gives516.23J(~2.1% drift). This isolates integration energy error at high speeds; no claim that RK4 universally solves it. Test scripts diagnose_pose_torque.py/diagnose_torque_cpu.py, remote pose-torque-{diagnose,zero,480,cutoff,rk4,capture,cpu} evidence; no loss/controller/noise/limit hacks.

User challenged comparison with Implement get-up system (4). Read that thread and independently compared both DEPLOYED configs/source. Same humanoid asset hash, engine YAML (torque/30Hzcontrol/240Hzphysics), and identical set_cmd/_build_solver/_create_obj_builder/_pre_sim_step source. Other walking run healthy4172/68370432samples, no failure. Differences: walking reference-state resets, fall contact termination (non-feet),1m pose termination, velocity imitation terms and1024x512 stock network versus this floor-only50/50pool, custom pose/height objective, distance termination and1024x1024. These produce different trajectories/exposure to high-speed instability; have NOT ablated each to quantify causality. Do not imply torque or240Hz always fails. Other pod untouched. Evidence Saved/MimicKit/torque-run-comparison.json.

User requested porting this experiment to DeepMimic, same training except remove floor-force termination and use torque instead of position control. Explicit clarification: **start from scratch**. Fresh actor/critic, optimizers, normalizers and counters; do not load position-policy weights or reinterpret its action-normalization buffers as torque. Same pose/height target, fixed weights, worst-body reduction, world orientations/fixed heading/XY alignment,2second horizon,512worlds,1024x1024 network, action noise.05,50/50noisy floor pool,1.75x Euclidean foot-distance termination and remaining-frame charge. No AMP discriminator or imitation reward. Runtime uses stock `deepmimic_humanoid_ppo_agent.yaml` directly while retaining the custom1024x1024 network (stock misleadingly named fc_2layers_1024units is1024x512). Verified stockDeepMimic PPO hyperparameters match the prior AMP-stripped PPO configuration after the same network/log overrides. WorldPoseEnv remains the custom task on CharEnv, not the stock walking imitation task.

Removed dependency on AMP environment just to register the network: shared networks.py holds the identical constructor, old AMP import alias retained for compatibility. Allow world_pose torque and fixed validated foot calibration on a fresh run; historical resume calibration checks retained. No impact config/peak accumulator enabled for this run. Direct torque uses upstream per-joint torque bounds, zero position/velocity motor gains; no extra controller. Existing baseline contact readout retained by engine, but8-substep impact conversion/peak accumulation disabled. Replayer metadata records control_mode and omits inactive force telemetry; original four weighted loss terms and total remain.

Previouscorrected2.2kN run gracefully saved final26590/435,666,944samples, verified19,707,842bytes SHAb9dac7d12a65804e95e6a6099e28ffe6ed8c0e58aaae8cfbfae48ec23c3a6cd0. Fresh run will use same owned a34l6y5ngp6s6a with renewed3h; no new pod/schedule. Separate stockDeepMimic torque walking pod p4q79u5vt1jo1a remains untouched. Evidencepose-torque-previous-final.json. Test/deployment results follow.

Preflight: initial test used an unspecified random network seed and hit a non-finite observation/reward during60tick rollout after its airborne probe. No training launched then, no runtime clamps/gain/solver edits made. Preserved remote pose-torque-test.log; exact initial offending state was not recorded, so cause remains unresolved. Repeated with the ACTUAL training seed20261014, paired with/without airborne probe: both pass512worlds x60finite ticks,4492completed episodes, fresh sample count0. This excludes the probe as the cause for that seed; it does not explain the first unseeded failure or prove all random policies stable. Disclosed to user; keep existing numerical fail/save/alert mechanism, no blind retraining if it recurs.

Seeded checks confirm no AMP modules/discriminator, exact prior PPO settings with stockDeepMimic config+same1024x1024 network/logging,140inputs/28torques, no impact accumulator, both position/velocity motor gains0, zero command=>zero motor torque, positive isolated25% torque changes joint velocity11.9646rad/s, limits50..200Nm. Exact original pose and height-band formulas,44.8225cm foot-distance threshold and single remaining-frame charge pass.257/512back starts, allfinite reset/replay values, fourloss terms, no inactive force fields. Tests17.60/17.84s, no optimizer steps. Evidencepose-torque-{skip,seeded}.json; tests use dedicated copied pipeline, production code/deployment follows only after passes.

## Previous - corrected restart initialization, October 15

User corrected the mistaken continuation below and authorized fixing it. The requested2.2kN arms/head variant must start from the initialization of the original2kN run: `/workspace/mimickit_trial/runs/20261015_034302_pose_height_distance175_512/checkpoint_0025442_final.zip`,416,858,112samples/offset25443, SHA98be6f047f031e02657dd627444edc186c9bcc3eae01830648905b2d35d9d4fd. Confirmed against original2kN launch command and actual remote file hash. Do NOT use final26843 or the latest arms/head checkpoint. Keep existing tested2.2kN seven-body selection, original losses,1.75x distance termination, remaining-frame cost,512worlds and all network/PPO/controller/physics settings. Only checkpoint origin changes; fresh three-hour deadline as requested. Save mistaken run safely before replacing it; no new physics tests or code changes needed.

Completed correction: mistaken arms/head run saved final27321/447,643,648samples, verified19,582,392bytes SHA6d3b3565c0d0925ae7470b7af777640fb81f06260da002465e3cdcea9e937570. New20261015_045834_pose_height_arms_head22_restart_512 PID4401 on same pod. Restored original416,858,112samples/offset25443 with optimizers/normalizers, exact2200N seven-body selection verified; advancing417,038,336samples, no failure flags. New hard stop1792043916.2508106=07:58:36Warsaw, existing guards/165s reserve; no new pod/schedule or parallel-torque changes. First25443 checkpoint verified19,483,813bytes SHA95ace9fab776f8ccd19506cce189fa66ca3a0baf0205893e8626f6e642b60446, S3latest_verified independently retrieved. Same backed-up arms-impact source reused; no duplicate source archive or altered settings.

Bridge21980/dashboard9624, only prior owned dashboard24836 stopped. Datedlabel2026-10-15_04-58-34_Pose_height_arms_head22_restart_512_1024x1024; replayer visibly selected correct25443 run with fourtick first replay, metadata2200N/sevenbodies checked. TB train/test/remaining-cost/episode-length points verified read-only; original series retained. Dedicated evidence restart-initial-{parent,previous-final,live,output-verification,observers}.json. Journal now explicitly records user's restart/resume/from-scratch meanings at the top. No Unreal/main-journal changes.

## Previous - 2.2kN arms and head only, WRONG continuation checkpoint, October 15

User requested restart of this run with impact limit2.2kN on both arms+head instead. Explicitly acknowledged continuing latest checkpoint and renewing3h, preserving1.75x foot distance and remaining-frame charge. Both arms means upper arm, forearm and hand on each side; head included. Pelvis, torso, thighs, shins and feet excluded from IMPACT termination. Independent foot-distance failure still applies. Detection at240Hz and reset at30Hz boundary unchanged; strict >2200N, selected-body peak recorded in replayer. Historical configs without floor_impact_bodies retain previous all-non-foot scope; new configs/replay metadata explicitly list selected seven bodies. No new physics/controller/learning settings, observation slots or loss terms.

Old impact2k run saved final0026843 at439,812,096samples, verified19,757,926bytes SHAeb9a8a62e10fdf8709a9ff935493a1e859d5ed0f42e2243e35ee776def30551d. Resume this exact checkpoint with optimizer/normalizer/counters.512world targeted tests passed:2500N injected separately into each of15 bodies triggers exactly the seven selected bodies;2199.9/2200/2200.1N strict threshold, combined failure charged once, unchanged140inputs and60finite policy steps. Recorded15tick test episode ends from FOOT DISTANCE with zero selected-body contact on terminaltick, valid force/body metadata and exact remaining charge. Physical sensor/backend is unchanged, so previous~2% physics overhead measurement applies to the same measurement mechanism; no new benchmark claimed. Evidencearms-impact-{parent,test}.json, scriptLabs/MimicKitTraining/test_arms_head_impact.py. Other torque experiment/pod and shared viewer code untouched.

Launched20261015_044930_pose_height_arms_head22_512 PID4292 on same a34l6y5ngp6s6a. Restored439,812,096samples/offset26844, optimizer/normalizer unchanged; live439,975,936samples and advancing, no numerical/backup errors. Hard stop1792043372.0095425 =07:49:32Warsaw, same guards and165s reserve. First26844 checkpoint verified19,489,276bytes SHAbe8d976c91e92ff30d94f762ddfebf5cd12967c3489dd5749eced5ed5a232cf7. Source727337bytes SHA81f392c03b26bbe80a8dff77053b94e4d9a1b41e230e626463e3df1c2c158a3b readback verified atarms-impact/source.zip. New observersbridge11828/dashboard24836, label2026-10-15_04-49-30_Pose_height_arms_head22_512_1024x1024; only old owned dashboard23608 stopped. No new pod/schedule, no changes to parallel torque run or UE/main journal.

Final verification:441,466,880samples/checkpoint26944, S3latest_verified read independently (19,488,401bytes SHA24ed2d1ab0fb6d221706d88c4dfbd7344868b8f84b89ee206323db1886e6e70a). Replayer selected new run, exact2200N and seven-body scope confirmed in replay metadata, every reported body belongs to selection. Latest15tick replay ends from distance only with zero arm/head floor force on terminaltick; remaining charge verified numerically. Allfour original loss terms, total/train/test and episode seconds have actual datedTB points; visible new run checked. Test mean0.2295s, train0.3100s at26944; no recovery claim. No extra evaluation or backup-cadence change. Handoff/source/evidence retained underarms-impact prefix.

## Previous - non-foot floor impact termination, October 15

User approved the proposed 2kN normal floor-contact threshold on every body except left/right feet. Resume latest checkpoint of current distance175 run, retaining its weights/optimizers/normalizers/counters, 1.75x full3D foot-distance limit, valid floor-start pool, original three losses and all other learning/controller/physics settings. Previous run saved final0025442 at416,858,112samples; verified19,771,527bytes SHA98be6f047f031e02657dd627444edc186c9bcc3eae01830648905b2d35d9d4fd. Evidencefloor-impact-parent.json. Renew existing three-hour runtime on the same owned L4 when launching, per standing restart instruction; no new pod/schedule.

Optional track_ground_contact_peaks backend flag accumulates normal ground-force magnitude per body across all eight240Hz physics substeps, entirely on GPU inside existing CUDAgraph. Buffer clears at each30Hz control tick. Installed Newton's MuJoCo contact export omits tangential friction; values are normal force in N, not impulse or full friction-inclusive force. Strictly greater than2000N fails; feet exempt, hands included, no grace period. Detection covers every substep; reset happens at the following policy-tick boundary, not mid-substep. Union with foot-distance failure charges termination_remaining=(60-t)*current weighted base loss once even if both fail. Reason0none/1distance/2impact/3both. Peak body is strongest non-foot contact during that policy tick. Reset clears displayed state per agent. No observations added.

Isolated tests passed: known screenshot24137 reconstructed with CUDAgraphs, forearm2759.9155N at policytick5, max body-position difference0.0212mm versus original recording. Threshold below/equal/above, foot exemption, hands, simultaneous failure cost, ticks1/30/60 accounting, partial reset isolation, unchanged140inputs, replay arrays and original four loss terms all verified.512world alternating graph benchmark: baseline9.870ms/controltick, measurement10.063ms, approximately1.95% extra physics time (not end-to-end training overhead).20.99s bounded test. Evidencefloor-impact-test.json, scriptLabs/MimicKitTraining/test_floor_impact.py; isolated source treeimpact_test, no training during tests.

Important consequence, disclosed to user: this strict all-non-foot rule can terminate immediately on floor starts. The known rollout also exceeds2kN on ticks1/2 before its forearm hit; latest-checkpoint test replay ends at tick1 from pelvis3653.29N. No silent threshold relaxation, warmup exemption, reset-pool alteration or success claim. Replayer retains plain name/value overlay and adds actual per-tick non-foot peak force/body and termination reason; missing historical data stays absent. Existing termination_remaining chart captures both failure causes; do not add a fifth loss for the same charge.

Deployment and live verification complete. Run20261015_042109_pose_height_impact2k_512 PID3912 on same owned L4a34l6y5ngp6s6a. Restored416,858,112samples/offset25443 with optimizers and normalizers; config comparator accepts only authorized impact/environment-sensor flags. Existing guards renewed to1792041643.6787767 /07:20:43Warsaw;165second final-save reserve unchanged, no schedules. Source723904bytes SHA67de69e7a10e0cbb6c3b9914a0ce26586196c93cc6e6d297e8e76814f30d3d82 uploaded/readback verified atfloor-impact/source.zip; includes patched upstream backend, pipeline, tests and local viewer files. Each new checkpoint includes actual backend source too. Firstcheckpoint25443 verified19,482,326bytes SHA854f1a303bedfd05c46241c7c190beb3ca446fc76569325e7a523e5a8eae466e; S3latest_verified independently retrieved. No numerical/backup failure flags; graph enabled.

Observersbridge5616/dashboard23608; stopped only previous owned dashboard16268 after its bridge exited. DatedTBlabel2026-10-15_04-21-09_Pose_height_impact2k_512_1024x1024. Allfourloss terms/total/train/test and episode-seconds charts verified through read-only API and visible dated run. Replayer selected new run, plain overlay shows actual tick2 left-hand3393.977N, both distance+impact failure, single remaining charge. Numerically remaining0.8465265 equals58times base0.01459528. First evaluation averages2.7415ticks/0.09138s; first training average2.9934ticks/0.09978s, so very short episodes are real threshold failures, not a replayer defect or evidence of recovery. Evidencefloor-impact-{test,live,output-verification,source-receipt,observers}.json. Main journal/UE/PHAT/BP/D-S untouched.

Follow-up live check25513/418,021,376samples confirms advancement, ~1.693e4transitions/s over recent updates, running CUDAgraph and no error flags. Early training mean episode length6.071ticks (still short); initial test above remains the last published test until the next normal100-update capture. No extra evaluations or changed save cadence.

## Previous - isotropic foot distance, 1.75x, October 15

Read-only impact diagnosis requested for screenshot rollout24137/tick5. Saved checkpoint0024137 contains exact14-frame deterministic replay but no contact forces. Isolated1world reconstruction from recorded initial root/joint rotations and matching actor, no training settings/state/deadline changes. Normal reset zero velocities preserved. Baseline CUDAgraph replay maximum body-position error0.0212mm versus saved; instrumented240Hz replay0.0269mm,0.00769mm versus baseline. Diagnostic18.52s total,104physics substeps, no second trainer/pod. Right forearm peak2759.942N at0.1375s/substep33/policytick5; hand852.316N at0.183333s/substep44/tick6; upperarm0N over saved episode. Values are reconstructed, not originally recorded. Installed Newton SensorContact docs say N; inspected solver_mujoco contact-conversion kernel exposes NORMAL force only (tangential omitted), so do not call this full contact-force vector magnitude including friction. Accurate floor impact termination should use this normal force at physics substeps; no impact termination/threshold implemented yet. EvidenceSaved/MimicKit/arm-impact-24137.json and remote matching.npz; scriptLabs/MimicKitTraining/diagnose_arm_impact.py. No trained recovery claim.


User initially said restart fresh, then immediately corrected to "restart from same point". Explicitly acknowledged resume from SAME pre-termination final23736 of20261015_023513_pose_height_feet_512, retaining weights/optimizers/normalizers/counters. Do not resume latest25014 and do not start fresh. Prior remaining-cost run stopped gracefully at409,845,760samples/final25014, verified19,685,275bytes SHA07878abb326da63c028e8d40fed1f654085d0fe1a30d29e5a0ad51decb356363.

New feet_distance_multiple=1.75 selects Euclidean 3D distance between left/right FOOT BODY ORIGINS, using the approved standing target's same full3D distance as reference. All directions count; invariant to whole-body translation/rotation, independent of pelvis orientation. It is not collider-edge clearance. Legacy lateral metric/calibration retained only for historical compatibility; new threshold derived from target FK, old lateral threshold and penalty weight are unused in this mode. Strict exceedance ends episode, equality allowed. Same metric filters precomputed floor poses and evaluates live failure. Keep50/50front/back and original noise; regenerate pool once at startup. Remaining-frame charge, original three losses/weights and all actor/controller/physics/PPO settings unchanged. Metadata records distance metric/reference/threshold/multiple, removing misleading lateral threshold labels for this mode.

512world numerical/physics tests pass: 3D norm against independent squared-distance calculation; translation and rigid axis/sign rotation invariance; each XYZ direction beyond limit fails; strict threshold equality; unchanged base losses, remaining charges at1/30/60ticks, partial resets/accounting/replay. Target foot distance0.2561287284m;1.75x limit0.4482252747m (44.82252747cm). All8192candidates accepted;16384resets all valid/grounded,8218back. Test same actor:32/512firsttick failures versus282/512under old lateral rule;15793failures over60ticks,0timeouts, selected replay2ticks. No recovery claim.

Continuation20261015_034302_pose_height_distance175_512 PID3119 on same SecureL4a34l6y5ngp6s6a,$0.59/hour. Correct prior388,907,008samples/offset23737 restored with optimizer/normalizer and exact remaining config match. Live23747/389,087,232samples,~1.53e4transitions/s. Fresh3h deadline1792039383.7871332=06:43:03Warsaw, existing guards/165s reserve, no new pod/schedule. Firstcheckpoint23737 verified19,432,873bytes SHA4d361e2c7a25c809759ecaa06c2c1e11ba19dc2b8e7ce513797c78d7d070385c. Source684048bytes SHAef0a6878f196cf52e41a9786d62a6d893531e771ec9ea17358a65fd3e1c5ca9b verified atisotropic175/source.zip. Local bridge5028/dashboard16268; previous dashboard4276 stopped after parent completion. New datedTBlabel2026-10-15_03-43-02_Pose_height_distance175_512_1024x1024. Live UI/telemetry verified: TB new dated run present, remaining-cost and episode-seconds charts have actual points; replayer selected new run with allfour per-tick terms+total. Actual replay distances23.5830cm,34.9451cm,59.5068cm: first2poses within44.8225cm, failure on tick2 beyond limit. Terminal charge equals58times current base per-tick loss. S3latest_verified independently retrieved. Previous evaluation summary wording correction now loaded in new process; no stale no-cost text. Evidenceisotropic-*.json. Main journal/Unreal/PHAT/BP/D/S untouched.

## Previous - charge unplayed ticks on width failure, October 15

User requested early termination charge remaining frames and resume from BEFORE termination was added. Use final23736 of20261015_023513_pose_height_feet_512 at388,907,008samples, SHA43315dc4d3f3ddb1f76ade2fb72b41f1a91ca9d68ecffde151abdbf411e8edd1 verified on pod. Do NOT resume from the policy that learned immediate failures. Latest valid-start run stopped gracefully and safely saved final24568/402,538,496samples, SHA c2aabeff785d56f0c4fee1c466cf8001f22f54932dcff90c0617f0fb06083cf2; evidence retained.

Keep valid reset pool, same1.25x31.88925982cm width limit and strict failure, no spread penalty. For failure at tick t of60: retain the original three per-tick weighted losses and add a separate termination_remaining=(60-t)*sum(current three per-tick losses), once on the failure tick. No extra charge on normal ticks or timeout. Original losses already divided by60; no second division. This charges the unplayed part as if the failure pose stayed frozen. It is not a prediction of future poses. Constant per-frame cost now produces the same undiscounted episode total for any failure tick or full horizon. Stock PPO gamma/failure bootstrap remain unchanged; no claim that all incentives or learning are solved.

New explicit termination_remaining_cost config/CLI flag; historical no-cost runs retain their original meaning. Replayer discovers the new fourth term and records its exact terminal-tick charge; TB maps loss/termination_remaining and retains episode train/test seconds. Original inputs, body target, weights, controller/physics/network/PPO unchanged. 512world test passes: exact remaining costs at ticks1/30/60, unchanged three base terms, strict threshold, zero extra cost at timeout, valid16384resets, partial reset isolation, completed-loss accounting and finite140inputs. Actual resumed replay independently confirms remaining charge1.087472677 at failuretick1 equals59times the three base terms, and reward equals negative sum of allfour.

Resumed20261015_031912_pose_height_remaining_cost_512 PID2688 on same L4a34l6y5ngp6s6a,$0.59/hour, prior388,907,008samples/offset23737 with optimizer/normalizer restored and exact config check apart from three authorized flags. Live23777/389,578,752samples; initial mean episode1.54ticks, no recovery claim. Fresh3h deadline1792037954.255297=06:19:14Warsaw, existing guards and165s save reserve, no new pod/schedules. Firstcheckpoint23737 verified19,431,549bytes SHA0172a81c8a6008ca34555c7ff4441a61bbd247d18737f1a0778ed7b8dfb73e0c. Source682268bytes SHA4f4dca190a6feaf78f5d3916550ff89534b75b116c20c44b2c7e4f9b8459da67 readbackverified atremaining-cost/source.zip. Local bridge23068/dashboard4276; prior dashboard14732 stopped. New datedTB run checked, termination_remaining and episode seconds verified by read-only API. Replayer new run selected, terminaltick visibly shows allfour terms+total.

Metadata-only caveat: train.py overwrote the correct Recorder terminal description in the evaluation.json summary with old no-cost wording. Actual replay.npz metadata, reward, loss arrays and displayed values are correct. Future-launch source fixed and uploaded; active process is deliberately not restarted for that text-only field. The handoff includes corrected train.py. Use actual termination_remaining_cost flag/loss data, not that stale evaluation summary sentence. Dedicated evidence remaining-cost-*.json. Main journal/Unreal/PHAT/BP/D/S untouched.

## Previous - precomputed valid floor starts, October 15

TensorBoard episode-length restoration: mapping train/test episode lengths from stock event ticks to seconds (30Hz) now applies to all objectives, previously AMP-only. Local dashboard restarted as PID14732 to backfill existing current-run events and keep updating; remote trainer, bridge, deadline and learning untouched. Visible filter includes episode/train_seconds and episode/test_seconds alongside losses. Values verified against original events via read-only API.


User explicitly requested precomputing starting poses and keeping only those inside the foot-width limit. This supersedes the previous no-reset-filtering restriction. Generate8192 candidates once at environment startup with the same +/-5degree joint noise and original joint limits. Check each in both front/back orientations against the SAME31.88925982cm pelvis-local lateral limit; retain6908 and reject1284. Uniformly sample retained joint poses and independently choose50/50front/back at reset. Each orientation has its collider-based2mm floor clearance precomputed. Separate deterministic seed20261015; regeneration is reproducible, no pool data added to actor inputs or large checkpoint payloads. Startup cost1.09s measured. No per-reset rejection or placement FK; upstream FK for synchronizing body states remains necessary and unchanged.

Actual512world test:16384 resets,0over-limit starts,8342back, finite bodies, floor clearance correct, partial resets leave other agents untouched. Strict below/equal/above threshold, unchanged three losses, no additional failure cost, PPO failure continuation0, completed episode accounting and first-terminal replay all pass. Test initially caught upstream's required body synchronization FK; corrected the instrumentation to distinguish it from candidate generation, without changing runtime physics.

Important limitation: filtering valid starts does NOT prevent the existing learned policy from crossing the limit immediately. Latest checkpoint test:380/512 first-tick failures,23917failed episodes across60ticks,0timeouts; selected replay1tick. All initial widths valid (maximum31.888875cm). No silent grace period, extra penalty, threshold relaxation or controller modification. Shorter negative-loss episodes remain favorable under the user's explicit terminate-only choice. Loss decreases alone must not be claimed as recovery progress.

Resume from verified final23837 of20261015_025754_pose_height_spread_stop_512. Continuation20261015_030447_pose_height_valid_starts_512 PID2282 on same owned SecureL4a34l6y5ngp6s6a,$0.59/hour. Only reset-pool flag added; exact remaining config comparison required, weights/optimizers/normalizers/counters restored. Fresh3h runtime per standing restart instruction: hardstop1792037089.2170975 /06:04:49Warsaw,165second final-save reserve and existing live guards. No new pod or schedule. DatedTB label2026-10-15_03-04-47_Pose_height_valid_starts_512_1024x1024; bridge2912/dashboard26668, previous owned dashboard10004 stopped. New source674894bytes SHAe8f607c36aec760d02a78b668e52186858081f40c945972c6abec184ec0ea908 uploaded/readback verified atvalid-reset-pool/source.zip. Dedicated evidencevalid-pool-*.json. Live verification passed: restored390,561,792samples/offset23838, advanced23888/391,397,376samples at~1.67e4transitions/s. Three original losses plus total present via read-only TB API; new dated run checked in visible TB. Replayer selected new run with3terms, noiseless capture and actual1tick failure, no joined resets. First checkpoint23838 verified19,430,392bytes SHAd68396d201a41c03049af73119e5972e8919d68a4c3f023aa38be56e88cb8a0a on S3. Mean episode1.23ticks; this remains an ineffective recovery policy, not a recovery success. Runtime pool startup1.46s. Main journal/Unreal/PHAT/BP/D/S unchanged.

## Previous - strict foot-spread early termination, October 15

User requested replacing the spread penalty with early termination at the SAME31.88925982cm pelvis-local lateral width limit (1.25x reference). Explicitly warned that negative losses make early termination advantageous; user chose "Terminate only, no extra cost". Respect that choice: no extra failure loss, no surviving-time bonus, no grace period, no reset-noise filtering, no terminal-value shaping. Stock DoneFlags.FAIL=1 and stock PPO failure continuation value0. Foot penalty removed from active loss terms/weights; original body_pose_mse/head_height_band/pelvis_height_band remain exactly unchanged, including original1/60 per-tick normalization. Thus early episode totals are partial sums, NOT comparable to previous full-horizon totals as evidence of learning.

Strict check runs after each physics/control tick: projected absolute foot separation along actual pelvis localY > threshold triggers FAIL; equality allowed. Other worlds continue independently; failure wins if threshold also exceeded at timeout. Completed-loss accounting now includes failures; resets clear per-world failure/loss accumulators. Recorder retains only first episode and includes true terminal flag/reason, threshold, three per-tick losses and exact shortened duration. Historical four-term captures/configs remain readable. Resume config migration only permits the explicit termination flag while requiring the same calibration and all prior settings. Source backed up/readback verified atfeet-termination/source.zip,673530bytes SHA37ac45aec256f3c9974a5f9bdcdac5e4355ffbb1a70cce67950d984a999a1df3.

Numerical/actual512world tests pass: below/equal/above/crossed-lateral threshold, large forward displacement ignored, no added foot loss, zero PPO failure value, exact original three terms/reward, timeouts, asynchronous resets and episode accounting, finite140inputs, first-episode replay cut. Important observed consequence disclosed BEFORE launch:71/512 noisy starts already wider than limit (median25.2876cm,max39.7595cm);296/512 fail first tick under latest actor (median33.0046cm,max48.0035cm). Over60ticks test recorded21,961 very short failures and0timeouts; selected replay is one tick. No hidden workaround introduced; strict rule intentionally retained as requested.

Parent run gracefully saved final23736 at388,907,008samples,checkpoint19,732,202bytes SHA43315dc4d3f3ddb1f76ade2fb72b41f1a91ca9d68ecffde151abdbf411e8edd1. Continuation20261015_025754_pose_height_spread_stop_512 PID1685 on SAME owned L4a34l6y5ngp6s6a,$0.59/hour. Restores learned state/counters, fresh physical episodes. Renewed3h hardstop1792036677.3415422 /05:57:57Warsaw, existing local27844/remote204guards and165second save reserve; no schedule/new GPU. New datedTB label2026-10-15_02-57-54_Pose_height_spread_stop_512_1024x1024, bridge2364/dashboard10004; previous owned dashboard29024 stopped after parent completed. Live23747/389,087,232samples advanced with verified checkpoint23737. Mean episode1.398ticks demonstrates very short failures, not recovery. Subsequently stopped gracefully for user-authorized valid reset filtering at final23837; final checkpoint19,448,683bytes SHAd79e7997f0da88596eb49b38c0c2153e03098b9f542bcfac3fe21273a7473129 verified on persistent storage. Dedicated evidencefeet-termination-*.json and valid-pool-parent.json. Main journal/Unreal/PHAT/BP/D/S unchanged.

## Previous - pelvis-lateral foot separation, October 15

User requested an additional split penalty and resume, weight calibrated to20% of existing total. User corrected allowed width from1.5x to1.25x approved standing width. Uses absolute foot-body-origin separation projected onto actual pelvis localY (full pelvis rotation, including tilt); no forward/back or pelvis-local vertical separation penalty. Squared excess only, zero below limit. Reference width0.2551140785m; threshold0.3188925982m (31.8893cm). Existing body pose/head/pelvis terms,140inputs,512worlds,2second horizon, reset distribution and controller/PPO unchanged.

Previous run stopped gracefully at364,986,368samples/final22276; checkpoint20,559,179bytes SHA f571134d0ffc44ce43c3dcd60142fb8ebf770c1bb0c3720891f2dbbb5a729f60 verified. Four512world batches/2048deterministic episodes on this exact actor with unchanged noisy front/back resets measured old-total mean0.2466974594 and raw new mean0.3166556209m2. Frozen coefficient0.1558143567092552 yields0.04933949187=20% old total; not dynamically renormalized during learning. No actor/critic gradient tuning or observation changes. Calibration source/weight stored with configs. Resume explicitly permits ONLY this additional config field, requires calibration checkpoint checksum on first addition, and exact same fixed calibration on later continuation; existing full config equality checks retained.

Tests passed: threshold/below/above/crossing, arbitrary whole-body rotations/translations, forward-back and vertical separation ignored, actual512world four-loss path against independent pelvis-matrix projection, unchanged old three terms, finite140inputs/60steps, partial reset isolation, exact reward and completed-episode totals,61frame replay with allfour terms+total. Four dashboard tests pass including the new term. No second training workload: bounded calibration ran after previous trainer stopped.

Continuation20261015_023513_pose_height_feet_512 trainer1074 on same owned L4 a34l6y5ngp6s6a,$0.59/hour, starts from364,986,368samples/update22277 with weights, optimizers, normalizers/counters restored; fresh physical episodes. Renewed three-hour hardstop1792035315.7761524 /05:35:15Warsaw, existing local27844/remote204guards and165second finalsave reserve; no new schedule/pod. New datedTB label2026-10-15_02-35-13_Pose_height_feet_512_1024x1024 because objective changed; history retained. Bridge7060/dashboard29024; previous owned dashboard10576 stopped after final telemetry. Source and calibration bundled tofeet-lateral/source.zip, SHA293c225b6c6086444a352c876ceed37d611f44eee53b8415c466948119dda1ca, readback verified. First new checkpoint22277 verified19,448,500bytes SHA61b34579fbde115cdc4846b2f88ddf6b4e3fff777d2e364af1b03f5014c6699a. Live22317/365,658,112samples at~2.25e4transitions/s, allfour terms nonzero, no numerical/backup alerts. Dedicated evidencefeet-lateral-*.json. UI verified: new run selected/playing, four per-tick name/value losses plus total. TensorBoard new dated run checked, loss/feet_lateral chart visible and allfour/train/total live points independently verified via read-only API. New total has an extra term, so it is not directly comparable to the previous three-term total. Main journal/Unreal/PHAT/BP/D/S unchanged.

## Previous - pose + height continuation, October 15

User requested resume ONLY pose-height for three hours. Height-only remains stopped. Latest final16350 restored from persistent storage:267,894,784samples,22,482,963bytes,SHA0aad92a7ef6502ad46e16b9242b546d5b39e705036f3eeca331c4b3b1cbccc6a. Weights, actor/critic optimizer state, normalizers and global counters restored; physical episodes restart. All three configuration equality checks passed; no input, target, reward, weight, reset, controller, PPO, cadence or retention change. One launcher validation restriction removed: height-band calibration now permits resume, with existing exact saved-config equality checks still enforced. Original height-band source bundle otherwise byte-identical; height-only code not deployed.

Old pod qjy94qxhccs256 remained EXITED; restart rejected for no host GPU capacity. Replaced with same-rate Secure L4 a34l6y5ngp6s6a at$0.59/hour; original pod/data preserved. Cached runtime and kernels restored rather than reinstalling; checkpoint downloaded cloud-to-cloud and checksum verified. New run20261015_011520_pose_height_bands_512_resume trainer586, SSH157.157.221.29:43603. Three-hour hardstop1792030522.913152 / October15 04:15:22Warsaw,165second final-evaluation/backup reserve; localguard27844/remoteguard204. Training window GPU ceiling$1.77 plus approximately149seconds replacement/setup ($0.025) and storage, not exact invoice. No schedules or second trainer.

Live check advanced16371/268,238,848samples at~2.18e4transitions/s; no failure/backup alerts. First resumed checkpoint16351 readback verified19,443,307bytes SHA79af90fe542cb4064ebf5dfa0e9b63e799c4ce736c3c782f7b7c815a59dd5e14. Original TB dated label retained for continuous history; resumed source appended, read-only API confirms all three terms plus train/total at samples beyond prior final. Bridge24804/dashboard10576. Replayer selected new continuation, playing noiseless rollout with all three weighted per-tick terms visible. Source664723bytes SHA531852fb3c1c62d8f4a86463f4f9a59df24b73270a085df956c3845c2a113572 backed up/readback verified atpose-height-resume/source.zip. Evidence Saved/MimicKit/pose-height-resume-*.json. No claim of recovered standing; continuation only. Main journal and Unreal/labs/assets unchanged.

## Previous - concurrent height-only comparison, October 14

User explicitly authorized a second experiment on the SAME GPU, keeping current experiment running. New comparison starts fresh with512worlds and identical policy/reset/physics/height targets/calibrated weights; only body-pose MSE removed. Exactly two loss terms head_height_band/pelvis_height_band plus total, per tick averaged60steps. Body pose calculation is skipped, not evaluated and multiplied by zero. No implicit heading/rotation penalty remains, although actor observations stay unchanged. Same shared hardstop23:57:59Warsaw; no new GPU rental or extension. Comparison uses isolated /workspace/mimickit_trial/pipeline_height_only copied from existing pipeline; original running code files untouched, including files snapshotted by its periodic backups. Per-run training outputs/checkpoint prefixes/observers independent; shared root stop.request stops both, per-run stop.request can stop one.

Preflight existing trainer4099 advancing1080/17,711,104samples at~2.44e4transitions/s; GPU980MiB/23034MiB with92%utilization. Capacity permits concurrent memory use; throughput contention expected. Single-process mp_util uses no network rendezvous, so common nominal master port is unused. One temporary512world height-only contract test precedes second trainer; no third persistent GPU workload. 512world test passed:140inputs/60ticks, body-MSE helper replaced with throwing stub and never called, exact two weighted height terms/reward/replay, partial reset isolation. Source667734bytes SHA5d46231c8e70e5b36f3c953eb5dad14a5634014cc6205bb8945ff23490b21950 verified atheight-only/source.zip. Second run20261014_181426_height_bands_only_512 PID4375 alongside original4099, noresume, same existing deadline1792015079.2680929. Launched directly with exact-one-existing-owned-trainer preflight, verified test receipt and immutable code directory; normal single-run launcher remains unchanged. Windows Python lacks tzdata, so initial naming attempt failed before any launch; used explicit Warsaw October14 UTC+02 naming for successful single launch. New observersbridge29568/dashboard1524, independent original observers retained. Label2026-10-14_18-14-26_Height_bands_only_512_1024x1024; TBfilter[Hh]eight_bands shows both. Agent YAML matches original exactly; original world_pose.py still byte-matches its checkpoint. Live verification passed: original advanced to1400/22,953,984samples at1.26e4transitions/s; new run40/671,744samples at1.30e4transitions/s, no numerical/backup alerts. Fresh prior_samples/iteration_offset both0. New checkpoint0 S3 readback verified19,443,010bytes SHA2d852b95b2c898dc17564fb584115292a496731f2a81ad0df2410fc96ef0fb70; original checkpoint1300 independently verified. Actual recorded replay head/pelvis penalties independently reconstructed from world heights, bands and weights; their sum equals negative reward. Replayer selected new run and shows exactly both per-tick height terms plus total, no body MSE. Read-only TensorBoard API confirms new train/test/head/pelvis/total scalars; both dated experiment labels visible. Evidence Saved/MimicKit/height-only-verification.json. Concurrent runs approximately halve per-run throughput versus the single-run baseline; same GPU hourly rate and deadline. Compare shared height terms rather than totals across different objectives. No learned recovery success claimed.

## Previous - worst-body pose plus head/pelvis height bands, October 14

User confirmed latest checkpoint is ONLY for one-time calibration, then FRESH weights/optimizers/normalizers/counters and new SIX-HOUR runtime. Three terms every tick, averaged across existing60ticks: unchanged worst-body combined world position+orientation MSE, plus head and pelvis squared vertical distance outside [0.80,1.10]*their respective target world heights. Zero inside band, penalty above or below. No dynamic weight normalization. Inputs140,512worlds,reset noise/front-back distribution,target,fixed heading,network,PPO/controller/physics unchanged. For new runs HUD/TB show body_pose_mse,head_height_band,pelvis_height_band,total (the old pose position/orientation split is grouped as the original single term).

Prior worst-body run stopped gracefully100,810,752samples/6153; final6152 verified20,543,116bytes SHAb3bf24078fdc06d7f1f526155c843b356f53b3eb6c9685998144a60505499734. Calibration uses that exact final policy/normalizer with deterministic actions, four batches of512noisy floor resets=2048episodes,995back/1053front,all60ticks. Mean old pose loss0.60598512; raw head band0.38195022m²,pelvis0.13575143m². Frozen weights head0.396638805991461,pelvis1.1159829406278405 make each weighted term0.15149628=oldloss/4 on calibration set. Later proportions naturally change as training changes the pose. Head target1.29922223m,band[1.03937778,1.42914445]m;pelvis target.85857230m,band[.68685784,.94442953]m.

Validation passed band boundaries/interior/both outside directions; unchanged140inputs/60ticktimeout; finite2048episodes; exact weighted reward accounting and actual61-pose replay with allthree terms+total. Checkpoint model is never loaded into the NEW training process. Evidenceheight-band-calibration.json includes target/checksum/batchmeans/scales/tests. No new pod/schedule/storage deletion or unrelated edits. New20261014_175757_pose_height_bands_512 PID4099, same owned qjy94qxhccs256 SecureL4$0.59/hour, no resume argument. Six-hour hardstop1792015079.2680929 /23:57:59Warsaw, existing165second finalsave reserve and live local28496/remote190guards. GPU ceiling$3.54 from renewed window plus preceding preparation/storage, not exact billing. Observersbridge2172/dashboard30580; datedlabel2026-10-14_17-57-57_Pose_height_bands_512_1024x1024. Source664724bytes SHAb24f1db5f5869d2055346cc8f764725499bb4809233c6f50483396c48face66e verified atheight-bands/source.zip. Actual agent YAML exactly unchanged from prior worst-body run. Live verification passed: zero prior_samples/iteration_offset, advancing70updates/1,163,264samples at~2.56e4transitions/s observed. No failure/backup alerts. Checkpoint0 verified19,443,106bytes SHA8854558d0856b58d4ebc4d992e762a566668ee4d461a8094364bf0c5037b5460, S3latest_verified retrieved independently. Actual replay61poses finite; allthree weighted terms reconstruct recorded reward; head/pelvis penalties independently recomputed from recorded world heights/bands/weights and match. Replayer explicitly selected new run,playing with allthree+total changing eachtick; read-only TB API confirms train,test,body_pose_mse,head_height_band,pelvis_height_band,total. Evidenceheight-band-verification.json. No claim of learned recovery; scales calibrated on old policy, fresh policy has a different initial loss.

## Previous - worst-body world pose MSE, October 14

Read-only diagnosis of user screenshot iteration1000/ticks16–17: reconstructed all body errors from exact checkpoint1000 replay using independent NumPy/SciPy rotation matrices; recorded loss agrees within3.88e-9. Selected body switches right_thigh to right_upper_arm at17. Tick16 position1.439108e-3/orientation1.147696e-2/total1.291607e-2; tick17 position6.770623e-3/orientation5.358431e-3/total1.212905e-2. Arm position already6.767819e-3 at16: no positional jump. Individual displayed components jump because selected body changes; total decreases6.1%. HUD position label is component of worst COMBINED body, not maximum positional error independently. No training/config/UI/deadline changes. Evidence Saved/MimicKit/worst-body-tick16-diagnosis.json.

User requested restart using maximum MSE so the worst limb must improve. Interpreted explicitly to user: compute equal-weight position MSE plus orientation-matrix MSE for each physical body, select the largest combined body error every tick, then average over the same60tick episode. Both displayed component losses come from that SAME selected body, not independently maximized components. No temporal maximum, no change to fixed world heading/XY alignment, target,140inputs,512worlds,reset distribution,noise,network,PPO or controller. Fresh weights/optimizers/normalizers/counters and renewed three-hour window. Existing mean mode remains reproducible without --worst-body; new config explicitly records reduction.

Previous20261014_160747_world_pose_mse_512 stopped gracefully at38,764,544samples/2366; final2365 verified19,863,096bytes SHA563e703164a48c8ecf691169b3ef47f192b2b139c432784cc546e751da0fa4d6. Actual512world contract/physics/replay test passes, including adversarial separate-body maxima, zero target, world rotations, unchanged140inputs,60ticks and component-to-reward accounting. Test-only tensor shape mistake caught and corrected before launch; runtime reward unchanged by that correction. Source658934bytes SHAff61bcb300f62181538a61c648a45a3154a9bdc369edbf29fc135bcdc271f42f readback verified atworst-body/source.zip.

New20261014_163918_worst_body_mse_512 PID3562, same owned qjy94qxhccs256. Explicit --worst-body, no resume. New hardstop1791999561.4949558 /19:39:21Warsaw; existing guards reload this and165second save reserve applies. Three-hour GPU ceiling$1.77 excluding preceding preparation/storage, not an exact invoice. Observersbridge30580/dashboard10536; label2026-10-14_16-39-18_Worst_body_MSE_512_1024x1024. Live verification passed: prior_samples0/iteration_offset0, exact previous agent configuration, no failures, advancing90updates/1,490,944samples at~2.54e4transitions/s (observed, not controlled benchmark). Checkpoint100 readback verified19,438,418bytes SHA411c76bec8464f99e8b0c1682f8af01d7a0ca4143d4fabb9d0577141b57c14e7. Replay metadata explicitly maximum_combined_error; recorded per-tick position+orientation components exactly reconstructtotal. Fresh run selected/playing in replayer, dated TB component/train/test/total charts retain history. Evidenceworst-body-verification.json. Current losses cannot be compared directly to previous mean-body totals: reduction changed. No cloud allocation/schedules, no unrelated edits.

## Previous - fixed-heading continuous world pose MSE, October 14

User requested fresh weights/counters, AMP contribution zero and simple MSE across the whole episode. Explicitly confirmed BOTH world body positions and orientations with equal weights, and a NEW THREE-HOUR window (supersedes the five-hour window). Target remains approved grounded humanoid_jump105; all512 worlds retain50/50front/back noisy floor resets,5degree joint noise,stocksigma.05,2seconds/60ticks and timeout semantics. No velocity penalty, best-frame selection, tail or early bonus. No discriminator model/optimizer/history/replay buffer/inference is constructed: ordinary PPO uses the same AMP actor/critic settings after removing discriminator-only keys, including existing action-bound weight10 and network1024x1024.

Loss = mean_over_60_ticks[mean_over_bodies_xyz((world_position-current_root_XY-target_position)^2) + mean_over_bodies_3x3((world_rotation_matrix-target_rotation_matrix)^2)]. Weights1/1; position unitsm² and orientation matrix unitsdimensionless. No heading alignment, no roll/pitch alignment, no rootZ subtraction. Matrix error avoids quaternion sign/angle-wrap ambiguity. All orientation slots in the actor are now world body orientations too; same140input count, world root velocities/key-position axes and existing DOF velocities. Heading must be visible to the actor if it is penalized. No added time/history inputs.

512world physical test passes: zero target error, translation invariance onlyXY, all three rotation axes penalized, quaternion sign invariance, actual world orientation slots,140inputs/no discriminator,244back/268front initialization,60step horizon, exact per-step reward = negative sum of the two MSE terms divided60, completed-episode aggregates and partial-reset isolation. Actual noiseless replay conversion has both weighted per-tick terms plus total. Prior AMP two-row/floor-only recorder tests and3dashboard tests also pass. Training/test component totals isolated so evaluation cannot contaminate training charts. Normal loss/train,test plus loss/position_mse,orientation_mse,total charts; plain HUD automatically displays both current-tick terms and total. Evidence world-pose-smoke.json.

Old AMP run20261014_153921_amp_standing_world_512 stopped gracefully at16,334,848samples; final evaluated996 archive verified29,433,659bytes SHA0859ab9c5e856556e4977f50d233a081d5809fcfcf5b2b4fba495ea9da063753. New run20261014_160747_world_pose_mse_512 PID3119, same owned qjy94qxhccs256 SecureL4$0.59/hour. Fresh prior_samples0/iteration_offset0 confirmed. New three-hour hardstop1791997669.8461218 /19:07:49Warsaw; trainer reserves165seconds for final evaluation/upload. Both existing guards live (local28496/remote190) reload this cutoff. No schedules or second GPU workload. GPU ceiling from launch$1.77; preparation before launch additionally billed, not an exact invoice.

Live verification: finite61-pose noiseless capture with two recorded per-tick terms andtotal; replay sigma0,training.05. Ordinary PPO config differs from previousAMP only in removing discriminator settings/net and changing agent type. First checkpoint0 verified, subsequently100 verified19,437,914bytes SHA56eb95c4f6cfa80dd18c26b41b8bb1136bb972e18d2e229376c923f1cb98bc4c; S3latest_verified matches local receipt. No numerical/backup failures. Training reaches2,637,824samples; ~2.5e4transitions/s observed, not a controlled benchmark. TB read-only API confirms allfive charts:loss/train,test,position_mse,orientation_mse,total; latest train.765395,test.758547, component total.760137 (different averaging windows). No recovery claim. Replayer explicitly selected new run, playing with tick-varying values; TensorBoard datedlabel2026-10-14_16-07-47_World_pose_MSE_512_1024x1024 preserves history. Observersbridge27248/dashboard4124; old dashboard17104 stopped after old bridge exited. Evidenceworld-pose-verification.json; launch/name/observer/manifest receipts adjacent.

Source646310bytes SHA7577a5a024e372063e77505417a549aff89f978bf54c6e891a81f9abb4589af7 uploaded/readback verified atworld-pose/source.zip. No main-journal/Unreal/PHAT/Blueprint/D-S changes. No new pod/schedules/storage pruning or save-cadence changes.

## Previous - AMP world-body discriminator, October 14 15:39 Warsaw

October14 live learning question: user's replayer was still displaying iteration0/16,384samples (CUA verified) while training had reached420/6,897,664samples. Refreshed latest capture; do not diagnose policy inactivity from stale playback. Latest local replay400 (front start) has measurable body movement: final-second mean body displacement.007224m/tick; head height.1838→.4144m, pelvis.2301→.1233m. This is NOT floor recovery and not a matched-reset learning comparison. Recent discriminator agent/reference accuracy both1.0; imitation reward~.135–.178; discriminator loss declines~.538→.482. Supports easy separation of floor episodes from static upright reference, NOT proof of a flat reward landscape or the exact cause of stalled learning. Stock BCE+regularization discriminator loss is not pose error; PPO receives scalar imitation rewards, no differentiable physics gradient from target pose. No training settings/deadline changed.


User requested a fresh five-hour run,100% floor starts, world-only discriminator values and the corrected standing pose. Clarified/approved all-body world positions/orientations/linear and angular velocities, aligned ONLY to latest pelvis XY and heading; preserve world height and roll/pitch. No local joint rotations/DOF velocities in discriminator. Actor observations remain140, discriminator675=3frames x15bodies x(3pos+6orientation+3linearvel+3angularvel). All3history samples use one common latest heading/XY frame, retaining motion over the window. Native Newton body velocities used; no finite-difference estimate. Static reference validated identical across frames and its discriminator observation computed once/reused, zero demo velocities. Stock discriminator hidden1024/512, actor/critic1024/1024, all optimizer/reward/controller/physics settings unchanged.

All512 worlds now reset to noisy floor poses, independent50/50back/front with existing5degree joint noise and collider clearance; upright cohort empty, floor timeout60ticks/2sec. No upright replay is fabricated; deterministic floor replay remains sigma0, training sigma.05. Floor-only recorder regression passes; previous two-row behavior preserved. World-state tests pass globalXY/yaw invariance, sensitivity to height/roll/pitch/velocities, quaternion sign invariance. Real512world smoke passes140/675 dimensions,244back/268front first reset,partial-reset history exact, unchanged floor-only horizon and finite states. Evidence amp-world-bodies-smoke.json. Local full environment import unavailable (gymnasium); representation and physical tests ran successfully in pod runtime, recorder tests also local.

Target is the USER APPROVED humanoid_jump frame105 landing pose, ankles flat preserving foot yaw, left knee straightened1.374889degrees with user's explicit approval, ankles recomputed and common root height adjusted so both sole surfaces are at ground (max corner residual1.83e-8m). No other joint edits;61identicalframes at30Hz. Source/pose report amp_standing_target.json and generator Saved/MimicKit/amp-standing/build_grounded_target.py. This is the desired reference, not a claim of learned stability/recovery.

Prior noiseless trainer2030 stopped gracefully at55,672,832samples; final3397 verified27,303,051bytes SHAacdca0597b0ab8d94e3d32f3849a76eb7d730ed65f714134cf25ed80a57ae432. New run20261014_153921_amp_standing_world_512 PID2672 on same owned qjy94qxhccs256 L4$0.59/hour, NO resume flag: fresh models/optimizers/normalizers/counters. Five-hour hardstop1792003162.7338574 /20:39:22Warsaw,165seconds reserved for final evaluation/checkpoint/upload. This supersedes indefinite authorization. Both live guards reload bounded control (local28496,remote190); no schedule/newpod. Five-hour GPU ceiling$2.95 from launch, preceding preparation billed separately. Live verification passed: fresh prior_samples0/offset0; advancing iteration160 at2,637,824samples (~1.73e+04transitions/s observed, not controlled benchmark). Floor-only deterministic61-pose replay finite and per-tick losses equal negative recorded AMP rewards. Browser playing new run; same TensorBoard page shows dated old/new runs and fresh charts. Checkpoint0 readback verified29,193,348bytes SHAcb9cf5643ecc017d5dd5643935153c61f4825a0f0a6a98490254dc5a6fc51533; first background backup took about144seconds with no reported error, while training continued. Latest verified receipt/evidence amp-world-bodies-verification.json; independent guards still active. Bridge4132/dashboard17104; dated TB label2026-10-14_15-39-21_AMP_standing_world_512_1024x1024 retains history alongside old run. Agent configuration equality verified against previous run.

Source649674bytes SHA155bb789a03ef144debb73d7518a0faeedea8dfa221b23a0fc99cd824c3d00e6 uploaded/readback verified atamp-standing/world-bodies-source.zip. Existing old source/checkpoints retained; no pruning or save cadence changes. Keep this branch out of ProjectJournal.md; no Unreal/PHAT/Blueprint/lab edits.

## Previous - AMP static standing, October 14 14:15 Warsaw

October14 noiseless replay requested: changed viewer capture back to existing stock TEST-mode rollout, both floor0/upright410. TEST uses actor distribution mode (no sampled action perturbation); training sigma remains.05 and floor reset pose noise remains unchanged. IMPORTANT correction to earlier journal/explanation: upstream _rollout_test checks an episode count PER ENVIRONMENT, not32total; it already completes every world. Earlier assertion that upright failures could end stock test before floor finishes was wrong. No additional physics rollout or stock test count change is needed. New AMPTestCohortRecorder only records during test; captures discriminator observations for two rows and scores their completed episodes in small batches using existing frozen discriminator, without optimizer/normalizer updates. Both per-tick reward arrays retained. UI explicitly distinguishes replay sigma0 and training sigma.05. Local and remote CPU tests pass early upright failure, exact reward scoring, training capture disabled and preserved historical training recorder behavior.

Graceful reload disclosed: prior rows trainer1788 finalized2857 at46,825,472samples; verified final SHA65cb20a7e4368225a266b6427b22db2254ae83145538653748949ce98adb823b. Continuation20261014_141524_amp_static_standing_512_noiseless trainer2030, same pod/configs/indefinite deadline. Actor/critic/discriminator optimizer, model and normalizers/counters restore; physical episodes and discriminator replay buffer restart as before. Target remains the existing hybrid; separate approved-looking foot-flat candidate has NOT been substituted. Same TensorBoard label accumulates continuation source. Live verification PASSED: capture2958 includes finite61-pose floor0/upright410 episodes, each sigma0 vs training.05; per-tick negative imitation rewards exactly match captured reward arrays. Browser selected new run and upright row, playing with tick-varying losses and explicit replay/train noise. Stock test took1.145seconds,512completed episodes; no extra physics pass. Training advancing2968/48,644,096samples, observed~1.45e4transitions/s (not a controlled benchmark). Checkpoint2958 verified27,171,522bytes SHAe2f67fad6ce6d750371322e39669fa0ed7ee0685afe2f2b04f7c372c5dde049d; same TensorBoard label confirmed49,135,616samples. Observers bridge13620/dashboard9264. Evidence amp-standing-noiseless-verification.json. Source643475bytes SHA6c9789459115ccbd8273b77f79920ea4090dd405bd0476aa71b8179b81cf3062 backed up/readback verified. Receipt amp-standing-noiseless-launch.json.

October14 user rejected stiff hybrid standing target and requested better visual candidate. Displayed original getup_facedown182, confirmed it is also stiff. Searched stock MimicKit motion archive using byte ranges (~1.25MB downloaded including index and six candidate clips, no full bundle). Preview candidate humanoid_jump frame105 after landing: unedited whole recorded articulation, arms lowered, feet centers25.6cm apart, knees26.6/25.7deg. Root XY/heading and floor display placement normalized only. Rendered front/side to Saved/MimicKit/amp-standing/landing-standing-candidate.png, pose/provenance adjacent JSON. Candidate is a moving clip frame; static balance NOT validated and it is NOT a new training target. Earlier jump2 preview rejected internally for pronounced backward lean. User must see candidate before a replacement; current trainer continues unchanged on existing hybrid target under indefinite authorization.

October14 14:52 upright replay added at user request. Each new capture now includes two actual-training rows: floor world0 and fixed upright world410, independent reset/terminal lengths and exact AMP rewards copied from their respective existing reward-buffer columns, no extra physics or discriminator forward passes. Stops upright recording at its first terminal, never joins multiple resets. Tests pass on local CPU and pod runtime for early termination before other row, reset isolation, distinct reward columns across PPO updates, converter rows and stock evaluation suspension. First real recording1456: floor60ticks/timeout3; upright58ticks/failure1; initial pelvis heights.1242/.8834m. Both visible per-tick loss arrays verified against their own raw reward arrays. Plain row dropdown below timeline labels cohort/world/ticks; overlay follows selected row, unrelated sword diagnostics hidden. Historical single-row files unchanged.

Recorder required a graceful reload, disclosed beforehand. Previous trainer1431 final1453 at23,822,336samples saved/verified SHA078cc884743f6f6104c400a8fc4e35938637ea2cf7435bd1d6ee284301384cfb. Continuation20261014_141524_amp_static_standing_512_rows trainer1788 starts offset1454 with weights, all three optimizer states, normalizers and counters restored; physical episodes and AMP replay buffer restart (existing loader limitation), no claim of bitwise uninterrupted training. Same configs, indefinite authorized runtime and same pod. First resumed checkpoint1454 verified SHA1d3191577ec048c98c3259a9da22a9e3d4a1243d507ed181a13ed55137c9376f. At1464 throughput~1.36e4transitions/s; observation only, not a controlled benchmark. Same TensorBoard run label with continuation source appended (verified sample24,657,920). Observers bridge26756/dashboard14152. Source archive642142bytes SHA2ac21c20583be1778aa1a07c2a48fc17efb23b7422b951565dbf608adf6071b7 verified. Receipts amp-standing-rows-launch.json/amp-standing-rows-verification.json. Training remains active; no deadline renewal, new GPU, tuning change, main journal or Unreal edits.

October14 replay history repair: server previously excluded last_batch_rollout whenever any archive existed; client only injected it while displaying latest, so selecting history removed newest. Concurrent history requests also cleared before awaiting then appended twice. Server now returns latest plus archives, deduplicating latest against matching archived step. Client builds options atomically, deduplicates capture IDs and rejects stale history/replay responses. Only local replayer server8021 restarted9308→29816; browser refreshed. Actual UI verified step2 selection retains1002/802/502/302; Refresh restores1002 with exactly5distinct entries. Synthetic server cases pass newer latest, duplicate archived latest and archive-only; JS deferred-reply test passes reversed response order, duplicate IDs and historical selection. GPU trainer1431 uninterrupted, update1020/16,728,064samples. Recorder STILL captures world0 only (floor cohort); user informed absence of upright replay is sampling bias, not missing upright training.102fixed upright/410floor unchanged. No new capture behavior or training restart in this repair.

**October 14 14:34 Warsaw — ongoing runtime explicitly authorized.** User said “no leave it ad vitam”: current AMP run continues until user stops it, with ongoing L4 billing $0.59/hour (~$14.16/day) plus storage. This supersedes the one-hour cutoff below for this pod/run only. Applied live without restarting trainer1431, observers or guards. Local and remote runtime_control.json carry until_stopped=true and hard_stop_unix=253402300799 (year9999 finite compatibility sentinel, because existing loaded readers reject Infinity). Both billing guards and observers reload that same control; no additional schedule/pod. Numerical safeguards, manual stop.request and checkpoint backups remain unchanged. Verified live status750/12,304,384samples, ~1.22e4transitions/s, samePID1431, trainer read new deadline253402300634 including its165second reserve. extend_runtime.py now exposes explicit --until-stopped; future bounded extensions reset the flag. Do not reset the deadline or restart a stopped/failed run without considering this latest user instruction; report failures rather than silently abandoning it.

Launch verified through update140 /2,310,144samples at~1.21e4transitions/s, no numerical/backup failures. Checkpoint100 verified27,145,147bytes SHA62f7984575e5685c403de61696397d232760fed8a8983d264dd13966b3619088 on existing volumeaj7d2jzwuq. Final source bundle639,884bytes SHA64fa5265513c1d7212871a09ca913d6bddef9604a0f50f7ee8bd2bd49e351592 readback verified atamp-standing/source.zip. Exact61-frame actual training replay finite,2seconds/terminal3, per-frame loss=-actual AMP reward (range first recording1.14e-3..3.22), fixedsigma.05. Browser8021 current run selected/playing, plain loss values change withtick; reloaded lost WebGL context. TensorBoard8035 existing historical logdir retained; current run selected with imitation reward, discriminator loss, actor and critic charts;12 measured reward points read through1,818,624samples, latest~.207 (not recovery evidence). Browser filter AMP_standing is intentional for current experiment; clear it to compare history. Observers9944/9428. Evidence amp-standing-verification.json, amp-standing-smoke.json, standing-candidates.json. Full GPU window including~10m49s setup is~$0.70 ceiling atfixedrate if cutoff15:15:26 is reached, not an exact bill. No learned recovery success claimed.

User requested vanilla MimicKit AMP except actor/critic1024→1024,512worlds,3-frame discriminator,2second episodes, noisy back/front floor starts and20% upright target starts. User then explicitly requested early termination ONLY for upright starters, and permanent cohort identity across resets to avoid distribution drift. Implemented102 fixed upright worlds (19.92%) and410 fixed floor worlds; each floor reset independently chooses back/front50/50 and reuses prior uniform±5degree joint noise, joint limits and2mm collider floor clearance. World0 is floor for replay. Upright worlds always reset exactly into the static target. Stock contact-failure rule applies to upright cohort; floor cohort uses stock TIME timeout/bootstrapping, not a fake success terminal. Discriminator history on reset repeats ACTUAL initialized pose/zero velocities for all3samples rather than a fictitious standing past.

Reference selection: fetched only two stock get-up files via ZIP byte ranges (~141KB total including directory metadata). Original face-down ending frame182 looked natural but fails a2second fixed-target physical hold. Tested standing candidates under unchanged stock Newton controller. Chosen target combines all recorded upper-body joint angles from that frame with the stock planted neutral leg stance; root heading/XY normalized,2mm floor placement. Full target contains lowered arms, not the original T-pose. Static61identicalframes at30Hz, looped; no get-up imitation sequence. Final hold across102upright worlds: head origin1.34324→1.34119m, zero non-foot failure flags. This validates the reference stance, NOT learned floor recovery. Candidate diagnostics preserved; no changes to humanoid geometry/mass/controllers/physics.

Vanilla AMP discriminator remains1024→512, reward scale2/task0/disc1, fixed action sigma5e-2, stock SGD optimizers/LRs, bounds penalty10, gamma.99/lambda.95/PPOclip.2 and normalizers. Actor/critic only use the requested1024→1024 ReLU network. Policy140inputs; discriminator426inputs (3frames). No previous MSE/time/velocity rewards or extra inputs. Fresh weights/counters. Stock32episode deterministic tests retained. Because upright failures can satisfy32testepisodes before floor world0 completes, viewer records a full ACTUAL TRAINING episode instead. Per-tick rewards are copied from AMP's existing reward buffer before optimization, across update boundaries; no second discriminator inference, no fabricated zero environment reward. The initial pose has reward0. Plain existing HUD displays negative imitation reward as loss; TensorBoard keeps imitation reward/discriminator loss/actor/critic and accuracies. Test environment return0 is not labeled learning performance.

New owned Secure L4 qjy94qxhccs256 at$0.59/hour, because prior stopped kq6bt5enkvigfi could not restart (host capacity). Prior pod/data untouched. Runtime/cache reused. New run20261014_141524_amp_static_standing_512,trainer1431, launch14:15:28. User restart refreshes one-hour cutoff15:15:26Warsaw (1791983726.8772707),165second save reserve; live local+remote guards, no schedules. Setup time is additionally billed from14:04:39; report it separately from the one-hour training window. Source already backed up; final edited source/first checkpoint and visible observers still being verified. Receipts amp-standing-name.txt/amp-standing-observers.json/amp-standing-dashboard-manifest.json. Local recorder unit test passes exact two-update per-tick rewards. Final512world real-engine smoke passes repeated partial resets/fixed cohorts, injected torso-contact termination split,60step floor horizon, correct3sample actual history, zero static demo velocities, network widths and stable reference hold. Initial dtype bug in masked done assignment caught/fixed before training; earlier target failure retained as evidence. No main journal/Unreal/PHAT/BP/D/S changes.

## CURRENT - velocity penalty disabled, October 14 12:09 Warsaw

Per-tick UI correction: replay.npz already contained loss_terms for all51poses, but local converter discarded it and HUD used rollout totals. Converter now forwards named frame_losses after asserting exact per-tick agreement with negative reward; viewer selects floor(playback frame) including scrubbing. Current capture11722 check: tick44 all0; tick45 early=-.6276287436; tick46 tail=.0936322957; velocity0; sums reproduce recorded episode totals. Only local bridge restarted28912->10156 to load converter; GPU trainer1352 uninterrupted, settings/deadline unchanged. Old archived JSON without arrays shows not recorded, never invented per-tick values. Browser scrub verified actual capture11772: tick45 early=-6.393e-1 and tail0; tick46 early0 and tail4.691e-2; plain name/value overlay with relevant progress restored.

User rejected the added card/table and clarified relevant information should remain. Restored plain overlay with dynamic name/value loss lines plus training total/noise/progress/frame/time/root/timestamp. Removed the card markup/styles/render code; unrelated diagnostics stay hidden. Training untouched. During edit, Windows default-encoding write failed; restored viewer immediately from the last verified UI archive and applied changes via explicit UTF-8 atomic replacement before refresh.

Replayer readability follow-up: replaced the composite-MimicKit debug overlay with a small top-left Loss breakdown card. Rows are still discovered from capture metadata; columns show weighted train/replay values and coefficient, total highlighted, velocity0 labeled Off. Retained agents/noise/step and playback time; removed irrelevant sword badge, foot-pin legend, combat/root debug dump, disabled combat controls and verbose duplicate toast for these runs only. Other viewers retain existing diagnostics. No trainer or observer restart.

Replayer HUD correction: previous top-left overlay always labeled MimicKit as final-frame MSE, despite composite values only appearing in the bottom message. Added assets/mimickit_losses.js to the existing Stepper viewer and used it for captures containing rollout_losses/loss_weights. Displays all metadata-discovered terms, weighted train/rollout values, coefficient, disabled state and total; current velocity explicitly0. Local Node checks pass actual current capture, an unknown future term, zero weight and absent metadata. Browser verified current no-velocity run shows all three terms and total in the main HUD with scientific notation, correct weights1/3/0 and capture-time labeling; new replayer tab retained. Display-only; no trainer/bridge/server restart, physics/settings/deadline change.

12:29 TensorBoard display repair: user correctly reported stalled graphs. Two causes: browser run regex neutral_pose_mse excluded all newer named runs; additionally verification had instantiated Dashboard, creating a newer empty event file (PID2520,88bytes). TensorBoard default reload_multifile=false then stopped polling the older still-active writer21288 file. API had only4points ending141,131,776 despite live events continuing. Restarted ONLY owned TensorBoard8035 PID8680 ->29720 with --reload_multifile true,15s reload, same logdir/history; receipt tensorboard-comparison-server.json. API now135points through162,594,816 with velocity0. Cleared run filter and selected four composite-loss tags in browser. NEVER instantiate Dashboard merely to verify data: use read-only event/API queries; retain multifile loading for future server launches. Trainer, bridge, settings and billing deadline untouched.

12:23 read-only stop report investigation: owned trainer1352 was still running, status9503/155,713,536samples at20,003transitions/s and log continued advancing; no failure/finished report, checkpoint9473 backup verified. Local bridge28912 and dashboard21288 alive. In-app replayer was showing old055611 run/step748 with filter055611; refreshed page and selected current120926 run, loaded actual step9522/156,024,832samples and enabled playback. No trainer restart, settings change or deadline extension. Future handoff must verify the visible selected run, not only backend telemetry.

User requested resume latest with velocity removed to check rising loss. Config-only change tail_velocity_weight .006666666666666667 -> 0: both joint and pelvis linear/angular velocity penalties have zero contribution. Tail pose coefficient3 and early-pose timing/reward unchanged. Same512 worlds, sigma5e-2, LR1e-4,141inputs,50frames and stock physics/controller/PPO. Preserve all previous runs and graphs; no new test rollouts.

Prior trainer1216 saved gracefully at140,460,032samples / final8572, verified11,085,118bytes SHA3dee27e650fcf4533625701b4e792b7aa330a29133dd6aaf8c1e1103253a7f6e. Sole continuation1352 /20261014_120926_neutral_mse_512_no_velocity restores policy, optimizer, normalizer and counters; fresh physical episodes. Same owned pod kq6bt5enkvigfi. User-requested resume refreshes cutoff1791976170.442011 =13:09:30Warsaw, trainer save cutoff13:06:45. Same live guards, no schedules/new pod. Observers bridge28912/dashboard21288; receipts no-velocity-name.txt/no-velocity-observers.json/no-velocity-dashboard-manifest.json. Source unchanged. Verified: only environment tail_velocity_weight differs; agent/engine configs exactly equal. Update8603/140,967,936samples advancing at19,742transitions/s, no numerical/backup failures. Actual51-pose training replay finite with velocity contribution zero at every frame and terms summing to reward. Four TensorBoard loss graphs verified; new checkpoint8573 uploaded/readback verified SHA c7574ea8f69cb50d7c2ae4e5c212283fd71284c529588129316ebc4c16c766af. Evidence no-velocity-verification.json. A lower total immediately after removing velocity is a changed objective, not evidence of learned improvement; compare retained pose components and actual replay.

## CURRENT - velocity loss divided by3, October 14 11:51 Warsaw

User requested resume latest with velocity loss divided by3. Config-only change: tail_velocity_weight .02 -> .02/3 (.006666666666666667), existing tail_multiplier3 retained. Effective tail pose coefficient remains3; combined joint+pelvis linear/angular velocity coefficient now .02 (previously.06). Early-pose timing/reward, tail-only scope,50steps,141inputs,512worlds,noise.05,LR1e-4,physics/controller unchanged. Exact config comparison: ONLY tail_velocity_weight differs; agent_config and engine_config equal. No code changes or fresh-policy reset.

Saved prior trainer1105 gracefully at121,225,216samples, final7398 verified11,082,101bytes SHA7d34c3810bd040548e610812d491d3538cd7cc54d8922e8af92f6d89f82dbc85. Sole trainer1216 /20261014_115155_neutral_mse_512_pelvis_vel_third resumed that checkpoint with optimizer/normalizer/counters, offset7399. Same pod kq6bt5enkvigfi. User-requested resume refreshed one-hour cutoff1791975118.0282924 /12:51:58Warsaw, trainer save cutoff12:49:13; same guards/no schedules. Observers bridge22792/dashboard11880. Current receipts velocity-third-name.txt, velocity-third-observers.json, velocity-third-dashboard-manifest.json.

New checkpoint7399 verified10,887,723bytes SHAa642602a6340c0955d1ddfe1835166363f0e853d937472311d2234e8a499863e. Actual training replay confirms effective weights3/.02, pelvis included, and weighted components sum exactly to reward. Four weighted graphs verified; test rollouts remain disabled. Evidence velocity-third-verification.json and velocity-third-resume-source.json. Source unchanged; dedicated journal/evidence uploaded with readback. Preserve unrelated work/main ProjectJournal.md.


## CURRENT - pelvis velocities and tail losses x3, October 14 11:34 Warsaw

User requested adding pelvis linear/angular velocities to the existing joint-velocity loss and multiplying both end losses by3, then resuming latest. Implemented tail-only sum of three per-coordinate means: mean(joint DOF velocity squared) + mean(pelvis body linear velocity squared) + mean(pelvis body angular velocity squared). Units m/s and rad/s; no hidden normalization. Existing joint contribution is not diluted by increasing its denominator. Pelvis is asserted body0 by name; read physical body velocity/angular-velocity tensors directly. Effective coefficients: tail pose3, combined velocity3*.02=.06; early-pose improvement/timing unchanged. All50steps/141inputs/512worlds/noise.05/LR1e-4 unchanged. Tests/evaluation remain disabled in production. Graph names: loss/early_pose,tail_mse,velocity,total; velocity replaces joint_velocity display for this run to reflect added pelvis terms. Internal historical key retained for checkpoint/replay compatibility, metadata explicitly records pelvis inclusion and effective weights.

Previous trainer866 gracefully stopped at102,252,544samples, final6240 verified11,115,813bytes SHA1c4627f5903f0a6922c4ef8f5899a3b3ebb001349d5ce6d73282f61868e8104b. Sole trainer1105 now20261014_113452_neutral_mse_512_pelvis_tail3 on same owned kq6bt5enkvigfi. Resumed weights/optimizer/normalizer/counters from final6240, offset6241; no input migration. User-requested resume renews one-hour window per standing instruction: hardstop1791974094.5362601 /12:34:54Warsaw; trainer save cutoff12:32:09. Same local/remote guards, no schedules/new pod. Observers bridge12216/dashboard17396, receipts pelvis-tail-observers.json/pelvis-tail-dashboard-manifest.json; current name pelvis-tail-name.txt.

Validation:64world actual physics smoke passes141inputs/50steps, reset isolation, unchanged4x bonus, tail-only penalties, components exactly sum to applied reward. CPU test executes actual reward method with joint speeds2, pelvis linear3/angular4: raw component means4+9+16=29, weighted velocity per tail frame=.348, pose=.06, reward=-.408; disabling pelvis givesvelocity.048 and beforetail alltermszero. Actual training replay51poses verified effective weights3/.06, pelvis inclusion, no evaluation, reward agreement. Four weighted graphs and new checkpoint upload verified (see pelvis-tail-verification.json for exact latest sample/hash); original checkpoint retained. No success/performance improvement claimed. Source/evidence/journal persisted with readback under timed_tail/source.zip. Preserve unrelated work, no main ProjectJournal.md changes.


## CURRENT - velocity contribution balanced, October 14 11:13 Warsaw

User approved fixed velocity weight0.02 with pose weight1 to balance their observed contributions. This is a fixed coefficient, NOT online/adaptive normalization. Early-pose timing/improvement term unchanged. Weighted loss components and their exact sum are shown in four TensorBoard graphs and actual-training replay; metadata records weights explicitly. Separate dated continuation preserves historical weight1 curves. No new tests/evaluation rollouts in training.

Gracefully saved previous trainer641 at79,527,936samples / final4853; checkpoint10,945,515bytes SHA d97e37ae5f9e4a22b273f27edb8dd5c25194dfe83bc1857afbaba1ca567a872d, upload/readback verified. Sole trainer now866, run20261014_111309_neutral_mse_512_tail_v002, same pod kq6bt5enkvigfi. Resumed final4853 with optimizer/normalizer/counters, offset4854,141inputs and512worlds unchanged. Administrative reload used --keep-deadline: hardstop still1791972462.4191146 /12:07:42Warsaw, trainer save cutoff12:04:57. No extra hour, GPU or schedules. Observers bridge5436/dashboard20820, receipts weighted-tail-observers.json, weighted-tail-dashboard-manifest.json, weighted-tail-name.txt.

Validation: repeated64-world50-frame smoke passed with weight0.02. Additional CPU execution of the actual reward method on controlled nonzero velocity2rad/s proves expected per-frame tail contributions: pose.1/5=.02, velocity4*.02/5=.016, reward-.036. Actual production51-pose replay finite, metadataweight.02, three components sum to negative reward. Allfour graphs verified; no test graph. At4874/79,872,000samples: early loss-.298899, tailpose.0434643, weightedvelocity.0405159, total-.214919; ~18,758transitions/s. This balances the recent measured tail contributions, not a guarantee they remain equal or proof of better recovery. First new checkpoint4854 verified10,887,092bytes SHA1ca3dab6db6863598599532cd6f09c6128f324ae52b63b711acc762ea5805856. Evidence weighted-tail-smoke.json/weighted-tail-verification.json. Source and journal are persisted in timed_tail/source.zip; saving cadence unchanged. Preserve unrelated work and main ProjectJournal.md.


## CURRENT - timed best pose plus five-frame tail, October 14 11:07 Warsaw

User authorized resume of latest checkpoint for one hour, preserving original 512 worlds, fixed noise 5e-2, LR 1e-4 and 141 inputs. User clarified best pose means lowest MSE; reward for attaining it immediately should be 4x the reward at 1.5s. Tail-only joint velocity penalty with same weight as tail pose MSE; remove separate evaluation and expose three components plus total. Interpretation explicitly communicated: early reward is improvement from initial MSE, multiplied by 4-3*t_best/45; this prevents multiplying a negative MSE from punishing earlier success. Record the true lowest MSE and earliest tick attaining it over ticks 0..45. Pay improvement at tick45. Add frames46..50: loss is mean body-position MSE + mean squared physical joint DOF velocity (rad/s squared, excluding floating-root velocity), both coefficients1. Five-frame terms are averaged across the tail so both have weight1. Total loss = negative early reward + tail pose mean + tail velocity mean. Early component and total may be negative. Do not label composite score as pure MSE.

Observation contract unchanged141: original remaining-time input still reaches0 at45 and stays0 during tail. Best/time bookkeeping is NOT observed. No change to physics, body, controller, target alignment, optimizer or normalizer. Resume counters/weights/optimizer/normalizer from final4603, SHA ff4a96726d7ef9dd2b83274c7dc92682a85f1d4e34cfce43a0f5b6542a0f2e98, 11047976bytes, verified cloud checkpoint. Separate chronological run because objective changed; preserve historical graphs. No --evaluate; replayer captures actual training episode,51poses for50steps, including per-frame component values.

Original stopped pod o927b6cxtqi2x0 could not start: Runpod returned insufficient host GPU capacity. It remains stopped and untouched. Replacement sole active pod kq6bt5enkvigfi, Secure L4 at0.59USD/h, allocated1791968430.660291. Local guard plus remote guard149 bound runtime; no schedules. Saved runtime409880235bytes and compiled-kernel cache restored directly storage-to-pod, avoiding laptop download/reinstall. Checkpoint fetched directly storage-to-pod and checksum verified. No checkpoint pruning or saving-cadence changes. Training launched as 20261014_110737_neutral_mse_512_timed_tail, PID641 at Unix1791968865.575419, resumed75,431,936samples/global offset4604 with optimizer+normalizer restored and no added inputs. Launcher refreshed authorized one-hour cutoff to 1791972462.4191146 (2026-10-14T12:07:42 Warsaw); trainer reserves165s for final checkpoint/upload. Initial allocation/setup consumed about7min before the new training hour. No extra evaluation pass. Local guard from timed-tail-guards.json and remote149 both read live pod-scoped deadline. Observers bridge13496/dashboard22724, replayer8021 and TensorBoard8035; receipts timed-tail-observers.json/timed-tail-dashboard-manifest.json.

Validation completed:64-world actual physics,50steps/51poses,141inputs, 4x reward ratio for equal improvement at t0 vs45, original remaining-time input preserved, partial-reset isolation, exact per-frame reward/component agreement, tail-only DOF velocity, terminal50. Initial test failed only because expected clock tensor became int64 at zero; corrected test dtype, rerun PASSED. Three dashboard tests passed, including exactly four loss graphs and no fake test or pure-MSE graph for this composite objective. Production replay is a real training episode (not a test) and independently checked to sum to its actual reward, finite poses, timing masks exact. Graphs loss/early_pose,tail_mse,joint_velocity,total. Record current component scale without silently tuning: at4654 early-.39962, tailMSE.05906, velocity2.97593,total2.63537; equal coefficients do NOT mean equal magnitudes. User informed. Initial throughput~19,814transitions/s; no claim of improvement/recovery yet. Checkpoint4654 verified10,907,740bytes SHA f122035024a3434469af250b7d87721fac505eeac760465e5e45d8260aa0bd6a. Evidence timed-tail-smoke.json and timed-tail-verification.json. Persist refreshed pipeline+vendor source, journal and bounded evidence in timed_tail/source.zip with checksum readback. Preserve UE/BP/PHAT/labs and keep this branch out of ProjectJournal.md.


## CURRENT — best-pose512, original141 inputs, October14 09:47 Warsaw

User clarified MAX meant BEST pose: use MINIMUM full-body position MSE over the whole episode. Explicitly DO NOT CHANGE INPUTS. Aborted maximum-loss draft NEVER launched training; its extra observation and maxoption were removed. No user-approved run ever used142inputs in this iteration. Do not append reward-history inputs or change the NN input contract without user direction. Internal per-world best-error record is reward bookkeeping ONLY, not an observation.

New sole trainer PID2387, run20261014_094731_neutral_mse_512_best_fixed005, fresh weights/optimizer/normalizer/counters, original512settings:141inputs including existingtime, fixedsupine,1.5s/45steps, sigma5e-2, actor/criticLR1e-4, no gradientcap/peragentnoise, same physics/controller/PPO. --best-loss pays ONLY -minimum_MSE atterminal45; record includesresetpose andeveryphysicalstep, no /45 scaling, no continuousreward, targetalignmentunchanged. It remembers a better earlierpose even if agent fallsagain, exactly requestedbest-pose objective. Historicalrewarddefinitions retained in separateconfigs/dashboards.

One-hourclock reset byrestartlauncher09:47:32: hardstop1791967652.6893697 =10:47:32Warsaw, trainercutoff10:44:47 (165s reserve). Samepod o927b6cxtqi2x0, liveguards1381/11816, no newpod/schedules. Observeridentities best512-observers.json, replayer8021/TensorBoard8035 separatechronologicalrun. Verified model141inputs, fresh prior_samples0/offset0; update30/507,904samples finite~24,462transitions/s. Agent/engine exactly equal baseline; envdiff only best_reward/objective. Recomputedepisode minimum fromrecordedphysics exactlymatchesreward0.3174428046. Checkpoint0 readbackverified10,904,684bytes SHA447b3bfc34d9b87926a6c2e8d088c61303e55a49f7d6fb1cb4bd207c02be3091. TensorBoard loss/train,test and replayer verified; evidence best512-verification.json. Previouscontinuousrun saved2052updates/33,619,968samples; checkpoint2051_final.zip verified10,968,941bytes SHA6002bb57837800473b04fa823f67af1f65d92530acab9f3b9119d0ed786be4ef. Do notresume it.

Prelaunch64worldphysics test_best_pose.py PASSED: exactly141inputs, unchangedtimeinput, initialpose included, earlyminimum survives laterworsening, independentperworld bookkeeping, partialresetisolated, zero rewardbeforeterminal, sum equalsnegativeactualminimum, finite45stepmotion. test_max_pose.py draft replaced bybest test. Originalterminal andcontinuous options retained; maxdraftoption removed. NoUE/BP/PHAT/D/S/mainjournalchanges.

## CURRENT — fresh512 with continuous upright MSE, October14 09:17 Warsaw

Furtherdiagnosis~09:36–09:42: historicalcomparison confirms genuine stagnation, notjust differing chartmetric. Original512at1500 hadterminaltestMSE0.176267; copiedcurrent1500 finalMSE0.32663. Bounded128world noisy rollout fromcheckpoint1500,seed461,sigma.05, freshphysicalepisodes, nolearning: meantrajectoryMSE.316457,best.309835,worst.325887, std.002695; headpeakmean.1241m,max.1451m; pelvispeakmean.2816m,max.3030m; actionclipping0%. All sampledpolicies staylow; no actuatorbound saturation. CriticMC RMSE.02259, overall explainedvariance.905; GAEstd.02185, time-meancomponent11.4% ofvariance. Not proof of gradientstarvation orbrokencritic. Recordedprior4200replay scored usingcurrentheading-only bodyMSE: continuous.220175, final.029467; headpeak1.069m. Current1650replay continuous.315916,final.327510,headpeak.1219m. Thus currentrewarddoes prefer priorbettertrajectory; floorbehaviorisnot the globaltarget. Localfloorstrategy/exploration-creditproblem is consistent with evidence but causalmechanism NOT isolated. Do not claim division45, clippedactions, missingreward, orintermediatepenalties provenrootcause.

Diagnostic briefly SIGSTOPed ONLYownedtrainer1773 for41.294s to avoid competingGPU workloads; remote detached supervisor enforced110s subprocess timeout and finally SIGCONT. VerifiedsamePID resumed and countersadvancing; no weights/settings/normalizer/timer change. Noextra checkpoints or newGPU. Scriptsdiagnose_continuous_pose.py, resultscontinuous512-credit-diagnosis.json andcontinuous512-trajectory-comparison.json. Sparse-vs-dense learningA/B has NOT been performed. Historical4200vs1650clipsare notmatchedtrainingduration and are used ONLY to compare rewardmeaning, notsampleratecausality.

Reward-scale check at user request: CPU-only check_reward_scale.py executed upstream PPO actor/critic loss functions with a saved real45-step reward trace and controlled synthetic model/values. Actorgradient for rewardscale1vs45:0.60943025vs0.60943127 (difference1.01e-6), confirming normalized advantages cancel uniform scaling with zero/consistently scaled criticvalues. Criticgradient ratio45.0 andlossratio2025.0 inzero-output control. Nonzerofixedcritic with ONLYrewards scaled changes normalizedadvantages; therefore algorithm is not fully scaleinvariant, but this is NOT evidence /45 caused currentpoorlearning. NolearningAB/livegradients measured; no secondGPUworkload, trainerpause, settingchange, timerextension or modelpromotion. Evidence continuous512-reward-scale.json. Do not claim actorlearning is45xweaker or scaling explains stagnation. User's point about one-term objective retaining sameoptimalbehavior is correct.

Read-only check09:24–09:27 at user's report of flatloss: no settings/timer/process changes. Atupdate530/8,699,904samples trainer healthy~24,545transitions/s; latest evaluated500. Test episode-averageMSE0.332552(update0) ->0.326636(update500), only1.78% improvement. World0 replay headpeak remains0.115m, pelvispeak0.236->0.268m; mean body travel0.316->0.488m overepisode. Actor hidden weights do change (RMS9.41e-4,max1.08e-2), PPO clipping~.2–.24, so not frozen/zero-update training. No recovery. Source confirms stock PPO normalizes advantages by std (floor1e-5), observedstd~3.2e-2: divisionby45 does NOT imply45xsmalleractorgradient. It changes reward/critic scale and temporal weighting; causal contribution to stagnation is UNTESTED. Explicitly disclosed /45 averaging implementation choice again; user has not requested a rescale or optimizerchange. Evidence Saved/MimicKit/continuous512-flat-diagnosis.json. Do not compare newepisode-average metric directly to old final-frameMSE or claim scaling proven cause.

User requested vanilla/original512 settings, changing loss from final-frame to continuous. Gracefully stopped1024 continuation at779updates/25,526,272samples; final778 checkpoint readbackverified SHA8006f9de38e27f1a09a769f031ba3c249f2a5a677e57c05faa21f13fa7bd78d8,10,916,500bytes. Do not resume1024.

New sole trainer PID1773, run20261014_091659_neutral_mse_512_continuous_fixed005, launched09:17:02 on existing pod o927b6cxtqi2x0. Fresh weights, optimizer, normalizer and zero counters: no --resume. Same512 worlds, fixedsupine start,1.5s/45steps, sigma5e-2, actor/criticLR1e-4, no gradient cap or peragent noise; original physics/controller/PPO and50update evaluation/save cadence unchanged. Added --continuous-loss only for neutral_pose: each step reward=-upright_body_position_MSE/45. Episode sum is negative mean MSE across45steps (matching previous continuous-loss convention, prevents accidental45x reward scale). Target still removes rootXY/heading only, preserves absolute standing height and tilt; no velocity loss. Test/replayer/TensorBoard loss now means episode-average pose MSE, NOT final-frame MSE. Historical runs remain available and labeled terminal vscontinuous.

Restart launcher reset approved hour: hardstop1791965821.6538322 =10:17:01 Warsaw, finalsave reserve165s =>10:14:16 trainer cutoff. Existing live guards1381/11816 read updated deadline. No newpod/schedules. Observers continuous512-observers.json; TensorBoard8035 has a separate datetime-named run, replayer8021 has actual physics. Verified fresh prior_samples0/iteration_offset0; update10/180,224samples finite,22,854transitions/s (early measurement). Agent/engine configs exactly match original; environment differs only in continuous_reward/objective. Actual45-frame physics replay finite with negative reward at every frame; configuredsigma.05. TensorBoard loss/train,test and replayer output confirmed. Checkpoint0 verified10,903,864bytes SHA6b1691bad4b2c26f99e33c5ef73e64b6557f6b1f27f58ff8ed8de3af46c8c466. Source/backup receipts in Saved/MimicKit/continuous512-*.

Before altered training:64world GPU smoke passed original terminal-only assertions AND all45 continuous step rewards, finitephysics/observations, exact negative episode-mean sum, unchanged45step horizon,141inputs and15bodies; uprighttarget/foot geometry checks retained. Original static YAML stays terminal; option stores continuous_reward/objective in newrun config. No resetnoise/frontstarts or AMP introduced. Preserve UE/PHAT/BP/D/S. Keep branch OUT of ProjectJournal.md.

## CURRENT — live runtime extensions and1024 continuation, October14 09:10 Warsaw

Standing user instruction: EACH USER-REQUESTED RESTART/RESUME starts a fresh ONE-HOUR GPU window, at the known Secure L4 rate$0.59/h. Earlier statements below saying a restart must inherit the old cutoff are superseded. Do not require repeated approval for that requested restart. No schedules. Live extensions update the existing trainer and both billing guards WITHOUT stopping/reloading training. Use `python Labs/MimicKitTraining/extend_runtime.py --seconds 3600` to set one hour from now; `--from-unix` can anchor to an actual user-requested launch. This is an authorized-action helper, not automatic permission to extend arbitrarily.

Current sole pod o927b6cxtqi2x0: corrected hardstop1791964622.560628 =09:57:02 Warsaw, one hour from the original fresh1024 launch08:57:02. Trainer reserves165s for final evaluation/save/upload:09:54:17. Allocation time is preserved separately for actual cost accounting. Old09:18 cutoff is superseded. Remote guard1381, localguard11816. Both reload pod-scoped runtime_control.json and preserve the last bounded deadline on missing/malformed data; the trainer checks once per update with file reads at most once/second. Bridge and dashboard follow the same deadline. Do not touch unrelated or exited pods.

One-time installation required a graceful checkpoint save/reload because the old trainer held its cutoff in memory. Original1024 finished403updates/13,205,504samples; checkpoint402_final.zip verified SHA331ea329335fee38a679f0a753898382d6382479bf317d728adfa8edee7b9cd2,10,917,734bytes. Continued as20261014_090600_neutral_mse_1024_liveclock, PID1428, launched09:07:37. resume.json verifies prior_samples13,205,504, iteration_offset403, optimizer/normalizer restored; fresh physical episodes as usual on checkpoint resume. No new weights/counter reset or learning-setting change for this administrative reload. Fixedsigma5e-2, LR1e-4,1024worlds, original supine1.5s terminalMSE unchanged.

New `start_training.py` is the entry point for USER-REQUESTED restarts: checks no existing trainer and unique run name, refreshes one-hour clock, then launches forwarded training args. `--keep-deadline` is ONLY for administrative reloads. It allocates no pod, does not kill a trainer, and does not choose/reset weights; pass/omit --resume according to the user's request. Retained train.py --max-samples is optional; removed the implicit100million-sample ceiling for time-bounded launches so a longer live deadline isn't defeated by a hidden sample stop. Explicit --max-samples still works. No optimizer/reward/physics changes.

Tests:3 deadline unit tests passed locally and remotely (live extension on same reader, invalid/other-pod rejection, consistent trainer/guard/observer boundaries). Live integration briefly moved the limit10s earlier, observed PID1428 still training at493/16,187,392samples with that new limit, then restored the approved09:57:02 cutoff without restarting. Confirmed samePID1428 at563/18,481,152samples with restored09:57 cutoff, no numerical/backup errors. Three mocked launcher tests also passed: restart refreshes onehour, administrative reload preserves deadline, active-trainer refusal does not extend billing. Final evidence in Saved/MimicKit/liveclock-test.json. Observer identities liveclock-observers.json (bridge18340,dashboard10208), existing TensorBoard8035 and replayer8021. Continuation is appended to SAME chronological1024 TensorBoard curve. Source/evidence backup receipt liveclock-source-backup.json. Keep this branch OUT of ProjectJournal.md; preserve UE/PHAT/BP/D/S.

## RUNNING — fresh1024 fixed-noise run, October14 08:57 Warsaw

User explicitly requested1024 agents, SAME settings, FRESH weights and reset counters (repeated request handled once). Only trainer PID1238 /20261014_085701_neutral_mse_1024_fixed005 launched08:57:02Warsaw. Prelaunch asserted no other trainer and exact agent/env/engine YAML equality with original256 run. No --resume: fresh policy/critic/optimizers/normalization and counters. Same fixed sigma5e-2, actor/critic LR1e-4, no gradient cap, no per-agent noise, fixed supine1.5s terminal upright-bodyMSE, test/checkpoint50updates. Numerical guard retained. Do not silently change settings if it fails.

Same pod o927b6cxtqi2x0, same$0.59/h approved-hour budget; hardstop09:18:11Warsaw /1791962291.135363, trainer cutoff09:15:26 /1791962126.135363. No new paid hour/deadline reset. Guards17284/174. All previous trainers/diagnostics finished. AMP/256 runs retained. Local receipt fixed1024-launch.json, observers fixed1024-observers.json; existing replayer8021/TensorBoard8035 preserved with a fresh chronological run and loss/train,test. Verified resume.json prior_samples0/iteration_offset0, update20 /688,128samples finite,~35,011transitions/s. Checkpoint0 readbackverified10,903,182bytes SHA1234095d3ab9c5af37937e4d1d84c39f7de6a17141a8af196c967ddad427bb4d. Actual physics replay and fresh TensorBoard loss/train,test verified; no numerical failure. No main-journal/UE/BP/PHAT/D/S changes or schedules.

## DIAGNOSED — optimizer changes trigger fixed256 physics failures, October14 08:47 Warsaw

User authorized diagnosis on current GPU after retry failed; production remains STOPPED, no1024 launch and no changed training settings. Sole pod o927b6cxtqi2x0 still allocated, hardstop09:18:11 unchanged. All four sequential disposable diagnostics completed; no active trainer/diagnostic GPU workload remains. No schedules. Decide next training configuration with user; do not blindly resume750 again.

Isolated checkpoint750 with same256/config/seed/restored optimizer/normalizer, fresh episodes, no benchmark pause. diagnose_fixed_noise.py records requested AND clamped actuator targets, actual physics tensors and observations around firstinvalid; stops immediately before later actions/learning can consume it. Normal training trace failed atglobal754 after3 complete updates. Failure world127 atphysicalstep29: input commands and applied targets finite, but actual bodyposition/rotation/velocity become nonfinite during env.step, not merely observation formatting. Last finite body velocity component201.39m/s and angular716.45rad/s. Prior3 bodyvelocitycomponentmax35.87,63.29,38.43m/s; applied target changes max1.26–1.37rad per1/30s interval. Raw requested targetmax17.59rad, actualclampedmax3.351rad; do NOT claim raw17.59commands reached actuators.

Causal isolation: freeze learned weights AND normalization =120updates finite, exact state_dict equality assertion passed. Allow weights/optimizers to update but freeze normalization =physics failure after6completedupdates/global757; exact _obs_norm state tensors match sourcecheckpoint, failed-model tensors all finite. Freeze weights, allow normalization updates =60updates finite. These single-seed bounded controls show weight updates suffice for failure in this setup; they do not prove normalization never contributes or that finite frozen motion is good recovery. Physics is trajectory-sensitive; failingtick/world differs from original and retry. Do not claim deterministic reproduction or that reducing agentcount universally causes failure.

Normal trace actor mean movement RMS on unchanged normalized observations after first3updates=.37746,.71604,.88942 normalized action units vs fixedsigma.05 (7.55,14.32,17.79sigma RMS). Max gradientnorm414.8,79.97,161.0. PPOclipfraction~.974; normalization-induced mean shifts .01789,.05973,.06288, smaller in this trace. Large finite controller updates precede violent physics/numerical collapse. Action-bound lossweight0 is inherited from the user-requested pure-MSE original512setup; engine still clamps targets. No LR/cap/noise/normalizer/reward/physics modifications promoted. Recommendation is a bounded optimizer-step limiting test, not guard removal or repeated identical restart; implementation choice pending user. Evidence Saved/MimicKit/fixed256-diagnosis.json and remote fixed_diag_{train,frozen,weights_only,normalization_only}; exactly one failed-policy snapshot per faileddiagnostic, no periodic diagnostic checkpoints.

## FAILED AGAIN — 256 fixed-noise retry, October14 08:38 Warsaw

Resume actually restored6,152,192samples/offset751 with optimizer and normalizer. It FAILED again atglobal763,1791959885.4693022, with first invalid next_obs atstep3/world30, then other worlds/actions/rewards. Guard rejected the rollout before PPO. No benchmark or SIGSTOP on this retry. No claim of root cause yet. Backup751 verified SHA260932cb4ddb9dc63030a3f03fd4f85cb85b75623d3f1b8347d9ffd5824596b7,10,903,306bytes. No trainer currently running; GPU remains billed within09:18:11deadline. User asked via pending question whether to diagnose on this GPU or stop billing; do not blindly restart/change hyperparameters. Failure evidence in fixed256/retry-failure.zip; earlier failure/scaling evidence9,065bytes SHAe248896cdd54edce554b1a5d63d154b11047281019e3c638b7381d990e4bd94f at fixed256/failure-scaling.zip.

User explicitly said resume it after being told the256 trainer stopped; resume256, NOT the earlier1024 request they paused. Sole owned pod o927b6cxtqi2x0 stays within original new-hour deadline09:18:11Warsaw; trainer cutoff09:15:26. New PID722/run20261014_083709_neutral_mse_256_fixed005_resumed launched08:37:09. Original checkpoint750 SHAe4e4da49a36a1471a34eb726c0ee6a73e4f735e9ce9928fd51abe7fc2c2f4b5a rechecked locally on pod before restore. Restore policy/optimizer/normalizer/counters and fixed sigma.05/LR1e-4, no gradient cap, no tuning. Fresh physical episodes on resume. launch receipt fixed256-resume-launch.json; observers fixed256-resume-observers.json. Same chronological TensorBoard curve with new segment source appended; new replayer run says resumed. Numerical guards enabled. No schedules or spending extension.

Previous256 PID447 stopped atupdate754 (08:32:19) because next_obs atstep31/world134 became nonfinite; rejected before PPO optimization. Last valid backup750 retained. This occurred several updates AFTER the scaling diagnostic resumed it, so it was not merely still SIGSTOPed. Cause is not yet isolated; do not assert pause caused it or had no effect on solver state. No1024 trainer launched. User asked to wait, then status, then explicitly approved this resume. Failed evidence preserved; do not automatically lowerLR/cap/noise or repeatedly restart if it fails again.

Scaling diagnosis completed before that failure: production paused103.79s with finally/SIGCONT and two sequential disposable copies on same host, same checkpoint700/config/model/optimizer, fresh physical episodes. Unprofiled median256 .579293s/update vs512 .661590s (12.4% shorter). Profile physics256 .373180s vs512 .454596s (17.9% shorter); actor+critic .102313/.100703s. Thus physics still dominates but does NOT scale proportionally with world count at these sizes. GPU parallelism and same solver stages are plausible mechanism; no exact kernel-level fixed-cost allocation measured. Two profiled updates per size plus10 retained unprofiled; no production training parameters changed. Measurements Saved/MimicKit/world-scaling.json, source benchmark_world_scaling.py. No diagnostic model checkpoints.

## RUNNING — original 512 configuration with256 agents, October14 08:22 Warsaw

User cancelled AMP and requested the ORIGINAL512 pure-RL run with fixed noise, changing only agent count to256. Fresh weights/optimizer/normalization/counters. No uniform noise or gradient cap. Exact baseline neutral_pose.py byte comparison with Saved/MimicKit/512-final-emergency.zip passed. Terminal upright full-body-position MSE,1.5s/45steps, fixed supine start, fixed sigma5e-2, actor/critic LR1e-4, original50-update test/save cadence preserved. Logging every10updates and failure guards retained. Run20261014_082133_neutral_mse_256_fixed005 launched08:22:05 Warsaw, PID447; fresh counters and no resume. Prelaunch comparisons verify engine/env config exactly match saved original512, agent config matches after original iters_per_output=50 (current extra iters_per_log=10 is telemetry only).

User approved a new one-hour L4 window before redirecting it from AMP. Old pod s7bscdkn0qtc5q restart failed due to no free GPUs on its host; it stays EXITED with its data. Replacement sole owned pod o927b6cxtqi2x0 at same$0.59/h allocated1791958691.135363, HARD STOP1791962291.135363 (09:18:11Warsaw), trainer cutoff09:15:26. Localguard17284, remoteguard174. Timer was not reset on task switch. No schedules. Cached runtime restored/readback-verified in34.24s; repository checked out at pinned2ed1e6c093bb0829f55d33cb4f7a1731cfe6cb69. Verified update20 /172,032samples finite,13,610transitions/s. Checkpoint0 readbackverified10,903,215bytes SHA3345cb13a7d6a6fa43002aafbe49e4886b9bbf7d060e53bb018b9e032e246819. Real physics replay present, no numerical/backup failure. Pod label still mimickit-amp-20261014 is allocation history, NOT task identity. Connection in Saved/MimicKit/pod.json. Preserve prior experiments/storage; no pruning. Keep all work out of ProjectJournal.md. Source55,037bytes uploaded/readbackverified at mimickit/pipeline_20261014/fixed256/source.tar.gz, SHA a360af0229c78df8bb05985fa366d94e96708de5bb2eac4c695472b52c8b737f. Observer identities fixed256-observers.json, retained replayer8021/TensorBoard8035. Chronological new run has loss/train,test and fixed-noise HUD; no historical chart deletion.

## STOPPED — AMP reached original spending deadline, October 14, 08:17 Warsaw

AMP run20261014_080100_amp_humanoid_512 stopped cleanly at204 completed updates /3,342,336samples after317.54s of training/evaluation/save time. No local failure, numerical_failure or backup_errors report. The inherited trainer deadline was08:04:51 Warsaw; owned pod s7bscdkn0qtc5q confirmed EXITED by deadline guard at08:07:36. It was not a new one-hour AMP authorization. User asked why it stopped; explained the inherited cutoff and requested approval for a new one-hour L4 window, at most$0.59GPU. Approval pending; do not rent/restart yet.

Final checkpoint203_final.zip readbackverified at mimickit/pipeline_20261014/runs/20261014_080100_amp_humanoid_512/checkpoint_0000203_final.zip,26,776,554bytes, SHA7a1ed2d0f1ceb302d933742c35f1c840faed157657f3a347e3a5241ee629fa78. Verified timestamp1791957898.5791185. Existing code saves discriminator optimizer but not its historical replay buffer; wrapper currently rejects AMP --resume. If restart approved, resolve documented AMP resume semantics before launch, retaining model/normalizers/three optimizer states/counters and clearly reporting if replay buffer is fresh. Do not silently reset weights or counters when continuing.

## RUNNING — vanilla AMP humanoid, October 14, 08:01 Warsaw

Dashboard correction: TensorBoard8035 retained obsolete reward/train,test=0 charts after derived event replacement. Restarted only its server to clear that cache; actual AMP reward/imitation atupdate100=0.458710 and discriminator loss1.715361. Training unchanged. Current TensorBoard PID in amp-observers.json.

User abandoned the pure-RL MSE experiment and requested vanilla MimicKit AMP with batch512, interpreted consistently with earlier requests as512 parallel agents. Prior cap10 run stopped cleanly at2186 completed updates /35,815,424samples. Final checkpoint2185 verified SHA7ad1b5bb4ef287438b5bba974146b493c92f000bd76c2e55dcb28e4dbbfeaf2b. Do not resume it.

Current sole trainer PID1006, run20261014_080100_amp_humanoid_512, actually launched07:58:59 Warsaw on same pod s7bscdkn0qtc5q. Fresh weights/counters. Stock amp_humanoid_env.yaml is exactly unchanged, including spinkick motion,10s horizon, randomized motion resets and stock humanoid. Stock amp_humanoid_agent.yaml matches except added iters_per_log=10; stock checkpoint/evaluation interval100, stock test32 episodes, optimizer/noise/action bounds/discriminator/rewards unchanged. No cap10 or per-agent noise carries over. Existing stock Newton backend retained (upstream example args default to Isaac Gym).512worlds x32rolloutsteps=16,384samples/update; upstream minibatch settings unchanged. Verified update60 /999,424samples finite,~11,195transitions/s. Replayer clip and eight AMP chart tags verified. Source/motion archive81,410bytes readbackverified at mimickit/pipeline_20261014/amp/source.zip, SHA d6f5242e4d3b0bf7c1893263c193f68d5fb89e22e94f18082aab744908832618. Checkpoint0 uploaded and readbackverified SHAafd595f141e993186d79e76e75a6d3c4fbae3071d47297f748727bd0f33c10bf,26,746,983bytes.

Unchanged hard GPU stop08:07:36Warsaw; trainer stops08:04:51 reserving165s to evaluate/save/upload. No new paid hour, schedule or other GPU workload. Existing localguard19468/remoteguard200 remain. Launch and observer receipts Saved/MimicKit/amp-launch.json and amp-observers.json. Replayer8021 and TensorBoard8035 retained; AMP charts show imitation reward, discriminator loss/accuracy, episode duration and actor/critic losses. Stock AMP environment return is zero because discriminator reward is calculated after collecting rollout; do not label that as a zero learning objective or MSE. Actual physics replay is labeled AMP spinkick.

Only spinkick asset downloaded directly on pod using ZIP byte ranges:88,586bytes transferred versus402MB archive; motion24,321bytes SHA0e2468b1d2812bf625a6847c8aaa53dceb5cb58a0a0ec8e78f0744656dfc77e3. Checkpoints include full model (actor/critic/discriminator and normalizers), all three optimizer states and counters. The discriminator historical replay buffer and physical episodes are NOT serialized; AMP resume is explicitly disabled in wrapper until that resume behavior is deliberately handled, rather than claiming an exact continuation. Source and motion preserved separately in persistent storage. No main-journal/UE/PHAT/BP/D/S changes.

## RUNNING — uniform-noise512 with user-approved gradient cap10, October 14, 07:35 Warsaw

User explicitly approved continuing the tested candidate with the upstream actor gradient norm cap **10**. Production **20261014_073427_neutral_mse_512_uniform_cap10**, PID844, is running on sole owned pod **s7bscdkn0qtc5q** (Secure L4,$0.59/h). Resumed the200-update candidate: model, per-agent fixed sigmas, actor/critic optimizer momentum, normalization and3,276,800sample counter restored. Actor/critic LR1e-4, sigma U(0,5e-2), original supine1.5s terminalMSE and stock physics/controller unchanged. Do not reduce LR, freeze normalization, change heading or silently adjust the noise distribution. The one newly approved training change is upstream grad_clip=10. No schedules.

Hard deadline remains **08:07:36 Warsaw /Unix1791958056.4437666**, not a fresh hour; trainer reserves165s and stops at1791957891.4437666. Localguard19468/remoteguard200 remain. First resumed checkpoint200 readbackverified SHA8a5aee484e9a9b04a7513b1e401eb5e6893582cbbee55dfeb7c77ff3f7a481a7,10,923,169bytes. Verified update530 / 8,699,904 samples at07:38:54 Warsaw, recent25,494 transitions/s, no numerical/backup failure. Latest test MSE0.272051 atupdate500 (initial0.334119); train MSE0.256901 at530. Checkpoint500 readbackverified SHA d5f2458bf6f31d4fefd0b94cc17918e1e8949bdca3638a7e58c790a508978e9c,10,923,124bytes. Replayer API confirms current run is running with a captured rollout. New run journal facts are measurements, not proof of recovery or long-term stability.

Observer identities Saved/MimicKit/uniform-cap10-observers.json: bridge1252, dashboard12816, existing TensorBoard8035 and replayer8021 retained. Chronological TensorBoard group includes the candidate's first200updates then the continuation on the SAME sample axis; prior scalar-only transfer3592bytes. Historic runs retained. Replay clearly labels training sigma U(0,5e-2), fixed per agent, and deterministic displayed evaluation noise0. Standard50-update checkpoint/evaluation saving unchanged. train.py adds optional --actor-grad-clip using existing upstream optimizer support; resumes preserve saved logging cadence to avoid altering the candidate config. This is not a bespoke optimizer rewrite.

Bounded matched-seed controls each completed200updates/3,276,800samples with the same task: original fixed noise5e-2, no gradient cap, final deterministic MSE0.324227; uniform noise+cap1, MSE0.333797 (stable but almost no improvement); uniform noise+cap10, MSE0.292658 vs its initial0.334119. All three finite. These are single-seed short controls, not significance/reliability claims. Cap10 reference replay46frames finite, terminal-only reward verified; world0 head peak0.1408m/pelvis peak0.3208m, so this is NOT standing/recovery. Candidate checkpoint10,894,968bytes readbackverified at mimickit/pipeline_20261014/uniform_noise_diagnosis/cap10_candidate200.zip, SHA8349a0a5f2dca7da52ca7776743bfc3b65b1b6f1d9c1e420bbe1f73df2479e36. Compact diagnosis/source/replay evidence121,949bytes at same prefix/evidence.zip, SHAfb1299ee5fdc6288436af639e90154ac2a2196295b862b8e4d4c322131b5ad9d. No additional periodic diagnostic model snapshots or checkpoint pruning.

### Diagnosis and spending history

User objected to giving up after the failure and requested continued work. Continue diagnosis/completion within the ORIGINAL approved hard stop08:07:36 Warsaw /Unix1791958056.4437666 and total$0.59 GPU ceiling; do not reset the hour. Pod yeacnxxlv5bdr1 also could not restart due to host capacity and remains EXITED. Current sole running pod **s7bscdkn0qtc5q**, same Secure L4 $0.59/h, allocated1791955040.5221214. Local guard19468 and remoteguard200 enforce the unchanged deadline. Cache restored30.61s. No schedules or unrelated changes. State/connection in Saved/MimicKit/pod.json; previous identity retained uniform512-failed-pod.json.

Read-only trace_uniform_failure.py reproduced the failure type (this run at update4/world410 rather than update31/world353; not a claim of deterministic reproduction). On identical first-minibatch observations/advantages/standardized noise, uniform sigma gradient norm230.32 vs original fixed5e-2 noise13.85, a16.63x increase. Before actor updates, max absolute log-ratio8.70e-4; likelihood matching is close, not responsible for97% clipping. Actor mean RMS changes over first four40-step optimizer updates:6.34e-2,1.18,1.38,18.87. Then finite input actions led to nonfinite PHYSICS body position/rotation/velocity, not just an observation conversion. Last finite failed-world body speed component97.03m/s/angular373.56rad/s; requested actions are finite and stock actuator target clipping remains in force. Trace stores one failure model and a compact three-step before/after snapshot, not periodic diagnostic models. Near-zero-noise gradients destabilizing shared policy updates are strongly implicated; the failure world itself has sigma2.64e-2, not minimum sigma.

Completed sequential bounded controls using check_uniform_gradient_cap.py: original fixed-noise512 configuration, uniform noise with upstream gradient cap1, and uniform noise with cap10. Each ran200updates with original terminal MSE/floor start/LR/normalization/controller/physics. Results and preserved evidence are recorded above. User subsequently approved cap10; production resumed from its200-update candidate. No periodic diagnostic checkpoints; finite capped candidates saved one final resumable bundle each.

## STOPPED — original 512 configuration with per-agent noise, October 14, 07:12 Warsaw

User requested a fresh restart of the last decent 512-agent run, changing only exploration noise to a fixed per-agent sigma drawn uniformly from zero to its original 5e-2. Explicitly approved up to one hour on L4, maximum $0.59 GPU. Do NOT apply the prior heading, normalization or LR proposals. Fresh policy/optimizer/normalizers and counters; fixed supine start, 1.5s/45-step terminal body-position MSE, stock humanoid/controller/physics, actor and critic LR 1e-4. The historical 512 evaluation/checkpoint cadence of 50 updates was restored, including deterministic evaluation, under the latest request to restart it exactly. Existing current telemetry cadence and numerical guards retained. Compared neutral_pose.py byte-for-byte with the saved 512 checkpoint: identical. No change to ProjectJournal, Unreal, D/S or PHAT.

Old pod wdpv87u3hcidr0 could not restart (host lacked free GPUs) and remains EXITED with its files intact. Same-price replacement L4 **yeacnxxlv5bdr1** allocated Unix1791954456.4437666; hard stop was1791958056.4437666 /08:07:36 Warsaw. Cached runtime restored in35.06s; no new dependency installation. New run **20261014_070953_neutral_mse_512_uniform_noise**, PID471, launched07:09:53. One GPU only; no schedules. **It failed at update31 and the replacement pod was confirmed EXITED at07:12:29.** GPU-time ceiling $0.0481, not an invoice. Receipt Saved/MimicKit/uniform512-stop-receipt.json. Do not describe this run as active or successful.

Implementation: optional agent_noise.PerAgentNoisePPO leaves stock policy means/critic intact, assigns512 reproducible uniform sigmas using an independent generator, saves their logstd as a model buffer, records each rollout sample's sigma and uses that same sigma after minibatch shuffling for PPO likelihoods. Only an exact PRNG zero is redrawn (continuous uniform has zero probability at that endpoint); no lower noise floor, LR adjustment or normalization changes. Actual sigma min6.142e-5/max4.9975e-2. Three tensor tests passed locally and remotely: stable assignment/state roundtrip, shuffled likelihoods against an independent Normal distribution, stock loss/gradient agreement with equal sigmas. Noise range and actual displayed rollout noise appear in replay metadata/HUD. Test/replayer remains deterministic as in the original 512 run.

Observed failure: last completed update30 =507,904 samples; recent throughput24,122 transitions/s. During update31, world353 first produced nonfinite next_obs at step16, followed by nonfinite actions/observations. Guard rejected the rollout BEFORE PPO consumed it. That world's sigma was3.16225e-2, not the smallest; this does not establish which agent/update caused the instability. Actor clipping fraction in preceding logs was about0.97. Root cause is not proven; do not silently retry with modified hyperparameters. Valid checkpoint0 was readback-verified (SHA411a7031bbe87e774e1950379752a381e3362866ffc2c4af231a0fa4d50b640f;10,922,828bytes), and no invalid checkpoint was promoted. Initial post-update0 deterministic mean MSE0.19710m² is not recovery success. Verified replay has46 finite frames and the requested terminal-only reward. It is an early replay, not the failed update31 rollout.

Persistence: source archive177,944bytes readback-verified at mimickit/pipeline_20261014/uniform512_source_001e55e539da.tar.gz. Failure evidence38,250bytes (logs/configs/telemetry/replay/noise assignment) readback-verified at runs/20261014_070953_neutral_mse_512_uniform_noise/failure_evidence.zip under the same prefix; SHA0f9f1683dba46f591717443543b54965f3af33df8ae98c9926ce2f72b7aaa73c. Existing production checkpoint saving unchanged, no pruning. Local bridge9236 received failure and exited; TensorBoard8035 has chronological run, loss/train,test and health/numerical_failure. Replayer8021 has early replay plus ERROR alert. Observer identities Saved/MimicKit/uniform512-observers.json. No paid restart remains authorized beyond the approved bounded trial without discussing the failed result.

## STOPPED — controlled investigation complete, October 14, 06:55 Warsaw

**Diagnosis complete; pod wdpv87u3hcidr0 confirmed EXITED at06:54:50Warsaw.** All owned diagnostic processes finished. Localguard30552 stopped after checking its command line; remoteguard ended with the pod. Additional GPU-time ceiling about$0.270, below the approved$0.30; this is not an exact invoice. Receipts: Saved/MimicKit/causal-stop-receipt.json and causal-evidence-receipt.json. No production policy, reward, controller, geometry, observations or normalizer behavior was changed. User explicitly approved up to30additional minutes on the SAME L4, maximum$0.30GPU. Hardstop06:57:23Warsaw / Unix1791953843.7756894; remoteguard1667/localguard30552. No new pod or schedule. Production completed at its original cutoff: final2377 /9,740,288samples, readbackverified SHA7b453cca267bdbfcb937dec986ec1675b14bc14fb7a1d0c4fb4b7c365cfbb501. Root stop.request from the earlier guard remains intentional; do not silently resume production.

**The earlier proposal to freeze normalization alone was incomplete and disproved by the controlled tests.** Two mechanisms can independently worsen the motion: changing observation normalization with fixed weights, and oversized optimizer updates with fixed normalization. Their effects interact; do not add their error increases or attribute a percentage of the original regression to each.

Started disposable copies of checkpoint150 with restored learned weights, optimizer/momentum and normalization, fresh physical episodes,128worlds/noise.005. First experiment: five branches,300updates /1,228,800transitions per branch, trainingseed9017. Evaluations use fresh simulators, same128initialposes/action seed7719,74back/54front. Initial bodypositions and initial policy states are bit-identical. All finite. Lower MSE is better:

| Configuration | Mean physical episode MSE |
|---|---:|
| Starting checkpoint150 |0.20521495|
| Original LR1e-6 and updating normalization |0.21859865|
| No actor/critic learning; normalization changes only |0.21643707|
| Frozen normalization; original LR1e-6 |0.24565941|
| Updating normalization; lower LR3e-7 |0.21664752|
| Frozen normalization AND lower LR3e-7 |0.20417538|

Control assertions verify norm-only actor AND critic weights unchanged, and frozen branches' normalization mean/std/count unchanged. Thus the interventions actually isolated those operations. Paired approximate95% intervals for MSE change versus starting policy exclude zero for all deteriorating branches; combined treatment interval[-.004266,.002187] includes zero. This supports preservation, NOT demonstrated improvement/recovery.

Independent trainingseed9018 repeated the main three branches for200updates. Equal200-update physical evaluations: stock .219059(seed9017)/.217047(seed9018); frozen-only .250542/.216570; frozen+3e-7 .205143/.203692. Same direction across both training seeds. The latter remains near baseline, not standing. Example first300-update branch: original head peak .493m versus baseline.586m; frozen+lowerLR .593m. No claim of trained floor recovery.

PPO makes40actor SGD steps per batch with fixed action sigma.005. Lowering LR based on the initialization update did not ensure later small policy changes. Read-only policy movement instrumentation in the second experiment samples the first512bufferstates every10updates: optimizer KL mean/max stock53.34/555.74, frozen29.51/204.78, frozen+3e-7 .0391/.0693. These joint-Gaussian KL values are highly variable, not deterministic constants or whole-batch averages. Normalization occurs after optimizer updates and can change commands independently of LR/PPO clipping. Earlier single copied update and raw clips are retained below.

**Separate real floor-start defect:** current heading extracts yaw from the projected root forward axis, which becomes undefined at pitch+/-90degrees (the chosen lying starts). Exact source-code CPU audit:89.999→90.001degrees changes bodypositions by at most.0000293m, but heading flips180degrees; MSE .286385→.305419 (other side.296229→.320653). The saved policy changes some APPLIED motor targets by28.35/32.08degrees (RMS11.74/13.43degrees). This is not an instantaneous physical joint rotation. Actual baseline rollout has64largeheadingflips with root rotation under10degrees,7after the first frame. This observation/reward discontinuity is confirmed; its share of long-run regression is not isolated. No arbitrary replacement heading was installed.

**Reproducibility audit:** two identical stock one-update runs plus a frozen run start with bit-identical observations, bodyposes/rootrotations, CPU/CUDA RNG and first actions; sampling permutation also identical. Physics diverges after the first step: initial reward difference2.28e-8, next observation max difference.001986, growing over32steps to44.54(in mixed observation units), motor request difference1.20rad. One-update optimizer KL varies208.01 versus.6347 for the two stock copies. This establishes real simulator/policy sensitivity, not a different seed or swapped checkpoint. Do not present a copied single-update KL as an exact historical/live-update reproduction. Heading discontinuity plausibly amplifies sensitivity but is NOT proven to explain all divergence. Three fresh evaluations of the unchanged baseline giveMSE.20521495/.20542671/.20518889: totalspread.00023782, much smaller than the.011–.040 regressions. Thus individual trajectories/updates are sensitive, while the128-world mean regression is robust in these repeats. One-update probes have32steps and no completed45-stepepisode, so their logged return0 is NOT a zero physicalMSE.

Recommendation: fix the floor-heading definition deliberately, then test the good checkpoint with frozen observation normalization and actorLR3e-7. Freezing alone is explicitly NOT recommended. The tested combined configuration prevented measured regression, but did not solve get-up learning; long-run safety/generalization is unproven. No further paid production training started. All evidence/code belongs to this dedicated branch, never ProjectJournal.md.

Evidence: Saved/MimicKit/causal-analysis.json, first-update-reproducibility.json, heading-discontinuity.json; remote causal_regression directory contains all model snapshots, full traces, physical evaluation arrays, per-update metrics, logs and source. Diagnostic .pt snapshots are evidence, not full optimizer-resume bundles; original production checkpoint150 remains the resumable source. Tests preserve old checkpoints, user assets and unrelated processes. Scripts: causal_regression.py, causal_regression_queue.py, analyze_causal_regression.py, audit_heading_singularity.py, analyze_first_update.py, preserve_causal_evidence.py. Initial four branches lack later read-only KL instrumentation; the second seed and traced repeats include it. Total long-branch transitions8,601,600, including1,228,800with learning disabled; three extra one-update probes add12,288. No continual evaluation overhead added to production.

Storage verification: one303,298,150-byte archive PUT failed with502BadGateway after retries. Retained the archive and uploaded19immutable16MiB-or-smaller parts, each readback SHA256 verified; manifest readback verified. Archive SHA34de999bf864b353e4e0fa083a57082693d3804bac0e5a927ab28cc2a8f36a2c. Manifest `mimickit/pipeline_20261014/causal_regression/34de999bf864/parts/manifest.json`. Concatenate listed parts in index order and verify fullarchivehash before extracting. This affects only the diagnostic evidence archive; production saving and retained checkpoints unchanged. No pruning/deletion. Final local helper/source and this updated journal are uploaded separately after shutdown. No new training or restart authorized after the bounded investigation.

## Latest diagnosis — rising loss after initial improvement, October14 06:20 Warsaw

User requested investigation only. Live trainer/settings/weights unchanged; same PID985/rate1e-6/deadline. Added read-only diagnostics `diagnose_regression.py` and `probe_normalizer_update.py`. Disposable copies ran on SAME owned GPU, then exited; no new pod/evaluation cadence or permanent test overhead. Samples and episode counters of production unaffected. Source and detailed evidence preserved in dedicated diagnostic archive, receipt Saved/MimicKit/regression-evidence-receipt.json.

**Regression is real**, not smoothing or changing front/back proportions. Raw training loss minimum.194681 atupdate120, later~.238. Evaluated saved150/500/1150 on identical128randomizedstarts (61back/67front), identical action-noise seed7719/sigma.005, each with a fresh simulator to avoid retained reset/solver state. Initial bodypositions exactly equal across snapshots. Mean episodeMSE .204683 / .226486 / .240578. Both sides worsen: back.198551→.245253, front.210266→.236323. Paired later-minus-early mean+.035895m², approximate95%CI[.032107,.039684] across these128pairedworlds (single seed, not a generalization guarantee). Mean maximum head height falls.5755→.3268m; pelvis.6367→.4076m. No nonfinite state. There is no claim of recovery/standing from these heights.

**Normalizer/network interaction isolated:** early150weights + late1150observationnormalizer givesMSE.203398; late1150weights + early150normalizer gives.211881, versus.240578 for late+late. Therefore changing normalization is a substantial contributor/interacts with learned weights; not proof that normalization alone explains every change. No production normalization swap performed.

Mechanism: upstream BaseAgent._train_iter runs rollout, constructs advantages, updates PPO/critic, THEN `_update_normalizers`. That final operation changes mean/std used to encode poses and can alter actions outside PPO's clipping. Small action sigma.005 magnifies the distribution change; earlier LR reduction only addressed optimizer movement, not input-rescaling movement. Disposable one-update probes restored exact model/optimizer/normalizer/counters but started fresh physical episodes, so are NOT exact historic/liveupdate replays. Atcheckpoint150, optimizer mean-action RMSshift.001497/KL1.255; subsequent normalization alone.0035365/KL7.0039 (2.36xRMS). At1150, optimizer.0005002/KL.1401; normalization.00007770/KL.00338. Early normalization movement is large, later smaller. GaussianKL uses28 independent outputs and fixedsigma.005 on identical batch states.

Optimizer also remains aggressive: logging around110–150 shows meanclipfraction.9124;451–550 .5604;1001–1150 .6301. Clipping is not a hard bound on the total policy change, and stock loop has no KL early stop. These data support stability concerns, not a complete proof of each optimizer step's causal effect on physical loss. No spontaneous NaN or restored-snapshot corruption.

Other checks: reward accounting independently verified previously; horizon bootstrap is exactly0; critic supports negative returns (no positive-value clamp). One-off true discounted-return comparison finds criticMSE improves .001557→.000435 and meanbias remains near0. Discounted episode return also worsens (-.16547→-.19471); increase is not solely undiscounted chart versusdiscounted objective mismatch. Early applied-action clipping11.86% vs late2.07%, reported separately from PPO clipping; do not confuse them or claim raw requests were applied unclamped.

Recommended next controlled experiment (NOT applied): resume a good early checkpoint with observation normalization frozen, compare at the same actorLR first; then reassess optimizer step size/KL behavior. Changing both at once would obscure the cause. All live settings preserved pending user direction. Existing bounded training still finishes/saves at06:24:38 before06:27:23GPUstop.


## Current handoff — sweep complete; selected LR continues, October 14, 06:09 Warsaw

**Only active trainer: PID985**, `20261014_055611_continuous_mse_128_lr1e6_r2`, actor LR1e-6. All task settings described below remain unchanged. No new pod or deadline extension: trainer cutoff06:24:38, hard GPU stop06:27:23 Warsaw. User has been told this cutoff. Remaining training continues on the existing authorization, no schedules. Guard148/local16036 remain. Check `Saved/MimicKit/sweep-observers.json` for current local observer identities.

Three-rate sweep compared at **2,052,096 samples each (update500)**. Mean of five logged training-MSE points over the preceding50updates: LR3e-7 **0.3056890**, LR1e-6 **0.2270894**, LR3e-6 **0.3186700**. Matching PPO clip fractions .2663/.5421/.8454. Middle rate best of these three for this seed/budget; not an exhaustive/global-optimum claim, not recovery success. High rate initially improved but regressed; low rate barely learned. Critic LR1e-4 and all other agent configs independently checked identical. No numerical training failures in these three valid runs. First middle launch's ownership-file race remains explicitly documented below.

Stopped weak trials gracefully after503 completed updates /2,060,288samples each. Final checkpoint502 for3e-7 SHA603c43de723ac4797f070ef03c03e0a9b4071603581bd38ad9ec922860d5adaf (10,969,282bytes), for3e-6 SHAa8c6b8f9ef28dc000c149612c6c9dc13547a803923dd671aa0c164c4432b2bf8 (10,969,168bytes), uploaded/readback verified. Evidence `sweep-stop-evidence.json`, `sweep-comparison.json`; no checkpoints deleted. Winner progressed to580updates/2,379,776samples with finite meanMSE.231647, ~8,166transitions/s alone. Concurrent combined throughput~9,300–9,500/s, a modest gain, not3x. Use equal samples for learning comparison because middle trial's corrected launch was later. Current checkpoint550 verified at time of this note; do not treat that as final.

Independent replay verification reconstructed each frame's body-position MSE with NumPy/SciPy from actual recorded transforms and neutral target. Maximum reward-accounting difference <9e-8m² across three46-frame captures; continuous episode score is sum of scaled per-frame rewards, not just final reward. Fixed the replay footer that initially still showed last-frame reward while HUD correctly showed episode mean. New regression test covers that mismatch; **10pipeline+2dashboard tests pass**, plus actualGPU reset/reward/failure smoke below. UI visibly verified actual-training mode/noise.005, mean-over45frames, allthree separate curves. Replayer currently selects middle LR; TensorBoard filtercontinuous_neutral_pose_mse and loss/train. Screenshots and metrics under Saved/MimicKit. No separate test rollout overhead added.

Error containment rejects invalid batches before optimization, refuses nonfinite model promotion, preserves prior verified checkpoints and isolates failure to its trial. Bridge writes explicit red replay error text, console alert and one Windows error beep (audio availability cannot block telemetry); backup failures included. Per-run ownership AND bridge status/error paths avoid concurrent shared-file races. No NaN replacement, force clamping, silent retry, controller/physics changes. Error JSON includes offending timestep/world; upper-level setup exceptions also persist a failure reason. Existing running trials use the same rollout/parameter guards; later setup-error catch applies on future starts. Final source/evidence archive receipt is `sweep-complete-source-receipt.json` after upload.


## Current handoff — continuous-loss LR sweep, October 14, 06:00 Warsaw

This section supersedes the STOPPED/terminal-loss statuses below. User authorized concurrent 128-world trials, random starting poses (50% back / 50% front), continuous upright-pose MSE, and visible numerical-failure alerts. No new pod, schedule, spending extension, Unreal/PHAT/Blueprint/D/S change or main-journal entry.

Owned Secure L4 pod **wdpv87u3hcidr0**, $0.59/hour. SSH root 213.173.105.19:12198. Existing hard stop **1791952043.7756894 = 06:27:23 Warsaw** remains. Trainers stop by 06:24:38, reserving165s for final checkpoints/readback. Remote guard148, local guard16036. `Saved/MimicKit/sweep.json` lists authoritative concurrent PIDs/run names; do not rely on historical single active_run.json. Each trainer now writes its own owner.json. Per-run stop.request stops one trial; root stop.request stops all.

Current trials (fresh policy/critic/optimizer/counters, common seed):
- `20261014_055611_continuous_mse_128_lr3e7`, PID842, actor LR3e-7.
- `20261014_055611_continuous_mse_128_lr1e6_r2`, PID985, actor LR1e-6.
- `20261014_055611_continuous_mse_128_lr3e6`, PID844, actor LR3e-6.

All use128worlds, action noise0.005, critic LR1e-4, stock humanoid/Newton physics/controllers/PPO,1.5seconds/45ticks. Each reset independently chooses back/front with probability0.5, adds uniform joint-coordinate noise bounded±5degrees, clips to original joint limits, retains zero initial velocities, and translates vertically to put the lowest ORIGINAL collider2mm above floor. No root-tilt noise or geometry changes. Separate seeded reset generator avoids coupling pose draws to action-noise RNG. Random-reset generator state is not yet included in checkpoint continuation; learned policy/optimizer/normalizer/counters ARE preserved, while resume deliberately starts fresh physical episodes.

Reward is **negative per-frame body-position MSE /45 on every tick**. Therefore episode return is negative mean MSE over all45frames (not terminal-only or summed45times). Target remains neutral upright aligned only to current rootXY/heading, retaining standing height and pitch/roll error. No motion imitation, velocity reward or added shaping.141observations unchanged. Continuous and terminal objectives are labeled separately in TB; do not compare them as identical objectives.

Numerical safety: inspect rollout observations/actions/rewards/next-observations and other float experience fields for NaN/Inf BEFORE PPO optimization; report offending timestep/world pairs, reject the whole corrupt batch, stop only that trial, preserve previous verified checkpoints. Also refuse promotion if updated model parameters become nonfinite. No nan_to_num or silent episode-reset/reward changes. Other sweep trials continue. Error JSON, console TRAINING ALERT, TensorBoard health/numerical_failure and bridge audible Windows error notification/red replay error text. Backup errors also surface. Explicit errors remain available; no automatic blind restart or LR change. Each run has independent backup worker and destination; saving policy unchanged, all periodic checkpoints retained.

Validation: actual128-world45-tick GPU smoke passed (61back/67front; exact floor clearance minimum.0019999817m; continuous reward equals independent mean MSE; finite physics, partial reset unaffected worlds). Passive baseline meanMSE.3031317, back.307751/front.298926. Injected NaN at timestep7/world11 rejected before optimization. Existing9pipeline+2dashboard tests passed. No extra evaluation episodes; replay copies an actual training episode, including current noise and mean-over-episode MSE.

Important implementation failure disclosed: initial concurrent launch raced on shared active_run.tmp, aborting the middle LR trial BEFORE training. Fixed ownership file to per-run; retained failed directory/log and restarted only that trial fresh as `_r2`. The other trials stayed running; compare at equal samples because middle trial started later. At06:00, LR3e-7/3e-6 reached170updates, middle70; all finite. Combined throughput~9.5ktransitions/s (~3.2k per trial). Early MSE.3070/.3111/.2812 respectively, NOT matched-step final comparison or recovery proof.

Earlier low-noise failure diagnosis: matched actor-step experiment confirmed reducing sigma0.05→0.005 at unchanged LR1e-4 made first-update KL0.0157→155.8; LR1e-6 restored comparable first-updateKL0.0157. LR1e-5 stillKL1.5688;1e-7KL.000157. This supports reducing actor step size; not proof of exact Newton solver failure cause. Fresh corrected terminal run `20261014_054006_neutral_mse_128_noise0005_lr1e6` completed948updates/3,883,008samples without numerical failure but MSE~.318 did not improve. Gracefully stopped for user's new task. Final checkpoint947 verified SHA c182623ff083293e02577bdba004a2afb16e550d6b794a1a8b2d8da1330e6313 (11,021,108bytes).

Observers: replayer8021 filter055611, TensorBoard8035 filtercontinuous_neutral_pose_mse, historical runs preserved. `Saved/MimicKit/sweep-observers.json` owns bridge/dashboard identities. No checkpoint downloads to laptop; compressed telemetry/replay + incremental event bytes only. Initial source archive readback verified `sweep-source-receipt.json`; later wrapper/UI corrections require refreshed source receipt. Preserve evidence and report actual sweep results before choosing a rate. Source paths `Labs/MimicKitTraining/recovery_pose.py`, `health.py`, `train.py` and `test_recovery_pose.py`.


## STOPPED — 128 run also failed numerically, October14 approximately05:30 Warsaw

128/noise0.005/no-evaluation fresh run failed at update44: new finite-return guard wrote numerical_failure.json and stopped before further updates. Lastlogged40/167936samples, finite meanMSE.248999; lastverifiedcheckpoint0 SHA315c8f8c3f2175176da7687247fd298af257fd6fbdc2868846ce7ed7e30915c1. No claim that128fixed the256failure. Exactfirstcorruptphysicalstate in128was not instrumented; prior256diagnostic confirmsphysicsNaNprecedinggradientcontamination. Notan evaluation ordeadlinefailure. Preserved128telemetry/replay/events/logs in failed128_evidence_6af357fe863f.zip readbackSHA6af357fe863f6e9942536ff6f1ee70da46cb9a9490c4091d192b115be9c1e932,27275bytes. Receipt128-failure-receipt.json. Runpod API confirmed ownedpodwdpv87u3hcidr0 EXITED; localguard21484 stopped afteridentitycheck toavoid redundantstopcall; noGPUbilling; no newpod/restart/extension authorizedafterthisfailure. Saving policyunchanged, no deletion. The requested no-evaluation implementationpassed9CPUtests andactualGPU4updatepipelineverification; production128stillunstableandrequiresdiagnosis/fix. Do not silently change noise/controller/learningrate or call itworking.


## Current handoff — 128 worlds, training-only replay, October14 05:27 Warsaw

User asked why256run was off, requested removing separate test overhead, then said "do128directly". Fresh128world run20261014_052723_neutral_mse_128_noise0005 on SAME SecureL4 podwdpv87u3hcidr0 $0.59/h,trainer1714. Noise0.005 retained; same objective/fixed supine1.5s45steps/physics/controllers/PPO. New authorized clock1791948443.7756894 to HARD STOP1791952043.7756894 =06:27:23 Warsaw. Trainer165s reserve. Remote guard1713,local21484; oldguard1099/10332 replaced after identity checks. Observers128-observers.json bridge20784,dashboard15696,existingTB28800/8035. One GPU workload; no schedules.

256run failed at update100 because recorder rejected nonfinite data; original log firstNaNs in training update80, BEFORE test. GPU remained running, deadline not reached. Lastverifiedcheckpoint50 retained. Diagnostic1 stopped at62 on first nonfinite observation; actorloss/gradient/parameter/action checks finite beforehand, rawactionmax92.108rad. CORRECTION: rawrequests are clamped by vanilla CharEnv;92rad was NOT applied target, so do not claim this alone caused failure. Diagnostic2 confirmedactualphysicsstate corrupt at84, world90:45nonfinite body-position coordinates,32nonfinite body-quaternion components,4dofpositions,28dofvelocities,74observation values. Rawactionmax16716.47 but appliedboundedmax3.351rad; all actionsfinite. Thus physics becomes invalid before feeding NaNs back into PPO. First failing update differs62/84 fromoriginal80; no exact deterministic reproduction or proven root cause of solver failure. No controller clamp/learning-rate/reward/noise/solver workaround applied. Evidence readbackverified noise_failure_evidence_63bfe7c018ef.zip SHA63bfe7c018ef8209ab9316f7e925d6a726c8ae1b64df2217b684db2af3f5aded,12,006,361bytes.128world count is USER choice, not claimed numerical fix. Added stop on nonfinite training mean return before further updates; previous verified checkpoints retained, no NaN sanitization.

Separate test episodes now OFF by default (--evaluate explicitlyoptsin). Genuine optional-test support in pinned vendor BaseAgent:skiptest_model when test_episodes0; test_infoNone meansno fake test scalar. Tracked upstream_optional_evaluation.patch records exacttwochangeblocks. Training/output/sample-count/reset cadence and PPO untouched. No final test either; finaltraining checkpoint still saved/uploaded. Resume config matching permits only requested test_episodes change besides pre-existing explicitheightmigration.

TrainingRecorder copies one actualworld0 trainingepisode each outputperiod. Arms before output; begins on an EXISTINGreset containingworld0, never callsadditionalreset/step; captures45steps+initial. Interruptedpartialcapture discarded atreset. Includes actual trainingnoise0.005, first/lastactionupdateindices (an episode can span PPOupdates), trainMSE, no testMSE; preservesrealcaptureage separatelyfromcheckpoint age. Initial output0maynotyetcontainreplay; appears once firstwholetrainingepisodecompletes. Historical evaluation replay/tests unchanged. MimicKit viewport shows testdisabled and actualtrainingmode/noise;trainandrolloutfinalMSEremain. ExistingTB runhistory kept;128training-onlyrunadded.

Nine CPUtestsPASS10.155s, including zeroevaluationcalls,unchangedupdate/output/resetcounts,reset-boundarycapture withoutsplicing and noextraphysicssteps. Actual256world no_evaluation_smoke_01 completed4updates/32768samples in5.465s aftersetup, no evaluation.json,46finiteframes/1.5s actualtrainingepisode, noise0.005 and trainMSE.190883. Finalcheckpoint3 readbackSHA2f23aa09412fca0a9964e826337f1adc75a08bc1f2f921a690c85c0ce96be923. This is pipelineverification, NOT standing/stabilityproof. Sourcearchive including patchedvendor/wrappers/viewer verified128-source-receipt.json. Saving unchanged; no retention/cleanup added. Mainjournal/Unreal/PHAT/BP/D/S untouched.


## Current handoff — 256 worlds, noise 0.005, October 14 05:03 Warsaw

User requested fresh restart with256agents/action noise0.005 and replay loss/noise display. Same terminal upright neutral body-position MSE, fixed supine1.5s45steps, original physics/controller/PPO. Fresh actor/critic/optimizer/normalizer/counters, resume.json prior_samples0,iteration_offset0. Only owned paid pod wdpv87u3hcidr0 SecureL4 $0.59/hour; run20261014_050315_neutral_mse_256_noise0005,trainer1100. New authorized one-hour clock1791946995.166011 to HARD STOP1791950595.166011 =06:03:15 Warsaw; trainer cutoff165s earlier. Remote guard1099,local10332; old guards612/12500 replaced after identity checks. No schedules. Observers256-observers.json:bridge22104,dashboard11808,existingTensorBoard28800/8035. One GPU workload only.

Persistent volume became full during prior512 run. It stopped/saved at4214 /69,058,560samples, but outstanding upload failures prevented final evaluation. Latest completed evaluation4200 ~.0288m²; NOT final4214 evaluation or recovery proof. Emergency11MBcheckpoint copied toPC with matching podSHA7dde9dfbe38748fc4a2f57ff9d2a7222714b6ecbabc156c83516b99ae39a7248. User explicitly approved one-time removal of redundant MimicKit checkpoints:72objects/817,487,112bytes removed; first/latest/final checkpoints and code/logs/replay preserved. Receipt authorized-checkpoint-pruning.json. THEN user added30GB and explicitly requested NO SAVING CHANGES. backup.py remains unchanged; ALL new periodic checkpoints retained, no automatic deletion/retention added. Recovered all37previously failed512uploads2450..4214 and readback-verified stopped_telemetry.zip; recovered_backups.json confirms. Cloud latest_verified restored to4214. Failed historical evidence retained, no invented final evaluation.

New train.py optional --action-noise checks positive finite value and FIXED Gaussian std type; selected_agent.yaml and provenance persist. Actual checkpoint action distribution logstd=-5.298317432 across28outputs =>std0.005. No other noise removed. Outputinterval50 unchanged from512:409600transitions between points at256worlds. Initial speed~13.4–14.8ktransitions/s; update80/663552samples verified. Checkpoint50 readbackSHAefd2cef66bf1c0b51559f1834fa87a4998d8348ed51581367edc8c12aa14fc74. Comparison changes BOTH world count andnoise, not an isolated world-count test.

Recorder metadata captures train/test terminal MSE and configured training noise paired to evaluation. Replayer viewport permanently shows train/test/this-rollout final MSE(m²), trainingnoise0.005 and displayed evaluationnoise0.000; historical unknown values say not recorded rather than using current config. InitialtrainMSE absent until episodes completed. No per-step extra copies; metrics piggyback existing evaluation. MimicKit-only HUD addition in external Stepper rollout_debug_viewer/viewer.html; before-copy Saved/MimicKit/viewer-before-noise-loss.html. Source archive includes viewer and wrappers, verified receipt256-source-receipt.json. Seven pipeline tests PASS5.12s including recorded metric persistence,real vsconfigurednoise,unknownhistoricalvalues. TensorBoard persistent timestamped run added alongside4096/512; loss/train,test remain positiveMSE on sample axis, same15s bridge/dashboard and50update evaluation.

Keep this branch OUT of ProjectJournal.md; no Unreal/PHAT/BP/D/S changes. No checkpoint-saving-policy change. Finalbilling/evaluation handled by existing independent guards; no automatic next run.


## Current handoff — fresh512-world comparison and persistent TensorBoard

User delegated noise demo to side agent; no noise experiment started here. User requested restart with512agents, chronological timestamped TensorBoard runs, loss/train and loss/test, twice data frequency. Fresh actor/critic,optimizer,normalizer and sample counters confirmed0 in resume.json. Same supine1.5s45step terminal MSE objective,noise.05,controller/physics/seed/PPO otherwise unchanged. Stock minibatch sizes scale with world count: actor4x512=2048,critic2x512=1024; rollout32x512=16384. This is native512world PPO, not a fixed-minibatch isolated physics benchmark.

Old4096run neutral_pose_l4_02 gracefully stopped at133,169,152cumulative samples, finalcompleted1015. Final evaluation MSE.1539672m² (not standing success), checkpoint0001015_final.zip verified SHA c5a0317f55b80736b4f0eb38a190b2bafb5b5b2b4912ee5b8504860c22de916d,10,915,982bytes. Preserved all raw events/replay/checkpoints.

Current ONLY active trainer **20261014_040619_neutral_mse_512**,PID613, SAME owned SecureL4 pod wdpv87u3hcidr0 $0.59/h. New one-hour timer Unix1791943606.7483256 to HARD STOP 1791947206.7483256 (05:06:46 Warsaw), ceiling additional$0.59. Both guard timers explicitly replaced: local12500,remote612; old guards28456/187 stopped after identity checks. No schedules created. Trainer reserves165s before hardstop. Log /workspace/mimickit_trial/neutral_512.log. Current initial measured speed~24,942transitions/s,.657s/update vs4096~47,000transitions/s,2.78s/update. Update200/3,293,184freshsamples confirmed; checkpoint150 verified SHA496b9f58a27dcd37ff354505c9f173388cb604337e01931c01e0f3568fc4d1bf,10,902,817bytes. Initial150evaluationMSE.30437535m²; no recovery claim.

train.py --output-interval50 writes selected_agent.yaml and records actual config; default100 preserved for previous use. Evaluation/TB/checkpoint cadence100->50updates, as stated to user. With512agents samples per interval819,200 vs old4096/10013,107,200; twice points per UPDATE,16x per SAMPLE because world count also changes. Do not claim simply2x per sample. Sync15s (was30),TBserver+UIreload15s, dashboard15s; staged refresh can add latency. Data only, no checkpoint downloads to laptop.

Persistent TensorBoard http://127.0.0.1:8035/#scalars&regexInput=neutral_pose_mse&_smoothingWeight=0 uses Saved/MimicKit/TensorBoardRuns. Chronological Warsaw YYYY-MM-DD_HH-MM-SS_objective_worlds. Dashboard manifest Saved/MimicKit/dashboard-manifest.json combines resumed segments of the same policy without changing sample indices; historical objectives remain under reward/train/test, MSE under loss/train/test with positive error (lower better). Optimizer actor/critic separate, performance uses interval samples/time to avoid upstream resumed cumulative-samples/segment-time error. Excludes zero-placeholder train return before ANY episode completes; includes final evaluated test points. Original event files untouched. Incremental local dashboard.py is bounded until deadline+180; restart dedupe checked. Unit test passes: stitching,sign,sampleaxis,no duplicates,skip empty episode points. Actual512test point spacing verified819200samples. Smoothing0 and no outlier exclusion for honest comparisons. Filtered UI selects4096 vs512,older runs available by clearing run filter.

Observer identities Saved/MimicKit/512-observers.json:bridge12952,TensorBoard28800,dashboard8448. UI verified: readable loss group with test/train, chronological4096/512 runs both selected, zero smoothing, no outlier suppression, automatic reload15s. Proof Saved/MimicKit/tensorboard-4096-vs-512.png. Source/manifest receipt Saved/MimicKit/512-dashboard-source-receipt.json verifies neutral_512_dashboard_c4a7398f8108.tar.gz. No second GPU workload. New source archive+manifest backed up after final observer edits. Keep branch out of ProjectJournal.md; no Unreal/D/S/PHAT changes.

## Current handoff — neutral MSE resumed with new one-hour timer

User asked "i hope you resumed" after clarifying resets must reset the timer. Authorized continuation at same Secure L4 $0.59/h, one-hour allocation ceiling $0.59. Original stopped pod aqdl0hk8g2x8zd could not restart: Runpod returned no free GPUs on its host. Remains EXITED; no GPU billing there. Replacement owned pod **wdpv87u3hcidr0**, allocated Unix1791941239.3246083, HARD STOP Unix1791944839.3246083. Local guard28456, remote guard187; no schedules recreated. New connection Saved/MimicKit/pod.json; original identity preserved Saved/MimicKit/neutral-resume-previous-allocation.json. Runtime/kernel cache restored in31.58s; no package rebuild. Initial background guard SSH wrapper timed out because its shell retained SSH streams; guard process verified alive, no duplicate guard. Later launches use detached subprocess with redirected descriptors. No deadline extension for setup.

Run **neutral_pose_l4_02**,remote PID424, resumes final302 checkpoint SHA35064158ca4c4c11ac5b76827728b7644fa1a88b931cd1941cd17ea673a2fc5c downloaded directly S3-to-pod and rehashed. Preserve actor/critic, optimizer, normalizer and39,714,816sample count because this request is RESUME; reset allocation/run timer. Same negative terminal15-body-position MSE, supine reset,1.5s45steps,4096worlds, stock physics/controller/PPO unchanged. New source from verified neutral_pose_source_4f6b52bf3cda.tar.gz. Trainer deadline reserves165s for final eval/upload. Local bridge9688,TensorBoard22472/8035; identities Saved/MimicKit/neutral-resume-observers.json. Resumed training verified: update303 /39,845,888samples, optimizer and normalizer restored, global offset303, initial throughput40,698transitions/s (warmup). Checkpoint303 readback verified SHAa9466f28c9d793bb5189e91e3eeca10955a29dc0de2397dbb1bb7a86e59e5a95,10,903,035bytes. Replayer run mimickit_neutral_pose_l4_02 selected and verified showing resumed303 evaluation (MSE.274749m²); training advanced to318 /41,811,968samples. Old observer data preserved. Viewer proof Saved/MimicKit/neutral-resumed-replayer.png. New billing cutoff04:27:19 Warsaw.

## Current handoff — stopped run and upright-target audit

User clarified that a training reset also means resetting the duration counter, not only learning/sample counters. Previous launch reset policy/optimizer/sample counters but retained the original allocation deadline: this was the source of the unexpected early stop. Do not silently interpret future reset requests as only resetting learning counters. No new paid run launched during this audit.

neutral_pose_l4_01 stopped after869.367s (14.49min),39,714,816fresh samples, final completed update302. Owned pod aqdl0hk8g2x8zd API desiredStatus EXITED. Final checkpoint0000302_final.zip verified on S3,10,909,760bytes,SHA35064158ca4c4c11ac5b76827728b7644fa1a88b931cd1941cd17ea673a2fc5c. Final4096episode mean MSE.272737592m²; initial evaluation.334514707m². This is error improvement, NOT standing/recovery.

User suspected full pelvis rotation was removed from reward. Executed actual production body_position_mse function with pinned torch_util on synthetic rigidly rotated neutral poses and final replay. It removes ONLY world-Z heading and rootXY, not pitch/roll or absolute height. UprightMSE0,yaw90~0,pitch90.113720,roll90.124429,upside-down.248857m² (rotations around pelvis at neutral root height). Final recorded rollout: pelvis.271159m vs target.882416m; head.116906m vs target1.342461m. FinalMSE.272806376 exactly equals negative recorded reward; vertical error contributes.195756793m². Actual head never rises above.116906m in this rollout. The policy has NOT learned to rise; no evidence that reward accepts lying as upright. Evidence Saved/MimicKit/neutral-upright-audit.json. Why optimization failed to discover recovery is not yet isolated; do not claim sparse reward or controller is proven cause. No reward/physics changes during audit. Stock heading uses projected root+X; its direction is ill-conditioned when that axis is vertical, a separate potential issue not equivalent to cancelling tilt.

## Current handoff — terminal upright neutral-pose MSE replacement

User requested restarting training with full-body MSE to an upright neutral pose. Explicit answers: body POSITIONS only, align target to current root XY and heading while retaining standing height, reward only at episode END. Fresh policy interpretation stated to user; preserve same supine starts/1.5s horizon. Sole reward = negative mean squared error over15 body origins ×3 coordinates in meters² at step45,zero before. No best-over-episode statistic,rotation/velocity reward,exponential shaping or imitation motion. Static target from pinned stock humanoid neutral init_pose.141observations=stock140physical + remaining time; obsolete height records removed from this new task. Actor141→1024→512→28,critic141→1024→512→1. Same stock controllers/physics/PPO and action_bound_weight0.

Stopped previous min_peaks_l4_03 gracefully at70,385,664samples. Final536 checkpoint readback verified SHA83e3f941dc25fa06485d6d0dfaa2e09cb5c9c1219fc20ba3b01194de38749cb1,10,952,921bytes; final same-objective evaluation.4418317m,45steps. Preserve failed/old evidence. Same owned pod aqdl0hk8g2x8zd; hard stop Unix1791940235.583346 unchanged. No new one-hour allocation authorized, no schedules to recreate. New task neutral_pose is separate from historical head_height; fresh run neutral_pose_l4_01 is RUNNING (remote PID1832), no resume checkpoint. Initial verified progress: update40 /5,373,952fresh samples,47,170transitions/s. Initial deterministic evaluation mean final MSE.3345147m² across4096episodes; no recovery claim. Numerical tests PASS: neutral zero error, yaw+XY invariance, vertical error retained (.3m raise gives.03m²), single-body perturbation weighting. Actual64world×45step physics PASS:141finite observations,15bodies,only final negativeMSE reward,partial reset,CUDA graph. Neutral foot bottoms.001m; initial supineMSE.320651m²,passive final.305490m². New scripts/config under Labs/MimicKitTraining, no Unreal/D/S/main journal changes.

Launch verification: initial checkpoint0 readback verified on persistent S3, SHA2bebc3362e791deabcd1bcc9af93932b11fab11fc7fa84c037fbf235fbcbccda,10,902,870bytes. Source archive neutral_pose_source_4f6b52bf3cda.tar.gz verified before launch. Replay independently checked with NumPy/SciPy:46frames,15bodies,zero interim rewards; final calculated MSE.334517399m² vs recorded reward-.334517449. Evidence Saved/MimicKit/neutral-replay-verification.json. Six existing CPU pipeline tests PASS8.509s. Bridge11380 and TensorBoard24784/8035, identities Saved/MimicKit/neutral-observers.json. Replayer8021 selected mimickit_neutral_pose_l4_01; initial replay is update0 until next periodic evaluation. TensorBoard Test_Return is NEGATIVE MSE (closer to0 is better); evaluation.json also reports positive MSE. Source and checkpoints backed up; no schedules recreated. Original spending guards unchanged.


## Current handoff — performance audit finished; training resumed unchanged

The user requested removing schedules and investigating speed. The ONLY schedule belonging to this thread, pelvis-and-head-rl-one-hour-checks, is deleted. No replacement schedule. Independent spending guards still enforce owned pod aqdl0hk8g2x8zd HARD STOP Unix1791940235.583346 ($0.59 allocation ceiling). Keep this branch out of ProjectJournal.md. Do not alter unrelated paused automations.

Current run **min_peaks_l4_03**,remote PID1527, resumed verified checkpoint460 from min_peaks_profile_01. Policy, optimizer, normalizer, objective and physics unchanged by audit; profiling/benchmarks are off. TensorBoard8035 PID20564,bridge21264, replayer run mimickit_min_peaks_l4_03; identities Saved/MimicKit/audited-observers.json. Launch verified: continued from60,424,192samples/global offset461, restored optimizer/normalizer; checkpoint461 SHA30eb634f00b243e56ccf3015ffd4fd9aae38820010a23374ca6374f54378950c verified (10,950,624bytes). New evaluation mean.464m under the unchanged minimum-of-peaks objective,45steps. Pre-audit checkpoint460 SHAad7cc7e1ee6f5b0e78ef67a8b22eed96e4647aacb703ec6cef7722fa016db10b,10,952,919bytes. Scoped disposable solver benchmark finished; no second GPU workload left. Source/evidence readback-verified in performance_audit_7d050699d53f.tar.gz (207,543bytes); receipt Saved/MimicKit/performance-source-receipt.json.

Measured performance (two lightly instrumented actual PPO updates):2.653/2.690s per131,072transitions. Physics mean1.9175s(71.8%); actor updates.3998s(15.0%); critic.1502s(5.6%); observation/reward/done.0869s(3.3%); return/advantage preparation.0527s(2.0%); action inference.0361s(1.4%). Nested minibatch gathers13.48ms are INCLUDED in actor/critic, not additive. Normalizer~.3ms. CPU time under observations includes waiting for asynchronous physics; do not report that1.98s as actual observation compute. Normal unprofiled baseline48.4ktransitions/s. Detailed trace took10.34s once including collection/processing; excluded from steady measurements. Instrumentation removed after three updates. L4 near72W cap,56C,no thermal slowdown; no power/OS changes.

Precision experiment on copied model and a real fixed training minibatch: FP32 actor/critic8.407/3.908ms; TF32-style high precision5.337/2.007ms; BF162.135/1.004ms. Estimated full-update time reduction~7%/~13%, not measured end-to-end speedup. Actor gradient relativeL2 differences6.66%/23.83%,critic.237%/4.79%; output max differences actor.000123/.001448. PPO clipping makes tiny prediction differences meaningful for gradients. NOT adopted; needs a bounded learning-quality comparison. Original precision restored after experiment, no benchmark optimizer update used for training.

Investigated backend sparse selection: humanoidnv34, MJWarp auto thresholdnv>32. Sparse factorization issues24 sequential qLD_acc kernels per physics substep. Tested supported dense Jacobian/mass layout with same solver limits/accuracy/contacts/timestep and all4096 sampled action sequences. Sparse45step physics2.7216s vs dense3.2503s: dense19.4%SLOWER; rejected. Scores.4151586/.4151466, body trajectory RMSdifference.0070m,max.7198m; first stepmax.00412m. No off/off control in this layout comparison, so do NOT attribute every trajectory discrepancy solely to layout; parity not established. Both finite and45steps complete. Benchmark explicit setup37.53/38.19s includes variant kernel compilation; duplicate initial attempt cancelled before measurement to preserve SolverMuJoCo isinstance behavior, then used a subclass. No unrequested accuracy reduction, collision removal, frequency change, world-count change or mixed precision applied.

Evidence in Saved/MimicKit/PerformanceAudit/:profile_0/1/2.json,profile_ops.json/txt,precision_benchmark.json,solver_benchmark.json. Standalone diagnostic scripts profile_training.py,benchmark_precision.py,benchmark_solver.py are opt-in and leave ordinary runs unchanged. External py-spy attach denied by container security; capabilities unchanged. Strongest measured conclusion: physics dominates; no validated dramatic free speedup. Further speed work should measure throughput AND learning quality before deploying altered precision or solver settings.


## Current handoff — schedules removed, performance audit in progress

User explicitly requested removing schedules and investigating training speed deeply. Deleted `pelvis-and-head-rl-one-hour-checks` through automation API; no other schedule for this thread exists. Preserve unrelated paused schedules. Independent spending guards remain unchanged at Unix1791940235.583346; do not recreate a follow-up schedule. Existing reward/body/controllers/PPO remain unchanged.

External py-spy attachment was refused by the container (no SYS_PTRACE); did NOT change container/security capabilities. Installed isolated py-spy tool only for that attempt, no training dependencies changed. Baseline48,430transitions/s,2.706s/update; L4 near72W power limit,56C,no thermal throttling. Saved/stopped `min_peaks_l4_01` at51,249,152samples,final390 checkpoint verified SHA f1c95de1654a19d045d89287c8ec60f9ec1f72ff2b4573a7834811a1a32612ab. Resumed `min_peaks_profile_01` PID1005 from exact checkpoint with unchanged config/state, solely adding three profiled updates after warmup. Profile wrappers restore all methods afterward. Two coarse timings plus one CPU/CUDA trace; nested ranges must not be summed. Disposable copied-model benchmark compares FP32,TF32 andBF16 timings/errors, with original precision restored and no policy/optimizer updates from benchmark. No acceleration applied yet. Profile observer IDs Saved/MimicKit/profile-observers.json (bridge16248,TensorBoard20236,port8035); current replayer run mimickit_min_peaks_profile_01. All profiling is bounded and same GPU, no second job or deadline extension. Await measurements before recommending changes.


## Current handoff — minimum of independent peaks, October14

User changed the objective to **min(max_t head Z, max_t pelvis Z)** and requested resume. Each maximum is independent and may occur at a different control tick. Same supine start,1.5s/45-step horizon, stock humanoid/Newton/controller/PPO and terminal-only reward. No imitation or extra task rewards. Old `pelvis_head_l4_02` stopped gracefully at37,093,376 samples; final evaluated checkpoint282 readback verified: SHA1dd7688bbee35d3164557c54f22b57619be6c94d8ca4cbf6191cb8ce7896ecb6,10,922,287bytes. Final old-objective evaluation1.0608668m peak simultaneous sum,4096episodes/45steps. Finalization now verified end-to-end; this value is not comparable to the new reward.

Same owned pod **aqdl0hk8g2x8zd**, Secure L4$0.59/h. Hard stop remains **Unix1791940235.583346**; no new allocation or extension. New run **min_peaks_l4_01** prepared to resume final282 with global offset283. Preserve all learned weights, optimizer momentum/counters, normalizer and cumulative samples; fresh physical episodes. To give the policy both independent records without reinterpreting its learned inputs, retain the previous142 inputs and append head/pelvis maxima. New actor/critic input width144; appended weights/momentum are zero. New channels start unit normalization. Old sum-peak input remains solely for exact policy compatibility; reward does not use it. Critic is preserved and must relearn the changed return scale. No transfer-quality claim.

Validation before launch: production CPU accounting passes with peaks at different times (expected1.1m vs instantaneous-minimum maximum.4m), zero rewards until45, final-step peak, partial reset and144-wide observation. Actual final282 checkpoint expansion preserves old weights/momentum and actor/critic outputs within floating-point tolerance. Strict resume config matching remains, permitting only this exact old-to-new objective migration. GPU smoke passes64worlds/45steps, finite144-wide observations, exact reward accounting and partial reset, cached CUDA physics graph. Resumed launch CONFIRMED PID852, global offset283,prior37,093,376samples; first checkpoint283 verified SHA758cbd94c30e65c62e3805d800b8aa1be8c615e5442eb4ccb5d4f5eb45cb8549 (10,950,593bytes). First4096-world evaluation new objective mean.371m,45steps. Actual replay46frames finite and terminal reward matches independently measured peak minimum. Six CPU pipeline tests pass10.749s in the existing Robotics environment; initial attempt in lightweight Python lacked MuJoCo (environment failure only). Observer bridge22812/TensorBoard15936 at8035; replayer8021 selected mimickit_min_peaks_l4_01. Source archive minimum_peaks_source_1a2f36229b08.tar.gz readback verified. Automation pelvis-and-head-rl-one-hour-checks updated with new objective/run and unchanged deadline. Initial throughput45,655transitions/s; not a final performance or recovery claim. Preserve this branch outside ProjectJournal.md.


## ACTIVE continuation — user approved another one-hour run, October14

User: "do it for 1h go". Owned pod **aqdl0hk8g2x8zd**, Secure NVIDIA L4 **$0.59/hour**, allocation Unix1791936635.583346, HARD STOP Unix1791940235.583346; maximum GPU charge$0.59 for allocation including setup. New authorization supersedes old completed deadline ONLY for this new pod. Never extend or allocate another without permission. Local guard PID4844,remote guard180. Remote launcher221. Same existing runtime/cache reused; startup log `/workspace/mimickit_trial/pelvis_head_resume.log`.

Run **pelvis_head_l4_02**,4096worlds, resumes verified old combined-reward checkpoint27 (3,670,016samples), preserving weights/optimizer/normalizer; fresh physical episodes. Reward/body/controller/episode/PPO unchanged. Existing config equality check still required; removed blanket refusal to resume the pure-RL task. Six pipeline CPU tests pass4.049s, including exact next-SGD-update restoration. Combined reward accounting test runs before launch.

Final replay issue FIXED in wrapper: after completed/stopped training, stock deterministic test_model records final policy, explicitly labels it with last COMPLETED global iteration, then makes immutable checkpoint_XXXXXXX_final.zip containing matching evaluation/replay plus TensorBoard/log files. Standard165s reserve before billing deadline covers~3s evaluation and verified upload. Existing periodic snapshots unchanged. Finalization not yet exercised end-to-end; verify final marker/replay at completion. Source archive `mimickit/pipeline_20261014/resume_source_4face5f5219b.tar.gz` readback verified before training. Full original vendor source bundled, current wrappers/config included, no secrets.

Local observers: bridge18564,TensorBoard2400 on8035,replayer8021 run **mimickit_pelvis_head_l4_02**. Old8035TensorBoard was replaced only after PID/command-line identity check; older runs' data preserved. Observer identities Saved/MimicKit/pelvis-resume-observers.json. Automation **pelvis-and-head-rl-one-hour-checks**,15min×5, ACTIVE; at completion preserve data/delete only owned pod/report and pause. Independent guards enforce deadline regardless. Keep branch OUT of ProjectJournal.md and leave Unreal/D/S untouched. RESTORED TRAINING CONFIRMED: optimizer/normalizer restored,prior3,670,016samples,global offset28; cumulative count passed4,194,304. Initial resumed evaluation peak(head+pelvis)mean~.416m,45steps. Checkpoint28 verified S3 SHA1a77f8aec056db41336e71e62693d24444703b8db764046a71d58b3003d7f495,10,917,157bytes. Runtime restore38.889s. No recovery claim.


## Final trial state — October14

Combined pelvis+head run stopped at original deadline reserve after28updates/3,670,016samples,83.51s trainer time. Finalcheckpoint27 verified on persistent storage, SHA90148dca472842f2d3f2416e06672055d8a7a03d58d51d72d244549fccfdd754,10,916,980bytes. Mean recent throughput~46,700transitions/s. Only evaluation0 was captured because output interval100 exceeded this short remaining trial; **replayer is initial-policy evaluation, NOT finalcheckpoint27**, final recovery ability not evaluated. Do not claim final learned result from it. Runpod API confirmedEXITED; owned pod then deleted after final telemetry archive readback verification. Code/runtime/checkpoints and all locally received final TensorBoard/telemetry persist. No paid GPU remains owned. Original spending ceiling$0.59 for one-hour allocation; exact billing not queried. Receipt Saved/MimicKit/pelvis-head-final-retirement.json.


## Current handoff — pelvis + head objective, October14

User revised the pure-RL objective to pelvis height + head height and explicitly asked to resume implementation before explaining NN architecture. Implemented terminal reward = max over45 control steps (including initial pose) of [head_body.Z + pelvis_body.Z], equal weights. This is maximum of the simultaneous sum, NOT sum of independently timed maxima. Same1.5s supine episodes, no imitation or other task rewards. Fresh policy `pelvis_head_l4_01` launched PID950 on existing pod; no old reward/critic state reused. Previous head-only run stopped at5,242,880 samples, finalcheckpoint39 verified SHA275f503150e3a0c5c58b364a403b4dfc08b28243dabdf5397983f2612f115f6e,10,916,702bytes. Existing GPU deadline Unix1791935610.5302784 unchanged, trainer reserve165s. Only a short pilot remains; do not extend/rent without permission.

Changed production score calculation and telemetry labels, versioned objective in saved YAML, kept peak/time observation and PPO/controller/physics unchanged. Test `test_combined_height.py` executes production height sum, maximum tracking, terminal reward and done logic with peaks at different times: verifies max(sum)=1.5 rather than incorrect sum(max)=2.3; final-step peak1.6 included, earlier rewards zero. Passed remotely before launch. Original64-world physics smoke still applies to unchanged physics/horizon; new replay must verify actual combined score. Local source compiles. Replayer `mimickit_pelvis_head_l4_01`; TensorBoard8035. No main journal edit. Training confirmed through first updates. First4096-world evaluation combined peak mean.348732m,45steps; actual46-frame replay verifies final reward equals max(headZ+pelvisZ), zero interim rewards, all finite. Checkpoint0 verified S3 SHA bf9744bd4024d173e6bda1d2e42b3388acfa4535c640992bb6f8a0f4ec26bd0d (10,916,980bytes). Source archive pelvis_head_source_f98af08a62c0.zip verified. No recovery claim. Actual NN architecture checked in pinned source: separate actor142->1024->512->28 and critic142->1024->512->1, ReLU,1,357,341parameters total; file name fc_2layers_1024units does NOT mean two1024layers.


## Current handoff — pure RL replacement, October 14, 2026

User stopped the imitation run and requested pure RL, episode length1.5s, sole objective maximum head height over the episode, starting lying on floor. Walking run stopped gracefully at92,405,760 cumulative samples; final completed checkpoint704 verified on S3: `mimickit/pipeline_20261014/runs/humanoid_walk_l4_01/checkpoint_0000704.zip`,16,292,617bytes,SHA25692ee63382fb28d2eb494f6dded069a166b196d566f9c6e9b78ee95abda7518f6. Latest walking evaluation at632 reached mean300steps/10s,return255.938. No walking policy weights reused for new task.

Replacement `head_height_l4_01` is RUNNING fresh training (remote PID707) on SAME pod opbcw8bjhuhsys, SAME hard deadline Unix1791935610.5302784, no additional allocation/budget. Guards remain; trainer stops165s early for backup. First GPU updates/evaluation complete; checkpoint0 verified on S3 (10,916,702bytes,SHA2567a92740405a2b965fbb5fe97f784fc538024304f37e4cde31515129f563255e6). Initial deterministic peak.115m; no recovery claim. TensorBoard8034,bridge/replayer run `mimickit_head_height_l4_01`; observer PIDs in Saved/MimicKit/head-height-observers.json. Source patch archive `mimickit/pipeline_20261014/head_height_source_c50082464deb.zip` readback verified; paired with previously backed-up upstream/runtime. Actual smoke receipt saved locally as Saved/MimicKit/head-height-smoke.json. Previous scheduled heartbeat no longer exists (update returned nonexistent); do not assume it will monitor. No main journal edits.

Implementation `Labs/MimicKitTraining/head_height.py` directly subclasses CharEnv, avoiding DeepMimicEnv/ref character/motion library sampling/tracking/target observations. Stock humanoid geometry/mass/inertia/controllers/Newton physics/PPO architecture unchanged. Fixed supine reset from stock initial joint pose, rootY=-pi/2,rootZ=.11500003m; lowest original collider5mm above floor. All45control steps at30Hz run, including falls. Peak includes starting head BODY origin height and subsequent control-step samples (not a continuous-time or240Hz substep maximum). Final reward alone equals this peak in meters. Peak and remaining horizon are appended to state so the objective is observable. SUCC flag2 is used as upstream TRUE terminal/zero bootstrap; it means finite horizon completion, NOT recovery success. Stock discount.99 kept: fixed45-step terminal reward has the same constant discount factor for every full episode. No tracking/shaping/energy penalties; action-bound auxiliary weight changed10->0 per sole-objective request. Stock actuator command bounds remain. PPO policy surrogate and critic regression remain necessary learner losses. Fresh observation size142.

Required tests BEFORE training: production reward accounting verifies earlier peak persistence and final-step maximum, zero rewards before step45, termination only45. Actual Newton CUDA smoke64worlds×45steps passed; finite observations/rewards, total reward=measured peak, partial reset clears only selected episodes, physics CUDA graph present. Initial head height.115m,passive peak.117592m. Remote report `/workspace/mimickit_trial/head_height_smoke.json`; code `test_head_height.py`, deterministic geometry preparation `Saved/MimicKit/prepare_head_height.py`. Do not interpret fixed episode length as learning. Compare peak-head-height reward and actual posture/replay. Checkpoints include custom task source/config, telemetry/replayer explicitly label horizon flag as non-success. No new physics tuning.


## Current handoff — one-hour trial running, October 14, 2026

User explicitly approved **one hour on Secure L4, maximum$0.59 GPU cost, with an early learning-progress check**. Owned pod `opbcw8bjhuhsys`,allocated Unix1791932010.5302784,hard GPU stop Unix1791935610.5302784. Identity/connection in `Saved/MimicKit/pod.json`; never allocate another pod or extend without user approval. Local guard21300 and remote guard bound to this identity. Runtime restored from verified persistent cache in **32.30seconds**,including real authenticated download,extraction,kernel restoration and import/device verification. Full fresh-pod cache reuse is now proven; no pip installation ran. GPU buffers/world construction and matching kernel loading still happen per process.

Run `humanoid_walk_l4_01` uses4096worlds,stock walking configuration. Resumed verified benchmark4096 checkpoint31 (4,194,304samples),including learned weights,SGD momentum/step counters,normalizer auxiliary state and RNG. New physical episodes; not bitwise continuation. New `resume.py` is tested: six CPU tests pass,including exact equality of the next SGD update after save/restore. Resume rejects mismatching engine/environment/agent configs. Upstream local iteration resets to0 so its mandatory first evaluation/log initialization works; checkpoints,replayer and status use global iteration offset32. TensorBoard's Iteration tag is local to this segment; Samples is cumulative. Do not mistake that local counter for lost training.

Live confirmation: global sample count passed5,505,024,normalizer/optimizer restored,first evaluation return13.6 (benchmark13.425). Too early to claim learned walking. Checkpoints now also bundle evaluation JSON,replay and resume metadata. Prefix `mimickit/pipeline_20261014/runs/humanoid_walk_l4_01/`. Exact running source archive receipt `Saved/MimicKit/source-backup.json` (at launch `source_1727aa0ed1c0.tar.gz`). Observer only runs during stock evaluations; fresh logger outputs explicitly flushed at saved checkpoints for prompt TensorBoard updates.

Local bridge19364,TensorBoard21936 on8033; new replayer run `mimickit_humanoid_walk_l4_01` on8021. Bridge/telemetry now accept a run name so stale benchmark completion markers cannot end a new stream. Scheduled thread follow-up `mimickit-one-hour-trial-checks`:15-minute checks,at most4,with first learning assessment,graceful stop on stalled/unresponsive learning or numerical/backup failure,and final storage verification/pod deletion. It must never extend the spending deadline or change vanilla training settings. Independent guards enforce the cap even if follow-up does not run. Check actual episode duration and motion,not reward alone. Finish/pause the follow-up after final reporting. Keep this branch out of ProjectJournal.md; no Unreal/Jolt/BP/D/S work.

## Completed L4 benchmark

**Benchmark completed; owned L4 stopped (EXITED) after27.96minutes including setup**, about$0.275 GPU cost at the approved$0.59/hour. Final cleanup deletes the stopped pod after verified source backup. No long training job/automation running. User approved only this short L4 benchmark; report results before further paid training. Preserve Unreal,PHAT,BP,D/S and unrelated processes. **Keep this branch out of ProjectJournal.md.** User's newest requirement: reusable setup costs should be paid once, not each training.

Measured32 stock PPO updates per batch size, identical seed.1024 worlds:1,048,576samples,**22,544 transitions/s**.4096 worlds:4,194,304samples,**38,763 transitions/s** (1.72x faster). Steady throughput is median update time after first five updates; includes physics,rollouts and PPO,excludes initialization/evaluation/saves. Entire runs after initialization64.78s and146.99s respectively, including evaluations,saves and observer microbenchmarks.100M transitions at the larger steady rate would take about43minutes; this is not a convergence prediction.

These benchmarks do **not** establish learned walking: mean final evaluation episode lengths1.002s/1.017s and returns12.819/13.425. Stock human15bodies,28jointDoFs plus root,50.05kg,original geometry/controller/reward/PPO. Policy30Hz,physics240Hz,original CUDA physics graph. Runtime actually reports Torch2.8.0.dev20250319+cu128 despite the image's2.8.0 tag; exact freeze is preserved.

Observer measurement: six64-step segments,off/on/on/off/off/on. Median difference+0.35% at1024,-0.23% at4096,within a small timing-noise band. Pose capture only runs during original evaluations; no copies during PPO collection. Direct GPU check found capture does not mutate body positions/rotations. Stock repeated resets did **not** produce identical trajectories, even off-versus-off (4096 maximum1.3706m); do not call this a deterministic trajectory-equivalence test. Cause was not investigated or changed for this benchmark.1024's older report field `identical_action_final_pose_max_difference` means repeated-reset difference, not identical simulator-state proof.

Replayer `http://127.0.0.1:8021/`,selected run `mimickit_humanoid_walk_01`; original humanoid and feet visually verified. Actual Newton world0 poses,cut at first complete failure/timeout,no reference-animation substitution. TensorBoard `http://127.0.0.1:8033/`,process3724; real upstream scalar tags verified. Upstream logger emits at output iterations and may buffer120s; not a per-update chart. Local bridge9304 finished and removed its active marker. Total laptop telemetry37,681bytes; checkpoints downloaded to laptop:zero. Viewer playback stays local. Existing viewer stop/pause buttons are not remote Runpod controls.

Persistence on volume `aj7d2jzwuq`,EU-RO-1:

- Both runs have update0 and31 checkpoint bundles (~16.18MB each),uploaded cloud-to-storage then streamed back and SHA256-verified before publishing latest markers. Prefixes `mimickit/pipeline_20261014/runs/benchmark_1024/` and `.../humanoid_walk_01/`. Include vanilla model,SGD state,counters,RNG/normalizer auxiliary state,configs,freeze,provenance. Physical episode state is not saved; resume must start new episodes. Resume loader still needs implementation; do not claim bitwise continuation.
- Logs,reports,configs,events,replay: `mimickit/pipeline_20261014/benchmark_evidence/mimickit-benchmark-evidence.zip`,82,594bytes,readback verified.
- Reusable dependencies: `mimickit/runtime/2bbcd197e97303ae.tar.gz`,409,880,235bytes; SHA256 `2bbcd197e97303aee0e1977eabbe9c386572f64d7a0e3f67180fa68fcaf786ce`. Packaging/upload/readback168.52s once. Extracted to container-local disk; Newton/MuJoCo imports and L4 access passed (`RESTORE_IMPORT_OK`).
- Compiled kernels: `mimickit/runtime/warp_e0e8ef63d6aa4847.tar.gz`,26,686,140bytes,readback verified. CUDA cache reuse already observed on second benchmark: many seconds of compilation became millisecond loads. CPU objects excluded to avoid host CPU feature assumptions. Changed GPU architecture/code can require fresh compilation under Warp's own cache keys.
- First setup mistakenly installed packages on network-mounted `/workspace`,causing slow small-file writes. New setup installs/restores on `/opt/mimickit-runtime` and preserves the stable workspace path via symlink. Future matching-image pods run local `cloud.py cache-hint` immediately before remote `setup.sh`; no fresh pip resolution. Restore checks base image/Python/Torch/CUDA compatibility and full-file SHA256. Uses stdlib HTTP and tar,without bootstrap dependencies.
- Runpod rejected query-signed URLs with401; standard SigV4 Authorization headers worked. Cache hint contains short-lived headers,chmod600,never archive/print it. Real ranged download206/1024bytes verified. Fresh-pod automated restoration remains untested; archive extraction/import and authenticated download components were individually tested on this pod.
- Latest code archive and verified receipt: `Saved/MimicKit/source-backup.json`. Includes pinned upstream source,official clip,wrappers,this journal; excludes credentials/build caches. Never route runtime/checkpoints through laptop.

All5 CPU tests pass (latest0.909s): partial recording refusal,disabled recorder neutrality,pose/axes conversion,stock feet,corrupt-storage refusal. Numerical evidence: `Saved/MimicKit/benchmark-results.json`, `cache-and-evidence-receipts.json`, `l4-stop-receipt.json`, `bridge-status.json`. Owned L4id`hkkg3htrc7zkat`; final retirement receipt records deletion. No paid pod should remain idle after preserving evidence.

## Preparation notes (superseded by completed benchmark above)

User authorized a new isolated vanilla MimicKit humanoid trial on Runpod Community, with low-bandwidth TensorBoard/replayer and code/checkpoint backups to the existing persistent volume. The old physical-recovery/Jolt branch stays stopped. Do not add this work to ProjectJournal.md. No Unreal, PHAT, Blueprint or D/S changes.

Task selection: stock DeepMimic humanoid PPO with the supplied `humanoid_walk.pkl`, replacing only the example spinkick clip. CharEnv alone has constant reward, so is not a useful learning test. Preserve upstream reward, body, controller, physics, PPO architecture and optimizer defaults. Newton1.0.0 is the upstream documented tested backend; its sim extra pins MuJoCo3.5.0/MJWarp3.5.0.2. Warp1.12.1. No Jolt matching.

Source pinned locally at MimicKit commit `2ed1e6c093bb0829f55d33cb4f7a1731cfe6cb69` under ignored `Saved/MimicKit/vendor/MimicKit`. Small integration wrappers under `Labs/MimicKitTraining`. Stock walking clip obtained from official archive using ZIP byte ranges:38,938 bytes,94,552 total bytes transferred instead of402,403,772. SHA256 `43f081d533a62aa440d2c3dae9089fe370e32f97ca349c288f9b866c0ac2fbcc`.

Storage: existing Runpod volume `aj7d2jzwuq`,EU-RO-1,170GB. Existing locally configured Runpod/S3 credentials work; credentials never placed in code/archive/logs. S3 write/readback verified,53-byte probe at `mimickit/pipeline_20261014/storage_probe.txt`. Remote-to-storage transfer avoids laptop checkpoint downloads. Code and checkpoint backups still need final publication verification.

Capacity: Community4090$0.34 and L40S$0.79 allocation attempts rejected for no capacity. Allocated PRO5000Blackwell48GB at$0.82/hour, pod `iyiv4fxfje2vv3`, prepared a163,482-byte source archive and began dependency installation. User challenged value before training. **Stopped and deleted that owned pod**, no training launched/no checkpoint lost. Receipt `Saved/MimicKit/pod-retired-iyiv4fxfje2vv3.json`. Fresh availability advertised5090$0.69 but actual allocation also rejected. No current owned paid pod. Asked whether to benchmark SecureL4$0.59 or wait for cheaper Community capacity; dependent allocation awaits answer.

Wrappers are prepared but not yet GPU-validated. Replay captures only world0 during existing deterministic evaluations; requires a complete episode including failure/timeout and records actual Newton body transforms. Physics remains stock CUDA graph. Training updates perform no replay GPU copies. Local bridge uses compressed incremental TensorBoard events and compact NPZ replay over SSH, never downloading checkpoints. Background S3 worker verifies uploaded checkpoint bytes before updating latest_verified; source/code backup separate. Training bundles retain vanilla model plus optimizer/counters/RNG/normalizer auxiliary state; physical episode state is not saved, so any later resume uses fresh episodes and must not claim bitwise continuation. Resume loader is not yet implemented.

User subsequently approved **Secure L4 at $0.59/hour for a short benchmark**. Allocated `hkkg3htrc7zkat`, identity in `Saved/MimicKit/pod.json`. Hard limit is **30 minutes including setup**, allocation Unix1791929914.928, stop by1791931714.928. Local guard PID25136 plus remote guard target only this pod. Retired PRO5000 guard17012 was stopped by identity. No longer training authorization is implied by this benchmark. No automation created; do not reuse old physical-recovery overnight prompts.

CPU validation: all five observer/geometry/backup tests pass (.414s). Incomplete episodes are refused; recording disabled leaves mock physics unchanged; coordinate transform and stock foot geometry checked; deliberately corrupted storage readback cannot publish a verified marker. Initial source archive167,693bytes verified on persistent volume at `mimickit/pipeline_20261014/source_6ea95e66e05b.tar.gz`. Final wrapper version will be backed up again after integration checks.

L4 provisioning confirmed NVIDIA L4 with23GB usable VRAM. Dependency installation is in progress on the pod; downloads stay cloud-side. Plan:32 actual stock PPO updates each at1024 and4096 worlds, then matched capture off/on microbenchmarks. Final checkpoint bundles include runtime package freeze and source/task provenance. Replay and TensorBoard hooks still require live validation. No completed training or performance claim.



## October17 — side-chat replay storage cleanup

User explicitly requested deleting replayer rollouts older than24hours. Removed 6817 persistent-storage replay recordings/old replay pointers; 14622648001 bytes freed. Every deletion independently returned404 afterward. No checkpoints, source animations, code, trainer/pod state or recent replay files changed. Replay files embedded inside checkpoint archives were retained. Two large non-replay dataset directories excluded from the final listing; no dataset deletion. Exact file manifests, cutoff timestamps and receipts: Saved/MimicKitEquipment/rollout-cleanup-20261017{,-extra,-focused}/; aggregate summary.json in rollout-cleanup-20261017. This was a one-time cleanup, not a retention-policy change.
