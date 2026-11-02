# Bodyflip native runtime

## Current state

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

The user accepted the current lab and requested the complete native port and
backup on November 2. The package now includes pike_final, both-arm return
protection, Pike heading/elevation aiming and the accepted continuous thrust
steering. The rejected06 chest lock is absent. Lab source hashes identify five
changed solver modules since the preceding port; only the Pike authored clip
changed. All earlier port behavior described below remains included.

Current settings: `Content/BodyflipLab/LabSettings.json`, copied read-only from
the live lab, with steering ON, source cutoff16, flip400/twist200, delay1s and the
current target/markers. **Start Bodyflip Saved Lab Setup** replays these exact
settings. Normal typed Settings now exposes **Pike: Steer Through Thrust** and
includes the same Pike cutoff. Existing Blueprint overrides remain untouched.
`Get Bodyflip State` Diagnostics Json includes `pikeSteeringFallback` when a fit
cannot be applied; it uses standard aim just as the lab does.

Normal Editor builds passed. TestNN is open in the normal editor. Cold reflection
is healthy (status3, native_properties0, pin_types0), and an owned Play startup
check advanced the existing Blueprint/NN for60 game ticks, then ended only that
owned session. No Blueprint/map/mesh assets or live lab settings were saved or
rewritten. Existing Blueprint compilation preserves all10,552 original pins/links.

Final evidence: `Saved/Diagnostics/BodyflipFinalPort20261102`; compact restorable
receipt: `Tools/Recovery/Receipts20261102Bodyflip/native-port-verification.json`.

- App versus package:18 cases /513 frames, maximum position difference7.54e-8m.
  Decoded inputs match exactly; Pike finite-difference roundoff changes fitted
  angles below1e-9degrees. The comparison permits1micrometre and1e-6radians;
  native physical-tracking limits were not relaxed.
- Pinned V8 versus Node:21 cases /607 frames /137251 numeric values, exact.
  Includes steering on/off, front/rear/fast flips and current/front/rear native
  rig variants. The front native-rig probe initially hit180s under load; isolated
  front/rear retries passed with600s time limits and unchanged numeric gates.
- Actual Unreal VM:513 frames /117,179 numeric values, exact. Package audit100
  checks passes, including current source, inputs, settings and protected assets.
- Initial native suite:16 pass,2 fail. Additional clear-air saved setup and full
  Unreal VM parity completed successfully. The host's900s overall limit then
  interrupted the repeated left-hand test; this is recorded, not treated as a pass.
- Clear-air saved setup:198 frames,6.76cm/12.96deg maximum physical tracking,
  0.466cm/0.492deg RMS,0.1094cm maximum leg-length error. Lowering only the physical
  test floor120cm preserves every canonical packet and removes all floor contacts.

**Remaining contact limits:** the original floor-level Space Gym setup commands
a foot into the floor during the flip and reaches89.2deg right-foot tracking
error. The combined left-hand push also fails the unchanged3cm leg-length gate
at4.125cm. Big/Small airborne throws pass. The earlier intermittent floor-level
Big Throw issue below is not declared fixed merely because this run passed it.
These contact issues are separate from the now-verified shared solver port.

The requested repository checkpoint includes the complete current work, exact
Pike FBX, saved lab profile, runtime/NN payloads and the pinned V8 DLL/license.
Other systems are backed up without claiming Bodyflip tests validate them.

## Earlier November 2 port verification (historical)

## November 2 port — built; one native floor-contact issue remains

The current accepted lab solver and captured tuning are ported and normally
built. This includes authored Lara/Snatch/Ball/Ninja poses, Keep/disabled jumps,
variant response and wobble, FinalNoAim throws, attack end frames, duration and
angular-distance return, coupled forearm/wrist inertia and the Pike interpolation
fix. No rejected braking or independent world-hand return was restored.

The exact settings are `Content/BodyflipLab/LabSettings.json` (November 2).
The read-only original snapshot is in
`Saved/Diagnostics/BodyflipPort20261102/lab-state.json`. The package includes
44 source modules and all authored inputs; no browser, local server or Node
process is required in game. It uses the existing pinned V8 integration.

### Controls and entry

**Start Bodyflip Saved Lab Setup** loads the captured Space Gym/Pike scene,
including target, all four markers (one enabled), platforms and timing, into
this agent's starting frame. It uses the agent's existing Kinematic or Physical
mode. This explicit node avoids changing the user's existing Blueprint wiring.

Normal **Start Bodyflip** retains idle/no-marker admission. New settings defaults
match the captured sliders. Existing serialized Blueprint values/connections
remain user overrides; they were not rewritten. Split Settings exposes motion
compensation, pelvis-to-five-spine transfer, 3D momentum, Space falling, shared
attack return duration/distance, per-attack end frames, shared pose blend/easing/
spin response and per-pose wobble. Legacy rate-based return is not revived.
Pose1–4 keep their enum values and display Lara/Snatch/Ball/Ninja; Keep is appended.
Legacy per-event pose blend pins remain compatible; shared settings own the
accepted pose transitions. Camera and playback UI are not gameplay settings.

