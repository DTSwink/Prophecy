# Slow loco policy — November 1, ten motions with signed limp-idle commands

**November 3 disabled-friction half rule — VERIFIED RUNNING.**
Resumed latest25579_final on retained pod9snbu59mla2xcd as
20261103_215952_uefn_slowloco_disabled_curriculum_dead_friction_half_2048,
trainer16389/guard16390. Checkpoint saved locally+persistent, SHA256
1ecaa990cb6657ce2233e98c53e55f5b9c47288480cd24e03d0ed969c869b090.
Preflight passed2048worlds, all16 disabled masks, production friction kernel
pair checks,36864 boundaries,3 resumed finite updates and8-row replay export.
Two mapping attempts failed safely before deployment (MuJoCo body-name prefix);
final mapping uses the existing contact runtime's unique suffix convention.
Live25580->25590,1,677,131,776samples, optimizer/normalizer restored. Eight live
replays independently reconstruct losses/rewards and carry friction0.5 metadata.
Persistent checkpoint readback verified; watchdog released until stopped.
Forward reward, actor command-jiggle loss200, FAIL500/body-jiggle termination,
physics except the friction rule,55cm/200tick sphere and300sec replays retained.
Source SHA256 1d154067a40448eec0fcaf3de3923fc499030bd1530db6b841714bf37b140b2e.
Helper Labs/RoboticMotionAE/deploy_dead_friction.py; evidence
Saved/MimicKitSlowLoco/dead-friction-half-20261103/. No improvement claim yet.

**Standing rule: disabled-limb friction is half baseline.**
Apply 0.5 to every segment of a disabled arm or leg, across all slow-loco motions
and row types, including vanilla limps. Active segments retain 1.0. A contact
involving two disabled segments is halved once, not quartered. This covers ground
and self contacts; mass, inertia, collisions and motor strength are unchanged.
Per-world material factors follow disabled flags at reset. Friction is scaled
before manifold assembly each substep from freshly rebuilt coefficients.
Preserve the pinned training adapter hook when rebuilding packages; the separate
shared/native lab adapter has diverged and must not be overwritten blindly.

**November 3, 21:40 Warsaw — local bridges revived.**
The slow-loco bridge/dashboard and TensorBoard were absent; existing replayer
8021 remained alive. Restarted observers through deploy_slow_policy.observe()
and the singleton serve_tensorboard.py supervisor. One worker per service;
thread-pool memory limits retained. Bridge download counter advanced
2,750,885 -> 2,754,982 bytes. TB8035 serves the current 18-05-09 run alongside
nine earlier runs; latest scalar sample 1,671,823,360 (training iteration25509).
Replayer8021 serves current capture25504, recorded21:36:43 Warsaw. Both APIs
HTTP200. Remote training untouched. Receipt:
Saved/MimicKitSlowLoco/bridges-revived-20261103.json.

**November 3 direct policy-command anti-jiggle loss — VERIFIED RUNNING.**
User approved a loss on the NN outputs. A deterministic 64-world, 300-tick audit
of checkpoint 24630 confirmed repeated reversals in noise-free motor commands
in all 64 worlds (45 also reached the body-jiggle termination). This is a command
regularizer added directly to the actor objective, not an environment reward cost.

Opt-in agent_config.action_jiggle v1: 13-frame window; at least 3 reversals per
motor, ignoring changes <=0.02 in normalized action units and carrying direction
through brief plateaus. For gated motor samples, penalize squared excess of
abs(mu[t+1]-2*mu[t]+mu[t-1]) above 0.04. Full gradients pass through the current
policy at all three states. Gate construction uses detached noise-free means;
exploration samples are never used in this loss. Windows crossing a done/reset
or rollout-buffer boundary are excluded. Enabled-motor masks and scope limit the
loss to moving crawl with both legs disabled; phase outputs and disabled motors
are excluded. Formula averages over all batch/motor slots, including zero masks.

Coefficient 200: coefficient 1 measured only ~0.1% of actor gradient. At final
coefficient, sampled raw loss .00191946, unweighted gradient norm .01606,
weighted gradient 3.212 versus combined actor gradient 15.8217 (~20%). This is
not a fixed percentage of total reward/loss. No dynamic reward renormalization.
CPU tests: constant/ramp/smooth 0.5Hz and 2Hz strokes/single shock/tiny chatter
have zero loss; 5Hz and alternating commands are detected. Gradient step reduces
the synthetic loss; disabled channels and reset/buffer boundaries are checked.
Final GPU preflight: actual checkpoint 24699, 2048 worlds, 36,864 boundary cases,
3 finite resumed updates, completed 8-row replay export, 244 seconds. Earlier
preflight failures were test-only (frozen parameter in gradient audit, then a
60-frame partial-replay limit); live trainer remained unchanged during testing.

Latest 24718_final saved locally + persistently, SHA256
ff24c011e4a8712797c4218bdb946e972a38717081a2b1b2f6d3ecb5abba2db6.
Resumed on same pod 9snbu59mla2xcd, trainer 14868 / guard 14869, run
20261103_180509_uefn_slowloco_disabled_curriculum_action_jiggle_2048.
Verified 24719 -> 24729, 1,620,705,280 samples, optimizers/normalizer restored,
160 observations/34 motors unchanged. Eight live rows independently reconstruct
reward, MSE, body-jiggle resets and command-jiggle diagnostic values. Live TB
weighted loss .0915779, raw .000457890, detected fraction .2061615. Persistent
checkpoint readback verified; deadline released to until-stopped. These checks
verify implementation and stable updates, not learned removal of vibration.

Forward signed reward maximum 5, existing body-jiggle reset/FAIL500, physics,
55cm pelvis sphere/200-tick recenter and 300-second replay cadence are unchanged.
Replayer records full mean-command traces and displays “Policy command jiggle
(actor loss)” separately from reward. TB run 18-05-09 cards:
policy/action_jiggle_raw, policy/action_jiggle_weighted,
policy/action_jiggle_detected_fraction. No new GPU or local service duplication.
Source archive SHA256 28bb40dd53d83566c9aac18faae9c6becd1949093e6a5578c2c97d2da62b32a5.
Helpers: action_jiggle.py, test_action_jiggle.py, deploy_action_jiggle.py.
Evidence: Saved/MimicKitSlowLoco/action-jiggle-20261103/.
User-requested cleanup completed: latest 24774 downloaded and SHA/ZIP verified
locally (6c10682ac2cc59d9675dd2777e7e059e6b7cc74835d7cded89f3d913e781d2b3).
Deleted 18 intermediate archives from persistent storage and the owned pod,
572,421,181 bytes on each. Finals, latest saves, local pins, rollback 24718_final
and original main 20414_final retained; event/replay history untouched. Old run
20261031_175934_uefn_slowloco_unperturbed_2048 retained entirely because its latest
receipt timed out. Cleanup helper now lists only checkpoint prefixes, parallelizes
independent reads, and uses bounded requests; unverifiable runs are skipped.
Evidence: action-jiggle-20261103/checkpoint-cleanup/{preserved,plan,complete}.json.

**November 3 body-vibration coverage fix — VERIFIED RUNNING.**
The user’s capture 24524, row 0 lasted 122 ticks with the v1 hand-only jiggle
counter at zero throughout. Its final pelvis gap was 0.553415 m, exceeding the
0.55 m sphere; that reset was not caused by jiggle. Pelvis angular cancellation
was 1.08 rad/s with 7 reversals at frame 60 and 2.56 rad/s with 14 at frame 70,
while the hands remained below threshold.

