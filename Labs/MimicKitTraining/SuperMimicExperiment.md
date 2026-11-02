# Isolated SuperMimic experiment

## Current status: stopped by user; no verified learning-speed gain

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
zero32tick score changed~.02–.04 cohortmean, oneFAILoutcome. New assertion was
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
Measured diagnostic variance-times-cost1.40–1.46; no followup-training gate passes.
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

October23 16:00UTC source audit while the second seed runs: reread SuperTrack
section5.2 in research/supertrack.txt (lines873-880). Its policy-transfer test
freezes all but the final layer and uses a small learning rate. Our imagined
actor update changes the full actor; earlier phase-stability froze a separate
phase-predictor copy, not the motor feature network. Thus final-layer-only
transfer remains untested and could reuse learned physical features if the
prepared raw-observation student cannot generalize. Do not launch it over the
current job or conflate it with a faithful full SuperTrack reproduction.
Primary: https://static-wordpress.akamaized.net/montreal.ubisoft.com/wp-content/uploads/2021/11/24183638/SuperTrack.pdf
SuperDyno author links rechecked: project still404; OpenReview still asks for
human verification. No access-control bypass; full paper remains unread.

October23 source audit: Motphys/Uni-SuperMimic pinned at
bc0f0f3499a12019ec0ea313ff37bbd0a70a6a04. It explicitly derives from
supermimic_vibed, so its reported result is not independent confirmation of
another algorithm. Config/network/learner and Apache/MIT notices saved under
research/unisupermimic. It uses the same32-step differentiable objective with
critic bootstrap,10-frame actor history/goal,500model-only warmup iterations,
global gradient clip1 plus per-element clip.1. Our current actor lacks that
history/goal architecture; simply copying its learning rate would not reproduce
its setup. This audit identifies remaining architecture/transfer differences,
not a verified diagnosis or new launch. Source:
https://github.com/Motphys/Uni-SuperMimic/tree/bc0f0f3499a12019ec0ea313ff37bbd0a70a6a04

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


Further primary-source audit (no new launch/change): SHAC, arxiv2204.07137,
and official NVlabs/DiffRL algorithms/shac.py use a separate target critic for
actor bootstrap, updated alpha=.4 each iteration; return normalization is
optional. Current imagined_exact.py evaluates the online critic directly.
Earlier real-critic/EMA experiment is not this same target-critic ablation.
This remains a possible next discrepancy if smooth-policy evidence is negative;
not a diagnosed cause or claimed gain. Sources reread October23:
https://arxiv.org/abs/2204.07137
https://github.com/NVlabs/DiffRL/blob/main/algorithms/shac.py

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

Calibration COMPLETE, downloaded/analyzed: policies and world deltas exactly0,
real reward error<.000263 and hard perturbed event mismatches0. For final-policy
noisy starts, first32ticks real failures268/1332(20.12%), model171/1332(12.84%);
143false negatives and46false positives. Initial policy shows similar optimism.
Across four (overlapping) branch cohorts, final-policy32tick return MAE7.07,
eight-tick1.18; actual/predicted failure10.15/7.34% at32ticks versus2.22/1.86%
at8ticks. These are horizon-dependent descriptive errors, not independent
learning replications. Evidence now supports task-relevant model bias; it does
not establish a reversed gradient or any speed gain. Reports:
prophecy-model-rollout-calibration-reports/verified-calibration.json.
Workers153.15/152.44s incl64.7s setup; parent235.89s. Prior fitting extra.
Primary motivation for the next correction: MBPO (arxiv.org/abs/1906.08253)
uses short model rollouts branched from real data to limit model bias. Our native
PPO adaptation is not MBPO reproduction. Existing3min heartbeat ACTIVE.

Short-world v1 COMPLETE/analyzed/archived-v1: real/short PPO45/36actorupdates,
178.42/181.24s actual learning,301.38/303.77s with checks. Noisy failures
24.174/24.474%,det20.345/19.970%; noisyreturns30.533/29.664,det44.813/45.017.
All failure/return paired intervals span0; no gain. Actual deltas.09796/.08556.
Forty-four model-fit outer iterations did not update actor under32tick gate;
v2 tests whether matching the gate to the used horizon improves learning/time.
Prior326.30s fitting extra; v1 reports/receipt archived before reuse. No promotion.

Primary-source refresh while v2 runs: MBPO abstract explicitly motivates short
rollouts branched from real states (arxiv.org/abs/1906.08253); paper/systematic
model-learning alternatives at arxiv.org/abs/2204.01464 (VaGraM) and official
github.com/pairlab/vagram. Prior VaGraM-like tests here already failed; do not
repeat unchanged. SuperMimic's project FAQ confirms fitting stays online and
its reported3h includes collection/fit/policy updates, excludes final evaluation.
No cross-hardware or end-to-end speed claim from reused warm models. If v2 still
fails, audit residual task-boundary calibration (COM2 velocity/direction errors)
and the RWM-U uncertainty/recurrent-model discrepancy before another correction.

### Completed frozen model rollout calibration

COMPLETE madmad74100/prophecy-model-rollout-calibration v1. Receipt
Saved/MimicKitSuperMimic/rollout-calibration-launch.json; two free T4s,
600s parent/800s Kaggle bound. Startup verified: model hashes/workers55.88s,
actual calibration130.81s, both completed219.18s; parent235.89s.
Initial96009 and final PPO-WM policy are frozen; the same completed fitted world
is reused with SHA256 verification, no refitting. Compare actual MuJoCo with
logged-control and closed-loop predictions at1/4/8/16/32ticks, branches0/24/56/80,
two new seeds683101/683102, deterministic and production noise. Same real starts
and action noise. Terminal reward counted once; logged-control diagnostic is
censored at real episode end so actions after reset cannot leak. Two CPU checks
pass for cohort boundaries/confusion counts. No learning-speed claim; this tests
whether short rollouts avoid task-relevant model error. Original/production intact.

PPO-WM v1 COMPLETE, downloaded/analyzed and archived-v1. At182.84/184.01s actual
learning (302.36/300.33s including checks), PPO/PPO-WM accepted46/40updates.
Noisy failures23.724/23.574%,det19.970/19.970%; noisy returns31.049/30.905,
det45.447/44.954. Noisy difference-.150pp,95%motion-cluster interval[-1.504,1.284];
no convincing advantage. Both actual actor deltas verified(.09917/.09735).
Earlier326.30s model preparation is additional; setup~107s/arm, final eval~39s.
World and final policy selectively preserved/hashes saved in ppo-world-v1-models.
Next action: inspect calibration before choosing short branched rollouts or a
model-confidence correction. No proof of model bias or reversed gradients yet.
Existing3min heartbeat ACTIVE; this opening is authoritative.

### Completed PPO on learned-model rollouts

COMPLETE madmad74100/prophecy-ppo-world-race v1, submitted11:59UTC.
Receipt Saved/MimicKitSuperMimic/ppo-world-launch.json; two free T4s,
300s/arm including75s real checks; parent1000s/Kaggle1250s bound.
STARTUP VERIFIED: bootstrap.79s, source hashes24.08s, earlier-checkpoint
SHA54.22s and both actual GPU workers54.22s. Do not duplicate.
Original checkpoints/production untouched.

ACTOR UPDATES VERIFIED: real PPO first update172.46s; PPO-WM first204.71s,
40native actor minibatch steps, L2delta.011207, KL.006186, all model data detached.
Scorer real-data max reward error.000111, perturbed hard-event mismatch0.
Initial model rollout~1.25s plusPPOupdate~1.02s, excluding online model fitting;
model gate can pause actor steps. No learning advantage established yet.

New structural control from SuperMimic Section4.2/Figure5(b): use native PPO
on detached learned-model rollouts, versus native PPO on real MuJoCo rollouts.
This separates model-prediction usefulness from differentiating through the
model. First complete-policy direction audit was inconclusive, not evidence of
a reversed gradient: model scaled positive noisy22.072->22.297%,det18.769->18.318%;
all failure change intervals span0. Model raw-positive noisy return fell1.31,
CI[-2.58,-.042], but this one proposal does not establish a general defect.
Both original models restored exactly; reports verified/archived-v1.

Both methods restore earlier96009 actor/critic/Adam under frozen119475 task.
PPO-WM uses32x1024 detached transitions, exact dense reward, hard perturbed
termination, sampled learned normal-row failure probability; resets to real
replay states after failure/timeout. Native targets, loss, phase mask, optimizer
moments, KLguard and .075 noise retained. World fit/collection remain online,
inside time budget; earlier326.30s model preparation extra. This is an adapted
PPO-WM screen, not an exact paper replication or a speed claim. Three CPU checks
pass against actual pinned PPO: terminal-versus-timeout bootstrap/no reset
crossing, next-phase input versus supervision, failure precedence/penalty scope.
Normal120/300tick evaluation limitation remains; full normal checks and independent
seeds required before promotion. Primary source reread:
https://arxiv.org/pdf/2610.28480 (Section4.2, Figure5, AppendixD).
Existing3min heartbeat ACTIVE; this opening is the authoritative job.

Further primary-source audit while v1 runs: RWM-U's official lightweight
implementation is available at github.com/leggedrobotics/robotic_world_model_lite,
pinned13a798e9d35dabf12c0e6e02977b25ec64dfb2bd. Nine small source/license files
(74828bytes) read-only under research/rwm-lite, hashes/provenance saved; no assets
or pretrained ANYmal weights downloaded/executed. It uses32tick recurrent
history,8tick forecast,5-member ensemble and uncertainty-penalized imagination.
Paper https://arxiv.org/html/2504.16680v3; project links confirm official source.
These are potential model-confidence corrections, not demonstrated fixes here.
Also reread MBPO https://arxiv.org/abs/1906.08253: short rollouts branched from
real data limit accumulated model error. If current PPO-WM fails, first measure
its rollout failure/return calibration at matched starting states; then a short
branched-rollout control can test compounding error without changing the task.
Do not claim that current results prove inaccurate gradients or model bias.

### Complete-policy direction audit: COMPLETE

prophecy-supermimic-policy-step v1 COMPLETE in352s parent. Actual proposal
L2 .015279PPO/.001481model. Matched motor KL.05 scales2.7184/7.6331;
model phases RMS.00377 versusPPO.00823. Each evaluates5signed probes x2reset
seeds xdet/noisy. Baselines vary by tiny floating reset differences, bounded
2e-4. Model scaled positive versusnegative: det failure-.300pp,noisy-.526pp;
both95%motion-cluster intervals include0; return intervals also include0.
Neither direction establishes improvement versus its own baseline. PPO negative
raw direction measurably worsens noisy outcomes; positive direction inconclusive.
Local geometry diagnostic only, not a learning-speed result. Reports:
prophecy-supermimic-policy-step-v1-reports/verified-policy-step.json.

Previous earlier-
policy comparison COMPLETE, downloaded/analyzed and archived-v1. PPO/model
61/54actual actorupdates,240.70/236.66s actual learning,361.86/363.28s with checks.
Noisy failures23.574/24.099%, deterministic19.369/20.120%; returns31.649/29.498
noisy,46.658/43.678det. Model returns decreased from its own baseline in both
modes (95%motion-cluster intervals exclude0); no gain. More headroom did not
rescue this method. Prior326.30s model fitting is extra. No promotion.

Completed diagnostic rationale: previous gradient_fidelity.py/objective_audit.py
change ONLY the first action at a chosen tick, while freezing the policy. That
does not validate a shared-network parameter update which changes every later
action and autoregressive phase across motions. New audit uses the actual
first full-world Adam update; native PPO's first rollout/update is a control.
Both start from96009 under frozen119475 task, both actors/critics restored before
each probe. Five predeclared probes: baseline, raw positive/negative proposal,
and positive/negative rescaled to maximum action KL.05 across BOTH signs.
Calibration uses a separate64tick noisy rollout(seed98117), no outcome-based
selection. Test seeds582701/582702 are new; deterministic and production noise.
Restore original model exactly at end; no saved promoted policy. Three CPU
checks cover equal-KL scaling, both-sign bound and exact weight restoration.
Normal rows still120/300ticks in this diagnostic; full300tick confirmation is
required before accepting an improvement. This is a local direction diagnostic,
NOT a learning-speed comparison; proposal data/optimizer schedules differ.
Use free Kaggle only. Production/original checkpoint files untouched.
The subsequent PPO-WM test above supersedes this completed diagnostic.

### Earlier-policy comparison: completed method/limits

PPO versus same stochastic incremental-world H32 method, exact reward and hard
forward events, sigma.075, actorLR1.125e-6, phase unchanged. Both96009 under
frozen119475 task. PPO restored historical Adam states(beta2=.999,critic1e-4);
model retains fresh actorbeta2=.95/critic2e-4, explicit method difference.
Source norms/shapes exactly match. Earlier policy was trained under an older
objective; this is adaptation to frozen119475, not historical continuation.
Actual world fresh fitting~41s/firstactor45.12s included. Actor noiseRMS.0749,
real reward maxerror.000129/hard event mismatch0. Inputs/hashes verified.
Evidence prophecy-supermimic-earlier-policy-v1-reports/verified-comparison.json.

### Frozen headroom/evaluation audit: COMPLETE

prophecy-supermimic-headroom v1 COMPLETE, reports downloaded and analyzed in
prophecy-supermimic-headroom-reports/verified-headroom.json. Actual model delta0
for both policies; no actor updates. Shape and all observation/action mean/std
buffers exactly equal locally. Private earlier96009 dataset contains only
model/resume state plus provenance, original SHA
837b98a83ec5e86219bfbb2a1fd100054f6889c865f4f2e61b8dcddae4042542.

Current119475/earlier96009 first120tick perturbed failures: deterministic
4.279/19.144%, noisy6.456/23.123%. Continuous480tick completed episodes: det
4.031/23.368%, noisy7.199/26.194%; after first120ticks noisy7.019/25.894%.
The earlier policy therefore has materially more room for learning. Continuous
resets do NOT reveal a catastrophic hidden reset problem in119475. They weight
short failed episodes differently; not identical estimands. Normal300tick
noisy episodes fail4.41/4.07%, versus1.57/1.57% within first120ticks: previous
normal-row screens were horizon-limited, not full-episode success measurements.
Perturbed120tick episodes have no unfinished cases. Actual yaw spans+/-180.
Workers190.37/194.30s plus parent87.67s bootstrap. Frozen evaluation only;
these differences are NOT learning or speed gains.

### Native AWR v2 outcome

COMPLETE; downloaded/analyzed/archived prophecy-native-awr-race-v2-reports and
native-awr-v2-launch.json. Equal241s including checks (~162/163s learning),
PPO/AWR noisy6.156/6.682%,det3.979/4.505%; noisy returns64.495/63.594,
det79.435/78.290.43/33actual updates; deltas.09695/.15782. No verified gain.
Replay did not rescue AWR; no promotion. Paired failure intervals span zero.

### Native AWR v2: completed replay adaptation

v2 tests a concrete paper/native-library discrepancy: FIFO retains last4 real
rollouts (up to131072 samples), and returns/advantage weights are recomputed
AFTER critic fitting, as in original AWR _update lines201--213.32tick segments
remain separate columns, preventing return propagation across unrelated starts.
Critic/actor minibatch step counts per NEW rollout stay identical to original,
not4x more updates. Full-rollout KL guard sees the replay dataset. Temperature,
noise/phase, optimizer states/LRs and task unchanged. This is a replay adaptation,
not an exact paper reproduction (paper uses different networks/SGD/50k buffer).
Four actual-library CPU checks pass: terminal/timeout targets, phase mask,
replay segment returns/full sampling, FIFO capacity/update-count/restoration.
All replay target recomputation and data handling counts inside wall budget.

Historical proposal to test earlier96009 is now completed; see frozen audit and
earlier-policy results above. The private dataset is uploaded and preserved.

v1 outcome: no convincing gain. PPO/AWR47/39outeriterations,168.540/165.672s
actual learning;242.985/242.779s including checks. Final perturbed noisy failures
6.907/6.532%, deterministic4.129/4.354%, noisy returns63.553/63.417, deterministic
78.958/78.054. AWR-PPO failure differences: noisy-.375pp (motion-cluster95%CI
[-1.495,.753]),det+.225pp (CI[-.525,.976]); return intervals also cross0.
Only one training seed. Initial noisy rates must be read from reports, not
assumed exactly identical; floating reset differences were below2e-4 audit bound.
Real actor delta.162513 and1560minibatch actorsteps confirmed, original critic
target equality0. Native current-rollout AWR therefore has no verified win.

