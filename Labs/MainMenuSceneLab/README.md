# Crimson water scene

Isolated Unreal 5.7 main-menu scene prototype: a crimson bed, live shallow water,
animated mannequin, physical rain streaks, volumetric cold smoke and wet-body
pearling. The game menu artwork remains separate. The main project and engine
assets are unchanged.

## First checkout and launch

The repository includes the curated mannequin dependencies, prepared materials
and lab Niagara systems. With Unreal 5.7 installed at the launch scripts' engine
path, run from this directory:

```powershell
./Build.ps1
./Open.ps1 -Visible
```

Use `./Prepare.ps1 -Wait` after changing material or Niagara preparation code.
It regenerates lab assets through Unreal Python and the native preparation
helpers, with project-identity guards and CPU/GPU compilation checks. The scripts
currently target `C:/Program Files/Epic Games/UE_5.7`; adjust that engine path if
installed elsewhere. Generated binaries, caches and recovery snapshots stay local.

The curated source-copy hashes are in `Resources/asset-provenance.json`.
`Tools/copy_assets.py` records the original main-project dependency selection;
it is not required on a checkout containing the copied Content assets.

## Scene interaction and saving

- Tab hides/shows the panel and gizmo.
- Click the mannequin to reveal red X/depth, green Y/sideways, blue Z/height
  handles. Drag an arrow to move the actual mesh and water colliders.
- Escape cancels a drag or deselects. Empty-space click deselects.
- WASD moves the mannequin while retaining the chosen height.
- Space toggles the authored side-step demonstration. P pauses the scene.
- Reset position, above Save/Revert on every tab, restores the starting location
  and heading. R additionally resets the water and animation time.
- F12 captures the viewport to `Saved/Captures/latest.png`.

Gizmo movement works while paused. Position limits are 450 cm horizontally from
the start and -30 to 400 cm vertically. Close-up camera follow waits until a drag
ends. Placement persists as `body_offset_x/y/z`.

Save look writes `Resources/scene.json` atomically and retains a local `.previous`
copy. Revert reloads the saved look. Live edits checkpoint after 250 ms idle and
on normal shutdown to `.recovery`; startup restores them only if the exact saved
file baseline still matches. A launcher `-Settings` path uses that file instead.

Before an authorized rebuild, run `./SaveLive.ps1`. It requests a save from the
exact running lab through `Saved/save-look.request`, waits for acknowledgement,
and checks the disk write. Do not ask the user to save repeatedly. The user
authorizes automatic save/close/normal-build/reopen of this isolated lab. Retained
native layout changes require a normal build, not Live Coding.

## Controls

There are 34 sliders across five tabs, plus actions and the resting-contact switch.

| Ground | Water | Rain | Air | Body |
| --- | --- | --- | --- | --- |
| Pattern size | Push strength | Density | Density | Wetness |
| Broad forms | Motion threshold | Drop width | Bank height | Bead density |
| Dark areas | Contact softness | Streak length | Lower edge | Bead size |
| Contrast | Damping | Brightness | Edge softness | Bead relief |
| Background ripple | Wave relief | Turbulence | Horizontal width | Trails |
| | | Fall speed | Drift speed | Runoff speed |
| | | Slant | Rolling motion | |
| | | Surface impact | Left / right | |
| | | Ripple size | Middle mist | |

The launcher accepts `-Ground`, `-Water`, `-Air`, and `-BodyCloseup`.
Body's close-up button returns to the whole scene on its next press.

## Ground and water

Ground uses a warped phase field with long curves and finer following strands.
Pattern size changes its world scale. Broad forms blends from fine grain to the
flowing pattern; Dark areas preserves the deeper black option. This is material
relief rather than coarse-mesh displacement. Background ripple controls only the
small ambient water normals; zero retains rain and contact waves.

The mannequin drives Epic WaterAdvanced/NiagaraFluids shallow water in the lab's
`NS_CrimsonShallowWater`: a 512-square grid over 10 m and a 3.5 cm puddle. The
engine solver and modules are unchanged; preparation links lab call inputs to
the live controls:

- Push strength, 0–3x, controls collision velocity transfer. Zero blocks new input.
- Motion threshold, 0–20 cm/s, rejects small horizontal contact movements.
- Contact softness, 0.5–20 cm, changes the collision coupling falloff distance.
- Damping, 0–100%, increases friction and velocity dissipation on a square curve.
  Zero retains friction 0.00025 and dissipation 0.0003; maximum is 0.01 and 0.05.
- Wave relief, 0–3x, changes visible collision-wave slopes, independently of rain
  and simulation energy.

