# Isolated blood decal merger experiment

This is a separate UE 5.7 project and map, `/Game/Maps/BloodMergeLab`.
It loads neither Prophecy's content nor its runtime modules. Python remote
execution is disabled to prevent connecting a script to the wrong editor.
The user's `explosionVFX` map and removed fountain are not changed.

October20 follow-up: the user requested installation. A production adapter now
uses this kernel in the existing floor-grid component, with receiver/plane
separation, preserved Blueprint API and corrected bounds. See
[integration status](../../Docs/BloodExperiments.md#rectangle-integration--october20).
This independent lab remains a synthetic floor-plane fixture.

## What changes

The old floor merger joins four equal squares and never revisits those joins.
An early square at an awkward offset can prevent a larger filled patch merging.
The experiment retains occupancy and partitions each changed 32×32-cell region
into rectangles again. Rectangles cannot cover empty cells or overlap each other.
A filled region becomes one rectangle; a rectangular hole stays empty.

The production code also passes full widths to Unreal's `DecalSize`, which is
half-extents. Its debug boxes show the intended width, but actual projectors
cover twice that width. This lab uses half-extents and draws debug bounds from
the actual projector. A one-centimetre penetration keeps projection intersecting
the receiver.

Repeated hits in occupied cells do no partitioning or component work. Only dirty
regions enter the queue; decal components are reused and surplus ones pooled.
The grid stops ticking when idle. Caps bound region and component counts.
Cold component creation is also capped at 16 per update and checks the time budget
between allocations. Components are prepared invisibly in the pool; the previous
complete footprint remains until its replacement can be published. New hits during
preparation remain in occupancy and are included. Unchanged component transforms
skip render-state updates.
At the component cap, occupancy stays queued with `CapacityBlocked=true`; raising
the cap and processing again resumes the pending update. It does not silently
discard that occupancy.

The algorithm is an independent implementation of
[Lysenko's 2D greedy rectangle partition](https://0fps.net/2012/06/30/meshing-in-a-minecraft-game/).
[Binary greedy meshing](https://github.com/cgerikj/binary-greedy-meshing) provides
related bitmask precedent; no code from that repository is copied here.
Greedy partitioning is not guaranteed to produce the global minimum rectangle
count. It deliberately stops at region boundaries to bound update work.

## Scene and controls

Open `BloodDecalLab.uproject`, then `/Game/Maps/BloodMergeLab`, and Play.
The paired actors are labelled `OLD_*` and `NEW_*`. Four fixtures cover a filled
patch, a patch with a hole, scattered splash cells, and a thin strip.
The old column models the existing square rule and oversized projectors;
it is a behavioral comparison, not a timing benchmark of production code.
`NEW_ContinuousSpray` generates deterministic rotating synthetic floor impacts.
It deliberately avoids Niagara and the user's assets so merger behavior is
repeatable and independent of simulation/rendering cost.

Select a `BloodMergeScene` actor to change `ShowBounds`, `Spray`, `CellSize`,
`MaxRegions`, `MaxDecals`, `MaxRegionsPerUpdate`, `MaxNewDecalsPerUpdate`,
and `UpdateBudgetMs`.
`AddStain` accepts a point on that actor's local plane and a radius;
`AddCell` is the exact cell-level input.

This is the floor-plane prototype; production installation status is linked
above. Separate surfaces need separate receiver identities/planes in production.
Textured blood appearance, aging, arbitrary receiver geometry and
Niagara callback integration are outside this isolated merger test.
The solid diagnostic decal intentionally makes all projected area visible.

## Reproduce

For a fast check without Unreal, run `Tools/TestKernel.ps1`. It compiles the
same header with MSVC and exhaustively checks all 4×4 occupancy masks at three
offsets, including the 32-bit edge, plus a full region and checkerboard.
The first run passed **196,610 cases with zero failures** in under two seconds,
including compilation. Results: `Saved/Results/kernel-validation.json`.

Build only this target:

```powershell
& 'C:/Program Files/Epic Games/UE_5.7/Engine/Build/BatchFiles/Build.bat' `
  BloodDecalLabEditor Win64 Development `
  "-Project=$PWD/Labs/BloodDecalLab/BloodDecalLab.uproject" `
  -WaitMutex -FromMsBuild -NoHotReloadFromIDE
```

`-NoHotReloadFromIDE` keeps this independent build out of the other editor's
Live Coding session. It does not reload or modify Prophecy.

Run `Tools/RunScene.ps1` for non-rendering (`-NullRHI`) verification, or add
`-Render` for an offscreen rendered comparison. The wrapper launches only this
project in a hidden, low-priority process and returns its process ID.
The Python script asserts the project identity, creates/saves the scene, verifies
coverage using actual decal component transforms, tests streaming/reuse/caps,
then optionally captures actual Unreal rendering. Results go to
`Saved/Results/validation.json` and, with rendering, `Saved/Results/comparison.png`.
Only one shader worker is allowed by this project's config.
The initial render startup required a prolonged shader compilation, so it was
stopped to avoid continued load on the user's editing session. A non-rendering
pass does not validate visual appearance or GPU performance.

## Verified results — October 20

The isolated normal build passed. Native validation passed 196,610 cases.
The latest Unreal commandlet passed another 4,005 kernel cases and 4,211 assertions
covering actual component bounds, holes, negative coordinates, streamed additions,
repeated hits, pooling, cap recovery, transformed/radius impact inputs, bounded
allocation, invisible preparation and hits arriving during preparation.
The saved scene and materials belong only to this lab.

| Fixture | Old-rule model | New rectangles |
|---|---:|---:|
| Filled 16×16 patch, awkward initial square | 43 | 1 |
| Patch with a 6×6 hole | 43 | 4 |
| Scattered impacts | 52 | 24 |
| Thin strip | 8 | 1 |

The new footprints exactly cover the same occupied cells, without overlapping.
In the final run, 1,719 streamed occupied cells became 1,088 rectangles across
regions. Among 288 non-idle updates, CPU p95 was **0.2029 ms**, maximum **0.2435 ms**.
The isolated partition kernel averaged **7.1717 µs** per 32×32 region over 20,000
iterations. These measurements used NullRHI; rendering was disabled.
Final commandlet completed at 05:28:43 UTC with zero errors. Each run creates a
fresh blank lab world before saving, so it cannot append duplicate fixtures.

`Saved/Results/footprints.png` is a diagram of exported **actual Unreal component
bounds**, not a rendered screenshot. Regenerate with `Tools/plot_footprints.py`
(Python + Matplotlib) after `RunScene.ps1`. The old column deliberately includes
the production half-extents mistake as well as its square-merge rule.
There is no production renderer/frame-time comparison yet.

## Allocation stress audit

`Tools/RunScene.ps1 -Performance` runs twelve trials each of a fresh 512-cell
checkerboard, a fully filled region, collapse from 512 projectors to one, and idle.
The first version's one-shot checkerboard creation reached **8.5786 ms** in one
update: the soft region budget was insufficient. That behavior has been changed.
After the allocation cap, the same fixture's per-update p95 was **0.2611 ms**,
maximum **0.7486 ms**, with at most 16 new components per update. Collapse to one
decal peaked at **0.0436 ms**. The isolated five-action build passed in 29.75 s.

This spreads work rather than removing it: the extreme checkerboard needed up to
34 updates (about 0.57 s at 60 Hz) before its complete footprint appeared. Its total
median CPU work was 6.7862 ms across those updates. Ordinary small/dense impacts
need far fewer components. Idle actors do not tick; manually calling the idle
processor for the benchmark measured at most 0.000202 ms.
`Populate` is a fixture helper that deliberately drains the queue synchronously;
normal `Tick` calls `ProcessChanges` once per update.

Receipts: `Saved/Results/performance-before-budget.json`, `performance.json` and
`validation.json`. These are NullRHI CPU measurements under competing workloads.

## Timing interpretation

The partition benchmark measures only the C++ rectangle algorithm.
Streaming timings also include synchronous Unreal component updates, but not
GPU rendering or deferred render-thread work. The time budget is checked
between allocations and regions; a single allocation or final publication of a
region can exceed it. No hard 0.25 ms frame-time or
production FPS improvement is claimed. Rendering benefits depend on visible
projected area, decal count and material cost.