**Queue Bodyflip Jump** exposes Enabled. Split Attack for an optional fixed
**World Throw Direction**. Native conversion treats it as a normalized vector
through the starting frame: translations and scale cannot bend the ray, and
later pelvis/root motion does not move it. Without a supplied ray the shared
throw solver aims from the target, retaining Small Throw's authored arc rule.
**Set Bodyflip Target** remains a UE world-centimetre point.

### Native corrections required by the port

The shared packet now carries `attackFree`. Native Jolt temporarily permits the
same authored attack/return joint freedom as the lab, then restores the live
user constraint limits. It changes only effective native limits, never PHAT or
mesh constraint profiles. Before this correction the native rig opposed legal
lab attacks; the saved Pike differed by up to 54 cm. The final saved scene has
5.212 cm maximum / 0.308 cm RMS body-position error across 198 frames and 23 bodies.

Fractional projectile release formerly inserted a release next to an existing
uniform collision cut. Small Throw produced a roughly 10-microsecond interval,
causing huge servo velocities. Mandatory release times now divide the frame
into spans, each subdivided evenly to respect the requested maximum step size.
Release times, total elapsed time, shared publication and other clients' queued
forces are preserved. Each resulting native Update also repeats activation
preflight: bodies can sleep between Updates, so the old once-per-frame preflight
could fault the rig after a throw returned to rest. Both throws now run through
the complete two-second fixture without that fault. No velocity cap, release
snap, extra damping or animation modification was introduced.

### Verification and remaining limit

Normal Win64 Development Editor build succeeded; the final host DLL hashes match
the project DLLs. Tests ran in isolated headless Unreal transient worlds with the
real mannequin/PHAT. The user's editor was closed before work and remains closed.
No Blueprint/map/PHAT/mesh assets were saved; all four before/after hashes match.
The live lab settings also match the read-only capture. No push was requested.

- Actual lab app versus packaged adapter: 14 cases / 405 frames, zero positional
  difference. Includes slashes, kick, sweep, both throws, twist variants, all four
  poses/Keep/disabled markers and a fixed world throw direction.
- Pinned V8 versus Node: 20 cases / 594 frames / 139,683 numbers, exact; includes six
  native-rig variants. Actual Unreal VM: 405 frames / 94,047 numbers, exact.
- Package/source/settings/asset audit: 101 checks pass. FinalNoAim manifest and
  baked clips match `Exports/Throws/FinalNoAim`, not another throw export.
- Existing manual-agent Blueprint compiles with all 10,552 original pin defaults
  and links preserved. Compilation used SkipSave; source bytes stay untouched.
- Native checks: 18 pass, 1 fails across the final 17-case combined run plus two
  explicitly airborne throw cases. Controls, saved tuning, world direction,
  substeps, preparation extension, kinematic/physical saved setup, pause/resume,
  NN handoff, paired/single hand pushes, Small Throw and release timing pass.
- Both airborne throws cover 121 frames including complete returns, restore the
  temporary limit override and preserve the captured joint profiles. Maximum
  physical position error: Big 0.656 cm, Small 0.988 cm; maximum leg-length error 0.127 cm.
  Native PHAT collider sheets were reviewed against planned poses.

**Fixture classification verified November 2:** this was the Space Gym airborne
controller placed at floor level, not a normal grounded throw or a jump that
later landed. All 121 frames have phase SPACE, grounded=false, zero gravity,
zero commanded translation and the same root position. Foot-floor contacts
already occur during PREPARING, before the throw. Lowering only the floor by
1.2 m gives identical canonical frames and no foot-floor contacts. The measured
4.273 cm discrepancy is calf_l to foot_l at 0.367 s. See
`Saved/Diagnostics/BodyflipPort20261102/throw-classification-check.json`.

**Unresolved:** `Prophecy.Bodyflip.PhysicalBigThrow`, the original fixture with
feet at floor level, intermittently fails its unchanged 3 cm leg-length gate. The
combined run measures 4.273 cm around 0.367 s, before release at 0.667 s. A left-foot
floor contact then reports a downward normal on the floor's bottom face; this
correlates with the transient stretch, but the collision cause is not yet proved.
Canonical motion and rig profiles match the passing focused run. The focused
full-return run passes at 0.365 cm; this does not erase the combined failure.
The separate AirBigThrow/AirSmallThrow fixtures put the floor 1.2 m lower (the lab
Space Gym height), keeping real collision and all original thresholds. The
original floor-contact tests remain intact. No ground-contact workaround or
threshold relaxation was applied. Follow this issue before claiming the entire
native physical suite is green; it does not invalidate the exact solver parity.

