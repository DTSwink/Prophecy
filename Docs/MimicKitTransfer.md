# Isolated Run LR checkpoint transfer assessment

## October 18 — native profile integrated for get-up training

User chose pure configured native MJWarp, cancelling proposed solver mixing.
The production adapter preserves the checkpoint's original joint-coordinate
convention around PHAT-centered native ball bounds; CPU randomized FK and
L4 real-engine/reset/PPO smoke pass (GPU body mapping error 5.6e-7 m).
Get-up continuation `20261018_084204_uefn_getup_native_mj_512` launched from
verified 656_final on L4 `ennp2v39ymd04t`; hard stop 10:34:09 Warsaw October18.
Original gains, torque envelope, zero armature, geometry and 240/30 Hz remain.
No custom motor/contact/projection passes execute in this backend. The native
profile still approximates PHAT limits and does not establish exact Jolt parity.
Current operational details/evidence are in the opening of MimicKitTraining.md.

## October 18 — native MuJoCo replacement audit

Latest state: training stopped, checkpoint 656_final locally/persistently
verified; the dedicated ten-minute L4 audit completed in 236.2 seconds and
its pod `u7yyhwcg8xt179` is confirmed EXITED. The older running entries below
are historical. See the opening of MimicKitTraining.md for full current status.
The disposable audit pod was subsequently deleted after local and persistent
S3 readback verification of its source/results/traces; retained training pods
were not deleted. Receipt: vanilla-calibration/persistent-audit.json.

The original archived Run LR 4013 policy passes 13/16 distinct ten-second
starts in native MJWarp using PHAT-centered spherical ball bounds, elliptic
friction, frictionless self contacts and contact solref [0.0175, 2]. It passes
0/16 with the unconfigured Newton-converted native model. Native ball joints
were previously unlimited. Original gains, torque caps, geometry, mass/inertia,
zero armature and 240 Hz / 30 Hz frequencies remain unchanged in the selected
candidate. Recorded Jolt reference passes 16/16; native transfer is incomplete.

On the replacement L4, selected physics takes 16.81 ms per policy tick for
512 worlds, versus 12.09 ms for unconfigured native physics. This is paired
physics timing, not full PPO. Three initial phases still fail; floor penetration
reaches 5.06 cm in recorded frames. Native spherical bounds do not reproduce
the exact PHAT swing ellipse/twist. Production training integration is pending:
native ball quaternion = reference * original quaternion, body rest transform
= original rest * inverse(reference); resets and policy observations must be
mapped consistently. Do not change only the model rest transform.

Saved settings, numerical traces, source and billing receipt are under
Saved/MimicKitTransfer/vanilla-calibration. The old successful Unreal/Jolt fixture
was used as recorded evidence; the user's editor/session/assets were untouched.

## Current handoff — no-armature checkpoint3913 and original-skin preview

**October17 20:32 latest: follow-up audit completed; current L4 remains running.**
Current run20261017_200515_uefn_equipment_idle18_512, same owned L4t7kby2z4440esp,
fresh three-hour deadline23:05:22 Warsaw.92 idle rows (74 recovery/18 ordinary),
168walk/252run; recovery-only head/hand27cm termination removed, feet/pose/clip-end
checks retained. Checkpoint20613_final resumed with full state, latest checked
21014 persistently verified; live21094/345.62M samples. Detailed guards/receipts
and current status are in MimicKitTraining.md, not the main journal.

Four new physics candidates were screened and rejected for no reliable gain:
contact impulse reuse, multiple-RHS factor solves, shared-memory scratch reuse,
active-only Jacobian clearing. No Jolt/MJ physical rule changed in this audit.
Shared PPO/auto-phase actor computation is accepted in canonical future packages,
local full-update10.549 ->10.095s (4.31%). CUDA capture adds no clear further gain.
Algebraic objective preserved; floating-point backward summation is NOT bitwise
equivalent. Exact old4013/archived body passed16 distinct10s phase starts before
and after a disposable update with either implementation; peak18.05/18.83/18.45cm,
no failures/warnings. Does not revalidate the newer PHAT or claim a native rerun.
Auto-phase metric aliasing was corrected; actual loss weight unchanged.
Source edeeaf57ed7f and complete audit are locally/persistently verified; live
L4 remains on0911d5acbdf9 without an extra interruption. See
Saved/MimicKitEquipment/optimization-followup/audit-complete.json.

**October17 19:24 latest: optimized MJ runtime resumed on L4.**
User authorized three hours, actual L4 speed measurement, and leaving it running.
Owned t7kby2z4440esp, run20261017_192404_uefn_equipment_solver_speed_512,
verified19683_final resume, $0.59/hour; hard stop22:11:33 Warsaw. See current
MimicKitTraining opening for guards, checkpoint, setup receipts and measured speed.
Unreal/Jolt remain unchanged. Actual warmed L4 full PPO last30 updates average
2.1941s /7,467 transitions/s versus previous3.065s /5,345:28.4% less update time.
Advancing at323.34M samples; first backup verified,20 replay rows/TB available,
no warnings/failures observed. Training is left running as requested.

**October17 implementation completed before this launch:**
Register-resident contact iteration, common-scale tangent preconditioning and
original-equation convergence checks now replace the wasteful inner loop.
The physical fixed point, torque law and required motor-branch damping remain
unchanged. 100 is still the difficult-case ceiling; average in the full PPO
trial is21.15–21.17 passes. Combined with fused FK/exact spawn caching, paired
local512-world full PPO takes13.621 ->10.603s/update (22.16% less time). This is
local4060 evidence, not an L4 throughput claim. Final production difficult cases
agree with independent float64 solutions within1.4e-5 generalized velocity;
packaged floor penetration remains4.378mm. GPU graphs, finite warnings and
nonfinite rejection pass. See current MimicKitTraining handoff and evidence.
No Jolt physical-rule change is needed: the numerical solve targets the same
existing equations. Owned klyceawn5edw3l remains EXITED, final19683 locally/S3
verified, speed heartbeat paused. Released source d61275b88cbc is locally and
persistent-S3 readback verified; final packaged PPO smoke passes. Earlier running
paragraphs are historical.

**October17 L4 follow-up:** user authorized three-hour continuation. Parallel
guard is running on replacement L4 klyceawn5edw3l with verified backups.
Measured last30 full PPO updates3.065s versus original1.79s,71% slower;
local4060 improvement did not transfer. User notified. No zero-overhead claim.
Training journal contains deadline, monitoring and receipts; Unreal unchanged.

**October17 follow-up: cheaper parallel floor guard, locally verified.** The
equipment-only opt-in now selects one warp per world/one lane per collider,
with ancestor-chain FK instead of serial whole-rig scans. Same geometric bound
and backtracking; no controller/mass/limits/velocities changed.1024 randomized
geometry tests and captured replay pass. Blocked corrections differ slightly
in float32 operation order (max generalized-coordinate delta5.1e-5), so not a
bit-identical replacement; clear proposals remain exact. Matched get-up peak
remains4.38mm vs5.68cm without guard. Paired512-world full PPO benchmark:
24 updates,393,216 transitions; local4060 median15.234s baseline vs12.001s
parallel, no detected slowdown or numerical failure. Not an L4 benchmark or
guaranteed21% speedup. Paid equipment pod remains EXITED at user request.
Existing-contact-only projection was also tested and rejected (5.58cm persists).
Source/evidence details are in Docs/MimicKitTraining.md.

**October17 equipment-only floor-aware projection:** optional engine setting
`transfer_floor_aware_projection` guards the post-contact angular split correction
against the static horizontal floor using exact sphere/capsule/box FK on GPU.
It backtracks blocked generalized-position corrections; no velocity edits or
angular-limit value changes. Clear proposals are bit-identical. This prioritizes
floor feasibility over completing that split correction immediately; it is not
a simultaneous position solve or a new Jolt-parity claim. Default remains off
for other engine configs; the current equipment recovery package explicitly
enables it. Unreal/Jolt unchanged. Same-policy get-up case improves5.68cm floor
penetration to4.39mm. Reset-only fixed-hip/pole foot IK clears separately detected
initial penetration. Remaining motion/contact penetration up to4.38mm is measured,
not hidden. Unit geometry/capture tests,512-world PPO smoke and matched32-world
policy tests pass. See dedicated training journal and
Saved/MimicKitEquipment/floor-recovery/ for scope, overhead and evidence.
The previous serial guard's L4 training cost was material: about3.2s/update versus1.8s before.
64-thread scheduling is bit-identical and improves an isolated local test,
but has not demonstrated lower whole-training cost. Do not call this free or
negligible overhead. The parallel replacement above supersedes that implementation;
it has local full-PPO validation, but no new paid L4 measurement.

**October16 equipment solver correction (deployed and training verified):**
the main block solver can cycle between motor torque-limit branches; the old
scalar fallback needed3,152 sweeps on the captured1274 case. A GPU simultaneous
solve now resolves the same capped-motor/contact/limit/friction equations before
that safeguard. Partial-pivot Newton with residual line search uses independent
16-sweep scalar seeds; stalled attempts never commit. Common block/100-contact
iteration path stays unchanged. No cycle detector (rejected after a2x physics
regression), controller/physics parameter change, limit/geometry change or CPU
readback. Sixteen reusable scratch slots add about40MB and one captured launch.
The finite-warning policy and final3,000-sweep safeguard remain for unseen cases;
do not claim global convergence or exact ordinary-contact convergence.

All51 captured states, CUDA graph replay, preserved invalid error codes and NaN
rejection pass. Captured1274 now uses16 seeds+9 Newton steps, with5.11e-6 maximum
velocity difference from the long float64 reference.262,144 noisy transitions
needed31 coupled calls and no old fallback/warnings. Final consolidated paired
PPO test has15 coupled solves/zero scalar fallback versus15 baseline fallbacks;
whole-update4.931/4.871s and physics2.319/2.365s are within observed variation.
Dedicated training journal records source hashes and cloud deployment state.
Run20261016_145703_uefn_equipment_velocity_512 resumes2322 on L4nsvb0bg53dnc32,
verified beyond2363 with S3 checkpoint/20 replay rows; fresh4h ends18:57 Warsaw.
Tiny observed idle foot-origin motion0.1–2mm/10s is explicitly accepted by the
user absent a clear bug. No demonstrated connection to the small residual in
ordinary finite-iteration contacts; those equations/iteration counts unchanged.
Original Unreal recordings are preserved and current user TestNN work untouched.

**October16 expanded-PHAT validation: Jolt bug deferred, MJ launch authorized.** All16 Run LR
starts finish10s, but phase0.25 tick87/substep4 has a20.23cm right-ankle separation
hidden by policy-boundary sampling. Exact-prefix interventions and a no-simulation
collision query isolate an incorrect floor-contact normal: the small foot against
the fixture's200m-wide thin floor box produces downward z=−1 instead of upward.
The query matches the full simulation's erroneous depth/normal exactly. Reversing
query order, or testing other box sizes at the same foot pose, returns upward.
An instrumented copy of the existing narrowphase code reproduces it inside EPA;
it does not need motors/limits/contact-cache reuse. Disabling contact POSITION
correction only at that identical step reduces the anchor error to0.03627cm,
confirming how the bad contact causes the jump. This is diagnostic evidence, NOT
a retained workaround: floor shape, physics settings, DLLs and gameplay unchanged.
Algorithm repair/general regression pending; no current-rig transfer acceptance.
After diagnosis the user explicitly authorized proceeding with MJ training while
deferring this native collision bug. No workaround was retained.
MJ equipment subsequently failed update132/world225. Captured GPU replay isolates
a finite3.10e-6 rounding floor against the strict2e-6 convergence gate; float64
reference difference4.35e-6. This is distinct from the deferred native floor bug.
The exhausted fallback now classifies bounded float32 rounding as a reported
warning only after motor and contact/limit checks; materially invalid results
remain rejected before PPO. No Jolt physics or motor/contact settings changed.
See the current training handoff for exact thresholds, regressions and billing
guard repair. The original world147 failure had no saved equation, so its precise
cause cannot be retroactively proved from the later capture.
**Latest user-directed policy:** iteration exhaustion with finite output is a
reported warning, not a fatal assertion. The10,000-sweep candidate below was
reverted before deployment; budget stays3,000. Continue with the finite computed
approximation and report residuals; NaN/Inf and invalid constraints still fail.
Warning counters/metrics stay on GPU until existing rollout-boundary validation.
See current training journal for tests and local fallback cost. No Jolt changes.
Subsequent equipment update1274/world267 exposed insufficient fallback budget,
not a rounding floor: six contacts, no limits;3,000 sweeps leave motor defect
2.533e-3Nm. Identical solve finishes under existing checks at3,152 sweeps with
1.887e-3Nm. Superseded candidate changed only cap3,000→10,000; early exit, normal block path, physics,
thresholds and GPU graph execution unchanged. Same3,152 result with caps3,200,
4,000 and10,000, CUDA graph regression passes. All four historical captures still
pass; unsupported-contact errors still reject. Difference from a fully converged
10k float64 reference is3.47e-4 generalized velocity, versus4.63e-4 at old cutoff;
this is iteration truncation under the EXISTING convergence criterion, not exact
arithmetic parity. No Jolt changes. Evidence Saved/MimicKitEquipment/failure1274/.
Evidence and training additions: opening of `MimicKitTraining.md` and
`Saved/MimicKitEquipment/native/anchor-*.json`, `stderr.log`.

**October16 Unreal display updated at user request:** the dedicated comparison map
was clean and outside Play, still using the old bounded-motor failure recording.
Imported `AS_Newton4013` and `AS_Jolt4013`, verified source/payload hashes and all
301 frames of all88 bone tracks (maximum import error0.000322cm/0.000257deg),
then saved ONLY the comparison map and those two new animations. Camera piloted;
both recordings play synchronously at0.25x in an owned Simulate session.
Receipts: `accepted-preview-refreshed.json` and `accepted-preview-playback.json`
under `Saved/MimicKitTransfer/no-armature-3913`. This is successful recorded physics
from checkpoint4013, not live policy inference in Unreal. These captures retain
the archived transfer rig's limits; they do not establish native parity for the
subsequently expanded canonical PHAT. No Blueprint, PHAT, mesh or training change.

### Active goal — October15 overnight

**Latest October16 solver pass verified; training stays stopped.**
Retained two changes: try the previous motor torque-limit branches before the50
preliminary sweeps, and copy already prepared manifold responses instead of
recomputing them. The cached branches are only a hint: momentum, contacts, limits
and forces are solved from current inputs. If any motor branch disagrees with
the resulting velocity, reject the guess and run the original full50-sweep seed
and final solve. Restore physical-mass responses before that retry because the
failed block attempt overwrote them with effective responses. The checked scalar
fallback and original thresholds/counts remain unchanged. This also handles stale
hints after resets without transferring old contact impulses into new contacts.

