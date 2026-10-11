# Sword holster numerical investigation — October 11, 2026

User requested an overnight port, safety checkpoint, broad numerical diagnosis,
systemic fixes and final performance audit. This is the decision/test annex;
the main journal only summarizes the current state. No visual motion claims.

## Plan and acceptance evidence

1. Freeze the live desktop lab state, current native profile, Blueprint graph,
   asset hashes and editor dirty/Play status. Preserve user edits and sessions.
2. Port missing behavior and current tuning. Build normally for retained layout
   changes; verify reflection and actual Play. Commit and push a curated safety
   checkpoint before the investigation changes gameplay behavior.
3. Run all pure lab/native regressions, then collect all failures from owned
   Unreal Play replays: idle/walk/run, kinematic/physical, both actions, repeated
   cycles, different gaze, acceleration/turning, timing/pause and cancellation.
   Keep per-tick phase/ownership, target/future/physical poses, equipment and
   constraint state. Compare parent-local rotations and lengths as well as world
   steps, separating expected locomotion from procedural discontinuities.
4. Classify stalls by authored geometry versus physical lag versus lifecycle.
   Classify snaps by raw NN, authored target, display, physics or ownership edge.
   Fix shared causes with bounded work; do not hide failures through increased
   tolerances, extra shrink, arbitrary delays or changed motor/asset tuning.
5. Rerun the complete matrix after fixes and retain first-failure evidence.
   Measure procedural and admission costs using the existing 100-agent benchmark;
   distinguish diagnostic overhead, whole-game cost and inactive work.

## Decisions and observations

- Initial live state: walking, S, gaze -24°, start25, reach230cm/s,
  rotation600°/s, slide150cm/s, shrink15%, unshrink.5s, head tilt45°.
  D return stored progress.9, S.7. Preserve current live values even when they
  differ from an earlier factory/default discussion. Gaze remains per-agent in UE.
- Native lacked the latest head vertical-axis bound. Port the exact local-X
  head-versus-spine05 swing projection, including the minimum boundary correction
  when spine motion makes the old head illegal. Legacy no-bound tests explicitly
  use90°. This is not a nose-pitch or world-Z limit.
- Locomotion must keep its own tick clock. Native reads current unmodified NN
  every update; test this under real moving agents, not only prerecorded walk.

## Results

- Port normal build: initial compilation failed on a new editor-helper
  `TObjectPtr` range declaration; corrected to explicit `UEdGraphNode*`.
  Incremental retry succeeded69.18s. One clean visible editor restart.
- Native initial suite12/12 passes. LabChannels18,000 samples:
  head2.96e-6°, neck7.25e-6°, position5.38e-7cm, completion mismatches0;
  slide geometry500 samples max1.88e-13cm /2.96e-6°.
- Lab collect-all initial run22/24 passes. Two stale checks fixed without
  changing motion: arm lengths must use continuous locomotion time, and S
  entry now permits the already-authorized tip2cm/angular-tolerance gate.
  Both focused reruns pass; full rerun follows later.
- Remote Python discovers the first editor, including an isolated commandlet.
  An attempted value refresh reached the commandlet and refused saving; no
  disk asset changed. Subsequent remote work is serialized after commandlet
  exit. Visible editor refresh/save succeeded; graph differs only in230/600
  speed literals. No saved map, sword, motors or PHAT changes.

Pending. Raw evidence is kept under `Saved/Diagnostics/SwordOvernight20261011/`.
Failures, exclusions and remaining limitations will be recorded explicitly.