Detector v2 retains the 15-tick window, 30-tick startup grace, 6 consecutive
hits, thresholds, and hand translation checks. It adds world angular reversal
checks for pelvis, torso, head, upper arms, forearms and hands (9 bodies), excluding
passive legs. Scope remains moving crawl with both legs disabled. Rescoring the
same old capture triggers at frame 64 instead of its actual sphere reset at 122;
this is an offline counterfactual, not a claim about a new policy trajectory.
Archived calibration detects 75/80 recent vibrating rows and all 4 known bad
examples, with no detections on 12 normal crawl/idle rollouts, 6 one-leg crawl
rollouts, or 98 reference sequences. Independent NumPy/Torch flags and streaks
match. Smooth gait, constant motion, a single shock and tiny jitter pass;
pelvis-only alternating rotation is detected. Scope and partial resets pass.

Full actual-checkpoint GPU preflight passed 2048 worlds, 36,864 boundary cases
and 3 finite resumed updates. Latest checkpoint 24567_final was saved locally
and persistently, SHA256 705dc53315bd2e5feb41039ea35e10dedeb5272bf0c84fb1144907b5632069df.
Resumed on retained pod 9snbu59mla2xcd, trainer 13212 / exit guard 13213, run
20261103_171810_uefn_slowloco_disabled_curriculum_body_jiggle_termination_2048.
Verified progress 24568 -> 24578, reaching 1,610,809,344 samples; actor/critic
optimizers and normalizer restored, 160 observations unchanged. All 8 first live
replay rows independently reconstruct MSE, signed forward reward, temporal jiggle
flags and terminal reward. All 8 terminate exactly on their first sustained
jiggle flag (frames 35, 88, 46, 43, 35, 90, 78, 35), charging FAIL500 once.
This verifies detection, not learned suppression; the resumed policy still jiggles.

Signed forward reward maximum 5 remains enabled; jiggle reward deduction stays
zero. Physics, strength, observations, 55 cm pelvis sphere, 200-tick recenter and
300-second replay cadence are unchanged. Persistent checkpoint 24568 readback
SHA256 e1ecfd636ea067bdcb2c5cd60ba193d2e92350e848b98304414dcd0b2164a157 verified;
setup deadline released to until-stopped. Local replayer serves capture 24568
with “Body jiggle reset counter / 6” overlay; TB run 17-18-10 publishes forward
reward and jiggle termination cards. Source archive SHA256
be1982b849b08f95377c7f43d66a9e9e1b0def4a4c8107551b145f6b4a288e86.
Helper: Labs/RoboticMotionAE/deploy_body_jiggle_termination.py. Evidence and plot:
Saved/MimicKitSlowLoco/body-jiggle-audit-20261103/. No GPU allocation or damping.

**November 3 local telemetry memory fix.** Local bridge/dashboard/TensorBoard and
replayer entrypoints limit numerical thread pools to1 before imports. Measured
live private commit across four workers fell~2250->390MB after restart and replay
requests; physical residency is a different metric. Same10 TensorBoard directories,
current jiggle card, history and live downloads verified. Singleton observer refresh
only; cloud training/main-chat preflight unchanged. Keep these local limits when
relaunching observers. Evidence: Saved/MimicKitTraining/local-memory-20261103/;
details in TrainingJournal.md. No training-package physics/settings changes.

**November 3 sustained jiggle termination + restored forward reward - VERIFIED RUNNING.**
User cancelled upper-body damping before deployment. The08:12:46 trainer
was left unchanged during tests; local physics restored to its exact inventory. Damping receipts
are explicitly cancelled under upperbody-damping-20261103; do not deploy that helper.
Replacement candidate applies only to moving crawl with both legs disabled.15-tick
hand window, cancellation >.08m/s or .8rad/s AND >=4 reversals around the window
mean (cosine<-.25; residual gates .04m/s/.4rad/s); require6 consecutive detections
after30-tick startup grace. Reuse FAIL500 exactly once, even with simultaneous sphere
failure. Later user instruction: remove the jiggle reward cost and restore the previous
signed displacement forward reward (maximum5, no lower clipping). Physics unchanged.
Full termination preflight passed2048 worlds,36864 boundaries,3 finite updates and
8 independent replay reconstructions; focused restored-reward preflight also passed
2048 worlds/36864 boundaries/3 resumed finite updates from24478. New run
20261103_164528_uefn_slowloco_disabled_curriculum_jiggle_termination_2048,
same pod9snbu59mla2xcd, trainer11973/guard11974, from latest24493_final.
Checkpoint downloaded locally and persistent SHA338ebe6f92ef5e97e13b2a84372b06e0c59d37cb60b43fdf3f54bdfaccf5b53a
verified. Advancing24494->24504,1,605,959,680samples, optimizer/normalizer restored,
160inputs unchanged. Eight live replay rewards independently reconstructed: jiggle
cost exactly0, signed forward reward enabled,500 failure charged exactly once;
3/8 end exactly on jiggle detector frame,2/8 reach300ticks. Persistent checkpoint
readback SHA verified; setup deadline released to until-stopped. Replay remains
every300seconds. TB16-45-28 publishes forward/jiggle-termination diagnostic tags;
8021 replayer publishes24494 with Jiggle reset counter/TERMINATED overlay.
Physics source unchanged, no damping/new GPU. Final source archive SHA
852ef899c3c208839981d59de1da0670875070cc04869d916629961481c57b3f.
Offline:68/80 recent
rows detected,0/12 normal crawl/idle,0/6 one-leg crawl,0/98 references;4/4 known
vibration clips detected. Latest held-out capture24459 detected6/8. Independent
NumPy/Torch flags/streaks match; normal smooth gait/constant motion/single impact/
tiny jitter pass, repeated chatter fails, partial resets and disabled scope pass.
Helper deploy_jiggle_termination.py; receipts jiggle-termination-20261103.

**November 3 jiggle coefficient9 / episode-scale500 — VERIFIED RUNNING.**
User clarified matching the500-point termination cost over a full episode.
Capture22905 has7 complete300tick rows. Old coefficient2 scores107–208 total;
new coefficient9 (4.5x), same5/tick cap, scores mean502.37/median505.01 on exactly
those rows. Fixed coefficient, not an adaptive normalization forcing cost500.
Tolerances,6frame window, physics, losses, termination, sphere and cadence unchanged.
Recorded reference still0; CPU independent reconstruction/isometry/reset checks pass.
Only pipeline/crawl_jiggle.py differs from previous source inventory.
Resumed retained pod9snbu59mla2xcd from latest22938_final (local/persistent SHA
148985e78765711b00f0f9b57dc59db57cc76fdfdcbdd397bfab43bccf7bc267).
Run20261103_081246_uefn_slowloco_disabled_curriculum_crawl_jiggle_2048,
trainer10346/guard10347; optimizer/normalizer restored. Verified22939->22949,
1,504,051,200samples;8 live replay rewards independently reconstructed with
coefficient9, zero forward bonus, unchanged500 failure penalty/.55m/200ticks.
New persistent checkpoint readback SHA verified; setup deadline released to
until-stopped. TB08-12-46 has fresh penalty1.535/tick, replayer publishes22939.
Helper deploy_crawl_jiggle_episode500.py; receipts
Saved/MimicKitSlowLoco/crawl-jiggle-episode500-20261103/.

