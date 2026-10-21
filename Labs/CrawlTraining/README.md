**STOPPED at user request — October17:** cancelled the added hour for run
20261017_135639_uefn_crawl_velocity_512. Graceful stop produced checkpoint1628;
local bytes/SHA verified before stopping the pod. Retained archive:
local-checkpoints/20261017_135639_uefn_crawl_velocity_512/checkpoint_0001628.zip,
SHAb2d38e957d29b3b9e75aedd516762aea1ba92bb7c6db63886fe0a577d6704650.
Runpod confirms owned o6qhah385ykhhx EXITED; user-stop-confirmed.json is the
billing-stop receipt. active_run.json is stopped; verified-checkpoint.json
points at1628. The one-hour schedule below is cancelled. Do not auto-resume.

**Additional hour startup (now stopped) — October17:** initial35-minute continuation
finished cleanly at26,427,392 samples, with checkpoint0001612_final.zip
checksum-verified locally (SHAaafec06143b40c4c26e2addfc9385610b5c72fb75b4e53b46ae4bd63ae955ed2).
User requested another hour. `resume_updated_window.py --continue-latest
--seconds 3600` restarts the owned stopped pod, restores the verified runtime,
reuses the matching retained final checkpoint, and keeps PHAT/references/config
unchanged. Deadline is set to3600s from the first learner status plus165s for
saving/shutdown; local backup now reloads runtime_control.json each cycle.
New run20261017_135639_uefn_crawl_velocity_512 resumes at1613, actual start
13:58:10 Warsaw; training stop14:58:10 and hard shutdown15:00:55 on October17.
Receipt updated-training-20261017/added-hour-receipt.json supersedes all old
deadlines. Startup connection allowance increased to120s; launch.py now casts
the allocation duration to integer seconds for argparse. The failed parser
attempt135506 never trained; its exit watcher and startup controller were
stopped before successful135639 launch on the already-restored runtime.
Successful startup log: updated-training-20261017/added-hour-start.log.
Optimizer/normalizers restored; first new checkpoint1613 is checksum-verified
locally (SHAe9e8750e90e3); local backup and deadline guard processes verified.

**Updated-animation continuation completed — October17:** user authorized AE
retraining and latest checkpoint finetuning for35minutes with current PHAT.
Local AE completed at run20261017_123736_updated_crawl_idle_2x512, best1500,
validation0.0612601; offline only. Latest verified policy checkpoint1311 has
21,495,808 samples and actor/critic optimizer + normalizer states.
`prepare_updated_crawl.py` projects the edited source, closes its loop, matches
authored hand XY/orientation and nonnegative collision-box clearance, then
solves contact IK with all upper-body constraints (including torso/head).
Root/legs preserved; final fit reserves the full1.05x angular margin plus
0.05degree numerical interior, with continuity weight20. Head orientation may
adjust minimally within limits. Four frames require hand XY relaxation (up
to0.854mm measured;2mm cap); height remains an exact constraint. The earlier
0.25degree-only fit is archived in before-five-percent and is superseded.
`install_updated_crawl.py` verifies dense contact/limits/seam before
installing the new policy copy. New crawl SHA
02bcdbbf559eb867784a70147b4f555cc64fc3e97ae35811b0be19f8fbd8b6f5;
idle remains SHA855f68c3fcf0e3cab0b148b79f7c14a9a22c557d712de8af60610fd49cf25a7e.
103,456 upper-body reference/margin samples accepted by exact Jolt; planted hand error<=0.755mm,
penetration<=0.145mm, loop seam<0.001mm. Unmodified left ankle reference conflicts
remain explicitly reported; no ankle PHAT change or full-body feasibility claim.
Evidence/backups under Saved/MimicKitCrawl/updated-training-20261017.
Current-PHAT16-world physics/PPO preflight passed. Final checkpoint1311 rollout
passed120 deterministic +80 noisy ticks, with restored optimizer/normalizers,
finite state and no weight updates. Dynamic hand minima: deterministic-2.516cm,
noisy-2.692cm; these differ from the sub-mm reference contact and are not a
perfect-dynamics claim. `resume_updated_window.py` reuses the owned L4 pod.
Run20261017_130908_uefn_crawl_velocity_512 is training on owned L4
o6qhah385ykhhx; remote assets/motions exactly match the hashes above and
current limits502187a97e7f. Checkpoint1312 (21,512,192 samples) is locally
checksum-verified locally and in cloud; subsequent updates reached1332 with
auto-phase MSE and no fatal failure. Live learner accepted the revised deadline.
Initial startup stopped safely on missing container-local runtime; retry
restored the verified cache but hit upload timeout. Final launch reuses the
identical retained checkpoint after SHA verification, avoiding that upload.
Training duration is2100s from actual start13:10:51 Warsaw: training stop
13:45:51 and hard shutdown13:48:36 on October17. This supersedes the initial
allocation-based13:37 deadline so retries do not consume requested training.
Local/remote guards reload the revised deadline; local backup helper restarted
with it. See running-verification.json and training-duration-receipt.json.

