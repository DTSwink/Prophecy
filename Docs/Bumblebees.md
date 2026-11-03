# Bumblebees (ambient wildlife)

Status: November 2, 2026. New isolated runtime module `ProphecyAmbient`; no existing gameplay module, Blueprint, map or tuning was changed.

## What it is
- `ABumblebeeZone` ("Bumblebee Zone"): a preference box. Place/scale it over a garden, set `BeeCount`, `Preference` (0 roam freely … 1 always land inside), `bAvoidIndoors`.
  Zones are not spatially loaded (World Partition) so bee state persists for the level lifetime.
- `ABumblebeeSwarm` ("Bumblebee Swarm"): one manager actor. Created automatically by the first zone if the level has none;
  place one yourself to tweak settings (distances, speeds, threat list, trace budget, shadows).
- Hero asset `SK_Bumblebee` (skeletal, `Fly` / `Idle_Landed` anims) is for close cinematics only; the swarm uses
  `SM_Bumblebee_Fly` / `SM_Bumblebee_Landed` (4 LODs each) through instanced static meshes.

Assets: `/Game/Prophecy/Creatures/Bumblebee` (created by `Exports/Bumblebee/setup_bumblebee.py`). Source art and FBX: `Exports/Bumblebee/`.

## Blueprint nodes (category "Bumblebees")
| Node | Use |
| --- | --- |
| **Spawn Bumblebee Zone** (Location, Box Extent, Bee Count, Preference, Size Multiplier, Wing Beat Hz, Walk Speed, Air Time; advanced: Rotation, Avoid Indoors, Show In Game) | the one node you need: creates a preference box; bees appear on surfaces inside it when a camera is near |
| Spawn Actor from Class → Bumblebee Zone | same, every zone setting exposed on spawn |
| **Set Bumblebee Size** (Scale) | global size, 1 = 2.5 cm model, default 0.75 (typical worker, about 1.9 cm); every bee also gets ×0.8–1.15, about 6% are queens ×1.2–1.35 |
| Add / Remove Bumblebee Threat (Actor) | bees take off when the actor moves close (player pawns are automatic) |
| Set Bumblebees Enabled (bool) | pause / resume the simulation |
| Show Bumblebee Zones (bool) | draw every zone box + label while playing |
| Get Bumblebee Stats | counts and cost (avg/max ms, traces/s) |
| Get Bumblebee Swarm | the manager actor (all tuning properties) |

Zone settings: **Wing Beat Hz** (default 150 = real *B. terrestris*; reads as a blur at any frame rate, the wing membrane fades
toward a blur look above ~40 Hz; 20–40 gives a visible stylised flap), **Walk Speed** (cm/s, default 2.5; each bee ×0.75–1.25;
the legs step from the distance actually walked, stride grows with speed, so feet never slide), **Air Time** (0 = short hops
and long rests, 1 = mostly flying; default 0.5: about 35–40% of the time in the air around flowers and props, more over
open ground where there is little to land on).

Zone visualiser: thick yellow box (resize with Box Extent or the scale gizmo, rotation supported), bee icon sprite and a label
"Bumblebee Zone / N bees / pref / size / wings Hz / walk / air" in the editor; tick **Show In Game** (or call Show Bumblebee Zones) to see it in Play.
Bee Count is read when the zone begins play.

## Behaviour
| State | What happens | Cost |
| --- | --- | --- |
| Landed | 2–14 s (× Air Time factor). 92% of landings walk: walking bouts (mean 2.6 s) with short heavy-tailed pauses, correlated-random-walk turning (Ornstein–Uhlenbeck), climbing bias on walls/stems. A surface probe every 1 cm (× scale) keeps them on the surface; at edges/obstacles they turn and carry on after a brief hesitation. Leaving the preference box steers them back. Legs: tripod gait, one cycle per stride walked (linear stance stroke = feet planted). | near only: ~2 line traces per cm walked |
| Take-off | when the landed timer ends, or when a threat moves within `ThreatRadius` faster than `ThreatMinSpeed` (or is within `ThreatPanicRadius`): flee flight away from it | 6–14 traces once |
| Flight | chains 0–8 aerial legs (mean 5 × Air Time) and then a landing. Landing spots: rays aimed past random points of the preference box hit whatever is there (walls, fences, stems, leaves, rocks, undersides down to `MinLandingNormalZ` -0.5, flowers, ground). Every leg is verified with sphere sweeps (`FlightClearance` 5 cm) before it is flown; corners are rounded only as much as stays inside that clearance. Speed is continuous: braking for tight turns (`TurnAcceleration`), constant time-to-contact landing approach down to `TouchdownSpeed`. **No hovering stop**: the next leg is planned on the final straight of the current one; if it is not ready the bee doubles back along its validated path. | 2–10 traces per leg, 0 while flying |
| Indoor escape (near player) | if the take-off point is under a roof with ≥3 of 4 walls around, the bee explores: 9-ray fan, prefers long free rays, open sky (door/window) and unvisited space (memory of last 6 waypoints), hover-look-fly steps until it has open sky, then normal landing. Max `MaxEscapingBees` at once; gives up after ~60 s and retries later. Zones with `bAvoidIndoors` also reject enclosed landing spots. | ~12 traces per step |