By default, actual submerged PHAT-body motion gates the collision provider.
Center and six extent samples account for rotation; an 80 ms release hold avoids
sampling flicker. **Allow resting contact (legacy)** keeps stationary shapes in
the solver and reproduces the older resting disturbance. Inactive shapes do not
remain solid fluid boundaries. Pure vertical forcing retains the stock solver's
horizontal-velocity limitation.

**Try calmer contact** sets push 0.6x, threshold 5 cm/s, softness 4 cm, damping
30%, resting contact off, and clears waves. **Clear existing waves** resets only
water, including its displayed field while paused; position and settings remain.
Clear old waves when comparing settings because raising a threshold cannot
instantly remove an existing wake.

## Rain and wet mannequin

Rain uses 98,532 instanced streak seeds in four independent jittered layers.
Density spans four times the original capacity: old 80% is now 20%; old 100% is
now 25%. Stored `rain_amount` remains in original units, 0–4. Width stays in
world units, so near and distant drops project differently. No screen overlay or
minimum screen-width clamp is used. Brightness and length help subpixel drops read.

Each seed has a paired analytical surface impact using the same position/clock.
At speed 1, the 1.6 s clock has a 1 s fall; impacts last 1.05 s and expand at
28 cm/s. Surface impact and Ripple size are independent. Directional antialiasing
and shallow refraction keep the rings visible in reflected light and the bed.
These are inexpensive material rings, separate from the real collision solver.

Try fine storm applies a dense narrow-drop preset. Density zero disables the
rain renderer and clock. Presets live in `Resources/presets/`.

The wet mannequin uses UV-attached clearcoat beads and bounded runoff along the
surface's gravity tangent. Wetness zero restores the dry coating; Runoff speed
zero holds droplets still. Runoff does not transport fluid across UV seams.

## Smoke and horizontal width

Smoke uses Epic NiagaraFluids `Grid3D_Gas_Smoke`, duplicated as `NS_UpperGasSmoke`,
with the native heterogeneous volume renderer. It is a real GPU gas field.
The source emits downward; density buoyancy returns it upward and vorticity
curls the flow. Temperature is zero. Drift speed changes the downward/return
pace, while Rolling motion controls curl. Zero drift pauses the gas.

**Horizontal width**, 0.25–8x, widens the actual source along world Y (left/right
on screen) through Epic's **Non Uniform Scale** input `(1,width,1)`. Height,
depth, center and vertical flow settings remain independent. Width 1 preserves
the earlier source shape. The old `haze_spread` remains as a compatibility
baseline; it mostly enlarged the container while the spherical radius capped
at 240 cm. The new control persists as `smoke_horizontal_width`.

The domain grows when necessary to fit the source plus 450 cm of return space
at either end. Resolution follows the previous cell size, capped at 512 along
the longest axis. A required resize waits 300 ms after the last size change and
restarts the gas once; let it reform for a few seconds. Width changes within the
existing domain affect the source without clearing it. Wider grids cost more GPU
memory. The volume is not a stretched 2D image.

Bank height moves the gas container. Lower edge and Edge softness control the
independent world-space crop that keeps the center black. Left / right moves
source and container together by up to 1,000 cm. Middle mist is separate and can
fill the center; leave it zero for black. Density zero disables smoke rendering
and pauses its simulation. Cold smoke / black center applies the corresponding
preset and resets horizontal width to 1x. Nothing has been baked yet.

## Verification

Normal build and native Niagara CPU/GPU preparation are checked before reopening.
`Open.ps1 -Capture -Offscreen -Settings <saved-test-file> -PoseTime 12 -Name <name>`
renders an isolated capture without desktop input. `-ValidateControls` and
`-ValidateGizmo` run shared native callbacks only with a settings file under Saved.
`-MoveTest` exercises translation; `-FreezeBody` isolates a stationary pose.
Never point diagnostic settings at the user's live look.

Local receipts include `Saved/Validation/weather-controls.json`,
`collision-controls.json`, `collision-response.json`, `mannequin-gizmo.json`, and
`smoke-width.json`. Captures and logs remain local rather than in Git.

The frozen-pose collision comparison measured mean squared XY normals 0.000397816
with the legacy provider versus exactly zero with the movement gate. The calmer
preset gave zero over an 8 s animated idle and a nonzero wake after 90 cm travel.
These are scene-specific behavior checks, not a general fluid-accuracy benchmark.
Gizmo checks cover actual picking, XYZ translation, scaled viewport geometry,
paused lifting, cancel, save/reload, reset and empty-space deselection.

The current handoff and dated visual evidence are in `Docs/WeaponWheelUI.md` at
the repository root. Refer to that document before restoring older test settings.
