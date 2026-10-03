# Sparse physical target pose draft

Source-only draft; no active changes, builds, Unreal launches or measured performance claims.

Promote `ProphecyNNPhysicalTargetPose.h`, `ProphecyNNPhysicalTargetPose.cpp` and
`ProphecyNNPhysicalTargetPoseTests.cpp` to `Source/GameAnimationSample3/Private/`.
Then apply `AgentTargetRead.apply-patch.txt` as its isolated Agent source edit. It adds one include
and replaces only the physical-data branch's whole-skeleton expansion/gather. No Agent header,
character component, snapshot publication, cadence, optional-feature setting or module dependency changes.

The Agent source used to prepare the patch has SHA-256
`C7548410EABAE15AF61418A61775F384BD132E26F28EAFE8975289DD4619BA79`.
The original block begins at line 1826 in `ReadNNFutureWorldPoseWithSnapshot`.
Apply the hunk to the current file; do not replace the entire Agent file if other work changed it.

## Retained behavior and work removed

The helper returns previous and future world transforms in the same PHAT order, skipping null body
setups and missing skeleton names and retaining duplicates. The Agent still uses its existing
`BlendAuthoredWorldTransform` followed by its existing `ApplyRigidForearms`, with the same alpha and snapshot.
The nonphysical branch is untouched.

The layout precomputes each skeleton bone's first matching NN index, each PHAT target index and its
minimal ancestor dependency closure. A supplied NN bone is component-space and needs only the original
`NNComponentPose[index] * ComponentWorld`. A missing bone retains every original
`ReferenceLocalPose[bone] * ParentWorld` multiplication, in ascending skeleton order; transforms are
never regrouped into a precomposed chain. Previous poses are still expanded before future poses.
When all 22 targets are NN supplied, each endpoint evaluates 22 transforms rather than 88.
The two stack-backed scratch arrays retain the reference-skeleton size, so parent indices need no remapping.

The cache retains only indices/names, with weak mesh and physics-asset identities. It shares layouts
across agents using the same mesh, PHAT and exact NN name sequence. Up to 64 layouts are retained;
invalid weak entries are removed on a miss and the least recently used entry is evicted when full.
Nothing keeps a UObject alive and there are no event delegates or shutdown dependencies.

Every call compares exact NN names, reference bone names/parents and current non-null PHAT body names
in order. A layout hash is not accepted as proof. Live reference transform values are read every
evaluation, so ref-pose value edits affect that same evaluation without rebuilding indices. Changes to
reference topology, PHAT names/order, source names/order, mesh identity and PHAT identity cannot reuse
incorrect indices. No compression or retarget-source state is cached; the input remains the latest snapshot.

The wrapper is explicitly game-thread-only, matching this physical target publishing path.
The private `FLayout` is exposed only to keep the independent oracle tests data-driven.

## Regression and measurement

Three automation tests use an independently frozen full-skeleton traversal as the oracle:

- `Prophecy.NN.PhysicalTargets.SparseMatchesFullTraversal`: 88 bones, 22 outputs, 128 randomized pose/layout
  combinations; missing NN helper/ancestor bones, all-reference fallback, reordered/duplicate/unknown NN
  names, PHAT skips/order/duplicates, nonuniform scales and reflected world scales. Every translation,
  quaternion component and scale component must match exactly. It also checks that a fully supplied
  22-target layout evaluates exactly 22 bones and unchanged layouts reuse their indices.
- `Prophecy.NN.PhysicalTargets.SourceReferenceAndAssetChanges`: live ref-pose value change without
  index rebuild; changed parents with rebuild; transient mesh/PHAT identities, null body rows,
  replaced ref skeleton and in-place PHAT name/order edits.
- `Prophecy.NN.PhysicalTargets.InterpolationAndRigidForearms`: all targets compared after the frozen
  Agent interpolation and actual `FProphecyNNPoseStore::ApplyRigidForearms`, enabled and disabled,
  at six alpha values. Uses its own scoped pose-store agent ID.

These tests have not been compiled or executed by this drafting agent. The parent owns build and
execution. After correctness passes, compare the same 100-agent benchmark's `targetRead` and full
world time; reduced arithmetic is not a substitute for that measured gate.

Remaining explicit boundary: the tests cover this target transform path, not an end-to-end gameplay
behavior or performance claim. Optional fists and broader integration remain frozen under the current
movement performance priority.
