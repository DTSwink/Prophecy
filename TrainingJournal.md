# Standalone training journal

This is the handoff for standalone policy/AE training, datasets, loss experiments,
Runpod/Kaggle jobs, checkpoint storage, TensorBoard and training replayers.
It is separate from [the Unreal/game journal](ProjectJournal.md). Established
Unreal-linked game labs, native integration, PHAT saves and Blueprint/runtime
contracts remain there. Training-only work must not append to ProjectJournal.md.

## Current handoff

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

**November 3 local observer memory reduction (side chat).**
Local bridge/dashboard/TensorBoard supervisor and Stepper replayer now set
OPENBLAS_NUM_THREADS/OMP_NUM_THREADS/MKL_NUM_THREADS/NUMEXPR_NUM_THREADS=1 before
numerical imports. Fresh import A/B: bridge private commit758->51MB, dashboard
390->37MB. After local service restart and real replay/telemetry requests:
bridge937->165MB, dashboard471->112MB, TensorBoard435->76MB, replayer407->37MB.
These are private committed memory, not physical RAM freed; live totals fluctuate.
Existing singleton observer launcher used; one worker per service. GPU trainer,
source package, rewards, current main-chat preflight and provider untouched.
TB still selects the same newest10 directories (8 currently contain scalar tags),
jiggle card works; replayer serves24459 and44 historical captures; bridge download
counter advanced3.08->8.50MB. Rules live in local entrypoints so future launches
inherit them. Bodyflip/Throw and Claude jobs untouched. Evidence/backups:
Saved/MimicKitTraining/local-memory-20261103/. Replayer entrypoint is
C:/Users/singerie/Documents/Cursor/stepper/training/rollout_debug_viewer/server.py.

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

**November 3 jiggle weight matched to an episode termination cost — VERIFIED RUNNING.**
User clarified comparable to500 termination points OVER AN EPISODE, not per tick.
Latest available capture22905: seven complete300tick rows cost107–208 total at
coefficient2. Increasing coefficient to9 (4.5x), retaining cap5, scores mean502.37,
median505.01 on those same rows. This is a fixed calibration, not automatic cost
normalization: better movement should cost less. Six-frame detector/tolerances,
all other reward/physics/termination/settings unchanged. Reference scores remain0;
independent CPU reconstruction, rigid-transform and partial-reset checks passed.
Only package pipeline/crawl_jiggle.py changed. Resumed latest22938_final, locally
downloaded/persistent SHA148985e78765711b00f0f9b57dc59db57cc76fdfdcbdd397bfab43bccf7bc267,
on retained pod9snbu59mla2xcd. Run20261103_081246_uefn_slowloco_disabled_curriculum_crawl_jiggle_2048,
trainer10346/guard10347. Verified22939->22949,1,504,051,200samples, optimizer/normalizer
restored, coefficient9 in8 independently reconstructed live replays, persistent
checkpoint readback hash verified and setup deadline released to until-stopped.
TB new08-12-46 penalty card live (1.535 mean/tick at22949); replayer22939 published.
No extra GPU/physics/other reward changes. Helper deploy_crawl_jiggle_episode500.py; receipts
Saved/MimicKitSlowLoco/crawl-jiggle-episode500-20261103/.

**November 3 crawl jiggle replacement — VERIFIED RUNNING.**
Latest user instruction explicitly supersedes the earlier21779 restart preference:
resume LATEST after replacing the additive forward bonus with a harsh multiframe
hand-jiggle cost. Current isolated both-passive-leg crawl scope retained.
Candidate uses6ticks/0.2s velocity cancellation on both hands: pelvis-relative
translation in world axes plus world angular motion, constant motion unpenalized.
Tolerance .05m/s and1rad/s; normalized squared excess, coefficient2, cap5 per tick,
subtracted outside exp(-pose_loss). First5samples warm up, per-world reset clears
history; no cross-episode leakage. Four known bad clips score3.62–4.19 mean cost;
their recorded references score0. CPU independent NumPy/Torch, partial reset,
translation and yaw checks pass. Full2048 GPU preflight passed36864 boundaries,
three resumed finite updates and independent eight-row reward reconstruction at
the initial stronger cap10. Final cap5 passes the same CPU reconstruction and
keeps worst discounted nonterminal cost <=500 (gamma .99). Actual final-cap5 run
verified advancing22803->22813,1,495,138,304samples; eight live replay rewards
independently reconstruct, forward bonus0, new cost active. Persistent checkpoint
readback hash verified and setup deadline released to until-stopped.
Run20261103_074137_uefn_slowloco_disabled_curriculum_crawl_jiggle_2048,
same retained pod9snbu59mla2xcd; trainer9488/guard9489. Resumed latest22802_final,
downloaded locally and SHA verified80049e3abd635959a65017bff71f45111bbb654443636168c3b92da6208cec6a;
optimizer and normalizer restored,160inputs unchanged. No new GPU allocated.
TB reward/crawl_jiggle_penalty displays fresh4.479 at1,495,138,304samples. Replayer
8021 publishes22803 and displays six-frame penalty/total reward; local converter
and dashboard mapping updated. Singleton observer refresh, no duplicate services.
Receipts: Saved/MimicKitSlowLoco/crawl-jiggle-20261103/; helper
Labs/RoboticMotionAE/deploy_crawl_jiggle.py. Physics, termination,55cm pelvis
sphere/200tick recenter and5-minute replay cadence remain unchanged.

**November 3 passive wrist damping probe — not deployed.**
Installed-Jolt diagnostic, frozen checkpoint22054, same recorded frame150 starts,
80ticks at30Hz/240Hz physics, both leg motors off, current motor caps unchanged.
Added separate implicit isotropic wrist/forearm viscous coupling tau=-c*relative
omega (no pose spring/world drag); independent two-inertia decay selftest error
1.12e-8rad/s. Row0 c=0/1/5/20/100Nm*s/rad travels50.34/50.59/49.47/46.06/54.65cm.
At c20 across rows0/2/5/7 wrist angular-velocity-change RMS falls57–66%, but
88–92% of forward travel remains and shoulder changes scarcely decrease.
At c100 row0 wrist changes fall79%, while hand translation cancellation increases
and forward travel increases9%. Wrist damping alone does NOT eliminate vibration
propulsion; the hand still oscillates through the rest of the arm. Ordinary
viscous damping also resists legitimate wrist motion; no retraining benefit claimed.
Eleven small single-threaded local probes completed; no extra GPU, production
source/settings, trainer or checkpoint changes. Scripts test_crawl_wrist_damping.py
and summarize_crawl_wrist_damping.py under Labs/RoboticMotionAE; complete traces,
results, physical selftest and comparison.png under
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

