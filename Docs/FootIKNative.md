# Foot IK native integration

## Current state — October 30

The accepted lab and setup were pushed as `76614437`. The saved setup is
`Labs/FootIKLab/approved/2026-10-30/`. The native integration is built and the
focused controller, handoff and cold Blueprint checks pass. No Blueprint wiring,
maps, actor tuning or user Play session were changed. The realtime-deadline
limitation below remains; this is not unconditional live-motion parity.

Build35 succeeds with normal dynamic UBA/NoPCH. Actual Unreal evidence:

- Moving/turning/reverse/stop/re-enable GameLifecycle passes twice after the
  held-command fix (final-native-20/21). Directional speed caps evolving during
  one held turn no longer repeatedly cancel its forecast; actual input, facing,
  gait and tuning changes still invalidate it. The separate HeldCommand test passes.
- Real root-ramp locomotion passes, including391 joined frames/155 material
  tread contacts in the retained ramp receipt and a later final-native-20 rerun.
- TerrainExitGame passes in final-native-23:83.69cm corrected history pair,
  **zero** first-publication predecessor error, ten fresh policy publications,
  one exit and retirement of the0.10-second local return. The compact NN state
  cannot retain every interpolated joint transform, so the exact full accepted
  pose also supplies the first new publication's predecessor. Later samples are
  ordinary NN output; no special NN input or root change is introduced.
- The exit test now requires an actual corrected episode rather than a nonzero
  correction at the exit itself. Canonical whole-shoe clearance can occur after
  influence has faded to zero. Exact predecessor, fresh inference, root continuity
  and return-retirement gates remain unchanged. Per-tick diagnostics are retained.
- Rotated authored-mesh history, independent pending-publication carriers,
  surface lifecycle/re-enable, collision coverage, live Jolt target/feedback
  identity and elevated/sliding Bodyflip handoff pass. Handoff/history rerun on Build35.
- Lower-only predictor:222 actual-engine frames /26,466 values exactly match
  the full graph's authoritative lower/root/pin outputs. Inference measured
 4,571->2,028ms; full reference and slide graphs remain unchanged.

**Realtime limit:** laptop memory/CPU pressure can still outlast the1.2-second
stair forecast. The current owner then displays current raw NN, not an expired
pose. A retained trace contains a correction interruption during such a gap;
passing lifecycle/solver tests does not establish uninterrupted terrain motion
under load. Surface slide entry also retains a substantial synchronous cost.
No forecast horizon or contact gate was shortened to improve timing. Broader
live acceptance must include visual motion and deadline checks on the intended
game workload; arbitrary mesh collision is also outside the adapter below.

Discarded initial-planner work is omitted with4,923 complete frames/43 checkpoints
exact; paired CPU1,141->797ms. Private graph source buffers and the unused
lower-only Step graph are released. Native shoe-corner construction preserves
8,192 complete shoes plus12 signed-zero/extreme cases exactly, with paired
function timing394->76ms. The full embedded solver subsequently passes all48
cases/26,296 frames with identical position/quaternion components and scalar
values (`native-corners-complete.json`); this microbenchmark is not an app speedup.

The final Build35 cold editor check passes: existing Blueprint status3,
native_properties0/pin_types0,60 actual Play ticks,25 NN targets and the public
disable-node call. BP/map hashes remain unchanged. The owned editor was closed;
the unrelated Main Menu editor was not touched. Some unrelated map actors
reported unsupported MACD admission; those actors are not validated by this check.

Fidelity and optimization evidence:

- Host-only dependency caches:20,121 complete frames /10,400 joint comparisons
  exact; sixteen-case CPU total121.80->90.56s (26% less).
- Embedded solver:48 cases /26,296 full frames and1,024 NN windows exact.
- Unreal NN backend:26 fixtures /1,876 poses, maximum float32 discrepancy
 0.000213831663 within0.0003. This comparison is not bitwise NN parity.
- Fresh coupled NN oracles:3,214 frames retain all semantic/contact/slide
  decisions, with continuous backend differences up to5.2mm /4.19 degrees.
- Exact floor/reach/ankle batches:1,928 complete frames/eight checkpoints;
  ankle search additionally covers2,402 individual searches. Warmed CPU
 570.3->500.0ms beyond the floor/reach-cache baseline (12.3% less).

These timings describe their measured workloads, not a universal frame-rate
multiplier. Tests reuse one owned headless host, one-thread private ORT, and
read-only project assets. Retained temporary caches are listed in
`Saved/Diagnostics/FootIKPort20261030/cleanup-pending.json`; their deletion was
blocked by automatic approval review. No workaround deletion was attempted.

## Controls and ownership

`UProphecyFootIKLiveLibrary` exposes the gameplay controls:

- **Set Foot IK Enabled** turns the private terrain layer on or off for a
  registered agent. Off cancels pending work and removes its targets, history,
  callbacks and active owner. Configuration is retained.