User requested removing previous checkpoints to free storage. One-time scoped
cleanup retained source checkpoint1311 and every new-run checkpoint; removed
9 local archives (299,950,532 bytes),7 pod archives (237,302,221 bytes), and10
S3 archives (311,711,616 bytes). Three dangling old-run cloud receipt pointers
also removed. Current verified-checkpoint.json now points at local1312;
local-backup-status.json remains the evolving local backup source of truth.
Other training families, AE models, source backups and diagnostics preserved.
Plans/receipts and prune_previous_checkpoints.py are in updated-training-20261017.
Verified local backup remains enabled independently of cloud quota/upload status.

**Current PHAT upper-body update — October17:** user authorized saving the
single Unreal PHAT in place with5% angular room and no ankle changes. Nine
profiles expanded: spine_03/spine_05, both clavicles/upperarms/hands, head.
Clavicle twist axes are now LIMITED; all six leg profiles are unchanged.
Fit uses the latest native crawl/idle, pure robot projections and existing
contact-corrected idle; excludes obsolete cleaned crawl and LAFAN. Saved-value
verification:358,456 dense samples and89,712 exact-Jolt reference/margin cases
pass. Geometry, frames, drives, damping and both canonical XMLs unchanged.
Canonical metadata and local crawl package/source.zip refreshed; policy/AE
motions untouched at that PHAT-save stage. The subsequent preparation above
replaces the old cleaned crawl and refreshes preflight. Viewer uses saved limits and
shows zero upper-arm violations. Original asset/metadata/viewer retained in
Saved/MimicKitCrawl/upperbody-limits-20261017/before; plan/applied-limits and
limit-verification JSONs alongside it. `fit_upperbody_limits.py --verify-saved`
rechecks without editing limits; `apply_upperbody_limits_unreal.py` saves only
the PHAT after exact non-angular-field and leg-profile preservation checks.
See Docs/MimicKitUEFNBodyMatching.md for exact current angles.

**Source shoulder-limit overlay — October17:** updated-source viewer checkbox
"Show shoulder limits" overlays green arms with both shoulders at nearest
admissible rotations. Works for authored and robot variants at all55 frames;
other local articulation stays fixed, so hands follow rather than staying
planted. This is a pose comparison, not simulated PHAT dynamics.
`add_source_limit_overlay.py` runs multistart constrained quaternion-distance
optimization and verifies all220 resulting shoulder poses in project Jolt.
Evidence: overlay-verification.json and overlay-jolt-output.csv alongside the
viewer. Checkbox toggling and both variants checked in browser. Motion files,
limits and training are unchanged. Rerun overlay script after regenerating
updated-source data.json.

