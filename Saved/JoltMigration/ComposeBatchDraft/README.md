# Pure completed-pose batch draft

Source only, no active changes/build/Unreal launch. Root approved the staged design. No speed claim until
same-binary Normal-priority A/B runs pass correctness and measure it.

## Promotion and diagnostic control

Add the three new private files `ProphecyJoltPoseBatch.h/.cpp` and `ProphecyJoltPoseBatchTests.cpp` to the game
module. Apply the isolated Character, Coordinator and Profiling patch files to current source. The profiling
hunk is deliberately separate for its owner. `ReportScopeLabel.txt` supplies the matching report-description
change for the harness owner; no harness source is edited here.

Baseline hashes used for the Character/Coordinator hunks:

| File | SHA-256 |
| --- | --- |
| Private/ProphecyJoltCharacterComponent.cpp | `3A97F72E07B461C4F65714CEA87B94C7B101E632B6BD6BB8E285482A38E8B013` |
| Public/ProphecyJoltCharacterComponent.h | `17091AF429C0A3173FC9131500340EBD858125E87149A173C51BDAD373F9A57E` |
| Private/ProphecyJoltCharacterWorldSubsystem.cpp | `C6F26F2C32BE82D42C8F22BF553312E52E5938E8141A33F62807ACE6CE10816B` |

Batching is enabled for two or more registered exact native Character components.
`-ProphecyJoltSerialCompose` bypasses staging for same-binary A/B. Admission, one-character worlds, native
derived/custom component classes and generic noncharacter step clients retain the existing serial path.
The ordinary client interface and serial consume/callback order are unchanged.

## Data and lifetime contract

After the one shared native Step, the coordinator captures eligible characters from its existing unique
registration snapshot. On GT the helper validates that a completed next step is available, captures body
transforms into each state's reusable body scratch and records the exact component carrier. Immutable
prepared layout/local-pose views and distinct output buffers become plain-data jobs. Two inline arrays
hold up to128 job/packet records without custom heap allocation. The existing pair of completed-pose
buffer sets is reused; ParallelFor's internal task/event machinery remains its own bounded overhead.

Workers call only the existing const FPreparedLayout::Compose: all changing-input/output validation and
the complete 88 local/component/world outputs remain. They access no UObject, weak-object lookup,
native physics system, delegate or GT-only profiler. Layouts and input buffers are state-owned plain data
and cannot be mutated/deleted on GT until every job joins. The GT packet ready flag is installed after join;
read failures are also held for serial consumption rather than aborting unrelated earlier clients.

UE5.7 Async/ParallelFor.h:430–466 verifies the default path helps execute these jobs and then waits on its
finished signal. Only its explicit PumpRenderingThread flag can pump the render thread; this call uses None
and does not pump game-thread callbacks. ParallelFor returns after every item body completes.

The completed packet lives inside its original private binding state. Serial PublishCompletedPose first
runs the existing live validation, then accepts a packet only when agent/mesh/asset/AnimInstance/owner,
rig generation, registration, completed revision, completed world step, authored-publication serial and
every component-carrier scalar still match. No tolerance admits a changed carrier. Replacing or deleting
a binding deletes its old packet. A changed carrier or republished authored/finger/helper pose causes
normal current body read and composition using the packet's reusable output storage.

Every successful PublishAuthoredTargets advances the new serial, with overflow refused before native
packet commit. This detects multiple same-frame target publications and finger/ref-pose changes even
when the NN snapshot revision and GFrameCounter do not change. The input packet is therefore never
accepted merely because its layout and frame number still match.

A prepared failure is reported only when that unchanged character reaches its original serial consume
turn. If an earlier callback removes it, the coordinator skips it; if inputs changed, it is recomputed.
This preserves failure latch/order and the prior published pose. Before animation callbacks, the chosen
output arrays move into the same local Completed value used by the original publication, so deletion of
State cannot invalidate in-flight output. Existing final swap-back and all callback guards remain.

## Native pose mutation boundary

Current world APIs can change a rig's position/orientation only by Step. Point impulses and joint changes
affect velocity/activation/constraints, not the completed pose immediately. DestroyBody rejects individual
rig members; whole-rig destruction invalidates identity. An extra Step or world replacement is rejected by
the existing completed-step/lifetime guards. Consequently current step+rig identity protects captured
body transforms between joined staging and serial consumption.

Any future rig teleport/body-position mutation API MUST invalidate these packets (for example through a
native pose-mutation serial included in the key), or force serial composition for that operation. This draft
does not add a mutation API or claim readiness for one. Private layout/visual-offset edits similarly require
the already-required disable/rebind operation.

## Profiling

Rename the former completed_pose_total field to completed_pose_serial. New compose_batch_wall covers
the entire staging wall interval: GT capture/body reads, parallel composition and result installation.
Thus `completed_pose_serial + compose_batch_wall` covers the disjoint completed-pose stages. BodyRead
remains an existing total and is nested within either batch staging or serial fallback; do not add it again.
Compose records serial fallback only. Query/proxy/validation child timers and coordinator/Agent parent
timers must not be added as independent work. Batch wall time is not the sum of workers' CPU usage.

Existing processor provenance measures GT locations, not worker placements. No worker invokes the
GT-only instrumentation. The dedicated GT batch scope accurately records its blocking wall duration.

## Verification

New `Prophecy.Jolt.Pose.ParallelBatchMatchesSerialAndIsolatesErrors` uses100 independent 88-bone/22-body
inputs and outputs sharing one immutable layout. It compares every scalar of all three output arrays
against serial composition, verifies one invalid packet does not alter valid peers, then verifies the forced
single-thread worker helper produces the same outputs. No timing assertions.

These tests are uncompiled/unexecuted here. Root should run existing pose/lifecycle tests, this new test,
the same real-RHI character/static/ISM blood path, and the100-character full pipeline with and without
-ProphecyJoltSerialCompose. Callback invalidation needs a live integration check: an earlier character's
finalization callback republishing a later character's targets or moving its carrier must trigger fallback;
removing/replacing that later binding must skip the stale packet and preserve existing error handling.
The draft does not claim that callback integration scenario was executed by this agent.
