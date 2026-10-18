# Prophecy — current handoff

Updated **October 18, 2026**, after the bomb fuse and detonation verification. This file and the current sections of linked topics take precedence over dated archives.

## Resume here

**Fragment transparency fade — October18 installed/verified, no restart:** Light
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
solid through120, fading121–239, destroyed240 for lifetime4/fade2. Both solid/half
screenshots inspected. Editor6904 remains explosionVFX/outside Play; user dirty map
and NewNiagaraSystem untouched. Base DLLs require minimal normal build before next
cold launch, incorporating fade, fragment toggle and impact event. See
[BombFuse](Docs/BombFuse.md); Saved/Diagnostics/BombFragmentFade, Tools/BombFuse.

**Explosion impact event — October18 installed/verified:** six-file extension,
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

**Fragment toggle — October18 installed, no restart:** Light Bomb Fuse
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

**Flexible bomb fuse / Niagara / hide / instant — October18 installed/verified:**
User requested the scabbard-style cosmetic dynamics, stiffness node, optional
Niagara at the moving burn tip/tangent, permanent hide node and instant detonation.
New skeletal asset prepared from original mesh (five AnimDynamics joints, fixed
shell), reusing existing holster native solver. Set Bomb Fuse Stiffness enables
or tunes it; Light Bomb Fuse has optional Fuse Sparks, Spark Rotation Offset and
Instant Explosion. +X follows the outward tangent at the deformed burn cut.
Empty Niagara means none. Hide Bomb Fuse permanently hides it per runtime instance,
stops dynamics/sparks and retains any running timer. Instant works immediately,
even on a hidden/already-burning bomb; zero burn speed accepted for instant only.
Body material now follows current original-component material during burning too.
Editor6804 exited after preserving current A_Bomb, PressureBomb
and new generated skeleton; it again hit a Slate shutdown error after saving.
No force kill. Minimal normal build6 actions passed139.46s; **base DLLs current**,
including all preceding bomb patches. Editor6904 open on explosionVFX/outside Play,
no dirty packages. Saved user assets match preservation hashes; graph untouched.
323 owned Play samples pass,179 spark-tip samples error<4.72e-7cm and tangent
dot>.999999. Hide, instant, null Niagara and material behavior checked. Combined
native test passes after Play initialization; first cold isolated invocation had
velocity failures, documented honestly in topic. Separate actual Play check of
all20 fragment velocities passes. No extra restart to investigate test harness.
See [BombFuse](Docs/BombFuse.md). Evidence Saved/Diagnostics/BombFuseFlexible;
reproducible tools Tools/BombFuse. Explosion impact-event extension stays PAUSED.

**Light Bomb Fuse — October18, installed and verified:** node in Prophecy/VFX
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

**Spawn VDB Effect node — October18, installed and verified:**
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

**Crawl stopped at user request — October17:** user cancelled the additional
hour. Stop request reached run20261017_135639_uefn_crawl_velocity_512;
checkpoint1628 was saved and checksum-verified locally (SHAb2d38e957d29).
Owned pod o6qhah385ykhhx explicitly stopped; API confirms EXITED. Active run
marked stopped, latest verified pointer updated. No further training restart
authorized. Receipts: Saved/MimicKitCrawl/user-stop-confirmed.json and
local-backup-status.json. The previously planned14:58 finish is cancelled.

**Additional crawl hour startup (now stopped) — October17:** previous35-minute run
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

**Updated-source AE completed /35-minute policy continuation running — October17:**
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

**Upper-body PHAT saved in place — October17, user authorized:** nine profiles
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

**Current-source shoulder-limit overlay — October17:** updated-source viewer now
has a checked-by-default "Show shoulder limits" checkbox. Green arms show both
nearest admissible shoulder rotations, for authored and robot views at all55
frames. Other local joints stay fixed; hands follow, with no planted-contact
solve or dynamic simulation. `add_source_limit_overlay.py` uses constrained
multistart quaternion-distance optimization; all220 resulting shoulder samples
accepted by exact project Jolt. overlay-verification.json records corrections.
Full-geometry handedness correction retained. Source/PHAT/training unchanged.