**Updated source audit and corrected viewer — October17:** current
recoveries/crawl.fbx saved12:07:07 Warsaw, SHA2e849ce9c90057c8a333ce506ded079b8987ccf00e5b46660ec267fd50fcbb84,
has55 frames at30Hz. Fresh SDK conversion preserves authored motion, with no
IK/contact cleanup/loop closure. `inspect_updated_source.py` compares authored
clavicle-relative shoulders and pure rigid-torso robot projection separately.
Fresh10:10:15UTC Unreal PHAT export matches canonical source-rig exactly.
Twist peaks R/L: authored60.7453/60.5029deg; robot50.0714/46.0837deg, versus
current limits38.75/33.46deg. Coupled swing fits. All1,732 Jolt classifications
agree. Evidence and interactive viewer:
http://127.0.0.1:8843/Saved/MimicKitCrawl/updated-source-2e849ce9c900/ .
Authored/robot selection, playback and peak-frame controls verified; screenshot
comparison.png saved. Full posed geometry reflects world Y for correct display
handedness, preserving names and motion data. The same display fix is applied
to upperarm-pose-audit and constrained-ik HTML (old screenshots remain historical).
No PHAT, policy/AE clip, dataset or training changes. Older results below use
the previous source FBX, not this edited source.

**Constrained contact-IK review candidate — October17:** user requested keeping
hands planted while removing the cleanup's excessive upper-arm rotation.
`constrained_contact.py` solves both arms together, preserves previous hand
positions/orientations exactly at keys, compensates head orientation, and retains
pelvis/legs/travel. Current PHAT shoulder/elbow/wrist limits are explicit
constraints with0.25deg margin; source-pose distance and correction continuity
are minimized. A rejected first pass had an elbow branch jump; continuity
weight20 resolves it. The full torso/head-limit probe did not converge, so the
accepted candidate explicitly constrains arms only and reports other conflicts.

`verify_constrained_contact.py` checks433 keys and1920Hz interpolated samples:
20,742 arm poses accepted by exact project Jolt; peak shoulder twist R/L
88.55/64.59 ->38.50/33.21degrees. Maximum hand interpolation deviation0.091mm;
planted floor gap/error0.749mm; penetration0.176mm; closed loop seam<0.0001mm;
max adjacent world rotation4.924deg. Torso/head/left ankle still exceed limits;
head's violating sample count increases346 ->675/3457 due to compensating torso
changes while preserving head world orientation. Not a full-body valid clip.
No PHAT edits or training restart. Original policy and AE clips unchanged.
Candidate and validation: Saved/MimicKitCrawl/constrained-ik/ . Open viewer:
http://127.0.0.1:8843/Saved/MimicKitCrawl/constrained-ik/ . Verified playback,
side-by-side close-up and scrub to previous worst frame280; overlay/source
comparison also available. Candidate is not installed into the training package.

**Upper-arm pose comparison — October17:** opened read-only viewer
http://127.0.0.1:8843/Saved/MimicKitCrawl/upperarm-pose-audit/ . The worst cleaned
crawl target is selected by minimum angular distance to the current admissible
shoulder rotation set. `upperarm_pose_audit.py` checks433 keys per shoulder,
with multistart constrained optimization and exact Jolt acceptance of the final
float32 poses. Right frame280:38.2449deg; left frame80:26.0757deg. Only selected
upper-arm local rotation changes; downstream elbow/hand follow, other local
rotations remain fixed. This is not a whole-body constrained/contact IK result.
Viewer provides synchronized target/closest cameras, overlay, close-up and joint
selector. Saved data.json includes clip/limit fingerprints, poses and method.
No training, PHAT, or motion file changes.

**Single current PHAT package correction — October17:** `prepare.py` now uses
`current_phat.py`, never historical profiles. Current source-rig and saved asset
hashes are checked; the three packaged model/limits/physics files are byte-identical
to Labs/MimicKitUEFN. Existing package and source.zip updated and verified, with
prior artifacts retained under before-current-phat-sync-20261017_112325.
Motion files unchanged. Bundle/start refuse stale current-PHAT validation;
start also compares remote assets against current local hashes. Preflight derives
locked-ball counts from actual modes (currently zero), not old ankle assumptions.
Four-world, three-tick no-learning physics check confirms loaded modes/angles,
zero bilateral ball rows and finite solver state. This is a loading check only;
full preflight/resume validation remains stale and training was not restarted.
Evidence: current-phat-sync.json and current-phat-analysis/package-verification.json.