Threats: `ThreatActors` list (+ `AddThreatActor`/`RemoveThreatActor` in BP), every actor tagged `BeeThreat`, and player pawns (`bPlayerPawnsAreThreats`). Speed is measured from position deltas, so kinematic/animated actors work too.

## Motion quality (November 3)
- Flight: validated polylines with **circular-arc corners** (constant speed along the arc, exact length); wide arcs up to
  `MaxCornerRadius` are swept along their own length, tight spots keep arcs inside the leg's validated clearance.
  Speed limited by `TurnAcceleration` and by `MaxPathTurnRate` (340 deg/s: bees slow and pivot in tight spots).
  Sway offset persists across legs (frame parallel-transported, no flips on vertical take-off/landing stretches).
  Body: heading from the path, bank from lateral acceleration (`BankPerG`), nose-up when braking, turn rate capped by
  `MaxBodyTurnRate` (360 deg/s, bumblebee body saccades ~350 deg/s); touchdown eases into the surface pose.
- Walking: short segments (0.8 cm x scale) whose path (head height) and end foothold are checked **before** walking them;
  footholds must be on the same surface (rise/drop <= 0.3 cm x scale), so no walking off rims, onto leaves below or into
  raised flower centres. Position/up glide along the checked segment.
- Measured (`-BeeTest=traj`, every bee near the patch at 60 Hz, `Saved/BeeTest/traj/traj.csv`): flights with a >25 deg
  heading jump in one frame 135 -> 23 of ~600, >60 cm/s speed steps 111 -> 3; walking vertical jitter max 16.5 -> 0.8 cm/s,
  2-3 mm snaps every probe -> none.

## Optimisation pass (November 3, after the motion fixes)
Deterministic swarm scene, same view, built-in profiler (ms of game thread per frame, ~300 near bees, ~280 flying):
flight 0.144 -> 0.084 (arc geometry and corner speeds computed once per leg instead of every frame),
render updates 0.093 -> 0.071 (bees on surfaces beyond 1.5 m send transforms only at ~half-pixel changes; one custom-data
write instead of two), tiers 0.030 -> 0.029 (frozen far bees re-check distance every 8th frame); **total 0.361 -> 0.262 ms**.
Trajectory/walk measurements unchanged. What remains scales with the number of flying bees in view (each needs a transform
every frame to look smooth): Air Time and the distance settings are the levers.

## Cost model
- One actor tick, no per-bee actors/components/skeletons. 8 ISM components (2 poses × 4 forced LODs).
- Tiers by distance to the nearest player camera: **near** < `NearDistance` (1500): full behaviour; walking only below
  `WalkDistance` (600, a 2 cm bee is a few pixels beyond that); **mid** < `VisibleDistance` (2500): fly/rest only;
  **far**: frozen in their last valid pose/path (no simulation, no instance updates) and culled on the GPU.
- Zones place their bees lazily when a camera comes within `PlacementDistance` (4000), i.e. where collision is loaded; then they persist.
- All traces share `MaxTracesPerFrame` (32); walking probes are capped at `MaxWalkTracesPerFrame` (16) so they can never starve
  take-offs or the next flight leg; bees already in the air and threatened bees plan first.
- Only bees that moved update their instance (incremental `UpdateInstanceTransform`); beyond LOD1 every 2nd frame, mid tier every 3rd.
- LOD distances 150 / 450 / 1000 / 2500 cm: 18k / 7.2k / 2.5k / 355 tris. Only LOD0–1 cast shadows, LOD3 has WPO disabled.
- Wings and legs animate on the GPU via World Position Offset from per-instance custom data
  (`0` flap amount, `1` leg cycles walked, `2` stride × walk amount, `3` wing beat Hz) and vertex-colour masks
  (R fur shadow, G wing id, B leg weight, A tripod group).