Uses the already bundled, pinned upstream MimicKit AWRAgent methods for
TD-lambda targets and weighted log likelihood, temperature1 and cap20.
Source SHA71a7233a87a0df690fbcadafd4781f0de83dd3be07bd1c84913458c4b1f4f3e9.
Temperature/cap also match bundled deepmimic_humanoid_awr_agent.yaml. Its
SGD/architecture/noise defaults differ; retained checkpoint-compatible Adam
and original production noise deliberately, rather than quietly changing them.
Only existing normal-row phase supervision is added. Original actor/V/Adam
states,1.125e-6 LR, sigma.075, gamma.99/lambda.98, rollout/update counts and
full-rollout KLguard.18 remain. First real rollout asserts exact PPO/AWR critic
target equality. v1 was native MimicKit's current-rollout AWR screen, NOT the
2019 paper's long-lived off-policy replay recipe. No learned Q/dynamics model.
Two CPU checks pass against actual pinned modules: failure/timeout bootstrap
and no reset crossing; weighted-action gradient and masked phase supervision.
Primary sources read: https://xbpeng.github.io/projects/AWR/AWR_2019.pdf,
https://github.com/xbpeng/awr (commit831442fb8d4c24bd200667cbc5e458c7657effc2),
https://raw.githubusercontent.com/xbpeng/MimicKit/main/mimickit/learning/awr_agent.py.
Reason to test: both world-model and newly fitted Q derivatives damaged this
strong policy; weighted regression favors better real sampled actions without
following either derivative. It is an unproven alternative, not a claimed fix.
Normalizers/task/checkpoints/production preserved. Free compute only.

### Off-policy C51 + TD3BC v4: COMPLETE, rejected

Downloaded/analyzed/archived prophecy-offpolicy-c51-race-v4-reports and
offpolicy-c51-v4-launch.json. Warmup51.464s passed: MSE170.074vs521.765 constant,
corr.823, no actor change.115 accepted actorsteps in the following20.08s,
BC active verified; noisy failures6.306->66.366% at71.544s, det4.204->56.231%.
Early regression stop. Final repeat66.216/56.156%, actor delta.361995.
PPO at62.386s noisy6.306%, det3.829%; at240.222s noisy6.006%,det3.979%.
The final113.76/240.22s comparison is NOT equal-time evidence. No gain.
Normal rows also collapsed (47.9% noisy first check), so deterministic phase
gradients alone cannot explain the whole regression. Do not blindly continue
the phase-only idea below. Behavior regularization at published alpha2.5 did
not protect this adapter; Q fit correlation is insufficient evidence of useful
action gradients. AWR is the next structural test, not another arbitrary LR.

### Previous real-transition off-policy C51 recipe (completed)

COMPLETED `madmad74100/prophecy-offpolicy-c51-race` v4, submitted10:32UTC.
Receipt offpolicy-c51-launch.json. Two FREE T4s, ppo/c51_td3, same original119475,
task and evaluation.240s including collection/Qwarmup and checks every60s;
candidate's first check at least20s after warmup.1100s parent/1350s Kaggle bound.
STARTUP VERIFIED: bootstrap1.08s, input hashes17.54s, both workers40.88s.
Actual v4 actor updates/real evaluations verified; results above supersede this plan.
No duplicate active jobs. Existing3min heartbeat remains ACTIVE.

v4 concrete correction: TD3+BC normalized Q plus behavior regression, alpha2.5
from author's implementation, with preserved initial real data mixed50/50with
fresh replay (RLPD source default). It constrains changes from a strong pretrained
policy driven by a newly fitted action critic; benefit is UNPROVEN. Motor+used
phase actions receive BC, unused normal phase remainszero. Keep initial data
so it cannot be overwritten by quickly changing online behavior. Original task,
phase/noise, C51 setup and actorLR unchanged. Six numerical tests pass, including
reward-scale invariance and behavior gradient. Per-update BC/q_weight andrecipe
metadata must verify active use. Source papers/code read:
https://arxiv.org/abs/2106.06860
https://raw.githubusercontent.com/sfujim/TD3_BC/main/TD3_BC.py (lines128--133)
https://arxiv.org/abs/2302.02948
https://raw.githubusercontent.com/ikostrikov/rlpd/main/train_finetuning.py
This is a combination in our compatible adapter, NOT exact TD3+BC/RLPD reproduction.

Best-heldout Q fit retained: check every5s, restore critic AND optimizer, stop
fit after>=30s and15s without improvement, max90s. Gate remains MSE<halfconstant
and correlation>.6. Actual real-MuJoCo outcomes, not Q estimates or updatecount,
decide progress. Warmup/collection are inside240s; setup/baseline additionally
recorded. No reused Q/world model, shared compilation cache is declared.

v3 COMPLETE/rejected, reports downloaded/analyzed/archived as
prophecy-offpolicy-c51-race-v3-reports. At matched first-check times180.09/183.43s:
C51/PPO noisy failures99.399/6.306%, det98.423/4.054%. Normal candidate100%failed,
returns~-90. Auto regression stop;793accepted actorsteps,3rejected,1592Qsteps,
actor delta1.14007. Full PPO600.997s/130outeriterations is NOT the matched-time
comparator; use first checks above. v3 best Qwarmup passed50.89s (MSE157.984vs
368.976, corr.758); validation worsened after10s, actual actor thencollapsed.
This disproves this adaptation's benefit; not the entire published framework.
No promotion. v3 receipt retained offpolicy-c51-v3-launch.json.

v2 COMPLETE: final-fit warmup7905steps/110.685s missed gate (51.3%MSE vs50%,
corr.739), zero actor updates; reports/receipt archived as-v2. v1 phase parity
assertion stopped before candidate collection: v2 proved exact nativebatch
error0, fullbatch2.92e-6 (floating point batching). v1 receipt/rawlog retained.
Failed setup/fits are overhead, never a speedup. Do not retry the failed
unregularized v3 or count critic-only v2 as learning. If v4 fails, remaining
structural mismatch worth auditing: deterministic phase control has no phase
exploration, unlike all-action exploration in ordinary TD3; inspect evidence
before another arbitrary LR sweep. Keep current active job authoritative.

Concrete alternative after failed model-based tests: official Holosoma C51
critic on stored REAL simulator transitions, no dynamics model. Pinned commit
874f83de7b830b55f9b14fc988f694b58af88400; unmodified critic, Apache2 license and
SHA provenance in Labs/MimicKitTraining/vendor. This is a checkpoint-compatible
FastTD3-style adaptation, not a faithful whole-framework reproduction.
Original actor, fixed motor sigma.075, phase input/output and normal supervised
phase loss retained. Critic sees34 executed motors +2 deterministic feedback
phase actions, current task context/age and physical history needed by the AE
reward. Normal rows' unused phase action zero. Initial queued phase equality
is asserted; actor frozen during warmup.

Recipe: twin LayerNorm/SiLU distributional Qs1024/512/256,201atoms[-105,105],
mean Q, gamma.99,3-step targets cut at FIRST reset, timeout bootstrap uses
pre-reset state, actual failure bootstrap0; reward unchanged including-100.
Collect256ticks/262144transitions,at most90s Q warmup against real discounted returns
with old V only for final-state bootstrap. Held-out worlds gate actor updates:
MSE<half constant predictor and correlation>.6; no actor changes on failedgate.
ActorAdam3e-5 (explicit finetuning adaptation; PPO1.125e-6 unchanged), KLrollback
.18, gradnorm1/component.1. CriticAdamW3e-4,beta2.95,wd.001,batch2048;2Qsteps
per simtick, actor every2Qsteps, targetPolyak.005, targetnoise.075 clipped3sigma.
Support clipping, real actor delta, rejected steps and warmup timings recorded.
Five CPU numerical tests passed: negative/integer C51 projection, first-failure
boundary, timeout pre-reset bootstrap, official critic terminal projection and
phase-action gradients/fallback. Fixed a float32 support-spacing cancellation
in our scalar warmup projector before launch; official critic source unchanged.

Use supermimic_kaggle.py status/logs/fetch for THIS job/version. Verify real
startup and actor updates, download reports and run analyze_supermimic_pilots.py
<prophecy-offpolicy-c51-race-reports> ppo c51_td3. If Qgate fails, inspect its
record before analyzer (which correctly refuses a no-actor comparison).
Compare deterministic/noisy actual MuJoCo failures and returns at matchedwall
including warmup; no world-model prior cost here. Same compiled simulatorcache
reused by both. Setup/baseline/finaleval additionally recorded. Replicate any
promising effect on independent training seeds. Originals/production untouched,
no paid compute, existing3min monitoring remains active.

### Completed direct tracking-gradient test: rejected

prophecy-supermimic-direct-tracking v1 COMPLETE, reports downloaded/analyzed.
PPO/candidate accepted53/55 actor updates,197.380/192.752s actual learning,
311.215/309.138s budget elapsed including113.835/116.386s checks.
Perturbed noisy failures6.456% ->6.231% PPO versus7.658% candidate;
deterministic4.204% ->4.204/4.805%. Returns64.08->64.60 PPO versus64.06->60.67
candidate noisy;78.70->79.05 versus78.72->75.88 deterministic. Candidate normal
noisy failures2.098% versus PPO.524%. Actor changes and fixed directgradient
scale.387224 verified. No improvement/promotion; stronger raw-error gradients
alone did not solve H32 model-based learning. Reports verified-comparison.json
under prophecy-supermimic-direct-tracking-reports; direct-tracking-analysis.txt.
Prior326.30s model preparation further disadvantages candidate in total time.

### Previous direct tracking-gradient configuration (completed)

COMPLETED `madmad74100/prophecy-supermimic-direct-tracking` v1, submitted09:30UTC.
Receipt Saved/MimicKitSuperMimic/direct-tracking-launch.json. Two free T4 workers:
ppo/direct_h32. Original119475, original verified increment model, task and
evaluation unchanged.300s including90s real-simulator checks, existing early
regression stops,900s parent/1100s Kaggle bounds. STARTUP/ACTOR UPDATES VERIFIED:
bootstrap.85s, hashes17.15s, both workers/cache40.71s. Baselines/real reward
verified by168.25s: max reward mismatch.00014949, hard failure mismatches0;
first2captured/eager fits exactly0. By205.71s PPO11updates, candidate9accepted.
Candidate flag true and fixed calibration.387224 on actual updates; noiseRMS
~.075 verified. No learning-benefit claim before real evaluations/final report.

New discrepancy from reading SuperTrack Algorithm2/section3.5: it minimizes
tracking errors directly through the model, while our candidates differentiate
the reciprocal task reward. For error L, that derivative is attenuated by
1/(1+L)^2. Test a fixed-scale raw weighted-error gradient, calibrated ONCE to
the median reciprocal derivative on actual held-out real transitions. Preserve
the original reward FORWARD for critic targets and failure/survival derivatives;
preserve hard terminal events, critic, exploration, autoregressive phase and LR.
This is a SuperTrack-inspired gradient adaptation, NOT a faithful reproduction
of SuperTrack or SuperDyno. The original task remains the outcome criterion.
Eight CPU numerical tests pass, including unchanged forward rewards/terminal
derivatives and actual actor update through the new path. Per-update enabled
flag/fixed calibration logged and checked by the report analyzer.

Primary SuperTrack paper (read locally after download):
https://static-wordpress.akamaized.net/montreal.ubisoft.com/wp-content/uploads/2021/11/24183638/SuperTrack.pdf
Local research/supertrack.pdf and .txt. Its acceleration model, residual PD
actions, L1 loss and reference-pose input differ from our frozen policy/task;
do not present this test as reproducing its reported speedup. SuperDyno primary
paper https://openreview.net/pdf?id=FPgKt7bA8w and indexed Algorithm1 checked:
it alternates model fit and differentiable policy optimization, so the abstract
does NOT establish a PPO-plus-supervised hybrid. Full PDF currently blocked by
OpenReview browser verification; author-linked dynamics-humanoid.github.io
returns404. Continue source audit; do not invent its Eq9 or claim exact method.
FastSAC official holosoma/MJWarp remains an untested framework alternative.
Read official FastSAC paper sections2.1/2.2 and source while this job runs:
https://younggyo.me/fastsac-humanoid/static/paper/fast_sac_paper.pdf
https://github.com/amazon-far/holosoma
Pinned source commit874f83de7b830b55f9b14fc988f694b58af88400, three agent files
and Apache2LICENSE under research/holosoma-source with SHA256 provenance.
Distinct route: reuse actual simulator transitions in off-policy RL, no dynamics
model. Source uses distributional C51 critics, mean Q rather than min with LN,
n-step returns/timeouts and pre-reset bootstrap, and configurable action bounds.
Before migration, adapt C51 support to our -100 terminal rewards (cannot copy
positive-only support), handle 34motors+deterministic autoregressive phase,
preserve/check initial policy actions and count any Q warmup/setup. Paper's
15min claim is velocity tracking on4090; whole-body tests use4L40/16384envs.
Do not claim comparable result for our T4/mature checkpoint. This is NEXT source
audit candidate if direct gradients fail, not authorization to duplicate active job.
Prior326.30s model preparation and new setup remain additional costs. No paid
compute, production and original checkpoints unchanged. Existing monitor active.

### Completed world-model width test: no advantage

`prophecy-supermimic-capacity` v1 COMPLETE by09:22UTC. Shared data/validation,
initial function parity and captured/eager fitting verified.5318/3810 optimizer
steps at widths1024/2048 in360.684/360.657s. Frozen policy delta exactly0 both.
Closed-loop H32 perturbed action RMSE.133891/.138096; state NSE.054102/.059037.
Wider model3.14% worse action error and9.12% worse state error at matched time;
predeclared gate FAILED. No actor test of wider model, no promotion. Reports:
capacity-reports/verified-capacity.json and capacity-analysis.txt. Historical
configuration follows; its ACTIVE status is superseded by the result above.

### Previous world-model width configuration

User explicitly reopened investigation October23. Free Kaggle only; preserve all
production and original checkpoints. A failed candidate does not end investigation.

ACTIVE `madmad74100/prophecy-supermimic-capacity` v1, submitted09:10UTC.
Receipt Saved/MimicKitSuperMimic/capacity-launch.json. Two free T4 workers:
width1024/width2048. Original119475 policy FROZEN; same verified warm increment
model, same fresh262144 real transitions, training/held-out worlds, original
normalizers, batch256 x8 and Adam2e-4. Only dynamics width differs. Width2048
is initialized by uniform neuron duplication, outgoing-weight splitting and
cancelling asymmetry; LayerNorm statistics and initial predictions are preserved
up to roundoff. CPU test confirms prediction/input-gradient parity and that
replicas acquire different gradients/weights. Mandatory GPU initial normalized
prediction max error<=2e-5, plus captured/eager first2fit updates.

Motivation: prior H32 policy forecasts drift substantially; more fitting/bigger
batch only modestly reduced action error. Public reproduction uses3x2048
dynamics layers, ours3x1024. Capacity has not been tested. Rechecked sources:
https://github.com/zita-ch/supermimic_vibed/blob/main/supermimic/networks.py
and function-preserving transfer https://arxiv.org/abs/1511.05641 . Our
LayerNorm-aware/cancelling-split implementation is an adaptation of Net2Wider,
not the paper implementation. It reuses fitted knowledge instead of cold start.

Maximum360s fitting including60s forecast checks; same early regression stop
(two consecutive >20% worse H32 state AND action errors); parent780s/Kaggle1000s.
No actor learning. STARTUP evidence: bootstrap.70s, data1.65s, hashes71.69s,
source75.06s, pip89.91s, cache/both workers127.39s. FITTING VERIFIED09:15UTC:
initial normalized prediction max error0/3.8147e-6; dynamics2,378,838/8,951,894
parameters. First2captured/eager optimizer updates exactly equal for BOTH widths.
Initial held-out H32 policy-driven perturbed NSE.06471068/.06471076 and action
RMSE.14719599/.14719601, same292valid rows; matched initial forecasts. Both
fits advancing, no improvement claim before elapsed-time checks/final analysis.
Verify shared-data hashes in final reports; do not mistake frozen actor for failure.
Download selective reports after completion; analyze_supermimic_fit_dose.py
<capacity-reports> --capacity. Gate another actor test on >=15% lower closed-loop
H32 action RMSE than1024, no worse state NSE, at matched fitting time. Even a
passed gate is not a policy-learning/speed win; require real MuJoCo/PPO follow-up
and independent seeds. Prior326.30s preparation plus new setup/fitting count.
Existing3min monitor ACTIVE, no paid compute or production changes.