**Updated authored crawl and viewer handedness — October17:** freshly imported
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

**Planted-hand arm IK candidate — October17:** user requested fixing excessive
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

**Worst upper-arm pose viewer — October17:** read-only comparison opened at
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

**Crawl package corrected to the single current PHAT — October17:** removed
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

**Current PHAT crawl analysis — October17, read-only:** user clarified that
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

**Crawl contact cleanup and one-hour resume — October17, authorized:** user
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

**Crawl STOPPED at user request — October17, hovering crawl hands:** pod
`g525r7hbc356yo` confirmed EXITED at Unix1792216522. User correctly flagged
that only crawl_idle received hand-contact fitting; crawl received ONLY an
eight-frame loop-seam correction. Crawl stance contacts were not cleaned or
validated before training. Do not describe both references as contact-corrected.
Receipt `Saved/MimicKitCrawl/hovering-hands-user-stop.json`; active_run marked
stopped_by_user_hovering_hands. Local crawl observers/deadline guard retired;
other locomotion run untouched. No automatic resume. Existing assets/checkpoints
preserved. Separate replay-selection bug also remains: first-agent fill yields
11idle/1crawl previews despite actual20idle/492crawl training allocation.

**Crawl TensorBoard auto-phase display fixed — October17:** phase head/MSE were
already trained and logged. Local dashboard omitted `uefn_crawl_idle_mse` from
its tracking-loss/auto-phase mapping. Added that objective and backfilled all
three crawl histories from raw events; exact step/value equality verified.
Charts `auto_phase/mse`, `auto_phase/weighted_loss` and `loss/auto_phase` now
publish, along with body-loss components. Restarted ONLY current crawl dashboard
(PID17188), no trainer/optimizer/run changes. Receipt
`Saved/MimicKitCrawl/autophase-dashboard-fix.json`.

**Crawl continuation authorized — October17:** user requested resuming latest
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

**Crawl wrist correction — October17, supersedes the diagnosis below:** user
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

**Crawl stopped again — October17, confirmed hand penetration:** user observed
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

**Crawl restart — October17, approved after corrected replay review:** fresh
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

**Crawl correction — October17, after user stopped the run:** policy dataset
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

**Crawl policy STOPPED at user request — October17:** user authorized a
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

**Smaller crawl AE1 — October17:** user requested **2 x 512 hidden neurons per
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

**Initial crawl-only robotic AE1 baseline — October17:** user clarified a separate crawling agent,
with ONLY the three curated crawls and no locomotion/idle additions. Authorized
local AE training, now COMPLETE separately in
`Saved/RoboticCrawlAE/runs/20261017_044043_crawl_only_ae1`; `completed.json`
records 12,000 updates in 382 seconds, best checkpoint at update 1,000 (balanced
validation MSE 0.099568). Exported `scorer.pt` passed parity and input-gradient
checks. Root-jitter costs increased in all test windows; body-jump costs in
94.7–100%; heading/XY score drift <=9.27e-5. Timing-shuffle check increased cost
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

**Lafan Cutter / crawls — October17:** native curator at `Labs/LafanCutter`,
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


**Explicit elbow posture / wrist twist — October16 current:** user reproduced a
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

**Unreal port/build state — user-requested grab behavior restoration:** user rejected
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

**Historical approach/held-elbow port to Unreal — October16 (superseded above):** explicitly requested by
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