The following state was last verified on November 2, 2026. This documentation
move on November 3 did not poll, stop, restart or modify training. Check live
receipts/provider state before operational actions; old PIDs are not proof of life.

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

## Routing and maintenance

- Start here for training work, then read the relevant current topic:
  [MimicKit training](Docs/MimicKitTraining.md),
  [slow loco](Labs/RoboticMotionAE/SlowLocoPolicy.md),
  [motion AE](Labs/RoboticMotionAE/README.md), or
  [crawl training](Labs/CrawlTraining/README.md).
- Keep this current handoff concise. Put detailed procedures and evidence in
  topic docs/receipts; preserve superseded work as explicitly historical entries.
- Only add an Unreal-journal note when actual Unreal integration, assets,
  Blueprint wiring, runtime/build state or a native compatibility contract changes.
  Link the training evidence rather than copying operational logs.
- Preserve the latest user instructions, protected checkpoints and unrelated
  workloads. Historical launches, approvals, timers and RUNNING labels below
  are evidence, not current authorization or proof that a process is still active.

## Historical entries moved from ProjectJournal.md

Moved intact on November 3, 2026, retaining their original order and wording.
The current handoff above supersedes their old status/authorization claims.
Original root-relative links still resolve because this journal is at repository root.

<a id="training-entry-0020"></a>

**November 2 user HOLD — KEEP CURRENT TRAINING RUNNING UNCHANGED.**
User withdrew the pending restart: "wait maybe it's learning ... dont do it".
No stop command was issued and no requested friction3x, elbow150Nm or five-minute
replay changes were applied. Read-only check confirms trainer1276 running,
iteration20616 /1351155712samples; no stop.request or finished.json.
Leave current220414 run/source/settings unchanged. Those requested changes are
ON HOLD, not authorized to deploy while the user watches learning. Extra trial
queue remains cancelled. Receipt: crawl-traction-20261102/user-hold-status.json.

<a id="training-entry-0021"></a>

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

<a id="training-entry-0022"></a>

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

<a id="training-entry-0023"></a>

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

<a id="training-entry-0024"></a>

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

<a id="training-entry-0025"></a>

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

<a id="training-entry-0026"></a>

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

<a id="training-entry-0027"></a>

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

<a id="training-entry-0033"></a>

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

<a id="training-entry-0034"></a>

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



<a id="training-entry-0067"></a>

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

<a id="training-entry-0068"></a>

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

<a id="training-entry-0069"></a>

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

<a id="training-entry-0070"></a>

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

<a id="training-entry-0071"></a>

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

<a id="training-entry-0072"></a>

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

<a id="training-entry-0073"></a>

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

<a id="training-entry-0074"></a>

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

<a id="training-entry-0075"></a>

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

<a id="training-entry-0076"></a>

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

<a id="training-entry-0077"></a>

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

<a id="training-entry-0078"></a>

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

<a id="training-entry-0079"></a>

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

<a id="training-entry-0080"></a>

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

<a id="training-entry-0081"></a>

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

<a id="training-entry-0082"></a>

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

<a id="training-entry-0083"></a>

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

<a id="training-entry-0084"></a>

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

<a id="training-entry-0085"></a>

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

<a id="training-entry-0086"></a>

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

<a id="training-entry-0087"></a>

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

<a id="training-entry-0088"></a>

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

<a id="training-entry-0089"></a>

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

<a id="training-entry-0090"></a>

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

<a id="training-entry-0091"></a>

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

<a id="training-entry-0092"></a>

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

<a id="training-entry-0093"></a>

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

<a id="training-entry-0094"></a>

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

<a id="training-entry-0095"></a>

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

<a id="training-entry-0096"></a>

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

<a id="training-entry-0097"></a>

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

<a id="training-entry-0098"></a>

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

<a id="training-entry-0099"></a>

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

<a id="training-entry-0100"></a>

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

<a id="training-entry-0101"></a>

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

<a id="training-entry-0102"></a>

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

<a id="training-entry-0103"></a>

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

<a id="training-entry-0104"></a>

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

<a id="training-entry-0105"></a>

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

<a id="training-entry-0106"></a>

**October31 contact-viewer playback freeze fixed.**
First RAF timestamp could precede performance.now() recorded by the Play handler,
producing a negative time/frame index and aborting draw. Clock now initializes
from the first RAF callback, elapsed time and sample indices are nonnegative,
and looping uses positive modulo. Clip changes/scrubbing reset the clock. Space
is captured once (no key-repeat toggling); button and Space verified in browser,
including pause/resume with button focus and last-frame wrap to frame0.6.
Source contact_viewer and served contact-cleanup-20261031 assets synchronized;
view.js?v=playback2 invalidates the old script cache. No motion/training changes.

<a id="training-entry-0107"></a>

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

<a id="training-entry-0108"></a>

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

<a id="training-entry-0109"></a>

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

<a id="training-entry-0110"></a>

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

<a id="training-entry-0111"></a>

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

<a id="training-entry-0112"></a>

**October31 hip-twist wording clarified:** Identify legs by pose, not screen side.
The raised-knee leg is internally left_thigh: saved twist6.89deg, knee height40.3cm.
The folded-flat leg is internally right_thigh: saved twist-112.27deg, knee height7.3cm.
Its twist axis is aligned with hip-to-knee within0.000005deg, so this is longitudinal
hip roll relative to the parent constraint frame, not an arbitrary transverse axis
and not visible torsion along a rigid capsule. Original sitting already had
-102.39deg on that folded-flat leg; arm-only draft identical. User editing did not
originate this large value. Raised-knee leg has a swing-limit issue, not112deg twist.
No live changes; pending choice about pose/limits remains unresolved.

<a id="training-entry-0113"></a>

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

<a id="training-entry-0114"></a>

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

<a id="training-entry-0115"></a>

**October31 user-approved sitting pose deployment in progress:** User saved the
chosen pose at17:53:22UTC and explicitly requested updating training now.
Apply exact saved40 coordinates as a static50-frame WRAP sitting target; restore
all seven other motions byte-for-byte from before/motions. Resume preserved
1436_final before rejected full-body targets, on the same allocated4000Ada pod.
Receipt Saved/MimicKitSlowLoco/user-pose-20261031/application.json.
Pelvis editor rotation now compensates both legs and preserves foot transforms;
108rotation cases,61drag samples and6unreachable cases pass. Current user save
supersedes earlier unchanged verification save; do not reset or re-optimize it.

<a id="training-entry-0116"></a>

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

<a id="training-entry-0117"></a>

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

<a id="training-entry-0118"></a>