Shoulder analysis specifically traces the source UEFN crawl/idle through robot
reduction and contact cleanup; no LAFAN motions are used. Upper-arm local rotation
changes from contact IK reach41.29deg right/43.00deg left during crawl. PHAT-frame
twist maxima R/L: full authored skeleton65.38/60.33deg; reduced robot55.93/46.09deg;
cleaned robot88.55/64.59deg. Actual current limits38.75/33.46deg. These connector
angles are distinct from authoring Euler values or visible arm direction. Cleanup
worsened the target constraints; source pose, reduction and fitted target must
not be conflated. Stage details: current-phat-analysis/shoulder-stages.json.

**Current PHAT analysis — October17 (package mismatch corrected above):**
User requested redoing analysis only, not restarting training. The current user
PHAT is authoritative; do not use pre-running archives as an alternate PHAT.
Fresh read-only export09:12:05UTC matches Saved/MimicKitUEFN/source-rig.json
exactly. Both ankle twists are limited (right31.27deg, left26.62deg), not locked.
Current canonical geometry and constraint frames match the policy copies.
The packaged limits still differ from current PHAT: previous restoration of
historical profiles was incorrect; only wrists had been corrected. No runtime
or package fix is claimed by this analysis, and nothing was restarted.

Audited only the actual cleaned policy crawl (433frames at240Hz) and idle
(48frames at30Hz, interpolated to240Hz), with the exact project Jolt classifier.
11,340 joint samples agree with the numerical coupled-swing classification.
Outside percentages are reference-pose samples, not policy failure rates:

| Joint | Crawl | Idle |
|---|---:|---:|
| Torso |100%|100%|
| Head/neck |10.16%|0%|
| Right shoulder |71.59%|0%|
| Left shoulder |67.90%|0%|
| Right wrist |42.26%|0%|
| Left wrist |33.95%|100%|
| Left ankle |80.14%|100%|
| Elbows, hips, knees, right ankle |0%|0%|

Torso swing1 reaches53.90deg crawl /30.38deg idle against15.71deg.
Left ankle swing2 reaches38.59deg /27.07deg against20.57deg; twist fits.
Idle left wrist exceeds the coupled swing ellipse even though individual
coordinate maxima are within their separate bounds. Contact IK did not enforce
these limits. Therefore cleaned ground-contact targets are not simultaneously
admissible under the current constraints; fitting hand clearance alone did not
establish feasible references. No PHAT/clip changes made by this audit.
Evidence/scripts: Saved/MimicKitCrawl/current-phat-analysis/{export_current.py,
live-rig.json,export-receipt.json,analyze.py,report.json,jolt-output.csv}.

**Contact cleanup / one-hour resume authorized — October17:** cleaned crawl
hand targets using authored XY/orientation and nonnegative box clearance.
433keys at240Hz preserve duration1.8s, pelvis/legs/travel and loop closure.
Dense check: planted hand gaps <=0.754/0.221mm; reference penetration <=0.142mm.
Idle and offline AE/originals unchanged. `crawl_contact.py`, `repair_references.py`
and `refresh_contacts.py` reproduce and verify the policy copies.
Resume checkpoint701 with original learned state.16-world test passed301
deterministic+160 noisy steps, finite/solver checks. Physical penetration still
reaches4cm; disclosed, no claim of a dynamic contact fix. Solver/limits unchanged.
Replay selection now1idle/11crawl with auto-phase capture, verified in preview.
Deploy `--resume-after-contact-cleanup --seconds 3600`, then `start --resume`.
Launched `20261017_081535_uefn_crawl_velocity_512` on pod `o6qhah385ykhhx`,
deadline09:13:50 Warsaw; trainer393, exit guard394, local guard11832.
Resume702 verified, training advancing; live replay verifies1idle/11crawl and
phase. Cloud upload failed with QuotaExceeded; checkpoint702 copied locally and
checksum-verified. `local_backup.py` helper18260 polls latest immutable archives;
pointer `local-backup-status.json`, files `local-checkpoints/<run>/`. Do not use
stale S3 pointers for future resume. Exit watcher572 replaces394 and waits for
local checksum acknowledgement, capped by original hard stop; deadline guards
unchanged. Cloud error preserved/disclosed. No storage deletion/resize.
Active receipts hold identity/deadline. Prior run saved
under stopped-run-20261017_065646; other loco unchanged.

