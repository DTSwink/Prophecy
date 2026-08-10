# Prophecy Standalone Simulation

A lightweight deterministic C++ locomotion lab with a raylib viewer. It contains a plane and persistent configurable blue Hero/red Villain counts driven by the walk/run root mover designed for the accepted neural-animation datasets.

Agents begin Idle with sheathed swords and their initial head search already complete. Current sight can wake them; an unrecognized opponent behind them remains unknown unless a qualifying locomotion sound causes an investigation that establishes visual recognition. A sound-confirmed enemy still running toward the listener triggers a timed draw while walking away; an empty bounded look-around returns a drawn sword to its sheath through the timed action path.

Post-battle cleanup uses that same bounded look-around. It is disabled while any opposing agent remains standing; after the last standing enemy falls, every visible non-dead enemy found by the sweep becomes an active finishing target. Clearing that set naturally starts another sweep, so newly visible survivors can be found without omniscient acquisition.

Standing combat uses load-aware perceived-target assignment at five hertz with a stable target commitment. Each attacker receives a deterministic personal approach role relative to its initial target line: some retain center pressure while most take left/right side or rear-quarter routes. Eight soft sectors, target-local load balancing, and cross-target ally spacing blend into the normal mover stick. Distant containment is almost direct pursuit; its diagonal spacing ramps up smoothly as opponents approach, producing separated curved contact without exact formation slots, collision, pathfinding, or squad synchronization.

With a drawn sword, standing attacks default to an 80-percent sword / 20-percent melee choice. A non-parried completed attack has a configurable 50-percent chance to skip normal cooldown and attack again on the next fixed tick; parry always enforces its separate configured cooldown. Grounded finishing never uses cooldown retreat or strafe.

The core also supports persistent club entities. Explicit pickup takes 1.0 second, first sheathing a drawn sword; explicit drop takes 0.1 second and leaves the club available to another agent. Club attacks reuse sword clips but apply melee-gauge damage. Club parries are silent, while a real-sword clash makes nearby Idle agents investigate the opposing participant. Training-camp club sources and autonomous club decisions are not implemented yet.

Crawling uses a separate Walk-derived mover mode with independently persistent speed and turn scales, both defaulting to 20 percent. Current crawling behavior supplies zero autonomous speed-stick input and cannot fight, follow, perform the automatic post-battle left/right sweep, promote finishing targets, or sheathe. It retains perception and recognition, however: heard footsteps and real-sword clashes use the normal sound-investigation head turn before look returns to root heading. The scaled controller remains ready for later non-combat crawl behavior without adding a second root-motion path. Entering a grounded state immediately releases a drawn sword or held club, while an owned sheathed sword remains equipped.

## Build

```powershell
cd StandaloneSim
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Configuration Release
```

The desktop shortcut launches the hidden live-build watcher. Source and data changes rebuild and replace the viewer without taking foreground focus.

## Controls

- `Z Q S D`: fly
- `Shift`: flight boost
- Left-drag empty viewport: no camera action
- Right drag: look
- Mouse wheel: dolly the camera
- Double-click an agent: enter follow camera
- Click an agent: select it and show its detailed state
- While paused, left-drag an agent: translate it on the ground without changing velocity
- While paused, `Ctrl` + left-drag an agent: rotate it toward the mouse on the ground
- `Enter`: follow the selected agent
- While following: right drag orbits and the wheel changes distance
- `Z Q S D`: leave follow and resume free-camera control
- `Space`: play/pause
- Square Stop toolbar icon: reset the same run to tick zero and pause
- `Left` / `Right`: one simulation tick; hold for continuous stepping
- `Ctrl` + `Left` / `Right`: one simulation second; hold for continuous stepping
- Keyboard stepping preserves the current play/pause state
- Seed field: Enter or click away to restart at tick zero and autosave the seed
- Camera toolbar icon: capture the current simulation window
- Save-layout toolbar icon: persist current agent translation/facing for future restarts

Editable Hero/Villain counts from zero through 100 sit in the simulation header beside seed and tick, and zero-versus-zero is valid. Committing either count restarts tick zero with the same seed and immediately persists both counts without saving unrelated pending option edits. Saved opening transforms are team-relative; extra agents are deterministically placed inside the saved layout bounds and added to the saved layout. Options are split into Cam, Move, Fight, Tact, Wnd, Look, Sens, and Snd tabs. Move contains Crawl speed and Crawl turn as Walk-relative percentages; Fight contains normal/parried cooldown, follow-up chance, drawn-sword attack chance, parry split, and per-clip stun; Tact contains target commitment, flank influence distance, early spread strength, angle jitter, radius jitter, and ally spacing radius; Sens contains recognition retention, vision range/angle, running-toward leeway, and failed-investigation memory; Snd contains event reach and its visualization toggle. Save persists every option, while Reset to Saved restores the saved profile. Seed changes autosave independently, and the shuffle button persists its generated value too.

## Diagnostics

```powershell
.\build\viewer_raylib\Release\prophecy_viewer.exe --headless-benchmark
```

While the viewer is open, `http://127.0.0.1:17831/snapshot` returns pull-only locomotion, engagement context, perception including post-battle finishing targets, timed-action/weapon, persistent-club, wound, head-look, and deterministic sound-event state. Start with `--no-telemetry` to remove the endpoint entirely.