### Completed full-imagination phase-gradient isolation

`madmad74100/prophecy-supermimic-full-phase` v1 COMPLETE by09:05UTC. Selective
reports/analyzer verified:56accepted actor updates each,194.488/194.140s actual
learning coupled/detached. Phase derivative separation and motor noise verified.
Both regress from initial policy: deterministic perturbed failure4.204% to
4.955/5.030%; noisy6.456% to8.258/7.733%. Returns78.700/78.703 to75.084/74.994det,
64.052/64.097 to59.445/59.943noisy. Removing phase gradient alone is insufficient
in full H32 as well as the earlier H4 DMO test; do not repeat/promote. Reports:
full-phase-reports/verified-comparison.json and full-phase-analysis.txt.
Historical test description follows.

Submitted~08:56UTC.
Receipt Saved/MimicKitSuperMimic/full-phase-launch.json. Two free T4 workers:
phase_coupled/phase_detached. Same original119475 and verified increment model,
stochastic motor imagination sigma.075, H32, exact reward/hard forward failures,
critic and LR. Only change: stop the task gradient through predicted phase before
feeding it into later observations/targets. Actual autoregressive phase values,
normal phase supervision and task are unchanged. Seven numerical tests pass,
including exact forward equality, task-gradient removal, normal supervised
gradient retained, and actual full updater accepting the option. Previously
--stop-phase-gradient reached H4 real-forward DMO only; that failed test does not
cover this H32 freely imagined path. No claim that phase is the cause.

Public reproduction train.py keeps motion-frame/goal advancement exogenous;
our predicted phase also changes the scoring target. Source rechecked online:
https://github.com/zita-ch/supermimic_vibed/blob/main/supermimic/train.py .
This is a controlled adaptation ablation, not an exact paper reproduction.
300s budget including90s real checks; existing regression stops,900s parent,
1100s Kaggle. First/per-update phase-head gradient norm and detachment flag
recorded. STARTUP VERIFIED: bootstrap0.67s, hashes4.65s, cache23.44s, both
workers23.44s. Baselines and warm-model SHA verified132.34s; skeleton parity
.00016272. Both captured/eager model checks exactly0. Analytic score max
.00017405/.00011832 coupled/detached; hard failure mismatches0. ACTOR PATHS
VERIFIED09:00UTC: both24accepted updates at90.74/90.43training seconds. NoiseRMS
~.075 both. Coupled phase-head gradient norm38.54 versus detached.00262 (normal
supervision retained); flags verify the ablation reaches the actual update.
This proved path separation, not learning benefit. Completed analyzer used
phase_coupled/phase_detached. Final rejected results above supersede interim
progress. Original model preparation326.30s and setup remain additional cost.

### Completed stochastic full-imagination versus PPO

`madmad74100/prophecy-supermimic-stochastic-full` v1 COMPLETE by08:51UTC.
Selective reports and analyzer verified both55actual actor updates, same CP/T4,
noise RMS.074852--.075136 on every candidate update. Actual learning198.385s PPO
versus193.483s candidate (2.5% gap); setup/baseline104.65/106.59s plus parent96.47s,
prior326.30s model preparation additional. Candidate fails to improve:
deterministic perturbed failure4.204->4.955%, versus PPO4.204->4.204%; noisy
candidate6.532->6.907%, PPO6.456->6.907%. Returns candidate78.704->75.524det,
63.995->61.815noisy; PPO78.706->79.090det,64.082->63.519noisy. Candidate-minus-PPO
return motion-cluster95% intervals[-5.202,-1.929]det,[-3.540,+.105]noisy.
The noisy return difference is uncertain; the deterministic return regression
is clearer. Neither evaluation establishes improved learning.
Normal-loco returns also regress. Reject; no promotion/speedup claim. Evidence:
stochastic-full-reports/verified-comparison.json. Historical configuration follows.

Submitted08:41:43UTC.
Receipt Saved/MimicKitSuperMimic/stochastic-full-launch.json. Free T4 pair:
ppo/stochastic_h32. Same original119475, original verified increment model and
unchanged task. Fully imagined exact-reward H32 now actually samples production
motor exploration sigma.075 using reparameterized actions. Previous full-imagined
path always called ctx.policy without sampling, and model_iteration did not pass
the existing stochastic_actor flag to it. Earlier noisy-race tested the older
base update, not this free-rollout/analytic-reward path. Prior full-imagined runs
did not request the flag; their results remain valid deterministic-imagination
tests. Optional behavior only; normal phase supervision, bounds, hard terminal
events, critic, actorLR and all production files unchanged.

This hypothesis is informed by the gradient audit's different noisy/deterministic
long-horizon outcomes, not proof that noise fixes learning. Six numerical tests
pass, including the actual new path: sampled actions retain actor gradients,
actor changes, dynamics stay frozen during policy update, deterministic default
RMS0 and stochastic RMS near.075. Each live update now reports
stochastic_imagination and imagined_action_noise_rms; analyzer must verify them.
300s training budget including90s evaluations; existing real-regression stops,
parent900s/Kaggle1100s. Two real reset seeds, deterministic and production-noisy
evaluations. Use actual learning seconds excluding checks AND setup/prior model
preparation326.30s for accounting. STARTUP VERIFIED08:44UTC: BOOTSTRAP0.89s,
data1.37s, hashes50.11s, cache96.47s; both workers actually started96.47s.
ACTOR PATHS VERIFIED08:46UTC: PPO6accepted updates; stochastic H32 has4accepted
at26.70training seconds. Actual imagined noiseRMS0.074945 matches requested.075;
stochastic_imagination=true. Captured/eager first2model fits equal0; real analytic
score max0.00011790, hard failure mismatch0. Both baselines collected; initial
noisy perturbed failure6.456/6.532%, deterministic same original policy. No
outcome/gain claim was made at startup; final rejected result is above.
Completed verification used analyze_supermimic_pilots.py with ppo/stochastic_h32.
Original/production checkpoints untouched. Existing3min monitor ACTIVE, free only.

### Completed auxiliary-loss influence diagnostic

`madmad74100/prophecy-supermimic-head-fit` v1 COMPLETE by08:36UTC.
Both reports/analyzer verified: shared data/validation identical, same initial
weights, policy and world deltas0. Auxiliary/state gradient norm ratios
4.916%,2.773%,3.782%; total/state cosine.998804,.999619,.999291 on3matched
batches, identical between workers. Below predeclared5%/.995 gate; BOTH fits
skipped as designed, not a broken optimizer. Actual audit29.65/30.16s including
~24s collection/wait, plus~186s setup. This does not prove no local effects,
but does not justify another blind three-minute fit. No policy learning.
Reports head-fit-reports/verified-head-fit.json and head-fit-analysis.txt.
Optional detach hook/test retained locally; not enabled in current actor test.

Receipt Saved/MimicKitSuperMimic/head-fit-launch.json. Paired free T4 workers
coupled/detached, original119475 policy/critic frozen, original increment warm
model unchanged. First measure state, reward-head and terminal-head gradients
into dynamics on3identical real batches (256x8). Run at most180s paired fitting
ONLY if auxiliary/state gradient norm>=5% or total/state cosine<.995 on any
batch; otherwise finish as diagnostic with zero model updates. This avoids
another fit if the suspected interference is negligible. Both workers use the
same fresh replay, normalizers, initial weights and random batches. Detaching
head inputs preserves all forward losses and head-weight learning while removing
their feedback into dynamics. Policy updates remain0. CPU test verifies that
specific gradient separation and unchanged head gradients. Default behavior
unchanged, isolated experiment flag only. No production or original mutations.
Startup/actual gradient measurements verified; job complete without fitting.

Completed verification used analyze_supermimic_fit_dose.py with --heads. Source:
https://github.com/zita-ch/supermimic_vibed/blob/main/supermimic/train.py fits
state error only. Our old model_loss also propagated reward/terminal prediction
loss through imagined physical states. This is a measured-code discrepancy,
not yet evidence it causes regression. Existing3min monitor ACTIVE; free only.
Previous326.30s model preparation plus every current setup/fit remains counted.

### Completed world-model fitting dose comparison

`madmad74100/prophecy-supermimic-fit-dose` v1 COMPLETE by08:28UTC.
Both selective reports and analyzer verified, shared data/validation SHA and
initial metrics identical, policy delta0, actual model deltas20.185/15.300.
Batch256/2048:5235/1763updates in360.63/360.74s,10.72M/28.88M nominal predictions.
Final H32 closed-loop perturbed stateNSE.06373/.06438 from.09080, actionRMSE
.14585/.14628 from.15792. Extra fit improves state error~30%, action prediction
only~7.5%; larger batch provides no clear final advantage. H1 improves too.
No actor training or learning-speed win. Do not promote from the early60s lead.
Reports fit-dose-reports/verified-fit-dose.json and fit-dose-analysis.txt.
Given modest action-forecast change and prior model-quality gains that still
regressed policy, measure remaining fitting-objective discrepancy before another
blind actor sweep. Completed setup/design details follow for reproducibility.

Receipt `Saved/MimicKitSuperMimic/fit-dose-launch.json`. Two free T4 workers:
batch256 and batch2048. Original119475 policy/critic frozen; same verified
increment model. New replay seed84731 (warm-fit seed57361), shared262144
transitions, whole-world held-out split, original training normalizers frozen.
Only fit batch size differs,8-step windows/Adam2e-4. Maximum360s fitting per arm
including60s checks; stop after two consecutive >20% regressions in both H32
closed-loop state and next-action error. Parent780s/Kaggle1000s. No actor learning.
STARTUP VERIFIED: actual v1 BOOTSTRAP_STARTED0.83s, DATA_LOCATED1.41s.
API live-log timeout followed by version-correct fallback. WORKERS VERIFIED by
08:21UTC: both warm-model SHA checks220.25s, skeleton parity220.68s; batch256
collecting real replay220.69s, batch2048 waiting for that same atomic data file.
FITTING VERIFIED08:22UTC: initial held-out metrics identical; captured/eager
first2updates exactly equal for BOTH batch sizes. At60s,856/306model updates,
1.75M/5.01M nominal predictions. Initial H32 closed-loop perturbed stateNSE.09080
and actionRMSE.15792; batch256 ->.08241/.16668, batch2048 ->.06648/.15427.
This early lead did not persist in the final result above; no policy promotion.

Validation measures held-out real trajectory prediction at1/8/32steps, with both
recorded actions and unchanged policy acting on model predictions/autoregressive
phase. Recorded exploration draws reused; resets mask remaining window. Both
workers must have identical initial metrics/data/validation hashes. CPU exact-
dynamics test passes for matched exploration/reset masking. GPU checks captured
versus eager fit on first2steps. Report model delta, zero policy delta, nominal
prediction count, fitting/setup/collection times. Prior326.30s preparation remains
additional cost. Source https://github.com/zita-ch/supermimic_vibed defaults
wm_batch2048,window8,500WM-only iterations x10batches =81.92M nominal predictions,
versus our previous5.44M. Width stays1024 to isolate batch/dose from capacity.

Completed verification used analyze_supermimic_fit_dose.py. Forecast improvement
is NOT a learning win; next action is the current head-fit diagnostic above.

Additional source discrepancy verified while this fit runs (not applied): public
zita-ch/supermimic_vibed/supermimic/train.py wm_update optimizes state error only.
Our supermimic_race.model_loss still backpropagates learned reward/termination
head errors through imagined physical states, although the actor now uses exact
analytic dense reward. The heads have separate weights but their input is not
detached, so they can influence transition-model gradients. This is a concrete
remaining difference, not proof of harmful interference. If extra fit is
insufficient, measure those dynamics-gradient contributions before selecting a
state-only/head-detached fitting ablation. Source rechecked online October23:
https://github.com/zita-ch/supermimic_vibed/blob/main/supermimic/train.py .

### Completed gradient-fidelity audit

`madmad74100/prophecy-supermimic-gradient-fidelity` v1 COMPLETE by08:12UTC.
Both reports/analyzer verified:32 matched real probes, seeds91871/92719, ages8/40,
deterministic/noisy, actor updates0/policy delta0, identical checkpoint/model SHA.
Anchored actor/reward/failure reconstruction passes. Audit375.60/390.34s plus
~229s bootstrap/worker setup; prior fitting326.30s separate. Reports:
gradient-fidelity-reports/verified-fidelity.json; gradient-fidelity-analysis.txt.

H1 advice improved immediate reward on99.607/99.633% of matched valid rows
(1018/817 total), measured/predicted correlation0.966/0.963, mean+.00638/+.01018.
Local action derivative is useful on these probes. H32 free forecasts drift:
deterministic state NSE~.005-.017 atH1 to.108-.243 atH32; actionRMSE~.038-.078
to.212-.303. Noisy H32 actionRMSE.126-.258. Anchored H32 dense short return
change+.301det (motion-cluster95%CI .046,.634),+.328noisy (CI -.163,.841).
Free dense short return-.132det (CI -.485,.221),+.629noisy (CI .034,1.291).
Full-episode means anchored+.354/+.386, free-dense-.028/+.606, full-.469/+.465;
ALL full-return CIs cross zero. Full noisy failure change-.49percentage points,
motion-cluster CI[-.989,-.120]pp: a local first-action probe, not actor training or
independent learning replication. Predicted full objective includes critic/failure,
so gain6-8 cannot be compared directly with32-tick reward. Mixed results do not
prove forward drift causes policy regression; measured drift justifies a bounded
fit test. Original commands/age captured BEFORE rollout and phase derivatives
retained, correcting old probe context bug. Production/originals untouched.

COMPLETED `madmad74100/prophecy-supermimic-critic-context` v1 about07:51UTC.
Both workers/reports/analyzer verified. Original57 vs context56actor updates,
197.04/195.40s actual learning. Initial det4.204%; final4.655/5.405%.
Initial noisy6.456/6.381%; final7.357/7.282%. Noisy returns64.039/64.180 ->
60.929/61.105; deterministic78.709/78.708 ->76.031/75.120. Both regress;
critic context did not rescue learning: REJECT. Not an unnoticed disabled feature:
initial values/actor unchanged exactly; final context weights norm3.323857,
every update used matching current/next and shuffled-minibatch context.
Nine local numerical checks pass; live score max<0.00015, hard mismatch0.
This was direct imagined-value context, separate from earlier PPO context sweep.
Three-frame AE history still absent; effect not ruled out by this limited test.
Reports `prophecy-supermimic-critic-context-reports/verified-comparison.json`;
`critic-context-analysis.txt`. Production and original119475 remain untouched.

COMPLETED `madmad74100/prophecy-supermimic-critic-horizon` v1 by07:35UTC.
Both final reports downloaded and analyzer passed. H32 critic56updates/194.98s
actual learning; no-critic65/194.54s. Initial noisy failure6.456% in both;
final critic7.282%, no-critic8.258%. Deterministic4.204% ->5.105/5.180%.
Noisy returns64.050/64.070 ->61.077/58.952; deterministic78.708/78.699 ->
75.255/74.493. Both regress: reject, no policy-learning improvement. Critic-free
parameters unchanged exactly and all actor updates have value/loss0; not a false
ablation. First90s result near baseline did not persist. Source119475 intact.
Reports `prophecy-supermimic-critic-horizon-reports/verified-comparison.json`;
`critic-horizon-analysis.txt`. Read-only context audit confirmed mean reward
spread0.4754/0.4970 for counterfactual ages10/45/75 with identical physical
state/history/phase and unchanged critic value, but this does not prove causality.

COMPLETED `madmad74100/prophecy-supermimic-increment-policy` v1 about07:23UTC.
Both actors/reports/analyzer verified. PPO54updates/197.58s actual learning vs
increment86updates/193.56s. Final actual MuJoCo perturbed loco failures det
4.655% versus6.006%, noisy5.931% versus9.084%; returns78.238/72.509 and
64.705/56.609. New model still regresses despite better prediction: REJECT as
production candidate. First score parity max0.0001062, hard COM2 mismatch0;
captured/eager model fits0, no actor rejections. No learning speedup established.
Reports increment-policy-reports/verified-comparison.json; original CP untouched.