**STOPPED at user request — October17:** crawl hands hover; only crawl_idle
received hand-contact fitting. Crawl got loop closure only, not stance-contact
cleanup. Pod `g525r7hbc356yo` confirmed EXITED (Unix1792216522); receipt
`hovering-hands-user-stop.json`. No automatic restart. Local crawl observers and
deadline guard retired, assets/checkpoints preserved, loco untouched. Replay
selection also still incorrectly shows11idle/1crawl; actual training20/492.

**TensorBoard display correction — October17:** auto-phase was already trained
and present in raw events. Added crawl objective to dashboard mapping and
backfilled three crawl histories, validating exact steps/values against raw
events. `auto_phase/mse`, `auto_phase/weighted_loss`, `loss/auto_phase` and body
loss components now publish. Only local dashboard restarted (PID17188);
training unchanged. Receipt `autophase-dashboard-fix.json`.

**Continuation authorized — October17:** resume latest verified iteration100
with saved policy/optimizer/normalizers and corrected wrists for two hours.
16-world local saved-policy rollout (160ticks noiseless +160 noisy) passes
finite/solver checks; residual hand depths reach26.74/30.74mm. This is disclosed
and not marked as a clean ground-contact regression. Explicit continuation uses
`launch.py deploy --resume-after-wrist-correction` then `start --resume`;
receipt `resume-contact-acceptance.json` preserves the test and user request.
No experimental ground recovery installed. New pod `g525r7hbc356yo`, deadline
08:53:55 Warsaw. Continuation `20261017_065646_uefn_crawl_velocity_512`
launched with `--resume`; trainer412, exit guard413 and local guard13676.
Resume verified: optimizer/normalizer restored,1,654,784 prior samples,
first continuation checkpoint101 independently hash-verified from storage.
Trainer advanced through five resumed updates; no failure/solver warnings.
Both remote wrist profiles confirmed60/45/90. See resume-start-verification.json.

**Wrist correction — October17:** the stopped run incorrectly restored old
30/20/50deg wrists instead of the user's saved60/45/90deg. `prepare.py` and
the local package now preserve the saved wrist profiles. Other pre-running
profiles stay unchanged; live PHAT untouched. With the original contact solver,
the same controlled idle now reaches1.07mm/15.77mm hand penetration versus
50.70mm/59.08mm before, within existing20mm slop in this test. The experimental
ground recovery is NOT installed or justified by the old-wrist experiment.
Full dynamic validation remains outstanding; deployment stays blocked.
Evidence: `hand-penetration/corrected-wrists-ablation.json`; prior limits and
audit saved under `hand-penetration/before-wrist-correction`.

**STOPPED again for confirmed dynamic hand penetration.** User reported hands
below ground; exact physical hand-box support heights reach 5–6cm penetration
in both the local preview and new run iteration100. Pod `i2nng9pcr65ldu` is
confirmed EXITED; see `penetration-stop-receipt.json`. Previous checks passed
initial contact and equation residuals, but did not validate dynamic ground
penetration. Local physics investigation in progress; do not restart yet.

**Current status — fresh restart launched October17.**
`20261017_061639_uefn_crawl_velocity_512`, Secure L4 pod `i2nng9pcr65ldu`,
512 worlds; source hashes verified on the remote machine. First PPO update and independently verified checkpoint backup complete;
trainer/guards alive, no reported solver or backup errors. Hard stop **08:14:56 Europe/Warsaw**, $0.59/hour, two-hour
allocation including setup. Only corrected UEFN crawl/idle; AE dataset separate.
Previous run `20261017_054944_uefn_crawl_velocity_512` stays stopped and archived.