**Left elbow hitch — October16 historical intermediate fix:** in the unmodified current
TestNN tick30 fixture, commanded left elbow made~0.9cm single-tick jumps at193,
218,256,275,307; the physical elbow followed. Wrist and shoulder stayed smooth.
Cause: fixed coarse half-step search near wrist alignment. Both lab `coupled.js`
and native `ProphecyReachArm.h` now scale elbow/roll search steps with remaining
quaternion error, retaining full steps above8deg and the same18-evaluation cap.
No new search/state or tolerance changes. Reconstructed one-step replay matches
the hitch within0.0004cm; full owned360-tick same-fixture capture verifies max
left-elbow step across absolute200–300: command0.90093→0.05366cm, physical
0.90080→0.05329cm, commanded angle2.252→0.131deg. Left physical grip acquires at111
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

**Reach/grab Unreal port — October16 complete:** user explicitly authorized the
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
**PHAT limits — October16:** at the user's request, saved seven angular-profile
expansions to contain the drawn/unarmed motion dataset plus5% room. Upper arms,
thighs, ankles and right knee changed; both user-edited wrists remain60/45/90deg.
Frames, geometry, mass/inertia, collisions and Blueprint wiring are unchanged.
Exact values and backup are in `Docs/MimicKitUEFNBodyMatching.md` (current section).
The REACH imported snapshot described below predates these seven expansions;
its lab files/session were not changed by this PHAT update.
**Lab refresh preference:** the user handles Refresh with the lab button. After
code edits, do not automatically reload, close or reopen their lab window. Leave
the running session alone and report that the change is ready to refresh.

**REACH elbow blend slider — October16:** **Elbow down blend** sits directly
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

**REACH rotation timing — October16:** shared right-panel **Sync rotation** slider
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

**REACH PHAT snapshot — October16:** imported the user's newly edited loaded
PHAT wrists into `Labs/ReachLab/phat.json`: both hands60/45/90degrees in
twist/swing2/swing1 order, all LIMITED; frames unchanged. Lab HTTP export matches
the file. Ready for user's manual Refresh; no build/restart/Play or asset save.
Before/after evidence: `Saved/Diagnostics/ReachPHATImport20261016/`.

**REACH elbow preference — installed and verified:** only `PreferredBend` in
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

**Current REACH solver — arm first:** the old forearm-derived virtual endpoint
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

**Reach lab ready — lab first, port later:** user requested the same rapid iteration
workflow as D/S. [REACH — Hand & Body Lab](Labs/ReachLab/README.md) runs at
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
icons use the user's latest captured values: L13/60/125cm with rotation180/0/90°,
R−14/47/125cm with rotation0/0/−90° (October15 explicit default update).
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

**Reach lab grab pipeline complete — October15:** both hands now have Grab ball
and one shared persistent **Ball radius** slider below the centered clamp checkbox
(0.5–15cm, initially3cm). It updates both balls together; per-hand radius inputs
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

**Complete — grab-angle Blueprint node:** user explicitly requested adjustable
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
Prophecy → Grab; call Set Grab Angle Tolerances before Grab Object/Grab Bone.
No user Blueprint wiring or default tuning changed. Evidence:
`Saved/Diagnostics/GrabAngleTolerances20261015/`.

**D/S motion is TEMPORARY FINAL, accepted by the user.** Preserve the accepted lab/Unreal motion and tuning; change it only on a new user request. Latest reported Sim slowdown was not reproduced, and the user subsequently said it looked good. The explicit right-wrist limit follow-up is complete; no implementation task remains active.

