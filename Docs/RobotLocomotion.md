# Physical robot locomotion

## October 26 — storage cleanup

User requested robotics-port leftovers be moved to the Recycle Bin. The recent
robot-port and camera diagnostics occupy only22.3MiB and7.1MiB respectively;
the transfer folder is0.90GiB including preserved source, profiles and evidence.
No multi-GB port-specific dump was found. Recycled94 obsolete Live Coding files
from Binaries/Win64, totaling1,943,291,063bytes (1.94GB/1.81GiB): game patch groups
2–20 and editor patch groups1–5. Every selected group was older than its current
normal DLL; no tracked files or current patches were selected.

All94 Recycle Bin payload hashes match the pre-move inventory and all original
paths are absent. The12 current camera patch files remain, together with normal
binaries, incremental build caches, source/assets, model weights/handoffs,
training environments/data and all transfer/performance results. Nothing was
permanently deleted; the bin must be emptied to reclaim disk space. No editor or
build was running at cleanup, and none was launched or stopped. The camera's
normal-build-before-cold-launch requirement remains unchanged.

Audit, exact hashes, recycle script and verified receipt:
`Saved/Diagnostics/RoboticsCleanup20261026/`.

## October 26 — player camera transition loaded and verified

Switching NN to either robot selects the physical rig's mass-weighted center of
mass in X/Y, projected onto floor Z=0. The camera retains its spring attachment
height, arm length, rotation, collision behavior and independent Blueprint
TargetOffset. Get Up to Clanker does not restart camera blending. Returning to NN
selects the normal root target again.

`Set Locomotion Camera Blend` takes Agent (Self), Blend In (default0.4), and
Blend Out (default1). It can be called before switching or from `Locomotion Type
Changed`. Durations use60 unpaused game ticks per authored second, smoothstep,
and zero for an immediate transition. Mid-blend duration changes start from the
current offset. Reapplying the same settings or editing only the inactive
direction does not restart the blend. The switch captures the current pivot before root/mesh handoff; its
first PostPhysics update also compensates late root movement. Existing attack
offsets are transferred into the new blend, not stacked as separate fades.

The existing player camera component owns the follow. New sidecar maps avoid
changing retained native layouts. Only a possessed robot reads the15 physical
body centers/masses, after physics; no floor traces, extra inference, NPC camera
work or idle-NN camera-follow tick. Unpossession/teardown restores the independent
offset. Ordinary attack/defense camera behavior resumes after the return.

Implementation: `ProphecyAttackCamera.cpp`, switch hooks in
`ProphecyRobotLocomotion.cpp`, node in `ProphecyLocomotionTypeLibrary.h`.
Validation tools: `Tools/Robotics/InstallLocomotionCamera.py`,
`Prophecy.Camera.LocomotionBlend`, existing attack/COM camera tests and the
extended `Prophecy.Robotics.AgentSwitch` real-rig check. Receipts under
`Saved/Diagnostics/LocomotionCamera20261026/`.

Loaded in interactive TestNN PID27348 without restarting. Initial incremental
Live Coding compiled16 affected units (882.69s under low memory); the final
same-settings safeguard compiled only1 unit (145.19s). Reload completed13:45:04UTC.
Final four tests pass: LocomotionBlend, AttackOffsetFade, COMAndPlayerRig and
AgentSwitch. They cover tick-count timing, duplicate/non-game ticks, late root
translation/yaw, interrupted returns, duration changes, zero duration, independent
offset preservation and retirement; the real-rig handoff test checks actual
mass-weighted COM, Get Up↔Clanker continuity, both NN ownership modes and return
to the ordinary camera. No user Play was started; transient test worlds were
destroyed. No robot policy/contact retuning or broad100-case rerun was needed.

Saved the dirty user PoseAgent before reflection reload, with previous disk bytes
preserved. Final full Blueprint graph equals the pre-load graph; LiveAgentTypes
status3/native0/pins0. The saved BP and TestNN hashes still match the preservation
receipt. New node reflection reports Self,0.4,1.0. Map stays open/outside Play.
**Normal DLLs predate this camera addition: minimal normal build before any cold
editor launch or packaging.**

## October 26 — contact correction installed; production Get Up and walk checks pass