# Crawl training

User-authorized separate two-hour crawl PPO experiment. Existing locomotion
pod, source archive, Unreal PHAT and editor remain unchanged.

Current preparation: `Saved/MimicKitCrawl`. Built from the deployed locomotion
archive SHA-256 `53e01c707017a9f79942113ab38da91253242d4723ff5de6f6e2ba464492f02a`.
The copied runtime is isolated under `package/`; edits to it are reproduced by
`prepare.py` and `patch_runtime.py`. Do not deploy the global loco package here.

## Requested training contract

- Fresh actor/critic, optimizer, normalizers and counters. Same PPO settings,
  1024/1024/512 actor and critic, fixed normalized action noise 0.05.
- 512 worlds: fixed 20 idle and 492 crawl, the closest whole-world allocation
  to 4%/96%. Only UEFN crawl/crawl_idle; LAFAN is AE-only. No adaptive resampling.
  Random starting times within each permanently assigned clip remain as in loco.
- 153 observations: 146 physical values, idle/crawl scalar (-1/0), four reserved
  limb-enabled values (right arm, left arm, right leg, left leg), circular phase.
  All limbs stay enabled. No direction, speed or drawn/sheathed command inputs.
- Same 34 velocity motors at 30 Hz / 240 Hz physics, gains/caps/contact settings,
  zero added armature and reference-speed-plus-torque-headroom command bounds.
- Same four weighted world-body MSE terms, pelvis-XY-aligned targets, COM velocity
  band MSE and supervised auto-phase auxiliary. `exp(-sum)` physical reward.
  Same fixed coefficients as loco. **No AE reward or inference in this run.**
- Only failure: a head/hand/foot collider centre exceeds 27 cm from its target.
  No ground-contact or additional stock pose-failure conditions. Ten-second
  timeout remains; both clips wrap, so there are no clip-end resets.
- Two policy clips: UEFN `crawl` (55 frames) and `crawl_idle` (48 frames), both
  30 Hz. The LAFAN cuts belong only to the separate offline AE dataset. Each
  training export gets one rigid yaw/XY alignment. Original datasets and AE
  exports remain unchanged; corrected policy copies live in `corrected-references`.
- Idle hand contact is restored by constrained torso/arm fitting: source hand XY
  and orientation, box bottoms at Z=0, unchanged pelvis/legs/body lengths.
  The reduced rigid torso had raised both hands about 6 cm; original robot hand
  boxes floated about 4 cm. All 48 corrected frames have <0.001 mm floor gap.
- Idle already closes. Crawl has a small authored endpoint mismatch; ease its
  last eight frames to opening articulation/height (maximum local correction
  4.124 degrees, height 0.48 mm), preserving all root XY travel. Both use WRAP.
  `repair_references.py` reproduces candidates and verifies position/rotation
  closure before `prepare.py` builds the package. No original files are changed.

## Stopped-run diagnosis

Screenshot row was world 0, idle, iteration 0: terminal flag 2 at 20 ticks
(0.6667 seconds), starting at 58% of the 1.5667-second clip. Maximum collider
deviation was 8.38 cm (head), below the 27 cm threshold. It ended at the clip
boundary, not from tracking failure. The old package, manifests, replay checks,
and source archive are preserved under `stopped-run-20261017_054944`.

## Original limits and physics checks

The crawl-only asset retains the current 15-body/34-DOF geometry, mass, inertia,
frames and motors, while restoring retained angular modes/bounds from
`Saved/MimicKitUEFN/before-omni-limits/live-rig.json`, EXCEPT both wrists which
preserve the latest saved user profiles from `source-rig.json` (60/45/90deg).
No live PHAT restoration.
Receipt: `original-limit-restoration.json`. The source motions exceed several
original bounds, particularly wrists and ankle twists: `reference-limit-audit.json`.
Tracking these exactly is not physically admissible; training must work within
the requested limits and existing target tolerance. No silent limit expansion.