COMPLETED `madmad74100/prophecy-supermimic-increment-audit` v1,07:12UTC.
Exact shared262144transitions verified by x/a/next_x SHA. Both policies unchanged.
180.16/180.29s residual/increments fits;4388/2656updates. At60s increments improves
h8 state NSE56% and next-action RMSE36%. At180s h1 .011838/.010584,
h8 .016464/.013441, next-action .085831/.059551, critic RMSEh1 5.709/2.791,
h8 6.979/4.589. This demonstrates improved MODEL conditioning, not faster learning.
Five CPU checks and captured/eager parity0 on2GPUsteps pass. Input and delta
normalization use ONLY235776training-world transitions; held-out worlds excluded.
Model package follows zita-ch/supermimic_vibed networks.py/train.py: independent
input/output scales, body-local SO(3)/velocity increments and LayerNorm, adapted
to ball joints and our first/THIRD-column6Dencoding. Width1024/3hidden unchanged.
Double-downloaded12.06MBweights identical SHA7369ac6f091fc87e8d0e62efddd30a86687d266f676273e1885596772205f430,
loaded weights-only/all finite/norm_count checked, private dataset uploaded.
Receipts incremental model audit reports/verified-model-comparison.json and
increment-model-dataset-upload.json. Referencecostandmodelprovenance retained.

### Remaining concrete critic discrepancy

Our retained critic is evaluated on ctx.obs(x,motion,phase): physical state and
commands/phase only. Unlike our reward, it does not observe episode age, the
normal/perturbed flag, or three-frame AE history. In particular age controls AE/MSE
mix and COM2 grace, but perturbed phase is autoregressive and not an episode clock.
Public reproductions give the critic privileged reference/body errors and task
context (zita mdp.py critic_features; Cuboi REVIEW_LOG F4 documents a related
missing-reward-context issue). This is a structural ambiguity, not yet proven the
cause of model-based regression; PPO can still improve with an imperfect baseline.
Prepared read-only supermimic_critic_context.py computes exact rewards at ages
10/45/75 for identical state/history/phase and checks unchanged critic values.
Measurement now VERIFIED in both H32 arms: changing only counterfactual ages
10/45/75 changes dense reward by mean0.4754/0.4970 (p90 .7229/.7255) across
784/756perturbed sampled rows. Critic predictions change exactly0. All sampled
perturbed rows differ by>.01reward. This measures input ambiguity only; these
counterfactual states need not be equally visited at each age, and it does NOT
establish causality for observed policy regression.
Important historical evidence: October21 PPO sweep ALREADY added perturbed flag,
elapsed ticks and tracking mix with zero initial critic projection;28.19% failures
versus27.67% baseline (CP91895), no benefit. See research-20261021/audit.md and
results.md, existing loco_privileged_critic.py. Do not claim the missing-context
observation is new or repeat that PPO test. What remains untested is its direct
pathwise-value contribution with this new model. Completed H32 critic-on/off did not rescue learning; current explicit-context
comparison tests whether the existing critic can use the missing schedule. Task, policy observation and production
remain unchanged. Earlier full-imagination update ignored the DMO-only critic_weight option.
New implementation explicitly supports0/1, and tests forbid even evaluating the
critic when0. Prior runs all used1, so their behavior/results unchanged.

Additional audit correction prepared locally (not in active notebook snapshot):
reward-gradient probes sampled motion IDs AFTER the real rollout. A reset inside
that rollout could assign a new motion, so those rows differentiated the wrong
starting command. Capture motion/perturbed IDs together with the starting pose.
This affects earlier gradient-probe interpretation, not actor training (which
already takes starting IDs from replay) or held-out model prediction measurements.
The completed incremental model audit embeds the old probe; do NOT select/promote based on its
probe averages. Use held-out prediction for the gate and real policy outcomes.
Policy follow-up was selected from improved held-out prediction and failed; no claim
is based on those probe averages. Critic-context comparison subsequently failed; current gradient-fidelity audit uses corrected initial commands.

COMPLETED `madmad74100/prophecy-supermimic-heading-policy` v1. Both workers/reports
verified and analyzer passed. Global stopped early on regression:81actor updates,
142.52s actual learning. Heading100updates/194.62s learning. Deterministic failures
initial4.204% -> global7.057%, heading5.480%; noisy initial6.532/6.381% ->9.685/8.634%.
Final deterministic returns70.981/73.817, noisy56.437/57.739. Heading improves over
bad global candidate but STILL regresses from original; no learning-speed win.
Do not present unequal early-stop endpoints as an equal-time superiority result.
Both total reward parity<0.00015; model fitting/eager parity and actor deltas verified.
Prior paired fits180s/data collection/setup explicitly retained in cost accounting.
Reports `prophecy-supermimic-heading-policy-reports/verified-comparison.json`.
The analyzer now accepts either explicit prior_ cost names or paired-model names;
it still requires every component and does not treat missing costs as zero.

COMPLETED `madmad74100/prophecy-supermimic-hard-events` v1. Both workers completed
and selective reports/analyzer verified. PPO55 vs candidate118 accepted updates;
197.805/195.688s actual learning,308.43/308.38s incl checks,446.65/448.25s workers
plus58s bootstrap. Perturbed-loco deterministic failures4.279/6.982%, noisy
7.282/10.060%; returns78.868/69.421 and62.904/54.283. REJECT candidate.
Corrected total reward parity was verified (max0.00011706), with hard COM2
mismatch0. Old smooth terminal cost averaged0.943904/tick on sampled successful
transitions. Removing that forward bias stopped immediate critic-value collapse
but did NOT improve real learning; it does not explain prior adaptation failures.
Six local numerical checks/captured fit parity passed, actual actor deltas checked.
Reports `prophecy-supermimic-hard-events-reports`, analysis `hard-events-analysis.txt`.

COMPLETED `madmad74100/prophecy-supermimic-heading-audit` v1, both fits and
reports verified.262,144IDENTICAL transitions (x/a/next_x SHA match), policies
unchanged exactly.180.14/180.21s fits,4366/3884updates global/heading. Heading
state errors slightly worse (h1 .011676 vs .010241;h8 .024263 vs .021942),
next-action RMSE .080742 vs .081187, critic RMSE improves h1 3.169 vs3.939,
h8 7.338 vs9.326. Common-row action-gradient probes improve mean actual return
in5/6 settings and positive fraction in5/6, mixed at prefix70 amplitude.01.
Rows only96--424after matched-reset filtering. This supports keeping heading
model as a next candidate, NOT a policy speedup claim. Timing~286/288s audit
plus70s setup and48s bootstrap. Both reward scorers passed; no policy updates.
Reports/analyzer: heading-audit-reports/verified-model-comparison.json.

New heading model removes pelvis yaw before dynamics prediction and restores it
afterward. Width, objective, scaling and initialization unchanged; reward heads
remain world-oriented because the task directions are world-oriented. Four CPU
checks pass: rotation round-trip, nontrivial learned dynamics equivariance,
finite-difference action gradients, and finite gradients near vertical heading.
This tests representation only; public reproductions also use independent
increment normalization and local SO(3) updates, which remain discrepancies.

COMPLETED `madmad74100/prophecy-supermimic-full-imagination` v1. Both workers
finished, reports downloaded and analyzed. PPO53 vs candidate110 accepted actor
updates;196.40/193.09s actual learning,310.67/~311s including intermediate checks,
~454s total per worker excluding parent bootstrap. Candidate analytic reward
matches real replay max0.00011724/mean0.00001142, hard COM2 mismatch0; captured
model fitting/eager parity checked. Yet real perturbed-loco deterministic failures
PPO4.279% vs candidate5.255%; noisy6.982% vs9.159%. Corresponding returns78.830 vs
73.269,63.551 vs56.592. Candidate regresses from its initial4.204/6.381% failures;
reject it. No speedup claim. Both use original119475; candidate reused prior warm
world-model fitting, so that prior cost would also count in any comparison.
Analysis: `Saved/MimicKitSuperMimic/full-imagination-analysis.txt` and job reports.

The full-imagination test closed a real coverage gap: earlier exact-reward tests
used real forward trajectories with learned backward derivatives, whereas free
imagination still used a learned reward head and hard-coded batch128. The new
H16/batch1024 analytic-score package did not fix learning. This is not proof the
published method cannot work. Further audit is explicitly authorized.

Primary references: https://arxiv.org/pdf/2610.28480 ;
https://github.com/zita-ch/supermimic_vibed ;
https://github.com/CuboiLeo/SuperMimic-Reproduced . Their heading-invariant/body-
local features and independent output-increment scales differ from our generic
observation residual. Public gains are author-reported, not independently
verified here. Our task/robot, mature checkpoint, batch1024/H16 and T4 also differ
from the headline experiment. No causal attribution before controlled results.

### Tested correction: terminal-cost forward semantics

New code audit06:38UTC found a material approximation in the latest fully
imagined analytic variant: sigmoid(COM2 margin/0.05) is used as failure
probability, multiplied by100, and also discounts survival. Even exact target
velocity has p~0.00285, causing~0.285 false terminal cost per tick; a valid30deg
heading error causes~3.98. Earlier dense-reward parity checks and hard-event
classification checks did not validate this softened TOTAL reward. Earlier
real-forward/learned-backward experiments anchor actual rewards, so this does
NOT explain every prior failure, and production is unaffected.

Launched `supermimic_hard_events_launch.py` as completed v1 after heading
job COMPLETE. Compare unchanged PPO vs same full-imagination candidate with
hard COM2 events in forward rewards, survival and detached critic targets;
backward uses the existing smooth surrogate derivative (biased straight-through,
not claimed exact differentiability). Normal-row classifier unchanged. Same
original CP/warm model/batch/LR/timing as prior300s test. Six local numerical
checks pass, including no false terminal cost and retained gradients. New real
held-out check also validates total perturbed reward, and measures the old
soft terminal cost on surviving transitions. Runtime rejects score mismatch.
The launcher's previous-job COMPLETE guard prevents duplicate active jobs.
This concrete scoring discrepancy takes priority over independent normalization
for that policy test. The active heading-policy comparison is the next step;
independent incremental normalization remains a structural audit. Do not silently alter task rewards or production to obtain a better score.

### Reused model provenance / continuation

Active launcher `supermimic_heading_policy_launch.py` is the prepared follow-up,
now submitted only after hard-events COMPLETE. Models from the shared-data180s
heading audit are private `madmad74100/prophecy-supermimic-heading-pair`.
Downloaded twice with matching SHA256, loaded weights-only and checked finite.
Upload receipt `Saved/MimicKitSuperMimic/heading-pair-dataset-upload.json`;
helper `supermimic_heading_pair_data.py`. Both local weights24.56MB total.
Both fits, collection and setup costs recorded; include before speedup claims.
The current models use unchanged policy scaling; independent input/output
increment normalization (public networks.py/train.py) remains untested.

Do not conclude the entire method fails from this candidate. If heading helps,
run a longer matched PPO comparison/independent seeds. Otherwise audit/port
independent increment scaling and body-local rotation updates coherently,
instead of more blind learning-rate changes. Keep original checkpoint/policy
and task scoring/physics intact. Check startup and actual updates, not API
RUNNING alone. `supermimic_kaggle.py` status/logs/fetch supports current slug.

## Previous result: screened experiments complete, no repeatable speedup

At October 23, about 01:28 UTC, final free Kaggle job
`madmad74100/prophecy-ppo-phase-confirmation` v1 is COMPLETE. All four workers
finished normally, reports and logs downloaded, and both independent-seed
analyses passed. No experiment remains active or queued. The existing
`check-kaggle-comparison-results` heartbeat is PAUSED through the app tool.
Production trainers and original checkpoints remain unchanged. No paid compute.

The longer confirmation did not reproduce the phase-freezing screen's apparent
benefit consistently. Final actual-MuJoCo perturbed locomotion failure rates:

| Training seed | PPO, no exploration | Fixed phase, no exploration | PPO, production exploration | Fixed phase, production exploration |
| --- | ---: | ---: | ---: | ---: |
| 92719 | 4.0541% | 3.7538% | 7.6577% | 6.6817% |
| 38147 | 3.9790% | 4.3544% | 6.2312% | 6.2312% |

Each cell contains 1,332 perturbed locomotion episodes. These cover the full
120-tick task. Normal-motion checks cover only 120 of 300 ticks; they do not
establish full normal-motion safety. Original checkpoint 119475 starts every
worker, with two T4s running each pair concurrently and treatment/GPU assignments
swapped for the second seed. No warm start from the best experimental policy.

Candidate-minus-PPO failure differences, with paired motion-cluster 95% intervals:
seed 92719 deterministic -0.3003pp [-1.2782, +0.5247], noisy -0.9760pp
[-2.0990, +0.1504]; seed 38147 deterministic +0.3754pp [-0.6006, +1.5060],
noisy 0pp [-1.1345, +1.1994]. These intervals describe evaluation variation,
not confidence across training seeds. None establishes a failure-rate advantage.

Returns corroborate the inconsistent outcome: PPO/fixed phase deterministic
79.353/79.708 and noisy 62.074/63.789 for seed 92719; deterministic 79.378/78.566
and noisy 64.579/64.428 for seed 38147. The first seed's noisy return difference
interval narrowly excludes zero [0.0105, 3.3033], but the second does not repeat
it [-1.8809, 1.5082]. Normal noisy failures are worse for the candidate in both
repeats: 0.8741/1.5734% and 1.3986/1.5734%. Those differences remain uncertain.
Idle return changes are mixed across seeds; zero idle failures cannot measure
pose quality. Do not select a favorable intermediate evaluation as the result.

Before-to-after comparisons also retained: seed 92719 starts at PPO/fixed
deterministic 4.2793/4.1291% and noisy 6.3063/6.4565%; both finish worse than
their own noisy start. Seed 38147 starts at deterministic 4.2042% and noisy
6.3814% in both arms. PPO deterministic improves to 3.9790%; fixed worsens to
4.3544%. Both noisy rates improve slightly to 6.2312%.

Actual learning and accounting, PPO/fixed phase respectively:
- Seed 92719: 132/128 updates, actor parameter L2 change 0.160159/0.159222,
  learning 488.16/485.02 seconds; 600.61/600.63 including intermediate checks;
  setup+baseline 104.39/105.05; total worker 742.32/743.98 seconds.
- Seed 38147: 130/130 updates, actor L2 change 0.159951/0.157848,
  learning 487.95/488.14 seconds; 601.45/602.52 including intermediate checks;
  setup+baseline 66.68/66.95; total worker 706.11/707.49 seconds.
- Parent completed both pairs at notebook second 1582.30, including approximately
  107 seconds before the first workers. No model fitting was used by this test.
  Reused compilation caches are recorded; this is not a cold-start speed claim.

All actors and critics actually changed. Fixed predictor parameter delta and
deployed fixed-probe drift were exactly zero. Live PPO phase drift RMS was
0.00412/0.00485 cycles across the two seeds. The shared phase-controller drift
mechanism exists, but these trials do not establish it as a cause of slow learning.

Reports: `Saved/MimicKitSuperMimic/prophecy-ppo-phase-confirmation-reports/`,
including four `result.json` files/logs, `verified-comparison-seed92719.json`,
`verified-comparison-seed38147.json`, and `verified-confirmation.json`.
Analyzer: `analyze_supermimic_phase_confirmation.py`; it labels cross-arm final
comparisons separately from within-arm before/after learning. Receipt:
`Saved/MimicKitSuperMimic/phase-confirmation-launch.json`.

Decision: retain production PPO. Close the tested SuperMimic-inspired variants,
derivative-model refinement, advantage-cap change, and fixed-phase follow-up
without promotion. Local model/gradient improvements did not become repeatable
policy-learning gains. This is not a disproof of SuperMimic or a claim to have
exhausted all RL methods; the adaptation is not the authors' complete framework.
The next distinct research branch would be an off-policy learner such as
FastSAC/FastTD3, already researched but not implemented or ruled out here; it
requires its own replay/critic integration and fair protocol. No such job is
queued. Do not automatically relaunch this completed sweep.

## Completed: phase-predictor stability screen v1, mixed

madmad74100/prophecy-ppo-phase-stability-race v1 COMPLETE around00:59UTC.
Version-correct live logs verified bootstrap, baseline and both actual updates;
both workers finished normally. Reports fetched and analyzer assertions passed.
50updates BOTH, actor L2 changes.101764/.102921; critic5.46547/5.44275.
Actual learning192.93/194.94s; budget incl checks308.46/312.10s;
checks115.53/117.16s, setup+baseline106.06/106.72s,total workers453.06/457.91s.
Parent bootstrap additional~92s. No model fitting used.

