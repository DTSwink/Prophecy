# Ambient birds (gulls + kingfishers)

Runtime module `ProphecyAmbient` (same as the bumblebees). Few birds, full skeletal meshes, realistic flight.
Models are **placeholders** (procedural, Blender) — a better model drops in if it keeps the bone names below.

## Use it

* Place a **Bird Zone** (or call **Spawn Bird Zone**): box = home range, `Species` (Gull / Kingfisher), `Bird Count`,
  `Primary Colour` / `Secondary Colour` (kingfisher brown / white; gulls all look the same), `Size Multiplier`,
  `Air Time` (0 mostly perched … 1 mostly flying), `Ambient Cries`.
* Birds spawn when a camera comes within `Activation Distance` (collision must be streamed in), perch on flat surfaces
  inside the box (kingfishers prefer raised perches: posts, rails, rocks, roofs), fly around above it, gulls walk.
* **Cries / SFX:** bind `OnBirdCry (Bird, Duration)` on a bird or `OnZoneBirdCry` on the zone and play your sound
  (attach to `Bird.Mesh`, socket `head`). `Bird Cry (Bird, Duration, Openness)` makes one call now;
  `Set Beak Open (0..1, <0 = automatic)` lets you drive the beak from your own audio envelope.
* **Threats:** player pawns, actors tagged `BirdThreat` / `BeeThreat`, classes in the flock's `Threat Classes`,
  or `Add Bird Threat`. Perched birds take off away from them, flying birds veer off / climb.
* **Death:** a bird dies (ragdoll + feather burst) when
  * Unreal damage ≥ `Lethal Damage` (10) — `Apply Damage` / `Apply Point Damage` (smaller damage = a few feathers + flee),
  * an object of a lethal class (default `/Game/_mygame/spear/A_Spear`), with a lethal tag (`Spear`, `BirdLethal`,
    `BodyflipProjectile`) or whose name contains Spear / Javelin / Arrow passes through it faster than `Lethal Min Speed`
    (750 cm/s). Swept test on the object's long axis — works for the Jolt-driven Bodyflip projectiles that have no Chaos collision,
  * a physics impact ≥ `Heavy Hit Impulse` (250 kg·cm/s; e.g. a thrown rock). Objects are watched while inside a bird's reach;
    their velocity is the Chaos body's or, when it reports none (Jolt-simulated or kinematically moved objects), measured from
    their motion, so a rock dropped through the project's Jolt physics counts too. Pawns never count (birds flee them),
  * `Kill Bird`. Neighbours within 25 m are startled.
* **Blood:** a hit that bleeds puts a stain on the plumage at the hit point (where the line of travel enters the body; a spear
  through the bird also leaves a smaller exit stain). Optional (flock `Blood Splat`, off by default): also spawn the project's
  `NS_bloodsplat` there; its `User.decal_callback` is bound automatically to the level's decal manager
  (`ProphecyBloodNiagaraCallbacks`), so drops stain the ground / meshes like the rest of the game's blood. It is authored for
  human-scale wounds and needs the level's blood fluid post-process: in a bare test map it renders as raw red streaks, and the
  first spawn compiles the system in editor builds (~1 s hitch). The plumage stain is a material mask in reference-pose space (4 most recent stains
  per bird): it follows the body in every pose, stays on the corpse, costs no render target and keeps the per-bird recolouring.
  * **Which hits bleed:** `Set Bird Bleed Condition` — bind a function (Create Event) that takes a `Bird Hit Info` and returns
    true to bleed. It carries `Source` (Damage / LethalObject / PhysicsImpact / Manual), `Object`, `Component`, `Location`,
    `Direction`, `Speed` (relative cm/s), `Momentum` (kg·cm/s), `ObjectForward`, `AlignmentDeg` (0 = tip first,
    90 = flat/sideways), `IncidenceDeg` (90 = straight into the body, 0 = grazing), `Damage`, `Bone`, `bLethal`, `bLethalObject`.
    Unbound = placeholder rule `DefaultShouldBleed`: kills and hits by lethal objects bleed, blunt wounds don't.
  * `On Bird Hit (Hit Info, Bled)` fires on every kill / wound. `Add Bird Blood Stain` / `Clear Blood Stains` act directly.
  * Tuning: species `Blood Stain Radius` (gull 4.5 cm, kingfisher 1.8 cm), `Blood VFX Scale`; flock `Blood Splat` on/off and
    `Blood Splat System`; material `BloodColour`, `BloodRoughness`. Console `birds.Blood 0` never / `1` condition / `2` always.
