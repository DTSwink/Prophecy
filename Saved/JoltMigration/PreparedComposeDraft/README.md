# Prepared completed-pose composition draft

Source only. No active files changed, builds or Unreal launches. The original `ComposeCompletedPose`
implementation remains byte-for-byte unchanged and is the independent oracle for the new path.

## Promotion

- Replace `Source/GameAnimationSample3/Public/ProphecyJoltPose.h` with the draft header.
- Replace `Source/GameAnimationSample3/Private/ProphecyJoltPose.cpp` with the draft implementation.
- Add `ProphecyJoltPreparedPoseTests.cpp` to that same active Private directory.
- Apply `CharacterPreparedCompose.apply-patch.txt` to the current Character source. It changes only
  state storage, admission preparation, body scratch allocation, composition and final buffer exchange.
  It does not change animation, RefreshBoneTransforms, query hooks, guards or profiling scopes.

The copied active file baselines are:

| Active file | SHA-256 |
| --- | --- |
| Public/ProphecyJoltPose.h | `2287D83B997AD5E3FBF09EBD491015136A9CE24A6B77BDB5B4321B7DFEBDFE5D` |
| Private/ProphecyJoltPose.cpp | `5A1D57B25B3603C6BA99D98040770562880F65D50C04367B83279F6943DA8DF0` |

The Character patch was checked against SHA-256
`417BD14D2A50B58E09C93DA838364DDF301B3A007A32B72EA2599DC7A1674242`.
Other agents own adjacent Character publication work; apply isolated hunks rather than a full-file copy.

## Work moved out of each frame

`ProphecyJolt::Pose::FPreparedLayout::Build` owns copies of the parent topology, dense bone-to-body map,
literal `BodyFromBoneRigid.Inverse()` results and visual scales. Build validates single-root order,
mapping uniqueness/index ranges, fixed offset frames and positive visual scales. The private bound rig
does not mutate these fields; an explicit rebind builds a new layout. Failed Build leaves the layout invalid.
It stores no UObject or native physics references.

Per-frame `Compose` still validates every changing local input, completed body frame, component carrier
and all three output transforms for every bone. Array-count checks and those error messages remain.
The exact original transform expression order, normalization calls, scale handling and
`GetRelativeTransform` calls are retained; no multiplication chains are regrouped. Local, component and
world arrays are all still produced for all 88 bones. The only cached transform calculation is the literal
inverse of each immutable body offset.

The reusable-output method empties output array lengths on failure while retaining capacities. This
removes repeated output allocation; the compatibility function retains its original allocation behavior.
The method is const and contains only pure math, so a future caller could share a prepared layout among
independent jobs. This draft introduces no tasks or per-bone parallel scheduling overhead.

## Publication lifetime

Character body readback uses a persistent transform scratch array solely before any callbacks. The
working composed pose moves out of `State.CompletedScratch` into the same local `Completed` value used
by existing publication. That local owns its arrays even if animation callbacks remove or replace State.
After the existing final exact-identity guard, `Swap(State.Completed, Completed)` publishes the new frame;
the old frame moves into `State.CompletedScratch` for the next composition. Previous published data is
untouched until this commit. Failure destroys only the in-flight local buffer; the path already stops on
publication failure. After the first two successful frames, all six pose arrays alternate without allocation.

No reference into state-owned pose scratch is held across animation/query/finalization callbacks.
The existing callback guards and their ordering are not changed.

## Verification to run

Three additional automation tests:

- `Prophecy.Jolt.Pose.PreparedFullFrameMatchesLegacy`: 64 randomized 88-bone/22-body frames, physical and
  helper roots, out-of-order body mappings, nonuniform visual/local scales, accepted near-unit rigid scales
  and large component translations. Compares every scalar component of all local/component/world outputs
  against the original function, checks inputs remain unchanged, and checks output allocation addresses
  stay stable across changing frames.
- `Prophecy.Jolt.Pose.PreparedValidationAndRebuild`: unchanged dynamic-frame errors, array mismatch,
  unnormalized rotations, invalid scale and composition producing invalid scale; empty outputs on failure;
  invalid topology/duplicates/fixed offsets rejected at preparation; exact output after an explicit rebuild.
- `Prophecy.Jolt.Pose.PreparedPublicationBufferLifetime`: the actual move-out/swap-back ownership pattern
  retains the previous published frame until commit, recycles it, and keeps an in-flight pose valid after
  deleting its prior owner state.

Tests have not been compiled or executed by the drafting agent. Root owns build, execution and the
same 100-agent benchmark. Measure Compose, BodyRead, completed publication and whole-world time after
correctness passes; this draft makes no unmeasured speed claim. All existing pose tests should also run.