PPO / frozen phase final deterministic perturbed-loco failures4.1291/3.5285%
(55/47 of1332), versus initial4.2042% both. Difference-.6006pp, motion-cluster95%
CI[-1.2841,0.0000]; return78.981/79.657, difference CI[-.3685,+1.8874].
Frozen before-to-after failures-.6757pp CI[-1.3414,-.0750], but this does NOT
establish advantage over PPO across training seeds.
Final noisy6.0811/6.2312% (81/83), versus initial6.4565/6.5315%. Difference+.1502pp,
CI[-.9717,+1.3494]; returns64.707/64.260, difference CI[-2.2120,+1.2043].
First93s noisy5.48% candidate versus6.91% PPO did not persist. Do not cherry-pick it.
Normal loco failures det.3497/.1748%, noisy1.3986/1.0490%; no established regression.
Idle tradeoff: deterministic perturbed-idle return79.634/78.015, difference
CI[-2.338,-.927]; normal-idle117.204/116.810, smaller but consistent decline.
Noisy idle return81.975/81.746. Zero idle failures cannot measure idle quality.
All intervals cluster evaluation motions, NOT independent training seeds.

Actual phase drift on fixed observations confirmed: live PPO RMS.004293cycles,
p95.006295,max.059872. Candidate's deployed frozen predictor drift and parameter
delta exactly0; its unused live phase head RMS.002810. This confirms the
mechanism exists, not that it explains slow learning. Autoregression retained.
Reports Saved/MimicKitSuperMimic/prophecy-ppo-phase-stability-race-reports/verified-comparison.json.

Screen configuration: original119475,1024worlds,noise.075,actor LR1.125e-6,
advantage cap4 in both arms. Reward/failure settings and normal phase supervision
unchanged.22CPU checks plus actual GPU invariants passed.

This preserves autoregression: predictor still reads current physical pose and
previous phase every tick. Only its weights are fixed; no authored clock.
The copied actor trunk+phase head is separate from motor learning; live model's
normal-row phase supervision is unchanged. Feedback for normal rows is bitwise
preserved after the queue operation. All reward weights, failure rules, noise,
PPO clipping and KL guard unchanged. This tests a different phase controller,
so lower MSE alone cannot establish better behavior; prioritize real failures
and returns, including normal-motion regression checks.

Evidence: frozen source omni_policy.eval_phase shares _actor_layers with motor
outputs, but autoregressive rows are excluded from phase supervision and phase
is outside the Gaussian-action PPO likelihood/KL. This was already identified,
not tested, in Saved/MimicKitLocomotion/research-20261021/audit-followup.md.
The SuperMimic primary paper https://arxiv.org/pdf/2610.28480 separates goal g_t
from motor action a_t; it does not establish that freezing OUR phase predictor
helps. This is a task-specific inference to test, not a claimed paper result.
Prior phase-gradient ablation detached analytic gradients through phase, but
DID NOT stop shared-weight changes from changing the deployed phase predictor.

Code supermimic_phase_stability.py.22CPU tests pass: initial output parity,
normal-row passthrough, unchanged action object/RNG/original model state layout,
constant copied weights, current-pose feedback and angular wrap metrics. Both
arms measure live predictor drift on the SAME fixed observations captured before
learning; candidate uses its frozen copy, whose parameter delta must remain0.
Captured original predictor saved beside experimental checkpoint for reproduction;
do not load that policy alone as a deployed candidate. Production untouched.
Use supermimic_kaggle.py phase-stability-race to launch, then version-correct logs,
status and fetch. Analyze analyze_supermimic_pilots.py with arms ppo frozen_phase.

## Completed: advantage cap4 versus10, no verified learning gain

madmad74100/prophecy-ppo-advantage-cap-race v1 COMPLETE, fetched00:44UTC.
Both actual actors updated:54/52updates, actor L2 changes.10731/.10485.
Actual learning195.72/197.24seconds; including intermediate checks307.50/311.17s;
setup+baseline104.66/104.98s and total workers449.65/454.09s. No model fitting.
Both start deterministic4.2042%, noisy6.4565% failures. Final deterministic BOTH
4.0541%. Final noisy cap4=7.4324% (99/1332), cap10=6.9069% (92/1332).
Cap10 minus cap4 difference-.5255pp,95% paired motion-cluster CI[-1.3494,+.3035].
Noisy returns62.459/63.413, difference CI[-.3680,+2.1666]. Both noisy results
worse than start, so seven fewer failures does NOT establish faster learning.
Normal noisy failures.874/1.224%; perturbed idle returns slightly worse cap10.
Intervals concern evaluation motions, NOT independent training seeds. Normal
checks truncated120/300ticks; perturbed full120. No promotion, cap4 retained.

Reports Saved/MimicKitSuperMimic/prophecy-ppo-advantage-cap-race-reports/verified-comparison.json.
Actual clipping hypothesis confirmed numerically, but benefit unproven: first
batch cap4 removed48.86% of terminal negative normalized actor-advantage mass,
19.62% across all negative advantages. This does NOT reduce the stored -100
reward or critic targets. Percentages vary across later batches; do not generalize
49% as an all-training measurement.21CPU tests and frozen upstream smoke check
verified target parity, zero failure bootstrap and RNG preservation. Native
runtime asserted recomputed advantages match upstream on every update.

Primary sources: https://arxiv.org/abs/1707.06347 and official RSL-RL
https://raw.githubusercontent.com/leggedrobotics/rsl_rl/main/rsl_rl/algorithms/ppo.py.
Q-Prop not added blindly: ICML2018 Mirage paper
https://proceedings.mlr.press/v80/tucker18a/tucker18a.pdf and author code
https://github.com/brain-research/mirage-rl show reported continuous-control
gains depended on biased asymmetric normalization. PIPPS
https://proceedings.mlr.press/v80/parmas18a/parmas18a.pdf motivates caution about
long pathwise derivatives but does not prove chaos explains our results.
Prior October21 critic-context trial28.19% versus baseline27.67%, no win; no
new duplicate critic-context/control-variate GPU run launched.

## Completed: objective-component audit v2, no single defective term isolated

madmad74100/prophecy-supermimic-objective-audit v2 COMPLETE around00:19UTC.
Exact session361283766; original actor/critic and derivative model frozen,
policy parameter delta exactly0. Deterministic/noisy workers300.15/324.02seconds
plus setup. Two reset/noise seeds91871/92719, prefixes8/40. Each tests dense,
dense+critic and full model gradients with +/-0.01 RMS action change for ONE
tick, then unchanged policy through120ticks in real MuJoCo. Same valid rows
within each comparison. Reward reconstruction<.000254, means<4.8e-7, hard
failure mismatches0. Reports objective-audit-reports/verified-objective-comparison.json.

No component wins consistently. Early noisy seed91871 mean real discounted
return difference (+direction minus -direction) is -.477 dense, +.279 with
critic, +.767 full. Seed92719 is +.360, -.031, +.154. Later prefix40 differences
are small/mixed. Local direction success mostly44-59%, much weaker than short
horizon dense-only probes. Removing the failure term is NOT supported. Paired
motion-cluster intervals mostly cross0; these are NOT independent training-seed
intervals. Strict matching leaves only81/98 valid noisy prefix40 rows. No policy
training or learning-speed inference from this diagnostic.

Monitoring correction: live_logs saved ALL events but printed a whitelist that
hid OBJECTIVE_AUDIT. Healthy v1 was unnecessarily canceled after8m25s (session
361281744), not stalled; raw JSON contains26 audit events. v2 was NOT canceled.
The reader now prints unfiltered nonempty tails, regression-tested. v2's stage
watchdog did not fire. Preserve this correction; do not cite v1 as runtime failure.

## Completed: derivative policy pilot v1 -- no learning-speed win

madmad74100/prophecy-supermimic-direction-policy-pilot v1 COMPLETE, fetched and
analyzed23:55UTC. Native PPO53updates/model47; actual learning197.30/198.12sec,
checks113.76/109.49sec. Actor parameter changes0.103765/0.037310; model delta0.
Noisy perturbed failures6.381->5.931% PPO versus6.532->5.931% model; equal final
failure rate, paired95% motion-cluster interval model-minus-PPO[-.897,+.898]pp.
Noisy returns64.192->64.691 PPO,63.980->64.300 model. Deterministic failures
4.204->3.829 PPO versus4.204->4.429 model; returns78.717->79.460 versus
78.704->77.885. Model-minus-PPO return CI[-2.764,-.419]. Normal noisy returns
also worse model69.174 versus PPO69.992. No promotion; don't raise LR to mask
worse action directions. These CIs cluster evaluation motions, NOT independent
training seeds. Normal evaluation truncated120/300ticks; perturbed complete120.

Reports: Saved/MimicKitSuperMimic/prophecy-supermimic-direction-policy-pilot-reports/
verified-comparison.json. Model reused180.28s fitting +23.75s collection +65.40s
worker setup +53.63s parent setup =323.05s minimum prior preparation; NOT a free
end-to-end tie. Prior fit SHA9603ba8b99a84891be01082d10881d22b396b0d988a33b465bde869e1012a8e3.

Previous KL hypothesis remains UNVERIFIED: logged model KL .0001-.0004 versus
PPO .005-.01 use different samples/aggregation. No common observation measurement
or larger-LR test done. The adverse real-return result makes objective-component
validation more useful than increasing the step size. Production/checkpoints intact.

## Completed: direct derivative supervision, v1

madmad74100/prophecy-supermimic-direction-model-audit v1 COMPLETE23:44UTC.
Identical shared data/pair hashes, zero actor/critic parameter changes.18CPU
checks plus actual structured JVP/finite-difference/parameter-gradient checks;
first two captured GPU Adam updates identical to eager for BOTH models.
Same180s fitting residual/directional:4382/3474updates; H1 state error
.011781/.011251, H8 .021454/.026915, next-action RMSE .083891/.075230.
Held-out directional-change MSE .025500/.019317 (24% lower); next-action
error10% lower. H1/H8 critic errors3.106/5.819 and10.401/12.787 (worse).
Common real-MuJoCo action probes: positive fractions for prefix8/40/70,
amplitude.01:58.95/63.96%,63.69/69.43%,66.35/85.58%; amplitude.04:
63.16/71.53%,78.57/77.98%,81.65/88.07%. Median return changes better in all6.
Mean real changes better in5/6; early prefix8,.04 worsens-.201->-.386 due
failure costs. Therefore promising SMALL local directions, not permission for
larger policy steps or a verified learning speedup. Same policy throughout.
Total audits285.41/287.72s +65.40s worker setup +53.63s parent setup. Neighbor
preparation.157s. Data collection22.91/23.75s. Reports and verified comparison:
Saved/MimicKitSuperMimic/prophecy-supermimic-direction-model-audit-reports/.
Training/heldout median standardized neighbor distances6.08/7.02 across180
coordinates,95th percentile12.71/13.56; these are approximate local targets.

Primary sources read before this change:
- DDPPO, ICLR2022: https://openreview.net/pdf?id=rzvOQrnclO0
  Author implementation https://github.com/CCreal/ddppo, commit
  d0650900a0bd706780c547348a47c0b47b9c2c9f; model_regular_on_jacobian.py lines
  227-332. It supervises model Jacobian times nearby-input displacement against
  the corresponding real next-state displacement, with weight_grad_loss=10.
- MB-MIX, AAAI2025: https://arxiv.org/html/2503.01178v1 section3.3 directly
  supervises state/action derivatives from a differentiable simulator. Our
  wrapper lacks these derivatives, so the DDPPO transition-pair method is the
  concrete next test. Do not claim this is full DDPPO or MB-MIX.

Plan: ordinary structured-model fitting versus the SAME objective plus
10x directional-change MSE. Exact torch.func.jvp avoids materializing all146
output Jacobians; gradients backpropagate into model parameters. Neighbors:
8192 training anchors, five nearest neighbors each; separate2048 held-out
anchors/worlds. Distance standardized using training-only statistics; derivative
and target use original model units. Same shared262144 real transitions,
identical initialized model, frozen original actor AND critic.180s fitting per
arm,60s regression gate, existing real H16 MuJoCo probes. No actor run unless
physical/action prediction and real directions support it. Include pair
preparation/setup/fitting in any eventual learning-speed claim. This changes
the derivative supervision itself, closing the unsuccessful value-weight search.

## Completed: value weighting plus ordinary MSE, v3

`madmad74100/prophecy-supermimic-value-model-audit` v3 COMPLETE, fetched/verified
23:22UTC; archived under Saved/MimicKitSuperMimic/
prophecy-supermimic-value-model-audit-v3-reports/. Combined objective rejected.
Unweighted/combined120s:2937/2964updates; H1 state error .01835/.03365,
H8 .02333/.03568; next-action RMSE .09961/.10878. Critic RMSE H1 4.373/4.026,
H8 8.807/7.677. Shared data hashes match; policy parameter delta exactly0.
Both first two captured Adam updates match eager exactly. Total audit229.80/
231.16s plus69.39s worker setup and29.85s parent setup. No policy improvement.
Common valid real-MuJoCo action probes (prefix8/40/70, amplitude.04):
positive-return-change fractions64.45/57.11%,79.52/71.69%,76.53/76.53%; mean
actual return changes +.00796/-.40743, +.15411/+.10574, +.19638/+.14339.
At amplitude.01 results likewise offered no consistent benefit. Dense-reward
probes omit critic bootstrap/failure derivatives; actual measured returns include
hard failure costs. This is a model diagnostic, not a policy-learning race.
No promotion; stop trying minor variants of value-gradient weighting.

## Completed: corrected value-gradient audit v2

`madmad74100/prophecy-supermimic-value-model-audit` v2 COMPLETE, fetched and
verified23:14UTC. Same dataset/weights, both policies exactly unchanged.
120s residual/value-weighted:3009/2943updates; H1 state error.01677/.06811,
H8 .01998/.09790; action RMSE.09728/.12820. Critic RMSE improved5.291->2.997
atH1 and5.587->3.903 atH8 (43%/30%), but at the cost of much worse physical
predictions. Weighted model fails existing.05accuracy gate, so simulator probes
skipped. This tradeoff motivates v3's existing add_mse option, not a learning-win
claim. Total audits225.21/147.65s plus66.47s worker setup+23.61s parent setup.
Reports Saved/MimicKitSuperMimic/prophecy-supermimic-value-model-audit-v2-reports/.

v2 setup: submitted23:07:40UTC; startup0.79s, hashes6.16s, pip21.03s, workers
23.61s, real data122.13s. Both first two captured updates matched eager exactly.
Free two-T4 comparison, original119475 policy AND critic frozen; same exact shared
262,144-transition dataset and identical fresh residual model initialization.
Residual unweighted versus VaGraM-inspired critic-gradient-weighted state errors.
120seconds fitting each, then held-out predictions, original critic-value errors
and H16 dense-reward real-MuJoCo action probes. No actor training yet. Parent900s
watchdog/Kaggle1100s timeout. Original checkpoints/production untouched.
Analysis command (current download folder; archived versions have own folders):
`analyze_supermimic_models.py Saved/MimicKitSuperMimic/prophecy-supermimic-value-model-audit-reports residual value_weighted`.