**November 3 crawl forward bonus replaced with temporal jiggle cost — VERIFIED RUNNING.**
User explicitly requested LATEST, superseding the earlier21779 restart preference.
Retained pod9snbu59mla2xcd; current continuation
20261103_074137_uefn_slowloco_disabled_curriculum_crawl_jiggle_2048,
trainer9488/exitguard9489, from checkpoint22802_final (locally downloaded and
persistent SHA80049e3abd635959a65017bff71f45111bbb654443636168c3b92da6208cec6a).
Same2048 all-two-passive-leg crawl worlds, physics/motors, .55m pelvis sphere,
200tick recenter, -500 failure,160observations and300s replay cadence.
Forward bonus now disabled. Six-frame/0.2s per-hand velocity cancellation on
pelvis-relative translation in world axes and world angular motion; tolerances
.05m/s and1rad/s, scales .1m/s and2rad/s, coefficient2, maximum5/tick.
Cost is subtracted AFTER exp(-pose_loss), first5samples warm up, reset clears
only the relevant world's history. Zero for constant-direction movement.
Four recorded bad clips:3.62–4.19 mean cost at150–230; recorded references0;
full twice-looped reference also0. Independent CPU NumPy/Torch agrees within
1.26e-5; partial resets and rigid world translation/yaw checks passed.
2048-world stress preflight at preliminary cap10 passed36864 boundaries, dead
motor/loss exclusions,3 finite resumed updates and8 independent replay checks.
Final cap reduced to5: worst discounted nonterminal cost <=500 at gamma .99;
final CPU checks passed. Actual cap5 continuation advanced22803->22813 with
finite updates and8 independently reconstructed replay rewards; forward bonus0.
Persistent checkpoint readback SHA verified, both guards alive, deadline released
to until-stopped. TB card receives fresh4.479 at1,495,138,304samples. Local8021
replayer publishes22803 with penalty/total reward overlay; local bridge converter
and dashboard mapping updated, singleton observers refreshed without duplicates.
TB reward/crawl_jiggle_penalty plus linear/angular cancellation metrics; replayer
shows per-frame Hand jiggle penalty (6 frames) and Total reward.
Source module Labs/RoboticMotionAE/crawl_jiggle.py; deploy helper
Labs/RoboticMotionAE/deploy_crawl_jiggle.py; receipts
Saved/MimicKitSlowLoco/crawl-jiggle-20261103/.

**November 3 passive wrist damping probe — not deployed.**
Frozen checkpoint22054 in installed Jolt, four matched frame150 starts,80ticks.
Separate passive wrist/forearm relative-angular damper, no stiffness, same50Nm
wrist motors; analytical two-inertia decay verified to1.12e-8rad/s.
Row0 damping0/1/5/20/100Nm*s/rad: forward50.34/50.59/49.47/46.06/54.65cm.
Damping20 lowers wrist angular-velocity-change RMS57–66% across four starts but
retains88–92% of travel. Damping100 lowers it79% on row0, while hand translation
reversal persists and travel rises9%. This is NOT a solution to vibration-driven
travel: shoulder/arm motion still moves the hands. No claim about retraining.
No live source/settings/trainer changes or GPU allocation. Eleven bounded local
single-threaded probes exited. Repro scripts: test_crawl_wrist_damping.py and
summarize_crawl_wrist_damping.py; receipts/plot/traces:
Saved/MimicKitSlowLoco/wrist-damping-20261103/.

**November 3 TensorBoard revived:** Local8035 server and slow-loco bridge/publisher
were absent; restarted through the existing singleton-managed helpers. Latest ten
historical comparisons retained; current03-55-35 run displays fresh data through
1,473,314,816samples (update22480). Remote reports training; no trainer/pod change.
Replayer8021 also restored (single server PID56124); API shows rollout22488,
captured06:35:44 Warsaw. Existing bridge supplies new rollouts.

**November 3 Jolt crawl transfer probe and overlay (diagnostic only).**
Frozen checkpoint22054 was evaluated in an isolated executable linked to the
installed project Jolt DLL (SHA e1081ed46c3ccdd398685ffa8a2909866870c734f0e9b7e538df2e71576668ac).
Current crawl geometry/mass/inertia/limits/gains/caps; both leg motors OFF,
240Hz physics/30Hz policy,100 velocity/20 position iterations. Four recorded
starts at frame1 and150, with/without speculative-contact gap filtering,16tests.
Observed-state inference phase reconstruction max error9.14e-5. Frame0 excluded:
its stored first phase prediction did not reconstruct, unlike all checked later
frames. No claim of full gameplay equivalence or episode success; tests do not reset.
Vibration propulsion DOES reproduce in Jolt: row0 warm start150, next80ticks,
standard contacts50.3cm forward versus recorded58.4cm, hand velocity reversals
45/62 versus62/57. Other three warm starts advance45.0/48.6/47.1cm with standard
contacts. Earlier-state full trajectories differ more; not trajectory parity.
No motor activation filter, physics fix, retraining, restart or extra GPU applied.
All16 local bounded-size diagnostics completed; Unreal/editor/gameplay untouched.
Interactive overlay: http://127.0.0.1:8863/Saved/MimicKitSlowLoco/jolt-vibration-20261103/
Orange Jolt/cyan recorded training; same coordinates and common30Hz timeline,
no frame-by-frame realignment/interpolation. Default150–230 loop, Space pause,
case/start/contact selection; reused existing8863server, no new background server.
Scripts: Labs/RoboticMotionAE/build_crawl_jolt_audit.py and test_crawl_jolt_audit.py.
Data/results/build hashes: Saved/MimicKitSlowLoco/jolt-vibration-20261103/.

**November 3 upstream physics audit — INVESTIGATION ONLY, NOT DEPLOYED.**
Instrumented the custom contact/motor solve and post-solve position projections in
an isolated remote source copy; production source hashes remained unchanged.
Checkpoint22054, eight exact recorded starts,300 control ticks at30Hz; compared
240/480/960Hz physics with fixed commands and then actual policy feedback. All
bounded diagnostic processes exited. Production status advanced22240->22280.
The valid row0 feedback window150–230 survives at every timestep: forward travel
56.89/58.79/58.36cm; signed position-projection contribution -0.001/-0.066/-0.180cm.
At240Hz motors supplied350.75J and contact impulses dissipated308.13J. These are
velocity-solve impulse-work measurements, NOT a full potential-energy audit.
Hand geometric-contact transitions60/59 at240Hz and84/78 at960Hz; cancellation
remains substantial. Finer physics did not eliminate vibration propulsion.
Evidence supports motor-powered oscillatory locomotion, not forward teleportation
from position projection or net energy creation by the contact velocity solve.
Hard contacts already use zero bounce; ordinary MuJoCo solref/solimp tuning does
not replace this custom solver. Current bounded velocity motors have no finite
activation/torque-rise state; passive joint damping and added armature are zero.
Recommended next physical candidate: finite motor torque buildup/reversal while
retaining sustained torque, integrated into the coupled motor/contact solve and
mirrored in deployment physics. NOT implemented or demonstrated effective yet.
Prior command-filter tests suppressed chatter but lost progress; do not claim
successful retraining from these frozen-policy probes. No training/reward changes,
no restart, no extra GPU allocated. Any eventual approved restart stays21779_final.
Receipts: Saved/MimicKitSlowLoco/physics-origin-20261103/summary.json; policy240,
policy480,policy960 traces/results. Fixed-command long trajectories diverge and
some diagnostics continue after failure; do not conflate these with valid episodes.

**November 3 arm bandwidth trial — TESTED, NOT DEPLOYED.**
User requested a physical arm-response constraint, then explicitly required testing
that it prevents bad motion before deployment. Restart source is now21779_final,
the initialization of the current pelvis55 run, NOT its latest checkpoint.
That locally preserved checkpoint SHA was reverified; see authorized-restart.json.
Ran three bounded scratch-only paired physics tests on the retained GPU, each16
worlds/eight identical recorded starts, deterministic checkpoint22054,300ticks.
Production trainer remained running; no optimizer updates or live source changes.
80ms smoothing plus reference-derived command slew limits reduced translation/
rotation cancellation76%/89% over common pre-failure windows in baseline-success
rows, but0/8 candidate episodes reached300ticks (baseline5/8). 35ms:0/8; slew-only:
1/8, with substantial residual chatter. Reference-only slew pass is not proof of
closed-loop capability. These frozen-policy tests cannot establish retraining's
outcome, but do not satisfy the requested demonstrated prevention, so NO controller,
observation, reward or termination changes deployed and NO restart performed.
All three diagnostic processes exited; current pelvis55 trainer still running.
Receipts/plots: Saved/MimicKitSlowLoco/arm-bandwidth-20261103/summary.json.