- **Current review setup:** user removed the continuous D/S branch and requested the October12 two-ball grab experiment on their existing one-shot tick30 branch. PoseAgent and TestNN are now saved locally with two radius3cm spheres assigned to the player. Ball physics prepares at tick29; both Grab Object calls start at tick30,120cm/s and180deg/s. Player sword hides at the trigger; grabs stay held for user review. See [reach/grab review fixture](Docs/ReachGrasp20261012.md). No reach/grasp runtime solver or D/S tuning changes; no commit/push.
- **Wrist-limit follow-up complete:** D/S frees the hand_r–lowerarm_r joint's three angular motions through the full return, then restores the exact entry motions/angles through existing completion/interruption cleanup. Retained layouts unchanged. Four owned-PIE checks/498 sampled checks pass, including custom limits, repeated requests and hide during both returns. Full BP graph unchanged; no assets saved/restart. Current user graph starts S during initialization; diagnostic waits for it to finish before its controlled D/S pair. [Wrist-limit lifetime and evidence](Docs/SwordHolster.md#right-wrist-limits-during-ds-october15-follow-up).
- **Reach/grab PHAT follow-up complete:** user requested hand control follow the edited PHAT automatically; explicitly reach/grab only, D/S excluded. Native overlay reads loaded asset wrist frames/modes/angles each active update and constrains hand orientation, including release return. 4,860 math cases and804 live wrist samples pass across Kin reach, Sim reach and Sim ball grabs. Editing an isolated transient PHAT during an active Kin reach updates the clamp without restarting it. **Ball fixture limitation:** both target positions reached, but neither grip acquired by210 under current wrist limits; no success claim for grasp acquisition. User asset unchanged, no retained layout changes/save/restart. [Details and evidence](Docs/ReachGrasp20261012.md#phat-wrist-constraints--october-15).
- **Remote checkpoint:** commit `965b9cb4ac649f8f4ce7604e9a6b5c33588b1536` on `codex/standalone-sim`; annotated tag `ds-temporary-final-2026-10-15`. Branch and tag verified on GitHub. Previous broad D/S checkpoint `b34e1b31` is its parent. Recovery manifest verifies all 5976 recorded files; this is a curated backup, not the whole project/machine.
- **Finger rendering follow-up:** grab calculation was active but LOD1 removed finger bones (`r.SkeletalMeshLODBias=1`). Saved test player's Mesh/PhysicalMesh Forced LOD Model1 (=renderLOD0) in TestNN, matching the original experiment. Attack Fists already enabled; no graph/runtime/global-LOD changes. Kinematic LOD0 finger/model error<3e-7cm; physical native finger poses already present and LOD0 selected with the pre-Play override. Evidence `Saved/Diagnostics/ReachGrabFingers20261015/`; use next Play for the saved override.
- **Editor:** grab-angle implementation required one normal build/restart. Its first launch mistakenly used WindowStyle Hidden; user reported no visible editor. Clean hidden editor25832 was closed and reopened visibly as13040, without another build or asset changes. Use **Normal** for the requested interactive editor/browser; **Hidden** only for background helpers. Latest lab task preserved this running editor. User PoseAgent/TestNN edits saved with prior disk backups; PHAT unchanged. Reflection status3/native_properties0/pin_types0; wiring preserved. Remote checkpoint predates these local assets and does not contain this scene.
- **Build:** normal incremental editor build succeeded in492.43s for the grab-angle node and incorporated preceding Live Coding patches through20. **Normal DLLs are current.** Keep future builds minimal/incremental and prefer reload-safe implementations where appropriate. Do not restart just to tidy, save, inspect or tune; retained native storage/layout changes still require normal build/restart.
- **Last saved asset verification:** PoseAgent compiled status3 and saved with TestNN for the grab fixture. Against the user's live pre-edit full graph, only the existing tick30 Branch's unused Else and its terminal reroute's unused Output gained links;28 nodes added, no existing nodes removed or tuning changed. Both reaches active at absolute30, physical grips90/93, held through220. A_Sword untouched in this task. Native reflection health remains status3, native_properties0, pin_types0. Evidence `Saved/Diagnostics/ReachGrabWiring20261015/`.
- **Local-only work:** TestNN, generated defense pickers, separate MimicKitTraining/PhysicalRecovery work and unrelated PDF remain outside this D/S checkpoint. Do not stage, clean or overwrite another task's work. `ProphecyFKReturnFeedbackTests.inl` has appeared dirty without a semantic `git diff`; inspect before treating it as a new change.
- **Primary references:** [D/S runtime and integration](Docs/SwordHolster.md), [lab controls/recorded problems](Labs/SwordHolsterLab/README.md), [attached-arm physics audit](Docs/SwordHolsterPhysicsAudit20261014.md). Full old opening retained in the [October10–15 archive](Docs/Journal/ProjectJournal-history-through-2026-10-15.md); rejected trials are historical, not pending work.

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
| FK→IK arm-return blend |Enabled, fractions.25→1|Disabled|
| Coordinated elbow IK correction |Enabled,15deg soft zone|Enabled,15deg soft zone|
| Independent hand rotation FK alpha |1|1|
| Big-node NN blend range |(1,1)|(0.7,1)|

Other saved values: axial shrink25% over.25s, unshrink.5s; attached hand speed150cm/s and angular speed200deg/s. Big-node grip holster rotation compensation80%, return duration.25s, S kinematic switch fraction.5. Leeway attachment phase disabled; tip tolerance2cm. D hand-local-X turn800deg/s, sigmoid exponent1.5, cutoff.4 of arm return. Negative angular speed reverses it; afterward existing hand return continues. Return durations can include angle-dependent extra time; base duration is not necessarily total duration.

For later user-requested imports, `node Tools/SwordHolster/SyncLabProfile.cjs` exports saved lab settings; inspect its semantic diff before applying. Existing big-node pins override imported values. `Prophecy.Editor.RefreshHolsterGripPins SetSlideSpeeds <draw> <sheathe>` updates only unlinked speed literals; preserve every other pin and compare the full graph before saving.

Latest import changed only S slide speed170→230 and its curve's first interior point to(.15053891961839325,.0988776276854313). Other S points: (.650179602563385,.7111385494636496), (.8849101307618773,.9562043029634382), (.9553293659722167,.9884497709488423). D remained330/linear. In the current saved geometry: S18ticks/.30s, D13ticks/.2167s. Duration depends on blade travel/shrink, not a fixed duration override.

### Ownership, timing and mode switches

- Authored seconds use60 unpaused game ticks. NN inference cadence is separate. Reach/slide curves affect only their procedural motion, not underlying idle/walk/run, head or FK return; each D/S return has its own timing curve.
- Reach uses FK, authored spine/clavicle targets and explicit elbow preference. The rejected direct-IK **reach** trial is removed. This is distinct from accepted FK→IK **return** and coordinated elbow IK correction. Old forearm-only bend limiter remains deleted; Main inertia scales strength without shortening duration.
- Geometry comes from authored sword/holster placement and blade marker; apply asset scale once and shrink only along blade axis. Capture references before moving the mount. Holster follows the actual component; compensation rotates about its origin without introducing pelvis-relative translation.
- S aims tip at entrance with angular tolerance. Optional leeway attachment phase first attaches, then aligns the tip within attached speed limits, then slides from the reached depth. It must not reset insertion to0. Holster-relative speed limits are intentional. Current saved leeway phase is off.
- During attached alignment/sliding in Sim, native upperarm_r/lowerarm_r/hand_r temporarily become kinematic and follow the completed actual pelvis/clavicle and holster-local sword path. Remaining body stays simulated. Sword stays attached to holster; no separate predicted sword path or attached hand–sword joint. Release restores simulation from current pose/COM/angular velocities and seeds return from actual current/previous arm poses. Ordinary kinematic characters do not receive this native ownership override.
- Holster simulation switches independently; a kinematic agent forces a kinematic holster while retaining its preference. Physical holster temporarily goes kinematic at the configured S reach fraction / during D sliding. Rotation compensation then applies; usual rest return and original joint restoration resume the prior preference. Interruption cleanup restores owned limits, collisions, joints and modes.
- Tab switches Sim/Kinematic without cancelling D/S, restarting clocks/shrink or losing attachment. Kin→Jolt queues the **entire** mode change at the existing safe admission boundary, avoiding an intermediate Chaos step. Rebind waits for native ownership. Completed attached-arm pose is republished at transfer; stale presentation blend is retired. **No added Sim→Kin whole-pose fade**: that trial delayed moving actions and was removed.
- A_Sword's consuming Tab→pause event was removed; character Tab works, Caps Lock backend selection is unchanged. RMB debug slowdown now uses `t.MaxFPS`, not fixed simulation delta. All agent/equipment overlap events are disabled in both modes at user request; blocking collision and queries remain.
- D/S suppresses right-arm collision for the action, restores it on completion/interruption, and applies head–clavicle suppression only during D/S. Neck/head and right-wrist angular limits are Free through the full return and restore their captured entry modes/angles afterward. See the physical-neck reference below for permanent neck pairs. Early NN return protects the gripping arm until release; arm return then uses its own clock/window.

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
| Breathing | [Breathing](Docs/Breathing.md): default upper+pelvis, only at zero movement input; active through D/S. Successive cached idle deltas move actual accepted pelvis/upper pose; legs keep feet in place and NN history receives it. Independent pelvis/upper amplitudes; speed snaps.3→1 by.1 using shared pre-baked samples. No presentation-only overlay. |
| Physical neck | [PhysicalNeck20261013](Docs/PhysicalNeck20261013.md): original PHAT23bodies/22joints, neck_01→neck_02→head, approved capsule size and split neck mass; actual neck_02 feeds NN. Both necks exclude head/clavicles/each other permanently; head–clavicle exclusions only during D/S. Solver comparison option remains available. |
| Get-up | [GetUp](Docs/GetUp.md): remain simulated, restore magnetization; both-arm anti-jiggle until lower handoff then prior independent settings; magnetization0→1 at lower marker; slot1 includes PhysicalMesh material. Independent lower/upper handoff/tempering. Automatic floor-lift correction and its toggle were removed; explicit Ground Offset remains. Old tick30 hookup is historical—inspect current BP. |
| Native reach/grasp | [ReachGrasp20261012](Docs/ReachGrasp20261012.md): Reach Target/Double Reach/Grab Object/Grab Bone, durable local contact point and one joint per hand, fit fingers once. Ball and forehead prototypes tested; lower chin blocked; concurrent attack/get-up ownership not fully tested. Do not silently promote prototype to universally validated behavior. |
| Cosmetic holster strap | [HolsterStrap](Docs/HolsterStrap.md): separate asset/AnimDynamics work, editable ABP body definitions with linked constraints. Does not replace the existing agent holster or D/S. |
| Separate local tasks | MimicKitTraining and PhysicalRecovery files are local work from other tasks. Check their own docs/status before touching; this D/S cleanup neither validates nor stages them. |

## GOLDEN RULES — read before touching Unreal

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

## Omni locomotion recording viewer — October15

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
- UE first slashLD =lab **variant21**, absolute61–101,21 unique30Hz policy frames from41 ticks,25 bones, excluding physical response/post-attack return. UE XYZcm -> lab XZYmetres; imported UE variants bypass harness forearm-roll repair. Original320 variants unchanged. Backup includes current saved lab profiles/view.
- Accepted original FK return with inertia, **not optional continuous spring**. Idle is real Unreal `M_Neutral_Stand_Idle_Loop` frame0, same across attacks, parent-local. Hand local inertia zero, parents still move hands. Spine01–05 share one weight, arms symmetric. Main inertia, bone weights, return/easing/timing are per attack. Spine angle adds flat seconds (.29s/90deg default), independent of base duration.
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
- [Full October10–15 handoff history](Docs/Journal/ProjectJournal-history-through-2026-10-15.md) preserves every superseded opening entry and previous build/save/test claim. Read current summaries first.
- **Update current sections instead of prepending endless logs.** Keep build coverage, saved assets, defaults versus actual BP, evidence and limits explicit. Detailed experiments belong in linked topic docs/receipts. Archive superseded behavior, preserve user corrections, and never revive an old investigation as unsolicited work.