Four runtime files changed. Cache cost for512 worlds:71,680bytes; two retry-kernel
launches added, one redundant preparation launch removed (net one extra GPU
launch), no new CPU readbacks or user knobs. All stays in captured GPU graphs.
The instrumented candidate accepted984,480 of1,048,049 previous-branch guesses
(93.9%) during its noisy test. Those diagnostic counters were not retained.
Exact unchanged-impulse exit in the seed showed only0.2% difference, within noise;
discarded. Its code and all other variants remain only in ignored diagnostics.

Paired512-world/24-input physics comparison:5.680->3.853ms (**32.2% less**), maximum
coordinate/velocity differences1.20e-7/1.44e-5. This repeated-input test is unusually
favorable to caching; do not present it as a32% training improvement.
Two alternating full-PPO comparisons (six disposable updates/variant, first
excluded) show a **2.6% median time saving across10 matched rounds**,9/10 faster.
First medians: reference5.104s, combined5.079s, vanilla2.939s; real physics
2.955->2.719s/update. Second three-way medians: reference5.239s, response-reuse-only
5.118s, combined4.951s; physics2.905->2.747s/update. Combined beats reuse-only in
all5 matched rounds. Thus real training physics saved about5–8%; whole-training
gain is modest. Current/vanilla observed ratio1.73x in the first comparison versus
its own reference1.74x; do not compare directly to the earlier1.63x ratio under
different machine load or claim the frozen-input gain applies to PPO. Unreal
remained open and untouched throughout; no saved benchmark optimizer/weights.

Final code passes all4 saved crashes against independent float64 equations,
CUDA graph replay, deliberately wrong cached branches and insufficient-solve
rejection. Three manifold controls pass on scalar and block paths. Final noisy
test:131,072 transitions,10,801 resets, zero failures,17 scalar fallbacks/3,520
sweeps (preceding pass19/3,808). Checkpoint4013 passes all16 starts for10s, max
16.940cm under27cm, zero fallbacks. Package/default-engine/failure guards and
Python compile checks pass. Both policy hashes and all current body hashes are
unchanged. Native receipt was left untouched/stale; this is not a new PHAT/Jolt
transfer certification. No cloud, production training, Unreal/lab changes or new
checkpoint copies. Initial disposable runner import/reference-source-line errors
were corrected and logs preserved; they did not run production training.
Evidence, frozen sources, rejected variants and final hash audit:
`Saved/MimicKitLocal/solver_followup/result.json`, `combined_physics.json`,
`ppo_final.json`, `ppo_isolation.json`, `noisy_final.json`, `regressions_final/`;
walking report `causal_transfer/solver_warm4013.json`.

**Earlier October16 coefficient/matrix optimization — verified baseline.**
**Transfer receipt is stale for the current body.** The final audit found that
the user's separate PHAT expansion changed the canonical XML/limits/physics at
06:57, before this optimization began. Native fixtures and their saved16x60s
results use the earlier archived body. The new MJ walking test uses the current
body and passes; it does not validate that body's dynamics in Jolt. Preserve the
new PHAT limits. They need updated native fixtures/tests before a new transfer
certificate or fresh all-motion training. `verify_transfer.py` now rejects this
asset mismatch before writing a receipt. Its identical-body/changed-XML,
changed-limits and changed-physics controls pass. The previous receipt was
restored byte-for-byte so its existing freshness checks reject the newer sources.
The briefly written, invalid refreshed receipt is preserved as
`solver_optimization/rejected_transfer_receipt.json`; it must not authorize a run.

The current source caches unchanged motor coefficients across the50 seed sweeps
and reuses one effective matrix for its factor, directly solving only the RHS
vectors needed by the contacts/limits. It no longer forms that full effective
inverse. Two runtime files changed: `sequential_contact_gpu.py` and
`block_contact_gpu.py`. GPU-only, no extra launches/readbacks, no new runtime knobs.
Keep seed50/final100/fallback3000/position20; this optimization changes no physical parameters, torque law,
friction, constraint order, rejection checks and accuracy thresholds are unchanged.
No custom native CUDA snippets were retained.

The final alternating512-world/24-input comparison measured full substep
**8.588->5.640ms (34.3% less time,1.52x throughput)**. Contact/motor solve measured
separately **7.463->4.439ms (40.5% less)**; seed3.345->2.122ms, final block
3.191->1.337ms. These separately timed stages are not strictly additive.
Final block shared memory36,448->10,848bytes; seed8,544->9,088bytes. Earlier quieter
paired measurement7.845->5.102ms gave the same approximately35% improvement.
Unreal was reopened externally during testing (PID16368); left untouched.
Do not compare the new absolute times directly to historical idle-GPU measurements.

**Full PPO comparison now exists:** vanilla, pre-this-pass and current engines,
same700 checkpoint/settings,512worlds,32steps/update, six disposable updates each,
first discarded, alternating order and independent RNG states. Medians:
vanilla3.231s, previous6.389s, current5.251s/update (**17.8% less time /1.22x
throughput**). Current was faster in all five measured pairs (1.21–1.37x).
Physics portion4.129->2.906s/update. Absolute timings varied with the active editor:
max/min ratios1.63/1.39/1.26 respectively. Current/vanilla observed ratio1.63x;
this is the present whole-loop comparison, not a claim of equivalent vanilla
physics or a guaranteed idle-GPU speed. No weights/optimizer states saved.

All four historical failure captures, independent float64 manifold controls,
CUDA graph replay and deliberate insufficient-solve rejection pass. Final frozen
coordinate/velocity differences1.20e-7/3.06e-5.131,072 noisy transitions: zero
failures,19 checked fallback solves/3,808 sweeps (previous16/3,616);10,768 resets.
4013 completes16/16 true starts for10s with zero fallbacks and max16.945cm target
error, below the original27cm threshold. Equivalent equations are not bit-identical
trajectories. Original native16x60s evidence is retained only for its older body;
it was not rerun or certified against the newer PHAT limits. The paired performance
comparisons use identical inputs/body settings on both sides. Historical impact
captures test the old recorded equations; the noisy and walking tests exercise
the current MJ body. Both saved policy hashes remain unchanged.
CPU packaging/stale-source/default-engine/PPO rejection checks also pass.

Rejected experiments: register/shuffle broadcasts (small benefit or slower and
more complexity), fully register-held motor impulses, streaming inverse rows,
and reciprocal multiplication in the seed (no sufficiently clear extra benefit
to justify changing its rounding). These exist only in ignored diagnostic files.
The retained seed cache preserves the original divisions and operation order.
An interrupted compilation was rerun; diagnostic import/path errors and
experimental compiler restrictions were corrected without affecting production.
Evidence, old source/receipt and rejected variants are under
`Saved/MimicKitLocal/solver_optimization/`; final reports are `physics_final.json`,
`ppo_final.json`, `noisy_final.json`, `regressions/` and `result.json`.
No production/cloud training resumed; Unreal, assets and user labs untouched.

**Earlier October16 projection optimization — historical baseline for this pass.**
User authorized maximizing performance without changing the matched physics.
Frozen, hash-checked pre-optimization kernels are under
`Saved/MimicKitLocal/optimization/reference/`; diagnostics and rejected experiments
remain in the parent directory. No cloud, Unreal changes or saved policy updates.
Current retained changes: exact zero correction for already-admissible joints;
precomputed bound parameters and per-substep inverse joint blocks; one complete
joint quaternion per GPU lane; compact joint-loop code generation; cached
effective constraint diagonals; skip remaining block sweeps only at an exact
unchanged-impulse fixed point. Seed50, final100, fallback3000, position20 and all
tolerances/torque caps/physical properties remain unchanged.

On alternating identical-input comparisons before the editor reopened, full
substep12.599ms ->7.526ms: **40.3% less GPU time /1.67x throughput**. Joint
projection4.878ms ->0.437ms (~11.2x); contact/motor solve7.473ms ->6.861ms.
The contact/motor solve remains the main cost; full physics is still about4.59x
vanilla on that fixture. Frozen pose-coordinate differences below3e-7 and velocity
differences below3e-5 on24 distinct impact inputs repeated across512worlds.
Independent20-case float64 projection control passes within5.63e-6, including
CUDA graph replay. No relaxed bounds, iteration counts, tolerance or motor laws.

Rejected: zero/eight preliminary sweeps, incoming-velocity/MJ/interior guesses,
short preliminary contact branches, extra shared impulse caching, conditional
zero-update branches,64-thread block solves and compact block-loop generation.
They worsened retries/cost or had no benefit. Seed25 looked faster on the impact
microbenchmark but caused224 fallback solves in131,072 noisy transitions versus
16 with retained seed50; keep50. Both noisy controls passed, no PPO updates.
Their roughly95s wall times include startup and active-editor contention and are
NOT a valid speed comparison against the earlier51.64s check.

**Earlier projection-pass PPO timing was inconclusive.** Unreal reopened at06:20 outside this
optimization job. It was left untouched. A later alternating, separate-RNG,
same-checkpoint paired benchmark completed6 disposable updates per version,
discarding the first. Reference26.73–35.81s/update; optimized9.56–42.38s/update.
Sample medians27.79/36.07s are preserved, not represented as a causal speedup or
slowdown. Even unchanged policy/optimizer times varied sharply. A separate
optimized-only measurement was likewise unstable. No idle-GPU whole-PPO speedup
is established by these data; do not turn the40.3% physics saving into a claimed
PPO improvement or claim the historical2.80x penalty versus vanilla is gone.
Reports: `optimization/update_profile.json`, `update_paired_editor.json`.

**Final correctness checks:** all four historical failure captures pass against
independent float64 equations (max3.69e-5), with CUDA graphs and deliberate
one-sweep rejection. Manifold/friction controls pass3 cases on both scalar and
block paths (max6.23e-5). Retained solver passes131,072 noisy transitions with
zero failures,16 explicit fallback solves/3,616 sweeps, no PPO updates. Accepted
checkpoint4013 completes16/16 true phase starts for10s again, max17.890cm under
the unchanged27cm threshold, zero fallbacks. This is a tracking acceptance check,
not bit-identical trajectories; previous max was16.957cm. Native rig/DLL and
checkpoint are unchanged, so native16x60s evidence is retained rather than rerun.
`verified_transfer.json` refreshed from `optimized_final4013.json` and the retained
native reports; previous receipt preserved in `optimization/reference/`.
Both4013 model and stopped700 archive hashes remain unchanged. CPU source-
inventory/stale-package/default-engine/PPO-rejection tests pass. Diagnostic PPO
weights were discarded; no production run, cloud spending, or Unreal changes.
Rejected candidate code was removed from runtime; evidence remains under Saved.

**Pre-optimization October16 performance audit — material overhead confirmed.** A proper paired
vanilla/current-profile benchmark was missing before the full-set launch. On the
local4060Laptop,512 worlds,1/240s substep,24 identical recorded impact inputs,
CUDA graphs, alternating order, warm compilation excluded: vanilla MJ1.641ms,
MJ+PHAT limits1.663ms, MJ+bounded motors1.745ms, full Jolt profile12.599ms per
substep (**7.68x** vanilla). Separate components: contact/motor solve7.473ms,
angular position projection4.878ms. Zero scalar fallbacks occurred: the recent
roundoff fix is not the source of this major overhead. These are different
physical equations, not evidence that vanilla can replace the transfer profile.

Complete disposable PPO-update checks (same checkpoint700/body/network/noise,
512worlds*32steps, six updates per engine, first excluded) measured medians
**6.581s profile versus2.350s vanilla (2.80x)**. Physics GPU time4.805s versus
0.694s/update; actor+critic optimization approximately0.355s versus0.370s, policy
inference0.059s versus0.056s. End-to-end trajectories/contacts/resets differ under
the two physics engines; the frozen-input comparison above is the controlled
physics comparison. No evaluation/checkpoint/replay IO in these update timings.
No weights were saved, no production training resumed, no physics settings changed.
Reports/scripts: `Saved/MimicKitLocal/performance_vanilla/{physics,update_profile,
update_vanilla}.json`, `benchmark_vanilla_transfer.py`, `benchmark_training_cost.py`.
The transfer implementation is working on tested RunLR cases but is NOT cheap.
Do not describe GPU residency alone as evidence of vanilla-like throughput.

**October16 crash diagnosis — training remains stopped.** The all27 run stopped
at03:49 after753 completed updates/12,337,152 samples. Its older running exception
handler left `status.json` saying training; process exit/failure.json are authoritative.
Status is now corrected to failed, preserving the old status in the diagnostic
receipt. Latest verified checkpoint remains iteration700/11,485,184 samples;
no rejected rollout was optimized or used to overwrite that checkpoint.

The exact first failure (world218, error6) is retained as
`first_failed_equations.npz`. It has two contacts, no active joint limits and finite
state. GPU replay reproduces a float32 velocity-update cycle: successive fallback
sweeps differ by5.364418e-6 indefinitely, above the unchanged2e-6 threshold, despite
motor residual1.373291e-4Nm (limit2e-3). This is accumulated rounding in incremental
velocity additions, not a changed reward, invalid network output or insufficient
GPU memory. Independent float64 equations reach the same solution within1.3e-5.

Fixed only the rare scalar fallback using compensated velocity summation (Kahan).
The original case now converges in256 sweeps rather than exhausting3000; residual
5.416870e-4Nm, maximum reference velocity difference1.260378e-5. Seed/fast block
solver, tolerances, iteration bounds, physics parameters and training configuration
are unchanged; still GPU-only and CUDA-graph compatible. Earlier saved equation
regressions pass, including deliberately insufficient solves remaining rejected.
A bounded512-world noisy rollout from the latest safe checkpoint passed131,072
transitions/256ticks in51.64s,14 fallback solves, zero solver errors and zero PPO
updates. This tests the fix, not learned locomotion or guaranteed indefinite stability.
Evidence: `Saved/MimicKitLocal/solver753/`. Main training has NOT been resumed.
The accepted Run LR4013 checkpoint also passes16/16 ten-second starts again,
max16.957cm, zero fallbacks. This is a fresh tracking check, not a bit-identical
trajectory claim or a repeat of the native60s suite. Report
`causal_transfer/solver753_compensated_4013.json`; consolidated source/capture hashes,
baseline diagnosis and checkpoint checksum are in `solver753/diagnosis.json`.
Reproduce the captured regression with `test_block_cycle.py --capture <npz>
--report-dir <directory>`; `test_solver_rollout.py <run> --out <report>` exercises
512 noisy worlds without PPO or weight writes. Existing pre-fix transfer receipt
hashes remain historical; do not bypass the stale-source check for a fresh launch.