**Locomotion October31 - previous-run storage cleanup complete:** Removed63
persistent intermediate checkpoints from19-05-37, freeing3,223,710,635bytes
(3.22GB). Kept first323238 and latest329638. Latest independently SHA/ZIP
verified locally and SHA readback verified in persistent storage before deletion.
Other runs, telemetry and active slow-loco training untouched. Receipt:
Saved/MimicKitLocomotion/checkpoint-cleanup-20261031-previous-run/complete.json.

<a id="training-entry-0119"></a>

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

<a id="training-entry-0120"></a>

**Slow loco AE October31 - complete, offline only:** Added six selected FBXs
(agonising, agonising_idle, limpL, limpR, lying, sitting) to the user's slowloco
Cutter dataset; original four cuts byte-identical, ten clips total. Separate
2x512/latent128 AE trained12,000updates locally in49.2s; selected best3000,
validation.032804/test.036992. Export/CPU/input-gradient/invariance checks pass.
Bundle Saved/RoboticMotionAE/20261031_slowloco/bundle; current policy and normal
AE untouched. Reopen saved dataset in Cutter to see additions; active draft
preserved. [AE preparation and limitations](Labs/RoboticMotionAE/README.md).

<a id="training-entry-0121"></a>

**Locomotion October31 - latest backed-up checkpoint downloaded:** Owned pod
jvf465ue7ydr0a already EXITED; SSH refused, no stop/restart performed this turn.
Latest available persistent checkpoint329638 from19-05-37 saved locally under
Saved/MimicKitLocomotion/preserved-latest; full SHA readback and ZIP CRC verified.
Training is stopped; cause not investigated in this download-only request.
[Checkpoint receipt/status](Docs/MimicKitTraining.md).

<a id="training-entry-0122"></a>

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

<a id="training-entry-0128"></a>

**Locomotion October30 - whole-body velocity/angular-velocity MSE x5 live:**
Replaces leg-only x5 on all rows, including custom MSE alongside prior; no leg
stacking. Position/rotation unchanged; existing pelvis relative emphasis retained.
Latest302476 preserved locally/cloud, resumed same$0.28/hour RTX4000Ada2048,
run01-09-28 until stopped. Verified302487,~23.7ktransitions/s,20 replay rows and
new persistent backup. Immutable source1c2d2b9; no rejected idle objective.
[Current training handoff](Docs/MimicKitTraining.md).

<a id="training-entry-0131"></a>

**Locomotion October29 evening - leg velocity MSE x5 extended to all rows:**
User clarified velocity/angular velocity only, legs only, including custom MSE
alongside prior. Replaces idle-only x5 without stacking; position/rotation and all
other settings unchanged. Resumed latest294801 on same$0.28/hour RTX4000Ada,
2048worlds,run18-54-46. Advancing294812 at~24ktransitions/s; backup/replay verified.
Immutable source4b3d171. [Current training handoff](Docs/MimicKitTraining.md).

<a id="training-entry-0132"></a>

**Locomotion October29 - idle leg velocity MSE x5 live:** all idle cohorts now
weight both thighs/shins/feet linear and angular velocity MSE x5, with existing
handoff and other losses unchanged. Resumed latest291954 on same$0.28/hour
RTX4000Ada,2048worlds,run16-34-13. Advancing291965 at~23.9ktransitions/s;
new backup/configs/replay verified. Immutable sourceba917fd; bounded idle reward
remains rejected. [Current training handoff](Docs/MimicKitTraining.md).

<a id="training-entry-0133"></a>

**Locomotion October29 afternoon - cheaper GPU migration live:** resumed latest
checkpoint288354 unchanged on Secure RTX4000Ada7rpazo6vljk1yp at$0.28/hour,
2048worlds, run13-37-26, until stopped. Advancing288365 at~23ktransitions/s;
new persistent checkpoint, configs and20 replay rows verified. Old L4 remains
stopped. One-minute booking schedule completed; rejected idle reward stays excluded.
[Training handoff](Docs/MimicKitTraining.md).

<a id="training-entry-0134"></a>

**Locomotion October29 - rejected idle reward experiment rolled back:** user
requested restoration of the previous setup. Resumed preserved pre-change final
checkpoint274953 (10.977B samples) with exact leg7/idle3 sourcea757d51, original
reciprocal reward and all previous settings. Same L4dt94w83iq0waci,2048worlds,
run00-41-10 until stopped. Advancing274974 at~24k transitions/s; new checkpoint
backup/configs/20 replay rows verified. Idle-comparison plan cancelled; rejected
idle-recovery checkpoints must not be used for future resumes.
[Current training handoff](Docs/MimicKitTraining.md).

<a id="training-entry-0153"></a>

**Locomotion October28 — resumed after funds interruption:** user selected latest
2048-agent foot-loss experiment. Preserved/verified checkpoint266159 at10.401B
samples; resumed unchanged on same L4 f0454mznhwpt34 ($0.59/hour), run13-01-24,
until stopped. Verified advancing266170, ~23.5k transitions/s, exact configs/source,
20 replay rows and new persistent checkpoint readback. Bridges restored; recovery
untouched. [Training handoff](Docs/MimicKitTraining.md).

<a id="training-entry-0336"></a>

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

<a id="training-entry-0337"></a>

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

<a id="training-entry-0338"></a>

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

<a id="training-entry-0339"></a>

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

<a id="training-entry-0340"></a>

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


<a id="training-entry-0341"></a>

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


<a id="training-entry-0342"></a>

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



<a id="training-entry-0343"></a>

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


<a id="training-entry-0344"></a>

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

<a id="training-entry-0345"></a>

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

<a id="training-entry-0346"></a>

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

<a id="training-entry-0347"></a>

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

<a id="training-entry-0348"></a>

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


<a id="training-entry-0349"></a>

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


<a id="training-entry-0350"></a>

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


<a id="training-entry-0352"></a>

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


<a id="training-entry-0383"></a>

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


<a id="training-entry-0385"></a>

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


<a id="training-entry-0388"></a>

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


<a id="training-entry-0390"></a>

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


<a id="training-entry-0391"></a>

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


<a id="training-entry-0392"></a>

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


<a id="training-entry-0393"></a>

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

<a id="training-entry-0394"></a>

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


<a id="training-entry-0395"></a>

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


<a id="training-entry-0396"></a>

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



<a id="training-entry-0397"></a>

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

<a id="training-entry-0398"></a>

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

<a id="training-entry-0399"></a>

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

<a id="training-entry-0403"></a>

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

<a id="training-entry-0404"></a>

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


<a id="training-entry-0405"></a>

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

<a id="training-entry-0408"></a>

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

<a id="training-entry-0409"></a>