**November 3 hand vibration investigation — OFFLINE ONLY, NOT DEPLOYED.**
Exact screenshot matched checkpoint22054, row0 of the current pelvis55 run.
Frames150–230: hand velocity direction reverses62/57 times versus0/0 for the
recorded reference; acceleration RMS is14.95/13.77m/s² versus2.23/2.20.
Hand speed itself is lower than reference, so increasing velocity magnitude
penalties alone would not specifically distinguish the chatter. Replay noise is0.
At frame187, pose reward is approximately2.8e-8 while the additive forward reward
is3.545: the exp(-pose loss) component is effectively saturated. Additional MSE
inside that exponential would have negligible influence at this rollout state.
Offline candidate: six-tick per-hand translation/angular velocity cancellation
(mean speed minus magnitude of mean velocity), with recorded-reference tolerances,
subtracted directly from final reward. A fixed coefficient gives1.65–2.00 mean
cost on four complete recorded rows while leaving their forward-minus-cost means
positive; sampled reference cost is0 by construction. This is detection/calibration,
not evidence of improved learning. No physics/contact-solver fault established:
30Hz replay lacks substep forces/actions. No GPU, training, reward, termination or
physics settings changed. Artifacts: Saved/MimicKitSlowLoco/hand-vibration-audit-20261103/.

**November 3 crawl pelvis sphere — 55 CM / 200 TICKS, VERIFIED RUNNING.**
Confirmed old80cm was the actual live radius. User requested55cm and latest resume.
Only perturbed moving-crawl pelvis radius changed: both physical failure check and
recorded target-sphere radius now0.55m. Other limb/motion radii,200tick crawl recenter,
reward/physics/curriculum and five-minute replay cadence are unchanged. Prepared
configs are byte-unchanged; source delta is only pipeline/slow_loco_disabled.py.
Resumed21779_final, downloaded locally and persistent SHA verified:
6f9a073b8afc3c77054d7aa3b30252a44e9d610a27508f09a9fda7e611bb413f.
Run `20261103_035535_uefn_slowloco_disabled_curriculum_crawl_pelvis55_2048`; same pod9snbu59mla2xcd, trainer6529/guard6530.
CPU checks cover55cm sphere boundary,200/400tick recenters and unaffected row/limb
radii. Optimizer/normalizer restored;21780->21790 /1428094976samples verified.
Eight independent replay loss reconstructions pass; all8 local replayer rows and
sphere points report55cm and200ticks. TB8035/replayer8021 HTTP200. Persistent backup
readback verified; setup guards released to until-stopped. Protected main20414 intact.
Receipts: Saved/MimicKitSlowLoco/pelvis55-20261103/.


**November 3 crawl pelvis sphere — 200 TICKS, VERIFIED RUNNING.**
User requested200 instead of the remembered150; live source/replay was actually130.
Crawl/crawl_idle recenter interval is now200ticks (6.667seconds at30Hz). Current
isolated run still uses only two-dead-leg crawl rows. Radius stays80cm for these
perturbed rows; other motion intervals, physics, rewards and curriculum are unchanged.
Resumed latest21435_final, saved locally and independently SHA-verified from persistent
storage (2540bb698a82f672e429ff4d2bb4a0d4fafc30b82cec3b94cf1e7fd78d78ba8a). Run `20261103_023246_uefn_slowloco_disabled_curriculum_crawl_pelvis200_2048` on retained pod9snbu59mla2xcd, trainer5605/guard5606.
Only pipeline/slow_loco_env.py changed (interval and descriptive metadata); prepared
configs match checkpoint exactly. CPU boundary checks cover400ticks, no early reset,
200/400 recenters, preserved70tick other-motion behavior and80cm radius boundary.
Restored optimizer/normalizer;21436->21446 /1405550592samples verified. Eight replay
rows independently reconstructed and local replayer metadata all report200ticks.
Persistent backup readback passed; both setup deadlines released to until-stopped.
Five-minute replay cadence retained; TB8035 and replayer8021 HTTP200. Exactly one
current bridge/dashboard via the fixed observer lifecycle. Main20414 remains protected.
Receipts: Saved/MimicKitSlowLoco/pelvis200-20261103/.


**November 3 local service memory cleanup — VERIFIED.**
39 slow-loco dashboard publishers had accumulated across resumptions since October31;
observe() launched a new publisher without retiring earlier ones. Each retained roughly
400MiB and reread historical events. Removed38 obsolete workers plus their38 Windows
venv launchers (15.22GiB private committed allocations), one obsolete reconnecting bridge
(~0.74GiB), and the October31 pose editor (~1.52GiB; saved poses retained).
Current dashboard/bridge and TensorBoard were replaced locally with lifecycle fixes;
remote trainer/pod/settings/checkpoints and game servers/billing guards were untouched.
observe() now serializes launches and identity-checks scoped observer process trees
before replacement. OS-released service locks reject duplicate workers (including
manual launches). Publishers exit when sources finish or their owner run is superseded;
bridges exit on supersession and close SSH children. TensorBoard replacement kills its
whole owned process tree, not just the Windows Python launcher. Pose editor now exits
after30minutes without requests; start it on demand when authoring again.
Three subprocess/lifecycle tests passed, including grandchild shutdown and crash-release
of locks. Two successive observe() calls left exactly one bridge and one publisher.
Live bridge/dashboard/TB ownership locks verified. TB8035 and replayer8021 HTTP200;
all10 previously visible TB runs still listed. Latest received training status21197 /
1389232128samples is training; bridge transfer timestamp is fresh. No GPU restart.
Receipts: Saved/MimicKitSlowLoco/dashboard-cleanup-20261103/.


**Journal routing:** [Standalone training journal](../../TrainingJournal.md) owns training status and experiment history.
Do not append training-only updates to ProjectJournal.md; reserve it for actual
Unreal integration and native compatibility notes. This topic keeps technical details.

**November 2 user cancellation — PRE-GRIP CRAWL RESTORED AND VERIFIED RUNNING.**
User cancelled grip3/elbow150 branch and requested the previous learner back,
keeping five-minute replays. Restore PRE-CHANGE20726_final (not new branch weights),
SHA49dd4d875e5c9b17dee0d0a4b233c8ade3a232fc9b19012b8ea4f6b3d45165b9.
Run `20261102_232738_uefn_slowloco_disabled_curriculum_crawl_signed5_restored_2048`, trainer4979/guard4980.
Retained same pod9snbu59mla2xcd ($0.28/hour). Source is byte-identical to previous220414
package except train.py/base_agent.py replay cadence hooks. All three configs
match20726 checkpoint exactly. Ground friction returns to1; elbows return to70Nm.
No new GPU/sweeps. Main20414 remains protected and paused. Source inventory,
exact previous engine/env/agent configs,160obs,restored optimizers/normalizer,
8 independent replay reconstructions and persistent checkpoint SHA readback pass.
20727->20737 verified; both setup controls released to until-stopped, then live
training log advances to20741/1359347712samples. TB8035 run23-27-38 and replayer8021
serve the restored run. Five-minute output flag verified; cadence implementation
is unchanged from the preceding observed5m13s interval. Cancelled branch final
checkpoint retained persistently for possible later use; none of its weights used.
Source SHAfcd3f0fc8369004cf633677d2d672703e2d6addab459ffa6e7f73006c5123650.
Receipts: Saved/MimicKitSlowLoco/restore-crawl-baseline-20261102/.

