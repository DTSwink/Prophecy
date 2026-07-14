# Prophecy Standalone Simulation

A lightweight deterministic C++ locomotion lab with a raylib viewer. The current slice contains a plane and two opposing agents driven by the walk/run root mover designed for the accepted neural-animation datasets.

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
- `Enter`: follow the selected agent
- While following: left drag orbits and the wheel changes distance
- `Z Q S D` or right drag: leave follow and resume free-camera control
- `Space`: play/pause
- `Left` / `Right`: previous/next simulation tick

All adjustable options are camera visualization settings. Hover transport icons for their names.

## Diagnostics

```powershell
.\build\viewer_raylib\Release\prophecy_viewer.exe --headless-benchmark
```

While the viewer is open, `http://127.0.0.1:17831/snapshot` returns pull-only locomotion state. Start with `--no-telemetry` to remove the endpoint entirely.

Use `--capture build/captures/frame.png --capture-tick 120 --background-reload --no-telemetry` to capture an exact rendered tick without taking focus. Configure a shipping-style core without rewind using `-DPROPHECY_ENABLE_REWIND=OFF`.