**October23 recovery â€” STOPPED, final custom-solver checkpoint downloaded:** user ended this experiment. Saved162044_final locally in `Saved/MimicKitEquipment/preserved-latest/20261023_090057_uefn_getup_custom_final_1024/`, verified SHA256 and ZIP against persistent backup. Recovery pod0to3wg3r3n926h confirmed EXITED; GPU billing stopped. Final replay available, prior native161960_final retained. Restart handoff points to custom162044 but no restart authorized. Receipts under `Saved/MimicKitEquipment/custom-solver-final-pass/`. The earlier RUNNING entry below is superseded.

<a id="training-entry-0410"></a>

**October23 recovery â€” custom solver final pass RUNNING:** saved native161960_final locally and verified persistent SHA256/ZIP, then resumed as `20261023_090057_uefn_getup_custom_final_1024` on recovery L4. Earlier Jolt-style contact/motor/limit solver plus floor guard restored;1,024 agents,240Hz physics/30Hz policy, learning settings unchanged. Advanced161971; new checkpoint161961 backup verified; TB/replayer live. First11 updates average~25.72s (~1.27k transitions/s) versus native~2.12s (~15.47k/s), about12x slower. Existing until-stopped duration retained. Audit `Saved/MimicKitEquipment/custom-solver-final-pass/verified.json`; see MimicKitTraining. Independent locomotion state below is owned by its other chat.

<a id="training-entry-0411"></a>

**October23 locomotion â€” STOPPED for final phase:** user requested latest download
and stop. Final154586 (3,559,882,752samples) preserved locally under
Saved/MimicKitLocomotion/preserved-latest/20261023_000133_uefn_locomotion_translation_speed_head_1024/.
Persistent readback, local SHA256 and ZIP verified. Loco pod leuh8va7hfcevy
confirmed EXITED; GPU billing stopped. Final TB/replayer sync finished.
Recovery untouched. Latest checkpoint/restart handoff updated; no new run started.

<a id="training-entry-0412"></a>

**October23 locomotion speed loss â€” RUNNING:** resumed latest140173_final as
20261023_000133_uefn_locomotion_translation_speed_head_1024. Extremity speed
subtracts only pelvis translation; rigid body rotation now counts. Added head;
all five reference limits recomputed at150% peak, idle uses backward walk.
Same soft-loss weight, perturbed idle/loco only. Other settings unchanged.
Latest CP preserved locally/S3; new backup and actual replay rewards verified.
Advanced140184 at~15.3k transitions/s. Recovery untouched. See MimicKitTraining.

<a id="training-entry-0413"></a>

**October 22 checkpoint cleanup:** downloaded and SHA256/ZIP-verified recovery145097 and locomotion137705 into each branch's `preserved-latest/<run>/`. Removed178 intermediate checkpoints from today's two active runs in persistent storage (7.92GB), plus corresponding pod copies; first/latest/newer checkpoints preserved. Both trainers remain running. Audit: `Saved/MimicKitEquipment/checkpoint-cleanup-20261022/completed.json`; details in `Docs/MimicKitTraining.md`. No retention-policy change.

<a id="training-entry-0414"></a>

**October22 locomotion checkpoint downloaded:** latest verified137705 saved in
Saved/MimicKitLocomotion/preserved-latest/20261022_203036_uefn_locomotion_walk_height2_1024/.
SHA256 and ZIP integrity checked; training left running. Receipt latest-local-checkpoint.json.

<a id="training-entry-0417"></a>

**October22 evening TensorBoard revived:** restarted missing local8035 server
and both bridge/dashboard pairs. Current recovery13-11-28/loco20-30-36 graphs
caught up; trainers untouched. Receipt Saved/MimicKit/tb-revive-20261022.json.

<a id="training-entry-0418"></a>

**October22 recovery checkpoint downloaded:** latest verified142097 saved locally
in MimicKitEquipment/preserved-latest; SHA256/ZIP checked. Both training runs
left unchanged. Receipt latest-local-checkpoint.json; see training journal.

<a id="training-entry-0419"></a>

**October22 walking height envelope â€” RUNNING:** locomotion resumed latest134504
as20261022_203036_uefn_locomotion_walk_height2_1024 on existing L4,1,024agents.
Walking rows also penalize the higher foot bottom exceeding the assigned walk's
reference maximum (24walks,1.88--6.26cm). Fixed weight calibrated2% of existing
loss using57,344noisy samples; existing8% airborne penalty unchanged. Reuses
foot detector; added math~0.047ms/batch. Actual replay losses/rewards, backup,
advancing134515 (~15.9k transitions/s) and newTBcard verified. Latest resume CP
preserved locally and S3. Recovery/idle viewer unchanged; see MimicKitTraining.

<a id="training-entry-0420"></a>

**October22 walking jump penalty â€” RUNNING:** locomotion resumed latest133578
on existing L4 leuh8va7hfcevy,1,024agents until stopped. New run
20261022_194959_uefn_locomotion_walk_ground8_1024. Only walking inputs, normal and
perturbed: squared excess when BOTH exact foot-box bottoms exceed1cm. Fixed
weight calibrated8% of existing live training loss; percentage varies afterward.
Analytic two-box detector~0.29ms/1,024worlds. Actual reward/masks, backup, advancing
133589 (~15.1k transitions/s), replay and loss/walking_airborne TB card verified.
Pre-change/latest saves preserved locally and S3. Recovery/idle viewer unchanged.
See MimicKitTraining opening and walking-airborne receipts.


<a id="training-entry-0421"></a>

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

<a id="training-entry-0422"></a>

**October22 first SuperMimic comparison â€” COMPLETE, adaptation failed:** isolated
free Kaggle two-T4 comparison from locomotion init119475,30min per worker.
Real-MuJoCo final perturbed-loco failures4.17% PPO versus62.99% adaptation;
normal-loco0.087% versus80.16%. Both finished with finite metrics, identical
checkpoint/reset observations and real experimental actor updates. Large
pre-clip gradients accompanied regression. This is our adaptation, not official
SuperMimic code. Do not promote experimental weights. Production untouched;
no further run launched. Reports/curve retained under Saved/MimicKitSuperMimic/.
See MimicKitTraining and Labs/MimicKitTraining/SuperMimicExperiment.md.

<a id="training-entry-0425"></a>

**October22 shared pelvis speed threshold corrected â€” RUNNING:** user requires
max of both get-up peaks for all perturbed rows, since front can roll into back.
Shared149.516cm/s replaces per-motion limits. Resumed latest130296 as
20261022_131128_uefn_getup_pelvismax7_1024, same L4/1,024agents until stopped.
Fixed loss weight recalibrated7%; all18perturbed replay rows share threshold.
New backup/reward/progress verified130307,~15.15k transitions/s. See training
journal opening and getup-pelvis-max receipts. Other settings/loco unchanged.