The user authorized installing the per-point correction for both robot modes.
The cumulative Jolt dependency patch now adds `mEnableSpeculativeContacts`,
default true. The shared robot callback opts out; ordinary pairs keep defaults.
The first production test exposed another integration omission: robot admission
did not install the callback unless hits/oil happened to enable a listener, and
the scoped protection listener bypassed it. `ScopedContacts::Refresh` now counts
robot ownership, admission refreshes it, and the scoped listener also applies
robot rules before its existing protection/oil/hit handling. Rig destruction
removes ownership and refreshes through existing body cleanup. No new polling,
timer, inference or skeleton work was introduced.

Normal Development Jolt/UE builds passed. The actual production owner, packaged
rig and NNE inference now pass **100/100 saved Get Up starts and16/16 five-second
walks**, including **15/15 native-successful walking controls**. Six focused
automation tests pass: ContactTransfer, AgentSwitch, ContactSettings penetration
slop/speculative distance, ScopedDefense and SwordNoReaction. The contact test
uses two60Hz game updates/four collision substeps per30Hz policy tick, original
first-terminal Get Up rules, and unchanged walking thresholds. It changes no
user world. Reproducer/preparation: `PrepareContactCheck.py`,
`ProphecyRobotContactTests.inl`; receipts under
`Saved/Diagnostics/RobotLocomotion20261026/contact-final/`.

The initial installed run failed99/100 Get Ups and10/15 native walking transfers;
kept under `contact-installed/` and `contact-game-cadence/`. Same-action first-step
probes narrowed this to the absent contact callback; changing update grouping or
world-basis rotation did not explain it. The rotated standalone control passes
16/16 Jolt and15/16 MuJoCo. No failure assertions were removed or relaxed.

Dirty PoseAgent BP and TestNN were saved before the necessary clean restart;
`contact-preservation/receipt.json` records hashes, still matching after tests.
Interactive TestNN PID27348 is open. Remote reflection confirms all five nodes,
three enum values and healthy LiveAgentTypes status3/native0/pins0/wiring
preserved. A brief owned12-frame Play session initialized the three placed user
BP agents and ended cleanly (`contact-play.json`); normal editor remains open.
Its loaded native DLL path and both staged copies match the new build manifest.
No user wiring/tuning, checkpoint, PHAT or map-content edits. Shipping uses the
same maintained source patch but its dependency was not built/tested this turn.
Running and long Get Up holds are not covered by the passing comparison.

## Earlier isolated investigation and provenance

**Transfer investigation follow-up:** a missed contact rule is now demonstrated
in isolation. The intended earlier robot callback suppressed an entire separated contact
manifold; the earlier successful RunLR experiment suppressed separated points
inside mixed touching/separated manifolds too. A tilted foot can otherwise
receive support/friction through corners that are still above the ground.
From identical saved MuJoCo walking starts, the old rule fails case1 at policy
tick43 (1.433s). Point contact completes its five-second walk, minimum pelvis
71.722cm and travel621.772cm. The comparison uses the same isolated executable
and DLL with only the contact switch changed. Its default trajectories match
the installed-DLL fixture **exactly** for both original walking cases.

Fixed broader check: two identical-pose seeds x eight directions x five seconds.
Success requires pelvis staying above60cm and more than100cm travel along the
command. MuJoCo succeeds15/16; old contact transfers14/15 of those successes;
point contact transfers15/15, with no regression among native successes. The
one MuJoCo failure is retained, not counted as a transfer failure. This is a
walking-only isolated result, not a claim of complete gameplay integration.
No new weights, PHAT tuning, editor action, production source change or DLL
installation occurred in this investigation.

Same-state one-240Hz-step checks localize the first discrepancy to contacts:
maximum angular-velocity error1.192rad/s with contacts versus0.0295 without;
the right foot is worst. Drag removal and the old motor-saturation diagnostic
do not repair the walking failure. The actionable follow-up is the reviewed
per-point opt-out for both robot modes, retaining the ordinary-object default.
The previous Clanker-only recommendation was superseded by the paired Get Up
regression check below. It has since been installed through a normal native
build/restart, including the listener-ownership fixes described above.