v2 correction: differentiate critic THROUGH the existing skeleton projection,
removing impossible hinge-constant changes and folding key-position sensitivity
into joint coordinates. v1 weighted fitting failed badly. Local CPU inspection
at normalized mean found the16 elbow/knee constants dominate squared gradient;
this point is not a real rollout, so v2 also measures the fraction over its full
real-transition dataset. No change to the original actor/critic/normalization.
Full-data diagnosis CONFIRMED:99.94493% of ambient squared critic derivatives
fall on the16 constant hinge coordinates. After projection that fraction is0,
95th percentile gradient norm28.67 versus v1 2342.35; weight normalization.8674
versus8192.49. Projection changes recorded states by at most3.04e-5 normalized
units; weight calculation1.56s. Initial weighted MSE.05735 versus ordinary.13349
(v1's near-zero state loss is gone). This diagnoses experimental weighting;
it does not establish a production PPO fault, since fixed coordinates never vary.
Logs include ambient/reachable constant-gradient energy and projection error;
abort if projection alters targets by>.01 normalized units.16CPU tests pass,
including constant-gradient removal, dependent-coordinate chain rule, and units.
Added model-level early stop after60s if single-step error has not improved5%
and next-action predictions have worsened. No actor pilot unless useful errors
improve; poor fits skip simulator probes. Reports v1 archived separately.

v1 COMPLETE, fetched/analyzed23:05UTC. Same data, zero policy delta,300s fits.
Unweighted/value-weighted H1 error.009695/.18530; H8 .01535/.50820; next-action
RMSE.07293/.27432; critic RMSE H1 4.695/16.381, H8 6.416/36.285. Weighted arm
skipped probes due poor accuracy. Unweighted7406steps, weighted7429; respective
total audits404.87/326.61s plus63.85s worker setup+97.51s parent setup. Weight
normalizer8192.49 while weighted initial error~6e-6 versus ordinary.13066 led to
the constant-coordinate diagnosis. Full results:
Saved/MimicKitSuperMimic/prophecy-supermimic-value-model-audit-v1-reports/.

Why another test after the architecture audits: this changes the model-learning
OBJECTIVE, not another LR/horizon/activation variant. Models still distort the
policy's next action by roughly its original exploration scale, and accurate
coordinates alone have not yielded useful policy updates. VaGraM directly
prioritizes state dimensions to which the current value function is sensitive.
Read paper and official source before implementing:
https://arxiv.org/abs/2204.01464
https://raw.githubusercontent.com/pairlab/vagram/main/mbrl/models/vaml_mlp.py
https://raw.githubusercontent.com/pairlab/vagram/main/mbrl/examples/conf/dynamics_model/vaml_ensemble.yaml
Adaptation: squared coordinate error weighted by squared gradient of our ONE
frozen PPO state-value critic (paper uses four SAC critics). Gradient norms
clipped at training-world95th percentile, weights normalized by ONE fixed global
training mean to preserve the old state-loss scale. No per-sample normalization,
no held-out statistics, no critic gradients during fitting. Compute/cache weights
once in shared data. Model and reward/termination losses otherwise unchanged.
Both arms log h1/h8 critic RMSE plus state/action prediction errors. Saved data
hashes AND value-weight hashes must match.15CPU tests pass, including training-only
clipping/scale and actual weighted-gradient effect; scripts compile. Captured fit
must again match eager first two updates per model. This is not full VaGraM.

Next: inspect real action probes on common valid rows. A substantial reduction
in critic error without worse real dense-reward directions can justify ONE
bounded real-critic actor pilot, preserving original exploration and using real
failure/return checks. Dense-reward probes omit bootstrap, so they alone cannot
prove or disprove the value-weighting benefit. Include300s fitting/setup when
counting total cost (v2 uses120s). If no improvement in relevant metrics, close this batch of
experiments rather than keep small model variants running. No tested method has
reliably beaten PPO; no experimental policy has been promoted. Heartbeat active.

## Completed: PWM-inspired regularization audit

`madmad74100/prophecy-supermimic-smooth-model-audit` v1 COMPLETE and fetched/
verified22:51UTC. Both trained on identical data; policy parameter delta0; exact
scoring passed. Fresh300s fits: residual7418updates, regularized7215. H1 state
error0.01228/0.01430, H8 0.01964/0.02045, next-action RMSE0.07671/0.08195.
Regularization did not improve prediction or show broad action-gradient gains.
Common valid H16 probes, residual/regularized positive fractions, prefix8/40/70
with amplitudes.01/.04:64.5/66.3%,63.8/65.9%;69.3/68.1%,76.2/75.6%;70.6/73.5%,
78.0/84.6%. Common counts392/414/163/172/102/91. Early .04 mean reward changes
negative for BOTH because of discrete failure costs. Later improvement is not
consistent across states; no basis for promotion or a learning-speed claim.
Total audit403.86/407.01s +worker setup61.86s +parent setup60.49s. Includes
22.5/23.4s recording/wait,300s fitting and gradient audit. No policy updates.
Report folder: Saved/MimicKitSuperMimic/prophecy-supermimic-smooth-model-audit-reports.

Source was author PWM code9816252019ad8ca9a4393bceacf8a4dde711a749,
models/mlp.py and pedagogical/ball_wall.py, not the full latent-space algorithm:
https://github.com/imgeorgiev/PWM
Same linear initialization, LayerNorm/Mish/SimNorm(8) on hidden layers only.
This finished the simple integration/regularization architecture comparisons.

## Completed: shared-data integration audit v3

`madmad74100/prophecy-supermimic-integration-audit` v3 COMPLETE, downloaded and
verified22:34UTC. Reports archived in integration-audit-v3-reports. Dataset hashes
identical, policies exactly unchanged, exact scoring passed both.180s fitting:
residual4319updates versus integrated3542. H1 normalized state error0.01209/
0.01164; H8 0.02210/0.02072; next-action RMSE0.08732/0.08154. Small prediction
improvement, not a learning result. Common matched H16 action-probe positive
fractions (residual/integrated), prefixes8/40/70 and amplitudes.01/.04:
61.3/65.9%,66.7/66.4%;67.3/71.6%,80.0/78.9%;72.5/75.2%,77.6/86.9%.
Common samples416/411/162/175/109/107. Mixed gains, many unusable directions,
not enough for a confident architecture verdict or production change.
Reports also preserve each arm's full retained-row means and common-row results.
Real prefix rollouts can diverge numerically, so unmatched rows are excluded;
these probes are a local diagnostic, not whole-policy performance evidence.
Total audit286/287s plus~72s worker construction and~100s parent setup; includes
recording and fits. No actor updates. No speedup established.

v2 used separately simulated datasets that diverged despite same seeds; it is
exploratory only. v1 canceled after5min setup stall; stage logs and pip180s bound
were added. v3 fixed dataset comparability. Exact-critic/PPO race also complete:
noisy failures6.907/7.207%, experimental return lower; difference inconclusive.

## Previous: model integration audit v2 (complete)

COMPLETED JOB: `madmad74100/prophecy-supermimic-integration-audit` v2, submitted
October22 22:15:57UTC. v2 startup VERIFIED0.91s, inputs found1.37s, hashes
verified47.93s, source copied50.04s, pip completed71.61s, cache restored/workers
started91.04s. No fit result yet as of22:17:44UTC. v1 printed BOOTSTRAP_STARTED at1.04s but no workers/setup
completion through five minutes. Cancellation requested via exact Version1 UI
(session361265264) at22:15:03UTC; API confirmed CANCEL_ACKNOWLEDGED before v2.
Do not duplicate v2. Retry adds setup-stage logging and
180second pip timeout. Browser status initially failed to fetch (Firebase error),
but Version History cancellation succeeded. Exact-critic-race v1 COMPLETE,
downloaded and analyzed. New audit:
two free T4s, original119475 policy frozen, same256ticks of original noisy
transitions, fresh identically initialized MLPs,180seconds model fitting per arm.
Residual-observation versus explicit velocity integration with learned pose
corrections. Ball-joint local rotations, world root rotation and COM-to-origin
height handled explicitly; prediction dt1/30, actual physics240Hz unchanged.
Compare held-out1/8tick errors and next-action error before H16 real-gradient
audit. No actor training until model evidence supports it.13CPU tests passed,
including SO(3) derivative at zero and COM-height preservation. Existing schedule
continues; do not duplicate a job after launch. Original/production untouched.

Exact-critic race result: PPO53updates/310.89s, exact42/309.79s including113.91/
112.31s checks; actual learning196.97/197.48s. Actor deltas0.10551/0.03325;
critic deltas5.5023/6.5370. Noisy perturbed failures7.207/6.907%, mean returns
63.031/62.548; deterministic4.429/4.279%. Experimental-minus-PPO failure change
-0.300pp, motion-cluster95% interval[-1.499,+0.977]pp; normal noisy0.699/1.224%,
normal return70.243/69.429. No reliable improvement. One training seed,120tick
checks only; no promotion. Reports and verified-comparison.json saved under
Saved/MimicKitSuperMimic/prophecy-supermimic-exact-critic-race-reports.

Next: inspect model audit. An improved prediction metric alone is not learning;
require actual action-gradient evidence before a bounded actor pilot, then a
matched PPO comparison and independent seeds if promising. Reject regression.
Source inspected online and locally:
https://github.com/CuboiLeo/SuperMimic-Reproduced/blob/main/src/supermimic/world_model/state_spec.py
This is an independent reproduction, not the official SuperMimic implementation.
PWM also motivates checking gradient usefulness separately from prediction MSE:
https://policy-world-model.github.io/media/pwm.pdf

## Previous: exact-score real-critic versus PPO race (complete)

COMPLETED JOB: madmad74100/prophecy-supermimic-exact-critic-race v1, submitted
October22 21:57:25UTC. Two free T4s,300seconds each including fixed90second
deterministic/noisy120tick checks. `ppo` uses unchanged original PPO/Adam state,
actual actorLR1.125e-6. `exact_critic` uses H16 real-forward/learned-backward,
exact dense reward, analytic COM2 failure gradient, no extra phase-reward
gradient,512fresh starts across16ticks, same actorLR. Fits a critic from actual
8tick transitions with correct failure/timeout accounting and EMA target;
critic bootstrap is enabled (weight1). Online world fitting resumed. Original
119475 checkpoint/warm model preserved; production untouched. Early regression
stops retained; verify both actor and critic parameter changes at completion.
Startup VERIFIED0.637s, cache restored51.5s, baseline/setup160s. Both actual
update paths VERIFIED: PPO11updates by39.7budget seconds; exact-critic6updates
by40.9s, real-critic fit loss1.138, exact-forward error0, mean error<1.2e-6,
COM2 error<6e-6, zero failure-class disagreement. No outcome verdict yet as of
October22 22:01:41UTC /October23 00:01:41Warsaw. The overnight10minute heartbeat
is ACTIVE and must continue from this job, without duplication.
Use logs/status/fetch; analyze_supermimic_pilots.py with arms ppo exact_critic.
Warm-model fitting is reused and must be included before claiming total cost
improvement; these are adaptation tests, not an official SuperMimic reproduction.

Phase-gradient pilots COMPLETE and analyzed. Extra phase derivative confirmed
(first phase-head grad norm1.669 vs0.001924), but detaching did NOT fix learning.
Backprop/detached accepted113/101updates in241.21/218.19s (detached stopped early
for normal-loco regression). Final noisy perturbed9.685/8.859% vs6.306/6.456%
initial; normal8.392/7.692%. Actor deltas0.08572/0.08193; model deltas0. Both
rejected. This rules out the extra phase gradient as a sufficient explanation;
do not describe it as the discovered cause or deploy a phase change.

Next decision: verify actual MuJoCo outcome versus native PPO at matched elapsed
times. If this full-return candidate improves, validate longer with independent
training/evaluation seeds and300tick normal episodes. If it fails, stop arbitrary
LR/horizon variants: remaining useful work is a better model/gradient audit
(e.g. the independent reproduction's compact state and integrated dynamics),
or a clear negative result for this adaptation. Research/read primary code
before choosing; preserve the original run. Existing10minute heartbeat ACTIVE.
Primary implementation detail inspected locally: independent reproduction's
src/supermimic/world_model/state_spec.py integrates updated velocities, then adds
learned position/rotation corrections; it is NOT strictly velocity-only. Its
zero-output prior is constant velocity; our current residual-observation model's
zero-output prior is unchanged pose despite nonzero velocities. This is a concrete
architecture difference worth testing only if the current full-return race fails.
Any adaptation must use our30Hz control interval, preserve240Hz actual physics,
and handle our ball joints/COM-to-origin velocities; do not copy G1 hinge-only
dimensions or its50Hz interval. Fit with frozen original policy, validate heldout
states and real action-direction effects before spending on actor learning.
Source: https://github.com/CuboiLeo/SuperMimic-Reproduced/blob/main/src/supermimic/world_model/state_spec.py

## Previous: phase-gradient pilots

COMPLETED JOB: madmad74100/prophecy-supermimic-phase-gradient-pilots v1, submitted
October22 21:48:30UTC. Two free T4s, original119475 policy and fixed audited warm
world model. H4, LR1.125e-6,2048fresh starts across8ticks, exact dense reward and
analytic COM2 failure derivatives, no critic bootstrap.240seconds incl90s checks.
`phase_backprop` is the previous BPTT behavior; `phase_detached` uses identical
actual autoregressive phase/target values but stops the task-reward derivative
through phase. Both retain original normal-row phase MSE. This tests a concrete
PPO/BPTT difference verified in the frozen source.zip, not a changed simulator
task. First update logs phase-head gradient norm; frozen-model delta must stay0.
Startup VERIFIED1.008s, cache restored92.6s, baseline/setup208s. Both actual
actor updates VERIFIED at216.25notebook seconds: accepted1, forward error0,
mean mismatch<2e-6, COM2 error<5e-6, zero failure-class disagreements. First
phase-head gradient norms1.669 (backprop) versus0.001924 (detached, normal-row
supervision only). Different sampled training states mean the ratio is diagnostic,
not a matched causal effect size. First outcome check pending. No production
change. Monitor logs/version and policy updates, fetch results and
analyze_supermimic_pilots.py with arms phase_backprop phase_detached.

Frozen-model v1 COMPLETE. Refitted/frozen:81/103actor updates in241.52/241.06s,
including77.13/80.16s checks. Verified world-parameter deltas6.9688/0.0; actor
deltas0.06027/0.07856. Noisy perturbed failures6.53->8.26% /6.46->10.36%; noisy
returns58.49/53.57. Frozen normal noisy failures5.24%. Both rejected. Reports
and verified-comparison.json downloaded. The fixed-model test does not support
refitting as the sole cause of regression. Fewer model computations produced
more actor updates, not better task performance.

Next: if detaching phase improves actual outcomes, validate against native PPO
at matched elapsed time with additional evaluation/training seeds and full300tick
normal episodes; no promotion from one short pilot. If not, test the now-verified
exact scoring with a real-transition EMA critic and H16 against PPO, since the
critic-free short objective may sacrifice later balance for immediate reward.
Do not repeat blind LR sweeps. Existing10minute overnight heartbeat ACTIVE.
Phase-specific concern: the existing KL check covers motor-action means only;
it does not bound changes in the deterministic phase prediction. Thus small
motor KL does not establish that this extra BPTT path is a small behavior change.
The phase ablation retains forward predictions and normal supervised targets;
its results, not this hypothesis alone, decide whether to change the adaptation.
Compact completed-test data: Saved/MimicKitSuperMimic/completed-pilot-summary.csv
(12arms, through frozen-model pilots). Budgets/evaluation overhead differ; this
is an inventory, not a ranked wall-clock speedup comparison. Original PPO's
short control6.456->6.532% noisy failures, so tiny sub-percentage changes in
one training seed are not enough to establish a winner.

## Previous: frozen-model pilots

COMPLETED JOB: madmad74100/prophecy-supermimic-frozen-model-pilots v1, submitted
October22 21:40:17UTC. Two free T4s,240seconds each, fixed90second checks.
Both exact dense reward plus analytic COM2 failure derivatives, H4, LR1.125e-6,
2048fresh starts across8ticks. `refitted` continues fitting dynamics; `frozen`
keeps the audited warm dynamics unchanged and asserts zero model-parameter
delta at completion. Same original119475 policy, real-forward anchoring,
hard termination/rewards, matching reset/noise seeds. No production changes.
Startup VERIFIED0.918s, cache restored42.9s, baseline/setup166s. Actual actor
updates verified: frozen55/refitted40 by~89budget seconds, no rejected steps,
real-forward error0, mean mismatch<2.7e-6, COM2 mismatch<1e-5, no failure-class
disagreements. Frozen model_steps stays0. First outcome check pending as of
21:44:49UTC. Existing10minute heartbeat is ACTIVE; no user input required.
Use existing logs/status/fetch helper, then analyze_supermimic_pilots.py with
arms refitted frozen. A fixed model is useful only if actual task outcomes improve.

Next diagnostic: `supermimic_kaggle.py phase-gradient-pilots` (now launched;
frozen-model completion and unchanged model were verified).
The frozen source.zip's OmniPPOModel includes a separate phase head in actor
parameters, but PPO uses its prediction under no_grad and supervises normal
rows only. Experimental BPTT additionally differentiates task reward through
the predicted reference phase; the successful local motor-action audit did NOT
test that path. Compare ordinary phase backprop with --stop-phase-gradient:
same actual autoregressive phase and target values, same normal-row phase MSE,
but detach predicted-phase input/target in the task-reward derivative. Both
use fixed audited world model, analytic scoring/failure derivative, H4, smallLR,
240s incl90s checks. First update logs phase-head gradient norm. Eleven CPU
numerical tests still pass; GPU update/outcome verification remains required.
This is an algorithmic ablation, NOT a production phase behavior change.
If it improves, compare against PPO rather than declaring victory from the
paired experimental arm alone. If not, next useful test is exact reward plus
real-transition EMA critic/H16 versus PPO, not another arbitrary LR sweep.

Failure-gradient pilots COMPLETE, reports and paired analysis downloaded.
Learned versus analytic:65/57accepted updates; actor deltas0.04528/0.04286.
Noisy perturbed failures6.456->7.432/6.907%, returns64.08->60.05/62.04.
Deterministic failures4.204->5.556/5.030%. Analytic preserves normal better
(noisy normal1.049% vs learned2.098%), but neither improves initial locomotion.
Analytic reconstructed COM2 matched actual velocity within1e-5m/s with zero
failure-class mismatches. Reject both as learning improvements. Warm-model
fitting took place during both; next test isolates that from fixed-model gradients.
Budget durations279.94/280.43s include155.16/157.61s intermediate evaluation;
actual learning124.79/122.83s. Duplicate evaluation at expiry fixed for new job.

## Previous: failure-gradient pilots

COMPLETED JOB: madmad74100/prophecy-supermimic-failure-gradient-pilots v1, submitted
October22 21:30:31UTC. Two free T4s; both H4, actorLR1.125e-6, exact dense reward,
no critic bootstrap,2048fresh starts across8ticks. Learned failure derivative
versus analytic smoothed COM2-boundary derivative; actual simulator hard
terminations and100penalty unchanged.240seconds including fixed60second checks.
Startup verified0.956s, restored cache49.5s, baseline/setup175.9s. Both workers
accepted real updates; analytic COM2 errors<1e-5m/s, zero predicate mismatches.
At60s, learned/analytic noisy perturbed failures6.607/6.456% vs6.456% initially;
at121s7.057/6.682%. No improvement so far. Analytic arm validates reconstructed COM2 against actual simulator velocity
(max2e-3 tolerance) AND requires zero failure-class mismatches on sampled
perturbed-loco states before any update. Eleven CPU tests pass. No production
change. Check actual startup/updates; fetch/analyze reports after completion.

Short-exact H1/H4 COMPLETE, both stopped at first90second check for major
regression:59/37accepted updates, actor parameter changes0.3132/0.2240.
Final noisy perturbed failures89.71/65.77%; normal96.15/87.24%. Full budget time
133.58/133.89s includes that intermediate check. Do not promote. This rejects
LR1.125e-5 for these fresh short-gradient updates; it does not establish that
one-step reward gradients preserve longer-term balance. Current low-LR paired
test separates update size from the failure-head derivative. Reports and
verified-comparison.json downloaded.

Next decision: if a failure-gradient arm improves actual noisy and noiseless
outcomes while preserving ordinary rows, compare it with native PPO at matched
elapsed time, fixed evaluation cadence and full300tick normal checks, then
independent seeds. If neither improves, do not repeat arbitrary LR sweeps.
Prepared next command `supermimic_kaggle.py frozen-model-pilots`: same H4 smallLR,
analytic scoring/failure derivatives,2048fresh starts, compares fixed audited
warm dynamics with continued online fitting for240s. Runtime asserts frozen
world weights have zero change. Model predictions getting better does not prove
gradients improve; the positive local action audit used the original warm model.
Then, if needed, short-horizon dense gradients may trade balance for immediate tracking. Test
the now-validated exact dense reward with a real-transition/EMA critic and H16,
against native PPO (earlier real-critic tests still used the learned dense
reward). Keep original task/checkpoint and record all setup/prior fitting cost.
Local pilot now avoids a redundant intermediate evaluation at budget expiry;
final evaluation remains separate and timed. This saves~40seconds of duplicate
testing without changing update logic. Not applied to the currently running v1.

## Previous: short exact-reward pilots

COMPLETED JOB: madmad74100/prophecy-supermimic-short-exact-pilots v1, submitted
October22 21:22:52UTC. Actual startup1.122s, compiled cache restored85.8s,
both workers alive. Two free T4s, H1 versus H4, exact existing dense reward,
real-forward/learned-backward, no critic bootstrap. Actor LR1.125e-5, batch2048
distinct fresh (world,start tick) pairs from eight newly collected ticks per
update. Same learned failure-head derivative and actual100failure penalty.
240seconds each including fixed90second evaluations, unchanged original policy
and warm model. Ten CPU tests pass, including fresh sampling across ring wrap;
on-policy means and exact real forward remain runtime assertions. No production
changes. If useful, validate against native PPO for longer matched elapsed time
and additional seeds; do not promote on a local gradient test or a tiny change.

Diagnostic prepared during short-exact v1, now active only in failure-gradient
v1's analytic arm: analytic COM2 speed/direction
failure surrogate in supermimic_exact_reward.py. Its hard predicate matches the
existing 0.7/1.7 and45degree boundaries; smooth sigmoid uses dimensionless margin
temperature0.05 only for derivatives. Actual simulator failure/reward would stay
unchanged via real-forward anchoring. Eleven CPU tests pass, including desired
gradient directions around each boundary. GPU velocity/predicate assertions
are required before every learning update. This may isolate erroneous
learned-failure-head gradients if short exact pilots regress.

Research rechecked: https://github.com/CuboiLeo/SuperMimic-Reproduced uses
analytic FK/reward heads and reports gains, but its strongest LAFAN result adds
anchor-relative observations and uses a different robot/hardware/evaluation.
Our global observations already expose heading; do not attribute its issue to
our policy without evidence. https://policy-world-model.github.io/media/pwm.pdf
Sections4.1/4.2 and5.3 distinguish model prediction accuracy from useful policy
gradients: smoothing and long-horizon gradient stability matter. A small forward
model error alone is therefore not a promotion gate. SimNorm/latent dynamics
would require a new model fit; first finish the cheaper exact-score/short-gradient
tests using the already fitted model. No reported external speedup is ours.

H32 exact-reward pilots COMPLETE:18accepted updates each. Small LR1.125e-6:
271.54s including112.91s checks, actor delta0.01546, noisy perturbed failures
86->84/1332 (6.456->6.306%), return64.081->64.050; deterministic56->56/1332.
No established gain: motion-cluster95% interval for noisy failure change spans
-0.972 to+0.674pp. Normal noisy failures9->11/572. Larger LR1.125e-5 regressed:
noisy perturbed86->174/1332 (13.063%), return45.533; normal18.182% failures.
Rejected. Reports and verified-comparison.json downloaded. This motivates
shorter gradients, which passed the direct real-action audit, with larger fresh
batches to reduce variance. Full reset errors remain<2.4e-7.

## Previous: H32 exact-reward learning pilots

COMPLETED JOB: madmad74100/prophecy-supermimic-exact-reward-pilots v1, submitted
21:09:03UTC; session361255623, startup1.483s, restored cache92s, both workers
alive. Two free T4s,
H32 real-forward/learned-backward, exact existing dense reward, no critic
bootstrap gradient, original learned failure head still supplies the gradient
for the unchanged100failure cost. Small/larger actorLR1.125e-6/1.125e-5;
240seconds each including matched deterministic/noisy intermediate checks.
Original119475 policy/warm model unchanged; same early regression stops and
numeric initial-state validation. No production change. Both actors accepted
their first real update at~29budget seconds (253notebook seconds); forward
error0, action-mean error<1.2e-6. First actor gradient norms30.6/116.5, KL0.00062/
0.1585. Dense/failure first-action gradient norms20.2/2.5 for small and21.8/33.2
for larger; direction alignment near0. This is an important diagnostic if the
larger arm regresses: the learned failure gradient can dominate its dense reward.
Exact-reward actor integration is prepared in
supermimic_decoupled.py; first update records dense/failure action-gradient norms.
If promising, compare with native PPO for equal elapsed time using additional
seeds and full300tick normal episodes; do not promote on these short pilots.

Exact-reward audit v2 COMPLETE: all scoring checks pass and all action gradients
are finite. One-step direction improves actual discounted reward in98.4–100%
of matched perturbed-loco rows; H4 direction in85.4–91.4%. Test prefixes8/40/70,
action RMS perturbations0.01/0.04. Matched rows174–492of666; unmatched/resetting
rows excluded, so this is local derivative evidence, NOT failure reduction.
No critic contribution in these probes. Mean real reward change positive for all
12probes (H1:+0.0034–0.0738; H4:+0.0064–0.1259). H1/H4 actual probe duration
57/62seconds after~202seconds setup; compiled cache restored113seconds into
notebook, useful but it does not eliminate environment construction/setup.

## Completed exact-reward audits

COMPLETED JOB: same exact-reward-audit slug, v2, submitted21:02:14UTC;
browser session361254498. Startup0.923s verified. Includes finite slerp repair
and new private compiled-cache dataset (ready,138files,44MB extracted/27MB zip).
No actor optimization; finish paired actual-reward gradient probes first.

STOPPED JOB: madmad74100/prophecy-supermimic-exact-reward-audit v1, submitted
October22 20:51:05UTC, browser session361252717. BOOTSTRAP_STARTED1.424seconds
verified from live logs. Two free T4 workers H1/H4, no policy optimization.
Nine CPU numerical tests pass. Seven simulator checkpoints through tick80 will
compare all existing weighted reward terms, including three-frame AE pelvis
translation. Stop before gradient probes if reward max error>0.002 or mean>0.0002.
If scoring matches, compare exact dense-reward action gradients against paired
real-MuJoCo interventions at ticks8/40/70 with NO critic bootstrap contribution.
Real-forward states/phase/rootXY are anchored; learned dynamics supplies only
derivatives. Logs via existing helper; receipts exact-reward-audit-launch.json.
Reset diagnostics compare four identical seeded resets with intervening ticks.
No production changes. This is validation, not a learning improvement claim.

V1 stopped at the nonfinite-gradient assertion before any policy update. All
seven scoring checkpoints PASSED: largest reward error0.000195, largest mean
error0.0000172. First-reset differences are at most2.384e-7, no changed channel
above1e-6: the earlier hash mismatch was rounding, not evidence of different
poses. The evaluator now records/checks numerical max error as well as hashes.
Root cause of gradient failure reproduced on CPU: stock slerp(q,q,phase) returns
q but phase gradient NaN because a masked branch divides by zero. Experimental
safe_reference_slerp keeps the exact constant-forward branches and finite zero
gradients;10CPU numerical tests pass. Production is unchanged. V1 reports kept
under prophecy-supermimic-exact-reward-audit-v1-reports before rerunning.
Compiled T4 Warp artifacts are being packaged privately (138files,27MB zip) to
avoid repeating~4minutes of setup on each pilot. Wait for upload receipt before
launching v2; do not duplicate a running audit.

DMO-inspired v1 COMPLETE. H4:70accepted updates,183.67s including111.62s checks;
H16:41updates,180.77s including75.93s checks. Actual actor parameter L2 changes
0.03956/0.02849. Final noisy perturbed failures8.4835/7.0571% versus6.5315%
initial; noisy returns58.54/61.99. Both noisy seed hashes match baseline/final.
Deterministic final4.8799% both; first-reset caveat below still applies.
Reports downloaded selectively. Reject both; no production promotion.
Next: verify a differentiable implementation of the existing reward against
actual simulator terms, including AE history, before any further learning test.
The old action audit showed nearly all positive short-return change came from
critic bootstrap; immediate reward changes were approximately zero or negative.
Do not spend another arbitrary LR sweep on that unverified gradient.

## Completed real-forward DMO-inspired pilots

COMPLETED JOB: `madmad74100/prophecy-supermimic-decoupled-pilots` v1. Launch receipt
Saved/MimicKitSuperMimic/decoupled-pilots-launch.json; original frozen119475 inputs,
two free T4s, H4 versus H16,180seconds each including intermediate checks. Same
two-seed120tick deterministic/noisy measurements and regression thresholds as
the noisy race. Private warm-model dataset, no prior notebook-output mounts.
Submitted20:33:17UTC, session361249646 verified in authenticated browser;
BOOTSTRAP_STARTED1.468s, both workers alive70s. Inspect live v1 for actor updates.
GPU update path verified: H4/H16 each accepted10updates by18.7/35.1learning-budget
seconds. Exact real-forward error0; on-policy mean error~0.000001. First noisy
checks6.53/6.83% versus6.53% baseline: no improvement established yet. Continue
until final report or early stop, then download selective reports and validate
actor deltas, seeded initial-state hashes, failure counts and returns. Do not
leave this as a RUNNING-only claim; worker/evaluation progress is already proven.

This implements the forward/backward separation described in the DMO primary
paper (https://arxiv.org/html/2509.00215v2, appendixA.1.3) and official code
(https://github.com/machines-in-motion/DMO_code). Fresh simulator trajectories
provide exact forward states; learned dynamics provide derivatives. Recorded
unclamped action samples preserve the correct clamp derivative. Actor means are
checked against collection-time means (max tolerance0.002); simulator-forward
values must match exactly. Only fresh trajectories collected before the current
actor update are used; hard reset boundaries block later-episode losses.
Our learned reward/failure gradients and policy architecture are retained, so
this is a DMO-inspired adaptation, not an exact reproduction. Critic is fitted
on real transitions with EMA target. Model gate checks one-step accuracy because
actor states never recursively drift. Eight CPU numerical checks pass, including
a deliberately biased-model case whose forward states are exact and whose actor
updates in the correct direction. GPU verification remains required.

Noisy race COMPLETE, reports downloaded. PPO:29updates/182.48s,106.56s learning
excluding75.92s checks; perturbed deterministic4.13->4.28%, noisy6.46->6.53%.
Stochastic H1 model:87updates/180.22s,71.07s learning excluding109.14s checks;
deterministic4.20->4.50%, noisy6.38->6.98%, noisy return64.19->62.35.
Actual actor parameter L2 changes0.07866/0.03054 verify both updated.
No improvement; reject stochastic imagination alone. Checks consumed unequal
fractions because they also trigger at accepted-update counts: do not describe
this as equal pure learning time. GPU setup~247s and final checks~37s additionally.
Report audit: initial observations match between arms. Within each arm, the first
deterministic seed's startup reset hash differs from later evaluations; second
seed and BOTH noisy seeds match exactly throughout. Motion/group assignments
match. Use noisy results as the verified paired comparison (PPO86->87failures,
model85->93 of1332); do not claim a small deterministic gain until first-reset
warmup is diagnosed. Saved verified-comparison.json records the hash checks.
Current DMO v1 already launched with the same evaluator; inspect its noisy hashes.

Next investigation if DMO also fails: examine learned reward-gradient accuracy
separately from dynamics/critic gradients. The earlier action audit's positive
short returns mostly came from critic estimates, not immediate reward. Replacing
the learned reward with exact differentiable task scoring is a stronger next
hypothesis than another arbitrary LR sweep. This requires reconstructing body
positions/rotations/velocities and the AE history from the146 physical state
features; match all existing real reward terms numerically before any trial.
The frozen source uses global_obs=true, so global heading is observed. Preserve
the user's reward/task and the original policy; do not simplify losses to claim
a win. DMO-BPTT without critic is another paper-supported ablation only if a
short-horizon reward-gradient audit first looks useful. SAPO adds entropy and
double critics, but would be a larger policy change and is lower priority.

## Previous work: matched noisy PPO/model comparison

COMPLETED JOB: `madmad74100/prophecy-supermimic-noisy-race` v1, submitted
October22 20:23:37UTC. Session361248027 verified in authenticated Kaggle Edit
link; BOOTSTRAP_STARTED0.946s and both workers alive45.3s. Two free T4s,
180seconds each including intermediate evaluation, original119475 policy,
same frozen source/task. `ppo` uses the original resumed PPO optimizer;
`stochastic_model` uses H1, real-transition critic with EMA, and differentiable
Gaussian action samples using the production standard deviation. Both evaluate
the same two reset seeds with and without exploration, independent per-seed
action-noise generators, over120ticks (full perturbed episodes; normal rows are
only checked for120ticks). Failures and returns are measured in actual MuJoCo.
Early stops: deterministic failure regression >3points perturbed/>2points normal,
or noisy regression >5points. Actual actor parameter change is recorded.
Noisy evaluation does not change reset distribution or phase queuing. CPU noise
reparameterization/RNG isolation and five existing numerical checks all pass.
The model reuses prior fitting, which must be counted before any speedup claim.
Launch/source hashes: Saved/MimicKitSuperMimic/noisy-race-launch.json.

User is sleeping and explicitly authorized continued free experiments and web
research if no improvement. Existing heartbeat updated to continue evidence-led
short tests, longer validation only for promising candidates, never paid compute
or production changes. Verify actual startup within5minutes; RUNNING is not proof.

One-step pilots v2 COMPLETE:160accepted actor updates per arm in~188seconds.
Final two-seed perturbed-loco failures61/1332=4.58% real critic and66/1332=4.95%
imagined critic; original frozen two-seed policy56/1332=4.20%. Normal failures
1/572 for each. Small early quick-check gains disappeared; no demonstrated
improvement. Reports downloaded selectively; no weights promoted.

Paper check: SuperMimic deliberately uses deterministic imagined actions and
action noise only for real collection. Our deterministic choice was not a
reproduction bug. Stochastic imagination is a SHAC-inspired adaptation:
https://raw.githubusercontent.com/NVlabs/DiffRL/main/algorithms/shac.py
uses deterministic=False in compute_actor_loss. The new noisy evaluation also
addresses the mismatch between deterministic diagnostics and the user's noisy
training-failure graph. It must not be confused with an algorithmic improvement.

Research leads if this fails: DMO uses simulator trajectories for the forward
pass and learned gradients for the backward pass, avoiding rollout drift
(https://machines-in-motion.github.io/DMO/). PWM emphasizes regularized models
and smoother gradients (https://policy-world-model.github.io/). Read the primary
papers/code before implementing; these are hypotheses, not verified wins here.

## Previous work: one-step pilots

COMPLETED JOB: `madmad74100/prophecy-supermimic-one-step-pilots` v2.
October22 20:02UTC: retry submitted20:01:49UTC and browser confirms
BOOTSTRAP_STARTED at0.8s. Exact session361242531, twoT4s, private. v1 session
361235490 was canceled in the authenticated browser after33minutes with zero
output; API confirmed CANCEL_ACKNOWLEDGED. Do not confuse v1/v2 log labels.
Same two180second learning tests and exact source hashes. Only input packaging
changed: warm model SHA6b1296f4... verified locally and uploaded as private
prophecy-supermimic-warm-start; previous notebook output/cache mounts removed.
The successful retry does not prove which dependency/platform fault stalled v1.
Compilation may repeat; do not count that as an algorithmic speedup. Monitor
startup actively: RUNNING alone is insufficient; if no first log within5minutes,
cancel the exact session identified in the browser rather than wait indefinitely.
Launch receipt preserves v1 separately. Production remains untouched.

Previous v1 stall:
October22 19:53UTC wake: unchanged RUNNING; bounded live-log read timed out,
zero events and no downloadable reports. No new job or training changes.
October22 19:50UTC check: Kaggle still reports RUNNING, but repeated bounded
live-log reads returned zero events (not even BOOTSTRAP_STARTED), and selective
output listing returned no reports. Submitted19:25UTC; execution is UNVERIFIED.
Official quota endpoint reports1.787GPU hours used of30, zero time reserved,
pay-to-scale disabled. This suggests preparation/queueing rather than verified
GPU execution; it does not establish the cause. Uploaded source/metadata match
the intended private T4 job and both warm-model/cache inputs. Do not duplicate
this job. Next wake check status/logs/output; if still stuck, investigate the
Kaggle session rather than tune training from nonexistent results. Browser is
not authenticated; API is authenticated. Never cancel using versionNumber=1:
that is not a verified global session ID. Existing900s worker watchdog and1100s
Kaggle execution limit remain; they cannot verify or bound pre-execution delay.
Live-log helper now preserves previously retrieved events on failed empty polls.
Two free T4s,180seconds learning/checks each plus setup/final evaluation.
Both use original119475 policy, warm cautious world model, H1, actor LR1.125e-6.
`imagined_critic` uses the existing imagined-data critic fit; `real_critic` uses
eight-step real-simulator lambda targets (.99discount/.98lambda), original
failure penalties and a slowly updated target critic (.005 new weight/update).
This tests real critic fitting plus target averaging as a package, not isolated
effects of those two settings. Failed transitions have zero bootstrap; timeout
uses actual final-state value. CPU check confirms terminal -100 is learned even
when the bootstrap critic predicts+100. Five numerical tests pass. No production
changes. Launch/source receipt: one-step-pilots-launch.json. Completion monitor
check-kaggle-comparison-results ACTIVE every10minutes and follows this section.

Audit COMPLETE,27.5/30.0seconds of actual probes after setup. On matched perturbed
rows, H1 predicted improving actions increased the measured short return in
88.5--99.0% of cases; H4 only58.7--66.5%. Crucial caveat: those returns include
the ORIGINAL critic's bootstrap and the improvement was almost entirely in
that value, not immediate reward. This is gradient fidelity evidence, not
better episode performance. Only~203--454of666perturbed rows qualified per probe:
seeded prefixes sometimes diverged, so mismatched/previously-ended rows were
excluded. Reported row bootstrap intervals are not independent-training-seed
confidence. The next pilot must prove actual episode failure improvement.
Reports: Saved/MimicKitSuperMimic/prophecy-supermimic-gradient-audit-reports/.
Remote compiled Warp cache was saved and is mounted for the next job.

## Previous work: action-gradient audit

`madmad74100/prophecy-supermimic-gradient-audit` v1 submitted after the cautious
pilots completed. No learning: original policy/critic119475, fitted world model
from cautious small_step, two T4s checking one- and four-step imagined returns.
For seeded real states after8/40ticks, compute the model's improving action
direction and test positive/negative RMS changes0.01/0.04 in real MuJoCo. Replays
the same prefix and excludes unmatched initial states (>0.0002 in any raw
observation coordinate) or previously ended episodes. Reports reward and bootstrap
effects separately. It tests gradient fidelity, not a learning-speed win.
Source/receipt: gradient-audit-launch.json and supermimic_gradient_audit.py.
Compiled Warp cache will be retained remotely for faster subsequent setup;
the selective report downloader does not copy it to the laptop.

Cautious pilots COMPLETE:155/159accepted actor updates in180s. Final two-seed
perturbed-loco failure7.06% (critic trained) and7.28% (critic fixed), versus the
original two-seed4.20% evaluation. Normal full300tick failures0.175/0%. Smaller
steps avoided abrupt divergence but did not produce a lasting improvement;
critic freezing alone did not solve it. Do not promote either policy.
Reports: Saved/MimicKitSuperMimic/prophecy-supermimic-cautious-pilots-reports/.

## Previous work: small policy steps, critic ablation

October22 evening, after laptop cleanup: private Kaggle
`madmad74100/prophecy-supermimic-cautious-pilots` v1 submitted. Two T4s,
180-second tests plus setup/final evaluation, both four-frame imagination and
actor LR1.125e-6 (production actor LR). One trains the critic on imagined
transitions; the other keeps the original critic fixed. Both start from the
original checkpoint119475, reusing only the fitted dynamics from fast-pilot h4.
This reuse is counted as prior work, not a fresh wall-clock race. No production
changes or paid GPU. Live logs use `supermimic_kaggle.py logs ... v1`.

The preceding fast pilots COMPLETE and automatically rejected both candidates:

| Candidate | Accepted actor updates | Real perturbed-loco failure | Stop time |
| --- | ---: | ---: | ---: |
| H4, LR1e-5 | 54 | 4.95% initial ->12.76% | 124.6s |
| H8, LR1e-5 | 48 | 4.95% initial ->20.27% | 125.8s |

These are single-seed checks over120ticks,666perturbed-loco rows. Normal-row
checks cover only the first120ticks, not their full300tick episodes; both ended
at3.50% normal failure. H4 briefly reached3.90% after six updates before drifting;
that small sample improvement is not established learning. Pre-clip actor
gradients were now tens rather than trillions. Both captured-model-fit checks
matched eager Adam exactly on two batches (maximum weight difference0).
Reports: Saved/MimicKitSuperMimic/prophecy-supermimic-fast-pilots-reports/.

Earlier quick H8/H16 pilots completed540model fits each but their model-quality
gates never passed: zero actor updates. Their unchanged performance was not a
successful learning result. Fast pilots reused that fitted model, accelerated
model fitting with a verified CUDA graph, and shortened diagnostic evaluations.
Cautious pilots additionally check after10accepted updates, then every30 or45s,
save promising intermediate policies, and retain the real-simulator early stop.

## Previous short-pilot launch

October22 20:33 Warsaw: user requested continued free experimentation, much
shorter tests and live inspection. Submitted private
`madmad74100/prophecy-supermimic-quick-pilots` v1: two T4s, structured model with
8- and16-frame actor horizons, at most240seconds each including intermediate
simulator checks. Setup/compilation is additional; whole job limited to15minutes.
Initial policy, task, rewards, physics and normalization unchanged. Fresh model
weights and actor Adam1e-5; original v1 files and results retained.

Concrete defect: v1 allowed the four hinge joints to rotate about forbidden axes
and predicted key-body positions independently of joint rotations. The original
checkpoint has first-layer column norms~3,600–3,800 on constant hinge channels.
On64random valid articulated poses, a0.001 unsupported rotation-encoding offset
changes normalized motor outputs by0.2867RMS. The structured projection reduces
that to4.34e-7RMS and its derivative on forbidden channels is exactly zero.
Valid physical poses are unchanged within4.70e-7maximum coordinate error.
Evidence: Saved/MimicKitSuperMimic/structured-local-verification.json.

`supermimic_structured.py` enforces the actual Z hinges and forward kinematics;
GPU startup separately asserts that it preserves real simulator observations.
`supermimic_pilot.py` measures held-out model error over the actual actor horizon,
reports implied next-action error, and evaluates in real MuJoCo after60seconds
then roughly every45seconds. It stops on >3percentage-point perturbed-loco or
>2point normal-loco regression relative to the initial evaluation. Each candidate
starts from the original verified checkpoint; no experimental weight is deployed.

Live monitoring is now VERIFIED: a CPU-only Kaggle probe returned active SSE
events through the official /api/v1/kernels/logs/stream route with versionLabel=v1.
The quick-pilot supervisor forwards worker progress to notebook stdout every15s;
use supermimic_kaggle.py logs madmad74100/prophecy-supermimic-quick-pilots v1.
This corrects the first experiment's inaccessible child-file-only logging.
No paid compute or production mutation authorized for this work.

## First experiment (complete)

Status, October 22, 18:20 UTC: private race
`madmad74100/prophecy-supermimic-vs-ppo` version1 COMPLETE. Both workers finished
30 minutes of learning on separate Tesla T4 GPUs and completed real-MuJoCo
evaluations. This adaptation degraded the policy substantially; do not promote
its weights or replace production PPO. No production state was changed.

## Measured result

Final evaluation uses four common reset seeds, identical initial observation
hashes and identical motion assignments. All recorded metrics were finite and
all evaluation episodes ended within the configured horizon.

| Real-MuJoCo failure rate | Existing PPO | World-model adaptation |
| --- | ---: | ---: |
| Perturbed locomotion, 2,664 episodes | 4.17% | 62.99% |
| Normal locomotion, 1,144 episodes | 0.087% | 80.16% |

The common initial evaluation (two seeds) was already at4.20% perturbed-loco
failure. PPO remained around4–5%, so this starting checkpoint and short test
do not establish PPO's longer-term learning speed. The experimental regression
is large and consistent across the motion-cluster evaluation interval.
Idle has no relevant failure termination, so its zero failure count is not
evidence of pose quality.

PPO completed462updates and15,138,816real transitions in1801.04seconds.
The world-model worker completed18,120model minibatches and5,628,928real
transitions in1800.36seconds. Its actor attempted990updates, accepted986 and
rejected4. The first attempt was at78.53seconds; this was not a case where the
actor stayed disabled. Both workers' setup/initial evaluation took~198seconds,
excluded from the equal learning budget.

The prototype's un-clipped actor gradient norm reached4.79e12 despite passing
the eight-step prediction gate. Clipping kept updates finite but did not prevent
real-simulator regression. The evidence indicates an unstable model-based
optimization path; it does not isolate whether longer-horizon model error,
learned reward/termination gradients or critic extrapolation dominates.
This is a result about our adaptation, not a reproduction or disproof of the
published SuperMimic implementation. No further GPU run was launched.

Downloaded logs, per-row evaluations, comparison JSON and the learning curve:
`Saved/MimicKitSuperMimic/prophecy-supermimic-vs-ppo-reports/`.
`learning-comparison.png` uses the same two seeds at every point; final table
above uses all four seeds. Original archive member verification passed; the
shared rebuilt checkpoint container SHA is
`b99643f0ff9be027ad12588f75fec766464eb175c48733ff82b3ce7b7aed9fc6`.

User authorized free Kaggle experimentation from an earlier locomotion checkpoint.
Do not change either live Runpod trainer, its billing, source or checkpoints.
Do not promote experimental weights without reviewing real-simulator results.

## Why test it

[SuperMimic](https://supermimic.github.io/) fits a differentiable dynamics model
from simulator transitions, then trains the policy through predicted trajectories.
Its [paper](https://arxiv.org/pdf/2610.28480) reports full-loop training on an H100,
compared with SONIC's separate multi-GPU training. This is not a measured speedup
over our PPO, our motion library or T4 hardware. The authors' public project did
not link official training code when checked on October 22.

Our native MuJoCo simulator can supply the required transition data; its contact
solver does not have to be differentiable. The main practical uncertainty is
whether a learned model predicts our contact dynamics accurately enough for
policy gradients to help. The controller may exploit errors in the model.

## Frozen inputs

- Checkpoint `0119475`, 2,409,365,504 samples: exact initialization of the active
  `20261022_104557_uefn_locomotion_pelvis_velocity5_1024` continuation.
- Checkpoint archive SHA256:
  `b08240a5064bedea9be4af53f8903adfb47c4d8714551a39ff70145216df5665`.
- Source archive SHA256:
  `534659c4cd91e3ed7de4d7b8707ba711f34725e5aaec2c05e611d41e02b3f846`.
- Private inputs: https://www.kaggle.com/datasets/madmad74100/prophecy-supermimic-private-race
- Local copies and receipts: `Saved/MimicKitSuperMimic/`.

Kaggle automatically extracts the uploaded ZIPs. Bootstrap verifies every member
against a manifest calculated from the original archives, then rebuilds a local
checkpoint ZIP. Its container checksum changes; the member bytes must not.
Source path changes are limited to replacing the Runpod workspace prefix.

## Comparison

Both workers use 1,024 agents, identical task/reward/termination configuration,
the saved policy/critic/normalization, and one T4 each in the same Kaggle session.
Worker 0 continues the existing PPO including saved Adam state and actual live
launcher actor LR1.125e-6 (the YAML's4.5e-6 is overridden after restore). Worker 1 uses a
paper-inspired world-model/BPTT adaptation, with fresh model and optimizer state.
No task difficulty reductions or production changes are part of this test.

The experimental model predicts unclipped physical observations, reprojects
rotation encodings and learns reward/failure heads from actual simulator labels.
It trains on eight-step windows and optimizes the actor through 32 imagined steps.
This is **not an exact SuperMimic reproduction**: it retains our policy inputs,
uses a smaller dynamics network and an observation-state representation, and
fits learned reward/failure heads. Section3.2 allows learned or analytic heads;
the unpublished implementation's exact choices cannot be verified. These
differences restrict conclusions about the published method, particularly if
this prototype fails.

Model fitting excludes complete held-out simulator worlds. Actor updates start
only after a recorded prediction-quality gate passes. Numerical checks cover
failure/timeout bootstrapping, replay boundaries, held-out worlds and gradients
through frozen dynamics. A restored-state GPU smoke check exercises the complete
actor/critic path before any experimental actor update is committed.

Default learning budget is 30 minutes per worker, including data collection,
model fitting, actor/critic updates and snapshot saves. Common setup and final
evaluation are recorded separately. Policies are saved every five minutes and
evaluated afterward in the original MuJoCo environment on common reset seeds.
Primary outcome is perturbed locomotion failure percentage versus elapsed
training time; also report returns and normal-row regressions. Four final reset
seeds measure evaluation variability, not independent training replicates.

If the model gate never passes, this is a failed model-fitting feasibility test,
not evidence that SuperMimic learns more slowly. If the policy improves only in
imagined rollouts, that is not a win. A promising result needs a second training
seed before recommending replacement of the production algorithm.

## Commands

Use `Saved/Robotics/env/Scripts/python.exe` with:

```
Labs/MimicKitTraining/supermimic_kaggle.py status madmad74100/prophecy-supermimic-runtime-preflight
Labs/MimicKitTraining/supermimic_kaggle.py race 1800
```

Launch the race only after successful simulator preflight. The launcher is
private, bounds the session, and stops its companion worker on failure. Existing
Kaggle bearer authentication is scoped to these API calls; credentials are never
uploaded. Do not recreate the already uploaded private dataset unnecessarily.