Two isolated runtime compatibility changes are necessary for crawling:

1. Original ankles have locked twist. Add an always-active bilateral local-X
   velocity row and zero-twist position projection, following the local Jolt
   `SwingTwistConstraintPart.h:420-424` construction. Other ball axes remain
   limited. `test_locked_twist.py` checks 129 rotations including identity,
   row activation/sign freedom and clamp against an independent construction.
2. Crawl contacts can exceed four points for one shape pair. Existing manifold
   equations already loop over all generated points; remove only the four-point
   admission restriction, retaining capacity checks, every normal row, friction,
   spin, convergence thresholds and solver iterations. This does not claim an
   identical manifold reduction to native Jolt. `test_contact_capacity.py`
   independently checks grouping/centroid/radius for 1,2,4,5,8,16 points.

`preflight.py` exercises actual CUDA physics, subset/full resets, observation
contract, fixed allocations, one disposable PPO update, noiseless capture and
replay loss reconstruction. Failed logs remain under the saved state directory.
Only a passed report permits `launch.py deploy`.

## AE and datasets

`crawl_idle.fbx` SHA-256
`c2c11c9bd05efc4b56792200f8a35b2f3293b6e5afc162d076a004073a5fc674`
was appended to both `Documents/Lafan Cutter/datasets/crawls` and `crawls_uefn`.
All three prior clip hashes are unchanged; imports preserve source FBX and
conversion receipts. The original skeleton round-trip error is below 0.000019 cm.

Updated 2x512/latent128 AE:
`Saved/RoboticCrawlAE/runs/20261017_053724_crawl_idle_2x512`.
Completed 3,000 updates, best at 1,000, validation MSE 0.063653; four equal-weight
clips for this offline AE (the 4% policy idle allocation is separate). Export and
basic corruption checks passed. This AE is reserved for future perturbation work.

## Deployment

`launch.py deploy` rents a separate Secure L4 at no more than $0.59/hour, with a
two-hour hard deadline from allocation, independent local/remote billing guards,
and failure stop/verified backups. Setup consumes part of that bounded window.
`launch.py start` verifies remote source hashes and starts fresh PPO, then the
existing low-bandwidth replay/TensorBoard observers. It never renews the deadline.
Active identity, receipts and guards live only in `Saved/MimicKitCrawl`.

## Corrected-package validation

`preflight/report.json`: 16 actual CUDA worlds, one disposable PPO update,
solver checks and eight-row replay passed. Initial idle hand floor gaps are
0.0040 / 0.0039 mm after runtime interpolation. Real termination-path tests
confirm no reset after passing both clip lengths, failure at 27.1 cm, and the
existing 10-second timeout. Both locked ankle rows remain active. This is
a wiring/numerics check, not a trained-policy quality claim. Original joint
limits still conflict with some reference poses; the audit remains unchanged
in purpose and no limits were expanded. Local preview in the policy viewer:
`mimickit_crawl_contact_fix_preview`. No cloud restart or production weights.

## Confirmed dynamic contact defect

`hand-penetration/diagnosis.json` summarizes exact replay support-height audits
and a local zero-command ablation. Angular position correction ON produces
5.07/5.91cm hand depth; OFF gives0.025/0.040cm. One correction pushes hands
down3.58/4.35cm after the velocity contact solve. The deployed solver has no
floor position recovery; previous loco evidence had stayed within2cm slop.

`ground_position.py` is an isolated GPU prototype, NOT installed in the package.
Using Jolt's2cm slop /0.2 relaxation /20cm cap with four passes lowers policy-
tick penetration to2.13/2.11cm, but its first substep still reaches2.64/2.95cm.
It preserves generalized velocities exactly. This is diagnostic evidence, not
a completed production fix or proof of Jolt equivalence. Coupled joint/contact
residuals, all-body/random-action behavior, CUDA graphs and throughput remain
to be validated. `launch.py` requires dynamic_penetration_validated=True, which
is currently false. Cloud is stopped; no automatic restart.