Evidence: `Saved/Diagnostics/BodyflipPort20261102/summary.json`,
`native-results.json`, `combined-final/Reports/index.json`,
`air-final/Reports/index.json`, per-agent JSON/contact sheets, `app-parity.json`,
`current-v8.json`, `package-audit.json` and `final-binaries.json`.
Full-return tests now fail immediately if their native world faults, rather than
continuing to compare a frozen last physical pose. The earlier failed runs are
retained for diagnosis. These are native automation/collider checks, not a claim
of an interactive test of the user's entire game map or a cooked shipping build.

Current Runtime.js: 998,973 bytes; SHA256
`432f52c2300aaa0980df058716b7327a3fb33e039803a760d4877688a4682441`.

## Historical package and verification notes

The entries below predate the November2 port and are retained as evidence.
Their pending-build/package status and old defaults are superseded above.

October31 context-refresh boundary: the standalone lab has newer, unfinished
direction-based aiming and cooperative-preparation experiments. They have NOT
been packaged or parity-tested in this runtime. The package below remains the
last packaged version, not the current lab source. See the
[lab handoff](../Labs/BodyflipLab/README.md#context-refresh-handoff---october-31).
Per-mode timeline persistence is UI-only and needs no native update. Flight and
recovery decoder sources have changed; runtime-only packaging rejects their old
asset fingerprints. Do not bypass this or assume a successful prior parity test
validates the newer code. No editor build/restart was performed for this handoff.

October31 current package:42modules/891446bytes; SHA256
5ed93ac7db5248d4c727e244e6304bbcfc0c34d874984c20ddf51b6d840c402f.
Airborne pelvis aim returns from Hit over Attack out; spine/shoulder offsets
retain follow-through. Before/at Hit and flipless motion are preserved. Native
slash V8 parity8frames/1723numbers exact. Lab-only no-op generation guards also
fixed marker-click freezes. No C++/Blueprint/editor changes. The separate
landing-to-NN issue remains. See the lab README for current scope/evidence.

Previous October31 package:42modules/890981bytes; SHA256
f15a76259e321254c5fabd66752eae0d417add02b944fdb05e4a3d4e219c44d3.
Includes accepted foot follow and balanced airborne contact-position aiming,
pelvis-local aim turn, independent shoulder steering and exact-integrator
refinement. Native V8 six cases48frames/10577numbers match Node exactly.
Header defaults remain source-only until a normal build; no editor/Blueprint
changes. Separate landing-to-NN wrist spike nearF199 remains unresolved in the
current scene; no speculative landing changes are packaged. Lab README has
current metrics and evidence. Older package hashes below are historical.

Default follow-up: core AimWeight and the typed Blueprint settings initializer now
default to1.0 (100%). Generated runtime refreshed. Header default is source-only
pending the next build; no editor rebuild/reload or existing Blueprint pin changes.
Current runtime882827bytes; SHA256
3e7e43b31452cc8dddd66ee795141ff103a6e9753ab6582d8c4631339603ddcf.

October31 physical aim follow-up (local after checkpoint09476308): prediction
now includes release carrier displacement/drift, uses neutral physical entry,
bounded iterative correction and the attacking shoulder in the contact chain.
Static/flipless attacks retain their exact approved path. Saved full-aim slash
hits within10.046cm of the12cm target centre; saved80% deliberately remains partial.
Runtime42modules/882829bytes, SHA256
c4294b7d578d4996ecf94504db3731b093e21b75377c2fa38fe8f1b8dc9433d7.
No C++/Blueprint/editor changes. See lab README for limits and verification.
Native V8 parity: six cases,48frames/10583numeric comparisons, zero difference.

October31 F145 release fix: floor projection of the captured leg now runs before
rebasing its world pose into source coordinates. Physical flight starts from that
captured articulation, retaining contact momentum/COM velocity and commanded
launch strength. Shared lab/runtime change; no C++/Blueprint/editor changes.
Package42modules/882017bytes; SHA256
25e7e0a15a71c0d334f1ad2ed2f5dbe15559ffaec789fb1170eac11d9d27a5d9.
364 release/origin checks,1126 leg-continuity,566 physical checks,14 strength
and five hand cases pass. Flipless Space gym19attacks/684samples remains exact.
Native V8 parity passes48frames/10583numeric comparisons exactly across kicks,
slashes, both throws, foot pushes and paired-hand pushes.
See the lab README for current-scene measurements and the pre-existing absolute
world-follow limitation; this fix adds no filter or new contact eligibility rule.

October31 follow-up: preserve planted-push ownership when another hand/foot/toe
contacts during LOAD/PUSH; retain collision response and release ownership once
lifted. Saved axis-only J2 now launches rather than switching to NN at ball_r
contact. Resolved COM velocity drives RISE/FALL status.24 focused checks and
five hand cases pass. Runtime42modules/881559bytes; SHA256
63b983582ff0c2a7943f0bda76435b6369b3b492c43d947a987ac13e0ddabcb6.
No C++/editor/Blueprint changes.

October31: predictable Jump% launch is shared by lab/native. Successful surface
pushes command COM launch energy, instead of taking whatever speed the visual
knee-extension curve delivered. Common100% reference height1.032640m; rebound
remains separate. An impulse at confirmed release preserves position, carries
the allowed tangential velocity and applies the requested skewed push speed.
Misses before push/zero% get no impulse. Feet/hands and spin/no-spin use the same
translation rule; non-spinning Space gym remains exact. Existing Blueprint Jump%
pin is unchanged. Package42modules/881111bytes, no C++/editor/Blueprint changes.
SHA256:fbbe07c333d10329fdddbe9eb0cda0d6bc61037bc5f311a2c50139393e29ff57.
14 strength cases and566 core flight checks pass; saved J2 now scales from~.83m
at70% to~2.16m at200% with the user's Rebound setting. See lab README for contract
and release/continuity receipts. Fresh native V8 parity passes48frames and10583
numeric comparisons exactly;19attack/684sample flipless Space gym preservation
also passes unchanged.

October31: active-spin sequences now share the lab's final COM/momentum balance,
including predicted aim before collision. Default momentum3D=true; false selects
commanded-axis balance in runtime settings. Existing no-spin attacks retain their
exact old motion/aim path. Runtime package42modules/879029bytes; actual app/native
adapter spinning-slash parity6frames passes. Core reaction cost is≈.7-1ms per60Hz
frame; target calibration remains a cached preparation task, not a per-frame
optimization. Aim is bounded and can miss physically incompatible directions.
No C++/Blueprint layout or editor rebuild in this turn; new option currently lives
in lab/runtime settings. See current lab README for metrics, scope and receipts.
Final native V8 parity:48frames/10583numeric comparisons, maximum difference0.
Runtime SHA256:cc28df8b099725f29536f0dbe8aba3b3493fc9125acbd3f7a7638c1d8823a21a.
Release-velocity fix: use instantaneous contact-side COM velocity instead of the
last240Hz tick's average. This restores the final push acceleration (saved J1
ballistic rise.482->.972m) without changing Jump% or the contact/angular solve.