<a id="training-entry-0426"></a>

**October22 local idle push viewer â€” ready/paused:** http://127.0.0.1:8850/ .
Frozen latest-at-capture locomotion checkpoint0122776, one local CPU agent with
real idle inputs, native240Hz physics/30Hz policy. Limb selection, directional
mass-independent velocity kicks, strength control, reset and pause. Pause/hide
stops simulation and continuous drawing. Verified30.18updates/s and equal1m/s
kicks across hand/foot/pelvis. No cloud/training/Unreal changes. Restart with
Labs/MimicKitIdleLive/start.ps1; see its README and MimicKitTraining opening.


<a id="training-entry-0428"></a>

**October22 recovery horizontal pelvis speed cost â€” RUNNING:** resumed latest
129835 on same L4,1,024agents until stopped. Run20261022_124925_uefn_getup_pelvis7_1024.
Perturbed/perturbed+ only: squared excess above front0.473/back1.495m/s reference
peaks, fixed weight calibrated7%. Verified XY horizontal/Z vertical and pelvis
origin vs COM; pure vertical speed contributes zero. New backup/replay/TB and
129846progress verified (~15.1k transitions/s). Existing foot/AE weights and
normal/loco/physics unchanged. See MimicKitTraining opening and pelvis receipts.

<a id="training-entry-0429"></a>

**October22 recovery foot penalties â€” RUNNING:** resumed latest129347 on existing
L4 0to3wg3r3n926h,1,024 agents until stopped. New run
20261022_122519_uefn_getup_feet7_1024 adds ankle target-velocity and idle-relative
foot rotation costs to perturbed/perturbed+ only, fixed weights calibrated to
7% EACH. Normal/loco/physics unchanged. Latest checkpoint locally/S3 preserved;
new backup, advancing129358 and replay/TB terms verified (~15.2k transitions/s).
See MimicKitTraining opening and getup-foot calibration/verification receipts.

<a id="training-entry-0436"></a>

**October22 recovery resumed after funds outage:** latest127054 locally verified;
replacement L4 0to3wg3r3n926h, $0.59/hour until stopped, exact existing1024-agent
settings. Run20261022_104951_uefn_getup_perturbed_plus_1024 advanced127055->127065,
15.49k transitions/s; new persistent backup/replay/TB verified. Old retained pod
upszb03gy35fzj remains stopped. Locomotion independently resumed by its own chat;
both current TB streams verified. See MimicKitTraining opening and recovery
funds-resume-verification.json. Supersedes prior recovery running-pod status.

<a id="training-entry-0437"></a>

**October22 locomotion resumed after funds shutdown â€” RUNNING:** latest119475
(2,409,365,504samples) locally/persistently verified, optimizer/normalizer restored.
Old L4q764mqd40pabiq unavailable after Runpod shutdown; retained disk preserved.
Replacement L4leuh8va7hfcevy,$0.59/hour,1,024agents until stopped, exact previous
settings/source. Run20261022_104557_uefn_locomotion_pelvis_velocity5_1024,
verified119476->119486 and first backup. TB10-45-57, bridge/dashboard publishing.
Recovery unchanged. See MimicKitTraining opening and funds-resume-* receipts.
Supersedes locomotion status below.

<a id="training-entry-0440"></a>

**October22 locomotion TB refreshed:** local observers restarted; missing event
history restored through2.324B samples, live cards verified17seconds old. Current
run23-17-29 selected. L4 training remained uninterrupted at~19.25ktransitions/s.
Dashboard skips unnecessary replay scans when full-batch counters are available;
bridge polling30seconds,TB cap10unchanged. See MimicKitTraining opening and
Saved/MimicKitLocomotion/tb-refresh-20261022.json.

<a id="training-entry-0441"></a>

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

<a id="training-entry-0442"></a>

**October21 pelvis velocity MSE x5 â€” RUNNING:** pelvis-only 3D linear velocity
contribution multiplied by5 on every locomotion-branch row (normal/perturbed,
idle/loco), retaining body mean and AE/MSE handoff. Latest99574_final
(1,757,249,536samples) locally/persistently verified and resumed as
20261021_231729_uefn_locomotion_pelvis_velocity5_1024, sameL4q764mqd40pabiq,
1,024agents,$0.59/hour until stopped. Verified99575->99585 at18.56ktransitions/s,
first backup verified, actual20row replay confirms new weighting. Other losses
and recovery branch unchanged. TB23-17-29; see MimicKitTraining opening and
Saved/MimicKitLocomotion/pelvis5-* receipts. Supersedes loco status below.

<a id="training-entry-0443"></a>

**October21 recovery perturbed+ switch scheduled:** in two hours, approximately
October22 01:16 Europe/Warsaw, resume latest with half the perturbed rows assigned
new initial velocities. Root linear velocity and local joint velocities come
from two different random locomotion frames; independent random 3D spin has
uniform magnitude 0â€“700 deg/s. Only these rows delay the 50% head-height failure
check from tick80 to100. Other settings unchanged. Implementation is scheduled,
not yet deployed. Plan Saved/MimicKitEquipment/perturbed-plus-switch.json;
heartbeat switch-half-of-perturbed-get-ups-to-perturbed. Preserve loco branch.

<a id="training-entry-0444"></a>

**October21 speed-loss TB card fixed:** dashboard whitelist omitted the already
logged loss/extremity_speed_excess. Added mapping, backfilled31points exactly,
restarted local dashboard only(PID2912), ongoing updates enabled. Trainer/GPU
uninterrupted. TB22-48-04 filtered to new card; see MimicKitTraining opening.

<a id="training-entry-0445"></a>

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

<a id="training-entry-0446"></a>

**October21 locomotion speed limits both150% â€” RUNNING:** feet raised135->150%,
hands unchanged150%, idle still uses matching walk backward. Latest99151_final
(1.743B) locally/persistently preserved, resumed20261021_221827_uefn_locomotion_extremity150_1024
on same L4q764mqd40pabiq,1,024agents,$0.59/hour until stopped. Verified99152->99172
at18.47ktransitions/s, first backup verified. TB22-18-27. Only speed-reference
artifact changed; recovery unchanged. See MimicKitTraining opening and speed150 receipts.
Supersedes earlier locomotion135%foot limit below.

<a id="training-entry-0447"></a>

**October21 persistent replay/checkpoint cleanup completed:** user approved deleting
the 468 intermediate physical UEFN checkpoint archives containing old replays.
Deleted exactly that list: 21,375,033,969 bytes (21.38 GB). Verified every deleted
key absent and all 14 protected latest/final saves present, including newer saves
found during execution. Training was not interrupted; local files, datasets,
source packages and TensorBoard logs untouched. Receipt:
Saved/MimicKitEquipment/replay-cleanup-20261021/completed.json.
This was a one-time cleanup, not a change to automatic retention.