**November 2 grip/elbow experiment — CANCELLED BY USER; historical verification below.**
Run `20261102_231246_uefn_slowloco_disabled_curriculum_crawl_grip3_elbow150_2048` on retained RTX4000Ada
pod9snbu59mla2xcd ($0.28/hour), trainer4313/guard4314.
Resumed latest20726_final; actor/critic optimizer/normalizer continuation checked
by training resume path. Advancing20727->20737/1359085568samples verified.
Hands AND forearms ground friction x3; elbows70->150Nm. Shoulders, wrists,
dead-limb mass, reward, curriculum and all other settings unchanged.
Output evaluation/checkpoint cadence now300wall-clock seconds at PPO boundaries;
publication includes evaluation time and bridge polling. This is not an iteration
approximation. Source SHAd2fa7aeeefd8cf49dfb0f89e1f6828a6797e28701c76c3e2a91709cec7d85b3d.
32-world/32tick actual-checkpoint smoke checked finite simulation, exact solver
manifold friction on all four intended bodies, unchanged self/other contacts and
150Nm elbow envelopes. No sweeps/new GPUs. First launch failed a strict resume
config comparison before updates; bounded setup guard retained GPU. Added exact
named x3 allowance and relaunched from same20726. Source inventory,160-observation model, optimizer/normalizer restore,8 independent
replay loss reconstructions and persistent checkpoint SHA readback all pass.
Both setup controls released to until-stopped. Post-release20737->20747 and
1359740928samples verified. Replay20727->20743 generated312.892seconds apart
(5m13s); both captures are served by replayer8021. TB8035 lists23-12-46 run.
Only the retained GPU is used; no improvement in learned crawling is claimed.
Latest20726 downloaded and SHA verified: 49dd4d875e5c9b17dee0d0a4b233c8ade3a232fc9b19012b8ea4f6b3d45165b9.
Main20414 remains separately preserved and SHA reverified; never resume main
from experimental weights. Receipts: Saved/MimicKitSlowLoco/grip3-elbow150-20261102/.

**November 2 crawl traction investigation — EXTRA TRIALS CANCELLED; ANALYSIS ONLY.**
User explicitly rejected further trial launches and requested simple mechanical
analysis. Sent SIGTERM ONLY to owned queue2839/2840 and trial2841/2842;
confirmed nvidia-smi shows ONLY original trainer1276, live20576/1348534272samples.
No new GPU allocated; no production physics/reward/source/settings changed.
Do not restart this queue or launch further tests without a new user instruction.
Remote cancelled.json and local cancelled-and-analysis.json supersede any old
adaptation-current.json/runner instructions. The four-way adaptation comparison
was NOT completed; do not claim adapted-policy results or a winning setup.

Recorded evidence retained under Saved/MimicKitSlowLoco/crawl-traction-20261102
and the same directory on /workspace/mimickit_trial. Pinned20426 replay includes
row3/227ticks. Initial positions match exactly; matched rerun trajectories are
not bit-identical (up to2.8cm first30frames). Frozen-policy probes measure slip
response ONLY, not learnability; fixed IK pulls are short strokes, not gait proof.

Simple conservative static estimate for matched row3, frames150–210:
hands support262.8N (right236.7,left26.1), legs304.2N, forearms200.3N.
If palms anchor while other surfaces resist at mu1, break-even palm mu is
(304.2+200.3)/262.8=1.92. Using proportional hand load allocation and frame169
joint lever arms plus arm gravity gives right elbow~97Nm versus current70Nm;
shoulder local components peak~65Nm versus100Nm, wrist~26Nm versus50Nm.
This excludes helpful forearm contact moments and is NOT an exact capacity
certificate or globally minimal modification. Targeted candidate, NOT DEPLOYED:
palm friction2.0, elbow cap100Nm, keep dead-leg mass, shoulder100 and wrist50.
A20% dead-leg mass reduction removes only4.9kg/~48N; it is less targeted than
fixing palm grip and the loaded elbow. Recommendation must not be described as
proven to generate sustained crawling. Helpers and raw probe traces retained.

**November 2 isolated crawl experiment — resumed after setup-deadline shutdown.**
Current run `20261102_220414_uefn_slowloco_disabled_curriculum_crawl_only_signed5_2048`
on the SAME Secure RTX4000Ada pod `9snbu59mla2xcd` at $0.28/hour;
trainer1276/exitguard1277, bridge58068/dashboard29400. No extra GPU allocated.
Resumed experiment20425_final with actor/critic optimizers and160-observation
normalizer restored. Exact experimental source/settings retained: all2048 rows
moving crawl, both legs passive/code12, both arms enabled,50% target playback;
signed displacement bonus5 outside exp(-loss), failure penalty500, pelvis sphere
0.8m resetting130ticks. Source SHA
f81a30bc10656a74b80da46222455a847decddc70902b4d85254b7973f6c0299.

The previous21-39-50 run stopped gracefully at20425 because the bounded setup
deadline reached its165-second shutdown reserve before verification released it.
It was NOT a storage-full crash. The old verification accepted a process during
final shutdown; that did not prove continuing training. The pod remained paid.
Verification now rejects finished.json and final-checkpoint backup receipts;
require advancing statuses AFTER releasing both setup controls, not just before.
Post-release advancing status verified at20516 /1344602112samples.
Current source hashes,160obs,8 independent replay loss reconstructions and new
persistent checkpoint SHA readback pass. Both controls now until-stopped.
TB8035 run22-04-14 has the four crawl reward/speed cards; replayer8021 serves8 rows.
This proves run health, NOT learned improvement.

MAIN REMAINS PAUSED at20414. Resume the main run later from MAIN20414 and archived
main-source.zip/configs, NEVER experimental weights. Main checkpoint SHA
cd4e1569da103b8ab07e2cbd265e0b21415e41e138e0402b984a74837320f99f.
Main source SHA5f07346b7b396477ff80d2b312732caf7a2a5e5551f111110248310022429032.
Main20414 was downloaded AGAIN and hash/ZIP verified before deleting anything;
it exists both in preserved-latest and crawl-relaunch-20261102 locally.
Experiment20425_final also downloaded/hash/ZIP verified, SHA
b2ac50804f77cc9422908145543cdca3648382fb9192d963f48713858d2d77dd.
Removed82 intermediate persistent checkpoint archives,2775938677bytes(2.59GiB),
and2 matching local pod intermediates(61504182bytes). Retained all final archives,
each run's latest_verified checkpoint, local preserved pins, MAIN20414 and
experiment20425_final; verified protected keys still exist after cleanup.
Receipts/downloads: Saved/MimicKitSlowLoco/crawl-relaunch-20261102/.
Main rollback package: Saved/MimicKitSlowLoco/crawl-only-experiment-20261102/.
Preserve stopped5xs589fdlcb7nr andvpv6saq7zyooak/disks; no restart alongside this pod.
Capacity automation was deleted after the earlier launch; no allocation required.