October31: attack compensation now includes anatomical joint projection in
source/target/trial momentum measurements and in the smoothed/recovery output.
This removes the mismatch where spine rotation was discarded after calculating
the pelvis response. Both rig profiles and rigid/soft modes pass56cases with
no further anatomical correction. Runtime-only package39modules/855374bytes;
no C++/Blueprint/build or editor changes. Native V8 parity passes48frames/
10595numeric comparisons exactly across kick, slash, both throws, foot and hands.
Runtime SHA256:7418504d61cf95a447be612b91c49908397fbd8779b4748bcdfbea7a8e1331e7.
See the current lab README.

October31: Direct to Armed now shares live-harness angular-distance timing
across all19attacks, including charge-specific throws. Attack In remains the
minimum; Armed-to-Hit/Release remains native speed. Existing smooth interpolation
and separate aiming/flip controllers remain. Runtime-only JS package updated;
48frames/10595values exact in native V8 parity (kick, slash, both throws, foot,
hands). No C++/Blueprint/build changes. See the current lab README.

October31: removed the rejected Modified rotations experiment. Upper-body
attacks now fit arm animation keys to the rig before blending, fixing the
saved slash's F148/F155 hinge-projection snaps. Full JS package regenerated;
native-slash Node/V8 parity passes8frames/1729numeric values exactly. Both rig
profiles pass the arm interpolation checks and60native-profile aiming cases
pass. No C++/Blueprint changes or editor build; physical tracking was not rerun.

October30 spin correction: user rejected the full-tensor experiment's unwanted
twist during a pure front flip. Packaged JS now captures command vectors in
world space and scales speed by inertia about their combined axis. This is
axis-controlled rotation, not full articulated angular-momentum conservation.
The former pelvis-following twist axis is still removed. No C++ layout/build/
editor change is needed. See the Bodyflip Lab README and axis-native-parity
receipt for current checks; historical physical tracking tests below were not
rerun for this control change.

The native controller is opt-in; startup and Play preserve existing Blueprint wiring and agent tuning. The current private ORT/V8 build passes native NN continuation exactly. Four profiles /64 poses match the preserved PyTorch fixtures within9.65e-6. The saved4.3167-second scene now completes all260frames with real NN callbacks in62.737s, including31.083s NN work and111.3MiB sampled JS peak; this is preparation time, not game frame time.