**Get Up contact comparison:** replayed the accepted100 saved starts with their
original poses, COM velocities, phase, frozen weights, spherical32 profile and
first-terminal success/failure rules. Both old manifold and new point filtering
pass100/100 with original PyTorch inference; the old-rule trajectories reproduce
all100 historical actual-Unreal trajectories exactly (maximum error0). Repeated
the full comparison using the packaged `getup_161960.onnx`: both rules again
pass100/100, median success24 policy ticks for each. Each of four25-case cohorts
(front/back, ordinary/perturbed+) passes in every variant. All99 saved native
MuJoCo successes transfer; the one native failure also succeeds under both rules.
400 isolated rollouts total; no observed success regression and no evidence
that Get Up needs a different contact rule. This does not establish improved
Get Up success or validate gameplay installation, obstacles or long standing
holds. Recommendation: use the same per-point rule for Get Up and Clanker.
No production code, DLL, weights, editor state or user assets changed here.
Receipts: `getup-torch.json`, `getup-onnx.json` and their `-summary.json` files in
the audit directory below. Reproducer: `Tools/Robotics/AuditGetUpContacts.py`.

Evidence: `Saved/Diagnostics/RobotLocomotion20261026/transfer-audit/`
(`directions-summary.json`, `directions.json`, `baseline.json`,
`same_dll_manifold.json`, `point_contacts.json`, `one-step.json`, `provenance.json`).
Reproducers: `Tools/Robotics/BuildAuditFixture.py`, `AuditTransfer.py`,
`AuditDirections.py`, `AuditStep.py`, `CompareNative.py`.
`AuditSequence.py` additionally retained the old fixed ten-second Get Up hold
experiment: both standalone baselines recover early, but continue issuing Get Up
long after standing and can fall again before the fixed Clanker switch. Its
mixed end results do not validate a full handoff or decide which contact rule
Get Up should use. The paired first-terminal check above answers the latter
regression question. The hold test is retained in `sequence.json`/NPZ, not
silently counted as a passing regression check. The previously passing actual
Unreal AgentSwitch tests remain the evidence for ownership/pose handoffs.

Requested Blueprint modes: `NN`, `Get Up`, `Clanker`. Native implementation and
owned headless checks are present. The original fixed Get Up/idle/walk/run
sequence below is historical; the new first-terminal Get Up and frozen-start
walking checks above validate the corrected production paths, not running.
No user Blueprint wiring or asset tuning has been changed. Interactive Unreal
was already closed at task entry. Final normal incremental build succeeded;
extended agent handoff checks pass. Headless reflection verification also passed:
all five functions, enum values, user BP loaded; LiveAgentTypes status3,
native_properties0,pin_types0,wiring_preserved1. No asset saves or user Play.
Earlier interactive TestNN PID22068 opened after the user dismissed the startup
warning. Remote `VerifyEditor.py` confirmed `/Game/testNN.testNN`, all five nodes,
three enum values, and the user BP. LiveAgentTypes remains status3,
native_properties0,pin_types0,wiring_preserved1. No assets saved or Play started.

The user selected the accepted Get Up **spherical32** angular-limit profile for
both robots. Both use one packaged `Content/locomotion/NN/robots/rig.json` and one
native spherical-limit implementation. Stock PHAT swing/twist fields cannot
represent an exact total-angle spherical limit, so the official PHAT asset has
not been overwritten with an approximation. The packaged profile is frozen from
the accepted PHAT-derived training rig; it is not a live PHAT reader.

## Controllers and runtime

- Get Up: accepted pelvismax final161960 from
  `Exports/MimicKitEquipment/Recovery_Pelvismax161960_Unreal_20261026`.
- Clanker: locomotion214358 /7,006,126,080 samples from
  `Saved/MimicKitLocomotion/unreal-handoff-20261026`.
- Native NNE ORT CPU actor and phase inference, cached models, no Python or
  training dependency during gameplay. Deterministic 154-float observation,
  34 angular-velocity commands and two phase values. Observation normalization,
  output normalization and velocity caps are embedded in ONNX.
- Shared trained15-body/14-joint compound rig,23 primitives,34 motor axes. No
  NN pose-following body drives while a robot owns motion. Joint motors retain
  trained finite torque caps. Policy30Hz, physics240Hz on the game's fixed clock.
  Limits blend in over24 unpaused game ticks (0.4 authored seconds).
- Clanker consumes the existing agent locomotion command: idle/walk/run and
  world movement direction. Get Up is the separate recovery controller; it
  remains selected until explicitly changed.
- Requires a registered NN agent, supported unit-scale mannequin, and an
  initialized Jolt world with the intended scene collision.