**November 2 crawl bonus follow-up — stall persists; ANALYSIS ONLY.**
User still sees no attempt to crawl with two passive legs. After~240updates/
49minutes, training speed remains~3–4cm/s; bonus is active, not a delivery bug.
Pinned20240 (973e279b62430cee495f2a52cde510f168e73d2143845ee7697b2a6a72ceb639).
Actual latest replay:119ticks then FAIL;17.7cm forward total, pelvis45.2->15.3cm.
After first30ticks, forward speed1.38cm/s; first-second displacement includes
inherited initial velocity and falling, not proof of a deliberate pulling stroke.
Read-only full2048-world/128tick PPO probe, normal mix/noise/reset path, no updates:
77worlds (3.76%) eligible. At age>=30, both-passive mean2.16cm/s, pelvis22.3cm,
upper command RMS1.035rad/s vs2.17–2.19 for one-leg cases moving27.3–29.2cm/s.
Bonus mean0.472 vs pose0.000240, but bonus zero for51% of late transitions.
Bonus reaches actual PPO TD-lambda targets. Its within-buffer contribution std
~6–8, vs direct failure-cost contribution std51/77/149 in the three batches
with failures (critic also carries future-failure estimates). This is signal
scale evidence, not a causal proof that reducing the failure penalty solves it.
Actual torque samples do not show continuously maxed shoulders; only final
physics substep sampled, so do not infer sustained mechanical capability.
Reward-design defect: clipping at zero rewards forward/back rocking with no
net travel (equal +/-10cm/s earns mean1.069). This loophole is mathematical;
the observed stall is not proven to be deliberate exploitation of it.
Recommended next controlled test, NOT deployed: signed net forward progress
(backward displacement cancels forward credit; cap positive overspeed), focused
two-passive-leg training from verified stable starts, then restore random dead
poses. Do not promise another weight increase alone will discover a new gait.
Current run unchanged and advancing20310; all412 source hashes unchanged;
probe exited. Evidence Saved/MimicKitSlowLoco/crawl-forward-followup-20261102/
{analysis.json,trace.npz,ppo-signal.json,training-trends.json,latest-crawl.png,
final-verification.json}; helper probe_crawl_forward_signal.py.

**November 2 crawl forward reward — VERIFIED RUNNING.**
User approved a separate movement reward that outweighs pose imitation, then
resume latest. Only moving `crawl`, perturbed and code12 (both legs passive):
add `5*clamp(1 - ||pelvis_origin_velocity_xy-target_xy||/||target_xy||,0,1)`
outside the existing exp(-loss). Target is precomputed full-cycle root travel
divided by duration, scaled by row rate (50%:23.376cm/s forward). Zero at rest,
5 at target, decreases for overspeed/lateral velocity; no vertical reward.
Original pose reward remains0..1; failure penalty500 and all other rows/settings
unchanged. New diagnostics reward/crawl_forward,crawl_pose,
crawl_forward_speed_m_s,crawl_target_speed_m_s average only eligible rows.
Replay stores per-row specification and reconstructed frame bonus; viewer shows
the separate bonus and exact total reward. Independent replay checker verifies it.
Source/helper: slow_loco_disabled.py, deploy_crawl_forward.py; receipts in
Saved/MimicKitSlowLoco/crawl-forward-deploy-20261102/. Full2048 preflight uses
checkpoint19986:36,864 boundaries, three finite PPO updates and33 independently
reconstructed replays passed. Latest20039_final preserved locally and persistent
with matching SHA, then SAME retained podvpv6saq7zyooak resumed into
20261102_192728_uefn_slowloco_disabled_curriculum_crawl_forward5_2048.
Trainer20260/guard20261; bridge55172/dashboard62772. Live20040->20050,
1314062336samples verified; actor/critic optimizers and normalizer restored,
160 observations retained, full production source hash matches. Independent33
live replay reconstructions pass; exactly one eligible replay row, bonus up to
3.501; other32 rows zero bonus. Persistent checkpoint readback SHA passed,
until-stopped released. TB8035 serves all four new reward cards for19-27-28.
Initial diagnostic mean bonus0.6166 versus pose0.0641, not evidence of learned
improvement. Source SHA5f07346b7b396477ff80d2b312732caf7a2a5e5551f111110248310022429032.
Receipt deployment-verified.json and bonus-live-verified.json in the directory above.
Original20039_final SHA e2b58bfe83ae77792f4ad54fee2467559ca380fc3dd2d8218e9a24c2a7e9296d.

**November 2 two-passive-leg crawl stall audit — ANALYSIS ONLY.**
Pinned actual checkpoint19886 (SHA aa06a9f844cca00d0daa4b14d62450b0d0868ffd967cc80f56b294f52aea6c28).
96 isolated GPU worlds,32 per leg mask,256 ticks with actual training noise,
random disabled-init bank and resets; no optimizer/normalizer updates.
One-right/one-left/both legs disabled mean forward speed28.48/30.47/3.84cm/s;
targets42.15/42.01/23.38cm/s. Both-passive pose position+rotation contributes
97.6% of mean loss. Dense reward is exp(-summed loss), median2.09e-6;
81.3% of transitions below0.001. Algebraically correcting uniform translation
velocity gives median absolute reward gain9.72e-8 (not a physical intervention).
COM full-cycle band accepts forward2.45–38.95cm/s for both passive; standing
still costs only0.000203 in this term. Body position targets follow actual
pelvis XY, so they do not provide dense world-progress correction.
80cm/130tick pelvis sphere admits approximately4.4–6.0cm/s constant forward
motion depending phase (assuming correct reference height/no lateral error),
far below23.38cm/s target. Of57 observed both-passive failures,53 hit pelvis;
two each hit hands. Counts are events with censored episodes, not failure rates.
Latest actual replay19886 differs: both-passive terminates57ticks/1.9s at right
hand54.39cm>54cm, pelvis still50.4cm<80cm; only4.97cm forward travel.
Failure penalty500/zero bootstrap confirmed; critic median value-261.6 for
both-passive, so punishment is present and represented. Arms receive nonzero
commands (~1.18rad/s RMS), correct enabled flags; passive legs zero torque,
excluded MSE/spheres;50% reference phase advances. No accidental arm disabling.
Secondary observability issue: actor/critic lack world-target lag/window age;
shifting scratch sphere target2m changes failure predicate but obs by0.0.
Do not add timing context automatically: user previously opposed it.
Recommended isolated next experiment, NOT deployed: separate dense forward
speed/progress reward for two-passive-leg moving crawl, outside the exponential
pose reward, retaining a bounded imitation component and existing failure cost.
Evidence establishes signal imbalance, not that this change will learn a gait
or that current torque suffices for sustained crawling. Do not increase caps or
failure cost on this evidence alone. Current run/source/settings unchanged;
412 production hashes match, training19986/1309868032samples, no audit processes.
Evidence Saved/MimicKitSlowLoco/crawl-stall-audit-20261102/{analysis.json,
signal-comparison.png,rollout.npz,ppo.json,final-verification.json}; helpers
audit_crawl_stall_remote.py and summarize_crawl_stall.py. Existing capacity
audit below remains limited to a short arm-driven stroke, not sustained gait.

**November 2 upper-body capacity audit — ANALYSIS ONLY, training unchanged.**
User asked whether moving crawl can propel itself with both legs passive.
Pinned checkpoint18486; isolated scratch source on the retained GPU, no new GPU.
Actual mass78.255kg, passive legs24.476kg; shoulder100Nm/axis, elbow70Nm,
wrist50Nm/axis, torso200Nm/axis. Existing head-height strength blend changes legs,
not these upper-body caps. All14 passive leg DOFs verified zero torque.
128 matched authored-start12s tests (policy1/2/4x caps, independent reference
servos, hold/off/powered-leg controls) did not establish sustained legless crawl.
This is not evidence of mechanical impossibility: even the generic powered-leg
reference servo failed. Random-passive follow-up hit the bounded900s audit timer
before output; no result is claimed for that campaign.
Independent64-world2.5s arm-pull tests and64-world selective-cap tests record
actual240Hz motor/ground impulses. Example at reference phase3/8: current caps
move COM17.15cm and pelvis24.61cm, with minimum pelvis35.8cm/head38.1cm and no
pelvis/torso/head floor contact. No initial velocity, external force or leg torque.
Same controller/target with shoulders2x gives COM17.73cm (only0.58cm improvement).
Whole upper body2x instead loses balance. This is a short-stroke capacity witness,
NOT proof of a repeatable gait, arbitrary random-leg recovery, or the23.4cm/s
reference-speed requirement. Starts vary strongly; repeated larger pulls can
tip sideways. More torque without retuning is not a trained-policy comparison.
Static holds carry269–323N on arms versus445–499N on passive legs. Equal friction
and rear-biased support make load transfer/hand placement strong suspects;
torque-only explanation is unsupported. One shoulder does reach its100Nm cap
during the selected stroke, so do not claim unlimited reserve or no saturation.
Stock ground sensor exposes normals only here; audit reconstructs ground-only
normal AND manifold tangential impulses (not self-contact). Selected force
integration agrees with measured horizontal COM displacement within~6mm.
Evidence Saved/MimicKitSlowLoco/crawl-capacity-20261102/analysis.json and
capacity-comparison.png; all selective starts retained, not only the example.
Helpers audit_crawl_capacity_remote.py, probe_crawl_pull_remote.py,
probe_crawl_selective_remote.py, summarize_crawl_capacity.py. All probe processes
exited.412 production file hashes unchanged; main2048 trainer advanced to19816,
1298726912samples. No live source/config/gain/reward/motion/deployment edits.