- **Configure Live Foot IK** accepts the lab's settings object. Changing it
  starts a fresh epoch from actual game history; a previous worker cannot
  publish into the new epoch.
- **Get Live Foot IK State** reports preparation, accepted frame, solver cost,
  diagnostic data and explicit unsupported-configuration errors.

Horizontal terrain retains the game NN stream and root mover. While enabled,
Foot IK selects the lab's Run181751 policy at the controller's current speed,
including walking. The existing policy blend handles entry and exit; no actor
tuning is overwritten. Forecasting waits until the published Walk contribution
has reached zero, then captures a fresh history pair. This prevents the retired
Walk policy from driving the agent while Run predicts its feet. A private
matching NN forecasts from the actual raw previous/current poses and the
controller's ten root samples, including all future headings. The accepted
terrain targets are joined onto the actual current body motion. The upper-body
policy remains authoritative; the terrain layer changes pelvis translation and
legs. Both whole-pose and single-body physical-target readers see the same final
target. Existing lower physical feedback uses this corrected target.

Incline/slide mode uses a causal owner: root integration, feet, support receipts
and recurrent NN advance together at120Hz, publishing one result per60Hz
unpaused authored game tick. It starts from the game's actual history, not a
canned warmup or a recorded course. The existing controller still supplies its
command velocity and future headings. Disabling reads a clean locomotion history
pair, separately from the visible sliding physical target. During a slide this
uses the canonical paused-policy resume rule. Higher-level full-body actions
retain priority. Actual surface and horizontal controller lifecycles pass within the scope above.
Bodyflip admission distinguishes a diagnostic Foot IK course from live terrain.
Successful admission releases live terrain before publishing the action; a
rejected action leaves the terrain owner intact. Elevated and sliding handoffs
pass dedicated actual-controller tests.

Reference-course playback is separately named under **Foot IK | Diagnostics**
in `UProphecyFootIKLibrary`. Its Play/Configure/Pause/Seek/Platforms/State nodes
exist for fidelity and physics tests. They are not the gameplay enable node.

## Collision and coordinates

The native boundary uses Unreal world centimetres and the agent's authored mesh
frame. The solver uses metres, Y up. Bone-axis conversion is centralized and
round-trip tested. Root heading is a controller heading; the virtual root bone's
orientation is not substituted for it. Published prior/current history is30Hz;
the final terrain presentation is60Hz without a second interpolation pass.

The current collision adapter captures actual finite box faces, including
oriented boxes and convex hulls proven to be exact boxes. It does not substitute
an AABB for a wedge or arbitrary mesh. Unsupported geometry is reported.
Horizontal stair placement and the incline/slide owner use different geometry
interfaces. Explicit incline configuration remains necessary; classifying any
vertical collider face as a wall would incorrectly treat staircase risers as
wall locomotion. Root-ramp versus foot-tread collision separation uses component
tags: `FootIKRoot` excludes a navigation ramp from foot contact; `FootIKFeet`
includes query-only treads even when they ignore the capsule's collision channel.
Treads retain actual yawed rectangles. Timed root samples preserve route order,
including return to the same horizontal point at another height. The carrier
follows actual capsule support while the NN retains its virtual flat root and
local gait. Disabling rebases only its world origin, not the already elevated
displayed pose. Real-controller ramp and action-handoff tests pass.

## Shared implementation and runtime

`Tools/FootIK/package-runtime.mjs` packages the canonical modules into
`Content/FootIKLab/Runtime.js` and records source/host-seam hashes. The default
browser paths and Bodyflip's shared `createFeet` API retain their behavior.
Optional native batches use the same candidate order, strict floating-point
operation order, joint limits and contact geometry. Unsupported custom geometry
falls back to the original calculation; it is not approximated.

The embedded engine is the official ClearScript V8 native Windows DLL7.5.1.1,
used through its native ABI without CLR, browser, Node process or HTTP server.
A small matching-math WebAssembly module preserves the canonical V8 version's
transcendental results. A one-ULP shoe tie can otherwise change the selected
contact and subsequent NN history. All vendor receipts and licenses are staged.