* **Feeding:**
  * Kingfishers (`bFishes`) go fishing every `FishingInterval` (30–90 s) when water is within `FishingRange` (40 m). Hunting
    follows high-speed studies of pied kingfishers:
    * Approach: fast and level (~8 m/s here; 10–12 m/s measured), 1.5 m below the hover height, then swoop up into the hover,
      trading speed for height.
    * Hover: 1.5–5 s with the body tilted up, the bill ~76° below the horizon (the neck takes the bend) and the head held still.
      The bird sometimes shifts the hover a few metres; a third of dives come straight out of the swoop at the top of the climb.
    * Dive: ballistic. One eased roll-over head-down, the last strokes fade, then gravity does the work and the wings sweep back
      as speed builds. From 4 m the bird enters the water beak-first at ~8–9 m/s about 0.8 s later.
    * Underwater it stops within a body length or two, turns back up and breaks out beating hard.
    * It comes up with a fish `FishingSuccess` (60 %) of the time. On a miss it hovers a little further along and dives again
      (up to 3 dives).
  * With a fish they land on the nearest low stretch of beach, holding it crosswise in the bill while it thrashes in bursts that
    die out over `FishStruggleTime` (45 s). Once it is still they drop it, peck at it (`PeckCount`) and fly off, leaving the
    remains. The fish thrashes at 6–11 beats/s in 1–3 s bursts with short pauses for the first half of `FishStruggleTime`, then
    tires: weaker, slower, shorter bursts and longer rests until it lies still.
    A flushed kingfisher flies off with its fish and lands elsewhere; an interrupted meal is left as remains.
  * Gulls (`bScavenges`) spot remains within `ScavengeRadius` (35 m) and claim them, one gull each. They land a short walk
    away, walk up, lower the head, open wide, take the remains, throw the head back and swallow them whole, which destroys
    the fish actor.
  * Fish: `ABirdFish`, flock `Fish Mesh` (placeholder `/Game/_mygame/assets/fish/SM_Fish`, the smoked fish). Any static
    mesh works: it is scaled to `FishLength`, its longest axis is the length and its thinnest axis the side it lies on.
  * Water: actors tagged `BirdWater`, the flock's `Water Actors` / **Add Bird Water**, or found automatically (flat actors
    whose mesh, class or name contains water / ocean / sea / lake, e.g. `water_plane`). The top of the bounds is the surface.
    Birds never land on water.
  * Events (bird): `On Bird Plunge (Bird, Water Location)` for the splash sound (flock `Splash System` spawns a Niagara
    splash if set), `On Bird Caught Fish`, `On Bird Left Remains`, `On Bird Swallowed`. Nodes: **Send Bird Fishing**,
    `Get Task`, `Get Fish`.
* Everything is tunable on the **Bird Flock** actor (created automatically) and per zone (`Override Settings`).
* Console: `birds.Enable 0/1`, `birds.Debug 1` (separation spheres, reserved spots).

## How it works

* `ABird` (one actor per bird, body-centre location) + `UBirdAnimInstance` (native, no graph): blends the clips
  Perch / Walk (cycle = 2 steps) / Glide / Flap (1 s cycle) / Hover (braking & take-off strokes), then adds head look
  (quick saccades) and the jaw (beak) procedurally. Walk plays at `WalkSpeed / Stride` so the feet stay planted;
  flap rate = species Hz × a per-bird factor (±`FlapHzVariation`, 12 % gull / 15 % kingfisher) that also wanders slowly,
  faster when climbing, and every wingbeat has a slightly different depth — a fixed fast beat aliases against the frame rate
  (10 Hz at 30 fps = the same 3 wing poses every beat).
