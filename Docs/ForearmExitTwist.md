# Left forearm revolution after hooks —2026-09-26

The current possessed agent repeatedly performs `hookL` at ticks90,180,270, etc. Its first attack ends at115. Read-only850-frame capture confirmed repeated large left forearm rotations in recovery. The forearm matches `ForearmRotationFromHand` throughout (numerical residual only); this is not an independently spinning forearm or a disabled special correction. The hand rotates with it. The correction deliberately inherits the hand's axial twist and removes wrist swing only.

## Cause and change

`ProphecySlashReturnLibrary.cpp::ApplyPose` used the sword's directed, Euler-unwrapped rotation route for the empty left hand. `MakeWeaponRoute` correctly excluded right-sword geometry from the left hand, but still chose a side-directed yaw goal. Without a real blade it skipped the blade-based shortest-safe-route selection, allowing an unnecessary almost-full revolution. The forearm faithfully followed that commanded hand rotation.

Empty hands now shortest-path quaternion-slerp toward the actual neutral hand orientation and toward NN orientation during transfer. Position still follows the existing front-of-torso route; progress, speed scaling, hold/blend clock, elbow reconstruction and clearance rules are unchanged. An actual held blade retains the existing winding, yaw limit and blade-clearance math exactly. Selection depends on actual blade geometry, not an attack-name exception. No new pose/history/timer, actor layout change or inactive work.

This does not disable or change forearm correction, wrist bend constraints, checkpoints, physics or Blueprint settings. In particular a55-degree wrist bend cone is not an axial-twist limiter.

## Controlled evidence

Editor-only `Prophecy.SlashReturn.UnarmedShortestRotation` defaults1. Value0 selects the previous rotation path for comparison; restored1 after captures. No Shipping comparison branch. All captures used owned PIE and ended it; no user Play stopped, graph rewired or asset explicitly saved.

`Saved/Diagnostics/ForearmExit/baseline.json`:850 frames; `legacy.json` and `fixed.json`:360 each. All3 agents recorded, including world future/presented poses and physical mesh transforms. Original and comparison-legacy measurements agree. Across the first114 ticks, all captured future positions and quaternion components are exactly identical between legacy and fixed. The difference starts at recovery, not from altered attack initialization.

| Recovery ticks | Previous net forearm roll | Fixed net roll | Previous largest policy rotation step | Fixed largest step |
|---|---:|---:|---:|---:|
|115–174|−320.13°|35.93°|76.41°|13.57°|
|205–264|−320.23°|35.78°|76.13°|13.59°|
|295–354|−319.79°|36.26°|76.01°|13.60°|

Roll is accumulated signed twist after transporting the previous forearm axis to the next, not wrapped Euler-angle subtraction. First recovery absolute roll travel321.09→39.95degrees. Metrics summarize published targets; no claim that all physical contacts or later recurrent positions remain identical. Data/analysis: `Saved/Diagnostics/ForearmExit/summary.json`, `AnalyzeForearmExitCompare.py`, `SummarizeForearmExit.py`.

Live build72.88s loaded11:39:09UTC. Eight existing native tests passed11:41:20UTC: sword route/lifecycle, five hand-recovery tests and two forearm correction tests. The additional UnarmedRotation test passed11:49:58UTC after its35.01s test-only build (short path, monotonic approach, quaternion sign, unchanged position, exact NN endpoint). No Blueprint layout changes. Include this Live Coding patch in the next authorized normal editor build.