The frozen Run181751 and Upper82500 ONNX graphs use private ORT sessions with
one intra/inter-op thread, sequential execution and thread spinning disabled.
Walk uses Run at the appropriate speed. Preparation reuses sessions for the same
direction while clearing recurrence and cancellation state; only one direction's
graphs are retained per stream. Game-wide inference settings are unchanged.
Cold sessions and optional V8 initialization use one sleeping1MB preparation
worker. No gait is advanced during warming; activation uses the latest measured
pair. Pending jobs are cancelable; completed sessions/heaps retire off the game
thread. The async preparation and cancellation lifecycle tests pass.
The live stair owner retains displayed120Hz history until the worker acknowledges
it, rather than expiring unconsumed samples after one second. A10-second native
backlog cap uses an explicit contiguous actual-history checkpoint. The worker
reconstructs its retained0.75-second boundary from actual raw30Hz poses and root
headings, including material contacts; it never fills a missing NN history row
from an old prediction. Ordinary gaps still fail. Node source and packaged
protocol tests cover delayed/capped histories, a nonzero initial epoch, preserved
stair contacts and192 fresh frames across stop/reverse/turn commands. The
corresponding native lifecycle passes in `Reports/final-native-16`. Initial
preparation remains reported until the first actual pose pair is submitted.
The native owner also warms the stair planner and publication V8
contexts on enable, before sampling that pair. Cold compilation therefore
cannot spend its1.23-second forecast lifetime. Ordinary NN/root movement stays
active during preparation. An explicit diagnostic snapshot now separates
initialization, forecast, planner and export costs and reports the exact reason
a candidate did not publish. Under memory/CPU pressure it can fall back to the
current raw NN pose; a result whose horizon has expired is never replayed.
Actual-history dispatch now copies immutable string references on the game
thread and assembles compact JSON on the worker. Only the last acknowledged
60Hz pair and every newer120Hz frame are resent; explicit capped checkpoints
remain complete. A990-frame paired test preserves all values and same-tick
contact replacements exactly. Idle solver/publication heaps retire through the
shared background queue rather than releasing their final references on GT.
Build15 also removes the worker's redundant DOM round trip: trusted serialized
source/history fragments enter the envelope unchanged, and `liveFrameTexts`
exports already serialized candidate frames. The old object-array operation
remains available. Source-envelope and packaged tests preserve numeric values,
signed zero, escaped text and120 exported frames; the separate export test
matches284 frames across20 range queries. Detailed NN/forecast substage timers
are diagnostic only; subsequent native timing is recorded in the reports above.
The live stair planner now decodes each prospective NN course once, reusing
only that immutable carrier across its complete boundary passes. Mutable knee,
contact and trajectory work remains independent. Its paired regression matches
3,232 complete frames,742 pin frames and16 complete checkpoints across flat,
stairs, descent and uneven terrain, including delayed actual-history recovery.
Finite-tread queries reject non-overlap before clipping and share identical
basis transforms only within one query;3,840 exact queries plus482 complete
frames/190 pin frames and two checkpoints pass. The packaged delayed-history
and frame-transport tests pass again. These changes leave lab defaults, time
windows and publication gates unchanged. Actual live timing, including late
plans under laptop memory pressure, is recorded separately from CPU microbenchmarks.
The configured Run checkpoint hash is validated rather than silently replacing
an unknown model. Surface upper-body export currently supports unarmed neutral
gaze; incompatible commands are reported rather than ignored.

## Evidence

Evidence is in `Saved/Diagnostics/FootIKPort20261030/`; reproducible compact inputs
are in `Tools/FootIK/parity-fixtures/`.

- `native-corners-complete.json`: latest48-case/26,296-frame exact packaged solver
  proof, including shoe corners and the three native solver batches.
- `Reports/final-native-23/`: Build35 actual terrain exit, history and Bodyflip
  priority checks. `editor-check.json`: final cold Blueprint/Play check.
- `Reports/final-native-20/` and `final-native-21/`: held-command controller
  lifecycle; latter is a second passing run. Historical terrain-exit failures
  there are superseded by the Build35 full-predecessor preservation.
- `Reports/NN/`: actual Unreal26-fixture NN pass, TestExit0. Warnings concern
  junction-path asset capitalization, not numerical comparisons.
- `native-nn-closed-loop-diagnostic.json`: produced by the coupled test; completion
  alone is not a fidelity pass. Inspect poses, root, contacts and mode transitions.
- `coupled-current/`: current canonical JS+Torch oracles with hashed actual
  request/reply pairs, separately generated from the 48 fixed-reply solver tests.
  Historical wall replies no longer answered the current forecast at one late
  call; independent Torch reproduced native output, identifying an outdated
  oracle pairing. Comparing all six retained Unreal captures with the fresh
  oracles gives identical contact/state/mode decisions over 3,214 frames.
  Continuous differences remain: up to 22 micrometres for recorded-source wall
  poses, about 5mm root drift with native source initialization, and 5.16mm arm
  drift and4.181 degrees joint-orientation difference in the accepted slide.
  This is not bit-identical NN output. The fresh actual Unreal rerun passed in
  `Reports/final-native-2`; see [NN evidence and reproduction](../Tools/FootIK/NATIVE_NN.md#current-coupled-oracle).
- Native controller, root bridge, cancellation/bounded extension, reference-agent
  publication and Jolt tracking have passing reports. Current build and final
  cold Blueprint status are recorded at the top of this document.

Slide-entry search still has a substantial synchronous cost. Moving a complete
calculation to native code is lossless, but does not itself establish a realtime
budget. Performance reports must distinguish warm solver CPU, entry worst case,
NN initialization and wall-clock paging on the busy laptop.

Use a normal build/restart under the journal's workflow, not Live Coding for this
retained state. The owned automation host disables Fab and Python startup for its
unattended tests; user editor preferences and project assets are unchanged.