* Body motion in flight (`BuildStrokeTables`): the body is not carried along the smooth path. Lift over the wingbeat
  (downstroke 55 % of the cycle, peaking early in it; upstroke `UpstrokeLift` × that at cruise, 0 when hovering; mean = weight)
  minus weight is double-integrated, so the heave follows g/f²: a gull at 3 Hz bobs ~5 cm peak to peak, a kingfisher at 10 Hz
  under 1 cm. The body is lowest mid-downstroke and rises through the end of it (as measured in swallows). There is also a forward
  surge from the thrust pulse, a `StrokePitchDeg` pitch swing (lift × fore/aft sweep), and turbulence (`GustRollDeg`,
  `GustHeaveCm`, felt most in glides). The head stays level against the pitch (gaze stabilisation). This is applied to the mesh
  only; spots, separation and sweeps use the smooth path.
* Articulation (`UBirdAnimInstance`):
  * Small looks use the head and upper neck. Deep reaches (pecking, picking food up, the hover-hunting bill-down pose, to
    −100°) curl the lower neck and the front of the back as well, so the body itself only leans a few degrees.
  * Walking and stepping add a slight body twist per step, a counter-swinging and bobbing tail, and a small nod. The head is
    held level: 85 % of the waddle roll is cancelled at the head.
  * Turns are led by the head; the body follows.
* Shadows: bounds come from the mesh asset (wings spread), so no feather sticks out of them and leaves stale cached shadows
  on the ground. A ragdoll switches back to bounds that follow its bodies.
* Idle life while perched: head saccades, and every `IdleActionTime` (gull 1.5–4.5 s, kingfisher 1.8–5.5 s) a turn on the
  spot with small steps (`TurnRateDeg`, the walk cycle advances with the turned angle) or a short shuffle
  (`ShuffleChance`, `ShuffleDistance`: gull 12–45 cm, kingfisher 3.5–9 cm). Longer walks (gulls) on top, `WalkChance` 0.7.
* Flight: coordinated, bank-limited turns (lateral accel = g·tan bank, roll-rate limited) → continuous curvature,
  velocity and orientation. Flight-path angle and speed are rate-limited; gulls alternate flap / glide bouts (gliding sinks),
  kingfishers flap with short undulating glides.