**Stopped local training configuration:** fresh all27 approved clips (12walk,14run,1idle),
512worlds, run `2026-10-16_02-07-18_omni_idle_fresh_512`, bounded1000updates.
Fresh weights/optimizers/counters; idle mode−1 and direction[1,0]. Same physical
observations,1024→512→512 network,34 velocity actions, next-tick Phase E prediction
only, original four losses/noise.05/PPO/27cm termination. No cloud. One GPU job.
TensorBoard8035 and noiseless replay8021 use this dated run. Initial setup at
02-05 failed before PPO because an unrelated `replay.py` shadowed the intended
adapter; the runner now loads the intended file explicitly. No invalid checkpoint
was promoted. Status/rolling verified archive are under Saved/MimicKitLocal.
At100updates, noiseless mean episode increased5.10→5.50ticks and total weighted
loss5.923→5.099; this is still very early/poor locomotion, not a trained full-set
policy. All four loss terms and actual targets reach replay8021; TB tags verified.
After the1000-update segment, `evaluate_omni.py` is prepared to test all27 clips at
four starting phases each, retaining first episodes and separate per-clip results.
It refuses to run while the owned trainer is active. Syntax checked only so far;
do not treat this future suite as completed. No second GPU workload.

At300updates/4,931,584samples, stock noiseless evaluation has mean5.488ticks and
return0.865; this has not yet established sustained locomotion. Its reported
weighted loss2.464 does not by itself demonstrate recovery or good tracking.
Current PID must be checked alongside status.json. Future runner failure handling
now writes failed status and the original exception BEFORE downloading diagnostic
CUDA data, so a failed download cannot hide the original failure. Simulated
ordinary/CUDA-download failures preserve the checkpoint and pass. The active
trainer was not reloaded or restarted for this reporting-only change.

**Command audit:**27 clips use25 unique gait/direction pairs. Run BR/Strafe_BR and
Run FL/Strafe_FL share commands; at the same phase their largest key-body target
differences are46.77cm and39.45cm, respectively (pelvis XY aligned). These are
different styles, not duplicate files. The physical observation can distinguish
their poses, so this is not proof of an impossible task. No clips were removed,
no style input was added, and training is unchanged. Inspect the per-clip suite
before blaming poor learning on this. Numerical report:
`Saved/MimicKitLocal/prepared/repeated-command-audit.json`.

**Transfer acceptance so far:**100 local fine-tune updates from3913 produced4013
(65,765,376samples). Both MJ and native Jolt40velocity/8position complete16/16 true
animation starts for10seconds. Maximum target errors16.933cm/16.860cm respectively,
below the unchanged27cm bound, actual support from feet, limits enabled. No claim
of bit-identical trajectories. `verified_transfer.json` hashes the model, code,
fixture and reports. Native single-thread fixture mean2.426ms/policytick; this is
not a many-agent Unreal benchmark. Fine-tune99-update continuation took545.93s,
last10mean5.557s/update (~2949transitions/s),14 explicitly solved fallback worlds.
Final archive SHA256 `da515fbc1bde4ab324175e0e51c91c48fbb7247f53e68dbfa523d0923946e057`.

**Longer validation passed:** four native starts initially failed around29s,
when their pelvis reached Y≈−100m: the diagnostic ground box ends at−100m. The
character ran off the finite test floor. This is not evidence of a controller or
animation-clock failure. Original failed evidence retained as `long_run4013_native40`.
`test_native_long.py` builds a separate fixture with ONLY floor half-extent changed
100→1000m, preserving the accepted DLL/rig and enforcing a boundary assertion;
All sixteen60-second uninterrupted starts now pass, feet-only support and about190m
travelled each. First four maximum12.444cm; remaining twelve are recorded separately
in `long_run4013_native40_floor1000_remaining.json/.npz`. This includes the previously
failing phase0.375. Updated receipt combines all16 without counting any start twice.
Acceptance is flat-floor tracking with the original27cm bound, not exact frame
equality, arbitrary terrain/disturbance robustness or a live Unreal controller.

**Unreal inference prepared, editor still closed:**4013 exported to
`integration4013/runLR_actor.onnx`. Embedded normalization/action scaling/34-action
clamp and2 Phase E outputs verified against4,800 recorded observations plus extreme
random inputs, batch sizes1/7/64. Max differences7.63e-6rad/s and1.19e-6 respectively.
CPU ORT median0.243ms/single actor,1.519ms/batch32 under concurrent local training;
not an Unreal/NNE or idle-machine performance result. Two harder phase starts
0.375/0.625 also run60s in native Jolt using ONNX feedback, max16.546cm. This is
export/runtime verification only; no live Unreal actor or DLL was installed.

The successful phase0.375 MJ/Jolt10s recordings have also been mapped onto all88
original weighted bones for the existing comparison map. The15 physical anchors
and their collider-bone offsets reproduce the captures within7.2e-15m; only
display-root XY is centered. Prepared `skin_Newton4013.json`/`skin_Jolt4013.json`,
with source hashes and `accepted-skin-recording.json`. UE assets now imported and
displayed, as recorded in the current handoff above. `install_skin_preview.py` accepts
tags Newton4013/Jolt4013, then `refresh_bounded_preview.py --accepted-transfer`
verifies every imported frame before updating ONLY the dedicated map. Preserve
active Play/dirty packages; these remain recordings, not live UE inference.

**Idle admissibility:** independent dense128-subdivision check of all14 joint
profiles (1,075,214 samples) has zero violations, including5% angular margin.
No PHAT expansion or motion change needed. Reproduce with
`Labs/MimicKitUEFN/verify_motion_limits.py --idle`; receipt in Saved/MimicKitUEFN/idle.

**Original checkpoint controls:**3913 at40/8 passes13/16;100/20 passes16/16 with
24.061cm maximum error;255/20 passes16/16 with22.991cm. Solver accuracy contributes
to the original failures, alongside the reduced/maximal-coordinate finite-step
difference isolated below. Do not attribute everything to one cause. These are
rig-only overrides; gameplay Jolt remains unchanged. Reports are in
`Saved/MimicKitTransfer/no-armature-3913/causal_transfer/`.

The first noisy512-world attempt rejected one active-set cycle before PPO. Its
equations are retained in the `01-46_transfer_capture_512` run. Fixed damping is
not universally sufficient: the saved wrist case still alternates opposite90Nm
caps. The fast solver now explicitly invokes the existing scalar projected
equations ONLY for worlds whose active-set search fails. It uses physical mass
responses, bounded3000 iterations, and requires velocity change<2e-6 plus motor
residual<2e-3Nm; otherwise error6 remains fatal. No forces, caps or physical
damping changed. Three captured cases agree with independent float64 references
within3.69e-5, CUDA capture passes; the noisy case converges in176 scalar sweeps.
Fallback counters are per world (tile-lane0); the initial counter-only32x overcount
was caught and fixed. Counts/iteration totals are logged per update. The successful
smoke itself needed zero fallbacks. No silently accepted invalid solver state.

**October16 isolated equation evidence.** Backup9de076f6 is pushed and recovery
manifest verified; subsequent status/test additions may still be local.
The remaining finite-step discrepancy has been isolated. Same24 incoming states,
Jolt255 velocity/20position iterations, manifold friction and exact Jolt limit
axes: physical angular difference0.219743rad/s at1/240s; halving the step gives
0.123586rad/s. At the incoming pose, zero incoming velocity reduces solved
angular difference to6.215e-4rad/s. Removing only reduced-coordinate curvature
acceleration in an isolation control reduces that difference to5.668e-4rad/s.
These controls explain a reduced-versus-maximal-coordinate integration difference;
they are NOT training modifications. Never feed old-frame velocities or the
diagnostic compensation force to a policy. `phase9_impact_jolt_axes_accurate*`.

The block motor solver had an actual numerical active-set cycle. Damping ONLY
the branch-selection estimate (not accepted physical velocity), with a bounded
60-branch search, solves both captured failures and agrees with independent
float64 scalar equations within3.69e-5 generalized velocity. One case needed14
branches, so the former12 limit was insufficient. Final accepted state still
satisfies the original torque equation. Captured CUDA tests pass. Exact Jolt-axis
motion test now completes16/16 actual animation starts for300ticks, max23.625cm,
no solver errors, zero reported motor-equation defect; partial reset/velocity
Jacobian checks pass. Removing the50-sweep initial estimate then failed in5/16
worlds on the first tick and was rejected; it is not used for training.
The zero-seed failure was retained separately. The temporary `..._graph.npz`
scratch capture overwrote the earlier second failure; its independent CPU/GPU
reports remain, so do not describe that earlier raw capture as still retained.

**Lower Jolt iteration control, checkpoint4013:** default10velocity/2position
passes0/16 ten-second starts;20/4 passes13/16 (failures at129,31,22ticks). Same
checkpoint, physical resets, materials, limits and tagged contact profile as40/8.
Thus40/8 remains the accepted rig-only override; do not advertise transfer at the
global gameplay defaults. Full reports `local_finetune4013_phases16_self0_native_point`
and `..._native_v20p4_point`. Timings here overlapped other local work and are not
a valid clean performance comparison. No gameplay settings or training changed.

`compare_batch_native.py` now also accepts per-motion first-episode captures from
`evaluate_omni.py`. A300tick accepted phase0.375 control through this adapter is
bit-identical to the prior Jolt state/action arrays. It labels a short MJ episode
as a short comparison, never full-horizon success. The pending GPU evaluator
also records ground forces and failure causes; these forces sample the last
substep, while the native report integrates all substep ground impulses.

A CPU-only early all-motion reset reconstruction was investigated and rejected:
it differed from captured GPU resets by about0.103mm position,0.000131 quaternion
component and0.000602rad/s angular velocity, despite identical source motion
hashes. Adding the actual joint-DOF round trip did not eliminate it. No tolerance
was relaxed and no policy trial used those approximate resets. The temporary
reconstruction code was removed; failure logs remain in Saved/MimicKitLocal.
Final per-motion transfer checks will use actual GPU-captured initial states.

`contact_engine.py` is the explicit local engine used by both successful fine-tune
and current fresh run. `train_local.py` restores complete archives or starts fresh,
checks latched solver errors before PPO, and keeps one rolling verified archive.
No cloud calls. Future omni training now selects this verified profile by default,
requiring zero added armature; an explicit opt-out only reproduces historical
diagnostics. Both package builders include the same eight contact modules, and
cloud launchers reject stale source before allocating/extending. No cached cloud
bundle was uploaded or deployed. Shared PPO guard checks solver errors once per
rollout before optimization. CPU source-inventory/default-selection/fatal-guard
tests pass. The already-running local job uses the identical explicit class and
was not restarted. Installed gameplay Jolt remains unchanged; native tests use
the separate point-contact DLL. Original PHAT, user assets and D/S are untouched.

Unreal13040 was closed gracefully for local GPU/RAM headroom. Only our comparison
PIE ended. Dirty PoseAgent was saved with its previous disk bytes preserved in
`Saved/MimicKitTransfer/headroom-close`; no other dirty packages existed. Receipt
records both hashes. The visible comparison remains the older failed motion on
disk; no updated UE visualization claim. Reopening still requires checking the
current normal-build state and preserving other branches' source changes.

### Earlier diagnostic evidence (current results above supersede pass/fail status)

**October16 direct-reset comparison supersedes the easier
post-first-step starts below.** The manifold/shared-projection MJ trial completed
16/16 starts for300ticks, max target24.12cm, body-velocity error6.13e-4. Starting
native Jolt40/8 from the actual animation reset (before ANY MJ step) completes
13/16: phases0.375/0.625/0.9375 fail at32/237/224ticks. Initial observation mapping
max8.01e-4. This is still failed transfer. No training, UE changes or profile
promotion. The editor continues showing the earlier failed comparison.

The newer comparison NPZ includes `initial`; native history index0 is that reset,
then index1 equals MJ states index0. The divergence audit now respects this offset.
At phase0.375 the first tick differs1.08mm; by tick5 the foot differs3.20cm and
4.55rad/s, with closed-loop actions already diverging. Do not use the earlier
post-MJ-step15/16 result as acceptance evidence.

Manifold/spin GPU equations pass independent float64 CPU checks on3 impact
states, max generalized-velocity error6.23e-5 scalar/5.07e-5 block; CUDA capture
passes. Shared-memory split projection passes20 cases within5.624e-6 and repeats
bit-exactly.512-world full-substep benchmark34.47ms, separate solve21.65ms and
projection14.50ms (separately timed laptop kernels; do not add them). Still not
acceptable final training throughput. `contact_manifolds_gpu.*`,
`contact_solvers_benchmark_shared_manifolds.json`.

New isolated Jolt hard-limit axes reproduce world-space construction across240
rotations. Active swing-axis error7.87e-5 (unnormalized cross error8.85e-8);
normalizing nearly zero boundary crosses amplifies float32 roundoff. The original
2e-5 unit-axis assertion failed; test now explicitly checks both1e-4 axis and1e-6
unnormalized error. This is a numerical test tolerance, no physics threshold.
Same-state24-impact test remains~0.231rad/s at the foot; axes alone do not remove
the remaining mismatch. Full motion with those axes then hit block active-set
nonconvergence (error5) after tick30. Trial rejected; exact first-substep failure
capture is in progress. No silently accepted solver fallback.

Velocity-transport isolation: at one-point impacts19/21, comparing the solved
velocity before changing the joint coordinate frame reduces foot difference
0.071/0.100 to0.021/0.022rad/s. At two-point impact31 it remains0.227rad/s.
This separates finite-step articulation transport from remaining contact response;
stale velocities are NOT fed to the policy. `velocity_transport.*`.
Actual primitive collider depth in all4800 saved MJ frames stays above−1.715cm,
within Jolt's2cm penetration slop, so missing floor position projection is not
active in that recording. `*_ground_depth.json` (policy-boundary sample, not proof
about every intermediate physics step).

Local dataset preparation: `prepare_local_omni.py` writes only configs/manifests
under `Saved/MimicKitLocal/prepared`,27 clips (idle1/walk12/run14), equal clip
sampling, original four loss weights, idle−1/direction[1,0], fresh weights/counters
planned. No training launcher invoked; transfer remains prerequisite.

**October16 current continuation, backup `a2e5ce72` pushed.** The block motor
solve plus parallel split projection completes16/16 evenly spaced starts over
300ticks/10s with the unchanged3913 actor, max key-point distance24.05cm, no
invalid solver flags. Final generalized motor-equation residual is zero to
float32 reporting precision; body-velocity/Jacobian max difference4.22e-4,
partial resets and captured CUDA execution pass. The previous scalar1000-iteration
trial completed15/16 (phase0.4375 failed223ticks). Numerical convergence matters;
do not combine these records or describe either as new training.

Native Jolt40velocity/8position from the new trial's initial states completes
15/16: phase0.1875 now fails44ticks. Earlier scalar-trial initial states had a
different late failure. Thus trajectory success is still sensitive and transfer
is **not accepted**. Native100/20 is being checked separately. All successful
native support is through feet. Installed DLL, active fixture and editor are
unchanged; the visible comparison still shows the older failed transfer.