**November 2 moving-crawl legs-only — VERIFIED RUNNING.**
Moving crawl (`crawl`, not `crawl_idle`) now always has both arms enabled.
Perturbed choices: right or left leg disabled (uniform selection,90% reference
speed), or both legs disabled (50%). No three-disabled moving-crawl rows.
Vanilla crawl unchanged. Crawl-idle/all other motions retain prior mask choices.
Global cohort quotas205/615/614/614 retained. Cohort3 redistributed equally over
7eligible motions (87/88each); cohorts1/2 remain76/77each over8motions. Lying and
sitting vanilla-only. Replayer33cases, including three moving-crawl cases.
130tick crawl sphere windows, radii,500/100 perturbed/vanilla failure penalties,
agonising exemptions, passive-limb torque/MSE/sphere exclusions unchanged.
Pure exhaustive rules comparison confirms all9other motions unchanged. Full2048
GPU preflight from SHA-verified18421 passed36864 boundaries, three finite resumed
updates, partial-reset masks/flags, reference speed consistency and33 independent
MSE/reward reconstructions. Unreachable crawl/cohort3 combination asserted absent.
Latest18485_final downloaded and SHA verified against persistent backup. Resumed
on SAME retained RTX4000Ada podvpv6saq7zyooak into
20261102_140858_uefn_slowloco_disabled_curriculum_crawl_legs_only_2048,
trainer5088/guard5089,bridge62948/dashboard9664. Live18486->18496,
1212219392samples verified. Optimizers/normalizer restored;33live replay cases
independently verified, moving-crawl arms enabled, persistent checkpoint readback
passed. Until-stopped released. TB8035 run14-08-58; local8021 replay verified33cases with both crawl arms enabled.
Helper Labs/RoboticMotionAE/deploy_crawl_legs_only.py; receipts in
Saved/MimicKitSlowLoco/crawl-legs-only-deploy-20261102. Source SHA 7b75073bb8269bb840f688dd52c0be8c8c9bfd582e9f5fd77bf20af34dd3b0d8.
Following sections are historical and superseded by this section where changed.

**November 2 crawl130 / perturbed penalty500 — VERIFIED RUNNING.**
User requested130tick crawl pelvis recenter and fivefold failure penalties on
all perturbed rows. Crawl/crawl_idle windows130, other motions70; sphere radii
unchanged. Precomputed per-world penalties500 for cohorts1/2/3,100 forvanilla.
Applied once on FAIL with zero bootstrap; no TIME penalty. Agonising variants
retain failure exemptions. Lying/sitting stay vanilla-only and34replays retained.
Row-specific penalty metadata is preserved through shared replay metadata, so
reward reconstruction and replayer reflect actual500/100 values correctly.
Full2048 preflight from SHA-verified18118 passed36864 boundary cases, three
finite resumed updates, disabled torque/MSE exclusions and34 independent reward
reconstructions. Actual periodic target class tested through130/260 recenter.
Resumed latest18220_final, locally/persistently SHA verified, on SAME retained
RTX4000Ada podvpv6saq7zyooak ($0.28/h). Run
20261102_131201_uefn_slowloco_disabled_curriculum_crawl130_penalty500_2048,
trainer4168/guard4169; bridge38704/dashboard48040. Live18221->18231,
1194852352samples verified; actor/critic optimizers and normalizer restored.
Live34rows independently reconstruct losses/rewards, correct penalty by cohort,
130/70 metadata, moving world target and exact recorded recenter positions.
Persistent checkpoint readback verified. Until-stopped released; TB8035 run
13-12-01. Local8021 replay verified34rows with130/70 windows and500/100 penalties.
Helper Labs/RoboticMotionAE/deploy_crawl130_penalty500.py; receipts under
Saved/MimicKitSlowLoco/crawl130-penalty500-deploy-20261102. Source SHA 3c6393fa9a6d97d643291a4ee9070fad2b3456892b661e7e29513f07bd54045a.
Following sections are historical and superseded where changed above.

**November 2 crawl100 / relaxed-pose sampling — VERIFIED RUNNING.**
Resumed latest17817_final, locally/persistently SHA verified, on SAME retained
RTX4000Ada podvpv6saq7zyooak ($0.28/h). New run
20261102_114802_uefn_slowloco_disabled_curriculum_crawl100_2048;
trainer3023/guard3024, bridge16144/dashboard7508. Live17818->17828,
1168441344samples, optimizer/normalizer restored. Persistent checkpoint readback
verified; setup watchdog released to until-stopped. No extra GPU allocated.
Lying/sitting now vanilla only. Global cohort counts205/615/614/614 retained;
perturbed slots evenly redistributed across8eligible motions (76/77 per group).
Crawl/crawl_idle world pelvis sphere reanchors every100ticks; other motions70.
Radii unchanged: pelvis40cm vanilla/80cm perturbed. Target follows the scaled
reference in world space, resets horizontal anchor only, and preserves target Z.
Per-row replay metadata now explicitly includes actual100/70 reset interval;
old screenshot150 label was not actual old physics70. Replayer34cases:
10vanilla +8each perturbed group. Local8021 converted replay and TB8035 run
11-48-02 verified. No motion/loss/strength/config changes. All previous passive
limb exclusions, agonising failure exemptions and -100 failure penalty retained.
Full2048 GPU preflight passed36864 termination boundaries, three finite resumed
updates and independent34-row MSE/reward reconstruction. Live checks also verify
crawl target movement and exact XY reanchor at recorded100tick boundaries.
At50% crawl speed, authored travel before reset is76.5cm, less than80cm radius:
standing still can still pass that case. At60% travel90.8cm exceeds radius. User
informed; exact requested radius/timing retained without tightening.
Helper Labs/RoboticMotionAE/deploy_crawl100.py; all receipts in
Saved/MimicKitSlowLoco/crawl100-deploy-20261102. Source SHA 4cd9f83407df2e004f7332f766299864a74b1e675725c55c3f35a4196742217d.
Following dated sections are historical run state, superseded by this section.

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

## Current continuation: all eight animations loop