* Landing: a free spot is chosen and **reserved** (traces: flat, room for the body, open sky, feet supported, clear
  approach corridor, spaced from every other bird's spot/position). Approach point upstream, final approach with a
  deceleration profile √(2·a·d), braking strokes (Hover) as speed drops, go-around on overshoot.
* **No overlap:** predictive avoidance between birds (closest approach within 1.5 s, one climbs / one dives) and a hard
  pass every frame: no two birds closer than the sum of their radii (half span in flight, ~0.7 span when hovering,
  body radius on the ground); landing spots are spaced so a hovering bird fits next to a perched one.
* Never through geometry: sphere sweep along every flight step; obstacle look-ahead steering.
* Ragdoll: physics asset built at runtime from bone names (torso, neck, head, tail, 3 wing segments ×2, 2 leg segments ×2),
  realistic masses (gull 1.25 kg, kingfisher 85 g), limited joints, wing drag. A live bird has no ragdoll bodies: one
  collision sphere (`Body`, blocks everything but Pawn / Camera, hit events → same handler) plus the flock's impact probes
  (body, head, wings). The ragdoll is created at death and simulates with the bird's velocity + the hit impulse at the hit
  bone. Continuous collision on torso + head only; a corpse lying still for 1 s is put to sleep.
* Feathers: instanced cards (one draw per species) simulated on the game thread as flat plates. Drag across the vane brings
  them to their falling speed (down ~25 cm/s, contour ~60, coverts ~100); drag along the vane is 0.15× that, so a tilted
  feather slides along its own plane. They tumble, then rock down with a lopsided tilt (asymmetric vanes) that makes each one
  glide to its own side. Drag is relative to the moving air: flock `Wind` (1.5 m/s breeze; the direction comes from the level's
  Wind Directional Source if there is one), slowed near the ground by a log boundary layer, with turbulent gusts a few metres
  across.
  * A falling feather drifts metres in even a light breeze, which is why feathers scatter. 60 % come loose at the hit, spread
    along the struck part of the body and carried along the strike; the rest are shed over the first 1.2 s of the fall with the
    body's velocity, plus a few more when it hits the ground.
  * 25–60 s life. Colours follow the bird (atlas + recolour masks).

## Performance
Cost model (flock tick, game thread): ~5 µs per live bird for behaviour, ~3 µs for impact probes, ~4 µs for visuals,
separation O(n²) on cached data (7 µs for 44 birds), feathers ~0.25 µs each while airborne and ~0 once landed.

* **One transform update per bird per frame:** the wingbeat body offset is written to the mesh before the actor move, so
  the move carries it; a bird standing still is not moved at all.
* **No kinematic bodies on live birds:** the old 14-body ragdoll per bird was dragged along every frame (most of the
  "visuals" cost). Now it is one sphere; the ragdoll appears at death.
* **Impact probes** query movable shapes only (the static tree — landscape, buildings, the ground under the bird — is
  skipped), and bone positions are read only when something is actually near.
* **No world sweeps:** lethal / threat / water discovery runs through every level's actor list in slices
  (`ScanActorsPerFrame`, 256 by default), plus an instant check of every spawned actor. Class results are cached, and
  names are matched without allocations. Lethal objects re-find their shaft once a second, not every frame.
* **Distance tiers** (from the player cameras, re-evaluated in slices with hysteresis; Flock › Birds|Performance):
  * `ShadowDistance` 45 m: no shadow beyond it.
  * `UpdateRateDistance` 25 m: birds standing about update bones at a reduced, interpolated rate. This is never used in
    flight or while feeding.
  * `FarDistance` 60 m + `FarTickInterval` 4: idle perched birds think every 4th frame. Any state change returns them to
    full rate, and skipped time never folds into a flight step.
  * Off screen, bones are not evaluated (unchanged).
* **Animation:** only clips that contribute are sampled; the static Perch / Glide poses are decompressed once and copied.
* **Feathers:** only instances that moved are sent to the renderer.
* **LODs:** 4 levels generated by `Exports/Birds/setup_bird_lods.py` (also run by setup_birds.py): 100 / 50 / 25 / 10 %
  at screen size 0.06 / 0.025 / 0.01. A gull is ~0.12 at 10 m and ~0.04 at 30 m. Gull vertices 10.6k → 3.7k → 2.2k →
  1.4k. Feather textures are capped at 1024. Re-run the script after importing the final models.

Measured, `-BirdTest=perf` (beach, 1280×720, fixed 60 Hz). Game-thread ms per frame; flock tick in brackets.

| Window | before | after |
|---|---|---|
| 12 birds | 4.74–4.85 (0.60–0.66) | 2.0–2.6 (0.19–0.26) |
| 44 birds | 9.48–9.79 (1.66–1.89) | 3.4–3.5 (0.56–0.63) |
| 44 birds, camera 120 m away | 11.39 (2.01) | 3.59 (0.58) |
| 44 birds, camera turned away | 8.19 (1.98) | 3.09 (0.59) |
| 11 simultaneous kills + 500 feathers | 16.99 (2.24) | 5.94 (0.74) |
| birds hidden, corpses lying (baseline) | 5.16 | 2.53 |
| worst single flock tick (kill burst) | 73 ms | 6.5 ms |

Regression after the pass (`-BirdTest=birds`, video parts 2–4) is unchanged:
* spear, rock and damage kills;
* ragdolls resting on the ground;
* the feeding chain end to end, from dive to swallowed;
* no overlap between birds.

## Bone names (for replacement models)
`root, pelvis, spine_01, spine_02, neck_01..03, head, jaw, tail, tailfan_[l|r]_01..03, clavicle_[l|r], upperarm_[l|r],
lowerarm_[l|r], hand_[l|r], prim_[l|r]_01..10, sec_[l|r]_01..N, tertial_[l|r], thigh/shin/tarsus/toes_[l|r]`.
Model faces +X, up +Z, origin under the feet; `BodyHeight` = body centre above feet. Required for ragdoll: pelvis, spine_02,
neck_01, head, jaw, tail (+ wings/legs optional). Required for beak/look: jaw, head, neck_02/03.
Re-export clips with the same names (A_<Species>_Perch/Walk/Glide/Flap/Hover) and run `Exports/Birds/setup_birds.py`
(it also regenerates the LODs).

## Assets
`/Game/Prophecy/Creatures/Birds/` — `Materials/M_Bird_Body | M_Bird_Feathers | M_BirdFeatherFX`, `SM_BirdFeatherFX`,
`Gull/`, `Kingfisher/` (SK, anims, MIs, textures). Re-import: `UnrealEditor-Cmd <uproject> -ExecutePythonScript=Exports/Birds/setup_birds.py -BirdSetupQuit -unattended -nullrhi`.

## Measured (beach test scene, 8 gulls + 4 kingfishers, 60 Hz)
| | |
|---|---|
| Flock tick (all birds + feathers) | 0.19–0.26 ms avg for 12 birds (see Performance) |
| Bird–bird overlap | none: closest pair ≥ 1.3–1.6× the no-overlap radius over the whole run, 0 hard corrections |
| Orientation snaps (> 480°/s) | 0 |
| Flight acceleration spikes (> 3 g) | 4 per 40 s (end of landing approaches) → addressed by the stopping-distance descent limit |
| Spear (fast tagged shaft through a perched gull) | killed, ragdoll on the ground, 70 feathers |
| Lethal point damage on a flying kingfisher | killed in the air, falls, 45 feathers, rests on the ground |
| Small damage | 9 feathers + flight |
| Rock (6 kg ball dropped on a perched gull, moved by the project's physics, no Chaos velocity) | killed at contact (measured 997 cm/s, momentum 5982 kg·cm/s), bleeds |
| Idle life (12 birds, 60 s) | ~67 turns on the spot + ~38 shuffles + 10 walks; separation still ≥ 1.5× the no-overlap radius |
| Feeding (test: struggle shortened to 12 s) | sent fishing → over the water 3.4 s → hovered 2.6 s → dive 1.3 s (reached −29 cm under the surface) → caught, emerged 0.4 s → landed on the beach 2.5 s later → held the fish until still (9 s) → dropped and pecked 7 s → left the remains; a gull 15.6 m away claimed them 1.2 s later, landed, walked up and swallowed them whole 11.7 s after claiming (fish actor destroyed) |
| Feathers | a spear kill on the sand scatters them over ~3 × 1 m downwind in the 1.5 m/s breeze; a kingfisher shot in flight leaves a trail of feathers |
| Blood | spear: entry stain on the folded wing / body + exit stain, follows the ragdoll; flock tick max 4.3 ms with Blood Splat off |
| Mesh facing / bank sign | head along actor forward (dot 0.9 in flight); right bank lowers the right wing |

## Tests
`-BirdTest=birds` (stills, 40 s trajectory capture, threat flush, spear / rock / damage kills, wound) and
`-BirdTest=video -BirdVideoPart=1|2|3|4|5` → `Saved/BirdTest/<run>/report.txt`, `traj.csv`, PNG / JPEG frames.
`-BirdTest=perf` → `BIRDPERF {...}` lines in the log, one per window. Each line has frame, game, render and GPU ms, plus
the flock tick split into simulate / probe / separation / visuals / feathers / scans.