The scalar seed50 plus block active-set solve100 passes all24 saved impact
equations (max motor defect1.91e-5Nm). Shared-block angular projection matches
the independent float64 reference over20 cases within5.624e-6 generalized pose
units; captured replay repeats exactly. Its first attempted tile-map signature
was rejected at compilation (array arguments unsupported); replaced with explicit
per-thread joint updates, then verified. No failed result was promoted.

512-world identical-impact benchmark: original scalar/full split correction
177ms per physics substep; block+parallel projection35.79ms, including collision,
motors, contacts, integration and split correction, excluding policy. Separate
component captures: solve14.41ms, projection19.71ms. These are diagnostic laptop
timings with Unreal open; neither claimed full training throughput nor acceptable
final optimization. No second GPU workload and no cloud spending.

Jolt tangent metric/manifold CPU isolation now includes joint-level torque caps
(the earlier uncapped diagnostic numbers are invalid and retained only as failed
evidence). One-point angular differences .1489→.07073rad/s and .1372→.09939 when
using Jolt's contacting-body tangent metric. Two-point manifold-centred friction
plus spin row reduces .2336→.2311rad/s; residual integration/constraint accuracy
remains. GPU manifold preparation/solve is currently under independent CPU-reference
test, opt-in diagnostic only. Evidence `friction_metric*.{json,npz,log}` and
`contact_manifolds_gpu.*` when complete.

Idle command contract now accepts−1, with direction[1,0]; walk0/run1 unchanged.
Three-mode subset/reset/phase-wrap/next-tick Phase E tests pass. This does not
launch training or alter the existing approved26 gait clips. Full dataset/idle
local training still awaits transfer verification.

**October16 continuation — the remaining impact causes are now isolated.**
Combined hard contact, hard-limit velocity and split angular correction passes
all16 phases for90ticks/3s, max target22.13cm. Previous baseline failed phase0.375
at15ticks. Partial reset and reported-body-velocity checks pass; captured GPU
execution stays finite. Motor equation residual peaks0.00571Nm. Ten-second
extension is running; native Jolt40/8 from those corrected initial states also
passes16/16 for89native ticks, peak target21.15cm, all ground support throughfeet.
No transfer acceptance yet: duration/force residual/overhead checks remain.
`contact_soft_limit_trial_cuda_0_relaxed_hard_project_worlds16.*`.

`phase9_impact.json` starts24 one-substep trials from the exact same incoming
states/commands/forces. Current MJ reproduces the captured reference velocities
within1.82e-5. Native vs MJ right-foot angular-velocity difference peaks4.09254rad/s;
without contacts it is0.10030, without friction2.37257. The experimental hard
normal/sequential-friction solve reduces it to0.23407. Remaining0.98838rad/s
head discrepancy disappears when the angular row is changed from soft MJ bias/
compliance to a hard zero-normal-velocity rule: overall maximum then0.23351rad/s,
at the foot. Removing limits in BOTH engines gives the same foot result0.23363.
This separates contact response from soft-limit response; neither is an actor,
input mapping or missing controller update. Evidence `phase9_impact_limits.*`.

Split angular-position correction was independently tested with no gravity,
contact, motor or incoming velocity. Mass-weighted generalized correction moves
root/parents as well as the joint; it does NOT clamp local pose with parents fixed.
Against Jolt20 position steps, four cases differ by at most0.221mm/0.0574degrees;
COM drift<5.1e-8m and velocities remain exactly zero. `probe_limit_projection.py`
is CPU reference only. GPU version passed20 cases against the independent float64
implementation, max generalized-pose difference5.63e-6, repeatable CUDA graph replay.
The CPU reference initially re-used other joints' old error within an iteration;
corrected it to re-evaluate each constraint at its turn, like Jolt and the GPU.
Its per-substep mass metric is frozen during angular relinearization;
this approximation is explicit, and not yet accepted for training.

Performance experiment: analytically eliminate unsaturated motors, solve contacts,
then update saturated motor set. CPU worst saved case converges with two motor
active sets and100 contact iterations (contact residual6.95e-8Ns), compared with
1000 full scalar iterations previously. Tangent projection metric MUST remain
unchanged when eliminating motors: substituting the effective inertia changes
sliding-friction direction. GPU active-set trial rejected4/24 impact cases with
an explicit nonconvergence flag. A short scalar-solve seed is being tested;
the combined motion trial continues using the validated1000-iteration solve.
Jolt's actual per-body tangent metric and manifold-centred friction still require
matching; the current reduced-coordinate point-contact prototype is not claimed
as exact Jolt physics. No training or engine installation during these tests.

Idle retarget preparation now succeeds separately (601frames/10s, mode−1,
direction[1,0], phase offset0). Existing clips/viewer were not overwritten.
Float32 FK verification changed from per-matrix-entry1e-6 to angular error2e-6rad,
and positional absolute tolerance from0.5 to1 micrometre after measured0.566um
round-trip error; unchanged bones/legs still require exact equality. These only
change verification, not the retargeted trajectory. Candidate remains unpromoted
until physics transfer passes. `Saved/MimicKitUEFN/idle/retarget/manifest.json`.

**Resume here after backup `985bfe14` (pushed):** broader testing prevents accepting
the four-phase result below as the finished match. Current MJ completes15/16
evenly spaced starting phases over10s; phase0.375 fails at tick15. Native with
matched self friction and100 velocity/20 position iterations completes14/16;
phase0.375 fails at22 and phase0.5625 at11. The cheaper40/8 profile likewise
fails the latter at10. Rig-only8 position steps, with default10 velocity steps,
already passes the original four phases, so the necessary correction there was
position solving, not simply more velocity iterations. No limits were removed
in these passing tests. All measured ground support comes through feet.
Native40/8 measured roughly4.7–5.5ms per policy tick (eight240Hz steps),100/20
roughly8ms, on the active laptop with Unreal open; these are diagnostic timings,
not a shipping/many-agent benchmark. Default10 velocity iterations still leave
large motor-equation residuals;100 reduces but does not eliminate them. Do not
claim exact dynamical parity from survival.

The separate per-point contact DLL was combined with the same rig settings using
a local include-header overlay (`build_point_profile.py`); installed DLL/source
unchanged. It still fails phase0.5625 at11. Saved trace audit finds<0.5mm position
and0.054rad/s angular-velocity discrepancy after the first native tick, followed
by6.49rad/s right-foot discrepancy at the next tick. Incoming state matches to
serialization precision. `probe_phase_impact.py` completed identical-state/
command controls over steps8–31; results are above. Shared-engine CPU capture
`body_velocity_engine_cpu_phase0.5625.npz` passed velocity/reset checks. This
remaining contact failure is why full-data training has NOT started.

Comparison harness now materializes NPZ arrays once instead of repeatedly
decompressing the complete recording per frame. Interrupted the owned, redundant
uncached16-phase diagnostic and reran it; no trainer/editor interruption. Outputs
are `body_velocity_engine_cuda_0_worlds16*`, `native_point_16phases.log`,
`divergence_world9_point.json`, and `phase9_impact.*` when complete.

Idle source preparation only: read-only export of the original project breathing
idle `/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop`,
601frames/10s, to `Saved/MimicKitUEFN/idle/`. This is the original animation,
not an NN continuation. No retarget/training promotion yet. Editor13040 remains
in the owned comparison PIE; editor-world accessor is null during that session,
game-world path and dirty PoseAgent checked unchanged. Exporter first rejected
that null accessor, then ambiguous duplicate idle names, before explicitly using
the same source as the existing breathing exporter. No asset save/UI change.

**Latest result: first four-phase native transfer pass, not yet promoted.**
The current corrected MJ baseline completes all four300-tick trials. Matching
self-contact material and increasing Jolt solver accuracy to100 velocity/
20 position iterations also completes all four299 native ticks after the common
initial MJ tick. Native peak target distances19.65/17.05/18.25/15.40cm; final
horizontal-aligned MJ body-position deviation9.16/5.25/6.01/4.73cm. Thus this is
a functional checkpoint-transfer pass, NOT identical trajectories or complete
physics equivalence. Observation mapping verified within1.82e-5. No policy
fine-tuning, physics library install, editor change, or training. Evidence:
`body_velocity_engine_cuda_0_self0_highiter_native.{json,npz}`.

The material error was **self** contact: MJ body shapes use condim1, which is
frictionless; native Jolt previously applied body friction1. Ground remains
friction1/rest0 in both. The isolated callback now has an opt-in override only
when BOTH tagged bodies belong to the SAME rig group. Other contacts are untouched.
With self friction corrected but original solver accuracy, native fails after
78/138/28/24ticks. With limits removed as an isolation control it fails25/37/31/25;
limits were NOT removed from any accepted configuration. High solver accuracy
without this self-material correction had failed in earlier controls.
`build_timestep_fixture.py` adds independent body/constraint iteration overrides
using stock Jolt APIs, separate timing and equation/anchor diagnostics. The
currently running controls separate100 velocity/default position from default
velocity/20 position. A16-phase MJ baseline is being captured for broader checks.
Do not assume100/20 is required or accept its cost without these tests. Installed
Jolt DLL and active fixture remain unchanged.

**Contact prototype convergence resolved, but prototype remains diagnostic.**
The captured worst two-contact/two-limit problem alternates between two solutions
even at3000 full iterations; it is not merely a slow solve. A0.5 iterative
relaxation factor converges to the SAME equations (not added physical damping):
float64 motor residual2.8e-6Nm by1000iterations. The resulting captured GPU
four-phase60-tick replay stays finite, with max residual1.11e-3Nm and max target
errors24.64/16.28/16.04/20.38cm. This still retains soft MJ limits, lacks Jolt
position projection/manifold friction and is too costly to promote. Prefer the
stock Jolt rig-profile route above if broader verification succeeds. Files:
`probe_contact_convergence.py`, `contact_convergence*.json`,
`contact_soft_limit_trial_cuda_0_relaxed.{json,npz}`. Production training continues
to use the existing MJ solver, not this contact experiment.

**Continuation after backup `d2627598`:** the body-velocity reporting correction
is now in the shared UEFN engine (`Labs/MimicKitUEFN/body_velocity.py`). It reads
current Newton generalized velocities, whose root is world COM velocity and
whose ball velocities are MJ child-local, before every drag/gyro calculation and
after the final substep. Both launches are captured on GPU. It does not read stale
MJ state on reset, change joint qvel, alter body poses, or replace the solver.
`test_body_velocity_engine.py` checked104 CPU substeps and partial resets; max
error versus independent MJ Jacobians5.91e-4 (m/s or rad/s by channel). Captured
CUDA test passed four300-tick/10s trials: max target errors19.02/21.01/17.83/17.14cm,
all end by horizon. Partial reset of worlds0/2 leaves worlds1/3 unchanged. CUDA
velocity error4.22e-4. A separate upstream control-boundary exp-map/quaternion
roundtrip moves FK positions by up to0.032mm; reported separately, not concealed
as velocity error. Previous pure-kernel test remains9.36e-6 on exactly matched
transforms. The reference animation already uses child-local velocity rotation.
This fixes a real force/reward reporting defect; it does NOT establish Jolt parity.

Both normal and no-armature package builders now include the required velocity
adapter; start/deploy checks reject a stale package. Refreshed local omni package
SHA `4a3dca6752dc5828cbb7163837701880ba95dddd67de125bade4a77caa03e7a5`,
578051bytes. No training, deployment or checkpoint change. Original frozen source
and installed Jolt DLL remain unchanged. Dedicated evidence:
`causal_transfer/body_velocity_engine_{cpu,cuda_0}.json`.

**Free-motion integration isolation:** `build_timestep_fixture.py` links only the
unchanged installed Jolt DLL. `probe_free_integration.py` disables gravity, motors,
drag, contact and limits, uses actual gyro cancellation in MJ, and compares three
recorded states, zero velocity and rigid spin at120/240/480/960Hz. Zero-velocity
states remain stationary (position discrepancy below0.4micrometres). Recorded
step8 angular velocity error0.684/0.341/0.170/0.0849rad/s respectively; position
error0.585/0.147/0.0372/0.0101mm. Step160 rigid-spin angular error similarly halves
0.114/0.0570/0.0285/0.0143rad/s. Thus even free articulated integration differs at
finite timestep, separate from contact/limit errors. Jolt's maximal-coordinate
velocity constraints plus later position correction are not identical to MJ's
continuous articulated acceleration constraints. This is not an export mass/axis
fit or license to remove physical Coriolis terms. No timestep changed in gameplay
or training. Evidence `causal_transfer/free_integration.json` and `timestep/build.json`.

An explicit diagnostic-only extension of `sequential_contact_adapter.py` can
retain MJ soft joint-limit rows while replacing contact friction, to isolate the
effect in a complete motion. It is NOT the final Jolt limit implementation and
is NOT a training default. `test_sequential_soft_limits.py` must pass its separate
CPU-equation/stock-MJ check before that experiment is accepted. It now passes:
six states on CPU/CUDA, velocity error below7.7e-6 versus both the independent
float64 equation solve and stock MJ, motor defect below2.3e-5Nm. Initial Warp
compile rejected a mutable constant bool; corrected to a dynamic bool. Full-motion
diagnostic's first construction was correctly rejected because Newton defaults
to sparse inertia; its isolated constructor now explicitly requests dense storage
(same equations/settings), leaving production source/defaults unchanged. Full
transfer and fresh full-dataset+idle training remain outstanding.

The first complete contact-control replay is **rejected**, preserved as
`contact_soft_limit_trial_invalid_v1.{json,npz}`. It produced nonfinite states at
policy ticks8/4/1/2. The numerical test originally used NumPy's equal-NaN default,
so matching invalid arrays escaped that assertion; explicit finite checks now
reject them before accepting/reporting motion. CPU tracing preserves the first
bad solve in `contact_first_invalid_v1.npz`. Initial interpretation was inactive
candidates with stale addresses. **Further tracing corrected that diagnosis:**
`contact_first_invalid_v2.npz` includes distances/margins and shows two extra
penetrating frictionless contacts (condim1). The prototype only supported condim3,
but incremented its contact count before rejecting the type; unused slots had
zero Jacobians and caused division by zero. Its error flag was also cleared each
substep, allowing a later step to hide the failure. The adapter now explicitly
supports condim1 and3 with per-contact friction, validates before adding a slot,
and latches errors. It also requires an active penetrating point because MJ can
retain stale row addresses outside the active margin; that is a separate valid
guard, not the cause of this captured failure. No denominator clamp or invented
force. Added mixed-type/inactive/stale-row regression. Re-running the equation
suite and motion control before accepting it. Production remains unaffected.