User requested locomotion-style looping for every native motion. All eight
training PKLs now use stock WRAP (1), with original frame arrays/fps unchanged.
The source Cutter dataset and AE data remain unchanged. MotionLib repeats phase
and accumulates horizontal cycle displacement; no clip-end reset.10s episode
timeout and27cm enabled-target checks remain, including disabled-foot exemptions.
64-world test verifies every target at26/28cm, no end-of-clip reset across multiple
cycles, cycle reference/velocity parity and retained timeout. Report loop-termination-test.json.
Run20261031_171941_uefn_slowloco_unperturbed_2048,trainer1066/exit guard1067,
same2048world RTX4000Ada pod/rate. Resumed latest1197_final,28,668,284bytes,
SHAb45b90c1f412025bfefe288f6b3f291df8d299cddca2624290eb1b92b377f7a1,
downloaded/hash/CRC verified. Source5413cb0aa8befb45efc8784f580b03f98837492ce6deba1c97b96fb894b5b5b0
persistently readback verified. Bridge55212/dashboard8040. Remote eight modes verified.
Live continuation verified at1198/78,577,664samples, optimizers/normalizers
restored from78,512,128samples. New checkpoint1198 (30,164,030bytes), SHA
e9db29c4dc080906cf4e755d81d2dea93481893775aa304f8673998fdeaf2f4f,
independently readback verified. Until-stopped control restored after checks.
Actual replay has all8WRAP modes, no clip-end flag2; crawl_idle,agonising,
agonising_idle,lying reach10s timeout over repeated cycles. Other rows can still
fail27cm checks. Disabled-foot exemption retained. TB17-19-41 and replay verified;
receipt loop-replay-verification.json. No learning-improvement claim.
Earlier continuation and initial launch details below are historical.

## Previous continuation: disabled-foot termination exemption

Run `20261031_143146_uefn_slowloco_unperturbed_2048`, same pod/rate2048worlds,
trainer816/exit guard817, resumed latest checkpoint278_final (18,284,544samples).
SHA498468a9da7d24e1ff96859a0255edc2ebc8672445e4a4f0094b42c6fc702273,
28,504,183bytes, preserved locally and verified persistent. Actor/critic optimizer
and normalization restored. Only termination changes: limpL ignores left-foot
target deviation; limpR ignores right-foot deviation. All other target points,
clip-end/timeouts, limb motors, observations and reward terms unchanged.
SlowLocoEnv owns the exemption; original OmniWalkEnv remains unchanged.
Actual64-world test covers each point at26/28cm across all8motions, preserves
head failure alongside exempt feet, clip-end and timeout. Test report:
Saved/MimicKitSlowLoco/disabled-foot-termination-test.json.
New source SHA6294179fa20cb03a6e3fb176543531175504baeb18c15659ff22d6bdbee76f84,
persistently readback verified. First new checkpoint279 and8-motion replay
confirm the exemption metadata. Bridge6556/dashboard47364.
Independent persistent readback of checkpoint279 passed; resumed samples18,350,080.
Until-stopped deadline restored after verification; TB14-31-46 and local8-row
replay verified. Training advancement receipt: disabled-foot-training-after.json.
Prior launch history follows; do not treat prior trainer/observer IDs as current.

User approved eight native targets only (LAFAN stays AE-only), RTX4000Ada up to
$0.28/hour until stopped. After earlier capacity failures, the heartbeat allocated
Community RTX4000Ada pod `5xs589fdlcb7nr` at $0.20/hour, October31 12:43UTC.
Run `20261031_134805_uefn_slowloco_unperturbed_2048`, trainer435/exit guard436,
started fresh. Verified update0->10 and65,536->720,896samples;160-input actor and
critic, zero prior samples/offset, finite8-motion replay with correct limp flags.
Checkpoint0 SHA25692f4006201aab6e49dbed61d7ea4e4c44ea9c2af94b6e96945d23755bb855b97,
28,320,638bytes, independently verified in persistent storage. Initial recent
mean8.15s/update (~8,041transitions/s), no numerical or backup failures.
Setup deadline released to until-stopped after verification. Local guard3620,
remote guard148 and trainer exit guard436 retained. Runtime cache restored19.24s.
Deployment helper explicitly detaches/reconciles guard subprocess; fixed initial
shell background-list SSH hang. Source package/settings were not changed.
Bridge50092/dashboard23340, TB supervisor56448/replayer13956. Both services
restored and current-run data verified. TB runFilter=13-48-05, port8035; replay8021.
Receipts live-verification.json, launch-contract-verification.json,
telemetry-verification.json, local-servers.json under Saved/MimicKitSlowLoco.
Heartbeat `launch-slow-loco-on-rtx-4000-ada` deleted after verified launch.
Old locomotion pods remain stopped. Do not repeat allocation/setup/launch.

## Prepared contract

Fresh actor/critic,2048worlds,256 per clip: crawl, crawl_idle, agonising,
agonising_idle, limpL, limpR, lying, sitting, in exactly that one-hot order.
160 observations:146physical +8one-hot +4limb-enabled (right arm,left arm,right
leg,left leg) +2circular phase. limpL disables left leg; limpR disables right.
All other limbs enabled. Hip/knee/ankle7DOFs have zero motor force bounds, in
the actual coupled solver and residual checks. This is passive, not a zero-speed
servo. Mass, collisions, joint limits and full physical observations remain.
World assignments stay fixed through resets, so limb flags/motor masks agree.

Unperturbed random reference-frame starts. Policy PKL frame arrays/fps match the
eight native robotic exports; only loop_mode changed toWRAP. No seam blending.
Clips repeat with standard horizontal cycle displacement;10s episode cap. Same original
crawl27cm head/hand/enabled-foot collider-target failure, four calibrated world-body
MSEs plus old flat-COM band term, exp(-sum)reward and auxiliary phase supervision.
No AE/inference, no new jiggle losses, no limb tracking masks or failure penalties.
Original crawl PPO settings:gamma.99,lambda.95,noise.05,SGD1e-4 actor/critic,
1024/1024/512 layers,32steps per update. Both networks see160 inputs.

Current normal-locomotion source archive was copied into an isolated package,
with the original crawl policy class for ordinary action noise and phase training.
Retained optimized physics, actual PHAT assets and backup/error guards. Restored
the previously tested crawl contact-capacity fix (all normal rows retained,
no change in friction/tolerances). New per-world motor mask multiplies bounds
in scalar/block/coupled solver and residuals; ordinary caps are unchanged.

## Evidence and launch

State/package: Saved/MimicKitSlowLoco. Source archive SHA256:
80c50218958386685cbdfda98efdb983e8d3be717685b9aeb9eb21b8005391b0.
Persistent readback verified at key
mimickit/pipeline_20261014/slowloco/source_80c502189583.zip.
source-inventory.json is authoritative for all exact package bytes, including
recorder changes (one replay per clip, limb metadata) and backup retention.
Initial checkpoint plus latest three verified backups retained, scoped only
to this new run; pruning happens after successful independent readback.

64world local CUDA preflight passed twice after fixes.90ticks of alternating
forceful commands: disabled torque max0 on final test (previous test7.5e-21Nm),
enabled peak200Nm. Exact one-hot/limb flags and subset/full reset checks;
finite physics, one disposable PPO update, finite parameters, phase head loss;
all8deterministic replay clips captured and local replay conversion passed.
Reports preflight.json, preflight-replay.log, replay.npz/replay.json.
This preflight is wiring verification; remote2048-world startup is verified above.

Use Saved/Robotics/env/Scripts/python.exe with
Labs/RoboticMotionAE/deploy_slow_policy.py:
1. allocate — reconcile pod.json/provider identity before any retry; never duplicate.
2. setup —1200s local setup watchdog; remote guard before runtime restore.
3. status —inspect runtime-cache-restored.json and setup errors.
4. launch —fresh2048; verified source inventory; trainer exit billing guard.
5. observe —isolated bridge/dashboard into existing all-history TB and replayer.
6. verify —requires fresh advancing status>=10updates, trainer/exit guard alive,
   no failures, independent persistent checkpoint hash; only then remove setup
   deadline and retain until-stopped authorization. Check two advancing statuses,
   actual remote observation/model/replay metadata and all8 motion labels as well.

No old checkpoint load: new motion-conditioning architecture requires fresh policy.
If setup/launch fails, use the owned pod's billing_stop helper and confirm EXITED;
do not leave an idle paid GPU. Verified running trainer retains its exit billing guard.
Source builders/preflight are beside this document. Dataset/AE remain separate
under Saved/RoboticMotionAE/20261031_slowloco and the user's Cutter directory.