The resumed13-test run passed11 checks: overlay ownership, V8 budget/recreation and cancellation/recreation, approved scene, trim extension, embedded parity, projectile geometry, fractional release, finite anchor carry, and the low-level finite-parent servo. The fixture creates the real separate manual PhysicalMesh and reuses the existing world/collision owner. The temporary-mesh nullable-owner and kinematic PHAT lookup corrections are built and verified by subsequent runs.

The integrated finite-parent diagnostic now passes at60/120/240/480Hz and both joint orders. The solver's instantaneous point-joint impulse matches the analytical Jacobian within5.4e-5kg cm/s. At60Hz the finite secant command is modified by that constraint, leaving.115cm anchor error; at120Hz it is.047cm. The active Bodyflip coordinator uses the lab's240Hz baseline plus angular subdivisions. Coarse cases check the measured constraint impulse and unconstrained finite endpoint;120Hz and finer retain the original.003rad/.05cm constrained endpoint limits. No joint is disabled and no saved tuning is changed.

The final release run passes all five tests: the complete kinematic/sim comparison, Big Throw, Small Throw, one-hand push and two-hand push. It captures actual Jolt poses and contact impulses. The base physical case has5.45cm maximum /0.231cm RMS body-position error and19.35deg maximum rotation error. The earlier24.35cm entry jump is corrected by feeding the held native pose into trajectory planning. Landing preserves the hand's existing world-space follow and return instead of replacing it with the shorter body blend. The common transition also restores velocity cancellation when bend feasibility fails. No tracking limit, motor cap or saved tuning was relaxed.

Native support IK now solves actual PHAT hinge axes/connectors before contact fitting.7,224 endpoint/hinge/anchor/continuity checks pass and ordinary lab profile outputs remain exact. When an elbow is effectively straight, its physical hinge supplies the otherwise ill-conditioned bend plane. This removes the spinning hand-release snap. Each hand's departure is a separate collision-history boundary, preventing recursive future reads when spin releases one hand early. The73-frame release-history regression has248 checks, including both boundaries and backward seeking.

Both physical palms register positive solved floor impulses within the complete interval0.416667–0.433333s, inside the freshly reported push window. This establishes contact during the same capture interval, not necessarily the same substep. Final position maxima/RMS in cm: base5.45/0.231, Big Throw8.09/0.599, Small Throw8.09/0.613, left hand6.18/0.318, both hands7.52/0.401. Maximum rotation errors stay below26.72deg. The one-hand case's largest leg segment-length discrepancy is2.954cm against the unchanged3cm limit: a narrow pass, not a claim of zero physical error. All five actual collider sheets were reviewed.

Carrier heading uses explicit commanded/landing metadata instead of the FBX root orientation. Start-yaw3180 checks, backward-landing817, focused57 checks and the actual native CarrierHeading test pass;16 old/new packets match exactly except heading. The throw audit samples the actual left throwing hand and normalizes float32 quaternions before angular comparison; release orientation passes its unchanged1e-5 tolerance. Optional traceSource packets expose source/projected poses. The transition entry has105 focused checks;39 general motion-blend checks pass. Three historical knee-test assertions about the old F59 pose/reversal fail identically before and after the transition fix; the other76 checks and all recorded metrics are identical. Do not report that historical fixture as a full pass.

The isolated host is reused between runs and shares project assets through junctions. Native reports live under Saved/Diagnostics/BodyflipPort20261030. Process exit0 does not establish a test pass: read the Automation report. The first resumed core run hit its480-second overall limit after a long editor startup; its successful NN/control results and overlay clock failure are preserved separately.

The current source embeds the canonical pure lab solver in an isolated V8
context, replacing the previously tested Windows Chakra host. It uses the same
pinned ClearScript native DLL as Foot IK, with a separate context, solver and
host callbacks; no native Foot IK controller state is shared. The common lab
Foot IK functions remain part of Bodyflip's packaged source. It does not run a
browser, Node process, local HTTP server, or a
second physics world during gameplay. The original equations for support
selection, hand/foot contact, body spin, attack compensation and predicted aiming
therefore have one maintained source. The generated runtime is accompanied by
source hashes in `Content/BodyflipLab/Receipt.json`.

The native package retains the licensed fdlibm/V8 sine/cosine compatibility shim
already used by Foot IK. Pinned V8 otherwise differed from Node by one ULP in a
few trig values, which the aiming Jacobian amplified into a sub-micrometre pose
difference. The shim matches the original Node oracle exactly in 1,284 math
samples and 1,721 sweep-frame values; the full 64-frame cohort is then bit-exact
without changing its comparison threshold. Browser/lab math is unchanged. The
shim's source/hash/license are in the receipt; the package skips it when
WebAssembly is unavailable, preserving historical Chakra diagnostics.