Mixed-type fix now passes the CPU/CUDA contact equation test (velocity error
1.42e-5), explicit inactive/stale-address and frictionless-contact regression,
and soft-limit control tests (7.7e-6 versus stock/independent equations). The four
60-tick CUDA motion controls remain finite and below27cm: maxima24.47/16.30/
16.08/23.16cm. Partial reset and graph replay checked. **Still not admissible for
training:** maximum motor-law residual in that full contact solve is12.54Nm at
100iterations, whereas sampled one-step tests were below3e-5Nm. Convergence in
the complete contact manifold needs work before promotion. No success claim from
this short replay. Native comparison uses the captured same phase/reference and
friction1/rest0 to isolate response rules; results follow in
`contact_soft_limit_trial_cuda_0_native.json` when complete. Current full-replay
evidence `contact_soft_limit_trial_cuda_0.{npz,json}` supersedes its invalid v1.

**Latest progress / resume here:** precautionary snapshot committed
and remote ref verified: `c2f6a742` on `origin/codex/standalone-sim`. It contains
the physical-training/retargeting/transfer source and dedicated journals. Other
chats' modified Blueprints, PHAT and reach/D/S files were left unstaged/untouched.
No cloud spend, no training, no editor restart. Goal remains incomplete.

Contact law is now isolated numerically. `probe_sequential_contacts.py` uses the
same articulated mass matrix and forces as MJ, with Jolt's sequential capped
motors, friction disc (bounded by the preceding normal impulse), then hard normal
impulse. In sampled step160 with friction1 and limits off, max angular-velocity
error falls from hard-MJ-pyramidal5.15rad/s to0.052rad/s; normal impulse0.608 versus
native0.571N.s. Six states8/24/48/80/112/160, friction0/1,10/100/1000iterations.
100 and1000iterations agree; no-contact residual0.05–0.12rad/s is separate
articulation/integration/force work. This is NOT a completed full-trajectory match.
Files: `causal_transfer/sequential_contacts.json`, per-state `sequential_*.npz`.

`sequential_contact_gpu.py` reproduces this independent CPU reference on CPU and
CUDA within1.23e-5rad/s; motor equation defect below3.4e-5Nm. CUDA graph replay
verified. Serial implementation was too slow (~53–87ms for512worlds/100iterations);
tiled version ~10.8ms with Unreal still running. This only times the prepared
equation problem, not complete physics or training. Still too costly to promote
without further work; don't call this optimized. Native Jolt remains unchanged.

`sequential_contact_adapter.py` integrates those equations into the actual MJWarp
step, model-scoped dispatcher, with GPU inertia inversion/contact Jacobians and
no per-step CPU readback. `test_sequential_contact_adapter.py`: all six same-state
inputs match CPU within1.42e-5rad/s, including captured CUDA replay; motor defect
2.29e-5Nm. It deliberately REQUIRES disabled limits/equalities, uniform friction,
condim3 and dense articulated inertia. It is an isolated test, NOT a training
default or full solver. Angular-limit projection, manifold friction (versus
per-point friction), position projection and residual integration are outstanding.
No environment/reward/default was changed. Evidence `sequential_adapter.json`.

**Rig-only speculative-point correction candidate:** `build_point_contact.py`
produces `point-contact/fixture.exe` plus a separate DLL; NEVER installs it in
Unreal. `rig_point_contact.patch` adds default-true
`ContactSettings::mEnableSpeculativeContacts`. Tagged-rig listener setsfalse:
separated points carry zero response even within a penetrating manifold; friction
center/torsion count only responding points; position solve skips inactive rows.
Original contact cache/order retained, persisted points reactivate normally.
Stock/unmarked dynamics are exactly identical across31policyticks/all15bodies.
Sphere regression passes, unmarked difference0, vs global zero-spec reference
9.37e-19, solid/persisted contacts confirmed. Step48 frictional same-state error
falls1.25->0.19rad/s when the separated extra corner is excluded.

The candidate alone does NOT make transfer pass: current checkpoint fails at
12/5/24/20ticks across four phases, versus original12/8/24/20. Do not promote or
claim matching because its local contact behavior is correct. Active fixture and
Unreal preview remain on the original installed DLL; this candidate is explicit.
Tests: `test_point_contacts.py`, `point-contact/{verification.json,build.json}`,
`causal_transfer/sequential_point_contacts.json`. The build restores dependency
source bytes in finally; installed DLL SHA remains
`69137ccc0b5b7dee38cf05a801254d2b06cfbfb9e105131960453c38a8147449`.
Intermediate build DLL is the candidate; subsequent ordinary builds recompile the
restored source. First fixture compilation failed under Windows PowerShell's
script policy; source restored, rerun with normal pwsh succeeded (no OS policy
change). GPU tile compiler rejects some1D shared-tile assignments;2D tile version
passes without modifying Warp/site-packages.

Next: finish remaining dynamics differences, particularly angular-limit response,
manifold friction and maximal-vs-articulated integration. Also fix/verify the known
Newton body-velocity reporting bug before fresh training: ball qvel is child-local,
while Newton FK interprets copied velocities in the parent frame. Old diagnostic
`audit_force_velocities.py` uses exact Jacobians only for forces; this is not yet
fixed in the shared engine. Avoid fitting compensating force offsets. Revalidate
the full saved actor over phases and sustained real support before training the
full dataset. Idle is still outstanding. Production training defaults and the
checkpoint remain unchanged.

`actual_body_velocity.py` now independently reconstructs real COM velocities
from MJ child-local joint velocities and current body transforms. All256 saved
physics states/all15bodies match the independent MuJoCo Jacobian reference within
9.36e-6 on CPU and CUDA; graph replay verified, measured0.149ms for256states on
the local GPU with editor open. No pose/velocity/physics state is changed by this
test. Before promoting, wire it after solver output (not into generalized qvel),
and explicitly verify reset synchronization and first-tick behavior: Newton's
cached body velocities can be stale during reset, while MJ state isn't copied
until stepping. Current evidence: `causal_transfer/actual_body_velocity.json`.
Its first attempt imported the environment's other MuJoCo version before probe
selected pinned dependencies; binary model load correctly rejected it. Import
order corrected, tests rerun. No library installation changed.

User authorized a precautionary Git push, continued local transfer diagnosis and
local training after a verified match. Preserve general Jolt gameplay rules; prefer
rig-scoped Jolt settings where they remove a mismatch without affecting other
bodies or adding substantial overhead. Otherwise match MJ training to Jolt.
No cloud rental or spending. Do not substitute checkpoint success in MJ for a
verified transfer. Fine-tune the existing checkpoint locally only if needed.

After transfer is verified, train from fresh weights/counters on the full approved
omnidirectional dataset, including idle: locomotion input -1, direction angle 0;
walk remains 0 and run 1. Start with 512 local worlds, reducing only if memory
requires it. Unreal may be closed after preserving user work. Retain the existing
1024/512/512 network, physical state plus mode/direction/phase inputs, next-tick
Phase E prediction, four world-body tracking terms and approved termination rules.
These are outstanding requirements, not completed work.

Latest four-phase current-runtime native verification fails at 12/8/24/20 policy
ticks; report `causal_transfer/live_native.json`. The matching MJ recording lasts
300 ticks for all four starts. No contact/limit change has yet been promoted.

### October15 evening: current-runtime retest and causal contact diagnosis

**Supersedes the prototype rollout/preview numbers below. Transfer still fails.**
User challenged the incomplete diagnosis; continued contained CPU tests using the
exact native project DLL. No paid compute, checkpoint changes, production physics
changes, original PHAT edits or unrelated Unreal work.

**Evidence correction:** the earlier coupled prototype cached Newton's initial
2ms timestep before Newton changed it to1/240s. The production motor adapter was
corrected to read the live timestep, but its four-phase recording was not regenerated
before the prior preview update. This was an evidence/verification error, disclosed
to the user. The historical `coupled_integrator_batch` is NOT the current runtime.
Its recorded torque has a205.23Nm maximum defect against the real end-step motor
law; it agrees within1.28e-4Nm only when acceleration uses the old0.48 timestep
ratio. Keep it as historical evidence, not a current-runtime success test.

Fresh `coupled_live_dt_batch` runs the CURRENT motor code at240Hz, checkpoint3913
unchanged. Four starts0/.25/.5/.75 ALL complete300ticks/10s. Peak target distances
18.76/19.46/15.64/13.99cm. Large ankle reversals0 and opposite near-cap torque pairs0
in all four. Independently recomputed actual end-velocity motor defect1.264e-4Nm.
Runtime221.63s on local CPU for four worlds; no GPU throughput claim.

Current Unreal map uses new `AS_JoltLiveMotor_3913` / `AS_NewtonLiveMotor_3913`,
121frames/4s at0.25x, synchronized recorded playback. MJ comes from the fresh
four-world capture. Jolt starts from that exact physical state and continues
past27cm failure at12ticks/0.40s, without reset/support. Repeating its first five
frames from identical state/commands reproduces exactly. All88bone imports match
within1.15e-4cm /1.29e-4deg. Old Bounded assets remain historical. User's dirty
`BP_ProphecyManualPoseAgent` remained dirty and unsaved. Only our owned comparison
Play was stopped/restarted. Current receipts: `live-motor-map-recording.json`,
`live-motor-preview-refreshed.json`, `live-motor-preview-playback.json`.

**Causal controls, same commands versus feedback:** `diagnose_causal_transfer.py`
records32ticks from a one-world current-runtime MJ run. Exact CPU batch sizes can
differ slightly numerically; do not conflate its13tick failure with the four-world
initial state's12tick failure. Native with its own policy feedback fails at13ticks;
replaying the exact MJ commands still fails at21ticks. Thus feedback amplifies an
existing physics discrepancy; it does not originate it. Removing drag, limits,
changing friction/restitution to training values, or100/20iterations does not
solve it. Feet diverge first, then body height. At tick5 worst relative body error
3.09cm; tick10 14.02cm; tick15 40.78cm. Angular body speed remains below19% of native
caps before failure. Evidence in `causal_transfer/{reference,closed,open,...}.npz`
and `summary.json`; all changes are diagnostic-only.

**Same-state tests:** `diagnose_contact_sources.py` reconstructs exact generalized
state from saved rigid-body state, checks the reconstruction, then compares one
240Hz step with identical commands. Six sampled substeps8/24/48/80/112/160; controls
remove contact/limits and independently replace force-input velocities. Complete
MJ replay reproduces recorded output within about4e-6rad/s in the shown sample.
At step160 full angular-speed discrepancy1.694rad/s becomes0.293 with contacts off;
with contacts/limits off and100/20native iterations it is0.030rad/s. Exact drag/gyro
input velocities barely change this contact discrepancy. At step48 angular-limit
projection separately causes1.51degrees pose discrepancy even without contacts.
Earlier zero-velocity limit tests explain this: Jolt directly projects position;
MJ applies a soft acceleration. Geometry alone cannot match those responses.

**Contact geometry vs response:** dedicated `contact-observation.exe` is a copy of
the native fixture with read-only manifold telemetry and diagnostic material knobs;
active_fixture.json and live DLL remain untouched. Real lowest-corner positions
and penetration depths match to hundredths of a millimetre. At step160 the same
single contact produces upward impulse MJ1.827N.s /Jolt0.520N.s; matched material
numbers alone give native0.454N.s, not parity. MJ contact normal uses solref
0.0175s/1 and solimp0.9/0.97/0.002; native uses its hard unilateral impulse solver.

**Previous per-rig speculative filter is incomplete for manifolds:** when one foot
corner penetrates, the manifold can also contain a separated corner1.67cm above
the floor. Rejecting only wholly separated manifolds leaves that point active.
Setting speculative distance0 in the isolated fixture removes that point in the
observed case, but manifold tolerance can still retain another0.75mm separated
point. This setting is NOT a complete per-point filter and is not promoted.
Closed-loop no-speculative diagnostic fails19ticks; with100/20iterations30ticks;
training material variant11ticks. Open-loop still fails21ticks. Thus premature
contact is a real flaw, but eliminating it alone does not solve transfer.

**Normal/friction separation:** with limits off, matching single-point geometry,
friction disabled and100/20native iterations, changing MJ contact rows ONLY in
an isolated same-state test from soft to the hard end-velocity equation reduces
step160 angular discrepancy0.591->0.0465rad/s, impulse0.134->1.190N.s versus native
1.122N.s. This identifies normal compliance as a cause, not arbitrary tuning.
Diagnostic standard MJ settings: direct solref[0,-240], solimp first two0.9999.
Reintroducing equal friction1 leaves a large difference: MJ pyramidal cone
2.987N.s upward versus Jolt0.571N.s. Elliptic MJ cone still2.760N.s; it is not
merely square-versus-circular cone geometry. Normal/tangential response differs.
Do NOT promote hard-contact parameters as a complete fix; they worsen some
frictional comparisons. `causal_transfer/contact_law.json` records actual momentum
changes as well as constraint impulses. Finite-step articulated integration leaves
small additional momentum/velocity differences; no claim of full exact parity.

Harness safeguards: native initialization now uses a unique temporary file per
fixture, avoiding possible cross-process collisions in the old shared initial.txt.
A batch-vs-single close-state prefix comparison was rejected; deterministic native
repeat now uses exactly the same state. A diagnostic ZERO friction with condim3
became ill-conditioned and failed; discarded, replaced with true condim1 frictionless
contact. The training-material flag mapping typo in that diagnostic was caught
by logged actual friction/restitution and fixed; rejected log retained. These
failed controls were not accepted as scientific results.

Current conclusion: geometry/mass/observation conversion are not sufficient for
transfer. Remaining demonstrated differences are normal contact compliance,
friction/normal coupling, angular-limit projection, and an incomplete speculative
manifold filter; finite solver convergence/integration contributes as well.
User chose matching MJ to Jolt, then clarified a preference for safe rig-scoped
Jolt changes where available, to avoid unnecessary training-side overhead.
No contact/limit changes or new training have yet been promoted.

### October15: Unreal comparison updated to corrected bounded motors

User requested the current corrected motion in Unreal. Read-only inspection found
the dedicated `M_JoltTransferFailure` map still playing old `AS_JoltContact_3913`
and `AS_NewtonCompare_3913`, with no Play session and a clean map. The unrelated
`BP_ProphecyManualPoseAgent` dirty package was preserved without saving it.

Added separate `AS_JoltBounded_3913` and `AS_NewtonBounded_3913` assets and updated
only this comparison map. Right: corrected MJ phase0 recording from
`coupled_integrator_batch/raw.npz`. Left: unchanged checkpoint3913 with current
native contact fixture, initialized from the same corrected-MJ state at tick1,
continued for4s without reset/support after the27cm threshold fails at tick16
(0.533s). Native prefix matches `corrected_native/default_0.npz` within1e-8.
Both clips contain121frames and use the original weighted mesh; horizontal root
translation is centered only for display. This is RECORDED physics, not live
policy execution inside Unreal. Playback runs synchronized at0.25x, looping.