<a id="training-entry-0448"></a>

**October21 locomotion extremity-speed limits â€” RUNNING:** perturbed rows fail
above135%foot/150%hand reference maximum in moving pelvis frame; idle uses
matching walk backward. Latest98733_final locally/persistently preserved;
resumed20261021_220225_uefn_locomotion_extremity_speed_1024 on replacement
L4q764mqd40pabiq,$0.59/hour,1,024agents until stopped. Verified98734->98754,
18.44k transitions/s, first backup readback verified. Replay5speed crossings
all terminate at first eligible tick. TB22-02-25. Initial startup table-shadowing
bug fixed/tested; old A40 stopped and unavailable. Recovery unchanged.
See MimicKitTraining opening. Supersedes loco status below.

<a id="training-entry-0449"></a>

**October21 locomotion perturbed idle pose MSE x5 â€” RUNNING:** position and
rotation only, perturbed ordinary idle only, across early MSE/handoff/full MSE.
Existing early coefficient0.01062843 retained; AE/velocities/normals/loco and
recovery untouched. Resumed preserved97272_final (1.682B samples) as
20261021_205453_uefn_locomotion_perturbed_idle_pose5_1024, same A40,$0.59/hour,
1,024agents until stopped. Advancing97273->97283,early14.0k transitions/s;
new backup persistent-verified. TB20-54-53. Scope tests and receipt details in
MimicKitTraining opening; Saved/MimicKitLocomotion/idle-pose5-*.
Supersedes earlier locomotion status below.

<a id="training-entry-0450"></a>

**October21 perturbed get-up jump termination â€” running:** pelvis worldZ
>=93.457782cm fails from tick6; first5ticks exempt, normals untouched. Existing
100failure cost/no success bonus. Latest104663_final locally/persistently
preserved, resumed20261021_200623_uefn_getup_pelvis_ceiling_1024 on sameL4,
1,024agents/until stopped. Verified104674 at~15.31ktransitions/s,backup and
11actual replay jumps terminated on first eligible crossing with penalty.
Previous success gates/all other settings retained; locomotion untouched.
See MimicKitTraining opening and pelvis-ceiling-verification.json.


<a id="training-entry-0451"></a>

**October21 locomotion early MSE+AE RUNNING:** user-requested added MSE
shares the AE fade: (1-mix)*AE + [mix+0.01062843*(1-mix)]*bodyMSE,
30ticks early/30ticks handoff. Calibration matches mean early costs~0.299 each;
late MSE, normals, physics/optimizers unchanged. Resumed preserved96009_final
(1.640B samples) on same A40wjxv6qigq3dy9o,$0.59/hour until stopped,1,024agents.
Run20261021_200213_uefn_locomotion_ae_earlymse_yaw180_1024, TB20-02-13.
Advancing96010->96020,early14.3k transitions/s,new backup persistent-verified.
Recovery untouched. See MimicKitTraining opening and early-mse verification
receipts in Saved/MimicKitLocomotion. Supersedes earlier locomotion status.

<a id="training-entry-0453"></a>

**October21 perturbed recovery success tightened / running:** exact screenshot
rollout103985 gives feet threshold13.034895cm and |head vertical speed|<2.103453m/s,
in addition to head>90%idle height. Both feet must pass; body-origin worldZ.
Latest104197_final saved locally/persistently before same-L4 restart as
20261021_194738_uefn_getup_success_gates_1024,1,024agents,until stopped.
Verified104208 at~15.85ktransitions/s, new persistent backup, all6recorded
successes satisfy new gates. Other settings unchanged; locomotion untouched.
See MimicKitTraining opening and success-gates-verification.json.


<a id="training-entry-0456"></a>

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

<a id="training-entry-0457"></a>

**October21 recovery resumed with1,024 agents:** latest99984_final retained;
new20261021_171139_uefn_getup_ae10_1024 on L4upszb03gy35fzj/$0.59hour,
until stopped. Optimizer/normalizer restored; other training settings unchanged.
Verified99985â†’99995 (~15.15k transitions/s early), persistent backup and replay.
Removed obsolete equipment512-agent launch restriction after first attempt
stopped automatically before training. Original/replacement retained pods
unavailable; both stopped. Locomotion untouched. See MimicKitTraining opening
and Saved/MimicKitEquipment/getup1024-verification.json.


<a id="training-entry-0458"></a>

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

<a id="training-entry-0460"></a>

**October21 recovery stopped / latest preserved:** user requested download then
stop. Final99984 at1,638,154,240samples verified locally and in persistent storage;
L4w9aq90rzkg1d0g confirmed EXITED. Prepared recovery resume pointer updated.
Final TB/replay synced; recovery bridge stopped. Locomotion untouched (its pod
independently reported EXITED). See Docs/MimicKitTraining opening and
Saved/MimicKitEquipment/stopped-latest-20261021.json. Supersedes running entry.


<a id="training-entry-0461"></a>

**October21 locomotion STOPPED by user:** final91895 checkpoint downloaded
and SHA/ZIP verified locally, preserved in persistent storage. L4rjsan0uitu03qd
confirmed EXITED; GPU billing stopped, local observers/active marker cleared.
Saved/MimicKitLocomotion/preserved-latest/20261021_091005_uefn_locomotion_ae30_mse30_yaw180_512/checkpoint_0091895_final.zip.
Recovery branch untouched. See MimicKitTraining opening and user-stop receipts.

<a id="training-entry-0472"></a>

**October21 recovery AE regularizer running:** user restores frozen AE on
perturbed get-ups only, additive to full position MSE. Fixed weight.2752568
calibrated for10% combined pose+AE cost on latest88363_final's evaluation.
Latest saved locally/S3 before resume; normal rows/settings unchanged. Live
20261021_091317_uefn_getup_ae10_512 on L4w9aq90rzkg1d0g until stopped, $.59/hr;
trainer696/guard697,bridge13512/dashboard1724. Verified88384 at~9.29ktransitions/s,
new checkpoint readback and actual18perturbed AE/2normal zero-AE replay rows.
See MimicKitTraining opening and getup-ae calibration/verification receipts.

<a id="training-entry-0473"></a>