The compiled native profile integration supplies the actual agent's collider
geometry, mass, COM, inertia and joint frames/limits to those equations. The live
PHAT differs from the lab mannequin, so treating them as identical would give
incorrect spin inertia and physically unreachable poses. Physical agents reuse
their captured Jolt rig; kinematic agents are inspected through a temporary
non-simulating mesh. The user's PHAT and tuning remain unchanged. This path is
covered by the isolated full-agent physical tests described above.

## Build and validation — October 30

Disk space is about12.5GiB. The isolated binary snapshot is the successful normal dynamic-UBA/NoPCH build-entry-return.log (155.23s). The final native-release-final.log / Reports/release-final run passes5/5 and exits normally in190.47s, with3.17GB peak committed memory under an enforced4GiB cap. Final solver changes are in the packaged JS, using that same binary snapshot. The host shares project assets and does not copy PDBs. User editor/Play and Blueprint wiring remain unchanged; enable the controller explicitly through StartBodyflip. Automatic approval review rejected cache-only cleanup; no files were deleted by that attempt.

Final Runtime SHA256 is `caf24be9d5809cdba6fc0161e7439c46ba52f1b127e4b185a2e023a8e46e90a5`.
The final native-profile Node/V8 comparison covers kick, foot push and paired-hand
push:24 frames and5,216 numeric values, with zero difference. The hands case used
13.875 CPU seconds,18.422 wall seconds and278,220,800 bytes peak process commitment
in this diagnostic. This single run does not establish an aggregate speedup.
The final Automation report has five Success states and no errors. The base case
logs the deliberately rejected seek beyond recorded projectile history. The four
other cases log the attack self-collision owner's world/subsystem lifetime-ending
warning during teardown. Dense F20–27 hand sheets and later return poses were
reviewed alongside the complete-motion samples.
The final read-only receipt audit matches all86 hashes:38 source modules, authored
inputs, packaged attacks/assets/runtime, adapter, polyfills and trig shim.

## Public control

Typed-pin validation: normal `build-blueprint-options-retry.log` succeeds; the
isolated `Prophecy.Bodyflip.Controls.BlueprintOptions` test passes with no errors
or warnings. It checks reflected writable option fields, normal nodes without
JSON input pins, every attack enum, defaults, spin inheritance/zero and units.
An independent lab check recognizes all48 encoded settings and20 attack choices.
The normal build exposed one missing `UObject/Package.h` include in BombBake after
unity regrouping; that include was added without changing behavior. User assets,
wiring and sessions were preserved. New reflection loads on next project launch.

Storage follow-up: the user explicitly requested Recycle Bin cleanup. Eight
disposable cache/obsolete-engine/archive paths totaling181,474,003bytes (173MiB)
were recycled successfully; nothing was permanently deleted. Working host binaries,
packaging dependencies and validation evidence remain. The receipt is
`Saved/Diagnostics/BodyflipPort20261030/recycled-files.json`. Bin contents still
use disk space until emptied. This supersedes the earlier blocked cleanup status.

`UProphecyBodyflipLibrary` provides these Blueprint-callable operations:

- **Start Bodyflip** (`StartBodyflipWithOptions`) takes Agent and typed Settings.
  Split Settings or use its generated Make Struct node to expose sequence,
  locomotion, contact, buildup, spin and attack-blending controls. It uses the
  native NN and queues no automatic jump. The agent must already be registered
  in a game world and retains its existing Kinematic/Physical mode.
- `PauseBodyflip`, `SeekBodyflip`, and `StopBodyflip` control that agent only.
- `SetBodyflipTarget` accepts a target in Unreal world centimetres.
- **Queue Bodyflip Jump** (`QueueBodyflipJumpWithOptions`) has Agent, At Time,
  Jump Percent, Push With, Spin, Pose and Attack pins. Split the last three
  struct pins to expose their fields, or connect their Make Struct nodes.
  Push With offers foot, nearest hand, left hand, right hand and both hands.
  Attack is a dropdown containing all melee/sword attacks, Sweep Kick and both
  throws, with delay, blend-in/out, throw charge and throw speed multiplier.
  Pose offers None and the four existing placeholders with blend-in/hold/out.
  Spin exposes signed flip/twist degrees per second, the12 axes, delay,
  acceleration/deceleration and Instant Spin. Inherit flags keep previous
  commands; disable inheritance to apply a new speed, including zero to stop.
  At Time is absolute playback seconds, not a delay from the node call.
- `SetBodyflipPlatforms` accepts finite oriented boxes in Unreal world space and
  their full dimensions in centimetres. These are the surfaces queried by the
  controller. It does not silently discover or modify arbitrary level geometry.
