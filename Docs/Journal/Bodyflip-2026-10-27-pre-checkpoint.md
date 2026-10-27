# Bodyflip work leading to the October 27 attack checkpoint

Historical notes; see Labs/BodyflipLab/README.md for current behavior.

**Bodyflip October27 - Direct to Armed applies to all16 attacks:**
Same viewport checkbox now labeled Direct to Armed, still after Raw leg. Added
matching control to soft-leg viewer; kick viewer retained. Existing saved toggle
key preserved. Timeline/manual upper14 blend current local pose directly to
Armed with velocity/acceleration continuity; Armed onward remains native, with
existing compensation/aim/variant/rate/follow-through/pelvis-only recovery.
Kicks retain their full-body solver.2596 direct-mode samples pass across all16;
manual/timeline parity<1.6e-16, upper native error<1.1e-14, Armed velocity join
<2e-5rad/s.84 off-mode cases/5100 samples unchanged. Syntax, aim and HTTP checks
pass. No browser control/state writes/restart; user Refresh. Local/unpushed.
[Current behavior and receipt](Labs/BodyflipLab/README.md).


**Bodyflip October27 - Direct to Armed checkbox placement:**
Moved Kick: direct to Armed from More options to the viewport checkbox row,
immediately right of Raw leg. Existing handlers/state retained. Raw leg is the
red original supporting jump-animation leg at native timing, pelvis-aligned,
without matching/IK/release blend; it does not alter motion. HTML placement and
served-file parity checked. No browser control/state writes; user Refresh.


**Bodyflip October27 - optional direct-to-Armed kick entry:**
Added Direct to Armed at right of viewer kick selector and Kick: direct to Armed
at bottom of app More options; default off, persisted. Shared viewer/manual/
timeline path skips recorded pre-Armed motion when enabled. Final Harness
native Armed lower bound: max(In, Armed/fps), then native Armed->Hit->End.
Direct local quaternion blend matches Armed velocity/acceleration; no stop there.
Existing full-body balance/pelvis-only recovery retained. Manual loop clock
shortens with entry; playhead retained on toggle.1182 direct-mode samples pass,
viewer parity<5.2e-14, hinges/COM/native strike/entry/recovery/seek checked.
1314 off-mode samples unchanged; persistence/placement/syntax/HTTP checks pass.
No scene writes, desktop/browser control, inference or restart. User Refresh
then enables checkbox. Local/unpushed. [Details](Labs/BodyflipLab/README.md).


**Bodyflip October27 - full-body kicks now connected to the app:**
App still used the spine-only attack mask, discarding recorded kick legs.
Shared kick-attack.js now connects the approved viewer solver to timeline and
manual Attack paths; kicks retain complete chamber/strike/follow-through and
pelvis-only recovery. Existing entry/out timing, selected variant/rate, moving
root/COM and smooth baseline entry/exit remain. Upper14 attacks unchanged;
Amount/Soft legs remain upper-attack controls, kicks use full-body balance.
Bounded cached plans prevent solving again for repeated markers.1314 kick
samples match viewer (<5.4e-15), including actual manual functions, moving gait,
rotations, sockets/hinges/COM/endpoints/seek.84 upper cases/5100 samples and2121
manual samples pass;90 sequence checks pass,32 overlaps2764ms. Saved Space gym
Kick L verified offline at Hit frame13; no scene writes. Current files served
byte-identically/no-store; user Refresh required. No browser/desktop control,
inference, workers or restart. Local/unpushed. Supersedes separate-preview status
below. [Current behavior](Labs/BodyflipLab/README.md).


**Bodyflip October27 - pelvis-only return; full attack follow-through restored:**
User rejected full-body direct return because it killed Slash R's post motion.
Recovery.pelvisReturn now returns only the pelvis from Hit to the ongoing baseline.
The source continues playing; inverse corrections at pelvis children preserve
all non-pelvis world orientations. Torso/arms/legs/weapon follow-through and
original timing are restored across all 16 timeline/manual attacks, rigid/soft/
zero compensation, viewers and both kick previews. Original end times unchanged.
Normal source recovery continues for other segments; kick COM remains fixed.
96 cases / 5784 samples verify every non-pelvis source orientation through the
whole follow-through (max 1.57e-15), exact strikes, monotone pelvis return,
endpoints, hinges/sockets and seek. Other 1390 return, 2379 integration, 1676
compensation and 7192 soft-leg samples pass. All 94 sequence checks pass;
32 overlaps 2202 ms. Twelve original/new Slash R collider+weapon frames reviewed.
Local/unpushed; no desktop/browser control, scene writes, inference or restart.
Existing service serves current scripts; user refreshes lab/viewers.
[Current behavior and validation](Labs/BodyflipLab/README.md).