**October21 locomotion AE30/MSE30 â€” running/verified:** latest78988_final
(1.294B) preserved locally/persistently, resumed sameL4rjsan0uitu03qd until-stopped.
Perturbed only:AE through30ticks,linear blend toMSE at60;originalAEweight6.94265826.
Normal rows/settings unchanged. Live20261021_091005_uefn_locomotion_ae30_mse30_yaw180_512,
trainer701/guard702;78989â†’79009 verified,~11.65k transitions/s,newbackup verified.
Replay confirms0/.5/1tracking weights at30/45/60. Recovery branch untouched.
See MimicKitTraining opening and Saved/MimicKitLocomotion/ae30-verification.json.

<a id="training-entry-0477"></a>

**October21 recovery resumed:** verified85149(1.395B) after storage cleanup,
same settings, replacement L4w9aq90rzkg1d0g at$0.59/hour until-stopped.
Old recovery GPU unavailable; retained disk preserved. Locomotion managed in
separate chat. Run20261021_074429_uefn_limp_floor_512,trainer479/exitguard480;
verified85150â†’85170 at~10.63k transitions/s and new85150 persistent readback.
Bridge18464/dashboard7392; TB and20-row replay available. Exact saved recovery
source retained via SHA-pinned launcher verification. See MimicKitTraining.

<a id="training-entry-0478"></a>

**October21 locomotion resumed:** latest75533 (1.238B samples), unchanged
settings and until-stopped authorization. Old L4 could not restart; replacement
L4rjsan0uitu03qd at$0.59/hour, live20261021_074500_uefn_locomotion_mse_yaw180_512.
Trainer481/exitguard482,bridge4900/dashboard22724. First75534 checkpoint
backup verified after fresh checkpoint-sized storage write/readback. Recovery
branch untouched. See MimicKitTraining opening and locomotion resume receipt.

<a id="training-entry-0479"></a>

**October21 authorized checkpoint cleanup:** latest recovery85149(1.395B) and
locomotion75533(1.238B) downloaded, SHA256/ZIP verified, preserved locally in
each branch's preserved-latest folder and in persistent storage. User-authorized
older physical loco/get-up checkpoints/replays removed:46.58GB persistent,
5.26GB local. Datasets, code, TB history, crawl/other Unreal models untouched.
No training restart. See MimicKitTraining opening and cleanup-20261021 receipts.

<a id="training-entry-0480"></a>

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

<a id="training-entry-0481"></a>

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

<a id="training-entry-0484"></a>

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

<a id="training-entry-0485"></a>

**Limp blend floor defect â€” October20, diagnosis preceding correction:**
Exact screenshot step79324 row11 reconstructed within1.42micrometres.
79.1% whole-pose blend to limp index31 places right hand44.5cm underground,
head25.8cm; saved limp endpoint only0.9cm penetration. Intermediate blended
pelvis height fails to clear the rotated/articulated body.16/18 replay starts
exceed5cm. Needs floor support recomputation after blending, at reset only.
Diagnostic turn did not modify or stop training; subsequently corrected above.

<a id="training-entry-0486"></a>

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

<a id="training-entry-0487"></a>

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

<a id="training-entry-0488"></a>

**Recovery start split â€” October20 17:14, verified running:**
Current run20261020_171428_uefn_normal_back80_half_random_512 resumes latest
77390_final (1,267,974,144 samples), preserved locally and persistent readback
verified. User changed only start distribution:256normal frame0 +256normal
random-frame rows;410back/102front retained. No stiff/limp/perturbed rows.
Same L4rovwuwstkm0s7r,trainer729/exitguard730,until-stopped authorization.
Verified iteration77521 advancing; checkpoint77491 backup verified.
Bridge448/dashboard8920 publishing; handoff watchdog released after verification.
See MimicKitTraining opening; supersedes frame0-only setup below.

<a id="training-entry-0489"></a>

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

<a id="training-entry-0491"></a>

**Random recovery poses â€” October20, whole-body rotations baked:**
The1,000 retained poses now also have a separate rotated/grounded dataset at
Saved/MimicKitEquipment/random-phat-poses-grounded/corpus.npz. Uniform SO(3)
root orientations, exact same local DOFs, zero velocities; minimal root height
against Z=0 using every collider. All1,000 nonpenetrating; lowering any pose
1micrometre causes penetration. Preview opened at
http://127.0.0.1:8843/Saved/MimicKitEquipment/random-phat-poses-grounded/.
Upright source preserved. Not deployed to training. See MimicKitTraining opening.

<a id="training-entry-0492"></a>

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

<a id="training-entry-0494"></a>

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

<a id="training-entry-0497"></a>

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

<a id="training-entry-0499"></a>

**MimicKit settings adopted â€” October20 14:10:** user approved noise0.075 and
GAE lambda0.98 from the completed comparison. Active
20261020_141039_uefn_getup_success_value_512 resumes latest72108_final/
1,181,433,856 samples, preserved locally and verified in S3. Same L4, until
stopped; trainer2154/guard2155, bridge25552/dashboard21856. Actual post-restore
noise verified0.075 and GAE0.98. Normal get-up failure card now counts all
completed normal get-up episodes every10updates, same cadence as perturbed
cards. Normal/perturbedâˆ’100 failure costs and success fix retained. First72109
backup verified;72119 advancing at~7.9ktransitions/s. See topic opening.

<a id="training-entry-0500"></a>

**Focused comparison complete â€” October20 13:55:** noise.075/GAE.98 modestly
better than current.05/.95 with success fix: failures30vs36 at64updates,
23vs32 at128,928 identical get-up starts; training411vs408seconds. No normal
loco regression. One training seed, short horizon; both test configs predate
normal-get-upâˆ’100 change. No alternative applied. Queue1224 exited.
Main133905 continues with normal-get-upâˆ’100,71741/1.175B,~8.3ktransitions/s,
backup71641 verified. See MimicKitTraining opening.

<a id="training-entry-0501"></a>

**MimicKit normal-get-up penalty â€” October20 13:39:** user requested sameâˆ’100
failure penalty for normal get-ups. Active133905_uefn_getup_success_value_512
resumes latest71440_final/1,170,489,344, locally/S3 verified. Trainer1587/guard1588,
same L4 and until-stopped budget. First71441 backup verified. Normal completion/
timeout unchanged, perturbed success fix retained. Focused comparison1224 was
paused during handoff and is resumed; both copies retain the frozen pre-change
objective for a fair comparison. Details in MimicKitTraining opening.

<a id="training-entry-0502"></a>

**MimicKit focused comparison requested â€” October20:** user now explicitly asks
to retry noise.075/GAE.98 against current.05/.95 with success fix. Bounded two-way
comparison queue1224,128updates each from70639, held-out evaluation at64/128.
No broader sweep or automatic live setting change. Main130053 continues unchanged.
See focused-success-launch.json and MimicKitTraining opening.

<a id="training-entry-0503"></a>