- `GetBodyflipState` reports preparation/playback state, time, root, velocity,
  phase, errors and the original diagnostic frame.

Typed Blueprint settings use centimetres, seconds and degrees. Ratios remain
0..1 and explicitly named percentages use0..100 (Jump Percent allows up to400).
Legacy JSON nodes remain deprecated for existing wiring and C++ diagnostics;
normal Blueprint use needs no JSON. Internal JSON retains lab units: metres,
seconds, degrees per second, and Y-up coordinates. Orientation follows the mesh's authored frame at controller
start. The first solved root maps exactly onto the agent's initial root low point,
so Space mode's authored height does not move the native carrier upward on entry.
The two world-space setter functions perform this conversion for callers, including
requests made while the first frame is still being prepared.
`trimOut` limits initial preparation; without it, the initial horizon is three
seconds. Seeking past the prepared end continues the same solver state and keeps
its cached prefix. Target/platform/event edits rebuild through the current trim
edge, retaining the displayed time while preparing.

## Execution and ownership

The C++ planner runs expensive motion preparation on one serialized worker lane.
It stores exact 60 Hz output frames, while the canonical controller retains its
own internal integration rate. The game thread publishes those frames; it does
not run the body/contact solver. While a changed scene is preparing, the current
pose and root remain displayed, and only that controller's projectiles pause.
The current source queues seeks during regeneration instead of reading the old
frame cache. Failed generations retain their error until an explicit rebuild;
pending seeks do not turn those failures into successful playback. Native
failed-generation, queued-budget and expanded ownership checks pass.
Paused/preparing poses publish equal previous/current samples so the native
servo receives no stale feed-forward velocity. Returning from a pause resumes
the retained motion; stopping from pause hands back a resting pose.
The native NN graphs use their own recurrent state and do not mutate the live
locomotion manager during planning.

Authored attack clips load on demand. Their redundant axes are computed from the
same stored quaternions when first used. The V8 host uses a 384 MiB soft heap
budget, collecting garbage before rejecting retained excess. Its allocation
settings reserve 448 MiB for old space, 32 MiB for new space and at most 32 MiB
of array buffers. Reported peak heap is sampled at commands and host callbacks,
not an allocator-level peak. These limits do not describe Unreal's or ORT's
separate allocations. The previous Chakra three-second fixture used about
287 MiB; that is historical evidence, not a V8 measurement.

A budget or execution-deadline failure pauses that controller with an error.
The planner's 120-second budget starts when its worker acquires the serialized
planning lane; waiting behind another agent does not consume that budget.
Direct VM commands are
synchronous and caller-cancelled; there is no additional per-command time gate.
Native NN cancellation is checked between model stages and recurrent steps;
an in-flight ORT call must return first. A later rebuild replaces the interrupted
VM on the worker. Native V8 cancellation/recreation and heap-budget/recreation
fixtures pass in the isolated host.

The native-profile two-hand fixture still requires substantial planning work:
the standalone cohort measured 38.69 seconds of CPU and 365.70 MiB peak process
memory for that case, versus 1.17–5.56 CPU seconds for the other seven cases.
Wall times were distorted by host paging. These are preparation diagnostics,
not gameplay frame-time measurements. The final cohort below supersedes these
earlier preparation timings; they are retained as historical evidence.

After the accepted wrist calculation reuse, a single replay of those eight hand
frames remains bit-exact. Runtime hash `0af4a8b4…c2d14d` ran inside an enforced
384 MiB Windows process committed-memory limit, with 380.36 MiB peak commitment
and 384.46 MiB peak working set (which also counts mapped/shared pages). It used
40.42 CPU seconds and 136.66 wall seconds during paging; this does not establish
an aggregate speedup. The separate receipt is
`Saved/Diagnostics/BodyflipPort20261030/v8-parity/hand-profile/accepted-wrist-v8-receipt.json`.
The original 64-frame receipt is preserved.

The earlier accepted contact-calculation reuse was packaged in Runtime
`626c70e2219a62ae9fd3f82c6bcee397281e88f2aa7e1c1f1d5e82488d2bb2fc`.
A fresh capped V8 replay matches all eight complete hand frames / 1,740 numeric
values exactly against the preserved original oracle. Peak process commitment
was 365.14 MiB under the 384 MiB job limit; CPU time was 32.80 seconds and wall
time 109.61 seconds. This is a single preparation measurement during paging,
not a gameplay performance claim. Its receipt is `hand-profile/accepted-v8-receipt.json`.

The Bodyflip pose hook includes a pose from 1/30 second earlier for the normal
NN recurrence. Presentation remains 60 Hz. Root contact comes from the posed
body, so an upright locomotion capsule must not trigger an earlier airborne
landing. The manager integration owns the carrier/root handoff and publication.