Scripts: `record_bounded_preview.py`, existing `install_skin_preview.py`, and
`refresh_bounded_preview.py` under `Labs/MimicKitTransfer`. Readback of all88bones
on every frame matches source within1.16e-4cm and7.23e-5degrees. Receipts in
`Saved/MimicKitTransfer/no-armature-3913`: `bounded-map-recording.json`,
`bounded-preview-refreshed.json`, `bounded-preview-playback.json`. Both new assets
are selected in the active dedicated simulated preview; clocks verified advancing.
No cloud job, new training, PHAT/mesh/Blueprint or gameplay controller changes.

### October15: bounded motors are now the default UEFN training runtime

User explicitly clarified that this must apply to **all future UEFN MJ training,
including resumed checkpoints**, not only transfer diagnostics. Implemented in
`Labs/MimicKitUEFN/velocity_motors.py`, loaded by `UefnNewtonEngine` before graph
capture. `omni_config.py` records `uefn_bounded_velocity_motors: true`; resume
validation permits this specific migration while retaining other config checks.
Historical checkpoint archives and frozen sources remain unchanged. Explicit
false is a diagnostic compatibility mode only, not the training default.

The verified joint motor/contact solve is unchanged mathematically. Removed the
prototype's unused dense inverse/mass scratch and dependency on the independent
box-QP prototype. Dispatch is per registered model/data, so unregistered engines
stay upstream and environments can uninstall out of order. Rows read Newton's
LIVE timestep array, including its update from the CPU model's default500Hz to
actual240Hz. Disabled actuation produces no motor rows. Solved torques populate
both actuator telemetry and the UEFN torque sensor using validated dof ordering.
Only velocity control is exposed here; Newton's auxiliary direct-torque channels
are unused/zero (validated in setup/integration tests and reported in motor
stats). This is not a general mixed direct-torque + velocity-control adapter.
Nonzero passive damping, non-one-hot gears and unsupported cap layouts are
rejected instead of approximated. No weakened gains/caps, additional armature,
body/PHAT changes, extra integration steps or CPU readback during physics.

Packaging includes the runtime. Deploy checks current source hashes BEFORE
allocating a GPU; restart on an existing pod also rejects stale source before
extending its timer. Current engine/config/train/motor files must match. A fresh
local package is built; no cloud deployment/training/spending occurred.

Jolt's active `contact-fixture.exe` ALREADY uses the same end-step bounded soft
motor law. The old initial-force-clipping saturation candidate is NOT selected.
No redundant Jolt motor solver or gameplay edits added. Seven native analytic
motor cases pass (maximum error2.83e-7rad/s); five MJ analytic cases pass on CPU
and CUDA with graph replay. Additional tests pass model ownership, out-of-order
uninstall, live timestep change, disabled actuation and solved torque reporting.
Integrated current UEFN engine test covers two worlds, reset, phase progression,
34 motors, original physical properties and finite states; see
`Saved/MimicKitUEFN/integrated-engine-cpu.json` and the bounded log
`Saved/MimicKitTransfer/no-armature-3913/integrated-motor-test.log`.

### October15: renewed same-state transfer diagnosis — still NOT transferable

`audit_coupled_transfer.py` compares the exact synchronized state and command
for ONE240Hz step, using the active project Jolt DLL fixture. Captures at policy
ticks0 and5; no accumulated policy-feedback difference in these comparisons.
Tests separate free motion, motors, gravity, limits, contacts, drag, iteration
counts and stationary controls. Preserve reference recordings/checkpoint3913.
An initial harness typo used native NO_LIMIT instead of NO_LIMITS. A stationary
control caught the error; both reports were regenerated with the correct switch.
Do not use the earlier off-limit results. Full-running results were unaffected.

At tick0, maximum body angular-speed discrepancy falls51.78→0.21rad/s with
motors but no contacts/gravity/limits/drag, and20.98→1.26rad/s in the complete
setup. Native100velocity/20position iterations reduce the latter to0.277rad/s.
These iteration changes are DIAGNOSTIC ONLY and do not solve closed-loop transfer.
Free moving-body residuals remain (~0.25rad/s); stationary free controls agree
within2.81e-6degrees with zero velocities, so no arbitrary stationary joint snap.

**A second distinct mismatch is directly isolated: angular-limit response.**
At corrected-MJ tick5 the left ankle's swing ellipse radius is1.154 (1 is the
boundary). Starting from that same pose with ALL velocities zero, motors off,
no gravity/contact/drag, Jolt rotates the foot1.079degrees in one step while its
reported velocity remains zero: positional projection. MJ rotates0.160degrees
and produces0.669rad/s: soft constraint acceleration. Raising Jolt position
iterations increases its correction to3.052degrees, without matching MJ's
velocity. Disabling limits in both removes this correction. Thus this measured
snap is neither changing NN commands nor an impact. Geometry/boundary values
alone do not make these solvers' limit responses equivalent. No limit softening,
removal, projection patch or PHAT change was promoted.

Closed-loop native transfer from the four corrected-MJ starts still fails the
27cm tracking check after16/6/29/14ticks (default).100/20iterations fail after
19/7/21/16ticks; matching material values or enabling speculative contacts also
fails all four. Diagnostic limit removal fails15/5/22/14ticks; with100/20iterations
45/7/36/17. Therefore limits are a verified contributor, NOT the sole proven
cause and disabling them is NOT a fix. Contact response, finite-step articulated
integration and the previously documented Newton body-velocity/drag mismatch
remain separate differences to quantify. No claim of successful Unreal transfer.
Evidence: `coupled-transfer-ablation.json`, `coupled-transfer-ablation-tick5.json`,
`tick5-limit-coordinates.json`, `isolated-limit-response.json`,
`corrected-native-report.json`, `corrected-native-no-limits-report.json`, and
small per-case traces in `corrected_native/`, all under the3913 evidence folder.

### October15: bounded motor integration — original checkpoint survives four starts

User rejected weakened gains and authorized trying an integration correction.
No Unreal changes, paid GPU, training, modified checkpoint or installed-library
edits. Two isolated prototypes, same gain/caps/body inertia/zero armature/dt:

- `capped_velocity_integrator.py`: reference box-QP end-velocity solve with
  the original constraint forces held fixed.32 scalar/coupled equation cases
  agree with independent float64 bounded least-squares within4.32e-5rad/s.
  Useful reference, not preferred for contacts. First running8steps reduce
  peak ankle delta54.91→5.60rad/s but retain small reversals.
- `coupled_velocity_motors.py`: preferred experiment. Reuses existing bounded
  scalar constraint mathematics with D=dt*gain and
  aref=(target_velocity-current_velocity)/dt. Thus torque equals the ORIGINAL
  capped gain*(target-end_velocity). Motor rows are inserted at the existing
  extension boundary before friction/limits/contacts and solved jointly by the
  existing Newton solver. Original actuation is excluded to avoid double force;
  ordinary body forces/contact/PHAT parameters remain. No second post-contact
  solve, extra physics steps, lower gains or added inertia. Existing scalar
  joint-level elbow/knee caps are intersected with actuator caps. Auxiliary
  direct-torque controls must be zero, explicitly checked every diagnostic step.

Five isolated saturated/unsaturated motor cases pass their analytical answers,
including the native Jolt scalar response2.727273rad/s at gain100/cap400.
Actual running-state8step test: ankleY2.912,-19.912,32.666,-14.125... becomes
2.912,.731,.511,.452,.431,.427,.432,.443,.458rad/s. No axis sign reversals
in the running test; max ankle step delta54.91→2.30rad/s. No-contact/gravity/
limit control agrees with the independent box-QP reference. Original baseline
still reproduces the recorded checkpoint step. Max motor equation defect
1.53e-5Nm. Evidence `capped-integrator-onset.json`,
`coupled-integrator-onset.json`, `capped_integrator/equation_tests.json`,
`capped_integrator/coupled_scalar_tests.json`.

Four-phase unchanged-policy10s test PASSED,300ticks each, original termination
rules, all original model/gain/cap arrays checked unchanged. Peak target error
21.61/21.64/17.45/16.11cm (original15.53/13.46/13.49/13.83cm; threshold27cm).
No large ankle velocity reversals in any; opposite near-cap pairs0/0/2/1,
with ZERO consecutive alternating pairs in all four. Isolated reversals remain;
do not claim no motor ever changes direction. Max motor equation defect1.27e-4Nm.
All four physically run30.0–30.7m over10s; pelvis height stays0.848–0.928m across
the tests. This is actual running, not an initial-pose survival count.
Max constraint rows50/450. Actor3913 SHA unchanged. Evidence:
`coupled_integrator_batch/{report.json,raw.npz,alternation.json,motion_summary.json}`.

Paired same-state CPU full-physics-step test (20samples per mode,5warmups,
alternating order) median123.04ms original /100.43ms coupled (ratio0.816).
Desktop/Unreal left open; NOT a cloud GPU or training-speed claim.

GPU512-world CUDA-graph capture/replay PASSED on the local RTX4060 Laptop GPU.
512 copies of the exact initial RunLR state, complete physics step plus identical
device-state restore; no actor/PPO/rollout timing. Max CPU/GPU generalized-speed
error3.40e-4rad/s original /2.41e-5rad/s coupled. Ten paired samples after warmup,
10graph replays per sample: median6.701ms original /7.491ms coupled (+11.8%).
Desktop remained active and individual samples vary materially (4.46–10.70ms
original,5.65–10.13ms coupled): PRELIMINARY local overhead only, not a precise
L4/training-throughput prediction or zero-overhead claim. All stepping stays on
GPU; diagnostics read back only outside captured stepping. Original gains,
caps, inertia and240Hz timestep retained. First-use stock physics CUDA kernel
compilation took several minutes and is excluded. GPU benchmark's first attempt
correctly failed parity because Newton's CPU model copy retained default500Hz;
its actual Warp model uses240Hz. Copying the LIVE Warp timestep fixed the test
setup; none of the prior CPU policy runs had this mistake. Saved
`capped_integrator/gpu_paired_benchmark.json` and `cpu_paired_benchmark.json`.

No Jolt-transfer or live Unreal integration claim: this is an isolated verified
simulation prototype. Original checkpoint survives the corrected training-side
motor integration on the four tested starts; native transfer still has its
previous separate differences. No paid GPU/training or gameplay edits. Owned
diagnostic interpreter closed after verification. Initial
prototype assertions intentionally rejected sparse mass layout, joint-level
caps and Newton's separate direct-torque channels until handled explicitly.
A diagnostic Warp struct loop used array.size incorrectly; scalar torque
verification caught it, replaced with explicit counts before full policy tests.

### October15: zero-additional-kernel motor-gain trials (checkpoint unchanged)

User authorized trying a fix and checking whether the existing checkpoint
survives it. Chose constant ankle gain changes first: no additional integration
steps, controller kernels, CPU transfers, armature, torque-cap removal or policy
retraining. All tests are isolated CPU processes; no Unreal/active native-driver
or frozen source/config/checkpoint modifications. Actor3913 SHA256 remains
`764f1eb6bd6035008eafd884954410f7e58246c2bba7a331b10847727ce0c7ef`.

`test_motor_gain_rollouts.py` records every240Hz generalized velocity/actuator
torque and every30Hz closed-loop state/action. It restores the cold solver
snapshot before reset, asserts equal initial observations across settings and
unchanged masses/inertias/armature/caps. Initial harness assertions caught that
Newton imports the ankle XML hinges as spherical joints; selection now uses
joint-body ownership/dofs, not presumed joint names/counts. No faulty physics
result was accepted. Baseline phase0 actions/states exactly match the earlier
300-tick recording (max difference0). Fresh baseline phases0/.25/.5 completed;
the fourth repeat was stopped to avoid redundant slow CPU work (the prior
four-phase baseline already completed). Saved partial report is not a20-case
completion. The candidate screen and gain10 confirmation then completed.

| Both ankles, all axes gain | Phase0 duration | Opposite near-cap torque pairs | Consecutive such pairs |
| --- | --- | --- | --- |
| 40 original | 10s, passed | 291 | 206 |
| 30 | 10s, passed | 56 | 30 |
| 20 | 10s, passed | 30 | 10 |
| 10 | 0.433s, failed27cm | 0 | 0 |
| 5 | 0.367s, failed27cm | 0 | 0 |
| 2.5 | 0.367s, failed27cm | 0 | 0 |

Pair definition: adjacent opposite actuator torques, both at least80Nm,
within the SAME held policy command. Consecutive pairs distinguish repeated
alternation from a single reversal. Large velocity-reversal count alone is
insufficient: gain20 removes >10rad/s-to-opposite->10rad/s crossings, but still
has smaller motor overshoots. Example right-ankle X at policy tick36 with
unchanged target1.98rad/s: -4.96,9.16,-8.09,-2.18rad/s, torques+90,-90,+90Nm.
Gain20 phase0 max tracking error15.42cm versus original15.53cm, but it is NOT
a complete chatter fix. Gain10 four-start confirmation fails at13/33/30/17
ticks (0.433/1.10/1.00/0.567s); no repeated near-cap alternation in any, though
phase.5 has one opposite near-cap pair. Failure means tracking threshold, not
necessarily lying on the floor. Do not compare its shorter raw counts as if
it completed10s.

The X/Z10,Y20 trial also failed all four phases at30/152/127/17 policy ticks.
Its final report serialization failed on a NumPy bool before raw traces were
saved; only terminal timings survive in command output. Serializer corrected;
do not invent missing torque/error data. User explicitly rejected gain reduction
as mitigation, correctly: it changes the controller rather than fixing bounded
motor integration. Gain experiments stopped; no production setting changed.

User authorized trying the proper capped-motor solve next. Isolated prototype
`capped_velocity_integrator.py` solves for end-step velocity and bounded motor
torque together, keeping gains/caps/inertia/timestep. Uses a convex box QP with
the full coupled articulated mass matrix and passive damping, implemented in
Warp with preallocated device arrays. Existing contact/limit constraint forces
are held from the ordinary constraint solve, like implicitfast: this is NOT yet
a joint motor/contact solver and must be tested accordingly. No performance,
checkpoint-survival or Jolt-transfer claim until measured. No cloud spend,
installed-library change or Unreal access.
Evidence: `motor_gain_screen/`, `motor_gain_candidates/`,
`motor_gain_candidates_confirmation/`, `motor-gain-comparison.json` under
`Saved/MimicKitTransfer/no-armature-3913/`.

### October15: traced reversal onset from the first physics step

Follow-up to the user's objection that the preceding test started after the
ankle was already moving fast. `audit_armature_reversal.py --systematic --onset`
now captures the ordinary reset after Newton-to-MuJoCo state synchronization,
immediately BEFORE its first integration. It holds the first actual policy
command fixed. All cases restore the exact full solver/raw snapshot. The
unmodified baseline matches the original eight substeps and the recorded
first policy tick; body masses/inertias remain unchanged. The earlier onset
uncertainty below is resolved by these additional controls.

