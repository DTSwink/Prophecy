# UI Workshop — Constellation weapon wheel

Independent **UE 5.7 project**, third visual checkpoint of the UI workstream. It does
not load Prophecy's map, plugins, agents, physics or Blueprint wiring. The main
editor can stay open. Scope is visual composition and selection; equipping,
inventory, gameplay input capture and shipping integration come after review.

## Open

Run `Open.ps1` (PowerShell). The window is named **Prophecy · UI Workshop —
Checkpoint 03**. The existing UE 5.7 installation runs it in `-game` mode.
This is native Slate UI over the original forest image, not a baked mockup.

- Move the mouse around the wheel, or use arrow keys, to select a weapon.
- Click confirms the preview selection. No gameplay action is connected yet.
- **Tab** opens/closes the wheel and its background blur.
- **R** opens the settings panel; **P** hides the lab footer for a clean view.
- **F5** reloads `Resources/wheel.json`; **F12** saves `Saved/Captures/latest.png`.
- **Save settings** persists the sliders and selected weapon to JSON.

**Overall UI size** scales the complete wheel around its center, including
weapons, type, shadows and glow. The forest and settings panel keep their size.
Mouse hit testing uses the same scale. The upper limit fits the current radius
inside the canvas; reducing the radius allows a higher scale factor.

**Selection color…** opens Unreal's color picker with live preview, wheel,
RGB/HSV and hex controls. It colors both the crescent and its halo while keeping
the bright core and star readable. Cancel restores the starting color. **Selection
glow** adjusts the soft halo separately from the sharp selection strokes.
Save settings persists scale, glow strength and the color's linear RGB channels.
The original user preset from checkpoint 02 is retained in
`Resources/checkpoint-02-user-preset.json`; all its existing values are preserved
in the active file. Only the three new fields were added.

The three darkness sliders are independent: **Weapon circle darkness**,
**Connecting arc darkness**, and **Name backdrop darkness**. The connecting
shadow is a curved annulus with the weapon interiors masked out, not straight
rectangular links. The center backdrop has its own opacity. Existing `shadow`
JSON values continue to control the weapon circles; the new fields are
`arc_shadow` and `label_shadow`.

The linework also has three independent brightness sliders (0–1):
**Center brightness** controls the name and its surrounding stars, diamonds and
lines; **Circle line brightness** controls the weapon-ring lines and ornaments;
**Connecting line brightness** controls the linking arcs and their stars/pearls.
They replace the shared Ornament brightness control. Center defaults to 1;
circles/connectors inherit the previous saved ornament brightness. Selection
glow/color, icons and darkness are separate. The pre-split user preset is retained
in `Resources/checkpoint-03-user-preset.json`. New fields are `center_brightness`,
`circle_brightness` and `connecting_brightness`; `ornament_opacity` is retained
only for backward compatibility with older presets.

**Center font size** changes just the label (12–36, whole steps, default22).
**Center decoration size** independently scales all surrounding stars, diamonds
and lateral lines together (0–1.5, default1; zero hides them). Text size cannot
move or resize decorations: their layout uses the original22-point label width.
Decoration size scales their positions, dimensions and line thicknesses about
the center; the name backing stays separate. Save settings persists
`center_font_size` and `center_decoration_size`. The pre-change preset is retained in
`Resources/pre-font-size-user-preset.json`.

Settings do not auto-save every mouse movement. `wheel.json` is the shared,
human-readable state for future sessions and agents. Manual F5 reload avoids a
background file watcher. Editing source requires closing only this lab window,
running `Build.ps1`, then opening it again. No Live Coding or main-editor restart.

## Modules and assets

