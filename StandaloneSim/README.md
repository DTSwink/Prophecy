# Prophecy Standalone Simulation

A lightweight deterministic C++ locomotion lab with a raylib viewer. It contains a plane and persistent configurable blue Hero/red Villain counts driven by the walk/run root mover designed for the accepted neural-animation datasets.

Agents begin Idle with sheathed swords and their initial head search already complete. Current sight can wake them; an unrecognized opponent behind them remains unknown unless a qualifying locomotion sound causes an investigation that establishes visual recognition. A sound-confirmed enemy still running toward the listener triggers a timed draw while walking away; an empty bounded look-around returns a drawn sword to its sheath through the timed action path.

Post-battle cleanup uses that same bounded look-around. It is disabled while any opposing agent remains standing; after the last standing enemy falls, every visible non-dead enemy found by the sweep becomes an active finishing target. Clearing that set naturally starts another sweep, so newly visible survivors can be found without omniscient acquisition.

Standing combat uses load-aware perceived-target assignment at five hertz with a stable target commitment. Each attacker receives a deterministic personal approach role relative to its initial target line: some retain center pressure while most take left/right side or rear-quarter routes. Eight soft sectors, target-local load balancing, and cross-target ally spacing blend into the normal mover stick to produce separated curved approaches without exact formation slots, collision, pathfinding, or squad synchronization.

The core also supports persistent training-stick entities. Explicit pickup takes 1.0 second, first sheathing a drawn sword; explicit drop takes 0.1 second and leaves the stick available to another agent. Stick attacks reuse sword clips but apply melee-gauge damage. Stick parries are silent, while a real-sword clash makes nearby Idle agents investigate the opposing participant. Training-camp stick sources and autonomous stick decisions are not implemented yet.

## Build

```powershell
cd StandaloneSim
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Configuration Release
```

The desktop shortcut launches the hidden live-build watcher. Source and data changes rebuild and replace the viewer without taking foreground focus.

## Controls

- `Z Q S D`: fly
- `Shift`: flight boost
- Left drag: look
- Right drag: pan in the camera view plane, with direct drag direction
- Mouse wheel: dolly the camera
- Double-click an agent: enter follow camera
- Click an agent: select it and show its detailed state
- While paused, left-drag an agent: translate it on the ground without changing velocity
- While paused, `Ctrl` + left-drag an agent: rotate it toward the mouse on the ground
- `Enter`: follow the selected agent
- While following: left drag orbits and the wheel changes distance
- `Z Q S D` or right drag: leave follow and resume free-camera control
- `Space`: play/pause
- Square Stop toolbar icon: reset the same run to tick zero and pause
- `Left` / `Right`: one simulation tick; hold for continuous stepping
- `Ctrl` + `Left` / `Right`: one simulation second; hold for continuous stepping
- Keyboard stepping preserves the current play/pause state
- Seed field: Enter or click away to restart at tick zero and autosave the seed
- Camera toolbar icon: capture the current simulation window
- Save-layout toolbar icon: persist current agent translation/facing for future restarts

Editable Hero/Villain counts from zero through 100 sit in the simulation header beside seed and tick, and zero-versus-zero is valid. Committing either count restarts tick zero with the same seed and immediately persists both counts without saving unrelated pending option edits. Saved opening transforms are team-relative; extra agents are deterministically placed inside the saved layout bounds and added to the saved layout. Options are split into Cam, Fight, Tact, Wnd, Look, Sens, and Snd tabs. Tact contains target commitment, flank influence distance, angle jitter, radius jitter, and ally spacing radius; Sens contains recognition retention, vision range/angle, running-toward leeway, and failed-investigation memory; Snd contains event reach and its visualization toggle. Save persists every option, while Reset to Saved restores the saved profile. Seed changes autosave independently, and the shuffle button persists its generated value too.

## Diagnostics

```powershell
.\build\viewer_raylib\Release\prophecy_viewer.exe --headless-benchmark
```

While the viewer is open, `http://127.0.0.1:17831/snapshot` returns pull-only locomotion, engagement context, perception including post-battle finishing targets, timed-action/weapon, persistent-stick, wound, head-look, and deterministic sound-event state. Start with `--no-telemetry` to remove the endpoint entirely.

The camera toolbar icon overwrites `%LOCALAPPDATA%\ProphecyStandaloneSim\latest-screenshot.png`, providing one stable path for immediate visual inspection without accumulating captures.

Use `--capture build/captures/frame.png --capture-tick 120 --background-reload --no-telemetry` to capture an exact rendered tick without taking focus. Configure a shipping-style core without rewind using `-DPROPHECY_ENABLE_REWIND=OFF`.