Initial right-ankle Y velocity is +2.912rad/s, target is -0.06036rad/s.
The gain40 motor requests -118.88Nm, capped at -90Nm. Results:

| First-step condition | Y velocity through the first steps (rad/s) |
| --- | --- |
| Actual running setup | 2.912, -19.912, 32.666, -14.125 |
| No contact, gravity or limits | 2.912, -53.722, 2.109, -0.076 |
| Same, only ankle motor active | 2.912, -54.604, 4.811, -53.646 |
| Same, ankle motor disabled | 2.912, 0.269, -1.469, -2.756 |
| Same, original ankle armature restored | 2.912, -20.314, 1.557, 0.014 |

The first violent reversal is therefore generated by motor braking overshoot,
not an earlier impact or a changing policy command. Floor contact affects its
subsequent development: with all ordinary motors but no contacts the Y axis
settles near the requested speed within the first policy tick, whereas floor
contact keeps the running case oscillating. Only the ankle motor is sufficient
to produce repeated reversals without contacts. Gravity, self-contact and
limits do not explain the onset. Restoring armature reduces the first jump
but does not prevent it. Do not interpret the previous continuation test as
proof that floor contact has no influence on the running trajectory.

**Mechanism verified with four additional controls (24 onset cases total):**
`mujoco_warp/_src/derivative.py:_qderiv_actuator_passive_vel` explicitly sets
the actuator velocity derivative to zero when its force reaches either cap.
The capped motor therefore loses its implicit velocity-damping contribution
on that step. The large braking impulse overshoots; torque flips next step.
This is the installed training simulator's saturation/integration behavior.

Two independent interventions leave mass/inertia and running contacts unchanged:

| Diagnostic intervention | First Y speeds (rad/s) | Y reversals in8steps |
| --- | --- | --- |
| Gain40,90Nm cap, original | 2.912,-19.912,32.666,-14.125 | 8 |
| Gain20, same90Nm cap | 2.912,1.656,1.359,1.217 | 0 |
| Gain40, ankle actuator force cap disabled | 2.912,1.644,1.427,1.313 | 0 |

With contacts/gravity/limits disabled those two controls also avoid the large
overshoot: first Y speed -0.040/-0.050rad/s respectively, versus -53.722rad/s
with the original capped gain40 motor. This separates saturation/integration
from merely "too much requested torque": the uncapped case requests MORE
initial torque (-118.88Nm), yet behaves smoothly because implicit damping stays
in the solve. Halved gain requests -59.44Nm and stays below the same90Nm cap.
Neither experiment is a proposed unlimited-torque production workaround.
Armature removal amplifies a saturation problem that remains reproducible with
the original armature restored. No need for another unknown earlier impact to
explain the observed first-step speed or the subsequent motor chatter.

Evidence: `Saved/MimicKitTransfer/no-armature-3913/reversal-onset-audit.json`.
This is isolated CPU diagnosis; no Unreal, training, model, motor settings or
active native-driver changes have been applied.

### October15: systematic reversal controls — completed20 cases

User challenged the earlier contact-inclusive diagnosis. Ran
`audit_armature_reversal.py --systematic`: same complete solver/raw-state snapshot,
constant command,8 physics steps, no changes to runtime/training/Unreal.
All2x2x2 contact/gravity/limit combinations; floor-only/self-only exclusions;
ankle motor off, ankle motor alone, original ankle armature restored, each in
running/no-contact/free conditions; all-motors-off free control. Full baseline
matches the earlier recording. Exact initial state asserted for every case.
Diagnostics include generalized ankle actuator/constraint torque, acceleration,
active contact kinds and constraint-row types/force magnitudes at every step.
Snapshot now includes nested efc arrays too. NXN collision exclusions update
the precomputed geometry-pair lists, not just contype/conaffinity; assertions
verify removed contacts/limits/ankle actuation are actually absent.

Results for the rapidly reversing ankle Y axis:

| Condition | Sign reversals over8 steps | Largest axis step change |
| --- | --- | --- |
| Current running state | 8 | 57.35rad/s |
| All contacts disabled | 8 | 57.35rad/s |
| Contacts + gravity + joint limits disabled | 8 | 57.35rad/s |
| Same free condition, ONLY ankle motor disabled | 0 | 4.60rad/s |
| Same free condition, ONLY ankle motor enabled | 8 | 56.42rad/s |
| Same free condition, original ankle armature restored | 6 | 23.77rad/s |

With contacts/gravity/limits removed, Y velocity is
34.13,-23.22,28.44,-26.95,25.43,-29.79,23.49,-31.97,22.37rad/s.
Motor torque alternates -90,+90Nm every substep; generalized ankle Y constraint
torque is exactly0 throughout. Zero active contacts verified. With ankle motor
alone it still alternates; with only ankle motor off it smoothly decays
34.13,29.52,26.19,23.56,21.42,19.66,18.20,17.00,16.00rad/s.
In the original running case, no contact exists in the first5 audited steps;
floor contact appears only at steps6 and8 and changes the later trajectory.
Independent gravity/limit/self-contact removal does not eliminate the chatter.

Bounded conclusion: contacts, gravity, joint limits and other motors are NOT
necessary to sustain this observed high-speed reversal. It is local motor
overcorrection in the training simulator, amplified by armature removal.
This tests continuation from an already-fast running snapshot; it does NOT
establish how the first high ankle speed developed earlier in the episode,
nor isolate every remaining Jolt transfer discrepancy. No gain/armature fix
was silently applied. Evidence `reversal-systematic-audit.json`; partial receipt
also retained. Previous4-case explanation alone was insufficient, as noted below.

### October15: armature versus ankle reversal, causal snapshot test

**Interpretation correction requested by user:** the original four cases below
kept contacts, gravity and limits active; the motors-off case disabled ALL
motors. They demonstrate armature sensitivity, but alone do not exclude contact
or constraint interaction and do not establish an isolated ankle-motor cause.
The previous categorical explanation exceeded that evidence. Systematic
contact/gravity/limit and selected-motor interventions are recorded separately.

User asked whether removing inertia caused the rapid physics-step reversals.
Diagnosis only: no training/settings/Unreal/active-contact configuration changes.
`audit_armature_reversal.py` replays the SAME full MuJoCo Warp solver snapshot,
including warm starts/contact arrays, raw Newton body/joint state and fixed
policy command, for eight1/240s steps. Original rigid-body masses/inertias are
asserted unchanged. Baseline reproduces the earlier recorded oscillation.
First attempt using repeated environment resets correctly failed the identical
state assertion (up to0.00149 in state components); replaced with full snapshot
restoration, not a loosened tolerance. Current test passes exact starting-state
equality and recorded-baseline reproduction.

Right-ankle Y command stays+2.772rad/s; initial actual speed+34.128rad/s:

| Intervention | Joint Y speeds at successive substeps (rad/s) | Largest joint-axis step change |
| --- | --- | --- |
| No armature, current motor | 34.13,-23.22,28.44,-26.95,25.43,-29.79,22.12,-33.42,16.49 | 57.35rad/s |
| Restore only ankle's0.01kg m2 per axis | 34.13,10.36,-13.07,8.36,-15.09,6.47,-16.83,4.89,2.86 | 23.77rad/s |
| Restore all original joint armatures | 34.13,10.42,-13.00,8.39,-15.02,6.51,-16.75,4.92,2.86 | 23.71rad/s |
| No armature, all motors off | 34.13,33.83,19.33,10.08,4.35,0.94,-0.97,-1.94,-2.31 | 14.50rad/s |

World-X foot reversal counts8/3/3/1 respectively; joint Y sign changes8/6/6/1.
Restoring armature does NOT immediately remove all overshoot from this already
fast initial state, but sharply reduces it and reaches near the command within
33ms. Almost identical ankle-only/all results isolate a predominantly local
ankle effect. Motors-off produces one smooth reversal, not repeated chatter.

Conclusion: removing artificial joint armature substantially aggravates motor
overshoot; it did not remove the foot's physical inertia. Same gain40 and90Nm
cap now act on less effective inertia. At force saturation MuJoCo Warp's
`derivative.py:_actuator_vel` omits the actuator velocity derivative, while
`forward.py:_actuator_force` clips the force. This explains how the capped motor
can overshoot and reverse torque on the next step despite implicit integration.
The observed chatter is present in the training simulator under a fixed action,
not generated by changing NN commands or solely by the Jolt adapter. This test
does not certify restored-armature gait or establish that it fixes transfer.
Do not silently restore armature or retune gains: no runtime changes made.
Evidence `no-armature-3913/armature-reversal-audit.json` (four cases,9 samples each).

### October15: contact suppression enabled for ongoing transfer work

User explicitly requested implementation, rather than leaving it as an optional
test. The active native driver is now `contact-fixture.exe`, selected through
`no-armature-3913/active_fixture.json`. Both `native_probe.py` and the comparison
recorder use this selection automatically. Build with
`build_rig_contact_filter.ps1 -ContactOnly`. The callback is installed by default;
`TRANSFER_RIG_ALLOW_SPECULATIVE=1` is the diagnostic opt-out. Archived baseline
executables/recordings remain intact. No torque-saturation candidate is enabled:
this changes contact response only, with the original Jolt motor controller.

Scope clarification: the current Unreal map is a recorded-physics comparison,
not a live policy actor. This implements the option in the real native Jolt
driver supplying that map, not in the shared gameplay WorldSubsystem. No engine
build/restart or original mesh/PHAT/Blueprint change. A future live integration
must explicitly carry this per-rig setting into its existing contact listener.

Contact-only self-test passes (real contacts/persistence/toggle-off, unmarked
body unchanged). Filter-disabled outputs exactly match the baseline across
eight frozen-state tests. Against global speculative-distance0, six states
match exactly; two differ by up to0.047cm/1.008degrees with the original motor.
Therefore previous exact eight-state equality applied only to the diagnostic
saturation controller; do not generalize it to all states/controllers. The
comparison is evidence, not an equivalence requirement. An initial test-control
failure was caused by an older baseline fixture lacking the global-setting
diagnostic switch; the build now adds it, and corrected evidence is retained
in `contact-only-snapshots.json`.

Completed four-phase feedback tests: failure at19/7/23/24 ticks, compared with
original19/7/21/17. Thus two starts improve modestly; all still fail within0.8s.
Four-second phase0 recording continues through the fall (final pelvis13.11cm).
`record_active_transfer.py` runs the selected configuration and records it;
recording prefix matches the corresponding phase0 test within1e-8.
Evidence `jolt_contact_only_report.json`, `jolt_contact_continued.npz`,
`contact-map-recording.json`. No new training or CPU/GPU policy changes.

Imported separate `AS_JoltContact_3913` and switched only the JOLT actor/label
in `M_JoltTransferFailure` to that recording. Original comparison recordings
retained. Readback of all121 frames/88 bones: max6.08e-5cm and8.86e-5degrees
local-transform error. Map saved, no Play started/stopped. User's dirty
PoseAgent remains unsaved/unchanged; editor left on the same comparison map.
`contact-preview-refreshed.json` verifies the displayed selection. This remains
recorded native Jolt physics, not live policy inference within Unreal.

### October15: per-rig predictive-contact experiment

User asked to try disabling predictive contact only for the experimental rig.
Implemented only in a separate CPU fixture linked to the exact project Jolt DLL;
Unreal, its running preview, gameplay settings and original assets were untouched.
`rig_contact_filter.inl` tags the fixture bodies and suppresses response for
negative-penetration manifolds in BOTH Added and Persisted callbacks. Real
contacts retain Jolt's default settings. World speculative distance remains2cm.
Build: `build_rig_contact_filter.ps1`; opt-in `TRANSFER_RIG_NO_SPECULATIVE=1`.
Diagnostic counters are single-thread-only; do not copy them into a parallel
runtime. Production would integrate the existing listener, not replace it.

Tests:
- Two independent falling spheres: untagged trajectory exactly unchanged from
  stock. Tagged trajectory matches global distance0 within9.37e-19.18 separated
  manifolds suppressed,102 solid contacts,238 persisted callbacks. Turning the
  filter off during the test preserves collision; minimum center height9.848cm
  for a10cm-radius sphere. No floor fall-through in this bounded test.
- Eight full-rig frozen-state substeps: per-rig and global0 outputs exactly
  match in reported position, orientation, linear/angular velocity and ground
  impulse. Test independently verifies each initial state and uses unique
  temporary input files; no actor/physics Python imports needed.
- Continuous policy feedback from four phases: per-rig crosses27cm at
  **13/7/13/15 ticks** (0.43/0.23/0.43/0.50s). Same executable with global0
  and callback disabled reproduces **10/6/12/12 ticks**. Original unmodified
  controller/contact baseline was19/7/21/17. These per-rig/global0 tests both
  include the earlier diagnostic motor-saturation change.

Conclusion: response suppression can be scoped to tagged bodies and keeps
actual collisions in these tests, but it is NOT an exact substitute for the
global setting during continuous contact. The callback acts after contact
generation and retains a different contact/cache history; the global setting
changes generation itself. No exhaustive attribution of their divergence yet.
Mixed-point manifolds and CCD are not certified. It does not solve transfer:
all four gait starts still fail quickly. No production promotion or GPU run.
Evidence: `rig-contact-selftest.json`, `rig-contact-snapshots.json`,
`jolt_rig_contact_filter_report.json`,
`jolt_contact_filter_global_control_report.json` under `no-armature-3913`.

### October15: causal substep audit requested after viewing drift

All tests isolated CPU fixtures; no editor commands, training, gameplay changes
or GPU allocation. `ablate_first_step.py` compares one1/240s step in both solvers
from the SAME exact current MuJoCo rigid-body state and command. Eight successive
states examined, restarting Jolt for each prediction to remove accumulated
policy feedback divergence. These are first-interval tests at phase0, not a
claim covering every pose. Baseline prefixes/observation contract remain intact.

**First large discrepancy is motor saturation at the right ankle.** At the
first compared substep, max rotation difference6.4088degrees; disabling contact
gives6.4084, additionally disabling angular limits6.4090. Disabling motors too
reduces this to0.2339degrees. Raising native velocity/position iterations to100/20
still gives6.3597degrees with contact/limits disabled. Initial joint-anchor
position errors below3.66e-5cm rule out an initial anchor-placement mismatch.

The earlier saturation diagnostic applied to this exact state reduces the
first error to0.2064degrees. Right ankle commands[-1.657,2.772,5.576]rad/s,
current joint velocities[-2.433,34.128,-1.061]rad/s and gain40 request
[31.05,-1254.23,265.47]Nm, clipped by MuJoCo to[31.05,-90,90]Nm.
The fixed command generates alternating ankle velocity at240Hz: world X
-25.38 -> +26.52 -> -19.86 -> +29.55rad/s. The30Hz viewer does not show all of
this substep oscillation. This is evidence of simulator-sensitive controller
behavior, not proof of an intentional reward exploit.