| Part | Location | Responsibility |
| --- | --- | --- |
| Layout and data | `Private/WheelModel.h`, `Resources/wheel.json` | Eight sectors, English names, hit testing and persistent tuning |
| Visual layers | `Private/WheelPainter.h` | Local feathered shadows, orbit lines, stars, dots, selected crescent and center label |
| Orbit art direction | `Private/WheelOrnaments.h` | Eight distinct ring profiles, inner sweeps, star anchors and constellation spacing |
| Soft masks | `Private/WheelMasks.h` | Smooth name veil and localized selection/star halos |
| Texture filtering | `Private/WheelTextures.h` | One-time alpha-weighted mip generation and trilinear icon sampling |
| Interaction | `Private/SWeaponWheel.h` | Atlas sampling, hover/click, keyboard, blur, review controls |
| Isolated host | `Private/WeaponWheelLab.cpp` | One-shot viewport attachment and native screenshot capture |
| Weapon drawings | `Resources/weapons.png` | One 4×2 RGBA atlas; each weapon can later become its own asset |
| Background | `Resources/forest.png` | User's original screenshot, blurred live by Slate |
| Art direction | `Resources/concept-reference.png` | Approved “Local shadows” reference |
| Provenance | `Resources/provenance.json` | Generation prompt, source and font notes |

`Private/` is under `Source/WeaponWheelLab/`. Background, local shadows,
ornaments, icons and selection are separate layers. Soft shadows share one
64×64 procedural alpha texture (16 KB) rendered as tinted quads. The name uses
its own continuously fading 256×128 veil, with no flat oval center. Local glow
uses a 256×256 crescent mask and 128×128 Gaussian spot, generated once. A separate
512×512 annular mask (1 MB) is rebuilt only when the wheel radius changes.
Geometry and icon selection
are wrapped in a Slate invalidation panel. No custom per-frame UI tick, polling
service, physics or scene simulation is added. Blur has a rendering cost while
the wheel is open; production GPU cost has not been benchmarked at this stage.

Checkpoint 02 enables native game-window DPI awareness, so Windows no longer
enlarges a low-resolution UI bitmap. The default capture is 1024×949 physical
pixels. Icons use a neutral monochrome replacement atlas and an 11-level
trilinear mip chain, filtered in linear space with alpha weighting to avoid
aliasing and transparent-edge contamination. This happens once on load, not
per frame. Dots, four-point stars and tapered selection ribbons have explicit
screen-pixel coverage fringes; curves are tessellated at roughly 1.5 design
pixels per segment. Main orbital arcs are concentric circles connecting the
weapon rings. All eight weapon centers share one
radius. These are native UI rendering changes, not extra 3D antialiasing passes.

Checkpoint 03 replaces the repeated dashed outer rings with eight authored
elliptical orbit arrangements: different tilts, gaps and interior curves.
Their pearls and stars lie on the same evaluated curves, and connecting-arc
stars are also anchored directly to their lines. Sparse pinpoints replace the
regular dash cadence. The bomb's fuse spark follows the icon-size control.
The glow is a lightweight local UI effect; it does not enable scene bloom.

Typography currently reads Georgia from the local Windows installation, with
an engine-font fallback. No Windows font is copied or redistributed. Choose a
redistributable font before shipping.

## Build and captures

`Build.ps1` builds only this standalone editor module incrementally using the
installed dynamic-RAM worker scheduler. `-NoHotReloadFromIDE` prevents UBT's
engine-wide Live Coding mutex from directing this unrelated DLL toward the
main editor. It is safe here because that editor has never loaded this project.
The module disables shared precompiled headers: its single translation unit
compiled in about 23 seconds without retaining a 2.4 GB UnrealEd PCH.

`Open.ps1 -Capture` runs a separate temporary lab instance, captures a clean
checkpoint image, checks the input handlers against the actual scaled canvas,
and exits that instance. It does not operate the desktop or
another Unreal process. Avoid launching it over an existing lab review session.
Add `-StayOpen` to leave that instance open for the user's review after capturing.
Generated build artifacts and captures stay ignored. Keep only a small number
of review captures; do not copy the main project's content or DDC here.

Slate blur behavior: [Epic SBackgroundBlur reference](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Slate/SBackgroundBlur).