**Bodyflip October27 - approved checkpoint pushed; airborne kicks refined in preview:**
Approved three-axis/opposite-angle state pushed and remote-verified as
`6a3c2f7c513c3313c9b0ad7e8e7ca7b7c17a403a` on `codex/standalone-sim`.
8943 recovery files verified (1,073,585,378 bytes; no LFS pointers).
Main lab still uses 50% = half opposite spine rotation on all 3 axes, no attack
exception. The prior 32-overlap timing limit remains documented.
Local `kick-preview.html` on 8876 now uses articulated momentum balance across
torso, shoulders and free leg, reducing pelvis overrotation and sideways spread.
The striking chain retains recorded world orientation, knee bend, hip-to-foot
direction and native timing; COM/pelvis motion can still translate its hip.
C2 source curves and velocity/acceleration-matched entry/return remove source-key
acceleration breaks. Damped balancing joints are followed by a common-body
momentum solve. Recovery returns the free leg while retaining whole-body turn.
No Kick L/R-specific response. Fixed sockets and hinged knees retained.
1136 dense samples pass through both full motions, including recovery, source
keys, strike direction, hinge/socket, velocity/acceleration continuity, COM,
seek, incoming spin and ballistic COM checks. Displayed solve residual <1e-8;
inter-tick RMS 0.15-0.18% of raw momentum. Both actual-collider comparison sheets
reviewed offline. Preparation about 0.6-0.7 s once per clip; bounded cached playback.
No browser/desktop interaction, scene writes, inference, worker or restart.
Kick work remains local/unpushed and isolated; main app/percentage unchanged.
User must refresh the existing kick viewer to see it.
[Current details, numerical limits and primary references](Labs/BodyflipLab/README.md).

**Bodyflip October27 - Slash L amplitude investigation (no motion edit):**
User noticed stronger lower-body rotation after3D integration. Controlled idle
Slash L at95%: previous peak pelvis yaw40.62deg, current124.85deg. Removing
lookahead gives125.02deg; restoring old leg-reference curves gives120.33deg.
Main cause is changed percentage semantics: old opposite spine-yaw angle target
versus new fraction of attack-added whole-body angular momentum. In-memory
restoration of only the old yaw target in the new solver gives18.94deg, so the
new distribution also changes amplitude; not a simple timing change. No runtime
code/settings changed. Audits in Saved/BodyflipLab/SpatialCompensation/slashL-*.json.

**Bodyflip October27 - Refresh matches Throw Lab:** green Refresh centered
below Copy/Rename/New scene in the top-right header; same styling as Throw Lab.
Existing top-row order and save/restore handler retained. HTML/CSS change only;
user Refresh loads it, no desktop/browser control.

**Bodyflip October27 - three-axis attack compensation, headbutt refinement:**
User approved the headbutt result and requested the full system for all attacks
without a rollout gate. Verified the running8876 service serves byte-identical
current app/response scripts with no-store; no attack-type gate exists. Saved
Space gym scene already has Soft legs enabled,95% compensation, Slash LD.
No redundant implementation or scene edits; refresh remains user-controlled.
Shared yaw/pitch/roll planner now serves all16 attacks, manual and scheduled;
no headbutt-name branch. Leg coordination blends from jump-throw to bilateral
counter-swing by measured upper-body rotation. Reference: Kristensen2002/2004
jumping headers; new joint-angle curves are qualitative authored targets.
The damped whole-leg response uses60 ms attack lookahead so it arrives during
impact, with60 Hz bounded planning and continuous analytic sampling. Upper
orientations, sockets and knee hinges preserved. Existing Amount/Soft legs UI;
Off compares rigid full rotation. Viewer now uses the actual main samplers for
Rigid /3D inertial comparison. All16-attack, manual/gait, signed3-axis and94
sequence checks pass;32 overlapping markers2834 ms. Displayed headbutt pitch
momentum RMS reduced44.9% at100% in the reduced model, not exact physical
conservation. Offline collider frames reviewed. No desktop/browser control,
live-state writes, inference or restart; user must Refresh. Local/unpushed after
681c75b5. [Current details and sources](Labs/BodyflipLab/README.md).

**Bodyflip October27 - whole-leg response integrated into the main app:**
User authorized deployment from the approved viewer to every attack. Shared
leg-response.js now drives the common compensation sampler for all16 timeline
attacks and all16 manual Attack-button paths; original upper motion retained.
Existing Soft legs and compensation controls, defaults and scene tuning retained.
Moving gait exposed a delayed knee-extension offset that could invert a knee.
Response now tracks available extension/flexion fractions, retaining smooth
angular motion without clipping displayed knees. Approved Slash L differs by
at most0.099degrees/0.735mm; its acceleration reduction remains75%.
7192 scheduled samples,2379 manual/moving-gait integration samples,94 sequence
checks (including32 overlaps), viewer parity/hinge/socket/seek checks pass.
**User stopped Computer Use and explicitly said not to use their computer:**
no further desktop/browser control; use background code/checks and leave Refresh
to the user. Existing app was not refreshed. No scene/state writes, inference,
Unreal/server restart or new push. Last verified remote checkpoint remains
`681c75b5` on `codex/standalone-sim` (8937 recovery blobs); this integration is
local. [Current behavior and validation](Labs/BodyflipLab/README.md).