Held and released throw objects use their exported mesh vertices, mass, centre
of mass and principal inertia. The projectile adapter owns only its objects.
It submits release timing and forces to the existing shared Jolt world. A
fractional release divides the current shared step at the release instant; it
does not advance Jolt independently. Seeking restores recorded owned projectile
states without stepping the shared world. A seek into an uncomputed or evicted
post-release frame is rejected before changing the character's displayed pose.
Scene edits invalidate that collision history. Unrelated world bodies and their
past collisions are never rewound.

Physical agents and projectiles require the project's normal shared Jolt setup:
initialize that world and enable its scene-collision owner. Supplying platform
boxes to Bodyflip defines motion/contact queries; it does not create duplicate
physical level geometry. The native integration fixture verifies that its real
UE floor has been imported into Jolt before testing body tracking.

## Packaging and verification

Run `Tools/Bodyflip/prepare-toolchain.ps1` to prepare the pinned build-time
esbuild 0.25.12 executable and standalone JSRT probe in `Saved/Diagnostics`.
Then run:

```
node Tools/Bodyflip/package-runtime.mjs
node Tools/Bodyflip/package-runtime.mjs --runtime-only
node Tools/Bodyflip/verify-embedded.mjs
node Tools/Bodyflip/verify-surface-projection.mjs
node Tools/Bodyflip/verify-memory-budget.mjs
```

`--runtime-only` retains all authored asset bytes and checks their receipt hashes,
attack catalog and decoder sources before rebuilding just the solver bundle.
It does not decode the clips. Full packages also record hashes of raw authored
inputs; a legacy receipt without those hashes is explicitly reported as such.
Use a full package after changing an authored input or its decoder.

The packager emits `Runtime.js`, `Assets.json`, `Projectiles.json`,
`AttackIndex.json`, individual `Attacks/*.json`, and `Receipt.json`.
The first contains the exact source modules transpiled to ES2017;
the others contain authored clips/physical geometry, not precomputed controller
trajectories. The native NN exporter separately supplies the seed banks and
seed/step ONNX graphs under `Content/BodyflipLab/NN`.

The historical standalone JSRT suite compares Node and system JSRT output over
mixed spin, reversal, kick and foot-push cases: 24 frames, maximum
position difference 1.17e-10 m and quaternion difference 5.55e-16. The foot-push
case uses a deterministic test NN callback, so this receipt alone does not
establish native NN or in-world physical parity.
The surface boundary regression compares the host to the app's surface-aware
target projection over 18 cases, including poses requiring 13 cm of clearance.
The historical Chakra memory check completed 181 frames and verified that a
reduced 96 MiB watermark interrupted and disposed cleanly. It does not validate
the replacement V8 wrapper's heap controls.

Native automation names:

- `Prophecy.Bodyflip.EmbeddedRuntimeParity`
- `Prophecy.Bodyflip.AsyncTrimExtension`
- `Prophecy.Bodyflip.V8.InterruptAndRecreate`
- `Prophecy.Bodyflip.V8.BudgetAndRecreate`
- `Prophecy.Bodyflip.Planner.QueueDoesNotSpendExecutionBudget`
- `Prophecy.Bodyflip.Controls.FailedGenerationRetainsError`
- `Prophecy.Bodyflip.Presentation.OverlayOwnership`
- `Prophecy.Bodyflip.NN.InitialAndContinuation`
- `Prophecy.Bodyflip.AgentKinematicAndSim`
- `Prophecy.Bodyflip.ApprovedScene`
- `Prophecy.Bodyflip.ProjectileGeometry`
- `Prophecy.Jolt.Bodyflip.FractionalRelease`

`ApprovedScene` runs the complete saved 4.3167-second scene with the native frozen
NN and writes every callback request/reply plus frame and heap diagnostics. Add
`-BodyflipTrace` to a bounded native diagnostic run to separate NN initialization
and inference time from script preparation. This instrumentation does not alter
the controller's 120-second execution deadline.

The native validation covers normal compilation, V8 lifecycle, queue/seek/owner
controls, native NN continuation, the complete approved scene, and all captured
PHAT bodies during kinematic/physical playback. Throw tests measure the actual
physical hand, held object and release boundary; the projectile-math tests alone
would not establish this. The current physical rerun is recorded above.

`verify-release-history.mjs` exercises separate release times for two hands
during spin, samples both boundaries at20-microsecond spacing, and reverses all
73 playback frames. Its deterministic NN stub isolates contact/history behavior;
native NN fidelity is established separately. Native collision ticks now retain
every hand's departure, so an early-released hand never reads an unfinished
future pose from the carrier while constructing its return.

Private retained layout and reflected API additions require a normal build.
Coordinate it with the concurrent Foot IK work, preserve the user's editor/Play
session, and follow ProjectJournal's save/restart procedure. Do not use Live
Coding for this port.