### Unreal collision debug snapshot

The viewer automatically loads the persistent manual bake at `data/unreal_collision.json`; workspace builds prefer the canonical source copy and portable builds fall back to their packaged copy. Use `--environment-collision <path>` to inspect a different snapshot. An open viewer checks the chosen file twice per second, waits for a changed write to remain stable, and atomically reloads it while retaining the previous valid geometry if parsing fails. The landscape cache is regenerated only when the user explicitly requests it, never on PIE or viewer launch. The 600 MB collision JSON and its 101 MB render cache are generated local artifacts and intentionally excluded from Git; the compact navigation artifact remains versioned.

The current `/Game/mybasic` cache contains two exact flat plane quads and every original triangle outside those plane rectangles. The main landscape plane is at `Z=0 m` and retains 102,870 shore/boundary triangles; `Landscape2` is at `Z=0.0250104 m` and retains 14,630. It also contains the four exact water quads, the ten prior house actors plus the 3,341-triangle forced-complex `tent`, all 11 forced-complex actors in folder `Hay` at 1,136 triangles each, 628 exact world-transformed complex fence instances, all 15 mountain actors from `mountains1`, and all 16 from `mountains2`. Hay uses yellow RGB `(228,190,58)`. The latter mountain folder includes the 98,647-triangle `slave mountain`. Fences contribute 2,224,099 triangles, mountains contribute 226,218, and the complete cache is 701 objects and 4,158,798 triangles. Mountains use warm rock-grey RGB `(218,210,210)` and cache one flat color per exact triangle from its geometric normal, with 68% ambient, 24% two-sided directional detail, and up to 8% upward sky fill. No tolerance, smoothing, decimation, or height approximation is applied to the retained landscape triangles. Landscape hole/material masks remain an explicit v1 limitation.

Coordinates use the shared sim convention—meters, X/Y ground plane, Z up—after the full Unreal world transform. The JSON remains authoritative. An unchanged snapshot loads prelit immutable GPU buffers from the versioned `unreal_collision.json.rendercache` sidecar after validating the JSON size and write time. A missing or stale sidecar triggers one JSON parse, static-light bake, GPU upload, and sidecar refresh. Mountain render vertices are split per triangle in that cache so their exact complex faces remain visually distinct; other surfaces retain smooth vertex-normal shading. Normal frames keep the cheap vertex-color path and do no environment rebuild, allocation, or lighting work. This remains visualization input only: it never enters `sim_core` or influences intent or movement, and the final embedded product can omit it entirely.

Press `P` to capture the current simulation window. Captures persist as numbered files under `%LOCALAPPDATA%\ProphecyStandaloneSim\screenshots\` (for example, `screenshot-000017.png`), continue their sequence across launches, and visibly stamp the camera position, yaw, pitch, and FOV into the image. The current capture number remains visible at the lower right, and a brief light white flash confirms a successful save. There is no toolbar screenshot button.

### Village navigation crowd test

`data/mybasic.navbin` is the manually rebuilt static Detour navigation artifact; viewer launch never rebakes it. It uses a 0.30 m agent radius, 1.72 m height, 0.30 m maximum climb, and 44.765083-degree maximum slope. Exact bench-top source triangles and tent surfaces rising above the climb allowance are nonwalkable, and the artifact disables 423 house-roof/tent-exterior polygons while preserving covered interior floors and stairs. The 100-agent village test loads one shared navmesh and Detour crowd, retains per-agent corridors, and uses the shared path queue, proximity grid, turn anticipation, and sampled avoidance steering. Its connected pool contains 701 destinations, including 40 attic polygons, and every fifth assignment deliberately requests an attic. Avoidance can steer around another agent but cannot stop movement or impose a hard capsule barrier; agents keep path intent and may overlap/pass through. Navigation updates at 15 Hz inside the 30 Hz simulation and visible positions extrapolate between solves.

```powershell
.\build\viewer_raylib\Release\prophecy_viewer.exe `
  --scenario .\data\village_crowd_debug.json `
  --navigation-crowd-test
```

The bottom overlay reports rolling navigation cost, trips, attic assignments, active jams, and preventive clears. `N` toggles the walkable-surface visualization. The persisted `X-ray agents` Camera option defaults off, so structures normally occlude agents. Crowd Walk animation uses cumulative travelled distance and retained facing instead of recomputing phase from instantaneous velocity. `B` and `R` still spawn visible regular blue/red agents under the cursor while this test is active. For a render-independent five-minute measurement, run `prophecy_navigation_crowd_benchmark.exe data\mybasic.navbin`; its timer excludes baking, loading, target-pool construction, its deterministic distant/face-to-face behavior probe, and rendering. The regression fails if agents do not sidestep when separated, fail to keep moving when face-to-face, produce a jam/corner stall, or reach a mean cost of 0.5 ms.

Use `--capture build/captures/frame.png --capture-tick 120 --background-reload --no-telemetry` to capture an exact rendered tick without taking focus. Configure a shipping-style core without rewind using `-DPROPHECY_ENABLE_REWIND=OFF`.