### Measured breakdown (November 3, 500 bees, worst-case close view: ~300 near + ~80 mid, ~280 flying, laptop)
| Part | Game-thread ms/frame | Knob |
| --- | --- | --- |
| Instance updates (render data of moving bees, ~11k/s) | 0.08 | `LOD1Distance` (full-rate updates inside it), mid-tier stagger, fewer flyers (Air Time) |
| Flight path following + speed planning | 0.08 | Air Time, `NearDistance`/`VisibleDistance` |
| Flight-leg traces (sweeps/lines, ~2–10 per leg) | 0.03 | Air Time, `AirLegRange` (longer legs = fewer plans), `MaxTracesPerFrame` |
| Tiering, threat checks, bookkeeping | 0.03 | number of bees, `ThreatActors` |
| Walking surface probes | 0.02 | `WalkDistance`, `MaxWalkTracesPerFrame`, `WalkerFraction` |
| Walking logic | 0.015 | `WalkDistance` |
| **Total swarm tick** | **≈0.26–0.3** (0.02 when all far) | `bumblebees.Enable 0` pauses |

Whole game thread: 2.32 ms with bees vs 2.01 ms paused / 2.03 ms no bees. GPU at 1600×1000: bees visible vs hidden
≈ +0.15–0.6 ms (laptop noise of the same size); shadows and WPO each below the noise (< 0.1 ms). Render thread: within noise.
Memory: static meshes 7.4 MB (both poses, 4 LODs), textures 6.5 MB (5 × 1K + 1K×512), instance buffers 1.2 MB (4,000 instances),
bee state 672 B × 500 = 0.33 MB → ≈ 15.5 MB total.
Cost A/B commands: `bumblebees.Render 0`, `bumblebees.Shadows 0`, `bumblebees.WPO 0`, `bumblebees.Profile 1` (+ `bumblebees.LogStats 1` → `BEEPROF` lines).

Console: `bumblebees.Enable 0/1`, `bumblebees.Debug 1` (paths) / `2` (+ every trace), `bumblebees.LogStats <sec>` (JSON `BEESTATS` lines),
`bumblebees.Profile`, `bumblebees.Render`, `bumblebees.Shadows`, `bumblebees.WPO`.

## Background tooling used
Claude's cloud session has no shell on this PC, so the user started `Saved/ClaudeJobs/StartRunner.cmd` once: a minimized PowerShell
loop that runs `*.ps1` files dropped into `Saved/ClaudeJobs/inbox` (logs in `outbox`). Close that window to revoke it.
Headless launches need `-unattended` (otherwise an invisible modal dialog blocks `-game -RenderOffscreen`) and
`-DisablePlugins=Fab` (Fab asserts without CEF), as in the existing Bodyflip automation. Asset setup must run in a full
`UnrealEditor-Cmd -ExecutePythonScript` session, not the `pythonscript` commandlet (Interchange texture import needs Slate).

## Verification
Headless runs only (no user editor/Play touched): `UnrealEditor.exe <uproject> /Engine/Maps/Entry?game=/Script/Engine.GameModeBase -game -RenderOffscreen -BeeTest=model|swarm` and `/Game/mybasic -game -RenderOffscreen -BeeTest=map`.
The test director (module-internal, only spawned with `-BeeTest=`) builds a throw-away scene at runtime, takes screenshots and writes
`Saved/BeeTest/<scene>/report.txt`.

Results (November 3, after the feedback round: no mid-air stops, legs from distance, 150 Hz wings, more walking, any surface, more flying):
- **Video** (`-BeeTest=video -BeeVideoPart=1|2|3`, three processes because RAM is tight; joined to `Saved/BeeTest/Bumblebees_Swarm_v2.mp4`):
  orbit, chase through flight legs and a landing, walking close-up on gritty ground, a bee on a vertical surface, wing side view, threat.
- **Flower patch** (45 bees with rock, tilted board, fence, leaves, log): ~35–40% flying; of the landed bees ~40% are on walls,
  slopes, leaves or flower tops, the rest on the ground; ~60% of landed bees walking at any time.
- **Swarm** (500 bees / 3 zones): 3,100 take-offs and 2,800 landings in ~3 min, 25 double-backs (bee reached the end of a leg before
  its next one was planned and turned back instead of stopping), 46 threat take-offs, 12 bees put in the closed room: all out
  (9 found the door by exploring, the rest through normal flights after landing near the door). In the big open field ~70% of bees
  are in the air (few surfaces to land on besides the ground); lower Air Time there if that is too busy.
- Earlier (November 2): model render check, size check vs UEFN mannequin (167.8 cm; default bee 1.9 cm), first video.
- **mybasic**: not run yet (RAM: ~3.4 GB free with the editor closed; loading the map drops below the watchdog threshold).