Both checkpoints use pelvis COM linear velocity. The Clanker handoff prose
incorrectly says body-origin velocity. Its frozen Newton root joint_qd and
`body_velocity.py` use COM; native encoder was corrected against that source.
The frozen XML, limits, physics, native engine and char observation source are
byte-identical between the two handoffs. Both actors retain their original weights.

## Blueprint API

`Set Locomotion Type` defaults Agent to Self. A request during Actor Tick is
queued to the next safe pre-actor physics admission window. The
`Locomotion Type Changed` event receives Previous Type and New Type after a
successful switch. Repeating the current type is a no-op; a newer request
cancels an older queued request.

`Set Locomotion Switch Upper Blend` and `Set Locomotion Switch Lower Blend`
configure independent per-agent returns to NN, including from that event.
The combined `Set Locomotion Switch Blend` is also available. Controls do not
change attack tuning. Defaults use the current Blueprint's lower duration1.5s
and accepted SlashLD upper profile: duration0.39s,inertia0.18,easing0,alpha hold
0.17,takeover coefficient1. The lower hold defaults0. Other attack families
have their own different profiles; these are explicit initial defaults.

NN entry captures current physical body velocities when simulated, or infers
them from the existing pose history when kinematic. Robot exit seeds both
previous and current lower/upper NN states from physical motion. Root planar
velocity is total COM velocity; yaw rate is total angular momentum about COM
divided by yaw inertia. The previous simulation mode is restored on return.
Physical NN return transfers the captured compound-body motion to each new
PHAT body's COM. Explicit simulation-mode/backend changes retire robot ownership
through the same return. Entry closes all angular bounds, including hinge locked
axes, over24 ticks; position joints remain intact. After that, motor packets only
publish on30Hz policy steps. No feature inference/history copying when inactive.

## Verification and provenance

Preparation scripts: `Tools/Robotics/PreparePolicies.py`, `PrepareRig.py`,
`PrepareObservationCheck.py`. No original checkpoint or training source edited.

Evidence is under `Saved/Diagnostics/RobotLocomotion20261026/`:

- Clanker ONNX/PyTorch:768 observations, max action error1.145e-5,phase1.272e-5.
- Actual Unreal NNE:32 Get Up +32 Clanker vectors; max errors1.008e-5 and9.537e-6.
- Observation contract:10 independently encoded recorded states; max error9.537e-7.
- Native physical check: two frozen fallen starts recovered, pelvis89.984
  and88.382cm; subsequent four-second Clanker idle remained upright, minimum
  pelvis81.287 and87.456cm after the COM correction.
- Actual-agent NN/Get Up/Clanker/NN transition test passes, including real shared
  physics steps and queued Tick requests. Kinematic entry error0cm/0.000003deg;
  return and first waiting subframe0.000003cm/0.000016deg. Physical NN entry
  0cm/0.000002deg; return0.000012cm/0.000021deg. Current COM/angular velocity
  inheritance and ordinary simulation-mode exit pass. Fixed the empty inherited
  Mesh skeleton lookup and stale presentation alpha without erasing physical
  velocity history. Final receipt: `agent-switch-final.log`.
- Reflection receipt: `editor-reflection.json` now records interactive TestNN;
  `reflection.log` records the earlier owned headless Entry verification.
- Movement test: first direction walks with minimum pelvis83.102cm, then falls
  after run starts (policy tick618, run starts570). Second direction falls during
  walking at464, before run. Failed assertions remain visible, not weakened.
- Original CPU MuJoCo control on the same two initial states, models, commands
  and phase feedback: both walk upright (min74.958/71.763cm), then fall after run
  at614/593. This identifies a checkpoint/transition limitation in running AND
  an additional Jolt transfer limitation in the second walking case. It does not
  justify claiming all failures originate in the weights. Reproducer:
  `Tools/Robotics/CompareNative.py` using Saved/Robotics/env Python, one CPU thread.
  Receipt: `native-mujoco-control.json`; no training/GPU workload or retuning.

The older100/100 Get Up test used actual Unreal/Jolt with Python inference.
The old RunLR16/16 test used an isolated modified-contact DLL and displayed
recordings in Unreal. Neither automatically validates this new Clanker checkpoint
or the new native agent handoff. See `Docs/MimicKitTransfer.md` for that evidence.