**Second large discrepancy is predictive floor contact.** With saturation
handling matched, the worst substep rotation difference is7.606degrees with
contact, versus1.119degrees without contact. At substep3 the right foot starts
1.621cm above the floor. Native Jolt produces4.743Ns vertical ground impulse;
MuJoCo Warp has zero active contacts. Its foot reaches0.459cm above the floor.
Later MuJoCo foot minimum reaches-0.999cm. In the frozen-state comparison,
disabling native speculative contacts alone removes that early impulse and
reduces the worst error across eight states to1.2705degrees. Matching only
friction/restitution also removes the substep3 impulse but retains5.3167degrees
worst error. This establishes a predictive-contact/material interaction, not
merely different friction. Contact buffers beyond `nacon` are stale and were
not counted as active contact evidence.

**Not a completed transfer fix:** the combined diagnostic (saturation behavior
plus speculative distance0) still fails27cm at10/6/12/12 policy ticks for the
four phase starts, versus original19/7/21/17. It makes the measured local
response closer but does not improve whole-gait reliability. No such settings
were promoted. Residual joint/integration/force/contact differences remain;
there is not yet evidence for a single complete cause or a robust remedy.
Zeroing drag with exact gyro cancellation in the contact/limit/motor-free test
reduces first angular error to0.1609degrees, still nonzero.

Evidence under `no-armature-3913`: `first-step-ablation.json`,
`first-step-saturation-ablation.json`, `contact-substeps.json`,
`contact-settings-comparison.json`, `ankle-torque-diagnosis.json`,
`jolt_matched_motor_no_speculative_report.json`. Small build helper
`build_ablation.ps1` compiles only a separate project-DLL fixture.
`compare_contact_snapshots.py` tests identical saved inputs independently.

### Dedicated failure map (latest user request)

Created and opened `/Game/_mygame/Tests/MimicKitTransfer/M_JoltTransferFailure`.
Left: Jolt failure. Right: same checkpoint in Newton/MuJoCo. Four seconds of
recorded physics, looping at0.25x, with horizontal pelvis centering solely for
display. Original heights, rotations and relative limb poses are retained.
The native policy was allowed to continue past the27cm failure threshold,
without a reset or external support: failure at tick19, minimum pelvis height
13.23cm, final15.40cm. The first20 states match the original diagnostic within
1e-8; evidence `jolt_failure_continued.npz`, `failure-map-recording.json`.
New helper `record_failure_map.py`; map setup `create_failure_map.py`.

The map is running in an owned Simulate session for the user to view. Both
animation clocks were verified equal and advancing (2.8125s observed), with
only the normal spectator pawn. This is a playback demonstration, not live
policy inference inside Unreal. Camera is piloted on the comparison view.
User may stop Simulate normally and reopen testNN afterward.

To safely switch maps, backed up the previous disk testNN file under
`no-armature-3913/before-failure-map`, then saved the user's current map edits.
Dirty PoseAgent Blueprint remains unsaved and unchanged. Saved only the new
map and its two new comparison animation assets beyond that necessary map
preservation. Receipt `failure-map-preservation.json` records both map hashes.
No original mesh/PHAT edits, code build/restart or cloud workload.

Visual verification limitation: editor screenshot automation repeatedly captured
a different close-up viewport despite the correct level camera being read back.
Computer Use initialization is unavailable (kernel-assets OS error3). The map,
camera, actors and advancing playback were verified through Unreal's API;
do not treat those screenshot files as verified comparison-map captures.
The unnecessary EditorSetViewportRealtime(True) call raised a handled editor
ensure (no matching realtime override); editor recovered, no restart was made.

October15. User authorized trying the reduced physical articulation while keeping
the existing skeletal mesh, bones and skin weights. **The skin mapping is now
implemented and previewable in Unreal. Live Jolt policy transfer still fails.**
No gameplay controller, original PHAT, mesh or Blueprint was changed.

Latest checkpoint is the verified no-armature fine-tune3913 (64,126,976 samples),
SHA256 `176473b5f1128e7dfd951db9ae5c5da5d99ad267add14842e01f804bb5bf3837`.
Local checkpoint and persistent copy are safe; owned pod `bpzuyhk04huodw` is
EXITED. No new GPU run was launched. Evidence is under
`Saved/MimicKitTransfer/no-armature-3913/`.

### Original weighted mesh, reduced-body mapping

- `build_skin_preview.py` maps the15 physical anchors into all88 original bones.
  Other bones retain their reference local transforms; merged spine, clavicle
  and neck members follow their corresponding rigid body. This does not provide
  the original independently articulated motion at those omitted joints.
- Body-to-bone offsets use the actual skeleton bind pose. The check caught a
  0.531mm difference between exported foot-body origins and foot-bone origins;
  this is retained as an offset, not introduced as a skin deformation.
- Bind-pose matrix error7.78e-16; grouped bone transform error below7.11e-15
  across both recorded clips. The same mapping applies to live body transforms;
  this preview contains recorded transforms only.
- Saved ONLY two new native AnimSequences under
  `/Game/_mygame/Tests/MimicKitTransfer/`:
  `AS_Rig15_Newton_3913` (10s training-simulator physics) and
  `AS_Rig15_Jolt_3913` (0.633s failed native transfer).
  The first was opened in the animation asset editor on the original
  `/Game/_mygame/SKM_UEFN_Mannequin`. Neither is a new training reference or a
  replacement for live physics. No new PHAT asset has been created.
- Read back every frame and all88 bones from Unreal: maximum local position
  error3.21e-4cm, rotation1.93e-4degrees. See `skin-verification.json`.
  These checks establish correct imported bone transforms, not subjective skin
  quality at shoulders/neck; the user can inspect the actual skinned preview.
- Original mesh/PHAT file hashes unchanged. Dirty user Blueprint and testNN map
  preserved exactly; no map actors, camera, Play, build or restart involved.
  Helpers: `install_skin_preview.py`, `verify_skin_preview.py`; receipts and
  explicit mapping in `skin-import-receipt.json`, `skin-mapping.json`.

### Latest physical transfer evidence

Four starts at phases0/.25/.5/.75 all finish10s in MuJoCo after fine-tuning
without armature. Peak target errors15.53/13.46/13.49/13.83cm. Native Jolt still
crosses27cm at19/7/21/17 policy ticks (0.633/0.233/0.700/0.567s).
Using training friction/restitution numbers fails at11/5/20/14ticks; it is not
a fix. Observations match within7.63e-6 and initial serialized physical state
within3.05e-7. These are four specific starts, not a general success rate.

An isolated motor test establishes a real difference at saturation: two
unit-inertia bodies, dt1/240s, gain100, target6rad/s and torque cap400Nm produce
relative3.333333rad/s in MuJoCo and MuJoCo Warp, versus2.727273 in native Jolt.
MuJoCo clips the initial actuator force; Jolt clips the solved soft-motor impulse.
An isolated candidate matches that scalar test, but full gait still fails at
10/15/17/8ticks. It is diagnostic only and was not promoted to engine code.
See `compare_motor_response.py`, `build_motor_comparison.ps1`,
`build_saturation_candidate.ps1` and their saved reports.

The previously identified Newton body-velocity reporting discrepancy also
remains. Using exact MuJoCo Jacobian velocities solely for the drag/gyro force
correction survives all four60-tick diagnostics; this does not establish that
all simulator semantics now match. No shared training implementation changed.

The actor is exported as `runLR_actor.onnx`: raw151 inputs, embedded saved
normalization,34 bounded velocity outputs and2 phase-prediction outputs.
Compared against the frozen actor on1,505 recorded observations plus stress
inputs: maximum velocity error1.43e-5rad/s, phase error1.43e-6.
Local single-thread inference medians0.213ms for one agent and1.643ms for32;
these are local CPU measurements, not Unreal performance claims.

## Historical assessment — checkpoint3042 before no-armature fine-tuning

October 15, 2026. User asked this fork to assess transfer to the physical mesh
without perturbing their Unreal work. **The checkpoint is not demonstrated as a
drop-in Jolt transfer. No production integration was performed.**

## Scope and preservation

- Latest downloaded Run LR checkpoint: update3042,49,856,512 cumulative samples,
  `Saved/MimicKitOmniRun/checkpoints/20261015_124835_uefn_runLR_velocity_512/checkpoint_0003042_final.zip`.
  SHA256 `f14dbe34eb5ce33989b760447b1822923d4e4d58443c818b27c3f3fa9f5e0092`.
- Extracted frozen checkpoint/config/source into `Saved/MimicKitTransfer`.
  New experiment source only in `Labs/MimicKitTransfer`.
- CPU-only inference and physics, one Torch thread per process. No training,
  GPU rental, Unreal RPC, editor restart, Play manipulation, asset edits,
  gameplay code changes, D/S/Reach lab changes or checkpoint modification.
- Unreal process13040 remained open. Saved PHAT and mesh SHA256 still match the
  checkpoint's source export. This does not inspect or alter unsaved editor work.
- This branch stays out of `ProjectJournal.md`.

## Results

Four deterministic starts at gait phases0,0.25,0.5,0.75. Training simulator uses
the frozen environment, actor, normalization and clock. No exploration noise.
Jolt starts from the corresponding actual MuJoCo state after the first policy
tick, avoiding the reset's stale zero body-velocity cache. Thereafter Jolt feeds
its own physical state back to the actor; no recorded actions or future poses
drive the character. The reference is used only for measuring error, and follows
the current horizontal pelvis exactly as in training.

| Initial phase | Training simulator | Jolt with PHAT body material | Jolt with training material numbers | Training simulator, armature removed only |
|---|---|---|---|---|
|0|10s timeout|11ticks /0.367s|10ticks /0.333s|10s timeout|
|0.25|10s timeout|6ticks /0.200s|5ticks /0.167s|8ticks /0.267s failure|
|0.5|10s timeout|19ticks /0.633s|11ticks /0.367s|10s timeout|
|0.75|10s timeout|21ticks /0.700s|14ticks /0.467s|10s timeout|

Jolt entries end when a target collider centre exceeds27cm deviation. Native
stock contact/pose termination is not implemented in this diagnostic, so this
cannot overstate success by counting an earlier native contact failure. Newton
uses all original termination conditions. These are four specific starting
phases, not a general success-rate estimate. The original checkpoint's cloud
evaluation remains separate (mean274.31 of300ticks).

The native model has the training15-body layout,23colliders and34actions. It is
already insufficient with these otherwise favorable structural conditions.
**The full23-body articulated physical mesh was not rolled out**: choosing new
controllers for its eight omitted joints would introduce an unapproved design.

## What was verified

- Actual project Jolt DLL, independently compiled small executable; no UBT or
  modified engine library. DLL hash and asset hashes are in the result summary.
- Frozen XML shapes, compound body masses/COM/inertia, collision exclusions and
  exported PHAT limit frames. Native inverse inertia and COM checked numerically
  for all15bodies; initial state error below3.81e-7 in serialized SI channels.
- All151 observation channels reconstructed from physical state agree with the
  frozen environment within7.63e-6. Actor outputs agree with recorded deterministic
  actions. No extra phase feedback or future-pose inputs.
- Policy commands are child-local angular velocities. Jolt rotation motors use
  **body2 constraint space**, unlike its linear motors. Velocity gains and torque
  caps come from the frozen model. Zero stiffness, damped native motor mode.
- Independent two-body physical motor test, with both child and constraint frames
  rotated, agrees with the analytic damped response within6.96e-9rad/s.
- Original velocity action bound ±2πrad/s applied after actor inference. Physical
  regression tests show commands±100 produce exactly the same state as±2π.
- Eight240Hz native steps per30Hz policy tick; aggregate physical drag retained,
  native gyro disabled, original exported body speed caps, no sleeping. No root
  forces, teleportation, posture correction, gains tuning or motor target smoothing.

## Actual differences and limitations

1. **Articulation:** training has15rigid bodies; saved physical rig has23. Spine01,
   spine02, spine04, spine05, both clavicles, neck02 and head articulation were
   merged into pelvis/torso/head compound bodies. The checkpoint has no separate
   control for these eight joints. The visible skeletal mesh can remain the same,
   but its physical layout and mapping are a separate design decision.
2. **Joint dynamics:** training adds generalized armature inertia (0.01/0.02kg·m²)
   on the34driven axes. It is not part of the exported rigid-body inertia, and
   native SixDOF motors do not reproduce it merely by copying body mass/inertia.
   Removing it in the isolated training simulator changes one previously good
   start into a0.267s failure and increases peak errors in the others. This proves
   sensitivity, not that armature alone explains every Jolt failure.
3. **Contacts and integration:** native implicit soft velocity motors and Jolt
   contacts are not MuJoCo's complete dynamics. PHAT-material case uses body
   friction0.7/restitution0.3 and a flat friction0.7/restitution0 ground. Alternate
   case uses1/0 for both. Neither works. This rules out just changing those two
   material numbers as a sufficient fix; it does not match contact compliance.
   Native global solver defaults are used; live level/Blueprint overrides were
   deliberately not queried. This is a transfer candidate, not a full reproduction
   of the user's current gameplay world.
4. **Training velocity reporting discrepancy:** for identical qpos/qvel, body
   positions agree within6.04e-6m, but reported limb angular velocities differ
   from independent MuJoCo Jacobians by up to5.374rad/s and COM linear velocities
   by4.035m/s. Newton's ball-joint FK velocity path rotates the copied MuJoCo
   components through the parent-joint frame. MuJoCo's ball velocities use the
   moving child frame. These reported body velocities feed the current velocity
   reward and force correction, so this needs separate attention. No shared
   training code was fixed here. Policy observation reconstruction uses the
   actual generalized state; the discrepancy was not hidden by fitting an offset.

## Rejected diagnostic results

The first native adapter incorrectly converted rotational targets to the parent
frame. This was caught by reading the native motor implementation; initial failure
times are invalid and retained as `rejected-wrong-motor-frame*.json` only. A second
audit restored the upstream CharEnv action clamp, initially omitted in the native
fixture; `rejected-missing-action-clamp*.json` are also superseded. Final figures
above include both corrections and the physical regression checks. No conclusions
about engine parity should be drawn from the rejected reports.

## Next decision

Do not deploy this checkpoint into the active physical mesh yet. First establish
a validated matching motor/dynamics implementation in the isolated15-body test,
including the armature and velocity-reporting issue. Then decide whether a
dedicated15-body physical configuration is acceptable or training must include
the full23-body articulation. Do not silently add stabilizers or eight ad-hoc
joint controllers to make a demo appear to work.

Evidence: `Saved/MimicKitTransfer/summary.json`, `newton_report.json`,
`jolt_report.json`, `jolt_training_contact_report.json`,
`newton_no_armature_report.json`, `velocity-report.json`, `adapter-tests.json`,
`motor-test.json`, phase trajectory NPZs and bounded logs. No GPU experiment was
started or resumed. All owned diagnostic processes finish normally.