**MimicKit sweeps stopped â€” October20 13:15:** user objects to repeated sweeps.
Queue551 and its process group stopped, cancel.request set; do not restart
comparisons automatically. Main130053 remains training,70890/1.161B samples,
no failure. Earlier completed sweeps showed only modest improvement; no major
learning-speed gain established. Latest70639 baseline894/928 successes versus
current settings895/928 after64updates; other latest variants incomplete.
Keep live settings unchanged. See MimicKitTraining opening.

<a id="training-entry-0504"></a>

**MimicKit corrected resume â€” October20 13:01:** active
20261020_130053_uefn_getup_success_value_512, from70639/1,157,365,760 samples,
with known success value100. Same L4rovwuwstkm0s7r,.59/hour until stopped;
trainer444/exit guard445, bridge21024/dashboard29160. First70640 S3 readback
verified. Isolated corrected-success sweeps queue551 now starts from70639 too,
not the superseded67931. Results pending. See MimicKitTraining opening.

<a id="training-entry-0505"></a>

**MimicKit stopped by user â€” October20 12:55:** rollback67931 was too early.
Trainer saved68077; local download matches verified S3 SHA. Sweeps cancelled;
owned L4rovwuwstkm0s7r confirmed EXITED, billing stopped. User points to the
failure-curve trough immediately before its rise around1.159B. Selected retained
70639/1,157,365,760 samples (6.20% reported failure), last saved checkpoint before
the trough/rise; downloaded and ZIP checked. Do not reuse67931 or resume sweeps
from it. Training remains stopped. See latest MimicKitTraining opening.

<a id="training-entry-0506"></a>

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

<a id="training-entry-0507"></a>

**MimicKit storage investigation â€” October20 12:31:** no trainer running;
latest L4 9r63p3vlvogqz5 and temporary CPU helper both confirmed stopped.
Full runtime SHA-verified locally with AWS downloader; pod S3 requests still
time out. Sudden underlying cause unproven. CPU direct mount listed files,
but full reads/relay not yet verified. Additional.06/hour relay approval pending;
user asks for root cause instead. See opening of Docs/MimicKitTraining.md.

<a id="training-entry-0509"></a>

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

<a id="training-entry-0510"></a>

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

<a id="training-entry-0511"></a>

**MimicKit harder get-up sampling â€” October20 09:46:** resumed verified latest
69138_final with2/3 of perturbed get-up starts above50% strength,1/3 below.
Active094614_uefn_getup_skew_linear_512, trainer8547/guard8548 on existing L4,
until stopped; other training settings retained. Sequential disposable learning
ablations running; no candidate deployed. See [MimicKitTraining](Docs/MimicKitTraining.md).

<a id="training-entry-0513"></a>

**MimicKit LR comparison â€” October20:** isolated10-full-update2x/4x/8x tests
finished. On928matched get-up starts: baseline794successes,2x792,4x792,fixed8x787.
8x hits guard8of10updates; no demonstrated gain over current2x. Live7410 unchanged.
Single training seed/short horizon; do not claim a long-run winner.
Details: [MimicKitTraining](Docs/MimicKitTraining.md).

<a id="training-entry-0514"></a>

**MimicKit continuation â€” October20 08:57:** user authorized double actual actor
LR and the verified observation optimization. Latest67931_final/1.113B samples
preserved locally and S3 before resume. Active085731_uefn_lr2_graphed_linear_512,
L4ka68jrougesuit, trainer7410/guard7411, until stopped. LR5.625e-7â†’1.125e-6;
Adam state/KLguard retained. Observation graph/device quaternion optimization and
replay fixes deployed; reward/physics/distribution unchanged. First new backup
verified; details in [MimicKitTraining](Docs/MimicKitTraining.md).

<a id="training-entry-0515"></a>

**MimicKit get-up learning audit â€” October20:** live run unchanged. Failure rate
still improves slowly (~18.3â†’17.8%); remaining failures concentrate in strongly
perturbed front starts. Actual restored actor LR is5.625e-7 (1/8 YAML), inherited
from earlier guard reductions, not a new slowdown. Isolated matched update favors
a2x LR trial;8x worsened getup surrogate. No tuning deployed. See
[MimicKitTraining](Docs/MimicKitTraining.md) for measured counts and limitations.

<a id="training-entry-0516"></a>

**MimicKit replayer repair â€” October20:** valid recordings from the new locomotion
failure-penalty run were rejected because the replay reward check omitted that
penalty. A second downloader retry bug then replaced the archive with its last
chunk. Both repaired locally; cloud trainer4368 unchanged and still advancing.
Failed downloads now restart from byte0 and preserve existing valid rollouts.
Details and verification: [MimicKitTraining](Docs/MimicKitTraining.md).

<a id="training-entry-0525"></a>

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

<a id="training-entry-0526"></a>

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

<a id="training-entry-0543"></a>

**Crawl stopped at user request â€” October17:** user cancelled the additional
hour. Stop request reached run20261017_135639_uefn_crawl_velocity_512;
checkpoint1628 was saved and checksum-verified locally (SHAb2d38e957d29).
Owned pod o6qhah385ykhhx explicitly stopped; API confirms EXITED. Active run
marked stopped, latest verified pointer updated. No further training restart
authorized. Receipts: Saved/MimicKitCrawl/user-stop-confirmed.json and
local-backup-status.json. The previously planned14:58 finish is cancelled.

<a id="training-entry-0544"></a>

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

<a id="training-entry-0545"></a>

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

<a id="training-entry-0549"></a>

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

<a id="training-entry-0550"></a>

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

<a id="training-entry-0553"></a>

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

<a id="training-entry-0554"></a>

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

<a id="training-entry-0555"></a>

**Crawl TensorBoard auto-phase display fixed â€” October17:** phase head/MSE were
already trained and logged. Local dashboard omitted `uefn_crawl_idle_mse` from
its tracking-loss/auto-phase mapping. Added that objective and backfilled all
three crawl histories from raw events; exact step/value equality verified.
Charts `auto_phase/mse`, `auto_phase/weighted_loss` and `loss/auto_phase` now
publish, along with body-loss components. Restarted ONLY current crawl dashboard
(PID17188), no trainer/optimizer/run changes. Receipt
`Saved/MimicKitCrawl/autophase-dashboard-fix.json`.

<a id="training-entry-0556"></a>

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

<a id="training-entry-0557"></a>

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

<a id="training-entry-0558"></a>

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

<a id="training-entry-0559"></a>

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

<a id="training-entry-0560"></a>

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

<a id="training-entry-0561"></a>

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

<a id="training-entry-0562"></a>

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

<a id="training-entry-0563"></a>

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

<a id="training-entry-0564"></a>

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

<a id="training-entry-0565"></a>

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


